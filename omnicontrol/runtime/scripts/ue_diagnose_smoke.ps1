param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$editor = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$editorCmd = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$buildPatch = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\BuildPatchTool.exe'

function Invoke-WithTimeout {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [int]$TimeoutSeconds = 30
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = (($Arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' ')
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        try { $proc.Kill() } catch {}
        return [ordered]@{
            status = 'timeout'
            stdout = ''
            stderr = ''
            exit_code = $null
        }
    }

    return [ordered]@{
        status = 'exited'
        stdout = $proc.StandardOutput.ReadToEnd().Trim()
        stderr = $proc.StandardError.ReadToEnd().Trim()
        exit_code = $proc.ExitCode
    }
}

$result = [ordered]@{
    status = "blocked"
    editor = $editor
    editor_cmd = $editorCmd
    build_patch = $buildPatch
    editor_exists = (Test-Path $editor)
    cmd_exists = (Test-Path $editorCmd)
    build_patch_exists = (Test-Path $buildPatch)
    timeout_seconds = 30
    blockers = @()
}

if (-not $result.editor_exists) {
    $result.status = "error"
    $result.blockers += "UnrealEditor.exe not found"
    $result | ConvertTo-Json -Depth 6
    exit 0
}

$helpResult = Invoke-WithTimeout -FilePath $editor -Arguments @('-help') -TimeoutSeconds 30
$result.help_status = $helpResult.status
$result.help_exit_code = $helpResult.exit_code
$result.help_stdout = $helpResult.stdout
$result.help_stderr = $helpResult.stderr

if ($helpResult.status -eq 'timeout') {
    $result.blockers += 'editor help command timed out'
}

if ($result.blockers.Count -eq 0) {
    $result.status = 'ok'
}

$result | ConvertTo-Json -Depth 6
