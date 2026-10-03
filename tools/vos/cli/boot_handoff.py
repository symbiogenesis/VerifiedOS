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
table's permission column against the assembled image's constants, the
fixture's initialization descriptor against its layout, and the contract's chain
tables (section 9) against `firmware/chain/vos_chain.h`, the model's boot-control
door declarations and the RoT configuration, and prints the payload's
measurement; it needs no toolchain and answers on either lane.

A green run says the host-compiled stage, the selected signature binding and this
emulator agree over the listed cases. `--signature-scheme slh256s` binds the real
verifier, with disposable OpenSSL-generated signatures; the default fixture mode
is labeled separately. Neither says the RoT hart executes the stage or M4.4's
kernel accepts the handoff. Every report carries `milestone_acceptance: open`.

The `chain-` subcommands are M3.5b's target chain campaign (the contract's section 9):
`chain-stage` compiles the chain's units through the contained compiler, signs the
images with disposable keys kept in its output lane and writes `firmware/chain/target/`;
`chain-verify` holds that directory to its manifest, this checkout, the composers'
layouts and section 9.13's freeze; `chain-target --staged` executes one boot case, the
main-die group over `cold-boot`'s outputs or the watchdog group on the golden emulator
and writes a shard receipt; `chain-join` composes the shard receipts into one campaign.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from vos import (
    boot_chain,
    boot_chain_target,
    boot_handoff,
    boot_release_target,
    boot_target,
    env,
    receipts,
)
from vos.cli import Table, dispatch
from vos.corpus import find_root


def cmd_layout(args: argparse.Namespace) -> int:
    root = find_root()
    lay = boot_handoff.layout(root)
    built = boot_handoff.assemble_mmode(root)
    chain = boot_handoff.chain_layout(root)
    doors, door_findings = boot_handoff.door_declarations(root)
    findings = (boot_handoff.contract_findings(root)
                + boot_handoff.composition_findings(lay, built)
                + boot_handoff.entry_table_findings(root, built)
                + boot_handoff.chain_contract_findings(root)
                + boot_handoff.chain_layout_findings(root)
                + door_findings
                + boot_handoff.chain_case_findings(root))
    print(f"header {lay['BOOT_HEADER_BYTES']} bytes, signed prefix "
          f"{lay['BOOT_SIGNED_BYTES']}, record {lay['HANDOFF_BYTES']} bytes")
    print(f"payload {len(built.payload)} bytes from {lay['BRINGUP_MMODE_LOAD_BASE']:#x}, "
          f"shake256 {hashlib.shake_256(built.payload).hexdigest(32)}")
    print(f"kernel entry {built.symbols['kernel_entry']:#x}, "
          f"handoff record at {lay['BRINGUP_HANDOFF_BASE']:#x}")
    print(f"chain: stage-2 header {chain['CHAIN_KSTAGE_HEADER_BYTES']} bytes, capture "
          f"{chain['CHAIN_CAPTURE_BYTES']:#x} bytes, kernel stage at "
          f"{chain['CHAIN_KERNEL_LOAD_BASE']:#x}, {len(boot_handoff.chain_cases(root))} cases")
    # The doors are the model lane's to land; their absence is reported, never passed over.
    print(f"chain: boot-control doors: rot.sail declares {len(doors)} of "
          f"{len(boot_handoff.DOORS)}; the RoT configuration "
          f"{'declares' if boot_handoff.boot_control_declared(root) else 'lacks'} "
          "platform.boot_control")
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
        receipts.write(out / "progress.json", {"status": "incomplete", "cases": []})
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


_FAILURES = (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError,
             subprocess.SubprocessError)


def cmd_chain_stage(args: argparse.Namespace) -> int:
    e = env.load()
    out = Path(args.out) if args.out else e.lane_root / "boot-chain-stage"
    out.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(out, "boot chain staging"):
        receipts.write(out / "stage.json", {"passed": False, "status": "incomplete"})
        try:
            result = boot_chain_target.stage(e.root, out, Path(args.ccomp), args.ccomp_arg)
        except _FAILURES as error:
            receipts.write(out / "stage.json", {"passed": False, "status": "failed", "error": str(error)})
            print(f"FAIL boot-handoff chain-stage: {error}")
            return 1
        receipts.write(out / "stage.json", result)
    print(f"ok boot-handoff chain-stage: {boot_chain.STAGED} written; receipt {out / 'stage.json'}; "
          f"private keys stay under {out / 'signing'}")
    return 0


def cmd_chain_verify(args: argparse.Namespace) -> int:
    try:
        found = boot_chain_target.verify(env.load(toolchain=False).root)
    except _FAILURES as error:
        print(f"FAIL boot-handoff chain-verify: {error}")
        return 1
    print(f"ok boot-handoff chain-verify: {len(found.streams)} staged streams and "
          f"{len(found.images)} signed images match {boot_chain.MANIFEST}, "
          f"{len(found.manifest['sources_sha256'])} source files, the composers' layouts and "
          "section 9.13's freeze")
    return 0


