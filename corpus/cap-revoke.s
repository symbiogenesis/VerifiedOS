# SPDX-License-Identifier: Apache-2.0
# The revocation filter and the sidecar behind it (R-08-005, R-08-005a,
# R-08-005b).
#
# *Freed ⇒ unreachable* holds at **access** time and not at sweep completion:
# the bit is set, and the next load of a stale capability delivers it with its
# validity tag cleared. That clear is one of the load's own defined results, so
# nothing traps, no cause code is raised, and the value itself arrives
# unchanged — which is the shape a load *has* to have for the check to be
# expressible at all.
#
# The program plays both parts. It is the kernel revocation path when it writes
# the bitmap through the sidecar's window, and it is the compartment holding a
# stale capability when it loads one back; on the composed machine those are two
# principals, separated by which of them the distribution hands a capability to
# that window (R-15-003), and there is nothing else separating them, because the
# bitmap is not addressable as data.
#
# The address arithmetic below is the sweep's own: a granule index is the
# offset from the covered interval's base over the granule width, and the word
# and bit it selects follow from that. It is computed rather than assembled in
# so that moving the object moves the bit with it.

        .equ    REV_WINDOW, 0x2200000
        .equ    INTERVAL, 0x80008000

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1

        # The object: a bounded view of `arena`, so its *base* is `arena` and
        # that is the granule the filter indexes by, whatever address the
        # capability happens to carry.
        li      t0, arena
        csetaddr c10, c8, t0
        csetboundsimm c10, c10, 64

        # The slot the capability is stored in, and the window the bitmap is
        # updated through.
        li      t0, slot
        csetaddr c11, c8, t0
        li      t0, REV_WINDOW
        csetaddr c12, c8, t0

        # The sweep's arithmetic: granule index, then the word and the bit.
        li      t0, arena
        li      t1, INTERVAL
        sub     t0, t0, t1
        srli    t0, t0, 3
        srli    s2, t0, 6
        andi    s3, t0, 63
        li      s4, 1
        sll     s4, s4, s3
        slli    s5, s2, 3
        cincoffset c13, c12, s5

        # The window round-trips: what the kernel writes is what it reads back,
        # and the plane the filter reads is that same structure rather than a
        # copy of it.
        li      gp, 1
        sd      s4, 0(c13)
        ld      t2, 0(c13)
        bne     t2, s4, fail
        sd      zero, 0(c13)
        ld      t2, 0(c13)
        bnez    t2, fail

        # Live: the capability comes back whole.
        li      gp, 2
        sc      c10, 0(c11)
        lc      c14, 0(c11)
        cgettag t2, c14
        li      t3, 1
        bne     t2, t3, fail

        # Revoked: the same load, and it still succeeds. What changes is the
        # tag; the bits are the bits that were stored.
        li      gp, 3
        sd      s4, 0(c13)
        lc      c14, 0(c11)
        cgettag t2, c14
        bnez    t2, fail
        cgetaddr t2, c14
        cgetaddr t3, c10
        bne     t2, t3, fail

        # Clearing the bit puts the object back in service, which is the
        # quarantine's other end: nothing about the stored capability changed.
        li      gp, 4
        sd      zero, 0(c13)
        lc      c14, 0(c11)
        cseqx   t2, c14, c10
        li      t3, 1
        bne     t2, t3, fail

        # The bit is keyed by the loaded capability's **base**, not by the
        # address it carries and not by the address it was loaded from: a stale
        # capability pointing into the middle of a freed object is caught
        # exactly as one pointing at its start is.
        li      gp, 5
        cincoffsetimm c15, c10, 32
        sc      c15, 8(c11)
        sd      s4, 0(c13)
        lc      c16, 8(c11)
        cgettag t2, c16
        bnez    t2, fail

        # A base outside the covered union takes the same path with a constant
        # live result. The root data capability's base is the bottom of the
        # address space, which no revocable interval covers, so it survives a
        # bitmap that is set for the object beside it.
        li      gp, 6
        sc      c8, 16(c11)
        lc      c17, 16(c11)
        cgettag t2, c17
        li      t3, 1
        bne     t2, t3, fail

        # The plane has no opinion about data. An untagged value round-trips
        # through the same granule whatever the bit says, or an integer would
        # not survive memory.
        li      gp, 7
        li      t4, 0x0123456789abcdef
        sd      t4, 24(c11)
        ld      t2, 24(c11)
        bne     t2, t4, fail
        lc      c18, 24(c11)
        cgettag t2, c18
        bnez    t2, fail
        cgetaddr t2, c18
        li      t3, 0xfffffffff
        and     t3, t4, t3
        bne     t2, t3, fail

        # And no opinion about the authority: the filter runs on the value a
        # load delivers, not on the capability that authorised it.
        li      gp, 8
        cgettag t2, c11
        li      t3, 1
        bne     t2, t3, fail

        # `cloadtags` reports the tags **as stored** rather than as the filter
        # would return them, which is one of the two parameters the profile
        # fixes where the pin leaves them open: the filter has no base to index
        # by when no capability is loaded (R-15-007q, R-08-007). So the sweep
        # reading a block sees the capability that is there, and the load of
        # that same granule still comes back revoked.
        li      gp, 9
        li      t0, block
        csetaddr c19, c8, t0
        cbo.zero (c19)
        sc      c10, 0(c19)
        cloadtags t2, (c19)
        li      t3, 1
        bne     t2, t3, fail
        lc      c20, 0(c19)
        cgettag t2, c20
        bnez    t2, fail
        sd      zero, 0(c13)

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
        .align  6
arena:
        .space  64
slot:
        .space  64
        .align  6
block:
        .space  64
