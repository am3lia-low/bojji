"""Scrub recall against planted PII.

EVAL-TIME.

Generation recorded what it planted in each email -- ``plant_pii`` carries the exact
NRIC, phone number or postal code that was inserted -- so recall is measurable
rather than asserted. This is the metric that says whether the guarantee at the top
of the pipeline actually holds.

**Recall is measured per PII type, not pooled.** The types have different detection
mechanisms and different residual risk: an NRIC has a checksum and should be near
perfect, while a free-text address without a street-type token is the known gap.
Pooling them would let a strong NRIC number hide a weak address one, and the address
gap is precisely what the writeup must state rather than defend away.

**Recall is measured against the value, not the placeholder count.** A scrub that
replaced *something* is not evidence it replaced the right thing. The test is that
the planted value no longer appears in the scrubbed text -- which is also what
matters operationally, since it is the value that would otherwise reach an external
API.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class TypeRecall:
    """Detection rate for one planted PII type."""

    pii_type: str
    detected: int
    planted: int
    missed_examples: tuple[str, ...] = ()

    @property
    def recall(self) -> float:
        return self.detected / self.planted if self.planted else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.pii_type,
            "planted": self.planted,
            "detected": self.detected,
            "missed": self.planted - self.detected,
            "recall": round(self.recall, 4),
            "missed_examples": list(self.missed_examples),
        }


@dataclass(frozen=True)
class ScrubReport:
    """Scrub recall overall and by type."""

    by_type: tuple[TypeRecall, ...]
    overall_detected: int
    overall_planted: int
    leaked_emails: tuple[str, ...] = ()

    @property
    def recall(self) -> float:
        return self.overall_detected / self.overall_planted if self.overall_planted else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "note": (
                "Measured against values the generator planted, by checking the value "
                "is absent from the scrubbed text. Free-text addresses without a "
                "street-type token are the known residual gap."
            ),
            "overall_recall": round(self.recall, 4),
            "planted": self.overall_planted,
            "detected": self.overall_detected,
            "by_type": [t.as_dict() for t in self.by_type],
            "n_emails_with_a_leak": len(self.leaked_emails),
            "leaked_email_ids": list(self.leaked_emails[:25]),
        }


def scrub_report(
    records: list[tuple[str, dict[str, str], str]],
    max_examples: int = 5,
) -> ScrubReport:
    """Measure detection over planted values.

    Args:
        records: ``(email_id, plant_pii, scrubbed_text)`` per email, where
            ``plant_pii`` maps a PII type to the value planted.

    A value is detected when it no longer appears in the scrubbed text. Comparison
    is case-insensitive, since a scrubbed NRIC is matched case-insensitively at
    detection time too.
    """
    detected_by_type: dict[str, int] = defaultdict(int)
    planted_by_type: dict[str, int] = defaultdict(int)
    missed_by_type: dict[str, list[str]] = defaultdict(list)
    leaked: list[str] = []

    for email_id, planted, scrubbed in records:
        haystack = scrubbed.lower()
        leaked_here = False
        for pii_type, value in planted.items():
            if not value:
                continue
            planted_by_type[pii_type] += 1
            if str(value).lower() in haystack:
                leaked_here = True
                if len(missed_by_type[pii_type]) < max_examples:
                    missed_by_type[pii_type].append(str(value))
            else:
                detected_by_type[pii_type] += 1
        if leaked_here:
            leaked.append(email_id)

    by_type = tuple(
        TypeRecall(
            pii_type=pii_type,
            detected=detected_by_type[pii_type],
            planted=planted_by_type[pii_type],
            missed_examples=tuple(missed_by_type[pii_type]),
        )
        for pii_type in sorted(planted_by_type)
    )

    return ScrubReport(
        by_type=by_type,
        overall_detected=sum(detected_by_type.values()),
        overall_planted=sum(planted_by_type.values()),
        leaked_emails=tuple(leaked),
    )


__all__ = ["ScrubReport", "TypeRecall", "scrub_report"]
