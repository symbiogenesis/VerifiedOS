# SPDX-License-Identifier: Apache-2.0
"""Independent default-formatting, lint-policy and publication refusal controls."""

import hashlib
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.cli import vela as cli
from vos.vela import MAX_SOURCE_BYTES, VelaError, translate

INDEPENDENT_CASES = True

_COMPACT = (b"module Example;\n/// Scales a count.\n"
            b"public Nat Scale(Nat value){return value+1_000;}")
_FORMATTED = (b"module Example;\n\n/// Scales a count.\n"
              b"public Nat Scale(Nat value)\n{\n    return value + 1_000;\n}\n")


def _call(arguments: list[str]) -> tuple[int, str, str]:
    with redirect_stdout(out := StringIO()), redirect_stderr(err := StringIO()):
        try:
            code = cli.main(arguments)
        except SystemExit as error:
            code = int(str(error.code))
    return code, out.getvalue(), err.getvalue()


def _defaults_and_provenance() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-default-style-") as directory:
        source = Path(directory) / "source.vela"
        source.write_bytes(_COMPACT)
        code, output, errors = _call(["check", str(source)])
        ensure(code == 0 and "unqualified" in output and not errors,
               f"default authoring command failed: {errors}")
        ensure(source.read_bytes() == _FORMATTED, "normal check did not write canonical Allman layout")
        source.write_bytes(_COMPACT)
        code, output, errors = _call(["emit", str(source)])
        ensure(code == 0 and not errors, f"default emission failed: {errors}")
        ensure(output == translate(_FORMATTED).gallina, "emission did not use the post-format source")
        ensure(hashlib.sha256(_FORMATTED).hexdigest() in output,
               "emitted provenance retained the original source digest")
        ensure(hashlib.sha256(_COMPACT).hexdigest() not in output,
               "pre-format provenance survived source rewriting")
        before = source.stat().st_mtime_ns
        code, _, errors = _call(["check", str(source)])
        ensure(code == 0 and not errors and source.stat().st_mtime_ns == before,
               "already canonical source was rewritten")


def _explicit_modes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-style-modes-") as directory:
        source = Path(directory) / "source.vela"
        source.write_bytes(_COMPACT)
        for command in (["fmt", str(source), "--check"],
                        ["check", str(source), "--format", "check"]):
            code, _, errors = _call(command)
            ensure(code == 1 and "format:" in errors and source.read_bytes() == _COMPACT,
                   "check-only formatting did not refuse without writes")
        code, output, errors = _call(["emit", str(source), "--format", "off"])
        ensure(code == 0 and not errors and source.read_bytes() == _COMPACT,
               "format off changed source")
        ensure(output == translate(_COMPACT).gallina, "format off changed exact source provenance")
        code, _, errors = _call(["fmt", str(source)])
        ensure(code == 0 and not errors and source.read_bytes() == _FORMATTED,
               "explicit formatter did not write canonical source")
        code, _, errors = _call(["fmt", str(source), "--check"])
        ensure(code == 0 and not errors, "canonical source failed format checking")


def _lint_policy() -> None:
    raw = b"module Example;public bool bad(bool Flag)=>Flag==true;"
    with tempfile.TemporaryDirectory(prefix="vos-vela-lint-policy-") as directory:
        source = Path(directory) / "source.vela"
        source.write_bytes(raw)
        code, output, errors = _call(["lint", str(source)])
        ensure(code == 0 and not output and source.read_bytes() == raw,
               "advisory linting failed or rewrote source")
        for identifier in ("VELA100", "VELA101", "VELA102", "VELA103"):
            ensure(f"warning {identifier}:" in errors, f"default lint {identifier} was not reported")
        code, output, errors = _call(["emit", str(source), "--deny", "VELA100"])
        ensure(code == 1 and not output and source.read_bytes() == raw,
               "a denied lint rewrote source or emitted output")
        ensure(f":1:{raw.index(b'bad') + 1}: error VELA100:" in errors,
               "denied-lint location describes uncommitted formatted source")
        allowed = [part for identifier in ("VELA100", "VELA101", "VELA102", "VELA103")
                   for part in ("--allow", identifier)]
        code, _, errors = _call(["check", str(source), *allowed])
        ensure(code == 0 and not errors, "explicit lint suppression was not honored")
        source.write_bytes(raw)
        code, output, errors = _call(["emit", str(source), "--format", "off", "--no-lint"])
        ensure(code == 0 and not errors and output == translate(raw).gallina,
               "lint opt-out disabled language checking or changed output")
        for arguments in (["--allow", "VELA999"],
                          ["--deny", "VELA100", "--allow", "VELA100"],
                          ["--no-lint", "--deny", "VELA100"]):
            code, output, _ = _call(["check", str(source), *arguments])
            ensure(code == 2 and not output and source.read_bytes() == raw,
                   "invalid lint policy was silently accepted or wrote source")


