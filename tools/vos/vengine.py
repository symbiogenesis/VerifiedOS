# SPDX-License-Identifier: Apache-2.0
"""The verification engine: it generates DII streams, drives an implementation
over RVFI-DII, adjudicates what comes back, and shrinks a counterexample.

TestRIG's own phrasing is the whole of the design: *vengines generate one or
more DII streams of instruction traces, and consume one or more RVFI streams of
execution traces*. This module is that role, in the one language this directory
carries, and it is a **binding** rather than a second TestRIG: what it holds is
the protocol and the shrinker, and everything it decides about behaviour it
decides through [trace.py](trace.py)'s adjudicator, which is the one this
repository already had.

Three things the corpus cannot do at all, and they are why this exists:

- **The sequence is under control.** A DII stream is instructions, not a
  program: nothing is fetched, so there is no layout, no linker, and no
  requirement that the stream be reachable code.
- **A counterexample shrinks.** `shrink` below is delta debugging over the
  stream, and it re-runs the implementation on each candidate rather than
  reasoning about which instruction mattered.
- **Generation does not depend on a person choosing what to write next**, which
  is the argument M2.1's 21,546 vectors and R1a's 658,659 already made here.

**What it does not have is a second executor.** M2's CHERI-QEMU fork is struck
and the RTL is R1b's, so today the second side is this one under a **seeded
defect**: `DEFECTS` below are packet-level mutations standing for the ways a
second implementation of the frozen profile gets an answer wrong, and each is
written so that most instructions do not expose it. That is what makes shrinking
a real measurement rather than a demonstration over a stream where every
instruction is a witness. When R2 supplies the RTL's `rvfi` port, `Session`
below is what it connects to and nothing else here changes.
"""

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

# The reset entry point RVFI-DII fixes, `rvfi_handler::get_entry`, which is also
# the address TestRIG's 64 KiB memory contract puts memory at.
ENTRY: Final = 0x8000_0000

# Where a generated stream puts the data it touches. It is inside the frozen
# profile's RAM and is reached through a capability derived from the reset root,
# because there is no default data capability and no integer-addressed access on
# this machine (R-15-001c): an integer base register would be read as an
# untagged capability and fault.
DATA: Final = ENTRY + 1024

# The registers a generated stream is allowed to write. `x1` is never among them
# because reset hands it the root **data** capability, which is the only store
# authority a stream has and which `x1` being the link register already makes
# fragile (M0.12's second finding).
INTEGERS: Final = tuple(range(5, 16))
CAPABILITIES: Final = tuple(range(16, 24))
ADDRESS_REG: Final = 24
AUTHORITY_REG: Final = 25

_ROOT = 1

# --- what a generated stream may contain -----------------------------------
#
# Every mnemonic below is a row of [dialect.py](dialect.py), so a stream is
# encoded by the same table the corpus assembles through rather than by a second
# encoder written here.

_RR = ("add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and",
       "addw", "subw", "sllw", "srlw", "sraw",
       "mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu",
       "mulw", "divw", "divuw", "remw", "remuw",
       "andn", "orn", "xnor", "max", "maxu", "min", "minu", "rol", "ror",
       "rolw", "rorw", "sh1add", "sh2add", "sh3add", "add.uw",
       "pack", "packh", "packw", "clmul", "clmulh", "xperm4", "xperm8",
       "czero.eqz", "czero.nez", "bclr", "bext", "binv", "bset")

_RI = ("addi", "slti", "sltiu", "xori", "ori", "andi", "addiw")

# The shift-immediate forms, with the width of the shift amount each admits.
_SHIFTS = (("slli", 6), ("srli", 6), ("srai", 6), ("rori", 6), ("slli.uw", 6),
           ("bclri", 6), ("bexti", 6), ("binvi", 6), ("bseti", 6),
           ("slliw", 5), ("srliw", 5), ("sraiw", 5), ("roriw", 5))

_UNARY = ("clz", "ctz", "cpop", "sext.b", "sext.h", "clzw", "ctzw", "cpopw",
          "zext.h", "rev8", "orc.b", "brev8")

# The capability inspections and derivations, split by what they take. Every one
# of them writes a register, which is what makes a tag observable at all.
_CAP2 = ("cgetperm", "cgettype", "cgetbase", "cgetlen", "cgettag", "cgetsealed",
         "cgetoffset", "cgetaddr", "cgettop", "cmove", "csealentry")
