<!-- GSD:project-start source:PROJECT.md -->
## Project

**OmniControl**

OmniControl is a capability-first local software automation framework for AI agent developers and advanced operators. It detects control planes, plans adapters, scaffolds automation harnesses, and runs real smoke and workflow verification against installed applications. The current focus is turning the existing prototype into a practically usable macOS automation framework with representative real-world application coverage.

**Core Value:** Real local macOS applications can be automated and verified through a consistent capability-first framework, with evidence-rich results that agent developers can trust.

### Constraints

- **Existing Architecture**: Build on the current capability-first detector/planner/runtime design — preserve the framework identity instead of replacing it with app-specific one-offs
- **Platform Focus**: macOS is the current priority — first-phase work should increase practical macOS usability before pursuing additional broad platform ambitions
- **Verification Standard**: v1 uses layered acceptance — core macOS apps should be few-but-hard, while extension apps may ship with `partial` outcomes if evidence and limitations are explicit
- **Target User**: Design decisions should favor AI agent developers and advanced operators — clarity of runtime evidence and debuggability matter more than consumer-facing polish
- **Execution Environment**: Real macOS automation depends on a live graphical session, app launchability, and OS automation permissions — plans must account for these as first-class runtime constraints
- **Coverage Scope**: The first macOS batch should be balanced across application domains and workflow types — avoid overfitting to a single app family or a single transport
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.10+ - Core CLI, detector, planner, runtime, benchmark runner, and scaffold generator in `pyproject.toml`, `omnicontrol/cli.py`, `omnicontrol/detector/capability_detector.py`, `omnicontrol/planner/adapter_selector.py`, `omnicontrol/runtime/live_smoke.py`, and `omnicontrol/benchmark.py`
- PowerShell - Windows automation payloads and smoke scripts in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/scripts/*.ps1`
- JavaScript - CDP probes and Node-driven smoke helpers in `omnicontrol/runtime/scripts/*.js`
- AppleScript - macOS Finder and Safari smoke scripts in `omnicontrol/runtime/scripts/*.applescript`
- JSON - Benchmark fixtures and persistent runtime knowledge in `benchmarks/local_closed_source_windows.json`, `benchmarks/local_closed_source_macos.json`, and `knowledge/kb.json`
- Markdown - Product and strategy docs in `README.md` and `docs/*.md`
## Runtime
- CPython 3.10 or newer required by `pyproject.toml`
- The installed CLI entry point is `omnicontrol = "omnicontrol.cli:main"` in `pyproject.toml`
- Runtime subprocess integration expects host tools such as `powershell`, `node`, and `osascript` as invoked from `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/adaptive_startup.py`
- `pip`/PEP 517 build flow via `setuptools.build_meta` in `pyproject.toml`
- Lockfile: missing; no `requirements.txt`, `poetry.lock`, or `uv.lock` detected at `/Users/daizhaorong/OmniControl`
## Frameworks
- Python standard library - Main application framework; `argparse`, `json`, `pathlib`, `subprocess`, `socket`, `urllib`, `ctypes`, and `xml.etree.ElementTree` drive nearly all functionality in `omnicontrol/cli.py`, `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/adaptive_startup.py`, and `omnicontrol/runtime/windows_ipc.py`
- `setuptools>=68` - Packaging and distribution backend in `pyproject.toml`
- `unittest` - Active test runner and suite style in `tests/test_*.py` and `tests/TEST.md`
- `pytest>=8` - Optional dev dependency only, declared in `[project.optional-dependencies].dev` in `pyproject.toml`
- `setuptools` package discovery - Package inclusion and runtime script assets configured in `pyproject.toml`
- No linter, formatter, type-checker, or task runner config detected; no `ruff`, `black`, `mypy`, `tox`, `nox`, or CI config files were found under `/Users/daizhaorong/OmniControl`
## Key Dependencies
- Python stdlib subprocess/process APIs - External tool orchestration and smoke execution in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/adaptive_startup.py`
- Python stdlib networking APIs - HTTP/CDP probing and QQ Music requests through `urllib.request` in `omnicontrol/runtime/live_smoke.py`
- Python stdlib `ctypes` and Win32 bindings - Windows window messaging and process inspection in `omnicontrol/runtime/windows_ipc.py`
- Node.js runtime - Required by CDP helper scripts such as `omnicontrol/runtime/scripts/chrome_cdp_smoke.js`, `omnicontrol/runtime/scripts/chrome_form_write_smoke.js`, `omnicontrol/runtime/scripts/desktop_cdp_observe.js`, and `omnicontrol/runtime/scripts/target_cdp_probe.js`
- Windows PowerShell - Required by Windows smoke profiles and process/window inspection in `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/adaptive_startup.py`, and `omnicontrol/runtime/scripts/*.ps1`
- `osascript` - Required by macOS smoke profiles executed from `omnicontrol/runtime/live_smoke.py` against `omnicontrol/runtime/scripts/finder_open_smoke.applescript`, `safari_open_smoke.applescript`, and `safari_dom_write_smoke.applescript`
## Configuration
- No environment-variable configuration contract is implemented in source; searches across `omnicontrol/`, `tests/`, `docs/`, `README.md`, and `pyproject.toml` did not detect `os.environ`, `getenv`, or named secret variables
- `.env` files: not detected in `/Users/daizhaorong/OmniControl`
- Runtime behavior is configured primarily by CLI flags in `omnicontrol/cli.py`, benchmark JSON files in `benchmarks/*.json`, profile metadata in `omnicontrol/runtime/kb.py`, and persisted learning data in `knowledge/kb.json`
- Build metadata and packaging live in `pyproject.toml`
- Generated artifacts default to local workspace directories from `omnicontrol/cli.py`:
## Platform Requirements
- Python 3.10+ and `setuptools` are required by `pyproject.toml`
- Node.js is required for CDP helper execution referenced by `omnicontrol/runtime/live_smoke.py` and `tests/test_cdp_target_helpers.py`
- Windows development is required to exercise most real smoke profiles, PowerShell automation, COM/UIA flows, and Win32 IPC in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/windows_ipc.py`
- macOS development is required for Finder/Safari AppleScript smoke coverage in `omnicontrol/runtime/live_smoke.py`
- Not a deployed web service; the project runs as a local operator CLI and scaffold generator from `omnicontrol/cli.py`
- Effective execution target is an operator workstation with installed vendor applications and local automation surfaces, as reflected in `README.md`, `benchmarks/local_closed_source_windows.json`, and `benchmarks/local_closed_source_macos.json`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Use `snake_case.py` for Python modules under `omnicontrol/` and `tests/`, such as `omnicontrol/runtime/live_smoke.py`, `omnicontrol/detector/capability_detector.py`, and `tests/test_live_smoke_helpers.py`.
- Reserve `__init__.py` for package markers and short package docstrings, as in `omnicontrol/__init__.py`, `omnicontrol/runtime/__init__.py`, and `omnicontrol/verifier/__init__.py`.
- Place JavaScript helper scripts in `omnicontrol/runtime/scripts/` with `snake_case.js` names, such as `omnicontrol/runtime/scripts/cdp_target_helpers.js`.
- Use `snake_case` for public and private functions, including helper-prefixed names like `_print_result` in `omnicontrol/cli.py`, `_materialization_reason` in `omnicontrol/runtime/invocation.py`, and `_evaluate_group` in `omnicontrol/runtime/strategy.py`.
- Use verb-led names that describe outcomes, such as `run_smoke`, `build_manifest`, `plan_remediation_actions`, `ensure_ascii_staging`, and `derive_preferred_order`.
- Test names follow `test_<behavior>` with explicit outcome wording, for example `test_blocked_when_required_preflight_fails` in `tests/test_orchestrator.py` and `test_build_software_native_plan_filters_web_substitute_variants` in `tests/test_transports.py`.
- Use `snake_case` for locals, parameters, and module constants.
- Use uppercase snake case for module-level constants and lookup tables, such as `DOCUMENT_EXTENSIONS`, `KNOWN_HINTS`, `BLOCKER_PATTERNS`, and `DEFAULT_ACTIONS_BY_BLOCKER` in `omnicontrol/detector/capability_detector.py`, `omnicontrol/runtime/strategy.py`, and `omnicontrol/runtime/remediation.py`.
- Use explicit descriptive names for intermediate payloads, for example `resolved_platform`, `normalized_needs`, `capability_reasons`, `required_failures`, and `output_dir`.
- Use `PascalCase` for dataclasses and type aliases, such as `DetectionResult` in `omnicontrol/models.py`, `AttemptSpec` in `omnicontrol/runtime/orchestrator.py`, `SmokeContract` in `omnicontrol/runtime/strategy.py`, and `ScriptArgStyle` in `omnicontrol/runtime/invocation.py`.
- Prefer `Literal[...]` for constrained string enums, for example `SmokeStatus` in `omnicontrol/runtime/strategy.py` and `ScriptArgStyle` in `omnicontrol/runtime/invocation.py`.
## Code Style
- No formatter configuration file is detected in `/Users/daizhaorong/OmniControl`; `.prettierrc*`, `prettier.config.*`, `biome.json`, and Python formatter configs are not present.
- Follow the style already present in `omnicontrol/`:
- Dataclasses consistently use `@dataclass(slots=True)` in runtime and model files such as `omnicontrol/models.py`, `omnicontrol/runtime/orchestrator.py`, and `omnicontrol/runtime/transports.py`. This means the codebase assumes Python 3.10+ even though no formatter enforces that style.
- No lint configuration is detected in `/Users/daizhaorong/OmniControl`; `eslint`, `biome`, `ruff`, `flake8`, `mypy`, and `pylint` config files are not present.
- In the absence of a linter, preserve the existing typed, low-magic style:
## Import Organization
- No path alias system is used. Import project code through absolute package imports such as `from omnicontrol.runtime.orchestrator import AttemptSpec` in `tests/test_orchestrator.py`.
- Reuse this structure for new modules under `omnicontrol/` and `tests/`.
## Error Handling
- Raise concrete built-in exceptions for invalid inputs and missing resources:
- Convert internal exceptions into structured payloads when the runtime is orchestrating retries, instead of letting them abort the full flow. `run_orchestrator` in `omnicontrol/runtime/orchestrator.py` catches `Exception`, stores the message in `detail` and `blocker`, and returns a dict payload with `"status": "blocked"` or `"status": "error"`.
- Encode failure state as data. Many runtime paths return dictionaries with keys such as `status`, `error`, `blockers`, `orchestration`, and `strategy`; see `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/strategy.py`, and `omnicontrol/runtime/live_smoke.py`.
- This pattern from `omnicontrol/runtime/orchestrator.py` is the repo’s preferred boundary between imperative work and structured result reporting.
## Logging
- User-facing output is centralized in `omnicontrol/cli.py::_print_result`.
- Internal runtime modules do not emit logs directly. They return structured dict payloads that the CLI formats later.
- Preserve this separation: new library/runtime code should return data; new terminal output should be added in `omnicontrol/cli.py` unless the feature is explicitly interactive.
## Comments
- Comments are sparse. Prefer self-explanatory names and extracted helper functions over inline narration.
- Add a docstring when a module or helper represents a reusable rule rather than a one-off branch. Examples:
- Not applicable. The JS files under `omnicontrol/runtime/scripts/` are helper scripts packaged as assets and do not use JSDoc.
## Function Design
- Most modules prefer small-to-medium helpers with one focused job, as in `omnicontrol/runtime/invocation.py`, `omnicontrol/runtime/remediation.py`, and `omnicontrol/runtime/strategy.py`.
- `omnicontrol/runtime/live_smoke.py` is the major exception: it is a large dispatcher plus implementation hub. New runtime helpers should be extracted rather than expanding unrelated branches inside that file when possible.
- Prefer keyword-only options after a required positional core, using `*` for clarity, as seen in:
- Use `Path | None`, `str | None`, and typed iterables instead of untyped `*args` or `**kwargs`, except where dynamic payload dictionaries are the API by design.
- Return dataclasses for internal domain models and typed runtime specs:
- Return plain `dict[str, Any]` for runtime execution payloads that cross process or CLI boundaries, as in `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/orchestrator.py`, and `omnicontrol/benchmark.py`.
- Provide `to_dict()` or `to_jsonable()` adapters when dataclasses need serialization, as in `omnicontrol/models.py`, `omnicontrol/runtime/orchestrator.py`, and `omnicontrol/runtime/strategy.py`.
## Module Design
- Modules usually expose symbols directly and are imported by file path; there is little indirection.
- Package `__init__.py` files are minimal and mostly descriptive. `omnicontrol/__init__.py` defines `__all__ = ["__version__"]`; subpackages such as `omnicontrol/runtime/__init__.py` and `omnicontrol/verifier/__init__.py` only carry docstrings.
- Barrel exports are not used. Import from the defining module, for example `from omnicontrol.runtime.transports import run_ordered_transport_attempts` in `tests/test_transports.py`.
## Prescriptive Guidance
- Add new runtime logic under the closest focused module in `omnicontrol/runtime/` if it matches an existing concern such as invocation, staging, pivots, remediation, strategy, or transports.
- Match the existing absolute import style from the `omnicontrol` package root.
- Keep CLI printing in `omnicontrol/cli.py`; do not introduce ad hoc prints in helper modules.
- Prefer structured results with `status`, `error`, `blockers`, and evidence fields over opaque exceptions once work enters orchestration code.
- Continue using `dataclass(slots=True)` and explicit type hints for new models and runtime specs.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- `omnicontrol/cli.py` keeps the public entrypoints thin and delegates domain work into detector, planner, emitter, benchmark, and runtime modules.
- `omnicontrol/models.py` provides the shared dataclasses passed across detection, planning, manifest building, scaffolding, and smoke execution.
- `omnicontrol/runtime/` acts as a second architecture inside the package: contracts, orchestration, adaptive startup, transport ordering, pivots, remediation, knowledge reuse, and OS-specific IPC are split into focused helpers under one large profile dispatcher in `omnicontrol/runtime/live_smoke.py`.
## Layers
- Purpose: Parse command-line arguments and route each subcommand into the correct workflow.
- Location: `omnicontrol/__main__.py`, `omnicontrol/cli.py`
- Contains: `argparse` definitions, subcommand dispatch, output formatting, and JSON/plain-text presentation.
- Depends on: `omnicontrol/benchmark.py`, `omnicontrol/detector/capability_detector.py`, `omnicontrol/planner/adapter_selector.py`, `omnicontrol/ir/manifest.py`, `omnicontrol/emitters/scaffold.py`, `omnicontrol/runtime/live_smoke.py`
- Used by: `python -m omnicontrol`, the `omnicontrol` console script from `pyproject.toml`, and CLI-oriented tests such as `tests/test_full_e2e.py`.
- Purpose: Define the normalized data exchanged between layers.
- Location: `omnicontrol/models.py`
- Contains: `Capability`, `DetectionResult`, `LanguageOption`, `LanguageDecision`, `AdapterPlan`, `HarnessManifest`, plus helpers such as `slugify`, `normalize_platform`, and `to_jsonable`.
- Depends on: Python stdlib only.
- Used by: Nearly every package layer, including `omnicontrol/detector/capability_detector.py`, `omnicontrol/planner/adapter_selector.py`, `omnicontrol/ir/manifest.py`, `omnicontrol/emitters/scaffold.py`, and `omnicontrol/verifier/contracts.py`.
- Purpose: Infer likely control surfaces from lightweight target signals without executing the target.
- Location: `omnicontrol/detector/capability_detector.py`
- Contains: target type/kind inference, keyword and need heuristics, directory signature scanning, and capability scoring inputs.
- Depends on: `omnicontrol/models.py`
- Used by: `omnicontrol/cli.py`, `omnicontrol/benchmark.py`, and tests such as `tests/test_core.py`.
- Purpose: Convert detected capabilities into a primary adapter choice, fallback chain, verification set, state model, suggested actions, and implementation language.
- Location: `omnicontrol/planner/adapter_selector.py`, `omnicontrol/planner/language_selector.py`, `omnicontrol/adapters/catalog.py`
- Contains: adapter profile catalog, capability-to-plan scoring, language ranking, and action synthesis.
- Depends on: `omnicontrol/models.py`, `omnicontrol/adapters/catalog.py`
- Used by: `omnicontrol/cli.py`, `omnicontrol/benchmark.py`, `omnicontrol/ir/manifest.py`, and scaffold generation tests.
- Purpose: Materialize planning output into a portable manifest and generated starter files.
- Location: `omnicontrol/ir/manifest.py`, `omnicontrol/emitters/scaffold.py`, `omnicontrol/verifier/contracts.py`
- Contains: `HarnessManifest` construction, generated `manifest.json`, `PLAN.md`, `SKILL.md`, runner templates, verifier templates, and verification text rendering.
- Depends on: `omnicontrol/models.py`, `omnicontrol/verifier/contracts.py`
- Used by: `omnicontrol/cli.py`, `omnicontrol/benchmark.py`, and scaffold assertions in `tests/test_core.py`.
- Purpose: Execute real smoke profiles against local software and normalize results into `ok / partial / blocked / error`.
- Location: `omnicontrol/runtime/live_smoke.py`
- Contains: the `run_smoke()` dispatcher, per-profile execution functions, subprocess wrappers, sidecar invocation plumbing, and result persistence.
- Depends on: the rest of `omnicontrol/runtime/`, packaged scripts under `omnicontrol/runtime/scripts/`, and `omnicontrol/models.py`.
- Used by: the `smoke` subcommand in `omnicontrol/cli.py`.
- Purpose: Keep the runtime subsystem modular despite the large profile surface.
- Location: `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/strategy.py`, `omnicontrol/runtime/contracts.py`, `omnicontrol/runtime/pivots.py`, `omnicontrol/runtime/remediation.py`, `omnicontrol/runtime/transports.py`, `omnicontrol/runtime/adaptive_startup.py`, `omnicontrol/runtime/invocation.py`, `omnicontrol/runtime/staging.py`, `omnicontrol/runtime/kb.py`, `omnicontrol/runtime/windows_ipc.py`
- Contains: reusable preflight/attempt orchestration, contract evaluation, blocker classification, pivot planning, KB-backed remediation, transport ranking, Windows process/window helpers, payload materialization, and ASCII-safe staging.
- Depends on: each other in a hub-and-spoke pattern centered around `omnicontrol/runtime/live_smoke.py`.
- Used by: smoke profiles and focused unit tests such as `tests/test_orchestrator.py`, `tests/test_strategy.py`, `tests/test_transports.py`, `tests/test_kb.py`, `tests/test_invocation.py`, and `tests/test_windows_ipc.py`.
## Data Flow
- CLI detection and planning are mostly stateless and derive outputs directly from current inputs.
- Generated scaffold artifacts persist only in the chosen output directory from `omnicontrol/emitters/scaffold.py`.
- Smoke execution persists operational memory in `knowledge/kb.json` through `omnicontrol/runtime/kb.py`.
- Per-run artifacts are written under directories like `smoke-output/...` or explicit output paths handled inside `omnicontrol/runtime/live_smoke.py`.
## Key Abstractions
- Purpose: Represent the pipeline boundaries between detection, planning, and generation.
- Examples: `omnicontrol/models.py`, `omnicontrol/ir/manifest.py`
- Pattern: immutable-style dataclass handoff between layers.
- Purpose: Centralize adapter priorities, default state models, and default verification methods.
- Examples: `omnicontrol/adapters/catalog.py`
- Pattern: static catalog lookup keyed by adapter name.
- Purpose: Turn raw profile outputs into normalized runtime verdicts with required and desired evidence checks.
- Examples: `omnicontrol/runtime/strategy.py`, `omnicontrol/runtime/contracts.py`
- Pattern: declarative contract evaluation rather than ad hoc per-profile status logic.
- Purpose: Standardize multi-attempt execution with preflight gating and attempt selection.
- Examples: `omnicontrol/runtime/orchestrator.py`, usage in `omnicontrol/runtime/live_smoke.py`
- Pattern: mini workflow engine for runtime smoke execution.
- Purpose: Encode how a blocked primary control plane can pivot to sidecars, tooling planes, or alternative entrypoints.
- Examples: `omnicontrol/runtime/pivots.py`, `omnicontrol/runtime/remediation.py`, `omnicontrol/runtime/kb.py`
- Pattern: metadata-driven fallback expansion layered on top of orchestrated attempts.
- Purpose: Rank and execute alternative command/control transports while preserving observed winning order.
- Examples: `omnicontrol/runtime/transports.py`, QQMusic-related code paths in `omnicontrol/runtime/live_smoke.py`
- Pattern: ordered transport selection with learned preferences from the knowledge base.
## Entry Points
- Location: `omnicontrol/__main__.py`
- Triggers: `python -m omnicontrol`
- Responsibilities: Call `omnicontrol.cli.main()` and exit with its return code.
- Location: `pyproject.toml`
- Triggers: `omnicontrol` command after package installation
- Responsibilities: Bind the console script name to `omnicontrol.cli:main`.
- Location: `omnicontrol/cli.py`
- Triggers: Any CLI invocation
- Responsibilities: Build parsers, route subcommands, construct detector/planner/runtime objects, and print final payloads.
- Location: `omnicontrol/benchmark.py`
- Triggers: `omnicontrol benchmark ...`
- Responsibilities: Batch-run detect/plan/scaffold over benchmark fixtures from `benchmarks/*.json`.
- Location: `omnicontrol/runtime/live_smoke.py`
- Triggers: `omnicontrol smoke <profile> ...`
- Responsibilities: Dispatch profile handlers, run orchestration, evaluate contracts, and persist reports plus knowledge.
## Error Handling
- CLI-level validation in `omnicontrol/cli.py` raises `ValueError` or `FileNotFoundError` for missing required arguments or executables before deep execution.
- `omnicontrol/runtime/orchestrator.py` catches exceptions inside preflight and attempt functions and converts them into structured orchestration payloads instead of crashing the whole workflow immediately.
- `omnicontrol/runtime/strategy.py` classifies blockers and synthesizes recovery hints from raw payload text.
- Profile functions in `omnicontrol/runtime/live_smoke.py` often accept `ok`, `partial`, and `blocked` as expected terminal states, but raise `RuntimeError` for unstructured hard failure after writing the result artifact.
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
