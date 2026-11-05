# SPDX-License-Identifier: Apache-2.0
"""Bounded, untrusted elaboration of mathematical Vela into existing CIC terms.

The surface parser owns syntax. This consumer checks its exact-source protocol,
then proposes terms for independent kernel checking; it supplies neither checked
parsing nor an independent source semantics. Vec is a recursive product family,
Fin an indexed inductive, and lookup recurses structurally on the finite index.
"""

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from vos.vela import StaticEvaluation
from vos.vela_ast import (
    DECIMAL,
    MAX_LITERAL_DIGITS,
    MAX_SOURCE_BYTES,
    ValueType,
    VelaError,
    source_text,
    trivia_end,
)

MAX_DEPTH = 128
MAX_WORK = 200_000
MAX_REDUCTIONS = 20_000
MAX_OUTPUT_BYTES = 1_048_576
MAX_UNIVERSE = 8
MAX_NAT_BITS = 4096
MAX_CONSTANT_NAT = 10 ** MAX_LITERAL_DIGITS - 1
MAX_PATTERN_NAT = 64


@dataclass(frozen=True)
class Elaboration:
    module: str
    gallina: str


type Node = dict[str, object]

_FIELDS: dict[str, set[str]] = {
    "surface_file": {"name", "declarations"},
    "alias": {"name", "generics", "contracts", "type", "modifiers"},
    "constant": {"name", "type", "value", "modifiers"},
    "constant_local": {"name", "type", "value"},
    "definition": {"name", "result", "generics", "parameters", "contracts", "value", "modifiers"},
    "function": {"name", "result", "generics", "parameters", "contracts", "body", "cancel", "modifiers"},
    "theorem": {"name", "generics", "parameters", "proposition", "body", "modifiers"},
    "lemma": {"name", "generics", "parameters", "proposition", "body", "modifiers"},
    "generic_parameter": {"name", "mode", "type"},
    "parameter": {"name", "type", "grade"},
    "lambda_parameter": {"name", "type", "grade"},
    "type": {"name", "arguments"},
    "function_type": {"mode", "generics", "parameters", "result", "captures", "effects", "contracts"},
    "group_type": {"type"}, "computed_type": {"value"}, "type_argument": {"type"},
    "tuple_type": {"types"},
    "name": {"name"}, "nat": {"value", "suffix"}, "bool": {"value"},
    "unit": set(), "tuple": {"values"}, "group": {"value"},
    "call": {"callee", "arguments"}, "generic_application": {"value", "arguments"},
    "argument": {"label", "value"},
    "binary": {"operator", "left", "right"}, "unary": {"operator", "value"},
    "operator": {"name"}, "type_expression": {"type"},
    "lambda": {"parameters", "body"}, "typed_lambda": {"signature", "body"},
    "let_expression": {"binding", "body"},
    "block": {"statements"}, "return": {"value"}, "expression_body": {"value"},
    "let": {"name", "type", "grade", "value"},
    "typed_local": {"name", "type", "grade", "value"},
    "let_pattern": {"pattern", "value"},
    "if": {"condition", "then", "else"},
    "match": {"value", "motive", "cases"}, "case": {"pattern", "statements"},
    "match_expression": {"value", "motive", "cases"},
    "expression_case": {"pattern", "value"}, "match_motive": {"name", "type"},
    "wildcard_pattern": set(), "binding_pattern": {"name"},
    "unit_pattern": set(), "group_pattern": {"pattern"},
    "tuple_pattern": {"patterns"}, "bool_pattern": {"value"},
    "nat_pattern": {"value", "suffix"}, "constructor_pattern": {"name", "arguments"},
    "quantifier": {"quantifier", "parameters", "value"},
    "hole": {"name"},
}
_PATTERN_KINDS = {
    "wildcard_pattern", "binding_pattern", "unit_pattern", "group_pattern",
    "tuple_pattern", "bool_pattern", "nat_pattern", "constructor_pattern",
}
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*")
_OPERATORS = {"+", "*", "-", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||", "!", "==>", "<==>"}
_SYNTAX_WORDS = {
    "function_type": ("mode", {"Fn", "FnMut", "FnOnce"}),
    "generic_parameter": ("mode", {"type", "ghost", "region", "effect", "captures", "grade"}),
    "quantifier": ("quantifier", {"forall", "exists"}),
}


class _Protocol:
    def __init__(self, source: bytes) -> None:
        source_text(source)
        self.source = source
        self.remaining = MAX_SOURCE_BYTES
        self.boundaries = {0}
        offset = 0
        for character in source.decode("utf-8"):
            offset += len(character.encode("utf-8"))
            self.boundaries.add(offset)

    def error(self, kind: str, message: str, node: Node | None = None) -> VelaError:
        offset = 0 if node is None else cast("list[int]", node.get("span", [0]))[0]
        prefix = self.source[:offset].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        return VelaError(kind, prefix.count("\n") + 1, len(prefix.rsplit("\n", 1)[-1]) + 1, message)

    def _span(self, raw: object, parent: tuple[int, int]) -> tuple[int, int]:
        if (not isinstance(raw, list) or len(raw) != 2
                or type(raw[0]) is not int or type(raw[1]) is not int):
            raise self.error("protocol", "syntax span must contain two integer offsets")
        start, end = cast("tuple[int, int]", tuple(raw))
        if (not parent[0] <= start < end <= parent[1]
                or start not in self.boundaries or end not in self.boundaries):
            raise self.error("protocol", "syntax span is empty, escaping or splits UTF-8")
        return start, end

    def _compact_name(self, raw: bytes) -> str:
        """Remove only lexer trivia; qualified names can contain nested comments."""
        value = raw.decode("utf-8")
        result: list[str] = []
        offset = 0
        while offset < len(value):
            if value[offset].isspace():
                offset += 1
            elif value.startswith("//", offset):
                found = re.search(r"[\r\n]", value[offset + 2:])
                offset = len(value) if found is None else offset + 2 + found.start()
            elif value.startswith("/*", offset):
                level = 1
                offset += 2
                while level and offset < len(value):
                    if value.startswith("/*", offset):
                        level += 1
                        offset += 2
                    elif value.startswith("*/", offset):
                        level -= 1
                        offset += 2
                    else:
                        offset += 1
                if level:
                    raise self.error("protocol", "unterminated trivia in syntax name")
            else:
                token = re.match(r"\?[A-Za-z_][A-Za-z_0-9]*|[A-Za-z_][A-Za-z_0-9]*|<==>|==>|&&|\|\||==|!=|<=|>=|[.+*\-/%<>!]", value[offset:])
                if token is None:
                    return "\x00"
                result.append(token.group())
                offset += len(token.group())
        if len(result) == 1:
            return result[0]
        if (len(result) % 2 == 1 and all(_IDENTIFIER.fullmatch(result[index]) for index in range(0, len(result), 2))
                and all(result[index] == "." for index in range(1, len(result), 2))):
            return "".join(result)
        return "\x00"

    @staticmethod
    def _word(value: bytes) -> bool:
        return value.isalnum() or value == b"_"

    def _token(self, node: Node, cursor: int, token: bytes) -> int:
        cursor = trivia_end(self.source, cursor, block_comments=True)
        end = cursor + len(token)
        if (self.source[cursor:end] != token
                or (self._word(token[-1:]) and self._word(self.source[end:end + 1]))):
            raise self.error("protocol", "syntax delimiter or keyword differs from source", node)
        return end

    def _child(self, node: Node, span: tuple[int, int], cursor: int, raw: object) -> int:
        if not isinstance(raw, dict):
            raise self.error("protocol", "syntax envelope requires a located child", node)
        child_span = self._span(raw.get("span"), span)
        if trivia_end(self.source, cursor, block_comments=True) != child_span[0]:
            raise self.error("protocol", "syntax child leaves source tokens uncovered", node)
        return child_span[1]

    def _list(self, node: Node, span: tuple[int, int], cursor: int, raw: object,
              opening: bytes = b"(", closing: bytes = b")", *, trailing: bool = True) -> int:
        if not isinstance(raw, list):
            raise self.error("protocol", "syntax envelope requires a child list", node)
        cursor = self._token(node, cursor, opening)
        for index, value in enumerate(raw):
            if index:
                cursor = self._token(node, cursor, b",")
            cursor = self._child(node, span, cursor, value)
        if raw and trailing:
            after = trivia_end(self.source, cursor, block_comments=True)
            if self.source[after:after + 1] == b",":
                cursor = after + 1
        return self._token(node, cursor, closing)

    def _generics(self, node: Node, span: tuple[int, int], cursor: int) -> int:
        values = node["generics"]
        if not isinstance(values, list):
            raise self.error("protocol", "generic telescope must be a child list", node)
        return self._list(node, span, cursor, values, b"<", b">") if values else cursor

    def _ordinary_envelope(self, node: Node, span: tuple[int, int]) -> None:
        kind = node["kind"]
        cursor = span[0]
        if kind in {"definition", "function", "alias", "theorem", "lemma"}:
            if node.get("contracts") or node.get("cancel"):
                return  # These roles are refused by the mathematical consumer.
            modifiers = node["modifiers"]
            if not isinstance(modifiers, list) or any(not isinstance(item, str) for item in modifiers):
                raise self.error("protocol", "declaration modifiers must be a name list", node)
            for modifier in modifiers:
                cursor = self._token(node, cursor, cast("str", modifier).encode())
            if kind != "function":
                cursor = self._token(node, cursor, cast("str", kind).encode())
            if kind in {"definition", "function"}:
                cursor = self._child(node, span, cursor, node["result"])
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._generics(node, span, cursor)
            if kind != "alias":
                cursor = self._list(node, span, cursor, node["parameters"])
            if kind in {"theorem", "lemma"}:
                cursor = self._token(node, cursor, b":")
                cursor = self._child(node, span, cursor, node["proposition"])
                if node["body"] is not None:
                    cursor = self._token(node, cursor, b"proof")
                    cursor = self._child(node, span, cursor, node["body"])
                else:
                    cursor = self._token(node, cursor, b";")
            elif kind in {"alias", "definition"}:
                cursor = self._token(node, cursor, b"=" if kind == "alias" else b"=>")
                cursor = self._child(node, span, cursor, node["type"] if kind == "alias" else node["value"])
                cursor = self._token(node, cursor, b";")
            elif node["body"] is None:
                cursor = self._token(node, cursor, b";")
            else:
                cursor = self._child(node, span, cursor, node["body"])
        elif kind in {"let", "typed_local", "parameter", "lambda_parameter", "generic_parameter"}:
            if node.get("grade") is not None:
                return
            if kind == "generic_parameter":
                if node["mode"] == "ghost":
                    cursor = self._token(node, cursor, b"ghost")
                    cursor = self._child(node, span, cursor, node["type"])
                elif node["mode"] != "type":
                    return
                cursor = self._child(node, span, cursor, node["name"])
                if node["mode"] == "type" and node["type"] is not None:
                    cursor = self._token(node, cursor, b":")
                    cursor = self._child(node, span, cursor, node["type"])
            else:
                if kind == "let":
                    cursor = self._token(node, cursor, b"let")
                if kind in {"parameter", "lambda_parameter"} and node.get("const", False):
                    cursor = self._token(node, cursor, b"const")
                if node["type"] is not None:
                    cursor = self._child(node, span, cursor, node["type"])
                if node["name"] is not None:
                    cursor = self._child(node, span, cursor, node["name"])
                if kind in {"let", "typed_local"}:
                    cursor = self._token(node, cursor, b"=")
                    cursor = self._child(node, span, cursor, node["value"])
                    if cursor < span[1]:
                        cursor = self._token(node, cursor, b";")
        elif kind == "let_pattern":
            pattern = node["pattern"]
            if (not isinstance(pattern, dict)
                    or pattern.get("kind") not in {"unit_pattern", "group_pattern", "tuple_pattern", "constructor_pattern"}):
                raise self.error("protocol", "let_pattern requires a parenthesized or constructor pattern", node)
            cursor = self._token(node, cursor, b"let")
            cursor = self._child(node, span, cursor, pattern)
            cursor = self._token(node, cursor, b"=")
            cursor = self._child(node, span, cursor, node["value"])
            if cursor < span[1]:
                cursor = self._token(node, cursor, b";")
        elif kind == "return":
            cursor = self._token(node, cursor, b"return")
            if node["value"] is not None:
                cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b";")
        elif kind == "if":
            cursor = self._token(node, cursor, b"if")
            cursor = self._token(node, cursor, b"(")
            cursor = self._child(node, span, cursor, node["condition"])
            cursor = self._token(node, cursor, b")")
            cursor = self._child(node, span, cursor, node["then"])
            if node["else"] is not None:
                cursor = self._token(node, cursor, b"else")
                cursor = self._child(node, span, cursor, node["else"])
        elif kind in {"match", "match_expression"}:
            cursor = self._token(node, cursor, b"match")
            cursor = self._token(node, cursor, b"(")
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b")")
            if node["motive"] is not None:
                if not isinstance(node["motive"], dict) or node["motive"].get("kind") != "match_motive":
                    raise self.error("protocol", "match motive must be a match_motive node", node)
                cursor = self._child(node, span, cursor, node["motive"])
            cases = node["cases"]
            expected_case = "expression_case" if kind == "match_expression" else "case"
            if (not isinstance(cases, list)
                    or any(not isinstance(item, dict) or item.get("kind") != expected_case for item in cases)):
                raise self.error("protocol", f"{kind} requires {expected_case} children", node)
            if kind == "match_expression":
                cursor = self._list(node, span, cursor, cases, b"{", b"}")
            else:
                cursor = self._token(node, cursor, b"{")
                self._sequence_envelope(node, span, "cases", cursor, b"}")
                return
        elif kind == "match_motive":
            cursor = self._token(node, cursor, b"as")
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._token(node, cursor, b":")
            cursor = self._child(node, span, cursor, node["type"])
        elif kind == "case":
            if not isinstance(node["pattern"], dict) or node["pattern"].get("kind") not in _PATTERN_KINDS:
                raise self.error("protocol", "match arm requires a pattern node", node)
            cursor = self._token(node, cursor, b"case")
            cursor = self._child(node, span, cursor, node["pattern"])
            cursor = self._token(node, cursor, b":")
            self._sequence_envelope(node, span, "statements", cursor)
            return
        elif kind == "expression_case":
            if not isinstance(node["pattern"], dict) or node["pattern"].get("kind") not in _PATTERN_KINDS:
                raise self.error("protocol", "match arm requires a pattern node", node)
            cursor = self._child(node, span, cursor, node["pattern"])
            cursor = self._token(node, cursor, b"=>")
            cursor = self._child(node, span, cursor, node["value"])
        elif kind == "wildcard_pattern":
            if self._word(self.source[span[0] - 1:span[0]]):
                raise self.error("protocol", "wildcard pattern splits a source token", node)
            cursor = self._token(node, cursor, b"_")
        elif kind == "binding_pattern":
            name = node["name"]
            if (not isinstance(name, dict) or not isinstance(name.get("text"), str)
                    or name["text"] == "_" or "." in name["text"]):
                raise self.error("protocol", "binding_pattern requires a non-wildcard unqualified name", node)
            cursor = self._child(node, span, cursor, name)
        elif kind == "constructor_pattern":
            arguments = node["arguments"]
            if (not isinstance(arguments, list)
                    or any(not isinstance(item, dict) or item.get("kind") not in _PATTERN_KINDS for item in arguments)):
                raise self.error("protocol", "constructor_pattern arguments must be pattern nodes", node)
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._list(node, span, cursor, arguments)
        elif kind in {"name", "hole"}:
            cursor = self._child(node, span, cursor, node["name"])
        elif kind == "binary":
            for field in ("left", "operator", "right"):
                cursor = self._child(node, span, cursor, node[field])
        elif kind == "unary":
            cursor = self._child(node, span, cursor, node["operator"])
            cursor = self._child(node, span, cursor, node["value"])
        elif kind in {"group", "group_type", "group_pattern", "operator"}:
            cursor = self._token(node, cursor, b"(")
            field = {"group": "value", "group_type": "type", "group_pattern": "pattern", "operator": "name"}[cast("str", kind)]
            if kind == "group_pattern" and (not isinstance(node["pattern"], dict) or node["pattern"].get("kind") not in _PATTERN_KINDS):
                raise self.error("protocol", "group_pattern requires a pattern child", node)
            cursor = self._child(node, span, cursor, node[field])
            cursor = self._token(node, cursor, b")")
        elif kind in {"tuple", "tuple_type", "tuple_pattern"}:
            field = {"tuple": "values", "tuple_type": "types", "tuple_pattern": "patterns"}[cast("str", kind)]
            if kind == "tuple_pattern":
                patterns = node["patterns"]
                if (not isinstance(patterns, list) or len(patterns) < 2
                        or any(not isinstance(item, dict) or item.get("kind") not in _PATTERN_KINDS for item in patterns)):
                    raise self.error("protocol", "tuple_pattern requires at least two pattern children", node)
            cursor = self._list(node, span, cursor, node[field], trailing=False)
        elif kind in {"type_expression", "type_argument", "computed_type"}:
            cursor = self._token(node, cursor, b"type")
            if kind == "computed_type":
                cursor = self._token(node, cursor, b"[")
                cursor = self._child(node, span, cursor, node["value"])
                cursor = self._token(node, cursor, b"]")
            else:
                cursor = self._child(node, span, cursor, node["type"])
        elif kind == "type":
            cursor = self._child(node, span, cursor, node["name"])
            values = node["arguments"]
            if not isinstance(values, list):
                raise self.error("protocol", "type arguments must be a child list", node)
            if values:
                cursor = self._list(node, span, cursor, values, b"<", b">")
        elif kind == "function_type":
            if node["captures"] or node["effects"] or node["contracts"]:
                return
            cursor = self._token(node, cursor, cast("str", node["mode"]).encode())
            cursor = self._generics(node, span, cursor)
            cursor = self._list(node, span, cursor, node["parameters"])
            cursor = self._token(node, cursor, b"->")
            cursor = self._child(node, span, cursor, node["result"])
        elif kind == "generic_application":
            cursor = self._child(node, span, cursor, node["value"])
            cursor = trivia_end(self.source, cursor, block_comments=True)
            explicit = self.source[cursor:cursor + 3] == b"::<"
            if not node["arguments"]:
                raise self.error("protocol", "generic application requires nonempty arguments", node)
            cursor = self._list(node, span, cursor, node["arguments"], b"::<" if explicit else b"<", b">")
            following = trivia_end(self.source, cursor, block_comments=True)
            if not explicit and self.source[following:following + 1] != b"(":
                raise self.error("protocol", "ordinary generic application must be followed by a call", node)
        elif kind == "typed_lambda":
            cursor = self._child(node, span, cursor, node["signature"])
            cursor = self._token(node, cursor, b"=>")
            cursor = self._child(node, span, cursor, node["body"])
        elif kind == "let_expression":
            binding = node["binding"]
            if not isinstance(binding, dict) or binding.get("kind") not in {"let", "typed_local", "let_pattern"}:
                raise self.error("protocol", "let_expression requires a local binding", node)
            cursor = self._child(node, span, cursor, binding)
            if self.source[cursor - 1:cursor] == b";":
                raise self.error("protocol", "let_expression binding cannot carry a statement semicolon", node)
            cursor = self._token(node, cursor, b"in")
            cursor = self._child(node, span, cursor, node["body"])
        elif kind == "quantifier":
            cursor = self._token(node, cursor, cast("str", node["quantifier"]).encode())
            cursor = self._list(node, span, cursor, node["parameters"])
            cursor = self._token(node, cursor, b"=>")
            cursor = self._child(node, span, cursor, node["value"])
        else:
            return
        if cursor != span[1]:
            raise self.error("protocol", "syntax envelope leaves trailing source tokens uncovered", node)

    def _lambda_envelope(self, node: Node, span: tuple[int, int]) -> None:
        parameters = node["parameters"]
        body = node["body"]
        if not isinstance(parameters, list) or not isinstance(body, dict):
            raise self.error("protocol", "lambda has invalid parameters or body", node)
        body_span = self._span(body.get("span"), span)
        if body_span[1] != span[1]:
            raise self.error("protocol", "lambda body leaves trailing source tokens", node)
        cursor = span[0]
        parenthesized = self.source[cursor:cursor + 1] == b"("
        if parenthesized:
            cursor += 1
        elif len(parameters) != 1:
            raise self.error("protocol", "a bare lambda requires one parameter", node)
        for index, parameter in enumerate(parameters):
            if not isinstance(parameter, dict):
                raise self.error("protocol", "lambda has an invalid parameter", node)
            parameter_span = self._span(parameter.get("span"), span)
            if trivia_end(self.source, cursor, block_comments=True) != parameter_span[0]:
                raise self.error("protocol", "lambda parameter leaves source tokens uncovered", node)
            if not parenthesized and parameter.get("type") is not None:
                raise self.error("protocol", "a bare lambda parameter cannot carry a type", node)
            cursor = trivia_end(self.source, parameter_span[1], block_comments=True)
            if index != len(parameters) - 1:
                if self.source[cursor:cursor + 1] != b",":
                    raise self.error("protocol", "lambda parameter separator differs from source", node)
                cursor += 1
        cursor = trivia_end(self.source, cursor, block_comments=True)
        if parenthesized:
            if parameters and self.source[cursor:cursor + 1] == b",":
                cursor = trivia_end(self.source, cursor + 1, block_comments=True)
            if self.source[cursor:cursor + 1] != b")":
                raise self.error("protocol", "lambda parameter delimiter differs from source", node)
            cursor = trivia_end(self.source, cursor + 1, block_comments=True)
        if (self.source[cursor:cursor + 2] != b"=>"
                or trivia_end(self.source, cursor + 2, block_comments=True) != body_span[0]):
            raise self.error("protocol", "lambda arrow or body leaves source tokens uncovered", node)

    def _call_envelope(self, node: Node, span: tuple[int, int]) -> None:
        callee, arguments = node["callee"], node["arguments"]
        if not isinstance(callee, dict) or not isinstance(arguments, list):
            raise self.error("protocol", "call has invalid callee or arguments", node)
        callee_span = self._span(callee.get("span"), span)
        cursor = trivia_end(self.source, callee_span[1], block_comments=True)
        if callee_span[0] != span[0] or self.source[cursor:cursor + 1] != b"(":
            raise self.error("protocol", "call callee or opening differs from source", node)
        cursor += 1
        for index, argument in enumerate(arguments):
            if not isinstance(argument, dict) or argument.get("kind") != "argument":
                raise self.error("protocol", "call requires located argument wrappers", node)
            argument_span = self._span(argument.get("span"), span)
            if trivia_end(self.source, cursor, block_comments=True) != argument_span[0]:
                raise self.error("protocol", "call argument leaves source tokens uncovered", node)
            cursor = trivia_end(self.source, argument_span[1], block_comments=True)
            if index != len(arguments) - 1:
                if self.source[cursor:cursor + 1] != b",":
                    raise self.error("protocol", "call argument separator differs from source", node)
                cursor += 1
        cursor = trivia_end(self.source, cursor, block_comments=True)
        if arguments and self.source[cursor:cursor + 1] == b",":
            cursor = trivia_end(self.source, cursor + 1, block_comments=True)
        if self.source[cursor:cursor + 1] != b")" or cursor + 1 != span[1]:
            raise self.error("protocol", "call closing or argument list differs from source", node)

    def _constant_envelope(self, node: Node, span: tuple[int, int]) -> None:
        annotation, name, value = node["type"], node["name"], node["value"]
        if not all(isinstance(part, dict) for part in (annotation, name, value)):
            raise self.error("protocol", "constant requires a type, name and initializer", node)
        annotation_span = self._span(cast("Node", annotation).get("span"), span)
        name_span = self._span(cast("Node", name).get("span"), span)
        value_span = self._span(cast("Node", value).get("span"), span)
        modifiers = node.get("modifiers", [])
        if not isinstance(modifiers, list) or any(not isinstance(item, str) for item in modifiers):
            raise self.error("protocol", "constant modifiers must be a list of names", node)
        cursor = span[0]
        for spelling in (*modifiers, "const"):
            token = cast("str", spelling).encode()
            following = self.source[cursor + len(token):cursor + len(token) + 1]
            if (self.source[cursor:cursor + len(token)] != token
                    or following.isalnum() or following == b"_"):
                raise self.error("protocol", "constant keyword or modifiers differ from source", node)
            cursor = trivia_end(self.source, cursor + len(token), block_comments=True)
        if cursor != annotation_span[0]:
            raise self.error("protocol", "constant type leaves source tokens uncovered", node)
        if trivia_end(self.source, annotation_span[1], block_comments=True) != name_span[0]:
            raise self.error("protocol", "constant name leaves source tokens uncovered", node)
        cursor = trivia_end(self.source, name_span[1], block_comments=True)
        if (self.source[cursor:cursor + 1] != b"="
                or trivia_end(self.source, cursor + 1, block_comments=True) != value_span[0]):
            raise self.error("protocol", "constant initializer differs from source", node)
        cursor = trivia_end(self.source, value_span[1], block_comments=True)
        if self.source[cursor:cursor + 1] != b";" or cursor + 1 != span[1]:
            raise self.error("protocol", "constant terminator leaves source tokens uncovered", node)

    def _sequence_envelope(self, node: Node, span: tuple[int, int], role: str,
                           cursor: int, closing: bytes = b"") -> None:
        values = node[role]
        if not isinstance(values, list):
            raise self.error("protocol", f"{role} must be an ordered syntax list", node)
        for value in values:
            if not isinstance(value, dict):
                raise self.error("protocol", f"{role} contains an invalid syntax node", node)
            child_span = self._span(value.get("span"), span)
            if trivia_end(self.source, cursor, block_comments=True) != child_span[0]:
                raise self.error("protocol", f"{role} are reordered or leave source tokens uncovered", node)
            cursor = child_span[1]
        end = trivia_end(self.source, cursor, block_comments=True)
        if not closing and cursor <= span[1] <= end:
            return
        cursor = end
        if self.source[cursor:cursor + len(closing)] != closing or cursor + len(closing) != span[1]:
            raise self.error("protocol", f"{role} leave trailing source tokens uncovered", node)

    def visit(self, raw: object, parent: tuple[int, int], depth: int = 0) -> None:
        if depth > MAX_DEPTH or self.remaining <= 0:
            raise self.error("limit", "surface syntax exceeds elaboration bounds")
        self.remaining -= 1
        if isinstance(raw, list):
            for value in raw:
                self.visit(value, parent, depth + 1)
            return
        if raw is None or isinstance(raw, (str, bool)):
            return
        if not isinstance(raw, dict):
            raise self.error("protocol", "unexpected syntax payload")
        node = cast("Node", raw)
        span = self._span(node.get("span"), parent)
        if "text" in node:
            text = node["text"]
            if (set(node) != {"text", "span"} or not isinstance(text, str)
                    or not (_IDENTIFIER.fullmatch(text) or text in _OPERATORS
                            or re.fullmatch(r"\?[A-Za-z_][A-Za-z_0-9]*", text))
                    or self._compact_name(self.source[span[0]:span[1]]) != text):
                raise self.error("protocol", "syntax identifier or operator differs from its source", node)
            if ((_IDENTIFIER.fullmatch(text) or text.startswith("?"))
                    and (self._word(self.source[span[0] - 1:span[0]])
                         or self._word(self.source[span[1]:span[1] + 1]))):
                raise self.error("protocol", "syntax identifier splits a source token", node)
            return
        kind = node.get("kind")
        if not isinstance(kind, str):
            raise self.error("protocol", "syntax node has no kind", node)
        fields = _FIELDS.get(kind)
        if fields is None:
            raise self.error("unsupported", f"'{kind}' is outside mathematical elaboration", node)
        optional = {"const"} if kind in {"parameter", "lambda_parameter"} else set()
        if (set(node) - optional != {"kind", "span", *fields}
                or ("const" in node and type(node["const"]) is not bool)):
            raise self.error("protocol", f"invalid fields for '{kind}'", node)
        if kind in _SYNTAX_WORDS:
            field, spellings = _SYNTAX_WORDS[kind]
            word = node[field]
            if not isinstance(word, str) or word not in spellings:
                raise self.error("protocol", f"invalid syntax word for '{kind}.{field}'", node)
        if node.get("const", False) and kind == "lambda_parameter" and node["type"] is None:
            raise self.error("protocol", "a constant lambda parameter requires an explicit type", node)
        if "grade" in fields and node["grade"] is not None:
            grade = node["grade"]
            if not isinstance(grade, dict) or not isinstance(grade.get("kind"), str):
                raise self.error("protocol", "optional grade must be null or a located syntax node", node)
            self._span(grade.get("span"), span)
        self._ordinary_envelope(node, span)
        if kind in {"nat", "nat_pattern"}:
            value, suffix = node["value"], node["suffix"]
            if not isinstance(value, str) or not isinstance(suffix, str):
                raise self.error("protocol", "invalid numeric literal payload", node)
            if len(value.replace("_", "")) > MAX_LITERAL_DIGITS:
                raise self.error("limit", "numeric literal exceeds digit bound", node)
            if self.source[span[0]:span[1]] != (value + suffix).encode():
                raise self.error("protocol", "numeric literal differs from its source", node)
            if suffix or not DECIMAL.fullmatch(value):
                raise self.error("unsupported", "only unsuffixed decimal Nat literals are supported", node)
        if kind in {"bool", "bool_pattern"}:
            value = node["value"]
            if type(value) is not bool or self.source[span[0]:span[1]] != (b"true" if value else b"false"):
                raise self.error("protocol", "Boolean literal differs from its source", node)
        if kind in {"unit", "unit_pattern"}:
            cursor = trivia_end(self.source, span[0] + 1, block_comments=True)
            if (self.source[span[0]:span[0] + 1] != b"("
                    or self.source[cursor:cursor + 1] != b")" or cursor + 1 != span[1]):
                raise self.error("protocol", "unit value differs from its source", node)
        if kind in {"block", "case"}:
            statements = node["statements"]
            if isinstance(statements, list):
                for statement in statements:
                    if isinstance(statement, dict) and statement.get("kind") in {"let", "typed_local", "let_pattern"}:
                        statement_span = self._span(statement.get("span"), span)
                        if self.source[statement_span[1] - 1:statement_span[1]] != b";":
                            raise self.error("protocol", "statement local binding lacks its semicolon", statement)
        if kind == "expression_body":
            if (self.source[span[0]:span[0] + 2] != b"=>"
                    or self.source[span[1] - 1:span[1]] != b";"):
                raise self.error("protocol", "expression body differs from its source delimiters", node)
            value = node["value"]
            if not isinstance(value, dict):
                raise self.error("protocol", "expression body has no value node", node)
            value_span = self._span(value.get("span"), (span[0] + 2, span[1] - 1))
            if (trivia_end(self.source, span[0] + 2, block_comments=True) != value_span[0]
                    or trivia_end(self.source, value_span[1], block_comments=True) != span[1] - 1):
                raise self.error("protocol", "expression body leaves source tokens uncovered", node)
        if kind == "lambda":
            self._lambda_envelope(node, span)
        if kind == "call":
            self._call_envelope(node, span)
        if kind in {"constant", "constant_local"}:
            self._constant_envelope(node, span)
        if kind == "surface_file":
            name = node["name"]
            if not isinstance(name, dict):
                raise self.error("protocol", "module requires its located name", node)
            name_span = self._span(name.get("span"), span)
            cursor = trivia_end(self.source, span[0] + len(b"module"), block_comments=True)
            if (self.source[span[0]:span[0] + len(b"module")] != b"module"
                    or self._word(self.source[span[0] + len(b"module"):span[0] + len(b"module") + 1])
                    or cursor != name_span[0]):
                raise self.error("protocol", "module header differs from source", node)
            cursor = trivia_end(self.source, name_span[1], block_comments=True)
            if self.source[cursor:cursor + 1] != b";":
                raise self.error("protocol", "module header lacks its source terminator", node)
            self._sequence_envelope(node, span, "declarations", cursor + 1)
        if kind == "block":
            if self.source[span[0]:span[0] + 1] != b"{":
                raise self.error("protocol", "block opening differs from source", node)
            self._sequence_envelope(node, span, "statements", span[0] + 1, b"}")
        if kind == "argument":
            value = node["value"]
            if not isinstance(value, dict):
                raise self.error("protocol", "call argument has no expression", node)
            value_span = self._span(value.get("span"), span)
            label = node["label"]
            if label is None:
                if value_span != span:
                    raise self.error("protocol", "positional argument leaves source tokens uncovered", node)
            else:
                if not isinstance(label, dict):
                    raise self.error("protocol", "call argument has an invalid label", node)
                label_span = self._span(label.get("span"), span)
                cursor = trivia_end(self.source, label_span[1], block_comments=True)
                if (label_span[0] != span[0] or self.source[cursor:cursor + 1] != b":"
                        or trivia_end(self.source, cursor + 1, block_comments=True) != value_span[0]
                        or value_span[1] != span[1]):
                    raise self.error("protocol", "argument label differs from source delimiters", node)
        if kind == "lambda_parameter" and node["type"] is None:
            name = node["name"]
            if not isinstance(name, dict):
                raise self.error("protocol", "inferred lambda parameter has no binder", node)
            name_span = self._span(name.get("span"), span)
            if name_span[0] != span[0] or (node["grade"] is None and name_span != span):
                raise self.error("protocol", "inferred lambda parameter has an annotation span", node)
        for key, value in node.items():
            if key not in {"span", "kind"}:
                self.visit(value, span, depth + 1)

    def decode(self, response: object) -> Node:
        if (not isinstance(response, dict) or set(response) != {"schema", "source_sha256", "ast"}
                or type(response["schema"]) is not int or response["schema"] != 2
                or response["source_sha256"] != hashlib.sha256(self.source).hexdigest()):
            raise self.error("protocol", "surface response has invalid schema or source binding")
        if not isinstance(response["ast"], dict):
            raise self.error("protocol", "expected a complete surface_file object")
        self.visit(response["ast"], (0, len(self.source)))
        root = cast("Node", response["ast"])
        if root.get("kind") != "surface_file":
            raise self.error("protocol", "expected a complete surface_file")
        start, end = cast("list[int]", root["span"])
        if (trivia_end(self.source, 0, block_comments=True) != start
                or trivia_end(self.source, end, block_comments=True) != len(self.source)):
            raise self.error("protocol", "module omits nontrivial source outside its span", root)
        return root


