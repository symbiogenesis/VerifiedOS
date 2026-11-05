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
type Parameter = tuple[str | None, Form] | tuple[str | None, Form, bool]
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
        for index, parameter in enumerate(parameters):
            if len(parameter) == 3:
                name, value_type, static = parameter
            else:
                name, value_type = parameter
                static = False
            if index:
                self.write(", ")
            start = self.offset
            if static:
                self.write("const ")
            annotation = value_type(self)
            binding = None
            if name is not None:
                self.write(" ")
                binding = self.name(name)
            node = self.node(kind, start, name=binding, type=annotation, grade=None)
            if static:
                node["const"] = True
            nodes.append(node)
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
        self.write(" => ")
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
                 *, arrow: bool = True, block: bool = False, constant: bool = False) -> None:
        self.write("\n")
        start = self.offset
        self.write("public const " if constant else "public ")
        annotation = result(self)
        self.write(" ")
        binding = self.name(name)
        parameter_nodes = self.parameters(parameters)
        self.write(" ")
        body_start = self.offset
        if block:
            body = value(self)
        elif arrow:
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
                                           body=body, cancel=None, modifiers=["public", "const"] if constant else ["public"]))

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

    def constant(self, name: str, value_type: Form, value: Form) -> None:
        self.write("\n")
        start = self.offset
        self.write("public const ")
        annotation = value_type(self)
        self.write(" ")
        binding = self.name(name)
        self.write(" = ")
        initializer = value(self)
        self.write(";")
        self.declarations.append(self.node("constant", start, name=binding, type=annotation,
                                           value=initializer, modifiers=["public"]))

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


def _call(name: str | Form, *arguments: Form, generics: tuple[Form, ...] = (),
          labels: tuple[str | None, ...] | None = None, trailing: bool = False,
          explicit: bool = False) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        callee = (_variable(name) if isinstance(name, str) else name)(fixture)
        if generics:
            fixture.write("::<" if explicit else "<")
            generic_nodes = fixture.forms(generics)
            fixture.write(">")
            callee = fixture.node("generic_application", start, value=callee, arguments=generic_nodes)
        fixture.write("(")
        args: list[Node] = []
        if labels is not None:
            ensure(len(labels) == len(arguments), "each fixture argument needs a label role")
        for index, value in enumerate(arguments):
            if index:
                fixture.write(", ")
            argument_start = fixture.offset
            label = None if labels is None else labels[index]
            label_node = None
            if label is not None:
                label_node = fixture.name(label)
                fixture.write(": ")
            expression = value(fixture)
            args.append(fixture.node("argument", argument_start, label=label_node, value=expression))
        if arguments and trailing:
            fixture.write(",")
        fixture.write(")")
        return fixture.node("call", start, callee=callee, arguments=args)
    return form


def _unit() -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("()")
        return fixture.node("unit", start)
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


