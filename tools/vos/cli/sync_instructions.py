# SPDX-License-Identifier: Apache-2.0
"""Validate AGENTS.md as the shared source and CLAUDE.md as its import."""

import argparse
import os
import stat
import tempfile
from pathlib import Path

from vos.corpus import find_root

NAMES = ("AGENTS.md", "CLAUDE.md")
IMPORT = b"@AGENTS.md\n"
IMPORTS = (IMPORT, b"@AGENTS.md\r\n")
RESOLVE = "move any CLAUDE.md instructions into AGENTS.md, preserving both sets of " \
          "edits, then replace CLAUDE.md with the single line `@AGENTS.md`"


class SyncError(ValueError):
    """The shared instructions or their import cannot be safely validated."""


def _read(root: Path) -> dict[str, bytes | None]:
    """Read only the named regular files; never follow a link outside the checkout."""
    found: dict[str, bytes | None] = {}
    for name in NAMES:
        path = root / name
        try:
            before = path.lstat()
        except FileNotFoundError:
            found[name] = None
            continue
        if not stat.S_ISREG(before.st_mode) or path.resolve().parent != root:
            raise SyncError(f"{name} must be a regular file directly inside {root}")
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise SyncError(f"{name} changed while opening it; rerun")
            found[name] = handle.read()
    return found


def _create(temporary: Path, target: Path) -> None:
    os.link(temporary, target)


def _replace(temporary: Path, target: Path) -> None:
    temporary.replace(target)


def _publish_import(root: Path, expected: dict[str, bytes | None]) -> None:
    """Publish complete import bytes after checking that neither input changed.

    Creation uses an exclusive hard link so a concurrently created CLAUDE.md cannot
    be overwritten. Migration replaces only the reviewed equal copy. As with any
    editor using atomic replacement, editors must coordinate the final replacement
    window; the content recheck catches changes during preparation.
    """
    temporary: Path | None = None
    target = root / "CLAUDE.md"
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".instruction-sync-",
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(IMPORT)
            handle.flush()
            os.fsync(handle.fileno())
        if _read(root) != expected:
            raise SyncError("instruction files changed while preparing the import; rerun")
        if expected["CLAUDE.md"] is None:
            _create(temporary, target)
        else:
            temporary.chmod(stat.S_IMODE(target.stat().st_mode))
            _replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def sync(root: Path, *, check: bool = False, source: str | None = None,
         migrate: bool = False) -> str:
    """Validate without Git or checkpoints; only create or explicitly migrate the import.

    AGENTS.md is never written. Legacy copies migrate only when their bytes agree,
    and unexpected CLAUDE.md content is always left for its owner to reconcile.
    """
    if source is not None:
        raise SyncError("--from is retired because AGENTS.md is the shared source; " + RESOLVE)
    if check and migrate:
        raise SyncError("--check is read-only and cannot be combined with --migrate")
    root = root.resolve(strict=True)
    current = _read(root)
    agents, claude = (current[name] for name in NAMES)
    if agents is None:
        raise SyncError("AGENTS.md is missing; restore the shared instructions there first")
    try:
        text = agents.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyncError("AGENTS.md must contain valid UTF-8 instructions") from exc
    if not text.removeprefix("\ufeff").strip():
        raise SyncError("AGENTS.md must contain nonempty shared instructions")
    if claude in IMPORTS:
        return "AGENTS.md is the shared source; CLAUDE.md imports it"
    if claude is None:
        if check:
            raise SyncError("CLAUDE.md is missing; run `python tools/run.py sync-instructions` "
                            "to create its AGENTS.md import")
        action = "created"
    elif claude == agents:
        if not migrate:
            raise SyncError("CLAUDE.md is a legacy copy; run "
                            "`python tools/run.py sync-instructions --migrate` "
                            "to replace the identical copy with an AGENTS.md import")
        action = "migrated"
    else:
        raise SyncError("CLAUDE.md must contain only `@AGENTS.md` and a final newline; " + RESOLVE)
    _publish_import(root, current)
    if _read(root) != {"AGENTS.md": agents, "CLAUDE.md": IMPORT}:
        raise SyncError("instruction files changed before import publication completed; rerun")
    return f"{action} CLAUDE.md as an import of AGENTS.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="validate without writing")
    action.add_argument("--migrate", action="store_true",
                        help="replace CLAUDE.md with an import only if it exactly copies AGENTS.md")
    action.add_argument("--from", dest="source",
                        help="retired: put all shared instructions in AGENTS.md")
    args = parser.parse_args(argv)
    try:
        print(sync(find_root(), check=args.check, source=args.source, migrate=args.migrate))
    except (OSError, ValueError) as err:
        print(f"instruction validation failed: {err}")
        return 1
    return 0
