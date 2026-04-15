from __future__ import annotations

from importlib import resources
from pathlib import Path
import json
import re
import socket
import subprocess
import tempfile
import time
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from omnicontrol.runtime.contracts import SMOKE_CONTRACTS
from omnicontrol.runtime.adaptive_startup import (
    adaptive_launch_cdp_app,
    adaptive_launch_cli_window_app,
    cleanup_process_group,
)
from omnicontrol.runtime.kb import PROFILE_METADATA, is_url_substitution_candidate, record_payload
from omnicontrol.runtime.kb import recommended_launch_overrides
from omnicontrol.runtime.kb import secondary_profile_specs
from omnicontrol.runtime.orchestrator import (
    AttemptSpec,
    PreflightCheck,
    path_exists_check,
)
from omnicontrol.runtime.staging import ensure_ascii_staging
from omnicontrol.runtime.remediation import build_attempts_from_actions
from omnicontrol.runtime.pivots import build_pivot_attempts_from_actions, run_with_strategy_pivots
from omnicontrol.runtime.strategy import evaluate_contract
from omnicontrol.runtime.invocation import prepare_script_payload
from omnicontrol.runtime.transports import (
    TransportAttemptSpec,
    TransportDescriptor,
    build_software_native_plan,
    run_ordered_transport_attempts,
)
from omnicontrol.runtime.windows_ipc import (
    TaggedPacketSpec,
    TopLevelWindowInfo,
    build_tagged_packet,
    close_top_level_windows,
    encode_utf16le_text,
    find_process_ids,
    list_top_level_windows,
    send_wm_copydata,
)
from omnicontrol.models import current_platform


