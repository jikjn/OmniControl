# Technology Stack

**Project:** OmniControl macOS automation runtime
**Researched:** 2026-04-15
**Scope:** Brownfield stack recommendations for making the existing Python-centric local automation framework practically usable on macOS
**Overall recommendation confidence:** HIGH

## Executive Recommendation

Use a **layered macOS runtime**:

1. **Keep CPython as the orchestration core**
2. **Add a stable signed macOS helper app as the automation principal**
3. **Use PyObjC for launchability, Accessibility, window/process inspection, and native macOS APIs**
4. **Keep AppleScript for scriptable apps like Finder and Microsoft 365**
5. **Use Playwright Python for browser-first and Electron/Chromium verification flows**
6. **Treat TCC permissions and verification artifacts as first-class runtime concerns**

Do **not** try to make one control plane do everything. On macOS in 2026, the practical stack is a control-plane ladder:

`app-native scriptability` -> `browser protocol` -> `native macOS APIs` -> `Accessibility fallback`

That fits the current OmniControl architecture because it preserves the existing Python CLI/orchestrator model, keeps AppleScript where it already works, and replaces the fragile macOS-only edges with a stronger native runtime instead of a rewrite.

## Recommended Stack

### Core Runtime

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| CPython | 3.12.x default, keep `>=3.10` compatibility during migration | Main CLI/orchestrator/runtime | PyObjC 12.1 supports Python 3.10-3.14; Python 3.12 is the safest current baseline for wheel availability and avoids forcing a brownfield rewrite to 3.13/3.14 behavior too early | HIGH |
| Stable macOS helper app bundle | Custom `OmniControl Agent.app` | Permission principal for Automation, Accessibility, Screen Recording, and launch control | macOS permissioning is tied to the calling app/binary identity. A stable signed app bundle is far more usable than a changing venv Python path or ad hoc `osascript` subprocesses | HIGH |
| CLI + helper IPC | Unix domain socket or stdio JSON-RPC | Keep current CLI architecture while moving macOS-specific calls into one durable host | Brownfield-friendly: existing Python CLI remains the front door, while macOS-sensitive operations move behind a narrow adapter boundary | HIGH |

### Native macOS Access

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| PyObjC | 12.1 | Python bridge to AppKit, Quartz, ApplicationServices, ScriptingBridge | Best fit for a Python-centric codebase that needs real macOS APIs without dropping into Swift/ObjC for the whole runtime | HIGH |
| `pyobjc-framework-Cocoa` / AppKit | 12.1 | App launch, activation, workspace inspection, app lifecycle | Needed for `NSWorkspace`, `NSRunningApplication`, and stable app launch/focus control | HIGH |
| `pyobjc-framework-ApplicationServices` | 12.1 | Accessibility/HIServices APIs | PyObjC documents HIServices as fully supported; this is the practical foundation for UI-state fallback on macOS | HIGH |
| `pyobjc-framework-Quartz` | 12.1 | Window enumeration, screenshots, event posting | Quartz/CoreGraphics covers verification artifacts and last-mile input/event fallback without adding another language runtime | HIGH |
| `pyobjc-framework-ScriptingBridge` | 12.1 optional | Structured access to scriptable apps when AppleScript strings become hard to maintain | Useful for selected adapters, but not required on day one because OmniControl already has AppleScript assets | MEDIUM |
| `psutil` | 7.2.2 | Cross-platform process discovery, child cleanup, process metadata | Better process observability and cleanup than shelling out to `ps`; complements `NSRunningApplication` instead of replacing it | HIGH |

### App Control Surfaces

