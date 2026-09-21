# SPDX-License-Identifier: Apache-2.0
"""Extract a declared periodic schedule, single-mode or multi-mode, and check finite phase service.

A `phase-schedule-v1` declaration is one periodic table; a `phase-schedule-v2`
declaration is a set of modes with the transitions between them, checked as the
reachable product. `--completion` adds completion order and quiescent drain over
the same declaration. The emitted contract is the v1 table for a v1 or
single-mode declaration and the mode contract otherwise; the receipt binds the
emitted bytes either way.
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos import phase_completion, phase_modes
from vos.jsonc import Json
from vos.phase_schedule import contract_bytes
from vos.phase_service import check

SOURCES = ("tools/vos/phase_schedule.py", "tools/vos/cli/phase_schedule.py",
           "tools/vos/phase_service.py", "docs/implementation/phase-service/schedule-input.md")
MODE_SOURCES = ("tools/vos/phase_modes.py", "docs/implementation/phase-service/mode-contract.md")
COMPLETION_SOURCES = ("tools/vos/phase_completion.py",)


def _write_contract(path: Path, inputs: tuple[Path, ...], raw: bytes) -> Path:
    output = path.resolve()
    if output in (source.resolve() for source in inputs):
        raise ValueError("output contract must not overwrite a source input")
    with output.open("xb") as stream:
        stream.write(raw)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py phase-schedule", description=__doc__)
    parser.add_argument("schedule", type=Path,
                        help="phase-schedule-v1 or phase-schedule-v2 JSON declaration")
    parser.add_argument("resources", type=Path, help="digest-bound phase-resources-v1 JSON")
    parser.add_argument("--json", action="store_true", help="emit the contract, trace and byte identities")
    parser.add_argument("--completion", action="store_true",
                        help="also check completion order and total quiescent drain")
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
        extraction = phase_modes.read(schedule_raw, resources_raw)
        sources = SOURCES
        if isinstance(extraction, phase_modes.ModeExtraction):
            report["schema"] = phase_modes.SCHEMA
            if phase_modes.single_mode(extraction.contract) is None:
                report["scope"] = "declared-mode-product-periodic-schedule"
            result = phase_modes.check(extraction.contract)
            completion = (phase_modes.check_completion(extraction.contract)
                          if args.completion else None)
            emitted = phase_modes.emitted_bytes(extraction.contract)
            report.update(phase_modes.receipt(extraction))
            sources += MODE_SOURCES
        else:
            report["schema"] = "phase-schedule-v1"
            result = check(extraction.contract)
            completion = phase_completion.check(extraction.contract) if args.completion else None
            emitted = contract_bytes(extraction.contract)
            report.update(asdict(extraction))
        report["contract_sha256"] = hashlib.sha256(emitted).hexdigest()
        report["result"] = asdict(result)
        if completion is not None:
            report["completion"] = asdict(completion)
            sources += COMPLETION_SOURCES
        report["sources_sha256"] = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources
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
        if isinstance(result, phase_modes.ModeResult):
            print(f"modes: trace_modes={result.trace_modes}, mode_states={result.mode_states}, "
                  f"transitions_taken={result.transitions_taken}")
        if completion is not None:
            print(f"completion: ordered={completion.ordered}, "
                  f"quiescent_drain={completion.quiescent_drain}, "
                  f"drain_status={completion.drain_status}, reason={completion.reason}")
        print("declared schedule only; target comparison open")
    passed = result.zero_wait and (completion is None or completion.ordered is True)
    return 0 if passed else 1
