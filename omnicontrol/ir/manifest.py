from __future__ import annotations

from pathlib import Path

from omnicontrol.models import AdapterPlan, DetectionResult, HarnessManifest, slugify


def build_manifest(
    project_name: str,
    detection: DetectionResult,
    plan: AdapterPlan,
    *,
    output_dir: str | None = None,
) -> HarnessManifest:
    return HarnessManifest(
        project=project_name,
        display_name=detection.display_name,
        slug=slugify(detection.display_name),
        detection=detection,
        plan=plan,
        output_dir=str(Path(output_dir)) if output_dir else None,
    )
