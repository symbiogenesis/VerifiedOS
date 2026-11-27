// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_ATTESTED_TLS_H
#define VOS_ATTESTED_TLS_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

#define VOS_ATLS_DOMAIN_STR "VerifiedOS/Q22c/TLS-attestation/v1"
#define VOS_ATLS_ROLE_STR "tls-attesting-client"

enum {
    VOS_ATLS_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_ATLS_EXPORTER_BYTES = 32u,
    VOS_ATLS_DOMAIN_BYTES = 35u,
    VOS_ATLS_ROLE_BYTES = 20u,
    VOS_ATLS_MAX_DOMAIN_BYTES = 64u,
    VOS_ATLS_MAX_ORIGIN_BYTES = 64u,
    VOS_ATLS_MAX_NONCE_BYTES = 32u,
    VOS_ATLS_MAX_PRINCIPAL_BYTES = 64u,
    VOS_ATLS_MAX_ROLE_BYTES = 32u,
    VOS_ATLS_MAX_ALIAS_BYTES = 64u,
    VOS_ATLS_MAX_REQUEST_BYTES = 128u,
    VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES = 175u,
    VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES = 512u,
    VOS_ATLS_MAX_MANIFEST_BYTES = 256u,
    VOS_ATLS_MAX_OBJECT_ID_BYTES = 64u,
    VOS_ATLS_MAX_OBJECT_BYTES = 256u,
    VOS_ATLS_MAX_FETCH_REQ_WIRE_BYTES = 364u,
    VOS_ATLS_MAX_FETCH_REP_WIRE_BYTES = 367u,
    VOS_ATLS_MAX_USED_NONCES = 32u,
    VOS_ATLS_MAX_USED_CONTEXTS = 32u,
    VOS_ATLS_MAX_ACCOUNTS = 8u,
    VOS_ATLS_MAX_MEASUREMENTS = 8u,
    VOS_ATLS_MAX_ALIASES = 16u,
    VOS_ATLS_MAX_APPROVED_GENS = 8u,
    VOS_ATLS_SCOPE_SOFTWARE = 0u,
    VOS_ATLS_SCOPE_UNIT = 1u,
    VOS_ATLS_SCOPE_MASK_SOFTWARE = 1u,
    VOS_ATLS_SCOPE_MASK_UNIT = 2u,
    VOS_ATLS_OP_ATTEST_LOCAL_SESSION = 1u,
    VOS_ATLS_REPLY_OK = 0u,
    VOS_ATLS_REPLY_REFUSED = 1u
};

enum vos_atls_status {
    VOS_ATLS_OK = 0,
    VOS_ATLS_ERR_INVALID = -1,
    VOS_ATLS_ERR_BOUNDS = -2,
    VOS_ATLS_ERR_WIRE_FORMAT = -3,
    VOS_ATLS_ERR_INELIGIBLE_CONTEXT = -4,
    VOS_ATLS_ERR_CREDENTIAL_AUTH = -5,
    VOS_ATLS_ERR_MEASUREMENT = -6,
    VOS_ATLS_ERR_ALIAS = -7,
    VOS_ATLS_ERR_PHASE = -8,
    VOS_ATLS_ERR_NONCE_REPLAY = -9,
    VOS_ATLS_ERR_SPENT_CONTEXT = -10,
    VOS_ATLS_ERR_DEADLINE = -11,
    VOS_ATLS_ERR_AUTHENTICITY = -12,
    VOS_ATLS_ERR_CHALLENGE_MISMATCH = -13,
    VOS_ATLS_ERR_EXPORTER_MISMATCH = -14,
    VOS_ATLS_ERR_POLICY = -15,
    VOS_ATLS_ERR_IDENTITY_SCOPE = -16,
    VOS_ATLS_ERR_FETCH = -17,
    VOS_ATLS_ERR_HISTORY_FULL = -18,
    VOS_ATLS_ERR_BUFFER = -19
};

