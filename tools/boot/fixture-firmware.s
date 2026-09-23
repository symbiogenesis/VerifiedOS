# SPDX-License-Identifier: Apache-2.0
# Boot harness fixture, rank 1: a stand-in for the M-mode firmware, and not the
# firmware. It exists so the harness's compose, boot and digest acts run end to
# end before any real roster member has an executable product; the real member
# is M3.5's, and its handoff is the purecap ABI contract's section 7.
#
# It prints `F` through the HTIF terminal, records a stage marker in its own
# data, and enters the next member at its entry. The store-side root travels in
# `c8`, which is this fixture's convention and not the real handoff's.

        .text
        .globl _start
_start:
        # c1 holds the store-side root at reset and is also the link register,
        # so it is moved out first, as every corpus member does.
        cmove   c8, c1
        li      t1, tohost
        csetaddr c31, c8, t1
        li      t0, 0x0101000000000046
        sd      t0, 0(c31)

        li      t1, stage
        csetaddr c9, c8, t1
        li      t0, 1
        sd      t0, 0(c9)

        # The next member's entry is an import the recipe resolves, so this unit
        # names no address it does not own.
        la      c5, kernel_entry
        cjr     c5

        .data
        .align  3
stage:
        .dword  0
