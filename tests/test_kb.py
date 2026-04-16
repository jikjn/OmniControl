from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from omnicontrol.runtime.kb import (
    PROFILE_INTERACTION_LEVEL,
    PROFILE_INVOCATION_CONTEXT,
    PROFILE_METADATA,
    PROFILE_ACCEPTED_INVOCATION_CONTEXTS,
    accepted_invocation_contexts,
    control_plane_weight,
    infer_secondary_profiles,
    kb_path,
    load_kb,
    save_kb,
    secondary_profile_specs,
    _launch_overrides,
)
from omnicontrol.runtime.contracts import SMOKE_CONTRACTS


class KnowledgeBaseProfileFamilyTests(unittest.TestCase):
    def test_infer_secondary_profiles_finds_lighter_siblings(self) -> None:
        with patch.dict(
            PROFILE_METADATA,
            {
                "demo-workflow": {
                    "product_key": "demo_suite",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["existing_cli", "cdp"],
                    "tags": ["workflow"],
                },
                "demo-write": {
                    "product_key": "demo_suite",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["cdp"],
                    "tags": ["write"],
                },
                "demo-open": {
                    "product_key": "demo_suite",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["existing_cli"],
                    "tags": ["open"],
                },
            },
        ), patch.dict(
            PROFILE_INTERACTION_LEVEL,
            {
                "demo-workflow": "workflow",
                "demo-write": "write",
                "demo-open": "open",
            },
        ), patch.dict(
            PROFILE_INVOCATION_CONTEXT,
            {
                "demo-workflow": "workspace",
                "demo-write": "workspace",
                "demo-open": "workspace",
            },
        ):
            specs = infer_secondary_profiles("demo-workflow")

        by_profile = {spec["profile"]: spec for spec in specs}
        self.assertIn("demo-write", by_profile)
        self.assertIn("demo-open", by_profile)
        self.assertEqual(by_profile["demo-write"]["action"], "switch_to_secondary_entrypoint")
        self.assertEqual(by_profile["demo-open"]["action"], "switch_to_tooling_plane")

    def test_infer_secondary_profiles_respects_invocation_context(self) -> None:
        with patch.dict(
            PROFILE_METADATA,
            {
                "demo-write-no-source": {
                    "product_key": "demo_docs",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["cdp"],
                    "tags": ["write"],
                },
                "demo-export-source": {
                    "product_key": "demo_docs",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["cdp"],
                    "tags": ["export"],
                },
            },
        ), patch.dict(
            PROFILE_INTERACTION_LEVEL,
            {
                "demo-write-no-source": "write",
                "demo-export-source": "export",
            },
        ), patch.dict(
            PROFILE_INVOCATION_CONTEXT,
            {
                "demo-write-no-source": "none",
                "demo-export-source": "source",
            },
        ):
            specs = infer_secondary_profiles("demo-write-no-source")

        self.assertEqual(specs, [])

    def test_secondary_profile_specs_keep_explicit_mapping_over_inferred_same_action(self) -> None:
        with patch.dict(
            PROFILE_METADATA,
            {
                "demo-primary": {
                    "product_key": "demo_explicit",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["cdp"],
                    "tags": ["write"],
                    "secondary_profiles": [
                        {
                            "action": "switch_to_secondary_entrypoint",
                            "profile": "demo-explicit",
                            "attempt_name": "explicit_sidecar",
                            "strategy": "switch_to_secondary_entrypoint",
                        }
                    ],
                },
                "demo-explicit": {
                    "product_key": "demo_explicit",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["cdp"],
                    "tags": ["read"],
                },
                "demo-inferred": {
                    "product_key": "demo_explicit",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["cdp"],
                    "tags": ["read"],
                },
            },
        ), patch.dict(
            PROFILE_INTERACTION_LEVEL,
            {
                "demo-primary": "write",
                "demo-explicit": "read",
                "demo-inferred": "read",
            },
        ):
            specs = secondary_profile_specs("demo-primary")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["profile"], "demo-explicit")
        self.assertEqual(specs[0]["attempt_name"], "explicit_sidecar")

    def test_accepted_invocation_contexts_can_widen_compatibility(self) -> None:
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
            self.assertEqual(accepted_invocation_contexts("demo-url-read"), ("none", "url"))
            specs = infer_secondary_profiles("demo-url-primary")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["profile"], "demo-url-read")
        self.assertEqual(specs[0]["source_arg"], "url")

    def test_infer_secondary_profiles_blocks_url_substitution_for_desktop_profiles(self) -> None:
        with patch.dict(
            PROFILE_METADATA,
            {
                "demo-desktop-primary": {
                    "product_key": "demo_desktop",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["native_script"],
                    "tags": ["write"],
                },
                "demo-web-sidecar": {
                    "product_key": "demo_desktop",
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
            specs = infer_secondary_profiles("demo-desktop-primary")
        self.assertEqual(specs, [])

    def test_control_plane_weight_prefers_background_vendor_planes(self) -> None:
        with patch.dict(
            PROFILE_METADATA,
            {
                "demo-vendor": {
                    "product_key": "demo_vendor",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["network_api", "vendor_command"],
                    "tags": ["write"],
                },
                "demo-uia": {
                    "product_key": "demo_vendor",
                    "software_type": "demo_type",
                    "target_kind": "desktop",
                    "platform": "windows",
                    "control_planes": ["uiautomation", "vision"],
                    "tags": ["write"],
                },
            },
        ):
            self.assertLess(control_plane_weight("demo-vendor"), control_plane_weight("demo-uia"))

    def test_qqmusic_play_contract_does_not_require_screenshot_evidence(self) -> None:
        self.assertNotIn("screenshot", SMOKE_CONTRACTS["qqmusic-play"].evidence_keys)

    def test_launch_overrides_capture_generic_transport_and_method_order(self) -> None:
        overrides = _launch_overrides(
            {
                "transport_attempts": [
                    {"transport_variant": "new_play", "command_ok": False},
                    {"transport_variant": "legacy_jump_xml", "command_ok": True},
                ],
                "command_attempts": [
                    {"method": "WebExecCommand2", "command_ok": False},
                    {"method": "ExecuteCommand", "command_ok": True},
                ],
            }
        )
        self.assertEqual(overrides["preferred_transport_order"], ["legacy_jump_xml", "new_play"])
        self.assertEqual(overrides["preferred_transport_variants"], ["legacy_jump_xml", "new_play"])
        self.assertEqual(overrides["preferred_method_order"], ["ExecuteCommand", "WebExecCommand2"])
        self.assertEqual(overrides["preferred_command_methods"], ["ExecuteCommand", "WebExecCommand2"])

    def test_kb_path_uses_runtime_managed_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            resolved = kb_path(cwd=cwd)
        self.assertIn("knowledge", str(resolved))
        self.assertNotEqual(resolved, cwd / "knowledge" / "kb.json")

    def test_save_kb_round_trips_from_runtime_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            save_kb({"version": 1, "updated_at": None, "cases": []}, cwd=cwd)
            loaded = load_kb(cwd=cwd)
        self.assertEqual(loaded["version"], 1)


if __name__ == "__main__":
    unittest.main()
