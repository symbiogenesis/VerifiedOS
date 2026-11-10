# SPDX-License-Identifier: Apache-2.0
"""Join production admission inputs without promoting references into proof evidence.

There is no production derivation checker yet. A successfully bound record is
therefore a replayable refusal, identifying each member's remaining obligations.
"""

import json
from pathlib import Path
from typing import Any, Final, TypedDict, cast

from vos import boot, composer, composition, source_bindings
from vos.atomic import atomic_path
from vos.jsonutil import unique_object
from vos.register import REGISTER, REQ_TOKEN_RE

CHECKERS = source_bindings.sources("admission-production")
SCOPE = "production-admission-refusal"
POPULATION: Final = "tools/admission/production-population.json"
ROUTES: Final = frozenset({"bootstrap-release", "tcb-release", "checker-admitted", "unresolved"})


class ProductionAdmissionError(ValueError):
    """Production inputs cannot be joined or a saved refusal is stale."""


class SourceRef(TypedDict):
    path: str
    sha256: str


class ProofRoute(TypedDict):
    member: str
    route: str
    requirements: list[str]


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


def _proof_routes(data: bytes, members: list[str]) -> dict[str, ProofRoute]:
    """Read the fixed reviewed policy, never infer a route from fixture tiers.

    [The proof-route predicate](../../docs/implementation/contracts/production-admission.md#production-proof-route-record)
    leaves classification judgment with the authored policy's review.
    """
    policy = _json(data, "production proof-route policy")
    if (not isinstance(policy, dict) or set(policy) != {"schema_version", "members"}
            or type(policy["schema_version"]) is not int or policy["schema_version"] != 1
            or not isinstance(policy["members"], list)):
        raise ProductionAdmissionError("production proof-route policy has an invalid schema")
    routes: dict[str, ProofRoute] = {}
    for entry in policy["members"]:
        if (not isinstance(entry, dict) or set(entry) != {"member", "route", "requirements"}
                or not isinstance(entry["member"], str) or not entry["member"]
                or not isinstance(entry["route"], str) or entry["route"] not in ROUTES
                or not isinstance(entry["requirements"], list) or not entry["requirements"]
                or any(not isinstance(item, str) or REQ_TOKEN_RE.fullmatch(item) is None
                       for item in entry["requirements"])
                or len(entry["requirements"]) != len(set(entry["requirements"]))):
            raise ProductionAdmissionError("production proof-route policy has an invalid member declaration")
        declaration = cast("ProofRoute", entry)
        if declaration["member"] in routes:
            raise ProductionAdmissionError("production proof-route policy repeats a member")
        routes[declaration["member"]] = declaration
    if set(routes) != set(members) or len(members) != len(set(members)):
        raise ProductionAdmissionError("production proof-route policy differs from runtime request membership")
    return routes


