# Testing Patterns

**Analysis Date:** 2026-04-15

## Test Framework

**Runner:**
- `unittest` from the Python standard library
- Config: Not detected; there is no `pytest.ini`, `tox.ini`, `setup.cfg`, or custom unittest config in `/Users/daizhaorong/OmniControl`

**Assertion Library:**
- `unittest.TestCase` assertions such as `assertEqual`, `assertIn`, `assertTrue`, `assertRaisesRegex`, and `assertIsNotNone`

**Run Commands:**
```bash
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_orchestrator -v
python3 -m unittest discover -s tests
```
- `pyproject.toml` declares `pytest>=8` under `[project.optional-dependencies].dev`, but the checked-in suite in `tests/` is written against `unittest`, not pytest fixtures or markers.

## Test File Organization

**Location:**
- Use a separate top-level `tests/` directory, not co-located test files.
- Keep one test module per production concern, for example:
  - `tests/test_core.py` for `omnicontrol/detector/`, `omnicontrol/planner/`, and scaffold flow
  - `tests/test_orchestrator.py` for `omnicontrol/runtime/orchestrator.py`
  - `tests/test_transports.py` for `omnicontrol/runtime/transports.py`
  - `tests/test_windows_ipc.py` for `omnicontrol/runtime/windows_ipc.py`

**Naming:**
- Name files `test_<module_or_feature>.py`.
- Name classes `<Feature>Tests`, such as `DetectorAndPlannerTests`, `TransportAttemptTests`, and `WindowsIPCHelperTests`.
- Name methods `test_<specific_behavior>`.

**Structure:**
```text
tests/
├── test_adaptive_startup.py
├── test_cdp_target_helpers.py
├── test_core.py
├── test_full_e2e.py
├── test_invocation.py
├── test_kb.py
├── test_live_smoke_helpers.py
├── test_live_smoke_macos.py
├── test_orchestrator.py
├── test_pivots.py
├── test_remediation.py
├── test_staging.py
├── test_strategy.py
├── test_transports.py
└── test_windows_ipc.py
```

## Test Structure

**Suite Organization:**
```python
class OrchestratorTests(unittest.TestCase):
    def test_blocked_when_required_preflight_fails(self) -> None:
        result = run_orchestrator(...)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("dependency missing", result["blockers"])
```
- This pattern from `tests/test_orchestrator.py` is representative of the overall suite.

**Patterns:**
- Use `setUp()` for reusable object construction when a test class exercises stateful collaborators, as in `tests/test_core.py`:
```python
def setUp(self) -> None:
    self.detector = CapabilityDetector()
    self.selector = AdapterSelector()
```
- Use `tempfile.TemporaryDirectory()` for filesystem isolation instead of checked-in fixtures. This appears in `tests/test_core.py`, `tests/test_full_e2e.py`, `tests/test_invocation.py`, `tests/test_live_smoke_helpers.py`, `tests/test_live_smoke_macos.py`, and `tests/test_staging.py`.
- Use `self.subTest(...)` to cover matrix-style cases without duplicating full test bodies, as in `tests/test_live_smoke_helpers.py` and `tests/test_strategy.py`.
- Prefer black-box assertions on structured dict payloads over inspecting private object state.

## Mocking

**Framework:** `unittest.mock.patch` and `patch.dict`

**Patterns:**
```python
with patch("omnicontrol.runtime.live_smoke.run_smoke", return_value={"status": "ok"}) as run_smoke:
    payload = attempt.run()
self.assertEqual(payload["status"], "partial")
run_smoke.assert_called_once()
```
- This pattern is used in `tests/test_live_smoke_helpers.py` to isolate secondary-profile execution.

```python
with patch.dict(
    PROFILE_METADATA,
    {"demo-url-primary": {...}, "demo-url-read": {...}},
), patch.dict(
    PROFILE_INTERACTION_LEVEL,
    {"demo-url-primary": "write", "demo-url-read": "read"},
):
    specs = infer_secondary_profiles("demo-url-primary")
```
- This pattern from `tests/test_kb.py` is the standard way to patch large in-memory registries and lookup tables.

**What to Mock:**
- External process and OS boundaries:
  - `subprocess.run` in `tests/test_live_smoke_macos.py`
  - `omnicontrol.runtime.live_smoke.run_smoke` in `tests/test_live_smoke_helpers.py`
  - Windows API enumeration helpers in `tests/test_windows_ipc.py`
- Mutable knowledge-base dictionaries and profile registries using `patch.dict` in `tests/test_kb.py` and `tests/test_live_smoke_helpers.py`
- Helper iterators that surface OS state, such as `_iter_process_entries` and `_iter_top_level_windows` in `tests/test_windows_ipc.py`

