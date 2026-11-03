# SPDX-License-Identifier: Apache-2.0
"""The wider parser entry cannot bypass schema or qualification boundaries."""

import hashlib
import json
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela_parser as parser
from vos import vela_surface as surface
from vos.cli import vela_parser as cli


def _build(directory: Path) -> parser.Build:
    executable = directory / "vela-parser"
    executable.write_bytes(b"fixture executable")
    return parser.Build(directory, executable, {
        "generated_sha256": {"vela-parser": hashlib.sha256(executable.read_bytes()).hexdigest()},
    })


def _entry_protocol() -> None:
    source = b"module M;"
    tree: dict[str, parser.Json] = {"kind": "surface_file", "span": [0, 9],
                                   "name": {"text": "M", "span": [7, 8]}, "declarations": []}
    with tempfile.TemporaryDirectory(prefix="vos-vela-surface-") as temporary:
        compiled = _build(Path(temporary))
        response = subprocess.CompletedProcess([], 0, json.dumps({"schema": 2, "ast": tree}).encode(), b"")
        with patch.object(parser.subprocess, "run", return_value=response) as run:
            result = parser.parse_source(compiled, source, surface=True)
        ensure(run.call_args.args[0] == [str(compiled.executable), "--surface"],
               "surface request used the pure native entry")
        ensure(result == {"schema": 2, "source_sha256": hashlib.sha256(source).hexdigest(), "ast": tree},
               "surface source binding or syntax changed")
        for surface, schema, kind in ((False, 2, "surface_file"), (True, 1, "file"),
                                      (True, True, "surface_file"), (True, 2, "file")):
            payload = {"schema": schema, "ast": {**tree, "kind": kind}}
            response = subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b"")
            with patch.object(parser.subprocess, "run", return_value=response):
                try:
                    parser.parse_source(compiled, source, surface=surface)
                except ValueError as error:
                    ensure("schema" in str(error), "entry mismatch has no schema refusal")
                else:
                    raise AssertionError("cross-entry or boolean schema accepted")


def _entry_cli() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-surface-") as temporary:
        directory = Path(temporary)
        source = directory / "surface.vela"
        source.write_bytes(b"module M;")
        compiled = _build(directory)
        with redirect_stdout(output := StringIO()), redirect_stderr(errors := StringIO()), \
                patch.object(cli.vela_parser, "build", return_value=compiled), \
                patch.object(cli.vela_parser, "parse_source", return_value={"schema": 2}) as parse:
            code = cli.main(["parse", "--surface", str(source)])
        ensure(code == 0 and json.loads(output.getvalue()) == {"schema": 2} and not errors.getvalue(),
               "surface CLI failed or mixed diagnostics with syntax")
        parse.assert_called_once_with(compiled, source.read_bytes(), surface=True)
        with redirect_stdout(output := StringIO()), redirect_stderr(errors := StringIO()), \
                patch.object(cli.vela_parser, "build", return_value=compiled), \
                patch.object(cli.vela_parser, "parse_source", side_effect=ValueError("invalid surface schema")) as parse:
            code = cli.main(["parse", "--surface", str(source)])
        ensure(code == 1 and not output.getvalue() and "invalid surface schema" in errors.getvalue(),
               "failed surface request emitted output or hid refusal")
        ensure(parse.call_count == 1, "surface failure retried through a fallback parser")


def _qualification_input_binding() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-surface-") as temporary:
        root = Path(temporary)
        files = [*(f"tools/vela/parser/{name}" for name in parser.SOURCES),
                 "tools/opam/sail.lock", "tools/vos/vela_parser.py", "tools/vos/vela_surface.py",
                 "tools/vela/examples/pure.vela", "tools/vela/examples/surface.vela"]
        for name in files:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
        initial = parser._inputs(root)
        for name in ("tools/vos/vela_surface.py", "tools/vela/examples/surface.vela"):
            path = root / name
            original = path.read_bytes()
            path.write_bytes(original + b" changed")
            changed = parser._inputs(root)
            ensure(changed[name] != initial[name], f"qualification omitted changed {name}")
            path.write_bytes(original)


