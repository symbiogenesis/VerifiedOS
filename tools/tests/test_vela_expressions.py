# SPDX-License-Identifier: Apache-2.0
"""Independent values, terms and refusals for extended pure expressions."""

from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela

_NAT = "Corelib.Init.Datatypes.nat"
_BOOL = "Corelib.Init.Datatypes.bool"
_TRUE = "Corelib.Init.Datatypes.true"
_FALSE = "Corelib.Init.Datatypes.false"
_BASE = (b"module M; public Nat Id(Nat value) => value; "
         b"public bool Echo(bool value) => value;")


def _refuses(source: str, kind: str, fragment: str = "") -> vela.VelaError:
    try:
        vela.translate(source.encode())
    except vela.VelaError as error:
        ensure(error.kind == kind and fragment in error.message,
               f"expected {kind}/{fragment!r}, got {error.kind}: {error.message}")
        return error
    raise AssertionError("accepted refused expression")


def _values() -> None:
    naturals = {"10 - 3 - 2": 5, "2 - 8": 0, "0 - 0": 0,
                "2 + 3 * 4 - 5": 9, "10 - (3 - 2)": 9,
                "Id(value: 8) - Id(value: 3)": 5}
    booleans = {"!false": True, "!true": False, "!!true": True,
                "!false || false && false": True, "!false == true": True,
                "!(true || false)": False, "true && false || true": True,
                "true && true": True, "false && true": False,
                "false || false": False, "false || true": True,
                "3 < 4": True, "4 < 4": False, "5 < 4": False,
                "4 > 3": True, "4 > 4": False, "3 > 4": False,
                "4 >= 4": True, "3 >= 4": False, "5 >= 4": True,
                "3 <= 4": True, "5 <= 4": False,
                "2 != 3": True, "2 != 2": False,
                "true != false": True, "false != false": False,
                "false != true": True, "true != true": False,
                "2 - 8 == 0 && 5 >= 4": True,
                "Echo(value: true) && !Echo(value: false)": True}
    for expression, expected in naturals.items():
        actual = vela.evaluate(_BASE, expression, "Nat")
        ensure(actual == vela.StaticEvaluation("Nat", expected), f"wrong Nat result for {expression}")
    for expression, expected in booleans.items():
        actual = vela.evaluate(_BASE, expression, "bool")
        ensure(actual == vela.StaticEvaluation("bool", expected), f"wrong bool result for {expression}")


def _terms() -> None:
    negate = f"(if v_left then {_FALSE} else {_TRUE})"
    boolean_equal = ("(let vela_eq_left := v_left in let vela_eq_right := v_right in "
                     "if vela_eq_left then vela_eq_right else "
                     f"(if vela_eq_right then {_FALSE} else {_TRUE}))")
    cases = [
        ("bool", "bool", "!left", negate),
        ("bool", "bool", "left && right", f"(if v_left then v_right else {_FALSE})"),
        ("bool", "bool", "left || right", f"(if v_left then {_TRUE} else v_right)"),
        ("Nat", "bool", "left != right",
         f"(if (Corelib.Init.Nat.eqb v_left v_right) then {_FALSE} else {_TRUE})"),
        ("bool", "bool", "left != right", f"(if {boolean_equal} then {_FALSE} else {_TRUE})"),
        ("Nat", "bool", "left < right", "(Corelib.Init.Nat.ltb v_left v_right)"),
        ("Nat", "bool", "left > right",
         "(let vela_cmp_left := v_left in let vela_cmp_right := v_right in "
         "Corelib.Init.Nat.ltb vela_cmp_right vela_cmp_left)"),
        ("Nat", "bool", "left >= right",
         "(let vela_cmp_left := v_left in let vela_cmp_right := v_right in "
         "Corelib.Init.Nat.leb vela_cmp_right vela_cmp_left)"),
        ("Nat", "Nat", "left - right", "(Corelib.Init.Nat.sub v_left v_right)"),
    ]
    for parameter_type, result_type, expression, term in cases:
        source = (f"module Terms; public {result_type} F({parameter_type} left, "
                  f"{parameter_type} right) => {expression};").encode()
        emitted = vela.translate(source).gallina
        ensure(f":=\n  {term}.\n" in emitted, f"unexpected emitted term for {expression}: {emitted}")
    source = (b"module Terms; public bool F(bool left, bool right) => "
              b"!left || right && false;")
    expected = f"(if {negate} then {_TRUE} else (if v_right then {_FALSE} else {_FALSE}))"
    ensure(f":=\n  {expected}.\n" in vela.translate(source).gallina,
           "logical precedence differs from independent term")
    source = (b"module Names; public Nat Left() => 3; public Nat Right() => 2; "
              b"public bool F(Nat vela_cmp_left, Nat vela_cmp_right) => Left() > Right();")
    emitted = vela.translate(source).gallina
    ensure("(let vela_cmp_left := f_Left in let vela_cmp_right := f_Right in "
           "Corelib.Init.Nat.ltb vela_cmp_right vela_cmp_left)" in emitted,
           "reversed comparison lost source operand order or once-only binding")
    ensure(f"(v_vela_cmp_left : {_NAT}) (v_vela_cmp_right : {_NAT}) : {_BOOL}" in emitted,
           "generated comparison names captured source parameters")


