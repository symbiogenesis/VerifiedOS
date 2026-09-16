# SPDX-License-Identifier: Apache-2.0
"""Exercise the identity and completion-cost joins across the phase instruments."""

import hashlib
import json
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos.cli import phase_evaluate, phase_schedule, phase_service
from vos.jsonc import Json


def _object(value: Json) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise TypeError("expected an object in the pipeline fixture or receipt")
    return value


def _read(path: Path) -> dict[str, Json]:
    return _object(cast(Json, json.loads(path.read_bytes())))


def _write(path: Path, value: dict[str, Json]) -> None:
    path.write_bytes((json.dumps(value, indent=2) + "\n").encode("utf-8"))


def _call(command: Callable[[list[str] | None], int], args: list[str]) -> tuple[int, dict[str, Json]]:
    output = StringIO()
    with redirect_stdout(output):
        code = command([*args, "--json"])
    return code, _object(cast(Json, json.loads(output.getvalue())))


def _bind(schedule: Path, costs: Path) -> None:
    data = _read(costs)
    data["schedule"] = {"id": _read(schedule)["name"], "path": schedule.name,
                        "sha256": hashlib.sha256(schedule.read_bytes()).hexdigest()}
    _write(costs, data)


def _inputs(folder: Path) -> tuple[Path, Path, Path]:
    resources, schedule, costs = (folder / name for name in ("resources.json", "schedule.json", "costs.json"))
    _write(resources, {
        "schema": "phase-resources-v1", "harts": [{"name": "main", "issue_limit": 1}],
        "operations": ["write"],
        "banks": [{"name": "ram", "path_cycles": 1, "occupancy_cycles": {"write": 2},
                   "refresh_cycles": None}],
    })
    _write(schedule, {
        "schema": "phase-schedule-v1", "name": "synthetic-pipeline", "mode": "periodic",
        "resources_sha256": hashlib.sha256(resources.read_bytes()).hexdigest(),
        "phases": [{"grant": 1, "refresh": [], "alternatives": [[
            {"hart": "main", "bank": "ram", "operation": "write"}]]},
            {"grant": 1, "refresh": [], "alternatives": [[]]},
            {"grant": 1, "refresh": [], "alternatives": [[]]}],
    })
    fixture = TOOLS.parent / "docs/implementation/phase-service/cost-examples/favorable.json"
    _write(costs, _read(fixture))
    _bind(schedule, costs)
    return schedule, resources, costs


def _evaluate(schedule: Path, resources: Path, costs: Path) -> tuple[int, dict[str, Json]]:
    return _call(phase_evaluate.main, [str(schedule), str(resources), "--costs", str(costs)])


def _complete_join() -> None:
    examples = TOOLS.parent / "docs/implementation/phase-service/schedule-examples"
    code, report = _evaluate(examples / "closed-companion.json", examples / "resources.json",
                             examples / "costs.json")
    ensure(code == 0 and report["branch_verdict"] == "favorable"
           and report["target_comparison"] == "open", "documented joined example drifted")
    with tempfile.TemporaryDirectory() as tmp:
        schedule, resources, costs = _inputs(Path(tmp))
        code, report = _evaluate(schedule, resources, costs)
        ensure(code == 0 and report["branch_verdict"] == "favorable", "synthetic join must close")
        ensure(report["target_comparison"] == "open", "arithmetic cannot qualify a target")
        ensure(_object(report["acceptance"])["drain"] == 1
               and _object(report["completion"])["quiescent_drain"] == 2,
               "completion must add the residual bank cycle to the fabric drain")
        contract = Path(tmp) / "emitted.json"
        emitted_code, emitted = _call(phase_schedule.main,
                                     [str(schedule), str(resources), "--output-contract", str(contract)])
        checked_code, checked = _call(phase_service.main, ["--contract", str(contract), "--completion"])
        ensure(emitted_code == checked_code == 0, "the emitted contract must be consumable directly")
        ensure(emitted["contract_sha256"] == checked["contract_sha256"]
               == _object(report["inputs_sha256"])["contract"], "all readers must bind identical bytes")
        ensure(checked["completion"] == report["completion"], "standalone and joined completion disagree")


