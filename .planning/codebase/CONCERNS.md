# Codebase Concerns

**Analysis Date:** 2026-04-15

## Tech Debt

**Runtime smoke implementation is concentrated in one oversized module:**
- Issue: `omnicontrol/runtime/live_smoke.py` is 3,852 lines and mixes CLI dispatch, startup strategy, subprocess orchestration, report writing, sidecar fallback logic, network probing, and app-specific profile code in one file.
- Files: `omnicontrol/runtime/live_smoke.py`, `tests/test_live_smoke_helpers.py`, `tests/test_live_smoke_macos.py`
- Impact: Small changes to one profile can regress unrelated profiles, review cost is high, and targeted testing is difficult because helpers and integrations are tightly coupled.
- Fix approach: Split `omnicontrol/runtime/live_smoke.py` by concern first, then by profile family. Keep `run_smoke()` as a thin registry and move per-profile execution into smaller modules under `omnicontrol/runtime/`.

**Smoke profile registration is duplicated across multiple registries:**
- Issue: New profiles must be added in more than one place: CLI choices in `omnicontrol/cli.py`, profile metadata and fallback mappings in `omnicontrol/runtime/kb.py`, and dispatch branches in `omnicontrol/runtime/live_smoke.py`.
- Files: `omnicontrol/cli.py`, `omnicontrol/runtime/kb.py`, `omnicontrol/runtime/live_smoke.py`
- Impact: Registry drift is likely. A profile can be accepted by the CLI but miss metadata or runtime handling, or vice versa.
- Fix approach: Define profiles once in a typed registry object and derive CLI choices, metadata, and dispatch from that source of truth.

**State and artifact locations depend on the caller's current working directory:**
- Issue: The knowledge base path is `Path.cwd() / "knowledge" / "kb.json"` and many smoke/report defaults are `Path.cwd() / "smoke-output" / ...`.
- Files: `omnicontrol/runtime/kb.py`, `omnicontrol/runtime/live_smoke.py`, `omnicontrol/cli.py`
- Impact: Running the same command from different directories creates separate knowledge bases and artifact trees. Learned launch overrides can silently disappear because the process is reading a different `kb.json`.
- Fix approach: Anchor persistent paths to the project root or an explicit config directory. Keep `--output` as an override, but stop using `Path.cwd()` for durable state.

**Knowledge-base writes are not atomic and have no locking:**
- Issue: `record_payload()` does read-modify-write on `knowledge/kb.json`, and `save_kb()` writes JSON directly with `Path.write_text(...)`.
- Files: `omnicontrol/runtime/kb.py`
- Impact: Concurrent smoke runs can lose updates or leave partially written JSON. This is especially risky because every smoke run records attempts and solutions.
- Fix approach: Write to a temp file and replace atomically, or add a file lock around `load_kb()` and `save_kb()`.

## Known Bugs

**Smoke profiles contain machine-specific Windows install paths:**
- Symptoms: Profiles fail immediately on machines that do not match the author's install layout.
- Files: `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/scripts/nx_diagnose_smoke.ps1`, `omnicontrol/runtime/scripts/ue_diagnose_smoke.ps1`, `omnicontrol/runtime/scripts/ue_python_write_smoke.ps1`
- Trigger: Run `quark-workflow`, `trae-workflow`, `cadv-view`, `cadv-zoom`, `cadv-workflow`, `nx-diagnose`, `ue-diagnose`, or `ue-python-write` on another Windows installation.
- Workaround: Pass overrides where supported or edit the hard-coded paths locally before running the profile.

**Learned knowledge is lost when commands are run outside the repo root:**
- Symptoms: A successful smoke run writes a new `knowledge/kb.json` under the invocation directory instead of reusing `/Users/daizhaorong/OmniControl/knowledge/kb.json`.
- Files: `omnicontrol/runtime/kb.py`, `omnicontrol/runtime/live_smoke.py`
- Trigger: Invoke `python -m omnicontrol smoke ...` from any directory other than the repository root.
- Workaround: Run commands only from `/Users/daizhaorong/OmniControl` until the path resolution is fixed.

## Security Considerations

**Startup cleanup can forcibly kill unrelated user sessions:**
- Risk: Startup helpers terminate every matching process name with `taskkill /F`, and some workflows explicitly request cleanup before launch.
- Files: `omnicontrol/runtime/adaptive_startup.py`, `omnicontrol/runtime/live_smoke.py`
- Current mitigation: Cleanup is gated by per-profile flags such as `clean_existing=True` or `False`.
- Recommendations: Track and terminate only processes launched by OmniControl, or narrow cleanup to instances using the same `--user-data-dir`. Avoid blanket process-name cleanup for user-facing apps such as Trae and browsers.

