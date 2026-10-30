# SPDX-License-Identifier: Apache-2.0
"""Stage a selected local Gallina dependency closure and bind its source bytes.

The source index owns Require parsing and dependency order. This module only
selects roots, copies their closure and checks the bytes a comparison consumed.
It invokes no prover and confers no compilation or proof verdict.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from vos import proofs
from vos.receipts import atomic_path, digest


class StagingError(ValueError):
    """A selected proof closure cannot be staged or no longer has its bound bytes."""


def _selected(root: Path, entries: tuple[str, ...]) -> tuple[Path, ...]:
    if not entries or len(set(entries)) != len(entries):
        raise StagingError("proof entry points must be nonempty and distinct")
    if any(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*\.v", name) is None for name in entries):
        raise StagingError("proof entry points must be plain module filenames")
    folder = root / "proofs"
    sources = sorted(folder.glob("*.v"))
    by_name = {source.name: source for source in sources}
    missing = [name for name in entries if name not in by_name]
    if missing:
        raise StagingError("unknown proof entry point: " + ", ".join(missing))
    if any(source.is_symlink() or not source.is_file() for source in sources):
        raise StagingError("proof sources must be regular files")
    try:
        index = proofs.SourceIndex.read(sources)
    except SystemExit as error:
        raise StagingError(str(error)) from error
    selected = {by_name[name] for name in entries}
    selected.update(dependency for source in tuple(selected) for dependency in index.imports[source])
    return tuple(source for wave in index.ordered for source in wave if source in selected)


def inputs(root: Path, entries: tuple[str, ...]) -> dict[str, str]:
    """Bind every selected source without staging or invoking the toolchain."""
    root = root.resolve()
    return {source.relative_to(root).as_posix(): digest(source)
            for source in _selected(root, entries)}


@dataclass(frozen=True)
class Staged:
    """A private staged closure in compile order, with immutable input identities."""

    sources: tuple[Path, ...]
    _root: Path
    _entries: tuple[str, ...]
    _expected: tuple[tuple[str, str], ...]

    @property
    def inputs(self) -> dict[str, str]:
        """Return a receipt-ready copy; callers cannot alter the retained identities."""
        return dict(self._expected)

    def validate(self, root: Path) -> None:
        """Refuse changed closure membership, original sources or staged sources."""
        root = root.resolve()
        if root != self._root:
            raise StagingError("proof staging belongs to another source checkout")
        current = _selected(root, self._entries)
        if tuple(source.relative_to(root).as_posix() for source in current) != tuple(self.inputs):
            raise StagingError("proof dependency closure changed during comparison")
        for staged, (name, expected) in zip(self.sources, self._expected, strict=True):
            if digest(root / name) != expected:
                raise StagingError(f"proof source bytes changed during comparison: {name}")
            if digest(staged) != expected:
                raise StagingError(f"staged proof bytes changed during comparison: {name}")


def stage(root: Path, destination: Path, entries: tuple[str, ...]) -> Staged:
    """Copy only the selected local closure, preserving bytes and compile order."""
    root, destination = root.resolve(), destination.resolve()
    sources = _selected(root, entries)
    if destination.is_relative_to(root / "proofs"):
        raise StagingError("proof staging must not overwrite the source directory")
    destination.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    expected: list[tuple[str, str]] = []
    for source in sources:
        target = destination / source.name
        with atomic_path(target) as pending:
            pending.write_bytes(source.read_bytes())
        staged.append(target)
        expected.append((source.relative_to(root).as_posix(), digest(target)))
    result = Staged(tuple(staged), root, entries, tuple(expected))
    result.validate(root)
    return result
