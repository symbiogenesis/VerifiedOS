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
from vos.vela_authoring import assist_loan_argument

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
    "import": {"name"},
    "alias": {"name", "generics", "contracts", "type", "modifiers"},
    "constant": {"name", "type", "value", "modifiers"},
    "constant_local": {"name", "type", "value"},
    "definition": {"name", "result", "generics", "parameters", "contracts", "value", "modifiers"},
    "function": {"name", "result", "generics", "parameters", "contracts", "body", "cancel", "modifiers"},
    "record": {"name", "generics", "parameters", "contracts", "declarations", "modifiers"},
    "union": {"name", "generics", "contracts", "constructors", "modifiers"},
    "constructor": {"name", "parameters", "result", "contracts"},
    "property": {"name", "type", "contracts", "value", "modifiers"},
    "theorem": {"name", "generics", "parameters", "contracts", "body", "modifiers"},
    "lemma": {"name", "generics", "parameters", "contracts", "body", "modifiers"},
    "generic_parameter": {"name", "mode", "type"},
    "parameter": {"name", "type", "grade"},
    "lambda_parameter": {"name", "type", "grade"},
    "type": {"name", "arguments"},
    "function_type": {"mode", "generics", "parameters", "result", "captures", "effects", "contracts"},
    "group_type": {"type"}, "computed_type": {"value"}, "type_argument": {"type"},
    "tuple_type": {"types"}, "modified_type": {"modifier", "lifetime", "type"},
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
    "var": {"name", "type", "grade", "value"},
    "typed_local": {"name", "type", "grade", "value"},
    "let_pattern": {"pattern", "value"},
    "var_pattern": {"pattern", "value"},
    "let_else": {"pattern", "value", "else"},
    "var_else": {"pattern", "value", "else"},
    "assignment": {"target", "operator", "value"},
    "expression_statement": {"value"},
    "range": {"start", "end"},
    "foreach": {"name", "range", "contracts", "body"},
    "foreach_collection": {"name", "type", "mode", "collection", "contracts", "body"},
    "break": set(), "continue": set(),
    "scope": {"resources", "body"},
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
    "contract": {"role", "value"},
    "propagate": {"value"},
    "assert": {"value", "by"}, "proof": {"body"},
    "hole": {"name"},
}
_PATTERN_KINDS = {
    "wildcard_pattern", "binding_pattern", "unit_pattern", "group_pattern",
    "tuple_pattern", "bool_pattern", "nat_pattern", "constructor_pattern",
}
_PATTERN_ARGUMENT_KINDS = _PATTERN_KINDS | {"labeled_pattern"}
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*")
_HEX_LITERAL = re.compile(r"0[xX][0-9a-fA-F](?:_?[0-9a-fA-F])*")
_BIN_LITERAL = re.compile(r"0[bB][01](?:_?[01])*")
_INT_SUFFIXES = {"", "u8", "u16", "u32", "u64", "usize", "i8", "i16", "i32", "i64", "byte"}
_OPERATORS = {
    "+", "*", "-", "/", "%", "&", "|", "^", "~",
    "==", "!=", "<", "<=", ">", ">=", "&&", "||", "!", "==>", "<==>",
}
_ASSIGN_OPERATORS = {"=", "+=", "-=", "*=", "/=", "%="}
_SYNTAX_WORDS = {
    "function_type": ("mode", {"Fn", "FnMut", "FnOnce"}),
    "generic_parameter": ("mode", {"type", "ghost", "region", "effect", "captures", "grade"}),
    "quantifier": ("quantifier", {"forall", "exists"}),
    "contract": ("role", {"requires", "ensures", "restores", "where", "decreases", "progress", "invariant"}),
    "modified_type": ("modifier", {"owned", "in", "ref", "out", "ghost", "tracked", "scoped"}),
    "foreach_collection": ("mode", {"value", "in", "ref"}),
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
                token = re.match(
                    r"\?[A-Za-z_][A-Za-z_0-9]*|[A-Za-z_][A-Za-z_0-9]*|<==>|==>|&&|\|\||==|!=|<=|>=|\+=|-=|\*=|/=|%=|[.+*\-/%<>!&|^~=]",
                    value[offset:],
                )
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
        if kind in {"definition", "function", "alias", "theorem", "lemma", "record", "union", "property"}:
            contracts = node.get("contracts")
            if node.get("cancel"):
                return  # These roles are refused by the mathematical consumer.
            if kind in {"theorem", "lemma"}:
                if not isinstance(contracts, list) or not contracts:
                    raise self.error("protocol", "theorem contracts must be a non-empty list", node)
                seen_ensures = False
                for item in contracts:
                    if not isinstance(item, dict) or item.get("kind") != "contract":
                        raise self.error("protocol", "theorem contracts must be contract nodes", node)
                    role = item.get("role")
                    if role == "ensures":
                        seen_ensures = True
                    elif seen_ensures or role not in {"decreases", "requires", "where"}:
                        raise self.error(
                            "protocol",
                            "theorem contracts must be precontracts followed by ensures clauses",
                            node,
                        )
                if not seen_ensures:
                    raise self.error("protocol", "theorem requires at least one ensures clause", node)
                if any(item.get("role") == "where" for item in contracts):
                    return
            elif kind == "record" and contracts:
                if not isinstance(contracts, list) or any(
                    not isinstance(item, dict) or item.get("kind") != "contract"
                    for item in contracts
                ):
                    raise self.error("protocol", "record contracts must be contract nodes", node)
                if any(item.get("role") != "invariant" for item in contracts):
                    return
            elif contracts and (
                kind not in {"definition", "function"}
                or not isinstance(contracts, list)
                or any(
                    not isinstance(item, dict)
                    or item.get("kind") != "contract"
                    or item.get("role") not in {"decreases", "requires", "ensures", "restores"}
                    for item in contracts
                )
            ):
                return
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
            if kind not in {"alias", "property", "union"}:
                cursor = self._list(node, span, cursor, node["parameters"])
            if contracts and isinstance(contracts, list):
                for contract_item in contracts:
                    cursor = self._child(node, span, cursor, contract_item)
            if kind in {"theorem", "lemma"}:
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
            elif kind == "union":
                constructors = node["constructors"]
                if (not isinstance(constructors, list)
                        or any(not isinstance(item, dict) or item.get("kind") != "constructor" for item in constructors)):
                    raise self.error("protocol", "union requires constructor children", node)
                cursor = self._token(node, cursor, b"{")
                self._sequence_envelope(node, span, "constructors", cursor, b"}")
                return
            elif kind in {"alias", "definition", "property"}:
                cursor = self._token(node, cursor, b"=" if kind == "alias" else b"=>")
                cursor = self._child(node, span, cursor, node["type"] if kind == "alias" else node["value"])
                cursor = self._token(node, cursor, b";")
            elif node["body"] is None:
                cursor = self._token(node, cursor, b";")
            else:
                cursor = self._child(node, span, cursor, node["body"])
        elif kind == "constructor":
            if node.get("contracts"):
                return
            cursor = self._child(node, span, cursor, node["name"])
            parameters = node["parameters"]
            if not isinstance(parameters, list):
                raise self.error("protocol", "constructor parameters must be a child list", node)
            after_name = trivia_end(self.source, cursor, block_comments=True)
            if self.source[after_name:after_name + 1] == b"(":
                cursor = self._list(node, span, cursor, parameters)
            elif parameters:
                raise self.error("protocol", "constructor parameters require parentheses", node)
            if node["result"] is not None:
                cursor = self._token(node, cursor, b":")
                cursor = self._child(node, span, cursor, node["result"])
            cursor = self._token(node, cursor, b";")
        elif kind in {"let", "var", "typed_local", "parameter", "lambda_parameter", "generic_parameter"}:
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
                if kind in {"let", "var"}:
                    cursor = self._token(node, cursor, cast("str", kind).encode())
                if kind in {"parameter", "lambda_parameter"} and node.get("const", False):
                    cursor = self._token(node, cursor, b"const")
                if node["type"] is not None:
                    cursor = self._child(node, span, cursor, node["type"])
                if node["name"] is not None:
                    cursor = self._child(node, span, cursor, node["name"])
                if kind in {"let", "var", "typed_local"}:
                    cursor = self._token(node, cursor, b"=")
                    cursor = self._child(node, span, cursor, node["value"])
                    if cursor < span[1]:
                        cursor = self._token(node, cursor, b";")
        elif kind in {"let_pattern", "var_pattern"}:
            pattern = node["pattern"]
            if (not isinstance(pattern, dict)
                    or pattern.get("kind") not in {"unit_pattern", "group_pattern", "tuple_pattern", "constructor_pattern"}):
                raise self.error("protocol", f"{kind} requires a parenthesized or constructor pattern", node)
            cursor = self._token(node, cursor, b"var" if kind == "var_pattern" else b"let")
            cursor = self._child(node, span, cursor, pattern)
            cursor = self._token(node, cursor, b"=")
            cursor = self._child(node, span, cursor, node["value"])
            if cursor < span[1]:
                cursor = self._token(node, cursor, b";")
        elif kind in {"let_else", "var_else"}:
            pattern = node["pattern"]
            if (not isinstance(pattern, dict)
                    or pattern.get("kind") not in {"unit_pattern", "group_pattern", "tuple_pattern", "constructor_pattern"}):
                raise self.error("protocol", f"{kind} requires a parenthesized or constructor pattern", node)
            if not isinstance(node["else"], dict) or node["else"].get("kind") != "block":
                raise self.error("protocol", f"{kind} requires a block else branch", node)
            cursor = self._token(node, cursor, b"var" if kind == "var_else" else b"let")
            cursor = self._child(node, span, cursor, pattern)
            cursor = self._token(node, cursor, b"=")
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b"else")
            cursor = self._child(node, span, cursor, node["else"])
        elif kind == "assignment":
            op = node["operator"]
            if not isinstance(op, dict) or op.get("text") not in _ASSIGN_OPERATORS:
                raise self.error("protocol", "assignment operator differs from source", node)
            for field in ("target", "operator", "value"):
                cursor = self._child(node, span, cursor, node[field])
            cursor = self._token(node, cursor, b";")
        elif kind == "expression_statement":
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b";")
        elif kind == "range":
            cursor = self._child(node, span, cursor, node["start"])
            cursor = self._token(node, cursor, b"..")
            cursor = self._child(node, span, cursor, node["end"])
        elif kind == "foreach":
            if not isinstance(node["range"], dict) or node["range"].get("kind") != "range":
                raise self.error("protocol", "foreach requires a range node", node)
            contracts = node["contracts"]
            if (not isinstance(contracts, list)
                    or any(not isinstance(item, dict) or item.get("kind") != "contract" for item in contracts)):
                raise self.error("protocol", "foreach contracts must be contract nodes", node)
            if not isinstance(node["body"], dict) or node["body"].get("kind") != "block":
                raise self.error("protocol", "foreach requires a block body", node)
            cursor = self._token(node, cursor, b"foreach")
            cursor = self._token(node, cursor, b"(")
            cursor = self._token(node, cursor, b"let")
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._token(node, cursor, b"in")
            cursor = self._child(node, span, cursor, node["range"])
            cursor = self._token(node, cursor, b")")
            for contract_item in contracts:
                cursor = self._child(node, span, cursor, contract_item)
            cursor = self._child(node, span, cursor, node["body"])
        elif kind == "foreach_collection":
            contracts = node["contracts"]
            if (not isinstance(contracts, list)
                    or any(not isinstance(item, dict) or item.get("kind") != "contract" for item in contracts)):
                raise self.error("protocol", "foreach_collection contracts must be contract nodes", node)
            if not isinstance(node["body"], dict) or node["body"].get("kind") != "block":
                raise self.error("protocol", "foreach_collection requires a block body", node)
            cursor = self._token(node, cursor, b"foreach")
            cursor = self._token(node, cursor, b"(")
            mode = cast("str", node["mode"])
            if mode == "value":
                after = trivia_end(self.source, cursor, block_comments=True)
                if node["type"] is None or (
                    self.source[after:after + 3] == b"let"
                    and not self._word(self.source[after + 3:after + 4])
                ):
                    cursor = self._token(node, cursor, b"let")
            else:
                cursor = self._token(node, cursor, mode.encode())
            if node["type"] is not None:
                cursor = self._child(node, span, cursor, node["type"])
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._token(node, cursor, b"in")
            cursor = self._child(node, span, cursor, node["collection"])
            cursor = self._token(node, cursor, b")")
            for contract_item in contracts:
                cursor = self._child(node, span, cursor, contract_item)
            cursor = self._child(node, span, cursor, node["body"])
        elif kind in {"break", "continue"}:
            cursor = self._token(node, cursor, cast("str", kind).encode())
            cursor = self._token(node, cursor, b";")
        elif kind == "scope":
            resources = node["resources"]
            if not isinstance(resources, list) or not resources:
                raise self.error("protocol", "scope requires a non-empty resource list", node)
            if not isinstance(node["body"], dict) or node["body"].get("kind") != "block":
                raise self.error("protocol", "scope requires a block body", node)
            cursor = self._token(node, cursor, b"scope")
            cursor = self._list(node, span, cursor, resources)
            lifts = node.get("lifts")
            if lifts is not None:
                if not isinstance(lifts, list) or not lifts:
                    raise self.error("protocol", "scope lifts must be a non-empty identifier list", node)
                cursor = self._token(node, cursor, b"lifts")
                for index, item in enumerate(lifts):
                    if index:
                        cursor = self._token(node, cursor, b",")
                    cursor = self._child(node, span, cursor, item)
                after_lifts = trivia_end(self.source, cursor, block_comments=True)
                if self.source[after_lifts:after_lifts + 1] == b",":
                    cursor = after_lifts + 1
            cursor = self._child(node, span, cursor, node["body"])
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
            op = node["operator"]
            if not isinstance(op, dict) or op.get("text") not in _OPERATORS:
                raise self.error("protocol", "binary operator differs from source", node)
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
        elif kind == "contract":
            if node["role"] not in {"decreases", "requires", "ensures", "restores", "invariant"}:
                return
            if "name" in node and node["role"] != "invariant":
                raise self.error("protocol", "only invariant contracts may carry a clause name", node)
            cursor = self._token(node, cursor, cast("str", node["role"]).encode())
            if "name" in node and node["name"] is not None:
                cursor = self._child(node, span, cursor, node["name"])
                cursor = self._token(node, cursor, b":")
            cursor = self._child(node, span, cursor, node["value"])
        elif kind == "modified_type":
            if node.get("lifetime") is not None:
                return
            cursor = self._token(node, cursor, cast("str", node["modifier"]).encode())
            cursor = self._child(node, span, cursor, node["type"])
        elif kind == "import":
            cursor = self._token(node, cursor, b"import")
            cursor = self._child(node, span, cursor, node["name"])
            cursor = self._token(node, cursor, b";")
        elif kind == "propagate":
            cursor = self._child(node, span, cursor, node["value"])
            cursor = self._token(node, cursor, b"?")
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
                            or text in _ASSIGN_OPERATORS
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
        optional = (
            {"const"}
            if kind in {"parameter", "lambda_parameter"}
            else ({"name"} if kind == "contract" else ({"lifts"} if kind == "scope" else set()))
        )
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
            digits = value[2:] if value.startswith(("0x", "0X", "0b", "0B")) else value
            if len(digits.replace("_", "")) > MAX_LITERAL_DIGITS:
                raise self.error("limit", "numeric literal exceeds digit bound", node)
            if self.source[span[0]:span[1]] != (value + suffix).encode():
                raise self.error("protocol", "numeric literal differs from its source", node)
            if suffix not in _INT_SUFFIXES or not (
                DECIMAL.fullmatch(value) or _HEX_LITERAL.fullmatch(value) or _BIN_LITERAL.fullmatch(value)
            ):
                raise self.error("unsupported", "unsupported numeric literal format or suffix", node)
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
                    if isinstance(statement, dict) and statement.get("kind") in {
                        "let",
                        "var",
                        "typed_local",
                        "let_pattern",
                        "var_pattern",
                    }:
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


@dataclass(frozen=True)
class _IntSpec:
    name: str
    tag: int
    bits: int
    signed: bool
    min_val: int
    max_val: int
    const: _Term


_INT_SPECS: dict[str, _IntSpec] = {
    "u8": _IntSpec("u8", 0, 8, False, 0, (1 << 8) - 1, _constant("u8")),
    "u16": _IntSpec("u16", 1, 16, False, 0, (1 << 16) - 1, _constant("u16")),
    "u32": _IntSpec("u32", 2, 32, False, 0, (1 << 32) - 1, _constant("u32")),
    "u64": _IntSpec("u64", 3, 64, False, 0, (1 << 64) - 1, _constant("u64")),
    "usize": _IntSpec("usize", 4, 64, False, 0, (1 << 64) - 1, _constant("usize")),
    "i8": _IntSpec("i8", 5, 8, True, -(1 << 7), (1 << 7) - 1, _constant("i8")),
    "i16": _IntSpec("i16", 6, 16, True, -(1 << 15), (1 << 15) - 1, _constant("i16")),
    "i32": _IntSpec("i32", 7, 32, True, -(1 << 31), (1 << 31) - 1, _constant("i32")),
    "i64": _IntSpec("i64", 8, 64, True, -(1 << 63), (1 << 63) - 1, _constant("i64")),
}
_U8 = _INT_SPECS["u8"].const
_USIZE = _INT_SPECS["usize"].const
_NUMERICS_ALIASES: dict[str, str] = {
    "int": "i32",
    "uint": "u32",
    "long": "i64",
    "ulong": "u64",
}
_INT_INTRINSICS = {
    "ShiftLeft",
    "ShiftRight",
    "WrappingAdd",
    "WrappingSub",
    "WrappingMul",
    "WrappingNeg",
    "WrappingShiftLeft",
    "SaturatingAdd",
    "SaturatingSub",
    "SaturatingMul",
    "SaturatingNeg",
    "CheckedAdd",
    "CheckedSub",
    "CheckedMul",
    "CheckedNeg",
    "CheckedDiv",
    "CheckedRem",
    "CheckedShiftLeft",
    "CheckedShiftRight",
}


def _parse_numeric_magnitude(value: str) -> int:
    cleaned = value.replace("_", "")
    if cleaned.startswith(("0x", "0X")):
        return int(cleaned, 16)
    if cleaned.startswith(("0b", "0B")):
        return int(cleaned, 2)
    return int(cleaned, 10)


def _allows_from_conversion(src: _IntSpec, dst: _IntSpec) -> bool:
    if src.name == dst.name:
        return True
    if src.name == "usize" or dst.name == "usize":
        return dst.name == "usize" and src.name in {"u8", "u16", "u32"}
    return src.min_val >= dst.min_val and src.max_val <= dst.max_val


def _wrap_int(spec: _IntSpec, val: int) -> int:
    u = val & ((1 << spec.bits) - 1)
    if spec.signed and (u & (1 << (spec.bits - 1))):
        return u - (1 << spec.bits)
    return u


def _clamp_int(spec: _IntSpec, val: int) -> int:
    return min(spec.max_val, max(spec.min_val, val))


def _trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _trunc_rem(a: int, b: int) -> int:
    return a - _trunc_div(a, b) * b


def _int_term(spec: _IntSpec, value: int) -> _Term:
    return _term("int", spec.const, value=value)


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


@dataclass(frozen=True)
class _RecordInvariant:
    name: str
    self_var: _Term
    term: _Term
    type: _Term
    node: Node


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
    is_dependent: bool = False
    tail_sig_types: tuple[_Term, ...] = ()
    invariants: tuple[_RecordInvariant, ...] = ()


@dataclass(frozen=True)
class _UnionCtor:
    name: str
    ctor_const: str
    ctor_binding: _Binding
    fields: tuple[_RecordField, ...]
    payload_type: _Term
    index: int
    is_dependent: bool = False
    tail_sig_types: tuple[_Term, ...] = ()


@dataclass(frozen=True)
class _UnionInfo:
    name: str
    type_const: str
    type_binding: _Binding
    generic_vars: tuple[_Term, ...]
    constructors: tuple[_UnionCtor, ...]
    suffix_types: tuple[_Term, ...]


class _Elaborator:
    def __init__(self, protocol: _Protocol) -> None:
        self.protocol = protocol
        self.serial = 0
        self.work = MAX_WORK
        self.reductions = MAX_REDUCTIONS
        self.metas: list[_Meta] = []
        self.decl_first_meta = 0
        self.whnf_cache: dict[int, tuple[_Term, _Term]] = {}
        self.types: dict[int, _Term] = {}
        # Callable parameter labels are source metadata, never CIC constructors.
        self.parameter_names: dict[int, str] = {}
        self.nullary_parameters: set[int] = set()
        self.constant_parameters: set[int] = set()
        self.readonly_span_vars: set[int] = set()
        self.static_forbidden: set[int] | None = None
        self.globals: dict[str, _Binding] = {}
        self.constants: dict[str, _Binding] = {}
        self.definitions: dict[str, _Term] = {}
        self.records: dict[str, _RecordInfo] = {}
        self.records_by_type: dict[str, _RecordInfo] = {}
        self.records_by_ctor: dict[str, _RecordInfo] = {}
        self.record_projections: dict[str, tuple[_RecordInfo, int]] = {}
        self.unions: dict[str, _UnionInfo] = {}
        self.unions_by_type: dict[str, _UnionInfo] = {}
        self.union_ctors: dict[str, tuple[_UnionInfo, _UnionCtor]] = {}
        self.unions_by_ctor: dict[str, tuple[_UnionInfo, _UnionCtor]] = {}
        self.builtin_unions: set[str] = {"Result", "ArithmeticError", "ConversionError"}
        self.builtin_union_ctors: set[str] = {
            "Err", "Ok", "Overflow", "ZeroDivisor", "InvalidShift", "OutOfRange",
        }
        self.active_facts: list[_Term] = []
        self.callable_preconditions: dict[str, list[tuple[tuple[int, ...], _Term]]] = {}
        self.fix_names: dict[int, str] = {}
        self.current_rec_var: _Term | None = None
        self.current_rec_name: str | None = None
        self.current_rec_generics: list[_Term] = []
        self.current_rec_params: list[_Term] = []
        self.current_rec_candidates: list[tuple[int, int]] = []
        self.current_rec_used: bool = False
        self.smaller_vars: dict[int, set[int]] = {}
        self.current_return_type: _Term | None = None
        self.mutable_locals: set[str] = set()
        self.entry_env: dict[str, _Binding] = {}
        self.final_ref_bindings: dict[str, _Binding] = {}
        self.final_return_facts: list[_Term] = []
        self.frozen_collections: set[str] = set()
        self.lifted_invariants: dict[str, set[str]] = {}
        self.active_lift_scopes: int = 0
        self.in_loop_depth: int = 0
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
        for spec in _INT_SPECS.values():
            bind(spec.name, _SORT)
        self.globals["byte"] = self.globals["u8"]
        for alias_name, target_name in _NUMERICS_ALIASES.items():
            self.globals[f"Vela.Numerics.{alias_name}"] = self.globals[target_name]
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
        bind("Span", telescope((a,), _SORT))
        span_a = _app(_constant("Span"), a)
        self.constants["Span_Base"] = _Binding(_constant("Span_Base"), telescope((a,), self.pi(span_a, _USIZE)), 1)
        self.constants["Span_Length"] = _Binding(_constant("Span_Length"), telescope((a,), self.pi(span_a, _USIZE)), 1)
        self.constants["Span_Tag"] = _Binding(_constant("Span_Tag"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_PermRead"] = _Binding(_constant("Span_PermRead"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_PermWrite"] = _Binding(_constant("Span_PermWrite"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_CanRead"] = _Binding(_constant("Span_CanRead"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_CanWrite"] = _Binding(_constant("Span_CanWrite"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_AllocZeroed"] = _Binding(
            _constant("Span_AllocZeroed"),
            telescope((a,), self.pi(_USIZE, self.pi(_USIZE, span_a))),
            1,
        )
        self.constants["Span_ReadOnly"] = _Binding(
            _constant("Span_ReadOnly"),
            telescope((a,), self.pi(span_a, span_a)),
            1,
        )
        self.constants["Span_Invalidate"] = _Binding(
            _constant("Span_Invalidate"),
            telescope((a,), self.pi(span_a, span_a)),
            1,
        )
        self.constants["Span_Disjoint"] = _Binding(
            _constant("Span_Disjoint"),
            telescope((a,), self.pi(span_a, self.pi(span_a, _BOOL))),
            1,
        )
        self.constants["Span_Read"] = _Binding(
            _constant("Span_Read"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, a))),
            1,
        )
        self.constants["Span_Write"] = _Binding(
            _constant("Span_Write"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, self.pi(a, span_a)))),
            1,
        )
        self.constants["Span_Fill"] = _Binding(
            _constant("Span_Fill"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, self.pi(_USIZE, self.pi(a, span_a))))),
            1,
        )
        self.constants["Span_Slice"] = _Binding(
            _constant("Span_Slice"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, self.pi(_USIZE, span_a)))),
            1,
        )
        self.constants["Span_CopyPrefix"] = _Binding(
            _constant("Span_CopyPrefix"),
            telescope((a,), self.pi(span_a, self.pi(span_a, self.pi(_USIZE, span_a)))),
            1,
        )
        self.constants["Span_Restore"] = _Binding(
            _constant("Span_Restore"),
            telescope((a,), self.pi(span_a, self.pi(span_a, span_a))),
            1,
        )
        bind("Seq", telescope((a,), _SORT))
        seq_a = _app(_constant("Seq"), a)
        self.constants["Seq_Empty"] = _Binding(_constant("Seq_Empty"), telescope((a,), seq_a), 1)
        self.constants["Seq_Cons"] = _Binding(
            _constant("Seq_Cons"), telescope((a,), self.pi(a, self.pi(seq_a, seq_a))), 1
        )
        self.constants["Seq_Singleton"] = _Binding(
            _constant("Seq_Singleton"), telescope((a,), self.pi(a, seq_a)), 1
        )
        self.constants["Seq_Count"] = _Binding(
            _constant("Seq_Count"), telescope((a,), self.pi(seq_a, _NAT)), 1
        )
        self.constants["Seq_At"] = _Binding(
            _constant("Seq_At"), telescope((a,), self.pi(a, self.pi(seq_a, self.pi(_NAT, a)))), 1
        )
        self.constants["Seq_Update"] = _Binding(
            _constant("Seq_Update"), telescope((a,), self.pi(seq_a, self.pi(_NAT, self.pi(a, seq_a)))), 1
        )
        self.constants["Seq_Append"] = _Binding(
            _constant("Seq_Append"), telescope((a,), self.pi(seq_a, self.pi(seq_a, seq_a))), 1
        )
        self.constants["Seq_Take"] = _Binding(
            _constant("Seq_Take"), telescope((a,), self.pi(seq_a, self.pi(_NAT, seq_a))), 1
        )
        self.constants["Seq_Skip"] = _Binding(
            _constant("Seq_Skip"), telescope((a,), self.pi(seq_a, self.pi(_NAT, seq_a))), 1
        )
        self.constants["Seq_Slice"] = _Binding(
            _constant("Seq_Slice"), telescope((a,), self.pi(seq_a, self.pi(_NAT, self.pi(_NAT, seq_a)))), 1
        )
        self.constants["Seq_Contains"] = _Binding(
            _constant("Seq_Contains"), telescope((a,), self.pi(seq_a, self.pi(a, _BOOL))), 1
        )
        self.constants["Seq_All"] = _Binding(
            _constant("Seq_All"), telescope((a,), self.pi(seq_a, self.pi(self.pi(a, _BOOL), _BOOL))), 1
        )
        self.constants["Seq_Any"] = _Binding(
            _constant("Seq_Any"), telescope((a,), self.pi(seq_a, self.pi(self.pi(a, _BOOL), _BOOL))), 1
        )
        self.constants["nat_to_usize"] = _Binding(
            _constant("nat_to_usize"), self.pi(_NAT, _USIZE), 0
        )
        self.constants["Vec_Model"] = _Binding(
            _constant("Vec_Model"), telescope((a, n), self.pi(vec, seq_a)), 2
        )
        self.constants["Span_Model"] = _Binding(
            _constant("Span_Model"), telescope((a,), self.pi(span_a, _app(_constant("Seq"), _U8))), 1
        )
        bind("Slots", telescope((a, n), _SORT))
        slots_an = _apps(_constant("Slots"), a, n)
        m = self.fresh(_NAT)
        slots_am = _apps(_constant("Slots"), a, m)
        self.constants["Slots_Mk"] = _Binding(
            _constant("Slots_Mk"),
            telescope(
                (a, n),
                self.pi(
                    _USIZE,
                    self.pi(
                        _USIZE,
                        self.pi(
                            _BOOL,
                            self.pi(_BOOL, self.pi(_BOOL, self.pi(seq_a, self.pi(seq_a, slots_an)))),
                        ),
                    ),
                ),
            ),
            2,
        )
        self.constants["Slots_Base"] = _Binding(
            _constant("Slots_Base"), telescope((a, n), self.pi(slots_an, _USIZE)), 2
        )
        self.constants["Slots_LiveCount"] = _Binding(
            _constant("Slots_LiveCount"), telescope((a, n), self.pi(slots_an, _USIZE)), 2
        )
        self.constants["Slots_Tag"] = _Binding(
            _constant("Slots_Tag"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_PermRead"] = _Binding(
            _constant("Slots_PermRead"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_PermWrite"] = _Binding(
            _constant("Slots_PermWrite"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_CanRead"] = _Binding(
            _constant("Slots_CanRead"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_CanWrite"] = _Binding(
            _constant("Slots_CanWrite"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_RepModel"] = _Binding(
            _constant("Slots_RepModel"), telescope((a, n), self.pi(slots_an, seq_a)), 2
        )
        self.constants["Slots_Model"] = _Binding(
            _constant("Slots_Model"), telescope((a, n), self.pi(slots_an, seq_a)), 2
        )
        self.constants["Slots_AllocVacant"] = _Binding(
            _constant("Slots_AllocVacant"), telescope((a, n), self.pi(_USIZE, slots_an)), 2
        )
        self.constants["Slots_Write"] = _Binding(
            _constant("Slots_Write"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, self.pi(a, slots_an)))),
            2,
        )
        self.constants["Slots_Read"] = _Binding(
            _constant("Slots_Read"),
            telescope((a, n), self.pi(a, self.pi(slots_an, self.pi(_USIZE, a)))),
            2,
        )
        self.constants["Slots_LivePrefix"] = _Binding(
            _constant("Slots_LivePrefix"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, _BOOL))),
            2,
        )
        self.constants["Slots_VacantRange"] = _Binding(
            _constant("Slots_VacantRange"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, self.pi(_USIZE, _BOOL)))),
            2,
        )
        self.constants["Slots_Disjoint"] = _Binding(
            _constant("Slots_Disjoint"),
            telescope((a, n, m), self.pi(slots_an, self.pi(slots_am, _BOOL))),
            3,
        )
        self.constants["Slots_RepEqual"] = _Binding(
            _constant("Slots_RepEqual"),
            telescope((a, n, m), self.pi(slots_an, self.pi(slots_am, self.pi(_USIZE, _BOOL)))),
            3,
        )
        self.constants["Slots_CopyRepresentation"] = _Binding(
            _constant("Slots_CopyRepresentation"),
            telescope((a, n, m), self.pi(slots_an, self.pi(slots_am, self.pi(_USIZE, slots_am)))),
            3,
        )
        self.constants["Slots_TransferSource"] = _Binding(
            _constant("Slots_TransferSource"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, slots_an))),
            2,
        )
        self.constants["Slots_TransferDest"] = _Binding(
            _constant("Slots_TransferDest"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, slots_an))),
            2,
        )
        self.constants["Slots_TransferType"] = _Binding(
            _constant("Slots_TransferType"),
            telescope(
                (a, n, m),
                self.pi(slots_an, self.pi(slots_am, self.pi(_USIZE, _term("prod", slots_an, slots_am)))),
            ),
            3,
        )
        self.constants["PrefixModel"] = _Binding(
            _constant("PrefixModel"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, seq_a))),
            2,
        )
        self.constants["LoopState"] = _Binding(
            _constant("LoopState"),
            telescope((a,), self.pi(a, self.pi(_NAT, a))),
            1,
        )
        self._register_builtin_unions()
        self._register_int_constants()

    def _register_builtin_unions(self) -> None:
        # ArithmeticError { Overflow(); ZeroDivisor(); InvalidShift(); }
        ae_type_const = "vela_ArithmeticError"
        ae_rep_type = _term("sum", _UNIT, _term("sum", _UNIT, _UNIT))
        ae_type_binding = _Binding(_constant(ae_type_const), _SORT, 0)
        self.globals["ArithmeticError"] = ae_type_binding
        self.constants[ae_type_const] = ae_type_binding
        ae_ctors: list[_UnionCtor] = []
        for idx, cname in enumerate(("Overflow", "ZeroDivisor", "InvalidShift")):
            c_const = f"vela_ArithmeticError_{cname}"
            u_var = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", u_var.value))
            c_sig = _term("pi", _UNIT, _constant(ae_type_const), value=u_var.value)
            c_binding = _Binding(_constant(c_const), c_sig, 0)
            self.globals[cname] = c_binding
            self.constants[c_const] = c_binding
            ae_ctors.append(_UnionCtor(cname, c_const, c_binding, (), _UNIT, idx))
        ae_info = _UnionInfo(
            "ArithmeticError",
            ae_type_const,
            ae_type_binding,
            (),
            tuple(ae_ctors),
            (ae_rep_type, _term("sum", _UNIT, _UNIT), _UNIT),
        )
        self.unions["ArithmeticError"] = ae_info
        self.unions_by_type[ae_type_const] = ae_info
        for uc in ae_ctors:
            self.union_ctors[uc.name] = (ae_info, uc)
            self.unions_by_ctor[uc.ctor_const] = (ae_info, uc)

        # ConversionError { OutOfRange(); }
        ce_type_const = "vela_ConversionError"
        ce_type_binding = _Binding(_constant(ce_type_const), _SORT, 0)
        self.globals["ConversionError"] = ce_type_binding
        self.constants[ce_type_const] = ce_type_binding
        oor_const = "vela_ConversionError_OutOfRange"
        oor_u = self.fresh(_UNIT)
        self.nullary_parameters.add(cast("int", oor_u.value))
        oor_sig = _term("pi", _UNIT, _constant(ce_type_const), value=oor_u.value)
        oor_binding = _Binding(_constant(oor_const), oor_sig, 0)
        self.globals["OutOfRange"] = oor_binding
        self.constants[oor_const] = oor_binding
        oor_ctor = _UnionCtor("OutOfRange", oor_const, oor_binding, (), _UNIT, 0)
        ce_info = _UnionInfo(
            "ConversionError",
            ce_type_const,
            ce_type_binding,
            (),
            (oor_ctor,),
            (_UNIT,),
        )
        self.unions["ConversionError"] = ce_info
        self.unions_by_type[ce_type_const] = ce_info
        self.union_ctors["OutOfRange"] = (ce_info, oor_ctor)
        self.unions_by_ctor[oor_const] = (ce_info, oor_ctor)

        # Result<TValue, TError> { Err(TError Error); Ok(TValue Value); }
        res_type_const = "vela_Result"
        tv_var = self.fresh(_SORT)
        te_var = self.fresh(_SORT)
        res_rep = _term("sum", te_var, tv_var)
        res_sig = self.wrap("pi", [tv_var, te_var], _SORT)
        res_type_binding = _Binding(_constant(res_type_const), res_sig, 2)
        self.globals["Result"] = res_type_binding
        self.constants[res_type_const] = res_type_binding
        res_app = _apps(_constant(res_type_const), tv_var, te_var)

        err_fvar = self.fresh(te_var)
        self.parameter_names[cast("int", err_fvar.value)] = "Error"
        err_const = "vela_Result_Err"
        err_sig = self.wrap("pi", [tv_var, te_var, err_fvar], res_app)
        err_binding = _Binding(_constant(err_const), err_sig, 2)
        self.globals["Err"] = err_binding
        self.constants[err_const] = err_binding
        err_ctor = _UnionCtor(
            "Err", err_const, err_binding, (_RecordField("Error", err_fvar, te_var, ""),), te_var, 0
        )

        ok_fvar = self.fresh(tv_var)
        self.parameter_names[cast("int", ok_fvar.value)] = "Value"
        ok_const = "vela_Result_Ok"
        ok_sig = self.wrap("pi", [tv_var, te_var, ok_fvar], res_app)
        ok_binding = _Binding(_constant(ok_const), ok_sig, 2)
        self.globals["Ok"] = ok_binding
        self.constants[ok_const] = ok_binding
        ok_ctor = _UnionCtor(
            "Ok", ok_const, ok_binding, (_RecordField("Value", ok_fvar, tv_var, ""),), tv_var, 1
        )

        res_info = _UnionInfo(
            "Result",
            res_type_const,
            res_type_binding,
            (tv_var, te_var),
            (err_ctor, ok_ctor),
            (res_rep, tv_var),
        )
        self.unions["Result"] = res_info
        self.unions_by_type[res_type_const] = res_info
        self.union_ctors["Err"] = (res_info, err_ctor)
        self.union_ctors["Ok"] = (res_info, ok_ctor)
        self.unions_by_ctor[err_const] = (res_info, err_ctor)
        self.unions_by_ctor[ok_const] = (res_info, ok_ctor)

    def _register_int_constants(self) -> None:
        ae_const = _constant(self.unions["ArithmeticError"].type_const)
        ce_const = _constant(self.unions["ConversionError"].type_const)
        res_const = _constant(self.unions["Result"].type_const)
        for spec in _INT_SPECS.values():
            t = spec.const
            res_arith = _apps(res_const, t, ae_const)
            res_conv = _apps(res_const, t, ce_const)
            for op in (
                "add", "sub", "mul", "div", "rem", "and", "or", "xor",
                "wrap_add", "wrap_sub", "wrap_mul", "sat_add", "sat_sub", "sat_mul",
            ):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(t, t)))
            for op in ("neg", "not", "wrap_neg", "sat_neg"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, t))
            for op in ("eq", "ne", "lt", "le", "gt", "ge"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(t, _BOOL)))
            for op in ("shl", "shr", "wrap_shl"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(_USIZE, t)))
            for op in ("chk_add", "chk_sub", "chk_mul", "chk_div", "chk_rem"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(t, res_arith)))
            cname_cneg = f"int_chk_neg_{spec.name}"
            self.constants[cname_cneg] = _Binding(_constant(cname_cneg), self.pi(t, res_arith))
            for op in ("chk_shl", "chk_shr"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(_USIZE, res_arith)))
            cname_nat = f"int_to_nat_{spec.name}"
            self.constants[cname_nat] = _Binding(_constant(cname_nat), self.pi(t, _NAT))
            cname_tf_nat = f"int_try_from_Nat_{spec.name}"
            self.constants[cname_tf_nat] = _Binding(_constant(cname_tf_nat), self.pi(_NAT, res_conv))
            for src in _INT_SPECS.values():
                cname_from = f"int_from_{src.name}_{spec.name}"
                self.constants[cname_from] = _Binding(_constant(cname_from), self.pi(src.const, t))
                cname_tf = f"int_try_from_{src.name}_{spec.name}"
                self.constants[cname_tf] = _Binding(_constant(cname_tf), self.pi(src.const, res_conv))

    def _int_spec(self, type_term: _Term) -> _IntSpec | None:
        resolved = self.whnf(type_term)
        if resolved.kind == "const" and isinstance(resolved.value, str):
            return _INT_SPECS.get(resolved.value)
        return None

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

    def substitute(
        self,
        term: _Term,
        variable: int,
        replacement: _Term,
        memo: dict[int, tuple[_Term, _Term]] | None = None,
    ) -> _Term:
        if memo is None:
            memo = {}
        tid = id(term)
        if tid in memo:
            return memo[tid][1]
        self.tick()
        resolved = self.resolve(term)
        if resolved.kind == "var" and resolved.value == variable:
            memo[tid] = (term, replacement)
            return replacement
        if resolved.kind in {"pi", "lam"} and resolved.value == variable:
            new_dom = self.substitute(resolved.args[0], variable, replacement, memo)
            res = (
                resolved
                if new_dom is resolved.args[0]
                else _term(resolved.kind, new_dom, resolved.args[1], value=resolved.value)
            )
            memo[tid] = (term, res)
            return res
        if resolved.kind == "let" and resolved.value == variable:
            new_dom = self.substitute(resolved.args[0], variable, replacement, memo)
            new_val = self.substitute(resolved.args[1], variable, replacement, memo)
            res = (
                resolved
                if (new_dom is resolved.args[0] and new_val is resolved.args[1])
                else _term("let", new_dom, new_val, resolved.args[2], value=resolved.value)
            )
            memo[tid] = (term, res)
            return res
        if resolved.kind == "fix" and resolved.value == variable:
            new_sig = self.substitute(resolved.args[0], variable, replacement, memo)
            res = (
                resolved
                if new_sig is resolved.args[0]
                else _term(
                    "fix",
                    new_sig,
                    resolved.args[1],
                    resolved.args[2],
                    resolved.args[3],
                    value=resolved.value,
                )
            )
            memo[tid] = (term, res)
            return res
        if not resolved.args:
            memo[tid] = (term, resolved)
            return resolved
        new_args = tuple(self.substitute(value, variable, replacement, memo) for value in resolved.args)
        if all(na is oa for na, oa in zip(new_args, resolved.args, strict=True)):
            memo[tid] = (term, resolved)
            return resolved
        res = _Term(resolved.kind, resolved.value, new_args)
        memo[tid] = (term, res)
        return res

    def free(
        self, term: _Term, memo: dict[int, tuple[_Term, frozenset[int]]] | None = None
    ) -> set[int]:
        if memo is None:
            memo = {}
        tid = id(term)
        if tid in memo:
            return set(memo[tid][1])
        self.tick()
        term = self.resolve(term)
        if term.kind == "var":
            fset = frozenset({cast("int", term.value)})
            memo[tid] = (term, fset)
            return set(fset)
        result: set[int] = set()
        for argument in term.args:
            result.update(self.free(argument, memo))
        if term.kind in {"pi", "lam", "let", "fix"}:
            result.discard(cast("int", term.value))
        memo[tid] = (term, frozenset(result))
        return result

    def _is_whnf_constructor(self, term: _Term) -> bool:
        if term.kind in {"nat", "int", "bool", "unit", "pair", "inl", "inr", "existT"}:
            return True
        if term.kind == "app" and term.args[0] == _constant("Succ"):
            return True
        head, _ = self.spine(term)
        return (
            head.kind == "const"
            and isinstance(head.value, str)
            and (head.value in self.records_by_ctor or head.value in self.unions_by_ctor)
        )

    def _lam_arity(self, term: _Term) -> int:
        count = 0
        curr = self.resolve(term)
        while curr.kind == "lam":
            count += 1
            curr = self.resolve(curr.args[1])
        return count

    def _build_dependent_record_tail(
        self, record_info: _RecordInfo, type_args: list[_Term], field_vals: list[_Term]
    ) -> _Term:
        right_val = field_vals[-1]
        for k in range(len(field_vals) - 2, 0, -1):
            fv = field_vals[k]
            fvar_id = cast("int", record_info.fields[k].var.value)
            ftype = self._instantiate_record_type(record_info, type_args, record_info.fields[k].type)
            tail_type = self._instantiate_record_type(record_info, type_args, record_info.tail_sig_types[k + 1])
            for j in range(k):
                earlier_id = cast("int", record_info.fields[j].var.value)
                ftype = self.substitute(ftype, earlier_id, field_vals[j])
                tail_type = self.substitute(tail_type, earlier_id, field_vals[j])
            fam_lam = _term("lam", ftype, tail_type, value=fvar_id)
            right_val = _term("existT", ftype, fam_lam, fv, right_val)
        return right_val

    def occurs(self, index: int, term: _Term) -> bool:
        term = self.resolve(term)
        return ((term.kind == "meta" and term.value == index)
                or any(self.occurs(index, child) for child in term.args))

    def natural_limit(self) -> int:
        return MAX_CONSTANT_NAT if self.static_forbidden is not None else (1 << MAX_NAT_BITS) - 1

    def whnf(self, term: _Term) -> _Term:
        self.tick()
        term = self.resolve(term)
        if self.static_forbidden is None and len(self.metas) == self.decl_first_meta:
            tid = id(term)
            cached = self.whnf_cache.get(tid)
            if cached is not None:
                return cached[1]
            res = self._whnf_core(term)
            self.whnf_cache[tid] = (term, res)
            self.whnf_cache[id(res)] = (res, res)
            return res
        return self._whnf_core(term)

    def _whnf_core(self, term: _Term) -> _Term:
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
                expected_whnf = self.whnf(term.args[0])
                kind = (
                    "int"
                    if self._int_spec(expected_whnf) is not None
                    else {_NAT: "nat", _BOOL: "bool", _UNIT: "unit"}[expected_whnf]
                )
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
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
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
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
            if scrutinee.kind == "pair":
                self.tick(True)
                branch = term.args[2]
                inner = self.substitute(branch.args[1], cast("int", branch.value), scrutinee.args[2])
                return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), scrutinee.args[3]))
            rec_head, rec_args = self.spine(scrutinee)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if (
                    not record_info.is_dependent
                    and record_info.fields
                    and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)
                ):
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
        if term.kind == "sigT_match":
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
            if scrutinee.kind == "existT":
                self.tick(True)
                branch = term.args[2]
                inner = self.substitute(branch.args[1], cast("int", branch.value), scrutinee.args[2])
                return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), scrutinee.args[3]))
            rec_head, rec_args = self.spine(scrutinee)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if (
                    record_info.is_dependent
                    and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)
                ):
                    self.tick(True)
                    type_args = rec_args[:len(record_info.generic_vars)]
                    field_vals = rec_args[len(record_info.generic_vars):]
                    left_val = field_vals[0]
                    right_val = self._build_dependent_record_tail(record_info, type_args, field_vals)
                    branch = term.args[2]
                    inner = self.substitute(branch.args[1], cast("int", branch.value), left_val)
                    return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), right_val))
            return term
        if term.kind in {"projT1", "projT2"}:
            pair_val = self._expand_union_ctor(self.whnf(term.args[2]))
            if pair_val.kind == "existT":
                self.tick(True)
                return self.whnf(pair_val.args[2] if term.kind == "projT1" else pair_val.args[3])
            rec_head, rec_args = self.spine(pair_val)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if (
                    record_info.is_dependent
                    and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)
                ):
                    self.tick(True)
                    type_args = rec_args[:len(record_info.generic_vars)]
                    field_vals = rec_args[len(record_info.generic_vars):]
                    if term.kind == "projT1":
                        return self.whnf(field_vals[0])
                    return self.whnf(self._build_dependent_record_tail(record_info, type_args, field_vals))
            return term
        if term.kind == "sum_match":
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
            if scrutinee.kind == "inl":
                self.tick(True)
                left_branch = term.args[2]
                return self.whnf(self.substitute(left_branch.args[1], cast("int", left_branch.value), scrutinee.args[2]))
            if scrutinee.kind == "inr":
                self.tick(True)
                right_branch = term.args[3]
                return self.whnf(self.substitute(right_branch.args[1], cast("int", right_branch.value), scrutinee.args[2]))
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
            if self.definitions[term.value].kind == "fix":
                return term
            self.tick(True)
            return self.whnf(self.definitions[term.value])
        if term.kind != "app":
            return term
        head, arguments = self.spine(term)
        if head.kind == "const" and head.value not in self.definitions:
            pass
        else:
            new_head = self.whnf(head)
            if new_head.kind == "lam":
                self.tick(True)
                substituted = self.substitute(new_head.args[1], cast("int", new_head.value), arguments[0])
                return self.whnf(_apps(substituted, *arguments[1:]))
            if new_head != head:
                term = _apps(new_head, *arguments)
                head, arguments = self.spine(term)
        if head.kind == "fix":
            struct_idx = cast("int", head.args[3].value)
            total_arity = self._lam_arity(head.args[1])
            if len(arguments) >= total_arity and self._is_whnf_constructor(self.whnf(arguments[struct_idx])):
                self.tick(True)
                fix_id = cast("int", head.value)
                self_rep = _constant(self.fix_names[fix_id]) if fix_id in self.fix_names else head
                unfolded = self.substitute(head.args[1], fix_id, self_rep)
                return self.whnf(_apps(unfolded, *arguments))
            return term
        if head.kind != "const":
            return term
        name = head.value
        if isinstance(name, str) and name in self.definitions and self.definitions[name].kind == "fix":
            fix_term = self.definitions[name]
            struct_idx = cast("int", fix_term.args[3].value)
            total_arity = self._lam_arity(fix_term.args[1])
            if len(arguments) >= total_arity and self._is_whnf_constructor(self.whnf(arguments[struct_idx])):
                self.tick(True)
                unfolded = self.substitute(fix_term.args[1], cast("int", fix_term.value), _constant(name))
                return self.whnf(_apps(unfolded, *arguments))
        if isinstance(name, str) and name in self.record_projections:
            record_info, field_index = self.record_projections[name]
            proj_arity = len(record_info.generic_vars) + 1
            if len(arguments) >= proj_arity:
                rec_val = self.whnf(arguments[proj_arity - 1])
                rec_head, rec_args = self.spine(rec_val)
                if (rec_head == _constant(record_info.ctor_const)
                        and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)):
                    self.tick(True)
                    projected = rec_args[len(record_info.generic_vars) + field_index]
                    return self.whnf(_apps(projected, *arguments[proj_arity:]))
        if name in {"Fst", "Snd"} and len(arguments) >= 3:
            pair = self.whnf(arguments[2])
            if pair.kind == "pair":
                self.tick(True)
                projected = pair.args[2] if name == "Fst" else pair.args[3]
                return self.whnf(_apps(projected, *arguments[3:]))
        if name == "At" and len(arguments) >= 4:
            vector, values = self.spine(self.whnf(arguments[2]))
            index, indices = self.spine(self.whnf(arguments[3]))
            if vector == _constant("VCons") and len(values) == 4:
                if index == _constant("FZero") and len(indices) == 2:
                    self.tick(True)
                    return self.whnf(_apps(values[2], *arguments[4:]))
                if index == _constant("FSucc") and len(indices) == 2:
                    self.tick(True)
                    at_step = _apps(_constant("At"), arguments[0], values[1], values[3], indices[1])
                    return self.whnf(_apps(at_step, *arguments[4:]))
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
        if name == "nat_to_usize" and len(arguments) == 1:
            n_w = self.whnf(arguments[0])
            if n_w.kind == "nat":
                self.tick(True)
                return _int_term(_INT_SPECS["usize"], cast("int", n_w.value))
        if isinstance(name, str) and name.startswith("int_"):
            reduced_int = self._whnf_int_op(name, arguments)
            if reduced_int is not None:
                return reduced_int
        if isinstance(name, str) and name.startswith("Span_"):
            reduced_span = self._whnf_span_op(name, arguments)
            if reduced_span is not None:
                return reduced_span
        if isinstance(name, str) and (name.startswith("Seq_") or name in {"Vec_Model", "Span_Model"}):
            reduced_seq = self._whnf_seq_op(name, arguments)
            if reduced_seq is not None:
                return reduced_seq
        if isinstance(name, str) and (name.startswith("Slots_") or name == "PrefixModel"):
            reduced_slots = self._whnf_slots_op(name, arguments)
            if reduced_slots is not None:
                return reduced_slots
        if head.value == "if" and len(arguments) >= 4:
            condition = self.whnf(arguments[1])
            if condition.kind == "bool":
                self.tick(True)
                chosen = arguments[2] if condition.value else arguments[3]
                return self.whnf(_apps(chosen, *arguments[4:]))
        return term

    def _make_result_ok(self, val_type: _Term, err_type: _Term, val_term: _Term) -> _Term:
        res_union = self.unions["Result"]
        ok_ctor = next(c for c in res_union.constructors if c.name == "Ok")
        return _apps(_constant(ok_ctor.ctor_const), val_type, err_type, val_term)

    def _make_result_err(self, val_type: _Term, err_type: _Term, err_term: _Term) -> _Term:
        res_union = self.unions["Result"]
        err_ctor = next(c for c in res_union.constructors if c.name == "Err")
        return _apps(_constant(err_ctor.ctor_const), val_type, err_type, err_term)

    def _make_arith_err(self, ctor_name: str) -> _Term:
        ae_union = self.unions["ArithmeticError"]
        ctor = next(c for c in ae_union.constructors if c.name == ctor_name)
        return _app(_constant(ctor.ctor_const), _term("unit"))

    def _make_conv_err(self) -> _Term:
        ce_union = self.unions["ConversionError"]
        ctor = ce_union.constructors[0]
        return _app(_constant(ctor.ctor_const), _term("unit"))

    def _whnf_int_op(self, name: str, arguments: list[_Term]) -> _Term | None:
        ae_const = _constant(self.unions["ArithmeticError"].type_const)
        ce_const = _constant(self.unions["ConversionError"].type_const)
        if name.startswith("int_to_nat_") and len(arguments) == 1:
            arg = self.whnf(arguments[0])
            if arg.kind == "int":
                self.tick(True)
                return _term("nat", value=max(0, cast("int", arg.value)))
            return None
        if name.startswith("int_from_") and len(arguments) == 1:
            parts = name.split("_")
            dst_spec = _INT_SPECS[parts[3]]
            arg = self.whnf(arguments[0])
            if arg.kind == "int":
                self.tick(True)
                return _int_term(dst_spec, cast("int", arg.value))
            return None
        if name.startswith("int_try_from_") and len(arguments) == 1:
            parts = name.split("_")
            dst_spec = _INT_SPECS[parts[4]]
            arg = self.whnf(arguments[0])
            if arg.kind in {"int", "nat"}:
                self.tick(True)
                val = cast("int", arg.value)
                if dst_spec.min_val <= val <= dst_spec.max_val:
                    return self._make_result_ok(dst_spec.const, ce_const, _int_term(dst_spec, val))
                return self._make_result_err(dst_spec.const, ce_const, self._make_conv_err())
            return None
        prefix, spec_name = name.rsplit("_", 1)
        spec = _INT_SPECS.get(spec_name)
        if spec is None:
            return None
        op = prefix[4:]  # strip "int_"
        if len(arguments) == 1 and op in {"neg", "not", "wrap_neg", "sat_neg", "chk_neg"}:
            arg = self.whnf(arguments[0])
            if arg.kind != "int":
                return None
            self.tick(True)
            a = cast("int", arg.value)
            if op in {"neg", "wrap_neg"}:
                return _int_term(spec, _wrap_int(spec, -a))
            if op == "not":
                return _int_term(spec, _wrap_int(spec, ~a))
            if op == "sat_neg":
                return _int_term(spec, _clamp_int(spec, -a))
            if spec.min_val <= -a <= spec.max_val:
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, -a))
            return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
        if len(arguments) == 2:
            left = self.whnf(arguments[0])
            right = self.whnf(arguments[1])
            if left.kind != "int" or right.kind != "int":
                return None
            self.tick(True)
            a = cast("int", left.value)
            b = cast("int", right.value)
            if op in {"add", "wrap_add"}:
                return _int_term(spec, _wrap_int(spec, a + b))
            if op in {"sub", "wrap_sub"}:
                return _int_term(spec, _wrap_int(spec, a - b))
            if op in {"mul", "wrap_mul"}:
                return _int_term(spec, _wrap_int(spec, a * b))
            if op == "div":
                if b == 0:
                    return _int_term(spec, 0)
                return _int_term(spec, _wrap_int(spec, _trunc_div(a, b)))
            if op == "rem":
                if b == 0:
                    return _int_term(spec, a)
                if spec.signed and a == spec.min_val and b == -1:
                    return _int_term(spec, 0)
                return _int_term(spec, _wrap_int(spec, _trunc_rem(a, b)))
            if op == "and":
                return _int_term(spec, _wrap_int(spec, a & b))
            if op == "or":
                return _int_term(spec, _wrap_int(spec, a | b))
            if op == "xor":
                return _int_term(spec, _wrap_int(spec, a ^ b))
            if op == "sat_add":
                return _int_term(spec, _clamp_int(spec, a + b))
            if op == "sat_sub":
                return _int_term(spec, _clamp_int(spec, a - b))
            if op == "sat_mul":
                return _int_term(spec, _clamp_int(spec, a * b))
            if op == "eq":
                return _term("bool", value=int(a == b))
            if op == "ne":
                return _term("bool", value=int(a != b))
            if op == "lt":
                return _term("bool", value=int(a < b))
            if op == "le":
                return _term("bool", value=int(a <= b))
            if op == "gt":
                return _term("bool", value=int(a > b))
            if op == "ge":
                return _term("bool", value=int(a >= b))
            if op in {"shl", "wrap_shl"}:
                if not 0 <= b < spec.bits:
                    return _int_term(spec, 0)
                return _int_term(spec, _wrap_int(spec, a << b))
            if op == "shr":
                if not 0 <= b < spec.bits:
                    return _int_term(spec, -1 if (spec.signed and a < 0) else 0)
                if spec.signed:
                    return _int_term(spec, a >> b)
                return _int_term(spec, (a & ((1 << spec.bits) - 1)) >> b)
            if op == "chk_add":
                if spec.min_val <= a + b <= spec.max_val:
                    return self._make_result_ok(spec.const, ae_const, _int_term(spec, a + b))
                return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
            if op == "chk_sub":
                if spec.min_val <= a - b <= spec.max_val:
                    return self._make_result_ok(spec.const, ae_const, _int_term(spec, a - b))
                return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
            if op == "chk_mul":
                if spec.min_val <= a * b <= spec.max_val:
                    return self._make_result_ok(spec.const, ae_const, _int_term(spec, a * b))
                return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
            if op == "chk_div":
                if b == 0:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("ZeroDivisor"))
                if spec.signed and a == spec.min_val and b == -1:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, _trunc_div(a, b)))
            if op == "chk_rem":
                if b == 0:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("ZeroDivisor"))
                if spec.signed and a == spec.min_val and b == -1:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, _trunc_rem(a, b)))
            if op == "chk_shl":
                if not 0 <= b < spec.bits:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("InvalidShift"))
                if not spec.min_val <= (a << b) <= spec.max_val:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, a << b))
            if op == "chk_shr":
                if not 0 <= b < spec.bits:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("InvalidShift"))
                shifted = (a >> b) if spec.signed else ((a & ((1 << spec.bits) - 1)) >> b)
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, shifted))
        return None

    def _eval_in_extent(self, addr: _Term, base: _Term, count: _Term) -> bool | None:
        addr_w = self.whnf(addr)
        base_w = self.whnf(base)
        count_w = self.whnf(count)
        if addr_w.kind == "int" and base_w.kind == "int" and count_w.kind == "int":
            a_v = cast("int", addr_w.value)
            b_v = cast("int", base_w.value)
            c_v = cast("int", count_w.value)
            return b_v <= a_v < b_v + c_v
        return None

    def _lookup_span_at_addr(self, elem: _Term, span_term: _Term, addr: _Term) -> _Term | None:
        self.tick()
        s = self.whnf(span_term)
        s_head, s_args = self.spine(s)
        if s_head.kind != "const" or not isinstance(s_head.value, str):
            return None
        sname = s_head.value
        if sname == "Span_AllocZeroed" and len(s_args) == 3:
            return _int_term(_INT_SPECS["u8"], 0)
        if sname in {"Span_ReadOnly", "Span_Invalidate"} and len(s_args) == 2:
            return self._lookup_span_at_addr(elem, s_args[1], addr)
        if sname == "Span_Slice" and len(s_args) == 4:
            return self._lookup_span_at_addr(elem, s_args[1], addr)
        if sname == "Span_Restore" and len(s_args) == 3:
            return self._lookup_span_at_addr(elem, s_args[2], addr)
        if sname == "Span_Write" and len(s_args) == 4:
            inner, w_idx, val = s_args[1], s_args[2], s_args[3]
            inner_base = self.whnf(_apps(_constant("Span_Base"), elem, inner))
            w_idx_w = self.whnf(w_idx)
            addr_w = self.whnf(addr)
            if inner_base.kind == "int" and w_idx_w.kind == "int" and addr_w.kind == "int":
                w_addr_v = _wrap_int(_INT_SPECS["usize"], cast("int", inner_base.value) + cast("int", w_idx_w.value))
                if cast("int", addr_w.value) == w_addr_v:
                    return self.whnf(val)
                return self._lookup_span_at_addr(elem, inner, addr_w)
            return None
        if sname == "Span_Fill" and len(s_args) == 5:
            inner, off, count, val = s_args[1], s_args[2], s_args[3], s_args[4]
            inner_base = self.whnf(_apps(_constant("Span_Base"), elem, inner))
            off_w = self.whnf(off)
            if inner_base.kind != "int" or off_w.kind != "int":
                return None
            f_base = _int_term(
                _INT_SPECS["usize"],
                _wrap_int(_INT_SPECS["usize"], cast("int", inner_base.value) + cast("int", off_w.value)),
            )
            in_ext = self._eval_in_extent(addr, f_base, count)
            if in_ext is True:
                return self.whnf(val)
            if in_ext is False:
                return self._lookup_span_at_addr(elem, inner, addr)
            return None
        if sname == "Span_CopyPrefix" and len(s_args) == 4:
            dst, src, count = s_args[1], s_args[2], s_args[3]
            d_base = self.whnf(_apps(_constant("Span_Base"), elem, dst))
            s_base = self.whnf(_apps(_constant("Span_Base"), elem, src))
            addr_w = self.whnf(addr)
            if d_base.kind != "int" or s_base.kind != "int" or addr_w.kind != "int":
                return None
            in_ext = self._eval_in_extent(addr_w, d_base, count)
            if in_ext is True:
                src_addr = _int_term(
                    _INT_SPECS["usize"],
                    _wrap_int(
                        _INT_SPECS["usize"],
                        cast("int", s_base.value) + (cast("int", addr_w.value) - cast("int", d_base.value)),
                    ),
                )
                return self._lookup_span_at_addr(elem, src, src_addr)
            if in_ext is False:
                return self._lookup_span_at_addr(elem, dst, addr_w)
            return None
        return None

    def _whnf_span_op(self, name: str, arguments: list[_Term]) -> _Term | None:
        if name in {"Span_CanRead", "Span_CanWrite"} and len(arguments) == 2:
            elem, s = arguments
            perm_const = "Span_PermRead" if name == "Span_CanRead" else "Span_PermWrite"
            self.tick(True)
            return self.whnf(
                _apps(
                    _constant("&&"),
                    _apps(_constant("Span_Tag"), elem, s),
                    _apps(_constant(perm_const), elem, s),
                )
            )
        if name in {"Span_Base", "Span_Length", "Span_Tag", "Span_PermRead", "Span_PermWrite"} and len(arguments) == 2:
            elem = arguments[0]
            s = self.whnf(arguments[1])
            s_head, s_args = self.spine(s)
            if s_head.kind != "const" or not isinstance(s_head.value, str):
                return None
            sname = s_head.value
            if sname == "Span_AllocZeroed" and len(s_args) == 3:
                self.tick(True)
                if name == "Span_Base":
                    return self.whnf(s_args[1])
                if name == "Span_Length":
                    return self.whnf(s_args[2])
                return _term("bool", value=1)
            if sname == "Span_ReadOnly" and len(s_args) == 2:
                self.tick(True)
                if name == "Span_PermWrite":
                    return _term("bool", value=0)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Invalidate" and len(s_args) == 2:
                self.tick(True)
                if name in {"Span_Tag", "Span_PermRead", "Span_PermWrite"}:
                    return _term("bool", value=0)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Write" and len(s_args) == 4:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Fill" and len(s_args) == 5:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Slice" and len(s_args) == 4:
                self.tick(True)
                if name == "Span_Base":
                    return self.whnf(
                        _apps(_constant("int_add_usize"), _apps(_constant("Span_Base"), elem, s_args[1]), s_args[2])
                    )
                if name == "Span_Length":
                    return self.whnf(s_args[3])
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_CopyPrefix" and len(s_args) == 4:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Restore" and len(s_args) == 3:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            return None
        if name == "Span_Disjoint" and len(arguments) == 3:
            elem, a, b = arguments
            ba = self.whnf(_apps(_constant("Span_Base"), elem, a))
            if ba.kind != "int":
                return None
            la = self.whnf(_apps(_constant("Span_Length"), elem, a))
            bb = self.whnf(_apps(_constant("Span_Base"), elem, b))
            lb = self.whnf(_apps(_constant("Span_Length"), elem, b))
            if la.kind != "int" or bb.kind != "int" or lb.kind != "int":
                return None
            self.tick(True)
            ba_v = cast("int", ba.value)
            la_v = cast("int", la.value)
            bb_v = cast("int", bb.value)
            lb_v = cast("int", lb.value)
            return _term("bool", value=int(ba_v + la_v <= bb_v or bb_v + lb_v <= ba_v))
        if name == "Span_Read" and len(arguments) == 3:
            elem, s, idx = arguments
            s_w = self.whnf(s)
            if s_w.kind != "app":
                return None
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Span_AllocZeroed") and len(s_args) == 3:
                self.tick(True)
                return _int_term(_INT_SPECS["u8"], 0)
            base_w = self.whnf(_apps(_constant("Span_Base"), elem, s_w))
            idx_w = self.whnf(idx)
            if base_w.kind != "int" or idx_w.kind != "int":
                return None
            addr = _int_term(
                _INT_SPECS["usize"],
                _wrap_int(_INT_SPECS["usize"], cast("int", base_w.value) + cast("int", idx_w.value)),
            )
            found = self._lookup_span_at_addr(elem, s_w, addr)
            if found is not None:
                self.tick(True)
                return found
            return None
        return None

    def _extract_seq_elements(self, seq_term: _Term) -> list[_Term] | None:
        cur = self.whnf(seq_term)
        elems: list[_Term] = []
        while True:
            head, args = self.spine(cur)
            if head == _constant("Seq_Empty") and len(args) == 1:
                return elems
            if head == _constant("Seq_Cons") and len(args) == 3:
                elems.append(args[1])
                cur = self.whnf(args[2])
                continue
            if head == _constant("Seq_Singleton") and len(args) == 2:
                elems.append(args[1])
                return elems
            return None

    def _build_seq_term(self, elem_type: _Term, elems: list[_Term]) -> _Term:
        acc = _app(_constant("Seq_Empty"), elem_type)
        for item in reversed(elems):
            acc = _apps(_constant("Seq_Cons"), elem_type, item, acc)
        return acc

    def _default_term_for_type(self, type_term: _Term) -> _Term:
        t_w = self.whnf(type_term)
        if t_w == _constant("Nat"):
            return _term("nat", value=0)
        if t_w == _constant("bool"):
            return _term("bool", value=0)
        if t_w == _constant("Unit"):
            return _term("unit")
        if t_w.kind == "const" and isinstance(t_w.value, str) and t_w.value in _INT_SPECS:
            return _int_term(_INT_SPECS[t_w.value], 0)
        if t_w.kind == "prod":
            return _term(
                "pair",
                t_w.args[0],
                t_w.args[1],
                self._default_term_for_type(t_w.args[0]),
                self._default_term_for_type(t_w.args[1]),
            )
        head, args = self.spine(t_w)
        if head == _constant("Seq") and len(args) == 1:
            return _app(_constant("Seq_Empty"), args[0])
        if head == _constant("Span") and len(args) == 1:
            z = _int_term(_INT_SPECS["usize"], 0)
            return _apps(_constant("Span_AllocZeroed"), args[0], z, z)
        if head == _constant("Slots") and len(args) == 2:
            z = _int_term(_INT_SPECS["usize"], 0)
            return _apps(_constant("Slots_AllocVacant"), args[0], args[1], z)
        if head.kind == "const" and isinstance(head.value, str) and head.value in self.records_by_type:
            rinfo = self.records_by_type[head.value]
            if not rinfo.fields:
                return _apps(_constant(rinfo.ctor_const), *args, _term("unit"))
            f_vals: list[_Term] = []
            for idx, rf in enumerate(rinfo.fields):
                fty = self._instantiate_record_type(rinfo, args, rf.type)
                for j in range(idx):
                    fty = self.substitute(fty, cast("int", rinfo.fields[j].var.value), f_vals[j])
                f_vals.append(self._default_term_for_type(fty))
            return _apps(_constant(rinfo.ctor_const), *args, *f_vals)
        if head.kind == "const" and isinstance(head.value, str) and head.value in self.unions_by_type:
            uinfo = self.unions_by_type[head.value]
            ctor = uinfo.constructors[0]
            if not ctor.fields:
                return _apps(_constant(ctor.ctor_const), *args, _term("unit"))
            f_vals = []
            for rf in ctor.fields:
                fty = self._instantiate_generic_type(uinfo.generic_vars, args, rf.type)
                f_vals.append(self._default_term_for_type(fty))
            return _apps(_constant(ctor.ctor_const), *args, *f_vals)
        return _term("nat", value=0)

    def _whnf_seq_op(self, name: str, arguments: list[_Term]) -> _Term | None:
        if name == "Seq_Singleton" and len(arguments) == 2:
            elem, val = arguments
            self.tick(True)
            return _apps(_constant("Seq_Cons"), elem, val, _app(_constant("Seq_Empty"), elem))
        if name == "Vec_Model" and len(arguments) == 3:
            elem, _len, vec_term = arguments
            v_w = self.whnf(vec_term)
            v_head, v_args = self.spine(v_w)
            if v_head == _constant("VNil") and len(v_args) in {1, 2}:
                self.tick(True)
                return _app(_constant("Seq_Empty"), elem)
            if v_head == _constant("VCons") and len(v_args) == 4:
                self.tick(True)
                tail_seq = self.whnf(_apps(_constant("Vec_Model"), elem, v_args[1], v_args[3]))
                return _apps(_constant("Seq_Cons"), elem, v_args[2], tail_seq)
            return None
        if name == "Span_Model" and len(arguments) == 2:
            elem, span_term = arguments
            s_w = self.whnf(span_term)
            len_w = self.whnf(_apps(_constant("Span_Length"), elem, s_w))
            if len_w.kind == "int":
                n = cast("int", len_w.value)
                if 0 <= n <= 64:
                    elems: list[_Term] = []
                    for i in range(n):
                        idx_term = _int_term(_INT_SPECS["usize"], i)
                        val_w = self.whnf(_apps(_constant("Span_Read"), elem, s_w, idx_term))
                        elems.append(val_w)
                    self.tick(True)
                    return self._build_seq_term(elem, elems)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Span_Write") and len(s_args) == 4:
                self.tick(True)
                inner_model = self.whnf(_apps(_constant("Span_Model"), elem, s_args[1]))
                idx_nat = self.whnf(_app(_constant("int_to_nat_usize"), s_args[2]))
                return self.whnf(_apps(_constant("Seq_Update"), elem, inner_model, idx_nat, s_args[3]))
            return None
        if name == "Seq_Count" and len(arguments) == 2:
            _elem, seq_term = arguments
            s_w = self.whnf(seq_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None:
                self.tick(True)
                return _term("nat", value=len(elems))
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Seq_Cons") and len(s_args) == 3:
                self.tick(True)
                return self.whnf(_app(_constant("Succ"), _apps(_constant("Seq_Count"), s_args[0], s_args[2])))
            if s_head == _constant("Seq_Update") and len(s_args) == 4:
                self.tick(True)
                return self.whnf(_apps(_constant("Seq_Count"), s_args[0], s_args[1]))
            if s_head == _constant("Seq_Append") and len(s_args) == 3:
                self.tick(True)
                c1 = _apps(_constant("Seq_Count"), s_args[0], s_args[1])
                c2 = _apps(_constant("Seq_Count"), s_args[0], s_args[2])
                return self.whnf(_apps(_constant("+"), c1, c2))
            if s_head == _constant("Vec_Model") and len(s_args) == 3:
                self.tick(True)
                return self.whnf(s_args[1])
            if s_head == _constant("Span_Model") and len(s_args) == 2:
                len_w = self.whnf(_apps(_constant("Span_Length"), s_args[0], s_args[1]))
                if len_w.kind == "int":
                    self.tick(True)
                    return _term("nat", value=max(0, cast("int", len_w.value)))
                self.tick(True)
                return self.whnf(_app(_constant("int_to_nat_usize"), len_w))
            if s_head == _constant("Slots_Model") and len(s_args) == 3:
                live_w = self.whnf(_apps(_constant("Slots_LiveCount"), s_args[0], s_args[1], s_args[2]))
                if live_w.kind == "int":
                    self.tick(True)
                    return _term("nat", value=max(0, cast("int", live_w.value)))
                self.tick(True)
                return self.whnf(_app(_constant("int_to_nat_usize"), live_w))
            if s_head == _constant("PrefixModel") and len(s_args) == 4:
                cnt_w = self.whnf(s_args[3])
                if cnt_w.kind == "int":
                    self.tick(True)
                    return _term("nat", value=max(0, cast("int", cnt_w.value)))
                self.tick(True)
                return self.whnf(_app(_constant("int_to_nat_usize"), cnt_w))
            return None
        if name == "Seq_At" and len(arguments) == 4:
            elem, default_val, seq_term, idx_term = arguments
            s_w = self.whnf(seq_term)
            i_w = self.whnf(idx_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None and i_w.kind == "nat":
                idx_val = cast("int", i_w.value)
                self.tick(True)
                if 0 <= idx_val < len(elems):
                    return self.whnf(elems[idx_val])
                return self.whnf(default_val)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Seq_Update") and len(s_args) == 4:
                upd_idx = self.whnf(s_args[2])
                if self.convertible(upd_idx, i_w):
                    self.tick(True)
                    return self.whnf(s_args[3])
                if upd_idx.kind == "nat" and i_w.kind == "nat" and upd_idx.value != i_w.value:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Seq_At"), elem, default_val, s_args[1], i_w))
            if s_head == _constant("Seq_Append") and len(s_args) == 3:
                r_elems = self._extract_seq_elements(s_args[2])
                if r_elems is not None and len(r_elems) == 1:
                    c_left = self.whnf(_apps(_constant("Seq_Count"), elem, s_args[1]))
                    if self.convertible(i_w, c_left):
                        self.tick(True)
                        return self.whnf(r_elems[0])
            i_head, i_args = self.spine(i_w)
            if s_head == _constant("Span_Model") and len(s_args) == 2:
                if i_w.kind == "nat":
                    idx_u = _int_term(_INT_SPECS["usize"], cast("int", i_w.value))
                    self.tick(True)
                    return self.whnf(_apps(_constant("Span_Read"), s_args[0], s_args[1], idx_u))
                if i_head == _constant("int_to_nat_usize") and len(i_args) == 1:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Span_Read"), s_args[0], s_args[1], i_args[0]))
            if s_head == _constant("Slots_Model") and len(s_args) == 3:
                if i_w.kind == "nat":
                    idx_u = _int_term(_INT_SPECS["usize"], cast("int", i_w.value))
                    self.tick(True)
                    return self.whnf(
                        _apps(_constant("Slots_Read"), s_args[0], s_args[1], default_val, s_args[2], idx_u)
                    )
                if i_head == _constant("int_to_nat_usize") and len(i_args) == 1:
                    self.tick(True)
                    return self.whnf(
                        _apps(_constant("Slots_Read"), s_args[0], s_args[1], default_val, s_args[2], i_args[0])
                    )
            return None
        if name == "Seq_Update" and len(arguments) == 4:
            elem, seq_term, idx_term, val_term = arguments
            s_w = self.whnf(seq_term)
            i_w = self.whnf(idx_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None and i_w.kind == "nat":
                idx_val = cast("int", i_w.value)
                self.tick(True)
                updated = list(elems)
                if 0 <= idx_val < len(updated):
                    updated[idx_val] = val_term
                return self._build_seq_term(elem, updated)
            return None
        if name == "Seq_Append" and len(arguments) == 3:
            elem, left_seq, right_seq = arguments
            l_w = self.whnf(left_seq)
            r_w = self.whnf(right_seq)
            l_elems = self._extract_seq_elements(l_w)
            r_elems = self._extract_seq_elements(r_w)
            if l_elems is not None and r_elems is not None:
                self.tick(True)
                return self._build_seq_term(elem, [*l_elems, *r_elems])
            if l_elems is not None and len(l_elems) == 0:
                self.tick(True)
                return r_w
            if r_elems is not None and len(r_elems) == 0:
                self.tick(True)
                return l_w
            return None
        if name == "Seq_Take" and len(arguments) == 3:
            elem, seq_term, count_term = arguments
            s_w = self.whnf(seq_term)
            c_w = self.whnf(count_term)
            if c_w.kind == "nat" and cast("int", c_w.value) == 0:
                self.tick(True)
                return _app(_constant("Seq_Empty"), elem)
            elems = self._extract_seq_elements(s_w)
            if elems is not None and c_w.kind == "nat":
                cnt = cast("int", c_w.value)
                self.tick(True)
                return self._build_seq_term(elem, elems[: max(0, cnt)])
            cnt_seq = self.whnf(_apps(_constant("Seq_Count"), elem, s_w))
            if self.convertible(cnt_seq, c_w):
                self.tick(True)
                return s_w
            return None
        if name == "Seq_Skip" and len(arguments) == 3:
            elem, seq_term, count_term = arguments
            s_w = self.whnf(seq_term)
            c_w = self.whnf(count_term)
            if c_w.kind == "nat" and cast("int", c_w.value) == 0:
                self.tick(True)
                return s_w
            elems = self._extract_seq_elements(s_w)
            if elems is not None and c_w.kind == "nat":
                cnt = cast("int", c_w.value)
                self.tick(True)
                return self._build_seq_term(elem, elems[max(0, cnt) :])
            return None
        if name == "Seq_Slice" and len(arguments) == 4:
            elem, seq_term, off_term, cnt_term = arguments
            self.tick(True)
            skipped = _apps(_constant("Seq_Skip"), elem, seq_term, off_term)
            return self.whnf(_apps(_constant("Seq_Take"), elem, skipped, cnt_term))
        if name == "Seq_Contains" and len(arguments) == 3:
            _elem, seq_term, val_term = arguments
            s_w = self.whnf(seq_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None:
                if len(elems) == 0:
                    self.tick(True)
                    return _term("bool", value=0)
                all_decided = True
                for item in elems:
                    if self.convertible(item, val_term):
                        self.tick(True)
                        return _term("bool", value=1)
                    item_w = self.whnf(item)
                    val_w = self.whnf(val_term)
                    if item_w.kind != val_w.kind or item_w.kind not in {"nat", "int", "bool"}:
                        all_decided = False
                if all_decided:
                    self.tick(True)
                    return _term("bool", value=0)
            return None
        if name in {"Seq_All", "Seq_Any"} and len(arguments) == 3:
            _elem, seq_term, pred_term = arguments
            s_w = self.whnf(seq_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None:
                is_all = name == "Seq_All"
                if len(elems) == 0:
                    self.tick(True)
                    return _term("bool", value=1 if is_all else 0)
                all_decided = True
                for item in elems:
                    res = self.whnf(_app(pred_term, item))
                    if res.kind == "bool":
                        if is_all and res.value == 0:
                            self.tick(True)
                            return _term("bool", value=0)
                        if not is_all and res.value == 1:
                            self.tick(True)
                            return _term("bool", value=1)
                    else:
                        all_decided = False
                if all_decided:
                    self.tick(True)
                    return _term("bool", value=1 if is_all else 0)
            return None
        return None

    def _whnf_slots_op(self, name: str, arguments: list[_Term]) -> _Term | None:
        if name in {"Slots_CanRead", "Slots_CanWrite"} and len(arguments) == 3:
            elem, cap, s = arguments
            s_w = self.whnf(s)
            head, args = self.spine(s_w)
            if head in {_constant("Slots_Write"), _constant("Slots_TransferSource"), _constant("Slots_TransferDest")} and len(args) >= 3:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, cap, args[2]))
            if head == _constant("Slots_CopyRepresentation") and len(args) == 6:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, args[2], args[4]))
            tag_t = self.whnf(_apps(_constant("Slots_Tag"), elem, cap, s_w))
            perm_const = "Slots_PermRead" if name == "Slots_CanRead" else "Slots_PermWrite"
            perm_t = self.whnf(_apps(_constant(perm_const), elem, cap, s_w))
            if tag_t.kind == "bool" and perm_t.kind == "bool":
                self.tick(True)
                return _term("bool", value=1 if (tag_t.value == 1 and perm_t.value == 1) else 0)
            return None
        if name in {
            "Slots_Base",
            "Slots_LiveCount",
            "Slots_Tag",
            "Slots_PermRead",
            "Slots_PermWrite",
            "Slots_RepModel",
            "Slots_Model",
        } and len(arguments) == 3:
            elem, cap, s = arguments
            s_w = self.whnf(s)
            head, args = self.spine(s_w)
            if head == _constant("Slots_Mk") and len(args) == 9:
                field_map = {
                    "Slots_Base": 2,
                    "Slots_LiveCount": 3,
                    "Slots_Tag": 4,
                    "Slots_PermRead": 5,
                    "Slots_PermWrite": 6,
                    "Slots_RepModel": 7,
                    "Slots_Model": 8,
                }
                self.tick(True)
                return self.whnf(args[field_map[name]])
            if head == _constant("Slots_AllocVacant") and len(args) == 3:
                self.tick(True)
                if name == "Slots_Base":
                    return self.whnf(args[2])
                if name == "Slots_LiveCount":
                    return _int_term(_INT_SPECS["usize"], 0)
                if name in {"Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    return _term("bool", value=1)
                if name in {"Slots_RepModel", "Slots_Model"}:
                    return _app(_constant("Seq_Empty"), elem)
            if head == _constant("Slots_Write") and len(args) == 5:
                inner_s = args[2]
                idx_t = self.whnf(args[3])
                val_t = args[4]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, inner_s))
                inner_live = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap, inner_s))
                if name == "Slots_LiveCount":
                    if idx_t.kind == "int" and inner_live.kind == "int":
                        i_val = cast("int", idx_t.value)
                        l_val = cast("int", inner_live.value)
                        self.tick(True)
                        return _int_term(_INT_SPECS["usize"], max(l_val, i_val + 1))
                    self.tick(True)
                    return self.whnf(
                        _apps(_constant("int_add_usize"), idx_t, _int_term(_INT_SPECS["usize"], 1))
                    )
                if name in {"Slots_RepModel", "Slots_Model"}:
                    inner_model = self.whnf(_apps(_constant(name), elem, cap, inner_s))
                    elems = self._extract_seq_elements(inner_model)
                    if idx_t.kind == "int" and inner_live.kind == "int":
                        i_val = cast("int", idx_t.value)
                        l_val = cast("int", inner_live.value)
                        if elems is not None:
                            if i_val == l_val and i_val == len(elems):
                                self.tick(True)
                                return self._build_seq_term(elem, [*elems, val_t])
                            if 0 <= i_val < len(elems):
                                updated = list(elems)
                                updated[i_val] = val_t
                                self.tick(True)
                                return self._build_seq_term(elem, updated)
                    self.tick(True)
                    return self.whnf(
                        _apps(
                            _constant("Seq_Append"),
                            elem,
                            inner_model,
                            _apps(_constant("Seq_Singleton"), elem, val_t),
                        )
                    )
            if head == _constant("Slots_CopyRepresentation") and len(args) == 6:
                src_cap, _dst_cap, src_s, dst_s, _cnt = args[1], args[2], args[3], args[4], args[5]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, dst_s))
                if name == "Slots_LiveCount":
                    self.tick(True)
                    return _int_term(_INT_SPECS["usize"], 0)
                if name == "Slots_RepModel":
                    self.tick(True)
                    return self.whnf(_apps(_constant("PrefixModel"), elem, src_cap, src_s, _cnt))
                self.tick(True)
                return _app(_constant("Seq_Empty"), elem)
            if head == _constant("Slots_TransferSource") and len(args) == 4:
                inner_s = args[2]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, inner_s))
                if name == "Slots_LiveCount":
                    self.tick(True)
                    return _int_term(_INT_SPECS["usize"], 0)
                if name in {"Slots_RepModel", "Slots_Model"}:
                    self.tick(True)
                    return _app(_constant("Seq_Empty"), elem)
            if head == _constant("Slots_TransferDest") and len(args) == 4:
                inner_s = args[2]
                cnt_t = args[3]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, inner_s))
                if name == "Slots_LiveCount":
                    self.tick(True)
                    return self.whnf(cnt_t)
                if name in {"Slots_RepModel", "Slots_Model"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Slots_RepModel"), elem, cap, inner_s))
            return None
        if name == "PrefixModel" and len(arguments) == 4:
            elem, cap, s, cnt = arguments
            s_w = self.whnf(s)
            cnt_w = self.whnf(cnt)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Slots_TransferDest") and len(s_args) == 4 and self.convertible(s_args[3], cnt_w):
                self.tick(True)
                return self.whnf(_apps(_constant("Slots_Model"), elem, cap, s_w))
            live_w = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap, s_w))
            model_w = self.whnf(_apps(_constant("Slots_Model"), elem, cap, s_w))
            elems = self._extract_seq_elements(model_w)
            if self.convertible(live_w, cnt_w) and elems is not None:
                self.tick(True)
                return model_w
            if elems is not None and cnt_w.kind == "int":
                k = max(0, cast("int", cnt_w.value))
                self.tick(True)
                return self._build_seq_term(elem, elems[:k])
            return None
        if name == "Slots_Read" and len(arguments) == 5:
            elem, cap, default_val, s, idx = arguments
            s_w = self.whnf(s)
            idx_w = self.whnf(idx)
            head, args = self.spine(s_w)
            if head == _constant("Slots_Write") and len(args) == 5:
                w_idx = self.whnf(args[3])
                if self.convertible(w_idx, idx_w):
                    self.tick(True)
                    return self.whnf(args[4])
                if w_idx.kind == "int" and idx_w.kind == "int" and w_idx.value != idx_w.value:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Slots_Read"), elem, cap, default_val, args[2], idx_w))
            if head == _constant("Slots_TransferDest") and len(args) == 4:
                inner_w = self.whnf(args[2])
                i_head, i_args = self.spine(inner_w)
                if i_head == _constant("Slots_CopyRepresentation") and len(i_args) == 6:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Slots_Read"), elem, i_args[1], default_val, i_args[3], idx_w))
            model_w = self.whnf(_apps(_constant("Slots_Model"), elem, cap, s_w))
            elems = self._extract_seq_elements(model_w)
            if elems is not None and idx_w.kind == "int":
                i_val = cast("int", idx_w.value)
                if 0 <= i_val < len(elems):
                    self.tick(True)
                    return self.whnf(elems[i_val])
            return None
        if name == "Slots_LivePrefix" and len(arguments) == 4:
            elem, cap, s, cnt = arguments
            s_w = self.whnf(s)
            cnt_w = self.whnf(cnt)
            cap_w = self.whnf(cap)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Slots_TransferDest") and len(s_args) == 4 and self.convertible(s_args[3], cnt_w):
                self.tick(True)
                return _term("bool", value=1)
            if (
                s_head in {_constant("Slots_TransferSource"), _constant("Slots_AllocVacant")}
                and cnt_w.kind == "int"
                and cast("int", cnt_w.value) == 0
            ):
                self.tick(True)
                return _term("bool", value=1)
            live_w = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap_w, s_w))
            can_read = self.whnf(_apps(_constant("Slots_CanRead"), elem, cap_w, s_w))
            if can_read.kind == "bool" and can_read.value == 0:
                self.tick(True)
                return _term("bool", value=0)
            if self.convertible(live_w, cnt_w):
                if cnt_w.kind == "int" and cap_w.kind in {"int", "nat"}:
                    c_val = cast("int", cnt_w.value)
                    cap_val = cast("int", cap_w.value)
                    if can_read.kind == "bool" and can_read.value == 1:
                        self.tick(True)
                        return _term("bool", value=1 if 0 <= c_val <= cap_val else 0)
            elif live_w.kind == "int" and cnt_w.kind == "int" and live_w.value != cnt_w.value:
                self.tick(True)
                return _term("bool", value=0)
            return None
        if name == "Slots_VacantRange" and len(arguments) == 5:
            elem, cap, s, start, end = arguments
            s_w = self.whnf(s)
            start_w = self.whnf(start)
            end_w = self.whnf(end)
            cap_w = self.whnf(cap)
            cap_u_w = self.whnf(self._slots_cap_usize_term(cap_w))
            s_head, s_args = self.spine(s_w)
            if (
                s_head == _constant("Slots_AllocVacant")
                and len(s_args) == 3
                and start_w.kind == "int"
                and cast("int", start_w.value) == 0
                and (self.convertible(end_w, cap_u_w) or (end_w.kind == "int" and cast("int", end_w.value) == 0))
            ):
                self.tick(True)
                return _term("bool", value=1)
            if (
                s_head == _constant("Slots_TransferSource")
                and len(s_args) == 4
                and start_w.kind == "int"
                and cast("int", start_w.value) == 0
                and (
                    self.convertible(end_w, s_args[3])
                    or self.convertible(end_w, cap_u_w)
                    or (end_w.kind == "int" and cast("int", end_w.value) == 0)
                )
            ):
                self.tick(True)
                return _term("bool", value=1)
            if (
                s_head == _constant("Slots_TransferDest")
                and len(s_args) == 4
                and self.convertible(start_w, s_args[3])
                and (self.convertible(end_w, cap_u_w) or self.convertible(end_w, s_args[3]))
            ):
                self.tick(True)
                return _term("bool", value=1)
            live_w = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap_w, s_w))
            can_write = self.whnf(_apps(_constant("Slots_CanWrite"), elem, cap_w, s_w))
            if can_write.kind == "bool" and can_write.value == 0:
                self.tick(True)
                return _term("bool", value=0)
            if (
                live_w.kind == "int"
                and start_w.kind == "int"
                and end_w.kind == "int"
                and cap_w.kind in {"int", "nat"}
                and can_write.kind == "bool"
                and can_write.value == 1
            ):
                l_val = cast("int", live_w.value)
                st_val = cast("int", start_w.value)
                en_val = cast("int", end_w.value)
                cp_val = cast("int", cap_w.value)
                self.tick(True)
                return _term("bool", value=1 if (l_val <= st_val <= en_val <= cp_val) else 0)
            return None
        if name == "Slots_Disjoint" and len(arguments) == 5:
            elem, cap_a, cap_b, s_a, s_b = arguments
            sa_w = self.whnf(s_a)
            sb_w = self.whnf(s_b)
            ca_w = self.whnf(cap_a)
            cb_w = self.whnf(cap_b)
            ba_w = self.whnf(_apps(_constant("Slots_Base"), elem, ca_w, sa_w))
            bb_w = self.whnf(_apps(_constant("Slots_Base"), elem, cb_w, sb_w))
            if (
                ca_w.kind in {"int", "nat"}
                and cb_w.kind in {"int", "nat"}
                and ba_w.kind == "int"
                and bb_w.kind == "int"
            ):
                ba_val = cast("int", ba_w.value)
                bb_val = cast("int", bb_w.value)
                ca_val = cast("int", ca_w.value)
                cb_val = cast("int", cb_w.value)
                disjoint = (ba_val + ca_val <= bb_val) or (bb_val + cb_val <= ba_val)
                self.tick(True)
                return _term("bool", value=1 if disjoint else 0)
            return None
        if name == "Slots_RepEqual" and len(arguments) == 6:
            elem, cap_a, cap_b, s_a, s_b, cnt = arguments
            sa_w = self.whnf(s_a)
            sb_w = self.whnf(s_b)
            cnt_w = self.whnf(cnt)
            head_a, args_a = self.spine(sa_w)
            if (
                head_a == _constant("Slots_CopyRepresentation")
                and len(args_a) == 6
                and self.convertible(args_a[1], cap_b)
                and self.convertible(args_a[3], sb_w)
                and self.convertible(args_a[5], cnt_w)
            ):
                self.tick(True)
                return _term("bool", value=1)
            rep_a = self.whnf(_apps(_constant("Slots_RepModel"), elem, cap_a, sa_w))
            mod_b = self.whnf(_apps(_constant("Slots_Model"), elem, cap_b, sb_w))
            if self.convertible(rep_a, mod_b):
                self.tick(True)
                return _term("bool", value=1)
            return None
        if name == "Slots_TransferType" and len(arguments) == 6:
            elem, src_cap, dst_cap, src_s, dst_s, cnt = arguments
            self.tick(True)
            src_next = _apps(_constant("Slots_TransferSource"), elem, src_cap, src_s, cnt)
            dst_next = _apps(_constant("Slots_TransferDest"), elem, dst_cap, dst_s, cnt)
            return _term(
                "pair",
                _apps(_constant("Slots"), elem, src_cap),
                _apps(_constant("Slots"), elem, dst_cap),
                src_next,
                dst_next,
            )
        return None

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
        if kind == "int":
            return term.args[0]
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
        if kind == "fix":
            return term.args[0]
        if kind in {"prod", "sum"}:
            return _term("sort", value=max(self.sort(term.args[0]), self.sort(term.args[1]), 0))
        if kind == "sigT":
            return _term("sort", value=max(self.sort(term.args[0]), self.sort(term.args[1].args[1]), 0))
        if kind == "pair":
            return _term("prod", term.args[0], term.args[1])
        if kind == "existT":
            return _term("sigT", term.args[0], term.args[1])
        if kind == "projT1":
            return term.args[0]
        if kind == "projT2":
            p1 = _term("projT1", term.args[0], term.args[1], term.args[2])
            return self.substitute(term.args[1].args[1], cast("int", term.args[1].value), p1)
        if kind == "ex":
            self.sort(term.args[0])
            if self.whnf(self.infer(term.args[1].args[1])) != _PROP:
                raise self.fail("type", "existential quantifier body must be a proposition")
            return _PROP
        if kind == "ex_intro":
            return _term("ex", term.args[0], term.args[1])
        if kind in {"inl", "inr"}:
            return _term("sum", term.args[0], term.args[1])
        if kind == "if":
            return term.args[0]
        if kind in {"bool_match", "unit_match", "pair_match", "sigT_match", "nat_match", "sum_match"}:
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
            if self.whnf(expected) == _NAT and self.whnf(self.infer(value)) == _USIZE:
                value = self.whnf(_app(_constant("int_to_nat_usize"), value))
            self.unify(self.infer(value), expected)
            return value
        if node["kind"] in {"type", "function_type", "group_type", "tuple_type", "computed_type"}:
            if node["kind"] == "type" and self.name(node["name"]) == "_" and not self.nodes(node["arguments"]):
                return self.meta(expected, environment)
            value = self.type(node, environment, require_sort=False)
            if self.whnf(expected) == _NAT and self.whnf(self.infer(value)) == _USIZE:
                value = self.whnf(_app(_constant("int_to_nat_usize"), value))
            self.unify(self.infer(value), expected)
            return value
        if self.whnf(expected) == _NAT and not self._is_unsuffixed_int_expr(node):
            expr_b = self.expression(node, environment)
            if self.whnf(expr_b.type) == _USIZE:
                return self.whnf(_app(_constant("int_to_nat_usize"), expr_b.term))
            self.unify(expr_b.type, expected)
            return expr_b.term
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
            expected_whnf = self.whnf(expected)
            if expected_whnf in {_NAT, _BOOL, _UNIT} or self._int_spec(expected_whnf) is not None:
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
        if term.kind == "fix":
            return term
        if term.kind == "let":
            return _term("let", term.args[0], term.args[1], self.specialize(term.args[2], depth + 1), value=term.value)
        if term.kind == "static":
            value = self.specialize(term.args[1], depth + 1)
            marked = _term("static", term.args[0], value)
            return marked if self.free(value) else self.whnf(marked)
        if term.kind == "const" and term.value in self.definitions:
            if self.definitions[term.value].kind == "fix":
                return term
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
        if term.kind in {"if", "bool_match", "unit_match", "pair_match", "sigT_match", "nat_match", "sum_match", "projT1", "projT2"}:
            reduced = self.whnf(specialized)
            return specialized if reduced == specialized else self.specialize(reduced, depth + 1)
        return specialized

    def apply(self, binding: _Binding, arguments: list[Node], environment: dict[str, _Binding]) -> _Binding:
        call_site = self.site
        term, value_type = binding.term, binding.type
        callee_head, callee_gen_args = self.spine(self.resolve(term))
        is_rec_call = (
            self.current_rec_var is not None
            and callee_head == self.current_rec_var
        )
        specializing = False
        specialized_term = term
        runtime_arguments: list[tuple[_Term, _Term]] = []
        future = self.whnf(value_type)
        protects_runtime = False
        while future.kind == "pi":
            protects_runtime = protects_runtime or cast("int", future.value) in self.constant_parameters
            future = self.whnf(future.args[1])
        if not arguments:
            if is_rec_call:
                raise self.fail("type", f"zero-parameter declaration '{self.current_rec_name}' cannot be structurally recursive")
            value_type = self.whnf(value_type)
            if value_type.kind != "pi" or cast("int", value_type.value) not in self.nullary_parameters:
                raise self.fail("type", "zero-argument call requires a zero-parameter source callable")
            self.unify(value_type.args[0], _UNIT)
            argument = _term("unit")
            res_term = _app(term, argument)
            res_type = self.substitute(value_type.args[1], cast("int", value_type.value), argument)
            if (
                callee_head.kind == "const"
                and isinstance(callee_head.value, str)
                and callee_head.value in self.records_by_ctor
            ):
                rinfo = self.records_by_ctor[callee_head.value]
                self._check_record_invariants(rinfo, callee_gen_args, res_term, environment, call_site)
            return _Binding(res_term, res_type)
        labeled = False
        val_args: list[_Term] = []
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
            arg_val_node = self._unwrap_group(self.node(node["value"]))
            arg_ident_node = (
                self._unwrap_group(self.node(arg_val_node["value"]))
                if (
                    arg_val_node["kind"] == "unary"
                    and isinstance(arg_val_node.get("operator"), dict)
                    and cast("Node", arg_val_node["operator"]).get("text") in {"ref", "in"}
                )
                else arg_val_node
            )
            if arg_ident_node["kind"] == "name":
                arg_vname = self.name(arg_ident_node["name"])
                lifted_set = self.lifted_invariants.get(arg_vname)
                if lifted_set is not None and len(lifted_set) > 0:
                    clause_n = min(lifted_set)
                    raise self.fail(
                        "type",
                        f"cannot pass record '{arg_vname}' to a callable while invariant '{clause_n}' is lifted",
                        node,
                    )
            required_static = cast("int", value_type.value) in self.constant_parameters
            checker = self.static_argument if required_static else self.check
            argument = checker(arg_ident_node if arg_ident_node is not arg_val_node else self.node(node["value"]), value_type.args[0], environment)
            val_args.append(argument)
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
        if (
            callee_head.kind == "const"
            and isinstance(callee_head.value, str)
            and callee_head.value in self.records_by_ctor
        ):
            rinfo = self.records_by_ctor[callee_head.value]
            self._check_record_invariants(rinfo, callee_gen_args, term, environment, call_site)
        if callee_head.kind == "const" and callee_head.value in self.callable_preconditions:
            full_args = callee_gen_args + val_args
            for param_ids, req_term in self.callable_preconditions[callee_head.value]:
                if len(full_args) >= len(param_ids):
                    inst_req = req_term
                    for pid, arg_val in zip(param_ids, full_args, strict=False):
                        inst_req = self.substitute(inst_req, pid, arg_val)
                    self._check_precondition_term(inst_req, environment, call_site)
        if is_rec_call:
            self.current_rec_used = True
            if len(callee_gen_args) != len(self.current_rec_generics):
                raise self.fail("type", "recursive call requires full generic instantiation")
            for g_arg, g_param in zip(callee_gen_args, self.current_rec_generics, strict=True):
                if not self._try_unify(g_arg, g_param):
                    raise self.fail("type", "polymorphic recursion with varying generic arguments is not supported")
            if len(val_args) != len(self.current_rec_params) or not self.current_rec_params:
                raise self.fail("type", f"recursive call to '{self.current_rec_name}' must supply all parameters")
            decreasing_indices = {
                i
                for i, pv in enumerate(self.current_rec_params)
                if (
                    self.resolve(val_args[i]).kind == "var"
                    and cast("int", self.resolve(val_args[i]).value)
                    in self.smaller_vars.get(cast("int", pv.value), set())
                )
            }
            self.current_rec_candidates = [
                (p_idx, p_var_id)
                for p_idx, p_var_id in self.current_rec_candidates
                if p_idx in decreasing_indices
            ]
            if not self.current_rec_candidates:
                raise self.fail(
                    "type",
                    f"recursive call to '{self.current_rec_name}' must pass a structurally smaller pattern binder for its decreasing parameter",
                )
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
            param_type_node = self.node(node["type"])
            is_readonly_span = (
                param_type_node["kind"] == "modified_type"
                and param_type_node.get("modifier") == "in"
            )
            is_ref_param = (
                param_type_node["kind"] == "modified_type"
                and param_type_node.get("modifier") == "ref"
            )
            domain = self.type(param_type_node, extended)
            variable = self.fresh(domain)
            variables.append(variable)
            if is_readonly_span:
                self.readonly_span_vars.add(cast("int", variable.value))
            static = cast("bool", node.get("const", False))
            if static:
                self.constant_parameters.add(cast("int", variable.value))
            if node["name"] is not None:
                name = self.name(node["name"])
                self.parameter_names[cast("int", variable.value)] = name
                if is_ref_param:
                    self.mutable_locals.add(name)
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
                parts = name.split(".")
                if (
                    len(parts) > 1
                    and not arguments
                    and name not in environment
                    and name not in self.globals
                    and (parts[0] in environment or parts[0] in self.globals)
                ):
                    curr = self.lookup(parts[0], environment)
                    curr_head, _ = self.spine(self.whnf(curr.type))
                    if curr_head.kind == "const" and isinstance(curr_head.value, str) and curr_head.value in self.records_by_type:
                        for seg in parts[1:]:
                            curr = self._project_member(curr, seg, node)
                        result = curr.term
                    else:
                        binding = self.lookup(name, environment, raw=True)
                        result = binding.term
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
        elif kind == "modified_type":
            if node.get("lifetime") is not None:
                raise self.fail("unsupported", "explicit loan lifetimes require the full frontend", node)
            modifier = node.get("modifier")
            if modifier not in {"in", "ref"}:
                raise self.fail("unsupported", f"type modifier '{modifier}' requires the full frontend", node)
            inner_type = self.type(self.node(node["type"]), environment, require_sort=require_sort)
            inner_w = self.whnf(inner_type)
            inner_head, inner_args = self.spine(inner_w)
            supported_loan = (
                (inner_head == _constant("Span") and len(inner_args) == 1 and self.whnf(inner_args[0]) == _U8)
                or (inner_head == _constant("Slots") and len(inner_args) == 2)
                or (inner_head == _constant("Vec") and len(inner_args) == 2)
                or (inner_head == _constant("Seq") and len(inner_args) == 1)
                or (inner_head == _constant("TextBuilder") and len(inner_args) == 1)
                or (
                    inner_head.kind == "const"
                    and isinstance(inner_head.value, str)
                    and inner_head.value in self.records_by_type
                )
            )
            if not supported_loan:
                raise self.fail(
                    "unsupported",
                    f"modifier '{modifier}' is only supported on Span<byte>, Slots<T, capacity>, Vec<T, n>, Seq<T>, TextBuilder<capacity> or record types in the first-slice carrier",
                    node,
                )
            result = inner_type
        else:
            raise self.fail("unsupported", f"'{kind}' is not a supported mathematical type")
        if require_sort:
            self.sort(result)
        return result

    def check(self, node: Node, expected: _Term, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "expression_body":
            return self.check(self.node(node["value"]), expected, environment)
        if node["kind"] == "group":
            return self.check(self.node(node["value"]), expected, environment)
        if node["kind"] not in {"lambda", "typed_lambda", "block"} and (
            self._is_propagatable_union(expected)
            or (self.current_return_type is not None and expected == self.current_return_type)
        ):
            split_prop = self._split_first_propagate(node)
            if split_prop is not None:
                prop_node, rebuild = split_prop
                return self._elaborate_propagate(
                    prop_node,
                    environment,
                    expected,
                    lambda temp_name, _ok_b, ok_env: self.check(
                        rebuild(
                            {
                                "kind": "name",
                                "span": prop_node["span"],
                                "name": {"text": temp_name, "span": prop_node["span"]},
                            }
                        ),
                        expected,
                        ok_env,
                    ),
                )
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
        if node["kind"] == "nat" and node["suffix"] == "":
            spec = self._int_spec(expected)
            if spec is not None:
                mag = _parse_numeric_magnitude(cast("str", node["value"]))
                if not spec.min_val <= mag <= spec.max_val:
                    raise self.fail(
                        "type",
                        f"integer literal {mag} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                        node,
                    )
                return _int_term(spec, mag)
        if node["kind"] == "unary" and self._int_spec(expected) is not None:
            res_u = self._elaborate_unary(node, environment, expected_int=expected)
            self.site = node
            self.unify(res_u.type, expected)
            return res_u.term
        if node["kind"] == "binary" and self._int_spec(expected) is not None:
            res_b = self._elaborate_binary(node, environment, expected_int=expected)
            self.site = node
            self.unify(res_b.type, expected)
            return res_b.term
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
            amount = _parse_numeric_magnitude(cast("str", node["value"]))
            suffix = cast("str", node["suffix"])
            if suffix or amount > MAX_PATTERN_NAT:
                return _Pat("int_lit", node, value=f"{amount}:{suffix}")
            result = _Pat("zero", node, value=f"{amount}:")
            for _ in range(amount):
                result = _Pat("succ", node, value=f"{amount}:", args=(result,))
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
            if cname in self.union_ctors:
                _, ctor_info = self.union_ctors[cname]
                if len(arguments) != len(ctor_info.fields):
                    raise self.fail(
                        "type",
                        f"constructor '{cname}' expects {len(ctor_info.fields)} pattern arguments, got {len(arguments)}",
                        node,
                    )
                labeled = False
                sub_patterns = []
                for idx, arg_node in enumerate(arguments):
                    expected_field = ctor_info.fields[idx]
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
                return _Pat("union", node, value=cname, args=tuple(sub_patterns))
            if cname not in self.globals:
                raise self.fail("name", f"unknown constructor '{cname}'", node)
            if cname in {"VNil", "VCons", "FZero", "FSucc"}:
                raise self.fail("unsupported", f"indexed elimination over '{cname}' requires the full frontend", node)
            raise self.fail("type", f"'{cname}' is not a pattern constructor", node)
        raise self.fail("protocol", f"unexpected pattern node '{kind}'", node)

    def _instantiate_generic_type(
        self, generic_vars: tuple[_Term, ...], type_args: list[_Term], target_type: _Term
    ) -> _Term:
        result = target_type
        for gv, arg in zip(generic_vars, type_args, strict=True):
            result = self.substitute(result, cast("int", gv.value), arg)
        return result

    def _instantiate_record_type(
        self, record_info: _RecordInfo, type_args: list[_Term], target_type: _Term
    ) -> _Term:
        return self._instantiate_generic_type(record_info.generic_vars, type_args, target_type)

    def _instantiate_record_field_type(
        self, record_info: _RecordInfo, type_args: list[_Term], field_idx: int, receiver_term: _Term
    ) -> _Term:
        ftype = self._instantiate_record_type(record_info, type_args, record_info.fields[field_idx].type)
        for j in range(field_idx):
            earlier_rf = record_info.fields[j]
            proj_term = _apps(_constant(earlier_rf.proj_const), *type_args, receiver_term)
            ftype = self.substitute(ftype, cast("int", earlier_rf.var.value), proj_term)
        return ftype

    def _expand_union_ctor(self, term: _Term) -> _Term:
        head, args = self.spine(term)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.unions_by_ctor:
            return term
        union_info, ctor_info = self.unions_by_ctor[head.value]
        expected_val_arity = len(ctor_info.fields) if ctor_info.fields else 1
        if len(args) != len(union_info.generic_vars) + expected_val_arity:
            return term
        type_args = args[:len(union_info.generic_vars)]
        field_vals = args[len(union_info.generic_vars):]
        field_types = [
            self._instantiate_generic_type(union_info.generic_vars, type_args, rf.type)
            for rf in ctor_info.fields
        ]
        if not ctor_info.fields:
            payload_val = _term("unit")
        elif len(ctor_info.fields) == 1:
            if len(union_info.constructors) == 1:
                payload_val = _term("pair", field_types[0], _UNIT, field_vals[0], _term("unit"))
            else:
                payload_val = field_vals[0]
        elif ctor_info.is_dependent:
            payload_val = field_vals[-1]
            for k in range(len(field_vals) - 2, -1, -1):
                fv = field_vals[k]
                fvar_id = cast("int", ctor_info.fields[k].var.value)
                ftype = field_types[k]
                tail_type = self._instantiate_generic_type(
                    union_info.generic_vars, type_args, ctor_info.tail_sig_types[k + 1]
                )
                for j in range(k):
                    earlier_id = cast("int", ctor_info.fields[j].var.value)
                    ftype = self.substitute(ftype, earlier_id, field_vals[j])
                    tail_type = self.substitute(tail_type, earlier_id, field_vals[j])
                fam_lam = _term("lam", ftype, tail_type, value=fvar_id)
                payload_val = _term("existT", ftype, fam_lam, fv, payload_val)
        else:
            payload_val = field_vals[-1]
            acc_type = field_types[-1]
            for fv, ft in reversed(list(zip(field_vals[:-1], field_types[:-1], strict=True))):
                payload_val = _term("pair", ft, acc_type, fv, payload_val)
                acc_type = _term("prod", ft, acc_type)
        if len(union_info.constructors) == 1:
            return payload_val
        inst_payload_types = [
            self._instantiate_generic_type(union_info.generic_vars, type_args, c.payload_type)
            for c in union_info.constructors
        ]
        inst_suffix_types = [
            self._instantiate_generic_type(union_info.generic_vars, type_args, st)
            for st in union_info.suffix_types
        ]
        idx = ctor_info.index
        if idx < len(union_info.constructors) - 1:
            result = _term("inl", inst_payload_types[idx], inst_suffix_types[idx + 1], payload_val)
        else:
            result = payload_val
        for j in range(idx - 1, -1, -1):
            result = _term("inr", inst_payload_types[j], inst_suffix_types[j + 1], result)
        return result

    def _typecheck_pattern(
        self,
        pat: _Pat,
        expected_type: _Term,
        environment: dict[str, _Binding],
        pattern_bindings: dict[str, _Binding] | None = None,
        *,
        smaller_roots: frozenset[int] = frozenset(),
        destruct_roots: frozenset[int] = frozenset(),
    ) -> _Term:
        self.tick()
        self.site = pat.node
        bound_var: _Term | None = None
        if pattern_bindings is not None:
            for name in pat.names:
                fresh_v = self.fresh(expected_type)
                for r_id in smaller_roots:
                    if r_id in self.smaller_vars:
                        self.smaller_vars[r_id].add(cast("int", fresh_v.value))
                pattern_bindings[name] = _Binding(fresh_v, expected_type)
                if bound_var is None:
                    bound_var = fresh_v
        if pat.kind == "wild":
            if bound_var is not None:
                return bound_var
            fresh_w = self.fresh(expected_type)
            for r_id in smaller_roots:
                if r_id in self.smaller_vars:
                    self.smaller_vars[r_id].add(cast("int", fresh_w.value))
            return fresh_w
        if pat.kind == "unit":
            self.unify(expected_type, _UNIT)
            return _term("unit")
        if pat.kind == "bool":
            self.unify(expected_type, _BOOL)
            return _term("bool", value=1 if pat.value else 0)
        spec = self._int_spec(expected_type)
        if spec is not None and pat.kind in {"zero", "succ", "int_lit"}:
            if pat.node["kind"] != "nat_pattern":
                raise self.fail("type", "constructor 'Succ' requires a Nat scrutinee", pat.node)
            amount = _parse_numeric_magnitude(cast("str", pat.node["value"]))
            suffix = cast("str", pat.node["suffix"])
            if suffix:
                canonical = "u8" if suffix == "byte" else _NUMERICS_ALIASES.get(suffix, suffix)
                if canonical != spec.name:
                    raise self.fail(
                        "type",
                        f"integer pattern suffix '{suffix}' does not match scrutinee type '{spec.name}'",
                        pat.node,
                    )
            if not spec.min_val <= amount <= spec.max_val:
                raise self.fail(
                    "type",
                    f"integer pattern {amount} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                    pat.node,
                )
            return _int_term(spec, amount)
        if pat.kind == "int_lit":
            self.unify(expected_type, _NAT)
            _, suffix = cast("str", pat.value).split(":", 1)
            if suffix:
                raise self.fail(
                    "type",
                    f"integer pattern with suffix '{suffix}' requires type '{suffix}', not Nat",
                    pat.node,
                )
            raise self.fail(
                "limit",
                f"natural pattern literal exceeds structural bound ({MAX_PATTERN_NAT})",
                pat.node,
            )
        if pat.kind in {"zero", "succ"}:
            self.unify(expected_type, _NAT)
            if pat.kind == "zero":
                return _term("nat", value=0)
            pred_term = self._typecheck_pattern(
                pat.args[0],
                _NAT,
                environment,
                pattern_bindings,
                smaller_roots=smaller_roots | destruct_roots,
                destruct_roots=destruct_roots,
            )
            return _app(_constant("Succ"), pred_term)
        if pat.kind == "record":
            record_info = self.records[cast("str", pat.value)]
            type_args = [self.meta(self.types[cast("int", gv.value)], environment) for gv in record_info.generic_vars]
            expected_rec_type = _apps(_constant(record_info.type_const), *type_args)
            self.unify(expected_type, expected_rec_type)
            sub_terms: list[_Term] = []
            for idx, (sub_pat, rf) in enumerate(zip(pat.args, record_info.fields, strict=True)):
                ftype = self._instantiate_record_type(record_info, type_args, rf.type)
                for j in range(idx):
                    ftype = self.substitute(ftype, cast("int", record_info.fields[j].var.value), sub_terms[j])
                sub_terms.append(
                    self._typecheck_pattern(sub_pat, ftype, environment, pattern_bindings)
                )
            if not sub_terms:
                return _apps(_constant(record_info.ctor_const), *type_args, _term("unit"))
            return _apps(_constant(record_info.ctor_const), *type_args, *sub_terms)
        if pat.kind == "union":
            union_info, ctor_info = self.union_ctors[cast("str", pat.value)]
            type_args = [self.meta(self.types[cast("int", gv.value)], environment) for gv in union_info.generic_vars]
            expected_union_type = _apps(_constant(union_info.type_const), *type_args)
            self.unify(expected_type, expected_union_type)
            sub_terms = []
            for idx, (sub_pat, rf) in enumerate(zip(pat.args, ctor_info.fields, strict=True)):
                ftype = self._instantiate_generic_type(union_info.generic_vars, type_args, rf.type)
                for j in range(idx):
                    ftype = self.substitute(ftype, cast("int", ctor_info.fields[j].var.value), sub_terms[j])
                sub_terms.append(
                    self._typecheck_pattern(sub_pat, ftype, environment, pattern_bindings)
                )
            if not sub_terms:
                return _apps(_constant(ctor_info.ctor_const), *type_args, _term("unit"))
            return _apps(_constant(ctor_info.ctor_const), *type_args, *sub_terms)
        if pat.kind == "pair":
            resolved = self.whnf(expected_type)
            if resolved.kind == "meta":
                left_type = self.meta(_SORT, environment)
                right_type = self.meta(_SORT, environment)
                self.unify(resolved, _term("prod", left_type, right_type))
                resolved = self.whnf(expected_type)
            if resolved.kind != "prod":
                raise self.fail("type", "tuple pattern requires a product scrutinee", pat.node)
            left_t = self._typecheck_pattern(pat.args[0], resolved.args[0], environment, pattern_bindings)
            right_t = self._typecheck_pattern(pat.args[1], resolved.args[1], environment, pattern_bindings)
            return _term("pair", resolved.args[0], resolved.args[1], left_t, right_t)
        raise self.fail("protocol", f"unexpected internal pattern '{pat.kind}'", pat.node)

    def _require_irrefutable(self, pat: _Pat) -> None:
        if pat.kind in {"bool", "zero", "succ", "int_lit", "union"}:
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
            for idx, (sub_pat, rf) in enumerate(zip(pat.args, record_info.fields, strict=True)):
                ftype = self._instantiate_record_field_type(record_info, type_args, idx, current.term)
                fterm = _apps(_constant(rf.proj_const), *type_args, current.term)
                self._bind_irrefutable(sub_pat, _Binding(fterm, ftype), extended)
        elif pat.kind == "pair":
            prod_type = self.whnf(current.type)
            left_type, right_type = prod_type.args
            left_term = _apps(_constant("Fst"), left_type, right_type, current.term)
            right_term = _apps(_constant("Snd"), left_type, right_type, current.term)
            self._bind_irrefutable(pat.args[0], _Binding(left_term, left_type), extended)
            self._bind_irrefutable(pat.args[1], _Binding(right_term, right_type), extended)

    def _collect_pat_names(self, pat: _Pat, out: set[str]) -> None:
        for name in pat.names:
            out.add(name)
        for child in pat.args:
            self._collect_pat_names(child, out)

    def local(self, node: Node, environment: dict[str, _Binding]) -> dict[str, _Binding]:
        self.site = node
        if node["kind"] in {"let_pattern", "var_pattern"}:
            binding = self.expression(self.node(node["value"]), environment)
            pat = self._parse_pattern(self.node(node["pattern"]), set())
            self._require_irrefutable(pat)
            self._typecheck_pattern(pat, binding.type, environment)
            extended = dict(environment)
            self._bind_irrefutable(pat, binding, extended)
            bound_names: set[str] = set()
            self._collect_pat_names(pat, bound_names)
            for bname in bound_names:
                if bname in self.frozen_collections:
                    raise self.fail("type", f"cannot rebind collection '{bname}' while iterating over it", node)
                if node["kind"] == "var_pattern":
                    self.mutable_locals.add(bname)
                else:
                    self.mutable_locals.discard(bname)
            return extended
        if node["kind"] == "constant_local":
            binding = self.constant_value(node, environment)
        elif node["kind"] not in {"let", "typed_local", "var"}:
            raise self.fail("unsupported", "only local let/var name bindings are supported")
        else:
            self.no_roles(node, "grade")
            if node["type"] is None:
                binding = self.expression(self.node(node["value"]), environment)
            else:
                value_type = self.type(self.node(node["type"]), environment)
                binding = _Binding(self.check(self.node(node["value"]), value_type, environment), value_type)
        extended = dict(environment)
        bname = self.name(node["name"])
        if bname in self.frozen_collections:
            raise self.fail("type", f"cannot rebind collection '{bname}' while iterating over it", node)
        if node["kind"] == "var":
            self.mutable_locals.add(bname)
        else:
            self.mutable_locals.discard(bname)
        self.bind_local(extended, bname, binding)
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
        if expected is not None and self._is_prop_type(expected):
            refine_scrutinee = True
        scrut_smaller_roots: frozenset[int] = frozenset[int]()
        scrut_destruct_roots: frozenset[int] = frozenset[int]()
        if scrutinee.term.kind == "var":
            scrut_var_id_0 = cast("int", scrutinee.term.value)
            scrut_smaller_roots = frozenset(
                [r_id for r_id, s_set in self.smaller_vars.items() if scrut_var_id_0 in s_set]
            )
            scrut_destruct_roots = frozenset(
                [
                    r_id
                    for r_id, s_set in self.smaller_vars.items()
                    if scrut_var_id_0 == r_id or scrut_var_id_0 in s_set
                ]
            )
        cases = self.nodes(node["cases"])
        rows: list[_Row] = []
        arm_pattern_bindings: list[dict[str, _Binding]] = []
        for arm_index, arm in enumerate(cases):
            self.node(arm, "expression_case" if expression_arms else "case")
            pat = self._parse_pattern(self.node(arm["pattern"]), set())
            bindings_for_arm: dict[str, _Binding] = {}
            self._typecheck_pattern(
                pat,
                scrutinee.type,
                environment,
                bindings_for_arm,
                smaller_roots=scrut_smaller_roots,
                destruct_roots=scrut_destruct_roots,
            )
            arm_pattern_bindings.append(bindings_for_arm)
            rows.append(_Row((pat,), (), arm, arm_index))
        scrutinee_type = self.whnf(scrutinee.type)
        scrutinee_head, _ = self.spine(scrutinee_type)
        if (scrutinee_type not in {_UNIT, _BOOL, _NAT}
                and self._int_spec(scrutinee_type) is None
                and scrutinee_type.kind != "prod"
                and not (
                    scrutinee_head.kind == "const"
                    and (scrutinee_head.value in self.records_by_type or scrutinee_head.value in self.unions_by_type)
                )):
            raise self.fail(
                "type",
                "match scrutinee must have type Nat, bool, Unit, a fixed-width integer, a product, a record or a union",
                value_node,
            )
        inferred_result: list[_Term | None] = [expected]
        local_visited: set[int] = set()

        def subst_cols(
            cols: list[tuple[_Term, _Term, _Term]], var_id: int, replacement: _Term
        ) -> list[tuple[_Term, _Term, _Term]]:
            return [(cv, cs, self.substitute(ct, var_id, replacement)) for cv, cs, ct in cols]

        def specialize_rows(active_rows: list[_Row], index: int, ctor_kind: str, ctor_term: _Term,
                            col_var_id: int, col_type: _Term, sub_count: int, *,
                            bool_value: bool = False, ctor_name: str = "") -> list[_Row]:
            specialized: list[_Row] = []
            for row in active_rows:
                pat = row.patterns[index]
                updated_bindings = tuple(
                    (
                        bname,
                        _Binding(
                            self.substitute(bval.term, col_var_id, ctor_term),
                            self.substitute(bval.type, col_var_id, ctor_term),
                        ),
                    )
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
                elif (
                    pat.kind == ctor_kind
                    and (ctor_kind != "bool" or pat.value == bool_value)
                    and (ctor_kind != "union" or pat.value == ctor_name)
                ):
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
                arm_facts = facts
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
                    if scrutinee.term.kind == "var":
                        scrut_id = cast("int", scrutinee.term.value)
                        arm_facts = tuple(
                            _Binding(
                                f.term,
                                self.substitute(f.type, scrut_id, leaf_pattern),
                                f.generics,
                                f.constant,
                            )
                            for f in facts
                        )
                for name, bound in first.bindings:
                    bound_term = bound.term
                    bound_type = bound.type
                    for col_var, col_scrutinee, _ in columns:
                        if col_var != col_scrutinee:
                            bound_term = self.substitute(bound_term, cast("int", col_var.value), col_scrutinee)
                            bound_type = self.substitute(bound_type, cast("int", col_var.value), col_scrutinee)
                    self.bind_local(arm_env, name, _Binding(bound_term, bound_type))
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
                evaluated = self.block(block_node, arm_env, leaf_expected, facts=arm_facts)
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
                    subst_cols(without_index, col_var_id, unit_term),
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
                self.active_facts.append(col_scrutinee)
                try:
                    yes = compile_matrix(
                        subst_cols(without_index, col_var_id, true_term),
                        specialize_rows(active_rows, index, "bool", true_term, col_var_id, _BOOL, 0, bool_value=True),
                        self.substitute(pattern_term, col_var_id, true_term),
                    )
                finally:
                    self.active_facts.pop()
                self.active_facts.append(_app(_constant("!"), col_scrutinee))
                try:
                    no = compile_matrix(
                        subst_cols(without_index, col_var_id, false_term),
                        specialize_rows(active_rows, index, "bool", false_term, col_var_id, _BOOL, 0, bool_value=False),
                        self.substitute(pattern_term, col_var_id, false_term),
                    )
                finally:
                    self.active_facts.pop()
                if motive_body is None:
                    return _term("if", cast("_Term", inferred_result[0]), col_scrutinee, yes, no)
                motive_lam = _term("lam", _BOOL, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id)
                return _term("bool_match", motive_lam, col_scrutinee, yes, no)

            col_int_spec = self._int_spec(col_type)
            if col_int_spec is not None:
                target_pat = first.patterns[index]
                target_val = _parse_numeric_magnitude(cast("str", target_pat.node["value"]))
                lit_term = _int_term(col_int_spec, target_val)
                yes_rows: list[_Row] = []
                no_rows: list[_Row] = []
                for row in active_rows:
                    pat = row.patterns[index]
                    updated_bindings = tuple(
                        (
                            bname,
                            _Binding(
                                self.substitute(bval.term, col_var_id, lit_term),
                                self.substitute(bval.type, col_var_id, lit_term),
                            ),
                        )
                        for bname, bval in row.bindings
                    )
                    if pat.kind == "wild":
                        extra = tuple((name, _Binding(lit_term, col_type)) for name in pat.names)
                        yes_rows.append(
                            _Row(
                                row.patterns[:index] + row.patterns[index + 1:],
                                updated_bindings + extra,
                                row.arm,
                                row.arm_index,
                            )
                        )
                        no_rows.append(row)
                    else:
                        row_val = _parse_numeric_magnitude(cast("str", pat.node["value"]))
                        if row_val == target_val:
                            yes_rows.append(
                                _Row(
                                    row.patterns[:index] + row.patterns[index + 1:],
                                    updated_bindings,
                                    row.arm,
                                    row.arm_index,
                                )
                            )
                        else:
                            no_rows.append(row)
                eq_cond = _apps(_constant(f"int_eq_{col_int_spec.name}"), col_scrutinee, lit_term)
                ne_cond = _apps(_constant(f"int_ne_{col_int_spec.name}"), col_scrutinee, lit_term)
                self.active_facts.append(eq_cond)
                try:
                    yes_branch = compile_matrix(
                        subst_cols(without_index, col_var_id, lit_term),
                        yes_rows,
                        self.substitute(pattern_term, col_var_id, lit_term),
                    )
                finally:
                    self.active_facts.pop()
                self.active_facts.append(ne_cond)
                try:
                    no_branch = compile_matrix(columns, no_rows, pattern_term)
                finally:
                    self.active_facts.pop()
                ret_ty = (
                    self.substitute(motive_body, root_var_id, pattern_term)
                    if motive_body is not None
                    else cast("_Term", inferred_result[0])
                )
                return _term("if", ret_ty, eq_cond, yes_branch, no_branch)

            if col_type.kind == "prod":
                left_type, right_type = col_type.args
                left_var = self.fresh(left_type)
                right_var = self.fresh(right_type)
                pair_term = _term("pair", left_type, right_type, left_var, right_var)
                sub_columns = [(left_var, left_var, left_type), (right_var, right_var, right_type)]
                body = compile_matrix(
                    subst_cols(columns[:index], col_var_id, pair_term)
                    + sub_columns
                    + subst_cols(columns[index + 1:], col_var_id, pair_term),
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
                if not record_info.fields:
                    ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, _term("unit"))
                    body = compile_matrix(
                        subst_cols(without_index, col_var_id, ctor_term),
                        specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, 0),
                        self.substitute(pattern_term, col_var_id, ctor_term),
                    )
                    if motive_body is None:
                        return body
                    motive_lam = _term(
                        "lam", col_type, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id
                    )
                    return _term("unit_match", motive_lam, col_scrutinee, body)
                if len(record_info.fields) == 1:
                    ft_0 = self._instantiate_record_type(record_info, col_type_args, record_info.fields[0].type)
                    fvar_0 = self.fresh(ft_0)
                    dummy_unit_var = self.fresh(_UNIT)
                    ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, fvar_0)
                    sub_columns = [(fvar_0, fvar_0, ft_0)]
                    body = compile_matrix(
                        subst_cols(columns[:index], col_var_id, ctor_term)
                        + sub_columns
                        + subst_cols(columns[index + 1:], col_var_id, ctor_term),
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
                        ft_0,
                        _term("lam", _UNIT, body, value=dummy_unit_var.value),
                        value=fvar_0.value,
                    )
                    return _term("pair_match", motive_lam, col_scrutinee, branch_lam)
                field_types: list[_Term] = []
                field_vars: list[_Term] = []
                for idx_f, rf in enumerate(record_info.fields):
                    ft = self._instantiate_record_type(record_info, col_type_args, rf.type)
                    for j in range(idx_f):
                        ft = self.substitute(ft, cast("int", record_info.fields[j].var.value), field_vars[j])
                    fv = self.fresh(ft)
                    field_types.append(ft)
                    field_vars.append(fv)
                ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, *field_vars)
                sub_columns = [(fv, fv, ft) for fv, ft in zip(field_vars, field_types, strict=True)]
                body = compile_matrix(
                    subst_cols(columns[:index], col_var_id, ctor_term)
                    + sub_columns
                    + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                    specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, len(field_vars)),
                    self.substitute(pattern_term, col_var_id, ctor_term),
                )
                if record_info.is_dependent:
                    tail_types: list[_Term] = []
                    for k in range(len(field_types) - 1):
                        tt = self._instantiate_record_type(
                            record_info, col_type_args, record_info.tail_sig_types[k + 1]
                        )
                        for j in range(k + 1):
                            tt = self.substitute(tt, cast("int", record_info.fields[j].var.value), field_vars[j])
                        tail_types.append(tt)
                else:
                    tail_types = [field_types[-1]]
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
                    if record_info.is_dependent and cast("int", left_var.value) in self.free(motive_return):
                        fam_lam = _term("lam", left_type, right_type, value=left_var.value)
                        proj1_var = _term("projT1", left_type, fam_lam, _term("var", value=scrut_var_id))
                        motive_return = self.substitute(motive_return, cast("int", left_var.value), proj1_var)
                        if motive_body is None and inferred_result[0] is not None:
                            inferred_result[0] = self.substitute(motive_return, scrut_var_id, scrut)
                    motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                    branch_lam = _term(
                        "lam",
                        left_type,
                        _term("lam", right_type, curr_body, value=right_var.value),
                        value=left_var.value,
                    )
                    match_kind = "sigT_match" if record_info.is_dependent else "pair_match"
                    curr_body = _term(match_kind, motive_lam, scrut, branch_lam)
                return curr_body

            if col_head.kind == "const" and isinstance(col_head.value, str) and col_head.value in self.unions_by_type:
                union_info = self.unions_by_type[col_head.value]
                if len(union_info.constructors) == 1:
                    ctor_info = union_info.constructors[0]
                    if not ctor_info.fields:
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, _term("unit"))
                        body = compile_matrix(
                            subst_cols(without_index, col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 0, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if motive_body is None:
                            return body
                        motive_lam = _term(
                            "lam", col_type, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id
                        )
                        return _term("unit_match", motive_lam, col_scrutinee, body)
                    if len(ctor_info.fields) == 1:
                        ft_0 = self._instantiate_generic_type(
                            union_info.generic_vars, col_type_args, ctor_info.fields[0].type
                        )
                        fvar_0 = self.fresh(ft_0)
                        dummy_unit_var = self.fresh(_UNIT)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, fvar_0)
                        sub_columns = [(fvar_0, fvar_0, ft_0)]
                        body = compile_matrix(
                            subst_cols(columns[:index], col_var_id, ctor_term)
                            + sub_columns
                            + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 1, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if motive_body is not None:
                            unit_motive_ret = self.substitute(
                                motive_body,
                                root_var_id,
                                self.substitute(
                                    pattern_term,
                                    col_var_id,
                                    _term("pair", ft_0, _UNIT, fvar_0, dummy_unit_var),
                                ),
                            )
                            body = _term(
                                "unit_match",
                                _term("lam", _UNIT, unit_motive_ret, value=dummy_unit_var.value),
                                dummy_unit_var,
                                body,
                            )
                        motive_return = (
                            self.substitute(motive_body, root_var_id, pattern_term)
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                        motive_lam = _term("lam", col_type, motive_return, value=col_var_id)
                        branch_lam = _term(
                            "lam",
                            ft_0,
                            _term("lam", _UNIT, body, value=dummy_unit_var.value),
                            value=fvar_0.value,
                        )
                        return _term("pair_match", motive_lam, col_scrutinee, branch_lam)
                    field_types = []
                    field_vars = []
                    for idx_f, rf in enumerate(ctor_info.fields):
                        ft = self._instantiate_generic_type(union_info.generic_vars, col_type_args, rf.type)
                        for j in range(idx_f):
                            ft = self.substitute(ft, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                        fv = self.fresh(ft)
                        field_types.append(ft)
                        field_vars.append(fv)
                    ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, *field_vars)
                    sub_columns = [(fv, fv, ft) for fv, ft in zip(field_vars, field_types, strict=True)]
                    body = compile_matrix(
                        subst_cols(columns[:index], col_var_id, ctor_term)
                        + sub_columns
                        + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                        specialize_rows(
                            active_rows,
                            index,
                            "union",
                            ctor_term,
                            col_var_id,
                            col_type,
                            len(field_vars),
                            ctor_name=ctor_info.name,
                        ),
                        self.substitute(pattern_term, col_var_id, ctor_term),
                    )
                    if ctor_info.is_dependent:
                        tail_types = []
                        for k in range(len(field_types) - 1):
                            tt = self._instantiate_generic_type(
                                union_info.generic_vars, col_type_args, ctor_info.tail_sig_types[k + 1]
                            )
                            for j in range(k + 1):
                                tt = self.substitute(tt, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                            tail_types.append(tt)
                    else:
                        tail_types = [field_types[-1]]
                        for ft in reversed(field_types[1:-1]):
                            tail_types.append(_term("prod", ft, tail_types[-1]))
                        tail_types.reverse()
                    tail_vars = [
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
                            if motive_body is not None and not ctor_info.is_dependent:
                                partial = scrut
                                p_type = scrut_type
                                for j in range(k - 1, -1, -1):
                                    partial = _term("pair", field_types[j], p_type, field_vars[j], partial)
                                    p_type = _term("prod", field_types[j], p_type)
                                motive_return = self.substitute(
                                    motive_body,
                                    root_var_id,
                                    self.substitute(pattern_term, col_var_id, partial),
                                )
                            else:
                                motive_return = cast("_Term", inferred_result[0])
                        if ctor_info.is_dependent and cast("int", left_var.value) in self.free(motive_return):
                            fam_lam = _term("lam", left_type, right_type, value=left_var.value)
                            proj1_var = _term("projT1", left_type, fam_lam, _term("var", value=scrut_var_id))
                            motive_return = self.substitute(motive_return, cast("int", left_var.value), proj1_var)
                            if motive_body is None and inferred_result[0] is not None:
                                inferred_result[0] = self.substitute(motive_return, scrut_var_id, scrut)
                        motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                        branch_lam = _term(
                            "lam",
                            left_type,
                            _term("lam", right_type, curr_body, value=right_var.value),
                            value=left_var.value,
                        )
                        match_kind = "sigT_match" if ctor_info.is_dependent else "pair_match"
                        curr_body = _term(match_kind, motive_lam, scrut, branch_lam)
                    return curr_body

                inst_payload_types = [
                    self._instantiate_generic_type(union_info.generic_vars, col_type_args, c.payload_type)
                    for c in union_info.constructors
                ]
                inst_suffix_types = [
                    self._instantiate_generic_type(union_info.generic_vars, col_type_args, st)
                    for st in union_info.suffix_types
                ]
                num_ctors = len(union_info.constructors)

                def suffix_inj(from_idx: int, inner_term: _Term) -> _Term:
                    acc = inner_term
                    for j in range(from_idx - 1, -1, -1):
                        acc = _term("inr", inst_payload_types[j], inst_suffix_types[j + 1], acc)
                    return acc

                def ctor_inj(ctor_idx: int, payload_term: _Term) -> _Term:
                    base = (
                        _term("inl", inst_payload_types[ctor_idx], inst_suffix_types[ctor_idx + 1], payload_term)
                        if ctor_idx < num_ctors - 1
                        else payload_term
                    )
                    return suffix_inj(ctor_idx, base)

                payload_vars: list[_Term] = []
                payload_branches: list[_Term] = []
                for ctor_idx, ctor_info in enumerate(union_info.constructors):
                    if not ctor_info.fields:
                        pvar = self.fresh(_UNIT)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, _term("unit"))
                        leaf_body = compile_matrix(
                            subst_cols(without_index, col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 0, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if motive_body is None:
                            pbranch = leaf_body
                        else:
                            motive_ret = self.substitute(
                                motive_body,
                                root_var_id,
                                self.substitute(pattern_term, col_var_id, ctor_inj(ctor_idx, pvar)),
                            )
                            pbranch = _term(
                                "unit_match",
                                _term("lam", _UNIT, motive_ret, value=pvar.value),
                                pvar,
                                leaf_body,
                            )
                        payload_vars.append(pvar)
                        payload_branches.append(pbranch)
                    elif len(ctor_info.fields) == 1:
                        ft_0 = self._instantiate_generic_type(
                            union_info.generic_vars, col_type_args, ctor_info.fields[0].type
                        )
                        pvar = self.fresh(ft_0)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, pvar)
                        sub_columns = [(pvar, pvar, ft_0)]
                        pbranch = compile_matrix(
                            subst_cols(columns[:index], col_var_id, ctor_term)
                            + sub_columns
                            + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 1, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        payload_vars.append(pvar)
                        payload_branches.append(pbranch)
                    else:
                        pvar = self.fresh(inst_payload_types[ctor_idx])
                        field_types = []
                        field_vars = []
                        for idx_f, rf in enumerate(ctor_info.fields):
                            ft = self._instantiate_generic_type(union_info.generic_vars, col_type_args, rf.type)
                            for j in range(idx_f):
                                ft = self.substitute(ft, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                            fv = self.fresh(ft)
                            field_types.append(ft)
                            field_vars.append(fv)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, *field_vars)
                        sub_columns = [(fv, fv, ft) for fv, ft in zip(field_vars, field_types, strict=True)]
                        leaf_body = compile_matrix(
                            subst_cols(columns[:index], col_var_id, ctor_term)
                            + sub_columns
                            + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                            specialize_rows(
                                active_rows,
                                index,
                                "union",
                                ctor_term,
                                col_var_id,
                                col_type,
                                len(field_vars),
                                ctor_name=ctor_info.name,
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if ctor_info.is_dependent:
                            tail_types = []
                            for k in range(len(field_types) - 1):
                                tt = self._instantiate_generic_type(
                                    union_info.generic_vars, col_type_args, ctor_info.tail_sig_types[k + 1]
                                )
                                for j in range(k + 1):
                                    tt = self.substitute(tt, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                                tail_types.append(tt)
                        else:
                            tail_types = [field_types[-1]]
                            for ft in reversed(field_types[1:-1]):
                                tail_types.append(_term("prod", ft, tail_types[-1]))
                            tail_types.reverse()
                        tail_vars = [
                            self.fresh(tail_types[k]) for k in range(len(field_types) - 2)
                        ] + [field_vars[-1]]
                        curr_body = leaf_body
                        for k in range(len(field_types) - 2, -1, -1):
                            left_var = field_vars[k]
                            left_type = field_types[k]
                            right_var = tail_vars[k]
                            right_type = tail_types[k]
                            if k == 0:
                                scrut = pvar
                                scrut_var_id = cast("int", pvar.value)
                                scrut_type = inst_payload_types[ctor_idx]
                            else:
                                scrut = tail_vars[k - 1]
                                scrut_var_id = cast("int", scrut.value)
                                scrut_type = tail_types[k - 1]
                            if motive_body is not None and not ctor_info.is_dependent:
                                partial = scrut
                                p_type = scrut_type
                                for j in range(k - 1, -1, -1):
                                    partial = _term("pair", field_types[j], p_type, field_vars[j], partial)
                                    p_type = _term("prod", field_types[j], p_type)
                                motive_return = self.substitute(
                                    motive_body,
                                    root_var_id,
                                    self.substitute(pattern_term, col_var_id, ctor_inj(ctor_idx, partial)),
                                )
                            else:
                                motive_return = cast("_Term", inferred_result[0])
                            if ctor_info.is_dependent and cast("int", left_var.value) in self.free(motive_return):
                                fam_lam = _term("lam", left_type, right_type, value=left_var.value)
                                proj1_var = _term("projT1", left_type, fam_lam, _term("var", value=scrut_var_id))
                                motive_return = self.substitute(motive_return, cast("int", left_var.value), proj1_var)
                                if motive_body is None and inferred_result[0] is not None:
                                    inferred_result[0] = self.substitute(motive_return, scrut_var_id, scrut)
                            motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                            branch_lam = _term(
                                "lam",
                                left_type,
                                _term("lam", right_type, curr_body, value=right_var.value),
                                value=left_var.value,
                            )
                            match_kind = "sigT_match" if ctor_info.is_dependent else "pair_match"
                            curr_body = _term(match_kind, motive_lam, scrut, branch_lam)
                        payload_vars.append(pvar)
                        payload_branches.append(curr_body)

                sum_vars = [self.fresh(inst_suffix_types[i]) for i in range(1, num_ctors - 1)]
                acc_body = payload_branches[-1]
                acc_var = payload_vars[-1]
                for i in range(num_ctors - 2, -1, -1):
                    left_lam = _term("lam", inst_payload_types[i], payload_branches[i], value=payload_vars[i].value)
                    right_lam = _term("lam", inst_suffix_types[i + 1], acc_body, value=acc_var.value)
                    if i == 0:
                        scrut = col_scrutinee
                        scrut_var_id = col_var_id
                        scrut_type = col_type
                        motive_return = (
                            self.substitute(motive_body, root_var_id, pattern_term)
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                    else:
                        scrut = sum_vars[i - 1]
                        scrut_var_id = cast("int", scrut.value)
                        scrut_type = inst_suffix_types[i]
                        motive_return = (
                            self.substitute(
                                motive_body,
                                root_var_id,
                                self.substitute(pattern_term, col_var_id, suffix_inj(i, scrut)),
                            )
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                    motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                    acc_body = _term("sum_match", motive_lam, scrut, left_lam, right_lam)
                    if i > 0:
                        acc_var = sum_vars[i - 1]
                return acc_body

            if col_type == _NAT:
                zero_term = _term("nat", value=0)
                zero_body = compile_matrix(
                    subst_cols(without_index, col_var_id, zero_term),
                    specialize_rows(active_rows, index, "zero", zero_term, col_var_id, _NAT, 0),
                    self.substitute(pattern_term, col_var_id, zero_term),
                )
                pred_var = self.fresh(_NAT)
                pred_var_id = cast("int", pred_var.value)
                for r_id, s_set in self.smaller_vars.items():
                    if (
                        col_var_id == r_id
                        or col_var_id in s_set
                        or (
                            col_scrutinee.kind == "var"
                            and (
                                cast("int", col_scrutinee.value) == r_id
                                or cast("int", col_scrutinee.value) in s_set
                            )
                        )
                    ):
                        s_set.add(pred_var_id)
                succ_term = _app(_constant("Succ"), pred_var)
                sub_columns = [(pred_var, pred_var, _NAT)]
                succ_body = compile_matrix(
                    subst_cols(columns[:index], col_var_id, succ_term)
                    + sub_columns
                    + subst_cols(columns[index + 1:], col_var_id, succ_term),
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
            int_spec = self._int_spec(expected)
            if expected not in {_NAT, _BOOL, _UNIT} and int_spec is None:
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
            if int_spec is not None:
                if normalized.kind != "int":
                    raise self.fail("inference", "constant initializer did not evaluate to an admitted static value", node)
                return _Binding(normalized, value_type, constant=True)
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

    def convertible(self, left: _Term, right: _Term) -> bool:
        if left == right:
            return True
        return self._try_unify(left, right)

    def _match_meta_pattern(self, pattern: _Term, target: _Term) -> bool:
        p = self.resolve(pattern)
        t = self.resolve(target)
        if p == t:
            return True
        if p.kind == "meta" or t.kind == "meta":
            return self._try_unify(p, t)
        if (
            p.kind == t.kind
            and p.value == t.value
            and len(p.args) == len(t.args)
            and p.kind not in {"pi", "lam", "let"}
        ):
            saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            if all(self._match_meta_pattern(pa, ta) for pa, ta in zip(p.args, t.args, strict=True)):
                return True
            self.metas = saved
        return self._try_unify(p, t)

    def _is_prop_type(self, value_type: _Term) -> bool:
        if value_type in {_PROP, _NAT, _BOOL, _UNIT, _SORT}:
            return False
        if value_type.kind in {"const", "app"}:
            head, _ = self.spine(value_type)
            if head == _constant("Eq"):
                return True
            if (
                head.kind == "const"
                and isinstance(head.value, str)
                and (
                    head.value in _INT_SPECS
                    or head.value in {"Span", "Vec", "Fin", "TextBuilder", "Seq", "Slots"}
                    or head.value in self.records_by_type
                    or head.value in self.unions_by_type
                )
            ):
                return False
        return self.whnf(self.infer(value_type)) == _PROP

    def _extract_equality(self, prop: _Term) -> tuple[_Term, _Term, _Term] | None:
        head, args = self.spine(self.resolve(prop))
        if head == _constant("Eq") and len(args) == 3:
            return args[0], args[1], args[2]
        head, args = self.spine(self.whnf(prop))
        if head == _constant("Eq") and len(args) == 3:
            return args[0], args[1], args[2]
        return None

    def _replace_subterm(
        self, term: _Term, eq_type: _Term, u: _Term, z: _Term, depth: int = 0
    ) -> tuple[_Term, bool]:
        if depth > 6:
            return term, False
        term = self.resolve(term)
        if term == u or (
            depth <= 3 and self._try_unify(self.infer(term), eq_type) and self._try_unify(term, u)
        ):
            return z, True
        if term.kind not in {"pi", "lam", "let"} and term.args:
            new_args: list[_Term] = []
            any_rep = False
            for arg in term.args:
                n_arg, rep = self._replace_subterm(arg, eq_type, u, z, depth + 1)
                new_args.append(n_arg)
                any_rep = any_rep or rep
            if any_rep:
                return _Term(term.kind, term.value, tuple(new_args)), True
        if depth <= 2:
            whnf_term = self.whnf(term)
            if whnf_term != term and whnf_term.kind != "if":
                return self._replace_subterm(whnf_term, eq_type, u, z, depth + 1)
        return term, False

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
        z_id = cast("int", z.value)

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
            whnf_l = self.whnf(sub_l)
            whnf_r = self.whnf(sub_r)
            if (whnf_l != sub_l or whnf_r != sub_r) and (
                whnf_l.kind == whnf_r.kind
                and whnf_l.value == whnf_r.value
                and len(whnf_l.args) == len(whnf_r.args)
                and whnf_l.kind not in {"pi", "lam", "let"}
            ):
                child_ctxs = []
                any_replaced = False
                ok = True
                for c_l, c_r in zip(whnf_l.args, whnf_r.args, strict=True):
                    c_ctx, c_rep = build_ctx(c_l, c_r)
                    if c_ctx is None:
                        ok = False
                        break
                    child_ctxs.append(c_ctx)
                    any_replaced = any_replaced or c_rep
                if ok and any_replaced:
                    return _Term(whnf_l.kind, whnf_l.value, tuple(child_ctxs)), True
            if self._try_unify(sub_l, sub_r):
                return sub_l, False
            return None, False

        ctx, replaced = build_ctx(lhs, rhs)
        if replaced and ctx is not None and ctx != z:
            fn = _term("lam", eq_type, ctx, value=z.value)
            return _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
        self.metas = [_Meta(m.type, m.scope, m.solution) for m in saved]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        ctx_l, rep_l = self._replace_subterm(lhs, eq_type, u, z)
        if rep_l and ctx_l != z and self._try_unify(self.substitute(ctx_l, z_id, v), rhs):
            fn = _term("lam", eq_type, ctx_l, value=z.value)
            return _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
        self.metas = [_Meta(m.type, m.scope, m.solution) for m in saved]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        ctx_r, rep_r = self._replace_subterm(rhs, eq_type, v, z)
        if rep_r and ctx_r != z and self._try_unify(self.substitute(ctx_r, z_id, u), lhs):
            fn = _term("lam", eq_type, ctx_r, value=z.value)
            return _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
        self.metas = saved
        return None

    def _try_congruence_trans(
        self,
        goal_type: _Term,
        lhs: _Term,
        rhs: _Term,
        eq_type: _Term,
        u: _Term,
        v: _Term,
        proof_term: _Term,
        edges: list[tuple[int, _Term, _Term, _Term]],
    ) -> _Term | None:
        if not edges:
            return None
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        z = self.fresh(eq_type)
        z_id = cast("int", z.value)
        ctx_l, rep_l = self._replace_subterm(lhs, eq_type, u, z)
        if rep_l and ctx_l != z:
            mid = self.substitute(ctx_l, z_id, v)
            fn = _term("lam", eq_type, ctx_l, value=z.value)
            congr_p = _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
            for _, eu, ev, ep in edges:
                step_saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._try_unify(eu, mid) and self._try_unify(ev, rhs):
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, congr_p, ep)
                self.metas = step_saved
                congr2 = self._try_congruence(goal_type, mid, rhs, goal_type, eu, ev, ep)
                if congr2 is not None:
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, congr_p, congr2)
        self.metas = [_Meta(m.type, m.scope, m.solution) for m in saved]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        ctx_r, rep_r = self._replace_subterm(rhs, eq_type, v, z)
        if rep_r and ctx_r != z:
            mid = self.substitute(ctx_r, z_id, u)
            fn = _term("lam", eq_type, ctx_r, value=z.value)
            congr_p = _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
            for _, eu, ev, ep in edges:
                step_saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._try_unify(eu, lhs) and self._try_unify(ev, mid):
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, ep, congr_p)
                self.metas = step_saved
                congr1 = self._try_congruence(goal_type, lhs, mid, goal_type, eu, ev, ep)
                if congr1 is not None:
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, congr1, congr_p)
        self.metas = saved
        return None

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
                congr = None
                if self._try_unify(self.infer(eq_type), _SORT) and self._try_unify(self.infer(goal_type), _SORT):
                    z = self.fresh(eq_type)
                    z_id = cast("int", z.value)
                    ctx_u, rep_u = self._replace_subterm(current, eq_type, u, z)
                    if rep_u and ctx_u != z:
                        next_t = self.substitute(ctx_u, z_id, v)
                        fn = _term("lam", eq_type, ctx_u, value=z.value)
                        congr = (
                            current,
                            next_t,
                            _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, fact.term),
                        )
                    elif u != v:
                        ctx_v, rep_v = self._replace_subterm(current, eq_type, v, z)
                        if rep_v and ctx_v != z:
                            next_t = self.substitute(ctx_v, z_id, u)
                            fn = _term("lam", eq_type, ctx_v, value=z.value)
                            sym_p = _apps(_constant("Symm"), eq_type, u, v, fact.term)
                            congr = (
                                current,
                                next_t,
                                _apps(_constant("Congr"), eq_type, goal_type, v, u, fn, sym_p),
                            )
                if congr is not None:
                    steps.append(congr)
                    current = congr[1]
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
                if (self.current_rec_var is None or binding.term != self.current_rec_var)
                and self._is_prop_type(binding.type)
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

        if goal_whnf.kind == "ex":
            for fact in reversed(all_facts):
                if self._try_unify(fact.type, goal):
                    return fact.term
            saved_ex = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            ex_layers: list[tuple[_Term, _Term, _Term]] = []
            curr_ex = goal_whnf
            while curr_ex.kind == "ex":
                ex_dom = curr_ex.args[0]
                ex_lam = curr_ex.args[1]
                w_meta = self.meta(ex_dom, environment)
                ex_layers.append((ex_dom, ex_lam, w_meta))
                curr_ex = self.whnf(self.substitute(ex_lam.args[1], cast("int", ex_lam.value), w_meta))
            for fact in reversed(all_facts):
                attempt_saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._match_meta_pattern(curr_ex, fact.type) and all(
                    self.resolve(wm).kind != "meta" for _, _, wm in ex_layers
                ):
                    acc_proof = fact.term
                    for k_ex in range(len(ex_layers) - 1, -1, -1):
                        dom_k, lam_k, wm_k = ex_layers[k_ex]
                        for j_ex in range(k_ex):
                            prev_var_id = cast("int", ex_layers[j_ex][1].value)
                            prev_val = self.resolve(ex_layers[j_ex][2])
                            dom_k = self.substitute(dom_k, prev_var_id, prev_val)
                            lam_k = self.substitute(lam_k, prev_var_id, prev_val)
                        acc_proof = _term("ex_intro", dom_k, lam_k, self.resolve(wm_k), acc_proof)
                    return acc_proof
                self.metas = attempt_saved
            self.metas = saved_ex

        goal_eq = self._extract_equality(goal)
        if goal_eq is not None:
            goal_type, lhs, rhs = goal_eq
            if allow_refl and not all_facts:
                if self._try_unify(lhs, rhs):
                    return _apps(_constant("Refl"), goal_type, lhs)
                split_proof = self._try_if_split_equality(goal_type, lhs, rhs)
                if split_proof is not None:
                    return split_proof
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
            for fact in reversed(all_facts):
                extracted = self._extract_equality(fact.type)
                if extracted is None:
                    continue
                eq_type, u, v = extracted
                ct = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, u, v, fact.term, edges)
                if ct is not None:
                    return ct
                if u != v:
                    sym_p = _apps(_constant("Symm"), eq_type, u, v, fact.term)
                    ct_sym = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, v, u, sym_p, edges)
                    if ct_sym is not None:
                        return ct_sym
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
            if allow_refl:
                split_proof = self._try_if_split_equality(goal_type, lhs, rhs)
                if split_proof is not None:
                    return split_proof

        for fact in reversed(all_facts):
            if self._try_unify(fact.type, goal):
                return fact.term

        raise self.fail(
            "type",
            "assertion could not be established; terms or dependent indices are not definitionally equal",
            node,
        )

    def _find_if_condition(self, term: _Term, depth: int = 0) -> _Term | None:
        if depth > MAX_DEPTH:
            return None
        w = self.whnf(term)
        if w.kind == "if":
            return w.args[1]
        if w.kind == "app":
            _, args = self.spine(w)
            for child in args:
                found = self._find_if_condition(child, depth + 1)
                if found is not None:
                    return found
        return None

    def _replace_exact(self, term: _Term, target: _Term, repl: _Term) -> tuple[_Term, bool]:
        term = self.resolve(term)
        if term == target:
            return repl, True
        if term.kind in {"pi", "lam", "let"} or not term.args:
            return term, False
        new_args: list[_Term] = []
        any_rep = False
        for arg in term.args:
            n_arg, rep = self._replace_exact(arg, target, repl)
            new_args.append(n_arg)
            any_rep = any_rep or rep
        if any_rep:
            return _Term(term.kind, term.value, tuple(new_args)), True
        return term, False

    def _expose_and_replace_if(
        self, term: _Term, cond: _Term, repl: _Term, depth: int = 0
    ) -> tuple[_Term, bool]:
        if depth > MAX_DEPTH:
            return term, False
        term = self.resolve(term)
        if term == cond:
            return repl, True
        w = self.whnf(term)
        if w == cond:
            return repl, True
        if w.kind == "if":
            if w.args[1] == cond:
                return _term("if", w.args[0], repl, w.args[2], w.args[3]), True
            c_rep, did_c = self._expose_and_replace_if(w.args[1], cond, repl, depth + 1)
            if did_c:
                return _term("if", w.args[0], c_rep, w.args[2], w.args[3]), True
            return w, False
        if w.kind == "app":
            head, args = self.spine(w)
            new_args: list[_Term] = []
            any_rep = False
            for a in args:
                na, r = self._expose_and_replace_if(a, cond, repl, depth + 1)
                new_args.append(na)
                any_rep = any_rep or r
            if any_rep:
                return _apps(head, *new_args), True
        return term, False

    def _try_if_split_equality(
        self, goal_type: _Term, lhs: _Term, rhs: _Term, depth: int = 0
    ) -> _Term | None:
        if depth > 8:
            return None
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        if self._try_unify(lhs, rhs):
            return _apps(_constant("Refl"), goal_type, self.whnf(rhs))
        self.metas = saved
        cond = self._find_if_condition(lhs)
        if cond is None:
            cond = self._find_if_condition(rhs)
        if cond is None:
            return None
        b_var = self.fresh(_BOOL)
        b_id = cast("int", b_var.value)
        lhs_b, rep_l = self._expose_and_replace_if(lhs, cond, b_var)
        rhs_b, rep_r = self._expose_and_replace_if(rhs, cond, b_var)
        if not rep_l and not rep_r:
            return None
        motive_body = _apps(_constant("Eq"), goal_type, lhs_b, rhs_b)
        motive_lam = _term("lam", _BOOL, motive_body, value=b_id)
        lhs_true = self.substitute(lhs_b, b_id, _term("bool", value=1))
        rhs_true = self.substitute(rhs_b, b_id, _term("bool", value=1))
        yes_proof = self._try_if_split_equality(goal_type, lhs_true, rhs_true, depth + 1)
        if yes_proof is None:
            return None
        lhs_false = self.substitute(lhs_b, b_id, _term("bool", value=0))
        rhs_false = self.substitute(rhs_b, b_id, _term("bool", value=0))
        no_proof = self._try_if_split_equality(goal_type, lhs_false, rhs_false, depth + 1)
        if no_proof is None:
            return None
        return _term("bool_match", motive_lam, cond, yes_proof, no_proof)

    def asserted_proposition(self, node: Node, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "group":
            return self.asserted_proposition(self.node(node["value"]), environment)
        if node["kind"] == "let_expression":
            return self.asserted_proposition(
                self.node(node["body"]), self.local(self.node(node["binding"]), environment)
            )
        if node["kind"] == "binary":
            operator = self.operator(node["operator"])
            if operator == "==":
                return self.proposition(node, environment)
            if operator == "==>":
                domain = self.asserted_proposition(self.node(node["left"]), environment)
                return self.pi(domain, self.asserted_proposition(self.node(node["right"]), environment))
        if node["kind"] == "quantifier":
            quantifier = node["quantifier"]
            if quantifier not in {"forall", "exists"}:
                raise self.fail("unsupported", f"quantifier '{quantifier}' is not supported", node)
            variables, extended = self.telescope([], self.nodes(node["parameters"]), environment)
            body = self.asserted_proposition(self.node(node["value"]), extended)
            if quantifier == "forall":
                return self.wrap("pi", variables, body)
            result = body
            for variable in reversed(variables):
                domain = self.types[cast("int", variable.value)]
                result = _term("ex", domain, _term("lam", domain, result, value=variable.value))
            return result
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
        goal_whnf = self.whnf(goal)
        justification = self.expression(by_node, environment)
        if goal_whnf.kind == "ex" and not self._is_prop_type(justification.type):
            ex_domains: list[tuple[_Term, _Term]] = []
            curr_ex = goal_whnf
            while curr_ex.kind == "ex":
                ex_domains.append((curr_ex.args[0], curr_ex.args[1]))
                curr_ex = self.whnf(curr_ex.args[1].args[1])
            unwrapped_by = self._unwrap_group(by_node)
            if len(ex_domains) > 1 and unwrapped_by["kind"] == "tuple":
                tuple_nodes = self.nodes(unwrapped_by["values"])
                if len(tuple_nodes) == len(ex_domains):
                    witnesses: list[tuple[_Term, _Term, _Term]] = []
                    inst_goal = goal_whnf
                    for t_node in tuple_nodes:
                        inst_ex = self.whnf(inst_goal)
                        dom = inst_ex.args[0]
                        lam = inst_ex.args[1]
                        w_term = self.check(t_node, dom, environment)
                        witnesses.append((dom, lam, w_term))
                        inst_goal = self.substitute(lam.args[1], cast("int", lam.value), w_term)
                    acc_proof = self._prove_proposition(inst_goal, environment, facts, assert_node)
                    for dom, lam, w_term in reversed(witnesses):
                        acc_proof = _term("ex_intro", dom, lam, w_term, acc_proof)
                    return acc_proof
            ex_dom_0 = goal_whnf.args[0]
            ex_lam_0 = goal_whnf.args[1]
            w_term_0 = self.check(by_node, ex_dom_0, environment)
            inst_goal_0 = self.substitute(ex_lam_0.args[1], cast("int", ex_lam_0.value), w_term_0)
            sub_proof = self._prove_proposition(inst_goal_0, environment, facts, assert_node)
            return _term("ex_intro", ex_dom_0, ex_lam_0, w_term_0, sub_proof)
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
        if goal_whnf.kind == "ex":
            if self._try_unify(justification.type, goal):
                return justification.term
            saved_ex = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            ex_layers: list[tuple[_Term, _Term, _Term]] = []
            curr_ex = goal_whnf
            while curr_ex.kind == "ex":
                ex_dom = curr_ex.args[0]
                ex_lam = curr_ex.args[1]
                w_meta = self.meta(ex_dom, environment)
                ex_layers.append((ex_dom, ex_lam, w_meta))
                curr_ex = self.whnf(self.substitute(ex_lam.args[1], cast("int", ex_lam.value), w_meta))
            if self._match_meta_pattern(curr_ex, justification.type) and all(
                self.resolve(wm).kind != "meta" for _, _, wm in ex_layers
            ):
                acc_proof = justification.term
                for k_ex in range(len(ex_layers) - 1, -1, -1):
                    dom_k, lam_k, wm_k = ex_layers[k_ex]
                    for j_ex in range(k_ex):
                        prev_var_id = cast("int", ex_layers[j_ex][1].value)
                        prev_val = self.resolve(ex_layers[j_ex][2])
                        dom_k = self.substitute(dom_k, prev_var_id, prev_val)
                        lam_k = self.substitute(lam_k, prev_var_id, prev_val)
                    acc_proof = _term("ex_intro", dom_k, lam_k, self.resolve(wm_k), acc_proof)
                return acc_proof
            self.metas = saved_ex
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
            ct = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, u, v, justification.term, edges)
            if ct is not None:
                return ct
            if u != v:
                sym_p = _apps(_constant("Symm"), eq_type, u, v, justification.term)
                ct_sym = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, v, u, sym_p, edges)
                if ct_sym is not None:
                    return ct_sym
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
            try:
                term = self._prove_proposition(goal, environment, facts, node)
            except VelaError:
                if self.current_return_type is not None and self._is_prop_type(self.current_return_type):
                    raise
                extracted = self._extract_equality(goal)
                if extracted is not None:
                    eq_ty, lhs_t, rhs_t = extracted
                    eq_ty_w = self.whnf(eq_ty)
                    if (
                        eq_ty_w == _BOOL
                        and self.whnf(rhs_t) == _term("bool", value=1)
                        and self._prove_bool_precondition(lhs_t, environment)
                    ):
                        return _Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), goal)
                    if eq_ty_w == _NAT or self._int_spec(eq_ty_w) is not None:
                        spec = self._int_spec(eq_ty_w)
                        bool_facts = self._expand_bool_facts(
                            [*self.active_facts, *self._fact_bool_terms(facts, environment)]
                        )
                        if self._prove_comparison("eq", spec, lhs_t, rhs_t, bool_facts):
                            return _Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), goal)
                saved_assert_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                try:
                    val_b = self.expression(self.node(node["value"]), environment)
                    if self.whnf(val_b.type) == _BOOL and self._prove_bool_precondition(val_b.term, environment):
                        eq_true = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                        return _Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), eq_true)
                except VelaError:
                    self.metas = saved_assert_m
                raise
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

    def _is_propagatable_union(self, value_type: _Term) -> bool:
        resolved = self.whnf(value_type)
        head, _ = self.spine(resolved)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.unions_by_type:
            return False
        union_info = self.unions_by_type[head.value]
        if len(union_info.constructors) != 2:
            return False
        names = {c.name for c in union_info.constructors}
        return names in ({"None", "Some"}, {"Err", "Ok"})

    @staticmethod
    def _with_node_field(node: Node, key: str, value: object) -> Node:
        copied = dict(node)
        copied[key] = value
        return copied

    @classmethod
    def _make_list_rebuilder(
        cls, node: Node, key: str, items: list[Node], idx: int, inner_rebuild: Callable[[Node], Node]
    ) -> Callable[[Node], Node]:
        return lambda repl: cls._with_node_field(
            node, key, [*items[:idx], inner_rebuild(repl), *items[idx + 1:]]
        )

    @classmethod
    def _make_nested_list_rebuilder(
        cls,
        node: Node,
        key: str,
        items: list[Node],
        idx: int,
        item_node: Node,
        child_key: str,
        inner_rebuild: Callable[[Node], Node],
    ) -> Callable[[Node], Node]:
        return lambda repl: cls._with_node_field(
            node,
            key,
            [*items[:idx], cls._with_node_field(item_node, child_key, inner_rebuild(repl)), *items[idx + 1:]],
        )

    def _split_first_propagate(self, node: Node) -> tuple[Node, Callable[[Node], Node]] | None:
        kind = node["kind"]
        if kind == "propagate":
            res_inner = self._split_first_propagate(self.node(node["value"]))
            if res_inner is not None:
                prop, inner_rebuild = res_inner
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            return node, lambda repl: repl
        if kind in {"group", "unary", "member", "is", "generic_application", "expression_body"}:
            res = self._split_first_propagate(self.node(node["value"]))
            if res is not None:
                prop, inner_rebuild = res
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            return None
        if kind == "binary":
            res_l = self._split_first_propagate(self.node(node["left"]))
            if res_l is not None:
                prop, inner_rebuild = res_l
                return prop, lambda repl: self._with_node_field(node, "left", inner_rebuild(repl))
            res_r = self._split_first_propagate(self.node(node["right"]))
            if res_r is not None:
                prop, inner_rebuild = res_r
                return prop, lambda repl: self._with_node_field(node, "right", inner_rebuild(repl))
            return None
        if kind == "tuple":
            vals = self.nodes(node["values"])
            for i, v in enumerate(vals):
                res = self._split_first_propagate(v)
                if res is not None:
                    prop, inner_rebuild = res
                    return prop, self._make_list_rebuilder(node, "values", vals, i, inner_rebuild)
            return None
        if kind == "call":
            res_c = self._split_first_propagate(self.node(node["callee"]))
            if res_c is not None:
                prop, inner_rebuild = res_c
                return prop, lambda repl: self._with_node_field(node, "callee", inner_rebuild(repl))
            args = self.nodes(node["arguments"])
            for i, a in enumerate(args):
                res_a = self._split_first_propagate(self.node(a["value"]))
                if res_a is not None:
                    prop, inner_rebuild = res_a
                    return prop, self._make_nested_list_rebuilder(node, "arguments", args, i, a, "value", inner_rebuild)
            return None
        if kind == "with_expression":
            res_v = self._split_first_propagate(self.node(node["value"]))
            if res_v is not None:
                prop, inner_rebuild = res_v
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            upds = self.nodes(node["updates"])
            for i, u in enumerate(upds):
                res_u = self._split_first_propagate(self.node(u["value"]))
                if res_u is not None:
                    prop, inner_rebuild = res_u
                    return prop, self._make_nested_list_rebuilder(node, "updates", upds, i, u, "value", inner_rebuild)
            return None
        if kind == "if_expression":
            res_cond = self._split_first_propagate(self.node(node["condition"]))
            if res_cond is not None:
                prop, inner_rebuild = res_cond
                return prop, lambda repl: self._with_node_field(node, "condition", inner_rebuild(repl))
            return None
        if kind == "match_expression":
            res_val = self._split_first_propagate(self.node(node["value"]))
            if res_val is not None:
                prop, inner_rebuild = res_val
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            return None
        if kind == "let_expression":
            bnode = self.node(node["binding"])
            if bnode.get("value") is not None:
                res_b = self._split_first_propagate(self.node(bnode["value"]))
                if res_b is not None:
                    prop, inner_rebuild = res_b
                    return prop, lambda repl: self._with_node_field(
                        node, "binding", self._with_node_field(bnode, "value", inner_rebuild(repl))
                    )
            return None
        return None

    def _elaborate_propagate(
        self,
        prop_node: Node,
        environment: dict[str, _Binding],
        target_return_type: _Term,
        continuation: Callable[[str, _Binding, dict[str, _Binding]], _Term],
    ) -> _Term:
        self.site = prop_node
        if self.active_lift_scopes > 0:
            raise self.fail(
                "type",
                "cannot propagate '?' early exit while a record invariant is lifted in an enclosing scope",
                prop_node,
            )
        scrutinee = self.expression(self.node(prop_node["value"]), environment)
        scrut_type = self.whnf(scrutinee.type)
        scrut_head, scrut_type_args = self.spine(scrut_type)
        if (
            scrut_head.kind != "const"
            or not isinstance(scrut_head.value, str)
            or scrut_head.value not in self.unions_by_type
        ):
            raise self.fail(
                "type",
                "'?' operator requires an Option (None/Some) or Result (Err/Ok) union operand",
                prop_node,
            )
        union_info = self.unions_by_type[scrut_head.value]
        if len(union_info.constructors) != 2:
            raise self.fail(
                "type",
                "'?' operator requires a 2-variant Option (None/Some) or Result (Err/Ok) union operand",
                prop_node,
            )
        ok_idx: int | None = None
        err_idx: int | None = None
        for idx, ctor in enumerate(union_info.constructors):
            if ctor.name in {"Some", "Ok"} and len(ctor.fields) == 1:
                ok_idx = idx
            elif (ctor.name == "None" and len(ctor.fields) == 0) or (
                ctor.name == "Err" and len(ctor.fields) == 1
            ):
                err_idx = idx
        if ok_idx is None or err_idx is None:
            raise self.fail(
                "type",
                "'?' operator requires an Option (None/Some) or Result (Err/Ok) union operand",
                prop_node,
            )
        ret_type = self.whnf(target_return_type)
        ret_head, ret_type_args = self.spine(ret_type)
        if (
            ret_head.kind != "const"
            or not isinstance(ret_head.value, str)
            or ret_head.value != scrut_head.value
            or not self._is_propagatable_union(ret_type)
        ):
            raise self.fail(
                "type",
                "'?' propagation requires an enclosing callable or block returning a compatible Option or Result union",
                prop_node,
            )
        inst_payload_types = [
            self._instantiate_generic_type(union_info.generic_vars, scrut_type_args, c.payload_type)
            for c in union_info.constructors
        ]
        err_ctor = union_info.constructors[err_idx]
        err_var = self.fresh(inst_payload_types[err_idx])
        if not err_ctor.fields:
            early_return_term = _apps(_constant(err_ctor.ctor_const), *ret_type_args, _term("unit"))
        else:
            ret_err_type = self._instantiate_generic_type(
                union_info.generic_vars, ret_type_args, err_ctor.payload_type
            )
            self.unify(inst_payload_types[err_idx], ret_err_type)
            early_return_term = _apps(_constant(err_ctor.ctor_const), *ret_type_args, err_var)
        ok_type = inst_payload_types[ok_idx]
        ok_var = self.fresh(ok_type)
        temp_name = f"__vela_prop_{ok_var.value}"
        ok_binding = _Binding(ok_var, ok_type)
        ok_env = dict(environment)
        ok_env[temp_name] = ok_binding
        ok_branch_term = continuation(temp_name, ok_binding, ok_env)
        scrut_var = self.fresh(scrut_type)
        motive_lam = _term("lam", scrut_type, target_return_type, value=scrut_var.value)
        if ok_idx == 0:
            left_lam = _term("lam", ok_type, ok_branch_term, value=ok_var.value)
            right_lam = _term("lam", inst_payload_types[1], early_return_term, value=err_var.value)
        else:
            left_lam = _term("lam", inst_payload_types[0], early_return_term, value=err_var.value)
            right_lam = _term("lam", ok_type, ok_branch_term, value=ok_var.value)
        return _term("sum_match", motive_lam, scrutinee.term, left_lam, right_lam)

    def _check_record_invariants(
        self,
        record_info: _RecordInfo,
        type_args: list[_Term],
        rec_term: _Term,
        environment: dict[str, _Binding],
        site: Node | None,
        *,
        only_clauses: set[str] | None = None,
        exclude_clauses: set[str] | None = None,
    ) -> None:
        if not record_info.invariants:
            return
        for inv in record_info.invariants:
            if only_clauses is not None and inv.name not in only_clauses:
                continue
            if exclude_clauses is not None and inv.name in exclude_clauses:
                continue
            inst_term = self._instantiate_record_type(record_info, type_args, inv.term)
            inst_term = self.substitute(inst_term, cast("int", inv.self_var.value), rec_term)
            inst_type = self._instantiate_record_type(record_info, type_args, inv.type)
            inst_type = self.substitute(inst_type, cast("int", inv.self_var.value), rec_term)
            clause_label = "" if inv.name.startswith("__anon_") else f" '{inv.name}'"
            if self.whnf(inst_type) == _BOOL:
                if not self._prove_bool_precondition(inst_term, environment):
                    raise self.fail(
                        "type",
                        f"record '{record_info.name}' invariant{clause_label} could not be established",
                        site if site is not None else self.site,
                    )
            else:
                self._prove_proposition(
                    inst_term,
                    environment,
                    (),
                    site if site is not None else cast("Node", self.site),
                )

    def _elaborate_assignment(self, statement: Node, extended: dict[str, _Binding]) -> dict[str, _Binding]:
        self.site = statement
        target = self._unwrap_group(self.node(statement["target"]))
        raw_op = statement["operator"]
        if (
            not isinstance(raw_op, dict)
            or not isinstance(raw_op.get("text"), str)
            or raw_op["text"] not in _ASSIGN_OPERATORS
        ):
            raise self.fail("protocol", "expected a supported assignment operator", statement)
        op = cast("str", raw_op["text"])
        val_node = self.node(statement["value"])
        updated = dict(extended)
        if target["kind"] == "name":
            tname = self.name(target["name"])
            if tname not in updated:
                raise self.fail("name", f"unknown identifier '{tname}'", target)
            if tname in self.frozen_collections:
                raise self.fail("type", f"cannot mutate collection '{tname}' while iterating over it", statement)
            if tname not in self.mutable_locals:
                raise self.fail(
                    "type",
                    f"cannot assign to immutable binding '{tname}'; declare it with 'var' or 'ref'",
                    target,
                )
            cur_b = updated[tname]
            if self._is_readonly_span(cur_b.term):
                raise self.fail("type", f"cannot mutate a read-only 'in' parameter '{tname}'", target)
            if op == "=":
                prev_assign_target = getattr(self, "_in_lifted_target_assignment", None)
                self._in_lifted_target_assignment = tname
                try:
                    rhs_term = self.check(val_node, cur_b.type, updated)
                finally:
                    self._in_lifted_target_assignment = prev_assign_target
            else:
                bin_op = op[:-1]
                bin_node: Node = {
                    "kind": "binary",
                    "span": statement["span"],
                    "operator": {"text": bin_op, "span": cast("Node", statement["operator"])["span"]},
                    "left": target,
                    "right": val_node,
                }
                rhs_term = self.check(bin_node, cur_b.type, updated)
            rec_head, rec_targs = self.spine(self.whnf(cur_b.type))
            if (
                rec_head.kind == "const"
                and isinstance(rec_head.value, str)
                and rec_head.value in self.records_by_type
            ):
                rinfo = self.records_by_type[rec_head.value]
                lifted = self.lifted_invariants.get(tname, set())
                self._check_record_invariants(
                    rinfo, rec_targs, rhs_term, updated, statement, exclude_clauses=lifted
                )
            updated[tname] = _Binding(rhs_term, cur_b.type)
            return updated
        if target["kind"] == "member":
            recv_node = self._unwrap_group(self.node(target["value"]))
            fname = self.name(target["name"])
            if recv_node["kind"] != "name":
                raise self.fail("type", "member assignment requires a named record variable target", target)
            rname = self.name(recv_node["name"])
            if rname not in updated:
                raise self.fail("name", f"unknown identifier '{rname}'", recv_node)
            if rname in self.frozen_collections:
                raise self.fail("type", f"cannot mutate collection '{rname}' while iterating over it", statement)
            if rname not in self.mutable_locals:
                raise self.fail(
                    "type",
                    f"cannot mutate field '{fname}' of immutable record '{rname}'; declare it with 'var' or 'ref'",
                    target,
                )
            cur_b = updated[rname]
            if self._is_readonly_span(cur_b.term):
                raise self.fail("type", f"cannot mutate a read-only 'in' parameter '{rname}'", target)
            rec_type = self.whnf(cur_b.type)
            head, type_args = self.spine(rec_type)
            if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
                raise self.fail("type", f"member assignment target '{rname}' must be a record", target)
            record_info = self.records_by_type[head.value]
            field_index = next((idx for idx, rf in enumerate(record_info.fields) if rf.name == fname), None)
            if field_index is None:
                raise self.fail("name", f"record '{record_info.name}' has no mutable field '{fname}'", target)
            rhs_expr: Node = (
                val_node
                if op == "="
                else {
                    "kind": "binary",
                    "span": statement["span"],
                    "operator": {"text": op[:-1], "span": cast("Node", statement["operator"])["span"]},
                    "left": target,
                    "right": val_node,
                }
            )
            final_fields: list[_Term] = []
            for idx, rf in enumerate(record_info.fields):
                ftype = self._instantiate_record_type(record_info, type_args, rf.type)
                for j in range(idx):
                    ftype = self.substitute(ftype, cast("int", record_info.fields[j].var.value), final_fields[j])
                if idx == field_index:
                    final_fields.append(self.check(rhs_expr, ftype, updated))
                else:
                    old_ftype = self._instantiate_record_field_type(record_info, type_args, idx, cur_b.term)
                    if not self._try_unify(old_ftype, ftype):
                        raise self.fail(
                            "type",
                            f"field assignment changes an index that field '{rf.name}' depends on; use 'with' to update dependent fields together",
                            statement,
                        )
                    final_fields.append(_apps(_constant(rf.proj_const), *type_args, cur_b.term))
            new_rec_term = _apps(_constant(record_info.ctor_const), *type_args, *final_fields)
            lifted = self.lifted_invariants.get(rname, set())
            self._check_record_invariants(
                record_info, type_args, new_rec_term, updated, statement, exclude_clauses=lifted
            )
            updated[rname] = _Binding(new_rec_term, cur_b.type)
            return updated
        raise self.fail("type", "assignment target must be a mutable local variable or record field", target)

    @staticmethod
    def _extract_ref_or_var_name(arg_node: Node) -> tuple[str | None, bool]:
        val = arg_node.get("value") if arg_node.get("kind") == "argument" else arg_node
        while isinstance(val, dict) and val.get("kind") == "group":
            val = val.get("value")
        if not isinstance(val, dict):
            return None, False
        if (
            val.get("kind") == "unary"
            and isinstance(val.get("operator"), dict)
            and cast("Node", val["operator"]).get("text") == "ref"
        ):
            inner = val.get("value")
            while isinstance(inner, dict) and inner.get("kind") == "group":
                inner = inner.get("value")
            if isinstance(inner, dict) and inner.get("kind") == "name" and isinstance(inner.get("name"), dict):
                return cast("str", cast("Node", inner["name"]).get("text")), True
            return None, True
        if val.get("kind") == "name" and isinstance(val.get("name"), dict):
            return cast("str", cast("Node", val["name"]).get("text")), False
        return None, False

    def _apply_ref_target_update(
        self, arg_node: Node, new_binding: _Binding, updated: dict[str, _Binding], site: Node
    ) -> bool:
        val = arg_node.get("value") if arg_node.get("kind") == "argument" else arg_node
        while isinstance(val, dict) and val.get("kind") == "group":
            val = val.get("value")
        if (
            isinstance(val, dict)
            and val.get("kind") == "unary"
            and isinstance(val.get("operator"), dict)
            and cast("Node", val["operator"]).get("text") in {"ref", "in"}
        ):
            val = val.get("value")
            while isinstance(val, dict) and val.get("kind") == "group":
                val = val.get("value")
        if not isinstance(val, dict):
            return False
        if val.get("kind") == "name" and isinstance(val.get("name"), dict):
            vname = cast("str", cast("Node", val["name"]).get("text"))
            if vname in updated:
                if vname in self.frozen_collections:
                    raise self.fail("type", f"cannot mutate frozen collection '{vname}'", site)
                updated[vname] = new_binding
                return True
            return False
        if val.get("kind") == "member" and isinstance(val.get("name"), dict) and isinstance(val.get("value"), dict):
            recv = self._unwrap_group(cast("Node", val["value"]))
            fname = cast("str", cast("Node", val["name"]).get("text"))
            if recv.get("kind") == "name" and isinstance(recv.get("name"), dict):
                rname = cast("str", cast("Node", recv["name"]).get("text"))
                if rname in updated:
                    if rname in self.frozen_collections:
                        raise self.fail("type", f"cannot mutate frozen collection '{rname}'", site)
                    if rname not in self.mutable_locals:
                        raise self.fail(
                            "type",
                            f"cannot mutate field '{fname}' of immutable record '{rname}'; declare it with 'var' or 'ref'",
                            site,
                        )
                    cur_b = updated[rname]
                    rec_type = self.whnf(cur_b.type)
                    head, type_args = self.spine(rec_type)
                    if (
                        head.kind == "const"
                        and isinstance(head.value, str)
                        and head.value in self.records_by_type
                    ):
                        record_info = self.records_by_type[head.value]
                        field_index = next(
                            (idx for idx, rf in enumerate(record_info.fields) if rf.name == fname), None
                        )
                        if field_index is not None:
                            final_fields: list[_Term] = []
                            for idx, rf in enumerate(record_info.fields):
                                if idx == field_index:
                                    final_fields.append(new_binding.term)
                                else:
                                    final_fields.append(_apps(_constant(rf.proj_const), *type_args, cur_b.term))
                            new_rec_term = _apps(_constant(record_info.ctor_const), *type_args, *final_fields)
                            lifted = self.lifted_invariants.get(rname, set())
                            self._check_record_invariants(
                                record_info, type_args, new_rec_term, updated, site, exclude_clauses=lifted
                            )
                            updated[rname] = _Binding(new_rec_term, cur_b.type)
                            return True
        return False

    def _elaborate_expression_statement(
        self, statement: Node, extended: dict[str, _Binding]
    ) -> dict[str, _Binding]:
        self.site = statement
        expr_node = self._unwrap_group(self.node(statement["value"]))
        updated = dict(extended)
        if expr_node["kind"] == "call":
            callee = self._unwrap_group(self.node(expr_node["callee"]))
            call_args = self.nodes(expr_node["arguments"])
            path = self._dotted_member_path(callee)
            if path is None and callee["kind"] == "generic_application":
                path = self._dotted_member_path(self.node(callee["value"]))
            if path in {"TransferType", "Slots.TransferType"} and len(call_args) == 3:
                res_b = self.expression(expr_node, updated)
                prod_ty = self.whnf(res_b.type)
                if prod_ty.kind == "prod":
                    src_ty, dst_ty = prod_ty.args
                    src_b = _Binding(
                        self.whnf(_apps(_constant("Fst"), src_ty, dst_ty, res_b.term)), src_ty
                    )
                    dst_b = _Binding(
                        self.whnf(_apps(_constant("Snd"), src_ty, dst_ty, res_b.term)), dst_ty
                    )
                    self._apply_ref_target_update(call_args[0], src_b, updated, statement)
                    self._apply_ref_target_update(call_args[1], dst_b, updated, statement)
                    return updated
            if path in {"CopyRepresentation", "Slots.CopyRepresentation"} and len(call_args) == 3:
                res_b = self.expression(expr_node, updated)
                if self._apply_ref_target_update(call_args[1], res_b, updated, statement):
                    return updated
            if path == "Slots.Write" and len(call_args) == 3:
                res_b = self.expression(expr_node, updated)
                if self._apply_ref_target_update(call_args[0], res_b, updated, statement):
                    return updated
            if path in {"Span.Write", "Span.Fill", "Span.CopyPrefix", "Span.Restore"} and len(call_args) >= 2:
                res_b = self.expression(expr_node, updated)
                if self._apply_ref_target_update(call_args[0], res_b, updated, statement):
                    return updated
            if path == "Format.Write" and len(call_args) == 2:
                b_name, _ = self._extract_ref_or_var_name(call_args[0])
                res_b = self.expression(expr_node, updated)
                if b_name is not None and b_name in updated:
                    updated[b_name] = res_b
                    return updated
        self.expression(expr_node, updated)
        return updated

    def _elaborate_scope_statement(
        self,
        statement: Node,
        extended: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> dict[str, _Binding]:
        self.site = statement
        loan_nodes = self.nodes(statement["resources"])
        lift_raw = statement.get("lifts")
        if lift_raw is not None and not isinstance(lift_raw, list):
            raise self.fail("protocol", "expected a syntax list", statement)
        lift_names = [] if lift_raw is None else [self.name(ln) for ln in lift_raw]
        if len(lift_names) != len(set(lift_names)):
            raise self.fail("name", "duplicate record invariant clause in scope lifts list", statement)
        loaned_records: list[tuple[str, _RecordInfo, list[_Term]]] = []
        seen_targets: set[str] = set()
        for loan_node in loan_nodes:
            self.node(loan_node, "unary")
            tname, is_ref = self._extract_ref_or_var_name(loan_node)
            if not is_ref or tname is None:
                raise self.fail("type", "scope header requires 'ref <variable>' loan targets", loan_node)
            if tname in seen_targets:
                raise self.fail("type", f"duplicate 'ref {tname}' loan in scope header", loan_node)
            seen_targets.add(tname)
            if tname not in extended:
                raise self.fail("name", f"unknown identifier '{tname}' in scope header", loan_node)
            if tname in self.frozen_collections:
                raise self.fail("type", f"cannot mutably loan frozen collection '{tname}'", loan_node)
            cur_b = extended[tname]
            if self._is_readonly_span(cur_b.term):
                raise self.fail(
                    "type", f"cannot take mutable 'ref' loan of read-only 'in' parameter '{tname}'", loan_node
                )
            rec_type = self.whnf(cur_b.type)
            head, type_args = self.spine(rec_type)
            if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
                raise self.fail(
                    "type", f"scope invariant lifting requires a record target, got '{tname}'", loan_node
                )
            rinfo = self.records_by_type[head.value]
            loaned_records.append((tname, rinfo, type_args))
        for cname in lift_names:
            matching = [
                tname
                for tname, rinfo, _ in loaned_records
                if any(inv.name == cname and not inv.name.startswith("__anon_") for inv in rinfo.invariants)
            ]
            if not matching:
                raise self.fail(
                    "name",
                    f"none of the loaned records in scope declare named invariant clause '{cname}'",
                    statement,
                )
        saved_mutable = set(self.mutable_locals)
        saved_lifted = {k: set(v) for k, v in self.lifted_invariants.items()}
        saved_active_facts = list(self.active_facts)
        # Remove facts originating from the lifted invariant clauses during the scope body,
        # while retaining pre-scope Slots_LivePrefix / Slots_VacantRange facts on the entry record term.
        lifted_by_target: dict[str, set[str]] = {}
        lifted_fact_terms: set[_Term] = set()
        pre_scope_slot_facts: list[_Term] = []
        for tname, rinfo, type_args in loaned_records:
            self.mutable_locals.add(tname)
            clauses_for_t = {
                inv.name
                for inv in rinfo.invariants
                if inv.name in lift_names
            }
            lifted_by_target[tname] = clauses_for_t
            self.lifted_invariants.setdefault(tname, set()).update(clauses_for_t)
            for inv in rinfo.invariants:
                if inv.name in clauses_for_t:
                    inst_t = self._instantiate_record_type(rinfo, type_args, inv.term)
                    inst_t = self.substitute(inst_t, cast("int", inv.self_var.value), extended[tname].term)
                    w_inst = self.whnf(inst_t)
                    lifted_fact_terms.add(w_inst)
                    w_head, _ = self.spine(w_inst)
                    if w_head in {_constant("Slots_LivePrefix"), _constant("Slots_VacantRange")}:
                        pre_scope_slot_facts.append(inst_t)
        self.active_facts = [
            *(f for f in self.active_facts if self.whnf(f) not in lifted_fact_terms),
            *pre_scope_slot_facts,
        ]
        self.active_lift_scopes += 1
        try:
            body_block = self.node(statement["body"], "block")
            after_env, _ = self._elaborate_non_returning_block(body_block, extended, facts)
        finally:
            self.active_lift_scopes -= 1
            self.mutable_locals = saved_mutable
            self.lifted_invariants = saved_lifted
            self.active_facts = saved_active_facts
        for tname, rinfo, type_args in loaned_records:
            self._check_record_invariants(
                rinfo,
                type_args,
                after_env[tname].term,
                after_env,
                statement,
                only_clauses=lifted_by_target[tname],
            )
            for inv in rinfo.invariants:
                inst_ty = self._instantiate_record_type(rinfo, type_args, inv.type)
                inst_ty = self.substitute(inst_ty, cast("int", inv.self_var.value), after_env[tname].term)
                if self.whnf(inst_ty) == _BOOL:
                    inst_t = self._instantiate_record_type(rinfo, type_args, inv.term)
                    inst_t = self.substitute(inst_t, cast("int", inv.self_var.value), after_env[tname].term)
                    self.active_facts.append(inst_t)
        return after_env

    def _check_loop_invariants(
        self,
        contracts: list[Node],
        env: dict[str, _Binding],
        site: Node,
        phase: str,
    ) -> list[_Term]:
        proved_bools: list[_Term] = []
        for contract in contracts:
            self.node(contract, "contract")
            if contract["role"] != "invariant":
                raise self.fail("unsupported", f"loop contract '{contract['role']}' is not supported", contract)
            c_val_node = self.node(contract["value"])
            c_val = self.expression(c_val_node, env)
            c_label = f" '{self.name(contract['name'])}'" if contract.get("name") is not None else ""
            if self.whnf(c_val.type) == _BOOL:
                if not self._prove_bool_precondition(c_val.term, env):
                    raise self.fail(
                        "type",
                        f"loop invariant{c_label} could not be established on loop {phase}",
                        contract,
                    )
                proved_bools.append(c_val.term)
            else:
                prop_t = self.proposition(c_val_node, env)
                self._prove_proposition(prop_t, env, (), contract)
        return proved_bools

    def _assume_loop_invariants(
        self,
        contracts: list[Node],
        env: dict[str, _Binding],
    ) -> list[_Term]:
        assumed_bools: list[_Term] = []
        for contract in contracts:
            self.node(contract, "contract")
            if contract["role"] != "invariant":
                raise self.fail("unsupported", f"loop contract '{contract['role']}' is not supported", contract)
            c_val_node = self.node(contract["value"])
            self.active_facts.extend(assumed_bools)
            try:
                c_val = self.expression(c_val_node, env)
            finally:
                for _ in assumed_bools:
                    self.active_facts.pop()
            if self.whnf(c_val.type) == _BOOL:
                assumed_bools.append(c_val.term)
            else:
                prop_t = self.proposition(c_val_node, env)
                extracted = self._extract_equality(prop_t)
                if extracted is not None:
                    eq_ty, u, v = extracted
                    eq_ty_w = self.whnf(eq_ty)
                    if eq_ty_w == _BOOL and self.whnf(v) == _term("bool", value=1):
                        assumed_bools.append(u)
                    elif self._int_spec(eq_ty_w) is not None or eq_ty_w == _NAT:
                        spec = self._int_spec(eq_ty_w)
                        eq_const = f"int_eq_{spec.name}" if spec is not None else "eq_nat"
                        assumed_bools.append(_apps(_constant(eq_const), u, v))
        return assumed_bools

    def _elaborate_non_returning_block(
        self,
        block_node: Node,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> tuple[dict[str, _Binding], str | None]:
        self.node(block_node, "block")
        statements = self.nodes(block_node["statements"])
        extended = dict(environment)
        statement_facts: list[_Binding] = []
        saved_active_len = len(self.active_facts)
        try:
            for statement in statements:
                self.site = statement
                kind = cast("str", statement["kind"])
                if kind in {"let", "typed_local", "let_pattern", "constant_local", "var", "var_pattern"}:
                    previous_keys = set(extended)
                    extended = self.local(statement, extended)
                    for new_key in set(extended) - previous_keys:
                        bound = extended[new_key]
                        if self._is_prop_type(bound.type):
                            statement_facts.append(bound)
                            self.active_facts.extend(self._fact_bool_terms((bound,), extended))
                    continue
                if kind in {"let_else", "var_else"}:
                    scrut = self.expression(self.node(statement["value"]), extended)
                    pat = self._parse_pattern(self.node(statement["pattern"]), set())
                    self._typecheck_pattern(pat, scrut.type, extended)
                    else_block = self.node(statement["else"], "block")
                    if self._pattern_matches_concretely(pat, scrut.term):
                        self._bind_concrete_pattern(
                            pat, scrut, extended, is_var=(kind == "var_else")
                        )
                        continue
                    if self._pattern_refuted_concretely(pat, scrut.term):
                        else_env, ctrl = self._elaborate_non_returning_block(
                            else_block, extended, (*facts, *statement_facts)
                        )
                        if ctrl not in {"break", "continue"}:
                            raise self.fail(
                                "type",
                                f"{kind.replace('_', '-')} else block must exit with return, break or continue",
                                statement,
                            )
                        return else_env, ctrl
                    else_env, ctrl = self._elaborate_non_returning_block(
                        else_block, dict(extended), (*facts, *statement_facts)
                    )
                    if ctrl not in {"break", "continue"}:
                        raise self.fail(
                            "type",
                            f"{kind.replace('_', '-')} else block must exit with return, break or continue",
                            statement,
                        )
                    self._bind_symbolic_pattern(pat, scrut, extended, is_var=(kind == "var_else"))
                    continue
                if kind == "assignment":
                    extended = self._elaborate_assignment(statement, extended)
                    continue
                if kind == "expression_statement":
                    extended = self._elaborate_expression_statement(statement, extended)
                    continue
                if kind == "assert":
                    fact = self._elaborate_assert(statement, extended, (*facts, *statement_facts))
                    statement_facts.append(fact)
                    self.active_facts.extend(self._fact_bool_terms((fact,), extended))
                    continue
                if kind == "proof":
                    sub_facts = self._elaborate_proof_statement(
                        self.node(statement["body"], "block"), extended, (*facts, *statement_facts)
                    )
                    statement_facts.extend(sub_facts)
                    self.active_facts.extend(self._fact_bool_terms(sub_facts, extended))
                    continue
                if kind == "scope":
                    extended = self._elaborate_scope_statement(
                        statement, extended, (*facts, *statement_facts)
                    )
                    continue
                if kind == "foreach":
                    extended = self._elaborate_foreach_statement(
                        statement, extended, (*facts, *statement_facts)
                    )
                    continue
                if kind == "foreach_collection":
                    extended = self._elaborate_foreach_collection_statement(
                        statement, extended, (*facts, *statement_facts)
                    )
                    continue
                if kind in {"break", "continue"}:
                    if self.in_loop_depth <= 0:
                        raise self.fail("type", f"'{kind}' statement is only permitted inside a loop", statement)
                    if self.active_lift_scopes > 0:
                        raise self.fail(
                            "type",
                            f"cannot '{kind}' out of a loop while a record invariant is lifted",
                            statement,
                        )
                    return extended, cast("str", kind)
                if kind == "if":
                    cond_raw = self.node(statement["condition"])
                    condition = self.check(cond_raw, _BOOL, extended)
                    cond_w = self.whnf(condition)
                    then_node = self.node(statement["then"])
                    then_block = (
                        then_node
                        if then_node["kind"] == "block"
                        else {"kind": "block", "span": then_node["span"], "statements": [then_node]}
                    )
                    else_raw = statement["else"]
                    else_block = (
                        None
                        if else_raw is None
                        else (
                            self.node(else_raw)
                            if self.node(else_raw)["kind"] == "block"
                            else {
                                "kind": "block",
                                "span": self.node(else_raw)["span"],
                                "statements": [self.node(else_raw)],
                            }
                        )
                    )
                    if cond_w.kind == "bool":
                        if cond_w.value == 1:
                            extended, ctrl = self._elaborate_non_returning_block(
                                then_block, extended, (*facts, *statement_facts)
                            )
                            if ctrl is not None:
                                return extended, ctrl
                        elif else_block is not None:
                            extended, ctrl = self._elaborate_non_returning_block(
                                else_block, extended, (*facts, *statement_facts)
                            )
                            if ctrl is not None:
                                return extended, ctrl
                        continue
                    self.active_facts.append(condition)
                    try:
                        then_env, then_ctrl = self._elaborate_non_returning_block(
                            then_block, dict(extended), (*facts, *statement_facts)
                        )
                    finally:
                        self.active_facts.pop()
                    if else_block is not None:
                        self.active_facts.append(_app(_constant("!"), condition))
                        try:
                            else_env, else_ctrl = self._elaborate_non_returning_block(
                                else_block, dict(extended), (*facts, *statement_facts)
                            )
                        finally:
                            self.active_facts.pop()
                    else:
                        else_env, else_ctrl = dict(extended), None
                    if then_ctrl is not None and else_ctrl is None:
                        self.active_facts.append(_app(_constant("!"), condition))
                        extended = else_env
                        continue
                    if else_ctrl is not None and then_ctrl is None:
                        self.active_facts.append(condition)
                        extended = then_env
                        continue
                    for k, orig_b in list(extended.items()):
                        tb = then_env.get(k, orig_b)
                        eb = else_env.get(k, orig_b)
                        if tb.term != eb.term:
                            extended[k] = _Binding(
                                self.whnf(_term("if", orig_b.type, condition, tb.term, eb.term)),
                                orig_b.type,
                            )
                    if then_ctrl is not None and then_ctrl == else_ctrl:
                        return extended, then_ctrl
                    continue
                if kind == "block":
                    extended, ctrl = self._elaborate_non_returning_block(
                        statement, extended, (*facts, *statement_facts)
                    )
                    if ctrl is not None:
                        return extended, ctrl
                    continue
                if kind == "return":
                    if self.active_lift_scopes > 0:
                        raise self.fail(
                            "type",
                            "cannot return from a callable while a record invariant is lifted in an enclosing scope",
                            statement,
                        )
                    raise self.fail("unsupported", "early return inside a loop or scope block is not supported", statement)
                raise self.fail("unsupported", f"statement '{kind}' requires the full frontend", statement)
            return extended, None
        finally:
            del self.active_facts[saved_active_len:]

    def _pattern_matches_concretely(self, pat: _Pat, term: _Term) -> bool:
        w = self.whnf(term)
        if pat.kind == "wild":
            return True
        if pat.kind == "bool":
            return w.kind == "bool" and bool(w.value) == pat.value
        if pat.kind == "zero":
            return w.kind == "nat" and w.value == 0
        if pat.kind == "succ":
            return w.kind == "nat" and cast("int", w.value) > 0
        if pat.kind == "int_lit":
            return w.kind == "int" and w.value == pat.value
        if pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            head, args = self.spine(w)
            if head == _constant(uctor.ctor_const):
                payload_args = args[len(uinfo.generic_vars) :]
                if not uctor.fields:
                    return True
                return all(
                    self._pattern_matches_concretely(sp, pa)
                    for sp, pa in zip(pat.args, payload_args, strict=True)
                )
        return False

    def _pattern_refuted_concretely(self, pat: _Pat, term: _Term) -> bool:
        w = self.whnf(term)
        if pat.kind == "bool" and w.kind == "bool":
            return bool(w.value) != pat.value
        if pat.kind == "zero" and w.kind == "nat":
            return cast("int", w.value) != 0
        if pat.kind == "succ" and w.kind == "nat":
            return cast("int", w.value) == 0
        if pat.kind == "int_lit" and w.kind == "int":
            return w.value != pat.value
        if pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            head, _ = self.spine(w)
            if head.kind == "const" and any(head == _constant(c.ctor_const) for c in uinfo.constructors):
                return head != _constant(uctor.ctor_const)
        return False

    def _bind_concrete_pattern(
        self, pat: _Pat, current: _Binding, extended: dict[str, _Binding], *, is_var: bool
    ) -> None:
        for name in pat.names:
            if is_var:
                self.mutable_locals.add(name)
            else:
                self.mutable_locals.discard(name)
            extended[name] = current
        w = self.whnf(current.term)
        if pat.kind == "succ" and w.kind == "nat":
            pred_b = _Binding(_term("nat", value=cast("int", w.value) - 1), _NAT)
            self._bind_concrete_pattern(pat.args[0], pred_b, extended, is_var=is_var)
        elif pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            _, type_args = self.spine(self.whnf(current.type))
            _, args = self.spine(w)
            payload_args = args[len(uinfo.generic_vars) :]
            for idx, (sp, pa) in enumerate(zip(pat.args, payload_args, strict=False)):
                fty = self._instantiate_generic_type(uinfo.generic_vars, type_args, uctor.fields[idx].type)
                self._bind_concrete_pattern(sp, _Binding(pa, fty), extended, is_var=is_var)

    def _bind_symbolic_pattern(
        self, pat: _Pat, current: _Binding, extended: dict[str, _Binding], *, is_var: bool
    ) -> None:
        for name in pat.names:
            if is_var:
                self.mutable_locals.add(name)
            else:
                self.mutable_locals.discard(name)
            extended[name] = current
        if pat.kind == "succ":
            pred_v = self.fresh(_NAT)
            self._bind_symbolic_pattern(pat.args[0], _Binding(pred_v, _NAT), extended, is_var=is_var)
        elif pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            _, type_args = self.spine(self.whnf(current.type))
            for idx, sp in enumerate(pat.args):
                fty = self._instantiate_generic_type(uinfo.generic_vars, type_args, uctor.fields[idx].type)
                fv = self.fresh(fty)
                self._bind_symbolic_pattern(sp, _Binding(fv, fty), extended, is_var=is_var)

    def _elaborate_foreach_statement(
        self,
        statement: Node,
        extended: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> dict[str, _Binding]:
        self.site = statement
        range_node = self.node(statement["range"], "range")
        start_node = self.node(range_node["start"])
        end_node = self.node(range_node["end"])
        if statement.get("type") is not None:
            elem_type = self.type(self.node(statement["type"]), extended)
            start_term = self.check(start_node, elem_type, extended)
            end_term = self.check(end_node, elem_type, extended)
        elif self._is_unsuffixed_int_expr(start_node) and not self._is_unsuffixed_int_expr(end_node):
            end_b = self.expression(end_node, extended)
            elem_type = end_b.type
            end_term = end_b.term
            start_term = self.check(start_node, elem_type, extended)
        else:
            start_b = self.expression(start_node, extended)
            elem_type = start_b.type
            start_term = start_b.term
            end_term = self.check(end_node, elem_type, extended)
        elem_w = self.whnf(elem_type)
        elem_spec = self._int_spec(elem_w)
        if elem_w != _NAT and elem_spec is None:
            raise self.fail(
                "type", "foreach range loop variable must have type Nat or a fixed-width integer", statement
            )
        var_name = self.name(statement["name"])
        if var_name in self.frozen_collections:
            raise self.fail("type", f"cannot shadow frozen collection '{var_name}'", statement)
        contracts = self.nodes(statement["contracts"])
        body_node = self.node(statement["body"], "block")
        start_w = self.whnf(start_term)
        end_w = self.whnf(end_term)
        saved_mutable = set(self.mutable_locals)
        self.mutable_locals.discard(var_name)
        self.in_loop_depth += 1
        try:
            # Verify loop invariants on entry (var_name = start_term)
            entry_env = dict(extended)
            entry_env[var_name] = _Binding(start_term, elem_type)
            self._check_loop_invariants(contracts, entry_env, statement, "entry")
            if (
                start_w.kind in {"nat", "int"}
                and end_w.kind in {"nat", "int"}
                and cast("int", end_w.value) - cast("int", start_w.value) <= 64
            ):
                s_val = cast("int", start_w.value)
                e_val = cast("int", end_w.value)
                cur_env = dict(extended)
                broke = False
                for i_val in range(s_val, e_val):
                    i_term = (
                        _int_term(elem_spec, i_val)
                        if elem_spec is not None
                        else _term("nat", value=i_val)
                    )
                    next_term = (
                        _int_term(elem_spec, i_val + 1)
                        if elem_spec is not None
                        else _term("nat", value=i_val + 1)
                    )
                    iter_env = dict(cur_env)
                    iter_env[var_name] = _Binding(i_term, elem_type)
                    self.mutable_locals.discard(var_name)
                    after_iter, ctrl = self._elaborate_non_returning_block(body_node, iter_env, facts)
                    for k in list(cur_env):
                        if k != var_name and k in after_iter and k in self.mutable_locals:
                            cur_env[k] = after_iter[k]
                    if ctrl == "break":
                        check_env = dict(cur_env)
                        check_env[var_name] = _Binding(i_term, elem_type)
                        self._check_loop_invariants(contracts, check_env, statement, "break")
                        broke = True
                        break
                    check_env = dict(cur_env)
                    check_env[var_name] = _Binding(next_term, elem_type)
                    self._check_loop_invariants(contracts, check_env, statement, "step")
                if not broke:
                    end_env = dict(cur_env)
                    end_env[var_name] = _Binding(end_term, elem_type)
                    proved = self._check_loop_invariants(contracts, end_env, statement, "exit")
                    self.active_facts.extend(proved)
                return cur_env

            # Symbolic range induction
            sym_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in sym_env and mname != var_name:
                    m_ty = sym_env[mname].type
                    sym_env[mname] = _Binding(self.fresh(m_ty), m_ty)
            i_var = self.fresh(elem_type)
            sym_env[var_name] = _Binding(i_var, elem_type)
            ge_op = f"int_ge_{elem_spec.name}" if elem_spec is not None else ">="
            lt_op = f"int_lt_{elem_spec.name}" if elem_spec is not None else "<"
            add_op = f"int_add_{elem_spec.name}" if elem_spec is not None else "+"
            one_term = _int_term(elem_spec, 1) if elem_spec is not None else _term("nat", value=1)
            next_i = _apps(_constant(add_op), i_var, one_term)
            saved_facts_len = len(self.active_facts)
            self.active_facts.append(_apps(_constant(ge_op), i_var, start_term))
            self.active_facts.append(_apps(_constant(lt_op), i_var, end_term))
            assumed = self._assume_loop_invariants(contracts, sym_env)
            self.active_facts.extend(assumed)
            try:
                after_sym, _ = self._elaborate_non_returning_block(body_node, sym_env, facts)
                step_env = dict(sym_env)
                for k in list(sym_env):
                    if k != var_name and k in after_sym and k in self.mutable_locals:
                        step_env[k] = after_sym[k]
                step_env[var_name] = _Binding(next_i, elem_type)
                self._check_loop_invariants(contracts, step_env, statement, "inductive step")
            finally:
                del self.active_facts[saved_facts_len:]
            post_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in post_env and mname != var_name and sym_env[mname].term != after_sym.get(mname, sym_env[mname]).term:
                    m_ty = post_env[mname].type
                    loop_tag = self.serial
                    self.serial += 1
                    post_env[mname] = _Binding(
                        _apps(_constant("LoopState"), m_ty, post_env[mname].term, _term("nat", value=loop_tag)),
                        m_ty,
                    )
            post_env_with_idx = dict(post_env)
            post_env_with_idx[var_name] = _Binding(end_term, elem_type)
            post_assumed = self._assume_loop_invariants(contracts, post_env_with_idx)
            self.active_facts.extend(post_assumed)
            return post_env
        finally:
            self.in_loop_depth -= 1
            self.mutable_locals = saved_mutable

    def _elaborate_foreach_collection_statement(
        self,
        statement: Node,
        extended: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> dict[str, _Binding]:
        self.site = statement
        mode = cast("str", statement["mode"])
        var_name = self.name(statement["name"])
        coll_node = self._unwrap_group(self.node(statement["collection"]))
        if coll_node["kind"] == "range":
            if mode != "value":
                raise self.fail("type", "range iteration only supports 'let' value elements", statement)
            return self._elaborate_foreach_statement(
                {
                    "kind": "foreach",
                    "span": statement["span"],
                    "name": statement["name"],
                    "type": statement["type"],
                    "range": coll_node,
                    "contracts": statement["contracts"],
                    "body": statement["body"],
                },
                extended,
                facts,
            )
        coll_name = self.name(coll_node["name"]) if coll_node["kind"] == "name" else None
        if coll_name is not None and coll_name in self.frozen_collections:
            raise self.fail("type", f"collection '{coll_name}' is already being iterated", coll_node)
        coll_b = self.expression(coll_node, extended)
        if mode == "ref":
            if coll_name is None or coll_name not in self.mutable_locals:
                raise self.fail(
                    "type",
                    "foreach 'ref' element iteration requires a mutable 'var' or 'ref' collection variable",
                    coll_node,
                )
            if self._is_readonly_span(coll_b.term):
                raise self.fail(
                    "type",
                    f"cannot iterate with 'ref' over read-only 'in' parameter '{coll_name}'",
                    coll_node,
                )
        coll_ty = self.whnf(coll_b.type)
        c_head, c_args = self.spine(coll_ty)
        kind_tag = ""
        if c_head == _constant("Span") and len(c_args) == 1 and self.whnf(c_args[0]) == _U8:
            kind_tag = "span"
            elem_type = _U8
            self._check_span_can_read(coll_b.term, extended, coll_node)
            if mode == "ref":
                self._check_span_can_write(coll_b.term, extended, coll_node)
            len_t = self.whnf(_apps(_constant("Span_Length"), _U8, coll_b.term))
            concrete_len = cast("int", len_t.value) if len_t.kind == "int" else None
        elif c_head == _constant("Slots") and len(c_args) == 2:
            kind_tag = "slots"
            elem_type = c_args[0]
            slots_cap = c_args[1]
            can_r = _apps(_constant("Slots_CanRead"), elem_type, slots_cap, coll_b.term)
            if not self._prove_bool_precondition(can_r, extended):
                raise self.fail("type", "cannot prove Slots.CanRead for collection iteration", coll_node)
            if mode == "ref":
                can_w = _apps(_constant("Slots_CanWrite"), elem_type, slots_cap, coll_b.term)
                if not self._prove_bool_precondition(can_w, extended):
                    raise self.fail("type", "cannot prove Slots.CanWrite for 'ref' collection iteration", coll_node)
            live_t = self.whnf(_apps(_constant("Slots_LiveCount"), elem_type, slots_cap, coll_b.term))
            concrete_len = cast("int", live_t.value) if live_t.kind == "int" else None
        elif c_head == _constant("Vec") and len(c_args) == 2:
            kind_tag = "vec"
            elem_type = c_args[0]
            len_t = self.whnf(c_args[1])
            concrete_len = cast("int", len_t.value) if len_t.kind == "nat" else None
        elif c_head == _constant("Seq") and len(c_args) == 1:
            if mode == "ref":
                raise self.fail(
                    "type", "pure sequence 'Seq<T>' does not support mutable 'ref' element iteration", statement
                )
            kind_tag = "seq"
            elem_type = c_args[0]
            cnt_t = self.whnf(_apps(_constant("Seq_Count"), elem_type, coll_b.term))
            concrete_len = cast("int", cnt_t.value) if cnt_t.kind == "nat" else None
        else:
            raise self.fail(
                "type",
                "foreach collection must have type Vec<T, n>, Span<byte>, Slots<T, capacity> or Seq<T>",
                coll_node,
            )
        if statement["type"] is not None:
            ann_type = self.type(self.node(statement["type"]), extended)
            self.unify(elem_type, ann_type)
        contracts = self.nodes(statement["contracts"])
        body_node = self.node(statement["body"], "block")
        saved_mutable = set(self.mutable_locals)
        saved_readonly = set(self.readonly_span_vars)
        if coll_name is not None:
            self.frozen_collections.add(coll_name)
        self.in_loop_depth += 1
        try:
            self._check_loop_invariants(contracts, extended, statement, "entry")
            cur_env = dict(extended)
            if concrete_len is not None and 0 <= concrete_len <= 64:
                cur_coll_term = coll_b.term
                for idx in range(concrete_len):
                    if kind_tag == "span":
                        idx_u = _int_term(_INT_SPECS["usize"], idx)
                        elem_term = self.whnf(_apps(_constant("Span_Read"), _U8, cur_coll_term, idx_u))
                    elif kind_tag == "slots":
                        idx_u = _int_term(_INT_SPECS["usize"], idx)
                        d_val = self._default_term_for_type(elem_type)
                        elem_term = self.whnf(
                            _apps(_constant("Slots_Read"), elem_type, c_args[1], d_val, cur_coll_term, idx_u)
                        )
                    else:
                        seq_m = (
                            self.whnf(_apps(_constant("Vec_Model"), elem_type, c_args[1], cur_coll_term))
                            if kind_tag == "vec"
                            else cur_coll_term
                        )
                        d_val = self._default_term_for_type(elem_type)
                        elem_term = self.whnf(
                            _apps(_constant("Seq_At"), elem_type, d_val, seq_m, _term("nat", value=idx))
                        )
                    iter_env = dict(cur_env)
                    if mode == "ref":
                        self.mutable_locals.add(var_name)
                        iter_env[var_name] = _Binding(elem_term, elem_type)
                    else:
                        self.mutable_locals.discard(var_name)
                        if mode == "in":
                            v_fresh = self.fresh(elem_type)
                            self.readonly_span_vars.add(cast("int", v_fresh.value))
                            iter_env[var_name] = _Binding(elem_term, elem_type)
                        else:
                            iter_env[var_name] = _Binding(elem_term, elem_type)
                    after_iter, ctrl = self._elaborate_non_returning_block(body_node, iter_env, facts)
                    for k in list(cur_env):
                        if k != var_name and k in after_iter and k in self.mutable_locals:
                            cur_env[k] = after_iter[k]
                    if mode == "ref" and coll_name is not None:
                        new_elem = after_iter[var_name].term
                        if kind_tag == "span":
                            idx_u = _int_term(_INT_SPECS["usize"], idx)
                            cur_coll_term = _apps(_constant("Span_Write"), _U8, cur_coll_term, idx_u, new_elem)
                            cur_env[coll_name] = _Binding(cur_coll_term, coll_b.type)
                        elif kind_tag == "slots":
                            idx_u = _int_term(_INT_SPECS["usize"], idx)
                            cur_coll_term = _apps(
                                _constant("Slots_Write"), elem_type, c_args[1], cur_coll_term, idx_u, new_elem
                            )
                            cur_env[coll_name] = _Binding(cur_coll_term, coll_b.type)
                        elif kind_tag == "vec":
                            cur_coll_term = self._update_vec_at(elem_type, cur_coll_term, idx, new_elem)
                            cur_env[coll_name] = _Binding(cur_coll_term, coll_b.type)
                    if ctrl == "break":
                        self._check_loop_invariants(contracts, cur_env, statement, "break")
                        break
                    self._check_loop_invariants(contracts, cur_env, statement, "step")
                return cur_env

            # Symbolic collection iteration
            sym_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in sym_env and mname != var_name and mname != coll_name:
                    m_ty = sym_env[mname].type
                    sym_env[mname] = _Binding(self.fresh(m_ty), m_ty)
            elem_var = self.fresh(elem_type)
            if mode == "ref":
                self.mutable_locals.add(var_name)
            else:
                self.mutable_locals.discard(var_name)
                if mode == "in":
                    self.readonly_span_vars.add(cast("int", elem_var.value))
            sym_env[var_name] = _Binding(elem_var, elem_type)
            saved_facts_len = len(self.active_facts)
            if kind_tag == "span":
                coll_model = self.whnf(_apps(_constant("Span_Model"), _U8, coll_b.term))
            elif kind_tag == "slots":
                coll_model = self.whnf(_apps(_constant("Slots_Model"), elem_type, c_args[1], coll_b.term))
            elif kind_tag == "vec":
                coll_model = self.whnf(_apps(_constant("Vec_Model"), elem_type, c_args[1], coll_b.term))
            else:
                coll_model = self.whnf(coll_b.term)
            for f_term in self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms(facts, extended)]):
                f_head, f_args = self.spine(f_term)
                if f_head == _constant("Seq_All") and len(f_args) == 3 and self.convertible(f_args[1], coll_model):
                    self.active_facts.append(self.whnf(_app(f_args[2], elem_var)))
            assumed = self._assume_loop_invariants(contracts, sym_env)
            self.active_facts.extend(assumed)
            try:
                after_sym, _ = self._elaborate_non_returning_block(body_node, sym_env, facts)
                step_env = dict(sym_env)
                for k in list(sym_env):
                    if k != var_name and k in after_sym and k in self.mutable_locals:
                        step_env[k] = after_sym[k]
                self._check_loop_invariants(contracts, step_env, statement, "inductive step")
            finally:
                del self.active_facts[saved_facts_len:]
            for mname in list(self.mutable_locals):
                if mname in cur_env and mname != var_name and sym_env.get(mname, cur_env[mname]).term != after_sym.get(mname, sym_env.get(mname, cur_env[mname])).term:
                    m_ty = cur_env[mname].type
                    loop_tag = self.serial
                    self.serial += 1
                    cur_env[mname] = _Binding(
                        _apps(_constant("LoopState"), m_ty, cur_env[mname].term, _term("nat", value=loop_tag)),
                        m_ty,
                    )
            post_assumed = self._assume_loop_invariants(contracts, cur_env)
            self.active_facts.extend(post_assumed)
            return cur_env
        finally:
            self.in_loop_depth -= 1
            if coll_name is not None:
                self.frozen_collections.discard(coll_name)
            self.mutable_locals = saved_mutable
            self.readonly_span_vars = saved_readonly

    def _update_vec_at(self, elem_type: _Term, vec_term: _Term, target_idx: int, new_val: _Term) -> _Term:
        v_w = self.whnf(vec_term)
        head, args = self.spine(v_w)
        if head == _constant("VCons") and len(args) == 4:
            if target_idx == 0:
                return _apps(_constant("VCons"), args[0], args[1], new_val, args[3])
            return _apps(
                _constant("VCons"),
                args[0],
                args[1],
                args[2],
                self._update_vec_at(elem_type, args[3], target_idx - 1, new_val),
            )
        return vec_term

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

        def lift_stmt_propagate(
            stmt: Node, field_key: str, idx_stmt: int
        ) -> _Binding | None:
            raw_field = stmt.get(field_key)
            if raw_field is None:
                return None
            split_res = self._split_first_propagate(self.node(raw_field))
            if split_res is None:
                return None
            prop_node, rebuild = split_res
            target_ret = expected if expected is not None else self.current_return_type
            if target_ret is None:
                raise self.fail(
                    "type",
                    "'?' propagation requires an enclosing callable or block returning an Option or Result union",
                    prop_node,
                )
            combined_f = (*active_facts, *statement_facts)
            term = self._elaborate_propagate(
                prop_node,
                extended,
                target_ret,
                lambda temp_name, _ok_b, ok_env: self.block(
                    {
                        "kind": "block",
                        "span": node["span"],
                        "statements": [
                            {
                                **stmt,
                                field_key: rebuild(
                                    {
                                        "kind": "name",
                                        "span": prop_node["span"],
                                        "name": {"text": temp_name, "span": prop_node["span"]},
                                    }
                                ),
                            },
                            *statements[idx_stmt + 1:],
                        ],
                    },
                    ok_env,
                    target_ret,
                    facts=combined_f,
                ).term,
            )
            return finish(_Binding(term, target_ret))

        saved_active_len = len(self.active_facts)
        self.active_facts.extend(self._fact_bool_terms(active_facts, extended))
        try:
            for index, statement in enumerate(statements):
                self.site = statement
                kind = cast("str", statement["kind"])
                if kind in {"let", "typed_local", "let_pattern", "constant_local", "var", "var_pattern"}:
                    if kind != "constant_local":
                        lifted = lift_stmt_propagate(statement, "value", index)
                        if lifted is not None:
                            return lifted
                    previous_keys = set(extended)
                    extended = self.local(statement, extended)
                    for new_key in set(extended) - previous_keys:
                        bound = extended[new_key]
                        if self._is_prop_type(bound.type):
                            statement_facts.append(bound)
                            self.active_facts.extend(self._fact_bool_terms((bound,), extended))
                    continue
                if kind == "assignment":
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
                    extended = self._elaborate_assignment(statement, extended)
                    continue
                if kind == "expression_statement":
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
                    extended = self._elaborate_expression_statement(statement, extended)
                    continue
                if kind == "scope":
                    extended = self._elaborate_scope_statement(
                        statement, extended, (*active_facts, *statement_facts)
                    )
                    continue
                if kind == "foreach":
                    extended = self._elaborate_foreach_statement(
                        statement, extended, (*active_facts, *statement_facts)
                    )
                    continue
                if kind == "foreach_collection":
                    extended = self._elaborate_foreach_collection_statement(
                        statement, extended, (*active_facts, *statement_facts)
                    )
                    continue
                if kind in {"break", "continue"}:
                    raise self.fail("type", f"'{kind}' statement is only permitted inside a loop", statement)
                if kind == "assert":
                    fact = self._elaborate_assert(statement, extended, (*active_facts, *statement_facts))
                    statement_facts.append(fact)
                    self.active_facts.extend(self._fact_bool_terms((fact,), extended))
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
                    self.active_facts.extend(self._fact_bool_terms(sub_facts, extended))
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
                if kind in {"let_else", "var_else"}:
                    if index == len(statements) - 1:
                        raise self.fail(
                            "type",
                            f"a pure block requires an explicit terminal return after {kind.replace('_', '-')}",
                            statement,
                        )
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
                    else_block = self.node(statement["else"], "block")
                    else_statements = self.nodes(else_block["statements"])
                    rest_statements = statements[index + 1:]
                    combined_facts = (*active_facts, *statement_facts)
                    visited_arms: set[int] = set()
                    saved_mut = set(self.mutable_locals)
                    if kind == "var_else":
                        pat_preview = self._parse_pattern(self.node(statement["pattern"]), set())
                        pnames: set[str] = set()
                        self._collect_pat_names(pat_preview, pnames)
                        self.mutable_locals.update(pnames)
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
                    try:
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
                    finally:
                        self.mutable_locals = saved_mut
                    return finish(result)
                if kind == "if" and index < len(statements) - 1:
                    lifted = lift_stmt_propagate(statement, "condition", index)
                    if lifted is not None:
                        return lifted
                    then_node = self.node(statement["then"])
                    then_stmts = (
                        self.nodes(then_node["statements"])
                        if then_node["kind"] == "block"
                        else [then_node]
                    )
                    else_raw = statement["else"]
                    else_stmts = (
                        None
                        if else_raw is None
                        else (
                            self.nodes(self.node(else_raw)["statements"])
                            if self.node(else_raw)["kind"] == "block"
                            else [self.node(else_raw)]
                        )
                    )
                    then_returns = bool(then_stmts and then_stmts[-1]["kind"] == "return")
                    else_returns = bool(else_stmts and else_stmts[-1]["kind"] == "return")
                    if not then_returns and not else_returns:
                        extended, _ = self._elaborate_non_returning_block(
                            {"kind": "block", "span": statement["span"], "statements": [statement]},
                            extended,
                            (*active_facts, *statement_facts),
                        )
                        continue
                    rest_statements = statements[index + 1:]
                    if then_returns and else_stmts is None:
                        cur_stmt: Node = {
                            **statement,
                            "else": {
                                "kind": "block",
                                "span": node["span"],
                                "statements": rest_statements,
                            },
                        }
                    elif then_returns and not else_returns and else_stmts is not None:
                        cur_stmt = {
                            **statement,
                            "else": {
                                "kind": "block",
                                "span": node["span"],
                                "statements": [*else_stmts, *rest_statements],
                            },
                        }
                    elif not then_returns and else_returns:
                        cur_stmt = {
                            **statement,
                            "then": {
                                "kind": "block",
                                "span": node["span"],
                                "statements": [*then_stmts, *rest_statements],
                            },
                        }
                    else:
                        raise self.fail("unsupported", "a returning terminal must be the final statement")
                elif index != len(statements) - 1:
                    raise self.fail("unsupported", "a returning terminal must be the final statement")
                else:
                    cur_stmt = statement
                if kind == "return":
                    if self.active_lift_scopes > 0:
                        raise self.fail(
                            "type",
                            "cannot return from a callable while a record invariant is lifted in an enclosing scope",
                            cur_stmt,
                        )
                    if cur_stmt["value"] is None:
                        value = _Binding(_term("unit"), _UNIT)
                        if expected is not None:
                            self.unify(value.type, expected)
                        self.final_ref_bindings = dict(extended)
                        self.final_return_facts = list(self.active_facts[saved_active_len:])
                        return finish(value)
                    lifted = lift_stmt_propagate(cur_stmt, "value", index)
                    if lifted is not None:
                        return lifted
                    value_node = self.node(cur_stmt["value"])
                    result = (
                        self.expression(value_node, extended)
                        if expected is None
                        else _Binding(self.check(value_node, expected, extended), expected)
                    )
                    self.final_ref_bindings = dict(extended)
                    self.final_return_facts = list(self.active_facts[saved_active_len:])
                    return finish(result)
                if kind == "if":
                    if cur_stmt["else"] is None:
                        raise self.fail("type", "every conditional branch must return")
                    lifted = lift_stmt_propagate(cur_stmt, "condition", index)
                    if lifted is not None:
                        return lifted
                    combined_facts = (*active_facts, *statement_facts)
                    cond_raw = self.node(cur_stmt["condition"])
                    cond_unwrapped = self._unwrap_group(cond_raw)
                    if cond_unwrapped["kind"] == "is":
                        return finish(
                            self._if_is(
                                cond_unwrapped,
                                self.node(cur_stmt["then"]),
                                self.node(cur_stmt["else"]),
                                extended,
                                expected,
                                expression_branches=False,
                                facts=combined_facts,
                                site_node=cur_stmt,
                            )
                        )
                    condition = self.check(cond_raw, _BOOL, extended)
                    self.active_facts.append(condition)
                    try:
                        yes = self.branch(self.node(cur_stmt["then"]), extended, expected, facts=combined_facts)
                        yes_refs = dict(self.final_ref_bindings)
                    finally:
                        self.active_facts.pop()
                    self.active_facts.append(_app(_constant("!"), condition))
                    try:
                        no = self.branch(self.node(cur_stmt["else"]), extended, yes.type, facts=combined_facts)
                        no_refs = dict(self.final_ref_bindings)
                    finally:
                        self.active_facts.pop()
                    merged_refs = dict(extended)
                    for rk in set(yes_refs) & set(no_refs):
                        yb = yes_refs[rk]
                        nb = no_refs[rk]
                        if yb.term != nb.term:
                            merged_refs[rk] = _Binding(
                                self.whnf(_term("if", yb.type, condition, yb.term, nb.term)),
                                yb.type,
                            )
                        else:
                            merged_refs[rk] = yb
                    self.final_ref_bindings = merged_refs
                    return finish(_Binding(_term("if", yes.type, condition, yes.term, no.term), yes.type))
                if kind == "match":
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
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
            if (
                statements
                and statements[-1]["kind"]
                in {"assignment", "expression_statement", "scope", "foreach", "foreach_collection"}
                and expected is not None
                and self.whnf(expected) == _UNIT
            ):
                self.final_ref_bindings = dict(extended)
                return finish(_Binding(_term("unit"), _UNIT))
            raise self.fail("type", "a pure block requires an explicit terminal return", node)
        finally:
            del self.active_facts[saved_active_len:]

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
        if head == _constant("Span") and len(type_args) == 1 and self.whnf(type_args[0]) == _U8:
            if member_name == "Model":
                self._check_span_can_read(receiver.term, {}, node)
                return _Binding(
                    _apps(_constant("Span_Model"), _U8, receiver.term),
                    _app(_constant("Seq"), _U8),
                )
            span_props: dict[str, tuple[str, _Term]] = {
                "Base": ("Span_Base", _USIZE),
                "Length": ("Span_Length", _USIZE),
                "Tag": ("Span_Tag", _BOOL),
                "PermRead": ("Span_PermRead", _BOOL),
                "PermWrite": ("Span_PermWrite", _BOOL),
                "CanRead": ("Span_CanRead", _BOOL),
                "CanWrite": ("Span_CanWrite", _BOOL),
            }
            if member_name not in span_props:
                raise self.fail("name", f"Span<byte> has no property '{member_name}'", node)
            const_name, prop_ty = span_props[member_name]
            return _Binding(_apps(_constant(const_name), _U8, receiver.term), prop_ty)
        if head == _constant("Vec") and len(type_args) == 2:
            if member_name == "Model":
                return _Binding(
                    _apps(_constant("Vec_Model"), type_args[0], type_args[1], receiver.term),
                    _app(_constant("Seq"), type_args[0]),
                )
            if member_name == "Count":
                return _Binding(type_args[1], _NAT)
            raise self.fail("name", f"Vec has no property '{member_name}'", node)
        if head == _constant("Seq") and len(type_args) == 1:
            if member_name == "Count":
                return _Binding(_apps(_constant("Seq_Count"), type_args[0], receiver.term), _NAT)
            if member_name == "Model":
                return receiver
            raise self.fail("name", f"Seq has no property '{member_name}'", node)
        if head == _constant("Slots") and len(type_args) == 2:
            elem_t, cap_t = type_args[0], type_args[1]
            if member_name == "Capacity":
                cap_w = self.whnf(cap_t)
                if cap_w.kind == "nat":
                    return _Binding(_int_term(_INT_SPECS["usize"], cast("int", cap_w.value)), _USIZE)
                return _Binding(cap_t, _NAT)
            if member_name == "Model":
                return _Binding(
                    _apps(_constant("Slots_Model"), elem_t, cap_t, receiver.term),
                    _app(_constant("Seq"), elem_t),
                )
            slots_props: dict[str, tuple[str, _Term]] = {
                "Base": ("Slots_Base", _USIZE),
                "LiveCount": ("Slots_LiveCount", _USIZE),
                "Tag": ("Slots_Tag", _BOOL),
                "PermRead": ("Slots_PermRead", _BOOL),
                "PermWrite": ("Slots_PermWrite", _BOOL),
                "CanRead": ("Slots_CanRead", _BOOL),
                "CanWrite": ("Slots_CanWrite", _BOOL),
            }
            if member_name not in slots_props:
                raise self.fail("name", f"Slots has no property '{member_name}'", node)
            const_name, prop_ty = slots_props[member_name]
            return _Binding(_apps(_constant(const_name), elem_t, cap_t, receiver.term), prop_ty)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
            raise self.fail(
                "unsupported",
                "member projection requires a record receiver, a Format.Write call or the full frontend",
                node,
            )
        record_info = self.records_by_type[head.value]
        for idx, rf in enumerate(record_info.fields):
            if rf.name == member_name:
                ftype = self._instantiate_record_field_type(record_info, type_args, idx, receiver.term)
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
            for j in range(idx):
                ftype = self.substitute(ftype, cast("int", record_info.fields[j].var.value), final_fields[j])
            if idx in update_by_index:
                u_node = update_by_index[idx]
                final_fields.append(self.check(self.node(u_node["value"]), ftype, environment))
            else:
                old_ftype = self._instantiate_record_field_type(record_info, type_args, idx, base.term)
                if not self._try_unify(old_ftype, ftype):
                    raise self.fail(
                        "type",
                        f"record update changes an index that field '{rf.name}' depends on; update '{rf.name}' as well",
                        node,
                    )
                final_fields.append(_apps(_constant(rf.proj_const), *type_args, base.term))
        result_term = _apps(_constant(record_info.ctor_const), *type_args, *final_fields)
        result_type = _apps(_constant(record_info.type_const), *type_args)
        if expected is not None:
            self.unify(result_type, expected)
        base_unwrapped = self._unwrap_group(base_node)
        base_name = self.name(base_unwrapped["name"]) if base_unwrapped["kind"] == "name" else None
        assign_target = getattr(self, "_in_lifted_target_assignment", None)
        excluded = (
            self.lifted_invariants.get(base_name, set())
            if base_name is not None and base_name == assign_target
            else set()
        )
        self._check_record_invariants(
            record_info, type_args, result_term, environment, node, exclude_clauses=excluded
        )
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

    def _parse_hole_ast(self, start_byte: int, end_byte: int, container: Node) -> Node:
        src = self.protocol.source
        raw_expr = src[start_byte:end_byte].decode("utf-8", errors="replace").strip()
        tokens: list[tuple[str, str, int, int]] = []
        cursor = trivia_end(src, start_byte, block_comments=True)
        multi_ops = (b"<==>", b"==>", b"::<", b"==", b"!=", b"<=", b">=", b"&&", b"||")
        single_ops = set(b"(){}[].,:=+-*/%<>!&|^~?")
        while cursor < end_byte:
            matched_multi = False
            for op in multi_ops:
                if src[cursor:cursor + len(op)] == op and cursor + len(op) <= end_byte:
                    tokens.append(("punct", op.decode("ascii"), cursor, cursor + len(op)))
                    cursor = trivia_end(src, cursor + len(op), block_comments=True)
                    matched_multi = True
                    break
            if matched_multi:
                continue
            byte0 = src[cursor]
            if byte0 in single_ops and not (
                byte0 == ord("?")
                and cursor + 1 < end_byte
                and (
                    ord("A") <= src[cursor + 1] <= ord("Z")
                    or ord("a") <= src[cursor + 1] <= ord("z")
                    or src[cursor + 1] == ord("_")
                )
            ):
                tokens.append(("punct", chr(byte0), cursor, cursor + 1))
                cursor = trivia_end(src, cursor + 1, block_comments=True)
                continue
            if byte0 == ord('"'):
                end = cursor + 1
                while end < end_byte and src[end] != ord('"'):
                    if src[end] == ord("\\"):
                        end += 2
                    else:
                        end += 1
                if end >= end_byte or src[end] != ord('"'):
                    raise self.fail("syntax", "unterminated string literal in interpolation hole", container)
                end += 1
                tokens.append(("string", src[cursor:end].decode("utf-8"), cursor, end))
                cursor = trivia_end(src, end, block_comments=True)
                continue
            if ord("0") <= byte0 <= ord("9"):
                end = cursor + 1
                while end < end_byte and (
                    ord("0") <= src[end] <= ord("9")
                    or ord("A") <= src[end] <= ord("Z")
                    or ord("a") <= src[end] <= ord("z")
                    or src[end] == ord("_")
                ):
                    end += 1
                token_str = src[cursor:end].decode("ascii")
                split_at = len(token_str)
                for sfx in ("usize", "byte", "u16", "u32", "u64", "i16", "i32", "i64", "u8", "i8"):
                    if token_str.endswith(sfx) and len(token_str) > len(sfx):
                        candidate_mag = token_str[:-len(sfx)]
                        if (
                            DECIMAL.fullmatch(candidate_mag)
                            or _HEX_LITERAL.fullmatch(candidate_mag)
                            or _BIN_LITERAL.fullmatch(candidate_mag)
                        ):
                            split_at = len(candidate_mag)
                            break
                else:
                    if not (
                        _HEX_LITERAL.fullmatch(token_str)
                        or _BIN_LITERAL.fullmatch(token_str)
                    ):
                        for idx_ch, ch in enumerate(token_str):
                            if not (ch.isdigit() or ch == "_"):
                                split_at = idx_ch
                                break
                tokens.append(("nat", f"{token_str[:split_at]}:{token_str[split_at:]}", cursor, end))
                cursor = trivia_end(src, end, block_comments=True)
                continue
            if (
                ord("A") <= byte0 <= ord("Z")
                or ord("a") <= byte0 <= ord("z")
                or byte0 in {ord("_"), ord("?")}
            ):
                end = cursor + 1
                if byte0 == ord("?") and (
                    end >= end_byte
                    or not (
                        ord("A") <= src[end] <= ord("Z")
                        or ord("a") <= src[end] <= ord("z")
                        or src[end] == ord("_")
                    )
                ):
                    raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
                while end < end_byte and (
                    ord("0") <= src[end] <= ord("9")
                    or ord("A") <= src[end] <= ord("Z")
                    or ord("a") <= src[end] <= ord("z")
                    or src[end] == ord("_")
                ):
                    end += 1
                tokens.append(("ident", src[cursor:end].decode("ascii"), cursor, end))
                cursor = trivia_end(src, end, block_comments=True)
                continue
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)

        if not tokens:
            raise self.fail("syntax", "empty interpolation hole in format template", container)

        pos = 0

        def peek() -> tuple[str, str, int, int] | None:
            return tokens[pos] if pos < len(tokens) else None

        def consume(expected_kind: str | None = None, expected_text: str | None = None) -> tuple[str, str, int, int]:
            nonlocal pos
            tok = peek()
            if tok is None or (expected_kind is not None and tok[0] != expected_kind) or (
                expected_text is not None and tok[1] != expected_text
            ):
                raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
            pos += 1
            return tok

        def has_generic_call_ahead(start_idx: int) -> bool:
            depth = 0
            idx = start_idx
            while idx < len(tokens):
                tk, tv, _, _ = tokens[idx]
                if tk == "punct" and tv in {"<", ":: <", "::<"}:
                    depth += 1
                elif tk == "punct" and tv == ">":
                    depth -= 1
                    if depth == 0:
                        return idx + 1 < len(tokens) and tokens[idx + 1][0] == "punct" and tokens[idx + 1][1] == "("
                elif tk == "punct" and tv in {";", "{", "}"}:
                    return False
                idx += 1
            return False

        def is_tok(kind: str, val: str | None = None) -> bool:
            t = peek()
            return t is not None and t[0] == kind and (val is None or t[1] == val)

        def parse_type_node() -> Node:
            t_tok = consume("ident")
            name_node: Node = {"text": t_tok[1], "span": [t_tok[2], t_tok[3]]}
            args: list[Node] = []
            end_b = t_tok[3]
            if is_tok("punct", "<"):
                consume("punct", "<")
                while True:
                    if is_tok("nat"):
                        ntok = consume("nat")
                        v_str, s_str = ntok[1].split(":", 1)
                        args.append({"kind": "nat", "span": [ntok[2], ntok[3]], "value": v_str, "suffix": s_str})
                    else:
                        args.append(parse_type_node())
                    if is_tok("punct", ","):
                        consume("punct", ",")
                        if is_tok("punct", ">"):
                            break
                    else:
                        break
                gt_tok = consume("punct", ">")
                end_b = gt_tok[3]
            return {"kind": "type", "span": [t_tok[2], end_b], "name": name_node, "arguments": args}

        def parse_pattern_node() -> Node:
            ptok = peek()
            if ptok is None:
                raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
            if ptok[0] == "ident" and ptok[1] == "_":
                consume("ident", "_")
                return {"kind": "wildcard_pattern", "span": [ptok[2], ptok[3]]}
            if ptok[0] == "ident" and ptok[1] in {"true", "false"}:
                consume("ident")
                return {"kind": "bool_pattern", "span": [ptok[2], ptok[3]], "value": ptok[1] == "true"}
            if ptok[0] == "nat":
                consume("nat")
                v_str, s_str = ptok[1].split(":", 1)
                return {"kind": "nat_pattern", "span": [ptok[2], ptok[3]], "value": v_str, "suffix": s_str}
            if ptok[0] == "ident":
                consume("ident")
                ident_node: Node = {"text": ptok[1], "span": [ptok[2], ptok[3]]}
                if is_tok("punct", "("):
                    consume("punct", "(")
                    pargs: list[Node] = []
                    if peek() is not None and not is_tok("punct", ")"):
                        while True:
                            if (
                                pos + 1 < len(tokens)
                                and tokens[pos][0] == "ident"
                                and tokens[pos + 1][0] == "punct"
                                and tokens[pos + 1][1] == ":"
                            ):
                                ltok = consume("ident")
                                consume("punct", ":")
                                inner_p = parse_pattern_node()
                                inner_end = cast("list[int]", inner_p["span"])[1]
                                pargs.append(
                                    {
                                        "kind": "labeled_pattern",
                                        "span": [ltok[2], inner_end],
                                        "label": {"text": ltok[1], "span": [ltok[2], ltok[3]]},
                                        "pattern": inner_p,
                                    }
                                )
                            else:
                                pargs.append(parse_pattern_node())
                            if is_tok("punct", ","):
                                consume("punct", ",")
                                if is_tok("punct", ")"):
                                    break
                            else:
                                break
                    rp = consume("punct", ")")
                    return {
                        "kind": "constructor_pattern",
                        "span": [ptok[2], rp[3]],
                        "name": ident_node,
                        "arguments": pargs,
                    }
                return {"kind": "binding_pattern", "span": [ptok[2], ptok[3]], "name": ident_node}
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)

        def parse_primary() -> Node:
            tok = peek()
            if tok is None:
                raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
            tk, tv, ts, te = tok
            if tk == "ident" and tv == "if":
                consume("ident", "if")
                consume("punct", "(")
                cond = parse_expr()
                consume("punct", ")")
                yes = parse_expr()
                consume("ident", "else")
                no = parse_expr()
                no_end = cast("list[int]", no["span"])[1]
                return {
                    "kind": "if_expression",
                    "span": [ts, no_end],
                    "condition": cond,
                    "then": yes,
                    "else": no,
                }
            if tk == "ident" and tv in {"true", "false"}:
                consume("ident")
                return {"kind": "bool", "span": [ts, te], "value": tv == "true"}
            if tk == "nat":
                consume("nat")
                v_str, s_str = tv.split(":", 1)
                return {"kind": "nat", "span": [ts, te], "value": v_str, "suffix": s_str}
            if tk == "string":
                consume("string")
                return {"kind": "string", "span": [ts, te], "value": tv}
            if tk == "punct" and tv == "(":
                consume("punct", "(")
                if is_tok("punct", ")"):
                    rp = consume("punct", ")")
                    return {"kind": "unit", "span": [ts, rp[3]]}
                first = parse_expr()
                if is_tok("punct", ","):
                    items = [first]
                    while is_tok("punct", ","):
                        consume("punct", ",")
                        items.append(parse_expr())
                    rp = consume("punct", ")")
                    return {"kind": "tuple", "span": [ts, rp[3]], "values": items}
                rp = consume("punct", ")")
                return {"kind": "group", "span": [ts, rp[3]], "value": first}
            if tk == "ident":
                consume("ident")
                kind_name = "hole" if tv.startswith("?") else "name"
                return {"kind": kind_name, "span": [ts, te], "name": {"text": tv, "span": [ts, te]}}
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)

        def parse_postfix() -> Node:
            node: Node = parse_primary()
            while True:
                nxt = peek()
                if nxt is None:
                    break
                nk, nv, _, _ = nxt
                node_start = cast("list[int]", node["span"])[0]
                if nk == "punct" and nv == ".":
                    consume("punct", ".")
                    mtok = consume("ident")
                    node = {
                        "kind": "member",
                        "span": [node_start, mtok[3]],
                        "value": node,
                        "name": {"text": mtok[1], "span": [mtok[2], mtok[3]]},
                    }
                    continue
                if nk == "punct" and (
                    nv == "::<" or (nv == "<" and node["kind"] == "name" and has_generic_call_ahead(pos))
                ):
                    consume("punct")
                    gargs: list[Node] = []
                    while True:
                        if is_tok("nat"):
                            ntok = consume("nat")
                            v_str, s_str = ntok[1].split(":", 1)
                            gargs.append(
                                {"kind": "nat", "span": [ntok[2], ntok[3]], "value": v_str, "suffix": s_str}
                            )
                        else:
                            gargs.append(parse_type_node())
                        if is_tok("punct", ","):
                            consume("punct", ",")
                            if is_tok("punct", ">"):
                                break
                        else:
                            break
                    gt_tok = consume("punct", ">")
                    node = {
                        "kind": "generic_application",
                        "span": [node_start, gt_tok[3]],
                        "value": node,
                        "arguments": gargs,
                    }
                    continue
                if nk == "punct" and nv == "(":
                    consume("punct", "(")
                    cargs: list[Node] = []
                    if peek() is not None and not is_tok("punct", ")"):
                        while True:
                            if (
                                pos + 1 < len(tokens)
                                and tokens[pos][0] == "ident"
                                and tokens[pos + 1][0] == "punct"
                                and tokens[pos + 1][1] == ":"
                            ):
                                ltok = consume("ident")
                                consume("punct", ":")
                                val_node = parse_expr()
                                val_end = cast("list[int]", val_node["span"])[1]
                                cargs.append(
                                    {
                                        "kind": "argument",
                                        "span": [ltok[2], val_end],
                                        "label": {"text": ltok[1], "span": [ltok[2], ltok[3]]},
                                        "value": val_node,
                                    }
                                )
                            else:
                                val_node = parse_expr()
                                val_span = cast("list[int]", val_node["span"])
                                cargs.append(
                                    {
                                        "kind": "argument",
                                        "span": [val_span[0], val_span[1]],
                                        "label": None,
                                        "value": val_node,
                                    }
                                )
                            if is_tok("punct", ","):
                                consume("punct", ",")
                                if is_tok("punct", ")"):
                                    break
                            else:
                                break
                    rp = consume("punct", ")")
                    node = {"kind": "call", "span": [node_start, rp[3]], "callee": node, "arguments": cargs}
                    continue
                if nk == "ident" and nv == "with":
                    consume("ident", "with")
                    consume("punct", "{")
                    updates: list[Node] = []
                    while peek() is not None and not is_tok("punct", "}"):
                        ftok = consume("ident")
                        consume("punct", "=")
                        fval = parse_expr()
                        fval_end = cast("list[int]", fval["span"])[1]
                        updates.append(
                            {
                                "kind": "field_update",
                                "span": [ftok[2], fval_end],
                                "name": {"text": ftok[1], "span": [ftok[2], ftok[3]]},
                                "value": fval,
                            }
                        )
                        if is_tok("punct", ","):
                            consume("punct", ",")
                        else:
                            break
                    rb = consume("punct", "}")
                    node = {
                        "kind": "with_expression",
                        "span": [node_start, rb[3]],
                        "value": node,
                        "updates": updates,
                    }
                    continue
                if nk == "ident" and nv == "is":
                    consume("ident", "is")
                    pat_node = parse_pattern_node()
                    pat_end = cast("list[int]", pat_node["span"])[1]
                    node = {"kind": "is", "span": [node_start, pat_end], "value": node, "pattern": pat_node}
                    continue
                if nk == "punct" and nv == "?":
                    qtok = consume("punct", "?")
                    node = {"kind": "try", "span": [node_start, qtok[3]], "value": node}
                    continue
                break
            return node

        def parse_unary() -> Node:
            tok = peek()
            if tok is not None and (
                (tok[0] == "punct" and tok[1] in {"!", "-", "~"})
                or (tok[0] == "ident" and tok[1] == "ref")
            ):
                consume()
                operand = parse_unary()
                op_end = cast("list[int]", operand["span"])[1]
                return {
                    "kind": "unary",
                    "span": [tok[2], op_end],
                    "operator": {"text": tok[1], "span": [tok[2], tok[3]]},
                    "value": operand,
                }
            return parse_postfix()

        def parse_bin(next_fn: Callable[[], Node], ops: set[str], *, right_assoc: bool = False) -> Node:
            left: Node = next_fn()
            while True:
                cur_op = peek()
                if cur_op is None or cur_op[0] != "punct" or cur_op[1] not in ops:
                    break
                op_tok = consume("punct")
                right = parse_bin(next_fn, ops, right_assoc=True) if right_assoc else next_fn()
                left_start = cast("list[int]", left["span"])[0]
                right_end = cast("list[int]", right["span"])[1]
                left = {
                    "kind": "binary",
                    "span": [left_start, right_end],
                    "operator": {"text": op_tok[1], "span": [op_tok[2], op_tok[3]]},
                    "left": left,
                    "right": right,
                }
            return left

        def parse_mul() -> Node:
            return parse_bin(parse_unary, {"*", "/", "%"})

        def parse_add() -> Node:
            return parse_bin(parse_mul, {"+", "-"})

        def parse_cmp() -> Node:
            return parse_bin(parse_add, {"<", "<=", ">", ">="})

        def parse_eq() -> Node:
            return parse_bin(parse_cmp, {"==", "!="})

        def parse_bitand() -> Node:
            return parse_bin(parse_eq, {"&"})

        def parse_bitxor() -> Node:
            return parse_bin(parse_bitand, {"^"})

        def parse_bitor() -> Node:
            return parse_bin(parse_bitxor, {"|"})

        def parse_and() -> Node:
            return parse_bin(parse_bitor, {"&&"})

        def parse_or() -> Node:
            return parse_bin(parse_and, {"||"})

        def parse_expr() -> Node:
            return parse_bin(parse_or, {"==>", "<==>"}, right_assoc=True)

        ast_node = parse_expr()
        if pos != len(tokens):
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
        self.protocol.visit(ast_node, (start_byte, end_byte))
        return ast_node

    def _check_hole_target_alias(self, node: Node, target_name: str) -> None:
        kind = node["kind"]
        if kind == "name":
            if self.name(node["name"]) == target_name:
                raise self.fail(
                    "type",
                    f"Format.Write hole cannot alias or read target buffer '{target_name}'",
                    node,
                )
            return
        if kind in {"group", "unary", "member", "is", "generic_application"}:
            self._check_hole_target_alias(self.node(node["value"]), target_name)
            return
        if kind == "binary":
            self._check_hole_target_alias(self.node(node["left"]), target_name)
            self._check_hole_target_alias(self.node(node["right"]), target_name)
            return
        if kind == "if_expression":
            self._check_hole_target_alias(self.node(node["condition"]), target_name)
            self._check_hole_target_alias(self.node(node["then"]), target_name)
            self._check_hole_target_alias(self.node(node["else"]), target_name)
            return
        if kind == "tuple":
            for item in self.nodes(node["values"]):
                self._check_hole_target_alias(item, target_name)
            return
        if kind == "call":
            self._check_hole_target_alias(self.node(node["callee"]), target_name)
            for arg_node in self.nodes(node["arguments"]):
                self._check_hole_target_alias(self.node(arg_node["value"]), target_name)
            return
        if kind == "with_expression":
            self._check_hole_target_alias(self.node(node["value"]), target_name)
            for upd_node in self.nodes(node["updates"]):
                self._check_hole_target_alias(self.node(upd_node["value"]), target_name)
            return

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
            hint = ""
            if target_arg["kind"] == "name":
                tname = self.name(target_arg["name"])
                t_err = self.protocol.error("type", "", target_arg)
                assist_loan_argument(self.protocol.source, t_err.line, t_err.column, "ref")
                hint = f"; write 'ref {tname}'"
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
        body_start_byte = cast("list[int]", template_arg["span"])[0] + 2
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
                scan = index + 1
                brace_depth = 1
                paren_depth = 0
                bracket_depth = 0
                in_quote = False
                colon_index: int | None = None
                while scan < len(body) and brace_depth > 0:
                    c_scan = body[scan]
                    if in_quote:
                        if c_scan == "\\":
                            scan += 2
                            continue
                        if c_scan == '"':
                            in_quote = False
                        scan += 1
                        continue
                    if c_scan == '"':
                        in_quote = True
                    elif c_scan == "{":
                        brace_depth += 1
                    elif c_scan == "}":
                        brace_depth -= 1
                        if brace_depth == 0:
                            break
                    elif c_scan == "(":
                        paren_depth += 1
                    elif c_scan == ")":
                        paren_depth = max(0, paren_depth - 1)
                    elif c_scan == "[":
                        bracket_depth += 1
                    elif c_scan == "]":
                        bracket_depth = max(0, bracket_depth - 1)
                    elif (
                        c_scan == ":"
                        and brace_depth == 1
                        and paren_depth == 0
                        and bracket_depth == 0
                        and not (scan + 1 < len(body) and body[scan + 1] == ":")
                        and not (scan > index + 1 and body[scan - 1] == ":")
                    ):
                        colon_index = scan
                    scan += 1
                if brace_depth != 0:
                    raise self.fail("syntax", "unterminated interpolation hole in format template", template_arg)
                end = scan
                raw_start = index + 1
                raw_end = colon_index if colon_index is not None else end
                spec = body[colon_index + 1:end].strip() if colon_index is not None else ""
                expr_byte_start = body_start_byte + len(body[:raw_start].encode("utf-8"))
                expr_byte_end = body_start_byte + len(body[:raw_end].encode("utf-8"))
                hole_ast = self._parse_hole_ast(expr_byte_start, expr_byte_end, template_arg)
                if target_name is not None:
                    self._check_hole_target_alias(hole_ast, target_name)
                hole_binding = self.expression(hole_ast, environment)
                if builder.term.kind == "var" and cast("int", builder.term.value) in self.free(hole_binding.term):
                    raise self.fail(
                        "type",
                        f"Format.Write hole cannot alias or read target buffer '{target_name or 'target'}'",
                        hole_ast,
                    )
                hole_type = self.whnf(hole_binding.type)
                head, type_args = self.spine(hole_type)
                hole_int_spec = self._int_spec(hole_type)
                if hole_type == _NAT or hole_int_spec is not None:
                    if spec not in {"", "d", "x", "x2", "x4", "x8", "X", "X2", "X4", "X8", "b"}:
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for Nat hole", template_arg
                        )
                    val = self.whnf(hole_binding.term)
                    if val.kind in {"nat", "int"}:
                        n_val = cast("int", val.value)
                        if spec in {"", "d"}:
                            concrete_bytes += len(str(n_val))
                        elif n_val < 0:
                            raise self.fail(
                                "type",
                                f"format specifier '{spec}' requires a non-negative integer value",
                                template_arg,
                            )
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
                    elif spec in {"x2", "X2", "x4", "X4", "x8", "X8"} and (
                        hole_int_spec is None or not hole_int_spec.signed
                    ):
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

    def _fact_bool_terms(self, facts: tuple[_Binding, ...] | list[_Binding], environment: dict[str, _Binding]) -> list[_Term]:
        terms: list[_Term] = []
        all_bindings = [
            *facts,
            *(
                b
                for b in environment.values()
                if (self.current_rec_var is None or b.term != self.current_rec_var)
                and self._is_prop_type(b.type)
            ),
        ]
        for fact in all_bindings:
            extracted = self._extract_equality(fact.type)
            if extracted is not None:
                eq_type, u, v = extracted
                eq_type_w = self.whnf(eq_type)
                if eq_type_w == _BOOL:
                    u_w = self.whnf(u)
                    v_w = self.whnf(v)
                    if v_w == _term("bool", value=1):
                        terms.append(u)
                    elif u_w == _term("bool", value=1):
                        terms.append(v)
                    elif v_w == _term("bool", value=0):
                        terms.append(_app(_constant("!"), u))
                    elif u_w == _term("bool", value=0):
                        terms.append(_app(_constant("!"), v))
                elif self._int_spec(eq_type_w) is not None or eq_type_w == _NAT:
                    spec = self._int_spec(eq_type_w)
                    eq_const = f"int_eq_{spec.name}" if spec is not None else "eq_nat"
                    terms.append(_apps(_constant(eq_const), u, v))
        for vname, b in environment.items():
            if self.current_rec_var is not None and b.term == self.current_rec_var:
                continue
            r_head, r_targs = self.spine(self.whnf(b.type))
            if (
                r_head.kind == "const"
                and isinstance(r_head.value, str)
                and r_head.value in self.records_by_type
            ):
                rinfo = self.records_by_type[r_head.value]
                lifted = self.lifted_invariants.get(vname, set())
                for inv in rinfo.invariants:
                    if inv.name in lifted:
                        continue
                    inst_ty = self._instantiate_record_type(rinfo, r_targs, inv.type)
                    inst_ty = self.substitute(inst_ty, cast("int", inv.self_var.value), b.term)
                    if self.whnf(inst_ty) == _BOOL:
                        inst_t = self._instantiate_record_type(rinfo, r_targs, inv.term)
                        inst_t = self.substitute(inst_t, cast("int", inv.self_var.value), b.term)
                        terms.append(inst_t)
        return terms

    def _negate_bool_term(self, term: _Term) -> _Term:
        w = self.whnf(term)
        head, args = self.spine(w)
        if head == _constant("!") and len(args) == 1:
            return args[0]
        if head.kind == "const" and isinstance(head.value, str) and len(args) == 2:
            cname = head.value
            flip_nat = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "eq_nat": "ne_nat", "ne_nat": "eq_nat"}
            if cname in flip_nat:
                return _apps(_constant(flip_nat[cname]), args[0], args[1])
            if cname.startswith("int_"):
                prefix, spec_name = cname.rsplit("_", 1)
                if spec_name in _INT_SPECS:
                    op = prefix[4:]
                    flip_int = {"lt": "ge", "le": "gt", "gt": "le", "ge": "lt", "eq": "ne", "ne": "eq"}
                    if op in flip_int:
                        return _apps(_constant(f"int_{flip_int[op]}_{spec_name}"), args[0], args[1])
        return _app(_constant("!"), w)

    def _expand_bool_facts(self, raw_facts: list[_Term]) -> list[_Term]:
        expanded: list[_Term] = []
        queue = list(raw_facts)
        while queue:
            item = self.whnf(queue.pop(0))
            if item.kind == "if" and len(item.args) == 4:
                cond_t = item.args[1]
                then_w = self.whnf(item.args[2])
                else_w = self.whnf(item.args[3])
                if then_w == _term("bool", value=0):
                    queue.append(self._negate_bool_term(cond_t))
                    queue.append(else_w)
                    continue
                if else_w == _term("bool", value=0):
                    queue.append(cond_t)
                    queue.append(then_w)
                    continue
            head, args = self.spine(item)
            if head == _constant("&&") and len(args) == 2:
                queue.append(args[0])
                queue.append(args[1])
                continue
            if head == _constant("!") and len(args) == 1:
                inner = self.whnf(args[0])
                i_head, i_args = self.spine(inner)
                if i_head == _constant("||") and len(i_args) == 2:
                    queue.append(self._negate_bool_term(i_args[0]))
                    queue.append(self._negate_bool_term(i_args[1]))
                    continue
                neg = self._negate_bool_term(inner)
                if neg != item:
                    queue.append(neg)
                    continue
            if item not in expanded:
                expanded.append(item)
                if head == _constant("Slots_LivePrefix") and len(args) == 4:
                    elem, cap, s, cnt = args
                    queue.append(_apps(_constant("Slots_CanRead"), elem, cap, s))
                    if not self._is_readonly_span(s):
                        queue.append(_apps(_constant("Slots_CanWrite"), elem, cap, s))
                    queue.append(_apps(_constant("int_eq_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), cnt))
                    queue.append(_apps(_constant("int_le_usize"), cnt, self._slots_cap_usize_term(cap)))
                elif head == _constant("Slots_VacantRange") and len(args) == 5:
                    elem, cap, s, start, end = args
                    queue.append(_apps(_constant("Slots_CanWrite"), elem, cap, s))
                    queue.append(_apps(_constant("Slots_CanRead"), elem, cap, s))
                    queue.append(_apps(_constant("int_le_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), start))
                    queue.append(_apps(_constant("int_le_usize"), start, end))
                    queue.append(_apps(_constant("int_le_usize"), end, self._slots_cap_usize_term(cap)))
                elif head == _constant("Slots_CanWrite") and len(args) == 3:
                    queue.append(_apps(_constant("Slots_CanRead"), args[0], args[1], args[2]))
        changed = True
        while changed:
            changed = False
            for f_item in list(expanded):
                fh, fa = self.spine(f_item)
                if fh == _constant("==>") and len(fa) == 2:
                    ant = self.whnf(fa[0])
                    con = self.whnf(fa[1])
                    if ant in expanded and con not in expanded:
                        expanded.append(con)
                        changed = True
        return expanded

    def _parse_cmp_fact(self, fact: _Term) -> tuple[str, _IntSpec | None, _Term, _Term] | None:
        w = self.whnf(fact)
        head, args = self.spine(w)
        if head.kind != "const" or not isinstance(head.value, str) or len(args) != 2:
            return None
        cname = head.value
        nat_map = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge", "eq_nat": "eq", "ne_nat": "ne"}
        if cname in nat_map:
            return nat_map[cname], None, args[0], args[1]
        if cname.startswith("int_"):
            prefix, spec_name = cname.rsplit("_", 1)
            spec = _INT_SPECS.get(spec_name)
            op = prefix[4:]
            if spec is not None and op in {"lt", "le", "gt", "ge", "eq", "ne"}:
                return op, spec, args[0], args[1]
        return None

    def _term_bounds(
        self,
        term: _Term,
        spec: _IntSpec | None,
        facts: list[_Term],
        depth: int = 0,
        visited: frozenset[_Term] = frozenset(),
    ) -> tuple[int, int, set[int]]:
        lo = spec.min_val if spec is not None else 0
        hi = spec.max_val if spec is not None else (1 << MAX_NAT_BITS) - 1
        ne_set: set[int] = set()
        w = self.whnf(term)
        if w.kind in {"int", "nat"}:
            val = cast("int", w.value)
            return val, val, set()
        if depth > 2 or w in visited:
            return lo, hi, ne_set
        next_visited = visited | {w}
        head, args = self.spine(w)
        if head.kind == "const" and isinstance(head.value, str):
            cname = head.value
            if cname == "Succ" and len(args) == 1:
                s_lo, s_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                lo = max(lo, s_lo + 1)
                hi = min(hi, s_hi + 1)
            elif cname.startswith("int_from_") and len(args) == 1:
                src_spec = _INT_SPECS[cname.split("_")[2]]
                s_lo, s_hi, s_ne = self._term_bounds(args[0], src_spec, facts, depth + 1, next_visited)
                lo = max(lo, s_lo)
                hi = min(hi, s_hi)
                ne_set.update(s_ne)
            elif cname.startswith("int_to_nat_") and len(args) == 1:
                src_spec = _INT_SPECS[cname.split("_")[3]]
                s_lo, s_hi, s_ne = self._term_bounds(args[0], src_spec, facts, depth + 1, next_visited)
                lo = max(lo, s_lo)
                hi = min(hi, s_hi)
                ne_set.update(s_ne)
            elif cname == "nat_to_usize" and len(args) == 1:
                s_lo, s_hi, s_ne = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                lo = max(lo, s_lo)
                hi = min(hi, s_hi)
                ne_set.update(s_ne)
            elif cname == "Seq_Count" and len(args) == 2:
                lo = max(lo, 0)
            elif spec is not None and len(args) == 2:
                if cname == f"int_and_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    if r_lo == r_hi and r_lo >= 0:
                        lo = max(lo, 0)
                        hi = min(hi, r_lo)
                    if l_lo == l_hi and l_lo >= 0:
                        lo = max(lo, 0)
                        hi = min(hi, l_lo)
                elif cname == f"int_rem_{spec.name}" and not spec.signed:
                    _, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    if r_hi > 0:
                        lo = max(lo, 0)
                        hi = min(hi, r_hi - 1)
                elif cname == f"int_shr_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], _INT_SPECS["usize"], facts, depth + 1, next_visited)
                    if 0 <= r_lo <= r_hi < spec.bits and (not spec.signed or l_lo >= 0):
                        lo = max(lo, max(0, l_lo) >> r_hi)
                        hi = min(hi, l_hi >> r_lo)
                elif cname == f"int_shl_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], _INT_SPECS["usize"], facts, depth + 1, next_visited)
                    if 0 <= r_lo <= r_hi < spec.bits and l_lo >= 0:
                        lo = max(lo, l_lo << r_lo)
                        hi = min(hi, l_hi << r_hi)
                elif cname == f"int_add_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo + r_lo)
                    hi = min(hi, l_hi + r_hi)
                elif cname == f"int_sub_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo - r_hi)
                    hi = min(hi, l_hi - r_lo)
                elif cname == f"int_mul_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    prods = (l_lo * r_lo, l_lo * r_hi, l_hi * r_lo, l_hi * r_hi)
                    lo = max(lo, min(prods))
                    hi = min(hi, max(prods))
            elif spec is None and len(args) == 2:
                if cname == "+":
                    l_lo, l_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], None, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo + r_lo)
                    hi = min(hi, l_hi + r_hi)
                elif cname == "-":
                    l_lo, l_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], None, facts, depth + 1, next_visited)
                    lo = max(0, l_lo - r_hi)
                    hi = min(hi, max(0, l_hi - r_lo))
                elif cname == "*":
                    l_lo, l_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], None, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo * r_lo)
                    hi = min(hi, l_hi * r_hi)
        uw = self._unwrap_numeric_subject(w)
        for fact in facts:
            parsed = self._parse_cmp_fact(fact)
            if parsed is None:
                continue
            f_op, f_spec, f_l, f_r = parsed
            ufl = self._unwrap_numeric_subject(f_l)
            ufr = self._unwrap_numeric_subject(f_r)
            if ufl == uw:
                r_lo, r_hi, _ = self._term_bounds(f_r, f_spec, facts, depth + 1, next_visited)
                if f_op == "lt":
                    hi = min(hi, r_hi - 1)
                elif f_op == "le":
                    hi = min(hi, r_hi)
                elif f_op == "gt":
                    lo = max(lo, r_lo + 1)
                elif f_op == "ge":
                    lo = max(lo, r_lo)
                elif f_op == "eq":
                    lo = max(lo, r_lo)
                    hi = min(hi, r_hi)
                elif f_op == "ne" and r_lo == r_hi:
                    ne_set.add(r_lo)
            elif ufr == uw:
                l_lo, l_hi, _ = self._term_bounds(f_l, f_spec, facts, depth + 1, next_visited)
                if f_op == "lt":
                    lo = max(lo, l_lo + 1)
                elif f_op == "le":
                    lo = max(lo, l_lo)
                elif f_op == "gt":
                    hi = min(hi, l_hi - 1)
                elif f_op == "ge":
                    hi = min(hi, l_hi)
                elif f_op == "eq":
                    lo = max(lo, l_lo)
                    hi = min(hi, l_hi)
                elif f_op == "ne" and l_lo == l_hi:
                    ne_set.add(l_lo)
        while lo in ne_set and lo <= hi:
            lo += 1
        while hi in ne_set and hi >= lo:
            hi -= 1
        return lo, hi, ne_set

    def _unwrap_numeric_subject(self, term: _Term, *, normalize_lit: bool = True) -> _Term:
        curr = self.whnf(term)
        while curr.kind == "app":
            head, args = self.spine(curr)
            if (
                head.kind == "const"
                and isinstance(head.value, str)
                and len(args) == 1
                and (
                    head.value.startswith("int_to_nat_")
                    or head.value.startswith("int_from_")
                    or head.value == "nat_to_usize"
                )
            ):
                curr = self.whnf(args[0])
            elif (
                head.kind == "const"
                and isinstance(head.value, str)
                and len(args) == 2
                and (head.value == "+" or head.value.startswith("int_add_"))
            ):
                a0 = self._unwrap_numeric_subject(args[0], normalize_lit=False)
                a1 = self._unwrap_numeric_subject(args[1], normalize_lit=False)
                if a0.kind in {"int", "nat"} and a0.value == 0:
                    curr = a1
                elif a1.kind in {"int", "nat"} and a1.value == 0:
                    curr = a0
                else:
                    return _apps(head, a0, a1)
            else:
                break
        if normalize_lit and curr.kind == "nat":
            return _int_term(_INT_SPECS["usize"], cast("int", curr.value))
        return curr

    def _extract_base_and_offset_term(self, term: _Term) -> tuple[_Term, _Term | None]:
        w = self._unwrap_numeric_subject(term)
        if w.kind == "app":
            head, args = self.spine(w)
            if (
                head.kind == "const"
                and isinstance(head.value, str)
                and len(args) == 2
                and (head.value == "+" or head.value.startswith("int_add_"))
            ):
                base_a, rem_a = self._extract_base_and_offset_term(args[0])
                if rem_a is None:
                    return base_a, args[1]
                return base_a, _apps(head, rem_a, args[1])
        return w, None

    def _same_numeric_subject(self, a: _Term, b: _Term) -> bool:
        return self._unwrap_numeric_subject(a) == self._unwrap_numeric_subject(b)

    def _prove_comparison(
        self, op_kind: str, spec: _IntSpec | None, lhs: _Term, rhs: _Term, facts: list[_Term]
    ) -> bool:
        wl = self.whnf(lhs)
        wr = self.whnf(rhs)
        if wl.kind in {"int", "nat"} and wr.kind in {"int", "nat"}:
            lv = cast("int", wl.value)
            rv = cast("int", wr.value)
            return (
                (op_kind == "lt" and lv < rv)
                or (op_kind == "le" and lv <= rv)
                or (op_kind == "gt" and lv > rv)
                or (op_kind == "ge" and lv >= rv)
                or (op_kind == "eq" and lv == rv)
                or (op_kind == "ne" and lv != rv)
            )
        uwl = self._unwrap_numeric_subject(wl)
        uwr = self._unwrap_numeric_subject(wr)
        if uwl == uwr and op_kind in {"le", "ge", "eq"}:
            return True
        for fact in facts:
            parsed = self._parse_cmp_fact(fact)
            if parsed is None:
                continue
            f_op, _, f_l, f_r = parsed
            ufl = self._unwrap_numeric_subject(f_l)
            ufr = self._unwrap_numeric_subject(f_r)
            if ufl == uwl and ufr == uwr:
                if op_kind == f_op:
                    return True
                if op_kind == "le" and f_op in {"lt", "eq"}:
                    return True
                if op_kind == "ge" and f_op in {"gt", "eq"}:
                    return True
                if op_kind == "ne" and f_op in {"lt", "gt"}:
                    return True
            if ufl == uwr and ufr == uwl:
                if op_kind == "lt" and f_op == "gt":
                    return True
                if op_kind == "le" and f_op in {"ge", "eq"}:
                    return True
                if op_kind == "gt" and f_op == "lt":
                    return True
                if op_kind == "ge" and f_op in {"le", "eq"}:
                    return True
                if op_kind == "eq" and f_op == "eq":
                    return True
                if op_kind == "ne" and f_op in {"ne", "lt", "gt"}:
                    return True
        l_lo, l_hi, l_ne = self._term_bounds(wl, spec, facts)
        r_lo, r_hi, r_ne = self._term_bounds(wr, spec, facts)
        if l_lo > l_hi or r_lo > r_hi:
            # Contradictory active facts (unreachable branch)
            return True
        if op_kind == "lt" and l_hi < r_lo:
            return True
        if op_kind == "le" and l_hi <= r_lo:
            return True
        if op_kind == "gt" and l_lo > r_hi:
            return True
        if op_kind == "ge" and l_lo >= r_hi:
            return True
        if op_kind == "eq" and l_lo == l_hi == r_lo == r_hi:
            return True
        if op_kind == "ne":
            if l_hi < r_lo or r_hi < l_lo:
                return True
            if r_lo == r_hi and r_lo in l_ne:
                return True
            if l_lo == l_hi and l_lo in r_ne:
                return True
        base_l, rem_l = self._extract_base_and_offset_term(wl)
        base_r, rem_r = self._extract_base_and_offset_term(wr)
        if self._same_numeric_subject(base_l, base_r) and (rem_l is not None or rem_r is not None):
            zero = _int_term(spec, 0) if spec is not None else _term("nat", value=0)
            off_l = zero if rem_l is None else rem_l
            off_r = zero if rem_r is None else rem_r
            return self._prove_comparison(op_kind, spec, off_l, off_r, facts)
        # Bounded transitive chaining over active comparison facts
        edges: dict[_Term, list[tuple[_Term, bool]]] = {}
        zero_subj = _int_term(_INT_SPECS["usize"], 0)
        if spec is None or not spec.signed:
            edges.setdefault(zero_subj, []).append((uwl, False))
            edges.setdefault(zero_subj, []).append((uwr, False))
        for fact in facts:
            parsed = self._parse_cmp_fact(fact)
            if parsed is None:
                continue
            f_op, f_spec, f_l, f_r = parsed
            ufl = self._unwrap_numeric_subject(f_l)
            ufr = self._unwrap_numeric_subject(f_r)
            if f_spec is None or not f_spec.signed:
                edges.setdefault(zero_subj, []).append((ufl, False))
                edges.setdefault(zero_subj, []).append((ufr, False))
            if f_op == "lt":
                edges.setdefault(ufl, []).append((ufr, True))
            elif f_op == "le":
                edges.setdefault(ufl, []).append((ufr, False))
            elif f_op == "gt":
                edges.setdefault(ufr, []).append((ufl, True))
            elif f_op == "ge":
                edges.setdefault(ufr, []).append((ufl, False))
            elif f_op == "eq":
                edges.setdefault(ufl, []).append((ufr, False))
                edges.setdefault(ufr, []).append((ufl, False))

        def can_reach(start_node: _Term, target_node: _Term, need_strict: bool) -> bool:
            frontier: list[tuple[_Term, bool, int]] = [(start_node, False, 0)]
            seen: dict[_Term, bool] = {start_node: False}
            while frontier:
                cur_n, has_strict, steps = frontier.pop(0)
                if cur_n == target_node and (has_strict or not need_strict):
                    return True
                if steps >= 4:
                    continue
                for nxt_n, edge_strict in edges.get(cur_n, ()):
                    nxt_strict = has_strict or edge_strict
                    if nxt_n not in seen or (nxt_strict and not seen[nxt_n]):
                        seen[nxt_n] = nxt_strict
                        frontier.append((nxt_n, nxt_strict, steps + 1))
            return False

        if op_kind == "lt" and can_reach(uwl, uwr, True):
            return True
        if op_kind == "le" and can_reach(uwl, uwr, False):
            return True
        if op_kind == "gt" and can_reach(uwr, uwl, True):
            return True
        if op_kind == "ge" and can_reach(uwr, uwl, False):
            return True
        if op_kind == "eq" and can_reach(uwl, uwr, False) and can_reach(uwr, uwl, False):
            return True
        if op_kind == "le":
            lh, la = self.spine(uwl)
            if lh == _constant("Succ") and len(la) == 1:
                if self._prove_comparison("lt", spec, la[0], uwr, facts):
                    return True
            elif (
                lh.kind == "const"
                and isinstance(lh.value, str)
                and (lh.value == "+" or lh.value.startswith("int_add_"))
                and len(la) == 2
                and self.whnf(la[1]).kind in {"nat", "int"}
                and self.whnf(la[1]).value == 1
            ) and self._prove_comparison("lt", spec, la[0], uwr, facts):
                return True
        return bool(op_kind == "ne" and (can_reach(uwl, uwr, True) or can_reach(uwr, uwl, True)))

    def _prove_bool_precondition(self, cond: _Term, environment: dict[str, _Binding]) -> bool:
        w = self.whnf(cond)
        if w == _term("bool", value=1):
            return True
        if w == _term("bool", value=0):
            return False
        facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
        if w in facts or cond in facts:
            return True
        head, args = self.spine(w)
        if head == _constant("&&") and len(args) == 2:
            return self._prove_bool_precondition(args[0], environment) and self._prove_bool_precondition(
                args[1], environment
            )
        if head == _constant("||") and len(args) == 2:
            return self._prove_bool_precondition(args[0], environment) or self._prove_bool_precondition(
                args[1], environment
            )
        if head == _constant("==>") and len(args) == 2:
            self.active_facts.append(args[0])
            try:
                return self._prove_bool_precondition(args[1], environment)
            finally:
                self.active_facts.pop()
        if head == _constant("!") and len(args) == 1:
            neg = self._negate_bool_term(args[0])
            if neg != w:
                return self._prove_bool_precondition(neg, environment)
        if head == _constant("Span_Disjoint") and len(args) == 3:
            a_t, b_t = args[1], args[2]
            if _apps(_constant("Span_Disjoint"), _U8, b_t, a_t) in facts:
                return True
            ra, rb = self._root_span(a_t), self._root_span(b_t)
            if (ra, rb) != (a_t, b_t) and (
                _apps(_constant("Span_Disjoint"), _U8, ra, rb) in facts
                or _apps(_constant("Span_Disjoint"), _U8, rb, ra) in facts
            ):
                return True
        if head == _constant("Slots_Disjoint") and len(args) == 5:
            elem, cap_a, cap_b, a_t, b_t = args
            if _apps(_constant("Slots_Disjoint"), elem, cap_b, cap_a, b_t, a_t) in facts:
                return True
            ra, rb = self._root_span(a_t), self._root_span(b_t)
            if (ra, rb) != (a_t, b_t):
                for f_item in facts:
                    fh, fa = self.spine(f_item)
                    if fh == _constant("Slots_Disjoint") and len(fa) == 5:
                        fra, frb = self._root_span(fa[3]), self._root_span(fa[4])
                        if (fra == ra and frb == rb) or (fra == rb and frb == ra):
                            return True
        if head == _constant("Slots_LivePrefix") and len(args) == 4:
            elem, cap, s, cnt = args
            return (
                self._prove_bool_precondition(_apps(_constant("Slots_CanRead"), elem, cap, s), environment)
                and self._prove_bool_precondition(
                    _apps(_constant("int_eq_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), cnt),
                    environment,
                )
                and self._prove_bool_precondition(
                    _apps(_constant("int_le_usize"), cnt, self._slots_cap_usize_term(cap)),
                    environment,
                )
            )
        if head == _constant("Slots_VacantRange") and len(args) == 5:
            elem, cap, s, start, end = args
            return (
                self._prove_bool_precondition(_apps(_constant("Slots_CanWrite"), elem, cap, s), environment)
                and self._prove_bool_precondition(
                    _apps(_constant("int_le_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), start),
                    environment,
                )
                and self._prove_bool_precondition(_apps(_constant("int_le_usize"), start, end), environment)
                and self._prove_bool_precondition(
                    _apps(_constant("int_le_usize"), end, self._slots_cap_usize_term(cap)),
                    environment,
                )
            )
        if head == _constant("Seq_All") and len(args) == 3:
            elem, seq_t, pred_t = args
            s_head, s_args = self.spine(self.whnf(seq_t))
            if s_head in {_constant("Seq_Take"), _constant("Seq_Skip"), _constant("Seq_Slice")} and len(s_args) >= 2:
                parent_all = self.whnf(_apps(_constant("Seq_All"), elem, s_args[1], pred_t))
                if any(self.convertible(f_item, parent_all) for f_item in facts):
                    return True
            if s_head == _constant("Seq_Take") and len(s_args) == 3:
                parent_seq = s_args[1]
                k_term = self.whnf(s_args[2])
                k_head, k_args = self.spine(k_term)
                prev_k: _Term | None = None
                if (k_head == _constant("Succ") and len(k_args) == 1) or (
                    k_head == _constant("+") and len(k_args) == 2 and self.whnf(k_args[1]) == _term("nat", value=1)
                ):
                    prev_k = k_args[0]
                elif (
                    k_head == _constant("int_to_nat_usize")
                    and len(k_args) == 1
                ):
                    ih, ia = self.spine(self.whnf(k_args[0]))
                    if ih == _constant("int_add_usize") and len(ia) == 2 and self.whnf(ia[1]) == _int_term(_INT_SPECS["usize"], 1):
                        prev_k = _app(_constant("int_to_nat_usize"), ia[0])
                if prev_k is not None:
                    prev_take_all = self.whnf(
                        _apps(_constant("Seq_All"), elem, _apps(_constant("Seq_Take"), elem, parent_seq, prev_k), pred_t)
                    )
                    if any(self.convertible(f_item, prev_take_all) for f_item in facts):
                        d_val = self._default_term_for_type(elem)
                        at_term = _apps(_constant("Seq_At"), elem, d_val, parent_seq, prev_k)
                        step_cond = self.whnf(_app(pred_t, at_term))
                        if self._prove_bool_precondition(step_cond, environment):
                            return True
            for f_item in facts:
                fh, fa = self.spine(f_item)
                if fh == _constant("Seq_All") and len(fa) == 3 and self.convertible(fa[2], pred_t):
                    th, ta = self.spine(self.whnf(fa[1]))
                    if th == _constant("Seq_Take") and len(ta) == 3 and self.convertible(ta[1], seq_t):
                        cnt_seq = _apps(_constant("Seq_Count"), elem, seq_t)
                        if self._prove_comparison("eq", None, ta[2], cnt_seq, facts):
                            return True
        for f_item in facts:
            fh, fa = self.spine(f_item)
            if fh == _constant("Seq_All") and len(fa) == 3:
                all_elem, all_seq, all_pred = fa
                d_val = self._default_term_for_type(all_elem)
                # Check if w is an instance of all_pred(Seq_At(all_elem, d_val, all_seq, idx))
                for sub_t in self._collect_seq_at_terms(w):
                    sh, sa = self.spine(sub_t)
                    if sh == _constant("Seq_At") and len(sa) == 4 and self.convertible(sa[2], all_seq):
                        inst_pred = self.whnf(_app(all_pred, sub_t))
                        if inst_pred == w:
                            cnt_seq = _apps(_constant("Seq_Count"), all_elem, all_seq)
                            if self._prove_comparison("lt", None, sa[3], cnt_seq, facts):
                                return True
                    elif sh == _constant("Span_Read") and len(sa) == 3:
                        span_m = self.whnf(_apps(_constant("Span_Model"), sa[0], sa[1]))
                        if self.convertible(span_m, all_seq):
                            inst_pred = self.whnf(_app(all_pred, sub_t))
                            if inst_pred == w:
                                span_len = _apps(_constant("Span_Length"), sa[0], sa[1])
                                if self._prove_comparison("lt", _INT_SPECS["usize"], sa[2], span_len, facts):
                                    return True
                    elif sh == _constant("Slots_Read") and len(sa) == 5:
                        slots_m = self.whnf(_apps(_constant("Slots_Model"), sa[0], sa[1], sa[3]))
                        if self.convertible(slots_m, all_seq):
                            inst_pred = self.whnf(_app(all_pred, sub_t))
                            if inst_pred == w:
                                slots_live = _apps(_constant("Slots_LiveCount"), sa[0], sa[1], sa[3])
                                if self._prove_comparison("lt", _INT_SPECS["usize"], sa[4], slots_live, facts):
                                    return True
        parsed = self._parse_cmp_fact(w)
        if parsed is not None:
            op_kind, spec, lhs, rhs = parsed
            return self._prove_comparison(op_kind, spec, lhs, rhs, facts)
        return False

    def _collect_seq_at_terms(self, term: _Term) -> list[_Term]:
        found: list[_Term] = []
        stack = [self.whnf(term)]
        visited: set[int] = set()
        while stack:
            cur = stack.pop()
            if id(cur) in visited:
                continue
            visited.add(id(cur))
            head, args = self.spine(cur)
            if head in {_constant("Seq_At"), _constant("Span_Read"), _constant("Slots_Read")}:
                found.append(cur)
            stack.extend(self.whnf(a) for a in args)
        return found

    def _check_precondition_term(
        self, req: _Term, environment: dict[str, _Binding], site: Node | None
    ) -> None:
        req_type = self.whnf(self.infer(req))
        if req_type == _BOOL:
            if not self._prove_bool_precondition(req, environment):
                raise self.fail(
                    "type",
                    "call precondition ('requires' clause) could not be established from active facts",
                    site,
                )
            return
        self._prove_proposition(req, environment, (), site if site is not None else cast("Node", self.site))

    def _root_span(self, span_term: _Term) -> _Term:
        curr = self.whnf(span_term)
        while curr.kind == "app":
            head, args = self.spine(curr)
            if head.kind != "const" or not isinstance(head.value, str):
                break
            sname = head.value
            if sname in {
                "Span_ReadOnly",
                "Span_Invalidate",
                "Span_Write",
                "Span_Fill",
                "Span_Slice",
                "Span_CopyPrefix",
                "Span_Restore",
            } and len(args) >= 2:
                curr = self.whnf(args[1])
            elif sname in {"Slots_Write", "Slots_TransferSource", "Slots_TransferDest"} and len(args) >= 3:
                curr = self.whnf(args[2])
            elif sname == "Slots_CopyRepresentation" and len(args) == 6:
                curr = self.whnf(args[4])
            else:
                break
        return curr

    def _is_readonly_span(self, span_term: _Term) -> bool:
        root = self._root_span(span_term)
        return root.kind == "var" and cast("int", root.value) in self.readonly_span_vars

    def _check_span_can_read(
        self, span_term: _Term, environment: dict[str, _Binding], site: Node
    ) -> None:
        cond = _apps(_constant("Span_CanRead"), _U8, span_term)
        if not self._prove_bool_precondition(cond, environment):
            raise self.fail(
                "type",
                "cannot prove Span has valid tag and read permission (Span.CanRead)",
                site,
            )

    def _check_span_can_write(
        self, span_term: _Term, environment: dict[str, _Binding], site: Node
    ) -> None:
        if self._is_readonly_span(span_term):
            raise self.fail("type", "cannot mutate a read-only 'in Span<byte>' borrow", site)
        cond = _apps(_constant("Span_CanWrite"), _U8, span_term)
        if not self._prove_bool_precondition(cond, environment):
            raise self.fail(
                "type",
                "cannot prove Span has valid tag and write permission (Span.CanWrite)",
                site,
            )

    def _check_span_disjoint(
        self, dst_term: _Term, src_term: _Term, environment: dict[str, _Binding], site: Node
    ) -> None:
        direct_ab = _apps(_constant("Span_Disjoint"), _U8, dst_term, src_term)
        direct_ba = _apps(_constant("Span_Disjoint"), _U8, src_term, dst_term)
        if self._prove_bool_precondition(direct_ab, environment) or self._prove_bool_precondition(
            direct_ba, environment
        ):
            return
        root_dst = self._root_span(dst_term)
        root_src = self._root_span(src_term)
        if root_dst != root_src:
            root_ab = _apps(_constant("Span_Disjoint"), _U8, root_dst, root_src)
            root_ba = _apps(_constant("Span_Disjoint"), _U8, root_src, root_dst)
            if self._prove_bool_precondition(root_ab, environment) or self._prove_bool_precondition(
                root_ba, environment
            ):
                return
        ba = _apps(_constant("Span_Base"), _U8, dst_term)
        la = _apps(_constant("Span_Length"), _U8, dst_term)
        bb = _apps(_constant("Span_Base"), _U8, src_term)
        lb = _apps(_constant("Span_Length"), _U8, src_term)
        cond_ab = _apps(_constant("int_le_usize"), _apps(_constant("int_add_usize"), ba, la), bb)
        cond_ba = _apps(_constant("int_le_usize"), _apps(_constant("int_add_usize"), bb, lb), ba)
        if self._prove_bool_precondition(cond_ab, environment) or self._prove_bool_precondition(
            cond_ba, environment
        ):
            return
        raise self.fail(
            "type",
            "cannot prove Span.CopyPrefix source and destination extents are disjoint",
            site,
        )

    def _elaborate_span_intrinsic(
        self,
        node: Node,
        member_name: str,
        call_args: list[Node],
        environment: dict[str, _Binding],
    ) -> _Binding:
        self.site = node
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                raise self.fail("name", f"Span.{member_name} does not accept labeled arguments", arg_node)
        raw_arg_nodes = [self._unwrap_group(self.node(a["value"])) for a in call_args]
        arg_nodes = [
            self._unwrap_group(self.node(n["value"]))
            if (
                n["kind"] == "unary"
                and isinstance(n.get("operator"), dict)
                and cast("Node", n["operator"]).get("text") in {"ref", "in"}
            )
            else n
            for n in raw_arg_nodes
        ]
        span_u8 = _app(_constant("Span"), _U8)
        if member_name == "AllocZeroed":
            if len(arg_nodes) == 1:
                base_t = _int_term(_INT_SPECS["usize"], 0)
                cap_t = self.check(arg_nodes[0], _USIZE, environment)
            elif len(arg_nodes) == 2:
                base_t = self.check(arg_nodes[0], _USIZE, environment)
                cap_t = self.check(arg_nodes[1], _USIZE, environment)
            else:
                raise self.fail("type", f"Span.AllocZeroed expects 1 or 2 arguments, got {len(arg_nodes)}", node)
            return _Binding(_apps(_constant("Span_AllocZeroed"), _U8, base_t, cap_t), span_u8)
        if member_name in {"ReadOnly", "Invalidate"}:
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Span.{member_name} expects 1 argument, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            return _Binding(_apps(_constant(f"Span_{member_name}"), _U8, s_t), span_u8)
        if member_name == "Disjoint":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Span.Disjoint expects 2 arguments, got {len(arg_nodes)}", node)
            a_t = self.check(arg_nodes[0], span_u8, environment)
            b_t = self.check(arg_nodes[1], span_u8, environment)
            return _Binding(_apps(_constant("Span_Disjoint"), _U8, a_t, b_t), _BOOL)
        if member_name == "Read":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Span.Read expects 2 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            idx_t = self.check(arg_nodes[1], _USIZE, environment)
            self._check_span_can_read(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            in_bounds = _apps(_constant("int_lt_usize"), idx_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Span.Read index is within Span.Length bounds", node)
            return _Binding(_apps(_constant("Span_Read"), _U8, s_t, idx_t), _U8)
        if member_name == "Write":
            if len(arg_nodes) != 3:
                raise self.fail("type", f"Span.Write expects 3 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            idx_t = self.check(arg_nodes[1], _USIZE, environment)
            val_t = self.check(arg_nodes[2], _U8, environment)
            self._check_span_can_write(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            in_bounds = _apps(_constant("int_lt_usize"), idx_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Span.Write index is within Span.Length bounds", node)
            return _Binding(_apps(_constant("Span_Write"), _U8, s_t, idx_t, val_t), span_u8)
        if member_name == "Fill":
            if len(arg_nodes) != 4:
                raise self.fail("type", f"Span.Fill expects 4 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            off_t = self.check(arg_nodes[1], _USIZE, environment)
            cnt_t = self.check(arg_nodes[2], _USIZE, environment)
            val_t = self.check(arg_nodes[3], _U8, environment)
            self._check_span_can_write(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            end_t = _apps(_constant("int_add_usize"), off_t, cnt_t)
            in_bounds = _apps(_constant("int_le_usize"), end_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail(
                    "type",
                    "cannot prove Span.Fill subrange (offset + count <= Span.Length) is in bounds",
                    node,
                )
            return _Binding(_apps(_constant("Span_Fill"), _U8, s_t, off_t, cnt_t, val_t), span_u8)
        if member_name == "Slice":
            if len(arg_nodes) != 3:
                raise self.fail("type", f"Span.Slice expects 3 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            off_t = self.check(arg_nodes[1], _USIZE, environment)
            cnt_t = self.check(arg_nodes[2], _USIZE, environment)
            self._check_span_can_read(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            end_t = _apps(_constant("int_add_usize"), off_t, cnt_t)
            in_bounds = _apps(_constant("int_le_usize"), end_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail(
                    "type",
                    "cannot prove Span.Slice subrange (offset + count <= Span.Length) is in bounds",
                    node,
                )
            return _Binding(_apps(_constant("Span_Slice"), _U8, s_t, off_t, cnt_t), span_u8)
        if member_name == "CopyPrefix":
            if len(arg_nodes) != 3:
                raise self.fail("type", f"Span.CopyPrefix expects 3 arguments, got {len(arg_nodes)}", node)
            dst_t = self.check(arg_nodes[0], span_u8, environment)
            src_t = self.check(arg_nodes[1], span_u8, environment)
            cnt_t = self.check(arg_nodes[2], _USIZE, environment)
            self._check_span_can_write(dst_t, environment, node)
            self._check_span_can_read(src_t, environment, node)
            dst_len = _apps(_constant("Span_Length"), _U8, dst_t)
            src_len = _apps(_constant("Span_Length"), _U8, src_t)
            if not self._prove_bool_precondition(_apps(_constant("int_le_usize"), cnt_t, dst_len), environment):
                raise self.fail("type", "cannot prove Span.CopyPrefix count <= dst.Length", node)
            if not self._prove_bool_precondition(_apps(_constant("int_le_usize"), cnt_t, src_len), environment):
                raise self.fail("type", "cannot prove Span.CopyPrefix count <= src.Length", node)
            self._check_span_disjoint(dst_t, src_t, environment, node)
            return _Binding(_apps(_constant("Span_CopyPrefix"), _U8, dst_t, src_t, cnt_t), span_u8)
        if member_name == "Restore":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Span.Restore expects 2 arguments, got {len(arg_nodes)}", node)
            parent_t = self.check(arg_nodes[0], span_u8, environment)
            view_t = self.check(arg_nodes[1], span_u8, environment)
            self._check_span_can_write(parent_t, environment, node)
            p_base = _apps(_constant("Span_Base"), _U8, parent_t)
            p_len = _apps(_constant("Span_Length"), _U8, parent_t)
            v_base = _apps(_constant("Span_Base"), _U8, view_t)
            v_len = _apps(_constant("Span_Length"), _U8, view_t)
            base_ok = _apps(_constant("int_ge_usize"), v_base, p_base)
            end_ok = _apps(
                _constant("int_le_usize"),
                _apps(_constant("int_add_usize"), v_base, v_len),
                _apps(_constant("int_add_usize"), p_base, p_len),
            )
            if not (
                self._prove_bool_precondition(base_ok, environment)
                and self._prove_bool_precondition(end_ok, environment)
            ):
                raise self.fail(
                    "type",
                    "cannot prove Span.Restore view extent is contained within parent extent",
                    node,
                )
            return _Binding(_apps(_constant("Span_Restore"), _U8, parent_t, view_t), span_u8)
        raise self.fail("name", f"unknown Span intrinsic 'Span.{member_name}'", node)

    def _seq_nat_arg(self, arg_node: Node, environment: dict[str, _Binding]) -> _Term:
        if self._is_unsuffixed_int_expr(arg_node):
            return self.check(arg_node, _NAT, environment)
        arg_b = self.expression(arg_node, environment)
        ty_w = self.whnf(arg_b.type)
        if ty_w == _NAT:
            return arg_b.term
        spec = self._int_spec(ty_w)
        if spec is not None and not spec.signed:
            val_w = self.whnf(arg_b.term)
            if val_w.kind == "int":
                return _term("nat", value=max(0, cast("int", val_w.value)))
            return _app(_constant(f"int_to_nat_{spec.name}"), arg_b.term)
        raise self.fail("type", "sequence index or count must be Nat or an unsigned integer", arg_node)

    def _elaborate_seq_intrinsic(
        self,
        node: Node,
        member_name: str,
        gen_args: list[Node],
        call_args: list[Node],
        environment: dict[str, _Binding],
    ) -> _Binding:
        self.site = node
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                raise self.fail("name", f"Seq.{member_name} does not accept labeled arguments", arg_node)
        arg_nodes = [self.node(a["value"]) for a in call_args]
        if member_name == "Empty":
            if arg_nodes:
                raise self.fail("type", f"Seq.Empty expects 0 arguments, got {len(arg_nodes)}", node)
            if len(gen_args) > 1:
                raise self.fail("type", "Seq.Empty accepts at most 1 generic type argument", node)
            elem_t = self.type(gen_args[0], environment) if gen_args else self.meta(_SORT, environment)
            return _Binding(_app(_constant("Seq_Empty"), elem_t), _app(_constant("Seq"), elem_t))
        if member_name == "Singleton":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.Singleton expects 1 argument, got {len(arg_nodes)}", node)
            if len(gen_args) > 1:
                raise self.fail("type", "Seq.Singleton accepts at most 1 generic type argument", node)
            if gen_args:
                elem_t = self.type(gen_args[0], environment)
                val_t = self.check(arg_nodes[0], elem_t, environment)
            else:
                val_b = self.expression(arg_nodes[0], environment)
                elem_t, val_t = val_b.type, val_b.term
            return _Binding(_apps(_constant("Seq_Singleton"), elem_t, val_t), _app(_constant("Seq"), elem_t))
        raise self.fail("name", f"unknown Seq intrinsic 'Seq.{member_name}'", node)

    def _elaborate_seq_method(
        self,
        node: Node,
        recv_b: _Binding,
        elem_t: _Term,
        member_name: str,
        call_args: list[Node],
        environment: dict[str, _Binding],
    ) -> _Binding:
        self.site = node
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                raise self.fail("name", f"Seq.{member_name} does not accept labeled arguments", arg_node)
        arg_nodes = [self.node(a["value"]) for a in call_args]
        seq_ty = _app(_constant("Seq"), elem_t)
        cnt_t = _apps(_constant("Seq_Count"), elem_t, recv_b.term)
        if member_name == "At":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.At expects 1 argument, got {len(arg_nodes)}", node)
            idx_t = self._seq_nat_arg(arg_nodes[0], environment)
            in_bounds = _apps(_constant("<"), idx_t, cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Seq.At index is within Seq.Count bounds", node)
            d_val = self._default_term_for_type(elem_t)
            return _Binding(_apps(_constant("Seq_At"), elem_t, d_val, recv_b.term, idx_t), elem_t)
        if member_name == "Update":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Seq.Update expects 2 arguments, got {len(arg_nodes)}", node)
            idx_t = self._seq_nat_arg(arg_nodes[0], environment)
            val_t = self.check(arg_nodes[1], elem_t, environment)
            in_bounds = _apps(_constant("<"), idx_t, cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Seq.Update index is within Seq.Count bounds", node)
            return _Binding(_apps(_constant("Seq_Update"), elem_t, recv_b.term, idx_t, val_t), seq_ty)
        if member_name == "Append":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.Append expects 1 argument, got {len(arg_nodes)}", node)
            other_t = self.check(arg_nodes[0], seq_ty, environment)
            return _Binding(_apps(_constant("Seq_Append"), elem_t, recv_b.term, other_t), seq_ty)
        if member_name in {"Take", "Skip"}:
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.{member_name} expects 1 argument, got {len(arg_nodes)}", node)
            n_t = self._seq_nat_arg(arg_nodes[0], environment)
            in_bounds = _apps(_constant("<="), n_t, cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", f"cannot prove Seq.{member_name} count <= Seq.Count", node)
            return _Binding(_apps(_constant(f"Seq_{member_name}"), elem_t, recv_b.term, n_t), seq_ty)
        if member_name == "Slice":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Seq.Slice expects 2 arguments, got {len(arg_nodes)}", node)
            off_t = self._seq_nat_arg(arg_nodes[0], environment)
            len_t = self._seq_nat_arg(arg_nodes[1], environment)
            in_bounds = _apps(_constant("<="), _apps(_constant("+"), off_t, len_t), cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail(
                    "type", "cannot prove Seq.Slice subrange (offset + count <= Seq.Count) is in bounds", node
                )
            return _Binding(_apps(_constant("Seq_Slice"), elem_t, recv_b.term, off_t, len_t), seq_ty)
        if member_name == "Contains":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.Contains expects 1 argument, got {len(arg_nodes)}", node)
            val_t = self.check(arg_nodes[0], elem_t, environment)
            elem_w = self.whnf(elem_t)
            spec = self._int_spec(elem_w)
            if spec is not None:
                eq_op = f"int_eq_{spec.name}"
            elif elem_w == _NAT:
                eq_op = "eq_nat"
            elif elem_w == _BOOL:
                eq_op = "eq_bool"
            else:
                raise self.fail(
                    "type", "Seq.Contains requires an element type with decidable equality (Nat, bool or integer)", node
                )
            x_var = self.fresh(elem_t)
            pred_lam = _term("lam", elem_t, _apps(_constant(eq_op), x_var, val_t), value=x_var.value)
            return _Binding(_apps(_constant("Seq_Any"), elem_t, recv_b.term, pred_lam), _BOOL)
        if member_name in {"All", "Any"}:
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.{member_name} expects 1 predicate argument, got {len(arg_nodes)}", node)
            pred_t = self.check(arg_nodes[0], self.pi(elem_t, _BOOL), environment)
            return _Binding(_apps(_constant(f"Seq_{member_name}"), elem_t, recv_b.term, pred_t), _BOOL)
        raise self.fail("name", f"Seq has no method '{member_name}'", node)

    def _unwrap_ref_expr_node(self, node: Node) -> Node:
        unwrapped = self._unwrap_group(node)
        if (
            unwrapped["kind"] == "unary"
            and isinstance(unwrapped.get("operator"), dict)
            and cast("Node", unwrapped["operator"]).get("text") in {"ref", "in"}
        ):
            return self._unwrap_group(self.node(unwrapped["value"]))
        return node

    def _slots_usize_arg(self, arg_node: Node, environment: dict[str, _Binding]) -> _Term:
        if self._is_unsuffixed_int_expr(arg_node):
            return self.check(arg_node, _USIZE, environment)
        arg_b = self.expression(arg_node, environment)
        ty_w = self.whnf(arg_b.type)
        if ty_w == _USIZE:
            return arg_b.term
        spec = self._int_spec(ty_w)
        if spec is not None and not spec.signed and _allows_from_conversion(spec, _INT_SPECS["usize"]):
            return _app(_constant(f"int_from_{spec.name}_usize"), arg_b.term)
        if ty_w == _NAT:
            val_w = self.whnf(arg_b.term)
            if val_w.kind == "nat":
                return _int_term(_INT_SPECS["usize"], cast("int", val_w.value))
            return _app(_constant("nat_to_usize"), arg_b.term)
        raise self.fail("type", "Slots index or count must have type usize", arg_node)

    def _slots_cap_usize_term(self, cap_t: _Term) -> _Term:
        cap_w = self.whnf(cap_t)
        if cap_w.kind == "nat":
            return _int_term(_INT_SPECS["usize"], cast("int", cap_w.value))
        if cap_w.kind == "int":
            return cap_w
        return _app(_constant("nat_to_usize"), cap_t)

    def _require_slots_binding(self, arg_node: Node, environment: dict[str, _Binding]) -> tuple[_Binding, _Term, _Term]:
        inner_node = self._unwrap_ref_expr_node(arg_node)
        b = self.expression(inner_node, environment)
        ty_w = self.whnf(b.type)
        head, args = self.spine(ty_w)
        if head != _constant("Slots") or len(args) != 2:
            raise self.fail("type", "expected a Slots<T, capacity> operand", arg_node)
        return b, args[0], args[1]

    def _check_slots_disjoint(
        self,
        elem_t: _Term,
        cap_a: _Term,
        s_a: _Term,
        cap_b: _Term,
        s_b: _Term,
        environment: dict[str, _Binding],
        site: Node,
    ) -> None:
        cond_ab = _apps(_constant("Slots_Disjoint"), elem_t, cap_a, cap_b, s_a, s_b)
        cond_ba = _apps(_constant("Slots_Disjoint"), elem_t, cap_b, cap_a, s_b, s_a)
        if self._prove_bool_precondition(cond_ab, environment) or self._prove_bool_precondition(
            cond_ba, environment
        ):
            return
        ra = self._root_span(s_a)
        rb = self._root_span(s_b)
        if (ra, rb) != (s_a, s_b):
            r_ab = _apps(_constant("Slots_Disjoint"), elem_t, cap_a, cap_b, ra, rb)
            r_ba = _apps(_constant("Slots_Disjoint"), elem_t, cap_b, cap_a, rb, ra)
            if self._prove_bool_precondition(r_ab, environment) or self._prove_bool_precondition(
                r_ba, environment
            ):
                return
        raise self.fail(
            "type",
            "cannot prove source and destination Slots extents are disjoint (Slots.Disjoint)",
            site,
        )

    def _elaborate_slots_intrinsic(
        self,
        node: Node,
        member_name: str,
        gen_args: list[Node],
        call_args: list[Node],
        environment: dict[str, _Binding],
        *,
        receiver: _Binding | None = None,
    ) -> _Binding:
        self.site = node
        allowed_labels = {
            "source", "src", "destination", "dst", "count", "slots",
            "index", "value", "start", "end", "base",
        }
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                lbl = self.name(arg_node["label"])
                if lbl not in allowed_labels:
                    raise self.fail("name", f"Slots.{member_name} does not accept label '{lbl}'", arg_node)
        arg_nodes = [self.node(a["value"]) for a in call_args]
        if member_name == "AllocVacant":
            if len(arg_nodes) > 1:
                raise self.fail("type", f"Slots.AllocVacant expects at most 1 argument (base), got {len(arg_nodes)}", node)
            if gen_args:
                if len(gen_args) != 2:
                    raise self.fail("type", "Slots.AllocVacant expects <T, capacity> generic arguments", node)
                elem_t = self.type(gen_args[0], environment)
                cap_t = self.argument(gen_args[1], _NAT, environment)
            else:
                elem_t = self.meta(_SORT, environment)
                cap_t = self.meta(_NAT, environment)
            base_t = (
                self._slots_usize_arg(arg_nodes[0], environment)
                if arg_nodes
                else _int_term(_INT_SPECS["usize"], 0)
            )
            return _Binding(
                _apps(_constant("Slots_AllocVacant"), elem_t, cap_t, base_t),
                _apps(_constant("Slots"), elem_t, cap_t),
            )
        if member_name == "LivePrefix":
            if receiver is not None:
                if len(arg_nodes) not in {1, 2}:
                    raise self.fail("type", "Slots.LivePrefix expects (count) or (0, count) arguments on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                if len(arg_nodes) == 2:
                    st_w = self.whnf(self._slots_usize_arg(arg_nodes[0], environment))
                    if st_w != _int_term(_INT_SPECS["usize"], 0):
                        raise self.fail("type", "LivePrefix start index must be 0", node)
                cnt_t = self._slots_usize_arg(arg_nodes[-1], environment)
            else:
                if len(arg_nodes) not in {2, 3}:
                    raise self.fail("type", "LivePrefix expects (slots, count) or (slots, 0, count) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                if len(arg_nodes) == 3:
                    st_w = self.whnf(self._slots_usize_arg(arg_nodes[1], environment))
                    if st_w != _int_term(_INT_SPECS["usize"], 0):
                        raise self.fail("type", "LivePrefix start index must be 0", node)
                cnt_t = self._slots_usize_arg(arg_nodes[-1], environment)
            return _Binding(_apps(_constant("Slots_LivePrefix"), elem_t, cap_t, s_b.term, cnt_t), _BOOL)
        if member_name in {"VacantRange", "VacantSuffix"}:
            if receiver is not None:
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                if member_name == "VacantSuffix":
                    if len(arg_nodes) != 1:
                        raise self.fail("type", "Slots.VacantSuffix expects 1 start argument", node)
                    start_t = self._slots_usize_arg(arg_nodes[0], environment)
                    end_t = self._slots_cap_usize_term(cap_t)
                else:
                    if len(arg_nodes) != 2:
                        raise self.fail("type", "Slots.VacantRange expects (start, end) arguments", node)
                    start_t = self._slots_usize_arg(arg_nodes[0], environment)
                    end_t = self._slots_usize_arg(arg_nodes[1], environment)
            else:
                if member_name == "VacantSuffix":
                    if len(arg_nodes) != 2:
                        raise self.fail("type", "VacantSuffix expects (slots, start) arguments", node)
                    s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                    start_t = self._slots_usize_arg(arg_nodes[1], environment)
                    end_t = self._slots_cap_usize_term(cap_t)
                else:
                    if len(arg_nodes) != 3:
                        raise self.fail("type", "VacantRange expects (slots, start, end) arguments", node)
                    s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                    start_t = self._slots_usize_arg(arg_nodes[1], environment)
                    end_t = self._slots_usize_arg(arg_nodes[2], environment)
            return _Binding(
                _apps(_constant("Slots_VacantRange"), elem_t, cap_t, s_b.term, start_t, end_t), _BOOL
            )
        if member_name == "PrefixModel":
            if receiver is not None:
                if len(arg_nodes) != 1:
                    raise self.fail("type", "Slots.PrefixModel expects 1 count argument on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                cnt_t = self._slots_usize_arg(arg_nodes[0], environment)
            else:
                if len(arg_nodes) != 2:
                    raise self.fail("type", "PrefixModel expects (slots, count) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                cnt_t = self._slots_usize_arg(arg_nodes[1], environment)
            return _Binding(
                _apps(_constant("PrefixModel"), elem_t, cap_t, s_b.term, cnt_t),
                _app(_constant("Seq"), elem_t),
            )
        if member_name == "Disjoint":
            if len(arg_nodes) != 2:
                raise self.fail("type", "Slots.Disjoint expects 2 Slots arguments", node)
            sa_b, elem_a, cap_a = self._require_slots_binding(arg_nodes[0], environment)
            sb_b, elem_b, cap_b = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_a, elem_b)
            return _Binding(
                _apps(_constant("Slots_Disjoint"), elem_a, cap_a, cap_b, sa_b.term, sb_b.term), _BOOL
            )
        if member_name == "RepEqual":
            if len(arg_nodes) != 3:
                raise self.fail("type", "Slots.RepEqual expects (dst, src, count) arguments", node)
            sa_b, elem_a, cap_a = self._require_slots_binding(arg_nodes[0], environment)
            sb_b, elem_b, cap_b = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_a, elem_b)
            cnt_t = self._slots_usize_arg(arg_nodes[2], environment)
            return _Binding(
                _apps(_constant("Slots_RepEqual"), elem_a, cap_a, cap_b, sa_b.term, sb_b.term, cnt_t), _BOOL
            )
        if member_name == "Read":
            if receiver is not None:
                if len(arg_nodes) != 1:
                    raise self.fail("type", "Slots.Read expects 1 index argument on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                idx_t = self._slots_usize_arg(arg_nodes[0], environment)
            else:
                if len(arg_nodes) != 2:
                    raise self.fail("type", "Slots.Read expects (slots, index) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                idx_t = self._slots_usize_arg(arg_nodes[1], environment)
            can_r = _apps(_constant("Slots_CanRead"), elem_t, cap_t, s_b.term)
            if not self._prove_bool_precondition(can_r, environment):
                raise self.fail("type", "cannot prove Slots has valid tag and read permission (Slots.CanRead)", node)
            live_t = _apps(_constant("Slots_LiveCount"), elem_t, cap_t, s_b.term)
            in_live = _apps(_constant("int_lt_usize"), idx_t, live_t)
            if not self._prove_bool_precondition(in_live, environment):
                raise self.fail(
                    "type",
                    "cannot read from a vacant or out-of-bounds slot; prove index < LiveCount (LivePrefix)",
                    node,
                )
            d_val = self._default_term_for_type(elem_t)
            return _Binding(_apps(_constant("Slots_Read"), elem_t, cap_t, d_val, s_b.term, idx_t), elem_t)
        if member_name == "Write":
            if receiver is not None:
                if len(arg_nodes) != 2:
                    raise self.fail("type", "Slots.Write expects (index, value) arguments on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                idx_t = self._slots_usize_arg(arg_nodes[0], environment)
                val_t = self.check(arg_nodes[1], elem_t, environment)
            else:
                if len(arg_nodes) != 3:
                    raise self.fail("type", "Slots.Write expects (slots, index, value) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                idx_t = self._slots_usize_arg(arg_nodes[1], environment)
                val_t = self.check(arg_nodes[2], elem_t, environment)
            if self._is_readonly_span(s_b.term):
                raise self.fail("type", "cannot write to a read-only 'in Slots' borrow", node)
            can_w = _apps(_constant("Slots_CanWrite"), elem_t, cap_t, s_b.term)
            if not self._prove_bool_precondition(can_w, environment):
                raise self.fail("type", "cannot prove Slots has valid tag and write permission (Slots.CanWrite)", node)
            live_t = _apps(_constant("Slots_LiveCount"), elem_t, cap_t, s_b.term)
            eq_live = _apps(_constant("int_eq_usize"), idx_t, live_t)
            cap_u = self._slots_cap_usize_term(cap_t)
            lt_cap = (
                _apps(_constant("int_lt_usize"), idx_t, cap_u)
                if self.whnf(cap_u).kind == "int"
                else _apps(_constant("<"), _app(_constant("int_to_nat_usize"), idx_t), cap_t)
            )
            if not (
                self._prove_bool_precondition(eq_live, environment)
                and self._prove_bool_precondition(lt_cap, environment)
            ):
                raise self.fail(
                    "type",
                    "cannot write to a non-vacant or out-of-bounds slot; prove VacantRange at index (index == LiveCount and index < capacity)",
                    node,
                )
            return _Binding(
                _apps(_constant("Slots_Write"), elem_t, cap_t, s_b.term, idx_t, val_t), s_b.type
            )
        if member_name == "CopyRepresentation":
            if len(arg_nodes) != 3:
                raise self.fail("type", "CopyRepresentation expects (src, dst, count) arguments", node)
            src_b, elem_src, cap_src = self._require_slots_binding(arg_nodes[0], environment)
            dst_b, elem_dst, cap_dst = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_src, elem_dst)
            cnt_t = self._slots_usize_arg(arg_nodes[2], environment)
            if self._is_readonly_span(dst_b.term):
                raise self.fail("type", "cannot copy representation into a read-only 'in Slots' destination", node)
            src_live = _apps(_constant("Slots_LivePrefix"), elem_src, cap_src, src_b.term, cnt_t)
            if not self._prove_bool_precondition(src_live, environment):
                raise self.fail(
                    "type",
                    "cannot prove CopyRepresentation source has LivePrefix(src, count)",
                    node,
                )
            zero_u = _int_term(_INT_SPECS["usize"], 0)
            dst_vacant = _apps(_constant("Slots_VacantRange"), elem_dst, cap_dst, dst_b.term, zero_u, cnt_t)
            if not self._prove_bool_precondition(dst_vacant, environment):
                raise self.fail(
                    "type",
                    "cannot prove CopyRepresentation destination has VacantRange(dst, 0, count)",
                    node,
                )
            self._check_slots_disjoint(elem_src, cap_src, src_b.term, cap_dst, dst_b.term, environment, node)
            return _Binding(
                _apps(
                    _constant("Slots_CopyRepresentation"),
                    elem_src,
                    cap_src,
                    cap_dst,
                    src_b.term,
                    dst_b.term,
                    cnt_t,
                ),
                dst_b.type,
            )
        if member_name == "TransferType":
            if len(arg_nodes) != 3:
                raise self.fail("type", "TransferType expects (ref src, ref dst, count) arguments", node)
            src_b, elem_src, cap_src = self._require_slots_binding(arg_nodes[0], environment)
            dst_b, elem_dst, cap_dst = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_src, elem_dst)
            if gen_args:
                if len(gen_args) != 1:
                    raise self.fail("type", "TransferType accepts at most 1 generic type argument <T>", node)
                ann_elem = self.type(gen_args[0], environment)
                self.unify(elem_src, ann_elem)
            cnt_t = self._slots_usize_arg(arg_nodes[2], environment)
            if self._is_readonly_span(src_b.term) or self._is_readonly_span(dst_b.term):
                raise self.fail("type", "TransferType requires mutable source and destination Slots", node)
            src_can_w = _apps(_constant("Slots_CanWrite"), elem_src, cap_src, src_b.term)
            if not self._prove_bool_precondition(src_can_w, environment):
                raise self.fail("type", "cannot prove TransferType source has write permission (Slots.CanWrite)", node)
            src_live = _apps(_constant("Slots_LivePrefix"), elem_src, cap_src, src_b.term, cnt_t)
            if not self._prove_bool_precondition(src_live, environment):
                raise self.fail("type", "cannot prove TransferType source has LivePrefix(src, count)", node)
            zero_u = _int_term(_INT_SPECS["usize"], 0)
            dst_vacant = _apps(_constant("Slots_VacantRange"), elem_dst, cap_dst, dst_b.term, zero_u, cnt_t)
            if not self._prove_bool_precondition(dst_vacant, environment):
                raise self.fail(
                    "type", "cannot prove TransferType destination has VacantRange(dst, 0, count)", node
                )
            self._check_slots_disjoint(elem_src, cap_src, src_b.term, cap_dst, dst_b.term, environment, node)
            rep_eq = _apps(_constant("Slots_RepEqual"), elem_src, cap_dst, cap_src, dst_b.term, src_b.term, cnt_t)
            if not self._prove_bool_precondition(rep_eq, environment):
                raise self.fail(
                    "type",
                    "cannot prove TransferType representation equality (Slots.RepEqual); call CopyRepresentation before TransferType",
                    node,
                )
            return _Binding(
                _apps(
                    _constant("Slots_TransferType"),
                    elem_src,
                    cap_src,
                    cap_dst,
                    src_b.term,
                    dst_b.term,
                    cnt_t,
                ),
                _term("prod", src_b.type, dst_b.type),
            )
        raise self.fail("name", f"unknown Slots intrinsic 'Slots.{member_name}'", node)

    @staticmethod
    def _dotted_member_path(node: Node) -> str | None:
        if node["kind"] == "name" and isinstance(node.get("name"), dict):
            text = cast("Node", node["name"]).get("text")
            return text if isinstance(text, str) else None
        if node["kind"] == "member" and isinstance(node.get("name"), dict) and isinstance(node.get("value"), dict):
            prefix = _Elaborator._dotted_member_path(cast("Node", node["value"]))
            suffix = cast("Node", node["name"]).get("text")
            if prefix is not None and isinstance(suffix, str):
                return f"{prefix}.{suffix}"
        return None

    def _resolve_int_type_receiver(self, node: Node, environment: dict[str, _Binding]) -> _IntSpec | None:
        path = self._dotted_member_path(node)
        if path is None:
            return None
        if "." not in path:
            if path in environment:
                return None
            binding = self.globals.get(path)
            if binding is not None and binding.type == _SORT:
                return self._int_spec(binding.term)
            return None
        if path.startswith("Vela.Numerics.") and "Vela" not in environment:
            binding = self.globals.get(path)
            if binding is not None and binding.type == _SORT:
                return self._int_spec(binding.term)
        return None

    def _is_unsuffixed_int_expr(self, node: Node) -> bool:
        kind = node["kind"]
        if kind == "nat":
            return cast("str", node.get("suffix", "")) == ""
        if kind == "group":
            return self._is_unsuffixed_int_expr(self.node(node["value"]))
        if kind == "unary" and isinstance(node.get("operator"), dict):
            op = cast("Node", node["operator"]).get("text")
            if op in {"-", "~"}:
                return self._is_unsuffixed_int_expr(self.node(node["value"]))
        if kind == "binary" and isinstance(node.get("operator"), dict):
            op = cast("Node", node["operator"]).get("text")
            if op in {"+", "-", "*", "/", "%", "&", "|", "^"}:
                return self._is_unsuffixed_int_expr(self.node(node["left"])) and self._is_unsuffixed_int_expr(
                    self.node(node["right"])
                )
        return False

    def _check_int_arith_precondition(
        self,
        operator: str,
        spec: _IntSpec,
        left: _Term,
        right: _Term,
        environment: dict[str, _Binding],
        node: Node,
    ) -> None:
        facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
        l_lo, l_hi, l_ne = self._term_bounds(left, spec, facts)
        r_lo, r_hi, r_ne = self._term_bounds(right, spec, facts)
        if l_lo > l_hi or r_lo > r_hi:
            return
        if operator == "+":
            lo = l_lo + r_lo
            hi = l_hi + r_hi
            for fact in facts:
                parsed = self._parse_cmp_fact(fact)
                if parsed is None:
                    continue
                f_op, f_spec, f_l, f_r = parsed
                fl_head, fl_args = self.spine(self.whnf(f_l))
                fr_head, fr_args = self.spine(self.whnf(f_r))
                # Recognize Nat(a) + Nat(b) <= K or a <= K - b
                if (
                    fl_head.kind == "const"
                    and fl_head.value in {"+", f"int_add_{spec.name}"}
                    and len(fl_args) == 2
                    and (
                        (self._same_numeric_subject(fl_args[0], left) and self._same_numeric_subject(fl_args[1], right))
                        or (self._same_numeric_subject(fl_args[0], right) and self._same_numeric_subject(fl_args[1], left))
                    )
                ):
                    _, k_hi, _ = self._term_bounds(f_r, f_spec, facts)
                    if f_op == "le":
                        hi = min(hi, k_hi)
                    elif f_op == "lt":
                        hi = min(hi, k_hi - 1)
                if (
                    fr_head.kind == "const"
                    and fr_head.value in {"-", f"int_sub_{spec.name}"}
                    and len(fr_args) == 2
                    and (
                        (self._same_numeric_subject(f_l, left) and self._same_numeric_subject(fr_args[1], right))
                        or (self._same_numeric_subject(f_l, right) and self._same_numeric_subject(fr_args[1], left))
                    )
                ):
                    _, k_hi, _ = self._term_bounds(fr_args[0], f_spec, facts)
                    if f_op == "le":
                        hi = min(hi, k_hi)
                    elif f_op == "lt":
                        hi = min(hi, k_hi - 1)
            if not (spec.min_val <= lo and hi <= spec.max_val):
                raise self.fail(
                    "type",
                    f"integer addition on '{spec.name}' may overflow ({lo}..{hi} is not within {spec.min_val}..{spec.max_val}); "
                    "prove the range or use WrappingAdd, SaturatingAdd or CheckedAdd",
                    node,
                )
            return
        if operator == "-":
            lo = l_lo - r_hi
            hi = l_hi - r_lo
            if self._same_numeric_subject(left, right):
                lo, hi = 0, 0
            else:
                if self._prove_comparison("ge", spec, left, right, facts):
                    lo = max(lo, 0)
                if self._prove_comparison("gt", spec, left, right, facts):
                    lo = max(lo, 1)
                if self._prove_comparison("le", spec, left, right, facts):
                    hi = min(hi, 0)
            if not (spec.min_val <= lo and hi <= spec.max_val):
                raise self.fail(
                    "type",
                    f"integer subtraction on '{spec.name}' may overflow ({lo}..{hi} is not within {spec.min_val}..{spec.max_val}); "
                    "prove the range or use WrappingSub, SaturatingSub or CheckedSub",
                    node,
                )
            return
        if operator == "*":
            prods = (l_lo * r_lo, l_lo * r_hi, l_hi * r_lo, l_hi * r_hi)
            lo = min(prods)
            hi = max(prods)
            for fact in facts:
                parsed = self._parse_cmp_fact(fact)
                if parsed is None:
                    continue
                f_op, f_spec, f_l, f_r = parsed
                fl_head, fl_args = self.spine(self.whnf(f_l))
                if (
                    fl_head.kind == "const"
                    and fl_head.value in {"*", f"int_mul_{spec.name}"}
                    and len(fl_args) == 2
                    and (
                        (self._same_numeric_subject(fl_args[0], left) and self._same_numeric_subject(fl_args[1], right))
                        or (self._same_numeric_subject(fl_args[0], right) and self._same_numeric_subject(fl_args[1], left))
                    )
                ):
                    _, k_hi, _ = self._term_bounds(f_r, f_spec, facts)
                    if f_op == "le":
                        hi = min(hi, k_hi)
                    elif f_op == "lt":
                        hi = min(hi, k_hi - 1)
            if not (spec.min_val <= lo and hi <= spec.max_val):
                raise self.fail(
                    "type",
                    f"integer multiplication on '{spec.name}' may overflow ({lo}..{hi} is not within {spec.min_val}..{spec.max_val}); "
                    "prove the range or use WrappingMul, SaturatingMul or CheckedMul",
                    node,
                )
            return
        if operator in {"/", "%"}:
            nonzero = (
                r_lo > 0
                or r_hi < 0
                or 0 in r_ne
                or self._prove_comparison("ne", spec, right, _int_term(spec, 0), facts)
            )
            if not nonzero:
                raise self.fail(
                    "type",
                    f"integer {'division' if operator == '/' else 'remainder'} on '{spec.name}' requires a proved nonzero divisor; "
                    f"prove divisor != 0 or use {'CheckedDiv' if operator == '/' else 'CheckedRem'}",
                    node,
                )
            if operator == "/" and spec.signed:
                can_be_min = (
                    l_lo <= spec.min_val <= l_hi
                    and spec.min_val not in l_ne
                    and not self._prove_comparison("ne", spec, left, _int_term(spec, spec.min_val), facts)
                )
                can_be_neg1 = (
                    r_lo <= -1 <= r_hi
                    and -1 not in r_ne
                    and not self._prove_comparison("ne", spec, right, _int_term(spec, -1), facts)
                )
                if can_be_min and can_be_neg1:
                    raise self.fail(
                        "type",
                        f"signed integer division on '{spec.name}' may overflow at {spec.name}.Min / -1; "
                        f"prove dividend != {spec.name}.Min or divisor != -1, or use CheckedDiv",
                        node,
                    )

    def _elaborate_unary(
        self, node: Node, environment: dict[str, _Binding], *, expected_int: _Term | None = None
    ) -> _Binding:
        if isinstance(node["operator"], dict) and node["operator"].get("text") == "ref":
            raise self.fail("type", "ref argument is only supported as the target of Format.Write", node)
        operator = self.operator(node["operator"])
        operand_node = self.node(node["value"])
        if operator == "!":
            value = self.check(operand_node, _BOOL, environment)
            return _Binding(_app(_constant("!"), value), _BOOL)
        if operator == "-" and operand_node["kind"] == "nat":
            suffix = cast("str", operand_node["suffix"])
            mag = _parse_numeric_magnitude(cast("str", operand_node["value"]))
            val = -mag
            if suffix:
                canonical = "u8" if suffix == "byte" else _NUMERICS_ALIASES.get(suffix, suffix)
                spec = _INT_SPECS.get(canonical)
            else:
                spec = self._int_spec(expected_int) if expected_int is not None else None
            if spec is None:
                raise self.fail(
                    "type",
                    "negative integer literal requires a signed integer type annotation or suffix",
                    node,
                )
            if not spec.signed:
                raise self.fail("type", f"unsigned integer type '{spec.name}' does not support negation", node)
            if not spec.min_val <= val <= spec.max_val:
                raise self.fail(
                    "type",
                    f"integer literal {val} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                    node,
                )
            return _Binding(_int_term(spec, val), spec.const)
        if operator in {"-", "~"}:
            if expected_int is not None and self._int_spec(expected_int) is not None:
                operand = _Binding(self.check(operand_node, expected_int, environment), expected_int)
            else:
                operand = self.expression(operand_node, environment)
            spec = self._int_spec(operand.type)
            if spec is None:
                raise self.fail(
                    "type",
                    f"unary operator '{operator}' requires a fixed-width integer operand",
                    node,
                )
            if operator == "~":
                return _Binding(_app(_constant(f"int_not_{spec.name}"), operand.term), spec.const)
            if not spec.signed:
                raise self.fail(
                    "type",
                    f"unsigned integer type '{spec.name}' does not support unary negation; use WrappingNeg if modular negation is intended",
                    node,
                )
            facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
            o_lo, o_hi, o_ne = self._term_bounds(operand.term, spec, facts)
            if (
                o_lo <= o_hi
                and o_lo <= spec.min_val <= o_hi
                and spec.min_val not in o_ne
                and not self._prove_comparison("ne", spec, operand.term, _int_term(spec, spec.min_val), facts)
            ):
                raise self.fail(
                    "type",
                    f"signed negation on '{spec.name}' may overflow at {spec.name}.Min; "
                    f"prove operand != {spec.name}.Min or use WrappingNeg, SaturatingNeg or CheckedNeg",
                    node,
                )
            return _Binding(_app(_constant(f"int_neg_{spec.name}"), operand.term), spec.const)
        raise self.fail("unsupported", f"prefix '{operator}' is unsupported")

    def _elaborate_binary(
        self, node: Node, environment: dict[str, _Binding], *, expected_int: _Term | None = None
    ) -> _Binding:
        operator = self.operator(node["operator"])
        left_node = self.node(node["left"])
        right_node = self.node(node["right"])
        if operator in {"&&", "||", "==>", "<==>"}:
            left_b = _Binding(self.check(left_node, _BOOL, environment), _BOOL)
            if operator in {"&&", "==>"}:
                self.active_facts.append(left_b.term)
                try:
                    right_b = _Binding(self.check(right_node, _BOOL, environment), _BOOL)
                finally:
                    self.active_facts.pop()
            else:
                right_b = _Binding(self.check(right_node, _BOOL, environment), _BOOL)
            return _Binding(_apps(_constant(operator), left_b.term, right_b.term), _BOOL)
        expected_spec = self._int_spec(expected_int) if expected_int is not None else None
        if expected_spec is not None and operator in {"+", "-", "*", "/", "%", "&", "|", "^"}:
            left = _Binding(self.check(left_node, expected_spec.const, environment), expected_spec.const)
            right = _Binding(self.check(right_node, expected_spec.const, environment), expected_spec.const)
        elif self._is_unsuffixed_int_expr(left_node) and not self._is_unsuffixed_int_expr(right_node):
            right = self.expression(right_node, environment)
            if self._int_spec(right.type) is not None:
                left = _Binding(self.check(left_node, right.type, environment), right.type)
            else:
                left = self.expression(left_node, environment)
        elif self._is_unsuffixed_int_expr(right_node) and not self._is_unsuffixed_int_expr(left_node):
            left = self.expression(left_node, environment)
            if self._int_spec(left.type) is not None:
                right = _Binding(self.check(right_node, left.type, environment), left.type)
            else:
                right = self.expression(right_node, environment)
        else:
            left = self.expression(left_node, environment)
            right = self.expression(right_node, environment)
        if operator in {"==", "!="}:
            self.unify(left.type, right.type)
            operand_type = self.whnf(left.type)
            int_spec = self._int_spec(operand_type)
            if int_spec is not None:
                op_name = f"int_{'eq' if operator == '==' else 'ne'}_{int_spec.name}"
                return _Binding(_apps(_constant(op_name), left.term, right.term), _BOOL)
            if operand_type not in {_NAT, _BOOL}:
                raise self.fail("unsupported", "Boolean equality is defined only on Nat, bool and fixed-width integers")
            operation = ("eq_" if operator == "==" else "ne_") + ("nat" if operand_type == _NAT else "bool")
            return _Binding(_apps(_constant(operation), left.term, right.term), _BOOL)
        if self._int_spec(left.type) is not None or self._int_spec(right.type) is not None:
            self.unify(left.type, right.type)
            spec = cast("_IntSpec", self._int_spec(left.type))
            if operator in {"<", "<=", ">", ">="}:
                cmp_map = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
                return _Binding(_apps(_constant(f"int_{cmp_map[operator]}_{spec.name}"), left.term, right.term), _BOOL)
            if operator in {"&", "|", "^"}:
                bit_map = {"&": "and", "|": "or", "^": "xor"}
                return _Binding(
                    _apps(_constant(f"int_{bit_map[operator]}_{spec.name}"), left.term, right.term), spec.const
                )
            if operator in {"+", "-", "*", "/", "%"}:
                self._check_int_arith_precondition(operator, spec, left.term, right.term, environment, node)
                arith_map = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem"}
                return _Binding(
                    _apps(_constant(f"int_{arith_map[operator]}_{spec.name}"), left.term, right.term), spec.const
                )
            raise self.fail("type", f"operator '{operator}' is not defined on integer type '{spec.name}'", node)
        if operator in {"&", "|", "^"}:
            raise self.fail(
                "type",
                f"bitwise operator '{operator}' requires a fixed-width integer operand; Nat does not support bitwise operations",
                node,
            )
        binding = self.globals.get(operator)
        if binding is None:
            raise self.fail("unsupported", f"operator '{operator}' is unsupported")
        signature = self.whnf(binding.type)
        self.unify(left.type, signature.args[0])
        signature = self.whnf(signature.args[1])
        self.unify(right.type, signature.args[0])
        return _Binding(_apps(binding.term, left.term, right.term), signature.args[1])

    def _elaborate_int_intrinsic(
        self,
        name: str,
        arg_nodes: list[Node],
        environment: dict[str, _Binding],
        node: Node,
        *,
        receiver: _Binding | None = None,
        expected_spec: _IntSpec | None = None,
    ) -> _Binding:
        for arg_n in arg_nodes:
            self.node(arg_n, "argument")
        val_nodes = [self.node(a["value"]) for a in arg_nodes]
        unary_ops = {"WrappingNeg": "wrap_neg", "SaturatingNeg": "sat_neg", "CheckedNeg": "chk_neg"}
        shift_ops = {
            "ShiftLeft": "shl",
            "ShiftRight": "shr",
            "WrappingShiftLeft": "wrap_shl",
            "CheckedShiftLeft": "chk_shl",
            "CheckedShiftRight": "chk_shr",
        }
        binary_ops = {
            "WrappingAdd": "wrap_add",
            "WrappingSub": "wrap_sub",
            "WrappingMul": "wrap_mul",
            "SaturatingAdd": "sat_add",
            "SaturatingSub": "sat_sub",
            "SaturatingMul": "sat_mul",
            "CheckedAdd": "chk_add",
            "CheckedSub": "chk_sub",
            "CheckedMul": "chk_mul",
            "CheckedDiv": "chk_div",
            "CheckedRem": "chk_rem",
        }
        is_checked = name.startswith("Checked")
        ae_const = _constant(self.unions["ArithmeticError"].type_const)
        res_const = _constant(self.unions["Result"].type_const)
        if name in unary_ops:
            if receiver is not None:
                if val_nodes:
                    raise self.fail("type", f"'{name}' expects no additional arguments when called on a receiver", node)
                op_binding = receiver
            else:
                if len(val_nodes) != 1:
                    raise self.fail("type", f"'{name}' expects 1 integer argument, got {len(val_nodes)}", node)
                if expected_spec is not None:
                    op_binding = _Binding(
                        self.check(val_nodes[0], expected_spec.const, environment), expected_spec.const
                    )
                else:
                    op_binding = self.expression(val_nodes[0], environment)
            spec = self._int_spec(op_binding.type)
            if spec is None or (expected_spec is not None and spec.name != expected_spec.name):
                raise self.fail("type", f"'{name}' requires a fixed-width integer operand", node)
            ret_type = _apps(res_const, spec.const, ae_const) if is_checked else spec.const
            return _Binding(_app(_constant(f"int_{unary_ops[name]}_{spec.name}"), op_binding.term), ret_type)
        if name in shift_ops:
            if receiver is not None:
                if len(val_nodes) != 1:
                    raise self.fail("type", f"'{name}' expects 1 shift-count argument when called on a receiver", node)
                lhs_binding = receiver
                count_node = val_nodes[0]
            else:
                if len(val_nodes) != 2:
                    raise self.fail("type", f"'{name}' expects (value, count) arguments, got {len(val_nodes)}", node)
                if expected_spec is not None:
                    lhs_binding = _Binding(
                        self.check(val_nodes[0], expected_spec.const, environment), expected_spec.const
                    )
                else:
                    lhs_binding = self.expression(val_nodes[0], environment)
                count_node = val_nodes[1]
            spec = self._int_spec(lhs_binding.type)
            if spec is None or (expected_spec is not None and spec.name != expected_spec.name):
                raise self.fail("type", f"'{name}' requires a fixed-width integer value operand", node)
            count_term = self.check(count_node, _USIZE, environment)
            if not is_checked:
                facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
                c_lo, c_hi, _ = self._term_bounds(count_term, _INT_SPECS["usize"], facts)
                if c_lo <= c_hi:
                    count_ok = c_lo >= 0 and (
                        c_hi < spec.bits
                        or self._prove_comparison(
                            "lt",
                            _INT_SPECS["usize"],
                            count_term,
                            _int_term(_INT_SPECS["usize"], spec.bits),
                            facts,
                        )
                    )
                    if not count_ok:
                        raise self.fail(
                            "type",
                            f"'{name}' on '{spec.name}' requires shift count < {spec.bits}; "
                            f"prove count < {spec.bits} or use Checked{name.removeprefix('Wrapping')}",
                            node,
                        )
                    if name == "ShiftLeft":
                        v_lo, v_hi, _ = self._term_bounds(lhs_binding.term, spec, facts)
                        eff_lo = max(0, c_lo)
                        eff_hi = min(c_hi, spec.bits - 1)
                        shifted = (v_lo << eff_lo, v_lo << eff_hi, v_hi << eff_lo, v_hi << eff_hi)
                        s_lo, s_hi = min(shifted), max(shifted)
                        if not (spec.min_val <= s_lo and s_hi <= spec.max_val):
                            raise self.fail(
                                "type",
                                f"ShiftLeft on '{spec.name}' may overflow ({s_lo}..{s_hi} is not within {spec.min_val}..{spec.max_val}); "
                                "prove the range or use WrappingShiftLeft or CheckedShiftLeft",
                                node,
                            )
            ret_type = _apps(res_const, spec.const, ae_const) if is_checked else spec.const
            return _Binding(
                _apps(_constant(f"int_{shift_ops[name]}_{spec.name}"), lhs_binding.term, count_term), ret_type
            )
        # Binary total/checked arithmetic
        if receiver is not None:
            if len(val_nodes) != 1:
                raise self.fail("type", f"'{name}' expects 1 right-hand argument when called on a receiver", node)
            lhs_b = receiver
            rhs_b = _Binding(self.check(val_nodes[0], lhs_b.type, environment), lhs_b.type)
        else:
            if len(val_nodes) != 2:
                raise self.fail("type", f"'{name}' expects 2 integer arguments, got {len(val_nodes)}", node)
            if expected_spec is not None:
                lhs_b = _Binding(self.check(val_nodes[0], expected_spec.const, environment), expected_spec.const)
                rhs_b = _Binding(self.check(val_nodes[1], expected_spec.const, environment), expected_spec.const)
            elif self._is_unsuffixed_int_expr(val_nodes[0]) and not self._is_unsuffixed_int_expr(val_nodes[1]):
                rhs_b = self.expression(val_nodes[1], environment)
                lhs_b = _Binding(self.check(val_nodes[0], rhs_b.type, environment), rhs_b.type)
            elif self._is_unsuffixed_int_expr(val_nodes[1]) and not self._is_unsuffixed_int_expr(val_nodes[0]):
                lhs_b = self.expression(val_nodes[0], environment)
                rhs_b = _Binding(self.check(val_nodes[1], lhs_b.type, environment), lhs_b.type)
            else:
                lhs_b = self.expression(val_nodes[0], environment)
                rhs_b = self.expression(val_nodes[1], environment)
        self.unify(lhs_b.type, rhs_b.type)
        spec = self._int_spec(lhs_b.type)
        if spec is None or (expected_spec is not None and spec.name != expected_spec.name):
            raise self.fail("type", f"'{name}' requires fixed-width integer operands", node)
        ret_type = _apps(res_const, spec.const, ae_const) if is_checked else spec.const
        return _Binding(
            _apps(_constant(f"int_{binary_ops[name]}_{spec.name}"), lhs_b.term, rhs_b.term), ret_type
        )

    def expression(self, node: Node, environment: dict[str, _Binding]) -> _Binding:
        self.tick()
        self.site = node
        kind = node["kind"]
        if kind == "nat":
            mag = _parse_numeric_magnitude(cast("str", node["value"]))
            suffix = cast("str", node["suffix"])
            if suffix:
                canonical = "u8" if suffix == "byte" else _NUMERICS_ALIASES.get(suffix, suffix)
                spec = _INT_SPECS[canonical]
                if not spec.min_val <= mag <= spec.max_val:
                    raise self.fail(
                        "type",
                        f"integer literal {mag} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                        node,
                    )
                return _Binding(_int_term(spec, mag), spec.const)
            return _Binding(_term("nat", value=mag), _NAT)
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
            recv_node = self.node(node["value"])
            member_name = self.name(node["name"])
            type_spec = self._resolve_int_type_receiver(recv_node, environment)
            if type_spec is not None:
                if member_name == "Min":
                    return _Binding(_int_term(type_spec, type_spec.min_val), type_spec.const)
                if member_name == "Max":
                    return _Binding(_int_term(type_spec, type_spec.max_val), type_spec.const)
                if member_name == "Bits":
                    return _Binding(_term("nat", value=type_spec.bits), _NAT)
                raise self.fail(
                    "name", f"integer type '{type_spec.name}' has no associated member '{member_name}'", node
                )
            full_path = self._dotted_member_path(node)
            if (
                full_path is not None
                and full_path.startswith("Vela.Numerics.")
                and "Vela" not in environment
                and full_path in self.globals
            ):
                return self.lookup(full_path, environment)
            return self._project_member(
                self.expression(recv_node, environment),
                member_name,
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
            call_args = self.nodes(node["arguments"])
            if callee["kind"] == "generic_application":
                base_callee = self.node(callee["value"])
                gen_args = self.nodes(callee["arguments"])
            else:
                base_callee = callee
                gen_args = []
            if base_callee["kind"] == "member":
                receiver = self.node(base_callee["value"])
                member_name = self.name(base_callee["name"])
                if receiver["kind"] == "name" and self.name(receiver["name"]) == "Seq" and "Seq" not in environment:
                    return self._elaborate_seq_intrinsic(node, member_name, gen_args, call_args, environment)
                if receiver["kind"] == "name" and self.name(receiver["name"]) == "Slots" and "Slots" not in environment:
                    return self._elaborate_slots_intrinsic(node, member_name, gen_args, call_args, environment)
                if not gen_args:
                    if (receiver["kind"] == "name"
                            and self.name(receiver["name"]) == "Format"
                            and member_name == "Write"):
                        return self._format_write(node, call_args, environment)
                    if receiver["kind"] == "name" and self.name(receiver["name"]) == "Span" and "Span" not in environment:
                        return self._elaborate_span_intrinsic(node, member_name, call_args, environment)
                    dst_spec = self._resolve_int_type_receiver(receiver, environment)
                    if dst_spec is not None:
                        if member_name in {"From", "TryFrom"}:
                            if len(call_args) != 1:
                                raise self.fail(
                                    "type",
                                    f"'{dst_spec.name}.{member_name}' expects 1 argument, got {len(call_args)}",
                                    node,
                                )
                            self.node(call_args[0], "argument")
                            src_b = self.expression(self.node(call_args[0]["value"]), environment)
                            src_spec = self._int_spec(src_b.type)
                            if member_name == "From":
                                if src_spec is None:
                                    raise self.fail(
                                        "type",
                                        f"'{dst_spec.name}.From' requires a fixed-width integer operand; use '{dst_spec.name}.TryFrom' for Nat",
                                        node,
                                    )
                                if not _allows_from_conversion(src_spec, dst_spec):
                                    raise self.fail(
                                        "type",
                                        f"'{dst_spec.name}.From' does not accept '{src_spec.name}' because the conversion may narrow or change sign; "
                                        f"use '{dst_spec.name}.TryFrom'",
                                        node,
                                    )
                                if src_spec.name == dst_spec.name:
                                    return _Binding(src_b.term, dst_spec.const)
                                return _Binding(
                                    _app(_constant(f"int_from_{src_spec.name}_{dst_spec.name}"), src_b.term),
                                    dst_spec.const,
                                )
                            res_const = _constant(self.unions["Result"].type_const)
                            ce_const = _constant(self.unions["ConversionError"].type_const)
                            ret_type = _apps(res_const, dst_spec.const, ce_const)
                            if src_spec is not None:
                                return _Binding(
                                    _app(_constant(f"int_try_from_{src_spec.name}_{dst_spec.name}"), src_b.term),
                                    ret_type,
                                )
                            if self.whnf(src_b.type) == _NAT:
                                return _Binding(
                                    _app(_constant(f"int_try_from_Nat_{dst_spec.name}"), src_b.term),
                                    ret_type,
                                )
                            raise self.fail(
                                "type",
                                f"'{dst_spec.name}.TryFrom' requires a fixed-width integer or Nat operand",
                                node,
                            )
                        if member_name in _INT_INTRINSICS:
                            return self._elaborate_int_intrinsic(
                                member_name, call_args, environment, node, expected_spec=dst_spec
                            )
                        raise self.fail(
                            "name",
                            f"integer type '{dst_spec.name}' has no associated function '{member_name}'",
                            node,
                        )
                    if self._dotted_member_path(receiver) == "Vela.Numerics" and member_name in _INT_INTRINSICS:
                        return self._elaborate_int_intrinsic(member_name, call_args, environment, node)
                    if (
                        member_name in _INT_INTRINSICS
                        or member_name in {"At", "Update", "Append", "Take", "Skip", "Slice", "Contains", "All", "Any"}
                        or member_name in {"LivePrefix", "VacantRange", "VacantSuffix", "PrefixModel", "Read", "Write"}
                    ):
                        recv_b = self.expression(receiver, environment)
                        if self._int_spec(recv_b.type) is not None and member_name in _INT_INTRINSICS:
                            return self._elaborate_int_intrinsic(
                                member_name, call_args, environment, node, receiver=recv_b
                            )
                        recv_head, recv_targs = self.spine(self.whnf(recv_b.type))
                        if recv_head == _constant("Seq") and len(recv_targs) == 1:
                            return self._elaborate_seq_method(
                                node, recv_b, recv_targs[0], member_name, call_args, environment
                            )
                        if (
                            recv_head == _constant("Slots")
                            and len(recv_targs) == 2
                            and member_name in {"LivePrefix", "VacantRange", "VacantSuffix", "PrefixModel", "Read", "Write"}
                        ):
                            return self._elaborate_slots_intrinsic(
                                node, member_name, gen_args, call_args, environment, receiver=recv_b
                            )
            if base_callee["kind"] == "name":
                cname = self.name(base_callee["name"])
                if cname == "old" and "old" not in environment and not gen_args:
                    if len(call_args) != 1:
                        raise self.fail("type", f"'old(...)' expects 1 argument, got {len(call_args)}", node)
                    self.node(call_args[0], "argument")
                    if call_args[0]["label"] is not None:
                        raise self.fail("name", "'old(...)' does not accept labeled arguments", call_args[0])
                    if not self.entry_env:
                        raise self.fail("type", "'old(...)' requires an enclosing callable pre-state", node)
                    return self.expression(self.node(call_args[0]["value"]), self.entry_env)
                if (
                    cname in {"LivePrefix", "VacantRange", "VacantSuffix", "PrefixModel", "CopyRepresentation", "TransferType"}
                    and cname not in environment
                    and cname not in self.globals
                ):
                    return self._elaborate_slots_intrinsic(node, cname, gen_args, call_args, environment)
                if not gen_args and cname == "Nat" and "Nat" not in environment:
                    if len(call_args) != 1:
                        raise self.fail("type", f"'Nat(...)' expects 1 argument, got {len(call_args)}", node)
                    self.node(call_args[0], "argument")
                    arg_b = self.expression(self.node(call_args[0]["value"]), environment)
                    src_spec = self._int_spec(arg_b.type)
                    if src_spec is not None:
                        if src_spec.signed:
                            raise self.fail(
                                "type",
                                f"'Nat(...)' total injection requires an unsigned integer operand, got signed '{src_spec.name}'",
                                node,
                            )
                        return _Binding(_app(_constant(f"int_to_nat_{src_spec.name}"), arg_b.term), _NAT)
                    if self.whnf(arg_b.type) == _NAT:
                        return arg_b
                    raise self.fail(
                        "type", "'Nat(...)' conversion requires an unsigned fixed-width integer operand", node
                    )
                if not gen_args and cname in _INT_INTRINSICS and cname not in environment and cname not in self.globals:
                    return self._elaborate_int_intrinsic(cname, call_args, environment, node)
            return self.apply(self.expression(callee, environment), call_args, environment)
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
            return self._elaborate_binary(node, environment)
        if kind == "unary":
            return self._elaborate_unary(node, environment)
        if kind == "propagate":
            ret_type = self.current_return_type if self.current_return_type is not None else _UNIT
            return _Binding(
                self._elaborate_propagate(node, environment, ret_type, lambda _name, val, _env: val.term),
                ret_type,
            )
        raise self.fail("unsupported", f"expression '{kind}' requires the full frontend")

    def proposition(self, node: Node, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "group":
            return self.proposition(self.node(node["value"]), environment)
        if node["kind"] == "let_expression":
            return self.proposition(self.node(node["body"]), self.local(self.node(node["binding"]), environment))
        if node["kind"] == "binary":
            operator = self.operator(node["operator"])
            if operator == "==":
                left_node = self.node(node["left"])
                right_node = self.node(node["right"])
                if self._is_unsuffixed_int_expr(left_node) and not self._is_unsuffixed_int_expr(right_node):
                    right_b = self.expression(right_node, environment)
                    left_t = self.check(left_node, right_b.type, environment)
                    self.unify(self.infer(right_b.type), _SORT)
                    return _apps(_constant("Eq"), right_b.type, left_t, right_b.term)
                left = self.expression(left_node, environment)
                right = self.check(right_node, left.type, environment)
                self.unify(self.infer(left.type), _SORT)
                return _apps(_constant("Eq"), left.type, left.term, right)
            if operator == "==>":
                domain = self.proposition(self.node(node["left"]), environment)
                return self.pi(domain, self.proposition(self.node(node["right"]), environment))
        if node["kind"] == "quantifier":
            quant = node["quantifier"]
            if quant not in {"forall", "exists"}:
                raise self.fail("unsupported", "only universal and existential propositions are supported")
            variables, extended = self.telescope([], self.nodes(node["parameters"]), environment)
            body = self.proposition(self.node(node["value"]), extended)
            if quant == "forall":
                return self.wrap("pi", variables, body)
            result = body
            for variable in reversed(variables):
                domain = self.types[cast("int", variable.value)]
                result = _term("ex", domain, _term("lam", domain, result, value=variable.value))
            return result
        value = self.expression(node, environment)
        self.unify(value.type, _PROP)
        return value.term

    def complete(self, term: _Term, seen: dict[int, _Term] | None = None) -> None:
        if seen is None:
            seen = {}
        tid = id(term)
        if tid in seen:
            return
        seen[tid] = term
        self.tick()
        term = self.resolve(term)
        if term.kind == "meta":
            raise self.fail("inference", "unresolved inference variable; add a type or generic argument")
        for child in term.args:
            self.complete(child, seen)

    def _evict_builtin_if_shadowed(self, name: str) -> None:
        if name in self.builtin_unions:
            self.builtin_unions.discard(name)
            uinfo = self.unions.pop(name, None)
            self.globals.pop(name, None)
            if uinfo is not None:
                for uc in uinfo.constructors:
                    if uc.name in self.builtin_union_ctors:
                        self.builtin_union_ctors.discard(uc.name)
                        self.union_ctors.pop(uc.name, None)
                        self.globals.pop(uc.name, None)
        elif name in self.builtin_union_ctors:
            self.builtin_union_ctors.discard(name)
            self.union_ctors.pop(name, None)
            self.globals.pop(name, None)

    def _record_declaration(self, node: Node, first_meta: int) -> None:
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"}
        if (not isinstance(modifiers, list)
                or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", node)
        record_contracts = self.nodes(node["contracts"])
        for c_node in record_contracts:
            self.node(c_node, "contract")
            if c_node["role"] != "invariant":
                raise self.fail("unsupported", f"record contract '{c_node['role']}' is not supported", c_node)
        name = self.name(node["name"])
        self._evict_builtin_if_shadowed(name)
        if (name in self.globals or name in self.records or name in self.unions
                or name in self.union_ctors or name in {"Type", "_", "this"} or "." in name):
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
        is_dependent = False
        for idx, fv in enumerate(field_vars):
            ftype = self.types[cast("int", fv.value)]
            if any(cast("int", earlier.value) in self.free(ftype) for earlier in field_vars[:idx]):
                is_dependent = True
                break
        tail_sig_types: tuple[_Term, ...] = ()
        if not field_vars:
            rep_type = _UNIT
        elif len(field_vars) == 1:
            rep_type = _term("prod", self.types[cast("int", field_vars[0].value)], _UNIT)
        elif is_dependent:
            curr_type = self.types[cast("int", field_vars[-1].value)]
            tail_sigs_rev: list[_Term] = [curr_type]
            for fv in reversed(field_vars[:-1]):
                fv_id = cast("int", fv.value)
                fv_type = self.types[fv_id]
                curr_type = _term("sigT", fv_type, _term("lam", fv_type, curr_type, value=fv_id))
                tail_sigs_rev.append(curr_type)
            tail_sigs_rev.reverse()
            tail_sig_types = tuple(tail_sigs_rev)
            rep_type = tail_sig_types[0]
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
        elif is_dependent:
            ctor_vars = [*generic_vars, *field_vars]
            ctor_body = field_vars[-1]
            for idx in range(len(field_vars) - 2, -1, -1):
                fv = field_vars[idx]
                sig_ty = tail_sig_types[idx]
                ctor_body = _term("existT", sig_ty.args[0], sig_ty.args[1], fv, ctor_body)
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
            proj_ret_type = ftype
            if len(field_vars) == 1:
                proj_body = _apps(_constant("Fst"), ftype, _UNIT, self_var)
            elif is_dependent:
                curr_term = self_var
                curr_sig = rep_type
                for step in range(idx):
                    step_val = _term("projT1", curr_sig.args[0], curr_sig.args[1], curr_term)
                    curr_term = _term("projT2", curr_sig.args[0], curr_sig.args[1], curr_term)
                    curr_sig = self.substitute(curr_sig.args[1].args[1], cast("int", curr_sig.args[1].value), step_val)
                    earlier_rf = record_fields[step]
                    proj_call = _apps(_constant(earlier_rf.proj_const), *generic_vars, self_var)
                    proj_ret_type = self.substitute(proj_ret_type, cast("int", earlier_rf.var.value), proj_call)
                if idx < len(field_vars) - 1:
                    curr_term = _term("projT1", curr_sig.args[0], curr_sig.args[1], curr_term)
                proj_body = curr_term
            else:
                curr_term = self_var
                curr_type = rep_type
                for _ in range(idx):
                    curr_term = _apps(_constant("Snd"), curr_type.args[0], curr_type.args[1], curr_term)
                    curr_type = curr_type.args[1]
                if idx < len(field_vars) - 1:
                    curr_term = _apps(_constant("Fst"), curr_type.args[0], curr_type.args[1], curr_term)
                proj_body = curr_term
            proj_sig = self.wrap("pi", proj_vars, proj_ret_type)
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
            is_dependent=is_dependent,
            tail_sig_types=tail_sig_types,
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
            for idx, rf in enumerate(record_fields):
                if rf.name not in generic_env:
                    rf_type = self._instantiate_record_field_type(record_info, list(generic_vars), idx, self_var)
                    prop_env[rf.name] = _Binding(_apps(_constant(rf.proj_const), *generic_vars, self_var), rf_type)
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

        invariants_list: list[_RecordInvariant] = []
        seen_inv_names: set[str] = set()
        for inv_idx, c_node in enumerate(record_contracts):
            self.site = c_node
            inv_first_meta = len(self.metas)
            raw_cname = c_node.get("name")
            if raw_cname is not None:
                cname = self.name(raw_cname)
                if cname in seen_inv_names:
                    raise self.fail("name", f"duplicate invariant clause name '{cname}' on record '{name}'", c_node)
                seen_inv_names.add(cname)
            else:
                cname = f"__anon_invariant_{inv_idx}"
            self_var = self.fresh(record_type_app)
            inv_env = dict(generic_env)
            inv_env["this"] = _Binding(self_var, record_type_app)
            for idx, rf in enumerate(record_fields):
                if rf.name not in generic_env:
                    rf_type = self._instantiate_record_field_type(record_info, list(generic_vars), idx, self_var)
                    inv_env[rf.name] = _Binding(_apps(_constant(rf.proj_const), *generic_vars, self_var), rf_type)
            for pname, rp in record_info.properties.items():
                if pname not in generic_env:
                    rp_type = self.substitute(rp.type, cast("int", rp.self_var.value), self_var)
                    inv_env[pname] = _Binding(_apps(_constant(rp.prop_const), *generic_vars, self_var), rp_type)
            val_node = self.node(c_node["value"])
            saved_inv_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            try:
                inv_b = self.expression(val_node, inv_env)
                inv_w = self.whnf(inv_b.type)
                if inv_w == _BOOL or self._is_prop_type(inv_w):
                    inv_term, inv_type = inv_b.term, inv_w
                else:
                    self.metas = saved_inv_metas
                    inv_term = self.proposition(val_node, inv_env)
                    inv_type = _PROP
            except VelaError:
                self.metas = saved_inv_metas
                inv_term = self.proposition(val_node, inv_env)
                inv_type = _PROP
            self.site = c_node
            self.complete(inv_term)
            self.complete(inv_type)
            for index in range(inv_first_meta, len(self.metas)):
                self.complete(_term("meta", value=index))
                self.complete(self.metas[index].type)
            invariants_list.append(_RecordInvariant(cname, self_var, inv_term, inv_type, c_node))
        record_info.invariants = tuple(invariants_list)

    def _union_declaration(self, node: Node, first_meta: int) -> None:
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"}
        if (not isinstance(modifiers, list)
                or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", node)
        self.no_roles(node, "contracts")
        name = self.name(node["name"])
        self._evict_builtin_if_shadowed(name)
        if (name in self.globals or name in self.records or name in self.unions
                or name in self.union_ctors or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'", node)
        generics = self.nodes(node["generics"])
        constructors = self.nodes(node["constructors"])
        if not constructors:
            raise self.fail("unsupported", "empty union declarations require the full frontend", node)
        generic_vars, generic_env = self.telescope(generics, [], {}, unit=False)
        seen_ctors: set[str] = set()
        ctor_specs: list[tuple[Node, str, list[str], list[_Term], _Term, bool, tuple[_Term, ...]]] = []
        for ctor_node in constructors:
            self.node(ctor_node, "constructor")
            self.no_roles(ctor_node, "contracts")
            if ctor_node["result"] is not None:
                raise self.fail(
                    "unsupported",
                    "indexed union constructor result clauses require the full frontend",
                    ctor_node,
                )
            cname = self.name(ctor_node["name"])
            self._evict_builtin_if_shadowed(cname)
            if (cname in self.globals or cname in self.records or cname in self.unions
                    or cname in self.union_ctors or cname == name or cname in seen_ctors
                    or cname in {"Type", "_", "this"} or "." in cname):
                raise self.fail("name", f"duplicate or reserved union constructor '{cname}'", ctor_node)
            seen_ctors.add(cname)
            cparams = self.nodes(ctor_node["parameters"])
            for param_node in cparams:
                self.node(param_node, "parameter")
                if param_node["name"] is None:
                    raise self.fail("protocol", "union constructor field requires an explicit name", param_node)
                fname = self.name(param_node["name"])
                if fname in {"Type", "_", "this"} or "." in fname:
                    raise self.fail("name", f"invalid or reserved union constructor field name '{fname}'", param_node)
                if param_node.get("const", False):
                    raise self.fail("unsupported", "union constructor fields cannot be marked const", param_node)
            field_vars, _ = self.telescope([], cparams, generic_env, unit=False)
            field_names = [self.name(p["name"]) for p in cparams]
            is_dep = False
            for idx, fv in enumerate(field_vars):
                ftype = self.types[cast("int", fv.value)]
                if any(cast("int", earlier.value) in self.free(ftype) for earlier in field_vars[:idx]):
                    is_dep = True
                    break
            tail_sig_types: tuple[_Term, ...] = ()
            if not field_vars:
                payload_type = _UNIT
            elif len(field_vars) == 1:
                f0_type = self.types[cast("int", field_vars[0].value)]
                payload_type = _term("prod", f0_type, _UNIT) if len(constructors) == 1 else f0_type
            elif is_dep:
                curr_type = self.types[cast("int", field_vars[-1].value)]
                tail_sigs_rev: list[_Term] = [curr_type]
                for fv in reversed(field_vars[:-1]):
                    fv_id = cast("int", fv.value)
                    fv_type = self.types[fv_id]
                    curr_type = _term("sigT", fv_type, _term("lam", fv_type, curr_type, value=fv_id))
                    tail_sigs_rev.append(curr_type)
                tail_sigs_rev.reverse()
                tail_sig_types = tuple(tail_sigs_rev)
                payload_type = tail_sig_types[0]
            else:
                payload_type = self.types[cast("int", field_vars[-1].value)]
                for fv in reversed(field_vars[:-1]):
                    payload_type = _term("prod", self.types[cast("int", fv.value)], payload_type)
            ctor_specs.append((ctor_node, cname, field_names, field_vars, payload_type, is_dep, tail_sig_types))

        payload_types = [spec[4] for spec in ctor_specs]
        if len(constructors) == 1:
            suffix_types = [payload_types[0]]
            rep_type = payload_types[0]
        else:
            suffix_types = [payload_types[-1]]
            for pt in reversed(payload_types[:-1]):
                suffix_types.append(_term("sum", pt, suffix_types[-1]))
            suffix_types.reverse()
            rep_type = suffix_types[0]
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

        union_type_app = _apps(_constant(type_emitted), *generic_vars)
        union_ctors: list[_UnionCtor] = []
        for idx, (ctor_node, cname, field_names, field_vars, payload_type, is_dep, tail_sig_types) in enumerate(ctor_specs):
            self.site = ctor_node
            if not field_vars:
                unit_var = self.fresh(_UNIT)
                self.nullary_parameters.add(cast("int", unit_var.value))
                ctor_vars = [*generic_vars, unit_var]
                payload_val = _term("unit")
            elif len(field_vars) == 1:
                ctor_vars = [*generic_vars, field_vars[0]]
                f0_type = self.types[cast("int", field_vars[0].value)]
                payload_val = (
                    _term("pair", f0_type, _UNIT, field_vars[0], _term("unit"))
                    if len(constructors) == 1
                    else field_vars[0]
                )
            elif is_dep:
                ctor_vars = [*generic_vars, *field_vars]
                payload_val = field_vars[-1]
                for f_idx in range(len(field_vars) - 2, -1, -1):
                    fv = field_vars[f_idx]
                    sig_ty = tail_sig_types[f_idx]
                    payload_val = _term("existT", sig_ty.args[0], sig_ty.args[1], fv, payload_val)
            else:
                ctor_vars = [*generic_vars, *field_vars]
                payload_val = field_vars[-1]
                acc_type = self.types[cast("int", field_vars[-1].value)]
                for fv in reversed(field_vars[:-1]):
                    fv_type = self.types[cast("int", fv.value)]
                    payload_val = _term("pair", fv_type, acc_type, fv, payload_val)
                    acc_type = _term("prod", fv_type, acc_type)
            if len(constructors) == 1:
                ctor_body = payload_val
            else:
                ctor_body = (
                    _term("inl", payload_types[idx], suffix_types[idx + 1], payload_val)
                    if idx < len(constructors) - 1
                    else payload_val
                )
                for j in range(idx - 1, -1, -1):
                    ctor_body = _term("inr", payload_types[j], suffix_types[j + 1], ctor_body)
            ctor_sig = self.wrap("pi", ctor_vars, union_type_app)
            ctor_def = self.wrap("lam", ctor_vars, ctor_body)
            self.complete(ctor_sig)
            self.complete(ctor_def)
            ctor_emitted = f"vela_d{len(self.output)}_{name}_{cname}"
            self.output.append(f"Definition {ctor_emitted} : {self.render(ctor_sig)} :=\n  {self.render(ctor_def)}.")
            ctor_binding = _Binding(_constant(ctor_emitted), ctor_sig, len(generics))
            self.globals[cname] = ctor_binding
            self.constants[ctor_emitted] = ctor_binding
            ctor_fields = tuple(
                _RecordField(fname, fvar, self.types[cast("int", fvar.value)], "")
                for fname, fvar in zip(field_names, field_vars, strict=True)
            )
            union_ctors.append(
                _UnionCtor(
                    name=cname,
                    ctor_const=ctor_emitted,
                    ctor_binding=ctor_binding,
                    fields=ctor_fields,
                    payload_type=payload_type,
                    index=idx,
                    is_dependent=is_dep,
                    tail_sig_types=tail_sig_types,
                )
            )

        union_info = _UnionInfo(
            name=name,
            type_const=type_emitted,
            type_binding=type_binding,
            generic_vars=tuple(generic_vars),
            constructors=tuple(union_ctors),
            suffix_types=tuple(suffix_types),
        )
        self.unions[name] = union_info
        self.unions_by_type[type_emitted] = union_info
        for uc in union_ctors:
            self.union_ctors[uc.name] = (union_info, uc)
            self.unions_by_ctor[uc.ctor_const] = (union_info, uc)

    def _has_unapplied_rec_var(self, term: _Term, rec_var_id: int) -> bool:
        term = self.resolve(term)
        if term.kind == "var":
            return cast("int", term.value) == rec_var_id
        if term.kind == "app":
            head, arguments = self.spine(term)
            if head.kind == "var" and cast("int", head.value) == rec_var_id:
                expected_arity = len(self.current_rec_generics) + len(self.current_rec_params)
                if len(arguments) < expected_arity:
                    return True
                return any(self._has_unapplied_rec_var(arg, rec_var_id) for arg in arguments)
            return self._has_unapplied_rec_var(head, rec_var_id) or any(
                self._has_unapplied_rec_var(arg, rec_var_id) for arg in arguments
            )
        return any(self._has_unapplied_rec_var(child, rec_var_id) for child in term.args)

    def declaration(self, node: Node) -> None:
        self.site = node
        self.work = MAX_WORK
        self.reductions = MAX_REDUCTIONS
        first_meta = len(self.metas)
        self.decl_first_meta = first_meta
        self.whnf_cache.clear()
        self.mutable_locals.clear()
        self.entry_env = {}
        self.final_ref_bindings = {}
        self.final_return_facts = []
        self.frozen_collections.clear()
        self.lifted_invariants.clear()
        self.active_lift_scopes = 0
        self.in_loop_depth = 0
        kind = node["kind"]
        if kind == "import":
            imp_name = self.name(node["name"])
            if imp_name != "Vela.Numerics":
                raise self.fail("unsupported", f"import '{imp_name}' requires the full frontend", node)
            for alias_name, target_name in _NUMERICS_ALIASES.items():
                if (alias_name in self.globals and self.globals[alias_name] != self.globals[target_name]) or (
                    alias_name in self.records or alias_name in self.unions or alias_name in self.union_ctors
                ):
                    raise self.fail("name", f"import alias '{alias_name}' conflicts with an existing declaration", node)
                self.globals[alias_name] = self.globals[target_name]
            return
        if kind == "record":
            self._record_declaration(node, first_meta)
            return
        if kind == "union":
            self._union_declaration(node, first_meta)
            return
        if kind not in {"alias", "definition", "function", "property", "theorem", "lemma", "constant"}:
            raise self.fail("unsupported", f"declaration '{kind}' requires the full frontend")
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"} | ({"const"} if kind in {"definition", "function"} else set())
        if (not isinstance(modifiers, list) or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers")
        decreases_clauses: list[Node] = []
        requires_clauses: list[Node] = []
        ensures_clauses: list[Node] = []
        restores_clauses: list[Node] = []
        if kind in {"definition", "function", "theorem", "lemma"}:
            self.no_roles(node, "cancel")
            has_params_or_generics = (
                kind in {"theorem", "lemma", "function"}
                or bool(self.nodes(node["parameters"]) or self.nodes(node["generics"]))
            )
            for contract in self.nodes(node["contracts"]):
                self.node(contract, "contract")
                role = contract["role"]
                if role == "decreases":
                    decreases_clauses.append(contract)
                elif role == "requires" and has_params_or_generics:
                    requires_clauses.append(contract)
                elif role == "ensures" and has_params_or_generics:
                    ensures_clauses.append(contract)
                elif role == "restores" and kind in {"definition", "function"} and has_params_or_generics:
                    restores_clauses.append(contract)
                else:
                    raise self.fail(
                        "unsupported",
                        f"contract '{role}' requires the full frontend",
                        contract,
                    )
            if len(decreases_clauses) > 1:
                raise self.fail("type", "at most one decreases clause is permitted", decreases_clauses[1])
            if kind in {"theorem", "lemma"} and not ensures_clauses:
                raise self.fail("protocol", "theorem requires at least one ensures clause", node)
        else:
            self.no_roles(node, "contracts", "cancel")
        name = self.name(node["name"])
        self._evict_builtin_if_shadowed(name)
        if (name in self.globals or name in self.records or name in self.unions
                or name in self.union_ctors or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'")
        generics = [] if kind in {"constant", "property"} else self.nodes(node["generics"])
        parameters = [] if kind in {"alias", "constant", "property"} else self.nodes(node["parameters"])
        variables, environment = self.telescope(
            generics, parameters, {}, unit=kind not in {"alias", "constant", "property"}
        )
        ref_param_names = set(self.mutable_locals)
        self.entry_env = dict(environment)
        self.final_ref_bindings = dict(environment)
        is_recursive = False
        self_var: _Term | None = None
        candidates: list[tuple[int, int]] = []
        req_bool_terms: list[_Term] = []
        req_vars: list[_Term] = []
        if kind == "constant":
            evaluated = self.constant_value(node, environment)
            body, result = evaluated.term, evaluated.type
            signature = self.wrap("pi", variables, result)
        elif kind == "property":
            result = self.type(self.node(node["type"]), environment)
            prev_ret = self.current_return_type
            self.current_return_type = result
            try:
                body = self.check(self.node(node["value"]), result, environment)
            finally:
                self.current_return_type = prev_ret
            signature = self.wrap("pi", variables, result)
        elif kind == "alias":
            body = self.type(self.node(node["type"]), environment)
            result = self.infer(body)
            signature = self.wrap("pi", variables, result)
        else:
            req_props: list[_Term] = []
            if kind in {"theorem", "lemma"}:
                for req_contract in requires_clauses:
                    req_val_node = self.node(req_contract["value"])
                    req_prop = self.asserted_proposition(req_val_node, environment)
                    req_props.append(req_prop)
                    if req_prop.kind == "app":
                        head_p, args_p = self.spine(req_prop)
                        if (
                            head_p.kind == "const"
                            and head_p.value == "Eq"
                            and len(args_p) == 3
                            and self.whnf(args_p[0]) == _BOOL
                        ):
                            rhs_w = self.whnf(args_p[2])
                            if rhs_w.kind == "bool" and rhs_w.value == 1:
                                req_bool_terms.append(args_p[1])
            else:
                for req_idx, req_contract in enumerate(requires_clauses):
                    req_val_node = self.node(req_contract["value"])
                    saved_req_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                    req_val: _Binding | None = None
                    if req_val_node["kind"] != "quantifier":
                        try:
                            req_val = self.expression(req_val_node, environment)
                        except VelaError:
                            self.metas = saved_req_metas
                            req_val = None
                    if req_val is not None and self.whnf(req_val.type) == _BOOL:
                        req_bool_terms.append(req_val.term)
                        eq_prop = _apps(_constant("Eq"), _BOOL, req_val.term, _term("bool", value=1))
                        req_var = self.fresh(eq_prop)
                        req_vars.append(req_var)
                        environment[f"__vela_req_{req_idx}"] = _Binding(req_var, eq_prop)
                    else:
                        self.metas = saved_req_metas
                        req_prop = self.proposition(req_val_node, environment)
                        req_var = self.fresh(req_prop)
                        req_vars.append(req_var)
                        environment[f"__vela_req_{req_idx}"] = _Binding(req_var, req_prop)
                        if req_prop.kind == "app":
                            head_p, args_p = self.spine(req_prop)
                            if (
                                head_p.kind == "const"
                                and head_p.value == "Eq"
                                and len(args_p) == 3
                                and self.whnf(args_p[0]) == _BOOL
                            ):
                                rhs_w = self.whnf(args_p[2])
                                if rhs_w.kind == "bool" and rhs_w.value == 1:
                                    req_bool_terms.append(args_p[1])
            if kind in {"theorem", "lemma"}:
                if len(ensures_clauses) > 1:
                    raise self.fail(
                        "unsupported",
                        "multiple ensures clauses on a theorem require the full frontend",
                        ensures_clauses[1],
                    )
                self.active_facts.extend(req_bool_terms)
                try:
                    result = self.proposition(self.node(ensures_clauses[0]["value"]), environment)
                finally:
                    for _ in req_bool_terms:
                        self.active_facts.pop()
                for req_prop in reversed(req_props):
                    result = self.pi(req_prop, result)
                if node["body"] is None:
                    raise self.fail("unsupported", "a theorem requires a complete explicit proof body", node)
                body_node = self.node(node["body"])
            else:
                result = self.type(self.node(node["result"]), environment)
                raw_body = node["value"] if kind == "definition" else node["body"]
                if raw_body is None:
                    raise self.fail("unsupported", "abstract callable signatures have no emitted implementation", node)
                body_node = self.node(raw_body)
            generic_vars = variables[:len(generics)]
            param_vars = variables[len(generics):]
            if decreases_clauses:
                dec_contract = decreases_clauses[0]
                dec_val = self.node(dec_contract["value"])
                if dec_val["kind"] != "name":
                    raise self.fail("type", "decreases clause must name a structural parameter", dec_val)
                dec_param_name = self.name(dec_val["name"])
                matched_idx: int | None = None
                for p_idx, p_node in enumerate(parameters):
                    if p_node["name"] is not None and self.name(p_node["name"]) == dec_param_name:
                        matched_idx = p_idx
                        break
                if matched_idx is None:
                    if dec_param_name in environment or dec_param_name in self.globals:
                        raise self.fail(
                            "type",
                            f"decreases clause '{dec_param_name}' must name a value parameter",
                            dec_val,
                        )
                    raise self.fail("name", f"unknown parameter '{dec_param_name}' in decreases clause", dec_val)
                p_var = param_vars[matched_idx]
                if self.whnf(self.types[cast("int", p_var.value)]) != _NAT:
                    raise self.fail(
                        "type",
                        f"decreases parameter '{dec_param_name}' must have type Nat",
                        dec_val,
                    )
                candidates = [(matched_idx, cast("int", p_var.value))]
            else:
                candidates = [
                    (p_idx, cast("int", param_vars[p_idx].value))
                    for p_idx in range(len(parameters))
                    if self.whnf(self.types[cast("int", param_vars[p_idx].value)]) == _NAT
                ]
            signature = self.wrap("pi", variables, result)
            self_var = self.fresh(signature)
            self_binding = _Binding(self_var, signature, len(generics))
            body_env = dict(environment)
            if name not in body_env:
                body_env[name] = self_binding
            self.current_rec_var = self_var
            self.current_rec_name = name
            self.current_rec_generics = list(generic_vars)
            self.current_rec_params = list(param_vars)
            self.current_rec_candidates = candidates
            self.smaller_vars = {p_var_id: set() for _, p_var_id in candidates}
            self.current_return_type = result
            entry_body_facts = [*req_bool_terms, *self._fact_bool_terms((), environment)]
            saved_body_facts = list(self.active_facts)
            self.active_facts.extend(entry_body_facts)
            try:
                body = self.check(body_node, result, body_env)
                if self._has_unapplied_rec_var(body, cast("int", self_var.value)):
                    raise self.fail("type", f"recursive reference to '{name}' must be a direct call", body_node)
                is_recursive = self.current_rec_used
                if is_recursive:
                    candidates = list(self.current_rec_candidates)
                if kind in {"definition", "function"}:
                    for pname in ref_param_names:
                        if pname in self.final_ref_bindings:
                            fin_b = self.final_ref_bindings[pname]
                            fin_head, fin_targs = self.spine(self.whnf(fin_b.type))
                            if (
                                fin_head.kind == "const"
                                and isinstance(fin_head.value, str)
                                and fin_head.value in self.records_by_type
                            ):
                                rinfo = self.records_by_type[fin_head.value]
                                self._check_record_invariants(
                                    rinfo, fin_targs, fin_b.term, self.final_ref_bindings, body_node
                                )
            finally:
                self.active_facts = saved_body_facts
                self.current_rec_var = None
                self.current_rec_name = None
                self.current_rec_generics = []
                self.current_rec_params = []
                self.current_rec_candidates = []
                self.current_rec_used = False
                self.smaller_vars = {}
                self.current_return_type = None
        lam_body = self.wrap("lam", variables, body)
        if is_recursive and self_var is not None:
            struct_p_idx, struct_var_id = candidates[0]
            struct_arity_index = len(generics) + struct_p_idx
            definition = _term(
                "fix",
                signature,
                lam_body,
                _term("nat", value=struct_var_id),
                _term("nat", value=struct_arity_index),
                value=self_var.value,
            )
        else:
            definition = lam_body
        self.site = node
        self.complete(signature)
        self.complete(definition)
        for index in range(first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)
        emitted = f"vela_d{len(self.output)}_{name}"
        if is_recursive and self_var is not None:
            self.fix_names[cast("int", self_var.value)] = emitted
        self.output.append(f"Definition {emitted} : {self.render(signature)} :=\n  {self.render(definition)}.")
        binding = _Binding(_constant(emitted), signature, len(generics), constant=kind == "constant")
        self.globals[name] = binding
        # Generated references never become names in the source namespace.
        self.constants[emitted] = binding
        self.definitions[emitted] = definition
        if req_bool_terms and kind in {"definition", "function"}:
            param_ids = tuple(cast("int", v.value) for v in variables)
            self.callable_preconditions[emitted] = [(param_ids, req_t) for req_t in req_bool_terms]
        if (ensures_clauses or restores_clauses) and kind in {"definition", "function"}:
            post_env = dict(environment)
            for pname in ref_param_names:
                if pname in self.final_ref_bindings:
                    post_env[pname] = self.final_ref_bindings[pname]
            call_term = _apps(_constant(emitted), *variables)
            post_env["result"] = _Binding(call_term, result)
            post_vars = [*variables, *req_vars]
            post_var_ids = {cast("int", v.value) for v in post_vars}
            saved_post_facts = list(self.active_facts)
            self.active_facts.extend(
                [
                    *req_bool_terms,
                    *self.final_return_facts,
                    *self._fact_bool_terms((), self.entry_env),
                    *self._fact_bool_terms((), post_env),
                ]
            )
            try:
                span_u8 = _app(_constant("Span"), _U8)
                for rest_idx, rest_contract in enumerate(restores_clauses):
                    rest_val_node = self.node(rest_contract["value"])
                    if rest_val_node["kind"] == "name":
                        target_param_name = self.name(rest_val_node["name"])
                        if target_param_name not in environment:
                            raise self.fail(
                                "name",
                                f"unknown parameter '{target_param_name}' in restores clause",
                                rest_val_node,
                            )
                        param_b = environment[target_param_name]
                        param_ty_w = self.whnf(param_b.type)
                        p_head, p_args = self.spine(param_ty_w)
                        if param_ty_w == span_u8:
                            if self._is_readonly_span(param_b.term):
                                raise self.fail(
                                    "type",
                                    f"restores parameter '{target_param_name}' cannot be a read-only 'in Span<byte>' borrow",
                                    rest_val_node,
                                )
                            if self.whnf(result) == span_u8:
                                restored_span_term = call_term
                            else:
                                res_head, _ = self.spine(self.whnf(result))
                                if (
                                    res_head.kind == "const"
                                    and isinstance(res_head.value, str)
                                    and res_head.value in self.records_by_type
                                    and any(rf.name == "RestoredDst" for rf in self.records_by_type[res_head.value].fields)
                                ):
                                    restored_span_term = self._project_member(
                                        post_env["result"], "RestoredDst", rest_contract
                                    ).term
                                elif (
                                    target_param_name in ref_param_names
                                    and target_param_name in self.final_ref_bindings
                                    and self.free(self.final_ref_bindings[target_param_name].term) <= post_var_ids
                                ):
                                    restored_span_term = self.final_ref_bindings[target_param_name].term
                                else:
                                    raise self.fail(
                                        "type",
                                        f"restores clause for '{target_param_name}' requires a Span<byte> return type or RestoredDst record field",
                                        rest_contract,
                                    )
                            for field_tag, eq_ty in (
                                ("Base", _USIZE),
                                ("Length", _USIZE),
                                ("Tag", _BOOL),
                                ("PermRead", _BOOL),
                                ("PermWrite", _BOOL),
                            ):
                                self.work = MAX_WORK
                                self.reductions = MAX_REDUCTIONS
                                lhs_f = _apps(_constant(f"Span_{field_tag}"), _U8, restored_span_term)
                                rhs_f = _apps(_constant(f"Span_{field_tag}"), _U8, param_b.term)
                                rest_prop = _apps(_constant("Eq"), eq_ty, lhs_f, rhs_f)
                                rest_proof = self._prove_proposition(rest_prop, post_env, (), rest_contract)
                                rest_sig = self.wrap("pi", post_vars, rest_prop)
                                rest_def = self.wrap("lam", post_vars, rest_proof)
                                self.complete(rest_sig)
                                self.complete(rest_def)
                                rest_emitted = f"{emitted}_restores_{rest_idx}_{field_tag}"
                                self.output.append(
                                    f"Definition {rest_emitted} : {self.render(rest_sig)} :=\n  {self.render(rest_def)}."
                                )
                                self.constants[rest_emitted] = _Binding(_constant(rest_emitted), rest_sig, len(generics))
                                self.definitions[rest_emitted] = rest_def
                        elif p_head == _constant("Slots") and len(p_args) == 2:
                            elem_t, cap_t = p_args
                            if self._is_readonly_span(param_b.term):
                                raise self.fail(
                                    "type",
                                    f"restores parameter '{target_param_name}' cannot be a read-only 'in' borrow",
                                    rest_val_node,
                                )
                            if self.whnf(result) == param_ty_w:
                                restored_slots_term = call_term
                            elif (
                                target_param_name in ref_param_names
                                and target_param_name in self.final_ref_bindings
                                and self.free(self.final_ref_bindings[target_param_name].term) <= post_var_ids
                            ):
                                restored_slots_term = self.final_ref_bindings[target_param_name].term
                            else:
                                res_head, _ = self.spine(self.whnf(result))
                                if (
                                    res_head.kind == "const"
                                    and isinstance(res_head.value, str)
                                    and res_head.value in self.records_by_type
                                    and any(rf.name == "RestoredDst" for rf in self.records_by_type[res_head.value].fields)
                                ):
                                    restored_slots_term = self._project_member(
                                        post_env["result"], "RestoredDst", rest_contract
                                    ).term
                                else:
                                    raise self.fail(
                                        "type",
                                        f"restores clause for '{target_param_name}' requires a Slots return type, ref parameter, or RestoredDst record field",
                                        rest_contract,
                                    )
                            for field_tag, eq_ty in (
                                ("Base", _USIZE),
                                ("Tag", _BOOL),
                                ("PermRead", _BOOL),
                                ("PermWrite", _BOOL),
                            ):
                                self.work = MAX_WORK
                                self.reductions = MAX_REDUCTIONS
                                lhs_f = _apps(_constant(f"Slots_{field_tag}"), elem_t, cap_t, restored_slots_term)
                                rhs_f = _apps(_constant(f"Slots_{field_tag}"), elem_t, cap_t, param_b.term)
                                rest_prop = _apps(_constant("Eq"), eq_ty, lhs_f, rhs_f)
                                rest_proof = self._prove_proposition(rest_prop, post_env, (), rest_contract)
                                rest_sig = self.wrap("pi", post_vars, rest_prop)
                                rest_def = self.wrap("lam", post_vars, rest_proof)
                                self.complete(rest_sig)
                                self.complete(rest_def)
                                rest_emitted = f"{emitted}_restores_{rest_idx}_{field_tag}"
                                self.output.append(
                                    f"Definition {rest_emitted} : {self.render(rest_sig)} :=\n  {self.render(rest_def)}."
                                )
                                self.constants[rest_emitted] = _Binding(_constant(rest_emitted), rest_sig, len(generics))
                                self.definitions[rest_emitted] = rest_def
                        else:
                            raise self.fail(
                                "type",
                                f"restores parameter '{target_param_name}' must have type Span<byte> or Slots<T, capacity>",
                                rest_val_node,
                            )
                    else:
                        self.work = MAX_WORK
                        self.reductions = MAX_REDUCTIONS
                        rest_prop = self.asserted_proposition(rest_val_node, post_env)
                        try:
                            rest_proof = self._prove_proposition(rest_prop, post_env, (), rest_contract)
                        except VelaError:
                            extracted = self._extract_equality(rest_prop)
                            proved_rest = False
                            if (
                                extracted is not None
                                and self.whnf(extracted[0]) == _BOOL
                                and self.whnf(extracted[2]) == _term("bool", value=1)
                                and self._prove_bool_precondition(extracted[1], post_env)
                            ):
                                proved_rest = True
                            if not proved_rest:
                                saved_rest_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                                try:
                                    rest_b = self.expression(rest_val_node, post_env)
                                    if self.whnf(rest_b.type) == _BOOL and self._prove_bool_precondition(rest_b.term, post_env):
                                        proved_rest = True
                                except VelaError:
                                    self.metas = saved_rest_m
                            if proved_rest:
                                rest_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                                rest_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                            else:
                                raise
                        if not (self.free(rest_prop) <= post_var_ids and self.free(rest_proof) <= post_var_ids):
                            rest_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                            rest_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                        rest_sig = self.wrap("pi", post_vars, rest_prop)
                        rest_def = self.wrap("lam", post_vars, rest_proof)
                        self.complete(rest_sig)
                        self.complete(rest_def)
                        rest_emitted = f"{emitted}_restores_{rest_idx}"
                        self.output.append(
                            f"Definition {rest_emitted} : {self.render(rest_sig)} :=\n  {self.render(rest_def)}."
                        )
                        self.constants[rest_emitted] = _Binding(_constant(rest_emitted), rest_sig, len(generics))
                        self.definitions[rest_emitted] = rest_def
                for ens_idx, ens_contract in enumerate(ensures_clauses):
                    self.work = MAX_WORK
                    self.reductions = MAX_REDUCTIONS
                    ens_val_node = self.node(ens_contract["value"])
                    ens_prop = self.asserted_proposition(ens_val_node, post_env)
                    try:
                        ens_proof = self._prove_proposition(ens_prop, post_env, (), ens_contract)
                    except VelaError:
                        extracted = self._extract_equality(ens_prop)
                        proved_alt = False
                        if extracted is not None:
                            eq_ty_w = self.whnf(extracted[0])
                            if (
                                eq_ty_w == _BOOL
                                and self.whnf(extracted[2]) == _term("bool", value=1)
                                and self._prove_bool_precondition(extracted[1], post_env)
                            ):
                                proved_alt = True
                            elif eq_ty_w == _NAT or self._int_spec(eq_ty_w) is not None:
                                spec = self._int_spec(eq_ty_w)
                                bool_facts = self._expand_bool_facts(
                                    [*self.active_facts, *self._fact_bool_terms((), post_env)]
                                )
                                if self._prove_comparison("eq", spec, extracted[1], extracted[2], bool_facts):
                                    proved_alt = True
                        if not proved_alt:
                            saved_ens_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                            try:
                                ens_b = self.expression(ens_val_node, post_env)
                                if self.whnf(ens_b.type) == _BOOL and self._prove_bool_precondition(ens_b.term, post_env):
                                    proved_alt = True
                            except VelaError:
                                self.metas = saved_ens_m
                        if proved_alt:
                            ens_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                            ens_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                        else:
                            raise
                    if not (self.free(ens_prop) <= post_var_ids and self.free(ens_proof) <= post_var_ids):
                        ens_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                        ens_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                    ens_sig = self.wrap("pi", post_vars, ens_prop)
                    ens_def = self.wrap("lam", post_vars, ens_proof)
                    self.complete(ens_sig)
                    self.complete(ens_def)
                    ens_emitted = f"{emitted}_ensures_{ens_idx}"
                    self.output.append(
                        f"Definition {ens_emitted} : {self.render(ens_sig)} :=\n  {self.render(ens_def)}."
                    )
                    self.constants[ens_emitted] = _Binding(_constant(ens_emitted), ens_sig, len(generics))
                    self.definitions[ens_emitted] = ens_def
            finally:
                self.active_facts = saved_post_facts

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
        if kind == "int":
            spec = cast("_IntSpec", self._int_spec(term.args[0]))
            int_val = cast("int", term.value)
            unsigned = int_val & ((1 << spec.bits) - 1)
            bits_term = "vela_bnil"
            for nib_idx in range(0, spec.bits, 4):
                nib = (unsigned >> nib_idx) & 0xF
                bits_term = f"(vela_x{nib:x} {bits_term})"
            return f"(@vela_mk_int ({spec.tag} : Corelib.Init.Datatypes.nat) {bits_term})"
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
        if kind == "fix":
            sig, lam_body, struct_var_term, _ = term.args
            binders: list[str] = []
            curr_lam = self.resolve(lam_body)
            curr_sig = self.resolve(sig)
            while curr_lam.kind == "lam" and curr_sig.kind == "pi":
                domain = curr_lam.args[0]
                binders.append(f"(vela_v{curr_lam.value} : {self.render(domain)})")
                curr_lam = self.resolve(curr_lam.args[1])
                curr_sig = self.resolve(curr_sig.args[1])
            binder_str = " ".join(binders)
            struct_name = f"vela_v{struct_var_term.value}"
            return (
                f"(fix vela_v{term.value} {binder_str} {{struct {struct_name}}} : "
                f"{self.render(curr_sig)} := {self.render(curr_lam)})"
            )
        if kind in {"pi", "lam"}:
            domain, body = term.args
            binder = f"vela_v{term.value} : {self.render(domain)}"
            return (f"(forall ({binder}), {self.render(body)})" if kind == "pi"
                    else f"(fun ({binder}) => {self.render(body)})")
        if kind == "app":
            head, arguments = self.spine(term)
            rendered_head = self.render(head)
            prefix = "(@" if (head.kind == "const" and not rendered_head.startswith("(")) else "("
            return prefix + rendered_head + " " + " ".join(self.render(value) for value in arguments) + ")"
        if kind == "prod":
            return f"(@Corelib.Init.Datatypes.prod {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind == "pair":
            return "(@Corelib.Init.Datatypes.pair " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "sigT":
            return f"(@Corelib.Init.Specif.sigT {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind == "existT":
            return "(@Corelib.Init.Specif.existT " + " ".join(self.render(value) for value in term.args) + ")"
        if kind in {"projT1", "projT2"}:
            return f"(@Corelib.Init.Specif.{kind} " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "ex":
            return f"(@Corelib.Init.Logic.ex {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind == "ex_intro":
            return "(@Corelib.Init.Logic.ex_intro " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "sum":
            return f"(@Corelib.Init.Datatypes.sum {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind in {"inl", "inr"}:
            return f"(@Corelib.Init.Datatypes.{kind} " + " ".join(self.render(value) for value in term.args) + ")"
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
        if kind == "sigT_match":
            motive, scrutinee, branch = term.args
            inner = branch.args[1]
            binder = f"vela_v{motive.value}"
            fst_binder = f"vela_v{branch.value}"
            snd_binder = f"vela_v{inner.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| @Corelib.Init.Specif.existT _ _ {fst_binder} {snd_binder} => {self.render(inner.args[1])} end)")
        if kind == "sum_match":
            motive, scrutinee, left_branch, right_branch = term.args
            binder = f"vela_v{motive.value}"
            left_binder = f"vela_v{left_branch.value}"
            right_binder = f"vela_v{right_branch.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| @Corelib.Init.Datatypes.inl _ _ {left_binder} => {self.render(left_branch.args[1])} "
                    f"| @Corelib.Init.Datatypes.inr _ _ {right_binder} => {self.render(right_branch.args[1])} end)")
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
    "u8": "(vela_int (0 : Corelib.Init.Datatypes.nat))",
    "u16": "(vela_int (1 : Corelib.Init.Datatypes.nat))",
    "u32": "(vela_int (2 : Corelib.Init.Datatypes.nat))",
    "u64": "(vela_int (3 : Corelib.Init.Datatypes.nat))",
    "usize": "(vela_int (4 : Corelib.Init.Datatypes.nat))",
    "i8": "(vela_int (5 : Corelib.Init.Datatypes.nat))",
    "i16": "(vela_int (6 : Corelib.Init.Datatypes.nat))",
    "i32": "(vela_int (7 : Corelib.Init.Datatypes.nat))",
    "i64": "(vela_int (8 : Corelib.Init.Datatypes.nat))",
    "vela_ArithmeticError": "vela_ArithmeticError",
    "vela_ArithmeticError_Overflow": "vela_ArithmeticError_Overflow",
    "vela_ArithmeticError_ZeroDivisor": "vela_ArithmeticError_ZeroDivisor",
    "vela_ArithmeticError_InvalidShift": "vela_ArithmeticError_InvalidShift",
    "vela_ConversionError": "vela_ConversionError",
    "vela_ConversionError_OutOfRange": "vela_ConversionError_OutOfRange",
    "vela_Result": "vela_Result",
    "vela_Result_Ok": "vela_Result_Ok",
    "vela_Result_Err": "vela_Result_Err",
    "Succ": "Corelib.Init.Datatypes.S", "Eq": "Corelib.Init.Logic.eq",
    "Refl": "Corelib.Init.Logic.eq_refl", "Symm": "Corelib.Init.Logic.eq_sym",
    "Trans": "Corelib.Init.Logic.eq_trans", "Congr": "vela_Congr",
    "Fst": "Corelib.Init.Datatypes.fst", "Snd": "Corelib.Init.Datatypes.snd",
    "Vec": "vela_Vec", "VNil": "vela_VNil", "VCons": "vela_VCons", "ByteLength": "vela_ByteLength",
    "TextBuilder": "vela_TextBuilder", "TextBuilderVal": "vela_text_builder",
    "EmptyBuilder": "vela_EmptyBuilder", "FormatStep": "vela_FormatStep",
    "Fits": "vela_Fits", "Written": "vela_Written",
    "Fin": "vela_Fin", "FZero": "vela_FZero", "FSucc": "vela_FSucc", "At": "vela_At",
    "Span": "vela_Span",
    "Span_Base": "vela_Span_Base",
    "Span_Length": "vela_Span_Length",
    "Span_Tag": "vela_Span_Tag",
    "Span_PermRead": "vela_Span_PermRead",
    "Span_PermWrite": "vela_Span_PermWrite",
    "Span_CanRead": "vela_Span_CanRead",
    "Span_CanWrite": "vela_Span_CanWrite",
    "Span_AllocZeroed": "vela_Span_AllocZeroed",
    "Span_ReadOnly": "vela_Span_ReadOnly",
    "Span_Invalidate": "vela_Span_Invalidate",
    "Span_Disjoint": "vela_Span_Disjoint",
    "Span_Read": "vela_Span_Read",
    "Span_Write": "vela_Span_Write",
    "Span_Fill": "vela_Span_Fill",
    "Span_Slice": "vela_Span_Slice",
    "Span_CopyPrefix": "vela_Span_CopyPrefix",
    "Span_Restore": "vela_Span_Restore",
    "nat_to_usize": "vela_nat_to_usize",
    "Seq": "vela_Seq",
    "Seq_Empty": "vela_Seq_Empty",
    "Seq_Cons": "vela_Seq_Cons",
    "Seq_Singleton": "vela_Seq_Singleton",
    "Seq_Count": "vela_Seq_Count",
    "Seq_At": "vela_Seq_At",
    "Seq_Update": "vela_Seq_Update",
    "Seq_Append": "vela_Seq_Append",
    "Seq_Take": "vela_Seq_Take",
    "Seq_Skip": "vela_Seq_Skip",
    "Seq_Slice": "vela_Seq_Slice",
    "Seq_Contains": "vela_Seq_Contains",
    "Seq_All": "vela_Seq_All",
    "Seq_Any": "vela_Seq_Any",
    "Vec_Model": "vela_Vec_Model",
    "Span_Model": "vela_Span_Model",
    "Slots": "vela_Slots",
    "Slots_Mk": "vela_Slots_Mk",
    "Slots_Base": "vela_Slots_Base",
    "Slots_LiveCount": "vela_Slots_LiveCount",
    "Slots_Tag": "vela_Slots_Tag",
    "Slots_PermRead": "vela_Slots_PermRead",
    "Slots_PermWrite": "vela_Slots_PermWrite",
    "Slots_CanRead": "vela_Slots_CanRead",
    "Slots_CanWrite": "vela_Slots_CanWrite",
    "Slots_RepModel": "vela_Slots_RepModel",
    "Slots_Model": "vela_Slots_Model",
    "Slots_AllocVacant": "vela_Slots_AllocVacant",
    "Slots_Write": "vela_Slots_Write",
    "Slots_Read": "vela_Slots_Read",
    "Slots_LivePrefix": "vela_Slots_LivePrefix",
    "Slots_VacantRange": "vela_Slots_VacantRange",
    "Slots_Disjoint": "vela_Slots_Disjoint",
    "Slots_RepEqual": "vela_Slots_RepEqual",
    "Slots_CopyRepresentation": "vela_Slots_CopyRepresentation",
    "Slots_TransferSource": "vela_Slots_TransferSource",
    "Slots_TransferDest": "vela_Slots_TransferDest",
    "Slots_TransferType": "vela_Slots_TransferType",
    "PrefixModel": "vela_PrefixModel",
    "LoopState": "vela_LoopState",
    "+": "Corelib.Init.Nat.add", "*": "Corelib.Init.Nat.mul", "-": "Corelib.Init.Nat.sub",
    "/": "Corelib.Init.Nat.div", "%": "Corelib.Init.Nat.modulo",
    "<=": "Corelib.Init.Nat.leb", "<": "Corelib.Init.Nat.ltb", ">=": "vela_ge", ">": "vela_gt",
    "eq_nat": "Corelib.Init.Nat.eqb", "ne_nat": "vela_ne_nat",
    "eq_bool": "vela_eq_bool", "ne_bool": "vela_ne_bool",
    "&&": "vela_and", "||": "vela_or", "!": "vela_not", "==>": "vela_implies", "<==>": "vela_eq_bool",
    **{
        f"int_{op}_{spec.name}": f"(vela_int_{op} ({spec.tag} : Corelib.Init.Datatypes.nat))"
        for spec in _INT_SPECS.values()
        for op in (
            "add", "sub", "mul", "div", "rem", "neg",
            "and", "or", "xor", "not",
            "shl", "shr", "eq", "ne", "lt", "le", "gt", "ge",
            "wrap_add", "wrap_sub", "wrap_mul", "wrap_neg", "wrap_shl",
            "sat_add", "sat_sub", "sat_mul", "sat_neg",
            "chk_add", "chk_sub", "chk_mul", "chk_div",
            "chk_rem", "chk_neg", "chk_shl", "chk_shr",
            "to_nat", "try_from_Nat",
        )
    },
    **{
        f"int_from_{src.name}_{dst.name}": (
            f"(vela_int_from ({src.tag} : Corelib.Init.Datatypes.nat) ({dst.tag} : Corelib.Init.Datatypes.nat))"
        )
        for src in _INT_SPECS.values()
        for dst in _INT_SPECS.values()
    },
    **{
        f"int_try_from_{src.name}_{dst.name}": (
            f"(vela_int_try_from ({src.tag} : Corelib.Init.Datatypes.nat) ({dst.tag} : Corelib.Init.Datatypes.nat))"
        )
        for src in _INT_SPECS.values()
        for dst in _INT_SPECS.values()
    },
}

_PRELUDE = """From Corelib Require Import Init.Datatypes Init.Nat Init.Logic Init.Specif.

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

Inductive vela_bits : Type@{vela_u0} :=
| vela_bnil : vela_bits
| vela_bcons : bool -> vela_bits -> vela_bits.

Abbreviation vela_0 x := (vela_bcons Corelib.Init.Datatypes.false x) (only parsing).
Abbreviation vela_1 x := (vela_bcons Corelib.Init.Datatypes.true x) (only parsing).
Abbreviation vela_x0 x := (vela_0 (vela_0 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_x1 x := (vela_0 (vela_0 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_x2 x := (vela_0 (vela_0 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_x3 x := (vela_0 (vela_0 (vela_1 (vela_1 x)))) (only parsing).
Abbreviation vela_x4 x := (vela_0 (vela_1 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_x5 x := (vela_0 (vela_1 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_x6 x := (vela_0 (vela_1 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_x7 x := (vela_0 (vela_1 (vela_1 (vela_1 x)))) (only parsing).
Abbreviation vela_x8 x := (vela_1 (vela_0 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_x9 x := (vela_1 (vela_0 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_xa x := (vela_1 (vela_0 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_xb x := (vela_1 (vela_0 (vela_1 (vela_1 x)))) (only parsing).
Abbreviation vela_xc x := (vela_1 (vela_1 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_xd x := (vela_1 (vela_1 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_xe x := (vela_1 (vela_1 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_xf x := (vela_1 (vela_1 (vela_1 (vela_1 x)))) (only parsing).

Inductive vela_int (tag : nat) : Type@{vela_u0} :=
| vela_mk_int : vela_bits -> vela_int tag.

Fixpoint vela_bits_eqb (a b : vela_bits) : bool :=
  match a, b with
  | vela_bnil, vela_bnil => true
  | vela_bcons x xs, vela_bcons y ys => vela_and (vela_eq_bool x y) (vela_bits_eqb xs ys)
  | _, _ => false
  end.

Definition vela_int_bits (tag : nat) (x : vela_int tag) : vela_bits :=
  match x with
  | vela_mk_int _ bs => bs
  end.

Definition vela_xorb (a b : bool) : bool := if a then vela_not b else b.

Fixpoint vela_bits_xor (a b : vela_bits) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys => vela_bcons (vela_xorb x y) (vela_bits_xor xs ys)
  | _, _ => vela_bnil
  end.

Fixpoint vela_bits_and (a b : vela_bits) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys => vela_bcons (vela_and x y) (vela_bits_and xs ys)
  | _, _ => vela_bnil
  end.

Fixpoint vela_bits_or (a b : vela_bits) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys => vela_bcons (vela_or x y) (vela_bits_or xs ys)
  | _, _ => vela_bnil
  end.

Fixpoint vela_bits_not (a : vela_bits) : vela_bits :=
  match a with
  | vela_bcons x xs => vela_bcons (vela_not x) (vela_bits_not xs)
  | vela_bnil => vela_bnil
  end.

Fixpoint vela_bits_ult (a b : vela_bits) : bool :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      if vela_eq_bool x y then vela_bits_ult xs ys else y
  | _, _ => false
  end.

Fixpoint vela_bits_ule (a b : vela_bits) : bool :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      if vela_eq_bool x y then vela_bits_ule xs ys else y
  | _, _ => true
  end.

Fixpoint vela_bits_rev_acc (a acc : vela_bits) : vela_bits :=
  match a with
  | vela_bnil => acc
  | vela_bcons x xs => vela_bits_rev_acc xs (vela_bcons x acc)
  end.

Definition vela_bits_rev (a : vela_bits) : vela_bits :=
  vela_bits_rev_acc a vela_bnil.

Fixpoint vela_bits_add_lsb (a b : vela_bits) (carry : bool) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      let sum := vela_xorb (vela_xorb x y) carry in
      let next_carry := vela_or (vela_and x y) (vela_and (vela_xorb x y) carry) in
      vela_bcons sum (vela_bits_add_lsb xs ys next_carry)
  | _, _ => vela_bnil
  end.

Definition vela_bits_add (a b : vela_bits) : vela_bits :=
  vela_bits_rev (vela_bits_add_lsb (vela_bits_rev a) (vela_bits_rev b) false).

Fixpoint vela_bits_sub_lsb (a b : vela_bits) (borrow : bool) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      let diff := vela_xorb (vela_xorb x y) borrow in
      let next_borrow := vela_or (vela_and (vela_not x) y) (vela_and (vela_not (vela_xorb x y)) borrow) in
      vela_bcons diff (vela_bits_sub_lsb xs ys next_borrow)
  | _, _ => vela_bnil
  end.

Definition vela_bits_sub (a b : vela_bits) : vela_bits :=
  vela_bits_rev (vela_bits_sub_lsb (vela_bits_rev a) (vela_bits_rev b) false).

Definition vela_tag_bits (tag : nat) : nat :=
  match tag with
  | O => 8
  | S O => 16
  | S (S O) => 32
  | S (S (S O)) => 64
  | S (S (S (S O))) => 64
  | S (S (S (S (S O)))) => 8
  | S (S (S (S (S (S O))))) => 16
  | S (S (S (S (S (S (S O)))))) => 32
  | _ => 64
  end.

Definition vela_tag_signed (tag : nat) : bool :=
  Corelib.Init.Nat.leb 5 tag.

Fixpoint vela_bits_len (a : vela_bits) : nat :=
  match a with
  | vela_bnil => O
  | vela_bcons _ xs => S (vela_bits_len xs)
  end.

Fixpoint vela_bits_pad (n : nat) (fill : bool) (a : vela_bits) : vela_bits :=
  match n with
  | O => a
  | S k => vela_bcons fill (vela_bits_pad k fill a)
  end.

Definition vela_ArithmeticError : Type@{vela_u0} :=
  @sum unit (@sum unit unit).
Definition vela_ArithmeticError_Overflow (_ : unit) : vela_ArithmeticError :=
  @inl unit (@sum unit unit) tt.
Definition vela_ArithmeticError_ZeroDivisor (_ : unit) : vela_ArithmeticError :=
  @inr unit (@sum unit unit) (@inl unit unit tt).
Definition vela_ArithmeticError_InvalidShift (_ : unit) : vela_ArithmeticError :=
  @inr unit (@sum unit unit) (@inr unit unit tt).

Definition vela_ConversionError : Type@{vela_u0} := unit.
Definition vela_ConversionError_OutOfRange (_ : unit) : vela_ConversionError := tt.

Definition vela_Result (TValue TError : Type@{vela_u0}) : Type@{vela_u0} :=
  @sum TError TValue.
Definition vela_Result_Err (TValue TError : Type@{vela_u0}) (e : TError) : vela_Result TValue TError :=
  @inl TError TValue e.
Definition vela_Result_Ok (TValue TError : Type@{vela_u0}) (v : TValue) : vela_Result TValue TError :=
  @inr TError TValue v.

Definition vela_int_add (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_add (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_sub (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_sub (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_mul (tag : nat) (a _ : vela_int tag) : vela_int tag := a.
Definition vela_int_div (tag : nat) (a _ : vela_int tag) : vela_int tag := a.
Definition vela_int_rem (tag : nat) (a _ : vela_int tag) : vela_int tag := a.
Definition vela_int_neg (tag : nat) (a : vela_int tag) : vela_int tag := a.
Definition vela_int_and (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_and (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_or (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_or (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_xor (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_xor (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_not (tag : nat) (a : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_not (vela_int_bits tag a)).
Definition vela_int_shl (tag : nat) (a : vela_int tag) (_ : vela_int (4 : nat)) : vela_int tag := a.
Definition vela_int_shr (tag : nat) (a : vela_int tag) (_ : vela_int (4 : nat)) : vela_int tag := a.
Definition vela_int_eq (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_eqb (vela_int_bits tag a) (vela_int_bits tag b).
Definition vela_int_ne (tag : nat) (a b : vela_int tag) : bool :=
  vela_not (vela_int_eq tag a b).
Definition vela_int_lt (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ult (vela_int_bits tag a) (vela_int_bits tag b).
Definition vela_int_le (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ule (vela_int_bits tag a) (vela_int_bits tag b).
Definition vela_int_gt (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ult (vela_int_bits tag b) (vela_int_bits tag a).
Definition vela_int_ge (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ule (vela_int_bits tag b) (vela_int_bits tag a).
Definition vela_int_wrap_add (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_int_add tag a b.
Definition vela_int_wrap_sub (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_int_sub tag a b.
Definition vela_int_wrap_mul (tag : nat) (a _ : vela_int tag) : vela_int tag := a.
Definition vela_int_wrap_neg (tag : nat) (a : vela_int tag) : vela_int tag := a.
Definition vela_int_wrap_shl (tag : nat) (a : vela_int tag) (_ : vela_int (4 : nat)) : vela_int tag := a.
Definition vela_int_sat_add (tag : nat) (a _ : vela_int tag) : vela_int tag := a.
Definition vela_int_sat_sub (tag : nat) (a _ : vela_int tag) : vela_int tag := a.
Definition vela_int_sat_mul (tag : nat) (a _ : vela_int tag) : vela_int tag := a.
Definition vela_int_sat_neg (tag : nat) (a : vela_int tag) : vela_int tag := a.
Definition vela_int_chk_add (tag : nat) (a _ : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_chk_sub (tag : nat) (a _ : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_chk_mul (tag : nat) (a _ : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_chk_div (tag : nat) (a _ : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_chk_rem (tag : nat) (a _ : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_chk_neg (tag : nat) (a : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_chk_shl (tag : nat) (a : vela_int tag) (_ : vela_int (4 : nat))
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_chk_shr (tag : nat) (a : vela_int tag) (_ : vela_int (4 : nat))
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.
Definition vela_int_to_nat (tag : nat) (_ : vela_int tag) : nat := O.
Definition vela_int_from (src dst : nat) (x : vela_int src) : vela_int dst :=
  let bs := vela_int_bits src x in
  let fill :=
    if vela_tag_signed src then
      match bs with
      | vela_bcons msb _ => msb
      | vela_bnil => false
      end
    else false
  in
  vela_mk_int dst (vela_bits_pad (Corelib.Init.Nat.sub (vela_tag_bits dst) (vela_bits_len bs)) fill bs).
Definition vela_int_try_from (src dst : nat) (x : vela_int src)
    : vela_Result (vela_int dst) vela_ConversionError :=
  vela_Result_Ok (vela_int dst) vela_ConversionError (vela_int_from src dst x).
Definition vela_int_try_from_Nat (dst : nat) (_ : nat)
    : vela_Result (vela_int dst) vela_ConversionError :=
  vela_Result_Ok (vela_int dst) vela_ConversionError (vela_mk_int dst vela_bnil).

Definition vela_u8_zero : vela_int (0 : nat) :=
  vela_mk_int (0 : nat) (vela_bits_pad 8 false vela_bnil).

Definition vela_in_extent (addr base len : vela_int (4 : nat)) : bool :=
  vela_and
    (vela_int_le (4 : nat) base addr)
    (vela_int_lt (4 : nat) addr (vela_int_add (4 : nat) base len)).

Inductive vela_ByteStore : Type@{vela_u0} :=
| vela_bs_empty : vela_ByteStore
| vela_bs_fill : vela_int (4 : nat) -> vela_int (4 : nat) -> vela_int (0 : nat) -> vela_ByteStore -> vela_ByteStore
| vela_bs_write : vela_int (4 : nat) -> vela_int (0 : nat) -> vela_ByteStore -> vela_ByteStore
| vela_bs_copy : vela_int (4 : nat) -> vela_int (4 : nat) -> vela_int (4 : nat) -> vela_ByteStore -> vela_ByteStore -> vela_ByteStore.

Fixpoint vela_store_lookup (st : vela_ByteStore) (addr : vela_int (4 : nat)) {struct st} : vela_int (0 : nat) :=
  match st with
  | vela_bs_empty => vela_u8_zero
  | vela_bs_fill base len val rest =>
      if vela_in_extent addr base len then val else vela_store_lookup rest addr
  | vela_bs_write waddr val rest =>
      if vela_int_eq (4 : nat) addr waddr then val else vela_store_lookup rest addr
  | vela_bs_copy dbase sbase count src_st rest =>
      if vela_in_extent addr dbase count then
        vela_store_lookup src_st (vela_int_add (4 : nat) sbase (vela_int_sub (4 : nat) addr dbase))
      else
        vela_store_lookup rest addr
  end.

Inductive vela_Span (A : Type@{vela_u0}) : Type@{vela_u0} :=
| vela_mk_span :
    vela_int (4 : nat) ->
    vela_int (4 : nat) ->
    bool ->
    bool ->
    bool ->
    vela_ByteStore ->
    vela_Span A.

Definition vela_Span_Base (A : Type@{vela_u0}) (s : vela_Span A) : vela_int (4 : nat) :=
  match s with
  | vela_mk_span _ base _ _ _ _ _ => base
  end.

Definition vela_Span_Length (A : Type@{vela_u0}) (s : vela_Span A) : vela_int (4 : nat) :=
  match s with
  | vela_mk_span _ _ len _ _ _ _ => len
  end.

Definition vela_Span_Tag (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  match s with
  | vela_mk_span _ _ _ tag _ _ _ => tag
  end.

Definition vela_Span_PermRead (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  match s with
  | vela_mk_span _ _ _ _ pr _ _ => pr
  end.

Definition vela_Span_PermWrite (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  match s with
  | vela_mk_span _ _ _ _ _ pw _ => pw
  end.

Definition vela_Span_Store (A : Type@{vela_u0}) (s : vela_Span A) : vela_ByteStore :=
  match s with
  | vela_mk_span _ _ _ _ _ _ st => st
  end.

Definition vela_Span_CanRead (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  vela_and (vela_Span_Tag A s) (vela_Span_PermRead A s).

Definition vela_Span_CanWrite (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  vela_and (vela_Span_Tag A s) (vela_Span_PermWrite A s).

Definition vela_Span_AllocZeroed (A : Type@{vela_u0}) (base cap : vela_int (4 : nat)) : vela_Span A :=
  vela_mk_span A base cap true true true vela_bs_empty.

Definition vela_Span_ReadOnly (A : Type@{vela_u0}) (s : vela_Span A) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    false
    (vela_Span_Store A s).

Definition vela_Span_Invalidate (A : Type@{vela_u0}) (s : vela_Span A) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    false
    false
    false
    (vela_Span_Store A s).

Definition vela_Span_Disjoint (A : Type@{vela_u0}) (a b : vela_Span A) : bool :=
  vela_or
    (vela_int_le (4 : nat)
      (vela_int_add (4 : nat) (vela_Span_Base A a) (vela_Span_Length A a))
      (vela_Span_Base A b))
    (vela_int_le (4 : nat)
      (vela_int_add (4 : nat) (vela_Span_Base A b) (vela_Span_Length A b))
      (vela_Span_Base A a)).

Definition vela_Span_Read (A : Type@{vela_u0}) (s : vela_Span A) (idx : vela_int (4 : nat)) : vela_int (0 : nat) :=
  vela_store_lookup (vela_Span_Store A s) (vela_int_add (4 : nat) (vela_Span_Base A s) idx).

Definition vela_Span_Write (A : Type@{vela_u0}) (s : vela_Span A) (idx : vela_int (4 : nat)) (val : vela_int (0 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    (vela_Span_PermWrite A s)
    (vela_bs_write (vela_int_add (4 : nat) (vela_Span_Base A s) idx) val (vela_Span_Store A s)).

Definition vela_Span_Fill (A : Type@{vela_u0}) (s : vela_Span A) (off count : vela_int (4 : nat)) (val : vela_int (0 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    (vela_Span_PermWrite A s)
    (vela_bs_fill (vela_int_add (4 : nat) (vela_Span_Base A s) off) count val (vela_Span_Store A s)).

Definition vela_Span_Slice (A : Type@{vela_u0}) (s : vela_Span A) (off count : vela_int (4 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_int_add (4 : nat) (vela_Span_Base A s) off)
    count
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    (vela_Span_PermWrite A s)
    (vela_Span_Store A s).

Definition vela_Span_CopyPrefix (A : Type@{vela_u0}) (dst src : vela_Span A) (count : vela_int (4 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A dst)
    (vela_Span_Length A dst)
    (vela_Span_Tag A dst)
    (vela_Span_PermRead A dst)
    (vela_Span_PermWrite A dst)
    (vela_bs_copy (vela_Span_Base A dst) (vela_Span_Base A src) count (vela_Span_Store A src) (vela_Span_Store A dst)).

Definition vela_Span_Restore (A : Type@{vela_u0}) (parent view : vela_Span A) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A parent)
    (vela_Span_Length A parent)
    (vela_Span_Tag A parent)
    (vela_Span_PermRead A parent)
    (vela_Span_PermWrite A parent)
    (vela_Span_Store A view).

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

Definition vela_nat_to_usize (_ : nat) : vela_int (4 : nat) :=
  vela_mk_int (4 : nat) (vela_bits_pad 64 false vela_bnil).

Inductive vela_Seq (A : Type@{vela_u0}) : Type@{vela_u0} :=
| vela_Seq_Empty : vela_Seq A
| vela_Seq_Cons : A -> vela_Seq A -> vela_Seq A.

Definition vela_Seq_Singleton (A : Type@{vela_u0}) (x : A) : vela_Seq A :=
  vela_Seq_Cons A x (vela_Seq_Empty A).

Fixpoint vela_Seq_Count (A : Type@{vela_u0}) (s : vela_Seq A) {struct s} : nat :=
  match s with
  | vela_Seq_Empty _ => O
  | vela_Seq_Cons _ _ xs => S (vela_Seq_Count A xs)
  end.

Fixpoint vela_Seq_At (A : Type@{vela_u0}) (d : A) (s : vela_Seq A) (idx : nat) {struct s} : A :=
  match s with
  | vela_Seq_Empty _ => d
  | vela_Seq_Cons _ x xs =>
      match idx with
      | O => x
      | S k => vela_Seq_At A d xs k
      end
  end.

Fixpoint vela_Seq_Update (A : Type@{vela_u0}) (s : vela_Seq A) (idx : nat) (val : A) {struct s} : vela_Seq A :=
  match s with
  | vela_Seq_Empty _ => vela_Seq_Empty A
  | vela_Seq_Cons _ x xs =>
      match idx with
      | O => vela_Seq_Cons A val xs
      | S k => vela_Seq_Cons A x (vela_Seq_Update A xs k val)
      end
  end.

Fixpoint vela_Seq_Append (A : Type@{vela_u0}) (a b : vela_Seq A) {struct a} : vela_Seq A :=
  match a with
  | vela_Seq_Empty _ => b
  | vela_Seq_Cons _ x xs => vela_Seq_Cons A x (vela_Seq_Append A xs b)
  end.

Fixpoint vela_Seq_Take (A : Type@{vela_u0}) (s : vela_Seq A) (n : nat) {struct n} : vela_Seq A :=
  match n with
  | O => vela_Seq_Empty A
  | S k =>
      match s with
      | vela_Seq_Empty _ => vela_Seq_Empty A
      | vela_Seq_Cons _ x xs => vela_Seq_Cons A x (vela_Seq_Take A xs k)
      end
  end.

Fixpoint vela_Seq_Skip (A : Type@{vela_u0}) (s : vela_Seq A) (n : nat) {struct n} : vela_Seq A :=
  match n with
  | O => s
  | S k =>
      match s with
      | vela_Seq_Empty _ => vela_Seq_Empty A
      | vela_Seq_Cons _ _ xs => vela_Seq_Skip A xs k
      end
  end.

Definition vela_Seq_Slice (A : Type@{vela_u0}) (s : vela_Seq A) (off cnt : nat) : vela_Seq A :=
  vela_Seq_Take A (vela_Seq_Skip A s off) cnt.

Definition vela_Seq_Contains (A : Type@{vela_u0}) (s : vela_Seq A) (_ : A) : bool :=
  match s with
  | vela_Seq_Empty _ => false
  | vela_Seq_Cons _ _ _ => true
  end.

Fixpoint vela_Seq_All (A : Type@{vela_u0}) (s : vela_Seq A) (p : A -> bool) {struct s} : bool :=
  match s with
  | vela_Seq_Empty _ => true
  | vela_Seq_Cons _ x xs => vela_and (p x) (vela_Seq_All A xs p)
  end.

Fixpoint vela_Seq_Any (A : Type@{vela_u0}) (s : vela_Seq A) (p : A -> bool) {struct s} : bool :=
  match s with
  | vela_Seq_Empty _ => false
  | vela_Seq_Cons _ x xs => vela_or (p x) (vela_Seq_Any A xs p)
  end.

Fixpoint vela_Vec_Model (A : Type@{vela_u0}) (n : nat) {struct n} : vela_Vec A n -> vela_Seq A :=
  match n return vela_Vec A n -> vela_Seq A with
  | O => fun _ => vela_Seq_Empty A
  | S k => fun v => vela_Seq_Cons A (@fst A (vela_Vec A k) v) (vela_Vec_Model A k (@snd A (vela_Vec A k) v))
  end.

Definition vela_Span_Model (A : Type@{vela_u0}) (_ : vela_Span A) : vela_Seq (vela_int (0 : nat)) :=
  vela_Seq_Empty (vela_int (0 : nat)).

Inductive vela_Slots (A : Type@{vela_u0}) (cap : nat) : Type@{vela_u0} :=
| vela_Slots_Mk :
    vela_int (4 : nat) ->
    vela_int (4 : nat) ->
    bool ->
    bool ->
    bool ->
    vela_Seq A ->
    vela_Seq A ->
    vela_Slots A cap.

Definition vela_Slots_Base (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_int (4 : nat) :=
  match s with
  | vela_Slots_Mk _ _ base _ _ _ _ _ _ => base
  end.

Definition vela_Slots_LiveCount (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_int (4 : nat) :=
  match s with
  | vela_Slots_Mk _ _ _ live _ _ _ _ _ => live
  end.

Definition vela_Slots_Tag (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  match s with
  | vela_Slots_Mk _ _ _ _ tag _ _ _ _ => tag
  end.

Definition vela_Slots_PermRead (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ pr _ _ _ => pr
  end.

Definition vela_Slots_PermWrite (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ _ pw _ _ => pw
  end.

Definition vela_Slots_RepModel (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_Seq A :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ _ _ rep _ => rep
  end.

Definition vela_Slots_Model (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_Seq A :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ _ _ _ m => m
  end.

Definition vela_Slots_CanRead (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  vela_and (vela_Slots_Tag A cap s) (vela_Slots_PermRead A cap s).

Definition vela_Slots_CanWrite (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  vela_and (vela_Slots_Tag A cap s) (vela_Slots_PermWrite A cap s).

Definition vela_Slots_AllocVacant (A : Type@{vela_u0}) (cap : nat) (base : vela_int (4 : nat)) : vela_Slots A cap :=
  vela_Slots_Mk A cap base (vela_nat_to_usize O) true true true (vela_Seq_Empty A) (vela_Seq_Empty A).

Definition vela_Slots_Write (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (idx : vela_int (4 : nat)) (val : A)
    : vela_Slots A cap :=
  vela_Slots_Mk A cap
    (vela_Slots_Base A cap s)
    idx
    (vela_Slots_Tag A cap s)
    (vela_Slots_PermRead A cap s)
    (vela_Slots_PermWrite A cap s)
    (vela_Seq_Singleton A val)
    (vela_Seq_Singleton A val).

Definition vela_Slots_Read (A : Type@{vela_u0}) (cap : nat) (d : A) (s : vela_Slots A cap) (idx : vela_int (4 : nat)) : A :=
  vela_Seq_At A d (vela_Slots_Model A cap s) (vela_int_to_nat (4 : nat) idx).

Definition vela_Slots_LivePrefix (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (cnt : vela_int (4 : nat)) : bool :=
  vela_and (vela_Slots_CanRead A cap s) (vela_int_eq (4 : nat) (vela_Slots_LiveCount A cap s) cnt).

Definition vela_Slots_VacantRange (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (start stop : vela_int (4 : nat)) : bool :=
  vela_and (vela_Slots_CanWrite A cap s) (vela_int_le (4 : nat) start stop).

Definition vela_Slots_Disjoint (A : Type@{vela_u0}) (n m : nat) (a : vela_Slots A n) (b : vela_Slots A m) : bool :=
  vela_int_ne (4 : nat) (vela_Slots_Base A n a) (vela_Slots_Base A m b).

Definition vela_Slots_RepEqual (A : Type@{vela_u0}) (n m : nat) (_ : vela_Slots A n) (_ : vela_Slots A m) (_ : vela_int (4 : nat)) : bool :=
  true.

Definition vela_Slots_CopyRepresentation (A : Type@{vela_u0}) (n m : nat) (src : vela_Slots A n) (dst : vela_Slots A m) (_ : vela_int (4 : nat))
    : vela_Slots A m :=
  vela_Slots_Mk A m
    (vela_Slots_Base A m dst)
    (vela_nat_to_usize O)
    (vela_Slots_Tag A m dst)
    (vela_Slots_PermRead A m dst)
    (vela_Slots_PermWrite A m dst)
    (vela_Slots_Model A n src)
    (vela_Seq_Empty A).

Definition vela_Slots_TransferSource (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (_ : vela_int (4 : nat))
    : vela_Slots A cap :=
  vela_Slots_Mk A cap
    (vela_Slots_Base A cap s)
    (vela_nat_to_usize O)
    (vela_Slots_Tag A cap s)
    (vela_Slots_PermRead A cap s)
    (vela_Slots_PermWrite A cap s)
    (vela_Seq_Empty A)
    (vela_Seq_Empty A).

Definition vela_Slots_TransferDest (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (cnt : vela_int (4 : nat))
    : vela_Slots A cap :=
  vela_Slots_Mk A cap
    (vela_Slots_Base A cap s)
    cnt
    (vela_Slots_Tag A cap s)
    (vela_Slots_PermRead A cap s)
    (vela_Slots_PermWrite A cap s)
    (vela_Slots_RepModel A cap s)
    (vela_Slots_RepModel A cap s).

Definition vela_Slots_TransferType (A : Type@{vela_u0}) (n m : nat) (src : vela_Slots A n) (dst : vela_Slots A m) (cnt : vela_int (4 : nat))
    : @prod (vela_Slots A n) (vela_Slots A m) :=
  @pair (vela_Slots A n) (vela_Slots A m)
    (vela_Slots_TransferSource A n src cnt)
    (vela_Slots_TransferDest A m dst cnt).

Definition vela_PrefixModel (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (_ : vela_int (4 : nat)) : vela_Seq A :=
  vela_Slots_Model A cap s.

Definition vela_LoopState (A : Type@{vela_u0}) (x : A) (_ : nat) : A := x.
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


