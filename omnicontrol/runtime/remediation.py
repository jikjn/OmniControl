from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from omnicontrol.runtime.kb import PROFILE_METADATA, find_matches
from omnicontrol.runtime.orchestrator import AttemptSpec


@dataclass(slots=True)
class RemediationContext:
    profile: str
    payload: dict[str, Any]
    prior_attempts: list[dict[str, Any]] = field(default_factory=list)
    kb_solution: dict[str, Any] | None = None


DEFAULT_ACTIONS_BY_BLOCKER: dict[str, list[str]] = {
    "license": ["probe_license_service", "validate_license_env"],
    "profile": ["discover_profiles", "supply_profile", "supply_profile_standalone_cpr", "supply_profile_standalone_name"],
    "timeout": ["increase_wait_budget", "reduce_scope", "switch_entrypoint"],
    "dependency": ["preflight_dependencies"],
    "focus": ["force_focus", "safe_click_focus", "attach_existing_window"],
    "runtime": ["capture_boot_diagnostics", "switch_entrypoint"],
}

DEFAULT_ACTIONS_BY_SOFTWARE_TYPE: dict[str, list[str]] = {
    "structured_api_sdk": ["supply_profile_standalone_cpr", "supply_profile_standalone_name", "start_station_standalone"],
    "game_engine_heavy_desktop": ["reduce_scope_buildpatch_help", "switch_to_editor_cmd_project"],
    "native_sdk_heavy_desktop": ["probe_license_service", "validate_license_env", "switch_to_nxcommand_shell"],
}


def best_solution_for(profile: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    matches = find_matches(profile, payload)
    for case in matches:
        solution = case.get("solution")
        if solution:
            return solution
    return None


def solution_actions(solution: dict[str, Any] | None) -> list[str]:
    if not solution:
        return []
    return list(solution.get("remediation_actions", []))


def plan_remediation_actions(profile: str, payload: dict[str, Any]) -> list[str]:
    strategy = payload.get("strategy", {})
    blocker_types = strategy.get("blocker_types", [])
    meta = PROFILE_METADATA.get(profile, {})
    software_type = meta.get("software_type")
    kb_solution = best_solution_for(profile, payload)

    actions: list[str] = []
    actions.extend(solution_actions(kb_solution))
    actions.extend(hint.get("action") for hint in strategy.get("recovery_hints", []))
    for blocker in blocker_types:
        actions.extend(DEFAULT_ACTIONS_BY_BLOCKER.get(blocker, []))
    if software_type:
        actions.extend(DEFAULT_ACTIONS_BY_SOFTWARE_TYPE.get(software_type, []))

    seen: set[str] = set()
    result: list[str] = []
    for action in actions:
        if not action or action in seen:
            continue
        seen.add(action)
        result.append(action)
    return result


def build_attempts_from_actions(
    profile: str,
    payload: dict[str, Any],
    action_map: dict[str, Callable[[], AttemptSpec | None]],
) -> list[AttemptSpec]:
    planned = plan_remediation_actions(profile, payload)
    attempts: list[AttemptSpec] = []
    for action in planned:
        factory = action_map.get(action)
        if factory is None:
            continue
        attempt = factory()
        if attempt is None:
            continue
        attempts.append(attempt)
    return attempts
