"""Calibration and the bucket rollup.

Two properties carry the contribution and are pinned here:

**Temperature scaling is monotonic**, so it cannot change which bucket is
predicted. Accuracy before and after is identical, and only the claimed confidence
moves. A calibration result is therefore never an accuracy result -- conflating them
in the writeup would be a real error, so the code is held to it.

**The rollup predicts the bucket of the predicted CLASS**, not the argmax of the
summed distribution. Those can differ, and the difference matters: the SOP lookup,
the drafter and the grounding metric all key off the class, so a bucket that
disagreed would apply a policy belonging to a class the rest of the pipeline never
used.
"""

from __future__ import annotations

import math

import pytest

from triage.models.calibration import (
    IDENTITY_TEMPERATURE,
    TemperatureScaler,
    expected_calibration_error,
)
from triage.nodes.calibrate import calibrate, rollup
from triage.schemas import Bucket, Classification

BUCKET_OF = {
    "filing": "auto_answerable",
    "payment": "auto_answerable",
    "residency": "auto_answerable",
    "account_specific": "requires_account_lookup",
    "hardship_or_waiver": "high_consequence",
    "oos_business_tax": "out_of_scope",
}


def classification(scores: dict[str, float], label: str | None = None) -> Classification:
    total = sum(scores.values())
    normalised = {k: v / total for k, v in scores.items()}
    return Classification(
        label=label or max(normalised, key=lambda k: normalised[k]),
        probabilities=normalised,
        model_name="test",
    )


# --------------------------------------------------------------------------- #
# Rollup
# --------------------------------------------------------------------------- #


def test_rollup_sums_within_bucket():
    """Three auto-answerable classes at 0.2 each is a 0.6 auto-answerable bucket."""
    result = classification({
        "filing": 0.2, "payment": 0.2, "residency": 0.2,
        "account_specific": 0.4,
    }, label="account_specific")

    bucket, summed = rollup(result, BUCKET_OF)

    assert summed[Bucket.AUTO_ANSWERABLE] == pytest.approx(0.6)
    assert summed[Bucket.REQUIRES_ACCOUNT_LOOKUP] == pytest.approx(0.4)
    assert bucket is Bucket.REQUIRES_ACCOUNT_LOOKUP, "bucket follows the predicted class"


def test_rollup_follows_the_class_not_the_argmax_bucket():
    """The distinguishing case: the class's bucket is NOT the largest bucket.

    Predicted class is ``account_specific`` at 0.4, but the auto-answerable bucket
    sums to 0.6. Following the argmax bucket here would auto-reply to an enquiry
    about a taxpayer's own record -- the exact failure the design exists to prevent.
    """
    result = classification({
        "filing": 0.2, "payment": 0.2, "residency": 0.2,
        "account_specific": 0.4,
    }, label="account_specific")

    bucket, summed = rollup(result, BUCKET_OF)

    assert summed[Bucket.AUTO_ANSWERABLE] > summed[Bucket.REQUIRES_ACCOUNT_LOOKUP]
    assert bucket is Bucket.REQUIRES_ACCOUNT_LOOKUP


def test_rollup_sums_to_one():
    result = classification({"filing": 0.5, "account_specific": 0.3, "hardship_or_waiver": 0.2})
    _, summed = rollup(result, BUCKET_OF)

    assert sum(summed.values()) == pytest.approx(1.0)


def test_unknown_class_rolls_into_no_supporting_sop():
    result = classification({"mystery_class": 0.9, "filing": 0.1}, label="mystery_class")
    bucket, summed = rollup(result, BUCKET_OF)

    assert bucket is Bucket.NO_SUPPORTING_SOP
    assert summed[Bucket.NO_SUPPORTING_SOP] == pytest.approx(0.9)


# --------------------------------------------------------------------------- #
# Temperature scaling
# --------------------------------------------------------------------------- #


def test_unfitted_scaler_leaves_calibrated_none():
    """The pipeline runs before calibration exists; a placeholder must be visible."""
    result = classification({"filing": 0.7, "account_specific": 0.3})
    bucket, summed = rollup(result, BUCKET_OF)

    score = calibrate(bucket, summed, TemperatureScaler())

    assert score.calibrated is None
    assert score.confidence == score.raw, "falls back to raw when unfitted"


