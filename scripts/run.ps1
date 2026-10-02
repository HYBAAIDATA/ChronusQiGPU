#Requires -Version 5.1
<#
.SYNOPSIS
  Path-agnostic Windows runner for the PYTHIA Python backend.

.DESCRIPTION
  Uses the repo's .venv/Scripts/python.exe when present, falling back to
  'python' or 'py' on PATH. Sets PYTHONPATH to the repo root and the MLA1517
  canonical python path so imports resolve without a global install.

.EXAMPLE
  .\scripts\run.ps1 main.py --help
  .\scripts\run.ps1 -m pytest tests/ -x -q
#>

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot '.venv/Scripts/python.exe'

$Python = if (Test-Path $VenvPython) {
    $VenvPython
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    'python'
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    'py'
}
else {
    throw "No Python interpreter found. Expected $VenvPython or python/py on PATH."
}

$env:PYTHONPATH = "$RepoRoot;$RepoRoot\chronus;$RepoRoot\chronus\mla1517_platform\python"

& $Python @args
exit $LASTEXITCODE
