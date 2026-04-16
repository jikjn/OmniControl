const fs = require("node:fs/promises");
const { waitForInspectableTarget } = require("./cdp_target_helpers.js");

function parseArgs(argv) {
  const parsed = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) continue;
    parsed[arg.slice(2)] = argv[i + 1];
    i += 1;
  }
  return parsed;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const port = Number(args.port);
  const outputDir = args["output-dir"];
  const workflowPath = args["workflow-path"];
  const preferTitle = args["prefer-title-contains"] ?? "";
  if (!port || !outputDir || !workflowPath) {
    throw new Error("Expected --port, --output-dir and --workflow-path");
  }

  await fs.mkdir(outputDir, { recursive: true });
  const workflow = JSON.parse(await fs.readFile(workflowPath, "utf8"));
  const target = await waitForInspectableTarget(`http://127.0.0.1:${port}`, preferTitle, 30000, 250, false);

  const socket = new WebSocket(target.webSocketDebuggerUrl);
  let nextId = 1;
  const pending = new Map();

  socket.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data.toString());
    if (!msg.id || !pending.has(msg.id)) return;
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
    else resolve(msg.result);
  });

  function send(method, params = {}) {
    const id = nextId++;
    socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
  }

  try {
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve, { once: true });
      socket.addEventListener("error", reject, { once: true });
    });
    await send("Runtime.enable");

    const stepResults = [];
    let requiredStepsTotal = 0;
    let requiredStepsOk = 0;
    let lastTitle = null;
    let lastMarker = null;

    for (const step of workflow.steps) {
      let expression = "";
      if (step.kind === "set") {
        expression = `
          document.title = ${JSON.stringify(step.title ?? "")};
          window.__omniMarker = ${JSON.stringify(step.marker ?? null)};
          JSON.stringify({title: document.title, marker: window.__omniMarker, href: location.href});
        `;
      } else if (step.kind === "eval") {
        expression = step.expression;
      } else {
        throw new Error(`Unsupported workflow step kind: ${step.kind}`);
      }

      const result = await send("Runtime.evaluate", {
        expression,
        returnByValue: true,
      });
      const data = JSON.parse(result.result.value);
      lastTitle = data.title ?? lastTitle;
      lastMarker = data.marker ?? lastMarker;
      let ok = true;
      if (step.expect_title !== undefined) ok = ok && data.title === step.expect_title;
      if (step.expect_marker !== undefined) ok = ok && data.marker === step.expect_marker;
      if (step.required) {
        requiredStepsTotal += 1;
        if (ok) requiredStepsOk += 1;
      }
      stepResults.push({
        name: step.name,
        kind: step.kind,
        required: Boolean(step.required),
        ok,
        title: data.title,
        marker: data.marker,
        href: data.href,
      });
    }

    console.log(JSON.stringify({
      status: requiredStepsTotal === requiredStepsOk ? "ok" : "partial",
      target_title: target.title,
      target_url: target.url,
      target_selection_attempts: target.__omniSelectionAttempts ?? null,
      target_prefer_matched: target.__omniPreferMatched ?? null,
      step_results: stepResults,
      required_steps_total: requiredStepsTotal,
      required_steps_ok: requiredStepsOk,
      all_required_steps_ok: requiredStepsTotal === requiredStepsOk,
      last_title: lastTitle,
      last_marker: lastMarker,
    }, null, 2));
  } finally {
    socket.close();
  }
}

main().catch((error) => {
  console.log(JSON.stringify({ status: "error", error: error.message }, null, 2));
  process.exitCode = 1;
});
