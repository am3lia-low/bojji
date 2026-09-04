"""One-call operational smoke check for the current Gemini drafting settings.

This is deliberately separate from the reviewed 50-item quality evaluation. It
checks that the current runtime configuration can produce and cite one grounded
draft without overwriting the drafts that the human reviewer rated.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from triage.env import load_env  # noqa: E402

load_env()

from eval.dataset import split  # noqa: E402
from triage.llm.client import (  # noqa: E402
    GeminiClient,
    LLMClient,
    LLMError,
    gemini_draft_settings,
)
from triage.nodes.draft import parse_citations, render_prompt  # noqa: E402
from triage.pii.scrubber import Scrubber  # noqa: E402
from triage.sop.index import build_index  # noqa: E402

DEFAULT_EMAIL_ID: Final[str] = "OOSA-GST-001-020"
DEFAULT_OUTPUT: Final[Path] = ROOT / "eval" / "results" / "drafting_runtime_smoke.json"


def run_smoke(
    *,
    email_id: str = DEFAULT_EMAIL_ID,
    client: LLMClient | None = None,
) -> dict[str, Any]:
    """Generate one synthetic, SOP-grounded draft and return metadata only."""
    try:
        item = next(row for row in split("test") if row.email.id == email_id)
    except StopIteration as exc:
        raise ValueError(f"email id is not in the test split: {email_id}") from exc

    if not item.source_sops:
        raise ValueError(f"email has no source SOPs: {email_id}")

    scrubbed = Scrubber().scrub(item.email.text)
    index = build_index()
    sops = tuple(index.by_id[sop_id] for sop_id in item.source_sops)
    prompt = render_prompt(sops, scrubbed.text)
    live_client = client

    started = time.perf_counter()
    try:
        if live_client is None:
            live_client = GeminiClient()
        response = live_client.generate(prompt)
    except LLMError as exc:
        return {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "purpose": "post-latency-tuning operational smoke check",
            "sample_size": 1,
            "email_id": email_id,
            "synthetic_email": True,
            "model": getattr(live_client, "model_name", None),
            "drafting_config": gemini_draft_settings(),
            "status": "failed",
            "failure_reason": exc.reason.value,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            "response_characters": 0,
            "valid_citation": False,
            "redacted_values": len(scrubbed.vault),
        }

    body, citations = parse_citations(response.text, frozenset(item.source_sops))
    valid_citation = bool(set(citations) & set(item.source_sops))
    status = "ok" if body and valid_citation else "failed"
    failure_reason = None if status == "ok" else "missing_body_or_valid_citation"
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "purpose": "post-latency-tuning operational smoke check",
        "sample_size": 1,
        "email_id": email_id,
        "synthetic_email": True,
        "model": response.model_name,
        "drafting_config": gemini_draft_settings(),
        "status": status,
        "failure_reason": failure_reason,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "response_characters": len(body),
        "valid_citation": valid_citation,
        "redacted_values": len(scrubbed.vault),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email-id", default=DEFAULT_EMAIL_ID)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = run_smoke(email_id=args.email_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