@dataclass(frozen=True)
class _Term:
    kind: str
    value: str | int = ""
    args: tuple[_Term, ...] = ()


def _term(kind: str, *args: _Term, value: str | int = "") -> _Term:
    return _Term(kind, value, tuple(args))


def _app(function: _Term, argument: _Term) -> _Term:
    return _term("app", function, argument)


def _apps(function: _Term, *arguments: _Term) -> _Term:
    for argument in arguments:
        function = _app(function, argument)
    return function


def _constant(name: str) -> _Term:
    return _term("const", value=name)


_NAT = _constant("Nat")
_BOOL = _constant("bool")
_UNIT = _constant("Unit")
_SORT = _term("sort", value=0)
_PROP = _term("sort", value=-1)


@dataclass
class _Meta:
    type: _Term
    scope: frozenset[int]
    solution: _Term | None = None


@dataclass(frozen=True)
class _Binding:
    term: _Term
    type: _Term
    generics: int = 0
    constant: bool = False


@dataclass(frozen=True)
class _Pat:
    kind: str
    node: Node
    names: tuple[str, ...] = ()
    value: bool = False
    args: tuple[_Pat, ...] = ()


@dataclass(frozen=True)
class _Row:
    patterns: tuple[_Pat, ...]
    bindings: tuple[tuple[str, _Binding], ...]
    arm: Node


