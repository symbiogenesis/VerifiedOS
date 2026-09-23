# SPDX-License-Identifier: Apache-2.0
"""The RTL's RVFI records, framed, checked, and projected onto the commit trace.

The co-simulation gate compares the curated scalar core under Verilator with the
golden model over the shared corpus, and the golden side of that comparison is
the commit trace of
[docs/assurance/differential-corpus.md](../../docs/assurance/differential-corpus.md)
§4, schema version 1. The RTL side is the core's RVFI port, one `rvfi_instr_t`
per commit port per cycle. This module is the adapter between them: a Verilator
harness writes each retirement as one line of a **frame**, and the frame is
decoded here, held to its own protocol, and projected onto the commit grammar
through [rvfi.py](rvfi.py)'s projection. Adjudication stays
[trace.py](trace.py)'s: the frame reaches `trace.adjudicate` and nothing here
decides what a divergence is. The harness contract the frame is one part of is
[docs/assurance/rtl-cosimulation-harness.md](../../docs/assurance/rtl-cosimulation-harness.md).

**The frame, version 1.** Text, one record per line, every line ending in a
newline and carrying no carriage return:

    vos-rtl-rvfi 1                         the header, first and exactly once
    P <order> <pc_rdata> ... <mem_wdata>   one retirement, the fields of `FIELDS`
    E <count>                              the trailer: how many `P` lines ran

Every `P` field is fixed-width hexadecimal, either case, at the width `FIELDS`
states, so a line cut short or two lines run together fail at the field rather
than decoding as plausible values. The fields are the RVFI port's at the curated
width (`CLEN == XLEN == 64`, eight-byte masks), each in the form the commit
trace compares, and the harness derives three of them that the port at the pin
does not state in that form. `order` is assigned by no line of the imported
`cva6_rvfi.sv`. `rd_tag` and `rd_wdata` are the two halves of the destination's
64-bit memory encoding, the same bits a store of it writes (§4), where the port
carries the register form: the SystemVerilog side converts through the authored
format package's `cap_reg_to_cap_mem`, which is the one implementation of that
algebra the RTL has, and this module never re-derives an encoding.
`mem_rtag`/`mem_wtag` are the tag of the access, which the port has no field
for. `mem_rmask`/`mem_wmask` are byte masks shifted to the access's own address,
a low run of one, two, four or eight ones, which is the shape the port writes.
`cause` is the `mcause` value of a trapping retirement and zero on every other.

**A protocol failure is not a divergence, and the two are reported apart.** A
torn record once read as a divergence about a run that agreed (S11), and a frame
that stops early reads as agreement over its prefix: `trace.adjudicate` treats
one stream running out as the two machines halting on different conditions,
which is right for the legacy oracle and wrong for a corpus gate. So `decode`
refuses every malformed or partial frame with a `FrameError` naming the line and
the kind, and `compare` reports completeness beside the verdict: a corpus-green
comparison is one where the verdict agrees *and* both streams were consumed
whole.

**What the frame carries beyond the packet is the trap cause**, so the `T`
record is compared rather than elided; the `S` and `C` records have no field on
either port and are elided and counted by `rvfi.packet_view`, exactly as for a
packet executor. A second memory access under one instruction has no field
either, since the port reports one access per instruction.

**`carry` runs the adapter backwards, and what it is for is measurement.** It
writes the retirements a frame would need to say exactly what a golden view
says, and names each retirement whose records no frame line can hold. Over the
golden model's own corpus traces that is the frame's carrying capacity, and a
seeded field change on the result is a mutant the comparison must report. The
producer there is the golden model re-encoded and never the RTL, so what it
establishes is the adapter's handling of real record shapes and nothing about the
core.
"""

import re
from dataclasses import dataclass, replace
from typing import Final

from vos import rvfi, trace

FORMAT: Final = "vos-rtl-rvfi"
VERSION: Final = 1
HEADER: Final = f"{FORMAT} {VERSION}"

# `rvfi.Execution.wire` names the RVFI-DII wire a packet arrived in, 1 or 2. A
# retirement decoded from a frame arrived in neither, so it carries 0.
WIRE: Final = 0

