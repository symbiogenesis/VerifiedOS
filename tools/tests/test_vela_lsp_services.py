# SPDX-License-Identifier: Apache-2.0
"""Independent resolved-name and stdio controls for pure Vela LSP services."""

import json
import subprocess
import sys
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.vela.lsp import Server

INDEPENDENT_CASES = True

_URI = "untitled:independent-navigation.vela"
_SCOPE = "\n".join((
    "module Scope;",
    "public Nat Earlier(Nat value) {",
    "  return value;",
    "}",
    "public Nat Later(Nat value, bool flag) {",
    "  let Earlier = value;",
    "  if (flag) {",
    "    let local = Earlier;",
    "    return Earlier(local);",
    "  } else {",
    "    let local = value;",
    "    return local;",
    "  }",
    "}",
))


def _object(value: object) -> dict[str, object]:
    ensure(isinstance(value, dict), f"expected object, got {value!r}")
    return cast("dict[str, object]", value)


def _array(value: object) -> list[object]:
    ensure(isinstance(value, list), f"expected array, got {value!r}")
    return cast("list[object]", value)


def _request(method: str, params: object = None, identity: int = 70) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identity, "method": method,
            "params": {} if params is None else params}


def _notice(method: str, params: object = None) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": {} if params is None else params}


def _params(line: int = 0, character: int = 0, uri: str = _URI) -> dict[str, object]:
    return {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}}


def _reply(server: Server, method: str, params: object = None,
           identity: int = 70) -> dict[str, object]:
    replies = server.handle(_request(method, params, identity))
    ensure(len(replies) == 1 and replies[0].get("id") == identity,
           f"service request lost correlation: {replies!r}")
    return replies[0]


def _result(server: Server, method: str, params: object = None) -> object:
    reply = _reply(server, method, params)
    ensure("result" in reply and "error" not in reply, f"service failed: {reply!r}")
    return reply["result"]


def _error(server: Server, method: str, params: object, code: int) -> None:
    reply = _reply(server, method, params)
    ensure(_object(reply.get("error")).get("code") == code,
           f"expected error {code}, got {reply!r}")


def _open(server: Server, text: str, uri: str = _URI, version: int = 1) -> None:
    replies = server.handle(_notice("textDocument/didOpen", {"textDocument": {
        "uri": uri, "languageId": "vela", "version": version, "text": text}}))
    ensure(len(replies) == 1 and replies[0].get("method") == "textDocument/publishDiagnostics",
           f"open omitted diagnostics: {replies!r}")


def _server(text: str = _SCOPE, uri: str = _URI) -> Server:
    server = Server()
    result = _object(_result(server, "initialize", {"capabilities": {}}))
    capabilities = _object(result.get("capabilities"))
    for provider in ("hoverProvider", "definitionProvider", "referencesProvider", "documentSymbolProvider"):
        ensure(bool(capabilities.get(provider)), f"implemented provider {provider} not advertised")
    for provider in ("completionProvider", "renameProvider"):
        ensure(not capabilities.get(provider), f"unimplemented provider {provider} advertised")
    server.handle(_notice("initialized"))
    _open(server, text, uri)
    return server


def _span(line: int, column: int, length: int) -> dict[str, object]:
    return {"start": {"line": line, "character": column},
            "end": {"line": line, "character": column + length}}


def _location(line: int, column: int, length: int, uri: str = _URI) -> dict[str, object]:
    return {"uri": uri, "range": _span(line, column, length)}


def _hover(server: Server, line: int, column: int, detail: str, length: int) -> None:
    result = _object(_result(server, "textDocument/hover", _params(line, column)))
    contents = _object(result.get("contents"))
    ensure(contents.get("kind") == "plaintext", "hover did not use plain text")
    value = contents.get("value")
    ensure(isinstance(value, str) and detail in value and "unqualified" in value.lower(),
           f"hover omitted the independently expected type or status: {result!r}")
    ensure(result.get("range") == _span(line, column, length),
           f"hover identifier range is wrong: {result!r}")


