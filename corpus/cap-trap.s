# SPDX-License-Identifier: Apache-2.0
# The trap path, taken eight times: a capability violation raises one cause
# code and reports its detail in `mtval`, the interrupted PCC is saved whole in
# MEPCC, and `mret` returns to it (R-15-073, R-15-073a).
#
# The handler is installed by writing MTCC, which is reachable because the
# reset PCC carries access-system-registers, and that permission *is* the
# privilege mechanism here rather than a ring (R-15-003).
#
# Each check leaves the cause it expects in `t5` and the trap value it expects
# in `t6`, so the handler is one comparison rather than eight, and a wrong cause
# fails where the fault was raised rather than three checks later. The `mtval`
# payload of a capability violation is the register that raised it above the
# five-bit violation code (core/cap_causes.sail).

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        li      t0, scratch
        csetaddr c10, c8, t0
        csetboundsimm c10, c10, 8

        # A length violation: the authority reaches eight bytes and the access
        # asks for the eight after them.
        li      gp, 1
        li      t5, 28
        li      t6, 0x141
        ld      t0, 8(c10)

        # A tag violation: an integer in a base register is an untagged
        # capability, so the access faults where it is rather than reaching
        # memory (R-15-001c).
        li      gp, 2
        li      t5, 28
        li      t6, 2
        ld      t0, 0(cnull)

        # A store through a read-only authority.
        li      gp, 3
        li      t0, 0x3
        candperm c11, c10, t0
        li      t5, 28
        li      t6, 0x173
        sd      zero, 0(c11)

        # A capability store through an authority that may store data but not
        # capabilities, which is the permission the tag plane turns on.
        li      gp, 4
        li      t0, 0x7
        candperm c12, c10, t0
        li      t5, 28
        li      t6, 405
        sc      c8, 0(c12)

        # A seal violation: a return capability is a backward-edge sentry, and a
        # call may not enter one. `cjalr` writing a link is what makes this a
        # call rather than a return (R-15-071).
        li      gp, 5
        call    .taken
.taken:
        cmove   c13, cra
        li      t5, 28
        li      t6, 419
        cjalr   cra, c13, 0

        # An execute violation: the store side of the root pair carries no
        # execute permission, so jumping to it faults rather than running.
        li      gp, 6
        cmove   c14, c10
        li      t5, 28
        li      t6, 465
        cjr     c14

        # A capability access is always naturally aligned, whatever the
        # platform admits for data, because a capability straddling a granule
        # boundary would have no tag of its own (R-15-203). This one is an
        # ordinary alignment exception rather than a capability violation, which
        # is why the expected cause is passed in rather than assumed.
        li      gp, 7
        li      t0, scratch
        csetaddr c15, c8, t0
        li      t5, 4
        li      t6, scratch + 4
        lc      c16, 4(c15)

        # An unallocated CSR address traps exactly as an unallocated instruction
        # encoding does, and the bank is closed by enumeration (R-15-014,
        # isa-profile.md §5). This is `csrrs t0, 0x3b0, zero`, an address the
        # PMP deletion left with no register behind it.
        li      gp, 8
        li      t5, 2
        li      t6, 0x3b0022f3
        .word   0x3b0022f3

        li      gp, 0
        j       pass

# The handler runs under MTCC's authority, which is the execute side of the
# root pair and so carries the access-system-registers permission the CSR reads
# below need. It resumes the interrupted program past the faulting instruction:
# MEPCC is *not* sealed on the way in, so its integer view can be advanced and
# `mret` returns through it (exceptions/sys_exceptions.sail).
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
scratch:
        .space  64
