# SPDX-License-Identifier: Apache-2.0
"""RVFI-DII wire protocol and projection to [differential-corpus.md](../../docs/assurance/differential-corpus.md) (§4) commit records.

Implements the 8-byte RVFI-DII instruction packet, version-1 (88-byte) and version-2
([core/rvfi_dii_v2.sail](../../model/model/core/rvfi_dii_v2.sail) + integer/memory
extensions) execution packets in little-endian byte order, and the lossy projection
between fixed-size RVFI packets and the commit-trace record grammar ([trace.py](trace.py)).
"""

from dataclasses import dataclass, replace
from typing import Final

# 8-byte RVFI-DII instruction packet (`insn[31:0]`, `time[47:32]`, `cmd[55:48]`, `pad[63:56]`).
DII_BYTES: Final = 8

CMD_END_OF_TRACE: Final = 0
CMD_INSTRUCTION: Final = 1
# Non-standard command implemented in `rvfi_dii.cpp` (`case 'v'`) to select wire version.
CMD_SET_VERSION: Final = ord("v")

# EndOfTrace with `insn == 0x56455253` ("VERS") probes supported RVFI-DII wire versions.
VERSION_PROBE: Final = 0x56455253
HALT_V1_ONLY: Final = 0x01
HALT_V2_CAPABLE: Final = 0x03

VERSION_REPLY: Final = b"version="
VERSION_REPLY_BYTES: Final = 16

EXEC_V1_BYTES: Final = 88
EXEC_V2_BYTES: Final = 64
EXT_INTEGER_BYTES: Final = 40
EXT_MEMACCESS_BYTES: Final = 88

MAGIC_V2: Final = b"trace-v2"
MAGIC_INTEGER: Final = b"int-data"
MAGIC_MEMORY: Final = b"mem-data"

AVAILABLE_INTEGER: Final = 0
AVAILABLE_MEMORY: Final = 1

# Default hexadecimal digit width for physical addresses (`(physaddrbits_len() + 3) // 4`).
PHYSADDR_DIGITS: Final = 16


def dii(insn: int, *, cmd: int = CMD_INSTRUCTION, time: int = 0) -> bytes:
    """Encode an 8-byte little-endian RVFI-DII instruction packet."""
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
    """Encode an `EndOfTrace` reset packet."""
    return dii(0, cmd=CMD_END_OF_TRACE)


def version_probe() -> bytes:
    return dii(VERSION_PROBE, cmd=CMD_END_OF_TRACE)


def select_version(version: int) -> bytes:
    return dii(version, cmd=CMD_SET_VERSION)


@dataclass(frozen=True)
class Execution:
    """Decoded RVFI-DII execution packet (`wire` = 1 or 2)."""

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
        """True if this packet reports a retired instruction (`halt == 0`)."""
        return self.halt == 0


def _u(data: bytes, at: int, size: int) -> int:
    return int.from_bytes(data[at:at + size], "little")


def decode_v1(data: bytes) -> Execution:
    """Decode an 88-byte RVFI-DII v1 execution packet."""
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
    """Return the total v2 packet length (in bytes) declared in its 64-byte header."""
    if len(head) < EXEC_V2_BYTES:
        raise ValueError(f"a v2 packet's head is {EXEC_V2_BYTES} bytes, got {len(head)}")
    if head[0:8] != MAGIC_V2:
        raise ValueError(f"a v2 packet opens with {MAGIC_V2!r}, got {head[0:8]!r}")
    return _u(head, 8, 8)


def decode_v2(data: bytes) -> Execution:
    """Decode a v2 execution packet (`rvfi_dii_v2.sail`) and its attached extensions."""
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
        # Bit 280 (byte 35, bit 0) carries destination capability tag `rd_tag` (R-15-007i).
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
    """Decode an `rvfi_mask_with_tag` bitmask into `(width_bytes, tag_bit)`, or `None` if 0.

    `rvfi_mask_with_tag` sets bits `0..w-1` for a `w`-byte access and bit `w` when the
    access carries a capability tag. Power-of-two widths disambiguate `w` from `w + 1`
    (length 2 is always a 2-byte untagged access because the capability tag granule is
    8 bytes per R-15-203).
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


# Canonical per-instruction effect order (`R`, `W`, `X`) used when comparing unordered
# RVFI packet fields against ordered commit-trace records.
EFFECT_ORDER: Final = ("R", "W", "X")

# Additional record kinds an executor port may carry beyond standard RVFI (`T` on RTL RVFI).
CARRIABLE: Final = ("T",)


def records(packet: Execution, *, addr_digits: int = PHYSADDR_DIGITS) -> list[str]:
    """Project `packet` into commit-trace record lines (`I`, `R`, `W`, `X`)."""
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
    """Counts of commit-trace records omitted when projecting to an RVFI packet view."""

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


def packet_view(commit: list[str], *,
                carried: frozenset[str] = frozenset()) -> tuple[list[str], Elided]:
    """Project a normalized commit-trace stream to the subset representable in RVFI packets.

    Strips and counts `S`, `C`, `T` (unless in `carried`), and secondary `R`/`W` records
    per instruction, and orders surviving effects in `EFFECT_ORDER` (+ `carried`).
    """
    unknown = carried - frozenset(CARRIABLE)
    if unknown:
        raise ValueError(f"no executor view carries {sorted(unknown)}; the kinds a view "
                         f"may keep beyond the packet's are {CARRIABLE}")
    order = EFFECT_ORDER + tuple(kind for kind in CARRIABLE if kind in carried)
    view: list[str] = []
    counts = dict.fromkeys("SCTRW", 0)
    group: dict[str, list[str]] = {kind: [] for kind in order}

    def flush() -> None:
        for kind in order:
            view.extend(group[kind])
            group[kind].clear()

    for record in commit:
        kind = record[0]
        if kind == "I":
            flush()
            view.append(record)
        elif kind in carried:
            group[kind].append(record)
        elif kind in ("S", "C", "T"):
            counts[kind] += 1
        elif kind == "X":
            group["X"].append(record)
        elif group[kind]:
            counts[kind] += 1
        else:
            group[kind].append(record)
    flush()
    return view, Elided(counts["S"], counts["C"], counts["T"],
                        counts["R"], counts["W"])


def address_digits(view: list[str]) -> int:
    """Infer the hexadecimal address width from the first `R` or `W` record in `view`."""
    for record in view:
        if record[0] in "RW":
            return len(record.split()[1])
    return PHYSADDR_DIGITS
