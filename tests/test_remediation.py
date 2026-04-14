from __future__ import annotations

import unittest

from omnicontrol.runtime.remediation import plan_remediation_actions


class RemediationTests(unittest.TestCase):
    def test_plan_actions_for_isight_blockers(self) -> None:
        payload = {
            "strategy": {
                "blocker_types": ["license", "profile"],
                "recovery_hints": [
                    {"action": "discover_profiles", "reason": "hint"},
                    {"action": "probe_license_service", "reason": "hint"},
                ],
            }
        }
        actions = plan_remediation_actions("isight-diagnose", payload)
        self.assertIn("discover_profiles", actions)
        self.assertIn("probe_license_service", actions)
        self.assertIn("supply_profile_standalone_cpr", actions)


if __name__ == "__main__":
    unittest.main()
