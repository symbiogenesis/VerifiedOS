# SPDX-License-Identifier: Apache-2.0
"""Join production admission inputs without promoting references into proof evidence.

There is no production derivation checker yet. A successfully bound record is
therefore a replayable refusal, identifying each member's remaining obligations.
"""

import json
from pathlib import Path
from typing import Any, TypedDict, cast

from vos import boot, composer, composition
from vos.jsonutil import unique_object

CHECKERS = ("tools/vos/admission_production.py", "tools/vos/cli/admission.py")
SCOPE = "production-admission-refusal"


class ProductionAdmissionError(ValueError):
    """Production inputs cannot be joined or a saved refusal is stale."""


class SourceRef(TypedDict):
    path: str
    sha256: str


def _path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if (Path(relative).is_absolute() or "\\" in relative or ".." in Path(relative).parts
            or not path.is_relative_to(root.resolve())):
        raise ProductionAdmissionError(f"path must stay relative to the checkout: {relative}")
    return path


def _references(value: object) -> list[SourceRef]:
    if isinstance(value, dict):
        if (set(value) == {"path", "sha256"} and isinstance(value["path"], str)
                and isinstance(value["sha256"], str)):
            return [SourceRef(path=value["path"], sha256=value["sha256"])]
        return [ref for child in value.values() for ref in _references(child)]
    if isinstance(value, list):
        return [ref for child in value for ref in _references(child)]
    return []


def _json(data: bytes, where: str) -> object:
    try:
        return json.loads(data, object_pairs_hook=unique_object)
    except (UnicodeDecodeError, ValueError) as error:
        raise ProductionAdmissionError(f"{where}: unreadable JSON: {error}") from error


def make_record(root: Path, source: str, projections: str, build_record: str,
                image: str, graph: str) -> dict[str, object]:
    """Bind the exact skeleton, replay its build, and refuse unchecked derivations.

    Runtime membership, tiers and derivation identities come exclusively from the
    regenerated request. Caller-supplied certificates or success flags cannot
    replace its unresolved evidence. The build checker owns graph/image validity.
    """
    snapshots: dict[str, bytes] = {}

    def read(relative: str, expected: str | None = None) -> bytes:
        path = _path(root, relative)
        normalized = path.relative_to(root.resolve()).as_posix()
        data = path.read_bytes()
        if ((expected is not None and composition.digest(data) != expected)
                or (normalized in snapshots and snapshots[normalized] != data)):
            raise ProductionAdmissionError(f"stale admission input: {relative}")
        snapshots[normalized] = data
        return data

    source_data = read(source)
    for checker in CHECKERS:
        read(checker)
    outputs = {name: read(f"{projections}/{name}") for name in composition.OUTPUTS}
    build_data, image_data, graph_data = read(build_record), read(image), read(graph)
    image_ref = {"path": image, "sha256": composition.digest(image_data)}
    built = _json(build_data, build_record)
    try:
        composition.validate_build_record(root, source, built, outputs, graph_data, image_ref)
    except (composition.CompositionError, boot.RecipeError) as error:
        raise ProductionAdmissionError(f"production admission build join: {error}") from error
    # The validator regenerates every projection before returning. Only those
    # checked bytes can supply member declarations and the common source binding.
    request = _json(outputs["admission-request.json"], "admission request skeleton")
    built = cast("dict[str, Any]", built)
    request = cast("dict[str, Any]", request)
    for ref in [*_references(built), *_references(_json(source_data, source))]:
        read(ref["path"], ref["sha256"])
    roster_ref = request["binding"]["roster"]
    roster_data = read(roster_ref["path"], roster_ref["sha256"])
    roster = boot.load_roster(root, roster_ref["path"], snapshot=roster_data)
    declared = roster.by_id()
    members: list[dict[str, object]] = []
    for member in request["payload"]["members"]:
        owner = declared[member["member"]]
        blockers = []
        if member["tier"] is None:
            blockers.append({"rule": "TierUnassigned", "owner": "M7.1c",
                             "detail": "the composition has no admission tier"})
        if member["derivation"]["source"] is None:
            blockers.append({"rule": "DerivationAbsent", "owner": owner.owner,
                             "detail": "the member has no declared checked derivation source"})
        blockers.append({"rule": "DerivationCheckerUnavailable", "owner": "M7.1c",
                         "detail": "no production checker validates proof terms, tier evidence or artifact binding"})
        if owner.status != "executable":
            blockers.append({"rule": "RosterMemberUnaccepted", "owner": owner.owner,
                             "detail": f"the roster declares {owner.status}"})
        members.append({"member": owner.id, "package_id": member["package_id"],
                        "artifact_slot": member["artifact_slot"],
                        "artifact": built["artifacts"][member["artifact_slot"]],
                        "tier": member["tier"], "derivation": member["derivation"],
                        "status": owner.status, "decision": "refused", "blockers": blockers})
    for relative, data in snapshots.items():
        if _path(root, relative).read_bytes() != data:
            raise ProductionAdmissionError(f"stale admission input: {relative}")
    return {"schema_version": 1, "scope": SCOPE, "production_admission": False,
            "decision": "refused", "generation_accepted": False,
            "composition": SourceRef(path=source, sha256=composition.digest(source_data)),
            "request": SourceRef(path=f"{projections}/admission-request.json",
                                 sha256=composition.digest(outputs["admission-request.json"])),
            "projections": projections,
            "build_record": SourceRef(path=build_record, sha256=composition.digest(build_data)),
            "image": image_ref, "graph": SourceRef(path=graph, sha256=composition.digest(graph_data)),
            "binding": request["binding"], "members": members,
            "inputs": [SourceRef(path=path, sha256=composition.digest(data))
                       for path, data in sorted(snapshots.items())],
            "open": ["real members' checked derivations and tier evidence",
                     "production derivation checker and admission refinement",
                     "accepted executable roster"]}


def validate_record(root: Path, record: object) -> None:
    """Recompute a saved refusal; validity never means generation acceptance."""
    if not isinstance(record, dict):
        raise ProductionAdmissionError("production admission record is not an object")
    try:
        expected = make_record(root, record["composition"]["path"], record["projections"],
                               record["build_record"]["path"], record["image"]["path"],
                               record["graph"]["path"])
        equal = composer.canonical_bytes(record) == composer.canonical_bytes(expected)
    except (KeyError, TypeError, ValueError) as error:
        raise ProductionAdmissionError(f"production admission record cannot be replayed: {error}") from error
    if not equal:
        raise ProductionAdmissionError("production admission record differs from current bound refusal")


def publish_record(root: Path, record: dict[str, object], destination: str) -> None:
    """Publish only after protecting and rechecking all consumed input bytes."""
    output = _path(root, destination)
    inputs = _references(record["inputs"])
    for ref in inputs:
        path = _path(root, ref["path"])
        if output == path or (output.exists() and output.samefile(path)):
            raise ProductionAdmissionError("production admission output would overwrite a consumed input")
        if composition.digest(path.read_bytes()) != ref["sha256"]:
            raise ProductionAdmissionError(f"stale admission input: {ref['path']}")
    validate_record(root, record)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(composer.canonical_bytes(record))
