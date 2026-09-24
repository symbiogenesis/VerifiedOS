# SPDX-License-Identifier: Apache-2.0
"""Admission metadata refusal, atomicity, identity and reference-case generation."""

import copy
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos import admission, boot, toolenv

ROOT = TOOLS.parent


def _reject(fn: Callable[[], object], needle: str) -> None:
    try:
        fn()
    except admission.AdmissionError as exc:
        ensure(needle in str(exc), f"wrong refusal: {exc}")
    else:
        raise AssertionError(f"missing refusal: {needle}")


@contextmanager
def _fixture() -> Iterator[tuple[Path, boot.Roster, dict[str, object]]]:
    parent = toolenv.environment(ROOT, sys.platform).parent / "admission-tests"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        root = Path(temporary)
        for relative in (admission.SOURCE, admission.CHECKER, boot.CONTRACT):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        roster = boot.load_roster(root, boot.CONTRACT)
        reference = admission.read_reference(root)
        members = []
        for index, member in enumerate(roster.members):
            if member.kind == "offline":
                continue
            artifact = f"{member.id}.bin"
            payload = f"fixture bytes for {member.id}".encode()
            (root / artifact).write_bytes(payload)
            tier = index % len(reference.tiers)
            members.append({"member": member.id, "artifact": artifact, "tier": tier,
                            "certificate": {"versions": list(reference.versions),
                                            "binds_sha256": admission.digest(payload),
                                            "steps": [{"judgment": 2, "move": reference.routing[f],
                                                       "facet": f, "site": i}
                                                      for i, f in enumerate(reference.required[tier])]}})
        raw: dict[str, object] = {"schema_version": 1, "scope": "fixture-reference",
                                 "profile": "AdmissionPath.demo", "members": members}
        (root / "request.json").write_bytes(admission.canonical(raw))
        yield root, roster, raw


def _reference_families() -> None:
    reference = admission.read_reference(ROOT)
    cases = admission.generated_cases(reference)
    names = [name for name, _ in cases]
    ensure(len(set(names)) == len(names), "comparison names must be unique")
    rules = {admission.decide(reference, package).rule for _, package in cases}
    ensure(rules == {None, "DerivationAbsent", "VersionMismatch", "BindingMismatch",
                     "TierUnrecognised", "FormUnrecognised", "DeletionUnconfirmed",
                     "CitationMissing", "AttributeMissing"}, "all refusal rules must be reached")
    for name, package in cases:
        verdict = admission.decide(reference, package)
        if any(part in name for part in ("covering", "duplicate", "reverse", "retag")):
            ensure(verdict.rule is None, f"acceptance-preserving case refused: {name}")
        if any(part in name for part in ("_drop_", "_judgment_", "_move_", "_facet_")):
            ensure(verdict.rule is not None, f"negative case accepted: {name}")
    source = admission.comparison_source(reference)
    ensure(source.count("Example compare_") == len(cases), "every case reaches Gallina")
    ensure("spec_check demo Cert full_reading" in source, "comparison calls the real reference")


def _phase_order() -> None:
    reference = admission.read_reference(ROOT)
    cases = dict(admission.generated_cases(reference))
    for name, rule in (("version_before_binding", "VersionMismatch"),
                       ("binding_before_tier", "BindingMismatch"),
                       ("tier_before_structure", "TierUnrecognised"),
                       ("deletion_before_citation", "DeletionUnconfirmed")):
        ensure(admission.decide(reference, cases[name]).rule == rule, name)
    package = cases["tier0_covering"]
    cert = package.certificate
    ensure(cert is not None, "fixture certificate")
    cert = cast("admission.Certificate", cert)
    steps = tuple(s for s in cert.steps if reference.moves[s.move] == "ConfirmADeletion")
    ensure(admission.decide(reference, replace(package, certificate=replace(cert, steps=steps))).rule
           == "CitationMissing", "citations must precede attributes")


