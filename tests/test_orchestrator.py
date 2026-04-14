from __future__ import annotations

import unittest

from omnicontrol.runtime.orchestrator import (
    AttemptSpec,
    OrchestratorSpec,
    PreflightCheck,
    PreflightResult,
    run_orchestrator,
)


class OrchestratorTests(unittest.TestCase):
    def test_blocked_when_required_preflight_fails(self) -> None:
        result = run_orchestrator(
            OrchestratorSpec(
                profile="demo",
                preflight=[
                    PreflightCheck(
                        name="missing_dep",
                        run=lambda: PreflightResult(
                            name="missing_dep",
                            ok=False,
                            detail="dependency missing",
                            required=True,
                            blocker="dependency missing",
                        ),
                    )
                ],
                attempts=[],
            )
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("dependency missing", result["blockers"])

    def test_ok_attempt_selected(self) -> None:
        result = run_orchestrator(
            OrchestratorSpec(
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
                attempts=[
                    AttemptSpec(
                        name="attempt1",
                        strategy="test",
                        run=lambda: {"status": "ok", "value": 1},
                    )
                ],
            )
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["orchestration"]["selected_attempt"], "attempt1")

    def test_partial_attempt_selected(self) -> None:
        result = run_orchestrator(
            OrchestratorSpec(
                profile="demo",
                preflight=[],
                attempts=[
                    AttemptSpec(
                        name="attempt1",
                        strategy="tooling",
                        run=lambda: {"status": "partial", "secondary_action_ok": True},
                    )
                ],
            )
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["orchestration"]["selected_attempt"], "attempt1")


if __name__ == "__main__":
    unittest.main()
