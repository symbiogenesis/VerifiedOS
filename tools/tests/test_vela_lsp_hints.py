# SPDX-License-Identifier: Apache-2.0
"""Independent authoring-hint controls over pure compiler facts and LSP wire data."""

import copy
import json
import subprocess
import sys
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from typing import cast

from tests.harness import Case, ensure
from vos.protocol_json import MAX_BODY_BYTES, encode_message
from vos.vela import VelaError, inspect_source
from vos.vela.lsp import Server
from vos.vela.lsp_services import InspectionError, project
from vos.vela.source import SourceSnapshot

INDEPENDENT_CASES = True

_URI = "untitled:authoring-hints.vela"
_TEXT = ("// 😀\r\nmodule Hints;\rpublic bool Pick(bool input) {\n"
         "  let count = 2;\r\n  if (input) {\r"
         "    let choice = count == 2;\n    return choice;\r\n"
         "  } else {\r    let choice = false;\n    return choice;\r\n  }\n}")


def _object(value: object) -> dict[str, object]:
    ensure(isinstance(value, dict), f"expected an object: {value!r}")
    return cast("dict[str, object]", value)


def _request(method: str, params: object = None, identity: object = 1) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identity, "method": method,
            "params": {} if params is None else params}


def _notice(method: str, params: object = None) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": {} if params is None else params}


def _reply(server: Server, method: str, params: object = None,
           identity: object = 1) -> dict[str, object]:
    replies = server.handle(_request(method, params, identity))
    ensure(len(replies) == 1 and replies[0].get("id") == identity,
           f"hint request lost correlation: {replies!r}")
    return replies[0]


def _result(server: Server, params: object) -> object:
    reply = _reply(server, "textDocument/inlayHint", params)
    ensure("result" in reply and "error" not in reply, f"hint query failed: {reply!r}")
    return reply["result"]


def _error(server: Server, params: object, code: int) -> None:
    reply = _reply(server, "textDocument/inlayHint", params)
    ensure(_object(reply.get("error")).get("code") == code,
           f"expected hint error {code}: {reply!r}")


def _params(start: tuple[int, int] = (0, 0), end: tuple[int, int] = (11, 1),
            uri: str = _URI) -> dict[str, object]:
    return {"textDocument": {"uri": uri}, "range": {
        "start": {"line": start[0], "character": start[1]},
        "end": {"line": end[0], "character": end[1]}}}


def _hint(line: int, column: int, value_type: str) -> dict[str, object]:
    return {"position": {"line": line, "character": column},
            "label": ": " + value_type, "kind": 1}


def _open(server: Server, text: str = _TEXT) -> None:
    server.handle(_notice("textDocument/didOpen", {"textDocument": {
        "uri": _URI, "languageId": "vela", "version": 1, "text": text}}))


def _inspect(source: bytes) -> dict[str, object]:
    try:
        return inspect_source(source)
    except VelaError as error:
        return {"status": "unavailable", "reason": error.kind}


def _server(text: str = _TEXT) -> Server:
    server = Server(checker=lambda _: None, inspector=_inspect)
    reply = _reply(server, "initialize")
    capabilities = _object(_object(reply.get("result")).get("capabilities"))
    ensure(capabilities.get("inlayHintProvider") is True,
           "implemented type hints were not advertised")
    server.handle(_notice("initialized"))
    _open(server, text)
    return server


def _inferred_types_scopes_and_ranges() -> None:
    server = _server()
    expected = [_hint(3, 11, "Nat"), _hint(5, 14, "bool"), _hint(8, 14, "bool")]
    ensure(_result(server, _params()) == expected,
           "hint labels, inferred types, sibling scopes or mixed-newline positions differ")
    ensure(_result(server, _params((3, 6), (3, 11))) == expected[:1],
           "an exactly enclosed identifier did not receive its end-anchored hint")
    ensure(_result(server, _params((5, 8), (8, 14))) == expected[1:],
           "range selection confused same-spelled declarations in sibling branches")
    for first, last in (((3, 7), (3, 11)), ((3, 6), (3, 10)),
                        ((3, 11), (3, 11)), ((0, 3), (0, 5))):
        ensure(_result(server, _params(first, last)) == [],
               f"partial identifier, empty range or supplementary comment received a hint: {first!r}")
    ensure(_result(server, _params((11, 0), (11, 1000))) == [],
           "clamping a range beyond line end manufactured a hint")
    explicit = _server("module Explicit;\npublic bool Id(bool value) { return value; }")
    ensure(_result(explicit, _params(end=(1, 999))) == [],
           "explicit parameter or function signature received a redundant type hint")
    namespaces = _server("module Names;\npublic Nat Earlier() { return 1; }\n"
                         "public bool Use() { let Earlier = Earlier() == 1; return Earlier; }")
    ensure(_result(namespaces, _params(end=(2, 999))) == [_hint(2, 31, "bool")],
           "a same-spelled function supplied the type or hint site of a local binding")


