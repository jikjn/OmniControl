# Architecture

**Analysis Date:** 2026-04-15

## Pattern Overview

**Overall:** Capability-first pipeline with a layered CLI core and a profile-driven runtime orchestration subsystem.

**Key Characteristics:**
- `omnicontrol/cli.py` keeps the public entrypoints thin and delegates domain work into detector, planner, emitter, benchmark, and runtime modules.
- `omnicontrol/models.py` provides the shared dataclasses passed across detection, planning, manifest building, scaffolding, and smoke execution.
- `omnicontrol/runtime/` acts as a second architecture inside the package: contracts, orchestration, adaptive startup, transport ordering, pivots, remediation, knowledge reuse, and OS-specific IPC are split into focused helpers under one large profile dispatcher in `omnicontrol/runtime/live_smoke.py`.

## Layers

**CLI and Command Dispatch:**
- Purpose: Parse command-line arguments and route each subcommand into the correct workflow.
- Location: `omnicontrol/__main__.py`, `omnicontrol/cli.py`
- Contains: `argparse` definitions, subcommand dispatch, output formatting, and JSON/plain-text presentation.
- Depends on: `omnicontrol/benchmark.py`, `omnicontrol/detector/capability_detector.py`, `omnicontrol/planner/adapter_selector.py`, `omnicontrol/ir/manifest.py`, `omnicontrol/emitters/scaffold.py`, `omnicontrol/runtime/live_smoke.py`
- Used by: `python -m omnicontrol`, the `omnicontrol` console script from `pyproject.toml`, and CLI-oriented tests such as `tests/test_full_e2e.py`.

**Core Domain Model:**
- Purpose: Define the normalized data exchanged between layers.
- Location: `omnicontrol/models.py`
- Contains: `Capability`, `DetectionResult`, `LanguageOption`, `LanguageDecision`, `AdapterPlan`, `HarnessManifest`, plus helpers such as `slugify`, `normalize_platform`, and `to_jsonable`.
- Depends on: Python stdlib only.
- Used by: Nearly every package layer, including `omnicontrol/detector/capability_detector.py`, `omnicontrol/planner/adapter_selector.py`, `omnicontrol/ir/manifest.py`, `omnicontrol/emitters/scaffold.py`, and `omnicontrol/verifier/contracts.py`.

**Detection Layer:**
- Purpose: Infer likely control surfaces from lightweight target signals without executing the target.
- Location: `omnicontrol/detector/capability_detector.py`
- Contains: target type/kind inference, keyword and need heuristics, directory signature scanning, and capability scoring inputs.
- Depends on: `omnicontrol/models.py`
- Used by: `omnicontrol/cli.py`, `omnicontrol/benchmark.py`, and tests such as `tests/test_core.py`.

**Planning Layer:**
- Purpose: Convert detected capabilities into a primary adapter choice, fallback chain, verification set, state model, suggested actions, and implementation language.
- Location: `omnicontrol/planner/adapter_selector.py`, `omnicontrol/planner/language_selector.py`, `omnicontrol/adapters/catalog.py`
- Contains: adapter profile catalog, capability-to-plan scoring, language ranking, and action synthesis.
- Depends on: `omnicontrol/models.py`, `omnicontrol/adapters/catalog.py`
- Used by: `omnicontrol/cli.py`, `omnicontrol/benchmark.py`, `omnicontrol/ir/manifest.py`, and scaffold generation tests.

**Manifest and Scaffold Generation:**
- Purpose: Materialize planning output into a portable manifest and generated starter files.
- Location: `omnicontrol/ir/manifest.py`, `omnicontrol/emitters/scaffold.py`, `omnicontrol/verifier/contracts.py`
- Contains: `HarnessManifest` construction, generated `manifest.json`, `PLAN.md`, `SKILL.md`, runner templates, verifier templates, and verification text rendering.
- Depends on: `omnicontrol/models.py`, `omnicontrol/verifier/contracts.py`
- Used by: `omnicontrol/cli.py`, `omnicontrol/benchmark.py`, and scaffold assertions in `tests/test_core.py`.

**Runtime Orchestration Layer:**
- Purpose: Execute real smoke profiles against local software and normalize results into `ok / partial / blocked / error`.
- Location: `omnicontrol/runtime/live_smoke.py`
- Contains: the `run_smoke()` dispatcher, per-profile execution functions, subprocess wrappers, sidecar invocation plumbing, and result persistence.
- Depends on: the rest of `omnicontrol/runtime/`, packaged scripts under `omnicontrol/runtime/scripts/`, and `omnicontrol/models.py`.
- Used by: the `smoke` subcommand in `omnicontrol/cli.py`.

