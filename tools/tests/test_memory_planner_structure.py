# SPDX-License-Identifier: Apache-2.0
"""Recognized structural candidates preserve the portable check and fallback boundary."""

import copy
import hashlib
import itertools
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import memory_planner as planner
from vos import memory_planner_candidates as candidates
from vos import memory_planner_structure as structure
from vos.cli import memory_planner as cli


def fixture(intervals: list[list[int]], sizes: tuple[int, ...]) -> tuple[dict[str, Any], planner.Placement]:
    raw: dict[str, Any] = {"name": "small-structural", "pools": [{"id": "pool", "capacity": 16}],
           "buffers": [{"id": f"object-{index}", "size": size, "allowed_pools": ["pool"],
                        "intervals": [interval]}
                       for index, (interval, size) in enumerate(zip(intervals, sizes, strict=True))]}
    offset = 0
    baseline = []
    for index, size in enumerate(sizes):
        baseline.append({"id": f"object-{index}", "pool": "pool", "offset": offset})
        offset += size
    return raw, baseline


def invoke(arguments: list[str]) -> tuple[int, dict[str, Any]]:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main([*arguments, "--json"])
    return code, json.loads(output.getvalue())


def small_exact_oracle() -> None:
    families = ([[0, 4], [1, 3], [1, 2]], [[0, 2], [1, 3], [2, 4]],
                [[0, 1], [1, 2], [2, 3]], [[0, 2], [0, 2], [2, 3]])
    for intervals in families:
        for sizes in itertools.product((1, 2), repeat=3):
            raw, baseline = fixture(intervals, sizes)
            instance = planner.parse_instance(raw)
            candidate = structure.TwoStackCandidate(max_objects=3)
            result = planner.plan(instance, baseline, candidates=(candidate,),
                                  certify=True, replay_budget=1000)
            ensure(result["evidence"]["status"] == "checked optimal",
                   "nested, crossing, equal and adjacent cases agree with exhaustive portable replay")
            ensure(not planner.check_placement(instance, result["placement"]),
                   "candidate is independently feasible in the original instance")
            ensure(planner.pool_heights(instance, result["placement"])["pool"]
                   == candidate.last_evidence["peak_live_load"], "construction attains peak load")
            ensure({row["id"] for row in result["placement"]} == {b.id for b in instance.buffers},
                   "conversion preserves every object identity")
    raw, _ = fixture([[0, planner.MAX_INTEGER - 1], [planner.MAX_INTEGER - 1, planner.MAX_INTEGER]], (2, 3))
    instance = planner.parse_instance(raw)
    candidate = structure.TwoStackCandidate(max_objects=2)
    placement = candidate(instance)
    ensure(planner.pool_heights(instance, placement)["pool"] == 3,
           "half-open adjacent endpoints preserve sharing without increment or overflow")
    case = structure.convert(instance, max_objects=2)
    ensure([(o.start, o.reuse) for o in case.objects] == [b.intervals[0] for b in instance.buffers],
           "conversion copies endpoint values exactly")


def unsupported_preserves_baseline() -> None:
    original, baseline = fixture([[0, 2], [1, 3]], (2, 2))
    variants: list[tuple[dict[str, Any], planner.Placement, str]] = []
    for key, value, reason in (("alignment", 2, "unit alignment"),
                               ("intervals", [], "one nonempty interval"),
                               ("intervals", [[0, 1], [2, 3]], "one nonempty interval"),
                               ("size", 0, "positive size"),
                               ("fixed_pool", "pool", "fixed locations"),
                               ("fixed_offset", 0, "fixed locations")):
        raw = copy.deepcopy(original)
        raw["buffers"][0][key] = value
        variants.append((raw, baseline, reason))
    raw = copy.deepcopy(original)
    raw["pools"][0]["reserved"] = [[8, 9]]
    variants.append((raw, baseline, "reserved ranges"))
    raw = copy.deepcopy(original)
    raw["conflicts"] = [["object-0", "object-1"]]
    variants.append((raw, baseline, "explicit conflicts"))
    raw = copy.deepcopy(original)
    raw["pools"].append({"id": "another", "capacity": 2})
    variants.append((raw, baseline, "exactly one pool"))
    raw = copy.deepcopy(original)
    raw["buffers"][1]["alias_of"] = "object-0"
    alias_baseline = copy.deepcopy(baseline)
    alias_baseline[1]["offset"] = 0
    variants.append((raw, alias_baseline, "aliases"))
    for raw, standing, reason in variants:
        before = copy.deepcopy(raw)
        instance = planner.parse_instance(raw)
        candidate = structure.TwoStackCandidate(max_objects=2)
        result = planner.plan(instance, standing, candidates=(candidate,))
        ensure(result["placement"] == standing and bool(result["evidence"]["rejected"]),
               "unsupported candidate must retain the independently checked baseline")
        ensure(reason in candidate.last_evidence["findings"][0], "unsupported constraint is diagnosed")
        ensure(raw == before, "recognition must not erase or mutate unsupported constraints")


