# SPDX-License-Identifier: Apache-2.0
"""Small read-only MCP stdio binding for the existing Sail context interface.

Supports the versioned 2026-07-28 stateless protocol and 2025-11-25 initialization.
There are no network listeners, model calls, executable tool arguments or caches.
The reader remains available during retrieval so cancellation can suppress replies.
"""

import json
import math
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, BinaryIO, Never

from jsonschema import Draft202012Validator

from vos import sailbundle, sailcontext

MODERN = "2026-07-28"
LEGACY = "2025-11-25"
INFO = {"name": "verifiedos-sail", "version": "1"}
PREFIX = "io.modelcontextprotocol/"
MAX_MESSAGE = 1_048_576
MAX_PENDING = 8


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"not a JSON number: {value}")


def _float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"JSON number exceeds finite precision: {value}")
    return parsed


def decode(raw: bytes) -> object:
    """RFC 8259 JSON; duplicate members and nonfinite numbers are refused."""
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant, parse_float=_float)


def tool_schema(operation: str) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "query": {"type": "string", "minLength": 1, "maxLength": 4096},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
        "max_chars": {"type": "integer", "minimum": 256, "maximum": 16000, "default": 1600},
    }
    if operation == "search":
        properties.update({
            "kinds": {"type": "array", "uniqueItems": True,
                      "items": {"enum": list(sailcontext.KINDS)}},
            "exclude": {"type": "array", "uniqueItems": True, "maxItems": 200,
                        "items": {"type": "string", "minLength": 1, "maxLength": 1024}},
        })
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "additionalProperties": False, "required": ["query"], "properties": properties}


def tools(root: Path) -> list[dict[str, Any]]:
    schema = decode((root / "tools/sail-context.schema.json").read_bytes())
    return [{"name": f"sail_{operation}", "description": description + " " + sailcontext.NOTICE,
             "inputSchema": tool_schema(operation), "outputSchema": schema,
             "annotations": {"readOnlyHint": True, "destructiveHint": False,
                             "idempotentHint": True, "openWorldHint": False}}
            for operation, description in (
                ("references", "Find incoming compiler-recorded links to an exact name."),
                ("search", "Rank local declaration examples by query words."),
                ("symbol", "Find an exact symbol across declaration kinds and scattered clauses."))]


