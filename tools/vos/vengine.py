# SPDX-License-Identifier: Apache-2.0
"""RVFI-DII verification engine: DII stream generation, socket session driving,
packet-level seeded defect injection, commit-trace adjudication via
[trace.py](trace.py), and `ddmin` counterexample shrinking."""

import random
import socket
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import IO, Final, Protocol

from vos import dialect, rvfi, trace

MASK64: Final = (1 << 64) - 1

# RVFI-DII reset entry point (`rvfi_handler::get_entry`) and base of the 64 KiB TestRIG RAM window.
ENTRY: Final = 0x8000_0000

# Scratch RAM window accessed via a capability derived from the reset root in `x1`.
DATA: Final = ENTRY + 1024

# Writable register pools for generated streams (`x1` is preserved because reset
# places the root data capability there).
INTEGERS: Final = tuple(range(5, 16))
CAPABILITIES: Final = tuple(range(16, 24))
ADDRESS_REG: Final = 24
AUTHORITY_REG: Final = 25

_ROOT = 1

# Mnemonics from [dialect.py](dialect.py) used by stream templates.
_RR = ("add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and",
       "addw", "subw", "sllw", "srlw", "sraw",
       "mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu",
       "mulw", "divw", "divuw", "remw", "remuw",
       "andn", "orn", "xnor", "max", "maxu", "min", "minu", "rol", "ror",
       "rolw", "rorw", "sh1add", "sh2add", "sh3add", "add.uw",
       "pack", "packh", "packw", "clmul", "clmulh", "xperm4", "xperm8",
       "czero.eqz", "czero.nez", "bclr", "bext", "binv", "bset")

_RI = ("addi", "slti", "sltiu", "xori", "ori", "andi", "addiw")

# Shift-immediate mnemonics paired with their shift-amount bit widths.
_SHIFTS = (("slli", 6), ("srli", 6), ("srai", 6), ("rori", 6), ("slli.uw", 6),
           ("bclri", 6), ("bexti", 6), ("binvi", 6), ("bseti", 6),
           ("slliw", 5), ("srliw", 5), ("sraiw", 5), ("roriw", 5))

_UNARY = ("clz", "ctz", "cpop", "sext.b", "sext.h", "clzw", "ctzw", "cpopw",
          "zext.h", "rev8", "orc.b", "brev8")

# Capability inspections and derivations grouped by operand signature.
_CAP2 = ("cgetperm", "cgettype", "cgetbase", "cgetlen", "cgettag", "cgetsealed",
         "cgetoffset", "cgetaddr", "cgettop", "cmove", "csealentry")
_CAP3 = ("csetaddr", "cincoffset", "candperm", "csetoffset", "csub", "cseqx",
         "ctoptr", "cfromptr")
_CAPI = ("cincoffsetimm",)

_LOADS = (("lb", 1), ("lh", 2), ("lw", 4), ("ld", 8),
          ("lbu", 1), ("lhu", 2), ("lwu", 4))
_STORES = (("sb", 1), ("sh", 2), ("sw", 4), ("sd", 8))

_CAP_LOAD = "lc"
_CAP_STORE = "sc"


