"""Typed state passed between graph nodes.

RUNTIME. Every node is ``pure(state) -> state``, so this module defines the only
contract between them. Nodes add fields; none removes or rewrites what an earlier
node wrote, which is what makes a completed :class:`TriageState` a full audit
record of how one email was handled -- the property the demo's reason chips and
the whole evaluation both read from.

Three modelling decisions here carry design weight rather than being convenience:

**Escalation reason is an enum, not a string.** It is reported per reason
(``BUILD.md`` S6.2), so a typo would silently create a seventh category and split
a metric. Six values, closed.

**A redirect is an automated action, not an escalation.** ``out_of_scope`` classes
auto-reply with a redirect, and that counts toward coverage under the no-back-door
policy (S5.6). Modelling it as an escalation would understate coverage on the
whole out-of-scope class.

**Drafting failure is separated from routing.** ``auto_reply_intended`` records
what the router decided; ``draft_status`` records what the drafter managed. A
Gemini rate-limit must never read back as "the router declined", or an outage
would leak into the risk-coverage curve, which is the headline result (S5.8).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Tolerance on a softmax summing to 1.0. Wide enough for float error accumulated
#: across the class set plus a temperature division, tight enough that a genuinely
#: malformed distribution -- a truncated dict, or scores that were never softmaxed
#: -- still fails.
_PROB_SUM_TOLERANCE: float = 1e-3

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class Bucket(StrEnum):
    """The five routing buckets (``sop_design.md`` S3).

    Mirrors ``triage.sop.index``, which derives the class -> bucket map from SOP
    frontmatter. Duplicated as an enum so the schema layer can be imported without
    loading the corpus, and cross-checked in tests rather than by inheritance.
    """

    AUTO_ANSWERABLE = "auto_answerable"
    REQUIRES_ACCOUNT_LOOKUP = "requires_account_lookup"
    HIGH_CONSEQUENCE = "high_consequence"
    OUT_OF_SCOPE = "out_of_scope"
    NO_SUPPORTING_SOP = "no_supporting_sop"


class EscalationReason(StrEnum):
    """Why an item went to the human queue. Reported per reason, so closed.

    Ordered by the router's precedence. The first four are structural -- they never
    consult the classifier's confidence and would fire identically at probability
    1.0. Only ``LOW_CONFIDENCE`` reads the calibrated score.
    """

    REQUIRES_ACCOUNT_LOOKUP = "requires_account_lookup"
    HIGH_CONSEQUENCE = "high_consequence"
    NO_SUPPORTING_SOP = "no_supporting_sop"
    COMPUTATION_REQUESTED = "computation_requested"
    ACCOUNT_SPECIFIC_SIGNAL = "account_specific_signal"
    FOREIGN_INCOME_SIGNAL = "foreign_income_signal"
    SCAM_SIGNAL = "scam_signal"
    LOW_CONFIDENCE = "low_confidence"


class Flag(StrEnum):
    """Signals that cut ACROSS classes, so they cannot be classes themselves.

    Detected after the bucket rollup and applied to a class the SOP declares them
    for, which keeps the taxonomy a clean partition (``sop_design.md`` S3.1).

    ``COMPUTATION_REQUESTED`` gates the rule the corpus exists to enforce: the
    agent never computes a tax or relief amount. ``ACCOUNT_SPECIFIC_SIGNAL`` is a
    backstop for a known taxonomy compromise -- ``account_specific`` is a class but
    structurally a flag, and topical vocabulary dominates the one-or-two-token
    possessive signal, so the confusion lands on the unsafe side (``BUILD.md``
    S9.6).

    ``MULTI_INTENT`` is free: two high-scoring classes IS multi-intent, and the
    distribution already exists. It is informational and does not itself escalate.
    """

    COMPUTATION_REQUESTED = "computation_requested"
    ACCOUNT_SPECIFIC_SIGNAL = "account_specific_signal"
    #: Two MISFILE guards. Unlike the flags above, these do not mark a condition
    #: that cuts across an otherwise-correct classification -- they catch the
    #: classifier putting an email in the wrong class, in the one direction where
    #: that error is unsafe. ``FOREIGN_INCOME_SIGNAL`` guards residency against
    #: absorbing a held-out foreign-income question; ``SCAM_SIGNAL`` guards the
    #: redirect SOPs against sending a fraud victim to another agency. Both
    #: triggers are declared in SOP frontmatter (SOP-RES-001, SOP-RTE-002), so the
    #: corpus already asked for them.
    FOREIGN_INCOME_SIGNAL = "foreign_income_signal"
    SCAM_SIGNAL = "scam_signal"
    MULTI_INTENT = "multi_intent"


class Action(StrEnum):
    """What the system did with an item.

    ``REDIRECT`` is deliberately distinct from ``AUTO_REPLY`` and from
    ``ESCALATE``: it is an automated action that counts toward coverage, but its
    content is a redirect rather than a substantive answer, so the two are reported
    separately (S5.6).
    """

    AUTO_REPLY = "auto_reply"
    REDIRECT = "redirect"
    ESCALATE = "escalate"


class DraftStatus(StrEnum):
    """Whether drafting produced text. Independent of the routing decision."""

    OK = "ok"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


class DraftFailure(StrEnum):
    """Why a draft call failed. Free-tier rate limits fire during eval sweeps, so
    this path is exercised rather than hypothetical (``BUILD.md`` S5.8)."""

    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"


# --------------------------------------------------------------------------- #
# Inbox
# --------------------------------------------------------------------------- #


class Email(BaseModel):
    """One inbound citizen email -- the pipeline's entry point.

    ``received_at`` is load-bearing rather than metadata: it drives the seasonality
    axis (filing Mar-Apr, estimates May-Jun, NOA Jun-Jul), so an evaluation slice
    can ask whether performance holds across the tax year.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    received_at: datetime
    subject: str = ""
    body: str = Field(min_length=1)
    sender: str | None = Field(default=None, alias="from")

    @property
    def text(self) -> str:
        """Subject and body as one string -- what the classifier sees.

        Joined rather than classified separately: a subject line often carries the
        intent ("GIRO deduction failed") while the body carries the detail, and
        splitting them would discard the strongest short signal in the message.
        """
        return f"{self.subject}\n\n{self.body}".strip()


