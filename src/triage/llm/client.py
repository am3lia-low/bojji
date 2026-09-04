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

**Retry policy follows the metric.** Runtime drafting and the classification
baseline do not retry, because hidden retries would distort availability or latency.
The evaluation-only groundedness judge allows two SDK retries and paced requests;
its availability is not a runtime service-level metric, and each result is saved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Protocol

from triage.schemas import DraftFailure

#: Pinned defaults. Overridable by environment so a rotated free-tier roster does
#: not require a code change.
DEFAULT_GEMINI_MODEL: Final[str] = "gemini-3.6-flash"

#: The generic Groq client defaults to the fixed Qwen model used by the zero-shot
#: classification baseline. The judge has its own default and environment override
#: below, so changing the judge cannot silently change that benchmark.
DEFAULT_GROQ_MODEL: Final[str] = "qwen/qwen3.8-27b"

#: Groundedness judge. Compound Mini has materially more free-tier TPM headroom
#: than the fixed Qwen baseline. It is eval-time only, receives the complete SOP
#: evidence, and has its external tools disabled in :class:`GroqJudgeClient`.
DEFAULT_GROQ_JUDGE_MODEL: Final[str] = "groq/compound-mini"

# The binary judge returns two short lines. A tight cap avoids reserving thousands
# of needless output tokens against Groq's free-tier tokens-per-minute allowance.
JUDGE_MAX_COMPLETION_TOKENS: Final[int] = 128

#: Per-attempt timeout: generous enough for a cold free-tier call, short enough
#: that a hung request fails the item rather than stalling a sweep.
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
    if any(k in text for k in (
        "rate limit",
        "rate_limit",
        "ratelimit",
        "429",
        "quota",
        "resource_exhausted",
        "tokens per minute",
    )):
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
        from google import genai
        from google.genai import types

        # The maintained SDK owns configuration on the client instance. That is
        # safer than the retired package's process-global ``configure(api_key=...)``
        # and keeps key rotation isolated to this call. The new SDK expects timeout
        # values in milliseconds.
        client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=int(DEFAULT_TIMEOUT * 1_000),
                # The SDK otherwise defaults to five attempts. Provider retries
                # would turn this 45-second budget into several hidden minutes and
                # contradict the explicit no-retry availability policy above.
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        response = client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature),
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
    """Generic Groq client, used by the fixed-model classification baseline.

    EVAL-TIME ONLY. Provider retries are disabled by default so the baseline's
    measured latency remains visible rather than being hidden in the SDK.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        max_retries: int = 0,
        disable_tools: bool = False,
    ) -> None:
        key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise LLMError(
                DraftFailure.API_ERROR,
                "GROQ_API_KEY is not set. The groundedness judge needs a free key "
                "from https://console.groq.com/keys",
            )
        self._model_name = model or os.environ.get("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self._key = key
        self._max_retries = max_retries
        self._disable_tools = disable_tools

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        try:
            from groq import Groq

            client = Groq(
                api_key=self._key,
                timeout=DEFAULT_TIMEOUT,
                max_retries=self._max_retries,
            )
            if self._disable_tools:
                # Compound models can search the web or execute code. A grounding
                # judge must use only the evidence supplied in the prompt.
                completion = client.chat.completions.create(
                    model=self._model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_completion_tokens=JUDGE_MAX_COMPLETION_TOKENS,
                    tool_choice="none",
                )
            else:
                completion = client.chat.completions.create(
                    model=self._model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_completion_tokens=JUDGE_MAX_COMPLETION_TOKENS,
                )
            text = (completion.choices[0].message.content or "").strip()
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(classify_error(exc), str(exc)) from exc

        if not text:
            raise LLMError(DraftFailure.API_ERROR, "provider returned no text")
        return LLMResponse(text=text, model_name=self._model_name)


class GroqJudgeClient(GroqClient):
    """Rate-limit-tolerant, evidence-only Groq groundedness judge.

    This separate client keeps the Qwen classification baseline fixed while the
    judge uses Compound Mini. Two SDK retries honour transient 429 responses; the
    surrounding evaluation additionally paces calls and checkpoints each verdict.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        judge_model = (
            model
            or os.environ.get("GROQ_JUDGE_MODEL")
            or DEFAULT_GROQ_JUDGE_MODEL
        )
        super().__init__(
            api_key=api_key,
            model=judge_model,
            max_retries=2,
            disable_tools=True,
        )


__all__ = [
    "DEFAULT_GEMINI_MODEL", "DEFAULT_GROQ_JUDGE_MODEL", "DEFAULT_GROQ_MODEL",
    "GEMINI_KEY_VARS",
    "JUDGE_MAX_COMPLETION_TOKENS",
    "GeminiClient", "GroqClient", "GroqJudgeClient", "gemini_keys",
    "LLMClient", "LLMError", "LLMResponse", "classify_error",
]
