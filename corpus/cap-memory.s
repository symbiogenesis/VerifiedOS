# The tag plane: what a capability store and load do to it, what an ordinary
# data store does to it, and what the two block instructions read and clear.
#
# Tag clearing is a property of the **write path** rather than an instruction
# (R-15-007r), the tag is keyed per 64-bit granule (R-15-203), and a load
# through an authority that may not carry capabilities delivers its value
# untagged rather than faulting (R-08-005b). All three are checked here rather
# than asserted.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        li      t0, scratch
        csetaddr c10, c8, t0

        # A capability survives a round trip through memory whole: same tag,
        # same bounds, same permissions, same object type.
        li      gp, 1
        sc      c8, 0(c10)
        lc      c11, 0(c10)
        cgettag t0, c11
        li      t1, 1
        bne     t0, t1, fail
        cseqx   t0, c11, c8
        li      t1, 1
        bne     t0, t1, fail

        # An ordinary data store over the same granule clears its tag, which is
        # what makes tag clearing a property of the write path and not an
        # instruction of its own.
        li      gp, 2
        sd      zero, 0(c10)
        lc      c12, 0(c10)
        cgettag t0, c12
        bnez    t0, fail

        # The tag belongs to the granule and not to its neighbours: a store into
        # one leaves the next standing.
        li      gp, 3
        sc      c8, 0(c10)
        sc      c8, 8(c10)
        sd      zero, 0(c10)
        lc      c12, 8(c10)
        cgettag t0, c12
        li      t1, 1
        bne     t0, t1, fail

        # `cloadtags` reports a whole block's tags as stored, in one operand
        # rather than in eight load-use latencies, and the block is the one
        # `cbo.zero` allocates rather than a cache line (R-15-007q).
        li      gp, 4
        sd      zero, 8(c10)
        sc      c8, 0(c10)
        sc      c8, 16(c10)
        cloadtags t0, (c10)
        li      t1, 5
        bne     t0, t1, fail

        # `cbo.zero` takes the data and the tags together, which is the whole of
        # the reclamation discipline: where a region is reclaimed the data is
        # dead and goes with the tags (R-15-007r, R-15-182).
        li      gp, 5
        cbo.zero (c10)
        cloadtags t0, (c10)
        bnez    t0, fail
        ld      t0, 0(c10)
        bnez    t0, fail
        ld      t0, 56(c10)
        bnez    t0, fail

        # An all-zeroes granule reads back as the untagged null capability,
        # which is the property eager zeroize relies on (R-15-182).
        li      gp, 6
        lc      c13, 0(c10)
        cgettag t0, c13
        bnez    t0, fail
        cgetperm t0, c13
        bnez    t0, fail
        cseqx   t0, c13, cnull
        li      t1, 1
        bne     t0, t1, fail

        # Load transitivity: an authority without `load-global` yields a local
        # result and one without `load-mutable` yields a read-only one, and both
        # are exact rather than rounded, because the read half of an admitted
        # set is itself an admitted set (R-15-074).
        li      gp, 7
        sc      c8, 0(c10)
        li      t0, 0xb
        candperm c14, c10, t0
        cgetperm t0, c14
        li      t1, 0xb
        bne     t0, t1, fail
        lc      c15, 0(c14)
        cgettag t0, c15
        li      t1, 1
        bne     t0, t1, fail
        cgetperm t0, c15
        li      t1, 0xca
        bne     t0, t1, fail
        andi    t1, t0, 1
        bnez    t1, fail

        # Without `load-capability` the load still succeeds and still delivers
        # its bits; what it does not deliver is the tag. That is the same shape
        # the revocation filter's result takes (R-08-005b).
        li      gp, 8
        li      t0, 0x3
        candperm c16, c10, t0
        lc      c17, 0(c16)
        cgettag t0, c17
        bnez    t0, fail
        cgetaddr t0, c17
        cgetaddr t1, c8
        bne     t0, t1, fail

        # A capability store is authorised by the base register like any other
        # access, so a narrowed authority reaches exactly its own extent. The
        # out-of-bounds half is a fault and is `cap-trap`'s.
        li      gp, 9
        csetboundsimm c18, c10, 16
        sc      c8, 8(c18)
        lc      c19, 8(c10)
        cgettag t0, c19
        li      t1, 1
        bne     t0, t1, fail

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
scratch:
        .space  128
