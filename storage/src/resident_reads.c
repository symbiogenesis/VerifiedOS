// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_reads.h"

#include <string.h>

static void stored(struct vos_resident_owner *o, uint32_t kind,
                   const void *address, size_t length)
{
    if (o->observe != 0) o->observe(o->observation, kind, address, length);
}

#define PUT(o, kind, cell, value) do { \
    stored((o), (kind), &(cell), sizeof(cell)); (cell) = (value); \
} while (0)

static int overlap(const void *a, size_t alen, const void *b, size_t blen)
{
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return alen != 0 && blen != 0 &&
           (x <= y ? y - x < alen : x - y < blen);
}

static int external(const struct vos_resident_owner *o, const void *p, size_t n)
{
    return (n == 0 || p != 0) && !overlap(o, sizeof(*o), p, n);
}

static int identity_ok(const struct vos_resident_identity *i)
{
    return i != 0 && (i->kind == VOS_RESIDENT_SYSTEM || i->kind == VOS_RESIDENT_USER)
           && i->version != 0;
}

static int identity_equal(const struct vos_resident_identity *a,
                          const struct vos_resident_identity *b)
{
    return a->owner == b->owner && a->domain == b->domain &&
           a->object == b->object && a->version == b->version &&
           a->kind == b->kind && a->generation == b->generation &&
           memcmp(a->root, b->root, sizeof(a->root)) == 0;
}

static int handle_equal(const struct vos_resident_handle *a,
                        const struct vos_resident_handle *b)
{
    return a->boot == b->boot && a->token == b->token &&
           a->holder == b->holder && a->start == b->start && a->length == b->length &&
           identity_equal(&a->identity, &b->identity);
}

static int authority(const struct vos_resident_owner *o,
                     const struct vos_resident_handle *h,
                     uint64_t domain, uint64_t now)
{
    const struct vos_resident_common *c = &o->common;
    if (h == 0 || h->holder >= VOS_RESIDENT_HOLDERS || !c->occupied || !c->accepting ||
        domain != c->identity.domain || h->boot != c->boot ||
        (c->grants & (1U << h->holder)) == 0 ||
        !identity_equal(&h->identity, &c->identity) ||
        (c->identity.kind == VOS_RESIDENT_SYSTEM &&
         c->identity.generation != c->generation)) return 0;
    const struct vos_resident_reservation *r = &c->reservation[h->holder];
    return r->live && now < r->expires && handle_equal(h, &r->handle);
}

int vos_resident_init(struct vos_resident_owner *o, uint64_t boot,
                      uint64_t generation, uint64_t limit,
                      vos_resident_observer observe, void *observation)
{
    if (o == 0 || limit == 0 || boot > limit || generation > limit) return 0;
    memset(o, 0, sizeof(*o));
    o->common.boot = boot; o->common.generation = generation;
    o->common.limit = limit; o->common.grants = (1U << VOS_RESIDENT_HOLDERS) - 1U;
    o->observe = observe; o->observation = observation;
    return 1;
}

int vos_resident_publish(struct vos_resident_owner *o,
                         const struct vos_resident_identity *identity,
                         const uint8_t *bytes, size_t length)
{
    if (o == 0 || !identity_ok(identity) || o->common.occupied ||
        length > VOS_RESIDENT_BYTES || (length != 0 && bytes == 0) ||
        identity->version <= o->common.last_version ||
        identity->version > o->common.limit ||
        (identity->kind == VOS_RESIDENT_SYSTEM &&
         identity->generation != o->common.generation)) return 0;
    const struct vos_resident_identity id = *identity;
    for (size_t i = 0; i < length; ++i)
        PUT(o, VOS_RESIDENT_COMMON, o->common.bytes[i], bytes[i]);
    PUT(o, VOS_RESIDENT_COMMON, o->common.identity, id);
    PUT(o, VOS_RESIDENT_COMMON, o->common.length, length);
    PUT(o, VOS_RESIDENT_COMMON, o->common.last_version, id.version);
    PUT(o, VOS_RESIDENT_COMMON, o->common.occupied, 1U);
    PUT(o, VOS_RESIDENT_COMMON, o->common.accepting, 1U);
    return 1;
}

int vos_resident_admit(struct vos_resident_owner *o, uint32_t holder,
                       uint64_t domain, const struct vos_resident_identity *identity,
                       size_t start, size_t length, uint64_t now, uint64_t expires,
                       struct vos_resident_handle *output)
{
    struct vos_resident_handle h;
    if (o == 0 || holder >= VOS_RESIDENT_HOLDERS || output == 0 ||
        !external(o, output, sizeof(*output)) || !identity_ok(identity)) return 0;
    struct vos_resident_common *c = &o->common;
    if (!c->occupied || !c->accepting || c->reservation[holder].live ||
        (c->grants & (1U << holder)) == 0 || domain != c->identity.domain ||
        !identity_equal(identity, &c->identity) ||
        (identity->kind == VOS_RESIDENT_SYSTEM && identity->generation != c->generation) ||
        start > c->length || length > c->length - start ||
        expires <= now || expires > c->limit || c->next_token >= c->limit) return 0;
    memset(&h, 0, sizeof(h));
    h.identity = *identity; h.boot = c->boot; h.token = c->next_token + 1;
    h.holder = holder; h.start = start; h.length = length;
    PUT(o, VOS_RESIDENT_COMMON, c->next_token, h.token);
    PUT(o, VOS_RESIDENT_COMMON, c->reservation[holder].handle, h);
    PUT(o, VOS_RESIDENT_COMMON, c->reservation[holder].expires, expires);
    PUT(o, VOS_RESIDENT_COMMON, c->reservation[holder].live, 1U);
    PUT(o, VOS_RESIDENT_RESPONSE, *output, h);
    return 1;
}

