# SPDX-License-Identifier: Apache-2.0
"""Enumerate Q22b's bounded flat-policy qualification, with ideal trust primitives."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos import witness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, prog="run.py witness")
    parser.add_argument("command", choices=("qualify",))
    parser.add_argument("--max-n", type=int, default=6, choices=range(1, 7))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = witness.quorum_sweep(args.max_n)
    source = "tools/vos/witness.py"
    digest = hashlib.sha256(Path(witness.__file__).read_bytes()).hexdigest()
    if args.json:
        print(json.dumps({**asdict(result), "source": source, "source_sha256": digest,
                          "scope": "bounded enumeration with ideal authentication and storage; "
                          "policy theorem and production validator remain open"}, sort_keys=True))
    else:
        verdict = "FAIL" if result.disagreements else "ok"
        print(f"{verdict} flat-policy honest intersection: N=1..{result.max_n}, "
              f"{result.policies} policies, {result.assignments} quorum/fault assignments")
        for disagreement in result.disagreements:
            print(f"FAIL {disagreement}")
        print(f"model: {source} sha256 {digest}")
        print("scope: bounded enumeration; authentication and durable continuity are "
              "ideal assumptions; policy theorem and production validator remain open")
        print("state/transition qualification: run.py test --only witness")
    return 1 if result.disagreements else 0
