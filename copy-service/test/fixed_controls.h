// SPDX-License-Identifier: Apache-2.0
/* Shared byte-level controls run unchanged by host and target producers. */
static int vos_copy_controls(vos_copy_ring *ring, uint8_t *source, uint8_t *destination)
{
    uint32_t i, j, request = 91, signal = 92, results[VOS_COPY_MAX_BATCH + 1];
    size_t length = 93;
    vos_copy_view view = {0, 0};
    vos_copy_slot slot = {VOS_COPY_TERMINAL, 1, 1, 7};
    vos_copy_request batch[VOS_COPY_MAX_BATCH];
    uint32_t signals[VOS_COPY_MAX_BATCH];
    vos_copy_init(ring);
    CHECK(!vos_copy_take(ring, destination, VOS_COPY_MAX_PAYLOAD + 2, &length, &request));
    CHECK(length == 93 && request == 91);
    for (i = 0; i < VOS_COPY_MAX_PAYLOAD + 1; ++i) source[i] = (uint8_t)(i * 17 + 3);
    for (i = 0; i < VOS_COPY_MAX_PAYLOAD + 2; ++i) destination[i] = 0xa5;
    CHECK(!vos_copy_stage(destination + 1, VOS_COPY_MAX_PAYLOAD, source, 0, 1));
    CHECK(destination[1] == 0xa5);
    CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION, 1, 0, NULL,
                            VOS_COPY_MAX_PAYLOAD + 1, VOS_COPY_MAX_PAYLOAD + 1, &signal));
    CHECK(signal == 92 && vos_copy_index_load(&ring->produced) == 0);
    CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION + 1, 1, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION, 1, VOS_COPY_OPERATION_COUNT,
                            source, 1, 1, &signal));
    CHECK(vos_copy_prepare_sleep(ring));
    CHECK(vos_copy_submit(ring, VOS_COPY_GENERATION, 1, 0, source,
                           VOS_COPY_MAX_PAYLOAD, VOS_COPY_MAX_PAYLOAD, &signal));
    CHECK(signal == 1 && vos_copy_word_load(&ring->armed) == 0);
    CHECK(!vos_copy_prepare_sleep(ring));
    CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION, 1, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_take(ring, destination, 0, &length, &request));
    CHECK(length == 93 && request == 91 && destination[1] == 0xa5);
    /* Change the external source after publication: only staged bytes survive. */
    for (i = 0; i < VOS_COPY_MAX_PAYLOAD + 1; ++i) source[i] = 0xff;
    CHECK(vos_copy_take(ring, destination + 1, VOS_COPY_MAX_PAYLOAD, &length, &request));
    CHECK(length == VOS_COPY_MAX_PAYLOAD && request == 1);
    CHECK(destination[0] == 0xa5 && destination[VOS_COPY_MAX_PAYLOAD + 1] == 0xa5);
    for (i = 0; i < VOS_COPY_MAX_PAYLOAD; ++i)
        CHECK(destination[i + 1] == (uint8_t)(i * 17 + 3));
    /* Every slot, full refusal, exact payload order, and repeated index wrap. */
    for (j = 0; j < 2 * VOS_COPY_INDEX_SPAN / VOS_COPY_CAPACITY + 1; ++j) {
        for (i = 0; i < VOS_COPY_CAPACITY; ++i) {
            source[0] = (uint8_t)i;
            CHECK(vos_copy_submit(ring, VOS_COPY_GENERATION, i, 0, source, 1, 1, &signal));
        }
        signal = 92;
        CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION, VOS_COPY_CAPACITY, 0,
                                NULL, 1, 1, &signal));
        CHECK(signal == 92);
        for (i = 0; i < VOS_COPY_CAPACITY; ++i) {
            CHECK(vos_copy_take(ring, destination, VOS_COPY_MAX_PAYLOAD + 2, &length, &request));
            CHECK(length == 1 && request == i && destination[0] == (uint8_t)i);
        }
    }
    CHECK(!vos_copy_advance(&slot, VOS_COPY_RECLAIM));
    CHECK(slot.state == VOS_COPY_TERMINAL && slot.readers == 1);
    slot.readers = 0;
    CHECK(vos_copy_advance(&slot, VOS_COPY_RECLAIM));
    view.produced = VOS_COPY_CAPACITY - 1;
    CHECK(vos_copy_batch(&view, VOS_COPY_MAX_BATCH, results));
    CHECK(results[0] == 1 && view.produced == VOS_COPY_CAPACITY);
    for (i = 1; i < VOS_COPY_MAX_BATCH; ++i) CHECK(results[i] == 0);
    results[0] = 99;
    CHECK(!vos_copy_batch(&view, VOS_COPY_MAX_BATCH + 1, results));
    CHECK(results[0] == 99 && view.produced == VOS_COPY_CAPACITY);
    view.produced = UINT32_MAX;
    CHECK(!vos_copy_publish(&view) && view.produced == UINT32_MAX);
    view.produced = 0; view.consumed = VOS_COPY_INDEX_SPAN;
    CHECK(!vos_copy_take_index(&view) && view.consumed == VOS_COPY_INDEX_SPAN);
    vos_copy_init(ring);
    for (i = 0; i < VOS_COPY_CAPACITY - 1; ++i)
        CHECK(vos_copy_submit(ring, VOS_COPY_GENERATION, i, 0, source, 1, 1, &signal));
    for (i = 0; i < VOS_COPY_MAX_BATCH; ++i) {
        batch[i].generation = VOS_COPY_GENERATION;
        batch[i].request = VOS_COPY_CAPACITY + i;
        batch[i].operation = 0; batch[i].source = source;
        batch[i].extent = 1; batch[i].length = 1;
    }
    results[0] = 99; signals[0] = 99;
    CHECK(!vos_copy_submit_batch(ring, NULL, VOS_COPY_MAX_BATCH + 1, results, signals));
    CHECK(results[0] == 99 && signals[0] == 99);
    CHECK(vos_copy_submit_batch(ring, batch, VOS_COPY_MAX_BATCH, results, signals));
    CHECK(results[0] == 1);
    for (i = 1; i < VOS_COPY_MAX_BATCH; ++i) CHECK(results[i] == 0 && signals[i] == 0);
    for (i = 0; i < VOS_COPY_CAPACITY; ++i)
        CHECK(vos_copy_take(ring, destination, VOS_COPY_MAX_PAYLOAD + 2, &length, &request));
    CHECK(request == VOS_COPY_CAPACITY);
    /* A malformed member cannot roll back a prior enqueue or stop later ones. */
    if (VOS_COPY_MAX_BATCH >= 3) {
        batch[1].length = 2;
        CHECK(vos_copy_submit_batch(ring, batch, 3, results, signals));
        CHECK(results[0] == 1 && results[1] == 0 && results[2] == 1);
        CHECK(vos_copy_take(ring, destination, VOS_COPY_MAX_PAYLOAD + 2, &length, &request));
        CHECK(request == batch[0].request);
        CHECK(vos_copy_take(ring, destination, VOS_COPY_MAX_PAYLOAD + 2, &length, &request));
        CHECK(request == batch[2].request);
    }
    for (i = 0; i < VOS_COPY_OPERATION_COUNT; ++i) {
        uint32_t limit = vos_copy_payload_limit(i);
        CHECK(vos_copy_submit(ring, VOS_COPY_GENERATION, i, i,
                               limit == 0 ? NULL : source, limit, limit, &signal));
        CHECK(vos_copy_take(ring, limit == 0 ? NULL : destination, limit, &length, &request));
        CHECK(length == limit && request == i);
        signal = 92;
        CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION, i, i, NULL, limit + 1, limit + 1, &signal));
        CHECK(signal == 92);
    }
    /* Force a live request window through the wire origin before checking IDs. */
    vos_copy_init(ring);
    vos_copy_index_store(&ring->produced, VOS_COPY_INDEX_SPAN - 1);
    vos_copy_index_store(&ring->consumed, VOS_COPY_INDEX_SPAN - 1);
    CHECK(vos_copy_submit(ring, VOS_COPY_GENERATION, 7, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION, 7, 0, source, 1, 1, &signal));
    CHECK(vos_copy_submit(ring, VOS_COPY_GENERATION, 8, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_submit(ring, VOS_COPY_GENERATION, 7, 0, source, 1, 1, &signal));
    CHECK(vos_copy_take(ring, destination, VOS_COPY_MAX_PAYLOAD + 2, &length, &request));
    CHECK(request == 7);
    CHECK(vos_copy_take(ring, destination, VOS_COPY_MAX_PAYLOAD + 2, &length, &request));
    CHECK(request == 8);
    return 0;
}
