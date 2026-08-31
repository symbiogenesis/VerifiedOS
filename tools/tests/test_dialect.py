# SPDX-License-Identifier: Apache-2.0
"""The dialect table's encodings, pinned word by word.

Every row of `dialect.TABLE` is **generated** from the curated model's `mapping clause
encdec` and its `mapping clause assembly`, so the model (model/model/) is the authority
behind every golden word here, not the RISC-V manuals: the rows deliberately diverge
where the model does. Nothing else on the host pins a single encoding; a flipped funct7
bit would otherwise pass every gate and surface only as a digest mismatch inside a WSL
emulator run. On a golden mismatch, read the row's `encdec` clause before touching
either side, and never repair a red run by rerecording alone.

The generation is why these words matter more than they did, not less. A transcription
goes wrong one row at a time; a generator goes wrong by a rule, and a rule wrong about
the positional binding between the two clauses moves forty-nine rows at once with the
count unchanged.
"""

import json
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Final

from tests.harness import Case, ensure
from vos import asm, corpus, dialect, dialectgen
from vos.dialect import AsmError

# One recorded word per operand kind, and one per row family whose encoding the
# module docstring singles out (the base-encoding control transfers, `lc`/`sc`,
# the custom-0 rows, the vector memory surface). Recorded from `dialect.encode`
# on this tree; rerecord a value only after reading the model's own clause, with
#   python -c "import sys; sys.path.insert(0, 'tools'); from vos import dialect;
#              print(hex(dialect.encode('<mnemonic>', [<operands>], <pc>)))"
_GOLDEN: Final[tuple[tuple[str, tuple[int, ...], int, int], ...]] = (
    ("add", (1, 2, 3), 0x0, 0x003100B3),
    ("sub", (1, 2, 3), 0x0, 0x403100B3),
    ("mul", (1, 2, 3), 0x0, 0x023100B3),
    ("sh1add", (1, 2, 3), 0x0, 0x203120B3),
    ("czero.eqz", (1, 2, 3), 0x0, 0x0E3150B3),
    ("addi", (5, 6, -1), 0x0, 0xFFF30293),
    ("andi", (5, 6, 255), 0x0, 0x0FF37293),
    ("slli", (1, 1, 63), 0x0, 0x03F09093),
    ("srai", (1, 1, 63), 0x0, 0x43F0D093),
    ("sraiw", (1, 1, 31), 0x0, 0x41F0D09B),
    ("bexti", (1, 2, 17), 0x0, 0x49115093),
    ("lw", (7, -4, 9), 0x0, 0xFFC4A383),
    ("lc", (7, 16, 9), 0x0, 0x0104A38F),
    ("sd", (7, -4, 9), 0x0, 0xFE74BE23),
    ("sc", (7, 16, 9), 0x0, 0x0074C823),
    ("beq", (1, 2, 0x100), 0x80, 0x08208063),
    ("bltu", (1, 2, 0x40), 0x80, 0xFC20E0E3),
    # The word is the one that was always recorded and the operand is written the way
    # the model reads it: `UTYPE`'s execute clause is `sign_extend(imm @ 0x000)`, so the
    # upper immediate's admitted range is signed and `0xFFFFF` is spelled `-1`. The bits
    # are unchanged, `lui` masking its operand into twenty either way.
    ("lui", (3, -1), 0x0, 0xFFFFF1B7),
    ("auipcc", (3, 1), 0x0, 0x00001197),
    ("clz", (1, 2), 0x0, 0x60011093),
    ("rev8", (1, 2), 0x0, 0x6B815093),
    ("cjal", (1, 0x800), 0x100, 0x700000EF),
    ("cjalr", (1, 5, 16), 0x0, 0x010280E7),
    ("csrrs", (5, 0x300, 0), 0x0, 0x300022F3),
    ("csrrwi", (5, 0x300, 31), 0x0, 0x300FD2F3),
    ("amoadd.w.aq", (10, 11, 12), 0x0, 0x04B6252F),
    ("amomaxu.d", (10, 11, 12), 0x0, 0xE0B6352F),
    ("fence", (0b1111, 0b0011), 0x0, 0x0F30000F),
    ("fence.t", (), 0x0, 0x0000400F),
    ("ecall", (), 0x0, 0x00000073),
    ("mret", (), 0x0, 0x30200073),
    ("cbo.zero", (5,), 0x0, 0x0042A00F),
    ("cbo.scrub", (5,), 0x0, 0x0052A00F),
    ("cgettag", (1, 2), 0x0, 0xFE4100DB),
    ("cmove", (1, 2), 0x0, 0xFEA100DB),
    ("csetbounds", (1, 2, 3), 0x0, 0x103100DB),
    ("cincoffset", (1, 2, 3), 0x0, 0x223100DB),
    ("cmovz", (1, 2, 3), 0x0, 0x443100DB),
    ("cincoffsetimm", (1, 2, -16), 0x0, 0xFF0110DB),
    ("csetboundsimm", (1, 2, 16), 0x0, 0x010120DB),
    ("cspecialrw", (1, 0b11100, 2), 0x0, 0x03C100DB),
    ("cloadtags", (1, 2), 0x0, 0xFF2100DB),
    ("creclaim", (1, 2), 0x0, 0xFF3100DB),
    ("cld", (1, 2, 3, 2), 0x0, 0x0431308B),
    ("csd", (1, 2, 3, 0), 0x0, 0x0031708B),
    ("cclear", (1, 0xFFFF), 0x0, 0xFFF00F8B),
    ("vmclear", (), 0x0, 0x0000100B),
    ("vkeccak.vi", (1, 2, 24), 0x0, 0x0181208B),
    # The FEC pair shares `funct3` 100 and differs in `funct7` alone, which is
    # what one row per code family rather than one `funct3` per family buys
    # (R-15-119b). The two words below differ by exactly 1 << 25.
    ("ldpcdec", (1, 2, 3), 0x0, 0x0031408B),
    ("polardec", (1, 2, 3), 0x0, 0x0231408B),
    ("vsetvli", (1, 2, 0b00011011000), 0x0, 0x0D8170D7),
    ("vmv.v.i", (1, -16), 0x0, 0x5E0830D7),
    ("vmv.v.x", (1, 2), 0x0, 0x5E0140D7),
    ("vmv.s.x", (1, 2), 0x0, 0x420160D7),
    ("vmv.x.s", (1, 2), 0x0, 0x422020D7),
    ("vle32.v", (1, 2, 0), 0x0, 0x00016087),
    ("vse8.v", (1, 2, 1), 0x0, 0x020100A7),
    ("vlse64.v", (1, 2, 3, 1), 0x0, 0x0A317087),
    ("vluxei16.v", (1, 2, 3, 0), 0x0, 0x04315087),
    ("vsoxei32.v", (1, 2, 3, 1), 0x0, 0x0E3160A7),
    ("vl1re8.v", (1, 2), 0x0, 0x02810087),
    ("vs1r.v", (1, 2), 0x0, 0x028100A7),
    ("vlm.v", (1, 2), 0x0, 0x02B10087),
    ("vsm.v", (1, 2), 0x0, 0x02B100A7),
    # Four rows the transcription never carried, recorded when generation reached them
    # (M1.4'). `vadc.vvm` is the one operand shape no other row here has: the mask
    # register printed as a literal, so a program writes `v0` and the encoding carries
    # nothing for it.
    ("vadd.vv", (1, 2, 3, 1), 0x0, 0x022180D7),
    ("vand.vi", (1, 2, -16, 0), 0x0, 0x242830D7),
    ("vmul.vv", (1, 2, 3, 1), 0x0, 0x9621A0D7),
    ("vadc.vvm", (1, 2, 3), 0x0, 0x402180D7),
)

