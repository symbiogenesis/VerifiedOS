# SPDX-License-Identifier: Apache-2.0
"""The frozen dialect's canonical 32-bit encodings, as one table.

This is the encoder half of the corpus assembler (M0.12). It holds one row per
mnemonic the curated model decodes, and nothing else: no parsing, no layout, no
pseudo-instruction, no symbol. Those are [asm.py](asm.py)'s, so that a row here
can be read against the `mapping clause encdec` it mirrors without reading a
line of the assembler around it.

**The rows are transcribed from the model, not from the RISC-V manuals.** Where
the two differ the model is what the corpus must run on, and they do differ:
`auipcc`, `cjal` and `cjalr` hold the base encodings of `auipc`, `jal` and
`jalr` because one ABI mode means there is no integer form to distinguish them
from ([isa-profile.md](../../docs/isa-profile.md) §1, R-15-001); `lc` sits at
MISC-MEM `funct3` 010 beside `cbo.zero` and is separated from it by a non-zero
destination; and `sc` is the capability store at STORE `funct3` 100 rather than
a store-conditional, `Zalrsc` having gone with the reservation (R-15-025).

**What is not here is as deliberate as what is.** The dictionary bundle format
of §1.1 is a fetch container the model does not yet implement, so the image this
encoder lays down is a stream of canonical 32-bit instructions, which is what
the curated model fetches today. The matrix and FEC surface is absent because
the datapaths those classes name arrive with M0.8c and M0.8d; the corpus version
that follows each of those adds its rows rather than this one anticipating them.

**The vector rows are M0.8b's, and they are the memory surface and what feeds
it** rather than the whole of RVV. The item that adds them is about the
capability semantics of a vector access, so what a program has to be able to
write is every form whose element addresses are made differently: unit-stride,
fault-only-first, runtime-strided, indexed in both orderings, whole-register,
and the mask pair, at all four element widths. The arithmetic is not here,
because a row nothing in the corpus writes is a row nothing checks.
"""

from dataclasses import dataclass
from typing import Final, Protocol

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

    A `for` loop at module scope leaves its variables bound in the module, and the
    obvious name for the index here is `_i`, which is also the name of the I-type
    encoder below. Nothing went wrong, because the encoder is defined after the loop
    and rebinds the name; but the module was one reordering away from every I-type
    instruction encoding through an integer, and the failure would have been
    `'int' object is not callable` far from its cause.
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

OP_IMM = 0b0010011
OP_IMM_32 = 0b0011011
OP = 0b0110011
OP_32 = 0b0111011
LOAD = 0b0000011
STORE = 0b0100011
BRANCH = 0b1100011
MISC_MEM = 0b0001111
SYSTEM = 0b1110011
AMO = 0b0101111
# The capability opcode ISAv9 allocates, carried across at the transplant.
CHERI = 0b1011011
# The one custom opcode the profile's own rows share. ISAv9 already spent
# custom-2 on the whole capability surface above, so the rows M0.6g adds take
# custom-0 between them and are separated by `funct3`, leaving custom-1 and
# custom-3 whole for the rows the freeze's measured act admits (R-15-014a).
CUSTOM_0 = 0b0001011

# --- the vector surface's three opcodes (M0.8b) ----------------------------
# The two the vector memory surface uses are the base ISA's floating-point load
# and store majors, which this profile has no other claimant for: scalar F and D
# went at c4 with the register file they addressed (R-15-039), so `0000111` and
# `0100111` carry vector accesses and nothing else. `OP_V` is RVV's own major.
LOAD_FP = 0b0000111
STORE_FP = 0b0100111
OP_V = 0b1010111

# The width code a vector access carries in its `funct3`, which is RVV's own
# encoding of EEW and is not the base ISA's: 8-bit is 000 and the other three
# start at 101 (`encdec_vlewidth`, extensions/V/vext_mem_insts.sail).
VLEWIDTH = {8: 0b000, 16: 0b101, 32: 0b110, 64: 0b111}


