# SPDX-License-Identifier: Apache-2.0
"""Independent syntax-word refusals at the mathematical consumer boundary."""

import copy
from typing import cast

from tests.harness import Case, ensure
from tests.test_vela_elaborate import (
    _NAT,
    Form,
    Node,
    _assert,
    _binary,
    _Fixture,
    _function_type,
    _lambda,
    _natural,
    _type,
    _variable,
)
from vos.vela_ast import VelaError
from vos.vela_elaborate import elaborate


def _quantifier(word: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(word + " ")
        parameters = fixture.parameters((("value", _NAT),))
        fixture.write(" => ")
        value = _binary("==", _variable("value"), _variable("value"))(fixture)
        return fixture.node("quantifier", start, quantifier=word, parameters=parameters, value=value)
    return form


def _callable_mode_type(mode: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(mode)
        params = fixture.parameters((("value", _NAT),))
        fixture.write(" -> ")
        output = _NAT(fixture)
        return fixture.node("function_type", start, mode=mode, generics=[], parameters=params,
                            result=output, captures=None, effects=[], contracts=[])
    return form


def _fixture(word: str = "forall") -> _Fixture:
    fixture = _Fixture("ProtocolWords")
    fixture.definition("Identity", _function_type((("value", _NAT),), _NAT), (),
                       _lambda((("value", _NAT),), _variable("value")))
    fixture.definition("Generic", _type("T"), (("value", _type("T")),), _variable("value"),
                       generics=(("type", "T", None),))
    fixture.theorem("Reflexive", (), _quantifier(word),
                    _assert(_binary("==", _variable("value"), _variable("value"))))
    return fixture


def _malformed_words() -> None:
    source, response = _fixture().response()
    elaborate(source, response)
    for role in ("callable", "generic", "quantifier"):
        for malformed in (None, False, 7, [], {}, "unknown", "\ud800"):
            changed = copy.deepcopy(response)
            declarations = cast("list[Node]", cast("Node", changed["ast"])["declarations"])
            if role == "callable":
                node, field = cast("Node", declarations[0]["result"]), "mode"
            elif role == "generic":
                node, field = cast("list[Node]", declarations[1]["generics"])[0], "mode"
            else:
                contract = cast("list[Node]", declarations[2]["contracts"])[0]
                node, field = cast("Node", contract["value"]), "quantifier"
            node[field] = malformed
            try:
                elaborate(source, changed)
            except VelaError as error:
                ensure(error.kind == "protocol" and "syntax word" in error.message,
                       f"malformed {role} word lost its protocol refusal: {error.kind}")
            else:
                raise AssertionError(f"malformed {role} word was accepted")
    ensure(elaborate(source, response).module == "ProtocolWords",
           "a refused syntax word damaged the next valid elaboration")


def _supported_and_unsupported_words() -> None:
    fixture = _fixture()
    output = elaborate(*fixture.response()).gallina
    ensure("Definition vela_d2_Reflexive" in output and "Corelib.Init.Logic.eq_refl" in output,
           "universal proof failed to emit its explicit equality witness")
    try:
        elaborate(*_fixture("exists").response())
    except VelaError as error:
        ensure(error.kind == "name",
               "an unwitnessed existential assertion did not reject the unbound quantifier variable")
    else:
        raise AssertionError("existential binder was treated as universally introduced")
    ex_fixture = _Fixture("ExistentialWitness")
    ex_fixture.theorem("HasWitness", (), _quantifier("exists"),
                       _assert(_quantifier("exists"), by=_natural(0)))
    ex_output = elaborate(*ex_fixture.response()).gallina
    ensure("@Corelib.Init.Logic.ex " in ex_output and "@Corelib.Init.Logic.ex_intro " in ex_output,
           "existential proof failed to emit ex and ex_intro")
    fnonce_fixture = _Fixture("UnsupportedCallableMode")
    fnonce_fixture.definition("Once", _callable_mode_type("FnOnce"), (),
                              _lambda((("value", _NAT),), _variable("value")))
    try:
        elaborate(*fnonce_fixture.response())
    except VelaError as error:
        ensure(error.kind == "unsupported" and "pure Fn" in error.message,
               "a source-bound FnOnce callable failed before its semantic boundary")
    else:
        raise AssertionError("FnOnce callable mode acquired a mathematical interpretation")
    source, response = fixture.response()
    declarations = cast("list[Node]", cast("Node", response["ast"])["declarations"])
    cast("Node", declarations[0]["result"])["mode"] = "FnOnce"
    try:
        elaborate(source, response)
    except VelaError as error:
        ensure(error.kind == "protocol", "a forged valid syntax word escaped source binding")
    else:
        raise AssertionError("a callable mode absent from source was accepted")


def cases() -> list[Case]:
    return [Case("mathematical-malformed-syntax-words", _malformed_words),
            Case("mathematical-word-semantics-and-source-binding", _supported_and_unsupported_words)]
