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

__all__ = ["MAX_BLOCK_DEPTH", "MAX_EXPRESSION_DEPTH", "MAX_LITERAL_DIGITS", "MAX_SOURCE_BYTES",
           "Translation", "ValueType", "VelaError", "translate", "translate_ast"]

_TYPES: dict[ValueType, str] = {
    "Nat": "Corelib.Init.Datatypes.nat",
    "bool": "Corelib.Init.Datatypes.bool",
}
_TRUE = "Corelib.Init.Datatypes.true"
_FALSE = "Corelib.Init.Datatypes.false"


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
    parameters: tuple[ValueType, ...]
    result: ValueType


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
                raise VelaError("unsupported", line, column,
                                f"'{spelling}' is outside the pure prototype")
            kind = "keyword" if spelling in syntax.KEYWORDS else "name"
        elif match := syntax.DECIMAL.match(text, offset):
            spelling = match.group()
            if len(spelling) > MAX_LITERAL_DIGITS:
                raise VelaError("limit", line, column,
                                f"literal exceeds {MAX_LITERAL_DIGITS} decimal digits")
            kind = "decimal"
        elif text[offset:offset + 2] in {"->", "==", "<="}:
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
        raise self._error("unsupported", f"type {token.text!r} is outside Nat and bool")

    def parse(self) -> syntax.Module:
        self._expect("module")
        module = self._name()
        self._expect(";")
        functions: list[syntax.Function] = []
        while self._current().kind != "eof":
            functions.append(self._function())
        if not functions:
            raise self._error("syntax", "module requires at least one function")
        return syntax.Module(module, tuple(functions))

    def _function(self) -> syntax.Function:
        self._expect("public")
        result = self._value_type()
        name = self._name()
        self._expect("(")
        parameters: list[tuple[syntax.Name, ValueType]] = []
        if not self._take(")"):
            while True:
                value_type = self._value_type()
                parameters.append((self._name(), value_type))
                if self._take(")"):
                    break
                self._expect(",")
        return syntax.Function(name, result, tuple(parameters), self._block(1))

    def _block(self, nesting: int) -> syntax.Block:
        self._expect("{")
        start = self._current()
        bindings: list[syntax.Binding] = []
        while self._current().text == "let":
            if nesting + len(bindings) > MAX_BLOCK_DEPTH:
                raise self._error("limit", f"block or binding nesting exceeds {MAX_BLOCK_DEPTH}")
            token = self._expect("let")
            name = self._name()
            self._expect("=")
            value = self._expression(1)
            self._expect(";")
            bindings.append(syntax.Binding(name, value, token.site))
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
            if not self._take(")"):
                while True:
                    arguments.append(self._expression(nesting + 1))
                    if self._take(")"):
                        break
                    self._expect(",")
            return syntax.expression("call", name.text, name.site, tuple(arguments))
        return syntax.expression("name", name.text, name.site)


def _error(kind: str, message: str, site: syntax.Site) -> VelaError:
    return VelaError(kind, site.line, site.column, message)


class _Elaborator:
    """Resolve and type located syntax, emitting only the established pure terms."""

    def __init__(self) -> None:
        self.functions: dict[str, _Signature] = {}

    def _bounded(self, value_type: ValueType, gallina: str,
                 children: tuple[_Expression, ...], site: syntax.Site) -> _Expression:
        depth = max((child.depth for child in children), default=0) + 1
        if depth > MAX_EXPRESSION_DEPTH:
            raise _error("limit", f"expression exceeds depth {MAX_EXPRESSION_DEPTH}", site)
        return _Expression(value_type, gallina, depth)

    def function(self, function: syntax.Function) -> str:
        name = function.name
        if name.text in self.functions:
            raise _error("name", f"duplicate function '{name.text}'", name.site)
        environment: dict[str, ValueType] = {}
        for parameter, value_type in function.parameters:
            if parameter.text in environment:
                raise _error("name", f"duplicate parameter '{parameter.text}'", parameter.site)
            environment[parameter.text] = value_type
        body = self._block(function.body, environment, 1)
        if body.value_type != function.result:
            raise _error("type", f"function '{name.text}' returns {body.value_type}, "
                         f"expected {function.result}", function.body.site)
        self.functions[name.text] = _Signature(tuple(value for _, value in function.parameters), function.result)
        binders = "".join(f" (v_{parameter.text} : {_TYPES[value_type]})"
                          for parameter, value_type in function.parameters)
        return f"Definition f_{name.text}{binders} : {_TYPES[function.result]} :=\n  {body.gallina}."

    def _block(self, block: syntax.Block, environment: dict[str, ValueType], nesting: int) -> _Expression:
        if nesting + len(block.bindings) > MAX_BLOCK_DEPTH:
            raise _error("limit", f"block or binding nesting exceeds {MAX_BLOCK_DEPTH}", block.site)
        extended = dict(environment)
        values: list[tuple[syntax.Binding, _Expression]] = []
        for binding in block.bindings:
            if binding.name.text in extended:
                raise _error("name", f"duplicate local binding '{binding.name.text}'", binding.name.site)
            value = self._expression(binding.value, extended)
            extended[binding.name.text] = value.value_type
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
                    environment: dict[str, ValueType]) -> _Expression:
        kind, value, site = expression.kind, expression.value, expression.site
        if kind == "nat":
            return _Expression("Nat", f"({int(cast('str', value))} : {_TYPES['Nat']})")
        if kind == "bool":
            return _Expression("bool", _TRUE if value else _FALSE)
        if kind == "group":
            return self._expression(expression.children[0], environment)
        name = cast("str", value)
        if kind == "name":
            value_type = environment.get(name)
            if value_type is None:
                raise _error("name", f"unbound value '{name}'", site)
            return _Expression(value_type, f"v_{name}")
        arguments = tuple(self._expression(child, environment) for child in expression.children)
        if kind == "call":
            signature = self.functions.get(name)
            if signature is None:
                raise _error("name", f"unknown or forward function '{name}'; "
                             "only earlier declarations are callable", site)
            if len(arguments) != len(signature.parameters):
                raise _error("type", f"function '{name}' expects {len(signature.parameters)} arguments, "
                             f"got {len(arguments)}", site)
            for index, (argument, expected) in enumerate(zip(arguments, signature.parameters, strict=True), start=1):
                if argument.value_type != expected:
                    raise _error("type", f"argument {index} to '{name}' must be {expected}, "
                                 f"got {argument.value_type}", site)
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


def _translate(source: bytes, module: syntax.Module) -> Translation:
    elaborator = _Elaborator()
    definitions = [elaborator.function(function) for function in module.functions]
    name = module.name.text
    header = ("(* SPDX-License-Identifier: Apache-2.0 *)\n"
              f"(* Vela pure prototype: unqualified. Source SHA256: {hashlib.sha256(source).hexdigest()} *)\n"
              "From Corelib Require Import Init.Datatypes Init.Nat.\n\n"
              f"Module Vela_{name}.\n\n")
    return Translation(name, header + "\n\n".join(definitions) + f"\n\nEnd Vela_{name}.\n")


def translate(source: bytes) -> Translation:
    """Validate the complete bounded source through the retained Python syntax route."""
    return _translate(source, _Parser(_tokens(source)).parse())


def translate_ast(source: bytes, response: object) -> Translation:
    """Decode native located syntax and use the common checker/emitter, with no fallback."""
    return _translate(source, syntax.decode(source, response))
