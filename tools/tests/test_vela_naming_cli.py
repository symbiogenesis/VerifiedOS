# SPDX-License-Identifier: Apache-2.0
"""Independent naming-warning, strict-check and publication controls for Vela."""

import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.cli import vela_parser as cli
from vos.vela import VelaError
from vos.vela_authoring import Finding
from vos.vela_mathematical import Compilation

SOURCE = b"module Named;\npublic definition element Identity<element>(element value) => value;\n"
GALLINA = "(* unchanged unqualified translation *)\nDefinition identity := fun value => value.\n"
MESSAGE = "generic type parameter 'element' should use PascalCase"
FINDING = Finding("VELA105", MESSAGE, 2, 36)
TREE: dict[str, object] = {"schema": 2, "source-bound-test-tree": True}


def _invoke(arguments: list[str]) -> tuple[int, str, str]:
    with redirect_stdout(out := StringIO()), redirect_stderr(err := StringIO()):
        try:
            result = cli.main(arguments)
        except SystemExit as error:
            if not isinstance(error.code, int):
                raise
            result = error.code
    return result, out.getvalue(), err.getvalue()


def _warnings_and_allow() -> None:
    with tempfile.TemporaryDirectory(prefix="vela-naming-cli-") as temporary:
        source = Path(temporary) / "input.vela"
        source.write_bytes(SOURCE)
        compilation = Compilation("Named", GALLINA, (FINDING,))
        with (patch.object(cli.vela_parser, "build", return_value=object()) as build,
              patch.object(cli.vela_parser, "parse_source", return_value=TREE) as parse,
              patch.object(cli.vela_mathematical, "inspect_source", return_value=compilation) as inspect):
            code, out, err = _invoke(["elaborate", str(source)])
            ensure(code == 0 and out == GALLINA, "advisory naming changed successful stdout")
            ensure(err == f"{source}:2:36: warning VELA105: {MESSAGE}\n",
                   "default warning lost its stable identity or original identifier position")
            ensure(build.call_count == 1 and parse.call_count == 1 and inspect.call_count == 1,
                   "naming inspection rebuilt or reparsed the module")
            ensure(parse.call_args.args[1] == SOURCE and parse.call_args.kwargs == {"surface": True}
                   and inspect.call_args.args == (SOURCE, TREE), "naming inspection lost exact source/tree identity")
            code, out, err = _invoke(["elaborate", str(source), "--allow", "VELA105", "--allow", "VELA105"])
            ensure(code == 0 and out == GALLINA and not err, "explicit allow failed to suppress advisory naming")
        ensure(source.read_bytes() == SOURCE, "naming warning or allow rewrote authored source")


def _strict_publication() -> None:
    with tempfile.TemporaryDirectory(prefix="vela-naming-deny-") as temporary:
        root = Path(temporary)
        source, output = root / "input.vela", root / "existing.v"
        source.write_bytes(SOURCE)
        output.write_bytes(b"retain existing artifact\n")
        compilation = Compilation("Named", GALLINA, (FINDING,))
        with (patch.object(cli.vela_parser, "build", return_value=object()),
              patch.object(cli.vela_parser, "parse_source", return_value=TREE),
              patch.object(cli.vela_mathematical, "inspect_source", return_value=compilation),
              patch.object(cli, "_publish") as publish):
            for arguments in (["--deny", "VELA105"],
                              ["--deny", "VELA105", "--deny", "VELA105", "--output", str(output)]):
                code, out, err = _invoke(["elaborate", str(source), *arguments])
                ensure(code == 1 and not out and err == f"{source}:2:36: error VELA105: {MESSAGE}\n",
                       "denied naming emitted terms or lost its explicit lint error")
                ensure(not publish.called and output.read_bytes() == b"retain existing artifact\n",
                       "denied naming reached output publication")
        ensure(source.read_bytes() == SOURCE and not list(root.glob(".existing.v.*.tmp")),
               "denied naming changed source or left a publication temporary")


