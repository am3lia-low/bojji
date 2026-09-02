"""The classifier contract.

RUNTIME.

One Protocol, two implementations: the fine-tuned MiniLM encoder that ships in the
runtime, and the LLM zero-shot baseline used only at evaluation time. Because both
satisfy the same interface, the ablation harness swaps them with no special-casing
and the calibration layer is written once (``BUILD.md`` S5.4).

**The return type is the design decision.** ``predict`` returns the full
distribution, not a label and a score. Two things downstream need it:

* the bucket rollup sums the probabilities of the classes within each bucket, and
* ``multi_intent`` reads the second-highest class.

Returning only the argmax would discard both for no saving. It is also the point of
difference with an LLM classifier: an encoder emits a calibratable distribution
natively, whereas extracting one from a text-generating model needs logprobs (not
always exposed) or repeated sampling with agreement measurement.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from triage.schemas import Classification


@runtime_checkable
class Classifier(Protocol):
    """Anything that can turn an email into a distribution over the 12 classes."""

    @property
    def name(self) -> str:
        """Identifier recorded alongside results, so a number can be traced.

        Free-tier model rosters rotate and checkpoints move, so a result that does
        not record which model produced it cannot be reproduced later.
        """
        ...

    @property
    def labels(self) -> tuple[str, ...]:
        """The class labels, in a fixed order.

        Order is load-bearing: the linear head's output index maps to this tuple,
        so a reordering would silently permute every prediction. It is persisted
        with the weights rather than re-derived.
        """
        ...

    def predict(self, text: str) -> Classification:
        """Classify one email."""
        ...

    def predict_batch(self, texts: list[str]) -> list[Classification]:
        """Classify many emails.

        Separate from :meth:`predict` because the encoder batches efficiently on
        CPU and an API-backed baseline needs rate-limit handling; a caller looping
        over ``predict`` would get neither.
        """
        ...
