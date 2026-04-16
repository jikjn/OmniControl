from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
import os
from pathlib import Path
import json
import re
import socket
import subprocess
import tempfile
import time
import zipfile
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
from omnicontrol.runtime.evidence import write_result_bundle
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
from omnicontrol.runtime.paths import resolve_run_output_dir, resolve_runtime_paths
from omnicontrol.runtime.registry import list_profile_ids
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
from omnicontrol.models import current_platform, dedupe_keep_order, display_name_from_target


DEFAULT_CHROME_URL = "data:text/html,<title>OmniControl Smoke</title><h1>OmniControl Smoke</h1>"
DEFAULT_WORD_PATH = Path(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE")
DEFAULT_WORD_MACOS_PATH = Path("/Applications/Microsoft Word.app")
DEFAULT_CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEFAULT_MASTERPDF_PATH = Path(r"C:\Program Files (x86)\MasterPDF\MasterPDF.exe")
DEFAULT_QQMUSIC_PATH = Path(r"C:\Program Files (x86)\Tencent\QQMusic\QQMusic.exe")

JETBRAINS_IDE_STEMS = (
    "pycharm",
    "idea",
    "intellij",
    "webstorm",
    "goland",
    "rider",
    "clion",
    "rubymine",
    "phpstorm",
    "datagrip",
    "dataspell",
    "rustrover",
)
JETBRAINS_UTILITY_STEMS = {"format", "inspect", "ltedit"}
CODE_IDE_STEMS = ("code", "code-insiders", "cursor", "windsurf", "trae", "codium", "vscodium")
IDE_WRITE_MARKER = "OmniControlIDEWriteOK"
IDE_BLOCKER_PATTERNS = {
    "subscription expired": "ide license dialog blocked the editor",
    "trial expired": "ide trial dialog blocked the editor",
    "license activation": "ide license activation dialog blocked the editor",
    "activation required": "ide license activation dialog blocked the editor",
}
IDE_LOG_BLOCKER_PATTERNS = {
    "currently being updated": "ide update in progress blocked the editor",
}
IDE_HASH_COMMENT_SUFFIXES = {
    ".py",
    ".ps1",
    ".psm1",
    ".psd1",
    ".rb",
    ".sh",
    ".bash",
    ".zsh",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
}
IDE_SLASH_COMMENT_SUFFIXES = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".kts",
    ".groovy",
    ".scala",
    ".swift",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".dart",
    ".php",
}
IDE_BLOCK_COMMENT_SUFFIXES = {".css", ".scss", ".less", ".jsonc"}
IDE_XML_COMMENT_SUFFIXES = {".xml", ".html", ".htm", ".xhtml", ".svg"}
JETBRAINS_MCP_COMPONENT_NAME = "McpServerSettings"
JETBRAINS_MCP_DEFAULT_PORT = 64342
JETBRAINS_MCP_PROTOCOL_VERSION = "2025-03-26"


def _default_output_dir(profile: str, override: Path | None = None) -> Path:
    return resolve_run_output_dir(profile, output=override)


def _default_output_file(profile: str, filename: str, override: Path | None = None) -> Path:
    if override is not None:
        return override
    return _default_output_dir(profile) / filename


