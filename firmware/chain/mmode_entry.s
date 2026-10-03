# SPDX-License-Identifier: Apache-2.0
# The target chain's M-mode stage entry, lowered by hand to the assembler dialect
# (docs/implementation/contracts/boot-handoff.md section 9.8).
#
# The released boot core starts here, at chain.mmode_load_base, under the model's
# reset distribution: PCC, MTCC and MEPCC the execute root with
# access-system-registers, MTDC null, c1 the store-side root, c2 and c3 the
# object-type roots. The entry derives bounded capabilities to the handoff record,
# the kernel-stage root this image carries, the kernel store, the kernel region,
# the mailbox's request and response slots and the M-mode capture from the
# store-side root, and calls the compiled body (mmode.c) through
# vos_chain_mmode_entry. On a release it installs section 6's kernel-entry state
# over the kernel.* layout and enters with `cjr c5`, as firmware/mmode/handoff.s
# does for the bring-up composition; on a refusal the body has zeroed the kernel
# region and the entry reports HTIF exit VOS_CHAIN_MMODE_EXIT_BASE plus the code
# at chain.tohost_base. A trap reaching the entry's handler reports
# 0x100 | mcause, which no case expects.
#
# Every VOS_* name is a macro of firmware/chain/vos_chain.h or
# firmware/include/vos_boot.h, which tools/vos/chain_mmode.py hands the assembler
# as imported constants, so this file restates none of their values. The
# compiled stream and the kernel-stage root key, labelled vos_chain_kernel_root,
# follow this text in the composed image. The body never writes mtimecmp, so no
# boundary event is armed when the kernel starts (R-15-066a).
#
# The bring-up composition, by section 6's selection, declares no sealing grant
# type, so neither object-type root at reset has an admitted derivation;
# sealing-bootstrap.md section 2 requires the broad roots cleared before the
# kernel runs: the stack takes c2 and the final clear takes c3.

        # Expanded permission bitmaps (model/model/core/cap_common.sail), section
        # 6's, as firmware/mmode/handoff.s spells them.
        .equ    PERMS_DATA_ROOT_GLOBAL, 0xdf
        .equ    PERMS_STACK_LOCAL, 0xfe
        .equ    PERMS_R_CAP_LM_LG_GLOBAL, 0xcb
        .equ    PERMS_R_GLOBAL, 0x3
        # The body's windows: read and global, or read, write and global.
        .equ    PERMS_RW_GLOBAL, 0x7
        # The body's own stack keeps every permission of the store-side root but
        # globality, the compiler harness's shape (tools/vos/cli/compiler_diff.py).
        .equ    PERMS_BODY_STACK, 0xffe
        # The body's stack: the region's top, outside every stage-1 payload, which
        # the RoT zeroed when it placed the image. tools/vos/chain_mmode.py holds
        # the compiled stream's frame sum and the payload's end against it.
        .equ    MMODE_STACK_BYTES, 32768
        .equ    MMODE_STACK_TOP, VOS_CHAIN_MMODE_LOAD_BASE + VOS_CHAIN_MMODE_REGION_BYTES
        .equ    MMODE_STACK_BASE, MMODE_STACK_TOP - MMODE_STACK_BYTES
        .equ    MMODE_TRAP_BASE, 0x100
        .equ    KERNEL_TEXT, VOS_CHAIN_KERNEL_LOAD_BASE + VOS_CHAIN_KERNEL_TEXT_AT

        .text
        .globl _start
