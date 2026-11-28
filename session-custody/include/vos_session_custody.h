// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_SESSION_CUSTODY_H
#define VOS_SESSION_CUSTODY_H

#include <stddef.h>
#include <stdint.h>

#include "vos_attested_tls.h"

/* Protocol interface modeled in [AttestedCustodyBridge.v](../../proofs/AttestedCustodyBridge.v)
 * and [attested-tls-protocol.md](../../docs/implementation/attested-tls-protocol.md). */

#define VOS_SC_EXPORTER_LABEL "EXPORTER-Channel-Binding"

enum {
    VOS_SC_EXPORTER_LABEL_BYTES = 24u,
    VOS_SC_KEY_BYTES = VOS_CRYPTO_KEY_BYTES_256,
    VOS_SC_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_SC_MAX_CONTEXTS = 16u,
    VOS_SC_MAX_CREDENTIALS = 8u,
    VOS_SC_MAX_SPENT_CONTEXTS = 32u
};

enum vos_sc_status {
    VOS_SC_OK = 0,
    VOS_SC_ERR_INVALID = -1,
    VOS_SC_ERR_BOUNDS = -2,
    VOS_SC_ERR_INELIGIBLE_TLS = -3,
    VOS_SC_ERR_HANDLE_AUTH = -4,
    VOS_SC_ERR_TEARDOWN = -5,
    VOS_SC_ERR_SPENT_CONTEXT = -6,
    VOS_SC_ERR_CONFIG_DIGEST = -7,
    VOS_SC_ERR_CREDENTIAL_AUTH = -8,
    VOS_SC_ERR_ATLS = -9,
    VOS_SC_ERR_CAPACITY = -10,
    VOS_SC_ERR_KEY_CUSTODY = -11
};

/* Opaque, MAC-authenticated TLS context handle. Carries no traffic key,
 * exporter, or mutable measurement field. */
struct vos_sc_context_handle {
    uint32_t slot;
    uint64_t context_id;
    uint64_t lifecycle_epoch;
    uint8_t sealed;
    uint8_t handle_mac[VOS_SC_DIGEST_BYTES];
};

/* Opaque, MAC-authenticated credential handle bound to a vault account slot. */
struct vos_sc_cred_handle {
    uint32_t slot;
    uint64_t cred_id;
    uint64_t lifecycle_epoch;
    uint8_t sealed;
    uint8_t handle_mac[VOS_SC_DIGEST_BYTES];
};

/* Registration record supplied by the TLS handshake boundary. */
struct vos_sc_tls_registration {
    uint64_t unit_id;
    uint32_t principal_len;
    uint8_t principal[VOS_ATLS_MAX_PRINCIPAL_BYTES];
    uint32_t origin_len;
    uint8_t origin[VOS_ATLS_MAX_ORIGIN_BYTES];
    uint8_t config_digest[VOS_SC_DIGEST_BYTES];
    uint8_t traffic_key[VOS_SC_KEY_BYTES];
    uint8_t handshake_complete;
    uint8_t server_authenticated;
    uint8_t early_data;
    uint8_t resumed;
};

struct vos_sc_context_slot {
    uint8_t active;
    uint8_t retired;
    uint8_t key_exposed;
    uint64_t context_id;
    uint64_t lifecycle_epoch;
    uint64_t unit_id;
    uint32_t principal_len;
    uint8_t principal[VOS_ATLS_MAX_PRINCIPAL_BYTES];
    uint32_t origin_len;
    uint8_t origin[VOS_ATLS_MAX_ORIGIN_BYTES];
    uint8_t config_digest[VOS_SC_DIGEST_BYTES];
    uint8_t traffic_key[VOS_SC_KEY_BYTES];
    uint8_t derived_exporter[VOS_ATLS_EXPORTER_BYTES];
    uint8_t handshake_complete;
    uint8_t server_authenticated;
    uint8_t early_data;
    uint8_t resumed;
};

struct vos_sc_cred_slot {
    uint8_t active;
    uint64_t cred_id;
    uint64_t lifecycle_epoch;
    struct vos_atls_credential cred;
};

struct vos_sc_vault {
    uint8_t initialized;
    uint64_t lifecycle_epoch;
    uint64_t next_context_id;
    uint64_t next_cred_id;
    uint8_t vault_custody_key[VOS_SC_KEY_BYTES];
    uint8_t expected_config_digest[VOS_SC_DIGEST_BYTES];
    struct vos_crypto_core crypto_core;
    struct vos_atls_broker broker;
    uint32_t account_charges[VOS_ATLS_MAX_ACCOUNTS];
    struct vos_sc_context_slot contexts[VOS_SC_MAX_CONTEXTS];
    struct vos_sc_cred_slot creds[VOS_SC_MAX_CREDENTIALS];
    uint32_t spent_context_count;
    uint64_t spent_contexts[VOS_SC_MAX_SPENT_CONTEXTS];
};

struct vos_sc_session {
    uint8_t initialized;
    uint8_t attested_open;
    uint64_t bound_lifecycle_epoch;
    uint8_t expected_config_digest[VOS_SC_DIGEST_BYTES];
    struct vos_sc_context_handle bound_handle;
    struct vos_atls_connection conn;
    uint32_t spent_count;
    uint64_t spent_ids[VOS_SC_MAX_SPENT_CONTEXTS];
};

