# SPDX-License-Identifier: Apache-2.0
# The RoT runtime's assembly, stage 0's entry and its only door user
# (docs/implementation/contracts/boot-handoff.md sections 9.6, 9.7 and 9.10).
# The image is entered at its base with PCC the reset execute root and c1 the
# store-side root; it reads the state record and nothing else from the ROM.
#
# A boot run arms the watchdog and walks the bring-up reset table, pets at each
# completion inside the window, reads the slot and attempt doors, selects and
# charges through vos_chain_select, writes the slot door and then the attempt
# door, verifies the selected stage-1 image through vos_chain_runtime_verify,
# pets once more, records what it read last and either writes the release door
# or completes its refusal through HTIF. A service run calls
# vos_chain_service_item6 and touches no door.
#
# The composer (tools/vos/chain_rot.py) places this text at the runtime base
# ahead of rot_policy.s and the compiled runtime.c, with the data below at
# chain.rot_runtime_data_at, and supplies every upper-case name as an `.equ`.
# Window capabilities live in c18 to c24 and are derived again by __rt_windows
# after every call into C, so nothing here rests on a callee preserving them.
# The two watchdog mutants of section 9.10 are text substitutions of this file
# (chain_rot.RUNTIME_MUTANTS), each naming a line that occurs once.

        .text
        .globl _start
_start:
        cmove   c4, c1
        la      c9, __rt_trap
        cspecialrw cnull, mtcc, c9
        li      t0, __rt_stack
        csetaddr csp, c4, t0
        li      t1, CHAIN_STACK_BYTES
        csetbounds csp, csp, t1
        li      t1, PERMS_STACK
        candperm csp, csp, t1
        li      t0, __rt_stack_top
        csetaddr csp, csp, t0
        call    __rt_windows

        # A service run's state record names it (section 9.7).
        ld      t1, VOS_CHAIN_STATE_RUN_KIND_AT(c18)
        li      t2, VOS_CHAIN_RUN_SERVICE
        beq     t1, t2, __rt_service

        # A state record that is not a boot run's refuses before anything is
        # armed (refuse-state).
        li      t0, VOS_CHAIN_ROT_STATE_BASE
        csetaddr c10, c4, t0
        li      t0, VOS_CHAIN_STATE_BYTES
        csetbounds c10, c10, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c10, c10, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE + VOS_CHAIN_CAPTURE_WINDOW_AT
        csetaddr c11, c4, t0
        li      t0, VOS_CHAIN_MMODE_REGION_BYTES
        csetbounds c11, c11, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c11, c11, t0
        li      a2, VOS_CHAIN_MMODE_REGION_BYTES
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE + VOS_CHAIN_CAPTURE_RECORD_AT
        csetaddr c13, c4, t0
        li      t0, VOS_HANDOFF_BYTES
        csetbounds c13, c13, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c13, c13, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE
        csetaddr c14, c4, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_WINDOW_BYTES
        csetbounds c14, c14, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c14, c14, t0
        call    vos_chain_runtime_admit
        call    __rt_windows
        bnez    a0, __rt_finish

        # The root policy over the ROM's root table (R-09-036a).
        li      t0, __rt_policy
        csetaddr c11, c4, t0
        call    __chain_policy

        # The bring-up reset table (section 9.6). Each step polls its ready
        # indication and never pets while it waits, so a step that never becomes
        # ready is ended by the bite and by nothing here.

        # step.arm: open the window; ready when the challenge reads nonzero.
        sd      zero, ROT_WDT_ARM(c20)
__rt_step_arm_wait:
        ld      t1, ROT_WDT_NONCE(c20)
        beqz    t1, __rt_step_arm_wait
        sd      t1, VOS_CHAIN_CAPTURE_NONCE_AT_ARM_AT(c19)
        call    __rt_step_completed
        ld      a0, ROT_WDT_TICKS(c20)          # step.arm's pet point reads the tick door
        ld      a1, ROT_WDT_EARLY(c20)
        ld      a2, ROT_WDT_LATE(c20)
        call    vos_chain_pet_due
        call    __rt_windows
        call    __rt_pet_or_skip

        # step.entropy: no action, the ROM ran the start-up tests.
__rt_step_entropy_wait:
        ld      t1, ROT_TRNG_HEALTH(c21)
        srli    t1, t1, 32                      # step.entropy ready: bit 32 set and bit 33 clear
        andi    t1, t1, 3
        li      t2, 1
        bne     t1, t2, __rt_step_entropy_wait
        call    __rt_step_completed
        ld      a0, ROT_WDT_TICKS(c20)
        ld      a1, ROT_WDT_EARLY(c20)
        ld      a2, ROT_WDT_LATE(c20)
        call    vos_chain_pet_due
        call    __rt_windows
        call    __rt_pet_or_skip

        # step.floor: no action; ready when counter 0 reads nonzero.
