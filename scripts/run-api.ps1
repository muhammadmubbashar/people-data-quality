$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m uvicorn people_quality.api:create_app --factory --host 127.0.0.1 --port 8000