def _references(server: Server, line: int, column: int, include: bool) -> object:
    params = _params(line, column)
    params["context"] = {"includeDeclaration": include}
    return _result(server, "textDocument/references", params)


def _resolved_namespaces_and_scopes() -> None:
    server = _server()
    _hover(server, 1, 11, "public Nat Earlier(Nat value)", 7)
    _hover(server, 4, 11, "public Nat Later(Nat value, bool flag)", 5)
    _hover(server, 4, 21, "value: Nat", 5)
    _hover(server, 4, 33, "flag: bool", 4)
    _hover(server, 5, 6, "Earlier: Nat", 7)
    for position, target in (((2, 9), (1, 23, 5)), ((5, 16), (4, 21, 5)),
                             ((7, 16), (5, 6, 7)), ((8, 11), (1, 11, 7)),
                             ((8, 19), (7, 8, 5)), ((11, 11), (10, 8, 5))):
        ensure(_result(server, "textDocument/definition", _params(*position)) == _location(*target),
               f"definition confused a scope or call/value namespace at {position}")
    ensure(_references(server, 1, 11, False) == [_location(8, 11, 7)],
           "function references included same-spelled local uses")
    ensure(_references(server, 1, 11, True) == [_location(1, 11, 7), _location(8, 11, 7)],
           "includeDeclaration did not include exactly the function declaration")
    ensure(_references(server, 5, 6, False) == [_location(7, 16, 7)],
           "value references included the same-spelled function call")
    ensure(_references(server, 4, 21, True) == [
        _location(4, 21, 5), _location(5, 16, 5), _location(10, 16, 5)],
        "same-spelled parameters in separate functions shared an identity")
    ensure(_references(server, 7, 8, True) == [_location(7, 8, 5), _location(8, 19, 5)],
           "sibling branch declarations shared an identity")
    symbols = [_object(value) for value in _array(_result(
        server, "textDocument/documentSymbol", {"textDocument": {"uri": _URI}}))]
    expected = [("Earlier", 12, 1, 11, 7), ("value", 13, 1, 23, 5),
                ("Later", 12, 4, 11, 5), ("value", 13, 4, 21, 5),
                ("flag", 13, 4, 33, 4), ("Earlier", 13, 5, 6, 7),
                ("local", 13, 7, 8, 5), ("local", 13, 10, 8, 5)]
    ensure(len(symbols) == len(expected), f"wrong complete symbol count: {symbols!r}")
    for actual, (name, kind, line, column, length) in zip(symbols, expected, strict=True):
        ensure(actual.get("name") == name and actual.get("kind") == kind
               and actual.get("location") == _location(line, column, length)
               and "children" not in actual,
               f"flat source-ordered symbol disagrees with the fixture: {actual!r}")
    inferred = _server("module Types;\npublic bool Choose(bool flag) {\n"
                       "  let local = flag;\n  return local;\n}")
    _hover(inferred, 2, 6, "local: bool", 5)
    ensure(_result(inferred, "textDocument/definition", _params(3, 9)) == _location(2, 6, 5),
           "inferred bool local did not resolve to its own declaration")


def _unicode_newlines_and_half_open_ranges() -> None:
    for newline in ("\n", "\r\n", "\r"):
        source = newline.join(("// 😀", "module Unicode;",
                               "public Nat Result(Nat input) {", "  return input;", "}"))
        server = _server(source)
        _hover(server, 2, 11, "public Nat Result(Nat input)", 6)
        ensure(_result(server, "textDocument/definition", _params(3, 10)) == _location(2, 22, 5),
               f"UTF-8 bytes or newline width leaked into UTF-16 positions for {newline!r}")
        for position in ((0, 3), (1, 0), (2, 10), (2, 17), (2, 27), (3, 14), (4, 999)):
            ensure(_result(server, "textDocument/hover", _params(*position)) is None,
                   f"non-symbol or half-open end {position} selected a symbol")
        _error(server, "textDocument/hover", _params(0, 4), -32602)
        _error(server, "textDocument/definition", _params(99, 0), -32602)


