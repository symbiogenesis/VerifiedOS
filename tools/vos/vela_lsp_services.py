# SPDX-License-Identifier: Apache-2.0
"""Bounded projection of the pure compiler's resolved facts into LSP results."""

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message
from vos.vela_ast import (
    IDENTIFIER,
    KEYWORDS,
    MAX_LITERAL_DIGITS,
    MAX_SOURCE_BYTES,
    UNSUPPORTED,
    Name,
    Site,
)
from vos.vela_documentation import DocumentationSource
from vos.vela_facts import MAX_OCCURRENCES, MAX_SYMBOLS
from vos.vela_source import SourceSnapshot

INSPECTION_SECONDS = 5
SEMANTIC_TOKEN_TYPES = ("function", "parameter", "variable")
SEMANTIC_TOKEN_MODIFIERS = ("declaration", "readonly")
METHODS = frozenset({"textDocument/hover", "textDocument/definition",
                     "textDocument/references", "textDocument/documentSymbol", "textDocument/inlayHint",
                     "textDocument/semanticTokens/full"})
type Inspector = Callable[[bytes], dict[str, object]]
type Position = tuple[int, int]
type QueryRange = tuple[Position, Position]


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
    type_hint: str | None
    documentation: str | None


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
    documentation = DocumentationSource(snapshot.source)
    symbols: list[_Symbol] = []
    for value in symbols_raw:
        fields = {"name", "kind", "detail", "line", "column"}
        if isinstance(value, dict) and "documentation" in value:
            fields.add("documentation")
        symbol = _object(value, fields)
        name, kind, detail = symbol["name"], symbol["kind"], symbol["detail"]
        if (not isinstance(name, str) or not IDENTIFIER.fullmatch(name)
                or name in KEYWORDS | UNSUPPORTED or kind not in {"function", "parameter", "variable", "constant"}
                or not isinstance(detail, str) or not detail or len(detail) > MAX_SOURCE_BYTES):
            raise InspectionError("Invalid pure prototype inspection symbol")
        first, last = _span(snapshot, lines, name, symbol)
        if symbols and first <= symbols[-1].start:
            raise InspectionError("Pure prototype inspection declarations are unordered or duplicated")
        type_hint = None
        if kind == "variable":
            # The pure compiler's closed detail format already records the
            # inferred type. Decode that fact; the adapter never infers a type.
            type_hint = {f"{name}: Nat": ": Nat", f"{name}: bool": ": bool"}.get(detail)
            if type_hint is None:
                raise InspectionError("Invalid pure prototype inferred local type")
        elif kind == "parameter":
            if detail not in {f"{name}: Nat", f"{name}: bool",
                              f"const {name}: Nat", f"const {name}: bool"}:
                raise InspectionError("Invalid pure prototype parameter detail")
        elif kind == "constant":
            natural_prefix = f"const Nat {name} = "
            natural = detail.removeprefix(natural_prefix)
            valid_natural = (detail.startswith(natural_prefix)
                             and 1 <= len(natural) <= MAX_LITERAL_DIGITS
                             and natural.isascii() and natural.isdecimal()
                             and (natural == "0" or not natural.startswith("0")))
            if not valid_natural and detail not in {
                    f"const bool {name} = true", f"const bool {name} = false",
                    f"const Nat {name}", f"const bool {name}"}:
                raise InspectionError("Invalid pure prototype constant detail")
        doc = None
        if "documentation" in symbol:
            site = Site(_integer(symbol["line"]), _integer(symbol["column"]))
            doc = documentation.validate(symbol["documentation"], Name(name, site), cast("str", kind))
        symbols.append(_Symbol(name, cast("str", kind), detail, first, last, type_hint, doc))
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
            position: Position | None, include_declaration: bool = False,
            requested_range: QueryRange | None = None) -> object:
    """Project only complete current facts; malformed producer data is a refusal."""
    try:
        inspection = _validate(snapshot, raw)
    except (ValueError, TypeError, KeyError) as error:
        raise InspectionError("Invalid pure prototype inspection result") from error
    empty: object = [] if method in {
        "textDocument/references", "textDocument/documentSymbol", "textDocument/inlayHint"} else None
    if method == "textDocument/semanticTokens/full":
        empty = {"data": []}
    if inspection is None:
        return empty
    if method == "textDocument/semanticTokens/full":
        data: list[int] = []
        previous_line, previous_start = 0, 0
        for occurrence in inspection.occurrences:
            symbol = inspection.symbols[occurrence.symbol]
            line, start = occurrence.start
            token_type = {"function": 0, "parameter": 1, "variable": 2, "constant": 2}[symbol.kind]
            modifiers = int(occurrence.declaration) | (0 if symbol.kind == "function" else 2)
            data.extend((line - previous_line,
                         start - previous_start if line == previous_line else start,
                         occurrence.end[1] - start, token_type, modifiers))
            previous_line, previous_start = line, start
        return {"data": data}
    if method == "textDocument/inlayHint":
        if requested_range is None:
            raise InspectionError("Pure prototype hints require a source range")
        first, last = requested_range
        return [{"position": {"line": symbol.end[0], "character": symbol.end[1]},
                 "label": symbol.type_hint, "kind": 1}
                for symbol in inspection.symbols
                if symbol.type_hint is not None and first <= symbol.start and symbol.end <= last]
    if method == "textDocument/documentSymbol":
        kinds = {"function": 12, "constant": 14, "parameter": 13, "variable": 13}
        return [{"name": symbol.name, "kind": kinds[symbol.kind],
                 "location": _location(snapshot.uri, symbol.start, symbol.end)}
                for symbol in inspection.symbols]
    selected = next((occurrence for occurrence in inspection.occurrences
                     if position is not None and occurrence.start <= position < occurrence.end), None)
    if selected is None:
        return empty
    symbol = inspection.symbols[selected.symbol]
    if method == "textDocument/hover":
        doc = "" if symbol.documentation is None else "\n\n" + symbol.documentation
        return {"contents": {"kind": "plaintext", "value": symbol.detail + doc + "\nVela pure prototype (unqualified)"},
                "range": _range(selected.start, selected.end)}
    if method == "textDocument/definition":
        return _location(snapshot.uri, symbol.start, symbol.end)
    return [_location(snapshot.uri, occurrence.start, occurrence.end)
            for occurrence in inspection.occurrences
            if occurrence.symbol == selected.symbol and (include_declaration or not occurrence.declaration)]
