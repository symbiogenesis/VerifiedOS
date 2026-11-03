# SPDX-License-Identifier: Apache-2.0
"""Independent editor controls for canonical Vela calls and binding diagnostics."""

from typing import cast

from tests.harness import Case, ensure
from vos.vela import inspect_source
from vos.vela_lsp import Server

INDEPENDENT_CASES = True

_URI = "untitled:canonical-authoring.vela"
_TEXT = ("// 😀\r\nmodule Labels;\r\n"
         "public Nat Echo(Nat value) => value;\r\n"
         "public Nat Use(Nat value) => Echo(value: value);")


def _object(value: object) -> dict[str, object]:
    ensure(isinstance(value, dict), f"expected an object: {value!r}")
    return cast("dict[str, object]", value)


def _notice(method: str, params: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def _query(server: Server, method: str, params: object) -> object:
    replies = server.handle({"jsonrpc": "2.0", "id": 7, "method": method, "params": params})
    ensure(len(replies) == 1 and replies[0].get("id") == 7,
           f"editor query lost its identity: {replies!r}")
    ensure("result" in replies[0] and "error" not in replies[0],
           f"editor query failed: {replies!r}")
    return replies[0]["result"]


def _position(line: int, character: int) -> dict[str, object]:
    return {"textDocument": {"uri": _URI},
            "position": {"line": line, "character": character}}


def _location(line: int, character: int) -> dict[str, object]:
    return {"uri": _URI, "range": {
        "start": {"line": line, "character": character},
        "end": {"line": line, "character": character + 5}}}


def _diagnostics(replies: list[dict[str, object]], version: int) -> list[object]:
    ensure(len(replies) == 1 and replies[0].get("method") == "textDocument/publishDiagnostics",
           f"editor did not publish a complete diagnostic update: {replies!r}")
    params = _object(replies[0].get("params"))
    ensure(params.get("uri") == _URI and params.get("version") == version,
           "diagnostic update is detached from its current document")
    values = params.get("diagnostics")
    ensure(isinstance(values, list), f"diagnostic update is malformed: {values!r}")
    return cast("list[object]", values)


def _server(text: str) -> tuple[Server, list[object]]:
    server = Server()
    _query(server, "initialize", {})
    server.handle(_notice("initialized", {}))
    replies = server.handle(_notice("textDocument/didOpen", {"textDocument": {
        "uri": _URI, "languageId": "vela", "version": 1, "text": text}}))
    return server, _diagnostics(replies, 1)


def _replace(server: Server, text: str, version: int) -> list[object]:
    replies = server.handle(_notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": version},
        "contentChanges": [{"text": text}]}))
    return _diagnostics(replies, version)


def _labels_are_parameter_references() -> None:
    raw = inspect_source(_TEXT.encode())
    occurrences = cast("list[dict[str, object]]", raw["occurrences"])
    sites = {(item["line"], item["column"]): item["symbol"] for item in occurrences}
    ensure(sites[(4, 35)] == sites[(3, 21)] == sites[(3, 31)],
           "argument label does not resolve to the callee parameter")
    ensure(sites[(4, 42)] == sites[(4, 20)] != sites[(4, 35)],
           "argument label was counted as a use of the same-spelled caller value")
    server, diagnostics = _server(_TEXT)
    ensure(diagnostics == [], f"canonical named call was refused: {diagnostics!r}")
    ensure(_query(server, "textDocument/definition", _position(3, 34)) == _location(2, 20),
           "label definition navigated to the caller's same-spelled binding")
    ensure(_query(server, "textDocument/definition", _position(3, 41)) == _location(3, 19),
           "argument value definition navigated to the callee's label")
    params = _position(3, 34)
    params["context"] = {"includeDeclaration": True}
    ensure(_query(server, "textDocument/references", params) == [
        _location(2, 20), _location(2, 30), _location(3, 34)],
        "parameter references confused labels with runtime value occurrences")
    hover = _object(_query(server, "textDocument/hover", _position(3, 34)))
    ensure("value: Nat" in str(_object(hover.get("contents")).get("value")),
           "argument label hover lost the resolved parameter's type")


def _label_edits_invalidate_editor_facts() -> None:
    server, diagnostics = _server(_TEXT)
    ensure(diagnostics == [], "named-call fixture must start valid")
    invalid = _TEXT.replace("Echo(value: value)", "Echo(wrong: value)")
    diagnostics = _replace(server, invalid, 2)
    ensure(len(diagnostics) == 1, "unknown label did not receive a diagnostic")
    ensure(_query(server, "textDocument/definition", _position(3, 34)) is None,
           "unknown label reused a previous snapshot's parameter identity")
    ensure(_query(server, "textDocument/hover", _position(3, 41)) is None,
           "failed complete checking retained partial call facts")
    restored = "// shifted\n" + _TEXT
    ensure(_replace(server, restored, 3) == [], "valid edited named call did not recover")
    ensure(_query(server, "textDocument/definition", _position(4, 34)) == _location(3, 20),
           "recovery reused stale source coordinates")


def _mutability_diagnostics_and_producer_boundary() -> None:
    immutable = ("// 😀\r\nmodule Bindings;\r\npublic Nat Read(Nat input) {\r\n"
                 "  let item = input;\r\n  item = 2;\r\n  return item;\r\n}")
    server, diagnostics = _server(immutable)
    ensure(len(diagnostics) == 1, "immutable reassignment lacked a diagnostic")
    diagnostic = _object(diagnostics[0])
    message = str(diagnostic.get("message")).lower()
    ensure(all(word in message for word in ("immutable", "item", "var", "pure")),
           f"reassignment diagnostic omitted binding, syntax or producer boundary: {message!r}")
    ensure(_object(diagnostic.get("range")).get("start") == {"line": 4, "character": 2},
           "reassignment diagnostic moved under UTF-8 or CRLF")
    borrowed = "module Loans; public Nat Read(ref Nat item) => item;"
    diagnostics = _replace(server, borrowed, 2)
    ensure(len(diagnostics) == 1, "unsupported loan syntax lacked a diagnostic")
    message = str(_object(diagnostics[0]).get("message")).lower()
    ensure("pure" in message and "ref" in message and "immutable" not in message,
           "unsupported exclusive loan was misreported as immutable rebinding")
    valid = "module Bindings; public Nat Read(Nat input) { let item = input; return item; }"
    ensure(_replace(server, valid, 3) == [], "valid immutable binding failed to clear diagnostics")


def cases() -> list[Case]:
    return [Case("named-label-and-value-identities-through-editor", _labels_are_parameter_references),
            Case("named-label-edit-invalidation-and-recovery", _label_edits_invalidate_editor_facts),
            Case("immutable-binding-diagnostic-and-loan-boundary", _mutability_diagnostics_and_producer_boundary)]
