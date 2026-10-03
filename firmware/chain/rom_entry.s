# SPDX-License-Identifier: Apache-2.0
# The RoT ROM program's assembly (docs/implementation/contracts/boot-handoff.md
# section 9.5): the reset entry, the device reads the C body cannot make, the
# bounded capabilities it hands that body, and the two endings.
#
# The contained compiler lowers no volatile access, so every door this program
# touches is touched here and rom.c's vos_chain_rom is pure over the windows it
# is handed. The composer (tools/vos/chain_rot.py) places this text at the
# reset entry ahead of rot_policy.s and the compiled stream, and supplies every
# upper-case name as an `.equ`: vos_boot.h's and vos_chain.h's macros under
# their own names, rot.sail's door offsets as ROT_*, the RoT composition's
# window bases as ROT_WINDOW_*, and the run's two parameters, ROM_FLOOR_ADVANCES
# (counter 0's advances in this power-on, F-438) and ROM_ENTROPY_FAILED (the
# entropy-halt case's injected health word, section 9.12).
#
# The ROM neither arms nor pets the watchdog: it counts from power-on and the
# runtime opens its window (section 9.5).

        .text
        .globl _start
_start:
        # The store-side root arrives in c1 and is kept in the ABI's reserved c4;
        # a trap reports 0x100 plus its cause through HTIF.
        cmove   c4, c1
        la      c9, __rom_trap
        cspecialrw cnull, mtcc, c9
        li      t0, __rom_stack
        csetaddr csp, c4, t0
        li      t1, CHAIN_STACK_BYTES
        csetbounds csp, csp, t1
        li      t1, PERMS_STACK
        candperm csp, csp, t1
        li      t0, __rom_stack_top
        csetaddr csp, csp, t0

        # The inputs record, filled in section 9.5's order.
        li      t0, __rom_inputs
        csetaddr c18, c4, t0

        # 1. The lifecycle index (R-09-037), before any image byte is read.
        li      t0, ROT_WINDOW_OTP
        csetaddr c19, c4, t0
        ld      t1, ROT_OTP_STATE(c19)
        sd      t1, CHAIN_INPUT_LIFECYCLE_AT(c18)

        # 2. The entropy root's start-up tests, then its health word (R-09-006a).
        # The entropy-halt case substitutes a failed word for the one read.
        li      t0, ROT_WINDOW_TRNG
        csetaddr c19, c4, t0
        sd      zero, ROT_TRNG_STARTUP(c19)
        ld      t1, ROT_TRNG_HEALTH(c19)
        li      t2, ROM_ENTROPY_FAILED
        beqz    t2, __rom_health_read
        li      t1, CHAIN_FAILED_HEALTH
__rom_health_read:
        sd      t1, CHAIN_INPUT_HEALTH_WORD_AT(c18)

        # 3. The boot-target latch (R-09-029).
        li      t0, VOS_CHAIN_BOOT_CONTROL_BASE
        csetaddr c19, c4, t0
        ld      t1, VOS_CHAIN_DOOR_BOOT_TARGET(c19)
        sd      t1, CHAIN_INPUT_BOOT_TARGET_AT(c18)

        # The floor, established in this power-on by advancing counter 0
        # (R-10-013's image security version), then read.
        li      t0, ROT_WINDOW_COUNTERS
        csetaddr c19, c4, t0
        li      t1, ROM_FLOOR_ADVANCES
__rom_floor_advance:
        beqz    t1, __rom_floor_read
        sd      zero, ROT_CTR_ADVANCE(c19)
        addi    t1, t1, -1
        j       __rom_floor_advance
