#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The RVFI-DII rig: generate a DII stream, drive an executor, adjudicate, shrink.

This is the instrument the plan's §10 sentence *one CI runner diffing one trace
format across three executors* has been describing and has had nothing behind.
[vos/rvfi.py](vos/rvfi.py) is the wire format, [vos/vengine.py](vos/vengine.py)
is the engine, and this is the command line over them.

Eight commands, and three of them need no toolchain:

    protocol   the wire this rig speaks, where it meets the commit trace, and
               where it cannot: readable on the host, and reads nothing but
               the two modules that implement it
    handshake  negotiate with the curated emulator and report what it answered
    run        generate, drive, adjudicate against a seeded defect, and shrink
    bridge     drive with the commit trace on as well, and hold the packets
               against the records the same run wrote
    adapt      hold an RTL harness's frame (vos/rtltrace.py) against the golden
               commit trace of the same program, from two files
    carry      run the corpus on the golden model, re-encode each trace as the
               frame an RTL would have to write, and hold the adapter to it and
               to seeded field changes
    framesim   build the SystemVerilog frame writer (tools/rvfi-harness/) behind
               its bench and hold the frame it writes to the decoder
    bmc        print the bounded model-checking smoke this harness owes, with its
               instruction scope read out of the dialect table; it runs nothing

`protocol`, `adapt` and `bmc` answer on either lane. The other five run in the
guest, where the emulator and the pinned Verilator are:

    python tools/run.py testrig handshake
    python tools/run.py testrig run --count 400 --shrink
    python tools/run.py testrig bridge --template mixed
    python tools/run.py testrig carry
    python tools/run.py testrig framesim --corpus

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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import IO, cast

from vos import bmc, dialect, differential, env, rtltrace, rvfi, trace, vengine
from vos.cli import rtl

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
    digits = rvfi.address_digits(view)
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


def cmd_adapt(args: argparse.Namespace) -> int:
    """Hold an RTL frame against the golden commit trace of the same program.

    File-only, so it answers on either lane: the frame is what a Verilator
    harness wrote and the reference is what the emulator's `--trace-commit`
    wrote. A protocol failure is reported as one and never as a divergence, and
    agreement over a prefix is reported as incomplete.
    """
    try:
        frame = args.frame.read_text(encoding="utf-8", newline="")
        reference = args.reference.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read an input: {exc}", file=sys.stderr)
        return 1
    try:
        result = rtltrace.compare(reference, frame, context=args.context)
    except rtltrace.FrameError as exc:
        print(f"FAIL protocol: {args.frame}: {exc}")
        print("  a frame that breaks its protocol is not adjudicated, so this is no "
              "statement about either executor's behaviour")
        return 1

    print(f"frame            {args.frame} ({rtltrace.HEADER})")
    print(f"retirements      {result.retired}")
    print(f"reference        {result.reference} comparable records after removing "
          f"{result.elided.total}")
    print(f"elided           {result.elided.line()}")
    print(f"candidate        {result.candidate} records")
    print(f"verdict          {result.line()}")

    if not result.verdict.ok:
        _report_divergence(result.verdict)
        if result.verdict.divergence is not None:
            print("FAIL the RTL and the golden model disagree about the same program")
        else:
            print(f"FAIL {result.verdict.line()}")
        return 1
    if not result.complete:
        print("FAIL the two streams agree over a prefix and one of them does not end "
              "there, so the run is not a corpus-green comparison")
        return 1
    print(f"TOTAL the RTL frame and the golden commit trace agree over "
          f"{result.verdict.compared} records, both streams whole")
    return 0


