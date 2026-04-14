param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$ProjectPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$editorCmd = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$project = $ProjectPath
$pyFile = Join-Path $OutputDir 'ue_write_inline.py'
$outputFile = Join-Path $OutputDir 'ue_python_write.txt'

$result = [ordered]@{
    status = "error"
    editor_cmd = $editorCmd
    project = $project
    output_file = $outputFile
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    $python = "import pathlib; pathlib.Path(r'$($outputFile.Replace('\', '/'))').write_text('ok from ue inline', encoding='utf-8')"
    Set-Content -Path $pyFile -Value $python -Encoding UTF8
    Remove-Item $outputFile -Force -ErrorAction SilentlyContinue

    if ($project) {
        $stdoutFile = Join-Path $OutputDir 'ue_stdout.txt'
        $stderrFile = Join-Path $OutputDir 'ue_stderr.txt'
        $args = @(
            $project,
            '-Unattended',
            '-NoSplash',
            '-NullRHI',
            '-stdout',
            '-FullStdOutLogOutput',
            '-run=pythonscript',
            "-script=$python",
            '-ExecCmds=QUIT_EDITOR'
        )
        $proc = Start-Process -FilePath $editorCmd -ArgumentList $args -PassThru -NoNewWindow -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
        $proc.WaitForExit(180000) | Out-Null
        if (-not $proc.HasExited) {
            try { Stop-Process -Id $proc.Id -Force } catch {}
        }
        $stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw } else { '' }
        $stderr = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { '' }
        $output = ($stdout + "`n" + $stderr)
        $result.command_args = $args
        $result.exit_code = $proc.ExitCode
    } else {
        $cmd = "`"$editorCmd`" -Unattended -NoSplash -NullRHI -stdout -FullStdOutLogOutput -run=pythonscript `"-script=$python`""
        $output = cmd /c $cmd 2>&1 | Out-String
        $result.command_line = $cmd
    }
    $result.file_exists = (Test-Path $outputFile)
    if ($result.file_exists) {
        $result.file_contents = [System.IO.File]::ReadAllText($outputFile)
    }
    $result.write_ok = $result.file_exists -and ($result.file_contents -eq 'ok from ue inline')
    $result.engine_version = '5.7.4'
    $result.log_excerpt = $output.Substring(0, [Math]::Min($output.Length, 8000))
    $result.status = if ($result.write_ok) { 'ok' } else { 'blocked' }
    if (-not $result.write_ok) {
        $result.blockers = @('python script did not produce expected output file')
    }
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    Get-Process | Where-Object { $_.ProcessName -like 'UnrealEditor*' -or $_.ProcessName -like 'CrashReportClient*' } | Stop-Process -Force -ErrorAction SilentlyContinue
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
}

$result | ConvertTo-Json -Depth 6
