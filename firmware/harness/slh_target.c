// SPDX-License-Identifier: Apache-2.0
// One translation unit for the selected purecap backend, with no external
// runtime dependency. Input capabilities come from the target composition.
#include "../crypto/keccak.c"
#include "../crypto/slh256s.c"

int main(const uint8_t *public_key, const uint8_t *message,
         const uint8_t *signature) {
  return vos_boot_slh256s_verify(NULL, message, VOS_BOOT_SIGNED_BYTES,
                                 signature, public_key) == VOS_SIG_ACCEPT ? 0 : 1;
}