_CAP3 = ("csetaddr", "cincoffset", "candperm", "csetoffset", "csub", "cseqx",
         "ctoptr", "cfromptr")
_CAPI = ("cincoffsetimm",)

_LOADS = (("lb", 1), ("lh", 2), ("lw", 4), ("ld", 8),
          ("lbu", 1), ("lhu", 2), ("lwu", 4))
_STORES = (("sb", 1), ("sh", 2), ("sw", 4), ("sd", 8))

# The frozen dialect's own capability load and store, which are what puts a tag
# in memory and takes one back out.
_CAP_LOAD = "lc"
_CAP_STORE = "sc"


class Choices:
    """A seeded source of decisions, so a run reproduces from its seed alone.

    One class rather than a bare `random.Random` at every site, because the
    generator's whole reproducibility claim rests on there being exactly one
    stream of decisions and one place it is seeded.
    """

    def __init__(self, seed: int) -> None:
        # Not a cryptographic generator and not asked to be: what it seeds is a
        # test stream whose only requirement is that the same seed replays it.
        self._rng = random.Random(seed)  # noqa: S311

    def below(self, bound: int) -> int:
        return self._rng.randrange(bound)

    def among[T](self, items: Sequence[T]) -> T:
        return items[self.below(len(items))]

    def signed(self, bits: int) -> int:
        return self.below(1 << bits) - (1 << (bits - 1))


def _seed_value(rd: int, pick: Choices, out: list[int]) -> None:
    """Put an arbitrary 64-bit-ish value in `rd`.

    Every register is the null capability at reset, so a stream that opens with
    arithmetic is arithmetic over zeroes and exercises one point of every
    operation's domain. The upper immediate is kept below 2^19 so that `lui`'s
    sign extension does not put the value in the negative half by construction;
    the `addi` beside it reaches the negative half on its own, which is what the
    W-form defect needs a witness for.
    """
    out.append(dialect.encode("lui", [rd, pick.below(1 << 19)], 0))
    out.append(dialect.encode("addi", [rd, rd, pick.signed(12)], 0))


def _authority(out: list[int]) -> None:
    """Derive a store authority at `DATA` from the reset root.

    Four instructions and no immediate wider than twelve bits: one, shifted to
    the entry point, offset to the data window, and turned into a capability by
    `csetaddr` off the root the reset put in `x1`.
    """
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
    """One access through the derived authority.

    The offset is a multiple of eight inside a 256-byte window, so a capability
    access is aligned by construction and every access lands in the same page.
    Alignment is not a rule of the protocol; it is what keeps a generated stream
    exercising the access rather than the alignment trap over and over.
    """
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


# The words a stream must not contain, and the reason is the packet rather than
# the machine. `cbo.zero` writes a 64-byte block and `cloadtags` reads eight
# granules, and `rvfi_write` and `rvfi_read` raise an internal error above
# sixteen bytes: the packet has one memory access per instruction and no form
# for a block, so under `--rvfi-dii` those instructions **stop the emulator**
# rather than reporting something narrower. The commit trace carries them and
# the packet does not, which is exactly what
# [docs/differential-corpus.md](../../docs/differential-corpus.md) §5 says, seen
# from the side that has to generate around it.
_BLOCK_MASK: Final = ~(0x1F << 15) & 0xFFFFFFFF
_BLOCK_WORDS: Final = frozenset({
    dialect.encode("cbo.zero", [AUTHORITY_REG], 0) & _BLOCK_MASK,
    dialect.encode("cbo.scrub", [AUTHORITY_REG], 0) & _BLOCK_MASK,
})
_CHERI_OPCODE: Final = 0b1011011
_BLOCK_FUNCT5: Final = frozenset({0b10010, 0b10011})


def blocked(word: int) -> bool:
    """Whether a word is one of the block operations the RVFI packet cannot carry."""
    if (word & _BLOCK_MASK) in _BLOCK_WORDS:
        return True
    if (word & 0x7F) != _CHERI_OPCODE or (word >> 25) != 0b1111111:
        return False
    return ((word >> 20) & 0x1F) in _BLOCK_FUNCT5


