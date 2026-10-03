$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.runtime'
foreach ($name in @('frontend', 'backend', 'ollama')) {
    $statePath = Join-Path $runtime "$name.json"
    if (!(Test-Path -LiteralPath $statePath)) { continue }
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $process = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
    # Creation time prevents a reused PID from stopping an unrelated process.
    if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $saved.started) {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not stop $name (PID $($process.Id))." }
        Write-Host "$name stopped."
    }
    Remove-Item -LiteralPath $statePath
}
Write-Host 'Local Chat stopped. Saved conversations are preserved.'
