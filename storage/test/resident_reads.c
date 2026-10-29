// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_reads.h"
#include "vos_node_image.h"

#include <stdio.h>
#include <string.h>

#define REQUIRE(condition, name) do { if (!(condition)) { \
    fprintf(stderr, "resident refusal: %s at %d\n", name, __LINE__); return 1; \
} } while (0)

struct observation {
    struct vos_resident_owner *owner;
    uint64_t common, private_writes, output, bytes;
    uint32_t read, bad_class, premature_zero;
};

struct authentication {
    struct vos_resident_identity expected;
    uint8_t bytes[VOS_RESIDENT_BYTES];
    size_t length;
    uint32_t calls, mutate;
    struct vos_resident_owner *owner;
};

static int contains(const void *base, size_t size, const void *address, size_t count)
{
    uintptr_t a = (uintptr_t)address, b = (uintptr_t)base;
    return a >= b && a - b <= size && count <= size - (a - b);
}

static void observe(void *opaque, uint32_t kind, const void *address, size_t bytes)
{
    struct observation *v = opaque;
    struct vos_resident_owner *o = v->owner;
    uint32_t expected = VOS_RESIDENT_RESPONSE, holder;
    if (contains(&o->common, sizeof(o->common), address, bytes))
        expected = VOS_RESIDENT_COMMON;
    else if (contains(o->pending, sizeof(o->pending), address, bytes) ||
             contains(o->sequence, sizeof(o->sequence), address, bytes))
        expected = VOS_RESIDENT_PRIVATE;
    if (kind != expected) v->bad_class = 1;
    if (v->read) {
        if (expected == VOS_RESIDENT_COMMON) ++v->common;
        else if (expected == VOS_RESIDENT_PRIVATE) ++v->private_writes;
        else ++v->output;
        v->bytes += bytes;
    }
    if (contains(o->common.bytes, sizeof(o->common.bytes), address, bytes)) {
        for (holder = 0; holder < VOS_RESIDENT_HOLDERS; ++holder)
            if (o->pending[holder].active || o->common.reservation[holder].live)
                v->premature_zero = 1;
    }
}

static int authenticate(void *opaque, const struct vos_resident_identity *id,
                        const uint8_t *bytes, size_t length)
{
    struct authentication *a = opaque;
    ++a->calls;
    if (a->mutate) a->owner->common.grants ^= 1U;
    return length == a->length && id->kind == a->expected.kind &&
           id->generation == a->expected.generation &&
           memcmp(id->root, a->expected.root, 32) == 0 &&
           memcmp(bytes, a->bytes, length) == 0;
}

static void fixture(struct vos_resident_owner *o, struct observation *v,
                    struct authentication *a, uint32_t kind, uint64_t limit)
{
    size_t i;
    memset(v, 0, sizeof(*v)); memset(a, 0, sizeof(*a));
    v->owner = o; a->owner = o;
    a->expected.owner = 7; a->expected.domain = 11; a->expected.object = 19;
    a->expected.version = 1; a->expected.generation = 1; a->expected.kind = kind;
    for (i = 0; i < 32; ++i) a->expected.root[i] = (uint8_t)(i + 31);
    a->length = 64;
    for (i = 0; i < a->length; ++i) a->bytes[i] = (uint8_t)(3 * i + 1);
    (void)vos_resident_init(o, 1, 1, limit, observe, v);
}

