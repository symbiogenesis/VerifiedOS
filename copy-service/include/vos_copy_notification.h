// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_COPY_NOTIFICATION_H
#define VOS_COPY_NOTIFICATION_H
#include <stdint.h>

/* Target assembly leaves, using ordinary memory operations, never a syscall.
 * The composition supplies exactly bounded data-only device capabilities.
 * notify: 1 accepted (including a zero request), 0 malformed scalar input.
 * poll: 0 no pending identity, 1 pending, -1 malformed identity.
 * Polling does not write back the shared pending word. */
int vos_copy_notify(uint64_t *door, uint32_t identity, uint32_t requested);
int vos_copy_poll(const uint64_t *pending, uint32_t identity);
#endif
