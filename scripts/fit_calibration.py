"""Fit the temperature on the calibration split.

BUILD-TIME. Writes ``models/classifier/calibration.json``.

**What is calibrated is the bucket distribution, not the class distribution.**
Thresholds are per bucket, so the confidence the router compares against a
threshold is the summed bucket probability -- and that is the quantity whose
reliability has to hold. Fitting on the 12-class distribution and applying to the
5-bucket one would fit a correction for a number the router never reads.

Summation happens in probability space, after the softmax, so there are no bucket
logits to divide. The bucket distribution is mapped back to log space and the
temperature applied there, which :func:`triage.nodes.calibrate.calibrate` mirrors
exactly -- the fit and its application are the same transformation by construction.

**Fitted on calibration, reported on test.** This script touches the calibration
split only. ``eval/run_eval.py`` measures ECE on test. Reporting the fit split
would be reporting on training data for the very quantity being measured.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from triage.env import load_env  # noqa: E402

load_env()

from eval.dataset import Labelled, split  # noqa: E402

from triage.models.calibration import (  # noqa: E402
    TemperatureScaler,
    expected_calibration_error,
)
from triage.models.encoder import EncoderClassifier  # noqa: E402
from triage.nodes.calibrate import rollup  # noqa: E402
from triage.schemas import Bucket  # noqa: E402

_EPSILON = 1e-12


def bucket_log_probabilities(
    rows: tuple[Labelled, ...],
    classifier: EncoderClassifier,
    bucket_of: dict[str, str],
    batch_size: int = 64,
) -> tuple[list[list[float]], list[int], list[int]]:
    """Return per-email bucket log-probabilities, predictions and true buckets.

    The true bucket is the bucket of the true CLASS -- the label the generator
    recorded, mapped through the same frontmatter-derived map the runtime uses.
    """
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


def _confidences(log_probabilities: list[list[float]], temperature: float) -> list[float]:
    """Softmax over temperature-scaled bucket log-probabilities; return the max."""
    out: list[float] = []
    for row in log_probabilities:
        scaled = [v / temperature for v in row]
        ceiling = max(scaled)
        exponentiated = [math.exp(v - ceiling) for v in scaled]
        total = sum(exponentiated)
        out.append(max(v / total for v in exponentiated))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="where to write calibration.json")
    parser.add_argument("--check", action="store_true", help="fit and report, write nothing")
    args = parser.parse_args()

    from triage.sop.index import build_index

    rows = split("calibration")
    if not rows:
        print("no calibration split found; run scripts/make_splits.py", file=sys.stderr)
        return 1

    classifier = EncoderClassifier()
    bucket_of = dict(build_index().bucket)

    print(f"fitting on {len(rows)} calibration examples ...")
    log_probabilities, predicted, truth = bucket_log_probabilities(rows, classifier, bucket_of)

    import torch

    from triage.models.calibration import fit_temperature

    logits = torch.tensor(log_probabilities, dtype=torch.float32)
    labels = torch.tensor(truth, dtype=torch.long)
    temperature = fit_temperature(logits, labels)

    correct = [p == t for p, t in zip(predicted, truth, strict=True)]
    ece_before = expected_calibration_error(_confidences(log_probabilities, 1.0), correct)
    ece_after = expected_calibration_error(_confidences(log_probabilities, temperature), correct)

    scaler = TemperatureScaler(
        temperature=temperature,
        fitted=True,
        n_examples=len(rows),
        ece_before=ece_before,
        ece_after=ece_after,
    )

    accuracy = sum(correct) / len(correct)
    print(f"  bucket accuracy   {accuracy:.4f}   (unchanged by scaling -- it is monotonic)")
    direction = "flattens" if temperature > 1 else "sharpens"
    print(f"  temperature       {temperature:.4f}   ({direction})")
    print(f"  ECE before        {ece_before:.4f}")
    print(f"  ECE after         {ece_after:.4f}   [calibration split -- NOT the reported figure]")

    if args.check:
        print("\n--check: nothing written.")
        return 0

    written = scaler.save(args.out)
    print(f"\nwrote {written}")
    print("Reported ECE comes from eval/run_eval.py on the test split.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
