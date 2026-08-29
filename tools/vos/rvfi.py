# SPDX-License-Identifier: Apache-2.0
"""RVFI-DII on the wire, and what one packet says in the commit trace's grammar.

Two formats meet in this module and only one of them is this repository's.

**RVFI-DII is TestRIG's.** It is two structures over one socket: an eight-byte
*instruction* packet the verification engine sends to the implementation, and an
*execution* packet the implementation sends back for each instruction it
retires. The field names, the byte offsets, the two command values and the
64 KiB-at-0x80000000 memory contract are `RVFI-DII.md`'s, read at the commit
[THIRD-PARTY.md](../../THIRD-PARTY.md) pins `upstream/TestRIG` at. The
**version-2** packet is not in that document, which describes v1 alone; it is
read from the model's own [core/rvfi_dii_v2.sail](../../model/model/core/rvfi_dii_v2.sail)
and [core/rvfi_dii.sail](../../model/model/core/rvfi_dii.sail), which are the
format's only written statement, and TestRIG's own issue tracker records that
the v2 protocol is undocumented.

**The commit trace is this repository's**, versioned in
[docs/differential-corpus.md](../../docs/differential-corpus.md) §4 and parsed
by [trace.py](trace.py). It is the dialect the corpus is versioned against and
the one every executor of the frozen profile emits.

**This repository carries a dialect of the standard packet rather than an
extension of it, and the ground is that the standard packet cannot be extended
to carry the schema.** The widening M0.12 made *is* inside the standard packet:
`rvfi_rd_tag` is one bit taken from the Integer extension's padding and the
memory masks carry the access's tag one bit above its byte mask, both of which
fit the CHERI-widened fields upstream already sized. What does not fit is
structural rather than a field short: the packet is fixed-size and holds **one**
memory access per instruction, so `cbo.zero`'s block write and `cloadtags`'
eight granule reads have no form in it at all; it has **no field** for the four
capability registers outside the merged file, upstream's own
`cheri_scr_read_write_data_available` bit being declared and unimplemented; and
its trap byte is a boolean where the schema's `T` record carries the cause. A
format that must grow a variable-length effect list, a fifth register file and a
cause field is a different grammar, not a longer packet. So the record stream
carries the whole schema, the packet carries the subset it can, and `records`
below is the projection between them, which is the only place the two are held
to say the same thing.

**Version 1 cannot carry the widening at all**, which is why every loop here
negotiates v2. `rvfi_get_exec_packet_v1` truncates the 32-bit masks to 8 bits,
and the tag of an eight-byte capability access sits at bit 8, so the truncation
deletes exactly the bit M0.12 added; and v1 has no `rd_tag` field to copy into.
A v1 conversation is therefore a conversation about an integer machine.

**Byte order is little-endian and it is the emulator's rather than a choice.**
The instruction packet is read straight into a `mach_bits` by
[rvfi_dii.cpp](../../model/c_emulator/rvfi_dii.cpp), and every execution packet
leaves through `mpz_export(..., -1, 1, 0, 0, ...)`, whose `-1` is
least-significant word first at a word size of one byte. Both are the host's
order on the little-endian hosts this lane runs on, and neither is negotiated.
"""

from dataclasses import dataclass, replace
from typing import Final

# --- the instruction packet ------------------------------------------------
#
#   struct RVFI_DII_Instruction_Packet {   // 8 bytes
#      Bit8  padding;   // [7]
#      Bit8  rvfi_cmd;  // [6]
#      Bit16 rvfi_time; // [5 - 4]
#      Bit32 rvfi_insn; // [0 - 3]
#   }
DII_BYTES: Final = 8

# The two commands RVFI-DII.md defines, and the third the model answers to.
CMD_END_OF_TRACE: Final = 0
CMD_INSTRUCTION: Final = 1
# `v`, which selects the wire format. It is not in RVFI-DII.md: the model
# implements it (`rvfi_dii.cpp`'s `case 'v'`) and it is how a v2 conversation is
# entered once the probe below says v2 is available.
CMD_SET_VERSION: Final = ord("v")

# An EndOfTrace whose instruction word is the ASCII "VERS" is a version probe
# rather than a reset. The reply is a v1-shaped packet whose halt byte says
# which formats the implementation has.
VERSION_PROBE: Final = 0x56455253
HALT_V1_ONLY: Final = 0x01
HALT_V2_CAPABLE: Final = 0x03

# What the model writes back when a `v` command is accepted: eight ASCII bytes
# and the selected version as a little-endian 64-bit word.
VERSION_REPLY: Final = b"version="
VERSION_REPLY_BYTES: Final = 16

# --- the execution packets -------------------------------------------------
EXEC_V1_BYTES: Final = 88
EXEC_V2_BYTES: Final = 64
EXT_INTEGER_BYTES: Final = 40
EXT_MEMACCESS_BYTES: Final = 88