def _explicit_annotations_and_inferred_flags() -> None:
    text = ("module Typed;\r\npublic Nat F() {\r  let Nat count = 1;\n"
            "  bool ready = true;\r\n  let next = count + 1;\n  return next;\n}")
    source = text.encode()
    facts = inspect_source(source)
    variables = {symbol["name"]: symbol for symbol in cast("list[dict[str, object]]", facts["symbols"])
                 if symbol["kind"] == "variable"}
    ensure(variables["count"].get("inferred") is False and variables["ready"].get("inferred") is False,
           "typed let or bare typed local lost its explicit-annotation fact")
    ensure("inferred" not in variables["next"], "inferred locals changed their established fact shape")
    snapshot = SourceSnapshot(_URI, 1, text, 1)
    ensure(project(snapshot, facts, "textDocument/inlayHint", None,
                   requested_range=((0, 0), (6, 1))) == [_hint(4, 10, "Nat")],
           "explicit local annotations acquired redundant hints or hid an inferred local")
    for malformed, kind in ((True, "variable"), (None, "variable"), (0, "variable"),
                             ("false", "variable"), (False, "function")):
        changed = copy.deepcopy(facts)
        symbol = next(symbol for symbol in cast("list[dict[str, object]]", changed["symbols"])
                      if symbol["kind"] == kind)
        symbol["inferred"] = malformed
        try:
            project(snapshot, changed, "textDocument/inlayHint", None,
                    requested_range=((0, 0), (6, 1)))
        except InspectionError:
            pass
        else:
            raise AssertionError("hint projection accepted an invented or misplaced inference flag")
    updated = text.replace("let Nat count", "let count")
    refreshed = inspect_source(updated.encode())
    ensure(project(SourceSnapshot(_URI, 2, updated, 2), refreshed, "textDocument/inlayHint", None,
                   requested_range=((0, 0), (6, 1))) == [_hint(2, 11, "Nat"), _hint(4, 10, "Nat")],
           "removing a type annotation failed to refresh inferred-local hints")


def _invalid_ranges_and_lifecycle() -> None:
    server = Server(checker=lambda _: None, inspector=_inspect)
    _error(server, _params(), -32002)
    _reply(server, "initialize")
    _error(server, _params(), -32002)
    server.handle(_notice("initialized"))
    _error(server, _params(), -32602)
    _open(server)
    variants: tuple[object, ...] = (
        {}, {"textDocument": {"uri": _URI}},
        {"textDocument": {"uri": _URI}, "range": {}},
        _params((3, 11), (3, 6)), _params((3, 100), (3, 99)),
        _params((-1, 0), (3, 11)), _params((True, 0), (3, 11)),
        _params((0, 4), (3, 11)), _params((0, 0), (20, 0)),
        _params(uri="file:///unopened-is-not-read.vela"),
    )
    for params in variants:
        _error(server, params, -32602)
    ensure(_result(server, _params()) == [
        _hint(3, 11, "Nat"), _hint(5, 14, "bool"), _hint(8, 14, "bool")],
        "invalid range poisoned later valid hints")
    resolved = _reply(server, "inlayHint/resolve", {})
    ensure(_object(resolved.get("error")).get("code") == -32601,
           "unimplemented resolve service was exposed")
    server.handle(_notice("textDocument/didClose", {"textDocument": {"uri": _URI}}))
    _error(server, _params(), -32602)
    _reply(server, "shutdown")
    _error(server, _params(), -32600)


