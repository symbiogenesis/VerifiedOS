# SPDX-License-Identifier: Apache-2.0
# The M extension, including the three cases a divider has to define rather
# than compute: division by zero, the signed overflow at the most negative
# dividend, and the remainder that goes with each.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        li      gp, 1
        li      t0, 6
        li      t1, 7
        mul     t2, t0, t1
        li      t3, 42
        bne     t2, t3, fail

        # The high half is where the three multiply-high forms differ, so each
        # is asked a question whose answer only it gets right.
        li      gp, 2
        li      t0, 1
        slli    t0, t0, 62
        li      t1, 4
        mulh    t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail

        li      gp, 3
        li      t0, -1
        li      t1, -1
        mulhu   t2, t0, t1
        li      t3, -2
        bne     t2, t3, fail
        mulh    t2, t0, t1
        bnez    t2, fail

        li      gp, 4
        li      t0, -1
        li      t1, 2
        mulhsu  t2, t0, t1
        li      t3, -1
        bne     t2, t3, fail

        # Signed division truncates toward zero, so the remainder takes the
        # dividend's sign.
        li      gp, 5
        li      t0, -7
        li      t1, 2
        div     t2, t0, t1
        li      t3, -3
        bne     t2, t3, fail
        rem     t2, t0, t1
        li      t3, -1
        bne     t2, t3, fail

        # Unsigned division reads the same bits as a very large dividend, so
        # -7 over two is (2^64 - 7) / 2 rather than -3.
        li      gp, 6
        divu    t2, t0, t1
        li      t3, 0x7ffffffffffffffc
        bne     t2, t3, fail
        remu    t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail

        # Division by zero is defined rather than trapping: the quotient is all
        # ones and the remainder is the dividend.
        li      gp, 7
        li      t0, 17
        div     t2, t0, zero
        li      t3, -1
        bne     t2, t3, fail
        rem     t2, t0, zero
        li      t3, 17
        bne     t2, t3, fail
        divu    t2, t0, zero
        li      t3, -1
        bne     t2, t3, fail
        remu    t2, t0, zero
        li      t3, 17
        bne     t2, t3, fail

        # The signed overflow: the most negative dividend over minus one is
        # itself, and its remainder is zero.
        li      gp, 8
        li      t0, 1
        slli    t0, t0, 63
        li      t1, -1
        div     t2, t0, t1
        bne     t2, t0, fail
        rem     t2, t0, t1
        bnez    t2, fail

        # The W forms compute at 32 bits and sign-extend, which is visible in
        # both the overflow and the division cases.
        li      gp, 9
        li      t0, 0x10000
        li      t1, 0x10000
        mulw    t2, t0, t1
        bnez    t2, fail
        mul     t2, t0, t1
        li      t3, 0x100000000
        bne     t2, t3, fail

        li      gp, 10
        li      t0, -7
        li      t1, 2
        divw    t2, t0, t1
        li      t3, -3
        bne     t2, t3, fail
        remw    t2, t0, t1
        li      t3, -1
        bne     t2, t3, fail
        li      t0, 0xffffffff
        li      t1, 2
        divuw   t2, t0, t1
        li      t3, 0x7fffffff
        bne     t2, t3, fail
        remuw   t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail

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
