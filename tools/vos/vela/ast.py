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
DECIMAL = re.compile(r"[0-9](?:_?[0-9])*")
KEYWORDS = frozenset({"module", "public", "return", "let", "const", "if", "else", "Nat", "bool",
                      "true", "false"})
UNSUPPORTED = frozenset({"fn", "Bool", "async", "await", "effect", "effects", "handler",
                        "handle", "resume", "dispose", "mut", "var", "unsafe", "borrow",
                        "requires", "ensures", "restores", "ghost", "tracked", "grade",
                        "proof", "owned", "move", "ref", "in", "out", "captures", "scope",
                        "spawn", "commit", "on", "cancel", "region", "view", "union", "foreach"})


def unsupported_message(spelling: str) -> str:
    """Explain requested ownership modes without claiming to check their laws."""
    mode = {"in": "a shared read loan", "ref": "an initialized exclusive loan",
            "out": "an exclusive initialization loan", "owned": "consuming ownership",
            "move": "an explicit ownership transfer"}.get(spelling)
    if spelling == "var":
        return ("'var' declares a mutable binding; let and unmarked type-first bindings are immutable. "
                "Local reassignment requires the wider Vela surface; the pure prototype does not support mutation")
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
    labels: tuple[Name | None, ...] = ()


def expression(kind: str, value: str | bool, site: Site,
               children: tuple[Expression, ...] = (), *, labels: tuple[Name | None, ...] = ()) -> Expression:
    depth = max((child.depth for child in children), default=0) + (kind != "group")
    if depth > MAX_EXPRESSION_DEPTH:
        raise VelaError("limit", site.line, site.column,
                        f"expression exceeds depth {MAX_EXPRESSION_DEPTH}")
    nesting = max((child.nesting for child in children), default=1)
    if kind in {"group", "unary"} or (kind == "call" and children):
        nesting += 1
    if nesting > MAX_EXPRESSION_DEPTH:
        raise VelaError("limit", site.line, site.column,
                        f"expression nesting exceeds {MAX_EXPRESSION_DEPTH}")
    return Expression(kind, value, site, children, depth, nesting, labels)


@dataclass(frozen=True)
class Binding:
    name: Name
    value: Expression
    site: Site
    annotation: ValueType | None = None
    explicit_binding: bool = True


@dataclass(frozen=True)
class Reassignment:
    name: Name
    value: Expression
    site: Site


@dataclass(frozen=True)
class Constant:
    name: Name
    value_type: ValueType
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
    bindings: tuple[Binding | Reassignment | Constant, ...]
    terminal: Return | Conditional
    site: Site


