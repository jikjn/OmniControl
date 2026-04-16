from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


SmokeStatus = Literal["ok", "partial", "blocked", "error"]


@dataclass(slots=True)
class ConditionSpec:
    key: str
    op: Literal["truthy", "equals", "contains", "nonempty"] = "truthy"
    expected: Any = None
    label: str | None = None

    def evaluate(self, payload: dict[str, Any]) -> tuple[bool, str]:
        value = payload.get(self.key)
        label = self.label or self.key
        if self.op == "truthy":
            return bool(value), f"{label} should be truthy"
        if self.op == "nonempty":
            ok = value is not None and value != "" and value != []
            return ok, f"{label} should be non-empty"
        if self.op == "equals":
            return value == self.expected, f"{label} should equal {self.expected!r}"
        if self.op == "contains":
            ok = value is not None and str(self.expected) in str(value)
            return ok, f"{label} should contain {self.expected!r}"
        return False, f"Unsupported op {self.op}"


@dataclass(slots=True)
class RecoveryHint:
    action: str
    reason: str


@dataclass(slots=True)
class SmokeContract:
    profile: str
    mode: Literal["read", "write", "diagnose"]
    required: list[ConditionSpec] = field(default_factory=list)
    desired: list[ConditionSpec] = field(default_factory=list)
    evidence_keys: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructuredSmokeResult:
    profile: str
    mode: str
    status: SmokeStatus
    raw_status: str
    required_passed: list[str]
    required_failed: list[str]
    desired_passed: list[str]
    desired_failed: list[str]
    blockers: list[str]
    blocker_types: list[str]
    recovery_hints: list[RecoveryHint]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["recovery_hints"] = [asdict(item) for item in self.recovery_hints]
        return data


BLOCKER_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("license", ("license port", "ufun", "license", "dsls")),
    ("profile", ("connection profile", "profile is required", "logon")),
    ("focus", ("focus", "foreground", "window not found")),
    ("dependency", ("not found", "missing", "not listening")),
    ("timeout", ("timed out", "timeout")),
    ("runtime", ("initialize", "startup", "failed to initialize")),
]


BLOCKER_HINTS: dict[str, list[RecoveryHint]] = {
    "license": [
        RecoveryHint("probe_license_service", "Check whether the required local or remote license port is listening."),
        RecoveryHint("validate_license_env", "Verify environment variables and license configuration files before running the app."),
    ],
    "profile": [
        RecoveryHint("discover_profiles", "List available connection or execution profiles before invoking the command."),
        RecoveryHint("supply_profile", "Retry the action with an explicit profile argument."),
    ],
    "focus": [
        RecoveryHint("force_focus", "Bring the target window to the foreground before sending input."),
        RecoveryHint("attach_existing_instance", "Attach to the existing window instead of assuming a new one appears."),
    ],
    "dependency": [
        RecoveryHint("preflight_dependencies", "Check required executables, ports and runtime files before the action."),
    ],
    "timeout": [
        RecoveryHint("increase_wait_budget", "Wait longer for the app to initialize or page to load."),
        RecoveryHint("reduce_scope", "Retry with a smaller target action to isolate where the latency comes from."),
    ],
    "runtime": [
        RecoveryHint("capture_boot_diagnostics", "Collect startup diagnostics and environment values before rerunning."),
    ],
}


def evaluate_contract(payload: dict[str, Any], contract: SmokeContract) -> StructuredSmokeResult:
    raw_status = str(payload.get("status", "error"))
    blockers = list(payload.get("blockers", []))
    blockers.extend(infer_blockers(payload))
    blocker_types = sorted({classify_blocker(item) for item in blockers if item})

    required_passed, required_failed = _evaluate_group(payload, contract.required)
    desired_passed, desired_failed = _evaluate_group(payload, contract.desired)

    if raw_status == "ok":
        if required_failed:
            status: SmokeStatus = "partial"
        elif desired_failed:
            status = "partial"
        else:
            status = "ok"
    elif raw_status == "partial":
        status = "partial"
    elif blockers:
        status = "blocked"
    else:
        status = "error"

    recovery_hints = []
    for blocker_type in blocker_types:
        recovery_hints.extend(BLOCKER_HINTS.get(blocker_type, []))
    if status == "partial" and desired_failed:
        recovery_hints.append(
            RecoveryHint(
                "strengthen_verification_or_focus",
                "The action completed partially; add stronger state verification or improve focus/activation handling.",
            )
        )

    evidence = {
        key: payload.get(key)
        for key in contract.evidence_keys
        if key in payload
    }

    return StructuredSmokeResult(
        profile=contract.profile,
        mode=contract.mode,
        status=status,
        raw_status=raw_status,
        required_passed=required_passed,
        required_failed=required_failed,
        desired_passed=desired_passed,
        desired_failed=desired_failed,
        blockers=sorted({item for item in blockers if item}),
        blocker_types=blocker_types,
        recovery_hints=_dedupe_hints(recovery_hints),
        evidence=evidence,
    )


def infer_blockers(payload: dict[str, Any]) -> list[str]:
    texts = []
    for key in ("error", "sample_output", "attempt_output", "stderr", "stdout"):
        value = payload.get(key)
        if value:
            texts.append(str(value))
    blockers: list[str] = []
    for text in texts:
        lowered = text.lower()
        if "failed to initialize ufun" in lowered:
            blockers.append("UFUN initialization failed")
        if "license port" in lowered:
            blockers.append("license port issue")
        if "connection profile is required" in lowered:
            blockers.append("connection profile is required")
        if "not listening" in lowered:
            blockers.append("required service port is not listening")
    return blockers


def classify_blocker(text: str) -> str:
    lowered = text.lower()
    for blocker_type, patterns in BLOCKER_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return blocker_type
    return "runtime"


def _evaluate_group(payload: dict[str, Any], specs: list[ConditionSpec]) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []
    for spec in specs:
        ok, description = spec.evaluate(payload)
        if ok:
            passed.append(description)
        else:
            failed.append(description)
    return passed, failed


def _dedupe_hints(hints: list[RecoveryHint]) -> list[RecoveryHint]:
    seen: set[tuple[str, str]] = set()
    result: list[RecoveryHint] = []
    for hint in hints:
        key = (hint.action, hint.reason)
        if key in seen:
            continue
        seen.add(key)
        result.append(hint)
    return result
