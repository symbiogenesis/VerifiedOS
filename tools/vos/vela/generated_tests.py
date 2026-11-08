# SPDX-License-Identifier: Apache-2.0
"""Independent coordinate/overlay/formatter oracles and isolated Hypothesis qualification (Q25x).

See [Generated development tests](../../../docs/languages/vela/tooling-protocols.md#generated-development-tests)
for the campaign bounds, independent oracle rules, seeded defect controls, and adoption disposition.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.metadata as importlib_metadata
import io
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from unittest.mock import patch

from vos import vela
from vos.vela import authoring
from vos.vela.ast import MAX_SOURCE_BYTES
from vos.vela.lsp import MAX_CHANGES, MAX_DOCUMENTS, Server
from vos.vela.lsp_format import formatting_edits
from vos.vela.source import MAX_URI_BYTES, SourceSnapshot

CANDIDATE_PACKAGES: tuple[str, ...] = ("hypothesis==6.170.14", "sortedcontainers==2.4.0")
CANDIDATE_VERSIONS: dict[str, str] = {"hypothesis": "6.170.14", "sortedcontainers": "2.4.0"}
COOLDOWN_CUTOFF = "2026-10-31T07:17:33Z"

EXPECTED_LICENSE_SHA256: dict[str, tuple[str, str]] = {
    "hypothesis": (
        "hypothesis-6.170.14.dist-info/licenses/LICENSE.txt",
        "ac89037bac63550644dce8cf32c6765e5fab9dc1a1ce94b89f8a805f341a6750",
    ),
    "sortedcontainers": (
        "sortedcontainers-2.4.0.dist-info/LICENSE",
        "1db7cae7fce6452e2e608e401a0f953e0133e4c2d75db69fb8ae851d2086f5b6",
    ),
}

EXPECTED_NATIVE_SHA256: frozenset[str] = frozenset({
    "b7722a385d97a5ce0e0a5800770516ce5557f4abed4503b12b7f8e6c6a202c3b",  # win_arm64 abi3
    "d53f91b1afbf54b0acbfa42b893221e8248f93fb810271eb9973a098231b7cfd",  # win_amd64 cp314
    "fd6780187c6b86d727f8ce8fc97defbeb48796bd090afe31200679343c8faa72",  # win_amd64 abi3
    "1a25e29e9b879fb3de4bdd805e11d416dc8a4fc62d2f81472095fbfa8630ea61",  # manylinux_aarch64 cp314
    "1c8c1a9e353817caa11a636b89cde86b136cff69fcef0426276e01c134ddabd7",  # manylinux_aarch64 abi3
    "e40780bfbfb364b2fcc2b65e7baba953e4e1eaacb19fdd39578130889f0ec427",  # manylinux_x86_64 cp314
    "f5aefc013fbc8d88682e30a70d7fd16c037cbbeb30f99c7d84097a5d6c94d380",  # manylinux_x86_64 abi3
})

DEFAULT_SEED = 20261107
DEFAULT_MAX_EXAMPLES = 64
DEFAULT_STEP_COUNT = 32
DEFAULT_MAX_DOCUMENT_BYTES = 4096
DEFAULT_TIMEOUT_SECONDS = 60

SEEDED_FAULTS: tuple[str, ...] = (
    "utf16-codepoint-confusion",
    "edit-against-original-document",
    "publish-early-edit-before-rollback",
)
HELD_OUT_FAULT = "publish-early-edit-before-rollback"


class ObservationMismatchError(AssertionError):
    """Raised when a system observation disagrees with the independent model."""


@dataclass(frozen=True)
class OracleLine:
    """Independently computed scalar, UTF-8 byte, and UTF-16 line boundaries."""

    start_cp: int
    end_cp: int
    start_byte: int
    end_byte: int
    content: str
    utf16_to_byte: dict[int, int]
    byte_to_utf16: dict[int, int]
    utf16_width: int


class OracleTextModel:
    """Independent scalar-traversal and explicit UTF-16 coordinate/edit oracle.

    Computes line breaks, UTF-8 byte boundaries, UTF-16 unit counts, line-end
    clamping, and sequential ranged edits directly from Unicode scalar values
    without calling any `SourceSnapshot` helper.
    """

    def __init__(
        self,
        raw: bytes,
        text: str,
        lines: tuple[OracleLine, ...],
        byte_to_pos: dict[int, dict[str, int]],
    ) -> None:
        self.raw = raw
        self.text = text
        self.lines = lines
        self.byte_to_pos = byte_to_pos

    @classmethod
    def from_text(cls, text: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> OracleTextModel:
        raw = text.encode("utf-8")
        if len(raw) > max_bytes:
            raise ValueError("source exceeds byte limit")
        lines: list[OracleLine] = []
        byte_to_pos: dict[int, dict[str, int]] = {}
        line_start_cp = 0
        line_start_byte = 0
        idx = 0
        byte_cursor = 0
        length = len(text)
        while idx < length:
            ch = text[idx]
            ch_bytes = len(ch.encode("utf-8"))
            if ch in "\r\n":
                line_obj = cls._make_line(
                    text, line_start_cp, idx, line_start_byte, byte_cursor, len(lines), byte_to_pos
                )
                lines.append(line_obj)
                if ch == "\r" and idx + 1 < length and text[idx + 1] == "\n":
                    idx += 2
                    byte_cursor += 2
                else:
                    idx += 1
                    byte_cursor += 1
                line_start_cp = idx
                line_start_byte = byte_cursor
            else:
                idx += 1
                byte_cursor += ch_bytes
        line_obj = cls._make_line(
            text, line_start_cp, length, line_start_byte, byte_cursor, len(lines), byte_to_pos
        )
        lines.append(line_obj)
        return cls(raw, text, tuple(lines), byte_to_pos)

    @staticmethod
    def _make_line(
        text: str,
        start_cp: int,
        end_cp: int,
        start_byte: int,
        end_byte: int,
        line_idx: int,
        byte_to_pos: dict[int, dict[str, int]],
    ) -> OracleLine:
        content = text[start_cp:end_cp]
        utf16_to_byte: dict[int, int] = {}
        byte_to_utf16: dict[int, int] = {}
        utf16_pos = 0
        b_pos = start_byte
        for ch in content:
            utf16_to_byte[utf16_pos] = b_pos
            byte_to_utf16[b_pos] = utf16_pos
            byte_to_pos[b_pos] = {"line": line_idx, "character": utf16_pos}
            utf16_pos += 1 if ord(ch) <= 0xFFFF else 2
            b_pos += len(ch.encode("utf-8"))
        utf16_to_byte[utf16_pos] = end_byte
        byte_to_utf16[end_byte] = utf16_pos
        byte_to_pos[end_byte] = {"line": line_idx, "character": utf16_pos}
        return OracleLine(
            start_cp=start_cp,
            end_cp=end_cp,
            start_byte=start_byte,
            end_byte=end_byte,
            content=content,
            utf16_to_byte=utf16_to_byte,
            byte_to_utf16=byte_to_utf16,
            utf16_width=utf16_pos,
        )

    def expected_byte_position(self, offset: object) -> dict[str, int] | None:
        if type(offset) is not int or offset < 0 or offset > len(self.raw):
            return None
        return self.byte_to_pos.get(offset)

    def expected_position_byte_offset(self, line: object, character: object) -> int | None:
        if (
            type(line) is not int
            or type(character) is not int
            or not 0 <= line < 2**31
            or not 0 <= character < 2**31
            or line >= len(self.lines)
        ):
            return None
        entry = self.lines[line]
        clamped = min(character, entry.utf16_width)
        return entry.utf16_to_byte.get(clamped)

    def expected_diagnostic_position(self, line: object, column: object) -> dict[str, int] | None:
        if type(line) is not int or type(column) is not int:
            return None
        if not 1 <= line <= len(self.lines):
            return None
        entry = self.lines[line - 1]
        if not 1 <= column <= len(entry.content) + 1:
            return None
        utf16_units = sum(1 if ord(ch) <= 0xFFFF else 2 for ch in entry.content[: column - 1])
        return {"line": line - 1, "character": utf16_units}

    def expected_full_range(self) -> dict[str, dict[str, int]]:
        last_idx = len(self.lines) - 1
        return {
            "start": {"line": 0, "character": 0},
            "end": {"line": last_idx, "character": self.lines[last_idx].utf16_width},
        }

    def expected_apply_change(
        self, change: object, *, max_bytes: int = MAX_SOURCE_BYTES
    ) -> OracleTextModel | None:
        if not isinstance(change, dict):
            return None
        replacement = change.get("text")
        if not isinstance(replacement, str):
            return None
        if "range" in change:
            if set(change) - {"range", "rangeLength", "text"}:
                return None
            span = change.get("range")
            if not isinstance(span, dict):
                return None
            start_pos = span.get("start")
            end_pos = span.get("end")
            if not isinstance(start_pos, dict) or not isinstance(end_pos, dict):
                return None
            s_line, s_char = start_pos.get("line"), start_pos.get("character")
            e_line, e_char = end_pos.get("line"), end_pos.get("character")
            if (
                type(s_line) is not int
                or type(s_char) is not int
                or type(e_line) is not int
                or type(e_char) is not int
                or not (-2**31 <= s_line < 2**31)
                or not (-2**31 <= s_char < 2**31)
                or not (-2**31 <= e_line < 2**31)
                or not (-2**31 <= e_char < 2**31)
            ):
                return None
            if (s_line, s_char) > (e_line, e_char):
                return None
            first = self.expected_position_byte_offset(s_line, s_char)
            last = self.expected_position_byte_offset(e_line, e_char)
            if first is None or last is None:
                return None
            if "rangeLength" in change:
                r_len = change["rangeLength"]
                if type(r_len) is not int or r_len < 0:
                    return None
                removed_str = self.raw[first:last].decode("utf-8")
                removed_units = sum(1 if ord(c) <= 0xFFFF else 2 for c in removed_str)
                if r_len != removed_units:
                    return None
            updated_bytes = self.raw[:first] + replacement.encode("utf-8") + self.raw[last:]
            try:
                updated_text = updated_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return None
        elif set(change) == {"text"}:
            updated_text = replacement
        else:
            return None
        try:
            return OracleTextModel.from_text(updated_text, max_bytes=max_bytes)
        except ValueError:
            return None


def verify_coordinate_observations(
    uri: str,
    version: int,
    text: str,
    queries: list[tuple[object, object]],
    byte_queries: list[object],
    diagnostic_sites: list[tuple[int, int]],
) -> None:
    """Compare `SourceSnapshot` against `OracleTextModel` across coordinates and diagnostics."""
    raw = text.encode("utf-8")
    if len(raw) > DEFAULT_MAX_DOCUMENT_BYTES:
        raise ValueError(f"normal campaign document exceeds {DEFAULT_MAX_DOCUMENT_BYTES} bytes")
    oracle = OracleTextModel.from_text(text)
    snapshot = SourceSnapshot(uri, version, text, 1)

    if snapshot.source != oracle.raw or snapshot.text != oracle.text:
        raise ObservationMismatchError("SourceSnapshot mutated or normalized original source bytes")

    for line, character in queries:
        expected_byte = oracle.expected_position_byte_offset(line, character)
        try:
            actual_byte: int | None = snapshot.position_byte_offset(
                cast("int", line), cast("int", character)
            )
        except ValueError:
            actual_byte = None
        if actual_byte != expected_byte:
            raise ObservationMismatchError(
                f"position_byte_offset mismatch at ({line!r}, {character!r}): "
                f"actual={actual_byte!r}, expected={expected_byte!r}"
            )
        if actual_byte is not None:
            expected_pos = oracle.expected_byte_position(actual_byte)
            actual_pos = snapshot.byte_position(actual_byte)
            if actual_pos != expected_pos:
                raise ObservationMismatchError(
                    f"byte_position mismatch at byte {actual_byte}: "
                    f"actual={actual_pos!r}, expected={expected_pos!r}"
                )

    for b_offset in byte_queries:
        expected_bpos = oracle.expected_byte_position(b_offset)
        try:
            actual_bpos: dict[str, int] | None = snapshot.byte_position(cast("int", b_offset))
        except ValueError:
            actual_bpos = None
        if actual_bpos != expected_bpos:
            raise ObservationMismatchError(
                f"byte_position mismatch at offset {b_offset!r}: "
                f"actual={actual_bpos!r}, expected={expected_bpos!r}"
            )

    for line, column in diagnostic_sites:
        expected_dpos = oracle.expected_diagnostic_position(line, column)
        try:
            actual_dpos: dict[str, int] | None = snapshot.diagnostic_position(line, column)
        except ValueError:
            actual_dpos = None
        if actual_dpos != expected_dpos:
            raise ObservationMismatchError(
                f"diagnostic_position mismatch at ({line}, {column}): "
                f"actual={actual_dpos!r}, expected={expected_dpos!r}"
            )


def deterministic_checker(raw: bytes) -> dict[str, object] | None:
    """Bounded deterministic diagnostic stub for protocol/overlay state tests."""
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    for idx, line in enumerate(text.split("\n"), start=1):
        marker = line.find("SYNTAX_ERROR")
        if marker != -1:
            return {
                "kind": "syntax",
                "message": "synthetic syntax error marker",
                "line": idx,
                "column": marker + 1,
            }
    return None


def deterministic_inspector(raw: bytes) -> dict[str, object]:
    """Bounded deterministic symbol/occurrence stub for overlay service requests."""
    if deterministic_checker(raw) is not None:
        return {"status": "unavailable", "reason": "syntax"}
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    symbols: list[dict[str, object]] = []
    occurrences: list[dict[str, object]] = []
    fn_idx: int | None = None
    param_idx: int | None = None
    local_idx: int | None = None

    for line_no, line in enumerate(lines, start=1):
        fn_decl = line.find("public Nat Entry(Nat input)")
        if fn_decl != -1 and fn_idx is None:
            entry_col = fn_decl + len("public Nat ") + 1
            input_col = fn_decl + len("public Nat Entry(Nat ") + 1
            fn_idx = len(symbols)
            symbols.append({
                "name": "Entry",
                "kind": "function",
                "detail": "public Nat Entry(Nat input)",
                "line": line_no,
                "column": entry_col,
            })
            occurrences.append({
                "symbol": fn_idx,
                "line": line_no,
                "column": entry_col,
                "declaration": True,
            })
            param_idx = len(symbols)
            symbols.append({
                "name": "input",
                "kind": "parameter",
                "detail": "input: Nat",
                "line": line_no,
                "column": input_col,
            })
            occurrences.append({
                "symbol": param_idx,
                "line": line_no,
                "column": input_col,
                "declaration": True,
            })
            continue

        let_decl = line.find("let local = input;")
        if let_decl != -1 and param_idx is not None and local_idx is None:
            local_col = let_decl + len("let ") + 1
            use_input_col = let_decl + len("let local = ") + 1
            local_idx = len(symbols)
            symbols.append({
                "name": "local",
                "kind": "variable",
                "detail": "local: Nat",
                "line": line_no,
                "column": local_col,
            })
            occurrences.append({
                "symbol": local_idx,
                "line": line_no,
                "column": local_col,
                "declaration": True,
            })
            occurrences.append({
                "symbol": param_idx,
                "line": line_no,
                "column": use_input_col,
                "declaration": False,
            })
            continue

        ret_stmt = line.find("return local;")
        if ret_stmt != -1 and local_idx is not None:
            use_local_col = ret_stmt + len("return ") + 1
            occurrences.append({
                "symbol": local_idx,
                "line": line_no,
                "column": use_local_col,
                "declaration": False,
            })

    if fn_idx is None or param_idx is None or local_idx is None:
        return {"status": "unavailable", "reason": "syntax"}
    return {"status": "ok", "symbols": symbols, "occurrences": occurrences}


def deterministic_formatter(raw: bytes) -> dict[str, object]:
    """Bounded in-process formatter stub for overlay formatting requests."""
    digest = hashlib.sha256(raw).hexdigest()
    if deterministic_checker(raw) is not None:
        return {"status": "unavailable", "reason": "syntax", "source_sha256": digest}
    normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return {"status": "ok", "formatted": normalized, "source_sha256": digest}


@dataclass(frozen=True)
class OracleDocState:
    uri: str
    version: int
    generation: int
    model: OracleTextModel

    @property
    def identity(self) -> str:
        fields = [self.uri, self.version, self.generation, self.model.text]
        return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode("utf-8")).hexdigest()


class OracleOverlayModel:
    """Independent protocol state, overlay snapshot, and query projection oracle."""

    def __init__(self) -> None:
        self.initialized = True
        self.ready = True
        self.shutdown = False
        self.generation = 0
        self.open_docs: dict[str, OracleDocState] = {}
        self.received_versions: dict[str, int] = {}
        self.desynchronized: set[str] = set()
        self.next_id = 1

    def make_server(self) -> Server:
        server = Server(
            checker=deterministic_checker,
            inspector=deterministic_inspector,
            formatter=deterministic_formatter,
        )
        init_replies = server.handle({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"capabilities": {}},
        })
        if len(init_replies) != 1 or "result" not in init_replies[0]:
            raise ObservationMismatchError("Server initialize failed")
        server.handle({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        return server

    @staticmethod
    def _clear_reply(uri: str) -> dict[str, object]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": []},
        }

    def _expected_diagnostics_reply(self, state: OracleDocState) -> dict[str, object]:
        diag = deterministic_checker(state.model.raw)
        items: list[dict[str, object]] = []
        if diag is not None:
            line = cast("int", diag["line"])
            col = cast("int", diag["column"])
            pos = state.model.expected_diagnostic_position(line, col)
            if pos is None:
                raise ValueError("expected valid diagnostic position")
            items.append({
                "range": {"start": pos, "end": pos},
                "severity": 1,
                "source": "vela-pure-prototype",
                "code": diag["kind"],
                "message": str(diag["message"])[:4096],
                "data": {
                    "snapshot": state.identity,
                    "generation": state.generation,
                    "unqualified": True,
                },
            })
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": state.uri, "version": state.version, "diagnostics": items},
        }

    def verify_state(self, server: Server) -> None:
        if server.ready != self.ready or server.shutdown != self.shutdown:
            raise ObservationMismatchError(
                f"lifecycle mismatch: server=({server.ready}, {server.shutdown}), "
                f"expected=({self.ready}, {self.shutdown})"
            )
        if server.generation != self.generation:
            raise ObservationMismatchError(
                f"generation mismatch: actual={server.generation}, expected={self.generation}"
            )
        if set(server.documents) != set(self.open_docs):
            raise ObservationMismatchError(
                f"open document set mismatch: actual={sorted(server.documents)}, "
                f"expected={sorted(self.open_docs)}"
            )
        if server.desynchronized != self.desynchronized:
            raise ObservationMismatchError(
                f"desynchronized set mismatch: actual={sorted(server.desynchronized)}, "
                f"expected={sorted(self.desynchronized)}"
            )
        if server.received_versions != self.received_versions:
            raise ObservationMismatchError(
                f"received_versions mismatch: actual={server.received_versions!r}, "
                f"expected={self.received_versions!r}"
            )
        for uri, expected_state in self.open_docs.items():
            actual_snap = server.documents[uri]
            if (
                actual_snap.uri != uri
                or actual_snap.version != expected_state.version
                or actual_snap.generation != expected_state.generation
                or actual_snap.source != expected_state.model.raw
                or actual_snap.text != expected_state.model.text
                or actual_snap.identity != expected_state.identity
            ):
                raise ObservationMismatchError(
                    f"overlay snapshot mismatch for {uri}: "
                    f"actual=(v={actual_snap.version}, gen={actual_snap.generation}, text={actual_snap.text!r}), "
                    f"expected=(v={expected_state.version}, gen={expected_state.generation}, text={expected_state.model.text!r})"
                )

    def step(self, server: Server, action: dict[str, object]) -> None:
        kind = action["action"]
        uri = cast("str", action.get("uri", "untitled:overlay-a.vela"))

        if kind == "open":
            version = cast("int", action["version"])
            text = cast("str", action["text"])
            raw = text.encode("utf-8")
            if len(raw) > DEFAULT_MAX_DOCUMENT_BYTES:
                raise ValueError("generated document exceeds campaign byte cap")
            with contextlib.redirect_stderr(io.StringIO()):
                replies = server.handle({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {
                            "uri": uri,
                            "languageId": "vela",
                            "version": version,
                            "text": text,
                        }
                    },
                })
            if (
                uri in self.open_docs
                or len(self.open_docs) >= MAX_DOCUMENTS
                or not uri
                or len(uri.encode("utf-8")) > MAX_URI_BYTES
                or type(version) is not int
                or not (-2**31 <= version < 2**31)
            ):
                if uri in self.open_docs:
                    self.desynchronized.add(uri)
                    expected_replies: list[dict[str, object]] = [self._clear_reply(uri)]
                else:
                    expected_replies = []
            else:
                doc = OracleTextModel.from_text(text)
                self.generation += 1
                state = OracleDocState(uri, version, self.generation, doc)
                self.open_docs[uri] = state
                self.received_versions[uri] = version
                self.desynchronized.discard(uri)
                expected_replies = [self._expected_diagnostics_reply(state)]
            if replies != expected_replies:
                raise ObservationMismatchError(
                    f"didOpen replies mismatch: actual={replies!r}, expected={expected_replies!r}"
                )
            self.verify_state(server)
            return

        if kind == "change":
            version = cast("int", action["version"])
            changes = action["changes"]
            with contextlib.redirect_stderr(io.StringIO()):
                replies = server.handle({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didChange",
                    "params": {
                        "textDocument": {"uri": uri, "version": version},
                        "contentChanges": changes,
                    },
                })
            if uri not in self.open_docs:
                expected_replies = []
            else:
                old_state = self.open_docs[uri]
                last_received = self.received_versions[uri]
                if type(version) is not int or not (-2**31 <= version < 2**31) or version <= last_received:
                    self.desynchronized.add(uri)
                    expected_replies = [self._clear_reply(uri)]
                else:
                    self.received_versions[uri] = version
                    if (
                        not isinstance(changes, list)
                        or len(changes) > MAX_CHANGES
                        or (
                            uri in self.desynchronized
                            and (
                                not changes
                                or not isinstance(changes[0], dict)
                                or "range" in changes[0]
                            )
                        )
                    ):
                        self.desynchronized.add(uri)
                        expected_replies = [self._clear_reply(uri)]
                    else:
                        candidate: OracleTextModel | None = old_state.model
                        for ch in changes:
                            next_candidate = candidate.expected_apply_change(
                                ch, max_bytes=DEFAULT_MAX_DOCUMENT_BYTES
                            )
                            if next_candidate is None:
                                candidate = None
                                break
                            candidate = next_candidate
                        if candidate is None:
                            self.desynchronized.add(uri)
                            expected_replies = [self._clear_reply(uri)]
                        else:
                            self.generation += 1
                            new_state = OracleDocState(uri, version, self.generation, candidate)
                            self.open_docs[uri] = new_state
                            self.desynchronized.discard(uri)
                            expected_replies = [self._expected_diagnostics_reply(new_state)]
            if replies != expected_replies:
                raise ObservationMismatchError(
                    f"didChange replies mismatch: actual={replies!r}, expected={expected_replies!r}"
                )
            self.verify_state(server)
            return

        if kind == "save":
            with contextlib.redirect_stderr(io.StringIO()):
                replies = server.handle({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didSave",
                    "params": {"textDocument": {"uri": uri}},
                })
            if uri not in self.open_docs:
                expected_replies = []
            elif uri in self.desynchronized:
                expected_replies = [self._clear_reply(uri)]
            else:
                expected_replies = [self._expected_diagnostics_reply(self.open_docs[uri])]
            if replies != expected_replies:
                raise ObservationMismatchError(
                    f"didSave replies mismatch: actual={replies!r}, expected={expected_replies!r}"
                )
            self.verify_state(server)
            return

        if kind == "close":
            with contextlib.redirect_stderr(io.StringIO()):
                replies = server.handle({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didClose",
                    "params": {"textDocument": {"uri": uri}},
                })
            if uri not in self.open_docs:
                expected_replies = []
            else:
                del self.open_docs[uri]
                self.desynchronized.discard(uri)
                del self.received_versions[uri]
                self.generation += 1
                expected_replies = [self._clear_reply(uri)]
            if replies != expected_replies:
                raise ObservationMismatchError(
                    f"didClose replies mismatch: actual={replies!r}, expected={expected_replies!r}"
                )
            self.verify_state(server)
            return

        if kind == "invalidate":
            method = cast("str", action.get("method", "workspace/didChangeConfiguration"))
            replies = server.handle({"jsonrpc": "2.0", "method": method, "params": {}})
            expected_replies = []
            for open_uri, old_state in list(self.open_docs.items()):
                if open_uri in self.desynchronized:
                    continue
                self.generation += 1
                refreshed = OracleDocState(
                    open_uri, old_state.version, self.generation, old_state.model
                )
                self.open_docs[open_uri] = refreshed
                expected_replies.append(self._expected_diagnostics_reply(refreshed))
            if replies != expected_replies:
                raise ObservationMismatchError(
                    f"invalidation replies mismatch: actual={replies!r}, expected={expected_replies!r}"
                )
            self.verify_state(server)
            return

        if kind == "cancel":
            req_id = cast("int", action.get("id", 99))
            replies = server.handle({
                "jsonrpc": "2.0",
                "method": "$/cancelRequest",
                "params": {"id": req_id},
            })
            if replies != []:
                raise ObservationMismatchError(f"cancelRequest was not a synchronous no-op: {replies!r}")
            self.verify_state(server)
            return

        if kind == "query":
            self._step_query(server, uri, action)
            self.verify_state(server)
            return

        raise ValueError(f"unknown action kind: {kind!r}")

    def _expected_symbols_and_occurrences(
        self, doc: OracleTextModel
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]] | None:
        raw_inspect = deterministic_inspector(doc.raw)
        if raw_inspect.get("status") != "ok":
            return None
        symbols_out: list[dict[str, object]] = []
        for sym in cast("list[dict[str, object]]", raw_inspect["symbols"]):
            name = cast("str", sym["name"])
            line = cast("int", sym["line"])
            col = cast("int", sym["column"])
            start = doc.expected_diagnostic_position(line, col)
            end = doc.expected_diagnostic_position(line, col + len(name))
            if start is None or end is None:
                raise ValueError("expected valid symbol positions")
            symbols_out.append({
                "name": name,
                "kind": sym["kind"],
                "detail": sym["detail"],
                "start": (start["line"], start["character"]),
                "end": (end["line"], end["character"]),
                "type_hint": ": Nat" if sym["kind"] == "variable" else None,
            })
        occurrences_out: list[dict[str, object]] = []
        for occ in cast("list[dict[str, object]]", raw_inspect["occurrences"]):
            sym_idx = cast("int", occ["symbol"])
            name = cast("str", symbols_out[sym_idx]["name"])
            line = cast("int", occ["line"])
            col = cast("int", occ["column"])
            start = doc.expected_diagnostic_position(line, col)
            end = doc.expected_diagnostic_position(line, col + len(name))
            if start is None or end is None:
                raise ValueError("expected valid occurrence positions")
            occurrences_out.append({
                "symbol": sym_idx,
                "start": (start["line"], start["character"]),
                "end": (end["line"], end["character"]),
                "declaration": occ["declaration"],
            })
        return symbols_out, occurrences_out

    def _step_query(self, server: Server, uri: str, action: dict[str, object]) -> None:
        method = cast("str", action["method"])
        req_id = self.next_id
        self.next_id += 1
        line = cast("int", action.get("line", 0))
        character = cast("int", action.get("character", 0))
        include_decl = bool(action.get("include_declaration", True))

        if method in {"textDocument/documentSymbol", "textDocument/semanticTokens/full"}:
            params: dict[str, object] = {"textDocument": {"uri": uri}}
        elif method == "textDocument/formatting":
            params = {
                "textDocument": {"uri": uri},
                "options": {"tabSize": 4, "insertSpaces": True},
            }
        elif method == "textDocument/inlayHint":
            end_line = cast("int", action.get("end_line", line))
            end_char = cast("int", action.get("end_character", character))
            params = {
                "textDocument": {"uri": uri},
                "range": {
                    "start": {"line": line, "character": character},
                    "end": {"line": end_line, "character": end_char},
                },
            }
        elif method == "textDocument/references":
            params = {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": include_decl},
            }
        else:
            params = {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            }

        replies = server.handle({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        if len(replies) != 1 or replies[0].get("id") != req_id:
            raise ObservationMismatchError(f"query {method} lost request correlation: {replies!r}")
        reply = replies[0]

        if uri not in self.open_docs:
            err = cast("dict[str, object]", reply.get("error", {}))
            if err.get("code") != -32602:
                raise ObservationMismatchError(
                    f"closed document query {method} did not refuse with -32602: {reply!r}"
                )
            return

        if uri in self.desynchronized:
            err = cast("dict[str, object]", reply.get("error", {}))
            if err.get("code") != -32801:
                raise ObservationMismatchError(
                    f"desynchronized document query {method} did not refuse with -32801: {reply!r}"
                )
            return

        doc = self.open_docs[uri].model
        clamped_pos: tuple[int, int] | None = None
        clamped_range: tuple[tuple[int, int], tuple[int, int]] | None = None

        if method in {"textDocument/hover", "textDocument/definition", "textDocument/references"}:
            b_off = doc.expected_position_byte_offset(line, character)
            if b_off is None:
                err = cast("dict[str, object]", reply.get("error", {}))
                if err.get("code") != -32602:
                    raise ObservationMismatchError(
                        f"invalid coordinate query {method} at ({line}, {character}) did not refuse: {reply!r}"
                    )
                return
            conv = doc.expected_byte_position(b_off)
            if conv is None:
                raise ValueError("expected valid byte position")
            clamped_pos = (conv["line"], conv["character"])

        if method == "textDocument/inlayHint":
            end_line = cast("int", action.get("end_line", line))
            end_char = cast("int", action.get("end_character", character))
            if (line, character) > (end_line, end_char):
                err = cast("dict[str, object]", reply.get("error", {}))
                if err.get("code") != -32602:
                    raise ObservationMismatchError(
                        f"reversed inlayHint range did not refuse with -32602: {reply!r}"
                    )
                return
            s_off = doc.expected_position_byte_offset(line, character)
            e_off = doc.expected_position_byte_offset(end_line, end_char)
            if s_off is None or e_off is None:
                err = cast("dict[str, object]", reply.get("error", {}))
                if err.get("code") != -32602:
                    raise ObservationMismatchError(
                        f"invalid inlayHint range did not refuse with -32602: {reply!r}"
                    )
                return
            s_conv = doc.expected_byte_position(s_off)
            e_conv = doc.expected_byte_position(e_off)
            if s_conv is None or e_conv is None:
                raise ValueError("expected valid inlayHint byte positions")
            clamped_range = (
                (s_conv["line"], s_conv["character"]),
                (e_conv["line"], e_conv["character"]),
            )

        if "result" not in reply:
            raise ObservationMismatchError(f"synchronized query {method} failed unexpectedly: {reply!r}")

        actual_result = reply["result"]
        expected_result = self._compute_expected_query_result(
            uri, doc, method, clamped_pos, include_decl, clamped_range
        )
        if actual_result != expected_result:
            raise ObservationMismatchError(
                f"query {method} mismatch on {uri}: actual={actual_result!r}, expected={expected_result!r}"
            )

    def _compute_expected_query_result(
        self,
        uri: str,
        doc: OracleTextModel,
        method: str,
        clamped_pos: tuple[int, int] | None,
        include_decl: bool,
        clamped_range: tuple[tuple[int, int], tuple[int, int]] | None,
    ) -> object:
        if method == "textDocument/formatting":
            fmt_raw = deterministic_formatter(doc.raw)
            if fmt_raw.get("status") != "ok":
                return []
            formatted_text = cast("str", fmt_raw["formatted"])
            if formatted_text == doc.text:
                return []
            return [{"range": doc.expected_full_range(), "newText": formatted_text}]

        projected = self._expected_symbols_and_occurrences(doc)
        if projected is None:
            if method in {
                "textDocument/references",
                "textDocument/documentSymbol",
                "textDocument/inlayHint",
            }:
                return []
            if method == "textDocument/semanticTokens/full":
                return {"data": []}
            return None

        symbols, occurrences = projected
        if method == "textDocument/documentSymbol":
            kinds = {"function": 12, "constant": 14, "parameter": 13, "variable": 13}
            return [
                {
                    "name": sym["name"],
                    "kind": kinds[cast("str", sym["kind"])],
                    "location": {
                        "uri": uri,
                        "range": {
                            "start": {
                                "line": cast("tuple[int, int]", sym["start"])[0],
                                "character": cast("tuple[int, int]", sym["start"])[1],
                            },
                            "end": {
                                "line": cast("tuple[int, int]", sym["end"])[0],
                                "character": cast("tuple[int, int]", sym["end"])[1],
                            },
                        },
                    },
                }
                for sym in symbols
            ]

        if method == "textDocument/semanticTokens/full":
            data: list[int] = []
            prev_line, prev_start = 0, 0
            for occ in occurrences:
                sym = symbols[cast("int", occ["symbol"])]
                occ_start = cast("tuple[int, int]", occ["start"])
                occ_end = cast("tuple[int, int]", occ["end"])
                tok_type = {"function": 0, "parameter": 1, "variable": 2, "constant": 2}[
                    cast("str", sym["kind"])
                ]
                modifiers = int(bool(occ["declaration"])) | (0 if sym["kind"] == "function" else 2)
                data.extend((
                    occ_start[0] - prev_line,
                    occ_start[1] - prev_start if occ_start[0] == prev_line else occ_start[1],
                    occ_end[1] - occ_start[1],
                    tok_type,
                    modifiers,
                ))
                prev_line, prev_start = occ_start
            return {"data": data}

        if method == "textDocument/inlayHint":
            if clamped_range is None:
                raise ValueError("expected clamped_range for inlayHint")
            req_start, req_end = clamped_range
            return [
                {
                    "position": {
                        "line": cast("tuple[int, int]", sym["end"])[0],
                        "character": cast("tuple[int, int]", sym["end"])[1],
                    },
                    "label": sym["type_hint"],
                    "kind": 1,
                }
                for sym in symbols
                if sym["type_hint"] is not None
                and req_start <= cast("tuple[int, int]", sym["start"])
                and cast("tuple[int, int]", sym["end"]) <= req_end
            ]

        if clamped_pos is None:
            raise ValueError("expected clamped_pos for positional query")
        selected = next(
            (
                occ
                for occ in occurrences
                if cast("tuple[int, int]", occ["start"]) <= clamped_pos < cast("tuple[int, int]", occ["end"])
            ),
            None,
        )
        if selected is None:
            return [] if method == "textDocument/references" else None

        sym = symbols[cast("int", selected["symbol"])]
        sel_start = cast("tuple[int, int]", selected["start"])
        sel_end = cast("tuple[int, int]", selected["end"])
        sym_start = cast("tuple[int, int]", sym["start"])
        sym_end = cast("tuple[int, int]", sym["end"])

        if method == "textDocument/hover":
            return {
                "contents": {
                    "kind": "plaintext",
                    "value": f"{sym['detail']}\nVela pure prototype (unqualified)",
                },
                "range": {
                    "start": {"line": sel_start[0], "character": sel_start[1]},
                    "end": {"line": sel_end[0], "character": sel_end[1]},
                },
            }
        if method == "textDocument/definition":
            return {
                "uri": uri,
                "range": {
                    "start": {"line": sym_start[0], "character": sym_start[1]},
                    "end": {"line": sym_end[0], "character": sym_end[1]},
                },
            }
        return [
            {
                "uri": uri,
                "range": {
                    "start": {
                        "line": cast("tuple[int, int]", occ["start"])[0],
                        "character": cast("tuple[int, int]", occ["start"])[1],
                    },
                    "end": {
                        "line": cast("tuple[int, int]", occ["end"])[0],
                        "character": cast("tuple[int, int]", occ["end"])[1],
                    },
                },
            }
            for occ in occurrences
            if occ["symbol"] == selected["symbol"] and (include_decl or not occ["declaration"])
        ]


def replay_overlay_trace(actions: list[dict[str, object]]) -> None:
    """Replay a bounded sequence of overlay and request actions against `OracleOverlayModel`."""
    if len(actions) > DEFAULT_STEP_COUNT:
        raise ValueError(f"trace exceeds {DEFAULT_STEP_COUNT} steps")
    model = OracleOverlayModel()
    server = model.make_server()
    for action in actions:
        model.step(server, action)


@dataclass(frozen=True)
class FormatTemplate:
    """Small supported pure-Vela template with independently known canonical text and facts."""

    module_name: str
    header_comment: str | None
    doc_comment: str | None
    detach_doc: bool
    const_decl: tuple[str, str, str] | None
    fn_name: str
    param_name: str
    local_name: str
    operator: str
    literal: str
    inline_comment: str | None
    newline: str
    indent_spaces: int
    inner_spaces: int

    def raw_source(self) -> bytes:
        pad = " " * self.indent_spaces
        gap = " " * max(1, self.inner_spaces)
        parts: list[str] = []
        if self.header_comment is not None:
            parts.append(f"{pad}{self.header_comment}")
        parts.append(f"{pad}module{gap}{self.module_name} ;")
        if self.const_decl is not None:
            c_type, c_name, c_val = self.const_decl
            parts.append(f"{pad}public{gap}const{gap}{c_type}{gap}{c_name}{gap}={gap}{c_val} ;")
        if self.doc_comment is not None:
            parts.append(f"{pad}{self.doc_comment}")
            if self.detach_doc:
                parts.append("")
        inline = f" {self.inline_comment}" if self.inline_comment is not None else ""
        parts.append(
            f"{pad}public{gap}Nat{gap}{self.fn_name} ( Nat{gap}{self.param_name} ){gap}{{"
        )
        parts.append(
            f"{pad}  let{gap}{self.local_name}{gap}={gap}{self.param_name}{gap}{self.operator}{gap}{self.literal} ;{inline}"
        )
        parts.append(f"{pad}  return{gap}{self.local_name} ;")
        parts.append(f"{pad}}}")
        return (self.newline.join(parts) + self.newline).encode("utf-8")

    def expected_canonical(self) -> bytes:
        lines: list[str] = []
        if self.header_comment is not None:
            lines.append(self.header_comment)
        lines.append(f"module {self.module_name};")
        if self.const_decl is not None:
            c_type, c_name, c_val = self.const_decl
            lines.append("")
            lines.append(f"public const {c_type} {c_name} = {c_val};")
        lines.append("")
        if self.doc_comment is not None:
            lines.append(self.doc_comment)
            if self.detach_doc:
                lines.append("")
        inline = f" {self.inline_comment}" if self.inline_comment is not None else ""
        lines.append(f"public Nat {self.fn_name}(Nat {self.param_name})")
        lines.append("{")
        lines.append(f"    let {self.local_name} = {self.param_name} {self.operator} {self.literal};{inline}")
        lines.append(f"    return {self.local_name};")
        lines.append("}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def expected_tokens(self) -> tuple[tuple[str, str], ...]:
        tokens: list[tuple[str, str]] = [("keyword", "module"), ("name", self.module_name), ("symbol", ";")]
        if self.const_decl is not None:
            c_type, c_name, c_val = self.const_decl
            val_kind = "keyword" if c_val in {"true", "false"} else "decimal"
            tokens.extend((
                ("keyword", "public"),
                ("keyword", "const"),
                ("keyword", c_type),
                ("name", c_name),
                ("symbol", "="),
                (val_kind, c_val),
                ("symbol", ";"),
            ))
        tokens.extend((
            ("keyword", "public"),
            ("keyword", "Nat"),
            ("name", self.fn_name),
            ("symbol", "("),
            ("keyword", "Nat"),
            ("name", self.param_name),
            ("symbol", ")"),
            ("symbol", "{"),
            ("keyword", "let"),
            ("name", self.local_name),
            ("symbol", "="),
            ("name", self.param_name),
            ("symbol", self.operator),
            ("decimal", self.literal),
            ("symbol", ";"),
            ("keyword", "return"),
            ("name", self.local_name),
            ("symbol", ";"),
            ("symbol", "}"),
            ("eof", "end of file"),
        ))
        return tuple(tokens)

    def expected_documentation(self) -> str | None:
        if self.doc_comment is None or self.detach_doc:
            return None
        return self.doc_comment.removeprefix("///").strip(" ")


def verify_format_template(template: FormatTemplate) -> None:
    """Check `format_source` and `formatting_edits` against `FormatTemplate`'s independent oracle."""
    raw = template.raw_source()
    if len(raw) > DEFAULT_MAX_DOCUMENT_BYTES:
        raise ValueError(f"template exceeds {DEFAULT_MAX_DOCUMENT_BYTES} bytes")
    caller_buffer = bytearray(raw)
    formatted = authoring.format_source(bytes(caller_buffer))
    if bytes(caller_buffer) != raw:
        raise ObservationMismatchError("format_source mutated caller-owned buffer")

    expected = template.expected_canonical()
    if formatted != expected:
        raise ObservationMismatchError(
            f"format_source output disagrees with template oracle:\n"
            f"actual:\n{formatted.decode('utf-8')}\nexpected:\n{expected.decode('utf-8')}"
        )

    reformatted = authoring.format_source(formatted)
    if reformatted != formatted:
        raise ObservationMismatchError("format_source is not idempotent")

    actual_tokens = tuple((tok.kind, tok.text) for tok in vela._tokens(formatted))
    if actual_tokens != template.expected_tokens():
        raise ObservationMismatchError(
            f"formatted token sequence drifted: actual={actual_tokens!r}, "
            f"expected={template.expected_tokens()!r}"
        )

    facts = vela.inspect_source(formatted)
    symbols = cast("list[dict[str, object]]", facts["symbols"])
    fn_symbol = next((sym for sym in symbols if sym.get("name") == template.fn_name), None)
    if fn_symbol is None:
        raise ObservationMismatchError(f"missing function symbol {template.fn_name!r} after formatting")
    doc_record = fn_symbol.get("documentation")
    actual_doc = cast("dict[str, object]", doc_record).get("text") if isinstance(doc_record, dict) else None
    expected_doc = template.expected_documentation()
    if actual_doc != expected_doc:
        raise ObservationMismatchError(
            f"documentation attachment mismatch on {template.fn_name}: "
            f"actual={actual_doc!r}, expected={expected_doc!r}"
        )

    raw_text = raw.decode("utf-8")
    snapshot = SourceSnapshot("untitled:format-template.vela", 1, raw_text, 1)
    worker_payload: dict[str, object] = {
        "status": "ok",
        "formatted": formatted.decode("utf-8"),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    }
    edits = formatting_edits(snapshot, worker_payload)
    if raw == expected:
        if edits != []:
            raise ObservationMismatchError(f"canonical source produced non-empty edits: {edits!r}")
    else:
        oracle_doc = OracleTextModel.from_text(raw_text)
        expected_edits = [{"range": oracle_doc.expected_full_range(), "newText": expected.decode("utf-8")}]
        if edits != expected_edits:
            raise ObservationMismatchError(
                f"formatting_edits mismatch: actual={edits!r}, expected={expected_edits!r}"
            )
        applied = oracle_doc.expected_apply_change(
            {"range": edits[0]["range"], "text": edits[0]["newText"]}
        )
        if applied is None or applied.raw != expected:
            raise ObservationMismatchError("applying formatting_edits did not produce canonical source")


