# SPDX-License-Identifier: Apache-2.0
"""Independent formatting, token, overlay and complete-reply wire controls."""

import hashlib
import json
import subprocess
import sys
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message, read_frame
from vos.vela import VelaError, inspect_source, translate
from vos.vela_authoring import format_source
from vos.vela_lsp import Server, serve
from vos.vela_lsp_format import format_document, formatting_edits
from vos.vela_lsp_services import InspectionError
from vos.vela_source import SourceSnapshot

INDEPENDENT_CASES = True
_URI = "untitled:editor.vela"
_TEXT = "module M;\npublic Nat Id(Nat value)=>value;"
_FORMATTED = "module M;\n\npublic Nat Id(Nat value) => value;\n"
_TOKENS = {"data": [1, 11, 2, 0, 1, 0, 7, 5, 1, 3, 0, 8, 5, 1, 2]}


def _object(value: object) -> dict[str, object]:
    ensure(isinstance(value, dict), f"expected an object: {value!r}")
    return cast("dict[str, object]", value)


def _request(method: str, params: object = None, identity: object = 1) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identity, "method": method,
            "params": {} if params is None else params}


def _notice(method: str, params: object = None) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": {} if params is None else params}


def _params(formatting: bool = False) -> dict[str, object]:
    result: dict[str, object] = {"textDocument": {"uri": _URI}}
    if formatting:
        result["options"] = {"tabSize": 2, "insertSpaces": False}
    return result


def _inspect(source: bytes) -> dict[str, object]:
    try:
        return inspect_source(source)
    except VelaError as error:
        return {"status": "unavailable", "reason": error.kind}


def _format(source: bytes) -> dict[str, object]:
    result: dict[str, object] = {"source_sha256": hashlib.sha256(source).hexdigest()}
    try:
        result.update(status="ok", formatted=format_source(source).decode())
    except VelaError as error:
        result.update(status="unavailable", reason=error.kind)
    return result


def _server(text: str = _TEXT) -> Server:
    server = Server(checker=lambda _: None, inspector=_inspect, formatter=_format)
    reply = server.handle(_request("initialize"))[0]
    capabilities = _object(_object(reply.get("result")).get("capabilities"))
    ensure(capabilities.get("documentFormattingProvider") is True,
           "document formatting capability is missing")
    ensure(capabilities.get("semanticTokensProvider") == {
        "legend": {"tokenTypes": ["function", "parameter", "variable"],
                   "tokenModifiers": ["declaration", "readonly"]}, "full": True, "range": False},
        "semantic token legend or supported operations differ from the contract")
    server.handle(_notice("initialized"))
    server.handle(_notice("textDocument/didOpen", {"textDocument": {
        "uri": _URI, "languageId": "vela", "version": 1, "text": text}}))
    return server


def _reply(server: Server, method: str, params: object = None) -> dict[str, object]:
    replies = server.handle(_request(method, params))
    ensure(len(replies) == 1 and replies[0].get("id") == 1, "editor request lost correlation")
    return replies[0]


def _result(server: Server, method: str, params: object = None) -> object:
    reply = _reply(server, method, params)
    ensure("result" in reply, f"editor request failed: {reply!r}")
    return reply["result"]


def _error(server: Server, method: str, params: object, code: int) -> None:
    ensure(_object(_reply(server, method, params).get("error")).get("code") == code,
           f"editor request failed to refuse with {code}")


def _edits(end: tuple[int, int], formatted: str = _FORMATTED) -> list[dict[str, object]]:
    return [{"range": {"start": {"line": 0, "character": 0},
                       "end": {"line": end[0], "character": end[1]}}, "newText": formatted}]