# The fields of one `P` line, in order, with their width in hexadecimal digits.
FIELDS: Final[tuple[tuple[str, int], ...]] = (
    ("order", 16),
    ("pc_rdata", 16),
    ("pc_wdata", 16),
    ("insn", 8),
    ("trap", 1),
    ("cause", 16),
    ("rd_addr", 2),
    ("rd_tag", 1),
    ("rd_wdata", 16),
    ("mem_addr", 16),
    ("mem_rmask", 2),
    ("mem_wmask", 2),
    ("mem_rtag", 1),
    ("mem_wtag", 1),
    ("mem_rdata", 16),
    ("mem_wdata", 16),
)
_FLAGS: Final = frozenset({"trap", "rd_tag", "mem_rtag", "mem_wtag"})
_HEX: Final = {width: re.compile(f"[0-9A-Fa-f]{{{width}}}") for _, width in FIELDS}
_TRAILER_RE: Final = re.compile(r"E (0|[1-9][0-9]*)")

# The widths an access of this machine has, in bytes. A tag rides only on a whole
# granule (R-15-203), so only the last of them can carry one.
_WIDTHS: Final = (1, 2, 4, 8)
_GRANULE: Final = 8
_REGISTERS: Final = 32

# `mcause`'s top bit says the trap was an interrupt; the rest is the code the
# commit trace's `T` record prints.
_INTERRUPT_BIT: Final = 63
_CODE_MASK: Final = (1 << _INTERRUPT_BIT) - 1
_WORD: Final = (1 << 64) - 1

# The one record kind the frame carries beyond the packet's.
CARRIED: Final = frozenset({"T"})


class FrameError(ValueError):
    """A frame that breaks its protocol, with the line and the kind of the break.

    Raised rather than returned because a caller that forgets to look at a
    returned error would adjudicate a torn stream, which is the failure this
    module exists to keep apart from a divergence.
    """

    def __init__(self, line: int, kind: str, message: str) -> None:
        super().__init__(f"line {line}: {kind}: {message}")
        self.line = line
        self.kind = kind


@dataclass(frozen=True)
class Retire:
    """One retirement: the packet-shaped part, and the cause the packet lacks."""

    packet: rvfi.Execution
    cause: int = 0


def _parse(line: str, number: int) -> dict[str, int]:
    tokens = line.split(" ")
    if len(tokens) != len(FIELDS) + 1:
        raise FrameError(number, "field-count",
                         f"a retirement carries {len(FIELDS)} fields after `P`, "
                         f"got {len(tokens) - 1}")
    values: dict[str, int] = {}
    for (name, width), token in zip(FIELDS, tokens[1:], strict=True):
        if not _HEX[width].fullmatch(token):
            raise FrameError(number, "field-width",
                             f"`{name}` is {width} hexadecimal digit(s), got {token!r}")
        values[name] = int(token, 16)
    return values


def _mask(number: int, name: str, mask: int, tag: int) -> int:
    """The mask in the dialect `rvfi.mask_access` reads: bytes, and the tag above."""
    if mask == 0:
        if tag:
            raise FrameError(number, "tag", f"`{name}` is empty and its access carries a tag")
        return 0
    width = next((w for w in _WIDTHS if mask == (1 << w) - 1), None)
    if width is None:
        raise FrameError(number, "mask",
                         f"`{name}` {mask:#04x} is not a low run of 1, 2, 4 or 8 ones")
    if tag and width < _GRANULE:
        raise FrameError(number, "tag",
                         f"a {width}-byte access carries a tag; only a whole "
                         f"{_GRANULE}-byte granule can (R-15-203)")
    return mask | (tag << width)


