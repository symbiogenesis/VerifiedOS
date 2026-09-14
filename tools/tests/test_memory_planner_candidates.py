# SPDX-License-Identifier: Apache-2.0
"""Semantic conversion and fallback tests; upstream execution is a separate demo."""

import argparse
import copy
import io
import json
import subprocess
import tarfile
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import memory_planner as planner
from vos import memory_planner_candidates as candidates
from vos.cli import memory_planner_candidates as cli


def model() -> planner.Instance:
    return candidates.comparison_corpus()[1]


def endpoint_conversion_preserves_conflicts() -> None:
    raw: dict[str, Any] = {"name": "all-endpoints", "pools": [{"id": "p", "capacity": 100}],
                           "buffers": [{"id": f"{start}:{end}", "size": 1,
                                        "allowed_pools": ["p"], "intervals": [[start, end]]}
                                       for start in (0, 1, 9, 9223372036854775806)
                                       for end in (1, 9, 9223372036854775807) if start < end]}
    instance = planner.parse_instance(raw)
    encoded = [tuple(map(int, line.split("\t"))) for line in candidates.encode_jobs(instance).splitlines()]
    for i, left in enumerate(instance.buffers):
        ensure(encoded[i][2] - encoded[i][1] >= 2, "nonempty interval lost its interior")
        for j, right in enumerate(instance.buffers):
            original = left.intervals[0][0] < right.intervals[0][1] and right.intervals[0][0] < left.intervals[0][1]
            converted = encoded[i][1] < encoded[j][2] and encoded[j][1] < encoded[i][2]
            ensure(original == converted, "rank conversion changed coexistence")


def richer_models_are_refused() -> None:
    mutations = [
        lambda raw: raw["buffers"][0].update(size=0),
        lambda raw: raw["buffers"][0].update(alignment=2),
        lambda raw: raw["buffers"][0].update(intervals=[[0, 1], [3, 4]]),
        lambda raw: raw["buffers"][0].update(fixed_offset=0),
        lambda raw: raw["buffers"][1].update(alias_of=raw["buffers"][0]["id"]),
        lambda raw: raw.update(conflicts=[[raw["buffers"][0]["id"], raw["buffers"][1]["id"]]]),
        lambda raw: raw["pools"][0].update(reserved=[[0, 1]]),
        lambda raw: raw["pools"].append({"id": "other", "capacity": 100}),
        lambda raw: raw["buffers"][0].update(size=1 << 31),
    ]
    for mutate in mutations:
        raw = asdict(model())
        raw["buffers"] = list(raw["buffers"])
        raw["pools"] = list(raw["pools"])
        mutate(raw)
        instance = planner.parse_instance(raw)
        try:
            candidates.encode_jobs(instance)
        except planner.UnsupportedError:
            continue
        raise AssertionError("a richer instance was silently narrowed")


def protocol_identity_is_strict() -> None:
    instance = model()
    for invalid in ("0\t0\n", "0\t0\n0\t1\n2\t2\n", "0\t0\n1\t2\n9\t4\n",
                    "0\t0\n1\t2\n2\t-1\n", "0\t0\textra\n1\t2\n2\t4\n"):
        try:
            candidates.decode_jobs(instance, invalid)
        except ValueError:
            continue
        raise AssertionError("malformed identity protocol accepted")
    valid = candidates.decode_jobs(instance, "2\t0\n0\t0\n1\t2\n")
    ensure(not planner.check_placement(instance, valid), "adjacent offsets lost original identity")


