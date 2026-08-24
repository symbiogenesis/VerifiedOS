# SPDX-License-Identifier: Apache-2.0
# The Root of Trust's four peripherals, checked from the only side a program on
# this emulator can reach them from: the outside (R-15-194).
#
# The OTP fuse bank, the entropy root, the monotonic counter file and the
# windowed watchdog are the platform's one management processor's, and there is
# exactly one management processor. The golden emulator is the C class (M0.10),
# so **there is nothing here for a program to reach, and every check below is a
# refusal**. The mechanism behind the doors is asserted where it lives, as
# properties over the model ([test_rot.sail](../model/model/unit_tests/test_rot.sail),
# [rot.sail](../model/model/sys/rot.sail)) and reached by the composition that
# composes hart 15 ([verifiedos-rot.json](../model/config/verifiedos-rot.json));
# what a whole program adds is the fault a requester actually takes, at the
# widths and through the authorities a requester actually has.
#
# The four windows are *in* the address map rather than absent from it, and
# check 10 is why that matters: an IO address no device claims falls through to
# the RAM path and reads as zero, which is silence and not a refusal. A slave
# that means to refuse has to be in the map to do it, and the two answers one
# page apart are what makes the refusal visible from here. This is the same
# contrast [platform-memseq.s](platform-memseq.s) draws for the refresh
# sequencer, and it is drawn again rather than inherited because the ground is
# different: the sequencer refuses **every** requester, and these four refuse
# every requester **that is not the RoT**, which from this composition is the
# same set and from verifiedos-rot.json is not.
#
# The handler is installed by writing MTCC, and each faulting check leaves the
# cause it expects in `t5` and the trap value in `t6`, exactly as
# [cap-trap.s](cap-trap.s) does. Check 10 leaves an impossible pair there, so a
# trap it does not expect fails rather than passing quietly.

        .equ    OTP, 0x2400000
        .equ    TRNG, 0x2500000
        .equ    CTR, 0x2600000
        .equ    WDT, 0x2700000
        .equ    WDT_TOP, 0x2700ff8
        .equ    UNCLAIMED, 0x2800000

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        # One authority over each window, derived from the root exactly as an
        # authority over any other device window is. That each is a well-formed
        # capability with load and store permission is the point: what refuses
        # the access below is the slave and not the authority.
        li      t0, OTP
        csetaddr c10, c8, t0
        li      t0, TRNG
        csetaddr c11, c8, t0
        li      t0, CTR
        csetaddr c12, c8, t0
        li      t0, WDT
        csetaddr c13, c8, t0

        # The lifecycle state is at the OTP window's first doubleword and it
        # does not read here. R-09-032 makes exactly one state readable at any
        # time, and to whom is R-15-194's: the state a relying party appraises
        # the part from reaches it through the attested devicetree and the
        # measured chain, never through a load on an application core.
        li      gp, 1
        li      t5, 5
        li      t6, OTP
        ld      t1, 0(c10)

        # And the lifecycle burn door does not answer either. This is the check
        # worth having a program for: a store here is the one access in the
        # whole address map that would advance a one-way fuse, so a machine that
        # let it through would let an application core spend a transition the
        # relation carries exactly once (R-09-033).
        li      gp, 2
        li      t5, 7
        li      t6, OTP
        sd      zero, 0(c10)

        # The entropy root's draw door. There is no reduced-rate answer and no
        # last-known-good one anywhere in this device (R-15-241b), and from here
        # there is no answer at all: the conditioner's output reaches the DRBG in
        # the crypto core and nothing on this die reaches it by a load
        # (R-15-241c).
        li      gp, 3
        li      t5, 5
        li      t6, TRNG
        ld      t1, 0(c11)

        # The counter file. A read of a monotonic counter is not a way in, and
        # neither is the advance door: a counter an application core could
        # advance is a counter an application core could spend, which is what
        # R-10-013's budget over a wearing part is stated against.
        li      gp, 4
        li      t5, 5
        li      t6, CTR
        ld      t1, 0(c12)

        li      gp, 5
        li      t5, 7
        li      t6, CTR
        sd      zero, 0(c12)

        # The watchdog, in both directions. The pet door is the one a wedged
        # core would want and the one a wedged core must not have: pets are
        # challenge-responses from a single capability holder (R-15-240), and
        # this composition is not it.
        li      gp, 6
        li      t5, 5
        li      t6, WDT
        ld      t1, 0(c13)

        li      gp, 7
        li      t5, 7
        li      t6, WDT
        sd      zero, 0(c13)

        # A capability-width access is not a way in either. There is nothing in
        # any of these windows a tag could be loaded out of and nothing an
        # authority could be stored into.
        li      gp, 8
        li      t5, 5
        li      t6, OTP
        lc      c14, 0(c10)

        # Nor is a narrower one. The refusal is the window's rather than one
        # register's, so it does not turn on the width a requester happens to
        # name.
        li      gp, 9
        li      t5, 5
        li      t6, CTR
        lw      t1, 0(c12)

        # The last doubleword of a window answers as the first does: the whole
        # region is refused, not one address inside it.
        li      gp, 10
        li      t0, WDT_TOP
        csetaddr c15, c8, t0
        li      t5, 5
        li      t6, WDT_TOP
        ld      t1, 0(c15)

        # The contrast that makes the refusal the slave's. One page above the
        # last window is IO memory no device claims, and it reads as zero rather
        # than faulting. `t5` and `t6` are set to a pair no trap can carry, so a
        # fault here is a failure and not a silent pass.
        li      gp, 11
        li      t5, 0
        li      t6, 0
        li      t0, UNCLAIMED
        csetaddr c16, c8, t0
        ld      t1, 0(c16)
        bnez    t1, fail

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
