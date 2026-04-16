const fs = require("node:fs/promises");
const path = require("node:path");
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
  const preferTitle = args["prefer-title-contains"] ?? "";
  const mode = args.mode ?? "observe";
  const writeTitle = args["write-title"] ?? "";
  const writeMarker = args["write-marker"] ?? "";

  if (!port || !outputDir) {
    throw new Error("Expected --port and --output-dir");
  }

  await fs.mkdir(outputDir, { recursive: true });
  const target = await waitForInspectableTarget(`http://127.0.0.1:${port}`, preferTitle);

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

    if (mode === "write") {
      await send("Runtime.evaluate", {
        expression: `
          window.__omniWrite = ${JSON.stringify(writeMarker)};
          document.title = ${JSON.stringify(writeTitle)};
          JSON.stringify({title: document.title, href: location.href, marker: window.__omniWrite});
        `,
        returnByValue: true,
      });
    }

    const readBack = await send("Runtime.evaluate", {
      expression: "JSON.stringify({title: document.title, href: location.href, marker: window.__omniWrite || null})",
      returnByValue: true,
    });
    const data = JSON.parse(readBack.result.value);

    console.log(JSON.stringify({
      status: "ok",
      target_title: target.title,
      target_url: target.url,
      evaluated_title: data.title,
      evaluated_href: data.href,
      marker: data.marker,
    }, null, 2));
  } finally {
    socket.close();
  }
}

main().catch((error) => {
  console.log(JSON.stringify({ status: "error", error: error.message }, null, 2));
  process.exitCode = 1;
});