class Choices:
    """Deterministic PRNG wrapper for reproducible stream generation."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)  # noqa: S311

    def below(self, bound: int) -> int:
        return self._rng.randrange(bound)

    def among[T](self, items: Sequence[T]) -> T:
        return items[self.below(len(items))]

    def signed(self, bits: int) -> int:
        return self.below(1 << bits) - (1 << (bits - 1))


def _seed_value(rd: int, pick: Choices, out: list[int]) -> None:
    """Seed `rd` with `lui` (imm < 2^19) followed by a signed 12-bit `addi`."""
    out.append(dialect.encode("lui", [rd, pick.below(1 << 19)], 0))
    out.append(dialect.encode("addi", [rd, rd, pick.signed(12)], 0))


def _authority(out: list[int]) -> None:
    """Derive a store capability at `DATA` in `AUTHORITY_REG` from the reset root in `x1`."""
    out.append(dialect.encode("addi", [ADDRESS_REG, 0, 1], 0))
    out.append(dialect.encode("slli", [ADDRESS_REG, ADDRESS_REG, 31], 0))
    out.append(dialect.encode("addi", [ADDRESS_REG, ADDRESS_REG, DATA - ENTRY], 0))
    out.append(dialect.encode("csetaddr", [AUTHORITY_REG, _ROOT, ADDRESS_REG], 0))


def _arith(pick: Choices) -> int:
    kind = pick.below(4)
    rd = pick.among(INTEGERS)
    rs1 = pick.among(INTEGERS)
    if kind == 0:
        return dialect.encode(pick.among(_RR), [rd, rs1, pick.among(INTEGERS)], 0)
    if kind == 1:
        return dialect.encode(pick.among(_RI), [rd, rs1, pick.signed(12)], 0)
    if kind == 2:
        name, width = pick.among(_SHIFTS)
        return dialect.encode(name, [rd, rs1, pick.below(1 << width)], 0)
    return dialect.encode(pick.among(_UNARY), [rd, rs1], 0)


def _cap(pick: Choices) -> int:
    kind = pick.below(3)
    cd = pick.among(CAPABILITIES)
    cs1 = pick.among((*CAPABILITIES, _ROOT, AUTHORITY_REG))
    if kind == 0:
        return dialect.encode(pick.among(_CAP2), [cd, cs1], 0)
    if kind == 1:
        return dialect.encode(pick.among(_CAP3), [cd, cs1, pick.among(INTEGERS)], 0)
    return dialect.encode(pick.among(_CAPI), [cd, cs1, pick.signed(12)], 0)


def _mem(pick: Choices) -> int:
    """Encode an 8-byte-aligned load or store within the 256-byte window at `DATA`."""
    offset = 8 * pick.below(32)
    kind = pick.below(4)
    if kind == 0:
        name, _ = pick.among(_LOADS)
        return dialect.encode(name, [pick.among(INTEGERS), offset, AUTHORITY_REG], 0)
    if kind == 1:
        name, _ = pick.among(_STORES)
        return dialect.encode(name, [pick.among(INTEGERS), offset, AUTHORITY_REG], 0)
    if kind == 2:
        return dialect.encode(_CAP_LOAD, [pick.among(CAPABILITIES), offset, AUTHORITY_REG], 0)
    return dialect.encode(_CAP_STORE, [pick.among(CAPABILITIES), offset, AUTHORITY_REG], 0)


# Block-memory instructions (`cbo.zero`, `cbo.scrub`, `cloadtags`) exceed RVFI-DII's
# 16-byte single-access packet limit and abort the emulator under `--rvfi-dii`; see
# [docs/assurance/differential-corpus.md](../../docs/assurance/differential-corpus.md).
_BLOCK_MASK: Final = ~(0x1F << 15) & 0xFFFFFFFF
_BLOCK_WORDS: Final = frozenset({
    dialect.encode("cbo.zero", [AUTHORITY_REG], 0) & _BLOCK_MASK,
    dialect.encode("cbo.scrub", [AUTHORITY_REG], 0) & _BLOCK_MASK,
})
_CHERI_OPCODE: Final = 0b1011011
_BLOCK_FUNCT5: Final = frozenset({0b10010, 0b10011})


def blocked(word: int) -> bool:
    """Return whether `word` encodes a block memory operation unsupported by RVFI-DII packets."""
    if (word & _BLOCK_MASK) in _BLOCK_WORDS:
        return True
    if (word & 0x7F) != _CHERI_OPCODE or (word >> 25) != 0b1111111:
        return False
    return ((word >> 20) & 0x1F) in _BLOCK_FUNCT5


def _random_word(pick: Choices) -> int:
    """Draw a uniformly random 32-bit instruction word (`bits[1:0] == 0b11`) excluding block ops."""
    while True:
        word = pick.below(1 << 32) | 0b11
        if not blocked(word):
            return word


class Body(Protocol):
    """Per-instruction generator callback for a stream template."""

    def __call__(self, pick: Choices) -> int: ...


@dataclass(frozen=True)
class Template:
    """DII stream template: register/authority preamble flags and per-instruction body generator."""

    name: str
    what: str
    body: Body
    values: bool = True
    authority: bool = False
    root: bool = False


def _preamble(template: Template, pick: Choices) -> list[int]:
    out: list[int] = []
    if template.values:
        for rd in INTEGERS:
            _seed_value(rd, pick, out)
    if template.root:
        out.append(dialect.encode("cmove", [CAPABILITIES[0], _ROOT], 0))
    if template.authority:
        _authority(out)
    return out


def _mixed(pick: Choices) -> int:
    kind = pick.below(3)
    if kind == 0:
        return _arith(pick)
    if kind == 1:
        return _cap(pick)
    return _mem(pick)


TEMPLATES: Final[dict[str, Template]] = {
    "arith": Template("arith", "the integer, M and bit-manipulation surface", _arith),
    "cap": Template("cap", "the capability inspections and monotone derivations",
                    _cap, root=True, authority=True),
    "mem": Template("mem", "loads and stores through a derived authority, data and "
                    "capability alike", _mem, root=True, authority=True),
    "mixed": Template("mixed", "all three, interleaved", _mixed, root=True, authority=True),
    "random": Template("random", "uniformly random 32-bit words, less the block "
                       "operations the packet cannot carry", _random_word,
                       values=False),
}


def generate(template: str, seed: int, count: int) -> list[int]:
    """Generate a DII stream consisting of `template`'s preamble and `count` body instructions."""
    if template not in TEMPLATES:
        raise ValueError(f"no template {template!r}; there are {', '.join(TEMPLATES)}")
    chosen = TEMPLATES[template]
    pick = Choices(seed)
    stream = _preamble(chosen, pick)
    stream.extend(chosen.body(pick) for _ in range(count))
    return stream


