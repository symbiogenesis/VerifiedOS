# SPDX-License-Identifier: Apache-2.0
# The boot-handoff harness's kernel-entry fixture and its composition. Not a kernel.
#
# It stands where M4.4's kernel entry will stand and checks, at its first
# instruction, the register state docs/implementation/contracts/purecap-abi.md
# section 7 and docs/implementation/contracts/boot-handoff.md section 6 require,
# then reports through HTIF: exit 0 when every check holds, and otherwise the
# number of the first failing check (a trap during check n reports n + 32).
# The .data half is the bring-up composition's kernel layout: the kernel data
# extent (holding tohost), the stack region, the root-set table's storage and
# the kernel initialization descriptor.
#
# tools/vos/boot_handoff.py appends this file to firmware/mmode/handoff.s and
# assembles the two as one image, the in-tree assembler having no linker.

        .equ    FIXTURE_HANDOFF_MAGIC, 0x31444e4148534f56
        .equ    FIXTURE_INIT_MAGIC, 0x3154494e49534f56
        .equ    FIXTURE_LOAD_BASE, 0x80000000
        .equ    PERMS_CODE_ROOT_ASR_GLOBAL, 0x9cb

        .text
        .align  11
kernel_text_base:
kernel_entry:
        # Check 1: every register but the five inputs (c2, c5, c10, c11, c12)
        # is null, its integer value and its tag. Each register is read before
        # it is used as its own scratch.
        bnez    x1, fail_scrub
        cgettag x1, c1
        bnez    x1, fail_scrub
        bnez    x3, fail_scrub
        cgettag x3, c3
        bnez    x3, fail_scrub
        bnez    x4, fail_scrub
        cgettag x4, c4
        bnez    x4, fail_scrub
        bnez    x6, fail_scrub
        cgettag x6, c6
        bnez    x6, fail_scrub
        bnez    x7, fail_scrub
        cgettag x7, c7
        bnez    x7, fail_scrub
        bnez    x8, fail_scrub
        cgettag x8, c8
        bnez    x8, fail_scrub
        bnez    x9, fail_scrub
        cgettag x9, c9
        bnez    x9, fail_scrub
        bnez    x13, fail_scrub
        cgettag x13, c13
        bnez    x13, fail_scrub
        bnez    x14, fail_scrub
        cgettag x14, c14
        bnez    x14, fail_scrub
        bnez    x15, fail_scrub
        cgettag x15, c15
        bnez    x15, fail_scrub
        bnez    x16, fail_scrub
        cgettag x16, c16
        bnez    x16, fail_scrub
        bnez    x17, fail_scrub
        cgettag x17, c17
        bnez    x17, fail_scrub
        bnez    x18, fail_scrub
        cgettag x18, c18
        bnez    x18, fail_scrub
        bnez    x19, fail_scrub
        cgettag x19, c19
        bnez    x19, fail_scrub
        bnez    x20, fail_scrub
        cgettag x20, c20
        bnez    x20, fail_scrub
        bnez    x21, fail_scrub
        cgettag x21, c21
        bnez    x21, fail_scrub
        bnez    x22, fail_scrub
        cgettag x22, c22
        bnez    x22, fail_scrub
        bnez    x23, fail_scrub
        cgettag x23, c23
        bnez    x23, fail_scrub
        bnez    x24, fail_scrub
        cgettag x24, c24
        bnez    x24, fail_scrub
        bnez    x25, fail_scrub
        cgettag x25, c25
        bnez    x25, fail_scrub
        bnez    x26, fail_scrub
        cgettag x26, c26
        bnez    x26, fail_scrub
        bnez    x27, fail_scrub
        cgettag x27, c27
        bnez    x27, fail_scrub
        bnez    x28, fail_scrub
        cgettag x28, c28
        bnez    x28, fail_scrub
        bnez    x29, fail_scrub
        cgettag x29, c29
        bnez    x29, fail_scrub
        bnez    x30, fail_scrub
        cgettag x30, c30
        bnez    x30, fail_scrub
        bnez    x31, fail_scrub
        cgettag x31, c31
        bnez    x31, fail_scrub

        # Check 2: c5 is the forward sentry over exactly the kernel text, and
        # the entry clears it.
        li      gp, 2
        cgettag t1, c5
        li      t2, 1
        bne     t1, t2, fail
        cgettype t1, c5
        li      t2, -2
        bne     t1, t2, fail
        cgetbase t1, c5
        li      t2, kernel_text_base
        bne     t1, t2, fail
        cgetlen t1, c5
        li      t2, kernel_text_end - kernel_text_base
        bne     t1, t2, fail
        cmove   c5, cnull

        # Check 3: PCC is that extent, unsealed, execute and
        # access-system-registers without store; the firmware text is outside it.
        li      gp, 3
        cspecialrw c14, pcc, cnull
        cgettag t1, c14
        li      t2, 1
        bne     t1, t2, fail
        cgetsealed t1, c14
        bnez    t1, fail
        cgetbase t1, c14
        li      t2, kernel_text_base
        bne     t1, t2, fail
        cgetlen t1, c14
        li      t2, kernel_text_end - kernel_text_base
        bne     t1, t2, fail
        cgetperm t1, c14
        li      t2, PERMS_CODE_ROOT_ASR_GLOBAL
        bne     t1, t2, fail
        cmove   c14, cnull

        # Check 4: csp is local perms_stack over the stack region, at its top.
        li      gp, 4
        cgettag t1, csp
        li      t2, 1
        bne     t1, t2, fail
        cgetperm t1, csp
        li      t2, 0xfe
        bne     t1, t2, fail
        cgetbase t1, csp
        li      t2, kstack_base
        bne     t1, t2, fail
        cgetlen t1, csp
        li      t2, kstack_end - kstack_base
        bne     t1, t2, fail
        cgetaddr t1, csp
        li      t2, kstack_end
        bne     t1, t2, fail

        # Check 5: c10 is the read-only, load-transitive root table, and its
        # one member is the writable kernel data root.
        li      gp, 5
        cgettag t1, c10
        li      t2, 1
        bne     t1, t2, fail
        cgetperm t1, c10
        li      t2, 0xcb
        bne     t1, t2, fail
        cgetbase t1, c10
        li      t2, root_table
        bne     t1, t2, fail
        cgetlen t1, c10
        li      t2, root_table_end - root_table
        bne     t1, t2, fail
        lc      c13, 0(c10)
        cgettag t1, c13
        li      t2, 1
        bne     t1, t2, fail
        cgetperm t1, c13
        li      t2, 0xdf
        bne     t1, t2, fail
        cgetbase t1, c13
        li      t2, kdata_base
        bne     t1, t2, fail
        cgetlen t1, c13
        li      t2, kdata_end - kdata_base
        bne     t1, t2, fail

        # Check 6: c11 is the read-only boot descriptor the RoT wrote before
        # release, and it names this image's load base.
        li      gp, 6
        cgettag t1, c11
        li      t2, 1
        bne     t1, t2, fail
        cgetperm t1, c11
        li      t2, 0x3
        bne     t1, t2, fail
        cgetbase t1, c11
        li      t2, BOOT_DESCRIPTOR
        bne     t1, t2, fail
        cgetlen t1, c11
        li      t2, BOOT_DESCRIPTOR_BYTES
        bne     t1, t2, fail
        ld      t1, 0(c11)
        li      t2, FIXTURE_HANDOFF_MAGIC
        bne     t1, t2, fail
        ld      t1, 8(c11)
        li      t2, 1
        bne     t1, t2, fail
        ld      t1, 56(c11)
        li      t2, FIXTURE_LOAD_BASE
        bne     t1, t2, fail

        # Check 7: c12 is the initialization descriptor for this hart.
        li      gp, 7
        cgettag t1, c12
        li      t2, 1
        bne     t1, t2, fail
        cgetperm t1, c12
        li      t2, 0xcb
        bne     t1, t2, fail
        cgetbase t1, c12
        li      t2, init_desc
        bne     t1, t2, fail
        cgetlen t1, c12
        li      t2, init_desc_end - init_desc
        bne     t1, t2, fail
        ld      t1, 0(c12)
        li      t2, FIXTURE_INIT_MAGIC
        bne     t1, t2, fail
        ld      t1, 16(c12)
        csrr    t2, mhartid
        bne     t1, t2, fail

        # Check 8: MTCC is the kernel trap entry inside the kernel text.
        li      gp, 8
        cspecialrw c14, mtcc, cnull
        cgettag t1, c14
        li      t2, 1
        bne     t1, t2, fail
        cgetaddr t1, c14
        li      t2, kernel_trap
        bne     t1, t2, fail
        cgetbase t1, c14
        li      t2, kernel_text_base
        bne     t1, t2, fail
        cgetlen t1, c14
        li      t2, kernel_text_end - kernel_text_base
        bne     t1, t2, fail
        cgetperm t1, c14
        li      t2, PERMS_CODE_ROOT_ASR_GLOBAL
        bne     t1, t2, fail
        cmove   c14, cnull

        # Check 9: MTDC is the kernel data root.
        li      gp, 9
        cspecialrw c14, mtdc, cnull
        cgettag t1, c14
        li      t2, 1
        bne     t1, t2, fail
        cgetbase t1, c14
        li      t2, kdata_base
        bne     t1, t2, fail
        cgetlen t1, c14
        li      t2, kdata_end - kdata_base
        bne     t1, t2, fail
        cgetperm t1, c14
        li      t2, 0xdf
        bne     t1, t2, fail
        cmove   c14, cnull

        # Check 10: MEPCC holds no continuation into the firmware.
        li      gp, 10
        cspecialrw c14, mepcc, cnull
        cgettag t1, c14
        bnez    t1, fail

        # Every check held: report through the table's data root.
        li      t0, 1
        li      t1, tohost
        csetaddr c13, c13, t1
        sd      t0, 0(c13)
pass_halt:
        j       pass_halt

fail_scrub:
        li      gp, 1
fail:
        slli    t0, gp, 1
        ori     t0, t0, 1
        # The failure path reports through MTDC, which check 5 has not
        # necessarily reached.
        cspecialrw c13, mtdc, cnull
        li      t1, tohost
        csetaddr c13, c13, t1
        sd      t0, 0(c13)
fail_halt:
        j       fail_halt

kernel_trap:
        addi    t0, gp, 32
        slli    t0, t0, 1
        ori     t0, t0, 1
        cspecialrw c13, mtdc, cnull
        li      t1, tohost
        csetaddr c13, c13, t1
        sd      t0, 0(c13)
trap_halt:
        j       trap_halt

        .align  11
kernel_text_end:

        .data
        .align  10
kdata_base:
tohost:
        .dword  0
        .space  1016
kdata_end:
kstack_base:
        .space  1024
kstack_end:
root_table:
        .dword  0
root_table_end:
        .align  6
init_desc:
        .dword  FIXTURE_INIT_MAGIC
        .dword  1
        # hart identity, composition identity, planned contexts, first successor
        .dword  0
        .dword  1
        .dword  1
        .dword  0
        .dword  0
        .dword  0
init_desc_end:
