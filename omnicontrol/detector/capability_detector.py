from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
import json

from omnicontrol.models import Capability, DetectionResult, display_name_from_target, normalize_platform


DOCUMENT_EXTENSIONS = {
    ".docx",
    ".xlsx",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".svg",
    ".html",
    ".md",
}


KNOWN_HINTS = {
    "office": ("native_script", 0.88, "Office apps often expose native scripting or automation entrypoints."),
    "excel": ("native_script", 0.90, "Excel commonly exposes COM or native scripting surfaces."),
    "word": ("native_script", 0.90, "Word commonly exposes COM or native scripting surfaces."),
    "powerpoint": ("native_script", 0.90, "PowerPoint commonly exposes COM or native scripting surfaces."),
    "photoshop": ("native_script", 0.90, "Photoshop commonly exposes official scripting surfaces."),
    "illustrator": ("plugin", 0.88, "Illustrator is often better served by plugin and scripting surfaces."),
    "electron": ("cdp", 0.92, "Electron targets are usually best approached through CDP."),
    "chrome": ("cdp", 0.94, "Chromium-family targets are usually best approached through CDP."),
    "browser": ("cdp", 0.90, "Browser targets usually justify a CDP-first plan."),
}


NEED_HINTS = {
    "browser": ("cdp", 0.92, "Browser automation needs align with CDP."),
    "dom": ("cdp", 0.94, "DOM-facing needs align with CDP and the Node ecosystem."),
    "network": ("cdp", 0.90, "Network-facing browser work aligns with CDP."),
    "api": ("api", 0.90, "The task explicitly mentions an API surface."),
    "http": ("api", 0.88, "HTTP-oriented work aligns with an API surface."),
    "rest": ("api", 0.90, "REST-oriented work aligns with an API surface."),
    "office": ("native_script", 0.88, "Office workflows usually prefer native scripting."),
    "com": ("native_script", 0.90, "COM implies a native scripting or automation surface."),
    "plugin": ("plugin", 0.90, "The task explicitly mentions plugins."),
    "extension": ("plugin", 0.88, "The task explicitly mentions extensions."),
    "shell": ("existing_cli", 0.82, "Shell-oriented workflows should prefer an existing CLI."),
    "batch": ("existing_cli", 0.80, "Batch-oriented workflows should prefer an existing CLI."),
    "export": ("file_format", 0.54, "Export workflows often involve a stable file-format layer."),
    "document": ("file_format", 0.86, "Document workflows align with a file-format layer."),
    "uia": ("uiautomation", 0.88, "The task explicitly mentions Windows UI Automation."),
    "ax": ("accessibility", 0.88, "The task explicitly mentions accessibility surfaces."),
}