**Runtime Support Modules:**
- Purpose: Keep the runtime subsystem modular despite the large profile surface.
- Location: `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/strategy.py`, `omnicontrol/runtime/contracts.py`, `omnicontrol/runtime/pivots.py`, `omnicontrol/runtime/remediation.py`, `omnicontrol/runtime/transports.py`, `omnicontrol/runtime/adaptive_startup.py`, `omnicontrol/runtime/invocation.py`, `omnicontrol/runtime/staging.py`, `omnicontrol/runtime/kb.py`, `omnicontrol/runtime/windows_ipc.py`
- Contains: reusable preflight/attempt orchestration, contract evaluation, blocker classification, pivot planning, KB-backed remediation, transport ranking, Windows process/window helpers, payload materialization, and ASCII-safe staging.
- Depends on: each other in a hub-and-spoke pattern centered around `omnicontrol/runtime/live_smoke.py`.
- Used by: smoke profiles and focused unit tests such as `tests/test_orchestrator.py`, `tests/test_strategy.py`, `tests/test_transports.py`, `tests/test_kb.py`, `tests/test_invocation.py`, and `tests/test_windows_ipc.py`.

## Data Flow

**Detect/Plan/Scaffold Flow:**

1. `omnicontrol/__main__.py` transfers control to `omnicontrol.cli.main()`.
2. `omnicontrol/cli.py` parses the command and builds a `CapabilityDetector` plus, for planning and scaffolding, an `AdapterSelector`.
3. `omnicontrol/detector/capability_detector.py` produces a `DetectionResult` using target inspection, hints, and path signatures.
4. `omnicontrol/planner/adapter_selector.py` combines that detection with `omnicontrol/adapters/catalog.py` and `omnicontrol/planner/language_selector.py` to produce an `AdapterPlan`.
5. `omnicontrol/ir/manifest.py` packages detection and plan into a `HarnessManifest`.
6. `omnicontrol/emitters/scaffold.py` writes generated files when the command is `scaffold`; otherwise `omnicontrol/cli.py` serializes the result via `to_jsonable()`.

**Benchmark Flow:**

1. `omnicontrol/cli.py` routes `benchmark` to `omnicontrol/benchmark.py`.
2. `omnicontrol/benchmark.py` reads a benchmark JSON file from `benchmarks/`, loops through items, and reuses the same detect/plan/manifest pipeline as the main CLI.
3. Optional scaffold output is written under a benchmark-local `scaffolds/` directory, and a consolidated JSON report is emitted as `benchmark-report.json`.

**Smoke Runtime Flow:**

1. `omnicontrol/cli.py` routes `smoke` to `omnicontrol/runtime/live_smoke.py:run_smoke`.
2. `run_smoke()` dispatches by profile name into a concrete profile function such as `run_word_workflow_smoke`, `run_chrome_cdp_smoke`, or `run_ue_python_write_smoke`.
3. The profile function assembles preflight checks, primary attempts, and sometimes pivot builders using `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/pivots.py`, and `omnicontrol/runtime/remediation.py`.
4. Platform and transport helpers such as `omnicontrol/runtime/adaptive_startup.py`, `omnicontrol/runtime/transports.py`, `omnicontrol/runtime/windows_ipc.py`, `omnicontrol/runtime/staging.py`, and packaged scripts under `omnicontrol/runtime/scripts/` perform the real process launch, command execution, or UI interaction.
5. `omnicontrol/runtime/strategy.py` evaluates the raw payload against the relevant contract in `omnicontrol/runtime/contracts.py` and rewrites the final status into structured strategy data.
6. `omnicontrol/runtime/kb.py` records the payload into `knowledge/kb.json` and can feed future launch overrides, preferred transport order, remediation actions, and sidecar profile suggestions back into later smoke runs.

**State Management:**
- CLI detection and planning are mostly stateless and derive outputs directly from current inputs.
- Generated scaffold artifacts persist only in the chosen output directory from `omnicontrol/emitters/scaffold.py`.
- Smoke execution persists operational memory in `knowledge/kb.json` through `omnicontrol/runtime/kb.py`.
- Per-run artifacts are written under directories like `smoke-output/...` or explicit output paths handled inside `omnicontrol/runtime/live_smoke.py`.

## Key Abstractions

