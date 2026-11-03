# SPDX-License-Identifier: Apache-2.0
"""Independent wire, overlay and coordinate controls for the host Vela LSP."""

import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from typing import cast, override
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.protocol_json import decode_message, encode_message, read_frame
from vos.vela_lsp import Server, diagnose, serve
from vos.vela_source import SourceSnapshot

_URI = "file:///workspace/unsaved.vela"
_GOOD = "module Demo; public Nat Answer() { return 42; }"


class _Fragmented(BytesIO):
    """A blocking stream can return fewer body bytes than requested."""

    @override
    def read(self, size: int | None = -1) -> bytes:
        return super().read(min(size, 3) if size is not None and size >= 0 else 3)


def _wire(message: dict[str, object]) -> bytes:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _request(method: str, params: object = None, identity: int = 1) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identity, "method": method,
            "params": {} if params is None else params}


def _notice(method: str, params: object = None) -> dict[str, object]:
    return {"jsonrpc": "2.0", "method": method, "params": {} if params is None else params}


def _open(uri: str = _URI, text: str = _GOOD, version: int = 1) -> dict[str, object]:
    return _notice("textDocument/didOpen", {
        "textDocument": {"uri": uri, "languageId": "vela", "version": version, "text": text}})


def _change(text: str, version: int, uri: str = _URI) -> dict[str, object]:
    return _notice("textDocument/didChange", {
        "textDocument": {"uri": uri, "version": version}, "contentChanges": [{"text": text}]})


def _record(value: object) -> dict[str, object]:
    ensure(isinstance(value, dict), f"expected object, got {value!r}")
    return cast("dict[str, object]", value)


def _published(messages: list[dict[str, object]]) -> dict[str, object]:
    ensure(len(messages) == 1, f"expected one diagnostic notification: {messages!r}")
    ensure(messages[0].get("method") == "textDocument/publishDiagnostics",
           f"unexpected publication {messages!r}")
    return _record(messages[0].get("params"))


def _initialize(server: Server) -> dict[str, object]:
    messages = server.handle(_request("initialize", {"capabilities": {}}, 7))
    ensure(len(messages) == 1 and messages[0].get("id") == 7,
           "initialize lost request correlation")
    result = _record(messages[0].get("result"))
    server.handle(_notice("initialized"))
    return _record(result.get("capabilities"))


def _refuses(operation: Callable[[], object], label: str) -> None:
    try:
        operation()
    except ValueError:
        return
    raise AssertionError(f"accepted {label}")


