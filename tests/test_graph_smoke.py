"""End-to-end graph tests, with a stub classifier and no network.

These exist to test the WIRING, not the model: that the nodes run in the declared
order, that state accumulates, that the conditional edge sends escalated items past
the drafter, and that every class in the corpus routes to the bucket its frontmatter
declares. A stub classifier makes each of those deterministic and keeps the suite
runnable with no weights on disk.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from triage.graph import GraphDeps, build_graph, run_one
from triage.models.calibration import TemperatureScaler
from triage.nodes.route import load_thresholds
from triage.schemas import (
    Action,
    Bucket,
    Classification,
    DraftStatus,
    Email,
    EscalationReason,
    TriageState,
)
from triage.sop.index import build_index


@pytest.fixture(scope="module")
def index():
    return build_index()


@pytest.fixture(scope="module")
def labels(index):
    return tuple(sorted({intent for sop in index.sops for intent in sop.intents}))


class StubClassifier:
    """Returns a fixed label with near-all the probability mass on it."""

    def __init__(self, label: str, labels: tuple[str, ...], confidence: float = 0.9) -> None:
        self._label = label
        self._labels = labels if label in labels else (*labels, label)
        self._confidence = confidence

    @property
    def name(self) -> str:
        return "stub"

    @property
    def labels(self) -> tuple[str, ...]:
        return self._labels

    def predict(self, text: str) -> Classification:
        spare = (1.0 - self._confidence) / max(len(self._labels) - 1, 1)
        scores = dict.fromkeys(self._labels, spare)
        scores[self._label] = self._confidence
        return Classification(label=self._label, probabilities=scores, model_name="stub")

    def predict_batch(self, texts: list[str]) -> list[Classification]:
        return [self.predict(t) for t in texts]


def make_email(body: str = "How do I file my tax return?", subject: str = "Filing") -> Email:
    return Email(
        id="test-1",
        received_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        subject=subject,
        body=body,
    )


def make_deps(index, labels, label: str, confidence: float = 0.9, **kwargs) -> GraphDeps:
    return GraphDeps(
        classifier=StubClassifier(label, labels, confidence),
        index=index,
        scaler=TemperatureScaler.load(),
        thresholds=load_thresholds(),
        client=None,
        **kwargs,
    )


def run(index, labels, label: str, email: Email | None = None, **kwargs) -> TriageState:
    deps = make_deps(index, labels, label, **kwargs)
    return run_one(build_graph(deps), TriageState(email=email or make_email()))


# --------------------------------------------------------------------------- #
# The pipeline runs, and every node contributes
# --------------------------------------------------------------------------- #


def test_every_node_populates_its_field(index, labels):
    state = run(index, labels, "filing")

    assert state.scrub is not None, "scrub node did not run"
    assert state.classification is not None, "classify node did not run"
    assert state.bucket_score is not None, "calibrate node did not run"
    assert state.decision is not None, "route node did not run"
    assert state.draft is not None, "neither draft nor declined node ran"


def test_state_accumulates_rather_than_replaces(index, labels):
    """A completed state is the audit record, so nothing an earlier node wrote is lost."""
    state = run(index, labels, "filing")

    assert state.email.id == "test-1"
    assert state.classification.label == "filing"
    assert state.bucket_score.bucket is Bucket.AUTO_ANSWERABLE
    assert state.sop_ids


# --------------------------------------------------------------------------- #
# The corpus decides routing, and every class agrees with its frontmatter
# --------------------------------------------------------------------------- #


def test_every_class_routes_to_its_declared_bucket(index, labels):
    for label in labels:
        state = run(index, labels, label)
        expected = Bucket(index.bucket_for(label))
        assert state.decision.bucket is expected, (
            f"{label} routed to {state.decision.bucket} not {expected}"
        )


def test_held_out_classes_escalate_as_unanswerable(index, labels):
    """The holdout is a matter of omitting a file, and must derive from an empty lookup."""
    unanswerable = index.unanswerable(labels)
    assert unanswerable, "expected at least one class with no indexed SOP"

    for label in unanswerable:
        state = run(index, labels, label)
        assert state.sop_ids == ()
        assert state.decision.action is Action.ESCALATE
        assert state.decision.reason is EscalationReason.NO_SUPPORTING_SOP


def test_unknown_label_escalates(index, labels):
    """A label the corpus never declared must fail toward the officer."""
    state = run(index, labels, "not_a_real_class")

    assert state.decision.action is Action.ESCALATE
    assert state.decision.reason is EscalationReason.NO_SUPPORTING_SOP


# --------------------------------------------------------------------------- #
# The conditional edge
# --------------------------------------------------------------------------- #


def test_escalated_items_never_reach_the_drafter(index, labels):
    state = run(index, labels, "hardship_or_waiver")

    assert state.decision.action is Action.ESCALATE
    assert state.draft.status is DraftStatus.NOT_ATTEMPTED
    assert state.draft.text is None


def test_out_of_scope_redirects_and_counts_as_automated(index, labels):
    """A redirect is an automated action and belongs in the coverage numerator."""
    state = run(index, labels, "oos_redirect")

    assert state.decision.action is Action.REDIRECT
    assert state.decision.is_automated
    assert state.auto_reply_intended


def test_low_confidence_escalates_auto_answerable(index, labels):
    """Below the bucket threshold, an auto-answerable item still escalates.

    The confidence that matters is the SUMMED bucket probability, not the class
    probability -- spreading mass across ``filing`` and its bucket-mates leaves
    routing confident even when the class is not, which is the rollup behaving as
    designed. So the mass has to sit on a class in a DIFFERENT bucket to drive the
    auto-answerable score down.
    """
    escalating = next(
        label for label in labels
        if index.bucket_for(label) == Bucket.HIGH_CONSEQUENCE.value
    )
    deps = make_deps(index, labels, "filing", confidence=0.9)

    # Hand-build a distribution: mostly high_consequence, predicted class filing.
    class Split:
        name = "split"
        labels = deps.classifier.labels

        def predict(self, text: str) -> Classification:
            spare = 0.05 / max(len(self.labels) - 2, 1)
            scores = dict.fromkeys(self.labels, spare)
            scores["filing"] = 0.25
            scores[escalating] = 0.70
            total = sum(scores.values())
            scores = {k: v / total for k, v in scores.items()}
            return Classification(label="filing", probabilities=scores, model_name="split")

        def predict_batch(self, texts: list[str]) -> list[Classification]:
            return [self.predict(t) for t in texts]

    from dataclasses import replace

    state = run_one(
        build_graph(replace(deps, classifier=Split())),
        TriageState(email=make_email()),
    )

    assert state.bucket_score.bucket is Bucket.AUTO_ANSWERABLE
    assert state.decision.action is Action.ESCALATE
    assert state.decision.reason is EscalationReason.LOW_CONFIDENCE
    assert state.draft.status is DraftStatus.NOT_ATTEMPTED


def test_multiplier_of_one_point_five_still_routes(index, labels):
    """The sweep pushes past 1.0; a clamped threshold must not raise (BUILD.md S9.9)."""
    state = run(index, labels, "filing", multiplier=1.5)

    assert state.decision is not None
    assert state.decision.threshold is None or 0.0 <= state.decision.threshold <= 1.0


# --------------------------------------------------------------------------- #
# PII never leaves the machine, and never reaches disk
# --------------------------------------------------------------------------- #


def test_classifier_sees_scrubbed_text_only(index, labels):
    email = make_email(body="My NRIC is S0433218J and I want to file.")
    state = run(index, labels, "filing", email=email)

    assert "S0433218J" not in state.scrub.text
    assert "[NRIC_1]" in state.scrub.text
    assert state.scrub.vault["[NRIC_1]"] == "S0433218J"


def test_redacted_state_carries_no_raw_pii(index, labels):
    email = make_email(body="My NRIC is S0433218J and I want to file.")
    state = run(index, labels, "filing", email=email)

    redacted = state.redacted()
    dumped = redacted.model_dump_json()

    assert "S0433218J" not in dumped
    assert redacted.scrub.vault == {}
    assert redacted.scrub.counts == state.scrub.counts, "counts are needed for recall"