def _edits_refusal_and_resynchronization() -> None:
    server = _server()
    server.handle(_notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 2},
        "contentChanges": [{"range": {"start": {"line": 0, "character": 0},
                                      "end": {"line": 0, "character": 0}}, "text": "// moved\n"}]}))
    ensure(_result(server, _params(end=(12, 1))) == [
        _hint(4, 11, "Nat"), _hint(6, 14, "bool"), _hint(9, 14, "bool")],
        "incremental edit reused old hint coordinates")
    with redirect_stderr(StringIO()):
        server.handle(_notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 3},
            "contentChanges": [{"range": {}, "text": "not applied"}]}))
    _error(server, _params(end=(12, 1)), -32801)
    server.handle(_notice("workspace/didChangeConfiguration", {}))
    _error(server, _params(end=(12, 1)), -32801)
    replacement = "module Changed;\npublic bool Pick() {\n  let count = false;\n  return count;\n}"
    server.handle(_notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 4},
        "contentChanges": [{"text": replacement}]}))
    ensure(_result(server, _params(end=(4, 1))) == [_hint(2, 11, "bool")],
           "full replacement failed to refresh the inferred type and remove old declarations")
    server.handle(_notice("workspace/didChangeWatchedFiles", {}))
    ensure(_result(server, _params(end=(4, 1))) == [_hint(2, 11, "bool")],
           "dependency invalidation reused or removed current hints")
    for version, text in enumerate(("module Bad; public Nat F() { let item = true; return item; }",
                                    "module Bad; public Nat F(ref Nat item) { return item; }",
                                    "module Bad; public Nat F() { let item = 2;"), start=5):
        server.handle(_notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": version},
            "contentChanges": [{"text": text}]}))
        ensure(_result(server, _params(end=(0, 999))) == [],
               "invalid, unsupported or incomplete source exposed stale or partial hints")


def _malformed_facts_and_worker_failure() -> None:
    server = _server()
    facts = inspect_source(_TEXT.encode("utf-8"))
    for detail in ("count: u64", "another: Nat", "Nat", "count: Nat\naccepted", ""):
        changed = copy.deepcopy(facts)
        symbols = cast("list[dict[str, object]]", changed["symbols"])
        count = next(symbol for symbol in symbols if symbol["kind"] == "variable")
        count["detail"] = detail
        server.inspector = lambda _, changed=changed: changed
        _error(server, _params((8, 8), (8, 14)), -32803)
    # Even a malformed fact outside the requested range refuses the whole query.
    server.inspector = lambda _: {"status": "unavailable", "reason": "inspection-limit"}
    _error(server, _params(), -32803)
    server.inspector = lambda _: (_ for _ in ()).throw(InspectionError("bounded worker failure"))
    _error(server, _params(), -32803)
    server.inspector = lambda _: (_ for _ in ()).throw(subprocess.TimeoutExpired("fixed", 5))
    _error(server, _params(), -32803)
    server.inspector = _inspect
    ensure(_result(server, _params()) == [
        _hint(3, 11, "Nat"), _hint(5, 14, "bool"), _hint(8, 14, "bool")],
        "worker failure poisoned a later independent hint request")


def _complete_reply_bounds() -> None:
    server = _server()
    request = _request("textDocument/inlayHint", _params(), "")
    envelope = len(json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode())
    request["id"] = "x" * (MAX_BODY_BYTES - envelope)
    ensure(len(encode_message(request).split(b"\r\n\r\n", 1)[1]) == MAX_BODY_BYTES,
           "hint bound control did not fill the valid incoming frame")
    refused = server.handle(request)[0]
    ensure(_object(refused.get("error")).get("code") == -32803 and refused.get("id") == request["id"],
           "oversized hint response was truncated or lost correlation")
    encode_message(refused)
    ensure(len(cast("list[object]", _result(server, _params()))) == 3 and server.exit_code is None,
           "oversized result poisoned the next query or terminated the session")


def _projection_source_links_and_limits() -> None:
    snapshot = SourceSnapshot(_URI, 1, _TEXT, 1)
    raw = inspect_source(snapshot.source)
    ensure(project(snapshot, raw, "textDocument/inlayHint", None,
                   requested_range=((3, 6), (3, 11))) == [_hint(3, 11, "Nat")],
           "projection did not use the bounded compiler's inferred fact")
    for field, value in (("line", 1), ("column", 8), ("name", "coun")):
        changed = copy.deepcopy(raw)
        symbol = next(symbol for symbol in cast("list[dict[str, object]]", changed["symbols"])
                      if symbol["kind"] == "variable")
        symbol[field] = value
        try:
            project(snapshot, changed, "textDocument/inlayHint", None,
                    requested_range=((0, 0), (11, 1)))
        except InspectionError:
            pass
        else:
            raise AssertionError("hint projection accepted a source-mismatched worker fact")
    oversized = copy.deepcopy(raw)
    oversized["symbols"] = cast("list[object]", oversized["symbols"]) * 200
    try:
        project(snapshot, oversized, "textDocument/inlayHint", None,
                requested_range=((0, 0), (11, 1)))
    except InspectionError:
        pass
    else:
        raise AssertionError("hint projection accepted an over-budget worker result")


