// SPDX-License-Identifier: Apache-2.0
// Compile one real interface at a time. All pointers are bounded, read-only
// capabilities supplied by the comparison composition; lengths stay explicit.
#include "keccak.c"
#if VOS_TARGET_SCHEME == 1
#include "slh256s.c"
#else
#include "mldsa87.c"
#endif

int main(const uint8_t *pk, size_t pk_len, const uint8_t *message,
         size_t message_len, const uint8_t *context, size_t context_len,
         const uint8_t *signature, size_t signature_len) {
  int accepted;
#if VOS_TARGET_SCHEME == 1
#if VOS_TARGET_INTERFACE == 1
  accepted = vos_slh256s_verify(pk, pk_len, message, message_len,
                               context, context_len, signature, signature_len);
#else
  (void)context; (void)context_len;
  accepted = vos_slh256s_verify_internal(pk, pk_len, message, message_len,
                                        signature, signature_len);
#endif
#else
#if VOS_TARGET_INTERFACE == 1
  accepted = vos_mldsa87_verify(pk, pk_len, message, message_len,
                               context, context_len, signature, signature_len);
#elif VOS_TARGET_INTERFACE == 2
  (void)context; (void)context_len;
  accepted = vos_mldsa87_verify_internal(pk, pk_len, message, message_len,
                                        signature, signature_len);
#else
  (void)context; (void)context_len;
  accepted = vos_mldsa87_verify_mu(pk, pk_len, message, message_len,
                                  signature, signature_len);
#endif
#endif
  return accepted ? 0 : 1;
}
