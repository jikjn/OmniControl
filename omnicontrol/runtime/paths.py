from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

from omnicontrol.models import current_platform


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    root: Path
    knowledge_dir: Path
    kb_path: Path
    artifacts_dir: Path
    smoke_output_dir: Path


def _default_runtime_root(
    *,
    env: Mapping[str, str],
    home: Path,
    platform_name: str,
) -> Path:
    explicit = env.get("OMNICONTROL_HOME") or env.get("OMNICONTROL_RUNTIME_ROOT")
    if explicit:
        return Path(explicit).expanduser()
    if platform_name == "windows":
        local_appdata = env.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "OmniControl"
        return home / "AppData" / "Local" / "OmniControl"
    if platform_name == "macos":
        return home / "Library" / "Application Support" / "OmniControl"
    data_home = env.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "omnicontrol"
    return home / ".local" / "share" / "omnicontrol"


def resolve_runtime_paths(
    *,
    cwd: Path | None = None,
    explicit_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform_name: str | None = None,
) -> RuntimePaths:
    resolved_env = env or os.environ
    resolved_home = (home or Path.home()).expanduser()
    resolved_platform = platform_name or current_platform()
    root = (explicit_root or _default_runtime_root(env=resolved_env, home=resolved_home, platform_name=resolved_platform)).expanduser()
    knowledge_dir = root / "knowledge"
    artifacts_dir = root / "artifacts"
    return RuntimePaths(
        root=root,
        knowledge_dir=knowledge_dir,
        kb_path=knowledge_dir / "kb.json",
        artifacts_dir=artifacts_dir,
        smoke_output_dir=artifacts_dir / "smoke-output",
    )


def legacy_kb_path(*, cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    return base / "knowledge" / "kb.json"


def resolve_run_output_dir(
    profile: str,
    *,
    output: Path | None = None,
    runtime_paths: RuntimePaths | None = None,
) -> Path:
    if output is not None:
        return output
    paths = runtime_paths or resolve_runtime_paths()
    return paths.smoke_output_dir / profile
