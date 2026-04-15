# Phase 1: Runtime Registry & Evidence Foundation - Pattern Map

**Mapped:** 2026-04-15
**Scope basis:** inferred from `.planning/ROADMAP.md` Phase 1 and `.planning/REQUIREMENTS.md` (`RTF-01`, `RTF-02`, `RTF-04`, `VER-01`, `VER-02`)
**Files analyzed:** 10 inferred Phase 1 targets
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `omnicontrol/runtime/registry.py` | utility | request-response | `omnicontrol/adapters/catalog.py` | exact |
| `omnicontrol/runtime/paths.py` | utility | file-I/O | `omnicontrol/runtime/staging.py` | exact |
| `omnicontrol/runtime/evidence.py` | utility | transform | `omnicontrol/runtime/strategy.py` | role-match |
| `omnicontrol/models.py` | model | transform | `omnicontrol/models.py` | exact |
| `omnicontrol/runtime/live_smoke.py` | service | request-response | `omnicontrol/runtime/live_smoke.py` | exact |
| `omnicontrol/runtime/contracts.py` | config | transform | `omnicontrol/runtime/contracts.py` | exact |
| `omnicontrol/runtime/kb.py` | service | file-I/O | `omnicontrol/runtime/kb.py` | exact |
| `tests/test_runtime_registry.py` | test | request-response | `tests/test_kb.py` | role-match |
| `tests/test_runtime_paths.py` | test | file-I/O | `tests/test_staging.py` | exact |
| `tests/test_runtime_evidence.py` | test | transform | `tests/test_strategy.py` | exact |

## Pattern Assignments

### `omnicontrol/runtime/registry.py` (utility, request-response)

**Primary analog:** `omnicontrol/adapters/catalog.py`

**Typed catalog dataclass pattern** ([omnicontrol/adapters/catalog.py](/Users/daizhaorong/OmniControl/omnicontrol/adapters/catalog.py:6))
```python
@dataclass(frozen=True, slots=True)
class AdapterProfile:
    name: str
    priority: float
    default_state_model: str
    default_verification: tuple[str, ...]
    summary: str
```

**Static registry table pattern** ([omnicontrol/adapters/catalog.py](/Users/daizhaorong/OmniControl/omnicontrol/adapters/catalog.py:15))
```python
ADAPTER_PROFILES: dict[str, AdapterProfile] = {
    "native_script": AdapterProfile(
        name="native_script",
        priority=0.95,
        default_state_model="backend_state",
        default_verification=("backend_query", "command_exit"),
        summary="Official scripting, SDK, COM, AppleScript or app-native automation.",
    ),
```

**Secondary analog for richer metadata rows:** `omnicontrol/runtime/kb.py`

**Metadata table shape** ([omnicontrol/runtime/kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:12))
```python
PROFILE_METADATA: dict[str, dict[str, Any]] = {
    "finder-open": {"product_key": "finder", "software_type": "macos_accessibility_desktop", "target_kind": "desktop", "platform": "macos", "control_planes": ["native_script", "accessibility"], "tags": ["finder", "macos", "open"]},
```

**Derived defaults enrichment pattern** ([omnicontrol/runtime/kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:371))
```python
for _profile_name, _meta in PROFILE_METADATA.items():
    _meta.setdefault("invocation_context", PROFILE_INVOCATION_CONTEXT.get(_profile_name, "none"))
    _meta.setdefault(
        "accepted_invocation_contexts",
        list(PROFILE_ACCEPTED_INVOCATION_CONTEXTS.get(_profile_name, (_meta["invocation_context"],))),
    )
```

**Use for Phase 1:** build a typed macOS app/profile registry as a module-level source of truth, not scattered per-profile dictionaries in `live_smoke.py`.

---

### `omnicontrol/runtime/paths.py` (utility, file-I/O)

**Primary analog:** `omnicontrol/runtime/staging.py`

**Dataclass result pattern** ([omnicontrol/runtime/staging.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/staging.py:8))
```python
@dataclass(slots=True)
class StagingInfo:
    original_path: str
    staged_path: str
    used_staging: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
```

