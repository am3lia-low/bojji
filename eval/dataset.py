"""Load the frozen corpus and its splits.

EVAL-TIME and BUILD-TIME.

``Email`` forbids extra fields on purpose: an inbox message carries an id, a
timestamp, a sender, a subject and a body, and nothing else. A real inbound email
has no ``label``. The generated corpus carries both the message and the ground
truth the generator recorded, so this module is the seam that splits them --
:class:`Labelled` keeps the truth beside the email rather than smuggling it inside,
which is what stops a metric from ever reading a field the runtime cannot see.

The ground-truth fields exist because generation recorded them, not because they
were annotated afterwards: the scenario spec knows which class it wrote from, which
SOPs it drew on, and whether it planted a computation request or PII. That is what
makes flag precision/recall and grounding accuracy free to compute (``BUILD.md``
S5.2, S9.2).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from triage.schemas import Email

#: Repository root, from this file.
ROOT: Final[Path] = Path(__file__).resolve().parents[1]

DEFAULT_EMAILS: Final[Path] = ROOT / "data" / "generated" / "emails.jsonl"
DEFAULT_SPLITS: Final[Path] = ROOT / "data" / "splits" / "splits.json"

#: Keys belonging to the inbox message. Everything else in a row is ground truth.
_EMAIL_KEYS: Final[frozenset[str]] = frozenset({
    "id", "received_at", "from", "subject", "body",
})


@dataclass(frozen=True)
class Labelled:
    """One generated email, with the ground truth recorded when it was written."""

    email: Email
    label: str
    scenario_id: str = ""
    source_sops: tuple[str, ...] = ()
    computation_requested: bool = False
    account_specific: bool = False
    plant_pii: dict[str, str] = field(default_factory=dict)
    season: str = ""
    persona_role: str = ""
    literacy: str = ""
    register: str = ""
    generator_model: str = ""

    @property
    def id(self) -> str:
        return self.email.id


def _row_to_labelled(row: dict[str, Any]) -> Labelled:
    return Labelled(
        email=Email.model_validate({k: v for k, v in row.items() if k in _EMAIL_KEYS}),
        label=str(row["label"]),
        scenario_id=str(row.get("scenario_id", "")),
        source_sops=tuple(row.get("source_sops") or ()),
        computation_requested=bool(row.get("computation_requested", False)),
        account_specific=bool(row.get("account_specific", False)),
        plant_pii=dict(row.get("plant_pii") or {}),
        season=str(row.get("season", "")),
        persona_role=str(row.get("persona_role", "")),
        literacy=str(row.get("literacy", "")),
        register=str(row.get("register", "")),
        generator_model=str(row.get("generator_model", "")),
    )


def load_emails(path: Path | None = None) -> tuple[Labelled, ...]:
    """Read ``emails.jsonl`` into labelled records."""
    source = path or DEFAULT_EMAILS
    if not source.exists():
        raise FileNotFoundError(
            f"no corpus at {source}. Run: python scripts/generate_emails.py"
        )
    with source.open(encoding="utf-8") as handle:
        return tuple(_row_to_labelled(json.loads(line)) for line in handle if line.strip())


def load_splits(path: Path | None = None) -> dict[str, str]:
    """Read the frozen split assignment: email id -> ``train``/``calibration``/``test``."""
    source = path or DEFAULT_SPLITS
    if not source.exists():
        raise FileNotFoundError(
            f"no splits at {source}. Run: python scripts/make_splits.py"
        )
    return dict(json.loads(source.read_text(encoding="utf-8"))["assignment"])


def split(
    name: str,
    emails: tuple[Labelled, ...] | None = None,
    assignment: dict[str, str] | None = None,
) -> tuple[Labelled, ...]:
    """Return one split.

    Results are reported on ``test`` and never on ``calibration``: the temperature
    is fitted on the latter, so reporting there would be reporting on training data
    for the very quantity being measured (``BUILD.md`` S5.5).
    """
    rows = emails if emails is not None else load_emails()
    mapping = assignment if assignment is not None else load_splits()
    return tuple(row for row in rows if mapping.get(row.id) == name)


def iter_splits(
    emails: tuple[Labelled, ...] | None = None,
) -> Iterator[tuple[str, tuple[Labelled, ...]]]:
    """Yield each split by name, in pipeline order."""
    rows = emails if emails is not None else load_emails()
    mapping = load_splits()
    for name in ("train", "calibration", "test"):
        yield name, split(name, rows, mapping)


__all__ = ["Labelled", "iter_splits", "load_emails", "load_splits", "split"]