static int exercise(uint32_t kind, uint32_t repetitions)
{
    struct vos_resident_owner o;
    struct observation v;
    struct authentication a;
    struct vos_resident_handle h[2], bad;
    struct vos_resident_common common;
    uint8_t output[64], source[64];
    uint64_t seq[2], old;
    size_t length;
    uint32_t n, holder, before_auth;
    fixture(&o, &v, &a, kind, 15);
    memcpy(source, a.bytes, sizeof(source));
    REQUIRE(vos_resident_publish(&o, &a.expected, source, sizeof(source)), "publish");
    source[0] ^= 1;
    REQUIRE(o.common.bytes[0] == a.bytes[0], "backing owns bytes");
    REQUIRE(vos_resident_admit(&o, 0, 11, &a.expected, 4, 17, 0, 12, &h[0]), "holder zero");
    REQUIRE(vos_resident_admit(&o, 1, 11, &a.expected, 15, 9, 0, 12, &h[1]), "holder one");
    memcpy(&common, &o.common, sizeof(common));
    v.read = 1;
    for (n = 0; n < repetitions; ++n) {
        for (holder = 0; holder < 2; ++holder) {
            length = 999;
            REQUIRE(vos_resident_begin(&o, &h[holder], 11, 0, h[holder].length, 1,
                                       &seq[holder]), "repeat begin");
            REQUIRE(vos_resident_complete(&o, &h[holder], 11, seq[holder], 1,
                                          authenticate, &a, output, sizeof(output), &length),
                    "repeat completion");
            REQUIRE(length == h[holder].length &&
                    memcmp(output, a.bytes + h[holder].start, length) == 0, "independent bytes");
        }
    }
    REQUIRE(a.calls == 2 * repetitions, "every-read verifier");
    REQUIRE(memcmp(&common, &o.common, sizeof(common)) == 0, "common state frame");
    REQUIRE(v.common == 0 && !v.bad_class && v.private_writes != 0 && v.output != 0,
            "classified traffic");
    /* Two concurrent pending transfers; refusals preserve the accepted requests. */
    REQUIRE(vos_resident_begin(&o, &h[0], 11, 1, 3, 1, &seq[0]), "first pending");
    REQUIRE(vos_resident_begin(&o, &h[1], 11, 9, 0, 1, &seq[1]), "empty pending");
    old = seq[0]; bad = h[0]; bad.identity.root[0] ^= 1;
    length = 999; before_auth = a.calls;
    REQUIRE(!vos_resident_complete(&o, &bad, 11, seq[0], 1, authenticate, &a,
                                   output, sizeof(output), &length), "wrong root");
    REQUIRE(!vos_resident_complete(&o, &h[0], 12, seq[0], 1, authenticate, &a,
                                   output, sizeof(output), &length), "wrong domain");
    REQUIRE(a.calls == before_auth && length == 999 && o.pending[0].active,
            "identity refusal preserves transfer");
    REQUIRE(!vos_resident_complete(&o, &h[0], 11, seq[0], 1, authenticate, &a,
                                   o.common.bytes, 64, &length), "output cannot alias common");
    REQUIRE(!vos_resident_begin(&o, &h[0], 11, 18, 0, 1, &seq[0]), "out of window");
    REQUIRE(vos_resident_complete(&o, &h[0], 11, old, 1, authenticate, &a,
                                  output, sizeof(output), &length), "finish first");
    REQUIRE(vos_resident_complete(&o, &h[1], 11, seq[1], 1, authenticate, &a,
                                  0, 0, &length) && length == 0, "empty boundary bytes");
    REQUIRE(vos_resident_begin(&o, &h[0], 11, 2, 4, 1, &seq[0]), "successor pending");
    length = 999;
    REQUIRE(!vos_resident_complete(&o, &h[0], 11, old, 1, authenticate, &a,
                                   output, sizeof(output), &length) && length == 999 &&
            o.pending[0].active && o.pending[0].sequence == seq[0], "stale completion");
    o.common.bytes[7] ^= 1; /* Explicit fixture corruption, outside observed owner work. */
    REQUIRE(!vos_resident_complete(&o, &h[0], 11, seq[0], 1, authenticate, &a,
                                   output, sizeof(output), &length) && length == 999,
            "actual-byte authentication");
    o.common.bytes[7] ^= 1;
    a.mutate = 1;
    REQUIRE(!vos_resident_complete(&o, &h[0], 11, seq[0], 1, authenticate, &a,
                                   output, sizeof(output), &length) && length == 999,
            "callback common drift refuses payload");
    a.mutate = 0;
    v.read = 0;
    vos_resident_grants(&o, 3);
    v.read = 1;
    REQUIRE(vos_resident_complete(&o, &h[0], 11, seq[0], 1, authenticate, &a,
                                  output, sizeof(output), &length), "canonical retry");
    v.read = 0;
    REQUIRE(vos_resident_begin(&o, &h[0], 11, 0, 1, 1, &seq[0]), "revocation pending");
    vos_resident_grants(&o, 2);
    length = 999;
    REQUIRE(!vos_resident_complete(&o, &h[0], 11, seq[0], 1, authenticate, &a,
                                   output, sizeof(output), &length), "revoked completion");
    vos_resident_grants(&o, 3);
    if (kind == VOS_RESIDENT_SYSTEM) {
        vos_resident_generation(&o, 2);
        REQUIRE(!vos_resident_complete(&o, &h[0], 11, seq[0], 1, authenticate, &a,
                                       output, sizeof(output), &length), "generation refusal");
    }
    REQUIRE(!vos_resident_retire(&o, 0), "unavailable barrier");
    REQUIRE(o.common.occupied && !o.common.accepting && !o.pending[0].active &&
            !o.pending[1].active && !o.common.reservation[0].live &&
            !o.common.reservation[1].live &&
            memcmp(o.common.bytes, a.bytes, a.length) == 0, "quarantined unchanged backing");
    REQUIRE(!vos_resident_publish(&o, &a.expected, a.bytes, a.length), "live replacement refuses");
    REQUIRE(vos_resident_retire(&o, 1), "completed barrier");
    REQUIRE(!v.premature_zero, "cancel before backing writes");
    for (n = 0; n < a.length; ++n) REQUIRE(o.common.bytes[n] == 0, "retired bytes zero");
    a.expected.version = 2; a.expected.generation = o.common.generation;
    REQUIRE(vos_resident_publish(&o, &a.expected, a.bytes, a.length), "new version");
    REQUIRE(!vos_resident_begin(&o, &h[0], 11, 0, 1, 1, &seq[0]), "old handle after reuse");
    REQUIRE(vos_resident_admit(&o, 0, 11, &a.expected, 0, 64, 1, 12, &h[0]), "readmit");
    REQUIRE(vos_resident_begin(&o, &h[0], 11, 0, 1, 1, &seq[0]) && seq[0] > old,
            "sequence survives backing reuse");
    REQUIRE(vos_resident_crash(&o, 2), "crash");
    REQUIRE(!vos_resident_begin(&o, &h[0], 11, 0, 1, 1, &old) &&
            !o.pending[0].active && o.sequence[0] == seq[0], "crash keeps exhausted identity");
    return 0;
}

