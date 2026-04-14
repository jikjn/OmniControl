from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal

from omnicontrol.runtime.contracts import SMOKE_CONTRACTS
from omnicontrol.runtime.kb import PROFILE_METADATA, find_matches, secondary_profile_specs
from omnicontrol.runtime.orchestrator import AttemptSpec, OrchestratorSpec, PreflightCheck, run_orchestrator


PivotKind = Literal["bootstrap", "entrypoint", "control_plane"]
PivotBuilder = Callable[[dict[str, Any]], tuple[list["PivotCandidate"], list[AttemptSpec]]]


@dataclass(slots=True)
class PivotCandidate:
    action: str
    pivot_kind: PivotKind
    reason: str
    next_control_plane: str | None = None
    next_profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_PIVOTS_BY_BLOCKER: dict[str, list[PivotCandidate]] = {
    "license": [
        PivotCandidate(
            action="switch_to_tooling_plane",
            pivot_kind="control_plane",
            reason="Switch to vendor tooling that can validate configuration and environment without the main runtime path.",
        ),
        PivotCandidate(
            action="bootstrap_license_tooling",
            pivot_kind="bootstrap",
            reason="Pivot to vendor license tooling before retrying the main control plane.",
        ),
        PivotCandidate(
            action="switch_to_shell_environment",
            pivot_kind="entrypoint",
            reason="Bootstrap the vendor shell environment and retry from a lower-level entrypoint.",
        ),
    ],
    "profile": [
        PivotCandidate(
            action="switch_to_tooling_plane",
            pivot_kind="control_plane",
            reason="Use vendor tooling to validate available profiles and shell setup before retrying the main client.",
        ),
        PivotCandidate(
            action="switch_to_shell_environment",
            pivot_kind="entrypoint",
            reason="Retry inside the vendor shell environment so profile resolution uses the vendor defaults.",
        ),
        PivotCandidate(
            action="switch_to_secondary_service",
            pivot_kind="control_plane",
            reason="Switch to a secondary vendor service or station instead of the primary client entrypoint.",
        ),
    ],
    "timeout": [
        PivotCandidate(
            action="reduce_scope_entrypoint",
            pivot_kind="entrypoint",
            reason="Use a smaller-scope entrypoint to confirm the runtime can start.",
        ),
        PivotCandidate(
            action="drop_project_context",
            pivot_kind="entrypoint",
            reason="Drop the heavier project context and retry on the bare engine/runtime.",
        ),
        PivotCandidate(
            action="switch_to_secondary_entrypoint",
            pivot_kind="entrypoint",
            reason="Switch to a different vendor entrypoint with a narrower startup path.",
        ),
    ],
    "runtime": [
        PivotCandidate(
            action="switch_to_tooling_plane",
            pivot_kind="control_plane",
            reason="Use lighter vendor tooling to confirm a secondary control plane is still executable.",
        ),
        PivotCandidate(
            action="switch_to_shell_environment",
            pivot_kind="entrypoint",
            reason="Bootstrap the vendor runtime environment before retrying.",
        ),
        PivotCandidate(
            action="switch_to_secondary_entrypoint",
            pivot_kind="entrypoint",
            reason="Try a secondary vendor entrypoint instead of repeating the same failing startup path.",
        ),
        PivotCandidate(
            action="drop_project_context",
            pivot_kind="entrypoint",
            reason="Remove surrounding project/application context and retry the core runtime only.",
        ),
    ],
}


