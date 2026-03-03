#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy pytest ruff

echo "Environment ready. Activate with: source .venv/bin/activate"