static int exhaustion(void)
{
    struct vos_resident_owner o;
    struct observation v;
    struct authentication a;
    struct vos_resident_handle h;
    uint8_t output[64];
    size_t length;
    uint64_t sequence;
    uint32_t n;
    memset(&o, 0x5a, sizeof(o));
    {
        struct vos_resident_owner original;
        memcpy(&original, &o, sizeof(o));
        REQUIRE(!vos_resident_init(&o, 4, 1, 3, observe, &v) &&
                memcmp(&original, &o, sizeof(o)) == 0, "initial boot bound");
        REQUIRE(!vos_resident_init(&o, 1, 4, 3, observe, &v) &&
                memcmp(&original, &o, sizeof(o)) == 0, "initial generation bound");
        REQUIRE(vos_resident_init(&o, 3, 3, 3, observe, &v), "initial exact counter bound");
    }
    fixture(&o, &v, &a, VOS_RESIDENT_USER, 3);
    REQUIRE(vos_resident_publish(&o, &a.expected, a.bytes, a.length), "bounded publish");
    REQUIRE(vos_resident_admit(&o, 0, 11, &a.expected, 0, 64, 0, 3, &h), "bounded admit");
    for (n = 0; n < 3; ++n) {
        REQUIRE(vos_resident_begin(&o, &h, 11, 0, 1, 1, &sequence), "finite request");
        REQUIRE(vos_resident_complete(&o, &h, 11, sequence, 1, authenticate, &a,
                                      output, sizeof(output), &length), "finite completion");
    }
    REQUIRE(!vos_resident_begin(&o, &h, 11, 0, 1, 1, &sequence) && o.sequence[0] == 3,
            "counter exhaustion");
    REQUIRE(!vos_resident_begin(&o, &h, 11, 0, 1, 3, &sequence), "expiry");
    return 0;
}