DEFAULT_PIVOTS_BY_SOFTWARE_TYPE: dict[str, list[PivotCandidate]] = {
    "structured_api_sdk": [
        PivotCandidate(
            action="switch_to_tooling_plane",
            pivot_kind="control_plane",
            reason="Use vendor environment and administrative tools to validate the stack before the main SDK client.",
        ),
        PivotCandidate(
            action="switch_to_shell_environment",
            pivot_kind="entrypoint",
            reason="Structured SDKs often need vendor batch setup before client commands behave correctly.",
        ),
        PivotCandidate(
            action="switch_to_secondary_service",
            pivot_kind="control_plane",
            reason="Retry on a station or secondary service plane instead of the main client.",
        ),
        PivotCandidate(
            action="bootstrap_license_tooling",
            pivot_kind="bootstrap",
            reason="Use vendor license tooling to normalize prerequisites before retrying.",
        ),
    ],
    "native_sdk_heavy_desktop": [
        PivotCandidate(
            action="switch_to_tooling_plane",
            pivot_kind="control_plane",
            reason="Use vendor shell tooling instead of the heavy NXOpen runtime to confirm a lighter control plane still works.",
        ),
        PivotCandidate(
            action="bootstrap_license_tooling",
            pivot_kind="bootstrap",
            reason="Heavy native SDKs often fail before the app starts when license prerequisites are not satisfied.",
        ),
        PivotCandidate(
            action="switch_to_shell_environment",
            pivot_kind="entrypoint",
            reason="Retry inside the vendor command shell rather than the raw executable environment.",
        ),
        PivotCandidate(
            action="switch_to_secondary_entrypoint",
            pivot_kind="entrypoint",
            reason="Switch to a lighter vendor tool instead of the primary automation entrypoint.",
        ),
    ],
    "game_engine_heavy_desktop": [
        PivotCandidate(
            action="switch_to_tooling_plane",
            pivot_kind="control_plane",
            reason="Use a lighter engine tool to verify the installed runtime before retrying the full editor path.",
        ),
        PivotCandidate(
            action="drop_project_context",
            pivot_kind="entrypoint",
            reason="Game engines frequently need a projectless commandlet path when the full editor path is too heavy.",
        ),
        PivotCandidate(
            action="reduce_scope_entrypoint",
            pivot_kind="entrypoint",
            reason="Reduce scope to a smaller tool or help path to verify the engine runtime itself is healthy.",
        ),
        PivotCandidate(
            action="switch_to_secondary_entrypoint",
            pivot_kind="entrypoint",
            reason="Use a secondary engine entrypoint that avoids the full GUI/editor boot path.",
        ),
    ],
}


def plan_pivot_candidates(profile: str, payload: dict[str, Any]) -> list[PivotCandidate]:
    strategy = payload.get("strategy", {})
    blocker_types = strategy.get("blocker_types", [])
    software_type = PROFILE_METADATA.get(profile, {}).get("software_type")

    actions: list[PivotCandidate] = []
    actions.extend(_metadata_profile_candidates(profile))
    solution = _best_solution_for(profile, payload)
    actions.extend(_solution_candidates(solution))
    for blocker_type in blocker_types:
        actions.extend(DEFAULT_PIVOTS_BY_BLOCKER.get(blocker_type, []))
    if software_type:
        actions.extend(DEFAULT_PIVOTS_BY_SOFTWARE_TYPE.get(software_type, []))

    seen: set[str] = set()
    result: list[PivotCandidate] = []
    for candidate in actions:
        if candidate.action in seen:
            continue
        seen.add(candidate.action)
        result.append(candidate)
    result.sort(key=lambda candidate: _candidate_priority(profile, candidate), reverse=True)
    return result


def _metadata_profile_candidates(profile: str) -> list[PivotCandidate]:
    candidates: list[PivotCandidate] = []
    for spec in secondary_profile_specs(profile):
        action = spec.get("action")
        secondary_profile = spec.get("profile")
        if not action or not secondary_profile:
            continue
        candidates.append(
            PivotCandidate(
                action=action,
                pivot_kind=_pivot_kind_for_action(action),
                reason=spec.get("reason")
                or f"Switch to related profile {secondary_profile} to verify a lighter sibling control plane.",
                next_profile=secondary_profile,
            )
        )
    return candidates


def _pivot_kind_for_action(action: str) -> PivotKind:
    if "tooling_plane" in action or "secondary_service" in action:
        return "control_plane"
    if "license" in action:
        return "bootstrap"
    return "entrypoint"


def _candidate_priority(profile: str, candidate: PivotCandidate) -> tuple[int, int, int, str]:
    contract = SMOKE_CONTRACTS.get(profile)
    mode = contract.mode if contract is not None else "read"
    kind_weight = {"entrypoint": 3, "bootstrap": 2, "control_plane": 1}.get(candidate.pivot_kind, 0)
    action_weight = _action_priority(mode, candidate.action)
    write_preserving = 0
    if mode == "write" and candidate.next_profile:
        next_contract = SMOKE_CONTRACTS.get(candidate.next_profile)
        if next_contract is not None and next_contract.mode == "write":
            write_preserving = 1
    return (action_weight, kind_weight, write_preserving, candidate.action)


def _action_priority(mode: str, action: str) -> int:
    if mode == "write":
        if action == "drop_project_context":
            return 600
        if action == "switch_to_secondary_entrypoint":
            return 550
        if action == "switch_to_shell_environment":
            return 500
        if action == "reduce_scope_entrypoint":
            return 450
        if action == "bootstrap_license_tooling":
            return 300
        if action == "switch_to_tooling_plane":
            return 200
        if action == "switch_to_secondary_service":
            return 150
    if action == "switch_to_tooling_plane":
        return 500
    if action == "bootstrap_license_tooling":
        return 450
    if action == "switch_to_shell_environment":
        return 400
    if action == "switch_to_secondary_entrypoint":
        return 350
    if action == "drop_project_context":
        return 300
    if action == "reduce_scope_entrypoint":
        return 250
    if action == "switch_to_secondary_service":
        return 200
    return 100


