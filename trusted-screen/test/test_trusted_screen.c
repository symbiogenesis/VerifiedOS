// SPDX-License-Identifier: Apache-2.0
#include "vos_trusted_screen.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static const uint8_t TEST_HMAC_KEY[VOS_CRYPTO_KEY_BYTES_256] = {
    0x10u, 0x21u, 0x32u, 0x43u, 0x54u, 0x65u, 0x76u, 0x87u,
    0x98u, 0xA9u, 0xBAu, 0xCBu, 0xDCu, 0xEDu, 0xFEu, 0x0Fu,
    0x11u, 0x22u, 0x33u, 0x44u, 0x55u, 0x66u, 0x77u, 0x88u,
    0x99u, 0xAAu, 0xBBu, 0xCCu, 0xDDu, 0xEEu, 0xFFu, 0x00u
};

static int all_zero(const void *ptr, size_t len)
{
    const uint8_t *p = (const uint8_t *)ptr;
    for (size_t i = 0u; i < len; ++i) {
        if (p[i] != 0u) {
            return 0;
        }
    }
    return 1;
}

static struct vos_ts_caveats make_all_caveats(void)
{
    struct vos_ts_caveats c;
    c.ack_off_device_trade = 1u;
    c.ack_surrendered_freshness = 1u;
    c.ack_discard_loss = 1u;
    c.ack_migration_roots = 1u;
    c.ack_not_rollback = 1u;
    return c;
}

static struct vos_ts_quoted_root make_root(uint8_t tag, const char *label)
{
    struct vos_ts_quoted_root r;
    memset(&r, 0, sizeof(r));
    for (size_t i = 0u; i < VOS_TS_ROOT_FP_BYTES; ++i) {
        r.fingerprint[i] = (uint8_t)(tag + (uint8_t)i);
    }
    const size_t llen = strlen(label);
    memcpy(r.label, label, llen);
    r.label[llen] = '\0';
    return r;
}

