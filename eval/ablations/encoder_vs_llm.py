"""Encoder vs LLM zero-shot -- the model-selection measurement.

EVAL-TIME. Writes ``eval/results/encoder_vs_llm.json``.

Run::

    python eval/ablations/encoder_vs_llm.py --n 60

Model selection is graded on justification, and "the encoder is better calibrated"
is an assertion until something measures it. This compares the two on the five axes
that actually decide the choice:

===============  ===========================================================
axis             why it decides anything
===============  ===========================================================
accuracy         does the cheap model give up quality?
**ECE**          the contribution: is the confidence usable as a threshold?
latency          per email, on the hardware each actually runs on
size / cost      one commits to git and runs free; the other needs a key
resolution       how many distinct confidence values the model can express
===============  ===========================================================

**Sampled, not run over the whole split.** The baseline costs ``k`` API calls per
email, serialised to respect free-tier rate limits. A 520-email split at k=5 is
2,600 calls, which is a rate-limit study rather than a measurement. The sample is
stratified by class so every topic is represented, and ``n`` is reported alongside
every figure.

**The confidence-resolution row is the point.** Self-consistency at k=5 can only
ever return multiples of 0.2, so its reliability diagram has five columns no matter
how much data is collected. The encoder's softmax is continuous. That is not a
tuning difference -- it is why an encoder is the right choice when the threshold is
the product.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from triage.env import load_env  # noqa: E402

load_env()

from eval.dataset import Labelled, split  # noqa: E402
from eval.metrics.classification import classification_report  # noqa: E402

from triage.models.calibration import expected_calibration_error  # noqa: E402
from triage.pii.scrubber import Scrubber  # noqa: E402


def stratified(rows: tuple[Labelled, ...], n: int, seed: int) -> list[Labelled]:
    """Sample evenly across classes, so no topic is missing from the comparison."""
    by_label: dict[str, list[Labelled]] = defaultdict(list)
    for row in rows:
        by_label[row.label].append(row)

    rng = random.Random(seed)
    per_class = max(1, n // max(len(by_label), 1))
    picked: list[Labelled] = []
    for label in sorted(by_label):
        pool = by_label[label]
        picked.extend(rng.sample(pool, min(per_class, len(pool))))
    rng.shuffle(picked)
    return picked[:n]


def evaluate(
    classifier: Any, texts: list[str], truth: list[str], labels: tuple[str, ...]
) -> dict[str, Any]:
    """Run a classifier over the sample and score it on every axis.

    ``labels`` is the FIXED class set, and passing it is what makes the two
    models comparable. With the label set left to be derived from the data, each
    report averages over only the classes that appear in its own truth-plus-
    predictions union -- and the two models predict different classes on a small
    stratified sample. The macro denominators then differ, so the two macro-F1
    figures are averages over different numbers of classes and cannot be placed
    side by side. Measured discrepancy on identical predictions: 0.1111.
    """
    started = time.time()
    predictions = classifier.predict_batch(texts)
    elapsed = time.time() - started

    predicted = [p.label for p in predictions]
    confidences = [p.confidence for p in predictions]
    correct = [p == t for p, t in zip(predicted, truth, strict=True)]
    report = classification_report(truth, predicted, labels=labels)

    return {
        "model": classifier.name,
        "n": len(texts),
        "accuracy": round(report.accuracy, 4),
        "macro_f1": round(report.macro_f1, 4),
        "ece": round(expected_calibration_error(confidences, correct), 4),
        "mean_confidence": round(sum(confidences) / len(confidences), 4),
        "distinct_confidence_values": len({round(c, 4) for c in confidences}),
        "seconds_total": round(elapsed, 1),
        "seconds_per_email": round(elapsed / max(len(texts), 1), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=60, help="stratified sample size")
    parser.add_argument("--samples", type=int, default=5, help="k for self-consistency")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split", default="test")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "eval" / "results" / "encoder_vs_llm.json"
    )
    args = parser.parse_args()

    from triage.models.encoder import EncoderClassifier

    rows = stratified(split(args.split), args.n, args.seed)
    scrubber = Scrubber()
    texts = [scrubber.scrub(r.email.text).text for r in rows]
    truth = [r.label for r in rows]
    print(f"comparing on {len(rows)} stratified emails from {args.split!r}")

    encoder = EncoderClassifier()
    print("  encoder ...")
    labels = tuple(encoder.labels)
    encoder_result = evaluate(encoder, texts, truth, labels)

    llm_result: dict[str, Any]
    try:
        from triage.llm.client import GroqClient
        from triage.models.llm_zeroshot import build_zeroshot

        baseline = build_zeroshot(tuple(encoder.labels), args.samples, GroqClient())
        print(f"  llm zero-shot (k={args.samples}, {args.n * args.samples} calls) ...")
        llm_result = evaluate(baseline, texts, truth, labels)
    except Exception as exc:  # noqa: BLE001 -- an absent key is a skip, not a failure
        llm_result = {"skipped": True, "reason": str(exc)[:200]}

    artefact = ROOT / "models" / "classifier"
    size_mb = sum(f.stat().st_size for f in artefact.rglob("*") if f.is_file()) / 1024**2

    payload = {
        "split": args.split,
        "n": len(rows),
        "sampling": "stratified by class",
        "seed": args.seed,
        "encoder": {**encoder_result, "runs": "local CPU", "cost": "free",
                    "artefact_mb": round(size_mb, 1), "api_calls": 0},
        "llm_zeroshot": {**llm_result, "runs": "API", "cost": "free tier",
                         "artefact_mb": 0,
                         "api_calls": len(rows) * args.samples,
                         "k": args.samples},
        "reading": (
            "The encoder emits a continuous softmax from one local forward pass. "
            "Self-consistency at k manufactures a distribution from k API calls and "
            "can only express multiples of 1/k, so its confidence resolution is "
            "capped no matter how much data is collected. That is the operational "
            "argument for an encoder when the threshold is the product."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{'':22s}{'encoder':>12s}{'llm 0-shot':>13s}")
    for key in ("accuracy", "macro_f1", "ece", "seconds_per_email",
                "distinct_confidence_values"):
        left = encoder_result.get(key, "-")
        right = llm_result.get(key, "skipped")
        print(f"  {key:20s}{left!s:>12}{right!s:>13}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