MAGIC_V2: Final = b"trace-v2"
MAGIC_INTEGER: Final = b"int-data"
MAGIC_MEMORY: Final = b"mem-data"

# Which extension follows the v2 packet, by the bit that announces it. Only the
# first two are implemented upstream; the other five are declared bits with no
# struct behind them, which is the half of the format the commit trace exists
# to carry.
AVAILABLE_INTEGER: Final = 0
AVAILABLE_MEMORY: Final = 1

# The address field of a commit-trace memory record is printed at the model's
# own physical-address width, `(physaddrbits_len() + 3) / 4` hexadecimal digits,
# where the RVFI packet zero-extends the same address to 64 bits. That width is
# the *type* `physaddrbits`' and not the frozen profile's 36-bit space, which is
# a property of the composition rather than of the model's address type, so it
# is sixteen digits and the two formats agree here by accident of width rather
# than by construction. It is a default and not a constant: `testrig.py bridge`
# measures it off the records it is comparing against, which is the only reading
# of it that cannot go stale.
PHYSADDR_DIGITS: Final = 16


def dii(insn: int, *, cmd: int = CMD_INSTRUCTION, time: int = 0) -> bytes:
    """One instruction packet, as the eight bytes that go on the wire."""
    if not 0 <= insn < (1 << 32):
        raise ValueError(f"an instruction word is 32 bits, got {insn:#x}")
    if not 0 <= cmd < (1 << 8):
        raise ValueError(f"a command is one byte, got {cmd:#x}")
    if not 0 <= time < (1 << 16):
        raise ValueError(f"a time is two bytes, got {time:#x}")
    return (insn | (time << 32) | (cmd << 48)).to_bytes(DII_BYTES, "little")


def instruction(insn: int, *, time: int = 0) -> bytes:
    return dii(insn, cmd=CMD_INSTRUCTION, time=time)


def end_of_trace() -> bytes:
    """Reset the implementation: registers, memory, and the PC back to 0x80000000.

    Every trace ends with one, and it is what makes each candidate stream a run
    of its own rather than a continuation of the last.
    """
    return dii(0, cmd=CMD_END_OF_TRACE)


def version_probe() -> bytes:
    return dii(VERSION_PROBE, cmd=CMD_END_OF_TRACE)


def select_version(version: int) -> bytes:
    return dii(version, cmd=CMD_SET_VERSION)


@dataclass(frozen=True)
class Execution:
    """One retired instruction as the implementation reported it.

    Frozen because a seeded defect is a *second* packet derived from this one
    rather than a mutation of it: an executor that edits its own report in place
    is one whose reference trace cannot be shown afterwards.

    `wire` is the format the packet arrived in, and it is carried because two of
    the fields below cannot be believed from a v1 packet: `rd_tag` has no v1
    field at all, and `mem_rmask`/`mem_wmask` arrive truncated to their byte
    halves, so the tag bit above the mask is gone rather than clear.
    """

    wire: int
    order: int = 0
    pc_rdata: int = 0
    pc_wdata: int = 0
    insn: int = 0
    trap: int = 0
    halt: int = 0
    intr: int = 0
    mode: int = 0
    ixl: int = 0
    rd_addr: int = 0
    rd_wdata: int = 0
    rd_tag: bool = False
    rs1_addr: int = 0
    rs1_rdata: int = 0
    rs2_addr: int = 0
    rs2_rdata: int = 0
    mem_addr: int = 0
    mem_rdata: int = 0
    mem_wdata: int = 0
    mem_rmask: int = 0
    mem_wmask: int = 0
    integer_present: bool = False
    memory_present: bool = False

    @property
    def retired(self) -> bool:
        """Whether this packet reports an instruction rather than an acknowledgement.

        A halt byte is set on the packet the model answers `EndOfTrace` with and
        on the one it answers the version probe with, neither of which is a
        retirement; under direct instruction injection the model never halts of
        its own accord, so there is no third reading of the byte to lose.
        """
        return self.halt == 0


def _u(data: bytes, at: int, size: int) -> int:
    return int.from_bytes(data[at:at + size], "little")


def decode_v1(data: bytes) -> Execution:
    """The 88-byte packet of RVFI-DII.md, at the byte offsets that document states."""
    if len(data) != EXEC_V1_BYTES:
        raise ValueError(f"a v1 execution packet is {EXEC_V1_BYTES} bytes, got {len(data)}")
    return Execution(
        wire=1,
        order=_u(data, 0, 8),
        pc_rdata=_u(data, 8, 8),
        pc_wdata=_u(data, 16, 8),
        insn=_u(data, 24, 8) & 0xFFFFFFFF,
        rs1_rdata=_u(data, 32, 8),
        rs2_rdata=_u(data, 40, 8),
        rd_wdata=_u(data, 48, 8),
        mem_addr=_u(data, 56, 8),
        mem_rdata=_u(data, 64, 8),
        mem_wdata=_u(data, 72, 8),
        mem_rmask=_u(data, 80, 1),
        mem_wmask=_u(data, 81, 1),
        rs1_addr=_u(data, 82, 1),
        rs2_addr=_u(data, 83, 1),
        rd_addr=_u(data, 84, 1),
        trap=_u(data, 85, 1),
        halt=_u(data, 86, 1),
        intr=_u(data, 87, 1),
        integer_present=True,
        memory_present=True,
    )