@contextlib.contextmanager
def seeded_fault_context(fault_name: str) -> Generator[None]:
    """Activate one of the seeded defects (or a synthetic stillborn mutant for control tests)."""
    if fault_name == "stillborn-mutant":
        raise RuntimeError("seeded mutant failed startup before observations")

    if fault_name == "utf16-codepoint-confusion":
        def _buggy_diagnostic_position(self: SourceSnapshot, line: int, column: int) -> dict[str, int]:
            lines = self.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            if not 1 <= line <= len(lines) or not 1 <= column <= len(lines[line - 1]) + 1:
                raise ValueError("producer diagnostic outside source")
            # Defect: counts Unicode code points instead of UTF-16 code units.
            return {"line": line - 1, "character": len(lines[line - 1][: column - 1])}

        with patch.object(SourceSnapshot, "diagnostic_position", _buggy_diagnostic_position):
            yield
        return

    if fault_name == "edit-against-original-document":
        def _buggy_changed_snapshot(
            self: Server, old: SourceSnapshot, version: int, changes: object
        ) -> SourceSnapshot:
            if not isinstance(changes, list) or len(changes) > MAX_CHANGES:
                raise ValueError("expected at most 64 ordered content changes")
            if old.uri in self.desynchronized and (
                not changes or not isinstance(changes[0], dict) or "range" in changes[0]
            ):
                raise ValueError("a complete replacement is required to restore synchronization")
            candidate = old
            for value in changes:
                if type(value) is not dict or type(value.get("text")) is not str:
                    raise ValueError("invalid change")
                text = cast("str", value["text"])
                if "range" in value:
                    span = value.get("range")
                    if not isinstance(span, dict):
                        raise ValueError("invalid range")
                    start = span.get("start")
                    end = span.get("end")
                    if not isinstance(start, dict) or not isinstance(end, dict):
                        raise ValueError("invalid positions")
                    s_line, s_char = start.get("line"), start.get("character")
                    e_line, e_char = end.get("line"), end.get("character")
                    if (
                        type(s_line) is not int
                        or type(s_char) is not int
                        or type(e_line) is not int
                        or type(e_char) is not int
                        or (s_line, s_char) > (e_line, e_char)
                    ):
                        raise ValueError("invalid or reversed range")
                    # Defect: resolves offsets and slices against `old` instead of `candidate`.
                    first = old.position_byte_offset(s_line, s_char)
                    last = old.position_byte_offset(e_line, e_char)
                    source = old.source
                    text = (source[:first] + text.encode("utf-8") + source[last:]).decode("utf-8")
                candidate = SourceSnapshot(old.uri, version, text, self.generation + 1)
            return self._snapshot(old.uri, version, candidate.text)

        with patch.object(Server, "_changed_snapshot", _buggy_changed_snapshot):
            yield
        return

    if fault_name == "publish-early-edit-before-rollback":
        def _buggy_early_publish_snapshot(
            self: Server, old: SourceSnapshot, version: int, changes: object
        ) -> SourceSnapshot:
            if not isinstance(changes, list) or len(changes) > MAX_CHANGES:
                raise ValueError("expected at most 64 ordered content changes")
            if old.uri in self.desynchronized and (
                not changes or not isinstance(changes[0], dict) or "range" in changes[0]
            ):
                raise ValueError("a complete replacement is required to restore synchronization")
            candidate = old
            for value in changes:
                if type(value) is not dict or type(value.get("text")) is not str:
                    raise ValueError("invalid change")
                text = cast("str", value["text"])
                if "range" in value:
                    span = value.get("range")
                    if not isinstance(span, dict):
                        raise ValueError("invalid range")
                    start = span.get("start")
                    end = span.get("end")
                    if not isinstance(start, dict) or not isinstance(end, dict):
                        raise ValueError("invalid positions")
                    s_line, s_char = start.get("line"), start.get("character")
                    e_line, e_char = end.get("line"), end.get("character")
                    if (
                        type(s_line) is not int
                        or type(s_char) is not int
                        or type(e_line) is not int
                        or type(e_char) is not int
                        or (s_line, s_char) > (e_line, e_char)
                    ):
                        raise ValueError("invalid or reversed range")
                    first = candidate.position_byte_offset(s_line, s_char)
                    last = candidate.position_byte_offset(e_line, e_char)
                    source = candidate.source
                    text = (source[:first] + text.encode("utf-8") + source[last:]).decode("utf-8")
                # Held-out defect: publishes each intermediate edit to `self.documents` and
                # increments `self.generation` before checking later edits in the batch.
                candidate = self._snapshot(old.uri, version, text)
                self.documents[old.uri] = candidate
            return candidate

        with patch.object(Server, "_changed_snapshot", _buggy_early_publish_snapshot):
            yield
        return

    raise ValueError(f"unknown fault name: {fault_name!r}")


