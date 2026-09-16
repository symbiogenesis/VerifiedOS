# SPDX-License-Identifier: Apache-2.0
"""Extract a declared single-mode periodic schedule and check finite phase service."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos.jsonc import Json
from vos.phase_schedule import contract_bytes, extract
from vos.phase_service import check


def _write_contract(path: Path, inputs: tuple[Path, ...], raw: bytes) -> Path:
    output = path.resolve()
    if output in (source.resolve() for source in inputs):
        raise ValueError("output contract must not overwrite a source input")
    with output.open("xb") as stream:
        stream.write(raw)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py phase-schedule", description=__doc__)
    parser.add_argument("schedule", type=Path, help="phase-schedule-v1 JSON declaration")
    parser.add_argument("resources", type=Path, help="digest-bound phase-resources-v1 JSON")
    parser.add_argument("--json", action="store_true", help="emit the contract, trace and byte identities")
    parser.add_argument("--output-contract", type=Path, metavar="FILE",
                        help="write canonical contract JSON, including a refuted contract")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    report: dict[str, Json] = {
        "scope": "declared-single-mode-periodic-schedule",
        "target_comparison": "open",
        "open_because": ["instruction-stream and arbiter correspondence", "all initial and mode states",
                         "qualified memory and timing", "workload WCET, area and power evidence"],
        "schedule": str(args.schedule), "resources": str(args.resources),
    }
    try:
        schedule_raw = args.schedule.read_bytes()
        resources_raw = args.resources.read_bytes()
        report["schedule_sha256"] = hashlib.sha256(schedule_raw).hexdigest()
        report["resources_sha256"] = hashlib.sha256(resources_raw).hexdigest()
        extraction = extract(schedule_raw, resources_raw)
        result = check(extraction.contract)
        emitted = contract_bytes(extraction.contract)
        report.update(asdict(extraction))
        report["contract_sha256"] = hashlib.sha256(emitted).hexdigest()
        report["result"] = asdict(result)
        report["sources_sha256"] = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("tools/vos/phase_schedule.py", "tools/vos/cli/phase_schedule.py",
                         "tools/vos/phase_service.py", "docs/implementation/phase-service/schedule-input.md")
        }
        if args.output_contract is not None:
            output = _write_contract(args.output_contract, (args.schedule, args.resources), emitted)
            report["output_contract"] = str(output)
    except (OSError, TypeError, ValueError) as err:
        report["error"] = str(err)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"malformed schedule/resources or unavailable output: {err}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{extraction.name}: zero_wait={result.zero_wait}, states={result.states}, "
              f"drain={result.drain}, reason={result.reason}, trace={result.trace}")
        print("declared schedule only; target comparison open")
    return 0 if result.zero_wait else 1
