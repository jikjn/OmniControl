# Generic Background Transports

## Goal

Closed-source desktop software should not be integrated one product at a time with ad hoc foreground automation.

OmniControl should instead treat background control as a transport problem:

1. discover candidate transports,
2. rank them by background safety and determinism,
3. probe the cheapest ones,
4. execute them in order,
5. learn the winning path for future runs.

## Transport Model

Each candidate transport should be described with the following properties:

- `name`
- `control_plane`
- `background_safe`
- `requires_focus`
- `startup_cost`
- `probe_cost`
- `determinism`
- `observability`
- `side_effect_risk`

These fields are enough to rank transports without product-specific heuristics.

## Ranking Rule

Default background-first ranking prefers:

1. no focus requirement,
2. background-safe transports,
3. low side-effect risk,
4. low startup cost,
5. low probe cost,
6. high determinism,
7. high observability.

Learned successful methods override the default order, but only within the discovered candidate set.

## Common Transport Families

Typical families for closed-source desktop software:

- `private_protocol`
  Examples: hidden window messages, tagged packet IPC, `WM_COPYDATA`, undocumented local bridges.
- `vendor_command`
  Examples: vendor XML bridge, private command method, local COM command.
- `network_api`
  Examples: localhost HTTP/WS service, embedded browser data endpoint.
- `service`
  Examples: background daemon or helper process with stable IPC.
- `cdp`
  Electron/Chromium apps with stable debugging attachment.
- `native_script`
  Official scripting host, COM automation, AppleScript, SDK entrypoint.
- `uiautomation`
  Accessibility/UIA only when no stronger background path exists.
- `vision`
  Last-resort fallback.

- `private_protocol`
  Examples: hidden helper window, `WM_COPYDATA`, tagged packet header, vendor URI handoff.

## Windows Private Protocol Pattern

Many Windows closed-source apps expose a background-only helper process or hidden window instead of a public API.

Common shape:

1. discover a stable hidden window class or title,
2. discover a packet header contract,
3. send a typed payload through `WM_COPYDATA`,
4. classify responses by timeout / result code / window state change.

Typical packet shape:

- `total_length`
- `tag`
- `version`
- `proto_type`
- `payload`

The project should treat this as a reusable transport family, not as a one-off hack for a single product.

## Execution Pattern

Recommended pattern per profile:

1. collect candidate transports,
2. rank them with the generic ranking rule,
3. run a cheap probe if available,
4. attempt execution in ranked order,
5. store:
   - ordered methods tried,
   - probe output,
   - winning method,
   - required launch overrides.

Recommended learned override keys:

- `preferred_transport_order`
- `preferred_transport_variants`
- `preferred_method_order`
- `preferred_strategy`
- `allow_attach_existing`
- `use_isolated_user_data`

## What This Solves

This design makes the project reusable across products:

- the ranking rule is generic,
- the attempt runner is generic,
- the learning path is generic,
- only the transport discovery and payload construction remain product-specific.

That is the minimum surface area needed to keep closed-source integrations fast and low-disruption over time.

## Windows Private Protocol Helper

For Windows apps that expose hidden message windows instead of public APIs, prefer a reusable helper instead of product-specific ad hoc code.

Current helper module:

- [windows_ipc.py](/C:/Users/33032/Downloads/OmniControl/omnicontrol/runtime/windows_ipc.py:1)

This module is intended to cover recurring patterns such as:

- UTF-16LE string payloads,
- tagged packet headers,
- `WM_COPYDATA` delivery,
- hidden class/title based window discovery.
