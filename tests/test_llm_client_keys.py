"""Gemini key rotation.

Free-tier drafting quota is a DAILY budget, not a per-minute one: once a key
returns 429 it keeps returning 429 for hours. Measured during this build, a run of
20 sequential drafts exhausted a single key after one success -- long enough to stop
an eval sweep or a live demo dead.

A second key lets the run continue. The rotation is narrow on purpose, and these
tests pin both halves of that: it fires on a rate limit, and it does NOT fire on
anything else.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from triage.llm.client import GeminiClient, GroqClient, GroqJudgeClient, LLMError
from triage.schemas import DraftFailure

THREE = [
    ("GEMINI_API_KEY", "k1"),
    ("GEMINI_API_KEY_2", "k2"),
    ("GEMINI_API_KEY_3", "k3"),
]


class FakeGemini(GeminiClient):
    """A client whose provider call is scripted per key.

    Any key absent from ``behaviour`` is treated as rate limited, which is the
    condition under test.
    """

    def __init__(self, keys, behaviour):
        super().__init__(api_keys=keys)
        self.behaviour = behaviour
        self.calls: list[str] = []

    def _call(self, key: str, prompt: str, temperature: float) -> str:
        self.calls.append(key)
        outcome = self.behaviour.get(key, Exception("429 quota exceeded"))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_first_key_is_used_when_it_works() -> None:
    client = FakeGemini(THREE, {"k1": "drafted"})

    assert client.generate("p").text == "drafted"
    assert client.calls == ["k1"]
    assert client.key_name == "GEMINI_API_KEY"


def test_rate_limit_rotates_to_the_next_key() -> None:
    client = FakeGemini(THREE, {"k2": "drafted"})

    assert client.generate("p").text == "drafted"
    assert client.calls == ["k1", "k2"]
    assert client.key_name == "GEMINI_API_KEY_2"


def test_an_exhausted_key_is_not_retried_on_later_calls() -> None:
    """The cursor advances permanently, because quota does not recover mid-run.

    Retrying the dead key would spend one doomed call per email for the rest of the
    sweep -- turning a fallback into a per-item latency cost.
    """
    client = FakeGemini(THREE, {"k2": "drafted"})
    client.generate("first")
    client.generate("second")

    assert client.calls == ["k1", "k2", "k2"]


def test_rotation_continues_through_every_key() -> None:
    client = FakeGemini(THREE, {"k3": "drafted"})

    assert client.generate("p").text == "drafted"
    assert client.calls == ["k1", "k2", "k3"]


def test_all_keys_exhausted_fails_as_a_rate_limit() -> None:
    """The designed failure path is unchanged: the item escalates with its SOP."""
    client = FakeGemini(THREE, {})

    with pytest.raises(LLMError) as caught:
        client.generate("p")

    assert caught.value.reason is DraftFailure.RATE_LIMIT
    assert client.calls == ["k1", "k2", "k3"]


def test_a_timeout_does_not_rotate() -> None:
    """Only quota is per key.

    A timeout, a withdrawn model or a malformed response would fail identically on
    the next key, so retrying there spends two keys on one failure and muddies the
    reported reason.
    """
    client = FakeGemini(THREE, {"k1": Exception("deadline exceeded timeout"), "k2": "x"})

    with pytest.raises(LLMError) as caught:
        client.generate("p")

    assert caught.value.reason is DraftFailure.TIMEOUT
    assert client.calls == ["k1"]


def test_a_single_key_behaves_exactly_as_before() -> None:
    """The fallback is additive: one key gives one attempt and the same reason."""
    client = FakeGemini([("GEMINI_API_KEY", "k1")], {})

    with pytest.raises(LLMError) as caught:
        client.generate("p")

    assert caught.value.reason is DraftFailure.RATE_LIMIT
    assert client.calls == ["k1"]
    assert client.n_keys == 1


def test_no_key_at_all_is_a_construction_error() -> None:
    with pytest.raises(LLMError):
        GeminiClient(api_keys=[])


def test_provider_sdk_retries_are_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """One provider attempt means the configured timeout remains a real bound."""
    from google import genai

    captured: dict[str, object] = {}

    class FakeModels:
        @staticmethod
        def generate_content(**_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(text="drafted")

    class FakeProviderClient:
        def __init__(self, *, api_key: str, http_options: object) -> None:
            captured["api_key"] = api_key
            captured["http_options"] = http_options
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeProviderClient)

    response = GeminiClient(api_key="fake-key").generate("prompt")

    assert response.text == "drafted"
    options = captured["http_options"]
    assert options.timeout == 45_000  # type: ignore[attr-defined]
    assert options.retry_options.attempts == 1  # type: ignore[attr-defined]


def test_judge_caps_output_tokens_and_disables_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import groq

    captured: dict[str, object] = {}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs: object) -> SimpleNamespace:
            captured["request"] = kwargs
            message = SimpleNamespace(
                content="VERDICT: GROUNDED\nREASON: Supported."
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeGroq:
        def __init__(
            self,
            *,
            api_key: str,
            timeout: float,
            max_retries: int,
        ) -> None:
            captured.update({
                "api_key": api_key,
                "timeout": timeout,
                "max_retries": max_retries,
            })
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(groq, "Groq", FakeGroq)

    response = GroqClient(api_key="fake-key").generate("prompt")

    assert response.text.startswith("VERDICT: GROUNDED")
    assert captured["max_retries"] == 0
    request = captured["request"]
    assert request["max_completion_tokens"] == 128  # type: ignore[index]
    assert "tool_choice" not in request  # type: ignore[operator]


def test_compound_judge_retries_and_disables_external_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import groq

    captured: dict[str, object] = {}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs: object) -> SimpleNamespace:
            captured["request"] = kwargs
            message = SimpleNamespace(
                content="VERDICT: GROUNDED\nREASON: Supported."
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeGroq:
        def __init__(
            self,
            *,
            api_key: str,
            timeout: float,
            max_retries: int,
        ) -> None:
            captured["max_retries"] = max_retries
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(groq, "Groq", FakeGroq)

    client = GroqJudgeClient(api_key="fake-key")
    response = client.generate("prompt")

    assert response.model_name == "groq/compound-mini"
    assert captured["max_retries"] == 2
    request = captured["request"]
    assert request["tool_choice"] == "none"  # type: ignore[index]
