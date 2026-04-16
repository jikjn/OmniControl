from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
from typing import Any

from omnicontrol.runtime.transports import derive_preferred_order


PROFILE_METADATA: dict[str, dict[str, Any]] = {
    "finder-open": {"product_key": "finder", "software_type": "macos_accessibility_desktop", "target_kind": "desktop", "platform": "macos", "control_planes": ["native_script", "accessibility"], "tags": ["finder", "macos", "open"]},
    "safari-open": {"product_key": "safari", "software_type": "macos_browser_native", "target_kind": "web", "platform": "macos", "control_planes": ["native_script", "accessibility"], "tags": ["safari", "browser", "read"]},
    "safari-dom-write": {
        "product_key": "safari",
        "software_type": "macos_browser_native",
        "target_kind": "web",
        "platform": "macos",
        "control_planes": ["native_script", "accessibility"],
        "tags": ["safari", "browser", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "safari-open",
                "attempt_name": "safari_open_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "source_arg": "url",
                "carry_note": "primary Safari DOM write path still blocked",
            }
        ],
    },
    "word-export": {"product_key": "microsoft_word", "software_type": "office_com_win", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script"], "tags": ["office", "word", "com"]},
    "word-write": {"product_key": "microsoft_word", "software_type": "office_com_win", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script"], "tags": ["office", "word", "write"]},
    "word-workflow": {
        "product_key": "microsoft_word",
        "software_type": "office_com_win",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["native_script"],
        "tags": ["office", "word", "workflow"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "word-write",
                "attempt_name": "word_write_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "output_mode": "default",
                "carry_note": "primary Word workflow path still blocked",
            }
        ],
    },
    "chrome-cdp": {"product_key": "google_chrome", "software_type": "browser_cdp", "target_kind": "web", "platform": "windows", "control_planes": ["cdp"], "tags": ["browser", "chrome"]},
    "chrome-form-write": {
        "product_key": "google_chrome",
        "software_type": "browser_cdp",
        "target_kind": "web",
        "platform": "windows",
        "control_planes": ["cdp"],
        "tags": ["browser", "chrome", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "chrome-cdp",
                "attempt_name": "chrome_observe_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "carry_note": "primary Chrome form-write path still blocked",
            }
        ],
    },
    "chrome-workflow": {
        "product_key": "google_chrome",
        "software_type": "browser_cdp",
        "target_kind": "web",
        "platform": "windows",
        "control_planes": ["cdp"],
        "tags": ["browser", "chrome", "workflow"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "chrome-form-write",
                "attempt_name": "chrome_form_write_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "carry_note": "primary Chrome workflow path still blocked",
            }
        ],
    },
    "everything-search": {"product_key": "everything", "software_type": "uia_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation"], "tags": ["search", "uia"]},
    "qqmusic-play": {"product_key": "qqmusic", "software_type": "vendor_web_shell_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["network_api", "vendor_command", "private_protocol", "vision"], "tags": ["qqmusic", "music", "play"]},
    "illustrator-export": {"product_key": "adobe_illustrator", "software_type": "official_script_plugin", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script", "plugin"], "tags": ["illustrator", "adobe", "svg"]},
    "masterpdf-pagedown": {"product_key": "masterpdf", "software_type": "pdf_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation"], "tags": ["pdf", "viewer"]},
    "masterpdf-zoom": {
        "product_key": "masterpdf",
        "software_type": "pdf_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["uiautomation", "vision"],
        "tags": ["pdf", "viewer", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "masterpdf-pagedown",
                "attempt_name": "masterpdf_pagedown_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "source_arg": "source",
                "carry_note": "primary MasterPDF zoom path still blocked",
            }
        ],
    },
    "masterpdf-workflow": {
        "product_key": "masterpdf",
        "software_type": "pdf_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["uiautomation", "vision"],
        "tags": ["pdf", "viewer", "workflow"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "masterpdf-pagedown",
                "attempt_name": "masterpdf_pagedown_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "source_arg": "source",
                "carry_note": "primary MasterPDF workflow path still blocked",
            }
        ],
    },
    "quark-cdp": {"product_key": "quark", "software_type": "electron_cdp", "target_kind": "desktop", "platform": "windows", "control_planes": ["cdp"], "tags": ["quark", "electron"]},
    "quark-cdp-write": {
        "product_key": "quark",
        "software_type": "electron_cdp",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["cdp"],
        "tags": ["quark", "electron", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "quark-cdp",
                "attempt_name": "quark_observe_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "carry_note": "primary Quark write path still blocked",
            }
        ],
    },
    "quark-workflow": {
        "product_key": "quark",
        "software_type": "electron_cdp",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["cdp"],
        "tags": ["quark", "electron", "workflow"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "quark-cdp-write",
                "attempt_name": "quark_write_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "carry_note": "primary Quark workflow path still blocked",
            }
        ],
    },
    "trae-open": {"product_key": "trae", "software_type": "ide_cli_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["existing_cli"], "tags": ["trae", "ide"]},
    "trae-cdp-write": {
        "product_key": "trae",
        "software_type": "ide_cli_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["existing_cli", "cdp"],
        "tags": ["trae", "ide", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_tooling_plane",
                "profile": "trae-open",
                "attempt_name": "trae_open_sidecar",
                "strategy": "switch_to_tooling_plane",
                "source_arg": "workspace",
                "carry_note": "primary Trae CDP path still blocked",
            }
        ],
    },
    "trae-workflow": {
        "product_key": "trae",
        "software_type": "ide_cli_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["existing_cli", "cdp"],
        "tags": ["trae", "ide", "workflow"],
        "secondary_profiles": [
            {
                "action": "switch_to_tooling_plane",
                "profile": "trae-open",
                "attempt_name": "trae_open_sidecar",
                "strategy": "switch_to_tooling_plane",
                "source_arg": "workspace",
                "carry_note": "primary Trae workflow path still blocked",
            }
        ],
    },
    "ide-open": {
        "product_key": "generic_ide",
        "software_type": "ide_cli_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["existing_cli"],
        "tags": ["ide", "generic", "open"],
    },
    "ide-write": {
        "product_key": "generic_ide",
        "software_type": "ide_cli_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["existing_cli", "file_format"],
        "tags": ["ide", "generic", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "ide-open",
                "attempt_name": "ide_open_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "source_arg": "source",
                "carry_note": "primary IDE write path still blocked",
            }
        ],
    },
    "ide-workflow": {
        "product_key": "generic_ide",
        "software_type": "ide_cli_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["existing_cli", "service", "file_format"],
        "tags": ["ide", "generic", "workflow"],
    },
    "cadv-view": {"product_key": "cadviewerve", "software_type": "weak_surface_with_fallback", "target_kind": "desktop", "platform": "windows", "control_planes": ["uiautomation"], "tags": ["cad", "viewer"]},
    "cadv-zoom": {
        "product_key": "cadviewerve",
        "software_type": "weak_surface_with_fallback",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["uiautomation", "vision"],
        "tags": ["cad", "viewer", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "cadv-view",
                "attempt_name": "cadv_view_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "source_arg": "source",
                "carry_note": "primary CadViewer zoom path still blocked",
            }
        ],
    },
    "cadv-workflow": {
        "product_key": "cadviewerve",
        "software_type": "weak_surface_with_fallback",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["uiautomation", "vision"],
        "tags": ["cad", "viewer", "workflow"],
        "secondary_profiles": [
            {
                "action": "switch_to_secondary_entrypoint",
                "profile": "cadv-zoom",
                "attempt_name": "cadv_zoom_sidecar",
                "strategy": "switch_to_secondary_entrypoint",
                "source_arg": "source",
                "carry_note": "primary CadViewer workflow path still blocked",
            }
        ],
    },
    "nx-diagnose": {"product_key": "siemens_nx", "software_type": "native_sdk_heavy_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script", "tooling"], "tags": ["nx", "license", "ufun", "tooling"]},
    "isight-diagnose": {"product_key": "simulia_isight", "software_type": "structured_api_sdk", "target_kind": "desktop", "platform": "windows", "control_planes": ["api", "tooling"], "tags": ["isight", "profile", "dsls", "tooling"]},
    "ue-diagnose": {"product_key": "unreal_engine", "software_type": "game_engine_heavy_desktop", "target_kind": "desktop", "platform": "windows", "control_planes": ["native_script", "vision", "tooling"], "tags": ["unreal", "timeout", "engine", "tooling"]},
    "ue-python-write": {
        "product_key": "unreal_engine",
        "software_type": "game_engine_heavy_desktop",
        "target_kind": "desktop",
        "platform": "windows",
        "control_planes": ["native_script"],
        "tags": ["unreal", "python", "write"],
        "secondary_profiles": [
            {
                "action": "switch_to_tooling_plane",
                "profile": "ue-diagnose",
                "attempt_name": "ue_diagnose_sidecar",
                "strategy": "switch_to_tooling_plane",
                "carry_note": "primary UE Python write path still blocked",
            }
        ],
    },
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