def _refusals_preserve_files() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-style-refusal-") as directory:
        root = Path(directory)
        source, output = root / "source.vela", root / "output.v"
        sentinel = b"previous generated artifact"
        output.write_bytes(sentinel)
        for raw in (b"module M;public Nat Broken()=>true;",
                    b"module M; public Nat Broken()=>1__000;",
                    b"module M; public Nat Broken(ref Nat value)=>value;",
                    b"\xff", b" " * (MAX_SOURCE_BYTES + 1)):
            source.write_bytes(raw)
            code, stdout, _ = _call(["emit", str(source), "--output", str(output)])
            ensure(code == 1 and not stdout and source.read_bytes() == raw,
                   "invalid source was formatted or emitted")
            ensure(output.read_bytes() == sentinel, "invalid source replaced generated output")
        source.write_bytes(_COMPACT)
        for destination in (source, root / "absent" / "output.v", root):
            code, stdout, errors = _call(["emit", str(source), "--output", str(destination)])
            ensure(code == 1 and not stdout and ": io:" in errors,
                   "invalid output destination was not diagnosed")
            ensure(source.read_bytes() == _COMPACT, "invalid output destination still reformatted source")
        alias = root / "hardlink.v"
        alias.hardlink_to(source)
        code, _, errors = _call(["emit", str(source), "--output", str(alias)])
        ensure(code == 1 and "aliases" in errors and source.read_bytes() == _COMPACT,
               "hardlink output alias escaped pre-format refusal")
        with patch.object(Path, "replace", side_effect=OSError("injected replacement failure")):
            code, _, errors = _call(["emit", str(source), "--output", str(output)])
        ensure(code == 1 and "injected replacement failure" in errors,
               "source publication failure was not diagnosed")
        ensure(source.read_bytes() == _COMPACT and output.read_bytes() == sentinel,
               "failed source publication changed input or output")
        ensure(not list(root.glob(".*.tmp")), "failed publication leaked temporary files")


def _concurrent_edit_and_special_files() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-style-snapshot-") as directory:
        root = Path(directory)
        source, output = root / "source.vela", root / "output.v"
        source.write_bytes(_COMPACT)
        output.write_bytes(b"previous")
        changed = b"module Example;public Nat Other()=>7;"

        def edit_during_format(_: bytes) -> bytes:
            source.write_bytes(changed)
            return _FORMATTED

        with patch.object(cli, "format_source", side_effect=edit_during_format):
            code, stdout, errors = _call(["emit", str(source), "--output", str(output)])
        ensure(code == 1 and not stdout and "source changed" in errors,
               "concurrent edit was not refused")
        ensure(source.read_bytes() == changed and output.read_bytes() == b"previous",
               "concurrent editor or previous output was overwritten")
        code, _, errors = _call(["check", str(root)])
        ensure(code == 1 and "regular file" in errors, "directory input was not refused")
        alias = root / "source-link.vela"
        try:
            alias.symlink_to(source)
        except OSError:
            ensure(os.name == "nt", "unexpected inability to create symlink")
        else:
            code, _, errors = _call(["check", str(alias)])
            ensure(code == 1 and "symbolic link" in errors and source.read_bytes() == changed,
                   "default formatting followed a source symlink")


def _unavailable_lints() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-lint-unavailable-") as directory:
        source = Path(directory) / "source.vela"
        source.write_bytes(_COMPACT)
        unavailable = VelaError("inspection-limit", 1, 1, "compiler inspection budget exhausted")
        with patch.object(cli, "lint_source", side_effect=unavailable):
            code, output, errors = _call(["check", str(source)])
            ensure(code == 0 and "unqualified" in output and "warning lint-unavailable:" in errors,
                   "optional lint unavailability changed compiler acceptance or claimed clean findings")
            ensure(source.read_bytes() == _FORMATTED, "advisory lint limits disabled default formatting")
            source.write_bytes(_COMPACT)
            for arguments in (["lint", str(source)],
                              ["emit", str(source), "--deny", "VELA100"]):
                code, output, errors = _call(arguments)
                ensure(code == 1 and not output and "error lint-unavailable:" in errors,
                       "required lint completeness was not enforced")
                ensure(source.read_bytes() == _COMPACT, "incomplete required lints rewrote source")


def cases() -> list[Case]:
    return [Case("vela-authoring-cli:defaults-and-provenance", _defaults_and_provenance),
            Case("vela-authoring-cli:explicit-modes", _explicit_modes),
            Case("vela-authoring-cli:lint-policy", _lint_policy),
            Case("vela-authoring-cli:refusal-publication", _refusals_preserve_files),
            Case("vela-authoring-cli:source-snapshot", _concurrent_edit_and_special_files),
            Case("vela-authoring-cli:lint-unavailable", _unavailable_lints)]