static int test_ba_display_and_one_time_wipe(void)
{
    uint8_t key_lz[VOS_BK_KEY_BYTES];
    for (size_t i = 0u; i < VOS_BK_KEY_BYTES; ++i) {
        key_lz[i] = (uint8_t)i;
    }

    char disp[VOS_TS_DISPLAY_SECRET_CHARS + 1u];
    CHECK(vos_ts_format_recovery_display(key_lz, disp) == VOS_TS_OK,
          "format 16x4 display");
    const char *expected_disp =
        "0001 0203 0405 0607 0809 0A0B 0C0D 0E0F "
        "1011 1213 1415 1617 1819 1A1B 1C1D 1E1F";
    CHECK(strlen(disp) == VOS_TS_DISPLAY_SECRET_CHARS, "display length 79");
    CHECK(strcmp(disp, expected_disp) == 0, "leading-zero 16x4 uppercase hex");

    struct vos_ts_trusted_path tp;
    vos_ts_trusted_path_init(&tp, 1u, 7u, TEST_HMAC_KEY);
    vos_ts_trusted_path_set_gate(&tp, 1u, 1u, 1u, 0u, 0u);
    struct vos_ts_caveats cav = make_all_caveats();

    /* BA-RESIDUAL: Export requires R-17-054a off-device trade caveat. */
    struct vos_ts_export_screen scr;
    vos_ts_export_init(&scr);
    struct vos_ts_caveats missing_r17 = cav;
    missing_r17.ack_off_device_trade = 0u;
    CHECK(vos_ts_export_authorize(&scr, &tp, &missing_r17, 42u, 99u, 1u) == VOS_TS_ERR_CAVEAT,
          "export refuses missing R-17-054a caveat");

    /* Rollback flow is refused by backup/migration witness issuer. */
    struct vos_ts_consent_witness rb_w;
    CHECK(vos_ts_issue_witness(&tp, VOS_TS_FLOW_SYSTEM_ROLLBACK, &cav,
                               42u, 99u, 1u, 0u, 0u, NULL, &rb_w) == VOS_TS_ERR_BINDING,
          "system rollback flow refused");

    CHECK(vos_ts_export_authorize(&scr, &tp, &cav, 42u, 99u, 1u) == VOS_TS_OK,
          "export authorize");
    CHECK(strstr(scr.warning_banner, "R-17-054a") != NULL,
          "export warning states R-17-054a");
    CHECK(strstr(scr.warning_banner, "not system rollback") != NULL,
          "export warning distinguishes from rollback");

    /* Show once succeeds. */
    CHECK(vos_ts_export_show_secret_once(&scr, &tp, key_lz) == VOS_TS_OK,
          "show secret once");
    CHECK(strcmp(scr.display_buf, expected_disp) == 0, "display buf matches");
    CHECK(memcmp(scr.secret_buf, key_lz, VOS_BK_KEY_BYTES) == 0, "secret buf matches");

    /* Redisplay while showing or after completion must refuse. */
    CHECK(vos_ts_export_show_secret_once(&scr, &tp, key_lz) == VOS_TS_ERR_REDISPLAY,
          "block redisplay while showing");
    CHECK(vos_ts_export_confirm_recorded(&scr, &tp, 42u, 99u, 1u) == VOS_TS_OK,
          "confirm recorded");
    CHECK(all_zero(scr.secret_buf, sizeof(scr.secret_buf)), "secret cleared on complete");
    CHECK(all_zero(scr.display_buf, sizeof(scr.display_buf)), "display cleared on complete");
    CHECK(vos_ts_export_show_secret_once(&scr, &tp, key_lz) == VOS_TS_ERR_REDISPLAY,
          "block redisplay after complete");

    /* Cancel, lock, and fault all clear secret & display buffers. */
    const enum vos_ts_exit_reason aborts[3] = {
        VOS_TS_EXIT_CANCEL, VOS_TS_EXIT_LOCK, VOS_TS_EXIT_FAULT
    };
    for (size_t i = 0u; i < 3u; ++i) {
        vos_ts_export_init(&scr);
        CHECK(vos_ts_export_authorize(&scr, &tp, &cav, 43u + i, 99u, 1u) == VOS_TS_OK,
              "reinit export");
        CHECK(vos_ts_export_show_secret_once(&scr, &tp, key_lz) == VOS_TS_OK,
              "show once before abort");
        vos_ts_export_abort(&scr, aborts[i]);
        CHECK(all_zero(scr.secret_buf, sizeof(scr.secret_buf)), "secret wiped on abort");
        CHECK(all_zero(scr.display_buf, sizeof(scr.display_buf)), "display wiped on abort");
        CHECK(vos_ts_export_show_secret_once(&scr, &tp, key_lz) == VOS_TS_ERR_REDISPLAY,
              "no redisplay after abort");
    }
    return 0;
}