def make_record(root: Path, source: str, projections: str, build_record: str,
                image: str, graph: str) -> dict[str, object]:
    """Bind the exact skeleton, replay its build, and refuse unchecked derivations.

    Runtime membership, tier declarations and derivation identities come from the
    regenerated request. The fixed reviewed policy supplies proof routes. Neither
    those declarations nor caller success flags replace checked evidence.
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
    checkers = source_bindings.sources("admission-production", root=root)
    for checker in checkers:
        read(checker)
    population_data, authority_data = read(POPULATION), read(REGISTER)
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
    routes = _proof_routes(population_data, [member["member"] for member in request["payload"]["members"]])
    members: list[dict[str, object]] = []
    for member in request["payload"]["members"]:
        owner = declared[member["member"]]
        route = routes[owner.id]
        blockers: list[dict[str, object]] = []
        if route["route"] == "checker-admitted":
            if member["tier"] is None:
                blockers.append({"rule": "TierUnassigned", "owner": "M7.1c",
                                 "detail": "the composition has no admission tier"})
            if member["derivation"]["source"] is None:
                blockers.append({"rule": "DerivationAbsent", "owner": owner.owner,
                                 "detail": "the member has no declared checked derivation source"})
            blockers.append({"rule": "DerivationCheckerUnavailable", "owner": "M7.1c",
                             "detail": "no production checker validates proof terms, tier evidence or artifact binding"})
        elif route["route"] in {"bootstrap-release", "tcb-release"}:
            blockers.append({"rule": "ReleaseEvidenceUnavailable", "owner": owner.owner,
                             "detail": "release-time source/binary correspondence, functional-refinement and measured-boot evidence is unchecked"})
        else:
            blockers.append({"rule": "ProofRouteUnresolved", "owner": "M7.1c/M7.1d",
                             "detail": "the installed member's release/admission proof boundary is unresolved"})
            if owner.id == "storage":
                blockers.extend([
                    {"rule": "StorageFilesystemBoundaryUnavailable", "owner": "M5.3d/M7.1a/M7.1d",
                     "requirements": ["R-06-006"],
                     "detail": "both volumes need the contained filesystem's complete installed population, entries and capability wiring"},
                    {"rule": "StorageIntegrityReaderBoundaryUnavailable", "owner": "M5.3d/M7.1a/M7.1d",
                     "requirements": ["R-06-005"],
                     "detail": "the protected integrity reader needs its own installed population and independent signed, boot-attested root"},
                    {"rule": "StorageTransactorBoundaryUnavailable", "owner": "M5.4/M7.1a/M7.1d",
                     "requirements": ["R-06-005"],
                     "detail": "the A/B transactor needs its own installed population, protected roots, atomic root flip and anti-rollback enforcement"},
                ])
        if owner.status != "executable":
            blockers.append({"rule": "RosterMemberUnaccepted", "owner": owner.owner,
                             "detail": f"the roster declares {owner.status}"})
        members.append({"member": owner.id, "package_id": member["package_id"],
                        "artifact_slot": member["artifact_slot"],
                        "artifact": built["artifacts"][member["artifact_slot"]],
                        "tier": member["tier"], "derivation": member["derivation"],
                        "proof_route": route["route"], "route_basis": route["requirements"],
                        "status": owner.status, "decision": "refused", "blockers": blockers})
    for relative, data in snapshots.items():
        if _path(root, relative).read_bytes() != data:
            raise ProductionAdmissionError(f"stale admission input: {relative}")
    if source_bindings.sources("admission-production", root=root) != checkers:
        raise ProductionAdmissionError("stale admission input: checker dependency membership changed")
    return {"schema_version": 2, "scope": SCOPE, "production_admission": False,
            "decision": "refused", "generation_accepted": False,
            "composition": SourceRef(path=source, sha256=composition.digest(source_data)),
            "request": SourceRef(path=f"{projections}/admission-request.json",
                                 sha256=composition.digest(outputs["admission-request.json"])),
            "projections": projections,
            "build_record": SourceRef(path=build_record, sha256=composition.digest(build_data)),
            "image": image_ref, "graph": SourceRef(path=graph, sha256=composition.digest(graph_data)),
            "binding": request["binding"], "members": members,
            "proof_routing": {"policy": SourceRef(path=POPULATION, sha256=composition.digest(population_data)),
                              "authority": SourceRef(path=REGISTER, sha256=composition.digest(authority_data))},
            "inputs": [SourceRef(path=path, sha256=composition.digest(data))
                       for path, data in sorted(snapshots.items())],
            "open": ["bootstrap and TCB release-proof evidence",
                     "unresolved installed-member release/admission boundaries",
                     "checker-admitted members' checked derivations and tier evidence",
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


def _publication_inputs(root: Path, record: dict[str, object], output: Path) -> None:
    """Protect the destination and the original bound input snapshots."""
    inputs = _references(record["inputs"])
    for ref in inputs:
        path = _path(root, ref["path"])
        if output == path or (output.exists() and output.samefile(path)):
            raise ProductionAdmissionError("production admission output would overwrite a consumed input")
        if composition.digest(path.read_bytes()) != ref["sha256"]:
            raise ProductionAdmissionError(f"stale admission input: {ref['path']}")


def publish_record(root: Path, record: dict[str, object], destination: str) -> None:
    """Preserve the prior record until pending bytes and bound inputs revalidate."""
    output = _path(root, destination)
    _publication_inputs(root, record, output)
    validate_record(root, record)
    output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(output) as pending:
        pending.write_bytes(composer.canonical_bytes(record))
        validate_record(root, record)
        _publication_inputs(root, record, output)
