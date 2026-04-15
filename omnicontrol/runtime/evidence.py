from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from omnicontrol.runtime.paths import RuntimePaths, resolve_runtime_paths


CANONICAL_ARTIFACT_KEYS = (
    "output",
    "output_docx",
    "screenshot",
    "before",
    "after",
    "xml_path",
    "legacy_xml_path",
    "runtime_auth_xml_path",
)


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    name: str
    path: str
    kind: str = "file"


@dataclass(frozen=True, slots=True)
class ResultBundle:
    run_id: str
    profile: str
    status: str | None
    generated_at: str
    report_path: str
    runtime: dict[str, str]
    artifacts: list[ArtifactRef]


def _coerce_path(value: Any) -> Path | None:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return Path(value)
    return None


def _collect_artifacts(payload: dict[str, Any]) -> list[ArtifactRef]:
    artifacts: list[ArtifactRef] = []
    seen: set[tuple[str, str]] = set()
    for key in CANONICAL_ARTIFACT_KEYS:
        path = _coerce_path(payload.get(key))
        if path is None:
            continue
        ref = (key, str(path))
        if ref in seen:
            continue
        seen.add(ref)
        artifacts.append(ArtifactRef(name=key, path=str(path)))
    return artifacts


def _append_bundle_fallback_artifact(
    artifacts: list[ArtifactRef],
    *,
    report_path: Path,
) -> list[ArtifactRef]:
    if artifacts:
        return artifacts
    return [
        ArtifactRef(
            name="result_bundle",
            path=str(report_path),
            kind="report",
        )
    ]


def write_result_bundle(
    profile: str,
    payload: dict[str, Any],
    *,
    report_dir: Path,
    runtime_paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "result.json"
    resolved_runtime = runtime_paths or resolve_runtime_paths()
    artifacts = _append_bundle_fallback_artifact(
        _collect_artifacts(payload),
        report_path=report_path,
    )
    bundle = dict(payload)
    bundle.setdefault("profile", profile)
    bundle.setdefault("run_id", uuid4().hex)
    bundle["generated_at"] = datetime.now(timezone.utc).isoformat()
    bundle["report_path"] = str(report_path)
    bundle["runtime"] = {
        "root": str(resolved_runtime.root),
        "knowledge_dir": str(resolved_runtime.knowledge_dir),
        "kb_path": str(resolved_runtime.kb_path),
        "smoke_output_dir": str(resolved_runtime.smoke_output_dir),
    }
    bundle["artifacts"] = [asdict(item) for item in artifacts]
    result_bundle = ResultBundle(
        run_id=str(bundle["run_id"]),
        profile=str(bundle["profile"]),
        status=bundle.get("status"),
        generated_at=str(bundle["generated_at"]),
        report_path=str(bundle["report_path"]),
        runtime=dict(bundle["runtime"]),
        artifacts=artifacts,
    )
    bundle["bundle"] = asdict(result_bundle)
    report_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return bundle
