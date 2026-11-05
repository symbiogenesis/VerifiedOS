# SPDX-License-Identifier: Apache-2.0
"""Independent automatic selection, native-parser identity and transport controls."""

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
from vos.vela_authoring import Finding
from vos.vela_mathematical import Compilation
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


def _capabilities_and_automatic_selection() -> None:
    with _running() as server:
        ensure(_post(server, "/api/capabilities", {}) == {"mathematical": False},
               "host service advertised a native mathematical parser")
        status, _, _ = _http(server, "/api/capabilities", {},
                             headers={"Authorization": "Bearer invalid"})
        ensure(status == 401, "capability discovery bypassed playground authentication")
        status, _, _ = _http(server, "/api/capabilities", {"source": _SOURCE})
        ensure(status == 400, "capabilities accepted a request body outside its contract")
        evaluated = _post(server, "/api/evaluate", {
            "source": _PURE, "expression": "Value()", "valueType": "Nat"})
        ensure(evaluated["ok"] is True and evaluated["value"] == "42",
               "source selection changed the pure compiler's existing result")
        compiled = _post(server, "/api/compile", {"source": _PURE})
        ensure(compiled["editorServices"] is True and compiled["findings"] == [],
               "pure compilation did not restore existing editor services")
        for mode in ("pure", "mathematical", "borrow", "", 1, None):
            status, _, body = _http(server, "/api/compile", {"source": _SOURCE, "mode": mode})
            ensure(status == 400 and "error" in json.loads(body),
                   f"client-selected compiler mode {mode!r} reached compilation")
    with _mathematical_server() as (server, _parser):
        ensure(_post(server, "/api/capabilities", {}) == {"mathematical": True},
               "prepared native service omitted its mathematical capability")


