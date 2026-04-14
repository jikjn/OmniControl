from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omnicontrol.detector.capability_detector import CapabilityDetector
from omnicontrol.emitters.scaffold import scaffold_project
from omnicontrol.ir.manifest import build_manifest
from omnicontrol.planner.adapter_selector import AdapterSelector


class DetectorAndPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = CapabilityDetector()
        self.selector = AdapterSelector()

    def test_document_target_prefers_file_format_and_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "report.docx"
            target.write_text("demo", encoding="utf-8")
            detection = self.detector.detect(
                str(target),
                platform="windows",
                target_kind="auto",
                needs=["document", "export"],
            )
            plan = self.selector.select(detection)
            self.assertEqual(plan.primary_adapter, "file_format")
            self.assertEqual(plan.language.primary, "python")

    def test_web_target_prefers_cdp_and_typescript(self) -> None:
        detection = self.detector.detect(
            "http://localhost:3000",
            platform="windows",
            target_kind="web",
            needs=["browser", "dom"],
        )
        plan = self.selector.select(detection)
        self.assertEqual(plan.primary_adapter, "cdp")
        self.assertEqual(plan.language.primary, "typescript")

    def test_windows_desktop_prefers_powershell(self) -> None:
        detection = self.detector.detect(
            "LegacyDesktopApp",
            platform="windows",
            target_kind="desktop",
            needs=["ui", "export"],
        )
        plan = self.selector.select(detection)
        self.assertIn(plan.primary_adapter, {"uiautomation", "native_script"})
        self.assertEqual(plan.language.primary, "powershell")

    def test_macos_desktop_prefers_applescript(self) -> None:
        detection = self.detector.detect(
            "Finder",
            platform="macos",
            target_kind="desktop",
            needs=["ui"],
        )
        plan = self.selector.select(detection)
        self.assertIn(plan.primary_adapter, {"accessibility", "native_script"})
        self.assertEqual(plan.language.primary, "applescript")

    def test_macos_desktop_prefers_accessibility_and_applescript(self) -> None:
        detection = self.detector.detect(
            "Finder",
            platform="macos",
            target_kind="desktop",
            needs=["ui"],
        )
        plan = self.selector.select(detection)
        self.assertIn(plan.primary_adapter, {"accessibility", "native_script"})
        self.assertEqual(plan.language.primary, "applescript")

    def test_scaffold_generates_primary_files(self) -> None:
        detection = self.detector.detect(
            "Excel",
            platform="windows",
            target_kind="desktop",
            needs=["office", "export"],
        )
        plan = self.selector.select(detection)
        manifest = build_manifest("OmniControl", detection, plan)
        with tempfile.TemporaryDirectory() as tmp_dir:
            generated = scaffold_project(manifest, Path(tmp_dir))
            names = {path.name for path in generated}
            self.assertIn("manifest.json", names)
            self.assertIn("SKILL.md", names)
            self.assertIn("PLAN.md", names)
            self.assertTrue(any(name.endswith(".ps1") for name in names))

    def test_macos_scaffold_generates_applescript(self) -> None:
        detection = self.detector.detect(
            "Finder",
            platform="macos",
            target_kind="desktop",
            needs=["ui"],
        )
        plan = self.selector.select(detection)
        manifest = build_manifest("OmniControl", detection, plan)
        with tempfile.TemporaryDirectory() as tmp_dir:
            generated = scaffold_project(manifest, Path(tmp_dir))
            names = {path.name for path in generated}
            self.assertIn("manifest.json", names)
            self.assertTrue(any(name.endswith(".applescript") for name in names))

    def test_script_signature_prefers_javascript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Scripting" / "Sample Scripts").mkdir(parents=True)
            (root / "Scripting" / "Sample Scripts" / "demo.jsx").write_text("// stub", encoding="utf-8")
            detection = self.detector.detect(
                str(root),
                platform="windows",
                target_kind="desktop",
                needs=["plugin"],
            )
            plan = self.selector.select(detection)
            self.assertEqual(plan.primary_adapter, "native_script")
            self.assertEqual(plan.language.primary, "javascript")

    def test_electron_signature_prefers_cdp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "resources").mkdir(parents=True)
            (root / "resources" / "app.asar").write_text("stub", encoding="utf-8")
            (root / "chrome_100_percent.pak").write_text("stub", encoding="utf-8")
            detection = self.detector.detect(
                str(root),
                platform="windows",
                target_kind="desktop",
                needs=[],
            )
            plan = self.selector.select(detection)
            self.assertEqual(plan.primary_adapter, "cdp")
            self.assertEqual(plan.language.primary, "typescript")


if __name__ == "__main__":
    unittest.main()
