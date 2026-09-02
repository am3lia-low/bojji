"""The evaluation entrypoint. One command, everything reported.

EVAL-TIME. Writes ``eval/results/``, which is committed so the README cites files
rather than remembered numbers -- the structural guard against a code/writeup
mismatch.

Run::

    python eval/run_eval.py                 # full run on the test split
    python eval/run_eval.py --limit 50      # quick smoke
    python eval/run_eval.py --no-draft      # routing only, no API calls

**Everything is measured on the test split.** The temperature was fitted on
``calibration``; reporting there would be reporting on training data for the very
quantity being measured.

**One pass, then a sweep.** Classification is the expensive step, so each email is
classified once and the resulting distributions are re-routed at each threshold
multiplier. The sweep calls the real router -- so the risk-coverage curve cannot
drift from the system it describes -- but does not re-run the model.

**Drafting is sampled, not run over the whole split.** Drafting every test item
would be ~370 free-tier calls to produce text that only ~50 sampled drafts are
judged on. The sample size is what the judge budget supports (``BUILD.md`` S6.3),
and drafting availability is reported over the sample with its denominator stated.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from triage.env import load_env  # noqa: E402

load_env()

from eval.dataset import Labelled, split  # noqa: E402
from eval.metrics.calibration import calibration_report, plot_reliability  # noqa: E402
from eval.metrics.classification import binary_report, classification_report  # noqa: E402
from eval.metrics.escalation import escalation_report, expected_reason  # noqa: E402
from eval.metrics.pii_recall import scrub_report  # noqa: E402
from eval.metrics.risk_coverage import (  # noqa: E402
    Outcome,
    plot_risk_coverage,
    risk_coverage_report,
)
from triage.models.calibration import TemperatureScaler  # noqa: E402
from triage.nodes.calibrate import calibrate, rollup  # noqa: E402
from triage.nodes.flags import detect_flags  # noqa: E402
from triage.nodes.route import load_thresholds, route  # noqa: E402
from triage.pii.scrubber import Scrubber, ScrubResult  # noqa: E402
from triage.schemas import Bucket, Flag  # noqa: E402
from triage.sop.index import SOPIndex, build_index  # noqa: E402

RESULTS = ROOT / "eval" / "results"

#: Threshold multipliers swept to trace the curve. Read from config so the sweep
#: and the policy it sweeps live in the same file.
DEFAULT_SWEEP = (0.2, 2.0, 37)


@dataclass
class Row:
    """One test email carried through the pipeline, holding everything metrics need."""

    item: Labelled
    scrubbed: str
    predicted: str
    probabilities: dict[str, float]
    bucket: Bucket
    summed: dict[Bucket, float]
    raw_confidence: float
    calibrated_confidence: float
    flags: frozenset[Flag]
    true_bucket: Bucket


def sweep_multipliers(config: dict[str, Any]) -> list[float]:
    """Read the sweep from ``config/thresholds.yaml``."""
    sweep = config.get("sweep") or {}
    low = float(sweep.get("multiplier_min", DEFAULT_SWEEP[0]))
    high = float(sweep.get("multiplier_max", DEFAULT_SWEEP[1]))
    steps = int(sweep.get("steps", DEFAULT_SWEEP[2]))
    if steps < 2:
        return [1.0]
    return [low + (high - low) * i / (steps - 1) for i in range(steps)]


def classify_split(
    rows: tuple[Labelled, ...],
    classifier: Any,
    index: SOPIndex,
    scaler: TemperatureScaler,
    batch_size: int = 32,
    *,
    scrub_text: bool = True,
) -> list[Row]:
    """Scrub, classify, roll up and calibrate every test email -- once.

    ``scrub_text=False`` classifies the raw email instead, for the scrub ablation.
    It exists only for that measurement: the runtime always scrubs, because the
    scrub gates every external call.
    """
    scrubber = Scrubber()
    bucket_of = dict(index.bucket)
    out: list[Row] = []

    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        scrubbed = [
            scrubber.scrub(item.email.text) if scrub_text
            else ScrubResult(text=item.email.text)
            for item in chunk
        ]
        predictions = classifier.predict_batch([s.text for s in scrubbed])

        for item, scrub, classification in zip(chunk, scrubbed, predictions, strict=True):
            bucket, summed = rollup(classification, bucket_of)
            score = calibrate(bucket, summed, scaler)
            out.append(Row(
                item=item,
                scrubbed=scrub.text,
                predicted=classification.label,
                probabilities=dict(classification.probabilities),
                bucket=bucket,
                summed=summed,
                raw_confidence=score.raw,
                calibrated_confidence=score.confidence,
                flags=detect_flags(scrub.text, classification),
                true_bucket=Bucket(
                    bucket_of.get(item.label, Bucket.NO_SUPPORTING_SOP.value)
                ),
            ))

        print(f"  classified {min(start + batch_size, len(rows))}/{len(rows)}", end="\r")

    print()
    return out


def route_at(
    rows: list[Row],
    index: SOPIndex,
    thresholds: dict[str, float],
    multiplier: float,
    calibrated: bool,
) -> list[tuple[Row, Any]]:
    """Re-route every row at one threshold multiplier, using the real router."""
    from triage.schemas import BucketScore

    results: list[tuple[Row, Any]] = []
    for row in rows:
        sops = index.sops_for(row.predicted)
        score = BucketScore(
            bucket=row.bucket,
            raw=row.raw_confidence,
            calibrated=row.calibrated_confidence if calibrated else None,
        )
        results.append((row, route(
            score, sops, row.flags, thresholds,
            calibrated=calibrated, multiplier=multiplier,
        )))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="test", help="which split to report on")
    parser.add_argument("--limit", type=int, default=None, help="truncate for a smoke run")
    parser.add_argument("--no-draft", action="store_true", help="skip drafting and the judge")
    parser.add_argument("--draft-sample", type=int, default=50, help="drafts to generate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args()

    started = time.time()
    args.out.mkdir(parents=True, exist_ok=True)

    import yaml

    from triage.models.encoder import EncoderClassifier

    config = yaml.safe_load((ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
    thresholds = load_thresholds()
    scaler = TemperatureScaler.load()
    index = build_index()
    classifier = EncoderClassifier()

    rows_in = split(args.split)
    if args.limit:
        rows_in = rows_in[: args.limit]
    if not rows_in:
        print(f"no rows in split {args.split!r}", file=sys.stderr)
        return 1

    if not scaler.fitted:
        print(
            "WARNING: calibration is NOT fitted -- these numbers must not be reported.\n"
            "         Run the training notebook: "
            "models/01_dataset_eda_and_training.ipynb\n",
            file=sys.stderr,
        )

    print(f"evaluating {len(rows_in)} emails from split {args.split!r}")
    rows = classify_split(rows_in, classifier, index, scaler)

    # ---- classification ---------------------------------------------------
    report_class = classification_report(
        [r.item.label for r in rows],
        [r.predicted for r in rows],
        labels=tuple(classifier.labels),
    )
    report_bucket = classification_report(
        [r.true_bucket.value for r in rows],
        [r.bucket.value for r in rows],
        labels=tuple(b.value for b in Bucket),
    )

    # ---- calibration ------------------------------------------------------
    bucket_correct = [r.bucket is r.true_bucket for r in rows]
    report_calib = calibration_report(
        [r.raw_confidence for r in rows],
        [r.calibrated_confidence for r in rows],
        bucket_correct,
        scaler.temperature,
    )

    # ---- risk-coverage: sweep the real router -----------------------------
    multipliers = sweep_multipliers(config)
    outcomes: dict[float, list[Outcome]] = {}
    for multiplier in multipliers:
        routed = route_at(rows, index, thresholds, multiplier, scaler.fitted)
        outcomes[multiplier] = [
            Outcome(
                label=row.item.label,
                automated=decision.is_automated,
                correct=row.predicted == row.item.label,
            )
            for row, decision in routed
        ]
    report_rc = risk_coverage_report(outcomes)

    # ---- escalation quality, at the operating point (multiplier 1.0) ------
    operating = route_at(rows, index, thresholds, 1.0, scaler.fitted)
    bucket_of = dict(index.bucket)
    report_esc = escalation_report(
        expected=[
            expected_reason(
                row.item.label, bucket_of,
                computation_requested=row.item.computation_requested,
            )
            for row, _ in operating
        ],
        actual=[decision.reason for _, decision in operating],
        automated=[decision.is_automated for _, decision in operating],
    )

    # ---- flags ------------------------------------------------------------
    # The two misfile guards are scored against the TRUE CLASS rather than a
    # planted spec field: their job is to notice that an email belongs to a class
    # the classifier did not pick, so the ground truth is simply "was it that
    # class?". A false positive costs coverage; a false negative auto-answers a
    # foreign-income question or redirects a fraud victim.
    report_flags = {
        "computation_requested": binary_report(
            [r.item.computation_requested for r in rows],
            [Flag.COMPUTATION_REQUESTED in r.flags for r in rows],
        ),
        "account_specific_signal": binary_report(
            [r.item.account_specific for r in rows],
            [Flag.ACCOUNT_SPECIFIC_SIGNAL in r.flags for r in rows],
        ),
        "foreign_income_signal": binary_report(
            [r.item.label == "foreign_income_dta" for r in rows],
            [Flag.FOREIGN_INCOME_SIGNAL in r.flags for r in rows],
        ),
        "scam_signal": binary_report(
            [r.item.label == "scam_report" for r in rows],
            [Flag.SCAM_SIGNAL in r.flags for r in rows],
        ),
    }

    # ---- scrub recall -----------------------------------------------------
    report_scrub = scrub_report(
        [(r.item.id, r.item.plant_pii, r.scrubbed) for r in rows if r.item.plant_pii]
    )

    # ---- drafting ---------------------------------------------------------
    report_draft: dict[str, Any] = {"skipped": True}
    if not args.no_draft:
        from eval.drafting import run_draft_sample

        report_draft = run_draft_sample(
            [(row, decision) for row, decision in operating if decision.is_automated],
            index=index,
            sample_size=args.draft_sample,
            seed=args.seed,
            out_dir=args.out,
        )

    # ---- write ------------------------------------------------------------
    summary = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": args.split,
        "n": len(rows),
        "seed": args.seed,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "models": {
            "classifier": classifier.name,
            "calibration": {
                "fitted": scaler.fitted,
                "temperature": round(scaler.temperature, 4),
                "n_calibration_examples": scaler.n_examples,
            },
        },
        "thresholds": thresholds,
        "calibrated_numbers_reportable": scaler.fitted,
        "headline": {
            "macro_f1_class": round(report_class.macro_f1, 4),
            "macro_f1_bucket": round(report_bucket.macro_f1, 4),
            "ece_before": round(report_calib.ece_before, 4),
            "ece_after": round(report_calib.ece_after, 4),
            "aurc_overall": round(report_rc.aurc_overall, 4),
            "must_escalate_recall": round(report_esc.must_escalate_recall, 4),
            "unsafe_automations": report_esc.unsafe_automations,
            "scrub_recall": round(report_scrub.recall, 4),
        },
        "elapsed_seconds": round(time.time() - started, 1),
    }

    written = {
        "summary.json": summary,
        "classification.json": report_class.as_dict(),
        "classification_buckets.json": report_bucket.as_dict(),
        "calibration.json": report_calib.as_dict(),
        "risk_coverage.json": report_rc.as_dict(),
        "escalation.json": report_esc.as_dict(),
        "flags.json": report_flags,
        "scrub_recall.json": report_scrub.as_dict(),
        "drafting.json": report_draft,
    }
    for name, payload in written.items():
        (args.out / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    plot_reliability(report_calib, args.out / "reliability.png")
    plot_risk_coverage(report_rc, args.out / "risk_coverage.png")

    # ---- console ----------------------------------------------------------
    print(f"\n{'=' * 66}\nRESULTS — split={args.split}  n={len(rows)}\n{'=' * 66}")
    print(f"  macro-F1 (12 classes)       {report_class.macro_f1:.4f}")
    print(f"  macro-F1 (5 buckets)        {report_bucket.macro_f1:.4f}")
    print(f"  bucket accuracy             {report_bucket.accuracy:.4f}")
    if worst := report_class.worst:
        print(f"  weakest class               {worst.label} (F1 {worst.f1:.3f}, n={worst.support})")
    print(f"\n  ECE before                  {report_calib.ece_before:.4f}")
    print(f"  ECE after   (T={scaler.temperature:.3f})     {report_calib.ece_after:.4f}"
          f"   [{report_calib.improvement:+.4f}]")
    print(f"\n  AURC (overall)              {report_rc.aurc_overall:.4f}")
    for target in (0.05, 0.10, 0.20):
        point = report_rc.operating_point(target)
        if point:
            print(f"    risk <= {target:.0%}  ->  coverage {point.coverage:.1%}"
                  f"   (multiplier {point.multiplier:.2f})")
    print(f"\n  must-escalate recall        {report_esc.must_escalate_recall:.4f}"
          f"   (n={report_esc.must_escalate_support})")
    print(f"  unsafe automations          {report_esc.unsafe_automations}")
    print(f"  false escalations           {report_esc.false_escalations}")
    print()
    for name, stats in report_flags.items():
        print(f"  flag {name:24s}P/R  {stats['precision']:.3f} / {stats['recall']:.3f}")
    print(f"\n  scrub recall                {report_scrub.recall:.4f}"
          f"   ({report_scrub.overall_detected}/{report_scrub.overall_planted} planted values)")
    if not report_draft.get("skipped"):
        print(f"  drafting availability       {report_draft.get('availability', 0):.4f}"
              f"   ({report_draft.get('n_ok', 0)}/{report_draft.get('n_attempted', 0)})")
    if not scaler.fitted:
        print("\n  *** UNFITTED CALIBRATION — these numbers must not be reported ***")
    print(f"\nwrote {len(written)} files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