def _record_bindings() -> None:
    with _fixture() as (root, roster, _):
        record = admission.make_record(root, "request.json", b"image", b"graph", roster)
        ensure(record["decision"] == "accepted", "covering fixture must accept")
        ensure(record["production_admission"] is False and bool(record["open"]),
               "metadata acceptance cannot close real admission")
        ensure(not admission.validate_record(root, record, b"image", b"graph", roster), "replay")
        ensure("image digest" in admission.validate_record(root, record, b"other", b"graph", roster)[0],
               "different image must refuse")
        ensure("graph digest" in admission.validate_record(root, record, b"image", b"other", roster)[0],
               "different graph must refuse")
        forged = dict(record, production_admission=True)
        ensure(bool(admission.validate_record(root, forged, b"image", b"graph", roster)), "forged promotion")
        forged = dict(record, schema_version=True)
        ensure(bool(admission.validate_record(root, forged, b"image", b"graph", roster)),
               "JSON booleans must not alias record integers")
        artifact = root / "rot-firmware.bin"
        artifact.write_bytes(b"replacement")
        ensure(bool(admission.validate_record(root, record, b"image", b"graph", roster)), "stale artifact")


def _whole_generation() -> None:
    with _fixture() as (root, roster, raw):
        members = cast("list[dict[str, object]]", raw["members"])
        for position in range(len(members)):
            damaged = copy.deepcopy(raw)
            cast("list[dict[str, object]]", damaged["members"])[position]["certificate"] = None
            (root / "request.json").write_bytes(admission.canonical(damaged))
            record = admission.make_record(root, "request.json", b"image", b"graph", roster)
            ensure(record["decision"] == "refused" and record["generation_accepted"] is False,
                   f"refused member {position} must cost the generation")
            ensure(len(cast("list[object]", record["members"])) == len(members),
                   "refusal must not filter a roster")
            ensure(bool(admission.validate_record(root, record, b"image", b"graph", roster)),
                   "a replayable refusal is not an accepted attachment")


def _input_refusals() -> None:
    with _fixture() as (root, roster, raw):
        def check(value: dict[str, object], needle: str) -> None:
            (root / "request.json").write_bytes(admission.canonical(value))
            _reject(lambda: admission.make_record(root, "request.json", b"i", b"g", roster), needle)

        check(dict(raw, scope="production"), "only fixture-reference")
        check(dict(raw, schema_version=True), "schema_version")
        check(dict(raw, admitted=True), "expected exactly")
        check(dict(raw, members=[]), "runtime roster")
        malformed = copy.deepcopy(raw)
        members = cast("list[dict[str, object]]", malformed["members"])
        members[0]["artifact"] = "../outside.bin"
        check(malformed, "relative to the checkout")
        malformed = copy.deepcopy(raw)
        members = cast("list[dict[str, object]]", malformed["members"])
        members[0]["tier"] = True
        check(malformed, "natural number")
        (root / "request.json").write_bytes(b'{"scope":1,"scope":2}')
        _reject(lambda: admission.make_record(root, "request.json", b"i", b"g", roster),
                "duplicate JSON key")


def _source_shape() -> None:
    with _fixture() as (root, _, _):
        path = root / admission.SOURCE
        original = path.read_text(encoding="utf-8")
        expected = admission.read_reference(root)
        path.write_text("(* outer (* nested *) comment *)\n" + original,
                        encoding="utf-8", newline="\n")
        ensure(admission.read_reference(root) == expected, "nested comments must be read correctly")
        for before, after, needle in (
            ("| TypeWellFormed => 0", "| TypeWellFormed => 7", "judgment coding"),
            ("| MemSpatial => CiteAnInvariant", "| MemSpatial => unexpected expression",
             "mapping arm"),
            ("| _ => None", "| _ => Some TypeWellFormed", "judgment decoding"),
        ):
            ensure(before in original, f"source fixture anchor missing: {before}")
            path.write_text(original.replace(before, after, 1), encoding="utf-8", newline="\n")
            _reject(lambda: admission.read_reference(root), needle)


def cases() -> list[Case]:
    return [Case("reference families cover acceptance and each refusal", _reference_families),
            Case("the reference first-failure phase order", _phase_order),
            Case("record binds exact bytes and cannot promote fixture evidence", _record_bindings),
            Case("every refused roster position costs the generation", _whole_generation),
            Case("unsupported and ambiguous requests fail closed", _input_refusals),
            Case("source vocabulary changes cannot silently shift decoding", _source_shape)]
