# SPDX-License-Identifier: Apache-2.0
"""Compose a descriptor-only typed graph and compare its finite source reference."""

import argparse
import json
from pathlib import Path

from vos import composer, corpus
from vos import composition as production


def _output(root: Path, relative: str, data: bytes) -> None:
    path = root / relative
    if (Path(relative).is_absolute() or ".." in Path(relative).parts
            or not path.resolve().is_relative_to(root.resolve())):
        raise composer.ComposerError("output path must stay inside the repository")
    if not path.resolve().is_relative_to((root / "out").resolve()):
        raise composer.ComposerError("generated composer output belongs under out/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _artifacts(root: Path, relative: str) -> dict[str, dict[str, str]]:
    """Resolve the producer's slot-to-path map without accepting reported digests."""
    value = production._json(production._path(root, relative))
    if not isinstance(value, dict):
        raise production.CompositionError("artifact paths: expected an object mapping slots to paths")
    result: dict[str, dict[str, str]] = {}
    for slot, path in value.items():
        if not isinstance(slot, str) or not isinstance(path, str):
            raise production.CompositionError("artifact paths: expected string slots and paths")
        result[slot] = production.reference(root, path)
    return result


def _reference_paths(value: object) -> list[str]:
    """Collect existing source references without reproducing composition fields."""
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"} and isinstance(value["path"], str):
            return [value["path"]]
        return [path for child in value.values() for path in _reference_paths(child)]
    if isinstance(value, list):
        return [path for child in value for path in _reference_paths(child)]
    return []


def _build_record(root: Path, args: argparse.Namespace) -> None:
    """Bind or check the actual published projections and produced byte files."""
    projection_paths = [f"{args.projections}/{name}" for name in production.OUTPUTS]
    outputs = {name: production._path(root, relative).read_bytes()
               for name, relative in zip(production.OUTPUTS, projection_paths, strict=True)}
    graph = production._path(root, args.graph).read_bytes()
    image = production.reference(root, args.image)
    if args.command == "check-build-record":
        record = production._json(production._path(root, args.record))
        production.validate_build_record(root, args.source, record, outputs, graph, image)
        print("ok composer: production build record binds current bytes; admission remains open")
        return
    artifacts = _artifacts(root, args.artifacts)
    record = production.build_record(root, args.source, outputs, artifacts, image, graph)
    bound_source = production._json(production._path(root, args.source),
                                    json.loads(outputs["manifest.json"])["binding"]["input"]["sha256"])
    # Publishing a record must not replace one of the products it just bound.
    inputs = [args.source, args.artifacts, args.image, args.graph, *projection_paths,
              *(ref["path"] for ref in artifacts.values()),
              *_reference_paths(record["binding"]), *_reference_paths(bound_source)]
    if production._path(root, args.output) in {production._path(root, path) for path in inputs}:
        raise production.CompositionError("build record output would overwrite an input or product")
    _output(root, args.output, composer.canonical_bytes(record))
    print(json.dumps({"output": args.output, "image_sha256": image["sha256"],
                      "graph_sha256": record["graph_sha256"],
                      "production_admission": False}, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    emit = commands.add_parser("compose", help="emit canonical graph bytes from a descriptor document")
    emit.add_argument("source")
    emit.add_argument("--output", required=True)
    fixture = commands.add_parser("fixture", help="emit the reference's synthetic descriptor document")
    fixture.add_argument("--output", required=True)
    project = commands.add_parser("project", help="emit checked production composition projections")
    project.add_argument("source")
    project.add_argument("--output", required=True)
    check_project = commands.add_parser("check-project", help="regenerate and compare production projections")
    check_project.add_argument("source", nargs="?", default=production.EXAMPLE)
    check_project.add_argument("--output", default=production.GENERATED)
    for command, help_text in (
            ("build-record", "bind published projections and produced artifacts to the final image"),
            ("check-build-record", "revalidate a saved production build record against current bytes")):
        build = commands.add_parser(command, help=help_text)
        build.add_argument("source")
        build.add_argument("--projections", default=production.GENERATED)
        build.add_argument("--graph", required=True)
        build.add_argument("--image", required=True)
        if command == "build-record":
            build.add_argument("--artifacts", required=True, help="JSON object mapping runtime slots to paths")
            build.add_argument("--output", required=True)
        else:
            build.add_argument("--record", required=True)
    promote = commands.add_parser("promote", help="check production admission readiness (currently refused)")
    promote.add_argument("source")
    commands.add_parser("compare", help="compare the executable filter with source predicate readings")
    commands.add_parser("prove", help="compile finite equalities in the native guest lane")
    args = parser.parse_args(argv)
    root = corpus.find_root()
    try:
        if args.command in ("build-record", "check-build-record"):
            _build_record(root, args)
            return 0
        if args.command == "project":
            result = production.emit(root, args.source, args.output)
            print(json.dumps({"output": args.output, "projections": result,
                              "production_admission": False}, indent=2))
            return 0
        if args.command == "check-project":
            production.check(root, args.source, args.output)
            print("ok composer: production composition projections reproduce; admission remains open")
            return 0
        if args.command == "promote":
            production.require_production(root, args.source)
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
    except (OSError, ValueError) as error:
        print(f"FAIL composer: {error}")
        return 1