int vos_resident_begin(struct vos_resident_owner *o,
                       const struct vos_resident_handle *h, uint64_t domain,
                       size_t offset, size_t length, uint64_t now,
                       uint64_t *sequence)
{
    if (o == 0 || sequence == 0 || !external(o, sequence, sizeof(*sequence)) ||
        !authority(o, h, domain, now) || offset > h->length ||
        length > h->length - offset) return 0;
    const uint32_t holder = h->holder;
    if (o->pending[holder].active || o->sequence[holder] >= o->common.limit) return 0;
    struct vos_resident_request r;
    memset(&r, 0, sizeof(r));
    r.active = 1; r.sequence = o->sequence[holder] + 1; r.token = h->token;
    r.offset = h->start + offset; r.length = length;
    /* BEGIN_TRAFFIC: all persistent read stores are holder-private or output. */
    PUT(o, VOS_RESIDENT_PRIVATE, o->sequence[holder], r.sequence);
    PUT(o, VOS_RESIDENT_PRIVATE, o->pending[holder], r);
    PUT(o, VOS_RESIDENT_RESPONSE, *sequence, r.sequence);
    return 1;
}

int vos_resident_complete(struct vos_resident_owner *o,
                          const struct vos_resident_handle *h,
                          uint64_t domain, uint64_t sequence, uint64_t now,
                          vos_resident_verifier verify, void *verification,
                          uint8_t *output, size_t capacity, size_t *length)
{
    struct vos_resident_common before;
    uint8_t snapshot[VOS_RESIDENT_BYTES];
    if (o == 0 || h == 0 || h->holder >= VOS_RESIDENT_HOLDERS || length == 0 ||
        !external(o, length, sizeof(*length))) return 0;
    const uint32_t holder = h->holder;
    const struct vos_resident_request r = o->pending[holder];
    if (!r.active || r.sequence != sequence || r.token != h->token ||
        !handle_equal(h, &o->common.reservation[holder].handle)) return 0;
    if (capacity < r.length || !external(o, output, r.length) ||
        overlap(output, r.length, length, sizeof(*length))) return 0;
    if (!authority(o, h, domain, now) || verify == 0) return 0;
    const struct vos_resident_identity id = o->common.identity;
    const size_t resident_length = o->common.length;
    memcpy(&before, &o->common, sizeof(before));
    for (size_t i = 0; i < resident_length; ++i) snapshot[i] = o->common.bytes[i];
    if (!verify(verification, &id, snapshot, resident_length)) return 0;
    /* The callback receives no owner alias. Recheck current state after it;
     * arbitrary external writes through opaque remain outside this observer. */
    if (!authority(o, h, domain, now) ||
        o->pending[holder].active != r.active ||
        o->pending[holder].sequence != r.sequence ||
        o->pending[holder].token != r.token ||
        o->pending[holder].offset != r.offset ||
        o->pending[holder].length != r.length ||
        memcmp(&o->common, &before, sizeof(before)) != 0 ||
        memcmp(o->common.bytes, snapshot, resident_length) != 0) return 0;
    for (size_t i = 0; i < r.length; ++i)
        PUT(o, VOS_RESIDENT_RESPONSE, output[i], snapshot[r.offset + i]);
    PUT(o, VOS_RESIDENT_RESPONSE, *length, r.length);
    PUT(o, VOS_RESIDENT_PRIVATE, o->pending[holder].active, 0U);
    return 1;
}

void vos_resident_grants(struct vos_resident_owner *o, uint32_t grants)
{
    if (o != 0 && grants < (1U << VOS_RESIDENT_HOLDERS))
        PUT(o, VOS_RESIDENT_COMMON, o->common.grants, grants);
}

void vos_resident_generation(struct vos_resident_owner *o, uint64_t generation)
{
    if (o != 0 && generation > o->common.generation && generation <= o->common.limit)
        PUT(o, VOS_RESIDENT_COMMON, o->common.generation, generation);
}

int vos_resident_retire(struct vos_resident_owner *o, int barrier_completed)
{
    if (o == 0 || !o->common.occupied) return 0;
    PUT(o, VOS_RESIDENT_COMMON, o->common.accepting, 0U);
    for (uint32_t holder = 0; holder < VOS_RESIDENT_HOLDERS; ++holder) {
        PUT(o, VOS_RESIDENT_PRIVATE, o->pending[holder].active, 0U);
        PUT(o, VOS_RESIDENT_COMMON, o->common.reservation[holder].live, 0U);
    }
    if (barrier_completed != 1) return 0;
    for (size_t i = 0; i < o->common.length; ++i)
        PUT(o, VOS_RESIDENT_COMMON, o->common.bytes[i], 0U);
    PUT(o, VOS_RESIDENT_COMMON, o->common.occupied, 0U);
    return 1;
}

int vos_resident_crash(struct vos_resident_owner *o, uint64_t new_boot)
{
    if (o == 0 || new_boot <= o->common.boot || new_boot > o->common.limit) return 0;
    PUT(o, VOS_RESIDENT_COMMON, o->common.accepting, 0U);
    PUT(o, VOS_RESIDENT_COMMON, o->common.grants, 0U);
    PUT(o, VOS_RESIDENT_COMMON, o->common.boot, new_boot);
    for (uint32_t holder = 0; holder < VOS_RESIDENT_HOLDERS; ++holder) {
        PUT(o, VOS_RESIDENT_COMMON, o->common.reservation[holder].live, 0U);
        PUT(o, VOS_RESIDENT_PRIVATE, o->pending[holder].active, 0U);
    }
    return 1;
}