def _framing() -> None:
    first: dict[str, object] = {"jsonrpc": "2.0", "method": "example", "params": {"text": "é😀"}}
    second = _request("shutdown", identity=9)
    body = json.dumps(first, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream = _Fragmented(_wire(first) + _wire(second))
    ensure(read_frame(stream) == body, "fragmented Unicode frame was not read by byte length")
    ensure(decode_message(cast("bytes", read_frame(stream))) == second,
           "coalesced second frame was consumed or damaged")
    ensure(read_frame(stream) is None, "clean EOF fabricated another frame")
    encoded = encode_message(first)
    header, actual = encoded.split(b"\r\n\r\n", 1)
    ensure(header == f"Content-Length: {len(actual)}".encode("ascii"),
           "outgoing length is not the UTF-8 byte length")
    ensure(json.loads(actual) == first, "outgoing message changed Unicode content")
    for raw in (b"Content-Length: 2\r\n\r\n{", b"Content-Length: 2\n\n{}",
                b"X: 2\r\n\r\n{}", b"Content-Length: -1\r\n\r\n",
                b"Content-Length: 1048577\r\n\r\n",
                b"Content-Length: 2\r\ncontent-length: 2\r\n\r\n{}",
                b"X: " + b"a" * 8192 + b"\r\n\r\n"):
        _refuses(lambda raw=raw: read_frame(BytesIO(raw)), "malformed/over-budget frame")


def _strict_json() -> None:
    for raw in (b'{"jsonrpc":"2.0","id":1,"id":2}', b'{"x":NaN}',
                b'{"x":Infinity}', b'{"x":1e9999}', b'{"x":"\xff"}', b"[]", b"{}x",
                b'{"a":{"b":1,"b":2}}'):
        _refuses(lambda raw=raw: decode_message(raw), "malformed JSON body")
    nested = b'{"x":' + b"[" * 64 + b"0" + b"]" * 64 + b"}"
    _refuses(lambda: decode_message(nested), "JSON nesting beyond 64 containers")
    escaped = {"text": '\\"' + "[" * 100 + "é😀" + "]" * 100}
    ensure(decode_message(json.dumps(escaped).encode()) == escaped,
           "JSON string contents counted as nesting")


def _coordinates() -> None:
    snapshot = SourceSnapshot(_URI, 1, "aé😀\r\nb\rc\n", 1)
    for offset, expected in ((0, (0, 0)), (1, (0, 1)), (3, (0, 2)), (7, (0, 4)),
                             (9, (1, 0)), (10, (1, 1)), (11, (2, 0)),
                             (12, (2, 1)), (13, (3, 0))):
        ensure(snapshot.byte_position(offset) == {"line": expected[0], "character": expected[1]},
               f"UTF-8 byte {offset} mapped to wrong UTF-16 position")
    for offset in (-1, 2, 4, 5, 6, 8, 14):
        _refuses(lambda offset=offset: snapshot.byte_position(offset),
                 f"interior/out-of-source byte offset {offset}")
    for line, column, expected in ((1, 1, (0, 0)), (1, 3, (0, 2)), (1, 4, (0, 4)),
                                    (2, 2, (1, 1)), (3, 1, (2, 0)), (4, 1, (3, 0))):
        ensure(snapshot.diagnostic_position(line, column) ==
               {"line": expected[0], "character": expected[1]},
               "prototype code-point diagnostics were treated as byte or UTF-16 columns")
    identities = {snapshot.identity,
                  SourceSnapshot(_URI, 2, snapshot.text, 1).identity,
                  SourceSnapshot(_URI, 1, snapshot.text, 2).identity,
                  SourceSnapshot(_URI + "x", 1, snapshot.text, 1).identity,
                  SourceSnapshot(_URI, 1, snapshot.text + "x", 1).identity}
    ensure(len(identities) == 5, "snapshot identity omitted one of its bound inputs")


def _lifecycle() -> None:
    server = Server(checker=lambda _: None)
    messages = server.handle(_request("textDocument/hover"))
    ensure(_record(messages[0].get("error")).get("code") == -32002,
           "request before initialize was not refused")
    capabilities = _initialize(server)
    ensure(capabilities.get("positionEncoding") == "utf-16", "default UTF-16 not advertised")
    sync = capabilities.get("textDocumentSync")
    ensure(sync == 2 or _record(sync).get("change") == 2, "incremental sync not advertised")
    for provider in ("hoverProvider", "definitionProvider", "referencesProvider", "documentSymbolProvider"):
        ensure(capabilities.get(provider) is True, f"implemented {provider} not advertised")
    for provider in ("completionProvider", "renameProvider", "semanticTokensProvider"):
        ensure(not capabilities.get(provider), f"unimplemented {provider} advertised")
    repeated = server.handle(_request("initialize", {"capabilities": {}}, 8))
    ensure("error" in repeated[0], "repeated initialize accepted")
    unknown = server.handle(_request("vela/compileAndAdmit", identity=11))
    ensure(unknown[0].get("id") == 11 and
           _record(unknown[0].get("error")).get("code") == -32601,
           "unknown request lost its identity or pretended to be supported")
    ensure(server.handle(_notice("$/cancelRequest", {"id": 11})) == [],
           "cancellation notification fabricated a response")
    shutdown = server.handle(_request("shutdown", identity=12))
    ensure(shutdown == [{"jsonrpc": "2.0", "id": 12, "result": None}],
           "shutdown did not acknowledge the request with null")
    ensure("error" in server.handle(_request("textDocument/hover"))[0],
           "request after shutdown accepted")
    ensure(server.handle(_notice("exit")) == [] and server.exit_code == 0,
           "shutdown/exit was not a clean session")
    unclean = Server(checker=lambda _: None)
    unclean.handle(_notice("exit"))
    ensure(unclean.exit_code == 1, "exit without shutdown reported success")


def _overlays() -> None:
    checks: list[bytes] = []

    def checker(source: bytes) -> dict[str, object] | None:
        checks.append(source)
        return {"kind": "type", "line": 1, "column": 1, "message": "chosen diagnostic"}

    server = Server(checker=checker)
    _initialize(server)
    publication = _published(server.handle(_open(text="unsaved", version=2)))
    ensure(publication.get("uri") == _URI and publication.get("version") == 2,
           "diagnostic publication omitted the document identity/version")
    ensure(checks == [b"unsaved"], "open did not use unsaved text")
    original = server.documents[_URI]
    diagnostics = cast("list[object]", publication.get("diagnostics"))
    data = _record(_record(diagnostics[0]).get("data"))
    ensure(data.get("snapshot") == original.identity and data.get("generation") == original.generation
           and data.get("unqualified") is True,
           "diagnostics did not bind their exact unqualified source snapshot")
    with redirect_stderr(StringIO()):
        stale = _published(server.handle(_change("older", 1)))
        duplicate = _published(server.handle(_change("same version", 2)))
    ensure(stale.get("diagnostics") == duplicate.get("diagnostics") == [],
           "rejected changes left old diagnostics visible")
    ensure(server.documents[_URI] == original and checks == [b"unsaved"],
           "stale or duplicate version changed the current overlay")
    ranged = _notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": 3},
        "contentChanges": [{"text": "valid-looking first replacement"},
                           {"range": {"start": {"line": 0, "character": 0},
                                      "end": {"line": 99, "character": 0}}, "text": "x"}]})
    with redirect_stderr(StringIO()):
        _published(server.handle(ranged))
    ensure(server.documents[_URI] == original and checks == [b"unsaved"],
           "invalid multi-edit update partially committed")
    publication = _published(server.handle(_change("new overlay", 4)))
    current = server.documents[_URI]
    ensure(current.text == "new overlay" and current.version == 4 and
           current.generation > original.generation and current.identity != original.identity,
           "accepted update did not create a fresh immutable snapshot")
    ensure(publication.get("version") == 4 and checks[-1] == b"new overlay",
           "diagnostics were computed for a superseded source")
    _published(server.handle(_notice("textDocument/didSave", {
        "textDocument": {"uri": _URI}, "text": "untrusted save payload"})))
    ensure(checks[-1] == b"new overlay", "save replaced the authoritative overlay")
    before = server.documents[_URI].generation
    _published(server.handle(_notice("workspace/didChangeConfiguration", {"settings": {}})))
    ensure(server.documents[_URI].generation > before, "configuration did not invalidate source closure")
    before = server.documents[_URI].generation
    _published(server.handle(_notice("workspace/didChangeWatchedFiles", {
        "changes": [{"uri": "file:///workspace/deleted.vela", "type": 3}]})))
    ensure(server.documents[_URI].generation > before, "dependency deletion did not invalidate source closure")
    closed = _published(server.handle(_notice("textDocument/didClose", {"textDocument": {"uri": _URI}})))
    ensure(closed.get("diagnostics") == [] and _URI not in server.documents,
           "close left diagnostics or the overlay alive")


