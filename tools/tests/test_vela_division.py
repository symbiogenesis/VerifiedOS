# SPDX-License-Identifier: Apache-2.0
"""Independent values, terms and source-bound controls for pure Nat division."""

import copy
import hashlib
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela, vela_ast
from vos.vela_authoring import format_source

_NAT = "Corelib.Init.Datatypes.nat"
_BASE = b"module M; public Nat Id(Nat value) => value;"


def _refuses(source: str, kind: str, fragment: str = "") -> vela.VelaError:
    try:
        vela.translate(source.encode())
    except vela.VelaError as error:
        ensure(error.kind == kind and fragment in error.message,
               f"expected {kind}/{fragment!r}, got {error.kind}: {error.message}")
        return error
    raise AssertionError("accepted refused division source")


def _values() -> None:
    cases = {"17 / 5": 3, "17 % 5": 2, "0 / 5": 0, "0 % 5": 0,
             "5 / 8": 0, "5 % 8": 5, "5 / 5": 1, "5 % 5": 0,
             "17 / 1": 17, "17 % 1": 0, "17 / 0": 0, "17 % 0": 17,
             "0 / 0": 0, "0 % 0": 0,
             "20 / 3 * 2": 12, "20 / (3 * 2)": 3,
             "20 % 6 * 2": 4, "20 % (6 * 2)": 8,
             "30 / 4 % 3": 1, "30 % 4 / 2": 1,
             "2 + 19 % 6 * 3": 5, "32 / 4 / 2": 4, "32 / (4 / 2)": 16,
             "1_024 / 1_00": 10, "1_024 % 1_00": 24,
             "Id(value: 17) / Id(value: 5)": 3,
             "Id(value: 17) % Id(value: 5)": 2,
             "8// division follows this line comment\n/2": 4}
    for expression, expected in cases.items():
        ensure(vela.evaluate(_BASE, expression, "Nat") == vela.StaticEvaluation("Nat", expected),
               f"wrong quotient/remainder for {expression}")
    ensure(vela.evaluate(_BASE, "17 / 5 == 3 && 17 % 5 != 0", "bool").value is True,
           "division did not compose with Boolean comparisons")


def _terms() -> None:
    cases = (("a / b", "(Corelib.Init.Nat.div v_a v_b)"),
             ("a % b", "(Corelib.Init.Nat.modulo v_a v_b)"),
             ("a / b * c", "(Corelib.Init.Nat.mul (Corelib.Init.Nat.div v_a v_b) v_c)"),
             ("a % b * c", "(Corelib.Init.Nat.mul (Corelib.Init.Nat.modulo v_a v_b) v_c)"),
             ("a * b / c", "(Corelib.Init.Nat.div (Corelib.Init.Nat.mul v_a v_b) v_c)"),
             ("a / b % c", "(Corelib.Init.Nat.modulo (Corelib.Init.Nat.div v_a v_b) v_c)"),
             ("a / (b * c)", "(Corelib.Init.Nat.div v_a (Corelib.Init.Nat.mul v_b v_c))"))
    for expression, expected in cases:
        source = ("module Terms; public Nat F(Nat a, Nat b, Nat c) => " + expression + ";").encode()
        ensure(f":=\n  {expected}.\n" in vela.translate(source).gallina,
               f"wrong emitted multiplicative grouping for {expression}")
    source = (b"module Calls; public Nat Left() => 17; public Nat Right() => 5; "
              b"public Nat Divide() => Left() / Right(); public Nat Remain() => Left() % Right();")
    emitted = vela.translate(source).gallina
    ensure("(Corelib.Init.Nat.div f_Left f_Right)" in emitted
           and "(Corelib.Init.Nat.modulo f_Left f_Right)" in emitted,
           "division emission changed operand order or duplicated calls")


def _constants_and_static_parameters() -> None:
    source = (b"module Static; public const Nat Groups = 17 / 5; public const Nat Tail = 17 % 5; "
              b"public const Nat ZeroQuotient = 17 / 0; public const Nat ZeroRemainder = 17 % 0; "
              b"public Nat Bucket(const Nat width, Nat value) { "
              b"const Nat step = width % 3 + 1; return value / step; } "
              b"public Nat Forward(const Nat width, Nat value) => Bucket(width: width, value: value); "
              b"public Nat F(Nat value) => Forward(width: 5, value: value);")
    for expression, expected in (("Groups", 3), ("Tail", 2), ("ZeroQuotient", 0),
                                 ("ZeroRemainder", 17), ("F(17)", 5),
                                 ("Forward(width: 0, value: 17)", 17)):
        ensure(vela.evaluate(source, expression, "Nat").value == expected,
               f"constant or static specialization changed {expression}")
    emitted = vela.translate(source).gallina
    for name, expected in (("Groups", 3), ("Tail", 2), ("ZeroQuotient", 0), ("ZeroRemainder", 17)):
        ensure(f"Definition c_{name} : {_NAT} :=\n  ({expected} : {_NAT})." in emitted,
               f"constant {name} did not normalize to its independent value")
    facts = vela.inspect_source(source)
    ensure(bool(facts["symbols"]) and bool(facts["occurrences"]),
           "division lost compiler facts for editor consumers")