def v2_trace_size(head: bytes) -> int:
    """How many bytes the whole v2 reply is, read out of its own first 64.

    The model always returns a maximum-size main packet and states the real
    length in the packet, leaving the emulator to send only that much: the
    caller therefore reads this many bytes and not a fixed number.
    """
    if len(head) < EXEC_V2_BYTES:
        raise ValueError(f"a v2 packet's head is {EXEC_V2_BYTES} bytes, got {len(head)}")
    if head[0:8] != MAGIC_V2:
        raise ValueError(f"a v2 packet opens with {MAGIC_V2!r}, got {head[0:8]!r}")
    return _u(head, 8, 8)


def decode_v2(data: bytes) -> Execution:
    """The 512-bit packet of `rvfi_dii_v2.sail`, with the extensions it announces.

    The extensions follow the main packet in the order their availability bits
    are numbered, which is the order `send_trace` writes them in, and each opens
    with a magic the decode holds it to: an extension read at the wrong offset
    would otherwise decode as plausible values rather than as a finding.
    """
    size = v2_trace_size(data)
    if len(data) != size:
        raise ValueError(f"a v2 packet states {size} bytes and {len(data)} arrived")

    available = _u(data, 56, 8)
    basic, pc = 16, 40
    packet = Execution(
        wire=2,
        order=_u(data, basic + 0, 8),
        insn=_u(data, basic + 8, 8) & 0xFFFFFFFF,
        trap=_u(data, basic + 16, 1),
        halt=_u(data, basic + 17, 1),
        intr=_u(data, basic + 18, 1),
        mode=_u(data, basic + 19, 1),
        ixl=_u(data, basic + 20, 1),
        pc_rdata=_u(data, pc + 0, 8),
        pc_wdata=_u(data, pc + 8, 8),
        integer_present=bool((available >> AVAILABLE_INTEGER) & 1),
        memory_present=bool((available >> AVAILABLE_MEMORY) & 1),
    )

    at = EXEC_V2_BYTES
    if packet.integer_present:
        packet = _with_integer(packet, data[at:at + EXT_INTEGER_BYTES])
        at += EXT_INTEGER_BYTES
    if packet.memory_present:
        packet = _with_memory(packet, data[at:at + EXT_MEMACCESS_BYTES])
        at += EXT_MEMACCESS_BYTES
    if at != size:
        raise ValueError(f"a v2 packet states {size} bytes and its extensions end at {at}")
    return packet


def _with_integer(packet: Execution, ext: bytes) -> Execution:
    if len(ext) != EXT_INTEGER_BYTES or ext[0:8] != MAGIC_INTEGER:
        raise ValueError(f"the integer extension is {EXT_INTEGER_BYTES} bytes opening "
                         f"{MAGIC_INTEGER!r}, got {len(ext)} bytes opening {ext[0:8]!r}")
    return replace(
        packet,
        rd_wdata=_u(ext, 8, 8),
        rs1_rdata=_u(ext, 16, 8),
        rs2_rdata=_u(ext, 24, 8),
        rd_addr=_u(ext, 32, 1),
        rs1_addr=_u(ext, 33, 1),
        rs2_addr=_u(ext, 34, 1),
        # Bit 280 of the extension, which is bit 0 of byte 35: the one bit of a
        # capability the integer reading of a register cannot show (R-15-007i),
        # taken from the packet's own padding at M0.12.
        rd_tag=bool(ext[35] & 1),
    )


def _with_memory(packet: Execution, ext: bytes) -> Execution:
    if len(ext) != EXT_MEMACCESS_BYTES or ext[0:8] != MAGIC_MEMORY:
        raise ValueError(f"the memory extension is {EXT_MEMACCESS_BYTES} bytes opening "
                         f"{MAGIC_MEMORY!r}, got {len(ext)} bytes opening {ext[0:8]!r}")
    return replace(
        packet,
        mem_rdata=_u(ext, 8, 32),
        mem_wdata=_u(ext, 40, 32),
        mem_rmask=_u(ext, 72, 4),
        mem_wmask=_u(ext, 76, 4),
        mem_addr=_u(ext, 80, 8),
    )