def _failed_surface_qualification() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-surface-") as temporary:
        root = Path(temporary)
        hashes = dict.fromkeys(parser.GENERATED, "same")
        compiled = parser.Build(root, root / "unused", {
            "inputs": {}, "toolchain": {}, "generated_sha256": hashes,
        })
        latest = root / "qualification.json"
        latest.write_text('{"status":"passed"}', encoding="utf-8")
        with patch.object(parser, "_work_root", return_value=root), \
                patch.object(parser, "build", return_value=compiled), \
                patch.object(parser, "_fixtures", return_value=["pure-passed"]), \
                patch.object(parser.vela_surface, "qualify", side_effect=ValueError("surface oracle differs")):
            try:
                parser.qualify(root)
            except ValueError as error:
                ensure(str(error) == "surface oracle differs", "surface qualification failure was replaced")
            else:
                raise AssertionError("failed surface oracle produced passing qualification")
        ensure(not latest.exists(), "failed surface oracle preserved stale passing evidence")


def _shared_primitive_oracle_required() -> None:
    fixture = next(value for value in surface.POSITIVE if value.name == "shared-syntax-primitives")
    result: dict[str, parser.Json] = {
        "ast": [{"kind": kind} for kind in fixture.kinds],
    }
    with patch.object(surface, "POSITIVE", (fixture,)), \
            patch.object(surface, "_precedence_and_spans"), \
            patch.object(surface, "_literal_and_comment_boundaries"), \
            patch.object(surface, "_argument_roles"), \
            patch.object(surface, "_shared_primitive_roles", side_effect=ValueError("primitive role changed")) as oracle:
        try:
            surface.qualify(lambda source: result)
        except ValueError as error:
            ensure(str(error) == "primitive role changed", "shared primitive oracle failure was replaced")
        else:
            raise AssertionError("shared primitive oracle was bypassed during qualification")
    oracle.assert_called_once_with(fixture.source.encode("utf-8"), result)


def _expression_binding_oracle_required() -> None:
    fixture = next(value for value in surface.POSITIVE if value.name == "expression-local-bindings")
    result: dict[str, parser.Json] = {"ast": [{"kind": kind} for kind in fixture.kinds]}
    with patch.object(surface, "POSITIVE", (fixture,)), \
            patch.object(surface, "_precedence_and_spans"), \
            patch.object(surface, "_literal_and_comment_boundaries"), \
            patch.object(surface, "_argument_roles"), \
            patch.object(surface, "_expression_binding_roles", side_effect=ValueError("binding scope changed")) as oracle:
        try:
            surface.qualify(lambda source: result)
        except ValueError as error:
            ensure(str(error) == "binding scope changed", "binding oracle failure was replaced")
        else:
            raise AssertionError("expression-binding oracle was bypassed during qualification")
    oracle.assert_called_once_with(fixture.source.encode("utf-8"), result)


def _binder_initializer_oracles_required() -> None:
    for name, oracle_name in (("generic-binders-and-typed-initializers", "_binder_initializer_roles"),
                              ("binder-initializer-errors-remain-syntax", "_binder_initializer_error_roles")):
        fixture = next(value for value in surface.POSITIVE if value.name == name)
        result: dict[str, parser.Json] = {"ast": [{"kind": kind} for kind in fixture.kinds]}
        with patch.object(surface, "POSITIVE", (fixture,)), \
                patch.object(surface, "_precedence_and_spans"), \
                patch.object(surface, "_literal_and_comment_boundaries"), \
            patch.object(surface, "_argument_roles"), \
                patch.object(surface, oracle_name, side_effect=ValueError("binder/initializer role changed")) as oracle:
            try:
                surface.qualify(lambda source, result=result: result)
            except ValueError as error:
                ensure(str(error) == "binder/initializer role changed", "binder/initializer oracle failure was replaced")
            else:
                raise AssertionError("binder/initializer oracle was bypassed during qualification")
        if name == "generic-binders-and-typed-initializers":
            oracle.assert_called_once_with(fixture.source.encode("utf-8"), result)
        else:
            oracle.assert_called_once_with(result)


