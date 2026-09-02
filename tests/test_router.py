"""Tests for the escalation logic -- the highest-value tests in the project.

A routing bug is not a crash. It is a citizen in financial distress receiving an
automated reply, or a taxpayer being told something about an account nobody looked
at. Those failures are silent, so they have to be caught here.

The properties under test divide into two kinds, and the distinction matters for
what the writeup may claim:

* **Structural** -- five of six escalation reasons never consult the model's
  confidence, and would fire identically at probability 1.0. These are guarantees.
* **Conditional** -- the sixth reads the calibrated confidence against a threshold.
  This one depends on the classifier being right, which is measured, not guaranteed.
"""

from __future__ import annotations

import pytest

from triage.nodes.flags import (
    detect_account_specific,
    detect_computation_requested,
    detect_flags,
)
from triage.nodes.route import PLACEHOLDER_THRESHOLD, load_thresholds, route
from triage.schemas import (
    Action,
    Bucket,
    BucketScore,
    Classification,
    EscalationReason,
    Flag,
)
from triage.sop.index import build_index

THRESHOLDS = {b.value: 0.75 for b in Bucket}


@pytest.fixture(scope="module")
def index():
    return build_index()


def sops_for(index, cls: str):
    return index.sops_for(cls)


def decide(index, cls: str, bucket: Bucket, confidence: float, flags=frozenset(), **kw):
    return route(
        BucketScore(bucket=bucket, raw=confidence, calibrated=confidence),
        sops_for(index, cls), flags, THRESHOLDS, calibrated=True, **kw,
    )


# --------------------------------------------------------------------------- #
# Structural guarantees: no confidence value changes these
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("confidence", [0.0, 0.5, 0.99, 1.0])
def test_account_specific_always_escalates(index, confidence: float) -> None:
    """Answering needs a record lookup the agent cannot do."""
    decision = decide(index, "account_specific", Bucket.REQUIRES_ACCOUNT_LOOKUP, confidence)
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.REQUIRES_ACCOUNT_LOOKUP


@pytest.mark.parametrize("cls", ["hardship_or_waiver", "scam_report"])
@pytest.mark.parametrize("confidence", [0.0, 0.99, 1.0])
def test_high_consequence_always_escalates(index, cls: str, confidence: float) -> None:
    """Financial distress and active fraud: no score may authorise an auto-reply."""
    decision = decide(index, cls, Bucket.HIGH_CONSEQUENCE, confidence)
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.HIGH_CONSEQUENCE


@pytest.mark.parametrize("cls", ["rental_income", "foreign_income_dta"])
def test_held_out_class_escalates_as_unanswerable(index, cls: str) -> None:
    """Derived from an empty lookup, never a hand-written bucket entry."""
    assert index.sops_for(cls) == ()
    decision = decide(index, cls, Bucket.NO_SUPPORTING_SOP, 0.99)
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.NO_SUPPORTING_SOP


def test_empty_sop_list_escalates_whatever_the_bucket_says(index) -> None:
    """The SOPs are the source of truth, not the bucket label.

    Asserted so that holding out a further SOP later needs no code change: an
    auto_answerable class whose SOPs vanished must still escalate.
    """
    decision = route(
        BucketScore(bucket=Bucket.AUTO_ANSWERABLE, raw=0.99, calibrated=0.99),
        (), frozenset(), THRESHOLDS, calibrated=True,
    )
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.NO_SUPPORTING_SOP


# --------------------------------------------------------------------------- #
# Flags: escalate across classes, but only where the SOP declares the trigger
# --------------------------------------------------------------------------- #

def test_computation_request_escalates_an_auto_answerable_class(index) -> None:
    """The failure mode the whole design exists to prevent.

    `tax_reliefs` is auto-answerable and the confidence is high, yet an email
    demanding arithmetic must still reach a human.
    """
    decision = decide(
        index, "tax_reliefs", Bucket.AUTO_ANSWERABLE, 0.99,
        frozenset({Flag.COMPUTATION_REQUESTED}),
    )
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.COMPUTATION_REQUESTED