def mask_access(mask: int) -> tuple[int, bool] | None:
    """The width in bytes and the tag an access mask carries, or `None` for no access.

    `rvfi_mask_with_tag` sets bits 0 through *w* − 1 for the bytes of a *w*-byte
    access and bit *w* where that access carried a validity tag, so a mask is a
    low run of ones whose length is either the width or the width plus one. The
    two readings are told apart by **the widths being powers of two**: a run of
    nine is an eight-byte tagged access because nine is not a width.

    The one length that is ambiguous is two, which is a two-byte untagged access
    and also a one-byte tagged one, and it is decided the first way because the
    tag granule is eight bytes (R-15-203): no access narrower than a granule can
    carry a tag, so the second reading names an access this machine has no form
    for. That ambiguity is the encoding's and is stated here rather than
    repaired, a repair being a second opinion about a wire format.
    """
    if mask == 0:
        return None
    ones = 0
    while (mask >> ones) & 1:
        ones += 1
    if mask >> ones:
        raise ValueError(f"an access mask is a low run of ones, got {mask:#x}")
    if ones & (ones - 1) == 0:
        return ones, False
    if (ones - 1) & (ones - 2) == 0:
        return ones - 1, True
    raise ValueError(f"an access mask of {ones} bytes names no width this machine has")


# The order effects are written in under their instruction, on both sides of any
# comparison a packet takes part in. **A packet is a structure and not a
# sequence**: it has one memory-read field group, one memory-write group and one
# destination-register group, and no field anywhere saying which happened first.
# The commit trace does carry that order, being a stream of callbacks in the
# order the model fired them, so a comparison that kept it would be comparing
# something only one side has. Both sides are therefore put in this order, which
# is the model's own for the instruction that has all three: an atomic reads,
# writes, and then writes its destination.
EFFECT_ORDER: Final = ("R", "W", "X")


def records(packet: Execution, *, addr_digits: int = PHYSADDR_DIGITS) -> list[str]:
    """One packet, in the commit trace's record grammar.

    This is the projection §4's schema and the standard packet meet at, and it
    is deliberately lossy in the direction the packet is: the `S`, `C` and `T`
    records have no fields here and nothing is invented for them.
    """
    out = [f"I {packet.order} {packet.pc_rdata:016X} {packet.insn:08X}"]
    for kind, mask, value in (("R", packet.mem_rmask, packet.mem_rdata),
                              ("W", packet.mem_wmask, packet.mem_wdata)):
        access = mask_access(mask)
        if access is None:
            continue
        width, tag = access
        bits = value & ((1 << (8 * width)) - 1)
        out.append(f"{kind} {packet.mem_addr:0{addr_digits}X} {width} {int(tag)} "
                   f"{bits:0{2 * width}X}")
    if packet.rd_addr:
        out.append(f"X {packet.rd_addr} {int(packet.rd_tag)} {packet.rd_wdata:016X}")
    return out


@dataclass(frozen=True)
class Elided:
    """What a commit stream loses on its way into the packet's shape.

    Counted rather than dropped in silence: these four numbers are the size of
    the gap between the two formats over the run that was actually driven, which
    is the only honest way to say how far a packet-only executor can be compared.
    """

    scr: int = 0
    csr: int = 0
    traps: int = 0
    extra_reads: int = 0
    extra_writes: int = 0

    @property
    def total(self) -> int:
        return self.scr + self.csr + self.traps + self.extra_reads + self.extra_writes

    def line(self) -> str:
        return (f"{self.scr} capability-register, {self.csr} CSR, {self.traps} trap, "
                f"{self.extra_reads} further-read and {self.extra_writes} further-write "
                f"records the packet has no field for")


def packet_view(commit: list[str]) -> tuple[list[str], Elided]:
    """A normalized commit stream cut down to what an RVFI packet could have said.

    Every record the packet cannot carry is removed and counted, so that a
    comparison between a packet stream and a commit stream is a comparison over
    the fields both formats have rather than a divergence at the first `S`. What
    survives is re-ordered into `EFFECT_ORDER` under its instruction, for the
    reason stated there.
    """
    view: list[str] = []
    counts = dict.fromkeys("SCTRW", 0)
    group: dict[str, list[str]] = {kind: [] for kind in EFFECT_ORDER}

    def flush() -> None:
        for kind in EFFECT_ORDER:
            view.extend(group[kind])
            group[kind].clear()

    for record in commit:
        kind = record[0]
        if kind == "I":
            flush()
            view.append(record)
        elif kind in ("S", "C", "T"):
            counts[kind] += 1
        elif kind == "X":
            group["X"].append(record)
        elif group[kind]:
            # The packet holds one read and one write, so a second of either is
            # an effect it has no field for rather than a record it disagrees on.
            counts[kind] += 1
        else:
            group[kind].append(record)
    flush()
    return view, Elided(counts["S"], counts["C"], counts["T"],
                        counts["R"], counts["W"])
