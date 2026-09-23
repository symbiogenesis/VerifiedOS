# SPDX-License-Identifier: Apache-2.0
"""M4.4's three trace questions, read off a commit trace.

[proofs/KernelInstance.v](../../proofs/KernelInstance.v) states what one run of one
kernel instance decides as decidable predicates over typed traces: the root is the
partition's (`RootIsThePartitions`), the switch is total (`SwitchIsTotal` with
`BurstWritesExactlyOnce`), and the frame is the table's (`FrameIsTheTables`), joined
as `RunAnswersM44`. This module is the reader a corpus run needs to ask them of the
emulator's actual trace, over the normalized record grammar of
[differential-corpus.md](../../docs/assurance/differential-corpus.md) section 4 that
[trace.py](trace.py) owns.

**It is a second statement of those predicates and is held to the first.**
[KernelVectors.v](../quickchick/KernelVectors.v) prints generated traces with the
Gallina definitions' verdicts beside them, and `run.py kernel check` holds every
verdict here against every verdict there. Each function below names the Gallina
definition it restates, and restates it clause for clause, including the ones a
reader would be tempted to improve: the last write to a register is the one compared,
a derivation's result is the first write to its declared register before the next
retire, and slot visits are identified by their tenant's declared text extent. Two
functions restate no Gallina definition and no vector holds them: `restore_bursts`
and `read_emulator_trace` are held only by the host cases in
[test_kernelrun.py](../tests/test_kernelrun.py).

**What the predicates do not say, and this reader therefore has to.** A corpus run is
one trace, and `RunAnswersM44` takes three: the confinement trace, one restore burst
and the frame trace. The confinement and frame questions read the whole trace. A
burst is cut here as the effect records under one maximal run of retires inside a
declared restore extent, which is a reading this module takes and states
(`restore_bursts`) rather than one KernelInstance.v fixes; the M4.4 member must
declare that extent, and which successor image each burst is held against.

Nothing here decodes a capability's bounds: a refusal is a cleared tag (R-15-007h),
as KernelInstance.v reading 1 requires.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from vos import trace

REGISTER_COUNT = 32  # R-15-007i; PartitionContext.v `register_count`

# One parsed record: the kind letter and its integer fields, in the schema's order.
# I: (pc, insn); X: (reg, tag, value); S: (scr, tag, value); C: (csr, value);
# R/W: (addr, width, tag, value); T: (interrupt, cause).
type Record = tuple[str, tuple[int, ...]]

# trace.normalize_commit drops an `I` record's order field and keeps every other
# record as the emulator spelled it, so a normalized `I` record is the one shape
# trace.COMMIT_RE no longer matches.
NORMALIZED_I_RE = re.compile(r"^I [0-9A-F]{16} [0-9A-F]{8}$")


class TraceError(ValueError):
    """A record outside the normalized commit-trace grammar."""


def parse_record(text: str) -> Record:
    """One normalized commit record: trace.py's grammar with the order dropped."""
    parts = text.split()
    kind = parts[0] if parts else ""
    if kind == "I":
        if NORMALIZED_I_RE.fullmatch(text) is None:
            raise TraceError(f"not a normalized `I` record: {text!r}")
        return kind, (int(parts[1], 16), int(parts[2], 16))
    if trace.COMMIT_RE.fullmatch(text) is None:
        raise TraceError(f"not a normalized commit record: {text!r}")
    if kind in ("X", "S"):
        return kind, (int(parts[1]), int(parts[2]), int(parts[3], 16))
    if kind == "C":
        return kind, (int(parts[1], 16), int(parts[2], 16))
    if kind in ("R", "W"):
        return kind, (int(parts[1], 16), int(parts[2]), int(parts[3]), int(parts[4], 16))
    return kind, (int(parts[1]), int(parts[2]))


def parse_records(lines: Iterable[str]) -> list[Record]:
    return [parse_record(line) for line in lines]


def read_emulator_trace(lines: Iterable[str]) -> list[Record]:
    """An emulator's `--trace-commit` output, normalized as the corpus runner
    normalizes it and then parsed."""
    return parse_records(trace.normalize_commit(list(lines)))


# =====================================================================================
# Declarations: what a run is read against (KernelInstance.v reading 8, gap f)
# =====================================================================================


