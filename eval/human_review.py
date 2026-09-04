"""Prepare blind human review sheets and score judge-human agreement.

This is deliberately separate from ``run_eval.py``. Draft generation and judging
consume API quota; human annotation happens later and must never trigger another
provider call. The workflow is:

1. ``prepare`` converts committed successful drafts into a blinded CSV. The sheet
   contains the same redacted email, SOPs, and draft seen by the judge, but omits
   the judge verdict, model label, confidence, and ground truth.
2. Reviewers fill fixed categorical fields independently.
3. ``score`` joins ratings to the sealed manifest, reports inter-human reliability,
   and compares the groundedness judge with the resolved human reference labels.

Human labels are never inferred or generated here. Missing labels and unresolved
reviewer disagreements keep the report visibly incomplete.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.drafting import render_judge_sops  # noqa: E402
from triage.sop.index import SOPIndex, build_index  # noqa: E402

DEFAULT_DRAFTS: Final[Path] = ROOT / "eval" / "results" / "drafts.json"
DEFAULT_REVIEW_DIR: Final[Path] = ROOT / "eval" / "human_review"
DEFAULT_MANIFEST: Final[Path] = DEFAULT_REVIEW_DIR / "manifest.json"
DEFAULT_REPORT: Final[Path] = ROOT / "eval" / "results" / "judge_human_agreement.json"
DEFAULT_MARKDOWN_REPORT: Final[Path] = (
    ROOT / "eval" / "results" / "HUMAN_EVAL_REPORT.md"
)

GROUNDING: Final[frozenset[str]] = frozenset({"GROUNDED", "UNGROUNDED", "UNSURE"})
PASS_FAIL: Final[frozenset[str]] = frozenset({"PASS", "FAIL", "UNSURE"})
ACCEPTANCE: Final[frozenset[str]] = frozenset({"ACCEPT", "REJECT", "UNSURE"})
REVIEW_FIELDS: Final[dict[str, frozenset[str]]] = {
    "groundedness": GROUNDING,
    "correct_next_step": PASS_FAIL,
    "safety_privacy": PASS_FAIL,
    "completeness": PASS_FAIL,
    "tone": PASS_FAIL,
    "overall_acceptability": ACCEPTANCE,
}
REVIEW_COLUMNS: Final[tuple[str, ...]] = (
    "review_order",
    "item_id",
    "evidence_sha256",
    "citizen_email_redacted",
    "sop_ids",
    "sop_text",
    "draft_redacted",
    *REVIEW_FIELDS,
    "review_notes",
    "reviewer_id",
)


@dataclass(frozen=True)
class Rating:
    """One complete human rating row."""

    item_id: str
    reviewer_id: str
    values: dict[str, str]
    notes: str


def _spreadsheet_safe(value: str) -> str:
    """Prevent imported citizen text from becoming a spreadsheet formula."""
    return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value


def evidence_hash(email: str, sop_ids: str, sop_text: str, draft: str) -> str:
    """Hash the exact evidence cells a reviewer sees."""
    payload = json.dumps(
        {
            "citizen_email_redacted": email,
            "sop_ids": sop_ids,
            "sop_text": sop_text,
            "draft_redacted": draft,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _review_evidence(draft: dict[str, Any], index: SOPIndex) -> dict[str, str]:
    sop_ids = tuple(str(value) for value in draft.get("sop_ids") or ())
    rendered_sops = render_judge_sops(sop_ids, index)
    evidence = {
        "citizen_email_redacted": _spreadsheet_safe(str(draft.get("email_text", ""))),
        "sop_ids": "; ".join(sop_ids),
        "sop_text": _spreadsheet_safe(rendered_sops),
        "draft_redacted": _spreadsheet_safe(str(draft.get("text", ""))),
    }
    evidence["evidence_sha256"] = evidence_hash(
        evidence["citizen_email_redacted"],
        evidence["sop_ids"],
        evidence["sop_text"],
        evidence["draft_redacted"],
    )
    return evidence


def _load_drafts(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(
            f"no draft records at {path}; run python eval/run_eval.py first"
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    successful = [
        draft
        for draft in document.get("drafts", [])
        if draft.get("status") == "ok" and draft.get("text")
    ]
    if not successful:
        raise ValueError(f"{path} contains no successful drafts to review")
    return document, successful


def _new_manifest(
    drafts_path: Path,
    draft_document: dict[str, Any],
    drafts: list[dict[str, Any]],
    *,
    seed: int,
    index: SOPIndex,
) -> dict[str, Any]:
    ordered = sorted(drafts, key=lambda draft: str(draft["email_id"]))
    item_ids = [f"JH-{index:03d}" for index in range(1, len(ordered) + 1)]
    overlap_target = min(len(ordered), max(20, math.ceil(0.30 * len(ordered))))
    overlap_ids = set(random.Random(seed).sample(item_ids, overlap_target))

    try:
        source_path = drafts_path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        source_path = drafts_path.name

    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": {
            "path": source_path,
            "sha256": hashlib.sha256(drafts_path.read_bytes()).hexdigest(),
            "drafter_model": draft_document.get("drafter_model"),
            "judge_model": draft_document.get("judge_model"),
            "judge_version": draft_document.get("judge_version"),
            "draft_prompt": draft_document.get("prompt"),
            "judge_prompt": draft_document.get("judge_prompt"),
        },
        "protocol": {
            "primary_review": "all successful drafts",
            "double_review_target": overlap_target,
            "double_review_rule": "max(20 items, 30% of successful drafts), capped at n",
            "selection_seed": seed,
            "blinding": (
                "Reviewer sheets omit judge verdicts, model predictions, confidence, "
                "ground-truth labels, and source email IDs."
            ),
        },
        "items": [
            {
                "item_id": item_id,
                "email_id": draft["email_id"],
                "scenario_id": draft.get("scenario_id", ""),
                "true_label": draft.get("label", ""),
                "predicted_label": draft.get("predicted_label", draft.get("label", "")),
                "route": draft.get("route", ""),
                "confidence": draft.get("confidence"),
                "sop_ids": list(draft.get("sop_ids") or ()),
                "judge_verdict": draft.get("judge_verdict"),
                "judge_reason": draft.get("judge_reason"),
                "judge_model": draft.get("judge_model"),
                "evidence_sha256": _review_evidence(draft, index)["evidence_sha256"],
                "double_review": item_id in overlap_ids,
            }
            for item_id, draft in zip(item_ids, ordered, strict=True)
        ],
    }


def prepare_review(
    drafts_path: Path,
    manifest_path: Path,
    output_path: Path,
    *,
    reviewer_id: str,
    seed: int = 42,
    overlap_only: bool = False,
) -> dict[str, int | str]:
    """Write a blinded, randomised reviewer CSV and a sealed join manifest."""
    if not reviewer_id.strip():
        raise ValueError("reviewer_id must not be blank")

    draft_document, drafts = _load_drafts(drafts_path)
    index = build_index()
    source_hash = hashlib.sha256(drafts_path.read_bytes()).hexdigest()
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("source", {}).get("sha256") != source_hash:
            raise ValueError(
                "drafts.json changed after the review manifest was created; use a "
                "new manifest path so old ratings cannot be joined to new drafts"
            )
    else:
        manifest = _new_manifest(
            drafts_path, draft_document, drafts, seed=seed, index=index
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    draft_by_email = {str(draft["email_id"]): draft for draft in drafts}
    selected = [
        item
        for item in manifest["items"]
        if not overlap_only or item.get("double_review") is True
    ]
    stable_reviewer_seed = int.from_bytes(
        hashlib.sha256(reviewer_id.encode("utf-8")).digest()[:4], "big"
    )
    random.Random(seed + stable_reviewer_seed).shuffle(selected)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for review_order, item in enumerate(selected, 1):
            draft = draft_by_email[str(item["email_id"])]
            evidence = _review_evidence(draft, index)
            if evidence["evidence_sha256"] != item.get("evidence_sha256"):
                raise ValueError(f"evidence changed for {item['item_id']}")
            row = {
                "review_order": review_order,
                "item_id": item["item_id"],
                **evidence,
                "review_notes": "",
                "reviewer_id": reviewer_id,
            }
            row.update(dict.fromkeys(REVIEW_FIELDS, ""))
            writer.writerow(row)

    return {
        "reviewer_id": reviewer_id,
        "n_items": len(selected),
        "output": str(output_path),
        "manifest": str(manifest_path),
    }


def sync_manifest_judgments(
    drafts_path: Path,
    manifest_path: Path,
) -> dict[str, int | str]:
    """Refresh hidden judge fields without changing reviewer evidence or IDs."""
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)

    draft_document, drafts = _load_drafts(drafts_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = build_index()
    draft_by_email = {str(draft["email_id"]): draft for draft in drafts}

    for item in manifest.get("items", []):
        email_id = str(item.get("email_id", ""))
        if email_id not in draft_by_email:
            raise ValueError(f"manifest email is missing from drafts.json: {email_id}")
        draft = draft_by_email[email_id]
        current_hash = _review_evidence(draft, index)["evidence_sha256"]
        if current_hash != item.get("evidence_sha256"):
            raise ValueError(
                f"review evidence changed for {item.get('item_id')}; existing ratings "
                "cannot be joined safely"
            )
        item["judge_verdict"] = draft.get("judge_verdict")
        item["judge_reason"] = draft.get("judge_reason")
        item["judge_model"] = draft.get("judge_model")

    source = manifest.setdefault("source", {})
    source["sha256"] = hashlib.sha256(drafts_path.read_bytes()).hexdigest()
    source["drafter_model"] = draft_document.get("drafter_model")
    source["judge_model"] = draft_document.get("judge_model")
    source["judge_version"] = draft_document.get("judge_version")
    manifest["judge_synced_at"] = datetime.now(UTC).isoformat(timespec="seconds")

    temporary = manifest_path.with_suffix(f"{manifest_path.suffix}.tmp")
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(temporary, manifest_path)
    judged = sum(
        item.get("judge_verdict") in {"GROUNDED", "UNGROUNDED"}
        for item in manifest.get("items", [])
    )
    return {
        "n_items": len(manifest.get("items", [])),
        "n_judged": judged,
        "judge_model": str(source.get("judge_model") or ""),
        "manifest": str(manifest_path),
    }


def _load_ratings(
    paths: list[Path],
    evidence_by_item: dict[str, str],
    *,
    require_notes: bool = True,
    allow_unsure: bool = True,
    normalize_overall_pass: bool = False,
) -> list[Rating]:
    ratings: list[Rating] = []
    seen: set[tuple[str, str]] = set()
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = set(REVIEW_COLUMNS) - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"{path} is missing columns: {sorted(missing)}")
            for line_number, row in enumerate(reader, 2):
                raw_values = {
                    field: str(row.get(field, "")).strip().upper()
                    for field in REVIEW_FIELDS
                }
                if (
                    normalize_overall_pass
                    and raw_values["overall_acceptability"] == "PASS"
                ):
                    raw_values["overall_acceptability"] = "ACCEPT"
                if not any(raw_values.values()):
                    continue
                item_id = str(row.get("item_id", "")).strip()
                reviewer_id = str(row.get("reviewer_id", "")).strip()
                if item_id not in evidence_by_item:
                    raise ValueError(f"{path}:{line_number}: unknown item_id {item_id!r}")
                supplied_hash = str(row.get("evidence_sha256", "")).strip()
                calculated_hash = evidence_hash(
                    str(row.get("citizen_email_redacted", "")),
                    str(row.get("sop_ids", "")),
                    str(row.get("sop_text", "")),
                    str(row.get("draft_redacted", "")),
                )
                if supplied_hash != evidence_by_item[item_id] or calculated_hash != supplied_hash:
                    raise ValueError(
                        f"{path}:{line_number}: review evidence changed for {item_id}"
                    )
                if not reviewer_id:
                    raise ValueError(f"{path}:{line_number}: reviewer_id is blank")
                key = (reviewer_id, item_id)
                if key in seen:
                    raise ValueError(
                        f"duplicate rating for reviewer {reviewer_id!r}, item {item_id!r}"
                    )
                for field, allowed in REVIEW_FIELDS.items():
                    if raw_values[field] not in allowed:
                        raise ValueError(
                            f"{path}:{line_number}: {field} must be one of "
                            f"{sorted(allowed)}, got {raw_values[field]!r}"
                        )
                if not allow_unsure and "UNSURE" in raw_values.values():
                    raise ValueError(
                        f"{path}:{line_number}: adjudication must resolve every "
                        "field without UNSURE"
                    )
                notes = str(row.get("review_notes", "")).strip()
                flagged = (
                    raw_values["groundedness"] != "GROUNDED"
                    or raw_values["safety_privacy"] != "PASS"
                    or raw_values["overall_acceptability"] != "ACCEPT"
                    or any(value in {"FAIL", "UNSURE"} for value in raw_values.values())
                )
                if require_notes and flagged and not notes:
                    raise ValueError(
                        f"{path}:{line_number}: review_notes are required for a "
                        "failure, rejection, or unsure verdict"
                    )
                if (
                    raw_values["groundedness"] == "UNGROUNDED"
                    or raw_values["safety_privacy"] == "FAIL"
                ) and raw_values["overall_acceptability"] != "REJECT":
                    raise ValueError(
                        f"{path}:{line_number}: an ungrounded or unsafe draft must "
                        "be REJECTED overall"
                    )
                ratings.append(Rating(item_id, reviewer_id, raw_values, notes))
                seen.add(key)
    return ratings


def _cohen_kappa(left: list[str], right: list[str], labels: tuple[str, ...]) -> float | None:
    if len(left) != len(right):
        raise ValueError("kappa inputs must have equal length")
    if not left:
        return None
    if len(set(left)) < 2 or len(set(right)) < 2:
        return None
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts, right_counts = Counter(left), Counter(right)
    expected = sum(
        left_counts[label] / len(left) * right_counts[label] / len(right)
        for label in labels
    )
    if expected == 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def _wilson(successes: int, total: int) -> dict[str, float | int | None]:
    """95% Wilson interval for a proportion, including small denominators."""
    if total == 0:
        return {"successes": successes, "n": total, "rate": None, "lower": None, "upper": None}
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return {
        "successes": successes,
        "n": total,
        "rate": round(proportion, 4),
        "lower": round(max(0.0, centre - margin), 4),
        "upper": round(min(1.0, centre + margin), 4),
    }


def _agreement(left: list[str], right: list[str], labels: tuple[str, ...]) -> dict[str, Any]:
    agreed = sum(a == b for a, b in zip(left, right, strict=True))
    confusion = {
        actual: {predicted: 0 for predicted in labels}
        for actual in labels
    }
    for actual, predicted in zip(left, right, strict=True):
        confusion[actual][predicted] += 1
    return {
        **_wilson(agreed, len(left)),
        "cohen_kappa": (
            None
            if (kappa := _cohen_kappa(left, right, labels)) is None
            else round(kappa, 4)
        ),
        "confusion_rows_reference_columns_comparison": confusion,
    }


def _resolve_references(
    manifest_items: list[dict[str, Any]],
    ratings: list[Rating],
    adjudications: list[Rating],
) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]]]:
    by_item: dict[str, list[Rating]] = defaultdict(list)
    for rating in ratings:
        by_item[rating.item_id].append(rating)
    adjudicated = {rating.item_id: rating for rating in adjudications}

    references: dict[str, dict[str, str]] = {}
    unresolved: list[dict[str, Any]] = []
    for item in manifest_items:
        item_id = str(item["item_id"])
        resolved: dict[str, str] = {}
        problem_fields: list[str] = []
        for field in REVIEW_FIELDS:
            values = [rating.values[field] for rating in by_item[item_id]]
            if item_id in adjudicated:
                resolved[field] = adjudicated[item_id].values[field]
            elif not values or "UNSURE" in values or len(set(values)) > 1:
                problem_fields.append(field)
            else:
                resolved[field] = values[0]
        if problem_fields:
            unresolved.append({"item_id": item_id, "fields": problem_fields})
        else:
            references[item_id] = resolved
    return references, unresolved


def _pairwise_reliability(ratings: list[Rating]) -> list[dict[str, Any]]:
    by_reviewer: dict[str, dict[str, Rating]] = defaultdict(dict)
    for rating in ratings:
        by_reviewer[rating.reviewer_id][rating.item_id] = rating

    reports: list[dict[str, Any]] = []
    for left_id, right_id in combinations(sorted(by_reviewer), 2):
        overlap = sorted(set(by_reviewer[left_id]) & set(by_reviewer[right_id]))
        grounded_overlap = [
            item_id
            for item_id in overlap
            if by_reviewer[left_id][item_id].values["groundedness"] != "UNSURE"
            and by_reviewer[right_id][item_id].values["groundedness"] != "UNSURE"
        ]
        overall_overlap = [
            item_id
            for item_id in overlap
            if by_reviewer[left_id][item_id].values["overall_acceptability"] != "UNSURE"
            and by_reviewer[right_id][item_id].values["overall_acceptability"] != "UNSURE"
        ]
        reports.append({
            "reviewers": [left_id, right_id],
            "n_rows_overlapping": len(overlap),
            "groundedness": _agreement(
                [by_reviewer[left_id][item].values["groundedness"] for item in grounded_overlap],
                [by_reviewer[right_id][item].values["groundedness"] for item in grounded_overlap],
                ("GROUNDED", "UNGROUNDED"),
            ),
            "overall_acceptability": _agreement(
                [
                    by_reviewer[left_id][item].values["overall_acceptability"]
                    for item in overall_overlap
                ],
                [
                    by_reviewer[right_id][item].values["overall_acceptability"]
                    for item in overall_overlap
                ],
                ("ACCEPT", "REJECT"),
            ),
        })
    return reports


def _judge_agreement(
    manifest_items: list[dict[str, Any]], references: dict[str, dict[str, str]]
) -> dict[str, Any]:
    comparable = [
        item
        for item in manifest_items
        if item.get("judge_verdict") in {"GROUNDED", "UNGROUNDED"}
        and item["item_id"] in references
    ]
    human = [references[str(item["item_id"])]["groundedness"] for item in comparable]
    judge = [str(item["judge_verdict"]) for item in comparable]
    report = _agreement(human, judge, ("GROUNDED", "UNGROUNDED"))

    human_ungrounded = sum(value == "UNGROUNDED" for value in human)
    judge_ungrounded = sum(value == "UNGROUNDED" for value in judge)
    caught = sum(
        want == "UNGROUNDED" and got == "UNGROUNDED"
        for want, got in zip(human, judge, strict=True)
    )
    true_ungrounded = caught
    report.update({
        "human_ungrounded": human_ungrounded,
        "judge_ungrounded": judge_ungrounded,
        "ungrounded_recall": (
            round(caught / human_ungrounded, 4) if human_ungrounded else None
        ),
        "ungrounded_precision": (
            round(true_ungrounded / judge_ungrounded, 4) if judge_ungrounded else None
        ),
        "note": (
            "Human labels are the reference. Ungrounded recall is the safety-critical "
            "quantity: it is the share of human-identified unsupported drafts the "
            "judge also catches."
        ),
    })

    by_route: dict[str, Any] = {}
    for route in sorted({str(item.get("route", "unknown")) for item in comparable}):
        subset = [item for item in comparable if str(item.get("route", "unknown")) == route]
        route_human = [references[str(item["item_id"])]["groundedness"] for item in subset]
        route_judge = [str(item["judge_verdict"]) for item in subset]
        by_route[route] = _agreement(
            route_human, route_judge, ("GROUNDED", "UNGROUNDED")
        )
    report["by_route"] = by_route
    return report


def _display_rate(value: Any) -> str:
    return "—" if value is None else f"{float(value):.1%}"


def _display_number(value: Any) -> str:
    return "—" if value is None else f"{float(value):.3f}"


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render the machine-readable result as the README-facing report."""
    coverage = report["coverage"]
    human_quality = report["human_quality"]
    agreement = report["judge_human_groundedness"]
    complete = report["status"] == "complete"

    lines = [
        "# Human draft evaluation and judge agreement",
        "",
        f"**Status: {str(report['status']).upper()}**",
        "",
    ]
    if not complete:
        lines.extend([
            "> This report is incomplete. It must not be cited as evidence of draft",
            "> quality or judge validity until every completion condition passes.",
            "",
        ])
    lines.extend([
        f"Generated: `{report['generated_at']}`",
        "",
        "## Evaluation coverage",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| Review design | {coverage['review_mode'].replace('_', ' ').title()} |",
        f"| Successful drafts | {coverage['successful_drafts']} |",
        f"| LLM-judge verdicts | {coverage['judge_verdicts']} |",
        f"| Resolved human references | {coverage['human_reference_labels']} |",
    ])
    if coverage["review_mode"] != "single_reviewer":
        lines.extend([
            f"| Independently double-reviewed | {coverage['double_reviewed']} |",
            f"| Required double-review target | {coverage['double_review_target']} |",
        ])
    lines.extend(["", "Completion checks:", ""])
    for name, passed in coverage["complete_conditions"].items():
        label = name.replace("_", " ")
        lines.append(f"- {'PASS' if passed else 'PENDING'} — {label}")

    lines.extend([
        "",
        "## Human draft-quality ratings",
        "",
        "Human labels are the reference. Intervals are 95% Wilson intervals for the",
        "observed sample proportions.",
        "",
        "| Dimension | Passing | Rate | 95% interval |",
        "|---|---:|---:|---:|",
    ])
    for field, metric in human_quality.items():
        label = field.replace("_", " ").title()
        interval = f"{_display_rate(metric['lower'])}–{_display_rate(metric['upper'])}"
        lines.append(
            f"| {label} | {metric['successes']}/{metric['n']} | "
            f"{_display_rate(metric['rate'])} | {interval} |"
        )

    lines.extend([
        "",
        "Human ratings by route:",
        "",
        "| Route | Items | Grounded | Next step | Safety | Complete | Tone | Overall |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for route, metrics in report["human_quality_by_route"].items():
        lines.append(
            f"| {route} | {metrics['n']} | "
            f"{_display_rate(metrics['groundedness']['rate'])} | "
            f"{_display_rate(metrics['correct_next_step']['rate'])} | "
            f"{_display_rate(metrics['safety_privacy']['rate'])} | "
            f"{_display_rate(metrics['completeness']['rate'])} | "
            f"{_display_rate(metrics['tone']['rate'])} | "
            f"{_display_rate(metrics['overall_acceptability']['rate'])} |"
        )

    lines.extend([
        "",
        "## LLM judge versus human groundedness",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Comparable items | {agreement['n']} |",
        f"| Raw agreement | {_display_rate(agreement['rate'])} |",
        f"| Cohen's κ | {_display_number(agreement['cohen_kappa'])} |",
        f"| Human-identified ungrounded drafts | {agreement['human_ungrounded']} |",
        f"| Judge ungrounded recall | {_display_rate(agreement['ungrounded_recall'])} |",
        f"| Judge ungrounded precision | {_display_rate(agreement['ungrounded_precision'])} |",
        "",
        "Confusion matrix (rows are human reference; columns are LLM judge):",
        "",
        "| Human \\ Judge | Grounded | Ungrounded |",
        "|---|---:|---:|",
    ])
    confusion = agreement["confusion_rows_reference_columns_comparison"]
    for human in ("GROUNDED", "UNGROUNDED"):
        lines.append(
            f"| {human.title()} | {confusion[human]['GROUNDED']} | "
            f"{confusion[human]['UNGROUNDED']} |"
        )

    lines.extend(["", "Agreement by route:", ""])
    lines.extend([
        "| Route | Comparable items | Agreement | Cohen's κ |",
        "|---|---:|---:|---:|",
    ])
    for route, metric in agreement["by_route"].items():
        lines.append(
            f"| {route} | {metric['n']} | {_display_rate(metric['rate'])} | "
            f"{_display_number(metric['cohen_kappa'])} |"
        )

    lines.extend(["", "## Inter-human reliability", ""])
    pairs = report["inter_human_reliability"]
    if pairs:
        lines.extend([
            "| Reviewers | Overlap | Groundedness agreement | Groundedness κ | "
            "Overall agreement | Overall κ |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for pair in pairs:
            grounded = pair["groundedness"]
            overall = pair["overall_acceptability"]
            lines.append(
                f"| {' / '.join(pair['reviewers'])} | {pair['n_rows_overlapping']} | "
                f"{_display_rate(grounded['rate'])} | "
                f"{_display_number(grounded['cohen_kappa'])} | "
                f"{_display_rate(overall['rate'])} | "
                f"{_display_number(overall['cohen_kappa'])} |"
            )
    else:
        if coverage["review_mode"] == "single_reviewer":
            lines.append("Not measured because this run uses one human reviewer.")
        else:
            lines.append("No reviewer pair has completed an overlapping sample.")

    lines.extend([
        "",
        "## Interpretation and limitations",
        "",
        report["interpretation"],
        "",
    ])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend([
        "",
        "The full annotation rubric and procedure are in [`eval/HUMAN_EVAL.md`](../HUMAN_EVAL.md).",
        "The machine-readable result is "
        "[`judge_human_agreement.json`](judge_human_agreement.json).",
        "",
    ])
    return "\n".join(lines)


def score_reviews(
    manifest_path: Path,
    rating_paths: list[Path],
    output_path: Path,
    *,
    adjudication_path: Path | None = None,
    markdown_path: Path | None = None,
    require_rating_notes: bool = True,
    single_reviewer: bool = False,
    normalize_overall_pass: bool = False,
) -> dict[str, Any]:
    """Validate human labels and write the agreement/quality report."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_items = list(manifest.get("items") or ())
    evidence_by_item = {
        str(item["item_id"]): str(item.get("evidence_sha256", ""))
        for item in manifest_items
    }
    if any(not value for value in evidence_by_item.values()):
        raise ValueError("manifest is missing per-item evidence hashes")
    ratings = _load_ratings(
        rating_paths,
        evidence_by_item,
        require_notes=require_rating_notes,
        normalize_overall_pass=normalize_overall_pass,
    )
    adjudications = (
        _load_ratings(
            [adjudication_path],
            evidence_by_item,
            require_notes=True,
            allow_unsure=False,
        )
        if adjudication_path is not None
        else []
    )
    references, unresolved = _resolve_references(
        manifest_items, ratings, adjudications
    )

    ratings_by_item: dict[str, list[Rating]] = defaultdict(list)
    for rating in ratings:
        ratings_by_item[rating.item_id].append(rating)
    double_reviewed = sum(len(values) >= 2 for values in ratings_by_item.values())
    target = int(manifest.get("protocol", {}).get("double_review_target", 0))
    reviewer_ids = sorted({rating.reviewer_id for rating in ratings})
    if single_reviewer and len(reviewer_ids) != 1:
        raise ValueError(
            "single-reviewer mode requires ratings from exactly one reviewer"
        )
    review_mode = "single_reviewer" if single_reviewer else "double_review"

    quality_labels = {
        "groundedness": "GROUNDED",
        "correct_next_step": "PASS",
        "safety_privacy": "PASS",
        "completeness": "PASS",
        "tone": "PASS",
        "overall_acceptability": "ACCEPT",
    }
    human_quality = {
        field: _wilson(
            sum(values[field] == success for values in references.values()),
            len(references),
        )
        for field, success in quality_labels.items()
    }
    route_by_item = {
        str(item["item_id"]): str(item.get("route") or "unknown")
        for item in manifest_items
    }
    human_quality_by_route: dict[str, Any] = {}
    for route in sorted(set(route_by_item.values())):
        route_references = [
            values
            for item_id, values in references.items()
            if route_by_item.get(item_id) == route
        ]
        if not route_references:
            continue
        human_quality_by_route[route] = {
            "n": len(route_references),
            **{
                field: _wilson(
                    sum(values[field] == success for values in route_references),
                    len(route_references),
                )
                for field, success in quality_labels.items()
            },
        }

    judged = sum(
        item.get("judge_verdict") in {"GROUNDED", "UNGROUNDED"}
        for item in manifest_items
    )
    complete_conditions: dict[str, bool] = {
        "all_successful_drafts_judged": judged == len(manifest_items),
        "all_successful_drafts_human_reviewed": len(references) == len(manifest_items),
        "no_unresolved_fields": not unresolved,
    }
    if single_reviewer:
        complete_conditions["one_reviewer_present"] = len(reviewer_ids) == 1
    else:
        complete_conditions["at_least_two_reviewers"] = len(reviewer_ids) >= 2
        complete_conditions["double_review_target_met"] = double_reviewed >= target
    complete = all(complete_conditions.values())

    reported_protocol = dict(manifest.get("protocol", {}))
    reported_protocol["review_mode"] = review_mode
    if single_reviewer:
        reported_protocol["configured_double_review_target"] = target
        reported_protocol["double_review_target"] = 0

    if single_reviewer:
        interpretation = (
            "One resolved human rating set is the reference for draft quality and "
            "judge comparison. Inter-human reliability is not measured. Wilson "
            "intervals show denominator uncertainty for the observed sample rates."
        )
    else:
        interpretation = (
            "The human reference is authoritative. Single-reviewed items use that "
            "reviewer's label; matching double reviews use their consensus; any "
            "disagreement or UNSURE value requires a separate adjudication row. "
            "Wilson intervals show denominator uncertainty for human quality rates."
        )

    limitations = [
        "Human review uses synthetic correspondence and authored SOPs, not real inbox mail.",
        "Agreement validates this judge prompt and sample, not arbitrary future prompts.",
        "A sample with no human-identified ungrounded draft cannot estimate judge recall.",
    ]
    if single_reviewer:
        limitations.append(
            "One reviewer supplied the human reference, so individual rating bias "
            "and inter-human reliability are not measured."
        )
    if not require_rating_notes:
        limitations.append(
            "The rating sheet did not include notes for every negative label, so "
            "some item-level rationale is unavailable."
        )
    if normalize_overall_pass:
        limitations.append(
            "Positive PASS values in the overall-acceptability column were "
            "normalized to the rubric's equivalent ACCEPT label."
        )

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "complete" if complete else "incomplete",
        "source": manifest.get("source", {}),
        "protocol": reported_protocol,
        "coverage": {
            "review_mode": review_mode,
            "successful_drafts": len(manifest_items),
            "judge_verdicts": judged,
            "human_reference_labels": len(references),
            "reviewers": reviewer_ids,
            "double_reviewed": double_reviewed,
            "double_review_target": 0 if single_reviewer else target,
            "independent_rating_notes_required": require_rating_notes,
            "normalized_overall_pass": normalize_overall_pass,
            "unresolved": unresolved,
            "complete_conditions": complete_conditions,
        },
        "human_quality": human_quality,
        "human_quality_by_route": human_quality_by_route,
        "inter_human_reliability": _pairwise_reliability(ratings),
        "judge_human_groundedness": _judge_agreement(manifest_items, references),
        "interpretation": interpretation,
        "limitations": limitations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="write a blinded reviewer CSV")
    prepare.add_argument("--drafts", type=Path, default=DEFAULT_DRAFTS)
    prepare.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--reviewer-id", required=True)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument(
        "--overlap-only",
        action="store_true",
        help="include only the preselected double-review subset",
    )

    score = commands.add_parser("score", help="score filled human review CSVs")
    score.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    score.add_argument("--ratings", type=Path, nargs="+", required=True)
    score.add_argument("--adjudication", type=Path, default=None)
    score.add_argument(
        "--allow-missing-rating-notes",
        action="store_true",
        help=(
            "allow missing notes in rating sheets; adjudication still requires "
            "notes for negative verdicts"
        ),
    )
    score.add_argument(
        "--single-reviewer",
        action="store_true",
        help="use one resolved reviewer sheet without inter-human reliability",
    )
    score.add_argument(
        "--normalize-overall-pass",
        action="store_true",
        help="treat PASS in overall_acceptability as the equivalent ACCEPT label",
    )
    score.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    score.add_argument(
        "--markdown-output", type=Path, default=DEFAULT_MARKDOWN_REPORT
    )

    sync = commands.add_parser(
        "sync-judge",
        help="refresh hidden manifest judge fields without changing review evidence",
    )
    sync.add_argument("--drafts", type=Path, default=DEFAULT_DRAFTS)
    sync.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "prepare":
        result = prepare_review(
            args.drafts,
            args.manifest,
            args.output,
            reviewer_id=args.reviewer_id,
            seed=args.seed,
            overlap_only=args.overlap_only,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "sync-judge":
        result = sync_manifest_judgments(args.drafts, args.manifest)
        print(json.dumps(result, indent=2))
        return 0

    report = score_reviews(
        args.manifest,
        args.ratings,
        args.output,
        adjudication_path=args.adjudication,
        markdown_path=args.markdown_output,
        require_rating_notes=not args.allow_missing_rating_notes,
        single_reviewer=args.single_reviewer,
        normalize_overall_pass=args.normalize_overall_pass,
    )
    print(json.dumps({
        "status": report["status"],
        "coverage": report["coverage"],
        "output": str(args.output),
    }, indent=2))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "Rating",
    "evidence_hash",
    "prepare_review",
    "render_markdown_report",
    "score_reviews",
    "sync_manifest_judgments",
]
