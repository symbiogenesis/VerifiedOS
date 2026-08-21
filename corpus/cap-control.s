# Domain entry, which on this machine is a property of the jump rather than of
# a call gate: `cjalr` unseals a forward-edge sentry into PCC and writes the
# return address already sealed as a backward-edge sentry, so the sentry pair is
# the platform's coarse-grained CFI and there is nothing else to invoke
# (R-15-068, R-15-069, R-15-071).
#
# The refusals belong to `cap-trap`: what is checked here is that each edge is
# admitted in its own role and that entering one carries its bounds into PCC.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1

        # A direct call. The link it writes is the next instruction's PCC,
        # sealed as the backward edge, which is what keeps a return address out
        # of software's gift.
        li      gp, 1
        li      t3, 0
        call    .callee_a
.after_a:
        li      t1, 1
        bne     t3, t1, fail
        la      c10, .after_a
        cgetaddr t0, c10
        cgetaddr t1, cra
        bne     t0, t1, fail
        cgetsealed t0, cra
        li      t1, 1
        bne     t0, t1, fail
        cgettype t0, cra
        li      t1, -3
        bne     t0, t1, fail

        # An indirect call through a forward-edge sentry, which `csealentry`
        # mints and only a jump writing a link may enter.
        li      gp, 2
        la      c11, .callee_b
        csealentry c12, c11
        cgettype t0, c12
        li      t1, -2
        bne     t0, t1, fail
        li      t3, 0
        cjalr   cra, c12, 0
        li      t1, 2
        bne     t3, t1, fail

        # A jump that writes no link may enter either edge, which is what makes
        # a return a jump and not a second instruction.
        li      gp, 3
        la      c13, .target_c
        csealentry c14, c13
        la      c15, .back_c
        li      t3, 0
        cjr     c14
.back_c:
        li      t1, 3
        bne     t3, t1, fail

        # Entering a sentry installs *its* bounds as the executing PCC's, so a
        # bounded entry point is a bounded domain rather than a bounded pointer
        # to an unbounded one. The callee below is exactly two instructions, so
        # eight bytes is the whole of it.
        li      gp, 4
        la      c16, .callee_d
        csetboundsimm c16, c16, 8
        csealentry c17, c16
        cjalr   cra, c17, 0
        cgetlen t0, c18
        li      t1, 8
        bne     t0, t1, fail
        cgetsealed t0, c18
        bnez    t0, fail

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

# The callees. Each returns with `ret`, which is a jump writing no link: the
# one role a backward-edge sentry is reachable in.
.callee_a:
        li      t3, 1
        ret

.callee_b:
        li      t3, 2
        # The sentry is unsealed *into* PCC, so the executing capability is
        # ordinary code authority and not a sealed one.
        cspecialrw c19, pcc, cnull
        cgetsealed t0, c19
        bnez    t0, fail
        ret

.target_c:
        li      t3, 3
        cjr     c15

.callee_d:
        cspecialrw c18, pcc, cnull
        ret

        .data
        .align  3
tohost:
        .dword  0
