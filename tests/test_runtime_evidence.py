from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omnicontrol.runtime.evidence import write_result_bundle
from omnicontrol.runtime.paths import resolve_runtime_paths


class RuntimeEvidenceTests(unittest.TestCase):
    def test_write_result_bundle_persists_canonical_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            output = root / "artifact.txt"
            output.write_text("artifact", encoding="utf-8")
            runtime_paths = resolve_runtime_paths(explicit_root=root / "runtime")
            payload = write_result_bundle(
                "finder-open",
                {
                    "profile": "finder-open",
                    "status": "ok",
                    "output": str(output),
                    "window_name": "Documents",
                },
                report_dir=report_dir,
                runtime_paths=runtime_paths,
            )
            report_path = report_dir / "result.json"
            persisted = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["report_path"], str(report_path))
        self.assertEqual(persisted["profile"], "finder-open")
        self.assertEqual(persisted["runtime"]["root"], str(runtime_paths.root))
        self.assertEqual(persisted["artifacts"][0]["path"], str(output))

    def test_write_result_bundle_preserves_legacy_report_path_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            payload = write_result_bundle(
                "safari-open",
                {"profile": "safari-open", "status": "partial", "title": "Example"},
                report_dir=report_dir,
            )
        self.assertIn("report_path", payload)
        self.assertIn("bundle", payload)
        self.assertEqual(payload["bundle"]["report_path"], payload["report_path"])

    def test_write_result_bundle_adds_bundle_fallback_artifact_when_none_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            payload = write_result_bundle(
                "finder-open",
                {"profile": "finder-open", "status": "ok", "window_name": "Documents"},
                report_dir=report_dir,
            )
            report_path = report_dir / "result.json"
            persisted = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(persisted["artifacts"])
        self.assertEqual(persisted["artifacts"][0]["name"], "result_bundle")
        self.assertEqual(persisted["artifacts"][0]["kind"], "report")
        self.assertEqual(persisted["artifacts"][0]["path"], str(report_path))
        self.assertEqual(payload["report_path"], str(report_path))

    def test_write_result_bundle_keeps_canonical_artifacts_without_relabeling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            screenshot = root / "shot.png"
            screenshot.write_bytes(b"png")
            persisted = write_result_bundle(
                "chrome-cdp",
                {"profile": "chrome-cdp", "status": "ok", "screenshot": str(screenshot)},
                report_dir=report_dir,
            )
        artifact_names = [item["name"] for item in persisted["artifacts"]]
        self.assertIn("screenshot", artifact_names)
        self.assertNotIn("result_bundle", artifact_names)


if __name__ == "__main__":
    unittest.main()
