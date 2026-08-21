# SPDX-License-Identifier: Apache-2.0
# The RV64I integer surface: arithmetic, logic, shifts, the W forms, and every
# branch condition. Nothing here is capability-specific; it is the base the
# curation did not disturb, and it is first in the corpus because a divergence
# in it localizes every later program's divergence away from the capability
# layer.
#
# `gp` names the check in flight, so a failure exits with `(gp << 1) | 1` and
# says which one. Every program in the corpus ends in the same six lines.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        li      gp, 1
        li      t0, 5
        li      t1, 7
        add     t2, t0, t1
        li      t3, 12
        bne     t2, t3, fail

        li      gp, 2
        sub     t2, t1, t0
        li      t3, 2
        bne     t2, t3, fail

        li      gp, 3
        and     t2, t0, t1
        li      t3, 5
        bne     t2, t3, fail
        or      t2, t0, t1
        li      t3, 7
        bne     t2, t3, fail
        xor     t2, t0, t1
        li      t3, 2
        bne     t2, t3, fail

        li      gp, 4
        addi    t2, t0, -6
        li      t3, -1
        bne     t2, t3, fail
        andi    t2, t1, 3
        li      t3, 3
        bne     t2, t3, fail
        ori     t2, t0, 8
        li      t3, 13
        bne     t2, t3, fail
        xori    t2, t0, -1
        li      t3, -6
        bne     t2, t3, fail

        # Shifts are XLEN-wide, and the arithmetic one is what says so: a
        # logical right shift of -1 by 60 leaves four bits, the arithmetic one
        # leaves -1.
        li      gp, 5
        li      t0, -1
        srli    t2, t0, 60
        li      t3, 15
        bne     t2, t3, fail
        srai    t2, t0, 60
        li      t3, -1
        bne     t2, t3, fail
        li      t0, 1
        slli    t2, t0, 63
        li      t3, -1
        slli    t3, t3, 63
        bne     t2, t3, fail

        li      gp, 6
        li      t0, 1
        li      t1, 63
        sll     t2, t0, t1
        li      t3, 1
        slli    t3, t3, 63
        bne     t2, t3, fail
        srl     t2, t3, t1
        li      t3, 1
        bne     t2, t3, fail

        # Set-less-than in both signednesses, which is the one place a
        # comparison's signedness is visible in the result rather than in a
        # branch.
        li      gp, 7
        li      t0, -1
        li      t1, 1
        slt     t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail
        sltu    t2, t0, t1
        bnez    t2, fail
        slti    t2, t0, 0
        li      t3, 1
        bne     t2, t3, fail
        sltiu   t2, t0, 1
        bnez    t2, fail

        li      gp, 8
        lui     t0, 0x12345
        li      t3, 0x12345000
        bne     t0, t3, fail

        # The W forms truncate to 32 bits and sign-extend the result, which is
        # what separates `addiw` from `addi` on a value at the boundary.
        li      gp, 9
        li      t0, 0x7fffffff
        addiw   t2, t0, 1
        li      t3, 1
        slli    t3, t3, 31
        sub     t3, zero, t3
        bne     t2, t3, fail
        addi    t2, t0, 1
        li      t3, 0x80000000
        bne     t2, t3, fail

        li      gp, 10
        li      t0, 1
        slliw   t2, t0, 31
        li      t3, 1
        slli    t3, t3, 31
        sub     t3, zero, t3
        bne     t2, t3, fail
        sraiw   t2, t2, 31
        li      t3, -1
        bne     t2, t3, fail
        srliw   t2, t3, 28
        li      t3, 15
        bne     t2, t3, fail

        li      gp, 11
        li      t0, 3
        li      t1, 4
        addw    t2, t0, t1
        li      t3, 7
        bne     t2, t3, fail
        subw    t2, t0, t1
        li      t3, -1
        bne     t2, t3, fail
        sllw    t2, t0, t1
        li      t3, 48
        bne     t2, t3, fail

        # Every branch condition, taken and not taken. A condition that fell
        # through where it should branch would leave `gp` at 12 and land in the
        # failure below it.
        li      gp, 12
        li      t0, -1
        li      t1, 1
        beq     t0, t0, .beq_ok
        j       fail
.beq_ok:
        bne     t0, t1, .bne_ok
        j       fail
.bne_ok:
        blt     t0, t1, .blt_ok
        j       fail
.blt_ok:
        bge     t1, t0, .bge_ok
        j       fail
.bge_ok:
        bltu    t1, t0, .bltu_ok
        j       fail
.bltu_ok:
        bgeu    t0, t1, .bgeu_ok
        j       fail
.bgeu_ok:
        beq     t0, t1, fail
        blt     t1, t0, fail
        bltu    t0, t1, fail

        # x0 reads zero however it is written, which on a merged register file
        # is the null capability's address rather than a hardwired integer
        # (R-15-007i, core/reg_type.sail).
        li      gp, 13
        li      zero, 7
        bnez    zero, fail
        add     zero, t0, t1
        bnez    zero, fail

        li      gp, 0
        j       pass

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