# --- RVFI-DII socket session -----------------------------------------------


class Session:
    """Client connection to an RVFI-DII server socket."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._file = sock.makefile("rwb")
        self.wire = 1

    def _send(self, payload: bytes) -> None:
        self._file.write(payload)
        self._file.flush()

    def _read(self, size: int) -> bytes:
        data = self._file.read(size)
        if len(data) != size:
            raise ConnectionError(f"the implementation closed the socket after "
                                  f"{len(data)} of {size} bytes")
        self._quickack()
        return data

    def _quickack(self) -> None:
        """Re-arm `TCP_QUICKACK` after each read so multi-write v2 replies do not stall on delayed ACKs."""
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)

    def _packet(self) -> rvfi.Execution:
        if self.wire == 1:
            return rvfi.decode_v1(self._read(rvfi.EXEC_V1_BYTES))
        head = self._read(rvfi.EXEC_V2_BYTES)
        size = rvfi.v2_trace_size(head)
        return rvfi.decode_v2(head + self._read(size - rvfi.EXEC_V2_BYTES))

    def negotiate(self) -> int:
        """Probe supported RVFI-DII wire versions (`"VERS"`) and select v2 when supported."""
        self._send(rvfi.version_probe())
        answer = rvfi.decode_v1(self._read(rvfi.EXEC_V1_BYTES))
        if answer.halt != rvfi.HALT_V2_CAPABLE:
            self.wire = 1
            return 1
        self._send(rvfi.select_version(2))
        reply = self._read(rvfi.VERSION_REPLY_BYTES)
        if reply[0:8] != rvfi.VERSION_REPLY:
            raise ConnectionError(f"the version reply opens {reply[0:8]!r}, "
                                  f"not {rvfi.VERSION_REPLY!r}")
        selected = int.from_bytes(reply[8:16], "little")
        if selected != 2:
            raise ConnectionError(f"asked for wire format 2 and was given {selected}")
        self.wire = 2
        return 2

    def drive(self, stream: Sequence[int]) -> list[rvfi.Execution]:
        """Inject `stream`, collect retired execution packets, and send `EndOfTrace` to reset state."""
        packets: list[rvfi.Execution] = []
        for word in stream:
            self._send(rvfi.instruction(word))
            packets.append(self._packet())
        self._send(rvfi.end_of_trace())
        self._packet()
        return [p for p in packets if p.retired]

    def close(self) -> None:
        """Close the socket so the RVFI-DII server exits on EOF."""
        self._file.close()
        self._sock.close()


def free_port() -> int:
    """Return an ephemeral loopback TCP port number."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def connect(port: int, child: subprocess.Popen[bytes], *, timeout: float = 30.0) -> Session:
    """Poll `127.0.0.1:port` until `child` accepts a connection, or fail if `child` exits or times out."""
    deadline = time.monotonic() + timeout
    while True:
        if child.poll() is not None:
            raise ConnectionError(
                f"the implementation exited with {child.returncode} before listening "
                f"on port {port}")
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        except OSError:
            if time.monotonic() > deadline:
                raise ConnectionError(
                    f"nothing was listening on port {port} within {timeout:g}s") from None
            time.sleep(0.02)
        else:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return Session(sock)