# One operand text per spec `asm._operand` dispatches on. A spec named by a KINDS
# row and absent here fails the structural case below with instructions.
_OPERAND_TEXT: Final[dict[str, str]] = {
    "reg": "x1", "vreg": "v1", "vm": "", "imm": "0", "sym": "0", "csr": "0x300",
    "scr": "pcc", "index": "c1[x2 << 1]", "mem": "0(x1)", "mem0": "(x1)", "v0": "v0",
}


def _raises(kind: type[BaseException], fn: Callable[[], object],
            *fragments: str) -> None:
    """The check that `fn` raises `kind` carrying every fragment in its message."""
    try:
        fn()
    except kind as err:
        for fragment in fragments:
            ensure(fragment in str(err),
                   f"{kind.__name__} said {str(err)!r}, which misses {fragment!r}")
        return
    raise AssertionError(f"{kind.__name__} was not raised")


def _golden_words() -> None:
    for mnemonic, operands, pc, want in _GOLDEN:
        got = dialect.encode(mnemonic, list(operands), pc)
        ensure(got == want,
               f"{mnemonic} {list(operands)} at pc {pc:#x} encoded {got:#010x}, "
               f"recorded {want:#010x}: read the model's encdec clause before "
               f"rerecording")


def _golden_covers_every_kind() -> None:
    used = {kind for row in dialect.TABLE.values() for kind in row.signature}
    hit = {kind for mnemonic, _, _, _ in _GOLDEN
           for kind in dialect.signature(mnemonic)}
    ensure(hit == used,
           f"the golden table exercises no row using operand kind(s) "
           f"{sorted(used - hit)}: add one per kind the table uses")


