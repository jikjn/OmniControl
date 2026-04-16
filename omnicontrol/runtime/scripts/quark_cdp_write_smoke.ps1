param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [Parameter(Mandatory = $true)]
    [string]$QuarkPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$result = [ordered]@{
    status = "error"
    app = $QuarkPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$proc = $null

try {
    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    Get-Process | Where-Object { $_.ProcessName -like 'quark*' } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $port = Get-Random -Minimum 45000 -Maximum 45999
    $proc = Start-Process -FilePath $QuarkPath -ArgumentList @("--remote-debugging-port=$port", "--remote-debugging-address=127.0.0.1") -PassThru
    Start-Sleep -Seconds 12
    $targetsJson = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/json/list" | Select-Object -ExpandProperty Content
    $env:QUARK_TARGETS = $targetsJson
    $probe = @'
const targets = JSON.parse(process.env.QUARK_TARGETS);
const target = targets.find(t => t.title.includes("夸克网盘") && t.webSocketDebuggerUrl)
  || targets.find(t => t.type === "page" && t.webSocketDebuggerUrl);
if (!target) throw new Error("No target found");
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
(async () => {
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  await send("Runtime.enable");
  await send("Runtime.evaluate", {
    expression: "window.__omniWrite='ok'; document.title='OmniControl Quark Write'; JSON.stringify({title: document.title, marker: window.__omniWrite, href: location.href})",
    returnByValue: true
  });
  const readBack = await send("Runtime.evaluate", {
    expression: "JSON.stringify({title: document.title, marker: window.__omniWrite, href: location.href})",
    returnByValue: true
  });
  console.log(readBack.result.value);
  socket.close();
})().catch(err => { console.error(err.message); process.exit(1); });
'@
    $probeOutput = $probe | node -
    Remove-Item Env:QUARK_TARGETS -ErrorAction SilentlyContinue
    $probeData = $probeOutput | ConvertFrom-Json

    $result.status = "ok"
    $result.port = $port
    $result.title = $probeData.title
    $result.marker = $probeData.marker
    $result.href = $probeData.href
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    if ($proc -and -not $proc.HasExited) {
        try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
    Get-Process | Where-Object { $_.ProcessName -like 'quark*' } | Stop-Process -Force -ErrorAction SilentlyContinue
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
}

$result | ConvertTo-Json -Depth 6
