"""Evaluation-only drafting and judge prompt tests."""

from __future__ import annotations

from eval.drafting import DraftRecord, judge_groundedness, render_judge_sops

from triage.llm.client import LLMResponse
from triage.sop.index import build_index


class CapturingJudge:
    model_name = "fake-judge"

    def __init__(self) -> None:
        self.prompt = ""

    def generate(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        self.prompt = prompt
        return LLMResponse(
            text="VERDICT: GROUNDED\nREASON: Every claim is supported.",
            model_name=self.model_name,
        )


def test_judge_and_human_review_receive_the_citizen_context() -> None:
    record = DraftRecord(
        email_id="email-1",
        label="filing",
        sop_ids=("SOP-FIL-001",),
        source_sops=("SOP-FIL-001",),
        status="ok",
        email_text="The citizen says their filing is already complete.",
        text="You said your filing is already complete.",
    )
    client = CapturingJudge()

    verdict, reason = judge_groundedness(record, build_index(), client)

    assert verdict == "GROUNDED"
    assert reason == "Every claim is supported."
    assert record.email_text in client.prompt
    assert record.text in client.prompt
    assert "SOP-FIL-001" in client.prompt


def test_judge_sop_rendering_removes_only_repeated_source_footnotes() -> None:
    rendered = render_judge_sops(("SOP-FIL-001",), build_index())

    assert "SOP-FIL-001" in rendered
    assert "## 2. Key facts the officer may state" in rendered
    assert "<sup>Source:" not in rendered
