# SPDX-License-Identifier: Apache-2.0
"""Independent declaration/type/identity oracles for the pure compiler inspector."""

import json
import sys
from contextlib import redirect_stdout
from io import BytesIO, StringIO, TextIOWrapper
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.vela import (
    VelaError,
    inspect_source,
    translate,
)
from vos.vela import (
    lsp_worker as vela_lsp_worker,
)

_SOURCE = """module Facts;
public Nat Step(Nat x) {
  let y = x + 1;
  return y;
}
public Nat Pick(bool choose, Nat x) {
  if (choose) {
    let y = Step(x);
    return y;
  } else {
    let y = x;
    return y;
  }
}
public Nat Other(Nat Step) { return Step(Step); }
"""


def _expected() -> dict[str, object]:
    declarations: list[tuple[str, str, str, int, int]] = [
        ("Step", "function", "public Nat Step(Nat x)", 2, 12),
        ("x", "parameter", "x: Nat", 2, 21),
        ("y", "variable", "y: Nat", 3, 7),
        ("Pick", "function", "public Nat Pick(bool choose, Nat x)", 6, 12),
        ("choose", "parameter", "choose: bool", 6, 22),
        ("x", "parameter", "x: Nat", 6, 34),
        ("y", "variable", "y: Nat", 8, 9),
        ("y", "variable", "y: Nat", 11, 9),
        ("Other", "function", "public Nat Other(Nat Step)", 15, 12),
        ("Step", "parameter", "Step: Nat", 15, 22),
    ]
    # Separate branch y declarations and separate x parameters intentionally use
    # distinct IDs; the last call uses the function, its argument the parameter.
    uses: list[tuple[int, int, int, bool]] = [
        (0, 2, 12, True), (1, 2, 21, True), (2, 3, 7, True),
        (1, 3, 11, False), (2, 4, 10, False),
        (3, 6, 12, True), (4, 6, 22, True), (5, 6, 34, True),
        (4, 7, 7, False), (6, 8, 9, True), (0, 8, 13, False),
        (5, 8, 18, False), (6, 9, 12, False), (7, 11, 9, True),
        (5, 11, 13, False), (7, 12, 12, False),
        (8, 15, 12, True), (9, 15, 22, True),
        (0, 15, 37, False), (9, 15, 42, False),
    ]
    return {"status": "ok", "symbols": [
                {"name": name, "kind": kind, "detail": detail, "line": line, "column": column}
                for name, kind, detail, line, column in declarations],
            "occurrences": [
                {"symbol": symbol, "line": line, "column": column, "declaration": declaration}
                for symbol, line, column, declaration in uses]}


def _resolved_oracle() -> None:
    expected = _expected()
    ensure(inspect_source(_SOURCE.encode()) == expected,
           "compiler facts differ from independent identities/types/sites")
    ensure(inspect_source(_SOURCE.encode()) == expected, "inspection is nondeterministic")
    # Each invocation returns new serialization containers, never shared state.
    changed = inspect_source(_SOURCE.encode())
    changed["symbols"] = []
    ensure(inspect_source(_SOURCE.encode()) == expected, "caller mutation changed compiler facts")


def _inferred_types_and_coordinates() -> None:
    source = "// 😀 café\nmodule Types;\npublic bool F(bool input) { let same = input == true; return same; }"
    expected: dict[str, object] = {"status": "ok", "symbols": [
        {"name": "F", "kind": "function", "detail": "public bool F(bool input)",
         "line": 3, "column": 13},
        {"name": "input", "kind": "parameter", "detail": "input: bool", "line": 3, "column": 20},
        {"name": "same", "kind": "variable", "detail": "same: bool", "line": 3, "column": 33}],
        "occurrences": [
            {"symbol": 0, "line": 3, "column": 13, "declaration": True},
            {"symbol": 1, "line": 3, "column": 20, "declaration": True},
            {"symbol": 2, "line": 3, "column": 33, "declaration": True},
            {"symbol": 1, "line": 3, "column": 40, "declaration": False},
            {"symbol": 2, "line": 3, "column": 62, "declaration": False}]}
    for newline in ("\n", "\r\n", "\r"):
        ensure(inspect_source(source.replace("\n", newline).encode()) == expected,
               f"inferred bool type or codepoint sites changed under {newline!r}")


