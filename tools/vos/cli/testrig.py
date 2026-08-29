#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The RVFI-DII rig: generate a DII stream, drive an executor, adjudicate, shrink.

This is the instrument the plan's §10 sentence *one CI runner diffing one trace
format across three executors* has been describing and has had nothing behind.
[vos/rvfi.py](vos/rvfi.py) is the wire format, [vos/vengine.py](vos/vengine.py)
is the engine, and this is the command line over them.

Four commands, and only the first needs no toolchain:

    protocol   the wire this rig speaks, where it meets the commit trace, and
               where it cannot: readable on the host, and reads nothing but
               the two modules that implement it
    handshake  negotiate with the curated emulator and report what it answered
    run        generate, drive, adjudicate against a seeded defect, and shrink
    bridge     drive with the commit trace on as well, and hold the packets
               against the records the same run wrote

The last three need a built emulator, so they run where it is:

    python tools/run.py testrig handshake
    python tools/run.py testrig run --count 400 --shrink
    python tools/run.py testrig bridge --template mixed

**`run` is a mutation gate and not a fuzzer.** A defect is seeded into the
second executor and the rig has to report it: a run that finds nothing is a
finding, exactly as a checker rule that says nothing about its own mutant is.
`--defect none` is the other arm, where the second executor is the first and
agreement is what is owed.
"""

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import IO, cast

from vos import env, rvfi, trace, vengine

type Command = Callable[[argparse.Namespace], int]

NO_DEFECT = "none"


def _rule(title: str) -> None:
    print(f"\n=== {title} ===")


def cmd_protocol(args: argparse.Namespace) -> int:
    """Print the wire this rig speaks and where the two formats meet.

    Everything below is read off the two modules that implement it rather than
    written down a second time, so a field that moves moves here as well.
    """
    _rule("RVFI-DII, the instruction packet the engine sends")
    print(f"  {rvfi.DII_BYTES} bytes, little-endian: "
          f"[0-3] insn, [4-5] time, [6] cmd, [7] padding")
    print(f"  cmd {rvfi.CMD_END_OF_TRACE} EndOfTrace   reset registers, memory and the "
          f"PC to {vengine.ENTRY:#x}")
    print(f"  cmd {rvfi.CMD_INSTRUCTION} Instruction  execute the word in insn")
    print(f"  cmd {rvfi.CMD_SET_VERSION:#x} '{chr(rvfi.CMD_SET_VERSION)}'  select the wire "
          f"format, acknowledged by {rvfi.VERSION_REPLY!r} and the version")
    print(f"  an EndOfTrace carrying insn {rvfi.VERSION_PROBE:#x} 'VERS' is a version "
          f"probe: halt {rvfi.HALT_V1_ONLY} is v1 only, halt {rvfi.HALT_V2_CAPABLE} is v2")

    _rule("RVFI-DII, the execution packet the implementation returns")
    print(f"  v1  {rvfi.EXEC_V1_BYTES} bytes, one fixed structure")
    print(f"  v2  {rvfi.EXEC_V2_BYTES} bytes stating their own total, then "
          f"{rvfi.EXT_INTEGER_BYTES} bytes of {rvfi.MAGIC_INTEGER.decode()} and "
          f"{rvfi.EXT_MEMACCESS_BYTES} of {rvfi.MAGIC_MEMORY.decode()} where announced")
    print("  v1 cannot carry this profile's widening at all: it has no rd_tag field, "
          "and it truncates")
    print("  the 32-bit access masks to their byte halves, which is where the tag bit "
          "sits. Every")
    print("  loop here negotiates v2.")

    _rule("where the packet and the commit trace meet")
    for record, how in (
        ("I", "rvfi_order, rvfi_pc_rdata and rvfi_insn, one for one"),
        ("X", "rvfi_rd_addr, rvfi_rd_wdata and rvfi_rd_tag, where rd is not x0"),
        ("R", "rvfi_mem_addr, rvfi_mem_rdata and the byte run of rvfi_mem_rmask, "
              "with the tag one bit above it"),
        ("W", "the same three write fields, and the same tag bit"),
    ):
        print(f"  {record}  {how}")

    _rule("where they do not")
    for record, why in (
        ("S", "the packet has no field for the four capability registers outside the "
              "merged file; upstream declares the availability bit and implements no "
              "structure behind it"),
        ("C", "the same, for CSR writes"),
        ("T", "rvfi_trap is a boolean where the schema's record carries the cause"),
        ("R/W beyond the first",
         "the packet holds one memory access per instruction, so a block operation "
         "has no form in it: `rvfi_write` raises an internal error above sixteen "
         "bytes, which stops the emulator rather than narrowing the report"),
        ("order",
         "carried by both and compared by neither: it counts retires from a reset, "
         "so two executors entering differently disagree on it while agreeing on "
         "everything else"),
        ("rs1/rs2",
         "carried by the packet and never populated by this model, which fills the "
         "destination half of the integer extension and not the source half"),
    ):
        print(f"  {record:<21} {why}")

    _rule("the templates a stream is generated from")
    for template in vengine.TEMPLATES.values():
        print(f"  {template.name:<8} {template.what}")

    _rule("the defects a second executor is seeded with")
    for defect in vengine.DEFECTS.values():
        print(f"  {defect.name}")
        print(f"    is        {defect.what}")
        print(f"    needs     {defect.witness}")

    print("\nok protocol: the wire format above is what vos/rvfi.py encodes and decodes.")
    return 0


def _requirements(e: env.Environment) -> str | None:
    if not e.simulator.exists():
        return f"no simulator at {e.simulator}; run `run.py model build` first"
    if not e.profile.is_file():
        return f"no frozen profile at {e.profile}"
    return None


class _Run:
    """One emulator, one socket, and the log the emulator wrote while it ran.

    A class rather than a pair of functions because the three are one lifetime:
    the session is only meaningful while the child is alive, and the log is only
    complete once it is not.
    """

    def __init__(self, e: env.Environment, *, trace_commit: bool = False) -> None:
        self.log_path = e.log("testrig")
        self.trace_path = self.log_path.with_suffix(".trace")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # The lane's two output files are opened with `w`, so a second rig in
        # this lane would truncate the first's while the first is still writing
        # into it, and the bridge would then read a torn trace as a divergence.
        # The lock is taken before either is opened, for the reason a build's is:
        # a refused run must not damage the run it was refused in favour of.
        self._lock = env.hold_lock(self.log_path, "an RVFI-DII run")
        self._log: IO[bytes] = self.log_path.open("wb")
        self.port = vengine.free_port()
        self.child = vengine.spawn(e.simulator, e.profile, self.port, self._log,
                                   trace_output=self.trace_path if trace_commit else None)
        try:
            self.session = vengine.connect(self.port, self.child)
        except ConnectionError:
            self._reap()
            raise

    def _reap(self) -> None:
        try:
            self.child.wait(timeout=30)
        except subprocess.TimeoutExpired:       # a child that will not leave on EOF
            self.child.kill()
            self.child.wait()
        self._log.close()
        self._lock.close()

    def close(self) -> None:
        self.session.close()
        self._reap()

    def commit(self) -> list[str]:
        """The commit trace this run wrote, once it has gone. Read after `close`."""
        return self.trace_path.read_text(encoding="utf-8", errors="replace").splitlines()


def cmd_handshake(args: argparse.Namespace) -> int:
    """Negotiate with the curated emulator and report what it answered."""
    e = env.load()
    if (missing := _requirements(e)) is not None:
        print(missing, file=sys.stderr)
        return 1

    run = _Run(e)
    try:
        wire = run.session.negotiate()
        # One instruction, so that the handshake is shown to have produced a
        # conversation and not only a version number: `addi x5, x0, 1` retires,
        # writes one register, and touches no memory.
        probe = 0x00100293
        packets = run.session.drive([probe])
    finally:
        run.close()

    print(f"port             {run.port}")
    print(f"wire format      v{wire}")
    print(f"packets          {len(packets)}")
    for packet in packets:
        print(f"  pc {packet.pc_rdata:#018x} insn {packet.insn:#010x} "
              f"mode {packet.mode} ixl {packet.ixl}")
        for record in rvfi.records(packet):
            print(f"    {record}")
    print(f"log              {run.log_path}")

    if wire != 2:
        print("the implementation offered only wire format 1, which cannot carry the "
              "capability widening", file=sys.stderr)
        return 1
    if not packets:
        print("the implementation retired nothing", file=sys.stderr)
        return 1
    print("ok handshake: the emulator speaks RVFI-DII v2 and retires an injected "
          "instruction.")
    return 0


def _report_divergence(verdict: trace.Verdict) -> None:
    divergence = verdict.divergence
    if divergence is None:
        return
    for record in verdict.agreed:
        print(f"          agreed    : {record}")
    print(f"          reference : {divergence[0]}")
    print(f"          candidate : {divergence[1]}")


@dataclass
class _Campaign:
    """What a sweep of seeds has driven and what it decided, accumulated.

    The counts are what makes this a measurement rather than a demonstration:
    the repository's standard is that validation is generated wherever an oracle
    exists, and a generated run that does not say how much it generated has not
    met it.
    """

    seeds: int = 0
    instructions: int = 0
    compared: int = 0
    runs: int = 0
    reported: int = 0
    silent: list[int] = field(default_factory=list)
    spurious: list[int] = field(default_factory=list)


def cmd_run(args: argparse.Namespace) -> int:
    """Generate streams, drive them, adjudicate, and shrink the first divergence.

    One emulator serves the whole sweep: every stream ends with an `EndOfTrace`,
    which resets registers, memory and the PC, so a seed is not a continuation
    of the one before it and the process start is paid once.
    """
    e = env.load()
    if (missing := _requirements(e)) is not None:
        print(missing, file=sys.stderr)
        return 1
    if args.defect != NO_DEFECT and args.defect not in vengine.DEFECTS:
        print(f"no defect {args.defect!r}; there are "
              f"{', '.join(vengine.DEFECTS)} and {NO_DEFECT}", file=sys.stderr)
        return 1

    defect = None if args.defect == NO_DEFECT else vengine.DEFECTS[args.defect]
    tally = _Campaign()
    first: tuple[int, list[int], list[int], trace.Verdict] | None = None

    run = _Run(e)
    try:
        wire = run.session.negotiate()
        if wire != 2:
            print("the implementation offered only wire format 1", file=sys.stderr)
            return 1

        def verdict_for(candidate: Sequence[int]) -> trace.Verdict:
            tally.runs += 1
            reference = run.session.drive(candidate)
            second = reference if defect is None else vengine.seeded(reference, defect)
            return vengine.adjudicate(reference, second, context=args.context)

        for seed in range(args.seed, args.seed + args.seeds):
            stream = vengine.generate(args.template, seed, args.count)
            verdict = verdict_for(stream)
            tally.seeds += 1
            tally.instructions += len(stream)
            tally.compared += verdict.compared
            if verdict.ok:
                if defect is not None:
                    tally.silent.append(seed)
                continue
            if defect is None:
                tally.spurious.append(seed)
                if first is None:
                    first = (seed, stream, list(stream), verdict)
                continue
            tally.reported += 1
            if first is not None:
                continue
            shortest = list(stream)
            if args.shrink:
                # The shrinker's own run count is discarded: every run it makes
                # goes through `verdict_for`, which is where the campaign counts
                # them, and two counters of one quantity is the defect this
                # repository is built to catch.
                shortest, _spent = vengine.shrink(
                    stream, lambda candidate: not verdict_for(candidate).ok,
                    budget=args.budget)
                verdict = verdict_for(shortest)
            first = (seed, stream, shortest, verdict)
    finally:
        run.close()

    print(f"template         {args.template} ({vengine.TEMPLATES[args.template].what})")
    print(f"seeds            {args.seed} through {args.seed + args.seeds - 1}")
    print(f"second executor  {args.defect}"
          f"{'' if defect is None else ': ' + defect.what}")
    print(f"wire format      v{wire}")
    print(f"instructions     {tally.instructions} driven over {tally.seeds} streams")
    print(f"records          {tally.compared} compared")
    print(f"executor runs    {tally.runs}")

    if first is not None:
        seed, stream, shortest, verdict = first
        print(f"counterexample   seed {seed}, {len(shortest)} instructions"
              f"{f' shrunk from {len(stream)}' if args.shrink and defect else ''}")
        for at, word in enumerate(shortest):
            print(f"  [{at}] {word:08X}")
        _report_divergence(verdict)

    if defect is None:
        if not tally.spurious:
            print(f"TOTAL agree over {tally.compared} records of "
                  f"{tally.instructions} instructions, no defect seeded")
            return 0
        print(f"FAIL the reference disagreed with itself on "
              f"{len(tally.spurious)} seed(s), which is a rig defect")
        return 1

    if not tally.reported:
        print(f"FAIL the seeded defect `{defect.name}` went unreported over "
              f"{tally.compared} records: no stream carried a witness, which needs "
              f"{defect.witness}")
        return 1
    print(f"TOTAL the seeded defect `{defect.name}` is reported on "
          f"{tally.reported} of {tally.seeds} seeds, silent on "
          f"{len(tally.silent)} that carried no witness")
    return 0


def cmd_bridge(args: argparse.Namespace) -> int:
    """Drive one run with both dialects on, and hold them against each other.

    The two callback classes are independent, so one run emits RVFI packets over
    the socket and commit records into the log at the same time. That is the
    only place the two formats can be compared without a second run to align
    against, and it is what makes the field-by-field meeting a measurement
    rather than a reading of two documents.
    """
    e = env.load()
    if (missing := _requirements(e)) is not None:
        print(missing, file=sys.stderr)
        return 1

    stream = vengine.generate(args.template, args.seed, args.count)
    run = _Run(e, trace_commit=True)
    try:
        wire = run.session.negotiate()
        packets = run.session.drive(stream)
    finally:
        run.close()

    commit = trace.normalize_commit(run.commit())
    view, elided = rvfi.packet_view(commit)
    digits = _address_digits(view)
    projected = vengine.project(packets, addr_digits=digits)
    verdict = trace.adjudicate(view, projected, args.context)

    print(f"template         {args.template}")
    print(f"stream           {len(stream)} instructions")
    print(f"wire format      v{wire}")
    print(f"packets          {len(packets)}")
    print(f"commit records   {len(commit)}")
    print(f"comparable       {len(view)} after removing {elided.total}")
    print(f"elided           {elided.line()}")
    print(f"address width    {digits} hexadecimal digits")
    print(f"verdict          {verdict.line()}")
    print(f"trace            {run.trace_path}")

    if not verdict.ok:
        _report_divergence(verdict)
        print("FAIL the packet and the record disagree about the same run, so one of "
              "the two emitters is wrong about a field both carry")
        return 1
    print(f"TOTAL the packet stream and the commit trace agree over "
          f"{verdict.compared} records of one run")
    return 0


def _address_digits(view: list[str]) -> int:
    """How wide a memory record writes its address, measured off the records.

    The commit trace prints the model's own physical-address width and the
    packet zero-extends to 64 bits, so the projection has to be rendered at
    whatever the run actually wrote. Measuring beats restating: the width is a
    property of the configuration, and a copy of it here would be a second place
    for it to be wrong.
    """
    for record in view:
        if record[0] in "RW":
            return len(record.split()[1])
    return rvfi.PHYSADDR_DIGITS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("protocol", help="the wire this rig speaks, and where the two "
                   "formats meet").set_defaults(run=cmd_protocol)

    sub.add_parser("handshake", help="negotiate with the emulator and report it"
                   ).set_defaults(run=cmd_handshake)

    def stream_args(target: argparse.ArgumentParser) -> None:
        target.add_argument("--template", default="mixed", choices=sorted(vengine.TEMPLATES),
                            help="what kind of stream to generate")
        target.add_argument("--seed", type=int, default=1, help="the generator's seed")
        target.add_argument("--count", type=int, default=200,
                            help="instructions after the template's preamble")
        target.add_argument("--context", type=int, default=4,
                            help="records of agreement to print before a divergence")

    run = sub.add_parser("run", help="generate, drive, adjudicate, and shrink")
    stream_args(run)
    run.add_argument("--defect", default="w-form-no-sext",
                     help=f"the defect the second executor carries, or {NO_DEFECT}")
    run.add_argument("--seeds", type=int, default=1,
                     help="how many consecutive seeds to sweep")
    run.add_argument("--shrink", action="store_true",
                     help="reduce the counterexample by delta debugging")
    run.add_argument("--budget", type=int, default=4000,
                     help="the most executor runs the shrinker may spend")
    run.set_defaults(run=cmd_run)

    bridge = sub.add_parser("bridge",
                            help="hold the packets against the commit records of one run")
    stream_args(bridge)
    bridge.set_defaults(run=cmd_bridge)

    args = parser.parse_args(argv)
    # `set_defaults(run=...)` puts the handler on the namespace, where its type is
    # gone: named here so that a handler with the wrong shape is a finding rather
    # than a TypeError on whichever subcommand nobody ran lately.
    handler = cast("Command", args.run)
    return handler(args)

