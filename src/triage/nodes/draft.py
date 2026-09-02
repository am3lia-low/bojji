"""Draft node -- the only node that may fail without invalidating the decision.

RUNTIME. Last in the chain, because everything upstream has already succeeded by
the time it runs.

Gemini is given the retrieved SOP group and the scrubbed email, and writes the
reply. There is deliberately **no template fallback** (``BUILD.md`` S5.8): a
degraded reply would hide that anything went wrong, and would give the demo a
second drafting path that could drift from the measured system.

**Two invariants this node must not break.**

1. *Drafting failure is not a routing signal.* A rate limit says nothing about
   whether the email was safe to auto-reply. The item is never relabelled
   ``low_confidence``; :attr:`TriageState.auto_reply_intended` still reads True and
   ``draft_status`` records what actually happened. If a Gemini outage leaked into
   the routing signal it would corrupt the risk-coverage curve, which is the
   headline result.
2. *Eval treats a failed draft as missing, not wrong.* There is no text to score,
   so the item leaves the groundedness denominator and is counted in drafting
   availability instead. Scoring an infrastructure failure as a groundedness
   failure would blame the model for a rate limit.

``sop_ids`` is populated on failure too. The officer working the queue writes the
reply from the same source the drafter would have used, so a failure costs a
paraphrase rather than the research.

**Rehydration happens here and only here.** The draft comes back containing
``[NRIC_1]``; real values are substituted locally, after the network call. A
placeholder the vault cannot resolve means the model invented one, which is a
fabrication rather than a redaction -- the draft is failed rather than sent with a
bare token in it.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Final

from triage.llm.client import LLMClient, LLMError
from triage.pii.scrubber import Scrubber
from triage.schemas import (
    DraftFailure,
    DraftResult,
    DraftStatus,
    TriageState,
)
from triage.sop.index import SOPIndex
from triage.sop.loader import SOP

#: Versioned template. On disk rather than inline so a prompt change is a diff in
#: its own file rather than a line buried in a module.
PROMPT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "llm" / "prompts" / "draft_reply.v1.txt"
)

#: The trailing line the drafter appends, naming what it grounded on. Parsed rather
#: than assumed, because grounding accuracy is measured against the scenario spec's
#: recorded ``source_sops`` (``BUILD.md`` S9.2).
_CITED_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*CITED:\s*(?P<ids>.*)$", re.MULTILINE | re.IGNORECASE
)

_SOP_ID_RE: Final[re.Pattern[str]] = re.compile(r"SOP-[A-Z]{3}-\d{3}")


@lru_cache(maxsize=1)
def _prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _scrubber() -> Scrubber:
    return Scrubber()


def render_prompt(sops: tuple[SOP, ...], subject: str, body: str) -> str:
    """Build the drafting prompt.

    The whole SOP group goes in, not a pre-selected member: a multi-relief question
    needs more than one, and pre-selecting would answer the wrong half. Worst case
    is the four relief SOPs at ~6,900 tokens, well inside free-tier limits -- the
    real risk is attention rather than capacity, which is what the grounding metric
    measures.
    """
    rendered = "\n\n".join(
        f"### {sop.sop_id} - {sop.title} (v{sop.version})\n\n{sop.body.strip()}"
        for sop in sops
    )
    return _prompt_template().format(sops=rendered, subject=subject or "(none)", body=body)


def parse_citations(text: str, valid: frozenset[str]) -> tuple[str, tuple[str, ...]]:
    """Split the reply from its trailing ``CITED:`` line.

    Returns the reply with the line removed and the SOP ids claimed, filtered to
    those actually supplied. A model naming a SOP it was never given is recorded as
    citing nothing rather than as citing a document that does not exist.
    """
    match = _CITED_RE.search(text)
    if match is None:
        return text.strip(), ()

    cited = tuple(
        sop_id for sop_id in _SOP_ID_RE.findall(match["ids"].upper()) if sop_id in valid
    )
    return (text[: match.start()] + text[match.end():]).strip(), cited


def _failed(
    state: TriageState,
    reason: DraftFailure,
    message: str,
    *,
    model_name: str | None = None,
) -> dict[str, object]:
    """A failed draft that still carries the SOPs the officer needs."""
    return {
        "draft": DraftResult(
            status=DraftStatus.FAILED,
            failure_reason=reason,
            sop_ids=state.sop_ids,
            model_name=model_name,
        ),
        "errors": [*state.errors, f"draft failed: {message}"],
    }


def draft_node(
    state: TriageState,
    index: SOPIndex,
    client: LLMClient | None,
) -> dict[str, object]:
    """Draft a reply, or record why there is none.

    Runs only for items the router chose to act on. An escalated item is not
    drafted -- an officer writes that reply -- so it records ``NOT_ATTEMPTED``,
    which keeps "the router declined" and "the drafter broke" separable in the
    evaluation.
    """
    decision = state.decision

    if decision is None or not decision.is_automated:
        return {"draft": DraftResult(status=DraftStatus.NOT_ATTEMPTED, sop_ids=state.sop_ids)}

    if state.scrub is None:
        return _failed(state, DraftFailure.API_ERROR, "no scrubbed text")

    sops = tuple(index.by_id[sid] for sid in state.sop_ids if sid in index.by_id)

    # A redirect for an out-of-scope enquiry is still SOP-grounded: the redirect
    # SOPs carry the destination agency and the approved phrasing for saying so.
    if not sops:
        return _failed(state, DraftFailure.API_ERROR, "no SOP to ground on")

    if client is None:
        return _failed(state, DraftFailure.API_ERROR, "no drafting client configured")

    prompt = render_prompt(sops, state.email.subject, state.scrub.text)
    model_name = getattr(client, "model_name", None)

    try:
        response = client.generate(prompt)
    except LLMError as exc:
        return _failed(state, exc.reason, f"{exc.reason}: {exc}", model_name=model_name)
    except Exception as exc:  # noqa: BLE001 -- a drafting crash must not stop triage
        return _failed(state, DraftFailure.API_ERROR, str(exc), model_name=model_name)

    body, cited = parse_citations(response.text, frozenset(state.sop_ids))

    # A placeholder the vault cannot resolve was invented by the model. Rehydrating
    # around it would send the citizen a reply containing a bare [NRIC_2].
    if unresolved := _scrubber().unresolved(body, state.scrub.vault):
        return _failed(
            state,
            DraftFailure.API_ERROR,
            f"fabricated placeholders {', '.join(unresolved)}",
            model_name=response.model_name,
        )

    return {
        "draft": DraftResult(
            status=DraftStatus.OK,
            text=_scrubber().rehydrate(body, state.scrub.vault),
            sop_ids=state.sop_ids,
            grounded_on=cited,
            model_name=response.model_name,
        )
    }


__all__ = ["draft_node", "parse_citations", "render_prompt"]