def build_pivot_attempts_from_actions(
    profile: str,
    payload: dict[str, Any],
    action_map: dict[str, Callable[[], AttemptSpec | None]],
) -> tuple[list[PivotCandidate], list[AttemptSpec]]:
    candidates = plan_pivot_candidates(profile, payload)
    attempts: list[AttemptSpec] = []
    for candidate in candidates:
        factory = action_map.get(candidate.action)
        if factory is None:
            continue
        attempt = factory()
        if attempt is None:
            continue
        attempts.append(attempt)
    return candidates, attempts


def run_with_strategy_pivots(
    *,
    profile: str,
    preflight: list[PreflightCheck],
    primary_attempts: list[AttemptSpec],
    pivot_builder: PivotBuilder | None = None,
) -> dict[str, Any]:
    primary_result = run_orchestrator(
        OrchestratorSpec(
            profile=profile,
            preflight=preflight,
            attempts=primary_attempts,
        )
    )
    primary_orchestration = _normalize_orchestration(primary_result.get("orchestration", {}), phase="primary")
    primary_result["orchestration"] = primary_orchestration

    if pivot_builder is None or primary_result.get("status") not in {"blocked", "error"}:
        return primary_result

    candidates, pivot_attempts = pivot_builder(primary_result)
    primary_orchestration["pivot_candidates"] = [candidate.to_dict() for candidate in candidates]
    if not pivot_attempts:
        primary_orchestration["pivoted"] = False
        return primary_result

    pivot_result = run_orchestrator(
        OrchestratorSpec(
            profile=profile,
            attempts=pivot_attempts,
        )
    )
    pivot_orchestration = _normalize_orchestration(pivot_result.get("orchestration", {}), phase="pivot")
    merged_orchestration = _merge_orchestration(primary_orchestration, pivot_orchestration)
    merged_orchestration["pivoted"] = True
    merged_orchestration["pivot_candidates"] = [candidate.to_dict() for candidate in candidates]

    if pivot_result.get("status") in {"ok", "partial"}:
        if pivot_result.get("status") == "partial":
            blockers = sorted(
                {
                    *primary_result.get("blockers", []),
                    *pivot_result.get("blockers", []),
                }
            )
            if blockers:
                pivot_result["blockers"] = blockers
        pivot_result["orchestration"] = merged_orchestration
        return pivot_result

    blockers = sorted(
        {
            *primary_result.get("blockers", []),
            *pivot_result.get("blockers", []),
        }
    )
    result: dict[str, Any] = {
        "status": "blocked" if blockers else pivot_result.get("status", primary_result.get("status", "error")),
        "orchestration": merged_orchestration,
    }
    if blockers:
        result["blockers"] = blockers
    if result["status"] == "error":
        result["error"] = pivot_result.get("error") or primary_result.get("error") or "All pivot attempts failed."
    return result


def _normalize_orchestration(orchestration: dict[str, Any], *, phase: str) -> dict[str, Any]:
    normalized = {
        "preflight": list(orchestration.get("preflight", [])),
        "attempts": [],
        "selected_attempt": orchestration.get("selected_attempt"),
        "selected_phase": phase if orchestration.get("selected_attempt") else None,
        "pivoted": orchestration.get("pivoted", False),
        "pivot_candidates": list(orchestration.get("pivot_candidates", [])),
    }
    for attempt in orchestration.get("attempts", []):
        item = dict(attempt)
        item.setdefault("phase", phase)
        normalized["attempts"].append(item)
    return normalized


def _merge_orchestration(primary: dict[str, Any], pivot: dict[str, Any]) -> dict[str, Any]:
    selected_attempt = pivot.get("selected_attempt") or primary.get("selected_attempt")
    selected_phase = "pivot" if pivot.get("selected_attempt") else primary.get("selected_phase")
    return {
        "preflight": list(primary.get("preflight", [])),
        "attempts": [*primary.get("attempts", []), *pivot.get("attempts", [])],
        "selected_attempt": selected_attempt,
        "selected_phase": selected_phase,
        "pivoted": bool(primary.get("pivot_candidates")),
        "pivot_candidates": list(primary.get("pivot_candidates", [])),
    }


def _best_solution_for(profile: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    for case in find_matches(profile, payload):
        solution = case.get("solution")
        if solution:
            return solution
    return None


def _solution_candidates(solution: dict[str, Any] | None) -> list[PivotCandidate]:
    if not solution:
        return []
    actions = solution.get("remediation_actions", [])
    return [
        PivotCandidate(
            action=action,
            pivot_kind="entrypoint",
            reason="Reapply a previously verified strategy for a similar blocked case.",
        )
        for action in actions
        if action
    ]
