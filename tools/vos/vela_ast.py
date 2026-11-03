# SPDX-License-Identifier: Apache-2.0
"""Located pure Vela syntax and strict decoding of the native parser protocol.

Decoding checks the protocol and its source binding. It does not establish lexer
correctness or correspondence between source grammar and the returned tree.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Literal, cast

MAX_SOURCE_BYTES = 65_536
MAX_EXPRESSION_DEPTH = 64
MAX_BLOCK_DEPTH = 64
MAX_LITERAL_DIGITS = 256
MAX_SYNTAX_DEPTH = 256

type ValueType = Literal["Nat", "bool"]

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DECIMAL = re.compile(r"[0-9]+")
KEYWORDS = frozenset({"module", "public", "return", "let", "if", "else", "Nat", "bool",
                      "true", "false"})
UNSUPPORTED = frozenset({"fn", "Bool", "async", "await", "effect", "effects", "handler",
                        "handle", "resume", "dispose", "mut", "var", "unsafe", "borrow",
                        "requires", "ensures", "restores", "ghost", "tracked", "grade",
                        "proof", "owned", "move", "ref", "in", "out", "captures", "scope",
                        "spawn", "commit", "on", "cancel", "region", "view", "union"})


def unsupported_message(spelling: str) -> str:
    """Explain requested ownership modes without claiming to check their laws."""
    mode = {"in": "a shared read loan", "ref": "an initialized exclusive loan",
            "out": "an exclusive initialization loan", "owned": "consuming ownership",
            "move": "an explicit ownership transfer"}.get(spelling)
    if mode is None:
        return f"'{spelling}' is outside the pure prototype"
    return (f"'{spelling}' requests {mode}; the pure Nat/bool prototype cannot check "
            "ownership, borrowing or resource lifetimes")


def trivia_end(source: bytes, offset: int, *, block_comments: bool = False) -> int:
    """Skip complete lexer trivia; never let a source span end inside a comment."""
    if not 0 <= offset <= len(source):
        return -1
    while offset < len(source):
        if source[offset] in b" \t\r\n":
            offset += 1
        elif source.startswith(b"//", offset):
            offset += 2
            while offset < len(source) and source[offset] not in b"\r\n":
                offset += 1
        elif block_comments and source.startswith(b"/*", offset):
            level = 1
            offset += 2
            while level and offset < len(source):
                if source.startswith(b"/*", offset):
                    level += 1
                    if level > MAX_SYNTAX_DEPTH:
                        return -1
                    offset += 2
                elif source.startswith(b"*/", offset):
                    level -= 1
                    offset += 2
                else:
                    offset += 1
            if level:
                return -1
        else:
            break
    return offset


class VelaError(Exception):
    """One bounded diagnostic; callers supply the source file's display name."""

    def __init__(self, kind: str, line: int, column: int, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.line = line
        self.column = column
        self.message = message


@dataclass(frozen=True)
class Site:
    line: int
    column: int


@dataclass(frozen=True)
class Name:
    text: str
    site: Site


@dataclass(frozen=True)
class Expression:
    kind: str
    value: str | bool
    site: Site
    children: tuple[Expression, ...] = ()
    depth: int = 1
    nesting: int = 1


def expression(kind: str, value: str | bool, site: Site,
               children: tuple[Expression, ...] = ()) -> Expression:
    depth = max((child.depth for child in children), default=0) + (kind != "group")
    if depth > MAX_EXPRESSION_DEPTH:
        raise VelaError("limit", site.line, site.column,
                        f"expression exceeds depth {MAX_EXPRESSION_DEPTH}")
    nesting = max((child.nesting for child in children), default=1)
    if kind == "group" or (kind == "call" and children):
        nesting += 1
    if nesting > MAX_EXPRESSION_DEPTH:
        raise VelaError("limit", site.line, site.column,
                        f"expression nesting exceeds {MAX_EXPRESSION_DEPTH}")
    return Expression(kind, value, site, children, depth, nesting)


@dataclass(frozen=True)
class Binding:
    name: Name
    value: Expression
    site: Site


@dataclass(frozen=True)
class Return:
    value: Expression
    site: Site


@dataclass(frozen=True)
class Conditional:
    condition: Expression
    yes: Block
    no: Block
    site: Site


@dataclass(frozen=True)
class Block:
    bindings: tuple[Binding, ...]
    terminal: Return | Conditional
    site: Site


@dataclass(frozen=True)
class Function:
    name: Name
    result: ValueType
    parameters: tuple[tuple[Name, ValueType], ...]
    body: Block


@dataclass(frozen=True)
class Module:
    name: Name
    functions: tuple[Function, ...]


def position(prefix: str) -> Site:
    normalized = prefix.replace("\r\n", "\n").replace("\r", "\n")
    return Site(normalized.count("\n") + 1, len(normalized.rsplit("\n", 1)[-1]) + 1)


def source_text(source: bytes) -> str:
    if len(source) > MAX_SOURCE_BYTES:
        raise VelaError("limit", 1, 1, f"source exceeds {MAX_SOURCE_BYTES} bytes")
    try:
        return source.decode("utf-8")
    except UnicodeDecodeError as error:
        site = position(source[:error.start].decode("utf-8"))
        raise VelaError("encoding", site.line, site.column, "source is not valid UTF-8") from error


class _Decoder:
    def __init__(self, source: bytes) -> None:
        text = source_text(source)
        self.source = source
        self.remaining = MAX_SOURCE_BYTES
        self.sites: dict[int, Site] = {}
        offset, line, column = 0, 1, 1
        previous = ""
        for character in text:
            self.sites[offset] = Site(line, column)
            if character == "\r":
                line, column = line + 1, 1
            elif character == "\n":
                if previous != "\r":
                    line += 1
                column = 1
            else:
                column += 1
            offset += len(character.encode("utf-8"))
            previous = character
        self.sites[offset] = Site(line, column)

    def _node(self, raw: object, kind: str, fields: set[str],
              parent: tuple[int, int], depth: int) -> tuple[dict[str, object], tuple[int, int], Site]:
        if depth > MAX_SYNTAX_DEPTH or self.remaining == 0:
            raise VelaError("limit", 1, 1, "native syntax tree exceeds decoding bounds")
        self.remaining -= 1
        if not isinstance(raw, dict) or set(raw) != {"kind", "span", *fields} or raw.get("kind") != kind:
            raise ValueError(f"native parser returned an invalid {kind} node")
        node = cast("dict[str, object]", raw)
        span = self._span(node["span"], parent)
        return node, span, self._site(span[0])

    def _span(self, raw: object, parent: tuple[int, int]) -> tuple[int, int]:
        if (not isinstance(raw, list) or len(raw) != 2
                or type(raw[0]) is not int or type(raw[1]) is not int):
            raise ValueError("native parser returned an invalid source span")
        start, end = cast("tuple[int, int]", tuple(raw))
        if not parent[0] <= start < end <= parent[1]:
            raise ValueError("native parser returned an empty, escaping or unordered span")
        if start not in self.sites or end not in self.sites:
            raise ValueError("native span splits a UTF-8 character")
        return start, end

    def _site(self, offset: int) -> Site:
        return self.sites[offset]

    def _text(self, raw: object, parent: tuple[int, int], *, identifier: bool = True) -> Name:
        if not isinstance(raw, dict) or set(raw) != {"text", "span"} or not isinstance(raw["text"], str):
            raise ValueError("native parser returned an invalid name or operator")
        text = raw["text"]
        start, end = self._span(raw["span"], parent)
        if self.source[start:end] != text.encode("utf-8"):
            raise ValueError("native name or operator differs from its source span")
        if identifier and (not IDENTIFIER.fullmatch(text) or text in KEYWORDS | UNSUPPORTED):
            raise ValueError("native parser returned an invalid identifier")
        return Name(text, self._site(start))

    def _list(self, raw: object) -> list[object]:
        if not isinstance(raw, list) or len(raw) > len(self.source):
            raise ValueError("native parser returned an invalid syntax list")
        return cast("list[object]", raw)

    def _ordered(self, raw: list[object], parent: tuple[int, int]) -> None:
        previous = parent[0]
        for item in raw:
            if not isinstance(item, dict):
                raise TypeError("native parser returned a non-node list member")
            start, previous_end = self._span(item.get("span"), parent)
            if start < previous:
                raise ValueError("native syntax list is overlapping or out of order")
            previous = previous_end

    def _type(self, raw: object, parent: tuple[int, int], depth: int) -> ValueType:
        node, span, _ = self._node(raw, "type", {"name"}, parent, depth)
        value = node["name"]
        if value not in ("Nat", "bool") or self.source[span[0]:span[1]] != str(value).encode():
            raise ValueError("native parser returned an invalid value type")
        return cast("ValueType", value)

    def _expression(self, raw: object, parent: tuple[int, int], depth: int) -> Expression:
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            raise TypeError("native parser returned an invalid expression")
        kind = raw["kind"]
        fields = {"nat": {"value"}, "bool": {"value"}, "name": {"name"},
                  "call": {"callee", "arguments"}, "binary": {"operator", "left", "right"},
                  "group": {"value"}}.get(kind)
        if fields is None:
            raise ValueError(f"native parser returned an unknown expression kind: {kind}")
        node, span, site = self._node(raw, kind, fields, parent, depth)
        def child(value: object) -> Expression:
            return self._expression(value, span, depth + 1)
        if kind == "nat":
            value = node["value"]
            if not isinstance(value, str) or not DECIMAL.fullmatch(value):
                raise ValueError("native parser returned an invalid decimal spelling")
            if len(value) > MAX_LITERAL_DIGITS:
                raise VelaError("limit", site.line, site.column, "native literal exceeds digit limit")
            if self.source[span[0]:span[1]] != value.encode():
                raise ValueError("native decimal differs from its source span")
            return expression(kind, value, site)
        if kind == "bool":
            value = node["value"]
            if type(value) is not bool or self.source[span[0]:span[1]] != (b"true" if value else b"false"):
                raise ValueError("native parser returned an invalid Boolean literal")
            return expression(kind, value, site)
        if kind == "name":
            name = self._text(node["name"], span)
            return expression(kind, name.text, name.site)
        if kind == "call":
            name = self._text(node["callee"], span)
            arguments = self._list(node["arguments"])
            self._ordered([node["callee"], *arguments], span)
            return expression(kind, name.text, name.site, tuple(child(value) for value in arguments))
        if kind == "group":
            return expression(kind, "", site, (child(node["value"]),))
        operator = self._text(node["operator"], span, identifier=False)
        if operator.text not in {"+", "*", "==", "<="}:
            raise ValueError("native parser returned an unknown binary operator")
        self._ordered([node["left"], node["operator"], node["right"]], span)
        return expression(kind, operator.text, operator.site, (child(node["left"]), child(node["right"])))

    def _block(self, raw: object, parent: tuple[int, int], depth: int) -> Block:
        node, span, _ = self._node(raw, "block", {"bindings", "exit"}, parent, depth)
        bindings = self._list(node["bindings"])
        self._ordered([*bindings, node["exit"]], span)
        if len(bindings) > MAX_BLOCK_DEPTH:
            raise VelaError("limit", 1, 1, "native block exceeds binding limit")
        converted: list[Binding] = []
        for raw_binding in bindings:
            binding, binding_span, site = self._node(raw_binding, "let", {"name", "value"}, span, depth + 1)
            self._ordered([binding["name"], binding["value"]], binding_span)
            converted.append(Binding(self._text(binding["name"], binding_span),
                                     self._expression(binding["value"], binding_span, depth + 2), site))
        raw_exit = node["exit"]
        if isinstance(raw_exit, dict) and raw_exit.get("kind") == "return":
            terminal, terminal_span, site = self._node(raw_exit, "return", {"value"}, span, depth + 1)
            exit_value: Return | Conditional = Return(self._expression(terminal["value"], terminal_span, depth + 2), site)
        else:
            terminal, terminal_span, site = self._node(raw_exit, "if", {"condition", "then", "else"}, span, depth + 1)
            self._ordered([terminal["condition"], terminal["then"], terminal["else"]], terminal_span)
            exit_value = Conditional(self._expression(terminal["condition"], terminal_span, depth + 2),
                                     self._block(terminal["then"], terminal_span, depth + 2),
                                     self._block(terminal["else"], terminal_span, depth + 2), site)
        return Block(tuple(converted), exit_value, converted[0].site if converted else exit_value.site)

    def _body(self, raw: object, parent: tuple[int, int], depth: int) -> Block:
        if not isinstance(raw, dict) or raw.get("kind") != "expression_body":
            return self._block(raw, parent, depth)
        node, span, site = self._node(raw, "expression_body", {"value"}, parent, depth)
        if (self.source[span[0]:span[0] + 2] != b"=>"
                or self.source[span[1] - 1:span[1]] != b";"):
            raise ValueError("native expression body differs from its source delimiters")
        raw_value = node["value"]
        if not isinstance(raw_value, dict) or "span" not in raw_value:
            raise ValueError("native expression body has no value node")
        value_span = self._span(raw_value.get("span"), (span[0] + 2, span[1] - 1))
        if (trivia_end(self.source, span[0] + 2) != value_span[0]
                or trivia_end(self.source, value_span[1]) != span[1] - 1):
            raise ValueError("native expression body leaves source tokens uncovered")
        value = self._expression(node["value"], (span[0] + 2, span[1] - 1), depth + 1)
        return Block((), Return(value, site), value.site)

    def module(self, raw: object) -> Module:
        node, span, _ = self._node(raw, "file", {"name", "functions"}, (0, len(self.source)), 1)
        functions = self._list(node["functions"])
        if not functions:
            raise ValueError("native syntax module has no functions")
        self._ordered([node["name"], *functions], span)
        converted: list[Function] = []
        for raw_function in functions:
            function, function_span, _ = self._node(raw_function, "function", {"name", "result", "parameters", "body"}, span, 2)
            parameters = self._list(function["parameters"])
            self._ordered([function["result"], function["name"], *parameters, function["body"]], function_span)
            converted_parameters: list[tuple[Name, ValueType]] = []
            for raw_parameter in parameters:
                parameter, parameter_span, _ = self._node(raw_parameter, "parameter", {"name", "type"}, function_span, 3)
                self._ordered([parameter["type"], parameter["name"]], parameter_span)
                converted_parameters.append((self._text(parameter["name"], parameter_span),
                                             self._type(parameter["type"], parameter_span, 4)))
            converted.append(Function(self._text(function["name"], function_span),
                                      self._type(function["result"], function_span, 3),
                                      tuple(converted_parameters), self._body(function["body"], function_span, 3)))
        return Module(self._text(node["name"], span), tuple(converted))


def decode(source: bytes, response: object) -> Module:
    """Accept only the complete, exact-source schema emitted by parse_source."""
    source_text(source)
    if (not isinstance(response, dict) or set(response) != {"schema", "source_sha256", "ast"}
            or type(response["schema"]) is not int or response["schema"] != 1
            or response["source_sha256"] != hashlib.sha256(source).hexdigest()):
        raise ValueError("native parser response has an invalid schema or source binding")
    return _Decoder(source).module(response["ast"])