def _failed_complete_checks_have_no_facts() -> None:
    sources = [
        "module Bad; public Nat Good(Nat x) { return x; } public Nat Bad() { return missing; }",
        "module Bad; public Nat Good() { return 0; } public Nat Bad() { return true; }",
        "module Bad; public Nat Good() { return 0; } public String Bad() { return 0; }",
        "module Bad; public Nat First() { return Later(); } public Nat Later() { return 0; }",
        "module Bad; public Nat Good() { return 0; } public Nat Broken() { return ; }",
    ]
    for source in sources:
        server = _server(source)
        for method in ("textDocument/hover", "textDocument/definition"):
            ensure(_result(server, method, _params(0, 23)) is None,
                   f"failed complete check leaked partial facts for {source!r}")
        ensure(_references(server, 0, 23, True) == [], "failed check retained references")
        ensure(_result(server, "textDocument/documentSymbol", {"textDocument": {"uri": _URI}}) == [],
               "failed check retained declaration symbols")


def _query_lifecycle_and_malformed_parameters() -> None:
    server = Server()
    _error(server, "textDocument/hover", _params(1, 11), -32002)
    _result(server, "initialize", {"capabilities": {}})
    ensure("error" in _reply(server, "textDocument/hover", _params(1, 11)),
           "query before initialized notification was accepted")
    server.handle(_notice("initialized"))
    _error(server, "textDocument/documentSymbol", {"textDocument": {"uri": _URI}}, -32602)
    _open(server, _SCOPE)
    invalid: list[object] = [None, [], {}, {"textDocument": {}}, _params(-1, 0),
                             _params(1, -1), _params(True, 0), _params(1, False),
                             {"textDocument": {"uri": 7}, "position": {"line": 0, "character": 0}},
                             {"textDocument": {"uri": _URI}, "position": {"line": 1}},
                             _params(0, 0, "untitled:never-opened")]
    for params in invalid:
        _error(server, "textDocument/hover", params, -32602)
    for context in (None, {}, {"includeDeclaration": 0}, {"includeDeclaration": "true"}):
        params = _params(1, 11)
        params["context"] = context
        _error(server, "textDocument/references", params, -32602)
    with patch.object(Path, "read_bytes", side_effect=AssertionError("URI caused disk access")), \
            patch.object(Path, "read_text", side_effect=AssertionError("URI caused disk access")):
        ensure(_result(server, "textDocument/definition", _params(8, 11)) == _location(1, 11, 7),
               "query did not resolve from the open overlay")
    server.handle(_notice("textDocument/didClose", {"textDocument": {"uri": _URI}}))
    _error(server, "textDocument/hover", _params(1, 11), -32602)
    _result(server, "shutdown")
    ensure("error" in _reply(server, "textDocument/hover", _params(1, 11)),
           "query after shutdown was accepted")


def _edits_invalidation_and_desynchronization() -> None:
    server = _server()
    _result(server, "textDocument/definition", _params(8, 11))
    server.handle(_notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": 2}, "contentChanges": [{
            "range": {"start": {"line": 0, "character": 0},
                      "end": {"line": 0, "character": 0}}, "text": "// moved 😀\r\n"}]}))
    ensure(_result(server, "textDocument/definition", _params(9, 11)) == _location(2, 11, 7),
           "incremental edit reused declaration coordinates from the previous snapshot")
    ensure(_result(server, "textDocument/hover", _params(1, 11)) is None,
           "incremental edit retained a symbol at its old location")
    for method in ("workspace/didChangeConfiguration", "workspace/didChangeWatchedFiles"):
        server.handle(_notice(method, {"settings": {}, "changes": []}))
        ensure(_result(server, "textDocument/definition", _params(9, 11)) == _location(2, 11, 7),
               "invalidation exposed a superseded or unavailable result")
    with redirect_stderr(StringIO()):
        server.handle(_notice("textDocument/didChange", {
            "textDocument": {"uri": _URI, "version": 3},
            "contentChanges": [{"range": {}, "text": "refused"}]}))
    for method in ("textDocument/hover", "textDocument/definition", "textDocument/references",
                   "textDocument/documentSymbol"):
        params = _params(9, 11)
        params["context"] = {"includeDeclaration": True}
        _error(server, method, params, -32801)
    server.handle(_notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": 4},
        "contentChanges": [{"text": "module Replacement; public bool Fresh() { return true; }"}]}))
    symbols = _array(_result(server, "textDocument/documentSymbol", {"textDocument": {"uri": _URI}}))
    ensure(len(symbols) == 1 and _object(symbols[0]).get("name") == "Fresh",
           "full resynchronization retained removed declarations")


