# SPDX-License-Identifier: Apache-2.0
"""Read local Python implementation dependencies without importing inspected code.

Lexical imports, including function and conditional imports, determine the closure
under ``tools/``. Callers explicitly seed dynamic command targets and subprocess
scripts, and bind their non-Python inputs separately. No filesystem or parse cache
survives a call, so a changed import edge is read from the selected checkout.
"""

import ast
import stat
import symtable
from collections.abc import Iterable
from pathlib import Path


def sources(root: Path, entrypoints: Iterable[str]) -> tuple[str, ...]:
    """Return sorted checkout-relative sources for explicit Python entry points.

    Missing project-local modules refuse rather than disappearing from identity.
    A ``from`` member may instead be a statically bound attribute of its module;
    the symbol table distinguishes those exports from missing helper modules.
    """
    boundary = root.resolve()
    tools = boundary / "tools"
    if tools.resolve() != tools:
        raise ValueError("Python dependency root must not redirect outside tools")
    parsed: dict[Path, tuple[ast.Module, frozenset[str]]] = {}
    found: set[Path] = set()
    pending: list[Path] = []

    def regular(path: Path) -> bool:
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            return False
        if path.resolve() != path or not path.is_relative_to(tools):
            raise ValueError(f"Python dependency path must stay within tools: {path}")
        return stat.S_ISREG(mode)

    def read(path: Path) -> tuple[ast.Module, frozenset[str]]:
        if path not in parsed:
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text, filename=str(path))
                symbols = symtable.symtable(text, str(path), "exec")
            except SyntaxError as error:
                raise ValueError(f"invalid Python dependency: {path}: {error}") from error
            bound = frozenset(symbol.get_name() for symbol in symbols.get_symbols()
                              if symbol.is_assigned() or symbol.is_imported()
                              or symbol.is_namespace())
            parsed[path] = tree, bound
        return parsed[path]

    def module(name: str) -> Path | None:
        base = tools.joinpath(*name.split("."))
        for path in (base / "__init__.py", base.with_suffix(".py")):
            if regular(path):
                return path
        return None

    entries = tuple(entrypoints)
    if not entries:
        raise ValueError("Python dependencies require at least one entry point")
    local: set[str] = set()
    for entry in entries:
        path = boundary / entry
        if (not entry or "\\" in entry or Path(entry).is_absolute()
                or ".." in Path(entry).parts or path.suffix != ".py"
                or not path.is_relative_to(tools) or not regular(path)):
            raise ValueError(f"missing or invalid Python entry point: {entry}")
        pending.append(path)
        local.add(path.relative_to(tools).parts[0].removesuffix(".py"))

    def add(name: str, *, required: bool) -> Path | None:
        path = module(name)
        if path is None:
            if required:
                raise ValueError(f"missing local Python dependency: {name}")
            return None
        pending.append(path)
        parts = name.split(".")
        for length in range(1, len(parts)):
            parent = module(".".join(parts[:length]))
            if parent is None or parent.name != "__init__.py":
                raise ValueError(f"missing local Python package: {'.'.join(parts[:length])}")
            pending.append(parent)
        return path

    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        tree, _ = read(path)
        relative = path.relative_to(tools)
        parts = (*relative.parts[:-1], path.stem)
        package = relative.parts[:-1]
        if path.name == "__init__.py":
            parts = package
        for length in range(1, len(parts)):
            add(".".join(parts[:length]), required=True)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    add(alias.name, required=top in local or module(top) is not None)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if node.level > len(package):
                        raise ValueError(f"relative Python import escapes its package: {path}")
                    anchor = package[:len(package) + 1 - node.level]
                else:
                    anchor = ()
                name = ".".join((*anchor, *((node.module,) if node.module else ())))
                top = name.split(".")[0]
                imported = add(name, required=bool(node.level) or top in local
                               or module(top) is not None)
                if imported is None:
                    continue
                _, bound = read(imported)
                for alias in node.names:
                    if alias.name == "*":
                        raise ValueError(f"wildcard local Python import is unsupported: {path}")
                    member = f"{name}.{alias.name}"
                    if module(member) is not None:
                        add(member, required=True)
                    elif alias.name not in bound:
                        raise ValueError(f"missing local Python dependency or export: {member}")
    return tuple(sorted(path.relative_to(boundary).as_posix() for path in found))
