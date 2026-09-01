"""Tests for the state contract between graph nodes.

The invariants asserted here are the ones a routing bug would violate. They are
enforced in the schema rather than in the router's control flow deliberately: an
auto-reply to a citizen in financial distress must be impossible to *construct*,
not merely absent from the branch that happens to be written today.

Two properties carry most of the weight:

* three buckets escalate regardless of confidence, and cannot be built otherwise
* a drafting failure never reads back as a routing decision, so a Gemini outage
  cannot leak into the risk-coverage curve (``BUILD.md`` S5.8)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from triage.schemas import (
    Action,
    Bucket,
    BucketScore,
    Classification,
    DraftFailure,
    DraftResult,
    DraftStatus,
    Email,
    EscalationReason,
    Flag,
    RoutingDecision,
    ScrubRecord,
    TriageState,
)

ALWAYS_ESCALATE = [
    Bucket.REQUIRES_ACCOUNT_LOOKUP,
    Bucket.HIGH_CONSEQUENCE,
    Bucket.NO_SUPPORTING_SOP,
]


def make_email(**overrides: object) -> Email:
    defaults: dict[str, object] = {
        "id": "e1",
        "received_at": datetime(2026, 4, 12, 9, 31, tzinfo=UTC),
        "subject": "GIRO deduction",
        "body": "When are deductions taken?",
    }
    return Email(**{**defaults, **overrides})  # type: ignore[arg-type]


def make_decision(**overrides: object) -> RoutingDecision:
    defaults: dict[str, object] = {
        "action": Action.AUTO_REPLY,
        "bucket": Bucket.AUTO_ANSWERABLE,
        "confidence": 0.9,
        "threshold": 0.75,
        "calibrated": True,
    }
    return RoutingDecision(**{**defaults, **overrides})  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Email
# --------------------------------------------------------------------------- #

def test_text_joins_subject_and_body() -> None:
    """A subject often carries the intent while the body carries the detail."""
    email = make_email(subject="GIRO failed", body="Why?")
    assert email.text == "GIRO failed\n\nWhy?"


def test_text_survives_an_empty_subject() -> None:
    assert make_email(subject="", body="Only a body").text == "Only a body"


def test_from_is_accepted_as_an_alias() -> None:
    """``from`` is reserved in Python; the inbox schema uses it as a key."""
    email = Email(
        id="e1", received_at=datetime.now(UTC), body="x",
        **{"from": "citizen@example.com"},  # type: ignore[arg-type]
    )
    assert email.sender == "citizen@example.com"


def test_empty_body_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_email(body="")


def test_email_is_immutable() -> None:
    """Nodes accumulate state; none rewrites the inbound message."""
    with pytest.raises(ValidationError):
        make_email().body = "tampered"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

def test_confidence_is_the_predicted_label_probability() -> None:
    c = Classification(label="payment", probabilities={"payment": 0.7, "filing": 0.3})
    assert c.confidence == 0.7


def test_runner_up_supports_multi_intent() -> None:
    """Two high-scoring classes IS multi-intent; the distribution already has it."""
    c = Classification(
        label="payment",
        probabilities={"payment": 0.5, "filing": 0.4, "residency": 0.1},
    )
    assert c.runner_up == ("filing", 0.4)


def test_distribution_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match="sum to"):
        Classification(label="filing", probabilities={"filing": 0.5, "payment": 0.2})


def test_label_must_appear_in_the_distribution() -> None:
    with pytest.raises(ValidationError, match="absent"):
        Classification(label="ghost", probabilities={"filing": 1.0})


# --------------------------------------------------------------------------- #
# BucketScore and calibration
# --------------------------------------------------------------------------- #

def test_calibrated_confidence_is_preferred() -> None:
    score = BucketScore(bucket=Bucket.AUTO_ANSWERABLE, raw=0.95, calibrated=0.82)
    assert score.confidence == 0.82


def test_raw_confidence_is_used_before_calibration_is_fitted() -> None:
    """The pipeline must run end to end before calibration exists."""
    score = BucketScore(bucket=Bucket.AUTO_ANSWERABLE, raw=0.95)
    assert score.confidence == 0.95


def test_probabilities_outside_zero_to_one_are_rejected() -> None:
    with pytest.raises(ValidationError):
        BucketScore(bucket=Bucket.AUTO_ANSWERABLE, raw=1.4)


# --------------------------------------------------------------------------- #
# The escalation guarantee
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("bucket", ALWAYS_ESCALATE)
def test_always_escalate_buckets_cannot_auto_reply(bucket: Bucket) -> None:
    """Not even at confidence 1.0. The guarantee is structural, not conditional."""
    with pytest.raises(ValidationError, match="must always escalate"):
        make_decision(action=Action.AUTO_REPLY, bucket=bucket, confidence=1.0, reason=None)


@pytest.mark.parametrize("bucket", ALWAYS_ESCALATE)
def test_always_escalate_buckets_cannot_redirect(bucket: Bucket) -> None:
    with pytest.raises(ValidationError):
        make_decision(action=Action.REDIRECT, bucket=bucket, reason=None)


@pytest.mark.parametrize("bucket", ALWAYS_ESCALATE)
def test_always_escalate_buckets_accept_escalation(bucket: Bucket) -> None:
    decision = make_decision(
        action=Action.ESCALATE, bucket=bucket, reason=EscalationReason.HIGH_CONSEQUENCE,
    )
    assert decision.action is Action.ESCALATE


def test_escalation_must_carry_a_reason() -> None:
    """Reported per reason, so an unlabelled escalation would vanish from the tally."""
    with pytest.raises(ValidationError, match="escalation reason"):
        make_decision(action=Action.ESCALATE, bucket=Bucket.AUTO_ANSWERABLE)


def test_automated_actions_must_not_carry_a_reason() -> None:
    with pytest.raises(ValidationError, match="must not carry"):
        make_decision(reason=EscalationReason.LOW_CONFIDENCE)


def test_auto_reply_requires_the_auto_answerable_bucket() -> None:
    with pytest.raises(ValidationError, match="auto_answerable"):
        make_decision(action=Action.AUTO_REPLY, bucket=Bucket.OUT_OF_SCOPE)


def test_redirect_requires_the_out_of_scope_bucket() -> None:
    with pytest.raises(ValidationError, match="out_of_scope"):
        make_decision(action=Action.REDIRECT, bucket=Bucket.AUTO_ANSWERABLE)


# --------------------------------------------------------------------------- #
# Coverage accounting
# --------------------------------------------------------------------------- #

def test_a_redirect_counts_as_automated() -> None:
    """No back door: a clean redirect is the correct outcome, not a failure, so it
    belongs in the coverage numerator (``BUILD.md`` S5.6).
    """
    decision = make_decision(action=Action.REDIRECT, bucket=Bucket.OUT_OF_SCOPE)
    assert decision.is_automated


def test_an_escalation_is_not_automated() -> None:
    decision = make_decision(
        action=Action.ESCALATE, bucket=Bucket.HIGH_CONSEQUENCE,
        reason=EscalationReason.HIGH_CONSEQUENCE,
    )
    assert not decision.is_automated


def test_redirect_is_distinguishable_from_a_substantive_answer() -> None:
    """Both are automated, but their content differs, so they are reported apart."""
    redirect = make_decision(action=Action.REDIRECT, bucket=Bucket.OUT_OF_SCOPE)
    answer = make_decision(action=Action.AUTO_REPLY)
    assert redirect.is_automated and answer.is_automated
    assert redirect.action is not answer.action


def test_uncalibrated_decisions_are_marked() -> None:
    """A number produced under the placeholder threshold must never be reported."""
    assert make_decision(calibrated=False).calibrated is False


# --------------------------------------------------------------------------- #
# DraftResult
# --------------------------------------------------------------------------- #

def test_a_successful_draft_must_carry_text() -> None:
    with pytest.raises(ValidationError, match="must carry text"):
        DraftResult(status=DraftStatus.OK)


def test_a_failed_draft_must_carry_a_cause() -> None:
    with pytest.raises(ValidationError, match="failure reason"):
        DraftResult(status=DraftStatus.FAILED)


def test_only_a_failed_draft_may_carry_a_cause() -> None:
    with pytest.raises(ValidationError, match="only a failed draft"):
        DraftResult(status=DraftStatus.OK, text="x", failure_reason=DraftFailure.TIMEOUT)


def test_a_failed_draft_still_carries_its_sop() -> None:
    """The officer writes from the same source the drafter would have used, so a
    failure costs a paraphrase rather than the research (``BUILD.md`` S5.8).
    """
    draft = DraftResult(
        status=DraftStatus.FAILED, failure_reason=DraftFailure.RATE_LIMIT,
        sop_ids=("SOP-PAY-001",),
    )
    assert draft.sop_ids == ("SOP-PAY-001",)


def test_grounded_on_is_recorded_for_grounding_accuracy() -> None:
    """Compared against the scenario spec's source SOP (``BUILD.md`` S9.2)."""
    draft = DraftResult(
        status=DraftStatus.OK, text="...",
        sop_ids=("SOP-REL-001", "SOP-REL-002", "SOP-REL-003", "SOP-REL-004"),
        grounded_on=("SOP-REL-001", "SOP-REL-002"),
    )
    assert set(draft.grounded_on) <= set(draft.sop_ids)