enum vos_atls_phase {
    VOS_ATLS_PHASE_FRESH = 0,
    VOS_ATLS_PHASE_WAITING = 1,
    VOS_ATLS_PHASE_OPEN = 2,
    VOS_ATLS_PHASE_CLOSED = 3
};

struct vos_atls_profile {
    uint32_t domain_len;
    uint8_t domain[VOS_ATLS_MAX_DOMAIN_BYTES];
    uint32_t attester_role_len;
    uint8_t attester_role[VOS_ATLS_MAX_ROLE_BYTES];
    uint32_t attest_operation;
    uint32_t challenge_bound;
    uint32_t request_bound;
    uint32_t evidence_bound;
    uint32_t manifest_bound;
    uint32_t object_bound;
};

struct vos_atls_protected_context {
    uint64_t context_id;
    uint64_t unit_id; /* Protected local custody of traffic-key holder; never transmitted. */
    uint32_t principal_len;
    uint8_t principal[VOS_ATLS_MAX_PRINCIPAL_BYTES];
    uint32_t origin_len;
    uint8_t origin[VOS_ATLS_MAX_ORIGIN_BYTES];
    uint8_t exporter[VOS_ATLS_EXPORTER_BYTES];
    uint8_t handshake_complete;
    uint8_t server_authenticated;
    uint8_t early_data;
    uint8_t resumed;
};

struct vos_atls_challenge {
    uint8_t unit_scope;
    uint32_t nonce_len;
    uint8_t nonce[VOS_ATLS_MAX_NONCE_BYTES];
    uint32_t origin_len;
    uint8_t origin[VOS_ATLS_MAX_ORIGIN_BYTES];
    uint32_t domain_len;
    uint8_t domain[VOS_ATLS_MAX_DOMAIN_BYTES];
};

struct vos_atls_evidence {
    uint64_t generation;
    uint8_t exporter[VOS_ATLS_EXPORTER_BYTES];
    struct vos_atls_challenge challenge;
    uint32_t principal_len;
    uint8_t principal[VOS_ATLS_MAX_PRINCIPAL_BYTES];
    uint32_t role_len;
    uint8_t role[VOS_ATLS_MAX_ROLE_BYTES];
    uint8_t has_alias;
    uint32_t alias_len;
    uint8_t alias[VOS_ATLS_MAX_ALIAS_BYTES];
    uint8_t seal_mac[VOS_ATLS_DIGEST_BYTES];
};

struct vos_atls_fetch_request {
    uint32_t object_id_len;
    uint8_t object_id[VOS_ATLS_MAX_OBJECT_ID_BYTES];
    uint32_t manifest_ref_len;
    uint8_t manifest_ref[VOS_ATLS_MAX_MANIFEST_BYTES];
    uint8_t expected_digest[VOS_ATLS_DIGEST_BYTES];
};

struct vos_atls_fetch_reply {
    uint8_t status;
    uint32_t object_id_len;
    uint8_t object_id[VOS_ATLS_MAX_OBJECT_ID_BYTES];
    uint32_t object_len;
    uint8_t object_bytes[VOS_ATLS_MAX_OBJECT_BYTES];
    uint8_t object_sha256[VOS_ATLS_DIGEST_BYTES];
};

struct vos_atls_credential {
    uint8_t sealed;
    uint64_t unit_id;
    uint32_t role_len;
    uint8_t role[VOS_ATLS_MAX_ROLE_BYTES];
    uint32_t principal_len;
    uint8_t principal[VOS_ATLS_MAX_PRINCIPAL_BYTES];
    uint32_t origin_len;
    uint8_t origin[VOS_ATLS_MAX_ORIGIN_BYTES];
    uint32_t scope_mask;
    uint32_t operation_mask;
    uint32_t domain_len;
    uint8_t domain[VOS_ATLS_MAX_DOMAIN_BYTES];
    uint32_t use_ceiling;
    uint64_t expiry;
    uint32_t account_id;
};