def _semantic_and_syntax_refusals() -> None:
    for operation in ("/", "%"):
        for expression in (f"true {operation} 2", f"1 {operation} false", f"true {operation} false"):
            _refuses(f"module M; public Nat F() => {expression};", "type", f"'{operation}'")
        _refuses(f"module M; public bool F() => 8 {operation} 3;", "type", "returns Nat")
        _refuses(f"module M; public Nat F() => missing {operation} 0;", "name", "unbound")
        for expression in (f"runtime {operation} 0", f"0 {operation} runtime"):
            _refuses("module M; public Nat F(Nat runtime) { const Nat Wrong = "
                     + expression + "; return Wrong; }", "unsupported", "runtime binding 'runtime'")
        _refuses("module M; public bool F(Nat runtime) { "
                 f"const bool Wrong = false && (runtime {operation} 0 == 0); return Wrong; }}",
                 "unsupported", "runtime binding 'runtime'")
        for expression in (f"{operation} 2", f"2 {operation}", f"2 {operation} {operation} 3",
                           f"2 {operation}= 3", f"2 {operation} * 3"):
            _refuses(f"module M; public Nat F() => {expression};", "syntax")
        source = f"module M;\r\n// supplementary comment: \U0001f680\r\npublic Nat F() => true {operation} 2;"
        error = _refuses(source, "type", f"'{operation}'")
        ensure((error.line, error.column) == (3, 23), "operator diagnostic lost original Unicode/CRLF site")
    _refuses("module M; public Nat F() => 8 // comment hides the apparent operand / 2;", "syntax")
    _refuses("module M; public Nat F() => 1" + "/1" * 64 + ";", "limit")


def _numeric_and_work_limits() -> None:
    maximum = "9" * vela.MAX_LITERAL_DIGITS
    ensure(vela.evaluate(_BASE, maximum + " / 1", "Nat").value == int(maximum),
           "division narrowed the existing numeric range")
    ensure(vela.evaluate(_BASE, maximum + " % 0", "Nat").value == int(maximum),
           "zero remainder narrowed the existing numeric range")
    for expression in (f"({maximum} * 2) / 2", f"({maximum} * 2) / 0",
                       f"({maximum} * 2) % 0", f"0 / ({maximum} * 2)", f"0 % ({maximum} * 2)"):
        try:
            vela.evaluate(_BASE, expression, "Nat")
        except vela.VelaError as error:
            ensure(error.kind == "limit", "division changed an operand's numeric-limit refusal")
        else:
            raise AssertionError("division hid a previously overflowing operand")
    declarations = ["module Work; public Nat F0(Nat value) => value;"]
    declarations.extend(f"public Nat F{index}(Nat value) => F{index - 1}(value) + F{index - 1}(value);"
                        for index in range(1, 16))
    source = " ".join(declarations).encode()
    for expression in ("F15(0) / 0", "F15(0) % 0", "0 / F15(0)", "0 % F15(0)"):
        try:
            vela.evaluate(source, expression, "Nat")
        except vela.VelaError as error:
            ensure(error.kind == "limit", "zero operands changed the static work-limit refusal")
        else:
            raise AssertionError("zero division/remainder skipped an expensive operand")
    for expression, fragment in ((f"({maximum} * 2) / F15(0)", "constant result exceeds"),
                                 (f"F15(0) / ({maximum} * 2)", "work or nesting budget")):
        try:
            vela.evaluate(source, expression, "Nat")
        except vela.VelaError as error:
            ensure(error.kind == "limit" and fragment in error.message,
                   "division evaluated operands in the wrong source order")
        else:
            raise AssertionError("costly division operands escaped static limits")


def _node(kind: str, start: int, end: int, **fields: object) -> dict[str, object]:
    return {"kind": kind, "span": [start, end], **fields}


def _name(text: str, start: int) -> dict[str, object]:
    return {"text": text, "span": [start, start + len(text)]}


def _native_fixture(source: bytes, operator: str, *, left: bytes = b"17", right: bytes = b"5"
                    ) -> tuple[dict[str, object], dict[str, object]]:
    """Construct a nullary block and operator from independently located source bytes."""
    module = source.index(b"module")
    declaration = source.index(b"public")
    result = source.index(b"Nat", declaration)
    function_name = source.index(b"F()", result)
    brace = source.index(b"{", function_name)
    returned = source.index(b"return", brace)
    left_start = source.index(left, returned)
    operator_start = source.index(operator.encode(), left_start + len(left))
    right_start = source.index(right, operator_start + 1)
    terminal_end = source.index(b";", right_start) + 1
    end = source.index(b"}", terminal_end) + 1
    expression = _node("binary", left_start, right_start + len(right),
                       operator=_name(operator, operator_start),
                       left=_node("nat", left_start, left_start + len(left), value=left.decode()),
                       right=_node("nat", right_start, right_start + len(right), value=right.decode()))
    function = _node("function", declaration, end, name=_name("F", function_name),
                     result=_node("type", result, result + 3, name="Nat"), parameters=[],
                     body=_node("block", brace, end, bindings=[],
                                exit=_node("return", returned, terminal_end, value=expression)))
    tree: dict[str, object] = {
        "schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
        "ast": _node("file", module, end, name=_name("M", module + 7), declarations=[function])}
    return tree, expression


