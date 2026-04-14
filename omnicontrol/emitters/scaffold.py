from __future__ import annotations

from pathlib import Path
import json

from omnicontrol.models import HarnessManifest, to_jsonable
from omnicontrol.verifier.contracts import summarize_contracts


LANGUAGE_EXTENSIONS = {
    "python": "py",
    "powershell": "ps1",
    "bash": "sh",
    "javascript": "js",
    "typescript": "ts",
    "applescript": "applescript",
    "csharp": "cs",
}


def scaffold_project(manifest: HarnessManifest, output_dir: Path) -> list[Path]:
    scripts_dir = output_dir / "scripts"
    output_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(to_jsonable(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    skill_path = output_dir / "SKILL.md"
    skill_path.write_text(render_skill(manifest), encoding="utf-8")

    ext = LANGUAGE_EXTENSIONS[manifest.plan.language.primary]
    runner_path = scripts_dir / f"run_adapter.{ext}"
    runner_path.write_text(render_runner(manifest), encoding="utf-8")

    verify_path = scripts_dir / f"verify_result.{ext}"
    verify_path.write_text(render_verify(manifest), encoding="utf-8")

    plan_path = output_dir / "PLAN.md"
    plan_path.write_text(render_plan(manifest), encoding="utf-8")

    return [manifest_path, skill_path, runner_path, verify_path, plan_path]


def render_skill(manifest: HarnessManifest) -> str:
    lang = manifest.plan.language.primary
    actions = "\n".join(f"- `{action}`" for action in manifest.plan.suggested_actions)
    verification = "\n".join(
        f"- {line}" for line in summarize_contracts(manifest.detection, manifest.plan)
    )
    return f"""---
name: "omnicontrol-{manifest.slug}"
description: "Capability-first adapter scaffold for {manifest.display_name}"
---

# OmniControl Skill for {manifest.display_name}

## Detection Summary

- Target: `{manifest.detection.target}`
- Platform: `{manifest.detection.platform}`
- Target kind: `{manifest.detection.target_kind}`
- Primary adapter: `{manifest.plan.primary_adapter}`
- Primary language: `{lang}`
- Fallback adapters: `{", ".join(manifest.plan.fallback_adapters) or "none"}`

## Suggested Actions

{actions}

## Verification

{verification}

## Generated Files

- `manifest.json`
- `PLAN.md`
- `scripts/run_adapter.{LANGUAGE_EXTENSIONS[lang]}`
- `scripts/verify_result.{LANGUAGE_EXTENSIONS[lang]}`
"""


def render_plan(manifest: HarnessManifest) -> str:
    ranking_lines = "\n".join(
        f"- `{option.language}`: {option.score:.2f} - {'; '.join(option.reasons[:2])}"
        for option in manifest.plan.language.ranking
    )
    capability_lines = "\n".join(
        f"- `{capability.name}` ({capability.confidence:.2f}): {'; '.join(capability.reasons[:2])}"
        for capability in manifest.detection.capabilities
    )
    return f"""# OmniControl Plan

## Target

- Input: `{manifest.detection.target}`
- Display name: `{manifest.display_name}`
- Target type: `{manifest.detection.target_type}`
- Target kind: `{manifest.detection.target_kind}`
- Platform: `{manifest.detection.platform}`

## Capabilities

{capability_lines}

## Plan

- Primary adapter: `{manifest.plan.primary_adapter}`
- Fallback adapters: `{", ".join(manifest.plan.fallback_adapters) or "none"}`
- State model: `{manifest.plan.state_model}`
- Verification methods: `{", ".join(manifest.plan.verification_methods)}`

## Language Decision

{ranking_lines}
"""


def render_runner(manifest: HarnessManifest) -> str:
    language = manifest.plan.language.primary
    target = manifest.detection.target.replace("\\", "\\\\")
    adapter = manifest.plan.primary_adapter
    action = manifest.plan.suggested_actions[0]

    if language == "python":
        return f"""#!/usr/bin/env python3
import json
import sys

action = sys.argv[1] if len(sys.argv) > 1 else "{action}"
payload = {{
    "target": "{target}",
    "adapter": "{adapter}",
    "language": "python",
    "action": action,
    "status": "stub",
    "next_step": "Replace this template with real adapter logic.",
}}
print(json.dumps(payload, indent=2))
"""
    if language == "powershell":
        return f"""param(
    [string]$Action = "{action}"
)

$payload = [ordered]@{{
    target = "{target}"
    adapter = "{adapter}"
    language = "powershell"
    action = $Action
    status = "stub"
    next_step = "Replace this template with real adapter logic."
}}

$payload | ConvertTo-Json -Depth 4
"""
    if language == "bash":
        return f"""#!/usr/bin/env bash
ACTION="${{1:-{action}}}"
printf '%s\n' '{{' \
  '  "target": "{target}",' \
  '  "adapter": "{adapter}",' \
  '  "language": "bash",' \
  "  \\\"action\\\": \\\"${{ACTION}}\\\"," \
  '  "status": "stub",' \
  '  "next_step": "Replace this template with real adapter logic."' \
  '}}'
"""
    if language in {"javascript", "typescript"}:
        runtime_name = language
        return f"""#!/usr/bin/env node
const action = process.argv[2] ?? "{action}";
const payload = {{
  target: "{target}",
  adapter: "{adapter}",
  language: "{runtime_name}",
  action,
  status: "stub",
  nextStep: "Replace this template with real adapter logic.",
}};

console.log(JSON.stringify(payload, null, 2));
"""
    if language == "applescript":
        return """on run argv
    set actionName to "{action}"
    if (count of argv) > 0 then
        set actionName to item 1 of argv
    end if

    set payload to "{{" & ¬
        "\\"target\\":\\"{target}\\"," & ¬
        "\\"adapter\\":\\"{adapter}\\"," & ¬
        "\\"language\\":\\"applescript\\"," & ¬
        "\\"action\\":\\"" & actionName & "\\"," & ¬
        "\\"status\\":\\"stub\\"," & ¬
        "\\"next_step\\":\\"Replace this template with real adapter logic.\\"" & ¬
        "}}"
    return payload
end run
""".format(action=action, target=target, adapter=adapter)
    return f"""using System;

public static class Program
{{
    public static void Main(string[] args)
    {{
        var action = args.Length > 0 ? args[0] : "{action}";
        Console.WriteLine($"{{{{\\\"target\\\":\\\"{target}\\\",\\\"adapter\\\":\\\"{adapter}\\\",\\\"language\\\":\\\"csharp\\\",\\\"action\\\":\\\"{{action}}\\\",\\\"status\\\":\\\"stub\\\",\\\"next_step\\\":\\\"Replace this template with real adapter logic.\\\"}}}}");
    }}
}}
"""


def render_verify(manifest: HarnessManifest) -> str:
    language = manifest.plan.language.primary
    methods = manifest.plan.verification_methods

    if language == "python":
        method_list = ", ".join(f'"{item}"' for item in methods)
        return f"""#!/usr/bin/env python3
import json

checks = [{method_list}]
print(json.dumps({{"checks": checks, "status": "stub"}}, indent=2))
"""
    if language == "powershell":
        method_list = ", ".join(f'"{item}"' for item in methods)
        return f"""$checks = @({method_list})
[ordered]@{{
    checks = $checks
    status = "stub"
}} | ConvertTo-Json -Depth 4
"""
    if language in {"javascript", "typescript"}:
        method_list = ", ".join(f'"{item}"' for item in methods)
        return f"""#!/usr/bin/env node
console.log(JSON.stringify({{ checks: [{method_list}], status: "stub", language: "{language}" }}, null, 2));
"""
    if language == "bash":
        return """#!/usr/bin/env bash
echo '{"checks": ["command_exit"], "status": "stub"}'
"""
    if language == "applescript":
        return """on run argv
    return "{""checks"": [""ui_object""], ""status"": ""stub""}"
end run
"""
    return """using System;

public static class Program
{
    public static void Main()
    {
        Console.WriteLine("{\\\"checks\\\": [\\\"backend_query\\\"], \\\"status\\\": \\\"stub\\\"}");
    }
}
"""
