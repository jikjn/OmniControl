from __future__ import annotations

import argparse
import unittest

from omnicontrol.cli import build_parser
from omnicontrol.runtime.registry import (
    ProfileDescriptor,
    get_profile_descriptor,
    list_profile_ids,
    metadata_for_profile,
    profile_choices,
)


def _smoke_profile_action(parser: argparse.ArgumentParser) -> argparse.Action:
    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    smoke_parser = subparsers.choices["smoke"]
    return next(action for action in smoke_parser._actions if action.dest == "profile")


class RuntimeRegistryTests(unittest.TestCase):
    def test_parser_uses_registry_derived_smoke_choices(self) -> None:
        parser = build_parser()
        profile_action = _smoke_profile_action(parser)
        self.assertEqual(tuple(profile_action.choices), profile_choices())

    def test_registry_lists_existing_profile_ids(self) -> None:
        ids = list_profile_ids()
        self.assertIn("finder-open", ids)
        self.assertIn("word-workflow", ids)
        self.assertEqual(ids, profile_choices())

    def test_metadata_view_preserves_compatibility_fields(self) -> None:
        metadata = metadata_for_profile("safari-dom-write")
        self.assertEqual(metadata["product_key"], "safari")
        self.assertEqual(metadata["invocation_context"], "url")
        self.assertEqual(metadata["interaction_level"], "write")
        self.assertTrue(metadata["secondary_profiles"])

    def test_descriptor_is_typed(self) -> None:
        descriptor = get_profile_descriptor("finder-open")
        self.assertIsInstance(descriptor, ProfileDescriptor)
        self.assertEqual(descriptor.profile_id, "finder-open")
        self.assertEqual(descriptor.accepted_invocation_contexts, ("none", "source"))


if __name__ == "__main__":
    unittest.main()
