---
phase: 01-runtime-registry-evidence-foundation
plan: 02
subsystem: runtime
tags: [registry, kb, smoke, runtime-root]
requires:
  - phase: 01-runtime-registry-evidence-foundation
    provides: typed registry, runtime paths, evidence contracts
provides:
  - registry-backed smoke CLI choices
  - stable KB persistence root
  - runtime-managed smoke output defaults
affects: [cli, kb, live_smoke, pivots, remediation]
tech-stack:
  added: []
  patterns: [registry-backed compatibility views, atomic kb writes, helper-based smoke output resolution]
key-files:
  created: []
  modified:
    - omnicontrol/cli.py
    - omnicontrol/runtime/kb.py
    - omnicontrol/runtime/live_smoke.py
    - tests/test_full_e2e.py
    - tests/test_kb.py
key-decisions:
  - "Keep PROFILE_METADATA patchable for brownfield tests while making registry.py the canonical source of descriptors."
  - "Use runtime-managed default roots but still read legacy repo-local KB files when present."
patterns-established:
  - "Default smoke artifact locations resolve through helper functions instead of inline Path.cwd() joins."
  - "KB persistence uses temp-file plus atomic replace."
requirements-completed: [RTF-01, RTF-02]
duration: 25min
completed: 2026-04-15
---

# Phase 01 Plan 02: Runtime Registry & Evidence Foundation Summary

**Registry-backed smoke entrypoints and runtime-managed KB/artifact roots without profile ID churn**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-15T15:28:00+08:00
- **Completed:** 2026-04-15T15:53:00+08:00
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Switched the `smoke` CLI to derive profile choices from the typed registry.
- Moved KB persistence to a stable runtime-managed path and preserved legacy repo-local KB reads.
- Replaced inline `Path.cwd()/smoke-output/...` defaults in `live_smoke.py` with shared runtime path helpers.

## Task Commits

No task commits were created in this worktree for the same dirty-tree reason documented in Plan 01.

## Files Created/Modified
- `omnicontrol/cli.py` - smoke profile choices now come from `profile_choices()`
- `omnicontrol/runtime/kb.py` - imports registry compatibility views, resolves stable KB path, writes atomically
- `omnicontrol/runtime/live_smoke.py` - default smoke output directories now flow through shared runtime path helpers
- `tests/test_full_e2e.py` - CLI smoke user path regression
- `tests/test_kb.py` - stable KB path round-trip coverage

## Decisions Made

- Registry migration stayed compatibility-first: existing dict-based metadata access remains valid for pivot/remediation tests.
- Legacy KB files are read as a migration bridge instead of being silently abandoned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Applied the migration in-place without task commits**
- **Found during:** Plan execution
- **Issue:** The same files already had uncommitted local changes before Phase 1 execution began.
- **Fix:** Preserved the existing worktree, completed the migration, and relied on targeted plus full-suite verification instead of per-task commits.
- **Files modified:** `.planning/phases/01-runtime-registry-evidence-foundation/01-runtime-registry-evidence-foundation-02-SUMMARY.md`
- **Verification:** `tests.test_pivots`, `tests.test_remediation`, `tests.test_live_smoke_helpers`, and `tests.test_live_smoke_macos` all passed after migration.

---

**Total deviations:** 1 auto-fixed (working-tree safety)
**Impact on plan:** No functional compromise. The migration landed, but commit granularity was intentionally suppressed to protect pre-existing changes.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

CLI and KB now resolve through the shared runtime contracts.
Ready for `01-03` to replace ad hoc `result.json` writes with the shared evidence pipeline.
