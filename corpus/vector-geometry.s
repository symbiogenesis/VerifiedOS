# SPDX-License-Identifier: Apache-2.0
# The one thing a program can see of the V class that it cannot see of the C
# class: the geometry. `vlenb` is the class table's vector length in bytes and
# the only figure from that table the instruction set carries (R-15-113,
# core/core_class.sail), and the forms whose extent is a *register's worth*
# are the ones that read it.
#
# **The program is written against `vlenb` and never against a number**, so it
# runs unchanged on the C-class emulator at VLEN=256 and on the V-class one at
# VLEN=4096, and every extent it derives moves with the geometry it was derived
# from. What it asserts is the relation rather than the value: VLMAX at SEW=64
# is `vlenb/8`, a whole-register transfer moves exactly `vlenb` bytes and not one
# more, and an authority shorter than a register's worth faults on the element
# that reaches past it (R-08-003, R-15-115).
#
# The trap contract is `cap-trap`'s: the expected cause in `t5`, the expected
# `mtval` in `t6`.

        .equ    VTYPE_E64_M1, (0 << 7) | (0 << 6) | (3 << 3) | 0

        .text
        .globl _start
_start:
        cmove   c8, c1
        la      c9, handler
        cspecialrw cnull, mtcc, c9

        li      t0, 0x200
        csrrs   zero, mstatus, t0

        # `vlenb` is a byte count, at least sixteen because the profile's
        # narrowest class is VLEN=256 and `Zvl128b` is what `V` itself requires,
        # and a power of two because a vector length is (R-15-113).
        li      gp, 1
        csrr    s2, vlenb
        li      t0, 16
        blt     s2, t0, fail
        addi    t0, s2, -1
        and     t0, t0, s2
        bnez    t0, fail

        # VLMAX at SEW=64 and LMUL=1 is a register's worth of elements, which is
        # the geometry read back through `vl` rather than through `vlenb`. `rs1`
        # is the zero register with a non-zero destination, which is how the
        # configuration instruction asks for VLMAX rather than for a count.
        li      gp, 2
        vsetvli s3, zero, VTYPE_E64_M1
        slli    t0, s3, 3
        bne     t0, s2, fail

        # Two buffers, each a register's worth with one element to spare, so a
        # transfer that ran long would be visible rather than refused.
        li      gp, 3
        li      t0, source
        csetaddr c10, c8, t0
        addi    t1, s2, 8
        csetbounds c10, c10, t1
        cgetlen t2, c10
        blt     t2, t1, fail
        li      t0, target
        csetaddr c11, c8, t0
        csetbounds c11, c11, t1
        cgetlen t2, c11
        blt     t2, t1, fail

        # A unit-stride store at VLMAX covers exactly a register's worth: the
        # first element and the last are written and the element past the end is
        # not.
        li      gp, 4
        li      t0, 0x5a5a5a5a5a5a5a5a
        vmv.v.x v8, t0
        vse64.v v8, (c10)
        ld      t1, 0(c10)
        bne     t1, t0, fail
        addi    t2, s2, -8
        cincoffset c12, c10, t2
        ld      t1, 0(c12)
        bne     t1, t0, fail
        cincoffset c12, c10, s2
        ld      t1, 0(c12)
        bnez    t1, fail

        # The whole-register pair moves the register and not the operation: it
        # reads no `vtype` and no `vl`, so its extent is `vlenb` however the unit
        # is configured. Setting `vl` to one element first is what makes that
        # visible: the transfer below still moves all of them.
        li      gp, 5
        li      t0, 1
        vsetvli t1, t0, VTYPE_E64_M1
        vl1re64.v v9, (c10)
        vs1r.v  v9, (c11)
        ld      t1, 0(c11)
        li      t0, 0x5a5a5a5a5a5a5a5a
        bne     t1, t0, fail
        addi    t2, s2, -8
        cincoffset c12, c11, t2
        ld      t1, 0(c12)
        bne     t1, t0, fail
        cincoffset c12, c11, s2
        ld      t1, 0(c12)
        bnez    t1, fail

        # And it is checked per element like every other vector access: an
        # authority half a register wide faults on the element that reaches past
        # it. The length is derived rather than written down, and held against
        # the register's own width first, because the capability format rounds a
        # requested bound above its byte-exact threshold (R-15-007c).
        li      gp, 6
        li      t0, source
        csetaddr c13, c8, t0
        srli    t1, s2, 1
        csetbounds c13, c13, t1
        cgetlen t2, c13
        bge     t2, s2, fail
        li      t5, 28
        li      t6, 417
        vl1re64.v v9, (c13)

        li      gp, 7
        li      t5, 28
        li      t6, 417
        vs1r.v  v9, (c13)

        li      gp, 0
        j       pass

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

        # A register's worth at the widest class the table declares is 512
        # bytes, and each buffer carries one element beyond it so that a
        # transfer running long has somewhere to be seen.
        .align  6
source:
        .space  520
        .align  6
target:
        .space  520
