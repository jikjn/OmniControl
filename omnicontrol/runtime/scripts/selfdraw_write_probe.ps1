param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [Parameter(Mandatory = $true)]
    [string]$WindowClass,
    [Parameter(Mandatory = $true)]
    [string]$InputSequence,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$SourceArg,
    [int]$LaunchWaitSeconds = 5,
    [int]$PostInputWaitSeconds = 1
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
public static class OmniWin32Probe {
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

$result = [ordered]@{
    status = "error"
    executable = $ExecutablePath
    window_class = $WindowClass
    input_sequence = $InputSequence
}

$proc = $null
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        throw "Executable not found: $ExecutablePath"
    }
    if ($SourceArg -and -not (Test-Path -LiteralPath $SourceArg)) {
        throw "Source argument path not found: $SourceArg"
    }

    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    $args = @()
    if ($SourceArg) { $args += $SourceArg }
    $proc = Start-Process -FilePath $ExecutablePath -ArgumentList $args -PassThru
    Start-Sleep -Seconds $LaunchWaitSeconds

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $cond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ClassNameProperty,
        $WindowClass
    )
    $window = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
    if ($null -eq $window) {
        throw "Target window not found."
    }

    $hwnd = [IntPtr]$window.Current.NativeWindowHandle
    [OmniWin32Probe]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 500

    $rect = New-Object OmniWin32Probe+RECT
    [OmniWin32Probe]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -le 0 -or $height -le 0) {
        throw "Invalid window bounds."
    }

    $centerX = [int]($rect.Left + ($width / 2))
    $centerY = [int]($rect.Top + ($height / 2))
    [OmniWin32Probe]::SetCursorPos($centerX, $centerY) | Out-Null
    Start-Sleep -Milliseconds 100
    [OmniWin32Probe]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    [OmniWin32Probe]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 300

    $beforePath = Join-Path $OutputDir 'before.png'
    $afterPath = Join-Path $OutputDir 'after.png'

    $bmp1 = New-Object System.Drawing.Bitmap $width, $height
    $g1 = [System.Drawing.Graphics]::FromImage($bmp1)
    $g1.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp1.Size)
    $bmp1.Save($beforePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g1.Dispose()

    [System.Windows.Forms.SendKeys]::SendWait($InputSequence)
    Start-Sleep -Seconds $PostInputWaitSeconds

    $bmp2 = New-Object System.Drawing.Bitmap $width, $height
    $g2 = [System.Drawing.Graphics]::FromImage($bmp2)
    $g2.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp2.Size)
    $bmp2.Save($afterPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g2.Dispose()

    $bytes1 = [System.IO.File]::ReadAllBytes($beforePath)
    $bytes2 = [System.IO.File]::ReadAllBytes($afterPath)
    $same = ($bytes1.Length -eq $bytes2.Length)
    if ($same) {
        for ($i = 0; $i -lt $bytes1.Length; $i++) {
            if ($bytes1[$i] -ne $bytes2[$i]) {
                $same = $false
                break
            }
        }
    }

    $result.status = "ok"
    $result.window_name = $window.Current.Name
    $result.window_handle = $window.Current.NativeWindowHandle
    $result.before = $beforePath
    $result.after = $afterPath
    $result.images_equal = $same
    $result.visual_changed = (-not $same)
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
