# SPDX-License-Identifier: Apache-2.0
# The inspection surface, read against the state the machine actually resets
# with: a **split** root pair, the execute side in PCC and the store side in
# `c1`, because no admitted permission set holds both store and execute
# (R-15-007l, R-15-007p, postlude/step_ext.sail).
#
# The permission answers are the *expanded* bitmap rather than the five-bit
# field, which is what lets `candperm` mask a non-orthogonal encoding
# (R-15-007b). Bit order, least significant first: global, R, W, LC, SC, SL,
# LG, LM, X, SE, US, ASR.
#
# Capabilities live in c10 upward here and in every corpus program, so that no
# capability register is also a `t` register the checks around it are using.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        # The store side: {global, R, W, LC, SC, SL, LG, LM} is the stack shape,
        # which carries `store-local` because `candperm` can only remove and a
        # stack capability has to be derivable from what reset hands out.
        li      gp, 1
        cgetperm t0, c1
        li      t1, 0xff
        bne     t0, t1, fail

        li      gp, 2
        cgettag t0, c1
        li      t1, 1
        bne     t0, t1, fail
        cgetsealed t0, c1
        bnez    t0, fail

        # An unsealed capability's object type reads as the negative
        # architectural value it stands for rather than as its four bits.
        li      gp, 3
        cgettype t0, c1
        li      t1, -1
        bne     t0, t1, fail

        # The root spans the whole 36-bit physical space, which is what makes it
        # a root: base zero, top 2^36, and an address that has not moved.
        li      gp, 4
        cgetbase t0, c1
        bnez    t0, fail
        cgetaddr t0, c1
        bnez    t0, fail
        cgetoffset t0, c1
        bnez    t0, fail
        cgetlen t0, c1
        li      t1, 0x1000000000
        bne     t0, t1, fail
        cgettop t0, c1
        li      t1, 0x1000000000
        bne     t0, t1, fail

        # The execute side, read out of PCC. It holds neither store permission
        # nor `store-local`, so W+X is not merely undelegated here but
        # unrepresentable in the format (R-15-007l).
        li      gp, 5
        cspecialrw c10, pcc, cnull
        cgetperm t0, c10
        li      t1, 0x9cb
        bne     t0, t1, fail
        andi    t1, t0, 4
        bnez    t1, fail
        andi    t1, t0, 0x100
        beqz    t1, fail

        # PCC's address is the address of the instruction that read it, which is
        # what makes it the program counter rather than a copy of one.
        li      gp, 6
.here:
        cspecialrw c11, pcc, cnull
        cgetaddr t0, c11
        la      c12, .here
        cgetaddr t1, c12
        bne     t0, t1, fail

        # The trap capabilities: MTCC and MEPCC start from the execute side and
        # MTDC is granted rather than assumed, so it starts untagged.
        li      gp, 7
        cspecialrw c13, mtcc, cnull
        cgettag t0, c13
        li      t1, 1
        bne     t0, t1, fail
        cgetperm t0, c13
        li      t1, 0x9cb
        bne     t0, t1, fail
        cspecialrw c14, mtdc, cnull
        cgettag t0, c14
        bnez    t0, fail

        # The null capability is what the zero register reads as, and it is the
        # all-zeroes granule: no tag, no authority, and the unsealed type.
        li      gp, 8
        cgettag t0, cnull
        bnez    t0, fail
        cgetperm t0, cnull
        bnez    t0, fail
        cgettype t0, cnull
        li      t1, -1
        bne     t0, t1, fail

        # `cmove` copies the register whole, tag included, which `cseqx` is what
        # says: it compares capabilities and not addresses.
        li      gp, 9
        cmove   c15, c1
        cseqx   t0, c15, c1
        li      t1, 1
        bne     t0, t1, fail
        cseqx   t0, c15, cnull
        bnez    t0, fail

        # `csub` and `ctoptr` are the two integer answers about a pair, and they
        # differ in what they subtract: an address from an address, and an
        # address from the other capability's base.
        li      gp, 10
        li      t0, 0x40
        csetaddr c16, c1, t0
        csub    t1, c16, c1
        li      t2, 0x40
        bne     t1, t2, fail
        ctoptr  t1, c16, c1
        bne     t1, t2, fail
        ctoptr  t1, cnull, c1
        bnez    t1, fail

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
