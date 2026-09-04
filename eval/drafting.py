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
fact unsupported by the SOP or not clearly attributed to the citizen?* Narrow
question, binary outcome, and a blind judge-human agreement workflow, which is what
makes an LLM judge defensible once the human labels exist rather than decorative.
Groq is the primary judge: free, fast, and a different model family from the drafter,
because a model must not be scored on its own output (S6.4).

**Judge outputs are committed** with each judge's model identifier and date, so a
grader reads the judgments without re-running anything or holding a key.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from triage.llm.client import LLMError, classify_error, gemini_draft_settings
from triage.nodes.draft import PROMPT_PATH, draft_node
from triage.schemas import DraftFailure, ScrubRecord, TriageState
from triage.sop.index import SOPIndex

#: Classes whose SOP lookup returns more than one document, so the drafter makes a
#: real selection. Grounding accuracy is meaningful only here.
MULTI_SOP_CLASSES: Final[frozenset[str]] = frozenset({"tax_reliefs", "payment"})

_VERDICT_RE: Final[re.Pattern[str]] = re.compile(
    r"VERDICT:\s*(?P<verdict>GROUNDED|UNGROUNDED)", re.IGNORECASE
)
_REASON_RE: Final[re.Pattern[str]] = re.compile(r"REASON:\s*(?P<reason>.+)", re.IGNORECASE)

# Source URLs document provenance but are not rules the judge can use. Removing
# their repeated HTML footnotes keeps the complete normative SOP evidence while
# avoiding needless input tokens on the free-tier judge.
_SOURCE_FOOTNOTE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?im)^[ \t]*<sup>Source:\s*https?://[^<\r\n]+</sup>[ \t]*\r?\n?"
)

DEFAULT_JUDGE_DELAY_SECONDS: Final[float] = 12.0

JUDGE_PROMPT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1]
    / "src" / "triage" / "llm" / "prompts" / "judge_groundedness.v2.txt"
)


@dataclass
class DraftRecord:
    """One sampled draft and everything measured about it."""

    email_id: str
    label: str
    sop_ids: tuple[str, ...]
    source_sops: tuple[str, ...]
    status: str
    scenario_id: str = ""
    predicted_label: str = ""
    route: str = ""
    confidence: float | None = None
    email_text: str = ""
    text: str | None = None
    failure_reason: str | None = None
    grounded_on: tuple[str, ...] = ()
    model_name: str | None = None
    judge_verdict: str | None = None
    judge_reason: str | None = None
    judge_model: str | None = None
    judge_failure_reason: str | None = None

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
            "scenario_id": self.scenario_id,
            "label": self.label,
            "predicted_label": self.predicted_label,
            "route": self.route,
            "confidence": self.confidence,
            "email_text": self.email_text,
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
            "judge_failure_reason": self.judge_failure_reason,
            "text": self.text,
        }


@dataclass(frozen=True)
class JudgeResult:
    """One judge attempt, including why a verdict may be missing."""

    verdict: str | None
    reason: str | None
    failure_reason: str | None


def _sample(items: list[Any], size: int, seed: int) -> list[Any]:
    """Deterministic sample, so a re-run judges the same drafts."""
    if len(items) <= size:
        return list(items)
    return random.Random(seed).sample(items, size)


def render_judge_sops(sop_ids: tuple[str, ...], index: SOPIndex) -> str:
    """Render the exact SOP evidence shared by the LLM and human reviewers."""
    sections: list[str] = []
    for sop_id in sop_ids:
        if sop_id not in index.by_id:
            continue
        sop = index.by_id[sop_id]
        body = _SOURCE_FOOTNOTE_RE.sub("", sop.body).strip()
        sections.append(f"### {sop.sop_id} - {sop.title}\n\n{body}")
    return "\n\n".join(sections)


def judge_groundedness_detailed(
    record: DraftRecord, index: SOPIndex, client: Any
) -> JudgeResult:
    """Ask the judge one binary question about one draft.

    A judge that errors or answers off-format returns ``None`` rather than a
    verdict. An unparseable answer is missing evidence, not a GROUNDED default --
    defaulting either way would quietly bias the reported rate.
    """
    if record.status != "ok" or not record.text:
        return JudgeResult(None, None, None)

    rendered = render_judge_sops(record.sop_ids, index)
    prompt = JUDGE_PROMPT_PATH.read_text(encoding="utf-8").format(
        email=record.email_text, sops=rendered, draft=record.text
    )

    try:
        response = client.generate(prompt)
    except LLMError as exc:
        return JudgeResult(None, None, exc.reason.value)
    except Exception as exc:  # noqa: BLE001 -- report missing judge data by category
        return JudgeResult(None, None, classify_error(exc).value)

    verdict = _VERDICT_RE.search(response.text)
    reason = _REASON_RE.search(response.text)
    return JudgeResult(
        verdict=verdict["verdict"].upper() if verdict else None,
        reason=reason["reason"].strip()[:300] if reason else None,
        failure_reason=None if verdict else "unparseable_response",
    )