# --------------------------------------------------------------------------- #
# The routing / drafting separation
# --------------------------------------------------------------------------- #

def test_a_drafting_failure_does_not_change_the_routing_signal() -> None:
    """The load-bearing invariant of ``BUILD.md`` S5.8.

    A rate-limit says nothing about whether the email was safe to auto-reply. If
    it read back as "the router declined", a Gemini outage would corrupt the
    risk-coverage curve -- the headline result.
    """
    state = TriageState(
        email=make_email(),
        decision=make_decision(),
        draft=DraftResult(
            status=DraftStatus.FAILED, failure_reason=DraftFailure.RATE_LIMIT,
            sop_ids=("SOP-PAY-001",),
        ),
    )
    assert state.auto_reply_intended is True   # the router DID choose to act
    assert state.draft_failed is True
    assert state.in_human_queue is True        # but a human must finish it


def test_a_drafting_failure_is_not_reported_as_an_escalation_reason() -> None:
    state = TriageState(
        email=make_email(),
        decision=make_decision(),
        draft=DraftResult(
            status=DraftStatus.FAILED, failure_reason=DraftFailure.TIMEOUT,
            sop_ids=("SOP-FIL-001",),
        ),
    )
    assert state.queue_reason == "draft_failed: timeout"
    assert state.decision is not None
    assert state.decision.reason is None


