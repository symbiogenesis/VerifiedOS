# SPDX-License-Identifier: Apache-2.0
"""Independent source-bound generic type naming and semantic refusal controls."""

import copy
from collections.abc import Callable
from typing import cast

from tests.harness import Case, ensure
from tests.test_vela_elaborate import (
    Form,
    Node,
    _assert,
    _binary,
    _boolean,
    _Fixture,
    _match_expr,
    _natural,
    _pat_bind,
    _pat_bool,
    _pat_wild,
    _type,
    _variable,
)
from vos.vela import (
    VelaError,
    authoring,
)
from vos.vela import (
    elaborate as language,
)
from vos.vela import (
    mathematical as adapter,
)


def _identity(fixture: _Fixture, spelling: str, index: int) -> None:
    fixture.definition(f"Identity{index}", _type(spelling), (("value", _type(spelling)),),
                       _variable("value"), generics=(("type", spelling, None),))


def _refuses(operation: Callable[[], object], kind: str) -> None:
    try:
        operation()
    except VelaError as error:
        ensure(error.kind == kind, f"naming inspection changed semantic refusal kind: {error.kind}")
        return
    raise AssertionError("naming inspection accepted invalid source")


def _type_names_and_value_indices() -> None:
    fixture = _Fixture("NamingRoles")
    for index, spelling in enumerate(("T", "TValue", "Element")):
        _identity(fixture, spelling, index)
    fixture.definition("Copy", _type("Vec", _type("T"), _variable("n")),
                       (("values", _type("Vec", _type("T"), _variable("n"))),), _variable("values"),
                       generics=(("type", "T", None), ("ghost", "n", _type("Nat"))))
    fixture.definition("ValueParameter", _type("Nat"), (), _natural(0),
                       generics=(("ghost", "N", _type("Nat")),))
    source, parsed = fixture.response()
    before = bytes(source)
    result = adapter.inspect_source(source, parsed)
    ensure(result.findings == (), "valid type names or generic value indices received VELA105")
    ensure(result.gallina == language.elaborate(source, parsed).gallina and source == before,
           "advisory naming inspection changed source or mathematical terms")


def _lowercase_underscore_names_and_source_order() -> None:
    fixture = _Fixture("NamingSites")
    for index, spelling in enumerate(("t", "t_value", "_T", "T_value")):
        _identity(fixture, spelling, index)
    source, parsed = fixture.response()
    result = adapter.inspect_source(source, parsed)
    expected: list[tuple[str, int, int]] = []
    text = source.decode("utf-8")
    for spelling in ("t", "t_value", "_T", "T_value"):
        prefix = text[:text.index(f"<{spelling}>") + 1]
        expected.append(("VELA105", prefix.count("\n") + 1, len(prefix.rsplit("\n", 1)[-1]) + 1))
    ensure([(item.code, item.line, item.column) for item in result.findings] == expected,
           "generic naming warnings lost source order or original binder coordinates")
    ensure(all("PascalCase" in item.message and spelling in item.message
               for item, spelling in zip(result.findings, ("t", "t_value", "_T", "T_value"), strict=True)),
           "generic naming warning omitted its actual name or required convention")
    ensure(result.gallina == language.elaborate(source, parsed).gallina,
           "style warnings changed the mathematical compiler's emitted interpretation")