def _formatting_exact_and_read_only() -> None:
    for text, end in ((_TEXT, (1, 32)), (_TEXT + "\r\n", (2, 0)),
                      (_TEXT.replace("\n", "\r"), (1, 32))):
        server = _server(text)
        original = server.documents[_URI]
        ensure(_result(server, "textDocument/formatting", _params(True)) == _edits(end),
               "whole-document formatting edit has wrong canonical bytes or UTF-16 bounds")
        ensure(server.documents[_URI] is original, "formatting mutated the current overlay")
        ensure(_result(server, "textDocument/semanticTokens/full", _params()) == _TOKENS,
               "formatting changed semantic sites before the client applied an edit")
    server = _server(_FORMATTED)
    ensure(_result(server, "textDocument/formatting", _params(True)) == [],
           "canonical source received a redundant edit")
    text = "// 😀\r\nmodule M;\rpublic Nat F()=>1; // 😀"
    expected = "// 😀\nmodule M;\n\npublic Nat F() => 1; // 😀\n"
    ensure(_result(_server(text), "textDocument/formatting", _params(True)) == _edits((2, 24), expected),
           "formatting lost comment bytes, mixed newline positions or supplementary UTF-16 units")


def _parameters_lifecycle_and_recovery() -> None:
    methods = ("textDocument/formatting", "textDocument/semanticTokens/full")
    for method in methods:
        params = _params(method.endswith("formatting"))
        server = Server(checker=lambda _: None)
        _error(server, method, params, -32002)
        server.handle(_request("initialize"))
        _error(server, method, params, -32002)
        server.handle(_notice("initialized"))
        _error(server, method, params, -32602)
        server = _server()
        with redirect_stderr(StringIO()):
            server.handle(_notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 2},
                          "contentChanges": [{"range": {}, "text": "bad"}]}))
        _error(server, method, params, -32801)
        server.handle(_notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 3},
                      "contentChanges": [{"text": _FORMATTED}]}))
        expected: object = [] if method.endswith("formatting") else {
            "data": [2, 11, 2, 0, 1, 0, 7, 5, 1, 3, 0, 10, 5, 1, 2]}
        ensure(_result(server, method, params) == expected, "recovery reused refused or old snapshot data")
        server.handle(_notice("workspace/didChangeConfiguration"))
        ensure(_result(server, method, params) == expected, "configuration invalidation lost current source")
        server.handle(_notice("textDocument/didClose", {"textDocument": {"uri": _URI}}))
        _error(server, method, params, -32602)
    server = _server()
    for options in (None, {}, {"tabSize": 0, "insertSpaces": True},
                    {"tabSize": True, "insertSpaces": True}, {"tabSize": 4, "insertSpaces": 1}):
        params = _params()
        params["options"] = options
        _error(server, "textDocument/formatting", params, -32602)
    for method in ("textDocument/semanticTokens/range", "textDocument/semanticTokens/full/delta",
                   "textDocument/rangeFormatting"):
        _error(server, method, _params(), -32601)
    for text in ("module M; public Nat F()=>true;", "module M; public Nat F()=>;",
                 "module M; public Nat F(ref Nat x)=>x;"):
        server = _server(text)
        ensure(_result(server, methods[0], _params(True)) == [], "refused source received a format edit")
        ensure(_result(server, methods[1], _params()) == {"data": []}, "refused source retained tokens")


