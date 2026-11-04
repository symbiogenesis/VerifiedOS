# SPDX-License-Identifier: Apache-2.0
"""Loopback-only HTTP transport for the unqualified pure Vela playground."""

import hashlib
import hmac
import secrets
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import cast, override

from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message
from vos.vela_ast import MAX_SOURCE_BYTES
from vos.vela_lsp import Server

MAX_SESSIONS = 8
SESSION_SECONDS = 1800
READ_SECONDS = 10
WORKER_SECONDS = 5
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/app.mjs": ("app.mjs", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


def _raw(message: dict[str, object]) -> bytes:
    return encode_message(message).split(b"\r\n\r\n", 1)[1]


def _validate_result(response: dict[str, object], request: dict[str, object], digest: str) -> None:
    if response.get("sourceHash") != digest or type(response.get("ok")) is not bool:
        raise ValueError("compiler worker returned an invalid source identity")
    if response["ok"]:
        fields = {"ok", "sourceHash", "module", "gallina"} if request["action"] == "compile" else {
            "ok", "sourceHash", "valueType", "value"}
        if set(response) != fields or not all(isinstance(response[key], str) for key in fields - {"ok"}):
            raise ValueError("compiler worker returned an invalid result")
        if request["action"] == "evaluate":
            value = cast("str", response["value"])
            if (response["valueType"] != request["valueType"]
                    or (request["valueType"] == "bool" and value not in {"true", "false"})
                    or (request["valueType"] == "Nat" and (not value.isascii() or not value.isdecimal()))):
                raise ValueError("compiler worker returned an invalid typed value")
    else:
        error = response.get("error")
        if (set(response) != {"ok", "sourceHash", "error"} or not isinstance(error, dict)
                or set(error) != {"kind", "message", "line", "column"}
                or not isinstance(error["kind"], str)
                or error["kind"] not in {"syntax", "name", "type", "unsupported", "limit", "encoding"}
                or not isinstance(error["message"], str)
                or type(error["line"]) is not int or type(error["column"]) is not int
                or error["line"] < 1 or error["column"] < 1):
            raise ValueError("compiler worker returned an invalid refusal")


def run_compiler(request: dict[str, object]) -> dict[str, object]:
    """Source is worker stdin data, never an executable argument or a disk path."""
    source = cast("str", request["source"]).encode("utf-8")
    digest = hashlib.sha256(source).hexdigest()
    try:
        directory = str(Path(__file__).resolve().parents[1])
        script = (f"import sys; sys.path.insert(0, {directory!r}); "
                  "from vos.vela_playground_worker import main; raise SystemExit(main())")
        done = subprocess.run([sys.executable, "-I", "-c", script], input=_raw(request),
                              capture_output=True, timeout=WORKER_SECONDS, check=False)
        if done.returncode != 0:
            raise ValueError("compiler worker unavailable or output exceeds its budget")
        response = decode_message(done.stdout)
        _validate_result(response, request, digest)
        _raw(response)
    except subprocess.TimeoutExpired:
        return {"ok": False, "sourceHash": digest,
                "error": {"kind": "timeout", "line": 1, "column": 1,
                          "message": "Compiler exceeded five seconds; no result"}}
    except (OSError, ValueError):
        return {"ok": False, "sourceHash": digest,
                "error": {"kind": "internal", "line": 1, "column": 1,
                          "message": "Compiler worker unavailable or response exceeds its budget"}}
    return response


@dataclass
class Session:
    server: Server = field(default_factory=Server)
    touched: float = field(default_factory=time.monotonic)


class PlaygroundServer(HTTPServer):
    """One synchronous request at a time bounds worker and overlay concurrency."""

    request_queue_size = 8

    def __init__(self, port: int = 8765, *, assets: Path | None = None) -> None:
        self.token = secrets.token_urlsafe(32)
        self.sessions: dict[str, Session] = {}
        self.assets = (Path(__file__).resolve().parents[1] / "vela" / "playground"
                       if assets is None else assets)
        super().__init__(("127.0.0.1", port), PlaygroundHandler)
        self.authority = f"127.0.0.1:{self.server_address[1]}"
        self.origin = f"http://{self.authority}"

    @property
    def launch_url(self) -> str:
        return f"{self.origin}/#token={self.token}"

    @override
    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        connection, address = super().get_request()
        connection.settimeout(READ_SECONDS)
        return connection, address

    def expire_sessions(self) -> None:
        now = time.monotonic()
        self.sessions = {identity: item for identity, item in self.sessions.items()
                         if now - item.touched < SESSION_SECONDS}

    @override
    def server_close(self) -> None:
        self.sessions.clear()
        super().server_close()


