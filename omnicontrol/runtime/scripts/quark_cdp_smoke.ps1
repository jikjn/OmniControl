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
    if (-not (Test-Path -LiteralPath $QuarkPath)) {
        throw "Quark executable not found: $QuarkPath"
    }
    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    Get-Process | Where-Object { $_.ProcessName -like 'quark*' } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    $port = Get-Random -Minimum 45000 -Maximum 45999
    $proc = Start-Process -FilePath $QuarkPath -ArgumentList @("--remote-debugging-port=$port", "--remote-debugging-address=127.0.0.1") -PassThru
    Start-Sleep -Seconds 12

    $versionJson = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/json/version" | Select-Object -ExpandProperty Content
    $targetsJson = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/json/list" | Select-Object -ExpandProperty Content
    $targetsPath = Join-Path $OutputDir 'targets.json'
    Set-Content -Path $targetsPath -Value $targetsJson -Encoding UTF8

    $env:QUARK_TARGETS = $targetsJson
    $probe = @'
const targets = JSON.parse(process.env.QUARK_TARGETS);
const target = targets.find(t => t.title.includes("夸克网盘") && t.webSocketDebuggerUrl)
  || targets.find(t => t.type === "page" && t.webSocketDebuggerUrl);
if (!target) { throw new Error("No target found"); }
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
  const evalResult = await send("Runtime.evaluate", {
    expression: "JSON.stringify({title: document.title, href: location.href})",
    returnByValue: true
  });
  const data = JSON.parse(evalResult.result.value);
  console.log(JSON.stringify({
    target_title: target.title,
    target_url: target.url,
    evaluated_title: data.title,
    evaluated_href: data.href
  }));
  socket.close();
})().catch(err => {
  console.error(err.message);
  process.exit(1);
});
'@
    $probeOutput = $probe | node -
    Remove-Item Env:QUARK_TARGETS -ErrorAction SilentlyContinue

    $probeData = $probeOutput | ConvertFrom-Json
    $versionData = $versionJson | ConvertFrom-Json

    $result.status = "ok"
    $result.port = $port
    $result.browser = $versionData.Browser
    $result.protocol = $versionData.'Protocol-Version'
    $result.target_title = $probeData.target_title
    $result.target_url = $probeData.target_url
    $result.evaluated_title = $probeData.evaluated_title
    $result.evaluated_href = $probeData.evaluated_href
    $result.targets_path = $targetsPath
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
