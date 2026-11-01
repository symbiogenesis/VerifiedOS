# SPDX-License-Identifier: Apache-2.0
"""Migration comparisons must expose differing acceptance, terms and locations."""

import hashlib
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import vela, vela_parser
from vos import vela_migration as migration
from vos.cli import vela_parser as cli


def _comparison() -> None:
    source = b"module M; public Nat F() { return 1; }"
    fixture = migration.Fixture("edited", source, "accepted")
    compiled = vela_parser.Build(TOOLS, TOOLS / "unused", {})
    translation = vela.translate(source)
    with patch.object(migration.vela_parser, "parse_source", return_value={}) as parse, \
            patch.object(migration.vela, "translate_ast", return_value=translation):
        agreed = migration.compare(compiled, (fixture,))
    ensure(agreed["status"] == "agreed" and agreed["differences"] == [], "equal output refused")
    parse.assert_called_once_with(compiled, source)
    ensure(agreed["checked_parser"] is False and agreed["python_retired"] is False,
           "development agreement promoted the parser")
    variants = (
        (vela.Translation("M", translation.gallina + "\n"), None, "accepted translations differ"),
        (None, vela.VelaError("limit", 1, 1, "bounded refusal"), "generated route differs"),
    )
    for result, error, reason in variants:
        with patch.object(migration.vela_parser, "parse_source", return_value={}), \
                patch.object(migration.vela, "translate_ast", return_value=result, side_effect=error):
            report = migration.compare(compiled, (fixture,))
        ensure(report["status"] == "differences" and report["differences"] == ["edited"],
               "different native behavior disappeared")
        ensure(reason in str(report["fixtures"]), "comparison lost its difference reason")


def _diagnostics() -> None:
    source = b"module M; public Nat F() { return missing; }"
    fixture = migration.Fixture("name-edit", source, "name")
    compiled = vela_parser.Build(TOOLS, TOOLS / "unused", {})
    for line, column, expected in ((1, 35, "agreed"), (2, 1, "differences")):
        with patch.object(migration.vela_parser, "parse_source", return_value={}), \
                patch.object(migration.vela, "translate_ast",
                             side_effect=vela.VelaError("name", line, column, "missing")):
            report = migration.compare(compiled, (fixture,))
        ensure(report["status"] == expected, "semantic diagnostic location was not compared")
    wrong_expectation = migration.Fixture("false-oracle", source, "type")
    with patch.object(migration.vela_parser, "parse_source", return_value={}), \
            patch.object(migration.vela, "translate_ast",
                         side_effect=vela.VelaError("name", 1, 35, "missing")):
        report = migration.compare(compiled, (wrong_expectation,))
    ensure(report["status"] == "differences" and "baseline differs" in str(report["fixtures"]),
           "agreement overrode an independent expected category")
    with patch.object(migration.vela_parser, "parse_source", side_effect=RuntimeError("broken protocol")), \
            patch.object(migration.vela, "translate_ast") as consume:
        try:
            migration.compare(compiled, (fixture,))
        except RuntimeError as error:
            ensure(str(error) == "broken protocol", "native failure cause lost")
        else:
            raise AssertionError("protocol failure counted as a source refusal")
        consume.assert_not_called()


def _fixture_baseline() -> None:
    example = (TOOLS / "vela/examples/pure.vela").read_bytes()
    cases = migration.fixtures(example)
    ensure(len({case.name for case in cases}) == len(cases), "duplicate migration identity")
    ensure(any(case.name == "group-boundary" for case in cases), "known limit difference omitted")
    for case in cases:
        outcome = migration._observe(lambda source=case.source: vela.translate(source))
        ensure(outcome["category"] == case.expected,
               f"migration oracle {case.name}: expected {case.expected}, got {outcome}")


def _freshness() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-migration-") as temporary:
        root = Path(temporary)
        directory = root / "build"
        directory.mkdir()
        inputs, toolchain = {"consumer": "original"}, {"compiler": "original"}
        for mode in ("inputs", "toolchain", "output", "crash", "none"):
            for name in (*vela_parser.GENERATED, "vela-parser"):
                (directory / name).write_bytes(b"original")
            outputs = {name: hashlib.sha256(b"original").hexdigest()
                       for name in (*vela_parser.GENERATED, "vela-parser")}
            receipt = {"directory": str(directory), "toolchain": toolchain,
                       "generated_sha256": outputs}
            latest = root / "migration.json"
            latest.write_text('{"status":"agreed","stale":true}', encoding="utf-8")

            def compare(_compiled: vela_parser.Build, _cases: tuple[migration.Fixture, ...],
                        change: str = mode) -> dict[str, object]:
                if change == "output":
                    (directory / "parser.ml").write_bytes(b"changed")
                if change == "crash":
                    raise RuntimeError("native comparison failed")
                return {"status": "agreed"}

            with patch.object(migration.vela_parser, "_work_root", return_value=root), \
                    patch.object(migration.vela_parser, "qualify", return_value={"build": receipt}), \
                    patch.object(migration.vela_parser, "read_source", return_value=b"example"), \
                    patch.object(migration, "fixtures", return_value=()), \
                    patch.object(migration, "compare", side_effect=compare), \
                    patch.object(migration, "_inputs", side_effect=[inputs, {"consumer": "changed"}]
                                 if mode == "inputs" else [inputs, inputs]), \
                    patch.object(migration.vela_parser, "_toolchain", return_value={"compiler": "changed"}
                                 if mode == "toolchain" else toolchain):
                try:
                    report = migration.qualify(root)
                except (RuntimeError, ValueError):
                    ensure(mode != "none" and not latest.exists(), "stale migration agreement survived failure")
                else:
                    ensure(mode == "none", f"changed {mode} acquired agreement")
                    ensure(json.loads(latest.read_text(encoding="utf-8")) == report,
                           "returned and retained migration evidence differ")


def _cli_verdict() -> None:
    for status, expected in (("agreed", 0), ("differences", 1)):
        with redirect_stdout(out := StringIO()), redirect_stderr(err := StringIO()), \
                patch.object(cli.vela_migration, "qualify", return_value={"status": status}):
            code = cli.main(["migration"])
        ensure(code == expected and json.loads(out.getvalue())["status"] == status and not err.getvalue(),
               "migration differences lost their nonzero verdict or report")


def cases() -> list[Case]:
    return [Case("agreement-and-difference-accounting", _comparison),
            Case("diagnostic-and-protocol-differences", _diagnostics),
            Case("independent-migration-categories", _fixture_baseline),
            Case("changed-comparison-inputs-refuse", _freshness),
            Case("cli-difference-verdict", _cli_verdict)]
