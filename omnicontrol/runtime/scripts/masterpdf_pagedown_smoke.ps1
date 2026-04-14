param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePdf,
    [Parameter(Mandatory = $true)]
    [string]$MasterPdfPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir
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
public static class Win32Capture {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
}
'@

$result = [ordered]@{
    status = "error"
    source = $SourcePdf
    app = $MasterPdfPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$startedProcess = $null
$windowPid = $null

try {
    if (-not (Test-Path -LiteralPath $SourcePdf)) {
        throw "Source PDF not found: $SourcePdf"
    }
    if (-not (Test-Path -LiteralPath $MasterPdfPath)) {
        throw "MasterPDF.exe not found: $MasterPdfPath"
    }

    $existing = @(Get-Process | Where-Object { $_.Path -like '*MasterPDF*' -or $_.ProcessName -like '*MasterPDF*' })
    if ($existing.Count -gt 0) {
        throw "MasterPDF is already running; close existing instances before smoke."
    }

    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $classCond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ClassNameProperty,
        'MASTER_PDF_FRAME'
    )

    $startedProcess = Start-Process -FilePath $MasterPdfPath -ArgumentList @($SourcePdf) -PassThru
    Start-Sleep -Seconds 5

    $window = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $classCond)
    if ($null -eq $window) {
        throw "MasterPDF window not found."
    }

    $windowPid = $window.Current.ProcessId
    $hwnd = [IntPtr]$window.Current.NativeWindowHandle
    [Win32Capture]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 700

    $rect = New-Object Win32Capture+RECT
    [Win32Capture]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -le 0 -or $height -le 0) {
        throw "Invalid MasterPDF window bounds."
    }

    $beforePath = Join-Path $OutputDir 'before.png'
    $afterPath = Join-Path $OutputDir 'after.png'

    $bmp1 = New-Object System.Drawing.Bitmap $width, $height
    $g1 = [System.Drawing.Graphics]::FromImage($bmp1)
    $g1.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp1.Size)
    $bmp1.Save($beforePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g1.Dispose()

    [System.Windows.Forms.SendKeys]::SendWait('{PGDN}')
    Start-Sleep -Seconds 1

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

    try {
        $windowPattern = $window.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern)
        $windowPattern.Close()
    } catch {}

    $result.status = "ok"
    $result.window_name = $window.Current.Name
    $result.window_handle = $window.Current.NativeWindowHandle
    $result.window_pid = $windowPid
    $result.before = $beforePath
    $result.after = $afterPath
    $result.images_equal = $same
    $result.page_advanced = (-not $same)
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    if ($windowPid) {
        $proc = Get-Process -Id $windowPid -ErrorAction SilentlyContinue
        if ($proc) {
            try { $proc.CloseMainWindow() | Out-Null } catch {}
            Start-Sleep -Milliseconds 500
            $proc = Get-Process -Id $windowPid -ErrorAction SilentlyContinue
            if ($proc) {
                try { Stop-Process -Id $windowPid -Force } catch {}
            }
        }
    } elseif ($startedProcess -and -not $startedProcess.HasExited) {
        try { $startedProcess.CloseMainWindow() | Out-Null } catch {}
        Start-Sleep -Milliseconds 500
        if (-not $startedProcess.HasExited) {
            try { Stop-Process -Id $startedProcess.Id -Force } catch {}
        }
    }
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
}

$result | ConvertTo-Json -Depth 6
