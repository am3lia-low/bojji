"""Resume only missing groundedness judgments without redrafting anything."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.drafting import (  # noqa: E402
    DEFAULT_JUDGE_DELAY_SECONDS,
    DraftRecord,
    judge_groundedness_detailed,
)
from triage.env import load_env  # noqa: E402
from triage.llm.client import GroqJudgeClient  # noqa: E402
from triage.sop.index import SOPIndex, build_index  # noqa: E402

DEFAULT_DRAFTS = ROOT / "eval" / "results" / "drafts.json"
DEFAULT_REPORT = ROOT / "eval" / "results" / "drafting.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _record(item: dict[str, Any]) -> DraftRecord:
    return DraftRecord(
        email_id=str(item["email_id"]),
        label=str(item["label"]),
        sop_ids=tuple(item.get("sop_ids") or ()),
        source_sops=tuple(item.get("source_sops") or ()),
        status=str(item["status"]),
        scenario_id=str(item.get("scenario_id") or ""),
        predicted_label=str(item.get("predicted_label") or ""),
        route=str(item.get("route") or ""),
        confidence=item.get("confidence"),
        email_text=str(item.get("email_text") or ""),
        text=item.get("text"),
        failure_reason=item.get("failure_reason"),
        grounded_on=tuple(item.get("grounded_on") or ()),
        model_name=item.get("model_name"),
        judge_verdict=item.get("judge_verdict"),
        judge_reason=item.get("judge_reason"),
        judge_model=item.get("judge_model"),
        judge_failure_reason=item.get("judge_failure_reason"),
    )


def _has_current_judgment(item: dict[str, Any], judge_model: str) -> bool:
    return (
        item.get("judge_verdict") in {"GROUNDED", "UNGROUNDED"}
        and item.get("judge_model") == judge_model
    )


def _refresh_report(
    report: dict[str, Any],
    items: list[dict[str, Any]],
    judge_model: str,
    judge_version: str | None,
) -> None:
    successful = [item for item in items if item.get("status") == "ok"]
    judged = [item for item in successful if _has_current_judgment(item, judge_model)]
    failures = Counter(
        str(
            item.get("judge_failure_reason")
            or ("stale_model" if item.get("judge_verdict") else "unknown")
        )
        for item in successful
        if item not in judged
    )
    routes = sorted({str(item.get("route") or "unknown") for item in judged})
    by_route = {
        route: {
            "n_judged": len(route_items),
            "n_grounded": sum(
                item.get("judge_verdict") == "GROUNDED" for item in route_items
            ),
        }
        for route in routes
        if (route_items := [item for item in judged if item.get("route") == route])
    }
    judge = report.setdefault("judge", {})
    judge.update({
        "model": judge_model,
        "version": judge_version,
        "n_eligible": len(successful),
        "n_judged": len(judged),
        "availability": round(len(judged) / len(successful), 4) if successful else None,
        "failures_by_reason": dict(sorted(failures.items())),
        "n_grounded": sum(item.get("judge_verdict") == "GROUNDED" for item in judged),
        "groundedness_rate": (
            round(
                sum(item.get("judge_verdict") == "GROUNDED" for item in judged)
                / len(judged),
                4,
            )
            if judged
            else None
        ),
        "by_route": by_route,
        "last_resumed_at": datetime.now(UTC).isoformat(timespec="seconds"),
    })


def resume_missing_judgments(
    drafts_path: Path,
    report_path: Path,
    index: SOPIndex,
    client: Any,
    *,
    max_items: int | None = None,
    delay_seconds: float = 0.0,
    rerun_all: bool = False,
) -> dict[str, Any]:
    """Attempt missing or stale judgments and persist progress after every item."""
    payload = json.loads(drafts_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    items = list(payload.get("drafts") or ())
    missing_or_stale = [
        item
        for item in items
        if item.get("status") == "ok"
        and (rerun_all or not _has_current_judgment(item, client.model_name))
    ]
    if max_items is not None:
        if max_items < 1:
            raise ValueError("max_items must be at least 1")
        missing_or_stale = missing_or_stale[:max_items]

    payload["judge_model"] = client.model_name
    payload["judge_version"] = getattr(client, "model_version", None)
    attempted_items: list[dict[str, Any]] = []
    for position, item in enumerate(missing_or_stale, 1):
        if position > 1 and delay_seconds > 0:
            time.sleep(delay_seconds)
        attempted_items.append(item)
        result = judge_groundedness_detailed(_record(item), index, client)
        item["judge_verdict"] = result.verdict
        item["judge_reason"] = result.reason
        item["judge_model"] = client.model_name if result.verdict else None
        item["judge_failure_reason"] = result.failure_reason
        _write_json_atomic(drafts_path, payload)
        print(f"  resumed judge {position}/{len(missing_or_stale)}")
        if result.failure_reason == "rate_limit":
            # The provider's rolling token window can be much longer than a
            # per-request backoff. Stop after the first 429 so the remaining
            # items stay resumable instead of spending requests that cannot pass.
            break

    _refresh_report(
        report,
        items,
        client.model_name,
        getattr(client, "model_version", None),
    )
    _write_json_atomic(report_path, report)
    remaining = sum(
        item.get("status") == "ok"
        and not _has_current_judgment(item, client.model_name)
        for item in items
    )
    attempted_remaining = sum(
        not _has_current_judgment(item, client.model_name)
        for item in attempted_items
    )
    return {
        "attempted": len(attempted_items),
        "resolved": len(attempted_items) - attempted_remaining,
        "remaining": remaining,
        "judge": report["judge"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drafts", type=Path, default=DEFAULT_DRAFTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="cap attempts, useful when a free-tier judge has a rolling TPM limit",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_JUDGE_DELAY_SECONDS,
        help="pause between calls to stay below the free-tier rolling TPM limit",
    )
    parser.add_argument(
        "--rerun-all",
        action="store_true",
        help="replace even current-model verdicts; stale-model verdicts rerun automatically",
    )
    args = parser.parse_args()
    load_env()
    result = resume_missing_judgments(
        args.drafts,
        args.report,
        build_index(),
        GroqJudgeClient(),
        max_items=args.max_items,
        delay_seconds=args.delay_seconds,
        rerun_all=args.rerun_all,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["remaining"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["resume_missing_judgments"]