def _random_word(pick: Choices) -> int:
    """A uniformly random word that is a 32-bit instruction and not a block operation.

    The low two bits are forced to `11` because this profile excludes `C` and
    fixes ILEN at 32, so a word without them is not an instruction this machine
    has. `rvfi_fetch` nonetheless takes upstream's compressed branch on one, and
    the two emitters then say different things about the same injected word: the
    commit trace's `fetch_callback` reports the sixteen-bit halfword the model
    decoded, while `rvfi_insn` was set to the whole word before that branch was
    taken. Which of the two is right is the model's question and not the
    generator's, and it is recorded rather than smoothed over; what the
    generator owes is not to spend its stream on encodings the profile does not
    have.
    """
    while True:
        word = pick.below(1 << 32) | 0b11
        if not blocked(word):
            return word


class Body(Protocol):
    """What every template's per-instruction generator is."""

    def __call__(self, pick: Choices) -> int: ...


@dataclass(frozen=True)
class Template:
    """A named way of generating a stream: a preamble, then a body repeated.

    The preamble is a property of the machine rather than of the template's
    taste. On a purecap machine with no default data capability the authority a
    memory access needs does not exist until a stream derives one, and every
    register holds the null capability until a stream puts something in it.
    """

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
    """A DII stream: the template's preamble, then `count` generated instructions."""
    if template not in TEMPLATES:
        raise ValueError(f"no template {template!r}; there are {', '.join(TEMPLATES)}")
    chosen = TEMPLATES[template]
    pick = Choices(seed)
    stream = _preamble(chosen, pick)
    stream.extend(chosen.body(pick) for _ in range(count))
    return stream


# --- the socket ------------------------------------------------------------


class Session:
    """One conversation with one implementation over one RVFI-DII socket.

    The implementation is the **server** and the engine is the client, which is
    TestRIG's own arrangement and is why the emulator prints a port and waits.
    """

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
        """Acknowledge at once rather than on a timer.

        This is worth 47 ms per instruction and the arithmetic behind that is
        the point rather than the number. A v2 reply is **two or three separate
        writes**, the packet and each extension the model announces, and the
        emulator's socket is Nagle-governed: the second write waits for the
        first to be acknowledged. Nothing here has anything to send back until
        the whole reply has arrived, so the kernel has nothing to piggyback the
        acknowledgement on and holds it for the delayed-acknowledgement timer,
        which is where the 47 ms comes from and why it is the same 47 ms
        whatever the instruction was. `TCP_NODELAY` on this side does not reach
        it: the write being held is the *implementation's*. Quick
        acknowledgement is one-shot in Linux's stack, so it is re-armed after
        every read rather than set once at connect.
        """
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)

    def _packet(self) -> rvfi.Execution:
        if self.wire == 1:
            return rvfi.decode_v1(self._read(rvfi.EXEC_V1_BYTES))
        head = self._read(rvfi.EXEC_V2_BYTES)
        size = rvfi.v2_trace_size(head)
        return rvfi.decode_v2(head + self._read(size - rvfi.EXEC_V2_BYTES))

    def negotiate(self) -> int:
        """Ask which wire formats the implementation has, and take the widest.

        The probe is an `EndOfTrace` whose instruction word is the ASCII "VERS",
        which is a reset in every field a reader can see and a question by
        convention. The reply is a v1-shaped packet whose halt byte is 1 for an
        implementation that has only v1 and 3 for one that also has v2; the
        second is then selected with a `v` command and acknowledged by an
        eight-byte string and the version.
        """
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
        """Inject one stream, collect what it retired, and reset.

        The `EndOfTrace` at the end is what makes each stream a run of its own:
        it resets registers, memory and the PC, so the next candidate a shrinker
        sends is not a continuation of the last. Its acknowledgement carries the
        halt byte and is not a retirement, so it is read and dropped.
        """
        packets: list[rvfi.Execution] = []
        for word in stream:
            self._send(rvfi.instruction(word))
            packets.append(self._packet())
        self._send(rvfi.end_of_trace())
        self._packet()
        return [p for p in packets if p.retired]

    def close(self) -> None:
        """Close, which the implementation reads as EOF and exits on."""
        self._file.close()
        self._sock.close()


