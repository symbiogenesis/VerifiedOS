# SPDX-License-Identifier: Apache-2.0
"""Offline executable port of HandlerGraph's descriptor-only graph filter.

The input is data, never package code. Numeric intent/type/world spaces remain
composition declarations; this tool neither closes their vocabulary nor decides
the reference's open ambiguity policy. Parser flags are declarations, not proof
evidence. Admission and real package descriptor production are separate joins.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

from vos import env
from vos.proofs import strip_comments

REFERENCE = "proofs/HandlerGraph.v"


class ComposerError(ValueError):
    """A descriptor or reference is malformed, unsupported or inconsistent."""


@dataclass(frozen=True)
class Edge:
    edge_owner: int
    edge_target: int
    edge_intent: int
    edge_from: int
    edge_to: int
    edge_limit: int
    edge_world: int
    edge_format: int
    edge_bounds: int
    edge_ring: int


@dataclass(frozen=True)
class Descriptor:
    package_id: str
    desc_manifest: int
    desc_edges: tuple[Edge, ...]


@dataclass(frozen=True)
class CompositionInput:
    descriptors: tuple[Descriptor, ...]
    roster: tuple[int, ...]
    type_count: int
    intent_count: int
    world_count: int
    inventory: frozenset[int]
    verified_parsers: frozenset[int]
    ring_depth_ceiling: int


@dataclass(frozen=True)
class Graph:
    graph_nodes: tuple[int, ...]
    graph_edges: tuple[Edge, ...]


@dataclass(frozen=True)
class RefusedEdge:
    descriptor: int
    position: int
    edge: Edge
    failed_conjuncts: tuple[int, ...]


def canonical_bytes(value: object) -> bytes:
    """One byte representation, including a final LF, for an artifact binding."""
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _object(value: object, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ComposerError(f"{where}: expected exactly {sorted(keys)}")
    return value


def _natural(value: object, where: str) -> int:
    if type(value) is not int or value < 0:
        raise ComposerError(f"{where}: expected a natural number")
    return value


def _array(value: object, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise ComposerError(f"{where}: expected an array")
    return value


def _numbers(value: object, where: str) -> tuple[int, ...]:
    result = tuple(_natural(item, where) for item in _array(value, where))
    if len(set(result)) != len(result):
        raise ComposerError(f"{where}: duplicate index")
    return result


def document(composition: CompositionInput) -> dict[str, object]:
    """Schema 1 is only the descriptor projection spec_compose actually reads."""
    return {"schema_version": 1,
            "descriptors": [asdict(item) for item in composition.descriptors],
            "roster": composition.roster,
            "type_count": composition.type_count,
            "intent_count": composition.intent_count,
            "world_count": composition.world_count,
            "inventory": sorted(composition.inventory),
            "verified_parsers": sorted(composition.verified_parsers),
            "ring_depth_ceiling": composition.ring_depth_ceiling}


def parse_document(value: object) -> CompositionInput:
    raw = _object(value, {"schema_version", "descriptors", "roster", "type_count",
                          "intent_count", "world_count", "inventory", "verified_parsers",
                          "ring_depth_ceiling"}, "composition")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ComposerError("composition: unsupported schema_version")
    descriptors: list[Descriptor] = []
    edge_fields = {field.name for field in fields(Edge)}
    for index, item in enumerate(_array(raw["descriptors"], "descriptors")):
        row = _object(item, {"package_id", "desc_manifest", "desc_edges"},
                      f"descriptor {index}")
        name = row["package_id"]
        if not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9-]*", name) is None:
            raise ComposerError(f"descriptor {index}: invalid package_id")
        edges: list[Edge] = []
        for item_edge in _array(row["desc_edges"], "desc_edges"):
            edge = _object(item_edge, edge_fields, "edge")
            edges.append(Edge(**{key: _natural(val, key) for key, val in edge.items()}))
        descriptors.append(Descriptor(name, _natural(row["desc_manifest"], "desc_manifest"),
                                      tuple(edges)))
    if len({item.package_id for item in descriptors}) != len(descriptors):
        raise ComposerError("descriptors: duplicate package_id")
    roster = _numbers(raw["roster"], "roster")
    if any(index >= len(descriptors) for index in roster):
        raise ComposerError("roster: missing descriptor")
    return CompositionInput(tuple(descriptors), roster,
                            _natural(raw["type_count"], "type_count"),
                            _natural(raw["intent_count"], "intent_count"),
                            _natural(raw["world_count"], "world_count"),
                            frozenset(_numbers(raw["inventory"], "inventory")),
                            frozenset(_numbers(raw["verified_parsers"], "verified_parsers")),
                            _natural(raw["ring_depth_ceiling"], "ring_depth_ceiling"))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ComposerError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_document(root: Path, relative: str) -> CompositionInput:
    path = root / relative
    if (Path(relative).is_absolute() or ".." in Path(relative).parts
            or not path.resolve().is_relative_to(root.resolve())):
        raise ComposerError("composition path must stay inside the repository")
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"),
                                   object_pairs_hook=_unique_object)
        return parse_document(value)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ComposerError(f"cannot read composition {relative}: {error}") from error


def edge_conjuncts(composition: CompositionInput, edge: Edge) -> tuple[bool, ...]:
    """The twelve ordered predicates of HandlerGraph.edge_conjuncts."""
    manifest = (composition.descriptors[edge.edge_owner].desc_manifest
                if edge.edge_owner < len(composition.descriptors) else 0)
    return (edge.edge_owner in composition.roster,
            edge.edge_target in composition.roster,
            edge.edge_limit > 0,
            edge.edge_intent < composition.intent_count,
            edge.edge_from < composition.type_count,
            edge.edge_to < composition.type_count,
            edge.edge_world < composition.world_count,
            edge.edge_format in composition.inventory,
            edge.edge_format in composition.verified_parsers,
            edge.edge_bounds <= manifest,
            edge.edge_ring > 0,
            edge.edge_ring <= composition.ring_depth_ceiling)


def compose(composition: CompositionInput) -> Graph:
    """Recompose from the whole requested roster, preserving declaration order.

    Like spec_compose, this filters malformed edges; it does not admit a
    generation. Removal must use a successor roster, not mutate this graph.
    """
    return Graph(composition.roster, tuple(
        edge for index in composition.roster
        for edge in composition.descriptors[index].desc_edges
        if all(edge_conjuncts(composition, edge))))


def refused_edges(composition: CompositionInput) -> tuple[RefusedEdge, ...]:
    refused: list[RefusedEdge] = []
    for index in composition.roster:
        for position, edge in enumerate(composition.descriptors[index].desc_edges):
            failed = tuple(k for k, good in enumerate(edge_conjuncts(composition, edge))
                           if not good)
            if failed:
                refused.append(RefusedEdge(index, position, edge, failed))
    return tuple(refused)


def graph_document(composition: CompositionInput) -> dict[str, object]:
    return {"schema_version": 1,
            "descriptors_sha256": hashlib.sha256(canonical_bytes(document(composition))).hexdigest(),
            "package_ids": [composition.descriptors[index].package_id
                            for index in composition.roster],
            "graph": asdict(compose(composition))}


def graph_bytes(composition: CompositionInput) -> bytes:
    return canonical_bytes(graph_document(composition))


def graph_sha256(composition: CompositionInput) -> str:
    return hashlib.sha256(graph_bytes(composition)).hexdigest()


def validate_graph(composition: CompositionInput, data: bytes,
                   package_ids: tuple[str, ...] | None = None) -> None:
    """Hold exact canonical bytes and, when supplied, the boot roster's order."""
    if data != graph_bytes(composition):
        raise ComposerError("graph differs from the declared descriptors and roster")
    expected = tuple(composition.descriptors[index].package_id for index in composition.roster)
    if package_ids is not None and package_ids != expected:
        raise ComposerError("graph package_ids differ from the boot roster")


