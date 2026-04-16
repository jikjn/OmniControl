param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$ProfileValue
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$fiper = 'C:\SIMULIA\Isight\2021\win_b64\code\command\fipercmd.bat'
$sample = 'C:\SIMULIA\Isight\2021\win_b64\examples\models\applications\I_Beam\I_Beam.zmf'

function Invoke-CapturedCmd {
    param(
        [string]$CommandLine
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'cmd.exe'
    $psi.Arguments = "/Q /C $CommandLine"
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
    fipercmd = $fiper
    sample = $sample
    blockers = @()
}

if (-not (Test-Path $fiper)) {
    $result.status = "error"
    $result.blockers += "fipercmd.bat not found"
    $result | ConvertTo-Json -Depth 6
    exit 0
}

$help = Invoke-CapturedCmd -CommandLine "call `"$fiper`" -help"
$profileArg = ""
if ($ProfileValue) {
    $profileArg = " profile:$ProfileValue"
}
$attempt = Invoke-CapturedCmd -CommandLine "call `"$fiper`" contents file:$sample$profileArg logonprompt:no -nogui"
$licenseListening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 4085 }
$dslsText = if (Test-Path 'C:\SIMULIA\Isight\2021\config\DSLicSrv.txt') { Get-Content 'C:\SIMULIA\Isight\2021\config\DSLicSrv.txt' | Out-String } else { '' }

$result.help_exit_code = $help.exit_code
$result.help_output = @($help.stdout, $help.stderr) -join "`n"
$result.attempt_exit_code = $attempt.exit_code
$result.attempt_output = @($attempt.stdout, $attempt.stderr) -join "`n"
$result.profile_value = $ProfileValue
$result.license_port_listening = [bool]$licenseListening
$result.dsls_hint = $dslsText.Trim()

if ($result.attempt_output -match 'connection profile is required') {
    $result.blockers += 'connection profile is required'
}
if ($result.attempt_output -match 'Error restoring variable collection') {
    $result.blockers += 'variable collection restore failed'
}
if (-not $licenseListening) {
    $result.blockers += 'DSLS port 4085 is not listening'
}
if ($result.blockers.Count -eq 0) {
    $result.status = "ok"
}

$result | ConvertTo-Json -Depth 6
