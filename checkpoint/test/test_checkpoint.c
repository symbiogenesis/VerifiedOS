// SPDX-License-Identifier: Apache-2.0
#include "vos_checkpoint.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                     \
    do {                                                                     \
        if (!(cond)) {                                                       \
            fprintf(stderr, "checkpoint_test FAILED (%s:%d): %s\n",          \
                    __FILE__, __LINE__, (msg));                              \
            return 1;                                                        \
        }                                                                    \
    } while (0)

static void init_keys(uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                      uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256])
{
    for (uint32_t i = 0u; i < VOS_CRYPTO_DIGEST_BYTES; ++i) {
        auth_key[i] = (uint8_t)(0x30u + i);
        master_key[i] = (uint8_t)(0x70u + i);
    }
}

static int test_wire_format_and_rejections(void)
{
    uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256];
    init_keys(auth_key, master_key);

    struct vos_cp_editor_doc doc;
    vos_cp_editor_doc_init(&doc);
    CHECK(vos_cp_editor_apply_insert(&doc, 0u, 'H') == VOS_CP_OK, "insert H");
    CHECK(vos_cp_editor_apply_insert(&doc, 1u, 'i') == VOS_CP_OK, "insert i");

    struct vos_cp_meta meta = {
        .app_id = VOS_CP_APP_EDITOR,
        .payload_kind = VOS_CP_PAYLOAD_SEMANTIC,
        .schema_version = VOS_CP_SCHEMA_VERSION,
        .generation = 7u,
        .confidentiality_label = 0x11u,
        .security_critical = 0u,
        .fresh_epoch = 0u,
        .forbidden_flags = 0u
    };
    uint8_t wire[VOS_CP_MAX_WIRE_BYTES];
    size_t wire_len = 0u;
    CHECK(vos_cp_encode_editor(&meta, &doc, auth_key, wire, sizeof(wire), &wire_len) == VOS_CP_OK,
          "encode editor semantic");

    struct vos_cp_meta dec_meta;
    struct vos_cp_editor_doc dec_doc;
    CHECK(vos_cp_decode_editor(wire, wire_len, auth_key, 0x11u, &dec_meta, &dec_doc) == VOS_CP_OK,
          "decode valid semantic");
    CHECK(dec_doc.text_len == 2u && dec_doc.cursor == 2u && dec_doc.undo_count == 2u,
          "decoded editor fields match");
    CHECK(dec_doc.text[0] == 'H' && dec_doc.text[1] == 'i', "decoded text matches");

    /* Trailing bytes rejected */
    uint8_t wire_extra[VOS_CP_MAX_WIRE_BYTES];
    memcpy(wire_extra, wire, wire_len);
    if (wire_len < sizeof(wire_extra)) {
        wire_extra[wire_len] = 0xAAu;
        CHECK(vos_cp_decode_editor(wire_extra, wire_len + 1u, auth_key, 0x11u,
                                   &dec_meta, &dec_doc) == VOS_CP_ERR_TRAILING_BYTES,
              "trailing bytes rejected");
    }

    /* Tampered payload rejected by HMAC tag check */
    uint8_t wire_tamper[VOS_CP_MAX_WIRE_BYTES];
    memcpy(wire_tamper, wire, wire_len);
    wire_tamper[VOS_CP_WIRE_HEADER_BYTES + 16u] ^= 0x01u;
    CHECK(vos_cp_decode_editor(wire_tamper, wire_len, auth_key, 0x11u,
                               &dec_meta, &dec_doc) == VOS_CP_ERR_AUTH_FAILED,
          "tampered HMAC rejected");

    /* Non-semantic / raw-heap / tagged payload rejected on encode and decode */
    struct vos_cp_meta raw_meta = meta;
    raw_meta.payload_kind = VOS_CP_PAYLOAD_RAW_HEAP;
    size_t bad_len = 0u;
    CHECK(vos_cp_encode_editor(&raw_meta, &doc, auth_key, wire, sizeof(wire), &bad_len) ==
          VOS_CP_ERR_NON_SEMANTIC,
          "reject raw heap encode");

    struct vos_cp_meta tagged_meta = meta;
    tagged_meta.forbidden_flags = VOS_CP_FORBID_TAGGED_CAPS;
    CHECK(vos_cp_encode_editor(&tagged_meta, &doc, auth_key, wire, sizeof(wire), &bad_len) ==
          VOS_CP_ERR_FORBIDDEN_AUTHORITY,
          "reject tagged capability encode");

    /* Decoder independently rejects non-semantic and tagged-cap wires even with valid HMAC */
    uint8_t crafted[VOS_CP_MAX_WIRE_BYTES];
    memcpy(crafted, wire, wire_len);
    crafted[16] = (uint8_t)VOS_CP_PAYLOAD_RAW_HEAP;
    crafted[17] = 0u;
    crafted[18] = 0u;
    crafted[19] = 0u;
    CHECK(vos_hmac_sha256(auth_key, VOS_CRYPTO_DIGEST_BYTES, crafted,
                          wire_len - VOS_CRYPTO_DIGEST_BYTES,
                          crafted + wire_len - VOS_CRYPTO_DIGEST_BYTES),
          "re-sign crafted raw heap wire");
    CHECK(vos_cp_decode_editor(crafted, wire_len, auth_key, 0x11u, &dec_meta, &dec_doc) ==
          VOS_CP_ERR_NON_SEMANTIC,
          "decoder rejects raw heap payload");

    memcpy(crafted, wire, wire_len);
    crafted[48] = (uint8_t)VOS_CP_FORBID_TAGGED_CAPS;
    CHECK(vos_hmac_sha256(auth_key, VOS_CRYPTO_DIGEST_BYTES, crafted,
                          wire_len - VOS_CRYPTO_DIGEST_BYTES,
                          crafted + wire_len - VOS_CRYPTO_DIGEST_BYTES),
          "re-sign crafted tagged wire");
    CHECK(vos_cp_decode_editor(crafted, wire_len, auth_key, 0x11u, &dec_meta, &dec_doc) ==
          VOS_CP_ERR_FORBIDDEN_AUTHORITY,
          "decoder rejects tagged capability flags");

    return 0;
}

