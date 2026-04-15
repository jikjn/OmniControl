# Feature Landscape

**Domain:** macOS local automation framework for AI agent developers
**Researched:** 2026-04-15
**Overall confidence:** MEDIUM-HIGH

## Executive Framing

For this project, "practically useful" does not mean broad but shallow app support. It means a small set of macOS applications can be detected, launched, driven, verified, and diagnosed through repeatable control planes with evidence an agent developer can trust.

The feature boundary is therefore not just "can click buttons". Table stakes are: multi-plane app control, preflight capability checks, explicit permission diagnosis, read/write/workflow verification, and evidence-rich outcomes. Differentiation comes from making those planes composable, grading support honestly, and helping operators recover from macOS-specific blockers without resorting to opaque one-off scripts.

The first macOS wave should exercise four distinct control planes:
- Apple Events / AppleScript for scriptable native and Office-style apps
- Accessibility/UI scripting for broad desktop coverage and unscripted apps
- CDP/browser-native automation for Chromium-class browsers
- File/CLI sidecars for verification, export, and recovery

That mix is more important than maximizing app count. A framework that proves six apps across four control planes is more useful than one that claims fifteen apps through brittle coordinate clicking.

## Table Stakes

Features users expect. Missing these means the framework is not credible for day-to-day agent development.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-plane app control (`native script`, `accessibility`, `browser protocol`, `file/CLI`) | macOS apps expose uneven automation surfaces; no single plane covers Finder, Safari, Chrome, Office, and dev tools reliably | High | Apple’s UI scripting guidance exists because many apps are only partially scriptable; OmniControl already has the right capability-first shape for this |
| App preflight and capability verification | Operators need to know whether failure is caused by app absence, wrong bundle/path, disabled automation permission, unreachable control plane, or real adapter bugs | Medium | Must check install path, launchability, bundle/process identity, permission state symptoms, and light probe success before deep workflows |
| Explicit TCC / permission diagnostics | macOS Automation, Accessibility, and Screen Recording permissions are first-class runtime constraints, not incidental errors | Medium | Distinguish `blocked: automation denied` from `blocked: app not scriptable` from `blocked: screen recording missing` |
| Read, write, and multi-step workflow profiles per app family | Read-only demos are insufficient; agent developers need proof that observation, mutation, and chained actions all work | High | The repo already trends this way with `open -> write -> workflow` profile ladders |
| Evidence-rich execution artifacts | A pass/fail bit is not enough; users need screenshots, structured outputs, captured values, generated files, and report JSON for debugging and trust | Medium | Browser ecosystems like Playwright normalized trace/screenshot evidence; desktop automation needs the same discipline |
| Honest outcome grading (`ok`, `partial`, `blocked`, `error`) | Desktop automation is variable; practical systems expose support quality instead of pretending every fallback is success | Medium | Existing runtime architecture already supports this and should stay central |
| Stable operator workflows | AI developers need a loop: detect, plan, smoke, inspect evidence, remediate, rerun | Medium | CLI flow matters more than consumer UX; output must be automatable and readable |
| Balanced core app coverage | A usable framework must prove representative classes: file manager, native browser, Chromium browser, document app, and developer workflow app | High | This is the minimum credible surface for local agent work on macOS |

## Differentiators

Features that materially separate OmniControl from ad hoc AppleScript wrappers or screenshot bots.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Capability-first planning with ranked primary and fallback planes | Lets agents target app families instead of hardcoded scripts and preserves framework coherence as coverage expands | High | This is already a repo strength; it should remain the product identity |
| Verified sidecar degradation inside an app family | Converts hard failure into honest `partial` by proving a lighter sibling plane still works | Medium | Example shape already exists in repo docs: `write -> read/open` pivots with original blocker preserved |
| First-class evidence bundles per run | Makes the framework usable for automated evaluation, regression testing, and post-mortem debugging | Medium | Bundle should include structured payload, control plane used, preflight results, artifacts, and remediation hints |
| Root-cause classifier for macOS blockers | Saves operator time by identifying likely causes such as TCC denial, Apple Event consent missing, app launch policy, unsupported dictionary operation, or DOM target mismatch | High | This is more valuable than adding more retries |
| Support tiers per app/action | Enables a few core apps to be held to high-confidence standards while extension apps ship as partial or read-only | Low | Essential for roadmap realism and brownfield progress |
| Control-plane introspection snapshots | Accessibility tree snapshots, Safari/DOM state, file hashes, and generated-document inspection make results inspectable by both humans and agents | Medium | Strong differentiator versus coordinate-clicking systems |
| Operator remediation workflows | Framework tells users what to do next: grant Automation, enable Accessibility, open once manually, supply bundle path, or switch profile | Medium | High leverage because macOS failures are often environmental, not code defects |
| Learned local knowledge per host/app | Remembers winning launch paths, transport order, and known blockers on a workstation | Medium | Repo already has KB support; this is a real advantage for repeated local use |

## Application Coverage Patterns

Coverage should be organized by app family and control-plane depth, not as a flat checklist of app names.

### Pattern 1: Native-scriptable core apps

