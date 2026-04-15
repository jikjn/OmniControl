---
phase: 01-runtime-registry-evidence-foundation
verified: 2026-04-15T07:25:10Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 1: Runtime Registry & Evidence Foundation Verification Report

**Phase Goal:** One typed registry, stable runtime roots, structured evidence outputs.
**Verified:** 2026-04-15T07:25:10Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | User can target supported smoke profiles through one typed registry-backed source of truth. | ✓ VERIFIED | [`omnicontrol/runtime/registry.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/registry.py:8) defines `ProfileDescriptor`, `PROFILE_METADATA`, `PROFILE_REGISTRY`, `list_profile_ids()`, and `profile_choices()`; [`omnicontrol/cli.py`](/Users/daizhaorong/OmniControl/omnicontrol/cli.py:61) derives `smoke` choices from `profile_choices()`. |
| 2 | The `smoke` entrypoint still accepts existing profile IDs while validating them against the shared registry. | ✓ VERIFIED | [`omnicontrol/cli.py`](/Users/daizhaorong/OmniControl/omnicontrol/cli.py:62) uses registry-backed choices; [`omnicontrol/runtime/live_smoke.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:76) rejects unknown profiles via `list_profile_ids()`. |
| 3 | Runtime knowledge and artifact roots resolve independently of the caller's working directory. | ✓ VERIFIED | [`omnicontrol/runtime/paths.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/paths.py:20) computes platform-managed roots from env/home/platform, not `cwd`; [`tests/test_runtime_paths.py`](/Users/daizhaorong/OmniControl/tests/test_runtime_paths.py:12) verifies identical roots across different cwd values. |
| 4 | Explicit caller-owned output overrides still take precedence, and legacy repo-local KB data can still be read during migration. | ✓ VERIFIED | [`omnicontrol/runtime/paths.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/paths.py:70) returns explicit output unchanged; [`omnicontrol/runtime/kb.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:50) falls back to `legacy_kb_path()` when stable KB does not exist; covered by [`tests/test_runtime_paths.py`](/Users/daizhaorong/OmniControl/tests/test_runtime_paths.py:25). |
| 5 | KB persistence no longer depends on direct non-atomic writes. | ✓ VERIFIED | [`omnicontrol/runtime/kb.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:60) writes via `NamedTemporaryFile` and `Path.replace()`. |
| 6 | A canonical structured `result.json` bundle exists and is the shared smoke persistence boundary. | ✓ VERIFIED | [`omnicontrol/runtime/evidence.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/evidence.py:66) implements `write_result_bundle()`; [`omnicontrol/runtime/live_smoke.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:352) routes smoke payload persistence through that writer. |
| 7 | Each structured result bundle includes concrete artifact references and runtime metadata. | ✓ VERIFIED | [`omnicontrol/runtime/evidence.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/evidence.py:13) normalizes artifact keys, and [`omnicontrol/runtime/evidence.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/evidence.py:82) writes `runtime` plus `artifacts[]`; [`tests/test_runtime_evidence.py`](/Users/daizhaorong/OmniControl/tests/test_runtime_evidence.py:13) asserts persisted artifact paths. |
| 8 | Legacy consumers still receive `report_path` and compatible evidence-bearing payload fields during migration. | ✓ VERIFIED | [`omnicontrol/runtime/evidence.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/evidence.py:81) preserves top-level `report_path`; [`omnicontrol/runtime/kb.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:97) records `report_path` and strategy evidence into KB entries; [`tests/test_runtime_evidence.py`](/Users/daizhaorong/OmniControl/tests/test_runtime_evidence.py:38) asserts the legacy contract is preserved. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `omnicontrol/runtime/registry.py` | Typed registry and compatibility metadata views | ✓ VERIFIED | Substantive implementation with dataclass model, metadata enrichment, registry materialization, and query helpers. |
| `omnicontrol/runtime/paths.py` | Stable runtime root and output path policy | ✓ VERIFIED | Platform-aware root resolution plus stable KB/artifact path derivation. |
| `omnicontrol/runtime/evidence.py` | Canonical result bundle writer | ✓ VERIFIED | Writes `result.json`, runtime metadata, `bundle`, and normalized `artifacts[]`. |
| `omnicontrol/runtime/kb.py` | Stable KB persistence and compatibility behavior | ✓ VERIFIED | Uses runtime-managed KB path, legacy fallback reads, and atomic writes. |
| `omnicontrol/runtime/live_smoke.py` | Smoke runtime wired to registry and shared evidence pipeline | ✓ VERIFIED | Validates profile IDs against registry and persists payloads through `write_result_bundle()`. |
| `omnicontrol/cli.py` | Registry-backed smoke CLI surface | ✓ VERIFIED | `smoke` parser derives profile choices from registry. |
| `tests/test_runtime_registry.py` | Registry regression coverage | ✓ VERIFIED | Covers parser choices, IDs, compatibility metadata, and typed descriptors. |
| `tests/test_runtime_paths.py` | Runtime-root regression coverage | ✓ VERIFIED | Covers cwd independence, override precedence, legacy KB reads, and stable save path. |
| `tests/test_runtime_evidence.py` | Result bundle regression coverage | ✓ VERIFIED | Covers canonical fields, runtime metadata, artifact refs, and legacy `report_path`. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `omnicontrol/cli.py` | `omnicontrol/runtime/registry.py` | smoke argument choices | ✓ WIRED | `profile_choices()` imported and used in `smoke.add_argument(...)`. |
| `omnicontrol/runtime/live_smoke.py` | `omnicontrol/runtime/registry.py` | profile validation | ✓ WIRED | `list_profile_ids()` imported and used to reject unknown profiles before dispatch. |
| `omnicontrol/runtime/kb.py` | `omnicontrol/runtime/paths.py` | stable KB path resolution | ✓ WIRED | `kb_path()` delegates to `resolve_runtime_paths()` and reads legacy path only as migration fallback. |
| `omnicontrol/runtime/live_smoke.py` | `omnicontrol/runtime/evidence.py` | shared result writer | ✓ WIRED | `_persist_payload()` calls `write_result_bundle()` for smoke result persistence. |
| `omnicontrol/runtime/kb.py` | evidence payload contract | report-path compatibility | ✓ WIRED | KB records `report_path` and evidence-bearing payload fields produced after shared bundle persistence. |
| `tests/test_runtime_registry.py` | `omnicontrol/runtime/registry.py` | registry assertions | ✓ WIRED | Imports registry helpers and asserts parser choices, IDs, metadata, and descriptor behavior. |
| `tests/test_runtime_paths.py` | `omnicontrol/runtime/paths.py` | runtime path assertions | ✓ WIRED | Imports and exercises `resolve_runtime_paths()`, `resolve_run_output_dir()`, and `legacy_kb_path()`. |
| `tests/test_runtime_evidence.py` | `omnicontrol/runtime/evidence.py` | bundle serialization assertions | ✓ WIRED | Imports `write_result_bundle()` and verifies persisted `result.json` contents. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `omnicontrol/runtime/registry.py` | `PROFILE_REGISTRY` / `PROFILE_METADATA` | `_BASE_PROFILE_METADATA` enriched into typed descriptors | Yes | ✓ FLOWING |
| `omnicontrol/runtime/kb.py` | `kb_path()` / persisted KB JSON | `resolve_runtime_paths()` root policy plus runtime writes | Yes | ✓ FLOWING |
| `omnicontrol/runtime/evidence.py` | `bundle["artifacts"]` / `bundle["runtime"]` | Incoming smoke payload keys plus resolved runtime paths | Yes | ✓ FLOWING |
| `omnicontrol/runtime/live_smoke.py` | persisted smoke payload | profile handler output -> `_finalize_payload()` -> `write_result_bundle()` -> `record_payload()` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Runtime contract tests execute successfully | `.venv/bin/python -m unittest tests.test_runtime_registry tests.test_runtime_paths tests.test_runtime_evidence -v` | 10 tests passed | ✓ PASS |
| Cross-module Phase 1 regressions still hold | `.venv/bin/python -m unittest tests.test_runtime_registry tests.test_runtime_paths tests.test_runtime_evidence tests.test_kb tests.test_full_e2e tests.test_pivots tests.test_remediation tests.test_live_smoke_helpers tests.test_live_smoke_macos -v` | User-supplied session evidence: 53 tests passed, 1 skipped | ✓ PASS |
| Full repository unittest discover remains green after Phase 1 | `.venv/bin/python -m unittest discover -s tests -v` | User-supplied session evidence: 103 tests passed, 10 skipped | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `RTF-01` | 01-01, 01-02 | Typed registry is the single source of truth | ✓ SATISFIED | Registry dataclass/helpers in [`registry.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/registry.py:8), CLI wiring in [`cli.py`](/Users/daizhaorong/OmniControl/omnicontrol/cli.py:61), and registry tests in [`test_runtime_registry.py`](/Users/daizhaorong/OmniControl/tests/test_runtime_registry.py:21). |
| `RTF-02` | 01-01, 01-02 | Runtime state uses stable framework-managed roots | ✓ SATISFIED | Stable root policy in [`paths.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/paths.py:20), KB migration in [`kb.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:46), and path tests in [`test_runtime_paths.py`](/Users/daizhaorong/OmniControl/tests/test_runtime_paths.py:12). |
| `RTF-04` | 01-01, 01-03 | Every run produces a structured evidence bundle | ✓ SATISFIED | Shared writer in [`evidence.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/evidence.py:66) and runtime persistence via [`live_smoke.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:352). |
| `VER-01` | 01-01, 01-03 | Each run writes structured `result.json` | ✓ SATISFIED | `write_result_bundle()` persists `result.json`; runtime and evidence tests assert the file and schema. |
| `VER-02` | 01-01, 01-03 | Reports reference concrete artifact paths | ✓ SATISFIED | `_collect_artifacts()` in [`evidence.py`](/Users/daizhaorong/OmniControl/omnicontrol/runtime/evidence.py:51) plus asserted artifact path coverage in [`test_runtime_evidence.py`](/Users/daizhaorong/OmniControl/tests/test_runtime_evidence.py:13). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `omnicontrol/runtime/live_smoke.py` | 93 | Long `if/elif` dispatch chain remains after registry extraction | ℹ️ Info | Registry is now authoritative for IDs and metadata, but handler dispatch is not yet descriptor-owned. This does not block the Phase 1 goal. |
| `tests/test_live_smoke_macos.py` | 33 | Mocked macOS smoke tests assert `report_path` compatibility but not `artifacts[]` contents | ℹ️ Info | The phase still verifies artifact references through `tests/test_runtime_evidence.py`; the macOS smoke test coverage is narrower than the plan wording. |

### Gaps Summary

No blocking gaps found. The phase goal is achieved in code: registry-backed profile selection is centralized, durable runtime state is detached from `cwd`, and smoke runs persist through a shared structured evidence writer with artifact references.

Residual risks from the disconfirmation pass are non-blocking: smoke handler dispatch still lives in `live_smoke.py` rather than in registry-owned descriptors, and the mocked macOS smoke tests do not themselves assert `artifacts[]` even though artifact-path behavior is covered by the runtime evidence tests.

---

_Verified: 2026-04-15T07:25:10Z_
_Verifier: Claude (gsd-verifier)_
