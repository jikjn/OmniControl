param(
    [Parameter(Mandatory = $true)]
    [string]$Query,
    [Parameter(Mandatory = $true)]
    [string]$EverythingPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$result = [ordered]@{
    status = "error"
    query = $Query
    everything_path = $EverythingPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    if (-not (Test-Path -LiteralPath $EverythingPath)) {
        throw "Everything.exe not found: $EverythingPath"
    }

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $classCond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ClassNameProperty,
        'EVERYTHING'
    )

    $before = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $classCond)
    $beforeHandles = @()
    for ($i = 0; $i -lt $before.Count; $i++) {
        $beforeHandles += $before.Item($i).Current.NativeWindowHandle
    }

    Start-Process -FilePath $EverythingPath -ArgumentList @('-new-window', '-search', $Query) | Out-Null
    Start-Sleep -Seconds 2

    $after = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $classCond)
    $window = $null
    for ($i = 0; $i -lt $after.Count; $i++) {
        $candidate = $after.Item($i)
        if ($beforeHandles -notcontains $candidate.Current.NativeWindowHandle) {
            $window = $candidate
            break
        }
    }

    if ($null -eq $window) {
        throw "New Everything search window not found."
    }

    $children = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    $named = @()
    for ($i = 0; $i -lt $children.Count; $i++) {
        $child = $children.Item($i)
        if ($child.Current.Name) {
            $named += [ordered]@{
                name = $child.Current.Name
                automation_id = $child.Current.AutomationId
                control_type = $child.Current.ControlType.ProgrammaticName
            }
        }
    }

    $statusText = $null
    foreach ($item in $named) {
        if ($item.automation_id -eq '10010') {
            $statusText = $item.name
            break
        }
    }
    if ($null -eq $statusText -and $named.Count -gt 0) {
        $statusText = $named[$named.Count - 1].name
    }

    $matchNames = @()
    foreach ($item in $named) {
        if ($item.name -ne $statusText) {
            $matchNames += $item.name
        }
    }

    try {
        $windowPattern = $window.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern)
        $windowPattern.Close()
    } catch {}

    $result.status = "ok"
    $result.window_handle = $window.Current.NativeWindowHandle
    $result.window_name = $window.Current.Name
    $result.status_text = $statusText
    $result.matches = $matchNames
    $result.match_count = $matchNames.Count
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
}

$result | ConvertTo-Json -Depth 6
