# SPDX-License-Identifier: Apache-2.0
"""Independent located fixtures for the native mathematical console adapter."""

import copy
import hashlib
import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_vela_elaborate import (
    Form,
    Node,
    _binary,
    _boolean,
    _call,
    _Fixture,
    _function_type,
    _inferred_lambda,
    _lambda,
    _natural,
    _type,
    _variable,
)
from vos import vela_elaborate as language
from vos import vela_mathematical as adapter
from vos.vela import StaticEvaluation, ValueType, VelaError


def _module() -> _Fixture:
    fixture = _Fixture("MathematicalConsole")
    fixture.definition("Identity", _type("T"), (("value", _type("T")),), _variable("value"),
                       generics=(("type", "T", None),))
    fixture.definition("Samples", _type("Vec", _type("Nat"), _natural(2)), (),
                       _call("VCons", _natural(7),
                             _call("VCons", _natural(8), _call("VNil", generics=(_type("Nat"),)))))
    fixture.definition("Copy", _type("Vec", _type("T"), _variable("n")),
                       (("values", _type("Vec", _type("T"), _variable("n"))),), _variable("values"),
                       generics=(("type", "T", None), ("ghost", "n", _type("Nat"))))
    return fixture


def _probe(form: Form, value_type: ValueType = "Nat") -> tuple[str, bytes, Node]:
    fixture = _Fixture("Playground")
    fixture.text = "module "
    fixture.start = 0
    fixture.module = fixture.name("Playground")
    fixture.write(";\n")
    start = fixture.offset
    fixture.write("public const ")
    annotation = _type(value_type)(fixture)
    fixture.write(" ")
    name = fixture.name("__vela_console_result")
    fixture.write(" =\n")
    expression_start = fixture.offset
    initializer = form(fixture)
    expression = fixture.text.encode()[expression_start:].decode()
    fixture.write("\n;")
    fixture.declarations.append(fixture.node("constant", start, name=name, type=annotation,
                                             value=initializer, modifiers=["public"]))
    source, parsed = fixture.response()
    return expression, source, parsed


def _evaluate(fixture: _Fixture, form: Form, value_type: ValueType = "Nat") -> StaticEvaluation:
    expression, probe, syntax = _probe(form, value_type)

    def parse(raw: bytes) -> object:
        ensure(raw == probe, "console changed the independently constructed constant source")
        return syntax

    return language.evaluate(*fixture.response(), expression, value_type, parse=parse)


def _refuses(operation: Callable[[], object], kind: str, *, expression: bool = True) -> VelaError:
    try:
        operation()
    except VelaError as error:
        ensure(error.kind == kind, f"expected {kind}, got {error.kind}: {error.message}")
        ensure(error.message.startswith("expression:") == expression,
               "diagnostic lost its original-source or expression context")
        return error
    raise AssertionError("accepted an invalid mathematical console request")


def _dependent_values() -> None:
    fixture = _module()
    before = fixture.response()[0]
    vectors = _call("Copy", _call("Samples"))
    second = _call("FSucc", _call("FZero", generics=(_natural(0),)))
    ensure(_evaluate(fixture, _call("At", vectors, second)) == StaticEvaluation("Nat", 8),
           "dependent lookup returned the wrong element")
    ensure(_evaluate(fixture, _call("At", vectors, _call("FZero", generics=(_natural(1),))))
           == StaticEvaluation("Nat", 7), "first dependent element changed")
    ensure(_evaluate(fixture, _call("Identity", _boolean(False)), "bool")
           == StaticEvaluation("bool", False), "false was confused with absent reduction")
    ensure(_evaluate(fixture, _call("Identity", _natural(42))) == StaticEvaluation("Nat", 42),
           "fresh generic natural instantiation failed")
    ensure(_evaluate(fixture, _binary("==", _call("At", vectors, second), _natural(8)), "bool")
           == StaticEvaluation("bool", True), "dependent result comparison changed")
    ensure(fixture.response()[0] == before, "evaluation changed original source bytes")


