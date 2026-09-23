#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M4.4's kernel instance, held against the Gallina front: the C and the trace reader.

    python tools/run.py kernel vectors [--show N]
    python tools/run.py kernel check [--vectors FILE]
    python tools/run.py kernel mutants [--vectors FILE]
    python tools/run.py kernel reader --vectors FILE

[kernel/](../../../kernel/) is the GC-free C of one kernel instance, authored against
[PartitionContext.v](../../../proofs/PartitionContext.v),
[CyclicExecutive.v](../../../proofs/CyclicExecutive.v) and
[KernelInstance.v](../../../proofs/KernelInstance.v).
[KernelVectors.v](../../quickchick/KernelVectors.v) walks generated domains over those
statements' definitions and prints each point's inputs beside the definitions' answers.

`vectors` compiles that harness in the CertiRocq oracle's switch against its `Require`
closure only, not the whole proof tree. `check` compiles the kernel C in its host model
with the lane's C compiler and holds every `kx`, `kc`, `kr` and `kq` line against it,
then holds every `kt` line against [vos/kernelrun.py](../kernelrun.py), the reader
that asks KernelInstance.v's three questions of an emulator's commit trace.
`mutants` runs authored seeded defects through both differentials and reports them in
[vos/seeded.py](../seeded.py)'s vocabulary, which is the positive control: a
differential that no seeded defect can move is not evidence that the two sides agree.
`reader` runs only the reader half over a vector file already on disk, on either lane.

**What a green run means.** That the kernel C's host model and the reader compute what
the Gallina definitions compute at every generated point. It is not target evidence:
the C here was compiled by the lane's host compiler, not by the accepted purecap
backend, and no image ran on the emulator. The kernel's target build, its
initial-capability handoff and its corpus member remain M4.4's joins, and every
report says so.
"""

import argparse
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from unittest import mock

from vos import cli, env, gallina, kernelrun, proofs, seeded
from vos.corpus import find_root

HARNESS: Final = gallina.KERNEL
VECTORS: Final = "kernel-vectors.txt"
KERNEL: Final = "kernel"
SOURCES: Final[tuple[str, ...]] = ("src/executive.c", "src/context.c", "src/partition.c")
HOST_HARNESS: Final = "test/host_vectors.c"
CFLAGS: Final[tuple[str, ...]] = (
    "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-pedantic", "-DVOS_HOST_MODEL")
C_FAMILIES: Final[tuple[str, ...]] = ("kx", "kc", "kr", "kq")
READER_FAMILIES: Final[tuple[str, ...]] = ("c", "b", "f", "run")
WAITS: Final = ("target evidence waits on M1.2f's accepted backend, M1.7's target path "
                "and M3.5's handoff; milestone_acceptance: open")


# =====================================================================================
# The Gallina side
# =====================================================================================


def closure(work: Path, harness: Path) -> list[list[Path]]:
    """The harness's `Require` closure over the staged tree, in dependency order."""
    sources = sorted((work / gallina.PROOFS).glob("*.v"))
    sources += sorted((work / "harness").glob("*.v"))
    index = proofs.SourceIndex.read(sources)
    wanted = set(index.imports[harness]) | {harness}
    return [[s for s in wave if s in wanted] for wave in index.ordered
            if any(s in wanted for s in wave)]


def emit(root: Path, work: Path, out: list[str]) -> list[str] | None:
    """Stage, compile the harness's closure, and read the vectors it prints."""
    found = gallina.prover(gallina.ORACLE_SWITCH)
    if found is None:
        out.append(f"FAIL no prover in the {gallina.ORACLE_SWITCH} switch; "
                   "tools/wasm-oracle/README.md states how it is created")
        return None
    gallina.stage(root, work)
    harness = work / "harness" / HARNESS
    if not harness.is_file():
        out.append(f"FAIL there is no harness at {gallina.HARNESS_DIR}/{HARNESS}")
        return None
    for wave in closure(work, harness):
        for source in wave:
            if source == harness:
                continue
            done = gallina.compile_one(found, work, source)
            if done.returncode != 0:
                out.append(f"FAIL {source.name} did not compile:\n"
                           f"{(done.stderr or done.stdout).strip()}")
                return None
    lines, said = gallina.vectors(found, work, harness)
    if said:
        out.append(f"FAIL {HARNESS} did not run:\n{said}")
        return None
    out.append(f"   {gallina.version(found)} in the {gallina.ORACLE_SWITCH} switch")
    return lines


