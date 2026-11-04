# SPDX-License-Identifier: Apache-2.0
"""Independent mode, native-parser identity and worker transport controls."""

import hashlib
import json
import tempfile
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_vela_playground import _http, _post, _running
from vos import vela_playground as playground
from vos.cli import vela_playground as playground_cli
from vos.commands import COMMANDS
from vos.vela import StaticEvaluation, VelaError
from vos.vela_elaborate import Elaboration
from vos.vela_playground_worker import compile_request

_PURE = "module Simple; public Nat Value() => 42;"
_SOURCE = ("module Indexed;\n// supplementary comment: \U0001f680\n"
           "public definition Vec<Nat, 2> Pair() => VCons(7, VCons(8, VNil<Nat>()));\n"
           "public definition Nat Last() => At(Pair(), FSucc(FZero<0>()));\n")
_DIGEST = hashlib.sha256(_SOURCE.encode()).hexdigest()


@contextmanager
def _mathematical_server() -> Generator[tuple[playground.PlaygroundServer, Path]]:
    with tempfile.TemporaryDirectory(prefix="vos-vela-math-http-") as temporary:
        parser = Path(temporary) / "vela-parser"
        parser.write_bytes(b"independently prepared native-parser fixture")
        with playground.PlaygroundServer(0, mathematical_parser=parser) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield server, parser
            finally:
                server.shutdown()
                thread.join(timeout=3)
                ensure(not thread.is_alive(), "mathematical HTTP service failed to stop")


def _result(value: str = "8", value_type: str = "Nat") -> dict[str, object]:
    return {"ok": True, "sourceHash": _DIGEST, "valueType": value_type, "value": value}


def _process(response: dict[str, object]) -> playground.subprocess.CompletedProcess[bytes]:
    return playground.subprocess.CompletedProcess([], 0, json.dumps(response).encode(), b"")


def _capabilities_and_pure_defaults() -> None:
    with _running() as server:
        ensure(_post(server, "/api/capabilities", {}) == {"mathematical": False},
               "host service advertised a native mathematical parser")
        status, _, _ = _http(server, "/api/capabilities", {},
                             headers={"Authorization": "Bearer invalid"})
        ensure(status == 401, "capability discovery bypassed playground authentication")
        status, _, _ = _http(server, "/api/capabilities", {"source": _SOURCE})
        ensure(status == 400, "capabilities accepted a request body outside its contract")
        implicit = _post(server, "/api/evaluate", {
            "source": _PURE, "expression": "Value()", "valueType": "Nat"})
        explicit = _post(server, "/api/evaluate", {
            "source": _PURE, "expression": "Value()", "valueType": "Nat", "mode": "pure"})
        ensure(implicit == explicit and implicit["value"] == "42",
               "adding an explicit pure mode changed the compiler's existing result")
        for mode in ("mathematical", "borrow", "", 1, None):
            status, _, body = _http(server, "/api/compile", {"source": _SOURCE, "mode": mode})
            ensure(status == 400 and "error" in json.loads(body),
                   f"unavailable or malformed mode {mode!r} reached compilation")
    with _mathematical_server() as (server, _parser):
        ensure(_post(server, "/api/capabilities", {}) == {"mathematical": True},
               "prepared native service omitted its mathematical capability")


def _http_dispatch_and_strict_fields() -> None:
    with _mathematical_server() as (server, parser):
        request = {"source": _SOURCE, "mode": "mathematical",
                   "expression": "Last()", "valueType": "Nat"}
        with patch.object(playground.subprocess, "run", return_value=_process(_result())) as worker:
            ensure(_post(server, "/api/evaluate", request) == _result(),
                   "mathematical HTTP response changed its exact source or typed value")
        forwarded = json.loads(cast("bytes", worker.call_args.kwargs["input"]))
        ensure(forwarded == {**request, "action": "evaluate"},
               "HTTP mathematical dispatch changed authored input or mode")
        invocation = cast("list[str]", worker.call_args.args[0])
        ensure(_SOURCE not in " ".join(invocation) and "Last()" not in " ".join(invocation),
               "authored mathematical source or expression became an executable argument")
        ensure(worker.call_args.kwargs["timeout"] == playground.WORKER_SECONDS,
               "mathematical compilation escaped the isolated worker timeout")
        compile_reply: dict[str, object] = {
            "ok": True, "sourceHash": _DIGEST, "module": "Indexed", "gallina": "Module Indexed.\nEnd Indexed.\n"}
        with patch.object(playground.subprocess, "run", return_value=_process(compile_reply)):
            ensure(_post(server, "/api/compile", {"source": _SOURCE, "mode": "mathematical"}) == compile_reply,
                   "mathematical compilation lost its Gallina result")
        invalid_requests: tuple[tuple[str, dict[str, object]], ...] = (
            ("/api/compile", {"source": _SOURCE, "mode": "mathematical", "parser": str(parser)}),
            ("/api/compile", {"source": _SOURCE, "mode": "mathematical", "executable": str(parser)}),
            ("/api/authoring", {"source": _SOURCE, "mode": "mathematical"}),
            ("/api/evaluate", {**request, "valueType": "Vec<Nat,2>"}),
            ("/api/evaluate", {**request, "expression": "x" * 4097}),
            ("/api/compile", {"source": _SOURCE, "mode": {"name": "mathematical"}}),
        )
        with patch.object(playground.subprocess, "run") as worker:
            for path, payload in invalid_requests:
                status, _, _ = _http(server, path, payload)
                ensure(status == 400, f"invalid mathematical request reached {path}")
            ensure(not worker.called, "malformed request launched a compiler worker")