__rt_step_floor_wait:
        ld      t1, ROT_CTR_BASE(c22)
        beqz    t1, __rt_step_floor_wait
        call    __rt_step_completed
        ld      a0, ROT_WDT_TICKS(c20)
        ld      a1, ROT_WDT_EARLY(c20)
        ld      a2, ROT_WDT_LATE(c20)
        call    vos_chain_pet_due
        call    __rt_windows
        call    __rt_pet_or_skip

        # Selection and counting (section 9.6): the slot and attempt doors as
        # selection starts, the decision over the measured latch, and the slot
        # door then the attempt door written before the verification they gate.
        ld      a1, VOS_CHAIN_DOOR_SLOT(c23)
        sd      a1, VOS_CHAIN_CAPTURE_SLOT_INITIAL_AT(c19)
        ld      a2, VOS_CHAIN_DOOR_ATTEMPTS(c23)
        sd      a2, VOS_CHAIN_CAPTURE_ATTEMPTS_INITIAL_AT(c19)
        ld      a0, VOS_CHAIN_STATE_BOOT_TARGET_AT(c18)
        cmove   c13, c24
        call    vos_chain_select
        mv      s1, a0
        call    __rt_windows
        ld      t1, CHAIN_SELECTION_CHARGED_AT(c24)
        beqz    t1, __rt_selected
        ld      t1, CHAIN_SELECTION_SLOT_AT(c24)
        sd      t1, VOS_CHAIN_DOOR_SLOT(c23)
        ld      t1, CHAIN_SELECTION_ATTEMPTS_AT(c24)
        sd      t1, VOS_CHAIN_DOOR_ATTEMPTS(c23)
__rt_selected:

        # vos_chain_runtime_verify(state, policy, selected, store, store_len,
        #     mmode_window, mmode_window_bytes, record, capture): the capture,
        #     the ninth argument, is passed at the caller's stack pointer.
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE
        csetaddr c7, c4, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_WINDOW_BYTES
        csetbounds c7, c7, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c7, c7, t0
        cincoffsetimm csp, csp, -16
        sc      c7, 0(csp)
        li      t0, VOS_CHAIN_STORE_A_BASE
        li      t1, VOS_CHAIN_SLOT_B
        bne     s1, t1, __rt_store_not_b
        li      t0, VOS_CHAIN_STORE_B_BASE
__rt_store_not_b:
        li      t1, VOS_CHAIN_SLOT_RECOVERY
        bne     s1, t1, __rt_store_chosen
        li      t0, VOS_CHAIN_STORE_RECOVERY_BASE
__rt_store_chosen:
        csetaddr c13, c4, t0
        li      t0, VOS_CHAIN_STORE_MMODE_BYTES
        csetbounds c13, c13, t0
        li      t0, PERMS_R_GLOBAL
        candperm c13, c13, t0
        li      a4, VOS_CHAIN_STORE_MMODE_BYTES
        li      t0, VOS_CHAIN_ROT_STATE_BASE
        csetaddr c10, c4, t0
        li      t0, VOS_CHAIN_STATE_BYTES
        csetbounds c10, c10, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c10, c10, t0
        li      t0, __rt_policy
        csetaddr c11, c4, t0
        li      t0, CHAIN_POLICY_BYTES
        csetbounds c11, c11, t0
        li      t0, PERMS_R_CAP_LM_LG_GLOBAL
        candperm c11, c11, t0
        mv      a2, s1
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE + VOS_CHAIN_CAPTURE_WINDOW_AT
        csetaddr c15, c4, t0
        li      t0, VOS_CHAIN_MMODE_REGION_BYTES
        csetbounds c15, c15, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c15, c15, t0
        li      a6, VOS_CHAIN_MMODE_REGION_BYTES
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE + VOS_CHAIN_CAPTURE_RECORD_AT
        csetaddr c17, c4, t0
        li      t0, VOS_HANDOFF_BYTES
        csetbounds c17, c17, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c17, c17, t0
        call    vos_chain_runtime_verify
        cincoffsetimm csp, csp, 16
        call    __rt_windows

        # The pet point after the stage-1 verification, the window it spent.
        ld      a0, ROT_WDT_TICKS(c20)
        ld      a1, ROT_WDT_EARLY(c20)
        ld      a2, ROT_WDT_LATE(c20)
        call    vos_chain_pet_due
        call    __rt_windows
        call    __rt_pet_or_skip

__rt_finish:
        # What the runtime read last (section 9.11).
        ld      t1, VOS_CHAIN_DOOR_SLOT(c23)
        sd      t1, VOS_CHAIN_CAPTURE_SLOT_FINAL_AT(c19)
        ld      t1, VOS_CHAIN_DOOR_ATTEMPTS(c23)
        sd      t1, VOS_CHAIN_CAPTURE_ATTEMPTS_FINAL_AT(c19)
        ld      t1, ROT_WDT_BITTEN(c20)
        sd      t1, VOS_CHAIN_CAPTURE_BITTEN_AT(c19)
        ld      t1, ROT_WDT_TICKS(c20)
        sd      t1, VOS_CHAIN_CAPTURE_TICKS_AT_END_AT(c19)
        ld      t1, VOS_CHAIN_CAPTURE_VERDICT_AT(c19)
        bnez    t1, __rt_complete
        # Release (R-09-006): the capture says so, then the door. The emulator
        # ends the run at this store, so nothing follows it.
        li      t1, 1
        sd      t1, VOS_CHAIN_CAPTURE_RELEASED_AT(c19)
        li      t1, VOS_CHAIN_RELEASE_WORD
        sd      t1, VOS_CHAIN_DOOR_RELEASE(c23)
