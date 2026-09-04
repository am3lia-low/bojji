"""Scenario-cluster bootstrap intervals for the headline evaluation metrics.

EVAL-TIME.

The generated emails are *variants nested inside authored scenarios*. Treating the
877 test emails as 877 independent observations would produce intervals that are
far too narrow: wording variants from one situation share the same intent and much
of the same difficulty. This module therefore resamples whole ``scenario_id``
clusters within true-class strata, with replacement, and carries every email in a
selected scenario into a bootstrap replicate. Preserving the designed class strata
prevents a replicate from dropping one of the few scenarios for a class and silently
changing the meaning of macro-F1.

The percentile intervals describe variation across the scenarios observed in the
frozen test split. They do not quantify distribution shift, synthetic-data bias, or
uncertainty about situations absent from the corpus. A degenerate interval when no
observed scenario contains a failure is called out explicitly rather than presented
as proof of zero deployment risk.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from eval.metrics.classification import classification_report


@dataclass(frozen=True)
class UncertaintyItem:
    """One routed test item reduced to the fields needed by the bootstrap."""

    scenario_id: str
    true_class: str
    predicted_class: str
    true_bucket: str
    predicted_bucket: str
    route: str
    automated: bool
    correct_automation: bool
    must_escalate: bool
    must_escalate_caught: bool


@dataclass(frozen=True)
class MetricInterval:
    """Point estimate and percentile confidence interval for one metric."""

    estimate: float
    lower: float
    upper: float
    confidence: float
    valid_resamples: int
    degenerate: bool

    def as_dict(self) -> dict[str, float | int | bool | str]:
        return {
            "estimate": round(self.estimate, 4),
            "lower": round(self.lower, 4),
            "upper": round(self.upper, 4),
            "confidence": self.confidence,
            "valid_resamples": self.valid_resamples,
            "degenerate": self.degenerate,
        }


Metric = Callable[[list[UncertaintyItem]], float | None]


def _quantile(values: list[float], probability: float) -> float:
    """Linear-interpolated quantile, avoiding a SciPy dependency."""
    if not values:
        raise ValueError("cannot take a quantile of an empty sample")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")

    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _accuracy(items: list[UncertaintyItem]) -> float:
    return (
        sum(item.true_bucket == item.predicted_bucket for item in items) / len(items)
        if items
        else 0.0
    )


def _coverage(items: list[UncertaintyItem]) -> float:
    return sum(item.automated for item in items) / len(items) if items else 0.0


def _risk(items: list[UncertaintyItem]) -> float | None:
    automated = [item for item in items if item.automated]
    if not automated:
        return None
    return sum(not item.correct_automation for item in automated) / len(automated)


def _route_coverage(items: list[UncertaintyItem], route: str) -> float:
    return sum(item.route == route for item in items) / len(items) if items else 0.0


def _route_risk(items: list[UncertaintyItem], route: str) -> float | None:
    routed = [item for item in items if item.route == route]
    if not routed:
        return None
    return sum(not item.correct_automation for item in routed) / len(routed)


def _must_escalate_recall(items: list[UncertaintyItem]) -> float | None:
    required = [item for item in items if item.must_escalate]
    if not required:
        return None
    return sum(item.must_escalate_caught for item in required) / len(required)


def _macro_f1(
    items: list[UncertaintyItem], labels: tuple[str, ...], *, bucket: bool
) -> float:
    truth = [item.true_bucket if bucket else item.true_class for item in items]
    predicted = [item.predicted_bucket if bucket else item.predicted_class for item in items]
    return classification_report(truth, predicted, labels=labels).macro_f1


def cluster_bootstrap_report(
    items: list[UncertaintyItem],
    *,
    class_labels: tuple[str, ...],
    bucket_labels: tuple[str, ...],
    n_resamples: int = 2_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict[str, Any]:
    """Return percentile intervals after resampling whole scenarios.

    The number of sampled clusters in each replicate equals the observed number of
    test scenarios. Selecting one cluster twice repeats all of its email variants,
    which is the standard non-parametric cluster bootstrap.
    """
    if not items:
        raise ValueError("at least one item is required")
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")
    if any(not item.scenario_id for item in items):
        raise ValueError("every item needs a scenario_id for clustered resampling")

    clusters: dict[str, list[UncertaintyItem]] = defaultdict(list)
    for item in items:
        clusters[item.scenario_id].append(item)
    cluster_ids = sorted(clusters)
    scenario_classes = {
        scenario_id: {item.true_class for item in scenario_items}
        for scenario_id, scenario_items in clusters.items()
    }
    if any(len(classes) != 1 for classes in scenario_classes.values()):
        raise ValueError("a scenario_id cannot span true-class strata")
    strata: dict[str, list[str]] = defaultdict(list)
    for scenario_id, classes in scenario_classes.items():
        strata[next(iter(classes))].append(scenario_id)

    metrics: Final[dict[str, Metric]] = {
        "class_macro_f1": lambda sample: _macro_f1(
            sample, class_labels, bucket=False
        ),
        "bucket_macro_f1": lambda sample: _macro_f1(
            sample, bucket_labels, bucket=True
        ),
        "bucket_accuracy": _accuracy,
        "operating_coverage": _coverage,
        "operating_risk": _risk,
        "auto_reply_coverage": lambda sample: _route_coverage(sample, "auto_reply"),
        "auto_reply_risk": lambda sample: _route_risk(sample, "auto_reply"),
        "redirect_coverage": lambda sample: _route_coverage(sample, "redirect"),
        "redirect_risk": lambda sample: _route_risk(sample, "redirect"),
        "must_escalate_recall": _must_escalate_recall,
    }

    observed = {name: metric(items) for name, metric in metrics.items()}
    draws: dict[str, list[float]] = {name: [] for name in metrics}
    rng = random.Random(seed)

    for _ in range(n_resamples):
        sampled: list[UncertaintyItem] = []
        for class_name in sorted(strata):
            stratum = sorted(strata[class_name])
            for _cluster in stratum:
                sampled.extend(clusters[rng.choice(stratum)])
        for name, metric in metrics.items():
            value = metric(sampled)
            if value is not None:
                draws[name].append(value)

    alpha = (1.0 - confidence) / 2.0
    intervals: dict[str, dict[str, float | int | bool | str]] = {}
    for name, estimate in observed.items():
        values = draws[name]
        if estimate is None or not values:
            intervals[name] = {
                "estimate": "undefined",
                "lower": "undefined",
                "upper": "undefined",
                "confidence": confidence,
                "valid_resamples": len(values),
                "degenerate": True,
            }
            continue
        interval = MetricInterval(
            estimate=estimate,
            lower=_quantile(values, alpha),
            upper=_quantile(values, 1.0 - alpha),
            confidence=confidence,
            valid_resamples=len(values),
            degenerate=min(values) == max(values),
        )
        intervals[name] = interval.as_dict()

    return {
        "method": "stratified percentile cluster bootstrap",
        "resampling_unit": "scenario_id",
        "strata": "true_class",
        "confidence": confidence,
        "n_resamples": n_resamples,
        "seed": seed,
        "n_emails": len(items),
        "n_scenarios": len(cluster_ids),
        "intervals": intervals,
        "interpretation": (
            "Intervals resample whole authored scenarios within true-class strata, "
            "not individual email variants. They preserve the benchmark's designed "
            "class mix and quantify variation across observed test scenarios only; "
            "they do not cover synthetic-data bias, distribution shift, or unseen "
            "situations. A degenerate interval with no observed failure is not proof "
            "of zero deployment risk."
        ),
    }


__all__ = ["MetricInterval", "UncertaintyItem", "cluster_bootstrap_report"]
