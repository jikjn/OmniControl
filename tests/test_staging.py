from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omnicontrol.runtime.staging import ensure_ascii_staging, needs_ascii_staging


class StagingTests(unittest.TestCase):
    def test_detects_non_ascii_path(self) -> None:
        self.assertTrue(needs_ascii_staging(Path("测试.txt")))

    def test_stages_unicode_file_to_ascii_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = root / "测试.txt"
            src.write_text("hello", encoding="utf-8")
            info = ensure_ascii_staging(src, root / "stage", staged_name="sample")
            self.assertTrue(info.used_staging)
            self.assertTrue(Path(info.staged_path).exists())


if __name__ == "__main__":
    unittest.main()
