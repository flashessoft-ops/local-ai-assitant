param([ValidateSet('All', 'Backend', 'Frontend')][string]$Service = 'All')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$runtime = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$vite = Join-Path $PSScriptRoot 'frontend\node_modules\vite\bin\vite.js'
$node = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
if (-not $node) {
    $bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    if (Test-Path -LiteralPath $bundledNode) { $node = $bundledNode }
}
if (!(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath $vite) -or !$node) { throw 'Dependencies missing. Follow README.md setup first.' }

function Start-LocalService($Name, $Executable, $Arguments, $Port, $CheckUrl) {
    $statePath = Join-Path $runtime "$Name.json"
    if (Test-Path -LiteralPath $statePath) {
        $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $existing = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
        if ($existing -and $existing.StartTime.ToUniversalTime().Ticks.ToString() -eq $saved.started) {
            Write-Host "$Name is already running."
            return
        }
    }
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is occupied. Stop its existing server first." }
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime "$Name.out.log") -RedirectStandardError (Join-Path $runtime "$Name.err.log")
    @{ pid = $process.Id; started = $process.StartTime.ToUniversalTime().Ticks.ToString() } | ConvertTo-Json | Set-Content -LiteralPath $statePath
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        $process.Refresh()
        if ($process.HasExited) { throw "$Name exited. See .runtime\$Name.err.log." }
        try {
            Invoke-WebRequest -Uri $CheckUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
            Write-Host "$Name started on port $Port."
            return
        } catch { }
    }
    throw "$Name did not become ready. See .runtime\$Name.err.log; run stop.ps1 to stop it."
}
if ($Service -in @('All', 'Backend')) {
    try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2 | Out-Null }
    catch { Start-LocalService 'ollama' (Get-Command ollama.exe -ErrorAction Stop).Source 'serve' 11434 'http://127.0.0.1:11434/api/tags' }
    Start-LocalService 'backend' $python '-m uvicorn backend.main:app --host 127.0.0.1 --port 8000' 8000 'http://127.0.0.1:8000/api/health'
}
if ($Service -in @('All', 'Frontend')) {
    Start-LocalService 'frontend' $node ('"' + $vite + '" "' + (Join-Path $PSScriptRoot 'frontend') + '" --host 127.0.0.1 --port 5173 --strictPort') 5173 'http://127.0.0.1:5173'
}
Write-Host 'Open http://127.0.0.1:5173 in your browser. Stop with .\stop.ps1.'