def _higher_order_and_static() -> None:
    fixture = _module()
    fixture.constant("__vela_console_result", _type("Nat"), _natural(41))
    ensure(_evaluate(fixture, _binary("+", _variable("__vela_console_result"), _natural(1)))
           == StaticEvaluation("Nat", 42), "synthetic binder captured an authored constant")
    fixture.definition("Apply", _type("U"),
                       (("function", _function_type((("value", _type("T")),), _type("U"))),
                        ("value", _type("T"))),
                       _call("function", _variable("value")),
                       generics=(("type", "T", None), ("type", "U", None)))
    value = _call("Apply", _inferred_lambda(("value",), _binary("+", _variable("value"), _natural(1))),
                  _natural(41))
    ensure(_evaluate(fixture, value) == StaticEvaluation("Nat", 42), "higher-order reduction changed")
    direct = _call(_lambda((("value", _type("Nat")),), _variable("value")), _natural(5))
    ensure(_evaluate(fixture, direct) == StaticEvaluation("Nat", 5), "typed lambda reduction changed")


def _semantic_refusals() -> None:
    fixture = _module()
    wrong = _call("At", _call("Samples"), _call("FZero", generics=(_natural(2),)))
    _refuses(lambda: _evaluate(fixture, wrong), "type")
    _refuses(lambda: _evaluate(fixture, _boolean(True)), "type")
    _refuses(lambda: _evaluate(fixture, _variable("missing")), "name")
    wrong_proof = _module()
    wrong_proof.theorem("False", (), _binary("==", _natural(0), _natural(1)),
                        _call("Refl", _natural(0)))
    called = False

    def parse(_raw: bytes) -> object:
        nonlocal called
        called = True
        raise AssertionError("expression parsed before the complete original proof was checked")

    _refuses(lambda: language.evaluate(*wrong_proof.response(), "1", "Nat", parse=parse),
             "type", expression=False)
    ensure(not called, "invalid original source reached expression parsing")


def _injection_and_coordinates() -> None:
    fixture = _module()
    for expression in ("1; public const Nat Injected = 2", "1; //", "1; /*", "", "1 +"):
        def parse(raw: bytes, expression: str = expression) -> object:
            ensure(raw.endswith(expression.encode() + b"\n;"), "expression bytes were rewritten")
            raise VelaError("syntax", 4, 2, "independent native syntax refusal")

        error = _refuses(lambda expression=expression, parse=parse: language.evaluate(
            *fixture.response(), expression, "Nat", parse=parse), "syntax")
        ensure(error.line == 1 and error.column <= len(expression) + 1,
               "synthetic-module coordinate escaped the console expression")
    expression, probe, syntax = _probe(_natural(1))
    altered = copy.deepcopy(syntax)
    cast("dict[str, object]", altered["ast"])["declarations"] = []
    _refuses(lambda: language.evaluate(*fixture.response(), expression, "Nat", parse=lambda _: altered),
             "protocol")
    stale = copy.deepcopy(syntax)
    stale["source_sha256"] = "0" * 64
    _refuses(lambda: language.evaluate(*fixture.response(), expression, "Nat", parse=lambda _: stale),
             "protocol")
    ensure(probe.endswith(b"\n;"), "probe lacks a non-swallowable terminator")


def _parsed_declaration_injection() -> None:
    fixture = _Fixture("Playground")
    fixture.text = "module "
    fixture.start = 0
    fixture.module = fixture.name("Playground")
    fixture.write(";\n")
    start = fixture.offset
    fixture.write("public const ")
    annotation = _type("Nat")(fixture)
    fixture.write(" ")
    name = fixture.name("__vela_console_result")
    fixture.write(" =\n")
    expression_start = fixture.offset
    initializer = _natural(1)(fixture)
    fixture.write(";")
    fixture.declarations.append(fixture.node("constant", start, name=name, type=annotation,
                                             value=initializer, modifiers=["public"]))
    fixture.write(" ")
    start = fixture.offset
    fixture.write("public const ")
    annotation = _type("Nat")(fixture)
    fixture.write(" ")
    name = fixture.name("Injected")
    fixture.write(" = ")
    initializer = _natural(2)(fixture)
    expression = fixture.text.encode()[expression_start:].decode()
    fixture.write("\n;")
    fixture.declarations.append(fixture.node("constant", start, name=name, type=annotation,
                                             value=initializer, modifiers=["public"]))
    probe, syntax = fixture.response()
    # Both declarations are valid and source-bound; the console alone must reject this input.
    language.elaborate(probe, syntax)
    error = _refuses(lambda: language.evaluate(*_module().response(), expression, "Nat",
                                              parse=lambda _: syntax), "syntax")
    ensure("exactly one" in error.message, "injected declaration failed for an unrelated reason")


