"""Local PII scrubbing with a reversible placeholder vault.

The scrub node gates every external call in the pipeline. Text is scrubbed
locally, the scrubbed form is what reaches the classifier and any LLM, and real
values are substituted back into the draft locally afterwards.

Detection is regex plus a street gazetteer, configured in
``config/pii_patterns.yaml`` rather than in this module. Free-text addresses
without a street-type token are the known residual gap; scrub recall is measured
against planted PII and reported rather than asserted.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import yaml

from triage.pii.nric import is_valid_nric

#: Default location of the pattern configuration, relative to the repo root.
DEFAULT_CONFIG: Final[Path] = (
    Path(__file__).resolve().parents[3] / "config" / "pii_patterns.yaml"
)

#: Validators a pattern may name via its ``validator:`` key. A validator
#: receives the matched text and returns whether it is genuinely PII, which
#: keeps false positives down on tokens that merely share a shape.
VALIDATORS: Final[dict[str, Callable[[str], bool]]] = {
    "nric_checksum": is_valid_nric,
}

#: Matches a placeholder emitted by :meth:`Scrubber.scrub`.
PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"\[([A-Z_]+)_(\d+)\]")


@dataclass(frozen=True)
class Pattern:
    """One configured detection rule."""

    name: str
    placeholder: str
    regex: re.Pattern[str]
    justification: str
    validator: Callable[[str], bool] | None = None

    def accepts(self, text: str) -> bool:
        """Return whether ``text`` survives this pattern's validator."""
        return self.validator is None or self.validator(text)


@dataclass
class ScrubResult:
    """The output of a scrub: redacted text plus the vault needed to reverse it."""

    text: str
    #: Placeholder token -> the original value it replaced.
    vault: dict[str, str] = field(default_factory=dict)
    #: Pattern name -> number of spans replaced, for recall reporting.
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def placeholders(self) -> list[str]:
        """Placeholder tokens present, in insertion order."""
        return list(self.vault)

    def __len__(self) -> int:
        return len(self.vault)


def _load_patterns(config_path: Path) -> tuple[list[Pattern], list[re.Pattern[str]]]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    patterns = [
        Pattern(
            name=entry["name"],
            placeholder=entry["placeholder"],
            regex=re.compile(entry["regex"]),
            justification=entry.get("justification", ""),
            validator=VALIDATORS.get(entry["validator"]) if entry.get("validator") else None,
        )
        for entry in raw.get("patterns", [])
    ]
    allowlist = [re.compile(p) for p in raw.get("allowlist", [])]
    return patterns, allowlist


class Scrubber:
    """Replaces PII with stable placeholders and substitutes it back.

    A single instance is stateless across calls: each :meth:`scrub` returns its
    own vault, so one scrubber can serve concurrent emails without leaking
    values between them.
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        path = Path(config_path) if config_path is not None else DEFAULT_CONFIG
        self.config_path = path
        self.patterns, self.allowlist = _load_patterns(path)

    def _allowlisted_spans(self, text: str) -> list[tuple[int, int]]:
        """Character spans that must be left untouched."""
        return [m.span() for rule in self.allowlist for m in rule.finditer(text)]

    def scrub(self, text: str) -> ScrubResult:
        """Replace detected PII in ``text`` with placeholders.

        Identical values map to the same placeholder within one call, so a
        citizen who states their NRIC twice yields ``[NRIC_1]`` both times and
        the draft rehydrates consistently.
        """
        protected = self._allowlisted_spans(text)
        # Spans already claimed by an earlier pattern; ordering in the config is
        # therefore significant and documented there.
        taken: list[tuple[int, int]] = list(protected)
        vault: dict[str, str] = {}
        seen: dict[tuple[str, str], str] = {}
        counts: dict[str, int] = {}
        replacements: list[tuple[int, int, str]] = []

        def overlaps(start: int, end: int) -> bool:
            return any(start < t_end and t_start < end for t_start, t_end in taken)

        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                start, end = match.span()
                value = match.group(0)
                if overlaps(start, end) or not pattern.accepts(value):
                    continue

                key = (pattern.placeholder, value.upper())
                token = seen.get(key)
                if token is None:
                    index = sum(
                        1 for k in seen if k[0] == pattern.placeholder
                    ) + 1
                    token = f"[{pattern.placeholder}_{index}]"
                    seen[key] = token
                    vault[token] = value

                taken.append((start, end))
                replacements.append((start, end, token))
                counts[pattern.name] = counts.get(pattern.name, 0) + 1

        scrubbed = text
        for start, end, token in sorted(replacements, reverse=True):
            scrubbed = scrubbed[:start] + token + scrubbed[end:]

        return ScrubResult(text=scrubbed, vault=vault, counts=counts)

    def rehydrate(self, text: str, vault: dict[str, str]) -> str:
        """Substitute real values back into ``text``.

        Placeholders absent from ``vault`` are left in place rather than raising:
        a model that invents ``[NRIC_9]`` must not crash the pipeline, and the
        surviving token is visible evidence of the fabrication.
        """
        for token, value in vault.items():
            text = text.replace(token, value)
        return text

    def unresolved(self, text: str, vault: dict[str, str]) -> list[str]:
        """Return placeholder tokens in ``text`` that ``vault`` cannot resolve.

        A non-empty result means a downstream model emitted a placeholder that
        was never issued, which the drafting node treats as a failure signal.
        """
        return [m.group(0) for m in PLACEHOLDER_RE.finditer(text) if m.group(0) not in vault]
