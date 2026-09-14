# SPDX-License-Identifier: Apache-2.0
"""Encoding directions and bounded refusals; real LRAT runs through the guest demo."""

import hashlib
import itertools
import json
import tempfile
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import memory_planner as planner
from vos import memory_planner_certificates as cert
from vos.cli import memory_planner_certificates as cli

ROOT = Path(__file__).resolve().parents[2]


def _instance(buffers: list[dict[str, Any]], capacity: int = 4, **extra: object) -> planner.Instance:
    return planner.parse_instance({"name": "encoding-test", "pools": [{"id": "a", "capacity": capacity}],
                                   "buffers": buffers, **extra})


def _buffer(identifier: str, size: int, **extra: object) -> dict[str, Any]:
    return {"id": identifier, "size": size, "allowed_pools": ["a"],
            "intervals": [[0, 2]], **extra}


def _satisfies(encoding: cert.Encoding, literals: tuple[int, ...]) -> bool:
    positive = {literal for literal in literals if literal > 0}
    return all(any((literal in positive) if literal > 0 else (-literal not in positive)
                   for literal in clause) for clause in encoding.clauses)


def _models(encoding: cert.Encoding) -> list[tuple[int, ...]]:
    # Bounded truth tables intentionally ignore the encoder's choice-group helper:
    # dropping an at-most-one or at-least-one clause changes this oracle's result.
    ensure(encoding.variable_count <= 15, "truth-table test fixture unexpectedly grew")
    return [tuple(i + 1 if value else -(i + 1) for i, value in enumerate(bits))
            for bits in itertools.product((False, True), repeat=encoding.variable_count)
            if _satisfies(encoding, tuple(i + 1 if value else -(i + 1)
                                          for i, value in enumerate(bits)))]


def _both_encoding_directions() -> None:
    for overlap in (True, False):
        instance = _instance([_buffer("x", 2), _buffer("y", 1, intervals=[[1, 3] if overlap else [2, 3]])], 3)
        for bound in (0, 2, 3):
            encoding = cert.encode(instance, objective_bound=bound)
            expected = set()
            for first, second in itertools.product(range(3), repeat=2):
                placement = [{"id": "x", "pool": "a", "offset": first},
                             {"id": "y", "pool": "a", "offset": second}]
                if planner.check_placement(instance, placement):
                    continue
                if sum(planner.pool_heights(instance, placement).values()) > bound:
                    continue
                expected.add((first, second))
                witness = cert.assignment_for_placement(instance, encoding, placement)
                ensure(_satisfies(encoding, witness), "legal smaller placement lost its encoded witness")
            actual = set()
            for model in _models(encoding):
                placement = cert.decode_assignment(instance, encoding, list(model))
                actual.add(tuple(row["offset"] for row in placement))
            ensure(actual == expected, "one-hot CNF solved a different placement problem")


def _aliases_reservations_gaps_and_zero_extents() -> None:
    instance = _instance([
        _buffer("root", 2, fixed_pool="b", fixed_offset=0, allowed_pools=["a", "b"]),
        _buffer("view", 1, alias_of="root", alias_offset=1, allowed_pools=["b"]),
        _buffer("zero", 0, fixed_offset=3, allowed_pools=["b"]),
    ], pools=[{"id": "a", "capacity": 3, "reserved": [[0, 1]]}, {"id": "b", "capacity": 3}])
    placement = [{"id": "root", "pool": "b", "offset": 0},
                 {"id": "view", "pool": "b", "offset": 1},
                 {"id": "zero", "pool": "b", "offset": 3}]
    encoding = cert.encode(instance, objective_bound=3, pool_limits={"b": 2, "a": 1})
    witness = cert.assignment_for_placement(instance, encoding, placement)
    ensure(_satisfies(encoding, witness), "zero-size address or pool reservation excluded legal layout")
    ensure(cert.decode_assignment(instance, encoding, list(witness)) == placement, "alias relation changed")
    ensure(not _models(cert.encode(instance, objective_bound=2)), "reservation cost omitted from objective")
    gaps = _instance([_buffer("x", 2, alignment=2, intervals=[[0, 1], [2, 3]]),
                      _buffer("y", 2, intervals=[[1, 2]])], 2)
    ensure(bool(_models(cert.encode(gaps, objective_bound=2))), "inactive gaps lost")
    conflict_raw = asdict(gaps)
    conflict_raw["conflicts"] = [["x", "y"]]
    ensure(not _models(cert.encode(planner.parse_instance(conflict_raw), objective_bound=2)),
           "explicit coexistence conflict disappeared")


