# SPDX-License-Identifier: Apache-2.0
# Fixed-package observer fixture: print F and report HTIF success. This is not
# a real roster member and carries no compiler or admission qualification.
        .text
        .globl _start
_start:
        cmove c8, c1
        la c5, tohost
        cgetaddr t1, c5
        csetaddr c31, c8, t1
        li t0, 0x0101000000000046
        sd t0, 0(c31)
        li t0, 1
        sd t0, 0(c31)
halt:
        j halt
        .data
        .align 3
tohost:
        .dword 0
