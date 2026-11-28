// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_CHECKPOINT_H
#define VOS_CHECKPOINT_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

enum {
    VOS_CP_MAX_TEXT_BYTES = 256u,
    VOS_CP_MAX_UNDO = 16u,
    VOS_CP_MAX_TILES = 16u,
    VOS_CP_MAX_IMAGE_HISTORY = 16u,
    VOS_CP_WIRE_HEADER_BYTES = 56u,
    VOS_CP_MAX_PAYLOAD_BYTES = 1056u,
    VOS_CP_MAX_WIRE_BYTES =
        VOS_CP_WIRE_HEADER_BYTES + VOS_CP_MAX_PAYLOAD_BYTES + VOS_CRYPTO_DIGEST_BYTES,
    VOS_CP_DEFAULT_SPACE_LIMIT = VOS_CP_MAX_WIRE_BYTES,
    VOS_CP_DEFAULT_ENDURANCE_LIMIT = 8u,
    VOS_CP_SCHEMA_VERSION = 1u,
    VOS_CP_WIRE_VERSION = 1u,
    VOS_CP_APP_COUNT = 2u
};

enum vos_cp_app_id {
    VOS_CP_APP_NONE = 0u,
    VOS_CP_APP_EDITOR = 1u,
    VOS_CP_APP_PAINTER = 2u
};

enum vos_cp_phase {
    VOS_CP_PHASE_ACTIVE = 0u,
    VOS_CP_PHASE_QUIESCING = 1u,
    VOS_CP_PHASE_RETIRING = 2u,
    VOS_CP_PHASE_HIBERNATED = 3u,
    VOS_CP_PHASE_RESTORING = 4u,
    VOS_CP_PHASE_CLOSED = 5u
};

enum vos_cp_payload_kind {
    VOS_CP_PAYLOAD_SEMANTIC = 1u,
    VOS_CP_PAYLOAD_RAW_HEAP = 2u,
    VOS_CP_PAYLOAD_EXECUTABLE = 3u,
    VOS_CP_PAYLOAD_SESSION_KEY = 4u
};

enum vos_cp_forbidden_bits {
    VOS_CP_FORBID_TAGGED_CAPS = 1u << 0u,
    VOS_CP_FORBID_SAVED_REGS = 1u << 1u,
    VOS_CP_FORBID_LIVE_GRANTS = 1u << 2u,
    VOS_CP_FORBID_SESSION_KEYS = 1u << 3u
};

enum vos_cp_grant_state {
    VOS_CP_GRANT_VALID = 0u,
    VOS_CP_GRANT_REVOKED = 1u,
    VOS_CP_GRANT_EXPIRED = 2u
};

enum vos_cp_recovery_outcome {
    VOS_CP_RECOVERY_NONE = 0u,
    VOS_CP_RECOVERY_OK = 1u,
    VOS_CP_RECOVERY_GRANT_REFUSED = 2u,
    VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT = 3u
};

enum vos_cp_crash_cut {
    VOS_CP_CUT_NONE = 0u,
    VOS_CP_CUT_AFTER_QUIESCE = 1u,
    VOS_CP_CUT_AFTER_STAGE_BEFORE_COMMIT = 2u,
    VOS_CP_CUT_AFTER_COMMIT_BEFORE_RELEASE = 3u,
    VOS_CP_CUT_AFTER_RELEASE_BEFORE_RESTORE = 4u,
    VOS_CP_CUT_DURING_RESTORE_BEFORE_FINISH = 5u
};

enum vos_cp_status {
    VOS_CP_OK = 0,
    VOS_CP_ERR_INVALID_ARG = -1,
    VOS_CP_ERR_BAD_FORMAT = -2,
    VOS_CP_ERR_NON_SEMANTIC = -3,
    VOS_CP_ERR_FORBIDDEN_AUTHORITY = -4,
    VOS_CP_ERR_TRAILING_BYTES = -5,
    VOS_CP_ERR_AUTH_FAILED = -6,
    VOS_CP_ERR_OUT_OF_SPACE = -7,
    VOS_CP_ERR_ENDURANCE_EXHAUSTED = -8,
    VOS_CP_ERR_REUSE_BARRIER = -9,
    VOS_CP_ERR_DUAL_OWNERSHIP = -10,
    VOS_CP_ERR_GRANT_REFUSED = -11,
    VOS_CP_ERR_INCOMPLETE_CHECKPOINT = -12,
    VOS_CP_ERR_BAD_STATE = -13,
    VOS_CP_ERR_FRESH_FAILED = -14
};

struct vos_cp_undo_entry {
    uint32_t op_kind;
    uint32_t offset;
    uint32_t prev_cursor;
    uint8_t old_byte;
    uint8_t new_byte;
    uint8_t reserved[2];
};

struct vos_cp_editor_doc {
    uint32_t text_len;
    uint32_t cursor;
    uint32_t undo_count;
    uint32_t dirty;
    uint8_t text[VOS_CP_MAX_TEXT_BYTES];
    struct vos_cp_undo_entry undo[VOS_CP_MAX_UNDO];
};

struct vos_cp_tile_desc {
    uint32_t tile_id;
    uint32_t width;
    uint32_t height;
    uint32_t revision;
    uint8_t content_digest[VOS_CRYPTO_DIGEST_BYTES];
};

struct vos_cp_image_op {
    uint32_t op_kind;
    uint32_t tile_id;
    uint32_t revision;
    uint32_t param;
};

struct vos_cp_painter_doc {
    uint32_t tile_count;
    uint32_t preview_width;
    uint32_t preview_height;
    uint32_t preview_epoch;
    uint32_t history_count;
    uint32_t dirty;
    struct vos_cp_tile_desc tiles[VOS_CP_MAX_TILES];
    struct vos_cp_image_op history[VOS_CP_MAX_IMAGE_HISTORY];
};