def _limits_never_truncate_into_false_infeasibility() -> None:
    instance = _instance([_buffer("x", 1)], planner.MAX_INTEGER)
    placement = [{"id": "x", "pool": "a", "offset": 0}]
    result = cert.certify(instance, placement, ROOT)
    ensure(result["placement"] == placement and result["evidence"]["status"] == "checked feasible"
           and result["evidence"]["certificate_status"] == "unknown",
           "finite-domain budget erased a valid fallback or became optimality")
    ensure("max_domain_values" in result["evidence"]["reason"], "domain refusal lost its reason")
    small = _instance([_buffer("x", 1), _buffer("y", 1)])
    for limits in (cert.Limits(max_work=1), cert.Limits(max_variables=1),
                   cert.Limits(max_clauses=1), cert.Limits(max_domain_values=1)):
        try:
            cert.encode(small, objective_bound=2, limits=limits)
        except cert.EncodingLimit:
            continue
        raise AssertionError("encoding returned a partial problem after its budget")
    invalid = cert.certify(small, [], ROOT)
    ensure(invalid["placement"] is None and "invalid candidate" in invalid["evidence"]["reason"],
           "invalid candidate reached optional toolchain work")


def _empty_domains_and_zero_objective() -> None:
    impossible = _instance([_buffer("x", 5)], 4)
    encoding = cert.encode(impossible)
    ensure(encoding.variable_count == 0 and encoding.clauses == ((),), "empty domain must encode contradiction")
    empty = _instance([], 0)
    ensure(_models(cert.encode(empty)) == [()], "empty feasible instance lost")
    ensure(not _models(cert.encode(empty, objective_bound=-1)), "negative total-height query must be UNSAT")
    zero = _instance([_buffer("x", 0, fixed_offset=4)], 4)
    candidate = [{"id": "x", "pool": "a", "offset": 4}]
    encoded = cert.encode(zero, objective_bound=0)
    ensure(_satisfies(encoded, cert.assignment_for_placement(zero, encoded, candidate)),
           "zero-sized address became charged memory")


def _identities_and_decoder_refusals() -> None:
    instance = _instance([_buffer("x", 1)], 2)
    encoded = cert.encode(instance, objective_bound=1)
    ensure(encoded.identity() == cert.encode(instance, objective_bound=1).identity(), "encoding is nondeterministic")
    ensure(encoded.identity()["cnf_sha256"] != cert.encode(instance, objective_bound=0).identity()["cnf_sha256"],
           "different optimization question has same formula identity")
    good = cert.assignment_for_placement(instance, encoded, [{"id": "x", "pool": "a", "offset": 0}])
    for bad in ([], [999], [*good, -good[0]], [-abs(literal) for literal in good]):
        try:
            cert.decode_assignment(instance, encoded, bad)
        except cert.CertificateError:
            continue
        raise AssertionError("malformed or non-model SAT assignment accepted")
    changed = _instance([_buffer("x", 2)], 2)
    try:
        cert.decode_assignment(changed, encoded, list(good))
    except cert.CertificateError:
        pass
    else:
        raise AssertionError("SAT assignment from another instance accepted")
    for report in ({}, {"evidence": {"status": "checked feasible"}},
                   {"evidence": {"status": "checked optimal", "instance_digest": "changed"}}):
        try:
            cert.replay(instance, report, ROOT)
        except cert.CertificateError:
            continue
        raise AssertionError("unbound certificate metadata reached external replay")


def _encode_cli_contract() -> None:
    output_dir = ROOT / "out"
    output_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary:
        path = Path(temporary) / "instance.json"
        path.write_text(json.dumps(asdict(_instance([_buffer("x", 1)], 1))), encoding="utf-8")
        stream = StringIO()
        with redirect_stdout(stream):
            code = cli.main(["encode", "--instance", str(path), "--bound", "0", "--dimacs"])
        ensure(code == 0 and stream.getvalue().startswith("p cnf "), "host encode route did not emit DIMACS")