@pytest.mark.parametrize(
    "cls", ["filing", "tax_reliefs", "payment", "residency", "assessment_and_amendment"],
)
def test_every_auto_answerable_class_escalates_computation(index, cls: str) -> None:
    """The rule holds across the taxonomy, not just where it was first written."""
    decision = decide(
        index, cls, Bucket.AUTO_ANSWERABLE, 0.99, frozenset({Flag.COMPUTATION_REQUESTED}),
    )
    assert decision.reason is EscalationReason.COMPUTATION_REQUESTED


def test_account_specific_backstop_catches_a_misrouted_email(index) -> None:
    """The case the backstop exists for.

    The classifier put an account enquiry in `payment` -- plausible, since the
    topical vocabulary dominates the possessive. The flag escalates it anyway.
    """
    decision = decide(
        index, "payment", Bucket.AUTO_ANSWERABLE, 0.95,
        frozenset({Flag.ACCOUNT_SPECIFIC_SIGNAL}),
    )
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.ACCOUNT_SPECIFIC_SIGNAL


def test_multi_intent_alone_does_not_escalate(index) -> None:
    """Informational. Two topics is not by itself a reason to refuse to answer."""
    decision = decide(
        index, "filing", Bucket.AUTO_ANSWERABLE, 0.95, frozenset({Flag.MULTI_INTENT}),
    )
    assert decision.action is Action.AUTO_REPLY
    assert Flag.MULTI_INTENT in decision.flags


def test_flags_are_recorded_even_when_they_do_not_decide(index) -> None:
    """The decision is an audit record, so a detected signal is never discarded."""
    decision = decide(
        index, "filing", Bucket.AUTO_ANSWERABLE, 0.95,
        frozenset({Flag.MULTI_INTENT, Flag.COMPUTATION_REQUESTED}),
    )
    assert decision.flags == frozenset({Flag.MULTI_INTENT, Flag.COMPUTATION_REQUESTED})


# --------------------------------------------------------------------------- #
# The one conditional reason
# --------------------------------------------------------------------------- #

def test_low_confidence_escalates(index) -> None:
    decision = decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.60)
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.LOW_CONFIDENCE
    assert decision.threshold == 0.75


def test_high_confidence_auto_replies(index) -> None:
    decision = decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.90)
    assert decision.action is Action.AUTO_REPLY
    assert decision.reason is None


def test_confidence_exactly_at_the_threshold_acts(index) -> None:
    """The comparison is strict, so the boundary is defined rather than incidental."""
    assert decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.75).action is Action.AUTO_REPLY


# --------------------------------------------------------------------------- #
# Precedence
# --------------------------------------------------------------------------- #

def test_bucket_escalation_outranks_a_high_score(index) -> None:
    decision = decide(index, "scam_report", Bucket.HIGH_CONSEQUENCE, 1.0)
    assert decision.reason is EscalationReason.HIGH_CONSEQUENCE


def test_computation_outranks_low_confidence(index) -> None:
    """The more specific reason is reported, since accuracy is measured per reason."""
    decision = decide(
        index, "tax_reliefs", Bucket.AUTO_ANSWERABLE, 0.10,
        frozenset({Flag.COMPUTATION_REQUESTED}),
    )
    assert decision.reason is EscalationReason.COMPUTATION_REQUESTED


# --------------------------------------------------------------------------- #
# Coverage accounting
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cls", ["oos_redirect"])
def test_confident_out_of_scope_redirects(index, cls: str) -> None:
    """A clean redirect is the correct outcome, and counts toward coverage."""
    decision = decide(index, cls, Bucket.OUT_OF_SCOPE, 0.95)
    assert decision.action is Action.REDIRECT
    assert decision.is_automated


def test_uncertain_out_of_scope_escalates(index) -> None:
    """A wrong redirect sends a citizen to the wrong agency -- visible, and theirs."""
    decision = decide(index, "oos_redirect", Bucket.OUT_OF_SCOPE, 0.40)
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.LOW_CONFIDENCE


# --------------------------------------------------------------------------- #
# The threshold sweep behind the risk-coverage curve
# --------------------------------------------------------------------------- #

def test_multiplier_scales_the_threshold(index) -> None:
    """The curve is swept with the real router, so it cannot drift from the system."""
    strict = decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.80, multiplier=1.2)
    lenient = decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.80, multiplier=0.5)
    assert strict.action is Action.ESCALATE
    assert lenient.action is Action.AUTO_REPLY


