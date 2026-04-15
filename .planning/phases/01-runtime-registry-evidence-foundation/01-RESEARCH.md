# Phase 1: Runtime Registry & Evidence Foundation - Research

**Researched:** 2026-04-15
**Domain:** Brownfield Python CLI runtime extraction for profile registry, stable runtime roots, and evidence/result contracts
**Confidence:** HIGH

## User Constraints

- No phase-specific `01-CONTEXT.md` exists in this phase directory, so there are no additional locked decisions beyond `PROJECT.md`, `REQUIREMENTS.md`, and `ROADMAP.md`. [VERIFIED: gsd init + filesystem check]
- Phase 1 scope is limited to `RTF-01`, `RTF-02`, `RTF-04`, `VER-01`, and `VER-02`; diagnostics taxonomy and broader outcome normalization are explicitly deferred to Phase 2. [VERIFIED: roadmap + requirements]
- The project direction is brownfield-first: preserve the existing capability-first CLI/runtime identity instead of replacing it with a new app-specific system. [VERIFIED: PROJECT.md]

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RTF-01 | Framework uses a typed app/profile registry as the single source of truth for supported macOS applications, modes, and metadata | Centralize profile descriptors and derive CLI choices, dispatch, metadata, and contracts from one registry module. [VERIFIED: codebase grep] |
| RTF-02 | Runtime writes artifacts and state to stable runtime-managed locations instead of depending on the current working directory | Introduce a runtime root policy plus a `RuntimePaths` helper and stop calling `Path.cwd()` for durable state. [VERIFIED: codebase grep] |
| RTF-04 | Every macOS run produces a structured evidence bundle that records result metadata and associated artifacts | Introduce a typed evidence bundle and one report writer that always emits `result.json` plus an `artifacts/` subtree. [VERIFIED: codebase grep] |
| VER-01 | Each macOS run writes a structured `result.json` report | Replace per-profile ad hoc JSON writes with one `write_result_bundle()` path. [VERIFIED: codebase grep] |
| VER-02 | Each report references concrete artifact paths for evidence instead of relying only on textual status summaries | Put artifact references in a typed `artifacts[]` section rather than only top-level keys like `output`, `screenshot`, or `report_path`. [VERIFIED: contracts.py + live_smoke.py] |

## Summary

Phase 1 is an extraction phase, not a feature-invention phase. The current runtime already has the right raw ingredients for this work: profile metadata in `kb.py`, contract declarations in `contracts.py`, orchestration primitives in `orchestrator.py`, and smoke entrypoints in `live_smoke.py`. The problem is that the same profile concept is registered in at least three places and durable runtime paths are still derived from `Path.cwd()`, which means behavior changes depending on where the CLI is launched. [VERIFIED: [cli.py](/Users/daizhaorong/OmniControl/omnicontrol/cli.py:61), [kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:12), [contracts.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/contracts.py:6), [live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:345)]

The safest Phase 1 plan is to introduce a thin typed registry and a thin runtime-path/evidence layer without rewriting profile implementations. `run_smoke()` should become a registry lookup plus a compatibility wrapper, existing profile function names should stay callable, and current payload keys should remain present during the migration. That gets the project to one source of truth and stable artifacts without breaking today’s smoke commands or test surface. [VERIFIED: codebase structure + passing targeted tests]

The evidence contract should be intentionally small in Phase 1. Do not try to solve the full blocker taxonomy here. A stable `result.json` should record run identity, profile identity, runtime root, status, timestamps, execution metadata, evidence summary, and concrete artifact references. That contract is enough for later phases to add macOS blocker categories and richer diagnostics without another report-format break. [VERIFIED: requirements + roadmap][ASSUMED]