def cmd_chain_target(args: argparse.Namespace) -> int:
    e = env.load()
    out = Path(args.out) if args.out else e.lane_root / "boot-chain-target"
    out.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(out, "boot chain target"):
        failed = {"passed": False, "status": "failed", "milestone_acceptance": "open"}
        receipts.write(out / "report.json", {**failed, "status": "incomplete"})
        receipts.write(out / "progress.json", {"status": "incomplete", "cases": []})
        try:
            selection = boot_chain_target.selection_of(args.case, args.group)
            result = boot_chain_target.run(
                e.root, out, Path(args.simulator), Path(args.build_receipt), selection,
                timeouts=boot_chain_target.run_timeouts(args.timeout, args.main_timeout,
                                                        args.short_timeout),
                jobs=args.jobs, cold_boot=Path(args.cold_boot) if args.cold_boot else None)
        except _FAILURES as error:
            receipts.write(out / "report.json", {**failed, "error": str(error)})
            print(f"FAIL boot-handoff chain-target: {error}")
            return 1
        result["status"] = "passed" if result["passed"] else "failed"
        receipts.write(out / "report.json", result)
    for row in result["cases"]:
        endings = ", ".join(f"{run['run']} {run.get('ending', 'not run')}" for run in row["runs"])
        print(f"{'PASS' if row['passed'] else 'FAIL':<5} {row['case']:<28} {endings}")
        for problem in row["problems"]:
            print(f"      {problem}")
        for run in row["runs"]:
            for problem in run.get("problems", []):
                print(f"      {problem}")
    for name in result["unexecuted_cases"]:
        print(f"UNRUN {name}{': ' + result['blocked'] if result.get('blocked') else ''}")
    print(f"{'ok' if result['passed'] else 'FAIL'} boot-handoff chain-target: {out / 'report.json'}; "
          "milestone_acceptance: open")
    return 0 if result["passed"] else 1


def cmd_chain_join(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        reports = {name: json.loads(Path(name).read_text(encoding="utf-8")) for name in args.reports}
        digests = {name: receipts.digest(Path(name)) for name in args.reports}
        result = boot_chain.join(find_root(), reports, digests)
    except _FAILURES as error:
        receipts.write(out / "report.json", {"passed": False, "status": "failed", "error": str(error),
                                              "milestone_acceptance": "open"})
        print(f"FAIL boot-handoff chain-join: {error}")
        return 1
    receipts.write(out / "report.json", result)
    print(f"{'ok' if result['passed'] else 'FAIL'} boot-handoff chain-join: {out / 'report.json'}; "
          f"{len(result['cases'])} of {len(result['case_set'])} cases executed"
          + (f"; unexecuted: {', '.join(result['unexecuted_cases'])}" if result["unexecuted_cases"]
             else "") + "; milestone_acceptance: open")
    return 0 if result["passed"] else 1


TABLE: Table = {
    "layout": (cmd_layout, "the contract's tables and the image against vos_boot.h and vos_chain.h"),
    "run": (cmd_run, "every contract case through the RoT stage and the golden emulator"),
    "signature-target": (cmd_signature_target, "real SLH verification on the RoT profile"),
    "release-target": (cmd_release_target, "RoT target release and captured main-die handoff"),
    "chain-stage": (cmd_chain_stage, "compile, lay out and sign the target chain's staged inputs"),
    "chain-verify": (cmd_chain_verify, "hold the staged chain to its manifest, sources and freeze"),
    "chain-target": (cmd_chain_target, "run staged chain cases on the golden emulator"),
    "chain-join": (cmd_chain_join, "compose chain shard receipts into one campaign receipt"),
}


def _chain_flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name == "chain-join":
        sub.add_argument("--out", required=True, help="directory for the joined report.json")
        sub.add_argument("reports", nargs="+", help="chain shard report.json files")
        return
    if name == "chain-verify":
        return
    sub.add_argument("--out", help="native output directory")
    if name == "chain-stage":
        sub.add_argument("--ccomp", required=True, help="accepted contained compiler executable")
        sub.add_argument("--ccomp-arg", action="append", default=[], help="compiler option, repeatable")
        return
    sub.add_argument("--staged", action="store_true", required=True,
                     help=f"execute the staged inputs under {boot_chain.STAGED}, the only source")
    chosen = sub.add_mutually_exclusive_group(required=True)
    chosen.add_argument("--case", choices=[spec.name for spec in boot_chain.CASES],
                        help="one case of the contract's section 9.12")
    chosen.add_argument("--group", choices=sorted(boot_chain.GROUPS),
                        help="the main-die or the watchdog group")
    sub.add_argument("--cold-boot",
                     help="cold-boot's output directory, holding its report.json, R1 capture and "
                          "R2 response; main-die cases require it")
    sub.add_argument("--simulator", required=True, help="golden emulator")
    sub.add_argument("--build-receipt", required=True, help="successful matching model build receipt")
    sub.add_argument("--timeout", type=int, default=boot_chain_target.TIMEOUTS["boot"],
                     help="seconds each boot run may take")
    sub.add_argument("--main-timeout", type=int, default=boot_chain_target.TIMEOUTS["main"],
                     help="seconds each main-die run may take")
    sub.add_argument("--short-timeout", type=int, default=boot_chain_target.TIMEOUTS["short"],
                     help="seconds each service, runtime-only or control run may take")
    sub.add_argument("--jobs", type=int, choices=range(1, 7), default=1,
                     help="cases of the selection executed at once")


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name.startswith("chain-"):
        _chain_flags(name, sub)
        return
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
