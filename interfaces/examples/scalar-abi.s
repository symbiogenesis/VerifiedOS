# SPDX-License-Identifier: Apache-2.0
# Scalar authoring witness for docs/implementation/purecap-abi-contract.md.
# This is an assembler and Sail-clause review fixture, not boot firmware or
# evidence of execution. Its input capabilities are producer obligations:
#
# PCC: firmware text, tagged/unsealed, execute and access-system-registers.
# c2: local perms_stack over [S,S+128), S aligned to 128, cursor S+128.
# c5: forward sentry targeting kernel_entry, exact bounds through kernel_end,
#     execute and access-system-registers, no store.
# c6: tagged/unsealed kernel trap entry with execute and ASR, direct-mode aligned.
# c7: kernel trap-data capability, granted by the composed distribution.
# c10: global perms_r_cap_lm_lg over a granule-aligned root table. Slot 0
#      contains a global writable capability D to a disjoint aligned 8-byte cell.
# c11/c12: boot and initialization descriptors with the contract's authority.
# All other input registers are arbitrary. Ordinary interrupts are disabled.
# Every loaded capability is unrevoked; memory accesses complete without an
# external memory fault. The table, descriptors and D are disjoint from stack
# and executing text. The stack's live slots are initialized by their stores.
# Descriptor provenance, layouts and initial context/schedule acceptance are
# supplied by the real producer join; this fixture does not inspect them.
# The final firmware sequence installs trap state and cannot return to firmware.

        .text
        .globl _start
_start:
        cspecialrw cnull, mtcc, c6
        cspecialrw cnull, mtdc, c7
        cmove   c31, cnull
        cspecialrw cnull, mepcc, c31
        # Preserve exactly c2, c5, c10, c11, c12. x0 is always null.
        cclear  0, 0xe3db
        cclear  1, 0xffff
        cjr     c5

kernel_entry:
        cmove   c5, cnull
        # Nonreturning kernel body. These calls exercise ordinary frame rules,
        # not descriptor validation or partition dispatch.
        cmove   c30, csp
        cincoffsetimm csp, csp, -32
        sc      c30, 0(csp)
        sc      cra, 8(csp)
        sc      c10, 16(csp)
        sc      c11, 24(csp)
        lc      c10, 0(c10)
        call    scalar_store
        lc      c10, 16(csp)
        lc      c11, 24(csp)
        lc      cra, 8(csp)
        lc      csp, 0(csp)
        # a0 now holds the restored root table, c11 the boot descriptor,
        # csp its original tagged value and cra null. D contains integer 42.
done:
        j       done

# Signature: scalar_store(capability D) -> unsigned 64-bit word.
# D is live across leaf_word and must survive its integer write to a0.
scalar_store:
        cmove   c30, csp
        cincoffsetimm csp, csp, -32
        sc      c30, 0(csp)
        sc      cra, 8(csp)
        sc      c10, 16(csp)
        call    leaf_word
        lc      c11, 16(csp)
        sd      a0, 0(c11)
        lc      cra, 8(csp)
        lc      csp, 0(csp)
        ret

# Signature: leaf_word() -> unsigned 64-bit word. No frame is needed.
leaf_word:
        li      a0, 42
        ret
kernel_end:
