"""Ablations -- what each design decision actually buys.

EVAL-TIME. Writes ``eval/results/ablations.json``.

Run::

    python eval/ablations/run_ablations.py

Three ablations are computed here. Each isolates one decision the design took, and
each is cheap because it reuses one classification pass -- the model runs once, and
the variants differ only in what is done with its output.

**Calibrated vs uncalibrated confidence.** The contribution. Does temperature
scaling move the risk-coverage curve, or only the ECE number? Both are reported,
because they answer different questions: ECE says the confidence is more honest,
AURC says whether that honesty changes any decision.

**Per-bucket vs a single global threshold.** The design argues thresholds belong at
bucket level because a bucket carries ~108 test examples against ~45 for a class.
This measures whether the per-bucket policy actually beats one number applied
everywhere, rather than asserting it.

**Scrubbed vs unscrubbed input.** Does removing PII cost classification accuracy?
The scrub is non-negotiable on privacy grounds, so this is not a decision under
review -- it quantifies a cost already accepted, which is the honest way to report
a constraint.

The multi-SOP grounding ablation (S6.5) is NOT here: it needs live drafting, so it
belongs with the drafting sample in ``eval/drafting.py`` rather than in this
offline pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from triage.env import load_env  # noqa: E402

load_env()

from eval.dataset import split  # noqa: E402
from eval.metrics.calibration import calibration_report  # noqa: E402
from eval.metrics.classification import classification_report  # noqa: E402
from eval.metrics.risk_coverage import Outcome, risk_coverage_report  # noqa: E402
from eval.run_eval import classify_split, route_at, sweep_multipliers  # noqa: E402

from triage.models.calibration import TemperatureScaler  # noqa: E402
from triage.nodes.route import load_thresholds  # noqa: E402
from triage.sop.index import build_index  # noqa: E402


def _curve(rows: list[Any], index: Any, thresholds: dict[str, float],
           multipliers: list[float], calibrated: bool) -> Any:
    """Sweep the real router and build the curve."""
    outcomes: dict[float, list[Outcome]] = {}
    for multiplier in multipliers:
        outcomes[multiplier] = [
            Outcome(
                label=row.item.label,
                automated=decision.is_automated,
                correct=row.predicted == row.item.label,
            )
            for row, decision in route_at(rows, index, thresholds, multiplier, calibrated)
        ]
    return risk_coverage_report(outcomes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results" / "ablations.json")
    args = parser.parse_args()

    import yaml

    from triage.models.encoder import EncoderClassifier

    config = yaml.safe_load((ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
    multipliers = sweep_multipliers(config)
    thresholds = load_thresholds()
    scaler = TemperatureScaler.load()
    index = build_index()
    classifier = EncoderClassifier()

    rows_in = split(args.split)
    if args.limit:
        rows_in = rows_in[: args.limit]
    print(f"ablations over {len(rows_in)} emails from {args.split!r}")

    rows = classify_split(rows_in, classifier, index, scaler)
    bucket_correct = [r.bucket is r.true_bucket for r in rows]

    # ---- 1. calibration ---------------------------------------------------
    calib = calibration_report(
        [r.raw_confidence for r in rows],
        [r.calibrated_confidence for r in rows],
        bucket_correct,
        scaler.temperature,
    )
    curve_raw = _curve(rows, index, thresholds, multipliers, calibrated=False)
    curve_cal = _curve(rows, index, thresholds, multipliers, calibrated=True)

    # ---- 2. per-bucket vs one global threshold ----------------------------
    # The global variant applies auto_answerable's threshold everywhere. The three
    # always-escalate buckets are unaffected -- the router never consults their
    # number -- so this isolates exactly the out_of_scope difference.
    global_value = thresholds.get("auto_answerable", 0.5)
    global_thresholds = dict.fromkeys(thresholds, global_value)
    curve_global = _curve(rows, index, global_thresholds, multipliers, calibrated=scaler.fitted)

    # ---- 3. scrubbed vs unscrubbed ---------------------------------------
    unscrubbed = classify_split(
        rows_in, classifier, index, scaler, scrub_text=False,
    )
    report_scrubbed = classification_report(
        [r.item.label for r in rows], [r.predicted for r in rows],
        labels=tuple(classifier.labels),
    )
    report_unscrubbed = classification_report(
        [r.item.label for r in unscrubbed], [r.predicted for r in unscrubbed],
        labels=tuple(classifier.labels),
    )

    payload: dict[str, Any] = {
        "split": args.split,
        "n": len(rows),
        "calibration": {
            "question": "Does temperature scaling change any decision, or only the ECE?",
            "temperature": round(scaler.temperature, 4),
            "ece_before": round(calib.ece_before, 4),
            "ece_after": round(calib.ece_after, 4),
            "aurc_uncalibrated": round(curve_raw.aurc_overall, 4),
            "aurc_calibrated": round(curve_cal.aurc_overall, 4),
            "note": (
                "ECE says the confidence is more honest; AURC says whether that "
                "honesty changes a routing decision. They can move independently."
            ),
        },
        "thresholds": {
            "question": "Do per-bucket thresholds beat one global number?",
            "aurc_per_bucket": round(curve_cal.aurc_overall, 4),
            "aurc_global": round(curve_global.aurc_overall, 4),
            "global_value_used": global_value,
            "note": (
                "Only auto_answerable and out_of_scope have a threshold that bites, "
                "so this isolates the out_of_scope difference."
            ),
        },
        "scrub": {
            "question": "Does removing PII cost classification accuracy?",
            "macro_f1_scrubbed": round(report_scrubbed.macro_f1, 4),
            "macro_f1_unscrubbed": round(report_unscrubbed.macro_f1, 4),
            "delta": round(report_unscrubbed.macro_f1 - report_scrubbed.macro_f1, 4),
            "note": (
                "Not a decision under review -- the scrub is non-negotiable on privacy "
                "grounds. This quantifies a cost already accepted."
            ),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{'=' * 62}\nABLATIONS — n={len(rows)}\n{'=' * 62}")
    print(f"  calibration   ECE  {calib.ece_before:.4f} -> {calib.ece_after:.4f}")
    print(f"                AURC {curve_raw.aurc_overall:.4f} -> {curve_cal.aurc_overall:.4f}")
    print(f"  thresholds    AURC per-bucket {curve_cal.aurc_overall:.4f}"
          f"  vs global {curve_global.aurc_overall:.4f}")
    print(f"  scrub         macro-F1 {report_scrubbed.macro_f1:.4f}"
          f"  vs unscrubbed {report_unscrubbed.macro_f1:.4f}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