def _vregisters() -> dict[str, int]:
    """`v0` through `v31`, and no second spelling of any of them.

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
# Field assembly. Each helper takes already-checked fields and returns the word,
# so range checking is one place (`_imm`) rather than one place per format.

def _imm(value: int, bits: int, *, signed: bool, name: str, align: int = 1) -> int:
    if align > 1 and value % align:
        raise AsmError(f"{name} {value} is not a multiple of {align}")
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    if not lo <= value <= hi:
        raise AsmError(f"{name} {value} is outside [{lo}, {hi}]")
    return value & ((1 << bits) - 1)


def _r(funct7: int, rs2: int, rs1: int, funct3: int, rd: int, op: int) -> int:
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | op


def _i(imm: int, rs1: int, funct3: int, rd: int, op: int) -> int:
    return (imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | op


def _s(imm: int, rs2: int, rs1: int, funct3: int, op: int) -> int:
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | \
        (funct3 << 12) | ((imm & 0x1F) << 7) | op


def _b(imm: int, rs2: int, rs1: int, funct3: int, op: int) -> int:
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) | \
        (rs1 << 15) | (funct3 << 12) | (((imm >> 1) & 0xF) << 8) | \
        (((imm >> 11) & 1) << 7) | op


def _u(imm20: int, rd: int, op: int) -> int:
    return (imm20 << 12) | (rd << 7) | op


def _j(imm: int, rd: int, op: int) -> int:
    return (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) | \
        (((imm >> 11) & 1) << 20) | (((imm >> 12) & 0xFF) << 12) | (rd << 7) | op


# ---------------------------------------------------------------------------
# The kinds. `operands` is the signature the parser fills, in source order:
#
#   reg   a register, in any of its three spellings
#   imm   an integer expression
#   sym   an integer expression naming a code address (branch and jump targets)
#   mem   `imm(reg)`, which the parser flattens into (imm, reg)
#   csr   a CSR by name or number
#   scr   a special capability register by name
#   vreg  a vector register, `v0` through `v31`
#   vm    the vector mask: `v0.t`, or nothing at all where the form is unmasked
#
# `emit(fields, ops, pc)` builds the word. `pc` is the address of the
# instruction, which only the pc-relative kinds read.

# The fields a row carries into its encoder: the constant bits of the encoding,
# named as the `mapping clause encdec` names them. `bool` is an `int` here and is
# meant to be, so a flag field like `signed` sits in the same table as `funct3`.
Fields = dict[str, int]


class Emit(Protocol):
    """What every kind's encoder is, stated once so the table below is checked.

    This is the reason the protocol exists rather than the encoders being stored as
    plain objects: `KINDS` is a dispatch table, and a table of callbacks that
    nothing types is a table where a member with the wrong arity or the wrong
    argument order is found by running the corpus, not by reading the module.
    """

    def __call__(self, f: Fields, o: list[int], pc: int) -> int: ...


@dataclass(frozen=True)
class Kind:
    operands: tuple[str, ...]
    emit: Emit


def _k_r(f: Fields, o: list[int], pc: int) -> int:
    return _r(f["funct7"], o[2], o[1], f["funct3"], o[0], f["op"])


def _k_i(f: Fields, o: list[int], pc: int) -> int:
    return _i(_imm(o[2], 12, signed=True, name="immediate"), o[1], f["funct3"], o[0], f["op"])


def _k_shift(f: Fields, o: list[int], pc: int) -> int:
    """Shift-immediate, where the shift amount's width says which base it is: six
    bits for the XLEN forms and five for the `W` forms, the top bits of the
    funct7 field carrying the operation."""
    width = f["shamt_bits"]
    shamt = _imm(o[2], width, signed=False, name="shift amount")
    return ((f["funct7"] | shamt) << 20) | (o[1] << 15) | (f["funct3"] << 12) | (o[0] << 7) | f["op"]


def _k_load(f: Fields, o: list[int], pc: int) -> int:
    return _i(_imm(o[1], 12, signed=True, name="offset"), o[2], f["funct3"], o[0], f["op"])


def _k_store(f: Fields, o: list[int], pc: int) -> int:
    return _s(_imm(o[1], 12, signed=True, name="offset"), o[0], o[2], f["funct3"], f["op"])


def _k_branch(f: Fields, o: list[int], pc: int) -> int:
    return _b(_imm(o[2] - pc, 13, signed=True, name="branch displacement", align=2),
              o[1], o[0], f["funct3"], f["op"])


def _k_u(f: Fields, o: list[int], pc: int) -> int:
    return _u(_imm(o[1], 20, signed=False, name="upper immediate"), o[0], f["op"])


def _k_jal(f: Fields, o: list[int], pc: int) -> int:
    return _j(_imm(o[1] - pc, 21, signed=True, name="jump displacement", align=2),
              o[0], f["op"])


def _k_jalr(f: Fields, o: list[int], pc: int) -> int:
    return _i(_imm(o[2], 12, signed=True, name="offset"), o[1], f["funct3"], o[0], f["op"])


def _k_unary(f: Fields, o: list[int], pc: int) -> int:
    """The one-source forms whose whole 12-bit immediate field is the operation."""
    return _i(f["funct12"], o[1], f["funct3"], o[0], f["op"])


def _k_csr(f: Fields, o: list[int], pc: int) -> int:
    return _i(o[1], o[2], f["funct3"], o[0], f["op"])


def _k_csri(f: Fields, o: list[int], pc: int) -> int:
    return _i(o[1], _imm(o[2], 5, signed=False, name="CSR immediate"), f["funct3"], o[0], f["op"])


def _k_amo(f: Fields, o: list[int], pc: int) -> int:
    return _r((f["funct5"] << 2) | f["ordering"], o[1], o[2], f["funct3"], o[0], f["op"])


def _k_fence(f: Fields, o: list[int], pc: int) -> int:
    return _i((_imm(o[0], 4, signed=False, name="predecessor set") << 4) |
              _imm(o[1], 4, signed=False, name="successor set"), 0, 0b000, 0, MISC_MEM)


def _k_none(f: Fields, o: list[int], pc: int) -> int:
    return f["word"]


def _k_cbo(f: Fields, o: list[int], pc: int) -> int:
    return _i(f["imm"], o[0], 0b010, 0, MISC_MEM)


def _k_cheri2(f: Fields, o: list[int], pc: int) -> int:
    """The two-operand capability forms: `funct7` is all ones and the operation
    is the five bits the second source register field carries."""
    return _r(0b1111111, f["funct5"], o[1], 0b000, o[0], CHERI)


def _k_cheri3(f: Fields, o: list[int], pc: int) -> int:
    return _r(f["funct7"], o[2], o[1], 0b000, o[0], CHERI)


def _k_cheri_imm(f: Fields, o: list[int], pc: int) -> int:
    # `signed` is the one field read as a flag rather than as bits, so it is the one
    # that narrows on the way out of the table (`Fields` is `dict[str, int]`).
    return _i(_imm(o[2], 12, signed=bool(f["signed"]), name="immediate"),
              o[1], f["funct3"], o[0], CHERI)


def _k_cspecialrw(f: Fields, o: list[int], pc: int) -> int:
    return _r(0b0000001, o[1], o[2], 0b000, o[0], CHERI)


def _k_paren(f: Fields, o: list[int], pc: int) -> int:
    """`rd, (cs1)`: the tag-group load, whose group is the block rather than an
    operand, so it names no offset."""
    return _r(0b1111111, f["funct5"], o[1], 0b000, o[0], CHERI)


def _k_indexed(f: Fields, o: list[int], pc: int) -> int:
    """`rd, cs1[rs2 << scale]`: the capability indexed access.

    An R-type whose `funct7` is five reserved zeroes over the two-bit scale. The
    store form reads its source out of the `rd` slot, which is what a
    three-register store has to do in this layout and is how RVV encodes `vs3`.
    """
    return _r(_imm(o[3], 2, signed=False, name="index scale"),
              o[2], o[1], f["funct3"], o[0], CUSTOM_0)


def _k_cclear(f: Fields, o: list[int], pc: int) -> int:
    """`cclear h, mask`: S-type field layout, read as a constant.

    The mask is the twelve immediate bits and the low four of the `rs2` field,
    the half selector is that field's top bit, and `rs1` is reserved zero. No
    destination register is named because the mask names the destinations.
    """
    h = _imm(o[0], 1, signed=False, name="register half")
    mask = _imm(o[1], 16, signed=False, name="register mask")
    return _s(mask & 0xFFF, (h << 4) | ((mask >> 12) & 0xF), 0, 0b000, CUSTOM_0)


# --- the vector kinds (M0.8b) ----------------------------------------------
# Every vector memory form has one layout, and it is worth writing once: the top
# twelve bits are `nf`, a reserved zero, `mop`, `vm`, and a five-bit field that
# is a constant for the unit-stride and whole-register forms and a register for
# the strided and indexed ones. That is an I-type shape for the store forms too,
# the source vector register sitting in the `rd` slot, which is what a
# three-register store has to do in this layout and is the same thing `csd`'s
# `indexed` kind does (extensions/V/vext_mem_insts.sail).

def _v_mem(f: Fields, vd: int, rs1: int, sub: int, vm: int) -> int:
    imm = (f["nf"] << 9) | (f["mop"] << 6) | (vm << 5) | sub
    return _i(imm, rs1, f["funct3"], vd, f["op"])


def _k_vmem(f: Fields, o: list[int], pc: int) -> int:
    """`vd, (rs1)[, v0.t]`: the unit-stride forms, whose five-bit field is the
    `lumop`/`sumop` constant naming which one it is."""
    return _v_mem(f, o[0], o[1], f["sub"], o[2])


def _k_vmems(f: Fields, o: list[int], pc: int) -> int:
    """`vd, (rs1), rs2[, v0.t]`: the stride is a runtime register, which is what
    puts this form off the data-independent-timing list (R-15-085a)."""
    return _v_mem(f, o[0], o[1], o[2], o[3])


def _k_vmemx(f: Fields, o: list[int], pc: int) -> int:
    """`vd, (rs1), vs2[, v0.t]`: the index is a vector register, so each element
    carries its own address and its own check (R-08-003)."""
    return _v_mem(f, o[0], o[1], o[2], o[3])


def _k_vmemw(f: Fields, o: list[int], pc: int) -> int:
    """`vd, (rs1)`: the whole-register and mask forms, whose `vm` is the literal
    one in the encoding rather than an operand, so they have no masked-off
    element (R-15-115b)."""
    return _v_mem(f, o[0], o[1], f["sub"], 1)


def _k_vsetvli(f: Fields, o: list[int], pc: int) -> int:
    """`rd, rs1, vtypei`: the eleven-bit `vtype` image, whose top three bits are
    reserved and whose remaining eight are `vma`, `vta`, `vsew` and `vlmul`. It
    is taken as a number rather than as `e64,m1,ta,ma`, because a program that
    writes the field out is a program whose `vtype` can be read against the
    model's own bitfield (extensions/V/vext_regs.sail)."""
    return _i(_imm(o[2], 11, signed=False, name="vtype immediate"), o[1], 0b111, o[0], OP_V)