INTERACTION_LEVEL_WEIGHT: dict[str, int] = {
    "diagnose": 0,
    "open": 0,
    "read": 1,
    "navigate": 1,
    "export": 1,
    "write": 2,
    "workflow": 3,
}


CONTROL_PLANE_WEIGHT: dict[str, int] = {
    "tooling": 0,
    "existing_cli": 1,
    "private_protocol": 1,
    "vendor_command": 1,
    "network_api": 1,
    "native_script": 2,
    "plugin": 2,
    "api": 2,
    "service": 2,
    "cdp": 3,
    "uiautomation": 4,
    "vision": 5,
}


for _profile_name, _meta in PROFILE_METADATA.items():
    _meta.setdefault("invocation_context", PROFILE_INVOCATION_CONTEXT.get(_profile_name, "none"))
    _meta.setdefault(
        "accepted_invocation_contexts",
        list(PROFILE_ACCEPTED_INVOCATION_CONTEXTS.get(_profile_name, (_meta["invocation_context"],))),
    )
    _meta.setdefault(
        "interaction_level",
        PROFILE_INTERACTION_LEVEL.get(_profile_name),
    )


def kb_path() -> Path:
    return Path.cwd() / "knowledge" / "kb.json"


def load_kb() -> dict[str, Any]:
    path = kb_path()
    if not path.exists():
        return {"version": 1, "updated_at": None, "cases": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_kb(data: dict[str, Any]) -> None:
    path = kb_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def record_payload(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    kb = load_kb()
    lookup = _build_lookup(profile, payload)
    case_id = _case_id_for(lookup)
    case = next((item for item in kb["cases"] if item["case_id"] == case_id), None)
    if case is None:
        case = {
            "case_id": case_id,
            "lookup": lookup,
            "summary": {
                "last_status": payload.get("status"),
                "times_seen": 0,
                "times_blocked": 0,
                "times_solved": 0,
                "first_seen_at": _now(),
                "last_seen_at": _now(),
            },
            "blocked_cases": [],
            "remediation_attempts": [],
            "solution": None,
        }
        kb["cases"].append(case)

    summary = case["summary"]
    summary["times_seen"] += 1
    summary["last_status"] = payload.get("status")
    summary["last_seen_at"] = _now()
    if payload.get("status") == "blocked":
        summary["times_blocked"] += 1
        case["blocked_cases"].append(
            {
                "run_id": _run_id(),
                "ts": _now(),
                "raw_status": payload.get("raw_status", payload.get("status")),
                "blockers": payload.get("strategy", {}).get("blockers", payload.get("blockers", [])),
                "evidence": payload.get("strategy", {}).get("evidence", {}),
                "report_path": payload.get("report_path"),
            }
        )

    for attempt in payload.get("orchestration", {}).get("attempts", []):
        case["remediation_attempts"].append(
            {
                "attempt_id": f"{attempt['name']}-{_run_id()}",
                "ts": _now(),
                "source": attempt["name"],
                "strategy": attempt["strategy"],
                "status": attempt["status"],
                "blockers": attempt.get("payload", {}).get("blockers", []),
                "evidence": attempt.get("payload", {}).get("strategy", {}).get("evidence", {}),
                "report_path": payload.get("report_path"),
            }
        )

    if payload.get("status") in {"ok", "partial"}:
        summary["times_solved"] += 1
        case["solution"] = {
            "status": "verified",
            "winning_attempt_id": payload.get("orchestration", {}).get("selected_attempt"),
            "selected_phase": payload.get("orchestration", {}).get("selected_phase"),
            "summary": _solution_summary(payload),
            "recipe": _solution_recipe(payload),
            "remediation_actions": _solution_actions(payload),
            "launch_overrides": _launch_overrides(payload),
            "verified_at": _now(),
            "success_report_path": payload.get("report_path"),
        }

    save_kb(kb)
    matched = find_matches(profile, payload, kb)
    return {
        "kb_path": str(kb_path()),
        "case_id": case_id,
        "matched_case_ids": [item["case_id"] for item in matched],
        "best_solution": next((item["solution"] for item in matched if item.get("solution")), None),
    }


def find_matches(profile: str, payload: dict[str, Any], kb: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    kb = kb or load_kb()
    lookup = _build_lookup(profile, payload)
    matches = []
    for case in kb["cases"]:
        score = 0
        case_lookup = case["lookup"]
        shared_planes = len(set(case_lookup["control_planes"]) & set(lookup["control_planes"]))
        same_product = case_lookup["product_key"] == lookup["product_key"]
        same_software_type = case_lookup["software_type"] == lookup["software_type"]
        if not same_product and not (same_software_type and shared_planes):
            continue
        if same_product:
            score += 100
        if same_software_type:
            score += 20
        score += shared_planes * 10
        score += len(set(case_lookup["blocker_patterns"]) & set(lookup["blocker_patterns"])) * 10
        if score > 0:
            case = dict(case)
            case["_score"] = score
            matches.append(case)
    matches.sort(key=lambda item: (item["_score"], item["summary"]["times_solved"], item["summary"]["last_seen_at"]), reverse=True)
    return matches[:5]


def recommended_launch_overrides(profile: str) -> dict[str, Any]:
    kb = load_kb()
    meta = PROFILE_METADATA.get(profile, {})
    product_key = meta.get("product_key")
    if not product_key:
        return {}
    matches = [
        case for case in kb["cases"]
        if case["lookup"]["product_key"] == product_key and case.get("solution")
    ]
    matches.sort(key=lambda item: (item["summary"]["times_solved"], item["summary"]["last_seen_at"]), reverse=True)
    if not matches:
        return {}
    return matches[0]["solution"].get("launch_overrides", {})


def secondary_profile_specs(profile: str) -> list[dict[str, Any]]:
    metadata = PROFILE_METADATA.get(profile, {})
    explicit_specs = [_normalized_secondary_spec(profile, spec, inferred=False) for spec in metadata.get("secondary_profiles", [])]
    explicit_specs = [spec for spec in explicit_specs if spec is not None]
    explicit_actions = {spec["action"] for spec in explicit_specs}
    explicit_profiles = {spec["profile"] for spec in explicit_specs}

    inferred_specs = []
    for spec in infer_secondary_profiles(profile):
        if spec["action"] in explicit_actions or spec["profile"] in explicit_profiles:
            continue
        inferred_specs.append(spec)
    return [*explicit_specs, *inferred_specs]


def infer_secondary_profiles(profile: str) -> list[dict[str, Any]]:
    primary_meta = PROFILE_METADATA.get(profile, {})
    product_key = primary_meta.get("product_key")
    if not product_key:
        return []

    primary_context = profile_invocation_context(profile)
    primary_interaction = profile_interaction_level(profile)
    primary_weight = interaction_level_weight(profile)
    primary_plane_weight = control_plane_weight(profile)

    ranked_specs: list[dict[str, Any]] = []
    for sibling, sibling_meta in PROFILE_METADATA.items():
        if sibling == profile or sibling_meta.get("product_key") != product_key:
            continue
        sibling_contexts = accepted_invocation_contexts(sibling)
        if not _invocation_context_compatible(primary_context, sibling_contexts):
            continue
        source_arg = _compatible_context_arg(primary_context, sibling_contexts)
        if is_url_substitution_candidate(
            primary_profile=profile,
            secondary_profile=sibling,
            source_arg=source_arg,
        ):
            continue

        sibling_weight = interaction_level_weight(sibling)
        sibling_plane_weight = control_plane_weight(sibling)
        sibling_interaction = profile_interaction_level(sibling)
        if sibling_weight > primary_weight:
            continue
        if sibling_weight == primary_weight and sibling_plane_weight >= primary_plane_weight:
            continue

        action = _infer_secondary_action(
            primary_profile=profile,
            secondary_profile=sibling,
            primary_interaction=primary_interaction,
            secondary_interaction=sibling_interaction,
        )
        if not action:
            continue

        score = ((primary_weight - sibling_weight) * 100) + ((primary_plane_weight - sibling_plane_weight) * 10)
        if primary_context != "none" and primary_context in sibling_contexts:
            score += 5
        if sibling_interaction in {"diagnose", "open", "read"}:
            score += 3

        spec = _normalized_secondary_spec(
            profile,
            {
                "action": action,
                "profile": sibling,
                "attempt_name": f"{sibling}_auto_sidecar",
                "strategy": action,
                "source_arg": source_arg,
                "carry_note": f"primary {profile} path still blocked",
                "reason": f"Switch to inferred sibling profile {sibling} to verify a lighter control plane for {product_key}.",
                "_score": score,
            },
            inferred=True,
        )
        if spec is not None:
            ranked_specs.append(spec)

    ranked_specs.sort(key=lambda item: (item.get("_score", 0), item["profile"]), reverse=True)
    best_by_action: dict[str, dict[str, Any]] = {}
    for spec in ranked_specs:
        best_by_action.setdefault(spec["action"], spec)

    result = list(best_by_action.values())
    result.sort(key=lambda item: (item.get("_score", 0), item["profile"]), reverse=True)
    for item in result:
        item.pop("_score", None)
    return result


def profile_invocation_context(profile: str) -> str:
    metadata = PROFILE_METADATA.get(profile, {})
    return str(metadata.get("invocation_context") or PROFILE_INVOCATION_CONTEXT.get(profile, "none"))


def allow_url_substitution(profile: str) -> bool:
    metadata = PROFILE_METADATA.get(profile, {})
    explicit = metadata.get("allow_url_substitution")
    if explicit is not None:
        return bool(explicit)
    return str(metadata.get("target_kind") or "desktop") == "web"


def is_url_substitution_candidate(
    *,
    primary_profile: str,
    secondary_profile: str,
    source_arg: str | None = None,
) -> bool:
    if allow_url_substitution(primary_profile):
        return False
    secondary_meta = PROFILE_METADATA.get(secondary_profile, {})
    if source_arg == "url":
        return True
    if profile_invocation_context(secondary_profile) == "url":
        return True
    return str(secondary_meta.get("target_kind") or "desktop") == "web"


def accepted_invocation_contexts(profile: str) -> tuple[str, ...]:
    metadata = PROFILE_METADATA.get(profile, {})
    accepted = metadata.get("accepted_invocation_contexts")
    if accepted:
        return tuple(str(item) for item in accepted)
    mapped = PROFILE_ACCEPTED_INVOCATION_CONTEXTS.get(profile)
    if mapped:
        return tuple(str(item) for item in mapped)
    default = profile_invocation_context(profile)
    return (default,)


def profile_interaction_level(profile: str) -> str:
    metadata = PROFILE_METADATA.get(profile, {})
    level = metadata.get("interaction_level")
    if level:
        return str(level)
    if profile in PROFILE_INTERACTION_LEVEL:
        return PROFILE_INTERACTION_LEVEL[profile]

    tags = set(metadata.get("tags", []))
    lowered = f"{profile} {' '.join(sorted(tags))}".lower()
    if "workflow" in lowered:
        return "workflow"
    if "diagnose" in lowered:
        return "diagnose"
    if "write" in lowered or "zoom" in lowered:
        return "write"
    if "open" in lowered:
        return "open"
    if "view" in lowered or "search" in lowered or "observe" in lowered:
        return "read"
    if "page" in lowered or "export" in lowered:
        return "navigate"
    return "read"


def interaction_level_weight(profile: str) -> int:
    return INTERACTION_LEVEL_WEIGHT.get(profile_interaction_level(profile), 10)


def control_plane_weight(profile: str) -> int:
    metadata = PROFILE_METADATA.get(profile, {})
    planes = metadata.get("control_planes", [])
    if not planes:
        return 10
    return min(CONTROL_PLANE_WEIGHT.get(str(plane), 10) for plane in planes)


def _normalized_secondary_spec(profile: str, spec: dict[str, Any], *, inferred: bool) -> dict[str, Any] | None:
    action = str(spec.get("action", "")).strip()
    secondary_profile = str(spec.get("profile", "")).strip()
    if not action or not secondary_profile or secondary_profile == profile:
        return None
    normalized = dict(spec)
    normalized["action"] = action
    normalized["profile"] = secondary_profile
    normalized["attempt_name"] = str(spec.get("attempt_name") or f"{secondary_profile}_sidecar")
    normalized["strategy"] = str(spec.get("strategy") or action)
    if "source_arg" not in normalized:
        context = profile_invocation_context(secondary_profile)
        normalized["source_arg"] = None if context == "none" else context
    normalized["inferred"] = inferred
    return normalized


def _invocation_context_compatible(primary: str, secondary_contexts: tuple[str, ...]) -> bool:
    return "none" in secondary_contexts or primary in secondary_contexts


def _compatible_context_arg(primary: str, secondary_contexts: tuple[str, ...]) -> str | None:
    if primary != "none" and primary in secondary_contexts:
        return primary
    if "none" in secondary_contexts:
        return None
    return primary if primary in secondary_contexts else None


def _infer_secondary_action(
    *,
    primary_profile: str,
    secondary_profile: str,
    primary_interaction: str,
    secondary_interaction: str,
) -> str | None:
    secondary_planes = set(PROFILE_METADATA.get(secondary_profile, {}).get("control_planes", []))
    primary_planes = set(PROFILE_METADATA.get(primary_profile, {}).get("control_planes", []))

    if secondary_interaction == "diagnose":
        return "switch_to_tooling_plane"
    if "tooling" in secondary_planes or "existing_cli" in secondary_planes:
        return "switch_to_tooling_plane"
    if "service" in secondary_planes:
        return "switch_to_secondary_service"
    if secondary_interaction in {"open", "read", "navigate", "export"}:
        return "switch_to_secondary_entrypoint"
    if secondary_planes and secondary_planes < primary_planes:
        return "switch_to_secondary_entrypoint"
    if INTERACTION_LEVEL_WEIGHT.get(secondary_interaction, 10) < INTERACTION_LEVEL_WEIGHT.get(primary_interaction, 10):
        return "switch_to_secondary_entrypoint"
    return None


def _build_lookup(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    meta = PROFILE_METADATA.get(profile, {})
    blocker_patterns = payload.get("strategy", {}).get("blocker_types", [])
    return {
        "product_key": meta.get("product_key", profile),
        "software_type": meta.get("software_type", "unknown"),
        "target_kind": meta.get("target_kind", "desktop"),
        "platform": meta.get("platform", "windows"),
        "profile": profile,
        "control_planes": meta.get("control_planes", []),
        "blocker_patterns": blocker_patterns,
        "tags": meta.get("tags", []),
    }


def _case_id_for(lookup: dict[str, Any]) -> str:
    blocker_key = "-".join(sorted(lookup["blocker_patterns"])) if lookup["blocker_patterns"] else "none"
    return f"{lookup['platform']}:{lookup['product_key']}:{lookup['profile']}:{blocker_key}"


def _solution_summary(payload: dict[str, Any]) -> str:
    startup = payload.get("startup", {})
    if startup:
        strategy = startup.get("strategy")
        if strategy:
            return f"Use startup strategy {strategy}."
    selected = _selected_attempt(payload)
    if selected and selected.get("phase") == "pivot":
        return f"Pivot to strategy {selected.get('strategy')} after the primary path was blocked."
    return f"{payload.get('profile')} completed with status {payload.get('status')}."


def _solution_recipe(payload: dict[str, Any]) -> list[str]:
    startup = payload.get("startup", {})
    recipe: list[str] = []
    if startup.get("attached_existing"):
        recipe.append("Attach to an existing debuggable instance.")
    if startup.get("strategy") == "restart_with_debug_port":
        recipe.append("Relaunch with a dedicated remote debugging port.")
    if startup.get("user_data_dir"):
        recipe.append("Use an isolated user-data directory.")
    if payload.get("marker") is not None:
        recipe.append("Perform a write action and read the marker back.")
    selected = _selected_attempt(payload)
    if selected and selected.get("phase") == "pivot" and selected.get("strategy"):
        recipe.append(f"Pivot to {selected['strategy']} after the primary path blocked.")
    return recipe or ["Repeat the same profile with the recorded startup strategy."]


def _solution_actions(payload: dict[str, Any]) -> list[str]:
    selected = _selected_attempt(payload)
    if not selected:
        return []
    strategy = selected.get("strategy")
    if not strategy or strategy == "direct_script":
        return []
    return [strategy]


def _selected_attempt(payload: dict[str, Any]) -> dict[str, Any] | None:
    orchestration = payload.get("orchestration", {})
    selected_name = orchestration.get("selected_attempt")
    if not selected_name:
        return None
    for attempt in orchestration.get("attempts", []):
        if attempt.get("name") == selected_name:
            return attempt
    return None


def _launch_overrides(payload: dict[str, Any]) -> dict[str, Any]:
    startup = payload.get("startup", {})
    overrides = {}
    if startup.get("strategy"):
        overrides["preferred_strategy"] = startup["strategy"]
    if startup.get("user_data_dir"):
        overrides["use_isolated_user_data"] = True
    if startup.get("attached_existing"):
        overrides["allow_attach_existing"] = True
    transport_attempts = payload.get("transport_attempts", [])
    preferred_transport_order = derive_preferred_order(
        transport_attempts,
        success_key="command_ok",
        name_keys=("transport_variant", "name"),
    )
    if preferred_transport_order:
        overrides["preferred_transport_order"] = preferred_transport_order
        overrides["preferred_transport_variants"] = preferred_transport_order

    attempts = payload.get("command_attempts", []) or payload.get("attempts", [])
    preferred_methods = derive_preferred_order(
        attempts,
        success_key="command_ok",
        name_keys=("method", "name"),
    )
    if preferred_methods:
        overrides["preferred_method_order"] = preferred_methods
        overrides["preferred_command_methods"] = preferred_methods
    return overrides


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _run_id() -> str:
    return datetime.now().strftime("run-%Y%m%d-%H%M%S")
