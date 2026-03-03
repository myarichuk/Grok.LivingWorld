#!/usr/bin/env python3
"""Detect escaped/corrupted Python source artifacts in the repo.

This catches deployment/fetch bugs where files are stored as escaped single-line
strings (for example: literal "\\n", "\\__all__", or leading "text\"\"\"").
"""

from __future__ import annotations

import ast
import pathlib

SUSPICIOUS_SNIPPETS = (
    'text"""',
    "\\__all__",
    "\\[",
    "\\]",
)


def _is_suspicious(content: str) -> list[str]:
    findings: list[str] = []
    for snippet in SUSPICIOUS_SNIPPETS:
        if snippet in content:
            findings.append(f"contains '{snippet}'")

    # One real line + many escaped newlines usually means escaped blob content.
    if content.count("\n") <= 1 and "\\n" in content:
        findings.append("looks like escaped single-line source")

    # Heuristic for repr-like escaped blobs.
    if content.count("\\") > 20 and content.count("\n") < 5:
        findings.append("high backslash density with low real newlines")

    return findings


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    src = root / "src"
    failed = False

    for path in sorted(src.rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        findings = _is_suspicious(content)
        if findings:
            failed = True
            print(f"FAIL {path.relative_to(root)} :: {'; '.join(findings)}")
            continue

        try:
            ast.parse(content, filename=str(path))
        except SyntaxError as exc:
            failed = True
            print(
                "FAIL "
                f"{path.relative_to(root)} :: syntax error at line {exc.lineno}: "
                f"{exc.msg}"
            )

    if failed:
        print("status=failed")
        return 1

    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