def run_smoke(
    profile: str,
    *,
    source: str | None = None,
    output: str | None = None,
    query: str | None = None,
    url: str | None = None,
    chrome_path: str | None = None,
    word_path: str | None = None,
    app_path: str | None = None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if profile not in list_profile_ids():
        raise ValueError(f"Unknown smoke profile: {profile}")
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
    if profile == "ide-open":
        if not app_path:
            raise ValueError("ide-open requires --app-path")
        return run_ide_open_smoke(
            target=Path(source) if source else Path.cwd(),
            app_path=Path(app_path),
            output_dir=Path(output) if output else None,
        )
    if profile == "ide-write":
        if not source:
            raise ValueError("ide-write requires --source")
        if not app_path:
            raise ValueError("ide-write requires --app-path")
        return run_ide_write_smoke(
            target=Path(source),
            app_path=Path(app_path),
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
        )
    if profile == "ide-workflow":
        if not app_path:
            raise ValueError("ide-workflow requires --app-path")
        return run_ide_workflow_smoke(
            target=Path(source) if source else Path.cwd(),
            app_path=Path(app_path),
            output_dir=Path(output) if output else None,
            _profile_chain=next_chain,
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


def run_ide_open_smoke(
    *,
    target: Path,
    app_path: Path,
    output_dir: Path | None,
) -> dict[str, Any]:
    if current_platform() != "windows":
        raise RuntimeError("ide-open currently requires Windows.")

    resolved_target = target.expanduser().resolve()
    if not resolved_target.exists():
        raise FileNotFoundError(f"IDE target not found: {resolved_target}")

    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "ide-open"
    output_dir.mkdir(parents=True, exist_ok=True)

    launch = _launch_ide_target(
        target=resolved_target,
        app_path=app_path,
        output_dir=output_dir,
        timeout=25.0,
    )
    blockers: list[str] = []
    if not launch["processes"]:
        blockers.append("ide process was not observed under the install root")
    if not launch["window_titles"]:
        blockers.append("ide window was not observed")
    if launch["matched_window"] is None:
        blockers.append("ide window title did not expose the requested target")
    blockers.extend(launch["detected_blockers"])
    blockers = dedupe_keep_order(blockers)

    payload = {
        "profile": "ide-open",
        "status": "ok" if launch["matched_window"] is not None else "blocked",
        "target": str(resolved_target),
        "target_kind": "directory" if resolved_target.is_dir() else "file",
        "target_tokens": launch["target_tokens"],
        "app_path": str(launch["spec"]["app_path"]),
        "launcher_path": str(launch["spec"]["launcher_path"]),
        "install_root": str(launch["spec"]["install_root"]),
        "process_root": str(launch["spec"]["process_root"]),
        "family": launch["spec"]["family"],
        "command": launch["command"],
        "launch_pid": launch["launch_pid"],
        "returncode": launch["returncode"],
        "process_count_before": launch["process_count_before"],
        "process_count": len(launch["processes"]),
        "new_process_count": launch["new_process_count"],
        "processes": launch["processes"],
        "windows": launch["window_titles"],
        "window_name": launch["matched_window"].title if launch["matched_window"] is not None else (launch["window_titles"][0] if launch["window_titles"] else ""),
        "window_handle": launch["matched_window"].hwnd if launch["matched_window"] is not None else 0,
        "opened_target": launch["matched_window"] is not None,
        "duration_seconds": launch["duration_seconds"],
        "detected_blockers": launch["detected_blockers"],
        "blockers": blockers,
    }
    payload = _finalize_payload("ide-open", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("ide-open", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "ide-open smoke failed"))
    return payload


def run_ide_write_smoke(
    *,
    target: Path,
    app_path: Path,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict[str, Any]:
    if current_platform() != "windows":
        raise RuntimeError("ide-write currently requires Windows.")

    resolved_target = target.expanduser().resolve()
    if not resolved_target.exists():
        raise FileNotFoundError(f"IDE target not found: {resolved_target}")
    if resolved_target.is_dir():
        raise ValueError("ide-write requires a file target.")

    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "ide-write"
    output_dir.mkdir(parents=True, exist_ok=True)

    def _attempt() -> dict[str, Any]:
        launch = _launch_ide_target(
            target=resolved_target,
            app_path=app_path,
            output_dir=output_dir,
            timeout=35.0,
        )
        blockers = list(launch["detected_blockers"])
        if not launch["processes"]:
            blockers.append("ide process was not observed under the install root")
        if not launch["window_titles"]:
            blockers.append("ide window did not expose any visible title")
        matched_window = launch["matched_window"]
        probe_payload: dict[str, Any] = {}
        mcp_payload: dict[str, Any] = {}
        mcp_error_note: str | None = None
        marker_written = False
        write_transport = "file_format"
        if matched_window is None:
            blockers.append("ide window title did not expose the requested target")
        else:
            if str(launch["spec"]["family"]) == "jetbrains":
                mcp_payload = _apply_jetbrains_mcp_file_write(
                    target=resolved_target,
                    app_path=app_path,
                    marker=IDE_WRITE_MARKER,
                )
                if mcp_payload.get("status") == "ok":
                    marker_written = True
                    write_transport = "jetbrains_mcp"
                elif mcp_payload.get("error"):
                    mcp_error_note = str(mcp_payload["error"])
            if not marker_written:
                probe_payload = _apply_safe_ide_file_write(
                    target=resolved_target,
                    marker=IDE_WRITE_MARKER,
                )
                if probe_payload.get("status") == "error":
                    blockers.append(str(probe_payload.get("error") or "safe IDE write failed"))
                marker_written = _wait_for_file_marker(
                    resolved_target,
                    IDE_WRITE_MARKER,
                    timeout=2.0,
                )
                if not marker_written:
                    if mcp_error_note:
                        blockers.append(mcp_error_note)
                    blockers.append("target file did not reflect the write marker")
                if str(launch["spec"]["family"]) == "jetbrains":
                    marker_line = int(probe_payload.get("marker_line") or 1)
                    navigation = _launch_ide_target(
                        target=resolved_target,
                        app_path=app_path,
                        output_dir=output_dir,
                        timeout=20.0,
                        line=marker_line,
                        column=1,
                    )
                    if navigation["matched_window"] is None:
                        blockers.append("ide did not navigate back to the written target")
                    else:
                        matched_window = navigation["matched_window"]
                        launch = navigation
        blockers = dedupe_keep_order(blockers)
        payload = {
            "profile": "ide-write",
            "status": "ok" if marker_written else "blocked",
            "target": str(resolved_target),
            "target_kind": "file",
            "target_tokens": launch["target_tokens"],
            "app_path": str(launch["spec"]["app_path"]),
            "launcher_path": str(launch["spec"]["launcher_path"]),
            "install_root": str(launch["spec"]["install_root"]),
            "process_root": str(launch["spec"]["process_root"]),
            "family": launch["spec"]["family"],
            "command": launch["command"],
            "launch_pid": launch["launch_pid"],
            "returncode": launch["returncode"],
            "process_count_before": launch["process_count_before"],
            "process_count": len(launch["processes"]),
            "new_process_count": launch["new_process_count"],
            "processes": launch["processes"],
            "windows": launch["window_titles"],
            "window_name": matched_window.title if matched_window is not None else (launch["window_titles"][0] if launch["window_titles"] else ""),
            "window_handle": matched_window.hwnd if matched_window is not None else 0,
            "opened_target": matched_window is not None,
            "marker": IDE_WRITE_MARKER,
            "write_ok": marker_written,
            "write_transport": write_transport,
            "file_value": _read_text_lossy(resolved_target),
            "duration_seconds": launch["duration_seconds"],
            "detected_blockers": launch["detected_blockers"],
            "blockers": blockers,
        }
        if mcp_payload:
            payload["mcp_status"] = mcp_payload.get("status")
            payload["mcp_error"] = mcp_payload.get("error")
            for key in (
                "mcp_base_url",
                "mcp_project_path",
                "mcp_path_in_project",
                "mcp_open_files",
                "mcp_active_file_path",
                "mcp_used_tools",
                "mcp_tool_count",
                "marker_line",
                "marker_line_text",
                "line_ending",
                "changed",
            ):
                if key in mcp_payload:
                    payload[key] = mcp_payload[key]
        if probe_payload:
            payload["probe_status"] = probe_payload.get("status")
            payload["probe_transport"] = probe_payload.get("transport")
            payload["probe_error"] = probe_payload.get("error")
            for key in ("marker_line", "marker_line_text", "line_ending", "changed"):
                if key in probe_payload:
                    payload[key] = probe_payload[key]
        return payload

    def _plan_ide_write_pivots(raw_payload: dict[str, Any]):
        action_map = _metadata_secondary_profile_action_map(
            "ide-write",
            raw_payload=raw_payload,
            output_dir=output_dir,
            source=resolved_target,
            app_path=app_path,
            profile_chain=_profile_chain,
        )
        return build_pivot_attempts_from_actions(
            "ide-write",
            _finalize_payload("ide-write", dict(raw_payload)),
            action_map,
        )

    payload = run_with_strategy_pivots(
        profile="ide-write",
        preflight=[
            PreflightCheck(
                name="ide_write_source_exists",
                run=lambda: path_exists_check("ide_write_source_exists", str(resolved_target)),
            ),
            PreflightCheck(
                name="ide_write_app_exists",
                run=lambda: path_exists_check("ide_write_app_exists", str(app_path)),
            ),
        ],
        primary_attempts=[
            AttemptSpec(name="ide_write", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=_plan_ide_write_pivots,
    )
    payload["profile"] = "ide-write"
    payload = _finalize_payload("ide-write", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("ide-write", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "ide-write smoke failed"))
    return payload


def run_ide_workflow_smoke(
    *,
    target: Path,
    app_path: Path,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict[str, Any]:
    if current_platform() != "windows":
        raise RuntimeError("ide-workflow currently requires Windows.")

    resolved_target = target.expanduser().resolve()
    if not resolved_target.exists():
        raise FileNotFoundError(f"IDE target not found: {resolved_target}")

    if output_dir is None:
        output_dir = Path.cwd() / "smoke-output" / "ide-workflow"
    output_dir.mkdir(parents=True, exist_ok=True)

    def _attempt() -> dict[str, Any]:
        spec = _resolve_ide_spec(app_path)
        blockers: list[str] = []
        workflow_steps: list[dict[str, Any]] = []
        required_steps_total = 0
        required_steps_ok = 0
        workflow_tools_used: list[str] = []

        def _record_step(
            name: str,
            ok: bool,
            *,
            detail: str,
            required: bool = True,
            evidence: dict[str, Any] | None = None,
        ) -> None:
            nonlocal required_steps_total
            nonlocal required_steps_ok
            if required:
                required_steps_total += 1
                if ok:
                    required_steps_ok += 1
            workflow_steps.append(
                {
                    "name": name,
                    "ok": ok,
                    "required": required,
                    "detail": detail,
                    "evidence": evidence or {},
                }
            )
            if required and not ok:
                blockers.append(detail)

        if str(spec["family"]) != "jetbrains":
            payload = {
                "profile": "ide-workflow",
                "status": "blocked",
                "requested_target": str(resolved_target),
                "target": str(resolved_target),
                "family": spec["family"],
                "launcher_path": str(spec["launcher_path"]),
                "workflow_steps": workflow_steps,
                "required_steps_total": 0,
                "required_steps_ok": 0,
                "all_required_steps_ok": False,
                "blockers": ["deep IDE workflow currently requires a JetBrains MCP-capable IDE family"],
            }
            return payload

        project_root = _guess_jetbrains_project_root(resolved_target)
        workflow_probe_dir = project_root / "smoke-output" / "ide-workflow-probe"
        workflow_probe_dir.mkdir(parents=True, exist_ok=True)
        workflow_run_id = int(time.time() * 1000)
        probe_target = workflow_probe_dir / f"deep_probe_{workflow_run_id}.py"
        path_in_project = str(probe_target.relative_to(project_root))
        workflow_probe_dir_in_project = str(workflow_probe_dir.relative_to(project_root))
        symbol_name = "new_name"
        renamed_symbol_name = "new_name"
        initial_text = (
            f"def {symbol_name}(x:int)->int:\n"
            "    return x+1\n\n"
            f"value = {symbol_name}(2)\n"
        )
        workflow_marker = f"OmniControlIdeWorkflow{workflow_run_id}"
        marker_line_text = _render_ide_marker_line(probe_target, workflow_marker)

        def _wait_for_local_text(snippet: str, *, timeout: float) -> str:
            deadline = time.time() + timeout
            last_text = ""
            while time.time() < deadline:
                last_text = _read_text_lossy(probe_target)
                if snippet in last_text:
                    return last_text
                time.sleep(0.5)
            return _read_text_lossy(probe_target)

        def _wait_for_local_file(timeout: float) -> bool:
            deadline = time.time() + timeout
            while time.time() < deadline:
                if probe_target.exists():
                    return True
                time.sleep(0.25)
            return probe_target.exists()

        launch = _launch_ide_target(
            target=project_root,
            app_path=app_path,
            output_dir=output_dir,
            timeout=35.0,
        )
        blockers.extend(launch["detected_blockers"])
        if not launch["processes"]:
            blockers.append("ide process was not observed under the install root")
        if not launch["window_titles"]:
            blockers.append("ide window did not expose any visible title")

        matched_window = launch["matched_window"]
        if matched_window is None:
            blockers.append("ide window title did not expose the requested workspace")

        active_file_path: str | None = None
        open_files: list[str] = []
        read_text = ""
        renamed_text = ""
        final_text = ""
        symbol_info_documentation = ""
        symbol_info_declaration = ""
        rename_response_text = ""
        search_entries: list[dict[str, Any]] = []
        matching_files: list[str] = []
        directory_tree = ""
        directory_tree_errors: list[str] = []
        problems_count: int | None = None
        problems: list[dict[str, Any]] = []
        terminal_output = ""
        terminal_exit_code: int | None = None
        mcp_base_url = ""
        mcp_tool_count = 0
        read_ok = False
        symbol_info_ok = False
        rename_ok = False
        write_ok = False
        reformat_ok = False
        find_file_ok = False
        directory_tree_ok = False
        search_ok = False
        problems_ok = False
        terminal_ok = False
        terminal_marker = f"OMNI_JB_TERMINAL_{int(time.time() * 1000)}"
        workflow_exception: str | None = None

        try:
            with _open_jetbrains_mcp_session(app_path, timeout=15.0) as session:
                mcp_base_url = session.base_url
                tools = session.list_tools()
                available_tool_names = {str(tool.get("name") or "") for tool in tools if tool.get("name")}
                mcp_tool_count = len(tools)
                required_tools = {
                    "create_new_file",
                    "open_file_in_editor",
                    "get_file_text_by_path",
                    "get_symbol_info",
                    "rename_refactoring",
                    "replace_text_in_file",
                    "reformat_file",
                    "find_files_by_name_keyword",
                    "list_directory_tree",
                    "search_in_files_by_text",
                    "get_all_open_file_paths",
                    "get_file_problems",
                    "execute_terminal_command",
                }
                missing_tools = sorted(tool for tool in required_tools if tool not in available_tool_names)
                _record_step(
                    "tool_inventory",
                    not missing_tools,
                    detail="required JetBrains MCP tools are available" if not missing_tools else f"missing JetBrains MCP tools: {', '.join(missing_tools)}",
                    evidence={"available_tools": sorted(available_tool_names)},
                )
                if missing_tools:
                    raise RuntimeError(f"missing JetBrains MCP tools: {', '.join(missing_tools)}")

                create_payload = session.call_tool(
                    "create_new_file",
                    {
                        "pathInProject": path_in_project,
                        "text": initial_text,
                        "overwrite": True,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(create_payload, "create_new_file")
                workflow_tools_used.append("create_new_file")
                create_ok = _wait_for_local_file(3.0)
                _record_step(
                    "create_probe_file",
                    create_ok,
                    detail="created workflow probe file inside the project" if create_ok else "JetBrains MCP did not materialize the probe file on disk",
                    evidence={"path_in_project": path_in_project, "exists_on_disk": create_ok},
                )
                if not create_ok:
                    raise RuntimeError("JetBrains MCP create_new_file did not materialize the probe file on disk")
                time.sleep(0.5)

                open_payload = session.call_tool(
                    "open_file_in_editor",
                    {
                        "filePath": path_in_project,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(open_payload, "open_file_in_editor")
                workflow_tools_used.append("open_file_in_editor")
                open_files_payload = _wait_for_jetbrains_open_file(
                    session,
                    project_path=project_root,
                    path_in_project=path_in_project,
                    timeout=8.0,
                )
                open_files_result = _decode_mcp_tool_result(open_files_payload)
                if isinstance(open_files_result, dict):
                    active_file_path = open_files_result.get("activeFilePath")
                    listed_files = open_files_result.get("openFiles")
                    if isinstance(listed_files, list):
                        open_files = [str(item) for item in listed_files]
                open_ok = active_file_path == path_in_project or path_in_project in open_files
                _record_step(
                    "open_probe_file",
                    open_ok,
                    detail="opened probe file in the IDE editor" if open_ok else "IDE did not report the probe file as active or open",
                    evidence={"active_file_path": active_file_path, "open_files": open_files},
                )
                workflow_tools_used.append("get_all_open_file_paths")

                read_payload = session.call_tool(
                    "get_file_text_by_path",
                    {
                        "pathInProject": path_in_project,
                        "truncateMode": "NONE",
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(read_payload, "get_file_text_by_path")
                workflow_tools_used.append("get_file_text_by_path")
                read_text = _mcp_response_text(read_payload)
                read_ok = initial_text.replace("\r\n", "\n").strip() in read_text.replace("\r\n", "\n")
                _record_step(
                    "read_probe_file",
                    read_ok,
                    detail="read probe file text through JetBrains MCP" if read_ok else "JetBrains MCP did not return the expected probe content",
                    evidence={"text_preview": read_text[:200]},
                )

                symbol_payload = session.call_tool(
                    "get_symbol_info",
                    {
                        "filePath": path_in_project,
                        "line": 1,
                        "column": 5,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(symbol_payload, "get_symbol_info")
                workflow_tools_used.append("get_symbol_info")
                symbol_result = _decode_mcp_tool_result(symbol_payload)
                if isinstance(symbol_result, dict):
                    symbol_info_documentation = str(symbol_result.get("documentation") or "")
                    symbol_info = symbol_result.get("symbolInfo")
                    if isinstance(symbol_info, dict):
                        symbol_info_declaration = str(symbol_info.get("declarationText") or "")
                symbol_info_ok = symbol_name in symbol_info_documentation or symbol_name in symbol_info_declaration
                _record_step(
                    "inspect_symbol_info",
                    symbol_info_ok,
                    detail="retrieved symbol information through JetBrains MCP" if symbol_info_ok else "JetBrains MCP did not return the expected symbol documentation",
                    evidence={
                        "declaration_text": symbol_info_declaration[:200],
                        "documentation": symbol_info_documentation[:200],
                    },
                )

                rename_payload = session.call_tool(
                    "rename_refactoring",
                    {
                        "pathInProject": path_in_project,
                        "symbolName": symbol_name,
                        "newName": renamed_symbol_name,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(rename_payload, "rename_refactoring")
                workflow_tools_used.append("rename_refactoring")
                rename_response_text = _mcp_response_text(rename_payload)
                rename_deadline = time.time() + 5.0
                while time.time() < rename_deadline:
                    rename_read_payload = session.call_tool(
                        "get_file_text_by_path",
                        {
                            "pathInProject": path_in_project,
                            "truncateMode": "NONE",
                            "projectPath": str(project_root),
                        },
                    )
                    _raise_for_mcp_tool_error(rename_read_payload, "get_file_text_by_path")
                    workflow_tools_used.append("get_file_text_by_path")
                    renamed_text = _mcp_response_text(rename_read_payload)
                    rename_ok = renamed_symbol_name in renamed_text and symbol_name not in renamed_text
                    if rename_ok:
                        break
                    time.sleep(0.5)
                if not rename_ok:
                    renamed_text = _wait_for_local_text(renamed_symbol_name, timeout=3.0)
                    rename_ok = renamed_symbol_name in renamed_text and symbol_name not in renamed_text
                _record_step(
                    "rename_symbol",
                    rename_ok,
                    detail="renamed the probe symbol through JetBrains MCP" if rename_ok else "JetBrains MCP rename_refactoring did not update the probe symbol",
                    evidence={
                        "rename_response": rename_response_text[:200],
                        "text_preview": renamed_text[:200],
                    },
                )

                base_text_for_marker = (renamed_text or _read_text_lossy(probe_target)).replace("\r\n", "\n")
                updated_text = f"{base_text_for_marker.rstrip(chr(10))}\n{marker_line_text}\n"
                replace_payload = session.call_tool(
                    "replace_text_in_file",
                    {
                        "pathInProject": path_in_project,
                        "oldText": base_text_for_marker,
                        "newText": updated_text,
                        "replaceAll": False,
                        "caseSensitive": True,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(replace_payload, "replace_text_in_file")
                workflow_tools_used.append("replace_text_in_file")
                final_text = _wait_for_local_text(workflow_marker, timeout=3.0)
                write_ok = workflow_marker in final_text and renamed_symbol_name in final_text
                _record_step(
                    "append_workflow_marker",
                    write_ok,
                    detail="appended a workflow marker through JetBrains MCP" if write_ok else "JetBrains MCP replace_text_in_file did not persist the workflow marker",
                    evidence={"marker": workflow_marker, "text_preview": final_text[:200]},
                )

                reformat_payload = session.call_tool(
                    "reformat_file",
                    {
                        "path": path_in_project,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(reformat_payload, "reformat_file")
                workflow_tools_used.append("reformat_file")
                reformat_response_text = _mcp_response_text(reformat_payload)
                time.sleep(0.5)
                final_text = _read_text_lossy(probe_target)
                reformat_ok = workflow_marker in final_text and renamed_symbol_name in final_text
                _record_step(
                    "reformat_probe_file",
                    reformat_ok,
                    detail="reformatted the probe file through JetBrains MCP" if reformat_ok else "JetBrains MCP reformat_file did not preserve the renamed probe content",
                    evidence={
                        "reformat_response": reformat_response_text[:200],
                        "text_preview": final_text[:200],
                    },
                )

                find_payload = session.call_tool(
                    "find_files_by_name_keyword",
                    {
                        "nameKeyword": probe_target.stem,
                        "fileCountLimit": 20,
                        "timeout": 15000,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(find_payload, "find_files_by_name_keyword")
                workflow_tools_used.append("find_files_by_name_keyword")
                find_result = _decode_mcp_tool_result(find_payload)
                if isinstance(find_result, dict):
                    files = find_result.get("files")
                    if isinstance(files, list):
                        matching_files = [str(item) for item in files]
                normalized_probe_path = path_in_project.replace("\\", "/").lower()
                find_file_ok = any(
                    candidate.replace("\\", "/").lower() == normalized_probe_path
                    or candidate.replace("\\", "/").lower().endswith(f"/{probe_target.name.lower()}")
                    or candidate.replace("\\", "/").lower() == probe_target.name.lower()
                    for candidate in matching_files
                )
                _record_step(
                    "find_probe_file",
                    find_file_ok,
                    detail="located the probe file by name inside the IDE index" if find_file_ok else "JetBrains MCP file-name search did not find the probe file",
                    evidence={"files": matching_files[:20]},
                )

                directory_tree_payload = session.call_tool(
                    "list_directory_tree",
                    {
                        "directoryPath": workflow_probe_dir_in_project,
                        "maxDepth": 3,
                        "timeout": 15000,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(directory_tree_payload, "list_directory_tree")
                workflow_tools_used.append("list_directory_tree")
                directory_tree_result = _decode_mcp_tool_result(directory_tree_payload)
                if isinstance(directory_tree_result, dict):
                    directory_tree = str(directory_tree_result.get("tree") or "")
                    errors = directory_tree_result.get("errors")
                    if isinstance(errors, list):
                        directory_tree_errors = [str(item) for item in errors]
                directory_tree_ok = probe_target.name in directory_tree
                _record_step(
                    "list_probe_directory",
                    directory_tree_ok,
                    detail="listed the workflow probe directory through JetBrains MCP" if directory_tree_ok else "JetBrains MCP directory tree did not include the probe file",
                    evidence={
                        "tree_preview": directory_tree[:300],
                        "errors": directory_tree_errors[:10],
                    },
                )

                search_payload = session.call_tool(
                    "search_in_files_by_text",
                    {
                        "searchText": workflow_marker,
                        "directoryToSearch": workflow_probe_dir_in_project,
                        "maxUsageCount": 20,
                        "timeout": 15000,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(search_payload, "search_in_files_by_text")
                workflow_tools_used.append("search_in_files_by_text")
                search_result = _decode_mcp_tool_result(search_payload)
                if isinstance(search_result, dict):
                    entries = search_result.get("entries")
                    if isinstance(entries, list):
                        search_entries = [entry for entry in entries if isinstance(entry, dict)]
                search_ok = any(str(entry.get("filePath") or "") == path_in_project for entry in search_entries)
                _record_step(
                    "search_project_text",
                    search_ok,
                    detail="searched the project and found the workflow marker" if search_ok else "JetBrains MCP search did not find the workflow marker in the probe file",
                    evidence={"entries": search_entries[:5]},
                )

                time.sleep(0.5)
                problems_payload = session.call_tool(
                    "get_file_problems",
                    {
                        "filePath": path_in_project,
                        "errorsOnly": True,
                        "timeout": 15000,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(problems_payload, "get_file_problems")
                workflow_tools_used.append("get_file_problems")
                problems_result = _decode_mcp_tool_result(problems_payload)
                if isinstance(problems_result, dict):
                    errors = problems_result.get("errors")
                    if isinstance(errors, list):
                        problems = [item for item in errors if isinstance(item, dict)]
                problems_count = len(problems)
                problems_ok = problems_count == 0
                _record_step(
                    "inspect_file_problems",
                    problems_ok,
                    detail="PyCharm reported no file errors for the workflow probe" if problems_ok else f"PyCharm reported {problems_count} file errors for the workflow probe",
                    evidence={"problems": problems[:5]},
                )

                terminal_payload = session.call_tool(
                    "execute_terminal_command",
                    {
                        "command": f"cmd /c echo {terminal_marker}",
                        "timeout": 15000,
                        "maxLinesCount": 50,
                        "truncateMode": "END",
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(terminal_payload, "execute_terminal_command")
                workflow_tools_used.append("execute_terminal_command")
                terminal_result = _decode_mcp_tool_result(terminal_payload)
                if isinstance(terminal_result, dict):
                    terminal_output = str(terminal_result.get("command_output") or "")
                    exit_code = terminal_result.get("command_exit_code")
                    if isinstance(exit_code, int):
                        terminal_exit_code = exit_code
                terminal_ok = terminal_exit_code == 0 and terminal_marker in terminal_output
                _record_step(
                    "execute_terminal_command",
                    terminal_ok,
                    detail="executed a terminal command through the IDE" if terminal_ok else "IDE terminal command did not return the expected output",
                    evidence={"command_output": terminal_output, "command_exit_code": terminal_exit_code},
                )
        except Exception as exc:
            workflow_exception = str(exc)
            blockers.append(workflow_exception)

        blockers = dedupe_keep_order(blockers)
        all_required_steps_ok = workflow_exception is None and required_steps_total > 0 and required_steps_ok == required_steps_total
        workflow_tools_used = dedupe_keep_order(workflow_tools_used)
        payload = {
            "profile": "ide-workflow",
            "status": "ok" if all_required_steps_ok else "blocked",
            "requested_target": str(resolved_target),
            "target": str(probe_target),
            "target_kind": "file",
            "app_path": str(spec["app_path"]),
            "launcher_path": str(spec["launcher_path"]),
            "install_root": str(spec["install_root"]),
            "process_root": str(spec["process_root"]),
            "family": spec["family"],
            "command": launch["command"],
            "launch_pid": launch["launch_pid"],
            "returncode": launch["returncode"],
            "process_count_before": launch["process_count_before"],
            "process_count": len(launch["processes"]),
            "new_process_count": launch["new_process_count"],
            "processes": launch["processes"],
            "windows": launch["window_titles"],
            "window_name": matched_window.title if matched_window is not None else (launch["window_titles"][0] if launch["window_titles"] else ""),
            "window_handle": matched_window.hwnd if matched_window is not None else 0,
            "opened_target": active_file_path == path_in_project or path_in_project in open_files,
            "workflow_target": str(probe_target),
            "workflow_path_in_project": path_in_project,
            "workflow_probe_directory": workflow_probe_dir_in_project,
            "workflow_symbol_name": symbol_name,
            "workflow_renamed_symbol": renamed_symbol_name,
            "workflow_marker": workflow_marker,
            "workflow_tools_used": workflow_tools_used,
            "mcp_base_url": mcp_base_url,
            "mcp_tool_count": mcp_tool_count,
            "mcp_active_file_path": active_file_path,
            "mcp_open_files": open_files,
            "read_ok": read_ok,
            "read_preview": read_text[:200],
            "symbol_info_ok": symbol_info_ok,
            "symbol_info_declaration": symbol_info_declaration[:200],
            "symbol_info_preview": symbol_info_documentation[:200],
            "rename_ok": rename_ok,
            "rename_response": rename_response_text[:200],
            "renamed_preview": renamed_text[:200],
            "write_ok": write_ok,
            "reformat_ok": reformat_ok,
            "find_file_ok": find_file_ok,
            "matching_files": matching_files[:20],
            "directory_tree_ok": directory_tree_ok,
            "directory_tree_preview": directory_tree[:300],
            "directory_tree_errors": directory_tree_errors[:10],
            "search_ok": search_ok,
            "search_entries": search_entries[:10],
            "problems_ok": problems_ok,
            "problems_count": problems_count,
            "terminal_ok": terminal_ok,
            "terminal_exit_code": terminal_exit_code,
            "terminal_marker": terminal_marker,
            "terminal_output": terminal_output,
            "final_preview": final_text[:200],
            "required_steps_total": required_steps_total,
            "required_steps_ok": required_steps_ok,
            "all_required_steps_ok": all_required_steps_ok,
            "workflow_steps": workflow_steps,
            "duration_seconds": launch["duration_seconds"],
            "detected_blockers": launch["detected_blockers"],
            "blockers": blockers,
        }
        return payload

    payload = run_with_strategy_pivots(
        profile="ide-workflow",
        preflight=[
            PreflightCheck(
                name="ide_workflow_target_exists",
                run=lambda: path_exists_check("ide_workflow_target_exists", str(resolved_target)),
            ),
            PreflightCheck(
                name="ide_workflow_app_exists",
                run=lambda: path_exists_check("ide_workflow_app_exists", str(app_path)),
            ),
        ],
        primary_attempts=[
            AttemptSpec(name="ide_workflow", strategy="direct_script", run=_attempt),
        ],
        pivot_builder=lambda raw_payload: ([], []),
    )
    payload["profile"] = "ide-workflow"
    payload = _finalize_payload("ide-workflow", payload)
    report_path = output_dir / "result.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    payload = _record_payload("ide-workflow", payload)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "ide-workflow smoke failed"))
    return payload


def _resolve_ide_spec(app_path: Path) -> dict[str, Any]:
    resolved = app_path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"IDE app path not found: {resolved}")

    family = _detect_ide_family(resolved)
    if family is None:
        raise RuntimeError(f"Unsupported IDE family for path: {resolved}")

    install_root = _detect_ide_install_root(resolved)
    if family == "jetbrains":
        launcher_path = _resolve_jetbrains_launcher(resolved, install_root)
    else:
        launcher_path = _resolve_code_family_launcher(resolved, install_root)

    return {
        "family": family,
        "app_path": resolved,
        "install_root": install_root,
        "process_root": install_root,
        "launcher_path": launcher_path,
    }


def _detect_ide_family(app_path: Path) -> str | None:
    lowered_path = str(app_path).lower().replace("\\", "/")
    normalized_stem = _normalized_ide_stem(app_path)

    if app_path.is_dir():
        bin_dir = app_path / "bin"
        if (app_path / "product-info.json").exists() or (bin_dir / "inspect.bat").exists():
            return "jetbrains"
        if any((bin_dir / f"{stem}.cmd").exists() or (bin_dir / f"{stem}.exe").exists() for stem in CODE_IDE_STEMS):
            return "code_family"

    if normalized_stem in JETBRAINS_IDE_STEMS:
        return "jetbrains"
    if normalized_stem in CODE_IDE_STEMS:
        return "code_family"

    if app_path.parent.name.lower() == "bin":
        install_root = app_path.parent.parent
        if (install_root / "product-info.json").exists() or (app_path.parent / "inspect.bat").exists():
            return "jetbrains"
        if any((app_path.parent / f"{stem}.cmd").exists() for stem in CODE_IDE_STEMS):
            return "code_family"

    if any(stem in lowered_path for stem in JETBRAINS_IDE_STEMS):
        return "jetbrains"
    if any(stem in lowered_path for stem in CODE_IDE_STEMS):
        return "code_family"
    return None


def _detect_ide_install_root(app_path: Path) -> Path:
    if app_path.is_dir():
        return app_path
    if app_path.parent.name.lower() == "bin":
        return app_path.parent.parent
    return app_path.parent


def _resolve_jetbrains_launcher(app_path: Path, install_root: Path) -> Path:
    bin_dir = install_root / "bin"
    if app_path.is_file() and app_path.suffix.lower() in {".bat", ".cmd"}:
        return app_path

    candidates: list[Path] = []
    normalized_stem = _normalized_ide_stem(app_path)
    if normalized_stem:
        candidates.extend(
            [
                bin_dir / f"{normalized_stem}.bat",
                bin_dir / f"{normalized_stem}.cmd",
            ]
        )
    if app_path.is_dir():
        lowered_name = app_path.name.lower()
        for stem in JETBRAINS_IDE_STEMS:
            if stem in lowered_name:
                candidates.append(bin_dir / f"{stem}.bat")
    candidates.extend(
        sorted(
            path
            for path in [*bin_dir.glob("*.bat"), *bin_dir.glob("*.cmd")]
            if path.stem.lower() not in JETBRAINS_UTILITY_STEMS
        )
    )

    for candidate in _dedupe_paths(candidates):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not resolve a JetBrains launcher under: {bin_dir}")


def _resolve_code_family_launcher(app_path: Path, install_root: Path) -> Path:
    bin_dir = install_root / "bin"
    candidates = [
        *(bin_dir / f"{stem}.cmd" for stem in CODE_IDE_STEMS),
        *(bin_dir / f"{stem}.bat" for stem in CODE_IDE_STEMS),
        *(bin_dir / f"{stem}.exe" for stem in CODE_IDE_STEMS),
        *bin_dir.glob("*.cmd"),
        *bin_dir.glob("*.bat"),
        *bin_dir.glob("*.exe"),
    ]
    if app_path.is_file():
        candidates.append(app_path)
    for candidate in _dedupe_paths(candidates):
        if candidate.exists():
            return candidate
    if app_path.exists():
        return app_path
    raise FileNotFoundError(f"Could not resolve an IDE launcher under: {bin_dir}")


def _launch_ide_target(
    *,
    target: Path,
    app_path: Path,
    output_dir: Path,
    timeout: float,
    line: int | None = None,
    column: int | None = None,
) -> dict[str, Any]:
    spec = _resolve_ide_spec(app_path)
    target_tokens = _ide_target_tokens(target)
    before_processes = _list_processes_under_root(spec["process_root"])
    before_process_ids = [int(item["pid"]) for item in before_processes]
    before_windows = list_top_level_windows(
        process_ids=before_process_ids,
        visible_only=True,
    )
    user_data_dir = output_dir / "user-data" if spec["family"] == "code_family" else None
    if user_data_dir is not None:
        user_data_dir.mkdir(parents=True, exist_ok=True)
    command = _build_ide_open_command(
        family=str(spec["family"]),
        launcher_path=Path(spec["launcher_path"]),
        target=target,
        project_path=_ide_project_context(target, family=str(spec["family"])),
        isolated_user_data_dir=user_data_dir,
        line=line,
        column=column,
    )
    start = time.time()
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processes, windows, matched_window = _wait_for_ide_target_window(
        process_root=Path(spec["process_root"]),
        target_tokens=target_tokens,
        timeout=timeout,
        before_process_ids=before_process_ids,
        before_windows=before_windows,
    )
    duration_seconds = round(time.time() - start, 3)
    before_pids = {int(item["pid"]) for item in before_processes}
    after_pids = {int(item["pid"]) for item in processes}
    detected_blockers = _collect_ide_window_blockers(windows)
    if user_data_dir is not None:
        detected_blockers.extend(_collect_ide_log_blockers(user_data_dir))
        detected_blockers = dedupe_keep_order(detected_blockers)
    return {
        "spec": spec,
        "target_tokens": target_tokens,
        "command": command,
        "launch_pid": proc.pid,
        "returncode": proc.poll() if proc.poll() is not None else 0,
        "process_count_before": len(before_processes),
        "new_process_count": len(after_pids - before_pids),
        "processes": processes,
        "windows": windows,
        "window_titles": [window.title for window in windows if window.title],
        "matched_window": matched_window,
        "duration_seconds": duration_seconds,
        "detected_blockers": detected_blockers,
    }


def _build_ide_open_command(
    *,
    family: str,
    launcher_path: Path,
    target: Path,
    project_path: Path | None = None,
    isolated_user_data_dir: Path | None = None,
    line: int | None = None,
    column: int | None = None,
) -> list[str]:
    normalized_line = max(1, line) if line is not None else None
    normalized_column = max(1, column) if column is not None else None
    file_target = _is_probably_file_target(target)
    args: list[str] = []
    if family == "code_family":
        args.extend(["--new-window", "--disable-extensions"])
        if isolated_user_data_dir is not None:
            args.extend(["--user-data-dir", str(isolated_user_data_dir)])
        if file_target:
            goto_line = normalized_line or 1
            goto_column = normalized_column or 1
            args.extend(["--goto", _build_code_family_goto_target(target, goto_line, goto_column)])
        else:
            if project_path is not None:
                args.append(str(project_path))
            args.append(str(target))
    else:
        if project_path is not None:
            args.append(str(project_path))
        if normalized_line is not None:
            args.extend(["--line", str(normalized_line)])
            if normalized_column is not None:
                args.extend(["--column", str(normalized_column)])
        args.append(str(target))
    if launcher_path.suffix.lower() in {".bat", ".cmd"}:
        return ["cmd", "/c", str(launcher_path), *args]
    return [str(launcher_path), *args]


def _build_code_family_goto_target(target: Path, line: int, column: int | None) -> str:
    suffix = f":{line}"
    if column is not None:
        suffix += f":{column}"
    return f"{target}{suffix}"


def _wait_for_ide_target_window(
    *,
    process_root: Path,
    target_tokens: list[str],
    timeout: float,
    before_process_ids: list[int] | None = None,
    before_windows: list[TopLevelWindowInfo] | None = None,
) -> tuple[list[dict[str, Any]], list[TopLevelWindowInfo], TopLevelWindowInfo | None]:
    deadline = time.time() + timeout
    last_processes: list[dict[str, Any]] = []
    last_windows: list[TopLevelWindowInfo] = []
    while time.time() < deadline:
        processes = _list_processes_under_root(process_root)
        windows = list_top_level_windows(
            process_ids=[int(item["pid"]) for item in processes],
            visible_only=True,
        )
        matched = _select_ide_target_window(
            windows,
            target_tokens,
            before_process_ids=before_process_ids,
            before_windows=before_windows,
        )
        if matched is not None:
            return processes, windows, matched
        last_processes = processes
        last_windows = windows
        time.sleep(0.5)
    return last_processes, last_windows, None


def _list_processes_under_root(root: Path) -> list[dict[str, Any]]:
    escaped_root = str(root).replace("'", "''")
    script = f"""
$root = [System.IO.Path]::GetFullPath('{escaped_root}')
$items = Get-CimInstance Win32_Process |
  Where-Object {{
    $_.ExecutablePath -and
    ([System.IO.Path]::GetFullPath($_.ExecutablePath)).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)
  }} |
  Select-Object @{{n='pid';e={{$_.ProcessId}}}},
                @{{n='name';e={{$_.Name}}}},
                @{{n='path';e={{$_.ExecutablePath}}}},
                @{{n='command_line';e={{$_.CommandLine}}}}
if ($items) {{ $items | ConvertTo-Json -Depth 4 -Compress }}
"""
    return _powershell_json_list(script)


def _powershell_json_list(script: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = (result.stdout or "").strip()
    if not stdout:
        return []
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return [payload]


def _ide_target_tokens(target: Path) -> list[str]:
    is_probably_file = _is_probably_file_target(target)
    tokens = [target.name]
    if is_probably_file:
        tokens.append(target.parent.name)
    else:
        tokens.append(display_name_from_target(str(target)))
    return [token for token in dedupe_keep_order([item for item in tokens if item]) if len(token) >= 2]


def _ide_window_matches_target(title: str, target_tokens: list[str]) -> bool:
    lowered_title = title.lower()
    if not target_tokens:
        return False
    if target_tokens[0].lower() not in lowered_title:
        return False
    if len(target_tokens) == 1:
        return True
    return all(token.lower() in lowered_title for token in target_tokens[1:])


def _select_ide_target_window(
    windows: list[TopLevelWindowInfo],
    target_tokens: list[str],
    *,
    before_process_ids: list[int] | None = None,
    before_windows: list[TopLevelWindowInfo] | None = None,
) -> TopLevelWindowInfo | None:
    baseline_process_ids = {int(item) for item in (before_process_ids or [])}
    baseline_hwnds = {int(window.hwnd) for window in (before_windows or [])}
    scored_candidates: list[tuple[int, bool, TopLevelWindowInfo]] = []
    for window in windows:
        if not window.title:
            continue
        score = _ide_window_match_score(window.title, target_tokens)
        if score > 0:
            is_new_window = window.hwnd not in baseline_hwnds or window.process_id not in baseline_process_ids
            scored_candidates.append((score, is_new_window, window))
    if not scored_candidates:
        return None
    fresh_candidates = [item for item in scored_candidates if item[1]]
    candidate_pool = fresh_candidates or scored_candidates
    contextual_candidates = [item for item in candidate_pool if item[0] > 1]
    if contextual_candidates:
        contextual_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return contextual_candidates[0][2]
    if len(candidate_pool) == 1:
        return candidate_pool[0][2]
    return None


def _ide_window_match_score(title: str, target_tokens: list[str]) -> int:
    lowered_title = title.lower()
    if not target_tokens:
        return 0
    if target_tokens[0].lower() not in lowered_title:
        return 0
    score = 1
    for token in target_tokens[1:]:
        if token.lower() in lowered_title:
            score += 1
    return score


def _ide_project_context(target: Path, *, family: str) -> Path | None:
    if _is_probably_file_target(target):
        if family == "jetbrains":
            return None
        return target.parent
    return None


def _collect_ide_window_blockers(windows: list[TopLevelWindowInfo]) -> list[str]:
    labels = [window.title for window in windows if window.title]
    for window in windows:
        if window.hwnd:
            labels.extend(_ide_window_descendant_names(window.hwnd))
    return _detect_ide_blockers(labels)


def _collect_ide_log_blockers(user_data_dir: Path) -> list[str]:
    log_root = user_data_dir / "logs"
    if not log_root.exists():
        return []
    blockers: list[str] = []
    for log_path in sorted(log_root.glob("*/main.log"), reverse=True):
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        for pattern, reason in IDE_LOG_BLOCKER_PATTERNS.items():
            if pattern in log_text:
                blockers.append(reason)
    return dedupe_keep_order(blockers)


def _detect_ide_blockers(labels: list[str]) -> list[str]:
    lowered_labels = [label.lower() for label in labels if label]
    blockers: list[str] = []
    for pattern, reason in IDE_BLOCKER_PATTERNS.items():
        if any(pattern in label for label in lowered_labels):
            blockers.append(reason)
    return dedupe_keep_order(blockers)


def _ide_window_descendant_names(hwnd: int) -> list[str]:
    script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::NativeWindowHandleProperty,
  {int(hwnd)}
)
$window = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
if ($null -eq $window) {{ return }}
$items = @()
$desc = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
for ($i = 0; $i -lt [Math]::Min($desc.Count, 80); $i++) {{
  $el = $desc.Item($i)
  if ($el.Current.Name) {{
    $items += [pscustomobject]@{{ name = $el.Current.Name }}
  }}
}}
if ($items) {{ $items | ConvertTo-Json -Depth 3 -Compress }}
"""
    return [str(item.get("name") or "") for item in _powershell_json_list(script) if item.get("name")]


def _apply_jetbrains_mcp_file_write(*, target: Path, app_path: Path, marker: str) -> dict[str, Any]:
    project_root = _guess_jetbrains_project_root(target)
    try:
        path_in_project = str(target.relative_to(project_root))
    except ValueError:
        return {
            "status": "error",
            "transport": "jetbrains_mcp",
            "error": f"target is outside the inferred project root: {project_root}",
        }

    original = _read_text_lossy(target)
    line_ending = _detect_line_ending(original)
    marker_line_text = _render_ide_marker_line(target, marker)
    if marker in original:
        updated = original
        changed = False
    else:
        separator = "" if not original or original.endswith(("\r\n", "\n")) else line_ending
        updated = f"{original}{separator}{marker_line_text}{line_ending}"
        changed = True

    last_error = "JetBrains MCP server was not reachable."
    for base_url in _candidate_jetbrains_mcp_base_urls(app_path):
        try:
            with _JetBrainsMcpSession(base_url=base_url, timeout=10.0) as session:
                tools = [str(tool.get("name") or "") for tool in session.list_tools() if tool.get("name")]
                open_payload = session.call_tool(
                    "open_file_in_editor",
                    {
                        "filePath": path_in_project,
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(open_payload, "open_file_in_editor")
                if changed:
                    replace_payload = session.call_tool(
                        "replace_text_in_file",
                        {
                            "pathInProject": path_in_project,
                            "oldText": original,
                            "newText": updated,
                            "replaceAll": False,
                            "caseSensitive": True,
                            "projectPath": str(project_root),
                        },
                    )
                    _raise_for_mcp_tool_error(replace_payload, "replace_text_in_file")
                read_payload = session.call_tool(
                    "get_file_text_by_path",
                    {
                        "pathInProject": path_in_project,
                        "truncateMode": "NONE",
                        "projectPath": str(project_root),
                    },
                )
                _raise_for_mcp_tool_error(read_payload, "get_file_text_by_path")
                readback_text = _mcp_response_text(read_payload)
                open_files_payload = session.call_tool(
                    "get_all_open_file_paths",
                    {"projectPath": str(project_root)},
                )
                _raise_for_mcp_tool_error(open_files_payload, "get_all_open_file_paths")
                open_files = _decode_mcp_tool_result(open_files_payload)
                open_files_list = []
                active_file_path = None
                if isinstance(open_files, dict):
                    active_file_path = open_files.get("activeFilePath")
                    listed = open_files.get("openFiles")
                    if isinstance(listed, list):
                        open_files_list = [str(item) for item in listed]
                marker_written = marker in readback_text or _wait_for_file_marker(target, marker, timeout=2.0)
                return {
                    "status": "ok" if marker_written else "error",
                    "transport": "jetbrains_mcp",
                    "mcp_base_url": base_url,
                    "mcp_project_path": str(project_root),
                    "mcp_path_in_project": path_in_project,
                    "mcp_used_tools": [
                        "open_file_in_editor",
                        *([] if not changed else ["replace_text_in_file"]),
                        "get_file_text_by_path",
                        "get_all_open_file_paths",
                    ],
                    "mcp_tool_count": len(tools),
                    "mcp_active_file_path": active_file_path,
                    "mcp_open_files": open_files_list,
                    "changed": changed,
                    "line_ending": "crlf" if line_ending == "\r\n" else "lf",
                    "marker_line_text": marker_line_text,
                    "marker_line": _find_marker_line(readback_text or updated, marker),
                    "error": None if marker_written else "JetBrains MCP write did not persist the marker.",
                }
        except Exception as exc:
            last_error = str(exc)
    return {
        "status": "error",
        "transport": "jetbrains_mcp",
        "error": last_error,
    }


@contextmanager
def _open_jetbrains_mcp_session(app_path: Path, *, timeout: float):
    last_error = "JetBrains MCP server was not reachable."
    for base_url in _candidate_jetbrains_mcp_base_urls(app_path):
        try:
            with _JetBrainsMcpSession(base_url=base_url, timeout=timeout) as session:
                yield session
                return
        except Exception as exc:
            last_error = str(exc)
    raise RuntimeError(last_error)


class _JetBrainsMcpSession:
    def __init__(self, *, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._endpoint_url: str | None = None
        self._stream: Any = None
        self._next_id = 1

    def __enter__(self) -> "_JetBrainsMcpSession":
        self._stream = urlopen(
            Request(f"{self.base_url}/sse", headers={"Accept": "text/event-stream"}),
            timeout=self.timeout,
        )
        endpoint = None
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            event = self._read_event()
            if event is None:
                break
            if event["event"] == "endpoint" and event["data"].startswith("/"):
                endpoint = event["data"]
                break
        if endpoint is None:
            raise RuntimeError(f"JetBrains MCP SSE endpoint was not announced by {self.base_url}")
        self._endpoint_url = f"{self.base_url}{endpoint}"
        init_response = self._request(
            "initialize",
            {
                "protocolVersion": JETBRAINS_MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "OmniControl",
                    "version": "0.1",
                },
            },
        )
        if "error" in init_response:
            raise RuntimeError(str(init_response["error"]))
        self._post_json({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._stream is not None:
            try:
                self._stream.close()
            except OSError:
                pass
        self._stream = None
        self._endpoint_url = None

    def list_tools(self) -> list[dict[str, Any]]:
        response = self._request("tools/list", {})
        result = response.get("result")
        if not isinstance(result, dict):
            return []
        tools = result.get("tools")
        if isinstance(tools, list):
            return [tool for tool in tools if isinstance(tool, dict)]
        return []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_request_id()
        self._post_json(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        response = self._wait_for_response(request_id)
        if not isinstance(response, dict):
            raise RuntimeError(f"JetBrains MCP returned a non-dict response for {method}")
        return response

    def _next_request_id(self) -> int:
        current = self._next_id
        self._next_id += 1
        return current

    def _post_json(self, payload: dict[str, Any]) -> None:
        if self._endpoint_url is None:
            raise RuntimeError("JetBrains MCP endpoint is not initialized.")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._endpoint_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            response.read()

    def _wait_for_response(self, request_id: int) -> dict[str, Any]:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            event = self._read_event()
            if event is None:
                break
            if event["event"] != "message":
                continue
            try:
                payload = json.loads(event["data"])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("id") == request_id:
                return payload
        raise RuntimeError(f"Timed out waiting for JetBrains MCP response {request_id}.")

    def _read_event(self) -> dict[str, str] | None:
        if self._stream is None:
            return None
        event_type = "message"
        data_lines: list[str] = []
        while True:
            raw_line = self._stream.readline()
            if not raw_line:
                return None
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line == "":
                return {
                    "event": event_type,
                    "data": "\n".join(data_lines),
                }
            if line.startswith("event: "):
                event_type = line[len("event: ") :]
            elif line.startswith("data: "):
                data_lines.append(line[len("data: ") :])


def _wait_for_jetbrains_open_file(
    session: _JetBrainsMcpSession,
    *,
    project_path: Path,
    path_in_project: str,
    timeout: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_payload: dict[str, Any] = {"result": {"structuredContent": {"activeFilePath": None, "openFiles": []}}}
    while time.time() < deadline:
        payload = session.call_tool(
            "get_all_open_file_paths",
            {"projectPath": str(project_path)},
        )
        last_payload = payload
        result = _decode_mcp_tool_result(payload)
        if isinstance(result, dict):
            active = result.get("activeFilePath")
            open_files = result.get("openFiles")
            if active == path_in_project:
                return payload
            if isinstance(open_files, list) and path_in_project in [str(item) for item in open_files]:
                return payload
        time.sleep(0.5)
    return last_payload


def _candidate_jetbrains_mcp_base_urls(app_path: Path) -> list[str]:
    return [f"http://127.0.0.1:{port}" for port in _candidate_jetbrains_mcp_ports(app_path)]


def _candidate_jetbrains_mcp_ports(app_path: Path) -> list[int]:
    ports = [JETBRAINS_MCP_DEFAULT_PORT]
    for config_path in _jetbrains_mcp_config_paths(app_path):
        port = _extract_jetbrains_mcp_port(config_path)
        if port is not None:
            ports.insert(0, port)
    return [int(port) for port in dedupe_keep_order(ports)]


def _jetbrains_mcp_config_paths(app_path: Path) -> list[Path]:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    jetbrains_root = Path(appdata) / "JetBrains"
    if not jetbrains_root.exists():
        return []
    search_tokens = {
        _normalized_ide_stem(app_path),
        _detect_ide_install_root(app_path).name.lower(),
    }
    configs: list[Path] = []
    for config_dir in jetbrains_root.iterdir():
        lowered_name = config_dir.name.lower()
        if not any(token and token in lowered_name for token in search_tokens):
            continue
        config_path = config_dir / "options" / "mcpServer.xml"
        if config_path.exists():
            configs.append(config_path)
    return sorted(configs, reverse=True)


def _extract_jetbrains_mcp_port(config_path: Path) -> int | None:
    try:
        root = ET.fromstring(config_path.read_text(encoding="utf-8"))
    except (ET.ParseError, OSError):
        return None
    component = None
    for candidate in root.findall("component"):
        if candidate.attrib.get("name") == JETBRAINS_MCP_COMPONENT_NAME:
            component = candidate
            break
    if component is None:
        return None
    enabled = None
    port = None
    for option in component.findall("option"):
        name = option.attrib.get("name")
        value = option.attrib.get("value")
        if name == "enableMcpServer":
            enabled = str(value).lower() == "true"
        if name == "mcpServerPort":
            try:
                port = int(str(value))
            except (TypeError, ValueError):
                port = None
    if enabled is False:
        return None
    return port


def _guess_jetbrains_project_root(target: Path) -> Path:
    cwd = Path.cwd().resolve()
    try:
        target.relative_to(cwd)
    except ValueError:
        return target.parent
    return cwd


def _raise_for_mcp_tool_error(response: dict[str, Any], tool_name: str) -> None:
    if "error" in response:
        raise RuntimeError(f"JetBrains MCP {tool_name} failed: {response['error']}")
    result = response.get("result")
    if isinstance(result, dict) and result.get("isError"):
        detail = _mcp_response_text(response)
        if detail:
            raise RuntimeError(f"JetBrains MCP {tool_name} failed: {detail}")
        raise RuntimeError(f"JetBrains MCP {tool_name} failed.")


def _decode_mcp_tool_result(response: dict[str, Any]) -> Any:
    result = response.get("result")
    if not isinstance(result, dict):
        return response
    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    text = _mcp_response_text(response)
    if not text:
        return result
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _mcp_response_text(response: dict[str, Any]) -> str:
    result = response.get("result")
    if not isinstance(result, dict):
        return ""
    parts: list[str] = []
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in parts if part)


def _apply_safe_ide_file_write(*, target: Path, marker: str) -> dict[str, Any]:
    try:
        original = _read_text_lossy(target)
        line_ending = _detect_line_ending(original)
        updated = original
        if marker not in original:
            marker_line_text = _render_ide_marker_line(target, marker)
            separator = "" if not original or original.endswith(("\r\n", "\n")) else line_ending
            updated = f"{original}{separator}{marker_line_text}{line_ending}"
            target.write_text(updated, encoding="utf-8")
            changed = True
        else:
            marker_line_text = _render_ide_marker_line(target, marker)
            changed = False
        return {
            "status": "ok",
            "transport": "file_format",
            "changed": changed,
            "line_ending": "crlf" if line_ending == "\r\n" else "lf",
            "marker_line_text": marker_line_text,
            "marker_line": _find_marker_line(updated, marker),
        }
    except Exception as exc:  # pragma: no cover - defensive filesystem edge
        return {
            "status": "error",
            "transport": "file_format",
            "error": str(exc),
        }


def _detect_line_ending(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    return "\n"


def _find_marker_line(text: str, marker: str) -> int:
    for index, line in enumerate(text.splitlines(), start=1):
        if marker in line:
            return index
    return 1


def _render_ide_marker_line(target: Path, marker: str) -> str:
    suffix = target.suffix.lower()
    if suffix in IDE_HASH_COMMENT_SUFFIXES:
        return f"# {marker}"
    if suffix in IDE_SLASH_COMMENT_SUFFIXES:
        return f"// {marker}"
    if suffix in IDE_BLOCK_COMMENT_SUFFIXES:
        return f"/* {marker} */"
    if suffix in IDE_XML_COMMENT_SUFFIXES:
        return f"<!-- {marker} -->"
    if suffix in {".cmd", ".bat"}:
        return f"REM {marker}"
    return marker
def _wait_for_file_marker(path: Path, marker: str, *, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if marker in _read_text_lossy(path):
            return True
        time.sleep(0.5)
    return marker in _read_text_lossy(path)


def _read_text_lossy(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _is_probably_file_target(target: Path) -> bool:
    return target.is_file() or bool(target.suffix)


def _normalized_ide_stem(path: Path) -> str:
    stem = path.stem.lower()
    return re.sub(r"64$", "", stem)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


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


def _persist_payload(profile: str, payload: dict[str, Any], report_dir: Path) -> dict[str, Any]:
    payload = _finalize_payload(profile, payload)
    payload = write_result_bundle(
        profile,
        payload,
        report_dir=report_dir,
        runtime_paths=resolve_runtime_paths(),
    )
    return _record_payload(profile, payload)


def run_finder_open_smoke(
    *,
    target_path: Path | None,
    output_dir: Path | None,
) -> dict:
    _require_macos("finder-open")
    if output_dir is None:
        output_dir = _default_output_dir("finder-open")
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _run_osascript_profile(
        "finder_open_smoke.applescript",
        args=[str(target_path)] if target_path is not None else [],
    )
    payload["profile"] = "finder-open"
    payload = _persist_payload("finder-open", payload, output_dir)
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
        output_dir = _default_output_dir("safari-open")
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _run_osascript_profile(
        "safari_open_smoke.applescript",
        args=[url] if url else [],
    )
    payload["profile"] = "safari-open"
    payload = _persist_payload("safari-open", payload, output_dir)
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
        output_dir = _default_output_dir("safari-dom-write")
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
    payload = _persist_payload("safari-dom-write", payload, output_dir)
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
        raise FileNotFoundError(f"Word application not found: {word_path}")
    if current_platform() == "macos":
        return _run_word_export_smoke_macos(
            source=source,
            output_pdf=output_pdf,
            word_path=word_path,
        )

    output_pdf = _default_output_file("word-export", f"{source.stem}-export.pdf", output_pdf)
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
    payload["command"] = command
    payload["returncode"] = result.returncode
    payload = _persist_payload("word-export", payload, output_pdf.parent)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "word-export smoke failed"))
    return payload


def run_word_write_smoke(
    *,
    output_docx: Path | None,
    word_path: Path,
) -> dict:
    if not word_path.exists():
        raise FileNotFoundError(f"Word application not found: {word_path}")
    if current_platform() == "macos":
        return _run_word_write_smoke_macos(
            output_docx=output_docx,
            word_path=word_path,
        )
    if output_docx is None:
        output_docx = _default_output_file("word-write", "word-write-smoke.docx")
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
    payload["command"] = command
    payload["returncode"] = result.returncode
    payload = _persist_payload("word-write", payload, output_docx.parent)
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
        raise FileNotFoundError(f"Word application not found: {word_path}")
    if current_platform() == "macos":
        return _run_word_workflow_smoke_macos(
            output_dir=output_dir,
            word_path=word_path,
            _profile_chain=_profile_chain,
        )
    if output_dir is None:
        output_dir = _default_output_dir("word-workflow")
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
    payload = _persist_payload("word-workflow", payload, output_dir)
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
        output_dir = _default_output_dir("chrome-cdp")
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
        payload = _persist_payload("chrome-cdp", payload, output_dir)
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
        output_dir = _default_output_dir("chrome-form-write")
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
    payload = _persist_payload("chrome-form-write", payload, output_dir)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "chrome-form-write smoke failed"))
    return payload


def run_everything_search_smoke(
    *,
    query: str,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("everything-search")
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
    payload["command"] = command
    payload["returncode"] = result.returncode
    payload = _persist_payload("everything-search", payload, output_dir)
    if result.returncode != 0:
        raise RuntimeError(payload.get("error", "everything-search smoke failed"))
    return payload


def run_illustrator_export_smoke(
    *,
    output_path: Path | None,
) -> dict:
    if output_path is None:
        output_path = _default_output_file("illustrator-export", "illustrator-smoke.svg")
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
    payload["command"] = command
    payload["returncode"] = result.returncode
    payload = _persist_payload("illustrator-export", payload, output_path.parent)
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
        output_dir = _default_output_dir("masterpdf-pagedown")
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
    payload["command"] = command
    payload["returncode"] = result.returncode
    payload = _persist_payload("masterpdf-pagedown", payload, output_dir)
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
        output_dir = _default_output_dir(app_label)
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
        payload["command"] = node_command
        payload["launch_command"] = command
        payload["port"] = port
        payload["returncode"] = result.returncode
        payload = _persist_payload(app_label, payload, output_dir)
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
        output_dir = _default_output_dir("quark-cdp")
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
        payload["command"] = command
        payload["returncode"] = result.returncode
        payload = _persist_payload("quark-cdp", payload, output_dir)
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
        output_dir = _default_output_dir("quark-cdp-write")
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
    payload = _persist_payload("quark-cdp-write", payload, output_dir)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "quark-cdp-write smoke failed"))
    return payload


def run_trae_open_smoke(
    *,
    workspace: Path,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("trae-open")
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
    payload["command"] = [str(trae_cli), "-n", "--user-data-dir", startup.user_data_dir or "", str(workspace)]
    payload["returncode"] = 0
    payload = _persist_payload("trae-open", payload, output_dir)
    cleanup_process_group("Trae")
    return payload


def run_trae_cdp_write_smoke(
    *,
    workspace: Path,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("trae-cdp-write")
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
    payload = _persist_payload("trae-cdp-write", payload, output_dir)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "trae-cdp-write smoke failed"))
    return payload


def run_nx_diagnose_smoke(
    *,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("nx-diagnose")
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
    payload = _persist_payload("nx-diagnose", payload, output_dir)
    return payload


def run_isight_diagnose_smoke(
    *,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("isight-diagnose")
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
    payload = _persist_payload("isight-diagnose", payload, output_dir)
    return payload


def run_ue_diagnose_smoke(
    *,
    output_dir: Path | None,
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("ue-diagnose")
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
    payload = _persist_payload("ue-diagnose", payload, output_dir)
    return payload


def run_ue_python_write_smoke(
    *,
    output_dir: Path | None,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("ue-python-write")
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
    payload = _persist_payload("ue-python-write", payload, output_dir)
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
        output_dir = _default_output_dir("cadv-view")
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
    payload["command"] = command
    payload["returncode"] = result.returncode
    payload = _persist_payload("cadv-view", payload, output_dir)
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
        output_dir = _default_output_dir(profile)
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
    payload = _persist_payload(profile, payload, output_dir)
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
        output_dir = _default_output_dir(profile)
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
    payload = _persist_payload(profile, payload, output_dir)
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
        output_dir = _default_output_dir(profile)
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
    payload = _persist_payload(profile, payload, output_dir)
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
    app_path: Path | None = None,
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
                app_path=app_path,
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
    app_path: Path | None = None,
    query: str | None = None,
    url: str | None = None,
) -> dict[str, str]:
    kwargs: dict[str, str] = {}
    if app_path is not None:
        kwargs["app_path"] = str(app_path)
    source_arg = spec.get("source_arg")
    if source_arg == "source":
        if source is not None:
            kwargs["source"] = str(source)
        return kwargs
    if source_arg == "workspace":
        if workspace is not None:
            kwargs["source"] = str(workspace)
        return kwargs
    if source_arg == "query":
        if query is not None:
            kwargs["query"] = query
        return kwargs
    if source_arg == "url":
        if url is not None:
            kwargs["url"] = url
        return kwargs
    return kwargs


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
        output_dir = _default_output_dir("qqmusic-play")
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
    payload = _persist_payload("qqmusic-play", payload, output_dir)
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
    if current_platform() == "macos":
        candidates = [
            DEFAULT_WORD_MACOS_PATH,
            Path.home() / "Applications" / "Microsoft Word.app",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return DEFAULT_WORD_MACOS_PATH

    candidates = [DEFAULT_WORD_PATH]
    candidates.extend(_app_paths_registry_values("WINWORD.EXE"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DEFAULT_WORD_PATH


def _run_word_export_smoke_macos(
    *,
    source: Path,
    output_pdf: Path | None,
    word_path: Path,
) -> dict:
    output_pdf = _default_output_file("word-export", f"{source.stem}-export.pdf", output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    payload = _run_osascript_profile(
        "word_export_smoke_macos.applescript",
        args=[str(source), str(output_pdf), str(word_path)],
    )
    payload["profile"] = "word-export"
    payload["output"] = str(output_pdf)
    payload["source"] = str(source)
    payload["word_path"] = str(word_path)
    payload.update(_pdf_output_details(output_pdf))
    payload = _persist_payload("word-export", payload, output_pdf.parent)
    if payload.get("returncode", 0) != 0 or payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "word-export smoke failed"))
    return payload


def _run_word_write_smoke_macos(
    *,
    output_docx: Path | None,
    word_path: Path,
) -> dict:
    if output_docx is None:
        output_docx = _default_output_file("word-write", "word-write-smoke.docx")
    output_docx.parent.mkdir(parents=True, exist_ok=True)

    payload = _run_osascript_profile(
        "word_write_smoke_macos.applescript",
        args=[str(output_docx), str(word_path)],
    )
    payload["profile"] = "word-write"
    payload["output"] = str(output_docx)
    payload["word_path"] = str(word_path)
    payload.update(_docx_output_details(output_docx))
    payload = _persist_payload("word-write", payload, output_docx.parent)
    if payload.get("returncode", 0) != 0 or payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "word-write smoke failed"))
    return payload


def _run_word_workflow_smoke_macos(
    *,
    output_dir: Path | None,
    word_path: Path,
    _profile_chain: tuple[str, ...] = (),
) -> dict:
    if output_dir is None:
        output_dir = _default_output_dir("word-workflow")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_docx = output_dir / "word-workflow.docx"

    def _attempt() -> dict[str, Any]:
        payload = _run_osascript_profile(
            "word_workflow_smoke_macos.applescript",
            args=[str(output_dir), str(word_path)],
        )
        payload["output_docx"] = str(output_docx)
        payload["word_path"] = str(word_path)
        payload.update(_workflow_docx_details(output_docx))
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
            AttemptSpec(name="word_workflow_macos", strategy="native_script", run=_attempt),
        ],
        pivot_builder=_plan_word_workflow_pivots,
    )
    payload["profile"] = "word-workflow"
    payload["output_docx"] = str(output_docx)
    payload["word_path"] = str(word_path)
    payload.update(_workflow_docx_details(output_docx))
    payload = _persist_payload("word-workflow", payload, output_dir)
    if payload.get("status") not in {"ok", "partial", "blocked"}:
        raise RuntimeError(payload.get("error", "word-workflow smoke failed"))
    return payload


def _docx_output_details(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {"exists": path.exists()}
    if not path.exists():
        return payload
    data = path.read_bytes()
    payload["size"] = len(data)
    payload["magic"] = "-".join(f"{byte:02X}" for byte in data[:4])
    payload["zip_ok"] = data[:4] == b"PK\x03\x04"
    return payload


def _pdf_output_details(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {"exists": path.exists()}
    if not path.exists():
        return payload
    data = path.read_bytes()
    payload["size"] = len(data)
    payload["magic"] = data[:5].decode("ascii", errors="replace")
    payload["magic_ok"] = data[:5] == b"%PDF-"
    return payload


def _workflow_docx_details(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "docx_exists": path.exists(),
        "output_docx": str(path),
    }
    if not path.exists():
        return payload
    data = path.read_bytes()
    payload["docx_size"] = len(data)
    payload["docx_magic"] = "-".join(f"{byte:02X}" for byte in data[:4])
    payload["docx_zip_ok"] = data[:4] == b"PK\x03\x04"
    try:
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    except (KeyError, OSError, zipfile.BadZipFile):
        payload["body_markers_ok"] = False
        return payload
    payload["body_markers_ok"] = (
        "OmniControl Word Workflow" in document_xml
        and "Step 1: body write" in document_xml
        and "Step 2:" in document_xml
    )
    return payload


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
