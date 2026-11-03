# SPDX-License-Identifier: Apache-2.0
"""Independent mathematical syntax fixtures and semantic/protocol neighbors.

The fixture writer spells each selected syntax role explicitly. It invokes
neither parser nor production decoder to obtain the expected located tree.
"""

import copy
import hashlib
from collections.abc import Callable
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela_elaborate as language
from vos.vela_ast import VelaError
from vos.vela_elaborate import elaborate

type Node = dict[str, object]
type Form = Callable[[_Fixture], Node]
type Parameter = tuple[str, Form]
type Generic = tuple[str, str, Form | None]


class _Fixture:
    def __init__(self, module: str = "Independent") -> None:
        self.text = "// caf\u00e9: original UTF-8 bytes remain the provenance.\n"
        self.start = self.offset
        self.write("module ")
        self.module = self.name(module)
        self.write(";")
        self.declarations: list[Node] = []

    @property
    def offset(self) -> int:
        return len(self.text.encode("utf-8"))

    def write(self, text: str) -> None:
        self.text += text

    def name(self, text: str) -> Node:
        start = self.offset
        self.write(text)
        return {"text": text, "span": [start, self.offset]}

    def node(self, kind: str, start: int, **fields: object) -> Node:
        return {"kind": kind, "span": [start, self.offset], **fields}

    def forms(self, forms: tuple[Form, ...]) -> list[Node]:
        nodes: list[Node] = []
        for index, form in enumerate(forms):
            if index:
                self.write(", ")
            nodes.append(form(self))
        return nodes

    def parameters(self, parameters: tuple[Parameter, ...], *, kind: str = "parameter") -> list[Node]:
        nodes: list[Node] = []
        self.write("(")
        for index, (name, value_type) in enumerate(parameters):
            if index:
                self.write(", ")
            start = self.offset
            annotation = value_type(self)
            self.write(" ")
            binding = self.name(name)
            nodes.append(self.node(kind, start, name=binding, type=annotation, grade=None))
        self.write(")")
        return nodes

    def generics(self, generics: tuple[Generic, ...]) -> list[Node]:
        nodes: list[Node] = []
        if not generics:
            return nodes
        self.write("<")
        for index, (mode, spelling, value_type) in enumerate(generics):
            if index:
                self.write(", ")
            start = self.offset
            if mode == "ghost":
                ensure(value_type is not None, "ghost fixture needs its type")
                self.write("ghost ")
                annotation = cast("Form", value_type)(self)
                self.write(" ")
                name = self.name(spelling)
            else:
                name = self.name(spelling)
                annotation = None
                if value_type is not None:
                    self.write(" : ")
                    annotation = value_type(self)
            nodes.append(self.node("generic_parameter", start, mode=mode, name=name, type=annotation))
        self.write(">")
        return nodes

    def definition(self, name: str, result: Form, parameters: tuple[Parameter, ...], value: Form,
                   generics: tuple[Generic, ...] = (), contracts: tuple[Form, ...] = ()) -> None:
        self.write("\n")
        start = self.offset
        self.write("public definition ")
        annotation = result(self)
        self.write(" ")
        binding = self.name(name)
        generic_nodes = self.generics(generics)
        parameter_nodes = self.parameters(parameters)
        obligations: list[Node] = []
        for contract in contracts:
            self.write(" ")
            obligations.append(contract(self))
        self.write(" = ")
        body = value(self)
        self.write(";")
        self.declarations.append(self.node("definition", start, name=binding, result=annotation,
                                           generics=generic_nodes, parameters=parameter_nodes,
                                           contracts=obligations, value=body, modifiers=["public"]))

    def theorem(self, name: str, parameters: tuple[Parameter, ...], proposition: Form,
                proof: Form | None, generics: tuple[Generic, ...] = ()) -> None:
        self.write("\n")
        start = self.offset
        self.write("public lemma ")
        binding = self.name(name)
        generic_nodes = self.generics(generics)
        parameter_nodes = self.parameters(parameters)
        self.write(": ")
        goal = proposition(self)
        body = None
        if proof is None:
            self.write(";")
        else:
            self.write(" proof ")
            block_start = self.offset
            self.write("{ ")
            return_start = self.offset
            self.write("return ")
            value = proof(self)
            self.write(";")
            terminal = self.node("return", return_start, value=value)
            self.write(" }")
            body = self.node("block", block_start, statements=[terminal])
        self.declarations.append(self.node("lemma", start, name=binding, generics=generic_nodes,
                                           parameters=parameter_nodes, proposition=goal, body=body,
                                           modifiers=["public"]))

    def function(self, name: str, result: Form, parameters: tuple[Parameter, ...], value: Form,
                 *, arrow: bool = True) -> None:
        self.write("\n")
        start = self.offset
        self.write("public ")
        annotation = result(self)
        self.write(" ")
        binding = self.name(name)
        parameter_nodes = self.parameters(parameters)
        self.write(" ")
        body_start = self.offset
        if arrow:
            self.write("=> ")
            returned = value(self)
            self.write(";")
            body = self.node("expression_body", body_start, value=returned)
        else:
            self.write("{ ")
            terminal_start = self.offset
            self.write("return ")
            returned = value(self)
            self.write(";")
            terminal = self.node("return", terminal_start, value=returned)
            self.write(" }")
            body = self.node("block", body_start, statements=[terminal])
        self.declarations.append(self.node("function", start, name=binding, result=annotation,
                                           generics=[], parameters=parameter_nodes, contracts=[],
                                           body=body, cancel=None, modifiers=["public"]))

    def alias(self, name: str, value_type: Form, generics: tuple[Generic, ...] = ()) -> None:
        self.write("\n")
        start = self.offset
        self.write("public alias ")
        binding = self.name(name)
        generic_nodes = self.generics(generics)
        self.write(" = ")
        annotation = value_type(self)
        self.write(";")
        self.declarations.append(self.node("alias", start, name=binding, generics=generic_nodes,
                                           contracts=[], type=annotation, modifiers=["public"]))

    def response(self) -> tuple[bytes, Node]:
        source = self.text.encode("utf-8")
        return source, {"schema": 2, "source_sha256": hashlib.sha256(source).hexdigest(),
                        "ast": self.node("surface_file", self.start, name=self.module,
                                         declarations=self.declarations)}