@dataclass(frozen=True)
class Extent:
    """KernelInstance.v `Extent`: a declared half-open address range."""

    base: int
    top: int

    def within(self, address: int) -> bool:
        return self.base <= address < self.top

    def separated(self, other: Extent) -> bool:
        return self.top <= other.base or other.top <= self.base

    def compatible(self, other: Extent) -> bool:
        return self == other or self.separated(other)


@dataclass(frozen=True)
class Attempt:
    """KernelInstance.v `Attempt`: a declared over-bound derivation site."""

    pc: int
    register: int
    target: str  # "R" for the root's top, "W<j>" for shared window j


@dataclass(frozen=True)
class CsrRow:
    """One roster row: the CSR address and the profile's two dispositions."""

    csr: int
    nameable: bool
    zeroized: bool


@dataclass(frozen=True)
class Image:
    """A successor context's witnessed half: 32 (value, tag) registers and the
    roster CSRs' saved values."""

    registers: tuple[tuple[int, bool], ...]
    csrs: dict[int, int]


@dataclass(frozen=True)
class Frame:
    """The table as a reader needs it: each slot's tenant text extent in
    `frame_slots` order, and how many lead slots are the reserved band."""

    extents: tuple[Extent, ...]
    reserved: int


# =====================================================================================
# Question one: the root is the partition's
# =====================================================================================


def well_formed_attempts(attempts: Sequence[Attempt]) -> bool:
    """`WellFormedAttempts`: distinct sites, and a result register in 1..31."""
    pcs = [a.pc for a in attempts]
    return (len(set(pcs)) == len(pcs)
            and all(0 < a.register < REGISTER_COUNT for a in attempts))


def attempts_cover(window_count: int, attempts: Sequence[Attempt]) -> bool:
    """`AttemptsCover`: the root's top and each declared window's top."""
    targets = {a.target for a in attempts}
    return "R" in targets and all(f"W{j}" in targets for j in range(window_count))


def next_result_untagged(register: int, records: Sequence[Record]) -> bool:
    """`next_result_untagged`: the first write to the declared register before the
    next retire, read by its tag; no such write is no witness."""
    for kind, fields in records:
        if kind == "I":
            return False
        if kind == "X" and fields[0] == register:
            return fields[1] == 0
    return False


def refused_at(pc: int, register: int, records: Sequence[Record]) -> bool:
    """`refused_at`: at the first retire at the attempt's site."""
    for index, (kind, fields) in enumerate(records):
        if kind == "I" and fields[0] == pc:
            return next_result_untagged(register, records[index + 1:])
    return False


def root_is_the_partitions(window_count: int, attempts: Sequence[Attempt],
                           records: Sequence[Record]) -> bool:
    """`RootIsThePartitions`."""
    return (attempts_cover(window_count, attempts)
            and all(refused_at(a.pc, a.register, records) for a in attempts))


# =====================================================================================
# Question two: the switch is total
# =====================================================================================


def _observed() -> range:
    """`observed_registers`: the statement's 32 less the zero register, which the
    model records no write for (KernelInstance.v reading 3)."""
    return range(1, REGISTER_COUNT)


def last_register_write(register: int, burst: Sequence[Record]) -> tuple[int, int] | None:
    found = None
    for kind, fields in burst:
        if kind == "X" and fields[0] == register:
            found = (fields[1], fields[2])
    return found


def last_csr_write(csr: int, burst: Sequence[Record]) -> int | None:
    found = None
    for kind, fields in burst:
        if kind == "C" and fields[0] == csr:
            found = fields[1]
    return found


def _nameable(roster: Sequence[CsrRow], csr: int) -> bool:
    return any(row.csr == csr and row.nameable for row in roster)


def csr_target(row: CsrRow, succ: Image, zero_word: int = 0) -> int:
    """`csr_target`: zero where the bank zeroizes, the saved value where it restores."""
    return zero_word if row.zeroized else succ.csrs[row.csr]


def register_burst_total(succ: Image, burst: Sequence[Record]) -> bool:
    """`RegisterBurstTotal`: every witnessed register's last write is the
    successor's value and tag."""
    for register in _observed():
        last = last_register_write(register, burst)
        value, tag = succ.registers[register]
        if last is None or last != (int(tag), value):
            return False
    return True