class CapabilityDetector:
    """Infer plausible control surfaces from lightweight target signals."""

    def detect(
        self,
        target: str,
        *,
        platform: str = "auto",
        target_kind: str = "auto",
        needs: Iterable[str] = (),
    ) -> DetectionResult:
        resolved_platform = normalize_platform(platform)
        normalized_needs = [need.strip().lower() for need in needs if need.strip()]
        signals: list[str] = []
        capability_reasons: dict[str, list[tuple[float, str]]] = defaultdict(list)

        inferred_type = self._infer_target_type(target)
        inferred_kind = self._infer_target_kind(
            target,
            inferred_type=inferred_type,
            target_kind=target_kind,
            needs=normalized_needs,
        )

        self._add_base_signals(
            target,
            inferred_type=inferred_type,
            platform=resolved_platform,
            target_kind=inferred_kind,
            signals=signals,
            capability_reasons=capability_reasons,
        )
        self._add_known_hints(target, capability_reasons, signals)
        self._add_need_hints(
            normalized_needs,
            capability_reasons,
            signals,
            platform=resolved_platform,
            target_kind=inferred_kind,
        )
        self._add_path_hints(target, inferred_type, capability_reasons, signals)
        self._add_directory_signatures(target, inferred_type, capability_reasons, signals)
        self._add_platform_hints(
            platform=resolved_platform,
            target_kind=inferred_kind,
            capability_reasons=capability_reasons,
            signals=signals,
        )

        capabilities = [
            Capability(
                name=name,
                confidence=round(max(score for score, _ in entries), 2),
                reasons=[reason for _, reason in entries],
                structured=name != "vision",
            )
            for name, entries in capability_reasons.items()
        ]
        capabilities.sort(key=lambda item: item.confidence, reverse=True)

        return DetectionResult(
            target=target,
            display_name=display_name_from_target(target),
            target_type=inferred_type,
            platform=resolved_platform,
            target_kind=inferred_kind,
            needs=normalized_needs,
            signals=signals,
            capabilities=capabilities,
        )

    def _infer_target_type(self, target: str) -> str:
        if self._looks_like_url(target):
            return "url"
        path = Path(target)
        if path.exists():
            return "directory" if path.is_dir() else "file"
        return "identifier"

    def _infer_target_kind(
        self,
        target: str,
        *,
        inferred_type: str,
        target_kind: str,
        needs: list[str],
    ) -> str:
        if target_kind != "auto":
            return target_kind
        lowered = target.lower()
        if inferred_type == "url":
            if any(need in {"api", "http", "rest"} for need in needs):
                return "service"
            return "web"
        if Path(target).suffix.lower() in DOCUMENT_EXTENSIONS:
            return "document"
        if inferred_type == "directory":
            if Path(target, "package.json").exists() or Path(target, "pyproject.toml").exists():
                return "codebase"
        if any(need in {"browser", "dom", "network"} for need in needs) or "electron" in lowered:
            return "web"
        if any(need in {"api", "http", "rest"} for need in needs):
            return "service"
        return "desktop"

    def _add_base_signals(
        self,
        target: str,
        *,
        inferred_type: str,
        platform: str,
        target_kind: str,
        signals: list[str],
        capability_reasons: dict[str, list[tuple[float, str]]],
    ) -> None:
        signals.append(f"target_type={inferred_type}")
        signals.append(f"target_kind={target_kind}")
        signals.append(f"platform={platform}")
        if target_kind in {"desktop", "web"}:
            capability_reasons["vision"].append((0.25, "Every GUI target keeps a vision fallback."))
        if inferred_type == "url":
            parsed = urlparse(target)
            signals.append(f"url_host={parsed.netloc or 'unknown'}")
            capability_reasons["api"].append((0.72, "A URL target can usually be probed through HTTP or API surfaces."))
        if target_kind == "web":
            capability_reasons["cdp"].append((0.78, "Web targets are usually worth trying through CDP first."))
        if target_kind == "service":
            capability_reasons["api"].append((0.84, "Service targets should default to structured API surfaces."))

    def _add_known_hints(
        self,
        target: str,
        capability_reasons: dict[str, list[tuple[float, str]]],
        signals: list[str],
    ) -> None:
        lowered = target.lower()
        for keyword, (capability, score, reason) in KNOWN_HINTS.items():
            if keyword in lowered:
                signals.append(f"known_hint={keyword}")
                capability_reasons[capability].append((score, reason))

    def _add_need_hints(
        self,
        needs: list[str],
        capability_reasons: dict[str, list[tuple[float, str]]],
        signals: list[str],
        *,
        platform: str,
        target_kind: str,
    ) -> None:
        for need in needs:
            signals.append(f"need={need}")
            if need == "ui" and target_kind == "desktop":
                if platform == "windows":
                    capability_reasons["uiautomation"].append(
                        (0.68, "Desktop UI needs on Windows should prefer UI Automation."),
                    )
                else:
                    capability_reasons["accessibility"].append(
                        (0.68, "Desktop UI needs on non-Windows platforms should prefer accessibility surfaces."),
                    )
                continue

            hint = NEED_HINTS.get(need)
            if hint is None:
                continue
            capability, score, reason = hint
            capability_reasons[capability].append((score, reason))

    def _add_path_hints(
        self,
        target: str,
        inferred_type: str,
        capability_reasons: dict[str, list[tuple[float, str]]],
        signals: list[str],
    ) -> None:
        path = Path(target)
        suffix = path.suffix.lower()
        if inferred_type in {"file", "identifier"}:
            signals.append(f"suffix={suffix or '(none)'}")
            if suffix in DOCUMENT_EXTENSIONS:
                capability_reasons["file_format"].append(
                    (0.90, f"{suffix} is a strong signal for a file-format control layer."),
                )
            if suffix in {".bat", ".cmd", ".ps1", ".sh"}:
                capability_reasons["existing_cli"].append(
                    (0.85, f"{suffix} suggests an existing script or shell entrypoint."),
                )
            if suffix == ".exe":
                capability_reasons["existing_cli"].append(
                    (0.45, "An executable may expose a CLI or shellable entrypoint."),
                )

        if inferred_type == "directory":
            if Path(target, "package.json").exists():
                capability_reasons["existing_cli"].append(
                    (0.70, "A package.json directory may expose Node CLI entrypoints."),
                )
                try:
                    package_data = json.loads(Path(target, "package.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    package_data = {}
                dependencies = {
                    *package_data.get("dependencies", {}).keys(),
                    *package_data.get("devDependencies", {}).keys(),
                }
                if "electron" in dependencies:
                    capability_reasons["cdp"].append(
                        (0.94, "Electron dependencies are a strong signal for CDP."),
                    )
            if Path(target, "pyproject.toml").exists() or Path(target, "setup.py").exists():
                capability_reasons["existing_cli"].append(
                    (0.68, "A Python package directory may expose CLI or script entrypoints."),
                )

    def _add_platform_hints(
        self,
        *,
        platform: str,
        target_kind: str,
        capability_reasons: dict[str, list[tuple[float, str]]],
        signals: list[str],
    ) -> None:
        if target_kind != "desktop":
            return
        if platform == "windows":
            signals.append("platform_surface=windows_uia")
            capability_reasons["uiautomation"].append(
                (0.66, "Windows desktop targets can often be approached through UI Automation."),
            )
        elif platform == "macos":
            signals.append("platform_surface=mac_accessibility")
            capability_reasons["accessibility"].append(
                (0.66, "macOS desktop targets can often be approached through accessibility surfaces."),
            )
        else:
            signals.append("platform_surface=linux_accessibility")
            capability_reasons["accessibility"].append(
                (0.58, "Linux desktop targets can often be approached through accessibility surfaces."),
            )

    def _add_directory_signatures(
        self,
        target: str,
        inferred_type: str,
        capability_reasons: dict[str, list[tuple[float, str]]],
        signals: list[str],
    ) -> None:
        if inferred_type != "directory":
            return
        root = Path(target)
        entries = self._collect_relative_entries(root)
        if not entries:
            return

        def has(fragment: str) -> bool:
            lowered = fragment.lower()
            return any(lowered in entry for entry in entries)

        if has("scripting") or has(".jsx"):
            signals.append("dir_signature=script_surface")
            capability_reasons["native_script"].append(
                (0.95, "The install tree contains scripting surfaces or JSX scripts."),
            )
            signals.append("preferred_language=javascript")
        if has("plug-ins") or has(".aip"):
            signals.append("dir_signature=plugin_surface")
            capability_reasons["plugin"].append(
                (0.92, "The install tree contains plugin directories or binaries."),
            )
        if has("ugopen") or has("automated_testing/python") or has("specialapi"):
            signals.append("dir_signature=native_sdk_surface")
            capability_reasons["native_script"].append(
                (0.94, "The install tree contains native SDK or automation traces."),
            )
            signals.append("preferred_language=python")
        if has("api/com") or has("publicinterfaces") or has("caamain.xml") or has("swaggerui"):
            signals.append("dir_signature=sdk_docs")
            capability_reasons["api"].append(
                (0.78, "The install tree contains API or SDK documentation surfaces."),
            )
        if has("app.asar") or has("quantum_app.asar") or has("resources/app"):
            signals.append("dir_signature=electron_bundle")
            capability_reasons["cdp"].append(
                (0.95, "The install tree contains Electron or Chromium app bundles."),
            )
        if has("chrome_100_percent.pak") or has("v8_context_snapshot.bin") or has("libegl.dll"):
            signals.append("dir_signature=chromium_runtime")
            capability_reasons["cdp"].append(
                (0.60, "The install tree contains Chromium runtime resources."),
            )
        if has("bin/code.cmd") or has("bin/trae.cmd") or has("apollocmd.exe"):
            signals.append("dir_signature=cli_surface")
            capability_reasons["existing_cli"].append(
                (0.86, "The install tree contains direct CLI entrypoints."),
            )
        if has("qqmusicaddin") or has("officeaddin"):
            signals.append("dir_signature=addin_surface")
            capability_reasons["plugin"].append(
                (0.76, "The install tree contains add-in style extension points."),
            )

    def _collect_relative_entries(self, root: Path, max_depth: int = 3, max_items: int = 600) -> list[str]:
        entries: list[str] = []
        root_parts = len(root.parts)
        for path in root.rglob("*"):
            try:
                depth = len(path.parts) - root_parts
            except OSError:
                continue
            if depth > max_depth:
                continue
            try:
                relative = path.relative_to(root).as_posix().lower()
            except OSError:
                continue
            entries.append(relative)
            if len(entries) >= max_items:
                break
        return entries

    def _looks_like_url(self, target: str) -> bool:
        parsed = urlparse(target)
        return bool(parsed.scheme and parsed.netloc)