# --------------------------------------------------------------------------- #
# Node outputs
# --------------------------------------------------------------------------- #


class ScrubRecord(BaseModel):
    """What the scrub node removed, and what is needed to reverse it.

    The vault stays in local state and is never sent anywhere. Rehydration happens
    locally after the draft returns, so real identifiers exist only on this machine.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    vault: dict[str, str] = Field(default_factory=dict, repr=False)
    counts: dict[str, int] = Field(default_factory=dict)

    @property
    def redacted_count(self) -> int:
        return len(self.vault)


class Classification(BaseModel):
    """The classifier's output: a label and the full distribution behind it.

    ``probabilities`` is kept in full rather than reduced to a top score, because
    the bucket rollup sums within-bucket probabilities and ``multi_intent`` reads
    the second-highest. Discarding the distribution would cost both for no saving.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    probabilities: dict[str, float]
    model_name: str = "unknown"

    @model_validator(mode="after")
    def _check_distribution(self) -> Self:
        if self.label not in self.probabilities:
            raise ValueError(f"label {self.label!r} absent from the distribution")
        total = sum(self.probabilities.values())
        if abs(total - 1.0) > _PROB_SUM_TOLERANCE:
            raise ValueError(f"probabilities sum to {total:.6f}, expected 1.0")
        return self

    @property
    def confidence(self) -> float:
        """Raw, uncalibrated probability of the predicted label.

        Systematically overconfident: a network reporting 0.95 may be right 85% of
        the time. That gap is what the project measures, and it is why this value
        must not be compared against a threshold directly -- use
        :attr:`RoutingDecision.confidence`, which is calibrated.
        """
        return self.probabilities[self.label]

    @property
    def runner_up(self) -> tuple[str, float] | None:
        """Second-highest class and its probability, for ``multi_intent``."""
        ranked = sorted(self.probabilities.items(), key=lambda kv: -kv[1])
        return ranked[1] if len(ranked) > 1 else None