def _http_dispatch_and_strict_fields() -> None:
    with _mathematical_server() as (server, parser):
        request = {"source": _SOURCE, "expression": "Last()", "valueType": "Nat"}
        with patch.object(playground.subprocess, "run", return_value=_process(_result())) as worker:
            ensure(_post(server, "/api/evaluate", request) == _result(),
                   "mathematical HTTP response changed its exact source or typed value")
        forwarded = json.loads(cast("bytes", worker.call_args.kwargs["input"]))
        ensure(forwarded == {**request, "action": "evaluate"},
               "HTTP automatic dispatch changed authored input")
        invocation = cast("list[str]", worker.call_args.args[0])
        ensure(_SOURCE not in " ".join(invocation) and "Last()" not in " ".join(invocation),
               "authored mathematical source or expression became an executable argument")
        ensure(worker.call_args.kwargs["timeout"] == playground.WORKER_SECONDS,
               "mathematical compilation escaped the isolated worker timeout")
        compile_reply: dict[str, object] = {
            "ok": True, "sourceHash": _DIGEST, "module": "Indexed", "gallina": "Module Indexed.\nEnd Indexed.\n",
            "editorServices": False, "findings": []}
        with patch.object(playground.subprocess, "run", return_value=_process(compile_reply)):
            ensure(_post(server, "/api/compile", {"source": _SOURCE}) == compile_reply,
                   "mathematical compilation lost its Gallina result")
        invalid_requests: tuple[tuple[str, dict[str, object]], ...] = (
            ("/api/compile", {"source": _SOURCE, "parser": str(parser)}),
            ("/api/compile", {"source": _SOURCE, "executable": str(parser)}),
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
        request = {"source": _SOURCE, "expression": "Last()", "valueType": "Nat"}
        malformed: tuple[dict[str, object], ...] = (
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
        semantic_error: dict[str, object] = {"kind": "type", "message": "expression: wrong vector length",
                                            "line": 1, "column": 1}
        semantic: dict[str, object] = {"ok": False, "sourceHash": _DIGEST, "error": semantic_error}
        for kind in ("type", "inference", "protocol"):
            semantic_error["kind"] = kind
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
            return _process({"ok": True, "sourceHash": _DIGEST, "module": "Indexed", "gallina": "stale terms",
                             "editorServices": False, "findings": []})

        request = {"source": _SOURCE}
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
        with patch.object(playground.subprocess, "run") as worker:
            pure = _post(server, "/api/compile", {"source": _PURE})
        ensure(pure["ok"] is False and pure["editorServices"] is False and not worker.called,
               "changed parser retained authority through automatic pure selection")
        authoring = _post(server, "/api/authoring", {"source": _PURE})
        ensure(authoring["ok"] is True,
               "independent authoring unnecessarily depended on mathematical parser identity")


def _worker_mathematical_routing() -> None:
    parser = Path("/prepared/native/vela-parser")
    compile_input: dict[str, object] = {"source": _SOURCE, "action": "compile"}
    with patch("vos.vela_mathematical.compile_source", return_value=Compilation("Indexed", "actual Gallina", ())) as compile_math:
        response = compile_request(compile_input, mathematical_parser=parser)
    ensure(response == {"ok": True, "sourceHash": _DIGEST,
                        "module": "Indexed", "gallina": "actual Gallina", "editorServices": False, "findings": []},
           "worker changed the mathematical elaborator's actual result")
    ensure(compile_math.call_args.args == (_SOURCE.encode(), parser),
           "worker did not forward the exact source bytes and server-owned parser")
    finding = Finding("VELA105", "generic type parameter 'element' should use PascalCase", 3, 36)
    with patch("vos.vela_mathematical.compile_source",
               return_value=Compilation("Indexed", "actual Gallina", (finding,))):
        response = compile_request(compile_input, mathematical_parser=parser)
    ensure(response["findings"] == [{"code": "VELA105", "message": finding.message, "line": 3, "column": 36}],
           "worker lost the mathematical producer's original naming finding")
    evaluate_input: dict[str, object] = {"source": _SOURCE, "action": "evaluate",
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
    ensure(response == {"ok": False, "sourceHash": _DIGEST, "editorServices": False,
                        "error": {"kind": "type", "message": "wrong length", "line": 3, "column": 12}},
           "worker lost original mathematical diagnostic positions or source identity")


def _automatic_selection_preserves_refusals() -> None:
    parser = Path("/prepared/native/vela-parser")
    with patch("vos.vela_mathematical.compile_source") as mathematical:
        pure = compile_request({"source": _PURE, "action": "compile"}, mathematical_parser=parser)
        ensure(pure["ok"] is True and pure["editorServices"] is True and pure["findings"] == []
               and not mathematical.called,
               "automatic source selection bypassed the accepted pure compiler")
        for source, kind in (("module Bad; public Nat Wrong() => true;", "type"),
                             ("module Bad; public Nat Wrong() => Missing;", "name")):
            refused = compile_request({"source": source, "action": "compile"}, mathematical_parser=parser)
            ensure(refused["ok"] is False and refused["editorServices"] is True
                   and cast("dict[str, object]", refused["error"])["kind"] == kind
                   and not mathematical.called,
                   "a pure semantic refusal was retried through mathematical elaboration")
        for kind in ("name", "type", "encoding", "limit"):
            with patch("vos.vela_playground_worker.translate", side_effect=VelaError(kind, 2, 3, "original refusal")):
                refused = compile_request({"source": _PURE, "action": "compile"}, mathematical_parser=parser)
            ensure(refused == {"ok": False, "sourceHash": hashlib.sha256(_PURE.encode()).hexdigest(),
                               "editorServices": True,
                               "error": {"kind": kind, "message": "original refusal", "line": 2, "column": 3}}
                   and not mathematical.called,
                   "automatic selection replaced a retained source judgment")
    with patch("vos.vela_mathematical.evaluate_source") as mathematical:
        for expression, kind in (("true", "type"), ("Missing()", "name"),
                                 ("1; public const Nat Injected = 7", "syntax"),
                                 ("9" * 4097, "limit")):
            refused = compile_request({"source": _PURE, "action": "evaluate", "expression": expression,
                                       "valueType": "Nat"}, mathematical_parser=parser)
            ensure(refused["ok"] is False and cast("dict[str, object]", refused["error"])["kind"] == kind
                   and not mathematical.called,
                   "a refused console expression changed the selected source compiler")
        accepted = compile_request({"source": _PURE, "action": "evaluate", "expression": "Value()",
                                    "valueType": "Nat"}, mathematical_parser=parser)
        ensure(accepted["ok"] is True and accepted["value"] == "42" and not mathematical.called,
               "pure worker did not recover after console refusal")


def _mathematical_naming_reply_validation() -> None:
    source = ("module Naming;\n// supplementary: \U0001f680\r\n"
              "public definition element Identity<element>(element value) => value;\n")
    digest = hashlib.sha256(source.encode()).hexdigest()
    finding: dict[str, object] = {
        "code": "VELA105", "message": "generic type parameter 'element' should use PascalCase",
        "line": 3, "column": 36}
    valid: dict[str, object] = {"ok": True, "sourceHash": digest, "module": "Naming",
                                "gallina": "actual checked-source terms", "editorServices": False, "findings": [finding]}
    request: dict[str, object] = {"source": source}
    malformed: tuple[dict[str, object], ...] = (
        {key: value for key, value in valid.items() if key != "findings"},
        {key: value for key, value in valid.items() if key != "editorServices"},
        {**valid, "editorServices": 0},
        {**valid, "editorServices": "false"},
        {**valid, "editorServices": True},
        {**valid, "findings": None},
        {**valid, "findings": "not a list"},
        {**valid, "findings": [{**finding, "code": "VELA100"}]},
        {**valid, "findings": [{**finding, "code": "VELA999"}]},
        {**valid, "findings": [{**finding, "line": True}]},
        {**valid, "findings": [{**finding, "line": 99}]},
        {**valid, "findings": [{**finding, "column": 999}]},
        {**valid, "findings": [{**finding, "column": 7}]},
        {**valid, "findings": [{**finding, "column": 37}]},
        {**valid, "findings": [{**finding, "message": ""}]},
        {**valid, "findings": [{**finding, "extra": "unrecognized"}]},
        {**valid, "findings": [finding, finding]},
        {**valid, "sourceHash": hashlib.sha256(b"old source").hexdigest()},
    )
    with _mathematical_server() as (server, _parser):
        with patch.object(playground.subprocess, "run", return_value=_process(valid)):
            ensure(_post(server, "/api/compile", request) == valid,
                   "valid naming warnings prevented mathematical compilation")
        for response in malformed:
            with patch.object(playground.subprocess, "run", return_value=_process(response)):
                refused = _post(server, "/api/compile", request)
            ensure(refused["ok"] is False and refused["sourceHash"] == digest
                   and cast("dict[str, object]", refused["error"])["kind"] == "internal"
                   and "gallina" not in refused and "findings" not in refused,
                   "invalid naming findings retained compilation output or a clean warning result")
        with patch.object(playground, "MAX_AUTHORING_FINDINGS", 0), \
                patch.object(playground.subprocess, "run", return_value=_process(valid)):
            refused = _post(server, "/api/compile", request)
        ensure(refused["ok"] is False and "gallina" not in refused,
               "mathematical naming findings escaped their configured count budget")
        underscored_source = source.replace("element", "T_value")
        underscored: dict[str, object] = {
            **valid, "sourceHash": hashlib.sha256(underscored_source.encode()).hexdigest(),
            "findings": [{**finding, "message": "generic type parameter 'T_value' should use PascalCase"}]}
        with patch.object(playground.subprocess, "run", return_value=_process(underscored)):
            ensure(_post(server, "/api/compile", {**request, "source": underscored_source}) == underscored,
                   "capital-initial name with underscores was confused with PascalCase")
        capital_source = source.replace("element", "T")
        capital: dict[str, object] = {
            **valid, "sourceHash": hashlib.sha256(capital_source.encode()).hexdigest(),
            "findings": [{**finding, "message": "generic type parameter 'T' should use PascalCase", "column": 30}]}
        with patch.object(playground.subprocess, "run", return_value=_process(capital)):
            refused = _post(server, "/api/compile", {**request, "source": capital_source})
        ensure(refused["ok"] is False and "findings" not in refused,
               "clean PascalCase type received a fabricated naming warning")
        two_source = source + "public definition item Again<item>(item value) => value;\n"
        later: dict[str, object] = {**finding, "line": 4, "column": 30,
                                    "message": "generic type parameter 'item' should use PascalCase"}
        reordered: dict[str, object] = {
            **valid, "sourceHash": hashlib.sha256(two_source.encode()).hexdigest(), "findings": [later, finding]}
        with patch.object(playground.subprocess, "run", return_value=_process(reordered)):
            refused = _post(server, "/api/compile", {**request, "source": two_source})
        ensure(refused["ok"] is False and "findings" not in refused,
               "out-of-order worker naming coordinates bypassed complete reply validation")
        with patch.object(playground.subprocess, "run", return_value=_process(valid)):
            ensure(_post(server, "/api/compile", request) == valid,
                   "mathematical naming transport failed recovery after malformed warnings")


def _native_cli_startup() -> None:
    commands = [command for command in COMMANDS if command.name.startswith("vela-playground")]
    ensure(len(commands) == 1 and commands[0].guest_only([]),
           "unified playground did not select exactly one native-backed launch")
    with patch("vos.vela_parser.build") as build, patch.object(playground_cli, "PlaygroundServer") as factory:
        prepared = build.return_value
        prepared.executable = Path("/native/lane/build/vela-parser")
        server = factory.return_value.__enter__.return_value
        server.launch_url = "http://127.0.0.1:12345/#token=fixture"
        ensure(playground_cli.main(["--port", "0"]) == 0,
               "mathematical playground failed its prepared native startup")
        ensure(build.call_count == 1 and factory.call_args.args == (0,)
               and factory.call_args.kwargs == {"mathematical_parser": prepared.executable},
               "native parser was rebuilt per request or not supplied to the local server")
        ensure(server.serve_forever.call_count == 1,
               "prepared mathematical playground did not enter its HTTP service")
    with patch("vos.vela_parser.build", side_effect=RuntimeError("native tools unavailable")), \
            patch.object(playground_cli, "PlaygroundServer") as factory:
        ensure(playground_cli.main(["--port", "0"]) == 1 and not factory.called,
               "unavailable native toolchain started a mathematical service without its parser")


def _pure_authoring_rejects_mathematical_lint() -> None:
    digest = hashlib.sha256(_PURE.encode()).hexdigest()
    clean: dict[str, object] = {"ok": True, "sourceHash": digest, "bindingPreview": _PURE, "findings": []}
    invalid: dict[str, object] = {
        **clean, "findings": [{"code": "VELA105", "message": "unsupported generic type naming finding",
                              "line": 1, "column": 1}]}
    with _running() as server:
        with patch.object(playground.subprocess, "run", return_value=_process(invalid)):
            refused = _post(server, "/api/authoring", {"source": _PURE})
        ensure(refused["ok"] is False and cast("dict[str, object]", refused["error"])["kind"] == "internal"
               and "findings" not in refused and "bindingPreview" not in refused,
               "pure authoring accepted a mathematical-only naming finding")
        with patch.object(playground.subprocess, "run", return_value=_process(clean)):
            ensure(_post(server, "/api/authoring", {"source": _PURE}) == clean,
                   "pure authoring failed recovery after a refused mathematical finding")


def _playground_formatting_example_assets() -> None:
    root = Path(__file__).resolve().parents[2]
    html = (root / "tools/vela/playground/index.html").read_text(encoding="utf-8")
    script = (root / "tools/vela/playground/app.mjs").read_text(encoding="utf-8")
    ensure('<option value="formatting">Raw strings &amp; checked formatting</option>' in html,
           "playground selector omitted the raw-strings and checked-formatting example")
    ensure("formatting: {" in script and "Format.Write(ref " in script and '"""' in script,
           "playground app.mjs omitted the raw-strings and checked-formatting example source")


def cases() -> list[Case]:
    return [Case("unified-capabilities-authentication-and-source-selection", _capabilities_and_automatic_selection),
            Case("unified-http-source-routing-and-request-field-refusals", _http_dispatch_and_strict_fields),
            Case("mathematical-worker-source-type-and-schema-refusals-with-recovery", _worker_reply_binding),
            Case("mathematical-changed-parser-identity-refuses-before-worker", _changed_parser_refuses),
            Case("mathematical-worker-reuses-elaborator-and-preserves-refusals", _worker_mathematical_routing),
            Case("automatic-selection-preserves-source-and-expression-refusals", _automatic_selection_preserves_refusals),
            Case("mathematical-naming-findings-source-shape-budget-and-recovery", _mathematical_naming_reply_validation),
            Case("pure-authoring-refuses-mathematical-only-naming-finding", _pure_authoring_rejects_mathematical_lint),
            Case("mathematical-cli-prepares-native-parser-once-and-refuses-missing-tools", _native_cli_startup),
            Case("playground-formatting-example-assets", _playground_formatting_example_assets)]
