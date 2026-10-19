param(
    [string]$ExpectedCommit = "",
    [string]$OutputDirectory = "",
    [switch]$Offline,
    [string]$Wheelhouse = ""
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ExpectedCommit) {
    $ExpectedCommit = (& git -C $repo rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Unable to resolve the source commit" }
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path ([IO.Path]::GetTempPath()) ("euclid-evidence-" + [guid]::NewGuid())
}
$arguments = @((Join-Path $PSScriptRoot "run_clean_install.py"),
    "--expected-commit", $ExpectedCommit, "--output-dir", $OutputDirectory)
if ($Offline) { $arguments += "--offline" }
if ($Wheelhouse) { $arguments += @("--wheelhouse", $Wheelhouse) }
& python @arguments
if ($LASTEXITCODE -ne 0) { throw "Clean-install acceptance failed; inspect $OutputDirectory" }
Write-Host "Installed-artifact acceptance passed. Evidence: $OutputDirectory"
