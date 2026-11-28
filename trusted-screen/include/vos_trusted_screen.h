// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_TRUSTED_SCREEN_H
#define VOS_TRUSTED_SCREEN_H

#include <stddef.h>
#include <stdint.h>

#include "vos_backup.h"
#include "vos_crypto_core.h"

/* Trusted-path backup and migration screens specified in
 * [BackupTrustedScreen.v](../../proofs/BackupTrustedScreen.v) and
 * [backup-migration.md](../../docs/implementation/contracts/backup-migration.md#3-backup-key-and-trusted-holder-actions).
 */

enum {
    VOS_TS_DISPLAY_SECRET_CHARS = 79u,
    VOS_TS_MAX_ROOTS = 8u,
    VOS_TS_ROOT_FP_BYTES = 32u,
    VOS_TS_ROOT_LABEL_MAX = 32u,
    VOS_TS_ROOT_LIST_TEXT_MAX = 1024u,
    VOS_TS_CAVEAT_MAX_CHARS = 256u,
    VOS_TS_HMAC_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_TS_MAX_SPENT_WITNESSES = 64u
};

enum vos_ts_status {
    VOS_TS_OK = 0,
    VOS_TS_ERR_INVALID = -1,
    VOS_TS_ERR_AUTH = -2,
    VOS_TS_ERR_LOCKED = -3,
    VOS_TS_ERR_LATCH = -4,
    VOS_TS_ERR_APP_SPOOF = -5,
    VOS_TS_ERR_CAVEAT = -6,
    VOS_TS_ERR_STATE = -7,
    VOS_TS_ERR_REDISPLAY = -8,
    VOS_TS_ERR_HEX_FORMAT = -9,
    VOS_TS_ERR_REPLAY = -10,
    VOS_TS_ERR_EXPIRED = -11,
    VOS_TS_ERR_BINDING = -12,
    VOS_TS_ERR_NOT_APPRAISED = -13,
    VOS_TS_ERR_ROOT_TRUNCATED = -14,
    VOS_TS_ERR_ROOT_MISMATCH = -15,
    VOS_TS_ERR_HMAC = -16
};

enum vos_ts_flow {
    VOS_TS_FLOW_BACKUP_EXPORT = 1u,
    VOS_TS_FLOW_USER_RESTORE = 2u,
    VOS_TS_FLOW_DEVICE_MIGRATION = 3u,
    VOS_TS_FLOW_SYSTEM_ROLLBACK = 4u
};

enum vos_ts_exit_reason {
    VOS_TS_EXIT_COMPLETE = 1u,
    VOS_TS_EXIT_CANCEL = 2u,
    VOS_TS_EXIT_LOCK = 3u,
    VOS_TS_EXIT_FAULT = 4u
};

enum vos_ts_export_phase {
    VOS_TS_EXP_IDLE = 0u,
    VOS_TS_EXP_AUTHORIZED = 1u,
    VOS_TS_EXP_DISPLAYING = 2u,
    VOS_TS_EXP_CONFIRMED = 3u,
    VOS_TS_EXP_CLEARED = 4u
};

enum vos_ts_restore_phase {
    VOS_TS_RST_IDLE = 0u,
    VOS_TS_RST_AUTHORIZED = 1u,
    VOS_TS_RST_KEY_ENTERED = 2u,
    VOS_TS_RST_COMMITTED = 3u,
    VOS_TS_RST_CLEARED = 4u
};

enum vos_ts_migration_phase {
    VOS_TS_MIG_IDLE = 0u,
    VOS_TS_MIG_ROOTS_SHOWN = 1u,
    VOS_TS_MIG_CONFIRMED = 2u,
    VOS_TS_MIG_CLEARED = 3u
};

struct vos_ts_trusted_path {
    uint32_t unlocked;
    uint32_t hw_latch_active;
    uint32_t primary_cred_verified;
    uint32_t receiver_cred_verified;
    uint32_t app_originated;
    uint64_t epoch;
    uint32_t unlocked_profile;
    uint64_t device_generation;
    uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256];
    uint64_t next_witness_seq;
    uint64_t min_valid_seq;
    uint32_t spent_count;
    uint64_t spent_seqs[VOS_TS_MAX_SPENT_WITNESSES];
};

