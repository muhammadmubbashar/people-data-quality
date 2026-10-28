param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $Python -c "import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Pass -Python with the path to Python 3.12 or 3.13.' }
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or 3.13 is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install --require-hashes -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install --no-deps --no-build-isolation -e .
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
if (-not (Test-Path -LiteralPath '.env')) {
    & '.\.venv\Scripts\python.exe' scripts/init_local.py
    if ($LASTEXITCODE -ne 0) { throw 'Local configuration failed.' }
}
Write-Output 'Setup complete. Start run-api.ps1 and run-ui.ps1 in separate terminals.'
