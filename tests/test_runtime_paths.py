from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omnicontrol.runtime.kb import kb_path, load_kb, save_kb
from omnicontrol.runtime.paths import legacy_kb_path, resolve_run_output_dir, resolve_runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_runtime_root_is_independent_of_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            cwd_a = root / "repo-a"
            cwd_b = root / "repo-b"
            cwd_a.mkdir()
            cwd_b.mkdir()
            first = resolve_runtime_paths(cwd=cwd_a, home=home)
            second = resolve_runtime_paths(cwd=cwd_b, home=home)
        self.assertEqual(first.root, second.root)
        self.assertEqual(first.kb_path, second.kb_path)

    def test_explicit_output_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            override = root / "custom-out"
            runtime_paths = resolve_runtime_paths(home=root / "home")
            resolved = resolve_run_output_dir("finder-open", output=override, runtime_paths=runtime_paths)
        self.assertEqual(resolved, override)

    def test_kb_load_can_read_legacy_repo_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            legacy = legacy_kb_path(cwd=cwd)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(json.dumps({"version": 1, "updated_at": None, "cases": []}), encoding="utf-8")
            loaded = load_kb(cwd=cwd)
        self.assertEqual(loaded["version"], 1)

    def test_kb_save_writes_to_stable_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "repo"
            cwd.mkdir()
            save_kb({"version": 1, "updated_at": None, "cases": []}, cwd=cwd)
            stable_path = kb_path(cwd=cwd)
        self.assertTrue(stable_path.exists())
        self.assertNotEqual(stable_path, legacy_kb_path(cwd=cwd))


if __name__ == "__main__":
    unittest.main()
