$ErrorActionPreference = 'Stop'

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install numpy pytest ruff

Write-Host 'Environment ready. Activate with: .\.venv\Scripts\Activate.ps1'
