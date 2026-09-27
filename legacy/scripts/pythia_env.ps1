# PYTHIA environment loader — populates MLA1517_*/PYTHIA_* vars from .env.
# Usage:  . .\scripts\pythia_env.ps1   (dot-source so vars persist in session)
#         python main.py

$envFile = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found at $envFile"
    return
}

$loaded = 0
foreach ($raw in (Get-Content $envFile)) {
    $line = $raw.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }
    $eq = $line.IndexOf("=")
    if ($eq -lt 1) { continue }
    $name = $line.Substring(0, $eq).Trim()
    $value = $line.Substring($eq + 1).Trim()
    if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    if ($name -match '^[A-Za-z_][A-Za-z0-9_]*$') {
        Set-Item -Path "Env:$name" -Value $value
        $loaded++
    }
}
Write-Host "pythia_env: loaded $loaded variables from $envFile"