def _row_count() -> None:
    """The table's size, against the artifact that determines it.

    Held rather than recorded, which is the whole of what generation changed here: the
    row count is a function of the model and the admission policy, so a number written
    down beside it would be a second statement of one fact and would have to be
    rerecorded every time the model moved. What this still pins is the two ways the
    count can be wrong without anybody deciding it: a generated row silently absent from
    what this module loads, and the one authored row going missing beside it.
    """
    root = corpus.find_root(Path(__file__).resolve())
    raw = json.loads((root / dialectgen.TABLE).read_text(encoding="utf-8"))
    admitted = int(raw["header"]["admitted"])
    ensure(len(dialect.TABLE) == admitted + 1,
           f"TABLE carries {len(dialect.TABLE)} rows against the {admitted} the "
           f"generated artifact admits plus the one authored `fence`")
    ensure("fence" in dialect.TABLE, "the one authored row is gone from the table")
    # A floor under the generated half, on the ground the floors group states: the day
    # the join stops matching anything is the day this says so rather than the day it
    # starts agreeing with everything. 353 is what the transcription this replaced
    # carried, so the generated table may not fall below it without a decision.
    ensure(admitted >= 353,
           f"the generated table admits {admitted} rows, fewer than the 353 the "
           f"transcription it replaced carried")


def _operand_specs_dispatch() -> None:
    # Every operand kind a row's signature names must be one `asm._operand` dispatches
    # on; a kind the generator emits and the parser does not know otherwise fails only
    # when a program first uses it, as an AssertionError deep in the assembler.
    assembler = asm.Assembler("")
    item = asm.Item("insn", 1, ".text", text="probe")
    for mnemonic, row in dialect.TABLE.items():
        for spec in row.signature:
            ensure(spec in _OPERAND_TEXT,
                   f"{mnemonic} names operand spec {spec!r} with no representative "
                   f"text in this module: add one to _OPERAND_TEXT")
            # An AsmError is a fine answer (the probe text was refused as a
            # program); only the no-such-spec AssertionError may not escape.
            with suppress(AsmError):
                assembler._operand(spec, _OPERAND_TEXT[spec], item, 0)


def _imm_range() -> None:
    _raises(AsmError, lambda: dialect.encode("addi", [1, 1, 2048], 0),
            "outside", "[-2048, 2047]")
    _raises(AsmError, lambda: dialect.encode("addi", [1, 1, -2049], 0), "outside")
    ensure(dialect.encode("addi", [1, 1, 2047], 0) == 0x7FF08093,
           "the top of the signed 12-bit range must still encode")


def _imm_alignment() -> None:
    _raises(AsmError, lambda: dialect.encode("beq", [1, 2, 0x81], 0),
            "not a multiple of 2")
    _raises(AsmError, lambda: dialect.encode("cjal", [1, 0x81], 0),
            "not a multiple of 2")