def _wire(message: dict[str, object]) -> bytes:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _real_process_hints_and_unsaved_edits() -> None:
    changed = "module Changed;\npublic bool Pick() {\n  let count = false;\n  return count;\n}"
    invalid = "module Bad;\npublic bool Pick() { let count = false; return 2; }"
    messages = [_request("initialize", identity=1), _notice("initialized"),
                _notice("textDocument/didOpen", {"textDocument": {
                    "uri": _URI, "languageId": "vela", "version": 1, "text": _TEXT}}),
                _request("textDocument/inlayHint", _params(), 2),
                _notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 2},
                    "contentChanges": [{"range": {"start": {"line": 0, "character": 0},
                                                  "end": {"line": 0, "character": 0}},
                                        "text": "// moved\n"}]}),
                _request("textDocument/inlayHint", _params(end=(12, 1)), 3),
                _notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 3},
                    "contentChanges": [{"text": changed}]}),
                _request("textDocument/inlayHint", _params(end=(4, 1)), 4),
                _notice("textDocument/didChange", {"textDocument": {"uri": _URI, "version": 4},
                    "contentChanges": [{"text": invalid}]}),
                _request("textDocument/inlayHint", _params(end=(1, 999)), 5),
                _request("shutdown", identity=6), _notice("exit")]
    tools = str(Path(__file__).resolve().parents[1])
    script = (f"import sys; sys.path.insert(0, {tools!r}); "
              "from vos.cli.vela_lsp import main; raise SystemExit(main())")
    completed = subprocess.run([sys.executable, "-I", "-c", script],
                               input=b"".join(_wire(message) for message in messages),
                               capture_output=True, timeout=30, check=False)
    ensure(completed.returncode == 0 and completed.stderr == b"",
           f"real hint process failed: {completed.stderr!r}")
    stream = BytesIO(completed.stdout)
    replies: dict[int, dict[str, object]] = {}
    versions: list[object] = []
    while header := stream.readline():
        ensure(header.startswith(b"Content-Length: ") and header.endswith(b"\r\n"),
               "hint process emitted logs or malformed framing")
        length = int(header[len(b"Content-Length: "):].strip())
        ensure(stream.readline() == b"\r\n", "hint process omitted frame separator")
        body = stream.read(length)
        ensure(len(body) == length, "hint response was truncated")
        reply = _object(json.loads(body))
        if "id" in reply:
            identity = reply["id"]
            ensure(type(identity) is int and identity not in replies,
                   "hint process repeated a response identity")
            replies[cast("int", identity)] = reply
        else:
            ensure(reply.get("method") == "textDocument/publishDiagnostics",
                   "hint process emitted an unexpected notification")
            publication = _object(reply.get("params"))
            version = publication.get("version")
            versions.append(version)
            ensure(bool(publication.get("diagnostics")) == (version == 4),
                   "wire fixture's independently expected diagnostics disagree")
    ensure(set(replies) == set(range(1, 7)) and versions == [1, 2, 3, 4],
           "hint session lost requests or versioned overlay diagnostics")
    ensure(replies[2].get("result") == [
        _hint(3, 11, "Nat"), _hint(5, 14, "bool"), _hint(8, 14, "bool")],
        "wire hints differ from independently expected inference/UTF-16 locations")
    ensure(replies[3].get("result") == [
        _hint(4, 11, "Nat"), _hint(6, 14, "bool"), _hint(9, 14, "bool")],
        "wire incremental edit reused old hint sites")
    ensure(replies[4].get("result") == [_hint(2, 11, "bool")] and replies[5].get("result") == [],
           "wire replacement or refused source reused old inferred facts")
    ensure(replies[6].get("result") is None and "error" not in replies[6],
           "hint process shutdown failed")


def cases() -> list[Case]:
    return [Case("inferred-types-sibling-scopes-and-exact-ranges", _inferred_types_scopes_and_ranges),
            Case("explicit-local-annotations-and-inference-flags", _explicit_annotations_and_inferred_flags),
            Case("invalid-ranges-lifecycle-and-no-resolve", _invalid_ranges_and_lifecycle),
            Case("incremental-edits-refusal-and-resynchronization", _edits_refusal_and_resynchronization),
            Case("malformed-facts-and-worker-failure", _malformed_facts_and_worker_failure),
            Case("complete-hint-reply-bounds-and-recovery", _complete_reply_bounds),
            Case("projection-source-links-and-limits", _projection_source_links_and_limits),
            Case("real-process-hints-and-unsaved-edits", _real_process_hints_and_unsaved_edits)]