static int node_image_join(uint32_t kind)
{
    struct vos_resident_owner o;
    struct observation v;
    struct authentication a;
    struct vos_resident_handle h[2];
    struct vos_node_geometry geometry = {4, 8, 96};
    struct vos_node node, decoded;
    uint8_t produced[96], returned[96];
    uint64_t seq[2];
    size_t length;
    uint32_t holder;
    fixture(&o, &v, &a, kind, 15);
    memset(&node, 0, sizeof(node));
    node.kind = VOS_NODE_LEAF; node.count = 2; node.node_id = 2; node.generation = 1;
    node.keys[0] = 3; node.values[0] = 100; node.keys[1] = 9; node.values[1] = 200;
    /* Independent canonical image; no expected byte is read from the encoder. */
    memset(a.bytes, 0, sizeof(a.bytes));
    memcpy(a.bytes, "VOSNODE1", 8);
    a.bytes[12] = 2; a.bytes[16] = 2; a.bytes[24] = 1;
    a.bytes[32] = 3; a.bytes[40] = 100; a.bytes[48] = 9; a.bytes[56] = 200;
    a.length = sizeof(produced);
    REQUIRE(vos_node_encode(&geometry, &node, produced, sizeof(produced)), "actual node encode");
    REQUIRE(memcmp(produced, a.bytes, sizeof(produced)) == 0, "independent node image");
    REQUIRE(vos_resident_publish(&o, &a.expected, produced, sizeof(produced)), "publish node image");
    REQUIRE(vos_resident_admit(&o, 0, 11, &a.expected, 32, 16, 0, 12, &h[0]), "node entry holder");
    REQUIRE(vos_resident_admit(&o, 1, 11, &a.expected, 0, 96, 0, 12, &h[1]), "node image holder");
    v.read = 1;
    for (holder = 0; holder < 2; ++holder) {
        REQUIRE(vos_resident_begin(&o, &h[holder], 11, 0, h[holder].length, 1,
                                   &seq[holder]), "node transfer");
        REQUIRE(vos_resident_complete(&o, &h[holder], 11, seq[holder], 1,
                                      authenticate, &a, returned, sizeof(returned), &length),
                "complete actual node transfer");
        REQUIRE(length == h[holder].length &&
                memcmp(returned, a.bytes + h[holder].start, length) == 0,
                "independent returned node bytes");
    }
    REQUIRE(vos_node_decode(&geometry, 2, 1, returned, length, &decoded) &&
            decoded.count == 2 && decoded.keys[0] == 3 && decoded.keys[1] == 9 &&
            decoded.values[0] == 100 && decoded.values[1] == 200,
            "decode actual resident response");
    REQUIRE(a.calls == 2 && v.common == 0 && !v.bad_class, "node join traffic and verification");
    return 0;
}

int main(void)
{
    uint32_t kind, repeats;
    for (kind = VOS_RESIDENT_SYSTEM; kind <= VOS_RESIDENT_USER; ++kind)
        for (repeats = 1; repeats <= 4; ++repeats)
            if (exercise(kind, repeats)) return 1;
    for (kind = VOS_RESIDENT_SYSTEM; kind <= VOS_RESIDENT_USER; ++kind)
        if (node_image_join(kind)) return 1;
    if (exhaustion()) return 1;
    fprintf(stderr, "ok resident C payload, lifetime and stored-write controls\n");
    return 0;
}
