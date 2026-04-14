from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnicontrol.runtime.live_smoke import run_finder_open_smoke, run_safari_dom_write_smoke


class _CompletedProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class MacosRuntimeSmokeTests(unittest.TestCase):
    def test_finder_open_requires_macos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "requires macOS"):
                run_finder_open_smoke(
                    target_path=Path(tmp),
                    output_dir=Path(tmp) / "finder-open",
                )

    def test_finder_open_mocked_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "finder-open"
            stdout = json.dumps(
                {
                    "status": "ok",
                    "resolved_path": "/Users/demo/Documents",
                    "window_name": "Documents",
                    "finder_running": True,
                }
            )
            with patch("omnicontrol.runtime.live_smoke.current_platform", return_value="macos"), patch(
                "omnicontrol.runtime.live_smoke.subprocess.run",
                return_value=_CompletedProcess(stdout=stdout),
            ), patch(
                "omnicontrol.runtime.live_smoke._record_payload",
                side_effect=lambda profile, payload: payload,
            ):
                payload = run_finder_open_smoke(
                    target_path=None,
                    output_dir=output_dir,
                )
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["window_name"], "Documents")
        self.assertEqual(payload["report_path"], str(output_dir / "result.json"))

    def test_safari_dom_write_mocked_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "safari-dom-write"
            stdout = json.dumps(
                {
                    "status": "ok",
                    "title": "OmniControl Safari Write",
                    "href": "https://example.com",
                    "marker": "written",
                    "textarea_value": "OmniControl wrote this",
                    "readyState": "complete",
                }
            )
            with patch("omnicontrol.runtime.live_smoke.current_platform", return_value="macos"), patch(
                "omnicontrol.runtime.live_smoke.subprocess.run",
                return_value=_CompletedProcess(stdout=stdout),
            ), patch(
                "omnicontrol.runtime.live_smoke._record_payload",
                side_effect=lambda profile, payload: payload,
            ):
                payload = run_safari_dom_write_smoke(
                    url="https://example.com",
                    output_dir=output_dir,
                )
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["title"], "OmniControl Safari Write")
        self.assertEqual(payload["marker"], "written")
        self.assertEqual(payload["orchestration"]["selected_phase"], "primary")


if __name__ == "__main__":
    unittest.main()