def _retire(values: dict[str, int], number: int, expected: int) -> Retire:
    for name in sorted(_FLAGS):
        if values[name] > 1:
            raise FrameError(number, "flag", f"`{name}` is 0 or 1, got {values[name]:X}")
    if values["order"] != expected:
        raise FrameError(number, "order",
                         f"retirement {expected} of this frame carries order "
                         f"{values['order']}: a packet was lost, repeated or reordered")
    if values["rd_addr"] >= _REGISTERS:
        raise FrameError(number, "register",
                         f"`rd_addr` names one of {_REGISTERS} registers, got "
                         f"{values['rd_addr']}")
    if values["rd_addr"] == 0 and (values["rd_wdata"] or values["rd_tag"]):
        raise FrameError(number, "rd-x0",
                         "a retirement naming x0 writes nothing, so its data and tag "
                         "are zero (RVFI)")
    if not values["trap"] and values["cause"]:
        raise FrameError(number, "cause",
                         "a cause is read only where the retirement trapped, and is "
                         "zero on every other")
    packet = rvfi.Execution(
        wire=WIRE,
        order=values["order"],
        pc_rdata=values["pc_rdata"],
        pc_wdata=values["pc_wdata"],
        insn=values["insn"],
        trap=values["trap"],
        rd_addr=values["rd_addr"],
        rd_wdata=values["rd_wdata"],
        rd_tag=bool(values["rd_tag"]),
        mem_addr=values["mem_addr"],
        mem_rdata=values["mem_rdata"],
        mem_wdata=values["mem_wdata"],
        mem_rmask=_mask(number, "mem_rmask", values["mem_rmask"], values["mem_rtag"]),
        mem_wmask=_mask(number, "mem_wmask", values["mem_wmask"], values["mem_wtag"]),
        integer_present=True,
        memory_present=True,
    )
    return Retire(packet, values["cause"])


def decode(text: str) -> list[Retire]:
    """Every retirement a whole frame carries, or the first way it is not whole."""
    if not text:
        raise FrameError(1, "header", f"an empty frame has no `{HEADER}` header")
    if not text.endswith("\n"):
        last = text.count("\n") + 1
        raise FrameError(last, "torn",
                         "the frame ends inside a line: the writer stopped mid-record")
    lines = text[:-1].split("\n")
    for number, line in enumerate(lines, start=1):
        if "\r" in line:
            raise FrameError(number, "carriage-return",
                             "a frame line carries no carriage return")
    head = lines[0].split(" ")
    if len(head) != 2 or head[0] != FORMAT:
        raise FrameError(1, "header", f"a frame opens with `{HEADER}`, got {lines[0]!r}")
    if head[1] != str(VERSION):
        raise FrameError(1, "version",
                         f"this reader decodes version {VERSION} and the frame is "
                         f"version {head[1]!r}; a different version is refused rather "
                         f"than read as this one")

    retires: list[Retire] = []
    for number, line in enumerate(lines[1:], start=2):
        if line.startswith("P "):
            retires.append(_retire(_parse(line, number), number, len(retires)))
        elif line.startswith("E"):
            trailer = _TRAILER_RE.fullmatch(line)
            if trailer is None:
                raise FrameError(number, "trailer",
                                 f"a trailer is `E` and a decimal count, got {line!r}")
            if int(trailer.group(1)) != len(retires):
                raise FrameError(number, "trailer",
                                 f"the trailer counts {trailer.group(1)} retirements "
                                 f"and the frame carried {len(retires)}")
            if number != len(lines):
                raise FrameError(number + 1, "after-trailer",
                                 "nothing follows the trailer")
            return retires
        else:
            raise FrameError(number, "record",
                             f"a frame line is `P` or `E`, got {line[:24]!r}")
    raise FrameError(len(lines) + 1, "partial",
                     f"the frame ends after {len(retires)} retirement(s) with no "
                     f"trailer: the run did not finish writing it")


def encode(retires: list[Retire]) -> str:
    """A frame carrying `retires`, as a producer following this contract writes it.

    The fixtures build frames through this rather than by hand, and a decode of
    its output is `retires` again: the round trip is what holds the two halves of
    the contract to one reading. Orders are written as carried, so a caller can
    build the lost and repeated packets the decoder must refuse.
    """
    out = [HEADER]
    for retire in retires:
        packet = retire.packet
        read = rvfi.mask_access(packet.mem_rmask)
        write = rvfi.mask_access(packet.mem_wmask)
        values = {
            "order": packet.order, "pc_rdata": packet.pc_rdata,
            "pc_wdata": packet.pc_wdata, "insn": packet.insn, "trap": packet.trap,
            "cause": retire.cause, "rd_addr": packet.rd_addr,
            "rd_tag": int(packet.rd_tag), "rd_wdata": packet.rd_wdata,
            "mem_addr": packet.mem_addr,
            "mem_rmask": 0 if read is None else (1 << read[0]) - 1,
            "mem_wmask": 0 if write is None else (1 << write[0]) - 1,
            "mem_rtag": 0 if read is None else int(read[1]),
            "mem_wtag": 0 if write is None else int(write[1]),
            "mem_rdata": packet.mem_rdata, "mem_wdata": packet.mem_wdata,
        }
        out.append("P " + " ".join(f"{values[name]:0{width}X}" for name, width in FIELDS))
    out.append(f"E {len(retires)}")
    return "\n".join(out) + "\n"


