# SPDX-License-Identifier: Apache-2.0
"""Compose a descriptor-only typed graph and compare its finite source reference."""

import argparse
import json
from pathlib import Path

from vos import composer, corpus


def _output(root: Path, relative: str, data: bytes) -> None:
    path = root / relative
    if (Path(relative).is_absolute() or ".." in Path(relative).parts
            or not path.resolve().is_relative_to(root.resolve())):
        raise composer.ComposerError("output path must stay inside the repository")
    if not path.resolve().is_relative_to((root / "out").resolve()):
        raise composer.ComposerError("generated composer output belongs under out/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    emit = commands.add_parser("compose", help="emit canonical graph bytes from a descriptor document")
    emit.add_argument("source")
    emit.add_argument("--output", required=True)
    fixture = commands.add_parser("fixture", help="emit the reference's synthetic descriptor document")
    fixture.add_argument("--output", required=True)
    commands.add_parser("compare", help="compare the executable filter with source predicate readings")
    commands.add_parser("prove", help="compile finite equalities in the native guest lane")
    args = parser.parse_args(argv)
    root = corpus.find_root()
    try:
        if args.command == "compose":
            composition = composer.load_document(root, args.source)
            _output(root, args.output, composer.graph_bytes(composition))
            print(json.dumps({"output": args.output, "graph_sha256": composer.graph_sha256(composition),
                              "accepted_edges": len(composer.compose(composition).graph_edges),
                              "refused_edges": len(composer.refused_edges(composition)),
                              "generation_admission": "separate"}, indent=2))
            return 0
        if args.command == "fixture":
            composition = composer.reference_fixture(root)
            _output(root, args.output, composer.canonical_bytes(composer.document(composition)))
            print(f"ok composer: emitted synthetic descriptors to {args.output}")
            return 0
        result = (composer.prove_reference(root) if args.command == "prove"
                  else composer.compare_reference(root))
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    except (composer.ComposerError, OSError, UnicodeError) as error:
        print(f"FAIL composer: {error}")
        return 1
