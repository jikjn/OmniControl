# Domain Pitfalls

**Domain:** Brownfield macOS local automation framework
**Researched:** 2026-04-15

## Critical Pitfalls

Mistakes here usually cause false claims of support, unusable real-world coverage, or expensive rewrites.

### Pitfall 1: Treating app launch as a solved problem
**What goes wrong:** The framework assumes an app is launchable by one hard-coded path or by process name, then interprets launch failure as an adapter bug.
**Why it happens:** Demo flows usually target one local machine. Real macOS installs vary across App Store builds, direct `.app` bundles, renamed apps, existing running instances, and apps that take time to surface a usable window after launch.
**Consequences:** High false-negative rates, attach-to-wrong-instance bugs, and “works on author machine only” coverage.
**Warning signs:**
- Profiles encode absolute `/Applications/...app` paths or one process name as the only launch strategy.
- “Launched successfully” is inferred from process spawn alone.
- The same profile behaves differently when the app is already running.
- Reports say `error` or `blocked` without distinguishing “not installed”, “opened but not ready”, and “opened existing substituted instance”.
**Prevention:** Add layered launch resolution: bundle identifier, application URL, known install locations, and explicit “already running” attach paths. Treat “launch requested”, “process exists”, “frontmost window appears”, and “automation transport becomes usable” as separate checkpoints. Persist learned launch hints in a stable project config root, not `cwd`.
**Detection:** Re-run the same workflow with the target app closed, already open, and installed in a non-default location.
**Which phase should address it:** Early platform hardening phase for app discovery, launch resolution, and startup diagnostics.

### Pitfall 2: Treating Accessibility permission as one global yes/no switch
**What goes wrong:** The framework checks Accessibility once, then assumes all UI automation will work.
**Why it happens:** Demo automation often stops at `AXIsProcessTrustedWithOptions`-style prompting. In practice, trust state, prompt behavior, host process identity, and live AX interaction reliability are separate concerns.
**Consequences:** Users grant permission yet workflows still fail with generic AX errors; support becomes unreproducible across packaging modes and helper processes.
**Warning signs:**
- The system only records “Accessibility granted: true/false”.
- Helper/sidecar processes perform AX work but only the main CLI is documented for permission setup.
- AX failures such as “cannot complete” are bucketed as generic runtime errors.
- No preflight confirms the framework can actually inspect a known UI element after permission is granted.
**Prevention:** Model Accessibility as a staged preflight: permission promptability, current trust state, controlling-process identity, and live smoke against a safe known target. Record which executable actually needs AX rights. Make AX-specific blocker states first-class in reports.
**Detection:** Test packaged app, CLI, and helper/sidecar execution paths separately; verify one can enumerate and inspect a simple Finder or System Settings UI element after permission is granted.
**Which phase should address it:** Platform permissions and diagnostics phase.

### Pitfall 3: Collapsing Apple Events failures, TCC denial, and “app is not scriptable” into one bucket
**What goes wrong:** AppleScript or Apple-event-based adapters fail, and the framework reports a generic automation failure instead of distinguishing permission denial from missing scriptability or dictionary mismatch.
**Why it happens:** Demo targets are usually Finder, Safari, or Script Editor-friendly apps. Real apps vary widely: some expose rich scripting dictionaries, some expose partial terminology, and many are effectively non-scriptable.
**Consequences:** Teams waste time “fixing” adapters for apps that do not support the required Apple-event surface, while real TCC permission issues remain hidden.
**Warning signs:**
- “AppleScript failed” is the only error class.
- No discovery step checks whether the target app exposes a usable scripting dictionary or specific verbs.
- The framework retries the same AppleScript on every run even after a stable “not scriptable” outcome.
- Permission prompts appear inconsistently and the report does not capture which target app was being automated.
**Prevention:** Split Apple-event outcomes into at least: permission denied, target not scriptable, target partially scriptable, command unsupported, and adapter bug. Add dictionary/sdef inspection and per-command capability metadata before claiming support. Cache negative findings by app version/build.
**Detection:** Run the same Apple-event preflight against Finder, Safari, and one known weakly-scriptable third-party app; verify the framework produces different blocker classes.
**Which phase should address it:** Apple Events transport phase and per-app capability modeling phase.

### Pitfall 4: Overfitting browser automation to one happy-path transport
**What goes wrong:** Browser support is declared “done” because one Chromium profile works through CDP on one machine, but real workflows break when attaching to existing sessions, using Safari, or dealing with user profiles and permission prompts.
**Why it happens:** Browser demos are easy with a fresh Chrome instance and a debug port. Real operator environments involve existing windows, profile contamination, security prompts, downloads, extensions, and browser-family differences.
**Consequences:** Browser coverage looks broad in demos but is brittle in real use, especially for attach flows and non-Chromium browsers.
**Warning signs:**
- The framework attaches to arbitrary existing Chrome sessions and assumes WebDriver/CDP parity.
- Browser runs reuse the user’s primary profile without isolation.
- Safari is treated as equivalent to Chromium despite requiring a different automation path.
- Verification checks only DOM reads, not downloads, uploads, dialogs, or multi-tab flows.
**Prevention:** Separate Chromium-launch, Chromium-attach, and Safari/WebKit strategies. Use isolated user-data dirs for managed Chromium sessions. Mark attach flows as lower-confidence because some commands are unsupported on existing remote-debug sessions. Keep browser-family-specific contracts rather than one generic “browser” adapter.
**Detection:** Run the same workflow in fresh Chromium, attached Chromium, and Safari. Include tabs, downloads, and modal/dialog steps, not just page reads.
**Which phase should address it:** Browser coverage phase with transport-specific verification.

