"""Blind review preparation and judge-human agreement tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from eval.human_review import (
    REVIEW_COLUMNS,
    evidence_hash,
    prepare_review,
    score_reviews,
    sync_manifest_judgments,
)

TEST_EVIDENCE_HASH = evidence_hash("email", "SOP-FIL-001", "sop", "draft")


def draft(email_id: str, judge: str = "GROUNDED") -> dict[str, object]:
    return {
        "email_id": email_id,
        "scenario_id": f"scenario-{email_id}",
        "label": "filing",
        "predicted_label": "filing",
        "route": "auto_reply",
        "confidence": 0.97,
        "sop_ids": ["SOP-FIL-001"],
        "source_sops": ["SOP-FIL-001"],
        "status": "ok",
        "failure_reason": None,
        "grounded_on": ["SOP-FIL-001"],
        "model_name": "fake-drafter",
        "judge_verdict": judge,
        "judge_reason": "test reason",
        "judge_model": "fake-judge",
        "email_text": "=not-a-formula",
        "text": "You may file online.",
    }


def write_drafts(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({
        "drafter_model": "fake-drafter",
        "judge_model": "fake-judge",
        "prompt": "draft.v1.txt",
        "judge_prompt": "judge.v2.txt",
        "drafts": items,
    }), encoding="utf-8")


def rating_row(
    item_id: str,
    reviewer: str,
    groundedness: str,
    *,
    overall: str | None = None,
) -> dict[str, object]:
    failed = groundedness == "UNGROUNDED"
    return {
        "review_order": 1,
        "item_id": item_id,
        "evidence_sha256": TEST_EVIDENCE_HASH,
        "citizen_email_redacted": "email",
        "sop_ids": "SOP-FIL-001",
        "sop_text": "sop",
        "draft_redacted": "draft",
        "groundedness": groundedness,
        "correct_next_step": "PASS",
        "safety_privacy": "PASS",
        "completeness": "PASS",
        "tone": "PASS",
        "overall_acceptability": overall or ("REJECT" if failed else "ACCEPT"),
        "review_notes": "unsupported claim" if failed else "",
        "reviewer_id": reviewer,
    }


def write_ratings(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest(items: list[dict[str, object]], target: int) -> dict[str, object]:
    return {
        "source": {"judge_model": "fake-judge"},
        "protocol": {"double_review_target": target},
        "items": [
            {**item, "evidence_sha256": TEST_EVIDENCE_HASH}
            for item in items
        ],
    }


def test_prepare_review_is_blind_and_spreadsheet_safe(tmp_path: Path) -> None:
    drafts = tmp_path / "drafts.json"
    manifest_path = tmp_path / "manifest.json"
    review = tmp_path / "review.csv"
    write_drafts(drafts, [draft("email-1"), draft("email-2")])

    result = prepare_review(
        drafts,
        manifest_path,
        review,
        reviewer_id="reviewer_a",
    )

    with review.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert result["n_items"] == 2
    assert len(rows) == 2
    assert "judge_verdict" not in rows[0]
    assert "predicted_label" not in rows[0]
    assert "email_id" not in rows[0]
    assert rows[0]["citizen_email_redacted"].startswith("'=")
    assert rows[0]["reviewer_id"] == "reviewer_a"


def test_sync_judge_preserves_review_csv_and_evidence(tmp_path: Path) -> None:
    drafts_path = tmp_path / "drafts.json"
    manifest_path = tmp_path / "manifest.json"
    review_path = tmp_path / "review.csv"
    item = draft("email-1")
    item["judge_verdict"] = None
    item["judge_reason"] = None
    item["judge_model"] = None
    write_drafts(drafts_path, [item])
    prepare_review(
        drafts_path,
        manifest_path,
        review_path,
        reviewer_id="reviewer_a",
    )
    original_csv = review_path.read_bytes()
    original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    item["judge_verdict"] = "UNGROUNDED"
    item["judge_reason"] = "Unsupported deadline."
    item["judge_model"] = "new-judge"
    write_drafts(drafts_path, [item])
    document = json.loads(drafts_path.read_text(encoding="utf-8"))
    document["judge_model"] = "new-judge"
    drafts_path.write_text(json.dumps(document), encoding="utf-8")

    result = sync_manifest_judgments(drafts_path, manifest_path)

    updated = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert review_path.read_bytes() == original_csv
    assert updated["items"][0]["evidence_sha256"] == (
        original_manifest["items"][0]["evidence_sha256"]
    )
    assert updated["items"][0]["judge_verdict"] == "UNGROUNDED"
    assert result["judge_model"] == "new-judge"


def test_complete_report_scores_safety_critical_judge_recall(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    output_path = tmp_path / "agreement.json"
    markdown_path = tmp_path / "agreement.md"
    items = [
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
        {"item_id": "JH-002", "judge_verdict": "GROUNDED", "route": "redirect"},
    ]
    manifest_path.write_text(json.dumps(manifest(items, target=2)), encoding="utf-8")
    rows = [
        rating_row("JH-001", "reviewer_a", "GROUNDED"),
        rating_row("JH-002", "reviewer_a", "UNGROUNDED"),
        rating_row("JH-001", "reviewer_b", "GROUNDED"),
        rating_row("JH-002", "reviewer_b", "UNGROUNDED"),
    ]
    write_ratings(ratings_path, rows)

    report = score_reviews(
        manifest_path,
        [ratings_path],
        output_path,
        markdown_path=markdown_path,
    )

    assert report["status"] == "complete"
    agreement = report["judge_human_groundedness"]
    assert agreement["rate"] == 0.5
    assert agreement["cohen_kappa"] is None
    assert agreement["ungrounded_recall"] == 0.0
    assert agreement["confusion_rows_reference_columns_comparison"]["UNGROUNDED"][
        "GROUNDED"
    ] == 1
    assert report["inter_human_reliability"][0]["groundedness"]["rate"] == 1.0
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "complete"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Human draft evaluation and judge agreement" in markdown
    assert "**Status: COMPLETE**" in markdown
    assert "| Judge ungrounded recall | 0.0% |" in markdown


def test_disagreement_stays_incomplete_until_adjudicated(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    output_path = tmp_path / "agreement.json"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=1)), encoding="utf-8")
    write_ratings(ratings_path, [
        rating_row("JH-001", "reviewer_a", "GROUNDED"),
        rating_row("JH-001", "reviewer_b", "UNGROUNDED"),
    ])

    report = score_reviews(manifest_path, [ratings_path], output_path)

    assert report["status"] == "incomplete"
    assert report["coverage"]["human_reference_labels"] == 0
    assert {entry["item_id"] for entry in report["coverage"]["unresolved"]} == {
        "JH-001"
    }


def test_separate_adjudication_resolves_a_disagreement(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    adjudication_path = tmp_path / "adjudicated.csv"
    output_path = tmp_path / "agreement.json"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=1)), encoding="utf-8")
    write_ratings(ratings_path, [
        rating_row("JH-001", "reviewer_a", "GROUNDED"),
        rating_row("JH-001", "reviewer_b", "UNGROUNDED"),
    ])
    write_ratings(adjudication_path, [
        rating_row("JH-001", "adjudicator", "UNGROUNDED"),
    ])

    report = score_reviews(
        manifest_path,
        [ratings_path],
        output_path,
        adjudication_path=adjudication_path,
    )

    assert report["status"] == "complete"
    assert report["coverage"]["unresolved"] == []
    assert report["human_quality"]["groundedness"]["rate"] == 0.0


def test_original_ratings_can_report_missing_note_protocol_deviation(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    output_path = tmp_path / "agreement.json"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=1)), encoding="utf-8")
    rows = [
        rating_row("JH-001", "reviewer_a", "GROUNDED", overall="REJECT"),
        rating_row("JH-001", "reviewer_b", "GROUNDED", overall="REJECT"),
    ]
    for row in rows:
        row["review_notes"] = ""
    write_ratings(ratings_path, rows)

    report = score_reviews(
        manifest_path,
        [ratings_path],
        output_path,
        require_rating_notes=False,
    )

    assert report["status"] == "complete"
    assert report["coverage"]["independent_rating_notes_required"] is False
    assert any("did not include notes" in item for item in report["limitations"])


def test_single_reviewer_mode_normalizes_positive_overall_label(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    output_path = tmp_path / "agreement.json"
    markdown_path = tmp_path / "agreement.md"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=1)), encoding="utf-8")
    row = rating_row("JH-001", "reviewer_a", "GROUNDED")
    row["overall_acceptability"] = "PASS"
    write_ratings(ratings_path, [row])

    report = score_reviews(
        manifest_path,
        [ratings_path],
        output_path,
        markdown_path=markdown_path,
        single_reviewer=True,
        normalize_overall_pass=True,
    )

    assert report["status"] == "complete"
    assert report["coverage"]["review_mode"] == "single_reviewer"
    assert report["coverage"]["double_review_target"] == 0
    assert report["human_quality"]["overall_acceptability"]["rate"] == 1.0
    assert report["human_quality_by_route"]["auto_reply"]["n"] == 1
    assert report["inter_human_reliability"] == []
    assert any("normalized" in item for item in report["limitations"])
    assert "Not measured because this run uses one human reviewer." in (
        markdown_path.read_text(encoding="utf-8")
    )


def test_single_reviewer_mode_rejects_multiple_reviewer_ids(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    output_path = tmp_path / "agreement.json"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=1)), encoding="utf-8")
    write_ratings(ratings_path, [
        rating_row("JH-001", "reviewer_a", "GROUNDED"),
        rating_row("JH-001", "reviewer_b", "GROUNDED"),
    ])

    with pytest.raises(ValueError, match="exactly one reviewer"):
        score_reviews(
            manifest_path,
            [ratings_path],
            output_path,
            single_reviewer=True,
        )


def test_adjudication_cannot_leave_unsure_labels(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    adjudication_path = tmp_path / "adjudicated.csv"
    output_path = tmp_path / "agreement.json"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=1)), encoding="utf-8")
    write_ratings(ratings_path, [
        rating_row("JH-001", "reviewer_a", "GROUNDED"),
        rating_row("JH-001", "reviewer_b", "UNGROUNDED"),
    ])
    row = rating_row("JH-001", "adjudicator", "UNSURE", overall="UNSURE")
    row["review_notes"] = "Requires a final decision."
    write_ratings(adjudication_path, [row])

    with pytest.raises(ValueError, match="adjudication must resolve"):
        score_reviews(
            manifest_path,
            [ratings_path],
            output_path,
            adjudication_path=adjudication_path,
        )


def test_ungrounded_draft_cannot_be_accepted(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    output_path = tmp_path / "agreement.json"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=0)), encoding="utf-8")
    write_ratings(ratings_path, [
        rating_row("JH-001", "reviewer_a", "UNGROUNDED", overall="ACCEPT"),
    ])

    with pytest.raises(ValueError, match="must be REJECTED"):
        score_reviews(manifest_path, [ratings_path], output_path)


def test_modified_review_evidence_is_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    ratings_path = tmp_path / "ratings.csv"
    output_path = tmp_path / "agreement.json"
    manifest_path.write_text(json.dumps(manifest([
        {"item_id": "JH-001", "judge_verdict": "GROUNDED", "route": "auto_reply"},
    ], target=0)), encoding="utf-8")
    row = rating_row("JH-001", "reviewer_a", "GROUNDED")
    row["draft_redacted"] = "a different draft"
    write_ratings(ratings_path, [row])

    with pytest.raises(ValueError, match="evidence changed"):
        score_reviews(manifest_path, [ratings_path], output_path)