Use for apps with strong Apple Event / AppleScript surfaces.

| App Class | Example Apps | Why It Matters | Complexity | Recommended Depth |
|-----------|--------------|----------------|------------|-------------------|
| File manager | Finder | Exercises app launch, navigation, selection, and filesystem-affecting workflows on a core macOS app | Medium | `open/read`, `navigation workflow`, selected-item verification |
| Native browser | Safari | Proves Apple-native browser control, page open, limited DOM interaction, and app/browser split logic | Medium | `open/read`, `DOM write`, title/URL/value verification |
| Document editor | Microsoft Word | Proves real write/export workflows and file-artifact verification | High | `write`, `export`, `workflow` with post-run file validation |

### Pattern 2: Accessibility-first desktop apps

Use for apps that are unscripted or only partially scriptable.

| App Class | Example Apps | Why It Matters | Complexity | Recommended Depth |
|-----------|--------------|----------------|------------|-------------------|
| Generic productivity UI | Notes, Slack, Electron utilities | Broadens practical app reach beyond dictionary-driven apps | High | start with `open/read` and one small mutation path |
| Developer tools UI | VS Code, Xcode, JetBrains IDEs | Important for AI agent developers; many flows require UI discovery and menu/keyboard control | High | `open workspace`, `find/open file`, simple edit verification |
| Settings / system surfaces | System Settings panels | Necessary for permission setup and diagnostics | Medium | navigation and state-reading only; avoid broad mutation promises in v1 |

### Pattern 3: Browser-native protocol apps

Use when the browser exposes a better automation plane than macOS UI automation.

| App Class | Example Apps | Why It Matters | Complexity | Recommended Depth |
|-----------|--------------|----------------|------------|-------------------|
| Chromium browsers | Chrome, Chromium, Edge | CDP is higher-fidelity than Accessibility for browser workflows and agent evals | Medium | `open/read`, form write, workflow with DOM-based assertions |
| Browser-hosted tools | internal tools, local dashboards, auth portals | Real agent work often terminates in the browser even when launched from desktop apps | Medium | validate page state via DOM, not screenshots alone |

### Pattern 4: CLI and sidecar-verifiable apps

Use when the safest proof of success is outside the UI plane.

| App Class | Example Apps | Why It Matters | Complexity | Recommended Depth |
|-----------|--------------|----------------|------------|-------------------|
| Terminal apps | Terminal, iTerm2 | Critical for developer workflows and a bridge between desktop and command execution | Medium | open session, run command, verify output artifact |
| File-producing workflows | Office export, downloaded files, generated docs | Gives strong postcondition checks independent of fragile UI state | Low | hash, magic bytes, XML/text markers, existence/mtime checks |

## Balanced First macOS Application Batch

This batch is the right first-wave target because it covers multiple control planes and the actual workflows AI agent developers care about.

| App | Primary Control Plane | Secondary / Verification Plane | Why It Should Be In Wave 1 | Complexity | Tier |
|-----|------------------------|-------------------------------|-----------------------------|------------|------|
| Finder | AppleScript + Accessibility | Filesystem verification | Baseline desktop/file workflow app; proves core macOS navigation and selection | Medium | Core |
| Safari | AppleScript / JavaScript in page | Screenshot + DOM/value verification | Native browser coverage and Apple Events permission path | Medium | Core |
| Chrome or Chromium | CDP | Screenshot + file/download verification | Best high-confidence browser plane for agent workflows | Medium | Core |
| Microsoft Word | AppleScript | DOCX/PDF artifact inspection | Strong write/export/workflow proof with objective output checks | High | Core |
| Terminal or iTerm2 | AppleScript / app-native automation | CLI stdout/file verification | Directly useful to AI developers and bridges desktop plus command workflows | Medium | Core |
| VS Code | CLI + Accessibility | Filesystem verification | High-value developer app; proves mixed control-plane operation on a real tool agents use | High | Extension |
| Notes or Reminders | Apple-native automation / Shortcuts where available, else Accessibility | Content readback | Tests lightweight productivity capture flows without overcommitting to heavy office semantics | Medium | Extension |

### Why this batch is balanced

- `Finder` proves OS-native desktop/file workflows.
- `Safari` proves Apple-native browser automation.
- `Chrome/Chromium` proves browser-protocol automation.
- `Word` proves rich document mutation plus artifact-based verification.
- `Terminal/iTerm2` proves developer workflow relevance.
- `VS Code` proves mixed app-family coverage for agent builders.
- `Notes/Reminders` proves lightweight productivity capture beyond browser/file cases.

### Coverage rule for Wave 1

Ship each core app with at least:
- one `read/open` profile
- one `write/mutate` profile where reasonable
- one multi-step `workflow` profile
- one postcondition verification path independent of the UI action itself

That produces fewer but materially better app integrations.

## Table Stakes vs Differentiating by Area

