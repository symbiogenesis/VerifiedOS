# SPDX-License-Identifier: Apache-2.0
"""Loopback-only HTTP transport for Vela's bounded development playground."""

import hashlib
import hmac
import secrets
import socket
import subprocess
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import cast, override

from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message
from vos.vela.ast import IDENTIFIER, MAX_SOURCE_BYTES
from vos.vela.authoring import LINT_CODES, is_pascal_case
from vos.vela.lsp import Server
from vos.vela.source import SourceSnapshot

MAX_SESSIONS = 8
SESSION_SECONDS = 1800
READ_SECONDS = 10
WORKER_SECONDS = 5
MAX_AUTHORING_FINDINGS = 8192
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/app.mjs": ("app.mjs", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


def _raw(message: dict[str, object]) -> bytes:
    return encode_message(message).split(b"\r\n\r\n", 1)[1]


def _validate_result(response: dict[str, object], request: dict[str, object], digest: str) -> None:
    if response.get("sourceHash") != digest or type(response.get("ok")) is not bool:
        raise ValueError("compiler worker returned an invalid source identity")
    compilation = request["action"] == "compile"
    if compilation and type(response.get("editorServices")) is not bool:
        raise ValueError("compiler worker returned invalid editor-service availability")
    if response["ok"]:
        if request["action"] == "authoring":
            _validate_authoring(response, cast("str", request["source"]))
            return
        fields = {"ok", "sourceHash", "module", "gallina", "findings", "editorServices"} if compilation else {
            "ok", "sourceHash", "valueType", "value"}
        if (set(response) != fields
                or not all(isinstance(response[key], str) for key in fields - {"ok", "findings", "editorServices"})):
            raise ValueError("compiler worker returned an invalid result")
        if compilation:
            if response["editorServices"]:
                if response["findings"] != []:
                    raise ValueError("pure compilation returned mathematical findings")
            else:
                _validate_findings(response["findings"], cast("str", request["source"]), mathematical=True)
        if request["action"] == "evaluate":
            value = cast("str", response["value"])
            if (response["valueType"] != request["valueType"]
                    or (request["valueType"] == "bool" and value not in {"true", "false"})
                    or (request["valueType"] == "Nat" and (not value.isascii() or not value.isdecimal()))):
                raise ValueError("compiler worker returned an invalid typed value")
    else:
        error = response.get("error")
        kinds = {"syntax", "name", "type", "unsupported", "limit", "encoding"}
        if request["action"] != "authoring" and (not compilation or not response["editorServices"]):
            kinds.update({"protocol", "inference"})
        if request["action"] == "authoring":
            kinds.update({"inspection-limit", "lint-preview", "format"})
        fields = {"ok", "sourceHash", "error"} | ({"editorServices"} if compilation else set())
        if (set(response) != fields or not isinstance(error, dict)
                or set(error) != {"kind", "message", "line", "column"}
                or not isinstance(error["kind"], str)
                or error["kind"] not in kinds
                or not isinstance(error["message"], str)
                or type(error["line"]) is not int or type(error["column"]) is not int
                or error["line"] < 1 or error["column"] < 1):
            raise ValueError("compiler worker returned an invalid refusal")


def _validate_authoring(response: dict[str, object], source: str) -> None:
    if set(response) != {"ok", "sourceHash", "findings", "bindingPreview"}:
        raise ValueError("authoring worker returned an invalid result")
    findings, preview = response["findings"], response["bindingPreview"]
    if (not isinstance(findings, list) or len(findings) > MAX_AUTHORING_FINDINGS
            or not isinstance(preview, str) or len(preview.encode("utf-8")) > MAX_SOURCE_BYTES):
        raise ValueError("authoring worker returned an invalid or oversized result")
    _validate_findings(findings, source)


