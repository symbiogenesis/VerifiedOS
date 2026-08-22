# SPDX-License-Identifier: Apache-2.0
# The capability semantics of the vector memory surface, from the only side a
# program reaches them from: a vector memory operation is scalar-issued, so it
# names a base register and that register holds the authority every one of its
# elements is checked against (R-08-003, R-15-115).
#
# Three things this member is about, and each of them is a claim about
# *elements* rather than about the access:
#
#   - the check lands per element, at the element's own address, so the same
#     instruction through the same base faults or does not according to how far
#     its elements reach and where its indices point;
#   - a vector store clears the validity tag of every granule it overwrites,
#     tag clearing being a property of the write path (R-15-115a, R-15-007r);
#   - only an **active** element raises, and a masked-off element writes
#     nothing, presents no address, and leaves the granule it would have
#     covered standing bit for bit (R-15-115b, R-15-085).
#
# **Every element count here is two and every extent is fixed**, which is what
# lets this program run unchanged on the C-class emulator at VLEN=256 and on the
# V-class one at VLEN=4096 and emit the same trace on both: `vl` is set from a
# register rather than from VLMAX, and no form whose extent is a register's
# worth appears. The geometry-dependent forms are `vector-geometry`'s.
#
# The trap contract is `cap-trap`'s: the expected cause is left in `t5` and the
# expected `mtval` in `t6`, so the handler is one comparison, and the `mtval`
# payload of a capability violation is the register that raised it above the
# five-bit violation code (core/cap_causes.sail).

        # vtype: vma=0, vta=0, vsew=e64, vlmul=m1. It is written out as the
        # field image the model's own bitfield decodes rather than as `e64,m1`,
        # so a reader can hold it against `Vtype` (extensions/V/vext_regs.sail).
        .equ    VTYPE_E64_M1, (0 << 7) | (0 << 6) | (3 << 3) | 0

        .text
        .globl _start