struct vos_ts_caveats {
    uint32_t ack_off_device_trade;
    uint32_t ack_surrendered_freshness;
    uint32_t ack_discard_loss;
    uint32_t ack_migration_roots;
    uint32_t ack_not_rollback;
};

struct vos_ts_consent_witness {
    uint32_t trusted_issued;
    uint32_t consumed;
    uint64_t seq;
    uint64_t epoch;
    enum vos_ts_flow flow;
    uint32_t unlocked_profile;
    uint64_t generation;
    uint64_t object_or_snapshot_id;
    uint64_t destination_id;
    uint64_t plan_id;
    uint32_t allow_discard;
    uint32_t allow_profile_mapping;
    uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t mac[VOS_TS_HMAC_BYTES];
};

struct vos_ts_quoted_root {
    uint8_t fingerprint[VOS_TS_ROOT_FP_BYTES];
    char label[VOS_TS_ROOT_LABEL_MAX];
};

struct vos_ts_export_screen {
    enum vos_ts_export_phase phase;
    uint32_t displayed_once;
    uint32_t confirmed;
    uint64_t snapshot_id;
    uint64_t destination_id;
    uint64_t plan_id;
    uint8_t secret_buf[VOS_BK_KEY_BYTES];
    char display_buf[VOS_TS_DISPLAY_SECRET_CHARS + 1u];
    char warning_banner[VOS_TS_CAVEAT_MAX_CHARS];
    struct vos_ts_consent_witness witness;
};

struct vos_ts_restore_screen {
    enum vos_ts_restore_phase phase;
    uint64_t object_id;
    uint64_t target_profile_id;
    uint64_t plan_id;
    uint32_t needs_discard;
    uint32_t allow_profile_mapping;
    uint8_t recovered_key[VOS_BK_KEY_BYTES];
    char warning_banner[VOS_TS_CAVEAT_MAX_CHARS];
    struct vos_ts_consent_witness witness;
};

struct vos_ts_migration_screen {
    enum vos_ts_migration_phase phase;
    uint32_t mutually_appraised;
    uint64_t receiver_gen;
    uint32_t receiving_profile;
    uint64_t channel_id;
    uint64_t plan_id;
    uint32_t root_count;
    struct vos_ts_quoted_root roots[VOS_TS_MAX_ROOTS];
    uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES];
    char rendered_roots[VOS_TS_ROOT_LIST_TEXT_MAX];
    char warning_banner[VOS_TS_CAVEAT_MAX_CHARS];
};

void vos_ts_wipe(void *ptr, size_t len);

enum vos_ts_status vos_ts_format_recovery_display(
    const uint8_t key[VOS_BK_KEY_BYTES],
    char out_display[VOS_TS_DISPLAY_SECRET_CHARS + 1u]);

void vos_ts_trusted_path_init(struct vos_ts_trusted_path *tp,
                              uint32_t unlocked_profile,
                              uint64_t device_generation,
                              const uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256]);

void vos_ts_trusted_path_set_gate(struct vos_ts_trusted_path *tp,
                                  uint32_t unlocked,
                                  uint32_t hw_latch_active,
                                  uint32_t primary_cred_verified,
                                  uint32_t receiver_cred_verified,
                                  uint32_t app_originated);

void vos_ts_trusted_path_lock(struct vos_ts_trusted_path *tp);

void vos_ts_trusted_path_restart(struct vos_ts_trusted_path *tp,
                                 uint32_t unlocked_profile,
                                 uint64_t device_generation);

void vos_ts_trusted_path_set_profile(struct vos_ts_trusted_path *tp,
                                     uint32_t new_profile);

void vos_ts_trusted_path_set_generation(struct vos_ts_trusted_path *tp,
                                        uint64_t new_generation);

enum vos_ts_status vos_ts_compute_root_digest(
    const struct vos_ts_quoted_root *roots,
    uint32_t root_count,
    uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES]);

enum vos_ts_status vos_ts_issue_witness(
    struct vos_ts_trusted_path *tp,
    enum vos_ts_flow flow,
    const struct vos_ts_caveats *cav,
    uint64_t obj_or_snap_id,
    uint64_t destination_id,
    uint64_t plan_id,
    uint32_t needs_discard,
    uint32_t allow_profile_mapping,
    const uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES],
    struct vos_ts_consent_witness *out_witness);

