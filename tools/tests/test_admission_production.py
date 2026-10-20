# SPDX-License-Identifier: Apache-2.0
"""Production skeleton, build and derivation joins remain honest whole-image refusals."""

import json
import os
import shutil
from collections.abc import Callable, Generator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition import ROOT, _resolve_descriptors, _sandbox, _write
from vos import admission_production as production
from vos import boot, composer, composition, image
from vos.cli import admission as cli

PROJECTIONS = "out/production"
BUILD = "products/build.json"
IMAGE = "products/image.elf"
GRAPH = "products/graph.json"


def _record(root: Path) -> dict[str, object]:
    return production.make_record(root, composition.EXAMPLE, PROJECTIONS, BUILD, IMAGE, GRAPH)


def _refused(fn: Callable[[], object], phrase: str) -> None:
    try:
        fn()
    except (production.ProductionAdmissionError, composition.CompositionError) as error:
        ensure(phrase in str(error), f"wrong refusal: {error}")
        return
    raise AssertionError(f"missing refusal: {phrase}")


@contextmanager
def _fixture(*, evidence: bool = True, kernel_status: str | None = None) -> Generator[tuple[Path, dict[str, Any]]]:
    # All products and derivation bytes below are synthetic controls. They supply
    # exact declared identities and a real ELF container, never proof evidence.
    with _sandbox() as (root, raw):
        if kernel_status is not None:
            contract = root / boot.CONTRACT
            lines = contract.read_bytes().splitlines(keepends=True)
            for index, line in enumerate(lines):
                if line.startswith(b"| `kernel` |"):
                    cells = line.split(b"|")
                    cells[4] = f" `{kernel_status}` ".encode()
                    lines[index] = b"|".join(cells)
            contract.write_bytes(b"".join(lines))
        for checker in production.CHECKERS:
            target = root / checker
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / checker, target)
        runtime = [member for member in raw["members"]
                   if member["id"] not in ("composer", "admission")]
        (root / "products").mkdir()
        (root / "derivations").mkdir()
        artifacts = {}
        for index, member in enumerate(runtime):
            artifact = f"products/{member['id']}.bin"
            (root / artifact).write_bytes(f"synthetic artifact for {member['id']}".encode())
            artifacts[member["artifact_slot"]] = composition.reference(root, artifact)
            if evidence:
                derivation = f"derivations/{member['id']}.json"
                (root / derivation).write_bytes(composer.canonical_bytes({
                    "scope": "fixture-reference", "production_admission": False,
                    "binds_sha256": artifacts[member["artifact_slot"]]["sha256"],
                    "steps": [{"judgment": 2, "move": 0, "facet": 0, "site": 0}]}))
                member["derivation"]["source"] = composition.reference(root, derivation)
                member["admission_tier"] = index % 3
        graph = _resolve_descriptors(root, raw)
        memory = boot.regions(root / raw["configuration"]["path"])[0]
        raw["graph_placement"] = {"base": hex(memory.base + 4096), "bytes": len(graph)}
        _write(root, raw)
        image.write_elf(root / IMAGE, [
            image.Section(".text", memory.base, bytearray(b"\x13\0\0\0"), executable=True),
            image.Section(".handler_graph", memory.base + 4096, bytearray(graph))], {}, memory.base)
        (root / GRAPH).write_bytes(graph)
        outputs = composition.projections(root)
        composition.emit(root, composition.EXAMPLE, PROJECTIONS)
        built = composition.build_record(root, composition.EXAMPLE, outputs, artifacts,
                                         composition.reference(root, IMAGE), graph)
        (root / BUILD).write_bytes(composer.canonical_bytes(built))
        yield root, raw