static int test_slate_exchange_and_barrier_refusals(void)
{
    uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256];
    init_keys(auth_key, master_key);

    struct vos_cp_engine eng;
    CHECK(vos_cp_engine_init(&eng, auth_key, master_key,
                             VOS_CP_DEFAULT_SPACE_LIMIT, 8u, 0x22u) == VOS_CP_OK,
          "engine init");

    CHECK(vos_cp_editor_apply_insert(&eng.editor_doc, 0u, 'A') == VOS_CP_OK, "edit A");
    CHECK(vos_cp_editor_apply_insert(&eng.editor_doc, 1u, 'B') == VOS_CP_OK, "edit B");
    CHECK(vos_cp_exclusive_slate(&eng), "exclusive initially");

    const struct vos_cp_roots cleared = vos_cp_roots_cleared();
    CHECK(vos_cp_switch_with_cut(&eng, VOS_CP_APP_PAINTER, &cleared,
                                 VOS_CP_GRANT_VALID, 0u, VOS_CP_CUT_NONE) == VOS_CP_OK,
          "editor -> painter switch");
    CHECK(eng.selected_app == VOS_CP_APP_PAINTER &&
          eng.apps[1].owns_slate == 1u && eng.apps[0].owns_slate == 0u &&
          eng.apps[1].session_authority == 0u,
          "painter holds slate exclusively with zero restored session");

    uint8_t tile_digest[VOS_CRYPTO_DIGEST_BYTES];
    memset(tile_digest, 0x5Au, sizeof(tile_digest));
    CHECK(vos_cp_painter_add_tile(&eng.painter_doc, 10u, 32u, 32u, 1u, tile_digest) == VOS_CP_OK,
          "painter add tile");

    CHECK(vos_cp_switch_with_cut(&eng, VOS_CP_APP_EDITOR, &cleared,
                                 VOS_CP_GRANT_VALID, 0u, VOS_CP_CUT_NONE) == VOS_CP_OK,
          "painter -> editor switch");
    CHECK(eng.selected_app == VOS_CP_APP_EDITOR &&
          eng.editor_doc.text_len == 2u && eng.editor_doc.cursor == 2u &&
          eng.editor_doc.undo_count == 2u &&
          eng.editor_doc.text[0] == 'A' && eng.editor_doc.text[1] == 'B',
          "editor document/cursor/undo restored across swap");

    /* Reuse barrier refusals: stale register, saved context, active loan, late DMA */
    struct vos_cp_engine eng_r;
    CHECK(vos_cp_engine_init(&eng_r, auth_key, master_key,
                             VOS_CP_DEFAULT_SPACE_LIMIT, 8u, 0x22u) == VOS_CP_OK,
          "barrier engine init");
    CHECK(vos_cp_request_switch(&eng_r, VOS_CP_APP_PAINTER) == VOS_CP_OK, "request");
    CHECK(vos_cp_stage_current(&eng_r, 0u) == VOS_CP_OK, "stage");
    CHECK(vos_cp_commit_staged(&eng_r) == VOS_CP_OK, "commit");

    struct vos_cp_roots bad_reg = cleared;
    bad_reg.live_registers_clear = 0u;
    CHECK(vos_cp_release_slate(&eng_r, &bad_reg) == VOS_CP_ERR_REUSE_BARRIER,
          "stale register refuses release");

    struct vos_cp_roots bad_saved = cleared;
    bad_saved.raw_saved_clear = 0u;
    CHECK(vos_cp_release_slate(&eng_r, &bad_saved) == VOS_CP_ERR_REUSE_BARRIER,
          "saved context refuses release");

    struct vos_cp_roots bad_loan = cleared;
    bad_loan.loans_closed = 0u;
    CHECK(vos_cp_release_slate(&eng_r, &bad_loan) == VOS_CP_ERR_REUSE_BARRIER,
          "active loan refuses release");

    struct vos_cp_roots bad_dma = cleared;
    bad_dma.devices_completed = 0u;
    CHECK(vos_cp_release_slate(&eng_r, &bad_dma) == VOS_CP_ERR_REUSE_BARRIER,
          "late DMA refuses release");

    /* Dual ownership refusal: cannot restore painter while editor still owns slate */
    eng_r.target_app = VOS_CP_APP_PAINTER;
    CHECK(vos_cp_begin_restore(&eng_r, VOS_CP_APP_PAINTER) == VOS_CP_ERR_DUAL_OWNERSHIP,
          "dual slate ownership refused");

    /* Space limit refusal */
    struct vos_cp_engine eng_sp;
    CHECK(vos_cp_engine_init(&eng_sp, auth_key, master_key, 48u, 8u, 0x22u) == VOS_CP_OK,
          "small space engine init");
    CHECK(vos_cp_request_switch(&eng_sp, VOS_CP_APP_PAINTER) == VOS_CP_OK, "request sp");
    CHECK(vos_cp_stage_current(&eng_sp, 0u) == VOS_CP_ERR_OUT_OF_SPACE,
          "checkpoint space limit refused");

    /* Endurance exhaustion refusal */
    struct vos_cp_engine eng_end;
    CHECK(vos_cp_engine_init(&eng_end, auth_key, master_key,
                             VOS_CP_DEFAULT_SPACE_LIMIT, 1u, 0x22u) == VOS_CP_OK,
          "endurance=1 init");
    CHECK(vos_cp_switch_with_cut(&eng_end, VOS_CP_APP_PAINTER, &cleared,
                                 VOS_CP_GRANT_VALID, 0u, VOS_CP_CUT_NONE) == VOS_CP_OK,
          "first switch consumes endurance");
    CHECK(vos_cp_request_switch(&eng_end, VOS_CP_APP_EDITOR) == VOS_CP_ERR_ENDURANCE_EXHAUSTED,
          "endurance exhaustion refused");

    return 0;
}

