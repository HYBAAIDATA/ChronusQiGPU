#Requires -Version 5.1
<#
.SYNOPSIS
  Windows smoke gauntlet for the repo's Python gates.

.DESCRIPTION
  Runs the same compileall + pytest smoke checks referenced by ci.yml,
  but using the local .venv so no global python/python3 shim is required.
#>
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $RepoRoot 'scripts/run.ps1'

$packages = @(
    'Intelligence',
    'core_engine',
    'mining',
    'hyba',
    'lucas',
    'scripts',
    'tests',
    'chronus',
    'chronus/mla1517_platform/python'
)

& $Runner -m compileall -q @packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Runner -m pytest tests/ -x -q
exit $LASTEXITCODE
