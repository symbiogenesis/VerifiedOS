# SPDX-License-Identifier: Apache-2.0
"""Per-coordinate controls for the reference component comparison."""

import json
from pathlib import Path

from tests.harness import Case, ensure
from vos import compiler_component as cc


def _population_and_wrappers() -> None:
    root = Path(__file__).resolve().parents[2]
    gallina = (root / "tools/wasm-oracle/ipc_oracle.v").read_text(encoding="utf-8")
    c_source = (root / "tools/wasm-oracle/ipc_oracle.c").read_text(encoding="utf-8")
    g, c, ids = cc.wrappers(gallina, c_source)
    ensure(bool(ids) and len(set(ids)) == len(ids), "nonempty unique source-owned population")
    ensure(g.replace("Compile Wasm ipc_checks.", "Compile Wasm ipc_oracle.") == gallina,
           "the Gallina wrapper changes only the observed definition")
    ensure("observed[k] = checks[k]" in c and "return (int)(k + 1)" in c,
           "the C wrapper serializes actual checks and preserves first failure")


def _every_coordinate_and_shape() -> None:
    root = Path(__file__).resolve().parents[2]
    ids = cc.population((root / "tools/wasm-oracle/ipc_oracle.v").read_text(encoding="utf-8"))
    good = cc.decode(cc.encode(ids, (True,) * len(ids), 0), ids)
    for index in range(len(ids)):
        values = [True] * len(ids)
        values[index] = False
        altered = cc.decode(cc.encode(ids, tuple(values), index + 1), ids)
        try:
            cc.compare(good, altered)
        except ValueError as err:
            ensure(str(index + 1) in str(err), "the first disagreement is localized")
        else:
            raise AssertionError(f"coordinate {index + 1} survived")
    canonical = cc.encode(ids, good.values, 0)
    for label in ("missing", "extra", "reordered", "non-Boolean", "first-failure", "truncated"):
        raw = json.loads(canonical)
        if label == "missing":
            raw["checks"].pop()
        elif label == "extra":
            raw["checks"].append(raw["checks"][0])
        elif label == "reordered":
            raw["checks"][0], raw["checks"][1] = raw["checks"][1], raw["checks"][0]
        elif label == "non-Boolean":
            raw["checks"][0][1] = 1
        elif label == "first-failure":
            raw["first_failure"] = 1
        text = json.dumps(raw) if label != "truncated" else canonical[:-1]
        try:
            cc.decode(text, ids)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{label} observation accepted")


def cases() -> list[Case]:
    return [Case("source-owned-component-wrappers", _population_and_wrappers),
            Case("component-coordinate-and-shape-refusals", _every_coordinate_and_shape)]
