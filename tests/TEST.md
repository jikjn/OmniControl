# Test Plan

## Test Inventory Plan

- `test_core.py`: 6 unit tests planned
- `test_full_e2e.py`: 3 CLI workflow tests planned
- `test_strategy.py`: 4 strategy tests planned
- `test_adaptive_startup.py`: 2 startup tests planned
- `test_orchestrator.py`: 3 orchestrator tests planned
- `test_pivots.py`: 4 pivot tests planned
- `test_remediation.py`: 1 remediation test planned
- `test_staging.py`: 2 staging tests planned

## Unit Test Plan

- `CapabilityDetector`
  - Detect document targets and file-format capability
  - Detect browser targets and CDP capability
  - Detect script/plugin signatures from install directories
  - Detect Electron/app.asar signatures from install directories
- `AdapterSelector`
  - Choose Windows desktop language decision correctly
  - Choose file-format adapter for document workflows
- `scaffold_project`
  - Verify generated files and primary script extension
- `benchmark`
  - Validate config-driven batch evaluation and report generation
- `strategy`
  - Validate unified `ok / partial / blocked` evaluation

## E2E Test Plan

- Run `python -m omnicontrol detect` and validate JSON structure
- Run `python -m omnicontrol scaffold` and validate manifest plus generated templates
- Run `python -m omnicontrol benchmark` and validate summary plus report output

## Realistic Workflow Scenarios

- **Workflow name**: Windows desktop planning
  - **Simulates**: Planning a COM/UIA style desktop adapter
  - **Operations chained**: detect -> plan
  - **Verified**: primary adapter, language choice, verification methods
- **Workflow name**: Document scaffold generation
  - **Simulates**: Generating a thin file-format adapter
  - **Operations chained**: detect -> plan -> scaffold
  - **Verified**: manifest creation, skill file, script templates

## Test Results

Command:

```text
python -m unittest discover -s tests -v
```

Output:

```text
test_extract_remote_debugging_port (test_adaptive_startup.AdaptiveStartupTests.test_extract_remote_debugging_port) ... ok
test_startup_info_to_dict (test_adaptive_startup.AdaptiveStartupTests.test_startup_info_to_dict) ... ok
test_document_target_prefers_file_format_and_python (test_core.DetectorAndPlannerTests.test_document_target_prefers_file_format_and_python) ... ok
test_electron_signature_prefers_cdp (test_core.DetectorAndPlannerTests.test_electron_signature_prefers_cdp) ... ok
test_scaffold_generates_primary_files (test_core.DetectorAndPlannerTests.test_scaffold_generates_primary_files) ... ok
test_script_signature_prefers_javascript (test_core.DetectorAndPlannerTests.test_script_signature_prefers_javascript) ... ok
test_web_target_prefers_cdp_and_typescript (test_core.DetectorAndPlannerTests.test_web_target_prefers_cdp_and_typescript) ... ok
test_windows_desktop_prefers_powershell (test_core.DetectorAndPlannerTests.test_windows_desktop_prefers_powershell) ... ok
test_benchmark_json (test_full_e2e.CliE2ETests.test_benchmark_json) ... ok
test_detect_json (test_full_e2e.CliE2ETests.test_detect_json) ... ok
test_scaffold_json (test_full_e2e.CliE2ETests.test_scaffold_json) ... ok
test_blocked_when_required_preflight_fails (test_orchestrator.OrchestratorTests.test_blocked_when_required_preflight_fails) ... ok
test_ok_attempt_selected (test_orchestrator.OrchestratorTests.test_ok_attempt_selected) ... ok
test_partial_attempt_selected (test_orchestrator.OrchestratorTests.test_partial_attempt_selected) ... ok
test_find_matches_does_not_cross_learn_unrelated_products (test_pivots.PivotTests.test_find_matches_does_not_cross_learn_unrelated_products) ... ok
test_plan_pivot_candidates_for_heavy_license_blocker (test_pivots.PivotTests.test_plan_pivot_candidates_for_heavy_license_blocker) ... ok
test_run_with_strategy_pivots_keeps_primary_blockers_on_partial (test_pivots.PivotTests.test_run_with_strategy_pivots_keeps_primary_blockers_on_partial) ... ok
test_run_with_strategy_pivots_merges_pivot_success (test_pivots.PivotTests.test_run_with_strategy_pivots_merges_pivot_success) ... ok
test_plan_actions_for_isight_blockers (test_remediation.RemediationTests.test_plan_actions_for_isight_blockers) ... ok
test_detects_non_ascii_path (test_staging.StagingTests.test_detects_non_ascii_path) ... ok
test_stages_unicode_file_to_ascii_location (test_staging.StagingTests.test_stages_unicode_file_to_ascii_location) ... ok
test_isight_tooling_plane_evaluates_partial (test_strategy.StrategyTests.test_isight_tooling_plane_evaluates_partial) ... ok
test_masterpdf_evaluates_partial_when_desired_effect_missing (test_strategy.StrategyTests.test_masterpdf_evaluates_partial_when_desired_effect_missing) ... ok
test_nx_evaluates_blocked (test_strategy.StrategyTests.test_nx_evaluates_blocked) ... ok
test_word_write_evaluates_ok (test_strategy.StrategyTests.test_word_write_evaluates_ok) ... ok

----------------------------------------------------------------------
Ran 25 tests in 0.771s

OK
```

## Summary Statistics

- Total tests: 25
- Pass rate: 100%
- Execution time: 0.771s

## Coverage Notes

- 当前覆盖了控制面探测、目录签名识别、适配器选择、语言决策、脚手架生成、批量 benchmark 和统一状态策略。
- 还没有覆盖真实 UIA、CDP、COM、AppleScript 或 hook/runtime 接入，这些属于后续适配器实现阶段。