struct vos_atls_client_request {
    /* Client request carries no exporter argument; broker reads exporter from ProtectedContext. */
    uint32_t role_len;
    uint8_t role[VOS_ATLS_MAX_ROLE_BYTES];
    uint32_t principal_len;
    uint8_t principal[VOS_ATLS_MAX_PRINCIPAL_BYTES];
    uint8_t scope;
    uint32_t operation;
    uint32_t domain_len;
    uint8_t domain[VOS_ATLS_MAX_DOMAIN_BYTES];
    uint32_t request_len;
    uint8_t request_bytes[VOS_ATLS_MAX_REQUEST_BYTES];
};

typedef int (*vos_atls_consent_fn)(const struct vos_atls_credential *cred,
                                   const struct vos_atls_client_request *req,
                                   uint32_t used_count,
                                   void *ctx);

struct vos_atls_cred_policy {
    uint32_t request_limit;
    uint32_t allowed_operation_mask;
    uint8_t needs_approval;
};

struct vos_atls_measurement_entry {
    uint8_t present;
    uint64_t unit_id;
    uint64_t generation;
};

struct vos_atls_alias_entry {
    uint8_t present;
    uint64_t unit_id;
    uint32_t origin_len;
    uint8_t origin[VOS_ATLS_MAX_ORIGIN_BYTES];
    uint32_t alias_len;
    uint8_t alias[VOS_ATLS_MAX_ALIAS_BYTES];
};

struct vos_atls_broker {
    uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256];
    uint64_t server_now;
    uint32_t account_used[VOS_ATLS_MAX_ACCOUNTS];
    vos_atls_consent_fn consent_allows;
    void *consent_ctx;
    struct vos_atls_measurement_entry measurements[VOS_ATLS_MAX_MEASUREMENTS];
    struct vos_atls_alias_entry aliases[VOS_ATLS_MAX_ALIASES];
};

struct vos_atls_appraisal_policy {
    uint32_t approved_gen_count;
    uint64_t approved_generations[VOS_ATLS_MAX_APPROVED_GENS];
    uint32_t required_principal_len;
    uint8_t required_principal[VOS_ATLS_MAX_PRINCIPAL_BYTES];
    uint8_t unit_policy;
    uint32_t expected_alias_len;
    uint8_t expected_alias[VOS_ATLS_MAX_ALIAS_BYTES];
};

struct vos_atls_nonce_record {
    uint32_t len;
    uint8_t bytes[VOS_ATLS_MAX_NONCE_BYTES];
};

struct vos_atls_connection {
    struct vos_atls_protected_context ctx;
    enum vos_atls_phase phase;
    struct vos_atls_challenge pending_challenge;
    uint64_t pending_deadline;
    uint32_t used_nonce_count;
    struct vos_atls_nonce_record used_nonces[VOS_ATLS_MAX_USED_NONCES];
    uint32_t used_context_count;
    uint64_t used_contexts[VOS_ATLS_MAX_USED_CONTEXTS];
};

void vos_atls_profile_default_init(struct vos_atls_profile *profile);

int vos_atls_profile_bounded(const struct vos_atls_profile *profile);

int vos_atls_context_usable(const struct vos_atls_protected_context *ctx);

int vos_atls_policy_valid(const struct vos_atls_appraisal_policy *policy);

enum vos_atls_status vos_atls_encode_challenge(const struct vos_atls_profile *profile,
                                               const struct vos_atls_challenge *chal,
                                               uint8_t *out,
                                               size_t cap,
                                               size_t *out_len);

enum vos_atls_status vos_atls_decode_challenge(const struct vos_atls_profile *profile,
                                               const uint8_t *wire,
                                               size_t wire_len,
                                               struct vos_atls_challenge *out);

