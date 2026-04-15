# Project Research Summary

**Project:** OmniControl
**Domain:** macOS local automation framework for AI agent developers
**Researched:** 2026-04-15
**Confidence:** HIGH

## Executive Summary

OmniControl is not a generic desktop click-bot. The research consistently points to a capability-first macOS automation runtime that preserves the existing Python orchestration model while formalizing multiple control planes: AppleScript for scriptable apps, Playwright/CDP for Chromium-class browser work, PyObjC for native launchability and OS APIs, and Accessibility only as a fallback when stronger surfaces do not exist. Experts build this kind of product by separating planning, app profiles, control-plane execution, verification, and evidence instead of letting one global smoke runner absorb all app-specific logic.

The recommended direction is to harden the runtime before broadening app count. Keep CPython as the control plane, add PyObjC-backed macOS execution boundaries, introduce a stable app/profile registry and evidence model, then prove a small first wave of core macOS apps across distinct control planes: Finder, Safari, Chromium, Word, and Terminal/iTerm. That set is enough to establish practical utility for agent developers without overclaiming universal desktop support.

The main risks are false support claims caused by weak launch handling, collapsed permission diagnostics, shallow single-step demos, and evidence that cannot explain failures. Mitigation is straightforward and should shape the roadmap: build staged preflight checks, normalize blocker taxonomy, require workflow-level verification with independent postconditions, and ship explicit support tiers (`core`, `extension`, `experimental`) instead of pretending every adapter is production-ready.

## Key Findings

### Recommended Stack

The stack recommendation is stable: keep the existing Python CLI/orchestrator, move macOS-sensitive operations behind PyObjC-backed runtime boundaries, use AppleScript where apps are actually scriptable, and standardize browser automation on Playwright Python. A signed helper app is a strong follow-on recommendation for stable TCC identity, but the immediate roadmap can start by introducing typed runtime boundaries and permission-aware preflight inside the current Python-led system.

**Core technologies:**
- `CPython 3.12.x` with `>=3.10` compatibility during migration: keeps the brownfield runtime intact while aligning with current dependency support.
- `PyObjC 12.1` (`Cocoa`, `ApplicationServices`, `Quartz`, optional `ScriptingBridge`): native launch, window/process inspection, Accessibility, screenshots, and macOS API access without a Swift rewrite.
- `Playwright Python 1.58.0`: primary browser plane for Chromium-class workflows and evidence-rich traces.
- `AppleScript`: first-choice adapter language for Finder, Safari app-level actions, and Office where scriptability exists.
- `psutil 7.2.2`: process discovery and cleanup support that complements AppKit-level launch handling.

### Expected Features

The table stakes are not broad app count. They are credible multi-plane automation, explicit environment diagnostics, read/write/workflow depth, and evidence operators can trust. Differentiation comes from capability-first planning, root-cause classification, honest partial support, and evidence bundles that make failures diagnosable.

**Must have (table stakes):**
- Multi-plane app control across native script, Accessibility, browser protocol, and file/CLI verification.
- App preflight and capability checks for install path, launchability, process identity, and transport readiness.
- Explicit TCC and permission diagnostics for Automation, Accessibility, Screen Recording, and file access blockers.
- Read, write, and multi-step workflow profiles for each core app family.
- Evidence-rich outcomes with structured results, artifacts, and normalized `ok/partial/blocked/error` grading.

**Should have (competitive):**
- Capability-first planning with ranked primary and fallback planes.
- Root-cause classification plus remediation guidance for macOS-specific blockers.
- First-class evidence bundles per run, including transport, environment, and postcondition artifacts.
- Support tiers and degraded-but-honest sidecar/fallback behavior within an app family.
- Learned local knowledge for launch hints, winning transports, and recurring host-specific blockers.

**Defer (v2+):**
- Broad extension-app coverage beyond the first representative batch.
- Deep VS Code editing flows and wider Electron/productivity coverage before core planes stabilize.
- System Settings mutation workflows; keep v1 focused on diagnostics and state-reading.
- Vision-first or coordinate-clicking strategies except as isolated fallback experiments.

### First-Wave App Coverage

