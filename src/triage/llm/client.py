"""Provider-agnostic LLM client.

RUNTIME for Gemini (drafting); EVAL-TIME for Groq (the groundedness judge).

One interface over both providers so the draft node and the judge share failure
classification, timeout handling and model-identifier recording. Free-tier rosters
rotate, so the identifier actually used is returned with every response and written
into ``eval/results/`` -- a number that does not record which model produced it
cannot be reproduced later.

**Failures are classified, not just caught.** The draft node's contract is that a
failure reaches the officer as a reason chip (``draft failed: rate limit``), so a
rate limit and a malformed response must be distinguishable here rather than
collapsed into one exception. :class:`LLMError` carries a
:class:`triage.schemas.DraftFailure`, which is the vocabulary the queue renders.

**No retries.** A free-tier rate limit does not clear in the few seconds a retry
would wait, and retrying inside an eval sweep would turn a visible availability
number into a hidden latency cost. Drafting availability is a reported metric
(``BUILD.md`` S6.2), so the failure is surfaced rather than papered over.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Protocol

from triage.schemas import DraftFailure

#: Pinned defaults. Overridable by environment so a rotated free-tier roster does
#: not require a code change.
DEFAULT_GEMINI_MODEL: Final[str] = "gemini-3.6-flash"

#: Groq's roster rotates, and this is not hypothetical: ``llama-3.3-70b-versatile``
#: -- the model this project originally pinned -- was withdrawn during the build and
#: every call began returning 404. Qwen is chosen over the ``openai/gpt-oss-*``
#: models also on the roster because GPT-4o generated the email corpus, and a judge
#: from the generator's family would weaken separation rule 3 (judge != generator,
#: ``BUILD.md`` S6.4). Override with ``GROQ_MODEL`` when this one rotates too; the
#: identifier actually used is recorded in ``eval/results/``.
DEFAULT_GROQ_MODEL: Final[str] = "qwen/qwen3.8-27b"

#: Generous enough for a cold free-tier call, short enough that a hung request
#: fails the item rather than stalling a sweep.
DEFAULT_TIMEOUT: Final[float] = 45.0


class LLMError(RuntimeError):
    """A classified provider failure."""

    def __init__(self, reason: DraftFailure, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class LLMResponse:
    """Generated text plus the identifier of the model that produced it."""

    text: str
    model_name: str


class LLMClient(Protocol):
    """Anything that turns a prompt into text."""

    @property
    def model_name(self) -> str: ...

    def generate(self, prompt: str, *, temperature: float = 0.2) -> LLMResponse: ...


def classify_error(exc: Exception) -> DraftFailure:
    """Map a provider exception onto the reported failure vocabulary.

    Matched on message text rather than exception type because the two SDKs raise
    unrelated hierarchies for the same conditions, and the queue chip needs one
    vocabulary. Anything unrecognised is ``api_error`` -- the honest default, since
    guessing ``rate_limit`` would understate a real outage.
    """
    text = f"{type(exc).__name__} {exc}".lower()
    if any(k in text for k in ("rate limit", "ratelimit", "429", "quota", "resource_exhausted")):
        return DraftFailure.RATE_LIMIT
    if any(k in text for k in ("timeout", "timed out", "deadline")):
        return DraftFailure.TIMEOUT
    return DraftFailure.API_ERROR


#: Environment variables searched, in order, for Gemini keys. The first is the
#: primary; the rest are fallbacks used only after the one before it is rate
#: limited. Free-tier drafting quota is a daily budget rather than a per-minute
#: one, so an exhausted key stays exhausted for hours -- long enough that an eval
#: sweep or a demo would otherwise have to stop and wait.
GEMINI_KEY_VARS: Final[tuple[str, ...]] = (
    "GEMINI_API_KEY",
    "GEMINI_API_KEY_2",
    "GEMINI_API_KEY_3",
)


def gemini_keys() -> list[tuple[str, str]]:
    """Return ``(variable name, key)`` for every Gemini key that is set.

    Names are returned alongside the values so a caller can report WHICH key is in
    use without printing the key itself.
    """
    return [
        (name, os.environ[name])
        for name in GEMINI_KEY_VARS
        if os.environ.get(name)
    ]


class GeminiClient:
    """Google Gemini, free tier -- the drafter.

    The key is read at construction so a missing one fails at startup rather than
    on the first citizen email. In the graph the drafter is constructed lazily, so
    an absent key surfaces as a drafting failure on every item -- which is the
    designed behaviour: the router's decision is unaffected, and the officer
    receives the item with its SOP attached.

    **Several keys may be supplied, and the client rotates through them on rate
    limit.** Free-tier drafting quota is a daily budget: once a key returns 429 it
    keeps returning 429 for hours, which is long enough to stop an eval sweep or a
    live demo dead. A second key in ``GEMINI_API_KEY_2`` lets the run continue.

    The rotation is deliberately narrow. It fires ONLY on a rate limit -- a timeout,
    a withdrawn model or a malformed response is not a quota problem and retrying it
    on another key would just spend two keys on the same failure. Once every key is
    exhausted the call fails exactly as a single-key client would, so the designed
    escalation path is unchanged and drafting availability is still reported
    honestly rather than being papered over.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        api_keys: list[tuple[str, str]] | None = None,
    ) -> None:
        if api_keys is not None:
            keys = list(api_keys)
        elif api_key:
            keys = [("GEMINI_API_KEY", api_key)]
        else:
            keys = gemini_keys()

        if not keys:
            raise LLMError(
                DraftFailure.API_ERROR,
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add a key "
                "from https://aistudio.google.com/apikey",
            )
        self._model_name = model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        self._keys = keys
        self._current = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def key_name(self) -> str:
        """Which environment variable supplied the key currently in use."""
        return self._keys[self._current][0]

    @property
    def n_keys(self) -> int:
        return len(self._keys)

    def _call(self, key: str, prompt: str, temperature: float) -> str:
        import google.generativeai as genai

        genai.configure(api_key=key)
        model = genai.GenerativeModel(self._model_name)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature},
            request_options={"timeout": DEFAULT_TIMEOUT},
        )
        return (response.text or "").strip()

    def generate(self, prompt: str, *, temperature: float = 0.2) -> LLMResponse:
        last: LLMError | None = None

        # Start at the key that worked last time. A key already known to be
        # exhausted is not retried on every subsequent email, which would spend one
        # doomed call per item for the rest of the run.
        #
        # The cursor is read ONCE into a local: ``self._current`` is advanced inside
        # the loop, so recomputing the index from it each pass would skip a key for
        # every rotation already made.
        start = self._current
        for index in range(start, len(self._keys)):
            name, key = self._keys[index]

            try:
                text = self._call(key, prompt, temperature)
            except Exception as exc:  # noqa: BLE001 -- classified, then re-raised
                reason = classify_error(exc)
                if reason is DraftFailure.RATE_LIMIT and index + 1 < len(self._keys):
                    # Quota is per key, so the next one may still have budget.
                    # Advance permanently: this key will not recover within the run.
                    self._current = index + 1
                    last = LLMError(reason, f"{name} rate limited: {exc}")
                    continue
                raise LLMError(reason, str(exc)) from exc

            if not text:
                # A blocked or empty completion has no text to ground-check, so it
                # is a failure rather than an empty draft the officer would have to
                # spot.
                raise LLMError(DraftFailure.API_ERROR, "provider returned no text")

            self._current = index
            return LLMResponse(text=text, model_name=self._model_name)

        raise last or LLMError(DraftFailure.RATE_LIMIT, "every Gemini key is rate limited")


class GroqClient:
    """Groq, free tier -- the groundedness judge.

    EVAL-TIME ONLY. A different model family from the drafter on purpose: a model
    must not be scored on its own output (``BUILD.md`` S6.4).
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise LLMError(
                DraftFailure.API_ERROR,
                "GROQ_API_KEY is not set. The groundedness judge needs a free key "
                "from https://console.groq.com/keys",
            )
        self._model_name = model or os.environ.get("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self._key = key

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        try:
            from groq import Groq

            client = Groq(api_key=self._key, timeout=DEFAULT_TIMEOUT)
            completion = client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            text = (completion.choices[0].message.content or "").strip()
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(classify_error(exc), str(exc)) from exc

        if not text:
            raise LLMError(DraftFailure.API_ERROR, "provider returned no text")
        return LLMResponse(text=text, model_name=self._model_name)


__all__ = [
    "DEFAULT_GEMINI_MODEL", "DEFAULT_GROQ_MODEL", "GEMINI_KEY_VARS",
    "GeminiClient", "GroqClient", "gemini_keys",
    "LLMClient", "LLMError", "LLMResponse", "classify_error",
]
