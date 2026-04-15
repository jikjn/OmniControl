# Architecture Patterns

**Domain:** Brownfield macOS local automation framework
**Researched:** 2026-04-15

## Recommended Architecture

Keep the existing capability-first shape, but split the current smoke runtime into four explicit layers:

```text
Capability Detection / Planning
    -> App Profile Registry
        -> Workflow Runner
            -> Control-Plane Executors
                -> Verification + Evidence Pipeline
                    -> Knowledge Store
```

The current codebase already has the seeds of this model: contracts, orchestrator specs, transport ranking, pivots, and knowledge reuse exist. The scaling issue is that app-specific logic, profile registration, control-plane invocation, and evidence shaping are still coupled inside `omnicontrol/runtime/live_smoke.py`. The brownfield move is not a rewrite. It is to make `live_smoke.py` a thin dispatcher and move each concern behind typed interfaces that new macOS apps can implement incrementally.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Capability Detector / Planner | Infer likely adapters and verification style from target signals | App Profile Registry, manifest/scaffold layer |
| App Profile Registry | Single source of truth for supported applications, capability modes, supported control planes, launch hints, verification contracts, sidecars, and evidence schema | CLI, Workflow Runner, Knowledge Store |
| Workflow Runner | Execute a `read`, `write`, or `workflow` request as a sequence of steps with retries, pivots, and status normalization | App Profile Registry, Control-Plane Executors, Verification Pipeline |
| Control-Plane Executors | Provide uniform execution APIs for AppleScript/JXA, Accessibility/UI scripting, browser/CDP, shell/CLI, file/document mutation, and future vision/plugin planes | Workflow Runner, Evidence Pipeline |
| Verification Pipeline | Evaluate step-level and workflow-level contracts, classify blockers, and emit normalized `ok/partial/blocked/error` results | Workflow Runner, Knowledge Store |
| Evidence Pipeline | Persist screenshots, exported files, DOM snapshots, window titles, stdout/stderr, step traces, and structured assertions in a stable artifact bundle | Verification Pipeline, Knowledge Store |
| Knowledge Store | Learn preferred transports, launch overrides, failure signatures, permission blockers, and last-known-good verification strategies | App Profile Registry, Workflow Runner |
| Artifact/Config Root Resolver | Resolve project-root or user-config-root state paths instead of `Path.cwd()` | Knowledge Store, Evidence Pipeline, CLI |

### App Profile Shape

The core extension point should be an `AppProfile` descriptor, not another branch in `run_smoke()`. Each app contributes metadata and references to reusable executors.

Recommended fields:

| Field | Purpose |
|------|---------|
| `profile_id` | Stable identifier, also CLI choice |
| `product_key` | App family key used for knowledge reuse across read/write/workflow profiles |
| `platform` | `macos` now, extensible later |
| `modes` | `read`, `write`, `workflow`, optionally `diagnose` |
| `capabilities` | Capability-first labels the planner can reason about |
| `control_planes` | Ordered supported planes such as `applescript`, `accessibility`, `cdp`, `shell`, `file`, `vision` |
| `launch_strategy` | How to start or attach to the app |
| `step_factory` | Builds workflow steps from reusable primitives |
| `contract` | Verification contract or contract set |
| `evidence_schema` | Required and optional evidence keys |
| `sidecars` | Secondary profile or secondary plane fallbacks |
| `preflight_checks` | Permissions, app installed, automation entitlement, debugger port, fixture availability |
| `risk_flags` | Focus-sensitive, destructive, background-safe, slow-start, permission-heavy |

This replaces the current three-way drift between CLI choices, `PROFILE_METADATA`, and `run_smoke()` dispatch.

### Control-Plane Abstractions

The framework should treat control planes as interchangeable executors with shared result semantics. The important boundary is: app adapters describe intent, control-plane executors perform the operation.

| Control Plane | Use For | Notes |
|--------------|---------|------|
| `applescript` / `jxa` | Native scriptable macOS apps such as Finder, Safari, Office for Mac | Best first choice when the app exposes a stable dictionary |
| `accessibility` | UI-driven read/write when no native automation surface exists | Must surface focus sensitivity and permissions as first-class blockers |
| `cdp` | Browser and Electron-style targets | Prefer for deterministic DOM read/write where available |
| `shell` / `cli` | Developer tools and apps with strong command surfaces | Best for low-focus, background-safe operations |
| `file` / `document` | Verification by exported artifact or direct file mutation | Often paired with another plane for postcondition checks |
| `vision` | Last-resort verification or interaction for weak surfaces | Keep isolated as a fallback plane, not the default architecture |

Each executor should implement the same conceptual interface:

```typescript
interface ControlPlaneExecutor {
  plane: string;
  preflight(step, context): PreflightResult;
  run(step, context): StepResult;
  collectEvidence(step, context, raw): EvidenceBundle;
  classifyFailure(raw): BlockerInfo[];
}
```

In Python this can be a protocol or dataclass-backed callable bundle. The important part is stable input/output shape, not OO purity.

### Workflow Runner

The unit of execution should move from “one profile function” to “one workflow definition made of steps.”

