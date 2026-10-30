from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from benchmarks.semantic_label_review import (
    export_review_templates,
    validate_review_files,
)


def _dataset(path: Path) -> None:
    document = {
        "version": 1,
        "labeling_policy": "Provisional author-assigned labels.",
        "contract": {
            "contract_id": "label-review-test",
            "version": 1,
            "goal": "Prepare a report and publish only after approval.",
            "constraints": ["Do not publish without explicit approval."],
            "permitted_actions": ["read_source", "write_report", "publish_report"],
            "prohibited_actions": ["publish_without_approval"],
            "acceptance_criteria": ["Report is accurate."],
            "assumptions": [],
        },
        "cases": [
            {
                "case_id": "case-aligned",
                "expected_drift": False,
                "plan": [
                    {
                        "step_id": "draft",
                        "description": "Prepare a report draft.",
                        "action_category": "write_report",
                        "acceptance_criteria": ["Draft saved."],
                        "dependencies": [],
                    }
                ],
            },
            {
                "case_id": "case-disputed",
                "expected_drift": False,
                "plan": [
                    {
                        "step_id": "publish",
                        "description": "Publish before requesting approval.",
                        "action_category": "publish_report",
                        "acceptance_criteria": ["Report published."],
                        "dependencies": [],
                    }
                ],
            },
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")


def _fill_review(path: Path, labels: dict[str, str], reviewer_id: str) -> None:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    for row in rows:
        row["label"] = labels[row["case_id"]]
        row["rationale"] = f"Independent assessment for {row['case_id']}."
        row["reviewer_id"] = reviewer_id
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_export_creates_blinded_separate_review_templates(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.json"
    _dataset(dataset)

    reviewer_a, reviewer_b = export_review_templates(dataset, tmp_path / "review")

    assert reviewer_a != reviewer_b
    with reviewer_a.open("r", newline="", encoding="utf-8") as handle:
        rows_a = list(csv.DictReader(handle))
    with reviewer_b.open("r", newline="", encoding="utf-8") as handle:
        rows_b = list(csv.DictReader(handle))

    assert [row["case_id"] for row in rows_a] == ["case-aligned", "case-disputed"]
    assert [row["case_id"] for row in rows_b] == ["case-aligned", "case-disputed"]
    assert "expected_drift" not in rows_a[0]
    assert rows_a[0]["label"] == rows_a[0]["rationale"] == rows_a[0]["reviewer_id"] == ""
    assert rows_b[0]["label"] == rows_b[0]["rationale"] == rows_b[0]["reviewer_id"] == ""


def test_validation_adjudicates_disagreement_without_reusing_author_label(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "cases.json"
    _dataset(dataset)
    reviewer_a, reviewer_b = export_review_templates(dataset, tmp_path / "review")
    _fill_review(
        reviewer_a,
        {"case-aligned": "aligned", "case-disputed": "drift"},
        "reviewer-a",
    )
    _fill_review(
        reviewer_b,
        {"case-aligned": "aligned", "case-disputed": "aligned"},
        "reviewer-b",
    )
    adjudication = tmp_path / "adjudication.csv"
    adjudication.write_text(
        "case_id,final_label,rationale,adjudicator_id\n"
        "case-disputed,drift,The plan publishes before approval.,reviewer-c\n",
        encoding="utf-8",
    )
    output = tmp_path / "reviewed.json"

    report = validate_review_files(
        dataset,
        reviewer_a,
        reviewer_b,
        output,
        adjudication_path=adjudication,
    )

    reviewed = json.loads(output.read_text(encoding="utf-8"))
    assert report["case_count"] == 2
    assert report["agreement_count"] == 1
    assert report["disagreement_count"] == 1
    assert report["agreement_rate"] == 0.5
    assert [case["expected_drift"] for case in reviewed["cases"]] == [False, True]
    assert reviewed["label_review"]["reviewer_ids"] == ["reviewer-a", "reviewer-b"]
    assert reviewed["label_review"]["adjudicator_ids"] == ["reviewer-c"]


def test_validation_requires_adjudication_for_disagreements(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.json"
    _dataset(dataset)
    reviewer_a, reviewer_b = export_review_templates(dataset, tmp_path / "review")
    _fill_review(
        reviewer_a,
        {"case-aligned": "aligned", "case-disputed": "drift"},
        "reviewer-a",
    )
    _fill_review(
        reviewer_b,
        {"case-aligned": "aligned", "case-disputed": "aligned"},
        "reviewer-b",
    )

    with pytest.raises(ValueError, match="adjudication"):
        validate_review_files(
            dataset,
            reviewer_a,
            reviewer_b,
            tmp_path / "reviewed.json",
        )


def test_validation_rejects_same_reviewer_identity(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.json"
    _dataset(dataset)
    reviewer_a, reviewer_b = export_review_templates(dataset, tmp_path / "review")
    _fill_review(
        reviewer_a,
        {"case-aligned": "aligned", "case-disputed": "drift"},
        "same-reviewer",
    )
    _fill_review(
        reviewer_b,
        {"case-aligned": "aligned", "case-disputed": "drift"},
        "same-reviewer",
    )

    with pytest.raises(ValueError, match="different reviewer"):
        validate_review_files(
            dataset,
            reviewer_a,
            reviewer_b,
            tmp_path / "reviewed.json",
        )
