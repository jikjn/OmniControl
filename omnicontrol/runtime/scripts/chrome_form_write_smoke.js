const fs = require("node:fs/promises");
const path = require("node:path");

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

async function waitForVersion(port) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return await response.json();
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("CDP endpoint not ready");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const port = Number(args.port);
  const outputDir = args["output-dir"];
  if (!port || !outputDir) throw new Error("Expected --port and --output-dir");

  await fs.mkdir(outputDir, { recursive: true });
  const version = await waitForVersion(port);
  const socket = new WebSocket(version.webSocketDebuggerUrl);
  let nextId = 1;
  const pending = new Map();
  let sessionId = null;
  let loadResolve = null;

  socket.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data.toString());
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else resolve(msg.result);
      return;
    }
    if (msg.method === "Page.loadEventFired" && msg.sessionId === sessionId && loadResolve) {
      loadResolve();
      loadResolve = null;
    }
  });

  function send(method, params = {}, activeSessionId = null) {
    const id = nextId++;
    const payload = { id, method, params };
    if (activeSessionId) payload.sessionId = activeSessionId;
    socket.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
  }

  try {
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve, { once: true });
      socket.addEventListener("error", reject, { once: true });
    });
    const target = await send("Target.createTarget", { url: "about:blank", background: true });
    const attached = await send("Target.attachToTarget", { targetId: target.targetId, flatten: true });
    sessionId = attached.sessionId;
    await send("Page.enable", {}, sessionId);
    await send("Runtime.enable", {}, sessionId);

    const html = "data:text/html,<title>Form Write</title><textarea id=t></textarea><script>window.__omni='init';</script>";
    const loaded = new Promise((resolve) => { loadResolve = resolve; });
    await send("Page.navigate", { url: html }, sessionId);
    await Promise.race([loaded, new Promise((_, reject) => setTimeout(() => reject(new Error("load timeout")), 10000))]);

    await send("Runtime.evaluate", {
      expression: "document.getElementById('t').value='OmniControl wrote this'; window.__omni='written'; document.title='Form Written';",
      returnByValue: true,
    }, sessionId);
    const readBack = await send("Runtime.evaluate", {
      expression: "JSON.stringify({title: document.title, value: document.getElementById('t').value, marker: window.__omni})",
      returnByValue: true,
    }, sessionId);
    const data = JSON.parse(readBack.result.value);
    const screenshot = await send("Page.captureScreenshot", { format: "png" }, sessionId);
    const screenshotPath = path.join(outputDir, "screenshot.png");
    await fs.writeFile(screenshotPath, Buffer.from(screenshot.data, "base64"));
    await send("Target.closeTarget", { targetId: target.targetId });

    console.log(JSON.stringify({
      status: "ok",
      browser: version.Browser,
      title: data.title,
      textarea_value: data.value,
      marker: data.marker,
      screenshot: screenshotPath,
      screenshot_exists: true,
    }, null, 2));
  } finally {
    socket.close();
  }
}

main().catch((error) => {
  console.log(JSON.stringify({ status: "error", error: error.message }, null, 2));
  process.exitCode = 1;
});
