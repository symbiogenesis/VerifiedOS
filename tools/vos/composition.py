# SPDX-License-Identifier: Apache-2.0
"""Checked production composition choices and incomplete, bound projections.

The roster owns executable status. These projections bind declarations and bytes;
neither a derivation reference nor a build record supplies admission evidence.
"""

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, validators

from vos import boot, composer
from vos.jsonutil import unique_object

SCHEMA = "tools/composer/composition.schema.json"
EXAMPLE = "tools/composer/m8a-composition.json"
GENERATED = "tools/composer/generated"
PRODUCERS = ("tools/vos/composition.py", "tools/vos/composer.py", "tools/vos/boot.py", SCHEMA)
OUTPUTS = ("manifest.json", "manifest.c", "graph-input.json", "recipe-members.json",
           "admission-request.json")


class CompositionError(ValueError):
    """A composition, projection or build binding fails its boundary."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if (Path(relative).is_absolute() or "\\" in relative or ".." in Path(relative).parts
            or not path.is_relative_to(root.resolve())):
        raise CompositionError(f"path must stay relative to the checkout: {relative}")
    return path


def reference(root: Path, relative: str) -> dict[str, str]:
    """Bind existing source bytes without implying a producer or proof verdict."""
    return {"path": relative, "sha256": digest(_path(root, relative).read_bytes())}


def _json(path: Path) -> object:
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as error:
        raise CompositionError(f"cannot read {path}: {error}") from error


def _is_integer(checker: object, value: object) -> bool:
    return type(value) is int


def _bound(root: Path, ref: object) -> None:
    if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
            or not isinstance(ref["path"], str) or not isinstance(ref["sha256"], str)):
        raise CompositionError("malformed source binding: expected string path and sha256 fields")
    if reference(root, ref["path"]) != ref:
        raise CompositionError(f"stale source binding: {ref['path']}")


def _placements(root: Path, raw: dict[str, Any], roster: boot.Roster) -> None:
    memory = boot.regions(_path(root, raw["configuration"]["path"]))
    extents: list[tuple[str, int, int]] = []
    for member in raw["members"]:
        placement = member["placement"]
        if placement is None:
            continue
        if roster.by_id()[member["id"]].kind != "image":
            raise CompositionError(f"{member['id']}: only image members have main-die placement")
        for section in ("text", "data"):
            start = int(placement[f"{section}_base"], 16)
            size = placement[f"{section}_bytes"]
            if start % (4 if section == "text" else 8):
                raise CompositionError(f"{member['id']} {section}: misaligned placement")
            if not any(region.holds(start, size)
                       and (region.executable if section == "text" else region.writable)
                       for region in memory):
                raise CompositionError(f"{member['id']} {section}: misplaced extent")
            extents.append((f"{member['id']} {section}", start, size))
    for field, width in (("tohost", 8), ("graph_placement", None)):
        value = raw[field]
        if value is None:
            continue
        start = int(value if width is not None else value["base"], 16)
        size = width if width is not None else value["bytes"]
        if ((width is not None and start % 8)
                or not any(region.holds(start, size) and (width is None or region.writable)
                           for region in memory)):
            raise CompositionError(f"{field}: misplaced extent")
        extents.append((field, start, size))
    for index, (name, start, size) in enumerate(extents):
        for other, base, length in extents[:index]:
            if start < base + length and base < start + size:
                raise CompositionError(f"{name} overlaps {other}")


def _graph(root: Path, raw: dict[str, Any]) -> composer.CompositionInput | None:
    descriptors = []
    graph_context = raw["graph"] if raw["graph"] is not None else {
        "type_count": 0, "intent_count": 0, "world_count": 0,
        "inventory": [], "verified_parsers": [], "ring_depth_ceiling": 0}
    for index, member in enumerate(raw["members"]):
        if member["descriptor"] is None:
            continue
        descriptor = _json(_path(root, member["descriptor"]["path"]))
        if not isinstance(descriptor, dict) or descriptor.get("package_id") != member["package_id"]:
            raise CompositionError(f"{member['id']}: descriptor package identity differs")
        try:
            # Even a partially resolved input must reject a malformed present
            # descriptor. Keep its original owner and target roster indices.
            parsed = composer.parse_document({"schema_version": 1, "descriptors": [descriptor], "roster": [0],
                                              **graph_context})
        except composer.ComposerError as error:
            raise CompositionError(f"{member['id']}: malformed descriptor: {error}") from error
        if any(edge.edge_owner != index for edge in parsed.descriptors[0].desc_edges):
            raise CompositionError(f"{member['id']}: handler edge claims another owner")
        if raw["graph"] is not None:
            context = replace(parsed, roster=tuple(range(len(raw["members"]))))
            known = parsed.descriptors[0]
            if any(not all(composer.edge_conjuncts_for_manifest(context, edge, known.desc_manifest))
                   for edge in known.desc_edges):
                raise CompositionError(f"{member['id']}: typed handler graph: a declared edge is refused")
        descriptors.append(descriptor)
    if raw["graph"] is None or len(descriptors) != len(raw["members"]):
        return None
    try:
        result = composer.parse_document({"schema_version": 1, "descriptors": descriptors,
                                          "roster": list(range(len(descriptors))), **raw["graph"]})
    except composer.ComposerError as error:
        raise CompositionError(f"typed handler graph: {error}") from error
    # The reference filter can drop malformed edges. Production declarations must
    # retain every declared relation, rather than silently using that fixture rule.
    if composer.refused_edges(result):
        raise CompositionError("typed handler graph: a declared edge is refused")
    placement = raw["graph_placement"]
    if placement is not None and len(composer.graph_bytes(result)) > placement["bytes"]:
        raise CompositionError("typed handler graph exceeds its reserved extent")
    return result


def load(root: Path, source: str = EXAMPLE) -> dict[str, Any]:
    """Read the strict schema and check its owners, separate relations and bindings."""
    schema = _json(_path(root, SCHEMA))
    if not isinstance(schema, dict):
        raise CompositionError("composition schema must be an object")
    raw = _json(_path(root, source))
    # JSON Schema accepts integral floats as integers. The typed graph and C
    # manifest require actual integer values, without coercing declared bytes.
    checker = Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_integer)
    validator = validators.extend(Draft202012Validator, type_checker=checker)
    errors = list(validator(schema).iter_errors(raw))
    if errors:
        raise CompositionError(f"composition schema: {errors[0].json_path}: {errors[0].message}")
    raw = cast("dict[str, Any]", raw)
    # The schema version is a const, so the integer type checker does not see it.
    if type(raw["schema_version"]) is not int:
        raise CompositionError("composition schema: $.schema_version: expected an integer")
    roster = boot.load_roster(root, boot.CONTRACT)
    names = [m["id"] for m in raw["members"]]
    if names != [m.id for m in roster.members]:
        raise CompositionError("members must match the real roster once each, in declaration order")
    producers = {p["id"]: p for p in raw["producers"]}
    if len(producers) != len(raw["producers"]):
        raise CompositionError("duplicate producer identity")
    for producer in raw["producers"]:
        for ref in producer["sources"]:
            _bound(root, ref)
    _bound(root, raw["configuration"])
    slots: set[str] = {"main-die-image"}
    for member in raw["members"]:
        declared = roster.by_id()[member["id"]]
        if member["package_id"] != member["id"]:
            raise CompositionError(f"{member['id']}: package identity must equal the roster member")
        producer = member["producer"]
        if producer is not None and producer not in producers:
            raise CompositionError(f"{member['id']}: unknown producer identity")
        for ref in member["sources"]:
            _bound(root, ref)
        for ref in (member["descriptor"], member["derivation"]["source"]):
            if ref is not None:
                _bound(root, ref)
        for slot in (member["artifact_slot"], member["derivation"]["slot"]):
            if slot in slots:
                raise CompositionError(f"duplicate symbolic slot: {slot}")
            slots.add(slot)
        if ((declared.kind != "image" and member["entry"] is not None)
                or (declared.kind == "image" and member["entry"] not in (None, "_start"))):
            raise CompositionError(f"{member['id']}: entry differs from the roster contract")
        if declared.kind == "offline" and member["admission_tier"] is not None:
            raise CompositionError("offline checkers cannot certify themselves")
        if declared.kind != "image" and member["imports"]:
            raise CompositionError(f"{member['id']}: only image members have image imports")
        for symbol, target in member["imports"].items():
            if (re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", symbol) is None or symbol == "tohost"
                    or target == member["id"] or target not in roster.by_id()
                    or roster.by_id()[target].kind != "image"):
                raise CompositionError(f"{member['id']}: invalid image import {symbol}")
    image_order = [m.id for m in roster.image_members()]
    if raw["startup"]["order"] != image_order[image_order.index("supervisor") + 1:]:
        raise CompositionError("supervisor startup order contradicts the roster ranks")
    order = raw["startup"]["order"]
    for relation in (raw["startup"]["dependencies"], raw["supervisor"]["authority"]):
        pairs = [(edge["member"], edge["requires"]) for edge in relation]
        if len(set(pairs)) != len(pairs):
            raise CompositionError("duplicate startup or authority relation")
        if any(a not in order or b not in order or order.index(b) >= order.index(a)
               for a, b in pairs):
            raise CompositionError("relation conflicts with supervisor startup order")
    required = {"member": "storage", "requires": "crypto-core"}
    if required not in raw["startup"]["dependencies"] or required not in raw["supervisor"]["authority"]:
        raise CompositionError("storage must depend on and hold an entry to crypto-core")
    policy = raw["supervisor"]["policy"]
    if (not order or len(order) > 16 or policy["restart_members"] >= 1 << len(order)
            or any(clear > threshold for clear, threshold in
                   zip(policy["clear_threshold"], policy["threshold"], strict=True))
            or any(delay > policy["ceiling"] for delay in policy["backoff"])):
        raise CompositionError("supervisor policy violates the immutable C manifest bounds")
    _placements(root, raw, roster)
    _graph(root, raw)
    return raw


def _binding(root: Path, source: str, raw: dict[str, Any]) -> dict[str, object]:
    return {"input": reference(root, source), "roster": reference(root, boot.CONTRACT),
            "projection_producers": [reference(root, path) for path in PRODUCERS],
            "member_producers": raw["producers"], "configuration": raw["configuration"]}


def _manifest(raw: dict[str, Any]) -> dict[str, object]:
    order = raw["startup"]["order"]
    return {"units": order, "order": list(range(len(order))),
            "edges": [sum(1 << order.index(edge["requires"]) for edge in raw["supervisor"]["authority"]
                          if edge["member"] == member) for member in order],
            "policy": raw["supervisor"]["policy"]}


def _manifest_c(binding: dict[str, object], manifest: dict[str, Any]) -> bytes:
    policy = manifest["policy"]
    def numbers(items: list[int]) -> str:
        return "{" + ", ".join(str(item) for item in items) + "}"
    arrays = ",\n    ".join(numbers(items) for items in
                            (manifest["order"], manifest["edges"], policy["threshold"],
                             policy["clear_threshold"], policy["respond"]))
    trailer = (f"{policy['min_dwell']}, {policy['max_interventions']}, {policy['escalation']}, "
               f"{len(policy['backoff'])}, {numbers(policy['backoff'])}, {policy['ceiling']}, "
               f"{policy['boot_bound']}, {policy['restart_members']}")
    return ("// SPDX-License-Identifier: Apache-2.0\n"
            "// Generated by composer project; admission and target qualification remain open.\n"
            f"// Binding SHA-256: {digest(composer.canonical_bytes(binding))}\n"
            '#include "vos_supervisor.h"\n\n'
            "const struct vos_supervisor_manifest vos_m8a_supervisor_manifest = {\n"
            f"    {len(manifest['units'])}, {arrays},\n    {trailer}\n}};\n").encode()


def projections(root: Path, source: str = EXAMPLE) -> dict[str, bytes]:
    """Emit the immutable manifest and skeletons without invented target products."""
    raw = load(root, source)
    roster = boot.load_roster(root, boot.CONTRACT)
    binding = _binding(root, source, raw)
    def envelope(kind: str, payload: object) -> bytes:
        return composer.canonical_bytes({"schema_version": 1, "kind": kind, "binding": binding,
                                         "production_admission": False, "payload": payload})
    manifest = _manifest(raw)
    graph = _graph(root, raw)
    image = [m for m in raw["members"] if roster.by_id()[m["id"]].kind == "image"]
    runtime = [m for m in raw["members"] if roster.by_id()[m["id"]].kind != "offline"]
    return {"manifest.json": envelope("supervisor-manifest", manifest),
            "manifest.c": _manifest_c(binding, manifest),
            "graph-input.json": envelope("typed-handler-graph-input", {
                "document": None if graph is None else composer.document(graph),
                "descriptor_slots": [{"member": m["id"], "package_id": m["package_id"],
                                      "source": m["descriptor"]} for m in raw["members"]]}),
            "recipe-members.json": envelope("image-recipe-members", {
                "name": raw["name"], "roster": boot.CONTRACT,
                "configuration": raw["configuration"], "tohost": raw["tohost"],
                "graph_placement": raw["graph_placement"], "inst_limit": raw["inst_limit"],
                "members": [{**m, "status": roster.by_id()[m["id"]].status} for m in image]}),
            "admission-request.json": envelope("production-admission-request-skeleton", {
                "image_slot": "main-die-image", "image_sha256": None, "graph_sha256": None,
                "build_record": None, "members": [{"member": m["id"], "package_id": m["package_id"],
                    "artifact_slot": m["artifact_slot"], "tier": m["admission_tier"],
                    "derivation": m["derivation"], "certificate": None} for m in runtime]})}


def emit(root: Path, source: str, output: str) -> dict[str, str]:
    """Write only the documented production projections or an ignored out/ directory."""
    destination = _path(root, output)
    if output != GENERATED and not destination.is_relative_to((root / "out").resolve()):
        raise CompositionError("projection output belongs under out/ or tools/composer/generated")
    outputs = projections(root, source)
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        (destination / name).write_bytes(data)
    return {name: digest(data) for name, data in outputs.items()}


def check(root: Path, source: str = EXAMPLE, output: str = GENERATED) -> None:
    """Regenerate rather than trusting a projection's self-reported binding."""
    destination = _path(root, output)
    for name, data in projections(root, source).items():
        if (destination / name).read_bytes() != data:
            raise CompositionError(f"stale generated projection: {name}")


