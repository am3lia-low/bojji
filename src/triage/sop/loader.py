"""Load and validate the SOP corpus from ``data/sop/*.md``.

RUNTIME. Imported by the graph; must work with no API key and no network.

The corpus is a flat directory of ~17 markdown files, loaded and validated into
memory at startup. At that size there is no vector DB, no external service and no
index to rebuild, which is a large part of why the free-tier constraint is
satisfiable at all (``BUILD.md`` S4.1).

The frontmatter is the integration seam. ``intents`` builds ``CLASS_TO_SOPS`` and
``auto_reply_permitted`` plus ``escalate_if`` build ``BUCKET``, so escalation
policy lives in the corpus rather than in code: an agency holding real internal
SOPs conforms them to this schema and the system routes against them with no code
change (``sop_design.md`` S4, S12).

Validation is strict and fails at startup rather than at request time. A corpus
that cannot be trusted is worse than one that is absent, because the failure would
surface as a wrong routing decision on a citizen's email rather than as an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Final

import yaml

#: Default corpus location, relative to the repository root.
DEFAULT_SOP_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "data" / "sop"

#: Splits leading YAML frontmatter from the markdown body.
_FRONTMATTER_RE: Final[re.Pattern[str]] = re.compile(
    r"\A---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL
)

#: Frontmatter keys every SOP must carry.
_REQUIRED: Final[frozenset[str]] = frozenset({
    "sop_id", "synthetic", "title", "version", "intents", "indexed",
    "auto_reply_permitted", "escalate_if", "references",
})

#: Escalation trigger naming differs by layer, and the mismatch is a known trap
#: (``BUILD.md`` appendix). SOP frontmatter says ``amount_computation_requested``;
#: the runtime flag the router tests is ``computation_requested``. Aliasing here
#: means the rest of the runtime sees one vocabulary.
ESCALATION_ALIASES: Final[dict[str, str]] = {
    "amount_computation_requested": "computation_requested",
    "hardship_or_waiver_request": "hardship_or_waiver",
}


class CorpusError(RuntimeError):
    """The SOP corpus is missing, malformed, or violates a structural guarantee."""


@dataclass(frozen=True)
class SOP:
    """One loaded procedure: its routing metadata plus the body the drafter reads."""

    sop_id: str
    title: str
    version: str
    intents: tuple[str, ...]
    indexed: bool
    auto_reply_permitted: bool
    escalate_if: tuple[str, ...]
    references: tuple[str, ...]
    body: str
    path: Path
    effective_date: str | None = None
    supersedes: str | None = None
    applies_to_ya: tuple[int, ...] = ()
    owner_queue: str | None = None
    handling_target: str | None = None

    @cached_property
    def approved_phrasing(self) -> dict[str, str]:
        """Parse section 4 into ``{block_id: text}``.

        This is the template floor: in ``local`` mode the draft node emits these
        blocks with slots filled, so the reply cannot assert a fact absent from
        the SOP and groundedness holds by construction (``BUILD.md`` S5.8). That
        makes section 4 load-bearing rather than decorative, which is why it is
        parsed and validated rather than left as prose.
        """
        section = _section(self.body, "4. Approved phrasing")
        blocks: dict[str, str] = {}
        for match in re.finditer(
            r"\*\*`(?P<id>[^`]+)`\*\*\s*\n\s*\n>\s*(?P<text>.+?)(?=\n\s*\n|\Z)",
            section,
            re.DOTALL,
        ):
            blocks[match["id"]] = " ".join(match["text"].split())
        return blocks

    @cached_property
    def facts(self) -> tuple[str, ...]:
        """Section 2 claims, without their source annotations."""
        section = _section(self.body, "2. Key facts")
        return tuple(
            " ".join(re.sub(r"<sup>.*?</sup>", "", line).split())
            for line in re.findall(r"^- (.+?)(?=\n- |\n#|\Z)", section, re.MULTILINE | re.DOTALL)
        )

    @cached_property
    def escalation_triggers(self) -> frozenset[str]:
        """``escalate_if`` mapped into the runtime's flag vocabulary."""
        return frozenset(ESCALATION_ALIASES.get(t, t) for t in self.escalate_if)


def _section(body: str, heading_prefix: str) -> str:
    """Return the text under the ``## <heading_prefix>...`` heading, or ``""``."""
    match = re.search(
        rf"^## {re.escape(heading_prefix)}.*?$\n(?P<body>.*?)(?=^## |\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    return match["body"] if match else ""


def _parse(path: Path) -> SOP:
    """Parse one SOP file, raising :class:`CorpusError` on any structural problem."""
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise CorpusError(f"{path.name}: missing YAML frontmatter")

    try:
        meta: dict[str, Any] = yaml.safe_load(match["frontmatter"]) or {}
    except yaml.YAMLError as exc:
        raise CorpusError(f"{path.name}: unparseable frontmatter: {exc}") from exc

    if missing := sorted(_REQUIRED - meta.keys()):
        raise CorpusError(f"{path.name}: frontmatter missing {', '.join(missing)}")

    # The misrepresentation guard is structural, not cosmetic: a synthetic SOP
    # that does not announce itself is the failure mode `sop_design.md` S8.2
    # exists to prevent, so an un-flagged file must not load at all.
    if meta["synthetic"] is not True:
        raise CorpusError(f"{path.name}: synthetic must be true")
    if not meta["intents"]:
        raise CorpusError(f"{path.name}: intents must not be empty")
    if not meta["references"]:
        raise CorpusError(f"{path.name}: references must not be empty -- every SOP "
                          "must trace to a public source")

    return SOP(
        sop_id=str(meta["sop_id"]),
        title=str(meta["title"]),
        version=str(meta["version"]),
        intents=tuple(meta["intents"]),
        indexed=bool(meta["indexed"]),
        auto_reply_permitted=bool(meta["auto_reply_permitted"]),
        escalate_if=tuple(meta.get("escalate_if") or ()),
        references=tuple(meta["references"]),
        body=match["body"],
        path=path,
        effective_date=_opt_str(meta.get("effective_date")),
        supersedes=_opt_str(meta.get("supersedes")),
        applies_to_ya=tuple(meta.get("applies_to_ya") or ()),
        owner_queue=_opt_str(meta.get("owner_queue")),
        handling_target=_opt_str(meta.get("handling_target")),
    )


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def load_corpus(sop_dir: Path | None = None) -> tuple[SOP, ...]:
    """Load every SOP in ``sop_dir``, sorted by ``sop_id``.

    Raises:
        CorpusError: if the directory is missing, empty, contains a malformed
            file, or defines a duplicate ``sop_id``.
    """
    directory = sop_dir or DEFAULT_SOP_DIR
    if not directory.is_dir():
        raise CorpusError(
            f"SOP corpus not found at {directory}. "
            "Run: python scripts/generate_sops.py"
        )

    sops = tuple(sorted((_parse(p) for p in directory.glob("*.md")), key=lambda s: s.sop_id))
    if not sops:
        raise CorpusError(f"no SOPs found in {directory}")

    seen: dict[str, Path] = {}
    for sop in sops:
        if sop.sop_id in seen:
            raise CorpusError(
                f"duplicate sop_id {sop.sop_id}: {seen[sop.sop_id].name} and {sop.path.name}"
            )
        seen[sop.sop_id] = sop.path
    return sops
