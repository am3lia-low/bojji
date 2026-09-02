"""Calibration metrics -- ECE and the reliability diagram.

EVAL-TIME.

ECE alone is not enough, which is why the diagram is produced alongside it. A
single number averages away *where* on the confidence range a model is wrong, and
that location is what an operator setting a threshold actually needs: a model that
is well calibrated at 0.5 and badly overconfident at 0.9 has a respectable ECE and
is exactly the model a 0.8 cutoff would misuse.

Reported **on the test split, before and after**, never on the calibration split
the temperature was fitted on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from triage.models.calibration import expected_calibration_error


@dataclass(frozen=True)
class Bin:
    """One confidence bin of a reliability diagram."""

    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float

    @property
    def gap(self) -> float:
        """Claimed confidence minus observed accuracy. Positive is overconfident."""
        return self.mean_confidence - self.accuracy

    def as_dict(self) -> dict[str, float | int]:
        return {
            "lower": round(self.lower, 3),
            "upper": round(self.upper, 3),
            "count": self.count,
            "mean_confidence": round(self.mean_confidence, 4),
            "accuracy": round(self.accuracy, 4),
            "gap": round(self.gap, 4),
        }


def reliability_bins(
    confidences: list[float], correct: list[bool], n_bins: int = 10
) -> tuple[Bin, ...]:
    """Bin predictions by confidence and compare claimed against observed accuracy.

    Empty bins are returned with ``count=0`` rather than omitted, so a diagram plots
    on a fixed axis and two runs stay visually comparable.
    """
    bins: list[Bin] = []
    for i in range(n_bins):
        low, high = i / n_bins, (i + 1) / n_bins
        members = [
            (c, ok)
            for c, ok in zip(confidences, correct, strict=True)
            if (low < c <= high) or (i == 0 and c <= high)
        ]
        if members:
            bins.append(Bin(
                lower=low, upper=high, count=len(members),
                mean_confidence=sum(c for c, _ in members) / len(members),
                accuracy=sum(ok for _, ok in members) / len(members),
            ))
        else:
            bins.append(Bin(lower=low, upper=high, count=0, mean_confidence=0.0, accuracy=0.0))
    return tuple(bins)


@dataclass(frozen=True)
class CalibrationReport:
    """ECE and reliability, before and after temperature scaling."""

    ece_before: float
    ece_after: float
    bins_before: tuple[Bin, ...]
    bins_after: tuple[Bin, ...]
    temperature: float
    n: int

    @property
    def improvement(self) -> float:
        """Reduction in ECE. Negative means scaling made calibration worse."""
        return self.ece_before - self.ece_after

    def as_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "temperature": round(self.temperature, 4),
            "ece_before": round(self.ece_before, 4),
            "ece_after": round(self.ece_after, 4),
            "ece_improvement": round(self.improvement, 4),
            "direction": "sharpened" if self.temperature < 1 else "flattened",
            "bins_before": [b.as_dict() for b in self.bins_before],
            "bins_after": [b.as_dict() for b in self.bins_after],
        }


def calibration_report(
    raw_confidences: list[float],
    calibrated_confidences: list[float],
    correct: list[bool],
    temperature: float,
    n_bins: int = 10,
) -> CalibrationReport:
    """Compare calibration before and after scaling, on the same predictions.

    ``correct`` is shared between the two because temperature scaling is monotonic
    and cannot change which bucket is predicted. That is the property worth stating
    in the writeup: a calibration result is never an accuracy result.
    """
    return CalibrationReport(
        ece_before=expected_calibration_error(raw_confidences, correct, n_bins),
        ece_after=expected_calibration_error(calibrated_confidences, correct, n_bins),
        bins_before=reliability_bins(raw_confidences, correct, n_bins),
        bins_after=reliability_bins(calibrated_confidences, correct, n_bins),
        temperature=temperature,
        n=len(correct),
    )


def plot_reliability(report: CalibrationReport, path: Path, title: str = "") -> Path | None:
    """Write a before/after reliability diagram. Returns None if matplotlib is absent.

    The plot is a deliverable the README cites, so it is generated from the same
    report object the JSON is written from -- the figure and the numbers cannot
    disagree.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for axis, bins, name, ece in (
        (axes[0], report.bins_before, "Before (raw)", report.ece_before),
        (axes[1], report.bins_after, f"After (T={report.temperature:.3f})", report.ece_after),
    ):
        centres = [(b.lower + b.upper) / 2 for b in bins]
        axis.plot([0, 1], [0, 1], "--", color="#888", linewidth=1, label="perfect")
        axis.bar(
            centres, [b.accuracy for b in bins], width=0.09,
            color="#4C72B0", edgecolor="white", label="observed accuracy",
        )
        axis.plot(
            [c for c, b in zip(centres, bins, strict=True) if b.count],
            [b.mean_confidence for b in bins if b.count],
            "o-", color="#C44E52", markersize=4, linewidth=1.2, label="mean confidence",
        )
        axis.set_title(f"{name}   ECE = {ece:.4f}")
        axis.set_xlabel("confidence")
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.grid(alpha=0.25)

    axes[0].set_ylabel("accuracy")
    axes[0].legend(loc="upper left", fontsize=8)
    figure.suptitle(title or "Reliability — bucket confidence, test split")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


__all__ = ["Bin", "CalibrationReport", "calibration_report", "plot_reliability", "reliability_bins"]