def _options_before_compilation() -> None:
    with (patch.object(cli.vela_parser, "read_source") as read,
          patch.object(cli.vela_parser, "build") as build,
          patch.object(cli.vela_mathematical, "inspect_source") as inspect):
        for options in (["--allow", "VELA105", "--deny", "VELA105"],
                        ["--deny", "VELA105", "--allow", "VELA105"]):
            code, out, err = _invoke(["elaborate", "missing.vela", *options])
            ensure(code == 2 and not out and "both allowed and denied" in err,
                   "conflicting naming policy did not fail before compilation")
        for arguments in (["elaborate", "missing.vela", "--deny", "VELA101"],
                          ["parse", "missing.vela", "--allow", "VELA105"],
                          ["elaborate-qualify", "--deny", "VELA105"]):
            code, out, err = _invoke(arguments)
            ensure(code == 2 and not out and bool(err), "unsupported command or lint acquired naming options")
        ensure(not read.called and not build.called and not inspect.called,
               "refused naming options consumed source or ran the native compiler")
    code, out, err = _invoke(["elaborate", "--help"])
    ensure(code == 0 and not err and "--allow" in out and "--deny" in out and "VELA105" in out,
           "mathematical elaboration help omits explicit naming enforcement")


def _semantic_failure_and_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="vela-naming-invalid-") as temporary:
        root = Path(temporary)
        source, output = root / "input.vela", root / "output.v"
        source.write_bytes(SOURCE)
        output.write_bytes(b"original artifact\n")
        with (patch.object(cli.vela_parser, "build", return_value=object()),
              patch.object(cli.vela_parser, "parse_source", return_value=TREE),
              patch.object(cli.vela_mathematical, "inspect_source",
                           side_effect=VelaError("type", 3, 9, "invalid equality proof"))):
            code, out, err = _invoke(["elaborate", str(source), "--output", str(output), "--deny", "VELA105"])
            ensure(code == 1 and not out and ":3:9: type: invalid equality proof" in err and "VELA105" not in err,
                   "invalid source produced style findings or obscured its semantic error")
        ensure(output.read_bytes() == b"original artifact\n", "semantic failure changed existing output")
        accepted = Compilation("Named", GALLINA, ())
        with (patch.object(cli.vela_parser, "build", return_value=object()),
              patch.object(cli.vela_parser, "parse_source", return_value=TREE),
              patch.object(cli.vela_mathematical, "inspect_source", return_value=accepted)):
            code, out, err = _invoke(["elaborate", str(source), "--output", str(output), "--deny", "VELA105"])
        ensure(code == 0 and not out and not err and output.read_bytes() == GALLINA.encode(),
               "clean strict naming did not recover after an invalid module")


def _warning_file_output() -> None:
    with tempfile.TemporaryDirectory(prefix="vela-naming-output-") as temporary:
        root = Path(temporary)
        source, output = root / "input.vela", root / "output.v"
        source.write_bytes(SOURCE)
        result = Compilation("Named", GALLINA, (FINDING,))
        with (patch.object(cli.vela_parser, "build", return_value=object()),
              patch.object(cli.vela_parser, "parse_source", return_value=TREE),
              patch.object(cli.vela_mathematical, "inspect_source", return_value=result)):
            code, out, err = _invoke(["elaborate", str(source), "--output", str(output)])
        ensure(code == 0 and not out and "warning VELA105" in err and output.read_bytes() == GALLINA.encode(),
               "advisory naming prevented atomic file emission or changed its bytes")
        ensure(source.read_bytes() == SOURCE, "naming inspection modified the source file")


def cases() -> list[Case]:
    return [Case("mathematical naming warnings and repeated explicit allow", _warnings_and_allow),
            Case("strict naming prevents stdout and destination publication", _strict_publication),
            Case("conflicting unsupported and scoped naming options", _options_before_compilation),
            Case("semantic failure preserves diagnostics output and strict recovery", _semantic_failure_and_recovery),
            Case("advisory naming preserves atomic file emission", _warning_file_output)]
