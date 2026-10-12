# SPDX-License-Identifier: Apache-2.0
"""Inspect decoded host inference inputs under symbolic composition grants."""

import argparse
import hashlib
import json
from dataclasses import asdict, fields
from pathlib import Path

from vos import inference_admission as admission
from vos.corpus import find_root
from vos.inference_contract import Ceiling, Costs, Shape, natural
from vos.inference_grant import KvPlacement, per_token_bytes
from vos.inference_residency import checked_routed_work


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate input field: {key}")
        result[key] = value
    return result


def _object(value: object, names: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError(f"{label} must contain exactly {', '.join(sorted(names))}")
    return {name: value[name] for name in names}


def _number(value: object, label: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{label} must be a nonnegative integer")
    return natural(value, label)


def _numbers(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an integer array")
    return tuple(_number(item, label) for item in value)


def inspect(raw: bytes, root: Path) -> dict[str, object]:
    """Fail closed on unknown/missing/coerced inputs; report the bound host scope."""
    data = _object(json.loads(raw, object_pairs_hook=_unique),
                   {"shape", "ceiling", "costs", "residency", "kv_placement", "server",
                    "sessions_open", "requested_rate", "route"}, "input")
    shape_data = _object(data["shape"], {item.name for item in fields(Shape)}, "shape")
    shape = Shape(**{name: _number(value, name) for name, value in shape_data.items()})
    ceiling_data = _object(data["ceiling"], {item.name for item in fields(Ceiling)}, "ceiling")
    ceiling = Ceiling(
        _number(ceiling_data["max_resident_bytes"], "max_resident_bytes"),
        _number(ceiling_data["max_context_length"], "max_context_length"),
        _numbers(ceiling_data["admitted_formats"], "admitted_formats"),
        _number(ceiling_data["max_expert_count"], "max_expert_count"),
        _number(ceiling_data["fixed_top_k"], "fixed_top_k"),
        _number(ceiling_data["max_kv_bytes_per_token"], "max_kv_bytes_per_token"),
        _number(ceiling_data["ceiling_grant"], "ceiling_grant"))
    cost_data = _object(data["costs"], {item.name for item in fields(Costs)}, "costs")
    costs = Costs(**{name: _number(value, name) for name, value in cost_data.items()})
    server_data = _object(data["server"], {item.name for item in fields(admission.Server)}, "server")
    server = admission.Server(_number(server_data["slot"], "slot"),
                              _numbers(server_data["workers"], "workers"),
                              _number(server_data["pool_bytes"], "pool_bytes"),
                              _number(server_data["session_capacity"], "session_capacity"))
    flags = data["residency"]
    if not isinstance(flags, list) or any(type(flag) is not bool for flag in flags):
        raise ValueError("residency must be an array of exact booleans")
    residency = tuple(flags)
    placement_value = data["kv_placement"]
    if not isinstance(placement_value, str):
        raise TypeError("kv_placement must name an explicit bank placement")
    placement = KvPlacement(placement_value)
    state = _number(data["sessions_open"], "sessions_open")
    requested = _number(data["requested_rate"], "requested_rate")
    route = _numbers(data["route"], "route")
    step = admission.opening(shape, ceiling, residency, placement, server, state, requested)
    work = checked_routed_work(shape, costs, residency, route) if step.refusal is None else None
    owners = ("proofs/InferenceAdmission.v", "tools/vos/inference_contract.py",
              "tools/vos/inference_residency.py", "tools/vos/inference_grant.py",
              "tools/vos/inference_admission.py", "tools/vos/cli/inference_admission.py")
    return {"schema_version": 1, "scope": "finite host reference with symbolic composition inputs",
            "production_admission": False,
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "sources": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                        for name in owners},
            "session_decision": "refused" if step.refusal is not None else "admitted",
            "refusal": step.refusal, "requested_rate": requested,
            "admitted_rate": step.admitted_rate, "bytes_per_token": per_token_bytes(shape, placement),
            "checked_route_work": work,
            "route_decision": "not_run" if step.refusal is not None else
                              ("valid" if work is not None else "refused"),
            "route_valid": (work is not None) if step.refusal is None else None,
            "sessions_before": state, "sessions_after": step.sessions_open,
            "server_before": asdict(server), "server_after": asdict(step.server),
            "open": ["wire parser correspondence", "concrete residency and uniform expert cost",
                     "kernel WCET and target correspondence", "DSE and qualified grant/latency",
                     "qualified KV placement"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, prog="run.py inference-admission")
    parser.add_argument("input", type=Path, help="JSON containing decoded host reference inputs")
    args = parser.parse_args(argv)
    try:
        result = inspect(args.input.read_bytes(), find_root())
    except (OSError, ValueError, TypeError) as error:
        print(f"FAIL inference-admission: {error}")
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["session_decision"] == "admitted" and result["route_valid"] else 1
