# SPDX-License-Identifier: Apache-2.0
"""Check supplied GEMM measurements against a separately reviewed campaign plan.

This checks identities, completeness and arithmetic, never producer truth or ISA
admission. The contract is docs/implementation/matrix-margin-contract.md.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import cast

from vos.jsonc import Json


@dataclass(frozen=True)
class Margin:
    id: str
    dtype: str
    throughput: str
    per_watt: str
    band: str
    wider_per_watt: bool


@dataclass(frozen=True)
class Comparison:
    plan_sha256: str
    report_sha256: str
    configuration_sha256: str
    protocol_sha256: str
    rvv_extensions: tuple[str, ...]
    cases: tuple[Margin, ...]
    band: str
    wider_per_watt: bool


def _pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _noninteger(_value: str) -> None:
    raise ValueError("floating-point and non-finite numbers are unsupported")


def _decode(blob: bytes) -> Json:
    return cast(Json, json.loads(blob.decode("utf-8"), object_pairs_hook=_pairs,
                                 parse_float=_noninteger, parse_constant=_noninteger))


def _object(value: Json, keys: set[str]) -> dict[str, Json]:
    if not isinstance(value, dict) or value.keys() != keys:
        raise ValueError(f"expected object fields: {', '.join(sorted(keys))}")
    return value


def _name(value: Json) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("expected nonempty name without surrounding whitespace")
    return value


def _digest(value: Json) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("expected full lowercase SHA-256 identity")
    return value


def _extensions(value: Json) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("extension set must be nonempty")
    names = tuple(_name(member) for member in value)
    if len(set(names)) != len(names):
        raise ValueError("duplicate extension")
    return tuple(sorted(names))


def _cases(value: Json, keys: set[str]) -> dict[str, dict[str, Json]]:
    if not isinstance(value, list) or not value:
        raise ValueError("case set must be nonempty")
    result: dict[str, dict[str, Json]] = {}
    for member in value:
        row = _object(member, keys)
        name = _name(row["id"])
        if name in result:
            raise ValueError(f"duplicate case: {name}")
        result[name] = row
    return result


def _positive(value: Json) -> int:
    if type(value) is not int or not 0 < value < 2**64:
        raise ValueError("measurements must be positive unsigned 64-bit integers")
    return value


def _arm(value: Json, output: str) -> tuple[int, int, str]:
    arm = _object(value, {"ticks", "energy_quanta", "output_sha256", "receipt_sha256"})
    if _digest(arm["output_sha256"]) != output:
        raise ValueError("measured output differs from the planned reference")
    return (_positive(arm["ticks"]), _positive(arm["energy_quanta"]),
            _digest(arm["receipt_sha256"]))


def _band(ratio: Fraction) -> str:
    if ratio < 8:
        return "below-band"
    return "review-band" if ratio < 10 else "clears-band"


def compare(plan_blob: bytes, report_blob: bytes) -> Comparison:
    """Refuse incomplete pairs and classify exact ratios without deciding admission."""
    plan = _object(_decode(plan_blob), {"schema", "configuration_sha256", "protocol_sha256",
                                       "rvv_extensions", "cases"})
    report = _object(_decode(report_blob), {"schema", "plan_sha256", "configuration_sha256",
                                           "rvv_extensions", "cases"})
    if plan["schema"] != "matrix-margin-plan-v1" or report["schema"] != "matrix-margin-report-v1":
        raise ValueError("unsupported matrix margin schema")
    plan_hash = hashlib.sha256(plan_blob).hexdigest()
    if _digest(report["plan_sha256"]) != plan_hash:
        raise ValueError("report does not bind the supplied plan bytes")
    configuration = _digest(plan["configuration_sha256"])
    protocol = _digest(plan["protocol_sha256"])
    if _digest(report["configuration_sha256"]) != configuration:
        raise ValueError("configuration differs between plan and report")
    extensions = _extensions(plan["rvv_extensions"])
    if _extensions(report["rvv_extensions"]) != extensions:
        raise ValueError("RVV denominator differs from the planned extension set")
    planned = _cases(plan["cases"], {"id", "dtype", "workload_sha256", "output_sha256"})
    measured = _cases(report["cases"], {"id", "workload_sha256", "rvv", "matrix"})
    if planned.keys() != measured.keys():
        raise ValueError("measured case set differs from the planned case set")
    if {_name(row["dtype"]) for row in planned.values()} != {"int8", "bf16"}:
        raise ValueError("plan must cover both int8 and bf16, and no other data type")
    margins: list[Margin] = []
    for name, expected in planned.items():
        row = measured[name]
        if _digest(row["workload_sha256"]) != _digest(expected["workload_sha256"]):
            raise ValueError(f"workload differs for {name}")
        output = _digest(expected["output_sha256"])
        rvv_time, rvv_energy, rvv_receipt = _arm(row["rvv"], output)
        matrix_time, matrix_energy, matrix_receipt = _arm(row["matrix"], output)
        if rvv_receipt == matrix_receipt:
            raise ValueError(f"both arms name the same receipt for {name}")
        throughput = Fraction(rvv_time, matrix_time)
        energy = Fraction(rvv_energy, matrix_energy)
        margins.append(Margin(name, _name(expected["dtype"]), str(throughput), str(energy),
                              _band(throughput), energy > throughput))
    bands = {margin.band for margin in margins}
    band = ("below-band" if "below-band" in bands else
            "review-band" if "review-band" in bands else "clears-band")
    return Comparison(plan_hash, hashlib.sha256(report_blob).hexdigest(), configuration,
                      protocol, extensions, tuple(margins), band,
                      all(margin.wider_per_watt for margin in margins))
