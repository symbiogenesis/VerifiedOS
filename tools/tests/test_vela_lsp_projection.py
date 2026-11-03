# SPDX-License-Identifier: Apache-2.0
"""Independent controls for the pure-fact worker boundary and LSP projection."""

import copy
import json
import subprocess
from collections.abc import Callable
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.protocol_json import MAX_BODY_BYTES, encode_message
from vos.vela_lsp import Server
from vos.vela_lsp_services import InspectionError, inspect_document, project
from vos.vela_source import SourceSnapshot

_URI = "untitled:projection.vela"
_TEXT = "module Demo;\r\n// 😀\rpublic Nat Id(Nat value) { return value; }\n"


def _facts() -> dict[str, object]:
    return {"status": "ok", "symbols": [
        {"name": "Id", "kind": "function", "detail": "public Nat Id(Nat value)", "line": 3, "column": 12},
        {"name": "value", "kind": "parameter", "detail": "value: Nat", "line": 3, "column": 19}],
        "occurrences": [
            {"symbol": 0, "line": 3, "column": 12, "declaration": True},
            {"symbol": 1, "line": 3, "column": 19, "declaration": True},
            {"symbol": 1, "line": 3, "column": 35, "declaration": False}]}


def _refuses(operation: Callable[[], object], message: str) -> None:
    try:
        operation()
    except InspectionError:
        return
    raise AssertionError(message)


def _request(method: str, params: object = None, identity: int = 1) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identity, "method": method,
            "params": {} if params is None else params}


def _notice(method: str, params: object = None) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": {} if params is None else params}


def _opened(inspector: Callable[[bytes], dict[str, object]],
            text: str = _TEXT, uri: str = _URI) -> Server:
    server = Server(checker=lambda _: None, inspector=inspector)
    server.handle(_request("initialize"))
    server.handle(_notice("initialized"))
    server.handle(_notice("textDocument/didOpen", {"textDocument": {
        "uri": uri, "languageId": "vela", "version": 1, "text": text}}))
    return server


def _params(uri: str = _URI) -> dict[str, object]:
    return {"textDocument": {"uri": uri}, "position": {"line": 2, "character": 34}}


def _error_code(reply: list[dict[str, object]]) -> object:
    error = reply[0].get("error")
    ensure(isinstance(error, dict), f"expected an error response: {reply!r}")
    return cast("dict[str, object]", error).get("code")


def _projection() -> None:
    snapshot = SourceSnapshot(_URI, 1, _TEXT, 1)
    hover = project(snapshot, _facts(), "textDocument/hover", (2, 34))
    ensure(hover == {"contents": {"kind": "plaintext", "value": "value: Nat\nVela pure prototype (unqualified)"},
                     "range": {"start": {"line": 2, "character": 34}, "end": {"line": 2, "character": 39}}},
           f"hover changed resolved type or coordinates: {hover!r}")
    location = {"uri": _URI, "range": {"start": {"line": 2, "character": 18},
                                       "end": {"line": 2, "character": 23}}}
    ensure(project(snapshot, _facts(), "textDocument/definition", (2, 36)) == location,
           "definition did not select exact parameter name")
    references = project(snapshot, _facts(), "textDocument/references", (2, 19), True)
    ensure(references == [location, {"uri": _URI, "range": {
        "start": {"line": 2, "character": 34}, "end": {"line": 2, "character": 39}}}],
        "references did not honor the compiler identity and declaration flag")
    ensure(project(snapshot, _facts(), "textDocument/references", (2, 19)) == cast("list[object]", references)[1:],
           "references included an unrequested declaration")
    for point in ((2, 39), (2, 33), (1, 3), (0, 7)):
        ensure(project(snapshot, _facts(), "textDocument/hover", point) is None,
               f"nonidentifier point selected a symbol: {point!r}")
    symbols = project(snapshot, _facts(), "textDocument/documentSymbol", None)
    ensure(isinstance(symbols, list) and len(symbols) == 2, "flat symbols lost a declaration")
    ensure(cast("list[dict[str, object]]", symbols)[1] == {"name": "value", "kind": 13, "location": location},
           "flat parameter symbol changed its exact name location")
    refused = {"status": "unavailable", "reason": "type"}
    ensure(project(snapshot, refused, "textDocument/hover", (2, 34)) is None
           and project(snapshot, refused, "textDocument/references", (2, 34)) == [],
           "failed complete source exposed facts")


def _producer_refusals() -> None:
    snapshot = SourceSnapshot(_URI, 1, _TEXT, 1)
    variants: list[dict[str, object]] = []
    missing = _facts()
    missing["occurrences"] = cast("list[object]", missing["occurrences"])[1:]
    variants.append(missing)
    for field, value in (("symbol", 20), ("symbol", True), ("declaration", 1),
                         ("line", 4), ("column", 36)):
        changed = _facts()
        cast("list[dict[str, object]]", changed["occurrences"])[2][field] = value
        variants.append(changed)
    duplicate = _facts()
    cast("list[object]", duplicate["occurrences"]).append(copy.deepcopy(
        cast("list[object]", duplicate["occurrences"])[2]))
    variants.append(duplicate)
    prefix = _facts()
    cast("list[dict[str, object]]", prefix["symbols"])[1]["name"] = "valu"
    variants.append(prefix)
    for raw in (*variants, {"status": "unavailable", "reason": "inspection-limit"},
                {"status": "ok", "symbols": [], "occurrences": [], "extra": True},
                {"status": "unavailable", "reason": []}):
        _refuses(lambda raw=raw: project(snapshot, raw, "textDocument/hover", (2, 34)),
                 f"malformed or incomplete producer result accepted: {raw!r}")
    bounded = _facts()
    bounded["symbols"] = cast("list[object]", bounded["symbols"]) * 513
    _refuses(lambda: project(snapshot, bounded, "textDocument/documentSymbol", None),
             "over-budget declaration set accepted")
    bounded = _facts()
    bounded["occurrences"] = cast("list[object]", bounded["occurrences"]) * 1366
    _refuses(lambda: project(snapshot, bounded, "textDocument/documentSymbol", None),
             "over-budget occurrence set accepted")