def free_port() -> int:
    """A port nothing is listening on, for an implementation that binds one.

    The emulator takes the port as an argument and `--rvfi-dii` refuses zero, so
    the engine has to choose. Binding and closing leaves a window in which
    something else could take it, which `connect` below reports rather than
    hangs on.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def connect(port: int, child: subprocess.Popen[bytes], *, timeout: float = 30.0) -> Session:
    """Connect once the implementation is listening, or say why it never was.

    There is no readiness event to wait on: the emulator announces its port on a
    stdout that is block-buffered into a pipe, and that same pipe is where the
    commit trace goes, so the announcement does not arrive until the run is
    over. What is polled instead is the thing actually being waited for, and the
    child is checked on every attempt so that an implementation that died is
    reported as dead rather than as slow.
    """
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
            # The conversation is one eight-byte question and one short answer
            # per instruction, which is the shape Nagle's algorithm delays: with
            # it on, a stream is paced by the peer's delayed acknowledgement
            # rather than by either machine, and a shrinker that re-runs the
            # stream hundreds of times pays that on every packet of every run.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return Session(sock)


def spawn(simulator: Path, profile: Path, port: int, log: IO[bytes], *,
          trace_output: Path | None = None) -> subprocess.Popen[bytes]:
    """The curated emulator, in the role of an RVFI-DII implementation.

    `--disable-trap-loop-detection` is passed because the detector is a property
    of a *program*: under direct instruction injection the engine chooses what
    executes next, so a stream of instructions that each trap is a stream the
    engine meant to send and not a machine that has stopped making progress.

    `--trace-commit` is passed where the caller wants both dialects out of one
    run. The two callback classes are registered independently, so the packets
    go over the socket and the records go to the trace log at the same time and
    say the same thing about the same step, which is what makes the two formats
    comparable without a second run to align against.

    **The trace goes to a file of its own and never to the shared stream**, and
    that is a correctness requirement rather than tidiness. The commit trace's
    default destination is `stdout`, which is block-buffered into a pipe, while
    the emulator's RVFI diagnostics go to an unbuffered `stderr`; and the
    end-of-trace acknowledgement is printed verbosely whatever `--trace-rvfi`
    says, `rvfi_dii.cpp` passing `trace_version != 0` where every other call
    site passes the flag. Captured on one descriptor the diagnostic lands inside
    whichever record the stdout buffer had half-written, which is a torn record
    rather than a lost one, so a reader sees a *divergence* about a run that
    agreed.
    """
    argv = [str(simulator), "--config", str(profile), "--rvfi-dii", str(port),
            "--disable-trap-loop-detection"]
    if trace_output is not None:
        argv += ["--trace-commit", "--trace-output", str(trace_output)]
    return subprocess.Popen(argv, stdout=log, stderr=log)


# --- the seeded second executor --------------------------------------------


class Mutation(Protocol):
    """What a seeded defect is: one packet in, one packet out."""

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
    """The same run as a second executor carrying `defect` would have reported it."""
    return [defect.apply(packet) for packet in packets]


# --- adjudication ----------------------------------------------------------


def project(packets: Sequence[rvfi.Execution], *,
            addr_digits: int = rvfi.PHYSADDR_DIGITS) -> list[str]:
    """A packet stream as commit-trace records, in the schema's own grammar.

    The projection is handed to [trace.py](trace.py)'s normalizer rather than
    used raw, which is what holds it to that grammar: a record the normalizer
    does not recognize would otherwise be dropped, and a projection quietly
    losing records is a rig that agrees about less than it says it does.
    """
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
    """Two implementations' packets, walked until they disagree."""
    return trace.adjudicate(project(reference, addr_digits=addr_digits),
                            project(candidate, addr_digits=addr_digits), context)


# --- shrinking -------------------------------------------------------------


def shrink(stream: Sequence[int], diverges: Callable[[Sequence[int]], bool],
           *, budget: int = 4000) -> tuple[list[int], int]:
    """Delta debugging over a DII stream: the shortest prefix-free subsequence
    that still makes the two executors disagree, and how many runs it took.

    This is Zeller and Hildebrandt's ddmin, and the reason it applies to a DII
    stream where it does not apply to a program is that an injected stream has
    **no layout**: nothing is fetched, so deleting an instruction moves no
    branch target and breaks no reachability. A stream carrying control flow
    would need the `rvfi_time` field, which is what TestRIG carries it for.

    `diverges` re-runs the implementation on each candidate rather than
    reasoning about which instruction mattered, so what comes back is a stream
    that has been *shown* to still fail. The budget bounds the number of runs,
    because the worst case is quadratic in the stream and a rig that cannot be
    interrupted is one nobody runs on a long stream.
    """
    best = list(stream)
    runs = 0
    width = 2
    while len(best) >= 2 and runs < budget:
        chunk = max(len(best) // width, 1)
        starts = list(range(0, len(best), chunk))

        # A subset first, because a stream whose witness sits in one part is cut
        # to that part in a single run where the complements would take `width`.
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