def _refuses(source: str, kind: str) -> None:
    try:
        inspect_source(source.encode())
    except VelaError as error:
        ensure(error.kind == kind, f"expected {kind}, got {error.kind}: {error}")
        return
    raise AssertionError(f"inspection published facts for refused {kind} source")


def _complete_check_only() -> None:
    prefix = "module Bad; public Nat Good(Nat x) { return x; } "
    for suffix, kind in (
            ("public Nat Bad() { return missing; }", "name"),
            ("public Nat Bad() { return true; }", "type"),
            ("public Nat Bad() { return Bad(); }", "name"),
            ("public Nat Bad() { return Later(); } public Nat Later() { return 0; }", "name"),
            ("public Nat Bad() { let x = 0; let x = 1; return x; }", "name"),
            ("public Nat Bad() { if (true) { let x = 1; return x; } else { return x; } }", "name"),
            ("public Nat Bad() { return 0;", "syntax"),
            ("async", "unsupported")):
        _refuses(prefix + suffix, kind)
    ensure(inspect_source(_SOURCE.encode()) == _expected(), "refused inspection leaked partial state")


def _inspection_limits_only() -> None:
    declarations = "module Many; " + " ".join(
        f"public Nat F{index}() {{ return 0; }}" for index in range(1024))
    accepted = inspect_source(declarations.encode())
    ensure(len(cast("list[object]", accepted["symbols"])) == 1024, "exact declaration limit refused")
    over = declarations + " public Nat Extra() { return 0; }"
    _refuses(over, "inspection-limit")
    ensure("Definition f_Extra" in translate(over.encode()).gallina,
           "inspection declaration limit changed ordinary translation")
    occurrences = "module Uses; " + " ".join(
        f"public Nat F{index}(Nat x) {{ return x+x+x+x+x+x; }}" for index in range(512))
    accepted = inspect_source(occurrences.encode())
    ensure(len(cast("list[object]", accepted["occurrences"])) == 4096, "exact occurrence limit refused")
    over = occurrences.replace("return x+x+x+x+x+x;", "return x+x+x+x+x+x+x;", 1)
    _refuses(over, "inspection-limit")
    ensure("Definition f_F511" in translate(over.encode()).gallina,
           "inspection occurrence limit changed ordinary translation")


def _worker(source: bytes, inspect: bool) -> tuple[int, object]:
    output = StringIO()
    with (TextIOWrapper(BytesIO(source), encoding="utf-8") as input_stream,
          patch.object(sys, "stdin", input_stream),
          patch.object(sys, "argv", ["vela-lsp-worker", *(["--inspect"] if inspect else [])]),
          redirect_stdout(output)):
        code = vela_lsp_worker.main()
    return code, json.loads(output.getvalue())


def _worker_modes_and_output_bound() -> None:
    ensure(_worker(_SOURCE.encode(), True) == (0, _expected()), "worker lost inspection facts")
    ensure(_worker(_SOURCE.encode(), False) == (0, None), "existing diagnostic mode changed")
    source = b"module Bad; public Nat Bad() { return true; }"
    ensure(_worker(source, True) == (0, {"status": "unavailable", "reason": "type"}),
           "failed worker inspection published partial facts")
    code, diagnostic = _worker(source, False)
    ensure(code == 0 and isinstance(diagnostic, dict) and diagnostic.get("kind") == "type",
           "existing worker diagnostics changed")
    with patch.object(vela_lsp_worker, "MAX_BODY_BYTES", 64):
        ensure(_worker(_SOURCE.encode(), True) ==
               (0, {"status": "unavailable", "reason": "inspection-limit"}),
               "oversized worker response was partially published")


def cases() -> list[Case]:
    return [Case("independent-resolved-identity-oracle", _resolved_oracle),
            Case("inferred-types-and-normalized-sites", _inferred_types_and_coordinates),
            Case("facts-require-complete-successful-check", _complete_check_only),
            Case("inspection-bounds-leave-translation-unchanged", _inspection_limits_only),
            Case("worker-modes-and-output-bound", _worker_modes_and_output_bound)]