@dataclass
class _Carry:
    """What `carry` measured over the corpus, accumulated.

    `refused` is the frame's structural gap, a property of the port; `broken` is a
    carriable member whose own re-encoding did not come back whole, which is a defect
    in the adapter. The seed tallies use the mutation vocabulary: a stillborn seed
    broke the frame's protocol and decided nothing about the comparison, a killed one
    was reported, and a survivor is the finding.
    """

    members: int = 0
    retirements: int = 0
    records: int = 0
    elided: rvfi.Elided = field(default_factory=rvfi.Elided)
    words: dict[str, set[int]] = field(default_factory=dict)
    families: dict[str, list[str]] = field(default_factory=dict)
    whole: list[str] = field(default_factory=list)
    refused: dict[str, dict[str, int]] = field(default_factory=dict)
    broken: list[str] = field(default_factory=list)
    golden: list[str] = field(default_factory=list)
    killed: dict[str, int] = field(default_factory=dict)
    stillborn: dict[str, int] = field(default_factory=dict)
    survived: dict[str, list[str]] = field(default_factory=dict)
    silent: dict[str, int] = field(default_factory=dict)


def _golden_trace(e: env.Environment, elf: Path, trace_path: Path,
                  timeout: int) -> tuple[list[str] | None, str]:
    """One corpus member on the golden emulator, with its commit trace in a file.

    The trace goes to a file of its own for the reason `vengine.spawn` gives: a
    record torn by a diagnostic on a shared descriptor reads as a divergence.
    """
    try:
        done = subprocess.run([str(e.simulator), "--config", str(e.profile),
                               "--trace-commit", "--trace-output", str(trace_path),
                               "--inst-limit", "1000000", str(elf)],
                              capture_output=True, text=True, errors="replace",
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, "no HTIF write within the timeout"
    try:
        lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return None, f"no commit trace: {exc}"
    said = done.stdout + done.stderr + "\n".join(lines)
    if "SUCCESS" not in said:
        return None, f"rc={done.returncode}, no HTIF success"
    return lines, ""


def _recorded_golden(e: env.Environment, corpus: differential.Corpus,
                     member: differential.Member, work: Path,
                     timeout: int) -> tuple[list[str] | None, str]:
    """A member's golden trace, held to the digest the manifest records for it.

    So what a caller re-encodes is the recorded golden run and not whatever this
    lane's emulator happens to write: a model that moved under the corpus is
    reported here rather than carried into a comparison as the reference.
    """
    elf = differential.assemble(corpus, member, work)
    lines, why = _golden_trace(e, elf, work / f"{member.name}.trace", timeout)
    if lines is None:
        return None, why
    normalized = trace.normalize_commit(lines)
    digest = trace.digest(normalized)
    if digest != member.digest:
        return None, (f"digest {digest} over {len(normalized)} records against the "
                      f"manifest's {member.digest}")
    return lines, ""


def family_rows() -> list[tuple[int, int, str]]:
    rows = []
    for row in dialect.TABLE.values():
        site = row.site.split(":")[0]
        name = (site.split("/extensions/")[1].split("/")[0] if "/extensions/" in site
                else site.rsplit("/", 1)[-1])
        rows.append((row.mask, row.word, name))
    return rows


def family(insn: int, rows: list[tuple[int, int, str]]) -> str:
    """The model directory whose `encdec` decodes `insn`, read off the dialect table.

    `V` names the vector family and so on; a word no row decodes is `unmatched`,
    which a trapping illegal word is. This is how the corpus-green scope is measured
    rather than read off the corpus's prose: a member that retires a word of a
    family the curated scalar core does not implement cannot pass on it.
    """
    found = sorted({name for mask, word, name in rows if insn & mask == word})
    return "+".join(found) if found else "unmatched"


def _spread(positions: list[int], count: int) -> list[int]:
    """Up to `count` positions from `positions`, evenly spaced and always the ends."""
    if len(positions) <= count:
        return positions
    if count == 1:
        return positions[:1]
    step = (len(positions) - 1) / (count - 1)
    return sorted({positions[round(i * step)] for i in range(count)})


def _seed_member(name: str, golden: list[str], retires: list[rtltrace.Retire],
                 elided: rvfi.Elided, sites: int, tally: _Carry) -> None:
    for seed in rtltrace.SEEDS:
        witnesses = [at for at in range(len(retires))
                     if rtltrace.seed(retires, at, seed.name) is not None]
        if not witnesses:
            tally.silent[seed.name] = tally.silent.get(seed.name, 0) + 1
            continue
        for at in _spread(witnesses, sites):
            seeded = rtltrace.seed(retires, at, seed.name)
            if seeded is None:
                continue
            try:
                decoded = rtltrace.decode(rtltrace.encode(seeded))
            except rtltrace.FrameError:
                tally.stillborn[seed.name] = tally.stillborn.get(seed.name, 0) + 1
                continue
            if rtltrace.compare_decoded(golden, decoded, elided).complete:
                tally.survived.setdefault(seed.name, []).append(f"{name}@{at}")
            else:
                tally.killed[seed.name] = tally.killed.get(seed.name, 0) + 1


def cmd_carry(args: argparse.Namespace) -> int:
    """Re-encode the corpus's golden traces as frames, and hold the adapter to them.

    Each member runs once on the golden emulator with its commit trace in a file;
    the trace is held against the manifest's digest, so what is re-encoded is the
    recorded golden run. `rtltrace.carry` then writes the frame an RTL harness would
    have to produce to say the same thing, naming each retirement no frame line can
    hold; a member with none must come back whole through encode, decode and the
    one adjudicator, and every seeded field change must then be reported.

    **The producer here is the golden model and never the RTL.** What this decides
    is how much of the corpus a frame can carry and that the adapter reports what
    it is seeded with over real record shapes. It is no statement about the core.
    """
    e = env.load()
    if (missing := _requirements(e)) is not None:
        print(missing, file=sys.stderr)
        return 1
    corpus = differential.load(e.root)
    wanted = set(args.member)
    members = [m for m in corpus.members if not wanted or m.name in wanted]
    if unknown := wanted - {m.name for m in members}:
        print(f"no such member: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 1

    out_dir = e.lane_root / "testrig-carry"
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = env.hold_lock(out_dir / "carry.log", "a frame-carrying run")
    tally = _Carry()
    rows = family_rows()
    seen: dict[int, str] = {}
    try:
        for member in members:
            tally.members += 1
            lines, why = _recorded_golden(e, corpus, member, out_dir, args.timeout)
            if lines is None:
                tally.golden.append(f"{member.name} ({why})")
                print(f"GOLDEN  {member.name}: {why}")
                continue
            golden, elided = rtltrace.view(lines)
            retires, refusals = rtltrace.carry(golden)
            decoded = rtltrace.decode(rtltrace.encode(retires))
            result = rtltrace.compare_decoded(golden, decoded, elided)
            for insn in {r.packet.insn for r in retires}:
                if insn not in seen:
                    seen[insn] = family(insn, rows)
            for name in sorted({seen[r.packet.insn] for r in retires}):
                tally.families.setdefault(name, []).append(member.name)
            tally.retirements += len(retires)
            tally.records += len(golden)
            tally.elided = rvfi.Elided(
                tally.elided.scr + elided.scr, tally.elided.csr + elided.csr,
                tally.elided.traps + elided.traps,
                tally.elided.extra_reads + elided.extra_reads,
                tally.elided.extra_writes + elided.extra_writes)
            reasons: dict[str, int] = {}
            for refusal in refusals:
                reasons[refusal.reason] = reasons.get(refusal.reason, 0) + 1
                tally.words.setdefault(refusal.reason, set()).add(refusal.insn)
            head = (f"{member.name}: {len(retires)} retirements, {len(golden)} records "
                    f"after eliding {elided.total}")
            if refusals:
                tally.refused[member.name] = reasons
                first = refusals[0]
                print(f"REFUSED {head}; {len(refusals)} retirement(s) no frame line holds "
                      f"({', '.join(f'{k} {v}' for k, v in sorted(reasons.items()))}), "
                      f"first at retirement {first.at}, pc {first.pc:#x}, insn "
                      f"{first.insn:08X}; verdict {result.line()}")
                continue
            if not result.complete:
                tally.broken.append(member.name)
                print(f"BROKEN  {head}; verdict {result.line()}")
                _report_divergence(result.verdict)
                continue
            tally.whole.append(member.name)
            print(f"WHOLE   {head}; {result.line()}")
            _seed_member(member.name, golden, decoded, elided, args.sites, tally)
    finally:
        lock.close()

    print(f"members          {tally.members}, {len(tally.whole)} carried whole, "
          f"{len(tally.refused)} refused, {len(tally.broken)} broken, "
          f"{len(tally.golden)} without a recorded golden run")
    print(f"records          {tally.records} in the frame's view over {tally.retirements} "
          f"retirements")
    print(f"elided           {tally.elided.line()}")
    for reason, what in rtltrace.REASONS.items():
        count = sum(r.get(reason, 0) for r in tally.refused.values())
        if count:
            words = ", ".join(f"{w:08X}" for w in sorted(tally.words.get(reason, set())))
            print(f"refused          {reason}: {count} ({what}); words {words}")
    # Which model family each member retires words of, so the scope a scalar core can
    # pass is measured: a family every member retires is named with its count alone.
    ran = tally.members - len(tally.golden)
    for name, holders in sorted(tally.families.items()):
        who = "" if len(holders) == ran else f": {', '.join(holders)}"
        print(f"family {name:<11} retired by {len(holders)} member(s){who}")
    for seed in rtltrace.SEEDS:
        killed = tally.killed.get(seed.name, 0)
        stillborn = tally.stillborn.get(seed.name, 0)
        survived = tally.survived.get(seed.name, [])
        print(f"seed {seed.name:<12} killed {killed}, stillborn {stillborn}, survived "
              f"{len(survived)}, no witness in {tally.silent.get(seed.name, 0)} member(s)"
              f"{': ' + ', '.join(survived[:5]) if survived else ''}")

    total_killed = sum(tally.killed.values())
    total_survived = sum(len(v) for v in tally.survived.values())
    total_stillborn = sum(tally.stillborn.values())
    if tally.golden or tally.broken or total_survived or total_stillborn or not tally.whole:
        print(f"FAIL {len(tally.golden)} golden run(s) missing, {len(tally.broken)} "
              f"carriable member(s) not whole, {total_survived} seed(s) survived, "
              f"{total_stillborn} stillborn, {len(tally.whole)} member(s) carried whole")
        return 1
    print(f"TOTAL {len(tally.whole)} of {tally.members} member(s) carried whole and "
          f"{total_killed} seeded field change(s) reported; {len(tally.refused)} member(s) "
          f"hold retirements no frame line can carry, which is the port's gap and not "
          f"the core's behaviour")
    return 0


def cmd_bmc(args: argparse.Namespace) -> int:
    """Print the bounded model-checking smoke this harness owes, and run nothing.

    File-only, like `protocol`: the plan is [vos/bmc.py](vos/bmc.py)'s and its
    instruction scope is read out of the dialect table here and now, so what prints
    is the plan the gate would run today. It exits nonzero only where the scope's
    classification and the dialect table disagree, which is a finding about the plan;
    that the smoke has not run is stated on every line that could be misread.
    """
    del args
    _rule("the predicate (R-15-094: bounded-depth evidence, the ground of no refinement)")
    print("  for the curated scalar core under a riscv-formal wrapper, with instruction")
    print("  and data memory responses unconstrained and reset held for the first cycle,")
    print("  no check below finds a counterexample within its depth, and the cover check")
    print("  reaches a retirement of the in-scope forms within the instruction depth")

    _rule("the checks, at their declared depths")
    for check in bmc.CHECKS:
        print(f"  {check.name:<9} {check.depth:>3}  {check.decides}")

    covered = bmc.scope()
    _rule(f"the instruction scope, read out of the dialect table ({len(covered)} forms)")
    print(f"  constructors {', '.join(sorted(bmc.SCOPE))}")
    for at in range(0, len(covered), 10):
        print(f"  {' '.join(covered[at:at + 10])}")

    _rule("excluded, and why riscv-formal's model cannot judge it here")
    for ctor, why in sorted(bmc.EXCLUDED.items()):
        print(f"  {ctor:<10} {why}")
    print("  and every constructor outside the base and M files: the capability, bit-")
    print("  manipulation, conditional, CSR, atomic, vector and FEC forms, which the")
    print("  RV64IM model the insn checks are scoped to does not judge")

    _rule("what it waits on")
    for name, what in bmc.INPUTS:
        print(f"  {name:<13} {what}")

    wrong = bmc.findings()
    for finding in wrong:
        print(f"FAIL {finding}")
    if wrong:
        return 1
    print("\nNOT RUN: this is the plan the smoke runs once the inputs above exist; no "
          "check has been run against any core.")
    return 0


# The testbench's stimulus word, field by field and most significant first, which is
# `stim_t` in tools/rvfi-harness/vos_rvfi_frame_tb.sv. The bench is the layout's
# owner; a copy that drifted from it would send every field to the wrong place, and
# `framesim` would report that as a frame that does not come back.
HARNESS_DIR = "tools/rvfi-harness"
HARNESS_SOURCES = (f"{HARNESS_DIR}/vos_rvfi_frame.sv", f"{HARNESS_DIR}/vos_rvfi_frame_tb.sv")
STIMULUS: tuple[tuple[str, int], ...] = (
    ("pad", 6), ("valid", 1), ("trap", 1), ("cause", 64), ("pc_rdata", 64),
    ("pc_wdata", 64), ("insn", 32), ("rd_addr", 5), ("rd_tag", 1), ("rd_bits", 64),
    ("mem_addr", 64), ("mem_rmask", 8), ("mem_wmask", 8), ("mem_rtag", 1),
    ("mem_wtag", 1), ("mem_rdata", 64), ("mem_wdata", 64))
STIMULUS_BITS = 512


@dataclass(frozen=True)
class Drive:
    """One stimulus line: a retirement, a stale cause the port presents, or an idle cycle."""

    retire: rtltrace.Retire | None
    stale_cause: int = 0


def stimulus_line(drive: Drive) -> str:
    """One `stim_t` word as the 128 hexadecimal digits `$readmemh` reads."""
    values = dict.fromkeys((name for name, _ in STIMULUS), 0)
    if drive.retire is not None:
        packet = drive.retire.packet
        read = rvfi.mask_access(packet.mem_rmask)
        write = rvfi.mask_access(packet.mem_wmask)
        values.update(
            valid=int(not packet.trap), trap=packet.trap,
            cause=drive.retire.cause if packet.trap else drive.stale_cause,
            pc_rdata=packet.pc_rdata, pc_wdata=packet.pc_wdata, insn=packet.insn,
            rd_addr=packet.rd_addr, rd_tag=int(packet.rd_tag), rd_bits=packet.rd_wdata,
            mem_addr=packet.mem_addr,
            mem_rmask=0 if read is None else (1 << read[0]) - 1,
            mem_wmask=0 if write is None else (1 << write[0]) - 1,
            mem_rtag=0 if read is None else int(read[1]),
            mem_wtag=0 if write is None else int(write[1]),
            mem_rdata=packet.mem_rdata, mem_wdata=packet.mem_wdata)
    word = 0
    for name, width in STIMULUS:
        if values[name] >> width:
            raise ValueError(f"stimulus field {name} {values[name]:#x} is wider than "
                             f"{width} bits")
        word = (word << width) | values[name]
    return f"{word:0{STIMULUS_BITS // 4}X}"


def _synthetic_drives() -> list[Drive]:
    """The bench's own fixture: every rule the writer applies, each with a witness.

    The two tagged encodings are values the golden model wrote into the corpus's
    commit traces, so the round trip is taken over capabilities the format produces
    rather than over bits chosen here.
    """
    base = rvfi.Execution(wire=rtltrace.WIRE, integer_present=True, memory_present=True)

    def at(order: int, pc: int, insn: int, **fields: int | bool) -> rtltrace.Retire:
        cause = int(fields.pop("cause", 0))
        return rtltrace.Retire(replace(base, order=order, pc_rdata=pc, pc_wdata=pc + 4,
                                       insn=insn, **fields), cause)

    return [
        Drive(at(0, 0x80000000, 0x00100293, rd_addr=5, rd_wdata=1)),
        Drive(None),
        Drive(at(1, 0x80000004, 0xFE12825B, rd_addr=9, rd_tag=True,
                  rd_wdata=0xC879000080008040)),
        Drive(at(2, 0x80000008, 0x0094B023, mem_addr=0x80008040, mem_wmask=0x1FF,
                  mem_wdata=0xC800000000000000)),
        Drive(at(3, 0x8000000C, 0x00042303, mem_addr=0x80008040, mem_rmask=0xF,
                  mem_rdata=0xFFFFFFFFFFFF0400, rd_addr=6, rd_wdata=0xFFFFFFFFFFFF0400)),
        Drive(at(4, 0x80000010, 0x00000013), stale_cause=5),
        Drive(at(5, 0x80000014, 0x00A4A3AF, mem_addr=0x80008048, mem_rmask=0x1FF,
                  mem_wmask=0xFF, mem_rdata=0xC879000080008040, mem_wdata=7, rd_addr=31,
                  rd_tag=True, rd_wdata=0xC879000080008040)),
        Drive(at(6, 0x80000018, 0x00050003, trap=1, cause=28)),
    ]


def _framesim_one(binary: Path, work: Path, name: str,
                  drives: list[Drive]) -> tuple[list[rtltrace.Retire] | None, str]:
    """One stimulus file through the built bench, and the frame it wrote, decoded."""
    stim = work / f"{name}.stim"
    frame = work / f"{name}.frame"
    stim.write_text("".join(stimulus_line(d) + "\n" for d in drives), encoding="ascii",
                    newline="\n")
    frame.unlink(missing_ok=True)
    done = subprocess.run([str(binary), f"+stimulus={stim}", f"+count={len(drives)}",
                           f"+frame={frame}"], capture_output=True, text=True,
                          errors="replace", check=False, cwd=work)
    if done.returncode:
        return None, f"the bench exited {done.returncode}: {(done.stdout + done.stderr)[-300:]}"
    try:
        return rtltrace.decode(frame.read_text(encoding="utf-8", newline="")), ""
    except (OSError, rtltrace.FrameError) as exc:
        return None, f"the frame the writer wrote is refused: {exc}"


def cmd_framesim(args: argparse.Namespace) -> int:
    """Build the SystemVerilog frame writer behind its bench and decode what it writes.

    The bench is driven from Python-written stimulus, so the expected retirements
    are stated once and the frame has to come back as exactly those: the writer's
    field widths, its order count, its trailer, the x0 and stale-cause rules, and
    the register-form round trip through the authored format package. With
    `--corpus` every member `carry` can hold whole is driven as well, from its
    golden trace, and the frame the writer returns must then agree with that trace
    through the one adjudicator. The producer is a fixture driver, so this is a
    statement about the writer and the package, not about the core.
    """
    e = env.load()
    root = e.root
    work = e.lane_root / "rvfi-harness"
    work.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    verilator = rtl._require_verilator(out)
    if verilator is None:
        print("\n".join(out))
        return 1
    lock = env.hold_lock(work / "framesim.log", "a frame-writer simulation")
    try:
        sources = (rtl.FORMAT_PACKAGE, rtl.ADAPTER_PACKAGE, *HARNESS_SOURCES)
        built = subprocess.run(
            [verilator, "--binary", "--timescale", "1ns/1ps", "-Wall", "-Wno-UNUSEDPARAM",
             "-Wno-UNUSEDSIGNAL", "--Mdir", str(work / "obj_dir"), "-o", "framesim",
             "--top-module", "vos_rvfi_frame_tb", *(str(root / s) for s in sources)],
            capture_output=True, text=True, errors="replace", check=False, cwd=work)
        (work / "build.log").write_text(built.stdout + built.stderr, encoding="utf-8")
        if built.returncode:
            print(built.stdout + built.stderr)
            print(f"FAIL the frame writer does not build under Verilator; log "
                  f"{work / 'build.log'}")
            return 1
        warnings = sum(1 for line in (built.stdout + built.stderr).splitlines()
                       if line.startswith("%Warning"))
        binary = work / "obj_dir" / "framesim"

        drives = _synthetic_drives()
        want = [d.retire for d in drives if d.retire is not None]
        got, why = _framesim_one(binary, work, "synthetic", drives)
        if got is None or got != want:
            print(f"FAIL synthetic: {why or 'the frame came back different'}")
            for line in (f"  want {w}\n  got  {g}" for w, g in zip(want, got or [], strict=False)
                         if w != g):
                print(line)
            return 1
        print(f"ok synthetic: {len(got)} retirement(s) from {len(drives)} stimulus "
              f"line(s) came back field for field")

        failures = 0
        members = 0
        retired = 0
        if args.corpus:
            corpus = differential.load(root)
            for member in corpus.members:
                lines, why = _recorded_golden(e, corpus, member, work, args.timeout)
                if lines is None:
                    print(f"FAIL {member.name}: {why}")
                    failures += 1
                    continue
                golden, elided = rtltrace.view(lines)
                retires, refusals = rtltrace.carry(golden)
                if refusals:
                    print(f"skip {member.name}: {len(refusals)} retirement(s) no frame "
                          f"line holds")
                    continue
                got, why = _framesim_one(binary, work, member.name,
                                         [Drive(r) for r in retires])
                if got is None or got != retires:
                    first = next((i for i, (w, g) in enumerate(
                        zip(retires, got or [], strict=False)) if w != g), None)
                    print(f"FAIL {member.name}: {why or f'retirement {first} came back different'}")
                    if first is not None and got is not None:
                        print(f"  want {retires[first]}\n  got  {got[first]}")
                    failures += 1
                    continue
                result = rtltrace.compare_decoded(golden, got, elided)
                if not result.complete:
                    print(f"FAIL {member.name}: {result.line()}")
                    failures += 1
                    continue
                members += 1
                retired += len(retires)
                print(f"ok {member.name}: {len(retires)} retirement(s) through the writer, "
                      f"{result.line()}")
    finally:
        lock.close()

    print(f"verilator        {rtl.VERILATOR_PIN}, {warnings} warning line(s) under -Wall")
    if failures:
        print(f"FAIL {failures} member(s) did not come back whole through the writer")
        return 1
    corpus_part = (f" and {members} corpus member(s) over {retired} retirements agree "
                   f"whole" if args.corpus else "")
    print(f"TOTAL the writer's frames decode as stated{corpus_part}; the driver is a "
          f"fixture, so nothing here is about the core")
    return 0


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

    adapt = sub.add_parser("adapt", help="hold an RTL frame against the golden commit "
                           "trace of the same program")
    adapt.add_argument("frame", type=Path, help=f"the RTL harness's `{rtltrace.FORMAT}` frame")
    adapt.add_argument("reference", type=Path,
                       help="the emulator's commit trace of the same program")
    adapt.add_argument("--context", type=int, default=4,
                       help="records of agreement to print before a divergence")
    adapt.set_defaults(run=cmd_adapt)

    carry = sub.add_parser("carry", help="re-encode the corpus's golden traces as frames "
                           "and hold the adapter to them and to seeded changes")
    carry.add_argument("member", nargs="*", help="corpus members to run (default: all)")
    carry.add_argument("--sites", type=int, default=4,
                       help="retirements per seed per member to seed at")
    carry.add_argument("--timeout", type=int, default=120,
                       help="seconds one member may run on the emulator")
    carry.set_defaults(run=cmd_carry)

    framesim = sub.add_parser("framesim", help="build the SystemVerilog frame writer and "
                              "hold what it writes to the decoder")
    framesim.add_argument("--corpus", action="store_true",
                          help="also drive every member carry holds whole, from its "
                               "golden trace")
    framesim.add_argument("--timeout", type=int, default=120,
                          help="seconds one member may run on the emulator")
    framesim.set_defaults(run=cmd_framesim)

    sub.add_parser("bmc", help="the bounded model-checking smoke this harness owes, as a "
                   "plan; runs nothing").set_defaults(run=cmd_bmc)

    args = parser.parse_args(argv)
    # `set_defaults(run=...)` puts the handler on the namespace, where its type is
    # gone: named here so that a handler with the wrong shape is a finding rather
    # than a TypeError on whichever subcommand nobody ran lately.
    handler = cast("Command", args.run)
    return handler(args)