def csr_burst_total(roster: Sequence[CsrRow], succ: Image, burst: Sequence[Record],
                    zero_word: int = 0) -> bool:
    """`CsrBurstTotal`: every nameable roster CSR's last write is its target."""
    for row in roster:
        if not row.nameable:
            continue
        last = last_csr_write(row.csr, burst)
        if last is None or last != csr_target(row, succ, zero_word):
            return False
    return True


def burst_carries_nothing_else(roster: Sequence[CsrRow], burst: Sequence[Record]) -> bool:
    """`BurstCarriesNothingElse`: no register write outside 1..31, and no CSR write
    the partition cannot name. A CSR outside the roster is not nameable, which is the
    roster's covering law read from the other side."""
    for kind, fields in burst:
        if kind == "X" and not 0 < fields[0] < REGISTER_COUNT:
            return False
        if kind == "C" and not _nameable(roster, fields[0]):
            return False
    return True


def switch_is_total(roster: Sequence[CsrRow], succ: Image, burst: Sequence[Record],
                    zero_word: int = 0) -> bool:
    """`SwitchIsTotal`."""
    return (register_burst_total(succ, burst)
            and csr_burst_total(roster, succ, burst, zero_word)
            and burst_carries_nothing_else(roster, burst))


def burst_writes_exactly_once(roster: Sequence[CsrRow], burst: Sequence[Record]) -> bool:
    """`BurstWritesExactlyOnce`: one write per witnessed register and per nameable
    roster CSR."""
    for register in _observed():
        if sum(1 for kind, f in burst if kind == "X" and f[0] == register) != 1:
            return False
    for row in roster:
        if row.nameable and sum(1 for kind, f in burst
                                if kind == "C" and f[0] == row.csr) != 1:
            return False
    return True


def restore_bursts(records: Sequence[Record], restore: Extent) -> list[list[Record]]:
    """The effect records under each maximal run of retires inside `restore`.

    This reader's own cut, not KernelInstance.v's: that file states the clause of a
    burst and does not say where a burst begins. A window from one slot boundary to
    the next holds the trap entry's save phase as well, and CHERI trap entry reaches
    its save area only through a general register, so over that whole window some
    register is necessarily written twice and `BurstWritesExactlyOnce` could not hold
    of any implementation. The member therefore declares its restore sequence's text.
    """
    bursts: list[list[Record]] = []
    current: list[Record] | None = None
    inside = False
    for kind, fields in records:
        if kind == "I":
            inside = restore.within(fields[0])
            if inside and current is None:
                current = []
            elif not inside and current is not None:
                bursts.append(current)
                current = None
            continue
        if inside and current is not None:
            current.append((kind, fields))
    if current is not None:
        bursts.append(current)
    return bursts


# =====================================================================================
# Question three: the frame is the table's
# =====================================================================================

# A site: ("switch",), ("slot", extent) or ("astray", pc).
type Site = tuple[str, object]


def site_of(switch_text: Extent, extents: Sequence[Extent], pc: int) -> Site:
    """`site_of`: the switch text first, then the first declared extent holding `pc`."""
    if switch_text.within(pc):
        return ("switch", None)
    for extent in extents:
        if extent.within(pc):
            return ("slot", extent)
    return ("astray", pc)


def sites(switch_text: Extent, frame: Frame, records: Sequence[Record]) -> list[Site]:
    """`sites`: maximal runs of retires at one site; dwell leaves the reading here."""
    out: list[Site] = []
    for kind, fields in records:
        if kind != "I":
            continue
        site = site_of(switch_text, frame.extents, fields[0])
        if not out or out[-1] != site:
            out.append(site)
    return out


def slot_visits(visits: Sequence[Site]) -> list[Extent]:
    return [site[1] for site in visits if site[0] == "slot"
            and isinstance(site[1], Extent)]


def extents_are_readable(switch_text: Extent, frame: Frame) -> bool:
    """`ExtentsAreReadable`."""
    extents = frame.extents
    return (all(a.compatible(b) for i, a in enumerate(extents) for b in extents[i + 1:])
            and all(switch_text.separated(e) for e in extents))


def reserved_entered_once(switch_text: Extent, frame: Frame,
                          records: Sequence[Record]) -> bool:
    """`ReservedEnteredOnce`, read by tenant text extent as the Gallina reads it."""
    visits = slot_visits(sites(switch_text, frame, records))
    reserved = frame.extents[:frame.reserved]
    return all(visits.count(e) == reserved.count(e) for e in reserved)