def records(retire: Retire, *, addr_digits: int = rvfi.PHYSADDR_DIGITS) -> list[str]:
    """One retirement in the commit grammar: the packet's records, and its trap.

    The `T` record follows the packet's own, which is the place `rvfi.packet_view`
    puts a carried kind on the golden side; the order is a convention the two
    views share and not a claim about the order the model fired its callbacks in.
    """
    out = rvfi.records(retire.packet, addr_digits=addr_digits)
    if retire.packet.trap:
        interrupt = retire.cause >> _INTERRUPT_BIT
        out.append(f"T {interrupt} {retire.cause & _CODE_MASK}")
    return out


def project(retires: list[Retire], *, addr_digits: int = rvfi.PHYSADDR_DIGITS) -> list[str]:
    """A frame as normalized commit records, held to the grammar by the normalizer.

    The same guard `vengine.project` keeps: the projection is handed to
    `trace.normalize_commit`, and a record it would drop is a finding here rather
    than a stream that quietly agrees about less than it says.
    """
    lines = [line for retire in retires for line in records(retire, addr_digits=addr_digits)]
    normalized = trace.normalize_commit(lines)
    if len(normalized) != len(lines):
        bad = next(line for line in lines if not trace.COMMIT_RE.match(line))
        raise ValueError(f"the frame projection is outside the commit grammar: {bad!r}")
    return normalized


def view(reference: list[str]) -> tuple[list[str], rvfi.Elided]:
    """The golden commit trace cut to what a frame can say, with what it lost counted."""
    return rvfi.packet_view(trace.normalize_commit(reference), carried=CARRIED)


@dataclass(frozen=True)
class Comparison:
    """One frame adjudicated against the golden commit trace of the same program."""

    verdict: trace.Verdict
    reference: int
    candidate: int
    retired: int
    elided: rvfi.Elided

    @property
    def complete(self) -> bool:
        """Agreement over both streams whole, which is what a corpus gate asks.

        `trace.adjudicate` answers agreement over the common prefix after aligning
        the candidate on the reference's first program counter; a candidate that
        stopped early, retired records the reference never reaches, or retired
        records before that first program counter agrees over that prefix and is
        not complete.
        """
        return (self.verdict.ok and self.verdict.compared == self.reference
                and self.verdict.compared == self.candidate)

    def line(self) -> str:
        if not self.verdict.ok:
            return self.verdict.line()
        if self.complete:
            return f"agreed over {self.verdict.compared} records, both streams whole"
        return (f"agreed over {self.verdict.compared} records of a reference of "
                f"{self.reference} and a candidate of {self.candidate}: incomplete")


def compare(reference: list[str], frame: str, *, context: int = 4) -> Comparison:
    """The golden commit trace against the RTL's frame, through the one adjudicator.

    `reference` is the emulator's commit trace as written, and it is normalized
    here. The frame is decoded first, so a protocol failure raises `FrameError`
    before anything is compared.
    """
    retires = decode(frame)
    golden, elided = view(reference)
    return compare_decoded(golden, retires, elided, context=context)


def compare_decoded(golden: list[str], retires: list[Retire], elided: rvfi.Elided, *,
                    context: int = 4) -> Comparison:
    """A decoded frame against a golden view that `view` already cut.

    The verdict is `trace.adjudicate`'s; this adds only the counts `complete`
    reads.
    """
    projected = project(retires, addr_digits=rvfi.address_digits(golden))
    verdict = trace.adjudicate(golden, projected, context)
    return Comparison(verdict, len(golden), len(projected), len(retires), elided)


