# SPDX-License-Identifier: Apache-2.0
# Generated client program: tools/bedrock2-lowering/hello.py.
# Inputs: HelloWorld.v (Rupicola derivation), hello_harness.c.
# No compiler source, runtime or library code is included.
# The M1.2f driver's harness around an emitted stream. Every authority is derived off the
# store-side root (R-15-001c). c4 is reserved by the selected scalar ABI; c8, like every
# allocatable register, can be overwritten by main. Clearing expanded permission bit 0
# removes globality while retaining root_data_cap's store-local stack shape.
        .text
        .globl _start
_start:
        cmove   c4, c1
        la      c9, __vos_handler
        cspecialrw cnull, mtcc, c9
        li      t0, __vos_stack
        csetaddr csp, c4, t0
        li      t1, 16384
__vos_stack_bounds:
        csetbounds csp, csp, t1
        li      t1, 0xFFE
        candperm csp, csp, t1
        li      t0, __vos_stack_top
        csetaddr csp, csp, t0
        li      t0, hello_values
        csetaddr c10, c4, t0
        csetboundsimm c10, c10, 112
        li      t0, hello_slots
        csetaddr c11, c4, t0
        csetboundsimm c11, c11, 112
        call    main
        li      gp, 1
        bnez    a0, __vos_fail
        li      t0, hello_values
        csetaddr c12, c4, t0
        li      t0, tohost
        csetaddr c31, c4, t0
        li      gp, 2
        ld      t2, 0(c12)
        li      t1, 72
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 3
        ld      t2, 8(c12)
        li      t1, 101
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 4
        ld      t2, 16(c12)
        li      t1, 108
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 5
        ld      t2, 24(c12)
        li      t1, 108
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 6
        ld      t2, 32(c12)
        li      t1, 111
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 7
        ld      t2, 40(c12)
        li      t1, 44
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 8
        ld      t2, 48(c12)
        li      t1, 32
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 9
        ld      t2, 56(c12)
        li      t1, 119
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 10
        ld      t2, 64(c12)
        li      t1, 111
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 11
        ld      t2, 72(c12)
        li      t1, 114
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 12
        ld      t2, 80(c12)
        li      t1, 108
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 13
        ld      t2, 88(c12)
        li      t1, 100
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 14
        ld      t2, 96(c12)
        li      t1, 33
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 15
        ld      t2, 104(c12)
        li      t1, 10
        bne     t2, t1, __vos_fail
        li      t1, 0x101000000000000
        or      t0, t1, t2
        sd      t0, 0(c31)
        li      gp, 0
        li      a0, 0
        beqz    a0, __vos_pass
        andi    gp, a0, 0xFF
        bnez    gp, __vos_fail
        li      gp, 0xFF
__vos_fail:
        slli    t0, gp, 1
        ori     t0, t0, 1
        j       __vos_exit
__vos_pass:
        li      t0, 1
__vos_exit:
        li      t1, tohost
        csetaddr c31, c4, t1
        sd      t0, 0(c31)
__vos_halt:
        j       __vos_halt
__vos_handler:
        csrr    t0, mcause
        andi    t0, t0, 0xFF
        ori     gp, t0, 0x100
        j       __vos_fail
# --- the emitted stream follows ---
# source-profile: verifiedos-scalar-source-v1; no pointer round-trip integer types

.text
.globl hello_char
hello_char:
 cmove c30, c2
 cincoffsetimm c2, c2, -16
 sc c30, 0(c2)
 sc c1, 8(c2)
 mv x11, x10
 sltiu x15, x11, 1
 mv x13, x15
 bne x13, x0, .L100
 mv x13, x10
 addi x31, x0, 1
 xor x11, x13, x31
 sltiu x11, x11, 1
 mv x14, x11
 bne x14, x0, .L101
 mv x15, x10
 addi x31, x0, 2
 xor x12, x15, x31
 sltiu x12, x12, 1
 mv x11, x12
 bne x11, x0, .L102
 mv x11, x10
 addi x31, x0, 3
 xor x11, x11, x31
 sltiu x11, x11, 1
 mv x13, x11
 bne x13, x0, .L103
 mv x12, x10
 addi x31, x0, 4
 xor x13, x12, x31
 sltiu x13, x13, 1
 mv x14, x13
 bne x14, x0, .L104
 mv x12, x10
 addi x31, x0, 5
 xor x14, x12, x31
 sltiu x14, x14, 1
 mv x13, x14
 bne x13, x0, .L105
 mv x11, x10
 addi x31, x0, 6
 xor x11, x11, x31
 sltiu x11, x11, 1
 mv x12, x11
 bne x12, x0, .L106
 mv x15, x10
 addi x31, x0, 7
 xor x15, x15, x31
 sltiu x15, x15, 1
 mv x15, x15
 bne x15, x0, .L107
 mv x11, x10
 addi x31, x0, 8
 xor x11, x11, x31
 sltiu x11, x11, 1
 mv x14, x11
 bne x14, x0, .L108
 mv x12, x10
 addi x31, x0, 9
 xor x12, x12, x31
 sltiu x12, x12, 1
 mv x14, x12
 bne x14, x0, .L109
 mv x12, x10
 addi x31, x0, 10
 xor x11, x12, x31
 sltiu x11, x11, 1
 mv x11, x11
 bne x11, x0, .L110
 mv x11, x10
 addi x31, x0, 11
 xor x11, x11, x31
 sltiu x11, x11, 1
 mv x13, x11
 bne x13, x0, .L111
 mv x11, x10
 addi x31, x0, 12
 xor x14, x11, x31
 sltiu x14, x14, 1
 mv x15, x14
 bne x15, x0, .L112
 mv x6, x10
 addi x31, x0, 13
 xor x13, x6, x31
 sltiu x13, x13, 1
 mv x6, x13
 bne x6, x0, .L113
 addi x6, x0, 0
 j .L114
