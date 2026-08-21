# The monotone derivations, and the one rule that makes them monotone: a
# derivation that would exceed its input yields an **untagged** result rather
# than trapping, so a failed derivation is a data result that faults at its next
# dereference and carries no cause code and no control-flow term in a timing
# bound (R-15-007h).
#
# Every check here is on that shape. Nothing in this program traps; the faults
# are `cap-trap`'s.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        # Narrowing takes the base from the input's address and the length from
        # the operand. At 64 bytes it is byte-exact, the frozen widths being
        # exact to 128 (R-15-007c).
        li      gp, 1
        csetboundsimm c10, c8, 64
        cgettag t0, c10
        li      t1, 1
        bne     t0, t1, fail
        cgetbase t0, c10
        bnez    t0, fail
        cgetlen t0, c10
        li      t1, 64
        bne     t0, t1, fail

        # Widening is the case the rule exists for: the result is constructed
        # and handed back with its tag cleared rather than refused.
        li      gp, 2
        csetboundsimm c11, c10, 128
        cgettag t0, c11
        bnez    t0, fail
        cgetlen t0, c11
        li      t1, 128
        bne     t0, t1, fail

        # An address may move inside the representable region and keep its
        # authority, which is what makes an offset an offset.
        li      gp, 3
        cincoffsetimm c12, c10, 32
        cgettag t0, c12
        li      t1, 1
        bne     t0, t1, fail
        cgetaddr t0, c12
        li      t1, 32
        bne     t0, t1, fail
        cgetoffset t0, c12
        li      t1, 32
        bne     t0, t1, fail
        cgetlen t0, c12
        li      t1, 64
        bne     t0, t1, fail

        # Far enough out it is unrepresentable, and then the same rule applies:
        # an untagged result, not a trap.
        li      gp, 4
        cincoffsetimm c13, c10, 2000
        cgettag t0, c13
        bnez    t0, fail
        li      t1, 0x100000
        csetaddr c13, c10, t1
        cgettag t0, c13
        bnez    t0, fail

        # `csetoffset` addresses from the base where `csetaddr` addresses
        # absolutely, which on a capability based at zero is the same number and
        # on one based elsewhere is not.
        li      gp, 5
        li      t0, 0x40
        csetaddr c14, c8, t0
        csetboundsimm c14, c14, 64
        li      t1, 16
        csetoffset c15, c14, t1
        cgetaddr t0, c15
        li      t1, 0x50
        bne     t0, t1, fail
        li      t1, 16
        csetaddr c15, c14, t1
        cgetaddr t0, c15
        li      t1, 16
        bne     t0, t1, fail

        # A mask reaches a non-orthogonal permission field by naming the
        # *expanded* bitmap: the result is the largest admitted set inside the
        # intersection, so `candperm` can only ever remove (R-15-007b).
        li      gp, 6
        li      t0, 0x3
        candperm c16, c8, t0
        cgetperm t1, c16
        li      t2, 0x3
        bne     t1, t2, fail

        li      gp, 7
        li      t0, -1
        candperm c17, c8, t0
        cgetperm t1, c17
        li      t2, 0xff
        bne     t1, t2, fail

        # Monotonicity, asked as a question rather than assumed: no bit the
        # result holds is one the input did not.
        li      gp, 8
        li      t0, 0xfff
        candperm c18, c16, t0
        cgetperm t1, c18
        cgetperm t2, c16
        not     t2, t2
        and     t1, t1, t2
        bnez    t1, fail

        # The reset roots hold neither sealing authority, so `cseal` is
        # exercised here in its refusal: no admitted permission set holds both
        # seal and unseal, and neither root holds either (R-15-007o). A success
        # case waits on the composed initial distribution of §3.
        li      gp, 9
        cseal   c19, c10, c8
        cgettag t0, c19
        bnez    t0, fail

        # `csealentry` mints the forward edge, which is a call target. The
        # backward edge is minted only by a call, so it is never software's to
        # forge (R-15-071).
        li      gp, 10
        cspecialrw c20, pcc, cnull
        csealentry c21, c20
        cgetsealed t0, c21
        li      t1, 1
        bne     t0, t1, fail
        cgettype t0, c21
        li      t1, -2
        bne     t0, t1, fail

        # A derivation on a sealed capability clears the tag, which is what
        # keeps a sentry from being edited into a different entry point.
        li      gp, 11
        cincoffsetimm c22, c21, 8
        cgettag t0, c22
        bnez    t0, fail
        li      t0, 0x3
        candperm c22, c21, t0
        cgettag t0, c22
        bnez    t0, fail

        # `cfromptr` at zero is the null capability rather than an offset of
        # zero, which is the one discontinuity in the derivation surface.
        li      gp, 12
        cfromptr c23, c8, zero
        cgettag t0, c23
        bnez    t0, fail
        cgetperm t0, c23
        bnez    t0, fail
        li      t0, 0x20
        cfromptr c24, c10, t0
        cgettag t0, c24
        li      t1, 1
        bne     t0, t1, fail
        cgetaddr t0, c24
        li      t1, 0x20
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