def switches_in_table_order(switch_text: Extent, frame: Frame,
                            records: Sequence[Record]) -> bool:
    """`SwitchesInTableOrder`: the slot visits are the table's list, in list order."""
    return slot_visits(sites(switch_text, frame, records)) == list(frame.extents)


def no_unnamed_switch(switch_text: Extent, frame: Frame, records: Sequence[Record]) -> bool:
    """`NoUnnamedSwitch`: one switch visit per table entry, and nothing astray."""
    visits = sites(switch_text, frame, records)
    return (sum(1 for s in visits if s[0] == "switch") == len(frame.extents)
            and not any(s[0] == "astray" for s in visits))


def frame_is_the_tables(switch_text: Extent, frame: Frame, records: Sequence[Record]) -> bool:
    """`FrameIsTheTables`."""
    return (extents_are_readable(switch_text, frame)
            and reserved_entered_once(switch_text, frame, records)
            and switches_in_table_order(switch_text, frame, records)
            and no_unnamed_switch(switch_text, frame, records))


# =====================================================================================
# The joined verdict
# =====================================================================================


def run_answers_m44(*, window_count: int, attempts: Sequence[Attempt],
                    roster: Sequence[CsrRow], succ: Image, switch_text: Extent,
                    frame: Frame, confinement: Sequence[Record], burst: Sequence[Record],
                    frame_trace: Sequence[Record], zero_word: int = 0) -> bool:
    """`RunAnswersM44`."""
    return (well_formed_attempts(attempts)
            and root_is_the_partitions(window_count, attempts, confinement)
            and switch_is_total(roster, succ, burst, zero_word)
            and burst_writes_exactly_once(roster, burst)
            and frame_is_the_tables(switch_text, frame, frame_trace))


# =====================================================================================
# The vector reading: `kt` lines from KernelVectors.v
# =====================================================================================


def parse_trace_field(text: str) -> list[Record]:
    """A vector's trace field: records joined by `;`, or `-` for none."""
    if text == "-":
        return []
    return parse_records(text.split(";"))


def parse_attempts(text: str) -> list[Attempt]:
    if text == "-":
        return []
    out: list[Attempt] = []
    for item in text.split(","):
        pc, register, target = item.split(":")
        out.append(Attempt(int(pc), int(register), target))
    return out


def _bits(text: str) -> list[bool]:
    words = text.split()
    if any(w not in ("0", "1") for w in words):
        raise TraceError(f"expected verdict bits, got {text!r}")
    return [w == "1" for w in words]


@dataclass
class VectorState:
    """The declarations the `kt d`, `kt r` and `kt s` lines carry."""

    switch_text: Extent | None = None
    frames: dict[int, Frame] | None = None
    roster: tuple[CsrRow, ...] = ()
    images: dict[int, Image] | None = None


@dataclass(frozen=True)
class Disagreement:
    line: int
    family: str
    column: str
    gallina: bool
    reader: bool


def _decl_frame(state: VectorState, words: list[str]) -> None:
    fid, reserved, switch = int(words[0]), int(words[1]), words[2]
    base, top = switch.split(":")
    state.switch_text = Extent(int(base), int(top))
    extents: list[Extent] = []
    for slot in words[3:]:
        _tenant, sbase, stop = slot.split(":")
        extents.append(Extent(int(sbase), int(stop)))
    if state.frames is None:
        state.frames = {}
    state.frames[fid] = Frame(tuple(extents), reserved)


def _decl_roster(state: VectorState, words: list[str]) -> None:
    rows: list[CsrRow] = []
    for item in words:
        csr, nameable, zeroized = item.split(":")
        rows.append(CsrRow(int(csr), nameable == "1", zeroized == "1"))
    state.roster = tuple(rows)


def _decl_image(state: VectorState, rest: str) -> None:
    regs_text, csrs_text = rest.split(" | ")
    seed, *regs = regs_text.split()
    registers: list[tuple[int, bool]] = []
    for reg in regs:
        value, tag = reg.split("/")
        registers.append((int(value), tag == "1"))
    if len(registers) != REGISTER_COUNT:
        raise TraceError(f"an image carries {len(registers)} registers, not 32")
    values = [int(v) for v in csrs_text.split()]
    if len(values) != len(state.roster):
        raise TraceError("an image's CSR values do not match the roster")
    if state.images is None:
        state.images = {}
    state.images[int(seed)] = Image(tuple(registers),
                                    {row.csr: v for row, v in zip(state.roster, values,
                                                                  strict=True)})


