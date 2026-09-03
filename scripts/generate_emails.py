"""Generate the synthetic email corpus from ``data/scenarios/*.yaml``.

BUILD-TIME ONLY. Uses a paid API. The output is frozen and committed, so a grader
reproducing the results never runs this script and never needs a key.

**The generator is never shown the label.** It receives a *situation* -- a citizen's
circumstance -- plus a persona and a style instruction, and writes an email. The
label is attached afterwards, from the scenario file. This is the corpus's central
anti-leakage property: if the prompt named the class, the emails would carry
vocabulary chosen *because* of the label, and a classifier would learn the
generator's tell rather than the citizen's problem. Reported accuracy would then be
measuring a shortcut.

``scripts/check_leakage.py`` and the EDA notebook test this empirically rather than
trusting the intent: TF-IDF plus logistic regression is fitted on the output, and a
near-perfect score means a giveaway token exists and the corpus is rebuilt.

**Model separation** (``BUILD.md`` S6.4) -- no model may be scored on its own
output:

    generation   OpenAI gpt-4o          <- here; build time, paid
    baseline     Groq qwen3.8-27b        <- must differ from the generator
    drafting     Gemini                  <- runtime, free tier
    judge        Groq qwen3.8-27b        <- must differ from the drafter

Groq appears twice without breaking the rule: the baseline CLASSIFIES EMAILS and
the judge SCORES DRAFTS, so neither is ever scored on its own output. Groq wrote
none of the text it sees in either role.

Usage:
    python scripts/generate_emails.py                 # full run, ~1,800 emails
    python scripts/generate_emails.py --limit 12      # smoke test
    python scripts/generate_emails.py --dry-run       # print prompts, call nothing
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final[Path] = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """Read ``.env`` into the environment without adding a dependency.

    Existing environment variables win, so an explicit export still overrides the
    file. ``.env`` is gitignored and must never be committed.
    """
    env_file = path or ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value


load_dotenv()
SCENARIO_DIR: Final[Path] = ROOT / "data" / "scenarios"
OUT_PATH: Final[Path] = ROOT / "data" / "generated" / "emails.jsonl"

SEED: Final[int] = 42
#: GPT-4o rather than gpt-4o-mini. The corpus is the foundation every downstream
#: metric rests on, and build-time cost is not constrained by the free-tier
#: requirement -- that applies to the runtime. The larger model sustains a persona
#: across variants, varies its openings, writes Singlish that reads as natural
#: rather than parodic, and is markedly better at NOT drifting into administrative
#: vocabulary that would leak the label. Roughly $15 for 1,800 emails against $1;
#: a formulaic corpus would teach the classifier the template instead of the
#: problem, which no amount of downstream care recovers.
MODEL: Final[str] = os.environ.get("OPENAI_GENERATION_MODEL", "gpt-4o")

#: Seasonal windows. `received_at` drives the seasonality axis, so an evaluation
#: slice can ask whether performance holds across the tax year rather than only in
#: aggregate (``BUILD.md`` S5.3).
SEASONS: Final[dict[str, tuple[int, int]]] = {
    "filing": (3, 4),      # Mar-Apr: returns due
    "estimates": (5, 6),   # May-Jun: provisional instalments begin
    "noa": (6, 7),         # Jun-Jul: assessments issued
    "any": (1, 12),
}

#: Style instructions. Kept out of the situation text so that literacy varies
#: independently of topic -- otherwise "imperfect English" would correlate with
#: whichever classes happened to be written that way.
STYLES: Final[dict[str, str]] = {
    "standard": (
        "Write in clear, standard English. Ordinary punctuation and sentence "
        "structure, the way a reasonably confident writer would send an enquiry."
    ),
    "imperfect": (
        "Write the way someone types quickly on a phone and does not re-read it. "
        "Include some of: missing apostrophes, run-on sentences, a typo or two, "
        "inconsistent capitalisation, no paragraph breaks. Stay readable."
    ),
    "singlish": (
        "Write in lightly Singlish-inflected English, as a Singaporean might write "
        "an informal but sincere enquiry. Occasional 'lah', 'leh', 'can or not', "
        "'how ah'. Keep it light -- one or two markers, not a parody."
    ),
}

REGISTERS: Final[dict[str, str]] = {
    "polite": "Polite and matter-of-fact.",
    "frustrated": "Mildly frustrated -- this is not their first attempt to find out.",
    "anxious": "Anxious. They are worried about getting something wrong.",
    "terse": "Very brief and to the point. Two or three sentences at most.",
}

SYSTEM_PROMPT: Final[str] = """\
You write realistic emails that members of the public send to a national tax \
authority in Singapore about their personal income tax.

