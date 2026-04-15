---
status: complete
phase: 01-runtime-registry-evidence-foundation
source:
  - 01-runtime-registry-evidence-foundation-01-SUMMARY.md
  - 01-runtime-registry-evidence-foundation-02-SUMMARY.md
  - 01-runtime-registry-evidence-foundation-03-SUMMARY.md
started: 2026-04-15T07:30:00Z
updated: 2026-04-15T07:40:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Smoke CLI Lists and Accepts Registry Profiles
expected: Running `omnicontrol smoke --help` should show the current shared smoke profile list instead of a stale hard-coded subset. Running `omnicontrol smoke finder-open --json` should still parse and return structured JSON output through the CLI entrypoint.
result: pass

### 2. Runtime KB Path Is Stable Outside Repo Root
expected: Running OmniControl from a different working directory should no longer create or depend on `./knowledge/kb.json` in that directory. Runtime knowledge should resolve to the framework-managed location instead.
result: pass

### 3. Default Smoke Output Uses Managed Runtime Roots
expected: Running a smoke profile without `--output` should write `result.json` and any default artifacts into the framework-managed runtime artifact root rather than under the caller's current directory.
result: pass

### 4. Result Bundle Keeps Compatibility and Adds Evidence
expected: A generated `result.json` should still include `report_path`, and it should now also include structured runtime metadata plus concrete `artifacts[]` paths.
result: pass

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None yet.