| Surface | Primary Stack | Secondary/Fallback | Why | Confidence |
|---------|---------------|--------------------|-----|------------|
| Finder / files | AppleScript + PyObjC launch/file checks | Accessibility only when Finder scriptability is insufficient | Finder is natively scriptable; filesystem verification is stronger than visual-only checks | HIGH |
| Browser (Chromium) | Playwright Python 1.58.0 launch mode | Playwright `connect_over_cdp` attach mode for existing sessions | Best verification and artifact story. CDP attach is practical for existing app sessions, but Playwright docs explicitly note it is lower fidelity than the native Playwright protocol | HIGH |
| Safari | AppleScript for simple app-level flows; SafariDriver/WebDriver only for isolated browser-only tests | Accessibility fallback | Safari is not a good foundation for the whole framework. Keep it narrow and explicit | MEDIUM |
| Microsoft 365 apps | AppleScript first | Accessibility fallback for gaps; filesystem/output verification | Office on Mac still exposes AppleScript-related integration points; this matches the current repo and is materially more practical than UI scripting first | MEDIUM |
| VS Code / developer apps | Native CLI surfaces first (`code`, `git`, shell tools) | CDP for Electron-based IDEs; Accessibility for UI-only steps | Developer tools often have better CLI/workspace surfaces than GUI automation. Use those first and reserve UI control for truly UI-bound steps | HIGH |
| Terminal / iTerm | Shell/CLI first | AppleScript when window/tab control is required | Terminal work should not go through Accessibility unless the workflow is explicitly window-management oriented | HIGH |

### Verification and Evidence

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Playwright traces | 1.58.0 | Browser workflow evidence | Playwright Trace Viewer provides rich step-by-step artifacts with screenshots, DOM snapshots, logs, network, and source mapping | HIGH |
| Quartz screenshots/window metadata | 12.1 via PyObjC | Native app verification evidence | Strong fallback for native app workflows when scriptable state alone is insufficient | HIGH |
| App-native state assertions | n/a | Semantic verification | Prefer document state, filesystem outputs, tab URLs, selected items, or app object-model reads over image-only checks | HIGH |
| Accessibility snapshots | 12.1 via PyObjC | Fallback structural verification | Useful when app-native APIs are absent, but weaker and more brittle than semantic state | HIGH |

### Permissions and Deployment

| Facility | Purpose | Why | Confidence |
|----------|---------|-----|------------|
| TCC-aware preflight checks | Detect Automation, Accessibility, Screen Recording, and file-access blockers | macOS usability fails mostly on permissions before adapter logic fails; the runtime must classify these separately | HIGH |
| Signed app identity for helper | Stable TCC entries and better launchability | Permission prompts and allow-lists are much more manageable with a stable bundle identifier than with ephemeral Python paths | HIGH |
| PPPC profile support for managed environments | Pre-authorize Automation/Accessibility/Post Event/file scopes | Apple’s PPPC payload explicitly covers Accessibility, AppleEvents, Post Event, Screen Recording, and System Policy All Files; this matters for repeatable team setup | HIGH |

## Prescriptive Choices

### Use These

#### 1. Keep Python as the control plane coordinator

Do not rewrite OmniControl around Swift just to become “more native.” The existing architecture already has the right shape: detector -> planner -> runtime -> contract evaluation. The missing piece is a stronger macOS execution host, not a new language for the whole system.

#### 2. Add a dedicated macOS automation host

Create a small long-lived helper process, ideally packaged as a signed `.app`, that owns:

- app launch and activation
- Apple Events dispatch
- Accessibility checks and actions
- screenshots/window enumeration
- permission preflight and diagnostics

This should be the runtime identity the OS sees. The current pattern of calling `osascript` and shell tools from arbitrary processes is acceptable for experiments, but it is the wrong principal for a practical framework because TCC state becomes fragmented and hard to explain.

#### 3. Use PyObjC as the native bridge

PyObjC is the best brownfield move because it keeps the runtime in Python while exposing AppKit, Quartz, HIServices, and optional ScriptingBridge access. It is the shortest path from the current subprocess-heavy macOS support to real macOS runtime control.

#### 4. Keep AppleScript as a first-class adapter language for scriptable apps

