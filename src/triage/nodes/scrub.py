"""Scrub node -- the gate every external call passes through.

RUNTIME. First node in the graph, deliberately: it runs before the classifier and
before any LLM call, so no node downstream of it ever sees a real identifier.

The node is a thin wrapper over :class:`triage.pii.scrubber.Scrubber`. The logic
lives there because it is also exercised by the scrub-recall metric and by the
scrub ablation, neither of which builds a graph.

**Failing open is the wrong default here.** If scrubbing raises, the state records
the error and carries the *unscrubbed* text nowhere: ``scrub`` stays ``None``, which
``TriageState.redacted`` reads as "never scrubbed" and blanks the body entirely
rather than assuming it was clean. The item then escalates, because a state with no
classification cannot route.
"""

from __future__ import annotations

from functools import lru_cache

from triage.pii.scrubber import Scrubber
from triage.schemas import ScrubRecord, TriageState


@lru_cache(maxsize=1)
def _scrubber() -> Scrubber:
    """One shared scrubber. Compiling the pattern set per email is pure waste, and
    the object is stateless across calls -- each scrub returns its own vault."""
    return Scrubber()


def scrub_node(state: TriageState) -> dict[str, object]:
    """Replace PII with placeholders before anything else touches the text."""
    try:
        result = _scrubber().scrub(state.email.text)
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        return {"errors": [*state.errors, f"scrub failed: {exc}"]}

    return {
        "scrub": ScrubRecord(text=result.text, vault=result.vault, counts=result.counts),
    }


__all__ = ["scrub_node"]