# --- running the adapter backwards, to measure it ----------------------------


@dataclass(frozen=True)
class Refusal:
    """One golden retirement no frame line can hold, and the shape that decides it."""

    at: int
    pc: int
    insn: int
    reason: str


# Why a retirement has no frame line, one key per structural shape. Each is a
# property of the port rather than of the golden model: one destination group,
# one address for its one read and one write, eight-byte masks, one cause.
REASONS: Final = {
    "wide-access": "an access wider than the eight bytes a curated mask covers",
    "two-addresses": "a read and a write under one instruction at different addresses",
    "two-registers": "more than one register write under one instruction",
    "two-traps": "more than one trap under one instruction",
}


def carry(golden: list[str]) -> tuple[list[Retire], list[Refusal]]:
    """The retirements a frame needs to say what a golden view says, and what it cannot.

    `golden` is a view `view` cut, so the records the port has no field for are
    already elided and counted; what remains is refused per retirement where no
    frame line holds it. A refused retirement is still written, carrying the part
    that fits, so a comparison over the result diverges at the first refusal
    rather than agreeing over a stream that skipped it. `pc_wdata` is the next
    retirement's program counter, and four bytes on for the last, a field the
    commit trace does not compare.
    """
    groups: list[list[str]] = []
    for record in golden:
        if record[0] == "I":
            groups.append([record])
        elif groups:
            groups[-1].append(record)
        else:
            raise ValueError(f"a golden view opens with an effect and no instruction: "
                             f"{record!r}")

    pcs = [int(group[0].split()[1], 16) for group in groups]
    retires: list[Retire] = []
    refusals: list[Refusal] = []
    for at, group in enumerate(groups):
        _, pc_text, insn_text = group[0].split()
        pc = int(pc_text, 16)
        fields: dict[str, int] = {}
        cause = 0
        refused: list[str] = []
        kinds = [record[0] for record in group[1:]]
        if kinds.count("X") > 1:
            refused.append("two-registers")
        if kinds.count("T") > 1:
            refused.append("two-traps")
        addresses: set[int] = set()
        for record in group[1:]:
            parts = record.split()
            if record[0] in "RW":
                address, width, tag, value = (int(parts[1], 16), int(parts[2]),
                                              int(parts[3]), int(parts[4], 16))
                if width not in _WIDTHS:
                    refused.append("wide-access")
                    continue
                addresses.add(address)
                side = "r" if record[0] == "R" else "w"
                fields["mem_addr"] = address
                fields[f"mem_{side}mask"] = ((1 << width) - 1) | (tag << width)
                fields[f"mem_{side}data"] = value
            elif record[0] == "X" and "rd_addr" not in fields:
                fields["rd_addr"] = int(parts[1])
                fields["rd_tag"] = int(parts[2])
                fields["rd_wdata"] = int(parts[3], 16)
            elif record[0] == "T" and "trap" not in fields:
                fields["trap"] = 1
                cause = (int(parts[1]) << _INTERRUPT_BIT) | (int(parts[2]) & _CODE_MASK)
        if len(addresses) > 1:
            refused.append("two-addresses")
        refusals.extend(Refusal(at, pc, int(insn_text, 16), reason)
                        for reason in dict.fromkeys(refused))
        packet = rvfi.Execution(
            wire=WIRE, order=at, pc_rdata=pc, insn=int(insn_text, 16),
            pc_wdata=pcs[at + 1] if at + 1 < len(pcs) else (pc + 4) & _WORD,
            trap=fields.get("trap", 0), rd_addr=fields.get("rd_addr", 0),
            rd_wdata=fields.get("rd_wdata", 0), rd_tag=bool(fields.get("rd_tag", 0)),
            mem_addr=fields.get("mem_addr", 0),
            mem_rdata=fields.get("mem_rdata", 0), mem_wdata=fields.get("mem_wdata", 0),
            mem_rmask=fields.get("mem_rmask", 0), mem_wmask=fields.get("mem_wmask", 0),
            integer_present=True, memory_present=True)
        retires.append(Retire(packet, cause))
    return retires, refusals


