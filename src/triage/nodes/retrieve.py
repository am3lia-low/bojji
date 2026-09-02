"""Retrieve node -- class to SOPs, by dictionary lookup.

RUNTIME. No search, no embeddings, no index (``sop_design.md`` S6).

"Retrieval" here is ``CLASS_TO_SOPS[class]``, a map built at startup by inverting
the ``intents:`` line each indexed SOP declares. At 17 documents and ~100KB there
is nothing a vector store would buy, and a similarity search sitting immediately
upstream of the escalation decision would add a failure mode to the one path in the
system that must not have one.

**An empty result is a signal, not an error.** Two classes -- ``rental_income`` and
``foreign_income_dta`` -- have no indexed SOP on purpose, so the lookup comes back
empty and the router escalates ``no_supporting_sop`` by derivation. That is the
holdout doing its job: unanswerable is a behaviour the eval tests, and it is
produced by omitting a file rather than by a hand-written rule that could drift out
of step with the corpus (``BUILD.md`` S5.6).

The whole group goes forward, not a pre-selected member. *"Can I claim for my child
and my mother?"* needs REL-001 and REL-002, so a pre-selection step would have to
choose one and would get that email wrong. Which SOPs the draft actually cites is
recorded and measured instead (S9.2).
"""

from __future__ import annotations

from triage.schemas import TriageState
from triage.sop.index import SOPIndex
from triage.sop.loader import SOP


def retrieve(index: SOPIndex, label: str) -> tuple[SOP, ...]:
    """Return every indexed SOP serving ``label``. Empty means unanswerable."""
    return index.sops_for(label)


def retrieve_node(state: TriageState, index: SOPIndex) -> dict[str, object]:
    """Look up the SOP group for the predicted class."""
    if state.classification is None:
        return {"errors": [*state.errors, "retrieve skipped: no classification"]}

    sops = retrieve(index, state.classification.label)
    return {"sop_ids": tuple(sop.sop_id for sop in sops)}


__all__ = ["retrieve", "retrieve_node"]