def judge_groundedness(
    record: DraftRecord, index: SOPIndex, client: Any
) -> tuple[str | None, str | None]:
    """Compatibility view returning only the parsed verdict and reason."""
    result = judge_groundedness_detailed(record, index, client)
    return result.verdict, result.reason


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
    from triage.llm.client import GeminiClient, GroqJudgeClient

    chosen = _sample(automated, sample_size, seed)
    if not chosen:
        return {"skipped": True, "reason": "no automated items to draft"}

    try:
        drafter: Any = GeminiClient()
    except LLMError as exc:
        drafter = None
        drafter_error: str | None = str(exc)
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
            scenario_id=row.item.scenario_id,
            predicted_label=row.predicted,
            route=_decision.action.value,
            confidence=_decision.confidence,
            email_text=row.scrub.text,
            failure_reason=DraftFailure.API_ERROR.value,
        )

        if drafter is None:
            record.failure_reason = DraftFailure.API_ERROR.value
        else:
            state = TriageState(
                email=row.item.email,
                scrub=ScrubRecord(
                    text=row.scrub.text,
                    vault=dict(row.scrub.vault),
                    counts=dict(row.scrub.counts),
                ),
                sop_ids=sop_ids,
                decision=_decision,
            )
            update = draft_node(state, index, drafter)
            completed = state.model_copy(update=update).redacted()
            result = completed.draft
            assert result is not None
            record.status = result.status.value
            record.failure_reason = (
                result.failure_reason.value if result.failure_reason is not None else None
            )
            record.text = result.text
            record.grounded_on = result.grounded_on
            record.model_name = result.model_name

        records.append(record)
        print(f"  drafted {len(records)}/{len(chosen)}", end="\r")
    print()

    # ---- judge -------------------------------------------------------------
    judge_model: str | None = None
    try:
        judge: Any = GroqJudgeClient()
        judge_model = judge.model_name
    except LLMError:
        judge = None

    if judge is not None:
        eligible_records = [
            record for record in records if record.status == "ok" and record.text
        ]
        for i, record in enumerate(eligible_records, 1):
            if i > 1:
                time.sleep(DEFAULT_JUDGE_DELAY_SECONDS)
            judge_result = judge_groundedness_detailed(record, index, judge)
            record.judge_verdict = judge_result.verdict
            record.judge_reason = judge_result.reason
            record.judge_model = judge_model if judge_result.verdict else None
            record.judge_failure_reason = judge_result.failure_reason
            print(f"  judged {i}/{len(eligible_records)}", end="\r")
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
    judge_failures = Counter(
        r.judge_failure_reason
        for r in records
        if r.status == "ok" and r.judge_verdict is None and r.judge_failure_reason
    )
    sample_by_route = Counter(r.route for r in records)
    sample_by_label = Counter(r.predicted_label for r in records)
    population_by_route = Counter(decision.action.value for _, decision in automated)
    population_by_label = Counter(row.predicted for row, _ in automated)
    judge_by_route = {
        route: {
            "n_judged": len(route_records),
            "n_grounded": sum(
                record.judge_verdict == "GROUNDED" for record in route_records
            ),
        }
        for route in sorted(sample_by_route)
        if (route_records := [record for record in judged if record.route == route])
    }

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "drafts.json").write_text(
            json.dumps({
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "drafter_model": next(
                    (r.model_name for r in records if r.model_name), None
                ),
                "drafting_config": gemini_draft_settings(),
                "judge_model": judge_model,
                "judge_version": getattr(judge, "model_version", None),
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
        "drafting_config": gemini_draft_settings(),
        "sample": {
            "method": "deterministic simple random sample without replacement",
            "seed": seed,
            "population_n": len(automated),
            "sample_n": len(records),
            "population_by_route": dict(sorted(population_by_route.items())),
            "sample_by_route": dict(sorted(sample_by_route.items())),
            "population_by_predicted_label": dict(sorted(population_by_label.items())),
            "sample_by_predicted_label": dict(sorted(sample_by_label.items())),
        },
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
            "version": getattr(judge, "model_version", None),
            "question": (
                "Does this reply assert any fact unsupported by the SOP or not "
                "clearly attributed to the citizen?"
            ),
            "n_eligible": n_ok,
            "n_judged": len(judged),
            "availability": round(len(judged) / n_ok, 4) if n_ok else None,
            "failures_by_reason": dict(sorted(judge_failures.items())),
            "n_grounded": n_grounded,
            "groundedness_rate": (
                round(n_grounded / len(judged), 4) if judged else None
            ),
            "by_route": judge_by_route,
            "note": (
                "Judge-human agreement over the same sample is reported separately "
                "once the drafts are hand-reviewed; a judge without measured "
                "agreement is decorative."
            ),
        },
    }


__all__ = [
    "DraftRecord",
    "DEFAULT_JUDGE_DELAY_SECONDS",
    "JudgeResult",
    "MULTI_SOP_CLASSES",
    "judge_groundedness",
    "judge_groundedness_detailed",
    "render_judge_sops",
    "run_draft_sample",
]
