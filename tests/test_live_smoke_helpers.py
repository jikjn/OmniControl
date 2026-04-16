from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from omnicontrol.runtime.kb import PROFILE_ACCEPTED_INVOCATION_CONTEXTS, PROFILE_INTERACTION_LEVEL, PROFILE_INVOCATION_CONTEXT, PROFILE_METADATA
from omnicontrol.runtime.live_smoke import (
    _apply_safe_ide_file_write,
    _build_ide_open_command,
    _build_sidecar_partial_payload,
    _collect_ide_log_blockers,
    _decode_mcp_tool_result,
    _detect_ide_family,
    _detect_ide_blockers,
    _detect_ide_install_root,
    _extract_jetbrains_mcp_port,
    _ide_target_tokens,
    _ide_project_context,
    _ide_window_matches_target,
    _metadata_secondary_profile_action_map,
    _qqmusic_build_play_command_xml,
    _qqmusic_build_songinfo_payload,
    _qqmusic_control_script_lines,
    _qqmusic_execute_transport_variants,
    _qqmusic_song_detail_url,
    _qqmusic_execute_control_methods,
    _qqmusic_select_candidate,
    _resolve_code_family_launcher,
    _resolve_ide_spec,
    _resolve_jetbrains_launcher,
    _run_cmd_chain,
    _select_ide_target_window,
)
from omnicontrol.runtime.pivots import plan_pivot_candidates
from omnicontrol.runtime.windows_ipc import TopLevelWindowInfo


