# SPDX-License-Identifier: Apache-2.0
"""The corpus assembler: parse, layout fixpoint, pseudos, and its error edges.

The assembler is a pure function of its source text, and the differential
corpus's evidence stands on that: the same program must lay out to the same
bytes on every run, the layout iteration must settle or say it cannot, and a
defect in the program must surface as an `AsmError` naming file and line, never
as the tool's own traceback.
"""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Final

from tests.harness import Case, ensure
from vos import asm, dialect
from vos.dialect import AsmError

_MASK64 = (1 << 64) - 1

# A program touching both sections, forward references through `li` and `la`,
# expressions over labels, and the data directives at every width.
_FIXTURE: Final[str] = """\
.text
_start:
    la ct0, message
    li t1, 0x12345678
    li t2, value
    lw a0, 0(t0)
    li gp, 1
    beqz t1, fail
    j done
fail:
    ebreak
done:
    ecall
.data
message:
    .asciz "hi", "yo"
    .align 3
value:
    .dword 0xdeadbeefcafebabe
    .word value - message
    .half 0xBEEF
    .byte 1, 2, 3
"""


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


def _assemble_twice_identical() -> None:
    first = asm.Assembler(_FIXTURE, "fixture.s").assemble()
    second = asm.Assembler(_FIXTURE, "fixture.s").assemble()
    for a, b in zip(first[0], second[0], strict=True):
        ensure(bytes(a.data) == bytes(b.data),
               f"section {a.name} differs between two assemblies of one source")
    ensure(first[1] == second[1], "the symbol tables differ between two assemblies")
    ensure(first[2] == second[2], "the entry points differ between two assemblies")
    ensure(first[2] == asm.TEXT_BASE, "_start must be the entry, at TEXT_BASE")
    ensure(bytes(first[0][1].data).startswith(b"hi\0yo\0"),
           "the data section must open with the fixture's strings")

    # And through the ELF writer: two files from one source are byte-identical.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        source = Path(td) / "fixture.s"
        source.write_text(_FIXTURE, encoding="utf-8", newline="")
        once, twice = Path(td) / "a.elf", Path(td) / "b.elf"
        asm.assemble_file(source, once)
        asm.assemble_file(source, twice)
        ensure(once.read_bytes() == twice.read_bytes(),
               "assemble_file wrote two different images from one source")


def _layout_settles() -> None:
    # `li` of a forward code symbol: the value grows past 2^31 once placed, so
    # the expansion widens across rounds and the fixpoint still lands.
    source = ".text\n_start:\n    li t0, target\ntarget:\n    ecall\n"
    sections, symbols, entry = asm.Assembler(source, "settle.s").assemble()
    ensure(len(sections[0].data) == 16,
           f"the settled text is {len(sections[0].data)} bytes, expected 16 "
           f"(a three-word li and the ecall)")
    ensure(symbols["target"] == (".text", 0x8000000C),
           f"target settled at {symbols['target']}, expected .text 0x8000000C")
    ensure(entry == asm.TEXT_BASE, "entry must default to _start")


def _layout_divergence() -> None:
    # The materialization length flips with the label's own address, so the
    # fixpoint oscillates and the eight-round guard must name it.
    source = (".text\nosc:\n    li t0, 0x100000000 * ((tail >> 2) & 1)\ntail:\n")
    _raises(AsmError, lambda: asm.Assembler(source, "osc.s").assemble(),
            "osc.s", "did not settle in eight rounds")