**Filesystem helper pattern** ([omnicontrol/runtime/staging.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/staging.py:27))
```python
def ensure_ascii_staging(path: Path, staging_root: Path, *, staged_name: str = "staged-target") -> StagingInfo:
    staging_root.mkdir(parents=True, exist_ok=True)
```

**Secondary analog:** `omnicontrol/runtime/invocation.py`

**Safe materialization into caller-owned root** ([omnicontrol/runtime/invocation.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/invocation.py:77))
```python
def materialize_script_payload(
    payload: str,
    output_dir: Path,
    *,
    stem: str = "payload",
    suffix: str = ".txt",
    reason: str | None = None,
    encoding: str = "utf-8",
) -> ScriptPayload:
    output_dir.mkdir(parents=True, exist_ok=True)
```

**Current anti-pattern to replace:** cwd-bound roots in `live_smoke.py` and `kb.py`

**Examples**:
- [omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:345)
- [omnicontrol/runtime/kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:383)

```python
output_dir = Path.cwd() / "smoke-output" / "finder-open"
return Path.cwd() / "knowledge" / "kb.json"
```

**Use for Phase 1:** centralize runtime root resolution in one helper module and return typed path objects or dataclasses; then inject those paths into `live_smoke.py` and `kb.py`.

---

### `omnicontrol/runtime/evidence.py` (utility, transform)

**Primary analog:** `omnicontrol/runtime/strategy.py`

**Structured result dataclass pattern** ([omnicontrol/runtime/strategy.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/strategy.py:48))
```python
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
```

**Evidence projection pattern** ([omnicontrol/runtime/strategy.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/strategy.py:139))
```python
evidence = {
    key: payload.get(key)
    for key in contract.evidence_keys
    if key in payload
}
```

**Secondary analog:** `omnicontrol/runtime/live_smoke.py`

**Finalize payload before persistence** ([omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:322))
```python
def _finalize_payload(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    contract = SMOKE_CONTRACTS.get(profile)
    if contract is None:
        return payload
    structured = evaluate_contract(payload, contract)
    payload["raw_status"] = payload.get("status")
    payload["status"] = structured.status
    payload["strategy"] = structured.to_dict()
    return payload
```

**Current per-profile report writing pattern** ([omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:354))
```python
report_path = output_dir / "result.json"
report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
payload["report_path"] = str(report_path)
```

**Use for Phase 1:** move report/evidence shaping into one reusable writer that returns a stable evidence bundle contract and artifact index instead of repeating ad hoc `result.json` writes across profiles.

---

### `omnicontrol/models.py` (model, transform)

**Analog:** `omnicontrol/models.py`

**Shared cross-layer dataclass pattern** ([omnicontrol/models.py](/Users/daizhaorong/OmniControl/omnicontrol/models.py:76))
```python
@dataclass(slots=True)
class Capability:
    name: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    structured: bool = True
```

**Serialization helper pattern** ([omnicontrol/models.py](/Users/daizhaorong/OmniControl/omnicontrol/models.py:64))
```python
def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
```

**Use for Phase 1:** if the registry, runtime roots, or evidence bundle are consumed across CLI/runtime/tests, model them here as `@dataclass(slots=True)` values plus `to_dict()`/`to_jsonable()` support.

---

### `omnicontrol/runtime/live_smoke.py` (service, request-response)

**Analog:** `omnicontrol/runtime/live_smoke.py`

**Dispatcher boundary pattern** ([omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:64))
```python
def run_smoke(
    profile: str,
    *,
    source: str | None = None,
    output: str | None = None,
    query: str | None = None,
    url: str | None = None,
```

**Per-profile workflow boundary** ([omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:419))
```python
payload = run_with_strategy_pivots(
    profile="safari-dom-write",
    preflight=[],
    primary_attempts=[
        AttemptSpec(name="safari_dom_write", strategy="direct_script", run=_attempt),
    ],
    pivot_builder=_plan_safari_write_pivots,
)
payload["profile"] = "safari-dom-write"
payload = _finalize_payload("safari-dom-write", payload)
```

