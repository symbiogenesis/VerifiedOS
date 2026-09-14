# SPDX-License-Identifier: Apache-2.0
"""Portable command receipts and refusal paths, independent of framework adapters."""

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import memory_planner as planner
from vos.cli import BY_NAME
from vos.cli import memory_planner as cli


def invoke(arguments: list[str]) -> tuple[int, dict[str, Any]]:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main([*arguments, "--json"])
    return code, json.loads(output.getvalue())


def service_overlay() -> None:
    code, report = invoke(["demo"])
    instance = planner.parse_instance(report["instance"])
    ensure(code == 0 and not planner.check_placement(instance, report["placement"]),
           "non-ML service returns an independently valid plan")
    before = planner.pool_heights(instance, report["baseline"])["scratch"]
    after = planner.pool_heights(instance, report["placement"])["scratch"]
    ensure(before == 28 * 1024 * 1024 and after == 16 * 1024 * 1024,
           "exclusive scratch phases save capacity across independent workers")
    bad = [dict(row, offset=0) for row in report["placement"]]
    ensure(bool(planner.check_placement(instance, bad)), "cross-worker sharing remains forbidden")


def input_binding_and_refusal() -> None:
    raw, baseline, _ = cli.service_demo()
    with tempfile.TemporaryDirectory() as directory:
        instance = Path(directory) / "instance.json"
        candidate = Path(directory) / "candidate.json"
        instance.write_text(json.dumps(raw), encoding="utf-8")
        candidate.write_text(json.dumps(baseline), encoding="utf-8")
        code, report = invoke(["check", "--instance", str(instance), "--candidate", str(candidate)])
        ensure(code == 0, "valid external placement accepted")
        ensure(report["input_sha256"][str(candidate)] == hashlib.sha256(candidate.read_bytes()).hexdigest(),
               "receipt binds exact candidate bytes")
        baseline[1]["offset"] = 1
        candidate.write_text(json.dumps(baseline), encoding="utf-8")
        code, report = invoke(["check", "--instance", str(instance), "--candidate", str(candidate)])
        ensure(code != 0 and report["placement"] is None,
               "misaligned baseline cannot become a compatibility fallback")
        instance.write_text("{", encoding="utf-8")
        code, report = invoke(["plan", "--instance", str(instance), "--baseline", str(candidate)])
        ensure(code == 2 and report["evidence"]["status"] == "unknown/unsupported",
               "malformed input is not infeasibility")


def contract_route_and_source_binding() -> None:
    code, report = invoke(["contracts"])
    ensure(code == 0 and bool(planner.parse_instance(report["instance"]).buffers),
           "bounded contract demo exports a core-compatible instance")
    root = Path(__file__).resolve().parents[2]
    for name, digest in report["sources_sha256"].items():
        ensure(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest,
               "receipt binds actual implementation bytes")


def optional_input_failure_retains_baseline() -> None:
    raw, baseline, _ = cli.service_demo()
    with tempfile.TemporaryDirectory() as directory:
        instance = Path(directory) / "instance.json"
        standing = Path(directory) / "baseline.json"
        candidate = Path(directory) / "candidate.json"
        instance.write_text(json.dumps(raw), encoding="utf-8")
        standing.write_text(json.dumps(baseline), encoding="utf-8")
        arguments = ["plan", "--instance", str(instance), "--baseline", str(standing),
                     "--candidate", str(candidate)]
        code, report = invoke(arguments)
        ensure(code == 0 and report["placement"] == baseline,
               "unreadable optional candidate cannot destroy a valid fallback")
        candidate.write_text("{", encoding="utf-8")
        code, report = invoke(arguments)
        ensure(code == 0 and report["placement"] == baseline and report["evidence"]["rejected"],
               "malformed optional candidate is rejected after baseline validation")
        standing.write_text("[]", encoding="utf-8")
        code, report = invoke(arguments)
        ensure(code == 1 and str(candidate) not in report["input_sha256"],
               "invalid baseline must prevent optional work")


def routing_and_bad_arguments() -> None:
    command = BY_NAME["memory-planner"]
    ensure(command.guest_only(["demo-tflm"]) and not command.guest_only(["demo"]),
           "only the C++ build demonstration needs the guest")
    for arguments in (["plan"], ["demo", "--work-budget", "-1"],
                      ["demo", "--replay-budget", "0"]):
        code, _ = invoke(arguments)
        ensure(code == 2, "invalid options return a typed error")


def cases() -> list[Case]:
    return [Case("bounded service overlay", service_overlay),
            Case("input hashes and refused baseline", input_binding_and_refusal),
            Case("contract route and source identity", contract_route_and_source_binding),
            Case("optional failures preserve fallback", optional_input_failure_retains_baseline),
            Case("host and guest routing", routing_and_bad_arguments)]