struct vos_cp_meta {
    uint32_t app_id;
    uint32_t payload_kind;
    uint32_t schema_version;
    uint64_t generation;
    uint32_t confidentiality_label;
    uint32_t security_critical;
    uint64_t fresh_epoch;
    uint32_t forbidden_flags;
};

struct vos_cp_roots {
    uint8_t inventory_complete;
    uint8_t bases_closed;
    uint8_t ingress_closed;
    uint8_t live_registers_clear;
    uint8_t raw_saved_clear;
    uint8_t mint_roots_clear;
    uint8_t loans_closed;
    uint8_t proxy_acknowledged;
    uint8_t devices_completed;
    uint8_t barrier_complete;
    uint8_t sweep_after_barrier;
    uint8_t sweep_complete;
    uint8_t data_tags_sanitized;
};

struct vos_cp_durable_slot {
    uint32_t valid;
    uint32_t committed;
    uint64_t generation;
    uint64_t fresh_epoch;
    uint8_t fresh_root[VOS_CRYPTO_DIGEST_BYTES];
    uint32_t wire_len;
    uint8_t wire[VOS_CP_MAX_WIRE_BYTES];
};

struct vos_cp_ab_store {
    struct vos_cp_durable_slot slots[2];
    uint32_t active_slot;
    uint32_t staging_dirty;
    uint64_t next_generation;
};

struct vos_cp_app_runtime {
    uint32_t phase;
    uint32_t owns_slate;
    uint32_t document_grant;
    uint32_t session_authority;
    uint32_t tagged_state_restored;
    uint32_t retirement_committed;
};

struct vos_cp_engine {
    uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES];
    struct vos_crypto_core crypto;
    uint32_t space_reserved;
    uint32_t endurance_used;
    uint32_t endurance_limit;
    uint32_t confidentiality_label;
    uint32_t selected_app;
    uint32_t target_app;
    uint32_t locked;
    uint32_t recovery_outcome;
    struct vos_cp_app_runtime apps[VOS_CP_APP_COUNT];
    struct vos_cp_ab_store stores[VOS_CP_APP_COUNT];
    struct vos_cp_editor_doc editor_doc;
    struct vos_cp_painter_doc painter_doc;
};

struct vos_cp_roots vos_cp_roots_cleared(void);
int vos_cp_roots_reusable(const struct vos_cp_roots *roots);

void vos_cp_editor_doc_init(struct vos_cp_editor_doc *doc);
int vos_cp_editor_apply_insert(struct vos_cp_editor_doc *doc, uint32_t offset, uint8_t ch);
void vos_cp_painter_doc_init(struct vos_cp_painter_doc *doc,
                             uint32_t preview_width, uint32_t preview_height);
int vos_cp_painter_add_tile(struct vos_cp_painter_doc *doc, uint32_t tile_id,
                            uint32_t width, uint32_t height, uint32_t revision,
                            const uint8_t digest[VOS_CRYPTO_DIGEST_BYTES]);

int vos_cp_encode_editor(const struct vos_cp_meta *meta,
                         const struct vos_cp_editor_doc *doc,
                         const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                         uint8_t *out_wire, size_t out_cap, size_t *out_len);

int vos_cp_encode_painter(const struct vos_cp_meta *meta,
                          const struct vos_cp_painter_doc *doc,
                          const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                          uint8_t *out_wire, size_t out_cap, size_t *out_len);

int vos_cp_decode_editor(const uint8_t *wire, size_t wire_len,
                         const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                         uint32_t expected_label,
                         struct vos_cp_meta *out_meta,
                         struct vos_cp_editor_doc *out_doc);

int vos_cp_decode_painter(const uint8_t *wire, size_t wire_len,
                          const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                          uint32_t expected_label,
                          struct vos_cp_meta *out_meta,
                          struct vos_cp_painter_doc *out_doc);

int vos_cp_engine_init(struct vos_cp_engine *eng,
                       const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                       const uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256],
                       uint32_t space_reserved,
                       uint32_t endurance_limit,
                       uint32_t confidentiality_label);

int vos_cp_request_switch(struct vos_cp_engine *eng, uint32_t target_app);
int vos_cp_stage_current(struct vos_cp_engine *eng, uint32_t security_critical);
int vos_cp_commit_staged(struct vos_cp_engine *eng);
int vos_cp_release_slate(struct vos_cp_engine *eng, const struct vos_cp_roots *roots);
int vos_cp_begin_restore(struct vos_cp_engine *eng, uint32_t target_app);
int vos_cp_finish_restore(struct vos_cp_engine *eng, uint32_t target_app,
                          uint32_t grant_state);

int vos_cp_switch_with_cut(struct vos_cp_engine *eng, uint32_t target_app,
                           const struct vos_cp_roots *roots,
                           uint32_t grant_state,
                           uint32_t security_critical,
                           enum vos_cp_crash_cut cut);

void vos_cp_inject_crash(struct vos_cp_engine *eng);
int vos_cp_recover_quarantined_slate(struct vos_cp_engine *eng,
                                     const struct vos_cp_roots *roots);

int vos_cp_lock_editor(struct vos_cp_engine *eng, const struct vos_cp_roots *roots,
                       uint32_t security_critical, enum vos_cp_crash_cut cut);
int vos_cp_unlock_editor(struct vos_cp_engine *eng, uint32_t grant_state,
                         const uint8_t *master_key, size_t master_key_len,
                         uint32_t *out_outcome);

const struct vos_cp_durable_slot *vos_cp_active_slot(const struct vos_cp_engine *eng,
                                                     uint32_t app_id);
int vos_cp_exclusive_slate(const struct vos_cp_engine *eng);

#endif
