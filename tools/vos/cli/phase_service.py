# SPDX-License-Identifier: Apache-2.0
"""Exercise Q22e's synthetic phase-service predicate and counterexample traces."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos.phase_service import check, scenarios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    contracts = scenarios()
    results = {name: check(contract) for name, contract in contracts.items()}
    expected = {"restricted-arrivals", "independent-banks"}
    passed = all(result.zero_wait == (name in expected) for name, result in results.items())
    root = Path(__file__).resolve().parents[3]
    sources = ("tools/vos/phase_service.py", "tools/vos/cli/phase_service.py",
               "tools/tests/test_phase_service.py")
    report = {
        "scope": "synthetic-finite-phase-service", "passed": passed,
        "target_comparison": "open",
        "sources_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                           for name in sources},
        "cases": {name: {"contract": asdict(contracts[name]), **asdict(result)}
                  for name, result in results.items()},
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, result in results.items():
            print(f"{name}: zero_wait={result.zero_wait}, states={result.states}, "
                  f"trace={result.trace}, failure={result.failure}")
        print("synthetic predicate assessment only; target comparison remains open")
    return 0 if passed else 1
