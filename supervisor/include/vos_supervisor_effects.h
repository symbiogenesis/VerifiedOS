// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_SUPERVISOR_EFFECTS_H
#define VOS_SUPERVISOR_EFFECTS_H

#include "vos_kernel.h"
#include "vos_supervisor.h"

/* Trusted kernel bindings, not requests supplied by an untrusted compartment.
 * No operation may re-enter this adapter. Every operation has a bounded wait
 * fixed by composition; this interface does not create a clock or a timeout.
 *
 * retire: stop the exact ownership-closed set, complete teardown and eager
 * zeroization, and return its actual revocation-completion receipt. A nonzero
 * return acknowledges teardown/zeroization, not revocation completion: the
 * adapter checks the kernel's five-condition predicate separately.
 * wait: acknowledge that the declared backoff delay has elapsed.
 * acquire: acquire serialization against every change to revocation and to the
 * stopped/started units, then read the current snapshot and current epoch under
 * that serialization. A zero return owns no lock. Any nonzero return must be
 * paired with release, even if its snapshot fails validation.
 * start: while serialized, derive exactly request->grants from the manifest at
 * request->epoch and acknowledge the unit's start. Refusal must not start that
 * unit or leave new grants accessible. It must not change the locked snapshot.
 * release: end serialization; it cannot fail or perform another start.
 *
 * acquire through release covers the whole bounded start sequence. Neither a
 * successful callback nor the numeric epoch alone proves kernel acceptance.
 */
struct vos_supervisor_effects {
    int (*retire)(void *context, uint32_t members, struct vos_completion *completion);
    int (*wait)(void *context, uint32_t delay);
    int (*acquire)(void *context, struct vos_supervisor_epoch *snapshot,
                   uint64_t *current_epoch);
    int (*start)(void *context, const struct vos_supervisor_start *request);
    void (*release)(void *context);
};

enum vos_supervisor_execution_status {
    VOS_SUPERVISOR_EXECUTED,
    VOS_SUPERVISOR_INVALID,
    VOS_SUPERVISOR_RETIRE_REFUSED,
    VOS_SUPERVISOR_REVOCATION_INCOMPLETE,
    VOS_SUPERVISOR_WAIT_REFUSED,
    VOS_SUPERVISOR_ACQUIRE_REFUSED,
    VOS_SUPERVISOR_SNAPSHOT_REFUSED,
    VOS_SUPERVISOR_START_REFUSED
};

struct vos_supervisor_execution {
    enum vos_supervisor_execution_status status;
    uint32_t stop_members;
    uint32_t delay;
    uint32_t started_members;
    uint32_t started_count;
    /* VOS_SUPERVISOR_UNITS when no start was refused. */
    uint32_t refused_unit;
};

/* Execute an explicitly selected initial bring-up (restart=0) or restart
 * (restart=1). The caller owns the policy/dwell/window/boot admission decision;
 * this function does not infer an action from independent detector predicates.
 * Input refusal invokes no effects. Later refusal preserves the acknowledged
 * prefix in out, performs no later effect except releasing a held lock, and
 * never retries or attempts rollback. The caller must consume this report
 * before choosing any recovery; repeating an initial bring-up is not recovery.
 * The manifest and callback table are copied before the first effect.
 */
enum vos_supervisor_execution_status vos_supervisor_execute(
    const struct vos_supervisor_manifest *manifest, uint32_t restart,
    uint32_t attempts, const struct vos_supervisor_effects *effects,
    void *context, struct vos_supervisor_execution *out);

#endif