NONMINIMAL_FAULT_TRACES: dict[str, dict[str, object]] = {
    "utf16-codepoint-confusion": {
        "kind": "coordinate",
        "uri": "untitled:unicode-shrink.vela",
        "version": 1,
        "lines": [
            "// header line 0 without supplementary chars\n",
            "// header line 1 padding\r\n",
            "// header line 2 padding\n",
            "// 😀 supplementary line with trailing tokens\n",
            "module Shrink;\n",
            "public Nat Entry(Nat input) {\n",
            "  return input;\n",
            "}\n",
        ],
        "queries": [(0, 0), (1, 2), (2, 4), (3, 5), (4, 0), (5, 6)],
        "byte_queries": [0, 3, 10],
        "diagnostic_sites": [(1, 1), (2, 3), (4, 6), (6, 4)],
    },
    "edit-against-original-document": {
        "kind": "overlay",
        "actions": [
            {
                "action": "open",
                "uri": "untitled:doc-a.vela",
                "version": 1,
                "text": "// pad 0\n// pad 1\nmodule Overlay;\npublic Nat Entry(Nat input) {\n  let local = input;\n  return local;\n}\n",
            },
            {"action": "save", "uri": "untitled:doc-a.vela"},
            {"action": "cancel", "id": 11},
            {"action": "invalidate", "method": "workspace/didChangeConfiguration"},
            {"action": "query", "uri": "untitled:doc-a.vela", "method": "textDocument/documentSymbol"},
            {
                "action": "change",
                "uri": "untitled:doc-a.vela",
                "version": 2,
                "changes": [
                    {
                        "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                        "text": "// first\n",
                    },
                    {
                        "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 0}},
                        "text": "// second\n",
                    },
                ],
            },
            {"action": "save", "uri": "untitled:doc-a.vela"},
            {"action": "cancel", "id": 12},
        ],
    },
    "publish-early-edit-before-rollback": {
        "kind": "overlay",
        "actions": [
            {
                "action": "open",
                "uri": "untitled:doc-a.vela",
                "version": 1,
                "text": "// pad 0\n// pad 1\nmodule Overlay;\npublic Nat Entry(Nat input) {\n  let local = input;\n  return local;\n}\n",
            },
            {"action": "save", "uri": "untitled:doc-a.vela"},
            {"action": "cancel", "id": 21},
            {"action": "invalidate", "method": "workspace/didChangeWatchedFiles"},
            {"action": "query", "uri": "untitled:doc-a.vela", "method": "textDocument/hover", "line": 3, "character": 11},
            {
                "action": "change",
                "uri": "untitled:doc-a.vela",
                "version": 2,
                "changes": [
                    {
                        "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                        "text": "// early valid edit\n",
                    },
                    {
                        "range": {"start": {"line": 99, "character": 0}, "end": {"line": 99, "character": 1}},
                        "text": "invalid range",
                    },
                ],
            },
            {"action": "cancel", "id": 22},
            {"action": "query", "uri": "untitled:doc-a.vela", "method": "textDocument/documentSymbol"},
        ],
    },
}


