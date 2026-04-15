# Coding Conventions

**Analysis Date:** 2026-04-15

## Naming Patterns

**Files:**
- Use `snake_case.py` for Python modules under `omnicontrol/` and `tests/`, such as `omnicontrol/runtime/live_smoke.py`, `omnicontrol/detector/capability_detector.py`, and `tests/test_live_smoke_helpers.py`.
- Reserve `__init__.py` for package markers and short package docstrings, as in `omnicontrol/__init__.py`, `omnicontrol/runtime/__init__.py`, and `omnicontrol/verifier/__init__.py`.
- Place JavaScript helper scripts in `omnicontrol/runtime/scripts/` with `snake_case.js` names, such as `omnicontrol/runtime/scripts/cdp_target_helpers.js`.

**Functions:**
- Use `snake_case` for public and private functions, including helper-prefixed names like `_print_result` in `omnicontrol/cli.py`, `_materialization_reason` in `omnicontrol/runtime/invocation.py`, and `_evaluate_group` in `omnicontrol/runtime/strategy.py`.
- Use verb-led names that describe outcomes, such as `run_smoke`, `build_manifest`, `plan_remediation_actions`, `ensure_ascii_staging`, and `derive_preferred_order`.
- Test names follow `test_<behavior>` with explicit outcome wording, for example `test_blocked_when_required_preflight_fails` in `tests/test_orchestrator.py` and `test_build_software_native_plan_filters_web_substitute_variants` in `tests/test_transports.py`.

**Variables:**
- Use `snake_case` for locals, parameters, and module constants.
- Use uppercase snake case for module-level constants and lookup tables, such as `DOCUMENT_EXTENSIONS`, `KNOWN_HINTS`, `BLOCKER_PATTERNS`, and `DEFAULT_ACTIONS_BY_BLOCKER` in `omnicontrol/detector/capability_detector.py`, `omnicontrol/runtime/strategy.py`, and `omnicontrol/runtime/remediation.py`.
- Use explicit descriptive names for intermediate payloads, for example `resolved_platform`, `normalized_needs`, `capability_reasons`, `required_failures`, and `output_dir`.

**Types:**
- Use `PascalCase` for dataclasses and type aliases, such as `DetectionResult` in `omnicontrol/models.py`, `AttemptSpec` in `omnicontrol/runtime/orchestrator.py`, `SmokeContract` in `omnicontrol/runtime/strategy.py`, and `ScriptArgStyle` in `omnicontrol/runtime/invocation.py`.
- Prefer `Literal[...]` for constrained string enums, for example `SmokeStatus` in `omnicontrol/runtime/strategy.py` and `ScriptArgStyle` in `omnicontrol/runtime/invocation.py`.

## Code Style

**Formatting:**
- No formatter configuration file is detected in `/Users/daizhaorong/OmniControl`; `.prettierrc*`, `prettier.config.*`, `biome.json`, and Python formatter configs are not present.
- Follow the style already present in `omnicontrol/`:
  - `from __future__ import annotations` at the top of nearly every Python file, including `omnicontrol/cli.py`, `omnicontrol/models.py`, and every `tests/test_*.py`.
  - Standard library imports grouped together, then first-party imports separated by a blank line.
  - Type annotations on public functions and most private helpers.
  - Short line wrapping with hanging indents for long calls, as in `omnicontrol/cli.py` and `omnicontrol/runtime/live_smoke.py`.
- Dataclasses consistently use `@dataclass(slots=True)` in runtime and model files such as `omnicontrol/models.py`, `omnicontrol/runtime/orchestrator.py`, and `omnicontrol/runtime/transports.py`. This means the codebase assumes Python 3.10+ even though no formatter enforces that style.

**Linting:**
- No lint configuration is detected in `/Users/daizhaorong/OmniControl`; `eslint`, `biome`, `ruff`, `flake8`, `mypy`, and `pylint` config files are not present.
- In the absence of a linter, preserve the existing typed, low-magic style:
  - Annotate function signatures.
  - Keep imports explicit.
  - Prefer small pure helpers over inline logic when a rule has a name, such as `_safe_stem` in `omnicontrol/runtime/invocation.py` and `classify_blocker` in `omnicontrol/runtime/strategy.py`.

## Import Organization

**Order:**
1. `from __future__ import annotations`
2. Standard library imports, often with `from ... import ...` before plain `import ...` when both are used, as in `omnicontrol/models.py` and `omnicontrol/runtime/live_smoke.py`
3. First-party `omnicontrol.*` imports

**Path Aliases:**
- No path alias system is used. Import project code through absolute package imports such as `from omnicontrol.runtime.orchestrator import AttemptSpec` in `tests/test_orchestrator.py`.

**Observed Pattern:**
```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import copy
from typing import Any, Callable

from omnicontrol.runtime.kb import PROFILE_METADATA, find_matches
from omnicontrol.runtime.orchestrator import AttemptSpec
```
- Reuse this structure for new modules under `omnicontrol/` and `tests/`.

## Error Handling

