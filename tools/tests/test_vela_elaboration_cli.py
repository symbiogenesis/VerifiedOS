# SPDX-License-Identifier: Apache-2.0
"""Publication and dispatch controls for native mathematical elaboration."""

import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.cli import vela_parser as cli
from vos.vela import VelaError
from vos.vela_mathematical import Compilation

SOURCE = b"module Demo; definition Nat Value() => 3;"
GALLINA = "(* unqualified test term *)\nDefinition value : nat := 3.\n"


def _invoke(arguments: list[str]) -> tuple[int, str, str]:
    with redirect_stdout(out := StringIO()), redirect_stderr(err := StringIO()):
        result = cli.main(arguments)
    return result, out.getvalue(), err.getvalue()


def _publication() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-elaboration-cli-") as temporary:
        root = Path(temporary)
        source, output = root / "input.vela", root / "output.v"
        source.write_bytes(SOURCE)
        tree: dict[str, object] = {"schema": 2}
        with (patch.object(cli.vela_parser, "build", return_value=object()) as build,
              patch.object(cli.vela_parser, "parse_source", return_value=tree) as parse,
              patch.object(cli.vela_mathematical, "inspect_source",
                           return_value=Compilation("Demo", GALLINA, ())) as elaborate):
            code, out, err = _invoke(["elaborate", str(source)])
            ensure(code == 0 and out == GALLINA and not err, "stdout differs from elaborated bytes")
            ensure(parse.call_args.args[1] == SOURCE and parse.call_args.kwargs == {"surface": True},
                   "elaboration did not consume the complete native surface")
            ensure(elaborate.call_args.args == (SOURCE, tree), "elaborator lost its source/tree binding")
            ensure(build.call_args.args[0] == Path(cli.__file__).resolve().parents[3],
                   "native build targeted a different checkout")
            code, out, err = _invoke(["elaborate", str(source), "--output", str(output)])
            ensure(code == 0 and not out and not err and output.read_bytes() == GALLINA.encode(),
                   "atomic file emission differs from stdout")
            original = output.read_bytes()
            with patch.object(cli.vela_mathematical, "inspect_source", side_effect=VelaError("type", 2, 4, "false proof")):
                code, out, err = _invoke(["elaborate", str(source), "--output", str(output)])
            ensure(code == 1 and not out and ":2:4: type: false proof" in err,
                   "failed elaboration lost its located diagnostic")
            ensure(output.read_bytes() == original, "failed elaboration overwrote existing output")
            with patch.object(cli.vela_parser, "parse_source", side_effect=VelaError("syntax", 1, 8, "invalid")):
                code, out, err = _invoke(["elaborate", str(source), "--output", str(output)])
            ensure(code == 1 and not out and ": syntax:" in err and output.read_bytes() == original,
                   "native parser failure published a term")
            for destination in (source, root / "alias.vela"):
                if destination != source:
                    destination.hardlink_to(source)
                code, out, err = _invoke(["elaborate", str(source), "--output", str(destination)])
                ensure(code == 1 and not out and "aliases" in err and source.read_bytes() == SOURCE,
                       "input alias was replaced")
            code, out, err = _invoke(["elaborate", str(source), "--output", str(root / "missing/out.v")])
            ensure(code == 1 and not out and bool(err) and not (root / "missing").exists(),
                   "publication created an undeclared directory")
            with patch.object(Path, "replace", side_effect=OSError("publication refused")):
                code, out, err = _invoke(["elaborate", str(source), "--output", str(output)])
            ensure(code == 1 and not out and "publication refused" in err and output.read_bytes() == original,
                   "failed replacement damaged the existing output")
            ensure(not list(root.glob(".output.v.*.tmp")), "atomic failure leaked a temporary output")


def _qualification() -> None:
    receipt = {"scope": "mathematical-terms", "status": "passed", "source_correspondence": False}
    with patch.object(cli.vela_elaboration_check, "qualify", return_value=receipt):
        code, out, err = _invoke(["elaborate-qualify"])
    ensure(code == 0 and not err and json.loads(out) == receipt, "native qualification receipt changed")
    with patch.object(cli.vela_elaboration_check, "qualify", side_effect=RuntimeError("kernel refused")):
        code, out, err = _invoke(["elaborate-qualify"])
    ensure(code == 1 and not out and "kernel refused" in err, "failed replay reported acceptance")


def cases() -> list[Case]:
    return [Case("complete native elaboration and atomic publication", _publication),
            Case("kernel qualification dispatch and failure", _qualification)]
