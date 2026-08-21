# SPDX-License-Identifier: Apache-2.0
# The capability indexed load and store: bounds and permissions checked on the
# authorising capability at base plus scaled index, and the access performed
# there, with no intermediate capability materialized at any point
# (R-15-007e, R-15-007f).
#
# The last clause is what the fault checks below are for. The pair this
# instruction replaces derives an intermediate with `cincoffset`, and
# `cincoffset` may leave the representable region, in which case the derived
# capability is *untagged* and the fault arrives one instruction later as a tag
# violation on a register the program never named. A single indexed access has
# no derivation step for that case to arise in, so an index the pair could not
# represent is an ordinary length violation on the authority the program did
# name, which is what taking the case off the dereference path means.
#
# Each check leaves the cause it expects in `t5` and the trap value it expects
# in `t6`; the `mtval` payload of a capability violation is the register that
# raised it above the five-bit violation code (core/cap_causes.sail).

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        # An array of eight doublewords, and an authority bounded to it.
        li      t0, array
        csetaddr c10, c8, t0
        csetboundsimm c10, c10, 64

        # The round trip: element three at the doubleword scale.
        li      gp, 1
        li      t0, 0x0123456789abcdef
        li      t1, 3
        csd     t0, c10[t1 << 3]
        cld     t2, c10[t1 << 3]
        bne     t0, t2, fail

        # The scale is part of the address rather than decoration: the same
        # doubleword is index 24 unscaled, index 12 at scale one, and index 6 at
        # scale two. Which scales the compiler emits is the composition-time
        # selection; the field's width is what the freeze fixes (R-15-007g).
        li      gp, 2
        li      t1, 24
        cld     t2, c10[t1 << 0]
        bne     t0, t2, fail
        li      t1, 12
        cld     t2, c10[t1 << 1]
        bne     t0, t2, fail
        li      t1, 6
        cld     t2, c10[t1 << 2]
        bne     t0, t2, fail

        # And it is the same access an ordinary displacement reaches, through
        # the same authority: this replaces a sequence rather than adding a
        # second memory path.
        li      gp, 3
        ld      t2, 24(c10)
        bne     t0, t2, fail

        # Index zero, and the zero register as the index: an index is the
        # integer reading of a register like any other operand.
        li      gp, 4
        li      t0, 0x5a5a5a5a5a5a5a5a
        csd     t0, c10[zero << 3]
        cld     t2, c10[zero << 3]
        bne     t0, t2, fail
        ld      t2, 0(c10)
        bne     t0, t2, fail

        # The store form names three registers, its source in the slot a load
        # writes; what it stores is that register's integer reading.
        li      gp, 5
        li      t1, 7
        li      t0, 0x00ff00ff00ff00ff
        csd     t0, c10[t1 << 3]
        ld      t2, 56(c10)
        bne     t0, t2, fail

        # Past the top of the authority: a length violation naming the
        # authorising register, checked at base plus scaled index.
        li      gp, 6
        li      t1, 8
        li      t5, 28
        li      t6, 0x141
        cld     t2, c10[t1 << 3]

        # And the store side of the same bound.
        li      gp, 7
        li      t5, 28
        li      t6, 0x141
        csd     t0, c10[t1 << 3]

        # An index the offset-then-dereference pair could not have represented:
        # still a length violation on the authority, and still at the access,
        # rather than a tag violation on an intermediate the program never made.
        li      gp, 8
        li      t1, 0x8000000
        li      t5, 28
        li      t6, 0x141
        cld     t2, c10[t1 << 3]

        # The authority is checked for the permission the access needs, exactly
        # as a displaced access is: a read-only view stores nowhere.
        li      gp, 9
        li      t0, 0x3
        candperm c11, c10, t0
        li      t1, 1
        li      t5, 28
        li      t6, 0x173
        csd     t0, c11[t1 << 3]

        # An integer in the base register is an untagged capability, so an
        # indexed access through it faults where it is rather than reaching
        # memory (R-15-001c).
        li      gp, 10
        li      t5, 28
        li      t6, 2
        cld     t2, cnull[t1 << 3]

        li      gp, 0
        j       pass

# The handler resumes the interrupted program past the faulting instruction.
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
array:
        .space  64