def _bound_refusal() -> None:
    with _fixture() as (root, raw):
        result = _record(root)
        ensure(result["decision"] == "refused" and result["generation_accepted"] is False
               and result["production_admission"] is False, "bound declarations never become evidence")
        expected = ["rot-firmware", "mmode-firmware", "kernel", "supervisor", "crypto-core",
                    "storage", "copy-service"]
        members = cast("list[dict[str, Any]]", result["members"])
        ensure([member["member"] for member in members] == expected,
               "independent complete runtime roster remains present in the refusal")
        built = json.loads((root / BUILD).read_bytes())
        for member in members:
            declaration = next(item for item in raw["members"] if item["id"] == member["member"])
            ensure(member["artifact"] == built["artifacts"][declaration["artifact_slot"]],
                   "actual member artifact joins its exact declared symbolic slot")
            ensure(member["tier"] == declaration["admission_tier"]
                   and member["derivation"] == declaration["derivation"],
                   "declared tier and source identity survive the join")
            rules = {blocker["rule"] for blocker in member["blockers"]}
            ensure("DerivationCheckerUnavailable" in rules and "DerivationAbsent" not in rules,
                   "present metadata is bound but never checked as a real derivation")
        ensure(result["image"] == composition.reference(root, IMAGE)
               and result["graph"] == composition.reference(root, GRAPH), "actual image and graph bytes bind")
        inputs = {ref["path"]: ref["sha256"] for ref in cast("list[dict[str, str]]", result["inputs"])}
        for member in members:
            ref = member["derivation"]["source"]
            ensure(inputs[ref["path"]] == ref["sha256"], "exact derivation source bytes bind")
        production.validate_record(root, result)
        ensure(composer.canonical_bytes(_record(root)) == composer.canonical_bytes(result),
               "unchanged joined refusal is deterministic")


def _missing_and_forged_evidence() -> None:
    with _fixture(evidence=False) as (root, _raw):
        result = _record(root)
        for member in cast("list[dict[str, Any]]", result["members"]):
            rules = {blocker["rule"] for blocker in member["blockers"]}
            ensure({"TierUnassigned", "DerivationAbsent", "DerivationCheckerUnavailable"} <= rules,
                   "each absent member reports its own evidence obligations")
            ensure(all(blocker["owner"] for blocker in member["blockers"]), "every blocker names its owner")
        for forged in (dict(result, generation_accepted=True), dict(result, production_admission=True),
                       dict(result, decision="accepted"), dict(result, schema_version=True)):
            _refused(lambda forged=forged: production.validate_record(root, forged), "differs")
        _refused(lambda: production.publish_record(root, dict(result, production_admission=True),
                                                  "products/forged.json"), "differs")
        ensure(not (root / "products/forged.json").exists(), "forged acceptance cannot publish")
        request = root / PROJECTIONS / "admission-request.json"
        value = json.loads(request.read_bytes())
        value["payload"]["members"][0]["certificate"] = {"accepted": True, "steps": []}
        request.write_bytes(composer.canonical_bytes(value))
        _refused(lambda: _record(root), "stale projection")


def _roster_status() -> None:
    for status in ("fixture", "executable"):
        with _fixture(kernel_status=status) as (root, _raw):
            result = _record(root)
            member = next(member for member in cast("list[dict[str, Any]]", result["members"])
                          if member["member"] == "kernel")
            rules = {blocker["rule"] for blocker in member["blockers"]}
            ensure(("RosterMemberUnaccepted" in rules) == (status != "executable"),
                   "fixture runtime members are unaccepted by the production boundary")
            ensure("DerivationCheckerUnavailable" in rules and result["generation_accepted"] is False,
                   "executable status alone supplies no derivation evidence")


def _stale_joins() -> None:
    for relative, phrase in ((IMAGE, "image"), (GRAPH, "graph"),
                             ("products/storage.bin", "stale source"),
                             ("derivations/storage.json", "stale source"),
                             (f"{PROJECTIONS}/manifest.c", "stale projection")):
        with _fixture() as (root, _raw):
            result = _record(root)
            path = root / relative
            path.write_bytes(path.read_bytes() + b"substitution")
            _refused(lambda result=result: production.validate_record(root, result), phrase)
    with _fixture() as (root, _raw):
        result = _record(root)
        built = json.loads((root / BUILD).read_bytes())
        built["artifacts"]["storage-artifact"] = built["artifacts"]["crypto-core-artifact"]
        (root / BUILD).write_bytes(composer.canonical_bytes(built))
        _refused(lambda: production.validate_record(root, result), "substituted artifact")
    for relative in (BUILD, *production.CHECKERS):
        with _fixture() as (root, _raw):
            result = _record(root)
            path = root / relative
            path.write_bytes(path.read_bytes() + b"\n")
            _refused(lambda result=result: production.validate_record(root, result), "differs")