def _validate_findings(findings: object, source: str, *, mathematical: bool = False) -> None:
    if not isinstance(findings, list) or len(findings) > MAX_AUTHORING_FINDINGS:
        raise ValueError("compiler worker returned oversized or invalid findings")
    snapshot = SourceSnapshot("vela:playground-findings", 0, source, 1)
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    previous = (0, 0)
    allowed = {"VELA105", "VELA106"} if mathematical else LINT_CODES - {"VELA105", "VELA106"}
    for finding in findings:
        if (not isinstance(finding, dict) or set(finding) != {"code", "message", "line", "column"}
                or not isinstance(finding["code"], str) or finding["code"] not in allowed
                or not isinstance(finding["message"], str) or not finding["message"]
                or type(finding["line"]) is not int or type(finding["column"]) is not int):
            raise ValueError("authoring worker returned an invalid finding")
        snapshot.diagnostic_position(finding["line"], finding["column"])
        if mathematical:
            site = (finding["line"], finding["column"])
            line, column = lines[site[0] - 1], site[1] - 1
            if finding["code"] == "VELA105":
                name = IDENTIFIER.match(line, column)
                if (site <= previous or name is None or is_pascal_case(name.group())
                        or (column and (line[column - 1].isascii()
                                        and (line[column - 1].isalnum() or line[column - 1] == "_")))):
                    raise ValueError("mathematical naming finding does not identify a source name")
            else:
                if site <= previous or column >= len(line) or line[column].isspace():
                    raise ValueError("mathematical pattern finding does not identify a source pattern")
                if "shadows constructor" in finding["message"]:
                    name = IDENTIFIER.match(line, column)
                    if (name is None
                            or f"'{name.group()}'" not in finding["message"]
                            or (column and line[column - 1].isascii()
                                and (line[column - 1].isalnum() or line[column - 1] == "_"))):
                        raise ValueError("mathematical constructor-shadowing finding does not match source binder")
                elif "unreachable" in finding["message"]:
                    if (column and line[column - 1].isascii()
                            and (line[column - 1].isalnum() or line[column - 1] == "_")
                            and (line[column].isalnum() or line[column] == "_")):
                        raise ValueError("mathematical unreachable-arm finding starts inside an identifier")
                else:
                    raise ValueError("mathematical pattern finding has unrecognized message")
            previous = site


def _compiler_response(request: dict[str, object], digest: str, *,
                       mathematical_parser: Path | None = None,
                       parser_sha256: str | None = None) -> dict[str, object]:
    directory = str(Path(__file__).resolve().parents[2])
    parser_argument = f"Path({str(mathematical_parser)!r})" if mathematical_parser is not None else "None"
    script = (f"import sys; sys.path.insert(0, {directory!r}); from pathlib import Path; "
              "from vos.vela.playground_worker import main; "
              f"raise SystemExit(main(mathematical_parser={parser_argument}, "
              f"parser_sha256={parser_sha256!r}))")
    done = subprocess.run([sys.executable, "-I", "-c", script], input=_raw(request),
                          capture_output=True, timeout=WORKER_SECONDS, check=False)
    if done.returncode != 0:
        raise ValueError("compiler worker unavailable or output exceeds its budget")
    response = decode_message(done.stdout)
    _validate_result(response, request, digest)
    _raw(response)
    return response


def _require_parser(parser: Path | None, digest: str | None) -> None:
    if parser is None or digest is None or hashlib.sha256(parser.read_bytes()).hexdigest() != digest:
        raise ValueError("prepared mathematical parser is unavailable or changed")