static int test_crash_cuts_and_ab_store(void)
{
    uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256];
    init_keys(auth_key, master_key);
    const struct vos_cp_roots cleared = vos_cp_roots_cleared();

    const enum vos_cp_crash_cut cuts[5] = {
        VOS_CP_CUT_AFTER_QUIESCE,
        VOS_CP_CUT_AFTER_STAGE_BEFORE_COMMIT,
        VOS_CP_CUT_AFTER_COMMIT_BEFORE_RELEASE,
        VOS_CP_CUT_AFTER_RELEASE_BEFORE_RESTORE,
        VOS_CP_CUT_DURING_RESTORE_BEFORE_FINISH
    };

    for (size_t i = 0u; i < 5u; ++i) {
        struct vos_cp_engine eng;
        CHECK(vos_cp_engine_init(&eng, auth_key, master_key,
                                 VOS_CP_DEFAULT_SPACE_LIMIT, 8u, 0x33u) == VOS_CP_OK,
              "crash cut engine init");
        CHECK(vos_cp_editor_apply_insert(&eng.editor_doc, 0u, 'X') == VOS_CP_OK, "edit X");
        CHECK(vos_cp_switch_with_cut(&eng, VOS_CP_APP_PAINTER, &cleared,
                                     VOS_CP_GRANT_VALID, 0u, cuts[i]) == VOS_CP_OK,
              "execute up to crash cut");
        CHECK(vos_cp_exclusive_slate(&eng), "exclusive after crash");

        const struct vos_cp_durable_slot *act = vos_cp_active_slot(&eng, VOS_CP_APP_EDITOR);
        CHECK(act != NULL, "active checkpoint always valid after crash");
        struct vos_cp_meta meta;
        struct vos_cp_editor_doc recovered_doc;
        CHECK(vos_cp_decode_editor(act->wire, act->wire_len, auth_key, 0x33u,
                                   &meta, &recovered_doc) == VOS_CP_OK,
              "active checkpoint decodes cleanly after crash");

        if (cuts[i] == VOS_CP_CUT_AFTER_QUIESCE ||
            cuts[i] == VOS_CP_CUT_AFTER_STAGE_BEFORE_COMMIT) {
            CHECK(recovered_doc.text_len == 0u && meta.generation == 1u,
                  "pre-commit crash preserves prior active checkpoint");
        } else {
            CHECK(recovered_doc.text_len == 1u && recovered_doc.text[0] == 'X' &&
                  meta.generation == 2u,
                  "post-commit crash preserves new committed checkpoint");
        }

        CHECK(vos_cp_recover_quarantined_slate(&eng, &cleared) == VOS_CP_OK,
              "quarantined slate recovers under complete roots");
        CHECK(eng.apps[0].owns_slate == 0u && eng.apps[1].owns_slate == 0u,
              "slate released after crash recovery");
    }

    return 0;
}