class PlaygroundHandler(BaseHTTPRequestHandler):
    server_version = "VelaPlayground"
    _body_read = False

    @override
    def setup(self) -> None:
        super().setup()
        self._read_timer = threading.Timer(READ_SECONDS, self._end_read)
        self._read_timer.daemon = True
        self._read_timer.start()

    def _end_read(self) -> None:
        try:
            self.connection.shutdown(socket.SHUT_RD)
        except OSError:
            pass

    @override
    def handle(self) -> None:
        try:
            super().handle()
        except (ConnectionError, TimeoutError):
            pass

    @override
    def finish(self) -> None:
        self._read_timer.cancel()
        super().finish()

    @property
    def playground(self) -> PlaygroundServer:
        return cast("PlaygroundServer", self.server)

    @override
    def log_message(self, _format: str, *args: object) -> None:
        """Avoid logging source, request paths or authentication material."""

    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self._read_timer.cancel()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        # Drain an ordinary bounded body before closing, so Windows can deliver
        # the error response without resetting a connection with unread bytes.
        lengths = self.headers.get_all("Content-Length", [])
        if (not self._body_read and len(lengths) == 1 and lengths[0].isascii()
                and lengths[0].isdecimal() and len(lengths[0]) <= 8
                and int(lengths[0]) <= MAX_BODY_BYTES
                and self.headers.get("Transfer-Encoding") is None):
            self._body_read = True
            try:
                self.rfile.read(int(lengths[0]))
            except OSError:
                self.close_connection = True
        self._send(status, _raw({"error": message}))

    def _authority(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        if hosts != [self.playground.authority] or origins not in ([], [self.playground.origin]):
            self._error(403, "Host or Origin does not match the local playground")
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - the standard HTTP dispatcher names this hook.
        if not self._authority():
            return
        asset = ASSETS.get(self.path)
        if asset is None:
            self._error(404, "Unknown playground asset")
            return
        try:
            body = (self.playground.assets / asset[0]).read_bytes()
        except OSError:
            self._error(503, "Playground assets unavailable")
            return
        self._send(200, body, asset[1])

    def do_POST(self) -> None:  # noqa: N802 - the standard HTTP dispatcher names this hook.
        if not self._authority():
            return
        authorization = self.headers.get_all("Authorization", [])
        if (len(authorization) != 1 or not hmac.compare_digest(
                authorization[0].encode("utf-8"), f"Bearer {self.playground.token}".encode())):
            self._error(401, "Missing or invalid playground token; reopen the printed launch URL")
            return
        if self.path not in {"/api/session", "/api/close", "/api/lsp", "/api/compile", "/api/evaluate"}:
            self._error(404, "Unknown playground operation")
            return
        lengths = self.headers.get_all("Content-Length", [])
        if (len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal()
                or len(lengths[0]) > 8 or self.headers.get("Transfer-Encoding") is not None):
            self._error(400, "One decimal Content-Length is required")
            return
        size = int(lengths[0])
        if size > MAX_BODY_BYTES:
            self._error(413, "Request exceeds the JSON byte budget")
            return
        if self.headers.get_all("Content-Type", []) != ["application/json"]:
            self._error(415, "Use application/json with UTF-8")
            return
        try:
            self._body_read = True
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Truncated JSON body")
            self._read_timer.cancel()
            request = decode_message(raw)
            response = self._dispatch(request)
            encoded = _raw(response)
        except TimeoutError:
            self._error(408, "Request read timed out")
            return
        except (ValueError, UnicodeError) as error:
            self._error(400, str(error))
            return
        except LookupError as error:
            self._error(410, str(error))
            return
        self._send(200, encoded)

    def _dispatch(self, request: dict[str, object]) -> dict[str, object]:
        self.playground.expire_sessions()
        if self.path == "/api/close":
            if set(request) != {"session"} or not isinstance(request["session"], str):
                raise ValueError("Expected a session identifier")
            self.playground.sessions.pop(request["session"], None)
            return {"closed": True}
        if self.path == "/api/session":
            if request:
                raise ValueError("Session creation requires an empty object")
            if len(self.playground.sessions) >= MAX_SESSIONS:
                raise ValueError("Session limit reached; close idle tabs and restart the playground")
            identity = secrets.token_urlsafe(24)
            self.playground.sessions[identity] = Session()
            return {"session": identity}
        if self.path == "/api/lsp":
            if (set(request) != {"session", "message"} or not isinstance(request["session"], str)
                    or not isinstance(request["message"], dict)):
                raise ValueError("Expected a session identifier and LSP message object")
            session = self.playground.sessions.get(request["session"])
            if session is None:
                raise LookupError("Session expired or unknown; reconnect to the playground")
            session.touched = time.monotonic()
            messages = session.server.handle(cast("dict[str, object]", request["message"]))
            if session.server.exit_code is not None:
                del self.playground.sessions[request["session"]]
            return {"messages": messages}
        expected = {"source"} if self.path == "/api/compile" else {"source", "expression", "valueType"}
        if set(request) != expected or not all(isinstance(value, str) for value in request.values()):
            raise ValueError("Compiler request has missing, extra or non-text fields")
        source = cast("str", request["source"])
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ValueError("Source exceeds the pure compiler's UTF-8 byte budget")
        if self.path == "/api/evaluate":
            if request["valueType"] not in {"Nat", "bool"}:
                raise ValueError("Expression result type must be Nat or bool")
            if len(cast("str", request["expression"]).encode("utf-8")) > 4096:
                raise ValueError("Expression exceeds 4096 UTF-8 bytes")
        return run_compiler({**request, "action": self.path.rsplit("/", 1)[1]})
