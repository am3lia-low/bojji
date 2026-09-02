"""Assign train / calibration / test splits, stratified by class and seeded.

BUILD-TIME ONLY. The split is committed so every downstream number is reproducible
without re-running generation.

**Why three splits rather than two.** Temperature scaling is *fitted* on the
calibration split and *reported* on the test split. Fitting and reporting on the
same data would make the headline calibration result meaningless -- a temperature
chosen to minimise error on a set will always look good on that set. The split
is what keeps the contribution honest (``BUILD.md`` S5.5).

**Grouped by scenario, not by email.** Every variant of one scenario shares a
situation, so variants of the same scenario are near-neighbours by construction.
Splitting them at random would put near-duplicates on both sides of the train/test
boundary and inflate the test score. All variants of a scenario therefore land in
the same split, which is a stricter and more honest test: the model is asked to
generalise to situations it has never seen, not to paraphrases it has.

That grouping is why the proportions land near, rather than exactly on, 50/20/30.

Usage:
    python scripts/make_splits.py
    python scripts/make_splits.py --check     # verify the committed split
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
EMAILS: Final[Path] = ROOT / "data" / "generated" / "emails.jsonl"
SPLIT_PATH: Final[Path] = ROOT / "data" / "splits" / "splits.json"

SEED: Final[int] = 42
TARGET: Final[dict[str, float]] = {"train": 0.5, "calibration": 0.2, "test": 0.3}


def load_rows() -> list[dict[str, Any]]:
    if not EMAILS.exists():
        raise SystemExit(
            f"{EMAILS.relative_to(ROOT)} not found.\n"
            "Run: python scripts/generate_emails.py"
        )
    return [json.loads(line) for line in EMAILS.read_text(encoding="utf-8").splitlines()]


def assign(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Return ``{email_id: split}``, grouping scenarios and stratifying by class."""
    rng = random.Random(SEED)

    # scenario -> its emails, and scenario -> its class
    by_scenario: dict[str, list[str]] = defaultdict(list)
    scenario_label: dict[str, str] = {}
    for row in rows:
        scenario = str(row["scenario_id"])
        by_scenario[scenario].append(str(row["id"]))
        scenario_label[scenario] = str(row["label"])

    # Stratify within each class, so a class cannot be starved in any split.
    scenarios_by_label: dict[str, list[str]] = defaultdict(list)
    for scenario, label in scenario_label.items():
        scenarios_by_label[label].append(scenario)

    assignment: dict[str, str] = {}
    for label in sorted(scenarios_by_label):
        scenarios = sorted(scenarios_by_label[label])
        rng.shuffle(scenarios)

        total = sum(len(by_scenario[s]) for s in scenarios)
        quota = {name: total * share for name, share in TARGET.items()}
        placed = dict.fromkeys(TARGET, 0)

        # Largest scenarios first: greedily give each to whichever split is
        # furthest below its quota. Placing big groups first keeps the final
        # proportions close to target despite indivisible groups.
        for scenario in sorted(scenarios, key=lambda s: -len(by_scenario[s])):
            split = max(TARGET, key=lambda name: quota[name] - placed[name])
            for email_id in by_scenario[scenario]:
                assignment[email_id] = split
            placed[split] += len(by_scenario[scenario])

    return assignment


def summarise(rows: list[dict[str, Any]], assignment: dict[str, str]) -> None:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[str(row["label"])][assignment[str(row["id"])]] += 1

    total = Counter(assignment.values())
    n = len(rows)
    print(f"\n{'class':28}{'train':>8}{'calib':>8}{'test':>8}")
    for label in sorted(counts):
        row_counts = counts[label]
        print(f"{label:28}{row_counts['train']:>8}{row_counts['calibration']:>8}"
              f"{row_counts['test']:>8}")
    print(f"{'TOTAL':28}{total['train']:>8}{total['calibration']:>8}{total['test']:>8}")
    print(f"{'share':28}{total['train']/n:>8.1%}{total['calibration']/n:>8.1%}"
          f"{total['test']/n:>8.1%}")

    test_per_class = [c["test"] for c in counts.values()]
    calib_total = total["calibration"]
    print(f"\ntest examples per class:      min {min(test_per_class)}, "
          f"max {max(test_per_class)}")
    print(f"calibration per bucket (~5):  ~{calib_total // 5}")

    if min(test_per_class) < 30:
        print("\nWARNING: a class has fewer than 30 test examples; per-class "
              "metrics will be noisy.")


def check_no_scenario_spans_splits(rows: list[dict[str, Any]], assignment: dict[str, str]) -> None:
    """A scenario in two splits would put near-duplicates across the boundary."""
    seen: dict[str, str] = {}
    for row in rows:
        scenario, split = str(row["scenario_id"]), assignment[str(row["id"])]
        if scenario in seen and seen[scenario] != split:
            raise SystemExit(f"scenario {scenario} spans {seen[scenario]} and {split}")
        seen[scenario] = split
    print(f"\nno scenario spans a split boundary ({len(seen)} scenarios)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the committed split")
    args = parser.parse_args()

    rows = load_rows()
    print(f"{len(rows)} emails, {len({r['scenario_id'] for r in rows})} scenarios")

    if args.check:
        if not SPLIT_PATH.exists():
            print(f"MISSING: {SPLIT_PATH.relative_to(ROOT)}")
            return 1
        stored = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))["assignment"]
        if stored != assign(rows):
            print("STALE: the committed split does not match a fresh seeded run.")
            return 1
        summarise(rows, stored)
        check_no_scenario_spans_splits(rows, stored)
        print(f"\n{SPLIT_PATH.relative_to(ROOT)} is current")
        return 0

    assignment = assign(rows)
    summarise(rows, assignment)
    check_no_scenario_spans_splits(rows, assignment)

    SPLIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_PATH.write_text(json.dumps({
        "seed": SEED,
        "target": TARGET,
        "grouped_by": "scenario_id",
        "note": ("All variants of a scenario share a split, so near-duplicates "
                 "cannot span the train/test boundary."),
        "assignment": assignment,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {SPLIT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