def spawn(simulator: Path, profile: Path, port: int, log: IO[bytes], *,
          trace_output: Path | None = None) -> subprocess.Popen[bytes]:
    """Launch the Sail emulator as an RVFI-DII server on `port`.

    When `trace_output` is given, `--trace-commit` writes directly to that file so
    buffered stdout commit records and unbuffered stderr RVFI diagnostics never interleave.
    """
    argv = [str(simulator), "--config", str(profile), "--rvfi-dii", str(port),
            "--disable-trap-loop-detection"]
    if trace_output is not None:
        argv += ["--trace-commit", "--trace-output", str(trace_output)]
    return subprocess.Popen(argv, stdout=log, stderr=log)


# --- seeded packet-level defects -------------------------------------------


class Mutation(Protocol):
    """Packet-level mutation modeling an executor defect."""

    def __call__(self, packet: rvfi.Execution) -> rvfi.Execution: ...


@dataclass(frozen=True)
class Defect:
    name: str
    what: str
    witness: str
    apply: Mutation


_OP_32: Final = 0b0111011
_OP_IMM_32: Final = 0b0011011
_LOAD: Final = 0b0000011
_UNSIGNED_FUNCT3: Final = frozenset({0b100, 0b101, 0b110})


def _w_form_no_sext(packet: rvfi.Execution) -> rvfi.Execution:
    if packet.rd_addr and (packet.insn & 0x7F) in (_OP_32, _OP_IMM_32):
        return replace(packet, rd_wdata=packet.rd_wdata & 0xFFFFFFFF)
    return packet


def _tag_dropped(packet: rvfi.Execution) -> rvfi.Execution:
    if packet.rd_tag:
        return replace(packet, rd_tag=False)
    return packet


def _store_tag_dropped(packet: rvfi.Execution) -> rvfi.Execution:
    access = rvfi.mask_access(packet.mem_wmask)
    if access is None or not access[1]:
        return packet
    width, _ = access
    return replace(packet, mem_wmask=packet.mem_wmask & ~(1 << width))


def _load_sign_extends(packet: rvfi.Execution) -> rvfi.Execution:
    if (packet.insn & 0x7F) != _LOAD or ((packet.insn >> 12) & 0x7) not in _UNSIGNED_FUNCT3:
        return packet
    access = rvfi.mask_access(packet.mem_rmask)
    if access is None:
        return packet
    width, _ = access
    top = 1 << (8 * width - 1)
    value = packet.rd_wdata & ((1 << (8 * width)) - 1)
    if not value & top:
        return packet
    return replace(packet, rd_wdata=(value | (MASK64 ^ ((1 << (8 * width)) - 1))) & MASK64)


