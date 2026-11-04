# SPDX-License-Identifier: Apache-2.0
"""Independent compiler-result and real HTTP/LSP controls for the local demo."""

import hashlib
import json
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela
from vos import vela_playground as playground

_SOURCE = ("module Demo;\n// supplementary comment: \U0001f680\n"
           "public Nat Square(Nat x) { let result = x * x; return result; }\n"
           "public bool Small(Nat x) => x <= 5;\n")
_URI = "untitled:playground.vela"


def _refuses(operation: Callable[[], object], kind: str | None = None) -> None:
    try:
        operation()
    except vela.VelaError as error:
        ensure(kind is None or error.kind == kind, f"wrong refusal kind: {error.kind}")
        return
    raise AssertionError("accepted refused compiler input")


def _static_values() -> None:
    source = _SOURCE.encode()
    before = bytes(source)
    natural = vela.evaluate(source, "Square(x: 7) + 1", "Nat")
    boolean = vela.evaluate(source, "Small(6)", "bool")
    ensure(natural == vela.StaticEvaluation("Nat", 50), "console changed pure-call arithmetic")
    ensure(boolean == vela.StaticEvaluation("bool", False), "console changed Boolean evaluation")
    ensure(source == before, "console changed authored source bytes")
    shadow = b"module M; public const Nat __vela_console_result = 9;"
    ensure(vela.evaluate(shadow, "__vela_console_result + 1", "Nat").value == 10,
           "synthetic declaration captured an authored constant")
    ensure(vela.evaluate(source, "Small(5)", "bool").value is True, "true branch changed")
    independent = (b"module Console; public const Nat Base = 7; "
                   b"public Nat Double(Nat value) => value + value; "
                   b"public Nat Choose(bool flag, Nat left, Nat right) { "
                   b"if (flag) { return left; } else { return right; } }")
    selected = "Double(value: Base) + Choose(flag: false, left: 1, right: 3)"
    ensure(vela.evaluate(independent, selected, "Nat").value == 17,
           "independent named-call/branch expression has wrong value")
    ensure(vela.evaluate(independent, "Base <= Double(3)", "bool").value is False,
           "false result was confused with absent evaluation")
    ensure(vela.evaluate(independent, "Double(value: 3) == 6", "bool").value is True,
           "independent equality expression has wrong value")


def _static_refusals() -> None:
    source = _SOURCE.encode()
    for expression in ("1; public const Nat Injected = 2", "1; //", "1; module Other;",
                       "1; public Nat Escape() => 4", "1); public const Nat Injected = (2",
                       "", "import Something", "Square(7); 2"):
        _refuses(lambda expression=expression: vela.evaluate(source, expression, "Nat"))
    _refuses(lambda: vela.evaluate(source, "Small(1)", "Nat"), "type")
    _refuses(lambda: vela.evaluate(source, "missing", "Nat"), "name")
    _refuses(lambda: vela.evaluate(source, "9" * 4097, "Nat"), "limit")
    _refuses(lambda: vela.evaluate(b"module M; public Nat Wrong() => true;", "42", "Nat"), "type")
    _refuses(lambda: vela.evaluate(b"\xff", "42", "Nat"), "encoding")
    runtime = b"module Bad; public Nat F(Nat runtime) { const Nat C = runtime; return C; }"
    _refuses(lambda: vela.evaluate(runtime, "1", "Nat"), "unsupported")
    maximum = "9" * vela.MAX_LITERAL_DIGITS
    _refuses(lambda: vela.evaluate(source, f"{maximum} * 2", "Nat"), "limit")
    declarations = ["module Work; public Nat F0(Nat x) => x;"]
    declarations.extend(f"public Nat F{index}(Nat x) => F{index - 1}(x) + F{index - 1}(x);"
                        for index in range(1, 16))
    exponential = " ".join(declarations).encode()
    vela.translate(exponential)
    _refuses(lambda: vela.evaluate(exponential, "F15(0)", "Nat"), "limit")
    with patch.object(vela, "MAX_STATIC_WORK", 2):
        _refuses(lambda: vela.evaluate(b"module M; public Nat Id(Nat x) => x;", "Id(1) + 2", "Nat"), "limit")
    with patch.object(vela, "MAX_OUTPUT_BYTES", 32):
        _refuses(lambda: vela.evaluate(source, "42", "Nat"), "limit")


@contextmanager
def _running() -> Iterator[playground.PlaygroundServer]:
    with tempfile.TemporaryDirectory(prefix="vos-vela-http-") as temporary:
        assets = Path(temporary)
        (assets / "index.html").write_text("<!doctype html><title>Vela fixture</title>", encoding="utf-8")
        (assets / "app.mjs").write_text("export const fixture = true;", encoding="utf-8")
        (assets / "style.css").write_text("body { color: black; }", encoding="utf-8")
        with playground.PlaygroundServer(0, assets=assets) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield server
            finally:
                server.shutdown()
                thread.join(timeout=3)
                ensure(not thread.is_alive(), "HTTP service failed to stop")


