"""The router -- the single gate where escalation happens.

RUNTIME. The highest-value component in the system, and the one the tests cover
most heavily.

Escalation is one decision made in one place, after the SOP lookup and before
drafting. Everything upstream only produces evidence; nothing else in the pipeline
decides whether a citizen gets an automated reply.

Eight reasons, checked in this order:

===  ==============================  ============================
 #   reason                          consults confidence?
===  ==============================  ============================
 1   requires_account_lookup         no
 2   high_consequence                no
 3   no_supporting_sop               no
 4   computation_requested           no
 5   account_specific_signal         no
 6   foreign_income_signal           no
 7   scam_signal                     no
 8   low_confidence                  yes
===  ==============================  ============================

Only the last reads the model. The other seven are structural and would fire
identically at probability 1.0 -- which is what makes "these buckets always
escalate" a property that can be tested rather than hoped for.

Reasons 4-7 are flags, and each fires only where a SOP declares its trigger, so
the corpus decides which conditions matter for which procedure. Reasons 6 and 7
are MISFILE guards specifically: they exist for the case where the classifier put
an email in the wrong class, in the direction where that error is unsafe.

**Thresholds are per bucket, not per class.** Three of five buckets escalate
regardless of confidence, so only ``auto_answerable`` and ``out_of_scope`` have a
threshold that bites. At 1,800 emails a bucket carries ~108 test examples against
~45 for a class, and a threshold set on 45 is not defensible -- the binomial
interval is wider than the effect (``sop_design.md`` S3).
"""

from __future__ import annotations

from typing import Final

import yaml

from triage.schemas import (
    Action,
    Bucket,
    BucketScore,
    EscalationReason,
    Flag,
    RoutingDecision,
)
from triage.sop.loader import SOP

#: Bucket -> escalation reason, for the three that always escalate.
_BUCKET_REASON: Final[dict[Bucket, EscalationReason]] = {
    Bucket.REQUIRES_ACCOUNT_LOOKUP: EscalationReason.REQUIRES_ACCOUNT_LOOKUP,
    Bucket.HIGH_CONSEQUENCE: EscalationReason.HIGH_CONSEQUENCE,
    Bucket.NO_SUPPORTING_SOP: EscalationReason.NO_SUPPORTING_SOP,
}

#: Flag -> the reason it escalates under, and the frontmatter trigger a SOP must
#: declare for it to apply. The corpus decides which conditions matter for which
#: procedure; this map only says what each one is called.
_FLAG_REASON: Final[dict[Flag, tuple[EscalationReason, str]]] = {
    Flag.COMPUTATION_REQUESTED: (
        EscalationReason.COMPUTATION_REQUESTED, "computation_requested",
    ),
    Flag.ACCOUNT_SPECIFIC_SIGNAL: (
        EscalationReason.ACCOUNT_SPECIFIC_SIGNAL, "account_specific",
    ),
    # Two misfile guards. Each fires only where a SOP declares the trigger, so
    # they cost nothing on the classes that never asked for them: SOP-RES-001
    # declares `foreign_income_dta` and SOP-RTE-002 declares `scam_report`, which
    # is the corpus saying "if this email is really that, I must not answer it."
    Flag.FOREIGN_INCOME_SIGNAL: (
        EscalationReason.FOREIGN_INCOME_SIGNAL, "foreign_income_dta",
    ),
    Flag.SCAM_SIGNAL: (
        EscalationReason.SCAM_SIGNAL, "scam_report",
    ),
}

#: Used until calibration is fitted. A number produced under it must never be
#: reported (``BUILD.md`` S7); ``RoutingDecision.calibrated`` carries the
#: distinction so a placeholder cannot be mistaken for a result.
PLACEHOLDER_THRESHOLD: Final[float] = 0.5


