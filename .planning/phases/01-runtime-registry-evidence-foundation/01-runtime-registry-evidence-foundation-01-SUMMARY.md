---
phase: 01-runtime-registry-evidence-foundation
plan: 01
subsystem: runtime
tags: [registry, runtime-paths, evidence, unittest]
requires: []
provides:
  - typed runtime registry contracts
  - stable runtime path contracts
  - canonical evidence bundle contracts
affects: [cli, kb, live_smoke, testing]
tech-stack:
  added: []
  patterns: [typed runtime contracts, evidence-first smoke reporting, cwd-independent runtime roots]
key-files:
  created:
    - omnicontrol/runtime/registry.py
    - omnicontrol/runtime/paths.py
    - omnicontrol/runtime/evidence.py
    - tests/test_runtime_registry.py
    - tests/test_runtime_paths.py
    - tests/test_runtime_evidence.py
  modified:
    - tests/test_full_e2e.py
    - tests/test_kb.py
key-decisions:
  - "Use additive contract modules first, then migrate existing callers onto them."
  - "Protect the user-facing smoke CLI with a mocked --json regression instead of relying only on internal helpers."
patterns-established:
  - "Registry contracts expose immutable descriptors while compatibility dict views remain patchable for brownfield tests."
  - "Runtime/evidence behavior is frozen by dedicated unittest modules before deeper refactors land."
requirements-completed: [RTF-01, RTF-02, RTF-04, VER-01, VER-02]
duration: 20min
completed: 2026-04-15
---

# Phase 01 Plan 01: Runtime Registry & Evidence Foundation Summary

**Typed smoke registry, cwd-independent runtime path contracts, and canonical evidence bundle tests for OmniControl**

## Performance

- **Duration:** 20 min
- **Started:** 2026-04-15T15:08:00+08:00
- **Completed:** 2026-04-15T15:28:00+08:00
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Added `registry.py`, `paths.py`, and `evidence.py` as the phase foundation contracts.
- Added dedicated regression suites for registry choices, runtime root resolution, and result bundle shape.
- Added a mocked `omnicontrol smoke ... --json` CLI regression so Phase 1 validates the real user entrypoint.

## Task Commits

No task commits were created in this worktree.

The repository already contained overlapping uncommitted phase files in the same execution surface, so this plan was kept uncommitted to avoid mixing user-owned and executor-owned history.

## Files Created/Modified
- `omnicontrol/runtime/registry.py` - typed profile descriptor and registry helpers
- `omnicontrol/runtime/paths.py` - stable runtime root and smoke-output path contracts
- `omnicontrol/runtime/evidence.py` - canonical result bundle writer contract
- `tests/test_runtime_registry.py` - registry and CLI choice regressions
- `tests/test_runtime_paths.py` - stable root and legacy KB migration regressions
- `tests/test_runtime_evidence.py` - `result.json` shape and artifact reference regressions
- `tests/test_full_e2e.py` - mocked `smoke --json` CLI regression
- `tests/test_kb.py` - runtime-managed KB path regression coverage

## Decisions Made

- Contract modules were introduced before broader migration to keep the brownfield refactor additive-first.
- CLI smoke verification now has its own regression rather than depending on indirect parser coverage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Kept plan execution uncommitted because the worktree already contained overlapping uncommitted phase edits**
- **Found during:** Plan execution setup
- **Issue:** Atomic task commits would have mixed pre-existing dirty changes with new plan changes in the same files.
- **Fix:** Executed the plan in-place, preserved the existing working tree, and documented the state explicitly in summaries.
- **Files modified:** `.planning/phases/01-runtime-registry-evidence-foundation/01-runtime-registry-evidence-foundation-01-SUMMARY.md`
- **Verification:** All targeted unittests passed after the contract/test layer landed.

---

**Total deviations:** 1 auto-fixed (working-tree safety)
**Impact on plan:** No scope creep. The only deviation was commit protocol suppression due an already-dirty execution surface.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Registry, path, and evidence contracts are in place and covered by dedicated tests.
Ready for `01-02` to migrate CLI, KB, and smoke runtime callers onto the new contracts.
