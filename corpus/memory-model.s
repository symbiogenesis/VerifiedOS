# SPDX-License-Identifier: Apache-2.0
# The memory model, exercised from the only side a program reaches it from.
#
# The architectural memory model is Ztso, adopted normatively in place of RVWMO
# (R-15-004), and under it the only reordering the machine exhibits is a store
# passing a later load through the store buffer (R-15-015). So `fence` collapses
# to two semantics and not two hundred and fifty-six: it drains the buffer iff
# its predecessor set contains a write and its successor set contains a read,
# and every other combination, `fence.tso` included, is a semantic no-op
# (R-15-017).
#
# **Which leaves this member two jobs, and neither of them is validating TSO.**
# One hart over single-copy memory has no execution that separates TSO from
# sequential consistency, so the ordering itself is an RTL-against-Sail
# obligation and not a thing a program can run into (R-15-016). What a program
# can run into is the *decode surface*, and that is where the profile diverges
# from the base ISA outright: the base ISA tells an implementation to treat a
# reserved `fm` as `fm`=0000 and execute it, and this profile traps it, because
# all reserved, custom, and unused encodings trap rather than silently executing
# (R-15-014). Checks 1 through 6 are therefore claims that a fence disturbs
# nothing and that a value is already where a fence would have put it; check 7
# is the reserved-`fm` trap; and check 8 is the residual class that stays legal
# and ignored, which is the contrast the trap is only meaningful against.
#
# Prediction is the other half of this milestone and has no check here at all,
# which is a fact about what a model can hold rather than an omission. All
# branch prediction is static, a fixed function of the encoding and the
# displacement sign with zero mutable predictor state (R-15-019), and the
# deletion is discharged structurally by rows A-04 through A-06 of the
# microarchitectural absence contract rather than by refinement (R-15-021):
# Sail carries architectural state, so no model and no program over it can state
# *there is no branch predictor*. Every branch below is answered the same way by
# a machine that predicts and one that does not.
#
# The handler is installed by writing MTCC, and the faulting check leaves the
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

        # The state every fence below must leave alone: an integer register and
        # a capability with its validity tag set. A fence that cleared a tag
        # would be a fence that destroyed authority, and no integer comparison
        # would notice (R-15-007i, R-15-007r).
        li      t0, scratch
        csetaddr c10, c8, t0
        csetboundsimm c10, c10, 64
        li      s6, 0x0123456789abcdef
        li      t3, 1

        # The draining arm: a predecessor set containing a write and a successor
        # set containing a read.
        li      gp, 1
        fence   rw, rw
        cgettag t2, c10
        bne     t2, t3, fail
        bne     s6, s6, fail

        # The minimal drain, and the one that shows the condition is over the
        # sets rather than over their size: `w, r` is the smallest pair that
        # drains, being exactly a write predecessor and a read successor.
        li      gp, 2
        fence   w, r
        cgettag t2, c10
        bne     t2, t3, fail

        # The mirror of it is a no-op: a read predecessor and a write successor
        # ask for the ordering Ztso already gives, which is every ordering but
        # the one the drain exists for.
        li      gp, 3
        fence   r, w
        cgettag t2, c10
        bne     t2, t3, fail

        # The I and O bits are read, which is the one place this profile's
        # `fence` diverges from upstream's semantics rather than from its
        # encoding: upstream ignores them here and made the implication a bit of
        # `menvcfg`, which left with the mode it gated (R-15-017).
        li      gp, 4
        fence   o, i
        cgettag t2, c10
        bne     t2, t3, fail

        # An empty set on either side is a no-op whatever stands on the other.
        li      gp, 5
        fence   0, rw
        fence   rw, 0
        fence.tso
        fence.t
        cgettag t2, c10
        bne     t2, t3, fail

        # A store is visible to the next load with no fence between them, and
        # interposing the drain changes nothing. This is not evidence that the
        # machine is TSO; it is the statement that the model cannot distinguish
        # TSO from sequential consistency, which is why R-15-016 puts the
        # guarantee on the RTL side. Both directions are run, because a drain
        # that had become a clobber would pass the first alone.
        li      gp, 6
        sd      s6, 0(c10)
        ld      t2, 0(c10)
        bne     t2, s6, fail
        fence   rw, rw
        ld      t2, 0(c10)
        bne     t2, s6, fail
        sc      c10, 32(c10)
        fence   w, r
        lc      c11, 32(c10)
        cgettag t2, c11
        bne     t2, t3, fail

        # A reserved `fm` traps. This is `fence` at `fm`=0001 over `rw, rw`, an
        # encoding the base ISA would have an implementation execute as
        # `fm`=0000 and this profile refuses (R-15-014, R-15-017). It is the one
        # architecturally observable difference the memory model makes.
        li      gp, 7
        li      t5, 2
        li      t6, 0x1330000f
        .word   0x1330000f

        # And the class that stays legal and ignored, without which the trap
        # above would read as a rule about reserved fields rather than about
        # reserved encodings. `rs1` and `rd` are reserved for finer-grained
        # fences of a *future* extension, so a program that sets them is asking
        # for a fence this machine is entitled to give it in full: this is
        # `fence rw, rw` with `rs1`=x5 and `rd`=x6, which retires and writes
        # nothing. `fence.t`'s own reserved fields trap instead, that
        # instruction having no future extension to reserve them for.
        li      gp, 8
        li      t1, 0x5a5a5a5a
        .word   0x0332830f
        li      t2, 0x5a5a5a5a
        bne     t1, t2, fail
        cgettag t2, c10
        bne     t2, t3, fail

        li      gp, 0
        j       pass

# The handler runs under MTCC's authority, which is the execute side of the root
# pair and so carries the access-system-registers permission the CSR reads below
# need. It resumes the interrupted program past the faulting instruction: MEPCC
# is *not* sealed on the way in, so its integer view can be advanced and `mret`
# returns through it (exceptions/sys_exceptions.sail).
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
scratch:
        .space  64