def case_complexity(case_data: dict[str, object]) -> int:
    """Measure explicit counterexample complexity in steps and serialized items."""
    if case_data.get("kind") == "coordinate":
        lines = cast("list[str]", case_data["lines"])
        queries = cast("list[tuple[object, object]]", case_data["queries"])
        b_queries = cast("list[object]", case_data.get("byte_queries", []))
        sites = cast("list[tuple[int, int]]", case_data["diagnostic_sites"])
        return len(lines) + len(queries) + len(b_queries) + len(sites)
    actions = cast("list[dict[str, object]]", case_data["actions"])
    return len(actions)


def execute_explicit_case(case_data: dict[str, object]) -> None:
    """Run an explicit JSON-serializable coordinate or overlay case against the independent oracle."""
    if case_data.get("kind") == "coordinate":
        uri = cast("str", case_data.get("uri", "untitled:coord.vela"))
        version = cast("int", case_data.get("version", 1))
        lines = cast("list[str]", case_data["lines"])
        text = "".join(lines)
        queries = [
            (item[0], item[1])
            for item in cast("list[list[object] | tuple[object, object]]", case_data["queries"])
        ]
        byte_queries = list(cast("list[object]", case_data.get("byte_queries", [])))
        sites = [
            (int(cast("int", item[0])), int(cast("int", item[1])))
            for item in cast("list[list[object] | tuple[object, object]]", case_data["diagnostic_sites"])
        ]
        verify_coordinate_observations(uri, version, text, queries, byte_queries, sites)
        return
    if case_data.get("kind") == "overlay":
        actions = cast("list[dict[str, object]]", case_data["actions"])
        replay_overlay_trace(actions)
        return
    raise ValueError(f"unsupported explicit case kind: {case_data.get('kind')!r}")


