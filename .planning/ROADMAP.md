# Roadmap: OmniControl

## Overview

This roadmap turns OmniControl's existing capability-first prototype into a practical macOS automation framework by hardening runtime foundations first, then proving representative core applications, and only then expanding into extension coverage with explicit support tiers and evidence-backed results.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Runtime Registry & Evidence Foundation** - Establish the shared registry, runtime roots, and evidence model every macOS run depends on.
- [ ] **Phase 2: macOS Diagnostics & Outcome Taxonomy** - Make macOS failures diagnosable before expanding application claims.
- [ ] **Phase 3: Finder & Safari Core Coverage** - Prove file-management and native browser workflows at core-app quality.
- [ ] **Phase 4: Word & Terminal Core Coverage** - Prove office and developer-workflow core coverage with explicit support tiers.
- [ ] **Phase 5: Extension Coverage & Graduated Support** - Add extension apps with honest depth limits and evidence-backed partial support.

## Phase Details

### Phase 1: Runtime Registry & Evidence Foundation
**Goal**: Users can run OmniControl against macOS apps through one typed registry with stable runtime state and evidence-rich result artifacts.
**Depends on**: Nothing (first phase)
**Requirements**: RTF-01, RTF-02, RTF-04, VER-01, VER-02
**Success Criteria** (what must be TRUE):
  1. User can target supported macOS apps through one registry-backed source of truth instead of scattered app-specific configuration.
  2. User can run OmniControl from any working directory and still find runtime state and artifacts in stable framework-managed locations.
  3. User receives a structured `result.json` for each run with linked artifact paths instead of a status-only summary.
**Plans**: TBD

### Phase 2: macOS Diagnostics & Outcome Taxonomy
**Goal**: Users can distinguish macOS environment blockers from real adapter failures through consistent preflight and normalized outcomes.
**Depends on**: Phase 1
**Requirements**: RTF-03, DIAG-01, DIAG-02, DIAG-03, VER-04
**Success Criteria** (what must be TRUE):
  1. User can see preflight results for app resolution, launchability, running state, and transport readiness before adapter execution proceeds.
  2. User can tell whether a failed run was blocked by Automation, Accessibility, Screen Recording, or file-access permissions without reading raw logs.
  3. User can see Apple Events failures classified as diagnosable blocker types rather than generic adapter errors.
  4. User can distinguish `partial`, `blocked`, and `error` outcomes because each one explains the concrete limitation or blocker.
**Plans**: TBD

### Phase 3: Finder & Safari Core Coverage
**Goal**: Users can rely on OmniControl for high-confidence Finder and Safari read, write, and workflow automation on macOS.
**Depends on**: Phase 2
**Requirements**: CORE-01, CORE-02, VER-03
**Success Criteria** (what must be TRUE):
  1. User can automate Finder read, write, and multi-step workflow scenarios with independent postcondition checks proving the file-system outcome.
  2. User can automate Safari read, write, and multi-step workflow scenarios with verification that checks browser state or produced artifacts rather than command success alone.
  3. User can trust workflow-mode success for these core apps because OmniControl validates observable postconditions after execution.
**Plans**: TBD

### Phase 4: Word & Terminal Core Coverage
**Goal**: Users can use OmniControl on macOS for core office and terminal workflows with explicit support-tier semantics.
**Depends on**: Phase 3
**Requirements**: CORE-03, CORE-04, CORE-05
**Success Criteria** (what must be TRUE):
  1. User can automate Microsoft Word read, write, and workflow scenarios with evidence showing the document outcome.
  2. User can automate Terminal or iTerm2 read, write, and workflow scenarios with verification tied to shell or file-system postconditions.
  3. User can see each core app's support tier in runtime output and documentation before relying on it in agent workflows.
**Plans**: TBD

### Phase 5: Extension Coverage & Graduated Support
**Goal**: Users can expand beyond the core macOS app set through extension adapters that declare honest depth, limits, and evidence-backed results.
**Depends on**: Phase 4
**Requirements**: EXT-01, EXT-02, EXT-03
**Success Criteria** (what must be TRUE):
  1. User can run verified developer-relevant read and write flows against VS Code as an extension app.
  2. User can use Notes or Reminders with a declared support tier, clear limitations, and evidence-backed results instead of implicit best-effort claims.
  3. User can tell how deep each extension app goes because support depth is declared per application rather than assumed to match the core-app standard.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Runtime Registry & Evidence Foundation | 0/TBD | Not started | - |
| 2. macOS Diagnostics & Outcome Taxonomy | 0/TBD | Not started | - |
| 3. Finder & Safari Core Coverage | 0/TBD | Not started | - |
| 4. Word & Terminal Core Coverage | 0/TBD | Not started | - |
| 5. Extension Coverage & Graduated Support | 0/TBD | Not started | - |