def _body(source: str, name: str) -> str:
    match = re.search(r"\bDefinition " + re.escape(name)
                      + r"\b[^=]*:=\s*(.*?)\.\s*(?=Definition|Example|Lemma|Theorem|$)",
                      source, re.DOTALL)
    if match is None:
        raise ComposerError(f"reference: cannot read definition {name}")
    return " ".join(match[1].split())


def _nat_list(body: str) -> tuple[int, ...]:
    numbers = tuple(int(item) for item in re.findall(r"\bcons (\d+)\b", body))
    remainder = re.sub(r"\bcons \d+\b|\bnil\b|[()]|\s", "", body)
    if remainder or not numbers:
        raise ComposerError("reference: unsupported natural list")
    return numbers


def _reference_fixture(source: str) -> tuple[CompositionInput, tuple[Edge, ...]]:
    """Read witness values, never duplicate their literals in the host oracle."""
    edges: dict[str, Edge] = {}
    for match in re.finditer(r"Definition (e_\w+) : Edge := edge_of ([\d ]+)\.", source):
        values = [int(item) for item in match[2].split()]
        if len(values) != len(fields(Edge)):
            raise ComposerError("reference: edge_of arity changed")
        edges[match[1]] = Edge(*values)
    decode = edges.get("e_decode")
    if decode is None:
        raise ComposerError("reference: missing e_decode")
    spoiled_body = _body(source, "spoiled_edges")
    spoiled = tuple(replace(decode, **{"edge_" + field: int(value)})
                    for field, value in re.findall(r"set_(\w+) (\d+) e_decode", spoiled_body))
    stripped = re.sub(r"cons|set_\w+ \d+ e_decode|nil|[()]|\s", "", spoiled_body)
    if stripped or len(spoiled) != 12:
        raise ComposerError("reference: unsupported spoiled-edge family")
    descriptor_body = _body(source, "demo_descriptor")
    descriptors: list[Descriptor] = []
    # Only the graph projection is read; node-admission/template fields are not
    # part of spec_compose and remain separate obligations.
    for index in range(5):
        match = re.search(r"\| " + str(index) + r" => descriptor_of (.*?) (\d+) "
                          r"(?:BaseImage|PackageSupplied)\b", descriptor_body)
        if match is None:
            raise ComposerError(f"reference: missing descriptor {index}")
        expression = match[1]
        names = re.findall(r"\be_\w+\b|\bspoiled_edges\b", expression)
        rest = re.sub(r"\be_\w+\b|\bspoiled_edges\b|\bcons\b|\bnil\b|[()]|\s", "", expression)
        if rest:
            raise ComposerError("reference: unsupported descriptor edges")
        declared = tuple(edge for name in names
                         for edge in (spoiled if name == "spoiled_edges" else (edges[name],)))
        descriptors.append(Descriptor(f"fixture-{index}", int(match[2]), declared))
    demo = _body(source, "demo")
    def literal(name: str) -> int:
        match = re.search(r"\b" + name + r" := (\d+);", demo)
        if match is None:
            raise ComposerError(f"reference: missing demo literal {name}")
        return int(match[1])
    inventory = re.search(r"in_inventory := fun f => Nat.ltb f (\d+);", demo)
    parser = re.search(r"verified_parser := fun f => negb \(Nat.eqb f (\d+)\);", demo)
    if inventory is None or parser is None:
        raise ComposerError("reference: unsupported format declarations")
    # The reference parser predicate is total. Materialize every format the
    # finite witness actually asks it about, including off-inventory formats.
    formats = {edge.edge_format for descriptor in descriptors for edge in descriptor.desc_edges}
    composition = CompositionInput(tuple(descriptors), _nat_list(_body(source, "demo_roster")),
                                   literal("type_count"), literal("intent_count"),
                                   literal("world_count"), frozenset(range(int(inventory[1]))),
                                   frozenset(formats - {int(parser[1])}),
                                   literal("ring_depth_ceiling"))
    return composition, spoiled