static int test_ba_consent_and_schema_restore(void)
{
    uint8_t key_lz[VOS_BK_KEY_BYTES];
    for (size_t i = 0u; i < VOS_BK_KEY_BYTES; ++i) {
        key_lz[i] = (uint8_t)i;
    }
    char canonical_hex[VOS_BK_RECOVERY_HEX_CHARS + 1u];
    CHECK(vos_bk_encode_recovery_secret(key_lz, canonical_hex) == VOS_BK_OK,
          "encode canonical 64 hex");

    struct vos_ts_trusted_path tp;
    vos_ts_trusted_path_init(&tp, 1u, 7u, TEST_HMAC_KEY);
    struct vos_ts_caveats cav = make_all_caveats();
    struct vos_ts_restore_screen rscr;

    /* Locked device, missing latch, missing cred, app-originated all refused. */
    vos_ts_restore_init(&rscr);
    vos_ts_trusted_path_set_gate(&tp, 0u, 1u, 1u, 0u, 0u);
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &cav, 77u, 1u, 10u, 0u, 0u) == VOS_TS_ERR_LOCKED,
          "locked device refused");

    vos_ts_trusted_path_set_gate(&tp, 1u, 0u, 1u, 0u, 0u);
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &cav, 77u, 1u, 10u, 0u, 0u) == VOS_TS_ERR_LATCH,
          "missing hw latch refused");

    vos_ts_trusted_path_set_gate(&tp, 1u, 1u, 0u, 0u, 0u);
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &cav, 77u, 1u, 10u, 0u, 0u) == VOS_TS_ERR_AUTH,
          "missing primary cred refused");

    vos_ts_trusted_path_set_gate(&tp, 1u, 1u, 1u, 0u, 1u);
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &cav, 77u, 1u, 10u, 0u, 0u) == VOS_TS_ERR_APP_SPOOF,
          "app-originated prompt refused");

    /* Missing surrendered-freshness or discard-loss caveats refused. */
    vos_ts_trusted_path_set_gate(&tp, 1u, 1u, 1u, 0u, 0u);
    struct vos_ts_caveats no_fresh = cav;
    no_fresh.ack_surrendered_freshness = 0u;
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &no_fresh, 77u, 1u, 10u, 0u, 0u) == VOS_TS_ERR_CAVEAT,
          "missing surrendered-freshness caveat refused");

    struct vos_ts_caveats no_discard = cav;
    no_discard.ack_discard_loss = 0u;
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &no_discard, 78u, 1u, 11u, 1u, 0u) == VOS_TS_ERR_CAVEAT,
          "BA-SCHEMA: discard plan without discard-loss ack refused");

    /* Valid restore with explicit discard plan. */
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &cav, 78u, 1u, 11u, 1u, 0u) == VOS_TS_OK,
          "BA-SCHEMA: restore authorize with discard ack");
    CHECK(strstr(rscr.warning_banner, "User-Data Restore") != NULL,
          "restore label visible");
    CHECK(strstr(rscr.warning_banner, "surrender freshness") != NULL,
          "surrender freshness caveat visible");
    CHECK(strstr(rscr.warning_banner, "Explicit discard") != NULL,
          "discard loss caveat visible");

    /* Non-canonical / lowercase / formatted / short secret entries refused. */
    char lower_hex[VOS_BK_RECOVERY_HEX_CHARS + 1u];
    memcpy(lower_hex, canonical_hex, sizeof(lower_hex));
    lower_hex[21] = 'a';
    CHECK(vos_ts_restore_enter_recovery_secret(&rscr, &tp, lower_hex, 64u) == VOS_TS_ERR_HEX_FORMAT,
          "lowercase secret rejected");
    CHECK(vos_ts_restore_enter_recovery_secret(&rscr, &tp, canonical_hex, 63u) == VOS_TS_ERR_HEX_FORMAT,
          "short secret rejected");
    char spaced[VOS_TS_DISPLAY_SECRET_CHARS + 1u];
    CHECK(vos_ts_format_recovery_display(key_lz, spaced) == VOS_TS_OK, "format spaced");
    CHECK(vos_ts_restore_enter_recovery_secret(&rscr, &tp, spaced, 79u) == VOS_TS_ERR_HEX_FORMAT,
          "spaced display string rejected as raw 64-char entry");

    /* Canonical 64-char entry succeeds and commits once. */
    CHECK(vos_ts_restore_enter_recovery_secret(&rscr, &tp, canonical_hex, 64u) == VOS_TS_OK,
          "canonical 64-char entry accepted");

    /* Plan change / profile change / lock expire witness before commit. */
    struct vos_ts_consent_witness w_copy = rscr.witness;
    uint8_t out_key[VOS_BK_KEY_BYTES];
    struct vos_ts_trusted_path tp_tmp = tp;
    struct vos_ts_restore_screen rscr_tmp = rscr;
    CHECK(vos_ts_restore_consume_and_commit(&rscr_tmp, &tp_tmp, 78u, 1u, 999u, out_key) == VOS_TS_ERR_BINDING,
          "plan change refuses witness");
    CHECK(all_zero(rscr_tmp.recovered_key, sizeof(rscr_tmp.recovered_key)),
          "key wiped on binding failure");

    tp_tmp = tp;
    rscr_tmp = rscr;
    vos_ts_trusted_path_set_profile(&tp_tmp, 2u);
    CHECK(vos_ts_restore_consume_and_commit(&rscr_tmp, &tp_tmp, 78u, 1u, 11u, out_key) == VOS_TS_ERR_BINDING,
          "profile change refuses witness");

    tp_tmp = tp;
    rscr_tmp = rscr;
    vos_ts_trusted_path_lock(&tp_tmp);
    vos_ts_trusted_path_set_gate(&tp_tmp, 1u, 1u, 1u, 0u, 0u);
    CHECK(vos_ts_restore_consume_and_commit(&rscr_tmp, &tp_tmp, 78u, 1u, 11u, out_key) == VOS_TS_ERR_REPLAY,
          "lock advances floor and invalidates pre-lock witness");

    /* Real commit succeeds and exports valid bk consent beforehand. */
    struct vos_bk_consent bkc;
    vos_ts_witness_to_bk_consent(&tp, &rscr.witness, 1u, &bkc);
    CHECK(bkc.valid == 1u && bkc.allow_discard == 1u && bkc.op == VOS_BK_OP_RESTORE,
          "valid bk consent projection");

    CHECK(vos_ts_restore_consume_and_commit(&rscr, &tp, 78u, 1u, 11u, out_key) == VOS_TS_OK,
          "restore witness commit");
    CHECK(memcmp(out_key, key_lz, VOS_BK_KEY_BYTES) == 0, "restored key matches");
    CHECK(all_zero(rscr.recovered_key, sizeof(rscr.recovered_key)), "internal key wiped");

    /* Replay of copied pre-consume witness must refuse. */
    CHECK(vos_ts_verify_and_consume_witness(&tp, &w_copy, VOS_TS_FLOW_USER_RESTORE,
                                            78u, 1u, 11u, 1u, NULL) == VOS_TS_ERR_REPLAY,
          "witness replay refused");

    /* App-forged witness (trusted_issued = 0 or tampered HMAC) refused. */
    struct vos_ts_consent_witness forged = w_copy;
    forged.seq = tp.next_witness_seq + 1u;
    forged.trusted_issued = 0u;
    CHECK(vos_ts_verify_and_consume_witness(&tp, &forged, VOS_TS_FLOW_USER_RESTORE,
                                            78u, 1u, 11u, 1u, NULL) == VOS_TS_ERR_APP_SPOOF,
          "app-originated witness refused");

    struct vos_ts_consent_witness fresh_w;
    CHECK(vos_ts_issue_witness(&tp, VOS_TS_FLOW_USER_RESTORE, &cav,
                               79u, 1u, 12u, 0u, 0u, NULL, &fresh_w) == VOS_TS_OK,
          "issue fresh witness");
    fresh_w.mac[0] ^= 0x5Au;
    CHECK(vos_ts_verify_and_consume_witness(&tp, &fresh_w, VOS_TS_FLOW_USER_RESTORE,
                                            79u, 1u, 12u, 0u, NULL) == VOS_TS_ERR_HMAC,
          "tampered HMAC witness refused");

    /* Abort on restore clears recovered_key. */
    vos_ts_restore_init(&rscr);
    CHECK(vos_ts_restore_authorize(&rscr, &tp, &cav, 80u, 1u, 13u, 0u, 0u) == VOS_TS_OK,
          "authorize before cancel");
    CHECK(vos_ts_restore_enter_recovery_secret(&rscr, &tp, canonical_hex, 64u) == VOS_TS_OK,
          "enter secret before cancel");
    vos_ts_restore_abort(&rscr, VOS_TS_EXIT_CANCEL);
    CHECK(all_zero(rscr.recovered_key, sizeof(rscr.recovered_key)),
          "restore abort wipes recovered key");
    return 0;
}

