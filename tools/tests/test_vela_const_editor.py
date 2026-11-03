# SPDX-License-Identifier: Apache-2.0
"""Independent editor checks for evaluated constants and required-static failures."""

import copy
from typing import cast

from tests.harness import Case, ensure
from vos.vela import inspect_source
from vos.vela_ast import MAX_LITERAL_DIGITS
from vos.vela_lsp import Server
from vos.vela_lsp_services import InspectionError, project
from vos.vela_source import SourceSnapshot

INDEPENDENT_CASES = True

_URI = "untitled:constant-editor.vela"
_TEXT = ("// 😀\r\nmodule Constants;\rpublic const Nat Limit = 2 + 3;\n"
         "public Nat Read() {\r\n  const bool Ready = true;\n"
         "  let selected = Limit;\r"
         "  if (Ready) { return selected; } else { return Limit; }\n}")


def _object(value: object) -> dict[str, object]:
    ensure(isinstance(value, dict), f"expected an object: {value!r}")
    return cast("dict[str, object]", value)


def _notice(method: str, params: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def _query(server: Server, method: str, params: object) -> object:
    replies = server.handle({"jsonrpc": "2.0", "id": 3, "method": method, "params": params})
    ensure(len(replies) == 1 and replies[0].get("id") == 3
           and "result" in replies[0] and "error" not in replies[0],
           f"constant editor request failed: {replies!r}")
    return replies[0]["result"]


def _params(line: int, character: int) -> dict[str, object]:
    return {"textDocument": {"uri": _URI},
            "position": {"line": line, "character": character}}


def _range(line: int, character: int, length: int) -> dict[str, object]:
    return {"start": {"line": line, "character": character},
            "end": {"line": line, "character": character + length}}


def _publication(replies: list[dict[str, object]], version: int) -> list[object]:
    ensure(len(replies) == 1 and replies[0].get("method") == "textDocument/publishDiagnostics",
           f"constant edit omitted its diagnostic snapshot: {replies!r}")
    params = _object(replies[0].get("params"))
    ensure(params.get("uri") == _URI and params.get("version") == version,
           "constant diagnostics are detached from the current document")
    values = params.get("diagnostics")
    ensure(isinstance(values, list), "malformed constant diagnostics")
    return cast("list[object]", values)


def _server() -> Server:
    server = Server()
    _query(server, "initialize", {})
    server.handle(_notice("initialized", {}))
    replies = server.handle(_notice("textDocument/didOpen", {"textDocument": {
        "uri": _URI, "languageId": "vela", "version": 1, "text": _TEXT}}))
    ensure(_publication(replies, 1) == [], "valid evaluated constants were refused")
    return server


def _replace(server: Server, text: str, version: int) -> list[object]:
    return _publication(server.handle(_notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": version},
        "contentChanges": [{"text": text}]})), version)


def _constant_navigation_and_display() -> None:
    server = _server()
    expected = {"uri": _URI, "range": _range(2, 17, 5)}
    ensure(_query(server, "textDocument/definition", _params(5, 17)) == expected,
           "global constant definition lost its exact mixed-newline location")
    ensure(_query(server, "textDocument/definition", _params(6, 6)) == {
        "uri": _URI, "range": _range(4, 13, 5)},
        "local constant definition lost its distinct identity")
    hover = _object(_query(server, "textDocument/hover", _params(5, 17)))
    ensure("const Nat Limit = 5" in str(_object(hover.get("contents")).get("value")),
           "constant hover did not display the compiler's evaluated typed value")
    symbols = cast("list[dict[str, object]]", _query(
        server, "textDocument/documentSymbol", {"textDocument": {"uri": _URI}}))
    constants = [symbol for symbol in symbols if symbol.get("kind") == 14]
    ensure([(item.get("name"), item.get("location")) for item in constants] == [
        ("Limit", expected), ("Ready", {"uri": _URI, "range": _range(4, 13, 5)})],
        "constant declarations were exposed as functions or mutable variables")
    hints = _query(server, "textDocument/inlayHint", {
        "textDocument": {"uri": _URI}, "range": {
            "start": {"line": 0, "character": 0}, "end": {"line": 7, "character": 1}}})
    ensure(hints == [{"position": {"line": 5, "character": 14}, "label": ": Nat", "kind": 1}],
           "explicitly typed constants received inferred-local hints")


def _static_failures_invalidate_and_recover() -> None:
    server = _server()
    failures = (
        "module Runtime; public Nat Read(Nat input) { const Nat Copy = input; return Copy; }",
        "module Runtime; public Nat Ignore(Nat value) => 0; "
        "public Nat Read(Nat input) { const Nat Copy = Ignore(value: input); return Copy; }",
        "module Runtime; public Nat Read() { let ordinary = 2; "
        "const Nat Copy = ordinary; return Copy; }",
        "module Runtime; public const Nat Limit = 5; "
        "public Nat Read(Nat Limit) { const Nat Copy = Limit; return Copy; }",
    )
    for version, text in enumerate(failures, 2):
        diagnostics = _replace(server, text, version)
        ensure(len(diagnostics) == 1, "runtime initializer dependency did not produce a refusal")
        message = str(_object(diagnostics[0]).get("message")).lower()
        ensure("const" in message and ("static" in message or "runtime" in message),
               f"phase refusal does not explain required-static evaluation: {message!r}")
        ensure(_query(server, "textDocument/documentSymbol", {"textDocument": {"uri": _URI}}) == [],
               "failed static evaluation leaked earlier valid declaration facts")
    ensure(_replace(server, _TEXT.replace("2 + 3", "8"), 6) == [],
           "valid constant edit did not restore editor facts")
    hover = _object(_query(server, "textDocument/hover", _params(5, 17)))
    ensure("const Nat Limit = 8" in str(_object(hover.get("contents")).get("value")),
           "edited initializer reused the old constant's evaluated value")


def _constant_fact_shape_is_bounded() -> None:
    snapshot = SourceSnapshot(_URI, 1, _TEXT, 1)
    raw = inspect_source(_TEXT.encode())
    symbols = cast("list[dict[str, object]]", raw["symbols"])
    index = next(index for index, symbol in enumerate(symbols) if symbol["name"] == "Limit")
    for detail in ("const Nat Limit = -1", "const Nat Limit = 00", "const Nat Limit = true",
                   "const bool Limit = 5", "const Nat Limit = " + "9" * (MAX_LITERAL_DIGITS + 1),
                   "const Nat Limit = ５"):
        changed = copy.deepcopy(raw)
        cast("list[dict[str, object]]", changed["symbols"])[index]["detail"] = detail
        try:
            project(snapshot, changed, "textDocument/hover", (5, 17))
        except InspectionError:
            continue
        raise AssertionError(f"constant projection accepted invalid compiler detail {detail!r}")


def cases() -> list[Case]:
    return [Case("constant-definitions-symbols-hover-and-hints", _constant_navigation_and_display),
            Case("static-dependency-diagnostics-invalidate-and-recover", _static_failures_invalidate_and_recover),
            Case("constant-fact-display-boundary", _constant_fact_shape_is_bounded)]
