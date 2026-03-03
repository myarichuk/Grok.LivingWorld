#!/usr/bin/env python3
"""Diagnose and bootstrap Grok REPL imports for this repository.

Usage:
    python scripts/grok_repl_doctor.py
"""

from __future__ import annotations

import importlib
import pathlib
import sys

REQUIRED_MODULES = (
    "ecs",
    "ttrpg_engine",
    "ttrpg_5e",
)


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def _ensure_src_on_path() -> pathlib.Path:
    src_path = _repo_root() / "src"
    src_str = str(src_path)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    return src_path


def _check_imports() -> list[str]:
    failures: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - diagnostic script
            failures.append(f"{module_name}: {exc}")
    return failures


def main() -> int:
    src_path = _ensure_src_on_path()
    failures = _check_imports()

    print(f"repo_root={_repo_root()}")
    print(f"src_path={src_path}")
    if failures:
        print("status=failed")
        for failure in failures:
            print(f"import_error={failure}")
        print("hint=run from repo root or set PYTHONPATH=src")
        return 1

    from ecs import World

    # Validate a basic symbol to prevent silent partial imports.
    _ = World
    print("status=ok")
    print("example=from ecs import World")
    print("example=from ttrpg_engine import KernelState")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