def _limits() -> None:
    fixture = _module()

    def unavailable(_source: bytes) -> object:
        raise AssertionError("invalid request reached native parser")

    _refuses(lambda: language.evaluate(*fixture.response(), "0" * 4097, "Nat", parse=unavailable), "limit")
    _refuses(lambda: language.evaluate(*fixture.response(), "\u00e9" * 2049, "Nat", parse=unavailable), "limit")
    _refuses(lambda: language.evaluate(*fixture.response(), "\ud800", "Nat", parse=unavailable), "encoding")
    invalid_request: dict[str, object] = {"valueType": "Unit"}
    _refuses(lambda: language.evaluate(*fixture.response(), "1", cast("ValueType", invalid_request["valueType"]),
                                       parse=unavailable), "type")
    for owner in ("MAX_WORK", "MAX_REDUCTIONS", "MAX_OUTPUT_BYTES"):
        with patch.object(language, owner, 0):
            _refuses(lambda: _evaluate(fixture, _natural(1)), "limit", expression=False)
    enormous = _binary("*", _natural(10 ** 200), _natural(10 ** 200))
    _refuses(lambda: _evaluate(fixture, enormous), "limit")

    def boundary(example: _Fixture) -> Node:
        example.write(" " * 4095)
        return _natural(1)(example)

    ensure(_evaluate(fixture, boundary) == StaticEvaluation("Nat", 1),
           "exact 4096-byte expression boundary was refused")


def _native_adapter() -> None:
    fixture = _module()
    source, syntax = fixture.response()
    expression, probe, probe_syntax = _probe(_call("At", _call("Samples"),
                                                _call("FZero", generics=(_natural(1),))))
    with tempfile.TemporaryDirectory(prefix="vela-mathematical-") as temporary:
        parser = Path(temporary) / "vela-parser"
        parser.write_bytes(b"independent fake parser bytes")
        inputs: list[bytes] = []

        def run(arguments: list[str], **keywords: object) -> subprocess.CompletedProcess[bytes]:
            ensure(arguments == [str(parser), "--surface"], "adapter bypassed native surface entry")
            raw = cast("bytes", keywords["input"])
            inputs.append(raw)
            answer = syntax if raw == source else probe_syntax
            ensure(raw in {source, probe}, "adapter changed source or expression bytes")
            response = json.dumps({"schema": 2, "ast": answer["ast"]}).encode()
            return subprocess.CompletedProcess(arguments, 0, stdout=response, stderr=b"")

        with patch.object(adapter.vela_parser.subprocess, "run", side_effect=run):
            compiled = adapter.compile_source(source, parser)
            ensure("vela_d1_Samples" in compiled.gallina, "adapter omitted dependent compilation")
            ensure(adapter.evaluate_source(source, expression, "Nat", parser) == StaticEvaluation("Nat", 7),
                   "native adapter changed mathematical observation")
        ensure(inputs == [source, source, probe], "adapter skipped original or single-probe parsing")
        receipt = adapter._build(parser)
        ensure(receipt.receipt == {"generated_sha256": {
            "vela-parser": hashlib.sha256(parser.read_bytes()).hexdigest()}},
            "adapter did not bind native executable bytes")


def cases() -> list[Case]:
    return [Case("dependent-vector-generic-and-boolean-values", _dependent_values),
            Case("higher-order-and-hygienic-static-reduction", _higher_order_and_static),
            Case("unequal-indices-types-and-invalid-original-proofs", _semantic_refusals),
            Case("single-initializer-source-binding-and-expression-coordinates", _injection_and_coordinates),
            Case("successfully-parsed-declaration-injection-is-refused", _parsed_declaration_injection),
            Case("mathematical-console-resource-and-unicode-bounds", _limits),
            Case("native-schema-two-compilation-and-evaluation-adapter", _native_adapter)]