def shrink_explicit_case(
    fault_name: str, initial_case: dict[str, object]
) -> tuple[dict[str, object], str]:
    """Deterministically shrink a failing explicit case while preserving its observation kind."""
    with seeded_fault_context(fault_name):
        try:
            execute_explicit_case(initial_case)
        except ObservationMismatchError as exc:
            target_prefix = str(exc).split(":", 1)[0]
        else:
            raise ValueError(f"initial case did not fail under {fault_name}")

        current: dict[str, object] = cast("dict[str, object]", json.loads(json.dumps(initial_case)))

        def still_fails(candidate: dict[str, object]) -> bool:
            try:
                execute_explicit_case(candidate)
            except ObservationMismatchError as err:
                return str(err).startswith(target_prefix)
            return False

        if current.get("kind") == "coordinate":
            for key in ("lines", "queries", "byte_queries", "diagnostic_sites"):
                items = list(cast("list[object]", current.get(key, [])))
                idx = 0
                while idx < len(items) and (len(items) > 1 or key == "byte_queries"):
                    trial_items = items[:idx] + items[idx + 1 :]
                    trial: dict[str, object] = dict(current)
                    trial[key] = trial_items
                    if key == "lines":
                        trial["queries"] = [(0, 5)]
                        trial["diagnostic_sites"] = [(1, 6)]
                    if still_fails(trial):
                        items = trial_items
                        current = trial
                    else:
                        idx += 1
        elif current.get("kind") == "overlay":
            actions = list(cast("list[dict[str, object]]", current["actions"]))
            idx = 0
            while idx < len(actions) and len(actions) > 1:
                trial_actions = actions[:idx] + actions[idx + 1 :]
                trial_overlay: dict[str, object] = {"kind": "overlay", "actions": trial_actions}
                if still_fails(trial_overlay):
                    actions = trial_actions
                    current = trial_overlay
                else:
                    idx += 1

        try:
            execute_explicit_case(current)
        except ObservationMismatchError as final_err:
            return current, str(final_err)
        raise ValueError(f"shrunk case lost failure under {fault_name}")