def _k_vmovi(f: Fields, o: list[int], pc: int) -> int:
    """`vd, simm`: the five-bit signed immediate rides the `rs1` field."""
    return _r(f["funct7"], 0, _imm(o[1], 5, signed=True, name="immediate"),
              f["funct3"], o[0], OP_V)


def _k_vmovx(f: Fields, o: list[int], pc: int) -> int:
    """`vd, rs1`: an integer register into a vector one."""
    return _r(f["funct7"], 0, o[1], f["funct3"], o[0], OP_V)


def _k_vmovs(f: Fields, o: list[int], pc: int) -> int:
    """`rd, vs2`: element zero of a vector register into an integer one, which
    is how a corpus program reads a vector result back to compare it."""
    return _r(f["funct7"], o[1], 0, f["funct3"], o[0], OP_V)


KINDS: dict[str, Kind] = {
    "r": Kind(("reg", "reg", "reg"), _k_r),
    "i": Kind(("reg", "reg", "imm"), _k_i),
    "shift": Kind(("reg", "reg", "imm"), _k_shift),
    "load": Kind(("reg", "mem"), _k_load),
    "store": Kind(("reg", "mem"), _k_store),
    "branch": Kind(("reg", "reg", "sym"), _k_branch),
    "u": Kind(("reg", "imm"), _k_u),
    "unary": Kind(("reg", "reg"), _k_unary),
    "jal": Kind(("reg", "sym"), _k_jal),
    "jalr": Kind(("reg", "reg", "imm"), _k_jalr),
    "csr": Kind(("reg", "csr", "reg"), _k_csr),
    "csri": Kind(("reg", "csr", "imm"), _k_csri),
    "amo": Kind(("reg", "reg", "mem0"), _k_amo),
    "fence": Kind(("imm", "imm"), _k_fence),
    "none": Kind((), _k_none),
    "cbo": Kind(("mem0",), _k_cbo),
    "cheri2": Kind(("reg", "reg"), _k_cheri2),
    "cheri3": Kind(("reg", "reg", "reg"), _k_cheri3),
    "cheri_imm": Kind(("reg", "reg", "imm"), _k_cheri_imm),
    "cspecialrw": Kind(("reg", "scr", "reg"), _k_cspecialrw),
    "paren": Kind(("reg", "mem0"), _k_paren),
    # `index` is `cs1[rs2 << scale]`, which the parser flattens into the base,
    # the index register, and the scale.
    "indexed": Kind(("reg", "index"), _k_indexed),
    "cclear": Kind(("imm", "imm"), _k_cclear),
    # The vector kinds. `vm` is the one operand a program leaves out rather than
    # spells: `v0.t` where the operation is masked and nothing at all where it is
    # not, which is how the model's own `maybe_vmask` mapping reads it back.
    "vsetvli": Kind(("reg", "reg", "imm"), _k_vsetvli),
    "vmovi": Kind(("vreg", "imm"), _k_vmovi),
    "vmovx": Kind(("vreg", "reg"), _k_vmovx),
    "vmovs": Kind(("reg", "vreg"), _k_vmovs),
    "vmem": Kind(("vreg", "mem0", "vm"), _k_vmem),
    "vmems": Kind(("vreg", "mem0", "reg", "vm"), _k_vmems),
    "vmemx": Kind(("vreg", "mem0", "vreg", "vm"), _k_vmemx),
    "vmemw": Kind(("vreg", "mem0"), _k_vmemw),
}