def _refused_edit_resynchronization() -> None:
    checks: list[bytes] = []

    def checker(source: bytes) -> dict[str, object] | None:
        checks.append(source)
        return {"kind": "syntax", "line": 1, "column": 1, "message": "broken input"}

    server = Server(checker=checker)
    _initialize(server)
    _published(server.handle(_open(text="old overlay")))
    invalid = _notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": 2},
        "contentChanges": [{"range": {}, "text": "unapplied client text"}]})
    with redirect_stderr(StringIO()):
        ensure(_published(server.handle(invalid)).get("diagnostics") == [],
               "refused edit did not clear obsolete diagnostics")
        for event in (_notice("textDocument/didSave", {"textDocument": {"uri": _URI}}),
                      _notice("workspace/didChangeConfiguration", {"settings": {}}),
                      _notice("workspace/didChangeWatchedFiles", {"changes": []})):
            for message in server.handle(event):
                ensure(_published([message]).get("diagnostics") == [],
                       "save/dependency invalidation revived diagnostics for unapplied source")
    ensure(checks == [b"old overlay"], "desynchronized document rechecked an obsolete overlay")
    ensure(server.documents[_URI].text == "old overlay" and server.documents[_URI].version == 1,
           "refused source was installed indirectly by save or invalidation")
    publication = _published(server.handle(_change("replacement", 3)))
    ensure(checks == [b"old overlay", b"replacement"] and publication.get("version") == 3
           and bool(publication.get("diagnostics")),
           "valid full replacement did not restore checking")
    current = server.documents[_URI]
    with redirect_stderr(StringIO()):
        publication = _published(server.handle(_change("\ud800", 4)))
    ensure(publication.get("diagnostics") == [] and server.documents[_URI] == current
           and checks == [b"old overlay", b"replacement"],
           "lone surrogate source changed the overlay or reached the producer")
    with redirect_stderr(StringIO()):
        server.handle(_change("x" * 65537, 8))
        older = _published(server.handle(_change("obsolete replacement", 7)))
    ensure(older.get("diagnostics") == [] and server.documents[_URI] == current
           and checks == [b"old overlay", b"replacement"],
           "older replacement restored diagnostics after a newer refused version")
    ensure(_published(server.handle(_change("current replacement", 9))).get("version") == 9
           and checks[-1] == b"current replacement",
           "newer full replacement did not restore synchronization")