def test_identity_temperature_is_a_no_op():
    result = classification({"filing": 0.7, "account_specific": 0.3})
    bucket, summed = rollup(result, BUCKET_OF)

    score = calibrate(
        bucket, summed, TemperatureScaler(temperature=IDENTITY_TEMPERATURE, fitted=True)
    )

    assert score.calibrated == pytest.approx(score.raw, abs=1e-6)


@pytest.mark.parametrize("temperature", [0.5, 0.7, 1.0, 1.5, 2.5])
def test_scaling_never_changes_the_predicted_bucket(temperature):
    """Monotonic: accuracy is identical before and after. The core claim."""
    result = classification({
        "filing": 0.3, "payment": 0.1, "account_specific": 0.35,
        "hardship_or_waiver": 0.15, "oos_business_tax": 0.1,
    }, label="account_specific")
    bucket, summed = rollup(result, BUCKET_OF)

    score = calibrate(bucket, summed, TemperatureScaler(temperature=temperature, fitted=True))

    assert score.bucket is bucket


def test_temperature_above_one_flattens():
    result = classification({"filing": 0.8, "account_specific": 0.2})
    bucket, summed = rollup(result, BUCKET_OF)

    hot = calibrate(bucket, summed, TemperatureScaler(temperature=2.0, fitted=True))

    assert hot.calibrated < hot.raw, "T > 1 must reduce confidence"


def test_temperature_below_one_sharpens():
    """The direction the fitted value actually took, because the rollup underconfidences."""
    result = classification({"filing": 0.8, "account_specific": 0.2})
    bucket, summed = rollup(result, BUCKET_OF)

    cold = calibrate(bucket, summed, TemperatureScaler(temperature=0.5, fitted=True))

    assert cold.calibrated > cold.raw, "T < 1 must increase confidence"


def test_calibrated_confidence_stays_a_probability():
    for temperature in (0.1, 0.5, 1.0, 3.0, 10.0):
        result = classification({"filing": 0.99, "account_specific": 0.01})
        bucket, summed = rollup(result, BUCKET_OF)
        score = calibrate(bucket, summed, TemperatureScaler(temperature=temperature, fitted=True))

        assert 0.0 <= score.confidence <= 1.0


def test_zero_mass_bucket_does_not_raise():
    """log(0) is guarded: a bucket holding no mass is representable, its log is not."""
    result = classification({"filing": 1.0})
    bucket, summed = rollup(result, BUCKET_OF)

    score = calibrate(bucket, summed, TemperatureScaler(temperature=0.7, fitted=True))

    assert not math.isnan(score.confidence)
    assert not math.isinf(score.confidence)


# --------------------------------------------------------------------------- #
# ECE
# --------------------------------------------------------------------------- #


def test_perfect_calibration_scores_zero():
    """Half the predictions at 0.5 confidence, half of them right."""
    confidences = [0.5] * 100
    correct = [i % 2 == 0 for i in range(100)]

    assert expected_calibration_error(confidences, correct) == pytest.approx(0.0, abs=1e-9)


def test_total_overconfidence_scores_one():
    confidences = [1.0] * 50
    correct = [False] * 50

    assert expected_calibration_error(confidences, correct) == pytest.approx(1.0)


def test_ece_of_nothing_is_zero():
    assert expected_calibration_error([], []) == 0.0


def test_scaler_round_trips_through_disk(tmp_path):
    """A model and its temperature must not be separable by accident."""
    original = TemperatureScaler(
        temperature=0.6831, fitted=True, n_examples=401,
        ece_before=0.288, ece_after=0.168,
    )
    path = original.save(tmp_path / "calibration.json")
    loaded = TemperatureScaler.load(path)

    assert loaded.temperature == pytest.approx(original.temperature)
    assert loaded.fitted
    assert loaded.n_examples == 401


def test_missing_file_loads_the_identity():
    """Falling back rather than raising: the graph must run before calibration exists."""
    loaded = TemperatureScaler.load(pytest.importorskip("pathlib").Path("does_not_exist.json"))

    assert loaded.temperature == IDENTITY_TEMPERATURE
    assert not loaded.fitted