__rt_released:
        j       __rt_released

__rt_service:
        # vos_chain_service_item6(state, request, response, capture).
        li      t0, VOS_CHAIN_ROT_STATE_BASE
        csetaddr c10, c4, t0
        li      t0, VOS_CHAIN_STATE_BYTES
        csetbounds c10, c10, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c10, c10, t0
        li      t0, VOS_CHAIN_ROT_STATE_BASE + VOS_CHAIN_STATE_REQUEST_AT
        csetaddr c11, c4, t0
        li      t0, VOS_CHAIN_REQUEST_BYTES
        csetbounds c11, c11, t0
        li      t0, PERMS_R_GLOBAL
        candperm c11, c11, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE + VOS_CHAIN_CAPTURE_RESPONSE_AT
        csetaddr c12, c4, t0
        li      t0, VOS_CHAIN_RESPONSE_BYTES
        csetbounds c12, c12, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c12, c12, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE
        csetaddr c13, c4, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_WINDOW_BYTES
        csetbounds c13, c13, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c13, c13, t0
        call    vos_chain_service_item6

__rt_complete:
        # A completed refusal or service: HTIF success, the capture deciding.
        li      t0, 1
        j       __rt_exit

__rt_trap:
        csrr    t0, mcause
        andi    t0, t0, 0xFF
        ori     t0, t0, 0x100
        slli    t0, t0, 1
        ori     t0, t0, 1
__rt_exit:
        li      t1, CHAIN_ROT_TOHOST
        csetaddr c31, c4, t1
        sd      t0, 0(c31)
__rt_halt:
        j       __rt_halt

# The window and door capabilities, each bounded to its extent. Clobbers t0.
__rt_windows:
        li      t0, VOS_CHAIN_ROT_STATE_BASE
        csetaddr c18, c4, t0
        li      t0, VOS_CHAIN_ROT_STATE_WINDOW_BYTES
        csetbounds c18, c18, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c18, c18, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_BASE
        csetaddr c19, c4, t0
        li      t0, VOS_CHAIN_ROT_CAPTURE_WINDOW_BYTES
        csetbounds c19, c19, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c19, c19, t0
        li      t0, ROT_WINDOW_WATCHDOG
        csetaddr c20, c4, t0
        li      t0, ROT_WDT_BYTES
        csetbounds c20, c20, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c20, c20, t0
        li      t0, ROT_WINDOW_TRNG
        csetaddr c21, c4, t0
        li      t0, ROT_TRNG_BYTES
        csetbounds c21, c21, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c21, c21, t0
        li      t0, ROT_WINDOW_COUNTERS
        csetaddr c22, c4, t0
        li      t0, ROT_CTR_BYTES
        csetbounds c22, c22, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c22, c22, t0
        li      t0, VOS_CHAIN_BOOT_CONTROL_BASE
        csetaddr c23, c4, t0
        li      t0, VOS_CHAIN_DOOR_BYTES
        csetbounds c23, c23, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c23, c23, t0
        li      t0, __rt_selection
        csetaddr c24, c4, t0
        li      t0, CHAIN_SELECTION_BYTES
        csetbounds c24, c24, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c24, c24, t0
        ret

# One reset-table step completed. Clobbers t1.
__rt_step_completed:
        ld      t1, VOS_CHAIN_CAPTURE_STEPS_COMPLETED_AT(c19)
        addi    t1, t1, 1
        sd      t1, VOS_CHAIN_CAPTURE_STEPS_COMPLETED_AT(c19)
        ret

# A pet point's act on vos_chain_pet_due's answer in a0: inside the window,
# answer the outstanding challenge (R-15-240's RoT-nonce challenge-response)
# and count an accepted pet; before it, count a skipped one and leave the
# watchdog alone, an early pet being a bite. Clobbers t1.
__rt_pet_or_skip:
        beqz    a0, __rt_pet_skip
        ld      t1, ROT_WDT_NONCE(c20)
        sd      t1, ROT_WDT_PET(c20)
        ld      t1, VOS_CHAIN_CAPTURE_PETS_ACCEPTED_AT(c19)
        addi    t1, t1, 1
        sd      t1, VOS_CHAIN_CAPTURE_PETS_ACCEPTED_AT(c19)
        ret
__rt_pet_skip:
        ld      t1, VOS_CHAIN_CAPTURE_PETS_SKIPPED_AT(c19)
        addi    t1, t1, 1
        sd      t1, VOS_CHAIN_CAPTURE_PETS_SKIPPED_AT(c19)
        ret

        .data
        .balign CHAIN_STACK_BYTES
__rt_stack:
        .space  CHAIN_STACK_BYTES
__rt_stack_top:
        .balign 8
__rt_policy:
        .space  CHAIN_POLICY_BYTES
__rt_selection:
        .space  CHAIN_SELECTION_BYTES
        .text