def load_thresholds(path: str | None = None) -> dict[str, float]:
    """Read per-bucket thresholds from ``config/thresholds.yaml``.

    In config rather than code so the escalation policy is readable in one file,
    diffable in git, and changeable without touching the pipeline.
    """
    from pathlib import Path

    config = Path(path) if path else (
        Path(__file__).resolve().parents[3] / "config" / "thresholds.yaml"
    )
    if not config.exists():
        return dict.fromkeys(
            (b.value for b in Bucket), PLACEHOLDER_THRESHOLD,
        )
    doc = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    return {
        bucket: float(entry["threshold"])
        for bucket, entry in (doc.get("buckets") or {}).items()
    }


def route(
    score: BucketScore,
    sops: tuple[SOP, ...],
    flags: frozenset[Flag],
    thresholds: dict[str, float],
    *,
    calibrated: bool = False,
    multiplier: float = 1.0,
) -> RoutingDecision:
    """Decide whether to act on this email, or hand it to an officer.

    Args:
        score: The rolled-up bucket and its confidence.
        sops: What the SOP lookup returned. Empty means unanswerable.
        flags: Orthogonal signals detected after the rollup.
        thresholds: Per-bucket cutoffs.
        calibrated: Whether ``score`` came from a fitted temperature.
        multiplier: Scales every threshold. Sweeping this generates the
            risk-coverage curve, so the curve is produced by the real router
            rather than by a reimplementation of it.

    Returns:
        The decision, including the reason when it escalates.
    """
    bucket = score.bucket
    confidence = score.confidence

    # 1-2. Buckets that escalate regardless of confidence.
    if bucket in _BUCKET_REASON and bucket is not Bucket.NO_SUPPORTING_SOP:
        return _escalate(bucket, confidence, _BUCKET_REASON[bucket], flags, calibrated)

    # 3. Unanswerable -- derived from an empty lookup, not a hand-written entry.
    # Checked against the SOPs rather than the bucket label so that holding out a
    # further SOP later needs no code change.
    if not sops:
        return _escalate(
            Bucket.NO_SUPPORTING_SOP, confidence,
            EscalationReason.NO_SUPPORTING_SOP, flags, calibrated,
        )

    # 4-5. Flags, but only where the SOP declares the trigger. The corpus decides
    # which conditions matter for which procedure.
    declared = {trigger for sop in sops for trigger in sop.escalation_triggers}
    for flag, (reason, trigger) in _FLAG_REASON.items():
        if flag in flags and trigger in declared:
            return _escalate(bucket, confidence, reason, flags, calibrated)

    # 6. The only test that reads the model's confidence.
    # Clamped to [0, 1]: the sweep pushes the multiplier above 1.0 to trace the
    # conservative end of the risk-coverage curve, and a threshold above 1.0 is
    # simply "always escalate" rather than an error.
    threshold = min(1.0, max(0.0, thresholds.get(bucket.value, PLACEHOLDER_THRESHOLD) * multiplier))
    if confidence < threshold:
        return RoutingDecision(
            action=Action.ESCALATE, bucket=bucket, confidence=confidence,
            threshold=threshold, reason=EscalationReason.LOW_CONFIDENCE,
            flags=flags, calibrated=calibrated,
        )

    # Act. A redirect is an automated action and counts toward coverage: under the
    # no-back-door policy a clean redirect is the correct outcome, not a failure.
    action = Action.REDIRECT if bucket is Bucket.OUT_OF_SCOPE else Action.AUTO_REPLY
    return RoutingDecision(
        action=action, bucket=bucket, confidence=confidence,
        threshold=threshold, flags=flags, calibrated=calibrated,
    )


def _escalate(
    bucket: Bucket,
    confidence: float,
    reason: EscalationReason,
    flags: frozenset[Flag],
    calibrated: bool,
) -> RoutingDecision:
    return RoutingDecision(
        action=Action.ESCALATE, bucket=bucket, confidence=confidence,
        reason=reason, flags=flags, calibrated=calibrated,
    )
