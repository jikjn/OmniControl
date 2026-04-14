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
  const label = args.label ?? "desktop-cdp";
  if (!port || !outputDir) {
    throw new Error("Expected --port and --output-dir");
  }

  await fs.mkdir(outputDir, { recursive: true });
  const version = await fetch(`http://127.0.0.1:${port}/json/version`).then((response) => response.json());
  const target = await waitForInspectableTarget(`http://127.0.0.1:${port}`);

  const socket = new WebSocket(target.webSocketDebuggerUrl);
  let nextId = 1;
  const pending = new Map();

  const opened = new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data.toString());
    if (!message.id || !pending.has(message.id)) {
      return;
    }
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) {
      reject(new Error(message.error.message || JSON.stringify(message.error)));
    } else {
      resolve(message.result);
    }
  });

  function send(method, params = {}) {
    const id = nextId += 1;
    socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
    });
  }

  try {
    await opened;
    await send("Page.enable");
    await send("Runtime.enable");
    const evaluated = await send("Runtime.evaluate", {
      expression: "JSON.stringify({title: document.title, href: location.href, bodyText: document.body ? document.body.innerText.slice(0, 500) : ''})",
      returnByValue: true,
    });
    const page = JSON.parse(evaluated.result.value);
    const screenshot = await send("Page.captureScreenshot", { format: "png" });
    const screenshotPath = path.join(outputDir, `${label}.png`);
    await fs.writeFile(screenshotPath, Buffer.from(screenshot.data, "base64"));

    console.log(JSON.stringify({
      status: "ok",
      browser: version.Browser,
      protocol: version["Protocol-Version"],
      target_title: target.title,
      target_url: target.url,
      evaluated_title: page.title,
      evaluated_href: page.href,
      body_text: page.bodyText,
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
