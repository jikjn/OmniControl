from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import hashlib
from pathlib import Path
import platform as platform_lib
import re
from typing import Any


def current_platform() -> str:
    system = platform_lib.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def normalize_platform(value: str) -> str:
    if value in {"auto", ""}:
        return current_platform()
    aliases = {
        "win": "windows",
        "windows": "windows",
        "mac": "macos",
        "macos": "macos",
        "osx": "macos",
        "linux": "linux",
    }
    return aliases.get(value.lower(), value.lower())


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    if cleaned:
        return cleaned
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"target-{digest}"


def display_name_from_target(target: str) -> str:
    if not target:
        return "Unnamed Target"
    if "://" in target:
        return target.split("://", maxsplit=1)[-1].strip("/") or target
    path = Path(target)
    if path.name:
        return path.stem or path.name
    return target


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


@dataclass(slots=True)
class Capability:
    name: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    structured: bool = True


@dataclass(slots=True)
class DetectionResult:
    target: str
    display_name: str
    target_type: str
    platform: str
    target_kind: str
    needs: list[str]
    signals: list[str]
    capabilities: list[Capability]


@dataclass(slots=True)
class LanguageOption:
    language: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LanguageDecision:
    primary: str
    alternatives: list[str]
    ranking: list[LanguageOption]
    reasons: list[str]


@dataclass(slots=True)
class AdapterPlan:
    primary_adapter: str
    fallback_adapters: list[str]
    state_model: str
    verification_methods: list[str]
    suggested_actions: list[str]
    language: LanguageDecision
    rationale: list[str]


@dataclass(slots=True)
class HarnessManifest:
    project: str
    display_name: str
    slug: str
    detection: DetectionResult
    plan: AdapterPlan
    output_dir: str | None = None
