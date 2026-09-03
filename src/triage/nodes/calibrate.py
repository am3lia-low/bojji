"""Rollup and calibration -- class probabilities into one bucket confidence.

RUNTIME. This is the node the contribution runs through.

Two steps, deliberately in one node because they are one transformation of one
distribution:

1. **Rollup.** The class probabilities are summed within their routing bucket,
   giving a distribution over 5. The predicted bucket is the one containing the
   predicted class -- NOT the argmax of the summed distribution. Those differ, and
   the difference matters: the SOP lookup, the drafter and the grounding metric all
   key off the predicted *class*, so a bucket that disagreed with it would route an
   item under a policy belonging to a class the rest of the pipeline never used.

2. **Calibration.** Temperature scaling, fitted on the calibration split and
   applied to the bucket logits. Raw softmax is systematically overconfident, which
   is why an off-the-shelf 0.8 cutoff is unsound and what this project measures.

**Why the summed probability and not the class probability.** ``tax_reliefs`` pulls
four SOPs and ``payment`` two, and every class in a bucket shares one policy. An
email split 0.45 / 0.40 between two auto-answerable classes is not an uncertain
*routing* decision even though it is an uncertain *class* decision -- the same reply
policy applies either way. Thresholding the class probability would escalate it and
lose coverage for no safety gain. This is the whole reason calibration sits at
bucket level (``sop_design.md`` S3).

**Applying temperature to summed probabilities, not raw logits.** The class
logits do not sum into 5 bucket logits -- summation happens in probability space,
after the softmax. So the bucket distribution is mapped back to log space
(``log p``) and the temperature applied there, which is the same monotonic
correction the scaler was fitted under. The training notebook's calibration section
fits on exactly this quantity -- through the same
:func:`triage.models.calibration.bucket_confidences` this module mirrors -- so the
fit and the application agree by construction.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from triage.models.calibration import TemperatureScaler
from triage.schemas import Bucket, BucketScore, Classification, TriageState

#: Guard for ``log(0)``. A bucket holding no probability mass is representable;
#: its log is not.
_EPSILON: float = 1e-12


def rollup(
    classification: Classification,
    bucket_of: Mapping[str, str],
) -> tuple[Bucket, dict[Bucket, float]]:
    """Sum the class distribution into buckets.

    Args:
        classification: The full class distribution.
        bucket_of: class -> bucket, derived from SOP frontmatter by
            :class:`triage.sop.index.SOPIndex`.

    Returns:
        The predicted bucket -- the one holding the predicted CLASS -- and the full
        summed distribution over buckets.

    An unknown class falls to ``no_supporting_sop``, which is the same derivation
    ``SOPIndex.bucket_for`` uses: a class no indexed SOP serves has nothing to
    ground a reply on, and the emptiness of the lookup is itself the signal.
    """
    summed: dict[Bucket, float] = dict.fromkeys(Bucket, 0.0)
    for label, probability in classification.probabilities.items():
        bucket = Bucket(bucket_of.get(label, Bucket.NO_SUPPORTING_SOP.value))
        summed[bucket] += probability

    predicted = Bucket(
        bucket_of.get(classification.label, Bucket.NO_SUPPORTING_SOP.value)
    )
    return predicted, summed


def calibrate(
    predicted: Bucket,
    summed: Mapping[Bucket, float],
    scaler: TemperatureScaler,
) -> BucketScore:
    """Apply temperature scaling to the summed bucket distribution.

    The correction is monotonic, so it cannot change which bucket is predicted --
    only how confident the system claims to be about it. A calibration result is
    therefore never an accuracy result, and the two must not be conflated.

    ``calibrated`` is left ``None`` when the scaler is unfitted, so
    :attr:`BucketScore.confidence` falls back to the raw value and a placeholder
    can never be reported as a measured one (``BUILD.md`` S7).
    """
    raw = min(1.0, max(0.0, summed[predicted]))

    if not scaler.fitted:
        return BucketScore(bucket=predicted, raw=raw, calibrated=None)

    logits = [math.log(max(summed[b], _EPSILON)) / scaler.temperature for b in Bucket]
    ceiling = max(logits)
    exponentiated = [math.exp(v - ceiling) for v in logits]
    total = sum(exponentiated)
    scaled = dict(zip(Bucket, (v / total for v in exponentiated), strict=True))

    return BucketScore(
        bucket=predicted,
        raw=raw,
        calibrated=min(1.0, max(0.0, scaled[predicted])),
    )


def calibrate_node(
    state: TriageState,
    bucket_of: Mapping[str, str],
    scaler: TemperatureScaler,
) -> dict[str, object]:
    """Roll the class distribution up to a bucket and correct its confidence."""
    if state.classification is None:
        return {"errors": [*state.errors, "calibrate skipped: no classification"]}

    predicted, summed = rollup(state.classification, bucket_of)
    return {"bucket_score": calibrate(predicted, summed, scaler)}


__all__ = ["calibrate", "calibrate_node", "rollup"]