def _type(name: str, *arguments: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        binding = fixture.name(name)
        args: list[Node] = []
        if arguments:
            fixture.write("<")
            args = fixture.forms(arguments)
            fixture.write(">")
        return fixture.node("type", start, name=binding, arguments=args)
    return form


def _variable(name: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        return fixture.node("name", start, name=fixture.name(name))
    return form


def _natural(value: int) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(str(value))
        return fixture.node("nat", start, value=str(value), suffix="")
    return form


def _boolean(value: bool) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("true" if value else "false")
        return fixture.node("bool", start, value=value)
    return form


def _group(value: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("(")
        node = value(fixture)
        fixture.write(")")
        return fixture.node("group", start, value=node)
    return form


def _call(name: str | Form, *arguments: Form, generics: tuple[Form, ...] = ()) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        callee = (_variable(name) if isinstance(name, str) else name)(fixture)
        if generics:
            fixture.write("::<")
            generic_nodes = fixture.forms(generics)
            fixture.write(">")
            callee = fixture.node("generic_application", start, value=callee, arguments=generic_nodes)
        fixture.write("(")
        args = fixture.forms(arguments)
        fixture.write(")")
        return fixture.node("call", start, callee=callee, arguments=args)
    return form


def _binary(operator: str, left: Form, right: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        first = left(fixture)
        fixture.write(" ")
        symbol = fixture.name(operator)
        fixture.write(" ")
        second = right(fixture)
        return fixture.node("binary", start, operator=symbol, left=first, right=second)
    return form


def _function_type(parameters: tuple[Parameter, ...], result: Form,
                   effects: tuple[Form, ...] = ()) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("Fn")
        params = fixture.parameters(parameters)
        fixture.write(" -> ")
        output = result(fixture)
        effect_nodes: list[Node] = []
        if effects:
            fixture.write(" effects(")
            effect_nodes = fixture.forms(effects)
            fixture.write(")")
        return fixture.node("function_type", start, mode="Fn", generics=[], parameters=params,
                            result=output, captures=None, effects=effect_nodes, contracts=[])
    return form


def _lambda(parameters: tuple[Parameter, ...], body: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        params = fixture.parameters(parameters, kind="lambda_parameter")
        fixture.write(" => ")
        value = body(fixture)
        return fixture.node("lambda", start, parameters=params, body=value)
    return form


def _inferred_lambda(names: tuple[str, ...], body: Form, *, bare: bool = False,
                     trivia: bool = False) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        if not bare:
            fixture.write("(")
        if trivia:
            fixture.write("/* before /* nested */ binder */ ")
        params: list[Node] = []
        for index, spelling in enumerate(names):
            if index:
                fixture.write(", ")
            parameter_start = fixture.offset
            binding = fixture.name(spelling)
            params.append(fixture.node("lambda_parameter", parameter_start,
                                      name=binding, type=None, grade=None))
            if trivia:
                fixture.write(" /* after binder */ ")
        if not bare:
            fixture.write(")")
        fixture.write(" => ")
        if trivia:
            fixture.write("// before body\r\n ")
        value = body(fixture)
        return fixture.node("lambda", start, parameters=params, body=value)
    return form


def _let(name: str, value: Form, body: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("let ")
        binding = fixture.name(name)
        fixture.write(" = ")
        initial = value(fixture)
        local = fixture.node("let", start, name=binding, type=None, grade=None, value=initial)
        fixture.write(" in ")
        output = body(fixture)
        return fixture.node("let_expression", start, binding=local, body=output)
    return form


def _type_value(value_type: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("type ")
        value = value_type(fixture)
        return fixture.node("type_expression", start, type=value)
    return form


def _computed(value: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("type[")
        expression = value(fixture)
        fixture.write("]")
        return fixture.node("computed_type", start, value=expression)
    return form


def _tuple(*values: Form, types: bool = False) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("(")
        nodes = fixture.forms(values)
        fixture.write(")")
        return fixture.node("tuple_type" if types else "tuple", start,
                            **{"types" if types else "values": nodes})
    return form


def _hole(name: str = "?unfinished") -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        binding = fixture.name(name)
        return fixture.node("hole", start, name=binding)
    return form


def _contract(role: str, value: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(role + " ")
        proposition = value(fixture)
        return fixture.node("contract", start, role=role, value=proposition)
    return form


def _modified(modifier: str, value_type: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(modifier + " ")
        annotation = value_type(fixture)
        return fixture.node("modified_type", start, modifier=modifier, lifetime=None, type=annotation)
    return form


_NAT = _type("Nat")
_BOOL = _type("bool")
_T = _type("T")
_POLY: tuple[Generic, ...] = (("type", "T", None),)


def _identity(fixture: _Fixture) -> None:
    fixture.definition("Identity", _T, (("value", _T),), _variable("value"), _POLY)


def _refuses(fixture: _Fixture, kind: str, fragment: str = "") -> VelaError:
    source, response = fixture.response()
    try:
        elaborate(source, response)
    except VelaError as error:
        ensure(error.kind == kind, f"expected {kind}, got {error.kind}: {error.message}")
        ensure(fragment in error.message, f"expected {fragment!r} in {error.message!r}")
        ensure(error.line > 0 and error.column > 0, "semantic refusal lost its source position")
        return error
    raise AssertionError(f"accepted intended {kind} neighbor: {source!r}")


def _polymorphism_and_higher_order() -> None:
    fixture = _Fixture()
    _identity(fixture)
    fixture.definition("Apply", _type("U"),
                       (("f", _function_type((("x", _T),), _type("U"))), ("x", _T)),
                       _call("f", _variable("x")), (*_POLY, ("type", "U", None)))
    fixture.definition("Mixed", _tuple(_NAT, _BOOL, types=True), (),
                       _tuple(_call("Identity", _natural(7)),
                              _call("Identity", _boolean(True), generics=(_BOOL,))))
    fixture.definition("Higher", _NAT, (),
                       _call("Apply", _lambda((("x", _type("_")),),
                                             _binary("+", _variable("x"), _natural(1))), _natural(4)))
    fixture.definition("Placeholder", _BOOL, (),
                       _call("Identity", _boolean(True), generics=(_type("_"),)))
    fixture.definition("FirstClass", _NAT, (), _call("Apply", _variable("Identity"), _natural(8)))
    source, response = fixture.response()
    result = elaborate(source, response)
    ensure(result.module == "Independent", "elaboration lost its source module")
    ensure(result == elaborate(source, response), "identical input is nondeterministic")
    ensure(hashlib.sha256(source).hexdigest() in result.gallina, "emission omitted exact source identity")
    ensure("Corelib.Init.Nat.add" in result.gallina, "higher-order body omitted its addition")
    ensure("vela_d0_Identity" in result.gallina and "vela_d3_Higher" in result.gallina,
           "definitions lost their independent hygienic names")
    ensure("Axiom " not in result.gallina and "Admitted" not in result.gallina,
           "generic inference emitted an unchecked assumption")


def _concise_lambdas_and_expression_bodies() -> None:
    def candidate(concise: bool, bare: bool = False) -> _Fixture:
        fixture = _Fixture()
        fixture.definition("Apply", _type("U"),
                           (("f", _function_type((("x", _T),), _type("U"))), ("x", _T)),
                           _call("f", _variable("x")), (*_POLY, ("type", "U", None)))
        addition = _binary("+", _variable("x"), _natural(1))
        callback = (_inferred_lambda(("x",), addition, bare=bare) if concise
                    else _lambda((("x", _NAT),), addition))
        fixture.function("Increment", _NAT, (("value", _NAT),),
                         _call("Apply", callback, _variable("value")), arrow=concise)
        signature = _function_type((("left", _NAT), ("right", _NAT)), _NAT)
        addition = _binary("+", _variable("left"), _variable("right"))
        callback = (_inferred_lambda(("left", "right"), addition) if concise
                    else _lambda((("left", _NAT), ("right", _NAT)), addition))
        fixture.definition("Addition", signature, (), callback)
        vector = _type("Vec", _NAT, _type("n"))
        signature = _function_type((("n", _NAT), ("values", vector)), vector)
        callback = (_inferred_lambda(("n", "values"), _variable("values")) if concise
                    else _lambda((("n", _NAT), ("values", vector)), _variable("values")))
        fixture.definition("Preserve", signature, (), callback)
        return fixture

    expanded = elaborate(*candidate(False).response()).gallina.split("\n", 2)[2]
    for bare in (False, True):
        fixture = candidate(True, bare)
        source, response = fixture.response()
        emitted = elaborate(source, response).gallina
        ensure(emitted.split("\n", 2)[2] == expanded,
               "concise lambda/return body changed the existing checked terms")
        ensure(hashlib.sha256(source).hexdigest() in emitted, "concise syntax lost source provenance")

    unresolved = _Fixture()
    unresolved.definition("Unknown", _NAT, (),
                          _let("identity", _inferred_lambda(("value",), _variable("value")), _natural(0)))
    _refuses(unresolved, "inference")
    wrong = _Fixture()
    wrong.function("Wrong", _NAT, (), _boolean(True))
    _refuses(wrong, "type")
    annotated = _Fixture()
    annotated.definition("Identity", _function_type((("value", _NAT),), _NAT), (),
                         _lambda((("value", _NAT),), _variable("value")))
    source, response = annotated.response()
    root = cast("Node", response["ast"])
    declaration = cast("list[Node]", root["declarations"])[0]
    parameter = cast("list[Node]", cast("Node", declaration["value"])["parameters"])[0]
    parameter["type"] = None
    try:
        elaborate(source, response)
    except VelaError as error:
        ensure(error.kind == "protocol", "omitted annotation forgery reached type inference")
    else:
        raise AssertionError("typed source accepted as an annotation-free lambda parameter")

    for label in ("arrow", "terminator", "value"):
        fixture = _Fixture()
        fixture.function("Constant", _NAT, (), _natural(1))
        source, response = fixture.response()
        root = cast("Node", response["ast"])
        declaration = cast("list[Node]", root["declarations"])[0]
        body = cast("Node", declaration["body"])
        start, end = cast("list[int]", body["span"])
        if label == "arrow":
            body["span"] = [start + 1, end]
        elif label == "terminator":
            body["span"] = [start, end - 1]
        else:
            cast("Node", body["value"])["span"] = [start, start + 1]
        try:
            elaborate(source, response)
        except VelaError as error:
            ensure(error.kind == "protocol", f"body {label} forgery reached semantic checking")
        else:
            raise AssertionError(f"accepted expression-body {label} corruption")


def _ergonomic_source_token_coverage() -> None:
    def surrounding(value: Form, before: str, after: str) -> Form:
        def form(fixture: _Fixture) -> Node:
            fixture.write(before)
            node = value(fixture)
            fixture.write(after)
            return node
        return form

    for before, after, value in (("", " + 1", 0), ("0 + ", "", 1),
                                 ("/* ", " */ 1", 0), ("// ", "\n 1", 0),
                                 ("\v", "", 1)):
        fixture = _Fixture()
        fixture.function("Forged", _NAT, (), surrounding(_natural(value), before, after))
        _refuses(fixture, "protocol")

    fixture = _Fixture()
    grouped = _group(_binary("+", _natural(0), _natural(1)))
    fixture.function("Grouped", _NAT, (),
                     surrounding(grouped, "/* before /* nested */ value */ ", " // after\r\n "))
    signature = _function_type((("left", _NAT), ("right", _NAT)), _NAT)
    fixture.definition("WithTrivia", signature, (),
                       _inferred_lambda(("left", "right"),
                                        _group(_binary("+", _variable("left"), _variable("right"))),
                                        trivia=True))
    emitted = elaborate(*fixture.response()).gallina
    ensure("Corelib.Init.Nat.add" in emitted, "valid grouped/trivia syntax was refused or changed")

    for typed_parameter in (0, 1):
        fixture = _Fixture()
        signature = (_function_type((("value", _NAT),), _NAT) if typed_parameter == 0
                     else _function_type((("first", _NAT), ("value", _NAT)), _NAT))
        parameters = ((("value", _BOOL),) if typed_parameter == 0
                      else (("first", _NAT), ("value", _BOOL)))
        fixture.definition("Annotation", signature, (), _lambda(parameters, _variable("value")))
        source, response = fixture.response()
        root = cast("Node", response["ast"])
        declaration = cast("list[Node]", root["declarations"])[0]
        parameter = cast("list[Node]", cast("Node", declaration["value"])["parameters"])[typed_parameter]
        parameter["type"] = None
        parameter["span"] = cast("Node", parameter["name"])["span"]
        try:
            elaborate(source, response)
        except VelaError as error:
            ensure(error.kind == "protocol", "shrunk parameter span erased an authored annotation")
        else:
            raise AssertionError("inferred lambda accepted an omitted annotation with a shrunk parameter span")


def _dependent_vectors_and_indices() -> None:
    fixture = _Fixture("Dependent")
    vector = _type("Vec", _T, _type("n"))
    fixture.alias("Words", vector, (*_POLY, ("ghost", "n", _NAT)))
    fixture.definition("Copy", vector, (("items", vector),), _variable("items"),
                       (*_POLY, ("ghost", "n", _NAT)))
    fixture.definition("First", _NAT, (("items", _type("Vec", _NAT, _natural(1))),),
                       _call("At", _call("Copy", _variable("items")),
                             _call("FZero", generics=(_natural(0),))))
    fixture.definition("One", _type("Vec", _NAT, _natural(1)), (),
                       _call("VCons", _natural(9), _call("VNil", generics=(_NAT,))))
    fixture.definition("Aliased", _type("Words", _NAT, _natural(1)), (),
                       _call("One"))
    fixture.definition("DependentFunction",
                       _function_type((("n", _NAT), ("xs", _type("Vec", _NAT, _type("n")))),
                                      _type("Vec", _NAT, _type("n"))), (),
                       _lambda((("n", _NAT), ("xs", _type("Vec", _NAT, _type("n")))),
                               _variable("xs")))
    source, response = fixture.response()
    result = elaborate(source, response)
    ensure("Dependent" in result.gallina, "dependent module omitted")
    wrong = _Fixture()
    wrong.definition("Wrong", _type("Vec", _NAT, _natural(2)), (),
                     _call("VCons", _natural(9), _call("VNil", generics=(_NAT,))))
    _refuses(wrong, "type")
    wrong = _Fixture()
    wrong.definition("OutOfBounds", _NAT, (),
                     _call("At", _call("VNil", generics=(_NAT,)),
                           _call("FZero", generics=(_natural(0),))))
    _refuses(wrong, "type")


def _proof_values_and_false_neighbors() -> None:
    fixture = _Fixture("Proofs")
    x = _variable("x")
    fixture.theorem("Reflexive", (("x", _T),), _binary("==", x, x), _call("Refl", x), _POLY)
    fixture.theorem("Composed", (("x", _NAT),), _binary("==", x, x),
                    _call("Trans", _call("Refl", x), _call("Symm", _call("Refl", x))))
    fixture.theorem("Congruent", (("x", _NAT),),
                    _binary("==", _binary("+", x, _natural(1)), _binary("+", x, _natural(1))),
                    _call("Congr", _lambda((("n", _NAT),),
                                            _binary("+", _variable("n"), _natural(1))),
                          _call("Refl", x)))
    fixture.definition("ProofParameter", _computed(_call("Eq", x, x, generics=(_NAT,))),
                       (("x", _NAT), ("evidence", _computed(_call("Eq", x, x, generics=(_NAT,))))),
                       _variable("evidence"))
    proposition_generic: tuple[Generic, ...] = (("type", "P", _type("Prop")),)
    fixture.definition("KeepProof", _type("P"), (("evidence", _type("P")),),
                       _variable("evidence"), proposition_generic)
    fixture.theorem("ForwardProof", (("evidence", _type("P")),), _variable("P"),
                    _call("KeepProof", _variable("evidence")), proposition_generic)
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Corelib.Init.Logic.eq" in emitted, "proof goal omitted propositional equality")
    for name, goal, proof, kind in (
            ("False", _binary("==", _natural(0), _natural(1)), _call("Refl", _natural(0)), "type"),
            ("NoProof", _binary("==", _natural(0), _natural(0)), None, "unsupported"),
            ("NotAProposition", _natural(0), _natural(0), "type")):
        wrong = _Fixture()
        wrong.theorem(name, (), goal, proof)
        _refuses(wrong, kind)


def _universes_and_scope() -> None:
    fixture = _Fixture("Universes")
    fixture.definition("Universe", _type("Type", _natural(1)), (), _type_value(_type("Type")))
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Type" in emitted, "type-valued definition lost its universe")
    wrong = _Fixture()
    wrong.definition("SelfTyped", _type("Type"), (), _type_value(_type("Type")))
    _refuses(wrong, "type")
    wrong = _Fixture()
    wrong.definition("Specialized", _T, (("value", _T),), _natural(1), _POLY)
    _refuses(wrong, "type")
    wrong = _Fixture()
    wrong.definition("UnboundIndex", _type("Vec", _NAT, _type("absent")), (),
                     _call("VNil", generics=(_NAT,)))
    _refuses(wrong, "name")


def _occurs_and_unresolved_inference() -> None:
    wrong = _Fixture()
    wrong.definition("SelfApplication", _NAT, (),
                     _let("unused", _lambda((("f", _type("_")),),
                                             _call("f", _variable("f"))), _natural(0)))
    _refuses(wrong, "type")
    wrong = _Fixture()
    wrong.definition("Ambiguous", _NAT, (),
                     _let("identity", _lambda((("x", _type("_")),), _variable("x")), _natural(0)))
    _refuses(wrong, "inference")
    wrong = _Fixture()
    _identity(wrong)
    wrong.definition("WrongDomain", _NAT, (),
                     _call("Identity", _boolean(True), generics=(_NAT,)))
    _refuses(wrong, "type")


def _definitional_conversion() -> None:
    fixture = _Fixture("Conversion")
    n = _variable("n")
    fixture.theorem("ZeroOnLeft", (("n", _NAT),),
                    _binary("==", _binary("+", _natural(0), n), n), _call("Refl", n))
    identity = _group(_lambda((("value", _NAT),), _variable("value")))
    fixture.theorem("Beta", (("n", _NAT),), _binary("==", _call(identity, n), n), _call("Refl", n))
    fixture.definition("ComputedLength", _type("Vec", _NAT,
                                               _group(_binary("+", _natural(0), _natural(1)))), (),
                       _call("VCons", _natural(4), _call("VNil", generics=(_NAT,))))
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Corelib.Init.Logic.eq_refl" in emitted, "definitional equality lost its proof constructor")
    # Nat.add recurses on its first operand: n + 0 is stuck for arbitrary n.
    # Accepting this neighbor with Refl would invent an arithmetic theorem.
    wrong = _Fixture()
    wrong.theorem("ZeroOnRight", (("n", _NAT),),
                  _binary("==", _binary("+", n, _natural(0)), n), _call("Refl", n))
    _refuses(wrong, "type")


def _products_and_lookup_computation() -> None:
    fixture = _Fixture("Elimination")
    fixture.definition("First", _NAT, (),
                       _call("Fst", _tuple(_natural(7), _boolean(True))))
    fixture.definition("Second", _BOOL, (),
                       _call("Snd", _tuple(_natural(7), _boolean(True)), generics=(_NAT, _BOOL)))
    fixture.theorem("Projection", (),
                    _binary("==", _call("Fst", _tuple(_natural(7), _boolean(False))), _natural(7)),
                    _call("Refl", _natural(7)))
    values = _call("VCons", _natural(7),
                   _call("VCons", _natural(9), _call("VNil", generics=(_NAT,))))
    fixture.theorem("LookupFirst", (),
                    _binary("==", _call("At", values, _call("FZero", generics=(_natural(1),))),
                            _natural(7)), _call("Refl", _natural(7)))
    fixture.theorem("LookupSecond", (),
                    _binary("==", _call("At", values,
                                        _call("FSucc", _call("FZero", generics=(_natural(0),)))),
                            _natural(9)), _call("Refl", _natural(9)))
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Corelib.Init.Datatypes.fst" in emitted and "Corelib.Init.Datatypes.snd" in emitted,
           "product elimination omitted the selected ordinary projections")
    wrong = _Fixture()
    wrong.definition("NotAProduct", _NAT, (), _call("Fst", _natural(7)))
    _refuses(wrong, "type")
    wrong = _Fixture()
    wrong.theorem("WrongLookup", (),
                  _binary("==", _call("At", values, _call("FZero", generics=(_natural(1),))),
                          _natural(9)), _call("Refl", _natural(9)))
    _refuses(wrong, "type")


def _strict_protocol() -> None:
    fixture = _Fixture("Protocol")
    fixture.definition("Value", _NAT, (), _natural(1))
    source, response = fixture.response()
    for label, mutate in (
            ("unexpected response field", lambda raw: raw.update(extra=True)),
            ("Boolean schema", lambda raw: raw.update(schema=True)),
            ("stale source digest", lambda raw: raw.update(source_sha256="0" * 64)),
            ("schema one", lambda raw: raw.update(schema=1))):
        changed = copy.deepcopy(response)
        mutate(changed)
        try:
            elaborate(source, changed)
        except (TypeError, ValueError):
            pass
        except VelaError as error:
            ensure(error.kind == "protocol", f"{label} reached semantic checking")
        else:
            raise AssertionError(f"accepted {label}")
    for label in ("field", "literal", "Boolean span", "escaping span", "name"):
        changed = copy.deepcopy(response)
        root = cast("Node", changed["ast"])
        declaration = cast("list[Node]", root["declarations"])[0]
        value = cast("Node", declaration["value"])
        if label == "field":
            value["escape"] = "Axiom evil : False."
        elif label == "literal":
            value["value"] = "2"
        elif label == "Boolean span":
            value["span"] = [True, len(source)]
        elif label == "escaping span":
            value["span"] = [0, len(source)]
        else:
            cast("Node", declaration["name"])["text"] = "Injected."
        try:
            elaborate(source, changed)
        except (TypeError, ValueError):
            pass
        except VelaError as error:
            ensure(error.kind == "protocol", f"native {label} corruption reached semantics")
        else:
            raise AssertionError(f"accepted native {label} mutation")


def _malformed_role_containers() -> None:
    fixture = _Fixture("Roles")
    fixture.definition("Lambda", _function_type((("x", _NAT),), _NAT), (),
                       _lambda((("x", _NAT),), _variable("x")))
    source, response = fixture.response()
    mutations: list[tuple[str, Node]] = []
    for malformed in (None, {}, True, "declarations", [None]):
        changed = copy.deepcopy(response)
        cast("Node", changed["ast"])["declarations"] = malformed
        mutations.append(("declaration container", changed))
    for field in ("generics", "parameters", "result"):
        changed = copy.deepcopy(response)
        root = cast("Node", changed["ast"])
        declaration = cast("list[Node]", root["declarations"])[0]
        declaration[field] = None
        mutations.append((field, changed))
    changed = copy.deepcopy(response)
    root = cast("Node", changed["ast"])
    declaration = cast("list[Node]", root["declarations"])[0]
    value = cast("Node", declaration["value"])
    parameter = cast("list[Node]", value["parameters"])[0]
    parameter["kind"] = "generic_parameter"
    del parameter["grade"]
    parameter["mode"] = "ghost"
    mutations.append(("generic binder inside lambda parameters", changed))
    for label, changed in mutations:
        try:
            elaborate(source, changed)
        except (TypeError, ValueError):
            pass
        except VelaError as error:
            ensure(error.kind == "protocol", f"malformed {label} reached semantic checking")
        else:
            raise AssertionError(f"accepted malformed {label}")


def _holes_unsupported_and_hygiene() -> None:
    wrong = _Fixture()
    wrong.definition("Unfinished", _NAT, (), _hole())
    _refuses(wrong, "inference")
    for role in ("requires", "ensures", "restores"):
        wrong = _Fixture()
        wrong.definition("Contract", _NAT, (), _natural(0),
                         contracts=(_contract(role, _boolean(True)),))
        _refuses(wrong, "unsupported")
    wrong = _Fixture()
    wrong.definition("Resource", _NAT, (("value", _modified("owned", _NAT)),), _variable("value"))
    _refuses(wrong, "unsupported")
    wrong = _Fixture()
    effectful = _function_type((("value", _NAT),), _NAT, effects=(_type("Read"),))
    wrong.definition("Effects", _NAT, (("f", effectful),), _call("f", _natural(0)))
    _refuses(wrong, "unsupported")
    fixture = _Fixture("Gallina.Module")
    fixture.definition("Definition", _NAT, (("Check", _NAT),), _variable("Check"))
    source, response = fixture.response()
    result = elaborate(source, response)
    ensure("Module Vela_Gallina_Module." in result.gallina, "qualified module escaped hygiene")
    ensure("vela_d0_Definition" in result.gallina and "(Check :" not in result.gallina,
           "source names captured Gallina syntax")
    fixture = _Fixture("InternalNames")
    fixture.definition("vela_d1_Later", _NAT, (), _natural(1))
    fixture.definition("Later", _BOOL, (), _boolean(True))
    fixture.definition("Use", _NAT, (), _call("vela_d1_Later"))
    source, response = fixture.response()
    elaborate(source, response)
    wrong = _Fixture()
    wrong.definition("Value", _NAT, (), _natural(1))
    wrong.definition("Hidden", _NAT, (), _call("vela_d0_Value"))
    _refuses(wrong, "name")


def _source_limits() -> None:
    # The source-size guard must run before descending even a missing AST.
    try:
        elaborate(b" " * 65_537, {})
    except VelaError as error:
        ensure(error.kind == "limit", "oversized source reached protocol decoding")
    else:
        raise AssertionError("oversized source accepted")
    wrong = _Fixture()
    nested: Form = _natural(0)
    for _ in range(300):
        nested = _group(nested)
    wrong.definition("Deep", _NAT, (), nested)
    _refuses(wrong, "limit")


def _elaboration_budgets() -> None:
    fixture = _Fixture()
    fixture.theorem("Computed", (), _binary("==", _binary("+", _natural(1), _natural(1)), _natural(2)),
                    _call("Refl", _natural(2)))
    source, response = fixture.response()
    elaborate(source, response)
    for owner in ("MAX_WORK", "MAX_REDUCTIONS", "MAX_OUTPUT_BYTES"):
        with patch.object(language, owner, 0):
            _refuses(fixture, "limit")


def cases() -> list[Case]:
    return [Case("fresh-polymorphism-and-higher-order-inference", _polymorphism_and_higher_order),
            Case("concise-lambdas-and-expression-body-terms", _concise_lambdas_and_expression_bodies),
            Case("ergonomic-source-token-coverage", _ergonomic_source_token_coverage),
            Case("dependent-vectors-and-finite-indices", _dependent_vectors_and_indices),
            Case("first-class-proofs-and-false-neighbors", _proof_values_and_false_neighbors),
            Case("predicative-universes-and-rigid-scope", _universes_and_scope),
            Case("occurs-and-unresolved-inference", _occurs_and_unresolved_inference),
            Case("definitional-reduction-without-arithmetic-assumptions", _definitional_conversion),
            Case("products-and-concrete-dependent-lookup", _products_and_lookup_computation),
            Case("strict-surface-schema-and-source-binding", _strict_protocol),
            Case("malformed-role-containers", _malformed_role_containers),
            Case("holes-unsupported-forms-and-hygiene", _holes_unsupported_and_hygiene),
            Case("bounded-source-and-syntax", _source_limits),
            Case("inference-reduction-and-output-budgets", _elaboration_budgets)]
