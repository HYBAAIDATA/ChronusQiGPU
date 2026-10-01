# Build the React operator frontend directly through Node, bypassing the
# broken NVM4W path on this Windows host.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repoRoot "frontend"

# Fix the obsolete C:\Users\USER NVM_HOME reference inherited by the process.
$env:NVM_HOME = "C:\nvm4w"

Set-Location $frontend
node ./node_modules/vite/bin/vite.js build