class _Elaborator:
    def __init__(self, protocol: _Protocol) -> None:
        self.protocol = protocol
        self.serial = 0
        self.work = MAX_WORK
        self.reductions = MAX_REDUCTIONS
        self.metas: list[_Meta] = []
        self.types: dict[int, _Term] = {}
        # Callable parameter labels are source metadata, never CIC constructors.
        self.parameter_names: dict[int, str] = {}
        self.nullary_parameters: set[int] = set()
        self.constant_parameters: set[int] = set()
        self.static_forbidden: set[int] | None = None
        self.globals: dict[str, _Binding] = {}
        self.constants: dict[str, _Binding] = {}
        self.definitions: dict[str, _Term] = {}
        self.output: list[str] = []
        self.site: Node | None = None
        self._builtins()

    def fail(self, kind: str, message: str, node: Node | None = None) -> VelaError:
        return self.protocol.error(kind, message, self.site if node is None else node)

    def tick(self, reduction: bool = False) -> None:
        self.work -= 1
        if reduction:
            self.reductions -= 1
        if self.work < 0 or self.reductions < 0:
            raise self.fail("limit", "elaboration work or definitional reduction budget exhausted")

    def fresh(self, value_type: _Term) -> _Term:
        index = self.serial
        self.serial += 1
        self.types[index] = value_type
        return _term("var", value=index)

    def pi(self, domain: _Term, codomain: _Term, *, nullary: bool = False) -> _Term:
        variable = self.fresh(domain)
        if nullary:
            self.nullary_parameters.add(cast("int", variable.value))
        return _term("pi", domain, codomain, value=variable.value)

    def _builtins(self) -> None:
        def bind(name: str, value_type: _Term, generics: int = 0) -> None:
            self.globals[name] = _Binding(_constant(name), value_type, generics)
            self.constants[name] = self.globals[name]

        for name in ("Nat", "bool", "Unit"):
            bind(name, _SORT)
        bind("Prop", _SORT)
        bind("Succ", self.pi(_NAT, _NAT))
        a = self.fresh(_SORT)
        b = self.fresh(_SORT)
        n = self.fresh(_NAT)
        x = self.fresh(a)
        y = self.fresh(a)
        z = self.fresh(a)

        def telescope(parameters: tuple[_Term, ...], result: _Term) -> _Term:
            for parameter in reversed(parameters):
                result = _term("pi", self.types[cast("int", parameter.value)], result, value=parameter.value)
            return result

        def eq(left: _Term, right: _Term) -> _Term:
            return _apps(_constant("Eq"), a, left, right)

        bind("Eq", telescope((a, x, y), _PROP), 1)
        bind("Refl", telescope((a, x), eq(x, x)), 1)
        bind("Symm", telescope((a, x, y), self.pi(eq(x, y), eq(y, x))), 3)
        bind("Trans", telescope((a, x, y, z), self.pi(eq(x, y), self.pi(eq(y, z), eq(x, z)))), 4)
        f = self.fresh(self.pi(a, b))
        congr_result = _apps(_constant("Eq"), b, _app(f, x), _app(f, y))
        bind("Congr", telescope((a, b, x, y, f), self.pi(eq(x, y), congr_result)), 4)
        bind("Fst", telescope((a, b), self.pi(_term("prod", a, b), a)), 2)
        bind("Snd", telescope((a, b), self.pi(_term("prod", a, b), b)), 2)
        bind("Vec", telescope((a, n), _SORT))
        bind("Fin", telescope((n,), _SORT))
        vec = _apps(_constant("Vec"), a, n)
        fin = _app(_constant("Fin"), n)
        successor = _app(_constant("Succ"), n)
        bind("VNil", telescope((a,), self.pi(_UNIT, _apps(_constant("Vec"), a, _term("nat", value=0)), nullary=True)), 1)
        bind("VCons", telescope((a, n), self.pi(a, self.pi(vec, _apps(_constant("Vec"), a, successor)))), 2)
        bind("FZero", telescope((n,), self.pi(_UNIT, _app(_constant("Fin"), successor), nullary=True)), 1)
        bind("FSucc", telescope((n,), self.pi(fin, _app(_constant("Fin"), successor))), 1)
        bind("At", telescope((a, n), self.pi(vec, self.pi(fin, a))), 2)
        for name in ("+", "*", "-", "/", "%"):
            bind(name, self.pi(_NAT, self.pi(_NAT, _NAT)))
        for name in ("<=", "<", ">=", ">"):
            bind(name, self.pi(_NAT, self.pi(_NAT, _BOOL)))
        for name in ("&&", "||", "==>", "<==>"):
            bind(name, self.pi(_BOOL, self.pi(_BOOL, _BOOL)))
        bind("!", self.pi(_BOOL, _BOOL))
        for name, domain in (("eq_nat", _NAT), ("ne_nat", _NAT), ("eq_bool", _BOOL), ("ne_bool", _BOOL)):
            bind(name, self.pi(domain, self.pi(domain, _BOOL)))

    def meta(self, value_type: _Term, environment: dict[str, _Binding]) -> _Term:
        index = len(self.metas)
        scope: set[int] = set()
        for binding in environment.values():
            scope.update(self.free(binding.term))
        self.metas.append(_Meta(value_type, frozenset(scope)))
        return _term("meta", value=index)

    def resolve(self, term: _Term) -> _Term:
        self.tick()
        if term.kind == "meta":
            solution = self.metas[cast("int", term.value)].solution
            if solution is not None:
                return self.resolve(solution)
        return term

    def substitute(self, term: _Term, variable: int, replacement: _Term) -> _Term:
        self.tick()
        term = self.resolve(term)
        if term.kind == "var" and term.value == variable:
            return replacement
        if term.kind in {"pi", "lam"} and term.value == variable:
            return _term(term.kind, self.substitute(term.args[0], variable, replacement), term.args[1], value=term.value)
        if term.kind == "let" and term.value == variable:
            return _term("let", self.substitute(term.args[0], variable, replacement),
                         self.substitute(term.args[1], variable, replacement), term.args[2], value=term.value)
        return _Term(term.kind, term.value, tuple(self.substitute(value, variable, replacement) for value in term.args))

    def free(self, term: _Term) -> set[int]:
        self.tick()
        term = self.resolve(term)
        if term.kind == "var":
            return {cast("int", term.value)}
        result: set[int] = set()
        for argument in term.args:
            result.update(self.free(argument))
        if term.kind in {"pi", "lam", "let"}:
            result.discard(cast("int", term.value))
        return result

    def occurs(self, index: int, term: _Term) -> bool:
        term = self.resolve(term)
        return ((term.kind == "meta" and term.value == index)
                or any(self.occurs(index, child) for child in term.args))

    def natural_limit(self) -> int:
        return MAX_CONSTANT_NAT if self.static_forbidden is not None else (1 << MAX_NAT_BITS) - 1

    def whnf(self, term: _Term) -> _Term:
        self.tick()
        term = self.resolve(term)
        if term.kind == "let":
            self.tick(True)
            return self.whnf(self.substitute(term.args[2], cast("int", term.value), term.args[1]))
        if term.kind == "static":
            if self.free(term.args[1]):
                return self.whnf(term.args[1])
            previous = self.static_forbidden
            self.static_forbidden = set() if previous is None else previous
            try:
                normalized = self.whnf(term.args[1])
                kind = {_NAT: "nat", _BOOL: "bool", _UNIT: "unit"}[self.whnf(term.args[0])]
                if normalized.kind != kind:
                    raise self.fail("inference", "constant initializer did not evaluate to an admitted static value")
                return normalized
            finally:
                self.static_forbidden = previous
        if term.kind == "nat" and not 0 <= cast("int", term.value) <= self.natural_limit():
            raise self.fail("limit", "computed natural exceeds representation bound")
        if term.kind in {"if", "bool_match"}:
            condition = self.whnf(term.args[1])
            if condition.kind == "bool":
                self.tick(True)
                return self.whnf(term.args[2] if condition.value else term.args[3])
            return term
        if term.kind == "unit_match":
            scrutinee = self.whnf(term.args[1])
            if scrutinee.kind == "unit":
                self.tick(True)
                return self.whnf(term.args[2])
            return term
        if term.kind == "pair_match":
            scrutinee = self.whnf(term.args[1])
            if scrutinee.kind == "pair":
                self.tick(True)
                branch = term.args[2]
                inner = self.substitute(branch.args[1], cast("int", branch.value), scrutinee.args[2])
                return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), scrutinee.args[3]))
            return term
        if term.kind == "nat_match":
            scrutinee = self.whnf(term.args[1])
            if scrutinee.kind == "nat":
                self.tick(True)
                amount = cast("int", scrutinee.value)
                if amount == 0:
                    return self.whnf(term.args[2])
                succ_branch = term.args[3]
                pred = _term("nat", value=amount - 1)
                return self.whnf(self.substitute(succ_branch.args[1], cast("int", succ_branch.value), pred))
            if scrutinee.kind == "app" and scrutinee.args[0] == _constant("Succ"):
                self.tick(True)
                succ_branch = term.args[3]
                return self.whnf(self.substitute(succ_branch.args[1], cast("int", succ_branch.value), scrutinee.args[1]))
            return term
        if term.kind == "const" and term.value in self.definitions:
            self.tick(True)
            return self.whnf(self.definitions[term.value])
        if term.kind != "app":
            return term
        function, argument = term.args
        function = self.whnf(function)
        if function.kind == "lam":
            self.tick(True)
            return self.whnf(self.substitute(function.args[1], cast("int", function.value), argument))
        term = _app(function, argument)
        head, arguments = self.spine(term)
        if head.kind != "const":
            return term
        name = head.value
        if name in {"Fst", "Snd"} and len(arguments) == 3:
            pair = self.whnf(arguments[2])
            if pair.kind == "pair":
                self.tick(True)
                return self.whnf(pair.args[2] if name == "Fst" else pair.args[3])
        if name == "At" and len(arguments) == 4:
            vector, values = self.spine(self.whnf(arguments[2]))
            index, indices = self.spine(self.whnf(arguments[3]))
            if vector == _constant("VCons") and len(values) == 4:
                if index == _constant("FZero") and len(indices) == 2:
                    self.tick(True)
                    return self.whnf(values[2])
                if index == _constant("FSucc") and len(indices) == 2:
                    self.tick(True)
                    return self.whnf(_apps(_constant("At"), arguments[0], values[1], values[3], indices[1]))
        if name == "Succ" and len(arguments) == 1:
            value = self.whnf(arguments[0])
            if value.kind == "nat":
                self.tick(True)
                if cast("int", value.value) >= self.natural_limit():
                    raise self.fail("limit", "computed natural exceeds representation bound")
                return _term("nat", value=cast("int", value.value) + 1)
        if name == "!" and len(arguments) == 1:
            value = self.whnf(arguments[0])
            if value.kind == "bool":
                self.tick(True)
                return _term("bool", value=1 - cast("int", value.value))
        if len(arguments) == 2 and name in _OPERATORS | {"eq_nat", "eq_bool", "ne_nat", "ne_bool"}:
            left, right = (self.whnf(value) for value in arguments)
            if left.kind == right.kind and left.kind in {"nat", "bool"}:
                a, b = cast("int", left.value), cast("int", right.value)
                operations = {"+": lambda: a + b, "*": lambda: a * b,
                              "-": lambda: max(0, a - b), "/": lambda: 0 if b == 0 else a // b,
                              "%": lambda: a if b == 0 else a % b,
                              "<=": lambda: int(a <= b), "<": lambda: int(a < b),
                              ">=": lambda: int(a >= b), ">": lambda: int(a > b),
                              "eq_nat": lambda: int(a == b), "eq_bool": lambda: int(a == b),
                              "ne_nat": lambda: int(a != b), "ne_bool": lambda: int(a != b),
                              "&&": lambda: int(bool(a and b)), "||": lambda: int(bool(a or b)),
                              "==>": lambda: int(not a or b), "<==>": lambda: int(a == b)}
                operation = operations.get(name)
                if operation is not None:
                    self.tick(True)
                    limit = self.natural_limit()
                    if ((name == "+" and a > limit - b)
                            or (name == "*" and a != 0 and b > limit // a)):
                        raise self.fail("limit", "computed natural exceeds representation bound")
                    value = operation()
                    if value > limit:
                        raise self.fail("limit", "computed natural exceeds representation bound")
                    kind = "nat" if name in {"+", "*", "-", "/", "%"} else "bool"
                    return _term(kind, value=value)
            if name == "+" and left.kind == "nat":
                self.tick(True)
                amount = cast("int", left.value)
                if amount == 0:
                    return right
                return _app(_constant("Succ"), _apps(_constant("+"), _term("nat", value=amount - 1), right))
        if head.value == "if" and len(arguments) == 4:
            condition = self.whnf(arguments[1])
            if condition.kind == "bool":
                self.tick(True)
                return self.whnf(arguments[2] if condition.value else arguments[3])
        return term

    @staticmethod
    def spine(term: _Term) -> tuple[_Term, list[_Term]]:
        arguments: list[_Term] = []
        while term.kind == "app":
            arguments.append(term.args[1])
            term = term.args[0]
        return term, list(reversed(arguments))

    def unify(self, left: _Term, right: _Term) -> None:
        self.tick()
        left, right = self.whnf(left), self.whnf(right)
        if (left.kind == right.kind and left.kind in {"pi", "lam"}
                and (cast("int", left.value) in self.nullary_parameters)
                != (cast("int", right.value) in self.nullary_parameters)):
            raise self.fail("type", "zero-parameter and explicit-parameter callables have different source arities")
        if (left.kind == right.kind and left.kind in {"pi", "lam"}
                and (cast("int", left.value) in self.constant_parameters)
                != (cast("int", right.value) in self.constant_parameters)):
            raise self.fail("type", "callable constant-parameter requirements differ")
        if left == right:
            return
        # Decimal literals abbreviate constructor chains; expose one successor
        # when an inferred predecessor is constrained by a concrete index.
        for literal, successor in ((left, right), (right, left)):
            if (literal.kind == "nat" and cast("int", literal.value) > 0
                    and successor.kind == "app" and successor.args[0] == _constant("Succ")):
                self.unify(_term("nat", value=cast("int", literal.value) - 1), successor.args[1])
                return
        if right.kind == "meta" and left.kind != "meta":
            left, right = right, left
        if left.kind == "meta":
            index = cast("int", left.value)
            if self.occurs(index, right):
                raise self.fail("type", "infinite type or cyclic dependent inference (occurs check)")
            record = self.metas[index]
            if not self.free(right) <= record.scope:
                raise self.fail("type", "inference would let a local dependent value escape its scope")
            # Narrow nested unsolved variables too: a future solution cannot escape indirectly.
            self.restrict(right, record.scope)
            self.unify(record.type, self.infer(right))
            record.solution = right
            return
        if left.kind != right.kind or left.value != right.value:
            if left.kind == right.kind and left.kind in {"pi", "lam"}:
                self.unify(left.args[0], right.args[0])
                aligned = self.substitute(right.args[1], cast("int", right.value), _term("var", value=left.value))
                self.unify(left.args[1], aligned)
                return
            raise self.fail("type", "terms or dependent indices are not definitionally equal")
        if len(left.args) != len(right.args):
            raise self.fail("type", "incompatible type constructors")
        for first, second in zip(left.args, right.args, strict=True):
            self.unify(first, second)

    def restrict(self, term: _Term, scope: frozenset[int]) -> None:
        term = self.resolve(term)
        if term.kind == "meta":
            record = self.metas[cast("int", term.value)]
            record.scope = record.scope & scope
        for child in term.args:
            self.restrict(child, scope)

    def infer(self, term: _Term) -> _Term:
        self.tick()
        term = self.resolve(term)
        kind = term.kind
        if kind == "meta":
            return self.metas[cast("int", term.value)].type
        if kind == "var":
            return self.types[cast("int", term.value)]
        if kind == "sort":
            return _term("sort", value=max(0, cast("int", term.value) + 1))
        if kind == "const":
            if term.value == "Prop":
                return _SORT
            return self.constants[cast("str", term.value)].type
        if kind == "nat":
            return _NAT
        if kind == "bool":
            return _BOOL
        if kind == "unit":
            return _UNIT
        if kind == "static":
            return term.args[0]
        if kind == "let":
            return self.substitute(self.infer(term.args[2]), cast("int", term.value), term.args[1])
        if kind == "pi":
            domain = self.sort(term.args[0])
            result = self.sort(term.args[1])
            return _term("sort", value=-1 if result == -1 else max(domain, result))
        if kind == "lam":
            return _term("pi", term.args[0], self.infer(term.args[1]), value=term.value)
        if kind == "app":
            function_type = self.whnf(self.infer(term.args[0]))
            if function_type.kind != "pi":
                raise self.fail("type", "application requires a function")
            self.unify(self.infer(term.args[1]), function_type.args[0])
            return self.substitute(function_type.args[1], cast("int", function_type.value), term.args[1])
        if kind == "prod":
            return _term("sort", value=max(self.sort(term.args[0]), self.sort(term.args[1]), 0))
        if kind == "pair":
            return _term("prod", term.args[0], term.args[1])
        if kind == "if":
            return term.args[0]
        if kind in {"bool_match", "unit_match", "pair_match", "nat_match"}:
            return self.substitute(term.args[0].args[1], cast("int", term.args[0].value), term.args[1])
        raise self.fail("type", "cannot infer internal term")

    def sort(self, term: _Term) -> int:
        value_type = self.whnf(self.infer(term))
        if value_type.kind != "sort":
            raise self.fail("type", "expected a type or proposition")
        level = cast("int", value_type.value)
        if level > MAX_UNIVERSE + 1:
            raise self.fail("limit", "universe formation exceeds the supported hierarchy")
        return level

    def node(self, raw: object, kind: str | None = None) -> Node:
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            raise self.fail("protocol", "expected a syntax node")
        node = cast("Node", raw)
        if kind is not None and node["kind"] != kind:
            raise self.fail("protocol", f"expected a '{kind}' node", node)
        return node

    def nodes(self, raw: object) -> list[Node]:
        if not isinstance(raw, list):
            raise self.fail("protocol", "expected a syntax-node list")
        return [self.node(value) for value in raw]

    def name(self, raw: object) -> str:
        if (not isinstance(raw, dict) or not isinstance(raw.get("text"), str)
                or not _IDENTIFIER.fullmatch(raw["text"])):
            raise self.fail("protocol", "expected a located name")
        return cast("str", raw["text"])

    def operator(self, raw: object) -> str:
        if not isinstance(raw, dict) or not isinstance(raw.get("text"), str) or raw["text"] not in _OPERATORS:
            raise self.fail("protocol", "expected a supported located operator")
        return cast("str", raw["text"])

    def no_roles(self, node: Node, *roles: str) -> None:
        for role in roles:
            value = node.get(role)
            if value is not None and value != []:
                raise self.fail("unsupported", f"'{role}' requires the full frontend", node)

    def bind_local(self, environment: dict[str, _Binding], name: str, binding: _Binding) -> None:
        if "." in name or (name != "_" and name in environment):
            raise self.fail("name", f"duplicate or invalid local binding '{name}'")
        if name != "_":
            environment[name] = binding

    def instantiate(self, binding: _Binding, environment: dict[str, _Binding],
                    arguments: list[Node] | None = None) -> _Binding:
        term, value_type = binding.term, binding.type
        if arguments is not None and len(arguments) != binding.generics:
            raise self.fail("type", f"expected {binding.generics} explicit generic arguments, got {len(arguments)}")
        for index in range(binding.generics):
            value_type = self.whnf(value_type)
            if value_type.kind != "pi":
                raise self.fail("type", "invalid generic telescope")
            domain = value_type.args[0]
            if arguments is None:
                argument = self.meta(domain, environment)
            else:
                argument = self.argument(arguments[index], domain, environment)
            term = _app(term, argument)
            value_type = self.substitute(value_type.args[1], cast("int", value_type.value), argument)
        return _Binding(term, value_type)

    def lookup(self, name: str, environment: dict[str, _Binding], *, raw: bool = False) -> _Binding:
        binding = environment.get(name, self.globals.get(name))
        if binding is None:
            raise self.fail("name", f"unknown or forward name '{name}'")
        if self.static_forbidden is not None and id(binding) in self.static_forbidden:
            raise self.fail("type", f"constant initializer depends on nonstatic binding '{name}'")
        return binding if raw else self.instantiate(binding, environment)

    def argument(self, node: Node, expected: _Term, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "type_argument":
            value = self.type(self.node(node["type"]), environment)
            self.unify(self.infer(value), expected)
            return value
        if node["kind"] in {"type", "function_type", "group_type", "tuple_type", "computed_type"}:
            if node["kind"] == "type" and self.name(node["name"]) == "_" and not self.nodes(node["arguments"]):
                return self.meta(expected, environment)
            value = self.type(node, environment, require_sort=False)
            self.unify(self.infer(value), expected)
            return value
        return self.check(node, expected, environment)

    def static_argument(self, node: Node, expected: _Term, environment: dict[str, _Binding],
                        *, type_syntax: bool = False) -> _Term:
        """Check the complete source dependency graph before reducing an argument."""
        previous = self.static_forbidden
        self.static_forbidden = (set() if previous is None else previous) | {
            id(binding) for binding in environment.values() if not binding.constant}
        try:
            value = self.argument(node, expected, environment) if type_syntax else self.check(node, expected, environment)
            self.complete(value)
            available = set().union(*(self.free(binding.term) for binding in environment.values()
                                      if binding.constant))
            dependencies = self.free(value)
            if not dependencies <= available:
                raise self.fail("type", "constant parameter requires a static argument", node)
            if self.whnf(expected) in {_NAT, _BOOL, _UNIT}:
                marked = _term("static", expected, value)
                return marked if dependencies else self.whnf(marked)
            return value
        finally:
            self.static_forbidden = previous

    def specialize(self, term: _Term, depth: int = 0) -> _Term:
        """Instantiate logical templates while preserving deferred static demands."""
        self.tick(True)
        if depth > MAX_DEPTH:
            raise self.fail("limit", "static specialization exceeds its nesting budget")
        term = self.resolve(term)
        if term.kind == "let":
            return _term("let", term.args[0], term.args[1], self.specialize(term.args[2], depth + 1), value=term.value)
        if term.kind == "static":
            value = self.specialize(term.args[1], depth + 1)
            marked = _term("static", term.args[0], value)
            return marked if self.free(value) else self.whnf(marked)
        if term.kind == "const" and term.value in self.definitions:
            return self.specialize(self.definitions[term.value], depth + 1)
        if term.kind == "app":
            function = self.specialize(term.args[0], depth + 1)
            argument = self.specialize(term.args[1], depth + 1)
            if function.kind == "let":
                body = self.specialize(_app(function.args[2], argument), depth + 1)
                return _term("let", function.args[0], function.args[1], body, value=function.value)
            if function.kind == "lam":
                return self.specialize(self.substitute(function.args[1], cast("int", function.value), argument), depth + 1)
            result = _app(function, argument)
            reduced = self.whnf(result)
            return result if reduced == result else self.specialize(reduced, depth + 1)
        specialized = _Term(term.kind, term.value, tuple(self.specialize(child, depth + 1) for child in term.args))
        if term.kind in {"if", "bool_match", "unit_match", "pair_match", "nat_match"}:
            reduced = self.whnf(specialized)
            return specialized if reduced == specialized else self.specialize(reduced, depth + 1)
        return specialized

    def apply(self, binding: _Binding, arguments: list[Node], environment: dict[str, _Binding]) -> _Binding:
        term, value_type = binding.term, binding.type
        specializing = False
        specialized_term = term
        runtime_arguments: list[tuple[_Term, _Term]] = []
        future = self.whnf(value_type)
        protects_runtime = False
        while future.kind == "pi":
            protects_runtime = protects_runtime or cast("int", future.value) in self.constant_parameters
            future = self.whnf(future.args[1])
        if not arguments:
            value_type = self.whnf(value_type)
            if value_type.kind != "pi" or cast("int", value_type.value) not in self.nullary_parameters:
                raise self.fail("type", "zero-argument call requires a zero-parameter source callable")
            self.unify(value_type.args[0], _UNIT)
            argument = _term("unit")
            return _Binding(_app(term, argument), self.substitute(value_type.args[1], cast("int", value_type.value), argument))
        labeled = False
        for node in arguments:
            self.node(node, "argument")
            label = node["label"]
            if label is None and labeled:
                raise self.fail("name", "positional arguments cannot follow a named argument", node)
            labeled = labeled or label is not None
            value_type = self.whnf(value_type)
            if value_type.kind == "meta":
                domain = self.meta(_SORT, environment)
                variable = self.fresh(domain)
                result = self.meta(_SORT, environment)
                self.unify(value_type, _term("pi", domain, result, value=variable.value))
                value_type = self.whnf(value_type)
            if value_type.kind != "pi":
                raise self.fail("type", "too many arguments or a non-callable value", node)
            if cast("int", value_type.value) in self.nullary_parameters:
                raise self.fail("type", "a zero-parameter callable accepts no explicit arguments", node)
            if label is not None:
                spelling = self.name(label)
                expected = self.parameter_names.get(cast("int", value_type.value))
                if expected is None:
                    raise self.fail("name", "unnamed callable parameters do not accept argument labels", node)
                if spelling != expected:
                    raise self.fail("name", f"expected argument label '{expected}', got '{spelling}'", node)
            required_static = cast("int", value_type.value) in self.constant_parameters
            checker = self.static_argument if required_static else self.check
            argument = checker(self.node(node["value"]), value_type.args[0], environment)
            specializing = specializing or required_static
            if required_static:
                specialized_term = _app(specialized_term, argument)
            elif protects_runtime:
                variable = self.fresh(value_type.args[0])
                runtime_arguments.append((variable, argument))
                specialized_term = _app(specialized_term, variable)
            else:
                specialized_term = _app(specialized_term, argument)
            term = _app(term, argument)
            value_type = self.substitute(value_type.args[1], cast("int", value_type.value), argument)
        if protects_runtime:
            term = self.specialize(specialized_term) if specializing else specialized_term
            for variable, argument in reversed(runtime_arguments):
                term = _term("let", self.types[cast("int", variable.value)], argument, term, value=variable.value)
        return _Binding(term, value_type)

    def telescope(self, generic_nodes: list[Node], parameter_nodes: list[Node],
                  environment: dict[str, _Binding], *, unit: bool = False) -> tuple[list[_Term], dict[str, _Binding]]:
        extended = dict(environment)
        variables: list[_Term] = []
        for node in generic_nodes:
            self.site = node
            self.node(node, "generic_parameter")
            mode = node["mode"]
            if not isinstance(mode, str) or mode not in {"type", "ghost"}:
                raise self.fail("unsupported", f"generic mode '{mode}' requires the full frontend")
            if mode == "ghost" and node["type"] is None:
                raise self.fail("protocol", "ghost binder lacks its type")
            domain = _SORT if node["type"] is None else self.type(self.node(node["type"]), extended)
            if mode == "type" and self.whnf(domain).kind != "sort":
                raise self.fail("type", "a type generic requires a universe kind")
            variable = self.fresh(domain)
            variables.append(variable)
            self.bind_local(extended, self.name(node["name"]), _Binding(variable, domain))
        for node in parameter_nodes:
            self.site = node
            if node["kind"] != "parameter":
                raise self.fail("protocol", "invalid parameter role")
            self.no_roles(node, "grade")
            domain = self.type(self.node(node["type"]), extended)
            variable = self.fresh(domain)
            variables.append(variable)
            static = cast("bool", node.get("const", False))
            if static:
                self.constant_parameters.add(cast("int", variable.value))
            if node["name"] is not None:
                name = self.name(node["name"])
                self.parameter_names[cast("int", variable.value)] = name
                self.bind_local(extended, name, _Binding(variable, domain, constant=static))
        if unit and not parameter_nodes:
            variable = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", variable.value))
            variables.append(variable)
        return variables, extended

    def wrap(self, kind: str, variables: list[_Term], result: _Term) -> _Term:
        for variable in reversed(variables):
            result = _term(kind, self.types[cast("int", variable.value)], result, value=variable.value)
        return result

    def type(self, node: Node, environment: dict[str, _Binding], *, require_sort: bool = True) -> _Term:
        self.tick()
        self.site = node
        kind = node["kind"]
        if kind == "type":
            name = self.name(node["name"])
            arguments = self.nodes(node["arguments"])
            if name == "_" and not arguments:
                result = self.meta(_SORT, environment)
            elif name == "Type":
                if not arguments:
                    result = _SORT
                elif len(arguments) == 1 and arguments[0]["kind"] == "nat":
                    level = int(cast("str", arguments[0]["value"]).replace("_", ""))
                    if not 0 <= level <= MAX_UNIVERSE:
                        raise self.fail("limit", f"Type level must be between 0 and {MAX_UNIVERSE}")
                    result = _term("sort", value=level)
                else:
                    raise self.fail("unsupported", "only numeric Type<n> universe levels are supported")
            elif name == "Prop":
                if arguments:
                    raise self.fail("type", "Prop takes no type arguments")
                result = _PROP
            else:
                binding = self.lookup(name, environment, raw=True)
                result, value_type = binding.term, binding.type
                for argument in arguments:
                    value_type = self.whnf(value_type)
                    if value_type.kind != "pi":
                        raise self.fail("type", f"too many arguments to '{name}'")
                    value = (self.static_argument(argument, value_type.args[0], environment, type_syntax=True)
                             if cast("int", value_type.value) in self.constant_parameters else
                             self.argument(argument, value_type.args[0], environment))
                    result = _app(result, value)
                    value_type = self.substitute(value_type.args[1], cast("int", value_type.value), value)
        elif kind in {"group_type", "type_argument"}:
            result = self.type(self.node(node["type"]), environment, require_sort=require_sort)
        elif kind == "tuple_type":
            values = [self.type(value, environment) for value in self.nodes(node["types"])]
            if len(values) < 2:
                raise self.fail("protocol", "a product type requires at least two components")
            result = values[-1]
            for value in reversed(values[:-1]):
                result = _term("prod", value, result)
        elif kind == "computed_type":
            result = self.expression(self.node(node["value"]), environment).term
        elif kind == "function_type":
            self.no_roles(node, "captures", "effects", "contracts")
            if node["mode"] != "Fn":
                raise self.fail("unsupported", "only pure Fn callable types are supported")
            variables, extended = self.telescope(self.nodes(node["generics"]), self.nodes(node["parameters"]), environment, unit=True)
            result = self.wrap("pi", variables, self.type(self.node(node["result"]), extended))
        else:
            raise self.fail("unsupported", f"'{kind}' is not a supported mathematical type")
        if require_sort:
            self.sort(result)
        return result

    def check(self, node: Node, expected: _Term, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] in {"lambda", "typed_lambda"}:
            return self.lambda_(node, environment, expected).term
        if node["kind"] == "block":
            return self.block(node, environment, expected).term
        if node["kind"] == "let_expression":
            return self.check(self.node(node["body"]), expected, self.local(self.node(node["binding"]), environment))
        if node["kind"] == "match_expression":
            return self.match(node, environment, expected, expression_arms=True).term
        if node["kind"] == "expression_body":
            return self.check(self.node(node["value"]), expected, environment)
        if node["kind"] == "tuple":
            expected_normal = self.whnf(expected)
            if expected_normal.kind == "prod":
                values = self.nodes(node["values"])
                if len(values) < 2:
                    raise self.fail("protocol", "a product requires at least two components")
                first = self.check(values[0], expected_normal.args[0], environment)
                if len(values) == 2:
                    second = self.check(values[1], expected_normal.args[1], environment)
                else:
                    rest = {"kind": "tuple", "span": node["span"], "values": values[1:]}
                    second = self.check(rest, expected_normal.args[1], environment)
                return _term("pair", expected_normal.args[0], expected_normal.args[1], first, second)
        value = self.expression(node, environment)
        self.site = node
        self.unify(value.type, expected)
        return value.term

    def lambda_(self, node: Node, environment: dict[str, _Binding], expected: _Term | None = None) -> _Binding:
        parameter_role = "lambda_parameter"
        if node["kind"] == "typed_lambda":
            parameter_role = "parameter"
            signature = self.type(self.node(node["signature"]), environment)
            if expected is not None:
                self.unify(signature, expected)
            signature_node = self.node(node["signature"], "function_type")
            if self.nodes(signature_node["generics"]):
                raise self.fail("unsupported", "generic lambda telescopes require explicit declarations", node)
            node = {"kind": "lambda", "parameters": signature_node["parameters"], "body": node["body"], "span": node["span"]}
            expected = signature
        parameters = self.nodes(node["parameters"])
        variables: list[_Term] = []
        extended = dict(environment)
        current = expected
        if not parameters:
            variable = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", variable.value))
            variables.append(variable)
            if current is not None:
                current = self.whnf(current)
                if current.kind != "pi":
                    raise self.fail("type", "lambda requires a callable expected type", node)
                if cast("int", current.value) not in self.nullary_parameters:
                    raise self.fail("type", "an empty lambda requires a zero-parameter source interface", node)
                self.unify(current.args[0], _UNIT)
                current = self.substitute(current.args[1], cast("int", current.value), variable)
        for parameter in parameters:
            self.site = parameter
            if parameter["kind"] != parameter_role:
                raise self.fail("protocol", "invalid lambda parameter syntax role")
            self.no_roles(parameter, "grade")
            annotation = parameter["type"]
            if annotation is None and parameter_role != "lambda_parameter":
                raise self.fail("protocol", "a declared callable parameter requires a type")
            domain = (self.meta(_SORT, extended) if annotation is None
                      else self.type(self.node(annotation), extended))
            expected_pi = None if current is None else self.whnf(current)
            if expected_pi is not None:
                if expected_pi.kind != "pi":
                    raise self.fail("type", "lambda has more parameters than its expected type")
                if cast("int", expected_pi.value) in self.nullary_parameters:
                    raise self.fail("type", "an explicit lambda parameter cannot satisfy a zero-parameter source interface")
                self.unify(domain, expected_pi.args[0])
            variable = self.fresh(domain)
            variables.append(variable)
            static = cast("bool", parameter.get("const", False))
            if expected_pi is not None:
                expected_static = cast("int", expected_pi.value) in self.constant_parameters
                if annotation is None:
                    static = expected_static
                elif static != expected_static:
                    raise self.fail("type", "lambda constant-parameter requirement differs from its expected type")
            if static:
                self.constant_parameters.add(cast("int", variable.value))
            name = self.name(parameter["name"])
            self.parameter_names[cast("int", variable.value)] = name
            self.bind_local(extended, name, _Binding(variable, domain, constant=static))
            if expected_pi is not None:
                current = self.substitute(expected_pi.args[1], cast("int", expected_pi.value), variable)
        body_node = self.node(node["body"])
        if current is None:
            body = self.block(body_node, extended) if body_node["kind"] == "block" else self.expression(body_node, extended)
        else:
            body = _Binding(self.check(body_node, current, extended), current)
        return _Binding(self.wrap("lam", variables, body.term), self.wrap("pi", variables, body.type))

    def _parse_pattern(self, node: Node, seen: set[str]) -> _Pat:
        self.tick()
        self.site = node
        kind = node["kind"]
        if kind == "wildcard_pattern":
            return _Pat("wild", node)
        if kind == "binding_pattern":
            name = self.name(node["name"])
            if "." in name or name == "_" or name in seen:
                raise self.fail("name", f"duplicate or invalid pattern binding '{name}'", node)
            seen.add(name)
            return _Pat("wild", node, names=(name,))
        if kind == "group_pattern":
            return self._parse_pattern(self.node(node["pattern"]), seen)
        if kind == "unit_pattern":
            return _Pat("unit", node)
        if kind == "bool_pattern":
            return _Pat("bool", node, value=cast("bool", node["value"]))
        if kind == "tuple_pattern":
            items = [self._parse_pattern(item, seen) for item in self.nodes(node["patterns"])]
            if len(items) < 2:
                raise self.fail("protocol", "a tuple pattern requires at least two components", node)
            result = items[-1]
            for item in reversed(items[:-1]):
                result = _Pat("pair", node, args=(item, result))
            return result
        if kind == "nat_pattern":
            amount = int(cast("str", node["value"]).replace("_", ""))
            if amount > MAX_PATTERN_NAT:
                raise self.fail("limit", f"natural pattern literal exceeds structural bound ({MAX_PATTERN_NAT})", node)
            result = _Pat("zero", node)
            for _ in range(amount):
                result = _Pat("succ", node, args=(result,))
            return result
        if kind == "constructor_pattern":
            cname = self.name(node["name"])
            arguments = self.nodes(node["arguments"])
            if cname == "Succ":
                if len(arguments) != 1:
                    raise self.fail("type", "constructor 'Succ' expects 1 pattern argument", node)
                return _Pat("succ", node, args=(self._parse_pattern(arguments[0], seen),))
            if cname not in self.globals:
                raise self.fail("name", f"unknown constructor '{cname}'", node)
            if cname in {"VNil", "VCons", "FZero", "FSucc", "Refl", "Symm", "Trans", "Congr"}:
                raise self.fail("unsupported", f"indexed elimination over '{cname}' requires the full frontend", node)
            raise self.fail("type", f"'{cname}' is not a pattern constructor", node)
        raise self.fail("protocol", f"unexpected pattern node '{kind}'", node)

    def _typecheck_pattern(self, pat: _Pat, expected_type: _Term, environment: dict[str, _Binding]) -> None:
        self.tick()
        self.site = pat.node
        if pat.kind == "wild":
            return
        if pat.kind == "unit":
            self.unify(expected_type, _UNIT)
            return
        if pat.kind == "bool":
            self.unify(expected_type, _BOOL)
            return
        if pat.kind in {"zero", "succ"}:
            self.unify(expected_type, _NAT)
            if pat.kind == "succ":
                self._typecheck_pattern(pat.args[0], _NAT, environment)
            return
        if pat.kind == "pair":
            resolved = self.whnf(expected_type)
            if resolved.kind == "meta":
                left_type = self.meta(_SORT, environment)
                right_type = self.meta(_SORT, environment)
                self.unify(resolved, _term("prod", left_type, right_type))
                resolved = self.whnf(expected_type)
            if resolved.kind != "prod":
                raise self.fail("type", "tuple pattern requires a product scrutinee", pat.node)
            self._typecheck_pattern(pat.args[0], resolved.args[0], environment)
            self._typecheck_pattern(pat.args[1], resolved.args[1], environment)
            return
        raise self.fail("protocol", f"unexpected internal pattern '{pat.kind}'", pat.node)

    def _require_irrefutable(self, pat: _Pat) -> None:
        if pat.kind in {"bool", "zero", "succ"}:
            raise self.fail("type", "local pattern binding requires an irrefutable pattern; use match", pat.node)
        for child in pat.args:
            self._require_irrefutable(child)

    def _bind_irrefutable(self, pat: _Pat, current: _Binding, extended: dict[str, _Binding]) -> None:
        self.site = pat.node
        for name in pat.names:
            self.bind_local(extended, name, current)
        if pat.kind == "pair":
            prod_type = self.whnf(current.type)
            left_type, right_type = prod_type.args
            left_term = _apps(_constant("Fst"), left_type, right_type, current.term)
            right_term = _apps(_constant("Snd"), left_type, right_type, current.term)
            self._bind_irrefutable(pat.args[0], _Binding(left_term, left_type), extended)
            self._bind_irrefutable(pat.args[1], _Binding(right_term, right_type), extended)

    def local(self, node: Node, environment: dict[str, _Binding]) -> dict[str, _Binding]:
        self.site = node
        if node["kind"] == "let_pattern":
            binding = self.expression(self.node(node["value"]), environment)
            pat = self._parse_pattern(self.node(node["pattern"]), set())
            self._require_irrefutable(pat)
            self._typecheck_pattern(pat, binding.type, environment)
            extended = dict(environment)
            self._bind_irrefutable(pat, binding, extended)
            return extended
        if node["kind"] == "constant_local":
            binding = self.constant_value(node, environment)
        elif node["kind"] not in {"let", "typed_local"}:
            raise self.fail("unsupported", "only immutable name bindings are supported")
        else:
            self.no_roles(node, "grade")
            if node["type"] is None:
                binding = self.expression(self.node(node["value"]), environment)
            else:
                value_type = self.type(self.node(node["type"]), environment)
                binding = _Binding(self.check(self.node(node["value"]), value_type, environment), value_type)
        extended = dict(environment)
        self.bind_local(extended, self.name(node["name"]), binding)
        return extended

    def match(self, node: Node, environment: dict[str, _Binding], expected: _Term | None = None,
              *, expression_arms: bool = True) -> _Binding:
        self.site = node
        scrutinee = self.expression(self.node(node["value"]), environment)
        root_var = self.fresh(scrutinee.type)
        root_var_id = cast("int", root_var.value)
        motive_node = node["motive"]
        motive_body: _Term | None = None
        if motive_node is not None:
            motive = self.node(motive_node, "match_motive")
            motive_env = dict(environment)
            self.bind_local(motive_env, self.name(motive["name"]), _Binding(root_var, scrutinee.type))
            motive_body = self.type(self.node(motive["type"]), motive_env)
            match_type = self.substitute(motive_body, root_var_id, scrutinee.term)
            if expected is not None:
                self.unify(match_type, expected)
        cases = self.nodes(node["cases"])
        rows: list[_Row] = []
        for arm in cases:
            self.node(arm, "expression_case" if expression_arms else "case")
            pat = self._parse_pattern(self.node(arm["pattern"]), set())
            self._typecheck_pattern(pat, scrutinee.type, environment)
            rows.append(_Row((pat,), (), arm))
        scrutinee_type = self.whnf(scrutinee.type)
        if scrutinee_type not in {_UNIT, _BOOL, _NAT} and scrutinee_type.kind != "prod":
            raise self.fail("type", "match scrutinee must have type Nat, bool, Unit or a product", self.node(node["value"]))
        inferred_result: list[_Term | None] = [expected]

        def specialize_rows(active_rows: list[_Row], index: int, ctor_kind: str, ctor_term: _Term,
                            col_type: _Term, sub_count: int, *, bool_value: bool = False) -> list[_Row]:
            specialized: list[_Row] = []
            for row in active_rows:
                pat = row.patterns[index]
                if pat.kind == "wild":
                    extra = tuple((name, _Binding(ctor_term, col_type)) for name in pat.names)
                    wilds = tuple(_Pat("wild", pat.node) for _ in range(sub_count))
                    specialized.append(_Row(
                        row.patterns[:index] + wilds + row.patterns[index + 1:],
                        row.bindings + extra,
                        row.arm,
                    ))
                elif pat.kind == ctor_kind and (ctor_kind != "bool" or pat.value == bool_value):
                    specialized.append(_Row(
                        row.patterns[:index] + pat.args + row.patterns[index + 1:],
                        row.bindings,
                        row.arm,
                    ))
            return specialized

        def compile_matrix(columns: list[tuple[_Term, _Term, _Term]], active_rows: list[_Row],
                           pattern_term: _Term) -> _Term:
            self.tick()
            if not active_rows:
                raise self.fail("type", "non-exhaustive match: missing pattern case", node)
            first = active_rows[0]
            if all(pat.kind == "wild" for pat in first.patterns):
                arm_env = dict(environment)
                for name, bound in first.bindings:
                    self.bind_local(arm_env, name, bound)
                for pat, (_, col_scrutinee, col_type) in zip(first.patterns, columns, strict=True):
                    for name in pat.names:
                        self.bind_local(arm_env, name, _Binding(col_scrutinee, col_type))
                arm = first.arm
                self.site = arm
                leaf_pattern = pattern_term
                for col_var, col_scrutinee, _ in columns:
                    if col_var != col_scrutinee:
                        leaf_pattern = self.substitute(leaf_pattern, cast("int", col_var.value), col_scrutinee)
                leaf_expected = (self.substitute(motive_body, root_var_id, leaf_pattern)
                                 if motive_body is not None else inferred_result[0])
                if expression_arms:
                    value_node = self.node(arm["value"])
                    if leaf_expected is None:
                        evaluated = self.expression(value_node, arm_env)
                        inferred_result[0] = evaluated.type
                        return evaluated.term
                    return self.check(value_node, leaf_expected, arm_env)
                block_node = {"kind": "block", "span": arm["span"], "statements": arm["statements"]}
                evaluated = self.block(block_node, arm_env, leaf_expected)
                if motive_body is None and inferred_result[0] is None:
                    inferred_result[0] = evaluated.type
                return evaluated.term

            index = next(i for i, pat in enumerate(first.patterns) if pat.kind != "wild")
            col_var, col_scrutinee, col_type = columns[index]
            col_var_id = cast("int", col_var.value)
            col_type = self.whnf(col_type)
            without_index = columns[:index] + columns[index + 1:]

            if col_type == _UNIT:
                unit_term = _term("unit")
                body = compile_matrix(
                    without_index,
                    specialize_rows(active_rows, index, "unit", unit_term, _UNIT, 0),
                    self.substitute(pattern_term, col_var_id, unit_term),
                )
                if motive_body is None:
                    return body
                motive_lam = _term("lam", _UNIT, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id)
                return _term("unit_match", motive_lam, col_scrutinee, body)

            if col_type == _BOOL:
                true_term = _term("bool", value=1)
                false_term = _term("bool", value=0)
                yes = compile_matrix(
                    without_index,
                    specialize_rows(active_rows, index, "bool", true_term, _BOOL, 0, bool_value=True),
                    self.substitute(pattern_term, col_var_id, true_term),
                )
                no = compile_matrix(
                    without_index,
                    specialize_rows(active_rows, index, "bool", false_term, _BOOL, 0, bool_value=False),
                    self.substitute(pattern_term, col_var_id, false_term),
                )
                if motive_body is None:
                    return _term("if", cast("_Term", inferred_result[0]), col_scrutinee, yes, no)
                motive_lam = _term("lam", _BOOL, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id)
                return _term("bool_match", motive_lam, col_scrutinee, yes, no)

            if col_type.kind == "prod":
                left_type, right_type = col_type.args
                left_var = self.fresh(left_type)
                right_var = self.fresh(right_type)
                pair_term = _term("pair", left_type, right_type, left_var, right_var)
                sub_columns = [(left_var, left_var, left_type), (right_var, right_var, right_type)]
                body = compile_matrix(
                    columns[:index] + sub_columns + columns[index + 1:],
                    specialize_rows(active_rows, index, "pair", pair_term, col_type, 2),
                    self.substitute(pattern_term, col_var_id, pair_term),
                )
                motive_return = (self.substitute(motive_body, root_var_id, pattern_term)
                                 if motive_body is not None else cast("_Term", inferred_result[0]))
                motive_lam = _term("lam", col_type, motive_return, value=col_var_id)
                branch_lam = _term("lam", left_type, _term("lam", right_type, body, value=right_var.value), value=left_var.value)
                return _term("pair_match", motive_lam, col_scrutinee, branch_lam)

            if col_type == _NAT:
                zero_term = _term("nat", value=0)
                zero_body = compile_matrix(
                    without_index,
                    specialize_rows(active_rows, index, "zero", zero_term, _NAT, 0),
                    self.substitute(pattern_term, col_var_id, zero_term),
                )
                pred_var = self.fresh(_NAT)
                succ_term = _app(_constant("Succ"), pred_var)
                sub_columns = [(pred_var, pred_var, _NAT)]
                succ_body = compile_matrix(
                    columns[:index] + sub_columns + columns[index + 1:],
                    specialize_rows(active_rows, index, "succ", succ_term, _NAT, 1),
                    self.substitute(pattern_term, col_var_id, succ_term),
                )
                motive_return = (self.substitute(motive_body, root_var_id, pattern_term)
                                 if motive_body is not None else cast("_Term", inferred_result[0]))
                motive_lam = _term("lam", _NAT, motive_return, value=col_var_id)
                succ_lam = _term("lam", _NAT, succ_body, value=pred_var.value)
                return _term("nat_match", motive_lam, col_scrutinee, zero_body, succ_lam)

            raise self.fail("type", "match column must have type Nat, bool, Unit or a product", node)

        term = compile_matrix([(root_var, scrutinee.term, scrutinee_type)], rows, root_var)
        result_type = (self.substitute(motive_body, root_var_id, scrutinee.term)
                       if motive_body is not None else cast("_Term", inferred_result[0]))
        return _Binding(term, result_type)

    def constant_value(self, node: Node, environment: dict[str, _Binding]) -> _Binding:
        previous = self.static_forbidden
        # Retain the surrounding bindings while checking the whole initializer.
        # Fresh lambda/function locals are distinct from its runtime inputs.
        self.static_forbidden = (set() if previous is None else previous) | {
            id(binding) for binding in environment.values() if not binding.constant}
        try:
            value_type = self.type(self.node(node["type"]), environment)
            expected = self.whnf(value_type)
            if expected not in {_NAT, _BOOL, _UNIT}:
                raise self.fail("unsupported", "mathematical constants require Nat, bool or Unit", node)
            value = self.check(self.node(node["value"]), value_type, environment)
            self.complete(value)
            available = set().union(*(self.free(binding.term) for binding in environment.values()
                                      if binding.constant))
            dependencies = self.free(value)
            if not dependencies <= available:
                raise self.fail("type", "constant initializer is not a closed static value", node)
            if dependencies:
                return _Binding(_term("static", value_type, value), value_type, constant=True)
            normalized = self.whnf(value)
            kind = {_NAT: "nat", _BOOL: "bool", _UNIT: "unit"}[expected]
            if normalized.kind != kind:
                raise self.fail("inference", "constant initializer did not evaluate to an admitted static value", node)
            if kind == "nat" and not 0 <= cast("int", normalized.value) <= MAX_CONSTANT_NAT:
                raise self.fail("limit", "constant natural exceeds representation bound", node)
            return _Binding(normalized, value_type, constant=True)
        finally:
            self.static_forbidden = previous

    def block(self, node: Node, environment: dict[str, _Binding], expected: _Term | None = None) -> _Binding:
        self.node(node, "block")
        statements = self.nodes(node["statements"])
        extended = dict(environment)
        for index, statement in enumerate(statements):
            self.site = statement
            kind = statement["kind"]
            if kind in {"let", "typed_local", "let_pattern", "constant_local"}:
                extended = self.local(statement, extended)
                continue
            if index != len(statements) - 1:
                raise self.fail("unsupported", "a returning terminal must be the final statement")
            if kind == "return":
                if statement["value"] is None:
                    value = _Binding(_term("unit"), _UNIT)
                    if expected is not None:
                        self.unify(value.type, expected)
                    return value
                value_node = self.node(statement["value"])
                return (self.expression(value_node, extended) if expected is None
                        else _Binding(self.check(value_node, expected, extended), expected))
            if kind == "if":
                condition = self.check(self.node(statement["condition"]), _BOOL, extended)
                if statement["else"] is None:
                    raise self.fail("type", "every conditional branch must return")
                yes = self.branch(self.node(statement["then"]), extended, expected)
                no = self.branch(self.node(statement["else"]), extended, yes.type)
                return _Binding(_term("if", yes.type, condition, yes.term, no.term), yes.type)
            if kind == "match":
                return self.match(statement, extended, expected, expression_arms=False)
            if kind == "block":
                return self.block(statement, extended, expected)
            raise self.fail("unsupported", f"statement '{kind}' requires the full frontend")
        raise self.fail("type", "a pure block requires an explicit terminal return", node)

    def branch(self, node: Node, environment: dict[str, _Binding], expected: _Term | None) -> _Binding:
        if node["kind"] == "block":
            return self.block(node, environment, expected)
        return self.block({"kind": "block", "span": node["span"], "statements": [node]}, environment, expected)

    def expression(self, node: Node, environment: dict[str, _Binding]) -> _Binding:
        self.tick()
        self.site = node
        kind = node["kind"]
        if kind == "nat":
            return _Binding(_term("nat", value=int(cast("str", node["value"]).replace("_", ""))), _NAT)
        if kind == "hole":
            raise self.fail("inference", "unfinished named proof hole; provide an explicit term")
        if kind == "bool":
            return _Binding(_term("bool", value=int(cast("bool", node["value"]))), _BOOL)
        if kind == "unit":
            return _Binding(_term("unit"), _UNIT)
        if kind in {"name", "operator"}:
            name = self.operator(node["name"]) if kind == "operator" else self.name(node["name"])
            if name == "Type":
                return _Binding(_SORT, _term("sort", value=1))
            if name == "Prop":
                return _Binding(_PROP, _SORT)
            if name == "_":
                value_type = self.meta(_SORT, environment)
                return _Binding(self.meta(value_type, environment), value_type)
            return self.lookup(name, environment)
        if kind == "group":
            return self.expression(self.node(node["value"]), environment)
        if kind == "type_expression":
            value = self.type(self.node(node["type"]), environment)
            return _Binding(value, self.infer(value))
        if kind == "tuple":
            values = [self.expression(value, environment) for value in self.nodes(node["values"])]
            if len(values) < 2:
                raise self.fail("protocol", "a product requires at least two components")
            result = values[-1]
            for value in reversed(values[:-1]):
                result = _Binding(_term("pair", value.type, result.type, value.term, result.term), _term("prod", value.type, result.type))
            return result
        if kind == "generic_application":
            target = self.node(node["value"])
            if target["kind"] != "name":
                raise self.fail("unsupported", "explicit generics require a declared callable name")
            binding = self.lookup(self.name(target["name"]), environment, raw=True)
            return self.instantiate(binding, environment, self.nodes(node["arguments"]))
        if kind == "call":
            return self.apply(self.expression(self.node(node["callee"]), environment), self.nodes(node["arguments"]), environment)
        if kind in {"lambda", "typed_lambda"}:
            return self.lambda_(node, environment)
        if kind == "let_expression":
            return self.expression(self.node(node["body"]), self.local(self.node(node["binding"]), environment))
        if kind == "match_expression":
            return self.match(node, environment, expression_arms=True)
        if kind == "block":
            return self.block(node, environment)
        if kind == "binary":
            operator = self.operator(node["operator"])
            left = self.expression(self.node(node["left"]), environment)
            right = self.expression(self.node(node["right"]), environment)
            if operator in {"==", "!="}:
                self.unify(left.type, right.type)
                operand_type = self.whnf(left.type)
                if operand_type not in {_NAT, _BOOL}:
                    raise self.fail("unsupported", "Boolean equality is defined only on Nat and bool")
                operation = ("eq_" if operator == "==" else "ne_") + ("nat" if operand_type == _NAT else "bool")
                return _Binding(_apps(_constant(operation), left.term, right.term), _BOOL)
            binding = self.globals.get(operator)
            if binding is None:
                raise self.fail("unsupported", f"operator '{operator}' is unsupported")
            signature = self.whnf(binding.type)
            self.unify(left.type, signature.args[0])
            signature = self.whnf(signature.args[1])
            self.unify(right.type, signature.args[0])
            return _Binding(_apps(binding.term, left.term, right.term), signature.args[1])
        if kind == "unary":
            operator = self.operator(node["operator"])
            if operator != "!":
                raise self.fail("unsupported", f"prefix '{operator}' is unsupported")
            value = self.check(self.node(node["value"]), _BOOL, environment)
            return _Binding(_app(_constant("!"), value), _BOOL)
        raise self.fail("unsupported", f"expression '{kind}' requires the full frontend")

    def proposition(self, node: Node, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "group":
            return self.proposition(self.node(node["value"]), environment)
        if node["kind"] == "binary":
            operator = self.operator(node["operator"])
            if operator == "==":
                left = self.expression(self.node(node["left"]), environment)
                right = self.check(self.node(node["right"]), left.type, environment)
                self.unify(self.infer(left.type), _SORT)
                return _apps(_constant("Eq"), left.type, left.term, right)
            if operator == "==>":
                domain = self.proposition(self.node(node["left"]), environment)
                return self.pi(domain, self.proposition(self.node(node["right"]), environment))
        if node["kind"] == "quantifier":
            if node["quantifier"] != "forall":
                raise self.fail("unsupported", "only universal propositions are supported")
            variables, extended = self.telescope([], self.nodes(node["parameters"]), environment)
            return self.wrap("pi", variables, self.proposition(self.node(node["value"]), extended))
        value = self.expression(node, environment)
        self.unify(value.type, _PROP)
        return value.term

    def complete(self, term: _Term) -> None:
        self.tick()
        term = self.resolve(term)
        if term.kind == "meta":
            raise self.fail("inference", "unresolved inference variable; add a type or generic argument")
        for child in term.args:
            self.complete(child)

    def declaration(self, node: Node) -> None:
        self.site = node
        first_meta = len(self.metas)
        kind = node["kind"]
        if kind not in {"alias", "definition", "function", "theorem", "lemma", "constant"}:
            raise self.fail("unsupported", f"declaration '{kind}' requires the full frontend")
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"} | ({"const"} if kind in {"definition", "function"} else set())
        if (not isinstance(modifiers, list) or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers")
        self.no_roles(node, "contracts", "cancel")
        name = self.name(node["name"])
        if name in self.globals or name in {"Type", "_"} or "." in name:
            raise self.fail("name", f"duplicate or reserved declaration '{name}'")
        generics = [] if kind == "constant" else self.nodes(node["generics"])
        parameters = [] if kind in {"alias", "constant"} else self.nodes(node["parameters"])
        variables, environment = self.telescope(generics, parameters, {}, unit=kind not in {"alias", "constant"})
        if kind == "constant":
            evaluated = self.constant_value(node, environment)
            body, result = evaluated.term, evaluated.type
        elif kind == "alias":
            body = self.type(self.node(node["type"]), environment)
            result = self.infer(body)
        elif kind in {"theorem", "lemma"}:
            result = self.proposition(self.node(node["proposition"]), environment)
            if node["body"] is None:
                raise self.fail("unsupported", "a theorem requires a complete explicit proof body", node)
            body = self.check(self.node(node["body"]), result, environment)
        else:
            result = self.type(self.node(node["result"]), environment)
            body_node = node["value"] if kind == "definition" else node["body"]
            if body_node is None:
                raise self.fail("unsupported", "abstract callable signatures have no emitted implementation", node)
            body = self.check(self.node(body_node), result, environment)
        signature = self.wrap("pi", variables, result)
        definition = self.wrap("lam", variables, body)
        self.site = node
        self.complete(signature)
        self.complete(definition)
        for index in range(first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)
        emitted = f"vela_d{len(self.output)}_{name}"
        self.output.append(f"Definition {emitted} : {self.render(signature)} :=\n  {self.render(definition)}.")
        binding = _Binding(_constant(emitted), signature, len(generics), constant=kind == "constant")
        self.globals[name] = binding
        # Generated references never become names in the source namespace.
        self.constants[emitted] = binding
        self.definitions[emitted] = definition

    def render(self, term: _Term) -> str:
        self.tick()
        term = self.resolve(term)
        kind = term.kind
        if kind == "sort":
            return "Prop" if term.value == -1 else f"Type@{{vela_u{term.value}}}"
        if kind == "var":
            return f"vela_v{term.value}"
        if kind == "const":
            name = cast("str", term.value)
            if name in _GALLINA:
                return _GALLINA[name]
            if name in self.definitions:
                return name
            raise self.fail("protocol", "unmapped internal constant")
        if kind == "nat":
            return f"({term.value} : Corelib.Init.Datatypes.nat)"
        if kind == "bool":
            return "Corelib.Init.Datatypes.true" if term.value else "Corelib.Init.Datatypes.false"
        if kind == "unit":
            return "Corelib.Init.Datatypes.tt"
        if kind == "static":
            value = term.args[1] if self.free(term.args[1]) else self.whnf(term)
            return self.render(value)
        if kind == "let":
            domain, value, body = term.args
            return (f"(let vela_v{term.value} : {self.render(domain)} := {self.render(value)} "
                    f"in {self.render(body)})")
        if kind in {"pi", "lam"}:
            domain, body = term.args
            binder = f"vela_v{term.value} : {self.render(domain)}"
            return (f"(forall ({binder}), {self.render(body)})" if kind == "pi"
                    else f"(fun ({binder}) => {self.render(body)})")
        if kind == "app":
            head, arguments = self.spine(term)
            prefix = "(@" if head.kind == "const" else "("
            return prefix + self.render(head) + " " + " ".join(self.render(value) for value in arguments) + ")"
        if kind == "prod":
            return f"(@Corelib.Init.Datatypes.prod {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind == "pair":
            return "(@Corelib.Init.Datatypes.pair " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "if":
            _, condition, yes, no = term.args
            return f"(if {self.render(condition)} then {self.render(yes)} else {self.render(no)})"
        if kind == "bool_match":
            motive, scrutinee, yes, no = term.args
            binder = f"vela_v{motive.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| Corelib.Init.Datatypes.true => {self.render(yes)} "
                    f"| Corelib.Init.Datatypes.false => {self.render(no)} end)")
        if kind == "unit_match":
            motive, scrutinee, body = term.args
            binder = f"vela_v{motive.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| Corelib.Init.Datatypes.tt => {self.render(body)} end)")
        if kind == "pair_match":
            motive, scrutinee, branch = term.args
            inner = branch.args[1]
            binder = f"vela_v{motive.value}"
            left_binder = f"vela_v{branch.value}"
            right_binder = f"vela_v{inner.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| @Corelib.Init.Datatypes.pair _ _ {left_binder} {right_binder} => {self.render(inner.args[1])} end)")
        if kind == "nat_match":
            motive, scrutinee, zero_branch, succ_branch = term.args
            binder = f"vela_v{motive.value}"
            pred_binder = f"vela_v{succ_branch.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| Corelib.Init.Datatypes.O => {self.render(zero_branch)} "
                    f"| Corelib.Init.Datatypes.S {pred_binder} => {self.render(succ_branch.args[1])} end)")
        raise self.fail("inference", "cannot emit an unresolved term")


_GALLINA = {
    "Nat": "Corelib.Init.Datatypes.nat", "bool": "Corelib.Init.Datatypes.bool",
    "Unit": "Corelib.Init.Datatypes.unit", "Prop": "Prop",
    "Succ": "Corelib.Init.Datatypes.S", "Eq": "Corelib.Init.Logic.eq",
    "Refl": "Corelib.Init.Logic.eq_refl", "Symm": "Corelib.Init.Logic.eq_sym",
    "Trans": "Corelib.Init.Logic.eq_trans", "Congr": "vela_Congr",
    "Fst": "Corelib.Init.Datatypes.fst", "Snd": "Corelib.Init.Datatypes.snd",
    "Vec": "vela_Vec", "VNil": "vela_VNil", "VCons": "vela_VCons",
    "Fin": "vela_Fin", "FZero": "vela_FZero", "FSucc": "vela_FSucc", "At": "vela_At",
    "+": "Corelib.Init.Nat.add", "*": "Corelib.Init.Nat.mul", "-": "Corelib.Init.Nat.sub",
    "/": "Corelib.Init.Nat.div", "%": "Corelib.Init.Nat.modulo",
    "<=": "Corelib.Init.Nat.leb", "<": "Corelib.Init.Nat.ltb", ">=": "vela_ge", ">": "vela_gt",
    "eq_nat": "Corelib.Init.Nat.eqb", "ne_nat": "vela_ne_nat",
    "eq_bool": "vela_eq_bool", "ne_bool": "vela_ne_bool",
    "&&": "vela_and", "||": "vela_or", "!": "vela_not", "==>": "vela_implies", "<==>": "vela_eq_bool",
}

_PRELUDE = """From Corelib Require Import Init.Datatypes Init.Nat Init.Logic.

Universe vela_u0 vela_u1 vela_u2 vela_u3 vela_u4 vela_u5 vela_u6 vela_u7 vela_u8 vela_u9.
Constraint vela_u0 < vela_u1.
Constraint vela_u1 < vela_u2.
Constraint vela_u2 < vela_u3.
Constraint vela_u3 < vela_u4.
Constraint vela_u4 < vela_u5.
Constraint vela_u5 < vela_u6.
Constraint vela_u6 < vela_u7.
Constraint vela_u7 < vela_u8.
Constraint vela_u8 < vela_u9.

Definition vela_not (a : bool) : bool := if a then false else true.
Definition vela_and (a b : bool) : bool := if a then b else false.
Definition vela_or (a b : bool) : bool := if a then true else b.
Definition vela_implies (a b : bool) : bool := if a then b else true.
Definition vela_eq_bool (a b : bool) : bool := if a then b else vela_not b.
Definition vela_ne_bool (a b : bool) : bool := vela_not (vela_eq_bool a b).
Definition vela_ne_nat (a b : nat) : bool := vela_not (Corelib.Init.Nat.eqb a b).
Definition vela_ge (a b : nat) : bool := Corelib.Init.Nat.leb b a.
Definition vela_gt (a b : nat) : bool := Corelib.Init.Nat.ltb b a.

Definition vela_Congr (A B : Type@{vela_u0}) (x y : A) (f : A -> B)
    (p : @Corelib.Init.Logic.eq A x y) : @Corelib.Init.Logic.eq B (f x) (f y) :=
  @Corelib.Init.Logic.f_equal A B f x y p.

Fixpoint vela_Vec (A : Type@{vela_u0}) (n : nat) {struct n} : Type@{vela_u0} :=
  match n with
  | O => unit
  | S k => @prod A (vela_Vec A k)
  end.
Definition vela_VNil (A : Type@{vela_u0}) (_ : unit) : vela_Vec A O := tt.
Definition vela_VCons (A : Type@{vela_u0}) (n : nat) (x : A) (xs : vela_Vec A n)
    : vela_Vec A (S n) := @pair A (vela_Vec A n) x xs.

Inductive vela_Fin : nat -> Type@{vela_u0} :=
| vela_fzero : forall n : nat, vela_Fin (S n)
| vela_fsucc : forall n : nat, vela_Fin n -> vela_Fin (S n).
Definition vela_FZero (n : nat) (_ : unit) : vela_Fin (S n) := vela_fzero n.
Definition vela_FSucc (n : nat) (i : vela_Fin n) : vela_Fin (S n) := vela_fsucc n i.
Fixpoint vela_lookup (A : Type@{vela_u0}) (n : nat) (i : vela_Fin n) {struct i}
    : vela_Vec A n -> A :=
  match i in vela_Fin size return vela_Vec A size -> A with
  | vela_fzero k => fun v => @fst A (vela_Vec A k) v
  | vela_fsucc k j => fun v => vela_lookup A k j (@snd A (vela_Vec A k) v)
  end.
Definition vela_At (A : Type@{vela_u0}) (n : nat) (xs : vela_Vec A n) (i : vela_Fin n)
    : A := vela_lookup A n i xs.
"""


def _checked_elaboration(source: bytes, parsed: object) -> tuple[Elaboration, _Elaborator]:
    protocol = _Protocol(source)
    try:
        root = protocol.decode(parsed)
        elaborator = _Elaborator(protocol)
        module = elaborator.name(root["name"])
        for declaration in elaborator.nodes(root["declarations"]):
            elaborator.declaration(declaration)
        generated_module = "Vela_" + module.replace(".", "_")
        gallina = ("(* SPDX-License-Identifier: Apache-2.0 *)\n"
                   "(* Vela mathematical elaboration: unqualified kernel proposal. "
                   f"Source SHA256: {hashlib.sha256(source).hexdigest()} *)\n"
                   f"Module {generated_module}.\n\n" + _PRELUDE + "\n"
                   + "\n\n".join(elaborator.output) + f"\n\nEnd {generated_module}.\n")
        if len(gallina.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise protocol.error("limit", "generated Gallina exceeds the output bound")
        return Elaboration(module, gallina), elaborator
    except RecursionError as error:
        raise protocol.error("limit", "elaboration nesting exceeds the host stack bound") from error


def elaborate(source: bytes, parsed: object) -> Elaboration:
    """Check an exact-source schema-2 AST and propose a complete bounded CIC file."""
    return _checked_elaboration(source, parsed)[0]


def _console_initializer(elaborator: _Elaborator, protocol: _Protocol, parsed: object,
                         prefix_bytes: int, expression_bytes: int) -> Node:
    root = protocol.decode(parsed)
    declarations = elaborator.nodes(root["declarations"])
    if len(declarations) != 1 or declarations[0]["kind"] != "constant":
        raise VelaError("syntax", 3, 1, "expected exactly one constant initializer")
    declaration = declarations[0]
    name = elaborator.name(declaration["name"])
    value = elaborator.node(declaration["value"])
    if (name != "__vela_console_result"
            or declaration["span"] != [len(b"module Playground;\n"), len(protocol.source)]
            or not prefix_bytes <= cast("list[int]", value["span"])[0]
            < cast("list[int]", value["span"])[1] <= prefix_bytes + expression_bytes):
        raise VelaError("syntax", 3, 1, "expected exactly one complete constant initializer")
    return declaration


def _console_value(elaborator: _Elaborator, declaration: Node,
                   value_type: ValueType) -> StaticEvaluation:
    result = elaborator.constant_value(declaration, {})
    normalized = elaborator.whnf(result.term)
    expected = "nat" if value_type == "Nat" else "bool"
    if normalized.kind != expected or elaborator.free(normalized):
        raise VelaError("inference", 1, 1, "constant did not reduce to a closed typed value")
    return StaticEvaluation(value_type, cast("int", normalized.value) if value_type == "Nat"
                            else bool(normalized.value))


def evaluate(source: bytes, parsed: object, expression: str, value_type: ValueType,
             *, parse: Callable[[bytes], object]) -> StaticEvaluation:
    """Reduce one source-bound console constant in the checked module's environment.

    The [mathematical console contract](../../docs/languages/vela/elaboration-prototype.md#commands-and-acceptance)
    retains the native parser and existing bounded constant reducer.
    """
    _, elaborator = _checked_elaboration(source, parsed)
    if value_type not in {"Nat", "bool"}:
        raise VelaError("type", 1, 1, "expression: expected Nat or bool result type")
    try:
        raw = expression.encode("utf-8")
    except UnicodeEncodeError as error:
        raise VelaError("encoding", 1, 1, "expression: invalid Unicode text") from error
    if len(raw) > 4096:
        raise VelaError("limit", 1, 1, "expression: exceeds 4096 UTF-8 bytes")
    prefix = f"module Playground;\npublic const {value_type} __vela_console_result =\n".encode()
    probe = prefix + raw + b"\n;"
    protocol = _Protocol(probe)
    try:
        declaration = _console_initializer(elaborator, protocol, parse(probe), len(prefix), len(raw))
    except VelaError as error:
        lines = expression.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        line = max(1, error.line - 2)
        column = error.column if line <= len(lines) else len(lines[-1]) + 1
        line = min(line, len(lines))
        column = min(column, len(lines[line - 1]) + 1)
        raise VelaError(error.kind, line, column, f"expression: {error.message}") from error
    except RecursionError as error:
        raise VelaError("limit", 1, 1, "expression: syntax nesting exceeds the host stack bound") from error
    elaborator.protocol = protocol
    try:
        return _console_value(elaborator, declaration, value_type)
    except VelaError as error:
        raise VelaError(error.kind, 1, 1, f"expression: {error.message}") from error
    except RecursionError as error:
        raise VelaError("limit", 1, 1, "expression: elaboration nesting exceeds the host stack bound") from error


