# SPDX-License-Identifier: Apache-2.0
"""Bounded projection of the pure compiler's resolved facts into LSP results."""

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message
from vos.vela_ast import IDENTIFIER, KEYWORDS, MAX_SOURCE_BYTES, UNSUPPORTED
from vos.vela_source import SourceSnapshot

MAX_SYMBOLS = 1024
MAX_OCCURRENCES = 4096
INSPECTION_SECONDS = 5
METHODS = frozenset({"textDocument/hover", "textDocument/definition",
                     "textDocument/references", "textDocument/documentSymbol"})
type Inspector = Callable[[bytes], dict[str, object]]
type Position = tuple[int, int]


class InspectionError(ValueError):
    """The current source cannot supply a complete bounded inspection result."""


def inspect_document(source: bytes) -> dict[str, object]:
    """Run only the checkout's fixed fact producer, never a client-selected tool."""
    tools = str(Path(__file__).resolve().parents[1])
    script = (f"import sys; sys.path.insert(0, {tools!r}); "
              "from vos.vela_lsp_worker import main; raise SystemExit(main())")
    try:
        done = subprocess.run([sys.executable, "-I", "-c", script, "--inspect"],
                              input=source, capture_output=True,
                              timeout=INSPECTION_SECONDS, check=False)
        if done.returncode != 0 or len(done.stdout) > MAX_BODY_BYTES:
            raise InspectionError("Pure prototype inspection worker failed or exceeded its output bound")
        return decode_message(done.stdout)
    except subprocess.TimeoutExpired as error:
        raise InspectionError("Pure prototype inspection exceeded 5 seconds") from error
    except (OSError, ValueError) as error:
        raise InspectionError("Pure prototype inspection worker unavailable") from error


@dataclass(frozen=True)
class _Symbol:
    name: str
    kind: str
    detail: str
    start: Position
    end: Position


@dataclass(frozen=True)
class _Occurrence:
    symbol: int
    start: Position
    end: Position
    declaration: bool


@dataclass(frozen=True)
class _Inspection:
    symbols: tuple[_Symbol, ...]
    occurrences: tuple[_Occurrence, ...]


