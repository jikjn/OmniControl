const fs = require("node:fs/promises");
const path = require("node:path");

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) {
      continue;
    }
    parsed[key.slice(2)] = argv[index + 1];
    index += 1;
  }
  return parsed;
}

async function waitForVersion(port) {
  const deadline = Date.now() + 15000;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`CDP endpoint not ready: ${lastError}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const port = Number(args.port);
  const url = args.url;
  const outputDir = args["output-dir"];

  if (!port || !url || !outputDir) {
    throw new Error("Expected --port, --url and --output-dir.");
  }

  await fs.mkdir(outputDir, { recursive: true });
  const version = await waitForVersion(port);
  const socket = new WebSocket(version.webSocketDebuggerUrl);

  let nextId = 1;
  const pending = new Map();
  let sessionId = null;
  let loadResolver = null;

  const openPromise = new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });

  socket.addEventListener("message", async (event) => {
    const message = JSON.parse(event.data.toString());
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        reject(new Error(message.error.message || JSON.stringify(message.error)));
      } else {
        resolve(message.result);
      }
      return;
    }
    if (message.method === "Page.loadEventFired" && message.sessionId === sessionId && loadResolver) {
      loadResolver();
      loadResolver = null;
    }
  });

  function send(method, params = {}, activeSessionId = null) {
    const id = nextId++;
    const payload = { id, method, params };
    if (activeSessionId) {
      payload.sessionId = activeSessionId;
    }
    socket.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
    });
  }

  try {
    await openPromise;
    const target = await send("Target.createTarget", { url: "about:blank", background: true });
    const attached = await send("Target.attachToTarget", {
      targetId: target.targetId,
      flatten: true,
    });
    sessionId = attached.sessionId;
    await send("Page.enable", {}, sessionId);
    await send("Runtime.enable", {}, sessionId);

    const loaded = new Promise((resolve) => {
      loadResolver = resolve;
    });

    await send("Page.navigate", { url }, sessionId);
    await Promise.race([
      loaded,
      new Promise((_, reject) => setTimeout(() => reject(new Error("Timed out waiting for Page.loadEventFired")), 10000)),
    ]);

    const evaluated = await send(
      "Runtime.evaluate",
      {
        expression: "JSON.stringify({title: document.title, href: location.href, bodyText: document.body ? document.body.innerText : ''})",
        returnByValue: true,
      },
      sessionId,
    );

    const pageInfo = JSON.parse(evaluated.result.value);
    const screenshot = await send("Page.captureScreenshot", { format: "png" }, sessionId);
    const screenshotPath = path.join(outputDir, "screenshot.png");
    await fs.writeFile(screenshotPath, Buffer.from(screenshot.data, "base64"));
    await send("Target.closeTarget", { targetId: target.targetId });

    console.log(
      JSON.stringify(
        {
          status: "ok",
          url,
          title: pageInfo.title,
          href: pageInfo.href,
          body_text: pageInfo.bodyText,
          screenshot: screenshotPath,
          screenshot_exists: true,
        },
        null,
        2,
      ),
    );
  } finally {
    socket.close();
  }
}

main().catch((error) => {
  console.log(JSON.stringify({ status: "error", error: error.message }, null, 2));
  process.exitCode = 1;
});
