// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_SUPERVISOR_CONTEXT_H
#define VOS_SUPERVISOR_CONTEXT_H

#include "vos_supervisor.h"
#include "vos_context_layout.h"

enum vos_supervisor_context_desired {
    VOS_SUPERVISOR_CONTEXT_HOLD,
    VOS_SUPERVISOR_CONTEXT_INITIAL,
    VOS_SUPERVISOR_CONTEXT_RESTART
};

enum vos_supervisor_context_phase {
    VOS_SUPERVISOR_CONTEXT_READY,
    VOS_SUPERVISOR_CONTEXT_AWAIT_ACK,
    VOS_SUPERVISOR_CONTEXT_BACKOFF,
    VOS_SUPERVISOR_CONTEXT_REFUSED
};

enum vos_supervisor_context_result {
    VOS_SUPERVISOR_CONTEXT_IDLE,
    VOS_SUPERVISOR_CONTEXT_WAIT,
    VOS_SUPERVISOR_CONTEXT_PUBLISH,
    VOS_SUPERVISOR_CONTEXT_DONE,
    VOS_SUPERVISOR_CONTEXT_REJECTED
};

/* Local reaction state, never a wire overlay or a saved callback continuation.
 * The acknowledged prefix remains visible after a refusal. */
struct vos_supervisor_context {
    uint64_t acknowledged_sequence;
    uint64_t outstanding_sequence;
    uint64_t epoch;
    uint32_t phase;
    uint32_t outstanding_operation;
    uint32_t lifecycle_phase;
    uint32_t status;
    uint32_t members;
    uint32_t started;
    uint32_t count;
    uint32_t refused;
    uint32_t attempts;
};

/* Fresh-entry recovery from a kernel-owned acknowledgment/snapshot. A failed
 * prefix becomes a new policy decision; only RESTART can retire it before retry.
 * Refusal leaves state unchanged. The caller supplies stable bounded regions. */
int vos_supervisor_context_recover(
    const struct vos_supervisor_manifest *manifest,
    const uint64_t ack[VOS_CTX_ACK_WORDS],
    struct vos_supervisor_context *state);

/* One bounded, nonblocking reaction. desired is an explicit policy decision,
 * not a detector inferred here. HOLD publishes nothing. RESTART remains selected
 * across retirement and backoff; a successful start returns DONE without another
 * request in that reaction. A refused acknowledgment is sticky until recover.
 * An unmatched acknowledgment is never consumed, even if its sequence is newer.
 *
 * request is a local output buffer. Its sequence word is always zero, including
 * on PUBLISH; publish_sequence is separate. The target wrapper must clear the
 * shared sequence before changing shared words, copy the bounded output, order
 * its stores, and store publish_sequence last as the completed reaction's final
 * publication act. Only the fixed poll-site return follows. A fault abandons
 * this local state and recovers from the kernel acknowledgment on fresh entry.
 * C stores here do not establish target ordering or region permissions. */
enum vos_supervisor_context_result vos_supervisor_context_step(
    const struct vos_supervisor_manifest *manifest,
    struct vos_supervisor_context *state,
    const uint64_t ack[VOS_CTX_ACK_WORDS], uint32_t desired,
    uint64_t request[VOS_CTX_REQ_WORDS], uint64_t *publish_sequence);

#endif