### Pitfall 5: Assuming Office automation on macOS matches Windows or is uniform across apps
**What goes wrong:** The framework ports Windows office assumptions directly to macOS, or treats Word, Excel, and PowerPoint as having equivalent automation capabilities.
**Why it happens:** Office demos usually prove one document edit and stop. On macOS, Office behavior is shaped by sandboxing, app-specific AppleScript/VBA support, UI differences, and file-open/save flows that are less uniform than on Windows.
**Consequences:** “Office support” lands as marketing rather than reliable capability; workflows fail on open/save/export/share cases even if text insertion passed.
**Warning signs:**
- A single “office-write” adapter is meant to cover all Office apps.
- Tests focus on typing into an already open document.
- Save/open/export flows are not verified.
- The framework does not account for file permission dialogs, sandboxed file access, or first-run prompts.
**Prevention:** Treat each Office app as a separate capability target. Verify open, read, mutate, save, export, and re-open flows independently. Prefer app-specific contracts and evidence over a generic office abstraction.
**Detection:** For each Office app, automate a full document lifecycle from launch to saved artifact, then re-open the artifact and verify the change persisted.
**Which phase should address it:** Office/productivity coverage phase.

### Pitfall 6: Shipping operation-level demos instead of workflow-level verification
**What goes wrong:** The framework proves isolated reads and writes but not the multi-step workflows that make the framework practically usable.
**Why it happens:** Single-step smokes are cheap and deterministic. Real workflows require launch timing, focus changes, cross-app handoff, dialogs, and persistence checks.
**Consequences:** Claimed support collapses under actual agent usage because the framework never validated end-to-end state transitions.
**Warning signs:**
- Success means “clicked button” or “typed text”, not “the target state changed and persisted”.
- No test crosses app boundaries such as Finder -> browser upload -> office save/export.
- Reports do not record pre-state and post-state.
- Workflows flake only on second or third step because readiness/focus was never modeled.
**Prevention:** Define support tiers around workflow classes, not raw commands. Every “supported” app needs at least one representative read workflow, one write workflow, and one multi-step persistence workflow. Add explicit waits for application-ready, document-ready, and dialog-ready states rather than fixed sleeps.
**Detection:** Require every new adapter to pass a persisted workflow verification, not only a smoke command.
**Which phase should address it:** Verification framework phase and first-wave app coverage phases.

### Pitfall 7: Weak evidence quality and poor blocker taxonomy
**What goes wrong:** Runs produce screenshots or plain logs that are not sufficient to tell whether failure came from permissions, launchability, unsupported transport, timing, or a genuine adapter defect.
**Why it happens:** Demo frameworks optimize for visible success, not for forensic debugging after failures on diverse machines.
**Consequences:** Roadmap decisions are made on noisy data, partial support is mislabeled as failure, and regressions cannot be triaged confidently.
**Warning signs:**
- Reports only contain pass/fail plus one screenshot.
- No capture of app version, bundle ID, transport used, permission state, or exact step that failed.
- “blocked”, “partial”, and “error” are used inconsistently.
- Evidence cannot prove persistence, only that a UI looked plausible once.
**Prevention:** Standardize evidence bundles per run: app identity, app version, launch method, transport chosen, permission preflight results, structured step timeline, before/after artifacts, and normalized blocker codes. Require machine-readable status semantics for `ok`, `partial`, `blocked`, and `error`.
**Detection:** Hand a failed run to someone who did not execute it; if they cannot determine root cause from artifacts alone, evidence quality is inadequate.
**Which phase should address it:** Runtime reporting and evidence-model phase.

## Moderate Pitfalls

### Pitfall 8: No explicit support tiers across apps and transports
**What goes wrong:** The framework treats every app as either “supported” or “unsupported”.
**Warning signs:**
- Roadmap language promises full support for extension apps.
- Runtime output hides whether a result came from a degraded fallback.
- Sidecars and alternate transports are used silently.
**Prevention:** Publish support tiers such as `core`, `extension`, and `experimental`, and record transport confidence in results.
**Which phase should address it:** Coverage policy phase and reporting phase.

### Pitfall 9: No per-app capability registry
**What goes wrong:** New adapters are added ad hoc, with no durable record of which actions are proven for which app/version/transport.
**Warning signs:**
- Capability claims live only in code branches and test names.
- The same discovery logic is rewritten for each app family.
- Regression reports cannot answer “what was supposed to work here?”
**Prevention:** Maintain a typed capability registry keyed by app identity, version range, transport, and verified workflow classes.
**Which phase should address it:** Adapter architecture and registry consolidation phase.

