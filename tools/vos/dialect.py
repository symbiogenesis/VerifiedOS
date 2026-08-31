# SPDX-License-Identifier: Apache-2.0
"""The frozen dialect's canonical 32-bit encodings, as one table.

This is the encoder half of the corpus assembler (M0.12). It holds one row per mnemonic
the curated model decodes, and nothing else: no parsing, no layout, no
pseudo-instruction, no symbol. Those are [asm.py](asm.py)'s, so that a row here can be
read against the `mapping clause encdec` it mirrors without reading a line of the
assembler around it.

**The rows are generated from the model, not transcribed from it and not read out of the
RISC-V manuals.** They were transcribed once, and the inversion is M1.4-prime's: the table is
now emitted by [dialectgen.py](dialectgen.py) out of the bundle the model writes about
itself, held byte-for-byte by K-88, and loaded here. A fact has one owner and every other
statement of it is generated; a hand-written restatement held equal by a rule is the
older discipline, because the rule can only tell you the two disagree after they already
do.

What that buys is measurable rather than tidy. The transcription carried 353 rows, of
which the generation reproduces 352, and the forms the model decodes that had no row at
all were reachable by no corpus program with nothing saying so. How many rows there are
today is the artifact's own header, which is why no count is written here: a docstring is
not a document `check.py` reads, so a figure in one is a restatement nothing can hold. It
also removes three classes of hand fact: the
branch and jump shift-by-one, which the model states structurally as `imm @ 0b0`; the
`nonzero_rd` refusal on `lc` and the twelve-or-twenty-four refusal on `vkeccak.vi`, which
were one-off rules quoting a clause and are now that clause's own guard; and the
exclusion of `clmulr` beside `clmul` and `clmulh`, which the admission derives from
`Zbc` being off and `Zbkc` on rather than from a comment.

**What is still authored here, each for a named reason.** The register, CSR and special
capability register spellings below are the assembler's vocabulary rather than the
model's encoding: the model encodes a register number and what a program may call it is
this repository's question. And `fence` is one authored row, because it is the one clause
whose `assembly` mapping the emitter leaves as unstructured body text, so the mnemonic it
spells is in the bundle as a skeleton and its operand run is not in the bundle at all.

**What is not here is as deliberate as what is.** The dictionary bundle format of §1.1 is
a fetch container the model does not yet implement, so the image this encoder lays down
is a stream of canonical 32-bit instructions, which is what the curated model fetches
today. The **matrix** surface is absent, and it is not waiting on a datapath: the frozen
profile books the unit and names no mnemonic, operand form or encoding for it, so there
is nothing in the model to generate from and nothing enters by inheritance (R-15-007j).

**The vector rows are no longer scoped, and that is a reversal this cell reports.** M0.8b
carried the vector memory surface and what feeds it, on the ground that a row nothing in
the corpus writes is a row nothing checks. That ground was a transcription cost, and
generation removes it: the table now carries every form the admission admits, the vector
arithmetic included. Nothing in the register, the profile or the plan decides whether it
should, so the widening is reported as an open finding rather than settled here.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from . import corpus
from .dialectgen import TABLE as TABLE_PATH
from .dialectgen import VERSION

# The 32 integer registers, spelled three ways. A register is one register with
# two readings, so `x5`, `t0`, `c5` and `ct0` are the same register and the
# capability spelling is a reading rather than a file (R-15-007i).
ABI_NAMES = (
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
)


def _registers() -> dict[str, int]:
    """Every spelling of every register, built inside a function deliberately.

    A `for` loop at module scope leaves its variables bound in the module, and a
    single-letter index at module scope is one reordering away from shadowing something
    that matters. Nothing here is a defect today; the function is what keeps it that way.
    """
    table: dict[str, int] = {}
    for number, abi in enumerate(ABI_NAMES):
        table[f"x{number}"] = number
        table[f"c{number}"] = number
        table[f"cx{number}"] = number
        table[abi] = number
        table[f"c{abi}"] = number
    table["fp"] = 8
    table["cfp"] = 8
    # The zero register's capability reading holds the null capability, so it is
    # `cnull` rather than `czero` (core/regs.sail).
    table["cnull"] = 0
    return table


REGISTERS: Final[dict[str, int]] = _registers()

# The CSR bank of isa-profile.md §5.1. An address absent from this map is not
# assembled by name; a program wanting one writes the number, and the model
# traps it if the bank does not allocate it (R-15-014).
CSRS: dict[str, int] = {
    "mstatus": 0x300, "misa": 0x301, "mie": 0x304,
    # `mtvec` and `mepc` are the integer *views* of MTCC's and MEPCC's
    # addresses rather than registers of their own (exceptions/sys_exceptions).
    "mtvec": 0x305, "mepc": 0x341,
    "mcause": 0x342, "mtval": 0x343, "mip": 0x344,
    "mvendorid": 0xF11, "marchid": 0xF12, "mimpid": 0xF13,
    "mhartid": 0xF14, "mconfigptr": 0xF15,
    "vstart": 0x008, "vxsat": 0x009, "vxrm": 0x00A, "vcsr": 0x00F,
    "vl": 0xC20, "vtype": 0xC21, "vlenb": 0xC22,
    "dcsr": 0x7B0, "dpc": 0x7B1, "dscratch0": 0x7B2, "dscratch1": 0x7B3,
}

# The special capability register bank `cspecialrw` names (core/cap_regs.sail).
SCRS: dict[str, int] = {"pcc": 0b00000, "mtcc": 0b11100, "mtdc": 0b11101,
                        "mepcc": 0b11111}


def _vregisters() -> dict[str, int]:
    """`v0` through `v31`, and no second spelling of any of them.

    This is a **second table** rather than a fourth spelling of `REGISTERS`.
    The architectural register file is one merged file of 32 registers of 64+1
    bits (R-15-007i) and the vector register file is a separate file of `VLEN`
    bits beside it, so `v5` and `x5` are different registers and a mnemonic
    naming one must not accept the other.

    The integer file has three spellings because a register there has two
    readings and an ABI role (R-15-007i). A vector register has one of each: it
    holds no capability, so there is no `cv3`, and the calling convention names
    none of them, so there is no ABI alias. The table is therefore the
    architectural names alone, which is also how the model's own `vreg_name`
    mapping spells them (extensions/V/vext_regs.sail).
    """
    return {f"v{number}": number for number in range(32)}


VREGISTERS: Final[dict[str, int]] = _vregisters()


class AsmError(Exception):
    """A defect in the program being assembled, reported with its source line by
    the caller. Never raised for a defect in this table, which is an assertion."""


# ---------------------------------------------------------------------------
# The row, and the two shapes it is made of.

@dataclass(frozen=True)
class Slot:
    """One operand of one row: what it is, how wide, and where its bits go.

    `pieces` is `(word_hi, word_lo, src_hi, src_lo)` per run, because a RISC-V immediate
    is scattered and a placement stated as one shift could not say so. `align` is the
    implicit shift the model states as `imm @ 0b0`, derived from the lowest source bit no
    run reaches rather than declared beside it.
    """

    kind: str
    name: str
    width: int
    signed: bool
    align: int
    pieces: tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True)
class Require:
    """One condition on an operand the model's own guard states.

    `ne` is a value the operand may not take and `in` is the set it must be in. Two
    shapes and no more, each generated from the `when` clause that states it: `lc`'s
    `cd != zreg` and `vkeccak.vi`'s `keccak_valid_rounds(rnd)` were the two hand rules
    this table used to carry, and they are the clause now.
    """

    kind: str
    operand: str
    values: tuple[int, ...]
    guard: str


@dataclass(frozen=True)
class Row:
    """One mnemonic: what a program writes, what the encoding fixes, and where the rest
    goes."""

    ctor: str
    site: str
    word: int
    mask: int
    guard: str
    signature: tuple[str, ...]
    slots: tuple[Slot, ...]
    requires: tuple[Require, ...]


# What a diagnostic calls each kind. The immediate kinds take the model's own name for
# the operand, which is the more useful thing to print; the rest are named for what a
# program got wrong rather than for what the model calls the field.
KINDS: Final[dict[str, str]] = {
    "reg": "register", "vreg": "vector register", "vm": "vector mask",
    "csr": "CSR address", "scr": "special capability register",
    "imm": "", "sym": "displacement", "mem": "", "mem0": "", "index": "", "v0": "",
}


def _fence() -> Row:
    """The one authored row, and the reason it is one.

    Every other row here is generated out of the model's paired `encdec` and `assembly`
    clauses. `FENCE`'s `assembly` clause is a `forwards ... when` whose body the emitter
    leaves as unstructured text, so the bundle carries the mnemonic only as a skeleton
    and carries its operand run not at all: there is nothing to generate the spelling
    from. The *encoding* is the model's own and resolves like every other, and it is
    restated here rather than looked up, because a row half generated and half authored
    would be worse to read than one of each.

    Two four-bit ordering sets in the immediate field, predecessor above successor, over
    a zero base register, a zero `funct3` and a zero destination (MISC-MEM,
    extensions/I/base_insts.sail).
    """
    return Row(
        ctor="FENCE",
        site="model/model/extensions/I/base_insts.sail",
        word=0b0001111,
        mask=0xF00FFFFF,
        guard="",
        signature=("imm", "imm"),
        slots=(
            Slot(kind="imm", name="pred", width=4, signed=False, align=1,
                 pieces=((27, 24, 3, 0),)),
            Slot(kind="imm", name="succ", width=4, signed=False, align=1,
                 pieces=((23, 20, 3, 0),)),
        ),
        requires=(),
    )


def _load(root: Path | None = None) -> dict[str, Row]:
    """The generated table, plus the one authored row.

    Read at import, because every caller here wants the whole table and a lazily built
    one would move the cost of a missing artifact from this module's own import to
    whichever caller touched it first.
    """
    here = root or corpus.find_root(Path(__file__).resolve())
    raw = json.loads((here / TABLE_PATH).read_text(encoding="utf-8"))
    header = raw.get("header", {})
    if header.get("version") != VERSION:
        raise AssertionError(
            f"{TABLE_PATH} states version {header.get('version')!r} and this reader is "
            f"written against version {VERSION}; regenerate it with "
            f"`python tools/run.py check --fix`")
    table: dict[str, Row] = {}
    for name, row in raw.get("rows", {}).items():
        table[name] = Row(
            ctor=str(row["ctor"]),
            site=str(row["site"]),
            word=int(row["word"]),
            mask=int(row["mask"]),
            guard=str(row["guard"]),
            signature=tuple(str(kind) for kind in row["signature"]),
            slots=tuple(Slot(kind=str(s["kind"]), name=str(s["name"]),
                             width=int(s["width"]), signed=bool(s["signed"]),
                             align=int(s["align"]),
                             pieces=tuple((int(p[0]), int(p[1]), int(p[2]), int(p[3]))
                                          for p in s["pieces"]))
                        for s in row["slots"]),
            requires=tuple(Require(kind=str(r[0]), operand=str(r[1]),
                                   values=tuple(int(v) for v in r[2]),
                                   guard=str(row["guard"]))
                           for r in row["requires"]),
        )
    # Raised rather than asserted: a duplicated row would silently take the later
    # definition, and `python -O` deletes an `assert`.
    fence = _fence()
    if "fence" in table:
        raise AssertionError("the generated table now carries `fence`, so the authored "
                             "row beside it is a second copy of one fact")
    table["fence"] = fence
    return table


TABLE: Final[dict[str, Row]] = _load()

# Every mnemonic the assembler will encode, for the corpus documentation and for
# the checker's count of this table.
MNEMONICS = tuple(sorted(TABLE))


def signature(mnemonic: str) -> tuple[str, ...]:
    """What a program writes after the mnemonic, in source order."""
    return TABLE[mnemonic].signature


def _fit(slot: Slot, value: int, mnemonic: str) -> int:
    """One operand's value as the bits that reach the word.

    The range and the alignment are the field's own, taken from the model: the width is
    the argument's declared width, the signedness is the reading the model's printer
    names, and the alignment is the implicit shift the `encdec` clause states. What the
    check is *for* is the same as it always was: a field that overflows its slot corrupts
    the neighbouring one silently, so this is where a program's defect is reported rather
    than assembled.
    """
    label = KINDS.get(slot.kind) or slot.name
    if slot.align > 1 and value % slot.align:
        raise AsmError(f"{label} {value} is not a multiple of {slot.align}")
    scaled = value // slot.align
    bits = slot.width - (slot.align.bit_length() - 1)
    low, high = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if slot.signed \
        else (0, (1 << bits) - 1)
    if not low <= scaled <= high:
        raise AsmError(f"{label} {value} is outside "
                       f"[{low * slot.align}, {high * slot.align}]")
    return value & ((1 << slot.width) - 1)


def _required(row: Row, mnemonic: str, values: list[int]) -> None:
    """Every condition the model's own guard places on an operand, at the site.

    Reported as a program's defect with the guard quoted, because that is the whole of
    what it is: the model states `cd != zreg` in the clause that decodes a capability
    load, and an assembler that emitted one anyway would lay down the cache-block
    encoding instead.
    """
    for want in row.requires:
        for slot, value in zip(row.slots, values, strict=True):
            if slot.name != want.operand:
                continue
            spelled = ", ".join(str(v) for v in want.values)
            if want.kind == "ne" and value in want.values:
                raise AsmError(f"{mnemonic} takes no {slot.name} of {spelled}: the "
                               f"model decodes it only `when {want.guard}`")
            if want.kind == "in" and value not in want.values:
                raise AsmError(f"{mnemonic} takes {slot.name} of {spelled} and no "
                               f"other: the model decodes it only "
                               f"`when {want.guard}`")


def encode(mnemonic: str, operands: list[int], pc: int) -> int:
    """The word `mnemonic` with these already-resolved operands encodes to.

    `operands` is flat and in source order, with a `mem` operand contributing its
    displacement and then its base register and an `index` operand its base, its index
    and its scale, which is the order the parser hands them over in and the order the
    model prints them in.
    """
    row = TABLE[mnemonic]
    if len(operands) != len(row.slots):
        raise AssertionError(f"{mnemonic} places {len(row.slots)} operands and was "
                             f"handed {len(operands)}")
    _required(row, mnemonic, operands)
    word = row.word
    for slot, given in zip(row.slots, operands, strict=True):
        # A `sym` is written as a code address and encoded as a displacement from the
        # instruction's own. The two constructors that take one are named in
        # dialectgen.PC_RELATIVE, that being the one fact about an operand the encoding
        # does not carry.
        value = _fit(slot, given - pc if slot.kind == "sym" else given, mnemonic)
        for _word_hi, word_lo, src_hi, src_lo in slot.pieces:
            run = (1 << (src_hi - src_lo + 1)) - 1
            word |= ((value >> src_lo) & run) << word_lo
    # Raised rather than asserted: this is the last thing standing between a
    # mis-generated row and an image the emulator runs anyway. A field that overflows
    # its slot corrupts the neighbouring one silently, and the corpus would report a
    # divergence in the model rather than a defect in this table. `python -O` must not
    # be able to switch that off.
    if not 0 <= word < (1 << 32):
        raise AssertionError(f"{mnemonic} encoded outside 32 bits: {word:#x}")
    return word
