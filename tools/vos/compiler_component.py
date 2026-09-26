# SPDX-License-Identifier: Apache-2.0
"""Ordered observations for the reference Gallina/authored-C comparison."""

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    values: tuple[bool, ...]
    first_failure: int


def families(source: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Read the closed cons/app vocabulary of the actual Gallina check owner."""
    source = re.sub(r"\(\*.*?\*\)", "", source, flags=re.DOTALL)
    rows = re.findall(r"Definition\s+(\w+_checks)\s*:\s*list bool\s*:=\s*(.*?)\.", source, re.DOTALL)
    definitions = dict(rows)
    if len(definitions) != len(rows):
        raise ValueError("duplicate check-family definition")
    if "ipc_checks" not in definitions:
        raise ValueError("missing IPC population owner")
    groups = re.findall(r"\b\w+_checks\b", definitions["ipc_checks"])
    if len(groups) != len(set(groups)) or set(groups) != set(definitions) - {"ipc_checks"}:
        raise ValueError("missing or duplicate check family")
    if re.sub(r"\b(?:app|\w+_checks)\b|[()\s]", "", definitions["ipc_checks"]):
        raise ValueError("unsupported IPC population expression")
    result: list[tuple[str, tuple[str, ...]]] = []
    for group in groups:
        body = definitions[group]
        checks = re.findall(r"\bc_\w+\b", body)
        if not checks or re.sub(r"\b(?:cons|nil|c_\w+)\b|[()\s]", "", body):
            raise ValueError(f"unsupported check family: {group}")
        result.append((group, tuple(checks)))
    identities = [name for _, checks in result for name in checks]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicated check identity")
    return tuple(result)


def population(source: str) -> tuple[str, ...]:
    return tuple(name for _, checks in families(source) for name in checks)


def encode(ids: tuple[str, ...], values: tuple[bool, ...], first: int) -> str:
    if len(ids) != len(values):
        raise ValueError("observation population length differs")
    return json.dumps({"schema": "vos-component-vector/1",
                       "checks": [[name, value] for name, value in zip(ids, values, strict=True)],
                       "first_failure": first}, separators=(",", ":"))


def decode(text: str, ids: tuple[str, ...]) -> Observation:
    """Reject malformed, incomplete and reordered records before comparison."""
    raw = json.loads(text)
    if (not isinstance(raw, dict) or set(raw) != {"schema", "checks", "first_failure"}
            or raw["schema"] != "vos-component-vector/1"):
        raise ValueError("unsupported component observation")
    checks = raw["checks"]
    if not isinstance(checks, list) or len(checks) != len(ids) or not ids:
        raise ValueError("component population length differs")
    values: list[bool] = []
    for i, (row, name) in enumerate(zip(checks, ids, strict=True), 1):
        if not isinstance(row, list) or len(row) != 2 or row[0] != name:
            raise ValueError(f"component identity/order differs at {i}")
        if type(row[1]) is not bool:
            raise ValueError(f"non-Boolean observation at {i}")
        values.append(row[1])
    first = next((i for i, value in enumerate(values, 1) if not value), 0)
    if type(raw["first_failure"]) is not int or raw["first_failure"] != first:
        raise ValueError("first failure disagrees with complete vector")
    return Observation(tuple(values), first)


def compare(left: Observation, right: Observation) -> None:
    if len(left.values) != len(right.values):
        raise ValueError("component vector lengths differ")
    for i, (a, b) in enumerate(zip(left.values, right.values, strict=True), 1):
        if a != b:
            raise ValueError(f"component value differs at {i}")
    if left.first_failure != right.first_failure:
        raise ValueError("component first failures differ")


def wrappers(gallina: str, c_source: str) -> tuple[str, str, tuple[str, ...]]:
    """Expose existing outputs without replacing a check or its implementation."""
    grouped = families(gallina)
    ids = tuple(name for _, checks in grouped for name in checks)
    old = "CertiRocq Compile Wasm ipc_oracle."
    if gallina.count(old) != 1:
        raise ValueError("missing or ambiguous Wasm observation boundary")
    observed_gallina = gallina.replace(old, "CertiRocq Compile Wasm ipc_checks.")
    if c_source.count("int main(void)") != 1:
        raise ValueError("missing or ambiguous C observation boundary")
    main = c_source.split("int main(void)", 1)[1]
    calls = re.findall(r"n\s*=\s*n\s*\+\s*(\w+_checks)\(checks\s*\+\s*n\);", main)
    if calls != [group for group, _ in grouped]:
        raise ValueError("C family order differs from Gallina population")
    bodies = dict(re.findall(r"static long (\w+_checks)\(long \*c\)\s*\{(.*?)(?=\nstatic long |\nint main|\Z)",
                             c_source, re.DOTALL))
    if set(bodies) != set(calls) or any(len(re.findall(r"\bn\s*\+\+", bodies[group])) != len(checks)
                                      for group, checks in grouped):
        raise ValueError("C family population differs from Gallina owner")
    count = re.findall(r"(?m)^#define CHECKS (\d+)\s*$", c_source)
    if count != [str(len(ids))]:
        raise ValueError("C population differs from Gallina owner")
    boundary = "    if (n != CHECKS)\n        return 255;\n"
    if c_source.count(boundary) != 1:
        raise ValueError("missing or ambiguous complete C population check")
    observed_c = c_source.replace("int main(void)", "int main(long *observed)")
    observed_c = observed_c.replace(boundary, boundary +
        "    for (k = 0; k < n; k++)\n        observed[k] = checks[k];\n"
        "    observed[n] = n;\n")
    return observed_gallina, observed_c, ids
