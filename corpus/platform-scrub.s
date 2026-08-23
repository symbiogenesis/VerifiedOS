# SPDX-License-Identifier: Apache-2.0
# The two block instructions the platform adds beside `fence.t`: the synchronous
# block verify-and-correct (R-15-177a) and the vector/matrix all-state clear
# (R-15-069d).
#
# They are here together because they are the same kind of row: net-new surface
# belonging to no standard extension and inherited from neither upstream model,
# each doing in one instruction what a machine with a walker or a software loop
# would do with an agent or a trip count. `cbo.scrub` is the scrubber R-15-177
# mandates, made an instruction so the scrubbing agent is the §11 schedule rather
# than an engine (R-15-010 test 5); `vmclear` is the partition switch's eager
# zeroize, made one instruction so the switch's cost is a constant rather than a
# per-class loop whose trip count the kernel proof would carry (R-15-069e,
# R-07-014c).
#
# **What the scrub is for is visible only against the write path.** Every
# ordinary store clears the validity tag of the granule it covers, tag clearing
# being a property of the write path and not an instruction (R-15-007r), so
# maintenance of a capability-bearing array through that path would destroy the
# authority in it. Checks 2 and 3 are that contrast: the same block, the same
# bits, and the tag survives one and not the other.
#
# The handler is installed by writing MTCC, which is reachable because the reset
# PCC carries access-system-registers, and each faulting check leaves the cause
# it expects in `t5` and the trap value in `t6`, exactly as [cap-trap.s](cap-trap.s)
# does.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        li      t0, block
        csetaddr c10, c8, t0
        li      t0, value
        csetaddr c11, c8, t0
        csetboundsimm c11, c11, 64

        # A block of capabilities and one doubleword of data beside them.
        li      gp, 1
        cbo.zero (c10)
        sc      c11, 0(c10)
        sc      c11, 8(c10)
        li      s6, 0x0123456789abcdef
        sd      s6, 16(c10)
        cloadtags t2, (c10)
        li      t3, 3
        bne     t2, t3, fail

        # The scrub reads every codeword in the block through the error-detecting
        # check and rewrites what it corrects, data plane and tag plane alike. On
        # a fault-free array there is nothing to correct, and the pass takes the
        # same cycles as one that corrected something: correction is invisible in
        # the result and in the timing both (R-15-179).
        #
        # The base register names an address anywhere in the block and the block
        # is the naturally aligned one containing it, as `cbo.zero` addresses it,
        # so the operand here is deliberately not aligned to the block.
        li      gp, 2
        cincoffsetimm c12, c10, 24
        cbo.scrub (c12)
        cloadtags t2, (c10)
        li      t3, 3
        bne     t2, t3, fail
        lc      c13, 0(c10)
        cgettag t2, c13
        li      t3, 1
        bne     t2, t3, fail
        cseqx   t2, c13, c11
        bne     t2, t3, fail
        ld      t2, 16(c10)
        bne     t2, s6, fail

        # The contrast. Putting a granule's own bits back through the store path
        # is a *data* write and clears its tag; that is the whole reason the
        # scrub is a block operation of its own and not a load-and-store loop.
        li      gp, 3
        ld      t4, 8(c10)
        sd      t4, 8(c10)
        cloadtags t2, (c10)
        li      t3, 1
        bne     t2, t3, fail
        ld      t2, 8(c10)
        bne     t2, t4, fail

        # Address progression stays in software: the instruction covers one block
        # and stops, so the block above this one is the scrub task's next
        # instruction and no walker crosses into it.
        li      gp, 4
        li      t0, block
        addi    t0, t0, 64
        csetaddr c14, c8, t0
        cbo.zero (c14)
        sc      c11, 0(c14)
        cbo.scrub (c10)
        cloadtags t2, (c14)
        li      t3, 1
        bne     t2, t3, fail

        # It reads the block *and* writes back what it corrects, so it needs both
        # permissions: a holder of a read-only view may not cause a write to
        # memory it cannot write, even one that puts back what it found. The
        # violation names the register that raised it (R-15-073a).
        li      gp, 5
        li      t0, 0x3
        candperm c15, c10, t0
        li      t5, 28
        li      t6, 499
        cbo.scrub (c15)

        # Read permission is owed first and separately, because the scrub reads
        # before it writes.
        li      gp, 6
        li      t0, 0x1
        candperm c16, c10, t0
        li      t5, 28
        li      t6, 530
        cbo.scrub (c16)

        # And only over an array that carries the code it verifies. A device
        # register has no codeword to scrub, so IO memory refuses it at the PMA
        # rather than at the instruction, which is where the distinction belongs.
        # The refusal is a store access fault, the scrub's rewrite being the half
        # it was denied.
        li      gp, 7
        li      t0, 0x2100000
        csetaddr c17, c8, t0
        li      t5, 7
        li      t6, 0x2100000
        cbo.scrub (c17)

        # `vmclear` clears the vector register file, the vector CSRs, the matrix
        # unit's architectural state, and the class's scratchpad in one
        # unconditional pass. All four are in the model: the scratchpad is the
        # extent this hart's class declares, and the matrix half is *nothing*,
        # an enumeration result rather than a residue, the unit holding no
        # architectural state of its own (vmclear.sail, R-15-117, R-15-118).
        # What this member checks is the CSR half: `vcsr` is writable, so it can
        # be dirtied and found clean afterwards, where the register file, `vl`
        # and `vtype` are asserted against their reset values rather than
        # against a configuration this program selected. The surface that would
        # dirty those three arrived with M0.8b and the rewrite over it is owed
        # (docs/differential-corpus.md §7). Reaching the CSR at all needs the
        # extension-context gate on, which is the next check's whole point.
        li      gp, 8
        li      t0, 0x200
        csrrs   zero, mstatus, t0
        li      t0, 7
        csrrw   zero, vcsr, t0
        csrr    t2, vcsr
        li      t3, 7
        bne     t2, t3, fail

        # **The clear does not ask the outgoing partition's permission.**
        # `mstatus.VS` gates every ordinary use of the vector unit, and the
        # partition being switched away from can write it; if `vmclear` were
        # gated on it too, that partition could dirty the unit, turn the gate
        # off, and leave the switch's zeroize trapping on the residue it exists
        # to erase (R-07-014a, R-15-214). So the gate is the class and not the
        # context: the unit is unreachable here and the clear still runs.
        li      gp, 9
        li      t0, 0x600
        csrrc   zero, mstatus, t0
        vmclear
        li      t0, 0x200
        csrrs   zero, mstatus, t0
        csrr    t2, vcsr
        bnez    t2, fail
        csrr    t2, vxsat
        bnez    t2, fail
        csrr    t2, vxrm
        bnez    t2, fail

        # `vtype` is cleared to *no configuration* rather than to zeroes, which
        # are different states: an all-zeroes `vtype` is a valid configuration,
        # SEW=8 at LMUL=1, that the successor partition never selected. `vill` is
        # what "no configuration" is spelled as, so that is what a cleared
        # `vtype` holds, and `vl` is zero beside it.
        li      gp, 10
        csrr    t2, vl
        bnez    t2, fail
        csrr    t2, vtype
        bgez    t2, fail

        # It disturbs nothing outside its own inventory: no integer register, no
        # capability register, and no memory. The switch that issues it has
        # already saved what it means to keep, and what this clears is exactly
        # what it does not save (R-07-014a).
        li      gp, 11
        cgettag t2, c11
        li      t3, 1
        bne     t2, t3, fail
        ld      t2, 16(c10)
        bne     t2, s6, fail

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
        .align  6
value:
        .space  64
block:
        .space  128