class ProtocolError(Exception):
    def __init__(self, code: int, message: str, data: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


def fail(code: int, message: str, data: object = None) -> Never:
    raise ProtocolError(code, message, data)


class Server:
    """One stdio process; all modern request context comes from that request."""

    def __init__(self, root: Path, output: BinaryIO) -> None:
        self.root = root
        self.output = output
        self.lock = threading.RLock()
        self.pending: dict[str | int, tuple[threading.Event, Future[None]]] = {}
        self.legacy_initialized = False
        self.legacy_ready = False
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sail-context")

    def send(self, message: dict[str, Any]) -> None:
        with self.lock:
            self.output.write((json.dumps(message, ensure_ascii=True, allow_nan=False,
                                          separators=(",", ":")) + "\n").encode("utf-8"))
            self.output.flush()

    def error(self, ident: str | int | None, code: int, message: str, data: object = None) -> None:
        payload: dict[str, Any] = {"code": code, "message": message}
        response: dict[str, Any] = {"jsonrpc": "2.0", "error": payload}
        if ident is not None:
            response["id"] = ident
        if data is not None:
            payload["data"] = data
        self.send(response)

    def result(self, ident: str | int, value: dict[str, Any], modern: bool) -> None:
        if modern:
            value = {**value, "resultType": "complete", "_meta": {PREFIX + "serverInfo": INFO}}
        self.send({"jsonrpc": "2.0", "id": ident, "result": value})

    def version(self, params: dict[str, Any]) -> bool:
        meta = params.get("_meta", {})
        if not isinstance(meta, dict):
            raise ProtocolError(-32602, "_meta must be an object")
        version = meta.get(PREFIX + "protocolVersion")
        if version is None and self.legacy_ready:
            return False
        if not isinstance(version, str) or not isinstance(meta.get(PREFIX + "clientCapabilities"), dict):
            raise ProtocolError(-32602, "modern requests require protocolVersion and clientCapabilities")
        if version != MODERN:
            raise ProtocolError(-32022, "Unsupported protocol version",
                                {"requested": version, "supported": [MODERN, LEGACY]})
        return True

    def cancel(self, ident: object) -> None:
        if not isinstance(ident, (str, int)) or isinstance(ident, bool):
            return
        with self.lock:
            if ident in self.pending:
                event, future = self.pending[ident]
                event.set()
                if future.cancel():
                    self.pending.pop(ident, None)

    def call(self, ident: str | int, params: dict[str, Any], modern: bool,
             cancelled: threading.Event) -> None:
        try:
            name, arguments = params.get("name"), params.get("arguments", {})
            operations: dict[str, sailcontext.Operation] = {
                "sail_search": "search", "sail_symbol": "symbol", "sail_references": "references"}
            operation = operations.get(name) if isinstance(name, str) else None
            if operation is None:
                fail(-32602, "Unknown tool")
            validator = Draft202012Validator(tool_schema(operation))
            invalid = next(iter(validator.iter_errors(arguments)), None)
            if invalid:
                value: dict[str, Any] = {"isError": True,
                                        "content": [{"type": "text", "text": invalid.message}]}
            else:
                try:
                    report = sailcontext.context(
                        self.root, operation, arguments["query"],
                        kinds=tuple(arguments.get("kinds", [])), exclude=tuple(arguments.get("exclude", [])),
                        limit=arguments.get("limit", 5), max_chars=arguments.get("max_chars", 1600))
                    value = {"content": [{"type": "text", "text": json.dumps(report, ensure_ascii=True)}],
                             "structuredContent": report, "isError": False}
                except (OSError, ValueError, sailbundle.BundleError) as exc:
                    value = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
            with self.lock:
                if not cancelled.is_set():
                    self.result(ident, value, modern)
        except ProtocolError as exc:
            with self.lock:
                if not cancelled.is_set():
                    self.error(ident, exc.code, str(exc), exc.data)
        except Exception:  # contain an unexpected tool fault without leaking process internals
            with self.lock:
                if not cancelled.is_set():
                    self.error(ident, -32603, "Internal tool error")
        finally:
            with self.lock:
                self.pending.pop(ident, None)

    def receive(self, message: object) -> None:
        ident: str | int | None = None
        try:
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                fail(-32600, "Expected one JSON-RPC 2.0 message")
            method = message.get("method")
            if not isinstance(method, str) or not method:
                fail(-32600, "Expected a method name")
            if "id" not in message:
                params = message.get("params", {})
                if isinstance(params, dict):
                    if method == "notifications/cancelled":
                        self.cancel(params.get("requestId"))
                    elif method == "notifications/initialized" and self.legacy_initialized:
                        self.legacy_ready = True
                return  # notifications, including unknown ones, have no response
            candidate = message["id"]
            if isinstance(candidate, bool) or not isinstance(candidate, (str, int)):
                fail(-32600, "Request id must be a string or integer")
            ident = candidate
            params = message.get("params", {})
            if not isinstance(params, dict):
                fail(-32602, "params must be an object")
            with self.lock:
                if ident in self.pending:
                    fail(-32600, "Request id is already in flight")
            if method == "initialize":
                if not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("capabilities"), dict):
                    fail(-32602, "initialize requires protocolVersion and capabilities")
                self.legacy_initialized = True
                self.legacy_ready = False
                self.result(ident, {"protocolVersion": LEGACY, "capabilities": {"tools": {}},
                                    "serverInfo": INFO, "instructions": sailcontext.NOTICE}, False)
                return
            modern = self.version(params)
            if method == "server/discover" and modern:
                self.result(ident, {"supportedVersions": [MODERN, LEGACY], "capabilities": {"tools": {}},
                                    "instructions": sailcontext.NOTICE, "ttlMs": 0, "cacheScope": "private"}, modern)
            elif method == "ping":
                self.result(ident, {}, modern)
            elif method == "tools/list":
                if params.get("cursor") is not None:
                    fail(-32602, "This finite tool list has no cursor")
                listing = {"tools": tools(self.root), **({"ttlMs": 0, "cacheScope": "private"} if modern else {})}
                self.result(ident, listing, modern)
            elif method == "tools/call":
                with self.lock:
                    if len(self.pending) >= MAX_PENDING:
                        fail(1001, "Too many pending requests; retry after completion")
                    event = threading.Event()
                    future = self.pool.submit(self.call, ident, params, modern, event)
                    self.pending[ident] = event, future
            else:
                fail(-32601, "Method not found")
        except ProtocolError as exc:
            self.error(ident, exc.code, str(exc), exc.data)
        except (OSError, ValueError):
            self.error(ident, -32603, "Cannot read the local tool contract")

    def close(self) -> None:
        self.pool.shutdown(wait=True)


def serve(root: Path, incoming: BinaryIO, outgoing: BinaryIO) -> int:
    server = Server(root, outgoing)
    try:
        while raw := incoming.readline(MAX_MESSAGE + 1):
            if len(raw) > MAX_MESSAGE:
                server.error(None, -32600, "Message exceeds the 1 MiB input limit")
                return 1
            try:
                message = decode(raw)
            except (ValueError, UnicodeError, RecursionError):
                server.error(None, -32700, "Invalid UTF-8 JSON")
                continue
            server.receive(message)
    finally:
        server.close()
    return 0
