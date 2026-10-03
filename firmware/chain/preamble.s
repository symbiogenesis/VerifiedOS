# SPDX-License-Identifier: Apache-2.0
# The runtime-only run's harness preamble (docs/implementation/contracts/
# boot-handoff.md section 9.2): the ROM's two device acts, the entropy root's
# start-up tests and counter 0's advance to the floor F, so the runtime meets
# the devices a boot run's runtime meets; then the runtime's entry with the
# authority the ROM hands it, PCC the reset execute root and c1 the
# store-side root, and no other register. Harness code, not firmware: it
# verifies nothing and measures nothing. The composer
# (tools/vos/chain_rot.py) supplies every upper-case name as an `.equ`,
# PREAMBLE_FLOOR_ADVANCES being F.

        .text
        .globl _start
_start:
        li      t0, ROT_WINDOW_TRNG
        csetaddr c5, c1, t0
        sd      zero, ROT_TRNG_STARTUP(c5)
        li      t0, ROT_WINDOW_COUNTERS
        csetaddr c5, c1, t0
        li      t1, PREAMBLE_FLOOR_ADVANCES
__preamble_floor_advance:
        beqz    t1, __preamble_enter
        sd      zero, ROT_CTR_ADVANCE(c5)
        addi    t1, t1, -1
        j       __preamble_floor_advance
__preamble_enter:
        la      c5, VOS_CHAIN_ROT_RUNTIME_BASE
        cclear  0, 0xffdd
        cclear  1, 0xffff
        cjr     c5
