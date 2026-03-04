#!/usr/bin/env python3
"""Build a single-file in-memory runtime module for REPL environments.

The generated script embeds all ``src/*.py`` files and installs an import hook
that serves project modules directly from memory.
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


def _path_to_module_name(path: pathlib.Path) -> str:
    parts = path.parts
    if parts[-1] == "__init__.py":
        return ".".join(parts[:-1])
    return ".".join(parts[:-1] + (parts[-1][:-3],))


def _collect_modules(repo_root: pathlib.Path) -> tuple[dict[str, str], set[str]]:
    src_root = repo_root / "src"
    modules: dict[str, str] = {}
    package_modules: set[str] = set()

    for path in sorted(src_root.rglob("*.py")):
        rel_from_src = path.relative_to(src_root)
        rel_path = str(path.relative_to(repo_root))
        content = path.read_text(encoding="utf-8")
        _check_source(content, rel_path)

        module_name = _path_to_module_name(rel_from_src)
        modules[module_name] = content
        if rel_from_src.name == "__init__.py":
            package_modules.add(module_name)

    if not modules:
        raise RuntimeError("no src/*.py files found")

    return modules, package_modules


def _render_unified_runtime(
    modules: dict[str, str],
    package_modules: set[str],
) -> str:
    lines = [
        "#!/usr/bin/env python3",
        '"""Unified in-memory runtime for Grok REPL."""',
        "",
        "from __future__ import annotations",
        "",
        "import argparse",
        "import importlib.abc",
        "import importlib.util",
        "import sys",
        "",
        "MODULE_SOURCES: dict[str, str] = {",
    ]

    for module_name, content in modules.items():
        lines.append(f"    {module_name!r}: {content!r},")

    lines.extend(
        [
            "}",
            "",
            "PACKAGE_MODULES: set[str] = {",
        ]
    )
    for module_name in sorted(package_modules):
        lines.append(f"    {module_name!r},")
    lines.extend(
        [
            "}",
            "",
            "",
            "class _UnifiedSourceLoader(importlib.abc.Loader):",
            "    def __init__(self, module_name: str) -> None:",
            "        self.module_name = module_name",
            "",
            "    def create_module(self, spec):",
            "        return None",
            "",
            "    def exec_module(self, module) -> None:",
            "        source = MODULE_SOURCES[self.module_name]",
            "        module.__file__ = f'<unified:{self.module_name}>'",
            "        if self.module_name in PACKAGE_MODULES:",
            "            module.__path__ = []",
            "            module.__package__ = self.module_name",
            "        else:",
            "            module.__package__ = self.module_name.rpartition('.')[0]",
            "        code = compile(source, module.__file__, 'exec')",
            "        exec(code, module.__dict__)",
            "",
            "",
            "class _UnifiedSourceFinder(importlib.abc.MetaPathFinder):",
            "    def find_spec(self, fullname, path=None, target=None):",
            "        if fullname not in MODULE_SOURCES:",
            "            return None",
            "        loader = _UnifiedSourceLoader(fullname)",
            "        return importlib.util.spec_from_loader(",
            "            fullname,",
            "            loader,",
            "            is_package=fullname in PACKAGE_MODULES,",
            "        )",
            "",
            "",
            "_FINDER: _UnifiedSourceFinder | None = None",
            "",
            "",
            "def install_importer() -> None:",
            "    global _FINDER",
            "    if _FINDER is not None:",
            "        return",
            "    _FINDER = _UnifiedSourceFinder()",
            "    sys.meta_path.insert(0, _FINDER)",
            "",
            "",
            "def check_imports() -> None:",
            "    install_importer()",
            "    from ecs import World  # noqa: F401",
            "    from ttrpg_engine import KernelState  # noqa: F401",
            "    from ttrpg_5e import Actor5eFactory  # noqa: F401",
            "",
            "",
            "def main() -> int:",
            "    parser = argparse.ArgumentParser()",
            "    parser.add_argument('--check', action='store_true')",
            "    args = parser.parse_args()",
            "",
            "    install_importer()",
            "    print('importer=installed')",
            "    if args.check:",
            "        check_imports()",
            "        print('check=ok')",
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
        default="scripts/grok_unified_engine.py",
        help="output path relative to repo root",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    modules, package_modules = _collect_modules(repo_root)
    output = _render_unified_runtime(modules, package_modules)

    output_path = (repo_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")

    print(f"unified_path={output_path}")
    print(f"module_count={len(modules)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
