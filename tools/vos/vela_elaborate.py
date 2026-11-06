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
MAX_STRING_BYTES = 256


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
    "record": {"name", "generics", "parameters", "contracts", "declarations", "modifiers"},
    "property": {"name", "type", "contracts", "value", "modifiers"},
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
    "string": {"value"}, "interpolated_string": {"value"}, "member": {"value", "name"},
    "unit": set(), "tuple": {"values"}, "group": {"value"},
    "call": {"callee", "arguments"}, "generic_application": {"value", "arguments"},
    "argument": {"label", "value"},
    "binary": {"operator", "left", "right"}, "unary": {"operator", "value"},
    "is": {"value", "pattern"},
    "with_expression": {"value", "updates"}, "field_update": {"name", "value"},
    "operator": {"name"}, "type_expression": {"type"},
    "lambda": {"parameters", "body"}, "typed_lambda": {"signature", "body"},
    "let_expression": {"binding", "body"},
    "if_expression": {"condition", "then", "else"},
    "block": {"statements"}, "return": {"value"}, "expression_body": {"value"},
    "let": {"name", "type", "grade", "value"},
    "typed_local": {"name", "type", "grade", "value"},
    "let_pattern": {"pattern", "value"},
    "let_else": {"pattern", "value", "else"},
    "if": {"condition", "then", "else"},
    "match": {"value", "motive", "cases"}, "case": {"pattern", "statements"},
    "match_expression": {"value", "motive", "cases"},
    "expression_case": {"pattern", "value"}, "match_motive": {"name", "type"},
    "wildcard_pattern": set(), "binding_pattern": {"name"},
    "unit_pattern": set(), "group_pattern": {"pattern"},
    "tuple_pattern": {"patterns"}, "bool_pattern": {"value"},
    "nat_pattern": {"value", "suffix"}, "constructor_pattern": {"name", "arguments"},
    "labeled_pattern": {"label", "pattern"},
    "quantifier": {"quantifier", "parameters", "value"},
    "assert": {"value", "by"}, "proof": {"body"},
    "hole": {"name"},
}
_PATTERN_KINDS = {
    "wildcard_pattern", "binding_pattern", "unit_pattern", "group_pattern",
    "tuple_pattern", "bool_pattern", "nat_pattern", "constructor_pattern",
}
_PATTERN_ARGUMENT_KINDS = _PATTERN_KINDS | {"labeled_pattern"}
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
        if kind in {"definition", "function", "alias", "theorem", "lemma", "record", "property"}:
            if node.get("contracts") or node.get("cancel"):
                return  # These roles are refused by the mathematical consumer.
            modifiers = node["modifiers"]
            if not isinstance(modifiers, list) or any(not isinstance(item, str) for item in modifiers):
                raise self.error("protocol", "declaration modifiers must be a name list", node)
            for modifier in modifiers:
                cursor = self._token(node, cursor, cast("str", modifier).encode())
            if kind not in {"function", "property"}:
                cursor = self._token(node, cursor, cast("str", kind).encode())
            if kind in {"definition", "function", "property"}:
                cursor = self._child(node, span, cursor, node["type" if kind == "property" else "result"])
            cursor = self._child(node, span, cursor, node["name"])
            if kind != "property":
                cursor = self._generics(node, span, cursor)
            if kind not in {"alias", "property"}:
                cursor = self._list(node, span, cursor, node["parameters"])
            if kind in {"theorem", "lemma"}:
                cursor = self._token(node, cursor, b":")
                cursor = self._child(node, span, cursor, node["proposition"])
                if node["body"] is not None:
                    cursor = self._token(node, cursor, b"proof")
                    cursor = self._child(node, span, cursor, node["body"])
                else:
                    cursor = self._token(node, cursor, b";")
            elif kind == "record":
                after = trivia_end(self.source, cursor, block_comments=True)
                if self.source[after:after + 1] == b"{":
                    self._sequence_envelope(node, span, "declarations", after + 1, b"}")
                    return
                if node["declarations"]:
                    raise self.error("protocol", "semicolon record tail cannot carry member declarations", node)
                cursor = self._token(node, cursor, b";")
            elif kind in {"alias", "definition", "property"}:
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
        elif kind == "let_else":
            pattern = node["pattern"]
            if (not isinstance(pattern, dict)
                    or pattern.get("kind") not in {"unit_pattern", "group_pattern", "tuple_pattern", "constructor_pattern"}):
                raise self.error("protocol", "let_else requires a parenthesized or constructor pattern", node)
            if not isinstance(node["else"], dict) or node["else"].get("kind") != "block":
                raise self.error("protocol", "let_else requires a block else branch", node)
            cursor = self._token(node, cursor, b"let")
            cursor = self._child(node, span, cursor, pattern)
            cursor = self._token(node, cursor, b"=")
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b"else")
            cursor = self._child(node, span, cursor, node["else"])
        elif kind == "return":
            cursor = self._token(node, cursor, b"return")
            if node["value"] is not None:
                cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b";")
        elif kind == "assert":
            cursor = self._token(node, cursor, b"assert")
            cursor = self._child(node, span, cursor, node["value"])
            if node["by"] is not None:
                cursor = self._token(node, cursor, b"by")
                cursor = self._child(node, span, cursor, node["by"])
                if not isinstance(node["by"], dict) or node["by"].get("kind") != "block":
                    cursor = self._token(node, cursor, b";")
            else:
                cursor = self._token(node, cursor, b";")
        elif kind == "proof":
            if not isinstance(node["body"], dict) or node["body"].get("kind") != "block":
                raise self.error("protocol", "proof statement requires a block body", node)
            cursor = self._token(node, cursor, b"proof")
            cursor = self._child(node, span, cursor, node["body"])
        elif kind in {"if", "if_expression"}:
            cursor = self._token(node, cursor, b"if")
            cursor = self._token(node, cursor, b"(")
            cursor = self._child(node, span, cursor, node["condition"])
            cursor = self._token(node, cursor, b")")
            cursor = self._child(node, span, cursor, node["then"])
            if kind == "if_expression" or node["else"] is not None:
                if node["else"] is None:
                    raise self.error("protocol", "if_expression requires an else branch", node)
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
                    or any(not isinstance(item, dict) or item.get("kind") not in _PATTERN_ARGUMENT_KINDS for item in arguments)):
                raise self.error("protocol", "constructor_pattern arguments must be pattern nodes", node)
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._list(node, span, cursor, arguments)
        elif kind == "labeled_pattern":
            if not isinstance(node["pattern"], dict) or node["pattern"].get("kind") not in _PATTERN_KINDS:
                raise self.error("protocol", "labeled_pattern requires a pattern child", node)
            cursor = self._child(node, span, cursor, node["label"])
            cursor = self._token(node, cursor, b":")
            cursor = self._child(node, span, cursor, node["pattern"])
        elif kind in {"name", "hole"}:
            cursor = self._child(node, span, cursor, node["name"])
        elif kind == "binary":
            for field in ("left", "operator", "right"):
                cursor = self._child(node, span, cursor, node[field])
        elif kind == "unary":
            cursor = self._child(node, span, cursor, node["operator"])
            cursor = self._child(node, span, cursor, node["value"])
        elif kind == "is":
            if not isinstance(node["pattern"], dict) or node["pattern"].get("kind") not in _PATTERN_KINDS:
                raise self.error("protocol", "is expression requires a pattern child", node)
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b"is")
            cursor = self._child(node, span, cursor, node["pattern"])
        elif kind == "with_expression":
            updates = node["updates"]
            if (not isinstance(updates, list) or not updates
                    or any(not isinstance(item, dict) or item.get("kind") != "field_update" for item in updates)):
                raise self.error("protocol", "with_expression requires nonempty field_update children", node)
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b"with")
            cursor = self._list(node, span, cursor, updates, b"{", b"}")
        elif kind == "field_update":
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._token(node, cursor, b"=")
            cursor = self._child(node, span, cursor, node["value"])
        elif kind == "member":
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b".")
            cursor = self._child(node, span, cursor, node["name"])
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
        if kind in {"string", "interpolated_string"}:
            value = node["value"]
            if not isinstance(value, str) or self.source[span[0]:span[1]] != value.encode("utf-8"):
                raise self.error("protocol", "string literal differs from its source", node)
            if kind == "string" and (len(value) < 2 or not value.startswith('"') or not value.endswith('"')):
                raise self.error("protocol", "string literal lacks quotation delimiters", node)
            if kind == "interpolated_string" and (len(value) < 3 or not value.startswith('$"') or not value.endswith('"')):
                raise self.error("protocol", "interpolated string literal lacks quotation delimiters", node)
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
    value: bool | str = False
    args: tuple[_Pat, ...] = ()


@dataclass(frozen=True)
class _Row:
    patterns: tuple[_Pat, ...]
    bindings: tuple[tuple[str, _Binding], ...]
    arm: Node
    arm_index: int = 0


@dataclass(frozen=True)
class _RecordField:
    name: str
    var: _Term
    type: _Term
    proj_const: str


@dataclass(frozen=True)
class _RecordProperty:
    name: str
    self_var: _Term
    type: _Term
    prop_const: str