def _reference_predicates(source: str) -> tuple[str, ...]:
    body = _body(source, "edge_conjuncts")
    expressions: list[str] = []
    while "fun e =>" in body:
        start = body.index("fun e =>") + len("fun e =>")
        depth = 0
        end = start
        for end in range(start, len(body)):
            if body[end] == "(":
                depth += 1
            elif body[end] == ")":
                if depth == 0:
                    break
                depth -= 1
        expressions.append(body[start:end].strip())
        body = body[end + 1:]
    if len(expressions) != 12:
        raise ComposerError("reference: edge conjunct count changed")
    return tuple(expressions)


def _reference_check(expression: str, composition: CompositionInput, edge: Edge) -> bool:
    """Evaluate the small read-only predicate grammar, separately from the port."""
    expression = re.sub(r"e\.\((edge_\w+)\)",
                        lambda match: str(getattr(edge, match[1])), expression)
    expression = re.sub(r"\(m\.\(descriptor\) (\d+)\)\.\(desc_manifest\)",
                        lambda match: str(composition.descriptors[int(match[1])].desc_manifest),
                        expression)
    expression = re.sub(r"m\.\((type_count|intent_count|world_count|ring_depth_ceiling)\)",
                        lambda match: str(getattr(composition, match[1])), expression)
    if match := re.fullmatch(r"mem_nat (\d+) r", expression):
        return int(match[1]) in composition.roster
    if match := re.fullmatch(r"Nat\.(ltb|leb) (\d+) (\d+)", expression):
        return int(match[2]) < int(match[3]) if match[1] == "ltb" else int(match[2]) <= int(match[3])
    if match := re.fullmatch(r"m\.\((in_inventory|verified_parser)\) (\d+)", expression):
        values = composition.inventory if match[1] == "in_inventory" else composition.verified_parsers
        return int(match[2]) in values
    raise ComposerError(f"reference: unsupported predicate {expression}")