**Primary recommendation:** Add three new runtime primitives first: `ProfileDescriptor`, `RuntimePaths`, and `ResultBundleWriter`; then adapt `cli.py`, `kb.py`, and `live_smoke.py` to consume them behind compatibility wrappers. [VERIFIED: codebase grep]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Smoke profile registry | API / Backend | — | The CLI and runtime are a local Python process; profile ownership belongs in typed Python descriptors, not scattered CLI literals. [VERIFIED: codebase grep] |
| Runtime root resolution | API / Backend | Database / Storage | Path policy is process-owned logic that decides where persistent KB and run artifacts live. [VERIFIED: codebase grep] |
| Result/evidence bundle emission | API / Backend | Database / Storage | The runtime creates and writes reports/artifacts; storage only persists them. [VERIFIED: live_smoke.py] |
| Knowledge-base persistence | Database / Storage | API / Backend | `kb.json` is durable state; the runtime should call a persistence layer, not build paths inline. [VERIFIED: kb.py] |
| CLI profile choice surface | Frontend Server (CLI boundary) | API / Backend | The command parser exposes available profiles, but choices should be derived from backend descriptors. [VERIFIED: cli.py] |
| Brownfield compatibility wrappers | API / Backend | Frontend Server (CLI boundary) | Existing function names and command arguments need to survive while the new registry is introduced. [VERIFIED: tests + live_smoke.py] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses`, `typing`, `pathlib`, `json`, `tempfile` | builtin with Python 3.10+ | Typed descriptors, path handling, report serialization, atomic temp-file writes | The current codebase already depends on stdlib dataclasses/pathlib, and Python docs support `NamedTemporaryFile` plus `Path.replace()` for safe staged writes. [VERIFIED: codebase grep][CITED: https://docs.python.org/3/library/tempfile.html][CITED: https://docs.python.org/3/library/pathlib.html] |
| `platformdirs` | 4.9.4, uploaded 2026-03-05 | Stable per-user data/config/cache/runtime roots independent of `cwd` | This is the smallest current package that standardizes writable app directories across macOS/Windows/Linux and matches the project’s `>=3.10` floor. [VERIFIED: PyPI][CITED: https://pypi.org/pypi/platformdirs/json] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `unittest` | builtin | Registry/path/result-bundle regression tests | Keep using the existing suite style; do not introduce pytest-only patterns in this phase. [VERIFIED: TESTING.md + pyproject.toml] |
| Python stdlib `importlib.resources` | builtin | Resolve packaged AppleScript/JS/PowerShell assets relative to the installed package | Keep using this for runtime scripts; do not bind asset lookup to repo-relative paths. [VERIFIED: live_smoke.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `platformdirs` runtime roots | Repo-root `.omnicontrol/` or `knowledge/` + `smoke-output/` | Better local discoverability, but weaker for installed CLI usage outside the repo and still requires custom cross-platform path policy. [VERIFIED: current repo layout][ASSUMED] |
| Typed descriptor registry | Keep parallel literals in `cli.py`, `kb.py`, and `contracts.py` | No migration work now, but registry drift remains the main scaling bottleneck. [VERIFIED: codebase grep] |
| Central result writer | Keep per-profile `report_path.write_text(...)` blocks | Lower short-term churn, but Phase 2+ will keep duplicating report fields and artifact linkage. [VERIFIED: codebase grep] |

**Installation:**
```bash
uv pip install platformdirs==4.9.4
```

**Version verification:** `platformdirs` 4.9.4 is current on PyPI and was uploaded on 2026-03-05. [VERIFIED: PyPI][CITED: https://pypi.org/project/platformdirs/]

## Architecture Patterns

### System Architecture Diagram

```text
omnicontrol smoke <profile>
        |
        v
  CLI parser (`cli.py`)
        |
        v
  Registry lookup (`ProfileDescriptor`)
        |
        +--> derive CLI-visible metadata and argument needs
        |
        +--> derive runtime roots (`RuntimePaths`)
        |
        v
  Existing profile executor (`run_*_smoke`)
        |
        +--> preflight / orchestration / contract evaluation
        |
        v
  Result bundle writer
        |
        +--> result.json
        +--> artifacts/
        +--> compatibility top-level payload keys
        |
        v
  Knowledge store (`kb.json`) update via stable root
```

### Recommended Project Structure

```text
omnicontrol/runtime/
├── registry.py       # Typed profile descriptors and registry helpers
├── paths.py          # RuntimeRoots / RuntimePaths resolution
├── results.py        # ResultBundle, ArtifactRef, writer helpers
├── kb.py             # Knowledge persistence + profile-derived helpers
├── contracts.py      # Contract declarations keyed by profile id
└── live_smoke.py     # Thin dispatcher + profile implementations
```

### Pattern 1: Descriptor-Backed Profile Registry
**What:** Define one typed `ProfileDescriptor` per profile with fields for `id`, `platform`, `invocation_context`, `interaction_level`, `control_planes`, `contract_key`, `default_artifact_subdir`, and an executor callable or executor name. [VERIFIED: kb.py + contracts.py + live_smoke.py]

**When to use:** Immediately for every existing smoke profile; do not create a second macOS-only registry. [VERIFIED: brownfield code shape]

**Example:**
```python
# Source: current codebase synthesis from cli.py, kb.py, contracts.py, live_smoke.py
from dataclasses import dataclass
from typing import Callable