class BucketScore(BaseModel):
    """The distribution rolled up from the class set into 5 buckets.

    Calibration and thresholds live at this level, not at class level: at 1,800
    emails a bucket carries ~108 test examples against ~45 for a class, and a
    threshold set on 45 is not defensible -- the binomial interval is wider than the
    effect (``sop_design.md`` S3).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bucket: Bucket
    raw: Annotated[float, Field(ge=0.0, le=1.0)]
    calibrated: Annotated[float, Field(ge=0.0, le=1.0)] | None = None

    @property
    def confidence(self) -> float:
        """Calibrated confidence where it exists, else raw.

        Falling back is deliberate: the pipeline must run end to end before
        calibration is fitted. Whether a reported number came from the fitted
        temperature is recorded on :attr:`RoutingDecision.calibrated`, so a
        placeholder figure can never be mistaken for a result.
        """
        return self.raw if self.calibrated is None else self.calibrated


class RoutingDecision(BaseModel):
    """The escalation decision -- the system's contribution, in one object.

    Invariants enforced below rather than left to the router's control flow, since
    a routing bug is a citizen-facing failure and must not depend on a branch being
    written correctly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action
    bucket: Bucket
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    threshold: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    reason: EscalationReason | None = None
    flags: frozenset[Flag] = frozenset()
    #: False while the placeholder threshold is in force. A number produced under
    #: a placeholder must never be reported (``BUILD.md`` S7).
    calibrated: bool = False

    @model_validator(mode="after")
    def _reason_matches_action(self) -> Self:
        if self.action is Action.ESCALATE and self.reason is None:
            raise ValueError("an escalated item must carry an escalation reason")
        if self.action is not Action.ESCALATE and self.reason is not None:
            raise ValueError(f"{self.action} must not carry an escalation reason")
        return self

    @model_validator(mode="after")
    def _always_escalate_buckets_escalate(self) -> Self:
        """Three buckets escalate regardless of confidence, and an empty SOP lookup
        escalates by derivation. Asserted here so no confidence value, and no
        future edit to the router, can produce an auto-reply for them.
        """
        always = {
            Bucket.REQUIRES_ACCOUNT_LOOKUP,
            Bucket.HIGH_CONSEQUENCE,
            Bucket.NO_SUPPORTING_SOP,
        }
        if self.bucket in always and self.action is not Action.ESCALATE:
            raise ValueError(f"bucket {self.bucket} must always escalate, got {self.action}")
        return self

    @model_validator(mode="after")
    def _redirect_only_for_out_of_scope(self) -> Self:
        if self.action is Action.REDIRECT and self.bucket is not Bucket.OUT_OF_SCOPE:
            raise ValueError(f"redirect is only valid for out_of_scope, got {self.bucket}")
        if self.action is Action.AUTO_REPLY and self.bucket is not Bucket.AUTO_ANSWERABLE:
            raise ValueError(f"auto_reply is only valid for auto_answerable, got {self.bucket}")
        return self

    @property
    def is_automated(self) -> bool:
        """Whether the system acted without a human.

        A redirect counts: under the no-back-door policy a clean redirect is the
        correct outcome, not a failure, so it belongs in the coverage numerator
        (``BUILD.md`` S5.6).
        """
        return self.action in (Action.AUTO_REPLY, Action.REDIRECT)


