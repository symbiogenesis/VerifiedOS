// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_RESIDENT_READS_H
#define VOS_RESIDENT_READS_H

#include <stddef.h>
#include <stdint.h>

#define VOS_RESIDENT_BYTES 512U
#define VOS_RESIDENT_HOLDERS 2U
#define VOS_RESIDENT_SYSTEM 1U
#define VOS_RESIDENT_USER 2U
#define VOS_RESIDENT_COMMON 1U
#define VOS_RESIDENT_PRIVATE 2U
#define VOS_RESIDENT_RESPONSE 3U

struct vos_resident_identity {
    uint64_t owner, domain, object, version, generation;
    uint32_t kind;
    uint8_t root[32];
};

struct vos_resident_handle {
    struct vos_resident_identity identity;
    uint64_t boot, token;
    uint32_t holder;
    size_t start, length;
};

struct vos_resident_reservation {
    struct vos_resident_handle handle;
    uint64_t expires;
    uint32_t live;
};

struct vos_resident_common {
    struct vos_resident_identity identity;
    struct vos_resident_reservation reservation[VOS_RESIDENT_HOLDERS];
    uint8_t bytes[VOS_RESIDENT_BYTES];
    size_t length;
    uint64_t boot, generation, next_token, last_version, limit;
    uint32_t occupied, accepting, grants;
};

struct vos_resident_request {
    uint64_t sequence, token;
    size_t offset, length;
    uint32_t active;
};

/* The owner record is private to the serialized storage service. The observer
 * is a read-only external test hook, not an untrusted compartment callback.
 * It observes explicit owner/output stores, including same-value stores. */
typedef void (*vos_resident_observer)(void *opaque, uint32_t classification,
                                     const void *address, size_t bytes);
typedef int (*vos_resident_verifier)(void *opaque,
                                    const struct vos_resident_identity *identity,
                                    const uint8_t *bytes, size_t length);

struct vos_resident_owner {
    struct vos_resident_common common;
    struct vos_resident_request pending[VOS_RESIDENT_HOLDERS];
    uint64_t sequence[VOS_RESIDENT_HOLDERS];
    vos_resident_observer observe;
    void *observation;
};

int vos_resident_init(struct vos_resident_owner *owner, uint64_t boot,
                      uint64_t generation, uint64_t counter_limit,
                      vos_resident_observer observe, void *observation);
/* Publication copies bytes; caller aliases cannot mutate retained backing.
 * This first C shape refuses replacement while its one backing is occupied. */
int vos_resident_publish(struct vos_resident_owner *owner,
                         const struct vos_resident_identity *identity,
                         const uint8_t *bytes, size_t length);
int vos_resident_admit(struct vos_resident_owner *owner, uint32_t holder,
                       uint64_t domain, const struct vos_resident_identity *identity,
                       size_t start, size_t length, uint64_t now, uint64_t expires,
                       struct vos_resident_handle *handle);
int vos_resident_begin(struct vos_resident_owner *owner,
                       const struct vos_resident_handle *handle, uint64_t domain,
                       size_t offset, size_t length, uint64_t now,
                       uint64_t *sequence);
/* Only a matching completion may consume a pending request. The verifier sees
 * isolated stack snapshots and runs on every matching authorized completion,
 * including an empty read. Its soundness and external writes are separate
 * trusted seams. Refusal publishes no output or length. Output regions must
 * be mutually disjoint and outside the owner. */
int vos_resident_complete(struct vos_resident_owner *owner,
                          const struct vos_resident_handle *handle,
                          uint64_t domain, uint64_t sequence, uint64_t now,
                          vos_resident_verifier verify, void *verification,
                          uint8_t *output, size_t capacity, size_t *length);
void vos_resident_grants(struct vos_resident_owner *owner, uint32_t grants);
void vos_resident_generation(struct vos_resident_owner *owner, uint64_t generation);
/* Closes admission and cancels every finite holder/transfer without waiting.
 * An unavailable barrier quarantines the original bytes. A true barrier is an
 * explicit trusted seam: this adapter supplies no kernel sweep/reuse evidence. */
int vos_resident_retire(struct vos_resident_owner *owner, int barrier_completed);
int vos_resident_crash(struct vos_resident_owner *owner, uint64_t new_boot);

#endif
