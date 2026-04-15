# Requirements: OmniControl

**Defined:** 2026-04-15
**Core Value:** Real local macOS applications can be automated and verified through a consistent capability-first framework, with evidence-rich results that agent developers can trust.

## v1 Requirements

### Runtime Foundation

- [ ] **RTF-01**: Framework uses a typed app/profile registry as the single source of truth for supported macOS applications, modes, and metadata
- [ ] **RTF-02**: Runtime writes artifacts and state to stable runtime-managed locations instead of depending on the current working directory
- [ ] **RTF-03**: Runtime returns normalized `ok`, `partial`, `blocked`, and `error` outcomes with a shared blocker taxonomy across macOS adapters
- [ ] **RTF-04**: Every macOS run produces a structured evidence bundle that records result metadata and associated artifacts

### macOS Environment & Diagnostics

- [ ] **DIAG-01**: Framework runs layered preflight checks for each macOS app covering install path or bundle resolution, launchability, running state, and transport readiness
- [ ] **DIAG-02**: Framework distinguishes Automation, Accessibility, Screen Recording, and file-access blockers instead of collapsing them into a generic runtime failure
- [ ] **DIAG-03**: Framework reports Apple Events failures as explicit diagnosable blocker types rather than generic adapter failure

### Core Application Coverage

- [ ] **CORE-01**: Framework supports `Finder` as a core macOS app with verified `read`, `write`, and `workflow` coverage
- [ ] **CORE-02**: Framework supports `Safari` as a core macOS app with verified `read`, `write`, and `workflow` coverage
- [ ] **CORE-03**: Framework supports `Microsoft Word` for Mac as a core macOS app with verified `read`, `write`, and `workflow` coverage
- [ ] **CORE-04**: Framework supports `Terminal` or `iTerm2` as a core macOS app family with verified `read`, `write`, and `workflow` coverage
- [ ] **CORE-05**: Each core app declares an explicit support tier and that tier is reflected in runtime output and documentation

### Extension Coverage

- [ ] **EXT-01**: Framework provides extension coverage for `VS Code` with at least verified developer-relevant read and write automation flows
- [ ] **EXT-02**: Framework provides extension coverage for `Notes` or `Reminders` with explicit support tier, clear limitations, and evidence-backed results
- [ ] **EXT-03**: Extension-app requirements define support depth per application instead of forcing one uniform standard across all extension apps

### Verification & Evidence

- [ ] **VER-01**: Each macOS run writes a structured `result.json` report
- [ ] **VER-02**: Each report references concrete artifact paths for evidence instead of relying only on textual status summaries
- [ ] **VER-03**: Workflow mode validates independent postconditions and does not treat command success alone as workflow success
- [ ] **VER-04**: `partial` results explain concrete limitations or blockers instead of reporting an ambiguous failure state

## v2 Requirements

### Additional App Coverage

- **APPS-01**: Framework adds core-quality coverage for Chromium-family browsers on macOS
- **APPS-02**: Framework expands Office for Mac support beyond Word to apps such as Excel and PowerPoint
- **APPS-03**: Framework broadens extension coverage to more developer and productivity apps after the core macOS runtime stabilizes

### Packaging & Runtime Identity

- **PKG-01**: Framework ships a stable signed macOS helper app or automation principal for stronger TCC identity handling
- **PKG-02**: Framework formalizes persistent host-specific launch hints and transport learning beyond the current JSON-first knowledge reuse

## Out of Scope

| Feature | Reason |
|---------|--------|
| Claiming support for all common macOS applications | v1 is focused on practical representative coverage, not exhaustive desktop support |
| Making Chromium browsers a v1 core requirement | v1 core batch is intentionally centered on Finder, Safari, Word, and Terminal/iTerm2 |
| Using vision-click or coordinate automation as the default primary strategy | v1 should prefer stronger control planes and keep weak surfaces as fallback or later work |
| Packaging the framework as a consumer-facing automation product | v1 is aimed at AI agent developers and advanced operators, not general end users |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RTF-01 | Phase TBD | Pending |
| RTF-02 | Phase TBD | Pending |
| RTF-03 | Phase TBD | Pending |
| RTF-04 | Phase TBD | Pending |
| DIAG-01 | Phase TBD | Pending |
| DIAG-02 | Phase TBD | Pending |
| DIAG-03 | Phase TBD | Pending |
| CORE-01 | Phase TBD | Pending |
| CORE-02 | Phase TBD | Pending |
| CORE-03 | Phase TBD | Pending |
| CORE-04 | Phase TBD | Pending |
| CORE-05 | Phase TBD | Pending |
| EXT-01 | Phase TBD | Pending |
| EXT-02 | Phase TBD | Pending |
| EXT-03 | Phase TBD | Pending |
| VER-01 | Phase TBD | Pending |
| VER-02 | Phase TBD | Pending |
| VER-03 | Phase TBD | Pending |
| VER-04 | Phase TBD | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 0
- Unmapped: 19 ⚠️

---
*Requirements defined: 2026-04-15*
*Last updated: 2026-04-15 after initial definition*
