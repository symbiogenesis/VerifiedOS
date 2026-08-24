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

        # The one `vtype` this member configures, written as its fields the way
        # [vector-geometry.s](vector-geometry.s) writes its own: `vma`, `vta`,
        # `vsew` and `vlmul`, with SEW=64 and the LMUL that makes one access a
        # group of eight registers, so four accesses are the whole file.
        .equ    VTYPE_E64_M8, (0 << 7) | (0 << 6) | (3 << 3) | 3

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
        #
        # **Every target is dirtied by the surface that owns it before the
        # clear runs**, because a state held against its reset value is a weaker
        # reading of the same clause: reset and the clear agree there by
        # construction, so a clause that cleared nothing would pass. `vcsr` is
        # dirtied by a CSR write, `vl` and `vtype` by the configuration
        # instruction that is their only writer, and the register file by a
        # vector load, which is the surface M0.8b supplies. Reaching any of them
        # needs the extension-context gate on, which is the next check's whole
        # point.
        #
        # **Every extent below is derived from `vlenb`**, the class table's
        # vector length in bytes and the only figure from that table the
        # instruction set carries (R-15-113), so nothing here is written against
        # the class this emulator composes. At SEW=64 and LMUL=8 one access
        # covers a group of eight registers, and `vl` times eight held against a
        # group's bytes is what says it covers the whole group rather than a
        # prefix of it.
        li      gp, 8
        li      t0, 0x200
        csrrs   zero, mstatus, t0
        li      t0, 7
        csrrw   zero, vcsr, t0
        csrr    t2, vcsr
        li      t3, 7
        bne     t2, t3, fail
        csrr    s2, vlenb
        vsetvli s3, zero, VTYPE_E64_M8
        slli    t1, s3, 3
        slli    t2, s2, 3
        bne     t1, t2, fail

        # A whole register file's worth of image, with the authority bounded to
        # exactly that, so an access that ran past the file faults rather than
        # reaching the datum beyond it.
        li      t0, vregs
        csetaddr c20, c8, t0
        slli    t3, s2, 5
        csetbounds c20, c20, t3

        # The pattern reaches the file through memory rather than through a
        # broadcast: one broadcast fills a group, four stores put that group
        # under all four quarters of the image, and four loads bring it back
        # into every one of the thirty-two registers. The image keeps the
        # pattern afterwards, which is what check 11 reads the cleared file back
        # over.
        li      t0, 0x5a5a5a5a5a5a5a5a
        vmv.v.x v0, t0
        cmove   c21, c20
        vse64.v v0, (c21)
        cincoffset c21, c21, t2
        vse64.v v0, (c21)
        cincoffset c21, c21, t2
        vse64.v v0, (c21)
        cincoffset c21, c21, t2
        vse64.v v0, (c21)
        cmove   c21, c20
        vle64.v v0, (c21)
        cincoffset c21, c21, t2
        vle64.v v8, (c21)
        cincoffset c21, c21, t2
        vle64.v v16, (c21)
        cincoffset c21, c21, t2
        vle64.v v24, (c21)

        # `vmv.x.s` reads element zero of the register it names whatever `vl`
        # and `vtype` say, so the last register of the last group is read back
        # directly: nothing but the fourth load reaches v31. `vl` is a count and
        # `vtype` a configuration rather than the `vill` the clear leaves.
        vmv.x.s t1, v31
        bne     t1, t0, fail
        csrr    t2, vl
        beqz    t2, fail
        csrr    t2, vtype
        bltz    t2, fail

        # **The clear does not ask the outgoing partition's permission.**
        # `mstatus.VS` gates every ordinary use of the vector unit, and the
        # partition being switched away from can write it; if `vmclear` were
        # gated on it too, that partition could dirty the unit, turn the gate
        # off, and leave the switch's zeroize trapping on the residue it exists
        # to erase (R-07-014a, R-15-214). So the gate is the class and not the
        # context: the unit is unreachable here and the clear still runs.
        #
        # The CSR half is read back here and in the check below, ahead of the
        # register file's, because reading the file back needs a configuration
        # and the instruction that selects one is `vl`'s and `vtype`'s only
        # writer: taken later, these two assertions would be about that
        # instruction rather than about the clear.
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

        # The register file is the largest member of the inventory and the one a
        # program reads back only through memory. It is stored out under a
        # configuration selected here rather than one that survived the clear,
        # four group accesses covering all thirty-two registers, and over the
        # image that still holds check 8's pattern: a register the clear missed
        # and a store that never happened both read back as the pattern rather
        # than as zero. The scan is every doubleword of the file and not a
        # sample of it, its trip count derived from `vlenb` like every other
        # extent here.
        li      gp, 11
        vsetvli s3, zero, VTYPE_E64_M8
        slli    t2, s2, 3
        cmove   c21, c20
        vse64.v v0, (c21)
        cincoffset c21, c21, t2
        vse64.v v8, (c21)
        cincoffset c21, c21, t2
        vse64.v v16, (c21)
        cincoffset c21, c21, t2
        vse64.v v24, (c21)
        cmove   c21, c20
        slli    t3, s2, 2
scan:
        ld      t1, 0(c21)
        bnez    t1, fail
        cincoffsetimm c21, c21, 8
        addi    t3, t3, -1
        bnez    t3, scan

        # It disturbs nothing outside its own inventory: no integer register, no
        # capability register, and no memory. The switch that issues it has
        # already saved what it means to keep, and what this clears is exactly
        # what it does not save (R-07-014a). The datum below and the tag beside
        # it are the ones checks 1 to 3 left, and no vector access above reaches
        # them, the file's image being a region of its own.
        li      gp, 12
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

        # The vector register file's image. A register at the widest class the
        # table declares is 512 bytes, so a whole file is 16 KiB and the
        # reservation is that; what the program covers is the class it runs on,
        # every extent of it derived from `vlenb`.
        .align  6
vregs:
        .space  16384
