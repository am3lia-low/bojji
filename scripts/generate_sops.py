"""Render ``data/sop_specs/*.yaml`` into the SOP corpus at ``data/sop/*.md``.

BUILD-TIME ONLY. Never imported by ``src/``.

The specs are the source of truth; the markdown is derived and must never be
hand-edited. Running this script is idempotent, so a spec change plus a re-run is
the only way the corpus changes.

Why generate rather than author markdown directly: the public-URL traceability
guarantee (``sop_design.md`` S8.2) is enforced here, not promised in a README.
Every fact carries a ``source`` handle, this script refuses to render a fact whose
handle does not resolve to a cited reference, and the rendered S2 prints the URL
beside the claim. A reviewer can therefore check any sentence in the corpus
against a page without leaving the file.

Three build-time checks run before anything is written, each guarding a design
property that would fail silently if it broke:

1. **Citations resolve.**  No fact may cite a handle absent from ``references``.
2. **The relief-cap holdout does not leak.**  No *indexed* spec may state the
   $80,000 personal relief cap as a fact. The cap is a property of the sum of all
   reliefs, so it cannot be derived from any single relief's rules — which is
   what makes SOP-REL-005 a genuine partial-answer holdout. If an indexed SOP
   restated it, the agent could answer the cap question from the index and the
   holdout would collapse into an ordinary answerable case.
3. **Held-out classes stay empty.**  ``rental_income`` and ``foreign_income_dta``
   must resolve to no indexed SOP, so that ``no_supporting_sop`` is *derived*
   from an empty lookup rather than hand-mapped (``BUILD.md`` S5.6).

Usage:
    python scripts/generate_sops.py            # render the corpus
    python scripts/generate_sops.py --check    # validate only, write nothing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SPEC_DIR: Final[Path] = ROOT / "data" / "sop_specs"
OUT_DIR: Final[Path] = ROOT / "data" / "sop"

#: Classes deliberately excluded from the index, yielding `no_supporting_sop`.
#: Listed here so the generator fails loudly if a holdout is ever un-held by
#: accident — the holdout is a design commitment, not an oversight.
HELD_OUT_CLASSES: Final[frozenset[str]] = frozenset({"rental_income", "foreign_income_dta"})

#: Marker for the leakage guard described in the module docstring.
RELIEF_CAP_MARKER: Final[str] = "80,000"

#: Prepended to every rendered SOP. The misrepresentation guard: a synthetic SOP
#: that reads like a real IRAS document is its own problem (`sop_design.md` S8.2).
BANNER: Final[str] = (
    "> **SYNTHETIC DOCUMENT.** Authored for a technical assessment. This is not an\n"
    "> IRAS document and does not reflect IRAS internal material, templates or\n"
    "> practice. Every factual claim is a restatement traceable to the public\n"
    "> source cited beside it in section 2.\n"
)


class SpecError(RuntimeError):
    """A spec violates a build-time guarantee."""


def load_specs() -> list[dict[str, Any]]:
    """Load every spec, sorted by ``sop_id`` for deterministic output."""
    specs = [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(SPEC_DIR.glob("*.yaml"))
    ]
    return sorted(specs, key=lambda spec: spec["sop_id"])


def check_citations(spec: dict[str, Any]) -> list[str]:
    """Return an error for every fact citing an unknown reference handle."""
    handles = {ref["id"] for ref in spec.get("references", [])}
    return [
        f"{spec['sop_id']}: fact cites unknown source {fact.get('source')!r} "
        f"-- {fact['text'][:60].strip()}..."
        for fact in spec.get("facts", [])
        if fact.get("source") not in handles
    ]


def check_relief_cap_leak(spec: dict[str, Any]) -> list[str]:
    """Return an error if an indexed spec states the global relief cap as a fact."""
    if not spec["indexed"]:
        return []
    return [
        f"{spec['sop_id']}: indexed spec states the ${RELIEF_CAP_MARKER} relief cap, "
        f"which belongs to the held-out SOP-REL-005 -- {fact['text'][:60].strip()}..."
        for fact in spec.get("facts", [])
        if RELIEF_CAP_MARKER in fact["text"]
    ]


def build_index(specs: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Map each class to its INDEXED SOPs. Held-out SOPs are excluded by design."""
    index: dict[str, list[str]] = {}
    for spec in specs:
        if not spec["indexed"]:
            continue
        for intent in spec["intents"]:
            index.setdefault(intent, []).append(spec["sop_id"])
    return index


