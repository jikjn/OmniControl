param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [Parameter(Mandatory = $true)]
    [string]$WordPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$outputDocx = Join-Path $OutputDir 'word-workflow.docx'
$outputPdf = Join-Path $OutputDir 'word-workflow.pdf'

$result = [ordered]@{
    status = "error"
    output_docx = $outputDocx
    word_path = $WordPath
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$word = $null
$doc = $null

try {
    $null = New-Item -ItemType Directory -Force -Path $OutputDir
    Remove-Item $outputDocx, $outputPdf -Force -ErrorAction SilentlyContinue

    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Add()

    $doc.Content.Text = "OmniControl Word Workflow`r`nStep 1: body write`r`nStep 2: exported artifact at $(Get-Date -Format o)"
    $doc.SaveAs2([ref]([string]$outputDocx))
    $doc.Close(0)
    $doc = $null
    $word.Quit()
    $word = $null

    $docxExists = Test-Path -LiteralPath $outputDocx
    if (-not $docxExists) { throw "Workflow DOCX was not created." }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $docxBytes = [System.IO.File]::ReadAllBytes($outputDocx)
    $docxMagic = [System.BitConverter]::ToString($docxBytes[0..3])
    $zip = [System.IO.Compression.ZipFile]::OpenRead($outputDocx)
    try {
        $entry = $zip.GetEntry('word/document.xml')
        if ($null -eq $entry) { throw "word/document.xml was not found in workflow DOCX." }
        $reader = New-Object System.IO.StreamReader($entry.Open())
        try {
            $documentXml = $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $zip.Dispose()
    }
    $bodyMarkersOk = ($documentXml -match 'OmniControl Word Workflow') -and ($documentXml -match 'Step 1: body write') -and ($documentXml -match 'Step 2:')

    $result.status = "ok"
    $result.docx_exists = $docxExists
    $result.docx_size = (Get-Item -LiteralPath $outputDocx).Length
    $result.docx_magic = $docxMagic
    $result.docx_zip_ok = ($docxMagic -eq '50-4B-03-04')
    $result.body_markers_ok = [bool]$bodyMarkersOk
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
