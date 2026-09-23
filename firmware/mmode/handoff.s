# SPDX-License-Identifier: Apache-2.0
# The M-mode stage's kernel handoff, lowered by hand to the assembler dialect.
#
# This is the first code the RoT releases the boot core into: it runs from the
# load base of the M-mode image region under the model's reset distribution
# (model/model/postlude/step_ext.sail) and ends in the no-link sentry jump of
# docs/implementation/contracts/purecap-abi.md section 7. The layout it installs
# is docs/implementation/contracts/boot-handoff.md section 6. It is a hand
# lowering because no compiler reaches the dialect yet: the C lowering of this
# stage waits on the primitive bindings for cspecialrw and csealentry (M1.2d)
# and on M1.7's target path, and the contract names that join.
#
# What it reads from the composition is symbolic: the kernel's text, data,
# stack, root table and initialization descriptor are labels the composed image
# defines (for the harness, firmware/harness/kernel_entry_fixture.s). The boot
# descriptor is the record the RoT wrote before release, at the constant below.
#
# The bring-up composition declares no sealing grant type, so neither
# object-type root at reset (c2, c3; implementation/contracts/sealing-bootstrap.md)
# has an admitted derivation: the stack takes c2 and the final clear takes c3.

        .equ    BOOT_DESCRIPTOR, 0x80010000
        .equ    BOOT_DESCRIPTOR_BYTES, 256
        # Expanded permission bitmaps (model/model/core/cap_common.sail).
        .equ    PERMS_DATA_ROOT_GLOBAL, 0xdf
        .equ    PERMS_STACK_LOCAL, 0xfe
        .equ    PERMS_R_CAP_LM_LG_GLOBAL, 0xcb
        .equ    PERMS_R_GLOBAL, 0x3

        .text
        .globl _start
_start:
        # The store-side root arrives in c1 (cra); nothing here calls, but the
        # root is moved out first as every corpus program does.
        cmove   c8, c1

        # The kernel's text authority: the reset execute root narrowed to the
        # kernel text extent. It keeps execute and access-system-registers and
        # never held store (perms_code_root_asr).
        la      c9, kernel_text_base
        li      t0, kernel_text_end - kernel_text_base
        csetbounds c9, c9, t0

        # MTCC: the kernel's trap entry inside that extent.
        li      t0, kernel_trap - kernel_text_base
        cincoffset c6, c9, t0
        cspecialrw cnull, mtcc, c6

        # The kernel data root, the one store-side extent this composition
        # declares, and MTDC from it.
        li      t0, kdata_base
        csetaddr c7, c8, t0
        li      t0, kdata_end - kdata_base
        csetbounds c7, c7, t0
        li      t0, PERMS_DATA_ROOT_GLOBAL
        candperm c7, c7, t0
        cspecialrw cnull, mtdc, c7

        # The root-set table: one tagged member per declared extent, written
        # through the store-side root, then handed over read-only with load
        # transitivity.
        li      t0, root_table
        csetaddr c10, c8, t0
        sc      c7, 0(c10)
        li      t0, root_table_end - root_table
        csetbounds c10, c10, t0
        li      t0, PERMS_R_CAP_LM_LG_GLOBAL
        candperm c10, c10, t0

        # The boot descriptor: the RoT's handoff record, read-only.
        li      t0, BOOT_DESCRIPTOR
        csetaddr c11, c8, t0
        li      t0, BOOT_DESCRIPTOR_BYTES
        csetbounds c11, c11, t0
        li      t0, PERMS_R_GLOBAL
        candperm c11, c11, t0

        # The kernel initialization descriptor.
        li      t0, init_desc
        csetaddr c12, c8, t0
        li      t0, init_desc_end - init_desc
        csetbounds c12, c12, t0
        li      t0, PERMS_R_CAP_LM_LG_GLOBAL
        candperm c12, c12, t0

        # The kernel stack: local perms_stack over the stack region, cursor at
        # its top. This replaces the seal root c2 held.
        li      t0, kstack_base
        csetaddr c2, c8, t0
        li      t0, kstack_end - kstack_base
        csetbounds c2, c2, t0
        li      t0, PERMS_STACK_LOCAL
        candperm c2, c2, t0
        li      t0, kstack_end - kstack_base
        cincoffset c2, c2, t0

        # The transient entry sentry, minted last: t0 is x5, the register the
        # sentry lives in, so no scratch write may follow it.
        li      t0, kernel_entry - kernel_text_base
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