def _object(value: object, fields: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise InspectionError("Invalid pure prototype inspection object")
    return cast("dict[str, object]", value)


def _integer(value: object) -> int:
    if type(value) is not int or not 0 <= value < 2 ** 31:
        raise InspectionError("Invalid pure prototype inspection integer")
    return value


def _span(snapshot: SourceSnapshot, lines: list[str], name: str,
          record: dict[str, object]) -> tuple[Position, Position]:
    line, column = _integer(record["line"]), _integer(record["column"])
    if not 1 <= line <= len(lines) or column < 1:
        raise InspectionError("Pure prototype inspection site is outside source")
    text, start = lines[line - 1], column - 1
    end = start + len(name)
    if (text[start:end] != name
            or (start and (text[start - 1].isascii() and (text[start - 1].isalnum() or text[start - 1] == "_")))
            or (end < len(text) and (text[end].isascii() and (text[end].isalnum() or text[end] == "_")))):
        raise InspectionError("Pure prototype inspection identifier differs from source")
    # The compiler's sites count normalized Unicode code points. Only the shared
    # source adapter converts those units to LSP's UTF-16 coordinates.
    first = snapshot.diagnostic_position(line, column)
    last = snapshot.diagnostic_position(line, column + len(name))
    return (first["line"], first["character"]), (last["line"], last["character"])


def _validate(snapshot: SourceSnapshot, raw: dict[str, object]) -> _Inspection | None:
    encode_message(raw)
    if raw.get("status") == "unavailable":
        record = _object(raw, {"status", "reason"})
        if record["reason"] in {"syntax", "name", "type", "unsupported", "limit", "encoding"}:
            return None
        raise InspectionError("Pure prototype inspection unavailable or exceeds its bounds")
    record = _object(raw, {"status", "symbols", "occurrences"})
    symbols_raw, occurrences_raw = record["symbols"], record["occurrences"]
    if (record["status"] != "ok" or not isinstance(symbols_raw, list)
            or not isinstance(occurrences_raw, list) or len(symbols_raw) > MAX_SYMBOLS
            or len(occurrences_raw) > MAX_OCCURRENCES):
        raise InspectionError("Pure prototype inspection exceeds its bounds or has invalid status")
    lines = snapshot.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    symbols: list[_Symbol] = []
    for value in symbols_raw:
        symbol = _object(value, {"name", "kind", "detail", "line", "column"})
        name, kind, detail = symbol["name"], symbol["kind"], symbol["detail"]
        if (not isinstance(name, str) or not IDENTIFIER.fullmatch(name)
                or name in KEYWORDS | UNSUPPORTED or kind not in {"function", "parameter", "variable"}
                or not isinstance(detail, str) or not detail or len(detail) > MAX_SOURCE_BYTES):
            raise InspectionError("Invalid pure prototype inspection symbol")
        first, last = _span(snapshot, lines, name, symbol)
        if symbols and first <= symbols[-1].start:
            raise InspectionError("Pure prototype inspection declarations are unordered or duplicated")
        symbols.append(_Symbol(name, cast("str", kind), detail, first, last))
    occurrences: list[_Occurrence] = []
    declarations: set[int] = set()
    for value in occurrences_raw:
        occurrence = _object(value, {"symbol", "line", "column", "declaration"})
        identity = _integer(occurrence["symbol"])
        declaration = occurrence["declaration"]
        if identity >= len(symbols) or type(declaration) is not bool:
            raise InspectionError("Invalid pure prototype inspection occurrence link")
        symbol = symbols[identity]
        first, last = _span(snapshot, lines, symbol.name, occurrence)
        if occurrences and first < occurrences[-1].end:
            raise InspectionError("Pure prototype inspection occurrences overlap or are unordered")
        if declaration:
            if identity in declarations or first != symbol.start:
                raise InspectionError("Invalid pure prototype inspection declaration link")
            declarations.add(identity)
        elif first == symbol.start:
            raise InspectionError("Pure prototype declaration mislabeled as reference")
        occurrences.append(_Occurrence(identity, first, last, declaration))
    if len(declarations) != len(symbols):
        raise InspectionError("Pure prototype inspection omits declaration occurrences")
    return _Inspection(tuple(symbols), tuple(occurrences))


def _range(start: Position, end: Position) -> dict[str, object]:
    return {"start": {"line": start[0], "character": start[1]},
            "end": {"line": end[0], "character": end[1]}}


def _location(uri: str, start: Position, end: Position) -> dict[str, object]:
    return {"uri": uri, "range": _range(start, end)}


def project(snapshot: SourceSnapshot, raw: dict[str, object], method: str,
            position: Position | None, include_declaration: bool = False) -> object:
    """Project only complete current facts; malformed producer data is a refusal."""
    try:
        inspection = _validate(snapshot, raw)
    except (ValueError, TypeError, KeyError) as error:
        raise InspectionError("Invalid pure prototype inspection result") from error
    empty: object = [] if method in {"textDocument/references", "textDocument/documentSymbol"} else None
    if inspection is None:
        return empty
    if method == "textDocument/documentSymbol":
        return [{"name": symbol.name, "kind": 12 if symbol.kind == "function" else 13,
                 "location": _location(snapshot.uri, symbol.start, symbol.end)}
                for symbol in inspection.symbols]
    selected = next((occurrence for occurrence in inspection.occurrences
                     if position is not None and occurrence.start <= position < occurrence.end), None)
    if selected is None:
        return empty
    symbol = inspection.symbols[selected.symbol]
    if method == "textDocument/hover":
        return {"contents": {"kind": "plaintext", "value": symbol.detail + "\nVela pure prototype (unqualified)"},
                "range": _range(selected.start, selected.end)}
    if method == "textDocument/definition":
        return _location(snapshot.uri, symbol.start, symbol.end)
    return [_location(snapshot.uri, occurrence.start, occurrence.end)
            for occurrence in inspection.occurrences
            if occurrence.symbol == selected.symbol and (include_declaration or not occurrence.declaration)]