def bounded_recognition_and_odd_cycle() -> None:
    raw, baseline = fixture([[0, 3], [1, 4], [2, 5]], (1, 1, 1))
    instance = planner.parse_instance(raw)
    candidate = structure.TwoStackCandidate(max_objects=3)
    result = planner.plan(instance, baseline, candidates=(candidate,))
    ensure(result["placement"] == baseline and result["evidence"]["status"] == "checked feasible",
           "a non-bipartite family supplies no optimum or fallback search")
    ensure("not bipartite" in candidate.last_evidence["findings"][0]
           and len(candidate.last_evidence["crossing_graph"]["odd_cycle"]) == 3,
           "non-bipartite refusal retains its odd-cycle diagnosis")
    limited = structure.TwoStackCandidate(max_objects=2)
    with patch.object(structure.structure, "two_colouring", side_effect=RuntimeError("must not recognize")):
        result = planner.plan(instance, baseline, candidates=(limited,))
    ensure(result["placement"] == baseline and "1..2 buffers" in limited.last_evidence["findings"][0],
           "object limit is enforced before graph recognition")
    untouched = structure.TwoStackCandidate(max_objects=3)
    result = planner.plan(instance, [], candidates=(untouched,))
    ensure(result["placement"] is None and untouched.last_evidence["status"] == "not attempted",
           "an invalid baseline prevents optional work")
    supported, _ = fixture([[0, 1], [1, 2]], (1, 1))
    candidate(planner.parse_instance(supported))
    planner.plan(instance, baseline, candidates=(candidate,))
    ensure("pool_heights" not in candidate.last_evidence and "peak_live_load" not in candidate.last_evidence,
           "reusing a producer cannot retain stale success diagnostics after refusal")


def corrupt_producer_rejected() -> None:
    raw, baseline = fixture([[0, 2], [1, 3]], (2, 2))
    instance = planner.parse_instance(raw)
    corrupt = [{"id": buffer.id, "arena": "pool", "base": 0} for buffer in instance.buffers]
    candidate = structure.TwoStackCandidate(max_objects=2)
    with patch.object(structure.structure, "two_stack_placement", return_value=corrupt):
        result = planner.plan(instance, baseline, candidates=(candidate,))
    ensure(result["placement"] == baseline and bool(result["evidence"]["rejected"]),
           "corrupted structural output cannot replace the valid fallback")
    ensure(candidate.last_evidence["status"] == "rejected candidate"
           and "overlap" in candidate.last_evidence["findings"][0],
           "portable checker supplies independent corruption finding")
    raw, baseline = fixture([[0, 1], [1, 2]], (2, 2))
    instance = planner.parse_instance(raw)
    nonminimal = [{"id": row["id"], "arena": row["pool"], "base": row["offset"]} for row in baseline]
    with patch.object(structure.structure, "two_stack_placement", return_value=nonminimal):
        result = planner.plan(instance, baseline, candidates=(candidate,))
    ensure(result["placement"] == baseline and "did not attain" in candidate.last_evidence["findings"][0],
           "feasible corrupted output must also satisfy the constructor's declared peak-load boundary")


