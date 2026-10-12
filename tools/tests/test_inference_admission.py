# SPDX-License-Identifier: Apache-2.0
"""Joined host opening, resource preservation and hostile decoded-input checks."""

import json
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import cast

from vos.inference_grant import KvPlacement

from tests.harness import Case, ensure
from vos import inference_admission as admission
from vos.cli import inference_admission as cli
from vos.inference_contract import Ceiling, Costs, Refusal, Shape

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
    ensure(report["decision"] == "admitted" and report["checked_route_work"] == 16,
           "front door joins source witness's rate and uniform work")
    ensure(report["production_admission"] is False, "host verdict must disclose scope")
    ensure(report["server_before"] == report["server_after"], "reported resource preservation")
    ensure(report["sources"] and report["input_sha256"], "report binds sources and actual input bytes")
    for key, value in (("extra", 0), ("requested_rate", True), ("residency", [1] * 4),
                       ("kv_placement", None), ("route", [-1]), ("shape", {})):
        data = _payload()
        data[key] = value
        try:
            cli.inspect(json.dumps(data).encode(), ROOT)
        except ValueError:
            continue
        raise AssertionError(f"malformed input accepted: {key}={value!r}")
    try:
        cli.inspect(b'{"shape": 0, "shape": 1}', ROOT)
    except ValueError:
        return
    raise AssertionError("duplicate JSON key accepted")


def cases() -> list[Case]:
    return [Case("joined residency/grant boundary and preserved resources", _boundaries_and_preservation),
            Case("every ceiling field boundary retains refusal cause", _ceiling_boundaries),
            Case("Gallina refusal precedence and zero grant", _refusal_precedence),
            Case("decoded inputs preserve the natural-number domain", _numeric_domain),
            Case("strict front door binds host inputs and rejects coercions", _front_door)]
