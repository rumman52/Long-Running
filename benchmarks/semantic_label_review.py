"""Blinded two-reviewer workflow for semantic-drift benchmark labels.

The exporter intentionally omits provisional author labels. The validator
requires independent reviewer IDs and third-party adjudication for disagreements.
It never overwrites the source dataset.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from intent_integrity.semantic_evaluation import load_semantic_evaluation_cases

REVIEW_FIELDS = (
    "case_id",
    "goal",
    "constraints_json",
    "plan_json",
    "label",
    "rationale",
    "reviewer_id",
)
ADJUDICATION_FIELDS = (
    "case_id",
    "final_label",
    "rationale",
    "adjudicator_id",
)
VALID_LABELS = frozenset({"aligned", "drift"})


def _object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _required_text(row: dict[str, str | None], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _spreadsheet_safe(value: str) -> str:
    """Prevent CSV cells from being interpreted as spreadsheet formulas."""
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def export_review_templates(
    dataset_path: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Create separate blinded CSV templates for two independent reviewers."""
    load_semantic_evaluation_cases(dataset_path)
    document = _object(
        json.loads(dataset_path.read_text(encoding="utf-8")),
        "dataset",
    )
    contract = _object(document.get("contract"), "contract")
    goal = contract.get("goal")
    constraints = contract.get("constraints")
    cases = document.get("cases")
    if not isinstance(goal, str) or not isinstance(constraints, list):
        raise ValueError("dataset contract must contain a goal and constraints")
    if not isinstance(cases, list) or not cases:
        raise ValueError("dataset cases must be a non-empty list")

    rows: list[dict[str, str]] = []
    for index, raw_case in enumerate(cases):
        case = _object(raw_case, f"cases[{index}]")
        case_id = case.get("case_id")
        plan = case.get("plan")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"cases[{index}].case_id must be a non-empty string")
        if not isinstance(plan, list) or not plan:
            raise ValueError(f"cases[{index}].plan must be a non-empty list")
        rows.append(
            {
                "case_id": _spreadsheet_safe(case_id),
                "goal": _spreadsheet_safe(goal),
                "constraints_json": json.dumps(
                    constraints,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "plan_json": json.dumps(
                    plan,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "label": "",
                "rationale": "",
                "reviewer_id": "",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    reviewer_a = output_dir / "reviewer-a.csv"
    reviewer_b = output_dir / "reviewer-b.csv"
    if reviewer_a.exists() or reviewer_b.exists():
        raise FileExistsError("review templates already exist; refusing to overwrite them")

    for path in (reviewer_a, reviewer_b):
        with path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return reviewer_a, reviewer_b


def _read_reviews(
    path: Path,
    expected_case_ids: set[str],
) -> tuple[dict[str, dict[str, str]], str]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise ValueError(f"{path.name} has an unexpected review-template header")
        rows_by_id: dict[str, dict[str, str]] = {}
        reviewer_ids: set[str] = set()
        for row_number, raw_row in enumerate(reader, start=2):
            row = {key: value for key, value in raw_row.items() if key is not None}
            case_id = _required_text(row, "case_id")
            if case_id not in expected_case_ids:
                raise ValueError(f"{path.name}:{row_number} contains an unknown case_id")
            if case_id in rows_by_id:
                raise ValueError(f"{path.name} contains duplicate case_id {case_id!r}")
            label = _required_text(row, "label").lower()
            if label not in VALID_LABELS:
                raise ValueError(f"{path.name}:{row_number} label must be aligned or drift")
            rationale = _required_text(row, "rationale")
            reviewer_id = _required_text(row, "reviewer_id")
            reviewer_ids.add(reviewer_id)
            rows_by_id[case_id] = {
                "label": label,
                "rationale": rationale,
                "reviewer_id": reviewer_id,
            }

    missing = expected_case_ids - set(rows_by_id)
    if missing:
        raise ValueError(f"{path.name} is missing case IDs: {', '.join(sorted(missing))}")
    if len(reviewer_ids) != 1:
        raise ValueError(f"{path.name} must contain exactly one reviewer identity")
    return rows_by_id, next(iter(reviewer_ids))


def _read_adjudications(
    path: Path | None,
    disagreement_ids: set[str],
    reviewer_ids: set[str],
) -> dict[str, dict[str, str]]:
    if disagreement_ids and path is None:
        raise ValueError("A third-party adjudication CSV is required for disagreements")
    if path is None:
        return {}

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ADJUDICATION_FIELDS:
            raise ValueError("adjudication CSV has an unexpected header")
        adjudications: dict[str, dict[str, str]] = {}
        adjudicator_ids: set[str] = set()
        for row_number, raw_row in enumerate(reader, start=2):
            row = {key: value for key, value in raw_row.items() if key is not None}
            case_id = _required_text(row, "case_id")
            if case_id not in disagreement_ids:
                raise ValueError(
                    f"adjudication CSV contains a case without reviewer disagreement: {case_id}"
                )
            if case_id in adjudications:
                raise ValueError(f"adjudication CSV contains duplicate case_id {case_id!r}")
            final_label = _required_text(row, "final_label").lower()
            if final_label not in VALID_LABELS:
                raise ValueError(
                    f"adjudication CSV:{row_number} final_label must be aligned or drift"
                )
            rationale = _required_text(row, "rationale")
            adjudicator_id = _required_text(row, "adjudicator_id")
            if adjudicator_id in reviewer_ids:
                raise ValueError("adjudicator must be different from both reviewers")
            adjudicator_ids.add(adjudicator_id)
            adjudications[case_id] = {
                "final_label": final_label,
                "rationale": rationale,
                "adjudicator_id": adjudicator_id,
            }

    missing = disagreement_ids - set(adjudications)
    if missing:
        raise ValueError(
            f"adjudication CSV is missing disputed case IDs: {', '.join(sorted(missing))}"
        )
    return adjudications


def validate_review_files(
    dataset_path: Path,
    reviewer_a_path: Path,
    reviewer_b_path: Path,
    output_path: Path,
    *,
    adjudication_path: Path | None = None,
) -> dict[str, object]:
    """Validate two independent reviews and write a separate adjudicated dataset."""
    if output_path.exists():
        raise FileExistsError("reviewed dataset already exists; refusing to overwrite it")

    load_semantic_evaluation_cases(dataset_path)
    source_bytes = dataset_path.read_bytes()
    document = _object(json.loads(source_bytes.decode("utf-8")), "dataset")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("dataset cases must be a non-empty list")
    expected_case_ids: set[str] = set()
    for index, raw_case in enumerate(cases):
        case = _object(raw_case, f"cases[{index}]")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in expected_case_ids:
            raise ValueError(f"cases[{index}] has a missing or duplicate case_id")
        expected_case_ids.add(case_id)

    review_a, reviewer_a_id = _read_reviews(reviewer_a_path, expected_case_ids)
    review_b, reviewer_b_id = _read_reviews(reviewer_b_path, expected_case_ids)
    if reviewer_a_id == reviewer_b_id:
        raise ValueError("the two review files must identify different reviewers")

    agreement_ids = {
        case_id
        for case_id in expected_case_ids
        if review_a[case_id]["label"] == review_b[case_id]["label"]
    }
    disagreement_ids = expected_case_ids - agreement_ids
    adjudications = _read_adjudications(
        adjudication_path,
        disagreement_ids,
        {reviewer_a_id, reviewer_b_id},
    )

    final_labels: dict[str, str] = {}
    for case_id in expected_case_ids:
        if case_id in disagreement_ids:
            final_labels[case_id] = adjudications[case_id]["final_label"]
        else:
            final_labels[case_id] = review_a[case_id]["label"]

    case_count = len(expected_case_ids)
    agreement_rate = len(agreement_ids) / case_count
    a_drift = sum(review_a[case_id]["label"] == "drift" for case_id in expected_case_ids)
    b_drift = sum(review_b[case_id]["label"] == "drift" for case_id in expected_case_ids)
    expected_agreement = (
        (a_drift / case_count) * (b_drift / case_count)
        + ((case_count - a_drift) / case_count)
        * ((case_count - b_drift) / case_count)
    )
    cohen_kappa = (
        (agreement_rate - expected_agreement) / (1 - expected_agreement)
        if expected_agreement < 1
        else None
    )

    for raw_case in cases:
        case = _object(raw_case, "case")
        case_id = str(case["case_id"])
        case["provisional_author_expected_drift"] = case["expected_drift"]
        case["expected_drift"] = final_labels[case_id] == "drift"

    adjudicator_ids = sorted(
        {item["adjudicator_id"] for item in adjudications.values()}
    )
    document["labeling_policy"] = (
        "Labels were independently assigned by two distinct reviewers. "
        "Every disagreement was resolved by a third-party adjudicator. "
        "Reviewer provenance and agreement statistics are recorded in label_review."
    )
    document["label_review"] = {
        "reviewer_ids": [reviewer_a_id, reviewer_b_id],
        "adjudicator_ids": adjudicator_ids,
        "case_count": case_count,
        "agreement_count": len(agreement_ids),
        "disagreement_count": len(disagreement_ids),
        "agreement_rate": round(agreement_rate, 6),
        "cohen_kappa": round(cohen_kappa, 6) if cohen_kappa is not None else None,
        "source_dataset_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "reviewed_at": datetime.now(UTC).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return {
        "case_count": case_count,
        "agreement_count": len(agreement_ids),
        "disagreement_count": len(disagreement_ids),
        "agreement_rate": round(agreement_rate, 6),
        "cohen_kappa": round(cohen_kappa, 6) if cohen_kappa is not None else None,
        "reviewer_ids": [reviewer_a_id, reviewer_b_id],
        "adjudicator_ids": adjudicator_ids,
        "output_path": str(output_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="create blinded reviewer CSV templates")
    export_parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("benchmarks/semantic_drift_cases.json"),
    )
    export_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/semantic-label-review"),
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="validate independent reviews and write an adjudicated dataset",
    )
    validate_parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("benchmarks/semantic_drift_cases.json"),
    )
    validate_parser.add_argument("--reviewer-a", type=Path, required=True)
    validate_parser.add_argument("--reviewer-b", type=Path, required=True)
    validate_parser.add_argument("--adjudication", type=Path)
    validate_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "export":
        reviewer_a, reviewer_b = export_review_templates(args.dataset, args.output_dir)
        print(json.dumps({"reviewer_a": str(reviewer_a), "reviewer_b": str(reviewer_b)}))
        return 0

    report = validate_review_files(
        args.dataset,
        args.reviewer_a,
        args.reviewer_b,
        args.output,
        adjudication_path=args.adjudication,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