Rules:
- Write ONLY the email. No subject line unless asked, no signature block, no \
commentary, no markdown.
- The writer is a member of the public, not a tax professional. They use everyday \
words, not technical terms, and they are often unsure what the right question is.
- Never state or imply what category the enquiry belongs to. Never use \
administrative or classificatory language.
- Do not invent specific figures, dates or reference numbers unless the situation \
calls for them.
- Do NOT write a sign-off, a name, or a placeholder such as "[Your Name]". End \
with the last sentence of the question itself.
- Vary the opening sharply. Many people open with the problem rather than a \
greeting. Never begin with "I hope you can help" or "I hope this email finds you".
- Use plain ASCII punctuation: straight quotes and apostrophes, and a hyphen \
rather than a dash.
- Length varies naturally: some write two sentences, others six.
"""


@dataclass(frozen=True)
class Scenario:
    """One authored situation, expanded into several emails."""

    scenario_id: str
    label: str
    source_sops: tuple[str, ...]
    situation: str
    role: str
    literacy: str
    register: str
    season: str
    computation_requested: bool
    account_specific: bool
    plant_pii: tuple[str, ...]
    variants: int
    notes: str


def load_scenarios() -> list[Scenario]:
    """Read every scenario file. Fails loudly rather than skipping a malformed one."""
    scenarios: list[Scenario] = []
    for path in sorted(SCENARIO_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        default_sops = tuple(s.strip() for s in doc["source_sops"])
        for entry in doc["scenarios"]:
            persona = entry["persona"]
            scenarios.append(Scenario(
                scenario_id=entry["scenario_id"],
                label=doc["label"],
                source_sops=tuple(entry.get("source_sops") or default_sops),
                situation=" ".join(entry["situation"].split()),
                role=persona["role"],
                literacy=persona["literacy"],
                register=persona["register"],
                season=entry.get("season", "any"),
                computation_requested=bool(entry["computation_requested"]),
                account_specific=bool(entry["account_specific"]),
                plant_pii=tuple(entry.get("plant_pii") or ()),
                variants=int(entry["variants"]),
                notes=entry.get("notes", ""),
            ))
    return scenarios


# --------------------------------------------------------------------------- #
# Fabricated identifiers
# --------------------------------------------------------------------------- #

def fake_nric(rng: random.Random) -> str:
    """A fabricated NRIC with a VALID checksum.

    Valid on purpose: the scrubber validates the check letter, so an invalid
    identifier would be silently ignored by the detector and scrub recall would be
    measured against something it was never meant to catch. These belong to nobody
    -- the digits are random and the format is public.

    The check letter comes from ``triage.pii.nric`` rather than a second copy of
    the tables. A duplicate is not merely redundant here: an inconsistency between
    the two would produce planted identifiers the scrubber cannot see, and the
    resulting recall figure would be wrong in the flattering direction.
    """
    sys.path.insert(0, str(ROOT / "src"))
    from triage.pii.nric import expected_check_letter

    prefix = rng.choice("STFGM")
    digits = "".join(str(rng.randint(0, 9)) for _ in range(7))
    return f"{prefix}{digits}{expected_check_letter(prefix, digits)}"


def fake_pii(kind: str, rng: random.Random) -> str:
    if kind == "nric":
        return fake_nric(rng)
    if kind == "phone":
        return f"{rng.choice('689')}{rng.randint(1000000, 9999999)}"
    if kind == "postcode":
        return f"{rng.randint(100000, 829999):06d}"
    if kind == "address":
        street = rng.choice(["Jalan Membina", "Lorong Chuan", "Bukit Batok Ave 3",
                             "Tampines Street 21", "Ang Mo Kio Ave 10"])
        unit = f"#{rng.randint(2, 25):02d}-{rng.randint(1, 199):03d}"
        return f"Blk {rng.randint(1, 999)} {street} {unit}"
    if kind == "email":
        return f"{rng.choice(['tan', 'lim', 'kumar', 'wong'])}{rng.randint(10, 99)}@example.com"
    raise ValueError(f"unknown PII kind: {kind}")


def received_at(season: str, rng: random.Random) -> datetime:
    lo, hi = SEASONS.get(season, SEASONS["any"])
    month = rng.randint(lo, hi)
    return datetime(2026, month, rng.randint(1, 28),
                    rng.randint(8, 19), rng.randint(0, 59), tzinfo=UTC)


def build_prompt(scenario: Scenario, rng: random.Random, planted: dict[str, str]) -> str:
    """Compose the user prompt. NOTE: the label never appears here."""
    parts = [
        f"Situation: {scenario.situation}",
        "",
        f"The writer is {scenario.role.replace('_', ' ')}. "
        f"{REGISTERS.get(scenario.register, '')}",
        STYLES[scenario.literacy],
    ]
    if scenario.computation_requested:
        parts.append(
            "Important: the writer explicitly asks to be TOLD A SPECIFIC AMOUNT -- "
            "how much they will get, owe, or be charged. Make that request clear."
        )
    if scenario.account_specific:
        parts.append(
            "Important: the writer is asking about THEIR OWN case and record, not "
            "about the rule in general. Use possessive phrasing naturally."
        )
    if planted:
        listed = ", ".join(f"{k}: {v}" for k, v in planted.items())
        parts.append(
            f"Include these details naturally in the email, exactly as written: {listed}"
        )
    parts += ["", "Write a subject line, then the email body, in this format:",
              "SUBJECT: <subject>", "BODY:", "<the email>"]
    return "\n".join(parts)


_SUBJECT_RE: Final[re.Pattern[str]] = re.compile(
    r"SUBJECT:\s*(?P<subject>.+?)\s*BODY:\s*(?P<body>.+)", re.S | re.I
)


#: Sign-off artefacts. A model-inserted placeholder would become a giveaway token
#: -- and one that correlates with whichever classes happened to draw it, which is
#: exactly the leakage the scenario design exists to prevent.
_SIGNOFF_RE: Final[re.Pattern[str]] = re.compile(
    r"\n\s*(best regards|kind regards|warm regards|regards|thank you|thanks"
    r"|sincerely|yours faithfully|yours sincerely|cheers)[,.]?"
    r"(\s*\n+\s*\[?[^\n\[\]]{0,40}\]?\s*)?$",
    re.I,
)
_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"\[(your name|name|full name)\]", re.I)

#: Smart punctuation -> ASCII. The corpus is read by a tokenizer, a regex scrubber
#: and a human reviewer; mixed encodings help none of them.
_PUNCT: Final[dict[str, str]] = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": " - ", "…": "...", " ": " ",
}


def clean(text: str) -> str:
    """Remove generator artefacts and normalise punctuation."""
    for smart, plain in _PUNCT.items():
        text = text.replace(smart, plain)
    text = _PLACEHOLDER_RE.sub("", text)
    text = _SIGNOFF_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_reply(text: str) -> tuple[str, str]:
    match = _SUBJECT_RE.search(text)
    if match:
        return match["subject"].strip(), match["body"].strip()
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return (lines[0][:80] if lines else "Enquiry"), "\n".join(lines[1:]).strip() or text.strip()


def generate(client: Any, prompt: str, temperature: float) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=400,
    )
    return response.choices[0].message.content or ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="generate at most N emails (smoke test)")
    parser.add_argument("--dry-run", action="store_true", help="print prompts, call nothing")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--resume", action="store_true",
                        help="skip emails already present in --out and append")
    args = parser.parse_args()

    scenarios = load_scenarios()
    planned = sum(s.variants for s in scenarios)
    print(f"{len(scenarios)} scenarios -> {planned} emails "
          f"across {len({s.label for s in scenarios})} classes")

    client = None
    if not args.dry_run:
        if not os.environ.get("OPENAI_API_KEY"):
            print("\nOPENAI_API_KEY is not set.\n"
                  "  cp .env.example .env   and fill it in, then re-run.\n"
                  "  Or preview prompts with: --dry-run", file=sys.stderr)
            return 1
        from openai import OpenAI

        client = OpenAI()

    # Resume support. A full run is ~1,800 API calls over roughly 80 minutes, so a
    # rate limit or a dropped connection near the end would otherwise discard every
    # completed email. Rows are appended as they arrive and already-generated ids
    # are skipped on restart, which makes the run restartable rather than
    # all-or-nothing. The seeded RNG is advanced in lockstep so a resumed run
    # produces the same planted identifiers it would have on a single pass.
    rows: list[dict[str, Any]] = []
    done: set[str] = set()
    if args.resume and args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows.append(row)
                done.add(str(row["id"]))
        print(f"resuming: {len(done)} emails already generated")

    if args.dry_run:
        handle = None
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        handle = args.out.open("a" if done else "w", encoding="utf-8")

    rng = random.Random(SEED)
    failures = 0
    started = time.time()

    for scenario in scenarios:
        for variant in range(scenario.variants):
            if args.limit and len(rows) >= args.limit:
                break

            # Draw from the RNG before the skip check, so a resumed run stays in
            # lockstep with the seeded sequence a single pass would have produced.
            planted = {kind: fake_pii(kind, rng) for kind in scenario.plant_pii}
            prompt = build_prompt(scenario, rng, planted)
            email_id = f"{scenario.scenario_id}-{variant:03d}"

            if email_id in done:
                received_at(scenario.season, rng)  # keep the RNG aligned
                continue

            if args.dry_run:
                if len(rows) < 3:
                    print(f"\n--- {email_id} [{scenario.label}] ---\n{prompt}")
                rows.append({"id": email_id})
                continue

            assert client is not None
            try:
                # Temperature climbs across variants of one scenario so the
                # variants diverge rather than paraphrasing each other.
                text = generate(client, prompt, 0.7 + 0.25 * (variant % 3))
            except Exception as exc:  # noqa: BLE001 - continue; report at the end
                failures += 1
                print(f"  FAILED {email_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
                time.sleep(2)
                continue

            subject, body = parse_reply(text)
            subject, body = clean(subject), clean(body)
            row: dict[str, Any] = {
                "id": email_id,
                "received_at": received_at(scenario.season, rng).isoformat(),
                "from": fake_pii("email", rng),
                "subject": subject,
                "body": body,
                # --- ground truth, free because the scenario declared it ---
                "label": scenario.label,
                "scenario_id": scenario.scenario_id,
                "source_sops": list(scenario.source_sops),
                "computation_requested": scenario.computation_requested,
                "account_specific": scenario.account_specific,
                "plant_pii": planted or None,
                "season": scenario.season,
                "persona_role": scenario.role,
                "literacy": scenario.literacy,
                "register": scenario.register,
                "generator_model": MODEL,
            }
            rows.append(row)
            # Flush per email: a run interrupted at 1,700 keeps its 1,700.
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()

            if len(rows) % 50 == 0:
                rate = len(rows) / (time.time() - started)
                print(f"  {len(rows)}/{planned}  ({rate:.1f}/s)")

        if args.limit and len(rows) >= args.limit:
            break

    if handle is not None:
        handle.close()

    if args.dry_run:
        print(f"\ndry run: {len(rows)} prompts, no API calls made")
        return 0

    by_label: dict[str, int] = {}
    for row in rows:
        by_label[row["label"]] = by_label.get(row["label"], 0) + 1

    try:
        shown: Path | str = args.out.relative_to(ROOT)
    except ValueError:  # an --out path outside the repository
        shown = args.out
    print(f"\nwrote {len(rows)} emails -> {shown}")
    print(f"failures: {failures}")
    print(f"model: {MODEL}   seed: {SEED}   elapsed: {time.time() - started:.0f}s")
    print("\nper class:")
    for label, count in sorted(by_label.items()):
        print(f"  {label:26} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