@dataclass(slots=True)
class ProfileDescriptor:
    id: str
    platform: str
    invocation_context: str
    interaction_level: str
    control_planes: tuple[str, ...]
    contract_key: str
    default_run_dir: str
    executor: Callable[..., dict]

PROFILE_REGISTRY: dict[str, ProfileDescriptor] = {
    "finder-open": ProfileDescriptor(
        id="finder-open",
        platform="macos",
        invocation_context="none",
        interaction_level="open",
        control_planes=("native_script", "accessibility"),
        contract_key="finder-open",
        default_run_dir="finder-open",
        executor=run_finder_open_smoke,
    ),
}
```

### Pattern 2: Runtime Context and Stable Roots
**What:** Resolve one `RuntimePaths` object per invocation and pass it downward instead of letting each profile derive `Path.cwd()` defaults. [VERIFIED: codebase grep][CITED: https://pypi.org/pypi/platformdirs/json]

**When to use:** For any durable path: `kb.json`, `result.json`, screenshots, generated DOCX/PDF, sidecar run dirs, and staged script payloads. [VERIFIED: live_smoke.py + kb.py]

**Example:**
```python
# Source: recommended pattern based on Python pathlib/tempfile docs and current cwd drift
from dataclasses import dataclass
from pathlib import Path
from platformdirs import PlatformDirs

@dataclass(slots=True)
class RuntimePaths:
    root: Path
    runs_root: Path
    knowledge_path: Path

    def run_dir(self, profile_id: str, run_id: str) -> Path:
        return self.runs_root / profile_id / run_id

def default_runtime_paths() -> RuntimePaths:
    dirs = PlatformDirs("OmniControl", False)
    root = dirs.user_data_path
    return RuntimePaths(
        root=root,
        runs_root=root / "runs",
        knowledge_path=root / "knowledge" / "kb.json",
    )
```

### Pattern 3: Central Result Bundle Writer
**What:** Emit one canonical bundle format with a stable schema and artifact references, while preserving legacy top-level keys during the migration window. [VERIFIED: live_smoke.py + contracts.py][ASSUMED]

**When to use:** For every smoke profile before writing to disk or recording KB entries. [VERIFIED: codebase grep]

**Example:**
```python
# Source: recommended pattern based on existing payload + contract structure
from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import tempfile

@dataclass(slots=True)
class ArtifactRef:
    kind: str
    path: str
    required: bool = False
    description: str | None = None

@dataclass(slots=True)
class ResultBundle:
    schema_version: str
    run_id: str
    profile: str
    status: str
    report_path: str
    artifacts: list[ArtifactRef] = field(default_factory=list)
    strategy: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

