# PYTHIA non-mining demo boot — control API + operator UI only.
#
# Mining workers are NOT spawned: PYTHIA_EXECUTION_DEVICE is deliberately
# unset, so the device gate fails closed and workers read as armed_no_device.
# Usage:  .\demo_boot.ps1        (port 3000)
#         .\demo_boot.ps1 3111   (alternate port)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$env:PYTHONPATH = "$PWD;$PWD\chronus\mla1517_platform\python"
$env:MLA1517_STRATUM_USER = 'demo'
$env:MLA1517_STRATUM_PASSWORD = 'x'
$env:MLA1517_STRATUM_ENDPOINT = 'stratum.braiins.com:3333'
$env:EUCLID_ADMIN_API_KEY = 'demo-key'
$env:PYTHIA_AUTOSTART_WORKERS = 'false'
# NOTE: PYTHIA_EXECUTION_DEVICE intentionally NOT set -> no mining workers.

$port = if ($args[0]) { $args[0] } else { 3000 }

Write-Host "Operator UI:  http://127.0.0.1:$port/#/algebra" -ForegroundColor Cyan
Write-Host "Operator key: demo-key (prompted when you run the self-test from the UI)" -ForegroundColor Cyan

python -u chronus/mla1517_platform/python/main.py `
  --host 127.0.0.1 --port $port --web-root dist/public