def _vectors_file(args: argparse.Namespace, root: Path, work: Path,
                  out: list[str]) -> Path | None:
    if args.vectors:
        path = Path(args.vectors)
        if not path.is_file():
            out.append(f"FAIL no vector file at {path}")
            return None
        out.append(f"   vectors read from {path}")
        return path
    lines = emit(root, work / "gallina", out)
    if lines is None:
        return None
    path = gallina.write(lines, work / VECTORS)
    out.append(f"   {len(lines)} vector(s) written to {path}")
    return path


# =====================================================================================
# The C side
# =====================================================================================


def c_compiler() -> str | None:
    return shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def build_host(kernel: Path, binary: Path, cc: str) -> subprocess.CompletedProcess[str]:
    """Compile the kernel sources and the host harness in the host model."""
    binary.parent.mkdir(parents=True, exist_ok=True)
    argv = [cc, *CFLAGS, "-I", str(kernel / "include"),
            *(str(kernel / s) for s in SOURCES), str(kernel / HOST_HARNESS),
            "-o", str(binary)]
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False)


def run_host(binary: Path, vectors: Path) -> subprocess.CompletedProcess[str]:
    with vectors.open("rb") as stdin:
        return subprocess.run([str(binary)], stdin=stdin, capture_output=True,
                              check=False, timeout=600, encoding="utf-8",
                              errors="replace")


_TOTAL_RE = re.compile(r"^FAIL (\d+) (?:disagreement|consumer check)", re.MULTILINE)


def disagreements_in(said: str) -> int:
    """The harness's own totals, which count every disagreement rather than the
    first few it prints."""
    return sum(int(n) for n in _TOTAL_RE.findall(said))


# =====================================================================================
# The reader side
# =====================================================================================


def reader_verdict(lines: list[str], out: list[str]) -> bool:
    """Hold the `kt` lines against the reader; True where every column agrees."""
    try:
        counts, found = kernelrun.check_vectors(lines)
    except (kernelrun.TraceError, ValueError) as err:
        out.append(f"FAIL the reader could not read a vector: {err}")
        return False
    out.append("   reader: " + "  ".join(f"kt {name} {count}" for name, count in counts.items()))
    empty = [name for name in READER_FAMILIES if counts.get(name, 0) == 0]
    out.extend(f"FAIL family kt {name} carried no line; an empty comparison decides nothing"
               for name in empty)
    out.extend(f"DIFFER kt {d.family} line {d.line} column {d.column}: "
               f"Gallina {int(d.gallina)}, reader {int(d.reader)}" for d in found[:20])
    if found:
        out.append(f"FAIL {len(found)} disagreement(s) between the reader and "
                   "KernelInstance.v")
    return not found and not empty


# =====================================================================================
# Commands
# =====================================================================================


def _lane_work() -> Path:
    e = env.load()
    return e.lane_root / KERNEL


