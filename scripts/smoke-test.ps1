# End-to-end smoke test for the local PYTHIA operator app.
# 1. Builds the frontend.
# 2. Starts the control API in a background job.
# 3. Runs scripts/smoke_test.py against it.
# 4. Shuts the API down and prints the result.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Set-Location $repoRoot

# Ensure durable-state directories exist.
$dirs = @("data", "data/intelligence", "data/hb")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

# Fix the obsolete C:\Users\USER NVM_HOME reference before any npm call.
$env:NVM_HOME = "C:\nvm4w"

& "$PSScriptRoot\build-frontend.ps1"

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$apiPort = if ($env:PYTHIA_SMOKE_PORT) { $env:PYTHIA_SMOKE_PORT } else { 3001 }
$apiJob = Start-Job -ScriptBlock {
    param($python, $root, $port)
    Set-Location $root
    & $python main.py --host 127.0.0.1 --port $port --web-root dist/public
} -ArgumentList $venvPython, $repoRoot, $apiPort

try {
    Start-Sleep -Seconds 3
    $env:PYTHIA_SMOKE_PORT = $apiPort
    & $venvPython scripts/smoke_test.py
    if ($LASTEXITCODE -ne 0) {
        throw "Smoke test failed with exit code $LASTEXITCODE"
    }
} finally {
    Stop-Job $apiJob -ErrorAction SilentlyContinue
    Remove-Job $apiJob -Force -ErrorAction SilentlyContinue
}
