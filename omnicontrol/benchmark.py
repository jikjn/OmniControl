from __future__ import annotations

from pathlib import Path
import json

from omnicontrol.detector.capability_detector import CapabilityDetector
from omnicontrol.emitters.scaffold import scaffold_project
from omnicontrol.ir.manifest import build_manifest
from omnicontrol.models import to_jsonable
from omnicontrol.planner.adapter_selector import AdapterSelector


def run_benchmark(
    config_path: Path,
    *,
    output_dir: Path,
    scaffold: bool = True,
) -> dict:
    detector = CapabilityDetector()
    selector = AdapterSelector()

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) and "items" in raw else raw

    output_dir.mkdir(parents=True, exist_ok=True)
    scaffold_root = output_dir / "scaffolds"
    if scaffold:
        scaffold_root.mkdir(parents=True, exist_ok=True)

    report_items = []
    primary_matches = 0
    language_matches = 0

    for item in items:
        detection = detector.detect(
            item["target"],
            platform=item.get("platform", "auto"),
            target_kind=item.get("kind", "auto"),
            needs=item.get("needs", []),
        )
        plan = selector.select(detection)
        manifest = build_manifest("OmniControl", detection, plan)
        generated_files: list[str] = []
        if scaffold:
            target_dir = scaffold_root / manifest.slug
            manifest = build_manifest(
                "OmniControl",
                detection,
                plan,
                output_dir=str(target_dir),
            )
            generated_files = [str(path) for path in scaffold_project(manifest, target_dir)]

        expected_primary = item.get("expected_primary")
        expected_language = item.get("expected_language")
        primary_ok = expected_primary is None or plan.primary_adapter == expected_primary
        language_ok = expected_language is None or plan.language.primary == expected_language

        if primary_ok:
            primary_matches += 1
        if language_ok:
            language_matches += 1

        report_items.append(
            {
                "name": item["name"],
                "category": item.get("category"),
                "target": item["target"],
                "expected_primary": expected_primary,
                "expected_language": expected_language,
                "primary_match": primary_ok,
                "language_match": language_ok,
                "detection": to_jsonable(detection),
                "plan": to_jsonable(plan),
                "generated_files": generated_files,
            }
        )

    summary = {
        "total": len(report_items),
        "primary_matches": primary_matches,
        "language_matches": language_matches,
        "scaffolded": scaffold,
    }
    report = {
        "config": str(config_path),
        "summary": summary,
        "items": report_items,
    }
    report_path = output_dir / "benchmark-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
