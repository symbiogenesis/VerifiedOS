# SPDX-License-Identifier: Apache-2.0
"""Independent full semantic-token streams from the pure compiler's facts."""

import copy
from collections.abc import Callable
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.vela import inspect_source
from vos.vela.lsp_services import (
    METHODS,
    SEMANTIC_TOKEN_MODIFIERS,
    SEMANTIC_TOKEN_TYPES,
    InspectionError,
    project,
)
from vos.vela.source import SourceSnapshot

INDEPENDENT_CASES = True

_METHOD = "textDocument/semanticTokens/full"
_URI = "untitled:semantic-tokens.vela"


def _tokens(text: str) -> object:
    return project(SourceSnapshot(_URI, 1, text, 1), inspect_source(text.encode()), _METHOD, None)


def _refuses(operation: Callable[[], object], message: str) -> None:
    try:
        operation()
    except InspectionError:
        return
    raise AssertionError(message)


def _exact_stream_and_legend() -> None:
    text = """module Tokens;
public const Nat Limit = 2;
public Nat Echo(Nat value)
{
    let saved = value + Limit;
    return saved;
}
public Nat Use(Nat value) => Echo(value: value);
"""
    expected = {"data": [
        1, 17, 5, 2, 3,  # Limit declaration: variable, declaration + readonly.
        1, 11, 4, 0, 1,  # Echo declaration: function, declaration.
        0, 9, 5, 1, 3,   # Echo's value parameter.
        2, 8, 5, 2, 3,   # saved declaration.
        0, 8, 5, 1, 2,   # value use.
        0, 8, 5, 2, 2,   # Limit use.
        1, 11, 5, 2, 2,  # saved use.
        2, 11, 3, 0, 1,  # Use declaration.
        0, 8, 5, 1, 3,   # Use's distinct value parameter.
        0, 10, 4, 0, 0,  # Echo call.
        0, 5, 5, 1, 2,   # Label references Echo's parameter.
        0, 7, 5, 1, 2,   # Actual argument references Use's parameter.
    ]}
    ensure(SEMANTIC_TOKEN_TYPES == ("function", "parameter", "variable")
           and SEMANTIC_TOKEN_MODIFIERS == ("declaration", "readonly") and _METHOD in METHODS,
           "semantic-token capability legend or method identity differs from its contract")
    raw = inspect_source(text.encode())
    before = copy.deepcopy(raw)
    actual = project(SourceSnapshot(_URI, 1, text, 1), raw, _METHOD, None)
    ensure(actual == expected, f"semantic-token stream differs from independent positions: {actual!r}")
    ensure(raw == before, "semantic-token projection mutated compiler facts")


def _distinct_call_and_value_namespaces() -> None:
    text = ("module Names;\npublic Nat Same(Nat value) => value;\n"
            "public Nat Use(Nat Same) => Same(Same);\n")
    ensure(_tokens(text) == {"data": [
        1, 11, 4, 0, 1, 0, 9, 5, 1, 3, 0, 10, 5, 1, 2,
        1, 11, 3, 0, 1, 0, 8, 4, 1, 3, 0, 9, 4, 0, 0, 0, 5, 4, 1, 2,
    ]}, "same-spelled callable and value received the wrong semantic-token classification")


def _sibling_scope_identities() -> None:
    text = """module Shadows;
public Nat F(bool choose)
{
    if (choose) {
        let item = 1;
        return item;
    } else {
        let item = 2;
        return item;
    }
}
"""
    raw = inspect_source(text.encode())
    occurrences = cast("list[dict[str, object]]", raw["occurrences"])
    ensure([item["symbol"] for item in occurrences if item["line"] in {5, 6, 8, 9}] == [2, 2, 3, 3],
           "sibling same-spelled bindings lost their independent resolved identities")
    ensure(project(SourceSnapshot(_URI, 1, text, 1), raw, _METHOD, None) == {"data": [
        1, 11, 1, 0, 1, 0, 7, 6, 1, 3, 2, 8, 6, 1, 2,
        1, 12, 4, 2, 3, 1, 15, 4, 2, 2, 2, 12, 4, 2, 3, 1, 15, 4, 2, 2,
    ]}, "sibling scopes lost an occurrence or changed declaration and readonly modifiers")