def _worker_reply_binding() -> None:
    with _mathematical_server() as (server, _parser):
        request = {"source": _SOURCE, "mode": "mathematical",
                   "expression": "Last()", "valueType": "Nat"}
        malformed = (
            {**_result(), "sourceHash": hashlib.sha256(b"different source").hexdigest()},
            {**_result(), "mode": "mathematical"},
            _result("-1"),
            _result("true", "bool"),
            {**_result(), "value": 8},
            {"ok": False, "sourceHash": _DIGEST,
             "error": {"kind": "type", "message": "wrong length", "line": True, "column": 1}},
            {"ok": False, "sourceHash": _DIGEST,
             "error": {"kind": "invented", "message": "wrong length", "line": 1, "column": 1}},
        )
        for response in malformed:
            with patch.object(playground.subprocess, "run", return_value=_process(response)):
                refused = _post(server, "/api/evaluate", request)
            ensure(refused["ok"] is False and refused["sourceHash"] == _DIGEST
                   and cast("dict[str, object]", refused["error"])["kind"] == "internal"
                   and "value" not in refused and "gallina" not in refused,
                   "malformed mathematical worker reply escaped source/type/schema validation")
        semantic: dict[str, object] = {"ok": False, "sourceHash": _DIGEST,
                                      "error": {"kind": "type", "message": "expression: wrong vector length",
                                                "line": 1, "column": 1}}
        for kind in ("type", "inference", "protocol"):
            cast("dict[str, object]", semantic["error"])["kind"] = kind
            with patch.object(playground.subprocess, "run", return_value=_process(semantic)):
                ensure(_post(server, "/api/evaluate", request) == semantic,
                       "semantic mathematical refusal was replaced with a success or infrastructure error")
        with patch.object(playground.subprocess, "run",
                          side_effect=playground.subprocess.TimeoutExpired("worker", playground.WORKER_SECONDS)):
            refused = _post(server, "/api/evaluate", request)
        ensure(refused["ok"] is False and refused["sourceHash"] == _DIGEST
               and cast("dict[str, object]", refused["error"])["kind"] == "timeout",
               "mathematical worker timeout retained a successful or unbound result")
        with patch.object(playground.subprocess, "run", return_value=_process(_result())):
            ensure(_post(server, "/api/evaluate", request) == _result(),
                   "mathematical transport failed recovery after rejected worker replies")


def _changed_parser_refuses() -> None:
    with _mathematical_server() as (server, parser):
        def replace_during_worker(*_args: object, **_kwargs: object) -> playground.subprocess.CompletedProcess[bytes]:
            parser.write_bytes(b"replaced parser with different executable bytes")
            return _process({"ok": True, "sourceHash": _DIGEST, "module": "Indexed", "gallina": "stale terms"})

        request = {"source": _SOURCE, "mode": "mathematical"}
        with patch.object(playground.subprocess, "run", side_effect=replace_during_worker) as worker:
            refused = _post(server, "/api/compile", request)
        ensure(worker.call_count == 1 and refused["ok"] is False and "gallina" not in refused,
               "parser changed during compilation retained its earlier successful result")
        with patch.object(playground.subprocess, "run") as worker:
            status, _, body = _http(server, "/api/compile", request)
        response = cast("dict[str, object]", json.loads(body))
        ensure(status != 200 or response.get("ok") is False,
               "changed native parser identity retained mathematical compile authority")
        ensure(not worker.called, "changed native parser launched an isolated compiler worker")
        pure = _post(server, "/api/evaluate", {
            "source": _PURE, "expression": "Value()", "valueType": "Nat"})
        ensure(pure["ok"] is True and pure["value"] == "42",
               "unavailable mathematical parser disabled the independent pure compiler")