class LiveSmokeHelperTests(unittest.TestCase):
    def test_resolve_ide_spec_for_jetbrains_executable_prefers_batch_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "PyCharm"
            (root / "bin").mkdir(parents=True)
            (root / "product-info.json").write_text("{}", encoding="utf-8")
            (root / "bin" / "pycharm64.exe").write_text("stub", encoding="utf-8")
            (root / "bin" / "pycharm.bat").write_text("@echo off", encoding="utf-8")

            spec = _resolve_ide_spec(root / "bin" / "pycharm64.exe")

        self.assertEqual(spec["family"], "jetbrains")
        self.assertEqual(spec["install_root"], root)
        self.assertEqual(spec["launcher_path"], root / "bin" / "pycharm.bat")

    def test_resolve_ide_spec_for_code_family_directory_prefers_cli_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Cursor"
            (root / "bin").mkdir(parents=True)
            (root / "bin" / "cursor.cmd").write_text("@echo off", encoding="utf-8")

            spec = _resolve_ide_spec(root)
            command = _build_ide_open_command(
                family=spec["family"],
                launcher_path=spec["launcher_path"],
                target=root / "workspace",
                isolated_user_data_dir=root / "user-data",
            )

        self.assertEqual(spec["family"], "code_family")
        self.assertEqual(spec["launcher_path"], root / "bin" / "cursor.cmd")
        self.assertEqual(command[:3], ["cmd", "/c", str(root / "bin" / "cursor.cmd")])
        self.assertIn("--new-window", command)
        self.assertIn("--user-data-dir", command)

    def test_resolve_ide_spec_for_code_family_executable_prefers_cli_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Code"
            (root / "bin").mkdir(parents=True)
            (root / "Code.exe").write_text("stub", encoding="utf-8")
            (root / "bin" / "code.cmd").write_text("@echo off", encoding="utf-8")

            spec = _resolve_ide_spec(root / "Code.exe")

        self.assertEqual(spec["family"], "code_family")
        self.assertEqual(spec["launcher_path"], root / "bin" / "code.cmd")

    def test_ide_family_helpers_recognize_jetbrains_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "WebStorm"
            (root / "bin").mkdir(parents=True)
            (root / "product-info.json").write_text("{}", encoding="utf-8")
            (root / "bin" / "webstorm.bat").write_text("@echo off", encoding="utf-8")
            (root / "bin" / "webstorm64.exe").write_text("stub", encoding="utf-8")

            family = _detect_ide_family(root / "bin" / "webstorm64.exe")
            install_root = _detect_ide_install_root(root / "bin" / "webstorm64.exe")
            launcher = _resolve_jetbrains_launcher(root / "bin" / "webstorm64.exe", install_root)

        self.assertEqual(family, "jetbrains")
        self.assertEqual(install_root, root)
        self.assertEqual(launcher, root / "bin" / "webstorm.bat")

    def test_ide_window_matching_uses_target_tokens(self) -> None:
        tokens = _ide_target_tokens(Path(r"D:\workspace\demo\probe.py"))
        self.assertIn("probe.py", tokens)
        self.assertTrue(_ide_window_matches_target("probe.py - demo", tokens))
        self.assertFalse(_ide_window_matches_target("probe.py - another", tokens))
        self.assertFalse(_ide_window_matches_target("README.md - another", tokens))

    def test_select_ide_target_window_allows_unique_filename_match(self) -> None:
        tokens = _ide_target_tokens(Path(r"D:\workspace\demo\probe.py"))
        selected = _select_ide_target_window(
            [
                TopLevelWindowInfo(
                    hwnd=101,
                    process_id=1,
                    class_name="SunAwtFrame",
                    title="probe.py",
                    visible=True,
                ),
            ],
            tokens,
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.hwnd, 101)

    def test_select_ide_target_window_prefers_new_window_when_titles_collide(self) -> None:
        tokens = _ide_target_tokens(Path(r"D:\workspace\demo\probe.py"))
        before_window = TopLevelWindowInfo(
            hwnd=101,
            process_id=1,
            class_name="Chrome_WidgetWin_1",
            title="probe.py - Visual Studio Code",
            visible=True,
        )
        selected = _select_ide_target_window(
            [
                before_window,
                TopLevelWindowInfo(
                    hwnd=202,
                    process_id=2,
                    class_name="Chrome_WidgetWin_1",
                    title="probe.py - Visual Studio Code",
                    visible=True,
                ),
            ],
            tokens,
            before_process_ids=[before_window.process_id],
            before_windows=[before_window],
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.hwnd, 202)

    def test_ide_project_context_omits_project_dir_for_jetbrains_file_targets(self) -> None:
        target = Path(r"D:\workspace\demo\probe.py")
        self.assertIsNone(_ide_project_context(target, family="jetbrains"))
        self.assertEqual(_ide_project_context(target, family="code_family"), target.parent)

    def test_build_ide_open_command_adds_line_and_column_for_jetbrains(self) -> None:
        command = _build_ide_open_command(
            family="jetbrains",
            launcher_path=Path(r"D:\PyCharm\bin\pycharm.bat"),
            project_path=Path(r"D:\workspace\demo"),
            target=Path(r"D:\workspace\demo\probe.py"),
            line=12,
            column=3,
        )
        self.assertEqual(
            command,
            [
                "cmd",
                "/c",
                r"D:\PyCharm\bin\pycharm.bat",
                r"D:\workspace\demo",
                "--line",
                "12",
                "--column",
                "3",
                r"D:\workspace\demo\probe.py",
            ],
        )

    def test_build_ide_open_command_uses_goto_for_code_family(self) -> None:
        command = _build_ide_open_command(
            family="code_family",
            launcher_path=Path(r"D:\Cursor\bin\cursor.cmd"),
            project_path=Path(r"D:\workspace\demo"),
            target=Path(r"D:\workspace\demo\probe.py"),
            isolated_user_data_dir=Path(r"D:\workspace\demo\.user-data"),
            line=7,
            column=2,
        )
        self.assertEqual(
            command,
            [
                "cmd",
                "/c",
                r"D:\Cursor\bin\cursor.cmd",
                "--new-window",
                "--disable-extensions",
                "--user-data-dir",
                r"D:\workspace\demo\.user-data",
                "--goto",
                r"D:\workspace\demo\probe.py:7:2",
            ],
        )

    def test_apply_safe_ide_file_write_appends_python_comment_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "probe.py"
            target.write_text("print('hello')\n", encoding="utf-8")

            payload = _apply_safe_ide_file_write(
                target=target,
                marker="Marker123",
            )

            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["transport"], "file_format")
            self.assertEqual(payload["marker_line_text"], "# Marker123")
            self.assertEqual(payload["marker_line"], 2)
            self.assertIn("Marker123", target.read_text(encoding="utf-8"))

    def test_detect_ide_blockers_flags_license_prompts(self) -> None:
        blockers = _detect_ide_blockers(
            ["Welcome to PyCharm", "Your Pro subscription expired"],
        )
        self.assertEqual(blockers, ["ide license dialog blocked the editor"])

    def test_collect_ide_log_blockers_flags_update_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs" / "20260416T163537"
            log_dir.mkdir(parents=True)
            (log_dir / "main.log").write_text(
                "Error: Code is currently being updated. Please wait.",
                encoding="utf-8",
            )
            blockers = _collect_ide_log_blockers(Path(tmp))
        self.assertEqual(blockers, ["ide update in progress blocked the editor"])

    def test_extract_jetbrains_mcp_port_reads_enabled_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "mcpServer.xml"
            config.write_text(
                "\n".join(
                    [
                        "<application>",
                        '  <component name="McpServerSettings">',
                        '    <option name="enableMcpServer" value="true" />',
                        '    <option name="mcpServerPort" value="65001" />',
                        "  </component>",
                        "</application>",
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(_extract_jetbrains_mcp_port(config), 65001)

    def test_extract_jetbrains_mcp_port_ignores_disabled_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "mcpServer.xml"
            config.write_text(
                "\n".join(
                    [
                        "<application>",
                        '  <component name="McpServerSettings">',
                        '    <option name="enableMcpServer" value="false" />',
                        '    <option name="mcpServerPort" value="65001" />',
                        "  </component>",
                        "</application>",
                    ]
                ),
                encoding="utf-8",
            )
            self.assertIsNone(_extract_jetbrains_mcp_port(config))

    def test_decode_mcp_tool_result_prefers_structured_content(self) -> None:
        payload = {
            "result": {
                "content": [{"type": "text", "text": '{"ignored":true}'}],
                "structuredContent": {"activeFilePath": "demo.py", "openFiles": ["demo.py"]},
            }
        }
        self.assertEqual(
            _decode_mcp_tool_result(payload),
            {"activeFilePath": "demo.py", "openFiles": ["demo.py"]},
        )

    def test_run_cmd_chain_handles_called_batch_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch_path = Path(tmp) / "hello world.cmd"
            batch_path.write_text("@echo off\necho HELLO_SIDE\n", encoding="utf-8")
            result = _run_cmd_chain(
                [
                    ["call", batch_path],
                    ["echo", "DONE_SIDE"],
                ],
                timeout=30,
            )
        self.assertEqual(result.returncode, 0)
        output = (result.stdout or "") + (result.stderr or "")
        self.assertIn("HELLO_SIDE", output)
        self.assertIn("DONE_SIDE", output)

    def test_build_sidecar_partial_payload_carries_primary_blockers(self) -> None:
        payload = _build_sidecar_partial_payload(
            raw_payload={"blockers": ["license blocked"]},
            success=True,
            action="vendor_tooling_plane",
            entrypoint="tool.exe -help",
            output_key="tool_output",
            output_text="tool ready",
            command="tool.exe -help",
            returncode=0,
            failure_blockers=["tool failed"],
            carry_note="primary runtime still blocked",
            extra={"tool_ready": True},
        )
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["secondary_action"], "vendor_tooling_plane")
        self.assertTrue(payload["secondary_action_ok"])
        self.assertEqual(
            payload["blockers"],
            ["license blocked", "primary runtime still blocked"],
        )
        self.assertTrue(payload["tool_ready"])

    def test_metadata_secondary_profile_action_map_matches_planned_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            cases = [
                ("word-workflow", ["runtime"], {}, "switch_to_secondary_entrypoint"),
                ("chrome-form-write", ["runtime"], {}, "switch_to_secondary_entrypoint"),
                ("chrome-workflow", ["runtime"], {}, "switch_to_secondary_entrypoint"),
                ("ue-python-write", ["runtime"], {}, "switch_to_tooling_plane"),
                ("quark-workflow", ["runtime"], {}, "switch_to_secondary_entrypoint"),
                ("trae-cdp-write", ["runtime"], {"workspace": workspace}, "switch_to_tooling_plane"),
                ("trae-workflow", ["runtime"], {"workspace": workspace}, "switch_to_tooling_plane"),
                ("ide-write", ["runtime"], {"source": root / "sample.py"}, "switch_to_secondary_entrypoint"),
                ("quark-cdp-write", ["runtime"], {}, "switch_to_secondary_entrypoint"),
                ("masterpdf-zoom", ["runtime"], {"source": root / "sample.pdf"}, "switch_to_secondary_entrypoint"),
                ("masterpdf-workflow", ["runtime"], {"source": root / "sample.pdf"}, "switch_to_secondary_entrypoint"),
                ("cadv-zoom", ["runtime"], {"source": root / "sample.dwg"}, "switch_to_secondary_entrypoint"),
                ("cadv-workflow", ["runtime"], {"source": root / "sample.dwg"}, "switch_to_secondary_entrypoint"),
            ]
            for profile, blocker_types, kwargs, expected_action in cases:
                with self.subTest(profile=profile):
                    candidates = plan_pivot_candidates(profile, {"strategy": {"blocker_types": blocker_types}})
                    self.assertIn(expected_action, [candidate.action for candidate in candidates])
                    action_map = _metadata_secondary_profile_action_map(
                        profile,
                        raw_payload={"status": "blocked", "blockers": ["primary blocked"]},
                        output_dir=root / profile,
                        **kwargs,
                    )
                    self.assertIn(expected_action, action_map)
                    self.assertIsNotNone(action_map[expected_action]())

    def test_secondary_profile_attempt_returns_partial_and_keeps_primary_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            action_map = _metadata_secondary_profile_action_map(
                "ue-python-write",
                raw_payload={"status": "blocked", "blockers": ["write failed"]},
                output_dir=Path(tmp),
            )
            attempt = action_map["switch_to_tooling_plane"]()
            self.assertIsNotNone(attempt)
            with patch(
                "omnicontrol.runtime.live_smoke.run_smoke",
                return_value={
                    "status": "partial",
                    "blockers": ["editor help only"],
                    "report_path": str(Path(tmp) / "sidecar-result.json"),
                    "orchestration": {"selected_attempt": "ue_buildpatch_help"},
                    "strategy": {"status": "partial", "blocker_types": ["runtime"]},
                },
            ):
                payload = attempt.run()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["secondary_profile"], "ue-diagnose")
        self.assertEqual(payload["secondary_profile_status"], "partial")
        self.assertEqual(payload["secondary_profile_selected_attempt"], "ue_buildpatch_help")
        self.assertEqual(
            payload["blockers"],
            ["editor help only", "primary UE Python write path still blocked", "write failed"],
        )

    def test_secondary_profile_attempt_uses_source_arg_when_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.pdf"
            source.write_text("stub", encoding="utf-8")
            action_map = _metadata_secondary_profile_action_map(
                "masterpdf-zoom",
                raw_payload={"status": "blocked", "blockers": ["zoom failed"]},
                output_dir=root / "out",
                source=source,
            )
            attempt = action_map["switch_to_secondary_entrypoint"]()
            self.assertIsNotNone(attempt)
            with patch(
                "omnicontrol.runtime.live_smoke.run_smoke",
                return_value={"status": "ok", "report_path": str(root / "sidecar-result.json")},
            ) as run_smoke:
                payload = attempt.run()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["secondary_profile"], "masterpdf-pagedown")
        run_smoke.assert_called_once()
        self.assertEqual(run_smoke.call_args.kwargs["source"], str(source))

    def test_secondary_profile_attempt_can_omit_output_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_map = _metadata_secondary_profile_action_map(
                "word-workflow",
                raw_payload={"status": "blocked", "blockers": ["workflow failed"]},
                output_dir=root / "out",
            )
            attempt = action_map["switch_to_secondary_entrypoint"]()
            self.assertIsNotNone(attempt)
            with patch(
                "omnicontrol.runtime.live_smoke.run_smoke",
                return_value={"status": "ok", "report_path": str(root / "sidecar-result.json")},
            ) as run_smoke:
                payload = attempt.run()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["secondary_profile"], "word-write")
        run_smoke.assert_called_once()
        self.assertNotIn("output", run_smoke.call_args.kwargs)

    def test_secondary_profile_attempt_can_pass_url_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(
                PROFILE_METADATA,
                {
                    "demo-url-primary": {
                        "product_key": "demo_web",
                        "software_type": "demo_type",
                        "target_kind": "web",
                        "platform": "windows",
                        "control_planes": ["cdp"],
                        "tags": ["write"],
                    },
                    "demo-url-read": {
                        "product_key": "demo_web",
                        "software_type": "demo_type",
                        "target_kind": "web",
                        "platform": "windows",
                        "control_planes": ["cdp"],
                        "tags": ["read"],
                    },
                },
            ), patch.dict(
                PROFILE_INTERACTION_LEVEL,
                {
                    "demo-url-primary": "write",
                    "demo-url-read": "read",
                },
            ), patch.dict(
                PROFILE_INVOCATION_CONTEXT,
                {
                    "demo-url-primary": "url",
                    "demo-url-read": "none",
                },
            ), patch.dict(
                PROFILE_ACCEPTED_INVOCATION_CONTEXTS,
                {
                    "demo-url-primary": ("url",),
                    "demo-url-read": ("none", "url"),
                },
            ):
                action_map = _metadata_secondary_profile_action_map(
                    "demo-url-primary",
                    raw_payload={"status": "blocked", "blockers": ["url write failed"]},
                    output_dir=root / "out",
                    url="https://example.com",
                )
                attempt = action_map["switch_to_secondary_entrypoint"]()
                self.assertIsNotNone(attempt)
                with patch(
                    "omnicontrol.runtime.live_smoke.run_smoke",
                    return_value={"status": "ok", "report_path": str(root / "sidecar-result.json")},
                ) as run_smoke:
                    payload = attempt.run()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["secondary_profile"], "demo-url-read")
        run_smoke.assert_called_once()
        self.assertEqual(run_smoke.call_args.kwargs["url"], "https://example.com")

    def test_secondary_profile_action_map_blocks_url_substitution_for_desktop_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(
                PROFILE_METADATA,
                {
                    "demo-desktop-primary": {
                        "product_key": "demo_desktop",
                        "software_type": "demo_desktop_type",
                        "target_kind": "desktop",
                        "platform": "windows",
                        "control_planes": ["native_script"],
                        "tags": ["write"],
                    },
                    "demo-web-sidecar": {
                        "product_key": "demo_desktop",
                        "software_type": "demo_web_type",
                        "target_kind": "web",
                        "platform": "windows",
                        "control_planes": ["cdp"],
                        "tags": ["read"],
                    },
                },
            ), patch.dict(
                PROFILE_INTERACTION_LEVEL,
                {
                    "demo-desktop-primary": "write",
                    "demo-web-sidecar": "read",
                },
            ), patch.dict(
                PROFILE_INVOCATION_CONTEXT,
                {
                    "demo-desktop-primary": "none",
                    "demo-web-sidecar": "url",
                },
            ), patch.dict(
                PROFILE_ACCEPTED_INVOCATION_CONTEXTS,
                {
                    "demo-desktop-primary": ("none",),
                    "demo-web-sidecar": ("url",),
                },
            ):
                action_map = _metadata_secondary_profile_action_map(
                    "demo-desktop-primary",
                    raw_payload={"status": "blocked", "blockers": ["desktop control failed"]},
                    output_dir=root / "out",
                    url="https://example.com",
                )
        self.assertEqual(action_map, {})

    def test_qqmusic_select_candidate_prefers_exact_title_and_singer(self) -> None:
        candidate = _qqmusic_select_candidate(
            "林俊杰 不存在的情人",
            [
                {"id": "2", "name": "不存在的爱人", "singer": "别人", "mid": "mid2"},
                {"id": "1", "name": "不存在的情人", "singer": "林俊杰", "mid": "mid1"},
            ],
        )
        self.assertEqual(candidate["id"], "1")

    def test_qqmusic_build_songinfo_payload_adds_file_aliases(self) -> None:
        payload = _qqmusic_build_songinfo_payload(
            {
                "id": 102388815,
                "type": 0,
                "mid": "004dqOA637OqwW",
                "name": "不存在的情人",
                "title": "不存在的情人",
                "interval": 243,
                "isonly": 0,
                "language": 0,
                "genre": 1,
                "index_cd": 0,
                "index_album": 11,
                "fnote": 4009,
                "time_public": "2011-12-31",
                "singer": [{"id": 4286, "mid": "001BLpXF2DyJe2", "title": "林俊杰"}],
                "album": {"id": 88971, "mid": "002PQCmo2azasb", "name": "学不会", "title": "学不会"},
                "mv": {"id": 81176, "vid": "j00223ucmzy"},
                "ksong": {"id": 50756, "mid": "0003wBtW2DVEmd"},
                "file": {
                    "media_mid": "004dkxa42XD2iU",
                    "size_192ogg": 5291260,
                    "size_128mp3": 3894325,
                    "size_320mp3": 9735514,
                    "size_ape": 0,
                    "size_flac": 26023450,
                    "size_dts": 0,
                    "size_try": 960887,
                    "try_begin": 61484,
                    "try_end": 99647,
                    "url": "",
                },
                "volume": {"gain": -9.104, "peak": 0.999, "lra": 14.715},
                "pay": {"pay_month": 1, "price_track": 200, "price_album": 0, "pay_play": 1, "pay_down": 1, "time_free": 0, "pay_status": 0},
                "action": {"switch": 16897793, "msgid": 13, "alert": 2},
            },
            source="2:1001:",
        )
        self.assertEqual(payload["file"]["size_128"], 3894325)
        self.assertEqual(payload["file"]["size_320"], 9735514)
        self.assertEqual(payload["source"], "2:1001:")
        self.assertIn("dl.stream.qqmusic.qq.com", payload["url"])

    def test_qqmusic_build_play_command_xml_uses_new_play_shape(self) -> None:
        xml = _qqmusic_build_play_command_xml(
            {
                "id": 102388815,
                "type": 0,
                "mid": "004dqOA637OqwW",
                "name": "不存在的情人",
                "title": "不存在的情人",
                "interval": 243,
                "isonly": 0,
                "language": 0,
                "genre": 1,
                "index_cd": 0,
                "index_album": 11,
                "fnote": 4009,
                "time_public": "2011-12-31",
                "singer": [{"id": 4286, "mid": "001BLpXF2DyJe2", "title": "林俊杰"}],
                "album": {"id": 88971, "mid": "002PQCmo2azasb", "name": "学不会", "title": "学不会"},
                "mv": {"id": 81176, "vid": "j00223ucmzy"},
                "ksong": {"id": 50756, "mid": "0003wBtW2DVEmd"},
                "file": {"media_mid": "004dkxa42XD2iU", "size_192ogg": 1, "size_128mp3": 2, "size_320mp3": 3, "size_ape": 0, "size_flac": 4, "size_dts": 0, "size_try": 5, "try_begin": 6, "try_end": 7},
                "volume": {"gain": -9.104, "peak": 0.999, "lra": 14.715},
                "pay": {"pay_month": 1, "price_track": 200, "price_album": 0, "pay_play": 1, "pay_down": 1, "time_free": 0, "pay_status": 0},
                "action": {"switch": 16897793, "msgid": 13, "alert": 2},
            }
        )
        self.assertIn('<cmd value="1002" verson="3">', xml)
        self.assertIn("<bsingle>1</bsingle>", xml)
        self.assertIn("<songinfo><![CDATA[[", xml)
        self.assertIn(_qqmusic_song_detail_url("004dqOA637OqwW"), xml)

    def test_qqmusic_control_script_lines_use_creator_and_method_specific_signatures(self) -> None:
        lines = _qqmusic_control_script_lines(
            method="WebExecCommand2",
            xml_path=Path(r"C:\temp\play.xml"),
        )
        script = "\n".join(lines)
        self.assertIn("QQMusicCreatorClass", script)
        self.assertIn('WebCreateInterface("IQQMusicControl")', script)
        self.assertIn("control.Bind();", script)
        self.assertIn('control.WebExecCommand2(commandXml, "")', script)

        probe_lines = _qqmusic_control_script_lines(
            method="CanWebExecCommand",
            xml_path=None,
        )
        probe_script = "\n".join(probe_lines)
        self.assertIn("[QQMusicControlBridge]::Invoke('CanWebExecCommand', '')", probe_script)
        self.assertNotIn("CanWebExecCommand($xml)", probe_script)

    def test_qqmusic_execute_control_methods_prefers_first_successful_web_method(self) -> None:
        attempts = iter(
            [
                {
                    "method": "CanWebExecCommand",
                    "returncode": 124,
                    "stdout": "",
                    "stderr": "probe timeout",
                    "command_ok": False,
                    "timed_out": True,
                    "powershell_path": "pwsh-probe",
                },
                {
                    "method": "WebExecCommand2",
                    "returncode": 124,
                    "stdout": "",
                    "stderr": "web2 timeout",
                    "command_ok": False,
                    "timed_out": True,
                    "powershell_path": "pwsh-web2",
                },
                {
                    "method": "WebExecCommand",
                    "returncode": 0,
                    "stdout": "RETURN=True",
                    "stderr": "",
                    "command_ok": True,
                    "timed_out": False,
                    "powershell_path": "pwsh-web",
                },
            ]
        )
        with patch(
            "omnicontrol.runtime.live_smoke._qqmusic_execute_control_command",
            side_effect=lambda *args, **kwargs: next(attempts),
        ):
            payload = _qqmusic_execute_control_methods("<xml/>")
        self.assertTrue(payload["command_ok"])
        self.assertEqual(payload["method"], "WebExecCommand")
        self.assertEqual(payload["powershell_path"], "pwsh-web")
        self.assertEqual(payload["command_probe"]["method"], "CanWebExecCommand")
        self.assertEqual(
            [attempt["method"] for attempt in payload["command_attempts"]],
            ["WebExecCommand2", "WebExecCommand"],
        )

    def test_qqmusic_execute_control_methods_respects_learned_method_order(self) -> None:
        attempts = iter(
            [
                {
                    "method": "CanWebExecCommand",
                    "returncode": 124,
                    "stdout": "",
                    "stderr": "probe timeout",
                    "command_ok": False,
                    "timed_out": True,
                    "powershell_path": "pwsh-probe",
                },
                {
                    "method": "ExecuteCommand",
                    "returncode": 0,
                    "stdout": "RETURN=True",
                    "stderr": "",
                    "command_ok": True,
                    "timed_out": False,
                    "powershell_path": "pwsh-exec",
                },
            ]
        )
        with patch(
            "omnicontrol.runtime.live_smoke.recommended_launch_overrides",
            return_value={"preferred_command_methods": ["ExecuteCommand", "WebExecCommand2"]},
        ), patch(
            "omnicontrol.runtime.live_smoke._qqmusic_execute_control_command",
            side_effect=lambda *args, **kwargs: next(attempts),
        ):
            payload = _qqmusic_execute_control_methods("<xml/>")
        self.assertTrue(payload["command_ok"])
        self.assertEqual(payload["method"], "ExecuteCommand")
        self.assertEqual(
            [attempt["method"] for attempt in payload["command_attempts"]],
            ["ExecuteCommand"],
        )

    def test_qqmusic_execute_transport_variants_prefers_software_native_paths(self) -> None:
        calls: list[str] = []

        def tencent_protocol(**_: object) -> dict:
            calls.append("tencent_protocol")
            return {
                "method": "tencent_protocol_file:playsong_query",
                "command_ok": False,
                "command_attempts": [{"method": "tencent_protocol_file:playsong_query", "command_ok": False}],
                "command_probe": {},
                "learned_overrides": {},
                "stdout": "",
                "stderr": "not verified",
                "powershell_path": "",
            }

        def private_protocol(**_: object) -> dict:
            calls.append("private_protocol")
            return {
                "method": "parsexml_legacy_proto1@null",
                "command_ok": False,
                "command_attempts": [{"method": "parsexml_legacy_proto1@null", "command_ok": False}],
                "command_probe": {"target_hwnd": 1},
                "learned_overrides": {},
                "stdout": "",
                "stderr": "not verified",
                "powershell_path": "",
            }

        def vendor_command(xml: str) -> dict:
            calls.append(xml)
            return {
                "method": "ExecuteCommand",
                "command_ok": True,
                "command_attempts": [{"method": "ExecuteCommand", "command_ok": True}],
                "command_probe": {"method": "CanWebExecCommand", "command_ok": False},
                "learned_overrides": {},
                "stdout": "",
                "stderr": "",
                "powershell_path": "pwsh",
            }

        with patch(
            "omnicontrol.runtime.live_smoke.recommended_launch_overrides",
            return_value={},
        ), patch(
            "omnicontrol.runtime.live_smoke._qqmusic_execute_tencent_protocol",
            side_effect=tencent_protocol,
        ), patch(
            "omnicontrol.runtime.live_smoke._qqmusic_execute_private_protocol",
            side_effect=private_protocol,
        ), patch(
            "omnicontrol.runtime.live_smoke._qqmusic_execute_control_methods",
            side_effect=vendor_command,
        ):
            payload = _qqmusic_execute_transport_variants(
                qqmusic_path=Path(r"C:\Program Files (x86)\Tencent\QQMusic\QQMusic.exe"),
                song_id=268880289,
                song_mid="003uy66u0GEiYW",
                legacy_xml="legacy",
                legacy_xml_path=r"C:\\legacy.xml",
                runtime_session={},
                runtime_auth_xml=None,
                expected_title="song",
                expected_singer="artist",
            )
        self.assertEqual(calls, ["tencent_protocol", "private_protocol", "legacy"])
        self.assertTrue(payload["command_ok"])
        self.assertEqual(payload["transport_variant"], "legacy_jump_xml")
        self.assertEqual(payload["transport_plan"], ["tencent_protocol", "private_protocol", "legacy_jump_xml"])
        self.assertEqual(payload["suppressed_transport_variants"], ["new_play"])
        self.assertEqual(len(payload["transport_attempts"]), 3)


if __name__ == "__main__":
    unittest.main()