def _extract_observation_error(exc: BaseException) -> ObservationMismatchError | None:
    if isinstance(exc, ObservationMismatchError):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            found = _extract_observation_error(sub)
            if found is not None:
                return found
    return None


def evaluate_seeded_fault(
    fault_name: str, runner: Callable[[], None] | None = None
) -> dict[str, object]:
    """Classify a seeded defect as `stillborn`, `killed`, or `survived`, and verify shrinking/replay."""
    trace = NONMINIMAL_FAULT_TRACES.get(fault_name)
    active_runner = runner or (lambda: execute_explicit_case(trace) if trace is not None else None)
    try:
        with seeded_fault_context(fault_name):
            try:
                active_runner()
            except BaseException as caught:
                obs_err = _extract_observation_error(caught)
                if obs_err is None:
                    return {
                        "fault": fault_name,
                        "held_out": fault_name == HELD_OUT_FAULT,
                        "status": "stillborn",
                        "reason": f"{type(caught).__name__}: {caught}",
                    }
                observation = str(obs_err)
            else:
                return {
                    "fault": fault_name,
                    "held_out": fault_name == HELD_OUT_FAULT,
                    "status": "survived",
                    "reason": "no ObservationMismatchError raised",
                }
    except Exception as startup_error:
        return {
            "fault": fault_name,
            "held_out": fault_name == HELD_OUT_FAULT,
            "status": "stillborn",
            "reason": f"{type(startup_error).__name__}: {startup_error}",
        }

    if trace is None:
        return {
            "fault": fault_name,
            "held_out": fault_name == HELD_OUT_FAULT,
            "status": "killed",
            "observation": observation,
        }

    initial_size = case_complexity(trace)
    shrunk_case, shrunk_obs = shrink_explicit_case(fault_name, trace)
    shrunk_size = case_complexity(shrunk_case)
    if shrunk_size >= initial_size:
        raise ValueError(
            f"seeded fault {fault_name} did not shrink to a strictly smaller trace "
            f"({shrunk_size} >= {initial_size})"
        )

    with seeded_fault_context(fault_name):
        try:
            execute_explicit_case(shrunk_case)
        except ObservationMismatchError as replay_err:
            replay_obs = str(replay_err)
        else:
            raise ValueError(f"shrunk explicit case failed to replay under {fault_name}")

    if replay_obs != shrunk_obs:
        raise ValueError(f"replay observation drifted for {fault_name}: {replay_obs!r} != {shrunk_obs!r}")

    return {
        "fault": fault_name,
        "held_out": fault_name == HELD_OUT_FAULT,
        "status": "killed",
        "generator_observation": observation,
        "initial_complexity": initial_size,
        "shrunk_complexity": shrunk_size,
        "observation": replay_obs,
        "shrunk_case": shrunk_case,
    }