def _inspection_and_reply_bounds() -> None:
    declarations = "module Many; " + " ".join(
        f"public Nat F{index}() {{ return 0; }}" for index in range(1025))
    occurrences = "module Uses; " + " ".join(
        f"public Nat F{index}(Nat x) {{ return {' + '.join(['x'] * 60)}; }}" for index in range(70))
    for text in (declarations, occurrences):
        server = _server(text)
        _error(server, "textDocument/documentSymbol", {"textDocument": {"uri": _URI}}, -32803)
        # Ordinary producer diagnostics remain independent of inspection limits.
        saved = server.handle(_notice("textDocument/didSave", {"textDocument": {"uri": _URI}}))
        ensure(_object(saved[0].get("params")).get("diagnostics") == [],
               "inspection bound changed ordinary source checking")
    long_uri = "untitled:" + "u" * 3000
    source = "module Reply; public Nat Base() { return 0; } " + " ".join(
        f"public Nat F{index}() {{ return {' + '.join(['Base()'] * 50)}; }}" for index in range(11))
    server = _server(source, long_uri)
    params = _params(0, 25, long_uri)
    params["context"] = {"includeDeclaration": True}
    _error(server, "textDocument/references", params, -32803)
    ensure(_result(server, "textDocument/definition", _params(0, 25, long_uri))
           == _location(0, 25, 4, long_uri),
           "oversized complete reference reply terminated or poisoned the session")


def _worker_failure_is_a_request_failure() -> None:
    server = _server()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 5)):
        _error(server, "textDocument/hover", _params(1, 11), -32803)
    for output in (b"not JSON", b'{"status":"ok","symbols":[],"occurrences":[{"symbol":8}]}',
                   b"x" * 1_048_577):
        completed = subprocess.CompletedProcess(["worker"], 0, stdout=output, stderr=b"")
        with patch("subprocess.run", return_value=completed):
            _error(server, "textDocument/hover", _params(1, 11), -32803)
    ensure(_result(server, "textDocument/definition", _params(8, 11)) == _location(1, 11, 7),
           "failed worker prevented a later independent inspection")