Wave 1 should prove a balanced set of app classes rather than maximize names. The strongest first batch is Finder, Safari, Chrome/Chromium, Microsoft Word, and Terminal or iTerm2. This covers Apple Events, browser protocol, file verification, developer workflow relevance, and workflow-level mutation/persistence checks. VS Code and Notes/Reminders fit as extension apps after the core evidence and control-plane model is stable.

### Architecture Approach

The architecture work should extract the current monolithic smoke runtime into explicit layers: capability detection and planning, an app profile registry, a step-based workflow runner, reusable control-plane executors, a verification and evidence pipeline, and a knowledge store rooted in stable project/user config rather than `cwd`. The core rule is that app adapters describe intent and contracts, while executors perform operations and the verification layer decides whether the result is actually trustworthy.

**Major components:**
1. `App Profile Registry` — single source of truth for supported apps, modes, control planes, preflight checks, and evidence schemas.
2. `Workflow Runner` — composes `launch/read/write/verify/pivot/artifact` steps into read, write, and workflow modes.
3. `Control-Plane Executors` — reusable adapters for AppleScript, Accessibility, CDP, shell/CLI, and file/document verification.
4. `Verification + Evidence Pipeline` — separates execution success from verification success and emits stable evidence bundles.
5. `Knowledge Store / Runtime Context` — remembers launch hints, winning transports, blocker fingerprints, and avoids `Path.cwd()`-scoped state.

### Critical Pitfalls

1. **Launch brittleness disguised as adapter failure** — use bundle-ID and app-URL resolution, distinguish launch checkpoints, and test closed/open/non-default installs.
2. **Permission checks treated as a single boolean** — model Automation, Accessibility, Screen Recording, and controlling-process identity as separate blocker classes with live preflight.
3. **Apple Events failures collapsed together** — separate permission denial, missing scriptability, unsupported commands, and adapter defects.
4. **Browser support overfit to one happy-path transport** — split Chromium launch, Chromium attach, and Safari strategies, and keep attach-mode confidence lower.
5. **Single-step demos mislabeled as practical support** — require persisted read/write/workflow proofs with independent verification artifacts.
6. **Weak evidence and inconsistent status semantics** — standardize evidence bundles and normalized blocker taxonomy before expanding adapter count.

## Implications for Roadmap

Based on the research, the roadmap should optimize for runtime credibility first, then representative app proof, then extension coverage.

### Phase 1: Runtime Foundation and Registry Extraction
**Rationale:** The current bottleneck is architecture drift inside the global smoke runtime, not lack of app ideas.
**Delivers:** Typed app profile registry, stable runtime/artifact roots, normalized result model, early blocker taxonomy, and initial executor boundaries.
**Addresses:** Multi-plane control, honest grading, stable operator workflows, extensibility for new macOS apps.
**Avoids:** Registration drift, `cwd`-scoped state, weak evidence, and hidden launch/permission failure modes.

### Phase 2: Permissions, Launch, and Preflight Hardening
**Rationale:** macOS usability fails on startup and TCC state before it fails on app-specific adapter logic.
**Delivers:** Layered launch resolution, staged preflight checks, app identity reporting, and explicit diagnostics for Automation, Accessibility, Screen Recording, and app scriptability.
**Addresses:** App preflight, capability verification, remediation workflows, and blocker classification.
**Avoids:** False negatives, “works only on one machine” behavior, and permission-related support confusion.

### Phase 3: Core Control Planes and Evidence Pipeline
**Rationale:** Before shipping many adapters, OmniControl needs reusable execution surfaces and comparable artifacts across planes.
**Delivers:** Reusable AppleScript, Accessibility, CDP, shell, and file/document executors; step-based workflow runner; per-run evidence bundles.
**Uses:** PyObjC, AppleScript, Playwright Python, existing contract/orchestrator primitives.
**Implements:** Executor abstraction, step taxonomy, verification/evidence separation.

