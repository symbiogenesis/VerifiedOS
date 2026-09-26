// SPDX-License-Identifier: Apache-2.0
// Functional, allocation-free signature verification. No target timing claim.
#ifndef VOS_SIGNATURE_H
#define VOS_SIGNATURE_H
#include <stddef.h>
#include <stdint.h>
#include "vos_boot.h"

#define VOS_SLH256S_PUBLIC_BYTES 64u
#define VOS_SLH256S_SIGNATURE_BYTES 29792u
#define VOS_MLDSA87_PUBLIC_BYTES 2592u
#define VOS_MLDSA87_SIGNATURE_BYTES 4627u
// Resource bound for these byte-message interfaces, not a FIPS parameter.
#define VOS_SIGNATURE_MESSAGE_MAX 65536u

// FIPS 205 Algorithm 20: internal message, with no external framing added.
int vos_slh256s_verify_internal(const uint8_t *pk, size_t pk_len,
  const uint8_t *message, size_t message_len, const uint8_t *sig, size_t sig_len);
// Pure external interfaces: prefix 0 || context length || context is bound.
// A null pointer is permitted only for a zero-length message or context.
// All lengths are checked before any input is read. Oversized inputs refuse.
int vos_slh256s_verify(const uint8_t *pk, size_t pk_len,
  const uint8_t *message, size_t message_len, const uint8_t *context,
  size_t context_len, const uint8_t *sig, size_t sig_len);
int vos_mldsa87_verify(const uint8_t *pk, size_t pk_len,
  const uint8_t *message, size_t message_len, const uint8_t *context,
  size_t context_len, const uint8_t *sig, size_t sig_len);
int vos_mldsa87_verify_internal(const uint8_t *pk, size_t pk_len,
  const uint8_t *message, size_t message_len, const uint8_t *sig, size_t sig_len);
// Test/composition boundary: authenticating mu belongs to its caller.
int vos_mldsa87_verify_mu(const uint8_t *pk, size_t pk_len,
  const uint8_t *mu, size_t mu_len, const uint8_t *sig, size_t sig_len);

// Bind this function to vos_rot_policy.verify. The boot contract uses the
// internal algorithm over exactly its signed prefix, not the pure wrapper.
vos_sig_result vos_boot_slh256s_verify(void *context, const uint8_t *message,
  size_t message_len, const uint8_t *signature, const uint8_t *public_key);
#endif
