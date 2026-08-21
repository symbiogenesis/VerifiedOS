# SPDX-License-Identifier: Apache-2.0
# The refresh and discharge sequencer, checked from the only side a program can
# reach it from: the outside (R-15-247h).
#
# The sequencer is a fixed-function register slave with no instruction fetch and
# no firmware, sequenced by the RoT while every application core, DMA engine,
# and capability-bearing fabric initiator is held in reset. A hart executing an
# instruction is by construction not in reset, so **there is nothing here for a
# program to reach, and every check below is a refusal**. The mechanism itself is
# asserted where it lives, as properties over the model
# ([test_platform.sail](../model/model/unit_tests/test_platform.sail),
# [memory_sequencer.sail](../model/model/sys/memory_sequencer.sail)); what a
# whole program adds is the fault a requester actually takes, at the widths and
# through the authorities a requester actually has.
#
# The window is *in* the address map rather than absent from it, and check 7 is
# why that matters: an IO address no device claims falls through to the RAM path
# and reads as zero, which is silence and not a refusal. A slave that means to
# refuse has to be in the map to do it, and the two answers one page apart are
# what makes the refusal visible from here.
#
# Check 8 is the refresh side, and it is deliberately modest. A refresh restores
# a charge no model represents and disturbs nothing observable, so what a program
# can say about it is that waiting changes nothing: a capability and a data word
# on the second class survive an interval of ticks unmoved. What it cannot say is
# anything about the cadence, which is a composition-time table
# ([the devicetree](../model/model/postlude/device_tree.sail) carries it) and not
# a result an instruction returns.
#
# The handler is installed by writing MTCC, and each faulting check leaves the
# cause it expects in `t5` and the trap value in `t6`, exactly as
# [cap-trap.s](cap-trap.s) does. Check 7 leaves an impossible pair there, so a
# trap it does not expect fails rather than passing quietly.

        .equ    SEQ, 0x2300000
        .equ    SEQ_8, 0x2300008
        .equ    SEQ_TOP, 0x2300ff8
        .equ    UNCLAIMED, 0x2310000
        .equ    BULK, 0x100000000

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        # One authority over the slave's window, derived from the root exactly
        # as an authority over any other device window is. That it is a
        # well-formed capability with load and store permission is the point:
        # what refuses the access below is the slave and not the authority.
        li      t0, SEQ
        csetaddr c10, c8, t0

        # A doubleword read of the window's first address.
        li      gp, 1
        li      t5, 5
        li      t6, SEQ
        ld      t1, 0(c10)

        # And a doubleword write of it. The slave answers in neither direction,
        # so there is no status register to poll and no command register to
        # write: a requester cannot start a discharge, cannot observe one, and
        # cannot learn where in the refresh sweep the machine is.
        li      gp, 2
        li      t5, 7
        li      t6, SEQ
        sd      zero, 0(c10)

        # A narrower access is not a way in either. The refusal is the window's
        # rather than one register's, so it does not turn on the width a
        # requester happens to name.
        li      gp, 3
        li      t5, 5
        li      t6, SEQ_8
        lw      t1, 8(c10)

        # Nor is a capability-width access, in either direction. There is
        # nothing in the window a tag could be loaded out of and nothing an
        # authority could be stored into.
        li      gp, 4
        li      t5, 5
        li      t6, SEQ
        lc      c13, 0(c10)

        li      gp, 5
        li      t5, 7
        li      t6, SEQ
        sc      c8, 0(c10)

        # The last doubleword of the window answers as the first does: the whole
        # region is refused, not one address inside it.
        li      gp, 6
        li      t0, SEQ_TOP
        csetaddr c11, c8, t0
        li      t5, 5
        li      t6, SEQ_TOP
        ld      t1, 0(c11)

        # The contrast that makes the refusal the slave's. One page above the
        # window is IO memory no device claims, and it reads as zero rather than
        # faulting. `t5` and `t6` are set to a pair no trap can carry, so a fault
        # here is a failure and not a silent pass.
        li      gp, 7
        li      t5, 0
        li      t6, 0
        li      t0, UNCLAIMED
        csetaddr c12, c8, t0
        ld      t1, 0(c12)
        bnez    t1, fail

        # And the refresh side: a capability and a data word on the second class
        # are unmoved by an interval of ticks. Refresh is not something a program
        # issues, observes, or waits on; the one thing it must not do is disturb
        # what it maintains.
        li      gp, 8
        li      t0, BULK
        csetaddr c14, c8, t0
        li      t0, value
        csetaddr c15, c8, t0
        csetboundsimm c15, c15, 64
        cbo.zero (c14)
        sc      c15, 0(c14)
        li      s6, 0x0123456789abcdef
        sd      s6, 32(c14)
        li      t1, 64
spin:
        addi    t1, t1, -1
        bnez    t1, spin
        lc      c16, 0(c14)
        cgettag t2, c16
        li      t3, 1
        bne     t2, t3, fail
        cseqx   t2, c16, c15
        bne     t2, t3, fail
        ld      t2, 32(c14)
        bne     t2, s6, fail

        li      gp, 0
        j       pass

# The handler runs under MTCC's authority, the execute side of the root pair,
# which carries the access-system-registers permission its CSR reads need. It
# resumes past the faulting instruction: MEPCC is not sealed on the way in, so
# its integer view can be advanced and `mret` returns through it.
handler:
        csrr    t4, mcause
        bne     t4, t5, fail
        csrr    t4, mtval
        bne     t4, t6, fail
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
        .align  6
value:
        .space  64