def _bounds_and_opaque_uris() -> None:
    server = Server(checker=lambda _: None)
    _initialize(server)
    with tempfile.TemporaryDirectory(prefix="vos-vela-lsp-") as directory:
        source = Path(directory) / "source.vela"
        source.write_text("not the overlay", encoding="utf-8")
        uri = source.as_uri()
        with patch.object(Path, "read_bytes", side_effect=AssertionError("URI read disk")), \
                patch.object(Path, "read_text", side_effect=AssertionError("URI read disk")):
            ensure(_published(server.handle(_open(uri, _GOOD))).get("diagnostics") == [],
                   "valid overlay did not clear diagnostics")
        ensure(source.read_text(encoding="utf-8") == "not the overlay",
               "opening an overlay changed the source file")
    snapshot = server.documents[uri]
    with redirect_stderr(StringIO()):
        _published(server.handle(_change("😀" * 16385, 2, uri)))
    ensure(server.documents[uri] == snapshot, "UTF-8 source-byte bound used character count")
    with redirect_stderr(StringIO()):
        server.handle(_open("x" * 4097))
    ensure("x" * 4097 not in server.documents, "oversized URI admitted")
    for index in range(15):
        _published(server.handle(_open(f"untitled:buffer-{index}")))
    with redirect_stderr(StringIO()):
        server.handle(_open("untitled:seventeenth"))
    ensure(len(server.documents) == 16 and "untitled:seventeenth" not in server.documents,
           "open-document budget did not refuse the extra document")


def _real_producer_and_timeout() -> None:
    ensure(diagnose(_GOOD.encode()) is None, "valid Nat source failed the existing producer")
    for text, kind in (("module Bad; public Nat F() { return true; }", "type"),
                       ("module Bad; public Nat F() { return ; }", "syntax"),
                       ("module Bad; public Nat F() { return missing; }", "name"),
                       ("module Bad; public String F() { return 0; }", "unsupported")):
        diagnostic = diagnose(text.encode())
        ensure(diagnostic is not None and diagnostic.get("kind") == kind,
               f"existing producer {kind} diagnostic lost: {diagnostic!r}")
    server = Server()
    _initialize(server)
    text = "// é😀\r\nmodule Bad;\rpublic Nat F() { return 😀; }"
    publication = _published(server.handle(_open(text=text)))
    diagnostics = cast("list[object]", publication.get("diagnostics"))
    ensure(len(diagnostics) == 1, "producer syntax diagnostic missing")
    start = _record(_record(_record(diagnostics[0]).get("range")).get("start"))
    ensure(start == {"line": 2, "character": 24}, "real producer/newline/UTF-16 location is wrong")
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("checker", 5)):
        diagnostic = diagnose(_GOOD.encode())
    ensure(diagnostic is not None and diagnostic.get("kind") == "timeout",
           "worker timeout did not become a bounded diagnostic")


