// SPDX-License-Identifier: Apache-2.0
/* Rows carry the exact host answers checked against Gallina. No target verdict
 * is recomputed in Python. The driver binds rows, proof comparison and image. */
int vos_copy_target_rows(const uint32_t *rows, uint32_t count,
                         uint8_t *source, uint8_t *destination)
{
    uint32_t k, j, n, out[10], results[VOS_COPY_MAX_BATCH];
    vos_copy_view view, published, taken;
    vos_copy_slot slot;
    vos_copy_world world;
    for (j = 0; j <= VOS_COPY_MAX_PAYLOAD; ++j) source[j] = 7;
    for (k = 0; k < count; ++k) {
        const uint32_t *a = rows + k * 22u + 2u;
        const uint32_t *expected = rows + k * 22u + 12u;
        n = rows[k * 22u + 1u];
        if (n > 10u) return 1;
        for (j = 0; j < 10u; ++j) out[j] = 0;
        if (a[0] == 0u) {
            view.produced = a[1] % VOS_COPY_INDEX_SPAN;
            view.consumed = a[2] % VOS_COPY_INDEX_SPAN;
            published = view; taken = view;
            out[6] = vos_copy_publish(&published);
            out[5] = vos_copy_take_index(&taken);
            out[0] = vos_copy_occupancy(&view);
            out[1] = view.produced; out[2] = view.consumed;
            out[3] = a[1] % VOS_COPY_CAPACITY;
            out[4] = published.produced; out[7] = taken.consumed;
        } else if (a[0] == 1u) {
            view.produced = a[1] % VOS_COPY_INDEX_SPAN;
            view.consumed = a[2] % VOS_COPY_INDEX_SPAN;
            if (a[3] > VOS_COPY_MAX_BATCH || a[3] + 1u != n) return 2;
            if (!vos_copy_batch(&view, a[3], results)) return 3;
            out[0] = view.produced;
            for (j = 0; j < a[3]; ++j) out[j + 1u] = results[j];
        } else if (a[0] == 2u) {
            slot.state = (vos_copy_state)a[2]; slot.readers = a[3];
            slot.validated = a[4]; slot.request = 7;
            if (vos_copy_advance(&slot, (vos_copy_event)a[1])) out[0] = slot.state + 1u;
        } else if (a[0] == 3u) {
            if (a[1] > VOS_COPY_MAX_PAYLOAD || a[2] > VOS_COPY_MAX_PAYLOAD + 1u) return 4;
            if (vos_copy_stage(destination, a[1], source, a[1], a[2])) out[0] = a[2] + 1u;
        } else if (a[0] == 4u) {
            world.view.produced = a[3] % VOS_COPY_INDEX_SPAN;
            world.view.consumed = a[4] % VOS_COPY_INDEX_SPAN;
            world.armed = a[5]; world.signals = 0;
            world.seen = a[6] % VOS_COPY_INDEX_SPAN;
            world.drained = a[7]; world.asleep = a[9];
            vos_copy_activation(&world, (vos_copy_reset)a[1], a[2], a[8]);
            out[0] = world.view.produced; out[1] = world.view.consumed;
            out[2] = world.armed; out[3] = world.signals; out[4] = world.seen;
            out[5] = world.drained; out[6] = world.asleep;
        } else return 5;
        for (j = 0; j < n; ++j) if (out[j] != expected[j]) return 6;
    }
    return count == 0u;
}
