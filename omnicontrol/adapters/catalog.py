from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdapterProfile:
    name: str
    priority: float
    default_state_model: str
    default_verification: tuple[str, ...]
    summary: str


ADAPTER_PROFILES: dict[str, AdapterProfile] = {
    "native_script": AdapterProfile(
        name="native_script",
        priority=0.95,
        default_state_model="backend_state",
        default_verification=("backend_query", "command_exit"),
        summary="Official scripting, SDK, COM, AppleScript or app-native automation.",
    ),
    "plugin": AdapterProfile(
        name="plugin",
        priority=0.92,
        default_state_model="backend_state",
        default_verification=("backend_query", "command_exit"),
        summary="App plugin or extension point with structured automation surface.",
    ),
    "api": AdapterProfile(
        name="api",
        priority=0.90,
        default_state_model="backend_state",
        default_verification=("backend_query", "http_status", "file_exists"),
        summary="REST, RPC or service API with structured request-response behavior.",
    ),
    "cdp": AdapterProfile(
        name="cdp",
        priority=0.89,
        default_state_model="backend_state",
        default_verification=("backend_query", "ui_object", "network_trace"),
        summary="Chrome DevTools Protocol or Electron debugging interface.",
    ),
    "existing_cli": AdapterProfile(
        name="existing_cli",
        priority=0.84,
        default_state_model="stateless",
        default_verification=("command_exit", "file_exists"),
        summary="Existing CLI, headless command or shellable backend.",
    ),
    "file_format": AdapterProfile(
        name="file_format",
        priority=0.80,
        default_state_model="stateless",
        default_verification=("file_exists", "file_hash", "file_schema"),
        summary="Open or stable file-format layer without direct app control.",
    ),
    "uiautomation": AdapterProfile(
        name="uiautomation",
        priority=0.70,
        default_state_model="backend_state",
        default_verification=("ui_object", "command_exit"),
        summary="Windows UI Automation surface for structured desktop UI control.",
    ),
    "accessibility": AdapterProfile(
        name="accessibility",
        priority=0.70,
        default_state_model="backend_state",
        default_verification=("ui_object", "command_exit"),
        summary="macOS accessibility or Linux AT-SPI control surface.",
    ),
    "vision": AdapterProfile(
        name="vision",
        priority=0.35,
        default_state_model="shadow_session",
        default_verification=("screenshot_diff", "manual_review"),
        summary="Last-resort visual fallback without stable object-level semantics.",
    ),
}