Recommended step taxonomy:

| Step Type | Purpose |
|-----------|---------|
| `launch_or_attach` | Start app or attach to existing instance |
| `read_state` | Read window/DOM/document/application state |
| `write_action` | Perform a mutation |
| `verify_postcondition` | Assert direct result of the mutation |
| `collect_artifact` | Export/save/screenshot/log for evidence |
| `pivot` | Switch control plane or sidecar profile |

This lets the same app expose:

```text
read = launch_or_attach -> read_state -> verify_postcondition
write = launch_or_attach -> write_action -> verify_postcondition -> collect_artifact
workflow = launch_or_attach -> read_state -> write_action -> verify_postcondition -> read_state -> collect_artifact
```

That is the right granularity for macOS because verification often needs a different plane than mutation. Example: write via AppleScript, verify via file artifact; or write via Accessibility, verify via AppleScript-readable state.

## Data Flow

1. Planner selects an app family and desired mode from capability signals.
2. App Profile Registry resolves the concrete macOS profile and supported control planes.
3. Workflow Runner builds the step graph for the requested mode.
4. Each step asks the chosen Control-Plane Executor for preflight, run, and evidence collection.
5. Verification Pipeline evaluates step contracts first, then the overall workflow contract.
6. Evidence Pipeline writes a stable artifact bundle:
   - `result.json`
   - `orchestration.json`
   - `evidence/` for screenshots, exported docs, DOM dumps, logs
   - `summary.md` for operator review
7. Knowledge Store records winning transport order, launch overrides, blocker fingerprints, and verification hints keyed by `product_key + mode + plane`.
8. Later runs reuse knowledge without changing the declarative app profile.

## Patterns to Follow

### Pattern 1: Registry-Driven Profiles
**What:** Define app support once in a typed registry and derive CLI choices, metadata, dispatch, and docs from it.
**When:** Immediately. This is the highest-leverage brownfield extraction because current registration is duplicated.
**Example:**
```typescript
profile = AppProfile(
  profile_id="safari-dom-write",
  product_key="safari",
  platform="macos",
  modes={"write"},
  control_planes=["applescript", "accessibility"],
  contract=SAFARI_DOM_WRITE_CONTRACT,
  step_factory=build_safari_dom_write_steps,
)
```

### Pattern 2: App Adapter Describes Intent, Executors Perform It
**What:** Keep app modules thin. They build steps and expected state, but do not embed subprocess, script-launch, and artifact-writing details.
**When:** For every new macOS app adapter.
**Example:**
```typescript
steps = [
  launch_or_attach("Safari"),
  write_dom(selector="#note", value="OmniControl wrote this", plane="applescript"),
  verify_dom(selector="#note", expected="OmniControl wrote this", plane="applescript"),
]
```

### Pattern 3: Verification Separate From Execution
**What:** A step can succeed operationally while failing verification. Preserve both.
**When:** Always, especially for UI scripting and focus-sensitive flows.
**Example:**
```typescript
StepResult {
  execution_status: "ok",
  verification_status: "partial",
  evidence: {"textarea_value": "", "window_title": "Safari"}
}
```

### Pattern 4: Evidence Bundle Per Run
**What:** Standardize artifacts so every control plane emits comparable evidence.
**When:** Before adding many more apps. Without this, `partial` vs `blocked` becomes hard to trust.
**Example:**
```text
artifacts/<run-id>/
  result.json
  orchestration.json
  evidence/
    screenshot.png
    stdout.txt
    dom.json
    exported.docx
```

### Pattern 5: Workflow Composition Over Profile Explosion
**What:** Define `read`, `write`, and `workflow` as compositions of shared steps rather than unrelated profile functions.
**When:** As `live_smoke.py` is split.
**Example:** `word-workflow` should be composed from document creation, content write, save/export, and artifact verification primitives, not a custom one-off body.

## Verification and Evidence Architecture

Verification needs two levels, not one:

| Level | Purpose | Output |
|------|---------|--------|
| Step verification | Did this specific control-plane action produce the expected local change? | Step assertion result plus evidence |
| Workflow verification | Did the end-to-end user-visible outcome occur? | Final normalized status plus aggregate evidence |

Recommended evidence categories:

| Evidence Type | Why It Matters |
|--------------|----------------|
| App state evidence | Window title, URL, selected file, document metadata |
| Artifact evidence | Exported file exists, checksum/magic, parsed content |
| Visual evidence | Screenshot before/after when state is not otherwise readable |
| Transport evidence | Which plane/transport won, attempts tried, timings |
| Failure evidence | stderr/stdout, AppleScript errors, permissions diagnosis, focused-window mismatch |
| Environment evidence | App version, bundle ID, macOS version, automation permissions hints |

Recommended result model additions:

| Field | Why |
|------|-----|
| `execution_status` | Distinguish transport success from verification success |
| `verification_status` | Make failed assertions explicit |
| `blocker_class` | `permissions`, `launch`, `focus`, `transport`, `adapter`, `environment` |
| `evidence_manifest` | Stable list of produced artifacts |
| `step_results` | Critical for debugging multi-step workflows |
| `winning_plane` | Needed for learning and future planning |

