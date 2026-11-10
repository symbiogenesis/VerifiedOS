# SPDX-License-Identifier: Apache-2.0
"""Standalone copy recipe closure, source snapshot and publication controls."""

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import copy_package as package
from vos import copy_service
from vos.cli import copy_service as cli


@contextmanager
def _fixture() -> Generator[tuple[Path, Path]]:
    with tempfile.TemporaryDirectory(prefix="vos-copy-package-test-") as temporary:
        root = Path(temporary).resolve() / "checkout"
        for relative in package.source_paths(TOOLS.parent):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TOOLS.parent / relative, path)
        yield root, Path(temporary).resolve() / "prepared"


def _refuses(action: Callable[[], object], phrase: str) -> None:
    try:
        action()
    except (OSError, ValueError) as error:
        ensure(phrase in str(error), str(error))
    else:
        raise AssertionError(f"expected source-preparation refusal: {phrase}")


def _complete_recipe() -> None:
    with _fixture() as (root, output):
        report = package.prepare(root, output)
        ensure(report["native_output"] is None and report["production_admission"] is False,
               "preparation supplies no target or production verdict")
        unit = (output / "src/package_unit.c").read_text(encoding="utf-8")
        ensure('#define VOS_COPY_TARGET' in unit and '#include "copy_service.c"' in unit,
               "recipe compiles the actual target core")
        ensure('#include "target_layout.c"' in unit and "comparison" not in unit,
               "standalone unit has shared layout checks and no comparison wrapper")
        comparison = (TOOLS.parent / "copy-service/test/target_unit.c").read_text(encoding="utf-8")
        ensure('#include "../src/target_layout.c"' in comparison,
               "existing target comparison uses the same layout owner")
        for relative in package.C_FILES:
            ensure((output / relative).read_bytes() == (root / "copy-service" / relative).read_bytes(),
                   f"complete copied source: {relative}")
        for relative in package.ADAPTERS:
            raw = (root / "copy-service" / relative).read_text(encoding="utf-8")
            ensure((output / relative).read_text(encoding="utf-8").endswith(raw),
                   f"complete adapter retained: {relative}")
        config = copy_service.configuration(root)
        ensure((output / "include/copy_service_config.h").read_text(encoding="utf-8")
               == copy_service.configuration_header(config), "owning declaration generates header")
        before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
        ensure(package.check(root, output) == report, "source record replays")
        ensure(package.prepare(root, output) == report, "unchanged preparation has the same record")
        ensure(before == {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()},
               "unchanged preparation is byte identical")


def _source_and_include_refusals() -> None:
    for defect in ("include", "adapter", "helper"):
        with _fixture() as (root, output):
            package.prepare(root, output)
            prior = (output / package.RECORD).read_bytes()
            if defect == "include":
                path = root / "copy-service/src/package_unit.c"
                path.write_text(path.read_text(encoding="utf-8") + '#include "target_comparison.c"\n', encoding="utf-8")
                _refuses(lambda: package.prepare(root, output), "unbound local C include")
            elif defect == "adapter":
                (root / "copy-service/src/notification_target.s").unlink()
                _refuses(lambda: package.prepare(root, output), "regular file")
            else:
                path = root / "tools/vos/copy_target.py"
                path.write_text(path.read_text(encoding="utf-8") + "\n# changed helper\n", encoding="utf-8")
                _refuses(lambda: package.check(root, output), "record differs")
            ensure((output / package.RECORD).read_bytes() == prior, "refusal preserves useful prior record")


def _input_drift_before_publication() -> None:
    with _fixture() as (root, output):
        package.prepare(root, output)
        prior = (output / package.RECORD).read_bytes()
        original = copy_service.configuration
        def changed(staging: Path) -> copy_service.Config:
            path = root / "copy-service/src/copy_service.c"
            path.write_bytes(path.read_bytes() + b"\n/* concurrent edit */\n")
            return original(staging)
        with patch.object(copy_service, "configuration", changed):
            _refuses(lambda: package.prepare(root, output), "source changed")
        ensure((output / package.RECORD).read_bytes() == prior, "source drift preserves prior record")


def _hidden_include_refusals() -> None:
    spellings = (
        ('#inc\\\nlude "unbound.h"\n', "unbound local C include"),
        ('#\\\ninclude "unbound.h"\n', "unbound local C include"),
        ('#include_next "unbound.h"\n', "unsupported C directive"),
        ('#import "unbound.h"\n', "unsupported C directive"),
        ('int vos_copy_comment_probe; /* comment\n*/ #include "unbound.h"\n', "unbound local C include"),
        ("int vos_copy_char_probe = '/*';\n#include \"unbound.h\"\nint vos_copy_char_end = '*/';\n",
         "unbound local C include"),
        ('\ufeff#include "unbound.h"\n', "unbound local C include"),
        ('#inc\\\rlude "unbound.h"\r', "unbound local C include"),
        ('#inc\\\r\nlude "unbound.h"\r\n', "unbound local C include"),
        ('#inc\\ \nlude "unbound.h"\n', "escaped C newline"),
        ('#inc\\\t\nlude "unbound.h"\n', "escaped C newline"),
        ('#\0include "unbound.h"\n', "embedded NUL"),
        ('#include <stdint.h"\n', "unsupported C include"),
        ('??=include "unbound.h"\n', "preprocessing spelling"),
        ('??=inc??/\nlude "unbound.h"\n', "preprocessing spelling"),
        ('%:include "unbound.h"\n', "preprocessing spelling"),
        ('%\\\n:include "unbound.h"\n', "preprocessing spelling"),
    )
    with _fixture() as (root, output):
        package.prepare(root, output)
        prior = (output / package.RECORD).read_bytes()
        unit = root / "copy-service/src/package_unit.c"
        original = unit.read_bytes()
        for directive, phrase in spellings:
            encoded = directive.encode("utf-8")
            unit.write_bytes(encoded + original if directive.startswith("\ufeff") else original + encoded)
            _refuses(lambda: package.prepare(root, output), phrase)
            ensure((output / package.RECORD).read_bytes() == prior,
                   f"hidden include refusal preserves useful record: {directive!r}")


