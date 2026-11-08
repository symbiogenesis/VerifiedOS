# SPDX-License-Identifier: Apache-2.0
"""RTL RVFI v1 frame codec, commit-trace projection, and golden-trace comparison; see
[docs/assurance/rtl-cosimulation-harness.md](../../docs/assurance/rtl-cosimulation-harness.md) and
[docs/assurance/differential-corpus.md](../../docs/assurance/differential-corpus.md).

Frame format (`vos-rtl-rvfi 1`):
- Header: `vos-rtl-rvfi 1`
- Retirement lines: `P <order> <pc_rdata> ... <mem_wdata>` with fixed-width hex fields (`FIELDS`)
- Trailer: `E <count>` matching the number of `P` lines

Decodes and validates retirement continuity (`pc_wdata == next.pc_rdata` for non-trapping
instructions), projects retirements onto the commit-trace grammar via [rvfi.py](rvfi.py)
plus `T` trap-cause records, and adjudicates against the golden trace via [trace.py](trace.py).
"""

import re
from dataclasses import dataclass, replace
from typing import Final

from vos import rvfi, trace

FORMAT: Final = "vos-rtl-rvfi"
VERSION: Final = 1
HEADER: Final = f"{FORMAT} {VERSION}"

# `rvfi.Execution.wire` is 0 for retirements decoded from an RTL text frame rather than RVFI-DII v1/v2.
WIRE: Final = 0

# Ordered `P`-line field names and their fixed hexadecimal digit widths.
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

# Supported memory access byte widths; capability tags require a full 8-byte granule (R-15-203).
_WIDTHS: Final = (1, 2, 4, 8)
_GRANULE: Final = 8
_REGISTERS: Final = 32

# `mcause` interrupt bit and exception-code mask for commit-trace `T` records.
_INTERRUPT_BIT: Final = 63
_CODE_MASK: Final = (1 << _INTERRUPT_BIT) - 1
_WORD: Final = (1 << 64) - 1

# Additional commit-trace record kinds carried by RTL frames beyond RVFI-DII packets.
CARRIED: Final = frozenset({"T"})

# `FrameError.kind` for `pc_wdata != next.pc_rdata` continuity violations.
CONTINUITY: Final = "continuity"


class FrameError(ValueError):
    """Raised when an RTL RVFI frame violates framing, field, or continuity invariants."""

    def __init__(self, line: int, kind: str, message: str) -> None:
        super().__init__(f"line {line}: {kind}: {message}")
        self.line = line
        self.kind = kind


@dataclass(frozen=True)
class Retire:
    """Single RTL retirement combining an `rvfi.Execution` packet and `mcause`."""

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
    """Validate byte `mask` and `tag` and pack them into the format expected by `rvfi.mask_access`."""
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


def _continuous(before: rvfi.Execution, after: rvfi.Execution, number: int) -> None:
    """Verify that a non-trapping retirement's `pc_wdata` equals the next retirement's `pc_rdata`."""
    if not before.trap and before.pc_wdata != after.pc_rdata:
        raise FrameError(number, CONTINUITY,
                         f"retirement {after.order} was fetched from {after.pc_rdata:#x} "
                         f"and the one before it, which did not trap, names "
                         f"{before.pc_wdata:#x} as the next program counter: a retirement "
                         f"was lost, repeated or misreported before the writer")


def decode(text: str) -> list[Retire]:
    """Decode and validate a complete `vos-rtl-rvfi 1` frame into `Retire` records."""
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
            retire = _retire(_parse(line, number), number, len(retires))
            if retires:
                _continuous(retires[-1].packet, retire.packet, number)
            retires.append(retire)
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
    """Serialize `retires` as a `vos-rtl-rvfi 1` frame."""
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
    """Project `retire` into commit-trace records (`rvfi.records` followed by `T` when trapping)."""
    out = rvfi.records(retire.packet, addr_digits=addr_digits)
    if retire.packet.trap:
        interrupt = retire.cause >> _INTERRUPT_BIT
        out.append(f"T {interrupt} {retire.cause & _CODE_MASK}")
    return out


def project(retires: list[Retire], *, addr_digits: int = rvfi.PHYSADDR_DIGITS) -> list[str]:
    """Project `retires` into normalized commit-trace records, rejecting lines outside `COMMIT_RE`."""
    lines = [line for retire in retires for line in records(retire, addr_digits=addr_digits)]
    normalized = trace.normalize_commit(lines)
    if len(normalized) != len(lines):
        bad = next(line for line in lines if not trace.COMMIT_RE.match(line))
        raise ValueError(f"the frame projection is outside the commit grammar: {bad!r}")
    return normalized


def view(reference: list[str]) -> tuple[list[str], rvfi.Elided]:
    """Filter normalized `reference` commit records to the subset representable by an RTL frame (`CARRIED`)."""
    return rvfi.packet_view(trace.normalize_commit(reference), carried=CARRIED)


@dataclass(frozen=True)
class Comparison:
    """Adjudication result comparing an RTL frame against a golden commit trace."""

    verdict: trace.Verdict
    reference: int
    candidate: int
    retired: int
    elided: rvfi.Elided

    @property
    def complete(self) -> bool:
        """Return whether both streams agreed and were consumed in full."""
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
    """Decode `frame` and adjudicate it against the `reference` golden commit trace."""
    retires = decode(frame)
    golden, elided = view(reference)
    return compare_decoded(golden, retires, elided, context=context)


def compare_decoded(golden: list[str], retires: list[Retire], elided: rvfi.Elided, *,
                    context: int = 4) -> Comparison:
    """Adjudicate decoded `retires` against an already-filtered `golden` commit view."""
    projected = project(retires, addr_digits=rvfi.address_digits(golden))
    verdict = trace.adjudicate(golden, projected, context)
    return Comparison(verdict, len(golden), len(projected), len(retires), elided)


# --- reverse projection and carrying-capacity measurement -------------------


@dataclass(frozen=True)
class Refusal:
    """Golden retirement whose effects exceed the capacity of a single RTL frame line."""

    at: int
    pc: int
    insn: int
    reason: str


# Structural reasons a retirement cannot be represented in a single RVFI port record.
REASONS: Final = {
    "wide-access": "an access wider than the eight bytes a curated mask covers",
    "two-addresses": "a read and a write under one instruction at different addresses",
    "two-registers": "more than one register write under one instruction",
    "two-traps": "more than one trap under one instruction",
}


def carry(golden: list[str]) -> tuple[list[Retire], list[Refusal]]:
    """Re-encode a filtered `golden` commit view into `Retire` records and list any `Refusal`s."""
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


# --- seeded retirement mutations --------------------------------------------


@dataclass(frozen=True)
class Seed:
    """Single-retirement field mutation used to test adapter and adjudicator sensitivity."""

    name: str
    what: str


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
    """Apply mutation `name` at `retires[at]`, or return `None` if `retires[at]` is not a witness for `name`."""
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
