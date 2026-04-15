# Codebase Structure

**Analysis Date:** 2026-04-15

## Directory Layout

```text
OmniControl/
├── omnicontrol/               # Source package
│   ├── adapters/              # Static adapter catalog
│   ├── detector/              # Capability detection heuristics
│   ├── emitters/              # Scaffold file generation
│   ├── ir/                    # Manifest construction
│   ├── planner/               # Adapter and language planning
│   ├── runtime/               # Smoke runtime orchestration and OS helpers
│   │   └── scripts/           # Packaged PowerShell, Node, and AppleScript assets
│   └── verifier/              # Verification text helpers
├── tests/                     # Unit and CLI/integration tests
├── benchmarks/                # Benchmark configs and matrix docs
├── docs/                      # Architecture and strategy design docs
├── knowledge/                 # Persistent runtime knowledge base
├── .planning/codebase/        # Generated codebase map documents
├── pyproject.toml             # Packaging and console script entry
├── uv.lock                    # Locked dependency graph
└── README.md                  # Project overview and usage
```

## Directory Purposes

**`omnicontrol/`:**
- Purpose: Main Python package.
- Contains: CLI entrypoints, datamodels, planning logic, runtime logic, and code generation helpers.
- Key files: `omnicontrol/cli.py`, `omnicontrol/models.py`, `omnicontrol/benchmark.py`, `omnicontrol/__main__.py`

**`omnicontrol/detector/`:**
- Purpose: Target inspection and capability inference.
- Contains: detection heuristics and package exports.
- Key files: `omnicontrol/detector/capability_detector.py`

**`omnicontrol/planner/`:**
- Purpose: Convert `DetectionResult` into `AdapterPlan` and language selection.
- Contains: adapter selector, language selector, package exports.
- Key files: `omnicontrol/planner/adapter_selector.py`, `omnicontrol/planner/language_selector.py`

**`omnicontrol/adapters/`:**
- Purpose: Hold the static adapter catalog used by planning.
- Contains: adapter profile definitions.
- Key files: `omnicontrol/adapters/catalog.py`

**`omnicontrol/ir/`:**
- Purpose: Build scaffold manifests from plan output.
- Contains: manifest constructors and package exports.
- Key files: `omnicontrol/ir/manifest.py`

**`omnicontrol/emitters/`:**
- Purpose: Generate scaffold artifacts for new adapters or harnesses.
- Contains: markdown/template rendering and file-writing logic.
- Key files: `omnicontrol/emitters/scaffold.py`

**`omnicontrol/verifier/`:**
- Purpose: Render human-readable verification guidance from plan verification methods.
- Contains: contract summary helpers.
- Key files: `omnicontrol/verifier/contracts.py`

**`omnicontrol/runtime/`:**
- Purpose: Runtime smoke system and reusable execution helpers.
- Contains: the large smoke profile dispatcher, orchestration primitives, contracts, pivots, remediation planning, KB integration, startup helpers, transport ordering, IPC helpers, and staging helpers.
- Key files: `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/strategy.py`, `omnicontrol/runtime/contracts.py`, `omnicontrol/runtime/kb.py`

**`omnicontrol/runtime/scripts/`:**
- Purpose: Store packaged script assets invoked by runtime profiles.
- Contains: `.ps1`, `.js`, and `.applescript` files.
- Key files: `omnicontrol/runtime/scripts/word_export_smoke.ps1`, `omnicontrol/runtime/scripts/chrome_cdp_smoke.js`, `omnicontrol/runtime/scripts/safari_open_smoke.applescript`

**`tests/`:**
- Purpose: Verify core heuristics, CLI flows, and runtime helper modules.
- Contains: `unittest` test modules plus `tests/TEST.md`.
- Key files: `tests/test_core.py`, `tests/test_full_e2e.py`, `tests/test_orchestrator.py`, `tests/test_kb.py`, `tests/test_windows_ipc.py`

**`benchmarks/`:**
- Purpose: Provide sample target matrices for batch evaluation.
- Contains: JSON benchmark definitions and a markdown matrix note.
- Key files: `benchmarks/local_closed_source_windows.json`, `benchmarks/local_closed_source_macos.json`, `benchmarks/LOCAL_TEST_MATRIX.md`

**`docs/`:**
- Purpose: Describe strategy and runtime design decisions that the source code implements.
- Contains: policy and strategy markdown documents.
- Key files: `docs/EXECUTION_STRATEGY.md`, `docs/BACKGROUND_FIRST_POLICY.md`, `docs/GENERIC_BACKGROUND_TRANSPORTS.md`, `docs/SIDECAR_CONTROL_PLANE_UPDATE.md`

**`knowledge/`:**
- Purpose: Persist learned runtime outcomes across smoke runs.
- Contains: `kb.json`
- Key files: `knowledge/kb.json`

## Key File Locations

**Entry Points:**
- `omnicontrol/__main__.py`: Module execution entrypoint for `python -m omnicontrol`.
- `omnicontrol/cli.py`: Main command router and output formatter.
- `pyproject.toml`: Installed `omnicontrol` console script definition.

