from __future__ import annotations

from dataclasses import asdict, dataclass, field
import copy
from typing import Any, Callable


@dataclass(slots=True)
class PreflightResult:
    name: str
    ok: bool
    detail: str
    required: bool = True
    blocker: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AttemptResult:
    name: str
    strategy: str
    status: str
    detail: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["payload"] = self.payload
        return data


@dataclass(slots=True)
class PreflightCheck:
    name: str
    run: Callable[[], PreflightResult]


@dataclass(slots=True)
class AttemptSpec:
    name: str
    strategy: str
    run: Callable[[], dict[str, Any]]


@dataclass(slots=True)
class OrchestratorSpec:
    profile: str
    preflight: list[PreflightCheck] = field(default_factory=list)
    attempts: list[AttemptSpec] = field(default_factory=list)


def run_orchestrator(spec: OrchestratorSpec) -> dict[str, Any]:
    preflight_results: list[PreflightResult] = []
    for check in spec.preflight:
        try:
            preflight_results.append(check.run())
        except Exception as error:
            preflight_results.append(
                PreflightResult(
                    name=check.name,
                    ok=False,
                    detail=str(error),
                    required=True,
                    blocker=str(error),
                )
            )

    required_failures = [item for item in preflight_results if item.required and not item.ok]
    orchestration = {
        "preflight": [item.to_dict() for item in preflight_results],
        "attempts": [],
        "selected_attempt": None,
    }

    if required_failures:
        blockers = [item.blocker or item.detail for item in required_failures]
        return {
            "status": "blocked",
            "blockers": blockers,
            "orchestration": orchestration,
        }

    blocked_payloads: list[dict[str, Any]] = []
    for attempt in spec.attempts:
        try:
            payload = attempt.run()
            status = str(payload.get("status", "error"))
            detail = payload.get("error")
        except Exception as error:
            payload = {"status": "error", "error": str(error)}
            status = "error"
            detail = str(error)

        orchestration["attempts"].append(
            AttemptResult(
                name=attempt.name,
                strategy=attempt.strategy,
                status=status,
                detail=detail,
                payload=copy.deepcopy(payload),
            ).to_dict()
        )

        if status in {"ok", "partial"}:
            orchestration["selected_attempt"] = attempt.name
            payload["orchestration"] = orchestration
            return payload

        if status == "blocked":
            blocked_payloads.append(payload)

    if blocked_payloads:
        merged_blockers: list[str] = []
        for payload in blocked_payloads:
            merged_blockers.extend(payload.get("blockers", []))
            if payload.get("error"):
                merged_blockers.append(str(payload["error"]))
        return {
            "status": "blocked",
            "blockers": sorted(set(item for item in merged_blockers if item)),
            "orchestration": orchestration,
        }

    return {
        "status": "error",
        "error": "All attempts failed.",
        "orchestration": orchestration,
    }


def path_exists_check(name: str, path: str, *, required: bool = True) -> PreflightResult:
    from pathlib import Path

    exists = Path(path).exists()
    detail = f"{path} exists" if exists else f"{path} missing"
    return PreflightResult(
        name=name,
        ok=exists,
        detail=detail,
        required=required,
        blocker=None if exists else detail,
        evidence={"path": path},
    )