def _receipt_scope_and_provenance() -> None:
    instance = _instance([_buffer("x", 1)], 1)
    placement = [{"id": "x", "pool": "a", "offset": 0}]
    encoding = cert.encode(instance, objective_bound=0)
    toolchain = {"checker_endpoint": "metadata-test endpoint", "pins": {"checker": "test pin"}}
    output_dir = ROOT / "out"
    output_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary:
        proof = Path(temporary) / "metadata-only.lrat"
        proof.write_bytes(b"metadata test only; not an LRAT proof")
        report: dict[str, Any] = {"placement": placement, "evidence": {
            "scope": cert.evidence_scope(), "status": "checked optimal",
            "certificate_status": "checked LRAT refutation", "checker_returncode": 0,
            "checker_output": "s VERIFIED UNSAT\n", "instance_digest": planner.instance_digest(instance),
            "encoding_version": cert.ENCODING_VERSION, "source_sha256": cert._source_identity(ROOT),
            "limits": asdict(cert.DEFAULT_LIMITS), "timeout_seconds": 1,
            "objective": {"metric": "sum-pool-extents-in-bytes", "pool_limits": {"a": 1},
                          "strictly_better_query_bound": 0},
            "pool_heights": {"a": 1},
            "encoding_sha256": encoding.identity()["encoding_sha256"],
            "cnf_sha256": encoding.identity()["cnf_sha256"],
            "toolchain": toolchain, "proof_endpoint": toolchain["checker_endpoint"],
            "artifacts": {"lrat": str(proof)},
            "certificate_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
        }}
        # This checks metadata only. The guest demo must still invoke real LRAT.
        with patch.object(cert, "_tools", return_value=toolchain), \
                patch.object(cert, "certify", return_value={"rechecked": True}) as native:
            ensure(cert.replay(instance, report, ROOT) == {"rechecked": True},
                   "valid scoped metadata did not reach native revalidation")
            native.assert_called_once()
            native.reset_mock()
            mutations: list[tuple[str, object]] = [
                ("scope", None), ("scope", {**cert.evidence_scope(), "admitted_verdict": True}),
                ("scope", {**cert.evidence_scope(), "grounds_refinement": 0}),
                ("scope", {**cert.evidence_scope(), "instance_lrat_replayed_by_rocq": True}),
                ("certificate_status", "unknown"), ("checker_returncode", False),
                ("checker_output", "s VERIFIED UNSAT\nextra acceptance\n"),
                ("proof_endpoint", "Rocq kernel rechecked this LRAT"),
                ("toolchain", {**toolchain, "pins": {"checker": "different pin"}}),
                ("limits", []), ("objective", None),
                ("objective", {**report["evidence"]["objective"], "strictly_better_query_bound": False}),
                ("pool_heights", {"a": 1.0}), ("artifacts", []),
            ]
            for field, value in mutations:
                changed = deepcopy(report)
                changed["evidence"][field] = value
                try:
                    cert.replay(instance, changed, ROOT)
                except cert.CertificateError:
                    continue
                raise AssertionError(f"forged or malformed receipt field reached replay: {field}")
            native.assert_not_called()


def _strict_json_and_input_identity() -> None:
    output_dir = ROOT / "out"
    output_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary:
        directory = Path(temporary)
        instance = directory / "instance.json"
        raw_instance = asdict(_instance([_buffer("x", 1)], 2))
        instance.write_text(json.dumps(raw_instance), encoding="utf-8")
        other = directory / "other.json"
        for role in ("instance", "candidate", "pool-limits", "evidence"):
            for malformed in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}'):
                other.write_text(malformed, encoding="utf-8")
                action = "verify" if role == "evidence" else "encode"
                argv = [action, "--instance", str(other if role == "instance" else instance)]
                if role != "instance":
                    argv.extend(["--" + role, str(other)])
                stream = StringIO()
                with redirect_stdout(stream):
                    code = cli.main(argv)
                result = json.loads(stream.getvalue())
                ensure(code == 1 and any("duplicate JSON" in text or "nonfinite JSON" in text
                                        for text in result["findings"]),
                       f"{role} accepted ambiguous JSON")
                ensure(result["input_sha256"][str(other)] == hashlib.sha256(other.read_bytes()).hexdigest(),
                       "rejected input lost the identity of the actual parsed bytes")
        for role in ("candidate", "pool-limits"):
            other.write_text("null", encoding="utf-8")
            with redirect_stdout(StringIO()):
                code = cli.main(["encode", "--instance", str(instance), "--" + role, str(other)])
            ensure(code == 1, "explicit null input silently changed the query")
        results = []
        for indent in (None, 2):
            instance.write_text(json.dumps(raw_instance, indent=indent), encoding="utf-8")
            stream = StringIO()
            with redirect_stdout(stream):
                code = cli.main(["encode", "--instance", str(instance), "--bound", "0"])
            ensure(code == 0, "valid strict JSON failed encoding")
            results.append(json.loads(stream.getvalue()))
        ensure(results[0]["encoding_sha256"] == results[1]["encoding_sha256"] and
               results[0]["input_sha256"] != results[1]["input_sha256"],
               "raw source identity was confused with normalized model identity")


def cases() -> list[Case]:
    return [Case("CNF both directions against complete truth tables", _both_encoding_directions),
            Case("CNF aliases reservations gaps and zero extents", _aliases_reservations_gaps_and_zero_extents),
            Case("encoding budgets keep feasible fallback", _limits_never_truncate_into_false_infeasibility),
            Case("empty domains and zero objective", _empty_domains_and_zero_objective),
            Case("formula identity and SAT decoder refusals", _identities_and_decoder_refusals),
            Case("host DIMACS command", _encode_cli_contract),
            Case("receipt rejects forged scope and checker provenance", _receipt_scope_and_provenance),
            Case("strict external JSON and exact input byte identity", _strict_json_and_input_identity)]
