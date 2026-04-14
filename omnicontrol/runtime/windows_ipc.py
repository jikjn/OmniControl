from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
from typing import Any, Iterable


WM_COPYDATA = 0x004A
WM_CLOSE = 0x0010
SMTO_ABORTIFHUNG = 0x0002
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260


def encode_utf16le_text(text: str, *, null_terminated: bool = True) -> bytes:
    payload = text.encode("utf-16le")
    if null_terminated:
        payload += b"\x00\x00"
    return payload


@dataclass(slots=True)
class TaggedPacketSpec:
    tag: bytes | str
    version: int
    proto_type: int
    header_layout: str = "u32_u32_u16_u16"
    include_total_length: bool = True
    extra_u32: int = 0


@dataclass(slots=True)
class TopLevelWindowInfo:
    hwnd: int
    process_id: int
    class_name: str
    title: str
    visible: bool


def build_tagged_packet(payload: bytes, spec: TaggedPacketSpec) -> bytes:
    tag_value = _normalize_tag(spec.tag)
    if spec.header_layout == "u32_u32_u16_u16":
        header_parts = [
            int(tag_value).to_bytes(4, "little", signed=False),
            int(spec.version).to_bytes(2, "little", signed=False),
            int(spec.proto_type).to_bytes(2, "little", signed=False),
        ]
    elif spec.header_layout == "u32_u32_u16_u16_u32":
        header_parts = [
            int(tag_value).to_bytes(4, "little", signed=False),
            int(spec.version).to_bytes(2, "little", signed=False),
            int(spec.proto_type).to_bytes(2, "little", signed=False),
            int(spec.extra_u32).to_bytes(4, "little", signed=False),
        ]
    else:
        raise ValueError(f"Unsupported header layout: {spec.header_layout}")

    header_size = 4 + sum(len(part) for part in header_parts)
    total_length = header_size + len(payload)
    prefix = total_length if spec.include_total_length else len(payload)
    return b"".join(
        [
            int(prefix).to_bytes(4, "little", signed=False),
            *header_parts,
            payload,
        ]
    )


def find_window_handle(*, class_name: str | None = None, title: str | None = None) -> int:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    find_window = user32.FindWindowW
    find_window.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    find_window.restype = wintypes.HWND
    handle = find_window(class_name, title)
    return int(handle or 0)


def find_process_ids(image_name: str) -> list[int]:
    normalized_name = image_name.lower()
    return [
        int(entry["process_id"])
        for entry in _iter_process_entries()
        if str(entry["image_name"]).lower() == normalized_name
    ]


def list_top_level_windows(
    *,
    process_ids: Iterable[int] | None = None,
    visible_only: bool | None = None,
    title_contains: str | None = None,
    class_name: str | None = None,
) -> list[TopLevelWindowInfo]:
    process_id_set = {int(item) for item in (process_ids or [])}
    windows = []
    for window in _iter_top_level_windows():
        if process_id_set and window.process_id not in process_id_set:
            continue
        if visible_only is True and not window.visible:
            continue
        if visible_only is False and window.visible:
            continue
        if title_contains and title_contains not in window.title:
            continue
        if class_name and window.class_name != class_name:
            continue
        windows.append(window)
    return windows


def close_top_level_windows(
    *,
    windows: Iterable[TopLevelWindowInfo],
    protect_hwnds: Iterable[int] = (),
    protect_classes: Iterable[str] = (),
    protect_titles: Iterable[str] = (),
    timeout_ms: int = 1000,
    dry_run: bool = False,
) -> dict[str, Any]:
    protected_hwnds = {int(hwnd) for hwnd in protect_hwnds}
    protected_classes = {str(item) for item in protect_classes if str(item)}
    protected_titles = {str(item) for item in protect_titles if str(item)}

    attempted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    closed = 0
    for window in windows:
        if (
            window.hwnd in protected_hwnds
            or window.class_name in protected_classes
            or window.title in protected_titles
        ):
            skipped.append(
                {
                    "hwnd": window.hwnd,
                    "process_id": window.process_id,
                    "class_name": window.class_name,
                    "title": window.title,
                    "reason": "protected",
                }
            )
            continue

        result = {
            "hwnd": window.hwnd,
            "process_id": window.process_id,
            "class_name": window.class_name,
            "title": window.title,
            "dry_run": dry_run,
        }
        if not dry_run:
            message_result = send_window_message(
                target_hwnd=window.hwnd,
                message=WM_CLOSE,
                timeout_ms=timeout_ms,
            )
            result.update(message_result)
            if message_result["returncode"] != 0 and not message_result["timed_out"]:
                closed += 1
        attempted.append(result)

    return {
        "attempted": len(attempted),
        "closed": closed,
        "skipped": skipped,
        "results": attempted,
        "dry_run": dry_run,
    }


