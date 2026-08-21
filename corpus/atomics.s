# SPDX-License-Identifier: Apache-2.0
# `A` narrowed to `Zaamo` + `Zabha`: unconditional atomic read-modify-write at
# four widths, with no reservation and no compare-and-swap (R-15-024). `Zabha`
# is width cases on the same operation rather than a new class, so the byte and
# halfword forms are checked for exactly that: the same answer at a narrower
# width, and the neighbours left standing.
#
# An atomic is a load and a store at once, so its authority owes both
# permissions, which is the one place `cap_data_checks` asks for two
# (core/addr_checks.sail).

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        li      t0, scratch
        csetaddr c10, c8, t0

        # The old value is the answer and the new value is in memory, which is
        # the whole of an atomic's contract.
        li      gp, 1
        li      t0, 5
        sd      t0, 0(c10)
        li      t1, 9
        amoswap.d t2, t1, (c10)
        li      t3, 5
        bne     t2, t3, fail
        ld      t2, 0(c10)
        li      t3, 9
        bne     t2, t3, fail

        li      gp, 2
        li      t1, 3
        amoadd.d t2, t1, (c10)
        li      t3, 9
        bne     t2, t3, fail
        ld      t2, 0(c10)
        li      t3, 12
        bne     t2, t3, fail

        li      gp, 3
        li      t0, 0xf0
        sd      t0, 0(c10)
        li      t1, 0x3c
        amoand.d t2, t1, (c10)
        ld      t2, 0(c10)
        li      t3, 0x30
        bne     t2, t3, fail
        li      t1, 0x0f
        amoor.d t2, t1, (c10)
        ld      t2, 0(c10)
        li      t3, 0x3f
        bne     t2, t3, fail
        li      t1, 0xff
        amoxor.d t2, t1, (c10)
        ld      t2, 0(c10)
        li      t3, 0xc0
        bne     t2, t3, fail

        # The four comparing forms, which differ from each other in signedness
        # and in nothing else.
        li      gp, 4
        li      t0, -1
        sd      t0, 0(c10)
        li      t1, 1
        amomin.d t2, t1, (c10)
        ld      t2, 0(c10)
        li      t3, -1
        bne     t2, t3, fail
        amomax.d t2, t1, (c10)
        ld      t2, 0(c10)
        li      t3, 1
        bne     t2, t3, fail

        li      gp, 5
        li      t0, -1
        sd      t0, 0(c10)
        li      t1, 1
        amominu.d t2, t1, (c10)
        ld      t2, 0(c10)
        li      t3, 1
        bne     t2, t3, fail
        li      t0, -1
        sd      t0, 0(c10)
        amomaxu.d t2, t1, (c10)
        ld      t2, 0(c10)
        li      t3, -1
        bne     t2, t3, fail

        # A word atomic answers sign-extended and touches four bytes, so the
        # doubleword around it says how far it reached.
        li      gp, 6
        cincoffsetimm c11, c10, 8
        li      t0, -1
        sd      t0, 8(c10)
        li      t1, 1
        amoadd.w t2, t1, (c11)
        li      t3, -1
        bne     t2, t3, fail
        ld      t2, 8(c10)
        li      t3, 0xffffffff00000000
        bne     t2, t3, fail

        # `Zabha`'s two widths, checked the same way: the answer is the old
        # value at that width, and the bytes beside it do not move.
        li      gp, 7
        cincoffsetimm c12, c10, 16
        li      t0, -1
        sd      t0, 16(c10)
        li      t1, 1
        amoadd.b t2, t1, (c12)
        li      t3, -1
        bne     t2, t3, fail
        ld      t2, 16(c10)
        li      t3, 0xffffffffffffff00
        bne     t2, t3, fail

        li      gp, 8
        cincoffsetimm c13, c10, 24
        li      t0, -1
        sd      t0, 24(c10)
        li      t1, 0x1234
        amoswap.h t2, t1, (c13)
        li      t3, -1
        bne     t2, t3, fail
        ld      t2, 24(c10)
        li      t3, 0xffffffffffff1234
        bne     t2, t3, fail

        # An atomic's store half clears the tag of the granule it writes,
        # because tag clearing is a property of the write path rather than of
        # any one instruction (R-15-007r).
        li      gp, 9
        sc      c8, 32(c10)
        cloadtags t0, (c10)
        li      t1, 0x10
        bne     t0, t1, fail
        cincoffsetimm c14, c10, 32
        li      t1, 0
        amoswap.d t2, t1, (c14)
        cloadtags t0, (c10)
        bnez    t0, fail

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
        .align  6
scratch:
        .space  64
