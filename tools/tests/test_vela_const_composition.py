# SPDX-License-Identifier: Apache-2.0
"""Independent compositional const values, static inputs and source-bound flags."""

import copy
import hashlib
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela


def _refuses(source: str, kind: str, message: str) -> None:
    try:
        vela.translate(source.encode())
    except vela.VelaError as error:
        ensure(error.kind == kind and message in error.message,
               f"wrong const-composition refusal: {error.kind}: {error.message}")
    else:
        raise AssertionError("accepted forbidden const composition")


def _both_phases_and_legacy_pure_calls() -> None:
    source = b"""module Compose;
public const Nat Square(Nat input) => input * input;
public Nat Earlier(Nat input) => input + 1;
public const Nat Limit = Square(Earlier(3));
public Nat Runtime(Nat input) => Square(input);
"""
    result = vela.translate(source).gallina
    ensure("Definition c_Limit : Corelib.Init.Datatypes.nat :=\n  (16 :" in result,
           "composed constant call did not compute sixteen")
    ensure("Definition f_Runtime (v_input :" in result and "(f_Square v_input)." in result,
           "const modifier made an ordinary runtime call unavailable")
    facts = vela.inspect_source(source)
    symbols = cast("list[dict[str, object]]", facts["symbols"])
    square = next(item for item in symbols if item["name"] == "Square")
    ensure(square["detail"] == "public const Nat Square(Nat input)",
           "const function lost its explicit editor signature")


def _specialized_static_input_and_runtime_data() -> None:
    source = b"""module Compose;
public const Nat Square(Nat input) => input * input;
public Nat Scale(const Nat factor, Nat value) {
    const Nat multiplier = Square(factor);
    return multiplier * value;
}
public Nat Forward(const Nat factor, Nat value) => Scale(factor: factor, value: value);
public Nat Runtime(Nat value) => Forward(factor: 4, value: value + 1);
public const Nat First = Scale(2, 3);
public const Nat Second = Scale(5, 3);
"""
    result = vela.translate(source).gallina
    runtime = result.split("Definition f_Runtime", 1)[1].split("Definition c_First", 1)[0]
    ensure("(16 : Corelib.Init.Datatypes.nat)" in runtime and "f_Scale" not in runtime
           and "f_Forward" not in runtime and "f_Square" not in runtime,
           "closed static forwarding did not specialize the multiplier")
    ensure(runtime.count("Corelib.Init.Nat.add") == 1,
           "runtime argument was duplicated during static specialization")
    ensure("Definition c_First : Corelib.Init.Datatypes.nat :=\n  (12 :" in result
           and "Definition c_Second : Corelib.Init.Datatypes.nat :=\n  (75 :" in result,
           "a dependent local constant was cached across different static instantiations")
    symbols = cast("list[dict[str, object]]", vela.inspect_source(source)["symbols"])
    ensure(next(item for item in symbols if item["name"] == "multiplier")["detail"]
           == "const Nat multiplier", "symbolic static local pretended to have a closed value")
    ensure(next(item for item in symbols if item["name"] == "factor")["detail"]
           == "const factor: Nat", "static parameter lost its availability promise")
    ensure(sum(item["name"] == "multiplier" for item in symbols) == 1,
           "specialization repeated source declarations in editor facts")


def _static_argument_dependency_and_typing_refusals() -> None:
    prefix = "module M; public Nat Select(const Nat factor, Nat value) => value; "
    for body in ("return Select(runtime, 1);",
                 "return Select(factor: runtime, value: 1);",
                 "let saved = 4; return Select(saved, 1);",
                 "if (false) { return Select(runtime, 1); } else { return 0; }"):
        _refuses(prefix + "public Nat Use(Nat runtime) { " + body + " }",
                 "unsupported", "runtime binding")
    _refuses("module M; public Nat Ignore(Nat value) => 0; "
             "public Nat Select(const Nat factor) => factor; "
             "public Nat Use(Nat runtime) => Select(Ignore(runtime));",
             "unsupported", "runtime binding")
    _refuses(prefix + "public Nat Use() => Select(true, 1);", "type", "must be Nat")
    _refuses(prefix + "public Nat Use() => Select(value: 4, factor: 1);", "name", "must name parameter 'factor'")
    _refuses("module M; public const Nat F(Nat value) { const Nat N = value; return N; }",
             "unsupported", "runtime binding")
    _refuses("module M; public const Nat F(const Nat value) { value = 3; return value; }",
             "unsupported", "cannot reassign const")
    for source in ("public const const Nat F() => 1;", "public Nat F(const const Nat x) => x;"):
        _refuses("module M; " + source, "syntax", "repeated const")