def _lexical_positive_controls() -> None:
    package._includes({"unit.c": b'\xef\xbb\xbf#include "header.h"\r\n', "include/header.h": b""})
    package._includes({"unit.c": b'/*\n#include "comment-only.h"\n*/\nint x;\n'})
    package._includes({"unit.c": b'const char *x = "/*"; int y = \'"\';\n'})


def _generation_uses_captured_declarations() -> None:
    with _fixture() as (root, output):
        expected = copy_service.configuration_header(copy_service.configuration(root))
        original = copy_service.configuration
        declaration = root / "interfaces/ring-reference.json"
        before = declaration.read_bytes()
        def transient(staging: Path) -> copy_service.Config:
            ensure(staging != root, "generation must not reread mutable live declarations")
            declaration.write_bytes(b'{"worlds":[]}')
            try:
                return original(staging)
            finally:
                declaration.write_bytes(before)
        with patch.object(copy_service, "configuration", transient):
            package.prepare(root, output)
        ensure((output / "include/copy_service_config.h").read_text(encoding="utf-8") == expected,
               "transient live declaration changes cannot select unbound constants")


def _output_refusals() -> None:
    for defect in ("changed", "missing", "added", "record"):
        with _fixture() as (root, output):
            package.prepare(root, output)
            target = output / "src/atomic_target.s"
            if defect == "changed":
                target.write_bytes(target.read_bytes() + b"\nret\n")
            elif defect == "missing":
                target.unlink()
            elif defect == "added":
                (output / "extra.s").write_bytes(b"ret\n")
            else:
                path = output / package.RECORD
                data = json.loads(path.read_bytes())
                data["production_admission"] = 0
                path.write_text(json.dumps(data), encoding="utf-8")
            _refuses(lambda: package.check(root, output), "unexpected" if defect == "added" else "differs")


def _aliases_preserve_inputs_and_record() -> None:
    for defect in ("input", "peer"):
        with _fixture() as (root, output):
            package.prepare(root, output)
            prior = (output / package.RECORD).read_bytes()
            target = output / "src/atomic_target.s"
            target.unlink()
            source = root / "copy-service/src/atomic_target.s" if defect == "input" else output / "src/copy_service.c"
            before = source.read_bytes()
            os.link(source, target)
            _refuses(lambda: package.prepare(root, output), "aliases")
            ensure(source.read_bytes() == before and (output / package.RECORD).read_bytes() == prior,
                   "alias refusal preserves consumed input and prior record")


def _public_command() -> None:
    with _fixture() as (root, output), patch.object(cli, "find_root", return_value=root), redirect_stdout(StringIO()):
        with patch.object(cli.env, "load", side_effect=AssertionError("host preparation must not enter WSL")):
            ensure(cli.main(["prepare-package", "--output", str(output)]) == 0, "public preparation succeeds")
            ensure(cli.main(["prepare-package", "--output", str(output), "--check"]) == 0,
                   "public read-only replay succeeds")
            (output / "src/atomic_target.s").unlink()
            ensure(cli.main(["prepare-package", "--output", str(output), "--check"]) == 1,
                   "public replay refuses a missing adapter")


def _native_syntax() -> None:
    compiler = copy_service.c_compiler()
    ensure(compiler is not None, "native C compiler missing")
    if compiler is None:
        return
    with _fixture() as (root, output):
        package.prepare(root, output)
        done = subprocess.run([compiler, *copy_service.CFLAGS, "-fsyntax-only", "-I", str(output / "include"),
                               str(output / "src/package_unit.c")], capture_output=True, text=True,
                              timeout=60, check=False, cwd=output)
        ensure(done.returncode == 0, done.stderr)


def cases() -> list[Case]:
    return [Case("complete comparison-free standalone source recipe", _complete_recipe),
            Case("source, include and required-adapter refusals", _source_and_include_refusals),
            Case("input drift prevents source-record publication", _input_drift_before_publication),
            Case("spliced, alternate and malformed include spellings refuse", _hidden_include_refusals),
            Case("BOM, CRLF, strings, character literals and comments preserve lexical meaning", _lexical_positive_controls),
            Case("generators consume captured declarations", _generation_uses_captured_declarations),
            Case("replay refuses changed, missing, added or substituted outputs", _output_refusals),
            Case("hardlink aliases preserve inputs and useful prior record", _aliases_preserve_inputs_and_record),
            Case("host public preparation and replay", _public_command),
            Case("strict native standalone C syntax", _native_syntax, lane="guest")]