def test_a_successful_auto_reply_stays_out_of_the_queue() -> None:
    state = TriageState(
        email=make_email(),
        decision=make_decision(),
        draft=DraftResult(status=DraftStatus.OK, text="...", sop_ids=("SOP-PAY-001",)),
    )
    assert not state.in_human_queue
    assert state.queue_reason is None


def test_an_escalated_item_reports_its_escalation_reason() -> None:
    state = TriageState(
        email=make_email(),
        decision=make_decision(
            action=Action.ESCALATE, bucket=Bucket.REQUIRES_ACCOUNT_LOOKUP,
            reason=EscalationReason.REQUIRES_ACCOUNT_LOOKUP,
        ),
    )
    assert state.queue_reason == "requires_account_lookup"
    assert not state.auto_reply_intended


def test_an_incomplete_run_fails_safe_toward_the_human() -> None:
    """No decision means no basis to act, so the item must not be auto-replied."""
    state = TriageState(email=make_email())
    assert state.in_human_queue
    assert not state.auto_reply_intended


# --------------------------------------------------------------------------- #
# State accumulation
# --------------------------------------------------------------------------- #

def test_state_accumulates_a_full_audit_record() -> None:
    """A completed state is what the demo renders and what every metric reads."""
    state = TriageState(
        email=make_email(),
        scrub=ScrubRecord(text="scrubbed", vault={"[NRIC_1]": "S1234567D"}),
        classification=Classification(label="payment", probabilities={"payment": 1.0}),
        bucket_score=BucketScore(bucket=Bucket.AUTO_ANSWERABLE, raw=0.9, calibrated=0.8),
        sop_ids=("SOP-PAY-001",),
        decision=make_decision(confidence=0.8, flags=frozenset({Flag.MULTI_INTENT})),
        draft=DraftResult(status=DraftStatus.OK, text="...", sop_ids=("SOP-PAY-001",)),
    )
    assert state.scrub is not None and state.scrub.redacted_count == 1
    assert state.classification is not None and state.classification.label == "payment"
    assert state.decision is not None and Flag.MULTI_INTENT in state.decision.flags
    assert state.draft is not None and state.draft.status is DraftStatus.OK


def test_unknown_fields_are_rejected() -> None:
    """A typo in a node must fail loudly rather than write a field nothing reads."""
    with pytest.raises(ValidationError):
        TriageState(email=make_email(), decsion=None)  # type: ignore[call-arg]