def _generic_callable(spelling: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("Fn")
        generic_nodes = fixture.generics((("type", spelling, None),))
        parameters = fixture.parameters((("value", _type(spelling)),))
        fixture.write(" -> ")
        result = _type(spelling)(fixture)
        return fixture.node("function_type", start, mode="Fn", generics=generic_nodes,
                            parameters=parameters, result=result, captures=None, effects=[], contracts=[])
    return form


def _nested_callable_and_alias_binders() -> None:
    fixture = _Fixture("NestedNaming")
    fixture.alias("Transform", _generic_callable("item"))
    fixture.alias("Words", _type("Vec", _type("element"), _variable("n")),
                  generics=(("type", "element", None), ("ghost", "n", _type("Nat"))))
    result = adapter.inspect_source(*fixture.response())
    ensure(len(result.findings) == 2 and "item" in result.findings[0].message
           and "element" in result.findings[1].message,
           "naming inspection missed nested callable or alias generic type binders")


def _unicode_and_mixed_newline_coordinates() -> None:
    fixture = _Fixture("UnicodeNaming")
    fixture.write("\r\n// supplementary comment: \U0001f680\r\n")
    _identity(fixture, "t", 0)
    result = adapter.inspect_source(*fixture.response())
    ensure(len(result.findings) == 1 and result.findings[0].line == 5
           and result.findings[0].column == 31,
           "Unicode comments or CRLF changed generic binder's character coordinates")


def _invalid_source_and_protocol_never_report_partial_warnings() -> None:
    fixture = _Fixture("NoPartialNaming")
    _identity(fixture, "t", 0)
    fixture.theorem("Impossible", (), _binary("==", _natural(1), _natural(2)),
                    _assert(_binary("==", _natural(1), _natural(2))))
    _refuses(lambda: adapter.inspect_source(*fixture.response()), "type")
    good = _Fixture("BoundNaming")
    _identity(good, "t", 0)
    source, parsed = good.response()
    stale = copy.deepcopy(parsed)
    stale["source_sha256"] = "0" * 64
    _refuses(lambda: adapter.inspect_source(source, stale), "protocol")
    forged = copy.deepcopy(parsed)
    ast = cast("Node", forged["ast"])
    declaration = cast("list[Node]", ast["declarations"])[0]
    generic = cast("list[Node]", declaration["generics"])[0]
    cast("Node", generic["name"])["text"] = "Unwritten"
    _refuses(lambda: adapter.inspect_source(source, forged), "protocol")


def _pattern_constructors_and_unreachable_arms() -> None:
    fixture = _Fixture("PatternLint")
    fixture.record("Token", ())
    fixture.definition(
        "ShadowAndUnreachable",
        _type("Nat"),
        (("flag", _type("bool")),),
        _match_expr(
            _variable("flag"),
            (
                (_pat_bind("None"), _natural(1)),
                (_pat_bind("Token"), _natural(2)),
                (_pat_wild(), _natural(3)),
            ),
        ),
    )
    fixture.definition(
        "BoolExhaustive",
        _type("Nat"),
        (("flag", _type("bool")),),
        _match_expr(
            _variable("flag"),
            (
                (_pat_bool(True), _natural(1)),
                (_pat_bool(False), _natural(2)),
                (_pat_wild(), _natural(3)),
            ),
        ),
    )
    source, parsed = fixture.response()
    result = adapter.inspect_source(source, parsed)
    ensure([item.code for item in result.findings] == ["VELA106", "VELA106", "VELA106", "VELA106"],
           f"expected four VELA106 pattern warnings, got {result.findings!r}")
    ensure("shadows constructor 'None'; write 'None()'" in result.findings[0].message,
           "first VELA106 omitted constructor-shadowing guidance for None")
    ensure("shadows constructor 'Token'; write 'Token()'" in result.findings[1].message,
           "second VELA106 omitted constructor-shadowing guidance for declared record")
    ensure("unreachable match arm after bare pattern binder 'None'" in result.findings[2].message
           and "unreachable match arm; earlier patterns already cover this case" in result.findings[3].message,
           "unreachable match arms did not emit VELA106")
    previewed = authoring.preview_pattern_constructors(source, parsed)
    ensure(b"None() => 1, Token() => 2, _ => 3" in previewed,
           "constructor-pattern preview did not rewrite bare nullary constructor binders")
    wrong = _Fixture("IllTypedUnreachable")
    wrong.definition(
        "BadUnreachable",
        _type("Nat"),
        (("flag", _type("bool")),),
        _match_expr(
            _variable("flag"),
            (
                (_pat_bool(True), _natural(1)),
                (_pat_bool(False), _natural(2)),
                (_pat_wild(), _boolean(True)),
            ),
        ),
    )
    _refuses(lambda: adapter.inspect_source(*wrong.response()), "type")


def cases() -> list[Case]:
    return [Case("generic-type-capitals-and-value-index-role-distinction", _type_names_and_value_indices),
            Case("generic-type-lowercase-underscore-source-order-and-unmodified-terms", _lowercase_underscore_names_and_source_order),
            Case("generic-type-nested-callable-and-alias-binders", _nested_callable_and_alias_binders),
            Case("generic-type-unicode-and-mixed-newline-source-coordinates", _unicode_and_mixed_newline_coordinates),
            Case("generic-type-invalid-proof-source-and-protocol-refusals", _invalid_source_and_protocol_never_report_partial_warnings),
            Case("pattern-constructor-shadowing-and-unreachable-arms", _pattern_constructors_and_unreachable_arms)]
