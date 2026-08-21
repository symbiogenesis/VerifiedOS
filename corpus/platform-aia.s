# SPDX-License-Identifier: Apache-2.0
# The two platform rows that are not capability instructions: `fence.t` and the
# machine-level interrupt file (R-15-062, R-15-064, R-15-065).
#
# They are together here because both are things the machine *does not* do.
# `fence.t`'s flush set is a single structure, the store buffer, everything else
# a temporal fence would name having been deleted or made partition-owned, so on
# an in-order single-copy machine its whole architectural content is that it
# retires having disturbed nothing. And an MSI is latched pending state that
# software polls, never a control transfer: the external-interrupt field is
# hardwired zero, so sending one moves a bit in a device and moves nothing in
# the core.
#
# Sending is a **store**, which is what makes interrupt-send authority a write
# capability in the composed topology rather than an entry in a side table. Here
# one program holds both the sender's authority and the receiver's; on the
# composed machine the distribution separates them, and nothing else does.

        .equ    IMSIC, 0x2100000

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        li      t0, IMSIC
        csetaddr c9, c8, t0
        li      t0, IMSIC + 8
        csetaddr c10, c8, t0

        # `fence.t` retires and disturbs nothing: not a register's integer
        # reading, and not the authority beside it in the same register.
        li      gp, 1
        li      t3, 0x0123456789abcdef
        cmove   c11, c8
        fence.t
        li      t4, 0x0123456789abcdef
        bne     t3, t4, fail
        cseqx   t0, c11, c8
        li      t1, 1
        bne     t0, t1, fail
        cgettag t0, c11
        li      t1, 1
        bne     t0, t1, fail

        # Sending identity five sets bit five of the pending array and nothing
        # else. The read is an ordinary load, the indirect interface that would
        # otherwise carry it being excluded (R-15-065).
        li      gp, 2
        sd      zero, 0(c10)
        li      t0, 5
        sd      t0, 0(c9)
        ld      t1, 0(c10)
        li      t2, 32
        bne     t1, t2, fail

        # Pending state accumulates: a second sender's identity joins the first
        # rather than replacing it, which is what *latched* means.
        li      gp, 3
        li      t0, 9
        sd      t0, 0(c9)
        ld      t1, 0(c10)
        li      t2, 0x220
        bne     t1, t2, fail

        # The receiver clears by writing the array back.
        li      gp, 4
        sd      zero, 0(c10)
        ld      t1, 0(c10)
        bnez    t1, fail

        # Identity zero is reserved: it cannot be sent, and it cannot be set by
        # writing the array either.
        li      gp, 5
        sd      zero, 0(c9)
        ld      t1, 0(c10)
        bnez    t1, fail
        li      t0, -1
        sd      t0, 0(c10)
        ld      t1, 0(c10)
        li      t2, -2
        bne     t1, t2, fail
        sd      zero, 0(c10)

        # An identity outside the file sets nothing rather than faulting: a
        # sender's authority is the capability it stored through, not the number
        # it chose.
        li      gp, 6
        li      t0, 64
        sd      t0, 0(c9)
        ld      t1, 0(c10)
        bnez    t1, fail

        # The doorbell is write-only. Reading back the number a sender wrote
        # would give the pending state a second name.
        li      gp, 7
        li      t0, 5
        sd      t0, 0(c9)
        ld      t1, 0(c9)
        bnez    t1, fail

        # And the send raised nothing. `mip` is narrowed to the machine-timer
        # bit, the external- and software-interrupt fields being hardwired zero
        # (R-15-066a), so an MSI that has just been latched leaves the core's
        # only asynchronous trap source untouched.
        li      gp, 8
        csrr    t1, mip
        li      t2, 0xffffffffffffff7f
        and     t1, t1, t2
        bnez    t1, fail
        ld      t1, 0(c10)
        li      t2, 32
        bne     t1, t2, fail
        sd      zero, 0(c10)

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
