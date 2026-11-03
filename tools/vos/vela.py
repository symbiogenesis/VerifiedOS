# SPDX-License-Identifier: Apache-2.0
"""Untrusted pure Vela syntax consumption and translation into existing CIC terms.

Both syntax routes feed the same name/type checker and emitter. The emitted
definitions interpret this fragment; no source-correspondence or kernel verdict
is supplied. Python parsing remains the default pending native qualification.
"""

import hashlib
from dataclasses import dataclass
from typing import cast

from vos import vela_ast as syntax
from vos.vela_ast import (
    MAX_BLOCK_DEPTH,
    MAX_EXPRESSION_DEPTH,
    MAX_LITERAL_DIGITS,
    MAX_SOURCE_BYTES,
    ValueType,
    VelaError,
)
from vos.vela_facts import Facts, SymbolKind

__all__ = ["MAX_BLOCK_DEPTH", "MAX_EXPRESSION_DEPTH", "MAX_LITERAL_DIGITS", "MAX_SOURCE_BYTES",
           "Translation", "ValueType", "VelaError", "inspect_source", "translate", "translate_ast"]

_TYPES: dict[ValueType, str] = {
    "Nat": "Corelib.Init.Datatypes.nat",
    "bool": "Corelib.Init.Datatypes.bool",
}
_TRUE = "Corelib.Init.Datatypes.true"
_FALSE = "Corelib.Init.Datatypes.false"
MAX_STATIC_WORK = 20_000
MAX_STATIC_DEPTH = 128
MAX_STATIC_NAT = 10 ** MAX_LITERAL_DIGITS - 1
MAX_OUTPUT_BYTES = 1_048_576


@dataclass(frozen=True)
class Translation:
    module: str
    gallina: str


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    line: int
    column: int

    @property
    def site(self) -> syntax.Site:
        return syntax.Site(self.line, self.column)


@dataclass(frozen=True)
class _Expression:
    value_type: ValueType
    gallina: str
    depth: int = 1


@dataclass(frozen=True)
class _Signature:
    parameters: tuple[tuple[syntax.Name, ValueType, int | None], ...]
    result: ValueType
    symbol: int | None
    source: syntax.Function
    constants: dict[str, _Local]


@dataclass(frozen=True)
class _Static:
    value_type: ValueType
    value: int | bool


@dataclass(frozen=True)
class _Local:
    value_type: ValueType
    symbol: int | None
    static: _Static | None = None
    required_static: bool = False
    gallina: str | None = None
    initializer: _Expression | None = None


def _tokens(source: bytes) -> list[_Token]:
    text = syntax.source_text(source).replace("\r\n", "\n").replace("\r", "\n")
    result: list[_Token] = []
    offset, line, column = 0, 1, 1
    while offset < len(text):
        character = text[offset]
        if character in " \t\n":
            if character == "\n":
                line, column = line + 1, 1
            else:
                column += 1
            offset += 1
            continue
        if text.startswith("//", offset):
            end = text.find("\n", offset)
            end = len(text) if end == -1 else end
            column += end - offset
            offset = end
            continue
        if match := syntax.IDENTIFIER.match(text, offset):
            spelling = match.group()
            if spelling in syntax.UNSUPPORTED:
                raise VelaError("unsupported", line, column, syntax.unsupported_message(spelling))
            kind = "keyword" if spelling in syntax.KEYWORDS else "name"
        elif match := syntax.DECIMAL.match(text, offset):
            spelling = match.group()
            if len(spelling.replace("_", "")) > MAX_LITERAL_DIGITS:
                raise VelaError("limit", line, column,
                                f"literal exceeds {MAX_LITERAL_DIGITS} decimal digits")
            kind = "decimal"
        elif text[offset:offset + 2] in {"->", "=>", "==", "<="}:
            spelling, kind = text[offset:offset + 2], "symbol"
        elif character in "();,:{}=+*":
            spelling, kind = character, "symbol"
        else:
            raise VelaError("syntax", line, column, f"unexpected character {character!r}")
        result.append(_Token(kind, spelling, line, column))
        offset += len(spelling)
        column += len(spelling)
    result.append(_Token("eof", "end of file", line, column))
    return result


