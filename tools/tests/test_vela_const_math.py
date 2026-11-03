# SPDX-License-Identifier: Apache-2.0
"""Independent mathematical phase interfaces and specialization neighbors."""

import copy
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_vela_elaborate import (
    _NAT,
    Form,
    Node,
    _binary,
    _boolean,
    _call,
    _choice,
    _Fixture,
    _function_type,
    _inferred_lambda,
    _lambda,
    _let,
    _local_constant,
    _natural,
    _type,
    _variable,
)
from vos import vela_elaborate as language
from vos.vela_ast import VelaError


def _refuses(fixture: _Fixture, kind: str, fragment: str = "") -> None:
    source, response = fixture.response()
    try:
        language.elaborate(source, response)
    except VelaError as error:
        ensure(error.kind == kind and fragment in error.message,
               f"constant interface refusal differs: {error.kind}: {error.message}")
        return
    raise AssertionError("accepted a forbidden constant mathematical interface")


def _square(fixture: _Fixture) -> None:
    fixture.function("Square", _NAT, (("value", _NAT),),
                     _binary("*", _variable("value"), _variable("value")), constant=True)


def _scale(fixture: _Fixture) -> None:
    _square(fixture)
    fixture.function("Scale", _NAT, (("factor", _NAT, True), ("value", _NAT)),
                     _local_constant("multiplier", _NAT, _call("Square", _variable("factor")),
                                     _binary("*", _variable("multiplier"), _variable("value"))), block=True)


def _composed_calls() -> None:
    fixture = _Fixture()
    _scale(fixture)
    fixture.function("RuntimeSquare", _NAT, (("value", _NAT),), _call("Square", _variable("value")))
    fixture.constant("Limit", _NAT, _call("Square", _natural(4)))
    fixture.function("Runtime", _NAT, (("value", _NAT),),
                     _call("Scale", _natural(4), _variable("value"), labels=("factor", "value")))
    source, response = fixture.response()
    output = language.elaborate(source, response).gallina
    runtime = output.split("Definition vela_d4_Runtime", 1)[1]
    ensure("(16 : Corelib.Init.Datatypes.nat)" in runtime and "vela_d1_Scale" not in runtime,
           "static-factor call failed to specialize its constant local to sixteen")
    ensure("vela_d0_Square" in output.split("Definition vela_d2_RuntimeSquare", 1)[1].split("Definition", 1)[0],
           "constant-compatible function lost its runtime call")
    ensure("(16 : Corelib.Init.Datatypes.nat)" in output.split("Definition vela_d3_Limit", 1)[1],
           "constant-compatible function failed in a required-static value")


def _forwarding_and_partial_application() -> None:
    fixture = _Fixture()
    _scale(fixture)
    fixture.function("Forward", _NAT, (("factor", _NAT, True), ("value", _NAT)),
                     _call("Scale", _variable("factor"), _variable("value")))
    fixture.function("Runtime", _NAT, (("value", _NAT),),
                     _call(_call("Forward", _natural(4)), _variable("value")))
    source, response = fixture.response()
    output = language.elaborate(source, response).gallina.split("Definition vela_d3_Runtime", 1)[1]
    ensure("(16 : Corelib.Init.Datatypes.nat)" in output,
           "forwarded or partially applied static parameter lost specialization")
    fixture = _Fixture()
    _scale(fixture)
    fixture.function("Bad", _NAT, (("factor", _NAT),), _call("Scale", _variable("factor"), _natural(2)))
    _refuses(fixture, "type", "nonstatic binding 'factor'")


def _runtime_arguments_remain_once() -> None:
    for runtime_first in (False, True):
        fixture = _Fixture()
        _square(fixture)
        parameters = ((("value", _NAT), ("factor", _NAT, True)) if runtime_first else
                      (("factor", _NAT, True), ("value", _NAT)))
        fixture.function("Twice", _NAT, parameters,
                         _binary("+", _binary("*", _variable("factor"), _variable("value")), _variable("value")))
        runtime = _call("Square", _variable("value"))
        invocation = (_call(_call("Twice", runtime), _natural(4)) if runtime_first else
                      _call("Twice", _natural(4), runtime))
        fixture.function("Use", _NAT, (("value", _NAT),), invocation)
        output = language.elaborate(*fixture.response()).gallina.split("Definition vela_d2_Use", 1)[1]
        ensure(output.count("vela_d0_Square") == 1 and "(let " in output,
               "specialization duplicated or reinterpreted the once-evaluated runtime argument")


def _higher_order_requirements() -> None:
    for inferred in (False, True):
        fixture = _Fixture()
        static_callable = _function_type((("amount", _NAT, True),), _NAT)
        fixture.function("Apply", _NAT, (("operation", static_callable),),
                         _call(_variable("operation"), _natural(3)))
        callback = (_inferred_lambda(("amount",), _variable("amount")) if inferred else
                    _lambda((("amount", _NAT, True),), _variable("amount")))
        fixture.function("Use", _NAT, (), _call("Apply", callback))
        language.elaborate(*fixture.response())
    fixture = _Fixture()
    static_callable = _function_type((("amount", _NAT, True),), _NAT)
    fixture.function("Bad", _NAT, (("operation", static_callable), ("runtime", _NAT)),
                     _call(_variable("operation"), _variable("runtime")))
    _refuses(fixture, "type", "nonstatic binding 'runtime'")
    fixture = _Fixture()
    ordinary_callable = _function_type((("amount", _NAT),), _NAT)
    fixture.function("Forget", ordinary_callable, (("operation", static_callable),), _variable("operation"))
    _refuses(fixture, "type", "constant-parameter requirements differ")


