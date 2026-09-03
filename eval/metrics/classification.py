"""Classification metrics -- macro-F1 and the per-class breakdown.

EVAL-TIME.

**Macro-averaged, not micro.** The corpus is balanced by construction, so the two
would nearly agree here; macro is still the right choice because it is the one that
stays honest if the balance ever changes, and because every class is reported
individually anyway. A per-class table is the actual deliverable -- a single F1
would let strong performance on ``filing`` mask a collapse on ``hardship_or_waiver``,
which is exactly the failure the escalation design exists to prevent.

Implemented here rather than imported from scikit-learn so that the confusion
matrix, the per-class table and the macro figure are computed from one pass over
one set of counts, and the numbers in the README cannot disagree with each other.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClassMetrics:
    """Precision, recall and F1 for one class, with its support."""

    label: str
    precision: float
    recall: float
    f1: float
    support: int

    def as_dict(self) -> dict[str, float | str | int]:
        return {
            "label": self.label,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "support": self.support,
        }


@dataclass(frozen=True)
class ClassificationReport:
    """The full picture: per class, the macro figures, and the confusion matrix."""

    per_class: tuple[ClassMetrics, ...]
    accuracy: float
    macro_f1: float
    macro_precision: float
    macro_recall: float
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    n: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "macro_precision": round(self.macro_precision, 4),
            "macro_recall": round(self.macro_recall, 4),
            "per_class": [m.as_dict() for m in self.per_class],
            "confusion": self.confusion,
        }

    @property
    def worst(self) -> ClassMetrics | None:
        """The weakest class by F1 -- what a reader should look at first."""
        return min(self.per_class, key=lambda m: m.f1) if self.per_class else None


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def classification_report(
    truth: list[str], predicted: list[str], labels: tuple[str, ...] | None = None
) -> ClassificationReport:
    """Compute per-class and macro metrics from aligned label sequences.

    A class with zero support is still reported, at zero, rather than dropped: a
    silently missing row would read as "not measured" when it means "never
    predicted and never present", and those are different.

    It is excluded from the macro averages, though. A structural zero -- a bucket
    that holds no classes by design -- is a fact about the taxonomy, not a fact
    about the model, and averaging it in understates performance on the classes
    that were actually predicted.
    """
    if len(truth) != len(predicted):
        raise ValueError(f"length mismatch: {len(truth)} truths, {len(predicted)} predictions")

    names = labels if labels is not None else tuple(sorted(set(truth) | set(predicted)))
    true_positive: Counter[str] = Counter()
    false_positive: Counter[str] = Counter()
    false_negative: Counter[str] = Counter()
    confusion: dict[str, dict[str, int]] = {t: dict.fromkeys(names, 0) for t in names}

    for actual, guess in zip(truth, predicted, strict=True):
        if actual in confusion and guess in confusion[actual]:
            confusion[actual][guess] += 1
        if actual == guess:
            true_positive[actual] += 1
        else:
            false_positive[guess] += 1
            false_negative[actual] += 1

    per_class: list[ClassMetrics] = []
    for label in names:
        tp, fp, fn = true_positive[label], false_positive[label], false_negative[label]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class.append(
            ClassMetrics(label, precision, recall, _f1(precision, recall), tp + fn)
        )

    # A class with no support is REPORTED at zero but excluded from the macro
    # average. Averaging it in measures the taxonomy's shape rather than the
    # model's performance: `requires_account_lookup` holds no classes by design --
    # it is reached through the account_specific flag, which the router consults
    # before any confidence -- so it has zero support on every split, and folding a
    # structural zero into the mean drags the score down by a fifth for a bucket
    # nothing was ever asked to predict.
    #
    # The row stays in `per_class` because "never present and never predicted" and
    # "not measured" are different things, and the reader should be able to see
    # which one this is.
    scored = [m for m in per_class if m.support > 0]
    count = len(scored) or 1

    n = len(truth)
    return ClassificationReport(
        per_class=tuple(per_class),
        accuracy=sum(true_positive.values()) / n if n else 0.0,
        macro_f1=sum(m.f1 for m in scored) / count,
        macro_precision=sum(m.precision for m in scored) / count,
        macro_recall=sum(m.recall for m in scored) / count,
        confusion=confusion,
        n=n,
    )


def binary_report(truth: list[bool], predicted: list[bool]) -> dict[str, float | int]:
    """Precision, recall and F1 for a flag.

    Used for ``computation_requested`` and the ``account_specific`` backstop, whose
    ground truth the generator recorded. Reported as precision *and* recall rather
    than accuracy because the two costs are asymmetric: a false positive escalates
    an answerable email and costs coverage, which is recoverable; a false negative
    lets the agent compute a relief amount, which is the failure the design exists
    to prevent (``BUILD.md`` S9.9).
    """
    tp = sum(t and p for t, p in zip(truth, predicted, strict=True))
    fp = sum((not t) and p for t, p in zip(truth, predicted, strict=True))
    fn = sum(t and (not p) for t, p in zip(truth, predicted, strict=True))
    tn = sum((not t) and (not p) for t, p in zip(truth, predicted, strict=True))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(_f1(precision, recall), 4),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "support": tp + fn,
    }


__all__ = ["ClassMetrics", "ClassificationReport", "binary_report", "classification_report"]