def _formatter_transport_and_limits() -> None:
    snapshot = SourceSnapshot(_URI, 1, _TEXT, 1)
    valid = _format(snapshot.source)
    ensure(formatting_edits(snapshot, valid) == _edits((1, 32)), "valid format worker result was refused")
    success = subprocess.CompletedProcess([], 0, json.dumps(valid).encode(), b"")
    with patch("vos.vela_lsp_format.subprocess.run", return_value=success) as worker:
        ensure(format_document(snapshot.source) == valid, "valid worker transport was refused")
        args, kwargs = worker.call_args
        command = args[0]
        ensure(command[0] == sys.executable and command[1] == "-I" and command[-1] == "--format"
               and kwargs["input"] == snapshot.source and kwargs["timeout"] == 5
               and kwargs["capture_output"] is True and kwargs["check"] is False,
               "formatter isolation, source input or bounded execution changed")
    for raw in ({}, {**valid, "extra": True}, {**valid, "source_sha256": "0" * 64},
                {**valid, "formatted": ""}, {**valid, "formatted": "x" * 65_537},
                {**valid, "formatted": 1}, {**valid, "formatted": "\ud800"},
                {"status": "unavailable", "reason": "limit", "source_sha256": valid["source_sha256"]},
                {"status": "unavailable", "reason": [], "source_sha256": valid["source_sha256"]}):
        try:
            formatting_edits(snapshot, raw)
        except InspectionError:
            pass
        else:
            raise AssertionError("malformed, stale or over-budget format result supplied an edit")
    for done in (subprocess.CompletedProcess([], 1, b"{}", b""),
                 subprocess.CompletedProcess([], 0, b"x" * (MAX_BODY_BYTES + 1), b""),
                 subprocess.CompletedProcess([], 0, b'{"status":"ok","status":"ok"}', b"")):
        with patch("vos.vela_lsp_format.subprocess.run", return_value=done):
            try:
                format_document(snapshot.source)
            except InspectionError:
                pass
            else:
                raise AssertionError("invalid format worker transport was accepted")
    with patch("vos.vela_lsp_format.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 5)):
        server = _server()
        server.formatter = format_document
        _error(server, "textDocument/formatting", _params(True), -32803)
    # This compact valid input expands beyond the source bound with Allman layout.
    huge = "module M;" + "".join(f"public Nat F{i}()=>1;" for i in range(2_700))
    ensure(len(huge.encode()) <= 65_536, "expansion fixture exceeds source bound before formatting")
    translate(huge.encode())
    report = _format(huge.encode())
    ensure(report.get("status") == "unavailable" and report.get("reason") == "limit",
           "format expansion did not reach its resource refusal")
    server = _server()
    server.formatter = lambda _: {**valid, "formatted": "x" * MAX_BODY_BYTES}
    _error(server, "textDocument/formatting", _params(True), -32803)
    server.formatter = _format
    ensure(_result(server, "textDocument/formatting", _params(True)) == _edits((1, 32)),
           "formatter failure poisoned the session")


def _large_ids_and_initialization_recovery() -> None:
    def full_request(method: str) -> dict[str, object]:
        request = {"jsonrpc": "2.0", "id": "", "method": method}
        overhead = len(json.dumps(request, separators=(",", ":")).encode())
        request["id"] = "i" * (MAX_BODY_BYTES - overhead)
        encode_message(request)
        return request

    server = Server()
    request = full_request("initialize")
    replies = server.handle(request)
    ensure("error" in replies[0] and not server.initialized,
           "oversized initialize reply changed lifecycle state")
    encode_message(replies[0])
    ensure("result" in server.handle(_request("initialize"))[0], "initialization refusal prevented retry")
    # The shortest unknown-method request leaves no room for even an empty correlated error.
    replies = server.handle(full_request("x"))
    ensure(replies[0].get("id") is None and _object(replies[0].get("error")).get("code") == -32803,
           "uncorrelatable oversized error was emitted or terminated the session")
    encode_message(replies[0])
    output = BytesIO()
    wire = b"".join(encode_message(message) for message in (
        full_request("initialize"), _request("initialize", identity=2),
        _request("shutdown", identity=3), _notice("exit")))
    ensure(serve(BytesIO(wire), output) == 0, "large initialize ID terminated the real stream")
    stream = BytesIO(output.getvalue())
    results = []
    while (raw := read_frame(stream)) is not None:
        results.append(decode_message(raw))
    ensure(len(results) == 3 and "error" in results[0] and "result" in results[1],
           "large-ID recovery lost later framed requests")


def _complete_editor_reply_bounds_and_recovery() -> None:
    text = "module M;\n" + "".join(f"public Nat F{index}()=>0;\n" for index in range(20))
    formatted = ("module M;\n\n"
                 + "\n\n".join(f"public Nat F{index}() => 0;" for index in range(20)) + "\n")
    tokens = {"data": [value for index in range(20)
                       for value in (1, 11, 2 if index < 10 else 3, 0, 1)]}
    for method, expected in (("textDocument/formatting", _edits((21, 0), formatted)),
                             ("textDocument/semanticTokens/full", tokens)):
        server = _server(text)
        snapshot = server.documents[_URI]
        params = _params(method.endswith("formatting"))
        request = _request(method, params, "")
        overhead = len(json.dumps(request, separators=(",", ":")).encode())
        request["id"] = "i" * (MAX_BODY_BYTES - overhead)
        encode_message(request)
        replies = server.handle(request)
        ensure(len(replies) == 1 and replies[0].get("id") == request["id"]
               and _object(replies[0].get("error")).get("code") == -32803,
               "complete editor reply exceeded its frame bound or lost request correlation")
        encode_message(replies[0])
        ensure(server.documents[_URI] is snapshot and _URI not in server.desynchronized
               and server.generation == snapshot.generation
               and server.received_versions[_URI] == snapshot.version == 1,
               "reply-bound refusal changed or desynchronized the current editor overlay")
        ensure(_result(server, method, params) == expected,
               "reply-bound refusal truncated editor results or poisoned a later bounded request")
        ensure(server.documents[_URI] is snapshot and _URI not in server.desynchronized
               and server.generation == snapshot.generation
               and server.received_versions[_URI] == snapshot.version == 1,
               "editor recovery changed the source snapshot or its current version")


def _real_process_editor_operations() -> None:
    messages = [_request("initialize", identity=1), _notice("initialized"),
                _notice("textDocument/didOpen", {"textDocument": {
                    "uri": _URI, "languageId": "vela", "version": 1, "text": _TEXT}}),
                _request("textDocument/formatting", _params(True), 2),
                _request("textDocument/semanticTokens/full", _params(), 3),
                _notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 2},
                    "contentChanges": [{"range": {"start": {"line": 0, "character": 0},
                                                  "end": {"line": 0, "character": 0}}, "text": "// 😀\r\n"}]}),
                _request("textDocument/formatting", _params(True), 4),
                _request("textDocument/semanticTokens/full", _params(), 5),
                _request("shutdown", identity=6), _notice("exit")]
    tools = str(Path(__file__).resolve().parents[1])
    script = (f"import sys; sys.path.insert(0, {tools!r}); "
              "from vos.cli.vela_lsp import main; raise SystemExit(main())")
    done = subprocess.run([sys.executable, "-I", "-c", script],
                          input=b"".join(encode_message(message) for message in messages),
                          capture_output=True, timeout=30, check=False)
    ensure(done.returncode == 0 and not done.stderr, f"editor stdio process failed: {done.stderr!r}")
    stream = BytesIO(done.stdout)
    replies: dict[object, dict[str, object]] = {}
    versions = []
    while (raw := read_frame(stream)) is not None:
        reply = decode_message(raw)
        if "id" in reply:
            ensure(reply["id"] not in replies, "stdio session duplicated a reply")
            replies[reply["id"]] = reply
        else:
            versions.append(_object(reply["params"])["version"])
    ensure(set(replies) == {1, 2, 3, 4, 5, 6} and versions == [1, 2],
           "stdio session lost requests or versioned overlays")
    ensure(replies[2].get("result") == _edits((1, 32)) and replies[3].get("result") == _TOKENS,
           "real formatter or semantic producer differs from independent expectations")
    ensure(replies[4].get("result") == _edits((2, 32), "// 😀\n" + _FORMATTED),
           "incremental overlay formatting used stale text or wrong source bounds")
    ensure(replies[5].get("result") == {"data": [2, 11, 2, 0, 1, 0, 7, 5, 1, 3, 0, 8, 5, 1, 2]},
           "incremental overlay tokens reused old coordinates")


def cases() -> list[Case]:
    return [Case("exact-formatting-edits-and-read-only-overlays", _formatting_exact_and_read_only),
            Case("editor-options-lifecycle-and-overlay-recovery", _parameters_lifecycle_and_recovery),
            Case("formatter-worker-transport-timeout-and-limits", _formatter_transport_and_limits),
            Case("large-request-ids-and-initialization-recovery", _large_ids_and_initialization_recovery),
            Case("complete-editor-reply-bounds-and-recovery", _complete_editor_reply_bounds_and_recovery),
            Case("real-process-editor-operations-and-unsaved-update", _real_process_editor_operations)]
