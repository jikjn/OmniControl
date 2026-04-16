from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ProfileDescriptor:
    profile_id: str
    product_key: str
    software_type: str
    target_kind: str
    platform: str
    control_planes: tuple[str, ...]
    tags: tuple[str, ...]
    invocation_context: str
    accepted_invocation_contexts: tuple[str, ...]
    interaction_level: str | None
    secondary_profiles: tuple[Mapping[str, Any], ...]


_BASE_PROFILE_METADATA: dict[str, dict[str, Any]] = {
    "finder-open": {"product_key": "finder", "software_type": "macos_accessibility_desktop", "target_kind": "desktop", "platform": "macos", "control_planes": ["native_script", "accessibility"], "tags": ["finder", "macos", "open"]},
    "safari-open": {"product_key": "safari", "software_type": "macos_browser_native", "target_kind": "web", "platform": "macos", "control_planes": ["native_script", "accessibility"], "tags": ["safari", "browser", "read"]},
    "safari-dom-write": {"product_key": "safari", "software_type": "macos_browser_native", "target_kind": "web", "platform": "macos", "control_planes": ["native_script", "accessibility"], "tags": ["safari", "browser", "write"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "safari-open", "attempt_name": "safari_open_sidecar", "strategy": "switch_to_secondary_entrypoint", "source_arg": "url", "carry_note": "primary Safari DOM write path still blocked"}]},
    "word-export": {"product_key": "microsoft_word", "software_type": "office_com_win", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script"], "tags": ["office", "word", "com"]},
    "word-write": {"product_key": "microsoft_word", "software_type": "office_com_win", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script"], "tags": ["office", "word", "write"]},
    "word-workflow": {"product_key": "microsoft_word", "software_type": "office_com_win", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script"], "tags": ["office", "word", "workflow"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "word-write", "attempt_name": "word_write_sidecar", "strategy": "switch_to_secondary_entrypoint", "output_mode": "default", "carry_note": "primary Word workflow path still blocked"}]},
    "chrome-cdp": {"product_key": "google_chrome", "software_type": "browser_cdp", "target_kind": "web", "platform": "windows", "control_planes": ["cdp"], "tags": ["browser", "chrome"]},
    "chrome-form-write": {"product_key": "google_chrome", "software_type": "browser_cdp", "target_kind": "web", "platform": "windows", "control_planes": ["cdp"], "tags": ["browser", "chrome", "write"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "chrome-cdp", "attempt_name": "chrome_observe_sidecar", "strategy": "switch_to_secondary_entrypoint", "carry_note": "primary Chrome form-write path still blocked"}]},
    "chrome-workflow": {"product_key": "google_chrome", "software_type": "browser_cdp", "target_kind": "web", "platform": "windows", "control_planes": ["cdp"], "tags": ["browser", "chrome", "workflow"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "chrome-form-write", "attempt_name": "chrome_form_write_sidecar", "strategy": "switch_to_secondary_entrypoint", "carry_note": "primary Chrome workflow path still blocked"}]},
    "everything-search": {"product_key": "everything", "software_type": "uia_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation"], "tags": ["search", "uia"]},
    "qqmusic-play": {"product_key": "qqmusic", "software_type": "vendor_web_shell_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["network_api", "vendor_command", "private_protocol", "vision"], "tags": ["qqmusic", "music", "play"]},
    "illustrator-export": {"product_key": "adobe_illustrator", "software_type": "official_script_plugin", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script", "plugin"], "tags": ["illustrator", "adobe", "svg"]},
    "masterpdf-pagedown": {"product_key": "masterpdf", "software_type": "pdf_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation"], "tags": ["pdf", "viewer"]},
    "masterpdf-zoom": {"product_key": "masterpdf", "software_type": "pdf_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation", "vision"], "tags": ["pdf", "viewer", "write"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "masterpdf-pagedown", "attempt_name": "masterpdf_pagedown_sidecar", "strategy": "switch_to_secondary_entrypoint", "source_arg": "source", "carry_note": "primary MasterPDF zoom path still blocked"}]},
    "masterpdf-workflow": {"product_key": "masterpdf", "software_type": "pdf_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation", "vision"], "tags": ["pdf", "viewer", "workflow"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "masterpdf-pagedown", "attempt_name": "masterpdf_pagedown_sidecar", "strategy": "switch_to_secondary_entrypoint", "source_arg": "source", "carry_note": "primary MasterPDF workflow path still blocked"}]},
    "quark-cdp": {"product_key": "quark", "software_type": "electron_cdp", "target_kind": "desktop", "platform": "windows", "control_planes": ["cdp"], "tags": ["quark", "electron"]},
    "quark-cdp-write": {"product_key": "quark", "software_type": "electron_cdp", "target_kind": "desktop", "platform": "windows", "control_planes": ["cdp"], "tags": ["quark", "electron", "write"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "quark-cdp", "attempt_name": "quark_observe_sidecar", "strategy": "switch_to_secondary_entrypoint", "carry_note": "primary Quark write path still blocked"}]},
    "quark-workflow": {"product_key": "quark", "software_type": "electron_cdp", "target_kind": "desktop", "platform": "windows", "control_planes": ["cdp"], "tags": ["quark", "electron", "workflow"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "quark-cdp-write", "attempt_name": "quark_write_sidecar", "strategy": "switch_to_secondary_entrypoint", "carry_note": "primary Quark workflow path still blocked"}]},
    "trae-open": {"product_key": "trae", "software_type": "ide_cli_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["existing_cli"], "tags": ["trae", "ide"]},
    "trae-cdp-write": {"product_key": "trae", "software_type": "ide_cli_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["existing_cli", "cdp"], "tags": ["trae", "ide", "write"], "secondary_profiles": [{"action": "switch_to_tooling_plane", "profile": "trae-open", "attempt_name": "trae_open_sidecar", "strategy": "switch_to_tooling_plane", "source_arg": "workspace", "carry_note": "primary Trae CDP path still blocked"}]},
    "trae-workflow": {"product_key": "trae", "software_type": "ide_cli_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["existing_cli", "cdp"], "tags": ["trae", "ide", "workflow"], "secondary_profiles": [{"action": "switch_to_tooling_plane", "profile": "trae-open", "attempt_name": "trae_open_sidecar", "strategy": "switch_to_tooling_plane", "source_arg": "workspace", "carry_note": "primary Trae workflow path still blocked"}]},
    "ide-open": {"product_key": "generic_ide", "software_type": "ide_cli_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["existing_cli"], "tags": ["ide", "generic", "open"]},
    "ide-write": {"product_key": "generic_ide", "software_type": "ide_cli_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["existing_cli", "file_format"], "tags": ["ide", "generic", "write"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "ide-open", "attempt_name": "ide_open_sidecar", "strategy": "switch_to_secondary_entrypoint", "source_arg": "source", "carry_note": "primary IDE write path still blocked"}]},
    "ide-workflow": {"product_key": "generic_ide", "software_type": "ide_cli_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["existing_cli", "service", "file_format"], "tags": ["ide", "generic", "workflow"]},
    "cadv-view": {"product_key": "cadviewerve", "software_type": "weak_surface_with_fallback", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation"], "tags": ["cad", "viewer"]},
    "cadv-zoom": {"product_key": "cadviewerve", "software_type": "weak_surface_with_fallback", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation", "vision"], "tags": ["cad", "viewer", "write"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "cadv-view", "attempt_name": "cadv_view_sidecar", "strategy": "switch_to_secondary_entrypoint", "source_arg": "source", "carry_note": "primary CadViewer zoom path still blocked"}]},
    "cadv-workflow": {"product_key": "cadviewerve", "software_type": "weak_surface_with_fallback", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation", "vision"], "tags": ["cad", "viewer", "workflow"], "secondary_profiles": [{"action": "switch_to_secondary_entrypoint", "profile": "cadv-zoom", "attempt_name": "cadv_zoom_sidecar", "strategy": "switch_to_secondary_entrypoint", "source_arg": "source", "carry_note": "primary CadViewer workflow path still blocked"}]},
    "nx-diagnose": {"product_key": "siemens_nx", "software_type": "native_sdk_heavy_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script", "tooling"], "tags": ["nx", "license", "ufun", "tooling"]},
    "isight-diagnose": {"product_key": "simulia_isight", "software_type": "structured_api_sdk", "target_kind": "desktop", "platform": "windows", "control_planes": ["api", "tooling"], "tags": ["isight", "profile", "dsls", "tooling"]},
    "ue-diagnose": {"product_key": "unreal_engine", "software_type": "game_engine_heavy_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script", "vision", "tooling"], "tags": ["unreal", "timeout", "engine", "tooling"]},
    "ue-python-write": {"product_key": "unreal_engine", "software_type": "game_engine_heavy_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script"], "tags": ["unreal", "python", "write"], "secondary_profiles": [{"action": "switch_to_tooling_plane", "profile": "ue-diagnose", "attempt_name": "ue_diagnose_sidecar", "strategy": "switch_to_tooling_plane", "carry_note": "primary UE Python write path still blocked"}]},
}

PROFILE_INVOCATION_CONTEXT: dict[str, str] = {
    "finder-open": "none",
    "safari-open": "url",
    "safari-dom-write": "url",
    "word-export": "source",
    "word-workflow": "none",
    "masterpdf-pagedown": "source",
    "masterpdf-zoom": "source",
    "masterpdf-workflow": "source",
    "chrome-workflow": "none",
    "quark-workflow": "none",
    "trae-open": "workspace",
    "trae-cdp-write": "workspace",
    "trae-workflow": "workspace",
    "ide-open": "source",
    "ide-write": "source",
    "ide-workflow": "workspace",
    "cadv-view": "source",
    "cadv-zoom": "source",
    "cadv-workflow": "source",
}

PROFILE_ACCEPTED_INVOCATION_CONTEXTS: dict[str, tuple[str, ...]] = {
    "finder-open": ("none", "source"),
    "safari-open": ("url", "none"),
    "safari-dom-write": ("url", "none"),
    "word-export": ("source",),
    "word-write": ("none",),
    "word-workflow": ("none",),
    "chrome-cdp": ("none", "url"),
    "chrome-form-write": ("none",),
    "chrome-workflow": ("none",),
    "everything-search": ("query",),
    "qqmusic-play": ("query",),
    "illustrator-export": ("none",),
    "masterpdf-pagedown": ("source",),
    "masterpdf-zoom": ("source",),
    "masterpdf-workflow": ("source",),
    "quark-cdp": ("none",),
    "quark-cdp-write": ("none",),
    "quark-workflow": ("none",),
    "trae-open": ("none", "workspace"),
    "trae-cdp-write": ("none", "workspace"),
    "trae-workflow": ("none", "workspace"),
    "ide-open": ("none", "source", "workspace"),
    "ide-write": ("source",),
    "ide-workflow": ("none", "source", "workspace"),
    "cadv-view": ("source",),
    "cadv-zoom": ("source",),
    "cadv-workflow": ("source",),
    "nx-diagnose": ("none",),
    "isight-diagnose": ("none",),
    "ue-diagnose": ("none",),
    "ue-python-write": ("none",),
}

PROFILE_INTERACTION_LEVEL: dict[str, str] = {
    "finder-open": "open",
    "safari-open": "read",
    "safari-dom-write": "write",
    "word-export": "export",
    "word-write": "write",
    "word-workflow": "workflow",
    "chrome-cdp": "read",
    "chrome-form-write": "write",
    "chrome-workflow": "workflow",
    "everything-search": "read",
    "qqmusic-play": "workflow",
    "illustrator-export": "export",
    "masterpdf-pagedown": "navigate",
    "masterpdf-zoom": "write",
    "masterpdf-workflow": "workflow",
    "quark-cdp": "read",
    "quark-cdp-write": "write",
    "quark-workflow": "workflow",
    "trae-open": "open",
    "trae-cdp-write": "write",
    "trae-workflow": "workflow",
    "ide-open": "open",
    "ide-write": "write",
    "ide-workflow": "workflow",
    "cadv-view": "read",
    "cadv-zoom": "write",
    "cadv-workflow": "workflow",
    "nx-diagnose": "diagnose",
    "isight-diagnose": "diagnose",
    "ue-diagnose": "diagnose",
    "ue-python-write": "write",
}


def _enrich_metadata(profile: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(metadata)
    invocation_context = PROFILE_INVOCATION_CONTEXT.get(profile, "none")
    enriched.setdefault("invocation_context", invocation_context)
    enriched.setdefault(
        "accepted_invocation_contexts",
        list(PROFILE_ACCEPTED_INVOCATION_CONTEXTS.get(profile, (invocation_context,))),
    )
    enriched.setdefault("interaction_level", PROFILE_INTERACTION_LEVEL.get(profile))
    return enriched


PROFILE_METADATA: dict[str, dict[str, Any]] = {
    profile: _enrich_metadata(profile, metadata)
    for profile, metadata in _BASE_PROFILE_METADATA.items()
}


def _descriptor_from_metadata(profile: str, metadata: Mapping[str, Any]) -> ProfileDescriptor:
    return ProfileDescriptor(
        profile_id=profile,
        product_key=str(metadata.get("product_key", "")),
        software_type=str(metadata.get("software_type", "")),
        target_kind=str(metadata.get("target_kind", "")),
        platform=str(metadata.get("platform", "")),
        control_planes=tuple(metadata.get("control_planes", ())),
        tags=tuple(metadata.get("tags", ())),
        invocation_context=str(metadata.get("invocation_context", "none")),
        accepted_invocation_contexts=tuple(metadata.get("accepted_invocation_contexts", ())),
        interaction_level=metadata.get("interaction_level"),
        secondary_profiles=tuple(
            MappingProxyType(dict(spec))
            for spec in metadata.get("secondary_profiles", ())
        ),
    )


PROFILE_REGISTRY: dict[str, ProfileDescriptor] = {
    profile: _descriptor_from_metadata(profile, metadata)
    for profile, metadata in PROFILE_METADATA.items()
}


def list_profile_ids() -> tuple[str, ...]:
    return tuple(PROFILE_METADATA.keys())


def profile_choices() -> tuple[str, ...]:
    return list_profile_ids()


def metadata_for_profile(profile: str) -> Mapping[str, Any]:
    if profile not in PROFILE_METADATA:
        raise KeyError(profile)
    return PROFILE_METADATA[profile]


def get_profile_descriptor(profile: str) -> ProfileDescriptor:
    if profile in PROFILE_REGISTRY:
        return PROFILE_REGISTRY[profile]
    return _descriptor_from_metadata(profile, metadata_for_profile(profile))
