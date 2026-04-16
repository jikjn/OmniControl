from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import shutil
import socket
import subprocess
import time
from typing import Callable, Any


@dataclass(slots=True)
class AdaptiveStartupInfo:
    strategy: str
    process_group: str
    existing_process_count: int = 0
    cleaned_existing_count: int = 0
    attached_existing: bool = False
    debug_port: int | None = None
    user_data_dir: str | None = None
    launched_process_ids: list[int] = field(default_factory=list)
    window_count: int = 0
    window_titles: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_remote_debugging_port(command_line: str | None) -> int | None:
    if not command_line:
        return None
    marker = "--remote-debugging-port="
    if marker not in command_line:
        return None
    tail = command_line.split(marker, maxsplit=1)[1]
    digits = []
    for char in tail:
        if char.isdigit():
            digits.append(char)
        else:
            break
    if not digits:
        return None
    return int("".join(digits))


def adaptive_launch_cdp_app(
    *,
    app_path: Path,
    process_name: str,
    process_group: str,
    output_dir: Path,
    startup_args: list[str] | None = None,
    isolate_user_data: bool = True,
    allow_attach_existing: bool = True,
    clean_existing: bool = False,
) -> tuple[AdaptiveStartupInfo, subprocess.Popen | None]:
    startup_args = startup_args or []
    processes = _list_processes_by_name(process_name)
    info = AdaptiveStartupInfo(
        strategy="unresolved",
        process_group=process_group,
        existing_process_count=len(processes),
    )

    if allow_attach_existing:
        for process in processes:
            port = extract_remote_debugging_port(process.get("command_line"))
            if port is None:
                continue
            try:
                _wait_for_cdp(port, timeout=2.5)
            except RuntimeError:
                continue
            info.strategy = "attach_existing_debug"
            info.attached_existing = True
            info.debug_port = port
            info.launched_process_ids = [process["pid"]]
            info.diagnostics.append("Attached to an existing debuggable instance.")
            return info, None

    if clean_existing and processes:
        _terminate_processes([process["pid"] for process in processes])
        info.cleaned_existing_count = len(processes)
        info.diagnostics.append("Cleaned existing processes before relaunch.")
        time.sleep(1)

    port = pick_free_port()
    command = [str(app_path), f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1", *startup_args]
    user_data_dir = None
    if isolate_user_data and not any("--user-data-dir" in arg for arg in startup_args):
        user_data_dir = output_dir / "profile"
        _reset_dir(user_data_dir)
        command.insert(3, f"--user-data-dir={user_data_dir}")
        info.user_data_dir = str(user_data_dir)

    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _wait_for_cdp(port)
    launched = _list_processes_by_name(process_name)
    info.strategy = "restart_with_debug_port"
    info.debug_port = port
    info.launched_process_ids = [process["pid"] for process in launched]
    info.diagnostics.append("Launched a fresh debuggable instance.")
    return info, proc


def adaptive_launch_cli_window_app(
    *,
    process_name: str,
    process_group: str,
    output_dir: Path,
    workspace: Path,
    command_builder: Callable[[Path], list[str]],
    clean_existing: bool = True,
    wait_seconds: float = 12.0,
) -> AdaptiveStartupInfo:
    existing = _list_processes_by_name(process_name)
    info = AdaptiveStartupInfo(
        strategy="isolated_cli_launch",
        process_group=process_group,
        existing_process_count=len(existing),
    )

    if clean_existing and existing:
        _terminate_processes([process["pid"] for process in existing])
        info.cleaned_existing_count = len(existing)
        info.diagnostics.append("Cleaned existing processes before isolated CLI launch.")
        time.sleep(1)

    user_data_dir = output_dir / "user-data"
    _reset_dir(user_data_dir)
    command = command_builder(user_data_dir)
    subprocess.run(command, check=False, capture_output=True, text=False)
    time.sleep(wait_seconds)

    processes = _list_processes_by_name(process_name)
    info.user_data_dir = str(user_data_dir)
    info.launched_process_ids = [process["pid"] for process in processes]
    windows = _list_windows_by_process_ids(info.launched_process_ids)
    info.window_count = len(windows)
    info.window_titles = [window["name"] for window in windows if window.get("name")]
    return info


def cleanup_process_group(process_name: str) -> None:
    processes = _list_processes_by_name(process_name)
    if processes:
        _terminate_processes([process["pid"] for process in processes])


def _list_processes_by_name(process_name: str) -> list[dict[str, Any]]:
    exe_name = f"{process_name}.exe"
    script = (
        "$items = Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.Name -eq '{exe_name}' }} | "
        "Select-Object @{n='pid';e={$_.ProcessId}}, "
        "@{n='name';e={$_.Name}}, "
        "@{n='command_line';e={$_.CommandLine}}, "
        "@{n='path';e={$_.ExecutablePath}}; "
        "if ($items) { $items | ConvertTo-Json -Depth 4 -Compress }"
    )
    return _powershell_json(script)


def _list_windows_by_process_ids(process_ids: list[int]) -> list[dict[str, Any]]:
    if not process_ids:
        return []
    joined = ",".join(str(pid) for pid in process_ids)
    script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$ids = @({joined})
$root=[System.Windows.Automation.AutomationElement]::RootElement
$wins=$root.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
$out=@()
for($i=0;$i -lt $wins.Count;$i++){{
  $w=$wins.Item($i)
  if($ids -contains $w.Current.ProcessId){{
    $out += [ordered]@{{
      name=$w.Current.Name
      class=$w.Current.ClassName
      pid=$w.Current.ProcessId
      hwnd=$w.Current.NativeWindowHandle
    }}
  }}
}}
if($out){{ $out | ConvertTo-Json -Depth 4 -Compress }}
"""
    return _powershell_json(script)


def _terminate_processes(process_ids: list[int]) -> None:
    for pid in process_ids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, check=False)


def _powershell_json(script: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = result.stdout.strip()
    if not stdout:
        return []
    data = json.loads(stdout)
    if isinstance(data, list):
        return data
    return [data]


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def _wait_for_cdp(port: int, timeout: float = 30.0) -> None:
    import urllib.request

    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as error:
            last_error = error
            time.sleep(0.25)
    raise RuntimeError(f"Chrome CDP endpoint did not become ready: {last_error}")


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])
