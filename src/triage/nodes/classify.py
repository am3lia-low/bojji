"""Classify node -- email text to a distribution over the taxonomy's classes.

RUNTIME.

The node holds no model logic. It calls whatever satisfies the
:class:`triage.models.base.Classifier` Protocol, which is what lets the ablation
harness swap the fine-tuned encoder for the LLM zero-shot baseline without
special-casing anything here (``BUILD.md`` S5.4).

**It classifies the scrubbed text, not the original.** Two reasons, and the second
is the load-bearing one: the classifier must see exactly what an external call
would see, so a flag or a prediction can never depend on a value the rest of the
pipeline never had. Falling back to raw text when scrubbing failed would break that
invariant silently, so a missing scrub record is an error rather than a fallback.
"""

from __future__ import annotations

from triage.models.base import Classifier
from triage.schemas import TriageState


def classify_node(state: TriageState, classifier: Classifier) -> dict[str, object]:
    """Run the classifier over the scrubbed email."""
    if state.scrub is None:
        return {"errors": [*state.errors, "classify skipped: no scrubbed text"]}

    try:
        classification = classifier.predict(state.scrub.text)
    except Exception as exc:  # noqa: BLE001 -- an unclassified item escalates
        return {"errors": [*state.errors, f"classify failed: {exc}"]}

    return {"classification": classification}


__all__ = ["classify_node"]
