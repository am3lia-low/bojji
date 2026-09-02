"""LLM zero-shot classifier -- the comparison baseline, never the runtime.

EVAL-TIME ONLY. Satisfies the same :class:`triage.models.base.Classifier` Protocol
as the encoder, so the ablation harness swaps them with no special-casing and the
calibration layer is written once.

**Why this exists.** Model selection is graded on justification, and "the encoder is
better calibrated" is an assertion until something measures it. This turns it into a
number: encoder vs LLM on accuracy, latency, size, cost and ECE (``BUILD.md`` S9.3).

**Why it is not the runtime classifier.** The whole contribution is calibration, and
this class is where the difficulty of getting a probability out of a text model is
visible rather than argued about:

* An LLM asked to classify returns *text*. There is no distribution to soften.
* Logprobs would give one, but they are not exposed by every provider and are not
  comparable across them.
* So confidence has to be *manufactured*, and this module does it by
  self-consistency: sample the model ``k`` times at non-zero temperature and read
  agreement as the probability. That costs ``k`` API calls per email, is coarse
  (with k=5 the resolution is 0.2), and its floor is 1/k rather than zero.

The encoder emits a calibratable distribution natively, from one CPU forward pass.
That contrast IS the model-selection argument, and it is why this module is
deliberately built the honest, expensive way rather than by asking the model to
state a confidence -- a self-reported number is not a frequency and would not be
calibratable at all.

**Ordering matters.** ``labels`` is fixed at construction and every distribution is
built over it, so the encoder and this baseline produce vectors that index
identically. Otherwise the two could not be compared.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from triage.llm.client import LLMClient, LLMError
from triage.schemas import Classification

#: Versioned prompt, on disk beside the drafting one.
PROMPT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "llm" / "prompts" / "classify_zeroshot.v1.txt"
)

#: Samples per email for self-consistency. Five is a compromise the design states
#: rather than hides: enough that agreement means something, few enough that a
#: 520-email test split stays inside a free tier. It caps confidence resolution at
#: 0.2, which is precisely the coarseness the encoder does not suffer from.
DEFAULT_SAMPLES: Final[int] = 5

#: Non-zero, because self-consistency needs the samples to be able to disagree. At
#: temperature 0 every sample is identical and the "distribution" is always 1.0 --
#: which would look like perfect confidence and calibrate to nonsense.
SAMPLING_TEMPERATURE: Final[float] = 0.7

#: Mass reserved for classes the model never named, spread evenly. Without it an
#: unsampled class has probability exactly zero, and a single confident error would
#: give infinite loss under any log-scoring rule.
_SMOOTHING: Final[float] = 0.01


@lru_cache(maxsize=1)
def _prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


class LLMZeroShotClassifier:
    """Classifies by prompting, with confidence from sample agreement.

    Args:
        client: Any :class:`~triage.llm.client.LLMClient`. Groq by default at the
            call site -- a different family from the drafter, so no model is scored
            on its own output.
        labels: The class set, in the SAME order the encoder uses.
        samples: How many times to sample each email.
    """

    def __init__(
        self,
        client: LLMClient,
        labels: tuple[str, ...],
        samples: int = DEFAULT_SAMPLES,
        descriptions: dict[str, str] | None = None,
    ) -> None:
        self._client = client
        self._labels = tuple(labels)
        self._samples = max(1, samples)
        self._descriptions = descriptions or {}

    @property
    def name(self) -> str:
        return f"llm-zeroshot-{self._client.model_name}-k{self._samples}"

    @property
    def labels(self) -> tuple[str, ...]:
        return self._labels

    def _render(self, text: str) -> str:
        catalogue = "\n".join(
            f"- {label}" + (f": {self._descriptions[label]}" if label in self._descriptions else "")
            for label in self._labels
        )
        return _prompt_template().format(labels=catalogue, email=text.strip())

    def _parse(self, reply: str) -> str | None:
        """Pull a known label out of a free-text reply.

        Matched against the known label set rather than trusted verbatim: a model
        that answers "this is a filing question" or invents ``tax_filing`` must not
        create a thirteenth class. An unparseable reply is a non-vote, not a guess.
        """
        # Strip any reasoning block first. Several current free-tier models emit
        # <think>...</think> before the answer, and that text discusses several
        # categories by name -- so parsing it would pick up whichever class the
        # model considered first rather than the one it concluded on.
        lowered = re.sub(r"<think>.*?</think>", " ", reply.lower(), flags=re.DOTALL)
        lowered = re.sub(r"<think>.*", " ", lowered, flags=re.DOTALL)

        if match := re.search(r"^\s*(?:label|answer|class)\s*:\s*([a-z_]+)", lowered, re.M):
            candidate = match.group(1)
            if candidate in self._labels:
                return candidate

        # Fall back to the first label mentioned anywhere, longest-first so that
        # `oos_business_tax` is not shadowed by a shorter overlapping name.
        for label in sorted(self._labels, key=len, reverse=True):
            if label in lowered:
                return label
        return None

    def _distribution(self, votes: list[str]) -> dict[str, float]:
        """Turn sample agreement into a probability distribution.

        Smoothed so no class sits at exactly zero. With no valid votes at all the
        result is uniform -- the honest representation of "this model told us
        nothing", and it routes to low confidence rather than to a fabricated class.
        """
        if not votes:
            return dict.fromkeys(self._labels, 1.0 / len(self._labels))

        counts = Counter(votes)
        floor = _SMOOTHING / len(self._labels)
        scores = {
            label: floor + (1.0 - _SMOOTHING) * counts[label] / len(votes)
            for label in self._labels
        }
        total = sum(scores.values())
        return {label: value / total for label, value in scores.items()}

    def predict(self, text: str) -> Classification:
        prompt = self._render(text)
        votes: list[str] = []

        for _ in range(self._samples):
            try:
                response = self._client.generate(prompt, temperature=SAMPLING_TEMPERATURE)
            except LLMError:
                # A dropped sample is a missing vote, not a wrong one. Losing one
                # of five widens the interval; inventing a vote would bias it.
                continue
            if (label := self._parse(response.text)) is not None:
                votes.append(label)

        scores = self._distribution(votes)
        return Classification(
            label=max(scores, key=lambda k: scores[k]),
            probabilities=scores,
            model_name=self.name,
        )

    def predict_batch(self, texts: list[str]) -> list[Classification]:
        """Classify many emails.

        Sequential on purpose: free-tier limits are per-request-rate, so parallel
        calls would trip them and turn a measurement into a rate-limit study. The
        cost of this baseline -- ``k`` calls per email, serialised -- is itself a
        model-selection finding worth reporting.
        """
        return [self.predict(text) for text in texts]


def build_zeroshot(
    labels: tuple[str, ...],
    samples: int = DEFAULT_SAMPLES,
    client: Any | None = None,
) -> LLMZeroShotClassifier:
    """Construct the baseline against Groq, with taxonomy descriptions if present.

    Descriptions come from ``config/taxonomy.yaml`` so the baseline is told what the
    classes mean in the same words the taxonomy defines them -- otherwise it would
    be guessing from label names and the comparison would be unfair to it.
    """
    if client is None:
        from triage.llm.client import GroqClient

        client = GroqClient()

    descriptions: dict[str, str] = {}
    config = Path(__file__).resolve().parents[3] / "config" / "taxonomy.yaml"
    if config.exists():
        import yaml

        document = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        for name, spec in (document.get("classes") or {}).items():
            if isinstance(spec, dict):
                text = spec.get("description") or spec.get("scope") or ""
                if text:
                    descriptions[str(name)] = " ".join(str(text).split())[:220]

    return LLMZeroShotClassifier(client, labels, samples, descriptions)


__all__ = ["DEFAULT_SAMPLES", "LLMZeroShotClassifier", "build_zeroshot"]
