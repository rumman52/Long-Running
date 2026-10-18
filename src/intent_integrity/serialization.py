"""JSON serialization helpers for portable intent contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from intent_integrity.models import Assumption, IntentContract

SCHEMA_VERSION = "1.0"

_ALLOWED_KEYS = {
    "schema_version",
    "contract_id",
    "version",
    "goal",
    "constraints",
    "permitted_actions",
    "prohibited_actions",
    "consequential_actions",
    "required_evidence_by_action",
    "required_approvals_by_action",
    "assumptions",
    "required_approvals",
    "acceptance_criteria",
}
_REQUIRED_KEYS = {
    "schema_version",
    "contract_id",
    "version",
    "goal",
    "permitted_actions",
    "prohibited_actions",
}


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string_list(
    value: object,
    name: str,
    *,
    default: tuple[str, ...] = (),
) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array of strings")
    result = tuple(_required_text(item, f"{name} item") for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _action_requirements(
    value: object,
    name: str,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object mapping action categories to ID arrays")
    result: list[tuple[str, tuple[str, ...]]] = []
    for category, identifiers in value.items():
        action_category = _required_text(category, f"{name} key")
        result.append((action_category, _string_list(identifiers, f"{name}.{action_category}")))
    return tuple(result)


def contract_from_dict(payload: Mapping[str, object]) -> IntentContract:
    """Parse a JSON-decoded mapping and reject unknown or malformed fields.

    This parser enforces structural constraints. Production hosts must additionally validate
    the contract's authority and obtain user/administrator approval before activating it.
    """
    unknown = set(payload) - _ALLOWED_KEYS
    missing = _REQUIRED_KEYS - set(payload)
    if unknown:
        raise ValueError(f"Unknown contract fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"Missing required contract fields: {', '.join(sorted(missing))}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema_version; expected {SCHEMA_VERSION}")

    contract_id = _required_text(payload["contract_id"], "contract_id")
    goal = _required_text(payload["goal"], "goal")
    version = payload["version"]
    if type(version) is not int or version < 1:
        raise ValueError("version must be a positive integer")

    constraints = _string_list(payload.get("constraints", []), "constraints")
    permitted_actions = _string_list(payload["permitted_actions"], "permitted_actions")
    prohibited_actions = _string_list(payload["prohibited_actions"], "prohibited_actions")
    consequential_actions = _string_list(
        payload.get("consequential_actions", []), "consequential_actions"
    )
    required_approvals = _string_list(
        payload.get("required_approvals", []), "required_approvals"
    )
    acceptance_criteria = _string_list(
        payload.get("acceptance_criteria", []), "acceptance_criteria"
    )
    required_evidence_by_action = _action_requirements(
        payload.get("required_evidence_by_action", {}), "required_evidence_by_action"
    )
    required_approvals_by_action = _action_requirements(
        payload.get("required_approvals_by_action", {}), "required_approvals_by_action"
    )

    if set(permitted_actions) & set(prohibited_actions):
        raise ValueError("An action category cannot be both permitted and prohibited")
    if not set(consequential_actions).issubset(permitted_actions):
        raise ValueError("consequential_actions must be a subset of permitted_actions")
    for name, requirements in (
        ("required_evidence_by_action", required_evidence_by_action),
        ("required_approvals_by_action", required_approvals_by_action),
    ):
        invalid_categories = {category for category, _ in requirements} - set(permitted_actions)
        if invalid_categories:
            raise ValueError(
                f"{name} contains non-permitted categories: "
                f"{', '.join(sorted(invalid_categories))}"
            )

    assumptions_value = payload.get("assumptions", [])
    if not isinstance(assumptions_value, list):
        raise ValueError("assumptions must be an array")
    assumptions: list[Assumption] = []
    seen_assumption_ids: set[str] = set()
    for index, raw_assumption in enumerate(assumptions_value):
        if not isinstance(raw_assumption, Mapping):
            raise ValueError(f"assumptions[{index}] must be an object")
        allowed_assumption_keys = {
            "assumption_id",
            "statement",
            "evidence_ids",
            "invalidation_conditions",
        }
        unknown_assumption_keys = set(raw_assumption) - allowed_assumption_keys
        if unknown_assumption_keys:
            raise ValueError(
                f"Unknown assumptions[{index}] fields: "
                f"{', '.join(sorted(unknown_assumption_keys))}"
            )
        assumption_id = _required_text(
            raw_assumption.get("assumption_id"), f"assumptions[{index}].assumption_id"
        )
        statement = _required_text(
            raw_assumption.get("statement"), f"assumptions[{index}].statement"
        )
        if assumption_id in seen_assumption_ids:
            raise ValueError(f"Duplicate assumption_id: {assumption_id}")
        seen_assumption_ids.add(assumption_id)
        evidence_ids = _string_list(
            raw_assumption.get("evidence_ids", []), f"assumptions[{index}].evidence_ids"
        )
        invalidation_conditions = _string_list(
            raw_assumption.get("invalidation_conditions", []),
            f"assumptions[{index}].invalidation_conditions",
        )
        assumptions.append(
            Assumption(
                assumption_id=assumption_id,
                statement=statement,
                evidence_ids=evidence_ids,
                invalidation_conditions=invalidation_conditions,
            )
        )

    return IntentContract(
        contract_id=contract_id,
        version=version,
        goal=goal,
        constraints=constraints,
        permitted_actions=permitted_actions,
        prohibited_actions=prohibited_actions,
        consequential_actions=consequential_actions,
        required_evidence_by_action=required_evidence_by_action,
        required_approvals_by_action=required_approvals_by_action,
        assumptions=tuple(assumptions),
        required_approvals=required_approvals,
        acceptance_criteria=acceptance_criteria,
    )


def contract_to_dict(contract: IntentContract) -> dict[str, Any]:
    """Serialize a contract to the portable JSON object shape."""
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": contract.contract_id,
        "version": contract.version,
        "goal": contract.goal,
        "constraints": list(contract.constraints),
        "permitted_actions": list(contract.permitted_actions),
        "prohibited_actions": list(contract.prohibited_actions),
        "consequential_actions": list(contract.consequential_actions),
        "required_evidence_by_action": {
            category: list(identifiers)
            for category, identifiers in contract.required_evidence_by_action
        },
        "required_approvals_by_action": {
            category: list(identifiers)
            for category, identifiers in contract.required_approvals_by_action
        },
        "assumptions": [
            {
                "assumption_id": assumption.assumption_id,
                "statement": assumption.statement,
                "evidence_ids": list(assumption.evidence_ids),
                "invalidation_conditions": list(assumption.invalidation_conditions),
            }
            for assumption in contract.assumptions
        ],
        "required_approvals": list(contract.required_approvals),
        "acceptance_criteria": list(contract.acceptance_criteria),
    }
