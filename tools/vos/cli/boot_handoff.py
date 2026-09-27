# SPDX-License-Identifier: Apache-2.0
"""M3.5's boot-handoff harness: the RoT's measured release of the boot core.

`run` compiles the RoT stage for the host, reads the RoT's device inputs from the
golden emulator under the RoT composition, submits every case of the
[boot-handoff contract](../../../docs/implementation/contracts/boot-handoff.md)'s
table to the stage, and starts the golden emulator on the main-die composition from
the placed bytes of each release. It writes `report.json` beside the per-case files
and exits 0 only when every row matches the contract. `layout` checks the contract's
header, record, composition and initialization-descriptor tables and its case table
against `firmware/include/vos_boot.h` and the harness's cases, the kernel-entry
table's permission column against the assembled image's constants, and the
fixture's initialization descriptor against its layout, and prints the payload's
measurement; it needs no toolchain and answers on either lane.

A green run says the host-compiled stage, the selected signature binding and this
emulator agree over the listed cases. `--signature-scheme slh256s` binds the real
verifier, with disposable OpenSSL-generated signatures; the default fixture mode
is labeled separately. Neither says the RoT hart executes the stage or M4.4's
kernel accepts the handoff. Every report carries `milestone_acceptance: open`.
"""

import argparse
import hashlib
import subprocess
from pathlib import Path

from vos import boot_handoff, boot_release_target, boot_target, env, receipts
from vos.cli import Table, dispatch
from vos.corpus import find_root


def cmd_layout(args: argparse.Namespace) -> int:
    root = find_root()
    lay = boot_handoff.layout(root)
    built = boot_handoff.assemble_mmode(root)
    findings = (boot_handoff.contract_findings(root)
                + boot_handoff.composition_findings(lay, built)
                + boot_handoff.entry_table_findings(root, built))
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
    out = Path(args.out) if args.out else e.lane_root / "boot-handoff"
    with env.hold_lock(out, "boot handoff"):
        return _run_handoff(args, e, out)


def _require_simulator(simulator: Path, explicit: bool, receipt: str | None) -> None:
    if explicit and not receipt:
        raise ValueError("an explicit simulator requires --build-receipt for its model sources")
    if not simulator.is_file():
        raise ValueError(f"no golden emulator at {simulator}; run `run.py model build` first")


def _run_handoff(args: argparse.Namespace, e: env.Environment, out: Path) -> int:
    simulator = Path(args.simulator) if args.simulator else e.simulator
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "report.json"
    receipts.write(report_path, {"status": "incomplete", "milestone_acceptance": "open",
                                "signature_scheme": args.signature_scheme})
    try:
        _require_simulator(simulator, bool(args.simulator), args.build_receipt)
        result = boot_handoff.run_harness(e.root, simulator, out, args.timeout,
                                          args.signature_scheme,
                                          Path(args.build_receipt) if args.build_receipt
                                          else e.log("model-build").with_suffix(".json"))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        receipts.write(report_path, {"status": "failed", "milestone_acceptance": "open",
                                    "signature_scheme": args.signature_scheme, "error": str(exc)})
        print(f"FAIL boot-handoff: {exc}")
        return 1
    result.report["status"] = "passed" if result.ok else "failed"
    receipts.write(report_path, result.report)
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
          f"cases; rot executor: host-compiled stage; signature verifier: {args.signature_scheme}; "
          f"milestone_acceptance: open; report {out / 'report.json'}")
    return 0 if result.ok else 1


def cmd_signature_target(args: argparse.Namespace) -> int:
    e = env.load()
    out = Path(args.out) if args.out else e.lane_root / "boot-signature-target"
    simulator = Path(args.simulator) if args.simulator else e.simulator
    with env.hold_lock(out, "boot signature target"):
        receipts.write(out / "report.json", {"status": "incomplete", "passed": False,
                                              "milestone_acceptance": "open"})
        try:
            result = boot_target.run(e.root, out, Path(args.ccomp), args.ccomp_arg, simulator,
                                      Path(args.build_receipt), Path(args.image),
                                      Path(args.public_key), args.timeout, args.inst_limit)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            receipts.write(out / "report.json", {"status": "failed", "passed": False,
                                                 "milestone_acceptance": "open", "error": str(exc)})
            print(f"FAIL boot signature target: {exc}")
            return 1
        result["status"] = "passed" if result["passed"] else "failed"
        receipts.write(out / "report.json", result)
    print(f"{'ok' if result['passed'] else 'FAIL'} boot signature target: {out / 'report.json'}; "
          "SLH callback on the RoT profile; milestone_acceptance: open")
    return 0 if result["passed"] else 1


def cmd_release_target(args: argparse.Namespace) -> int:
    e = env.load()
    out = Path(args.out) if args.out else e.lane_root / "boot-release-target"
    simulator = Path(args.simulator) if args.simulator else e.simulator
    with env.hold_lock(out, "boot release target"):
        receipts.write(out / "report.json", {"status": "incomplete", "passed": False,
                                              "milestone_acceptance": "open"})
        try:
            result = boot_release_target.run(e.root, out, Path(args.ccomp), args.ccomp_arg, simulator,
                                              Path(args.build_receipt), Path(args.image),
                                              Path(args.public_key), args.timeout, args.inst_limit)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            receipts.write(out / "report.json", {"status": "failed", "passed": False,
                                                 "milestone_acceptance": "open", "error": str(exc)})
            print(f"FAIL boot release target: {exc}")
            return 1
        result["status"] = "passed" if result["passed"] else "failed"
        receipts.write(out / "report.json", result)
    print(f"{'ok' if result['passed'] else 'FAIL'} boot release target: {out / 'report.json'}; "
          "RoT target release; milestone_acceptance: open")
    return 0 if result["passed"] else 1


TABLE: Table = {
    "layout": (cmd_layout, "the contract's tables and the image against vos_boot.h"),
    "run": (cmd_run, "every contract case through the RoT stage and the golden emulator"),
    "signature-target": (cmd_signature_target, "real SLH verification on the RoT profile"),
    "release-target": (cmd_release_target, "RoT target release and captured main-die handoff"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name in ("signature-target", "release-target"):
        sub.add_argument("--ccomp", required=True, help="accepted contained compiler executable")
        sub.add_argument("--ccomp-arg", action="append", default=[], help="compiler option, repeatable")
        sub.add_argument("--simulator", help="golden emulator (default: lane model build)")
        sub.add_argument("--build-receipt", required=True, help="successful matching model build receipt")
        sub.add_argument("--image", required=True, help="complete real-signed boot image")
        sub.add_argument("--public-key", required=True, help="exact raw SLH public-key file")
        sub.add_argument("--out", help="native output directory")
        sub.add_argument("--timeout", type=int, default=1200, help="seconds per target run")
        sub.add_argument("--inst-limit", type=int,
                         default=1_500_000_000 if name == "release-target" else 150_000_000,
                         help="instructions per target run")
    if name == "run":
        sub.add_argument("--out", help="output directory (default: the lane's boot-handoff/)")
        sub.add_argument("--timeout", type=int, default=60,
                         help="seconds allowed for each emulator run")
        sub.add_argument("--signature-scheme", choices=("fixture", "slh256s"), default="fixture",
                         help="fixture controls or real SLH-DSA-SHAKE-256s verification")
        sub.add_argument("--simulator", help="explicit golden emulator, requiring --build-receipt")
        sub.add_argument("--build-receipt", help="successful model build receipt binding the simulator")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py boot-handoff")
