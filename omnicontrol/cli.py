from __future__ import annotations

import argparse
import json
from pathlib import Path

from omnicontrol.benchmark import run_benchmark
from omnicontrol.detector.capability_detector import CapabilityDetector
from omnicontrol.emitters.scaffold import scaffold_project
from omnicontrol.ir.manifest import build_manifest
from omnicontrol.models import to_jsonable
from omnicontrol.planner.adapter_selector import AdapterSelector
from omnicontrol.runtime.live_smoke import run_smoke
from omnicontrol.runtime.registry import profile_choices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnicontrol",
        description="Capability-first control-plane scaffolder.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("detect", "plan", "scaffold"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("target", help="Target path, URL or software identifier.")
        subparser.add_argument("--platform", default="auto", help="auto|windows|macos|linux")
        subparser.add_argument(
            "--kind",
            default="auto",
            help="auto|desktop|web|service|document|codebase",
        )
        subparser.add_argument(
            "--need",
            action="append",
            default=[],
            help="Repeatable workload hint such as office, export, browser, dom, shell.",
        )
        subparser.add_argument("--json", action="store_true", help="Print JSON output.")
        if name == "scaffold":
            subparser.add_argument(
                "--output",
                default=None,
                help="Directory for generated artifacts. Defaults to ./generated/<slug>.",
            )

    bench = subparsers.add_parser("benchmark")
    bench.add_argument("config", help="Path to a benchmark JSON config.")
    bench.add_argument(
        "--output",
        default=None,
        help="Directory for benchmark reports. Defaults to ./benchmark-output/<config-stem>.",
    )
    bench.add_argument("--json", action="store_true", help="Print JSON output.")
    bench.add_argument(
        "--no-scaffold",
        action="store_true",
        help="Only run detect/plan without generating scaffold artifacts.",
    )

    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("profile", choices=profile_choices())
    smoke.add_argument("--source", help="Source file for profiles that require it.")
    smoke.add_argument(
        "--output",
        default=None,
        help="Output PDF path for word-export, or output directory for chrome-cdp.",
    )
    smoke.add_argument("--query", default=None, help="Search query for everything-search.")
    smoke.add_argument("--url", default=None, help="Target URL for chrome-cdp.")
    smoke.add_argument("--chrome-path", default=None, help="Override chrome.exe path.")
    smoke.add_argument("--word-path", default=None, help="Override Word executable or app path.")
    smoke.add_argument("--app-path", default=None, help="Override app or launcher path for generic IDE profiles.")
    smoke.add_argument("--json", action="store_true", help="Print JSON output.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "benchmark":
        config_path = Path(args.config)
        output_dir = (
            Path(args.output)
            if args.output
            else Path.cwd() / "benchmark-output" / config_path.stem
        )
        report = run_benchmark(
            config_path,
            output_dir=output_dir,
            scaffold=not args.no_scaffold,
        )
        return _print_result(report, use_json=args.json)
    if args.command == "smoke":
        payload = run_smoke(
            args.profile,
            source=args.source,
            output=args.output,
            query=args.query,
            url=args.url,
            chrome_path=args.chrome_path,
            word_path=args.word_path,
            app_path=args.app_path,
        )
        return _print_result(payload, use_json=args.json)

    detector = CapabilityDetector()
    detection = detector.detect(
        args.target,
        platform=args.platform,
        target_kind=args.kind,
        needs=args.need,
    )

    if args.command == "detect":
        return _print_result(to_jsonable(detection), use_json=args.json)

    selector = AdapterSelector()
    plan = selector.select(detection)
    manifest = build_manifest("OmniControl", detection, plan)

    if args.command == "plan":
        return _print_result(to_jsonable(manifest), use_json=args.json)

    output_dir = Path(args.output) if args.output else Path.cwd() / "generated" / manifest.slug
    manifest = build_manifest("OmniControl", detection, plan, output_dir=str(output_dir))
    generated_files = [str(path) for path in scaffold_project(manifest, output_dir)]
    payload = to_jsonable(manifest)
    payload["generated_files"] = generated_files
    return _print_result(payload, use_json=args.json)


def _print_result(payload: dict, *, use_json: bool) -> int:
    if use_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if "profile" in payload and "status" in payload:
        print(f"Smoke profile: {payload['profile']}")
        print(f"Status: {payload['status']}")
        if "output" in payload:
            print(f"Artifact: {payload['output']}")
        if "screenshot" in payload:
            print(f"Screenshot: {payload['screenshot']}")
        if "before" in payload and "after" in payload:
            print(f"Before: {payload['before']}")
            print(f"After: {payload['after']}")
        if "status_text" in payload:
            print(f"Status Text: {payload['status_text']}")
        if "matches" in payload:
            print(f"Matches: {', '.join(payload['matches'])}")
        if "title" in payload:
            print(f"Title: {payload['title']}")
        if "family" in payload:
            print(f"Family: {payload['family']}")
        if "window_name" in payload:
            print(f"Window: {payload['window_name']}")
        if "textarea_value" in payload:
            print(f"Textarea: {payload['textarea_value']}")
        if "marker" in payload:
            print(f"Marker: {payload['marker']}")
        if "page_advanced" in payload:
            print(f"Page Advanced: {payload['page_advanced']}")
        if "all_required_steps_changed" in payload:
            print(f"Workflow Changed: {payload['all_required_steps_changed']}")
        if "all_required_steps_ok" in payload:
            print(f"Workflow OK: {payload['all_required_steps_ok']}")
        if "svg_ok" in payload:
            print(f"SVG OK: {payload['svg_ok']}")
        if "zip_ok" in payload:
            print(f"DOCX ZIP OK: {payload['zip_ok']}")
        if "write_ok" in payload:
            print(f"Write OK: {payload['write_ok']}")
        if "blockers" in payload:
            print(f"Blockers: {', '.join(payload['blockers'])}")
        if "strategy" in payload:
            print(f"Strategy Status: {payload['strategy']['status']}")
            if payload["strategy"]["blockers"]:
                print(f"Strategy Blockers: {', '.join(payload['strategy']['blockers'])}")
        if "report_path" in payload:
            print(f"Report: {payload['report_path']}")
        if payload.get("error"):
            print(f"Error: {payload['error']}")
        return 0

    if "summary" in payload and "items" in payload:
        print(f"Benchmark report: {payload['report_path']}")
        print(
            f"Total: {payload['summary']['total']} | "
            f"Primary matches: {payload['summary']['primary_matches']} | "
            f"Language matches: {payload['summary']['language_matches']}"
        )
        for item in payload["items"]:
            print(
                f"  - {item['name']}: {item['plan']['primary_adapter']} / "
                f"{item['plan']['language']['primary']}"
            )
        return 0

    if "plan" not in payload:
        print(f"Target: {payload['display_name']}")
        print(f"Platform: {payload['platform']} | Kind: {payload['target_kind']}")
        print("Capabilities:")
        for capability in payload["capabilities"]:
            reasons = "; ".join(capability["reasons"][:2])
            print(f"  - {capability['name']} ({capability['confidence']:.2f}) | {reasons}")
        return 0

    print(f"Target: {payload['display_name']}")
    print(
        f"Primary adapter: {payload['plan']['primary_adapter']} | "
        f"Language: {payload['plan']['language']['primary']}"
    )
    print(f"Fallbacks: {', '.join(payload['plan']['fallback_adapters']) or 'none'}")
    print(f"State model: {payload['plan']['state_model']}")
    print("Suggested actions:")
    for action in payload["plan"]["suggested_actions"]:
        print(f"  - {action}")
    print("Verification:")
    for method in payload["plan"]["verification_methods"]:
        print(f"  - {method}")
    if "generated_files" in payload:
        print("Generated files:")
        for path in payload["generated_files"]:
            print(f"  - {path}")
    return 0
