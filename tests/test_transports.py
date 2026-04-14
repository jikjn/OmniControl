from __future__ import annotations

import unittest

from omnicontrol.runtime.transports import (
    TransportDescriptor,
    TransportAttemptSpec,
    build_background_first_plan,
    build_software_native_plan,
    derive_preferred_order,
    rank_transport_descriptors,
    run_ordered_transport_attempts,
)


class TransportAttemptTests(unittest.TestCase):
    def test_rank_transport_descriptors_prefers_background_safe_paths(self) -> None:
        ranked = rank_transport_descriptors(
            [
                TransportDescriptor(
                    name="vision",
                    control_plane="vision",
                    background_safe=False,
                    requires_focus=True,
                    startup_cost=3,
                    probe_cost=3,
                    determinism=2,
                    observability=2,
                    side_effect_risk=4,
                ),
                TransportDescriptor(
                    name="vendor_command",
                    control_plane="vendor_command",
                    background_safe=True,
                    requires_focus=False,
                    startup_cost=1,
                    probe_cost=1,
                    determinism=5,
                    observability=4,
                    side_effect_risk=1,
                ),
            ]
        )
        self.assertEqual([descriptor.name for descriptor in ranked], ["vendor_command", "vision"])

    def test_build_background_first_plan_respects_preferred_order(self) -> None:
        plan = build_background_first_plan(
            [
                TransportDescriptor(name="vendor_command", control_plane="vendor_command"),
                TransportDescriptor(name="network_api", control_plane="network_api"),
                TransportDescriptor(name="uia", control_plane="uiautomation", requires_focus=True, background_safe=False),
            ],
            preferred_order=["network_api"],
        )
        self.assertEqual(plan, ["network_api", "vendor_command", "uia"])

    def test_build_software_native_plan_filters_web_substitute_variants(self) -> None:
        plan = build_software_native_plan(
            [
                TransportDescriptor(name="private_protocol", control_plane="private_protocol", software_native=True),
                TransportDescriptor(name="webview_navigation", control_plane="vendor_command", software_native=False),
                TransportDescriptor(name="legacy_vendor_command", control_plane="vendor_command", software_native=True),
            ],
            preferred_order=["webview_navigation", "private_protocol"],
        )
        self.assertEqual(plan, ["private_protocol", "legacy_vendor_command"])

    def test_run_ordered_transport_attempts_prefers_learned_order(self) -> None:
        calls: list[str] = []

        def attempt(name: str, ok: bool) -> dict:
            calls.append(name)
            return {"method": name, "command_ok": ok}

        payload = run_ordered_transport_attempts(
            [
                TransportAttemptSpec("alpha", lambda: attempt("alpha", False)),
                TransportAttemptSpec("beta", lambda: attempt("beta", True)),
            ],
            learned_order=["beta", "alpha"],
        )

        self.assertEqual(calls, ["beta"])
        self.assertEqual(payload["method"], "beta")
        self.assertEqual(payload["ordered_methods"], ["beta", "alpha"])

    def test_run_ordered_transport_attempts_keeps_probe_and_failures(self) -> None:
        payload = run_ordered_transport_attempts(
            [
                TransportAttemptSpec("alpha", lambda: {"method": "alpha", "command_ok": False}),
                TransportAttemptSpec("beta", lambda: {"method": "beta", "command_ok": False}),
            ],
            probe=lambda: {"method": "probe", "command_ok": False},
        )

        self.assertEqual(payload["method"], "alpha")
        self.assertEqual(payload["probe"]["method"], "probe")
        self.assertEqual([item["method"] for item in payload["attempts"]], ["alpha", "beta"])

    def test_derive_preferred_order_promotes_successful_entries(self) -> None:
        order = derive_preferred_order(
            [
                {"transport_variant": "new_play", "command_ok": False},
                {"transport_variant": "legacy_jump_xml", "command_ok": True},
                {"transport_variant": "new_play", "command_ok": False},
            ]
        )
        self.assertEqual(order, ["legacy_jump_xml", "new_play"])


if __name__ == "__main__":
    unittest.main()
