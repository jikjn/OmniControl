from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import shutil


@dataclass(slots=True)
class StagingInfo:
    original_path: str
    staged_path: str
    used_staging: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def needs_ascii_staging(path: Path) -> bool:
    try:
        str(path).encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def ensure_ascii_staging(path: Path, staging_root: Path, *, staged_name: str = "staged-target") -> StagingInfo:
    staging_root.mkdir(parents=True, exist_ok=True)
    if not needs_ascii_staging(path):
        return StagingInfo(
            original_path=str(path),
            staged_path=str(path),
            used_staging=False,
            reason=None,
        )

    staged_base = staging_root / staged_name
    if staged_base.exists():
        shutil.rmtree(staged_base, ignore_errors=True)
    staged_base.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        target = staged_base / f"{staged_name}{path.suffix}"
        shutil.copy2(path, target)
    else:
        shutil.copytree(path, staged_base, dirs_exist_ok=True)
        project_files = list(staged_base.glob("*.uproject"))
        if len(project_files) == 1:
            target = staged_base / f"{staged_name}.uproject"
            project_files[0].rename(target)
        else:
            target = staged_base

    return StagingInfo(
        original_path=str(path),
        staged_path=str(target),
        used_staging=True,
        reason="non_ascii_path",
    )