def _edit(start: tuple[int, int], end: tuple[int, int], text: str,
          range_length: int | None = None) -> dict[str, object]:
    change: dict[str, object] = {
        "range": {"start": {"line": start[0], "character": start[1]},
                  "end": {"line": end[0], "character": end[1]}}, "text": text}
    if range_length is not None:
        change["rangeLength"] = range_length
    return change


def _edits(version: int, changes: list[dict[str, object]]) -> dict[str, object]:
    return _notice("textDocument/didChange", {
        "textDocument": {"uri": _URI, "version": version}, "contentChanges": changes})


def _inverse_coordinates() -> None:
    snapshot = SourceSnapshot(_URI, 1, "a😀b\r\ncé\rd\n", 1)
    expected = {(0, 0): 0, (0, 1): 1, (0, 3): 5, (0, 4): 6, (0, 99): 6,
                (1, 0): 8, (1, 1): 9, (1, 2): 11, (1, 99): 11,
                (2, 0): 12, (2, 1): 13, (3, 0): 14, (3, 99): 14}
    for position, offset in expected.items():
        ensure(snapshot.position_byte_offset(*position) == offset,
               f"UTF-16 position {position} did not map to expected exact UTF-8 byte {offset}")
    for line, character in ((0, 2), (-1, 0), (4, 0), (0, -1), (True, 0), (0, True),
                            (0, 2 ** 31), (2 ** 31, 0), (0.0, 0), (0, 1.0)):
        _refuses(lambda line=line, character=character:
                 snapshot.position_byte_offset(cast("int", line), cast("int", character)),
                 f"invalid/interior UTF-16 position {(line, character)}")
    empty = SourceSnapshot(_URI, 1, "", 1)
    ensure(empty.position_byte_offset(0, 100) == 0, "empty line did not clamp to its end")
    # Unicode separators are ordinary source characters, not LSP line breaks.
    separators = SourceSnapshot(_URI, 1, "a\u2028b\u0085c", 1)
    ensure(separators.position_byte_offset(0, 4) == 7,
           "Unicode line separator changed the LF/CRLF/CR line model")
    _refuses(lambda: separators.position_byte_offset(1, 0), "invented Unicode-separator line")


def _sequential_incremental_edits() -> None:
    checks: list[bytes] = []

    def checker(source: bytes) -> None:
        checks.append(source)

    server = Server(checker=checker)
    _initialize(server)
    _published(server.handle(_open(text="a😀b\r\ncé\rd\n")))
    original = server.documents[_URI]
    publication = _published(server.handle(_edits(2, [
        _edit((0, 1), (0, 3), "XY", 2),
        _edit((0, 2), (1, 1), "!", 5),
        _edit((1, 0), (1, 1), "Z")])))
    current = server.documents[_URI]
    ensure(current.text == "aX!é\rZ\n" and checks == [original.source, "aX!é\rZ\n".encode()],
           "sequential edits used original coordinates or normalized exact newline bytes")
    ensure(current.version == publication.get("version") == 2 and
           current.generation == server.generation == original.generation + 1,
           "intermediate edits committed multiple versions/generations")
    # An edit can create CRLF by joining an inserted CR with an existing LF.
    _published(server.handle(_edits(3, [{"text": "a\nb"}, _edit((0, 99), (0, 100), "\r")])))
    ensure(server.documents[_URI].text == "a\r\nb", "clamped insertion did not create CRLF")
    _published(server.handle(_edits(4, [_edit((0, 1), (1, 0), "", 2)])))
    ensure(server.documents[_URI].text == "ab", "range did not remove a complete CRLF")
    before = server.documents[_URI]
    _published(server.handle(_edits(5, [])))
    ensure(server.documents[_URI].text == before.text and server.documents[_URI].version == 5
           and server.documents[_URI].generation == before.generation + 1,
           "empty synchronized batch did not advance its version atomically")
    _published(server.handle(_edits(6, [_edit((0, 0), (0, 0), "x")] * 64)))
    ensure(server.documents[_URI].text == "x" * 64 + "ab", "64-edit boundary was refused")


