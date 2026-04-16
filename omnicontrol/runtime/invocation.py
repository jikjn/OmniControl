from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Iterable, Literal


ScriptArgStyle = Literal["prefixed", "separate", "stdin"]

_UNSAFE_INLINE_CHARS = frozenset(" \t\r\n;\"'`(){}[]|&<>")
_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(slots=True)
class ScriptPayload:
    mode: Literal["inline", "file"]
    value: str
    path: str | None
    reason: str | None
    length: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ResponseFile:
    path: str
    argv: list[str]
    argument: str

    def to_dict(self) -> dict:
        return asdict(self)


def should_materialize_script(payload: str, *, max_inline_chars: int = 120) -> bool:
    """Return true when a script body is too fragile to pass inline as argv text."""
    if len(payload) > max_inline_chars:
        return True
    if any(ord(char) > 127 for char in payload):
        return True
    return any(char in _UNSAFE_INLINE_CHARS for char in payload)


def prepare_script_payload(
    payload: str,
    output_dir: Path,
    *,
    stem: str = "payload",
    suffix: str = ".txt",
    prefer_file: bool = False,
    max_inline_chars: int = 120,
    encoding: str = "utf-8",
) -> ScriptPayload:
    reason = _materialization_reason(payload, max_inline_chars=max_inline_chars)
    if prefer_file or reason is not None:
        if prefer_file and reason is None:
            reason = "file_transport_preferred"
        return materialize_script_payload(
            payload,
            output_dir,
            stem=stem,
            suffix=suffix,
            reason=reason or "file_transport_preferred",
            encoding=encoding,
        )
    return ScriptPayload(
        mode="inline",
        value=payload,
        path=None,
        reason=None,
        length=len(payload),
    )


def materialize_script_payload(
    payload: str,
    output_dir: Path,
    *,
    stem: str = "payload",
    suffix: str = ".txt",
    reason: str | None = None,
    encoding: str = "utf-8",
) -> ScriptPayload:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = _safe_stem(stem)
    safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    script_path = output_dir / f"{safe_stem}{safe_suffix}"
    script_path.write_text(payload, encoding=encoding)
    return ScriptPayload(
        mode="file",
        value=str(script_path),
        path=str(script_path),
        reason=reason or _materialization_reason(payload) or "file_transport_preferred",
        length=len(payload),
    )


def build_script_file_argument(
    script_path: str | Path,
    *,
    flag: str = "-script",
    style: ScriptArgStyle = "prefixed",
) -> list[str]:
    script_value = str(script_path)
    if style == "prefixed":
        separator = "" if flag.endswith("=") else "="
        return [f"{flag}{separator}{script_value}"]
    if style == "separate":
        return [flag, script_value]
    if style == "stdin":
        return []
    raise ValueError(f"Unsupported script argument style: {style}")


def build_external_command(executable: str | Path, args: Iterable[str | Path]) -> list[str]:
    return [str(executable), *[str(arg) for arg in args]]


def materialize_response_file(
    argv: Iterable[str | Path],
    output_dir: Path,
    *,
    stem: str = "args",
    suffix: str = ".rsp",
    encoding: str = "utf-8",
) -> ResponseFile:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{_safe_stem(stem)}{suffix if suffix.startswith('.') else f'.{suffix}'}"
    argv_list = [str(arg) for arg in argv]
    path.write_text("\n".join(_quote_response_arg(arg) for arg in argv_list), encoding=encoding)
    return ResponseFile(path=str(path), argv=argv_list, argument=f"@{path}")


def _materialization_reason(payload: str, *, max_inline_chars: int = 120) -> str | None:
    if len(payload) > max_inline_chars:
        return "length"
    if any(ord(char) > 127 for char in payload):
        return "non_ascii"
    if any(char in _UNSAFE_INLINE_CHARS for char in payload):
        return "metacharacter"
    return None


def _safe_stem(stem: str) -> str:
    safe = _SAFE_STEM_RE.sub("_", stem).strip("._")
    return safe or "payload"


def _quote_response_arg(arg: str) -> str:
    if arg and not any(char.isspace() or char == '"' for char in arg):
        return arg
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'
