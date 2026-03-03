from __future__ import annotations

import ast
from pathlib import Path


def test_all_src_python_files_are_valid_syntax() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for path in sorted((repo_root / "src").rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        ast.parse(content, filename=str(path))


def test_package_init_files_are_not_escaped_blobs() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    suspicious_tokens = ('text"""', "\\__all__", "\\[", "\\]")

    for path in sorted((repo_root / "src").rglob("__init__.py")):
        content = path.read_text(encoding="utf-8")
        assert content.count("\n") > 1
        for token in suspicious_tokens:
            assert token not in content