**Sidecar output isolation pattern** ([omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:2246))
```python
secondary_output_dir = output_dir / "sidecars" / secondary_profile
```

**Sidecar payload merge pattern** ([omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:2325))
```python
success = secondary_payload.get("status") in {"ok", "partial"}
payload: dict[str, Any] = {
    "status": "partial" if success else "blocked",
    "secondary_action": "related_profile_control_plane",
    "secondary_action_ok": success,
    "secondary_profile": secondary_profile,
    "secondary_profile_report_path": secondary_payload.get("report_path"),
```

**Use for Phase 1:** keep `run_smoke()` as the orchestration entrypoint, but push registry lookup, root resolution, and evidence writing into focused helpers rather than expanding repeated branches.

---

### `omnicontrol/runtime/contracts.py` (config, transform)

**Analog:** `omnicontrol/runtime/contracts.py`

**Declarative contract table pattern** ([omnicontrol/runtime/contracts.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/contracts.py:6))
```python
SMOKE_CONTRACTS: dict[str, SmokeContract] = {
    "finder-open": SmokeContract(
        profile="finder-open",
        mode="read",
        required=[
            ConditionSpec("finder_running"),
            ConditionSpec("window_name", "nonempty"),
        ],
        evidence_keys=["resolved_path", "window_name"],
    ),
```

**Use for Phase 1:** if evidence bundle/report fields become standardized, keep the declarative mapping style here instead of adding profile-specific conditionals in `live_smoke.py`.

---

### `omnicontrol/runtime/kb.py` (service, file-I/O)

**Analog:** `omnicontrol/runtime/kb.py`

**Stable case record structure** ([omnicontrol/runtime/kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:407))
```python
case = {
    "case_id": case_id,
    "lookup": lookup,
    "summary": {
        "last_status": payload.get("status"),
        "times_seen": 0,
        "times_blocked": 0,
        "times_solved": 0,
```

**Evidence/report backreference pattern** ([omnicontrol/runtime/kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:430))
```python
case["blocked_cases"].append(
    {
        "run_id": _run_id(),
        "ts": _now(),
        "raw_status": payload.get("raw_status", payload.get("status")),
        "blockers": payload.get("strategy", {}).get("blockers", payload.get("blockers", [])),
        "evidence": payload.get("strategy", {}).get("evidence", {}),
        "report_path": payload.get("report_path"),
    }
)
```

**Use for Phase 1:** runtime evidence/report schema should stay compatible with KB learning, since KB already expects `status`, `raw_status`, `strategy.evidence`, and `report_path`.

---

### `tests/test_runtime_registry.py` (test, request-response)

**Primary analog:** `tests/test_kb.py`

**Patch-in metadata table + assert derived behavior** ([tests/test_kb.py](/Users/daizhaorong/OmniControl/tests/test_kb.py:22))
```python
with patch.dict(
    PROFILE_METADATA,
    {
        "demo-workflow": {
            "product_key": "demo_suite",
            "software_type": "demo_type",
```

**Use for Phase 1:** test registry lookups with `patch.dict(...)` over registry tables and assert fallback/derived metadata behavior without touching live OS automation.

---

### `tests/test_runtime_paths.py` (test, file-I/O)

**Primary analog:** `tests/test_staging.py`

**TemporaryDirectory + Path assertions** ([tests/test_staging.py](/Users/daizhaorong/OmniControl/tests/test_staging.py:15))
```python
with tempfile.TemporaryDirectory() as tmp_dir:
    root = Path(tmp_dir)
    src = root / "测试.txt"
    src.write_text("hello", encoding="utf-8")
```

**Secondary analog:** `tests/test_invocation.py`

**Materialization-to-disk assertion style** ([tests/test_invocation.py](/Users/daizhaorong/OmniControl/tests/test_invocation.py:23))
```python
with tempfile.TemporaryDirectory() as tmp_dir:
    result = prepare_script_payload(
        payload,
        Path(tmp_dir),
        stem="demo payload",
        suffix=".py",
        prefer_file=True,
    )
```