def _native_source_binding() -> None:
    for operation, target in (("/", "div"), ("%", "modulo")):
        for newline in (b"\n", b"\r\n", b"\r"):
            source = (b"// caf\xc3\xa9" + newline + b"module M;" + newline + b"public Nat F() {" + newline
                      + b" return 17 " + operation.encode() + b" // operand comment" + newline
                      + b" 5;" + newline + b"}" + newline + b"// tail")
            tree, expression = _native_fixture(source, operation)
            decoded = vela_ast.decode(source, tree)
            declaration = decoded.declarations[0]
            ensure(isinstance(declaration, vela_ast.Function), "native fixture lost its function")
            if not isinstance(declaration, vela_ast.Function):
                raise TypeError("native fixture lost its function")
            terminal = declaration.body.terminal
            ensure(isinstance(terminal, vela_ast.Return), "native fixture lost its return")
            if not isinstance(terminal, vela_ast.Return):
                raise TypeError("native fixture lost its return")
            ensure(terminal.value.value == operation and terminal.value.site == vela_ast.Site(4, 12),
                   "native division lost operator spelling or original newline coordinates")
            with patch.object(vela, "_tokens", side_effect=AssertionError("Python syntax fallback")):
                emitted = vela.translate_ast(source, tree).gallina
            ensure(f"(Corelib.Init.Nat.{target} (17 : {_NAT}) (5 : {_NAT}))" in emitted,
                   "native division emitted the wrong operation or source operands")
            for mutation in ("operator", "missing-right", "extra-field", "operator-span"):
                changed = copy.deepcopy(expression)
                if mutation == "operator":
                    changed["operator"] = _name("%" if operation == "/" else "/",
                                                source.index(operation.encode(), source.index(b"17")))
                elif mutation == "missing-right":
                    del changed["right"]
                elif mutation == "extra-field":
                    changed["ignored"] = _node("nat", 0, 1, value="0")
                else:
                    changed["operator"] = _name(operation, source.index(b"// operand") + 1)
                changed_tree, _ = _native_fixture(source, operation)
                root = cast("dict[str, object]", changed_tree["ast"])
                declarations = cast("list[dict[str, object]]", root["declarations"])
                body = cast("dict[str, object]", declarations[0]["body"])
                terminal = cast("dict[str, object]", body["exit"])
                terminal["value"] = changed
                _refuses_native(source, changed_tree)
        for expression in (f"17 {operation} + 5", f"17 {operation}= 5",
                           f"17 * 3 {operation} 5", f"17 {operation} 5 * 2"):
            source = ("module M; public Nat F() { return " + expression + "; }").encode()
            tree, _ = _native_fixture(source, operation)
            _refuses_native(source, tree)


def _refuses_native(source: bytes, tree: dict[str, object]) -> None:
    try:
        with patch.object(vela, "_tokens", side_effect=AssertionError("Python syntax fallback")):
            vela.translate_ast(source, tree)
    except (TypeError, ValueError):
        return
    raise AssertionError("native division accepted omitted, substituted or extra source tokens")


def _formatting() -> None:
    source = (b"module M;\r\n/// Quotient and remainder.\r\n"
              b"public Nat F(Nat count,Nat width)=>count/width%3*2;")
    expected = (b"module M;\n\n/// Quotient and remainder.\n"
                b"public Nat F(Nat count, Nat width) => count / width % 3 * 2;\n")
    original = bytes(source)
    ensure(format_source(source) == expected, "division/remainder spacing changed canonical bytes")
    ensure(format_source(expected) == expected and source == original,
           "division formatting was not source-preserving and idempotent")
    ensure(vela.translate(source).gallina.splitlines()[2:] == vela.translate(expected).gallina.splitlines()[2:],
           "division formatting changed emitted terms")
    for expression in (b"count / // quotient\nwidth", b"count // dividend\n/ width",
                       b"count % // remainder\nwidth", b"count // dividend\n% width"):
        commented = b"module M; public Nat F(Nat count, Nat width) => " + expression + b";"
        formatted = format_source(commented)
        ensure(format_source(formatted) == formatted, "division comment formatting did not stabilize")
        ensure(vela.translate(commented).gallina.splitlines()[2:] == vela.translate(formatted).gallina.splitlines()[2:],
               "division comment formatting changed interpretation")


def cases() -> list[Case]:
    return [Case("natural-division-independent-values", _values),
            Case("natural-division-exact-terms-and-precedence", _terms),
            Case("natural-division-constants-static-parameters-and-facts", _constants_and_static_parameters),
            Case("natural-division-semantic-and-syntax-refusals", _semantic_and_syntax_refusals),
            Case("natural-division-numeric-work-limits-and-evaluation-order", _numeric_and_work_limits),
            Case("natural-division-independent-native-ast-source-binding", _native_source_binding),
            Case("natural-division-formatting-comments-and-source-preservation", _formatting)]