def check_holdouts(index: dict[str, list[str]]) -> list[str]:
    """Return an error if a held-out class resolved to any indexed SOP."""
    return [
        f"{cls}: expected no indexed SOP (holdout), found {index[cls]}"
        for cls in sorted(HELD_OUT_CLASSES)
        if cls in index
    ]


def validate(specs: list[dict[str, Any]]) -> list[str]:
    """Run every build-time check and return all errors found."""
    errors: list[str] = []
    for spec in specs:
        errors += check_citations(spec)
        errors += check_relief_cap_leak(spec)
    errors += check_holdouts(build_index(specs))
    return errors


#: Frontmatter keys whose value must stay a string when the corpus is re-read.
#: ``version`` is the one that bites: an unquoted ``1.0`` round-trips as a float,
#: so ``"2.0" > "1.0"`` silently becomes a numeric comparison, and a hypothetical
#: ``1.10`` would order below ``1.9``. Supersession is part of the corpus's
#: deliberate complexity, so the field has to survive the round trip intact.
_QUOTED_KEYS: Final[frozenset[str]] = frozenset({"version"})

#: Characters that make a bare YAML scalar ambiguous or invalid. A colon is the
#: one that actually occurs here -- the redirect SOPs are titled
#: "Redirect: business and corporate income tax" -- and an unquoted colon makes
#: the whole document unparseable rather than merely misread.
_NEEDS_QUOTING: Final[re.Pattern[str]] = re.compile(r"""[:#\[\]{}&*!|>'"%@`]|^[-?]|^\s|\s$""")


