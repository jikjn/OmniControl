param(
    [Parameter(Mandatory = $true)]
    [string]$SourceCad,
    [Parameter(Mandatory = $true)]
    [string]$CadViewerPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$result = [ordered]@{
    status = "error"
    source = $SourceCad
    app = $CadViewerPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$proc = $null

try {
    if (-not (Test-Path -LiteralPath $SourceCad)) {
        throw "Source CAD file not found: $SourceCad"
    }
    if (-not (Test-Path -LiteralPath $CadViewerPath)) {
        throw "CadViewer app not found: $CadViewerPath"
    }
    $null = New-Item -ItemType Directory -Force -Path $OutputDir

    $proc = Start-Process -FilePath $CadViewerPath -ArgumentList @($SourceCad) -PassThru
    Start-Sleep -Seconds 5

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $cond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
        $proc.Id
    )
    $window = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
    if ($null -eq $window) {
        throw "CadViewer window not found."
    }

    $result.status = "ok"
    $result.window_name = $window.Current.Name
    $result.window_class = $window.Current.ClassName
    $result.window_handle = $window.Current.NativeWindowHandle
    $result.window_pid = $window.Current.ProcessId
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    if ($proc -and -not $proc.HasExited) {
        try { $proc.CloseMainWindow() | Out-Null } catch {}
        Start-Sleep -Milliseconds 500
        if (-not $proc.HasExited) {
            try { Stop-Process -Id $proc.Id -Force } catch {}
        }
    }
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
}

$result | ConvertTo-Json -Depth 6
