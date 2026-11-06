# SPDX-License-Identifier: Apache-2.0
"""Native syntax adapter for bounded mathematical compilation and observation."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos import vela_elaborate, vela_parser
from vos.vela import StaticEvaluation, ValueType
from vos.vela_ast import Name, position
from vos.vela_authoring import Finding, generic_type_findings, pattern_constructor_findings
from vos.vela_elaborate import Elaboration


def _build(parser: Path) -> vela_parser.Build:
    digest = hashlib.sha256(parser.read_bytes()).hexdigest()
    return vela_parser.Build(parser.parent, parser, {"generated_sha256": {"vela-parser": digest}})


@dataclass(frozen=True)
class Compilation(Elaboration):
    findings: tuple[Finding, ...] = ()


def inspect_source(source: bytes, parsed: object) -> Compilation:
    """Inspect type binders only after complete exact-source semantic acceptance.

    The [generic naming contract](../../docs/languages/vela/authoring-tools.md#generic-type-parameter-naming)
    keeps this advisory inspection separate from mathematical acceptance.
    """
    translation = vela_elaborate.elaborate(source, parsed)
    ast = cast("dict[str, object]", parsed)["ast"]
    pending: list[object] = [ast]
    names: list[tuple[int, Name]] = []
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("kind") == "generic_parameter" and item.get("mode") == "type":
                identifier = cast("dict[str, object]", item["name"])
                offset = cast("list[int]", identifier["span"])[0]
                names.append((offset, Name(cast("str", identifier["text"]),
                                           position(source[:offset].decode("utf-8")))))
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    names.sort(key=lambda item: item[0])
    findings = sorted(
        (*generic_type_findings(tuple(name for _, name in names)),
         *pattern_constructor_findings(source, cast("dict[str, object]", ast))),
        key=lambda item: (item.line, item.column, item.code),
    )
    return Compilation(translation.module, translation.gallina, tuple(findings))


def compile_source(source: bytes, parser: Path) -> Compilation:
    """Use the selected native parser and the existing exact-source elaborator."""
    parsed = vela_parser.parse_source(_build(parser), source, surface=True)
    return inspect_source(source, parsed)


def evaluate_source(source: bytes, expression: str, value_type: ValueType,
                    parser: Path) -> StaticEvaluation:
    """Check the entire module before parsing and reducing one console initializer."""
    compiled = _build(parser)
    parsed = vela_parser.parse_source(compiled, source, surface=True)
    return vela_elaborate.evaluate(
        source, parsed, expression, value_type,
        parse=lambda probe: vela_parser.parse_source(compiled, probe, surface=True))