**Remote-debug workflows intentionally expose local automation endpoints:**
- Risk: CDP profiles launch apps with `--remote-debugging-port` and then poll `http://127.0.0.1:<port>/json/version`.
- Files: `omnicontrol/runtime/adaptive_startup.py`, `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/scripts/chrome_cdp_smoke.js`, `omnicontrol/runtime/scripts/desktop_cdp_observe.js`
- Current mitigation: Endpoints are bound to `127.0.0.1`.
- Recommendations: Treat these runs as privileged local automation sessions, use isolated user-data directories consistently, and avoid attaching to arbitrary existing processes unless the user has explicitly opted in.

## Performance Bottlenecks

**Startup discovery repeatedly scans all Windows processes and top-level windows:**
- Problem: `_list_processes_by_name()` uses `Get-CimInstance Win32_Process` for every check, and `_list_windows_by_process_ids()` walks all top-level windows through UIAutomation.
- Files: `omnicontrol/runtime/adaptive_startup.py`
- Cause: Process and window discovery are implemented as full-system PowerShell queries with no caching or narrowing beyond post-filtering.
- Improvement path: Replace repeated global scans with narrower queries, cache results within one smoke run, and reuse discovered process/window handles across retry steps.

**Every smoke profile pays repeated subprocess startup cost:**
- Problem: `omnicontrol/runtime/live_smoke.py` launches PowerShell, Node, browsers, and helper scripts many times inside a single smoke run and across sidecar fallbacks.
- Files: `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/adaptive_startup.py`
- Cause: The runtime favors isolated one-shot helpers instead of long-lived sessions.
- Improvement path: Reuse helper processes where possible, especially for repeated PowerShell and CDP operations within the same profile.

## Fragile Areas

**Fallback orchestration hides root causes behind generic blocked/error payloads:**
- Files: `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/live_smoke.py`
- Why fragile: `run_orchestrator()` catches broad exceptions and converts them into plain payloads, and `_run_secondary_profile_sidecar()` does the same for sidecar failures. This drops stack context and makes real faults look the same as expected runtime blockers.
- Safe modification: Preserve structured exception details in the payload and log tracebacks separately before simplifying status for end users.
- Test coverage: `tests/test_orchestrator.py` covers happy-path selection logic, but there are no tests asserting traceback preservation or richer failure diagnostics.

**Profile behavior depends on large mutable metadata tables:**
- Files: `omnicontrol/runtime/kb.py`, `tests/test_kb.py`, `tests/test_strategy.py`
- Why fragile: Secondary profile inference, invocation context compatibility, interaction weighting, and control-plane ranking all depend on large dictionary tables. A small metadata change can alter fallback behavior globally.
- Safe modification: Add regression tests whenever changing `PROFILE_METADATA`, `PROFILE_INVOCATION_CONTEXT`, `PROFILE_ACCEPTED_INVOCATION_CONTEXTS`, or interaction weights.
- Test coverage: Helper tests cover selected inference cases, but not every built-in profile family or all cross-profile combinations.

## Scaling Limits

**Adding more runtime profiles does not scale with the current architecture:**
- Current capacity: Fewer than 30 smoke profiles are supported, but each one is manually threaded through CLI parsing, metadata, runtime dispatch, scripts, and contracts.
- Limit: Adding profiles increases cross-file coordination cost and makes consistency bugs more likely.
- Scaling path: Move to declarative profile descriptors with per-profile executors, generated CLI choices, and schema validation at import time.

## Missing Critical Features

**No durable project-root resolution for persistent runtime state:**
- Problem: The runtime has no explicit concept of a repository root or config root, so persistence falls back to the shell's current directory.
- Blocks: Reliable knowledge reuse, reproducible report locations, and safe invocation from editors, CI, or parent directories.

## Test Coverage Gaps

**Real platform integrations remain largely untested:**
- What's not tested: Real UIA, CDP, COM, AppleScript, and heavyweight desktop smoke execution paths.
- Files: `tests/TEST.md`, `tests/test_live_smoke_macos.py`, `tests/test_live_smoke_helpers.py`, `omnicontrol/runtime/live_smoke.py`
- Risk: The project can pass its current suite while machine-specific automation paths are broken on real hosts.
- Priority: High

**Adaptive startup cleanup and process discovery are only lightly tested:**
- What's not tested: Real `taskkill` cleanup behavior, `Get-CimInstance` parsing, UIAutomation window enumeration, and repeated attach/relaunch flows.
- Files: `tests/test_adaptive_startup.py`, `omnicontrol/runtime/adaptive_startup.py`
- Risk: Destructive or slow startup behavior can regress without detection.
- Priority: High

---

*Concerns audit: 2026-04-15*
