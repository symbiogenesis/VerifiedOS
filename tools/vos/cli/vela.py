# SPDX-License-Identifier: Apache-2.0
"""Format, lint and check pure Vela, or emit its unqualified Gallina translation."""

import argparse
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

from vos.atomic import atomic_path
from vos.vela import MAX_SOURCE_BYTES, VelaError, translate
from vos.vela.authoring import LINT_CODES, format_source, lint_source, preview_bindings


@dataclass(frozen=True)
class _Source:
    path: Path
    data: bytes
    identity: tuple[int, int, int, int]
    mode: int


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    # Windows path stat and descriptor fstat expose different legacy ctime
    # meanings after a write. File identity, size, mtime and exact bytes agree.
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _read_source(path: Path) -> _Source:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise OSError("source must be a regular file, not a symbolic link or special file")
    with path.open("rb") as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(before):
            raise OSError("source changed while it was opened")
        data = stream.read(MAX_SOURCE_BYTES + 1)
    if _identity(path.lstat()) != _identity(before):
        raise OSError("source changed while it was read")
    return _Source(path, data, _identity(before), stat.S_IMODE(before.st_mode))


def _unchanged(source: _Source) -> None:
    current = _read_source(source.path)
    if current.identity != source.identity or current.data != source.data:
        raise OSError("source changed during compilation; no pending source rewrite was applied")


def _destination(source: Path, destination: Path) -> None:
    if (source.resolve() == destination.resolve()
            or (destination.exists() and source.samefile(destination))):
        raise OSError("output aliases the input")
    if not destination.parent.is_dir():
        raise OSError("output parent directory does not exist")
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise OSError("output must be a regular file, not a symbolic link or special file")


def _rewrite(source: _Source, formatted: bytes) -> _Source:
    _unchanged(source)
    if formatted == source.data:
        return source
    with atomic_path(source.path) as pending:
        pending.write_bytes(formatted)
        pending.chmod(source.mode)
        _unchanged(source)
    current = _read_source(source.path)
    if current.data != formatted:
        raise OSError("source changed after formatting; generated output was not published")
    return current


def _lint(path: Path, source: bytes, allowed: set[str], denied: set[str], *,
          require_complete: bool = True) -> bool:
    failed = False
    try:
        findings = lint_source(source)
    except VelaError as error:
        if error.kind != "inspection-limit":
            raise
        level = "error" if require_complete else "warning"
        print(f"{path}:{error.line}:{error.column}: {level} lint-unavailable: {error.message}",
              file=sys.stderr)
        return not require_complete
    for finding in findings:
        if finding.code in allowed:
            continue
        is_error = finding.code in denied
        failed |= is_error
        level = "error" if is_error else "warning"
        print(f"{path}:{finding.line}:{finding.column}: {level} {finding.code}: {finding.message}",
              file=sys.stderr)
    return not failed


def _preview_output(candidate: bytes) -> None:
    binary = cast("BinaryIO | None", getattr(sys.stdout, "buffer", None))
    if binary is None:
        sys.stdout.write(candidate.decode("utf-8"))
    else:
        binary.write(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "emit", "fmt", "lint"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
        if name == "fmt":
            command.add_argument("--check", action="store_true",
                                 help="report formatting differences without writing")
        else:
            command.add_argument("--allow", action="append", choices=sorted(LINT_CODES), default=[],
                                 help="suppress an optional lint (repeatable)")
            command.add_argument("--deny", action="append", choices=sorted(LINT_CODES), default=[],
                                 help="make an optional lint an error (repeatable)")
        if name == "lint":
            command.add_argument("--preview-bindings", action="store_true",
                                 help="print a checked explicit-let candidate without writing source")
        if name in {"check", "emit"}:
            command.add_argument("--format", choices=("write", "check", "off"), default="off",
                                 help="source formatting mode (default: off; write requires explicit opt-in)")
            command.add_argument("--no-lint", action="store_true",
                                 help="disable optional lints; language checks remain required")
        if name == "emit":
            command.add_argument("--output", type=Path,
                                 help="atomically replace a file in an existing directory")
    args = parser.parse_args(argv)
    allowed = set(getattr(args, "allow", []))
    denied = set(getattr(args, "deny", []))
    if allowed & denied:
        parser.error("a lint cannot be both allowed and denied")
    if getattr(args, "no_lint", False) and (allowed or denied):
        parser.error("--no-lint cannot be combined with --allow or --deny")
    path = Path(args.source)
    try:
        source = _read_source(path)
        # A failed complete check never rewrites even syntactically valid input.
        translation = translate(source.data)
        if args.command == "lint":
            if not _lint(path, source.data, allowed, denied):
                return 1
            if args.preview_bindings:
                candidate = source.data if "VELA104" in allowed else preview_bindings(source.data)
                _unchanged(source)
                _preview_output(candidate)
            return 0
        formatting = "check" if args.command == "fmt" and args.check else (
            "write" if args.command == "fmt" else args.format)
        candidate = source.data if formatting == "off" else format_source(source.data)
        if formatting == "check" and candidate != source.data:
            print(f"{path}:1:1: format: source differs from Vela style; run vela fmt", file=sys.stderr)
            return 1
        # Fresh emission and lint locations bind exactly the candidate bytes.
        if candidate != source.data:
            translation = translate(candidate)
        if args.command != "fmt" and not args.no_lint:
            # A denied lint keeps the original source unchanged, so its locations
            # must describe that original snapshot, not the uncommitted layout.
            try:
                findings = lint_source(source.data)
            except VelaError as error:
                if error.kind != "inspection-limit":
                    raise
                if denied:
                    _lint(path, source.data, allowed, denied)
                    return 1
                findings = ()
            if any(finding.code in denied for finding in findings):
                _lint(path, source.data, allowed, denied)
                return 1
        destination = args.output if args.command == "emit" else None
        if destination is not None:
            _destination(path, destination)
            # Stage output before changing source, so a preparation failure writes neither.
            with atomic_path(destination) as pending:
                pending.write_text(translation.gallina, encoding="utf-8", newline="")
                _destination(path, destination)
                current = _rewrite(source, candidate)
                _unchanged(current)
        else:
            current = _rewrite(source, candidate)
            _unchanged(current)
        if (args.command != "fmt" and not args.no_lint
                and not _lint(path, candidate, allowed, denied, require_complete=bool(denied))):
            return 1
        if args.command == "check":
            print(f"ok vela: {translation.module}: pure prototype checked; unqualified")
        elif args.command == "emit" and destination is None:
            print(translation.gallina, end="")
        elif args.command == "fmt":
            print(f"ok vela: {translation.module}: style checked" if args.check else
                  f"ok vela: {translation.module}: source formatted")
    except VelaError as error:
        print(f"{path}:{error.line}:{error.column}: {error.kind}: {error.message}",
              file=sys.stderr)
        return 1
    except OSError as error:
        print(f"{path}:1:1: io: {error}", file=sys.stderr)
        return 1
    return 0