### Pitfall 10: Polluting the user’s real environment during automation
**What goes wrong:** Automation reuses primary browser profiles, opens personal documents, or leaves apps in mutated state, making failures hard to trust or reproduce.
**Warning signs:**
- Tests depend on preexisting tabs, accounts, or documents.
- Cleanup kills all matching processes instead of framework-launched instances.
- Re-running a workflow changes the outcome because prior state leaked.
**Prevention:** Use isolated browser profiles, temp documents, explicit fixture directories, and launch-instance tracking for cleanup. Never rely on ambient user state for a passing result.
**Which phase should address it:** Test harness isolation phase and adaptive startup/cleanup phase.

## Minor Pitfalls

### Pitfall 11: Fixed sleeps instead of readiness checks
**What goes wrong:** Workflows pass locally and flake elsewhere because the framework waits for elapsed time instead of observable state.
**Prevention:** Replace sleeps with window, AX, document, network, or artifact readiness predicates.
**Which phase should address it:** Verification framework phase.

### Pitfall 12: Ignoring macOS-specific packaging identity
**What goes wrong:** Permissions and launch behavior differ between CLI runs, local builds, packaged apps, and helper executables, but the framework treats them as the same actor.
**Prevention:** Make executable identity explicit in diagnostics and installation/setup docs; test each packaging mode that will be supported.
**Which phase should address it:** Packaging and operator setup phase.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| App discovery and startup | Hard-coded paths; success inferred from spawn | Add bundle-ID and app-URL resolution, “already running” handling, and multi-stage startup checkpoints |
| Accessibility diagnostics | Permission shown as global boolean | Add controlling-process identity, live AX preflight, and AX-specific blocker codes |
| Apple Events transport | Permission denial and non-scriptability conflated | Add sdef/dictionary inspection and separate status codes |
| Browser coverage | CDP happy path mistaken for browser support | Split fresh-launch, attach, and Safari/WebKit strategies; isolate profiles |
| Office automation | “Office” treated as one app family | Verify each app separately across open/edit/save/export/reopen |
| Workflow verification | Single actions passed off as support | Require persisted multi-step workflow proofs |
| Reporting/evidence | Screenshots used as proof of correctness | Emit structured evidence bundles with before/after artifacts and normalized blocker reasons |
| Adapter scaling | Capabilities live in scattered code paths | Consolidate into a typed registry and derive runtime/reporting from it |

## Sources

- Apple Developer Documentation, `NSWorkspace openApplication(at:configuration:completionHandler:)` — asynchronous app launch and completion model. https://developer.apple.com/documentation/appkit/nsworkspace/openapplication%28at%3Aconfiguration%3Acompletionhandler%3A%29?changes=_9_5 — HIGH
- Apple Developer Documentation, `AXUIElementSetAttributeValue` and related Accessibility APIs — low-level AX operations can fail independently of trust state. https://developer.apple.com/documentation/applicationservices/1460434-axuielementsetattributevalue — HIGH
- Apple Developer Documentation, `NSScriptSuiteRegistry` — scriptability is app-defined via scripting terminology and not universal. https://developer.apple.com/documentation/foundation/nsscriptsuiteregistry — HIGH
- Apple Mac Automation Scripting Guide — application/script app model and AppleScript automation foundations. https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/TypesofScripts.html — MEDIUM
- Chrome for Developers, “Operation not supported when using remote debugging” — attaching to existing Chrome sessions is not equivalent to a fresh launched automation session. https://developer.chrome.com/docs/chromedriver/help/operation-not-supported-when-using-remote-debugging?hl=en — HIGH
- WebKit, “WebKit Features in Safari 16.4” — Safari WebDriver behavior evolves separately and should not be assumed to match Chromium automation paths. https://webkit.org/blog/13966/webkit-features-in-safari-16-4/ — MEDIUM
- Microsoft Learn, “Office for Mac for Visual Basic for Applications (VBA)” — Office for Mac sandboxing and Mac-specific automation constraints. https://learn.microsoft.com/hu-hu/office/vba/api/overview/office-mac — MEDIUM
- OmniControl project context, `.planning/PROJECT.md` — v1 emphasis on real app coverage, layered acceptance, and evidence-rich diagnostics. `/Users/daizhaorong/OmniControl/.planning/PROJECT.md` — HIGH
- OmniControl codebase concerns, `.planning/codebase/CONCERNS.md` — current risk areas around path resolution, registry drift, hidden root causes, and real integration gaps. `/Users/daizhaorong/OmniControl/.planning/codebase/CONCERNS.md` — HIGH
- OmniControl testing notes, `.planning/codebase/TESTING.md` — current test strengths and real integration coverage gaps. `/Users/daizhaorong/OmniControl/.planning/codebase/TESTING.md` — HIGH

