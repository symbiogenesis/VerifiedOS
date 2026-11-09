# SPDX-License-Identifier: Apache-2.0
# Fixture-only controller. The peer entry is one 4096-byte page after this
# package; no production capability wiring, compiler or admission is exercised.
        .text
        .globl _start
_start:
        cmove c8, c1
        la c5, tohost
        cgetaddr t1, c5
        li t2, 3840
        add t1, t1, t2
        csetaddr c5, c5, t1
        cjalr c1, c5, 0
        li t1, 7
        bne t0, t1, failed
        la c5, tohost
        cgetaddr t1, c5
        csetaddr c31, c8, t1
        li t0, 0x0101000000000046
        sd t0, 0(c31)
        li t0, 1
        sd t0, 0(c31)
halt:
        j halt
failed:
        la c5, tohost
        cgetaddr t1, c5
        csetaddr c31, c8, t1
        li t0, 3
        sd t0, 0(c31)
        j halt
        .data
        .align 3
tohost:
        .dword 0
