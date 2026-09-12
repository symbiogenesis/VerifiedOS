# SPDX-License-Identifier: Apache-2.0
"""Exercise Q22e's synthetic phase-service predicate and counterexample traces.

With no argument the fixed synthetic scenarios run and the exit code says whether
each still decides as expected. `--contract FILE` checks one JSON contract instead
(`grants`, `arrivals`, and optionally `banks`, `refresh`, `paths`, shaped as the
`Contract` dataclass is), exiting 0 on zero wait, 1 on a refutation and 2 on a
malformed contract. Either way the receipt reads the composition's own `qualified`
and `frozen` flags: the target comparison stays open while any of them is false,
and while the emitted schedule has no artifact this tool could read at all.
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos import config
from vos.jsonc import Json, load
from vos.phase_service import Batch, Contract, Result, check, scenarios

CONFIG = "model/config/verifiedos.json"

# The coefficient owners the comparison waits on, each read at the flag the
# configuration keeps for it. The schedule R-11-017 emits is absent from this table
# because nothing yet carries it: its row is stated below as unreadable rather than
# read as false.
FLAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("first_class_qualified", ("memory", "classes", "first", "qualified")),
    ("second_class_qualified", ("memory", "classes", "second", "qualified")),
    ("timing_qualified", ("timing", "operations", "qualified")),
)

EXPECTED_ZERO_WAIT = frozenset({"restricted-arrivals", "independent-banks",
                                "refresh-quiet-window", "refresh-other-bank",
                                "path-equal", "path-other-hart"})


def _ints(node: Json, what: str) -> tuple[int, ...]:
    if not isinstance(node, list) or any(isinstance(x, bool) or not isinstance(x, int)
                                         for x in node):
        raise TypeError(f"{what} must be a list of integers")
    return tuple(x for x in node if isinstance(x, int))


def _batches(node: Json, what: str) -> tuple[Batch, ...]:
    if not isinstance(node, list):
        raise TypeError(f"{what} must be a list of request batches")
    batches: list[Batch] = []
    for batch in node:
        if not isinstance(batch, list):
            raise TypeError(f"{what} must be a list of request batches")
        batches.append(tuple(_ints(request, f"a request in {what}") for request in batch))
    return tuple(batches)


def load_contract(path: Path) -> Contract:
    """One contract out of a JSON file; a wrong shape is a `TypeError` and a wrong
    figure a `ValueError`, and the command reports either as malformed."""
    data = load(path)
    if not isinstance(data, dict):
        raise TypeError("a contract is a JSON object")
    arrivals = data.get("arrivals")
    if not isinstance(arrivals, list):
        raise TypeError("arrivals must list one alternative set per phase")
    banks = data.get("banks", 1)
    if isinstance(banks, bool) or not isinstance(banks, int):
        raise TypeError("banks must be an integer")
    return Contract(
        grants=_ints(data.get("grants"), "grants"),
        arrivals=tuple(_batches(phase, "an arrival phase") for phase in arrivals),
        banks=banks,
        refresh=_batches(data.get("refresh", []), "refresh"),
        paths=_ints(data.get("paths", []), "paths"),
    )


def inputs(root: Path) -> dict[str, Json]:
    """What the composition says about the coefficients, flag by flag.

    A flag reads `true`, `false`, or `null` where the configuration does not carry
    it; every core class contributes its own `frozen` flag, because R-15-108's issue
    widths are selected per class. `schedule` is `null` on purpose: R-11-017's
    artifact does not exist, so there is nothing to read and no value to invent.
    """
    path = root / CONFIG
    flags: dict[str, Json] = {}
    for name, keys in FLAGS:
        found = config.value(path, *keys)
        flags[name] = found if isinstance(found, bool) else None
    classes = config.value(path, "platform", "core_classes")
    if isinstance(classes, dict):
        for name in classes:
            found = config.value(path, "platform", "core_classes", name, "frozen")
            flags[f"core_class_{name}_frozen"] = found if isinstance(found, bool) else None
    flags["schedule"] = None
    return flags


def open_because(flags: dict[str, Json]) -> list[str]:
    """The inputs that keep the target comparison open: every flag not read `true`."""
    return [name for name, value in flags.items() if value is not True]


def _receipt(root: Path, flags: dict[str, Json]) -> dict[str, Json]:
    sources = ("tools/vos/phase_service.py", "tools/vos/cli/phase_service.py",
               "tools/tests/test_phase_service.py")
    because: list[Json] = list(open_because(flags))
    digests: dict[str, Json] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in sources}
    return {
        "scope": "synthetic-finite-phase-service",
        "target_comparison": "open" if because else "evaluable",
        "open_because": because,
        "inputs": dict(flags),
        "sources_sha256": digests,
    }


def _case(contract: Contract, result: Result) -> Json:
    entry: dict[str, Json] = {"contract": asdict(contract)}
    entry.update(asdict(result))
    return entry


def _line(name: str, result: Result) -> str:
    return (f"{name}: zero_wait={result.zero_wait}, states={result.states}, "
            f"drain={result.drain}, trace={result.trace}, failure={result.failure}, "
            f"reason={result.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--contract", type=Path, metavar="FILE",
                        help="check this JSON contract instead of the fixed scenarios")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    flags = inputs(root)
    report = _receipt(root, flags)
    standing = ", ".join(open_because(flags))
    verdict = "open" if standing else "evaluable"
    if args.contract is not None:
        try:
            contract = load_contract(args.contract)
            result = check(contract)
        except (TypeError, ValueError) as err:
            if args.json:
                print(json.dumps({**report, "error": str(err)}, indent=2))
            else:
                print(f"malformed contract: {err}")
            return 2
        report["contract"] = str(args.contract)
        report["result"] = _case(contract, result)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(_line(args.contract.name, result))
            print(f"synthetic predicate over the supplied contract; target comparison "
                  f"{verdict}: {standing}")
        return 0 if result.zero_wait else 1
    contracts = scenarios()
    results = {name: check(contract) for name, contract in contracts.items()}
    passed = all(result.zero_wait == (name in EXPECTED_ZERO_WAIT)
                 for name, result in results.items())
    report["passed"] = passed
    report["cases"] = {name: _case(contracts[name], result)
                       for name, result in results.items()}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, result in results.items():
            print(_line(name, result))
        print(f"synthetic predicate assessment only; target comparison {verdict}: {standing}")
    return 0 if passed else 1
