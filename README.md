# OmniControl

English | [简体中文](./README.zh-CN.md)

OmniControl is a capability-first control-plane scaffolder for software automation.
Instead of assuming a single automation stack, it separates the problem into three decisions:

1. Detect which control surfaces a target exposes.
2. Choose the most stable adapter strategy and fallback chain.
3. Choose the most suitable scripting language for that target and task.

The project is designed to stay lightweight at the generation layer while still supporting targeted runtime validation when needed.

## What It Does

- Detects likely control surfaces such as native scripts, plugins, CLIs, file formats, UI automation, CDP, and vision fallback.
- Produces plans with a primary adapter, fallback adapters, a language choice, and verification hints.
- Scaffolds lightweight manifests and script templates.
- Provides runtime smoke entrypoints for selected profile-based integrations.
- Uses structured outcomes like `ok`, `partial`, `blocked`, and `error` instead of treating every run as binary success/failure.
- Supports recovery pivots so a blocked primary path can degrade to a lighter sibling path when appropriate.
- Materializes complex script payloads into files when inline command-line transport would be fragile.

## CLI

OmniControl exposes five top-level commands:

- `detect`
- `plan`
- `scaffold`
- `benchmark`
- `smoke`

Help:

```bash
python -m omnicontrol --help
python -m omnicontrol smoke --help
```

## Quick Start

```bash
cd OmniControl

python -m omnicontrol detect "SomeDesktopApp" --platform windows --kind desktop --need ui
python -m omnicontrol plan "https://example.com" --kind web --need browser --need dom --json
python -m omnicontrol scaffold "LegacyDesktopApp" --platform windows --kind desktop --need ui --output .\generated\legacy-app
```

## Benchmark Configs

`benchmark` consumes a JSON file that describes local targets and expected planning outcomes.

Minimal example:

```json
{
  "items": [
    {
      "name": "sample_web_target",
      "target": "https://example.com",
      "platform": "windows",
      "kind": "web",
      "needs": ["browser", "dom"],
      "expected_primary": "cdp",
      "expected_language": "typescript"
    }
  ]
}
```

Run it with:

```bash
python -m omnicontrol benchmark .\my-benchmark.json --json
```

## Runtime Smoke

`smoke` is the runtime verification entrypoint.
Profiles are intentionally targeted rather than universal. Depending on the profile, a run may validate:

- file export or file-format writes
- CDP read/write flows
- desktop UI automation checks
- vendor CLI or native-script entrypoints
- workflow-style multi-step verification
- diagnose flows that may return `partial` instead of hard failure

Examples:

```bash
python -m omnicontrol smoke chrome-cdp --json
python -m omnicontrol smoke chrome-form-write --json
python -m omnicontrol smoke word-write --json
python -m omnicontrol smoke nx-diagnose --json
```

## Design Principles

- Control-plane first, not source-code first.
- Verification-first, not command-execution-first.
- Thin scaffolds by default, deeper runtime paths only where justified.
- Language choice should follow the control surface, not a single-language bias.
- Public repo content should stay free of local machine traces and internal working notes.

## Repository Layout

- `omnicontrol/`: package source
- `tests/`: unit tests
- `pyproject.toml`: packaging and CLI entrypoint

Runtime outputs such as `smoke-output/`, `benchmark-output/`, caches, and learned local state are intentionally not tracked.

## Boundaries

OmniControl is not a general-purpose RPA platform.

- It does not promise universal GUI discovery and end-to-end automation for arbitrary applications.
- Its CDP and runtime integrations are lightweight, profile-oriented entrypoints rather than full vendor SDK wrappers.
- Some profiles require locally installed third-party software and environment-specific setup.
- Internal research notes, local benchmark inventories, and machine-specific runtime traces are intentionally excluded from the public repository.

## Development

Install in editable mode:

```bash
pip install -e .
```

Run a lightweight test slice:

```bash
python -m unittest tests.test_invocation tests.test_staging tests.test_transports
```
