from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CliE2ETests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "omnicontrol", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_detect_json(self) -> None:
        result = self._run(
            "detect",
            "http://localhost:3000",
            "--kind",
            "web",
            "--need",
            "browser",
            "--json",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["target_kind"], "web")
        capability_names = {item["name"] for item in payload["capabilities"]}
        self.assertIn("cdp", capability_names)

    def test_scaffold_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self._run(
                "scaffold",
                "report.docx",
                "--platform",
                "windows",
                "--kind",
                "document",
                "--need",
                "export",
                "--output",
                tmp_dir,
                "--json",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["plan"]["primary_adapter"], "file_format")
            self.assertTrue((Path(tmp_dir) / "manifest.json").exists())
            self.assertTrue(any(path.endswith(".py") for path in payload["generated_files"]))

    def test_benchmark_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            script_app = root / "IllustratorLike"
            (script_app / "Scripting").mkdir(parents=True)
            (script_app / "Scripting" / "demo.jsx").write_text("// stub", encoding="utf-8")

            electron_app = root / "ElectronLike"
            (electron_app / "resources").mkdir(parents=True)
            (electron_app / "resources" / "app.asar").write_text("stub", encoding="utf-8")

            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "name": "script_like",
                                "category": "official_script_plugin",
                                "target": str(script_app),
                                "platform": "windows",
                                "kind": "desktop",
                                "needs": ["plugin"],
                                "expected_primary": "native_script",
                                "expected_language": "javascript",
                            },
                            {
                                "name": "electron_like",
                                "category": "electron_cdp",
                                "target": str(electron_app),
                                "platform": "windows",
                                "kind": "desktop",
                                "needs": [],
                                "expected_primary": "cdp",
                                "expected_language": "typescript",
                            },
                            {
                                "name": "finder_like",
                                "category": "accessibility_desktop",
                                "target": "Finder",
                                "platform": "macos",
                                "kind": "desktop",
                                "needs": ["ui"],
                                "expected_primary": "accessibility",
                                "expected_language": "applescript",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            output_dir = root / "bench-output"
            result = self._run(
                "benchmark",
                str(config_path),
                "--output",
                str(output_dir),
                "--json",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["total"], 3)
            self.assertEqual(payload["summary"]["primary_matches"], 3)
            self.assertEqual(payload["summary"]["language_matches"], 3)
            self.assertTrue((output_dir / "benchmark-report.json").exists())


if __name__ == "__main__":
    unittest.main()