def _http(server: playground.PlaygroundServer, path: str, payload: object = None, *,
          method: str = "POST", headers: dict[str, str] | None = None,
          raw: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    request_headers = {"Authorization": f"Bearer {server.token}", "Content-Type": "application/json",
                       "Origin": server.origin}
    request_headers.update({} if headers is None else headers)
    body = json.dumps(payload, ensure_ascii=False).encode() if raw is None else raw
    try:
        connection.request(method, path, body=None if method == "GET" else body, headers=request_headers)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def _post(server: playground.PlaygroundServer, path: str, payload: object) -> dict[str, object]:
    status, _headers, raw = _http(server, path, payload)
    ensure(status == 200, f"HTTP {status}: {raw!r}")
    return cast("dict[str, object]", json.loads(raw))


def _rpc(server: playground.PlaygroundServer, session: str, method: str,
         params: object = None, identity: int | None = None) -> list[dict[str, object]]:
    message: dict[str, object] = {"jsonrpc": "2.0", "method": method,
                                 "params": {} if params is None else params}
    if identity is not None:
        message["id"] = identity
    response = _post(server, "/api/lsp", {"session": session, "message": message})
    return cast("list[dict[str, object]]", response["messages"])


def _http_compiler() -> None:
    with _running() as server:
        digest = hashlib.sha256(_SOURCE.encode()).hexdigest()
        compiled = _post(server, "/api/compile", {"source": _SOURCE})
        ensure(compiled["ok"] is True and compiled["sourceHash"] == digest and compiled["module"] == "Demo",
               "HTTP compile lost original source identity")
        ensure(compiled["gallina"] == vela.translate(_SOURCE.encode()).gallina,
               "HTTP compile did not expose actual compiler emission")
        evaluated = _post(server, "/api/evaluate",
                          {"source": _SOURCE, "expression": "Square(7)", "valueType": "Nat"})
        ensure(evaluated == {"ok": True, "sourceHash": digest, "valueType": "Nat", "value": "49"},
               "isolated worker returned a fabricated expression value")
        boolean = _post(server, "/api/evaluate",
                        {"source": _SOURCE, "expression": "Small(2)", "valueType": "bool"})
        ensure(boolean["value"] == "true", "Boolean worker result uses wrong representation")
        refused = _post(server, "/api/evaluate",
                        {"source": _SOURCE, "expression": "Square(true)", "valueType": "Nat"})
        error = cast("dict[str, object]", refused["error"])
        ensure(refused["ok"] is False and error["kind"] == "type"
               and str(error["message"]).startswith("expression:") and "gallina" not in refused,
               "refused expression retained success or lost its expression context")
        broken = "module Bad; public Nat Wrong() => true;"
        refused = _post(server, "/api/compile", {"source": broken})
        ensure(refused["ok"] is False and refused["sourceHash"] == hashlib.sha256(broken.encode()).hexdigest(),
               "failed compiler request lost its exact source binding")
        with patch.object(playground.subprocess, "run", side_effect=playground.subprocess.TimeoutExpired("worker", 5)):
            timeout = _post(server, "/api/compile", {"source": _SOURCE})
        ensure(timeout["ok"] is False and cast("dict[str, object]", timeout["error"])["kind"] == "timeout",
               "worker timeout masqueraded as completed compilation")
        malformed = {"ok": False, "sourceHash": digest,
                     "error": {"kind": [], "message": "bad", "line": 1, "column": 1}}
        process = playground.subprocess.CompletedProcess([], 0, json.dumps(malformed).encode(), b"")
        with patch.object(playground.subprocess, "run", return_value=process):
            refused = _post(server, "/api/compile", {"source": _SOURCE})
        ensure(refused["ok"] is False and cast("dict[str, object]", refused["error"])["kind"] == "internal",
               "malformed worker result escaped schema checking")


def _http_authority_and_bounds() -> None:
    with _running() as server:
        for path in ("/", "/index.html", "/app.mjs", "/style.css"):
            status, headers, _raw = _http(server, path, method="GET")
            ensure(status == 200 and headers.get("Cache-Control") == "no-store"
                   and headers.get("Referrer-Policy") == "no-referrer"
                   and headers.get("X-Frame-Options") == "DENY", "asset response lacks local privacy policy")
        for path in ("/../README.md", "/%2e%2e/README.md", "/README.md", "/app.mjs?anything"):
            ensure(_http(server, path, method="GET")[0] == 404, "HTTP exposed a client-selected file")
        for headers, expected in (({"Host": "attacker.invalid"}, 403),
                                  ({"Origin": "https://attacker.invalid"}, 403),
                                  ({"Authorization": "Bearer wrong"}, 401),
                                  ({"Content-Type": "text/plain"}, 415),
                                  ({"Content-Length": "1048577"}, 413),
                                  ({"Transfer-Encoding": "chunked"}, 400)):
            raw = b"" if "Content-Length" in headers or "Transfer-Encoding" in headers else b"{}"
            ensure(_http(server, "/api/session", raw=raw, headers=headers)[0] == expected,
                   f"HTTP authority/body guard failed: {headers}")
        for raw in (b'{"source":"a","source":"b"}', b"[]", b'{"x":NaN}', b'{"x":"\xff"}',
                    b'{"x":' + b"[" * 64 + b"0" + b"]" * 64 + b"}"):
            ensure(_http(server, "/api/compile", raw=raw)[0] == 400, "HTTP accepted invalid strict JSON")
        for payload in ({}, {"source": _SOURCE, "path": "arbitrary"}, {"source": 12},
                        {"source": "x" * (vela.MAX_SOURCE_BYTES + 1)}):
            ensure(_http(server, "/api/compile", payload)[0] == 400, "HTTP accepted invalid compiler shape/size")
        ensure(_http(server, "/api/evaluate", {"source": _SOURCE, "expression": "1", "valueType": "usize"})[0] == 400,
               "HTTP accepted a represented expression type")
        ensure(_http(server, "/api/lsp", {"session": "missing", "message": {}})[0] == 410,
               "unknown session created an implicit LSP server")
        with patch.object(playground, "MAX_SESSIONS", 1):
            identity = cast("str", _post(server, "/api/session", {})["session"])
            ensure(_http(server, "/api/session", {})[0] == 400, "HTTP admitted excess sessions")
            server.sessions[identity].touched -= playground.SESSION_SECONDS + 1
            ensure(_http(server, "/api/lsp", {"session": identity, "message": {}})[0] == 410,
                   "expired session remained usable")
            ensure(isinstance(_post(server, "/api/session", {})["session"], str), "expiry did not release a slot")


def _http_lsp() -> None:
    with _running() as server:
        session = cast("str", _post(server, "/api/session", {})["session"])
        other = cast("str", _post(server, "/api/session", {})["session"])
        initialized = _rpc(server, session, "initialize", {"capabilities": {}}, 1)
        ensure(initialized[0]["id"] == 1 and "result" in initialized[0], "HTTP LSP initialize failed")
        _rpc(server, session, "initialized")
        messages = _rpc(server, session, "textDocument/didOpen", {
            "textDocument": {"uri": _URI, "languageId": "vela", "version": 1, "text": _SOURCE}})
        params = cast("dict[str, object]", messages[0]["params"])
        ensure(params["version"] == 1 and params["diagnostics"] == [], "valid unsaved source has wrong diagnostics")
        result = _rpc(server, session, "textDocument/hover", {
            "textDocument": {"uri": _URI}, "position": {"line": 2, "character": 12}}, 2)
        ensure("Square" in str(result[0].get("result")), "real hover lost compiler signature")
        defined = _rpc(server, session, "textDocument/definition", {
            "textDocument": {"uri": _URI}, "position": {"line": 2, "character": 54}}, 3)
        ensure(defined[0].get("result") == {"uri": _URI, "range": {
            "start": {"line": 2, "character": 31}, "end": {"line": 2, "character": 37}}},
            "definition did not return the independently expected local declaration")
        formatted = _rpc(server, session, "textDocument/formatting", {
            "textDocument": {"uri": _URI}, "options": {"tabSize": 2, "insertSpaces": True}}, 4)
        ensure(isinstance(formatted[0].get("result"), list), "formatting did not return an editor edit")
        _rpc(server, other, "initialize", {"capabilities": {}}, 10)
        _rpc(server, other, "initialized")
        missing = _rpc(server, other, "textDocument/hover", {
            "textDocument": {"uri": _URI}, "position": {"line": 2, "character": 12}}, 11)
        ensure("error" in missing[0], "LSP session leaked another tab's open document")
        broken = _SOURCE.replace("x * x", "true")
        changed = _rpc(server, session, "textDocument/didChange", {
            "textDocument": {"uri": _URI, "version": 2}, "contentChanges": [{"text": broken}]})
        params = cast("dict[str, object]", changed[0]["params"])
        ensure(params["version"] == 2 and params["diagnostics"], "changed unsaved source lost its error/version")
        _rpc(server, session, "textDocument/didChange", {
            "textDocument": {"uri": _URI, "version": 1}, "contentChanges": [{"text": _SOURCE}]})
        refused = _rpc(server, session, "textDocument/hover", {
            "textDocument": {"uri": _URI}, "position": {"line": 2, "character": 12}}, 12)
        ensure(refused[0].get("result") is None, "older update restored successful semantic facts")
        recovered = _rpc(server, session, "textDocument/didChange", {
            "textDocument": {"uri": _URI, "version": 3}, "contentChanges": [{"text": _SOURCE}]})
        ensure(cast("dict[str, object]", recovered[0]["params"])["diagnostics"] == [], "full replacement failed recovery")
        _rpc(server, session, "shutdown", identity=20)
        _rpc(server, session, "exit")


def cases() -> list[Case]:
    return [Case("compiler-owned-static-natural-and-boolean-results", _static_values),
            Case("compiler-refusals-injection-and-existing-budgets", _static_refusals),
            Case("real-isolated-http-compilation-and-evaluation", _http_compiler),
            Case("http-auth-authority-strict-json-path-and-session-bounds", _http_authority_and_bounds),
            Case("real-http-lsp-lifecycle-overlays-navigation-and-formatting", _http_lsp)]