@dataclass(frozen=True)
class Function:
    name: Name
    result: ValueType
    parameters: tuple[tuple[Name, ValueType], ...]
    body: Block
    is_const: bool = False
    const_parameters: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Module:
    name: Name
    declarations: tuple[Function | Constant, ...]


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

    def _keyword(self, cursor: int, keyword: bytes) -> int:
        end = cursor + len(keyword)
        following = self.source[end:end + 1]
        if (self.source[cursor:end] != keyword
                or (following and (following.isalnum() or following == b"_"))):
            raise ValueError("native syntax keyword differs from its source")
        return trivia_end(self.source, end)

    def _identifier_edges(self, start: int, end: int) -> None:
        for adjacent in (self.source[start - 1:start] if start else b"", self.source[end:end + 1]):
            if adjacent and (adjacent.isalnum() or adjacent == b"_"):
                raise ValueError("native identifier or type splits a source token")

    def _text(self, raw: object, parent: tuple[int, int], *, identifier: bool = True) -> Name:
        if not isinstance(raw, dict) or set(raw) != {"text", "span"} or not isinstance(raw["text"], str):
            raise ValueError("native parser returned an invalid name or operator")
        text = raw["text"]
        start, end = self._span(raw["span"], parent)
        if self.source[start:end] != text.encode("utf-8"):
            raise ValueError("native name or operator differs from its source span")
        if identifier and (not IDENTIFIER.fullmatch(text) or text in KEYWORDS | UNSUPPORTED):
            raise ValueError("native parser returned an invalid identifier")
        if identifier:
            self._identifier_edges(start, end)
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
        self._identifier_edges(*span)
        return cast("ValueType", value)

    def _expression(self, raw: object, parent: tuple[int, int], depth: int) -> Expression:
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            raise TypeError("native parser returned an invalid expression")
        kind = raw["kind"]
        fields = {"nat": {"value"}, "bool": {"value"}, "name": {"name"},
                  "call": {"callee", "arguments"}, "binary": {"operator", "left", "right"},
                  "unary": {"operator", "value"},
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
            if len(value.replace("_", "")) > MAX_LITERAL_DIGITS:
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
            if not isinstance(node["name"], dict) or self._span(node["name"].get("span"), span) != span:
                raise ValueError("native name expression leaves source tokens uncovered")
            return expression(kind, name.text, name.site)
        if kind == "call":
            name = self._text(node["callee"], span)
            arguments = self._list(node["arguments"])
            self._ordered([node["callee"], *arguments], span)
            raw_callee = node["callee"]
            if not isinstance(raw_callee, dict):
                raise TypeError("native call has no callee")
            callee_span = self._span(raw_callee.get("span"), span)
            if callee_span[0] != span[0]:
                raise ValueError("native call leaves source callee tokens uncovered")
            cursor = trivia_end(self.source, callee_span[1])
            if self.source[cursor:cursor + 1] != b"(":
                raise ValueError("native call differs from its source opening")
            cursor = trivia_end(self.source, cursor + 1)
            for index, raw_argument in enumerate(arguments):
                if not isinstance(raw_argument, dict):
                    raise TypeError("native call has an invalid argument")
                argument_span = self._span(raw_argument.get("span"), span)
                if cursor != argument_span[0]:
                    raise ValueError("native call leaves source argument tokens uncovered")
                cursor = trivia_end(self.source, argument_span[1])
                if index < len(arguments) - 1:
                    if self.source[cursor:cursor + 1] != b",":
                        raise ValueError("native call differs from its source separator")
                    cursor = trivia_end(self.source, cursor + 1)
            if arguments and self.source[cursor:cursor + 1] == b",":
                cursor = trivia_end(self.source, cursor + 1)
            if cursor != span[1] - 1 or self.source[cursor:cursor + 1] != b")":
                raise ValueError("native call leaves source argument tokens uncovered")
            values: list[Expression] = []
            labels: list[Name | None] = []
            for raw_argument in arguments:
                argument, argument_span, _ = self._node(raw_argument, "argument", {"label", "value"}, span, depth + 1)
                label = None if argument["label"] is None else self._text(argument["label"], argument_span)
                value = self._expression(argument["value"], argument_span, depth + 2)
                if not isinstance(argument["value"], dict):
                    raise TypeError("native argument has no expression")
                value_span = self._span(argument["value"].get("span"), argument_span)
                if label is None:
                    if value_span != argument_span:
                        raise ValueError("native positional argument leaves source tokens uncovered")
                else:
                    raw_label = argument["label"]
                    if not isinstance(raw_label, dict):
                        raise TypeError("native argument has an invalid label")
                    label_span = self._span(raw_label.get("span"), argument_span)
                    colon = trivia_end(self.source, label_span[1])
                    if (label_span[0] != argument_span[0] or self.source[colon:colon + 1] != b":"
                            or trivia_end(self.source, colon + 1) != value_span[0]
                            or value_span[1] != argument_span[1]):
                        raise ValueError("native argument label differs from source delimiters")
                labels.append(label)
                values.append(value)
            return expression(kind, name.text, name.site, tuple(values), labels=tuple(labels))
        if kind == "group":
            raw_value = node["value"]
            if not isinstance(raw_value, dict):
                raise TypeError("native group has no located value")
            value_span = self._span(raw_value.get("span"), span)
            if (self.source[span[0]:span[0] + 1] != b"("
                    or trivia_end(self.source, span[0] + 1) != value_span[0]
                    or trivia_end(self.source, value_span[1]) != span[1] - 1
                    or self.source[span[1] - 1:span[1]] != b")"):
                raise ValueError("native group leaves source tokens uncovered")
            return expression(kind, "", site, (child(node["value"]),))
        operator = self._text(node["operator"], span, identifier=False)
        if kind == "unary":
            if operator.text != "!":
                raise ValueError("native parser returned an unknown unary operator")
            self._ordered([node["operator"], node["value"]], span)
            if not isinstance(node["operator"], dict) or not isinstance(node["value"], dict):
                raise TypeError("native unary operator has no located operand")
            operator_span = self._span(node["operator"].get("span"), span)
            value_span = self._span(node["value"].get("span"), span)
            if (operator_span[0] != span[0] or value_span[1] != span[1]
                    or trivia_end(self.source, operator_span[1]) != value_span[0]):
                raise ValueError("native unary expression leaves source tokens uncovered")
            return expression(kind, operator.text, operator.site, (child(node["value"]),))
        if operator.text not in {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"}:
            raise ValueError("native parser returned an unknown binary operator")
        self._ordered([node["left"], node["operator"], node["right"]], span)
        if not all(isinstance(node[field], dict) for field in ("left", "operator", "right")):
            raise TypeError("native operator has no located operands")
        left_span = self._span(cast("dict[str, object]", node["left"]).get("span"), span)
        op_span = self._span(cast("dict[str, object]", node["operator"]).get("span"), span)
        right_span = self._span(cast("dict[str, object]", node["right"]).get("span"), span)
        if (left_span[0] != span[0] or right_span[1] != span[1]
                or trivia_end(self.source, left_span[1]) != op_span[0]
                or trivia_end(self.source, op_span[1]) != right_span[0]):
            raise ValueError("native binary expression leaves source tokens uncovered")
        return expression(kind, operator.text, operator.site, (child(node["left"]), child(node["right"])))

    def _constant(self, raw: object, kind: str, parent: tuple[int, int], depth: int) -> Constant:
        node, span, site = self._node(raw, kind, {"name", "type", "value"}, parent, depth)
        self._ordered([node["type"], node["name"], node["value"]], span)
        value_type = self._type(node["type"], span, depth + 1)
        name = self._text(node["name"], span)
        value = self._expression(node["value"], span, depth + 1)
        cursor = span[0]
        for keyword in ((b"public", b"const") if kind == "constant" else (b"const",)):
            if self.source[cursor:cursor + len(keyword)] != keyword:
                raise ValueError("native constant differs from its source declaration")
            end = cursor + len(keyword)
            if self.source[end:end + 1] and (self.source[end:end + 1].isalnum() or self.source[end:end + 1] == b"_"):
                raise ValueError("native constant keyword ends inside an identifier")
            cursor = trivia_end(self.source, end)
        raw_type, raw_name, raw_value = node["type"], node["name"], node["value"]
        if not all(isinstance(item, dict) for item in (raw_type, raw_name, raw_value)):
            raise TypeError("native constant is missing located fields")
        type_span = self._span(cast("dict[str, object]", raw_type).get("span"), span)
        name_span = self._span(cast("dict[str, object]", raw_name).get("span"), span)
        value_span = self._span(cast("dict[str, object]", raw_value).get("span"), span)
        equal = trivia_end(self.source, name_span[1])
        if (cursor != type_span[0] or trivia_end(self.source, type_span[1]) != name_span[0]
                or self.source[equal:equal + 1] != b"="
                or trivia_end(self.source, equal + 1) != value_span[0]
                or trivia_end(self.source, value_span[1]) != span[1] - 1
                or self.source[span[1] - 1:span[1]] != b";"):
            raise ValueError("native constant leaves source tokens uncovered")
        return Constant(name, value_type, value, site)

    def _block(self, raw: object, parent: tuple[int, int], depth: int) -> Block:
        node, span, _ = self._node(raw, "block", {"bindings", "exit"}, parent, depth)
        bindings = self._list(node["bindings"])
        self._ordered([*bindings, node["exit"]], span)
        if self.source[span[0]:span[0] + 1] != b"{" or self.source[span[1] - 1:span[1]] != b"}":
            raise ValueError("native block differs from its source braces")
        cursor = trivia_end(self.source, span[0] + 1)
        for raw_statement in [*bindings, node["exit"]]:
            if not isinstance(raw_statement, dict):
                raise TypeError("native block has no located statement")
            statement_span = self._span(raw_statement.get("span"), span)
            if cursor != statement_span[0]:
                raise ValueError("native block leaves source statements uncovered")
            cursor = trivia_end(self.source, statement_span[1])
        if cursor != span[1] - 1:
            raise ValueError("native block leaves source statements uncovered")
        if len(bindings) > MAX_BLOCK_DEPTH:
            raise VelaError("limit", 1, 1, "native block exceeds binding limit")
        converted: list[Binding | Reassignment | Constant] = []
        for raw_binding in bindings:
            kind = raw_binding.get("kind") if isinstance(raw_binding, dict) else None
            if kind == "constant_local":
                converted.append(self._constant(raw_binding, kind, span, depth + 1))
                continue
            if kind not in {"let", "reassignment"}:
                raise ValueError("native block has an invalid binding role")
            fields = {"name", "value"}
            annotated = isinstance(raw_binding, dict) and "type" in raw_binding
            if annotated:
                if kind == "reassignment":
                    raise ValueError("native reassignment cannot carry a type annotation")
                fields.add("type")
            binding, binding_span, site = self._node(raw_binding, kind, fields, span, depth + 1)
            raw_annotation = binding.get("type")
            self._ordered(([raw_annotation] if annotated else []) + [binding["name"], binding["value"]], binding_span)
            raw_name, raw_value = binding["name"], binding["value"]
            if not isinstance(raw_name, dict) or not isinstance(raw_value, dict):
                raise TypeError("native binding has no located name/value")
            name_span = self._span(raw_name.get("span"), binding_span)
            value_span = self._span(raw_value.get("span"), binding_span)
            cursor = self._keyword(binding_span[0], b"let") if kind == "let" else binding_span[0]
            annotation = None
            if annotated:
                if not isinstance(raw_annotation, dict):
                    raise TypeError("native typed binding has no located annotation")
                annotation_span = self._span(raw_annotation.get("span"), binding_span)
                if cursor != annotation_span[0]:
                    raise ValueError("native typed binding leaves its annotation uncovered")
                annotation = self._type(raw_annotation, binding_span, depth + 2)
                cursor = trivia_end(self.source, annotation_span[1])
            equal = trivia_end(self.source, name_span[1])
            if (cursor != name_span[0] or self.source[equal:equal + 1] != b"="
                    or trivia_end(self.source, equal + 1) != value_span[0]
                    or trivia_end(self.source, value_span[1]) != binding_span[1] - 1
                    or self.source[binding_span[1] - 1:binding_span[1]] != b";"):
                raise ValueError("native binding differs from its source spelling or coverage")
            binding_name = self._text(binding["name"], binding_span)
            binding_value = self._expression(binding["value"], binding_span, depth + 2)
            converted.append(Reassignment(binding_name, binding_value, site) if kind == "reassignment"
                             else Binding(binding_name, binding_value, site, annotation, kind == "let"))
        raw_exit = node["exit"]
        if isinstance(raw_exit, dict) and raw_exit.get("kind") == "return":
            terminal, terminal_span, site = self._node(raw_exit, "return", {"value"}, span, depth + 1)
            raw_value = terminal["value"]
            if not isinstance(raw_value, dict):
                raise TypeError("native return has no located value")
            value_span = self._span(raw_value.get("span"), terminal_span)
            if (self._keyword(terminal_span[0], b"return") != value_span[0]
                    or trivia_end(self.source, value_span[1]) != terminal_span[1] - 1
                    or self.source[terminal_span[1] - 1:terminal_span[1]] != b";"):
                raise ValueError("native return leaves source tokens uncovered")
            exit_value: Return | Conditional = Return(self._expression(terminal["value"], terminal_span, depth + 2), site)
        else:
            terminal, terminal_span, site = self._node(raw_exit, "if", {"condition", "then", "else"}, span, depth + 1)
            self._ordered([terminal["condition"], terminal["then"], terminal["else"]], terminal_span)
            raw_condition, raw_yes, raw_no = terminal["condition"], terminal["then"], terminal["else"]
            if not all(isinstance(item, dict) for item in (raw_condition, raw_yes, raw_no)):
                raise TypeError("native conditional has no located branches")
            condition_span = self._span(cast("dict[str, object]", raw_condition).get("span"), terminal_span)
            yes_span = self._span(cast("dict[str, object]", raw_yes).get("span"), terminal_span)
            no_span = self._span(cast("dict[str, object]", raw_no).get("span"), terminal_span)
            opening = self._keyword(terminal_span[0], b"if")
            closing = trivia_end(self.source, condition_span[1])
            if (self.source[opening:opening + 1] != b"("
                    or trivia_end(self.source, opening + 1) != condition_span[0]
                    or self.source[closing:closing + 1] != b")"
                    or trivia_end(self.source, closing + 1) != yes_span[0]
                    or self._keyword(trivia_end(self.source, yes_span[1]), b"else") != no_span[0]
                    or no_span[1] != terminal_span[1]):
                raise ValueError("native conditional leaves source branches uncovered")
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
        node, span, _ = self._node(raw, "file", {"name", "declarations"}, (0, len(self.source)), 1)
        declarations = self._list(node["declarations"])
        if not declarations:
            raise ValueError("native syntax module has no declarations")
        self._ordered([node["name"], *declarations], span)
        raw_name = node["name"]
        if not isinstance(raw_name, dict):
            raise TypeError("native module has no located name")
        name_span = self._span(raw_name.get("span"), span)
        semicolon = trivia_end(self.source, name_span[1])
        if (span[0] != trivia_end(self.source, 0) or self._keyword(span[0], b"module") != name_span[0]
                or self.source[semicolon:semicolon + 1] != b";"):
            raise ValueError("native module differs from its source header")
        cursor = trivia_end(self.source, semicolon + 1)
        for raw_declaration in declarations:
            if not isinstance(raw_declaration, dict):
                raise TypeError("native module has no located declaration")
            declaration_span = self._span(raw_declaration.get("span"), span)
            if declaration_span[0] != cursor:
                raise ValueError("native module leaves source declarations uncovered")
            cursor = trivia_end(self.source, declaration_span[1])
        if cursor != len(self.source):
            raise ValueError("native module leaves source declarations uncovered")
        converted: list[Function | Constant] = []
        for raw_function in declarations:
            if isinstance(raw_function, dict) and raw_function.get("kind") == "constant":
                converted.append(self._constant(raw_function, "constant", span, 2))
                continue
            function_fields = {"name", "result", "parameters", "body"}
            if isinstance(raw_function, dict) and "const" in raw_function:
                function_fields.add("const")
            function, function_span, _ = self._node(raw_function, "function", function_fields, span, 2)
            is_const = function.get("const", False)
            if type(is_const) is not bool:
                raise ValueError("native function has an invalid const qualifier")
            parameters = self._list(function["parameters"])
            self._ordered([function["result"], function["name"], *parameters, function["body"]], function_span)
            converted_parameters: list[tuple[Name, ValueType]] = []
            const_parameters: set[str] = set()
            for raw_parameter in parameters:
                parameter_fields = {"name", "type"}
                if isinstance(raw_parameter, dict) and "const" in raw_parameter:
                    parameter_fields.add("const")
                parameter, parameter_span, _ = self._node(raw_parameter, "parameter", parameter_fields, function_span, 3)
                parameter_const = parameter.get("const", False)
                if type(parameter_const) is not bool:
                    raise ValueError("native parameter has an invalid const qualifier")
                self._ordered([parameter["type"], parameter["name"]], parameter_span)
                parameter_name = self._text(parameter["name"], parameter_span)
                converted_parameters.append((parameter_name, self._type(parameter["type"], parameter_span, 4)))
                if parameter_const:
                    const_parameters.add(parameter_name.text)
            raw_result, raw_name, raw_body = function["result"], function["name"], function["body"]
            if not all(isinstance(item, dict) for item in (raw_result, raw_name, raw_body)):
                raise TypeError("native function has no located signature/body")
            result_span = self._span(cast("dict[str, object]", raw_result).get("span"), function_span)
            name_span = self._span(cast("dict[str, object]", raw_name).get("span"), function_span)
            body_span = self._span(cast("dict[str, object]", raw_body).get("span"), function_span)
            opening = trivia_end(self.source, name_span[1])
            result_start = self._keyword(function_span[0], b"public")
            if is_const:
                result_start = self._keyword(result_start, b"const")
            if (result_start != result_span[0]
                    or trivia_end(self.source, result_span[1]) != name_span[0]
                    or self.source[opening:opening + 1] != b"("):
                raise ValueError("native function differs from its source signature")
            cursor = trivia_end(self.source, opening + 1)
            for index, raw_parameter in enumerate(parameters):
                if not isinstance(raw_parameter, dict):
                    raise TypeError("native function has no located parameter")
                parameter_span = self._span(raw_parameter.get("span"), function_span)
                raw_type, raw_parameter_name = raw_parameter["type"], raw_parameter["name"]
                if not isinstance(raw_type, dict) or not isinstance(raw_parameter_name, dict):
                    raise TypeError("native parameter has no located name/type")
                type_span = self._span(raw_type.get("span"), parameter_span)
                binder_span = self._span(raw_parameter_name.get("span"), parameter_span)
                type_start = parameter_span[0]
                if raw_parameter.get("const", False):
                    type_start = self._keyword(type_start, b"const")
                if (cursor != parameter_span[0] or type_span[0] != type_start
                        or trivia_end(self.source, type_span[1]) != binder_span[0]
                        or binder_span[1] != parameter_span[1]):
                    raise ValueError("native function leaves source parameters uncovered")
                cursor = trivia_end(self.source, parameter_span[1])
                if index < len(parameters) - 1:
                    if self.source[cursor:cursor + 1] != b",":
                        raise ValueError("native function parameter separator differs")
                    cursor = trivia_end(self.source, cursor + 1)
            if parameters and self.source[cursor:cursor + 1] == b",":
                cursor = trivia_end(self.source, cursor + 1)
            if (self.source[cursor:cursor + 1] != b")"
                    or trivia_end(self.source, cursor + 1) != body_span[0]
                    or body_span[1] != function_span[1]):
                raise ValueError("native function leaves source signature/body tokens uncovered")
            converted.append(Function(self._text(function["name"], function_span),
                                      self._type(function["result"], function_span, 3),
                                      tuple(converted_parameters), self._body(function["body"], function_span, 3),
                                      is_const, frozenset(const_parameters)))
        return Module(self._text(node["name"], span), tuple(converted))


def decode(source: bytes, response: object) -> Module:
    """Accept only the complete, exact-source schema emitted by parse_source."""
    source_text(source)
    if (not isinstance(response, dict) or set(response) != {"schema", "source_sha256", "ast"}
            or type(response["schema"]) is not int or response["schema"] != 1
            or response["source_sha256"] != hashlib.sha256(source).hexdigest()):
        raise ValueError("native parser response has an invalid schema or source binding")
    return _Decoder(source).module(response["ast"])
