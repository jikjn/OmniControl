param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [Parameter(Mandatory = $true)]
    [string]$TraeCli
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$result = [ordered]@{
    status = "error"
    workspace = $Workspace
    trae_cli = $TraeCli
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    if (-not (Test-Path -LiteralPath $TraeCli)) {
        throw "Trae CLI not found: $TraeCli"
    }
    if (-not (Test-Path -LiteralPath $Workspace)) {
        throw "Workspace not found: $Workspace"
    }

    Get-Process | Where-Object { $_.ProcessName -like 'Trae*' } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    $userDataDir = Join-Path $OutputDir 'user-data'
    if (Test-Path -LiteralPath $userDataDir) {
        Remove-Item -LiteralPath $userDataDir -Recurse -Force
    }
    $null = New-Item -ItemType Directory -Force -Path $userDataDir

    & $TraeCli -n --user-data-dir $userDataDir $Workspace | Out-Null
    Start-Sleep -Seconds 12

    $processes = @(Get-Process | Where-Object { $_.ProcessName -like 'Trae*' })
    $processIds = $processes | Select-Object -ExpandProperty Id
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    $windowInfo = @()
    for ($i = 0; $i -lt $wins.Count; $i++) {
        $win = $wins.Item($i)
        if ($processIds -contains $win.Current.ProcessId) {
            $windowInfo += [ordered]@{
                name = $win.Current.Name
                class = $win.Current.ClassName
                pid = $win.Current.ProcessId
                hwnd = $win.Current.NativeWindowHandle
            }
        }
    }

    $cmdLines = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'Trae.exe' -and $_.CommandLine -like "*$userDataDir*"
    } | Select-Object ProcessId, CommandLine

    $result.status = "ok"
    $result.user_data_dir = $userDataDir
    $result.user_data_exists = (Test-Path -LiteralPath $userDataDir)
    $result.process_count = $processes.Count
    $result.windows = $windowInfo
    $result.command_lines = $cmdLines
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    Get-Process | Where-Object { $_.ProcessName -like 'Trae*' } | Stop-Process -Force -ErrorAction SilentlyContinue
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
}

$result | ConvertTo-Json -Depth 6
