# SPDX-License-Identifier: Apache-2.0
"""Joined host opening, resource preservation and hostile decoded-input checks."""

import json
import tempfile
from contextlib import redirect_stdout
from dataclasses import asdict, fields, replace
from io import StringIO
from pathlib import Path
from typing import cast

from tests.harness import Case, ensure
from vos import inference_admission as admission
from vos.cli import inference_admission as cli
from vos.inference_contract import Ceiling, Costs, Refusal, Shape
from vos.inference_grant import KvPlacement

ROOT = Path(__file__).resolve().parents[2]
SHAPE = Shape(40, 128, 1, 4, 2, 8)
CEILING = Ceiling(40, 128, (1,), 4, 2, 8, 200)
SERVER = admission.Server(7, (3, 5), 4096, 2)


def _open(shape: Shape = SHAPE, ceiling: Ceiling = CEILING,
          residency: tuple[bool, ...] = (True,) * 4, state: int = 0,
          rate: int = 4) -> admission.Step:
    return admission.opening(shape, ceiling, residency, KvPlacement.BANK, SERVER, state, rate)


def _boundaries_and_preservation() -> None:
    for occupancy in range(4):
        for requested in range(7):
            step = _open(state=occupancy, rate=requested)
            accepted = occupancy < 2 and requested * 48 <= 200
            ensure((step.refusal is None) == accepted, "independent resource/spending boundary")
            ensure(step.server is SERVER, "opening must preserve actual declared server")
            ensure(step.sessions_open == occupancy + int(accepted), "occupancy changes only on admission")
            ensure(step.admitted_rate == (4 if accepted else None), "no degraded or refused admitted rate")


def _ceiling_boundaries() -> None:
    changed = (
        ("resident_bytes", 41, Refusal.RESIDENT_BYTES_ABOVE_CEILING),
        ("context_length", 129, Refusal.CONTEXT_ABOVE_CEILING),
        ("format", 2, Refusal.FORMAT_NOT_ADMITTED),
        ("expert_count", 5, Refusal.EXPERT_COUNT_ABOVE_CEILING),
        ("top_k", 1, Refusal.TOP_K_NOT_THE_FIXED_VALUE),
        ("kv_bytes_per_token", 9, Refusal.KV_PER_TOKEN_ABOVE_CEILING),
    )
    for field, value, reason in changed:
        step = _open(replace(SHAPE, **{field: value}), residency=(True,) * 5)
        ensure(step.refusal == reason, f"ceiling field {field} retains cause")
        ensure(step.server is SERVER and step.sessions_open == 0, "ceiling refusal preserves resources")


def _refusal_precedence() -> None:
    bad = replace(SHAPE, resident_bytes=41, top_k=5)
    ensure(_open(bad, residency=(False,) * 4).refusal == Refusal.EXPERT_NOT_RESIDENT,
           "finite residency wrapper precedes top-k and ceiling")
    ensure(_open(bad).refusal == Refusal.TOP_K_NOT_THE_FIXED_VALUE,
           "top-k/count wrapper precedes resident-byte ceiling")
    empty = replace(SHAPE, resident_bytes=0, kv_bytes_per_token=0)
    ensure(_open(empty, state=2, rate=5).refusal == Refusal.PER_TOKEN_BYTES_NOT_DECLARED,
           "undefined traffic precedes exhaustion and rate")
    ensure(_open(state=2, rate=5).refusal == Refusal.SESSION_POOL_EXHAUSTED,
           "pool refusal precedes excessive rate")
    zero = _open(ceiling=replace(CEILING, ceiling_grant=0), rate=0)
    ensure(zero.refusal is None and zero.admitted_rate == 0, "positive traffic with zero grant follows nat division")


def _numeric_domain() -> None:
    for field in fields(SHAPE):
        for bad in (True, False, -1, 0.5, "4", None):
            try:
                replace(SHAPE, **{field.name: cast(int, bad)})
            except ValueError:
                continue
            raise AssertionError(f"non-natural {field.name} accepted: {bad!r}")
    for field in fields(CEILING):
        if field.name != "admitted_formats":
            try:
                replace(CEILING, **{field.name: True})
            except ValueError:
                continue
            raise AssertionError(f"boolean ceiling accepted: {field.name}")