### Phase 4: Core App Wave 1
**Rationale:** The first meaningful product proof is a small balanced set of real apps with read/write/workflow depth.
**Delivers:** Finder, Safari, Chrome/Chromium, Word, and Terminal/iTerm profiles with independent postcondition verification and support-tier labeling.
**Addresses:** Balanced first-wave coverage across file management, browser, office/productivity, and developer workflows.
**Avoids:** Broad but shallow app claims and read-only demo inflation.

### Phase 5: Extension Coverage and Knowledge Reuse
**Rationale:** Extension apps only make sense once core planes and evidence semantics are proven.
**Delivers:** VS Code and lightweight productivity app coverage, host-specific launch/transport learning, richer remediation guidance, and selective fallback expansion.
**Addresses:** Differentiators such as learned local knowledge, support tiers, and degraded-but-honest fallback.
**Avoids:** Premature scaling of brittle adapters and silent fallback behavior.

### Phase Ordering Rationale

- Registry and runtime context come first because every later app and control plane depends on one source of truth and stable artifact roots.
- Permissions and launch hardening precede broad app work because macOS environment blockers would otherwise contaminate adapter validation.
- Executor and evidence standardization should happen before multiple new adapters so results stay comparable and roadmap decisions are based on clean data.
- Core app coverage should prove one representative app per important control-plane family before extension apps are considered.
- Extension coverage belongs last because it depends on proven blocker taxonomy, reusable executors, and honest support-tier semantics.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Packaging identity and stable helper-app direction if the roadmap wants to formalize a signed `OmniControl Agent.app` early.
- **Phase 4:** App-specific Safari and Word workflow details, especially around scriptability limits, document export, and permission prompts on current macOS builds.
- **Phase 5:** VS Code and Electron-family extension patterns, since mixed CLI plus Accessibility behavior is more variable than the core app set.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Registry extraction and stable artifact-root work are well-supported by existing codebase research.
- **Phase 3:** Executor boundaries, step-based workflows, and evidence normalization are already strongly implied by current runtime architecture and research outputs.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official-platform and package sources align on Python + PyObjC + Playwright as the pragmatic macOS direction. |
| Features | MEDIUM-HIGH | Strong project-fit and good platform grounding, with some differentiation recommendations based on synthesis rather than single-source proof. |
| Architecture | HIGH | Well-supported by direct codebase analysis and the existing capability-first runtime shape. |
| Pitfalls | HIGH | Risks are consistent across platform docs, codebase concerns, and the realities of macOS automation. |

**Overall confidence:** HIGH

### Gaps to Address

- Stable helper-app packaging should be validated during planning if the team wants TCC identity stability in the first milestone rather than later.
- Office automation depth beyond Word remains unresolved; Excel and PowerPoint should not be implied by a generic “Office” abstraction.
- Safari should be treated as a narrower browser target than Chromium until concrete workflow coverage is proven on the target macOS version.
- Support-tier criteria need to be formalized in roadmap language so `partial` means the same thing across adapters.

## Sources

### Primary (HIGH confidence)
- [.planning/research/STACK.md](/Users/daizhaorong/OmniControl/.planning/research/STACK.md)
- [.planning/research/FEATURES.md](/Users/daizhaorong/OmniControl/.planning/research/FEATURES.md)
- [.planning/research/ARCHITECTURE.md](/Users/daizhaorong/OmniControl/.planning/research/ARCHITECTURE.md)
- [.planning/research/PITFALLS.md](/Users/daizhaorong/OmniControl/.planning/research/PITFALLS.md)
- [.planning/PROJECT.md](/Users/daizhaorong/OmniControl/.planning/PROJECT.md)
- Apple Support and Apple Developer documentation referenced throughout the research for Automation, Accessibility, launch behavior, and PPPC/TCC constraints.
- PyObjC official docs and PyPI release data for supported Python versions, ApplicationServices, Quartz, ScriptingBridge, and signing considerations.
- Playwright official docs and PyPI release data for Python runtime fit, CDP attach limitations, and trace-based evidence.

### Secondary (MEDIUM confidence)
- Microsoft Learn sources for Office for Mac automation and update behavior.
- Chrome and WebKit documentation used to distinguish Chromium attach flows from Safari/WebKit automation semantics.

---
*Research completed: 2026-04-15*
*Ready for roadmap: yes*