enum vos_ts_status vos_ts_verify_and_consume_witness(
    struct vos_ts_trusted_path *tp,
    struct vos_ts_consent_witness *witness,
    enum vos_ts_flow expected_flow,
    uint64_t expected_obj_id,
    uint64_t expected_dst_id,
    uint64_t expected_plan_id,
    uint32_t expected_needs_discard,
    const uint8_t expected_root_digest[VOS_CRYPTO_DIGEST_BYTES]);

void vos_ts_witness_to_bk_consent(const struct vos_ts_trusted_path *tp,
                                  const struct vos_ts_consent_witness *witness,
                                  uint32_t target_profile,
                                  struct vos_bk_consent *out_consent);

void vos_ts_export_init(struct vos_ts_export_screen *scr);

enum vos_ts_status vos_ts_export_authorize(
    struct vos_ts_export_screen *scr,
    struct vos_ts_trusted_path *tp,
    const struct vos_ts_caveats *cav,
    uint64_t snapshot_id,
    uint64_t destination_id,
    uint64_t plan_id);

enum vos_ts_status vos_ts_export_show_secret_once(
    struct vos_ts_export_screen *scr,
    const struct vos_ts_trusted_path *tp,
    const uint8_t key[VOS_BK_KEY_BYTES]);

enum vos_ts_status vos_ts_export_confirm_recorded(
    struct vos_ts_export_screen *scr,
    struct vos_ts_trusted_path *tp,
    uint64_t snapshot_id,
    uint64_t destination_id,
    uint64_t plan_id);

void vos_ts_export_abort(struct vos_ts_export_screen *scr,
                         enum vos_ts_exit_reason reason);

void vos_ts_restore_init(struct vos_ts_restore_screen *scr);

enum vos_ts_status vos_ts_restore_authorize(
    struct vos_ts_restore_screen *scr,
    struct vos_ts_trusted_path *tp,
    const struct vos_ts_caveats *cav,
    uint64_t object_id,
    uint64_t target_profile_id,
    uint64_t plan_id,
    uint32_t needs_discard,
    uint32_t allow_profile_mapping);

enum vos_ts_status vos_ts_restore_enter_recovery_secret(
    struct vos_ts_restore_screen *scr,
    const struct vos_ts_trusted_path *tp,
    const char *entry,
    size_t entry_len);

enum vos_ts_status vos_ts_restore_consume_and_commit(
    struct vos_ts_restore_screen *scr,
    struct vos_ts_trusted_path *tp,
    uint64_t object_id,
    uint64_t target_profile_id,
    uint64_t plan_id,
    uint8_t key_out[VOS_BK_KEY_BYTES]);

void vos_ts_restore_abort(struct vos_ts_restore_screen *scr,
                          enum vos_ts_exit_reason reason);

void vos_ts_migration_init(struct vos_ts_migration_screen *scr);

enum vos_ts_status vos_ts_migration_present_roots(
    struct vos_ts_migration_screen *scr,
    const struct vos_ts_trusted_path *tp,
    uint32_t mutually_appraised,
    uint64_t receiver_gen,
    uint32_t receiving_profile,
    uint64_t channel_id,
    uint64_t plan_id,
    const struct vos_ts_quoted_root *roots,
    uint32_t root_count);

enum vos_ts_status vos_ts_migration_confirm(
    struct vos_ts_migration_screen *scr,
    struct vos_ts_trusted_path *tp,
    const struct vos_ts_caveats *cav,
    const struct vos_ts_quoted_root *confirmed_roots,
    uint32_t confirmed_count,
    uint64_t channel_id,
    uint64_t plan_id,
    struct vos_ts_consent_witness *out_witness);

enum vos_ts_status vos_ts_migration_consume_transfer(
    struct vos_ts_migration_screen *scr,
    struct vos_ts_trusted_path *tp,
    struct vos_ts_consent_witness *witness,
    uint64_t receiver_gen,
    uint64_t channel_id,
    uint64_t plan_id);

void vos_ts_migration_abort(struct vos_ts_migration_screen *scr,
                            enum vos_ts_exit_reason reason);

#endif