DEFAULT_CHROME_URL = "data:text/html,<title>OmniControl Smoke</title><h1>OmniControl Smoke</h1>"
DEFAULT_WORD_PATH = Path(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE")
DEFAULT_CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEFAULT_ILLUSTRATOR_OUTPUT = Path.cwd() / "smoke-output" / "illustrator-export" / "illustrator-smoke.svg"
DEFAULT_MASTERPDF_PATH = Path(r"C:\Program Files (x86)\MasterPDF\MasterPDF.exe")
DEFAULT_QQMUSIC_PATH = Path(r"C:\Program Files (x86)\Tencent\QQMusic\QQMusic.exe")


def run_smoke(
    profile: str,
    *,
    source: str | None = None,
    output: str | None = None,
    query: str | None = None,
    url: str | None = None,
    chrome_path: str | None = None,
    word_path: str | None = None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if profile in _profile_chain:
        chain = " -> ".join([*_profile_chain, profile])
        raise RuntimeError(f"Detected recursive secondary profile cycle: {chain}")
    next_chain = (*_profile_chain, profile)
    if profile == "finder-open":
        return run_finder_open_smoke(
            target_path=Path(source) if source else None,
            output_dir=Path(output) if output else None,
        )
    if profile == "safari-open":
        return run_safari_open_smoke(
            url=url,
            output_dir=Path(output) if output else None,
        )
    if profile == "safari-dom-write":
        return run_safari_dom_write_smoke(
            url=url,
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "word-export":
        if not source:
            raise ValueError("word-export requires --source")
        return run_word_export_smoke(
            source=Path(source),
            output_pdf=Path(output) if output else None,
            word_path=Path(word_path) if word_path else _resolve_word_path(),
        )
    if profile == "word-write":
        return run_word_write_smoke(
            output_docx=Path(output) if output else None,
            word_path=Path(word_path) if word_path else _resolve_word_path(),
        )
    if profile == "word-workflow":
        return run_word_workflow_smoke(
            output_dir=Path(output) if output else None,
            word_path=Path(word_path) if word_path else _resolve_word_path(),
            _profile_chain=next_chain,
        )
    if profile == "chrome-cdp":
        return run_chrome_cdp_smoke(
            url=url or DEFAULT_CHROME_URL,
            output_dir=Path(output) if output else None,
            chrome_path=Path(chrome_path) if chrome_path else _resolve_chrome_path(),
        )
    if profile == "chrome-form-write":
        return run_chrome_form_write_smoke(
            output_dir=Path(output) if output else None,
            chrome_path=Path(chrome_path) if chrome_path else _resolve_chrome_path(),
            _profile_chain=next_chain,
        )
    if profile == "chrome-workflow":
        return run_cdp_workflow_smoke(
            profile="chrome-workflow",
            app_path=Path(chrome_path) if chrome_path else _resolve_chrome_path(),
            process_name="chrome",
            output_dir=Path(output) if output else None,
            startup_args=["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "about:blank"],
            isolate_user_data=True,
            allow_attach_existing=False,
            clean_existing=False,
            prefer_title_contains="",
            _profile_chain=next_chain,
            workflow={
                "steps": [
                    {"name": "write_step_1", "kind": "set", "title": "OmniControl Chrome Step 1", "marker": "step1", "expect_marker": "step1", "required": True},
                    {"name": "write_step_2", "kind": "set", "title": "OmniControl Chrome Step 2", "marker": "step2", "expect_title": "OmniControl Chrome Step 2", "expect_marker": "step2", "required": True},
                    {"name": "write_step_3", "kind": "set", "title": "OmniControl Chrome Step 3", "marker": "step3", "expect_title": "OmniControl Chrome Step 3", "expect_marker": "step3", "required": True},
                ]
            },
        )
    if profile == "everything-search":
        if not query:
            raise ValueError("everything-search requires --query")
        return run_everything_search_smoke(
            query=query,
            output_dir=Path(output) if output else None,
        )
    if profile == "qqmusic-play":
        if not query:
            raise ValueError("qqmusic-play requires --query")
        return run_qqmusic_play_smoke(
            query=query,
            output_dir=Path(output) if output else None,
            qqmusic_path=DEFAULT_QQMUSIC_PATH,
        )
    if profile == "illustrator-export":
        return run_illustrator_export_smoke(
            output_path=Path(output) if output else None,
        )
    if profile == "masterpdf-pagedown":
        if not source:
            raise ValueError("masterpdf-pagedown requires --source")
        return run_masterpdf_pagedown_smoke(
            source=Path(source),
            output_dir=Path(output) if output else None,
            masterpdf_path=DEFAULT_MASTERPDF_PATH,
        )
    if profile == "masterpdf-zoom":
        if not source:
            raise ValueError("masterpdf-zoom requires --source")
        return run_selfdraw_write_smoke(
            profile="masterpdf-zoom",
            executable_path=DEFAULT_MASTERPDF_PATH,
            source=Path(source),
            window_class="MASTER_PDF_FRAME",
            input_sequence="^{ADD}",
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "masterpdf-workflow":
        if not source:
            raise ValueError("masterpdf-workflow requires --source")
        return run_selfdraw_workflow_smoke(
            profile="masterpdf-workflow",
            executable_path=DEFAULT_MASTERPDF_PATH,
            source=Path(source),
            window_class="MASTER_PDF_FRAME",
            workflow={
                "steps": [
                    {"name": "zoom_in_1", "sequence": "^{ADD}", "required": True, "wait_ms": 1000},
                    {"name": "zoom_in_2", "sequence": "^{ADD}", "required": True, "wait_ms": 1000},
                    {"name": "page_down", "sequence": "{PGDN}", "required": True, "wait_ms": 1000},
                ]
            },
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "quark-cdp":
        return run_quark_cdp_smoke(
            output_dir=Path(output) if output else None,
        )
    if profile == "quark-cdp-write":
        return run_quark_cdp_write_smoke(
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "quark-workflow":
        return run_cdp_workflow_smoke(
            profile="quark-workflow",
            app_path=Path(r"C:\Users\33032\AppData\Local\Programs\Quark\quark.exe"),
            process_name="quark",
            output_dir=Path(output) if output else None,
            startup_args=[],
            isolate_user_data=False,
            allow_attach_existing=True,
            clean_existing=False,
            prefer_title_contains="夸克网盘",
            _profile_chain=next_chain,
            workflow={
                "steps": [
                    {"name": "write_step_1", "kind": "set", "title": "OmniControl Quark Step 1", "marker": "step1", "expect_marker": "step1", "required": True},
                    {"name": "write_step_2", "kind": "set", "title": "OmniControl Quark Step 2", "marker": "step2", "expect_title": "OmniControl Quark Step 2", "expect_marker": "step2", "required": True},
                    {"name": "write_step_3", "kind": "set", "title": "OmniControl Quark Step 3", "marker": "step3", "expect_title": "OmniControl Quark Step 3", "expect_marker": "step3", "required": True},
                ]
            },
        )
    if profile == "trae-open":
        return run_trae_open_smoke(
            workspace=Path(source) if source else Path.cwd(),
            output_dir=Path(output) if output else None,
        )
    if profile == "trae-cdp-write":
        return run_trae_cdp_write_smoke(
            workspace=Path(source) if source else Path.cwd(),
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "trae-workflow":
        return run_cdp_workflow_smoke(
            profile="trae-workflow",
            app_path=Path(r"C:\Users\33032\AppData\Local\Programs\Trae\Trae.exe"),
            process_name="Trae",
            output_dir=Path(output) if output else None,
            startup_args=["-n", str(Path(source) if source else Path.cwd())],
            isolate_user_data=True,
            allow_attach_existing=False,
            clean_existing=True,
            prefer_title_contains="vscode-file://",
            workspace=Path(source) if source else Path.cwd(),
            _profile_chain=next_chain,
            workflow={
                "steps": [
                    {"name": "write_step_1", "kind": "set", "title": "OmniControl Trae Step 1", "marker": "step1", "expect_marker": "step1", "required": True},
                    {"name": "write_step_2", "kind": "set", "title": "OmniControl Trae Step 2", "marker": "step2", "expect_title": "OmniControl Trae Step 2", "expect_marker": "step2", "required": True},
                    {"name": "write_step_3", "kind": "set", "title": "OmniControl Trae Step 3", "marker": "step3", "expect_title": "OmniControl Trae Step 3", "expect_marker": "step3", "required": True},
                ]
            },
        )
    if profile == "cadv-view":
        if not source:
            raise ValueError("cadv-view requires --source")
        return run_cadviewer_view_smoke(
            source=Path(source),
            output_dir=Path(output) if output else None,
            app_path=Path(r"C:\Program Files (x86)\CadViewerVE\XDCadViewer.exe"),
        )
    if profile == "cadv-zoom":
        if not source:
            raise ValueError("cadv-zoom requires --source")
        return run_selfdraw_write_smoke(
            profile="cadv-zoom",
            executable_path=Path(r"C:\Program Files (x86)\CadViewerVE\XDCadViewer.exe"),
            source=Path(source),
            window_class="CadViewerVE_Cls",
            input_sequence="^{ADD}",
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "cadv-workflow":
        if not source:
            raise ValueError("cadv-workflow requires --source")
        return run_selfdraw_workflow_smoke(
            profile="cadv-workflow",
            executable_path=Path(r"C:\Program Files (x86)\CadViewerVE\XDCadViewer.exe"),
            source=Path(source),
            window_class="CadViewerVE_Cls",
            workflow={
                "steps": [
                    {"name": "zoom_in_1", "sequence": "^{ADD}", "required": True, "wait_ms": 1000},
                    {"name": "zoom_in_2", "sequence": "^{ADD}", "required": True, "wait_ms": 1000},
                    {"name": "zoom_in_3", "sequence": "^{ADD}", "required": True, "wait_ms": 1000},
                ]
            },
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "nx-diagnose":
        return run_nx_diagnose_smoke(
            output_dir=Path(output) if output else None,
        )
    if profile == "isight-diagnose":
        return run_isight_diagnose_smoke(
            output_dir=Path(output) if output else None,
        )
    if profile == "ue-diagnose":
        return run_ue_diagnose_smoke(
            output_dir=Path(output) if output else None,
        )
    if profile == "ue-python-write":
        return run_ue_python_write_smoke(
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    raise ValueError(f"Unknown smoke profile: {profile}")


def _finalize_payload(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    contract = SMOKE_CONTRACTS.get(profile)
    if contract is None:
        return payload
    structured = evaluate_contract(payload, contract)
    payload["raw_status"] = payload.get("status")
    payload["status"] = structured.status
    payload["strategy"] = structured.to_dict()
    return payload


def _record_payload(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload["knowledge"] = record_payload(profile, payload)
    return payload


def run_finder_open_smoke(
    *,
    target_path: Path | None,
    output_dir: Path | None,
) -> dict:
    _require_macos("finder-open")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "finder-open"
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _run_osascript_profile(
        "finder_open_smoke.applescript",
        args=[str(target_path)] if target_path is not None else [],
    )
    payload["profile"] = "finder-open"
    payload = _finalize_payload("finder-open", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("finder-open", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "finder-open smoke failed"))
    return payload


def run_safari_open_smoke(
    *,
    url: str | None,
    output_dir: Path | None,
) -> dict:
    _require_macos("safari-open")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "safari-open"
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _run_osascript_profile(
        "safari_open_smoke.applescript",
        args=[url] if url else [],
    )
    payload["profile"] = "safari-open"
    payload = _finalize_payload("safari-open", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("safari-open", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "safari-open smoke failed"))
    return payload


def run_safari_dom_write_smoke(
    *,
    url: str | None,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    _require_macos("safari-dom-write")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "safari-dom-write"
    output_dir.mkdir(parents=True, exist_ok=True)

    def _attempt() -> dict[str, Any]:
        return _run_osascript_profile(
            "safari_dom_write_smoke.applescript",
            args=[url] if url else [],
        )

    def _plan_safari_write_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            "safari-dom-write",
            raw_payload=raw_payload,
            output_dir=output_dir,
            url=url,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            "safari-dom-write",
            _finalize_payload("safari-dom-write", dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile="safari-dom-write",
        preflight=[],
        primary_attempts=[
            AttemptSpec(name="safari_dom_write", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_safari_write_pivots,
    )
    payload["profile"] = "safari-dom-write"
    payload = _finalize_payload("safari-dom-write", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("safari-dom-write", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "safari-dom-write smoke failed"))
    return payload


def run_word_export_smoke(
    *,
    source: Path,
    output_pdf: Path | None,
    word_path: Path,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(f"Source document not found: {source}")
    if not word_path.exists():
        raise FileNotFoundError(f"WINWORD.EXE not found: {word_path}")

    if output_pdf is None:
        output_dir = Path.cwd() / "smoke-output" / "word-export"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_pdf = output_dir / f"{source.stem}-export.pdf"
    else:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

    script_path = _resource_path("word_export_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-SourceDocx",
        str(source),
        "-OutputPdf",
        str(output_pdf),
        "-WordPath",
        str(word_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=False,
        check=False,
    )
    payload = _parse_json_output(result.stdout, result.stderr)
    payload["profile"] = "word-export"
    payload = _finalize_payload("word-export", payload)
    payload["command"] = command
    payload["returncode"] = result.returncode
    report_path = output_pdf.parent / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("word-export", payload)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "word-export smoke failed"))
    return payload


def run_word_write_smoke(
    *,
    output_docx: Path | None,
    word_path: Path,
) -> dict:
    if not word_path.exists():
        raise FileNotFoundError(f"WINWORD.EXE not found: {word_path}")
    if output_docx is None:
        output_docx = Path.cwd() / "smoke-output" / "word-write" / "word-write-smoke.docx"
    output_docx.parent.mkdir(parents=True, exist_ok=True)

    script_path = _resource_path("word_write_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-OutputDocx",
        str(output_docx),
        "-WordPath",
        str(word_path),
    ]
    result = subprocess.run(command, capture_output=True, text=False, check=False)
    payload = _parse_json_output(result.stdout, result.stderr)
    payload["profile"] = "word-write"
    payload = _finalize_payload("word-write", payload)
    payload["command"] = command
    payload["returncode"] = result.returncode
    report_path = output_docx.parent / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("word-write", payload)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "word-write smoke failed"))
    return payload


def run_word_workflow_smoke(
    *,
    output_dir: Path | None,
    word_path: Path,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if not word_path.exists():
        raise FileNotFoundError(f"WINWORD.EXE not found: {word_path}")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "word-workflow"
    output_dir.mkdir(parents=True, exist_ok=True)

    def _attempt() -> dict[str, Any]:
        script_path = _resource_path("word_workflow_smoke.ps1")
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-OutputDir",
            str(output_dir),
            "-WordPath",
            str(word_path),
        ]
        result = subprocess.run(command, capture_output=True, text=False, check=False)
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["command"] = command
        payload["returncode"] = result.returncode
        return payload

    def _plan_word_workflow_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            "word-workflow",
            raw_payload=raw_payload,
            output_dir=output_dir,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            "word-workflow",
            _finalize_payload("word-workflow", dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile="word-workflow",
        preflight=[
            PreflightCheck(
                name="word_exists",
                run=lambda: path_exists_check("word_exists", str(word_path)),
            )
        ],
        primary_attempts=[
            AttemptSpec(name="word_workflow", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_word_workflow_pivots,
    )
    payload["profile"] = "word-workflow"
    payload = _finalize_payload("word-workflow", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("word-workflow", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "word-workflow smoke failed"))
    return payload


def run_chrome_cdp_smoke(
    *,
    url: str,
    output_dir: Path | None,
    chrome_path: Path,
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "chrome-cdp"
    output_dir.mkdir(parents=True, exist_ok=True)
    startup, chrome_proc = adaptive_launch_cdp_app(
        app_path=chrome_path,
        process_name="chrome",
        process_group="chrome_cdp",
        output_dir=output_dir,
        startup_args=["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "about:blank"],
        isolate_user_data=True,
        allow_attach_existing=False,
        clean_existing=False,
    )

    try:
        script_path = _resource_path("chrome_cdp_smoke.js")
        command = [
            "node",
            str(script_path),
            "--port",
            str(startup.debug_port),
            "--url",
            url,
            "--output-dir",
            str(output_dir),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["startup"] = startup.to_dict()
        payload["profile"] = "chrome-cdp"
        payload = _finalize_payload("chrome-cdp", payload)
        payload["command"] = command
        payload["chrome_command"] = startup.diagnostics
        payload["port"] = startup.debug_port
        payload["returncode"] = result.returncode
        payload["chrome_pid"] = chrome_proc.pid if chrome_proc else None
        report_path = output_dir / "result.json"
        report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["report_path"] = str(report_path)
        payload = _record_payload("chrome-cdp", payload)
        if result.returncode != 0:
            raise RuntimeError(payload.get("error", "chrome-cdp smoke failed"))
        return payload
    finally:
        if chrome_proc is not None:
            chrome_proc.terminate()
            try:
                chrome_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                chrome_proc.kill()
                chrome_proc.wait(timeout=5)


def run_chrome_form_write_smoke(
    *,
    output_dir: Path | None,
    chrome_path: Path,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "chrome-form-write"
    output_dir.mkdir(parents=True, exist_ok=True)
    def _attempt() -> dict[str, Any]:
        startup, chrome_proc = adaptive_launch_cdp_app(
            app_path=chrome_path,
            process_name="chrome",
            process_group="chrome_form_write",
            output_dir=output_dir,
            startup_args=["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "about:blank"],
            isolate_user_data=True,
            allow_attach_existing=False,
            clean_existing=False,
        )
        try:
            script_path = _resource_path("chrome_form_write_smoke.js")
            command = [
                "node",
                str(script_path),
                "--port",
                str(startup.debug_port),
                "--output-dir",
                str(output_dir),
            ]
            result = subprocess.run(command, capture_output=True, text=False, check=False)
            payload = _parse_json_output(result.stdout, result.stderr)
            payload["startup"] = startup.to_dict()
            payload["command"] = command
            payload["port"] = startup.debug_port
            payload["returncode"] = result.returncode
            return payload
        finally:
            if chrome_proc is not None:
                chrome_proc.terminate()
                try:
                    chrome_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    chrome_proc.kill()
                    chrome_proc.wait(timeout=5)

    def _plan_chrome_write_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            "chrome-form-write",
            raw_payload=raw_payload,
            output_dir=output_dir,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            "chrome-form-write",
            _finalize_payload("chrome-form-write", dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile="chrome-form-write",
        preflight=[
            PreflightCheck(
                name="chrome_exists",
                run=lambda: path_exists_check("chrome_exists", str(chrome_path)),
            )
        ],
        primary_attempts=[
            AttemptSpec(name="chrome_form_write", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_chrome_write_pivots,
    )
    payload["profile"] = "chrome-form-write"
    payload = _finalize_payload("chrome-form-write", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("chrome-form-write", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "chrome-form-write smoke failed"))
    return payload


def run_everything_search_smoke(
    *,
    query: str,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "everything-search"
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = _resource_path("everything_search_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Query",
        query,
        "-EverythingPath",
        r"C:\Program Files\Everything\Everything.exe",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=False,
        check=False,
    )
    payload = _parse_json_output(result.stdout, result.stderr)
    payload["profile"] = "everything-search"
    payload = _finalize_payload("everything-search", payload)
    payload["command"] = command
    payload["returncode"] = result.returncode
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("everything-search", payload)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "everything-search smoke failed"))
    return payload


def run_illustrator_export_smoke(
    *,
    output_path: Path | None,
) -> dict:
    if output_path is None:
        output_path = DEFAULT_ILLUSTRATOR_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    script_path = _resource_path("illustrator_export_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-OutputPath",
        str(output_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=False,
        check=False,
    )
    payload = _parse_json_output(result.stdout, result.stderr)
    payload["profile"] = "illustrator-export"
    payload = _finalize_payload("illustrator-export", payload)
    payload["command"] = command
    payload["returncode"] = result.returncode
    report_path = output_path.parent / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("illustrator-export", payload)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "illustrator-export smoke failed"))
    return payload


def run_masterpdf_pagedown_smoke(
    *,
    source: Path,
    output_dir: Path | None,
    masterpdf_path: Path,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(f"Source PDF not found: {source}")
    if not masterpdf_path.exists():
        raise FileNotFoundError(f"MasterPDF.exe not found: {masterpdf_path}")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "masterpdf-pagedown"
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = _resource_path("masterpdf_pagedown_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-SourcePdf",
        str(source),
        "-MasterPdfPath",
        str(masterpdf_path),
        "-OutputDir",
        str(output_dir),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=False,
        check=False,
    )
    payload = _parse_json_output(result.stdout, result.stderr)
    payload["profile"] = "masterpdf-pagedown"
    payload = _finalize_payload("masterpdf-pagedown", payload)
    payload["command"] = command
    payload["returncode"] = result.returncode
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("masterpdf-pagedown", payload)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "masterpdf-pagedown smoke failed"))
    return payload


def run_desktop_cdp_observe_smoke(
    *,
    app_path: Path,
    output_dir: Path | None,
    startup_args: list[str],
    app_label: str,
) -> dict:
    if not app_path.exists():
        raise FileNotFoundError(f"App not found: {app_path}")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / app_label
    output_dir.mkdir(parents=True, exist_ok=True)

    port = _pick_free_port()
    command = [
        str(app_path),
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        *startup_args,
    ]
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for_cdp(port)
        script_path = _resource_path("desktop_cdp_observe.js")
        node_command = [
            "node",
            str(script_path),
            "--port",
            str(port),
            "--output-dir",
            str(output_dir),
            "--label",
            app_label,
        ]
        result = subprocess.run(
            node_command,
            capture_output=True,
            text=False,
            check=False,
        )
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["profile"] = app_label
        payload = _finalize_payload(app_label, payload)
        payload["command"] = node_command
        payload["launch_command"] = command
        payload["port"] = port
        payload["returncode"] = result.returncode
        report_path = output_dir / "result.json"
        report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["report_path"] = str(report_path)
        if result.returncode != 0:
            raise RuntimeError(payload.get("error", f"{app_label} smoke failed"))
        return payload
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def run_quark_cdp_smoke(
    *,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "quark-cdp"
    output_dir.mkdir(parents=True, exist_ok=True)
    learned = recommended_launch_overrides("quark-cdp")
    startup, proc = adaptive_launch_cdp_app(
        app_path=Path(r"C:\Users\33032\AppData\Local\Programs\Quark\quark.exe"),
        process_name="quark",
        process_group="quark_cdp",
        output_dir=output_dir,
        startup_args=[],
        isolate_user_data=False,
        allow_attach_existing=learned.get("allow_attach_existing", True),
        clean_existing=learned.get("preferred_strategy") == "restart_with_debug_port",
    )
    try:
        script_path = _resource_path("target_cdp_probe.js")
        command = [
            "node",
            str(script_path),
            "--port",
            str(startup.debug_port),
            "--output-dir",
            str(output_dir),
            "--prefer-title-contains",
            "夸克网盘",
            "--mode",
            "observe",
        ]
        result = subprocess.run(command, capture_output=True, text=False, check=False)
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["startup"] = startup.to_dict()
        payload["startup"]["learned_overrides"] = learned
        payload["profile"] = "quark-cdp"
        payload = _finalize_payload("quark-cdp", payload)
        payload["command"] = command
        payload["returncode"] = result.returncode
        report_path = output_dir / "result.json"
        report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["report_path"] = str(report_path)
        payload = _record_payload("quark-cdp", payload)
        if result.returncode != 0:
            raise RuntimeError(payload.get("error", "quark-cdp smoke failed"))
        return payload
    finally:
        cleanup_process_group("quark")


def run_quark_cdp_write_smoke(
    *,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "quark-cdp-write"
    output_dir.mkdir(parents=True, exist_ok=True)

    app_path = Path(r"C:\Users\33032\AppData\Local\Programs\Quark\quark.exe")

    def _attempt() -> dict[str, Any]:
        learned = recommended_launch_overrides("quark-cdp-write")
        startup, proc = adaptive_launch_cdp_app(
            app_path=app_path,
            process_name="quark",
            process_group="quark_cdp_write",
            output_dir=output_dir,
            startup_args=[],
            isolate_user_data=False,
            allow_attach_existing=learned.get("allow_attach_existing", True),
            clean_existing=learned.get("preferred_strategy") == "restart_with_debug_port",
        )
        try:
            script_path = _resource_path("target_cdp_probe.js")
            command = [
                "node",
                str(script_path),
                "--port",
                str(startup.debug_port),
                "--output-dir",
                str(output_dir),
                "--prefer-title-contains",
                "夸克网盘",
                "--mode",
                "write",
                "--write-title",
                "OmniControl Quark Write",
                "--write-marker",
                "ok",
            ]
            result = subprocess.run(command, capture_output=True, text=False, check=False)
            payload = _parse_json_output(result.stdout, result.stderr)
            payload["title"] = payload.get("evaluated_title")
            payload["href"] = payload.get("evaluated_href")
            payload["startup"] = startup.to_dict()
            payload["startup"]["learned_overrides"] = learned
            payload["command"] = command
            payload["returncode"] = result.returncode
            return payload
        finally:
            cleanup_process_group("quark")

    def _plan_quark_write_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            "quark-cdp-write",
            raw_payload=raw_payload,
            output_dir=output_dir,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            "quark-cdp-write",
            _finalize_payload("quark-cdp-write", dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile="quark-cdp-write",
        preflight=[
            PreflightCheck(
                name="quark_exists",
                run=lambda: path_exists_check("quark_exists", str(app_path)),
            )
        ],
        primary_attempts=[
            AttemptSpec(name="quark_write", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_quark_write_pivots,
    )

    payload["profile"] = "quark-cdp-write"
    payload = _finalize_payload("quark-cdp-write", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("quark-cdp-write", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "quark-cdp-write smoke failed"))
    return payload


def run_trae_open_smoke(
    *,
    workspace: Path,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "trae-open"
    output_dir.mkdir(parents=True, exist_ok=True)

    trae_cli = Path(r"C:\Users\33032\AppData\Local\Programs\Trae\bin\trae.cmd")
    learned = recommended_launch_overrides("trae-open")
    startup = adaptive_launch_cli_window_app(
        process_name="Trae",
        process_group="trae_open",
        output_dir=output_dir,
        workspace=workspace,
        command_builder=lambda user_data_dir: [
            str(trae_cli),
            "-n",
            "--user-data-dir",
            str(user_data_dir),
            str(workspace),
        ],
        clean_existing=learned.get("preferred_strategy", "isolated_cli_launch") == "isolated_cli_launch",
        wait_seconds=12.0,
    )
    payload = {
        "status": "ok",
        "workspace": str(workspace),
        "trae_cli": str(trae_cli),
        "user_data_dir": startup.user_data_dir,
        "user_data_exists": Path(startup.user_data_dir).exists() if startup.user_data_dir else False,
        "process_count": len(startup.launched_process_ids),
        "windows": startup.window_titles,
        "startup": startup.to_dict(),
        "learned_overrides": learned,
        "duration_seconds": startup.diagnostics and 0 or 0,
    }
    payload["profile"] = "trae-open"
    payload = _finalize_payload("trae-open", payload)
    payload["command"] = [str(trae_cli), "-n", "--user-data-dir", startup.user_data_dir or "", str(workspace)]
    payload["returncode"] = 0
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("trae-open", payload)
    cleanup_process_group("Trae")
    return payload


def run_trae_cdp_write_smoke(
    *,
    workspace: Path,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "trae-cdp-write"
    output_dir.mkdir(parents=True, exist_ok=True)

    trae_path = Path(r"C:\Users\33032\AppData\Local\Programs\Trae\Trae.exe")
    def _attempt() -> dict[str, Any]:
        learned = recommended_launch_overrides("trae-cdp-write")
        startup, proc = adaptive_launch_cdp_app(
            app_path=trae_path,
            process_name="Trae",
            process_group="trae_cdp_write",
            output_dir=output_dir,
            startup_args=["-n", str(workspace)],
            isolate_user_data=True,
            allow_attach_existing=learned.get("allow_attach_existing", False),
            clean_existing=learned.get("preferred_strategy", "restart_with_debug_port") == "restart_with_debug_port",
        )
        try:
            script_path = _resource_path("target_cdp_probe.js")
            command = [
                "node",
                str(script_path),
                "--port",
                str(startup.debug_port),
                "--output-dir",
                str(output_dir),
                "--prefer-title-contains",
                "vscode-file://",
                "--mode",
                "write",
                "--write-title",
                "OmniControl Trae Write",
                "--write-marker",
                "ok",
            ]
            result = subprocess.run(command, capture_output=True, text=False, check=False)
            payload = _parse_json_output(result.stdout, result.stderr)
            payload["title"] = payload.get("evaluated_title")
            payload["href"] = payload.get("evaluated_href")
            payload["workspace"] = str(workspace)
            payload["startup"] = startup.to_dict()
            payload["startup"]["learned_overrides"] = learned
            payload["command"] = command
            payload["returncode"] = result.returncode
            return payload
        finally:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            cleanup_process_group("Trae")

    def _plan_trae_write_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            "trae-cdp-write",
            raw_payload=raw_payload,
            output_dir=output_dir,
            workspace=workspace,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            "trae-cdp-write",
            _finalize_payload("trae-cdp-write", dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile="trae-cdp-write",
        preflight=[
            PreflightCheck(
                name="trae_exists",
                run=lambda: path_exists_check("trae_exists", str(trae_path)),
            )
        ],
        primary_attempts=[
            AttemptSpec(name="trae_cdp_write", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_trae_write_pivots,
    )

    payload["profile"] = "trae-cdp-write"
    payload = _finalize_payload("trae-cdp-write", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("trae-cdp-write", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "trae-cdp-write smoke failed"))
    return payload


def run_nx_diagnose_smoke(
    *,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "nx-diagnose"
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = _resource_path("nx_diagnose_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-OutputDir",
        str(output_dir),
    ]

    def _attempt() -> dict[str, Any]:
        result = subprocess.run(command, capture_output=True, text=False, check=False)
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["command"] = command
        payload["returncode"] = result.returncode
        return payload

    def _attempt_env_print(raw_payload: dict[str, Any]) -> dict[str, Any]:
        result = _run_cmd_chain(
            [
                ["call", r"C:\Program Files\Siemens\NX1953\UGII\ugiicmd.bat", r"C:\Program Files\Siemens\NX1953"],
                [r"C:\Program Files\Siemens\NX1953\NXBIN\env_print.exe", "-n"],
            ],
            timeout=30,
        )
        text = _combined_output(result)
        success = result.returncode == 0 and bool(text.strip())
        return _build_sidecar_partial_payload(
            raw_payload=raw_payload,
            success=success,
            action="vendor_shell_env_print",
            entrypoint="ugiicmd.bat + env_print.exe -n",
            output_key="env_print_output",
            output_text=text,
            command=result.args,
            returncode=result.returncode,
            failure_blockers=["env_print did not complete successfully"],
            carry_note="primary NXOpen runtime still blocked",
        )

    def _attempt_lmstat(raw_payload: dict[str, Any]) -> dict[str, Any]:
        license_server = "28000@LocalHost"
        cmd = [
            r"C:\Program Files\Siemens\NX1953\UGFLEXLM\lmutil.exe",
            "lmstat",
            "-c",
            license_server,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
        text = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        success = "Cannot connect to license server system" not in text and result.returncode == 0
        payload = _build_sidecar_partial_payload(
            raw_payload=raw_payload,
            success=success,
            action="vendor_license_probe",
            entrypoint="lmutil lmstat",
            output_key="lmstat_output",
            output_text=text,
            command=cmd,
            returncode=result.returncode,
            failure_blockers=["license port 28000 is not listening"],
            carry_note="primary NXOpen runtime still blocked",
            extra={
                "license_server": license_server,
            },
        )
        payload.update(
            {
            "license_server": license_server,
            }
        )
        return payload

    def _attempt_nxcommand_help(raw_payload: dict[str, Any]) -> dict[str, Any]:
        result = _run_cmd_chain(
            [
                ["call", r"C:\Program Files\Siemens\NX1953\UGII\nxcommand.bat", "-help"],
            ],
            timeout=30,
        )
        text = _combined_output(result)
        success = result.returncode == 0 and "NX " in text
        return _build_sidecar_partial_payload(
            raw_payload=raw_payload,
            success=success,
            action="vendor_command_help",
            entrypoint="nxcommand.bat -help",
            output_key="nxcommand_output",
            output_text=text,
            command=result.args,
            returncode=result.returncode,
            failure_blockers=["nxcommand help did not complete successfully"],
            carry_note="primary NXOpen runtime still blocked",
        )

    def _attempt_display_nx_help(raw_payload: dict[str, Any]) -> dict[str, Any]:
        cmd = [r"C:\Program Files\Siemens\NX1953\NXBIN\display_nx_help.exe", "-help"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
        text = _combined_output(result)
        success = result.returncode == 0 and "usage:" in text.lower()
        return _build_sidecar_partial_payload(
            raw_payload=raw_payload,
            success=success,
            action="vendor_display_help",
            entrypoint="display_nx_help.exe -help",
            output_key="display_help_output",
            output_text=text,
            command=cmd,
            returncode=result.returncode,
            failure_blockers=["display_nx_help did not complete successfully"],
            carry_note="primary NXOpen runtime still blocked",
        )

    def _plan_nx_pivots(raw_payload: dict[str, Any]):
        return build_pivot_attempts_from_actions(
            "nx-diagnose",
            _finalize_payload("nx-diagnose", dict(raw_payload)),
            {
                "switch_to_tooling_plane": lambda: AttemptSpec(
                    name="nxcommand_help",
                    strategy="switch_to_tooling_plane",
                    run=lambda: _attempt_nxcommand_help(raw_payload),
                ),
                "bootstrap_license_tooling": lambda: AttemptSpec(
                    name="nx_lmstat",
                    strategy="bootstrap_license_tooling",
                    run=lambda: _attempt_lmstat(raw_payload),
                ),
                "switch_to_shell_environment": lambda: AttemptSpec(
                    name="nx_env_print",
                    strategy="switch_to_shell_environment",
                    run=lambda: _attempt_env_print(raw_payload),
                ),
                "switch_to_secondary_entrypoint": lambda: AttemptSpec(
                    name="nx_display_help",
                    strategy="switch_to_secondary_entrypoint",
                    run=lambda: _attempt_display_nx_help(raw_payload),
                ),
            },
        )

    payload = run_with_strategy_pivots(
        profile="nx-diagnose",
        preflight=[
            PreflightCheck(
                name="run_journal_exists",
                run=lambda: path_exists_check(
                    "run_journal_exists",
                    r"C:\Program Files\Siemens\NX1953\NXBIN\run_journal.exe",
                ),
            )
        ],
        primary_attempts=[
            AttemptSpec(name="nx_diagnose_script", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_nx_pivots,
    )

    payload["profile"] = "nx-diagnose"
    payload = _finalize_payload("nx-diagnose", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("nx-diagnose", payload)
    return payload


def run_isight_diagnose_smoke(
    *,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "isight-diagnose"
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = _resource_path("isight_diagnose_smoke.ps1")

    def _attempt(profile_value: str | None = None) -> dict[str, Any]:
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-OutputDir",
            str(output_dir),
        ]
        if profile_value:
            command.extend(["-ProfileValue", profile_value])
        result = subprocess.run(command, capture_output=True, text=False, check=False)
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["command"] = command
        payload["returncode"] = result.returncode
        return payload

    def _attempt_station(profile_value: str, raw_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = _run_cmd_chain(
            [
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\station.bat", f"profile:{profile_value}", "-nogui"],
            ],
            timeout=60,
        )
        text = _combined_output(result)
        success = "Exception" not in text and result.returncode == 0
        payload = {
            "status": "partial" if success else "blocked",
            "station_output": text[:4000],
            "command": result.args,
            "returncode": result.returncode,
        }
        if success:
            if raw_payload is not None:
                payload["blockers"] = _carry_forward_blockers(raw_payload, "primary Isight runtime still blocked")
        else:
            payload["blockers"] = ["station standalone failed"]
        return payload

    def _attempt_fiperenv(profile_value: str, raw_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = _run_cmd_chain(
            [
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\fiperenv.bat"],
                [
                    "call",
                    r"C:\SIMULIA\Isight\2021\win_b64\code\command\fipercmd.bat",
                    "contents",
                    r"file:C:\SIMULIA\Isight\2021\win_b64\examples\models\applications\I_Beam\I_Beam.zmf",
                    f"profile:{profile_value}",
                    "logonprompt:no",
                    "-nogui",
                ],
            ],
            timeout=120,
        )
        text = _combined_output(result)
        success = "Creating contents summary" in text and "ERROR:" not in text and result.returncode == 0
        payload = {
            "status": "partial" if success else "blocked",
            "fiperenv_output": text[:4000],
            "command": result.args,
            "returncode": result.returncode,
        }
        blockers: list[str] = []
        if "connection profile is required" in text:
            blockers.append("connection profile is required")
        if "Error restoring variable collection" in text:
            blockers.append("variable collection restore failed")
        if success and raw_payload is not None:
            payload["blockers"] = _carry_forward_blockers(raw_payload, "primary Isight runtime still blocked")
            return payload
        if not blockers and payload["status"] != "partial":
            blockers.append("shell environment pivot did not resolve Isight startup")
        if blockers:
            payload["blockers"] = blockers
        return payload

    def _attempt_fipercmd_help(raw_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = _run_cmd_chain(
            [
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\fiperenv.bat"],
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\fipercmd.bat", "help"],
            ],
            timeout=120,
        )
        text = _combined_output(result)
        command_surface_available = "Commands" in text and "contents" in text and "jobstatus" in text
        payload = _build_sidecar_partial_payload(
            raw_payload=raw_payload,
            success=command_surface_available,
            action="fipercmd_help_surface",
            entrypoint="fiperenv.bat + fipercmd.bat help",
            output_key="command_surface_output",
            output_text=text,
            command=result.args,
            returncode=result.returncode,
            failure_blockers=["command surface help did not return expected output"],
            carry_note="primary Isight runtime still blocked",
            extra={
                "command_surface_available": command_surface_available,
            },
        )
        return payload

    def _attempt_isight_tooling_plane(raw_payload: dict[str, Any]) -> dict[str, Any]:
        env_result = _run_cmd_chain(
            [
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\fiperenv.bat"],
                ["set", "FIPER"],
            ],
            timeout=60,
        )
        env_text = _combined_output(env_result)
        lic_result = _run_cmd_chain(
            [
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\licusage.bat", "-h"],
            ],
            timeout=60,
        )
        lic_text = _combined_output(lic_result)
        help_result = _run_cmd_chain(
            [
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\fiperenv.bat"],
                ["call", r"C:\SIMULIA\Isight\2021\win_b64\code\command\fipercmd.bat", "help", "contents", "profile:standalone", "-nogui"],
            ],
            timeout=60,
        )
        help_text = _combined_output(help_result)

        fiper_home = _extract_env_assignment(env_text, "FIPER_HOME")
        fiper_conf = _extract_env_assignment(env_text, "FIPER_CONF")
        env_ok = bool(fiper_home and fiper_conf)
        lic_ok = "Usage:" in lic_text and "licusage.py" in lic_text
        help_ok = "contents: Gives a contents summary" in help_text
        success = env_ok and lic_ok and help_ok

        payload = {
            "status": "partial" if success else "blocked",
            "secondary_action": "vendor_tooling_plane",
            "secondary_action_ok": success,
            "tooling_verified": success,
            "tooling_entrypoint": "fiperenv.bat + licusage.bat -h + fipercmd.bat help contents",
            "fiper_home": fiper_home,
            "fiper_conf": fiper_conf,
            "licusage_help_ok": lic_ok,
            "contents_help_ok": help_ok,
            "fiperenv_output": env_text[:4000],
            "licusage_output": lic_text[:4000],
            "contents_help_output": help_text[:4000],
            "command": [env_result.args, lic_result.args, help_result.args],
            "returncode": max(env_result.returncode, lic_result.returncode, help_result.returncode),
        }
        if success:
            payload["blockers"] = _carry_forward_blockers(raw_payload, "primary Isight runtime still blocked")
        else:
            blockers: list[str] = []
            if not env_ok:
                blockers.append("tooling environment bootstrap failed")
            if not lic_ok:
                blockers.append("license tooling did not respond as expected")
            if not help_ok:
                blockers.append("tooling contents help did not respond as expected")
            payload["blockers"] = blockers
        return payload

    def _plan_isight_remediation(raw_payload: dict[str, Any]) -> list[AttemptSpec]:
        action_map = {
            "supply_profile_standalone_cpr": lambda: AttemptSpec(
                name="isight_standalone_cpr",
                strategy="supply_profile",
                run=lambda: _attempt(r"C:\SIMULIA\Isight\2021\config\standalone.cpr"),
            ),
            "supply_profile_standalone_name": lambda: AttemptSpec(
                name="isight_standalone_name",
                strategy="supply_profile",
                run=lambda: _attempt("standalone"),
            ),
            "start_station_standalone": lambda: AttemptSpec(
                name="isight_station_standalone",
                strategy="supply_profile",
                run=lambda: _attempt_station("standalone"),
            ),
        }
        return build_attempts_from_actions("isight-diagnose", _finalize_payload("isight-diagnose", dict(raw_payload)), action_map)

    def _plan_isight_pivots(raw_payload: dict[str, Any]):
        return build_pivot_attempts_from_actions(
            "isight-diagnose",
            _finalize_payload("isight-diagnose", dict(raw_payload)),
            {
                "switch_to_tooling_plane": lambda: AttemptSpec(
                    name="isight_tooling_plane",
                    strategy="switch_to_tooling_plane",
                    run=lambda: _attempt_isight_tooling_plane(raw_payload),
                ),
                "switch_to_shell_environment": lambda: AttemptSpec(
                    name="isight_fiperenv_standalone",
                    strategy="switch_to_shell_environment",
                    run=lambda: _attempt_fiperenv("standalone", raw_payload),
                ),
                "switch_to_secondary_service": lambda: AttemptSpec(
                    name="isight_station_standalone",
                    strategy="switch_to_secondary_service",
                    run=lambda: _attempt_station("standalone", raw_payload),
                ),
                "switch_to_secondary_entrypoint": lambda: AttemptSpec(
                    name="isight_fipercmd_help",
                    strategy="switch_to_secondary_entrypoint",
                    run=lambda: _attempt_fipercmd_help(raw_payload),
                ),
            },
        )

    payload = run_with_strategy_pivots(
        profile="isight-diagnose",
        preflight=[
            PreflightCheck(
                name="fipercmd_exists",
                run=lambda: path_exists_check(
                    "fipercmd_exists",
                    r"C:\SIMULIA\Isight\2021\win_b64\code\command\fipercmd.bat",
                ),
            )
        ],
        primary_attempts=[
            AttemptSpec(name="isight_default", strategy="direct_script", run=lambda: _attempt(None)),
            *_plan_isight_remediation({"status": "blocked", "blockers": ["connection profile is required", "DSLS port 4085 is not listening"]}),
        ],
        pivot_builder=_plan_isight_pivots,
    )

    payload["profile"] = "isight-diagnose"
    payload = _finalize_payload("isight-diagnose", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("isight-diagnose", payload)
    return payload


def run_ue_diagnose_smoke(
    *,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "ue-diagnose"
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = _resource_path("ue_diagnose_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-OutputDir",
        str(output_dir),
    ]

    def _attempt_editor() -> dict[str, Any]:
        result = subprocess.run(command, capture_output=True, text=False, check=False)
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["command"] = command
        payload["returncode"] = result.returncode
        return payload

    def _attempt_buildpatch(raw_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        buildpatch = Path(r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\BuildPatchTool.exe")
        command2 = [str(buildpatch), "-help"]
        result = subprocess.run(command2, capture_output=True, text=True, check=False, timeout=30)
        text = (result.stdout or "") + (result.stderr or "")
        return _build_sidecar_partial_payload(
            raw_payload=raw_payload,
            success="Supported modes" in text,
            action="vendor_tooling_plane",
            entrypoint="BuildPatchTool.exe -help",
            output_key="build_patch_help",
            output_text=text.strip(),
            command=command2,
            returncode=result.returncode,
            failure_blockers=["BuildPatchTool did not return expected help output"],
            carry_note="primary UE editor path still blocked",
        )

    def _attempt_editor_cmd(raw_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        editor_cmd = Path(r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
        project = Path(r"C:\Users\33032\Documents\Unreal Projects\我的项目\我的项目.uproject")
        command2 = [
            str(editor_cmd),
            str(project),
            "-Unattended",
            "-NoSplash",
            "-NullRHI",
            "-stdout",
            "-FullStdOutLogOutput",
            "-ExecCmds=QUIT_EDITOR",
        ]
        result = subprocess.run(command2, capture_output=True, text=True, check=False, timeout=60)
        text = (result.stdout or "") + (result.stderr or "")
        return _build_sidecar_partial_payload(
            raw_payload=raw_payload,
            success="Running engine for game" in text,
            action="secondary_engine_entrypoint",
            entrypoint="UnrealEditor-Cmd.exe <project> -ExecCmds=QUIT_EDITOR",
            output_key="editor_cmd_output",
            output_text=text[:8000],
            command=command2,
            returncode=result.returncode,
            failure_blockers=["Editor-Cmd did not reach game startup"],
            carry_note="primary UE editor path still blocked",
        )

    def _plan_ue_pivots(raw_payload: dict[str, Any]):
        return build_pivot_attempts_from_actions(
            "ue-diagnose",
            _finalize_payload("ue-diagnose", dict(raw_payload)),
            {
                "switch_to_tooling_plane": lambda: AttemptSpec(
                    name="ue_buildpatch_help",
                    strategy="switch_to_tooling_plane",
                    run=lambda: _attempt_buildpatch(raw_payload),
                ),
                "switch_to_secondary_entrypoint": lambda: AttemptSpec(
                    name="ue_editor_cmd_project",
                    strategy="switch_to_secondary_entrypoint",
                    run=lambda: _attempt_editor_cmd(raw_payload),
                ),
            },
        )

    payload = run_with_strategy_pivots(
        profile="ue-diagnose",
        preflight=[
            PreflightCheck(
                name="unreal_editor_exists",
                run=lambda: path_exists_check(
                    "unreal_editor_exists",
                    r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe",
                ),
            )
        ],
        primary_attempts=[
            AttemptSpec(name="ue_editor_help", strategy="direct_script", run=_attempt_editor),
        ],
        pivot_builder=_plan_ue_pivots,
    )

    payload["profile"] = "ue-diagnose"
    payload = _finalize_payload("ue-diagnose", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("ue-diagnose", payload)
    return payload


def run_ue_python_write_smoke(
    *,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "ue-python-write"
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = _resource_path("ue_python_write_smoke.ps1")
    output_file = output_dir / "ue_python_write.txt"
    python_payload = (
        "import pathlib; "
        f"pathlib.Path(r'{str(output_file).replace(chr(92), '/')}').write_text("
        "'ok from ue inline', encoding='utf-8')"
    )
    script_payload = prepare_script_payload(
        python_payload,
        output_dir,
        stem="ue_write_payload",
        suffix=".py",
        prefer_file=True,
    )
    project_info = ensure_ascii_staging(
        Path(r"C:\Users\33032\Documents\Unreal Projects\我的项目\我的项目.uproject"),
        output_dir / "staging",
        staged_name="ue_project",
    )

    def _attempt(project_path: str | None, name: str) -> AttemptSpec:
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-OutputDir",
            str(output_dir),
        ]
        command.extend(["-ScriptPath", script_payload.value])
        if project_path:
            command.extend(["-ProjectPath", project_path])

        def _run() -> dict[str, Any]:
            result = subprocess.run(command, capture_output=True, text=False, check=False)
            payload = _parse_json_output(result.stdout, result.stderr)
            if project_path:
                payload["staging"] = project_info.to_dict()
            payload["script_payload"] = script_payload.to_dict()
            payload["command"] = command
            payload["returncode"] = result.returncode
            return payload

        return AttemptSpec(name=name, strategy="direct_script" if project_path else "drop_project_context", run=_run)

    def _plan_ue_write_pivots(raw_payload: dict[str, Any]):
        action_map = {
            "drop_project_context": lambda: _attempt(None, "ue_python_write_engine"),
        }
        action_map.update(
            _metadata_secondary_profile_action_map(
                "ue-python-write",
                raw_payload=raw_payload,
                output_dir=output_dir,
                profile_chain=_profile_chain,
            )
        )
        return build_pivot_attempts_from_actions(
            "ue-python-write",
            _finalize_payload("ue-python-write", dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile="ue-python-write",
        preflight=[
            PreflightCheck(
                name="unreal_editor_cmd_exists",
                run=lambda: path_exists_check(
                    "unreal_editor_cmd_exists",
                    r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
                ),
            )
        ],
        primary_attempts=[
            _attempt(project_info.staged_path, "ue_python_write_project"),
        ],
        pivot_builder=_plan_ue_write_pivots,
    )

    payload["profile"] = "ue-python-write"
    payload = _finalize_payload("ue-python-write", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("ue-python-write", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "ue-python-write smoke failed"))
    return payload


def run_cadviewer_view_smoke(
    *,
    source: Path,
    output_dir: Path | None,
    app_path: Path,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(f"Source CAD file not found: {source}")
    if not app_path.exists():
        raise FileNotFoundError(f"CadViewer app not found: {app_path}")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "cadv-view"
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = _resource_path("cadv_view_smoke.ps1")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-SourceCad",
        str(source),
        "-CadViewerPath",
        str(app_path),
        "-OutputDir",
        str(output_dir),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=False,
        check=False,
    )
    payload = _parse_json_output(result.stdout, result.stderr)
    payload["profile"] = "cadv-view"
    payload = _finalize_payload("cadv-view", payload)
    payload["command"] = command
    payload["returncode"] = result.returncode
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("cadv-view", payload)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "cadv-view smoke failed"))
    return payload


def run_selfdraw_write_smoke(
    *,
    profile: str,
    executable_path: Path,
    source: Path,
    window_class: str,
    input_sequence: str,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / profile
    output_dir.mkdir(parents=True, exist_ok=True)
    def _attempt() -> dict[str, Any]:
        script_path = _resource_path("selfdraw_write_probe.ps1")
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-ExecutablePath",
            str(executable_path),
            "-SourceArg",
            str(source),
            "-WindowClass",
            window_class,
            "-InputSequence",
            input_sequence,
            "-OutputDir",
            str(output_dir),
        ]
        result = subprocess.run(command, capture_output=True, text=False, check=False)
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["page_advanced"] = payload.get("visual_changed")
        payload["command"] = command
        payload["returncode"] = result.returncode
        return payload

    def _plan_selfdraw_write_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            profile,
            raw_payload=raw_payload,
            output_dir=output_dir,
            source=source,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            profile,
            _finalize_payload(profile, dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile=profile,
        preflight=[
            PreflightCheck(
                name=f"{profile}_source_exists",
                run=lambda: path_exists_check(f"{profile}_source_exists", str(source)),
            ),
            PreflightCheck(
                name=f"{profile}_app_exists",
                run=lambda: path_exists_check(f"{profile}_app_exists", str(executable_path)),
            ),
        ],
        primary_attempts=[
            AttemptSpec(name=f"{profile}_write", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_selfdraw_write_pivots,
    )
    payload["profile"] = profile
    payload = _finalize_payload(profile, payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload(profile, payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", f"{profile} smoke failed"))
    return payload


def run_selfdraw_workflow_smoke(
    *,
    profile: str,
    executable_path: Path,
    source: Path,
    window_class: str,
    workflow: dict[str, Any],
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / profile
    output_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = output_dir / "workflow.json"
    workflow_path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")
    def _attempt() -> dict[str, Any]:
        script_path = _resource_path("selfdraw_workflow_probe.ps1")
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-ExecutablePath",
            str(executable_path),
            "-SourceArg",
            str(source),
            "-WindowClass",
            window_class,
            "-WorkflowPath",
            str(workflow_path),
            "-OutputDir",
            str(output_dir),
        ]
        result = subprocess.run(command, capture_output=True, text=False, check=False)
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["command"] = command
        payload["returncode"] = result.returncode
        return payload

    def _plan_selfdraw_workflow_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            profile,
            raw_payload=raw_payload,
            output_dir=output_dir,
            source=source,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            profile,
            _finalize_payload(profile, dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile=profile,
        preflight=[
            PreflightCheck(
                name=f"{profile}_source_exists",
                run=lambda: path_exists_check(f"{profile}_source_exists", str(source)),
            ),
            PreflightCheck(
                name=f"{profile}_app_exists",
                run=lambda: path_exists_check(f"{profile}_app_exists", str(executable_path)),
            ),
        ],
        primary_attempts=[
            AttemptSpec(name=f"{profile}_workflow", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_selfdraw_workflow_pivots,
    )
    payload["profile"] = profile
    payload = _finalize_payload(profile, payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload(profile, payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", f"{profile} smoke failed"))
    return payload


def run_cdp_workflow_smoke(
    *,
    profile: str,
    app_path: Path,
    process_name: str,
    output_dir: Path | None,
    startup_args: list[str],
    isolate_user_data: bool,
    allow_attach_existing: bool,
    clean_existing: bool,
    prefer_title_contains: str,
    workflow: dict[str, Any],
    workspace: Path | None = None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / profile
    output_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = output_dir / "workflow.json"
    workflow_path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")

    def _attempt() -> dict[str, Any]:
        startup, proc = adaptive_launch_cdp_app(
            app_path=app_path,
            process_name=process_name,
            process_group=profile.replace("-", "_"),
            output_dir=output_dir,
            startup_args=startup_args,
            isolate_user_data=isolate_user_data,
            allow_attach_existing=allow_attach_existing,
            clean_existing=clean_existing,
        )
        try:
            script_path = _resource_path("cdp_workflow_probe.js")
            command = [
                "node",
                str(script_path),
                "--port",
                str(startup.debug_port),
                "--output-dir",
                str(output_dir),
                "--workflow-path",
                str(workflow_path),
                "--prefer-title-contains",
                prefer_title_contains,
            ]
            result = subprocess.run(command, capture_output=True, text=False, check=False)
            payload = _parse_json_output(result.stdout, result.stderr)
            payload["startup"] = startup.to_dict()
            payload["command"] = command
            payload["returncode"] = result.returncode
            return payload
        finally:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            cleanup_process_group(process_name)

    def _plan_workflow_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            profile,
            raw_payload=raw_payload,
            output_dir=output_dir,
            workspace=workspace,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            profile,
            _finalize_payload(profile, dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile=profile,
        preflight=[
            PreflightCheck(
                name=f"{profile}_app_exists",
                run=lambda: path_exists_check(f"{profile}_app_exists", str(app_path)),
            )
        ],
        primary_attempts=[
            AttemptSpec(name=f"{profile}_workflow", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_workflow_pivots,
    )

    payload["profile"] = profile
    payload = _finalize_payload(profile, payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload(profile, payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", f"{profile} smoke failed"))
    return payload


def _metadata_secondary_profile_action_map(
    primary_profile: str,
    *,
    raw_payload: dict[str, Any],
    output_dir: Path,
    source: Path | None = None,
    workspace: Path | None = None,
    query: str | None = None,
    url: str | None = None,
    profile_chain: tuple[str, ...] = (),
) -> dict[str, Callable[[], AttemptSpec | None]]:
    specs = secondary_profile_specs(primary_profile)
    action_map: dict[str, Callable[[], AttemptSpec | None]] = {}
    for spec in specs:
        action = str(spec.get("action", "")).strip()
        if not action:
            continue

        def _factory(spec: dict[str, Any] = spec, action: str = action) -> AttemptSpec | None:
            secondary_profile = str(spec.get("profile", "")).strip()
            if not secondary_profile or secondary_profile == primary_profile:
                return None
            if is_url_substitution_candidate(
                primary_profile=primary_profile,
                secondary_profile=secondary_profile,
                source_arg=str(spec.get("source_arg") or "") or None,
            ):
                return None
            invocation_kwargs = _secondary_profile_invocation_kwargs(
                spec,
                source=source,
                workspace=workspace,
                query=query,
                url=url,
            )
            required_source = spec.get("source_arg")
            if required_source in {"source", "workspace", "query", "url"} and not invocation_kwargs:
                return None
            attempt_name = str(spec.get("attempt_name") or f"{secondary_profile}_sidecar")
            strategy = str(spec.get("strategy") or action)
            secondary_output_dir = output_dir / "sidecars" / secondary_profile
            return AttemptSpec(
                name=attempt_name,
                strategy=strategy,
                run=lambda: _run_secondary_profile_sidecar(
                    primary_profile=primary_profile,
                    secondary_profile=secondary_profile,
                    action=action,
                    raw_payload=raw_payload,
                    invocation_kwargs=invocation_kwargs,
                    output_dir=secondary_output_dir,
                    carry_note=spec.get("carry_note"),
                    profile_chain=profile_chain,
                ),
            )

        action_map[action] = _factory
    return action_map


def _secondary_profile_invocation_kwargs(
    spec: dict[str, Any],
    *,
    source: Path | None = None,
    workspace: Path | None = None,
    query: str | None = None,
    url: str | None = None,
) -> dict[str, str]:
    source_arg = spec.get("source_arg")
    if source_arg == "source":
        return {"source": str(source)} if source is not None else {}
    if source_arg == "workspace":
        return {"source": str(workspace)} if workspace is not None else {}
    if source_arg == "query":
        return {"query": query} if query is not None else {}
    if source_arg == "url":
        return {"url": url} if url is not None else {}
    return {}


def _run_secondary_profile_sidecar(
    *,
    primary_profile: str,
    secondary_profile: str,
    action: str,
    raw_payload: dict[str, Any],
    invocation_kwargs: dict[str, str],
    output_dir: Path,
    carry_note: str | None,
    profile_chain: tuple[str, ...],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_mode = "directory" if action else "directory"
    specs = [spec for spec in secondary_profile_specs(primary_profile) if spec.get("profile") == secondary_profile and spec.get("action") == action]
    if specs:
        output_mode = str(specs[0].get("output_mode", "directory"))
    try:
        smoke_kwargs: dict[str, Any] = {
            "_profile_chain": profile_chain,
            **invocation_kwargs,
        }
        if output_mode == "directory":
            smoke_kwargs["output"] = str(output_dir)
        secondary_payload = run_smoke(secondary_profile, **smoke_kwargs)
    except Exception as error:
        return {
            "status": "blocked",
            "secondary_action": "related_profile_control_plane",
            "secondary_action_ok": False,
            "secondary_profile": secondary_profile,
            "secondary_profile_action": action,
            "tooling_verified": False,
            "tooling_entrypoint": f"profile:{secondary_profile}",
            "blockers": [str(error)],
            "error": str(error),
            "command": ["omnicontrol-smoke", secondary_profile],
            "returncode": 1,
        }

    success = secondary_payload.get("status") in {"ok", "partial"}
    payload: dict[str, Any] = {
        "status": "partial" if success else "blocked",
        "secondary_action": "related_profile_control_plane",
        "secondary_action_ok": success,
        "secondary_profile": secondary_profile,
        "secondary_profile_action": action,
        "secondary_profile_status": secondary_payload.get("status"),
        "secondary_profile_blockers": list(secondary_payload.get("blockers", [])),
        "secondary_profile_report_path": secondary_payload.get("report_path"),
        "secondary_profile_selected_attempt": secondary_payload.get("orchestration", {}).get("selected_attempt"),
        "secondary_profile_strategy": secondary_payload.get("strategy"),
        "tooling_verified": success,
        "tooling_entrypoint": f"profile:{secondary_profile}",
        "command": ["omnicontrol-smoke", secondary_profile],
        "returncode": secondary_payload.get("returncode", 0 if success else 1),
    }
    if secondary_payload.get("error"):
        payload["error"] = secondary_payload["error"]

    if success:
        payload["blockers"] = sorted(
            {
                *_carry_forward_blockers(raw_payload, carry_note),
                *secondary_payload.get("blockers", []),
            }
        )
        return payload

    blockers = sorted(
        {
            *secondary_payload.get("blockers", []),
            *([str(secondary_payload["error"])] if secondary_payload.get("error") else []),
        }
    )
    payload["blockers"] = blockers or [f"{secondary_profile} did not verify a usable secondary control plane"]
    return payload


def _resource_path(name: str) -> Path:
    return Path(resources.files("omnicontrol.runtime").joinpath("scripts", name))


def _run_osascript_profile(script_name: str, *, args: list[str]) -> dict[str, Any]:
    script_path = _resource_path(script_name)
    command = ["osascript", str(script_path), *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    payload = _parse_json_output(result.stdout, result.stderr)
    payload["command"] = command
    payload["returncode"] = result.returncode
    return payload


def _require_macos(profile: str) -> None:
    if current_platform() != "macos":
        raise RuntimeError(f"{profile} requires macOS.")


def _parse_json_output(stdout: str | bytes, stderr: str | bytes) -> dict:
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    text = stdout.strip()
    if not text:
        return {"status": "error", "error": stderr.strip() or "No output from smoke script."}
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        return {
            "status": "error",
            "error": f"Invalid JSON output: {error}",
            "stdout": stdout,
            "stderr": stderr,
        }


def _decode_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return value.strip()


def _run_cmd_chain(
    commands: list[list[str | Path]],
    *,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    command_text = " && ".join(_cmd_fragment(command) for command in commands if command)
    script_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".cmd",
            prefix="omnicontrol-chain-",
            delete=False,
        ) as handle:
            script_path = Path(handle.name)
            handle.write("@echo off\n")
            handle.write(command_text)
            handle.write("\n")
        result = subprocess.run(
            ["cmd", "/Q", "/C", str(script_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        result.args = command_text
        return result
    finally:
        if script_path is not None:
            script_path.unlink(missing_ok=True)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return ((result.stdout or "") + "\n" + (result.stderr or "")).strip()


def _cmd_fragment(command: list[str | Path]) -> str:
    parts = [str(part) for part in command]
    if not parts:
        return ""
    if parts[0].lower() == "call":
        return "call " + subprocess.list2cmdline(parts[1:])
    return subprocess.list2cmdline(parts)


def _carry_forward_blockers(raw_payload: dict[str, Any], note: str | None = None) -> list[str]:
    blockers = list(raw_payload.get("blockers", []))
    if note:
        blockers.append(note)
    return sorted({item for item in blockers if item})


def _build_sidecar_partial_payload(
    *,
    raw_payload: dict[str, Any] | None,
    success: bool,
    action: str,
    entrypoint: str,
    output_key: str,
    output_text: str,
    command: Any,
    returncode: int,
    failure_blockers: list[str],
    carry_note: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "partial" if success else "blocked",
        "secondary_action": action,
        "secondary_action_ok": success,
        "tooling_verified": success,
        "tooling_entrypoint": entrypoint,
        output_key: output_text[:4000],
        "command": command,
        "returncode": returncode,
    }
    if extra:
        payload.update(extra)
    if success:
        if raw_payload is not None:
            payload["blockers"] = _carry_forward_blockers(raw_payload, carry_note)
    else:
        payload["blockers"] = failure_blockers
    return payload


def _qqmusic_http_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Referer": "https://y.qq.com/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _qqmusic_search_candidates(query: str) -> list[dict[str, Any]]:
    url = (
        "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg"
        f"?format=json&key={quote(query)}"
    )
    payload = _qqmusic_http_json(url)
    return list(payload.get("data", {}).get("song", {}).get("itemlist", []))


def _qqmusic_select_candidate(query: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        raise RuntimeError(f"QQMusic smartbox returned no song candidates for query: {query}")

    tokens = [token for token in re.split(r"\s+", query.strip()) if token]

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        title = str(item.get("name", ""))
        singer = str(item.get("singer", ""))
        exact_title = 1 if any(token == title for token in tokens) else 0
        exact_singer = 1 if any(token == singer for token in tokens) else 0
        contains_hits = sum(1 for token in tokens if token and (token in title or token in singer))
        return (exact_title + exact_singer, contains_hits, -int(item.get("id", 0)))

    return max(items, key=score)


def _qqmusic_fetch_song_detail(song_id: int) -> dict[str, Any]:
    url = (
        "https://u.y.qq.com/cgi-bin/musicu.fcg?format=json&data="
        f"{quote(json.dumps({'comm': {'ct': 24, 'cv': 0}, 'songinfo': {'method': 'get_song_detail_yqq', 'module': 'music.pf_song_detail_svr', 'param': {'song_id': song_id}}}, ensure_ascii=False), safe='')}"
    )
    payload = _qqmusic_http_json(url)
    return dict(payload.get("songinfo", {}).get("data", {}))


def _qqmusic_fetch_legacy_play_command_xml(song_id: int) -> str | None:
    url = f"https://jump.qq.com/qqmusic_4?musicid={song_id}&ishide=1&from=portal"
    request = Request(
        url,
        headers={
            "Referer": "https://y.qq.com/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urlopen(request, timeout=20) as response:
        text = response.read().decode("utf-8", errors="ignore")
    match = re.search(
        r"<!--\s*(<command-lable-xwl78-qq-music>.*?</command-lable-xwl78-qq-music>)\s*-->",
        text,
        re.S,
    )
    return match.group(1).strip() if match else None


def _qqmusic_song_detail_url(song_mid: str) -> str:
    if not song_mid:
        return "https://y.qq.com/"
    return f"https://y.qq.com/n/ryqq/songDetail/{song_mid}"


def _qqmusic_build_songinfo_payload(track_info: dict[str, Any], *, source: str) -> dict[str, Any]:
    file_info = dict(track_info.get("file", {}))
    media_mid = str(file_info.get("media_mid", ""))
    filename = f"C400{media_mid}.m4a" if media_mid else ""
    fallback_url = f"https://dl.stream.qqmusic.qq.com/{filename}" if filename else ""
    url = str(file_info.get("url") or fallback_url)
    return {
        "id": track_info["id"],
        "type": track_info.get("type", 0),
        "subtype": 5,
        "mid": track_info["mid"],
        "name": track_info.get("name") or track_info.get("title") or "",
        "title": track_info.get("title") or track_info.get("name") or "",
        "interval": track_info.get("interval", 0),
        "isonly": track_info.get("isonly", 0),
        "language": track_info.get("language", 0),
        "genre": track_info.get("genre", 0),
        "index_cd": track_info.get("index_cd", 0),
        "index_album": track_info.get("index_album", 0),
        "status": track_info.get("index_album") or 31,
        "fnote": track_info.get("fnote", 0),
        "time_public": track_info.get("time_public", ""),
        "url": url,
        "singer": [
            {
                "id": singer.get("id", 0),
                "mid": singer.get("mid", ""),
                "name": "",
                "title": singer.get("title") or singer.get("name") or "",
            }
            for singer in track_info.get("singer", [])
        ],
        "album": dict(track_info.get("album", {})),
        "mv": dict(track_info.get("mv", {})),
        "ksong": dict(track_info.get("ksong", {})),
        "file": {
            **file_info,
            "url": url,
            "size_ogg": file_info.get("size_192ogg", 0),
            "size_128": file_info.get("size_128mp3", 0),
            "size_320": file_info.get("size_320mp3", 0),
            "size_ape": file_info.get("size_ape", 0),
            "size_flac": file_info.get("size_flac", 0),
            "size_dts": file_info.get("size_dts", 0),
        },
        "volume": dict(track_info.get("volume", {"gain": 0, "peak": 0, "lra": 0})),
        "pay": {
            "pay_month": track_info.get("pay", {}).get("pay_month", 0),
            "price_track": track_info.get("pay", {}).get("price_track", 0),
            "price_album": track_info.get("pay", {}).get("price_album", 0),
            "pay_play": track_info.get("pay", {}).get("pay_play", 0),
            "pay_down": track_info.get("pay", {}).get("pay_down", 0),
            "time_free": track_info.get("pay", {}).get("time_free", 0),
            "pay_status": track_info.get("pay", {}).get("pay_status", 0),
        },
        "action": {
            "switch": track_info.get("action", {}).get("switch", 0),
            "msgid": track_info.get("action", {}).get("msgid", 0),
            "alert": track_info.get("action", {}).get("alert", 0),
        },
        "source": source,
        "trace": track_info.get("trace", ""),
    }


def _qqmusic_build_play_command_xml(
    track_info: dict[str, Any],
    *,
    source: str = "2:1001:",
    target_url: str | None = None,
) -> str:
    if target_url is None:
        target_url = _qqmusic_song_detail_url(str(track_info.get("mid", "")))
    songinfo = _qqmusic_build_songinfo_payload(track_info, source=source)
    songinfo_json = json.dumps([songinfo], ensure_ascii=False, separators=(",", ":"))
    return (
        '<command-lable-xwl78-qq-music>'
        '<cmd value="1002" verson="3">'
        '<qq uin="0"/>'
        "<playindex>0</playindex>"
        "<clearlast>1</clearlast>"
        "<listname><![CDATA[]]></listname>"
        "<listkey></listkey>"
        "<bsingle>1</bsingle>"
        "<webview>3</webview>"
        f"<targeturl>{target_url}</targeturl>"
        "<music>"
        f"<songinfo><![CDATA[{songinfo_json}]]></songinfo>"
        "</music>"
        '<adddepottag depot="0"/><addplaylisttag playlist="0"/>'
        "<cat>-1</cat>"
        "<insertbefore>-2</insertbefore>"
        "</cmd>"
        '<cmd value="1008"><isshow>0</isshow></cmd>'
        "</command-lable-xwl78-qq-music>"
    )


QQMUSIC_PRIVATE_PROTOCOL_WINDOW_CLASS = "csQQMusicComApiWnd2017"
QQMUSIC_PROTECTED_WINDOW_CLASSES = (
    QQMUSIC_PRIVATE_PROTOCOL_WINDOW_CLASS,
    "QQMusic_Daemon_Wnd",
)
QQMUSIC_REPAIR_WINDOW_TOKENS = ("\u53cd\u9988", "\u4fee\u590d")
QQMUSIC_TRANSPORT_DESCRIPTORS: tuple[TransportDescriptor, ...] = (
    TransportDescriptor(
        name="legacy_jump_xml_runtime_auth",
        control_plane="vendor_command",
        software_native=True,
        background_safe=True,
        requires_focus=False,
        startup_cost=0,
        probe_cost=1,
        determinism=4,
        observability=4,
        side_effect_risk=1,
    ),
    TransportDescriptor(
        name="tencent_protocol",
        control_plane="vendor_command",
        software_native=True,
        background_safe=True,
        requires_focus=False,
        startup_cost=0,
        probe_cost=0,
        determinism=4,
        observability=4,
        side_effect_risk=1,
    ),
    TransportDescriptor(
        name="private_protocol",
        control_plane="private_protocol",
        software_native=True,
        background_safe=True,
        requires_focus=False,
        startup_cost=1,
        probe_cost=1,
        determinism=4,
        observability=4,
        side_effect_risk=1,
    ),
    TransportDescriptor(
        name="legacy_jump_xml",
        control_plane="vendor_command",
        software_native=True,
        background_safe=True,
        requires_focus=False,
        startup_cost=1,
        probe_cost=1,
        determinism=3,
        observability=3,
        side_effect_risk=1,
    ),
    TransportDescriptor(
        name="new_play",
        control_plane="vendor_command",
        software_native=False,
        background_safe=False,
        requires_focus=True,
        startup_cost=1,
        probe_cost=2,
        determinism=2,
        observability=2,
        side_effect_risk=5,
    ),
)
QQMUSIC_VENDOR_COMMAND_METHODS: tuple[tuple[str, int], ...] = (
    ("WebExecCommand2", 4),
    ("WebExecCommand", 4),
    ("ExecuteCommand", 4),
)
QQMUSIC_CONTROL_PROPERTY_NAMES: tuple[str, ...] = (
    "QQMusicControlProperty_dwVersion",
    "QQMusicControlProperty_dwQQUin",
    "QQMusicControlProperty_strKey",
    "QQMusicControlProperty_strPlatformKey",
    "QQMusicControlProperty_nLoginType",
)


def _qqmusic_process_windows(*, visible_only: bool | None = None) -> list[TopLevelWindowInfo]:
    process_ids = find_process_ids("QQMusic.exe")
    if not process_ids:
        return []
    return list_top_level_windows(process_ids=process_ids, visible_only=visible_only)


def _qqmusic_select_main_window(windows: list[TopLevelWindowInfo]) -> TopLevelWindowInfo | None:
    for window in windows:
        if window.visible and window.class_name == "TXGuiFoundation" and window.title.strip():
            return window
    for window in windows:
        if window.visible and window.title.strip():
            return window
    return windows[0] if windows else None


def _qqmusic_window_snapshot() -> dict[str, Any]:
    process_ids = find_process_ids("QQMusic.exe")
    if not process_ids:
        return {"status": "error", "error": "QQMusic process not found"}

    windows = list_top_level_windows(process_ids=process_ids)
    main_window = _qqmusic_select_main_window(windows)
    daemon_window = next((window for window in windows if window.class_name == "QQMusic_Daemon_Wnd"), None)
    return {
        "status": "ok",
        "title": main_window.title if main_window else "",
        "handle": main_window.hwnd if main_window else 0,
        "process_id": main_window.process_id if main_window else process_ids[0],
        "daemon_title": daemon_window.title if daemon_window else "",
        "window_titles": [
            {
                "hwnd": window.hwnd,
                "class": window.class_name,
                "text": window.title,
                "visible": window.visible,
            }
            for window in windows
        ],
    }


def _qqmusic_is_interference_window(window: TopLevelWindowInfo) -> bool:
    title = window.title.strip()
    if not title:
        return False
    if window.class_name in QQMUSIC_PROTECTED_WINDOW_CLASSES:
        return False
    return all(token in title for token in QQMUSIC_REPAIR_WINDOW_TOKENS)


def _qqmusic_cleanup_interference_windows(
    *,
    protect_hwnds: set[int] | None = None,
    baseline_hwnds: set[int] | None = None,
) -> dict[str, Any]:
    protect_hwnds = set(protect_hwnds or set())
    baseline_hwnds = set(baseline_hwnds or set())
    windows = _qqmusic_process_windows(visible_only=True)
    candidates = [
        window
        for window in windows
        if _qqmusic_is_interference_window(window)
        and (not baseline_hwnds or window.hwnd not in baseline_hwnds)
    ]
    return close_top_level_windows(
        windows=candidates,
        protect_hwnds=protect_hwnds | baseline_hwnds,
        protect_classes=QQMUSIC_PROTECTED_WINDOW_CLASSES,
        timeout_ms=500,
    )


def _qqmusic_verification_title(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("daemon_title") or snapshot.get("title") or "")


def _qqmusic_playback_verified(
    snapshot: dict[str, Any],
    *,
    expected_title: str,
    expected_singer: str,
) -> bool:
    verification_title = _qqmusic_verification_title(snapshot)
    return bool(
        expected_title
        and expected_title in verification_title
        and (not expected_singer or expected_singer in verification_title)
    )


def _qqmusic_protocol_string_candidates(song_id: int) -> list[dict[str, str]]:
    return [
        {
            "name": "playsong_query",
            "payload": f"tencent://QQMusic/?version=1&cmd_count=1&cmd_0=playsong&id_0={song_id}&songtype_0=0",
        },
        {
            "name": "playsong_ands",
            "payload": f"tencent://QQMusic/?version=1&&cmd_count==1&&cmd_0==playsong&&id_0=={song_id}&&songtype_0==0",
        },
        {
            "name": "addsong_query",
            "payload": f"tencent://QQMusic/?version=1&cmd_count=1&cmd_0=addsong&id_0={song_id}&songtype_0=0",
        },
        {
            "name": "bare_query",
            "payload": f"QQMusic/?version=1&cmd_count=1&cmd_0=playsong&id_0={song_id}&songtype_0=0",
        },
        {
            "name": "bare_ands",
            "payload": f"QQMusic/?version=1&&cmd_count==1&&cmd_0==playsong&&id_0=={song_id}&&songtype_0==0",
        },
    ]


def _qqmusic_run_tencent_protocol_attempt(
    *,
    qqmusic_path: Path,
    attempt_name: str,
    payload_text: str,
    use_file: bool,
    expected_title: str,
    expected_singer: str,
) -> dict[str, Any]:
    protocol_path: Path | None = None
    try:
        if use_file:
            protocol_path = Path(tempfile.gettempdir()) / f"omnicontrol-qqmusic-{attempt_name}.txt"
            protocol_path.write_text(payload_text, encoding="utf-8")
            command = [str(qqmusic_path), "/TencentProtocolFile", str(protocol_path)]
        else:
            command = [str(qqmusic_path), "/TencentProtocol", payload_text]

        subprocess.Popen(command)
        time.sleep(1.5)
        snapshot = _qqmusic_window_snapshot()
        verification_title = _qqmusic_verification_title(snapshot)
        playback_verified = _qqmusic_playback_verified(
            snapshot,
            expected_title=expected_title,
            expected_singer=expected_singer,
        )
        return {
            "method": attempt_name,
            "returncode": 0 if playback_verified else 1,
            "stdout": "",
            "stderr": "" if playback_verified else "TencentProtocol did not change playback title",
            "command_ok": playback_verified,
            "timed_out": False,
            "powershell_path": "",
            "command": command,
            "payload_text": payload_text,
            "verification_title": verification_title,
            "playback_verified": playback_verified,
            "protocol_file": str(protocol_path) if protocol_path is not None else None,
        }
    finally:
        if protocol_path is not None:
            protocol_path.unlink(missing_ok=True)


def _qqmusic_execute_tencent_protocol(
    *,
    qqmusic_path: Path,
    song_id: int,
    expected_title: str,
    expected_singer: str,
) -> dict[str, Any]:
    learned = recommended_launch_overrides("qqmusic-play")
    preferred_methods: list[str] = []
    for key in ("preferred_method_order", "preferred_command_methods"):
        for method in learned.get(key, []):
            method_name = str(method)
            if method_name and method_name not in preferred_methods:
                preferred_methods.append(method_name)

    specs: list[TransportAttemptSpec] = []
    for candidate in _qqmusic_protocol_string_candidates(song_id):
        for route_name, use_file in (("file", True), ("direct", False)):
            method_name = f"tencent_protocol_{route_name}:{candidate['name']}"
            specs.append(
                TransportAttemptSpec(
                    name=method_name,
                    run=lambda candidate=candidate, method_name=method_name, use_file=use_file: _qqmusic_run_tencent_protocol_attempt(
                        qqmusic_path=qqmusic_path,
                        attempt_name=method_name,
                        payload_text=str(candidate["payload"]),
                        use_file=use_file,
                        expected_title=expected_title,
                        expected_singer=expected_singer,
                    ),
                )
            )

    payload = run_ordered_transport_attempts(
        specs,
        learned_order=preferred_methods,
        success_key="command_ok",
    )
    payload["command_attempts"] = payload.pop("attempts")
    payload["command_probe"] = {}
    payload["learned_overrides"] = learned
    return payload


def _qqmusic_powershell_path(*, prefer_32_bit: bool = True) -> str:
    windows_root = Path(r"C:\Windows")
    if prefer_32_bit:
        candidates = [
            windows_root / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
            windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        ]
    else:
        candidates = [
            windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
            windows_root / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "powershell"


def _qqmusic_control_helper_script_path() -> Path:
    return _resource_path("qqmusic_control_helper.ps1")


def _run_qqmusic_control_helper(
    mode: str,
    *,
    method: str | None = None,
    xml_path: Path | None = None,
    version: int | None = None,
    qq_uin: int | None = None,
    key: str | None = None,
    platform_key: str | None = None,
    login_type: int | None = None,
    do_login: bool = True,
    do_bind: bool = True,
    do_load_playlist: bool = False,
    timeout: int = 8,
) -> dict[str, Any]:
    powershell_path = _qqmusic_powershell_path()
    command = [
        powershell_path,
        "-Sta",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(_qqmusic_control_helper_script_path()),
        "-Mode",
        mode,
        "-DoLogin",
        ("1" if do_login else "0"),
        "-DoBind",
        ("1" if do_bind else "0"),
        "-DoLoadPlayList",
        ("1" if do_load_playlist else "0"),
    ]
    if method:
        command.extend(["-Method", method])
    if xml_path is not None:
        command.extend(["-XmlPath", str(xml_path)])
    if version is not None:
        command.extend(["-Version", str(version)])
    if qq_uin is not None:
        command.extend(["-QQUin", str(qq_uin)])
    if key:
        command.extend(["-Key", key])
    if platform_key:
        command.extend(["-PlatformKey", platform_key])
    if login_type is not None:
        command.extend(["-LoginType", str(login_type)])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        payload = _parse_json_output(result.stdout, result.stderr)
        payload["returncode"] = result.returncode
        payload["powershell_path"] = powershell_path
        payload["command"] = command
        payload["stdout"] = _decode_output_text(result.stdout)
        payload["stderr"] = _decode_output_text(result.stderr)
        return payload
    except subprocess.TimeoutExpired as error:
        return {
            "returncode": 124,
            "powershell_path": powershell_path,
            "command": command,
            "stdout": _decode_output_text(error.stdout),
            "stderr": _decode_output_text(error.stderr) or "QQMusic control helper timed out",
        }


def _qqmusic_execute_control_command(
    xml: str | None,
    *,
    method: str,
    timeout: int = 8,
) -> dict[str, Any]:
    xml_path: Path | None = None
    try:
        if xml is not None:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".xml",
                prefix="omnicontrol-qqmusic-",
                delete=False,
            ) as xml_handle:
                xml_path = Path(xml_handle.name)
                xml_handle.write(xml)
        payload = _run_qqmusic_control_helper(
            "invoke",
            method=method,
            xml_path=xml_path,
            timeout=timeout,
        )
        return_value = payload.get("return_value")
        if method == "CanWebExecCommand":
            command_ok = str(return_value).strip().lower() not in {"", "0", "false", "none"}
        else:
            command_ok = int(payload.get("returncode", 1)) == 0
        return {
            "method": method,
            "returncode": int(payload.get("returncode", 1)),
            "stdout": str(payload.get("stdout") or ""),
            "stderr": str(payload.get("stderr") or ""),
            "command_ok": command_ok,
            "timed_out": int(payload.get("returncode", 1)) == 124,
            "powershell_path": str(payload.get("powershell_path") or ""),
            "return_value": return_value,
        }
    finally:
        if xml_path is not None:
            xml_path.unlink(missing_ok=True)


def _qqmusic_control_script_lines(
    *,
    method: str,
    xml_path: Path | None,
) -> list[str]:
    lines = [
        'Add-Type @"',
        "using System;",
        "using System.Runtime.InteropServices;",
        '[ComImport, Guid("10126174-A34C-4DA4-9B5A-B71DE87EDD34"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]',
        "public interface IQQMusicCreator {",
        "  [DispId(2)] [return: MarshalAs(UnmanagedType.IDispatch)] object WebCreateInterface([MarshalAs(UnmanagedType.BStr)] string bstrRiid);",
        "}",
        '[ComImport, Guid("6927992D-6A89-4549-8A32-95901BF5D920")]',
        "public class QQMusicCreatorClass { }",
        '[ComImport, Guid("B07CCA0D-7B19-4921-868C-46B6C837825D"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]',
        "public interface IQQMusicControl {",
        "  [DispId(10)] void Bind();",
        "  [DispId(12)] object ExecuteCommand([MarshalAs(UnmanagedType.BStr)] string bstrCmd);",
        "  [DispId(18)] int CanWebExecCommand();",
        "  [DispId(19)] object WebExecCommand([MarshalAs(UnmanagedType.BStr)] string bstrCmd);",
        "  [DispId(23)] object WebExecCommand2([MarshalAs(UnmanagedType.BStr)] string bstrCmd, [MarshalAs(UnmanagedType.BStr)] string bstrAdvCmd);",
        "}",
        "public static class QQMusicControlBridge {",
        "  public static object Invoke(string method, string commandXml) {",
        "    IQQMusicCreator creator = (IQQMusicCreator)new QQMusicCreatorClass();",
        '    IQQMusicControl control = (IQQMusicControl)creator.WebCreateInterface("IQQMusicControl");',
        "    try { control.Bind(); } catch { }",
        '    if (method == "CanWebExecCommand") return control.CanWebExecCommand();',
        '    if (method == "ExecuteCommand") return control.ExecuteCommand(commandXml);',
        '    if (method == "WebExecCommand") return control.WebExecCommand(commandXml);',
        '    if (method == "WebExecCommand2") return control.WebExecCommand2(commandXml, "");',
        '    throw new InvalidOperationException("Unsupported QQMusic control method: " + method);',
        "  }",
        "}",
        '"@',
        "$result = $null",
        "try {",
    ]
    if xml_path is not None:
        lines.insert(0, f"$xml = Get-Content -LiteralPath '{xml_path}' -Raw")

    if method == "CanWebExecCommand":
        lines.append("  $result = [QQMusicControlBridge]::Invoke('CanWebExecCommand', '')")
    elif method == "WebExecCommand2":
        lines.append("  $result = [QQMusicControlBridge]::Invoke('WebExecCommand2', $xml)")
    elif xml_path is not None:
        lines.append(f"  $result = [QQMusicControlBridge]::Invoke('{method}', $xml)")
    else:
        lines.append(f"  $result = [QQMusicControlBridge]::Invoke('{method}', '')")

    lines.extend(
        [
            "} catch {",
            "  Write-Error $_",
            "  exit 1",
            "}",
            "if ($null -ne $result) {",
            "  Write-Output ('RETURN=' + $result)",
            "}",
        ]
    )
    return lines


def _qqmusic_execute_control_methods(xml: str) -> dict[str, Any]:
    learned = recommended_launch_overrides("qqmusic-play")
    preferred_methods: list[str] = []
    for key in ("preferred_method_order", "preferred_command_methods"):
        for method in learned.get(key, []):
            method_name = str(method)
            if method_name and method_name not in preferred_methods:
                preferred_methods.append(method_name)
    probe_payload = _qqmusic_execute_control_command(None, method="CanWebExecCommand", timeout=2)
    if probe_payload.get("returncode") == 0 and not probe_payload.get("command_ok"):
        method_specs = [item for item in QQMUSIC_VENDOR_COMMAND_METHODS if item[0] == "ExecuteCommand"]
    else:
        method_specs = list(QQMUSIC_VENDOR_COMMAND_METHODS)
    specs = [
        TransportAttemptSpec(
            name=method,
            run=lambda method=method, timeout=timeout: _qqmusic_execute_control_command(
                xml,
                method=method,
                timeout=timeout,
            ),
        )
        for method, timeout in method_specs
    ]
    payload = run_ordered_transport_attempts(
        specs,
        probe=lambda: probe_payload,
        learned_order=preferred_methods,
        success_key="command_ok",
    )
    payload["command_attempts"] = payload.pop("attempts")
    payload["command_probe"] = payload.pop("probe")
    payload["learned_overrides"] = learned
    return payload


def _qqmusic_private_protocol_context() -> dict[str, Any]:
    windows = _qqmusic_process_windows()
    main_window = _qqmusic_select_main_window(windows)
    dummy_window = next((window for window in windows if window.class_name.startswith("QQMusicDummyWindow")), None)
    target_window = next((window for window in windows if window.class_name == QQMUSIC_PRIVATE_PROTOCOL_WINDOW_CLASS), None)

    sender_hwnds: list[int] = []
    for candidate in [
        main_window.hwnd if main_window is not None else 0,
        dummy_window.hwnd if dummy_window is not None else 0,
        0,
    ]:
        if candidate not in sender_hwnds:
            sender_hwnds.append(candidate)

    return {
        "process_ids": sorted({window.process_id for window in windows}),
        "target_hwnd": target_window.hwnd if target_window is not None else 0,
        "main_hwnd": main_window.hwnd if main_window is not None else 0,
        "sender_hwnds": sender_hwnds,
    }


def _qqmusic_private_protocol_attempt_matrix(
    *,
    song_id: int,
    song_mid: str,
    legacy_xml_path: str | None,
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    if legacy_xml_path:
        parse_xml_payload = f"/ParseXMLFile '{legacy_xml_path}'"
        attempts.extend(
            [
                {"name": "parsexml_legacy_proto1", "proto_type": 1, "payload_text": parse_xml_payload},
                {"name": "parsexml_legacy_proto0", "proto_type": 0, "payload_text": parse_xml_payload},
                {"name": "parsexml_legacy_proto2", "proto_type": 2, "payload_text": parse_xml_payload},
            ]
        )
    if song_mid:
        attempts.extend(
            [
                {
                    "name": "tencent_url_proto4",
                    "proto_type": 4,
                    "payload_text": f"tencent://QQMusic/?cmd=play&songid={song_id}&songmid={song_mid}",
                },
                {
                    "name": "tencent_url_proto3",
                    "proto_type": 3,
                    "payload_text": f"tencent://QQMusic/?cmd=play&songid={song_id}&songmid={song_mid}",
                },
                {
                    "name": "tencent_mid_proto4",
                    "proto_type": 4,
                    "payload_text": f"tencent://QQMusic/?cmd=play&mid={song_mid}",
                },
                {
                    "name": "tencent_mid_proto3",
                    "proto_type": 3,
                    "payload_text": f"tencent://QQMusic/?cmd=play&mid={song_mid}",
                },
            ]
        )
    return attempts


def _qqmusic_run_private_protocol_attempt(
    *,
    attempt_name: str,
    target_hwnd: int,
    sender_hwnd: int,
    proto_type: int,
    payload_text: str,
    expected_title: str,
    expected_singer: str,
) -> dict[str, Any]:
    packet = build_tagged_packet(
        encode_utf16le_text(payload_text),
        TaggedPacketSpec(tag="QMAS", version=100, proto_type=proto_type),
    )
    message_result = send_wm_copydata(
        target_hwnd=target_hwnd,
        sender_hwnd=sender_hwnd,
        payload=packet,
        timeout_ms=1000,
    )
    time.sleep(0.15)
    snapshot = _qqmusic_window_snapshot()
    verification_title = _qqmusic_verification_title(snapshot)
    playback_verified = _qqmusic_playback_verified(
        snapshot,
        expected_title=expected_title,
        expected_singer=expected_singer,
    )
    return {
        "method": attempt_name,
        "returncode": message_result["returncode"],
        "stdout": "",
        "stderr": "" if playback_verified else "private protocol did not change playback title",
        "command_ok": playback_verified,
        "timed_out": bool(message_result["timed_out"]),
        "powershell_path": "",
        "sender_hwnd": sender_hwnd,
        "target_hwnd": target_hwnd,
        "proto_type": proto_type,
        "payload_text": payload_text,
        "wm_copydata": message_result,
        "verification_title": verification_title,
        "playback_verified": playback_verified,
    }


def _qqmusic_execute_private_protocol(
    *,
    song_id: int,
    song_mid: str,
    legacy_xml_path: str | None,
    expected_title: str,
    expected_singer: str,
) -> dict[str, Any]:
    learned = recommended_launch_overrides("qqmusic-play")
    preferred_methods: list[str] = []
    for key in ("preferred_method_order", "preferred_command_methods"):
        for method in learned.get(key, []):
            method_name = str(method)
            if method_name and method_name not in preferred_methods:
                preferred_methods.append(method_name)

    context = _qqmusic_private_protocol_context()
    if not context["target_hwnd"]:
        return {
            "method": "private_protocol_unavailable",
            "returncode": 1,
            "stdout": "",
            "stderr": "QQMusic private protocol window was not found",
            "command_ok": False,
            "timed_out": False,
            "powershell_path": "",
            "command_attempts": [],
            "command_probe": context,
            "learned_overrides": learned,
        }

    specs: list[TransportAttemptSpec] = []
    for sender_hwnd in context["sender_hwnds"]:
        for attempt in _qqmusic_private_protocol_attempt_matrix(
            song_id=song_id,
            song_mid=song_mid,
            legacy_xml_path=legacy_xml_path,
        ):
            spec_name = f"{attempt['name']}@{sender_hwnd or 'null'}"
            specs.append(
                TransportAttemptSpec(
                    name=spec_name,
                    run=lambda sender_hwnd=sender_hwnd, attempt=attempt, spec_name=spec_name: _qqmusic_run_private_protocol_attempt(
                        attempt_name=spec_name,
                        target_hwnd=context["target_hwnd"],
                        sender_hwnd=sender_hwnd,
                        proto_type=int(attempt["proto_type"]),
                        payload_text=str(attempt["payload_text"]),
                        expected_title=expected_title,
                        expected_singer=expected_singer,
                    ),
                )
            )

    payload = run_ordered_transport_attempts(
        specs,
        probe=lambda: context,
        learned_order=preferred_methods,
        success_key="command_ok",
    )
    payload["command_attempts"] = payload.pop("attempts")
    payload["command_probe"] = payload.pop("probe")
    payload["learned_overrides"] = learned
    return payload


def _qqmusic_build_transport_specs(
    *,
    qqmusic_path: Path,
    song_id: int,
    song_mid: str,
    legacy_xml: str | None,
    legacy_xml_path: str | None,
    runtime_session: dict[str, Any],
    runtime_auth_xml: str | None,
    expected_title: str,
    expected_singer: str,
) -> dict[str, Any]:
    learned = recommended_launch_overrides("qqmusic-play")
    preferred_transports = [
        str(item)
        for item in learned.get("preferred_transport_variants", learned.get("preferred_transport_order", []))
        if str(item)
    ]
    transport_plan = build_software_native_plan(
        QQMUSIC_TRANSPORT_DESCRIPTORS,
        preferred_order=preferred_transports,
    )
    suppressed = [descriptor.name for descriptor in QQMUSIC_TRANSPORT_DESCRIPTORS if not descriptor.software_native]

    specs: list[TransportAttemptSpec] = []
    for transport_name in transport_plan:
        if transport_name == "legacy_jump_xml_runtime_auth" and runtime_auth_xml:
            specs.append(
                TransportAttemptSpec(
                    name=transport_name,
                    run=lambda runtime_auth_xml=runtime_auth_xml, transport_name=transport_name: {
                        **_qqmusic_execute_control_methods(runtime_auth_xml),
                        "transport_variant": transport_name,
                    },
                )
            )
        elif transport_name == "tencent_protocol":
            specs.append(
                TransportAttemptSpec(
                    name=transport_name,
                    run=lambda transport_name=transport_name: {
                        **_qqmusic_execute_tencent_protocol(
                            qqmusic_path=qqmusic_path,
                            song_id=song_id,
                            expected_title=expected_title,
                            expected_singer=expected_singer,
                        ),
                        "transport_variant": transport_name,
                    },
                )
            )
        elif transport_name == "private_protocol":
            specs.append(
                TransportAttemptSpec(
                    name=transport_name,
                    run=lambda transport_name=transport_name: {
                        **_qqmusic_execute_private_protocol(
                            song_id=song_id,
                            song_mid=song_mid,
                            legacy_xml_path=legacy_xml_path,
                            expected_title=expected_title,
                            expected_singer=expected_singer,
                        ),
                        "transport_variant": transport_name,
                    },
                )
            )
        elif transport_name == "legacy_jump_xml" and legacy_xml:
            specs.append(
                TransportAttemptSpec(
                    name=transport_name,
                    run=lambda legacy_xml=legacy_xml, transport_name=transport_name: {
                        **_qqmusic_execute_control_methods(legacy_xml),
                        "transport_variant": transport_name,
                    },
                )
            )

    return {
        "specs": specs,
        "transport_plan": transport_plan,
        "suppressed_transport_variants": suppressed,
    }


def _qqmusic_execute_transport_variants(
    *,
    qqmusic_path: Path,
    song_id: int,
    song_mid: str,
    legacy_xml: str | None,
    legacy_xml_path: str | None,
    runtime_session: dict[str, Any],
    runtime_auth_xml: str | None,
    expected_title: str,
    expected_singer: str,
) -> dict[str, Any]:
    transport = _qqmusic_build_transport_specs(
        qqmusic_path=qqmusic_path,
        song_id=song_id,
        song_mid=song_mid,
        legacy_xml=legacy_xml,
        legacy_xml_path=legacy_xml_path,
        runtime_session=runtime_session,
        runtime_auth_xml=runtime_auth_xml,
        expected_title=expected_title,
        expected_singer=expected_singer,
    )
    specs = transport["specs"]
    if not specs:
        return {
            "command_ok": False,
            "transport_variant": "",
            "transport_attempts": [],
            "transport_plan": transport["transport_plan"],
            "suppressed_transport_variants": transport["suppressed_transport_variants"],
            "method": "",
            "stdout": "",
            "stderr": "No software-native QQMusic transport was available",
            "command_attempts": [],
            "command_probe": {},
            "powershell_path": "",
            "learned_overrides": recommended_launch_overrides("qqmusic-play"),
        }

    payload = run_ordered_transport_attempts(
        specs,
        learned_order=transport["transport_plan"],
        success_key="command_ok",
    )
    payload["transport_attempts"] = payload.pop("attempts")
    payload["transport_plan"] = transport["transport_plan"]
    payload["suppressed_transport_variants"] = transport["suppressed_transport_variants"]
    return payload


def _qqmusic_ensure_running(app_path: Path) -> bool:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "if (Get-Process QQMusic -ErrorAction SilentlyContinue) { 'running' }"],
        capture_output=True,
        check=False,
    )
    if "running" in _decode_output_text(result.stdout):
        return False
    subprocess.Popen([str(app_path)])
    time.sleep(6)
    return True


def run_qqmusic_play_smoke(
    *,
    query: str,
    output_dir: Path | None,
    qqmusic_path: Path,
) -> dict[str, Any]:
    if not qqmusic_path.exists():
        raise FileNotFoundError(f"QQMusic app not found: {qqmusic_path}")
    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "qqmusic-play"
    output_dir.mkdir(parents=True, exist_ok=True)

    launched = _qqmusic_ensure_running(qqmusic_path)
    candidates = _qqmusic_search_candidates(query)
    selected = _qqmusic_select_candidate(query, candidates)
    detail = _qqmusic_fetch_song_detail(int(selected["id"]))
    track_info = dict(detail.get("track_info", {}))
    if not track_info:
        raise RuntimeError(f"QQMusic detail API returned no track_info for song id {selected['id']}")

    (output_dir / "play-command.xml").unlink(missing_ok=True)
    legacy_xml = _qqmusic_fetch_legacy_play_command_xml(int(selected["id"]))
    legacy_xml_path: str | None = None
    if legacy_xml:
        legacy_path = output_dir / "legacy-play-command.xml"
        legacy_path.write_text(legacy_xml, encoding="utf-8")
        legacy_xml_path = str(legacy_path)
    else:
        (output_dir / "legacy-play-command.xml").unlink(missing_ok=True)
    runtime_session = _qqmusic_runtime_session()
    runtime_auth_info: dict[str, Any] | None = None
    runtime_auth_xml: str | None = None
    runtime_auth_xml_path: str | None = None
    if legacy_xml:
        try:
            runtime_auth_info = _qqmusic_fetch_authenticated_playback_info(
                track_info=track_info,
                runtime_session=runtime_session,
            )
        except Exception as error:
            runtime_auth_info = {"error": str(error)}
        if runtime_auth_info and runtime_auth_info.get("full_url"):
            runtime_auth_xml = _qqmusic_patch_legacy_xml_with_runtime_auth(
                legacy_xml,
                runtime_session=runtime_session,
                playback_info=runtime_auth_info,
            )
            runtime_auth_path = output_dir / "legacy-play-command-runtime-auth.xml"
            runtime_auth_path.write_text(runtime_auth_xml, encoding="utf-8")
            runtime_auth_xml_path = str(runtime_auth_path)
        else:
            (output_dir / "legacy-play-command-runtime-auth.xml").unlink(missing_ok=True)
    expected_title = str(track_info.get("title") or selected.get("name") or "")
    expected_singer = str(selected.get("singer") or "")

    initial_snapshot = _qqmusic_window_snapshot()
    initial_main_hwnd = int(initial_snapshot.get("handle") or 0)
    pre_cleanup = _qqmusic_cleanup_interference_windows(
        protect_hwnds={initial_main_hwnd} if initial_main_hwnd else set(),
    )
    baseline_hwnds = {window.hwnd for window in _qqmusic_process_windows(visible_only=True)}
    before = _qqmusic_window_snapshot()
    command_payload = _qqmusic_execute_transport_variants(
        qqmusic_path=qqmusic_path,
        song_id=int(selected["id"]),
        song_mid=str(selected.get("mid") or ""),
        legacy_xml=legacy_xml,
        legacy_xml_path=legacy_xml_path,
        runtime_session=runtime_session,
        runtime_auth_xml=runtime_auth_xml,
        expected_title=expected_title,
        expected_singer=expected_singer,
    )
    time.sleep(1)
    after = _qqmusic_window_snapshot()
    final_main_hwnd = int(after.get("handle") or before.get("handle") or 0)
    post_cleanup = _qqmusic_cleanup_interference_windows(
        protect_hwnds={final_main_hwnd} if final_main_hwnd else set(),
        baseline_hwnds=baseline_hwnds,
    )
    control_context = _qqmusic_control_context_snapshot()
    control_events = _qqmusic_control_event_probe(str(output_dir / "legacy-play-command.xml")) if legacy_xml_path else {}

    before_title = str(before.get("title", ""))
    after_title = str(after.get("title", ""))
    before_daemon_title = str(before.get("daemon_title", ""))
    after_daemon_title = str(after.get("daemon_title", ""))
    verification_title = after_daemon_title or after_title
    playback_verified = bool(
        expected_title
        and expected_title in verification_title
        and (not expected_singer or expected_singer in verification_title)
    )
    blockers: list[str] = []
    if not command_payload["command_ok"]:
        blockers.append("QQMusic control command failed")
    if not playback_verified:
        blockers.append("vendor command accepted but playback was not verified from window title")

    payload = {
        "profile": "qqmusic-play",
        "status": "partial" if command_payload["command_ok"] else "blocked",
        "query": query,
        "launched_app": launched,
        "song_id": int(selected["id"]),
        "song_mid": selected.get("mid"),
        "song_name": selected.get("name"),
        "singer_name": selected.get("singer"),
        "search_result_count": len(candidates),
        "detail_ok": bool(track_info),
        "command_ok": command_payload["command_ok"],
        "command_method": command_payload["method"],
        "transport_variant": command_payload.get("transport_variant"),
        "transport_attempts": command_payload.get("transport_attempts", []),
        "transport_plan": command_payload.get("transport_plan", []),
        "suppressed_transport_variants": command_payload.get("suppressed_transport_variants", []),
        "command_stdout": command_payload["stdout"],
        "command_stderr": command_payload["stderr"],
        "command_attempts": command_payload["command_attempts"],
        "command_probe": command_payload["command_probe"],
        "command_powershell_path": command_payload["powershell_path"],
        "learned_overrides": command_payload["learned_overrides"],
        "runtime_session": runtime_session,
        "runtime_auth_info": runtime_auth_info,
        "runtime_auth_xml_path": runtime_auth_xml_path,
        "control_context": control_context,
        "control_events": control_events,
        "interference_cleanup_before": pre_cleanup,
        "interference_cleanup_after": post_cleanup,
        "title_before": before_title,
        "title": after_title,
        "daemon_title_before": before_daemon_title,
        "daemon_title": after_daemon_title,
        "verification_title": verification_title,
        "window_titles_before": before.get("window_titles", []),
        "window_titles": after.get("window_titles", []),
        "xml_path": None,
        "legacy_xml_path": legacy_xml_path,
        "playback_verified": playback_verified,
        "blockers": blockers,
        "selected_song": selected,
    }
    payload = _finalize_payload("qqmusic-play", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("qqmusic-play", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "qqmusic-play smoke failed"))
    return payload


def _extract_return_value(text: str) -> str | None:
    prefix = "RETURN="
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):]
    return None


def _qqmusic_control_context_snapshot() -> dict[str, Any]:
    return _run_qqmusic_control_helper(
        "context",
        timeout=8,
    )


def _qqmusic_control_event_probe(xml_path: str) -> dict[str, Any]:
    return _run_qqmusic_control_helper(
        "events",
        xml_path=Path(xml_path),
        timeout=12,
    )


def _qqmusic_runtime_session() -> dict[str, Any]:
    return _run_qqmusic_control_helper(
        "runtime",
        do_login=False,
        do_bind=False,
        timeout=12,
    )


def _qqmusic_fetch_authenticated_playback_info(
    *,
    track_info: dict[str, Any],
    runtime_session: dict[str, Any],
) -> dict[str, Any] | None:
    qqmusic_uin = str(runtime_session.get("qqmusic_uin") or "")
    qqmusic_key = str(runtime_session.get("qqmusic_key") or "")
    qqmusic_guid = str(runtime_session.get("qqmusic_guid") or "")
    tme_login_type = str(runtime_session.get("tmeLoginType") or "")
    if not (qqmusic_uin and qqmusic_key and qqmusic_guid):
        return None

    media_mid = str(track_info.get("file", {}).get("media_mid", ""))
    song_mid = str(track_info.get("mid", ""))
    if not (media_mid and song_mid):
        return None

    request_payload = {
        "comm": {
            "authst": qqmusic_key,
            "cv": "2045",
            "ct": "19",
            "uin": qqmusic_uin,
            "guid": qqmusic_guid,
            "patch": "118",
            "tmeAppID": "qqmusic",
            "tmeLoginType": tme_login_type or "0",
        },
        "req_1": {
            "module": "music.vkey.GetEVkey",
            "method": "CgiGetHotVkey",
            "param": {
                "filename": [f"C400{media_mid}.m4a"],
                "songmid": [song_mid],
                "guid": qqmusic_guid,
                "uin": qqmusic_uin,
                "loginflag": 1,
                "platform": "20",
            },
        },
    }
    cookie_pairs = [
        ("psrf_qqopenid", str(runtime_session.get("psrf_qqopenid") or "")),
        ("psrf_qqrefresh_token", str(runtime_session.get("psrf_qqrefresh_token") or "")),
        ("qm_keyst", str(runtime_session.get("qm_keyst") or "")),
        ("qqmusic_gkey", str(runtime_session.get("qqmusic_gkey") or "")),
        ("qqmusic_guid", qqmusic_guid),
        ("qqmusic_key", qqmusic_key),
        ("qqmusic_miniversion", str(runtime_session.get("qqmusic_miniversion") or "")),
        ("qqmusic_uin", qqmusic_uin),
        ("qqmusic_version", str(runtime_session.get("qqmusic_version") or "")),
        ("tmeLoginType", tme_login_type),
        ("uid", str(runtime_session.get("uid") or "")),
        ("qm_hideuin", str(runtime_session.get("qm_hideuin") or qqmusic_uin)),
        ("qm_method", str(runtime_session.get("qm_method") or "")),
    ]
    cookie_header = "; ".join(f"{key}={value}" for key, value in cookie_pairs if value)
    url = (
        "https://u.y.qq.com/cgi-bin/musicu.fcg?format=json&data="
        f"{quote(json.dumps(request_payload, ensure_ascii=False, separators=(',', ':')), safe='')}"
    )
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)",
            "Referer": "https://y.qq.com/",
            "Cookie": cookie_header,
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    urls = payload.get("req_1", {}).get("data", {}).get("urls", [])
    if not urls:
        return None
    item = dict(urls[0])
    purl = str(item.get("purl") or "")
    if not purl:
        return None
    vkey_match = re.search(r"[?&]vkey=([^&]+)", purl)
    return {
        "runtime_session_uin": qqmusic_uin,
        "full_url": f"http://aqqmusic.tc.qq.com/{purl}",
        "vkey": vkey_match.group(1) if vkey_match else "",
        "purl": purl,
        "raw": payload,
    }


def _qqmusic_patch_legacy_xml_with_runtime_auth(
    legacy_xml: str,
    *,
    runtime_session: dict[str, Any],
    playback_info: dict[str, Any],
) -> str:
    root = ET.fromstring(legacy_xml)
    qq_node = root.find("./cmd/qq")
    if qq_node is not None:
        qq_node.set("uin", str(runtime_session.get("qqmusic_uin") or "0"))
    music_url = root.find("./cmd/music/url")
    if music_url is not None:
        music_url.text = str(playback_info.get("full_url") or "")
    exp_fuin = root.find("./cmd/expinfo/fuin")
    if exp_fuin is not None:
        exp_fuin.text = str(runtime_session.get("qqmusic_uin") or "0")
    chk_url = root.find("./cmd/chkinfo/url")
    if chk_url is not None:
        chk_url.text = str(playback_info.get("full_url") or "")
    chk_uin = root.find("./cmd/chkinfo/uin")
    if chk_uin is not None:
        chk_uin.text = str(runtime_session.get("qqmusic_uin") or "0")
    chk_key = root.find("./cmd/chkinfo/key")
    if chk_key is not None:
        chk_key.text = str(playback_info.get("vkey") or "")
    return ET.tostring(root, encoding="unicode")


def _extract_env_assignment(text: str, name: str) -> str | None:
    prefix = f"{name}="
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def _resolve_word_path() -> Path:
    candidates = [DEFAULT_WORD_PATH]
    candidates.extend(_app_paths_registry_values("WINWORD.EXE"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DEFAULT_WORD_PATH


def _resolve_chrome_path() -> Path:
    candidates = [DEFAULT_CHROME_PATH]
    candidates.extend(_app_paths_registry_values("chrome.exe"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DEFAULT_CHROME_PATH


def _app_paths_registry_values(executable_name: str) -> list[Path]:
    try:
        import winreg
    except ImportError:  # pragma: no cover - non-Windows
        return []

    subkeys = [
        rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}",
        rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}",
    ]
    roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    results: list[Path] = []
    for root in roots:
        for subkey in subkeys:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    results.append(Path(value))
            except OSError:
                continue
    return results