def cmd_vectors(args: argparse.Namespace) -> int:
    """Emit the Gallina vectors and print a sample."""
    root = find_root()
    work = _lane_work()
    out: list[str] = [f"== {HARNESS} against its Require closure"]
    with env.hold_lock(work, "a kernel vector run"):
        lines = emit(root, work / "gallina", out)
        if lines is None:
            print("\n".join(out))
            return 1
        path = gallina.write(lines, work / VECTORS)
    out.append(f"   {len(lines)} vector(s) written to {path}")
    out.extend(f"     {line[:160]}" for line in lines[:args.show])
    out.append(f"ok the Gallina front answered {len(lines)} generated inputs")
    print("\n".join(out))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Both differentials over one vector file."""
    root = find_root()
    work = _lane_work()
    out: list[str] = ["== the kernel instance against the Gallina front"]
    with env.hold_lock(work, "a kernel vector run"):
        vectors = _vectors_file(args, root, work, out)
        if vectors is None:
            print("\n".join(out))
            return 1
        cc = c_compiler()
        c_ok = False
        if cc is None:
            out.append("FAIL no C compiler on this lane's PATH (cc, gcc or clang)")
        else:
            binary = work / "host_vectors"
            built = build_host(root / KERNEL, binary, cc)
            if built.returncode != 0:
                out.append(f"FAIL the kernel C did not compile under {cc}:\n"
                           f"{(built.stderr or built.stdout).strip()}")
            else:
                ran = run_host(binary, vectors)
                out.extend(f"   {line}" if not line.startswith(("ok", "FAIL")) else line
                           for line in ran.stdout.splitlines())
                c_ok = ran.returncode == 0
        lines = vectors.read_text(encoding="utf-8").splitlines()
        r_ok = reader_verdict(lines, out)
    out.append(f"   {WAITS}")
    if c_ok and r_ok:
        out.append("ok the kernel C and the trace reader agree with the Gallina front")
        print("\n".join(out))
        return 0
    print("\n".join(out))
    return 1


def cmd_reader(args: argparse.Namespace) -> int:
    """The reader half alone, over a vector file already on disk."""
    path = Path(args.vectors)
    out: list[str] = ["== the trace reader against KernelInstance.v"]
    if not path.is_file():
        print(f"FAIL no vector file at {path}")
        return 1
    ok = reader_verdict(path.read_text(encoding="utf-8").splitlines(), out)
    if ok:
        out.append("ok the reader agrees with KernelInstance.v on every kt line")
    print("\n".join(out))
    return 0 if ok else 1


# --- seeded defects -------------------------------------------------------------------


@dataclass(frozen=True)
class CMutant:
    """One authored defect in the kernel C: a file, the text it replaces, the text it
    writes, and the construction the replacement is."""

    name: str
    path: str
    old: str
    new: str

    @property
    def what(self) -> str:
        return f"C {self.name} ({self.path})"


C_MUTANTS: Final[tuple[CMutant, ...]] = (
    CMutant("restore truncated to the low registers", "src/context.c",
            "for (r = 0; r < VOS_REGISTER_COUNT; r++) {\n    post->reg[r] = succ->reg[r];",
            "for (r = 0; r < 16u; r++) {\n    post->reg[r] = succ->reg[r];"),
    CMutant("restore dropping the validity tag", "src/context.c",
            "post->reg[r] = succ->reg[r];", "post->reg[r].value = succ->reg[r].value;"),
    CMutant("switch exempting a nameable CSR", "src/context.c",
            "    if (row->nameable) {", "    if (row->nameable && i != 0u) {"),
    CMutant("zeroize written as a restore", "src/context.c",
            "post->csr[i] = 0;", "post->csr[i] = succ->csr[i];"),
    CMutant("switch carrying a predecessor CSR", "src/context.c",
            "} else {\n        post->csr[i] = succ->csr[i];",
            "} else {\n        post->csr[i] = pre->csr[i];"),
    CMutant("static pending arm reading the whole file", "src/context.c",
            "return succ->pending & m->pending_static_mask;", "return succ->pending;"),
    CMutant("rotation omitting the restorable restore", "src/context.c",
            "if (row->nameable && !row->zeroized) {\n      post->csr[i] = succ->csr[i];",
            "if (row->nameable && !row->zeroized) {\n      post->csr[i] = pre->csr[i];"),
    CMutant("rotation ignoring R-07-037c's arm", "src/context.c",
            "if (m->rotation_swaps_pending) {", "if (0) {"),
    CMutant("filter ignoring the bitmap", "src/context.c",
            "return vos_cap_tag(c) && !vos_bitmap_marks(bm, vos_cap_base(c));",
            "return vos_cap_tag(c) && bm != 0;"),
    CMutant("sanitized check skipping register 1", "src/context.c",
            "for (r = 1u; r < VOS_REGISTER_COUNT; r++) {\n    if (vos_cap_tag",
            "for (r = 2u; r < VOS_REGISTER_COUNT; r++) {\n    if (vos_cap_tag"),
    CMutant("sanitized check stopping before register 31", "src/context.c",
            "for (r = 1u; r < VOS_REGISTER_COUNT; r++) {\n    if (vos_cap_tag",
            "for (r = 1u; r + 1u < VOS_REGISTER_COUNT; r++) {\n    if (vos_cap_tag"),
    CMutant("completion reading the epoch", "src/context.c",
            "&& c->loans_cancelled && c->device_boundary_reached;",
            "&& c->loans_cancelled && c->epoch_advanced;"),
    CMutant("completion omitting the loan condition", "src/context.c",
            "&& c->loans_cancelled && c->device_boundary_reached;",
            "&& c->device_boundary_reached;"),
    CMutant("slot interval closed at its end", "src/executive.c",
            "instant < s->offset + s->width", "instant <= s->offset + s->width"),
    CMutant("disjointness strict at the boundary", "src/executive.c",
            "if (s->offset + s->width <= t->offset) {", "if (s->offset + s->width < t->offset) {"),
    CMutant("in-frame check strict at the frame's end", "src/executive.c",
            "return s->offset + s->width <= major_frame;",
            "return s->offset + s->width < major_frame;"),
    CMutant("executive wrapping one entry late", "src/executive.c",
            "if (next >= f->slot_count) {", "if (next > f->slot_count) {"),
    CMutant("release ignoring the slot's offset", "src/executive.c",
            "e->frame_index * f->major_frame + f->slots[e->cursor].offset;",
            "e->frame_index * f->major_frame;"),
    CMutant("validation accepting overlapping slots", "src/executive.c",
            "if (!vos_frame_pairwise_disjoint(f)) {", "if (0) {"),
    CMutant("no planned-successor check", "src/partition.c",
            "if (p < 0 || !d->partitions[p].has_context) {", "if (p < 0) {"),
    CMutant("hart identity not checked", "src/partition.c",
            "if (d->hart_id != hart_id) {", "if (d->hart_id != hart_id && d == 0) {"),
    CMutant("switch text allowed inside a partition", "src/partition.c",
            "if (!vos_extent_separated(&d->switch_text, &d->partitions[a].text)) {",
            "if (0) {"),
)


def run_c_mutant(mutant: CMutant, kernel: Path, scratch: Path, vectors: Path,
                 cc: str) -> seeded.Verdict:
    source = (kernel / mutant.path).read_text(encoding="utf-8")
    if source.count(mutant.old) != 1:
        return seeded.Verdict(mutant, seeded.UNSEEDED,
                              f"the seed occurs {source.count(mutant.old)} times, not once")
    tree = scratch / "kernel"
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(kernel, tree)
    (tree / mutant.path).write_text(source.replace(mutant.old, mutant.new),
                                    encoding="utf-8", newline="\n")
    binary = scratch / "mutant"
    built = build_host(tree, binary, cc)
    if built.returncode != 0:
        return seeded.Verdict(mutant, seeded.STILLBORN, "did not compile")
    ran = run_host(binary, vectors)
    moved = disagreements_in(ran.stdout)
    if ran.returncode == 0:
        return seeded.Verdict(mutant, seeded.SURVIVED, "every line still agreed")
    if ran.returncode == 1 and moved:
        return seeded.Verdict(mutant, seeded.KILLED, f"{moved} disagreement(s) reported",
                              moved)
    return seeded.Verdict(mutant, seeded.KILLED,
                          f"harness exit {ran.returncode} with {moved} reported line(s)",
                          moved)


@dataclass(frozen=True)
class ReaderMutant:
    """One authored defect in the reader: the function it replaces and the
    construction the replacement is."""

    name: str
    attribute: str
    replacement: Callable[..., object]

    @property
    def what(self) -> str:
        return f"reader {self.name} ({self.attribute})"


def _first_write(register: int, burst: Sequence[kernelrun.Record]
                 ) -> tuple[int, int] | None:
    for kind, fields in burst:
        if kind == "X" and fields[0] == register:
            return (fields[1], fields[2])
    return None


def _truncated(succ: kernelrun.Image, burst: Sequence[kernelrun.Record]) -> bool:
    for register in range(1, 16):
        value, tag = succ.registers[register]
        if kernelrun.last_register_write(register, burst) != (int(tag), value):
            return False
    return True


def _tagless(succ: kernelrun.Image, burst: Sequence[kernelrun.Record]) -> bool:
    for register in range(1, kernelrun.REGISTER_COUNT):
        last = kernelrun.last_register_write(register, burst)
        if last is None or last[1] != succ.registers[register][0]:
            return False
    return True


def _exempting(roster: Sequence[kernelrun.CsrRow], succ: kernelrun.Image,
               burst: Sequence[kernelrun.Record], zero_word: int = 0) -> bool:
    for row in [r for r in roster if r.nameable][1:]:
        if kernelrun.last_csr_write(row.csr, burst) != kernelrun.csr_target(
                row, succ, zero_word):
            return False
    return True


def _late_result(register: int, records: Sequence[kernelrun.Record]) -> bool:
    for kind, fields in records:
        if kind == "X" and fields[0] == register:
            return fields[1] == 0
    return False


def _unordered(switch_text: kernelrun.Extent, frame: kernelrun.Frame,
               records: Sequence[kernelrun.Record]) -> bool:
    visits = kernelrun.slot_visits(kernelrun.sites(switch_text, frame, records))
    return sorted(visits, key=_extent_key) == sorted(frame.extents, key=_extent_key)


def _extent_key(extent: kernelrun.Extent) -> tuple[int, int]:
    return (extent.base, extent.top)


def _no_astray(switch_text: kernelrun.Extent, frame: kernelrun.Frame,
               records: Sequence[kernelrun.Record]) -> bool:
    visits = kernelrun.sites(switch_text, frame, records)
    return sum(1 for s in visits if s[0] == "switch") == len(frame.extents)


def _declared_multiplicity(switch_text: kernelrun.Extent, frame: kernelrun.Frame,
                           records: Sequence[kernelrun.Record]) -> bool:
    visits = kernelrun.slot_visits(kernelrun.sites(switch_text, frame, records))
    return all(visits.count(e) == frame.extents.count(e)
               for e in frame.extents[:frame.reserved])


def _registers_once(roster: Sequence[kernelrun.CsrRow],
                    burst: Sequence[kernelrun.Record]) -> bool:
    return all(sum(1 for kind, f in burst if kind == "X" and f[0] == register) == 1
               for register in range(1, kernelrun.REGISTER_COUNT))


def _any_csr(roster: Sequence[kernelrun.CsrRow],
             burst: Sequence[kernelrun.Record]) -> bool:
    return all(0 < f[0] < kernelrun.REGISTER_COUNT for kind, f in burst if kind == "X")


READER_MUTANTS: Final[tuple[ReaderMutant, ...]] = (
    ReaderMutant("restore truncated to the low registers accepted",
                 "register_burst_total", _truncated),
    ReaderMutant("validity tag not compared", "register_burst_total", _tagless),
    ReaderMutant("a nameable CSR exempted", "csr_burst_total", _exempting),
    ReaderMutant("the first write compared instead of the last", "last_register_write",
                 _first_write),
    ReaderMutant("attempt coverage not required", "attempts_cover", lambda w, a: True),
    ReaderMutant("a result after the next retire accepted", "next_result_untagged",
                 _late_result),
    ReaderMutant("slot order not compared", "switches_in_table_order", _unordered),
    ReaderMutant("a retire outside every extent ignored", "no_unnamed_switch", _no_astray),
    ReaderMutant("reserved visits counted against the whole table",
                 "reserved_entered_once", _declared_multiplicity),
    ReaderMutant("exactly-once blind to CSRs", "burst_writes_exactly_once", _registers_once),
    ReaderMutant("CSR names not read", "burst_carries_nothing_else", _any_csr),
    ReaderMutant("duplicate attempt sites admitted", "well_formed_attempts",
                 lambda a: all(0 < x.register < kernelrun.REGISTER_COUNT for x in a)),
)


def run_reader_mutant(mutant: ReaderMutant, lines: list[str]) -> seeded.Verdict:
    if not hasattr(kernelrun, mutant.attribute):
        return seeded.Verdict(mutant, seeded.UNSEEDED,
                              f"kernelrun has no attribute {mutant.attribute}")
    with mock.patch.object(kernelrun, mutant.attribute, mutant.replacement):
        try:
            _, found = kernelrun.check_vectors(lines)
        except (kernelrun.TraceError, ValueError) as err:
            return seeded.Verdict(mutant, seeded.KILLED, f"the reader raised: {err}")
    if found:
        return seeded.Verdict(mutant, seeded.KILLED,
                              f"{len(found)} disagreement(s), first at line {found[0].line} "
                              f"column {found[0].column}", len(found))
    return seeded.Verdict(mutant, seeded.SURVIVED, "every kt line still agreed")


def cmd_mutants(args: argparse.Namespace) -> int:
    """Every authored defect through its differential: the positive control."""
    root = find_root()
    work = _lane_work()
    out: list[str] = ["== seeded defects in the kernel C and the trace reader"]
    with env.hold_lock(work, "a kernel vector run"):
        vectors = _vectors_file(args, root, work, out)
        if vectors is None:
            print("\n".join(out))
            return 1
        cc = c_compiler()
        if cc is None:
            out.append("FAIL no C compiler on this lane's PATH (cc, gcc or clang)")
            print("\n".join(out))
            return 1
        lines = vectors.read_text(encoding="utf-8").splitlines()
        with tempfile.TemporaryDirectory(prefix="kernel-mutant-", dir=work) as scratch:
            verdicts = [run_c_mutant(c_mutant, root / KERNEL, Path(scratch), vectors, cc)
                        for c_mutant in C_MUTANTS]
        verdicts.extend(run_reader_mutant(r_mutant, lines) for r_mutant in READER_MUTANTS)
    scope = seeded.Scope(whole=len(verdicts), ran=len(verdicts))
    code = seeded.summarize(out, verdicts, "the kernel instance's authored defects",
                            "Gallina-vector", scope)
    print("\n".join(out))
    return code


COMMANDS: cli.Table = {
    "vectors": (cmd_vectors, "compile KernelVectors.v against its closure; print vectors"),
    "check": (cmd_check, "the kernel C and the trace reader against the vectors"),
    "mutants": (cmd_mutants, "authored defects through both differentials"),
    "reader": (cmd_reader, "the trace reader alone over a vector file on disk"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name == "vectors":
        sub.add_argument("--show", type=int, default=3, metavar="N",
                         help="print the first N vectors as a sample")
    if name in ("check", "mutants"):
        sub.add_argument("--vectors", metavar="FILE",
                         help="read this vector file instead of emitting one")
    if name == "reader":
        sub.add_argument("--vectors", metavar="FILE", required=True,
                         help="the vector file to read")


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, _flags, prog="run.py kernel")