**What NOT to Mock:**
- Pure ranking, selection, and serialization helpers. Tests for `omnicontrol/runtime/transports.py`, `omnicontrol/runtime/orchestrator.py`, and `omnicontrol/runtime/strategy.py` exercise the real functions directly.
- Temporary filesystem interactions when the behavior under test is file emission or file materialization; `tests/test_invocation.py` and `tests/test_staging.py` write real temp files.

## Fixtures and Factories

**Test Data:**
```python
with tempfile.TemporaryDirectory() as tmp_dir:
    root = Path(tmp_dir)
    (root / "resources").mkdir(parents=True)
    (root / "resources" / "app.asar").write_text("stub", encoding="utf-8")
    detection = self.detector.detect(str(root), platform="windows", target_kind="desktop", needs=[])
```
- This from `tests/test_core.py` is the dominant fixture style: build only the minimal directory or file signature needed for the branch being tested.

**Location:**
- No shared fixture module or factory package is present.
- Inline fixtures live inside each test method.
- One planning document exists at `tests/TEST.md`, but it is descriptive documentation, not executable test support code.

## Coverage

**Requirements:** None enforced by tooling. No coverage configuration or threshold file is detected.

**View Coverage:**
```bash
Not detected
```

**Observed Verification Limits:**
- The codebase uses `@dataclass(slots=True)` throughout `omnicontrol/`, so most tests require Python 3.10+. Running `python3 -m unittest discover -s tests -v` in the current environment used Python 3.9 and failed imports in modules such as `omnicontrol/models.py` and `omnicontrol/runtime/strategy.py`.
- `tests/test_cdp_target_helpers.py` opens a local `ThreadingHTTPServer`, which requires socket bind permissions not available in the current sandboxed run.

## Test Types

**Unit Tests:**
- Pure logic and data-shaping tests dominate the suite.
- Examples:
  - `tests/test_orchestrator.py` validates orchestration status selection
  - `tests/test_strategy.py` validates contract evaluation and blocker classification
  - `tests/test_transports.py` validates ranking and attempt ordering
  - `tests/test_remediation.py` validates remediation action planning

**Integration Tests:**
- Filesystem integration:
  - `tests/test_invocation.py`
  - `tests/test_staging.py`
  - parts of `tests/test_core.py`
- Subprocess and CLI integration:
  - `tests/test_full_e2e.py` runs `python -m omnicontrol ...` through `subprocess.run`
- OS-boundary integration with mocks:
  - `tests/test_live_smoke_macos.py`
  - `tests/test_windows_ipc.py`

**E2E Tests:**
- `tests/test_full_e2e.py` is the closest thing to end-to-end coverage. It exercises the package entrypoint through CLI commands and verifies generated files and JSON payloads.
- There is no browser automation framework such as Playwright or Cypress, and no external service test environment is configured.

## Common Patterns

**Async Testing:**
```python
server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetSequenceHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
```
- `tests/test_cdp_target_helpers.py` uses a real background HTTP server plus polling to test target discovery behavior. Use this pattern only for networking logic that cannot be validated as a pure function.

**Error Testing:**
```python
with self.assertRaisesRegex(RuntimeError, "requires macOS"):
    run_finder_open_smoke(target_path=Path(tmp), output_dir=Path(tmp) / "finder-open")
```
- This pattern from `tests/test_live_smoke_macos.py` is the standard way to validate guardrails and platform restrictions.

**CLI Testing:**
```python
def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "omnicontrol", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
```
- Reuse the helper pattern from `tests/test_full_e2e.py` for new command-level tests.

**Registry/Matrix Testing:**
```python
for profile, blocker_types, kwargs, expected_action in cases:
    with self.subTest(profile=profile):
        candidates = plan_pivot_candidates(profile, {"strategy": {"blocker_types": blocker_types}})
        self.assertIn(expected_action, [candidate.action for candidate in candidates])
```
- `tests/test_live_smoke_helpers.py` uses list-driven subtests for broad profile coverage with low duplication. Prefer this over many nearly identical methods.

## Prescriptive Guidance

- Add new tests under `tests/` with `test_<feature>.py` naming.
- Default to `unittest.TestCase`; do not introduce pytest-only idioms unless the suite is deliberately migrated.
- Use temp directories and temp files instead of committed fixtures when verifying generated artifacts.
- Patch OS/process/network boundaries, but keep pure planners, selectors, and contract evaluators unmocked.
- When a function returns structured dict payloads, assert on the keys and status transitions that matter, not on incidental formatting.
- For new CLI coverage, follow the `subprocess.run(..., capture_output=True, text=True, check=True)` pattern from `tests/test_full_e2e.py`.

---

*Testing analysis: 2026-04-15*