**Configuration:**
- `pyproject.toml`: Build system, Python requirement, optional dev dependencies, package discovery, and package data.
- `uv.lock`: Locked environment state for the current package dependency set.
- `knowledge/kb.json`: Runtime-learned behavior and profile memory store.

**Core Logic:**
- `omnicontrol/models.py`: Shared dataclasses and serialization helpers.
- `omnicontrol/detector/capability_detector.py`: Detection heuristics.
- `omnicontrol/planner/adapter_selector.py`: Primary adapter planning.
- `omnicontrol/planner/language_selector.py`: Language ranking.
- `omnicontrol/runtime/live_smoke.py`: Smoke execution entry and profile implementations.

**Testing:**
- `tests/test_core.py`: Detector/planner/scaffold behavior.
- `tests/test_full_e2e.py`: CLI end-to-end coverage.
- `tests/test_orchestrator.py`: Runtime orchestration semantics.
- `tests/test_strategy.py`: Contract evaluation behavior.
- `tests/test_kb.py`: Knowledge base logic.

## Naming Conventions

**Files:**
- Use `snake_case.py` for Python modules, for example `capability_detector.py`, `adapter_selector.py`, and `live_smoke.py`.
- Use lower-case, underscore-separated test names prefixed with `test_`, for example `tests/test_transports.py`.
- Use upper-case markdown names for top-level planning and documentation artifacts when they act as canonical docs, for example `README.md` and `benchmarks/LOCAL_TEST_MATRIX.md`.
- Use lower-case, underscore-separated script asset names in `omnicontrol/runtime/scripts/`, for example `chrome_form_write_smoke.js` and `finder_open_smoke.applescript`.

**Directories:**
- Use short lower-case package directories matching architectural slices, for example `omnicontrol/detector/`, `omnicontrol/planner/`, and `omnicontrol/runtime/`.
- Keep runtime helper assets under the subdirectory that owns them; script payloads stay in `omnicontrol/runtime/scripts/` instead of top-level `scripts/`.

## Where to Add New Code

**New detect/plan feature:**
- Primary code: `omnicontrol/detector/` for new target heuristics, `omnicontrol/planner/` for adapter or language selection changes, and `omnicontrol/adapters/catalog.py` if a new adapter profile is required.
- Tests: add corresponding assertions in `tests/test_core.py` or create a focused module such as `tests/test_<feature>.py`.

**New scaffold behavior:**
- Primary code: `omnicontrol/emitters/scaffold.py` and, if the manifest shape changes, `omnicontrol/models.py` plus `omnicontrol/ir/manifest.py`.
- Tests: extend `tests/test_core.py` with generated-file expectations.

**New smoke profile:**
- Implementation: add the profile branch in `omnicontrol/runtime/live_smoke.py`, define its contract in `omnicontrol/runtime/contracts.py`, add metadata in `omnicontrol/runtime/kb.py`, and place any reusable script asset in `omnicontrol/runtime/scripts/`.
- Supporting helpers: if the behavior is reusable across profiles, extract it into a focused runtime helper module under `omnicontrol/runtime/` instead of growing `live_smoke.py` further.
- Tests: add unit coverage in the nearest helper test file such as `tests/test_strategy.py`, `tests/test_pivots.py`, or `tests/test_live_smoke_helpers.py`; add end-to-end CLI coverage only when the new profile can be exercised safely in test conditions.

**New benchmark fixture:**
- Implementation: add JSON config under `benchmarks/`.
- Tests: extend `tests/test_full_e2e.py` or create a focused benchmark test if the fixture changes benchmark semantics.

**New documentation or policy note:**
- Implementation: place source-of-truth architectural notes in `docs/`.
- Planner metadata: place generated mapper outputs in `.planning/codebase/`, not `docs/`.

**Utilities:**
- Shared helpers: place cross-profile runtime helpers in `omnicontrol/runtime/`; place cross-pipeline dataclasses and serialization helpers in `omnicontrol/models.py`.

## Special Directories

**`.planning/codebase/`:**
- Purpose: Generated codebase intelligence documents for later planning and execution steps.
- Generated: Yes
- Committed: Yes

**`knowledge/`:**
- Purpose: Persist runtime learning between smoke runs.
- Generated: Yes
- Committed: Yes

**`omnicontrol/runtime/scripts/`:**
- Purpose: Ship executable helper assets as package data.
- Generated: No
- Committed: Yes

**`OmniControl.egg-info/`:**
- Purpose: Packaging metadata generated by local builds/installations.
- Generated: Yes
- Committed: Yes in the current repository state

**`.venv/`:**
- Purpose: Local virtual environment.
- Generated: Yes
- Committed: No

## Placement Guidance

- Put new public CLI commands in `omnicontrol/cli.py` and keep them thin; move substantive logic into a package module.
- Put new shared dataclasses in `omnicontrol/models.py` when multiple layers need them.
- Put new declarative smoke expectations in `omnicontrol/runtime/contracts.py` before adding profile-specific status branching.
- Put profile-specific process knowledge in `omnicontrol/runtime/kb.py` when it should influence pivots, remediation, or repeated transport choice.
- Do not add new top-level source folders when the code naturally belongs under an existing slice in `omnicontrol/`.

---

*Structure analysis: 2026-04-15*