def _worker_mathematical_routing() -> None:
    parser = Path("/prepared/native/vela-parser")
    compile_input: dict[str, object] = {"source": _SOURCE, "mode": "mathematical", "action": "compile"}
    with patch("vos.vela_mathematical.compile_source", return_value=Elaboration("Indexed", "actual Gallina")) as compile_math:
        response = compile_request(compile_input, mathematical_parser=parser)
    ensure(response == {"ok": True, "sourceHash": _DIGEST,
                        "module": "Indexed", "gallina": "actual Gallina"},
           "worker changed the mathematical elaborator's actual result")
    ensure(compile_math.call_args.args == (_SOURCE.encode(), parser),
           "worker did not forward the exact source bytes and server-owned parser")
    evaluate_input: dict[str, object] = {"source": _SOURCE, "mode": "mathematical", "action": "evaluate",
                                       "expression": "Last()", "valueType": "Nat"}
    with patch("vos.vela_mathematical.evaluate_source", return_value=StaticEvaluation("Nat", 8)) as evaluate_math:
        response = compile_request(evaluate_input, mathematical_parser=parser)
    ensure(response == _result(), "worker fabricated a mathematical console value")
    ensure(evaluate_math.call_args.args == (_SOURCE.encode(), "Last()", "Nat", parser),
           "worker changed the selected expression, result type or parser identity")
    with patch("vos.vela_mathematical.evaluate_source", return_value=StaticEvaluation("bool", False)):
        response = compile_request({**evaluate_input, "valueType": "bool"}, mathematical_parser=parser)
    ensure(response == _result("false", "bool"), "false mathematical result was confused with no result")
    with patch("vos.vela_mathematical.compile_source", side_effect=VelaError("type", 3, 12, "wrong length")):
        response = compile_request(compile_input, mathematical_parser=parser)
    ensure(response == {"ok": False, "sourceHash": _DIGEST,
                        "error": {"kind": "type", "message": "wrong length", "line": 3, "column": 12}},
           "worker lost original mathematical diagnostic positions or source identity")


def _native_cli_startup() -> None:
    commands = [command for command in COMMANDS if command.name == "vela-playground-math"]
    ensure(len(commands) == 1 and commands[0].guest_only([]),
           "native mathematical playground command did not select the guest toolchain")
    with patch("vos.vela_parser.build") as build, patch.object(playground_cli, "PlaygroundServer") as factory:
        prepared = build.return_value
        prepared.executable = Path("/native/lane/build/vela-parser")
        server = factory.return_value.__enter__.return_value
        server.launch_url = "http://127.0.0.1:12345/#token=fixture"
        ensure(playground_cli.serve(["--port", "0"], mathematical=True) == 0,
               "mathematical playground failed its prepared native startup")
        ensure(build.call_count == 1 and factory.call_args.args == (0,)
               and factory.call_args.kwargs == {"mathematical_parser": prepared.executable},
               "native parser was rebuilt per request or not supplied to the local server")
        ensure(server.serve_forever.call_count == 1,
               "prepared mathematical playground did not enter its HTTP service")
    with patch("vos.vela_parser.build", side_effect=RuntimeError("native tools unavailable")), \
            patch.object(playground_cli, "PlaygroundServer") as factory:
        ensure(playground_cli.serve(["--port", "0"], mathematical=True) == 1 and not factory.called,
               "unavailable native toolchain started a mathematical service without its parser")
    with patch("vos.vela_parser.build") as build, patch.object(playground_cli, "PlaygroundServer") as factory:
        factory.return_value.__enter__.return_value.launch_url = "http://127.0.0.1:12345/"
        ensure(playground_cli.serve(["--port", "0"]) == 0 and not build.called,
               "retained pure host command unexpectedly invoked the native parser toolchain")


def cases() -> list[Case]:
    return [Case("mathematical-capabilities-authentication-and-retained-pure-default", _capabilities_and_pure_defaults),
            Case("mathematical-http-mode-routing-and-request-field-refusals", _http_dispatch_and_strict_fields),
            Case("mathematical-worker-source-type-and-schema-refusals-with-recovery", _worker_reply_binding),
            Case("mathematical-changed-parser-identity-refuses-before-worker", _changed_parser_refuses),
            Case("mathematical-worker-reuses-elaborator-and-preserves-refusals", _worker_mathematical_routing),
            Case("mathematical-cli-prepares-native-parser-once-and-refuses-missing-tools", _native_cli_startup)]