# --- seeded field changes, which the comparison must report ------------------


@dataclass(frozen=True)
class Seed:
    """One field change to one retirement, standing for a way an RTL gets it wrong."""

    name: str
    what: str


# Every seed moves a field the commit trace compares, so a seed that changes the
# frame and leaves the projection unmoved is a finding about the adapter rather
# than a mutant designed to survive. Bits above an access's width and `pc_wdata`
# are outside the compared records by the schema's construction and are seeded by
# nothing here.
SEEDS: Final = (
    Seed("pc", "the retirement reports the next instruction's program counter "
               "four bytes on"),
    Seed("insn", "one bit of the retired word is wrong"),
    Seed("rd-value", "the lowest bit of the destination write is wrong"),
    Seed("rd-tag", "the destination write reports the other tag"),
    Seed("rd-register", "the destination write lands in a neighbouring register"),
    Seed("read-value", "the lowest bit of the loaded bytes is wrong"),
    Seed("write-value", "the lowest bit of the stored bytes is wrong"),
    Seed("access-tag", "an eight-byte access reports the other tag"),
    Seed("cause", "a trap reports the next cause code"),
    Seed("trap-flag", "a trap is reported as an ordinary retirement, with no cause"),
    Seed("lost", "the retirement is missing from the frame"),
)


def seed(retires: list[Retire], at: int, name: str) -> list[Retire] | None:
    """`retires` with seed `name` applied at retirement `at`, or `None` where it has
    no witness there: a register seed at an instruction that writes none, a tag seed
    at an access narrower than a granule, a cause or trap-flag seed where nothing
    trapped.

    The orders are rewritten after a loss, so a lost retirement arrives as a
    well-formed frame one line shorter and is the comparison's to report rather
    than the decoder's.
    """
    retire = retires[at]
    packet = retire.packet
    changed: Retire | None = None
    read = rvfi.mask_access(packet.mem_rmask)
    write = rvfi.mask_access(packet.mem_wmask)
    if name == "pc":
        changed = replace(retire, packet=replace(packet, pc_rdata=(packet.pc_rdata + 4) & _WORD))
    elif name == "insn":
        changed = replace(retire, packet=replace(packet, insn=packet.insn ^ (1 << 7)))
    elif name == "rd-value" and packet.rd_addr:
        changed = replace(retire, packet=replace(packet, rd_wdata=packet.rd_wdata ^ 1))
    elif name == "rd-tag" and packet.rd_addr:
        changed = replace(retire, packet=replace(packet, rd_tag=not packet.rd_tag))
    elif name == "rd-register" and packet.rd_addr:
        changed = replace(retire, packet=replace(
            packet, rd_addr=packet.rd_addr % (_REGISTERS - 1) + 1))
    elif name == "read-value" and read is not None:
        changed = replace(retire, packet=replace(packet, mem_rdata=packet.mem_rdata ^ 1))
    elif name == "write-value" and write is not None:
        changed = replace(retire, packet=replace(packet, mem_wdata=packet.mem_wdata ^ 1))
    elif name == "access-tag":
        for side, access in (("mem_rmask", read), ("mem_wmask", write)):
            if access is not None and access[0] == _GRANULE:
                mask = getattr(packet, side) ^ (1 << _GRANULE)
                changed = replace(retire, packet=replace(packet, **{side: mask}))
                break
    elif name == "cause" and packet.trap:
        changed = replace(retire, cause=(retire.cause & ~_CODE_MASK)
                          | ((retire.cause + 1) & _CODE_MASK))
    elif name == "trap-flag" and packet.trap:
        changed = replace(retire, packet=replace(packet, trap=0), cause=0)
    elif name == "lost":
        rest = retires[:at] + retires[at + 1:]
        return [replace(r, packet=replace(r.packet, order=i)) for i, r in enumerate(rest)]
    elif name not in {s.name for s in SEEDS}:
        raise ValueError(f"no seed {name!r}; there are {', '.join(s.name for s in SEEDS)}")
    if changed is None:
        return None
    return [*retires[:at], changed, *retires[at + 1:]]
