$ErrorActionPreference = 'Stop'

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .venv
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .venv
}
else {
    throw "Python not found. Install Python 3.10+ and retry."
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

try {
    python -m pip install setuptools wheel
    python -m pip install -e ".[dev]"
    Write-Host 'Installed package in editable mode with dev extras.'
}
catch {
    Write-Host 'Editable install failed; installing direct dev dependencies instead.'
    python -m pip install numpy pytest ruff
}

Write-Host 'Environment ready. Activate with: .\.venv\Scripts\Activate.ps1'
