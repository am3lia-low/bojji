"""LangGraph assembly -- the pipeline, wired.

RUNTIME. The one place the node order is stated, and the only module that knows
about all of them.

::

    scrub -> classify -> calibrate -> retrieve -> route -+-> draft    -> END
                                                         |
                                                         +-> declined -> END

LangGraph rather than a plain function chain, for one reason that pays off in this
domain: the execution path is a declared graph rather than an implicit consequence
of control flow, so "what happened to this email" is answerable by reading the
edges. High-stakes auditable workflows favour constrained patterns whose path is
traceable end to end (``BUILD.md`` S3).

**The conditional edge is the escalation gate made structural.** An escalated item
does not reach the drafting node at all -- not by an early return inside the drafter,
which a later edit could remove, but because no edge leads there. The router is the
single place that decision is made.

**Dependencies are injected at build time, not imported by the nodes.** The
classifier, SOP index, temperature and thresholds are bound into the graph by
:func:`build_graph`, so the ablation harness swaps a classifier or a temperature
without touching a node, and tests construct a graph with fakes and no model on
disk. A node that reached for a global would make both impossible.

**State merges rather than replaces.** Each node returns only the fields it sets;
``TriageState`` accumulates them, so a completed state is the full audit record of
one decision -- which is what the demo renders and what every metric reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from langgraph.graph import END, StateGraph

from triage.llm.client import LLMClient, LLMError
from triage.models.base import Classifier
from triage.models.calibration import TemperatureScaler
from triage.nodes.calibrate import calibrate_node
from triage.nodes.classify import classify_node
from triage.nodes.draft import draft_node
from triage.nodes.flags import detect_flags
from triage.nodes.retrieve import retrieve_node
from triage.nodes.route import load_thresholds, route
from triage.nodes.scrub import scrub_node
from triage.schemas import (
    Action,
    Bucket,
    DraftResult,
    DraftStatus,
    EscalationReason,
    RoutingDecision,
    TriageState,
)
from triage.sop.index import SOPIndex, build_index

#: Confidence recorded when the pipeline could not produce one. The item escalates,
#: so the value is never compared against a threshold; 0.0 is the honest record of
#: "no confidence was obtained" rather than a score that might be read as measured.
_NO_CONFIDENCE: Final[float] = 0.0


@dataclass(frozen=True)
class GraphDeps:
    """Everything the nodes need, resolved once at startup.

    Assembled here rather than loaded per email: the SOP corpus is parsed and
    validated once, the classifier holds its weights, and the thresholds are read
    from config. A per-email reload would put a file-system error on the path of a
    citizen's enquiry.
    """

    classifier: Classifier
    index: SOPIndex
    scaler: TemperatureScaler
    thresholds: Mapping[str, float]
    client: LLMClient | None = None
    multiplier: float = 1.0

    @property
    def bucket_of(self) -> Mapping[str, str]:
        """class -> bucket, derived from SOP frontmatter."""
        return self.index.bucket


def _route_node(state: TriageState, deps: GraphDeps) -> dict[str, Any]:
    """Detect flags and make the escalation decision.

    Flag detection sits here rather than in its own node because it is an input to
    exactly one decision and has no other consumer -- a separate node would add a
    graph edge that never branches.

    An item that reached this point without a bucket score never got a usable
    prediction. It escalates as ``no_supporting_sop``: the pipeline has no grounds
    to act, and failing toward the officer is the only safe direction.
    """
    if state.bucket_score is None:
        return {
            "decision": RoutingDecision(
                action=Action.ESCALATE,
                bucket=Bucket.NO_SUPPORTING_SOP,
                confidence=_NO_CONFIDENCE,
                reason=EscalationReason.NO_SUPPORTING_SOP,
                calibrated=deps.scaler.fitted,
            ),
            "errors": [*state.errors, "routed without a prediction: escalating"],
        }

    text = state.scrub.text if state.scrub else state.email.text
    flags = detect_flags(text, state.classification)
    sops = tuple(deps.index.by_id[sid] for sid in state.sop_ids if sid in deps.index.by_id)

    decision = route(
        state.bucket_score,
        sops,
        flags,
        dict(deps.thresholds),
        calibrated=deps.scaler.fitted,
        multiplier=deps.multiplier,
    )
    return {"decision": decision}


def _should_draft(state: TriageState) -> str:
    """The conditional edge: only an item the router acted on reaches the drafter."""
    return "draft" if state.auto_reply_intended else "declined"


def _not_attempted(state: TriageState) -> dict[str, Any]:
    """Record that drafting was declined rather than skipped.

    An escalated item never reaches the drafting node -- that is the escalation gate
    being structural rather than a branch inside the drafter. But its ``draft``
    field must still be populated, because ``None`` is ambiguous: it reads equally
    as "the router declined" and as "the run stopped early". ``NOT_ATTEMPTED`` says
    which, so drafting availability counts only items drafting was actually asked
    for (``BUILD.md`` S5.8).
    """
    return {"draft": DraftResult(status=DraftStatus.NOT_ATTEMPTED, sop_ids=state.sop_ids)}


def build_graph(deps: GraphDeps) -> Any:
    """Compile the triage graph.

    Nodes are bound to ``deps`` here, so each remains ``pure(state) -> partial
    state`` and stays independently testable without a graph.
    """
    builder: StateGraph[TriageState, None, TriageState, TriageState] = StateGraph(
        TriageState
    )

    builder.add_node("scrub", scrub_node)
    builder.add_node("classify", lambda s: classify_node(s, deps.classifier))
    builder.add_node("calibrate", lambda s: calibrate_node(s, deps.bucket_of, deps.scaler))
    builder.add_node("retrieve", lambda s: retrieve_node(s, deps.index))
    builder.add_node("route", lambda s: _route_node(s, deps))
    builder.add_node("draft", lambda s: draft_node(s, deps.index, deps.client))
    builder.add_node("declined", _not_attempted)

    builder.set_entry_point("scrub")
    builder.add_edge("scrub", "classify")
    builder.add_edge("classify", "calibrate")
    builder.add_edge("calibrate", "retrieve")
    builder.add_edge("retrieve", "route")
    builder.add_conditional_edges(
        "route", _should_draft, {"draft": "draft", "declined": "declined"}
    )
    builder.add_edge("draft", END)
    builder.add_edge("declined", END)

    return builder.compile()


def build_default_deps(
    *,
    classifier: Classifier | None = None,
    drafting: bool = True,
    multiplier: float = 1.0,
) -> GraphDeps:
    """Assemble dependencies from what is on disk.

    Args:
        classifier: Overrides the fine-tuned encoder, for ablations and tests.
        drafting: When False, no LLM client is constructed. Every auto-reply then
            records a drafting failure, which is the correct behaviour for a
            routing-only eval sweep: the routing decision is unaffected, and
            drafting availability reports the absence honestly.
        multiplier: Scales every threshold. Swept to trace the risk-coverage curve.

    A missing ``GEMINI_API_KEY`` is not fatal. The item escalates to the officer
    carrying its SOP, exactly as a rate limit would -- the designed failure path
    rather than a special case (``BUILD.md`` S5.8).
    """
    if classifier is None:
        from triage.models.encoder import EncoderClassifier

        classifier = EncoderClassifier()

    client: LLMClient | None = None
    if drafting:
        from triage.llm.client import GeminiClient

        try:
            client = GeminiClient()
        except LLMError:
            client = None

    return GraphDeps(
        classifier=classifier,
        index=build_index(),
        scaler=TemperatureScaler.load(),
        thresholds=load_thresholds(),
        client=client,
        multiplier=multiplier,
    )


def run_one(graph: Any, state: TriageState) -> TriageState:
    """Run one email through a compiled graph and return the completed state.

    LangGraph returns the accumulated state as a mapping; it is validated back into
    a :class:`TriageState` so callers always receive the typed object.
    """
    result = graph.invoke(state)
    return result if isinstance(result, TriageState) else TriageState.model_validate(result)


__all__ = ["GraphDeps", "build_default_deps", "build_graph", "run_one"]
