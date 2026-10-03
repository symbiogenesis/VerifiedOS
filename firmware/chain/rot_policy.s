# SPDX-License-Identifier: Apache-2.0
# The ROM root policy both RoT programs hand their C bodies
# (docs/implementation/contracts/boot-handoff.md sections 9.5 and 9.6; the C
# record is vos_chain.h's vos_chain_rom_policy). The ROM program's root table
# sits at CHAIN_ROOT_TABLE_BASE: a doubleword whose bit i says lifecycle state i
# accepts a root (R-09-036), then one SLH-DSA-SHAKE-256s public key per state at
# CHAIN_ROOT_TABLE_KEYS_AT plus i times the key's size. The ROM verifies the
# runtime under it and the runtime the M-mode image under the same table
# (R-09-036a). The composer (tools/vos/chain_rot.py) supplies every name this
# file uses as an `.equ`.
#
# __chain_policy: fill the record c11 addresses with one bounded read-only
# capability per accepted root and null for every other state. c4 holds the
# store-side root; t0 to t5 and c12 to c14 are clobbered; returns through c1.
        .text
__chain_policy:
        li      t0, CHAIN_ROOT_TABLE_BASE
        csetaddr c12, c4, t0
        ld      t2, CHAIN_ROOT_TABLE_PRESENT_AT(c12)
        li      t5, CHAIN_ROOT_TABLE_BASE + CHAIN_ROOT_TABLE_KEYS_AT
        cmove   c13, c11
        li      t3, 0
__chain_policy_next:
        li      t1, VOS_LIFECYCLE_COUNT
        bgeu    t3, t1, __chain_policy_done
        srl     t1, t2, t3
        andi    t1, t1, 1
        cmove   c14, cnull
        beqz    t1, __chain_policy_store
        csetaddr c14, c4, t5
        li      t1, VOS_BOOT_PUBLIC_KEY_BYTES
        csetbounds c14, c14, t1
        li      t1, PERMS_R_GLOBAL
        candperm c14, c14, t1
__chain_policy_store:
        sc      c14, 0(c13)
        cincoffsetimm c13, c13, CHAIN_POINTER_BYTES
        addi    t5, t5, VOS_BOOT_PUBLIC_KEY_BYTES
        addi    t3, t3, 1
        j       __chain_policy_next
__chain_policy_done:
        ret