def _hygienic_once_only_arguments() -> None:
    source = b"""module Hygiene;
public Nat Helper(const Nat factor, Nat second, Nat first) {
    let value = first + first;
    return value + second + factor;
}
public Nat Call(Nat first, Nat second) => Helper(2, first + 1, second + 3);
"""
    result = vela.translate(source).gallina.split("Definition f_Call", 1)[1]
    ensure(result.count("Corelib.Init.Nat.add v_first") == 1
           and result.count("Corelib.Init.Nat.add v_second") == 1,
           "runtime actuals were duplicated or captured by callee binders")
    first_actual = result.index("Corelib.Init.Nat.add v_first")
    second_actual = result.index("Corelib.Init.Nat.add v_second")
    ensure(first_actual < second_actual, "specialization reordered runtime argument evaluation")
    ensure("vela_arg_0" in result and "vela_arg_1" in result,
           "specialization failed to generate independent argument binders")


def _bounded_specialization() -> None:
    source = b"module M; public Nat F(const Nat n, Nat x) { const Nat N = n * n; return N + x; } " \
             b"public Nat Use(Nat x) => F(4, x);"
    with patch.object(vela, "MAX_STATIC_WORK", 4):
        _refuses(source.decode(), "limit", "budget")
    with patch.object(vela, "MAX_STATIC_DEPTH", 0):
        _refuses(source.decode(), "limit", "budget")
    with patch.object(vela, "MAX_OUTPUT_BYTES", 64):
        _refuses(source.decode(), "limit", "output")


def _independent_const_tree(source: bytes) -> dict[str, object]:
    def node(kind: str, start: int, end: int, **fields: object) -> dict[str, object]:
        return {"kind": kind, "span": [start, end], **fields}
    def name(text: str, start: int) -> dict[str, object]:
        return {"text": text, "span": [start, start + len(text)]}
    declaration = source.index(b"public")
    result = source.index(b"Nat", declaration)
    function_name = source.index(b"F(", result)
    parameter = source.index(b"const", function_name)
    parameter_type = source.index(b"Nat", parameter)
    parameter_name = source.index(b"input", parameter_type)
    arrow = source.index(b"=>", parameter_name)
    value = source.index(b"input", arrow)
    parameter_node = node("parameter", parameter, parameter_name + 5,
                          name=name("input", parameter_name),
                          type=node("type", parameter_type, parameter_type + 3, name="Nat"))
    parameter_node["const"] = True
    function = node("function", declaration, len(source), name=name("F", function_name),
                    result=node("type", result, result + 3, name="Nat"), parameters=[parameter_node],
                    body=node("expression_body", arrow, len(source),
                              value=node("name", value, value + 5, name=name("input", value))))
    function["const"] = True
    module = source.index(b"module")
    return {"schema": 1, "source_sha256": hashlib.sha256(source).hexdigest(),
            "ast": node("file", module, len(source), name=name("M", module + 7), declarations=[function])}


def _independent_qualifier_protocol() -> None:
    for newline in (b"\n", b"\r\n", b"\r"):
        source = "// café".encode() + newline + b"module M; public const Nat F(const Nat input) => input;"
        response = _independent_const_tree(source)
        with patch.object(vela, "_tokens", side_effect=AssertionError("Python parser fallback")):
            actual = vela.translate_ast(source, response)
        ensure(actual == vela.translate(source), "constant qualifiers changed pure-route agreement")
        for function_flag in (False, True):
            for corruption in ("missing", "false", "integer", "string"):
                changed = copy.deepcopy(response)
                ast = cast("dict[str, object]", changed["ast"])
                function = cast("list[dict[str, object]]", ast["declarations"])[0]
                target = function if function_flag else cast("list[dict[str, object]]", function["parameters"])[0]
                if corruption == "missing":
                    target.pop("const")
                else:
                    target["const"] = {"false": False, "integer": 1, "string": "const"}[corruption]
                try:
                    vela.translate_ast(source, changed)
                except (TypeError, ValueError):
                    pass
                else:
                    raise AssertionError(f"accepted {corruption} {'function' if function_flag else 'parameter'} qualifier")
        for remove in (b"public const", b"F(const"):
            changed_source = source.replace(remove, remove.replace(b"const", b"     "))
            changed = copy.deepcopy(response)
            changed["source_sha256"] = hashlib.sha256(changed_source).hexdigest()
            try:
                vela.translate_ast(changed_source, changed)
            except ValueError:
                pass
            else:
                raise AssertionError("accepted an invented qualifier absent from source")


def cases() -> list[Case]:
    return [Case("constant-function-runtime-static-and-legacy-calls", _both_phases_and_legacy_pure_calls),
            Case("symbolic-static-parameters-and-closed-specialization", _specialized_static_input_and_runtime_data),
            Case("static-argument-dependency-type-and-immutability-refusals", _static_argument_dependency_and_typing_refusals),
            Case("hygienic-left-to-right-once-only-runtime-arguments", _hygienic_once_only_arguments),
            Case("bounded-closed-specialization", _bounded_specialization),
            Case("independent-const-function-and-parameter-provenance", _independent_qualifier_protocol)]
