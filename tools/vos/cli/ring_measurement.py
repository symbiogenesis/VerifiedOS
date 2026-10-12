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


def _evidence(report: dict[str, object]) -> None:
    for field in ("identity", "capture_sha256", "expected_identity_sha256",
                  "declaration_sha256", "sources_sha256"):
        if field in report:
            print(f"  {field}: {json.dumps(report[field], sort_keys=True)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py ring-measurement", description=__doc__)
    parser.add_argument("capture", type=Path, help="ring capture JSON under roster-measurement")
    parser.add_argument("--expected-identity", type=Path, required=True,
                        help="independent roster, image, composition and capture identities")
    parser.add_argument("--json", action="store_true", help="emit identities, accounting and exact rates")
    args = parser.parse_args(argv)
    root = corpus.find_root()
    report: dict[str, object] = {"scope": SCOPE, "milestone_acceptance": "open"}
    try:
        result = analyze(args.capture.read_bytes(), args.expected_identity.read_bytes(), root)
        sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in ("tools/vos/ring_measurement.py", "tools/vos/jsonutil.py",
                                "tools/vos/cli/ring_measurement.py",
                                "tools/vos/cli/ring.py", "docs/implementation/contracts/roster-measurement.md")}
        report.update({"identity": result.identity, "capture_sha256": result.capture_sha256,
                       "expected_identity_sha256": result.expected_identity_sha256,
                       "declaration_sha256": result.declaration_sha256, "sources_sha256": sources})
        # Decodable observations can sum or multiply into an exact value beyond
        # the interpreter's decimal conversion limit. Check the entire report
        # before publishing either a success line or partial measurements.
        try:
            rendered = json.dumps({**asdict(result), "sources_sha256": sources}, indent=2)
        except ValueError as error:
            raise ValueError(f"exact measurement report cannot be encoded as JSON: {error}") from error
    except (OSError, ValueError, RecursionError) as error:
        report.update({"verdict": "malformed", "reason": str(error)})
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"FAIL ring-measurement: {_display(str(error))}; {SCOPE}; milestone acceptance open")
            _evidence(report)
        return 2
    if args.json:
        print(rendered)
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
        _evidence(report)
    return 1 if result.findings else 0
