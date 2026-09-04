"""Resumable judge evaluation tests."""

from __future__ import annotations

import json
from pathlib import Path

from eval.resume_judge import resume_missing_judgments

from triage.llm.client import LLMError, LLMResponse
from triage.schemas import DraftFailure
from triage.sop.index import build_index


class FakeJudge:
    model_name = "fake-judge"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text="VERDICT: GROUNDED\nREASON: Supported by the supplied SOP.",
            model_name=self.model_name,
        )


class RateLimitedJudge(FakeJudge):
    def generate(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        self.calls += 1
        raise LLMError(DraftFailure.RATE_LIMIT, "429 retry later")


def test_resume_only_retries_missing_successful_drafts(tmp_path: Path) -> None:
    drafts_path = tmp_path / "drafts.json"
    report_path = tmp_path / "drafting.json"
    base = {
        "scenario_id": "scenario-1",
        "label": "filing",
        "predicted_label": "filing",
        "route": "auto_reply",
        "confidence": 0.98,
        "email_text": "How do I file?",
        "sop_ids": ["SOP-FIL-001"],
        "source_sops": ["SOP-FIL-001"],
        "grounded_on": ["SOP-FIL-001"],
        "model_name": "fake-drafter",
        "judge_reason": None,
        "judge_model": None,
        "judge_failure_reason": None,
    }
    items = [
        {
            **base,
            "email_id": "ok-missing",
            "status": "ok",
            "failure_reason": None,
            "text": "You may file online.",
            "judge_verdict": None,
        },
        {
            **base,
            "email_id": "draft-failed",
            "status": "failed",
            "failure_reason": "timeout",
            "text": None,
            "judge_verdict": None,
        },
        {
            **base,
            "email_id": "already-judged",
            "status": "ok",
            "failure_reason": None,
            "text": "You may file online.",
            "judge_verdict": "GROUNDED",
            "judge_model": "fake-judge",
        },
        {
            **base,
            "email_id": "ok-missing-2",
            "status": "ok",
            "failure_reason": None,
            "text": "You may file online.",
            "judge_verdict": None,
        },
    ]
    drafts_path.write_text(json.dumps({"drafts": items}), encoding="utf-8")
    report_path.write_text(json.dumps({"judge": {}}), encoding="utf-8")
    client = FakeJudge()

    result = resume_missing_judgments(
        drafts_path,
        report_path,
        build_index(),
        client,
        max_items=1,
    )

    assert client.calls == 1
    assert result["attempted"] == 1
    assert result["resolved"] == 1
    assert result["remaining"] == 1
    updated = json.loads(drafts_path.read_text(encoding="utf-8"))["drafts"]
    assert updated[0]["judge_verdict"] == "GROUNDED"
    assert updated[1]["judge_verdict"] is None
    report = json.loads(report_path.read_text(encoding="utf-8"))["judge"]
    assert report["n_eligible"] == 3
    assert report["n_judged"] == 2
    assert report["availability"] == 0.6667


def test_resume_replaces_verdicts_from_a_stale_judge_model(tmp_path: Path) -> None:
    drafts_path = tmp_path / "drafts.json"
    report_path = tmp_path / "drafting.json"
    item = {
        "email_id": "stale",
        "scenario_id": "scenario-1",
        "label": "filing",
        "predicted_label": "filing",
        "route": "auto_reply",
        "confidence": 0.98,
        "email_text": "How do I file?",
        "sop_ids": ["SOP-FIL-001"],
        "source_sops": ["SOP-FIL-001"],
        "status": "ok",
        "failure_reason": None,
        "grounded_on": ["SOP-FIL-001"],
        "model_name": "fake-drafter",
        "text": "You may file online.",
        "judge_verdict": "UNGROUNDED",
        "judge_reason": "Old result.",
        "judge_model": "old-judge",
        "judge_failure_reason": None,
    }
    drafts_path.write_text(json.dumps({"drafts": [item]}), encoding="utf-8")
    report_path.write_text(json.dumps({"judge": {}}), encoding="utf-8")
    client = FakeJudge()

    result = resume_missing_judgments(
        drafts_path,
        report_path,
        build_index(),
        client,
    )

    assert result["resolved"] == 1
    updated = json.loads(drafts_path.read_text(encoding="utf-8"))
    assert updated["judge_model"] == "fake-judge"
    assert updated["drafts"][0]["judge_verdict"] == "GROUNDED"
    assert updated["drafts"][0]["judge_model"] == "fake-judge"


def test_resume_stops_after_first_rate_limit(tmp_path: Path) -> None:
    drafts_path = tmp_path / "drafts.json"
    report_path = tmp_path / "drafting.json"
    items = [
        {
            "email_id": f"missing-{index}",
            "scenario_id": "scenario-1",
            "label": "filing",
            "predicted_label": "filing",
            "route": "auto_reply",
            "confidence": 0.98,
            "email_text": "How do I file?",
            "sop_ids": ["SOP-FIL-001"],
            "source_sops": ["SOP-FIL-001"],
            "status": "ok",
            "failure_reason": None,
            "grounded_on": ["SOP-FIL-001"],
            "model_name": "fake-drafter",
            "text": "You may file online.",
            "judge_verdict": None,
            "judge_reason": None,
            "judge_model": None,
            "judge_failure_reason": None,
        }
        for index in range(3)
    ]
    drafts_path.write_text(json.dumps({"drafts": items}), encoding="utf-8")
    report_path.write_text(json.dumps({"judge": {}}), encoding="utf-8")
    client = RateLimitedJudge()

    result = resume_missing_judgments(
        drafts_path,
        report_path,
        build_index(),
        client,
    )

    assert client.calls == 1
    assert result["attempted"] == 1
    assert result["resolved"] == 0
    assert result["remaining"] == 3
