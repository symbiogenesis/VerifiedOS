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
from vos.vela import elaborate as language
from vos.vela.ast import VelaError
from vos.vela.elaborate import elaborate, elaborate_package

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
                proof: Form | None, generics: tuple[Generic, ...] = (),
                contracts: tuple[Form, ...] = ()) -> None:
        self.write("\n")
        start = self.offset
        self.write("public lemma ")
        binding = self.name(name)
        generic_nodes = self.generics(generics)
        parameter_nodes = self.parameters(parameters)
        obligations: list[Node] = []
        for contract in contracts:
            self.write(" ")
            obligations.append(contract(self))
        self.write(" ")
        obligations.append(_contract("ensures", proposition)(self))
        body = None
        if proof is None:
            self.write(";")
        else:
            self.write(" proof ")
            saved_text = self.text
            block_start = self.offset
            self.write("{ ")
            probe_text = self.text
            probe_node = proof(self)
            if probe_node["kind"] == "block":
                self.text = saved_text
                body = proof(self)
            elif probe_node["kind"] in {"assert", "return", "match", "if", "proof"}:
                self.write(" }")
                body = self.node("block", block_start, statements=[probe_node])
            else:
                self.text = probe_text
                return_start = self.offset
                self.write("return ")
                value = proof(self)
                self.write(";")
                terminal = self.node("return", return_start, value=value)
                self.write(" }")
                body = self.node("block", block_start, statements=[terminal])
        self.declarations.append(self.node("lemma", start, name=binding, generics=generic_nodes,
                                           parameters=parameter_nodes, contracts=obligations, body=body,
                                           modifiers=["public"]))

    def function(self, name: str, result: Form, parameters: tuple[Parameter, ...], value: Form,
                 *, arrow: bool = True, block: bool = False, constant: bool = False,
                 generics: tuple[Generic, ...] = (), contracts: tuple[Form, ...] = ()) -> None:
        self.write("\n")
        start = self.offset
        self.write("public const " if constant else "public ")
        annotation = result(self)
        self.write(" ")
        binding = self.name(name)
        generic_nodes = self.generics(generics)
        parameter_nodes = self.parameters(parameters)
        obligations: list[Node] = []
        for contract in contracts:
            self.write(" ")
            obligations.append(contract(self))
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
                                           generics=generic_nodes, parameters=parameter_nodes,
                                           contracts=obligations,
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

    def record(self, name: str, parameters: tuple[Parameter, ...],
               properties: tuple[tuple[str, Form, Form], ...] = (),
               generics: tuple[Generic, ...] = (),
               contracts: tuple[Form, ...] = ()) -> None:
        self.write("\n")
        start = self.offset
        self.write("public record ")
        binding = self.name(name)
        generic_nodes = self.generics(generics)
        parameter_nodes = self.parameters(parameters)
        obligations: list[Node] = []
        for contract in contracts:
            self.write(" ")
            obligations.append(contract(self))
        member_nodes: list[Node] = []
        if properties:
            self.write(" {")
            for prop_name, prop_type, prop_value in properties:
                self.write(" ")
                prop_start = self.offset
                self.write("public ")
                annotation = prop_type(self)
                self.write(" ")
                prop_binding = self.name(prop_name)
                self.write(" => ")
                body = prop_value(self)
                self.write(";")
                member_nodes.append(
                    self.node("property", prop_start, name=prop_binding, type=annotation,
                              contracts=[], value=body, modifiers=["public"])
                )
            self.write(" }")
        else:
            self.write(";")
        self.declarations.append(
            self.node("record", start, name=binding, generics=generic_nodes,
                      parameters=parameter_nodes, contracts=obligations, declarations=member_nodes,
                      modifiers=["public"])
        )

    def union(self, name: str, constructors: tuple[tuple[str, tuple[Parameter, ...]], ...],
              generics: tuple[Generic, ...] = ()) -> None:
        self.write("\n")
        start = self.offset
        self.write("public union ")
        binding = self.name(name)
        generic_nodes = self.generics(generics)
        self.write(" {")
        ctor_nodes: list[Node] = []
        for ctor_name, ctor_params in constructors:
            self.write(" ")
            cstart = self.offset
            c_binding = self.name(ctor_name)
            p_nodes = self.parameters(ctor_params)
            self.write(";")
            ctor_nodes.append(
                self.node("constructor", cstart, name=c_binding, parameters=p_nodes,
                          result=None, contracts=[])
            )
        if constructors:
            self.write(" ")
        self.write("}")
        self.declarations.append(
            self.node("union", start, name=binding, generics=generic_nodes,
                      contracts=[], constructors=ctor_nodes, modifiers=["public"])
        )

    def property_decl(self, name: str, value_type: Form, value: Form) -> None:
        self.write("\n")
        start = self.offset
        self.write("public ")
        annotation = value_type(self)
        self.write(" ")
        binding = self.name(name)
        self.write(" => ")
        body = value(self)
        self.write(";")
        self.declarations.append(
            self.node("property", start, name=binding, type=annotation,
                      contracts=[], value=body, modifiers=["public"])
        )

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


def _variable(name: str, *generics: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        base = fixture.node("name", start, name=fixture.name(name))
        if generics:
            fixture.write("::<")
            gen_nodes = fixture.forms(generics)
            fixture.write(">")
            return fixture.node("generic_application", start, value=base, arguments=gen_nodes)
        return base
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


def _assert(value: Form, by: Form | None = None, *, by_block: tuple[Form, ...] | None = None) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("assert ")
        val_node = value(fixture)
        by_node = None
        if by_block is not None:
            fixture.write(" by ")
            block_start = fixture.offset
            fixture.write("{ ")
            stmts: list[Node] = []
            for index, stmt in enumerate(by_block):
                if index:
                    fixture.write(" ")
                stmts.append(stmt(fixture))
            fixture.write(" }")
            by_node = fixture.node("block", block_start, statements=stmts)
        elif by is not None:
            fixture.write(" by ")
            by_node = by(fixture)
            fixture.write(";")
        else:
            fixture.write(";")
        return fixture.node("assert", start, value=val_node, by=by_node)
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
                    _assert(_binary("==", _variable("Answer"), _natural(42))))
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
                    _assert(_binary("==", _call("Identity", _natural(0), labels=("value",)), _natural(1))))
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
    _identity(fixture)
    x = _variable("x")
    fixture.theorem("Reflexive", (("x", _T),), _binary("==", x, x), _assert(_binary("==", x, x)), _POLY)
    fixture.theorem(
        "Composed",
        (("x", _NAT),),
        _binary("==", x, x),
        _assert(
            _binary("==", x, x),
            by_block=(
                _assert(_binary("==", x, _call("Identity", x))),
                _assert(_binary("==", _call("Identity", x), x)),
            ),
        ),
    )
    fixture.theorem(
        "Congruent",
        (("x", _NAT),),
        _binary("==", _binary("+", x, _natural(1)), _binary("+", x, _natural(1))),
        _assert(
            _binary("==", _binary("+", x, _natural(1)), _binary("+", x, _natural(1))),
            by=_call("Reflexive", x),
        ),
    )
    fixture.definition("ProofParameter", _computed(_call("Eq", x, x, generics=(_NAT,))),
                       (("x", _NAT), ("evidence", _computed(_call("Eq", x, x, generics=(_NAT,))))),
                       _variable("evidence"))
    proposition_generic: tuple[Generic, ...] = (("type", "P", _type("Prop")),)
    fixture.definition("KeepProof", _type("P"), (("evidence", _type("P")),),
                       _variable("evidence"), proposition_generic)
    fixture.theorem("ForwardProof", (("evidence", _type("P")),), _variable("P"),
                    _assert(_variable("P"), by=_call("KeepProof", _variable("evidence"))),
                    proposition_generic)
    fixture.theorem("WithRequires", (("x", _NAT),), _binary("==", x, _natural(0)),
                    _assert(_binary("==", x, _natural(0))),
                    contracts=(_contract("requires", _binary("==", x, _natural(0))),))
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Corelib.Init.Logic.eq" in emitted, "proof goal omitted propositional equality")
    ensure(
        "Corelib.Init.Logic.eq_refl" in emitted
        and "Corelib.Init.Logic.eq_sym" in emitted
        and "Corelib.Init.Logic.eq_trans" in emitted
        and "vela_Congr" in emitted,
        "assert and by-justifications omitted equality proof constructors",
    )
    for name, goal, proof, kind in (
            ("False", _binary("==", _natural(0), _natural(1)),
             _assert(_binary("==", _natural(0), _natural(1))), "type"),
            ("FalseByExpr", _binary("==", _natural(0), _natural(1)),
             _assert(_binary("==", _natural(0), _natural(1)), by=_natural(0)), "type"),
            ("FalseByBlock", _binary("==", _natural(0), _natural(0)),
             _assert(_binary("==", _natural(0), _natural(0)),
                     by_block=(_assert(_binary("==", _natural(1), _natural(1))),)), "type"),
            ("ObsoleteRefl", _binary("==", _natural(0), _natural(0)),
             _call("Refl", _natural(0)), "name"),
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
                    _binary("==", _binary("+", _natural(0), n), n),
                    _assert(_binary("==", _binary("+", _natural(0), n), n)))
    identity = _group(_lambda((("value", _NAT),), _variable("value")))
    fixture.theorem("Beta", (("n", _NAT),), _binary("==", _call(identity, n), n),
                    _assert(_binary("==", _call(identity, n), n)))
    fixture.definition("ComputedLength", _type("Vec", _NAT,
                                               _group(_binary("+", _natural(0), _natural(1)))), (),
                       _call("VCons", _natural(4), _call("VNil", generics=(_NAT,))))
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Corelib.Init.Logic.eq_refl" in emitted, "definitional equality lost its proof constructor")
    # Nat.add recurses on its first operand: n + 0 is stuck for arbitrary n.
    # Accepting this neighbor with bare assert would invent an arithmetic theorem.
    wrong = _Fixture()
    wrong.theorem("ZeroOnRight", (("n", _NAT),),
                  _binary("==", _binary("+", n, _natural(0)), n),
                  _assert(_binary("==", _binary("+", n, _natural(0)), n)))
    _refuses(wrong, "type")


def _products_and_lookup_computation() -> None:
    fixture = _Fixture("Elimination")
    fixture.definition("First", _NAT, (),
                       _call("Fst", _tuple(_natural(7), _boolean(True))))
    fixture.definition("Second", _BOOL, (),
                       _call("Snd", _tuple(_natural(7), _boolean(True)), generics=(_NAT, _BOOL)))
    fixture.theorem("Projection", (),
                    _binary("==", _call("Fst", _tuple(_natural(7), _boolean(False))), _natural(7)),
                    _assert(_binary("==", _call("Fst", _tuple(_natural(7), _boolean(False))), _natural(7))))
    values = _call("VCons", _natural(7),
                   _call("VCons", _natural(9), _call("VNil", generics=(_NAT,))))
    fixture.theorem("LookupFirst", (),
                    _binary("==", _call("At", values, _call("FZero", generics=(_natural(1),))),
                            _natural(7)),
                    _assert(_binary("==", _call("At", values, _call("FZero", generics=(_natural(1),))),
                                    _natural(7))))
    fixture.theorem("LookupSecond", (),
                    _binary("==", _call("At", values,
                                        _call("FSucc", _call("FZero", generics=(_natural(0),)))),
                            _natural(9)),
                    _assert(_binary("==", _call("At", values,
                                                _call("FSucc", _call("FZero", generics=(_natural(0),)))),
                                    _natural(9))))
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
                          _natural(9)),
                  _assert(_binary("==", _call("At", values, _call("FZero", generics=(_natural(1),))),
                                  _natural(9))))
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
                    _assert(_binary("==", _binary("+", _natural(1), _natural(1)), _natural(2))))
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
        if arguments:
            fixture.write("(")
            nodes = fixture.forms(arguments)
            fixture.write(")")
        else:
            nodes = []
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
                motive: tuple[str, Form] | None = None, *, assert_arms: bool = False) -> Form:
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
            pat_node = pat(fixture)
            fixture.write(" => ")
            if assert_arms:
                stmt_node = body(fixture)
                case_nodes.append(fixture.node("case", case_start, pattern=pat_node, statements=[stmt_node]))
            else:
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
        _assert(_binary("==", _call("Predecessor", _call("Succ", _variable("value"))), _variable("value"))),
    )
    fixture.theorem(
        "StaticMatchedValue", (),
        _binary("==", _variable("StaticMatched"), _natural(0)),
        _assert(_binary("==", _variable("StaticMatched"), _natural(0))),
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
        _match_stmt(
            _variable("flag"),
            ((_pat_bool(True),
              _assert(_binary("==", _call("Not", _call("Not", _boolean(True))), _boolean(True)))),
             (_pat_bool(False),
              _assert(_binary("==", _call("Not", _call("Not", _boolean(False))), _boolean(False))))),
            assert_arms=True,
        ),
    )
    fixture.theorem(
        "UnitEta", (("token", _type("Unit")),),
        _binary("==", _variable("token"), _unit()),
        _match_stmt(
            _variable("token"),
            ((_pat_unit(), _assert(_binary("==", _unit(), _unit()))),),
            motive=("current", _computed(_call("Eq", _variable("current"), _unit()))),
            assert_arms=True,
        ),
    )
    fixture.theorem(
        "PairEta", (("pair", _tuple(_T, _type("U"), types=True)),),
        _binary("==", _variable("pair"),
                _tuple(_call("Fst", _variable("pair")), _call("Snd", _variable("pair")))),
        _match_stmt(
            _variable("pair"),
            ((_pat_tuple(_pat_bind("left"), _pat_bind("right")),
              _assert(_binary("==", _tuple(_variable("left"), _variable("right")),
                              _tuple(_call("Fst", _tuple(_variable("left"), _variable("right"))),
                                     _call("Snd", _tuple(_variable("left"), _variable("right"))))))),),
            motive=("whole", _computed(_call("Eq", _variable("whole"),
                                             _tuple(_call("Fst", _variable("whole")),
                                                    _call("Snd", _variable("whole")))))),
            assert_arms=True,
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
        _assert(_binary("==", _variable("HeaderBytes"), _natural(10))),
    )
    fixture.theorem(
        "PacketWrites32",
        (),
        _binary("==", _call("Written", _call("FormatPacket", _natural(42), _boolean(True))), _natural(32)),
        _assert(_binary("==", _call("Written", _call("FormatPacket", _natural(42), _boolean(True))), _natural(32))),
    )
    fixture.definition(
        "Scale",
        _NAT,
        (("factor", _NAT), ("value", _NAT)),
        _binary("*", _variable("factor"), _variable("value")),
    )
    fixture.record("Holder", (("b", _NAT),))
    fixture.definition(
        "FormatComputed",
        _type("TextBuilder", _natural(48)),
        (("b", _type("TextBuilder", _natural(48))), ("holder", _type("Holder")), ("id", _NAT), ("ok", _BOOL)),
        _call(
            _member(_variable("Format"), "Write"),
            _ref_arg(_variable("b")),
            _interpolated_literal(
                '$"next=0x{id + 1:x4} scaled=0x{Scale(factor: 2, value: holder.b):x4} cond={if (ok) true else false}"'
            ),
        ),
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
            _interpolated_literal('$"n={Written(b) + 1:x4}"'),
        ),
    )
    _refuses(alias_read, "type", "alias")

    bad_hole_syntax = _Fixture("BadHoleSyntax")
    bad_hole_syntax.definition(
        "Wrong",
        _type("TextBuilder", _natural(16)),
        (("b", _type("TextBuilder", _natural(16))), ("id", _NAT)),
        _call(
            _member(_variable("Format"), "Write"),
            _ref_arg(_variable("b")),
            _interpolated_literal('$"n={id + :x4}"'),
        ),
    )
    _refuses(bad_hole_syntax, "unsupported", "hole")