def compare_reference(root: Path) -> dict[str, object]:
    """Source comparison, not extraction, proof execution or a kernel verdict."""
    raw = (root / REFERENCE).read_bytes()
    source = strip_comments(raw.decode("utf-8"))
    composition, spoiled = _reference_fixture(source)
    predicates = _reference_predicates(source)
    declared = tuple(edge for index in composition.roster
                     for edge in composition.descriptors[index].desc_edges)
    expected = tuple(tuple(_reference_check(p, composition, edge) for p in predicates)
                     for edge in declared)
    actual = tuple(edge_conjuncts(composition, edge) for edge in declared)
    failures: list[str] = []
    if actual != expected:
        failures.append("predicate decisions disagree with the source reference")
    reference_graph = Graph(composition.roster, tuple(edge for edge, checks in zip(declared, expected, strict=True)
                                                    if all(checks)))
    if compose(composition) != reference_graph:
        failures.append("composed graph disagrees with the reference filter")
    for index, edge in enumerate(spoiled):
        checks = edge_conjuncts(composition, edge)
        if tuple(k for k, good in enumerate(checks) if not good) != (index,):
            failures.append(f"spoiled edge {index} does not break exactly conjunct {index}")
        weakened = tuple(item for item, row in zip(declared, expected, strict=True)
                         if all(value for k, value in enumerate(row) if k != index))
        if edge not in weakened or len(weakened) != len(reference_graph.graph_edges) + 1:
            failures.append(f"dropped conjunct {index} lacks its additional edge")
    return {"scope": "source-reference-comparison", "reference": REFERENCE,
            "reference_sha256": hashlib.sha256(raw).hexdigest(),
            "declared_edges": len(declared), "accepted_edges": len(reference_graph.graph_edges),
            "spoiled_edges": len(spoiled), "dropped_conjuncts": len(predicates),
            "passed": not failures, "failures": failures,
            "graph_sha256": graph_sha256(composition)}


def reference_fixture(root: Path) -> CompositionInput:
    """The source's synthetic demo descriptor projection, for reproducible checks."""
    return _reference_fixture(strip_comments((root / REFERENCE).read_text(encoding="utf-8")))[0]


def _gallina_list(items: tuple[str, ...]) -> str:
    result = "nil"
    for item in reversed(items):
        result = f"cons ({item}) ({result})"
    return result


def _gallina_graph(graph: Graph) -> str:
    nodes = _gallina_list(tuple(str(index) for index in graph.graph_nodes))
    edges = _gallina_list(tuple("edge_of " + " ".join(str(value) for value in asdict(edge).values())
                               for edge in graph.graph_edges))
    return f"{{| graph_nodes := {nodes}; graph_edges := {edges} |}}"


