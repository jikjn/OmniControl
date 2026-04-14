# Sidecar Control Plane Update

Date: `2026-04-13`

## What Changed

OmniControl now treats a verified secondary control plane as a first-class outcome for heavy vendor runtimes.

- `nx-diagnose` no longer stops at "journal path blocked".
  - Primary path is still blocked by `UFUN initialization failed` and `license port 28000 is not listening`.
  - Secondary path `ugiicmd.bat + env_print.exe -n` now succeeds.
  - Result status is now `partial` instead of pure `blocked`.
- `isight-diagnose` no longer stops at "contents/logon blocked".
  - Primary path is still blocked by connection-profile and DSLS issues.
  - Secondary path `fiperenv.bat + fipercmd.bat help` now succeeds.
  - Result status is now `partial` instead of pure `blocked`.

## Framework Change

Pivoted `partial` results now keep the original blockers attached. This lets the knowledge base learn cases of the form:

- a lighter vendor control plane is executable
- the primary runtime is still blocked

That is materially better than recording a false `ok`, and materially better than collapsing everything back to `blocked`.

The rollout is no longer diagnose-only. Secondary profile sidecars now have two layers:

- explicit profile metadata for high-confidence product-specific siblings
- automatic sibling inference inside a product family, based on interaction level, control-plane weight, and invocation-context compatibility
- accepted invocation contexts per profile, so lighter siblings can explicitly say whether they accept `none`, `source`, `workspace`, `query`, or `url`

That means new profile families no longer need a hand-written pair every time before they can participate in sidecar fallback, and they no longer need to fit only the old `source/workspace` argument model.

Secondary profile sidecars are now declared or inferred through shared helpers, so the same pivot shape can be reused by more profile families:

- `word-workflow -> word-write`
  - The Word family now has a real workflow profile instead of stopping at single-write/export primitives.
- `chrome-form-write -> chrome-cdp`
  - If the write path blocks, OmniControl can still verify the lighter read-only CDP plane and keep the original write blockers attached.
- `chrome-workflow -> chrome-form-write`
  - Chrome now has a workflow-level write profile on top of the existing single-write path.
- `masterpdf-zoom -> masterpdf-pagedown`
  - If the zoom/write probe blocks, OmniControl can pivot to the simpler page-navigation sibling profile against the same PDF source.
- `masterpdf-workflow -> masterpdf-pagedown`
  - Workflow-level failure can now degrade to a lighter sibling profile instead of stopping at a hard `blocked`.
- `ue-python-write -> ue-diagnose`
  - If the project write path blocks, OmniControl can pivot to the lighter UE diagnostic plane and keep the original write blockers attached.
- `trae-cdp-write -> trae-open`
  - If the CDP write path blocks, OmniControl can still verify the vendor CLI/open plane in an isolated workspace.
- `trae-workflow -> trae-open`
  - Workflow-level CDP failures can now degrade to a verified vendor open plane instead of stopping at pure `blocked`.
- `quark-cdp-write -> quark-cdp`
  - If write semantics fail, OmniControl can still pivot to the lighter observe profile and record that the CDP surface remains reachable.
- `quark-workflow -> quark-cdp-write`
  - Quark now has a workflow-level write profile instead of stopping at a single write probe.
- `cadv-zoom -> cadv-view`
  - If zoom/write verification blocks, OmniControl can still confirm the viewer surface through the lighter open/view profile.
- `cadv-workflow -> cadv-zoom`
  - CadViewer now has a workflow-level profile on top of the existing zoom/write probe.
- `safari-dom-write -> safari-open`
  - The first macOS browser write family is now wired as a write profile plus a lighter open/read sibling.

This keeps the mechanism profile-oriented instead of app-patch-oriented: add a `secondary_profiles` declaration when you need an explicit preference, or let the family-level inference choose a lighter sibling automatically. The pivot planner now also injects both explicit and inferred sidecars directly into pivot candidates, so they are available even when the blocker family would not otherwise propose the same action.

The current metadata surface is now:

