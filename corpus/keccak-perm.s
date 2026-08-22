# SPDX-License-Identifier: Apache-2.0
# The frozen Keccak unit, run as an instruction stream against the FIPS 202 and
# NIST ACVP known answers (R-15-056, R-15-056a, R-15-057a, R-15-058).
#
# The model's own `$[test]` harness asserts the permutation against the same
# vectors and asserts it about a *function*
# (model/model/unit_tests/test_keccak.sail). What is here is the other half: the
# permutation reached the way software reaches it, through a decoded instruction
# over a vector register group loaded and stored through a capability, on the
# C class's own VLEN of 256 where the 2048-bit element group is LMUL=8 and one
# permutation names eight of the thirty-two vector registers (R-15-059a).
#
# **The RVV instructions here are written as words rather than as mnemonics, and
# that is deliberate.** `vsetvli` and the unit-stride vector load and store are
# the V-class datapath's surface, which M0.8b lands; the dialect table carries
# `vkeccak.vi` because that row is this item's, and the three words below are
# spelled out with their fields the way [platform-coreclass.s](platform-coreclass.s)
# spells the `mhartid` write, so this member claims no lane it is not.
#
#   0x01BE72D7  vsetvli t0, t3, e64, m8      zimm 0x1B: vlmul 011, vsew 011
#   0x0205F007  vle64.v v0, (c10)            nf 1, vm 1, unit stride, width 111
#   0x0205F027  vse64.v v0, (c10)            the same at STORE-FP
#
# The handler is installed by writing MTCC, which is reachable because the reset
# PCC carries access-system-registers, and each faulting check leaves the cause
# it expects in `t5` and the trap value in `t6`, exactly as
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

        # Reaching the vector unit at all needs the extension-context gate on,
        # `mstatus.VS` being what a partition setup turns on for a partition
        # that may use it (R-07-012, R-15-049).
        li      t0, 0x200
        csrrs   zero, mstatus, t0

        # The one configuration the instruction decodes at: SEW=64 and the LMUL
        # that makes the 2048-bit element group one register group. At this
        # class's VLEN=256 that is LMUL=8 and `vl` is the group's 32 elements,
        # which is VLMAX exactly, so there is no tail and no mask.
        li      gp, 1
        li      t3, 32
        .word   0x01BE72D7
        csrr    t1, vl
        bne     t1, t3, fail
        csrr    t1, vlenb
        li      t2, 32
        bne     t1, t2, fail

        li      t0, scratch
        csetaddr c10, c8, t0

        # Keccak-f[1600] over the all-zero state, which is what reset leaves in
        # the vector register file (core/regs.sail), against the published
        # vector for the permutation.
        li      gp, 2
        vkeccak.vi v0, v0, 24
        .word   0x0205F027
        ld      t1, 0(c10)
        li      t2, 0xF1258F7940E1DDE7
        bne     t1, t2, fail
        ld      t1, 96(c10)
        li      t2, 0x81A57C16DBCF555F
        bne     t1, t2, fail
        ld      t1, 192(c10)
        li      t2, 0xEAF1FF7B5CECA249
        bne     t1, t2, fail

        # The same permutation over the state it just wrote, which is the second
        # half of the published pair and the first non-zero input here. Doing it
        # in place is also what shows the destination is read back as the source:
        # a clause writing the result somewhere else would pass the check above
        # and fail this one.
        li      gp, 3
        vkeccak.vi v0, v0, 24
        .word   0x0205F027
        ld      t1, 0(c10)
        li      t2, 0x2D5C954DF96ECB3C
        bne     t1, t2, fail
        ld      t1, 192(c10)
        li      t2, 0x20D06CD26A8FBF5C
        bne     t1, t2, fail

        # The short round count, which is TurboSHAKE's and KangarooTwelve's
        # (R-15-056a), from a cleared file and into a **separate** group. The
        # switch's own eager zeroize is what clears the file, so this check also
        # runs the two instructions against each other; `vmclear` leaves `vtype`
        # holding no configuration, which is why the configuration is set again
        # rather than assumed to have survived (R-15-069d).
        li      gp, 4
        vmclear
        .word   0x01BE72D7
        vkeccak.vi v8, v0, 12
        .word   0x0205F427
        ld      t1, 0(c10)
        li      t2, 0x8E5E5438B9A78617
        bne     t1, t2, fail
        ld      t1, 192(c10)
        li      t2, 0xCFFD0D76222CA01C
        bne     t1, t2, fail
        # And the source group survived: a permutation into another group leaves
        # the group it read alone.
        .word   0x0205F027
        ld      t1, 0(c10)
        bnez    t1, fail
        ld      t1, 192(c10)
        bnez    t1, fail

        # One NIST ACVP message end to end. The SHA-3-256 rate is 136 bytes, so
        # the padded block for the empty message is the domain-separation byte
        # 0x06 at byte 0 and the 0x80 at byte 135, which is lane 0 and lane 16 in
        # the standard's lane order; the first four lanes of the result read
        # little-endian are the published digest
        # a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a. This
        # is the check that fixes the **lane order**, which no permutation of an
        # all-zero state can.
        li      gp, 5
        li      t0, block
        csetaddr c11, c8, t0
        .word   0x0205F807
        vkeccak.vi v16, v16, 24
        .word   0x0205F827
        ld      t1, 0(c10)
        li      t2, 0x66D71EBFF8C6FFA7
        bne     t1, t2, fail
        ld      t1, 8(c10)
        li      t2, 0x62D661A05647C151
        bne     t1, t2, fail
        ld      t1, 16(c10)
        li      t2, 0xFA493BE44DFF80F5
        bne     t1, t2, fail
        ld      t1, 24(c10)
        li      t2, 0x4A43F8804B0AD882
        bne     t1, t2, fail

        # The round count is selected by an immediate with the unassigned values
        # **illegal** rather than rounded to an admitted one (R-15-057a), so a
        # third value reaches no decode clause and traps exactly as any
        # unallocated encoding does (R-15-014). This is `vkeccak.vi v0, v0, 23`,
        # assembled by hand because the dialect table refuses to emit it.
        li      gp, 6
        li      t5, 2
        li      t6, 0x0170200B
        .word   0x0170200B

        # The capability checks reach this unit as they reach every other: the
        # element group is loaded through an explicit capability operand of the
        # issuing context and an authority that does not cover the access faults
        # where the access is (R-08-003, R-15-118). Sixty-four bytes of authority
        # against a 256-byte element group is a length violation on register 12.
        li      gp, 7
        li      t0, block
        csetaddr c12, c8, t0
        csetboundsimm c12, c12, 64
        li      t5, 28
        li      t6, 0x181
        .word   0x02067007

        # And the gate is the context as well as the class, which is where this
        # instruction parts company with `vmclear`: that one is the switcher's
        # and must not be trappable by the partition it exists to erase, and this
        # one is the partition's own and reads and writes the architectural
        # vector register file (extensions/keccak/keccak_insts.sail).
        li      gp, 8
        li      t0, 0x600
        csrrc   zero, mstatus, t0
        li      t5, 2
        li      t6, 0x0180200B
        .word   0x0180200B
        li      t0, 0x200
        csrrs   zero, mstatus, t0

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
# The SHA-3-256 padded block for the empty message, as the 32 elements of one
# 2048-bit element group: lane 0 and lane 16 carry the padding and everything
# else is zero, the seven elements above the 1600-bit state included.
block:
        .dword  0x0000000000000006
        .space  120
        .dword  0x8000000000000000
        .space  120
scratch:
        .space  256
