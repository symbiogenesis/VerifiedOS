# SPDX-License-Identifier: Apache-2.0
"""M3.5's boot-handoff harness: the RoT's measured release of the boot core.

`run` compiles the RoT stage for the host, reads the RoT's device inputs from the
golden emulator under the RoT composition, submits every case of the
[boot-handoff contract](../../../docs/implementation/contracts/boot-handoff.md)'s
table to the stage, and starts the golden emulator on the main-die composition from
the placed bytes of each release. It writes `report.json` beside the per-case files
and exits 0 only when every row matches the contract. `layout` checks the contract's
tables and the assembled image against `firmware/include/vos_boot.h` and prints the
payload's measurement; it needs no toolchain and answers on either lane.

A green run says the host-compiled stage, the fixture signature and this emulator
agree with the contract over the listed cases. It does not say the RoT hart executes
the stage, that any signature scheme verifies, or that M4.4's kernel accepts the
handoff, and every report carries `milestone_acceptance: open`.
"""

import argparse
import hashlib
import json
from pathlib import Path

from vos import boot_handoff, env
from vos.cli import Table, dispatch
from vos.corpus import find_root


def cmd_layout(args: argparse.Namespace) -> int:
    root = find_root()
    lay = boot_handoff.layout(root)
    built = boot_handoff.assemble_mmode(root)
    findings = (boot_handoff.contract_findings(root)
                + boot_handoff.composition_findings(lay, built))
    print(f"header {lay['BOOT_HEADER_BYTES']} bytes, signed prefix "
          f"{lay['BOOT_SIGNED_BYTES']}, record {lay['HANDOFF_BYTES']} bytes")
    print(f"payload {len(built.payload)} bytes from {lay['BRINGUP_MMODE_LOAD_BASE']:#x}, "
          f"shake256 {hashlib.shake_256(built.payload).hexdigest(32)}")
    print(f"kernel entry {built.symbols['kernel_entry']:#x}, "
          f"handoff record at {lay['BRINGUP_HANDOFF_BASE']:#x}")
    for finding in findings:
        print(f"FAIL {finding}")
    print("ok boot-handoff layout" if not findings else
          f"FAIL boot-handoff layout: {len(findings)} finding(s)")
    return 1 if findings else 0


def cmd_run(args: argparse.Namespace) -> int:
    e = env.load()
    if not e.simulator.is_file():
        print(f"no golden emulator at {e.simulator}; run `run.py model build` first")
        return 1
    out = Path(args.out) if args.out else e.lane_root / "boot-handoff"
    result = boot_handoff.run_harness(e.root, e.simulator, out, args.timeout)
    (out / "report.json").write_text(json.dumps(result.report, indent=2) + "\n",
                                     encoding="utf-8")
    for line in result.lines:
        tail = f"; forced past the RoT: {line.forced}" if line.forced is not None else ""
        state = "PASS" if not line.problems else "FAIL"
        print(f"{state:<5} {line.case:<32} {line.rot_verdict:<20} {line.emulator}{tail}")
        for problem in line.problems:
            print(f"      {problem}")
    for finding in result.findings:
        print(f"FAIL  {finding}")
    passed = sum(1 for line in result.lines if not line.problems)
    print(f"TOTAL pass={passed} fail={len(result.lines) - passed} of {len(result.lines)} "
          f"cases; rot executor: host-compiled stage; signature verifier: fixture; "
          f"milestone_acceptance: open; report {out / 'report.json'}")
    return 0 if result.ok else 1


TABLE: Table = {
    "layout": (cmd_layout, "the contract's tables and the image against vos_boot.h"),
    "run": (cmd_run, "every contract case through the RoT stage and the golden emulator"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name == "run":
        sub.add_argument("--out", help="output directory (default: the lane's boot-handoff/)")
        sub.add_argument("--timeout", type=int, default=60,
                         help="seconds allowed for each emulator run")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py boot-handoff")