- `invocation_context`
  - the primary context shape a profile normally uses
- `accepted_invocation_contexts`
  - all context shapes the profile can accept when reused as a sidecar
- `interaction_level`
  - rough heaviness of the action, used to rank lighter sibling profiles

## Verified Outputs

- [NX Diagnose Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/nx-diagnose/result.json)
- [Isight Diagnose Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/isight-diagnose/result.json)
- [Chrome Form Write Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/chrome-form-write/result.json)
- [Trae Workflow Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/trae-workflow/result.json)
- [MasterPDF Workflow Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/masterpdf-workflow/result.json)

Latest real-smoke observations after the generalized rollout:

- `word-workflow`
  - Primary workflow now returns `ok`.
  - The workflow verifies multi-step Word content creation by reading the saved DOCX back and confirming the expected markers exist in `word/document.xml`.
- `chrome-form-write`
  - Normal path still returns `ok`.
  - When forced onto a missing `chrome.exe` path, the profile now pivots to `chrome-cdp` and returns structured `partial` with both the original blocker and the verified sidecar evidence.
- `chrome-workflow`
  - Primary workflow returns `ok`.
- `quark-workflow`
  - Primary workflow returns `ok`.
- `trae-workflow`
  - Primary workflow now returns `ok` again after the generic CDP target-selection fix.
  - The fix is not `Trae`-specific: the workflow/write probes now share a helper that polls `/json/list`, scores inspectable targets, and matches both title and URL instead of doing a one-shot title-only pick.
- `masterpdf-workflow`
  - Primary workflow returns `ok` in the latest run.
- `cadv-workflow`
  - Primary workflow returns `ok`.
- `ue-python-write`
  - The write profile now again finishes as `ok`.
  - The generic pivot planner now prioritizes write-preserving entrypoint pivots such as `drop_project_context` before control-plane-only sidecars, so write profiles do not regress into diagnose-style `partial`.

Windows write/workflow families currently verified to finish as `ok`:

- `word-write`
- `word-workflow`
- `chrome-form-write`
- `chrome-workflow`
- `quark-cdp-write`
- `quark-workflow`
- `trae-cdp-write`
- `trae-workflow`
- `masterpdf-zoom`
- `masterpdf-workflow`
- `cadv-zoom`
- `cadv-workflow`
- `ue-python-write`

macOS integration status after this rollout:

- Planning/detection/scaffold coverage is now verified in-project.
- Runtime profile entrypoints now exist for:
  - `finder-open`
  - `safari-open`
  - `safari-dom-write`
- `benchmark benchmarks/local_closed_source_macos.json --json` passes with:
  - `Finder -> accessibility + applescript`
  - document bypass -> `file_format + python`
  - browser/web -> `cdp + typescript`
- This is real architecture/planning/generation support, not just a claimed platform string.
- Runtime smoke for macOS profiles is implemented and unit-tested, but not yet live-smoke validated on this machine because the current host is Windows.

## Latest Test Run

Command:

```text
python -m unittest discover -s tests -v
python -m omnicontrol benchmark benchmarks\local_closed_source_macos.json --json
```

Result:

- Total tests: `49`
- Total tests: `52`
- Pass rate: `100%`

## Why This Matters

This is not "more retries on the same broken path". It is a different strategy:

- keep the blocked primary path visible
- switch to a lighter vendor-side control plane
- verify that the lighter path is truly executable
- persist that result so later runs can reuse it

## Next Step

The next useful push is no longer "add another recovery hint" or "hardcode one more app-specific recovery chain".

It is:

1. Keep promoting sidecar profiles into richer executable actions inside the same product family.
2. For NX, move from `env_print` toward a lighter vendor command that reveals more structured runtime state without requiring full NXOpen success.
3. For Isight, move from `fipercmd help` toward a local-file or profile-inspection action that does more than enumerate the command surface.
4. Keep enriching profile metadata so family-level inference can make better choices without another hand-written pair.
5. Add more profiles that accept `query` / `url` / optional workspace contexts so future product families can reuse the same sidecar planner without changing runtime code.