**Patterns:**
- Raise concrete built-in exceptions for invalid inputs and missing resources:
  - `ValueError` for unsupported options in `omnicontrol/runtime/invocation.py` and `omnicontrol/runtime/live_smoke.py`
  - `FileNotFoundError` for absent executables or source files in `omnicontrol/runtime/live_smoke.py`
  - `RuntimeError` for orchestration or runtime failures in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/adaptive_startup.py`
- Convert internal exceptions into structured payloads when the runtime is orchestrating retries, instead of letting them abort the full flow. `run_orchestrator` in `omnicontrol/runtime/orchestrator.py` catches `Exception`, stores the message in `detail` and `blocker`, and returns a dict payload with `"status": "blocked"` or `"status": "error"`.
- Encode failure state as data. Many runtime paths return dictionaries with keys such as `status`, `error`, `blockers`, `orchestration`, and `strategy`; see `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/strategy.py`, and `omnicontrol/runtime/live_smoke.py`.

**Use This Pattern For New Code:**
```python
try:
    payload = attempt.run()
    status = str(payload.get("status", "error"))
except Exception as error:
    payload = {"status": "error", "error": str(error)}
    status = "error"
```
- This pattern from `omnicontrol/runtime/orchestrator.py` is the repo’s preferred boundary between imperative work and structured result reporting.

## Logging

**Framework:** `print` in the CLI only; no `logging` module usage detected in `omnicontrol/`.

**Patterns:**
- User-facing output is centralized in `omnicontrol/cli.py::_print_result`.
- Internal runtime modules do not emit logs directly. They return structured dict payloads that the CLI formats later.
- Preserve this separation: new library/runtime code should return data; new terminal output should be added in `omnicontrol/cli.py` unless the feature is explicitly interactive.

## Comments

**When to Comment:**
- Comments are sparse. Prefer self-explanatory names and extracted helper functions over inline narration.
- Add a docstring when a module or helper represents a reusable rule rather than a one-off branch. Examples:
  - `omnicontrol/detector/capability_detector.py`: `"""Infer plausible control surfaces from lightweight target signals."""`
  - `omnicontrol/planner/language_selector.py`: `"""Choose a scripting language based on platform, adapter and workload."""`
  - `omnicontrol/runtime/invocation.py`: `"""Return true when a script body is too fragile to pass inline as argv text."""`

**JSDoc/TSDoc:**
- Not applicable. The JS files under `omnicontrol/runtime/scripts/` are helper scripts packaged as assets and do not use JSDoc.

## Function Design

**Size:** 
- Most modules prefer small-to-medium helpers with one focused job, as in `omnicontrol/runtime/invocation.py`, `omnicontrol/runtime/remediation.py`, and `omnicontrol/runtime/strategy.py`.
- `omnicontrol/runtime/live_smoke.py` is the major exception: it is a large dispatcher plus implementation hub. New runtime helpers should be extracted rather than expanding unrelated branches inside that file when possible.

**Parameters:**
- Prefer keyword-only options after a required positional core, using `*` for clarity, as seen in:
  - `CapabilityDetector.detect` in `omnicontrol/detector/capability_detector.py`
  - `run_smoke` in `omnicontrol/runtime/live_smoke.py`
  - `prepare_script_payload` in `omnicontrol/runtime/invocation.py`
- Use `Path | None`, `str | None`, and typed iterables instead of untyped `*args` or `**kwargs`, except where dynamic payload dictionaries are the API by design.

**Return Values:**
- Return dataclasses for internal domain models and typed runtime specs:
  - `Capability`, `DetectionResult`, `AdapterPlan`, and `HarnessManifest` in `omnicontrol/models.py`
  - `PreflightResult` and `AttemptResult` in `omnicontrol/runtime/orchestrator.py`
- Return plain `dict[str, Any]` for runtime execution payloads that cross process or CLI boundaries, as in `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/orchestrator.py`, and `omnicontrol/benchmark.py`.
- Provide `to_dict()` or `to_jsonable()` adapters when dataclasses need serialization, as in `omnicontrol/models.py`, `omnicontrol/runtime/orchestrator.py`, and `omnicontrol/runtime/strategy.py`.

## Module Design

**Exports:**
- Modules usually expose symbols directly and are imported by file path; there is little indirection.
- Package `__init__.py` files are minimal and mostly descriptive. `omnicontrol/__init__.py` defines `__all__ = ["__version__"]`; subpackages such as `omnicontrol/runtime/__init__.py` and `omnicontrol/verifier/__init__.py` only carry docstrings.

**Barrel Files:**
- Barrel exports are not used. Import from the defining module, for example `from omnicontrol.runtime.transports import run_ordered_transport_attempts` in `tests/test_transports.py`.

## Prescriptive Guidance

- Add new runtime logic under the closest focused module in `omnicontrol/runtime/` if it matches an existing concern such as invocation, staging, pivots, remediation, strategy, or transports.
- Match the existing absolute import style from the `omnicontrol` package root.
- Keep CLI printing in `omnicontrol/cli.py`; do not introduce ad hoc prints in helper modules.
- Prefer structured results with `status`, `error`, `blockers`, and evidence fields over opaque exceptions once work enters orchestration code.
- Continue using `dataclass(slots=True)` and explicit type hints for new models and runtime specs.

---

*Convention analysis: 2026-04-15*
