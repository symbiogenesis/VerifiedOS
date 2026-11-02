# SPDX-License-Identifier: Apache-2.0
"""Untrusted host LSP adapter for the existing pure Vela diagnostic producer."""

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Never, cast

from vos.protocol_json import FrameError, MessageError, decode_message, encode_message, read_frame
from vos.vela_source import SourceSnapshot

MAX_DOCUMENTS = 16
WORKER_SECONDS = 5
type Checker = Callable[[bytes], dict[str, object] | None]


def _invalid(message: str) -> Never:
    raise ValueError(message)


def diagnose(source: bytes) -> dict[str, object] | None:
    """Use the same interpreter and compiler checkout, without client-selected paths."""
    try:
        # -I excludes caller PYTHONPATH and user site packages. The only added path
        # is this adapter's own tools directory; no client text is executable code.
        tools = str(Path(__file__).resolve().parents[1])
        script = (f"import sys; sys.path.insert(0, {tools!r}); "
                  "from vos.vela_lsp_worker import main; raise SystemExit(main())")
        done = subprocess.run([sys.executable, "-I", "-c", script], input=source,
                              capture_output=True, timeout=WORKER_SECONDS, check=False)
        if done.returncode != 0:
            _invalid("pure diagnostic worker failed")
        result = json.loads(done.stdout)
        if result is None:
            return None
        if (not isinstance(result, dict) or set(result) != {"kind", "line", "column", "message"}
                or not isinstance(result["kind"], str) or not isinstance(result["message"], str)
                or type(result["line"]) is not int or type(result["column"]) is not int):
            _invalid("invalid pure diagnostic worker result")
        return cast("dict[str, object]", result)
    except subprocess.TimeoutExpired:
        return {"kind": "timeout", "line": 1, "column": 1,
                "message": "Pure prototype check exceeded 5 seconds; no acceptance verdict"}
    except (OSError, ValueError):
        return {"kind": "internal", "line": 1, "column": 1,
                "message": "Pure prototype diagnostic worker unavailable; no acceptance verdict"}


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        _invalid("expected an object")
    return cast("dict[str, object]", value)


def _string(value: object) -> str:
    if not isinstance(value, str):
        _invalid("expected a string")
    return value


def _integer(value: object) -> int:
    if type(value) is not int or not -(2 ** 31) <= value < 2 ** 31:
        raise ValueError("expected a 32-bit integer")
    return value