class _Parser:
    """Legacy syntax route; actions contain no resolution, typing or emission."""

    def __init__(self, tokens: list[_Token]) -> None:
        self.tokens = tokens
        self.offset = 0

    def _current(self) -> _Token:
        return self.tokens[self.offset]

    def _error(self, kind: str, message: str, token: _Token | None = None) -> VelaError:
        site = self._current() if token is None else token
        return VelaError(kind, site.line, site.column, message)

    def _take(self, spelling: str) -> bool:
        if self._current().text == spelling:
            self.offset += 1
            return True
        return False

    def _expect(self, spelling: str) -> _Token:
        token = self._current()
        if not self._take(spelling):
            raise self._error("syntax", f"expected '{spelling}', found {token.text!r}")
        return token

    def _name(self) -> syntax.Name:
        token = self._current()
        if token.kind != "name":
            raise self._error("syntax", f"expected identifier, found {token.text!r}")
        self.offset += 1
        return syntax.Name(token.text, token.site)

    def _value_type(self) -> ValueType:
        token = self._current()
        if token.text in {"Nat", "bool"}:
            self.offset += 1
            return token.text
        if token.kind not in {"name", "keyword"}:
            raise self._error("syntax", f"expected parameter or result type, found {token.text!r}")
        raise self._error("unsupported", f"type {token.text!r} is outside Nat and bool")

    def parse(self) -> syntax.Module:
        self._expect("module")
        module = self._name()
        self._expect(";")
        declarations: list[syntax.Function | syntax.Constant] = []
        while self._current().kind != "eof":
            start = self._expect("public")
            is_const = self._take("const")
            if self._current().text == "const":
                raise self._error("syntax", "repeated const declaration modifier")
            if is_const and self._current().kind == "name" and self.tokens[self.offset + 1].text == "=":
                raise self._error("syntax", "const requires an explicit type before its name")
            result = self._value_type()
            name = self._name()
            if self._current().text == "(":
                declarations.append(self._function(name, result, is_const))
            elif is_const:
                self._expect("=")
                value = self._expression(1)
                self._expect(";")
                declarations.append(syntax.Constant(name, result, value, start.site))
            else:
                raise self._error("syntax", "expected '(' after function name")
        if not declarations:
            raise self._error("syntax", "module requires at least one function or constant")
        return syntax.Module(module, tuple(declarations))

    def _constant(self, start: _Token | None = None) -> syntax.Constant:
        token = self._expect("const")
        if self._current().kind == "name" and self.tokens[self.offset + 1].text == "=":
            raise self._error("syntax", "const requires an explicit type before its name")
        value_type = self._value_type()
        name = self._name()
        self._expect("=")
        value = self._expression(1)
        self._expect(";")
        return syntax.Constant(name, value_type, value, (token if start is None else start).site)

    def _function(self, name: syntax.Name, result: ValueType, is_const: bool) -> syntax.Function:
        self._expect("(")
        parameters: list[tuple[syntax.Name, ValueType]] = []
        const_parameters: set[str] = set()
        if not self._take(")"):
            while True:
                parameter_const = self._take("const")
                if self._current().text == "const":
                    raise self._error("syntax", "repeated const parameter qualifier")
                value_type = self._value_type()
                parameter = self._name()
                parameters.append((parameter, value_type))
                if parameter_const:
                    const_parameters.add(parameter.text)
                if self._take(")"):
                    break
                self._expect(",")
                if self._take(")"):
                    break
        arrow = self._current()
        if self._take("=>"):
            value = self._expression(1)
            self._expect(";")
            body = syntax.Block((), syntax.Return(value, arrow.site), value.site)
        else:
            body = self._block(1)
        return syntax.Function(name, result, tuple(parameters), body, is_const, frozenset(const_parameters))

    def _block(self, nesting: int) -> syntax.Block:
        self._expect("{")
        start = self._current()
        bindings: list[syntax.Binding | syntax.Reassignment | syntax.Constant] = []
        while (self._current().text in {"let", "const"}
               or (self._current().kind == "name" and self.tokens[self.offset + 1].text == "=")):
            if nesting + len(bindings) > MAX_BLOCK_DEPTH:
                raise self._error("limit", f"block or binding nesting exceeds {MAX_BLOCK_DEPTH}")
            if self._current().text == "const":
                bindings.append(self._constant())
                continue
            token = self._current()
            immutable = self._take("let")
            name = self._name()
            self._expect("=")
            value = self._expression(1)
            self._expect(";")
            constructor = syntax.Binding if immutable else syntax.Reassignment
            bindings.append(constructor(name, value, token.site))
        if nesting + len(bindings) > MAX_BLOCK_DEPTH:
            raise self._error("limit", f"block or binding nesting exceeds {MAX_BLOCK_DEPTH}")
        token = self._current()
        if self._take("return"):
            terminal: syntax.Return | syntax.Conditional = syntax.Return(self._expression(1), token.site)
            self._expect(";")
        elif self._take("if"):
            self._expect("(")
            condition = self._expression(1)
            self._expect(")")
            yes = self._block(nesting + len(bindings) + 1)
            self._expect("else")
            no = self._block(nesting + len(bindings) + 1)
            terminal = syntax.Conditional(condition, yes, no, token.site)
        else:
            raise self._error("syntax", "expected let, return or a returning if statement")
        self._expect("}")
        return syntax.Block(tuple(bindings), terminal, start.site)

    def _expression(self, nesting: int) -> syntax.Expression:
        if nesting > MAX_EXPRESSION_DEPTH:
            raise self._error("limit", f"expression nesting exceeds {MAX_EXPRESSION_DEPTH}")
        left = self._sum(nesting)
        token = self._current()
        if token.text in {"==", "<="}:
            self.offset += 1
            return syntax.expression("binary", token.text, token.site, (left, self._sum(nesting)))
        return left

    def _sum(self, nesting: int) -> syntax.Expression:
        left = self._product(nesting)
        while self._current().text == "+":
            token = self._expect("+")
            left = syntax.expression("binary", "+", token.site, (left, self._product(nesting)))
        return left

    def _product(self, nesting: int) -> syntax.Expression:
        left = self._atom(nesting)
        while self._current().text == "*":
            token = self._expect("*")
            left = syntax.expression("binary", "*", token.site, (left, self._atom(nesting)))
        return left

    def _atom(self, nesting: int) -> syntax.Expression:
        token = self._current()
        if self._take("("):
            result = self._expression(nesting + 1)
            self._expect(")")
            return syntax.expression("group", "", token.site, (result,))
        if token.kind == "decimal":
            self.offset += 1
            return syntax.expression("nat", token.text, token.site)
        if token.text in {"true", "false"}:
            self.offset += 1
            return syntax.expression("bool", token.text == "true", token.site)
        if token.kind != "name":
            raise self._error("syntax", f"expected expression, found {token.text!r}")
        name = self._name()
        if self._take("("):
            arguments: list[syntax.Expression] = []
            labels: list[syntax.Name | None] = []
            if not self._take(")"):
                while True:
                    label = None
                    if self._current().kind == "name" and self.tokens[self.offset + 1].text == ":":
                        label = self._name()
                        self._expect(":")
                    labels.append(label)
                    arguments.append(self._expression(nesting + 1))
                    if self._take(")"):
                        break
                    self._expect(",")
                    if self._take(")"):
                        break
            return syntax.expression("call", name.text, name.site, tuple(arguments), labels=tuple(labels))
        return syntax.expression("name", name.text, name.site)