def _fm_value(value: Any, key: str = "") -> str:
    """Render one frontmatter scalar or flow sequence, quoting where YAML needs it."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    text = str(value)
    if key in _QUOTED_KEYS or _NEEDS_QUOTING.search(text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def render_frontmatter(spec: dict[str, Any], urls: list[str]) -> str:
    """Render the YAML frontmatter — the integration seam the runtime reads.

    ``intents`` builds ``CLASS_TO_SOPS``; ``auto_reply_permitted`` and
    ``escalate_if`` build ``BUCKET``. Escalation policy is therefore corpus-derived
    rather than hardcoded, which is what lets an agency conform real SOPs to this
    schema and change system behaviour without touching code (`sop_design.md` S4).
    """
    lines = ["---", "synthetic: true"]
    for key in (
        "sop_id", "title", "version", "effective_date", "supersedes",
        "applies_to_ya", "intents", "indexed", "owner_queue",
        "handling_target", "auto_reply_permitted",
    ):
        lines.append(f"{key}: {_fm_value(spec.get(key), key)}")
    lines.append("escalate_if:")
    lines += [f"  - {item}" for item in spec.get("escalate_if", [])]
    lines.append("references:")
    lines += [f"  - {url}" for url in urls]
    lines.append(f"last_reviewed: {spec['references'][0]['fetched']}")
    lines.append("---")
    return "\n".join(lines)


def render_body(spec: dict[str, Any], ref_urls: dict[str, str]) -> str:
    """Render the officer-facing procedure: sections S1-S6 (`sop_design.md` S4)."""
    out: list[str] = [f"# {spec['sop_id']} - {spec['title']}", "", BANNER]

    if not spec["indexed"]:
        out += [
            "> **HELD OUT OF THE INDEX.** This procedure is authored but excluded "
            "from\n> the runtime lookup, so the classes it serves resolve to no SOP. "
            "See\n> `sop_design.md` S5.\n",
        ]

    out += ["## 1. Scope", "", spec["scope"].strip(), ""]
    if spec.get("not_in_scope"):
        out.append("**Not in scope:**")
        out += [
            f"- {item['text'].strip()} -> escalate (`{item['route_to']}`)"
            for item in spec["not_in_scope"]
        ]
        out.append("")

    out += ["## 2. Key facts the officer may state", ""]
    for fact in spec["facts"]:
        text = " ".join(fact["text"].split())
        out.append(f"- {text}  \n  <sup>Source: {ref_urls[fact['source']]}</sup>")
    out.append("")

    out += ["## 3. Decision steps", ""]
    for i, step in enumerate(spec["decision_steps"], 1):
        reason = f" (`{step['reason']}`)" if step.get("reason") else ""
        out.append(f"{i}. **If** {step['condition'].strip()}  \n"
                   f"   -> {step['action'].strip()}{reason}")
    out.append("")

    out += ["## 4. Approved phrasing", ""]
    for block in spec["approved_phrasing"]:
        text = " ".join(block["text"].split())
        out += [f"**`{block['id']}`**", "", f"> {text}", ""]

    out += ["## 5. Do not", ""]
    out += [f"- {' '.join(item.split())}" for item in spec["do_not"]]
    out.append("")

    out += ["## 6. Related", ""]
    out += [f"- {item}" for item in spec.get("related", [])] or ["- (none)"]
    out.append("")

    return "\n".join(out)


def render(spec: dict[str, Any]) -> str:
    """Render one spec to its complete markdown document."""
    ref_urls = {ref["id"]: ref["url"] for ref in spec["references"]}
    urls = [ref["url"] for ref in spec["references"]]
    return render_frontmatter(spec, urls) + "\n\n" + render_body(spec, ref_urls)


def _assert_round_trips(document: str, spec: dict[str, Any]) -> None:
    """Fail if the rendered frontmatter will not parse back to what the spec said."""
    _, _, rest = document.partition("---\n")
    frontmatter, _, _ = rest.partition("\n---\n")
    try:
        parsed = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        raise SpecError(f"{spec['sop_id']}: rendered frontmatter does not parse: {exc}") from exc
    for key in ("sop_id", "title", "version"):
        if str(parsed.get(key)) != str(spec[key]):
            raise SpecError(
                f"{spec['sop_id']}: {key} did not survive rendering -- "
                f"spec {spec[key]!r}, parsed back as {parsed.get(key)!r}"
            )
    if parsed.get("intents") != list(spec["intents"]):
        raise SpecError(f"{spec['sop_id']}: intents did not survive rendering")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = parser.parse_args()

    specs = load_specs()
    errors = validate(specs)
    if errors:
        print(f"FAILED: {len(errors)} error(s)\n", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    index = build_index(specs)
    indexed = [s for s in specs if s["indexed"]]
    facts = sum(len(s.get("facts", [])) for s in specs)
    print(f"validated {len(specs)} specs ({len(indexed)} indexed, "
          f"{len(specs) - len(indexed)} held out), {facts} facts, all citations resolve")

    if args.check:
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.md"):
        stale.unlink()  # derived output: regenerate from scratch, never merge
    for spec in specs:
        document = render(spec)
        # Round-trip before writing. The runtime loader parses this frontmatter
        # strictly and fails at startup on a malformed file, so a rendering bug
        # must surface here -- at build time, against the spec that caused it --
        # rather than as a startup failure with no indication of which field broke.
        _assert_round_trips(document, spec)
        (OUT_DIR / f"{spec['sop_id']}.md").write_text(document, encoding="utf-8")

    print(f"wrote {len(specs)} SOPs -> {OUT_DIR.relative_to(ROOT)}")
    print("\nCLASS_TO_SOPS (indexed only):")
    for cls, sops in sorted(index.items()):
        print(f"  {cls:26} -> {', '.join(sops)}")
    print(f"  {'(held out)':26} -> {', '.join(sorted(HELD_OUT_CLASSES))} => no_supporting_sop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
