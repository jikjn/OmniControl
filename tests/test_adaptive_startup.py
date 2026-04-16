from __future__ import annotations

import unittest

from omnicontrol.runtime.adaptive_startup import AdaptiveStartupInfo, extract_remote_debugging_port


class AdaptiveStartupTests(unittest.TestCase):
    def test_extract_remote_debugging_port(self) -> None:
        command = 'quark.exe --remote-debugging-port=45443 --remote-debugging-address=127.0.0.1'
        self.assertEqual(extract_remote_debugging_port(command), 45443)

    def test_startup_info_to_dict(self) -> None:
        info = AdaptiveStartupInfo(
            strategy="attach_existing_debug",
            process_group="quark",
            existing_process_count=2,
            attached_existing=True,
            debug_port=45443,
            launched_process_ids=[1234],
        )
        data = info.to_dict()
        self.assertEqual(data["strategy"], "attach_existing_debug")
        self.assertEqual(data["debug_port"], 45443)


if __name__ == "__main__":
    unittest.main()
