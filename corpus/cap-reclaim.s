# SPDX-License-Identifier: Apache-2.0
# The block revocation reclaim: the §8 sweep's inner loop as one instruction
# (R-15-007s, R-08-007b).
#
# The program is the sweep. It writes the bitmap through the sidecar's window as
# the kernel revocation path does, then walks a granule group as the sweep task
# does, one `creclaim` per group; on the composed machine those are the same
# principal and it is the only one holding a capability to that window
# (R-08-005a, R-15-003).
#
# **The instruction is the conditional form and that is why it is admissible at
# all.** A *bulk* tag clear over a group is excluded, because it destroys
# authority wholesale with nothing deciding which (R-15-007r); this one clears a
# granule only where the load filter's own predicate says the capability in it is
# dead, so what it can do to a granule is exactly what the next capability load
# of that granule would have done to the value it delivered (R-08-005b).
#
# **What separates it from that load is where the clear lands.** The filter
# clears the *value the load delivers* and leaves memory alone, so clearing the
# bit puts the object back in service ([cap-revoke.s](cap-revoke.s)). `creclaim`
# clears the tag *in memory*, so it does not: that is the reclamation half of the
# protocol rather than the containment half, and check 7 below is the difference
# stated as a program.

        .equ    REV_WINDOW, 0x2200000
        .equ    INTERVAL, 0x80008000

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1

        # Two objects with **different bases**, so the bit that decides one does
        # not decide the other. That is the property the whole instruction rests
        # on: the predicate is the stored capability's base and not the granule
        # it happens to be sitting in.
        li      t0, obj_a
        csetaddr c10, c8, t0
        csetboundsimm c10, c10, 64
        li      t0, obj_b
        csetaddr c11, c8, t0
        csetboundsimm c11, c11, 64

        # The group the sweep walks, which is a third place again: neither
        # object lives in the block that holds the capabilities to them.
        li      t0, block
        csetaddr c12, c8, t0

        # The bitmap's window, and the word and bit that name `obj_a`'s base
        # granule. The arithmetic is the sweep's own: a granule index is the
        # offset from the covered interval's base over the granule width.
        li      t0, REV_WINDOW
        csetaddr c13, c8, t0
        li      t0, obj_a
        li      t1, INTERVAL
        sub     t0, t0, t1
        srli    t0, t0, 3
        srli    s2, t0, 6
        andi    s3, t0, 63
        li      s4, 1
        sll     s4, s4, s3
        slli    s5, s2, 3
        cincoffset c14, c13, s5

        # The group: two capabilities and one doubleword of data, so the pass has
        # a granule with no tag to consider and no base to index by.
        li      gp, 1
        cbo.zero (c12)
        sc      c10, 0(c12)
        sc      c11, 8(c12)
        li      s6, 0x0123456789abcdef
        sd      s6, 16(c12)
        cloadtags t2, (c12)
        li      t3, 3
        bne     t2, t3, fail

        # Keep the first granule's bits, so the claim that a cleared granule
        # differs in its tag and in nothing else has something to be checked
        # against.
        ld      s7, 0(c12)

        # With no bit set the pass changes nothing and says so. A sweep over a
        # live domain is not a no-op by accident: every granule still takes its
        # cycle, which is what keeps the sweep one entry per group in the
        # timing-annotated model rather than a function of what it finds.
        li      gp, 2
        creclaim t2, (c12)
        li      t3, 3
        bne     t2, t3, fail

        # `obj_a` is freed. The bit is set, and the pass clears that granule's
        # tag and returns the tags that survive it.
        li      gp, 3
        sd      s4, 0(c14)
        creclaim t2, (c12)
        li      t3, 2
        bne     t2, t3, fail

        # No data is written by either case: the cleared granule holds the bits
        # it held, and the value was never materialized to clear it.
        li      gp, 4
        ld      t2, 0(c12)
        bne     t2, s7, fail
        ld      t2, 16(c12)
        bne     t2, s6, fail

        # The clear is what a load of that granule now sees, and the granule
        # beside it is untouched: same block, same instruction, different bases.
        li      gp, 5
        lc      c15, 0(c12)
        cgettag t2, c15
        bnez    t2, fail
        lc      c16, 8(c12)
        cgettag t2, c16
        li      t3, 1
        bne     t2, t3, fail
        cseqx   t2, c16, c11
        bne     t2, t3, fail

        # A second pass over the same group answers the same thing. The sweep may
        # revisit a group without its result depending on how many times it has,
        # which is what lets the quantum be a group count rather than a schedule.
        li      gp, 6
        creclaim t2, (c12)
        li      t3, 2
        bne     t2, t3, fail

        # **The clear is in memory and the filter's is not.** Clearing the
        # revocation bit puts the *object* back in service, and a capability the
        # filter had been clearing would come back whole; this one does not,
        # because its tag is gone from the granule rather than from a delivered
        # value. That is the reclamation half of the protocol: the bit and the
        # granule under it return to service, and the authority that named the
        # dead object does not (R-08-007a).
        li      gp, 7
        sd      zero, 0(c14)
        lc      c17, 0(c12)
        cgettag t2, c17
        bnez    t2, fail
        cloadtags t2, (c12)
        li      t3, 2
        bne     t2, t3, fail

        # And the pass ends at its group boundary. The next group is the sweep
        # task's next instruction, so nothing continues autonomously past this
        # one: a second group holding a capability to the same freed object is
        # left standing by a `creclaim` over the first, however many bits are
        # set, and takes its own instruction to reach (R-08-009).
        li      gp, 8
        li      t0, block
        addi    t0, t0, 64
        csetaddr c18, c8, t0
        cbo.zero (c18)
        sc      c10, 0(c18)
        sd      s4, 0(c14)
        creclaim t2, (c12)
        li      t3, 2
        bne     t2, t3, fail
        cloadtags t2, (c18)
        li      t3, 1
        bne     t2, t3, fail
        creclaim t2, (c18)
        bnez    t2, fail
        sd      zero, 0(c14)

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
obj_a:
        .space  64
obj_b:
        .space  64
block:
        .space  128
