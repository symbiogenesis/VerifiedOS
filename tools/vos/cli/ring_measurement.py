# SPDX-License-Identifier: Apache-2.0
"""Compare supplied ring observations with their bound identities and declaration."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos import corpus
from vos.ring_measurement import SCOPE, analyze


def _display(value: str) -> str:
    """Escape capture text for terminals without changing structured identifiers."""
    return json.dumps(value, ensure_ascii=True)[1:-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py ring-measurement", description=__doc__)
    parser.add_argument("capture", type=Path, help="ring capture JSON under roster-measurement")
    parser.add_argument("--expected-identity", type=Path, required=True,
                        help="independent roster, image, composition and capture identities")
    parser.add_argument("--json", action="store_true", help="emit identities, accounting and exact rates")
    args = parser.parse_args(argv)
    root = corpus.find_root()
    try:
        result = analyze(args.capture.read_bytes(), args.expected_identity.read_bytes(), root)
        sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in ("tools/vos/ring_measurement.py", "tools/vos/cli/ring_measurement.py",
                                "tools/vos/cli/ring.py", "docs/implementation/contracts/roster-measurement.md")}
    except (OSError, ValueError, RecursionError) as error:
        if args.json:
            print(json.dumps({"verdict": "malformed", "reason": str(error),
                              "scope": SCOPE, "milestone_acceptance": "open"}, indent=2))
        else:
            print(f"FAIL ring-measurement: {_display(str(error))}; {SCOPE}; milestone acceptance open")
        return 2
    if args.json:
        print(json.dumps({**asdict(result), "sources_sha256": sources}, indent=2))
    else:
        print(f"{'FAIL' if result.findings else 'ok'} ring-measurement: {result.verdict}; "
              f"{SCOPE}; milestone acceptance open")
        for ring in result.rings:
            print(f"  {_display(ring.ring_id)}: queue {ring.queue_high_water}/{ring.capacity}, "
                  f"batch {ring.batch_high_water}/{ring.max_batch_size}, "
                  f"cost {ring.max_activation_cost}/{ring.slot_budget} declaration_units; "
                  f"unmeasured tail {ring.unmeasured_tail_ticks} ticks")
        for finding in result.findings:
            print(f"  {_display(finding)}")
    return 1 if result.findings else 0
