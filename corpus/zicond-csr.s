# SPDX-License-Identifier: Apache-2.0
# Two surfaces that have nothing to do with each other except that both are
# small: `Zicond`, the branchless select that is doubly load-bearing under
# static-only prediction (R-15-054), and the CSR bank, which is closed by
# enumeration (R-15-014, isa-profile.md §5).
#
# The bank's *absent* half is `cap-trap`'s, where an unallocated address traps.
# What is here is the present half: what each surviving register reads, which
# ones are writable, and the four capability registers `cspecialrw` reaches.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1

        # `czero.eqz` clears its result where the condition is zero and passes
        # the value through where it is not; `czero.nez` is the other polarity.
        # Together they are a select with no branch and no data-dependent
        # timing.
        li      gp, 1
        li      t0, 0x1234
        li      t1, 0
        czero.eqz t2, t0, t1
        bnez    t2, fail
        czero.nez t2, t0, t1
        li      t3, 0x1234
        bne     t2, t3, fail

        li      gp, 2
        li      t1, 1
        czero.eqz t2, t0, t1
        li      t3, 0x1234
        bne     t2, t3, fail
        czero.nez t2, t0, t1
        bnez    t2, fail

        # The select an if-conversion emits: one arm masked, the other masked
        # the other way, and the two combined with an `or` that cannot carry.
        li      gp, 3
        li      t0, 0xaaaa
        li      t1, 0xbbbb
        li      t2, 0
        czero.nez t3, t0, t2
        czero.eqz t4, t1, t2
        or      t5, t3, t4
        li      t6, 0xaaaa
        bne     t5, t6, fail
        li      t2, 1
        czero.nez t3, t0, t2
        czero.eqz t4, t1, t2
        or      t5, t3, t4
        li      t6, 0xbbbb
        bne     t5, t6, fail

        # `mcause` is writable and reads back what was written, which is what
        # makes the CSR trio's read-modify-write behaviour checkable at all.
        li      gp, 4
        li      t0, 0x25
        csrrw   t1, mcause, t0
        csrr    t2, mcause
        bne     t2, t0, fail
        li      t0, 0x42
        csrrw   t1, mcause, t0
        li      t3, 0x25
        bne     t1, t3, fail

        li      gp, 5
        li      t0, 0x100
        csrrs   t1, mcause, t0
        csrr    t2, mcause
        li      t3, 0x142
        bne     t2, t3, fail
        li      t0, 0x42
        csrrc   t1, mcause, t0
        csrr    t2, mcause
        li      t3, 0x100
        bne     t2, t3, fail

        # The immediate forms name a five-bit unsigned constant where the
        # register forms name a register, and nothing else differs.
        li      gp, 6
        csrrwi  t1, mcause, 7
        csrr    t2, mcause
        li      t3, 7
        bne     t2, t3, fail
        csrrsi  t1, mcause, 8
        csrr    t2, mcause
        li      t3, 15
        bne     t2, t3, fail
        csrrci  t1, mcause, 1
        csrr    t2, mcause
        li      t3, 14
        bne     t2, t3, fail

        # `misa` is read-only, so there is no runtime ISA morphing and therefore
        # no runtime CHERI disable (R-15-052).
        li      gp, 7
        csrr    t0, misa
        li      t1, 0
        csrrw   t2, misa, t1
        csrr    t2, misa
        bne     t2, t0, fail
        beqz    t0, fail

        # The four implementation identifiers are hardwired zero, one Sail model
        # frozen with the proof leaving no discovery question to ask
        # (R-15-052a). `mhartid` is the one with a consumer, and this
        # configuration composes a single hart at zero.
        li      gp, 8
        csrr    t0, mvendorid
        bnez    t0, fail
        csrr    t0, marchid
        bnez    t0, fail
        csrr    t0, mimpid
        bnez    t0, fail
        csrr    t0, mconfigptr
        bnez    t0, fail
        csrr    t0, mhartid
        bnez    t0, fail

        # `mie` keeps the machine-timer bit alone, so a write of all ones
        # legalizes to `MTIE`: what was deleted here is fields, not registers
        # (R-15-066a). `mip` is read-only outright, its one writer being the
        # timer comparator, so the check is that a write does not move it and
        # not that it reads zero: `MTIP` is set at reset, where `mtimecmp` is
        # zero and nothing has armed it.
        li      gp, 9
        li      t0, -1
        csrrw   t1, mie, t0
        csrr    t2, mie
        li      t3, 0x80
        bne     t2, t3, fail
        csrr    t3, mip
        csrrw   t1, mip, t0
        csrr    t2, mip
        bne     t2, t3, fail

        # MTDC is granted rather than assumed, so it starts untagged and holds
        # what `cspecialrw` puts in it. The permission that reaches it is the
        # access-system-registers bit on PCC, which is what privilege is here
        # (R-15-003).
        li      gp, 10
        cspecialrw c10, mtdc, c8
        cgettag t0, c10
        bnez    t0, fail
        cspecialrw c11, mtdc, cnull
        cseqx   t0, c11, c8
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
