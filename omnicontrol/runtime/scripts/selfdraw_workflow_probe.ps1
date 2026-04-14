param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [Parameter(Mandatory = $true)]
    [string]$WindowClass,
    [Parameter(Mandatory = $true)]
    [string]$WorkflowPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$SourceArg,
    [int]$LaunchWaitSeconds = 5
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class OmniWorkflowWin32 {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
'@

$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004

function Save-Screen([int]$x, [int]$y, [int]$w, [int]$h, [string]$path) {
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
}

function Files-Differ([string]$a, [string]$b) {
    $bytes1 = [System.IO.File]::ReadAllBytes($a)
    $bytes2 = [System.IO.File]::ReadAllBytes($b)
    if ($bytes1.Length -ne $bytes2.Length) { return $true }
    for ($i = 0; $i -lt $bytes1.Length; $i++) {
        if ($bytes1[$i] -ne $bytes2[$i]) { return $true }
    }
    return $false
}

$result = [ordered]@{
    status = "error"
    executable = $ExecutablePath
    window_class = $WindowClass
    workflow_path = $WorkflowPath
}

$proc = $null
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $workflow = Get-Content $WorkflowPath -Raw | ConvertFrom-Json
    $null = New-Item -ItemType Directory -Force -Path $OutputDir

    $args = @()
    if ($SourceArg) { $args += $SourceArg }
    $proc = Start-Process -FilePath $ExecutablePath -ArgumentList $args -PassThru
    Start-Sleep -Seconds $LaunchWaitSeconds

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, $WindowClass)
    $window = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
    if ($null -eq $window) { throw "Target window not found." }

    $hwnd = [IntPtr]$window.Current.NativeWindowHandle
    [OmniWorkflowWin32]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 500
    $rect = New-Object OmniWorkflowWin32+RECT
    [OmniWorkflowWin32]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top

    $centerX = [int]($rect.Left + ($width / 2))
    $centerY = [int]($rect.Top + ($height / 2))
    [OmniWorkflowWin32]::SetCursorPos($centerX, $centerY) | Out-Null
    Start-Sleep -Milliseconds 100
    [OmniWorkflowWin32]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    [OmniWorkflowWin32]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 300

    $stepResults = @()
    $requiredTotal = 0
    $requiredChanged = 0
    foreach ($step in $workflow.steps) {
        $stepDir = Join-Path $OutputDir $step.name
        New-Item -ItemType Directory -Force -Path $stepDir | Out-Null
        $before = Join-Path $stepDir 'before.png'
        $after = Join-Path $stepDir 'after.png'
        Save-Screen $rect.Left $rect.Top $width $height $before
        [System.Windows.Forms.SendKeys]::SendWait($step.sequence)
        $waitMs = 1000
        if ($null -ne $step.wait_ms) {
            $waitMs = [int]$step.wait_ms
        }
        Start-Sleep -Milliseconds $waitMs
        Save-Screen $rect.Left $rect.Top $width $height $after
        $changed = Files-Differ $before $after
        if ($step.required) {
            $requiredTotal += 1
            if ($changed) { $requiredChanged += 1 }
        }
        $stepResults += [ordered]@{
            name = $step.name
            sequence = $step.sequence
            required = [bool]$step.required
            changed = [bool]$changed
            before = $before
            after = $after
        }
    }

    $result.status = if ($requiredChanged -eq $requiredTotal) { 'ok' } else { 'partial' }
    $result.window_name = $window.Current.Name
    $result.window_handle = $window.Current.NativeWindowHandle
    $result.step_results = $stepResults
    $result.required_steps_total = $requiredTotal
    $result.required_steps_changed = $requiredChanged
    $result.all_required_steps_changed = ($requiredChanged -eq $requiredTotal)
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

$result | ConvertTo-Json -Depth 8