_start:
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        # The extension-context gate. `mstatus.VS` is what a partition setup
        # turns on for a partition that may use the unit, and with it off no
        # vector instruction decodes at all (R-07-012, R-15-049).
        li      t0, 0x200
        csrrs   zero, mstatus, t0

        # Two 64-bit elements, from a register rather than from VLMAX.
        li      gp, 1
        li      t0, 2
        vsetvli t1, t0, VTYPE_E64_M1
        li      t2, 2
        bne     t1, t2, fail
        csrr    t1, vl
        bne     t1, t2, fail
        csrr    t1, vtype
        li      t2, VTYPE_E64_M1
        bne     t1, t2, fail

        li      t0, scratch
        csetaddr c10, c8, t0
        csetboundsimm c10, c10, 64
        li      t0, buffer
        csetaddr c11, c8, t0
        csetboundsimm c11, c11, 64

        # A unit-stride store puts one value at each element's own address.
        li      gp, 2
        vmv.v.i v8, 7
        vse64.v v8, (c10)
        ld      t0, 0(c10)
        li      t1, 7
        bne     t0, t1, fail
        ld      t0, 8(c10)
        bne     t0, t1, fail

        # And a unit-stride load reads each of them back. The round trip goes
        # out through a second buffer because element one is not reachable with
        # the scalar move, which reads element zero alone.
        li      gp, 3
        li      t0, 0x0011223344556677
        sd      t0, 0(c10)
        li      t1, 0x778899aabbccddee
        sd      t1, 8(c10)
        vle64.v v9, (c10)
        vmv.x.s t2, v9
        bne     t2, t0, fail
        vse64.v v9, (c11)
        ld      t2, 0(c11)
        bne     t2, t0, fail
        ld      t2, 8(c11)
        bne     t2, t1, fail

        # The check is per element. This authority reaches one element and the
        # operation has two, so it is the *second* element that is outside it,
        # and the violation names the base register the access took its
        # authority from rather than the vector destination (R-15-073a).
        li      gp, 4
        li      t0, scratch
        csetaddr c12, c8, t0
        csetboundsimm c12, c12, 8
        li      t5, 28
        li      t6, 385
        vle64.v v9, (c12)

        # Masking that element off retires the operation. The check it owes is
        # still performed and its failure is discarded, which is what keeps the
        # mask out of the trap and out of the memory traffic alike (R-15-115b).
        # The active element still loads, so the operation is not a no-op.
        li      gp, 5
        vmv.v.i v0, 0
        li      t0, 1
        vmv.s.x v0, t0
        vle64.v v9, (c12), v0.t
        vmv.x.s t2, v9
        li      t0, 0x0011223344556677
        bne     t2, t0, fail

        # The mask decides which element raises and nothing else: turning the
        # second element back on brings the same violation back at the same
        # address.
        li      gp, 6
        li      t0, 3
        vmv.s.x v0, t0
        li      t5, 28
        li      t6, 385
        vle64.v v9, (c12), v0.t

        # A vector store clears the tag of the granule its element overwrites,
        # and the masked-off element's granule keeps both its tag and its bits.
        # The two granules are the two halves of one operation, so this is one
        # store rather than two runs.
        li      gp, 7
        sc      c8, 0(c10)
        sc      c8, 8(c10)
        cloadtags t0, (c10)
        andi    t0, t0, 3
        li      t1, 3
        bne     t0, t1, fail

        li      gp, 8
        vmv.v.i v0, 0
        li      t0, 1
        vmv.s.x v0, t0
        vmv.v.i v8, 9
        vse64.v v8, (c10), v0.t
        cloadtags t0, (c10)
        andi    t0, t0, 3
        li      t1, 2
        bne     t0, t1, fail

        li      gp, 9
        ld      t0, 0(c10)
        li      t1, 9
        bne     t0, t1, fail
        lc      c13, 0(c10)
        cgettag t0, c13
        bnez    t0, fail

        li      gp, 10
        lc      c14, 8(c10)
        cgettag t0, c14
        beqz    t0, fail
        cgetaddr t0, c14
        cgetaddr t1, c8
        bne     t0, t1, fail

        # The store side raises where the load side does, and stays silent
        # where the load side stays silent: a masked-off store element that
        # reached memory would write it.
        li      gp, 11
        vmv.v.i v0, 0
        li      t0, 1
        vmv.s.x v0, t0
        vse64.v v8, (c12), v0.t
        li      t0, 3
        vmv.s.x v0, t0
        li      t5, 28
        li      t6, 385
        vse64.v v8, (c12), v0.t

        # The indexed form. Each element's address is a runtime index out of a
        # vector register, so no check over the base can stand in for the
        # per-element one, which is R-15-085a's whole reason for putting this
        # form off the data-independent-timing list and admitting it anyway.
        li      gp, 12
        li      t0, indices
        csetaddr c15, c8, t0
        csetboundsimm c15, c15, 16
        vle64.v v4, (c15)
        li      t0, scratch
        csetaddr c16, c8, t0
        csetboundsimm c16, c16, 16
        li      t0, 0x1234567812345678
        sd      t0, 0(c16)
        li      t5, 28
        li      t6, 513
        vluxei64.v v9, (c16), v4

        li      gp, 13
        vmv.v.i v0, 0
        li      t0, 1
        vmv.s.x v0, t0
        vluxei64.v v9, (c16), v4, v0.t
        vmv.x.s t2, v9
        li      t0, 0x1234567812345678
        bne     t2, t0, fail

        # The ordered form answers the same, the two orderings differing in
        # nothing this model can observe.
        li      gp, 14
        vloxei64.v v9, (c16), v4, v0.t
        vmv.x.s t2, v9
        bne     t2, t0, fail

        # A runtime stride, which is off the same list for the same reason.
        li      gp, 15
        li      t0, 0x00feedfacecafe00
        sd      t0, 0(c10)
        li      t1, 0x00badc0ffee0dd00
        sd      t1, 16(c10)
        li      t2, 16
        vlse64.v v9, (c10), t2
        vmv.x.s t3, v9
        bne     t3, t0, fail
        vsse64.v v9, (c11), t2
        ld      t3, 0(c11)
        bne     t3, t0, fail
        ld      t3, 16(c11)
        bne     t3, t1, fail

        # The mask load and store, whose element is one bit and whose access is
        # `ceil(vl/8)` bytes: their inactive elements are past `evl` and are
        # tail rather than masked-off, so they owe no discarded check.
        li      gp, 16
        li      t0, 0x03
        sb      t0, 0(c10)
        vlm.v   v10, (c10)
        vsm.v   v10, (c11)
        lbu     t1, 0(c11)
        bne     t1, t0, fail

        li      gp, 0
        j       pass

# The handler is `cap-trap`'s: it runs under MTCC's authority, holds the cause
# and the trap value against what the check in flight declared, and resumes past
# the faulting instruction.
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

        # `scratch` is block-aligned because `cloadtags` reports one CBO block
        # and takes its base from the authority rather than from an operand.
        .align  6
scratch:
        .space  64
        .align  6
buffer:
        .space  64
        .align  3
indices:
        .dword  0
        .dword  32