def _rows() -> dict[str, tuple[str, Fields]]:
    table: dict[str, tuple[str, Fields]] = {}

    def add(name: str, kind: str, **fields: int) -> None:
        # Raised rather than asserted. These are assertions in the sense that they
        # can only fail on a defect in the table below, but `python -O` deletes an
        # `assert` and this table is built at import: a duplicated row would then
        # silently take the later definition, and a bad kind would fail later and
        # elsewhere. The check has to outlive the flag.
        if name in table:
            raise AssertionError(f"{name} is already in the table")
        if kind not in KINDS:
            raise AssertionError(f"{name} names no kind {kind}")
        table[name] = (kind, fields)

    # --- RV64I -------------------------------------------------------------
    add("lui", "u", op=0b0110111)
    # The base's `auipc`, `jal` and `jalr` are these three: purecap has no
    # integer control transfer to distinguish them from (R-15-001).
    add("auipcc", "u", op=0b0010111)
    add("cjal", "jal", op=0b1101111)
    add("cjalr", "jalr", funct3=0b000, op=0b1100111)

    for name, funct3 in (("beq", 0b000), ("bne", 0b001), ("blt", 0b100),
                         ("bge", 0b101), ("bltu", 0b110), ("bgeu", 0b111)):
        add(name, "branch", funct3=funct3, op=BRANCH)

    # funct3 is the unsigned flag over the two width bits (core/types.sail).
    for name, funct3 in (("lb", 0b000), ("lh", 0b001), ("lw", 0b010), ("ld", 0b011),
                         ("lbu", 0b100), ("lhu", 0b101), ("lwu", 0b110)):
        add(name, "load", funct3=funct3, op=LOAD)
    for name, funct3 in (("sb", 0b000), ("sh", 0b001), ("sw", 0b010), ("sd", 0b011)):
        add(name, "store", funct3=funct3, op=STORE)

    for name, funct3 in (("addi", 0b000), ("slti", 0b010), ("sltiu", 0b011),
                         ("xori", 0b100), ("ori", 0b110), ("andi", 0b111)):
        add(name, "i", funct3=funct3, op=OP_IMM)
    add("slli", "shift", funct7=0b000000 << 6, funct3=0b001, op=OP_IMM, shamt_bits=6)
    add("srli", "shift", funct7=0b000000 << 6, funct3=0b101, op=OP_IMM, shamt_bits=6)
    add("srai", "shift", funct7=0b010000 << 6, funct3=0b101, op=OP_IMM, shamt_bits=6)

    for name, funct7, funct3 in (
        ("add", 0b0000000, 0b000), ("sub", 0b0100000, 0b000),
        ("sll", 0b0000000, 0b001), ("slt", 0b0000000, 0b010),
        ("sltu", 0b0000000, 0b011), ("xor", 0b0000000, 0b100),
        ("srl", 0b0000000, 0b101), ("sra", 0b0100000, 0b101),
        ("or", 0b0000000, 0b110), ("and", 0b0000000, 0b111),
    ):
        add(name, "r", funct7=funct7, funct3=funct3, op=OP)

    add("addiw", "i", funct3=0b000, op=OP_IMM_32)
    add("slliw", "shift", funct7=0b0000000 << 5, funct3=0b001, op=OP_IMM_32, shamt_bits=5)
    add("srliw", "shift", funct7=0b0000000 << 5, funct3=0b101, op=OP_IMM_32, shamt_bits=5)
    add("sraiw", "shift", funct7=0b0100000 << 5, funct3=0b101, op=OP_IMM_32, shamt_bits=5)
    for name, funct7, funct3 in (
        ("addw", 0b0000000, 0b000), ("subw", 0b0100000, 0b000),
        ("sllw", 0b0000000, 0b001), ("srlw", 0b0000000, 0b101),
        ("sraw", 0b0100000, 0b101),
    ):
        add(name, "r", funct7=funct7, funct3=funct3, op=OP_32)

    add("fence", "fence")
    add("fence.tso", "none", word=_i(0b1000_0011_0011, 0, 0b000, 0, MISC_MEM))
    # The temporal-isolation fence, at MISC-MEM funct3 100, which is vacant:
    # `fence` is 000, `cbo.zero` and `lc` share 010, and `fence.i` went with
    # `Zifencei`. Every other field is zero and reserved (R-15-062, R-15-014).
    add("fence.t", "none", word=_i(0, 0, 0b100, 0, MISC_MEM))
    add("ecall", "none", word=_i(0, 0, 0b000, 0, SYSTEM))
    add("ebreak", "none", word=_i(1, 0, 0b000, 0, SYSTEM))
    add("mret", "none", word=_r(0b0011000, 0b00010, 0, 0b000, 0, SYSTEM))
    add("wfi", "none", word=_r(0b0001000, 0b00101, 0, 0b000, 0, SYSTEM))

    # --- M -----------------------------------------------------------------
    for name, funct3 in (("mul", 0b000), ("mulh", 0b001), ("mulhsu", 0b010),
                         ("mulhu", 0b011), ("div", 0b100), ("divu", 0b101),
                         ("rem", 0b110), ("remu", 0b111)):
        add(name, "r", funct7=0b0000001, funct3=funct3, op=OP)
    for name, funct3 in (("mulw", 0b000), ("divw", 0b100), ("divuw", 0b101),
                         ("remw", 0b110), ("remuw", 0b111)):
        add(name, "r", funct7=0b0000001, funct3=funct3, op=OP_32)

    # --- Zicsr -------------------------------------------------------------
    for name, funct3 in (("csrrw", 0b001), ("csrrs", 0b010), ("csrrc", 0b011)):
        add(name, "csr", funct3=funct3, op=SYSTEM)
    for name, funct3 in (("csrrwi", 0b101), ("csrrsi", 0b110), ("csrrci", 0b111)):
        add(name, "csri", funct3=funct3, op=SYSTEM)

    # --- Zaamo + Zabha -----------------------------------------------------
    # The umbrella `A` is off and the parts are on: unconditional atomic RMW at
    # four widths, no reservation and no compare-and-swap (R-15-024).
    amo_ops = {"amoswap": 0b00001, "amoadd": 0b00000, "amoxor": 0b00100,
               "amoand": 0b01100, "amoor": 0b01000, "amomin": 0b10000,
               "amomax": 0b10100, "amominu": 0b11000, "amomaxu": 0b11100}
    widths = {"b": 0b000, "h": 0b001, "w": 0b010, "d": 0b011}
    orderings = {"": 0b00, ".aq": 0b10, ".rl": 0b01, ".aqrl": 0b11}
    for op_name, funct5 in amo_ops.items():
        for width, funct3 in widths.items():
            for suffix, ordering in orderings.items():
                add(f"{op_name}.{width}{suffix}", "amo",
                    funct5=funct5, ordering=ordering, funct3=funct3, op=AMO)

    # --- Zba / Zbb / Zbs ---------------------------------------------------
    add("add.uw", "r", funct7=0b0000100, funct3=0b000, op=OP_32)
    add("slli.uw", "shift", funct7=0b000010 << 6, funct3=0b001, op=OP_IMM_32, shamt_bits=6)
    for shamt, name in ((0b01, "sh1add"), (0b10, "sh2add"), (0b11, "sh3add")):
        add(name, "r", funct7=0b0010000, funct3=shamt << 1, op=OP)
        add(f"{name}.uw", "r", funct7=0b0010000, funct3=shamt << 1, op=OP_32)

    for name, funct7, funct3 in (
        ("andn", 0b0100000, 0b111), ("orn", 0b0100000, 0b110),
        ("xnor", 0b0100000, 0b100), ("max", 0b0000101, 0b110),
        ("maxu", 0b0000101, 0b111), ("min", 0b0000101, 0b100),
        ("minu", 0b0000101, 0b101), ("rol", 0b0110000, 0b001),
        ("ror", 0b0110000, 0b101),
    ):
        add(name, "r", funct7=funct7, funct3=funct3, op=OP)
    add("rolw", "r", funct7=0b0110000, funct3=0b001, op=OP_32)
    add("rorw", "r", funct7=0b0110000, funct3=0b101, op=OP_32)
    add("rori", "shift", funct7=0b011000 << 6, funct3=0b101, op=OP_IMM, shamt_bits=6)
    add("roriw", "shift", funct7=0b0110000 << 5, funct3=0b101, op=OP_IMM_32, shamt_bits=5)

    for name, funct12, op in (
        ("clz", 0b011000000000, OP_IMM), ("ctz", 0b011000000001, OP_IMM),
        ("cpop", 0b011000000010, OP_IMM), ("sext.b", 0b011000000100, OP_IMM),
        ("sext.h", 0b011000000101, OP_IMM), ("clzw", 0b011000000000, OP_IMM_32),
        ("ctzw", 0b011000000001, OP_IMM_32), ("cpopw", 0b011000000010, OP_IMM_32),
    ):
        add(name, "unary", funct12=funct12, funct3=0b001, op=op)
    add("zext.h", "unary", funct12=0b000010000000, funct3=0b100, op=OP_32)
    add("rev8", "unary", funct12=0b011010111000, funct3=0b101, op=OP_IMM)
    add("orc.b", "unary", funct12=0b001010000111, funct3=0b101, op=OP_IMM)
    add("brev8", "unary", funct12=0b011010000111, funct3=0b101, op=OP_IMM)

    for name, funct7, funct3 in (
        ("bclr", 0b0100100, 0b001), ("bext", 0b0100100, 0b101),
        ("binv", 0b0110100, 0b001), ("bset", 0b0010100, 0b001),
    ):
        add(name, "r", funct7=funct7, funct3=funct3, op=OP)
    for name, funct6, funct3 in (
        ("bclri", 0b010010, 0b001), ("bexti", 0b010010, 0b101),
        ("binvi", 0b011010, 0b001), ("bseti", 0b001010, 0b001),
    ):
        add(name, "shift", funct7=funct6 << 6, funct3=funct3, op=OP_IMM, shamt_bits=6)

    # --- Zbkb / Zbkc / Zbkx ------------------------------------------------
    add("pack", "r", funct7=0b0000100, funct3=0b100, op=OP)
    add("packh", "r", funct7=0b0000100, funct3=0b111, op=OP)
    add("packw", "r", funct7=0b0000100, funct3=0b100, op=OP_32)
    add("clmul", "r", funct7=0b0000101, funct3=0b001, op=OP)
    add("clmulh", "r", funct7=0b0000101, funct3=0b011, op=OP)
    add("xperm4", "r", funct7=0b0010100, funct3=0b010, op=OP)
    add("xperm8", "r", funct7=0b0010100, funct3=0b100, op=OP)

    # --- Zicond ------------------------------------------------------------
    add("czero.eqz", "r", funct7=0b0000111, funct3=0b101, op=OP)
    add("czero.nez", "r", funct7=0b0000111, funct3=0b111, op=OP)

    # --- Zicboz, and the block scrub beside it -----------------------------
    # Both are MISC-MEM funct3 010 at a zero destination, which is what `lc`'s
    # non-zero one is separated from. The scrub takes 5 rather than one of the
    # three points `Zicbom` vacated: reusing a named standard encoding would
    # make a stock disassembler print the wrong instruction where an unallocated
    # one makes it print none (R-15-060, R-15-177a).
    add("cbo.zero", "cbo", imm=0b000000000100)
    add("cbo.scrub", "cbo", imm=0b000000000101)

    # --- CHERI: inspection and the two-operand derivations -----------------
    for name, funct5 in (
        ("cgetperm", 0b00000), ("cgettype", 0b00001), ("cgetbase", 0b00010),
        ("cgetlen", 0b00011), ("cgettag", 0b00100), ("cgetsealed", 0b00101),
        ("cgetoffset", 0b00110), ("cgetaddr", 0b01111), ("cgettop", 0b11000),
        ("cmove", 0b01010), ("csealentry", 0b10001),
    ):
        add(name, "cheri2", funct5=funct5)
    # The two block operations over the tag plane. `creclaim` takes the first
    # sub-opcode of this group that ISAv9 never allocated, so it sits beside
    # `cloadtags` and contends for no custom opcode space (R-15-007s).
    add("cloadtags", "paren", funct5=0b10010)
    add("creclaim", "paren", funct5=0b10011)

    # --- CHERI: the three-operand derivations ------------------------------
    for name, funct7 in (
        ("csetbounds", 0b0001000), ("cseal", 0b0001011), ("cunseal", 0b0001100),
        ("candperm", 0b0001101), ("csetoffset", 0b0001111), ("csetaddr", 0b0010000),
        ("cincoffset", 0b0010001), ("ctoptr", 0b0010010), ("cfromptr", 0b0010011),
        ("csub", 0b0010100), ("cseqx", 0b0100001),
    ):
        add(name, "cheri3", funct7=funct7)
    add("cincoffsetimm", "cheri_imm", funct3=0b001, signed=True)
    add("csetboundsimm", "cheri_imm", funct3=0b010, signed=False)
    add("cspecialrw", "cspecialrw")

    # --- CHERI: the capability load and store ------------------------------
    # `lc` shares MISC-MEM funct3 010 with the cache-block operations and is
    # separated from them by a non-zero destination (extensions/CHERI).
    add("lc", "load", funct3=0b010, op=MISC_MEM, nonzero_rd=True)
    add("sc", "store", funct3=0b100, op=STORE)

    # --- CHERI: the conditional capability move ----------------------------
    # The dialect's own encoding rather than custom opcode space, at the first
    # free `funct7` pair above ISAv9's highest three-operand allocation
    # (R-15-054a).
    add("cmovz", "cheri3", funct7=0b0100010)
    add("cmovn", "cheri3", funct7=0b0100011)

    # --- The profile's custom opcode space ---------------------------------
    # The indexed access carries `ld`'s and `sd`'s own width code in its
    # `funct3`, so the width reads off the same three bits the base ISA puts it
    # in; the masked clear takes 000 beside them (R-15-007e, R-15-069a).
    add("cld", "indexed", funct3=0b011)
    add("csd", "indexed", funct3=0b111)
    add("cclear", "cclear")
    # The vector/matrix all-state clear takes 001 beside the masked clear's 000.
    # It names no operand and no destination, the class's unit-state inventory
    # naming them all, so every other field is zero and reserved (R-15-069d).
    add("vmclear", "none", word=_r(0, 0, 0, 0b001, 0, CUSTOM_0))

    # --- V: the vector memory surface, and the moves that feed it ----------
    # M0.8b's rows. `nf` here is the encoded three-bit field and not the segment
    # count: `encdec_nfields` maps 000 to one field, and the whole-register and
    # mask forms carry the same 000 as a literal. Every row below is at nf=1,
    # the segment forms being a field this table does not yet spell because no
    # member of the corpus writes one.
    for width, code in VLEWIDTH.items():
        add(f"vle{width}.v", "vmem", nf=0, mop=0b00, sub=0b00000, funct3=code, op=LOAD_FP)
        add(f"vse{width}.v", "vmem", nf=0, mop=0b00, sub=0b00000, funct3=code, op=STORE_FP)
        add(f"vle{width}ff.v", "vmem", nf=0, mop=0b00, sub=0b10000, funct3=code, op=LOAD_FP)
        add(f"vlse{width}.v", "vmems", nf=0, mop=0b10, funct3=code, op=LOAD_FP)
        add(f"vsse{width}.v", "vmems", nf=0, mop=0b10, funct3=code, op=STORE_FP)
        # The index EEW is what the mnemonic names, and the data EEW is `vtype`'s
        # `vsew`: the two are separately encoded, which is the whole reason an
        # indexed element's address is a runtime value (R-15-085a).
        add(f"vluxei{width}.v", "vmemx", nf=0, mop=0b01, funct3=code, op=LOAD_FP)
        add(f"vloxei{width}.v", "vmemx", nf=0, mop=0b11, funct3=code, op=LOAD_FP)
        add(f"vsuxei{width}.v", "vmemx", nf=0, mop=0b01, funct3=code, op=STORE_FP)
        add(f"vsoxei{width}.v", "vmemx", nf=0, mop=0b11, funct3=code, op=STORE_FP)
        add(f"vl1re{width}.v", "vmemw", nf=0, mop=0b00, sub=0b01000, funct3=code, op=LOAD_FP)
    # The whole-register store and the mask pair carry no width code at all: the
    # transfer is a register's worth of bytes and the mask access is one byte per
    # element, so both are `funct3` 000 whatever `vtype` says.
    add("vs1r.v", "vmemw", nf=0, mop=0b00, sub=0b01000, funct3=0b000, op=STORE_FP)
    add("vlm.v", "vmemw", nf=0, mop=0b00, sub=0b01011, funct3=0b000, op=LOAD_FP)
    add("vsm.v", "vmemw", nf=0, mop=0b00, sub=0b01011, funct3=0b000, op=STORE_FP)

    # `vsetvli` is here because no vector memory operation means anything without
    # it: `vl` and `vtype` are what say how many elements an access has and how
    # wide each one is, and they are read-only CSRs this is the only writer of.
    add("vsetvli", "vsetvli")

    # The four moves a program needs to put a value into the vector file and read
    # one back out, which is what makes a vector memory check a check rather than
    # a store nobody reads. `vmv.v.i` is also how `v0` is given a mask, the mask
    # being an ordinary vector register (extensions/V/vext_arith_insts.sail).
    add("vmv.v.i", "vmovi", funct7=0b0101111, funct3=0b011)
    add("vmv.v.x", "vmovx", funct7=0b0101111, funct3=0b100)
    add("vmv.s.x", "vmovx", funct7=0b0100001, funct3=0b110)
    add("vmv.x.s", "vmovs", funct7=0b0100001, funct3=0b010)

    return table


