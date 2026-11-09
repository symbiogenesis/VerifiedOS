# SPDX-License-Identifier: Apache-2.0
# Fixture-only worker. Its own initialized value is reached by a PC-relative
# reference and returned to the controller through the fixture's scalar ABI.
        .text
        .globl _start
_start:
        la c5, value
        ld t0, 0(c5)
        ret
        .data
        .align 3
value:
        .dword 7