| Area | Table Stakes | Differentiating |
|------|--------------|-----------------|
| App coverage | Finder, Safari, Chromium browser, document app, terminal-class app | Mixed support tiers with developer-centric extensions like VS Code |
| Capability verification | Install checks, launch checks, bundle/process identity, minimal control-plane probe | Capability manifests with ranked fallback planes and reusable family metadata |
| Evidence | Structured result JSON, screenshots where useful, output file verification | Evidence bundles with control-plane snapshots, before/after state, and replayable diagnostics |
| Diagnostics | Explicit `blocked` reasons and remediation hints | Root-cause classification plus preserved primary blocker when a lighter plane succeeds |
| Operator workflow | Detect -> plan -> smoke -> inspect -> rerun | Learned workstation-specific knowledge and guided remediation/replay |

## Anti-Features / Explicit Non-Goals

Features to explicitly avoid in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Broad coordinate-based clicking as the primary automation strategy | Fragile across resolutions, themes, window positions, and localization; produces weak evidence | Use Accessibility, AppleScript, CDP, or file verification first; reserve coordinates for last-resort experiments only |
| Claiming universal macOS app support | Not credible for v1 and encourages shallow adapters | Publish explicit support tiers and action-level capability depth |
| Building consumer-grade no-code UX now | Misaligned with the stated user: AI agent developers and advanced operators | Keep the CLI and report artifacts strong and scriptable |
| Hiding environmental blockers behind retries | Makes failures opaque and slows operators down | Surface permission, launch, and control-plane blockers explicitly |
| Shipping many read-only demos with no mutation proof | Does not establish practical usefulness | Require write/workflow depth for core apps |
| Treating shell execution as equivalent to app automation | Avoids the hard problem and leaves desktop app coverage unproven | Use Terminal coverage as one app family, not as a substitute for GUI automation |
| Overcommitting to unsupported system mutation flows | macOS permission and safety boundaries make some settings flows risky and unstable | Prefer diagnostics and guided remediation for system settings in v1 |

## Feature Dependencies

```text
Capability detection -> preflight verification -> app family profile selection
Preflight verification -> blocker classification -> remediation guidance
App family profile selection -> read/open profile -> write profile -> workflow profile
Accessibility support -> permission diagnostics -> accessibility tree / UI verification
Apple Events support -> Automation permission handling -> native-script workflows
Browser protocol support -> DOM assertions -> workflow evidence
Write/workflow profiles -> artifact verification -> high-confidence `ok`
Sidecar/fallback planning -> honest `partial` outcomes -> broader practical coverage
Evidence bundles -> operator debugging -> repeatable agent evaluation
Knowledge base reuse -> faster reruns -> workstation-specific reliability
```

## MVP Recommendation

Prioritize:
1. Finder family: `open/read` plus navigation verification
2. Safari family: `open/read` and one DOM write workflow
3. Chrome/Chromium family: CDP observe, form write, workflow
4. Word family: write/export/workflow with file-level verification
5. Terminal family: open session, run command, verify output artifact

Defer:
- VS Code deep editing workflows: valuable, but should follow once the core evidence/diagnostic model is solid
- Broad Notes/Slack/Electron coverage: useful extension surface, but should not preempt hardening the core families
- System Settings mutation workflows: diagnostic and permission-read flows first, mutation later if justified

## Sources

- `/Users/daizhaorong/OmniControl/.planning/PROJECT.md` - project requirements and scope grounding. Confidence: HIGH
- `/Users/daizhaorong/OmniControl/.planning/codebase/STACK.md` - existing runtime/tooling surfaces. Confidence: HIGH
- `/Users/daizhaorong/OmniControl/.planning/codebase/ARCHITECTURE.md` - capability-first/runtime architecture constraints. Confidence: HIGH
- `/Users/daizhaorong/OmniControl/docs/SIDECAR_CONTROL_PLANE_UPDATE.md` - existing sidecar/fallback product direction. Confidence: HIGH
- `/Users/daizhaorong/OmniControl/benchmarks/local_closed_source_macos.json` - current macOS benchmark coverage. Confidence: HIGH
- Apple, "Mac Automation Scripting Guide: Automating the User Interface" - confirms GUI scripting is necessary when app scripting is incomplete and depends on Accessibility authorization. https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AutomatetheUserInterface.html . Confidence: HIGH
- Apple Support, "Allow apps to automate and control other apps" - confirms Automation permission is a first-class runtime gate in macOS Privacy & Security. https://support.apple.com/guide/mac-help/mchl108e1718/mac . Confidence: HIGH
- Apple, "Accelerating app interactions with App Intents" - shows Apple’s current direction for exposing app actions through system surfaces like Shortcuts and Siri. https://developer.apple.com/documentation/appintents/acceleratingappinteractionswithappintents . Confidence: MEDIUM
- Apple, "Capturing screen content in macOS" - confirms Screen Recording permission is part of evidence/screenshot capture on modern macOS. https://developer.apple.com/documentation/ScreenCaptureKit/capturing-screen-content-in-macos . Confidence: HIGH
- Playwright docs, "Visual comparisons" - representative evidence that modern automation frameworks are expected to emit screenshots and comparable artifacts, though browser-specific. https://playwright.dev/docs/test-snapshots . Confidence: MEDIUM
