"""Risk-coverage -- the headline result.

EVAL-TIME.

The question an agency actually has is not "can AI draft replies to citizens" but
*what fraction of my inbox can I safely automate, and at what error rate?* That is
a curve, not a number, and this module computes it.

**Coverage** is the share of items the system acted on without a human: auto-replies
plus redirects. A redirect counts -- under the no-back-door policy a clean redirect
is the correct outcome rather than a failure (``BUILD.md`` S5.6).

**Risk** is the share of those automated actions that were wrong: the class was
misrouted, so the citizen received a reply grounded in the wrong procedure, was
redirected to the wrong agency, or was answered when they should have been
escalated. Risk is measured over the *automated* items only -- it is the error rate
an agency would be accepting in exchange for that coverage.

**The curve comes from the real router**, swept over a global multiplier on every
per-bucket threshold, rather than from a reimplementation of the decision rule. A
reimplementation is a second thing to keep in step, and the one thing that must not
drift from the system is the description of when it declines to act.

**Reported per topic, never as an aggregate.** A single "X% of the inbox" figure
depends on the class volume mix, which is unpublished, seasonal and
unascertainable; asserting one would be a fabricated denominator. Per-topic coverage
is composable -- an agency knows its own mix and multiplies through (``sop_design.md``
S7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


#: One evaluated item, reduced to what the curve needs.
@dataclass(frozen=True)
class Outcome:
    """The result of routing one email at one threshold multiplier."""

    label: str
    automated: bool
    correct: bool

    @property
    def wrong_automation(self) -> bool:
        """An automated action taken on a misrouted email -- the citizen-facing failure."""
        return self.automated and not self.correct


@dataclass(frozen=True)
class CurvePoint:
    """Coverage and risk at one operating point."""

    multiplier: float
    coverage: float
    risk: float
    n: int
    n_automated: int
    n_wrong: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "multiplier": round(self.multiplier, 4),
            "coverage": round(self.coverage, 4),
            "risk": round(self.risk, 4),
            "n": self.n,
            "n_automated": self.n_automated,
            "n_wrong": self.n_wrong,
        }


def curve_point(multiplier: float, outcomes: list[Outcome]) -> CurvePoint:
    """Reduce a set of outcomes at one multiplier to a coverage/risk pair.

    Risk is undefined when nothing is automated -- there is no denominator. It is
    reported as 0.0, which is correct in the sense that no citizen was exposed to
    an error, and unambiguous because ``n_automated`` accompanies it.
    """
    n = len(outcomes)
    automated = [o for o in outcomes if o.automated]
    wrong = [o for o in automated if not o.correct]
    return CurvePoint(
        multiplier=multiplier,
        coverage=len(automated) / n if n else 0.0,
        risk=len(wrong) / len(automated) if automated else 0.0,
        n=n,
        n_automated=len(automated),
        n_wrong=len(wrong),
    )


def aurc(points: list[CurvePoint]) -> float:
    """Area under the risk-coverage curve, by the trapezoid rule.

    Lower is better: it summarises risk accumulated across the whole coverage range,
    so it compares two systems without first agreeing on an operating point. It is a
    summary of the curve and not a substitute for it -- the curve is what an operator
    reads to choose a threshold.
    """
    ordered = sorted(points, key=lambda p: p.coverage)
    if len(ordered) < 2:
        return 0.0

    area = 0.0
    for left, right in zip(ordered, ordered[1:], strict=False):
        width = right.coverage - left.coverage
        area += width * (left.risk + right.risk) / 2

    span = ordered[-1].coverage - ordered[0].coverage
    return area / span if span > 0 else 0.0


@dataclass(frozen=True)
class RiskCoverageReport:
    """The curve overall and per topic."""

    overall: tuple[CurvePoint, ...]
    per_topic: dict[str, tuple[CurvePoint, ...]]
    aurc_overall: float
    aurc_per_topic: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "note": (
                "Reported per topic. An aggregate inbox figure would need a class "
                "volume mix that is unpublished and seasonal; per-topic coverage is "
                "composable and an agency can multiply through its own mix."
            ),
            "aurc_overall": round(self.aurc_overall, 4),
            "overall": [p.as_dict() for p in self.overall],
            "aurc_per_topic": {k: round(v, 4) for k, v in sorted(self.aurc_per_topic.items())},
            "per_topic": {
                topic: [p.as_dict() for p in points]
                for topic, points in sorted(self.per_topic.items())
            },
        }

    def operating_point(self, max_risk: float) -> CurvePoint | None:
        """The highest-coverage point whose risk stays within ``max_risk``.

        This is how a threshold is actually chosen: an agency states the error rate
        it can accept and reads off the coverage that buys, rather than picking a
        confidence cutoff and discovering the error rate afterwards.
        """
        eligible = [p for p in self.overall if p.risk <= max_risk]
        return max(eligible, key=lambda p: p.coverage) if eligible else None


def risk_coverage_report(
    outcomes_by_multiplier: dict[float, list[Outcome]],
) -> RiskCoverageReport:
    """Build the curve overall and per topic from swept outcomes."""
    overall = tuple(
        curve_point(m, outcomes) for m, outcomes in sorted(outcomes_by_multiplier.items())
    )

    topics: set[str] = {o.label for outcomes in outcomes_by_multiplier.values() for o in outcomes}
    per_topic: dict[str, tuple[CurvePoint, ...]] = {}
    for topic in topics:
        points: list[CurvePoint] = []
        for multiplier, outcomes in sorted(outcomes_by_multiplier.items()):
            subset = [o for o in outcomes if o.label == topic]
            if subset:
                points.append(curve_point(multiplier, subset))
        per_topic[topic] = tuple(points)

    return RiskCoverageReport(
        overall=overall,
        per_topic=per_topic,
        aurc_overall=aurc(list(overall)),
        aurc_per_topic={t: aurc(list(p)) for t, p in per_topic.items()},
    )


def plot_risk_coverage(
    report: RiskCoverageReport, path: Path, title: str = "", max_topics: int = 12
) -> Path | None:
    """Write the risk-coverage figure. Returns None if matplotlib is absent."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))

    overall = sorted(report.overall, key=lambda p: p.coverage)
    axes[0].plot(
        [p.coverage for p in overall], [p.risk for p in overall],
        "o-", color="#C44E52", markersize=4, linewidth=1.6,
    )
    axes[0].set_title(f"Overall   AURC = {report.aurc_overall:.4f}")
    axes[0].set_xlabel("coverage (share automated)")
    axes[0].set_ylabel("risk (error rate among automated)")
    axes[0].grid(alpha=0.25)

    colours = plt.get_cmap("tab20")
    for i, (topic, points) in enumerate(sorted(report.per_topic.items())[:max_topics]):
        ordered = sorted(points, key=lambda p: p.coverage)
        axes[1].plot(
            [p.coverage for p in ordered], [p.risk for p in ordered],
            "o-", markersize=3, linewidth=1.2, color=colours(i % 20), label=topic,
        )
    axes[1].set_title("Per topic")
    axes[1].set_xlabel("coverage (share automated)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(fontsize=6.5, loc="upper left", ncol=2)

    figure.suptitle(title or "Risk-coverage — test split, swept over the real router")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


__all__ = [
    "CurvePoint", "Outcome", "RiskCoverageReport", "aurc", "curve_point",
    "plot_risk_coverage", "risk_coverage_report",
]