TABLE = _rows()

# Every mnemonic the assembler will encode, for the corpus documentation and for
# the checker's count of this table.
MNEMONICS = tuple(sorted(TABLE))


def signature(mnemonic: str) -> tuple[str, ...]:
    kind, _ = TABLE[mnemonic]
    return KINDS[kind].operands


def encode(mnemonic: str, operands: list[int], pc: int) -> int:
    """The word `mnemonic` with these already-resolved operands encodes to.

    `operands` is flat and in source order, with a `mem` operand contributing
    its displacement and then its base register, which is the order the memory
    kinds above read them in.
    """
    kind, fields = TABLE[mnemonic]
    if fields.get("nonzero_rd") and operands[0] == 0:
        # The decode clause carries this as `when cd != zreg`: at a zero
        # destination the encoding is the cache-block block's, so a capability
        # load written that way would assemble to `cbo.zero` (R-15-060).
        raise AsmError(f"{mnemonic} into the null register is the cache-block "
                       f"encoding, not a capability load")
    word = KINDS[kind].emit(fields, operands, pc)
    # Raised rather than asserted: this is the last thing standing between a
    # mis-transcribed row and an image the emulator runs anyway. A field that
    # overflows its slot corrupts the neighbouring one silently, and the corpus
    # would report a divergence in the model rather than a defect in this table.
    # `python -O` must not be able to switch that off.
    if not 0 <= word < (1 << 32):
        raise AssertionError(f"{mnemonic} encoded outside 32 bits: {word:#x}")
    return word
