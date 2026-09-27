# SPDX-License-Identifier: Apache-2.0
# c10: exact device-word capability, x11: identity, x12: binary signal request.
# The validated device-register declaration owns COPY_NOTIFICATION_IDENTITIES.
.text
vos_copy_notify:
    beqz x11, vos_copy_notify_invalid
    li x5, COPY_NOTIFICATION_IDENTITIES
    bgeu x11, x5, vos_copy_notify_invalid
    li x5, 1
    bgtu x12, x5, vos_copy_notify_invalid
    beqz x12, vos_copy_notify_done
    fence iorw, iorw
vos_copy_notify_store:
    sd x11, 0(c10)
    fence iorw, iorw
vos_copy_notify_done:
    li x10, 1
    ret
vos_copy_notify_invalid:
    li x10, 0
    ret
vos_copy_poll:
    beqz x11, vos_copy_poll_invalid
    li x5, COPY_NOTIFICATION_IDENTITIES
    bgeu x11, x5, vos_copy_poll_invalid
    fence iorw, iorw
    ld x5, 0(c10)
    fence iorw, iorw
    srl x5, x5, x11
    andi x10, x5, 1
    ret
vos_copy_poll_invalid:
    li x10, -1
    ret
