# SPDX-License-Identifier: Apache-2.0
# The core class, from the only side a program reaches it from.
#
# There is one Sail model parameterized by core class and one capability
# encoding (R-15-005), and heterogeneity lives in the datapath rather than in
# the trust structure (R-04-009): the classes share the base ISA, the capability
# model, and the kernel binary, and differ only in execution resources. So the
# class is **not architectural state**. No CSR reports it, no instruction reads
# it, and nothing in the decode surface branches on it; one kernel binary runs
# unmodified on every class and selects its per-hart state, the core's class,
# and the island binding from `mhartid` against the attested devicetree at boot
# (R-15-052b, R-09-007).
#
# That leaves exactly two things a program can see, and this member is about
# both. The **identity** is `mhartid`, which indexes the composed roster rather
# than standing beside it, so its value is a composition-time constant and the
# register is otherwise inert. The **geometry** is `vlenb`, the one figure from
# the class table that reaches the instruction set: at the C class's declared
# VLEN of 256 bits it reads 32, and a composition whose roster puts this hart on
# a class declaring some other vector length is refused before it runs
# (postlude/validate_config.sail).
#
# The contrast the last three checks draw is the point. `vmclear` and `fence.t`
# are the partition switch (R-07-014c, R-15-213), and what they scrub is what a
# partition did; what a core *is* survives both, because a class is fixed at
# composition and there is no migration between classes (R-07-013).
#
# The handler is installed by writing MTCC, which is reachable because the reset
# PCC carries access-system-registers, and the one faulting check leaves the
# cause it expects in `t5` and the trap value in `t6`, exactly as
# [cap-trap.s](cap-trap.s) does.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        # The identity is the roster row this model was built as. This
        # composition names one hart and the roster puts it at zero, and reading
        # twice is how *inert* is checked at all: the register carries no
        # per-partition state, so a read is not an event.
        li      gp, 1
        csrr    t0, mhartid
        bnez    t0, fail
        csrr    t1, mhartid
        bne     t1, t0, fail

        # And it is read-only, so a partition cannot present itself as another
        # core. `mhartid` is at 0xF14, whose top two address bits are the
        # read-only encoding, so the write traps as an unallocated encoding does
        # rather than being quietly dropped (R-15-052b, R-15-014). This is
        # `csrrw zero, mhartid, t0`, assembled by hand because a corpus program
        # that meant to write a read-only CSR is indistinguishable from one that
        # did it by accident.
        li      gp, 2
        li      t5, 2
        li      t6, 0xf1429073
        .word   0xf1429073

        # The geometry, which is the one class-table figure the instruction set
        # carries. Reaching a vector CSR at all needs the extension-context gate
        # on, `mstatus.VS` being what a partition setup turns on for a partition
        # that may use the unit (R-07-012, R-15-049).
        li      gp, 3
        li      t0, 0x200
        csrrs   zero, mstatus, t0
        csrr    t1, vlenb
        li      t2, 32
        bne     t1, t2, fail

        # Dirty the partition's vector configuration, so the clear below has
        # something to clear and the contrast has two sides.
        li      gp, 4
        li      t0, 7
        csrrw   zero, vcsr, t0
        csrr    t1, vcsr
        li      t2, 7
        bne     t1, t2, fail

        # The switch's eager zeroize scrubs what the partition did and leaves
        # what the core is. `vcsr` goes to zero and `vtype` to *no
        # configuration*, which is `vill` set rather than all zeroes; `vlenb`
        # and `mhartid` do not move, because a vector length and a hart identity
        # are composition constants and not context (R-07-014c, R-15-069d).
        li      gp, 5
        vmclear
        csrr    t1, vcsr
        bnez    t1, fail
        csrr    t1, vtype
        bgez    t1, fail
        csrr    t1, vlenb
        li      t2, 32
        bne     t1, t2, fail
        csrr    t1, mhartid
        bnez    t1, fail

        # The other half of the switch is the flush, whose set is a single
        # structure (R-15-213). It disturbs neither figure for the same reason:
        # neither is in the set, and neither is in any set, being properties of
        # the composition rather than state the machine accumulated.
        li      gp, 6
        fence.t
        csrr    t1, vlenb
        li      t2, 32
        bne     t1, t2, fail
        csrr    t1, mhartid
        bnez    t1, fail

        # And the gate itself is not the class. A partition may turn the vector
        # unit off for itself, which makes the unit unreachable and changes
        # nothing about what core this is: the identity still reads through, and
        # the geometry is unmoved when the gate comes back. This is why
        # `vmclear` gates on the class rather than on the context (R-15-069d).
        li      gp, 7
        li      t0, 0x600
        csrrc   zero, mstatus, t0
        csrr    t1, mhartid
        bnez    t1, fail
        li      t0, 0x200
        csrrs   zero, mstatus, t0
        csrr    t1, vlenb
        li      t2, 32
        bne     t1, t2, fail

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