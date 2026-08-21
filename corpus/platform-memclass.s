# SPDX-License-Identifier: Apache-2.0
# The boundary between the two static latency classes of main memory
# (R-15-247), exercised across it rather than on either side of it.
#
# Main memory is bespoke 6T SRAM for the scalar working set and every
# cycle-critical array, and oxide-semiconductor 2T0C decks for bulk. Each region
# is placed on one of them at composition by the static memory plan, and each
# class enters the schedule as **one fixed latency constant**: there is no
# cache, no migration, no tiering, no wake-on-access, and no runtime promotion,
# so a second class is a second constant and not a hierarchy.
#
# **Which means there is nothing here for a program to observe, and that is
# exactly what this member checks.** The class boundary is latency-criticality
# and carries no trust gradient (R-15-247s): tags, ECC, and the R-08-005
# revocation load filter are identical across it, so no capability, compartment,
# or confidentiality label is weakened by residing on the second class and no
# TCB boundary tracks the memory boundary. Every check below is therefore a
# claim of the form *this answers the same on both media*, and a divergence
# would be the finding. A timing difference is real and is invisible from
# inside: it is the constant the static memory plan charges placement against
# (R-15-247j), not a result an instruction returns.
#
# The tag plane is the structure that could have made the boundary a trust
# boundary and does not. Validity tags are native to each class's own array, one
# plane per class, read and written in parallel with the data, with no sidecar
# in a foreign medium and no tag table (R-15-247a, R-15-203) — which is also
# what keeps `cloadtags` at one cost model wherever the group it names resides.
#
# Two things the corpus cannot reach and does not pretend to: refresh and
# discharge, which are §12 matter with no instruction to issue them at all
# (R-15-247h), and the constants themselves, which are R-15-247m's to measure on
# a repaired macro and which the configuration marks unqualified until then.
#
# The handler is installed by writing MTCC, and the faulting check leaves the
# cause it expects in `t5` and the trap value in `t6`, exactly as
# [cap-trap.s](cap-trap.s) does.

        .equ    BULK, 0x100000000
        .equ    REV_WINDOW, 0x2200000
        .equ    INTERVAL, 0x80008000

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        # The two authorities under test, derived from the same root and
        # differing in nothing but the address they name: one over a block on
        # the first class, one over a block on the second. Both are 64-byte
        # aligned, so each names the whole of its own CBO block.
        li      t0, block
        csetaddr c10, c8, t0
        li      t0, BULK
        csetaddr c11, c8, t0

        # The value stored throughout: a capability bounded to `value`, so it
        # carries a base of its own and a round trip that lost anything would
        # show it.
        li      t0, value
        csetaddr c12, c8, t0
        csetboundsimm c12, c12, 64

        # A capability derived on the first class survives a round trip through
        # a second-class granule with its authority intact. The medium reaches
        # the value nowhere: the granule's own plane carries the tag.
        li      gp, 1
        cbo.zero (c11)
        sc      c12, 0(c11)
        lc      c13, 0(c11)
        cgettag t2, c13
        li      t3, 1
        bne     t2, t3, fail
        cseqx   t2, c13, c12
        bne     t2, t3, fail

        # And the write path clears a tag here exactly as it clears one there.
        # Tag clearing is a property of the write and not of the medium
        # (R-15-007r), so the second class neither preserves an authority a data
        # store overwrote nor loses one a capability store put down.
        li      gp, 2
        li      s6, 0x0123456789abcdef
        sd      s6, 0(c11)
        lc      c13, 0(c11)
        cgettag t2, c13
        bnez    t2, fail
        ld      t2, 0(c11)
        bne     t2, s6, fail

        # `cloadtags` returns the same answer over the same pattern on either
        # class, which is the one cost model R-15-007q admits it on: native tags
        # are read in parallel with the data on both media, so the instruction
        # buys issue rather than traffic wherever the group resides.
        li      gp, 3
        cbo.zero (c11)
        cbo.zero (c10)
        sc      c12, 0(c11)
        sc      c12, 16(c11)
        sc      c12, 0(c10)
        sc      c12, 16(c10)
        cloadtags t2, (c11)
        cloadtags t3, (c10)
        bne     t2, t3, fail
        li      t4, 5
        bne     t2, t4, fail

        # Eager zeroize clears both planes on the second class, and the result
        # reads back as an untagged NULL rather than as an all-zeroes bit
        # pattern with an undefined reading (R-15-182, R-15-060). That property
        # is what `cbo.zero` relies on being able to read back, and it is a
        # property of the format rather than of the array it lands in.
        li      gp, 4
        cbo.zero (c11)
        cloadtags t2, (c11)
        bnez    t2, fail
        ld      t2, 0(c11)
        bnez    t2, fail
        lc      c13, 0(c11)
        cgettag t2, c13
        bnez    t2, fail
        cgetaddr t2, c13
        bnez    t2, fail

        # `cbo.scrub` is exactly value- and tag-preserving here too, where a
        # store of the same bits clears the tag: the same contrast
        # [platform-scrub.s](platform-scrub.s) draws on the first class, drawn
        # again on the second because the ECC planes are identical across the
        # boundary and the maintenance pass therefore is (R-15-177a).
        li      gp, 5
        sc      c12, 0(c11)
        sd      s6, 8(c11)
        cbo.scrub (c11)
        cloadtags t2, (c11)
        li      t3, 1
        bne     t2, t3, fail
        lc      c13, 0(c11)
        cseqx   t2, c13, c12
        bne     t2, t3, fail
        ld      t2, 8(c11)
        bne     t2, s6, fail
        ld      t4, 0(c11)
        sd      t4, 0(c11)
        cloadtags t2, (c11)
        bnez    t2, fail

        # **The load filter is keyed by the loaded capability's base and not by
        # where it was loaded from**, so a capability into a revoked first-class
        # granule loses its tag when it is loaded out of a second-class slot.
        # That is R-08-005a read across the boundary: the filter is one
        # mechanism over an address-keyed bitmap, and the class of the slot
        # holding the capability is not one of its inputs.
        li      gp, 6
        li      t0, object
        li      t1, INTERVAL
        sub     t0, t0, t1
        srli    t0, t0, 3
        srli    s2, t0, 6
        andi    s3, t0, 63
        li      s4, 1
        sll     s4, s4, s3
        slli    s5, s2, 3
        li      t0, REV_WINDOW
        csetaddr c14, c8, t0
        cincoffset c15, c14, s5

        li      t0, object
        csetaddr c16, c8, t0
        csetboundsimm c16, c16, 8
        cbo.zero (c11)
        sc      c16, 32(c11)
        lc      c17, 32(c11)
        cgettag t2, c17
        li      t3, 1
        bne     t2, t3, fail
        sd      s4, 0(c15)
        lc      c17, 32(c11)
        cgettag t2, c17
        bnez    t2, fail
        sd      zero, 0(c15)
        lc      c17, 32(c11)
        cseqx   t2, c17, c16
        bne     t2, t3, fail

        # An atomic reaches the second class as a single bounded memory
        # transaction (R-15-087), and its store half clears the tag of the
        # granule it covers exactly as an ordinary store does.
        li      gp, 7
        cbo.zero (c11)
        li      t1, 5
        sd      t1, 48(c11)
        cincoffsetimm c24, c11, 48
        li      t1, 3
        amoadd.d t2, t1, (c24)
        li      t3, 5
        bne     t2, t3, fail
        ld      t2, 48(c11)
        li      t3, 8
        bne     t2, t3, fail
        sc      c12, 40(c11)
        cincoffsetimm c24, c11, 40
        li      t1, 0
        amoadd.d t2, t1, (c24)
        cloadtags t2, (c11)
        bnez    t2, fail

        # And an authority that does not cover a second-class address faults on
        # the authority, with the same cause and the same `mtval` detail it
        # would carry on the first class: the violation names the register that
        # raised it (R-15-073a), and nothing about the medium enters it.
        li      gp, 8
        csetboundsimm c25, c11, 8
        cincoffsetimm c25, c25, 8
        li      t5, 28
        li      t6, 801
        ld      t2, 0(c25)

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
        .align  3
object:
        .space  8
        .align  6
value:
        .space  64
block:
        .space  64
