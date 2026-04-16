param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$result = [ordered]@{
    status = "error"
    output = $OutputPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$existing = @()
$ai = $null

try {
    $existing = @(Get-Process | Where-Object { $_.ProcessName -like 'Illustrator*' })
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPath)
    $jsPath = $OutputPath.Replace('\', '/')
    $jsx = @"
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var doc = app.documents.add();
var text = doc.textFrames.add();
text.contents = 'OmniControl Illustrator Smoke';
text.top = 200;
text.left = 80;
var rect = doc.pathItems.rectangle(260, 40, 240, 120);
var color = new RGBColor();
color.red = 20; color.green = 120; color.blue = 220;
rect.filled = true;
rect.fillColor = color;
var target = new File('$jsPath');
var opts = new ExportOptionsSVG();
opts.embedRasterImages = true;
doc.exportFile(target, ExportType.SVG, opts);
doc.close(SaveOptions.DONOTSAVECHANGES);
target.fsName;
"@

    $ai = New-Object -ComObject Illustrator.Application
    $scriptResult = $ai.DoJavaScript($jsx)

    if (-not (Test-Path -LiteralPath $OutputPath)) {
        throw "Illustrator output file was not created."
    }

    $head = Get-Content -LiteralPath $OutputPath -TotalCount 5
    $svgOk = ($head -join "`n") -match '<svg'
    $result.status = "ok"
    $result.output = $OutputPath
    $result.exists = $true
    $result.size = (Get-Item -LiteralPath $OutputPath).Length
    $result.svg_ok = [bool]$svgOk
    $result.script_result = $scriptResult
    $result.attached_existing_app = ($existing.Count -gt 0)
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
    if ($ai -ne $null) {
        if ($existing.Count -eq 0) {
            try { $ai.Quit() } catch {}
        }
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($ai) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$result | ConvertTo-Json -Depth 6
