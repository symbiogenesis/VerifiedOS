# SPDX-License-Identifier: Apache-2.0
"""Native syntax adapter for bounded mathematical compilation and observation."""

import hashlib
from pathlib import Path

from vos import vela_elaborate, vela_parser
from vos.vela import StaticEvaluation, ValueType
from vos.vela_elaborate import Elaboration


def _build(parser: Path) -> vela_parser.Build:
    digest = hashlib.sha256(parser.read_bytes()).hexdigest()
    return vela_parser.Build(parser.parent, parser, {"generated_sha256": {"vela-parser": digest}})


def compile_source(source: bytes, parser: Path) -> Elaboration:
    """Use the selected native parser and the existing exact-source elaborator."""
    parsed = vela_parser.parse_source(_build(parser), source, surface=True)
    return vela_elaborate.elaborate(source, parsed)


def evaluate_source(source: bytes, expression: str, value_type: ValueType,
                    parser: Path) -> StaticEvaluation:
    """Check the entire module before parsing and reducing one console initializer."""
    compiled = _build(parser)
    parsed = vela_parser.parse_source(compiled, source, surface=True)
    return vela_elaborate.evaluate(
        source, parsed, expression, value_type,
        parse=lambda probe: vela_parser.parse_source(compiled, probe, surface=True))