def _error(kind: str, message: str, site: syntax.Site) -> VelaError:
    return VelaError(kind, site.line, site.column, message)


class _Elaborator:
    """Resolve and type located syntax, emitting only the established pure terms."""

    def __init__(self, facts: Facts | None = None) -> None:
        self.functions: dict[str, _Signature] = {}
        self.constants: dict[str, _Local] = {}
        self.static_work = MAX_STATIC_WORK
        self.specialization_depth = 0
        self.fresh_argument = 0
        self.facts = facts

    def _declare(self, name: syntax.Name, kind: SymbolKind, detail: str) -> int | None:
        return None if self.facts is None else self.facts.declare(name, kind, detail)

    def _reference(self, identity: int | None, site: syntax.Site) -> None:
        if self.facts is not None:
            if identity is None:
                raise RuntimeError("pure inspection is missing a resolved declaration identity")
            self.facts.reference(identity, site)

    def _bounded(self, value_type: ValueType, gallina: str,
                 children: tuple[_Expression, ...], site: syntax.Site) -> _Expression:
        depth = max((child.depth for child in children), default=0) + 1
        if depth > MAX_EXPRESSION_DEPTH:
            raise _error("limit", f"expression exceeds depth {MAX_EXPRESSION_DEPTH}", site)
        return _Expression(value_type, gallina, depth)

    def function(self, function: syntax.Function) -> str:
        name = function.name
        if name.text in self.functions or name.text in self.constants:
            raise _error("name", f"duplicate function '{name.text}'", name.site)
        parameters = ", ".join(f"{'const ' if parameter.text in function.const_parameters else ''}{value_type} {parameter.text}"
                               for parameter, value_type in function.parameters)
        identity = self._declare(name, "function",
                                 f"public {'const ' if function.is_const else ''}{function.result} {name.text}({parameters})")
        environment: dict[str, _Local] = {}
        parameter_facts: list[tuple[syntax.Name, ValueType, int | None]] = []
        for parameter, value_type in function.parameters:
            if parameter.text in environment:
                raise _error("name", f"duplicate parameter '{parameter.text}'", parameter.site)
            required_static = parameter.text in function.const_parameters
            symbol = self._declare(parameter, "parameter",
                                   f"{'const ' if required_static else ''}{parameter.text}: {value_type}")
            environment[parameter.text] = _Local(value_type, symbol, required_static=required_static)
            parameter_facts.append((parameter, value_type, symbol))
        body = self._block(function.body, environment, 1)
        if body.value_type != function.result:
            raise _error("type", f"function '{name.text}' returns {body.value_type}, "
                         f"expected {function.result}", function.body.site)
        self.functions[name.text] = _Signature(tuple(parameter_facts),
                                               function.result, identity, function, dict(self.constants))
        binders = "".join(f" (v_{parameter.text} : {_TYPES[value_type]})"
                          for parameter, value_type in function.parameters)
        return f"Definition f_{name.text}{binders} : {_TYPES[function.result]} :=\n  {body.gallina}."

    def _static_tick(self, site: syntax.Site, depth: int = 0) -> None:
        self.static_work -= 1
        if self.static_work < 0 or depth > MAX_STATIC_DEPTH:
            raise _error("limit", "constant evaluation work or nesting budget exhausted", site)

    def _literal(self, value: _Static) -> str:
        if value.value_type == "bool":
            return _TRUE if value.value else _FALSE
        return f"({value.value} : {_TYPES['Nat']})"

    def _require_static(self, expression: syntax.Expression, environment: dict[str, _Local]) -> None:
        pending = [expression]
        while pending:
            current = pending.pop()
            self._static_tick(current.site)
            if current.kind == "name":
                name = cast("str", current.value)
                local = environment.get(name, self.constants.get(name))
                if local is not None and local.static is None and not local.required_static:
                    raise _error("unsupported", f"constant initializer depends on runtime binding '{name}'; "
                                 "only earlier constants and static pure-call arguments are permitted", current.site)
            pending.extend(reversed(current.children))

    def _static_value(self, expression: syntax.Expression, environment: dict[str, _Local]) -> _Static | None:
        """Evaluate closed static inputs; retain symbolic static binders until specialization."""
        pending = [expression]
        while pending:
            current = pending.pop()
            self._static_tick(current.site)
            if current.kind == "name":
                local = environment.get(cast("str", current.value), self.constants.get(cast("str", current.value)))
                if local is not None and local.static is None:
                    return None
            pending.extend(current.children)
        available = {name: local.static for name, local in {**self.constants, **environment}.items()
                     if local.static is not None}
        return self._evaluate(expression, available)

    def _constant(self, declaration: syntax.Constant, environment: dict[str, _Local]) -> _Local:
        checked = self._expression(declaration.value, environment)
        if checked.value_type != declaration.value_type:
            raise _error("type", f"constant '{declaration.name.text}' must be {declaration.value_type}, "
                         f"got {checked.value_type}", declaration.name.site)
        self._require_static(declaration.value, environment)
        value = self._static_value(declaration.value, environment)
        detail = f"const {declaration.value_type} {declaration.name.text}"
        if value is not None:
            spelling = ("true" if value.value else "false") if value.value_type == "bool" else str(value.value)
            detail += f" = {spelling}"
        symbol = self._declare(declaration.name, "constant", detail)
        return _Local(declaration.value_type, symbol, value, True,
                      initializer=checked if value is None else _Expression(value.value_type, self._literal(value)))

    def constant(self, declaration: syntax.Constant) -> str:
        name = declaration.name
        if name.text in self.constants or name.text in self.functions:
            raise _error("name", f"duplicate declaration '{name.text}'", name.site)
        local = self._constant(declaration, {})
        self.constants[name.text] = local
        if local.static is None:
            raise RuntimeError("constant declaration lost its static value")
        return f"Definition c_{name.text} : {_TYPES[local.value_type]} :=\n  {self._literal(local.static)}."

    def _evaluate(self, expression: syntax.Expression, environment: dict[str, _Static], depth: int = 0) -> _Static:
        self._static_tick(expression.site, depth)
        kind, name = expression.kind, cast("str", expression.value)
        if kind == "nat":
            return _Static("Nat", int(name.replace("_", "")))
        if kind == "bool":
            return _Static("bool", cast("bool", expression.value))
        if kind == "name":
            value = environment.get(name)
            if value is None:
                raise _error("unsupported", f"constant initializer has no static value for '{name}'", expression.site)
            return value
        if kind == "group":
            return self._evaluate(expression.children[0], environment, depth + 1)
        arguments = tuple(self._evaluate(child, environment, depth + 1) for child in expression.children)
        if kind == "call":
            signature = self.functions[name]
            inputs = {parameter.text: value for (parameter, _, _), value in zip(signature.parameters, arguments, strict=True)}
            captured = {label: local.static for label, local in signature.constants.items() if local.static is not None}
            return self._evaluate_block(signature.source.body, {**captured, **inputs}, depth + 1)
        left, right = arguments
        if name == "==":
            return _Static("bool", left.value == right.value)
        first, second = left.value, right.value
        if name == "<=":
            return _Static("bool", first <= second)
        if ((name == "+" and first > MAX_STATIC_NAT - second)
                or (name == "*" and first != 0 and second > MAX_STATIC_NAT // first)):
            raise _error("limit", f"constant result exceeds {MAX_LITERAL_DIGITS} decimal digits", expression.site)
        return _Static("Nat", first + second if name == "+" else first * second)

    def _evaluate_block(self, block: syntax.Block, environment: dict[str, _Static], depth: int) -> _Static:
        self._static_tick(block.site, depth)
        extended = dict(environment)
        for binding in block.bindings:
            if isinstance(binding, syntax.Reassignment):
                raise _error("unsupported", "constant evaluation does not admit reassignment", binding.site)
            value = self._evaluate(binding.value, extended, depth + 1)
            extended[binding.name.text] = value
        terminal = block.terminal
        if isinstance(terminal, syntax.Return):
            return self._evaluate(terminal.value, extended, depth + 1)
        condition = self._evaluate(terminal.condition, extended, depth + 1)
        return self._evaluate_block(terminal.yes if condition.value else terminal.no, extended, depth + 1)

    def _block(self, block: syntax.Block, environment: dict[str, _Local], nesting: int) -> _Expression:
        if nesting + len(block.bindings) > MAX_BLOCK_DEPTH:
            raise _error("limit", f"block or binding nesting exceeds {MAX_BLOCK_DEPTH}", block.site)
        extended = dict(environment)
        values: list[tuple[syntax.Binding | syntax.Constant, _Expression]] = []
        for binding in block.bindings:
            if isinstance(binding, syntax.Reassignment):
                selected = extended.get(binding.name.text, self.constants.get(binding.name.text))
                if selected is None:
                    raise _error("name", f"unbound assignment target '{binding.name.text}'", binding.name.site)
                mode = "const" if selected.static is not None or selected.required_static else "immutable binding"
                raise _error("unsupported", f"cannot reassign {mode} '{binding.name.text}'; "
                             "let and unmarked type-first bindings are immutable. Declare var for local "
                             "reassignment in the wider Vela surface; the pure prototype does not support mutation",
                             binding.name.site)
            if binding.name.text in extended:
                raise _error("name", f"duplicate local binding '{binding.name.text}'", binding.name.site)
            if isinstance(binding, syntax.Constant):
                local = self._constant(binding, extended)
                extended[binding.name.text] = local
                if local.initializer is None:
                    raise RuntimeError("local constant lost its checked expression")
                values.append((binding, local.initializer))
                continue
            value = self._expression(binding.value, extended)
            symbol = self._declare(binding.name, "variable", f"{binding.name.text}: {value.value_type}")
            extended[binding.name.text] = _Local(value.value_type, symbol)
            values.append((binding, value))
        terminal = block.terminal
        if isinstance(terminal, syntax.Return):
            body = self._expression(terminal.value, extended)
        else:
            condition = self._expression(terminal.condition, extended)
            if condition.value_type != "bool":
                raise _error("type", "if condition must be bool", terminal.site)
            yes = self._block(terminal.yes, extended, nesting + len(values) + 1)
            no = self._block(terminal.no, extended, nesting + len(values) + 1)
            if yes.value_type != no.value_type:
                raise _error("type", "if branches must have the same type", terminal.site)
            body = self._bounded(yes.value_type,
                                 f"(if {condition.gallina} then {yes.gallina} else {no.gallina})",
                                 (condition, yes, no), terminal.site)
        for binding, value in reversed(values):
            body = self._bounded(body.value_type,
                                 f"(let v_{binding.name.text} := {value.gallina} in {body.gallina})",
                                 (value, body), binding.site)
        return body

    def _expression(self, expression: syntax.Expression,
                    environment: dict[str, _Local]) -> _Expression:
        kind, value, site = expression.kind, expression.value, expression.site
        if kind == "nat":
            return _Expression("Nat", f"({int(cast('str', value).replace('_', ''))} : {_TYPES['Nat']})")
        if kind == "bool":
            return _Expression("bool", _TRUE if value else _FALSE)
        if kind == "group":
            return self._expression(expression.children[0], environment)
        name = cast("str", value)
        if kind == "name":
            local = environment.get(name, self.constants.get(name))
            if local is None:
                raise _error("name", f"unbound value '{name}'", site)
            self._reference(local.symbol, site)
            return _Expression(local.value_type, local.gallina if local.gallina is not None
                               else f"v_{name}" if name in environment else f"c_{name}")
        arguments = tuple(self._expression(child, environment) for child in expression.children)
        if kind == "call":
            signature = self.functions.get(name)
            if signature is None:
                local = environment.get(name, self.constants.get(name))
                if local is not None and (local.static is not None or local.required_static):
                    raise _error("type", f"constant '{name}' is a value and cannot be called", site)
                raise _error("name", f"unknown or forward function '{name}'; "
                             "only earlier declarations are callable", site)
            if len(arguments) != len(signature.parameters):
                raise _error("type", f"function '{name}' expects {len(signature.parameters)} arguments, "
                             f"got {len(arguments)}", site)
            labeled = False
            for index, (argument, (parameter, expected, symbol), label) in enumerate(
                    zip(arguments, signature.parameters, expression.labels, strict=True), start=1):
                if label is None:
                    if labeled:
                        raise _error("name", "positional arguments cannot follow a named argument", expression.children[index - 1].site)
                else:
                    labeled = True
                    if label.text != parameter.text:
                        raise _error("name", f"argument {index} to '{name}' must name parameter '{parameter.text}', "
                                     f"got '{label.text}'", label.site)
                    self._reference(symbol, label.site)
                if argument.value_type != expected:
                    raise _error("type", f"argument {index} to '{name}' must be {expected}, "
                                 f"got {argument.value_type}", site)
                if parameter.text in signature.source.const_parameters:
                    self._require_static(expression.children[index - 1], environment)
            self._reference(signature.symbol, site)
            if signature.source.const_parameters:
                static_arguments = {parameter.text: self._static_value(source, environment)
                                    for (parameter, _, _), source in zip(signature.parameters, expression.children, strict=True)
                                    if parameter.text in signature.source.const_parameters}
                closed_arguments = {name: value for name, value in static_arguments.items() if value is not None}
                if len(closed_arguments) == len(static_arguments):
                    return self._specialize(signature, arguments, closed_arguments, site)
            term = f"f_{name}"
            if arguments:
                term = "(" + term + " " + " ".join(argument.gallina for argument in arguments) + ")"
            return self._bounded(signature.result, term, arguments, site)
        left, right = arguments
        if name in {"+", "*"}:
            if left.value_type != "Nat" or right.value_type != "Nat":
                raise _error("type", f"'{name}' operands must be Nat", site)
            operation = "add" if name == "+" else "mul"
            return self._bounded("Nat", f"(Corelib.Init.Nat.{operation} {left.gallina} {right.gallina})", arguments, site)
        if left.value_type != right.value_type:
            raise _error("type", f"'{name}' operands must have the same type", site)
        if name == "<=":
            if left.value_type != "Nat":
                raise _error("type", "'<=' operands must be Nat", site)
            term = f"(Corelib.Init.Nat.leb {left.gallina} {right.gallina})"
        elif left.value_type == "Nat":
            term = f"(Corelib.Init.Nat.eqb {left.gallina} {right.gallina})"
        else:
            # User locals start with v_; these fresh binders evaluate operands once.
            term = (f"(let vela_eq_left := {left.gallina} in "
                    f"let vela_eq_right := {right.gallina} in "
                    "if vela_eq_left then vela_eq_right else "
                    f"(if vela_eq_right then {_FALSE} else {_TRUE}))")
        return self._bounded("bool", term, arguments, site)

    def _specialize(self, signature: _Signature, arguments: tuple[_Expression, ...],
                    static_arguments: dict[str, _Static], site: syntax.Site) -> _Expression:
        """Instantiate static binders while evaluating each runtime argument exactly once."""
        self.specialization_depth += 1
        previous_facts = self.facts
        self.facts = None
        try:
            self._static_tick(site, self.specialization_depth)
            environment = {name: _Local(local.value_type, None, local.static, local.required_static,
                                        f"c_{name}") for name, local in signature.constants.items()}
            bindings: list[tuple[str, _Expression]] = []
            for (parameter, value_type, _), argument in zip(signature.parameters, arguments, strict=True):
                value = static_arguments.get(parameter.text)
                if value is not None:
                    environment[parameter.text] = _Local(value_type, None, value, True, self._literal(value))
                else:
                    fresh = f"vela_arg_{self.fresh_argument}"
                    self.fresh_argument += 1
                    bindings.append((fresh, argument))
                    environment[parameter.text] = _Local(value_type, None, gallina=fresh)
            body = self._block(signature.source.body, environment, 1)
            for fresh, argument in reversed(bindings):
                body = self._bounded(body.value_type, f"(let {fresh} := {argument.gallina} in {body.gallina})",
                                     (argument, body), site)
            return body
        finally:
            self.facts = previous_facts
            self.specialization_depth -= 1


def _translate(source: bytes, module: syntax.Module, facts: Facts | None = None) -> Translation:
    elaborator = _Elaborator(facts)
    definitions = [elaborator.constant(declaration) if isinstance(declaration, syntax.Constant)
                   else elaborator.function(declaration) for declaration in module.declarations]
    name = module.name.text
    header = ("(* SPDX-License-Identifier: Apache-2.0 *)\n"
              f"(* Vela pure prototype: unqualified. Source SHA256: {hashlib.sha256(source).hexdigest()} *)\n"
              "From Corelib Require Import Init.Datatypes Init.Nat.\n\n"
              f"Module Vela_{name}.\n\n")
    gallina = header + "\n\n".join(definitions) + f"\n\nEnd Vela_{name}.\n"
    if len(gallina.encode()) > MAX_OUTPUT_BYTES:
        raise _error("limit", "pure translation exceeds its output byte budget", module.name.site)
    return Translation(name, gallina)


def translate(source: bytes) -> Translation:
    """Validate the complete bounded source through the retained Python syntax route."""
    return _translate(source, _Parser(_tokens(source)).parse())


def inspect_source(source: bytes) -> dict[str, object]:
    """Return diagnostic resolution facts only after a complete successful pure check."""
    module = _Parser(_tokens(source)).parse()
    facts = Facts()
    _translate(source, module, facts)
    return facts.result()


def translate_ast(source: bytes, response: object) -> Translation:
    """Decode native located syntax and use the common checker/emitter, with no fallback."""
    return _translate(source, syntax.decode(source, response))