def _local_constant(name: str, value_type: Form, value: Form, body: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("{ ")
        constant_start = fixture.offset
        fixture.write("const ")
        annotation = value_type(fixture)
        fixture.write(" ")
        binding = fixture.name(name)
        fixture.write(" = ")
        initializer = value(fixture)
        fixture.write(";")
        constant = fixture.node("constant_local", constant_start, name=binding,
                                type=annotation, value=initializer)
        fixture.write(" return ")
        return_start = fixture.offset - len("return ")
        result = body(fixture)
        fixture.write(";")
        terminal = fixture.node("return", return_start, value=result)
        fixture.write(" }")
        return fixture.node("block", start, statements=[constant, terminal])
    return form


def _choice(condition: Form, yes: Form, no: Form) -> Form:
    def branch(fixture: _Fixture, value: Form) -> Node:
        start = fixture.offset
        fixture.write("{ return ")
        return_start = start + 2
        expression = value(fixture)
        fixture.write(";")
        terminal = fixture.node("return", return_start, value=expression)
        fixture.write(" }")
        return fixture.node("block", start, statements=[terminal])

    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("{ ")
        if_start = fixture.offset
        fixture.write("if (")
        selected = condition(fixture)
        fixture.write(") ")
        accepted = branch(fixture, yes)
        fixture.write(" else ")
        rejected = branch(fixture, no)
        conditional = fixture.node("if", if_start, condition=selected,
                                   **{"then": accepted, "else": rejected})
        fixture.write(" }")
        return fixture.node("block", start, statements=[conditional])
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


def _familiar_generic_spellings() -> None:
    def candidate(explicit: bool) -> _Fixture:
        fixture = _Fixture("GenericSpellings")
        _identity(fixture)
        fixture.definition("Value", _NAT, (),
                           _call("Identity", _natural(7), generics=(_NAT,), explicit=explicit))
        return fixture

    canonical_source, canonical_tree = candidate(False).response()
    explicit_source, explicit_tree = candidate(True).response()
    canonical = elaborate(canonical_source, canonical_tree).gallina
    explicit = elaborate(explicit_source, explicit_tree).gallina
    ensure(b"Identity<Nat>(7)" in canonical_source and b"Identity::<Nat>(7)" in explicit_source,
           "generic spelling controls do not independently select both markers")
    ensure(canonical.split("\n", 2)[2] == explicit.split("\n", 2)[2],
           "ordinary and explicit generic calls changed interpreted terms")

    for marker in (b"= ", b"==", b"->"):
        source = canonical_source.replace(b"=>", marker, 1)
        tree = copy.deepcopy(canonical_tree)
        tree["source_sha256"] = hashlib.sha256(source).hexdigest()
        try:
            elaborate(source, tree)
        except VelaError as error:
            ensure(error.kind == "protocol", "a forged mathematical body marker reached semantics")
        else:
            raise AssertionError("a mathematical definition accepted a legacy or invented body marker")

    def generic_value(explicit: bool) -> Form:
        def form(fixture: _Fixture) -> Node:
            start = fixture.offset
            value = _variable("Identity")(fixture)
            fixture.write("::<" if explicit else "<")
            argument = _NAT(fixture)
            fixture.write(">")
            return fixture.node("generic_application", start, value=value, arguments=[argument])
        return form

    for explicit in (False, True):
        fixture = _Fixture("GenericValues")
        _identity(fixture)
        fixture.definition("Value", _function_type((("value", _NAT),), _NAT), (),
                           generic_value(explicit))
        if explicit:
            ensure("vela_d0_Identity" in elaborate(*fixture.response()).gallina,
                   "explicit generic function values lost their interpretation")
        else:
            _refuses(fixture, "protocol", "followed by a call")


def _canonical_named_call_terms() -> None:
    def candidate(named: bool) -> _Fixture:
        fixture = _Fixture("NamedCalls")
        _identity(fixture)
        fixture.definition("Apply", _type("U"),
                           (("function", _function_type((("input", _T),), _type("U"))),
                            ("value", _T)),
                           _call("function", _variable("value"),
                                 labels=("input",) if named else None),
                           (*_POLY, ("type", "U", None)))
        fixture.definition("Use", _NAT, (),
                           _call("Apply", _inferred_lambda(("implementation",),
                                  _binary("+", _variable("implementation"), _natural(1)), bare=True),
                                 _call("Identity", _natural(41),
                                       labels=("value",) if named else None),
                                 labels=(None, "value") if named else None,
                                 generics=(_NAT, _NAT), trailing=True))
        fixture.definition("Empty", _type("Unit"), (),
                           _call("Identity", _unit(), generics=(_type("Unit"),),
                                 labels=("value",) if named else None))
        vector = _type("Vec", _NAT, _type("count"))
        signature = _function_type((("count", _NAT), ("values", vector)), vector)
        fixture.alias("Reader", signature)
        fixture.definition("Preserve", _type("Reader"), (),
                           _inferred_lambda(("length", "storage"), _variable("storage")))
        fixture.definition("Keep", vector, (("count", _NAT), ("values", vector)), _variable("values"))
        singleton = _call("VCons", _natural(7), _call("VNil", generics=(_NAT,)))
        fixture.definition("Preserved", _type("Vec", _NAT, _natural(1)), (),
                           _call(_call("Preserve"), _natural(1), singleton,
                                 labels=("count", "values") if named else None))
        partial = _call("Keep", _natural(1), labels=("count",) if named else None)
        fixture.definition("Partial", _type("Vec", _NAT, _natural(1)), (),
                           _call(partial, singleton, labels=("values",) if named else None))
        fixture.definition("WithUnit", _tuple(_type("Unit"), _NAT, types=True), (),
                           _tuple(_unit(), _natural(7)))
        return fixture

    positional = elaborate(*candidate(False).response()).gallina.split("\n", 2)[2]
    source, response = candidate(True).response()
    named = elaborate(source, response).gallina
    ensure(named.split("\n", 2)[2] == positional,
           "argument labels changed dependent, generic, aliased, partial or Unit CIC terms")
    ensure(hashlib.sha256(source).hexdigest() in named, "labeled calls lost exact source provenance")
    ensure("Corelib.Init.Datatypes.unit" in named and "Corelib.Init.Datatypes.tt" in named,
           "canonical Unit type and value lost their existing interpretation")


def _required_static_constants() -> None:
    fixture = _Fixture("Constants")
    fixture.constant("Base", _NAT, _natural(21))
    fixture.definition("Twice", _NAT, (("value", _NAT),),
                       _let("copy", _variable("value"), _binary("+", _variable("copy"), _variable("copy"))))
    fixture.constant("Answer", _NAT, _call("Twice", _variable("Base"), labels=("value",)))
    fixture.constant("Accepted", _BOOL, _binary("<=", _variable("Answer"), _natural(42)))
    fixture.constant("Nothing", _type("Unit"), _unit())
    fixture.function("Local", _NAT, (),
                     _local_constant("Next", _NAT, _binary("+", _variable("Answer"), _natural(1)),
                                     _variable("Next")), block=True)
    fixture.constant("Length", _NAT, _natural(1))
    fixture.definition("One", _type("Vec", _NAT, _type("Length")), (),
                       _call("VCons", _natural(7), _call("VNil", generics=(_NAT,))))
    fixture.theorem("Computed", (), _binary("==", _variable("Answer"), _natural(42)),
                    _call("Refl", _natural(42)))
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Definition vela_d2_Answer : Corelib.Init.Datatypes.nat :=\n  (42 :" in emitted,
           "module constant was not emitted as its evaluated scalar value")
    ensure("Definition vela_d3_Accepted : Corelib.Init.Datatypes.bool :=\n  Corelib.Init.Datatypes.true." in emitted,
           "comparison constant did not evaluate to its independently expected Boolean")
    local = emitted.split("Definition vela_d5_Local", 1)[1].split("Definition", 1)[0]
    ensure("(43 : Corelib.Init.Datatypes.nat)" in local and "Corelib.Init.Nat.add" not in local,
           "local constant retained runtime arithmetic instead of its evaluated value")
    ensure("Corelib.Init.Datatypes.tt" in emitted and hashlib.sha256(source).hexdigest() in emitted,
           "Unit constant or exact source provenance was lost")


def _static_dependency_refusals() -> None:
    for role in ("parameter", "ordinary-let", "ignored", "dead-branch", "ghost"):
        fixture = _Fixture()
        fixture.definition("Ignore", _NAT, (("unused", _NAT),), _natural(0))
        initial = _variable("runtime")
        if role == "ignored":
            initial = _call("Ignore", initial)
        elif role == "dead-branch":
            initial = _call(_group(_lambda((), _choice(_boolean(False), initial, _natural(0)))))
        body = _local_constant("Chosen", _NAT, initial, _variable("Chosen"))
        if role == "ordinary-let":
            fixture.definition("Wrong", _NAT, (),
                               _let("runtime", _natural(3), _call(_group(_lambda((), body)))))
        elif role == "ghost":
            fixture.definition("Wrong", _NAT, (), _call(_group(_lambda((), body))),
                               (("ghost", "runtime", _NAT),))
        else:
            fixture.function("Wrong", _NAT, (("runtime", _NAT),), body, block=True)
        _refuses(fixture, "type", "nonstatic binding 'runtime'")
    for name in ("Missing", "Self"):
        fixture = _Fixture()
        fixture.constant("Self", _NAT, _variable(name))
        _refuses(fixture, "name")
    fixture = _Fixture()
    fixture.constant("WrongType", _NAT, _boolean(True))
    _refuses(fixture, "type")
    fixture = _Fixture()
    fixture.constant("Value", _NAT, _natural(1))
    fixture.definition("Wrong", _NAT, (), _call("Value"))
    _refuses(fixture, "type")
    fixture = _Fixture()
    fixture.constant("Pair", _tuple(_NAT, _BOOL, types=True), _tuple(_natural(1), _boolean(True)))
    _refuses(fixture, "unsupported", "Nat, bool or Unit")
    fixture = _Fixture()
    fixture.constant("Overflow", _NAT, _binary("*", _natural(10 ** 200), _natural(10 ** 200)))
    _refuses(fixture, "limit", "representation bound")
    fixture = _Fixture()
    fixture.constant("Boundary", _NAT, _natural(10 ** 256 - 1))
    elaborate(*fixture.response())
    fixture.constant("Overflow", _NAT, _call("Succ", _variable("Boundary")))
    _refuses(fixture, "limit", "representation bound")
    fixture = _Fixture()
    fixture.definition("Work", _NAT, (("value", _NAT),), _binary("+", _variable("value"), _natural(1)))
    fixture.constant("Constant", _NAT, _call("Work", _natural(1)))
    with patch.object(language, "MAX_REDUCTIONS", 0):
        _refuses(fixture, "limit")


def _source_callable_arities() -> None:
    fixture = _Fixture()
    fixture.definition("Empty", _NAT, (), _natural(7))
    fixture.definition("Explicit", _NAT, (("token", _type("Unit")),), _natural(7))
    fixture.definition("UseEmpty", _NAT, (), _call("Empty"))
    fixture.definition("UseExplicit", _NAT, (), _call("Explicit", _unit(), labels=("token",)))
    fixture.definition("UseLambda", _NAT, (), _call(_group(_lambda((), _natural(7)))))
    elaborate(*fixture.response())
    for empty_declaration, explicit_argument in ((False, False), (True, True)):
        fixture = _Fixture()
        fixture.definition("Call", _NAT,
                           () if empty_declaration else (("token", _type("Unit")),), _natural(1))
        fixture.definition("Wrong", _NAT, (), _call("Call", *([_unit()] if explicit_argument else [])))
        _refuses(fixture, "type", "zero-parameter")
    for empty_interface in (False, True):
        fixture = _Fixture()
        signature = _function_type(() if empty_interface else (("published", _type("Unit")),), _NAT)
        implementation = _lambda((("actual", _type("Unit")),) if empty_interface else (), _natural(1))
        fixture.definition("Wrong", signature, (), implementation)
        _refuses(fixture, "type", "zero-parameter")
    for empty_interface in (False, True):
        fixture = _Fixture()
        source_signature = _function_type(((None, _type("Unit")),) if empty_interface else (), _NAT)
        interface = _function_type(() if empty_interface else ((None, _type("Unit")),), _NAT)
        fixture.definition("Apply", _NAT, (("function", interface),), _natural(0))
        fixture.definition("Wrong", _NAT, (("function", source_signature),),
                           _call("Apply", _variable("function")))
        _refuses(fixture, "type", "different source arities")
    fixture = _Fixture()
    fixture.definition("Wrong", _NAT,
                       (("function", _function_type(((None, _type("Unit")),), _NAT)),),
                       _call("function"))
    _refuses(fixture, "type", "zero-parameter")
    fixture = _Fixture()
    fixture.definition("Use", _NAT,
                       (("function", _function_type(((None, _type("Unit")),), _NAT)),),
                       _call("function", _unit()))
    elaborate(*fixture.response())


def _constant_source_protocol() -> None:
    fixture = _Fixture()
    fixture.constant("Answer", _NAT, _binary("+", _natural(20), _natural(22)))
    source, response = fixture.response()
    for mutation in ("name", "keyword", "type", "initializer", "equals", "terminator"):
        changed = copy.deepcopy(response)
        constant = cast("list[Node]", cast("Node", changed["ast"])["declarations"])[0]
        if mutation == "name":
            cast("Node", constant["name"])["text"] = "Other"
        elif mutation == "keyword":
            start, end = cast("list[int]", constant["span"])
            constant["span"] = [start + len("public const "), end]
        elif mutation == "type":
            constant["type"] = None
        elif mutation in {"initializer", "equals"}:
            initial = cast("Node", constant["value"])
            start, end = cast("list[int]", initial["span"])
            initial["span"] = [start - 2, end] if mutation == "equals" else [start, end - 1]
        else:
            start, end = cast("list[int]", constant["span"])
            constant["span"] = [start, end - 1]
        try:
            elaborate(source, changed)
        except VelaError as error:
            ensure(error.kind == "protocol", f"constant {mutation} forgery reached semantic evaluation")
        else:
            raise AssertionError(f"accepted constant {mutation} corruption")
    fixture = _Fixture()
    fixture.constant("First", _NAT, _natural(1))
    fixture.constant("Second", _NAT, _variable("First"))
    source, response = fixture.response()
    for omission in (False, True):
        changed = copy.deepcopy(response)
        root = cast("Node", changed["ast"])
        declarations = cast("list[Node]", root["declarations"])
        root["declarations"] = declarations[1:] if omission else list(reversed(declarations))
        try:
            elaborate(source, changed)
        except VelaError as error:
            ensure(error.kind == "protocol", "module constant order forgery reached dependency checking")
        else:
            raise AssertionError("accepted omitted or reordered module constants")
    fixture = _Fixture()
    fixture.function("Local", _NAT, (),
                     _local_constant("value", _NAT, _natural(1), _variable("value")), block=True)
    source, response = fixture.response()
    for omission in (False, True):
        changed = copy.deepcopy(response)
        declaration = cast("list[Node]", cast("Node", changed["ast"])["declarations"])[0]
        body = cast("Node", declaration["body"])
        statements = cast("list[Node]", body["statements"])
        body["statements"] = statements[1:] if omission else list(reversed(statements))
        try:
            elaborate(source, changed)
        except VelaError as error:
            ensure(error.kind == "protocol", "local constant order forgery reached static evaluation")
        else:
            raise AssertionError("accepted omitted or reordered local constant statements")


def _lexical_boundaries_and_hidden_bindings() -> None:
    def remove_space(fixture: _Fixture, pattern: bytes) -> tuple[bytes, Node]:
        source, response = fixture.response()
        offset = source.index(pattern) + pattern.index(b" ")
        source = source[:offset] + source[offset + 1:]

        def adjust(raw: object) -> None:
            if isinstance(raw, list):
                for child in raw:
                    adjust(child)
            elif isinstance(raw, dict):
                if "span" in raw:
                    raw["span"] = [position - (position > offset) for position in raw["span"]]
                for key, child in raw.items():
                    if key != "span":
                        adjust(child)
        adjust(response)
        response["source_sha256"] = hashlib.sha256(source).hexdigest()
        return source, response

    def refuse(source: bytes, response: Node) -> None:
        try:
            elaborate(source, response)
        except VelaError as error:
            ensure(error.kind == "protocol", "source omission or token splitting reached semantic evaluation")
        else:
            raise AssertionError("accepted source token splitting or hidden runtime binding")

    fixture = _Fixture("X")
    fixture.constant("Limit", _NAT, _natural(1))
    refuse(*remove_space(fixture, b"module X"))
    fixture = _Fixture()
    fixture.constant("Limit", _NAT, _natural(1))
    refuse(*remove_space(fixture, b"Nat Limit"))
    fixture = _Fixture()
    fixture.alias("Same", _T, _POLY)
    fixture.constant("Limit", _type("Same", _NAT), _natural(1))
    elaborate(*remove_space(fixture, b"> Limit"))

    def grouped_type(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("(")
        annotation = _NAT(fixture)
        fixture.write(")")
        return fixture.node("group_type", start, type=annotation)
    fixture = _Fixture()
    fixture.constant("Limit", grouped_type, _natural(1))
    elaborate(*remove_space(fixture, b") Limit"))

    def hidden_body(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("{ ")
        statements: list[Node] = []
        for spelling, initial in (("padding", _variable("Shadow")), ("Shadow", _variable("runtime"))):
            first = fixture.offset
            fixture.write("let ")
            name = fixture.name(spelling)
            fixture.write(" = ")
            value = initial(fixture)
            fixture.write(";")
            statements.append(fixture.node("let", first, name=name, type=None, grade=None, value=value))
            fixture.write(" ")
        statements.append(_local_constant("Chosen", _NAT, _variable("Shadow"), _variable("Chosen"))(fixture))
        fixture.write(" }")
        return fixture.node("block", start, statements=statements)
    fixture = _Fixture()
    fixture.constant("Shadow", _NAT, _natural(1))
    fixture.function("Wrong", _NAT, (("runtime", _NAT),), hidden_body, block=True)
    _refuses(fixture, "type", "nonstatic binding 'Shadow'")
    source, response = fixture.response()
    for widen_value, empty_grade in ((False, False), (True, False), (False, True)):
        changed = copy.deepcopy(response)
        declaration = cast("list[Node]", cast("Node", changed["ast"])["declarations"])[1]
        statements = cast("list[Node]", cast("Node", declaration["body"])["statements"])
        padding, hidden = statements[:2]
        cast("list[int]", padding["span"])[1] = cast("list[int]", hidden["span"])[1]
        if widen_value:
            cast("list[int]", cast("Node", padding["value"])["span"])[1] = cast("list[int]", hidden["span"])[1] - 1
        if empty_grade:
            padding["grade"] = []
        del statements[1]
        refuse(source, changed)
    fixture = _Fixture()
    fixture.constant("Shadow", _NAT, _natural(1))
    fixture.function("Wrong", _NAT, (("Shadow", _NAT),),
                     _local_constant("Chosen", _NAT, _variable("Shadow"), _variable("Chosen")), block=True)
    source, response = fixture.response()
    declaration = cast("list[Node]", cast("Node", response["ast"])["declarations"])[1]
    declaration["parameters"] = []
    refuse(source, response)

    fixture = _Fixture()
    fixture.definition("Identity", _NAT, (("value", _NAT),), _variable("value"))
    source, response = fixture.response()
    for malformed in ([], False, "", 0, {}):
        changed = copy.deepcopy(response)
        declaration = cast("list[Node]", cast("Node", changed["ast"])["declarations"])[0]
        cast("list[Node]", declaration["parameters"])[0]["grade"] = malformed
        refuse(source, changed)


def _named_call_refusals() -> None:
    for labels, fragment in ((("missing", "right"), "expected argument label 'left'"),
                              (("right", "left"), "expected argument label 'left'"),
                              (("left", "left"), "expected argument label 'right'"),
                              (("left", None), "positional arguments cannot follow")):
        fixture = _Fixture()
        fixture.definition("Choose", _NAT, (("left", _NAT), ("right", _NAT)), _variable("left"))
        fixture.definition("Wrong", _NAT, (),
                           _call("Choose", _natural(1), _natural(2), labels=labels))
        _refuses(fixture, "name", fragment)
    fixture = _Fixture()
    fixture.definition("Use", _NAT,
                       (("callback", _function_type(((None, _NAT),), _NAT)),),
                       _call("callback", _natural(1), labels=("implementation",)))
    _refuses(fixture, "name", "unnamed callable parameters")
    fixture = _Fixture()
    fixture.definition("Builtin", _NAT, (), _call("Succ", _natural(1), labels=("value",)))
    _refuses(fixture, "name", "unnamed callable parameters")
    for public_name in ("published", None):
        fixture = _Fixture()
        signature = _function_type(((public_name, _NAT),), _NAT)
        fixture.definition("Build", signature, (),
                           _inferred_lambda(("implementation",), _variable("implementation"), bare=True))
        fixture.definition("Wrong", _NAT, (),
                           _call(_call("Build"), _natural(1), labels=("implementation",)))
        _refuses(fixture, "name", "expected argument label" if public_name else "unnamed callable parameters")
    fixture = _Fixture()
    _identity(fixture)
    fixture.definition("Incomplete", _NAT, (),
                       _call("Identity", _boolean(True), generics=(_NAT,), labels=("value",)))
    _refuses(fixture, "type")
    fixture = _Fixture()
    vector = _type("Vec", _NAT, _type("count"))
    fixture.definition("Keep", vector, (("count", _NAT), ("values", vector)), _variable("values"))
    fixture.definition("WrongIndex", _type("Vec", _NAT, _natural(0)), (),
                       _call("Keep", _natural(1), _call("VNil", generics=(_NAT,)),
                             labels=("count", "values")))
    _refuses(fixture, "type")
    fixture = _Fixture()
    _identity(fixture)
    fixture.theorem("False", (),
                    _binary("==", _call("Identity", _natural(0), labels=("value",)), _natural(1)),
                    _call("Refl", _natural(0)))
    _refuses(fixture, "type")


def _named_argument_source_protocol() -> None:
    fixture = _Fixture()
    _identity(fixture)
    fixture.definition("Use", _NAT, (), _call("Identity", _natural(7), labels=("value",)))
    source, response = fixture.response()
    for mutation in ("label-text", "label-span", "drop-label", "hide-label", "legacy-expression",
                     "value-span", "argument-end", "call-end"):
        changed = copy.deepcopy(response)
        root = cast("Node", changed["ast"])
        declaration = cast("list[Node]", root["declarations"])[1]
        call = cast("Node", declaration["value"])
        arguments = cast("list[Node]", call["arguments"])
        argument = arguments[0]
        value = cast("Node", argument["value"])
        if mutation == "label-text":
            cast("Node", argument["label"])["text"] = "wrong"
        elif mutation == "label-span":
            span = cast("list[int]", cast("Node", argument["label"])["span"])
            cast("Node", argument["label"])["span"] = [span[0] + 1, span[1]]
        elif mutation in {"drop-label", "hide-label"}:
            argument["label"] = None
            if mutation == "hide-label":
                argument["span"] = value["span"]
        elif mutation == "legacy-expression":
            arguments[0] = value
        elif mutation == "value-span":
            value["span"] = argument["span"]
        else:
            node = argument if mutation == "argument-end" else call
            start, end = cast("list[int]", node["span"])
            node["span"] = [start, end - 1]
        try:
            elaborate(source, changed)
        except VelaError as error:
            ensure(error.kind == "protocol", f"argument {mutation} corruption reached semantics")
        else:
            raise AssertionError(f"accepted argument protocol corruption: {mutation}")
    fixture = _Fixture()
    fixture.definition("UnitValue", _type("Unit"), (), _natural(1))
    source, response = fixture.response()
    declaration = cast("list[Node]", cast("Node", response["ast"])["declarations"])[0]
    value = cast("Node", declaration["value"])
    value.pop("value")
    value.pop("suffix")
    value["kind"] = "unit"
    try:
        elaborate(source, response)
    except VelaError as error:
        ensure(error.kind == "protocol", "forged Unit value reached type checking")
    else:
        raise AssertionError("literal bytes reinterpreted as a Unit value")


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


def _pat_wild() -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("_")
        return fixture.node("wildcard_pattern", start)
    return form


def _pat_bind(name: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        return fixture.node("binding_pattern", start, name=fixture.name(name))
    return form


def _pat_unit() -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("()")
        return fixture.node("unit_pattern", start)
    return form


def _pat_group(inner: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("(")
        node = inner(fixture)
        fixture.write(")")
        return fixture.node("group_pattern", start, pattern=node)
    return form


def _pat_tuple(*patterns: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("(")
        nodes = fixture.forms(patterns)
        fixture.write(")")
        return fixture.node("tuple_pattern", start, patterns=nodes)
    return form


def _pat_bool(value: bool) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("true" if value else "false")
        return fixture.node("bool_pattern", start, value=value)
    return form


def _pat_nat(value: int, suffix: str = "") -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(f"{value}{suffix}")
        return fixture.node("nat_pattern", start, value=str(value), suffix=suffix)
    return form


def _pat_ctor(name: str, *arguments: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        ctor = fixture.name(name)
        fixture.write("(")
        nodes = fixture.forms(arguments)
        fixture.write(")")
        return fixture.node("constructor_pattern", start, name=ctor, arguments=nodes)
    return form


def _let_pattern(pattern: Form, value: Form, body: Form, *, block: bool = False) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        if block:
            fixture.write("{ ")
            local_start = fixture.offset
            fixture.write("let ")
            pat_node = pattern(fixture)
            fixture.write(" = ")
            val_node = value(fixture)
            fixture.write(";")
            local_node = fixture.node("let_pattern", local_start, pattern=pat_node, value=val_node)
            fixture.write(" ")
            ret_start = fixture.offset
            fixture.write("return ")
            out_node = body(fixture)
            fixture.write(";")
            ret_node = fixture.node("return", ret_start, value=out_node)
            fixture.write(" }")
            return fixture.node("block", start, statements=[local_node, ret_node])
        fixture.write("let ")
        pat_node = pattern(fixture)
        fixture.write(" = ")
        val_node = value(fixture)
        local_node = fixture.node("let_pattern", start, pattern=pat_node, value=val_node)
        fixture.write(" in ")
        out_node = body(fixture)
        return fixture.node("let_expression", start, binding=local_node, body=out_node)
    return form


def _match_expr(value: Form, arms: tuple[tuple[Form, Form], ...],
                motive: tuple[str, Form] | None = None, *, trailing: bool = False) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("match (")
        scrutinee = value(fixture)
        fixture.write(")")
        motive_node = None
        if motive is not None:
            fixture.write(" ")
            motive_start = fixture.offset
            fixture.write("as ")
            binder = fixture.name(motive[0])
            fixture.write(" : ")
            motive_type = motive[1](fixture)
            motive_node = fixture.node("match_motive", motive_start, name=binder, type=motive_type)
        fixture.write(" {")
        case_nodes: list[Node] = []
        for index, (pat, body) in enumerate(arms):
            if index:
                fixture.write(",")
            fixture.write(" ")
            case_start = fixture.offset
            pat_node = pat(fixture)
            fixture.write(" => ")
            body_node = body(fixture)
            case_nodes.append(fixture.node("expression_case", case_start, pattern=pat_node, value=body_node))
        if arms and trailing:
            fixture.write(",")
        if arms:
            fixture.write(" ")
        fixture.write("}")
        return fixture.node("match_expression", start, value=scrutinee, motive=motive_node, cases=case_nodes)
    return form


def _match_stmt(value: Form, arms: tuple[tuple[Form, Form], ...],
                motive: tuple[str, Form] | None = None) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("{ ")
        match_start = fixture.offset
        fixture.write("match (")
        scrutinee = value(fixture)
        fixture.write(")")
        motive_node = None
        if motive is not None:
            fixture.write(" ")
            motive_start = fixture.offset
            fixture.write("as ")
            binder = fixture.name(motive[0])
            fixture.write(" : ")
            motive_type = motive[1](fixture)
            motive_node = fixture.node("match_motive", motive_start, name=binder, type=motive_type)
        fixture.write(" {")
        case_nodes: list[Node] = []
        for pat, body in arms:
            fixture.write(" ")
            case_start = fixture.offset
            fixture.write("case ")
            pat_node = pat(fixture)
            fixture.write(": ")
            ret_start = fixture.offset
            fixture.write("return ")
            body_node = body(fixture)
            fixture.write(";")
            ret_node = fixture.node("return", ret_start, value=body_node)
            case_nodes.append(fixture.node("case", case_start, pattern=pat_node, statements=[ret_node]))
        if arms:
            fixture.write(" ")
        fixture.write("}")
        match_node = fixture.node("match", match_start, value=scrutinee, motive=motive_node, cases=case_nodes)
        fixture.write(" }")
        return fixture.node("block", start, statements=[match_node])
    return form


def _pattern_matching_and_destructuring() -> None:
    fixture = _Fixture("Patterns")
    fixture.definition(
        "Swap", _tuple(_type("U"), _T, types=True),
        (("pair", _tuple(_T, _type("U"), types=True)),),
        _let_pattern(_pat_tuple(_pat_bind("left"), _pat_bind("right")),
                     _variable("pair"),
                     _tuple(_variable("right"), _variable("left"))),
        (*_POLY, ("type", "U", None)),
    )
    fixture.function(
        "NestedSum", _NAT,
        (("triple", _tuple(_NAT, _NAT, _NAT, types=True)), ("token", _type("Unit"))),
        _let_pattern(
            _pat_unit(), _variable("token"),
            _let_pattern(
                _pat_group(_pat_tuple(_pat_bind("a"), _pat_wild(), _pat_bind("c"))),
                _variable("triple"),
                _binary("+", _variable("a"), _variable("c")),
                block=True,
            ),
            block=True,
        ),
        block=True,
    )
    fixture.definition(
        "Predecessor", _NAT, (("value", _NAT),),
        _match_expr(
            _variable("value"),
            ((_pat_nat(0), _natural(0)),
             (_pat_ctor("Succ", _pat_bind("previous")), _variable("previous"))),
            trailing=True,
        ),
    )
    fixture.definition(
        "ClassifyNat", _NAT, (("value", _NAT),),
        _match_expr(
            _variable("value"),
            ((_pat_nat(0), _natural(10)),
             (_pat_nat(1), _natural(20)),
             (_pat_ctor("Succ", _pat_ctor("Succ", _pat_bind("rest"))), _variable("rest"))),
        ),
    )
    fixture.function(
        "ClassifyPair", _NAT, (("item", _tuple(_BOOL, _NAT, types=True)),),
        _match_stmt(
            _variable("item"),
            ((_pat_tuple(_pat_bool(True), _pat_nat(0)), _natural(1)),
             (_pat_tuple(_pat_bool(True), _pat_ctor("Succ", _pat_bind("k"))),
              _binary("+", _variable("k"), _natural(2))),
             (_pat_tuple(_pat_bool(False), _pat_wild()), _natural(0))),
        ),
        block=True,
    )
    fixture.constant(
        "StaticMatched", _NAT,
        _call("ClassifyNat", _call("NestedSum", _tuple(_natural(1), _natural(9), _natural(1)), _unit())),
    )
    fixture.theorem(
        "PredecessorStep", (("value", _NAT),),
        _binary("==", _call("Predecessor", _call("Succ", _variable("value"))), _variable("value")),
        _call("Refl", _variable("value")),
    )
    fixture.theorem(
        "StaticMatchedValue", (),
        _binary("==", _variable("StaticMatched"), _natural(0)),
        _call("Refl", _natural(0)),
    )
    fixture.definition(
        "Not", _BOOL, (("flag", _BOOL),),
        _match_expr(
            _variable("flag"),
            ((_pat_bool(True), _boolean(False)),
             (_pat_bool(False), _boolean(True))),
        ),
    )
    fixture.theorem(
        "BoolInvolution", (("flag", _BOOL),),
        _binary("==", _call("Not", _call("Not", _variable("flag"))), _variable("flag")),
        _match_expr(
            _variable("flag"),
            ((_pat_bool(True), _call("Refl", _boolean(True))),
             (_pat_bool(False), _call("Refl", _boolean(False)))),
            motive=("branch", _computed(_call("Eq", _call("Not", _call("Not", _variable("branch"))),
                                              _variable("branch")))),
        ),
    )
    fixture.theorem(
        "UnitEta", (("token", _type("Unit")),),
        _binary("==", _variable("token"), _unit()),
        _match_expr(
            _variable("token"),
            ((_pat_unit(), _call("Refl", _unit())),),
            motive=("current", _computed(_call("Eq", _variable("current"), _unit()))),
        ),
    )
    fixture.theorem(
        "PairEta", (("pair", _tuple(_T, _type("U"), types=True)),),
        _binary("==", _variable("pair"),
                _tuple(_call("Fst", _variable("pair")), _call("Snd", _variable("pair")))),
        _match_expr(
            _variable("pair"),
            ((_pat_tuple(_pat_bind("left"), _pat_bind("right")),
              _call("Refl", _tuple(_variable("left"), _variable("right")))),),
            motive=("whole", _computed(_call("Eq", _variable("whole"),
                                             _tuple(_call("Fst", _variable("whole")),
                                                    _call("Snd", _variable("whole")))))),
        ),
        (*_POLY, ("type", "U", None)),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Corelib.Init.Datatypes.O =>" in emitted and "Corelib.Init.Datatypes.S " in emitted,
           "Nat match lost its constructor branches")
    ensure("@Corelib.Init.Datatypes.pair _ _" in emitted,
           "product match lost its pair elimination branch")


def _pattern_matching_refusals_and_protocol() -> None:
    for name, body, kind, fragment in (
        ("NonExhaustiveZero", _match_expr(_variable("value"), ((_pat_nat(0), _natural(0)),)),
         "type", "non-exhaustive"),
        ("NonExhaustiveOne", _match_expr(_variable("value"),
                                         ((_pat_nat(0), _natural(0)), (_pat_nat(1), _natural(1)))),
         "type", "non-exhaustive"),
        ("NonExhaustiveSucc", _match_expr(_variable("value"),
                                          ((_pat_ctor("Succ", _pat_bind("k")), _variable("k")),)),
         "type", "non-exhaustive"),
        ("EmptyMatch", _match_expr(_variable("value"), ()), "type", "non-exhaustive"),
        ("RefutableLocal", _let_pattern(_pat_ctor("Succ", _pat_bind("k")), _variable("value"), _variable("k")),
         "type", "irrefutable"),
        ("RefutableTupleLocal", _let_pattern(_pat_tuple(_pat_nat(0), _pat_bind("k")),
                                             _tuple(_variable("value"), _variable("value")), _variable("k")),
         "type", "irrefutable"),
        ("DuplicateTupleBinder", _let_pattern(_pat_tuple(_pat_bind("x"), _pat_bind("x")),
                                              _tuple(_variable("value"), _variable("value")), _variable("x")),
         "name", "duplicate"),
        ("DuplicateMatchBinder", _match_expr(_tuple(_variable("value"), _variable("value")),
                                             ((_pat_tuple(_pat_bind("x"), _pat_bind("x")), _variable("x")),)),
         "name", "duplicate"),
        ("UnknownConstructor", _match_expr(_variable("value"), ((_pat_ctor("Missing", _pat_bind("k")), _variable("k")),)),
         "name", "unknown constructor"),
        ("IndexedConstructor", _match_expr(_variable("value"), ((_pat_ctor("VNil"), _natural(0)),)),
         "unsupported", "indexed elimination"),
        ("WrongSuccArity", _match_expr(_variable("value"),
                                       ((_pat_nat(0), _natural(0)),
                                        (_pat_ctor("Succ", _pat_bind("a"), _pat_bind("b")), _variable("a")))),
         "type", "expects 1"),
        ("WrongPatternType", _match_expr(_variable("value"),
                                         ((_pat_bool(True), _natural(1)), (_pat_bool(False), _natural(0)))),
         "type", ""),
        ("NotAProductScrutinee", _let_pattern(_pat_tuple(_pat_bind("a"), _pat_bind("b")),
                                              _variable("value"), _variable("a")),
         "type", "product"),
        ("PatternBoundLimit", _match_expr(_variable("value"),
                                          ((_pat_nat(65), _natural(1)), (_pat_wild(), _natural(0)))),
         "limit", "structural bound"),
    ):
        wrong = _Fixture("PatternRefusals")
        wrong.definition(name, _NAT, (("value", _NAT),), body)
        _refuses(wrong, kind, fragment)

    fixture = _Fixture("PatternProtocol")
    fixture.definition(
        "Valid", _NAT, (("pair", _tuple(_NAT, _NAT, types=True)),),
        _let_pattern(_pat_tuple(_pat_bind("a"), _pat_bind("b")), _variable("pair"),
                     _match_expr(_variable("a"),
                                 ((_pat_nat(0), _variable("b")),
                                  (_pat_ctor("Succ", _pat_bind("k")), _variable("k"))))),
    )
    source, response = fixture.response()
    elaborate(source, response)

    tampered = copy.deepcopy(response)
    declaration = cast("list[Node]", cast("Node", tampered["ast"])["declarations"])[0]
    let_expr = cast("Node", declaration["value"])
    let_pat = cast("Node", let_expr["binding"])
    tuple_pat = cast("Node", let_pat["pattern"])
    first_bind = cast("list[Node]", tuple_pat["patterns"])[0]
    cast("Node", first_bind["name"])["text"] = "_"
    try:
        elaborate(source, tampered)
    except VelaError as error:
        ensure(error.kind == "protocol", "wildcard inside binding_pattern reached semantics")
    else:
        raise AssertionError("accepted binding_pattern with wildcard text")


def _string_literal(spelling: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(spelling)
        return fixture.node("string", start, value=spelling)
    return form


def _interpolated_literal(spelling: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(spelling)
        return fixture.node("interpolated_string", start, value=spelling)
    return form


def _member(receiver: Form, member_name: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        value = receiver(fixture)
        fixture.write(".")
        name = fixture.name(member_name)
        return fixture.node("member", start, value=value, name=name)
    return form


def _ref_arg(inner: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        operator = fixture.name("ref")
        fixture.write(" ")
        value = inner(fixture)
        return fixture.node("unary", start, operator=operator, value=value)
    return form


def _raw_strings_and_checked_formatting() -> None:
    fixture = _Fixture("CheckedFormatting")
    raw_multiline = '"""\n    [vela-hdr]\n    """'
    fixture.definition("HeaderTag", _type("Vec", _NAT, _natural(10)), (), _string_literal(raw_multiline))
    fixture.constant("HeaderBytes", _NAT, _call("ByteLength", _call("HeaderTag")))
    fixture.definition(
        "FormatPacket",
        _type("TextBuilder", _natural(36)),
        (("id", _NAT), ("ok", _BOOL)),
        _call(
            _member(_variable("Format"), "Write"),
            _ref_arg(
                _call(
                    _member(_variable("Format"), "Write"),
                    _ref_arg(_call("EmptyBuilder", generics=(_natural(36),))),
                    _interpolated_literal('$"hdr={HeaderTag()} "'),
                )
            ),
            _interpolated_literal('$"id=0x{id:x4} ok={ok}"'),
        ),
    )
    fixture.theorem(
        "DedentedLength",
        (),
        _binary("==", _variable("HeaderBytes"), _natural(10)),
        _call("Refl", _natural(10)),
    )
    fixture.theorem(
        "PacketWrites32",
        (),
        _binary("==", _call("Written", _call("FormatPacket", _natural(42), _boolean(True))), _natural(32)),
        _call("Refl", _natural(32)),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("vela_TextBuilder" in emitted and "vela_FormatStep" in emitted,
           "elaborated Gallina lost TextBuilder or FormatStep definitions")

    standalone = _Fixture("StandaloneInterpolated")
    standalone.definition("Wrong", _type("Vec", _NAT, _natural(3)), (), _interpolated_literal('$"abc"'))
    _refuses(standalone, "type", "Format.Write")

    missing_ref = _Fixture("MissingRef")
    missing_ref.definition(
        "Wrong",
        _type("TextBuilder", _natural(16)),
        (("b", _type("TextBuilder", _natural(16))),),
        _call(_member(_variable("Format"), "Write"), _variable("b"), _interpolated_literal('$"ok"')),
    )
    _refuses(missing_ref, "type", "ref TextBuilder")

    alias_read = _Fixture("AliasRead")
    alias_read.definition(
        "Wrong",
        _type("TextBuilder", _natural(16)),
        (("b", _type("TextBuilder", _natural(16))),),
        _call(
            _member(_variable("Format"), "Write"),
            _ref_arg(_variable("b")),
            _interpolated_literal('$"n={Written(b):x4}"'),
        ),
    )
    _refuses(alias_read, "type", "alias")


def cases() -> list[Case]:
    return [Case("fresh-polymorphism-and-higher-order-inference", _polymorphism_and_higher_order),
            Case("familiar-generic-markers-and-mathematical-body-source-binding", _familiar_generic_spellings),
            Case("canonical-named-dependent-call-term-agreement", _canonical_named_call_terms),
            Case("required-static-values-and-dependent-indices", _required_static_constants),
            Case("static-dependencies-types-and-numeric-bounds", _static_dependency_refusals),
            Case("source-nullary-versus-explicit-Unit-arities", _source_callable_arities),
            Case("constant-complete-source-protocol", _constant_source_protocol),
            Case("lexical-edges-and-hidden-runtime-binding-refusals", _lexical_boundaries_and_hidden_bindings),
            Case("named-call-interface-order-and-semantic-refusals", _named_call_refusals),
            Case("named-argument-complete-source-protocol", _named_argument_source_protocol),
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
            Case("inference-reduction-and-output-budgets", _elaboration_budgets),
            Case("pattern-matching-and-product-destructuring", _pattern_matching_and_destructuring),
            Case("pattern-matching-refusals-and-protocol", _pattern_matching_refusals_and_protocol),
            Case("raw-strings-and-checked-formatting", _raw_strings_and_checked_formatting)]