class DraftResult(BaseModel):
    """The drafter's output, or the reason there is none.

    ``sop_ids`` is always populated, even on failure: the officer working the
    review queue writes the reply from the same source the drafter would have used,
    so a failure costs a paraphrase rather than the research (``BUILD.md`` S5.8).

    ``grounded_on`` is what the draft actually cited, and is compared against the
    scenario spec's source SOP to measure grounding accuracy (S9.2). It applies to
    ``tax_reliefs`` and ``payment``, the two classes that pull a group.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: DraftStatus
    text: str | None = None
    failure_reason: DraftFailure | None = None
    sop_ids: tuple[str, ...] = ()
    grounded_on: tuple[str, ...] = ()
    model_name: str | None = None

    @model_validator(mode="after")
    def _status_matches_payload(self) -> Self:
        if self.status is DraftStatus.OK and not self.text:
            raise ValueError("a successful draft must carry text")
        if self.status is DraftStatus.FAILED and self.failure_reason is None:
            raise ValueError("a failed draft must carry a failure reason")
        if self.status is not DraftStatus.FAILED and self.failure_reason is not None:
            raise ValueError("only a failed draft may carry a failure reason")
        return self


# --------------------------------------------------------------------------- #
# Graph state
# --------------------------------------------------------------------------- #


class TriageState(BaseModel):
    """Everything known about one email, accumulated across the graph.

    Nodes append; nothing is overwritten. A completed state is therefore the audit
    record for one decision -- which is what the demo's reason chips render and what
    every evaluation metric reads.
    """

    model_config = ConfigDict(extra="forbid")

    email: Email
    scrub: ScrubRecord | None = None
    classification: Classification | None = None
    bucket_score: BucketScore | None = None
    sop_ids: tuple[str, ...] = ()
    decision: RoutingDecision | None = None
    draft: DraftResult | None = None
    #: Node-level failures that did not stop the run, for the demo and for triage.
    errors: list[str] = Field(default_factory=list)

    @property
    def auto_reply_intended(self) -> bool:
        """Whether the ROUTER chose to act, regardless of what drafting managed.

        The load-bearing distinction of ``BUILD.md`` S5.8. A drafting failure must
        not read back as a routing decision: a rate-limit says nothing about
        whether the email was safe to auto-reply, and if it leaked into the routing
        signal a Gemini outage would corrupt the risk-coverage curve.
        """
        return self.decision is not None and self.decision.is_automated

    @property
    def draft_failed(self) -> bool:
        return self.draft is not None and self.draft.status is DraftStatus.FAILED

    @property
    def in_human_queue(self) -> bool:
        """Items an officer must work: escalations, plus drafting failures.

        Two different populations sharing one queue. ``auto_reply_intended``
        separates them for evaluation.
        """
        if self.decision is None:
            return True  # incomplete run: fail safe toward the human
        return not self.decision.is_automated or self.draft_failed

    @property
    def queue_reason(self) -> str | None:
        """Why this item is in the human queue -- the demo's reason chip.

        A drafting failure is reported as ``draft_failed: <cause>`` and never as an
        escalation reason, so the two remain separable downstream.
        """
        if self.draft_failed and self.decision is not None and self.decision.is_automated:
            assert self.draft is not None and self.draft.failure_reason is not None
            return f"draft_failed: {self.draft.failure_reason}"
        if self.decision is not None and self.decision.reason is not None:
            return str(self.decision.reason)
        return None

    def redacted(self) -> TriageState:
        """A copy safe to write to disk: no vault, no unscrubbed text.

        The ordinary serialisation of this state contains raw PII by design -- the
        vault holds real identifiers so the draft can be rehydrated locally, and
        ``email.body`` is the message as received. That is correct in memory and
        wrong on disk, because ``eval/results/`` is committed to the repository and
        the demo writes its queues out.

        This method is the boundary. It replaces the email text with the scrubbed
        form, empties the vault, and keeps the redaction *counts*, which is what
        scrub-recall reporting actually needs. Anything persisted or displayed goes
        through here; nothing else should serialise a :class:`TriageState`.

        Falls back to redacting the body entirely if scrubbing has not run, rather
        than passing the original through -- a state that never reached the scrub
        node must not be written out on the assumption that it was clean.
        """
        if self.scrub is None:
            safe_body = "[UNSCRUBBED - REDACTED]"
            safe_subject = "[UNSCRUBBED - REDACTED]"
        else:
            safe_body = self.scrub.text
            safe_subject = ""

        return self.model_copy(
            update={
                "email": self.email.model_copy(
                    update={"body": safe_body, "subject": safe_subject, "sender": None}
                ),
                "scrub": (
                    None
                    if self.scrub is None
                    else ScrubRecord(text=self.scrub.text, vault={}, counts=self.scrub.counts)
                ),
            }
        )


__all__ = [
    "Action",
    "Bucket",
    "BucketScore",
    "Classification",
    "DraftFailure",
    "DraftResult",
    "DraftStatus",
    "Email",
    "EscalationReason",
    "Flag",
    "RoutingDecision",
    "ScrubRecord",
    "TriageState",
]
