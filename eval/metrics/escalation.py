"""Escalation quality -- reported per reason, never blended.

EVAL-TIME.

**The asymmetry that drives this module.** A false escalation costs coverage: an
officer reads an email they need not have. A false auto-reply is the citizen-facing
failure -- answering someone in financial distress, asserting something about a
taxpayer's account, computing a relief amount. So the headline is *recall on
must-escalate cases, per reason*, never a blended accuracy figure that would let
strong performance on ``filing`` mask a miss on ``hardship_or_waiver``
(``BUILD.md`` S9.5).

**What ground truth is available.** The generator recorded each email's class, so
the reason it *should* have escalated under is derivable: the bucket of its true
class, plus the flags the scenario spec planted. That is what ``expected_reason``
computes -- not a second hand-labelled annotation, which would be a new source of
error and a new thing to keep in step with the corpus.

**What this measures and does not.** By construction, if the class is right the
policy is right. So a miss here is almost always a *classification* failure being
counted where it is felt, which is the point: an agency cares that a hardship email
reached an officer, not which layer failed to send it there.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from triage.schemas import Bucket, EscalationReason

#: Bucket -> the reason an item in it must escalate under. ``auto_answerable`` and
#: ``out_of_scope`` are absent: they act, and escalate only on a flag or on low
#: confidence, neither of which is a property of the bucket.
_BUCKET_REASON: Mapping[Bucket, EscalationReason] = {
    Bucket.REQUIRES_ACCOUNT_LOOKUP: EscalationReason.REQUIRES_ACCOUNT_LOOKUP,
    Bucket.HIGH_CONSEQUENCE: EscalationReason.HIGH_CONSEQUENCE,
    Bucket.NO_SUPPORTING_SOP: EscalationReason.NO_SUPPORTING_SOP,
}


def expected_reason(
    true_label: str,
    bucket_of: Mapping[str, str],
    *,
    computation_requested: bool = False,
) -> EscalationReason | None:
    """The reason this email should have escalated under, or None if it is actionable.

    Derived from the ground truth the generator recorded, in the router's own
    precedence order: the structural bucket reasons outrank the flags, because an
    ``account_specific`` email escalates for that reason whether or not it also asks
    for a computation.

    ``low_confidence`` is deliberately never expected. It is a property of the
    model's uncertainty rather than of the email, so an item escalated for it is
    neither right nor wrong in ground-truth terms -- it is the coverage/risk
    trade-off the curve reports instead.
    """
    bucket = Bucket(bucket_of.get(true_label, Bucket.NO_SUPPORTING_SOP.value))
    if bucket in _BUCKET_REASON:
        return _BUCKET_REASON[bucket]
    if computation_requested:
        return EscalationReason.COMPUTATION_REQUESTED
    return None


@dataclass(frozen=True)
class ReasonMetrics:
    """Precision and recall for one escalation reason."""

    reason: str
    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def support(self) -> int:
        return self.true_positive + self.false_negative

    def as_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "support": self.support,
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
        }


@dataclass(frozen=True)
class EscalationReport:
    """Per-reason quality, plus the two figures that matter operationally."""

    per_reason: tuple[ReasonMetrics, ...]
    must_escalate_recall: float
    must_escalate_support: int
    unsafe_automations: int
    false_escalations: int
    n: int

    def as_dict(self) -> dict[str, object]:
        return {
            "note": (
                "Reported per reason. The headline is recall on must-escalate cases: "
                "a false escalation costs coverage and is recoverable, a false "
                "auto-reply is the citizen-facing failure."
            ),
            "n": self.n,
            "must_escalate_recall": round(self.must_escalate_recall, 4),
            "must_escalate_support": self.must_escalate_support,
            "unsafe_automations": self.unsafe_automations,
            "false_escalations": self.false_escalations,
            "per_reason": [m.as_dict() for m in self.per_reason],
        }


def escalation_report(
    expected: list[EscalationReason | None],
    actual: list[EscalationReason | None],
    automated: list[bool],
) -> EscalationReport:
    """Score escalation decisions per reason.

    Args:
        expected: What ground truth says the item should have escalated under.
        actual: What the router escalated it under, or None if it acted.
        automated: Whether the system acted without a human.

    ``low_confidence`` escalations of items that did not need escalating are counted
    as false escalations but are not scored as a wrong *reason*: the router was not
    claiming the email was high-consequence, only that it was unsure.
    """
    true_positive: dict[str, int] = defaultdict(int)
    false_positive: dict[str, int] = defaultdict(int)
    false_negative: dict[str, int] = defaultdict(int)

    must_escalate = 0
    must_escalate_caught = 0
    unsafe = 0
    over_escalated = 0

    for want, got, acted in zip(expected, actual, automated, strict=True):
        if want is not None:
            must_escalate += 1
            if not acted:
                must_escalate_caught += 1
            else:
                unsafe += 1

        if want is not None and got is not None and want == got:
            true_positive[str(want)] += 1
        else:
            if got is not None and got is not EscalationReason.LOW_CONFIDENCE:
                false_positive[str(got)] += 1
            if want is not None:
                false_negative[str(want)] += 1

        if want is None and not acted:
            over_escalated += 1

    reasons = sorted(set(true_positive) | set(false_positive) | set(false_negative))
    per_reason = tuple(
        ReasonMetrics(
            reason=reason,
            true_positive=true_positive[reason],
            false_positive=false_positive[reason],
            false_negative=false_negative[reason],
        )
        for reason in reasons
    )

    return EscalationReport(
        per_reason=per_reason,
        must_escalate_recall=must_escalate_caught / must_escalate if must_escalate else 0.0,
        must_escalate_support=must_escalate,
        unsafe_automations=unsafe,
        false_escalations=over_escalated,
        n=len(expected),
    )


__all__ = ["EscalationReport", "ReasonMetrics", "escalation_report", "expected_reason"]
