from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from omnicontrol.runtime.live_smoke import (
    run_finder_open_smoke,
    run_safari_dom_write_smoke,
    run_word_export_smoke,
    run_word_workflow_smoke,
    run_word_write_smoke,
)


class _CompletedProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class MacosRuntimeSmokeTests(unittest.TestCase):
    def test_finder_open_requires_non_macos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("omnicontrol.runtime.live_smoke.current_platform", return_value="linux"):
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
            persisted = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["window_name"], "Documents")
        self.assertEqual(payload["report_path"], str(output_dir / "result.json"))
        self.assertTrue(persisted["artifacts"])
        self.assertEqual(persisted["artifacts"][0]["name"], "result_bundle")
        self.assertEqual(persisted["artifacts"][0]["kind"], "report")
        self.assertEqual(persisted["artifacts"][0]["path"], str(output_dir / "result.json"))

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

    def test_word_write_mocked_success_on_macos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            word_app = root / "Microsoft Word.app"
            word_app.mkdir()
            output_docx = root / "word-write.docx"
            with zipfile.ZipFile(output_docx, "w") as archive:
                archive.writestr("word/document.xml", "<w:t>OmniControl write smoke</w:t>")
            stdout = json.dumps(
                {
                    "status": "ok",
                    "output": str(output_docx),
                    "word_path": str(word_app),
                }
            )
            with patch("omnicontrol.runtime.live_smoke.current_platform", return_value="macos"), patch(
                "omnicontrol.runtime.live_smoke.subprocess.run",
                return_value=_CompletedProcess(stdout=stdout),
            ), patch(
                "omnicontrol.runtime.live_smoke._record_payload",
                side_effect=lambda profile, payload: payload,
            ):
                payload = run_word_write_smoke(
                    output_docx=output_docx,
                    word_path=word_app,
                )
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["exists"])
        self.assertTrue(payload["zip_ok"])
        self.assertEqual(payload["report_path"], str(output_docx.parent / "result.json"))

    def test_word_export_mocked_success_on_macos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            word_app = root / "Microsoft Word.app"
            word_app.mkdir()
            source = root / "source.docx"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("word/document.xml", "<w:t>Source</w:t>")
            output_pdf = root / "word-export.pdf"
            output_pdf.write_bytes(b"%PDF-1.7\n%test\n")
            stdout = json.dumps(
                {
                    "status": "ok",
                    "source": str(source),
                    "output": str(output_pdf),
                    "word_path": str(word_app),
                }
            )
            with patch("omnicontrol.runtime.live_smoke.current_platform", return_value="macos"), patch(
                "omnicontrol.runtime.live_smoke.subprocess.run",
                return_value=_CompletedProcess(stdout=stdout),
            ), patch(
                "omnicontrol.runtime.live_smoke._record_payload",
                side_effect=lambda profile, payload: payload,
            ):
                payload = run_word_export_smoke(
                    source=source,
                    output_pdf=output_pdf,
                    word_path=word_app,
                )
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["exists"])
        self.assertTrue(payload["magic_ok"])

    def test_word_workflow_mocked_success_on_macos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            word_app = root / "Microsoft Word.app"
            word_app.mkdir()
            output_dir = root / "word-workflow"
            output_dir.mkdir()
            output_docx = output_dir / "word-workflow.docx"
            with zipfile.ZipFile(output_docx, "w") as archive:
                archive.writestr(
                    "word/document.xml",
                    "<w:t>OmniControl Word Workflow</w:t><w:t>Step 1: body write</w:t><w:t>Step 2: exported artifact</w:t>",
                )
            stdout = json.dumps(
                {
                    "status": "ok",
                    "output_docx": str(output_docx),
                    "word_path": str(word_app),
                }
            )
            with patch("omnicontrol.runtime.live_smoke.current_platform", return_value="macos"), patch(
                "omnicontrol.runtime.live_smoke.subprocess.run",
                return_value=_CompletedProcess(stdout=stdout),
            ), patch(
                "omnicontrol.runtime.live_smoke._record_payload",
                side_effect=lambda profile, payload: payload,
            ):
                payload = run_word_workflow_smoke(
                    output_dir=output_dir,
                    word_path=word_app,
                )
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["docx_exists"])
        self.assertTrue(payload["docx_zip_ok"])
        self.assertTrue(payload["body_markers_ok"])


if __name__ == "__main__":
    unittest.main()
