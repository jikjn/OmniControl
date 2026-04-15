# External Integrations

**Analysis Date:** 2026-04-15

## APIs & External Services

**Public web APIs:**
- QQ Music web APIs - Song lookup and metadata retrieval for the `qqmusic-play` smoke profile in `omnicontrol/runtime/live_smoke.py`
  - SDK/Client: Python stdlib `urllib.request` and `json` in `omnicontrol/runtime/live_smoke.py`
  - Auth: No repo-managed secret; requests set a browser-style `Referer` header and rely on public endpoints
  - Endpoints implemented in code:
    - `https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg`
    - `https://u.y.qq.com/cgi-bin/musicu.fcg`
    - `https://jump.qq.com/qqmusic_4`
    - `https://dl.stream.qqmusic.qq.com/...`
    - `https://y.qq.com/...`

**Local debugging/control APIs:**
- Chromium DevTools Protocol (CDP) over localhost - Browser and Electron control for Chrome, Quark, and Trae profiles in `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/adaptive_startup.py`, and `omnicontrol/runtime/scripts/*.js`
  - SDK/Client: Custom Node helpers in `omnicontrol/runtime/scripts/chrome_cdp_smoke.js`, `chrome_form_write_smoke.js`, `desktop_cdp_observe.js`, `cdp_workflow_probe.js`, and `target_cdp_probe.js`
  - Auth: None; connects to local `http://127.0.0.1:<port>/json/version` and target websocket URLs discovered from `/json/list`

**Vendor desktop automation surfaces:**
- Microsoft Word COM automation - Windows smoke automation in `omnicontrol/runtime/live_smoke.py` via `omnicontrol/runtime/scripts/word_export_smoke.ps1`, `word_write_smoke.ps1`, and `word_workflow_smoke.ps1`
  - SDK/Client: PowerShell scripts launched by Python subprocesses
  - Auth: None in repo; depends on locally installed Office
- Adobe Illustrator scripting/plugin surface - Export smoke in `omnicontrol/runtime/live_smoke.py` via `omnicontrol/runtime/scripts/illustrator_export_smoke.ps1`
  - SDK/Client: PowerShell plus host Illustrator scripting surface
  - Auth: None in repo; depends on local install
- Everything desktop search - UI automation smoke in `omnicontrol/runtime/live_smoke.py` via `omnicontrol/runtime/scripts/everything_search_smoke.ps1`
  - SDK/Client: PowerShell/UI Automation
  - Auth: None
- QQ Music vendor commands and private protocol - Multiple control paths in `omnicontrol/runtime/live_smoke.py`
  - SDK/Client: PowerShell helper generation, Win32 `WM_COPYDATA`, custom tagged packets in `omnicontrol/runtime/windows_ipc.py`, and protocol payloads such as `tencent://QQMusic/...`
  - Auth: Local runtime state only; no stored token/env contract in repo
- Siemens NX tooling - Diagnostic smoke attempts in `omnicontrol/runtime/live_smoke.py`
  - SDK/Client: Vendor executables like `run_journal.exe` and `display_nx_help.exe`
  - Auth: None in repo; runtime blocked/partial states are handled through contracts
- SIMULIA Isight tooling - Diagnostic and remediation attempts in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/scripts/isight_diagnose_smoke.ps1`
  - SDK/Client: Vendor batch files such as `fiperenv.bat`, `fipercmd.bat`, and `licusage.bat`
  - Auth: None in repo; relies on local install/profile licensing
- Unreal Engine command-line tooling - Diagnostic and Python-write probes in `omnicontrol/runtime/live_smoke.py`
  - SDK/Client: `UnrealEditor-Cmd.exe` and `UnrealEditor.exe`
  - Auth: None in repo
- macOS Finder and Safari scripting - AppleScript-driven automation in `omnicontrol/runtime/live_smoke.py`
  - SDK/Client: `osascript` plus `omnicontrol/runtime/scripts/finder_open_smoke.applescript`, `safari_open_smoke.applescript`, and `safari_dom_write_smoke.applescript`
  - Auth: None

## Data Storage

**Databases:**
- Not detected
  - Connection: Not applicable
  - Client: Not applicable

**File Storage:**
- Local filesystem only
  - Persistent learning data: `knowledge/kb.json` from `omnicontrol/runtime/kb.py`
  - Benchmark configs: `benchmarks/local_closed_source_windows.json` and `benchmarks/local_closed_source_macos.json`
  - Generated scaffolds: `generated/<slug>/` from `omnicontrol/cli.py`
  - Benchmark reports: `benchmark-output/<config-stem>/benchmark-report.json` from `omnicontrol/benchmark.py`
  - Smoke evidence: `smoke-output/<profile>/` from `omnicontrol/runtime/live_smoke.py`

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- Custom/no centralized auth
  - Implementation: Integration calls are local-process, local-file, or public-endpoint based; the codebase does not define OAuth, API key loading, session storage, or user identity management in `omnicontrol/`, `tests/`, `docs/`, or `pyproject.toml`

## Monitoring & Observability

**Error Tracking:**
- None detected

**Logs:**
- Structured JSON result files written per benchmark and smoke run in `omnicontrol/benchmark.py` and `omnicontrol/runtime/live_smoke.py`
- Runtime knowledge and remediation history persisted in `knowledge/kb.json` through `omnicontrol/runtime/kb.py`

## CI/CD & Deployment

**Hosting:**
- Not applicable; no server deployment target detected

**CI Pipeline:**
- None detected; no `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, or similar pipeline config was found under `/Users/daizhaorong/OmniControl`

## Environment Configuration

**Required env vars:**
- None detected in source

**Secrets location:**
- Not applicable; no secret-loading files or secret-backed config contract were detected in the repository

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- QQ Music HTTP requests from `omnicontrol/runtime/live_smoke.py`
- Localhost CDP polling and websocket attachment from `omnicontrol/runtime/adaptive_startup.py`, `omnicontrol/runtime/live_smoke.py`, and `omnicontrol/runtime/scripts/*.js`

---

*Integration audit: 2026-04-15*