def cli_controls_and_source_binding() -> None:
    for action in ("check", "solve", "verify", "contracts", "resources", "resource-proof", "demo-tflm", "structure-corpus"):
        code, result = invoke([action, "--two-stack"])
        ensure(code == 2 and not result["input_sha256"]
               and "--two-stack" in result["evidence"]["findings"][0],
               "unused candidate controls are explicitly refused before I/O")
    for action in ("check", "solve", "verify", "contracts", "resources", "resource-proof", "demo-tflm"):
        for value in ("0", "3"):
            code, result = invoke([action, "--two-stack-max-objects", value])
            ensure(code == 2 and not result["input_sha256"]
                   and "--two-stack-max-objects" in result["evidence"]["findings"][0],
                   "unused object controls are explicitly refused even when set to zero")
    for arguments in (["demo", "--two-stack"], ["structure-corpus"],
                      ["demo", "--two-stack-max-objects", "3"],
                      ["demo", "--two-stack", "--two-stack-max-objects", "0"],
                      ["demo", "--two-stack", "--two-stack-max-objects", "-1"]):
        code, result = invoke(arguments)
        ensure(code == 2 and not result["input_sha256"], "the explicit positive object limit is required and consumed")
    raw, baseline = fixture([[0, 1], [1, 2]], (2, 3))
    with tempfile.TemporaryDirectory() as directory:
        instance = Path(directory) / "instance.json"
        standing = Path(directory) / "baseline.json"
        instance.write_text(json.dumps(raw), encoding="utf-8")
        standing.write_text(json.dumps(baseline), encoding="utf-8")
        code, result = invoke(["plan", "--instance", str(instance), "--baseline", str(standing),
                               "--two-stack", "--two-stack-max-objects", "2"])
    ensure(code == 0 and result["evidence"]["status"] == "checked feasible"
           and result["two_stack_candidate"]["status"] == "checked candidate",
           "explicit structural selection preserves the separate certification endpoint")
    root = Path(__file__).resolve().parents[2]
    for name in ("tools/vos/memory_planner_structure.py", "tools/vos/static_memory_structure.py",
                 "tools/vos/static_memory.py", "tools/vos/memory_planner_candidates.py"):
        ensure(result["sources_sha256"][name] == hashlib.sha256((root / name).read_bytes()).hexdigest(),
               "candidate and corpus implementation bytes are bound in the receipt")
    code, result = invoke(["demo", "--two-stack", "--two-stack-max-objects", "8"])
    ensure(code == 0 and result["two_stack_candidate"]["status"] == "unsupported"
           and bool(result["placement"]), "the richer service demo retains its checked incumbent")


def corpus_is_deterministic() -> None:
    code, report = invoke(["structure-corpus", "--two-stack-max-objects", "512"])
    ensure(code == 0 and report == invoke(["structure-corpus", "--two-stack-max-objects", "512"])[1],
           "same corpus, source identities and object limit yield identical reports")
    ensure([row["name"] for row in report["results"]] == [i.name for i in candidates.comparison_corpus()],
           "corpus membership comes from the existing owner")
    ensure([row["name"] for row in report["results"] if row["eligible"]]
           == ["adjacent", "equal-overlap", "mixed-crossing", "nested"],
           "recognized examples and diagnosed non-bipartite larger traces remain visible")
    ensure(all(row["selected"]["evidence"]["status"] == "checked feasible" for row in report["results"]),
           "a structural report does not claim finite optimality certification")
    limited = structure.corpus_report(max_objects=2)
    ensure(all(not row["eligible"] for row in limited["results"]), "corpus honors the same object limit")
    ensure("seconds" not in json.dumps(report) and "elapsed" not in json.dumps(report),
           "eligibility reporting contains no benchmark measurements")


def cases() -> list[Case]:
    return [Case("two-stack exhaustive small oracle and endpoints", small_exact_oracle),
            Case("two-stack unsupported constraints retain baseline", unsupported_preserves_baseline),
            Case("two-stack bound and odd-cycle refusal", bounded_recognition_and_odd_cycle),
            Case("two-stack corruption rejected independently", corrupt_producer_rejected),
            Case("two-stack CLI controls and source identity", cli_controls_and_source_binding),
            Case("two-stack deterministic corpus eligibility", corpus_is_deterministic)]