def check_vectors(lines: Iterable[str]) -> tuple[dict[str, int], list[Disagreement]]:
    """Hold every `kt` verdict against this module's own; other families are skipped.

    Returns the line count per `kt` family and every disagreement. A line that does
    not parse raises TraceError, since a vector the reader cannot read is not one it
    agreed with.
    """
    state = VectorState()
    counts = {"d": 0, "r": 0, "s": 0, "c": 0, "b": 0, "f": 0, "run": 0}
    found: list[Disagreement] = []

    def held(number: int, family: str, columns: Sequence[str],
             gallina: Sequence[bool], reader: Sequence[bool]) -> None:
        if len(gallina) != len(columns):
            raise TraceError(f"line {number}: {len(gallina)} verdicts for "
                             f"{len(columns)} columns")
        for column, want, got in zip(columns, gallina, reader, strict=True):
            if want != got:
                found.append(Disagreement(number, family, column, want, got))

    for number, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if not line.startswith("kt "):
            continue
        family = line.split(" ", 2)[1]
        if family not in counts:
            raise TraceError(f"line {number}: unknown kt family {family!r}")
        counts[family] += 1
        body = line.split(" ", 2)[2]
        if family == "d":
            _decl_frame(state, body.split())
            continue
        if family == "r":
            _decl_roster(state, body.split())
            continue
        if family == "s":
            _decl_image(state, body)
            continue
        left, right = body.rsplit(" -> ", 1)
        verdicts = _bits(right)
        if family == "c":
            window, attempts_text, trace_text = left.split(" ", 2)
            attempts = parse_attempts(attempts_text)
            records = parse_trace_field(trace_text)
            w = int(window)
            held(number, "c", ("well_formed", "cover", "root"), verdicts,
                 (well_formed_attempts(attempts), attempts_cover(w, attempts),
                  root_is_the_partitions(w, attempts, records)))
        elif family == "b":
            seed, trace_text = left.split(" ", 1)
            burst = parse_trace_field(trace_text)
            succ = _image(state, int(seed))
            roster = state.roster
            held(number, "b", ("total", "registers", "csrs", "nothing_else", "exactly_once"),
                 verdicts,
                 (switch_is_total(roster, succ, burst), register_burst_total(succ, burst),
                  csr_burst_total(roster, succ, burst),
                  burst_carries_nothing_else(roster, burst),
                  burst_writes_exactly_once(roster, burst)))
        elif family == "f":
            fid, trace_text = left.split(" ", 1)
            frame = _frame(state, int(fid))
            switch = _switch(state)
            records = parse_trace_field(trace_text)
            held(number, "f", ("readable", "reserved_once", "in_order", "no_unnamed",
                               "frame"), verdicts,
                 (extents_are_readable(switch, frame),
                  reserved_entered_once(switch, frame, records),
                  switches_in_table_order(switch, frame, records),
                  no_unnamed_switch(switch, frame, records),
                  frame_is_the_tables(switch, frame, records)))
        else:
            fid, window, seed, attempts_text, traces = left.split(" ", 4)
            confinement_text, burst_text, frame_text = traces.split(" | ")
            held(number, "run", ("run",), verdicts,
                 (run_answers_m44(
                     window_count=int(window), attempts=parse_attempts(attempts_text),
                     roster=state.roster, succ=_image(state, int(seed)),
                     switch_text=_switch(state), frame=_frame(state, int(fid)),
                     confinement=parse_trace_field(confinement_text),
                     burst=parse_trace_field(burst_text),
                     frame_trace=parse_trace_field(frame_text)),))
    return counts, found


def _image(state: VectorState, seed: int) -> Image:
    if state.images is None or seed not in state.images:
        raise TraceError(f"no successor image declared for seed {seed}")
    return state.images[seed]


def _frame(state: VectorState, fid: int) -> Frame:
    if state.frames is None or fid not in state.frames:
        raise TraceError(f"no frame declared with id {fid}")
    return state.frames[fid]


def _switch(state: VectorState) -> Extent:
    if state.switch_text is None:
        raise TraceError("no switch text declared")
    return state.switch_text
