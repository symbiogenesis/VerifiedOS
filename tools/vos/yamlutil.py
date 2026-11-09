# SPDX-License-Identifier: Apache-2.0
"""Compose policy YAML without constructing objects or guessing keys from lines."""

import re
from collections.abc import Iterator
from typing import cast, override

from ruamel.yaml.composer import Composer
from ruamel.yaml.error import StreamMark, YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from ruamel.yaml.parser import Parser
from ruamel.yaml.reader import Reader
from ruamel.yaml.resolver import BaseResolver
from ruamel.yaml.scanner import Scanner

__all__ = [
    "MappingNode",
    "Node",
    "ScalarNode",
    "SequenceNode",
    "StreamMark",
    "fields",
    "lines",
    "mappings",
    "read",
    "start",
]

_BREAK: re.Pattern[str] = re.compile(r"\r\n|[\r\n\x85\u2028\u2029]")


class _NodeLoader(Reader, Scanner, Parser, Composer, BaseResolver):
    """Pure-Python YAML node composer without implicit scalar tag coercion."""

    comment_handling = None
    max_depth = None
    processing_version = (1, 1)

    def __init__(self, text: str) -> None:
        Reader.__init__(self, text, loader=self)
        Scanner.__init__(self, loader=self)
        Parser.__init__(self, loader=self)
        Composer.__init__(self, loader=self)
        BaseResolver.__init__(self, loadumper=self)

    @override
    def forward(self, length: int = 1) -> None:
        if self.pointer + length + 1 >= len(self.buffer):
            self.update(length + 1)
        while length != 0:
            ch = self.buffer[self.pointer]
            self.pointer += 1
            self.index += 1
            if ch in "\n\x85\u2028\u2029" or (
                ch == "\r" and self.buffer[self.pointer] != "\n"
            ):
                self.line += 1
                self.column = 0
            elif ch != "\ufeff":
                self.column += 1
            length -= 1


def lines(text: str) -> list[str]:
    """Source lines under the parser's YAML line-break convention."""
    return cast("list[str]", _BREAK.split(text))


def start(node: Node) -> StreamMark:
    """Require the source position a consumer uses for diagnostics and policy."""
    mark = node.start_mark
    if mark is None:
        raise ValueError("YAML node has no source start")
    return cast("StreamMark", mark)


def fields(node: MappingNode) -> dict[str, Node]:
    """Read a mapping without silently collapsing duplicate or compound keys."""
    found: dict[str, Node] = {}
    for key, value in node.value:
        where = f"line {start(key).line + 1}"
        if not isinstance(key, ScalarNode) or key.tag != "tag:yaml.org,2002:str":
            raise ValueError(f"{where}: YAML mapping keys must be strings")
        if key.value == "<<":
            raise ValueError(f"{where}: YAML merge keys are not admitted")
        if key.value in found:
            raise ValueError(f"{where}: duplicate YAML key {key.value!r}")
        found[key.value] = value
    return found


def read(text: str) -> Node:
    """Read one nonempty tree; refuse aliases, merges and non-text scalar tags.

    BaseResolver leaves plain scalars as text, including workflow keys such as `on`.
    Composition never invokes a YAML constructor. Node identity detects aliases
    and cycles before a consumer can miss a second occurrence or recurse forever.
    """
    loader = _NodeLoader(text)
    try:
        root = cast("Node | None", loader.get_single_node())
    except (YAMLError, RecursionError) as error:
        raise ValueError(f"invalid YAML: {error}") from error
    finally:
        loader.dispose()
    if root is None:
        raise ValueError("empty YAML document")
    pending = [root]
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        where = f"line {start(node).line + 1}"
        if id(node) in seen:
            raise ValueError(f"{where}: YAML aliases and cycles are not admitted")
        seen.add(id(node))
        if isinstance(node, MappingNode):
            kind = "map"
            fields(node)
            pending.extend(child for pair in node.value for child in pair)
        elif isinstance(node, SequenceNode):
            kind = "seq"
            pending.extend(node.value)
        else:
            kind = "str"
        if node.tag != f"tag:yaml.org,2002:{kind}":
            raise ValueError(f"{where}: YAML tag {node.tag!r} is not admitted for {kind}")
    return root


def mappings(root: Node) -> Iterator[MappingNode]:
    """Visit the actual mappings of a tree already validated by `read`."""
    pending = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, MappingNode):
            yield node
            pending.extend(reversed(tuple(fields(node).values())))
        elif isinstance(node, SequenceNode):
            pending.extend(reversed(node.value))