**Use for Phase 1:** verify runtime root creation, artifact/report path allocation, and cwd-independence with temp directories and exact path assertions.

---

### `tests/test_runtime_evidence.py` (test, transform)

**Primary analog:** `tests/test_strategy.py`

**Payload-in, structured-result-out assertions** ([tests/test_strategy.py](/Users/daizhaorong/OmniControl/tests/test_strategy.py:10))
```python
payload = {
    "status": "ok",
    "exists": True,
    "zip_ok": True,
    "output": "out.docx",
}
result = evaluate_contract(payload, SMOKE_CONTRACTS["word-write"])
```

**Secondary analog:** `tests/test_live_smoke_helpers.py`

**Evidence/backreference assertions on sidecar payloads** ([tests/test_live_smoke_helpers.py](/Users/daizhaorong/OmniControl/tests/test_live_smoke_helpers.py:98))
```python
with patch(
    "omnicontrol.runtime.live_smoke.run_smoke",
    return_value={
        "status": "partial",
        "blockers": ["editor help only"],
        "report_path": str(Path(tmp) / "sidecar-result.json"),
```

**Use for Phase 1:** test evidence bundle assembly as pure functions first; only use mocked `run_smoke()` or helper-level tests for wiring.

## Shared Patterns

### Static Registry Tables
**Sources:** [omnicontrol/adapters/catalog.py](/Users/daizhaorong/OmniControl/omnicontrol/adapters/catalog.py:15), [omnicontrol/runtime/kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:12)

Copy the repo’s pattern of:
- frozen/slotted dataclass row types when the schema is stable
- module-level `dict[str, ...]` registries keyed by profile/app id
- a small enrichment pass with `setdefault(...)` for derived defaults

### Filesystem Ownership
**Sources:** [omnicontrol/runtime/staging.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/staging.py:27), [omnicontrol/runtime/invocation.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/invocation.py:77)

Copy the repo’s pattern of:
- accepting `Path` inputs, not raw cwd-relative strings
- creating directories inside the helper that owns the path
- returning a small dataclass with resolved paths and reason metadata

### Result Normalization
**Sources:** [omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:322), [omnicontrol/runtime/strategy.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/strategy.py:105)

Copy the repo’s pattern of:
- raw payload first
- one normalization pass that rewrites `status`
- attaching structured result data under `strategy`
- selecting evidence fields declaratively from the contract

### Orchestration Boundary
**Sources:** [omnicontrol/runtime/orchestrator.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/orchestrator.py:55), [omnicontrol/runtime/live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:419)

Use `run_smoke()` as the public runtime entrypoint and keep orchestration helpers pure:
```python
payload = run_with_strategy_pivots(...)
payload = _finalize_payload(profile, payload)
```

Do not let registry/path/evidence helpers call CLI code or print directly.

### Structured Failure-As-Data
**Sources:** [omnicontrol/runtime/orchestrator.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/orchestrator.py:87), [omnicontrol/runtime/kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:430)

Keep failures shaped as dictionaries with `status`, `error`, `blockers`, `strategy`, `report_path`, and evidence fields so later persistence and KB reuse stay compatible.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `omnicontrol/runtime/evidence.py` | utility | transform | No dedicated evidence-bundle module exists yet; current logic is split across `live_smoke.py`, `strategy.py`, and `kb.py`. |
| `omnicontrol/runtime/paths.py` | utility | file-I/O | No centralized runtime-root manager exists yet; current path logic is scattered and cwd-bound. |

## Metadata

**Analog search scope:** `omnicontrol/adapters/`, `omnicontrol/models.py`, `omnicontrol/runtime/`, `tests/`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
**Highest-value analogs:** `omnicontrol/adapters/catalog.py`, `omnicontrol/runtime/staging.py`, `omnicontrol/runtime/strategy.py`, `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/kb.py`, `tests/test_staging.py`, `tests/test_strategy.py`, `tests/test_kb.py`
**Current Phase 1 technical gap:** stable runtime roots and evidence writing do not have a single owner; both are repeated across `live_smoke.py` and still depend on `Path.cwd()`.
