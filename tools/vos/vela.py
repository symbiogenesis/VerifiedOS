# SPDX-License-Identifier: Apache-2.0
"""Untrusted translation of the pure Vela prototype into existing CIC terms.

The emitted definitions are this fragment's interpretation. This module provides
no source evaluator, semantic correspondence proof or kernel-acceptance verdict.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

MAX_SOURCE_BYTES = 65_536
MAX_EXPRESSION_DEPTH = 64
MAX_BLOCK_DEPTH = 64
MAX_LITERAL_DIGITS = 256

type ValueType = Literal["Nat", "bool"]

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DECIMAL = re.compile(r"[0-9]+")
_KEYWORDS = frozenset({"module", "public", "return", "let", "if", "else", "Nat", "bool",
                       "true", "false"})
_UNSUPPORTED = frozenset({"fn", "Bool", "async", "await", "effect", "effects", "handler",
                          "handle", "resume", "dispose", "mut", "var", "unsafe", "borrow",
                          "requires", "ensures", "restores", "ghost", "tracked", "grade",
                          "proof", "owned", "move", "ref", "in", "captures", "scope",
                          "spawn", "commit", "on", "cancel", "region", "view", "union"})
_TYPES: dict[ValueType, str] = {
    "Nat": "Corelib.Init.Datatypes.nat",
    "bool": "Corelib.Init.Datatypes.bool",
}
_TRUE = "Corelib.Init.Datatypes.true"
_FALSE = "Corelib.Init.Datatypes.false"


class VelaError(Exception):
    """One bounded diagnostic; callers supply the source file's display name."""

    def __init__(self, kind: str, line: int, column: int, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.line = line
        self.column = column
        self.message = message


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


@dataclass(frozen=True)
class _Expression:
    value_type: ValueType
    gallina: str
    depth: int = 1


@dataclass(frozen=True)
class _Signature:
    parameters: tuple[ValueType, ...]
    result: ValueType


def _position(prefix: str) -> tuple[int, int]:
    normalized = prefix.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.count("\n") + 1, len(normalized.rsplit("\n", 1)[-1]) + 1


def _tokens(source: bytes) -> list[_Token]:
    if len(source) > MAX_SOURCE_BYTES:
        raise VelaError("limit", 1, 1, f"source exceeds {MAX_SOURCE_BYTES} bytes")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as error:
        line, column = _position(source[:error.start].decode("utf-8"))
        raise VelaError("encoding", line, column, "source is not valid UTF-8") from error
    text = text.replace("\r\n", "\n").replace("\r", "\n")
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
        if match := _IDENTIFIER.match(text, offset):
            spelling = match.group()
            if spelling in _UNSUPPORTED:
                raise VelaError("unsupported", line, column,
                                f"'{spelling}' is outside the pure prototype")
            kind = "keyword" if spelling in _KEYWORDS else "name"
        elif match := _DECIMAL.match(text, offset):
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
    def __init__(self, tokens: list[_Token]) -> None:
        self.tokens = tokens
        self.offset = 0
        self.functions: dict[str, _Signature] = {}

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

    def _name(self) -> _Token:
        token = self._current()
        if token.kind != "name":
            raise self._error("syntax", f"expected identifier, found {token.text!r}")
        self.offset += 1
        return token

    def _value_type(self) -> ValueType:
        token = self._current()
        if token.text == "Nat":
            self.offset += 1
            return "Nat"
        if token.text == "bool":
            self.offset += 1
            return "bool"
        raise self._error("unsupported", f"type {token.text!r} is outside Nat and bool")

    def _bounded(self, value_type: ValueType, gallina: str,
                 children: tuple[_Expression, ...], token: _Token) -> _Expression:
        depth = max((child.depth for child in children), default=0) + 1
        if depth > MAX_EXPRESSION_DEPTH:
            raise self._error("limit", f"expression exceeds depth {MAX_EXPRESSION_DEPTH}", token)
        return _Expression(value_type, gallina, depth)

    def parse(self) -> tuple[str, list[str]]:
        self._expect("module")
        module = self._name().text
        self._expect(";")
        definitions: list[str] = []
        while self._current().kind != "eof":
            definitions.append(self._function())
        if not definitions:
            raise self._error("syntax", "module requires at least one function")
        return module, definitions

    def _function(self) -> str:
        self._expect("public")
        result_type = self._value_type()
        name = self._name()
        if name.text in self.functions:
            raise self._error("name", f"duplicate function '{name.text}'", name)
        self._expect("(")
        environment: dict[str, ValueType] = {}
        parameters: list[tuple[str, ValueType]] = []
        if not self._take(")"):
            while True:
                value_type = self._value_type()
                parameter = self._name()
                if parameter.text in environment:
                    raise self._error("name", f"duplicate parameter '{parameter.text}'", parameter)
                parameters.append((parameter.text, value_type))
                environment[parameter.text] = value_type
                if self._take(")"):
                    break
                self._expect(",")
        self._expect("{")
        body_start = self._current()
        body = self._statements(environment, 1)
        self._expect("}")
        if body.value_type != result_type:
            raise self._error("type", f"function '{name.text}' returns {body.value_type}, "
                              f"expected {result_type}", body_start)
        self.functions[name.text] = _Signature(tuple(item[1] for item in parameters), result_type)
        binders = "".join(f" (v_{parameter} : {_TYPES[value_type]})"
                          for parameter, value_type in parameters)
        return f"Definition f_{name.text}{binders} : {_TYPES[result_type]} :=\n  {body.gallina}."

    def _block(self, environment: dict[str, ValueType], nesting: int) -> _Expression:
        self._expect("{")
        body = self._statements(environment, nesting)
        self._expect("}")
        return body

    def _statements(self, environment: dict[str, ValueType], nesting: int) -> _Expression:
        """A bounded binding sequence ending in an explicit return on every path."""
        token = self._current()
        if nesting > MAX_BLOCK_DEPTH:
            raise self._error("limit", f"block or binding nesting exceeds {MAX_BLOCK_DEPTH}")
        if self._take("let"):
            name = self._name()
            if name.text in environment:
                raise self._error("name", f"duplicate local binding '{name.text}'", name)
            self._expect("=")
            value = self._expression(environment, 1)
            self._expect(";")
            extended = {**environment, name.text: value.value_type}
            body = self._statements(extended, nesting + 1)
            return self._bounded(body.value_type,
                                 f"(let v_{name.text} := {value.gallina} in {body.gallina})",
                                 (value, body), token)
        if self._take("if"):
            self._expect("(")
            condition = self._expression(environment, 1)
            self._expect(")")
            if condition.value_type != "bool":
                raise self._error("type", "if condition must be bool", token)
            yes = self._block(environment, nesting + 1)
            self._expect("else")
            no = self._block(environment, nesting + 1)
            if yes.value_type != no.value_type:
                raise self._error("type", "if branches must have the same type", token)
            return self._bounded(yes.value_type,
                                 f"(if {condition.gallina} then {yes.gallina} else {no.gallina})",
                                 (condition, yes, no), token)
        if self._take("return"):
            value = self._expression(environment, 1)
            self._expect(";")
            return value
        raise self._error("syntax", "expected let, return or a returning if statement")

    def _expression(self, environment: dict[str, ValueType], nesting: int) -> _Expression:
        if nesting > MAX_EXPRESSION_DEPTH:
            raise self._error("limit", f"expression nesting exceeds {MAX_EXPRESSION_DEPTH}")
        left = self._sum(environment, nesting)
        token = self._current()
        if token.text in {"==", "<="}:
            self.offset += 1
            right = self._sum(environment, nesting)
            if left.value_type != right.value_type:
                raise self._error("type", f"'{token.text}' operands must have the same type", token)
            if token.text == "<=":
                if left.value_type != "Nat":
                    raise self._error("type", "'<=' operands must be Nat", token)
                term = f"(Corelib.Init.Nat.leb {left.gallina} {right.gallina})"
            elif left.value_type == "Nat":
                term = f"(Corelib.Init.Nat.eqb {left.gallina} {right.gallina})"
            else:
                # Bind both operands once: duplicating emitted right operands
                # would make nested equality expand exponentially on the host.
                # User locals always start with v_, so these binders are fresh.
                term = (f"(let vela_eq_left := {left.gallina} in "
                        f"let vela_eq_right := {right.gallina} in "
                        "if vela_eq_left then vela_eq_right else "
                        f"(if vela_eq_right then {_FALSE} else {_TRUE}))")
            return self._bounded("bool", term, (left, right), token)
        return left

    def _sum(self, environment: dict[str, ValueType], nesting: int) -> _Expression:
        left = self._product(environment, nesting)
        while self._current().text == "+":
            token = self._current()
            self.offset += 1
            left = self._arithmetic(left, self._product(environment, nesting), "add", token)
        return left

    def _product(self, environment: dict[str, ValueType], nesting: int) -> _Expression:
        left = self._atom(environment, nesting)
        while self._current().text == "*":
            token = self._current()
            self.offset += 1
            left = self._arithmetic(left, self._atom(environment, nesting), "mul", token)
        return left

    def _arithmetic(self, left: _Expression, right: _Expression,
                    operation: str, token: _Token) -> _Expression:
        if left.value_type != "Nat" or right.value_type != "Nat":
            raise self._error("type", f"'{token.text}' operands must be Nat", token)
        return self._bounded("Nat", f"(Corelib.Init.Nat.{operation} {left.gallina} {right.gallina})",
                             (left, right), token)

    def _atom(self, environment: dict[str, ValueType], nesting: int) -> _Expression:
        token = self._current()
        if self._take("("):
            result = self._expression(environment, nesting + 1)
            self._expect(")")
            return result
        if token.kind == "decimal":
            self.offset += 1
            return _Expression("Nat", f"({int(token.text)} : {_TYPES['Nat']})")
        if token.text in {"true", "false"}:
            self.offset += 1
            return _Expression("bool", _TRUE if token.text == "true" else _FALSE)
        if token.kind != "name":
            raise self._error("syntax", f"expected expression, found {token.text!r}")
        self.offset += 1
        if self._take("("):
            arguments: list[_Expression] = []
            if not self._take(")"):
                while True:
                    arguments.append(self._expression(environment, nesting + 1))
                    if self._take(")"):
                        break
                    self._expect(",")
            signature = self.functions.get(token.text)
            if signature is None:
                raise self._error("name", f"unknown or forward function '{token.text}'; "
                                  "only earlier declarations are callable", token)
            if len(arguments) != len(signature.parameters):
                raise self._error("type", f"function '{token.text}' expects "
                                  f"{len(signature.parameters)} arguments, got {len(arguments)}", token)
            for index, (argument, expected) in enumerate(
                    zip(arguments, signature.parameters, strict=True), start=1):
                if argument.value_type != expected:
                    raise self._error("type", f"argument {index} to '{token.text}' must be {expected}, "
                                      f"got {argument.value_type}", token)
            term = f"f_{token.text}"
            if arguments:
                term = "(" + term + " " + " ".join(argument.gallina for argument in arguments) + ")"
            return self._bounded(signature.result, term, tuple(arguments), token)
        value_type = environment.get(token.text)
        if value_type is None:
            raise self._error("name", f"unbound value '{token.text}'", token)
        return _Expression(value_type, f"v_{token.text}")


def translate(source: bytes) -> Translation:
    """Validate the complete bounded source before returning any generated text."""
    module, definitions = _Parser(_tokens(source)).parse()
    header = ("(* SPDX-License-Identifier: Apache-2.0 *)\n"
              f"(* Vela pure prototype: unqualified. Source SHA256: {hashlib.sha256(source).hexdigest()} *)\n"
              "From Corelib Require Import Init.Datatypes Init.Nat.\n\n"
              f"Module Vela_{module}.\n\n")
    return Translation(module, header + "\n\n".join(definitions) + f"\n\nEnd Vela_{module}.\n")