def _incremental_rollback_and_recovery() -> None:
    checks: list[bytes] = []

    def checker(source: bytes) -> None:
        checks.append(source)

    server = Server(checker=checker)
    _initialize(server)
    _published(server.handle(_open(text="a😀b")))
    original = server.documents[_URI]
    with redirect_stderr(StringIO()):
        publication = _published(server.handle(_edits(2, [
            _edit((0, 0), (0, 0), "X"), _edit((0, 3), (0, 3), "!")])))
        ensure(publication.get("diagnostics") == [], "refused later edit left old diagnostics")
        for version, changes in ((3, [_edit((0, 0), (0, 1), "Y")]), (4, [])):
            publication = _published(server.handle(_edits(version, changes)))
            ensure(publication.get("diagnostics") == [], "desynchronized text was rechecked")
    ensure(server.documents[_URI] == original and server.generation == original.generation
           and checks == [original.source], "refused batch partially committed or invoked producer")
    publication = _published(server.handle(_edits(5, [
        {"text": "Q😀\r\nR"}, _edit((0, 1), (1, 0), "!", 4)])))
    ensure(server.documents[_URI].text == "Q!R" and publication.get("version") == 5
           and checks == [original.source, b"Q!R"],
           "full replacement followed by ranged edit did not restore synchronization")


def _incremental_refusals_and_limits() -> None:
    malformed: list[list[dict[str, object]]] = [
        [_edit((0, 3), (0, 1), "x")],
        [_edit((0, 0), (1, 0), "x")],
        [_edit((0, 2), (0, 3), "x")],
        [_edit((0, 0), (0, 1), "x", 2)],
        [_edit((0, 0), (0, 1), "x", -1)],
        [_edit((0, 0), (0, 1), "x", True)],
        [{"range": None, "text": "x"}],
        [{"range": {"start": [], "end": {"line": 0, "character": 0}}, "text": "x"}],
        [{"rangeLength": 1, "text": "x"}],
        [_edit((0, 0), (0, 0), "\ud800")],
        [_edit((0, 0), (0, 0), "x")] * 65,
        [{"text": "x" * 65537}, {"text": "would fit"}],
        [{"text": "x" * 65536}, _edit((0, 0), (0, 0), "é"), {"text": "would fit"}],
    ]
    for index, changes in enumerate(malformed):
        checks: list[bytes] = []
        server = Server(checker=checks.append)
        _initialize(server)
        _published(server.handle(_open(text="a😀b")))
        original = server.documents[_URI]
        with redirect_stderr(StringIO()):
            publication = _published(server.handle(_edits(2, changes)))
        ensure(publication.get("diagnostics") == [] and server.documents[_URI] == original
               and server.generation == original.generation and checks == [original.source],
               f"malformed/over-budget incremental batch {index} was partially accepted")


def _incremental_process_transcript() -> None:
    source = "// é😀\r\nmodule Wire;\r\npublic Nat F() { return true; }"
    messages = [_request("initialize", {"capabilities": {}}, 20), _notice("initialized"),
                _open(text=source), _edits(2, [_edit((2, 24), (2, 28), "42", 4)]),
                _request("shutdown", identity=21), _notice("exit")]
    tools = str(Path(__file__).resolve().parents[1])
    script = (f"import sys; sys.path.insert(0, {tools!r}); "
              "from vos.cli.vela_lsp import main; raise SystemExit(main())")
    completed = subprocess.run([sys.executable, "-I", "-c", script],
                               input=b"".join(_wire(message) for message in messages),
                               capture_output=True, timeout=30, check=False)
    ensure(completed.returncode == 0 and completed.stderr == b"",
           f"incremental CLI session failed: {completed.stderr!r}")
    stream = BytesIO(completed.stdout)
    replies: list[dict[str, object]] = []
    while header := stream.readline():
        ensure(header.startswith(b"Content-Length: ") and header.endswith(b"\r\n"),
               "incremental CLI stdout contained logs or malformed headers")
        size = int(header[len(b"Content-Length: "):].strip())
        ensure(stream.readline() == b"\r\n", "incremental CLI frame separator malformed")
        body = stream.read(size)
        ensure(len(body) == size, "incremental CLI reply body truncated")
        replies.append(_record(json.loads(body)))
    ensure(len(replies) == 4 and replies[0].get("id") == 20 and replies[3].get("id") == 21,
           "incremental CLI lifecycle replies lost correlation")
    before, after = _published([replies[1]]), _published([replies[2]])
    diagnostics = cast("list[object]", before.get("diagnostics"))
    ensure(before.get("version") == 1 and len(diagnostics) == 1
           and _record(diagnostics[0]).get("code") == "type",
           "real CLI producer did not report the independently expected type error")
    ensure(after.get("version") == 2 and after.get("diagnostics") == [],
           "incremental CLI edit did not clear the real type error at its new version")