static int test_ba_migrate_roots_and_appraisal(void)
{
    struct vos_ts_trusted_path tp;
    vos_ts_trusted_path_init(&tp, 1u, 7u, TEST_HMAC_KEY);
    vos_ts_trusted_path_set_gate(&tp, 1u, 1u, 1u, 1u, 0u);
    struct vos_ts_caveats cav = make_all_caveats();

    struct vos_ts_quoted_root roots[2];
    roots[0] = make_root(0x10u, "RoT-A");
    roots[1] = make_root(0x20u, "RoT-B");

    struct vos_ts_migration_screen mscr;
    vos_ts_migration_init(&mscr);

    /* Unappraised peer refused. */
    CHECK(vos_ts_migration_present_roots(&mscr, &tp, 0u, 7u, 1u, 55u, 1u, roots, 2u) == VOS_TS_ERR_NOT_APPRAISED,
          "unappraised peer refused");

    /* Oversize / truncated root list (> VOS_TS_MAX_ROOTS) refused. */
    struct vos_ts_quoted_root too_many[VOS_TS_MAX_ROOTS + 1u];
    for (uint32_t i = 0u; i < VOS_TS_MAX_ROOTS + 1u; ++i) {
        too_many[i] = make_root((uint8_t)(0x30u + i), "RootN");
    }
    CHECK(vos_ts_migration_present_roots(&mscr, &tp, 1u, 7u, 1u, 55u, 1u,
                                         too_many, VOS_TS_MAX_ROOTS + 1u) == VOS_TS_ERR_ROOT_TRUNCATED,
          "oversize root set refused rather than truncated");

    /* Missing receiver credential refused. */
    vos_ts_trusted_path_set_gate(&tp, 1u, 1u, 1u, 0u, 0u);
    CHECK(vos_ts_migration_present_roots(&mscr, &tp, 1u, 7u, 1u, 55u, 1u, roots, 2u) == VOS_TS_ERR_AUTH,
          "missing receiver cred refused");

    /* Present full root set. */
    vos_ts_trusted_path_set_gate(&tp, 1u, 1u, 1u, 1u, 0u);
    CHECK(vos_ts_migration_present_roots(&mscr, &tp, 1u, 7u, 1u, 55u, 1u, roots, 2u) == VOS_TS_OK,
          "present complete quoted roots");
    CHECK(strstr(mscr.rendered_roots, "RoT-A:") != NULL &&
          strstr(mscr.rendered_roots, "RoT-B:") != NULL,
          "both roots rendered without truncation");

    /* Truncated or substituted root confirmation refused. */
    struct vos_ts_consent_witness mig_w;
    CHECK(vos_ts_migration_confirm(&mscr, &tp, &cav, roots, 1u, 55u, 1u, &mig_w) == VOS_TS_ERR_ROOT_MISMATCH,
          "truncated confirmation refused");
    struct vos_ts_quoted_root sub_roots[2];
    sub_roots[0] = roots[0];
    sub_roots[1] = make_root(0x99u, "RoT-Evil");
    CHECK(vos_ts_migration_confirm(&mscr, &tp, &cav, sub_roots, 2u, 55u, 1u, &mig_w) == VOS_TS_ERR_ROOT_MISMATCH,
          "substituted root confirmation refused");

    /* Exact root confirmation issues witness and consumes cleanly. */
    CHECK(vos_ts_migration_confirm(&mscr, &tp, &cav, roots, 2u, 55u, 1u, &mig_w) == VOS_TS_OK,
          "exact root confirmation succeeds");
    CHECK(vos_ts_migration_consume_transfer(&mscr, &tp, &mig_w, 7u, 55u, 1u) == VOS_TS_OK,
          "migration witness transfer consume");
    CHECK(vos_ts_migration_consume_transfer(&mscr, &tp, &mig_w, 7u, 55u, 1u) == VOS_TS_ERR_NOT_APPRAISED ||
          vos_ts_verify_and_consume_witness(&tp, &mig_w, VOS_TS_FLOW_DEVICE_MIGRATION,
                                            7u, 55u, 1u, 0u, mscr.root_digest) == VOS_TS_ERR_REPLAY,
          "migration witness cannot replay");
    vos_ts_migration_abort(&mscr, VOS_TS_EXIT_COMPLETE);
    CHECK(all_zero(mscr.roots, sizeof(mscr.roots)), "migration roots wiped");
    return 0;
}

int main(void)
{
    if (test_ba_display_and_one_time_wipe() != 0) {
        return 1;
    }
    if (test_ba_consent_and_schema_restore() != 0) {
        return 1;
    }
    if (test_ba_migrate_roots_and_appraisal() != 0) {
        return 1;
    }
    printf("trusted_screen_test: ok\n");
    return 0;
}