def _error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class Server:
    def __init__(self, checker: Checker | None = None) -> None:
        self.checker = diagnose if checker is None else checker
        self.documents: dict[str, SourceSnapshot] = {}
        self.desynchronized: set[str] = set()
        self.received_versions: dict[str, int] = {}
        self.generation = 0
        self.initialized = False
        self.ready = False
        self.shutdown = False
        self.exit_code: int | None = None

    def _snapshot(self, uri: str, version: int, text: str) -> SourceSnapshot:
        candidate = SourceSnapshot(uri, version, text, self.generation + 1)
        self.generation += 1
        return candidate

    def _clear(self, uri: str) -> dict[str, object]:
        return {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": []}}

    def _diagnostics(self, snapshot: SourceSnapshot) -> dict[str, object]:
        diagnostics: list[dict[str, object]] = []
        result = self.checker(snapshot.source)
        if result is not None:
            position = snapshot.diagnostic_position(cast("int", result["line"]),
                                                    cast("int", result["column"]))
            diagnostics.append({"range": {"start": position, "end": position}, "severity": 1,
                                "source": "vela-pure-prototype", "code": result["kind"],
                                "message": _string(result["message"])[:4096],
                                "data": {"snapshot": snapshot.identity,
                                         "generation": snapshot.generation, "unqualified": True}})
        return {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                "params": {"uri": snapshot.uri, "version": snapshot.version,
                           "diagnostics": diagnostics}}

    def handle(self, message: dict[str, object]) -> list[dict[str, object]]:
        if self.exit_code is not None:
            return []
        request = "id" in message
        request_id = message.get("id")
        method = message.get("method")
        if (message.get("jsonrpc") != "2.0" or not isinstance(method, str)
                or (request and not (isinstance(request_id, str) or type(request_id) is int))):
            return [_error(None, -32600, "Invalid Request")]
        if method == "exit" and not request:
            self.exit_code = 0 if self.shutdown else 1
            return []
        if not self.initialized and method != "initialize":
            return [_error(request_id, -32002, "Server not initialized")] if request else []
        if self.shutdown:
            return [_error(request_id, -32600, "Server has shut down")] if request else []
        try:
            params_value = message.get("params")
            params = {} if params_value is None else _object(params_value)
            if method == "initialize" and request:
                if self.initialized:
                    return [_error(request_id, -32600, "Server already initialized")]
                capabilities = _object(params.get("capabilities", {}))
                general = _object(capabilities.get("general", {}))
                encodings = general.get("positionEncodings", ["utf-16"])
                if not isinstance(encodings, list) or not all(isinstance(e, str) for e in encodings):
                    _invalid("invalid positionEncodings")
                # UTF-16 is mandatory in LSP even when omitted from the offer.
                self.initialized = True
                return [{"jsonrpc": "2.0", "id": request_id, "result": {
                    "capabilities": {"positionEncoding": "utf-16", "textDocumentSync": {
                        "openClose": True, "change": 1, "save": {"includeText": False}}},
                    "serverInfo": {"name": "Vela pure prototype (unqualified)", "version": "0"}}}]
            if method == "shutdown" and request:
                self.shutdown = True
                self.documents.clear()
                self.desynchronized.clear()
                self.received_versions.clear()
                return [{"jsonrpc": "2.0", "id": request_id, "result": None}]
            if request:
                return [_error(request_id, -32601, "Method not found")]
            if method == "initialized":
                self.ready = True
                return []
            if method == "$/cancelRequest":
                return []
            if not self.ready:
                _invalid("initialized notification is required before document work")
            if method in {"workspace/didChangeConfiguration", "workspace/didChangeWatchedFiles"}:
                output: list[dict[str, object]] = []
                for uri, old in list(self.documents.items()):
                    if uri in self.desynchronized:
                        continue
                    snapshot = self._snapshot(uri, old.version, old.text)
                    self.documents[uri] = snapshot
                    output.append(self._diagnostics(snapshot))
                return output
            if method not in {"textDocument/didOpen", "textDocument/didChange",
                              "textDocument/didSave", "textDocument/didClose"}:
                return []
            document = _object(params.get("textDocument"))
            uri = _string(document.get("uri"))
            if method == "textDocument/didOpen":
                if uri in self.documents or len(self.documents) >= MAX_DOCUMENTS:
                    _invalid("duplicate open or document count exceeds limit")
                if document.get("languageId") != "vela":
                    _invalid("expected Vela languageId")
                snapshot = self._snapshot(uri, _integer(document.get("version")),
                                          _string(document.get("text")))
                self.received_versions[uri] = snapshot.version
            else:
                if uri not in self.documents:
                    _invalid("document is not open")
                old = self.documents[uri]
                if method == "textDocument/didClose":
                    del self.documents[uri]
                    self.desynchronized.discard(uri)
                    del self.received_versions[uri]
                    self.generation += 1
                    return [self._clear(uri)]
                if method == "textDocument/didSave":
                    if uri in self.desynchronized:
                        return [self._clear(uri)]
                    return [self._diagnostics(old)]
                version = _integer(document.get("version"))
                if version <= self.received_versions[uri]:
                    _invalid("document version must strictly increase")
                # Remember newer received versions even if their text is refused.
                # An older later update cannot resynchronize the document.
                self.received_versions[uri] = version
                changes = params.get("contentChanges")
                if not isinstance(changes, list) or len(changes) != 1:
                    _invalid("one complete replacement is required")
                change = _object(changes[0])
                if set(change) != {"text"}:
                    _invalid("incremental/ranged edits are unsupported")
                snapshot = self._snapshot(uri, version, _string(change["text"]))
            self.documents[uri] = snapshot
            self.desynchronized.discard(uri)
            return [self._diagnostics(snapshot)]
        except (ValueError, UnicodeError) as error:
            if request:
                return [_error(request_id, -32602, str(error)[:256])]
            print(f"vela-lsp: ignored {method}: {str(error)[:256]}", file=sys.stderr)
            params_value = message.get("params")
            if isinstance(params_value, dict):
                document_value = params_value.get("textDocument")
                if isinstance(document_value, dict):
                    uri_value = document_value.get("uri")
                    if isinstance(uri_value, str) and uri_value in self.documents:
                        self.desynchronized.add(uri_value)
                        return [self._clear(uri_value)]
            return []


def serve(input_stream: BinaryIO, output_stream: BinaryIO) -> int:
    server = Server()
    try:
        while server.exit_code is None:
            raw = read_frame(input_stream)
            if raw is None:
                return 1
            try:
                message = decode_message(raw)
            except FrameError:
                raise
            except MessageError:
                replies = [_error(None, -32600, "Invalid Request")]
            except (ValueError, UnicodeError):
                replies = [_error(None, -32700, "Parse error")]
            else:
                replies = server.handle(message)
            output_stream.writelines(encode_message(reply) for reply in replies)
            output_stream.flush()
    except (FrameError, OSError, ValueError) as error:
        print(f"vela-lsp: session closed: {str(error)[:256]}", file=sys.stderr)
        return 1
    return server.exit_code