def _payload() -> dict[str, object]:
    return {"shape": asdict(SHAPE), "ceiling": asdict(CEILING),
            "costs": asdict(Costs(10, 3, 100)), "server": asdict(SERVER),
            "residency": [True] * 4, "kv_placement": KvPlacement.BANK.value,
            "sessions_open": 0, "requested_rate": 4, "route": [0, 2]}


def _front_door() -> None:
    raw = json.dumps(_payload()).encode()
    report = cli.inspect(raw, ROOT)
    ensure(report["session_decision"] == "admitted" and report["checked_route_work"] == 16,
           "front door joins decoded fixture rate and uniform work")
    ensure(report["production_admission"] is False, "host verdict must disclose scope")
    ensure(report["server_before"] == report["server_after"], "reported resource preservation")
    ensure(bool(report["sources"]) and bool(report["input_sha256"]),
           "report binds sources and actual input bytes")
    exhausted = _payload()
    exhausted["sessions_open"] = 2
    refused = cli.inspect(json.dumps(exhausted).encode(), ROOT)
    ensure(refused["route_decision"] == "not_run" and refused["route_valid"] is None,
           "refused session cannot supply a route-check verdict")
    invalid_route = _payload()
    invalid_route["route"] = [4, 4]
    routed = cli.inspect(json.dumps(invalid_route).encode(), ROOT)
    ensure(routed["session_decision"] == "admitted" and routed["route_decision"] == "refused"
           and routed["route_valid"] is False and routed["checked_route_work"] is None,
           "opening and route refusal are separate source operations")
    for key, value in (("extra", 0), ("requested_rate", True), ("residency", [1] * 4),
                       ("kv_placement", None), ("route", [-1]), ("shape", {})):
        data = _payload()
        data[key] = value
        try:
            cli.inspect(json.dumps(data).encode(), ROOT)
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"malformed input accepted: {key}={value!r}")
    try:
        cli.inspect(b'{"shape": 0, "shape": 1}', ROOT)
    except ValueError:
        return
    raise AssertionError("duplicate JSON key accepted")


def _cli_exit_codes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-inference-") as directory:
        path = Path(directory) / "input.json"
        for change, expected in (({}, 0), ({"requested_rate": 5}, 1),
                                 ({"route": [4, 4]}, 1), ({"requested_rate": True}, 2)):
            data = _payload()
            data.update(change)
            path.write_text(json.dumps(data), encoding="utf-8")
            with redirect_stdout(StringIO()):
                code = cli.main([str(path)])
            ensure(code == expected, f"CLI preserves semantic/invalid-input exit: {change}")
        path.write_bytes(b"invalid JSON")
        with redirect_stdout(StringIO()):
            code = cli.main([str(path)])
        ensure(code == 2, "invalid serialized input has no admission verdict")


def _deeply_nested_input() -> None:
    data = _payload()
    del data["route"]
    # The pinned CPython's C decoder has its own platform-dependent stack bound.
    depth = 65536
    raw = (json.dumps(data)[:-1].encode() + b', "route": '
           + b"[" * depth + b"0" + b"]" * depth + b"}")
    with tempfile.TemporaryDirectory(prefix="vos-inference-nesting-") as directory:
        path = Path(directory) / "input.json"
        path.write_bytes(raw)
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main([str(path)])
        ensure(code == 2 and output.getvalue().startswith("FAIL inference-admission:"),
               "over-nested decoded input must fail through the invalid-input CLI boundary")
        ensure("nesting" in output.getvalue(), "decoder limit refusal retains its cause")
        try:
            cli.inspect(raw, ROOT)
        except ValueError:
            pass
        else:
            raise AssertionError("inspection accepted an over-nested route")
        path.write_text(json.dumps(_payload()), encoding="utf-8")
        with redirect_stdout(StringIO()):
            code = cli.main([str(path)])
        ensure(code == 0, "decoder limit refusal must preserve the inhabited valid input")


def cases() -> list[Case]:
    return [Case("joined residency/grant boundary and preserved resources", _boundaries_and_preservation),
            Case("every ceiling field boundary retains refusal cause", _ceiling_boundaries),
            Case("Gallina refusal precedence and zero grant", _refusal_precedence),
            Case("decoded inputs preserve the natural-number domain", _numeric_domain),
            Case("strict front door binds host inputs and rejects coercions", _front_door),
            Case("command exit codes distinguish success, refusal and malformed input", _cli_exit_codes),
            Case("over-nested route refuses cleanly beside a valid opening", _deeply_nested_input)]
