from __future__ import annotations

from omnicontrol.runtime.strategy import ConditionSpec, SmokeContract


SMOKE_CONTRACTS: dict[str, SmokeContract] = {
    "finder-open": SmokeContract(
        profile="finder-open",
        mode="read",
        required=[
            ConditionSpec("finder_running"),
            ConditionSpec("window_name", "nonempty"),
        ],
        evidence_keys=["resolved_path", "window_name"],
    ),
    "safari-open": SmokeContract(
        profile="safari-open",
        mode="read",
        required=[
            ConditionSpec("title", "nonempty"),
            ConditionSpec("href", "nonempty"),
        ],
        evidence_keys=["title", "href", "readyState", "secondary_action", "secondary_profile", "secondary_profile_status"],
    ),
    "safari-dom-write": SmokeContract(
        profile="safari-dom-write",
        mode="write",
        required=[
            ConditionSpec("title", "equals", "OmniControl Safari Write"),
            ConditionSpec("marker", "equals", "written"),
            ConditionSpec("textarea_value", "equals", "OmniControl wrote this"),
        ],
        evidence_keys=["title", "href", "marker", "textarea_value", "readyState", "secondary_action", "secondary_profile", "secondary_profile_status"],
    ),
    "word-export": SmokeContract(
        profile="word-export",
        mode="write",
        required=[
            ConditionSpec("exists"),
            ConditionSpec("magic_ok"),
        ],
        evidence_keys=["output", "size", "magic", "duration_seconds"],
    ),
    "word-write": SmokeContract(
        profile="word-write",
        mode="write",
        required=[
            ConditionSpec("exists"),
            ConditionSpec("zip_ok"),
        ],
        evidence_keys=["output", "size", "magic", "duration_seconds"],
    ),
    "word-workflow": SmokeContract(
        profile="word-workflow",
        mode="write",
        required=[
            ConditionSpec("docx_exists"),
            ConditionSpec("docx_zip_ok"),
            ConditionSpec("body_markers_ok"),
        ],
        evidence_keys=["output_docx", "docx_size", "body_markers_ok", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "chrome-cdp": SmokeContract(
        profile="chrome-cdp",
        mode="read",
        required=[
            ConditionSpec("screenshot_exists"),
            ConditionSpec("href", "nonempty"),
        ],
        evidence_keys=["title", "href", "screenshot", "duration_seconds"],
    ),
    "chrome-form-write": SmokeContract(
        profile="chrome-form-write",
        mode="write",
        required=[
            ConditionSpec("title", "equals", "Form Written"),
            ConditionSpec("textarea_value", "equals", "OmniControl wrote this"),
            ConditionSpec("marker", "equals", "written"),
            ConditionSpec("screenshot_exists"),
        ],
        evidence_keys=["title", "textarea_value", "marker", "screenshot", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "chrome-workflow": SmokeContract(
        profile="chrome-workflow",
        mode="write",
        required=[
            ConditionSpec("all_required_steps_ok"),
        ],
        evidence_keys=["last_title", "last_marker", "required_steps_total", "required_steps_ok", "target_selection_attempts", "target_prefer_matched", "secondary_action", "secondary_profile", "secondary_profile_status"],
    ),
    "everything-search": SmokeContract(
        profile="everything-search",
        mode="read",
        required=[
            ConditionSpec("match_count"),
            ConditionSpec("status_text", "nonempty"),
        ],
        evidence_keys=["query", "status_text", "matches", "duration_seconds"],
    ),
    "qqmusic-play": SmokeContract(
        profile="qqmusic-play",
        mode="write",
        required=[
            ConditionSpec("song_id"),
            ConditionSpec("detail_ok"),
            ConditionSpec("command_ok"),
        ],
        desired=[
            ConditionSpec("playback_verified"),
        ],
        evidence_keys=[
            "query",
            "song_id",
            "song_mid",
            "song_name",
            "singer_name",
            "transport_variant",
            "transport_plan",
            "transport_attempts",
            "suppressed_transport_variants",
            "command_method",
            "command_attempts",
            "command_probe",
            "runtime_session",
            "runtime_auth_info",
            "runtime_auth_xml_path",
            "control_context",
            "control_events",
            "interference_cleanup_before",
            "interference_cleanup_after",
            "title",
            "daemon_title",
            "verification_title",
            "xml_path",
            "legacy_xml_path",
            "playback_verified",
        ],
    ),
    "illustrator-export": SmokeContract(
        profile="illustrator-export",
        mode="write",
        required=[
            ConditionSpec("exists"),
            ConditionSpec("svg_ok"),
        ],
        evidence_keys=["output", "size", "script_result", "duration_seconds"],
    ),
    "masterpdf-pagedown": SmokeContract(
        profile="masterpdf-pagedown",
        mode="write",
        required=[
            ConditionSpec("window_name", "nonempty"),
        ],
        desired=[
            ConditionSpec("page_advanced"),
        ],
        evidence_keys=["window_name", "before", "after", "duration_seconds"],
    ),
    "masterpdf-zoom": SmokeContract(
        profile="masterpdf-zoom",
        mode="write",
        required=[
            ConditionSpec("window_name", "nonempty"),
            ConditionSpec("visual_changed"),
        ],
        evidence_keys=["window_name", "before", "after", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "masterpdf-workflow": SmokeContract(
        profile="masterpdf-workflow",
        mode="write",
        required=[
            ConditionSpec("all_required_steps_changed"),
        ],
        evidence_keys=["window_name", "required_steps_total", "required_steps_changed", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "quark-cdp": SmokeContract(
        profile="quark-cdp",
        mode="read",
        required=[
            ConditionSpec("target_title", "nonempty"),
            ConditionSpec("evaluated_href", "nonempty"),
        ],
        evidence_keys=["browser", "target_title", "evaluated_href", "duration_seconds"],
    ),
    "quark-cdp-write": SmokeContract(
        profile="quark-cdp-write",
        mode="write",
        required=[
            ConditionSpec("title", "equals", "OmniControl Quark Write"),
            ConditionSpec("marker", "equals", "ok"),
        ],
        evidence_keys=["title", "marker", "href", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "quark-workflow": SmokeContract(
        profile="quark-workflow",
        mode="write",
        required=[
            ConditionSpec("all_required_steps_ok"),
        ],
        evidence_keys=["last_title", "last_marker", "required_steps_total", "required_steps_ok", "target_selection_attempts", "target_prefer_matched", "secondary_action", "secondary_profile", "secondary_profile_status"],
    ),
    "trae-open": SmokeContract(
        profile="trae-open",
        mode="write",
        required=[
            ConditionSpec("user_data_exists"),
            ConditionSpec("process_count"),
            ConditionSpec("windows", "nonempty"),
        ],
        evidence_keys=["workspace", "user_data_dir", "windows", "duration_seconds"],
    ),
    "trae-cdp-write": SmokeContract(
        profile="trae-cdp-write",
        mode="write",
        required=[
            ConditionSpec("title", "equals", "OmniControl Trae Write"),
            ConditionSpec("marker", "equals", "ok"),
        ],
        evidence_keys=["title", "marker", "href", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "trae-workflow": SmokeContract(
        profile="trae-workflow",
        mode="write",
        required=[
            ConditionSpec("all_required_steps_ok"),
        ],
        evidence_keys=["last_title", "last_marker", "required_steps_total", "required_steps_ok", "secondary_action", "secondary_profile", "secondary_profile_status"],
    ),
    "cadv-view": SmokeContract(
        profile="cadv-view",
        mode="read",
        required=[
            ConditionSpec("window_name", "nonempty"),
            ConditionSpec("window_class", "nonempty"),
        ],
        evidence_keys=["window_name", "window_class", "duration_seconds"],
    ),
    "cadv-zoom": SmokeContract(
        profile="cadv-zoom",
        mode="write",
        required=[
            ConditionSpec("window_name", "nonempty"),
            ConditionSpec("visual_changed"),
        ],
        evidence_keys=["window_name", "before", "after", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "cadv-workflow": SmokeContract(
        profile="cadv-workflow",
        mode="write",
        required=[
            ConditionSpec("all_required_steps_changed"),
        ],
        evidence_keys=["window_name", "required_steps_total", "required_steps_changed", "secondary_action", "secondary_profile", "secondary_profile_status", "duration_seconds"],
    ),
    "nx-diagnose": SmokeContract(
        profile="nx-diagnose",
        mode="diagnose",
        required=[],
        evidence_keys=[
            "help_exit_code",
            "sample_exit_code",
            "splm_license_server",
            "license_port_listening",
            "secondary_action",
            "secondary_action_ok",
            "tooling_verified",
            "tooling_entrypoint",
            "nxcommand_output",
        ],
    ),
    "isight-diagnose": SmokeContract(
        profile="isight-diagnose",
        mode="diagnose",
        required=[],
        evidence_keys=[
            "license_port_listening",
            "dsls_hint",
            "secondary_action",
            "secondary_action_ok",
            "tooling_verified",
            "tooling_entrypoint",
            "fiper_home",
            "fiper_conf",
            "licusage_help_ok",
            "contents_help_ok",
        ],
    ),
    "ue-diagnose": SmokeContract(
        profile="ue-diagnose",
        mode="diagnose",
        required=[],
        evidence_keys=[
            "editor_exists",
            "cmd_exists",
            "help_status",
            "timeout_seconds",
            "secondary_action",
            "secondary_action_ok",
            "tooling_verified",
            "tooling_entrypoint",
        ],
    ),
    "ue-python-write": SmokeContract(
        profile="ue-python-write",
        mode="write",
        required=[
            ConditionSpec("file_exists"),
            ConditionSpec("write_ok"),
        ],
        evidence_keys=["output_file", "engine_version", "secondary_action", "secondary_profile", "secondary_profile_status", "tooling_entrypoint", "duration_seconds"],
    ),
}
