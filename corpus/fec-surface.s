# SPDX-License-Identifier: Apache-2.0
# The FEC decoders' instruction surface, from the only side a program on this
# machine reaches it from (R-15-119, R-15-119a, R-15-119b).
#
# **The golden emulator is the C class and its composed hart carries no
# decoder**, so what a corpus program can exercise here is the refusal and the
# encoding, and that is the whole of what this member claims. The gate is the
# composed roster entry's FEC attachment (R-12-038, R-15-114), the reference
# composition attaches the units to the pinned radio V pair, and the hart this
# emulator runs is hart zero, so both mnemonics reach no decode clause and trap
# exactly as any unallocated encoding does (R-15-014). The other side of the
# surface, the pass itself and the two authorities it is checked against, is
# asserted as properties over the model instead
# (model/model/unit_tests/test_fec.sail), which is the same division
# [keccak-perm.s](keccak-perm.s) makes and arrives at here from the far end: a
# program reaches the encoding and a property reaches the semantics.
#
# **Nothing here is a hand-written word**, and that is worth stating because the
# obvious way to check an encoding is to write one. The trap value carries the
# faulting instruction, so the program reads back the word the assembler built
# for each mnemonic and asks its questions of that: which opcode and `funct3`
# the pair sits at, that the code family is the sub-opcode and that nothing else
# moves with it, that each operand lands in the field the operand form names,
# and that the descriptor register is an ordinary register whose contents reach
# no field. A `.word` would have made every one of those the member's own claim
# rather than the encoder's answer.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        # Every trap this member takes is an illegal instruction, so the cause
        # is set once. The handler leaves the faulting word in s2 rather than
        # comparing it against a constant the program carries, which is what
        # keeps the encoding the encoder's answer.
        li      t5, 2

        # The composed hart, which is what the gate reads through. `mhartid`
        # indexes the composed roster and the roster is what says which cores
        # carry the decoders (R-15-052b), so this is the fact the refusals below
        # stand on rather than a coincidence about an opcode.
        li      gp, 1
        csrr    t1, mhartid
        bnez    t1, fail

        # `ldpcdec cd, cs1, rs2`, refused on a hart with no decoder attached.
        li      gp, 2
        li      t0, 16
        ldpcdec c9, c8, t0
        mv      s3, s2

        # Custom-0 at `funct3` 100, which is where the pair sits and is the
        # whole of what it spends: `cclear` is 000, `vmclear` 001,
        # `vkeccak.vi` 010 and the indexed access's width-coded pair 011 and
        # 111, so this is the first free point and both mnemonics take it.
        li      gp, 3
        li      t2, 0x707F
        and     t1, s3, t2
        li      t2, 0x400B
        bne     t1, t2, fail

        # Each operand in the field the form names: the descriptor in `rs2`, the
        # consuming authority in `rs1`, and the producing authority in the `rd`
        # slot read as a source, which is what a three-register form has to do in
        # this layout and is exactly what `csd` does.
        li      gp, 4
        srli    t1, s3, 20
        andi    t1, t1, 0x1F
        li      t2, 5
        bne     t1, t2, fail
        srli    t1, s3, 15
        andi    t1, t1, 0x1F
        li      t2, 8
        bne     t1, t2, fail
        srli    t1, s3, 7
        andi    t1, t1, 0x1F
        li      t2, 9
        bne     t1, t2, fail

        # `polardec` over the same operands, refused for the same reason.
        li      gp, 5
        polardec c9, c8, t0
        mv      s4, s2

        li      gp, 6
        li      t2, 0x707F
        and     t1, s4, t2
        li      t2, 0x400B
        bne     t1, t2, fail

        # The code family is the sub-opcode and **nothing else moves with it**,
        # which is what puts both decoders in one `funct3` rather than one each.
        # One step in `funct7` is 1 << 25.
        li      gp, 7
        sub     t1, s4, s3
        li      t2, 0x2000000
        bne     t1, t2, fail

        # The descriptor is an ordinary register and its contents reach no field
        # of the encoding, which is the invariance R-15-119a requires seen from a
        # program: a different value in the same register is the same word, and a
        # different register is the same word with the `rs2` field moved. No
        # channel-code parameter has anywhere to go.
        li      gp, 8
        li      t0, 0x1234
        ldpcdec c9, c8, t0
        bne     s2, s3, fail

        li      gp, 9
        li      t1, 32
        ldpcdec c9, c8, t1
        sub     t1, s2, s3
        li      t2, 0x100000
        bne     t1, t2, fail

        li      gp, 0
        j       pass

# The handler runs under MTCC's authority, the execute side of the root pair,
# which carries the access-system-registers permission its CSR reads need. It
# leaves the faulting word in s2 for the program and resumes past the faulting
# instruction: MEPCC is not sealed on the way in, so its integer view can be
# advanced and `mret` returns through it.
handler:
        csrr    t4, mcause
        bne     t4, t5, fail
        csrr    s2, mtval
        csrr    t4, mepc
        addi    t4, t4, 4
        csrw    mepc, t4
        mret

fail:
        slli    t0, gp, 1
        ori     t0, t0, 1
        j       exit
pass:
        li      t0, 1
exit:
        li      t1, tohost
        csetaddr c31, c8, t1
        sd      t0, 0(c31)
halt:
        j       halt

        .data
        .align  3
tohost:
        .dword  0