__rom_floor_read:
        ld      t1, ROT_CTR_BASE(c19)
        sd      t1, CHAIN_INPUT_FLOOR_AT(c18)
        # The slot and attempt doors are the runtime's to read.
        sd      zero, CHAIN_INPUT_SLOT_AT(c18)
        sd      zero, CHAIN_INPUT_ATTEMPTS_AT(c18)

        # The root policy over the ROM's root table.
        li      t0, __rom_policy
        csetaddr c11, c4, t0
        call    __chain_policy

        # vos_chain_rom(inputs, policy, store, store_len, runtime_region,
        #               runtime_region_bytes, state, capture), each pointer a
        # capability bounded to its window.
        li      t0, __rom_inputs
        csetaddr c10, c4, t0
        li      t0, CHAIN_INPUT_BYTES
        csetbounds c10, c10, t0
        li      t0, PERMS_R_GLOBAL
        candperm c10, c10, t0
        li      t0, __rom_policy
        csetaddr c11, c4, t0
        li      t0, CHAIN_POLICY_BYTES
        csetbounds c11, c11, t0
        li      t0, PERMS_R_CAP_LM_LG_GLOBAL
        candperm c11, c11, t0
        li      t0, VOS_CHAIN_STORE_RUNTIME_BASE
        csetaddr c12, c4, t0
        li      t0, VOS_CHAIN_STORE_RUNTIME_BYTES
        csetbounds c12, c12, t0
        li      t0, PERMS_R_GLOBAL
        candperm c12, c12, t0
        li      a3, VOS_CHAIN_STORE_RUNTIME_BYTES
        li      t0, VOS_CHAIN_ROT_RUNTIME_BASE
        csetaddr c14, c4, t0
        li      t0, VOS_CHAIN_ROT_RUNTIME_REGION_BYTES
        csetbounds c14, c14, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c14, c14, t0
        li      a5, VOS_CHAIN_ROT_RUNTIME_REGION_BYTES
        li      t0, VOS_CHAIN_ROT_STATE_BASE
        csetaddr c16, c4, t0
        li      t0, VOS_CHAIN_STATE_BYTES
        csetbounds c16, c16, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c16, c16, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE
        csetaddr c17, c4, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_WINDOW_BYTES
        csetbounds c17, c17, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c17, c17, t0
        call    vos_chain_rom
        bnez    a0, __rom_refused

        # Run RotRuntime (R-09-002): enter stage 0 at its base with the RoT's own
        # authority, PCC the reset execute root and c1 the store-side root, and
        # no other register.
        la      c5, VOS_CHAIN_ROT_RUNTIME_BASE
        cmove   c1, c4
        cclear  0, 0xffdd
        cclear  1, 0xffff
        cjr     c5

__rom_refused:
        # A completed refusal: the boot-control values read last, then HTIF
        # success, which is the completed attempt the capture decides.
        li      t0, VOS_CHAIN_BOOT_CONTROL_BASE
        csetaddr c19, c4, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE
        csetaddr c20, c4, t0
        ld      t1, VOS_CHAIN_DOOR_SLOT(c19)
        sd      t1, VOS_CHAIN_CAPTURE_SLOT_FINAL_AT(c20)
        ld      t1, VOS_CHAIN_DOOR_ATTEMPTS(c19)
        sd      t1, VOS_CHAIN_CAPTURE_ATTEMPTS_FINAL_AT(c20)
        li      t0, 1
        j       __rom_exit

__rom_trap:
        csrr    t0, mcause
        andi    t0, t0, 0xFF
        ori     t0, t0, 0x100
        slli    t0, t0, 1
        ori     t0, t0, 1
__rom_exit:
        li      t1, CHAIN_ROT_TOHOST
        csetaddr c31, c4, t1
        sd      t0, 0(c31)
__rom_halt:
        j       __rom_halt

        .data
        .balign CHAIN_STACK_BYTES
__rom_stack:
        .space  CHAIN_STACK_BYTES
__rom_stack_top:
        .balign 8
__rom_inputs:
        .space  CHAIN_INPUT_BYTES
__rom_policy:
        .space  CHAIN_POLICY_BYTES
        .text