def verify_installed_closure() -> dict[str, object]:
    """Verify the isolated environment's Python minor version, package versions, and license/native hashes."""
    if sys.version_info[:2] != (3, 14):
        raise ValueError(f"expected Python 3.14, got {sys.version.split()[0]}")
    packages: dict[str, dict[str, object]] = {}
    native_sha256: str | None = None
    for pkg_name, expected_version in CANDIDATE_VERSIONS.items():
        dist = importlib_metadata.distribution(pkg_name)
        if dist.version != expected_version:
            raise ValueError(f"expected {pkg_name}=={expected_version}, got {dist.version}")
        lic_rel, expected_lic_sha = EXPECTED_LICENSE_SHA256[pkg_name]
        lic_path = Path(str(dist.locate_file(lic_rel)))
        actual_lic_sha = hashlib.sha256(lic_path.read_bytes()).hexdigest()
        if actual_lic_sha != expected_lic_sha:
            raise ValueError(
                f"license SHA-256 mismatch for {pkg_name} ({lic_rel}): "
                f"{actual_lic_sha} != {expected_lic_sha}"
            )
        if pkg_name == "hypothesis":
            for entry in dist.files or []:
                rel = str(entry).replace("\\", "/")
                if rel.startswith("hypothesis/_native") and rel.endswith((".pyd", ".so")):
                    bin_path = Path(str(dist.locate_file(entry)))
                    native_sha256 = hashlib.sha256(bin_path.read_bytes()).hexdigest()
                    if native_sha256 not in EXPECTED_NATIVE_SHA256:
                        raise ValueError(
                            f"unrecognized hypothesis/_native binary SHA-256 on {platform.platform()}: "
                            f"{native_sha256}"
                        )
        packages[pkg_name] = {
            "version": dist.version,
            "license_path": lic_rel,
            "license_sha256": actual_lic_sha,
        }
    if native_sha256 is None:
        raise ValueError("hypothesis/_native extension binary not found in isolated distribution")
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": packages,
        "hypothesis_native_sha256": native_sha256,
    }


