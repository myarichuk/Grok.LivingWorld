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
python -m pip install -e ".[dev]"

echo "Environment ready. Activate with: source .venv/bin/activate"
