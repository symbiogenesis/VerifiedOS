# SPDX-License-Identifier: Apache-2.0
"""Native parser protocol, bounded execution and exact toolchain controls."""

import hashlib
import json
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import vela_parser as parser
from vos.cli import vela_parser as cli
from vos.vela import MAX_SOURCE_BYTES, VelaError


def _build(directory: Path) -> parser.Build:
    executable = directory / "vela-parser"
    executable.write_bytes(b"test executable identity")
    return parser.Build(directory, executable,
                        {"generated_sha256": {"vela-parser": hashlib.sha256(executable.read_bytes()).hexdigest()}})


def _response(value: object, code: int = 0, stderr: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(["vela-parser"], code, json.dumps(value).encode(), stderr)


def _expect_failure(compiled: parser.Build, response: subprocess.CompletedProcess[bytes],
                    message: str) -> None:
    with patch.object(parser.subprocess, "run", return_value=response):
        try:
            parser.parse_source(compiled, b"module M;")
        except (TypeError, ValueError, RuntimeError) as error:
            ensure(message in str(error), f"missing refusal detail: {error}")
        else:
            raise AssertionError("invalid native response accepted")


def _protocol() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-parser-") as temporary:
        compiled = _build(Path(temporary))
        ast = {"kind": "file", "span": [0, 9], "name": {"text": "M", "span": [7, 8]}, "declarations": []}
        source = b"module M;\r\n// exact bytes"
        with patch.object(parser.subprocess, "run", return_value=_response({"schema": 1, "ast": ast})) as process:
            result = parser.parse_source(compiled, source)
        ensure(result["ast"] == ast, "native syntax tree changed in orchestration")
        ensure(result["source_sha256"] == hashlib.sha256(source).hexdigest(), "source digest normalized bytes")
        ensure(process.call_args.kwargs["input"] == source, "parser received changed source")
        ensure(process.call_args.kwargs["timeout"] == parser.PARSE_TIMEOUT, "parser has no duration bound")
        for value, message in (
                ({"schema": True, "ast": ast}, "schema"),
                ({"schema": 2, "ast": ast}, "schema"),
                ({"schema": 1, "ast": {"kind": "file", "span": [0, 100]}}, "outside"),
                ({"schema": 1, "ast": {"kind": "file", "span": [False, 9]}}, "span"),
                ({"schema": 1, "ast": None}, "tree")):
            _expect_failure(compiled, _response(value), message)
        _expect_failure(compiled, _response({"schema": 1, "ast": ast}, stderr=b"warning"), "standard error")
        _expect_failure(compiled, _response({}, 7), "exited 7")
        _expect_failure(compiled, subprocess.CompletedProcess([], 0, b"{invalid", b""), "malformed JSON")
        refusal = {"kind": "syntax", "line": 3, "column": 10, "message": "expected expression"}
        with patch.object(parser.subprocess, "run", return_value=_response(refusal, 1)):
            try:
                parser.parse_source(compiled, source)
            except VelaError as error:
                ensure((error.kind, error.line, error.column) == ("syntax", 3, 10), "native diagnostic lost")
            else:
                raise AssertionError("native refusal accepted")
        _expect_failure(compiled, _response({**refusal, "line": True}, 1), "invalid refusal")
        compiled.executable.write_bytes(b"changed")
        with patch.object(parser.subprocess, "run") as process:
            try:
                parser.parse_source(compiled, source)
            except ValueError as error:
                ensure("changed after" in str(error), "stale executable refusal missing")
            else:
                raise AssertionError("changed executable consumed")
            process.assert_not_called()


def _bounds() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-parser-") as temporary:
        directory = Path(temporary)
        compiled = _build(directory)
        source = directory / "source.vela"
        source.write_bytes(b" " * (MAX_SOURCE_BYTES + 1))
        for operation in (lambda: parser.read_source(source),
                          lambda: parser.parse_source(compiled, source.read_bytes())):
            with patch.object(parser.subprocess, "run") as process:
                try:
                    operation()
                except VelaError as error:
                    ensure(error.kind == "limit", "oversized source has wrong diagnostic")
                else:
                    raise AssertionError("oversized source accepted")
                process.assert_not_called()
        with patch.object(parser.subprocess, "run", side_effect=subprocess.TimeoutExpired("parser", 15)):
            try:
                parser.parse_source(compiled, b"module M;")
            except VelaError as error:
                ensure(error.kind == "limit", "timeout has wrong diagnostic")
            else:
                raise AssertionError("timed-out parse accepted")
        with patch.object(parser.subprocess, "run", side_effect=subprocess.TimeoutExpired("tool", 120)):
            try:
                parser._run(["tool"], directory)
            except RuntimeError as error:
                ensure("exceeded" in str(error), "build timeout has no useful refusal")
            else:
                raise AssertionError("timed-out build accepted")


def _versions() -> None:
    root = TOOLS.parent
    locked = parser._locked_versions(root)
    expected = [f"menhir, version {locked['menhir']}", locked["ocaml-base-compiler"],
                f"The OCaml lexer generator, version {locked['ocaml-base-compiler']}", str(root)]
    with patch.object(parser, "_run", side_effect=expected), patch.object(parser, "_digest", return_value="a" * 64):
        result = parser._toolchain(root)
    ensure(result["ocamlc"] == locked["ocaml-base-compiler"], "accepted compiler differs from lock")
    for index in range(3):
        changed = [*expected]
        changed[index] = "different version"
        with patch.object(parser, "_run", side_effect=changed):
            try:
                parser._toolchain(root)
            except ValueError as error:
                ensure("identity differs" in str(error), "version refusal missing")
            else:
                raise AssertionError("different parser toolchain accepted")


def _failed_build() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-parser-") as temporary:
        root = Path(temporary)
        sources = root / "tools/vela/parser"
        sources.mkdir(parents=True)
        for name in parser.SOURCES:
            (sources / name).write_text("authored input\n", encoding="utf-8")
        (root / "tools/opam").mkdir()
        (root / "tools/opam/sail.lock").write_text("snapshot\n", encoding="utf-8")
        (root / "tools/vos").mkdir()
        (root / "tools/vos/vela_parser.py").write_text("driver\n", encoding="utf-8")
        (root / "tools/vos/vela_surface.py").write_text("fixtures\n", encoding="utf-8")
        (root / "tools/vela/examples").mkdir()
        for name in ("pure.vela", "surface.vela"):
            (root / "tools/vela/examples" / name).write_text("example\n", encoding="utf-8")
        output = root / "native-build"
        output.mkdir()
        with patch.object(parser, "_run", side_effect=RuntimeError("generator refused grammar")):
            try:
                parser._compile(root, output, {})
            except RuntimeError as error:
                ensure("refused grammar" in str(error), "generator failure hidden")
            else:
                raise AssertionError("failed generator acquired a build")
        ensure(not (output / "receipt.json").exists(), "failed build left a passing receipt")


def _cli() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-parser-") as temporary:
        source = Path(temporary) / "source.vela"
        source.write_bytes(b"module M;")
        with redirect_stdout(out := StringIO()), redirect_stderr(err := StringIO()), \
                patch.object(cli.vela_parser, "build", side_effect=RuntimeError("no locked toolchain")):
            code = cli.main(["parse", str(source)])
        ensure(code == 1 and not out.getvalue() and "no locked toolchain" in err.getvalue(),
               "failed build emitted an AST or lost its cause")


def _qualification_freshness() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-vela-parser-") as temporary:
        root = Path(temporary)
        output = root / "build"
        output.mkdir()
        example = root / "tools/vela/examples/pure.vela"
        example.parent.mkdir(parents=True)
        source = b"module M; public Nat F() { return 1; }\r\n"
        inputs, toolchain = {"source": "original"}, {"compiler": "original"}
        surface_example = example.with_name("surface.vela")
        for change in ("source", "toolchain", "generated", "executable", "example", "surface", "none"):
            example.write_bytes(source)
            surface_example.write_bytes(source)
            for name in (*parser.GENERATED, "vela-parser"):
                (output / name).write_bytes(b"original")
            hashes = {name: hashlib.sha256(b"original").hexdigest()
                      for name in (*parser.GENERATED, "vela-parser")}
            compiled = parser.Build(output, output / "vela-parser",
                                    {"inputs": inputs, "toolchain": toolchain,
                                     "generated_sha256": hashes})
            latest = root / "qualification.json"
            latest.write_text('{"status":"passed","old":true}', encoding="utf-8")

            def parse_example(_compiled: parser.Build, _source: bytes, *, surface: bool = False,
                              mode: str = change) -> dict[str, parser.Json]:
                if mode in {"generated", "executable"}:
                    (output / ("parser.ml" if mode == "generated" else "vela-parser")).write_bytes(b"changed")
                elif mode == "example":
                    example.write_bytes(source + b"// changed")
                elif mode == "surface" and surface:
                    surface_example.write_bytes(source + b"// changed")
                return {"schema": 1}

            with patch.object(parser, "_work_root", return_value=root), \
                    patch.object(parser, "build", return_value=compiled), \
                    patch.object(parser, "_fixtures", return_value=["independent"]), \
                    patch.object(parser.vela_surface, "qualify", return_value=["surface-independent"]), \
                    patch.object(parser, "parse_source", side_effect=parse_example), \
                    patch.object(parser, "_inputs", return_value={"source": "changed"} if change == "source" else inputs), \
                    patch.object(parser, "_toolchain", return_value={"compiler": "changed"} if change == "toolchain" else toolchain):
                try:
                    report = parser.qualify(root)
                except ValueError as error:
                    ensure(change != "none" and "changed" in str(error), f"unexpected qualification refusal: {error}")
                    ensure(not latest.exists(), "refused qualification preserved a stale passing report")
                else:
                    ensure(change == "none", f"changed {change} accepted after qualification fixtures")
                    ensure(report["example"] == {"path": "tools/vela/examples/pure.vela",
                                                  "source_sha256": hashlib.sha256(source).hexdigest()},
                           "qualification omitted tested example byte identity")
                    ensure(json.loads(latest.read_text(encoding="utf-8")) == report,
                           "published qualification report differs from returned evidence")


def cases() -> list[Case]:
    return [Case("native-protocol-and-source-identity", _protocol),
            Case("bounded-read-and-process-controls", _bounds),
            Case("snapshot-version-controls", _versions),
            Case("generator-failure-without-receipt", _failed_build),
            Case("qualification-rechecks-tested-inputs", _qualification_freshness),
            Case("cli-failure-without-output", _cli)]