.L113:
 addi x6, x0, 10
 j .L114
.L112:
 addi x6, x0, 33
 j .L114
.L111:
 addi x6, x0, 100
 j .L114
.L110:
 addi x6, x0, 108
 j .L114
.L109:
 addi x6, x0, 114
 j .L114
.L108:
 addi x6, x0, 111
 j .L114
.L107:
 addi x6, x0, 119
 j .L114
.L106:
 addi x6, x0, 32
 j .L114
.L105:
 addi x6, x0, 44
 j .L114
.L104:
 addi x6, x0, 111
 j .L114
.L103:
 addi x6, x0, 108
 j .L114
.L102:
 addi x6, x0, 108
 j .L114
.L101:
 addi x6, x0, 101
 j .L114
.L100:
 addi x6, x0, 72
.L114:
 mv x10, x6
 lc c1, 8(c2)
 lc c2, 0(c2)
 cjalr cnull, cra, 0

.text
.globl main
main:
 cmove c30, c2
 cincoffsetimm c2, c2, -48
 sc c30, 0(c2)
 sc c1, 8(c2)
 sc c11, 32(c2)
 sc c10, 24(c2)
 addi x11, x0, 0
 sd x11, 16(c2)
.L115:
 ld x10, 16(c2)
 mv x12, x10
 addi x31, x0, 14
 bge x12, x31, .L116
 mv x10, x10
 cjal cra, hello_char
 lc c11, 24(c2)
 cmove c14, c11
 ld x11, 16(c2)
 mv x11, x11
 slli x12, x11, 3
 cincoffset c13, c14, x12
 mv x10, x10
 sd x10, 0(c13)
 lc c11, 32(c2)
 cmove c10, c11
 ld x15, 16(c2)
 mv x12, x15
 slli x15, x12, 3
 cincoffset c14, c10, x15
 lc c10, 24(c2)
 cmove c12, c10
 ld x15, 16(c2)
 mv x10, x15
 slli x11, x10, 3
 cincoffset c13, c12, x11
 sc c13, 0(c14)
 ld x12, 16(c2)
 mv x13, x12
 addi x14, x13, 1
 sd x14, 16(c2)
 j .L115
.L116:
 addi x10, x0, 0
 sd x10, 16(c2)
.L117:
 ld x12, 16(c2)
 mv x11, x12
 addi x31, x0, 14
 bge x11, x31, .L118
 lc c13, 32(c2)
 cmove c10, c13
 ld x15, 16(c2)
 mv x11, x15
 slli x12, x11, 3
 cincoffset c15, c10, x12
 lc c14, 0(c15)
 sc c14, 24(c2)
 ld x10, 16(c2)
 mv x10, x10
 cjal cra, hello_char
 lc c14, 24(c2)
 cmove c11, c14
 ld x15, 0(c11)
 mv x14, x10
 beq x15, x14, .L119
 addiw x10, x0, 1
 j .L120
.L119:
 lc c12, 24(c2)
 cmove c13, c12
 cmove c14, c12
 ld x14, 0(c14)
 sd x14, 0(c13)
 ld x13, 16(c2)
 mv x15, x13
 addi x13, x15, 1
 sd x13, 16(c2)
 j .L117
.L118:
 addiw x10, x0, 0
.L120:
 lc c1, 8(c2)
 lc c2, 0(c2)
 cjalr cnull, cra, 0
# --- the emitted stream ends ---
        .data
        .align  3
tohost:
        .dword  0
        .align  8
__vos_stack:
        .space  16384
__vos_stack_top:
        .align 3
hello_values:
        .space 112
hello_slots:
        .space 112
