"""The post-tuning smoke check records only reproducible operational metadata."""

from __future__ import annotations

import re

from eval.smoke_drafting import run_smoke

from triage.llm.client import LLMResponse, gemini_draft_settings


class CitingClient:
    model_name = "fake-gemini"

    def generate(self, prompt: str, *, temperature: float = 0.2) -> LLMResponse:
        evidence = prompt.split("--- STANDARD OPERATING PROCEDURE(S) ---", 1)[1]
        evidence = evidence.split("--- CITIZEN'S EMAIL ---", 1)[0]
        sop_id = re.search(r"SOP-[A-Z]{3}-\d{3}", evidence)
        assert sop_id is not None
        return LLMResponse(
            text=f"Please contact the appropriate agency.\nCITED: {sop_id.group(0)}",
            model_name=self.model_name,
        )


def test_smoke_records_current_config_and_a_valid_citation() -> None:
    report = run_smoke(client=CitingClient())

    assert report["status"] == "ok"
    assert report["model"] == "fake-gemini"
    assert report["drafting_config"] == gemini_draft_settings()
    assert report["valid_citation"] is True
    assert report["response_characters"] > 0
    assert "text" not in report