enum vos_atls_status vos_atls_encode_evidence(const struct vos_atls_profile *profile,
                                              const struct vos_atls_evidence *ev,
                                              uint8_t *out,
                                              size_t cap,
                                              size_t *out_len);

enum vos_atls_status vos_atls_decode_evidence(const struct vos_atls_profile *profile,
                                              const uint8_t *wire,
                                              size_t wire_len,
                                              struct vos_atls_evidence *out);

enum vos_atls_status vos_atls_encode_fetch_request(const struct vos_atls_profile *profile,
                                                   const struct vos_atls_fetch_request *req,
                                                   uint8_t *out,
                                                   size_t cap,
                                                   size_t *out_len);

enum vos_atls_status vos_atls_decode_fetch_request(const struct vos_atls_profile *profile,
                                                   const uint8_t *wire,
                                                   size_t wire_len,
                                                   struct vos_atls_fetch_request *out);

enum vos_atls_status vos_atls_encode_fetch_reply(const struct vos_atls_profile *profile,
                                                 const struct vos_atls_fetch_reply *rep,
                                                 uint8_t *out,
                                                 size_t cap,
                                                 size_t *out_len);

enum vos_atls_status vos_atls_decode_fetch_reply(const struct vos_atls_profile *profile,
                                                 const uint8_t *wire,
                                                 size_t wire_len,
                                                 struct vos_atls_fetch_reply *out);

void vos_atls_broker_init(struct vos_atls_broker *broker,
                          const uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256],
                          uint64_t server_now);

enum vos_atls_status vos_atls_broker_set_measurement(struct vos_atls_broker *broker,
                                                     uint64_t unit_id,
                                                     uint64_t generation);

enum vos_atls_status vos_atls_broker_set_alias(struct vos_atls_broker *broker,
                                               const uint8_t *origin,
                                               uint32_t origin_len,
                                               uint64_t unit_id,
                                               const uint8_t *alias,
                                               uint32_t alias_len);

enum vos_atls_status vos_atls_delegate_credential(const struct vos_atls_credential *parent,
                                                  struct vos_atls_credential *child);

enum vos_atls_status vos_atls_issue_local(const struct vos_atls_profile *profile,
                                          const struct vos_atls_cred_policy *cred_policy,
                                          const struct vos_atls_credential *credential,
                                          struct vos_atls_broker *broker,
                                          const struct vos_atls_client_request *request,
                                          const struct vos_atls_protected_context *ctx,
                                          const struct vos_atls_challenge *challenge,
                                          struct vos_atls_evidence *out_evidence,
                                          uint8_t *out_wire,
                                          size_t out_wire_cap,
                                          size_t *out_wire_len);

void vos_atls_connection_init(struct vos_atls_connection *conn,
                              const struct vos_atls_protected_context *initial_ctx);

enum vos_atls_status vos_atls_begin_appraisal(const struct vos_atls_profile *profile,
                                              const struct vos_atls_appraisal_policy *policy,
                                              struct vos_atls_connection *conn,
                                              const uint8_t *nonce,
                                              uint32_t nonce_len,
                                              uint64_t now,
                                              uint64_t deadline,
                                              uint8_t *out_challenge_wire,
                                              size_t cap,
                                              size_t *out_len);

enum vos_atls_status vos_atls_decide(const struct vos_atls_profile *profile,
                                     const struct vos_atls_appraisal_policy *policy,
                                     const uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256],
                                     struct vos_atls_connection *conn,
                                     uint64_t now,
                                     const uint8_t *evidence_wire,
                                     size_t evidence_wire_len);

enum vos_atls_status vos_atls_fetch_one(const struct vos_atls_profile *profile,
                                        struct vos_atls_connection *conn,
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

enum vos_atls_status vos_atls_reconnect(struct vos_atls_connection *conn,
                                        const struct vos_atls_protected_context *new_ctx);

void vos_atls_close(struct vos_atls_connection *conn);

#endif