DEFECTS: Final[dict[str, Defect]] = {
    "w-form-no-sext": Defect(
        "w-form-no-sext",
        "a second executor that computes the W forms in 32 bits and forgets to "
        "sign-extend the result back to XLEN",
        "a W-form instruction whose 32-bit result has its top bit set",
        _w_form_no_sext),
    "tag-dropped": Defect(
        "tag-dropped",
        "a second executor that reports the integer reading of a register write "
        "and not the tag beside it (R-15-007i)",
        "an instruction that writes a tagged capability to a register",
        _tag_dropped),
    "store-tag-dropped": Defect(
        "store-tag-dropped",
        "a second executor whose store reports the byte mask without the tag bit "
        "above it, so a capability store reads as a store of the same 64 bits as data",
        "a capability store of a tagged capability",
        _store_tag_dropped),
    "load-sign-extends": Defect(
        "load-sign-extends",
        "a second executor that ignores a load's unsigned flag and sign-extends "
        "the delivered value",
        "an unsigned load whose top loaded bit is set",
        _load_sign_extends),
}


def seeded(packets: Sequence[rvfi.Execution], defect: Defect) -> list[rvfi.Execution]:
    """Apply `defect` to every packet in `packets`."""
    return [defect.apply(packet) for packet in packets]


# --- adjudication ----------------------------------------------------------


def project(packets: Sequence[rvfi.Execution], *,
            addr_digits: int = rvfi.PHYSADDR_DIGITS) -> list[str]:
    """Project `packets` into normalized commit-trace records, rejecting lines outside `COMMIT_RE`."""
    lines: list[str] = []
    for packet in packets:
        lines.extend(rvfi.records(packet, addr_digits=addr_digits))
    records = trace.normalize_commit(lines)
    if len(records) != len(lines):
        bad = next(line for line in lines if not trace.COMMIT_RE.match(line))
        raise ValueError(f"the packet projection is outside the commit grammar: {bad!r}")
    return records


def adjudicate(reference: Sequence[rvfi.Execution], candidate: Sequence[rvfi.Execution],
               *, addr_digits: int = rvfi.PHYSADDR_DIGITS,
               context: int = 4) -> trace.Verdict:
    """Adjudicate two RVFI packet streams after projecting both into commit-trace records."""
    return trace.adjudicate(project(reference, addr_digits=addr_digits),
                            project(candidate, addr_digits=addr_digits), context)


# --- shrinking -------------------------------------------------------------


def shrink(stream: Sequence[int], diverges: Callable[[Sequence[int]], bool],
           *, budget: int = 4000) -> tuple[list[int], int]:
    """Minimize a diverging DII `stream` with `ddmin` within `budget` re-executions."""
    best = list(stream)
    runs = 0
    width = 2
    while len(best) >= 2 and runs < budget:
        chunk = max(len(best) // width, 1)
        starts = list(range(0, len(best), chunk))

        # Test single chunks first before testing their complements.
        cut = None
        for start in starts:
            if runs >= budget:
                break
            runs += 1
            candidate = best[start:start + chunk]
            if diverges(candidate):
                cut = candidate
                break
        if cut is not None:
            best, width = cut, 2
            continue

        for start in starts:
            candidate = best[:start] + best[start + chunk:]
            if len(candidate) == len(best):
                continue
            if runs >= budget:
                break
            runs += 1
            if diverges(candidate):
                cut = candidate
                break
        if cut is not None:
            best = cut
            width = max(width - 1, 2)
        elif width >= len(best):
            break
        else:
            width = min(width * 2, len(best))
    return best, runs