def _identity_failures() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for field, wrong in (("id", "another-schedule"), ("sha256", "0" * 64), ("path", "other.json")):
            schedule, resources, costs = _inputs(Path(tmp))
            data = _read(costs)
            _object(data["schedule"])[field] = wrong
            _write(costs, data)
            code, report = _evaluate(schedule, resources, costs)
            ensure(code == 2 and "error" in report, f"mismatched schedule {field} accepted")
        schedule, resources, costs = _inputs(Path(tmp))
        resources.write_bytes(resources.read_bytes() + b"\n")
        ensure(_evaluate(schedule, resources, costs)[0] == 2, "stale resource bytes accepted")


def _drain_join() -> None:
    examples: tuple[tuple[Json, str, int], ...] = (
        ([1, 1], "refuted", 1), ([1, 2], "inconclusive", 0), (None, "open", 0))
    with tempfile.TemporaryDirectory() as tmp:
        for bound, verdict, exit_code in examples:
            schedule, resources, costs = _inputs(Path(tmp))
            data = _read(costs)
            _object(data["boundary"])["d_pipe_completion"] = bound
            _write(costs, data)
            code, report = _evaluate(schedule, resources, costs)
            ensure(code == exit_code and report["branch_verdict"] == verdict,
                   f"completion bound did not constrain declared drain {bound}")


def _service_refutation_wins() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        schedule, resources, costs = _inputs(Path(tmp))
        data = _read(schedule)
        phases = data["phases"]
        if not isinstance(phases, list):
            raise TypeError("fixture phases missing")
        _object(phases[0])["grant"] = 0
        _write(schedule, data)
        _bind(schedule, costs)
        code, report = _evaluate(schedule, resources, costs)
        ensure(_object(report["cost"])["arithmetic_verdict"] == "favorable",
               "this regression must retain favorable standalone arithmetic")
        ensure(code == 1 and report["branch_verdict"] == "refuted"
               and report["target_comparison"] == "open", "cost arithmetic concealed service refusal")


def _completion_refutation_wins() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        schedule, resources, costs = _inputs(Path(tmp))
        data = _read(resources)
        data["banks"] = [
            {"name": "long", "path_cycles": 0, "occupancy_cycles": {"write": 3}, "refresh_cycles": None},
            {"name": "short", "path_cycles": 0, "occupancy_cycles": {"write": 1}, "refresh_cycles": None},
        ]
        _write(resources, data)
        data = _read(schedule)
        data["resources_sha256"] = hashlib.sha256(resources.read_bytes()).hexdigest()
        data["phases"] = [
            {"grant": 1, "refresh": [], "alternatives": [[
                {"hart": "main", "bank": "long", "operation": "write"}]]},
            {"grant": 1, "refresh": [], "alternatives": [[
                {"hart": "main", "bank": "short", "operation": "write"}]]},
            {"grant": 0, "refresh": [], "alternatives": [[]]},
        ]
        _write(schedule, data)
        _bind(schedule, costs)
        code, report = _evaluate(schedule, resources, costs)
        ensure(_object(report["acceptance"])["zero_wait"] is True
               and _object(report["cost"])["arithmetic_verdict"] == "favorable",
               "the counterexample must pass acceptance and arithmetic")
        ensure(code == 1 and report["branch_verdict"] == "refuted"
               and _object(report["completion"])["ordered"] is False,
               "a favorable acceptance/cost pair hid completion inversion")


def cases() -> list[Case]:
    return [Case("complete-join", _complete_join), Case("identity-failures", _identity_failures),
            Case("drain-join", _drain_join), Case("service-refutation-wins", _service_refutation_wins),
            Case("completion-refutation-wins", _completion_refutation_wins)]