def _publication_and_cli() -> None:
    with _fixture() as (root, _raw):
        result = _record(root)
        protected = [IMAGE, GRAPH, BUILD, composition.EXAMPLE,
                     "products/storage.bin", "derivations/storage.json",
                     f"{PROJECTIONS}/admission-request.json", *production.CHECKERS]
        for relative in protected:
            before = (root / relative).read_bytes()
            _refused(lambda relative=relative: production.publish_record(root, result, relative), "overwrite")
            ensure((root / relative).read_bytes() == before, "publication preserves each consumed input")
        alias = root / "products/alias.json"
        os.link(root / "derivations/storage.json", alias)
        _refused(lambda: production.publish_record(root, result, "products/alias.json"), "overwrite")
        production.publish_record(root, result, "products/admission.json")
        production.validate_record(root, json.loads((root / "products/admission.json").read_bytes()))
        args = ["production-record", composition.EXAMPLE, "--projections", PROJECTIONS,
                "--build-record", BUILD, "--image", IMAGE, "--graph", GRAPH,
                "--out", "products/cli-admission.json"]
        output = StringIO()
        with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
            ensure(cli.main(args) == 1, "CLI never succeeds a generation with an unavailable checker")
            ensure(cli.main(["check-production-record", "products/cli-admission.json"]) == 1,
                   "current refusal replay remains a refused generation")
            saved = root / "products/cli-admission.json"
            original = saved.read_bytes()
            for duplicate in (b'"production_admission":true,', b'"schema_version":true,',
                              b'"image":{"path":"products/substitute.bin","sha256":"forged"},'):
                saved.write_bytes(b"{" + duplicate + original[1:])
                ensure(cli.main(["check-production-record", "products/cli-admission.json"]) == 2,
                       "ambiguous saved production flags and identities are unreadable input")
            saved.write_bytes(original)
            ensure(cli.main(["check-production-record", "products/cli-admission.json"]) == 1,
                   "restored exact refusal record still replays")
        ensure('"production_admission": false' in output.getvalue(), "CLI preserves evidence scope")
        ensure("duplicate JSON key" in output.getvalue(), "saved-record ambiguity receives a named refusal")


def _publication_drift() -> None:
    with _fixture() as (root, _raw):
        result = _record(root)
        path = root / "derivations/storage.json"
        path.write_bytes(b"new purported derivation")
        _refused(lambda: production.publish_record(root, result, "products/admission.json"), "stale admission input")
        ensure(not (root / "products/admission.json").exists(), "drift publishes no record")


def _construction_drift() -> None:
    validate = composition.validate_build_record
    for relative in (IMAGE, GRAPH, "products/storage.bin", "derivations/storage.json",
                     f"{PROJECTIONS}/admission-request.json", BUILD, *production.CHECKERS):
        with _fixture() as (root, _raw):
            def substituted_join(root_path: Path, source: str, record: object, outputs: dict[str, bytes],
                                 graph_data: bytes, image_ref: dict[str, str], relative: str = relative) -> None:
                validate(root_path, source, record, outputs, graph_data, image_ref)
                path = root_path / relative
                path.write_bytes(path.read_bytes() + b"\n")
            with patch.object(composition, "validate_build_record", substituted_join):
                _refused(lambda: _record(root), "stale admission input")


def cases() -> list[Case]:
    return [Case("production joins bind every declared identity but refuse unchecked evidence", _bound_refusal),
            Case("missing tiers and derivations remain per-member generation refusals", _missing_and_forged_evidence),
            Case("production status rejects fixtures and retains executable proof obligations", _roster_status),
            Case("image graph artifact derivation and projection substitutions refuse", _stale_joins),
            Case("publication protects consumed bytes and CLI reports a refused generation", _publication_and_cli),
            Case("derivation drift before publication withholds the record", _publication_drift),
            Case("drift after the build join cannot publish stale owner identities", _construction_drift)]