def _worker_boundary() -> None:
    done = subprocess.CompletedProcess(["fixed"], 0, b'{"status":"unavailable","reason":"syntax"}', b"")
    with patch("vos.vela_lsp_services.subprocess.run", return_value=done) as run:
        ensure(inspect_document(b"source") == {"status": "unavailable", "reason": "syntax"},
               "worker JSON was not consumed")
        command = run.call_args.args[0]
        ensure(command[1:3] == ["-I", "-c"] and command[-1] == "--inspect"
               and run.call_args.kwargs["input"] == b"source"
               and run.call_args.kwargs["timeout"] == 5,
               "inspection did not use isolated fixed producer and timeout")
    for done in (subprocess.CompletedProcess(["fixed"], 1, b"", b""),
                 subprocess.CompletedProcess(["fixed"], 0, b"x" * (MAX_BODY_BYTES + 1), b""),
                 subprocess.CompletedProcess(["fixed"], 0, b'{"status":"ok","status":"ok"}', b"")):
        with patch("vos.vela_lsp_services.subprocess.run", return_value=done):
            _refuses(lambda: inspect_document(b"source"), "bad worker output accepted")
    with patch("vos.vela_lsp_services.subprocess.run", side_effect=subprocess.TimeoutExpired("fixed", 5)):
        _refuses(lambda: inspect_document(b"source"), "worker timeout accepted")


def _request_refusals() -> None:
    server = _opened(lambda _: _facts())
    for params in ({}, {"textDocument": {"uri": "untitled:unknown"}},
                   {"textDocument": {"uri": _URI}, "position": {"line": True, "character": 0}},
                   {"textDocument": {"uri": _URI}, "position": {"line": -1, "character": 0}},
                   {"textDocument": {"uri": _URI}, "position": {"line": 1, "character": 4}}):
        # The supplementary character in '// 😀' occupies UTF-16 columns 3..5.
        ensure(_error_code(server.handle(_request("textDocument/hover", params))) == -32602,
               "invalid query position or unopened document accepted")
    params = _params()
    params["context"] = {"includeDeclaration": 1}
    ensure(_error_code(server.handle(_request("textDocument/references", params))) == -32602,
           "nonboolean declaration flag accepted")
    server.desynchronized.add(_URI)
    ensure(_error_code(server.handle(_request("textDocument/hover", _params()))) == -32801,
           "desynchronized overlay exposed facts")
    before_ready = Server(checker=lambda _: None, inspector=lambda _: _facts())
    before_ready.handle(_request("initialize"))
    ensure(_error_code(before_ready.handle(_request("textDocument/hover", _params()))) == -32002,
           "query before initialized notification accepted")


def _oversized_reply_recovery() -> None:
    uri = "untitled:" + "x" * 4080
    text = "module Demo;\n" + "".join(f"public Nat F{index}() {{ return 0; }}\n" for index in range(300))
    raw: dict[str, object] = {"status": "ok", "symbols": [
        {"name": f"F{index}", "kind": "function", "detail": f"public Nat F{index}()",
         "line": index + 2, "column": 12} for index in range(300)],
        "occurrences": [{"symbol": index, "line": index + 2, "column": 12, "declaration": True}
                        for index in range(300)]}
    server = _opened(lambda _: raw, text, uri)
    oversized = server.handle(_request("textDocument/documentSymbol", {"textDocument": {"uri": uri}}, 90))
    ensure(oversized[0]["id"] == 90 and _error_code(oversized) == -32803,
           "oversized result was truncated or lost request correlation")
    params = {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 11}}
    recovered = server.handle(_request("textDocument/hover", params, 91))
    ensure(recovered[0]["id"] == 91 and "result" in recovered[0] and server.exit_code is None,
           "oversized query terminated the session or poisoned the next result")


def _frame_sized_request_id_recovery() -> None:
    server = _opened(lambda _: _facts(), uri="u")
    request = _request("textDocument/documentSymbol", {"textDocument": {"uri": "u"}})
    request["id"] = ""
    envelope = len(json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode())
    request["id"] = "x" * (MAX_BODY_BYTES - envelope)
    ensure(len(encode_message(request).split(b"\r\n\r\n", 1)[1]) == MAX_BODY_BYTES,
           "large-ID control did not fill the valid incoming frame")
    refused = server.handle(request)
    ensure(_error_code(refused) == -32803 and refused[0]["id"] == request["id"],
           "oversized large-ID reply lost its correlated refusal")
    encode_message(refused[0])
    recovered = server.handle(_request("textDocument/hover", _params("u"), 92))
    ensure(recovered[0]["id"] == 92 and "result" in recovered[0] and server.exit_code is None,
           "large-ID reply refusal poisoned the next query")


def cases() -> list[Case]:
    return [Case("resolved-fact-projection-and-source-units", _projection),
            Case("producer-shape-source-links-and-bounds", _producer_refusals),
            Case("isolated-inspection-worker-boundary", _worker_boundary),
            Case("query-parameter-lifecycle-and-overlay-refusals", _request_refusals),
            Case("oversized-result-refusal-and-session-recovery", _oversized_reply_recovery),
            Case("frame-sized-request-id-recovery", _frame_sized_request_id_recovery)]