The current `SmokeContract` model is a good base. Extend it so contracts can evaluate both step outputs and final outputs. Do not bury evidence only in ad hoc payload keys.

## Anti-Patterns to Avoid

### Anti-Pattern 1: App Logic Embedded In The Global Dispatcher
**What:** More `if profile == ...` branches in `live_smoke.py`.
**Why bad:** Every new macOS app increases coupling between dispatch, runtime helpers, and verification details.
**Instead:** One registry entry plus one app module with a step factory.

### Anti-Pattern 2: Plane-Specific Payload Shapes
**What:** Each control plane returning unrelated keys and custom status interpretation.
**Why bad:** Verification becomes per-profile glue code.
**Instead:** Normalize through `StepResult`, `EvidenceBundle`, and `BlockerInfo`.

### Anti-Pattern 3: CWD-Scoped State
**What:** Knowledge and artifacts rooted at `Path.cwd()`.
**Why bad:** Brownfield scaling breaks because evidence and learned behavior fragment by invocation directory.
**Instead:** Resolve project root or configurable state root once at startup.

### Anti-Pattern 4: Using Vision As A Primary Architecture
**What:** Designing new adapters around screenshots and pixel automation first.
**Why bad:** It is fragile, expensive, and hard to verify.
**Instead:** Prefer native script, CDP, CLI, or file evidence; keep vision as a last-resort fallback plane.

## Scalability Considerations

| Concern | At 5 macOS apps | At 15 macOS apps | At 40+ macOS apps |
|---------|-----------------|------------------|-------------------|
| Profile registration | Manual is tolerable but already risky | Must be registry-driven | Must be schema-validated at import time |
| Control-plane logic | Shared helpers work | Needs executor modules by plane | Needs stronger capability metadata and plane contracts |
| Verification | Per-profile contracts work | Step-level verification needed | Needs reusable assertion library and artifact parsing |
| Evidence volume | Manual inspection possible | Standard artifact bundles required | Needs retention policy and indexing |
| Knowledge reuse | Flat JSON survives | Needs atomic writes and stable keys | Likely needs per-product records and migration support |
| Brownfield maintainability | `live_smoke.py` still manageable | Becomes the bottleneck | Unmaintainable without extraction |

## Suggested Build Order

Build order should reduce coordination risk before adding many more adapters.

1. **Introduce a typed App Profile Registry**
   - Derive CLI smoke choices, metadata, and dispatch from one source.
   - Keep existing profile implementations intact behind the registry first.
   - This removes the current three-file registration drift immediately.

2. **Add stable runtime context and artifact root resolution**
   - Fix `Path.cwd()` dependence for `knowledge/` and `smoke-output/`.
   - Add atomic knowledge writes before parallel or repeated macOS verification expands.

3. **Extract control-plane executors from `live_smoke.py`**
   - Start with macOS-relevant planes: `applescript`, `accessibility`, `cdp`, `shell`.
   - Move subprocess/script-launch details out of app profiles.

4. **Introduce step-based Workflow Runner**
   - Reuse existing `OrchestratorSpec`, `AttemptSpec`, and pivot concepts.
   - Map current read/write/workflow profiles into step graphs without changing result semantics yet.

5. **Standardize StepResult, EvidenceBundle, and blocker taxonomy**
   - Extend the existing contract model rather than replacing it.
   - Ensure every run produces structured evidence suitable for `partial` and `blocked` debugging.

6. **Migrate core macOS apps first**
   - Suggested first set: Finder, Safari, Word for Mac.
   - They cover native script, browser/native hybrid, document write, and workflow verification.

7. **Add extension apps only after core planes are stable**
   - Electron-like apps, weaker Accessibility-only apps, and vision-assisted apps should come after the executor and verification model is proven.

## Brownfield Extension Guidance

For each new macOS application, the implementation checklist should be:

1. Add one `AppProfile` entry.
2. Reuse an existing control-plane executor if possible.
3. Define `read`, `write`, and `workflow` as compositions of shared steps, not separate bespoke runtimes.
4. Declare explicit verification contracts and evidence schema.
5. Add blocker classification for app-specific permission or launch failures.
6. Add one representative real-app smoke and one failure-path smoke.

This is the right structure for a capability-first framework because the planner can continue reasoning at the capability level, while runtime execution becomes modular at the app-profile and control-plane level.

## Sources

- Local project context: `/Users/daizhaorong/OmniControl/.planning/PROJECT.md`
- Codebase architecture map: `/Users/daizhaorong/OmniControl/.planning/codebase/ARCHITECTURE.md`
- Codebase structure map: `/Users/daizhaorong/OmniControl/.planning/codebase/STRUCTURE.md`
- Codebase concerns audit: `/Users/daizhaorong/OmniControl/.planning/codebase/CONCERNS.md`
- Runtime primitives reviewed directly: `omnicontrol/runtime/orchestrator.py`, `omnicontrol/runtime/strategy.py`, `omnicontrol/runtime/transports.py`, `omnicontrol/runtime/contracts.py`, `omnicontrol/runtime/kb.py`, `omnicontrol/cli.py`
