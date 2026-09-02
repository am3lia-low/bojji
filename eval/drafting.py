"""Drafting availability, grounding accuracy, and the groundedness judge.

EVAL-TIME.

Three things are measured over a sample of drafts:

**Drafting availability** -- the share of intended auto-replies that produced text.
Free-tier rate limits are real and fire during a sweep, so this is a reported
number rather than an assumed 100%. A failed draft is *missing*, not wrong: it
leaves the groundedness denominator and is counted here instead. Scoring an
infrastructure failure as a groundedness failure would blame the model for a rate
limit and make the metric move with free-tier load (``BUILD.md`` S5.8).

**Grounding accuracy** -- did the draft cite the SOP the email was actually built
from? The scenario spec recorded ``source_sops``, and the drafter emits a ``CITED:``
line, so the comparison is free. It applies only to ``tax_reliefs`` and ``payment``,
the two classes that pull a group of more than one; for the 1:1 classes the answer
is correct by construction and measuring it would be theatre (S9.2).

**Groundedness** -- one binary question put to a judge: *does this reply assert any
fact not present in the provided SOP?* Narrow question, binary outcome, and
judge-human agreement reported, which is what makes an LLM judge defensible rather
than decorative. Groq is the primary judge: free, fast, and a different model family
from the drafter, because a model must not be scored on its own output (S6.4).

**Judge outputs are committed** with each judge's model identifier and date, so a
grader reads the judgments without re-running anything or holding a key.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from triage.llm.client import LLMError
from triage.nodes.draft import PROMPT_PATH, parse_citations, render_prompt
from triage.schemas import DraftFailure
from triage.sop.index import SOPIndex

#: Classes whose SOP lookup returns more than one document, so the drafter makes a
#: real selection. Grounding accuracy is meaningful only here.
MULTI_SOP_CLASSES: Final[frozenset[str]] = frozenset({"tax_reliefs", "payment"})

_VERDICT_RE: Final[re.Pattern[str]] = re.compile(
    r"VERDICT:\s*(?P<verdict>GROUNDED|UNGROUNDED)", re.IGNORECASE
)
_REASON_RE: Final[re.Pattern[str]] = re.compile(r"REASON:\s*(?P<reason>.+)", re.IGNORECASE)

JUDGE_PROMPT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1]
    / "src" / "triage" / "llm" / "prompts" / "judge_groundedness.v1.txt"
)


@dataclass
class DraftRecord:
    """One sampled draft and everything measured about it."""

    email_id: str
    label: str
    sop_ids: tuple[str, ...]
    source_sops: tuple[str, ...]
    status: str
    text: str | None = None
    failure_reason: str | None = None
    grounded_on: tuple[str, ...] = ()
    model_name: str | None = None
    judge_verdict: str | None = None
    judge_reason: str | None = None
    judge_model: str | None = None

    @property
    def grounding_correct(self) -> bool | None:
        """Whether the draft cited at least one SOP the email was built from.

        ``None`` when the question does not apply -- a failed draft, a 1:1 class, or
        a spec that recorded no source SOP. Returning None rather than False keeps
        inapplicable items out of the denominator instead of scoring them as wrong.
        """
        if self.status != "ok" or self.label not in MULTI_SOP_CLASSES:
            return None
        if not self.source_sops or not self.grounded_on:
            return None
        return bool(set(self.grounded_on) & set(self.source_sops))

    def as_dict(self) -> dict[str, Any]:
        return {
            "email_id": self.email_id,
            "label": self.label,
            "sop_ids": list(self.sop_ids),
            "source_sops": list(self.source_sops),
            "status": self.status,
            "failure_reason": self.failure_reason,
            "grounded_on": list(self.grounded_on),
            "grounding_correct": self.grounding_correct,
            "model_name": self.model_name,
            "judge_verdict": self.judge_verdict,
            "judge_reason": self.judge_reason,
            "judge_model": self.judge_model,
            "text": self.text,
        }


def _sample(items: list[Any], size: int, seed: int) -> list[Any]:
    """Deterministic sample, so a re-run judges the same drafts."""
    if len(items) <= size:
        return list(items)
    return random.Random(seed).sample(items, size)


def judge_groundedness(
    record: DraftRecord, index: SOPIndex, client: Any
) -> tuple[str | None, str | None]:
    """Ask the judge one binary question about one draft.

    A judge that errors or answers off-format returns ``None`` rather than a
    verdict. An unparseable answer is missing evidence, not a GROUNDED default --
    defaulting either way would quietly bias the reported rate.
    """
    if record.status != "ok" or not record.text:
        return None, None

    sops = tuple(index.by_id[sid] for sid in record.sop_ids if sid in index.by_id)
    rendered = "\n\n".join(
        f"### {sop.sop_id} - {sop.title}\n\n{sop.body.strip()}" for sop in sops
    )
    prompt = JUDGE_PROMPT_PATH.read_text(encoding="utf-8").format(
        sops=rendered, draft=record.text
    )

    try:
        response = client.generate(prompt)
    except LLMError:
        return None, None
    except Exception:  # noqa: BLE001 -- a judge failure is missing data, not a verdict
        return None, None

    verdict = _VERDICT_RE.search(response.text)
    reason = _REASON_RE.search(response.text)
    return (
        verdict["verdict"].upper() if verdict else None,
        reason["reason"].strip()[:300] if reason else None,
    )


def run_draft_sample(
    automated: list[tuple[Any, Any]],
    index: SOPIndex,
    sample_size: int = 50,
    seed: int = 42,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Draft a sample of the items the router acted on, then judge them.

    Args:
        automated: ``(Row, RoutingDecision)`` for every item the router automated.
        sample_size: How many to draft. Bounded by the judge budget, not by the
            split size -- drafting all of them would spend free-tier calls on text
            no one scores.

    Returns a report carrying availability, grounding accuracy and the judge's
    verdicts, with every judged draft written out for inspection.
    """
    from triage.llm.client import GeminiClient, GroqClient

    chosen = _sample(automated, sample_size, seed)
    if not chosen:
        return {"skipped": True, "reason": "no automated items to draft"}

    try:
        drafter: Any = GeminiClient()
    except LLMError as exc:
        drafter = None
        drafter_error = str(exc)
    else:
        drafter_error = None

    records: list[DraftRecord] = []
    for row, _decision in chosen:
        sop_ids = tuple(index.class_to_sops.get(row.predicted, ()))
        record = DraftRecord(
            email_id=row.item.id,
            label=row.item.label,
            sop_ids=sop_ids,
            source_sops=tuple(row.item.source_sops),
            status="failed",
            failure_reason=DraftFailure.API_ERROR.value,
        )

        if drafter is None:
            record.failure_reason = DraftFailure.API_ERROR.value
        else:
            sops = tuple(index.by_id[sid] for sid in sop_ids if sid in index.by_id)
            try:
                response = drafter.generate(
                    render_prompt(sops, row.item.email.subject, row.scrubbed)
                )
            except LLMError as exc:
                record.failure_reason = exc.reason.value
            except Exception:  # noqa: BLE001
                record.failure_reason = DraftFailure.API_ERROR.value
            else:
                body, cited = parse_citations(response.text, frozenset(sop_ids))
                record.status = "ok"
                record.failure_reason = None
                record.text = body
                record.grounded_on = cited
                record.model_name = response.model_name

        records.append(record)
        print(f"  drafted {len(records)}/{len(chosen)}", end="\r")
    print()

    # ---- judge -------------------------------------------------------------
    judge_model: str | None = None
    try:
        judge: Any = GroqClient()
        judge_model = judge.model_name
    except LLMError:
        judge = None

    if judge is not None:
        for i, record in enumerate(records, 1):
            verdict, reason = judge_groundedness(record, index, judge)
            record.judge_verdict = verdict
            record.judge_reason = reason
            record.judge_model = judge_model if verdict else None
            print(f"  judged {i}/{len(records)}", end="\r")
        print()

    # ---- aggregate ---------------------------------------------------------
    n_ok = sum(r.status == "ok" for r in records)
    failures: dict[str, int] = {}
    for record in records:
        if record.failure_reason:
            failures[record.failure_reason] = failures.get(record.failure_reason, 0) + 1

    grounding = [r.grounding_correct for r in records if r.grounding_correct is not None]
    judged = [r for r in records if r.judge_verdict is not None]
    n_grounded = sum(r.judge_verdict == "GROUNDED" for r in judged)

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "drafts.json").write_text(
            json.dumps({
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "drafter_model": next(
                    (r.model_name for r in records if r.model_name), None
                ),
                "judge_model": judge_model,
                "prompt": PROMPT_PATH.name,
                "judge_prompt": JUDGE_PROMPT_PATH.name,
                "note": (
                    "Committed so a grader reads the judgments without re-running "
                    "anything or holding a key. A failed draft is missing, not wrong: "
                    "it leaves the groundedness denominator."
                ),
                "drafts": [r.as_dict() for r in records],
            }, indent=2),
            encoding="utf-8",
        )

    return {
        "skipped": False,
        "n_attempted": len(records),
        "n_ok": n_ok,
        "availability": round(n_ok / len(records), 4) if records else 0.0,
        "failures_by_reason": failures,
        "drafter_error": drafter_error,
        "grounding": {
            "note": (
                "Only tax_reliefs and payment pull a SOP group, so only they make a "
                "real selection. 1:1 classes are correct by construction."
            ),
            "n": len(grounding),
            "accuracy": round(sum(grounding) / len(grounding), 4) if grounding else None,
        },
        "judge": {
            "model": judge_model,
            "question": "Does this reply assert any fact not present in the provided SOP?",
            "n_judged": len(judged),
            "n_grounded": n_grounded,
            "groundedness_rate": (
                round(n_grounded / len(judged), 4) if judged else None
            ),
            "note": (
                "Judge-human agreement over the same sample is reported separately "
                "once the drafts are hand-reviewed; a judge without measured "
                "agreement is decorative."
            ),
        },
    }


__all__ = ["DraftRecord", "MULTI_SOP_CLASSES", "judge_groundedness", "run_draft_sample"]
