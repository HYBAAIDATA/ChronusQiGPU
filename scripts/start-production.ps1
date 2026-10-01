# Start the PYTHIA control API with production configuration.
# The API loads .env automatically; this script only ensures the data
# directories exist and the frontend has been built.
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
& $venvPython main.py --host 0.0.0.0 --port 3000 --web-root dist/public
