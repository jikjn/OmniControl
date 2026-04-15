# Technology Stack

**Analysis Date:** 2026-04-15

## Languages

**Primary:**
- Python 3.10+ - Core CLI, detector, planner, runtime, benchmark runner, and scaffold generator in `pyproject.toml`, `omnicontrol/cli.py`, `omnicontrol/detector/capability_detector.py`, `omnicontrol/planner/adapter_selector.py`, `omnicontrol/runtime/live_smoke.py`, and `omnicontrol/benchmark.py`

**Secondary:**
- PowerShell - Windows automation payloads and smoke scripts in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/scripts/*.ps1`
- JavaScript - CDP probes and Node-driven smoke helpers in `omnicontrol/runtime/scripts/*.js`
- AppleScript - macOS Finder and Safari smoke scripts in `omnicontrol/runtime/scripts/*.applescript`
- JSON - Benchmark fixtures and persistent runtime knowledge in `benchmarks/local_closed_source_windows.json`, `benchmarks/local_closed_source_macos.json`, and `knowledge/kb.json`
- Markdown - Product and strategy docs in `README.md` and `docs/*.md`

## Runtime

**Environment:**
- CPython 3.10 or newer required by `pyproject.toml`
- The installed CLI entry point is `omnicontrol = "omnicontrol.cli:main"` in `pyproject.toml`
- Runtime subprocess integration expects host tools such as `powershell`, `node`, and `osascript` as invoked from `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/adaptive_startup.py`

**Package Manager:**
- `pip`/PEP 517 build flow via `setuptools.build_meta` in `pyproject.toml`
- Lockfile: missing; no `requirements.txt`, `poetry.lock`, or `uv.lock` detected at `/Users/daizhaorong/OmniControl`

## Frameworks

**Core:**
- Python standard library - Main application framework; `argparse`, `json`, `pathlib`, `subprocess`, `socket`, `urllib`, `ctypes`, and `xml.etree.ElementTree` drive nearly all functionality in `omnicontrol/cli.py`, `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/adaptive_startup.py`, and `omnicontrol/runtime/windows_ipc.py`
- `setuptools>=68` - Packaging and distribution backend in `pyproject.toml`

**Testing:**
- `unittest` - Active test runner and suite style in `tests/test_*.py` and `tests/TEST.md`
- `pytest>=8` - Optional dev dependency only, declared in `[project.optional-dependencies].dev` in `pyproject.toml`

**Build/Dev:**
- `setuptools` package discovery - Package inclusion and runtime script assets configured in `pyproject.toml`
- No linter, formatter, type-checker, or task runner config detected; no `ruff`, `black`, `mypy`, `tox`, `nox`, or CI config files were found under `/Users/daizhaorong/OmniControl`

## Key Dependencies

**Critical:**
- Python stdlib subprocess/process APIs - External tool orchestration and smoke execution in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/adaptive_startup.py`
- Python stdlib networking APIs - HTTP/CDP probing and QQ Music requests through `urllib.request` in `omnicontrol/runtime/live_smoke.py`
- Python stdlib `ctypes` and Win32 bindings - Windows window messaging and process inspection in `omnicontrol/runtime/windows_ipc.py`

**Infrastructure:**
- Node.js runtime - Required by CDP helper scripts such as `omnicontrol/runtime/scripts/chrome_cdp_smoke.js`, `omnicontrol/runtime/scripts/chrome_form_write_smoke.js`, `omnicontrol/runtime/scripts/desktop_cdp_observe.js`, and `omnicontrol/runtime/scripts/target_cdp_probe.js`
- Windows PowerShell - Required by Windows smoke profiles and process/window inspection in `omnicontrol/runtime/live_smoke.py`, `omnicontrol/runtime/adaptive_startup.py`, and `omnicontrol/runtime/scripts/*.ps1`
- `osascript` - Required by macOS smoke profiles executed from `omnicontrol/runtime/live_smoke.py` against `omnicontrol/runtime/scripts/finder_open_smoke.applescript`, `safari_open_smoke.applescript`, and `safari_dom_write_smoke.applescript`

## Configuration

**Environment:**
- No environment-variable configuration contract is implemented in source; searches across `omnicontrol/`, `tests/`, `docs/`, `README.md`, and `pyproject.toml` did not detect `os.environ`, `getenv`, or named secret variables
- `.env` files: not detected in `/Users/daizhaorong/OmniControl`
- Runtime behavior is configured primarily by CLI flags in `omnicontrol/cli.py`, benchmark JSON files in `benchmarks/*.json`, profile metadata in `omnicontrol/runtime/kb.py`, and persisted learning data in `knowledge/kb.json`

**Build:**
- Build metadata and packaging live in `pyproject.toml`
- Generated artifacts default to local workspace directories from `omnicontrol/cli.py`:
  - `generated/<slug>/` for scaffolds
  - `benchmark-output/<config-stem>/` for benchmark reports
  - `smoke-output/<profile>/` for smoke evidence from `omnicontrol/runtime/live_smoke.py`

## Platform Requirements

**Development:**
- Python 3.10+ and `setuptools` are required by `pyproject.toml`
- Node.js is required for CDP helper execution referenced by `omnicontrol/runtime/live_smoke.py` and `tests/test_cdp_target_helpers.py`
- Windows development is required to exercise most real smoke profiles, PowerShell automation, COM/UIA flows, and Win32 IPC in `omnicontrol/runtime/live_smoke.py` and `omnicontrol/runtime/windows_ipc.py`
- macOS development is required for Finder/Safari AppleScript smoke coverage in `omnicontrol/runtime/live_smoke.py`

**Production:**
- Not a deployed web service; the project runs as a local operator CLI and scaffold generator from `omnicontrol/cli.py`
- Effective execution target is an operator workstation with installed vendor applications and local automation surfaces, as reflected in `README.md`, `benchmarks/local_closed_source_windows.json`, and `benchmarks/local_closed_source_macos.json`

---

*Stack analysis: 2026-04-15*