@dataclass
class _RecordInfo:
    name: str
    type_const: str
    ctor_const: str
    type_binding: _Binding
    ctor_binding: _Binding
    generic_vars: tuple[_Term, ...]
    fields: tuple[_RecordField, ...]
    properties: dict[str, _RecordProperty]


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
        self.records: dict[str, _RecordInfo] = {}
        self.records_by_type: dict[str, _RecordInfo] = {}
        self.records_by_ctor: dict[str, _RecordInfo] = {}
        self.record_projections: dict[str, tuple[_RecordInfo, int]] = {}
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
        self.constants["Refl"] = _Binding(_constant("Refl"), telescope((a, x), eq(x, x)), 1)
        self.constants["Symm"] = _Binding(
            _constant("Symm"), telescope((a, x, y), self.pi(eq(x, y), eq(y, x))), 3
        )
        self.constants["Trans"] = _Binding(
            _constant("Trans"), telescope((a, x, y, z), self.pi(eq(x, y), self.pi(eq(y, z), eq(x, z)))), 4
        )
        f = self.fresh(self.pi(a, b))
        congr_result = _apps(_constant("Eq"), b, _app(f, x), _app(f, y))
        self.constants["Congr"] = _Binding(
            _constant("Congr"), telescope((a, b, x, y, f), self.pi(eq(x, y), congr_result)), 4
        )
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
        vec_nat = _apps(_constant("Vec"), _NAT, n)
        tb = _app(_constant("TextBuilder"), n)
        bind("ByteLength", telescope((n,), self.pi(vec_nat, _NAT)), 1)
        bind("TextBuilder", telescope((n,), _SORT))
        bind("EmptyBuilder", telescope((n,), self.pi(_UNIT, tb, nullary=True)), 1)
        bind("Fits", telescope((n,), self.pi(tb, _BOOL)), 1)
        bind("Written", telescope((n,), self.pi(tb, _NAT)), 1)
        self.constants["TextBuilderVal"] = _Binding(
            _constant("TextBuilderVal"), telescope((n,), self.pi(_BOOL, self.pi(_NAT, tb))), 1
        )
        self.constants["FormatStep"] = _Binding(
            _constant("FormatStep"), telescope((n,), self.pi(tb, self.pi(_NAT, tb))), 1
        )
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
            rec_head, rec_args = self.spine(scrutinee)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if not record_info.fields and len(rec_args) == len(record_info.generic_vars) + 1:
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
            rec_head, rec_args = self.spine(scrutinee)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if record_info.fields and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields):
                    self.tick(True)
                    type_args = rec_args[:len(record_info.generic_vars)]
                    field_vals = rec_args[len(record_info.generic_vars):]
                    field_types = [
                        self._instantiate_record_type(record_info, type_args, rf.type)
                        for rf in record_info.fields
                    ]
                    left_val = field_vals[0]
                    if len(field_vals) == 1:
                        right_val = _term("unit")
                    else:
                        right_val = field_vals[-1]
                        right_type = field_types[-1]
                        for fv, ft in reversed(list(zip(field_vals[1:-1], field_types[1:-1], strict=True))):
                            right_val = _term("pair", ft, right_type, fv, right_val)
                            right_type = _term("prod", ft, right_type)
                    branch = term.args[2]
                    inner = self.substitute(branch.args[1], cast("int", branch.value), left_val)
                    return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), right_val))
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
        if isinstance(name, str) and name in self.record_projections:
            record_info, field_index = self.record_projections[name]
            if len(arguments) == len(record_info.generic_vars) + 1:
                rec_val = self.whnf(arguments[-1])
                rec_head, rec_args = self.spine(rec_val)
                if (rec_head == _constant(record_info.ctor_const)
                        and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)):
                    self.tick(True)
                    return self.whnf(rec_args[len(record_info.generic_vars) + field_index])
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
        if name == "ByteLength" and len(arguments) == 2:
            self.tick(True)
            return self.whnf(arguments[0])
        if name == "EmptyBuilder" and len(arguments) == 2 and self.whnf(arguments[1]).kind == "unit":
            self.tick(True)
            return _apps(
                _constant("TextBuilderVal"),
                self.whnf(arguments[0]),
                _term("bool", value=1),
                _term("nat", value=0),
            )
        if name in {"Fits", "Written"} and len(arguments) == 2:
            builder_head, builder_args = self.spine(self.whnf(arguments[1]))
            if builder_head == _constant("TextBuilderVal") and len(builder_args) == 3:
                self.tick(True)
                return self.whnf(builder_args[1] if name == "Fits" else builder_args[2])
        if name == "FormatStep" and len(arguments) == 3:
            cap = self.whnf(arguments[0])
            builder_head, builder_args = self.spine(self.whnf(arguments[1]))
            chunk = self.whnf(arguments[2])
            if (cap.kind == "nat" and chunk.kind == "nat"
                    and builder_head == _constant("TextBuilderVal") and len(builder_args) == 3):
                ok = self.whnf(builder_args[1])
                used = self.whnf(builder_args[2])
                if ok.kind == "bool" and used.kind == "nat":
                    self.tick(True)
                    total = cast("int", used.value) + cast("int", chunk.value)
                    if total > self.natural_limit():
                        raise self.fail("limit", "computed natural exceeds representation bound")
                    fits = int(bool(cast("int", ok.value)) and total <= cast("int", cap.value))
                    return _apps(
                        _constant("TextBuilderVal"),
                        cap,
                        _term("bool", value=fits),
                        _term("nat", value=total),
                    )
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
            if name == "+" and left.kind == "app" and left.args[0] == _constant("Succ"):
                self.tick(True)
                return _app(_constant("Succ"), self.whnf(_apps(_constant("+"), left.args[1], right)))
            if left.kind == "bool" and name in {"&&", "||", "==>"}:
                self.tick(True)
                if name == "&&":
                    return right if left.value else _term("bool", value=0)
                if name == "||":
                    return _term("bool", value=1) if left.value else right
                return right if left.value else _term("bool", value=1)
            l_kind, l_pred = self._peel_nat(left)
            r_kind, r_pred = self._peel_nat(right)
            if name == "-":
                if l_kind == "zero":
                    self.tick(True)
                    return _term("nat", value=0)
                if r_kind == "zero":
                    self.tick(True)
                    return left
                if l_kind == "succ" and r_kind == "succ" and l_pred is not None and r_pred is not None:
                    self.tick(True)
                    return self.whnf(_apps(_constant("-"), l_pred, r_pred))
            if name == "<=":
                if l_kind == "zero":
                    self.tick(True)
                    return _term("bool", value=1)
                if l_kind == "succ" and r_kind == "zero":
                    self.tick(True)
                    return _term("bool", value=0)
                if l_kind == "succ" and r_kind == "succ" and l_pred is not None and r_pred is not None:
                    self.tick(True)
                    return self.whnf(_apps(_constant("<="), l_pred, r_pred))
            if name == "<" and r_kind in {"zero", "succ"}:
                self.tick(True)
                return self.whnf(_apps(_constant("<="), _app(_constant("Succ"), left), right))
            if name == ">=" and (l_kind in {"zero", "succ"} or r_kind in {"zero", "succ"}):
                self.tick(True)
                return self.whnf(_apps(_constant("<="), right, left))
            if name == ">" and l_kind in {"zero", "succ"}:
                self.tick(True)
                return self.whnf(_apps(_constant("<="), _app(_constant("Succ"), right), left))
            if name in {"eq_nat", "ne_nat"}:
                if (l_kind == "zero" and r_kind == "succ") or (l_kind == "succ" and r_kind == "zero"):
                    self.tick(True)
                    return _term("bool", value=0 if name == "eq_nat" else 1)
                if l_kind == "succ" and r_kind == "succ" and l_pred is not None and r_pred is not None:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), l_pred, r_pred))
        if head.value == "if" and len(arguments) == 4:
            condition = self.whnf(arguments[1])
            if condition.kind == "bool":
                self.tick(True)
                return self.whnf(arguments[2] if condition.value else arguments[3])
        return term

    @staticmethod
    def _peel_nat(term: _Term) -> tuple[str, _Term | None]:
        if term.kind == "nat":
            amount = cast("int", term.value)
            return ("zero", None) if amount == 0 else ("succ", _term("nat", value=amount - 1))
        if term.kind == "app" and term.args[0] == _constant("Succ"):
            return "succ", term.args[1]
        return "other", None

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
        if node["kind"] == "if_expression":
            return self.if_expression(node, environment, expected).term
        if node["kind"] == "with_expression":
            return self.with_expression(node, environment, expected).term
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
                if arguments[0]["kind"] == "labeled_pattern":
                    raise self.fail("name", "constructor 'Succ' does not accept labeled pattern arguments", arguments[0])
                return _Pat("succ", node, args=(self._parse_pattern(arguments[0], seen),))
            if cname in self.records:
                record_info = self.records[cname]
                if len(arguments) != len(record_info.fields):
                    raise self.fail(
                        "type",
                        f"constructor '{cname}' expects {len(record_info.fields)} pattern arguments, got {len(arguments)}",
                        node,
                    )
                labeled = False
                sub_patterns: list[_Pat] = []
                for idx, arg_node in enumerate(arguments):
                    expected_field = record_info.fields[idx]
                    if arg_node["kind"] == "labeled_pattern":
                        labeled = True
                        spelling = self.name(arg_node["label"])
                        if spelling != expected_field.name:
                            raise self.fail(
                                "name",
                                f"expected pattern field label '{expected_field.name}', got '{spelling}'",
                                arg_node,
                            )
                        sub_patterns.append(self._parse_pattern(self.node(arg_node["pattern"]), seen))
                    else:
                        if labeled:
                            raise self.fail(
                                "name",
                                "positional pattern arguments cannot follow a labeled pattern argument",
                                arg_node,
                            )
                        sub_patterns.append(self._parse_pattern(arg_node, seen))
                return _Pat("record", node, value=cname, args=tuple(sub_patterns))
            if cname not in self.globals:
                raise self.fail("name", f"unknown constructor '{cname}'", node)
            if cname in {"VNil", "VCons", "FZero", "FSucc"}:
                raise self.fail("unsupported", f"indexed elimination over '{cname}' requires the full frontend", node)
            raise self.fail("type", f"'{cname}' is not a pattern constructor", node)
        raise self.fail("protocol", f"unexpected pattern node '{kind}'", node)

    def _instantiate_record_type(
        self, record_info: _RecordInfo, type_args: list[_Term], target_type: _Term
    ) -> _Term:
        result = target_type
        for gv, arg in zip(record_info.generic_vars, type_args, strict=True):
            result = self.substitute(result, cast("int", gv.value), arg)
        return result

    def _typecheck_pattern(
        self,
        pat: _Pat,
        expected_type: _Term,
        environment: dict[str, _Binding],
        pattern_bindings: dict[str, _Binding] | None = None,
    ) -> None:
        self.tick()
        self.site = pat.node
        if pattern_bindings is not None:
            for name in pat.names:
                pattern_bindings[name] = _Binding(self.fresh(expected_type), expected_type)
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
                self._typecheck_pattern(pat.args[0], _NAT, environment, pattern_bindings)
            return
        if pat.kind == "record":
            record_info = self.records[cast("str", pat.value)]
            type_args = [self.meta(self.types[cast("int", gv.value)], environment) for gv in record_info.generic_vars]
            expected_rec_type = _apps(_constant(record_info.type_const), *type_args)
            self.unify(expected_type, expected_rec_type)
            for sub_pat, rf in zip(pat.args, record_info.fields, strict=True):
                ftype = self._instantiate_record_type(record_info, type_args, rf.type)
                self._typecheck_pattern(sub_pat, ftype, environment, pattern_bindings)
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
            self._typecheck_pattern(pat.args[0], resolved.args[0], environment, pattern_bindings)
            self._typecheck_pattern(pat.args[1], resolved.args[1], environment, pattern_bindings)
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
        if pat.kind == "record":
            rec_type = self.whnf(current.type)
            _, type_args = self.spine(rec_type)
            record_info = self.records[cast("str", pat.value)]
            for sub_pat, rf in zip(pat.args, record_info.fields, strict=True):
                ftype = self._instantiate_record_type(record_info, type_args, rf.type)
                fterm = _apps(_constant(rf.proj_const), *type_args, current.term)
                self._bind_irrefutable(sub_pat, _Binding(fterm, ftype), extended)
        elif pat.kind == "pair":
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
              *, expression_arms: bool = True, facts: tuple[_Binding, ...] = (),
              refine_scrutinee: bool = False, expected_scrutinee_type: _Term | None = None,
              visited_arms: set[int] | None = None, synthetic: bool = False) -> _Binding:
        self.site = node
        value_node = self.node(node["value"])
        if expected_scrutinee_type is not None:
            scrutinee = _Binding(self.check(value_node, expected_scrutinee_type, environment), expected_scrutinee_type)
        else:
            scrutinee = self.expression(value_node, environment)
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
        elif (expected is not None and scrutinee.term.kind == "var"
              and cast("int", scrutinee.term.value) in self.free(expected)):
            motive_body = self.substitute(expected, cast("int", scrutinee.term.value), root_var)
        cases = self.nodes(node["cases"])
        rows: list[_Row] = []
        arm_pattern_bindings: list[dict[str, _Binding]] = []
        for arm_index, arm in enumerate(cases):
            self.node(arm, "expression_case" if expression_arms else "case")
            pat = self._parse_pattern(self.node(arm["pattern"]), set())
            bindings_for_arm: dict[str, _Binding] = {}
            self._typecheck_pattern(pat, scrutinee.type, environment, bindings_for_arm)
            arm_pattern_bindings.append(bindings_for_arm)
            rows.append(_Row((pat,), (), arm, arm_index))
        scrutinee_type = self.whnf(scrutinee.type)
        scrutinee_head, _ = self.spine(scrutinee_type)
        if (scrutinee_type not in {_UNIT, _BOOL, _NAT}
                and scrutinee_type.kind != "prod"
                and not (scrutinee_head.kind == "const" and scrutinee_head.value in self.records_by_type)):
            raise self.fail(
                "type",
                "match scrutinee must have type Nat, bool, Unit, a product or a record",
                value_node,
            )
        inferred_result: list[_Term | None] = [expected]
        local_visited: set[int] = set()

        def specialize_rows(active_rows: list[_Row], index: int, ctor_kind: str, ctor_term: _Term,
                            col_var_id: int, col_type: _Term, sub_count: int, *, bool_value: bool = False) -> list[_Row]:
            specialized: list[_Row] = []
            for row in active_rows:
                pat = row.patterns[index]
                updated_bindings = tuple(
                    (bname, _Binding(self.substitute(bval.term, col_var_id, ctor_term), bval.type))
                    for bname, bval in row.bindings
                )
                if pat.kind == "wild":
                    extra = tuple((name, _Binding(ctor_term, col_type)) for name in pat.names)
                    wilds = tuple(_Pat("wild", pat.node) for _ in range(sub_count))
                    specialized.append(_Row(
                        row.patterns[:index] + wilds + row.patterns[index + 1:],
                        updated_bindings + extra,
                        row.arm,
                        row.arm_index,
                    ))
                elif pat.kind == ctor_kind and (ctor_kind != "bool" or pat.value == bool_value):
                    specialized.append(_Row(
                        row.patterns[:index] + pat.args + row.patterns[index + 1:],
                        updated_bindings,
                        row.arm,
                        row.arm_index,
                    ))
            return specialized

        def compile_matrix(columns: list[tuple[_Term, _Term, _Term]], active_rows: list[_Row],
                           pattern_term: _Term) -> _Term:
            self.tick()
            if not active_rows:
                raise self.fail("type", "non-exhaustive match: missing pattern case", node)
            first = active_rows[0]
            if all(pat.kind == "wild" for pat in first.patterns):
                local_visited.add(first.arm_index)
                if visited_arms is not None:
                    visited_arms.add(first.arm_index)
                arm_env = dict(environment)
                leaf_pattern = pattern_term
                for col_var, col_scrutinee, _ in columns:
                    if col_var != col_scrutinee:
                        leaf_pattern = self.substitute(leaf_pattern, cast("int", col_var.value), col_scrutinee)
                if refine_scrutinee:
                    for env_name, env_binding in list(arm_env.items()):
                        if env_binding.term == scrutinee.term:
                            arm_env[env_name] = _Binding(
                                leaf_pattern,
                                scrutinee.type,
                                env_binding.generics,
                                env_binding.constant,
                            )
                        elif scrutinee.term.kind == "var" and cast("int", scrutinee.term.value) in self.free(env_binding.type):
                            arm_env[env_name] = _Binding(
                                env_binding.term,
                                self.substitute(env_binding.type, cast("int", scrutinee.term.value), leaf_pattern),
                                env_binding.generics,
                                env_binding.constant,
                            )
                for name, bound in first.bindings:
                    bound_term = bound.term
                    for col_var, col_scrutinee, _ in columns:
                        if col_var != col_scrutinee:
                            bound_term = self.substitute(bound_term, cast("int", col_var.value), col_scrutinee)
                    self.bind_local(arm_env, name, _Binding(bound_term, bound.type))
                for pat, (_, col_scrutinee, col_type) in zip(first.patterns, columns, strict=True):
                    for name in pat.names:
                        self.bind_local(arm_env, name, _Binding(col_scrutinee, col_type))
                arm = first.arm
                self.site = arm
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
                evaluated = self.block(block_node, arm_env, leaf_expected, facts=facts)
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
                    specialize_rows(active_rows, index, "unit", unit_term, col_var_id, _UNIT, 0),
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
                    specialize_rows(active_rows, index, "bool", true_term, col_var_id, _BOOL, 0, bool_value=True),
                    self.substitute(pattern_term, col_var_id, true_term),
                )
                no = compile_matrix(
                    without_index,
                    specialize_rows(active_rows, index, "bool", false_term, col_var_id, _BOOL, 0, bool_value=False),
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
                    specialize_rows(active_rows, index, "pair", pair_term, col_var_id, col_type, 2),
                    self.substitute(pattern_term, col_var_id, pair_term),
                )
                motive_return = (self.substitute(motive_body, root_var_id, pattern_term)
                                 if motive_body is not None else cast("_Term", inferred_result[0]))
                motive_lam = _term("lam", col_type, motive_return, value=col_var_id)
                branch_lam = _term("lam", left_type, _term("lam", right_type, body, value=right_var.value), value=left_var.value)
                return _term("pair_match", motive_lam, col_scrutinee, branch_lam)

            col_head, col_type_args = self.spine(col_type)
            if col_head.kind == "const" and isinstance(col_head.value, str) and col_head.value in self.records_by_type:
                record_info = self.records_by_type[col_head.value]
                field_types = [
                    self._instantiate_record_type(record_info, col_type_args, rf.type)
                    for rf in record_info.fields
                ]
                if not field_types:
                    ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, _term("unit"))
                    body = compile_matrix(
                        without_index,
                        specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, 0),
                        self.substitute(pattern_term, col_var_id, ctor_term),
                    )
                    if motive_body is None:
                        return body
                    motive_lam = _term(
                        "lam", col_type, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id
                    )
                    return _term("unit_match", motive_lam, col_scrutinee, body)
                if len(field_types) == 1:
                    fvar_0 = self.fresh(field_types[0])
                    dummy_unit_var = self.fresh(_UNIT)
                    ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, fvar_0)
                    sub_columns = [(fvar_0, fvar_0, field_types[0])]
                    body = compile_matrix(
                        columns[:index] + sub_columns + columns[index + 1:],
                        specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, 1),
                        self.substitute(pattern_term, col_var_id, ctor_term),
                    )
                    motive_return = (
                        self.substitute(motive_body, root_var_id, pattern_term)
                        if motive_body is not None
                        else cast("_Term", inferred_result[0])
                    )
                    motive_lam = _term("lam", col_type, motive_return, value=col_var_id)
                    branch_lam = _term(
                        "lam",
                        field_types[0],
                        _term("lam", _UNIT, body, value=dummy_unit_var.value),
                        value=fvar_0.value,
                    )
                    return _term("pair_match", motive_lam, col_scrutinee, branch_lam)
                field_vars = [self.fresh(ft) for ft in field_types]
                ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, *field_vars)
                sub_columns = [(fv, fv, ft) for fv, ft in zip(field_vars, field_types, strict=True)]
                body = compile_matrix(
                    columns[:index] + sub_columns + columns[index + 1:],
                    specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, len(field_vars)),
                    self.substitute(pattern_term, col_var_id, ctor_term),
                )
                tail_types: list[_Term] = [field_types[-1]]
                for ft in reversed(field_types[1:-1]):
                    tail_types.append(_term("prod", ft, tail_types[-1]))
                tail_types.reverse()
                tail_vars: list[_Term] = [
                    self.fresh(tail_types[k]) for k in range(len(field_types) - 2)
                ] + [field_vars[-1]]
                curr_body = body
                for k in range(len(field_types) - 2, -1, -1):
                    left_var = field_vars[k]
                    left_type = field_types[k]
                    right_var = tail_vars[k]
                    right_type = tail_types[k]
                    if k == 0:
                        scrut = col_scrutinee
                        scrut_var_id = col_var_id
                        scrut_type = col_type
                        motive_return = (
                            self.substitute(motive_body, root_var_id, pattern_term)
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                    else:
                        scrut = tail_vars[k - 1]
                        scrut_var_id = cast("int", scrut.value)
                        scrut_type = tail_types[k - 1]
                        motive_return = cast("_Term", inferred_result[0])
                    motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                    branch_lam = _term(
                        "lam",
                        left_type,
                        _term("lam", right_type, curr_body, value=right_var.value),
                        value=left_var.value,
                    )
                    curr_body = _term("pair_match", motive_lam, scrut, branch_lam)
                return curr_body

            if col_type == _NAT:
                zero_term = _term("nat", value=0)
                zero_body = compile_matrix(
                    without_index,
                    specialize_rows(active_rows, index, "zero", zero_term, col_var_id, _NAT, 0),
                    self.substitute(pattern_term, col_var_id, zero_term),
                )
                pred_var = self.fresh(_NAT)
                succ_term = _app(_constant("Succ"), pred_var)
                sub_columns = [(pred_var, pred_var, _NAT)]
                succ_body = compile_matrix(
                    columns[:index] + sub_columns + columns[index + 1:],
                    specialize_rows(active_rows, index, "succ", succ_term, col_var_id, _NAT, 1),
                    self.substitute(pattern_term, col_var_id, succ_term),
                )
                motive_return = (self.substitute(motive_body, root_var_id, pattern_term)
                                 if motive_body is not None else cast("_Term", inferred_result[0]))
                motive_lam = _term("lam", _NAT, motive_return, value=col_var_id)
                succ_lam = _term("lam", _NAT, succ_body, value=pred_var.value)
                return _term("nat_match", motive_lam, col_scrutinee, zero_body, succ_lam)

            raise self.fail("type", "match column must have type Nat, bool, Unit, a product or a record", node)

        term = compile_matrix([(root_var, scrutinee.term, scrutinee_type)], rows, root_var)
        result_type = (self.substitute(motive_body, root_var_id, scrutinee.term)
                       if motive_body is not None else cast("_Term", inferred_result[0]))
        if not synthetic:
            for arm_index, arm in enumerate(cases):
                if arm_index in local_visited:
                    continue
                arm_env = dict(environment)
                for bname, bval in arm_pattern_bindings[arm_index].items():
                    self.bind_local(arm_env, bname, bval)
                self.site = arm
                if expression_arms:
                    self.check(self.node(arm["value"]), result_type, arm_env)
                else:
                    block_node = {"kind": "block", "span": arm["span"], "statements": arm["statements"]}
                    self.block(block_node, arm_env, result_type, facts=facts)
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

    def _try_unify(self, left: _Term, right: _Term) -> bool:
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        try:
            self.unify(left, right)
        except VelaError as error:
            if error.kind != "type":
                raise
            self.metas = saved
            return False
        else:
            return True

    def _is_prop_type(self, value_type: _Term) -> bool:
        return self.whnf(self.infer(value_type)) == _PROP

    def _extract_equality(self, prop: _Term) -> tuple[_Term, _Term, _Term] | None:
        head, args = self.spine(self.resolve(prop))
        if head == _constant("Eq") and len(args) == 3:
            return args[0], args[1], args[2]
        head, args = self.spine(self.whnf(prop))
        if head == _constant("Eq") and len(args) == 3:
            return args[0], args[1], args[2]
        return None

    def _try_congruence(
        self,
        goal_type: _Term,
        lhs: _Term,
        rhs: _Term,
        eq_type: _Term,
        u: _Term,
        v: _Term,
        proof_term: _Term,
    ) -> _Term | None:
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        z = self.fresh(eq_type)

        def build_ctx(sub_l: _Term, sub_r: _Term) -> tuple[_Term | None, bool]:
            sub_l = self.resolve(sub_l)
            sub_r = self.resolve(sub_r)
            if sub_l == u and sub_r == v:
                return z, True
            if (sub_l != lhs or sub_r != rhs) and (
                self._try_unify(self.infer(sub_l), eq_type)
                and self._try_unify(sub_l, u)
                and self._try_unify(sub_r, v)
            ):
                return z, True
            if (sub_l.kind == sub_r.kind
                    and sub_l.value == sub_r.value
                    and len(sub_l.args) == len(sub_r.args)
                    and sub_l.kind not in {"pi", "lam", "let"}):
                child_ctxs: list[_Term] = []
                any_replaced = False
                ok = True
                for c_l, c_r in zip(sub_l.args, sub_r.args, strict=True):
                    c_ctx, c_rep = build_ctx(c_l, c_r)
                    if c_ctx is None:
                        ok = False
                        break
                    child_ctxs.append(c_ctx)
                    any_replaced = any_replaced or c_rep
                if ok and any_replaced:
                    return _Term(sub_l.kind, sub_l.value, tuple(child_ctxs)), True
            if self._try_unify(sub_l, sub_r):
                return sub_l, False
            return None, False

        ctx, replaced = build_ctx(lhs, rhs)
        if not replaced or ctx is None or ctx == z:
            self.metas = saved
            return None
        fn = _term("lam", eq_type, ctx, value=z.value)
        return _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)

    def _equality_edges(
        self, goal_type: _Term, facts: tuple[_Binding, ...]
    ) -> list[tuple[int, _Term, _Term, _Term]]:
        edges: list[tuple[int, _Term, _Term, _Term]] = []
        for idx, fact in enumerate(facts):
            extracted = self._extract_equality(fact.type)
            if extracted is None:
                continue
            eq_type, u, v = extracted
            if not self._try_unify(eq_type, goal_type):
                continue
            edges.append((idx, u, v, fact.term))
            if u != v:
                edges.append((idx, v, u, _apps(_constant("Symm"), goal_type, u, v, fact.term)))
        return edges

    def _chain_sequence(
        self, goal_type: _Term, lhs: _Term, rhs: _Term, sequence: tuple[_Binding, ...]
    ) -> _Term | None:
        if len(sequence) < 2:
            return None
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        steps: list[tuple[_Term, _Term, _Term]] = []
        current = lhs
        for fact in sequence:
            extracted = self._extract_equality(fact.type)
            if extracted is None:
                self.metas = saved
                return None
            eq_type, u, v = extracted
            if not self._try_unify(eq_type, goal_type):
                self.metas = saved
                return None
            if u == current:
                steps.append((u, v, fact.term))
                current = v
            elif v == current:
                steps.append((v, u, _apps(_constant("Symm"), goal_type, u, v, fact.term)))
                current = u
            elif self._try_unify(u, current):
                steps.append((current, v, fact.term))
                current = v
            elif self._try_unify(v, current):
                steps.append((current, u, _apps(_constant("Symm"), goal_type, u, v, fact.term)))
                current = u
            else:
                self.metas = saved
                return None
        if current != rhs and not self._try_unify(current, rhs):
            self.metas = saved
            return None
        acc_u, acc_v, acc_term = steps[0]
        for _, next_v, next_term in steps[1:]:
            acc_term = _apps(_constant("Trans"), goal_type, acc_u, acc_v, next_v, acc_term, next_term)
            acc_v = next_v
        return acc_term

    def _prove_proposition(
        self,
        goal: _Term,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
        node: Node,
        *,
        allow_refl: bool = True,
        include_env: bool = True,
    ) -> _Term:
        self.tick()
        self.site = node
        env_facts = (
            tuple(
                binding for binding in environment.values()
                if self._is_prop_type(binding.type)
                and not any(binding.term == existing.term for existing in facts)
            )
            if include_env
            else ()
        )
        all_facts = (*facts, *env_facts)
        for fact in reversed(all_facts):
            if fact.type == goal:
                return fact.term
        goal_whnf = self.whnf(goal)
        if goal_whnf.kind == "pi" and cast("int", goal_whnf.value) not in self.nullary_parameters:
            for fact in reversed(all_facts):
                if self._try_unify(fact.type, goal):
                    return fact.term
            var_id = cast("int", goal_whnf.value)
            domain = goal_whnf.args[0]
            var = self.fresh(domain)
            child_env = dict(environment)
            child_facts = list(facts)
            if var_id in self.parameter_names:
                param_name = self.parameter_names[var_id]
                self.parameter_names[cast("int", var.value)] = param_name
                self.bind_local(child_env, param_name, _Binding(var, domain))
            if self._is_prop_type(domain):
                child_facts.append(_Binding(var, domain))
            codomain = self.substitute(goal_whnf.args[1], var_id, var)
            body_term = self._prove_proposition(
                codomain,
                child_env,
                tuple(child_facts),
                node,
                allow_refl=allow_refl,
                include_env=include_env,
            )
            return _term("lam", domain, body_term, value=var.value)

        goal_eq = self._extract_equality(goal)
        if goal_eq is not None:
            goal_type, lhs, rhs = goal_eq
            edges = self._equality_edges(goal_type, all_facts)
            for _, u, v, p in reversed(edges):
                if u == lhs and v == rhs:
                    return p
            for i1, u1, v1, p1 in edges:
                if u1 != lhs:
                    continue
                for i2, u2, v2, p2 in edges:
                    if v1 == u2 and v2 == rhs and (i1 != i2 or u1 != v1):
                        return _apps(_constant("Trans"), goal_type, lhs, v1, rhs, p1, p2)
                    if v1 == u2 and i1 != i2:
                        for i3, u3, v3, p3 in edges:
                            if v2 == u3 and v3 == rhs and i3 not in {i1, i2}:
                                step12 = _apps(_constant("Trans"), goal_type, lhs, v1, v2, p1, p2)
                                return _apps(_constant("Trans"), goal_type, lhs, v2, rhs, step12, p3)
            for _, u, v, p in reversed(edges):
                if u != lhs or v != rhs:
                    congr = self._try_congruence(goal_type, lhs, rhs, goal_type, u, v, p)
                    if congr is not None:
                        return congr
            for fact in reversed(all_facts):
                extracted = self._extract_equality(fact.type)
                if extracted is None:
                    continue
                eq_type, u, v = extracted
                if u != lhs or v != rhs:
                    congr = self._try_congruence(goal_type, lhs, rhs, eq_type, u, v, fact.term)
                    if congr is not None:
                        return congr
                    if u != v:
                        sym_p = _apps(_constant("Symm"), eq_type, u, v, fact.term)
                        congr_sym = self._try_congruence(goal_type, lhs, rhs, eq_type, v, u, sym_p)
                        if congr_sym is not None:
                            return congr_sym
            for _, u, v, p in reversed(edges):
                saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._try_unify(u, lhs) and self._try_unify(v, rhs):
                    return p
                self.metas = saved
            for i1, u1, v1, p1 in edges:
                saved1 = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if not self._try_unify(u1, lhs):
                    self.metas = saved1
                    continue
                for i2, u2, v2, p2 in edges:
                    if i1 == i2:
                        continue
                    saved2 = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                    if self._try_unify(v1, u2) and self._try_unify(v2, rhs):
                        return _apps(_constant("Trans"), goal_type, lhs, v1, rhs, p1, p2)
                    self.metas = saved2
                self.metas = saved1
            if allow_refl and self._try_unify(lhs, rhs):
                return _apps(_constant("Refl"), goal_type, lhs)

        for fact in reversed(all_facts):
            if self._try_unify(fact.type, goal):
                return fact.term

        raise self.fail(
            "type",
            "assertion could not be established; terms or dependent indices are not definitionally equal",
            node,
        )

    def asserted_proposition(self, node: Node, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "group":
            return self.asserted_proposition(self.node(node["value"]), environment)
        if node["kind"] == "binary":
            operator = self.operator(node["operator"])
            if operator == "==":
                return self.proposition(node, environment)
            if operator == "==>":
                domain = self.asserted_proposition(self.node(node["left"]), environment)
                return self.pi(domain, self.asserted_proposition(self.node(node["right"]), environment))
        if node["kind"] == "quantifier":
            if node["quantifier"] != "forall":
                raise self.fail("unsupported", "only universal propositions are supported", node)
            variables, extended = self.telescope([], self.nodes(node["parameters"]), environment)
            return self.wrap("pi", variables, self.asserted_proposition(self.node(node["value"]), extended))
        value = self.expression(node, environment)
        value_type = self.whnf(value.type)
        if value_type == _PROP:
            return value.term
        if value_type == _BOOL:
            return _apps(_constant("Eq"), _BOOL, value.term, _term("bool", value=1))
        self.unify(value.type, _PROP)
        return value.term

    def _elaborate_by_expression(
        self,
        goal: _Term,
        by_node: Node,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
        assert_node: Node,
    ) -> _Term:
        self.site = by_node
        if by_node["kind"] in {"lambda", "typed_lambda", "match_expression", "if_expression"}:
            return self.check(by_node, goal, environment)
        justification = self.expression(by_node, environment)
        goal_whnf = self.whnf(goal)
        while self.whnf(justification.type).kind == "pi" and goal_whnf.kind != "pi":
            pi_type = self.whnf(justification.type)
            if cast("int", pi_type.value) in self.nullary_parameters:
                break
            domain = pi_type.args[0]
            if self._is_prop_type(domain):
                arg = self._prove_proposition(domain, environment, facts, by_node)
            else:
                arg = self.meta(domain, environment)
            justification = _Binding(
                _app(justification.term, arg),
                self.substitute(pi_type.args[1], cast("int", pi_type.value), arg),
            )
        if not self._is_prop_type(justification.type):
            raise self.fail("type", "assert 'by' justification must be a proof of a proposition", by_node)
        goal_eq = self._extract_equality(goal)
        just_eq = self._extract_equality(justification.type)
        if goal_eq is not None and just_eq is not None:
            goal_type, lhs, rhs = goal_eq
            eq_type, u, v = just_eq
            if u != lhs or v != rhs:
                congr = self._try_congruence(goal_type, lhs, rhs, eq_type, u, v, justification.term)
                if congr is not None:
                    return congr
                if u != v:
                    sym_p = _apps(_constant("Symm"), eq_type, u, v, justification.term)
                    congr_sym = self._try_congruence(goal_type, lhs, rhs, eq_type, v, u, sym_p)
                    if congr_sym is not None:
                        return congr_sym
        if self._try_unify(justification.type, goal):
            return justification.term
        if goal_eq is not None and just_eq is not None:
            goal_type, lhs, rhs = goal_eq
            eq_type, u, v = just_eq
            saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            if (self._try_unify(eq_type, goal_type)
                    and self._try_unify(v, lhs)
                    and self._try_unify(u, rhs)):
                return _apps(_constant("Symm"), goal_type, u, v, justification.term)
            self.metas = saved
            edges = self._equality_edges(goal_type, facts)
            if self._try_unify(eq_type, goal_type):
                just_orientations = [(u, v, justification.term)]
                if u != v:
                    just_orientations.append((v, u, _apps(_constant("Symm"), goal_type, u, v, justification.term)))
                for ju, jv, jp in just_orientations:
                    if ju == lhs or self._try_unify(ju, lhs):
                        for _, eu, ev, ep in edges:
                            if (jv == eu or self._try_unify(jv, eu)) and (ev == rhs or self._try_unify(ev, rhs)):
                                return _apps(_constant("Trans"), goal_type, lhs, jv, rhs, jp, ep)
                    if jv == rhs or self._try_unify(jv, rhs):
                        for _, eu, ev, ep in edges:
                            if (eu == lhs or self._try_unify(eu, lhs)) and (ev == ju or self._try_unify(ev, ju)):
                                return _apps(_constant("Trans"), goal_type, lhs, ju, rhs, ep, jp)
        raise self.fail("type", "assert justification does not establish the asserted proposition", assert_node)

    def _elaborate_by_block(
        self,
        goal: _Term,
        by_node: Node,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
        assert_node: Node,
    ) -> _Term:
        self.node(by_node, "block")
        statements = self.nodes(by_node["statements"])
        if not statements:
            raise self.fail("type", "empty 'by' block cannot justify assertion", by_node)
        child_env = dict(environment)
        active_facts: list[_Binding] = list(facts)
        child_facts: list[_Binding] = []
        peeled_vars: list[_Term] = []
        target_goal = goal
        while self._is_prop_type(target_goal):
            resolved = self.whnf(target_goal)
            if resolved.kind != "pi" or cast("int", resolved.value) in self.nullary_parameters:
                break
            var_id = cast("int", resolved.value)
            if var_id in self.parameter_names:
                param_name = self.parameter_names[var_id]
                if param_name in child_env:
                    break
                var = self.fresh(resolved.args[0])
                self.parameter_names[cast("int", var.value)] = param_name
                self.bind_local(child_env, param_name, _Binding(var, resolved.args[0]))
                if self._is_prop_type(resolved.args[0]):
                    active_facts.append(_Binding(var, resolved.args[0]))
            else:
                var = self.fresh(resolved.args[0])
                active_facts.append(_Binding(var, resolved.args[0]))
            peeled_vars.append(var)
            target_goal = self.substitute(resolved.args[1], var_id, var)

        def finish(term: _Term) -> _Term:
            return self.wrap("lam", peeled_vars, term) if peeled_vars else term

        for index, statement in enumerate(statements):
            self.site = statement
            kind = statement["kind"]
            if kind in {"let", "typed_local", "let_pattern", "constant_local"}:
                previous_keys = set(child_env)
                child_env = self.local(statement, child_env)
                for new_key in set(child_env) - previous_keys:
                    bound = child_env[new_key]
                    if self._is_prop_type(bound.type):
                        child_facts.append(bound)
                continue
            if kind == "assert":
                fact = self._elaborate_assert(statement, child_env, (*active_facts, *child_facts))
                child_facts.append(fact)
                continue
            if kind == "proof":
                sub_facts = self._elaborate_proof_statement(
                    self.node(statement["body"], "block"), child_env, (*active_facts, *child_facts)
                )
                child_facts.extend(sub_facts)
                continue
            if kind == "let_else":
                if index == len(statements) - 1:
                    raise self.fail("type", "a pure block requires an explicit terminal return after let-else", statement)
                synthetic = {"kind": "block", "span": by_node["span"], "statements": statements[index:]}
                evaluated = self.block(synthetic, child_env, target_goal, facts=(*active_facts, *child_facts))
                return finish(evaluated.term)
            if index == len(statements) - 1 and kind in {"match", "if", "return", "block"}:
                synthetic = {"kind": "block", "span": by_node["span"], "statements": [statement]}
                evaluated = self.block(synthetic, child_env, target_goal, facts=(*active_facts, *child_facts))
                return finish(evaluated.term)
            raise self.fail("unsupported", f"statement '{kind}' is not supported in an assert 'by' block", statement)

        if not child_facts:
            raise self.fail("type", "assert 'by' block contains no proof steps", by_node)
        goal_eq = self._extract_equality(target_goal)
        if goal_eq is not None and len(child_facts) >= 2:
            goal_type, lhs, rhs = goal_eq
            chained = self._chain_sequence(goal_type, lhs, rhs, tuple(child_facts))
            if chained is not None:
                return finish(chained)
        return finish(
            self._prove_proposition(
                target_goal,
                child_env,
                tuple(child_facts),
                assert_node,
                allow_refl=False,
                include_env=False,
            )
        )

    def _elaborate_assert(
        self, node: Node, environment: dict[str, _Binding], facts: tuple[_Binding, ...]
    ) -> _Binding:
        self.site = node
        goal = self.asserted_proposition(self.node(node["value"]), environment)
        by_raw = node["by"]
        if by_raw is None:
            term = self._prove_proposition(goal, environment, facts, node)
        else:
            by_node = self.node(by_raw)
            if by_node["kind"] == "block":
                term = self._elaborate_by_block(goal, by_node, environment, facts, node)
            else:
                term = self._elaborate_by_expression(goal, by_node, environment, facts, node)
        return _Binding(term, goal)

    def _elaborate_proof_statement(
        self, body_node: Node, environment: dict[str, _Binding], facts: tuple[_Binding, ...]
    ) -> list[_Binding]:
        self.node(body_node, "block")
        statements = self.nodes(body_node["statements"])
        extended = dict(environment)
        new_facts: list[_Binding] = []
        for statement in statements:
            self.site = statement
            kind = statement["kind"]
            if kind in {"let", "typed_local", "let_pattern", "constant_local"}:
                previous_keys = set(extended)
                extended = self.local(statement, extended)
                for new_key in set(extended) - previous_keys:
                    bound = extended[new_key]
                    if self._is_prop_type(bound.type):
                        new_facts.append(bound)
                continue
            if kind == "assert":
                new_facts.append(self._elaborate_assert(statement, extended, (*facts, *new_facts)))
                continue
            if kind == "proof":
                sub = self._elaborate_proof_statement(
                    self.node(statement["body"], "block"), extended, (*facts, *new_facts)
                )
                new_facts.extend(sub)
                continue
            raise self.fail("unsupported", f"statement '{kind}' requires the full frontend", statement)
        return new_facts

    @staticmethod
    def _unwrap_group(node: Node) -> Node:
        while node["kind"] == "group" and isinstance(node.get("value"), dict):
            node = cast("Node", node["value"])
        return node

    def block(self, node: Node, environment: dict[str, _Binding], expected: _Term | None = None,
              *, facts: tuple[_Binding, ...] = ()) -> _Binding:
        self.node(node, "block")
        statements = self.nodes(node["statements"])
        extended = dict(environment)
        active_facts: list[_Binding] = list(facts)
        statement_facts: list[_Binding] = []
        peeled_vars: list[_Term] = []
        returns_lambda = False
        final_assert_value: Node | None = None
        if statements:
            last = statements[-1]
            if last["kind"] == "return" and isinstance(last.get("value"), dict):
                unwrapped = self._unwrap_group(cast("Node", last["value"]))
                returns_lambda = unwrapped["kind"] in {"lambda", "typed_lambda"}
            elif last["kind"] == "assert" and isinstance(last.get("value"), dict):
                final_assert_value = self._unwrap_group(cast("Node", last["value"]))
        if not returns_lambda:
            while expected is not None and self._is_prop_type(expected):
                resolved_expected = self.whnf(expected)
                if (resolved_expected.kind != "pi"
                        or cast("int", resolved_expected.value) in self.nullary_parameters):
                    break
                var_id = cast("int", resolved_expected.value)
                if var_id in self.parameter_names:
                    if final_assert_value is not None and final_assert_value["kind"] == "quantifier":
                        break
                    param_name = self.parameter_names[var_id]
                    if param_name in extended:
                        break
                    var = self.fresh(resolved_expected.args[0])
                    self.parameter_names[cast("int", var.value)] = param_name
                    self.bind_local(extended, param_name, _Binding(var, resolved_expected.args[0]))
                    if self._is_prop_type(resolved_expected.args[0]):
                        active_facts.append(_Binding(var, resolved_expected.args[0]))
                else:
                    if (final_assert_value is not None
                            and final_assert_value["kind"] == "binary"
                            and isinstance(final_assert_value.get("operator"), dict)
                            and cast("Node", final_assert_value["operator"]).get("text") == "==>"):
                        break
                    var = self.fresh(resolved_expected.args[0])
                    active_facts.append(_Binding(var, resolved_expected.args[0]))
                peeled_vars.append(var)
                expected = self.substitute(resolved_expected.args[1], var_id, var)

        def finish(result: _Binding) -> _Binding:
            if not peeled_vars:
                return result
            return _Binding(
                self.wrap("lam", peeled_vars, result.term),
                self.wrap("pi", peeled_vars, result.type),
            )

        for index, statement in enumerate(statements):
            self.site = statement
            kind = statement["kind"]
            if kind in {"let", "typed_local", "let_pattern", "constant_local"}:
                previous_keys = set(extended)
                extended = self.local(statement, extended)
                for new_key in set(extended) - previous_keys:
                    bound = extended[new_key]
                    if self._is_prop_type(bound.type):
                        statement_facts.append(bound)
                continue
            if kind == "assert":
                fact = self._elaborate_assert(statement, extended, (*active_facts, *statement_facts))
                statement_facts.append(fact)
                if index == len(statements) - 1 and expected is not None and self._is_prop_type(expected):
                    term = self._prove_proposition(
                        expected,
                        extended,
                        tuple(statement_facts),
                        statement,
                        allow_refl=False,
                        include_env=False,
                    )
                    return finish(_Binding(term, expected))
                continue
            if kind == "proof":
                sub_facts = self._elaborate_proof_statement(
                    self.node(statement["body"], "block"), extended, (*active_facts, *statement_facts)
                )
                statement_facts.extend(sub_facts)
                if index == len(statements) - 1 and expected is not None and self._is_prop_type(expected):
                    term = self._prove_proposition(
                        expected,
                        extended,
                        tuple(statement_facts),
                        statement,
                        allow_refl=False,
                        include_env=False,
                    )
                    return finish(_Binding(term, expected))
                continue
            if kind == "let_else":
                if index == len(statements) - 1:
                    raise self.fail("type", "a pure block requires an explicit terminal return after let-else", statement)
                else_block = self.node(statement["else"], "block")
                else_statements = self.nodes(else_block["statements"])
                rest_statements = statements[index + 1:]
                combined_facts = (*active_facts, *statement_facts)
                visited_arms: set[int] = set()
                synthetic_match: Node = {
                    "kind": "match",
                    "span": node["span"],
                    "value": statement["value"],
                    "motive": None,
                    "cases": [
                        {
                            "kind": "case",
                            "span": node["span"],
                            "pattern": statement["pattern"],
                            "statements": rest_statements,
                        },
                        {
                            "kind": "case",
                            "span": else_block["span"],
                            "pattern": {"kind": "wildcard_pattern", "span": else_block["span"]},
                            "statements": else_statements,
                        },
                    ],
                }
                result = self.match(
                    synthetic_match,
                    extended,
                    expected,
                    expression_arms=False,
                    facts=combined_facts,
                    refine_scrutinee=True,
                    visited_arms=visited_arms,
                    synthetic=True,
                )
                if 1 not in visited_arms:
                    self.block(else_block, extended, result.type, facts=combined_facts)
                return finish(result)
            if index != len(statements) - 1:
                raise self.fail("unsupported", "a returning terminal must be the final statement")
            if kind == "return":
                if statement["value"] is None:
                    value = _Binding(_term("unit"), _UNIT)
                    if expected is not None:
                        self.unify(value.type, expected)
                    return finish(value)
                value_node = self.node(statement["value"])
                result = (
                    self.expression(value_node, extended)
                    if expected is None
                    else _Binding(self.check(value_node, expected, extended), expected)
                )
                return finish(result)
            if kind == "if":
                if statement["else"] is None:
                    raise self.fail("type", "every conditional branch must return")
                combined_facts = (*active_facts, *statement_facts)
                cond_raw = self.node(statement["condition"])
                cond_unwrapped = self._unwrap_group(cond_raw)
                if cond_unwrapped["kind"] == "is":
                    return finish(
                        self._if_is(
                            cond_unwrapped,
                            self.node(statement["then"]),
                            self.node(statement["else"]),
                            extended,
                            expected,
                            expression_branches=False,
                            facts=combined_facts,
                            site_node=statement,
                        )
                    )
                condition = self.check(cond_raw, _BOOL, extended)
                yes = self.branch(self.node(statement["then"]), extended, expected, facts=combined_facts)
                no = self.branch(self.node(statement["else"]), extended, yes.type, facts=combined_facts)
                return finish(_Binding(_term("if", yes.type, condition, yes.term, no.term), yes.type))
            if kind == "match":
                return finish(
                    self.match(
                        statement,
                        extended,
                        expected,
                        expression_arms=False,
                        facts=(*active_facts, *statement_facts),
                    )
                )
            if kind == "block":
                return finish(
                    self.block(statement, extended, expected, facts=(*active_facts, *statement_facts))
                )
            raise self.fail("unsupported", f"statement '{kind}' requires the full frontend")
        raise self.fail("type", "a pure block requires an explicit terminal return", node)

    def branch(self, node: Node, environment: dict[str, _Binding], expected: _Term | None,
               *, facts: tuple[_Binding, ...] = ()) -> _Binding:
        if node["kind"] == "block":
            return self.block(node, environment, expected, facts=facts)
        return self.block(
            {"kind": "block", "span": node["span"], "statements": [node]},
            environment,
            expected,
            facts=facts,
        )

    def _if_is(
        self,
        is_node: Node,
        then_node: Node,
        else_node: Node,
        environment: dict[str, _Binding],
        expected: _Term | None = None,
        *,
        expression_branches: bool = True,
        facts: tuple[_Binding, ...] = (),
        site_node: Node,
    ) -> _Binding:
        visited_arms: set[int] = set()
        if expression_branches:
            synthetic: Node = {
                "kind": "match_expression",
                "span": site_node["span"],
                "value": is_node["value"],
                "motive": None,
                "cases": [
                    {
                        "kind": "expression_case",
                        "span": then_node["span"],
                        "pattern": is_node["pattern"],
                        "value": then_node,
                    },
                    {
                        "kind": "expression_case",
                        "span": else_node["span"],
                        "pattern": {"kind": "wildcard_pattern", "span": else_node["span"]},
                        "value": else_node,
                    },
                ],
            }
            result = self.match(
                synthetic,
                environment,
                expected,
                expression_arms=True,
                facts=facts,
                refine_scrutinee=True,
                visited_arms=visited_arms,
                synthetic=True,
            )
            if 1 not in visited_arms:
                self.check(else_node, result.type, environment)
            return result
        then_stmts = self.nodes(then_node["statements"]) if then_node["kind"] == "block" else [then_node]
        else_stmts = self.nodes(else_node["statements"]) if else_node["kind"] == "block" else [else_node]
        synthetic = {
            "kind": "match",
            "span": site_node["span"],
            "value": is_node["value"],
            "motive": None,
            "cases": [
                {
                    "kind": "case",
                    "span": then_node["span"],
                    "pattern": is_node["pattern"],
                    "statements": then_stmts,
                },
                {
                    "kind": "case",
                    "span": else_node["span"],
                    "pattern": {"kind": "wildcard_pattern", "span": else_node["span"]},
                    "statements": else_stmts,
                },
            ],
        }
        result = self.match(
            synthetic,
            environment,
            expected,
            expression_arms=False,
            facts=facts,
            refine_scrutinee=True,
            visited_arms=visited_arms,
            synthetic=True,
        )
        if 1 not in visited_arms:
            self.branch(else_node, environment, result.type, facts=facts)
        return result

    def if_expression(
        self, node: Node, environment: dict[str, _Binding], expected: _Term | None = None
    ) -> _Binding:
        self.site = node
        cond_raw = self.node(node["condition"])
        cond_unwrapped = self._unwrap_group(cond_raw)
        then_node = self.node(node["then"])
        else_node = self.node(node["else"])
        if cond_unwrapped["kind"] == "is":
            return self._if_is(
                cond_unwrapped,
                then_node,
                else_node,
                environment,
                expected,
                expression_branches=True,
                site_node=node,
            )
        synthetic: Node = {
            "kind": "match_expression",
            "span": node["span"],
            "value": cond_raw,
            "motive": None,
            "cases": [
                {
                    "kind": "expression_case",
                    "span": then_node["span"],
                    "pattern": {"kind": "bool_pattern", "span": cond_raw["span"], "value": True},
                    "value": then_node,
                },
                {
                    "kind": "expression_case",
                    "span": else_node["span"],
                    "pattern": {"kind": "bool_pattern", "span": cond_raw["span"], "value": False},
                    "value": else_node,
                },
            ],
        }
        return self.match(
            synthetic,
            environment,
            expected,
            expression_arms=True,
            refine_scrutinee=True,
            expected_scrutinee_type=_BOOL,
            synthetic=True,
        )

    def _is_expression(self, node: Node, environment: dict[str, _Binding]) -> _Binding:
        self.site = node
        pat_node = self.node(node["pattern"])
        synthetic: Node = {
            "kind": "match_expression",
            "span": node["span"],
            "value": node["value"],
            "motive": None,
            "cases": [
                {
                    "kind": "expression_case",
                    "span": pat_node["span"],
                    "pattern": pat_node,
                    "value": {"kind": "bool", "span": pat_node["span"], "value": True},
                },
                {
                    "kind": "expression_case",
                    "span": node["span"],
                    "pattern": {"kind": "wildcard_pattern", "span": pat_node["span"]},
                    "value": {"kind": "bool", "span": node["span"], "value": False},
                },
            ],
        }
        return self.match(synthetic, environment, _BOOL, expression_arms=True, synthetic=True)

    def _project_member(self, receiver: _Binding, member_name: str, node: Node) -> _Binding:
        self.site = node
        receiver_type = self.whnf(receiver.type)
        head, type_args = self.spine(receiver_type)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
            raise self.fail(
                "unsupported",
                "member projection requires a record receiver, a Format.Write call or the full frontend",
                node,
            )
        record_info = self.records_by_type[head.value]
        for rf in record_info.fields:
            if rf.name == member_name:
                ftype = self._instantiate_record_type(record_info, type_args, rf.type)
                fterm = _apps(_constant(rf.proj_const), *type_args, receiver.term)
                return _Binding(fterm, ftype)
        if member_name in record_info.properties:
            prop_info = record_info.properties[member_name]
            ptype = self._instantiate_record_type(record_info, type_args, prop_info.type)
            ptype = self.substitute(ptype, cast("int", prop_info.self_var.value), receiver.term)
            pterm = _apps(_constant(prop_info.prop_const), *type_args, receiver.term)
            return _Binding(pterm, ptype)
        raise self.fail("name", f"record '{record_info.name}' has no field or property '{member_name}'", node)

    def with_expression(
        self, node: Node, environment: dict[str, _Binding], expected: _Term | None = None
    ) -> _Binding:
        self.site = node
        base_node = self.node(node["value"])
        expected_head = self.spine(self.whnf(expected))[0] if expected is not None else None
        if (
            expected is not None
            and expected_head is not None
            and expected_head.kind == "const"
            and expected_head.value in self.records_by_type
        ):
            base_term = self.check(base_node, expected, environment)
            base = _Binding(base_term, expected)
        else:
            base = self.expression(base_node, environment)
        base_type = self.whnf(base.type)
        head, type_args = self.spine(base_type)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
            raise self.fail("type", "record update 'with { ... }' requires a record value", base_node)
        record_info = self.records_by_type[head.value]
        field_index_by_name = {rf.name: idx for idx, rf in enumerate(record_info.fields)}
        updates = self.nodes(node["updates"])
        update_by_index: dict[int, Node] = {}
        last_index = -1
        last_name = ""
        for update_node in updates:
            self.node(update_node, "field_update")
            fname = self.name(update_node["name"])
            if fname not in field_index_by_name:
                raise self.fail("name", f"record '{record_info.name}' has no field '{fname}'", update_node)
            fidx = field_index_by_name[fname]
            if fidx in update_by_index:
                raise self.fail("name", f"duplicate field '{fname}' in record update", update_node)
            if fidx < last_index:
                raise self.fail(
                    "name",
                    f"record update fields must appear in declaration order; '{fname}' cannot follow '{last_name}'",
                    update_node,
                )
            update_by_index[fidx] = update_node
            last_index = fidx
            last_name = fname
        if not record_info.fields:
            raise self.fail("type", f"record '{record_info.name}' has no fields to update", node)
        final_fields: list[_Term] = []
        for idx, rf in enumerate(record_info.fields):
            ftype = self._instantiate_record_type(record_info, type_args, rf.type)
            if idx in update_by_index:
                u_node = update_by_index[idx]
                final_fields.append(self.check(self.node(u_node["value"]), ftype, environment))
            else:
                final_fields.append(_apps(_constant(rf.proj_const), *type_args, base.term))
        result_term = _apps(_constant(record_info.ctor_const), *type_args, *final_fields)
        result_type = _apps(_constant(record_info.type_const), *type_args)
        if expected is not None:
            self.unify(result_type, expected)
        return _Binding(result_term, result_type)

    def _decode_escaped_segment(self, segment: str, node: Node) -> bytes:
        escapes = {"\\": "\\", '"': '"', "'": "'", "n": "\n", "r": "\r", "t": "\t", "0": "\0"}
        chars: list[str] = []
        index = 0
        while index < len(segment):
            ch = segment[index]
            if ch != "\\":
                chars.append(ch)
                index += 1
                continue
            if index + 1 >= len(segment):
                raise self.fail("syntax", "unterminated escape sequence in string literal", node)
            nxt = segment[index + 1]
            if nxt in escapes:
                chars.append(escapes[nxt])
                index += 2
                continue
            if nxt == "u" and index + 2 < len(segment) and segment[index + 2] == "{":
                end = segment.find("}", index + 3)
                if end == -1:
                    raise self.fail("syntax", "unterminated \\u{...} escape sequence", node)
                hex_digits = segment[index + 3:end]
                if not (1 <= len(hex_digits) <= 6 and all(c in "0123456789abcdefABCDEF" for c in hex_digits)):
                    raise self.fail("syntax", "invalid \\u{...} hex digits", node)
                codepoint = int(hex_digits, 16)
                if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                    raise self.fail("syntax", "Unicode scalar escape is out of range or a surrogate", node)
                chars.append(chr(codepoint))
                index = end + 1
                continue
            raise self.fail("syntax", f"unsupported string escape '\\{nxt}'", node)
        return "".join(chars).encode("utf-8")

    def _decode_string_literal(self, spelling: str, node: Node) -> bytes:
        if spelling.startswith('"""'):
            quotes = len(spelling) - len(spelling.lstrip('"'))
            body = spelling[quotes:-quotes]
            if "\n" in body or "\r" in body:
                normalized = body.replace("\r\n", "\n").replace("\r", "\n")
                lines = normalized.split("\n")
                closing_indent = lines[-1]
                dedented: list[str] = []
                for content_line in lines[1:-1]:
                    if content_line == "":
                        dedented.append("")
                    else:
                        if not content_line.startswith(closing_indent):
                            raise self.fail(
                                "syntax",
                                "raw string content line has less indentation than closing delimiter",
                                node,
                            )
                        dedented.append(content_line[len(closing_indent):])
                raw_bytes = "\n".join(dedented).encode("utf-8")
            else:
                raw_bytes = body.encode("utf-8")
        else:
            raw_bytes = self._decode_escaped_segment(spelling[1:-1], node)
        if len(raw_bytes) > MAX_STRING_BYTES:
            raise self.fail("limit", f"string literal exceeds {MAX_STRING_BYTES} UTF-8 bytes", node)
        return raw_bytes

    def _bytes_binding(self, raw_bytes: bytes) -> _Binding:
        term = _apps(_constant("VNil"), _NAT, _term("unit"))
        for length, byte_val in enumerate(reversed(raw_bytes)):
            term = _apps(
                _constant("VCons"),
                _NAT,
                _term("nat", value=length),
                _term("nat", value=byte_val),
                term,
            )
        return _Binding(term, _apps(_constant("Vec"), _NAT, _term("nat", value=len(raw_bytes))))

    def _elaborate_hole_expression(
        self, expr_text: str, node: Node, environment: dict[str, _Binding]
    ) -> _Binding:
        text = expr_text.strip()
        if not text:
            raise self.fail("syntax", "empty interpolation hole in format template", node)
        if text in {"true", "false"}:
            return _Binding(_term("bool", value=1 if text == "true" else 0), _BOOL)
        if DECIMAL.fullmatch(text):
            if len(text.replace("_", "")) > MAX_LITERAL_DIGITS:
                raise self.fail("limit", "numeric literal exceeds digit bound", node)
            return _Binding(_term("nat", value=int(text.replace("_", ""))), _NAT)
        if text.startswith('"') and text.endswith('"') and len(text) >= 2:
            return self._bytes_binding(self._decode_string_literal(text, node))
        if _IDENTIFIER.fullmatch(text):
            if "." in text and text not in environment and text not in self.globals:
                parts = text.split(".")
                current = self.lookup(parts[0], environment)
                for member_name in parts[1:]:
                    current = self._project_member(current, member_name, node)
                return current
            return self.lookup(text, environment)
        call_match = re.fullmatch(r"([A-Za-z_][A-Za-z_0-9]*)\((.*)\)", text, re.DOTALL)
        if call_match is not None:
            callee_name, raw_args = call_match.group(1), call_match.group(2).strip()
            callee = self.lookup(callee_name, environment)
            if not raw_args:
                return self.apply(callee, [], environment)
            arg_binding = self._elaborate_hole_expression(raw_args, node, environment)
            fn_type = self.whnf(callee.type)
            if fn_type.kind != "pi" or cast("int", fn_type.value) in self.nullary_parameters:
                raise self.fail("type", f"invalid call to '{callee_name}' in interpolation hole", node)
            self.unify(arg_binding.type, fn_type.args[0])
            return _Binding(
                _app(callee.term, arg_binding.term),
                self.substitute(fn_type.args[1], cast("int", fn_type.value), arg_binding.term),
            )
        raise self.fail("unsupported", f"unsupported interpolation hole expression '{text}'", node)

    def _format_write(
        self, node: Node, arguments: list[Node], environment: dict[str, _Binding]
    ) -> _Binding:
        if len(arguments) != 2:
            raise self.fail("type", "Format.Write requires (ref builder, $\"...\") arguments", node)
        labeled = False
        for idx, arg_node in enumerate(arguments):
            self.node(arg_node, "argument")
            label = arg_node["label"]
            if label is None and labeled:
                raise self.fail("name", "positional arguments cannot follow a named argument", arg_node)
            labeled = labeled or label is not None
            if label is not None:
                spelling = self.name(label)
                expected_label = "target" if idx == 0 else "template"
                if spelling != expected_label:
                    raise self.fail(
                        "name", f"expected argument label '{expected_label}', got '{spelling}'", arg_node
                    )
        target_arg = self.node(arguments[0]["value"])
        if (target_arg["kind"] != "unary"
                or not isinstance(target_arg["operator"], dict)
                or target_arg["operator"].get("text") != "ref"):
            hint = (
                f"; write 'ref {self.name(target_arg['name'])}'"
                if target_arg["kind"] == "name"
                else ""
            )
            raise self.fail(
                "type",
                f"Format.Write requires an explicit ref TextBuilder<capacity> target{hint}",
                arguments[0],
            )
        target_inner = self.node(target_arg["value"])
        target_name = self.name(target_inner["name"]) if target_inner["kind"] == "name" else None
        builder = self.expression(target_inner, environment)
        capacity = self.meta(_NAT, environment)
        self.unify(builder.type, _app(_constant("TextBuilder"), capacity))
        capacity = self.whnf(capacity)
        template_arg = self.node(arguments[1]["value"])
        if template_arg["kind"] != "interpolated_string":
            raise self.fail(
                "type",
                "Format.Write requires an interpolated $\"...\" format template",
                arguments[1],
            )
        spelling = cast("str", template_arg["value"])
        body = spelling[2:-1]
        literal_chars: list[str] = []
        chunk_terms: list[_Term] = []
        concrete_bytes = 0
        index = 0
        while index < len(body):
            ch = body[index]
            if ch == "{":
                if index + 1 < len(body) and body[index + 1] == "{":
                    literal_chars.append("{")
                    index += 2
                    continue
                if literal_chars:
                    concrete_bytes += len(
                        self._decode_escaped_segment("".join(literal_chars), template_arg)
                    )
                    literal_chars.clear()
                end = body.find("}", index + 1)
                if end == -1:
                    raise self.fail("syntax", "unterminated interpolation hole in format template", template_arg)
                hole_content = body[index + 1:end]
                if ":" in hole_content:
                    expr_part, spec_part = hole_content.rsplit(":", 1)
                    expr_text, spec = expr_part.strip(), spec_part.strip()
                else:
                    expr_text, spec = hole_content.strip(), ""
                if target_name is not None and re.search(rf"\b{re.escape(target_name)}\b", expr_text):
                    raise self.fail(
                        "type",
                        f"Format.Write hole cannot alias or read target buffer '{target_name}'",
                        template_arg,
                    )
                hole_binding = self._elaborate_hole_expression(expr_text, template_arg, environment)
                hole_type = self.whnf(hole_binding.type)
                head, type_args = self.spine(hole_type)
                if hole_type == _NAT:
                    if spec not in {"", "d", "x", "x2", "x4", "x8", "X", "X2", "X4", "X8", "b"}:
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for Nat hole", template_arg
                        )
                    val = self.whnf(hole_binding.term)
                    if val.kind == "nat":
                        n_val = cast("int", val.value)
                        if spec in {"", "d"}:
                            concrete_bytes += len(str(n_val))
                        elif spec in {"x", "X"}:
                            concrete_bytes += len(format(n_val, "x"))
                        elif spec in {"x2", "X2"}:
                            concrete_bytes += max(2, len(format(n_val, "x")))
                        elif spec in {"x4", "X4"}:
                            concrete_bytes += max(4, len(format(n_val, "x")))
                        elif spec in {"x8", "X8"}:
                            concrete_bytes += max(8, len(format(n_val, "x")))
                        else:
                            concrete_bytes += len(format(n_val, "b"))
                    elif spec in {"x2", "X2", "x4", "X4", "x8", "X8"}:
                        concrete_bytes += int(spec[1:])
                    else:
                        raise self.fail(
                            "type",
                            "symbolic Nat hole requires a fixed-width hex specifier (x2, x4, x8) or concrete value",
                            template_arg,
                        )
                elif hole_type == _BOOL:
                    if spec != "":
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for bool hole", template_arg
                        )
                    val = self.whnf(hole_binding.term)
                    if val.kind == "bool":
                        concrete_bytes += 4 if val.value else 5
                    else:
                        chunk_terms.append(
                            _term("if", _NAT, hole_binding.term, _term("nat", value=4), _term("nat", value=5))
                        )
                elif head == _constant("Vec") and len(type_args) == 2 and self.whnf(type_args[0]) == _NAT:
                    if spec != "":
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for byte-vector hole", template_arg
                        )
                    len_term = self.whnf(type_args[1])
                    if len_term.kind == "nat":
                        concrete_bytes += cast("int", len_term.value)
                    else:
                        chunk_terms.append(len_term)
                else:
                    raise self.fail(
                        "type",
                        "interpolated hole type does not implement static Format<T>",
                        template_arg,
                    )
                index = end + 1
                continue
            if ch == "}":
                if index + 1 < len(body) and body[index + 1] == "}":
                    literal_chars.append("}")
                    index += 2
                    continue
                raise self.fail("syntax", "unescaped closing '}' in interpolated format template", template_arg)
            literal_chars.append(ch)
            index += 1
        if literal_chars:
            concrete_bytes += len(self._decode_escaped_segment("".join(literal_chars), template_arg))
        if concrete_bytes > MAX_STRING_BYTES:
            raise self.fail(
                "limit", f"formatted template exceeds {MAX_STRING_BYTES} UTF-8 bytes", template_arg
            )
        total_chunk = _term("nat", value=concrete_bytes)
        for extra in chunk_terms:
            total_chunk = (
                extra if total_chunk == _term("nat", value=0) else _apps(_constant("+"), total_chunk, extra)
            )
        return _Binding(
            _apps(_constant("FormatStep"), capacity, builder.term, total_chunk),
            _app(_constant("TextBuilder"), capacity),
        )

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
        if kind == "string":
            return self._bytes_binding(self._decode_string_literal(cast("str", node["value"]), node))
        if kind == "interpolated_string":
            raise self.fail(
                "type",
                "interpolated format template requires an explicit Format.Write destination buffer",
                node,
            )
        if kind == "member":
            return self._project_member(
                self.expression(self.node(node["value"]), environment),
                self.name(node["name"]),
                node,
            )
        if kind in {"name", "operator"}:
            name = self.operator(node["name"]) if kind == "operator" else self.name(node["name"])
            if name == "Type":
                return _Binding(_SORT, _term("sort", value=1))
            if name == "Prop":
                return _Binding(_PROP, _SORT)
            if name == "_":
                value_type = self.meta(_SORT, environment)
                return _Binding(self.meta(value_type, environment), value_type)
            if kind == "name" and name not in environment and name in self.records:
                if self.static_forbidden is not None and id(self.records[name].ctor_binding) in self.static_forbidden:
                    raise self.fail("type", f"constant initializer depends on nonstatic binding '{name}'")
                return self.instantiate(self.records[name].ctor_binding, environment)
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
            target_name = self.name(target["name"])
            if target_name not in environment and target_name in self.records:
                binding = self.records[target_name].ctor_binding
            else:
                binding = self.lookup(target_name, environment, raw=True)
            return self.instantiate(binding, environment, self.nodes(node["arguments"]))
        if kind == "call":
            callee = self.node(node["callee"])
            if callee["kind"] == "member":
                receiver = self.node(callee["value"])
                if (receiver["kind"] == "name"
                        and self.name(receiver["name"]) == "Format"
                        and self.name(callee["name"]) == "Write"):
                    return self._format_write(node, self.nodes(node["arguments"]), environment)
            return self.apply(self.expression(callee, environment), self.nodes(node["arguments"]), environment)
        if kind in {"lambda", "typed_lambda"}:
            return self.lambda_(node, environment)
        if kind == "let_expression":
            return self.expression(self.node(node["body"]), self.local(self.node(node["binding"]), environment))
        if kind == "if_expression":
            return self.if_expression(node, environment)
        if kind == "with_expression":
            return self.with_expression(node, environment)
        if kind == "is":
            return self._is_expression(node, environment)
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
            if isinstance(node["operator"], dict) and node["operator"].get("text") == "ref":
                raise self.fail("type", "ref argument is only supported as the target of Format.Write", node)
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

    def _record_declaration(self, node: Node, first_meta: int) -> None:
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"}
        if (not isinstance(modifiers, list)
                or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", node)
        self.no_roles(node, "contracts")
        name = self.name(node["name"])
        if name in self.globals or name in self.records or name in {"Type", "_", "this"} or "." in name:
            raise self.fail("name", f"duplicate or reserved declaration '{name}'", node)
        generics = self.nodes(node["generics"])
        parameters = self.nodes(node["parameters"])
        for param_node in parameters:
            self.node(param_node, "parameter")
            if param_node["name"] is None:
                raise self.fail("protocol", "record field requires an explicit name", param_node)
            fname = self.name(param_node["name"])
            if fname in {"Type", "_", "this"} or "." in fname:
                raise self.fail("name", f"invalid or reserved record field name '{fname}'", param_node)
            if param_node.get("const", False):
                raise self.fail("unsupported", "record fields cannot be marked const", param_node)
        variables, environment = self.telescope(generics, parameters, {}, unit=False)
        generic_vars = variables[:len(generics)]
        field_vars = variables[len(generics):]
        field_names = [self.name(p["name"]) for p in parameters]
        for idx, fv in enumerate(field_vars):
            ftype = self.types[cast("int", fv.value)]
            if any(cast("int", earlier.value) in self.free(ftype) for earlier in field_vars[:idx]):
                raise self.fail(
                    "unsupported",
                    "dependent record field telescopes require sigT lowering in the full frontend",
                    parameters[idx],
                )
        if not field_vars:
            rep_type = _UNIT
        elif len(field_vars) == 1:
            rep_type = _term("prod", self.types[cast("int", field_vars[0].value)], _UNIT)
        else:
            rep_type = self.types[cast("int", field_vars[-1].value)]
            for fv in reversed(field_vars[:-1]):
                rep_type = _term("prod", self.types[cast("int", fv.value)], rep_type)
        rep_sort = _term("sort", value=max(self.sort(rep_type), 0))
        type_sig = self.wrap("pi", generic_vars, rep_sort)
        type_def = self.wrap("lam", generic_vars, rep_type)
        self.site = node
        self.complete(type_sig)
        self.complete(type_def)
        for index in range(first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)
        type_emitted = f"vela_d{len(self.output)}_{name}"
        self.output.append(f"Definition {type_emitted} : {self.render(type_sig)} :=\n  {self.render(type_def)}.")
        type_binding = _Binding(_constant(type_emitted), type_sig, len(generics))
        self.globals[name] = type_binding
        self.constants[type_emitted] = type_binding

        record_type_app = _apps(_constant(type_emitted), *generic_vars)
        if not field_vars:
            unit_var = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", unit_var.value))
            ctor_vars = [*generic_vars, unit_var]
            ctor_body = _term("unit")
        elif len(field_vars) == 1:
            ctor_vars = [*generic_vars, field_vars[0]]
            f0_type = self.types[cast("int", field_vars[0].value)]
            ctor_body = _term("pair", f0_type, _UNIT, field_vars[0], _term("unit"))
        else:
            ctor_vars = [*generic_vars, *field_vars]
            ctor_body = field_vars[-1]
            acc_type = self.types[cast("int", field_vars[-1].value)]
            for fv in reversed(field_vars[:-1]):
                fv_type = self.types[cast("int", fv.value)]
                ctor_body = _term("pair", fv_type, acc_type, fv, ctor_body)
                acc_type = _term("prod", fv_type, acc_type)
        ctor_sig = self.wrap("pi", ctor_vars, record_type_app)
        ctor_def = self.wrap("lam", ctor_vars, ctor_body)
        self.complete(ctor_sig)
        self.complete(ctor_def)
        ctor_emitted = f"vela_d{len(self.output)}_{name}_ctor"
        self.output.append(f"Definition {ctor_emitted} : {self.render(ctor_sig)} :=\n  {self.render(ctor_def)}.")
        ctor_binding = _Binding(_constant(ctor_emitted), ctor_sig, len(generics))
        self.constants[ctor_emitted] = ctor_binding

        record_fields: list[_RecordField] = []
        for idx, (fname, fvar) in enumerate(zip(field_names, field_vars, strict=True)):
            ftype = self.types[cast("int", fvar.value)]
            self_var = self.fresh(record_type_app)
            proj_vars = [*generic_vars, self_var]
            if len(field_vars) == 1:
                proj_body = _apps(_constant("Fst"), ftype, _UNIT, self_var)
            else:
                curr_term = self_var
                curr_type = rep_type
                for _ in range(idx):
                    curr_term = _apps(_constant("Snd"), curr_type.args[0], curr_type.args[1], curr_term)
                    curr_type = curr_type.args[1]
                if idx < len(field_vars) - 1:
                    curr_term = _apps(_constant("Fst"), curr_type.args[0], curr_type.args[1], curr_term)
                proj_body = curr_term
            proj_sig = self.wrap("pi", proj_vars, ftype)
            proj_def = self.wrap("lam", proj_vars, proj_body)
            self.complete(proj_sig)
            self.complete(proj_def)
            proj_emitted = f"vela_d{len(self.output)}_{name}_{fname}"
            self.output.append(f"Definition {proj_emitted} : {self.render(proj_sig)} :=\n  {self.render(proj_def)}.")
            proj_binding = _Binding(_constant(proj_emitted), proj_sig, len(generics))
            self.constants[proj_emitted] = proj_binding
            record_fields.append(_RecordField(fname, fvar, ftype, proj_emitted))

        record_info = _RecordInfo(
            name=name,
            type_const=type_emitted,
            ctor_const=ctor_emitted,
            type_binding=type_binding,
            ctor_binding=ctor_binding,
            generic_vars=tuple(generic_vars),
            fields=tuple(record_fields),
            properties={},
        )
        self.records[name] = record_info
        self.records_by_type[type_emitted] = record_info
        self.records_by_ctor[ctor_emitted] = record_info
        for idx, rf in enumerate(record_fields):
            self.record_projections[rf.proj_const] = (record_info, idx)

        generic_env: dict[str, _Binding] = {}
        for gnode in generics:
            gname = self.name(gnode["name"])
            generic_env[gname] = environment[gname]
        for member_node in self.nodes(node["declarations"]):
            self.site = member_node
            if member_node["kind"] != "property":
                raise self.fail(
                    "unsupported",
                    f"record member '{member_node['kind']}' requires the full frontend",
                    member_node,
                )
            prop_first_meta = len(self.metas)
            p_modifiers = member_node["modifiers"]
            if (not isinstance(p_modifiers, list)
                    or any(not isinstance(value, str) or value not in allowed_modifiers for value in p_modifiers)
                    or len(p_modifiers) != len(set(p_modifiers))):
                raise self.fail("unsupported", "unsupported or repeated declaration modifiers", member_node)
            self.no_roles(member_node, "contracts")
            prop_name = self.name(member_node["name"])
            if (prop_name in {"Type", "_", "this"} or "." in prop_name
                    or any(rf.name == prop_name for rf in record_fields)
                    or prop_name in record_info.properties):
                raise self.fail("name", f"duplicate or reserved property '{prop_name}' on record '{name}'", member_node)
            self_var = self.fresh(record_type_app)
            prop_env = dict(generic_env)
            prop_env["this"] = _Binding(self_var, record_type_app)
            for rf in record_fields:
                if rf.name not in generic_env:
                    prop_env[rf.name] = _Binding(_apps(_constant(rf.proj_const), *generic_vars, self_var), rf.type)
            prop_type = self.type(self.node(member_node["type"]), prop_env)
            prop_body = self.check(self.node(member_node["value"]), prop_type, prop_env)
            prop_vars = [*generic_vars, self_var]
            prop_sig = self.wrap("pi", prop_vars, prop_type)
            prop_def = self.wrap("lam", prop_vars, prop_body)
            self.site = member_node
            self.complete(prop_sig)
            self.complete(prop_def)
            for index in range(prop_first_meta, len(self.metas)):
                self.complete(_term("meta", value=index))
                self.complete(self.metas[index].type)
            prop_emitted = f"vela_d{len(self.output)}_{name}_{prop_name}"
            self.output.append(f"Definition {prop_emitted} : {self.render(prop_sig)} :=\n  {self.render(prop_def)}.")
            prop_binding = _Binding(_constant(prop_emitted), prop_sig, len(generics))
            self.constants[prop_emitted] = prop_binding
            self.definitions[prop_emitted] = prop_def
            record_info.properties[prop_name] = _RecordProperty(prop_name, self_var, prop_type, prop_emitted)

    def declaration(self, node: Node) -> None:
        self.site = node
        first_meta = len(self.metas)
        kind = node["kind"]
        if kind == "record":
            self._record_declaration(node, first_meta)
            return
        if kind not in {"alias", "definition", "function", "property", "theorem", "lemma", "constant"}:
            raise self.fail("unsupported", f"declaration '{kind}' requires the full frontend")
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"} | ({"const"} if kind in {"definition", "function"} else set())
        if (not isinstance(modifiers, list) or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers")
        self.no_roles(node, "contracts", "cancel")
        name = self.name(node["name"])
        if name in self.globals or name in self.records or name in {"Type", "_", "this"} or "." in name:
            raise self.fail("name", f"duplicate or reserved declaration '{name}'")
        generics = [] if kind in {"constant", "property"} else self.nodes(node["generics"])
        parameters = [] if kind in {"alias", "constant", "property"} else self.nodes(node["parameters"])
        variables, environment = self.telescope(
            generics, parameters, {}, unit=kind not in {"alias", "constant", "property"}
        )
        if kind == "constant":
            evaluated = self.constant_value(node, environment)
            body, result = evaluated.term, evaluated.type
        elif kind == "property":
            result = self.type(self.node(node["type"]), environment)
            body = self.check(self.node(node["value"]), result, environment)
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
            if name in self.definitions or name in self.constants:
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
    "Vec": "vela_Vec", "VNil": "vela_VNil", "VCons": "vela_VCons", "ByteLength": "vela_ByteLength",
    "TextBuilder": "vela_TextBuilder", "TextBuilderVal": "vela_text_builder",
    "EmptyBuilder": "vela_EmptyBuilder", "FormatStep": "vela_FormatStep",
    "Fits": "vela_Fits", "Written": "vela_Written",
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
Definition vela_ByteLength (n : nat) (_ : vela_Vec nat n) : nat := n.

Inductive vela_TextBuilder (capacity : nat) : Type@{vela_u0} :=
| vela_text_builder : bool -> nat -> vela_TextBuilder capacity.
Definition vela_EmptyBuilder (capacity : nat) (_ : unit) : vela_TextBuilder capacity :=
  vela_text_builder capacity true O.
Definition vela_FormatStep (capacity : nat) (builder : vela_TextBuilder capacity) (chunk : nat)
    : vela_TextBuilder capacity :=
  match builder with
  | vela_text_builder _ ok used =>
      vela_text_builder capacity
        (vela_and ok (Corelib.Init.Nat.leb (Corelib.Init.Nat.add used chunk) capacity))
        (Corelib.Init.Nat.add used chunk)
  end.
Definition vela_Fits (capacity : nat) (builder : vela_TextBuilder capacity) : bool :=
  match builder with
  | vela_text_builder _ ok _ => ok
  end.
Definition vela_Written (capacity : nat) (builder : vela_TextBuilder capacity) : nat :=
  match builder with
  | vela_text_builder _ _ used => used
  end.
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


