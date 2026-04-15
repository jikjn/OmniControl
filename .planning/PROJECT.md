# OmniControl

## What This Is

OmniControl is a capability-first local software automation framework for AI agent developers and advanced operators. It detects control planes, plans adapters, scaffolds automation harnesses, and runs real smoke and workflow verification against installed applications. The current focus is turning the existing prototype into a practically usable macOS automation framework with representative real-world application coverage.

## Core Value

Real local macOS applications can be automated and verified through a consistent capability-first framework, with evidence-rich results that agent developers can trust.

## Requirements

### Validated

- ✓ Capability-first detection, planning, and scaffold generation already exist in the CLI and core domain model — existing brownfield baseline
- ✓ Runtime smoke orchestration, contract evaluation, fallback/pivot logic, and evidence recording already exist — existing brownfield baseline
- ✓ Initial platform-specific automation surfaces already exist for Windows-heavy runtime coverage and limited macOS AppleScript coverage — existing brownfield baseline

### Active

- [ ] Prove OmniControl is practically usable on macOS across real common applications, not just synthetic smoke demos
- [ ] Establish a balanced first wave of macOS adapter coverage across file management, browser, office/productivity, and developer workflow applications
- [ ] Validate representative read, write, and multi-step workflow chains on macOS, with core applications held to a high-confidence standard and extension applications allowed to land as partial support
- [ ] Improve runtime verification so macOS results clearly distinguish app-launch limitations, automation permission issues, transport gaps, and real adapter failures
- [ ] Expand the framework so new macOS applications can be added through the existing capability-first architecture rather than one-off scripts

### Out of Scope

- Broad end-user product polish or non-technical onboarding UX — v1 is aimed at AI agent developers and advanced operators first
- Perfect, hard-guaranteed support for every macOS desktop application — v1 will prioritize representative coverage and layered validation over exhaustive support
- Major new platform expansion beyond the current macOS push — Windows support exists, but this initialization is focused on making macOS practically usable
- General consumer automation product packaging or hosted service delivery — the project remains a local operator/developer framework

## Context

This is a brownfield project with an existing capability-first architecture already mapped in `.planning/codebase/`. The codebase is a Python 3.10+ CLI with runtime orchestration, smoke contracts, adaptive startup logic, sidecar pivots, knowledge-base reuse, and platform-specific helper scripts. Current runtime coverage is strongest on Windows, while macOS support exists but is still limited and has not yet been proven at a practical, real-application level.

The immediate product direction is to make macOS support real enough for day-to-day agent development use. That means not merely adding a few isolated demos, but proving the framework on a balanced set of applications that collectively exercise multiple control planes and multiple workflow styles. The first batch should be chosen for representativeness: enough to demonstrate file operations, browser interactions, office/productivity tasks, and developer workflow actions through the same framework.

The intended v1 primary user is the AI agent developer who needs a reliable local software control substrate. The project should still remain useful to the author directly and extensible for future third-party adapter authors, but those are secondary to proving the framework as a practical automation base for agent systems.

## Constraints

- **Existing Architecture**: Build on the current capability-first detector/planner/runtime design — preserve the framework identity instead of replacing it with app-specific one-offs
- **Platform Focus**: macOS is the current priority — first-phase work should increase practical macOS usability before pursuing additional broad platform ambitions
- **Verification Standard**: v1 uses layered acceptance — core macOS apps should be few-but-hard, while extension apps may ship with `partial` outcomes if evidence and limitations are explicit
- **Target User**: Design decisions should favor AI agent developers and advanced operators — clarity of runtime evidence and debuggability matter more than consumer-facing polish
- **Execution Environment**: Real macOS automation depends on a live graphical session, app launchability, and OS automation permissions — plans must account for these as first-class runtime constraints
- **Coverage Scope**: The first macOS batch should be balanced across application domains and workflow types — avoid overfitting to a single app family or a single transport

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Prioritize macOS practical usability as the next major project direction | The existing framework already has brownfield foundations, but macOS has not yet been proven as a real operator-grade target | — Pending |
| Define v1 success as practical coverage of real common applications, not just smoke demos | The goal is real agent usefulness on macOS, which requires representative real-world validation | — Pending |
| Use a balanced first batch of macOS applications | The framework should prove multiple control planes and app classes, not only one narrow family of apps | — Pending |
| Validate read, write, and multi-step workflow paths | Practical usability depends on proving all three behavior classes, not just observation or launch checks | — Pending |
| Adopt layered acceptance: core apps hard, extension apps may be partial | This gives v1 enough rigor to be credible without blocking progress on exhaustive support | — Pending |
| Treat AI agent developers as the primary v1 user | This best matches the current codebase shape and clarifies tradeoffs around evidence, diagnostics, and adapter design | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check -> still the right priority?
3. Audit Out of Scope -> reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-15 after initialization*
