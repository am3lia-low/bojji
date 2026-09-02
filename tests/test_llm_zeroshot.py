"""The LLM zero-shot baseline.

Tested with a fake client, so the suite needs no key and no network. What is being
tested is the *manufacturing of a distribution* from text replies -- the part that
makes this baseline defensible as a comparison, and the part that shows why an
encoder is the better runtime choice.
"""

from __future__ import annotations

import pytest

from triage.llm.client import LLMError, LLMResponse
from triage.models.base import Classifier
from triage.models.llm_zeroshot import LLMZeroShotClassifier
from triage.schemas import DraftFailure

LABELS = ("filing", "payment", "tax_reliefs", "account_specific", "oos_business_tax")


class FakeClient:
    """Replays a fixed list of replies, cycling if asked for more."""

    def __init__(self, replies: list[str], model_name: str = "fake-judge") -> None:
        self._replies = replies
        self._model_name = model_name
        self.calls = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, *, temperature: float = 0.2) -> LLMResponse:
        reply = self._replies[self.calls % len(self._replies)]
        self.calls += 1
        return LLMResponse(text=reply, model_name=self._model_name)


class AlwaysFails:
    model_name = "broken"

    def generate(self, prompt: str, *, temperature: float = 0.2) -> LLMResponse:
        raise LLMError(DraftFailure.RATE_LIMIT, "simulated")


def build(replies: list[str], samples: int = 5) -> LLMZeroShotClassifier:
    return LLMZeroShotClassifier(FakeClient(replies), LABELS, samples=samples)


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


def test_satisfies_the_classifier_protocol():
    """The whole point: the ablation harness swaps it for the encoder unchanged."""
    assert isinstance(build(["filing"]), Classifier)


def test_distribution_is_over_the_supplied_labels_in_order():
    result = build(["filing"]).predict("anything")

    assert tuple(result.probabilities) == LABELS


def test_probabilities_sum_to_one():
    result = build(["filing", "payment", "filing"]).predict("anything")

    assert sum(result.probabilities.values()) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Self-consistency: agreement becomes confidence
# --------------------------------------------------------------------------- #


def test_unanimous_samples_give_high_confidence():
    result = build(["filing"] * 5, samples=5).predict("How do I file?")

    assert result.label == "filing"
    assert result.confidence > 0.9


def test_split_samples_give_lower_confidence():
    """Three votes to two is genuine uncertainty, and must read as such."""
    result = build(["filing", "filing", "filing", "payment", "payment"], samples=5).predict("x")

    assert result.label == "filing"
    assert 0.5 < result.confidence < 0.7


def test_confidence_resolution_is_capped_by_k():
    """The model-selection argument, as a test.

    With k samples the only reachable confidences are multiples of 1/k. No amount of
    data changes that, which is why the encoder's continuous softmax is the better
    thing to calibrate and threshold.
    """
    seen = set()
    for votes in range(1, 4):
        replies = ["filing"] * votes + ["payment"] * (3 - votes)
        seen.add(round(build(replies, samples=3).predict("x").confidence, 2))

    assert len(seen) <= 3, "resolution should be coarse, bounded by k"


def test_it_costs_k_calls_per_email():
    """Reported as a model-selection finding: k API calls against one CPU pass."""
    client = FakeClient(["filing"])
    LLMZeroShotClassifier(client, LABELS, samples=5).predict("x")

    assert client.calls == 5


# --------------------------------------------------------------------------- #
# Parsing: a model must not be able to invent a class
# --------------------------------------------------------------------------- #


def test_unknown_label_is_not_adopted():
    """``tax_filing`` is not in the taxonomy and must not become a thirteenth class."""
    result = build(["tax_filing"] * 3, samples=3).predict("x")

    assert result.label in LABELS


def test_prose_reply_is_parsed():
    result = build(["I think this is a filing question."] * 3, samples=3).predict("x")

    assert result.label == "filing"


def test_longest_label_wins_over_a_shorter_overlap():
    """``oos_business_tax`` must not be shadowed by a shorter name inside it."""
    result = build(["oos_business_tax"] * 3, samples=3).predict("x")

    assert result.label == "oos_business_tax"


def test_reasoning_block_is_ignored():
    """Reasoning models name several categories while thinking; only the answer counts."""
    reply = "<think>Could be payment or tax_reliefs, hmm.</think>\nfiling"
    result = build([reply] * 3, samples=3).predict("x")

    assert result.label == "filing"


def test_labelled_answer_format_is_parsed():
    result = build(["Label: payment"] * 3, samples=3).predict("x")

    assert result.label == "payment"


# --------------------------------------------------------------------------- #
# Degradation
# --------------------------------------------------------------------------- #


def test_unparseable_replies_give_a_uniform_distribution():
    """Telling us nothing must read as no information, not as a confident guess."""
    result = build(["???"] * 3, samples=3).predict("x")

    assert result.confidence == pytest.approx(1.0 / len(LABELS))


def test_total_api_failure_gives_uniform_rather_than_raising():
    """A baseline that crashed mid-sweep would lose the whole comparison."""
    result = LLMZeroShotClassifier(AlwaysFails(), LABELS, samples=3).predict("x")

    assert result.confidence == pytest.approx(1.0 / len(LABELS))


def test_a_dropped_sample_is_a_missing_vote_not_a_wrong_one():
    """Losing one of k widens the interval; inventing a vote would bias it."""
    class SometimesFails:
        model_name = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, temperature: float = 0.2) -> LLMResponse:
            self.calls += 1
            if self.calls == 2:
                raise LLMError(DraftFailure.RATE_LIMIT, "simulated")
            return LLMResponse(text="filing", model_name="flaky")

    result = LLMZeroShotClassifier(SometimesFails(), LABELS, samples=3).predict("x")

    assert result.label == "filing"
    assert result.confidence > 0.9, "two agreeing votes out of two counted"


def test_no_class_has_exactly_zero_probability():
    """Smoothed, so a single confident error is not infinitely penalised."""
    result = build(["filing"] * 5, samples=5).predict("x")

    assert all(p > 0 for p in result.probabilities.values())


def test_name_records_the_model_and_k():
    """A result that does not say which model produced it cannot be reproduced."""
    name = build(["filing"], samples=4).name

    assert "fake-judge" in name
    assert "k4" in name