def reference_program(root: Path) -> str:
    """Turn executable results into equalities Rocq decides against the source."""
    composition = reference_fixture(root)
    lines = ["(* Generated finite comparison, not an implementation proof. *)",
             "Require Import HandlerGraph."]
    names: list[str] = []
    def example(name: str, proposition: str) -> None:
        names.append(name)
        lines.append(f"Example {name} : {proposition} := eq_refl.")
    example("composer_graph_agrees", "demo_graph = " + _gallina_graph(compose(composition)))
    declared = tuple(edge for index in composition.roster
                     for edge in composition.descriptors[index].desc_edges)
    for index in range(12):
        weakened = Graph(composition.roster, tuple(edge for edge in declared
                          if all(good for k, good in enumerate(edge_conjuncts(composition, edge))
                                 if k != index)))
        example(f"composer_drop_{index}",
                f"compose_without {index} demo demo_ambient demo_roster = " + _gallina_graph(weakened))
    for index, refused in enumerate(refused_edges(composition)):
        checks = _gallina_list(tuple("true" if value else "false"
                                    for value in edge_conjuncts(composition, refused.edge)))
        example(f"composer_spoiled_{index}",
                f"map_over (fun p => p (spoiled_at {index})) (edge_conjuncts demo demo_roster) = {checks}")
    for length in range(len(composition.roster) + 1):
        current = replace(composition, roster=composition.roster[:length])
        roster = _gallina_list(tuple(str(index) for index in current.roster))
        example(f"composer_roster_{length}",
                f"spec_compose demo probing_ambient ({roster}) = " + _gallina_graph(compose(current)))
    lines.extend(f"Print Assumptions {name}." for name in names)
    return "\n".join(lines) + "\n"


def prove_reference(root: Path) -> dict[str, object]:
    """Focused finite reference comparison in this checkout's native guest lane."""
    if sys.platform == "win32":
        raise ComposerError("reference compilation needs the guest lane")
    work = (env.lane_root(env.lane_of(root)) / "composer-reference").resolve()
    if (work.is_relative_to(root.resolve()) or work.is_relative_to(Path("/tmp"))  # noqa: S108
            or work.is_relative_to(Path("/var/tmp"))  # noqa: S108
            or env.filesystem(work) in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS):
        raise ComposerError(f"reference outputs need persistent native lane storage: {work}")
    work.mkdir(parents=True, exist_ok=True)
    result_path = work / "result.json"
    result_path.unlink(missing_ok=True)
    source = work / "HandlerGraph.v"
    shutil.copyfile(root / REFERENCE, source)
    producer = root / "tools/vos/composer.py"
    producer_digest = hashlib.sha256(producer.read_bytes()).hexdigest()
    program = reference_program(root)
    comparison = work / "ComposerComparison.v"
    comparison.write_text(program, encoding="utf-8", newline="")
    logs = env.log_root() / env.lane_of(root) / "composer-reference"
    logs.mkdir(parents=True, exist_ok=True)
    commands = ([*env.rocq_command(), "-q", "-Q", str(work), "", str(source)],
                [*env.rocq_command(), "-q", "-Q", str(work), "", str(comparison)],
                [*env.rocqchk_command(), "-silent", "-Q", str(work), "", "ComposerComparison"])
    log_paths: list[str] = []
    for index, command in enumerate(commands):
        done = subprocess.run(command, cwd=work, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", check=False, timeout=180)
        path = logs / f"phase-{index}.log"
        path.write_text(done.stdout + done.stderr, encoding="utf-8", newline="")
        log_paths.append(str(path))
        if done.returncode:
            raise ComposerError(f"reference phase {index} exited {done.returncode}: {path}")
    if (source.read_bytes() != (root / REFERENCE).read_bytes()
            or producer_digest != hashlib.sha256(producer.read_bytes()).hexdigest()
            or program != reference_program(root)):
        raise ComposerError("reference comparison inputs changed during the run")
    result: dict[str, object] = {
        "scope": "finite-compiled-reference-comparison", "passed": True,
        "reference_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "producer_sha256": producer_digest,
        "program_sha256": hashlib.sha256(program.encode("utf-8")).hexdigest(),
        "program": str(comparison), "logs": log_paths}
    result_path.write_bytes(canonical_bytes(result))
    return result