_start:
        # The store-side root moves into c4, which the selected scalar ABI
        # reserves, so it survives the body's call.
        cmove   c4, c1
        la      c9, __vos_mmode_trap
        cspecialrw cnull, mtcc, c9

        # The body's stack, cursor at its top.
        li      t0, MMODE_STACK_BASE
        csetaddr csp, c4, t0
        li      t1, MMODE_STACK_BYTES
        csetbounds csp, csp, t1
        li      t1, PERMS_BODY_STACK
        candperm csp, csp, t1
        li      t0, MMODE_STACK_TOP
        csetaddr csp, csp, t0

        # c10: the handoff record the RoT wrote, read-only.
        li      t0, VOS_CHAIN_HANDOFF_BASE
        csetaddr c10, c4, t0
        li      t0, VOS_HANDOFF_BYTES
        csetbounds c10, c10, t0
        li      t0, PERMS_R_GLOBAL
        candperm c10, c10, t0
        # c11: the kernel-stage root this measured image carries, read-only.
        li      t0, vos_chain_kernel_root
        csetaddr c11, c4, t0
        li      t0, VOS_CHAIN_KSTAGE_PUBLIC_KEY_BYTES
        csetbounds c11, c11, t0
        li      t0, PERMS_R_GLOBAL
        candperm c11, c11, t0
        # c12: the kernel store window, read-only.
        li      t0, VOS_CHAIN_KERNEL_STORE_BASE
        csetaddr c12, c4, t0
        li      t0, VOS_CHAIN_KERNEL_STORE_BYTES
        csetbounds c12, c12, t0
        li      t0, PERMS_R_GLOBAL
        candperm c12, c12, t0
        # c13: the kernel region, read/write.
        li      t0, VOS_CHAIN_KERNEL_LOAD_BASE
        csetaddr c13, c4, t0
        li      t0, VOS_CHAIN_KERNEL_REGION_BYTES
        csetbounds c13, c13, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c13, c13, t0
        # c14: the mailbox's request slot, read/write.
        li      t0, VOS_CHAIN_MAILBOX_BASE + VOS_CHAIN_MAILBOX_REQUEST_AT
        csetaddr c14, c4, t0
        li      t0, VOS_CHAIN_REQUEST_BYTES
        csetbounds c14, c14, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c14, c14, t0
        # c15: the mailbox's response slot, read-only.
        li      t0, VOS_CHAIN_MAILBOX_BASE + VOS_CHAIN_MAILBOX_RESPONSE_AT
        csetaddr c15, c4, t0
        li      t0, VOS_CHAIN_RESPONSE_BYTES
        csetbounds c15, c15, t0
        li      t0, PERMS_R_GLOBAL
        candperm c15, c15, t0
        # c16: the M-mode capture, read/write.
        li      t0, VOS_CHAIN_MMODE_CAPTURE_BASE
        csetaddr c16, c4, t0
        li      t0, VOS_CHAIN_MCAPTURE_BYTES
        csetbounds c16, c16, t0
        li      t0, PERMS_RW_GLOBAL
        candperm c16, c16, t0

        call    vos_chain_mmode_entry
        bnez    a0, __vos_mmode_refuse

        # The release: section 6's state over the kernel.* layout.
        # The kernel's text authority: the reset execute root narrowed to the
        # kernel text extent. It keeps execute and access-system-registers and
        # never held store (perms_code_root_asr).
        la      c9, KERNEL_TEXT
        li      t0, VOS_CHAIN_KERNEL_TEXT_BYTES
        csetbounds c9, c9, t0

        # MTCC: the kernel's trap entry inside that extent.
        li      t0, VOS_CHAIN_KERNEL_TRAP_AT
        cincoffset c6, c9, t0
        cspecialrw cnull, mtcc, c6

        # The kernel data root, the one store-side extent this composition
        # declares, and MTDC from it.
        li      t0, VOS_CHAIN_KERNEL_LOAD_BASE + VOS_CHAIN_KERNEL_DATA_AT
        csetaddr c7, c4, t0
        li      t0, VOS_CHAIN_KERNEL_DATA_BYTES
        csetbounds c7, c7, t0
        li      t0, PERMS_DATA_ROOT_GLOBAL
        candperm c7, c7, t0
        cspecialrw cnull, mtdc, c7

        # The root-set table: one tagged member per declared extent, written
        # through the store-side root after the placement the body measured,
        # then handed over read-only with load transitivity.
        li      t0, VOS_CHAIN_KERNEL_LOAD_BASE + VOS_CHAIN_KERNEL_ROOT_TABLE_AT
        csetaddr c10, c4, t0
        sc      c7, 0(c10)
        li      t0, VOS_CHAIN_KERNEL_ROOT_TABLE_BYTES
        csetbounds c10, c10, t0
        li      t0, PERMS_R_CAP_LM_LG_GLOBAL
        candperm c10, c10, t0

        # The boot descriptor: the RoT's handoff record, read-only.
        li      t0, VOS_CHAIN_HANDOFF_BASE
        csetaddr c11, c4, t0
        li      t0, VOS_HANDOFF_BYTES
        csetbounds c11, c11, t0
        li      t0, PERMS_R_GLOBAL
        candperm c11, c11, t0

        # The kernel initialization descriptor.
        li      t0, VOS_CHAIN_KERNEL_LOAD_BASE + VOS_CHAIN_KERNEL_INIT_AT
        csetaddr c12, c4, t0
        li      t0, VOS_CHAIN_KERNEL_INIT_BYTES
        csetbounds c12, c12, t0
        li      t0, PERMS_R_CAP_LM_LG_GLOBAL
        candperm c12, c12, t0

        # The kernel stack: local perms_stack over the stack region, cursor at
        # its top. This replaces the body's stack in c2.
        li      t0, VOS_CHAIN_KERNEL_LOAD_BASE + VOS_CHAIN_KERNEL_STACK_AT
        csetaddr c2, c4, t0
        li      t0, VOS_CHAIN_KERNEL_STACK_BYTES
        csetbounds c2, c2, t0
        li      t0, PERMS_STACK_LOCAL
        candperm c2, c2, t0
        li      t0, VOS_CHAIN_KERNEL_STACK_BYTES
        cincoffset c2, c2, t0

        # The transient entry sentry, minted last: t0 is x5, the register the
        # sentry lives in, so no scratch write may follow it.
        li      t0, VOS_CHAIN_KERNEL_ENTRY_AT
        cincoffset c5, c9, t0
        csealentry c5, c5

        # MEPCC is cleared through a nonzero null source: cspecialrw with cnull
        # as its source only reads.
        cmove   c31, cnull
        cspecialrw cnull, mepcc, c31

        # Keep exactly c2, c5, c10, c11 and c12, then enter with no link.
        cclear  0, 0xe3db
        cclear  1, 0xffff
        cjr     c5

__vos_mmode_refuse:
        # The body zeroed the kernel region; report its code through the main-die
        # run's one HTIF word.
        addi    t0, a0, VOS_CHAIN_MMODE_EXIT_BASE
        slli    t0, t0, 1
        ori     t0, t0, 1
__vos_mmode_report:
        li      t1, VOS_CHAIN_TOHOST_BASE
        csetaddr c31, c4, t1
        li      t1, 8
        csetbounds c31, c31, t1
        sd      t0, 0(c31)
__vos_mmode_halt:
        j       __vos_mmode_halt

__vos_mmode_trap:
        csrr    t0, mcause
        andi    t0, t0, 0xFF
        ori     t0, t0, MMODE_TRAP_BASE
        slli    t0, t0, 1
        ori     t0, t0, 1
        j       __vos_mmode_report
# --- the compiled body follows ---