def build_record(root: Path, source: str, outputs: dict[str, bytes],
                 artifacts: dict[str, dict[str, str]], image: dict[str, str], graph: bytes) -> dict[str, object]:
    """Resolve produced artifact slots separately; this is byte binding, not admission."""
    expected = projections(root, source)
    if outputs != expected:
        raise CompositionError("build record: stale projection bindings")
    raw = load(root, source)
    composed = _graph(root, raw)
    if composed is None or composer.graph_bytes(composed) != graph:
        raise CompositionError("build record: stale or missing graph binding")
    roster = boot.load_roster(root, boot.CONTRACT)
    slots = {m["artifact_slot"] for m in raw["members"] if roster.by_id()[m["id"]].kind != "offline"}
    if not isinstance(artifacts, dict):
        raise CompositionError("build record: malformed artifact map: expected an object")
    if set(artifacts) != slots:
        raise CompositionError("build record: artifact slots differ from the runtime roster")
    for ref in [*artifacts.values(), image]:
        _bound(root, ref)
    if len({_path(root, ref["path"]) for ref in artifacts.values()}) != len(slots):
        raise CompositionError("build record: runtime members share a substituted artifact")
    return {"schema_version": 1, "kind": "production-composition-build-bindings",
            "binding": _binding(root, source, raw), "production_admission": False,
            "projections": {name: digest(data) for name, data in outputs.items()},
            "artifacts": artifacts, "image": image, "graph_sha256": digest(graph)}


def validate_build_record(root: Path, source: str, record: dict[str, Any],
                          outputs: dict[str, bytes], graph: bytes, image: dict[str, str]) -> None:
    if record.get("image") != image:
        raise CompositionError("build record: stale image binding")
    try:
        expected = build_record(root, source, outputs, record["artifacts"], image, graph)
    except (KeyError, TypeError) as error:
        raise CompositionError("build record: malformed record") from error
    try:
        actual = composer.canonical_bytes(record)
    except (TypeError, ValueError) as error:
        raise CompositionError("build record: malformed record") from error
    # Python equality aliases booleans, integers and floats. The generated JSON
    # record must retain the exact types at its version and admission boundaries.
    if actual != composer.canonical_bytes(expected):
        raise CompositionError("build record: substituted binding or derivation reference")


def require_production(root: Path, source: str = EXAMPLE) -> None:
    raw = load(root, source)
    blocked = boot.load_roster(root, boot.CONTRACT).blocking()
    if blocked:
        raise CompositionError("production promotion refused: " + "; ".join(
            f"{m.id} is {m.status} (owner {m.owner})" for m in blocked))
    # This checkpoint has no actual derivation checker, even when all slots are filled.
    raise CompositionError(f"{raw['name']}: independent production admission remains open")