def write_bundle(bundle: ResultBundle, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=report_path.parent) as tmp:
        json.dump(asdict(bundle), tmp, indent=2, ensure_ascii=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(report_path)
```

### Anti-Patterns to Avoid

- **Big-bang rewrite of `live_smoke.py`:** Phase 1 should not repartition all 4,048 lines at once; extract registry/path/result seams first and keep executors in place. [VERIFIED: wc + concerns audit]
- **MacOS-only registry fork:** The requirement is a single typed app/profile registry, not a second registry that only covers the new phase. [VERIFIED: REQUIREMENTS.md]
- **Schema-first over-design:** Do not introduce a huge JSON schema or external validation framework before the fields are stabilized by real runs. [ASSUMED]
- **Hard switch to new paths without compatibility migration:** Existing users may already rely on repo-local `knowledge/kb.json` and `smoke-output/`; preserve a legacy import path or one-time migration. [VERIFIED: repo layout][ASSUMED]

## Recommended Implementation Slices

1. **Introduce `registry.py` without changing behavior**
   - Move profile identity fields out of `kb.py` into typed descriptors.
   - Derive CLI `choices=` from the registry.
   - Keep `run_smoke()` branch logic temporarily, but replace string literals with descriptor lookups.
   - Target files: `omnicontrol/runtime/registry.py`, `omnicontrol/cli.py`, `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/kb.py`. [VERIFIED: codebase grep]

2. **Introduce `paths.py` and stable root resolution**
   - Add explicit runtime-root precedence: CLI override or env override, then default runtime root.
   - Replace durable `Path.cwd()` usage in KB and result-output defaults.
   - Keep caller-supplied `--output` working exactly as today.
   - Target files: `omnicontrol/runtime/paths.py`, `omnicontrol/runtime/kb.py`, `omnicontrol/runtime/live_smoke.py`. [VERIFIED: codebase grep]

3. **Introduce `results.py` and central report emission**
   - Add `ResultBundle`, `ArtifactRef`, `write_bundle()`, and payload-backfill helpers.
   - Make every profile call the same writer rather than `report_path.write_text(...)`.
   - Ensure `report_path` still exists in the returned payload for compatibility.
   - Target files: `omnicontrol/runtime/results.py`, `omnicontrol/runtime/live_smoke.py`. [VERIFIED: codebase grep]

4. **Migrate KB persistence to stable paths and atomic writes**
   - Point `kb_path()` at the runtime root instead of `Path.cwd()`.
   - Use staged temp-file writes plus `Path.replace()`.
   - Leave KB schema version as-is unless a migration is required by new lookup data.
   - Target files: `omnicontrol/runtime/kb.py`. [VERIFIED: kb.py][CITED: https://docs.python.org/3/library/tempfile.html][CITED: https://docs.python.org/3/library/pathlib.html]

5. **Backfill focused tests before deeper runtime refactors**
   - Add tests for registry-derived CLI choices, root resolution, result-bundle writing, and legacy payload compatibility.
   - Keep macOS smoke tests mocked; do not require live TCC permissions in this phase.
   - Target files: new `tests/test_registry.py`, `tests/test_paths.py`, `tests/test_results.py`, plus updates to `tests/test_full_e2e.py` and `tests/test_kb.py`. [VERIFIED: current test suite]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS-specific user/runtime directories | Custom `if sys.platform` directory map | `platformdirs` | This is solved already and reduces cross-platform path bugs. [VERIFIED: PyPI][CITED: https://pypi.org/pypi/platformdirs/json] |
| Atomic JSON persistence | Open/write directly to the final `kb.json`/`result.json` path | `tempfile.NamedTemporaryFile` + `Path.replace()` | The Python docs already support this staged-write pattern, and current direct writes are vulnerable to torn updates. [VERIFIED: kb.py + live_smoke.py][CITED: https://docs.python.org/3/library/tempfile.html][CITED: https://docs.python.org/3/library/pathlib.html] |
| Profile availability lists | Manual duplicate literals in argparse and runtime modules | Derive from `ProfileDescriptor` registry | The current duplication is the scaling bottleneck and a drift risk. [VERIFIED: codebase grep] |
| Artifact references | Flat ad hoc keys only (`output`, `screenshot`, `report_path`) | Typed `artifacts[]` collection plus legacy backfill | Later phases need evidence composability across apps and modes. [VERIFIED: contracts.py + live_smoke.py][ASSUMED] |

**Key insight:** Phase 1 should hand-roll only the domain model that is unique to OmniControl, not the generic filesystem and registry plumbing that already has standard solutions. [VERIFIED: codebase + external docs]

## Common Pitfalls

### Pitfall 1: Breaking CLI behavior while extracting the registry
**What goes wrong:** The new registry changes profile IDs, required args, or `choices` ordering and existing smoke commands stop working. [VERIFIED: cli.py]
**Why it happens:** `cli.py`, `kb.py`, `contracts.py`, and `live_smoke.py` all currently encode profile identity independently. [VERIFIED: codebase grep]
**How to avoid:** Add the registry first, derive CLI choices from it, and keep old executor function names plus smoke args intact. [VERIFIED: current brownfield seams]
**Warning signs:** Tests begin failing in `tests/test_full_e2e.py` or profile IDs disappear from `omnicontrol smoke --help`. [VERIFIED: test suite]

### Pitfall 2: Solving cwd drift only for reports, not for KB and sidecars
**What goes wrong:** `result.json` moves to a stable root, but KB writes or sidecar outputs still land under the invocation directory. [VERIFIED: codebase grep]
**Why it happens:** Path defaults are repeated in many helper/profile functions, not only in one entrypoint. [VERIFIED: live_smoke.py + kb.py]
**How to avoid:** Introduce `RuntimePaths` and prohibit durable `Path.cwd()` usage below CLI argument parsing. [VERIFIED: codebase grep][ASSUMED]
**Warning signs:** Running the same profile from two directories creates two `kb.json` files or mismatched sidecar artifact trees. [VERIFIED: concerns audit]

### Pitfall 3: Making `result.json` a dump of whatever payload exists today
**What goes wrong:** The contract stays unstable because every profile keeps inventing its own top-level evidence keys. [VERIFIED: contracts.py + live_smoke.py]
**Why it happens:** Current evidence is implicit in payload shape and contract-specific `evidence_keys`, not in a shared bundle model. [VERIFIED: strategy.py + contracts.py]
**How to avoid:** Separate canonical bundle fields from profile-specific evidence details and artifact refs. [VERIFIED: current contract model][ASSUMED]
**Warning signs:** Phase 2 needs to change report shape again just to add blocker categories or preflight evidence. [ASSUMED]

### Pitfall 4: Introducing a new dependency when stdlib would do
**What goes wrong:** The phase adds validation or serialization libraries that do not materially reduce risk. [VERIFIED: current dependencies are empty]
**Why it happens:** Registry/evidence work often drifts toward schema framework adoption.
**How to avoid:** Keep typing in stdlib dataclasses for now; only add `platformdirs` because it directly addresses a documented current defect. [VERIFIED: pyproject.toml + concerns audit][CITED: https://pypi.org/pypi/platformdirs/json]
**Warning signs:** The plan starts including migration to Pydantic or a new CLI framework even though the current problem is registry/path duplication. [ASSUMED]

### Pitfall 5: Running or validating with the wrong Python
**What goes wrong:** Tests fail on imports or dataclass features when invoked with system `python3` 3.9.6 instead of the repo virtualenv’s Python 3.11.11. [VERIFIED: local environment + TESTING.md]
**Why it happens:** The repo requires Python `>=3.10`, but the shell default is older on this machine. [VERIFIED: pyproject.toml + local environment]
**How to avoid:** Standardize validation commands on `.venv/bin/python`. [VERIFIED: local environment]
**Warning signs:** Import errors around `@dataclass(slots=True)` or inconsistent local test results. [VERIFIED: TESTING.md]

## Code Examples

Verified patterns from current code and official docs:

### Derive CLI smoke choices from the registry
```python
# Source: current codebase issue in cli.py + recommended fix
def register_smoke_command(subparsers, registry):
    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("profile", choices=sorted(registry.profile_ids()))
    smoke.add_argument("--source")
    smoke.add_argument("--output")
    smoke.add_argument("--query")
    smoke.add_argument("--url")
```

### Atomic JSON write for KB or result bundles
```python
# Source: Python tempfile/pathlib docs
import json
import tempfile
from pathlib import Path

def atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as tmp:
        json.dump(payload, tmp, indent=2, ensure_ascii=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parallel registries in multiple files | Single typed registry with derived views | Phase 1 recommendation | Eliminates drift between CLI, contracts, metadata, and dispatch. [VERIFIED: codebase grep][ASSUMED] |
| `Path.cwd()` for durable runtime state | Stable runtime root policy | Phase 1 recommendation | Makes CLI behavior deterministic from any working directory. [VERIFIED: concerns audit][ASSUMED] |
| Per-profile JSON writes | Shared result bundle writer | Phase 1 recommendation | Makes evidence extensible for later diagnostics phases. [VERIFIED: codebase grep][ASSUMED] |

**Deprecated/outdated:**
- Cwd-relative durable KB and artifact defaults are already known project defects and should not be extended further. [VERIFIED: concerns audit]

## Brownfield Migration Strategy

- Preserve profile IDs exactly as they exist today; the registry should be additive first, not a rename vehicle. [VERIFIED: cli.py + tests]
- Preserve return payload compatibility for current callers and tests: keep `status`, `report_path`, and existing common evidence keys while adding canonical bundle fields. [VERIFIED: tests/test_live_smoke_macos.py]
- Migrate path defaults behind helpers first, then move profile functions one by one to those helpers. Do not change every executor signature in the same slice. [VERIFIED: live_smoke.py size + existing tests]
- Import or copy legacy repo-local `knowledge/kb.json` into the stable root on first write, or provide an explicit one-time migration command. This is the cleanest way to avoid silent knowledge loss after the path change. [VERIFIED: current repo layout][ASSUMED]
- Keep Windows-heavy profiles compiling even if this phase is macOS-focused; the registry extraction should be profile-family-agnostic. [VERIFIED: current registry spans Windows and macOS]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `platformdirs` is acceptable as the only new dependency for stable runtime roots | Standard Stack | If rejected, planner must use a repo-root or env-configured root strategy instead |
| A2 | A compatibility window keeping legacy top-level payload keys is needed after introducing the canonical result bundle | Architecture Patterns / Migration Strategy | If unnecessary, implementation can be simpler; if necessary and skipped, current callers/tests may break |
| A3 | First-write import or explicit migration of legacy `knowledge/kb.json` is preferable to silently abandoning repo-local state | Brownfield Migration Strategy | If wrong, planner may over-engineer migration or preserve stale state unexpectedly |

## Open Questions

1. **What should the default stable runtime root be for local development?**
   - What we know: `Path.cwd()` is wrong for durable state, and the project is both a repo and an installable CLI. [VERIFIED: codebase grep + pyproject.toml]
   - What's unclear: Whether the team prefers repo-local discoverability or user-scoped app dirs as the default developer experience. [ASSUMED]
   - Recommendation: Default to user-scoped runtime roots, but support an explicit env/CLI override for repo-local development. [ASSUMED]

2. **Should the KB path change include automatic migration?**
   - What we know: Existing learned state lives under repo-local `knowledge/kb.json`. [VERIFIED: repo layout + kb.py]
   - What's unclear: Whether preserving historical KB cases matters for current operators.
   - Recommendation: Plan a minimal first-write migration or a one-shot command; do not silently fork state. [ASSUMED]

3. **How much of `result.json` should be canonical in Phase 1?**
   - What we know: Requirements only demand structured result reports and artifact references, not the full blocker taxonomy. [VERIFIED: REQUIREMENTS.md]
   - What's unclear: Whether downstream tooling will consume `result.json` immediately.
   - Recommendation: Canonicalize run identity, status, timestamps, artifact refs, strategy summary, and runtime-path metadata now; keep detailed evidence payload profile-specific. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Repo Python | Implementation + validation | ✓ | `.venv/bin/python` 3.11.11 | — |
| System Python | Ad hoc CLI/test invocation | ✓ but wrong baseline | `python3` 3.9.6 | Use `.venv/bin/python` |
| `osascript` | Mocked macOS smoke helpers and future live macOS runs | ✓ | `/usr/bin/osascript` present | Mocked tests if live automation not needed |
| Node.js | Existing CDP helper scripts | ✓ | 24.7.0 | Mocked tests for this phase |
| PowerShell / `pwsh` | Windows-heavy smoke profiles | ✗ | — | No local fallback for real Windows runtime validation |
| `uv` | Dependency install and workflow commands | ✓ | 0.8.14 | `pip` if needed |

**Missing dependencies with no fallback:**
- PowerShell is absent locally, so Windows-heavy smoke profiles cannot be exercised end-to-end on this machine. [VERIFIED: local environment]

**Missing dependencies with fallback:**
- System `python3` is too old for the repo floor, but `.venv/bin/python` is available and works. [VERIFIED: local environment + pyproject.toml]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib) [VERIFIED: TESTING.md] |
| Config file | none — existing suite uses direct `unittest` discovery [VERIFIED: TESTING.md] |
| Quick run command | `.venv/bin/python -m unittest tests.test_kb tests.test_strategy tests.test_live_smoke_macos -v` [VERIFIED: local run] |
| Full suite command | `.venv/bin/python -m unittest discover -s tests -v` [VERIFIED: TESTING.md] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RTF-01 | Registry is the single source for CLI choices and profile metadata | unit + CLI | `.venv/bin/python -m unittest tests.test_registry tests.test_full_e2e -v` | ❌ Wave 0 |
| RTF-02 | Durable KB and run artifacts resolve independent of `cwd` | unit + filesystem | `.venv/bin/python -m unittest tests.test_paths tests.test_kb -v` | ❌ Wave 0 |
| RTF-04 | Each run emits a structured evidence bundle | unit | `.venv/bin/python -m unittest tests.test_results -v` | ❌ Wave 0 |
| VER-01 | `result.json` is written via one canonical writer | unit + mocked integration | `.venv/bin/python -m unittest tests.test_results tests.test_live_smoke_macos -v` | ❌ Wave 0 |
| VER-02 | `result.json` contains concrete artifact references | unit + mocked integration | `.venv/bin/python -m unittest tests.test_results tests.test_live_smoke_macos -v` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m unittest tests.test_kb tests.test_strategy tests.test_live_smoke_macos -v`
- **Per wave merge:** `.venv/bin/python -m unittest discover -s tests -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_registry.py` — verify CLI choices, metadata derivation, and descriptor completeness
- [ ] `tests/test_paths.py` — verify runtime-root precedence, stable run dirs, and `cwd` independence
- [ ] `tests/test_results.py` — verify canonical bundle shape, artifact refs, atomic write behavior, and legacy payload compatibility
- [ ] `tests/test_kb.py` additions — verify stable KB path resolution and migration/compatibility behavior
- [ ] `tests/test_full_e2e.py` additions — verify `omnicontrol smoke` still accepts existing profile IDs derived from the registry

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | none — local CLI only in this phase |
| V3 Session Management | no | none |
| V4 Access Control | no | none |
| V5 Input Validation | yes | Validate profile IDs, path overrides, and output locations before writes using typed registry/path helpers. [VERIFIED: cli.py + live_smoke.py] |
| V6 Cryptography | no | none required in this phase |

### Known Threat Patterns for Python CLI runtime state

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Writing durable state to attacker-controlled or accidental `cwd` | Tampering | Resolve durable paths from runtime policy, not process working directory. [VERIFIED: concerns audit] |
| Partial or torn JSON writes for `kb.json` / `result.json` | Tampering | Staged temp-file write plus atomic replace. [VERIFIED: kb.py][CITED: https://docs.python.org/3/library/tempfile.html][CITED: https://docs.python.org/3/library/pathlib.html] |
| Unvalidated `--output` paths overwriting unexpected locations | Tampering | Normalize explicit overrides and restrict directory/file semantics per profile mode. [VERIFIED: cli.py + live_smoke.py][ASSUMED] |

## Sources

### Primary (HIGH confidence)

- [PROJECT.md](/Users/daizhaorong/OmniControl/.planning/PROJECT.md) - project direction and constraints
- [REQUIREMENTS.md](/Users/daizhaorong/OmniControl/.planning/REQUIREMENTS.md) - Phase 1 requirement scope
- [ROADMAP.md](/Users/daizhaorong/OmniControl/.planning/ROADMAP.md) - phase goal and success criteria
- [ARCHITECTURE.md](/Users/daizhaorong/OmniControl/.planning/codebase/ARCHITECTURE.md) - runtime layering and flow
- [CONCERNS.md](/Users/daizhaorong/OmniControl/.planning/codebase/CONCERNS.md) - duplicated registry and cwd-path defects
- [TESTING.md](/Users/daizhaorong/OmniControl/.planning/codebase/TESTING.md) - test framework and local validation constraints
- [cli.py](/Users/daizhaorong/OmniControl/omnicontrol/cli.py:61) - hard-coded smoke profile list and cwd-relative defaults
- [kb.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/kb.py:384) - cwd-relative KB path and metadata registry
- [contracts.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/contracts.py:6) - shared contract declarations
- [live_smoke.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/live_smoke.py:64) - dispatcher, executor signatures, and repeated report writing
- [strategy.py](/Users/daizhaorong/OmniControl/omnicontrol/runtime/strategy.py:1) - normalized smoke result model
- [tests/test_kb.py](/Users/daizhaorong/OmniControl/tests/test_kb.py:1) - current metadata-side behavior coverage
- [tests/test_live_smoke_macos.py](/Users/daizhaorong/OmniControl/tests/test_live_smoke_macos.py:1) - mocked macOS runtime expectations
- [tests/test_full_e2e.py](/Users/daizhaorong/OmniControl/tests/test_full_e2e.py:1) - CLI command-level coverage
- Python `tempfile` docs - staged temporary files and cleanup semantics: https://docs.python.org/3/library/tempfile.html
- Python `pathlib` docs - `Path.replace()` behavior: https://docs.python.org/3/library/pathlib.html
- `platformdirs` PyPI metadata and docs links: https://pypi.org/pypi/platformdirs/json

### Secondary (MEDIUM confidence)

- `platformdirs` project page with release date and package details: https://pypi.org/project/platformdirs/

### Tertiary (LOW confidence)

- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - mostly stdlib plus one verified small dependency with current PyPI metadata
- Architecture: HIGH - recommendations map directly onto observed code duplication and path defects
- Pitfalls: HIGH - each major pitfall is already visible in code, tests, or prior concerns docs

**Research date:** 2026-04-15
**Valid until:** 2026-05-15