def test_a_high_multiplier_escalates_everything_answerable(index) -> None:
    decision = decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.99, multiplier=2.0)
    assert decision.action is Action.ESCALATE


def test_a_low_multiplier_never_unlocks_an_always_escalate_bucket(index) -> None:
    """Sweeping the curve must not be able to disable the structural guarantees."""
    decision = decide(index, "scam_report", Bucket.HIGH_CONSEQUENCE, 0.01, multiplier=0.0)
    assert decision.action is Action.ESCALATE


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def test_thresholds_load_for_every_bucket() -> None:
    thresholds = load_thresholds()
    for bucket in Bucket:
        assert bucket.value in thresholds


def test_missing_config_falls_back_to_the_placeholder(tmp_path) -> None:
    thresholds = load_thresholds(str(tmp_path / "absent.yaml"))
    assert thresholds[Bucket.AUTO_ANSWERABLE.value] == PLACEHOLDER_THRESHOLD


def test_uncalibrated_decisions_are_marked(index) -> None:
    """A number produced under the placeholder threshold must never be reported."""
    decision = route(
        BucketScore(bucket=Bucket.AUTO_ANSWERABLE, raw=0.9),
        sops_for(index, "filing"), frozenset(), THRESHOLDS, calibrated=False,
    )
    assert decision.calibrated is False


# --------------------------------------------------------------------------- #
# Flag detection
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text", [
    "How much child relief will I get?",
    "Can you calculate my tax for me",
    "what amount do I owe now",
    "Please tell me the exact figure I need to pay",
    "I earn 80,000 dollars, what will my tax be?",
    "Is it $4,000 for my case?",
    "how many dollars is the relief",
    "Can you work out the total for me",
])
def test_computation_requests_are_detected(text: str) -> None:
    assert detect_computation_requested(text)


@pytest.mark.parametrize("text", [
    "What are the conditions for claiming child relief?",
    "When is the filing deadline?",
    "How do I apply for GIRO?",
    "The relief is $4,000 per child, is that right for everyone?",
    "Which reliefs am I eligible to claim in general?",
])
def test_ordinary_questions_are_not_computation_requests(text: str) -> None:
    """Precision matters: a false positive escalates an answerable email."""
    assert not detect_computation_requested(text)


@pytest.mark.parametrize("text", [
    "Why was my GIRO deduction reversed?",
    "What is the status of my refund",
    "I still have not received my tax bill",
    "Can you check my account please",
    "when will I receive the money",
    "my claim was rejected and I do not understand why",
])
def test_account_specific_phrasing_is_detected(text: str) -> None:
    assert detect_account_specific(text)


@pytest.mark.parametrize("text", [
    "When are GIRO deductions taken each month?",
    "What is the filing deadline this year?",
    "How does the No-Filing Service work?",
    "Who must file an income tax return?",
])
def test_generic_questions_are_not_account_specific(text: str) -> None:
    assert not detect_account_specific(text)


def test_multi_intent_reads_the_runner_up() -> None:
    classification = Classification(
        label="filing", probabilities={"filing": 0.55, "payment": 0.40, "residency": 0.05},
    )
    assert Flag.MULTI_INTENT in detect_flags("When is the deadline?", classification)


def test_a_confident_prediction_is_not_multi_intent() -> None:
    classification = Classification(
        label="filing", probabilities={"filing": 0.92, "payment": 0.05, "residency": 0.03},
    )
    assert Flag.MULTI_INTENT not in detect_flags("When is the deadline?", classification)


def test_flags_combine() -> None:
    text = "Why was my relief rejected and how much should I have received?"
    flags = detect_flags(text)
    assert Flag.COMPUTATION_REQUESTED in flags
    assert Flag.ACCOUNT_SPECIFIC_SIGNAL in flags


