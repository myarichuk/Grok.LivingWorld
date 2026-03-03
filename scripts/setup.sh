#!/usr/bin/env bash
set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "Python not found. Install Python 3.10+ and retry." >&2
  exit 1
fi

$PYTHON_BIN -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# Prefer editable install of project + dev extras, then fall back to direct deps.
if python -m pip install setuptools wheel && python -m pip install -e ".[dev]"; then
  echo "Installed package in editable mode with dev extras."
else
  echo "Editable install failed; installing direct dev dependencies instead."
  python -m pip install numpy pytest ruff
fi

echo "Environment ready. Activate with: source .venv/bin/activate"
