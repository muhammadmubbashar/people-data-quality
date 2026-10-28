$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m streamlit run ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
