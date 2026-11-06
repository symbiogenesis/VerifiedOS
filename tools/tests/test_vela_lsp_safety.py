# SPDX-License-Identifier: Apache-2.0
"""Independent refusal and recovery controls at the LSP producer/edit boundary."""

import json
import subprocess
from contextlib import redirect_stderr
from io import StringIO
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.protocol_json import MAX_BODY_BYTES, encode_message
from vos.vela.lsp import Server, diagnose

INDEPENDENT_CASES = True
_URI = "untitled:safety.vela"
_SOURCE = b"module M; public Nat F()=>true;"


def _notice(method: str, params: object = None) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": {} if params is None else params}


def _open(server: Server, text: str) -> None:
    server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    server.handle(_notice("initialized"))
    server.handle(_notice("textDocument/didOpen", {"textDocument": {
        "uri": _URI, "languageId": "vela", "version": 1, "text": text}}))


def _edit(start: int, end: int, text: str) -> dict[str, object]:
    return {"range": {"start": {"line": 0, "character": start},
                      "end": {"line": 0, "character": end}}, "text": text}


def _change(server: Server, version: int, edits: list[dict[str, object]]) -> list[dict[str, object]]:
    return server.handle(_notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": version}, "contentChanges": edits}))


def _clamped_reversed_edit_rollback() -> None:
    batches: tuple[list[dict[str, object]], ...] = (
        [_edit(100, 99, "bad")],
        [_edit(0, 0, "first"), _edit(100, 99, "bad")],
        [{"text": "replacement"}, _edit(100, 99, "bad")])
    for edits in batches:
        checked: list[bytes] = []
        server = Server(checker=checked.append)
        _open(server, "a😀b")
        original = server.documents[_URI]
        with redirect_stderr(StringIO()):
            messages = _change(server, 2, edits)
        ensure(messages == [{"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                             "params": {"uri": _URI, "diagnostics": []}}],
               "reversed edit did not clear obsolete diagnostics")
        ensure(server.documents[_URI] is original and server.generation == original.generation
               and checked == [original.source] and _URI in server.desynchronized,
               "clamping hid reversal or a refused edit batch partially committed")
        ensure(server.received_versions[_URI] == 2, "refused edit lost its newer received version")
        with redirect_stderr(StringIO()):
            _change(server, 3, [_edit(0, 0, "still desynchronized")])
        ensure(server.documents[_URI] is original and checked == [original.source],
               "ranged edit restored synchronization after a reversed edit")
        _change(server, 4, [{"text": "ok"}, _edit(99, 100, "!")])
        ensure(server.documents[_URI].text == "ok!" and _URI not in server.desynchronized
               and checked == [original.source, b"ok!"],
               "valid full replacement and ordered clamped edit failed recovery")


def _malformed_diagnostic_worker() -> None:
    valid = {"kind": "type", "line": 1, "column": 1, "message": "chosen diagnostic"}
    variants = [b'{"kind":"type","line":1,"line":1,"column":1,"message":"duplicate"}',
                b"null" + b" " * MAX_BODY_BYTES,
                b'{"kind":"type","line":1,"column":1,"message":"\\ud800"}',
                *[json.dumps({**valid, **changed}).encode() for changed in (
                    {"line": 0}, {"line": 2}, {"column": 0}, {"column": len(_SOURCE) + 2},
                    {"line": True}, {"column": 1.0}, {"kind": ""}, {"kind": "unknown"},
                    {"kind": "x" * (MAX_BODY_BYTES - 100)})]]
    for raw in variants:
        done = subprocess.CompletedProcess(["fixed"], 0, raw, b"")
        with patch("vos.vela.lsp.subprocess.run", return_value=done):
            result = diagnose(_SOURCE)
        if result is None:
            raise AssertionError("malformed worker output erased its failure diagnostic")
        ensure(result.get("kind") == "internal"
               and result.get("line") == result.get("column") == 1,
               f"malformed worker output escaped its boundary: {raw[:120]!r}")
        encode_message(result)
    for raw, expected in ((b" \r\nnull\t", None), (json.dumps(valid).encode(), valid)):
        with patch("vos.vela.lsp.subprocess.run", return_value=subprocess.CompletedProcess([], 0, raw, b"")):
            ensure(diagnose(_SOURCE) == expected, "valid diagnostic worker output was refused")


def _worker_failure_keeps_overlay_synchronized() -> None:
    invalid = subprocess.CompletedProcess([], 0,
        b'{"kind":"type","line":999,"column":1,"message":"bad site"}', b"")
    server = Server()
    with patch("vos.vela.lsp.subprocess.run", return_value=invalid):
        _open(server, _SOURCE.decode())
    ensure(_URI not in server.desynchronized and server.documents[_URI].text == _SOURCE.decode(),
           "malformed producer coordinates desynchronized the valid client overlay")
    valid = {"kind": "type", "line": 1, "column": 26, "message": "chosen type error"}
    with patch("vos.vela.lsp.subprocess.run", return_value=subprocess.CompletedProcess(
            [], 0, json.dumps(valid).encode(), b"")):
        replies = server.handle(_notice("textDocument/didSave", {"textDocument": {"uri": _URI}}))
    params = cast("dict[str, object]", replies[0]["params"])
    diagnostics = cast("list[dict[str, object]]", params["diagnostics"])
    ensure(params["version"] == 1 and len(diagnostics) == 1 and diagnostics[0]["code"] == "type",
           "valid worker recovery could not recheck the retained synchronized overlay")
    encode_message(replies[0])


def cases() -> list[Case]:
    return [Case("clamped-reversed-edit-atomic-refusal-and-recovery", _clamped_reversed_edit_rollback),
            Case("diagnostic-worker-strict-json-sites-and-bound", _malformed_diagnostic_worker),
            Case("worker-failure-retains-client-synchronization", _worker_failure_keeps_overlay_synchronized)]