For Finder and Microsoft 365 on macOS, AppleScript remains practical. OmniControl already has AppleScript smoke assets; keep them, but formalize them:

- prefer compiled `.scpt` assets over free-form inline strings
- normalize inputs/outputs as JSON-safe text
- pair every AppleScript action with independent verification
- classify Apple Event permission denials separately from adapter failure

#### 5. Standardize browser automation on Playwright Python

Use Playwright Python for browser workflows and browser verification. Prefer:

- `launch_persistent_context` or normal Playwright launch when OmniControl owns browser startup
- `connect_over_cdp` only when attaching to an already-running Chromium/Electron target is required

This aligns the browser stack with the Python core and gives better evidence than the current Node-only helper approach.

#### 6. Use app-native surfaces before Accessibility

For developer tools especially:

- use `code` for VS Code workspace/file actions
- use shell/git directly for terminal workflows
- use browser/Electron protocols when available
- use Accessibility only when the action is genuinely UI-only

This reduces brittleness and makes verification materially stronger.

## Do Not Use These as Foundations

| Avoid | Why Not | What To Use Instead |
|------|---------|---------------------|
| `System Events` GUI scripting as the default automation plane | Too brittle, permission-heavy, and poor for semantic verification | App-native scripting, Playwright/CDP, PyObjC native APIs, then Accessibility fallback |
| A raw venv Python interpreter as the only macOS automation principal | TCC identity becomes unstable across machines, paths, and rebuilds | Stable signed helper app bundle |
| Node.js as a mandatory browser runtime for macOS | It adds a second primary runtime without solving native macOS automation | Playwright Python, keep existing JS helpers only as transition shims |
| Selenium/WebDriver as the main browser stack | Worse fit for Chromium attach workflows and weaker brownfield alignment with current CDP-oriented logic | Playwright Python |
| JXA as a primary language | No strong advantage over AppleScript plus PyObjC, and it increases maintenance surface | AppleScript for scriptable apps, Python/PyObjC for everything else |
| Screenshot-only verification | Produces weak evidence and poor failure classification | Semantic state + filesystem/DOM assertions + AX/window evidence + screenshot last |

## Brownfield Migration Path

### Phase 1: Strengthen the existing Python runtime

- Raise the default development runtime to Python 3.12
- Add explicit macOS extras in packaging
- Keep current AppleScript profiles working
- Introduce PyObjC-backed preflight helpers for:
  - Accessibility trusted check
  - Automation denial classification
  - app launch/activation
  - window/process inspection

### Phase 2: Unify macOS-sensitive execution behind one helper

- Add `OmniControl Agent.app`
- Route Apple Events, AX, screenshotting, and app launch through it
- Keep CLI contracts and output format stable

### Phase 3: Replace browser JS helpers with Python-native Playwright

- Port existing CDP smoke/write/workflow profiles to Playwright Python
- Keep CDP attach mode where existing-session workflows matter
- Emit Playwright trace artifacts into the current evidence model

### Phase 4: Tighten adapter-specific planes

- Finder/files: AppleScript + file assertions
- Browser: Playwright
- Office: AppleScript + output/document verification
- Developer apps: CLI first, Electron/CDP where available, AX last

## Suggested Dependencies

### Core install

```bash
python -m pip install \
  pyobjc-core==12.1 \
  pyobjc-framework-Cocoa==12.1 \
  pyobjc-framework-ApplicationServices==12.1 \
  pyobjc-framework-Quartz==12.1 \
  psutil==7.2.2 \
  playwright==1.58.0
```

### Optional install

```bash
python -m pip install \
  pyobjc-framework-ScriptingBridge==12.1

python -m playwright install chromium webkit
```

## Implementation Notes

### Launchability

Use this launch order:

1. `NSWorkspace` / `NSRunningApplication` via PyObjC
2. `open -a` / LaunchServices fallback
3. app-native startup arguments when the app supports them