def run_compiler(request: dict[str, object], *, mathematical_parser: Path | None = None,
                 parser_sha256: str | None = None) -> dict[str, object]:
    """Source is worker stdin data, never an executable argument or a disk path."""
    source = cast("str", request["source"]).encode("utf-8")
    digest = hashlib.sha256(source).hexdigest()
    response: dict[str, object]
    try:
        if mathematical_parser is not None and request["action"] != "authoring":
            _require_parser(mathematical_parser, parser_sha256)
            response = _compiler_response(request, digest, mathematical_parser=mathematical_parser,
                                          parser_sha256=parser_sha256)
            _require_parser(mathematical_parser, parser_sha256)
        else:
            response = _compiler_response(request, digest)
    except subprocess.TimeoutExpired:
        response = {"ok": False, "sourceHash": digest,
                    "error": {"kind": "timeout", "line": 1, "column": 1,
                              "message": "Compiler exceeded five seconds; no result"}}
    except (OSError, ValueError):
        response = {"ok": False, "sourceHash": digest,
                    "error": {"kind": "internal", "line": 1, "column": 1,
                              "message": "Compiler worker unavailable or response exceeds its budget"}}
    else:
        return response
    if request["action"] == "compile":
        response["editorServices"] = False
    return response


@dataclass
class Session:
    server: Server = field(default_factory=Server)
    touched: float = field(default_factory=time.monotonic)


class PlaygroundServer(HTTPServer):
    """One synchronous request at a time bounds worker and overlay concurrency."""

    request_queue_size = 8

    def __init__(self, port: int = 8765, *, assets: Path | None = None,
                 mathematical_parser: Path | None = None) -> None:
        self.token = secrets.token_urlsafe(32)
        self.mathematical_parser = mathematical_parser
        self.parser_sha256 = (hashlib.sha256(mathematical_parser.read_bytes()).hexdigest()
                              if mathematical_parser is not None else None)
        self.sessions: dict[str, Session] = {}
        self.assets = (Path(__file__).resolve().parents[2] / "vela" / "playground"
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
        return connection, cast("tuple[str, int]", address)

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
        with suppress(OSError):
            self.connection.shutdown(socket.SHUT_RD)

    @override
    def handle(self) -> None:
        with suppress(ConnectionError, TimeoutError):
            super().handle()

    @override
    def finish(self) -> None:
        self._read_timer.cancel()
        super().finish()

    @property
    def playground(self) -> PlaygroundServer:
        return cast("PlaygroundServer", self.server)

    @override
    def log_message(self, format: str, *args: object) -> None:
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

    def do_GET(self) -> None:
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

    def _read_json(self, size: int) -> dict[str, object]:
        self._body_read = True
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("Truncated JSON body")
        self._read_timer.cancel()
        return decode_message(raw)

    def do_POST(self) -> None:
        if not self._authority():
            return
        authorization = self.headers.get_all("Authorization", [])
        if (len(authorization) != 1 or not hmac.compare_digest(
                authorization[0].encode("utf-8"), f"Bearer {self.playground.token}".encode())):
            self._error(401, "Missing or invalid playground token; reopen the printed launch URL")
            return
        if self.path not in {"/api/session", "/api/close", "/api/lsp", "/api/compile", "/api/evaluate",
                             "/api/authoring", "/api/capabilities"}:
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
            request = self._read_json(size)
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
        if self.path == "/api/capabilities":
            if request:
                raise ValueError("Capability query requires an empty object")
            return {"mathematical": self.playground.mathematical_parser is not None}
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
        expected = {"source", "expression", "valueType"} if self.path == "/api/evaluate" else {"source"}
        if set(request) != expected or not all(isinstance(value, str) for value in request.values()):
            raise ValueError("Compiler request has missing, extra or non-text fields")
        source = cast("str", request["source"])
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ValueError("Source exceeds the compiler's UTF-8 byte budget")
        if self.path == "/api/evaluate":
            if request["valueType"] not in {"Nat", "bool"}:
                raise ValueError("Expression result type must be Nat or bool")
            if len(cast("str", request["expression"]).encode("utf-8")) > 4096:
                raise ValueError("Expression exceeds 4096 UTF-8 bytes")
        operation = {**request, "action": self.path.rsplit("/", 1)[1]}
        return run_compiler(operation, mathematical_parser=self.playground.mathematical_parser,
                            parser_sha256=self.playground.parser_sha256)