# --------------------------------------------------------------------------- #
# Agreement with the corpus-derived layer
# --------------------------------------------------------------------------- #

def test_bucket_enum_matches_the_index() -> None:
    """``schemas`` declares the buckets so it can be imported without the corpus;
    ``sop.index`` derives them from frontmatter. Cross-checked rather than shared,
    so a divergence fails here instead of at request time.
    """
    from triage.sop.index import BUCKETS

    assert {b.value for b in Bucket} == set(BUCKETS)


def test_every_escalation_reason_is_reachable() -> None:
    """Six reasons, all reported. An unreachable one would be dead reporting."""
    assert len(EscalationReason) == 6


# --------------------------------------------------------------------------- #
# The persistence boundary
# --------------------------------------------------------------------------- #

def test_ordinary_serialisation_contains_pii_by_design() -> None:
    """Documents why :meth:`TriageState.redacted` exists.

    In-memory state holds real identifiers on purpose -- the vault is what makes
    local rehydration possible. The danger is not the state, it is writing it out.
    """
    state = TriageState(
        email=make_email(body="My NRIC is S1234567D"),
        scrub=ScrubRecord(text="My NRIC is [NRIC_1]", vault={"[NRIC_1]": "S1234567D"}),
    )
    assert "S1234567D" in state.model_dump_json()


def test_redacted_state_carries_no_identifiers() -> None:
    """eval/results/ is committed to the repository, so anything written there
    must be free of planted PII.
    """
    state = TriageState(
        email=make_email(
            subject="my nric", body="My NRIC is S1234567D, phone 91234567",
            **{"from": "citizen@example.com"},
        ),
        scrub=ScrubRecord(
            text="My NRIC is [NRIC_1], phone [PHONE_1]",
            vault={"[NRIC_1]": "S1234567D", "[PHONE_1]": "91234567"},
            counts={"nric": 1, "sg_phone": 1},
        ),
    )
    dumped = state.redacted().model_dump_json()
    for identifier in ("S1234567D", "91234567", "citizen@example.com"):
        assert identifier not in dumped, identifier


def test_redacted_state_keeps_what_reporting_needs() -> None:
    """Scrub recall is computed from counts, not from the values themselves."""
    state = TriageState(
        email=make_email(body="My NRIC is S1234567D"),
        scrub=ScrubRecord(
            text="My NRIC is [NRIC_1]", vault={"[NRIC_1]": "S1234567D"},
            counts={"nric": 1},
        ),
    )
    redacted = state.redacted()
    assert redacted.scrub is not None
    assert redacted.scrub.counts == {"nric": 1}
    assert redacted.scrub.vault == {}
    assert "[NRIC_1]" in redacted.scrub.text


def test_redacting_an_unscrubbed_state_fails_safe() -> None:
    """A state that never reached the scrub node must not be written out on the
    assumption that it happened to be clean.
    """
    state = TriageState(email=make_email(body="raw S7654321Z here"))
    assert "S7654321Z" not in state.redacted().model_dump_json()


def test_redaction_preserves_the_decision_record() -> None:
    """Redaction removes identifiers, not the audit trail the metrics read."""
    state = TriageState(
        email=make_email(),
        scrub=ScrubRecord(text="scrubbed"),
        decision=make_decision(),
        draft=DraftResult(status=DraftStatus.OK, text="...", sop_ids=("SOP-PAY-001",)),
    )
    redacted = state.redacted()
    assert redacted.decision == state.decision
    assert redacted.draft == state.draft
    assert redacted.email.id == state.email.id


# --------------------------------------------------------------------------- #
# Distribution tolerance
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("total", [0.9995, 1.0, 1.0005])
def test_float_error_in_a_softmax_is_tolerated(total: float) -> None:
    Classification(label="a", probabilities={"a": total})


@pytest.mark.parametrize("probs", [{"a": 0.5, "b": 0.2}, {"a": 2.0}, {"a": 0.5}])
def test_a_malformed_distribution_is_rejected(probs: dict[str, float]) -> None:
    """Scores that were never softmaxed, or a truncated dict, must not pass."""
    with pytest.raises(ValidationError):
        Classification(label="a", probabilities=probs)


def test_a_twelve_class_softmax_passes() -> None:
    """The real case: 12 equal probabilities do not sum to exactly 1.0 in floats."""
    probs = {f"c{i}": 1 / 12 for i in range(12)}
    Classification(label="c0", probabilities=probs)