Record:

- requested bundle ID / app path
- resolved app path
- PID
- activation result
- frontmost/window-seen result

This will let OmniControl distinguish “app not installed,” “launched but not scriptable,” and “launched but permission blocked.”

### Permission Model

Preflight and classify these separately:

- Automation / Apple Events
- Accessibility
- Screen Recording
- Files & Folders / Full Disk Access where relevant
- Developer Tools for environments that require it

Do not collapse these into generic adapter failure. On macOS, that is the difference between a usable framework and one that feels random.

If you package the helper as an app, account for PyObjC signing/notarization requirements. PyObjC documents Hardened Runtime/JIT-related signing considerations, which matters if `OmniControl Agent.app` becomes the stable shipped automation principal.

### Verification Ladder

For every workflow step, prefer this order:

1. semantic app state
2. filesystem/output artifact
3. browser DOM/network evidence
4. accessibility/window evidence
5. screenshot

That matches the current OmniControl contract model and should be encoded as adapter policy, not left to individual scripts.

## Confidence by Recommendation Area

| Area | Confidence | Notes |
|------|------------|-------|
| Python + PyObjC native runtime | HIGH | Strong fit with current architecture and current PyObjC docs |
| Stable helper app as permission principal | HIGH | Best practical answer to macOS TCC usability; partly inference from Apple permission model, but well-supported |
| Playwright Python for browser workflows | HIGH | Official docs and current release data strongly support it |
| AppleScript-first for Finder and Office | MEDIUM | Pragmatically correct and brownfield-friendly; Office evidence is more indirect than Apple’s own platform docs |
| ScriptingBridge as optional structured layer | MEDIUM | Officially available through PyObjC, but not required for first practical rollout |
| Avoid JXA / GUI scripting as foundations | MEDIUM | Strong practical recommendation, but based partly on engineering judgment rather than a single official doc |

## Sources

- Apple Support: Allow apps to automate and control other apps on Mac  
  https://support.apple.com/guide/mac-help/allow-apps-to-automate-and-control-other-apps-mchl108e1718/mac
- Apple Support: Allow accessibility apps to access your Mac  
  https://support.apple.com/guide/mac-help/allow-accessibility-apps-to-access-your-mac-mh43185/mac
- Apple Support: Privacy Preferences Policy Control payload settings  
  https://support.apple.com/guide/deployment/privacy-preferences-policy-control-payload-dep38df53c2a/web
- PyObjC: supported platforms  
  https://pyobjc.readthedocs.io/en/latest/supported-platforms.html
- PyObjC: ScriptingBridge API notes  
  https://pyobjc.readthedocs.io/en/latest/apinotes/ScriptingBridge.html
- PyObjC: ApplicationServices API notes  
  https://pyobjc.readthedocs.io/en/latest/apinotes/ApplicationServices.html
- PyObjC: Code signing and notarizing  
  https://pyobjc.readthedocs.io/en/latest/notes/codesigning.html
- PyPI: pyobjc-core 12.1 release  
  https://pypi.org/project/pyobjc-core/
- PyPI: psutil 7.2.2 release  
  https://pypi.org/project/psutil/
- PyPI: playwright 1.58.0 release  
  https://pypi.org/project/playwright/
- Playwright Python: `BrowserType.connect_over_cdp`  
  https://playwright.dev/python/docs/api/class-browsertype
- Playwright Python: Trace Viewer  
  https://playwright.dev/python/docs/trace-viewer
- Microsoft Learn: Run an AppleScript with VB  
  https://learn.microsoft.com/en-us/office/vba/office-mac/applescripttask
- Microsoft Learn: Office for Mac update history  
  https://learn.microsoft.com/en-us/officeupdates/update-history-office-for-mac
- VS Code: Visual Studio Code on macOS  
  https://code.visualstudio.com/docs/setup/mac