def run_hypothesis_campaign_in_process(
    *,
    seed: int = DEFAULT_SEED,
    max_examples: int = DEFAULT_MAX_EXAMPLES,
    step_count: int = DEFAULT_STEP_COUNT,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Execute the 4 Hypothesis property/stateful subjects and 3 fault controls inside the isolated venv."""
    start_wall = time.monotonic()
    closure = verify_installed_closure()
    hyp = importlib.import_module("hypothesis")
    st = importlib.import_module("hypothesis.strategies")
    stateful = importlib.import_module("hypothesis.stateful")

    settings_factory = hyp.settings
    given = hyp.given
    seed_decorator = hyp.seed
    health_check = hyp.HealthCheck
    state_machine_base = stateful.RuleBasedStateMachine
    initialize = stateful.initialize
    rule = stateful.rule
    invariant = stateful.invariant

    campaign_settings = settings_factory(
        max_examples=max_examples,
        stateful_step_count=step_count,
        database=None,
        derandomize=True,
        deadline=None,
        suppress_health_check=list(health_check),
    )

    # Subject 1: Source coordinates
    line_piece_strategy = st.sampled_from([
        "// ascii line",
        "// 😀 supplementary",
        "// 🚀✨ two supplementary",
        "module Coord;",
        "public Nat Entry(Nat input) {",
        "  let local = input;",
        "  return local;",
        "}",
    ])
    newline_strategy = st.sampled_from(["\n", "\r\n", "\r"])
    coord_case_strategy = st.fixed_dictionaries({
        "kind": st.just("coordinate"),
        "uri": st.just("untitled:hyp-coord.vela"),
        "version": st.integers(min_value=1, max_value=16),
        "lines": st.lists(
            st.builds(lambda body, nl: body + nl, line_piece_strategy, newline_strategy),
            min_size=1,
            max_size=8,
        ),
        "queries": st.lists(
            st.tuples(st.integers(min_value=-1, max_value=9), st.integers(min_value=-1, max_value=24)),
            min_size=4,
            max_size=12,
        ),
        "byte_queries": st.lists(st.integers(min_value=-1, max_value=64), min_size=2, max_size=8),
        "diagnostic_sites": st.lists(
            st.tuples(st.integers(min_value=0, max_value=10), st.integers(min_value=0, max_value=24)),
            min_size=3,
            max_size=8,
        ),
    })

    coord_runs = 0

    def _check_source_coordinates(case_data: dict[str, object]) -> None:
        nonlocal coord_runs
        coord_runs += 1
        execute_explicit_case(case_data)

    check_source_coordinates = cast(
        "Callable[[], None]",
        seed_decorator(seed)(campaign_settings(given(case_data=coord_case_strategy)(_check_source_coordinates))),
    )
    check_source_coordinates()

    # Subject 2 & 3: Synchronous overlays and supported requests (stateful + trace property)
    valid_doc_strategy = st.builds(
        lambda header, nl: nl.join([
            header,
            "module Overlay;",
            "public Nat Entry(Nat input) {",
            "  let local = input;",
            "  return local;",
            "}",
        ]) + nl,
        st.sampled_from(["// 😀 header", "// clean header", "// SYNTAX_ERROR line"]),
        newline_strategy,
    )

    change_item_strategy = st.one_of(
        st.fixed_dictionaries({"text": valid_doc_strategy}),
        st.fixed_dictionaries({
            "range": st.fixed_dictionaries({
                "start": st.fixed_dictionaries({"line": st.just(0), "character": st.just(0)}),
                "end": st.fixed_dictionaries({"line": st.just(0), "character": st.just(0)}),
            }),
            "text": st.sampled_from(["// edit 😀\n", "// edit ascii\r\n", "// SYNTAX_ERROR\n"]),
        }),
        st.fixed_dictionaries({
            "range": st.fixed_dictionaries({
                "start": st.fixed_dictionaries({"line": st.just(1), "character": st.just(0)}),
                "end": st.fixed_dictionaries({"line": st.just(1), "character": st.just(0)}),
            }),
            "text": st.sampled_from(["// line1 edit\n", "// line1 😀\n"]),
        }),
        st.fixed_dictionaries({
            "range": st.fixed_dictionaries({
                "start": st.fixed_dictionaries({"line": st.just(50), "character": st.just(0)}),
                "end": st.fixed_dictionaries({"line": st.just(50), "character": st.just(1)}),
            }),
            "text": st.just("invalid line"),
        }),
    )

    overlay_step_count = 0

    class OverlayStateMachine(state_machine_base):  # type: ignore[misc,valid-type]
        def __init__(self) -> None:
            super().__init__()
            self.model = OracleOverlayModel()
            self.server = self.model.make_server()
            self.next_ver = 1

        def _init_default_doc(self, text: str) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            ver = self.next_ver
            self.next_ver += 1
            self.model.step(
                self.server,
                {"action": "open", "uri": "untitled:doc-a.vela", "version": ver, "text": text},
            )

        init_default_doc = initialize(text=valid_doc_strategy)(_init_default_doc)

        def _open_or_reopen_doc(self, uri: str, text: str) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            if uri in self.model.open_docs:
                self.model.step(self.server, {"action": "close", "uri": uri})
            ver = self.next_ver
            self.next_ver += 1
            self.model.step(self.server, {"action": "open", "uri": uri, "version": ver, "text": text})

        open_or_reopen_doc = rule(
            uri=st.sampled_from(["untitled:doc-a.vela", "untitled:doc-b.vela"]),
            text=valid_doc_strategy,
        )(_open_or_reopen_doc)

        def _change_doc(self, uri: str, changes: list[object], stale: bool) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            if uri in self.model.desynchronized and changes and isinstance(changes[0], dict) and "range" in changes[0]:
                # Also exercise recovery via full replacement before applying ranged edits.
                rec_ver = self.next_ver
                self.next_ver += 1
                self.model.step(
                    self.server,
                    {
                        "action": "change",
                        "uri": uri,
                        "version": rec_ver,
                        "changes": [
                            {
                                "text": "// recovered\nmodule Overlay;\npublic Nat Entry(Nat input) {\n  let local = input;\n  return local;\n}\n"
                            }
                        ],
                    },
                )
            if stale:
                ver = max(0, self.next_ver - 1)
            else:
                ver = self.next_ver
                self.next_ver += 1
            self.model.step(
                self.server,
                {"action": "change", "uri": uri, "version": ver, "changes": changes},
            )

        change_doc = rule(
            uri=st.sampled_from(["untitled:doc-a.vela", "untitled:doc-b.vela"]),
            changes=st.lists(change_item_strategy, min_size=1, max_size=3),
            stale=st.sampled_from([False, False, False, True]),
        )(_change_doc)

        def _change_doc_batch(self, uri: str, first_text: str, second_kind: str) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            if uri not in self.model.open_docs or uri in self.model.desynchronized:
                if uri in self.model.open_docs:
                    self.model.step(self.server, {"action": "close", "uri": uri})
                open_ver = self.next_ver
                self.next_ver += 1
                self.model.step(
                    self.server,
                    {
                        "action": "open",
                        "uri": uri,
                        "version": open_ver,
                        "text": "// header\nmodule Overlay;\npublic Nat Entry(Nat input) {\n  let local = input;\n  return local;\n}\n",
                    },
                )
            second_edit = (
                {
                    "range": {
                        "start": {"line": 1, "character": 0},
                        "end": {"line": 1, "character": 0},
                    },
                    "text": "// second edit\n",
                }
                if second_kind == "line1_valid"
                else {
                    "range": {
                        "start": {"line": 99, "character": 0},
                        "end": {"line": 99, "character": 1},
                    },
                    "text": "invalid range",
                }
            )
            ver = self.next_ver
            self.next_ver += 1
            self.model.step(
                self.server,
                {
                    "action": "change",
                    "uri": uri,
                    "version": ver,
                    "changes": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 0},
                            },
                            "text": first_text,
                        },
                        second_edit,
                    ],
                },
            )

        change_doc_batch = rule(
            uri=st.sampled_from(["untitled:doc-a.vela", "untitled:doc-b.vela"]),
            first_text=st.sampled_from(["// first edit\n", "// first 😀\r\n"]),
            second_kind=st.sampled_from(["line1_valid", "line99_invalid"]),
        )(_change_doc_batch)

        def _save_doc(self, uri: str) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            self.model.step(self.server, {"action": "save", "uri": uri})

        save_doc = rule(uri=st.sampled_from(["untitled:doc-a.vela", "untitled:doc-b.vela"]))(_save_doc)

        def _close_doc(self, uri: str) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            self.model.step(self.server, {"action": "close", "uri": uri})

        close_doc = rule(uri=st.sampled_from(["untitled:doc-a.vela", "untitled:doc-b.vela"]))(_close_doc)

        def _invalidate_config(self, method: str) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            self.model.step(self.server, {"action": "invalidate", "method": method})

        invalidate_config = rule(
            method=st.sampled_from([
                "workspace/didChangeConfiguration",
                "workspace/didChangeWatchedFiles",
            ])
        )(_invalidate_config)

        def _cancel_req(self, req_id: int) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            self.model.step(self.server, {"action": "cancel", "id": req_id})

        cancel_req = rule(req_id=st.integers(min_value=1, max_value=200))(_cancel_req)

        def _query_service(
            self,
            uri: str,
            method: str,
            line: int,
            character: int,
            include_declaration: bool,
        ) -> None:
            nonlocal overlay_step_count
            overlay_step_count += 1
            self.model.step(
                self.server,
                {
                    "action": "query",
                    "uri": uri,
                    "method": method,
                    "line": line,
                    "character": character,
                    "end_line": line + 3,
                    "end_character": character + 10,
                    "include_declaration": include_declaration,
                },
            )

        query_service = rule(
            uri=st.sampled_from(["untitled:doc-a.vela", "untitled:doc-b.vela"]),
            method=st.sampled_from([
                "textDocument/hover",
                "textDocument/definition",
                "textDocument/references",
                "textDocument/documentSymbol",
                "textDocument/inlayHint",
                "textDocument/semanticTokens/full",
                "textDocument/formatting",
            ]),
            line=st.integers(min_value=0, max_value=6),
            character=st.integers(min_value=0, max_value=24),
            include_declaration=st.booleans(),
        )(_query_service)

        def _check_synchronization_invariants(self) -> None:
            self.model.verify_state(self.server)

        check_synchronization_invariants = invariant()(_check_synchronization_invariants)

    run_state_machine_as_test = stateful.run_state_machine_as_test

    def run_overlay_machine() -> None:
        seed_decorator(seed)(run_state_machine_as_test)(
            OverlayStateMachine, settings=campaign_settings
        )

    run_overlay_machine()

    # Subject 4: Pure formatting
    template_strategy = st.builds(
        FormatTemplate,
        module_name=st.sampled_from(["FormatMod", "AlphaMod", "UnicodeMod"]),
        header_comment=st.sampled_from([None, "// header comment", "// 😀 header"]),
        doc_comment=st.sampled_from([None, "/// Computes the bounded value.", "/// 😀 Unicode doc."]),
        detach_doc=st.booleans(),
        const_decl=st.sampled_from([
            None,
            ("Nat", "BaseLimit", "1_000"),
            ("bool", "DefaultFlag", "true"),
        ]),
        fn_name=st.sampled_from(["Compute", "Evaluate"]),
        param_name=st.sampled_from(["input", "count"]),
        local_name=st.sampled_from(["localVal", "stepVal"]),
        operator=st.sampled_from(["+", "-", "*", "/", "%"]),
        literal=st.sampled_from(["1", "42", "1_000"]),
        inline_comment=st.sampled_from([None, "// inline note", "// inline 😀"]),
        newline=newline_strategy,
        indent_spaces=st.integers(min_value=0, max_value=3),
        inner_spaces=st.integers(min_value=1, max_value=3),
    )

    format_runs = 0

    def _check_pure_formatting(template: FormatTemplate) -> None:
        nonlocal format_runs
        format_runs += 1
        verify_format_template(template)

    check_pure_formatting = cast(
        "Callable[[], None]",
        seed_decorator(seed)(campaign_settings(given(template=template_strategy)(_check_pure_formatting))),
    )
    check_pure_formatting()

    # Seeded fault controls (verify Hypothesis kills each executable mutant and shrinks explicit traces)
    fault_verdicts: dict[str, dict[str, object]] = {}
    for fault_name in SEEDED_FAULTS:
        if fault_name == "utf16-codepoint-confusion":
            verdict = evaluate_seeded_fault(fault_name, check_source_coordinates)
        else:
            verdict = evaluate_seeded_fault(fault_name, run_overlay_machine)
        if verdict["status"] != "killed":
            raise ValueError(f"seeded fault {fault_name} was not killed: {verdict}")
        fault_verdicts[fault_name] = verdict

    elapsed = round(time.monotonic() - start_wall, 3)
    if elapsed > timeout_seconds:
        raise ValueError(f"campaign exceeded {timeout_seconds}s wall-time bound ({elapsed}s)")

    return {
        "status": "qualified-isolated",
        "seed": seed,
        "settings": {
            "max_examples": max_examples,
            "stateful_step_count": step_count,
            "max_document_bytes": DEFAULT_MAX_DOCUMENT_BYTES,
            "timeout_seconds": timeout_seconds,
            "database": None,
            "derandomize": True,
        },
        "closure": closure,
        "subjects": {
            "source_coordinates": {"examples": coord_runs, "status": "passed"},
            "synchronous_overlays": {"steps": overlay_step_count, "status": "passed"},
            "supported_requests": {"steps": overlay_step_count, "status": "passed"},
            "pure_formatting": {"examples": format_runs, "status": "passed"},
        },
        "fault_controls": fault_verdicts,
        "elapsed_seconds": elapsed,
        "adoption_disposition": {
            "promote_to_ordinary_closure": False,
            "reason": (
                "Keep hypothesis==6.170.14 (MPL-2.0, with compiled Rust/PyO3 _native extension "
                "whose published wheels omit separate crate license texts) as an isolated "
                "development-only instrument provisioned in a temporary venv by `vela generated-tests`, "
                "while retaining the independent coordinate/overlay/formatter models and explicit "
                "shrunk regression fixtures in the Apache-2.0 test suite."
            ),
        },
    }


def qualify_isolated_campaign(
    root: Path,
    *,
    seed: int = DEFAULT_SEED,
    max_examples: int = DEFAULT_MAX_EXAMPLES,
    step_count: int = DEFAULT_STEP_COUNT,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Provision `hypothesis==6.170.14` in a disposable venv and run the bounded Q25x campaign."""
    if sys.version_info[:2] != (3, 14):
        raise ValueError(f"Q25x requires Python 3.14, got {sys.version.split()[0]}")
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        raise RuntimeError("uv executable not found on PATH")
    tools_dir = str((root / "tools").resolve())
    with tempfile.TemporaryDirectory(prefix="vos-vela-q25x-") as tmp_dir:
        venv_dir = Path(tmp_dir) / "venv"
        subprocess.run(
            [uv_bin, "venv", "--python", sys.executable, str(venv_dir)],
            check=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        venv_python = (
            venv_dir / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else venv_dir / "bin" / "python"
        )
        subprocess.run(
            [
                uv_bin,
                "pip",
                "install",
                "--python",
                str(venv_python),
                "--exclude-newer",
                COOLDOWN_CUTOFF,
                *CANDIDATE_PACKAGES,
            ],
            check=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        script = (
            f"import json, pathlib, sys; sys.path.insert(0, {tools_dir!r}); "
            "from vos.vela.generated_tests import run_hypothesis_campaign_in_process; "
            f"res = run_hypothesis_campaign_in_process(seed={seed}, max_examples={max_examples}, "
            f"step_count={step_count}, timeout_seconds={timeout_seconds}); "
            "print(json.dumps(res, sort_keys=True))"
        )
        completed = subprocess.run(
            [str(venv_python), "-I", "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"isolated Hypothesis campaign failed (exit {completed.returncode}): "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )
        return cast("dict[str, object]", json.loads(completed.stdout))
