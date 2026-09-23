# SPDX-License-Identifier: Apache-2.0
# Boot harness fixture, rank 2: a stand-in for the kernel, and not the kernel.
# The real member is M4.4's GC-free C, entered by the handoff the purecap ABI
# contract's section 7 selects.
#
# It installs a trap handler, takes one environment call so the event log
# carries a trap, prints `K` through the HTIF terminal, and enters the next
# member at its entry.

        .text
        .globl _start
_start:
        la      c9, handler
        cspecialrw cnull, mtcc, c9
        ecall

        li      t1, tohost
        csetaddr c31, c8, t1
        li      t0, 0x010100000000004B
        sd      t0, 0(c31)

        la      c5, service_entry
        cjr     c5

# The handler runs under MTCC's authority and resumes past the call: MEPCC is
# not sealed on the way in, so its integer view is advanced and `mret` returns
# through it, as the corpus's cap-trap member does.
handler:
        csrr    t4, mepc
        addi    t4, t4, 4
        csrw    mepc, t4
        mret