def _if_expr(condition: Form, yes: Form, no: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("if (")
        cond_node = condition(fixture)
        fixture.write(") ")
        yes_node = yes(fixture)
        fixture.write(" else ")
        no_node = no(fixture)
        return fixture.node("if_expression", start, condition=cond_node, **{"then": yes_node, "else": no_node})
    return form


def _with_expr(value: Form, updates: tuple[tuple[str, Form], ...]) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        val_node = value(fixture)
        fixture.write(" with { ")
        update_nodes: list[Node] = []
        for index, (fname, fval) in enumerate(updates):
            if index:
                fixture.write(", ")
            ustart = fixture.offset
            name_node = fixture.name(fname)
            fixture.write(" = ")
            fval_node = fval(fixture)
            update_nodes.append(fixture.node("field_update", ustart, name=name_node, value=fval_node))
        fixture.write(" }")
        return fixture.node("with_expression", start, value=val_node, updates=update_nodes)
    return form


def _is_expr(value: Form, pattern: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        val_node = value(fixture)
        fixture.write(" is ")
        pat_node = pattern(fixture)
        return fixture.node("is", start, value=val_node, pattern=pat_node)
    return form


def _pat_labeled(label: str, pattern: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        lbl_node = fixture.name(label)
        fixture.write(": ")
        pat_node = pattern(fixture)
        return fixture.node("labeled_pattern", start, label=lbl_node, pattern=pat_node)
    return form


def _let_else_block(pattern: Form, value: Form, otherwise: Form, body: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("{ ")
        le_start = fixture.offset
        fixture.write("let ")
        pat_node = pattern(fixture)
        fixture.write(" = ")
        val_node = value(fixture)
        fixture.write(" else ")
        else_start = fixture.offset
        fixture.write("{ ")
        else_ret_start = fixture.offset
        fixture.write("return ")
        else_val = otherwise(fixture)
        fixture.write(";")
        else_ret = fixture.node("return", else_ret_start, value=else_val)
        fixture.write(" }")
        else_blk = fixture.node("block", else_start, statements=[else_ret])
        le_node = fixture.node("let_else", le_start, pattern=pat_node, value=val_node, **{"else": else_blk})
        fixture.write(" ")
        ret_start = fixture.offset
        fixture.write("return ")
        out_val = body(fixture)
        fixture.write(";")
        ret_node = fixture.node("return", ret_start, value=out_val)
        fixture.write(" }")
        return fixture.node("block", start, statements=[le_node, ret_node])
    return form


def _records_properties_updates_guards_and_expressions() -> None:
    fixture = _Fixture("Ergonomics")
    fixture.record(
        "Counter",
        (("Value", _NAT), ("Limit", _NAT)),
        properties=(
            ("AtLimit", _BOOL, _binary(">=", _member(_variable("this"), "Value"), _member(_variable("this"), "Limit"))),
            ("Remaining", _NAT, _binary("-", _member(_variable("this"), "Limit"), _member(_variable("this"), "Value"))),
        ),
    )
    fixture.property_decl("DefaultStep", _NAT, _natural(1))
    fixture.definition(
        "Advance",
        _type("Counter"),
        (("counter", _type("Counter")), ("step", _NAT)),
        _if_expr(
            _member(_variable("counter"), "AtLimit"),
            _variable("counter"),
            _with_expr(
                _variable("counter"),
                (("Value", _binary("+", _member(_variable("counter"), "Value"), _variable("step"))),),
            ),
        ),
    )
    fixture.definition(
        "Unpack",
        _NAT,
        (("counter", _type("Counter")),),
        _match_expr(
            _variable("counter"),
            ((
                _pat_ctor(
                    "Counter",
                    _pat_labeled("Value", _pat_bind("current")),
                    _pat_labeled("Limit", _pat_bind("maximum")),
                ),
                _if_expr(
                    _binary("<=", _variable("current"), _variable("maximum")),
                    _binary("-", _variable("maximum"), _variable("current")),
                    _natural(0),
                ),
            ),),
        ),
    )
    fixture.function(
        "StepIfPositive",
        _NAT,
        (("value", _NAT), ("counter", _type("Counter"))),
        _let_else_block(
            _pat_ctor("Succ", _pat_bind("previous")),
            _variable("value"),
            _member(_variable("counter"), "Value"),
            _if_expr(
                _is_expr(_variable("previous"), _pat_ctor("Succ", _pat_bind("inner"))),
                _binary(
                    "+",
                    _binary("+", _member(_variable("counter"), "Value"), _variable("inner")),
                    _member(_variable("counter"), "Limit"),
                ),
                _binary("+", _member(_variable("counter"), "Value"), _member(_variable("counter"), "Limit")),
            ),
        ),
        block=True,
    )
    sample = _call("Counter", _natural(2), _natural(5), labels=("Value", "Limit"))
    fixture.theorem(
        "AdvanceCheck",
        (),
        _binary(
            "==",
            _member(_call("Advance", sample, _variable("DefaultStep")), "Value"),
            _natural(3),
        ),
        _assert(
            _binary(
                "==",
                _member(_call("Advance", sample, _variable("DefaultStep")), "Value"),
                _natural(3),
            )
        ),
    )
    fixture.theorem(
        "UnpackCheck",
        (),
        _binary("==", _call("Unpack", sample), _member(sample, "Remaining")),
        _assert(_binary("==", _call("Unpack", sample), _member(sample, "Remaining"))),
    )
    fixture.theorem(
        "GuardCheck",
        (),
        _binary(
            "==",
            _call("StepIfPositive", _natural(2), _call("Counter", _natural(10), _natural(5))),
            _natural(15),
        ),
        _assert(
            _binary(
                "==",
                _call("StepIfPositive", _natural(2), _call("Counter", _natural(10), _natural(5))),
                _natural(15),
            )
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("vela_d0_Counter" in emitted and "vela_d5_Counter_Remaining" in emitted,
           "elaborated Gallina omitted record or property definitions")

    for name, result_type, body, kind, fragment in (
        ("IfNonBool", _NAT, _if_expr(_natural(1), _natural(1), _natural(0)), "type", ""),
        ("IfBranchMismatch", _NAT, _if_expr(_boolean(True), _natural(1), _boolean(False)), "type", ""),
        ("WithNonRecord", _NAT, _with_expr(_natural(1), (("Value", _natural(2)),)), "type", "record"),
        ("UnknownLabelPattern", _NAT, _match_expr(
            _variable("counter"),
            ((_pat_ctor("Counter", _pat_labeled("Missing", _pat_bind("x")), _pat_labeled("Limit", _pat_bind("y"))),
              _variable("x")),)), "name", "expected pattern field label"),
        ("OutOfOrderLabelPattern", _NAT, _match_expr(
            _variable("counter"),
            ((_pat_ctor("Counter", _pat_labeled("Limit", _pat_bind("y")), _pat_labeled("Value", _pat_bind("x"))),
              _variable("x")),)), "name", "expected pattern field label"),
        ("PositionalAfterLabelPattern", _NAT, _match_expr(
            _variable("counter"),
            ((_pat_ctor("Counter", _pat_labeled("Value", _pat_bind("x")), _pat_bind("y")),
              _variable("x")),)), "name", "positional pattern"),
        ("UnnamedConstructorLabelPattern", _NAT, _match_expr(
            _natural(1),
            ((_pat_nat(0), _natural(0)),
             (_pat_ctor("Succ", _pat_labeled("value", _pat_bind("k"))), _variable("k"))),), "name", "does not accept labeled pattern arguments"),
        ("WithUnknownField", _type("Counter"), _with_expr(_variable("counter"), (("Missing", _natural(1)),)), "name", "no field"),
        ("WithOutOfOrder", _type("Counter"), _with_expr(
            _variable("counter"),
            (("Limit", _natural(1)), ("Value", _natural(2))),
        ), "name", "declaration order"),
        ("WithDuplicateField", _type("Counter"), _with_expr(
            _variable("counter"),
            (("Value", _natural(1)), ("Value", _natural(2))),
        ), "name", "duplicate field"),
        ("WithTypeMismatch", _type("Counter"), _with_expr(_variable("counter"), (("Value", _boolean(True)),)), "type", ""),
        ("UnknownProperty", _NAT, _member(_variable("counter"), "Missing"), "name", "no field or property"),
    ):
        wrong = _Fixture("ErgonomicsRefusals")
        wrong.record("Counter", (("Value", _NAT), ("Limit", _NAT)))
        wrong.definition(name, result_type, (("counter", _type("Counter")),), body)
        _refuses(wrong, kind, fragment)


def _union_declarations_and_elimination() -> None:
    fixture = _Fixture("Unions")
    fixture.union(
        "Option",
        (("None", ()), ("Some", (("Value", _T),))),
        generics=_POLY,
    )
    fixture.union(
        "Status",
        (
            ("Idle", ()),
            ("Busy", (("Step", _NAT),)),
            ("Split", (("Left", _NAT), ("Right", _NAT))),
        ),
    )
    fixture.union("Single", (("Only", (("Item", _NAT),)),))
    fixture.definition(
        "UnwrapOr",
        _T,
        (("item", _type("Option", _T)), ("fallback", _T)),
        _match_expr(
            _variable("item"),
            (
                (_pat_ctor("None"), _variable("fallback")),
                (_pat_ctor("Some", _pat_labeled("Value", _pat_bind("inner"))), _variable("inner")),
            ),
        ),
        generics=_POLY,
    )
    fixture.definition(
        "MeasureStatus",
        _NAT,
        (("status", _type("Status")),),
        _match_expr(
            _variable("status"),
            (
                (_pat_ctor("Idle"), _natural(0)),
                (_pat_ctor("Busy", _pat_labeled("Step", _pat_bind("step"))), _variable("step")),
                (
                    _pat_ctor(
                        "Split",
                        _pat_labeled("Left", _pat_bind("left")),
                        _pat_labeled("Right", _pat_bind("right")),
                    ),
                    _binary("+", _variable("left"), _variable("right")),
                ),
            ),
        ),
    )
    fixture.definition(
        "UnwrapSingle",
        _NAT,
        (("single", _type("Single")),),
        _match_expr(_variable("single"), ((_pat_ctor("Only", _pat_bind("v")), _variable("v")),)),
    )
    fixture.function(
        "UnwrapGuarded",
        _NAT,
        (("item", _type("Option", _NAT)), ("fallback", _NAT)),
        _let_else_block(
            _pat_ctor("Some", _pat_labeled("Value", _pat_bind("current"))),
            _variable("item"),
            _variable("fallback"),
            _if_expr(
                _is_expr(_variable("item"), _pat_ctor("Some", _pat_bind("inner"))),
                _binary("+", _variable("current"), _variable("inner")),
                _variable("fallback"),
            ),
        ),
        block=True,
    )
    fixture.constant(
        "StaticSplit",
        _NAT,
        _call("MeasureStatus", _call("Split", _natural(3), _natural(4), labels=("Left", "Right"))),
    )
    fixture.theorem(
        "UnwrapSome",
        (("value", _NAT), ("fallback", _NAT)),
        _binary("==", _call("UnwrapOr", _call("Some", _variable("value"), labels=("Value",)), _variable("fallback")), _variable("value")),
        _assert(_binary("==", _call("UnwrapOr", _call("Some", _variable("value"), labels=("Value",)), _variable("fallback")), _variable("value"))),
    )
    fixture.theorem(
        "SplitProof",
        (),
        _binary("==", _variable("StaticSplit"), _natural(7)),
        _assert(_binary("==", _variable("StaticSplit"), _natural(7))),
    )
    fixture.theorem(
        "SingleProof",
        (("n", _NAT),),
        _binary("==", _call("UnwrapSingle", _call("Only", _variable("n"))), _variable("n")),
        _assert(_binary("==", _call("UnwrapSingle", _call("Only", _variable("n"))), _variable("n"))),
    )
    fixture.theorem(
        "OptionRoundTrip",
        (("item", _type("Option", _NAT)),),
        _binary(
            "==",
            _match_expr(
                _variable("item"),
                (
                    (_pat_ctor("None"), _variable("None", _NAT)),
                    (_pat_ctor("Some", _pat_bind("v")), _call("Some", _variable("v"), generics=(_NAT,))),
                ),
            ),
            _variable("item"),
        ),
        _match_stmt(
            _variable("item"),
            (
                (
                    _pat_ctor("None"),
                    _assert(
                        _binary(
                            "==",
                            _match_expr(
                                _variable("None", _NAT),
                                (
                                    (_pat_ctor("None"), _variable("None", _NAT)),
                                    (_pat_ctor("Some", _pat_bind("v")), _call("Some", _variable("v"), generics=(_NAT,))),
                                ),
                            ),
                            _variable("None", _NAT),
                        )
                    ),
                ),
                (
                    _pat_ctor("Some", _pat_bind("v")),
                    _assert(
                        _binary(
                            "==",
                            _match_expr(
                                _call("Some", _variable("v"), generics=(_NAT,)),
                                (
                                    (_pat_ctor("None"), _variable("None", _NAT)),
                                    (_pat_ctor("Some", _pat_bind("inner")), _call("Some", _variable("inner"), generics=(_NAT,))),
                                ),
                            ),
                            _call("Some", _variable("v"), generics=(_NAT,)),
                        )
                    ),
                ),
            ),
            assert_arms=True,
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("@Corelib.Init.Datatypes.sum" in emitted and "@Corelib.Init.Datatypes.inl" in emitted
           and "@Corelib.Init.Datatypes.inr" in emitted,
           "elaborated Gallina omitted sum type or injection constructors for union")

    for name, body, kind, fragment in (
        ("NonExhaustiveUnion", _match_expr(_variable("item"), ((_pat_ctor("None"), _natural(0)),)), "type", "non-exhaustive"),
        ("NullaryUnionCtorCall", _match_expr(_call("None", generics=(_NAT,)), ((_pat_ctor("None"), _natural(0)), (_pat_ctor("Some", _pat_bind("v")), _variable("v")))), "type", "written bare"),
        ("UppercaseUnknownCtorPattern", _match_expr(_variable("item"), ((_pat_ctor("UnknownUpper"), _natural(0)),)), "name", "unknown constructor"),
        ("RefutableUnionLet", _let_pattern(_pat_ctor("Some", _pat_bind("v")), _variable("item"), _variable("v")), "type", "irrefutable"),
        ("WrongUnionArity", _match_expr(
            _variable("item"),
            ((_pat_ctor("None"), _natural(0)),
             (_pat_ctor("Some", _pat_bind("a"), _pat_bind("b")), _variable("a"))),
        ), "type", "expects 1"),
        ("UnknownUnionLabel", _match_expr(
            _variable("item"),
            ((_pat_ctor("None"), _natural(0)),
             (_pat_ctor("Some", _pat_labeled("Missing", _pat_bind("a"))), _variable("a"))),
        ), "name", "expected pattern field label"),
        ("UnionWithUpdate", _with_expr(_variable("item"), (("Value", _natural(1)),)), "type", "record"),
    ):
        wrong = _Fixture("UnionRefusals")
        wrong.union("Option", (("None", ()), ("Some", (("Value", _T),))), generics=_POLY)
        wrong.definition(name, _NAT, (("item", _type("Option", _NAT)),), body)
        _refuses(wrong, kind, fragment)

    dup_ctor = _Fixture("DupCtor")
    dup_ctor.union("Bad", (("Case", ()), ("Case", (("Value", _NAT),))))
    _refuses(dup_ctor, "name", "duplicate")


def _propagate(value: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        val_node = value(fixture)
        fixture.write("?")
        return fixture.node("propagate", start, value=val_node)
    return form


def _exists(parameters: tuple[Parameter, ...], body: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("exists ")
        param_nodes = fixture.parameters(parameters)
        fixture.write(" => ")
        val_node = body(fixture)
        return fixture.node("quantifier", start, quantifier="exists", parameters=param_nodes, value=val_node)
    return form


def _structural_recursion_and_decreases() -> None:
    fixture = _Fixture("Recursion")
    fixture.definition(
        "AddRec",
        _NAT,
        (("left", _NAT), ("right", _NAT)),
        _match_expr(
            _variable("left"),
            (
                (_pat_nat(0), _variable("right")),
                (_pat_ctor("Succ", _pat_bind("k")), _call("Succ", _call("AddRec", _variable("k"), _variable("right")))),
            ),
        ),
        contracts=(_contract("decreases", _variable("left")),),
    )
    fixture.definition(
        "DoubleRec",
        _NAT,
        (("n", _NAT),),
        _match_expr(
            _variable("n"),
            (
                (_pat_nat(0), _natural(0)),
                (_pat_ctor("Succ", _pat_bind("k")), _call("Succ", _call("Succ", _call("DoubleRec", _variable("k"))))),
            ),
        ),
    )
    fixture.theorem(
        "AddRecCheck",
        (),
        _binary("==", _call("AddRec", _natural(2), _natural(3)), _natural(5)),
        _assert(_binary("==", _call("AddRec", _natural(2), _natural(3)), _natural(5))),
    )
    fixture.theorem(
        "DoubleRecCheck",
        (),
        _binary("==", _call("DoubleRec", _natural(3)), _natural(6)),
        _assert(_binary("==", _call("DoubleRec", _natural(3)), _natural(6))),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("(fix vela_v" in emitted and "{struct vela_v" in emitted,
           "elaborated Gallina omitted structural fixpoint for recursive definition")

    non_dec = _Fixture("NonDecreasing")
    non_dec.definition("Bad", _NAT, (("n", _NAT),), _call("Bad", _variable("n")))
    _refuses(non_dec, "type", "structurally smaller")

    wrong_dec = _Fixture("WrongDecreases")
    wrong_dec.definition(
        "Bad",
        _NAT,
        (("a", _NAT), ("b", _NAT)),
        _match_expr(
            _variable("b"),
            (
                (_pat_nat(0), _natural(0)),
                (_pat_ctor("Succ", _pat_bind("k")), _call("Bad", _variable("a"), _variable("k"))),
            ),
        ),
        contracts=(_contract("decreases", _variable("a")),),
    )
    _refuses(wrong_dec, "type", "structurally smaller")

    non_nat_dec = _Fixture("NonNatDecreases")
    non_nat_dec.definition(
        "Bad",
        _NAT,
        (("flag", _BOOL),),
        _natural(0),
        contracts=(_contract("decreases", _variable("flag")),),
    )
    _refuses(non_nat_dec, "type", "must have type Nat")

    unk_dec = _Fixture("UnknownDecreases")
    unk_dec.definition(
        "Bad",
        _NAT,
        (("n", _NAT),),
        _natural(0),
        contracts=(_contract("decreases", _variable("missing")),),
    )
    _refuses(unk_dec, "name", "unknown parameter")

    unapplied = _Fixture("UnappliedSelf")
    unapplied.definition("Use", _NAT, (("f", _function_type(((None, _NAT),), _NAT)),), _call("f", _natural(0)))
    unapplied.definition(
        "Bad",
        _NAT,
        (("n", _NAT),),
        _match_expr(
            _variable("n"),
            (
                (_pat_nat(0), _natural(0)),
                (_pat_ctor("Succ", _pat_bind("k")), _call("Use", _variable("Bad"))),
            ),
        ),
    )
    _refuses(unapplied, "type", "direct call")


def _inductive_proofs_and_equational_rewriting() -> None:
    fixture = _Fixture("InductiveProofs")
    fixture.theorem(
        "AddZeroRight",
        (("n", _NAT),),
        _binary("==", _binary("+", _variable("n"), _natural(0)), _variable("n")),
        _match_stmt(
            _variable("n"),
            (
                (_pat_nat(0), _assert(_binary("==", _binary("+", _natural(0), _natural(0)), _natural(0)))),
                (
                    _pat_ctor("Succ", _pat_bind("k")),
                    _assert(
                        _binary("==", _binary("+", _call("Succ", _variable("k")), _natural(0)), _call("Succ", _variable("k"))),
                        by=_call("AddZeroRight", _variable("k")),
                    ),
                ),
            ),
            assert_arms=True,
        ),
    )
    fixture.theorem(
        "AddSuccRight",
        (("a", _NAT), ("b", _NAT)),
        _binary("==", _binary("+", _variable("a"), _call("Succ", _variable("b"))), _call("Succ", _binary("+", _variable("a"), _variable("b")))),
        _match_stmt(
            _variable("a"),
            (
                (
                    _pat_nat(0),
                    _assert(
                        _binary(
                            "==",
                            _binary("+", _natural(0), _call("Succ", _variable("b"))),
                            _call("Succ", _binary("+", _natural(0), _variable("b"))),
                        )
                    ),
                ),
                (
                    _pat_ctor("Succ", _pat_bind("k")),
                    _assert(
                        _binary(
                            "==",
                            _binary("+", _call("Succ", _variable("k")), _call("Succ", _variable("b"))),
                            _call("Succ", _binary("+", _call("Succ", _variable("k")), _variable("b"))),
                        ),
                        by=_call("AddSuccRight", _variable("k"), _variable("b")),
                    ),
                ),
            ),
            assert_arms=True,
        ),
    )
    fixture.theorem(
        "AddComm",
        (("a", _NAT), ("b", _NAT)),
        _binary("==", _binary("+", _variable("a"), _variable("b")), _binary("+", _variable("b"), _variable("a"))),
        _match_stmt(
            _variable("a"),
            (
                (
                    _pat_nat(0),
                    _assert(
                        _binary("==", _binary("+", _natural(0), _variable("b")), _binary("+", _variable("b"), _natural(0))),
                        by=_call("AddZeroRight", _variable("b")),
                    ),
                ),
                (
                    _pat_ctor("Succ", _pat_bind("k")),
                    _assert(
                        _binary(
                            "==",
                            _binary("+", _call("Succ", _variable("k")), _variable("b")),
                            _binary("+", _variable("b"), _call("Succ", _variable("k"))),
                        ),
                        by_block=(
                            _assert(
                                _binary(
                                    "==",
                                    _call("Succ", _binary("+", _variable("k"), _variable("b"))),
                                    _call("Succ", _binary("+", _variable("b"), _variable("k"))),
                                ),
                                by=_call("AddComm", _variable("k"), _variable("b")),
                            ),
                            _assert(
                                _binary(
                                    "==",
                                    _binary("+", _variable("b"), _call("Succ", _variable("k"))),
                                    _call("Succ", _binary("+", _variable("b"), _variable("k"))),
                                ),
                                by=_call("AddSuccRight", _variable("b"), _variable("k")),
                            ),
                        ),
                    ),
                ),
            ),
            assert_arms=True,
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Definition vela_d0_AddZeroRight" in emitted and "Definition vela_d2_AddComm" in emitted
           and "@vela_Congr" in emitted and "@Corelib.Init.Logic.eq_sym" in emitted,
           "elaborated inductive proofs omitted congruence or symmetry combinators")

    circular = _Fixture("CircularProof")
    circular.theorem(
        "Bad",
        (("n", _NAT),),
        _binary("==", _variable("n"), _natural(0)),
        _assert(_binary("==", _variable("n"), _natural(0)), by=_call("Bad", _variable("n"))),
    )
    _refuses(circular, "type", "structurally smaller")


def _dependent_records_and_existential_propositions() -> None:
    fixture = _Fixture("DependentRecordsAndExistentials")
    fixture.record(
        "BoundedIndex",
        (("Limit", _NAT), ("Index", _type("Fin", _variable("Limit")))),
        properties=(("Capacity", _NAT, _member(_variable("this"), "Limit")),),
    )
    fixture.union(
        "PackedVec",
        (
            ("Empty", ()),
            ("NonEmpty", (("Length", _NAT), ("Items", _type("Vec", _T, _variable("Length"))))),
        ),
        generics=_POLY,
    )
    fixture.definition(
        "ZeroBounded",
        _type("BoundedIndex"),
        (),
        _call("BoundedIndex", _natural(1), _call("FZero", generics=(_natural(0),)), labels=("Limit", "Index")),
    )
    fixture.definition(
        "ReadBounded",
        _NAT,
        (("b", _type("BoundedIndex")), ("values", _type("Vec", _NAT, _member(_variable("b"), "Limit")))),
        _call("At", _variable("values"), _member(_variable("b"), "Index")),
    )
    fixture.definition(
        "RebindBounded",
        _type("BoundedIndex"),
        (("b", _type("BoundedIndex")),),
        _with_expr(_variable("b"), (("Limit", _natural(1)), ("Index", _call("FZero", generics=(_natural(0),))))),
    )
    fixture.definition(
        "PackedLength",
        _NAT,
        (("packed", _type("PackedVec", _NAT)),),
        _match_expr(
            _variable("packed"),
            (
                (_pat_ctor("Empty"), _natural(0)),
                (_pat_ctor("NonEmpty", _pat_labeled("Length", _pat_bind("n")), _pat_labeled("Items", _pat_wild())), _variable("n")),
            ),
        ),
    )
    fixture.theorem(
        "ZeroBoundedCapacity",
        (),
        _binary("==", _member(_call("ZeroBounded"), "Capacity"), _natural(1)),
        _assert(_binary("==", _member(_call("ZeroBounded"), "Capacity"), _natural(1))),
    )
    fixture.theorem(
        "PackedNonEmptyLength",
        (),
        _binary(
            "==",
            _call("PackedLength", _call("NonEmpty", _natural(1), _call("VCons", _natural(9), _call("VNil", generics=(_NAT,))))),
            _natural(1),
        ),
        _assert(
            _binary(
                "==",
                _call("PackedLength", _call("NonEmpty", _natural(1), _call("VCons", _natural(9), _call("VNil", generics=(_NAT,))))),
                _natural(1),
            )
        ),
    )
    fixture.theorem(
        "ExistsEqual",
        (("n", _NAT),),
        _exists((("m", _NAT),), _binary("==", _variable("m"), _variable("n"))),
        _assert(_exists((("m", _NAT),), _binary("==", _variable("m"), _variable("n"))), by=_variable("n")),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("@Corelib.Init.Specif.sigT" in emitted and "@Corelib.Init.Specif.existT" in emitted
           and "@Corelib.Init.Specif.projT1" in emitted and "@Corelib.Init.Specif.projT2" in emitted
           and "@Corelib.Init.Logic.ex" in emitted and "@Corelib.Init.Logic.ex_intro" in emitted,
           "elaborated Gallina omitted sigT/existT/projT or ex/ex_intro combinators")

    partial_upd = _Fixture("PartialDependentUpdate")
    partial_upd.record("BoundedIndex", (("Limit", _NAT), ("Index", _type("Fin", _variable("Limit")))))
    partial_upd.definition(
        "Wrong",
        _type("BoundedIndex"),
        (("b", _type("BoundedIndex")),),
        _with_expr(_variable("b"), (("Limit", _natural(2)),)),
    )
    _refuses(partial_upd, "type", "depends on")

    bad_ex = _Fixture("BadExistentialWitness")
    bad_ex.theorem(
        "Wrong",
        (),
        _exists((("m", _NAT),), _binary("==", _variable("m"), _natural(1))),
        _assert(_exists((("m", _NAT),), _binary("==", _variable("m"), _natural(1))), by=_natural(0)),
    )
    _refuses(bad_ex, "type")


def _early_return_propagation() -> None:
    fixture = _Fixture("Propagation")
    fixture.union("Option", (("None", ()), ("Some", (("Value", _T),))), generics=_POLY)
    fixture.union(
        "Result",
        (("Err", (("Error", _type("E")),)), ("Ok", (("Value", _T),))),
        generics=(*_POLY, ("type", "E", None)),
    )
    fixture.definition(
        "AddOptions",
        _type("Option", _NAT),
        (("left", _type("Option", _NAT)), ("right", _type("Option", _NAT))),
        _call("Some", _binary("+", _propagate(_variable("left")), _propagate(_variable("right")))),
    )
    fixture.function(
        "AddResults",
        _type("Result", _NAT, _BOOL),
        (("left", _type("Result", _NAT, _BOOL)), ("right", _type("Result", _NAT, _BOOL))),
        _call("Ok", _binary("+", _propagate(_variable("left")), _propagate(_variable("right")))),
        arrow=False,
    )
    fixture.theorem(
        "AddOptionsSome",
        (),
        _binary(
            "==",
            _call("AddOptions", _call("Some", _natural(3)), _call("Some", _natural(4))),
            _call("Some", _natural(7)),
        ),
        _assert(
            _binary(
                "==",
                _call("AddOptions", _call("Some", _natural(3)), _call("Some", _natural(4))),
                _call("Some", _natural(7)),
            )
        ),
    )
    fixture.theorem(
        "AddOptionsNone",
        (),
        _binary(
            "==",
            _call("AddOptions", _variable("None", _NAT), _call("Some", _natural(4))),
            _variable("None", _NAT),
        ),
        _assert(
            _binary(
                "==",
                _call("AddOptions", _variable("None", _NAT), _call("Some", _natural(4))),
                _variable("None", _NAT),
            )
        ),
    )
    fixture.theorem(
        "AddResultsErr",
        (),
        _binary(
            "==",
            _call("AddResults", _call("Err", _boolean(True), generics=(_NAT, _BOOL)), _call("Ok", _natural(4), generics=(_NAT, _BOOL))),
            _call("Err", _boolean(True), generics=(_NAT, _BOOL)),
        ),
        _assert(
            _binary(
                "==",
                _call("AddResults", _call("Err", _boolean(True), generics=(_NAT, _BOOL)), _call("Ok", _natural(4), generics=(_NAT, _BOOL))),
                _call("Err", _boolean(True), generics=(_NAT, _BOOL)),
            )
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Definition vela_d6_AddOptions" in emitted and "Definition vela_d7_AddResults" in emitted,
           "elaborated Gallina omitted propagated callable definitions")

    bad_op = _Fixture("PropagateNonUnion")
    bad_op.union("Option", (("None", ()), ("Some", (("Value", _T),))), generics=_POLY)
    bad_op.definition("Wrong", _type("Option", _NAT), (("n", _NAT),), _call("Some", _propagate(_variable("n"))))
    _refuses(bad_op, "type", "Option")

    bad_ret = _Fixture("PropagateIncompatibleReturn")
    bad_ret.union("Option", (("None", ()), ("Some", (("Value", _T),))), generics=_POLY)
    bad_ret.definition("Wrong", _NAT, (("x", _type("Option", _NAT)),), _propagate(_variable("x")))
    _refuses(bad_ret, "type", "enclosing callable")


def _int_lit(value: str, suffix: str = "") -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(value + suffix)
        return fixture.node("nat", start, value=value, suffix=suffix)
    return form


def _unary_op(operator: str, inner: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        op_node = fixture.name(operator)
        val_node = inner(fixture)
        return fixture.node("unary", start, operator=op_node, value=val_node)
    return form


def _import_decl(fixture: _Fixture, module_name: str) -> None:
    fixture.write("\n")
    start = fixture.offset
    fixture.write("import ")
    name_node = fixture.name(module_name)
    fixture.write(";")
    fixture.declarations.append(
        fixture.node("import", start, name=name_node)
    )


def _represented_integers_and_conversions() -> None:
    fixture = _Fixture("Numerics")
    _import_decl(fixture, "Vela.Numerics")

    # Constants and literal forms (decimal, hex, binary, _ separators, contextual, negative min)
    fixture.constant("ByteMax", _type("byte"), _member(_variable("byte"), "Max"))
    fixture.constant("U8Bits", _NAT, _member(_variable("u8"), "Bits"))
    fixture.constant("I32Min", _type("int"), _member(_variable("i32"), "Min"))
    fixture.constant("I32MinLit", _type("i32"), _unary_op("-", _int_lit("2147483648", "i32")))
    fixture.constant("I8MinContextual", _type("i8"), _unary_op("-", _int_lit("128")))
    fixture.constant("HexMask", _type("u16"), _int_lit("0xFF_00", "u16"))
    fixture.constant("BinFlags", _type("u8"), _int_lit("0b1010_0101", "u8"))
    fixture.constant("QualifiedIntMax", _type("Vela.Numerics.int"), _member(_member(_variable("Vela"), "Numerics"), "int.Max") if False else _member(_member(_member(_variable("Vela"), "Numerics"), "int"), "Max"))

    # Precondition-checked arithmetic and bitwise operations
    fixture.definition(
        "AddBounded",
        _type("u32"),
        (("a", _type("u32")), ("b", _type("u32"))),
        _binary("+", _variable("a"), _variable("b")),
        contracts=(
            _contract("requires", _binary("<=", _variable("a"), _int_lit("1000", "u32"))),
            _contract("requires", _binary("<=", _variable("b"), _int_lit("2000", "u32"))),
        ),
    )
    fixture.definition(
        "CallAddBounded",
        _type("u32"),
        (("x", _type("u32")),),
        _call("AddBounded", _variable("x"), _int_lit("500", "u32")),
        contracts=(_contract("requires", _binary("<=", _variable("x"), _int_lit("400", "u32"))),),
    )
    fixture.definition(
        "SafeSignedDiv",
        _type("i32"),
        (("a", _type("i32")), ("d", _type("i32"))),
        _binary("/", _variable("a"), _variable("d")),
        contracts=(
            _contract("requires", _binary(">", _variable("a"), _member(_variable("i32"), "Min"))),
            _contract("requires", _binary(">", _variable("d"), _int_lit("0", "i32"))),
        ),
    )
    fixture.definition(
        "BranchCheckedInc",
        _type("u8"),
        (("x", _type("u8")),),
        _if_expr(
            _binary("<", _variable("x"), _int_lit("255", "u8")),
            _binary("+", _variable("x"), _int_lit("1", "u8")),
            _variable("x"),
        ),
    )
    fixture.definition(
        "MaskedAddAndShift",
        _type("u8"),
        (("x", _type("u8")), ("s", _type("usize"))),
        _call(
            _member(
                _binary("+", _binary("&", _variable("x"), _int_lit("0x0F", "u8")), _int_lit("1", "u8")),
                "ShiftLeft",
            ),
            _binary("&", _variable("s"), _int_lit("3", "usize")),
        ),
    )
    fixture.definition(
        "WidenedBytePlusOne",
        _type("u16"),
        (("b", _type("byte")),),
        _binary("+", _call(_member(_variable("u16"), "From"), _variable("b")), _int_lit("1", "u16")),
    )

    # Total Wrapping*, Saturating*, Checked* operations and ? propagation
    fixture.function(
        "CheckedLinear",
        _type("Result", _type("u8"), _type("ArithmeticError")),
        (("x", _type("u8")), ("scale", _type("u8")), ("offset", _type("u8"))),
        _call(
            "Ok",
            _propagate(
                _call(
                    _member(
                        _propagate(_call(_member(_variable("x"), "CheckedMul"), _variable("scale"))),
                        "CheckedAdd",
                    ),
                    _variable("offset"),
                )
            ),
            generics=(_type("u8"), _type("ArithmeticError")),
        ),
        arrow=False,
    )

    # Theorems verifying reduction of concrete operations, conversions, and error variants
    fixture.theorem(
        "MinLiteralAgreement",
        (),
        _binary("==", _variable("I32Min"), _variable("I32MinLit")),
        _assert(_binary("==", _variable("I32Min"), _variable("I32MinLit"))),
    )
    fixture.theorem(
        "WrappingAddCheck",
        (),
        _binary(
            "==",
            _call(_member(_int_lit("255", "u8"), "WrappingAdd"), _int_lit("1", "u8")),
            _int_lit("0", "u8"),
        ),
        _assert(
            _binary(
                "==",
                _call(_member(_int_lit("255", "u8"), "WrappingAdd"), _int_lit("1", "u8")),
                _int_lit("0", "u8"),
            )
        ),
    )
    fixture.theorem(
        "SaturatingAddCheck",
        (),
        _binary(
            "==",
            _call(_member(_int_lit("250", "u8"), "SaturatingAdd"), _int_lit("10", "u8")),
            _int_lit("255", "u8"),
        ),
        _assert(
            _binary(
                "==",
                _call(_member(_int_lit("250", "u8"), "SaturatingAdd"), _int_lit("10", "u8")),
                _int_lit("255", "u8"),
            )
        ),
    )
    fixture.theorem(
        "SaturatingNegCheck",
        (),
        _binary(
            "==",
            _call(_member(_variable("I8MinContextual"), "SaturatingNeg")),
            _int_lit("127", "i8"),
        ),
        _assert(
            _binary(
                "==",
                _call(_member(_variable("I8MinContextual"), "SaturatingNeg")),
                _int_lit("127", "i8"),
            )
        ),
    )
    fixture.theorem(
        "CheckedLinearOkCheck",
        (),
        _binary(
            "==",
            _call("CheckedLinear", _int_lit("10", "u8"), _int_lit("20", "u8"), _int_lit("5", "u8")),
            _call("Ok", _int_lit("205", "u8"), generics=(_type("u8"), _type("ArithmeticError"))),
        ),
        _assert(
            _binary(
                "==",
                _call("CheckedLinear", _int_lit("10", "u8"), _int_lit("20", "u8"), _int_lit("5", "u8")),
                _call("Ok", _int_lit("205", "u8"), generics=(_type("u8"), _type("ArithmeticError"))),
            )
        ),
    )
    fixture.theorem(
        "CheckedLinearOverflowCheck",
        (),
        _binary(
            "==",
            _call("CheckedLinear", _int_lit("20", "u8"), _int_lit("20", "u8"), _int_lit("5", "u8")),
            _call("Err", _variable("Overflow"), generics=(_type("u8"), _type("ArithmeticError"))),
        ),
        _assert(
            _binary(
                "==",
                _call("CheckedLinear", _int_lit("20", "u8"), _int_lit("20", "u8"), _int_lit("5", "u8")),
                _call("Err", _variable("Overflow"), generics=(_type("u8"), _type("ArithmeticError"))),
            )
        ),
    )
    fixture.theorem(
        "CheckedDivZeroCheck",
        (),
        _binary(
            "==",
            _call(_member(_int_lit("10", "u8"), "CheckedDiv"), _int_lit("0", "u8")),
            _call("Err", _variable("ZeroDivisor"), generics=(_type("u8"), _type("ArithmeticError"))),
        ),
        _assert(
            _binary(
                "==",
                _call(_member(_int_lit("10", "u8"), "CheckedDiv"), _int_lit("0", "u8")),
                _call("Err", _variable("ZeroDivisor"), generics=(_type("u8"), _type("ArithmeticError"))),
            )
        ),
    )
    fixture.theorem(
        "NatConversionCheck",
        (),
        _binary("==", _call("Nat", _int_lit("42", "u8")), _natural(42)),
        _assert(_binary("==", _call("Nat", _int_lit("42", "u8")), _natural(42))),
    )
    fixture.theorem(
        "FromConversionCheck",
        (),
        _binary(
            "==",
            _call(_member(_variable("i32"), "From"), _int_lit("200", "u8")),
            _int_lit("200", "i32"),
        ),
        _assert(
            _binary(
                "==",
                _call(_member(_variable("i32"), "From"), _int_lit("200", "u8")),
                _int_lit("200", "i32"),
            )
        ),
    )
    fixture.theorem(
        "TryFromOkCheck",
        (),
        _binary(
            "==",
            _call(_member(_variable("u8"), "TryFrom"), _int_lit("200", "u16")),
            _call("Ok", _int_lit("200", "u8"), generics=(_type("u8"), _type("ConversionError"))),
        ),
        _assert(
            _binary(
                "==",
                _call(_member(_variable("u8"), "TryFrom"), _int_lit("200", "u16")),
                _call("Ok", _int_lit("200", "u8"), generics=(_type("u8"), _type("ConversionError"))),
            )
        ),
    )
    fixture.theorem(
        "TryFromErrCheck",
        (),
        _binary(
            "==",
            _call(_member(_variable("u8"), "TryFrom"), _int_lit("300", "u16")),
            _call("Err", _variable("OutOfRange"), generics=(_type("u8"), _type("ConversionError"))),
        ),
        _assert(
            _binary(
                "==",
                _call(_member(_variable("u8"), "TryFrom"), _int_lit("300", "u16")),
                _call("Err", _variable("OutOfRange"), generics=(_type("u8"), _type("ConversionError"))),
            )
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Inductive vela_int" in emitted and "vela_int_chk_mul" in emitted,
           "elaborated Gallina omitted fixed-width integer definitions")

    # Negative tests: out-of-range literals, unproved preconditions, and invalid conversions
    for name, param_types, ret_type, body, kind, fragment in (
        ("LiteralOutOfRange", (), _type("u8"), _int_lit("256", "u8"), "type", "out of range"),
        ("ContextualOutOfRange", (), _type("u8"), _int_lit("256"), "type", "out of range"),
        ("NegativeUnsigned", (), _type("u8"), _unary_op("-", _int_lit("1", "u8")), "type", "unsigned"),
        ("SignedNegMinOverflow", (), _type("i8"), _unary_op("-", _member(_variable("i8"), "Min")), "type", "overflow"),
        ("ConcreteAddOverflow", (), _type("u8"), _binary("+", _int_lit("255", "u8"), _int_lit("1", "u8")), "type", "overflow"),
        ("ConcreteSubUnderflow", (), _type("u8"), _binary("-", _int_lit("0", "u8"), _int_lit("1", "u8")), "type", "overflow"),
        ("ConcreteDivZero", (), _type("u8"), _binary("/", _int_lit("10", "u8"), _int_lit("0", "u8")), "type", "nonzero divisor"),
        ("ConcreteSignedDivOverflow", (), _type("i8"), _binary("/", _member(_variable("i8"), "Min"), _unary_op("-", _int_lit("1", "i8"))), "type", "overflow"),
        ("ConcreteShiftOutOfRange", (), _type("u8"), _call(_member(_int_lit("1", "u8"), "ShiftLeft"), _int_lit("8", "usize")), "type", "shift count"),
        ("ConcreteWrappingShiftOutOfRange", (), _type("u8"), _call(_member(_int_lit("1", "u8"), "WrappingShiftLeft"), _int_lit("8", "usize")), "type", "shift count"),
        ("UnprovedSymbolicAdd", (("a", _type("u8")), ("b", _type("u8"))), _type("u8"), _binary("+", _variable("a"), _variable("b")), "type", "overflow"),
        ("UnprovedSymbolicDiv", (("a", _type("u8")), ("d", _type("u8"))), _type("u8"), _binary("/", _variable("a"), _variable("d")), "type", "nonzero divisor"),
        ("SignedToNat", (("x", _type("i32")),), _NAT, _call("Nat", _variable("x")), "type", "unsigned"),
        ("NarrowingFrom", (("x", _type("u16")),), _type("u8"), _call(_member(_variable("u8"), "From"), _variable("x")), "type", "TryFrom"),
        ("SignChangingFrom", (("x", _type("i32")),), _type("u32"), _call(_member(_variable("u32"), "From"), _variable("x")), "type", "TryFrom"),
        ("UsizeToU32From", (("x", _type("usize")),), _type("u32"), _call(_member(_variable("u32"), "From"), _variable("x")), "type", "TryFrom"),
        ("BitwiseOnNat", (("a", _NAT), ("b", _NAT)), _NAT, _binary("&", _variable("a"), _variable("b")), "type", "fixed-width integer"),
    ):
        wrong = _Fixture(f"NumericsRefusal_{name}")
        wrong.definition(name, ret_type, param_types, body)
        _refuses(wrong, kind, fragment)

    no_import = _Fixture("UnimportedAlias")
    no_import.definition("UseInt", _type("int"), (("x", _type("int")),), _variable("x"))
    _refuses(no_import, "name", "int")


def _invariant_contract(value: Form, clause_name: str | None = None) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("invariant ")
        name_node = None
        if clause_name is not None:
            name_node = fixture.name(clause_name)
            fixture.write(": ")
        val_node = value(fixture)
        if name_node is not None:
            return fixture.node("contract", start, role="invariant", name=name_node, value=val_node)
        return fixture.node("contract", start, role="invariant", value=val_node)
    return form


def _block_stmts(*statements: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("{ ")
        stmt_nodes: list[Node] = []
        for index, stmt in enumerate(statements):
            if index:
                fixture.write(" ")
            stmt_nodes.append(stmt(fixture))
        fixture.write(" }")
        return fixture.node("block", start, statements=stmt_nodes)
    return form


def _return_stmt(value: Form | None = None) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("return")
        val_node = None
        if value is not None:
            fixture.write(" ")
            val_node = value(fixture)
        fixture.write(";")
        return fixture.node("return", start, value=val_node)
    return form


def _let_stmt(name: str, value: Form, value_type: Form | None = None) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("let ")
        type_node = None
        if value_type is not None:
            type_node = value_type(fixture)
            fixture.write(" ")
        binding = fixture.name(name)
        fixture.write(" = ")
        val_node = value(fixture)
        fixture.write(";")
        return fixture.node("let", start, name=binding, type=type_node, grade=None, value=val_node)
    return form


def _var_stmt(name: str, value: Form, value_type: Form | None = None) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("var ")
        type_node = None
        if value_type is not None:
            type_node = value_type(fixture)
            fixture.write(" ")
        binding = fixture.name(name)
        fixture.write(" = ")
        val_node = value(fixture)
        fixture.write(";")
        return fixture.node("var", start, name=binding, type=type_node, grade=None, value=val_node)
    return form


def _assign_stmt(target: Form, operator: str, value: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        tgt_node = target(fixture)
        fixture.write(" ")
        op_node = fixture.name(operator)
        fixture.write(" ")
        val_node = value(fixture)
        fixture.write(";")
        return fixture.node("assignment", start, target=tgt_node, operator=op_node, value=val_node)
    return form


def _expr_stmt(value: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        val_node = value(fixture)
        fixture.write(";")
        return fixture.node("expression_statement", start, value=val_node)
    return form


def _if_stmt(condition: Form, then_blk: Form, else_blk: Form | None = None) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("if (")
        cond_node = condition(fixture)
        fixture.write(") ")
        then_node = then_blk(fixture)
        else_node = None
        if else_blk is not None:
            fixture.write(" else ")
            else_node = else_blk(fixture)
        return fixture.node("if", start, condition=cond_node, **{"then": then_node, "else": else_node})
    return form


def _break_stmt() -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("break;")
        return fixture.node("break", start)
    return form


def _continue_stmt() -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("continue;")
        return fixture.node("continue", start)
    return form


def _foreach_range(var_name: str, start_expr: Form, end_expr: Form,
                   body_stmts: tuple[Form, ...], contracts: tuple[Form, ...] = ()) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("foreach (let ")
        name_node = fixture.name(var_name)
        fixture.write(" in ")
        rstart = fixture.offset
        s_node = start_expr(fixture)
        fixture.write("..")
        e_node = end_expr(fixture)
        range_node: Node = {"kind": "range", "span": [rstart, fixture.offset], "start": s_node, "end": e_node}
        fixture.write(")")
        contract_nodes: list[Node] = []
        for contract in contracts:
            fixture.write(" ")
            contract_nodes.append(contract(fixture))
        fixture.write(" ")
        body_node = _block_stmts(*body_stmts)(fixture)
        return fixture.node("foreach", start, name=name_node, range=range_node,
                            contracts=contract_nodes, body=body_node)
    return form


def _foreach_coll(mode: str, var_name: str, collection: Form, body_stmts: tuple[Form, ...],
                  *, item_type: Form | None = None, contracts: tuple[Form, ...] = ()) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("foreach (")
        fixture.write("let " if mode == "value" else f"{mode} ")
        type_node = None
        if item_type is not None:
            type_node = item_type(fixture)
            fixture.write(" ")
        name_node = fixture.name(var_name)
        fixture.write(" in ")
        coll_node = collection(fixture)
        fixture.write(")")
        contract_nodes: list[Node] = []
        for contract in contracts:
            fixture.write(" ")
            contract_nodes.append(contract(fixture))
        fixture.write(" ")
        body_node = _block_stmts(*body_stmts)(fixture)
        return fixture.node("foreach_collection", start, mode=mode, type=type_node,
                            name=name_node, collection=coll_node,
                            contracts=contract_nodes, body=body_node)
    return form


def _open_lifts(resources: tuple[Form, ...], lifts: tuple[str, ...],
                body_stmts: tuple[Form, ...]) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("open (")
        res_nodes = fixture.forms(resources)
        fixture.write(") lifts ")
        lift_nodes: list[Node] = []
        for index, lift_name in enumerate(lifts):
            if index:
                fixture.write(", ")
            lift_nodes.append(fixture.name(lift_name))
        fixture.write(" ")
        body_node = _block_stmts(*body_stmts)(fixture)
        return fixture.node("open_invariant", start, resources=res_nodes, lifts=lift_nodes, body=body_node)
    return form


def _task_scope(resources: tuple[Form, ...], body_stmts: tuple[Form, ...]) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("scope (")
        res_nodes = fixture.forms(resources)
        fixture.write(") ")
        body_node = _block_stmts(*body_stmts)(fixture)
        return fixture.node("scope", start, resources=res_nodes, body=body_node)
    return form


def _pure_sequences_and_model_reasoning() -> None:
    fixture = _Fixture("Sequences")
    fixture.definition(
        "BuildSeq",
        _type("Seq", _type("u32")),
        (),
        _call(
            _member(
                _call(
                    _member(_call(_member(_variable("Seq"), "Singleton"), _int_lit("10", "u32")), "Append"),
                    _call(
                        _member(_call(_member(_variable("Seq"), "Empty"), generics=(_type("u32"),)), "Append"),
                        _call(_member(_variable("Seq"), "Singleton"), _int_lit("20", "u32")),
                    ),
                ),
                "Update",
            ),
            _natural(1),
            _int_lit("30", "u32"),
        ),
    )
    fixture.theorem(
        "SeqOpsCheck",
        (),
        _binary(
            "==",
            _binary(
                "&&",
                _binary(
                    "&&",
                    _binary("==", _member(_call("BuildSeq"), "Count"), _natural(2)),
                    _binary("==", _call(_member(_call("BuildSeq"), "At"), _natural(1)), _int_lit("30", "u32")),
                ),
                _binary(
                    "&&",
                    _call(_member(_call("BuildSeq"), "Contains"), _int_lit("10", "u32")),
                    _binary(
                        "&&",
                        _call(
                            _member(_call("BuildSeq"), "All"),
                            _inferred_lambda(("x",), _binary(">=", _variable("x"), _int_lit("10", "u32")), bare=True),
                        ),
                        _call(
                            _member(_call("BuildSeq"), "Any"),
                            _inferred_lambda(("x",), _binary("==", _variable("x"), _int_lit("30", "u32")), bare=True),
                        ),
                    ),
                ),
            ),
            _boolean(True),
        ),
        _assert(
            _binary(
                "==",
                _binary(
                    "&&",
                    _binary(
                        "&&",
                        _binary("==", _member(_call("BuildSeq"), "Count"), _natural(2)),
                        _binary("==", _call(_member(_call("BuildSeq"), "At"), _natural(1)), _int_lit("30", "u32")),
                    ),
                    _binary(
                        "&&",
                        _call(_member(_call("BuildSeq"), "Contains"), _int_lit("10", "u32")),
                        _binary(
                            "&&",
                            _call(
                                _member(_call("BuildSeq"), "All"),
                                _inferred_lambda(("x",), _binary(">=", _variable("x"), _int_lit("10", "u32")), bare=True),
                            ),
                            _call(
                                _member(_call("BuildSeq"), "Any"),
                                _inferred_lambda(("x",), _binary("==", _variable("x"), _int_lit("30", "u32")), bare=True),
                            ),
                        ),
                    ),
                ),
                _boolean(True),
            )
        ),
    )
    fixture.theorem(
        "SeqSliceCheck",
        (),
        _binary(
            "==",
            _call(
                _member(
                    _call(_member(_call(_member(_call("BuildSeq"), "Take"), _natural(2)), "Skip"), _natural(1)),
                    "Slice",
                ),
                _natural(0),
                _natural(1),
            ),
            _call(_member(_variable("Seq"), "Singleton"), _int_lit("30", "u32")),
        ),
        _assert(
            _binary(
                "==",
                _call(
                    _member(
                        _call(_member(_call(_member(_call("BuildSeq"), "Take"), _natural(2)), "Skip"), _natural(1)),
                        "Slice",
                    ),
                    _natural(0),
                    _natural(1),
                ),
                _call(_member(_variable("Seq"), "Singleton"), _int_lit("30", "u32")),
            )
        ),
    )
    fixture.theorem(
        "VecModelCheck",
        (),
        _binary(
            "==",
            _member(_call("VCons", _int_lit("7", "u32"), _call("VNil", generics=(_type("u32"),))), "Model"),
            _call(_member(_variable("Seq"), "Singleton"), _int_lit("7", "u32")),
        ),
        _assert(
            _binary(
                "==",
                _member(_call("VCons", _int_lit("7", "u32"), _call("VNil", generics=(_type("u32"),))), "Model"),
                _call(_member(_variable("Seq"), "Singleton"), _int_lit("7", "u32")),
            )
        ),
    )
    fixture.function(
        "MutateSpanFirst",
        _type("Unit"),
        (("s", _modified("ref", _type("Span", _type("byte")))),),
        _block_stmts(
            _expr_stmt(_call(_member(_variable("Span"), "Write"), _ref_arg(_variable("s")), _int_lit("0", "usize"), _int_lit("99", "byte"))),
            _return_stmt(_unit()),
        ),
        block=True,
        contracts=(
            _contract("requires", _member(_variable("s"), "CanRead")),
            _contract("requires", _member(_variable("s"), "CanWrite")),
            _contract("requires", _binary(">", _member(_variable("s"), "Length"), _int_lit("0", "usize"))),
            _contract(
                "restores",
                _binary(
                    "==",
                    _member(_call("final", _variable("s")), "Model"),
                    _call(_member(_call("old", _member(_variable("s"), "Model")), "Update"), _natural(0), _int_lit("99", "byte")),
                ),
            ),
            _contract(
                "ensures",
                _binary(
                    "==",
                    _member(_variable("s"), "Model"),
                    _call(_member(_call("old", _member(_variable("s"), "Model")), "Update"), _natural(0), _int_lit("99", "byte")),
                ),
            ),
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Inductive vela_Seq" in emitted and "vela_Seq_Update" in emitted,
           "elaborated Gallina omitted Seq definitions")

    oob = _Fixture("SeqAtOutOfBounds")
    oob.definition(
        "BadAt",
        _type("u32"),
        (("s", _type("Seq", _type("u32"))),),
        _call(_member(_variable("s"), "At"), _natural(0)),
    )
    _refuses(oob, "type", "Seq.Count bounds")

    old_outside = _Fixture("OldOutsideCallable")
    old_outside.constant("BadOld", _NAT, _call("old", _natural(1)))
    _refuses(old_outside, "type", "old")

    final_outside = _Fixture("FinalOutsidePostState")
    final_outside.constant("BadFinal", _NAT, _call("final", _natural(1)))
    _refuses(final_outside, "type", "final")

    bad_pred = _Fixture("SeqAllNonPredicate")
    bad_pred.definition(
        "BadAll",
        _BOOL,
        (("s", _type("Seq", _type("u32"))),),
        _call(_member(_variable("s"), "All"), _natural(0)),
    )
    _refuses(bad_pred, "type", "not definitionally equal")


def _mutable_locals_assignments_and_bounded_loops() -> None:
    fixture = _Fixture("LoopsAndLocals")
    fixture.record("Tally", (("Count", _type("usize")), ("Total", _type("u32"))))
    fixture.function(
        "AccumulateRange",
        _type("usize"),
        (),
        _block_stmts(
            _var_stmt("t", _call("Tally", _int_lit("0", "usize"), _int_lit("0", "u32"))),
            _foreach_range(
                "i",
                _int_lit("0", "usize"),
                _int_lit("4", "usize"),
                (
                    _if_stmt(
                        _binary("==", _variable("i"), _int_lit("1", "usize")),
                        _block_stmts(_continue_stmt()),
                    ),
                    _assign_stmt(_member(_variable("t"), "Count"), "+=", _int_lit("1", "usize")),
                    _if_stmt(
                        _binary("==", _variable("i"), _int_lit("2", "usize")),
                        _block_stmts(_break_stmt()),
                    ),
                ),
            ),
            _return_stmt(_member(_variable("t"), "Count")),
        ),
        block=True,
        contracts=(_contract("ensures", _binary("==", _variable("result"), _int_lit("2", "usize"))),),
    )
    fixture.function(
        "SumVec",
        _type("u32"),
        (("items", _type("Vec", _type("u32"), _natural(3))),),
        _block_stmts(
            _var_stmt("acc", _int_lit("0", "u32")),
            _foreach_coll(
                "value",
                "x",
                _variable("items"),
                (_assign_stmt(_variable("acc"), "=", _call(_member(_variable("acc"), "WrappingAdd"), _variable("x"))),),
            ),
            _return_stmt(_variable("acc")),
        ),
        block=True,
    )
    fixture.function(
        "ZeroAndCountSpan",
        _type("usize"),
        (),
        _block_stmts(
            _var_stmt("buf", _call(_member(_variable("Span"), "AllocZeroed"), _int_lit("3", "usize"))),
            _foreach_coll(
                "ref",
                "b",
                _variable("buf"),
                (_assign_stmt(_variable("b"), "=", _int_lit("7", "byte")),),
            ),
            _var_stmt("sevens", _int_lit("0", "usize")),
            _foreach_coll(
                "in",
                "b",
                _variable("buf"),
                (
                    _if_stmt(
                        _binary("==", _variable("b"), _int_lit("7", "byte")),
                        _block_stmts(_assign_stmt(_variable("sevens"), "=", _call(_member(_variable("sevens"), "WrappingAdd"), _int_lit("1", "usize")))),
                    ),
                ),
            ),
            _return_stmt(_variable("sevens")),
        ),
        block=True,
        contracts=(_contract("ensures", _binary("==", _variable("result"), _int_lit("3", "usize"))),),
    )
    fixture.function(
        "CheckAllNonZero",
        _BOOL,
        (("s", _modified("in", _type("Span", _type("byte")))), ("n", _type("usize"))),
        _block_stmts(
            _var_stmt("ok", _boolean(True)),
            _foreach_range(
                "i",
                _int_lit("0", "usize"),
                _variable("n"),
                (
                    _let_stmt("v", _call(_member(_variable("Span"), "Read"), _variable("s"), _variable("i"))),
                    _if_stmt(
                        _binary("==", _variable("v"), _int_lit("0", "byte")),
                        _block_stmts(_assign_stmt(_variable("ok"), "=", _boolean(False))),
                    ),
                ),
                contracts=(
                    _invariant_contract(
                        _binary(
                            "==>",
                            _variable("ok"),
                            _call(
                                _member(_call(_member(_member(_variable("s"), "Model"), "Take"), _call("Nat", _variable("i"))), "All"),
                                _inferred_lambda(("b",), _binary("!=", _variable("b"), _int_lit("0", "byte")), bare=True),
                            ),
                        )
                    ),
                ),
            ),
            _return_stmt(_variable("ok")),
        ),
        block=True,
        contracts=(
            _contract("requires", _member(_variable("s"), "CanRead")),
            _contract("requires", _binary("==", _member(_variable("s"), "Length"), _variable("n"))),
            _contract(
                "ensures",
                _binary(
                    "==>",
                    _variable("result"),
                    _call(
                        _member(_member(_variable("s"), "Model"), "All"),
                        _inferred_lambda(("b",), _binary("!=", _variable("b"), _int_lit("0", "byte")), bare=True),
                    ),
                ),
            ),
        ),
    )
    source, response = fixture.response()
    elaborate(source, response)

    assign_let = _Fixture("AssignImmutableLet")
    assign_let.function(
        "Bad",
        _NAT,
        (),
        _block_stmts(
            _let_stmt("x", _natural(1)),
            _assign_stmt(_variable("x"), "=", _natural(2)),
            _return_stmt(_variable("x")),
        ),
        block=True,
    )
    _refuses(assign_let, "type", "immutable")

    assign_in_elem = _Fixture("AssignInForeachElem")
    assign_in_elem.function(
        "Bad",
        _type("Unit"),
        (("v", _type("Vec", _type("u32"), _natural(2))),),
        _block_stmts(
            _foreach_coll("in", "x", _variable("v"), (_assign_stmt(_variable("x"), "=", _int_lit("1", "u32")),)),
            _return_stmt(_unit()),
        ),
        block=True,
    )
    _refuses(assign_in_elem, "type", "immutable")

    mutate_frozen = _Fixture("MutateFrozenCollection")
    mutate_frozen.function(
        "Bad",
        _type("Unit"),
        (("buf", _modified("ref", _type("Span", _type("byte")))),),
        _block_stmts(
            _foreach_coll(
                "in",
                "b",
                _variable("buf"),
                (_expr_stmt(_call(_member(_variable("Span"), "Write"), _ref_arg(_variable("buf")), _int_lit("0", "usize"), _int_lit("1", "byte"))),),
            ),
            _return_stmt(_unit()),
        ),
        block=True,
        contracts=(
            _contract("requires", _member(_variable("buf"), "CanRead")),
            _contract("requires", _member(_variable("buf"), "CanWrite")),
            _contract("requires", _binary("==", _member(_variable("buf"), "Length"), _int_lit("2", "usize"))),
        ),
    )
    _refuses(mutate_frozen, "type", "frozen")

    break_outside = _Fixture("BreakOutsideLoop")
    break_outside.function("Bad", _type("Unit"), (), _block_stmts(_break_stmt()), block=True)
    _refuses(break_outside, "type", "inside a loop")

    bad_loop_inv = _Fixture("UnprovedLoopInvariant")
    bad_loop_inv.function(
        "Bad",
        _type("Unit"),
        (("n", _type("usize")),),
        _block_stmts(
            _var_stmt("c", _int_lit("0", "usize")),
            _foreach_range(
                "i",
                _int_lit("0", "usize"),
                _variable("n"),
                (),
                contracts=(_invariant_contract(_binary("==", _variable("c"), _int_lit("1", "usize"))),),
            ),
            _return_stmt(_unit()),
        ),
        block=True,
    )
    _refuses(bad_loop_inv, "type", "loop invariant")


def _record_invariants_and_selective_lifting() -> None:
    fixture = _Fixture("RecordInvariants")
    fixture.record(
        "Window",
        (("Low", _type("u32")), ("High", _type("u32")), ("SpanSize", _type("u32"))),
        contracts=(
            _invariant_contract(_binary("<=", _member(_variable("this"), "Low"), _member(_variable("this"), "High")), "Ordered"),
            _invariant_contract(
                _binary(
                    "==",
                    _member(_variable("this"), "SpanSize"),
                    _call(_member(_member(_variable("this"), "High"), "WrappingSub"), _member(_variable("this"), "Low")),
                ),
                "ConsistentSpan",
            ),
            _invariant_contract(_binary("<=", _member(_variable("this"), "High"), _int_lit("1000", "u32"))),
        ),
    )
    fixture.definition(
        "MakeWindow",
        _type("Window"),
        (),
        _call("Window", _int_lit("10", "u32"), _int_lit("30", "u32"), _int_lit("20", "u32")),
    )
    fixture.definition(
        "ShiftHigh",
        _type("Window"),
        (),
        _with_expr(_call("MakeWindow"), (("High", _int_lit("40", "u32")), ("SpanSize", _int_lit("30", "u32")))),
    )
    fixture.function(
        "ObserveLowLeHigh",
        _BOOL,
        (("w", _type("Window")),),
        _block_stmts(
            _assert(_binary("<=", _member(_variable("w"), "Low"), _member(_variable("w"), "High"))),
            _assert(_binary("<=", _member(_variable("w"), "High"), _int_lit("1000", "u32"))),
            _return_stmt(_binary("<=", _member(_variable("w"), "Low"), _member(_variable("w"), "High"))),
        ),
        block=True,
    )
    fixture.function(
        "AdjustWindowInPlace",
        _type("Window"),
        (("w", _type("Window")),),
        _block_stmts(
            _var_stmt("cur", _variable("w")),
            _open_lifts(
                (_ref_arg(_variable("cur")),),
                ("Ordered", "ConsistentSpan"),
                (
                    _assign_stmt(_member(_variable("cur"), "Low"), "=", _int_lit("50", "u32")),
                    _assign_stmt(_member(_variable("cur"), "High"), "=", _int_lit("80", "u32")),
                    _assign_stmt(
                        _member(_variable("cur"), "SpanSize"),
                        "=",
                        _call(_member(_member(_variable("cur"), "High"), "WrappingSub"), _member(_variable("cur"), "Low")),
                    ),
                ),
            ),
            _assert(_binary("<=", _member(_variable("cur"), "Low"), _member(_variable("cur"), "High"))),
            _return_stmt(_variable("cur")),
        ),
        block=True,
    )
    source, response = fixture.response()
    elaborate(source, response)

    bad_ctor = _Fixture("RecordInvariantBadCtor")
    bad_ctor.record(
        "Pair",
        (("A", _type("u32")), ("B", _type("u32"))),
        contracts=(_invariant_contract(_binary("<=", _member(_variable("this"), "A"), _member(_variable("this"), "B")), "Ordered"),),
    )
    bad_ctor.definition("Bad", _type("Pair"), (), _call("Pair", _int_lit("10", "u32"), _int_lit("5", "u32")))
    _refuses(bad_ctor, "type", "Ordered")

    bad_with = _Fixture("RecordInvariantBadWith")
    bad_with.record(
        "Pair",
        (("A", _type("u32")), ("B", _type("u32"))),
        contracts=(_invariant_contract(_binary("<=", _member(_variable("this"), "A"), _member(_variable("this"), "B")), "Ordered"),),
    )
    bad_with.definition(
        "Bad",
        _type("Pair"),
        (),
        _with_expr(_call("Pair", _int_lit("1", "u32"), _int_lit("5", "u32")), (("A", _int_lit("10", "u32")),)),
    )
    _refuses(bad_with, "type", "Ordered")

    unlifted_violation = _Fixture("RecordUnliftedViolation")
    unlifted_violation.record(
        "Pair",
        (("A", _type("u32")), ("B", _type("u32"))),
        contracts=(_invariant_contract(_binary("<=", _member(_variable("this"), "A"), _member(_variable("this"), "B")), "Ordered"),),
    )
    unlifted_violation.function(
        "Bad",
        _type("Pair"),
        (),
        _block_stmts(
            _var_stmt("p", _call("Pair", _int_lit("1", "u32"), _int_lit("5", "u32"))),
            _assign_stmt(_member(_variable("p"), "A"), "=", _int_lit("10", "u32")),
            _return_stmt(_variable("p")),
        ),
        block=True,
    )
    _refuses(unlifted_violation, "type", "Ordered")

    unrestored_scope = _Fixture("RecordUnrestoredScope")
    unrestored_scope.record(
        "Pair",
        (("A", _type("u32")), ("B", _type("u32"))),
        contracts=(_invariant_contract(_binary("<=", _member(_variable("this"), "A"), _member(_variable("this"), "B")), "Ordered"),),
    )
    unrestored_scope.function(
        "Bad",
        _type("Pair"),
        (),
        _block_stmts(
            _var_stmt("p", _call("Pair", _int_lit("1", "u32"), _int_lit("5", "u32"))),
            _open_lifts(
                (_ref_arg(_variable("p")),),
                ("Ordered",),
                (_assign_stmt(_member(_variable("p"), "A"), "=", _int_lit("10", "u32")),),
            ),
            _return_stmt(_variable("p")),
        ),
        block=True,
    )
    _refuses(unrestored_scope, "type", "Ordered")

    escape_call = _Fixture("RecordLiftedEscapeCall")
    escape_call.record(
        "Pair",
        (("A", _type("u32")), ("B", _type("u32"))),
        contracts=(_invariant_contract(_binary("<=", _member(_variable("this"), "A"), _member(_variable("this"), "B")), "Ordered"),),
    )
    escape_call.definition("ReadA", _type("u32"), (("p", _type("Pair")),), _member(_variable("p"), "A"))
    escape_call.function(
        "Bad",
        _type("Pair"),
        (),
        _block_stmts(
            _var_stmt("p", _call("Pair", _int_lit("1", "u32"), _int_lit("5", "u32"))),
            _open_lifts(
                (_ref_arg(_variable("p")),),
                ("Ordered",),
                (_let_stmt("x", _call("ReadA", _variable("p"))),),
            ),
            _return_stmt(_variable("p")),
        ),
        block=True,
    )
    _refuses(escape_call, "type", "lifted")

    unknown_clause = _Fixture("RecordUnknownLiftClause")
    unknown_clause.record(
        "Pair",
        (("A", _type("u32")), ("B", _type("u32"))),
        contracts=(_invariant_contract(_binary("<=", _member(_variable("this"), "A"), _member(_variable("this"), "B")), "Ordered"),),
    )
    unknown_clause.function(
        "Bad",
        _type("Pair"),
        (),
        _block_stmts(
            _var_stmt("p", _call("Pair", _int_lit("1", "u32"), _int_lit("5", "u32"))),
            _open_lifts((_ref_arg(_variable("p")),), ("Missing",), ()),
            _return_stmt(_variable("p")),
        ),
        block=True,
    )
    _refuses(unknown_clause, "name", "Missing")

    # Structured task scopes keep the `scope` keyword; they are design-only syntax.
    task_scope = _Fixture("TaskScopeIsNotInvariantLifting")
    task_scope.record(
        "Pair",
        (("A", _type("u32")), ("B", _type("u32"))),
        contracts=(_invariant_contract(_binary("<=", _member(_variable("this"), "A"), _member(_variable("this"), "B")), "Ordered"),),
    )
    task_scope.function(
        "Bad",
        _type("Pair"),
        (),
        _block_stmts(
            _var_stmt("p", _call("Pair", _int_lit("1", "u32"), _int_lit("5", "u32"))),
            _task_scope((_ref_arg(_variable("p")),), ()),
            _return_stmt(_variable("p")),
        ),
        block=True,
    )
    _refuses(task_scope, "unsupported", "'scope' is outside mathematical elaboration")


def _vacant_slots_and_two_step_relocation() -> None:
    fixture = _Fixture("SlotsAndRelocation")
    fixture.function(
        "WriteAndReadTwo",
        _type("u32"),
        (),
        _block_stmts(
            _var_stmt("s", _call(_member(_variable("Slots"), "AllocVacant"), generics=(_type("u32"), _natural(4)))),
            _expr_stmt(_call(_member(_variable("Slots"), "Write"), _ref_arg(_variable("s")), _int_lit("0", "usize"), _int_lit("11", "u32"))),
            _expr_stmt(_call(_member(_variable("Slots"), "Write"), _ref_arg(_variable("s")), _int_lit("1", "usize"), _int_lit("22", "u32"))),
            _assert(_call("LivePrefix", _variable("s"), _int_lit("2", "usize"))),
            _assert(_call("VacantSuffix", _variable("s"), _int_lit("2", "usize"))),
            _let_stmt("first", _call(_member(_variable("Slots"), "Read"), _variable("s"), _int_lit("0", "usize"))),
            _let_stmt("second", _call(_member(_variable("Slots"), "Read"), _variable("s"), _int_lit("1", "usize"))),
            _return_stmt(_call(_member(_variable("first"), "WrappingAdd"), _variable("second"))),
        ),
        block=True,
        contracts=(_contract("ensures", _binary("==", _variable("result"), _int_lit("33", "u32"))),),
    )
    fixture.function(
        "RelocatePrefix",
        _type("Unit"),
        (
            ("dst", _modified("ref", _type("Slots", _T, _variable("M")))),
            ("src", _modified("ref", _type("Slots", _T, _variable("N")))),
            ("count", _type("usize")),
        ),
        _block_stmts(
            _expr_stmt(
                _call(
                    "CopyRepresentation",
                    _variable("src"),
                    _ref_arg(_variable("dst")),
                    _variable("count"),
                )
            ),
            _expr_stmt(
                _call(
                    "TransferType",
                    _ref_arg(_variable("src")),
                    _ref_arg(_variable("dst")),
                    _variable("count"),
                    generics=(_T,),
                )
            ),
            _return_stmt(_unit()),
        ),
        block=True,
        generics=(("type", "T", None), ("ghost", "M", _type("usize")), ("ghost", "N", _type("usize"))),
        contracts=(
            _contract("requires", _call(_member(_variable("Slots"), "Disjoint"), _variable("dst"), _variable("src"))),
            _contract("requires", _binary("<=", _variable("count"), _variable("N"))),
            _contract("requires", _binary("<=", _variable("count"), _variable("M"))),
            _contract("requires", _call("LivePrefix", _variable("src"), _variable("count"))),
            _contract("requires", _call("VacantSuffix", _variable("src"), _variable("count"))),
            _contract("requires", _call("VacantRange", _variable("dst"), _int_lit("0", "usize"), _variable("M"))),
            _contract("ensures", _call("LivePrefix", _variable("dst"), _variable("count"))),
            _contract("ensures", _call("VacantSuffix", _variable("dst"), _variable("count"))),
            _contract("ensures", _call("VacantRange", _variable("src"), _int_lit("0", "usize"), _variable("N"))),
            _contract(
                "ensures",
                _binary(
                    "==",
                    _call("PrefixModel", _variable("dst"), _variable("count")),
                    _call("old", _call("PrefixModel", _variable("src"), _variable("count"))),
                ),
            ),
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Inductive vela_Slots" in emitted and "vela_Slots_TransferType" in emitted,
           "elaborated Gallina omitted Slots definitions")

    # Verify capacity invariance: N = 4usize vs N = 1_000_000_000usize take identical elaboration work
    for cap_lit in ("4", "1000000000"):
        cap_fix = _Fixture(f"SlotsCap_{cap_lit}")
        cap_fix.function(
            "RelocFixed",
            _type("Unit"),
            (
                ("dst", _modified("ref", _type("Slots", _type("u32"), _int_lit(cap_lit, "usize")))),
                ("src", _modified("ref", _type("Slots", _type("u32"), _int_lit(cap_lit, "usize")))),
                ("count", _type("usize")),
            ),
            _block_stmts(
                _expr_stmt(
                    _call(
                        "CopyRepresentation",
                        _variable("src"),
                        _ref_arg(_variable("dst")),
                        _variable("count"),
                    )
                ),
                _expr_stmt(
                    _call(
                        "TransferType",
                        _ref_arg(_variable("src")),
                        _ref_arg(_variable("dst")),
                        _variable("count"),
                        generics=(_type("u32"),),
                    )
                ),
                _return_stmt(_unit()),
            ),
            block=True,
            contracts=(
                _contract("requires", _call(_member(_variable("Slots"), "Disjoint"), _variable("dst"), _variable("src"))),
                _contract("requires", _binary("<=", _variable("count"), _int_lit(cap_lit, "usize"))),
                _contract("requires", _call("LivePrefix", _variable("src"), _variable("count"))),
                _contract("requires", _call("VacantRange", _variable("dst"), _int_lit("0", "usize"), _int_lit(cap_lit, "usize"))),
                _contract("ensures", _call("LivePrefix", _variable("dst"), _variable("count"))),
            ),
        )
        cs, cr = cap_fix.response()
        elaborate(cs, cr)

    read_vacant = _Fixture("SlotsReadVacant")
    read_vacant.function(
        "Bad",
        _type("u32"),
        (),
        _block_stmts(
            _var_stmt("s", _call(_member(_variable("Slots"), "AllocVacant"), generics=(_type("u32"), _natural(4)))),
            _return_stmt(_call(_member(_variable("Slots"), "Read"), _variable("s"), _int_lit("0", "usize"))),
        ),
        block=True,
    )
    _refuses(read_vacant, "type", "LivePrefix")

    write_non_vacant = _Fixture("SlotsWriteNonVacant")
    write_non_vacant.function(
        "Bad",
        _type("Unit"),
        (),
        _block_stmts(
            _var_stmt("s", _call(_member(_variable("Slots"), "AllocVacant"), generics=(_type("u32"), _natural(4)))),
            _expr_stmt(_call(_member(_variable("Slots"), "Write"), _ref_arg(_variable("s")), _int_lit("0", "usize"), _int_lit("1", "u32"))),
            _expr_stmt(_call(_member(_variable("Slots"), "Write"), _ref_arg(_variable("s")), _int_lit("0", "usize"), _int_lit("2", "u32"))),
            _return_stmt(_unit()),
        ),
        block=True,
    )
    _refuses(write_non_vacant, "type", "VacantRange")

    copy_no_disjoint = _Fixture("SlotsCopyWithoutDisjoint")
    copy_no_disjoint.function(
        "Bad",
        _type("Unit"),
        (
            ("dst", _modified("ref", _type("Slots", _type("u32"), _int_lit("4", "usize")))),
            ("src", _modified("in", _type("Slots", _type("u32"), _int_lit("4", "usize")))),
        ),
        _block_stmts(
            _expr_stmt(
                _call(
                    "CopyRepresentation",
                    _variable("src"),
                    _ref_arg(_variable("dst")),
                    _int_lit("2", "usize"),
                )
            ),
            _return_stmt(_unit()),
        ),
        block=True,
        contracts=(
            _contract("requires", _call("LivePrefix", _variable("src"), _int_lit("2", "usize"))),
            _contract("requires", _call("VacantRange", _variable("dst"), _int_lit("0", "usize"), _int_lit("4", "usize"))),
        ),
    )
    _refuses(copy_no_disjoint, "type", "Disjoint")

    transfer_without_copy = _Fixture("SlotsTransferWithoutCopy")
    transfer_without_copy.function(
        "Bad",
        _type("Unit"),
        (
            ("dst", _modified("ref", _type("Slots", _type("u32"), _int_lit("4", "usize")))),
            ("src", _modified("ref", _type("Slots", _type("u32"), _int_lit("4", "usize")))),
        ),
        _block_stmts(
            _expr_stmt(
                _call(
                    "TransferType",
                    _ref_arg(_variable("src")),
                    _ref_arg(_variable("dst")),
                    _int_lit("2", "usize"),
                    generics=(_type("u32"),),
                )
            ),
            _return_stmt(_unit()),
        ),
        block=True,
        contracts=(
            _contract("requires", _call(_member(_variable("Slots"), "Disjoint"), _variable("dst"), _variable("src"))),
            _contract("requires", _call("LivePrefix", _variable("src"), _int_lit("2", "usize"))),
            _contract("requires", _call("VacantRange", _variable("dst"), _int_lit("0", "usize"), _int_lit("4", "usize"))),
        ),
    )
    _refuses(transfer_without_copy, "type", "CopyRepresentation")


def _char_lit(spelling: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(spelling)
        return fixture.node("character", start, value=spelling)
    return form


def _pat_char(spelling: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(spelling)
        return fixture.node("character_pattern", start, value=spelling)
    return form


def _pat_string(spelling: str) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write(spelling)
        return fixture.node("string_pattern", start, value=spelling)
    return form


def _index_expr(receiver: Form, index: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        val_node = receiver(fixture)
        fixture.write("[")
        idx_node = index(fixture)
        fixture.write("]")
        return fixture.node("index", start, value=val_node, index=idx_node)
    return form


def _while_stmt(
    condition: Form,
    body_stmts: tuple[Form, ...],
    contracts: tuple[Form, ...] = (),
) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("while (")
        cond_node = condition(fixture)
        fixture.write(")")
        contract_nodes: list[Node] = []
        for contract in contracts:
            fixture.write(" ")
            contract_nodes.append(contract(fixture))
        fixture.write(" ")
        body_node = _block_stmts(*body_stmts)(fixture)
        return fixture.node(
            "while",
            start,
            condition=cond_node,
            contracts=contract_nodes,
            body=body_node,
        )
    return form


def _calc_stmt(*steps: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("calc ")
        body_node = _block_stmts(*steps)(fixture)
        return fixture.node("calc", start, body=body_node)
    return form


def _record_def_member(
    name: str,
    result: Form,
    parameters: tuple[Parameter, ...],
    value: Form,
    *,
    generics: tuple[Generic, ...] = (),
    contracts: tuple[Form, ...] = (),
) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("public definition ")
        annotation = result(fixture)
        fixture.write(" ")
        binding = fixture.name(name)
        generic_nodes = fixture.generics(generics)
        parameter_nodes = fixture.parameters(parameters)
        obligations: list[Node] = []
        for contract in contracts:
            fixture.write(" ")
            obligations.append(contract(fixture))
        fixture.write(" => ")
        body = value(fixture)
        fixture.write(";")
        return fixture.node(
            "definition",
            start,
            name=binding,
            result=annotation,
            generics=generic_nodes,
            parameters=parameter_nodes,
            contracts=obligations,
            value=body,
            modifiers=["public"],
        )
    return form


def _record_fn_member(
    name: str,
    result: Form,
    parameters: tuple[Parameter, ...],
    value: Form,
    *,
    block: bool = False,
    generics: tuple[Generic, ...] = (),
    contracts: tuple[Form, ...] = (),
) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("public ")
        annotation = result(fixture)
        fixture.write(" ")
        binding = fixture.name(name)
        generic_nodes = fixture.generics(generics)
        parameter_nodes = fixture.parameters(parameters)
        obligations: list[Node] = []
        for contract in contracts:
            fixture.write(" ")
            obligations.append(contract(fixture))
        fixture.write(" ")
        if block:
            body = value(fixture)
        else:
            bstart = fixture.offset
            fixture.write("=> ")
            ret_val = value(fixture)
            fixture.write(";")
            body = fixture.node("expression_body", bstart, value=ret_val)
        return fixture.node(
            "function",
            start,
            name=binding,
            result=annotation,
            generics=generic_nodes,
            parameters=parameter_nodes,
            contracts=obligations,
            body=body,
            cancel=None,
            modifiers=["public"],
        )
    return form


def _record_with_members(
    fixture: _Fixture,
    name: str,
    parameters: tuple[Parameter, ...],
    members: tuple[Form, ...],
    *,
    generics: tuple[Generic, ...] = (),
    contracts: tuple[Form, ...] = (),
) -> None:
    fixture.write("\n")
    start = fixture.offset
    fixture.write("public record ")
    binding = fixture.name(name)
    generic_nodes = fixture.generics(generics)
    parameter_nodes = fixture.parameters(parameters)
    obligations: list[Node] = []
    for contract in contracts:
        fixture.write(" ")
        obligations.append(contract(fixture))
    fixture.write(" {")
    member_nodes: list[Node] = []
    for member in members:
        fixture.write(" ")
        member_nodes.append(member(fixture))
    fixture.write(" }")
    fixture.declarations.append(
        fixture.node(
            "record",
            start,
            name=binding,
            generics=generic_nodes,
            parameters=parameter_nodes,
            contracts=obligations,
            declarations=member_nodes,
            modifiers=["public"],
        )
    )


def _characters_conversions_patterns_and_formatting() -> None:
    fixture = _Fixture("Characters")
    fixture.constant("AsciiA", _type("char"), _char_lit("'A'"))
    fixture.constant("Newline", _type("char"), _char_lit(r"'\n'"))
    fixture.constant("HexA", _type("char"), _char_lit(r"'\u{41}'"))
    fixture.constant("GreekAlpha", _type("char"), _char_lit(r"'\u{03B1}'"))
    fixture.definition(
        "IsAsciiUpper",
        _BOOL,
        (("c", _type("char")),),
        _binary(
            "&&",
            _binary(">=", _variable("c"), _char_lit("'A'")),
            _binary("<=", _variable("c"), _char_lit("'Z'")),
        ),
    )
    fixture.definition(
        "ClassifyPunct",
        _NAT,
        (("c", _type("char")),),
        _match_expr(
            _variable("c"),
            (
                (_pat_char("':'"), _natural(1)),
                (_pat_char("'/'"), _natural(2)),
                (_pat_wild(), _natural(0)),
            ),
        ),
    )
    fixture.definition(
        "ClassifyTag",
        _NAT,
        (("tag", _type("Vec", _NAT, _natural(2))),),
        _match_expr(
            _variable("tag"),
            (
                (_pat_string('"ok"'), _natural(1)),
                (_pat_string('"no"'), _natural(2)),
                (_pat_wild(), _natural(0)),
            ),
        ),
    )
    fixture.definition(
        "FormatSep",
        _type("TextBuilder", _natural(8)),
        (("b", _type("TextBuilder", _natural(8))), ("c", _type("char"))),
        _call(
            _member(_variable("Format"), "Write"),
            _ref_arg(_variable("b")),
            _interpolated_literal('$"[{c}]"'),
        ),
        contracts=(_contract("requires", _binary("<=", _variable("c"), _char_lit("'Z'"))),),
    )
    char_conj = _binary(
        "&&",
        _binary("==", _variable("AsciiA"), _variable("HexA")),
        _binary(
            "&&",
            _binary("==", _call("Nat", _variable("AsciiA")), _natural(65)),
            _binary(
                "&&",
                _binary(
                    "==",
                    _call(_member(_variable("u32"), "From"), _variable("GreekAlpha")),
                    _int_lit("0x03B1", "u32"),
                ),
                _binary(
                    "&&",
                    _binary(
                        "==",
                        _call(_member(_variable("char"), "From"), _int_lit("65", "u8")),
                        _char_lit("'A'"),
                    ),
                    _binary(
                        "&&",
                        _binary(
                            "==",
                            _call(_member(_variable("char"), "TryFrom"), _int_lit("0xD800", "u32")),
                            _call("Err", _variable("OutOfRange"), generics=(_type("char"), _type("ConversionError"))),
                        ),
                        _binary(
                            "&&",
                            _binary("==", _call("ClassifyPunct", _char_lit("':'")), _natural(1)),
                            _binary("==", _call("ClassifyTag", _string_literal('"ok"')), _natural(1)),
                        ),
                    ),
                ),
            ),
        ),
    )
    fixture.theorem(
        "CharEscapeAndConversions",
        (),
        _binary("==", char_conj, _boolean(True)),
        _assert(_binary("==", char_conj, _boolean(True))),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("Inductive vela_char" in emitted, "elaborated Gallina omitted vela_char")

    bad_surrogate = _Fixture("BadSurrogateChar")
    bad_surrogate.constant("Bad", _type("char"), _char_lit(r"'\u{D800}'"))
    _refuses(bad_surrogate, "syntax", "surrogate")

    non_exhaustive_char = _Fixture("NonExhaustiveChar")
    non_exhaustive_char.definition(
        "Bad",
        _NAT,
        (("c", _type("char")),),
        _match_expr(_variable("c"), ((_pat_char("'a'"), _natural(1)),)),
    )
    _refuses(non_exhaustive_char, "type", "non-exhaustive")


def _structural_equality_and_seq_contains() -> None:
    fixture = _Fixture("StructuralEquality")
    fixture.record("Point", (("X", _type("u32")), ("Y", _type("u32"))))
    fixture.union("Tag", (("Empty", ()), ("Val", (("Code", _type("u32")),))))
    eq_conj = _binary(
        "&&",
        _binary("==", _unit(), _unit()),
        _binary(
            "&&",
            _binary(
                "==",
                _tuple(_int_lit("1", "u32"), _boolean(True)),
                _tuple(_int_lit("1", "u32"), _boolean(True)),
            ),
            _binary(
                "&&",
                _binary("!=", _string_literal('"ok"'), _string_literal('"no"')),
                _binary(
                    "&&",
                    _binary(
                        "==",
                        _call("Point", _int_lit("3", "u32"), _int_lit("4", "u32")),
                        _call("Point", _int_lit("3", "u32"), _int_lit("4", "u32")),
                    ),
                    _binary(
                        "&&",
                        _binary(
                            "!=",
                            _variable("Empty"),
                            _call("Val", _int_lit("7", "u32")),
                        ),
                        _call(
                            _member(
                                _call(
                                    _member(_variable("Seq"), "Singleton"),
                                    _call("Point", _int_lit("1", "u32"), _int_lit("2", "u32")),
                                ),
                                "Contains",
                            ),
                            _call("Point", _int_lit("1", "u32"), _int_lit("2", "u32")),
                        ),
                    ),
                ),
            ),
        ),
    )
    fixture.theorem(
        "StructuralEqChecks",
        (),
        _binary("==", eq_conj, _boolean(True)),
        _assert(_binary("==", eq_conj, _boolean(True))),
    )
    source, response = fixture.response()
    elaborate(source, response)

    dep_rec_eq = _Fixture("DepRecEq")
    dep_rec_eq.record("Dep", (("N", _NAT), ("Items", _type("Vec", _NAT, _variable("N")))))
    dep_rec_eq.definition(
        "BadEq",
        _BOOL,
        (("a", _type("Dep")), ("b", _type("Dep"))),
        _binary("==", _variable("a"), _variable("b")),
    )
    _refuses(dep_rec_eq, "unsupported", "dependent record")


def _postfix_indexing_and_indexed_assignment() -> None:
    fixture = _Fixture("Indexing")
    fixture.function(
        "ReadAndMutateAll",
        _type("u32"),
        (("buf", _modified("ref", _type("Span", _type("byte")))),),
        _block_stmts(
            _assign_stmt(_index_expr(_variable("buf"), _int_lit("0", "usize")), "=", _int_lit("10", "byte")),
            _assign_stmt(_index_expr(_variable("buf"), _int_lit("0", "usize")), "+=", _int_lit("5", "byte")),
            _var_stmt("seq", _call(_member(_variable("Seq"), "Singleton"), _int_lit("20", "u32"))),
            _assign_stmt(_index_expr(_variable("seq"), _natural(0)), "+=", _int_lit("7", "u32")),
            _var_stmt(
                "vec",
                _call(
                    "VCons",
                    _int_lit("3", "u32"),
                    _call("VNil", generics=(_type("u32"),)),
                ),
            ),
            _assign_stmt(_index_expr(_variable("vec"), _natural(0)), "=", _int_lit("9", "u32")),
            _var_stmt(
                "slots",
                _call(_member(_variable("Slots"), "AllocVacant"), generics=(_type("u32"), _natural(2))),
            ),
            _assign_stmt(_index_expr(_variable("slots"), _int_lit("0", "usize")), "=", _int_lit("4", "u32")),
            _return_stmt(
                _binary(
                    "+",
                    _call(_member(_variable("u32"), "From"), _index_expr(_variable("buf"), _int_lit("0", "usize"))),
                    _binary(
                        "+",
                        _index_expr(_variable("seq"), _natural(0)),
                        _binary(
                            "+",
                            _index_expr(_variable("vec"), _natural(0)),
                            _index_expr(_variable("slots"), _int_lit("0", "usize")),
                        ),
                    ),
                )
            ),
        ),
        block=True,
        contracts=(
            _contract("requires", _member(_variable("buf"), "CanRead")),
            _contract("requires", _member(_variable("buf"), "CanWrite")),
            _contract("requires", _binary("==", _member(_variable("buf"), "Length"), _int_lit("2", "usize"))),
            _contract("ensures", _binary("==", _variable("result"), _int_lit("55", "u32"))),
        ),
    )
    source, response = fixture.response()
    elaborate(source, response)

    oob_span = _Fixture("OobSpanIndex")
    oob_span.definition(
        "Bad",
        _type("byte"),
        (("s", _type("Span", _type("byte"))),),
        _index_expr(_variable("s"), _int_lit("0", "usize")),
        contracts=(_contract("requires", _member(_variable("s"), "CanRead")),),
    )
    _refuses(oob_span, "type", "Span.Length bounds")

    oob_vec_write = _Fixture("OobVecWrite")
    oob_vec_write.function(
        "Bad",
        _type("Vec", _type("u32"), _natural(1)),
        (("v", _type("Vec", _type("u32"), _natural(1))),),
        _block_stmts(
            _var_stmt("m", _variable("v")),
            _assign_stmt(_index_expr(_variable("m"), _natural(2)), "=", _int_lit("1", "u32")),
            _return_stmt(_variable("m")),
        ),
        block=True,
    )
    _refuses(oob_vec_write, "type", "in bounds")


def _bounded_while_loops_and_decreases_contracts() -> None:
    fixture = _Fixture("BoundedWhile")
    fixture.function(
        "CountWhile",
        _type("usize"),
        (),
        _block_stmts(
            _var_stmt("i", _int_lit("0", "usize")),
            _var_stmt("acc", _int_lit("0", "usize")),
            _while_stmt(
                _binary("<", _variable("i"), _int_lit("4", "usize")),
                (
                    _assign_stmt(_variable("i"), "+=", _int_lit("1", "usize")),
                    _if_stmt(
                        _binary("==", _variable("i"), _int_lit("2", "usize")),
                        _block_stmts(_continue_stmt()),
                    ),
                    _assign_stmt(_variable("acc"), "+=", _int_lit("1", "usize")),
                ),
                contracts=(
                    _contract("invariant", _binary("<=", _variable("i"), _int_lit("4", "usize"))),
                    _contract("decreases", _binary("-", _int_lit("4", "usize"), _variable("i"))),
                ),
            ),
            _return_stmt(_variable("acc")),
        ),
        block=True,
        contracts=(_contract("ensures", _binary("==", _variable("result"), _int_lit("3", "usize"))),),
    )
    fixture.function(
        "SymbolicWhileInvariant",
        _type("usize"),
        (("n", _type("usize")),),
        _block_stmts(
            _var_stmt("i", _int_lit("0", "usize")),
            _while_stmt(
                _binary("<", _variable("i"), _variable("n")),
                (_assign_stmt(_variable("i"), "+=", _int_lit("1", "usize")),),
                contracts=(
                    _contract("invariant", _binary("<=", _variable("i"), _variable("n"))),
                    _contract("decreases", _binary("-", _variable("n"), _variable("i"))),
                ),
            ),
            _return_stmt(_variable("i")),
        ),
        block=True,
        contracts=(
            _contract("requires", _binary("<=", _variable("n"), _int_lit("10", "usize"))),
            _contract("ensures", _binary("==", _variable("result"), _variable("n"))),
        ),
    )
    source, response = fixture.response()
    elaborate(source, response)

    non_decreasing = _Fixture("WhileNonDecreasing")
    non_decreasing.function(
        "Bad",
        _type("usize"),
        (),
        _block_stmts(
            _var_stmt("i", _int_lit("0", "usize")),
            _while_stmt(
                _binary("<", _variable("i"), _int_lit("2", "usize")),
                (_assign_stmt(_variable("i"), "+=", _int_lit("1", "usize")),),
                contracts=(_contract("decreases", _variable("i")),),
            ),
            _return_stmt(_variable("i")),
        ),
        block=True,
    )
    _refuses(non_decreasing, "type", "strictly decrease")


def _calculational_proofs_where_and_multi_ensures() -> None:
    fixture = _Fixture("CalcAndMultiEnsures")
    fixture.definition(
        "Double",
        _NAT,
        (("x", _NAT),),
        _binary("+", _variable("x"), _variable("x")),
        contracts=(_contract("where", _binary("<=", _variable("x"), _natural(100))),),
    )
    fixture.theorem(
        "ChainCalcAndMultiEnsures",
        (("a", _NAT), ("b", _NAT), ("c", _NAT)),
        _binary("==", _variable("a"), _variable("c")),
        _block_stmts(
            _calc_stmt(
                _assert(_binary("==", _variable("a"), _variable("b"))),
                _assert(_binary("==", _variable("b"), _variable("c"))),
            ),
            _assert(_binary("==", _variable("c"), _variable("a"))),
        ),
        contracts=(
            _contract("where", _binary("==", _variable("a"), _variable("b"))),
            _contract("requires", _binary("==", _variable("b"), _variable("c"))),
            _contract("ensures", _binary("==", _variable("c"), _variable("a"))),
        ),
    )
    source, response = fixture.response()
    emitted = elaborate(source, response).gallina
    ensure("_ensures_1" in emitted, "multiple ensures clauses on theorem did not emit _ensures_1")

    bad_calc = _Fixture("BadCalcStep")
    bad_calc.theorem(
        "BrokenChain",
        (("a", _NAT), ("b", _NAT), ("c", _NAT)),
        _binary("==", _variable("a"), _variable("c")),
        _block_stmts(
            _calc_stmt(
                _assert(_binary("==", _variable("a"), _variable("b"))),
                _assert(_binary("==", _variable("c"), _variable("c"))),
            ),
        ),
        contracts=(
            _contract("requires", _binary("==", _variable("a"), _variable("b"))),
            _contract("requires", _binary("==", _variable("b"), _variable("c"))),
        ),
    )
    _refuses(bad_calc, "type", "left-hand side does not match previous right-hand side")


def _record_member_methods_and_contracts() -> None:
    fixture = _Fixture("RecordMethods")
    _record_with_members(
        fixture,
        "BoundedCounter",
        (("Value", _type("u32")), ("Limit", _type("u32"))),
        (
            _record_def_member(
                "Remaining",
                _type("u32"),
                (),
                _binary("-", _variable("Limit"), _variable("Value")),
            ),
            _record_fn_member(
                "Add",
                _type("BoundedCounter"),
                (("delta", _type("u32")),),
                _with_expr(_variable("this"), (("Value", _binary("+", _variable("Value"), _variable("delta"))),)),
                contracts=(
                    _contract("where", _binary("<=", _variable("delta"), _call(_member(_variable("this"), "Remaining")))),
                    _contract(
                        "ensures",
                        _binary(
                            "==",
                            _member(_variable("result"), "Value"),
                            _binary("+", _variable("Value"), _variable("delta")),
                        ),
                    ),
                ),
            ),
        ),
        contracts=(_contract("invariant", _binary("<=", _variable("Value"), _variable("Limit"))),),
    )
    fixture.definition(
        "UseCounter",
        _type("u32"),
        (),
        _call(
            _member(
                _call(
                    _member(_call("BoundedCounter", _int_lit("3", "u32"), _int_lit("10", "u32")), "Add"),
                    _int_lit("4", "u32"),
                ),
                "Remaining",
            )
        ),
    )
    fixture.theorem(
        "UseCounterCheck",
        (),
        _binary("==", _call("UseCounter"), _int_lit("3", "u32")),
        _assert(_binary("==", _call("UseCounter"), _int_lit("3", "u32"))),
    )
    source, response = fixture.response()
    elaborate(source, response)

    violate_method_pre = _Fixture("ViolateRecordMethodPre")
    _record_with_members(
        violate_method_pre,
        "Counter",
        (("Value", _type("u32")),),
        (
            _record_def_member(
                "Dec",
                _type("u32"),
                (("step", _type("u32")),),
                _binary("-", _variable("Value"), _variable("step")),
                contracts=(_contract("requires", _binary("<=", _variable("step"), _variable("Value"))),),
            ),
        ),
    )
    violate_method_pre.definition(
        "BadCall",
        _type("u32"),
        (),
        _call(_member(_call("Counter", _int_lit("2", "u32")), "Dec"), _int_lit("5", "u32")),
    )
    _refuses(violate_method_pre, "type", "precondition")


def _out_arg(value: Form) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        op = fixture.name("out")
        fixture.write(" ")
        inner = value(fixture)
        return fixture.node("unary", start, operator=op, value=inner)

    return form


def _import_decl(fixture: _Fixture, module_path: str) -> None:
    fixture.write("\n")
    start = fixture.offset
    fixture.write("import ")
    name_node = fixture.name(module_path)
    fixture.write(";")
    fixture.declarations.append(fixture.node("import", start, name=name_node))


def _interface_fn_sig(
    name: str,
    result: Form,
    parameters: tuple[Parameter, ...],
    contracts: tuple[Form, ...] = (),
) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        res_node = result(fixture)
        fixture.write(" ")
        name_node = fixture.name(name)
        param_nodes = fixture.parameters(parameters)
        contract_nodes: list[Node] = []
        for c in contracts:
            fixture.write(" ")
            contract_nodes.append(c(fixture))
        fixture.write(";")
        return fixture.node(
            "function",
            start,
            name=name_node,
            result=res_node,
            generics=[],
            parameters=param_nodes,
            contracts=contract_nodes,
            body=None,
            cancel=None,
            modifiers=[],
        )

    return form


def _interface_law_sig(
    name: str,
    parameters: tuple[Parameter, ...],
    proposition: Form,
    contracts: tuple[Form, ...] = (),
) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("lemma ")
        name_node = fixture.name(name)
        param_nodes = fixture.parameters(parameters)
        contract_nodes: list[Node] = []
        for c in contracts:
            fixture.write(" ")
            contract_nodes.append(c(fixture))
        fixture.write(" ")
        contract_nodes.append(_contract("ensures", proposition)(fixture))
        fixture.write(";")
        return fixture.node(
            "lemma",
            start,
            name=name_node,
            generics=[],
            parameters=param_nodes,
            contracts=contract_nodes,
            body=None,
            modifiers=[],
        )

    return form


def _interface_decl(
    fixture: _Fixture,
    name: str,
    generics: tuple[Generic, ...],
    members: tuple[Form, ...],
    contracts: tuple[Form, ...] = (),
) -> None:
    fixture.write("\n")
    start = fixture.offset
    fixture.write("public interface ")
    name_node = fixture.name(name)
    gen_nodes = fixture.generics(generics)
    contract_nodes: list[Node] = []
    for c in contracts:
        fixture.write(" ")
        contract_nodes.append(c(fixture))
    fixture.write(" {")
    member_nodes: list[Node] = []
    for m in members:
        fixture.write(" ")
        member_nodes.append(m(fixture))
    fixture.write(" }")
    fixture.declarations.append(
        fixture.node(
            "interface",
            start,
            name=name_node,
            generics=gen_nodes,
            contracts=contract_nodes,
            declarations=member_nodes,
            modifiers=["public"],
        )
    )


def _impl_law_member(
    name: str,
    parameters: tuple[Parameter, ...],
    proposition: Form,
    proof: Form,
    contracts: tuple[Form, ...] = (),
) -> Form:
    def form(fixture: _Fixture) -> Node:
        start = fixture.offset
        fixture.write("lemma ")
        name_node = fixture.name(name)
        param_nodes = fixture.parameters(parameters)
        contract_nodes: list[Node] = []
        for c in contracts:
            fixture.write(" ")
            contract_nodes.append(c(fixture))
        fixture.write(" ")
        contract_nodes.append(_contract("ensures", proposition)(fixture))
        fixture.write(" proof ")
        body_node = _block_stmts(proof)(fixture)
        return fixture.node(
            "lemma",
            start,
            name=name_node,
            generics=[],
            parameters=param_nodes,
            contracts=contract_nodes,
            body=body_node,
            modifiers=[],
        )

    return form


def _impl_decl(
    fixture: _Fixture,
    target_type: Form,
    members: tuple[Form, ...],
    generics: tuple[Generic, ...] = (),
    contracts: tuple[Form, ...] = (),
) -> None:
    fixture.write("\n")
    start = fixture.offset
    fixture.write("public impl")
    gen_nodes = fixture.generics(generics)
    fixture.write(" ")
    ty_node = target_type(fixture)
    contract_nodes: list[Node] = []
    for c in contracts:
        fixture.write(" ")
        contract_nodes.append(c(fixture))
    fixture.write(" {")
    member_nodes: list[Node] = []
    for m in members:
        fixture.write(" ")
        member_nodes.append(m(fixture))
    fixture.write(" }")
    fixture.declarations.append(
        fixture.node(
            "impl",
            start,
            generics=gen_nodes,
            type=ty_node,
            contracts=contract_nodes,
            declarations=member_nodes,
            modifiers=["public"],
        )
    )


def _out_loan_parameters_and_initialization_tracking() -> None:
    fixture = _Fixture("OutLoanParameters")
    fixture.function(
        "InitPair",
        _type("Unit"),
        (("x", _NAT), ("first", _modified("out", _NAT)), ("second", _modified("out", _NAT))),
        _block_stmts(
            _assign_stmt(_variable("first"), "=", _binary("+", _variable("x"), _natural(1))),
            _assign_stmt(_variable("second"), "=", _binary("+", _variable("first"), _natural(1))),
            _return_stmt(),
        ),
        block=True,
        contracts=(
            _contract("ensures", _binary("==", _variable("first"), _binary("+", _variable("x"), _natural(1)))),
            _contract("ensures", _binary("==", _variable("second"), _binary("+", _variable("x"), _natural(2)))),
        ),
    )
    fixture.function(
        "InitFromBranch",
        _type("Unit"),
        (("flag", _BOOL), ("x", _NAT), ("dst", _modified("out", _NAT))),
        _block_stmts(
            _if_stmt(
                _variable("flag"),
                _block_stmts(_assign_stmt(_variable("dst"), "=", _binary("+", _variable("x"), _natural(1)))),
                _block_stmts(_assign_stmt(_variable("dst"), "=", _binary("+", _variable("x"), _natural(2)))),
            ),
            _return_stmt(),
        ),
        block=True,
        contracts=(_contract("ensures", _binary(">", _variable("dst"), _variable("x"))),),
    )
    fixture.function(
        "DelegateOut",
        _type("Unit"),
        (("x", _NAT), ("a", _modified("out", _NAT)), ("b", _modified("out", _NAT))),
        _block_stmts(
            _expr_stmt(_call("InitPair", _variable("x"), _out_arg(_variable("a")), _out_arg(_variable("b")))),
            _return_stmt(),
        ),
        block=True,
        contracts=(
            _contract("ensures", _binary("==", _variable("a"), _binary("+", _variable("x"), _natural(1)))),
            _contract("ensures", _binary("==", _variable("b"), _binary("+", _variable("x"), _natural(2)))),
        ),
    )
    fixture.function(
        "UseOutCaller",
        _NAT,
        (),
        _block_stmts(
            _var_stmt("a", _natural(0)),
            _var_stmt("b", _natural(0)),
            _expr_stmt(_call("DelegateOut", _natural(10), _out_arg(_variable("a")), _out_arg(_variable("b")))),
            _return_stmt(_binary("+", _variable("a"), _variable("b"))),
        ),
        block=True,
        contracts=(_contract("ensures", _binary("==", _variable("result"), _natural(23))),),
    )
    source, response = fixture.response()
    elaborate(source, response)

    uninit_return = _Fixture("UninitOutReturn")
    uninit_return.function(
        "Bad",
        _type("Unit"),
        (("dst", _modified("out", _NAT)),),
        _block_stmts(_return_stmt()),
        block=True,
    )
    _refuses(uninit_return, "type", "before 'out' parameter 'dst' is initialized")

    uninit_branch = _Fixture("UninitOutBranch")
    uninit_branch.function(
        "Bad",
        _type("Unit"),
        (("flag", _BOOL), ("dst", _modified("out", _NAT))),
        _block_stmts(
            _if_stmt(
                _variable("flag"),
                _block_stmts(_assign_stmt(_variable("dst"), "=", _natural(1))),
            ),
            _return_stmt(),
        ),
        block=True,
    )
    _refuses(uninit_branch, "type", "before 'out' parameter 'dst' is initialized")

    read_uninit = _Fixture("ReadUninitOut")
    read_uninit.function(
        "Bad",
        _NAT,
        (("dst", _modified("out", _NAT)),),
        _block_stmts(_return_stmt(_variable("dst"))),
        block=True,
    )
    _refuses(read_uninit, "type", "cannot read uninitialized 'out' parameter 'dst'")

    compound_uninit = _Fixture("CompoundUninitOut")
    compound_uninit.function(
        "Bad",
        _type("Unit"),
        (("dst", _modified("out", _NAT)),),
        _block_stmts(
            _assign_stmt(_variable("dst"), "+=", _natural(1)),
            _return_stmt(),
        ),
        block=True,
    )
    _refuses(compound_uninit, "type", "uninitialized 'out' parameter 'dst'")

    partial_uninit = _Fixture("PartialUninitOut")
    partial_uninit.record("PairRec", (("X", _NAT), ("Y", _NAT)))
    partial_uninit.function(
        "Bad",
        _type("Unit"),
        (("dst", _modified("out", _type("PairRec"))),),
        _block_stmts(
            _assign_stmt(_member(_variable("dst"), "X"), "=", _natural(1)),
            _return_stmt(),
        ),
        block=True,
    )
    _refuses(partial_uninit, "type", "uninitialized 'out' parameter 'dst'")

    old_on_out = _Fixture("OldOnOut")
    old_on_out.function(
        "Bad",
        _type("Unit"),
        (("dst", _modified("out", _NAT)),),
        _block_stmts(
            _assign_stmt(_variable("dst"), "=", _natural(1)),
            _return_stmt(),
        ),
        block=True,
        contracts=(_contract("ensures", _binary("==", _variable("dst"), _call("old", _variable("dst")))),),
    )
    _refuses(old_on_out, "type", "write-only 'out' parameter 'dst'")

    missing_out_mod = _Fixture("MissingOutMod")
    missing_out_mod.function(
        "Init",
        _type("Unit"),
        (("dst", _modified("out", _NAT)),),
        _block_stmts(_assign_stmt(_variable("dst"), "=", _natural(1)), _return_stmt()),
        block=True,
    )
    missing_out_mod.function(
        "Caller",
        _type("Unit"),
        (),
        _block_stmts(
            _var_stmt("x", _natural(0)),
            _expr_stmt(_call("Init", _variable("x"))),
            _return_stmt(),
        ),
        block=True,
    )
    _refuses(missing_out_mod, "type", "an 'out' parameter requires an 'out' call-site argument modifier")

    overlap_out = _Fixture("OverlapOut")
    overlap_out.function(
        "InitTwo",
        _type("Unit"),
        (("a", _modified("out", _NAT)), ("b", _modified("out", _NAT))),
        _block_stmts(
            _assign_stmt(_variable("a"), "=", _natural(1)),
            _assign_stmt(_variable("b"), "=", _natural(2)),
            _return_stmt(),
        ),
        block=True,
    )
    overlap_out.function(
        "Caller",
        _type("Unit"),
        (),
        _block_stmts(
            _var_stmt("x", _natural(0)),
            _expr_stmt(_call("InitTwo", _out_arg(_variable("x")), _out_arg(_variable("x")))),
            _return_stmt(),
        ),
        block=True,
    )
    _refuses(overlap_out, "type", "overlapping loan for 'x'")


def _interfaces_nonoverlapping_impls_and_where_constraints() -> None:
    fixture = _Fixture("InterfacesAndImpls")
    _interface_decl(
        fixture,
        "Steppable",
        (("type", "T", None),),
        (
            _interface_fn_sig(
                "Step",
                _type("T"),
                (("x", _type("T")),),
            ),
            _interface_law_sig(
                "StepDeterministic",
                (("x", _type("T")),),
                _binary("==", _call("Step", _variable("x")), _call("Step", _variable("x"))),
            ),
        ),
    )
    _impl_decl(
        fixture,
        _type("Steppable", _NAT),
        (
            _record_def_member(
                "Step",
                _NAT,
                (("x", _NAT),),
                _binary("+", _variable("x"), _natural(1)),
            ),
            _impl_law_member(
                "StepDeterministic",
                (("x", _NAT),),
                _binary("==", _call("Step", _variable("x")), _call("Step", _variable("x"))),
                _assert(_binary("==", _call("Step", _variable("x")), _call("Step", _variable("x")))),
            ),
        ),
    )
    fixture.function(
        "StepTwice",
        _type("T"),
        (("x", _type("T")),),
        _block_stmts(
            _let_stmt("first", _call(_member(_variable("x"), "Step"))),
            _return_stmt(_call(_member(_variable("Steppable"), "Step"), _variable("first"))),
        ),
        block=True,
        generics=(("type", "T", None),),
        contracts=(_contract("where", _call("Steppable", _type_value(_type("T")))),),
    )
    fixture.theorem(
        "StepTwiceNatCheck",
        (),
        _binary("==", _call("StepTwice", _natural(5)), _natural(7)),
        _assert(_binary("==", _call("StepTwice", _natural(5)), _natural(7))),
    )
    source, response = fixture.response()
    elaborate(source, response)

    blanket = _Fixture("BlanketImplRefused")
    _interface_decl(
        blanket,
        "IdIface",
        (("type", "T", None),),
        (_interface_fn_sig("Id", _type("T"), (("x", _type("T")),)),),
    )
    _impl_decl(
        blanket,
        _type("IdIface", _type("T")),
        (_record_def_member("Id", _type("T"), (("x", _type("T")),), _variable("x")),),
        generics=(("type", "T", None),),
    )
    _refuses(blanket, "type", "blanket impl")

    overlap = _Fixture("OverlapImplRefused")
    _interface_decl(
        overlap,
        "IdIface",
        (("type", "T", None),),
        (_interface_fn_sig("Id", _type("T"), (("x", _type("T")),)),),
    )
    _impl_decl(
        overlap,
        _type("IdIface", _NAT),
        (_record_def_member("Id", _NAT, (("x", _NAT),), _variable("x")),),
    )
    _impl_decl(
        overlap,
        _type("IdIface", _NAT),
        (_record_def_member("Id", _NAT, (("x", _NAT),), _variable("x")),),
    )
    _refuses(overlap, "type", "overlapping or duplicate impl")

    missing_law = _Fixture("MissingImplLaw")
    _interface_decl(
        missing_law,
        "Lawful",
        (("type", "T", None),),
        (
            _interface_fn_sig("Act", _type("T"), (("x", _type("T")),)),
            _interface_law_sig(
                "SelfEq",
                (("x", _type("T")),),
                _binary("==", _call("Act", _variable("x")), _call("Act", _variable("x"))),
            ),
        ),
    )
    _impl_decl(
        missing_law,
        _type("Lawful", _NAT),
        (_record_def_member("Act", _NAT, (("x", _NAT),), _variable("x")),),
    )
    _refuses(missing_law, "type", "is missing required law 'SelfEq'")

    unsatisfied = _Fixture("UnsatisfiedWhere")
    _interface_decl(
        unsatisfied,
        "Steppable",
        (("type", "T", None),),
        (_interface_fn_sig("Step", _type("T"), (("x", _type("T")),)),),
    )
    unsatisfied.definition(
        "UseStep",
        _type("T"),
        (("x", _type("T")),),
        _call(_member(_variable("Steppable"), "Step"), _variable("x")),
        generics=(("type", "T", None),),
        contracts=(_contract("where", _call("Steppable", _type_value(_type("T")))),),
    )
    unsatisfied.definition(
        "BadCall",
        _BOOL,
        (),
        _call("UseStep", _boolean(True)),
    )
    _refuses(unsatisfied, "type", "no implementation of interface 'Steppable'")


def _multi_module_imports_and_visibility() -> None:
    math_mod = _Fixture("MathMod")
    math_mod.definition(
        "Double",
        _NAT,
        (("x", _NAT),),
        _binary("+", _variable("x"), _variable("x")),
    )
    math_mod.write("\n")
    priv_start = math_mod.offset
    math_mod.write("private definition Nat Secret(Nat x) => x + 1;")
    math_mod.declarations.append(
        {
            "kind": "definition",
            "span": [priv_start, math_mod.offset],
            "name": {"text": "Secret", "span": [priv_start + 23, priv_start + 29]},
            "result": {"kind": "type", "span": [priv_start + 19, priv_start + 22], "name": {"text": "Nat", "span": [priv_start + 19, priv_start + 22]}, "arguments": []},
            "generics": [],
            "parameters": [
                {
                    "kind": "parameter",
                    "span": [priv_start + 30, priv_start + 35],
                    "name": {"text": "x", "span": [priv_start + 34, priv_start + 35]},
                    "type": {"kind": "type", "span": [priv_start + 30, priv_start + 33], "name": {"text": "Nat", "span": [priv_start + 30, priv_start + 33]}, "arguments": []},
                    "grade": None,
                }
            ],
            "contracts": [],
            "value": {
                "kind": "binary",
                "span": [priv_start + 40, priv_start + 45],
                "operator": {"text": "+", "span": [priv_start + 42, priv_start + 43]},
                "left": {"kind": "name", "span": [priv_start + 40, priv_start + 41], "name": {"text": "x", "span": [priv_start + 40, priv_start + 41]}},
                "right": {"kind": "nat", "span": [priv_start + 44, priv_start + 45], "value": "1", "suffix": ""},
            },
            "modifiers": ["private"],
        }
    )

    consumer = _Fixture("ConsumerMod")
    _import_decl(consumer, "MathMod")
    consumer.definition(
        "Quad",
        _NAT,
        (("x", _NAT),),
        _call(_member(_variable("MathMod"), "Double"), _call("Double", _variable("x"))),
    )
    consumer.theorem(
        "QuadCheck",
        (),
        _binary("==", _call("Quad", _natural(3)), _natural(12)),
        _assert(_binary("==", _call("Quad", _natural(3)), _natural(12))),
    )
    pkg_results = elaborate_package([consumer.response(), math_mod.response()])
    ensure(
        tuple(pkg_results.keys()) == ("MathMod", "ConsumerMod"),
        "elaborate_package did not topologically order dependencies",
    )

    priv_access = _Fixture("PrivConsumer")
    _import_decl(priv_access, "MathMod")
    priv_access.definition("Bad", _NAT, (), _call("Secret", _natural(1)))
    try:
        elaborate_package([math_mod.response(), priv_access.response()])
    except VelaError as error:
        ensure(error.kind == "name" and "private declaration 'Secret'" in error.message, f"unexpected error: {error}")
    else:
        raise AssertionError("accepted cross-module private call")

    cyc_a = _Fixture("CycA")
    _import_decl(cyc_a, "CycB")
    cyc_b = _Fixture("CycB")
    _import_decl(cyc_b, "CycA")
    try:
        elaborate_package([cyc_a.response(), cyc_b.response()])
    except VelaError as error:
        ensure(error.kind == "name" and "circular module import" in error.message, f"unexpected error: {error}")
    else:
        raise AssertionError("accepted circular module imports")


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
            Case("concise-lambdas-and-expression-bodies", _concise_lambdas_and_expression_bodies),
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
            Case("raw-strings-and-checked-formatting", _raw_strings_and_checked_formatting),
            Case("records-properties-updates-guards-and-expressions", _records_properties_updates_guards_and_expressions),
            Case("tagged-union-declarations-and-elimination", _union_declarations_and_elimination),
            Case("structural-recursion-and-decreases-contracts", _structural_recursion_and_decreases),
            Case("inductive-proofs-and-equational-rewriting", _inductive_proofs_and_equational_rewriting),
            Case("dependent-records-and-existential-propositions", _dependent_records_and_existential_propositions),
            Case("early-return-propagation-for-option-and-result", _early_return_propagation),
            Case("represented-integers-preconditions-and-conversions", _represented_integers_and_conversions),
            Case("pure-sequences-and-model-reasoning", _pure_sequences_and_model_reasoning),
            Case("mutable-locals-assignments-and-bounded-loops", _mutable_locals_assignments_and_bounded_loops),
            Case("record-invariants-and-selective-lifting", _record_invariants_and_selective_lifting),
            Case("vacant-slots-and-two-step-relocation", _vacant_slots_and_two_step_relocation),
            Case("characters-conversions-patterns-and-formatting", _characters_conversions_patterns_and_formatting),
            Case("structural-equality-and-seq-contains", _structural_equality_and_seq_contains),
            Case("postfix-indexing-and-indexed-assignment", _postfix_indexing_and_indexed_assignment),
            Case("bounded-while-loops-and-decreases-contracts", _bounded_while_loops_and_decreases_contracts),
            Case("calculational-proofs-where-and-multi-ensures", _calculational_proofs_where_and_multi_ensures),
            Case("record-member-methods-and-contracts", _record_member_methods_and_contracts),
            Case("out-loan-parameters-and-initialization-tracking", _out_loan_parameters_and_initialization_tracking),
            Case("interfaces-nonoverlapping-impls-and-where-constraints", _interfaces_nonoverlapping_impls_and_where_constraints),
            Case("multi-module-imports-and-visibility", _multi_module_imports_and_visibility)]
