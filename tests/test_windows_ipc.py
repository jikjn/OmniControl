from __future__ import annotations

import ctypes
import unittest
from unittest.mock import patch

from omnicontrol.runtime.windows_ipc import (
    WM_CLOSE,
    WM_COPYDATA,
    TopLevelWindowInfo,
    TaggedPacketSpec,
    build_tagged_packet,
    close_top_level_windows,
    encode_utf16le_text,
    find_process_ids,
    find_window_handle,
    list_top_level_windows,
    send_window_message,
    send_wm_copydata,
)


@unittest.skipUnless(hasattr(ctypes, "WinDLL"), "requires Windows ctypes.WinDLL support")
class WindowsIPCHelperTests(unittest.TestCase):
    def test_encode_utf16le_text_can_append_null(self) -> None:
        payload = encode_utf16le_text("abc")
        self.assertEqual(payload, b"a\x00b\x00c\x00\x00\x00")

    def test_build_tagged_packet_uses_expected_header_shape(self) -> None:
        packet = build_tagged_packet(
            b"payload",
            TaggedPacketSpec(tag="QMAS", version=100, proto_type=7),
        )
        self.assertEqual(int.from_bytes(packet[0:4], "little"), 12 + len(b"payload"))
        self.assertEqual(packet[4:8], b"QMAS")
        self.assertEqual(int.from_bytes(packet[8:10], "little"), 100)
        self.assertEqual(int.from_bytes(packet[10:12], "little"), 7)
        self.assertEqual(packet[12:], b"payload")

    def test_build_tagged_packet_supports_extended_header_shape(self) -> None:
        packet = build_tagged_packet(
            b"payload",
            TaggedPacketSpec(
                tag="QMAS",
                version=100,
                proto_type=4,
                header_layout="u32_u32_u16_u16_u32",
                extra_u32=1002,
            ),
        )
        self.assertEqual(int.from_bytes(packet[0:4], "little"), 16 + len(b"payload"))
        self.assertEqual(packet[4:8], b"QMAS")
        self.assertEqual(int.from_bytes(packet[8:10], "little"), 100)
        self.assertEqual(int.from_bytes(packet[10:12], "little"), 4)
        self.assertEqual(int.from_bytes(packet[12:16], "little"), 1002)
        self.assertEqual(packet[16:], b"payload")

    def test_find_window_handle_returns_zero_for_missing_window(self) -> None:
        self.assertEqual(
            find_window_handle(class_name="DefinitelyMissingWindowClass", title="DefinitelyMissingWindowTitle"),
            0,
        )

    def test_find_process_ids_filters_matching_image_name(self) -> None:
        with patch(
            "omnicontrol.runtime.windows_ipc._iter_process_entries",
            return_value=[
                {"process_id": 101, "image_name": "QQMusic.exe"},
                {"process_id": 202, "image_name": "Other.exe"},
                {"process_id": 303, "image_name": "qqmusic.exe"},
            ],
        ):
            self.assertEqual(find_process_ids("QQMusic.exe"), [101, 303])

    def test_list_top_level_windows_filters_by_process_and_visibility(self) -> None:
        windows = [
            TopLevelWindowInfo(hwnd=1, process_id=10, class_name="Main", title="Main Window", visible=True),
            TopLevelWindowInfo(hwnd=2, process_id=10, class_name="Popup", title="Repair Popup", visible=True),
            TopLevelWindowInfo(hwnd=3, process_id=11, class_name="Other", title="Other", visible=False),
        ]
        with patch("omnicontrol.runtime.windows_ipc._iter_top_level_windows", return_value=windows):
            filtered = list_top_level_windows(process_ids=[10], visible_only=True)
        self.assertEqual([window.hwnd for window in filtered], [1, 2])

    def test_close_top_level_windows_respects_protection(self) -> None:
        windows = [
            TopLevelWindowInfo(hwnd=1, process_id=10, class_name="Main", title="Main Window", visible=True),
            TopLevelWindowInfo(hwnd=2, process_id=10, class_name="Popup", title="Repair Popup", visible=True),
        ]
        with patch(
            "omnicontrol.runtime.windows_ipc.send_window_message",
            return_value={
                "returncode": 1,
                "result": 0,
                "error_code": 0,
                "target_hwnd": 2,
                "sender_hwnd": 0,
                "message": WM_CLOSE,
                "timed_out": False,
            },
        ) as send_window_message_mock:
            payload = close_top_level_windows(
                windows=windows,
                protect_titles=["Main Window"],
            )
        self.assertEqual(payload["attempted"], 1)
        self.assertEqual(payload["closed"], 1)
        self.assertEqual(payload["skipped"][0]["title"], "Main Window")
        send_window_message_mock.assert_called_once()

    def test_send_wm_copydata_reports_basic_result_shape(self) -> None:
        payload = encode_utf16le_text("ping")
        result = send_wm_copydata(
            target_hwnd=0,
            payload=payload,
            timeout_ms=10,
        )
        self.assertEqual(result["payload_size"], len(payload))
        self.assertEqual(result["target_hwnd"], 0)
        self.assertIn("error_code", result)
        self.assertIn("timed_out", result)
        self.assertEqual(WM_COPYDATA, 0x004A)

    def test_send_window_message_reports_basic_result_shape(self) -> None:
        result = send_window_message(
            target_hwnd=0,
            message=WM_CLOSE,
            timeout_ms=10,
        )
        self.assertEqual(result["target_hwnd"], 0)
        self.assertEqual(result["message"], WM_CLOSE)
        self.assertIn("error_code", result)
        self.assertIn("timed_out", result)


if __name__ == "__main__":
    unittest.main()
