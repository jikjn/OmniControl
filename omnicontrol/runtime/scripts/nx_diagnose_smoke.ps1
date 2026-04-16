param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$runJournal = 'C:\Program Files\Siemens\NX1953\NXBIN\run_journal.exe'
$sample = 'C:\Program Files\Siemens\NX1953\UGOPEN\SampleNXOpenApplications\Python\ValidateNXOpenSetup\ValidateNXOpenSetup.py'

function Invoke-CapturedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments
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
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    return [ordered]@{
        exit_code = $proc.ExitCode
        stdout = $stdout.Trim()
        stderr = $stderr.Trim()
    }
}

$result = [ordered]@{
    status = "blocked"
    run_journal = $runJournal
    sample = $sample
    blockers = @()
}

if (-not (Test-Path $runJournal)) {
    $result.status = "error"
    $result.blockers += "run_journal.exe not found"
    $result | ConvertTo-Json -Depth 6
    exit 0
}

$help = Invoke-CapturedProcess -FilePath $runJournal -Arguments @('-help')
$attempt = Invoke-CapturedProcess -FilePath $runJournal -Arguments @($sample)
$licenseListening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 28000 }

$result.help_exit_code = $help.exit_code
$result.help_output = @($help.stdout, $help.stderr) -join "`n"
$result.sample_exit_code = $attempt.exit_code
$result.sample_output = @($attempt.stdout, $attempt.stderr) -join "`n"
$result.splm_license_server = $env:SPLM_LICENSE_SERVER
$result.license_port_listening = [bool]$licenseListening

if ($result.sample_output -match 'failed to initialize UFUN') {
    $result.blockers += 'UFUN initialization failed'
}
if (-not $licenseListening) {
    $result.blockers += 'license port 28000 is not listening'
}
if ($result.blockers.Count -eq 0) {
    $result.status = "ok"
}

$result | ConvertTo-Json -Depth 6
