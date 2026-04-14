from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


TransportPredicate = Callable[[dict[str, Any]], bool]
TransportRunner = Callable[[], dict[str, Any]]


@dataclass(slots=True)
class TransportDescriptor:
    name: str
    control_plane: str
    software_native: bool = True
    background_safe: bool = True
    requires_focus: bool = False
    startup_cost: int = 0
    probe_cost: int = 0
    determinism: int = 5
    observability: int = 5
    side_effect_risk: int = 0


@dataclass(slots=True)
class TransportAttemptSpec:
    name: str
    run: TransportRunner
    is_success: TransportPredicate | None = None


def run_ordered_transport_attempts(
    attempts: list[TransportAttemptSpec],
    *,
    learned_order: Iterable[str] = (),
    probe: TransportRunner | None = None,
    success_key: str = "command_ok",
) -> dict[str, Any]:
    learned = [str(name) for name in learned_order if str(name)]
    ordered_specs = _ordered_specs(attempts, learned)
    probe_payload = probe() if probe is not None else {}

    attempt_payloads: list[dict[str, Any]] = []
    for spec in ordered_specs:
        payload = dict(spec.run())
        payload.setdefault("method", spec.name)
        attempt_payloads.append(payload)
        predicate = spec.is_success or (lambda item: bool(item.get(success_key)))
        if predicate(payload):
            return {
                **payload,
                "attempts": attempt_payloads,
                "probe": probe_payload,
                "learned_order": learned,
                "ordered_methods": [item.name for item in ordered_specs],
            }

    fallback = attempt_payloads[0] if attempt_payloads else {
        "method": "",
        "returncode": 1,
        "stdout": "",
        "stderr": "No transport attempts were executed",
    }
    return {
        **fallback,
        "attempts": attempt_payloads,
        "probe": probe_payload,
        "learned_order": learned,
        "ordered_methods": [item.name for item in ordered_specs],
    }


def derive_preferred_order(
    attempts: Iterable[dict[str, Any]],
    *,
    success_key: str = "command_ok",
    name_keys: tuple[str, ...] = ("method", "name", "transport_variant"),
) -> list[str]:
    successful: list[str] = []
    observed: list[str] = []
    for attempt in attempts:
        name = next((str(attempt.get(key)) for key in name_keys if attempt.get(key)), "")
        if not name:
            continue
        if name not in observed:
            observed.append(name)
        if attempt.get(success_key) and name not in successful:
            successful.append(name)
    ordered: list[str] = []
    for name in [*successful, *observed]:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def rank_transport_descriptors(
    descriptors: Iterable[TransportDescriptor],
    *,
    preferred_order: Iterable[str] | None = None,
) -> list[TransportDescriptor]:
    preferred = [str(name) for name in (preferred_order or []) if str(name)]
    descriptor_list = list(descriptors)
    by_name = {descriptor.name: descriptor for descriptor in descriptor_list}
    ranked: list[TransportDescriptor] = []

    for name in preferred:
        descriptor = by_name.get(name)
        if descriptor is not None and all(item.name != descriptor.name for item in ranked):
            ranked.append(descriptor)

    remainder = [descriptor for descriptor in descriptor_list if all(item.name != descriptor.name for item in ranked)]
    remainder.sort(
        key=lambda descriptor: (
            int(not descriptor.software_native),
            int(descriptor.requires_focus),
            int(not descriptor.background_safe),
            descriptor.side_effect_risk,
            descriptor.startup_cost,
            descriptor.probe_cost,
            -descriptor.determinism,
            -descriptor.observability,
            descriptor.name,
        )
    )
    ranked.extend(remainder)
    return ranked


def build_background_first_plan(
    descriptors: Iterable[TransportDescriptor],
    *,
    preferred_order: Iterable[str] | None = None,
) -> list[str]:
    return [descriptor.name for descriptor in rank_transport_descriptors(descriptors, preferred_order=preferred_order)]


def build_software_native_plan(
    descriptors: Iterable[TransportDescriptor],
    *,
    preferred_order: Iterable[str] | None = None,
) -> list[str]:
    ranked = rank_transport_descriptors(descriptors, preferred_order=preferred_order)
    return [descriptor.name for descriptor in ranked if descriptor.software_native]


def _ordered_specs(
    attempts: list[TransportAttemptSpec],
    learned_order: list[str],
) -> list[TransportAttemptSpec]:
    attempt_map = {attempt.name: attempt for attempt in attempts}
    ordered: list[TransportAttemptSpec] = []
    for name in learned_order:
        if name in attempt_map and all(item.name != name for item in ordered):
            ordered.append(attempt_map[name])
    for attempt in attempts:
        if all(item.name != attempt.name for item in ordered):
            ordered.append(attempt)
    return ordered


OrderedAttemptSpec = TransportAttemptSpec


def prioritize_attempts(
    specs: Iterable[TransportAttemptSpec],
    *,
    preferred_order: Iterable[str] | None = None,
) -> list[TransportAttemptSpec]:
    return _ordered_specs(list(specs), [str(item) for item in (preferred_order or []) if str(item)])


def run_ordered_attempts(
    specs: Iterable[TransportAttemptSpec],
    *,
    preferred_order: Iterable[str] | None = None,
    probe: TransportRunner | None = None,
    success_key: str = "command_ok",
) -> dict[str, Any]:
    return run_ordered_transport_attempts(
        list(specs),
        learned_order=tuple(preferred_order or ()),
        probe=probe,
        success_key=success_key,
    )
