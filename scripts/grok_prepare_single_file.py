#!/usr/bin/env python3
"""Build a plain single-file source installer for Grok-style REPL bootstrapping.

This generator scans src/*.py and emits scripts/grok_src_dropper.py.
The generated file contains plain source text (not base64) and writes it to disk.
"""

from __future__ import annotations

import argparse
import ast
import pathlib

SUSPICIOUS_SNIPPETS = (
    'text"""',
    "\\__all__",
    "\\[",
    "\\]",
)


def _check_source(content: str, rel_path: str) -> None:
    for snippet in SUSPICIOUS_SNIPPETS:
        if snippet in content:
            raise RuntimeError(f"integrity failed for {rel_path}: contains {snippet!r}")

    if content.count("\n") <= 1 and "\\n" in content:
        raise RuntimeError(
            f"integrity failed for {rel_path}: looks like escaped single-line source"
        )

    ast.parse(content, filename=rel_path)


def _collect_sources(repo_root: pathlib.Path) -> dict[str, str]:
    src_root = repo_root / "src"
    sources: dict[str, str] = {}

    for path in sorted(src_root.rglob("*.py")):
        rel_path = str(path.relative_to(repo_root))
        content = path.read_text(encoding="utf-8")
        _check_source(content, rel_path)
        sources[rel_path] = content

    if not sources:
        raise RuntimeError("no src/*.py files found")

    return sources


def _render_dropper(sources: dict[str, str]) -> str:
    lines = [
        "#!/usr/bin/env python3",
        '"""Plain source dropper for Grok REPL deployment."""',
        "",
        "from __future__ import annotations",
        "",
        "import argparse",
        "import ast",
        "import pathlib",
        "",
        "SOURCES: dict[str, str] = {",
    ]

    for rel_path, content in sources.items():
        lines.append(f"    {rel_path!r}: {content!r},")

    lines.extend(
        [
            "}",
            "",
            "",
            "def install(root: pathlib.Path) -> None:",
            "    for rel_path, content in SOURCES.items():",
            "        path = root / rel_path",
            "        path.parent.mkdir(parents=True, exist_ok=True)",
            "        path.write_text(content, encoding='utf-8')",
            "",
            "",
            "def verify(root: pathlib.Path) -> None:",
            "    for rel_path in sorted(SOURCES):",
            "        content = (root / rel_path).read_text(encoding='utf-8')",
            "        ast.parse(content, filename=rel_path)",
            "",
            "",
            "def main() -> int:",
            "    parser = argparse.ArgumentParser()",
            "    parser.add_argument('--root', default='.')",
            "    parser.add_argument('--no-verify', action='store_true')",
            "    args = parser.parse_args()",
            "",
            "    root = pathlib.Path(args.root).resolve()",
            "    install(root)",
            "    print('install=ok')",
            "    if not args.no_verify:",
            "        verify(root)",
            "        print('verify=ok')",
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
        default="scripts/grok_src_dropper.py",
        help="output path relative to repo root",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    sources = _collect_sources(repo_root)
    output = _render_dropper(sources)

    output_path = (repo_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")

    print(f"dropper_path={output_path}")
    print(f"source_count={len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