def _csr_range() -> None:
    # The wave the range check landed in turned an out-of-range CSR address from
    # an AssertionError blaming the table into the operand diagnostic every other
    # program defect gets.
    _raises(AsmError, lambda: dialect.encode("csrrs", [5, 0x1000, 0], 0),
            "CSR address", "outside")
    _raises(AsmError, lambda: dialect.encode("csrrwi", [5, -1, 0], 0), "CSR address")
    word = dialect.encode("csrrs", [5, dialect.CSRS["mstatus"], 0], 0)
    ensure(word == 0x300022F3,
           f"csrrs t0, mstatus, x0 encoded {word:#010x}, recorded 0x300022f3")
    ensure(word.to_bytes(4, "little").hex() == "f3220030",
           "the image bytes of csrrs t0, mstatus, x0 must stay f3220030")


def _csr_range_names_the_line() -> None:
    source = ".text\n_start:\n    csrrs t0, 0x1000, x0\n"
    _raises(AsmError, lambda: asm.Assembler(source, "t.s").assemble(),
            "t.s:3", "CSR address")


def _vkeccak_rounds() -> None:
    # The refusal was a hand rule quoting the clause and is now the clause: the guard
    # `keccak_valid_rounds(rnd)` is read out of the model and carried to the site, so
    # the diagnostic names the predicate rather than restating what it admits.
    for rounds in (0, 1, 11, 13, 16, 23, 25, 31):
        _raises(AsmError,
                lambda r=rounds: dialect.encode("vkeccak.vi", [1, 2, r], 0),
                "rnd of 12, 24", "keccak_valid_rounds")
    ensure(dialect.encode("vkeccak.vi", [1, 2, 12], 0) == 0x00C1208B,
           "the 12-round form must still encode")


def _lc_null_destination() -> None:
    # At a zero destination the bit pattern is the cache-block block's, so the encoder
    # refuses rather than laying down `cbo.zero`. This too is now the model's own guard
    # rather than a rule beside it, so the diagnostic quotes `cd != zreg`.
    _raises(AsmError, lambda: dialect.encode("lc", [0, 0, 1], 0), "cd != zreg")
    ensure(dialect.encode("lc", [1, 0, 2], 0) == 0x0001208F,
           "a non-null destination must still encode")


def _operand_width_guard() -> None:
    # Every field's width now comes from the model, so a register past its five bits is
    # the operand diagnostic every other program defect gets rather than the 32-bit
    # assertion it used to reach.
    _raises(AsmError, lambda: dialect.encode("add", [1, 1, 4096], 0),
            "register 4096", "outside", "[0, 31]")


def _overflow_guard() -> None:
    """The 32-bit guard, which no operand can reach any more and still must be there.

    Its subject moved with the table: it used to catch an over-wide operand and now
    catches a *row* whose placement runs past the word, which is a defect in the
    generator rather than in a program. Seeded here rather than argued about, because a
    guard nothing exercises is a guard nobody notices the deletion of.
    """
    row = dialect.TABLE["add"]
    broken = dialect.Row(
        ctor=row.ctor, site=row.site, word=1 << 32, mask=row.mask, guard=row.guard,
        signature=row.signature, slots=row.slots, requires=row.requires)
    dialect.TABLE["_probe"] = broken
    try:
        _raises(AssertionError, lambda: dialect.encode("_probe", [1, 1, 1], 0),
                "outside 32 bits")
    finally:
        del dialect.TABLE["_probe"]


def cases() -> list[Case]:
    return [
        Case("golden-words", _golden_words),
        Case("golden-covers-every-kind", _golden_covers_every_kind),
        Case("row-count", _row_count),
        Case("operand-specs-dispatch", _operand_specs_dispatch),
        Case("imm-range", _imm_range),
        Case("imm-alignment", _imm_alignment),
        Case("csr-range", _csr_range),
        Case("csr-range-names-the-line", _csr_range_names_the_line),
        Case("vkeccak-rounds", _vkeccak_rounds),
        Case("lc-null-destination", _lc_null_destination),
        Case("operand-width-guard", _operand_width_guard),
        Case("overflow-guard", _overflow_guard),
    ]
