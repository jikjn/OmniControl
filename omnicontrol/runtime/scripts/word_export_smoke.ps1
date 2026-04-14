param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDocx,
    [Parameter(Mandatory = $true)]
    [string]$OutputPdf,
    [Parameter(Mandatory = $true)]
    [string]$WordPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$result = [ordered]@{
    status = "error"
    source = $SourceDocx
    output = $OutputPdf
    word_path = $WordPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$word = $null
$document = $null

try {
    if (-not (Test-Path -LiteralPath $SourceDocx)) {
        throw "Source document not found: $SourceDocx"
    }
    if (-not (Test-Path -LiteralPath $WordPath)) {
        throw "WINWORD.EXE not found: $WordPath"
    }

    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPdf)
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($SourceDocx, $false, $true)
    $document.ExportAsFixedFormat($OutputPdf, 17)
    $document.Close(0)
    $document = $null
    $word.Quit()
    $word = $null

    $exists = Test-Path -LiteralPath $OutputPdf
    if (-not $exists) {
        throw "PDF output was not created."
    }

    $bytes = [System.IO.File]::ReadAllBytes($OutputPdf)
    $magic = [System.Text.Encoding]::ASCII.GetString($bytes, 0, [Math]::Min(5, $bytes.Length))
    $result.status = "ok"
    $result.exists = $exists
    $result.size = (Get-Item -LiteralPath $OutputPdf).Length
    $result.magic = $magic
    $result.magic_ok = $magic -eq "%PDF-"
}
catch {
    $result.status = "error"
    $result.error = $_.Exception.Message
}
finally {
    $stopwatch.Stop()
    $result.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
    if ($document -ne $null) {
        try { $document.Close(0) } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) } catch {}
    }
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$result | ConvertTo-Json -Depth 6