def send_window_message(
    *,
    target_hwnd: int,
    message: int,
    sender_hwnd: int = 0,
    w_param: int = 0,
    l_param: int = 0,
    timeout_ms: int = 1000,
    flags: int = SMTO_ABORTIFHUNG,
) -> dict[str, Any]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    send_message_timeout = user32.SendMessageTimeoutW
    send_message_timeout.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(wintypes.DWORD),
    ]
    send_message_timeout.restype = wintypes.LPARAM

    result = wintypes.DWORD()
    ret = send_message_timeout(
        int(target_hwnd),
        int(message),
        int(w_param or sender_hwnd),
        int(l_param),
        int(flags),
        int(timeout_ms),
        ctypes.byref(result),
    )
    error_code = ctypes.get_last_error()
    return {
        "returncode": int(ret),
        "result": int(result.value),
        "error_code": int(error_code),
        "target_hwnd": int(target_hwnd),
        "sender_hwnd": int(sender_hwnd),
        "message": int(message),
        "timed_out": int(ret) == 0 and error_code == 1460,
    }


def send_wm_copydata(
    *,
    target_hwnd: int,
    sender_hwnd: int = 0,
    payload: bytes,
    dw_data: int = 0,
    timeout_ms: int = 1000,
    flags: int = SMTO_ABORTIFHUNG,
) -> dict[str, Any]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    send_message_timeout = user32.SendMessageTimeoutW
    send_message_timeout.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(wintypes.DWORD),
    ]
    send_message_timeout.restype = wintypes.LPARAM

    class COPYDATASTRUCT(ctypes.Structure):
        _fields_ = [
            ("dwData", wintypes.LPARAM),
            ("cbData", wintypes.DWORD),
            ("lpData", ctypes.c_void_p),
        ]

    payload_buffer = ctypes.create_string_buffer(payload)
    cds = COPYDATASTRUCT(
        dw_data,
        len(payload),
        ctypes.cast(payload_buffer, ctypes.c_void_p).value,
    )
    result = wintypes.DWORD()
    ret = send_message_timeout(
        int(target_hwnd),
        WM_COPYDATA,
        int(sender_hwnd),
        ctypes.addressof(cds),
        int(flags),
        int(timeout_ms),
        ctypes.byref(result),
    )
    error_code = ctypes.get_last_error()
    return {
        "returncode": int(ret),
        "result": int(result.value),
        "error_code": int(error_code),
        "target_hwnd": int(target_hwnd),
        "sender_hwnd": int(sender_hwnd),
        "dw_data": int(dw_data),
        "payload_size": len(payload),
        "timed_out": int(ret) == 0 and error_code == 1460,
    }


def _normalize_tag(tag: bytes | str) -> int:
    if isinstance(tag, str):
        tag = tag.encode("ascii")
    if len(tag) != 4:
        raise ValueError("Tag must be exactly 4 bytes")
    return int.from_bytes(tag, "little", signed=False)


def _iter_process_entries() -> list[dict[str, Any]]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    process_first = kernel32.Process32FirstW
    process_first.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    process_first.restype = wintypes.BOOL
    process_next = kernel32.Process32NextW
    process_next.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    process_next.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * MAX_PATH),
        ]

    snapshot = create_snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or int(snapshot) == int(INVALID_HANDLE_VALUE):
        return []

    entries: list[dict[str, Any]] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not process_first(snapshot, ctypes.byref(entry)):
            return []
        while True:
            entries.append(
                {
                    "process_id": int(entry.th32ProcessID),
                    "image_name": str(entry.szExeFile),
                }
            )
            if not process_next(snapshot, ctypes.byref(entry)):
                break
    finally:
        close_handle(snapshot)
    return entries


def _iter_top_level_windows() -> list[TopLevelWindowInfo]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_windows = user32.EnumWindows
    get_window_text = user32.GetWindowTextW
    get_class_name = user32.GetClassNameW
    is_window_visible = user32.IsWindowVisible
    get_window_thread_process_id = user32.GetWindowThreadProcessId

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    enum_windows.argtypes = [callback_type, wintypes.LPARAM]
    enum_windows.restype = wintypes.BOOL
    get_window_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    get_window_text.restype = ctypes.c_int
    get_class_name.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    get_class_name.restype = ctypes.c_int
    is_window_visible.argtypes = [wintypes.HWND]
    is_window_visible.restype = wintypes.BOOL
    get_window_thread_process_id.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    get_window_thread_process_id.restype = wintypes.DWORD

    windows: list[TopLevelWindowInfo] = []

    @callback_type
    def callback(hwnd: int, _l_param: int) -> bool:
        process_id = wintypes.DWORD()
        get_window_thread_process_id(hwnd, ctypes.byref(process_id))
        title_buffer = ctypes.create_unicode_buffer(512)
        class_buffer = ctypes.create_unicode_buffer(256)
        get_window_text(hwnd, title_buffer, len(title_buffer))
        get_class_name(hwnd, class_buffer, len(class_buffer))
        windows.append(
            TopLevelWindowInfo(
                hwnd=int(hwnd),
                process_id=int(process_id.value),
                class_name=class_buffer.value,
                title=title_buffer.value,
                visible=bool(is_window_visible(hwnd)),
            )
        )
        return True

    enum_windows(callback, 0)
    return windows
