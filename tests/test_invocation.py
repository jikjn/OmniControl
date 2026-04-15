from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omnicontrol.runtime.invocation import (
    build_external_command,
    build_script_file_argument,
    materialize_response_file,
    prepare_script_payload,
    should_materialize_script,
)


class InvocationPayloadTests(unittest.TestCase):
    def test_detects_complex_inline_script_as_materialization_required(self) -> None:
        payload = "import pathlib; pathlib.Path(r'C:/x y/out.txt').write_text('ok', encoding='utf-8')"
        self.assertTrue(should_materialize_script(payload))

    def test_materialize_script_preserves_payload_exactly(self) -> None:
        payload = "import pathlib; pathlib.Path(r'C:/x y/out.txt').write_text('ok', encoding='utf-8')"
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = prepare_script_payload(
                payload,
                Path(tmp_dir),
                stem="demo payload",
                suffix=".py",
                prefer_file=True,
            )
            self.assertEqual(result.mode, "file")
            self.assertEqual(Path(result.value).read_text(encoding="utf-8"), payload)

    def test_prefixed_script_argument_uses_path_not_inline_payload(self) -> None:
        script_path = Path(r"C:\tmp path\payload.py")
        args = build_script_file_argument(script_path, flag="-script", style="prefixed")
        self.assertEqual(args, [r"-script=C:\tmp path\payload.py"])
        self.assertNotIn("import pathlib", args[0])

    def test_separate_script_argument_keeps_flag_and_path_as_two_args(self) -> None:
        args = build_script_file_argument(r"C:\tmp path\payload.jsx", flag="--script", style="separate")
        self.assertEqual(args, ["--script", r"C:\tmp path\payload.jsx"])

    def test_response_file_argument_materializes_argv(self) -> None:
        argv = ["--query", "a value with spaces", "--expr", "x='a;b'"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            response = materialize_response_file(argv, Path(tmp_dir), stem="vendor args")
            response_path = Path(response.path)
            self.assertEqual(response.argv, argv)
            self.assertEqual(response.argument, f"@{response_path}")
            contents = response_path.read_text(encoding="utf-8")
            self.assertIn('"a value with spaces"', contents)
            self.assertIn("x='a;b'", contents)

    def test_policy_materializes_non_ascii_or_long_payload(self) -> None:
        self.assertTrue(should_materialize_script("print('中文')"))
        self.assertTrue(should_materialize_script("x" * 121))

    def test_build_external_command_returns_argv_list(self) -> None:
        command = build_external_command(r"C:\Program Files\Vendor\App.exe", ["--script", r"C:\tmp path\a.py"])
        self.assertEqual(
            command,
            [r"C:\Program Files\Vendor\App.exe", "--script", r"C:\tmp path\a.py"],
        )


class UnrealSmokeScriptRegressionTests(unittest.TestCase):
    def test_ue_python_write_smoke_uses_script_file_not_inline_python(self) -> None:
        script = Path("omnicontrol/runtime/scripts/ue_python_write_smoke.ps1").read_text(encoding="utf-8")
        self.assertIn('"-script=$pyFile"', script)
        self.assertIn("Join-WindowsArguments", script)
        self.assertNotIn('"-script=$python"', script)
        self.assertNotIn("cmd /c $cmd", script)


if __name__ == "__main__":
    unittest.main()
