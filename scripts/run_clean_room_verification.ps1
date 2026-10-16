# 1. Verify working branch and head commit (must be at 4226a3c9)
Set-Location "C:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main"
git status --short --branch
git rev-parse HEAD

# 2. Build the enterprise distribution wheel (offline, self-contained)
python scripts\build_standalone_wheel.py
$wheel = Get-ChildItem "dist\euclid_engine-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

Write-Host "`n[*] Built enterprise wheel: $($wheel.FullName)"

# 3. Create a clean, isolated virtual environment in $env:TEMP
$cleanEnv = "$env:TEMP\euclid-clean-env"
if (Test-Path $cleanEnv) { Remove-Item $cleanEnv -Recurse -Force }
python -m venv $cleanEnv

$cleanPython = "$cleanEnv\Scripts\python.exe"
$cleanPip = "$cleanEnv\Scripts\pip.exe"

# 4. Install the enterprise wheel into the clean venv
& $cleanPip install --no-index --find-links="dist" $wheel.FullName

# 5. Execute out-of-tree verification from an empty temporary directory
$isolatedDir = "$env:TEMP\euclid-isolated-run"
if (Test-Path $isolatedDir) { Remove-Item $isolatedDir -Recurse -Force }
New-Item -ItemType Directory -Path $isolatedDir -Force | Out-Null

Copy-Item "scripts\verify_clean_install.py" "$isolatedDir\verify_clean_install.py"
Copy-Item "tests\test_unified_intelligence_consolidation.py" "$isolatedDir\test_unified_intelligence_consolidation.py"
Set-Location $isolatedDir

# Run verification harness against clean installed packages (cwd is empty)
& $cleanPython verify_clean_install.py
$testExit = $LASTEXITCODE

if ($testExit -eq 0) {
    Write-Host "`n[*] Running consolidation test suite out-of-tree from clean venv..."
    & $cleanPython -m unittest test_unified_intelligence_consolidation.py
    $testExit = $LASTEXITCODE
}

# 6. Return to repo root and report outcome
Set-Location "C:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main"
if ($testExit -eq 0) {
    Write-Host "`n[+] Verification Checkpoint PASSED: Installed artifact operates correctly out-of-tree." -ForegroundColor Green
} else {
    Write-Host "`n[!] Verification Checkpoint FAILED with exit code $testExit" -ForegroundColor Red
}
exit $testExit