def _wire(message: dict[str, object]) -> bytes:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _process_wire_services_and_unsaved_edit() -> None:
    source = ("// 😀\r\nmodule Wire;\r\npublic Nat Echo(Nat arg) { return arg; }\r\n"
              "public Nat Use() { return Echo(1); }")
    position = _params(3, 26)
    references = {**position, "context": {"includeDeclaration": True}}
    messages = [_request("initialize", {"capabilities": {}}, 1), _notice("initialized"),
                _notice("textDocument/didOpen", {"textDocument": {
                    "uri": _URI, "languageId": "vela", "version": 1, "text": source}}),
                _request("textDocument/hover", position, 2),
                _request("textDocument/definition", position, 3),
                _request("textDocument/references", references, 4),
                _request("textDocument/documentSymbol", {"textDocument": {"uri": _URI}}, 5),
                _notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 2},
                    "contentChanges": [{"range": {"start": {"line": 0, "character": 0},
                                                  "end": {"line": 0, "character": 0}},
                                        "text": "// moved\n"}]}),
                _request("textDocument/definition", _params(4, 26), 6),
                _request("textDocument/hover", _params(2, 11), 7),
                _request("shutdown", identity=8), _notice("exit")]
    tools = str(Path(__file__).resolve().parents[1])
    script = (f"import sys; sys.path.insert(0, {tools!r}); "
              "from vos.cli.vela_lsp import main; raise SystemExit(main())")
    completed = subprocess.run([sys.executable, "-I", "-c", script],
                               input=b"".join(_wire(message) for message in messages),
                               capture_output=True, timeout=30, check=False)
    ensure(completed.returncode == 0 and completed.stderr == b"",
           f"real service process failed: {completed.stderr!r}")
    stream = BytesIO(completed.stdout)
    replies: dict[int, dict[str, object]] = {}
    versions: list[object] = []
    while header := stream.readline():
        ensure(header.startswith(b"Content-Length: ") and header.endswith(b"\r\n"),
               "service process stdout contains logs or malformed framing")
        length = int(header[len(b"Content-Length: "):].strip())
        ensure(stream.readline() == b"\r\n", "service process omitted frame separator")
        body = stream.read(length)
        ensure(len(body) == length, "service process reply was truncated")
        reply = _object(json.loads(body))
        if "id" in reply:
            identity = reply["id"]
            ensure(type(identity) is int and identity not in replies, "wire response identity repeated")
            replies[cast("int", identity)] = reply
        else:
            ensure(reply.get("method") == "textDocument/publishDiagnostics", "unexpected wire notification")
            publication = _object(reply.get("params"))
            ensure(publication.get("diagnostics") == [], "wire fixture unexpectedly failed pure checking")
            versions.append(publication.get("version"))
    ensure(set(replies) == set(range(1, 9)) and versions == [1, 2],
           "wire service session lost requests or versioned overlay diagnostics")
    hover = _object(replies[2].get("result"))
    contents = _object(hover.get("contents"))
    ensure(contents.get("kind") == "plaintext" and "public Nat Echo(Nat arg)" in str(contents.get("value"))
           and "unqualified" in str(contents.get("value")).lower()
           and hover.get("range") == _span(3, 26, 4), "wire hover facts/range disagree with source")
    ensure(replies[3].get("result") == _location(2, 11, 4), "wire definition is wrong")
    ensure(replies[4].get("result") == [_location(2, 11, 4), _location(3, 26, 4)],
           "wire references did not honor declaration inclusion")
    symbols = [_object(value) for value in _array(replies[5].get("result"))]
    ensure([symbol.get("name") for symbol in symbols] == ["Echo", "arg", "Use"]
           and [symbol.get("location") for symbol in symbols]
           == [_location(2, 11, 4), _location(2, 20, 3), _location(3, 11, 3)],
           "wire flat symbol projection disagrees with independently expected declarations")
    ensure(replies[6].get("result") == _location(3, 11, 4) and replies[7].get("result") is None,
           "wire incremental update reused old declaration facts")
    ensure(replies[8].get("result") is None and "error" not in replies[8], "wire shutdown failed")


def cases() -> list[Case]:
    return [Case("resolved-identities-scopes-and-symbols", _resolved_namespaces_and_scopes),
            Case("unicode-newlines-and-half-open-selection", _unicode_newlines_and_half_open_ranges),
            Case("failed-complete-checks-have-no-facts", _failed_complete_checks_have_no_facts),
            Case("query-lifecycle-and-malformed-parameters", _query_lifecycle_and_malformed_parameters),
            Case("edits-invalidation-and-desynchronization", _edits_invalidation_and_desynchronization),
            Case("inspection-and-complete-reply-bounds", _inspection_and_reply_bounds),
            Case("worker-failure-is-a-request-failure", _worker_failure_is_a_request_failure),
            Case("real-process-services-and-unsaved-edit", _process_wire_services_and_unsaved_edit)]
