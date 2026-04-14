# Background-First Policy

## Goal

For closed-source desktop software, OmniControl should prefer control planes that:

1. run without taking foreground focus,
2. minimize interference with the user's active session,
3. get faster over time by learning successful launch and command paths.

This policy is stricter than "just make it work". A foreground-only automation path is a last resort, not the default.

## Preferred Control Plane Order

When multiple control planes are available for the same product, prefer them in this order:

1. `tooling`
2. `existing_cli`
3. `private_protocol`
4. `vendor_command`
5. `network_api`
6. `native_script`
7. `plugin`
8. `api`
9. `service`
10. `cdp`
11. `uiautomation`
12. `vision`

Interpretation:

- `private_protocol`, `vendor_command`, `network_api`, and `service` are usually the best background-capable paths for closed-source software.
- `cdp` is acceptable when the app is Electron/Chromium based and the debugging path does not steal focus.
- `uiautomation` and `vision` are fallback planes. They are often slower, more fragile, and more disruptive.

## No-Focus Rule

Default behavior:

- Do not promote a focus-based path when a background-capable path exists.
- Do not switch to `uiautomation` or `vision` just because it is easy to prototype.
- Do not treat page navigation plus visible clicking as a "background" solution.
- Do not take screenshots or rely on visual capture when window titles, process state, protocol responses or other non-visual evidence are sufficient.

Allowed exceptions:

- The user explicitly asks for a temporary foreground fallback.
- All background-capable paths are blocked and the remaining goal is urgent.
- The attempt is marked as diagnostic evidence collection, not a preferred solution.

## Learning Rules

Successful runs should store reusable execution preferences in the knowledge base:

- startup strategy,
- isolated profile requirements,
- attach-existing preference,
- preferred vendor command method order.

Once a product has a verified background path, later runs should try that path first.

## Closed-Source Guidance

For closed-source products, spend effort in this order:

1. discover vendor protocol / IPC / hidden API,
2. discover browser-shell bridge or local HTTP service,
3. discover reusable startup and attach rules,
4. use focus-based UI fallback only if the above fail.

This keeps future integrations faster and reduces user disruption.
