from __future__ import annotations

import unittest

from omnicontrol.runtime.kb import find_matches
from omnicontrol.runtime.orchestrator import AttemptSpec, PreflightCheck, PreflightResult
from omnicontrol.runtime.pivots import plan_pivot_candidates, run_with_strategy_pivots


class PivotTests(unittest.TestCase):
    def test_plan_pivot_candidates_for_heavy_license_blocker(self) -> None:
        payload = {
            "strategy": {
                "blocker_types": ["license", "runtime"],
            }
        }
        candidates = plan_pivot_candidates("nx-diagnose", payload)
        actions = [candidate.action for candidate in candidates]
        self.assertIn("switch_to_tooling_plane", actions)
        self.assertIn("bootstrap_license_tooling", actions)
        self.assertIn("switch_to_shell_environment", actions)

    def test_plan_pivot_candidates_for_ue_timeout_includes_tooling_plane(self) -> None:
        payload = {
            "strategy": {
                "blocker_types": ["timeout"],
            }
        }
        candidates = plan_pivot_candidates("ue-diagnose", payload)
        actions = [candidate.action for candidate in candidates]
        self.assertIn("switch_to_tooling_plane", actions)
        self.assertIn("switch_to_secondary_entrypoint", actions)

    def test_metadata_sidecar_candidates_are_available_without_matching_blocker_family(self) -> None:
        payload = {
            "strategy": {
                "blocker_types": ["dependency"],
            }
        }
        candidates = plan_pivot_candidates("chrome-form-write", payload)
        actions = [candidate.action for candidate in candidates]
        self.assertIn("switch_to_secondary_entrypoint", actions)

    def test_write_profiles_prefer_write_preserving_entrypoint_pivots(self) -> None:
        payload = {
            "strategy": {
                "blocker_types": ["runtime", "timeout"],
            }
        }
        candidates = plan_pivot_candidates("ue-python-write", payload)
        actions = [candidate.action for candidate in candidates]
        self.assertLess(actions.index("drop_project_context"), actions.index("switch_to_tooling_plane"))

    def test_run_with_strategy_pivots_merges_pivot_success(self) -> None:
        result = run_with_strategy_pivots(
            profile="demo",
            preflight=[
                PreflightCheck(
                    name="ok",
                    run=lambda: PreflightResult(
                        name="ok",
                        ok=True,
                        detail="ok",
                    ),
                )
            ],
            primary_attempts=[
                AttemptSpec(
                    name="primary",
                    strategy="direct_script",
                    run=lambda: {"status": "blocked", "blockers": ["primary blocked"]},
                )
            ],
            pivot_builder=lambda _: (
                plan_pivot_candidates("ue-python-write", {"strategy": {"blocker_types": ["runtime"]}}),
                [
                    AttemptSpec(
                        name="pivot_engine",
                        strategy="drop_project_context",
                        run=lambda: {"status": "ok", "write_ok": True},
                    )
                ],
            ),
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["orchestration"]["selected_attempt"], "pivot_engine")
        self.assertEqual(result["orchestration"]["selected_phase"], "pivot")
        self.assertTrue(result["orchestration"]["pivoted"])
        self.assertEqual(len(result["orchestration"]["attempts"]), 2)
        self.assertEqual(result["orchestration"]["attempts"][0]["phase"], "primary")
        self.assertEqual(result["orchestration"]["attempts"][1]["phase"], "pivot")

    def test_run_with_strategy_pivots_keeps_primary_blockers_on_partial(self) -> None:
        result = run_with_strategy_pivots(
            profile="demo",
            preflight=[],
            primary_attempts=[
                AttemptSpec(
                    name="primary",
                    strategy="direct_script",
                    run=lambda: {"status": "blocked", "blockers": ["license missing"]},
                )
            ],
            pivot_builder=lambda _: (
                plan_pivot_candidates("nx-diagnose", {"strategy": {"blocker_types": ["license", "runtime"]}}),
                [
                    AttemptSpec(
                        name="secondary",
                        strategy="switch_to_secondary_entrypoint",
                        run=lambda: {"status": "partial", "secondary_action_ok": True},
                    )
                ],
            ),
        )
        self.assertEqual(result["status"], "partial")
        self.assertIn("license missing", result["blockers"])
        self.assertEqual(result["orchestration"]["selected_attempt"], "secondary")

    def test_find_matches_does_not_cross_learn_unrelated_products(self) -> None:
        kb = {
            "version": 1,
            "updated_at": None,
            "cases": [
                {
                    "case_id": "ue",
                    "lookup": {
                        "product_key": "unreal_engine",
                        "software_type": "game_engine_heavy_desktop",
                        "target_kind": "desktop",
                        "platform": "windows",
                        "profile": "ue-python-write",
                        "control_planes": ["native_script"],
                        "blocker_patterns": ["runtime"],
                        "tags": [],
                    },
                    "summary": {"times_solved": 1, "last_seen_at": "2026-04-13T00:00:00+08:00"},
                    "solution": {"remediation_actions": ["drop_project_context"]},
                }
            ],
        }
        matches = find_matches(
            "nx-diagnose",
            {"strategy": {"blocker_types": ["license", "runtime"]}},
            kb=kb,
        )
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