def _semantic_refusals() -> None:
    for expression, fragment in (("!1", "'!'"), ("1 && true", "'&&'"),
                                 ("false || 2", "'||'"), ("true < false", "'<'"),
                                 ("true >= false", "'>='"), ("true > false", "'>'"),
                                 ("1 != false", "same type"), ("true - false", "'-'")):
        _refuses(f"module M; public bool F() => {expression};", "type", fragment)
    _refuses("module M; public Nat F() => 1 < 2;", "type", "returns bool")
    _refuses("module M; public bool F() => false && missing;", "name", "unbound")
    _refuses("module M; public bool F() => true || Missing();", "name", "unknown or forward")
    for operation in ("false && runtime", "true || runtime"):
        _refuses(f"module M; public bool F(bool runtime) {{ const bool Bad = {operation}; return Bad; }}",
                 "unsupported", "runtime binding 'runtime'")
    _refuses("module M; public bool Static(const bool value) => value; "
             "public bool F(bool flag) => false && Static(flag);", "unsupported", "runtime binding 'flag'")
    _refuses("module M; public bool F() => true || (0 && false);", "type", "'&&'")


def _syntax_and_limits() -> None:
    for expression in ("1 < 2 < 3", "1 >= 2 == false", "true &&", "|| false",
                       "-1", "1--2", "true & false", "true | false", "!", "1 <> 2"):
        _refuses(f"module M; public bool F() => {expression};", "syntax")
    prefix = "module M; public bool F() => "
    _refuses(prefix + "!" * 2000 + "true;", "limit")
    source = (prefix + "!" * 63 + "true;").encode()
    ensure(vela.evaluate(source, "F()", "bool").value is False, "bounded prefix chain changed value")
    _refuses(prefix + "!" * 64 + "true;", "limit")
    source = "module M;\r\n// unicode: \U0001f680\r\npublic bool F() => !1;"
    error = _refuses(source, "type", "'!'")
    ensure((error.line, error.column) == (3, 20), "negation diagnostic lost original operator location")
    with patch.object(vela, "MAX_OUTPUT_BYTES", 300):
        _refuses("module M; public bool F(bool left, bool right) => left >= right;", "type")
        _refuses("module M; public bool F(Nat left, Nat right) => left >= right;", "limit")


def _short_circuit() -> None:
    maximum = "9" * vela.MAX_LITERAL_DIGITS
    expensive = f"({maximum} * 2 == 0)"
    for expression, expected in ((f"false && {expensive}", False), (f"true || {expensive}", True)):
        ensure(vela.evaluate(_BASE, expression, "bool").value is expected,
               "skipped logical operand consumed arithmetic budget")
    for expression in (f"true && {expensive}", f"false || {expensive}"):
        try:
            vela.evaluate(_BASE, expression, "bool")
        except vela.VelaError as error:
            ensure(error.kind == "limit", "live expensive operand had the wrong refusal")
        else:
            raise AssertionError("live expensive logical operand escaped numeric budget")
    declarations = ["module Work; public Nat F0(Nat x) => x;"]
    declarations.extend(f"public Nat F{index}(Nat x) => F{index - 1}(x) + F{index - 1}(x);"
                        for index in range(1, 16))
    source = " ".join(declarations).encode()
    ensure(vela.evaluate(source, "false && (F15(0) == 0)", "bool").value is False,
           "short circuit evaluated an exponentially costly call")
    try:
        vela.evaluate(source, "true && (F15(0) == 0)", "bool")
    except vela.VelaError as error:
        ensure(error.kind == "limit", "live expensive call had wrong refusal")
    else:
        raise AssertionError("live expensive call escaped work budget")


def _constants_and_facts() -> None:
    source = (b"module Static; public const Nat Limit = 8 - 3; "
              b"public bool Select(const bool enabled, bool value) { "
              b"const bool disabled = !enabled; return disabled || value; } "
              b"public bool F(bool value) => Select(enabled: true, value: value); "
              b"public const bool Ready = !false && Limit >= 5 && Limit != 0;")
    ensure(vela.evaluate(source, "F(false)", "bool").value is False,
           "static Boolean parameter specialization changed logical value")
    ensure(vela.evaluate(source, "Select(enabled: false, value: false)", "bool").value is True,
           "symbolic static negation failed to specialize")
    emitted = vela.translate(source).gallina
    ensure(f"Definition c_Ready : {_BOOL} :=\n  {_TRUE}." in emitted,
           "combined constant operators did not normalize")
    facts = vela.inspect_source(source)
    ensure(bool(facts["symbols"]) and bool(facts["occurrences"]), "operator increment dropped resolved editor facts")


def cases() -> list[Case]:
    return [Case("independent-operator-values", _values),
            Case("independent-operator-terms-and-hygiene", _terms),
            Case("operator-semantic-negative-neighbors", _semantic_refusals),
            Case("operator-syntax-coordinates-and-bounds", _syntax_and_limits),
            Case("logical-short-circuit-numeric-and-work-budgets", _short_circuit),
            Case("operator-constants-static-parameters-and-facts", _constants_and_facts)]