def _static_callback_value() -> None:
    fixture = _Fixture()
    _square(fixture)
    callback_type = _function_type((("amount", _NAT),), _NAT)
    fixture.function("ApplyStatic", _NAT, (("operation", callback_type, True), ("value", _NAT)),
                     _local_constant("seed", _NAT, _call(_variable("operation"), _natural(3)),
                                     _binary("*", _variable("seed"), _variable("value"))), block=True)
    fixture.function("Use", _NAT, (("value", _NAT),),
                     _call("ApplyStatic", _variable("Square"), _variable("value")))
    output = language.elaborate(*fixture.response()).gallina.split("Definition vela_d2_Use", 1)[1]
    ensure("(9 : Corelib.Init.Datatypes.nat)" in output,
           "a static callable value did not compute the demanded scalar constant")
    fixture.function("Bad", _NAT, (("operation", callback_type), ("value", _NAT)),
                     _call("ApplyStatic", _variable("operation"), _variable("value")))
    _refuses(fixture, "type", "nonstatic binding 'operation'")


def _generic_and_dependent_parameters() -> None:
    fixture = _Fixture()
    fixture.definition("Select", _type("T"), (("index", _NAT, True), ("value", _type("T"))),
                       _variable("value"), generics=(("type", "T", None),))
    fixture.function("Use", _NAT, (("value", _NAT),),
                     _call("Select", _natural(0), _variable("value"), generics=(_NAT,)))
    vector = _type("Vec", _NAT, _variable("length"))
    fixture.definition("Vector", vector, (("length", _NAT, True), ("value", vector)), _variable("value"))
    one = _type("Vec", _NAT, _natural(1))
    fixture.function("UseVector", one, (("value", one),),
                     _call("Vector", _natural(1), _variable("value"), labels=("length", "value")))
    language.elaborate(*fixture.response())
    fixture.function("Bad", _NAT, (("runtime", _NAT),),
                     _call("Select", _variable("runtime"), _natural(1), generics=(_NAT,)))
    _refuses(fixture, "type", "nonstatic binding 'runtime'")


def _dependency_neighbors() -> None:
    def ignored(runtime: Form) -> Form:
        return _call("Ignore", runtime)

    for form in (_variable("runtime"), ignored(_variable("runtime")),
                 _choice(_boolean(False), _variable("runtime"), _natural(2))):
        fixture = _Fixture()
        fixture.function("Ignore", _NAT, (("unused", _NAT),), _natural(2))
        fixture.function("Require", _NAT, (("amount", _NAT, True),), _variable("amount"))
        fixture.function("Bad", _NAT, (("runtime", _NAT),), _call("Require", form))
        _refuses(fixture, "type", "nonstatic binding 'runtime'")
    fixture = _Fixture()
    fixture.function("Require", _NAT, (("amount", _NAT, True),), _variable("amount"))
    fixture.function("Alias", _NAT, (("amount", _NAT, True),),
                     _let("saved", _variable("amount"), _call("Require", _variable("saved"))))
    _refuses(fixture, "type", "nonstatic binding 'saved'")


def _qualifier_source_binding() -> None:
    fixture = _Fixture()
    _scale(fixture)
    source, response = fixture.response()
    for mutation in ("missing-function", "repeated-function", "missing-parameter", "false-parameter", "invented-parameter", "malformed-parameter"):
        changed = copy.deepcopy(response)
        declarations = cast("list[Node]", cast("Node", changed["ast"])["declarations"])
        square, scale = declarations
        parameters = cast("list[Node]", scale["parameters"])
        if mutation == "missing-function":
            square["modifiers"] = ["public"]
        elif mutation == "repeated-function":
            square["modifiers"] = ["public", "const", "const"]
        elif mutation == "missing-parameter":
            parameters[0].pop("const")
        elif mutation == "false-parameter":
            parameters[0]["const"] = False
        elif mutation == "invented-parameter":
            parameters[1]["const"] = True
        else:
            parameters[0]["const"] = "true"
        try:
            language.elaborate(source, changed)
        except VelaError as error:
            ensure(error.kind == "protocol", f"{mutation} escaped source-protocol validation")
        else:
            raise AssertionError(f"accepted {mutation} qualifier forgery")


def _symbolic_limits() -> None:
    fixture = _Fixture()
    _scale(fixture)
    fixture.function("Use", _NAT, (("value", _NAT),), _call("Scale", _natural(4), _variable("value")))
    source, response = fixture.response()
    with patch.object(language, "MAX_REDUCTIONS", 2):
        try:
            language.elaborate(source, response)
        except VelaError as error:
            ensure(error.kind == "limit", "bounded specialization did not return a limit refusal")
        else:
            raise AssertionError("specialization ignored its reduction budget")
    with patch.object(language, "MAX_CONSTANT_NAT", 15):
        _refuses(fixture, "limit", "representation bound")


def cases() -> list[Case]:
    return [Case("const-functions-static-and-runtime-application", _composed_calls),
            Case("const-parameter-forwarding-and-partial-application", _forwarding_and_partial_application),
            Case("specialization-keeps-runtime-arguments-once", _runtime_arguments_remain_once),
            Case("const-callable-types-inferred-lambdas-and-erasure-refusal", _higher_order_requirements),
            Case("static-callable-values-are-distinct-from-callable-parameter-contracts", _static_callback_value),
            Case("generic-and-dependent-constant-parameter-substitution", _generic_and_dependent_parameters),
            Case("const-argument-whole-dependency-refusals", _dependency_neighbors),
            Case("const-qualifier-complete-source-provenance", _qualifier_source_binding),
            Case("bounded-symbolic-static-specialization", _symbolic_limits)]
