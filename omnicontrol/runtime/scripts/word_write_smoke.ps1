param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDocx,
    [Parameter(Mandatory = $true)]
    [string]$WordPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$result = [ordered]@{
    status = "error"
    output = $OutputDocx
    word_path = $WordPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$word = $null
$doc = $null

try {
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputDocx)
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Add()
    $doc.Content.Text = "OmniControl write smoke`r`nGenerated at: $(Get-Date -Format o)"
    $doc.SaveAs([ref]$OutputDocx)
    $doc.Close(0)
    $doc = $null
    $word.Quit()
    $word = $null

    $exists = Test-Path -LiteralPath $OutputDocx
    if (-not $exists) { throw "Output DOCX was not created." }
    $zipBytes = [System.IO.File]::ReadAllBytes($OutputDocx)
    $magic = [System.BitConverter]::ToString($zipBytes[0..3])

    $result.status = "ok"
    $result.exists = $exists
    $result.size = (Get-Item -LiteralPath $OutputDocx).Length
    $result.magic = $magic
    $result.zip_ok = ($magic -eq '50-4B-03-04')
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
    if ($doc -ne $null) {
        try { $doc.Close(0) } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc) } catch {}
    }
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$result | ConvertTo-Json -Depth 6