def rejected_upstream_retains_baseline() -> None:
    instance = model()
    baseline = candidates.separate_baseline(instance)
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        executable = output / "fixture-binary"
        executable.write_bytes(b"a fixture, never upstream execution")
        candidate = candidates.IdeallocCandidate(executable, candidates.digest(executable), output)

        def corrupt(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
            Path(command[2]).write_text("0\t0\n1\t0\n2\t0\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0)

        with patch.object(candidates.subprocess, "run", side_effect=corrupt):
            result = planner.plan(instance, baseline, candidates=(candidate,))
        ensure(result["placement"] == baseline, "overlapping upstream candidate displaced baseline")
        ensure(candidate.last_evidence["findings"], "original-model checker diagnostic lost")
        with patch.object(candidates.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 1)):
            result = planner.plan(instance, baseline, candidates=(candidate,))
        ensure(result["placement"] == baseline and result["evidence"]["rejected"], "timeout lost fallback")
        executable.write_bytes(b"changed")
        with patch.object(candidates.subprocess, "run") as run:
            result = planner.plan(instance, baseline, candidates=(candidate,))
            ensure(not run.called and result["placement"] == baseline, "changed executable was launched")


def invalid_baseline_stops_optional_work() -> None:
    instance = model()
    baseline = candidates.separate_baseline(instance)
    baseline[0]["offset"] = 1000
    with patch.object(candidates, "greedy_candidate") as callback:
        result = planner.plan(instance, baseline, candidates=(callback,))
        ensure(not callback.called and result["placement"] is None, "candidate ran before valid baseline")


def corpus_candidates_are_checked_and_repeatable() -> None:
    for instance in candidates.comparison_corpus():
        before = copy.deepcopy(asdict(instance))
        candidate = candidates.greedy_candidate(instance)
        ensure(candidate == candidates.greedy_candidate(instance), "local heuristic is nondeterministic")
        ensure(not planner.check_placement(instance, candidate), "local heuristic placement invalid")
        ensure(asdict(instance) == before, "local heuristic mutated input")


def dependency_archive_and_source_identity() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        package = output / "crate-1.0"
        package.mkdir()
        source = package / "lib.rs"
        source.write_bytes(b"original")
        archive = output / "crate-1.0.crate"
        with tarfile.open(archive, "w:gz") as stream:
            row = tarfile.TarInfo("crate-1.0/lib.rs")
            row.size = 8
            stream.addfile(row, io.BytesIO(b"original"))
        checksum = candidates.digest(archive)
        candidates.verify_crate(package, archive, checksum)
        source.write_bytes(b"tampered")
        try:
            candidates.verify_crate(package, archive, checksum)
        except ValueError:
            pass
        else:
            raise AssertionError("tampered unpacked dependency passed its lock-bound archive")
        with tarfile.open(archive, "w:gz") as stream:
            row = tarfile.TarInfo("crate-1.0/../outside")
            row.size = 1
            stream.addfile(row, io.BytesIO(b"x"))
        try:
            candidates.verify_crate(package, archive, candidates.digest(archive))
        except ValueError:
            return
        raise AssertionError("archive traversal was accepted")


def setup_failure_preserves_cli_baseline() -> None:
    instance = model()
    baseline = candidates.separate_baseline(instance)
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        source, standing = output / "instance.json", output / "baseline.json"
        source.write_text(json.dumps(asdict(instance)), encoding="utf-8")
        standing.write_text(json.dumps(baseline), encoding="utf-8")
        args = argparse.Namespace(action="plan", instance=source, baseline=standing, timeout=30, iterations=1)
        with patch.object(candidates, "build_idealloc", side_effect=ValueError("fixture setup failure")):
            result = cli.run(args, Path(__file__).resolve().parents[2], output)
        ensure(result["placement"] == baseline, "optional setup failure lost checked CLI baseline")
        ensure(result["candidate"]["reason"] == "fixture setup failure", "setup failure diagnostic lost")


def cases() -> list[Case]:
    return [Case("half-open to open conversion preserves all pair conflicts", endpoint_conversion_preserves_conflicts),
            Case("richer models refused without narrowing", richer_models_are_refused),
            Case("upstream identity protocol strict", protocol_identity_is_strict),
            Case("bad upstream output timeout and tampering retain baseline", rejected_upstream_retains_baseline),
            Case("invalid baseline blocks optional work", invalid_baseline_stops_optional_work),
            Case("comparison corpus local candidates checked", corpus_candidates_are_checked_and_repeatable),
            Case("dependency archive and unpacked-source tampering refused", dependency_archive_and_source_identity),
            Case("optional setup failure preserves CLI baseline", setup_failure_preserves_cli_baseline)]