static int test_lock_unlock_recovery(void)
{
    uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256];
    init_keys(auth_key, master_key);
    const struct vos_cp_roots cleared = vos_cp_roots_cleared();

    struct vos_cp_engine eng;
    CHECK(vos_cp_engine_init(&eng, auth_key, master_key,
                             VOS_CP_DEFAULT_SPACE_LIMIT, 8u, 0x44u) == VOS_CP_OK,
          "lock/unlock init");
    CHECK(vos_cp_editor_apply_insert(&eng.editor_doc, 0u, 'L') == VOS_CP_OK, "edit L");
    CHECK(vos_cp_editor_apply_insert(&eng.editor_doc, 1u, 'K') == VOS_CP_OK, "edit K");

    CHECK(vos_cp_lock_editor(&eng, &cleared, 1u, VOS_CP_CUT_NONE) == VOS_CP_OK,
          "lock editor with Fresh checkpoint");
    CHECK(eng.locked == 1u && eng.apps[0].owns_slate == 0u &&
          eng.apps[0].document_grant == 0u && eng.apps[0].session_authority == 0u &&
          eng.editor_doc.text_len == 0u,
          "locked editor zeroized volatile state and session authority");

    /* Revoked grant refuses unlock and never reinstates session authority */
    uint32_t outcome = VOS_CP_RECOVERY_NONE;
    CHECK(vos_cp_unlock_editor(&eng, VOS_CP_GRANT_REVOKED, master_key,
                               VOS_CRYPTO_KEY_BYTES_256, &outcome) == VOS_CP_ERR_GRANT_REFUSED,
          "revoked grant refused");
    CHECK(outcome == VOS_CP_RECOVERY_GRANT_REFUSED &&
          eng.apps[0].document_grant == 0u && eng.apps[0].session_authority == 0u,
          "revoked grant outcome and zero session");

    /* Expired grant refuses unlock */
    CHECK(vos_cp_unlock_editor(&eng, VOS_CP_GRANT_EXPIRED, master_key,
                               VOS_CRYPTO_KEY_BYTES_256, &outcome) == VOS_CP_ERR_GRANT_REFUSED,
          "expired grant refused");
    CHECK(outcome == VOS_CP_RECOVERY_GRANT_REFUSED &&
          eng.apps[0].document_grant == 0u && eng.apps[0].session_authority == 0u,
          "expired grant outcome and zero session");

    /* Valid grant restores acknowledged edits/cursor/undo with zero session/tagged state */
    CHECK(vos_cp_unlock_editor(&eng, VOS_CP_GRANT_VALID, master_key,
                               VOS_CRYPTO_KEY_BYTES_256, &outcome) == VOS_CP_OK,
          "valid grant unlock succeeds");
    CHECK(outcome == VOS_CP_RECOVERY_OK &&
          eng.editor_doc.text_len == 2u && eng.editor_doc.text[0] == 'L' &&
          eng.editor_doc.text[1] == 'K' && eng.editor_doc.cursor == 2u &&
          eng.editor_doc.undo_count == 2u &&
          eng.apps[0].document_grant == 1u &&
          eng.apps[0].session_authority == 0u &&
          eng.apps[0].tagged_state_restored == 0u,
          "unlock restored document without reviving session or tagged state");

    /* Incomplete/corrupted checkpoint preserves declared recovery outcome */
    CHECK(vos_cp_lock_editor(&eng, &cleared, 1u, VOS_CP_CUT_NONE) == VOS_CP_OK,
          "relock editor");
    struct vos_cp_ab_store *ed_store = &eng.stores[0];
    ed_store->slots[ed_store->active_slot].committed = 0u;
    CHECK(vos_cp_unlock_editor(&eng, VOS_CP_GRANT_VALID, master_key,
                               VOS_CRYPTO_KEY_BYTES_256, &outcome) ==
          VOS_CP_ERR_INCOMPLETE_CHECKPOINT,
          "incomplete checkpoint refused on unlock");
    CHECK(outcome == VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT &&
          eng.apps[0].document_grant == 0u && eng.apps[0].session_authority == 0u,
          "incomplete checkpoint sets declared recovery outcome");

    return 0;
}

int main(void)
{
    if (test_wire_format_and_rejections() != 0) {
        return 1;
    }
    if (test_crash_cuts_and_ab_store() != 0) {
        return 1;
    }
    if (test_slate_exchange_and_barrier_refusals() != 0) {
        return 1;
    }
    if (test_lock_unlock_recovery() != 0) {
        return 1;
    }
    printf("checkpoint_test: ok\n");
    return 0;
}