enum vos_sc_status vos_sc_vault_init(struct vos_sc_vault *vault,
                                     const uint8_t hmac_key[VOS_SC_KEY_BYTES],
                                     const uint8_t custody_key[VOS_SC_KEY_BYTES],
                                     const uint8_t config_digest[VOS_SC_DIGEST_BYTES],
                                     uint64_t server_now);

enum vos_sc_status vos_sc_set_measurement(struct vos_sc_vault *vault,
                                          uint64_t unit_id,
                                          uint64_t generation);

enum vos_sc_status vos_sc_set_alias(struct vos_sc_vault *vault,
                                    const uint8_t *origin,
                                    uint32_t origin_len,
                                    uint64_t unit_id,
                                    const uint8_t *alias,
                                    uint32_t alias_len);

enum vos_sc_status vos_sc_register_tls_context(struct vos_sc_vault *vault,
                                               const struct vos_sc_tls_registration *reg,
                                               struct vos_sc_context_handle *out_handle);

enum vos_sc_status vos_sc_register_credential(struct vos_sc_vault *vault,
                                              const struct vos_atls_credential *cred,
                                              struct vos_sc_cred_handle *out_handle);

enum vos_sc_status vos_sc_delegate_credential(struct vos_sc_vault *vault,
                                              const struct vos_sc_cred_handle *parent_handle,
                                              const struct vos_atls_credential *child_spec,
                                              struct vos_sc_cred_handle *out_child_handle);

enum vos_sc_status vos_sc_derive_exporter_for_test(const struct vos_sc_vault *vault,
                                                   const struct vos_sc_context_handle *ctx_handle,
                                                   uint8_t out_exporter[VOS_ATLS_EXPORTER_BYTES]);

enum vos_sc_status vos_sc_quote_session(struct vos_sc_vault *vault,
                                        const struct vos_atls_profile *profile,
                                        const struct vos_atls_cred_policy *cred_policy,
                                        const struct vos_sc_cred_handle *cred_handle,
                                        const struct vos_sc_context_handle *ctx_handle,
                                        const struct vos_atls_client_request *request,
                                        const uint8_t *challenge_wire,
                                        size_t challenge_wire_len,
                                        uint8_t *out_evidence_wire,
                                        size_t out_evidence_cap,
                                        size_t *out_evidence_len);

enum vos_sc_status vos_sc_teardown_context(struct vos_sc_vault *vault,
                                           const struct vos_sc_context_handle *ctx_handle);

enum vos_sc_status vos_sc_advance_lifecycle(struct vos_sc_vault *vault);

enum vos_sc_status vos_sc_retire_unit_generation(struct vos_sc_vault *vault,
                                                 uint64_t unit_id,
                                                 uint64_t new_generation);

enum vos_sc_status vos_sc_mark_key_exposed(struct vos_sc_vault *vault,
                                           const struct vos_sc_context_handle *ctx_handle);

enum vos_sc_status vos_sc_session_open(struct vos_sc_session *session,
                                       const struct vos_sc_vault *vault,
                                       const struct vos_sc_context_handle *ctx_handle,
                                       const uint8_t expected_config_digest[VOS_SC_DIGEST_BYTES]);

enum vos_sc_status vos_sc_session_begin(struct vos_sc_session *session,
                                        struct vos_sc_vault *vault,
                                        const struct vos_atls_profile *profile,
                                        const struct vos_atls_appraisal_policy *policy,
                                        const uint8_t *nonce,
                                        uint32_t nonce_len,
                                        uint64_t now,
                                        uint64_t deadline,
                                        uint8_t *out_challenge_wire,
                                        size_t cap,
                                        size_t *out_len);

enum vos_sc_status vos_sc_session_decide(struct vos_sc_session *session,
                                         const struct vos_sc_vault *vault,
                                         const struct vos_atls_profile *profile,
                                         const struct vos_atls_appraisal_policy *policy,
                                         const uint8_t hmac_key[VOS_SC_KEY_BYTES],
                                         uint64_t now,
                                         const uint8_t *evidence_wire,
                                         size_t evidence_wire_len);

enum vos_sc_status vos_sc_session_fetch_one(struct vos_sc_session *session,
                                            const struct vos_sc_vault *vault,
                                            const struct vos_atls_profile *profile,
                                            uint64_t now,
                                            const uint8_t *req_wire,
                                            size_t req_wire_len,
                                            uint32_t manifest_authenticated,
                                            uint32_t object_matches,
                                            const uint8_t *object_bytes,
                                            uint32_t object_len,
                                            uint8_t *out_reply_wire,
                                            size_t cap,
                                            size_t *out_reply_len);

enum vos_sc_status vos_sc_session_reconnect(struct vos_sc_session *session,
                                            const struct vos_sc_vault *vault,
                                            const struct vos_sc_context_handle *new_ctx_handle,
                                            const uint8_t expected_config_digest[VOS_SC_DIGEST_BYTES]);

void vos_sc_session_close(struct vos_sc_session *session, struct vos_sc_vault *vault);

#endif