def _unicode_comments_and_newline_units() -> None:
    for newline in ("\n", "\r\n", "\r"):
        text = newline.join(("// 😀 Nat Phantom", "module Unicode;", "/// Echoes café 😀.",
                             "public Nat Echo(Nat value) => value;", ""))
        ensure(_tokens(text) == {"data": [
            3, 11, 4, 0, 1, 0, 9, 5, 1, 3, 0, 10, 5, 1, 2,
        ]}, "comments, supplementary text or newline encoding invented or moved semantic tokens")
    # The projection converts compiler code-point sites through the shared source
    # adapter. This independent witness isolates that unit conversion without
    # giving the comment a fact in the real compiler fixture above.
    text = "// 😀 Echo"
    raw: dict[str, object] = {"status": "ok", "symbols": [
        {"name": "Echo", "kind": "function", "detail": "public Nat Echo()", "line": 1, "column": 6}],
        "occurrences": [{"symbol": 0, "line": 1, "column": 6, "declaration": True}]}
    ensure(project(SourceSnapshot(_URI, 1, text, 1), raw, _METHOD, None)
           == {"data": [0, 6, 4, 0, 1]}, "semantic-token start used Unicode code points instead of UTF-16")


def _unavailable_and_malformed_facts() -> None:
    text = "module M; public Nat Echo(Nat value) => value;"
    snapshot = SourceSnapshot(_URI, 1, text, 1)
    for reason in ("syntax", "name", "type", "unsupported", "limit", "encoding"):
        ensure(project(snapshot, {"status": "unavailable", "reason": reason}, _METHOD, None) == {"data": []},
               "unavailable source exposed a semantic-token stream or nonstandard result")
    raw = inspect_source(text.encode())
    variants: list[dict[str, object]] = []
    for corruption in ("missing-declaration", "overlap", "wrong-kind", "wrong-spelling", "wrong-link"):
        changed = copy.deepcopy(raw)
        symbols = cast("list[dict[str, object]]", changed["symbols"])
        occurrences = cast("list[dict[str, object]]", changed["occurrences"])
        if corruption == "missing-declaration":
            occurrences.pop(0)
        elif corruption == "overlap":
            occurrences.append(copy.deepcopy(occurrences[-1]))
        elif corruption == "wrong-kind":
            symbols[0]["kind"] = "keyword"
        elif corruption == "wrong-spelling":
            symbols[0]["name"] = "Ech"
        else:
            occurrences[-1]["symbol"] = 99
        variants.append(changed)
    for changed in variants:
        _refuses(lambda changed=changed: project(snapshot, changed, _METHOD, None),
                 "malformed compiler facts supplied a partial semantic-token stream")


def _inspection_bounds_are_complete_refusals() -> None:
    text = "module M; public Nat Echo(Nat value) => value;"
    snapshot = SourceSnapshot(_URI, 1, text, 1)
    raw = inspect_source(text.encode())
    for name, bound in (("MAX_SYMBOLS", 1), ("MAX_OCCURRENCES", 2)):
        with patch(f"vos.vela.lsp_services.{name}", bound):
            _refuses(lambda: project(snapshot, raw, _METHOD, None),
                     "inspection bound truncated rather than refused semantic tokens")
    changed = copy.deepcopy(raw)
    cast("list[dict[str, object]]", changed["symbols"])[0]["detail"] = "x" * 1_048_576
    _refuses(lambda: project(snapshot, changed, _METHOD, None),
             "oversized worker transport supplied a semantic-token stream")


def cases() -> list[Case]:
    return [Case("semantic-token-exact-stream-and-fixed-legend", _exact_stream_and_legend),
            Case("semantic-token-distinct-call-and-value-namespaces", _distinct_call_and_value_namespaces),
            Case("semantic-token-sibling-scope-identities", _sibling_scope_identities),
            Case("semantic-token-unicode-comments-and-newline-units", _unicode_comments_and_newline_units),
            Case("semantic-token-unavailable-and-malformed-facts", _unavailable_and_malformed_facts),
            Case("semantic-token-complete-inspection-bounds", _inspection_bounds_are_complete_refusals)]