def _sext(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    return (value ^ (1 << (bits - 1))) - (1 << (bits - 1))


def _run_materialization(program: list[asm.Instr]) -> int:
    """The four mnemonics `_materialize` may emit, with the model's semantics:
    `lui` sign-extends to XLEN, `addiw` adds at 32 bits and re-extends, `x0`
    always reads zero. Returns what lands in x5."""
    regs = [0] * 32
    for mnemonic, operands in program:
        if mnemonic == "lui":
            result = _sext(operands[1] << 12, 32)
        elif mnemonic == "addiw":
            result = _sext(regs[operands[1]] + operands[2], 32)
        elif mnemonic == "addi":
            result = regs[operands[1]] + operands[2]
        elif mnemonic == "slli":
            result = regs[operands[1]] << operands[2]
        else:
            raise AssertionError(f"_materialize emitted {mnemonic}, not one of its four")
        regs[operands[0]] = result & _MASK64
        regs[0] = 0
    return regs[5]


def _materialize_edges() -> None:
    # The exact expansions at the edges, where the addiw re-extension comment in
    # `_materialize` is load-bearing: +2^31 is NOT the lui form (lui would come
    # out sign-extended), and -2^31 is exactly the lui form.
    #
    # The upper immediate is handed over **signed**, which is the reading `UTYPE`'s own
    # execute clause states (`sign_extend(imm @ 0x000)`) and the one the generated
    # encoder table therefore admits. The bits are unchanged, `lui` masking its operand
    # into twenty either way, and the semantics below re-extend it exactly as the model
    # does; what moved is only which of the two spellings of one bit pattern is written.
    expansions: list[tuple[int, list[asm.Instr]]] = [
        (0, [("addiw", [5, 0, 0])]),
        (-1, [("addiw", [5, 0, -1])]),
        (1 << 31, [("addiw", [5, 0, 1]), ("slli", [5, 5, 31])]),
        (-(1 << 31), [("lui", [5, -0x80000])]),
        ((1 << 31) - 1, [("lui", [5, -0x80000]), ("addiw", [5, 5, -1])]),
    ]
    for value, want in expansions:
        out: list[asm.Instr] = []
        asm._materialize(5, value, out)
        ensure(out == want, f"_materialize({value:#x}) emitted {out}, expected {want}")


def _materialize_round_trip() -> None:
    # Semantic check across the boundary and trailing-zero-run cases, the latter
    # exercising the recursive shift path.
    edges = (0, 1, -1, (1 << 31) - 1, 1 << 31, -(1 << 31), -(1 << 31) - 1,
             0x123450000, 1 << 63, -(1 << 63), (1 << 64) - 1, 0x7FFFF800,
             0xDEADBEEFCAFEBABE)
    for value in edges:
        out: list[asm.Instr] = []
        asm._materialize(5, value, out)
        got = _run_materialization(out)
        ensure(got == value & _MASK64,
               f"_materialize({value:#x}) runs to {got:#x}, not the value")


def _pseudo_la_ret() -> None:
    # `la` is the purecap pair off PCC and `ret` the linkless capability jump;
    # the expectation is built through dialect.encode, so this pins the
    # expansion rather than re-pinning the encodings test_dialect holds.
    source = ".text\n_start:\n    la ct0, target\n    ret\ntarget:\n"
    sections, _, _ = asm.Assembler(source, "la.s").assemble()
    data = bytes(sections[0].data)
    words = [int.from_bytes(data[at:at + 4], "little") for at in range(0, len(data), 4)]
    want = [dialect.encode("auipcc", [5, 0], 0x80000000),
            dialect.encode("cincoffsetimm", [5, 5, 0xC], 0x80000004),
            dialect.encode("cjalr", [0, 1, 0], 0x80000008)]
    ensure(words == want,
           f"la+ret assembled {[hex(w) for w in words]}, "
           f"expected {[hex(w) for w in want]}")


def _bare_directives() -> None:
    # Each argument-taking directive must state its arity as this module's own
    # diagnostic with file:line, never as an IndexError blaming the tool. Any
    # other exception escapes this case as its failure.
    for source, wording in ((".section", "takes a section name"),
                            (".equ", "takes a name and a value"),
                            (".space", "takes a size"),
                            (".align", "takes a boundary")):
        _raises(AsmError, lambda s=source: asm.Assembler(s, "f.s"),
                "f.s:1", wording)


def _asciz_terminators() -> None:
    # One terminator per string, inside the join: what every other assembler
    # means by `.asciz "a", "b"`.
    sections, _, _ = asm.Assembler('.data\ns:\n    .asciz "a", "b"\n', "z.s").assemble()
    ensure(bytes(sections[1].data) == b"a\0b\0",
           f".asciz laid down {bytes(sections[1].data)!r}, expected b'a\\x00b\\x00'")
    sections, _, _ = asm.Assembler('.data\ns:\n    .ascii "ab"\n', "z.s").assemble()
    ensure(bytes(sections[1].data) == b"ab", ".ascii must append no terminator")


def _split_operands() -> None:
    ensure(asm._split_operands('"a,\\"b", c') == ['"a,\\"b"', "c"],
           "a comma inside a quoted string must not split")
    ensure(asm._split_operands("8(sp), x1") == ["8(sp)", "x1"],
           "a memory operand must split from its neighbour")
    ensure(asm._split_operands("a, (b, c), d") == ["a", "(b, c)", "d"],
           "a comma inside parentheses must not split")
    ensure(asm._split_operands("") == [], "no operands is an empty list")


def _strict_no_symbol() -> None:
    # A typo'd CSR name falls back to expression evaluation, reads zero while
    # the layout settles, and must then be refused by name at strict encode.
    source = ".text\n_start:\n    csrr t0, mstatuss\n"
    _raises(AsmError, lambda: asm.Assembler(source, "t.s").assemble(),
            "t.s:3", "no symbol mstatuss")


def cases() -> list[Case]:
    return [
        Case("assemble-twice-identical", _assemble_twice_identical),
        Case("layout-settles", _layout_settles),
        Case("layout-divergence", _layout_divergence),
        Case("materialize-edges", _materialize_edges),
        Case("materialize-round-trip", _materialize_round_trip),
        Case("pseudo-la-ret", _pseudo_la_ret),
        Case("bare-directives", _bare_directives),
        Case("asciz-terminators", _asciz_terminators),
        Case("split-operands", _split_operands),
        Case("strict-no-symbol", _strict_no_symbol),
    ]