@pytest.mark.parametrize(
    "cls", ["filing", "tax_reliefs", "payment", "residency", "assessment_and_amendment"],
)
def test_scam_signal_escalates_every_auto_answerable_class(index, cls: str) -> None:
    """A misfiled fraud report must never be auto-answered with tax content.

    The scam flag is a MISFILE guard: a correctly classified scam report already
    escalates on the ``high_consequence`` bucket without consulting it. It matters
    only when the classifier put a fraud report somewhere else, and the unsafe
    directions are two, not one:

    * redirected to another agency (``oos_redirect``), which SOP-RTE-002 has
      always covered; and
    * answered with substantive tax content from an auto-answerable SOP, which
      nothing covered until these five SOPs declared the trigger.

    The flag is computed from text alone and is independent of the predicted class,
    but the router honours it only where a RETRIEVED SOP declares it -- so declaring
    it in frontmatter is what makes it bite. That is the corpus-as-policy seam
    working: no code change, no retrain, and the 12-class label set is untouched.
    """
    decision = decide(
        index, cls, Bucket.AUTO_ANSWERABLE, 0.99, frozenset({Flag.SCAM_SIGNAL}),
    )
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.SCAM_SIGNAL


def test_scam_signal_still_escalates_an_out_of_scope_redirect(index) -> None:
    """The original guard is unaffected: a fraud victim is not redirected away."""
    decision = decide(
        index, "oos_redirect", Bucket.OUT_OF_SCOPE, 0.99,
        frozenset({Flag.SCAM_SIGNAL}),
    )
    assert decision.action is Action.ESCALATE
    assert decision.reason is EscalationReason.SCAM_SIGNAL


# --------------------------------------------------------------------------- #
# Exhaustive invariants
# --------------------------------------------------------------------------- #

_ALWAYS_ESCALATE = {
    Bucket.REQUIRES_ACCOUNT_LOOKUP: "account_specific",
    Bucket.HIGH_CONSEQUENCE: "scam_report",
}


@pytest.mark.parametrize("bucket,cls", list(_ALWAYS_ESCALATE.items()))
@pytest.mark.parametrize("confidence", [0.0, 0.5, 0.9, 1.0])
def test_always_escalate_buckets_ignore_every_flag_combination(
    index, bucket: Bucket, cls: str, confidence: float
) -> None:
    """No flag combination and no confidence can make these buckets act.

    Swept over the full power set of flags rather than a sample: these two buckets
    are the ones where an automated reply would be worst, so the guarantee is
    asserted exhaustively rather than spot-checked.
    """
    import itertools

    flags = list(Flag)
    for size in range(len(flags) + 1):
        for combination in itertools.combinations(flags, size):
            decision = decide(index, cls, bucket, confidence, frozenset(combination))
            assert decision.action is Action.ESCALATE
            assert decision.reason is not None


@pytest.mark.parametrize("confidence", [0.0, 0.49, 0.75, 1.0])
def test_escalation_implies_a_reason_and_action_implies_none(
    index, confidence: float
) -> None:
    """``reason`` is present exactly when the item escalated.

    The officer queue groups by reason, so an escalation without one is an item
    nobody can triage; an action carrying one would be a contradiction the demo
    would render.
    """
    for bucket, cls in (
        (Bucket.AUTO_ANSWERABLE, "filing"),
        (Bucket.OUT_OF_SCOPE, "oos_redirect"),
        (Bucket.REQUIRES_ACCOUNT_LOOKUP, "account_specific"),
        (Bucket.HIGH_CONSEQUENCE, "scam_report"),
    ):
        decision = decide(index, cls, bucket, confidence)
        assert (decision.action is Action.ESCALATE) == (decision.reason is not None)


def test_threshold_boundary_escalates_strictly_below(index) -> None:
    """The rule is ``confidence < threshold``: equality acts.

    Pinned because the boundary decides coverage at the operating point, and a
    later edit to ``<=`` would move every reported coverage figure without any
    test noticing.
    """
    assert decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.7499).action is Action.ESCALATE
    assert decide(index, "filing", Bucket.AUTO_ANSWERABLE, 0.75).action is Action.AUTO_REPLY


@pytest.mark.parametrize("multiplier", [2.0, 3.0, 100.0])
def test_multiplier_above_the_sweep_maximum_does_not_raise(
    index, multiplier: float
) -> None:
    """The sweep pushes the multiplier past 1.0; a threshold above 1.0 is clamped.

    ``BUILD.md`` S9.9 records this as one of two router bugs found by testing. The
    clamp means "always escalate" rather than a validation error.
    """
    decision = decide(
        index, "filing", Bucket.AUTO_ANSWERABLE, 0.9, multiplier=multiplier
    )
    assert decision.threshold is not None
    assert decision.threshold <= 1.0
    assert decision.action is Action.ESCALATE