def _explicit_value_oracles_required() -> None:
    for name, oracle_name in (("explicit-values-loans-and-options", "_explicit_value_roles"),
                              ("explicit-pointer-operators", "_pointer_roles"),
                              ("explicit-values-errors-remain-syntax", "_explicit_error_roles"),
                              ("expressions-and-closures", "_propagation_member_role")):
        fixture = next(value for value in surface.POSITIVE if value.name == name)
        result: dict[str, parser.Json] = {"ast": [{"kind": kind} for kind in fixture.kinds]}
        with patch.object(surface, "POSITIVE", (fixture,)), \
                patch.object(surface, "_precedence_and_spans"), \
                patch.object(surface, "_literal_and_comment_boundaries"), \
            patch.object(surface, "_argument_roles"), \
                patch.object(surface, oracle_name, side_effect=ValueError("explicit role changed")) as oracle:
            try:
                surface.qualify(lambda source, result=result: result)
            except ValueError as error:
                ensure(str(error) == "explicit role changed", "explicit-value oracle failure was replaced")
            else:
                raise AssertionError("explicit-value oracle was bypassed during qualification")
        if name in {"explicit-values-errors-remain-syntax", "expressions-and-closures"}:
            oracle.assert_called_once_with(result)
        else:
            oracle.assert_called_once_with(fixture.source.encode("utf-8"), result)


def _concise_authoring_oracle_required() -> None:
    fixture = next(value for value in surface.POSITIVE if value.name == "concise-authoring-syntax")
    result: dict[str, parser.Json] = {"ast": [{"kind": kind} for kind in fixture.kinds]}
    with patch.object(surface, "POSITIVE", (fixture,)), \
            patch.object(surface, "_precedence_and_spans"), \
            patch.object(surface, "_literal_and_comment_boundaries"), \
            patch.object(surface, "_argument_roles"), \
            patch.object(surface, "_concise_authoring_roles", side_effect=ValueError("concise role changed")) as oracle:
        try:
            surface.qualify(lambda source: result)
        except ValueError as error:
            ensure(str(error) == "concise role changed", "concise oracle failure was replaced")
        else:
            raise AssertionError("concise authoring oracle was bypassed during qualification")
    oracle.assert_called_once_with(fixture.source.encode("utf-8"), result)


def _constant_oracle_required() -> None:
    fixture = next(value for value in surface.POSITIVE if value.name == "required-static-constants")
    result: dict[str, parser.Json] = {"ast": [{"kind": kind} for kind in fixture.kinds]}
    with patch.object(surface, "POSITIVE", (fixture,)), \
            patch.object(surface, "_precedence_and_spans"), \
            patch.object(surface, "_literal_and_comment_boundaries"), \
            patch.object(surface, "_argument_roles"), \
            patch.object(surface, "_required_static_roles", side_effect=ValueError("constant role changed")) as oracle:
        try:
            surface.qualify(lambda source: result)
        except ValueError as error:
            ensure(str(error) == "constant role changed", "constant role oracle failure was replaced")
        else:
            raise AssertionError("required-static syntax oracle was bypassed")
    oracle.assert_called_once_with(fixture.source.encode("utf-8"), result)


def cases() -> list[Case]:
    return [Case("concise-authoring-oracle-is-required", _concise_authoring_oracle_required),
            Case("constant-declaration-order-and-span-oracle-is-required", _constant_oracle_required),
            Case("surface-entry-schema-and-source-binding", _entry_protocol),
            Case("surface-cli-and-no-fallback", _entry_cli),
            Case("surface-fixture-input-identities", _qualification_input_binding),
            Case("surface-oracle-failure-without-receipt", _failed_surface_qualification),
            Case("shared-primitive-oracle-is-required", _shared_primitive_oracle_required),
            Case("expression-binding-oracle-is-required", _expression_binding_oracle_required),
            Case("binder-initializer-oracles-are-required", _binder_initializer_oracles_required),
            Case("explicit-value-oracles-are-required", _explicit_value_oracles_required)]
