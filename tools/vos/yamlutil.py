# SPDX-License-Identifier: Apache-2.0
"""Compose policy YAML without constructing objects or guessing keys from lines."""

import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from yaml.error import Mark
    from yaml.nodes import MappingNode, Node

_BREAK: re.Pattern[str] = re.compile(r"\r\n|[\r\n\x85\u2028\u2029]")


def lines(text: str) -> list[str]:
    """Source lines under the parser's YAML line-break convention."""
    return cast("list[str]", _BREAK.split(text))


def start(node: Node) -> Mark:
    """Require the source position a consumer uses for diagnostics and policy."""
    mark = node.start_mark
    if mark is None:
        raise ValueError("YAML node has no source start")
    return cast("Mark", mark)


def fields(node: MappingNode) -> dict[str, Node]:
    """Read a mapping without silently collapsing duplicate or compound keys."""
    from yaml.nodes import ScalarNode  # noqa: PLC0415

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

    BaseLoader leaves plain scalars as text, including workflow keys such as `on`.
    Composition never invokes a YAML constructor. Node identity detects aliases
    and cycles before a consumer can miss a second occurrence or recurse forever.
    """
    from yaml import YAMLError, compose  # noqa: PLC0415
    from yaml.nodes import MappingNode, SequenceNode  # noqa: PLC0415

    try:
        from yaml.cyaml import CBaseLoader as NodeLoader  # noqa: PLC0415
    except ImportError:
        from yaml import BaseLoader as NodeLoader  # noqa: PLC0415

    try:
        root = cast("Node | None", compose(text, Loader=NodeLoader))
    except (YAMLError, RecursionError) as error:
        raise ValueError(f"invalid YAML: {error}") from error
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
    from yaml.nodes import MappingNode, SequenceNode  # noqa: PLC0415

    pending = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, MappingNode):
            yield node
            pending.extend(reversed(tuple(fields(node).values())))
        elif isinstance(node, SequenceNode):
            pending.extend(reversed(node.value))
