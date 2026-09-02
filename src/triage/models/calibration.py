"""Temperature scaling -- the project's contribution, in one small class.

RUNTIME for ``apply``; BUILD-TIME for ``fit``.

**The problem.** Raw softmax is systematically overconfident. A network reporting
0.95 may be right 85% of the time. That gap is exactly why an off-the-shelf 0.8
cutoff is unsound, and it is what this module measures and corrects.

**The correction.** Divide the logits by a single learned scalar before the
softmax. One parameter, fitted by minimising negative log-likelihood on the
calibration split.

**Why one parameter and not a curve.** The calibration split holds ~360 examples
across five buckets, roughly 72 each. Isotonic regression is non-parametric and
would overfit at that size; a single scalar cannot. This is a decision about data
volume, not convenience -- isotonic becomes worth revisiting only if the dataset
grows (``BUILD.md`` S5.5).

**What temperature scaling does and does not do.** It is monotonic, so it cannot
change which class is predicted: accuracy before and after is identical. It changes
only *how confident* the model claims to be, which is the number the router
thresholds against. A calibration result is therefore never an accuracy result, and
the two must not be conflated in the writeup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

#: Fitted parameters live beside the weights, so a model and its temperature
#: cannot be separated by accident.
DEFAULT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3] / "models" / "classifier" / "calibration.json"
)

#: The placeholder shipped before calibration is fitted. T = 1.0 is the identity,
#: so an uncalibrated pipeline behaves exactly as the raw model -- it does not
#: silently apply a half-fitted correction. Whether a number came from a fitted
#: temperature is recorded on the decision, and a placeholder result is never
#: reported (``BUILD.md`` S7).
IDENTITY_TEMPERATURE: Final[float] = 1.0


@dataclass(frozen=True)
class TemperatureScaler:
    """A fitted temperature, plus the provenance needed to trust it."""

    temperature: float = IDENTITY_TEMPERATURE
    fitted: bool = False
    n_examples: int = 0
    ece_before: float | None = None
    ece_after: float | None = None

    def apply(self, logits: Any) -> Any:
        """Divide logits by the temperature. Softmax is the caller's job.

        A temperature above 1.0 flattens the distribution -- the usual direction,
        since the correction is nearly always downward. Below 1.0 it sharpens.
        """
        return logits / self.temperature

    def save(self, path: Path | None = None) -> Path:
        target = path or DEFAULT_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "temperature": self.temperature,
            "fitted": self.fitted,
            "n_examples": self.n_examples,
            "ece_before": self.ece_before,
            "ece_after": self.ece_after,
            "method": "temperature_scaling",
            "note": ("Fitted on the calibration split, reported on test. Monotonic, "
                     "so accuracy is unchanged -- only confidence is corrected."),
        }, indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> TemperatureScaler:
        """Load a fitted temperature, or the identity if none exists.

        Falling back to the identity rather than raising is deliberate: the graph
        must run end to end before calibration is fitted. The ``fitted`` flag
        carries the distinction forward so a placeholder can never be mistaken for
        a result.
        """
        source = path or DEFAULT_PATH
        if not source.exists():
            return cls()
        data = json.loads(source.read_text(encoding="utf-8"))
        return cls(
            temperature=float(data["temperature"]),
            fitted=bool(data.get("fitted", True)),
            n_examples=int(data.get("n_examples", 0)),
            ece_before=data.get("ece_before"),
            ece_after=data.get("ece_after"),
        )


def expected_calibration_error(
    confidences: list[float], correct: list[bool], n_bins: int = 10,
) -> float:
    """Expected Calibration Error: the gap between claimed and actual accuracy.

    Confidences are binned; within each bin the mean confidence is compared with
    the observed accuracy, and the absolute gaps are averaged weighted by bin size.
    Zero means the model's stated confidence matches reality.

    Reported before and after fitting, on the test split, alongside reliability
    diagrams -- a single ECE number hides *where* on the confidence range the model
    is wrong, which is what the diagram shows.
    """
    if not confidences:
        return 0.0

    total = len(confidences)
    error = 0.0
    for i in range(n_bins):
        low, high = i / n_bins, (i + 1) / n_bins
        members = [
            (c, ok) for c, ok in zip(confidences, correct, strict=True)
            if (low < c <= high) or (i == 0 and c <= high)
        ]
        if not members:
            continue
        mean_confidence = sum(c for c, _ in members) / len(members)
        accuracy = sum(ok for _, ok in members) / len(members)
        error += (len(members) / total) * abs(mean_confidence - accuracy)
    return error


def fit_temperature(
    logits: Any, labels: Any, *, max_iter: int = 100, lr: float = 0.01,
) -> float:
    """Fit a single temperature by minimising NLL on the calibration split.

    BUILD-TIME. Optimised with LBFGS over one parameter, which converges in a few
    dozen iterations.

    Args:
        logits: ``(n, n_classes)`` raw logits from the calibration split.
        labels: ``(n,)`` integer class indices.

    Returns:
        The fitted temperature.
    """
    import torch

    log_temperature = torch.zeros(1, requires_grad=True)  # optimise in log space
    optimiser = torch.optim.LBFGS([log_temperature], lr=lr, max_iter=max_iter)
    loss_fn = torch.nn.CrossEntropyLoss()

    def closure() -> torch.Tensor:
        optimiser.zero_grad()
        loss = loss_fn(logits / log_temperature.exp(), labels)
        loss.backward()
        return loss

    optimiser.step(closure)  # type: ignore[arg-type]
    return float(log_temperature.exp().item())


#: Guards ``log(0)`` when a bucket carries no probability mass at all.
_EPSILON: Final[float] = 1e-12


def bucket_confidences(
    log_probabilities: list[list[float]],
    predicted: list[int],
    temperature: float,
) -> list[float]:
    """Softmax over temperature-scaled bucket log-probabilities.

    Returns the probability of the PREDICTED bucket, not the maximum.

    Those differ, and the difference is the point. The predicted bucket is the one
    holding the predicted CLASS; the argmax is the largest summed bucket. An email
    at ``account_specific`` 0.40 with three auto-answerable classes at 0.20 each has
    0.60 of bucket mass on ``auto_answerable`` and 0.40 on the bucket that actually
    applies -- so ``max`` reports 0.60 for a decision made at 0.40. On the
    calibration split the two disagree on 38 of 401 emails (9.5%), mean gap 0.109.

    :func:`triage.nodes.calibrate.calibrate` returns ``p[predicted]`` and the router
    thresholds that value, so scoring ``max`` here would fit the temperature against
    a number the runtime never reads.
    """
    import math

    out: list[float] = []
    for row, index in zip(log_probabilities, predicted, strict=True):
        scaled = [v / temperature for v in row]
        ceiling = max(scaled)
        exponentiated = [math.exp(v - ceiling) for v in scaled]
        out.append(exponentiated[index] / sum(exponentiated))
    return out


def bucket_log_probabilities(
    rows: Any,
    classifier: Any,
    bucket_of: dict[str, str],
    batch_size: int = 64,
) -> tuple[list[list[float]], list[int], list[int]]:
    """Return per-email bucket log-probabilities, predictions and true buckets.

    The true bucket is the bucket of the true CLASS -- the label the generator
    recorded, mapped through the same frontmatter-derived map the runtime uses.
    """
    import math

    from triage.nodes.calibrate import rollup
    from triage.schemas import Bucket

    order = list(Bucket)
    index_of = {bucket: i for i, bucket in enumerate(order)}

    log_probabilities: list[list[float]] = []
    predicted: list[int] = []
    truth: list[int] = []

    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        for row, classification in zip(
            chunk, classifier.predict_batch([r.email.text for r in chunk]), strict=True
        ):
            bucket, summed = rollup(classification, bucket_of)
            log_probabilities.append([math.log(max(summed[b], _EPSILON)) for b in order])
            predicted.append(index_of[bucket])
            truth.append(index_of[Bucket(bucket_of.get(row.label, Bucket.NO_SUPPORTING_SOP.value))])

    return log_probabilities, predicted, truth
