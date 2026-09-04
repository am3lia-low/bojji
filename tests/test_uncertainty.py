"""Scenario-cluster bootstrap tests."""

from __future__ import annotations

import pytest
from eval.metrics.uncertainty import UncertaintyItem, cluster_bootstrap_report


def item(
    scenario: str,
    true_class: str,
    predicted_class: str,
    *,
    automated: bool,
    must_escalate: bool = False,
) -> UncertaintyItem:
    true_bucket = "auto" if true_class == "filing" else "high"
    predicted_bucket = "auto" if predicted_class == "filing" else "high"
    return UncertaintyItem(
        scenario_id=scenario,
        true_class=true_class,
        predicted_class=predicted_class,
        true_bucket=true_bucket,
        predicted_bucket=predicted_bucket,
        route="auto_reply" if automated else "escalate",
        automated=automated,
        correct_automation=(not automated or true_class == predicted_class),
        must_escalate=must_escalate,
        must_escalate_caught=(not must_escalate or not automated),
    )


@pytest.fixture
def sample() -> list[UncertaintyItem]:
    # The two variants in scenario A must travel together in every replicate.
    return [
        item("A", "filing", "filing", automated=True),
        item("A", "filing", "filing", automated=True),
        item("B", "hardship", "hardship", automated=False, must_escalate=True),
        item("C", "hardship", "filing", automated=True, must_escalate=True),
    ]


def test_cluster_bootstrap_is_deterministic(sample: list[UncertaintyItem]) -> None:
    kwargs = {
        "class_labels": ("filing", "hardship"),
        "bucket_labels": ("auto", "high"),
        "n_resamples": 250,
        "confidence": 0.95,
        "seed": 19,
    }
    assert cluster_bootstrap_report(sample, **kwargs) == cluster_bootstrap_report(
        sample, **kwargs
    )


def test_point_estimates_use_the_unsampled_observations(
    sample: list[UncertaintyItem],
) -> None:
    report = cluster_bootstrap_report(
        sample,
        class_labels=("filing", "hardship"),
        bucket_labels=("auto", "high"),
        n_resamples=100,
    )

    assert report["n_scenarios"] == 3
    assert report["intervals"]["bucket_accuracy"]["estimate"] == 0.75
    assert report["intervals"]["operating_coverage"]["estimate"] == 0.75
    assert report["intervals"]["operating_risk"]["estimate"] == pytest.approx(0.3333)
    assert report["intervals"]["must_escalate_recall"]["estimate"] == 0.5


def test_degenerate_interval_is_explicit() -> None:
    rows = [
        item("A", "filing", "filing", automated=True),
        item("B", "hardship", "hardship", automated=False, must_escalate=True),
    ]
    report = cluster_bootstrap_report(
        rows,
        class_labels=("filing", "hardship"),
        bucket_labels=("auto", "high"),
        n_resamples=100,
    )

    recall = report["intervals"]["must_escalate_recall"]
    assert recall["estimate"] == 1.0
    assert recall["degenerate"] is True
    assert "not proof" in report["interpretation"]


def test_missing_scenario_id_is_rejected() -> None:
    row = item("A", "filing", "filing", automated=True)
    blank = UncertaintyItem(**{**row.__dict__, "scenario_id": ""})
    with pytest.raises(ValueError, match="scenario_id"):
        cluster_bootstrap_report(
            [blank],
            class_labels=("filing",),
            bucket_labels=("auto",),
        )
