# SPDX-License-Identifier: Apache-2.0
"""Compare stock compiler assembly while masking only compartment-comment digits."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos.assembly_compare import compare


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path, help="original baseline assembly")
    parser.add_argument("right", type=Path, help="original candidate assembly")
    parser.add_argument("--json", action="store_true", help="emit identities and pair verdict")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        left, right = args.left.read_bytes(), args.right.read_bytes()
        sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in ("tools/vos/assembly_compare.py",
                                "tools/vos/cli/assembly_compare.py",
                                "docs/implementation/compiler-assembly-comparison.md")}
    except OSError as err:
        if args.json:
            print(json.dumps({"verdict": "unsupported", "reason": str(err),
                              "milestone_acceptance": "open"}, indent=2))
        else:
            print(f"FAIL assembly-compare: unreadable input or contract: {err}")
        return 2
    result = compare(left, right)
    if args.json:
        print(json.dumps({"scope": "assembly-byte-pair", "milestone_acceptance": "open",
                          "sources_sha256": sources, **asdict(result)}, indent=2))
    else:
        print(f"{'ok' if result.exit_code == 0 else 'FAIL'} assembly-compare: "
              f"{result.verdict}: {result.reason}")
        print(f"  left: {result.left.sha256}; right: {result.right.sha256}")
        if result.first_difference is not None:
            print(f"  normalized byte {result.first_difference}, "
                  f"left line {result.left_line}, right line {result.right_line}")
        print("pair comparison only; compiler campaign acceptance remains open")
    return result.exit_code
