param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$ProjectPath,
    [string]$ScriptPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$editorCmd = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$project = $ProjectPath
$pyFile = if ($ScriptPath) { $ScriptPath } else { Join-Path $OutputDir 'ue_write_inline.py' }
$outputFile = Join-Path $OutputDir 'ue_python_write.txt'

function ConvertTo-WindowsArgument {
    param([string]$Argument)
    if ($null -eq $Argument -or $Argument.Length -eq 0) {
        return '""'
    }
    if ($Argument -notmatch '[\s"]') {
        return $Argument
    }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($char in $Argument.ToCharArray()) {
        if ($char -eq '\') {
            $slashes += 1
            continue
        }
        if ($char -eq '"') {
            [void]$builder.Append(('\' * (($slashes * 2) + 1)))
            [void]$builder.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes -gt 0) {
            [void]$builder.Append(('\' * $slashes))
            $slashes = 0
        }
        [void]$builder.Append($char)
    }
    if ($slashes -gt 0) {
        [void]$builder.Append(('\' * ($slashes * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Join-WindowsArguments {
    param([string[]]$Arguments)
    return (($Arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join ' ')
}

$result = [ordered]@{
    status = "error"
    editor_cmd = $editorCmd
    project = $project
    output_file = $outputFile
    script_file = $pyFile
    script_transport = "file"
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    $python = "import pathlib; pathlib.Path(r'$($outputFile.Replace('\', '/'))').write_text('ok from ue inline', encoding='utf-8')"
    if (-not $ScriptPath) {
        Set-Content -Path $pyFile -Value $python -Encoding UTF8
    }
    Remove-Item $outputFile -Force -ErrorAction SilentlyContinue

    $stdoutFile = Join-Path $OutputDir 'ue_stdout.txt'
    $stderrFile = Join-Path $OutputDir 'ue_stderr.txt'
    if ($project) {
        $args = @(
            $project,
            '-Unattended',
            '-NoSplash',
            '-NullRHI',
            '-stdout',
            '-FullStdOutLogOutput',
            '-run=pythonscript',
            "-script=$pyFile",
            '-ExecCmds=QUIT_EDITOR'
        )
    } else {
        $args = @(
            '-Unattended',
            '-NoSplash',
            '-NullRHI',
            '-stdout',
            '-FullStdOutLogOutput',
            '-run=pythonscript',
            "-script=$pyFile"
        )
    }
    $argumentLine = Join-WindowsArguments $args
    $proc = Start-Process -FilePath $editorCmd -ArgumentList $argumentLine -PassThru -NoNewWindow -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
    $proc.WaitForExit(180000) | Out-Null
    if (-not $proc.HasExited) {
        try { Stop-Process -Id $proc.Id -Force } catch {}
    }
    $stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw } else { '' }
    $stderr = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { '' }
    $output = ($stdout + "`n" + $stderr)
    $result.command_args = $args
    $result.command_argument_line = $argumentLine
    $result.exit_code = $proc.ExitCode
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
