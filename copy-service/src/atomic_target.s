# SPDX-License-Identifier: Apache-2.0
# Scalar ABI, all ordinary registers caller-clobbered; csp/cra restored.
# Header offsets and request stride are checked by vos_copy_target_layout.
# External-call-free C stages own validation, staging, and slot transitions.
# This adapter owns the atomic SC boundary. Fences include the Ztso Store/Load
# edge between arming and rechecking, and payload release/acquire edges.
.text
vos_copy_init:
    cmove c5, c2
    cincoffsetimm c2, c2, -16
    sc c1, 0(c2)
    sc c5, 8(c2)
    fence rw, rw
    sb x0, 0(c10)
    sb x0, 1(c10)
    sw x0, 4(c10)
    fence rw, rw
    call vos_copy_init_slots
    lc c1, 0(c2)
    lc c2, 8(c2)
    ret
vos_copy_submit:
    cmove c5, c2
    cincoffsetimm c2, c2, -96
    sc c1, 0(c2)
    sc c5, 8(c2)
    sc c10, 16(c2)
    sc c17, 24(c2)
    sw x11, 32(c2)
    sw x12, 36(c2)
    sw x13, 40(c2)
    sc c14, 48(c2)
    sd x15, 56(c2)
    sd x16, 64(c2)
    fence rw, rw
    lbu x5, 0(c10)
    lbu x6, 1(c10)
    fence rw, rw
    sw x5, 72(c2)
    sw x6, 76(c2)
    cincoffsetimm c11, c2, 32
    cincoffsetimm c12, c2, 72
    call vos_copy_submit_snapshot
    beqz x10, vos_copy_submit_return
    lc c5, 16(c2)
    lwu x6, 72(c2)
    fence rw, rw
    sb x6, 0(c5)
    fence rw, rw
    cincoffsetimm c5, c5, 4
    amoswap.w.aqrl x6, x0, (c5)
    fence rw, rw
    lc c5, 24(c2)
    sw x6, 0(c5)
vos_copy_submit_return:
    lc c1, 0(c2)
    lc c2, 8(c2)
    ret
vos_copy_take:
    cmove c5, c2
    cincoffsetimm c2, c2, -48
    sc c1, 0(c2)
    sc c5, 8(c2)
    sc c10, 16(c2)
    fence rw, rw
    lbu x5, 0(c10)
    lbu x6, 1(c10)
    fence rw, rw
    sw x5, 24(c2)
    sw x6, 28(c2)
    cincoffsetimm c15, c2, 24
    call vos_copy_take_snapshot
    beqz x10, vos_copy_take_return
    lc c5, 16(c2)
    lwu x6, 28(c2)
    fence rw, rw
    sb x6, 1(c5)
    fence rw, rw
vos_copy_take_return:
    lc c1, 0(c2)
    lc c2, 8(c2)
    ret
vos_copy_prepare_sleep:
    li x5, 1
    fence rw, rw
    sw x5, 4(c10)
    fence rw, rw
    lbu x5, 0(c10)
    lbu x6, 1(c10)
    fence rw, rw
    sub x10, x5, x6
    seqz x10, x10
    ret
vos_copy_submit_batch:
    li x5, COPY_MAX_BATCH
    bgtu x12, x5, vos_copy_batch_refuse
    cmove c5, c2
    cincoffsetimm c2, c2, -96
    sc c1, 0(c2)
    sc c5, 8(c2)
    sc c10, 16(c2)
    sc c11, 24(c2)
    sd x12, 32(c2)
    sc c13, 40(c2)
    sc c14, 48(c2)
    sd x0, 56(c2)
vos_copy_batch_loop:
    ld x5, 56(c2)
    ld x6, 32(c2)
    beq x5, x6, vos_copy_batch_done
    lc c5, 24(c2)
    lwu x11, 0(c5)
    lwu x12, 4(c5)
    lwu x13, 8(c5)
    lc c14, 16(c5)
    ld x15, 24(c5)
    ld x16, 32(c5)
    sw x0, 64(c2)
    cincoffsetimm c17, c2, 64
    lc c10, 16(c2)
    call vos_copy_submit
    lc c5, 40(c2)
    sw x10, 0(c5)
    cincoffsetimm c5, c5, 4
    sc c5, 40(c2)
    lc c5, 48(c2)
    lwu x6, 64(c2)
    sw x6, 0(c5)
    cincoffsetimm c5, c5, 4
    sc c5, 48(c2)
    lc c5, 24(c2)
    cincoffsetimm c5, c5, 40
    sc c5, 24(c2)
    ld x5, 56(c2)
    addi x5, x5, 1
    sd x5, 56(c2)
    j vos_copy_batch_loop
vos_copy_batch_done:
    li x10, 1
    lc c1, 0(c2)
    lc c2, 8(c2)
    ret
vos_copy_batch_refuse:
    li x10, 0
    ret
