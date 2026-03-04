#!/usr/bin/env python3
"""Build a single-file Grok REPL bundle from src/ Python modules.

This script validates source integrity, then emits dist/grok_repl_bundle.py.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
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

    if content.count("\n") <= 1 and "\\n" in content:
        findings.append("looks like escaped single-line source")

    if content.count("\\") > 20 and content.count("\n") < 5:
        findings.append("high backslash density with low real newlines")

    return findings


def _collect_sources(repo_root: pathlib.Path) -> dict[str, tuple[str, str]]:
    src_root = repo_root / "src"
    sources: dict[str, tuple[str, str]] = {}

    for path in sorted(src_root.rglob("*.py")):
        rel_path = str(path.relative_to(repo_root))
        content = path.read_text(encoding="utf-8")

        findings = _is_suspicious(content)
        if findings:
            details = "; ".join(findings)
            raise RuntimeError(f"integrity failed for {rel_path}: {details}")

        try:
            ast.parse(content, filename=rel_path)
        except SyntaxError as exc:
            raise RuntimeError(
                f"syntax failed for {rel_path} line {exc.lineno}: {exc.msg}"
            ) from exc

        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        sources[rel_path] = (encoded, digest)

    if not sources:
        raise RuntimeError("no src/*.py files found")

    return sources


def _render_bundle(sources: dict[str, tuple[str, str]]) -> str:
    lines = [
        "#!/usr/bin/env python3",
        '"""Self-contained Grok REPL installer for this project."""',
        "",
        "from __future__ import annotations",
        "",
        "import argparse",
        "import ast",
        "import base64",
        "import hashlib",
        "import pathlib",
        "import sys",
        "",
        "SUSPICIOUS_SNIPPETS = (",
        "    'text\\\"\\\"\\\"',",
        "    '\\\\__all__',",
        "    '\\\\[',",
        "    '\\\\]',",
        ")",
        "",
        "SOURCES_B64: dict[str, str] = {",
    ]

    for rel_path, (encoded, _) in sources.items():
        lines.append(f"    {rel_path!r}: {encoded!r},")

    lines.append("}")
    lines.append("")
    lines.append("SOURCES_SHA256: dict[str, str] = {")
    for rel_path, (_, digest) in sources.items():
        lines.append(f"    {rel_path!r}: {digest!r},")

    lines.extend(
        [
            "}",
            "",
            "",
            "def _is_suspicious(content: str) -> list[str]:",
            "    findings: list[str] = []",
            "    for snippet in SUSPICIOUS_SNIPPETS:",
            "        if snippet in content:",
            "            findings.append(f\"contains {snippet!r}\")",
            "",
            "    if content.count('\\n') <= 1 and '\\\\n' in content:",
            "        findings.append('looks like escaped single-line source')",
            "",
            "    if content.count('\\\\') > 20 and content.count('\\n') < 5:",
            "        findings.append('high backslash density with low real newlines')",
            "",
            "    return findings",
            "",
            "",
            "def _install(root: pathlib.Path) -> None:",
            "    for rel_path, encoded in SOURCES_B64.items():",
            "        path = root / rel_path",
            "        path.parent.mkdir(parents=True, exist_ok=True)",
            "        content = base64.b64decode(encoded).decode('utf-8')",
            "        path.write_text(content, encoding='utf-8')",
            "",
            "",
            "def _verify(root: pathlib.Path) -> None:",
            "    for rel_path in sorted(SOURCES_B64):",
            "        path = root / rel_path",
            "        if not path.exists():",
            "            raise RuntimeError(f'missing file: {rel_path}')",
            "        content = path.read_text(encoding='utf-8')",
            "        findings = _is_suspicious(content)",
            "        if findings:",
            "            details = '; '.join(findings)",
            "            raise RuntimeError(",
            "                f'integrity failed for {rel_path}: {details}'",
            "            )",
            "        digest = hashlib.sha256(content.encode('utf-8')).hexdigest()",
            "        expected = SOURCES_SHA256[rel_path]",
            "        if digest != expected:",
            "            raise RuntimeError(f'hash mismatch for {rel_path}')",
            "        ast.parse(content, filename=rel_path)",
            "",
            "",
            "def _doctor(root: pathlib.Path) -> None:",
            "    src = root / 'src'",
            "    src_str = str(src)",
            "    if src_str not in sys.path:",
            "        sys.path.insert(0, src_str)",
            "",
            "    from ecs import World  # noqa: F401",
            "    from ttrpg_engine import KernelState  # noqa: F401",
            "    from ttrpg_5e import Actor5eFactory  # noqa: F401",
            "",
            "",
            "def main() -> int:",
            "    parser = argparse.ArgumentParser()",
            "    parser.add_argument(",
            "        '--root', default='.', help='target root directory'",
            "    )",
            "    parser.add_argument('--no-install', action='store_true')",
            "    parser.add_argument('--no-verify', action='store_true')",
            "    parser.add_argument('--no-doctor', action='store_true')",
            "    args = parser.parse_args()",
            "",
            "    root = pathlib.Path(args.root).resolve()",
            "    if not args.no_install:",
            "        _install(root)",
            "        print('install=ok')",
            "    if not args.no_verify:",
            "        _verify(root)",
            "        print('verify=ok')",
            "    if not args.no_doctor:",
            "        _doctor(root)",
            "        print('doctor=ok')",
            "    print(f'root={root}')",
            "    return 0",
            "",
            "",
            "if __name__ == '__main__':",
            "    raise SystemExit(main())",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="scripts/grok_repl_bundle.py",
        help="bundle output path relative to repo root",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    sources = _collect_sources(repo_root)
    bundle = _render_bundle(sources)

    output_path = (repo_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(bundle, encoding="utf-8")

    print(f"bundle_path={output_path}")
    print(f"source_count={len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