def _serve_transcript() -> None:
    messages = [_request("initialize", {"capabilities": {}}, 20), _notice("initialized"),
                _open(text="module Wire; public Nat F() { return true; }"),
                _request("shutdown", identity=21), _notice("exit")]
    output = BytesIO()
    ensure(serve(_Fragmented(b"".join(_wire(message) for message in messages)), output) == 0,
           "wire session did not complete cleanly")
    stream = BytesIO(output.getvalue())
    replies: list[dict[str, object]] = []
    while header := stream.readline():
        ensure(header.startswith(b"Content-Length: ") and header.endswith(b"\r\n"),
               "stdout contained logs or an invalid header")
        size = int(header[len(b"Content-Length: "):].strip())
        ensure(stream.readline() == b"\r\n", "reply header separator malformed")
        body = stream.read(size)
        ensure(len(body) == size, "reply length does not match emitted bytes")
        replies.append(_record(json.loads(body)))
    ensure(len(replies) == 3 and replies[0].get("id") == 20 and replies[-1].get("id") == 21,
           f"wire lifecycle replies are not correlated: {replies!r}")
    publication = _published([replies[1]])
    ensure(publication.get("version") == 1 and bool(publication.get("diagnostics")),
           "wire session lost the pure type error")
    ensure(serve(BytesIO(_wire(_notice("exit"))), BytesIO()) == 1,
           "unclean wire exit returned success")
    ensure(serve(BytesIO(), BytesIO()) == 1, "unexpected EOF returned success")
    with redirect_stderr(StringIO()):
        ensure(serve(BytesIO(b"Content-Length: 8\r\n\r\n{}"), BytesIO()) == 1,
               "truncated frame did not fail the session")
    malformed = b"Content-Length: 1\r\n\r\nx"
    output = BytesIO()
    serve(BytesIO(malformed + _wire(_notice("exit"))), output)
    stream = BytesIO(output.getvalue())
    header = stream.readline()
    size = int(header[len(b"Content-Length: "):].strip())
    ensure(stream.readline() == b"\r\n", "parse-error response header malformed")
    error = _record(json.loads(stream.read(size)))
    ensure(error.get("id") is None and _record(error.get("error")).get("code") == -32700,
           "malformed JSON did not receive a correlated-null parse error")
    for body in (b"[]", b"null", b'"text"'):
        output = BytesIO()
        raw = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        serve(BytesIO(raw + _wire(_notice("exit"))), output)
        reply_body = output.getvalue().split(b"\r\n\r\n", 1)[1]
        reply = _record(json.loads(reply_body))
        ensure(_record(reply.get("error")).get("code") == -32600,
               "valid non-message JSON was mislabeled as a parse error")


def cases() -> list[Case]:
    return [Case("fragmented-and-coalesced-frames", _framing),
            Case("strict-json-and-nesting", _strict_json),
            Case("source-coordinates-and-identities", _coordinates),
            Case("lifecycle-and-advertised-subset", _lifecycle),
            Case("versioned-full-overlays-and-invalidation", _overlays),
            Case("refused-edit-resynchronization", _refused_edit_resynchronization),
            Case("resource-bounds-and-opaque-uris", _bounds_and_opaque_uris),
            Case("existing-producer-and-timeout", _real_producer_and_timeout),
            Case("inverse-utf16-source-coordinates", _inverse_coordinates),
            Case("sequential-incremental-edits", _sequential_incremental_edits),
            Case("incremental-rollback-and-recovery", _incremental_rollback_and_recovery),
            Case("incremental-refusals-and-limits", _incremental_refusals_and_limits),
            Case("incremental-process-transcript", _incremental_process_transcript),
            Case("independent-wire-transcript", _serve_transcript)]
