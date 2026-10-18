from intent_integrity import Assumption, IntentContract, contract_from_dict, contract_to_dict


def sample_contract_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "contract_id": "task-17",
        "version": 3,
        "goal": "Publish the release only after the current build passes.",
        "constraints": ["Do not publish if the release candidate changes."],
        "permitted_actions": ["run_tests", "publish_release"],
        "prohibited_actions": ["delete_repository"],
        "consequential_actions": ["publish_release"],
        "required_evidence_by_action": {"publish_release": ["build-result"]},
        "required_approvals_by_action": {"publish_release": ["release-approval"]},
        "assumptions": [
            {
                "assumption_id": "source-unchanged",
                "statement": "The release candidate has not changed since testing.",
                "evidence_ids": ["build-result"],
                "invalidation_conditions": ["A new commit is pushed."],
            }
        ],
        "required_approvals": ["release-manager"],
        "acceptance_criteria": ["The published version matches the verified candidate."],
    }


def test_contract_round_trip_preserves_semantics() -> None:
    original = contract_from_dict(sample_contract_payload())
    serialized = contract_to_dict(original)
    restored = contract_from_dict(serialized)
    assert restored == original


def test_contract_parser_rejects_unknown_fields() -> None:
    payload = sample_contract_payload()
    payload["unrecognized_policy"] = True
    try:
        contract_from_dict(payload)
    except ValueError as exc:
        assert "Unknown contract fields" in str(exc)
    else:
        raise AssertionError("Unknown fields must be rejected")


def test_contract_parser_rejects_unsupported_schema_version() -> None:
    payload = sample_contract_payload()
    payload["schema_version"] = "2.0"
    try:
        contract_from_dict(payload)
    except ValueError as exc:
        assert "Unsupported schema_version" in str(exc)
    else:
        raise AssertionError("Unsupported schema versions must be rejected")


def test_contract_parser_rejects_boolean_as_integer_version() -> None:
    payload = sample_contract_payload()
    payload["version"] = True
    try:
        contract_from_dict(payload)
    except ValueError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("Boolean values must not be accepted as versions")


def test_contract_parser_rejects_action_that_is_both_permitted_and_prohibited() -> None:
    payload = sample_contract_payload()
    payload["prohibited_actions"] = ["publish_release"]
    try:
        contract_from_dict(payload)
    except ValueError as exc:
        assert "both permitted and prohibited" in str(exc)
    else:
        raise AssertionError("Conflicting action policy must be rejected")


def test_assumption_model_is_round_tripped() -> None:
    contract = IntentContract(
        contract_id="task-18",
        version=1,
        goal="Check assumptions",
        permitted_actions=("run_tests",),
        assumptions=(
            Assumption(
                assumption_id="repo-exists",
                statement="The repository is available.",
                evidence_ids=("repo-metadata",),
                invalidation_conditions=("Repository is archived.",),
            ),
        ),
    )
    assert contract_from_dict(contract_to_dict(contract)) == contract


def test_serialized_contract_matches_published_json_schema() -> None:
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator

    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "intent-contract.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    contract = contract_from_dict(sample_contract_payload())
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(contract_to_dict(contract)))
    assert errors == []