**DetectionResult / AdapterPlan / HarnessManifest:**
- Purpose: Represent the pipeline boundaries between detection, planning, and generation.
- Examples: `omnicontrol/models.py`, `omnicontrol/ir/manifest.py`
- Pattern: immutable-style dataclass handoff between layers.

**AdapterProfile:**
- Purpose: Centralize adapter priorities, default state models, and default verification methods.
- Examples: `omnicontrol/adapters/catalog.py`
- Pattern: static catalog lookup keyed by adapter name.

**SmokeContract and ConditionSpec:**
- Purpose: Turn raw profile outputs into normalized runtime verdicts with required and desired evidence checks.
- Examples: `omnicontrol/runtime/strategy.py`, `omnicontrol/runtime/contracts.py`
- Pattern: declarative contract evaluation rather than ad hoc per-profile status logic.

**OrchestratorSpec / AttemptSpec / PreflightCheck:**
- Purpose: Standardize multi-attempt execution with preflight gating and attempt selection.
- Examples: `omnicontrol/runtime/orchestrator.py`, usage in `omnicontrol/runtime/live_smoke.py`
- Pattern: mini workflow engine for runtime smoke execution.

**PivotCandidate and remediation action planning:**
- Purpose: Encode how a blocked primary control plane can pivot to sidecars, tooling planes, or alternative entrypoints.
- Examples: `omnicontrol/runtime/pivots.py`, `omnicontrol/runtime/remediation.py`, `omnicontrol/runtime/kb.py`
- Pattern: metadata-driven fallback expansion layered on top of orchestrated attempts.

**TransportDescriptor / TransportAttemptSpec:**
- Purpose: Rank and execute alternative command/control transports while preserving observed winning order.
- Examples: `omnicontrol/runtime/transports.py`, QQMusic-related code paths in `omnicontrol/runtime/live_smoke.py`
- Pattern: ordered transport selection with learned preferences from the knowledge base.

## Entry Points

**CLI Package Entry Point:**
- Location: `omnicontrol/__main__.py`
- Triggers: `python -m omnicontrol`
- Responsibilities: Call `omnicontrol.cli.main()` and exit with its return code.

**Installed Console Script:**
- Location: `pyproject.toml`
- Triggers: `omnicontrol` command after package installation
- Responsibilities: Bind the console script name to `omnicontrol.cli:main`.

**Primary Command Router:**
- Location: `omnicontrol/cli.py`
- Triggers: Any CLI invocation
- Responsibilities: Build parsers, route subcommands, construct detector/planner/runtime objects, and print final payloads.

**Benchmark Entry Point:**
- Location: `omnicontrol/benchmark.py`
- Triggers: `omnicontrol benchmark ...`
- Responsibilities: Batch-run detect/plan/scaffold over benchmark fixtures from `benchmarks/*.json`.

**Smoke Runtime Entry Point:**
- Location: `omnicontrol/runtime/live_smoke.py`
- Triggers: `omnicontrol smoke <profile> ...`
- Responsibilities: Dispatch profile handlers, run orchestration, evaluate contracts, and persist reports plus knowledge.

## Error Handling

**Strategy:** Fail fast on missing prerequisites, downgrade to `blocked` or `partial` when the runtime contract indicates recoverable failure, and preserve structured evidence for later reuse.

**Patterns:**
- CLI-level validation in `omnicontrol/cli.py` raises `ValueError` or `FileNotFoundError` for missing required arguments or executables before deep execution.
- `omnicontrol/runtime/orchestrator.py` catches exceptions inside preflight and attempt functions and converts them into structured orchestration payloads instead of crashing the whole workflow immediately.
- `omnicontrol/runtime/strategy.py` classifies blockers and synthesizes recovery hints from raw payload text.
- Profile functions in `omnicontrol/runtime/live_smoke.py` often accept `ok`, `partial`, and `blocked` as expected terminal states, but raise `RuntimeError` for unstructured hard failure after writing the result artifact.

## Cross-Cutting Concerns

**Logging:** There is no centralized logging framework. Runtime evidence is captured into returned payload dictionaries and persisted as JSON reports in `smoke-output/...` and `knowledge/kb.json`.

**Validation:** Input validation is split between `argparse` in `omnicontrol/cli.py`, file existence checks in runtime helpers such as `omnicontrol/runtime/orchestrator.py:path_exists_check`, and contract validation in `omnicontrol/runtime/strategy.py`.

**Authentication:** No repo-wide auth layer exists. Authentication or environment-sensitive behavior is profile-specific and embedded in smoke profile implementations and metadata such as `omnicontrol/runtime/kb.py`.

---

*Architecture analysis: 2026-04-15*
