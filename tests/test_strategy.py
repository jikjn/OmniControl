from __future__ import annotations

import unittest

from omnicontrol.runtime.contracts import SMOKE_CONTRACTS
from omnicontrol.runtime.strategy import evaluate_contract


class StrategyTests(unittest.TestCase):
    def test_word_write_evaluates_ok(self) -> None:
        payload = {
            "status": "ok",
            "exists": True,
            "zip_ok": True,
            "output": "out.docx",
        }
        result = evaluate_contract(payload, SMOKE_CONTRACTS["word-write"])
        self.assertEqual(result.status, "ok")
        self.assertFalse(result.required_failed)

    def test_masterpdf_evaluates_partial_when_desired_effect_missing(self) -> None:
        payload = {
            "status": "ok",
            "window_name": "environment-physics.pdf - 迅读PDF",
            "page_advanced": False,
        }
        result = evaluate_contract(payload, SMOKE_CONTRACTS["masterpdf-pagedown"])
        self.assertEqual(result.status, "partial")
        self.assertTrue(result.desired_failed)

    def test_nx_evaluates_blocked(self) -> None:
        payload = {
            "status": "blocked",
            "blockers": [
                "UFUN initialization failed",
                "license port 28000 is not listening",
            ],
            "sample_output": "run_journal: failed to initialize UFUN 949885",
        }
        result = evaluate_contract(payload, SMOKE_CONTRACTS["nx-diagnose"])
        self.assertEqual(result.status, "blocked")
        self.assertIn("license", result.blocker_types)

    def test_isight_tooling_plane_evaluates_partial(self) -> None:
        payload = {
            "status": "partial",
            "secondary_action": "vendor_tooling_plane",
            "secondary_action_ok": True,
            "tooling_verified": True,
            "tooling_entrypoint": "fiperenv.bat + licusage.bat -h + fipercmd.bat help contents",
        }
        result = evaluate_contract(payload, SMOKE_CONTRACTS["isight-diagnose"])
        self.assertEqual(result.status, "partial")
        self.assertFalse(result.required_failed)

    def test_ue_tooling_plane_evaluates_partial(self) -> None:
        payload = {
            "status": "partial",
            "secondary_action": "vendor_tooling_plane",
            "secondary_action_ok": True,
            "tooling_verified": True,
            "tooling_entrypoint": "BuildPatchTool.exe -help",
        }
        result = evaluate_contract(payload, SMOKE_CONTRACTS["ue-diagnose"])
        self.assertEqual(result.status, "partial")
        self.assertFalse(result.required_failed)

    def test_ide_workflow_evaluates_ok(self) -> None:
        payload = {
            "status": "ok",
            "all_required_steps_ok": True,
            "required_steps_total": 13,
            "required_steps_ok": 13,
            "symbol_info_ok": True,
            "rename_ok": True,
            "reformat_ok": True,
            "find_file_ok": True,
            "directory_tree_ok": True,
            "search_ok": True,
            "problems_ok": True,
            "terminal_ok": True,
            "workflow_tools_used": ["create_new_file", "rename_refactoring", "execute_terminal_command"],
        }
        result = evaluate_contract(payload, SMOKE_CONTRACTS["ide-workflow"])
        self.assertEqual(result.status, "ok")
        self.assertFalse(result.required_failed)

    def test_write_profiles_allow_secondary_profile_partial(self) -> None:
        cases = [
            ("word-workflow", "word-write"),
            ("chrome-form-write", "chrome-cdp"),
            ("chrome-workflow", "chrome-form-write"),
            ("masterpdf-zoom", "masterpdf-pagedown"),
            ("masterpdf-workflow", "masterpdf-pagedown"),
            ("quark-cdp-write", "quark-cdp"),
            ("quark-workflow", "quark-cdp-write"),
            ("trae-cdp-write", "trae-open"),
            ("trae-workflow", "trae-open"),
            ("cadv-zoom", "cadv-view"),
            ("cadv-workflow", "cadv-zoom"),
            ("ue-python-write", "ue-diagnose"),
        ]
        for profile, secondary_profile in cases:
            with self.subTest(profile=profile):
                payload = {
                    "status": "partial",
                    "secondary_action": "related_profile_control_plane",
                    "secondary_action_ok": True,
                    "secondary_profile": secondary_profile,
                    "secondary_profile_status": "ok",
                    "tooling_entrypoint": f"profile:{secondary_profile}",
                }
                result = evaluate_contract(payload, SMOKE_CONTRACTS[profile])
                self.assertEqual(result.status, "partial")
                self.assertEqual(result.evidence["secondary_profile"], secondary_profile)


if __name__ == "__main__":
    unittest.main()
