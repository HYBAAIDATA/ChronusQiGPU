#Requires -Version 5.1
<#
.SYNOPSIS
  Path-agnostic Windows runner for the PYTHIA Python backend.

.DESCRIPTION
  Uses the repo's .venv/Scripts/python.exe when present, falling back to a real
  Python install before PATH shims. Sets PYTHONPATH to the repo root and the
  MLA1517 canonical python path so imports resolve without a global install.

.EXAMPLE
  .\scripts\run.ps1 main.py --help
  .\scripts\run.ps1 -m pytest tests/ -x -q
#>

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot '.venv/Scripts/python.exe'

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$PrefixArgs = @()
    )

    try {
        $probe = @($PrefixArgs) + @('-c', 'import sys; print(sys.version_info[:2])')
        $null = & $Command @probe 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Test-WindowsAppsAlias {
    param(
        [Parameter(Mandatory = $true)]
        $CommandInfo
    )

    $source = [string]$CommandInfo.Source
    return $source -like "$env:LOCALAPPDATA\Microsoft\WindowsApps\python*.exe"
}

$Python = $null
$PythonPrefixArgs = @()

if ((Test-Path $VenvPython) -and (Test-PythonCandidate $VenvPython)) {
    $Python = $VenvPython
}
else {
    $KnownPython = @(
        (Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs/Python/Python313/python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs/Python/Python311/python.exe'),
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        'C:\Python312\python.exe'
    )

    foreach ($candidate in $KnownPython) {
        if ($candidate -and (Test-Path $candidate) -and (Test-PythonCandidate $candidate)) {
            $Python = $candidate
            break
        }
    }
}

if (-not $Python) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand -and -not (Test-WindowsAppsAlias $PythonCommand) -and (Test-PythonCandidate $PythonCommand.Source)) {
        $Python = $PythonCommand.Source
    }
}

if (-not $Python) {
    $PyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($PyCommand -and (Test-PythonCandidate $PyCommand.Source @('-3'))) {
        $Python = $PyCommand.Source
        $PythonPrefixArgs = @('-3')
    }
}

if (-not $Python) {
    throw "No usable Python interpreter found. Expected $VenvPython, a Python.org install, or py on PATH."
}

$env:PYTHONPATH = "$RepoRoot;$RepoRoot\chronus;$RepoRoot\chronus\mla1517_platform\python"

& $Python @PythonPrefixArgs @args
exit $LASTEXITCODE
