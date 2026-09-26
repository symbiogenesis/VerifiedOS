// SPDX-License-Identifier: Apache-2.0
// Host-only comparison driver. stdio is deliberately outside the verifier.
#include <stdio.h>
#include <string.h>
#include "vos_signature.h"

static uint8_t pk[2593], message[65537], context[256], signature[65537];
static uint8_t image[VOS_BOOT_HEADER_BYTES + 65536], window[65536], handoff[VOS_HANDOFF_BYTES];

static size_t read_file(const char *path, uint8_t *out, size_t capacity) {
  FILE *f = fopen(path, "rb");
  if (!f) return (size_t)-1;
  size_t size = fread(out, 1, capacity, f);
  int extra = fgetc(f), failed = ferror(f);
  fclose(f);
  return failed || extra != EOF ? (size_t)-1 : size;
}
static void release(void *count) { (*(unsigned *)count)++; }

int main(int argc, char **argv) {
  if (argc == 2 && !strcmp(argv[1], "bounds")) {
    // Declared invalid lengths refuse before even null storage is read.
    int accepted = vos_slh256s_verify_internal(NULL, 64, NULL, 65537, NULL, 29792)
      | vos_slh256s_verify(NULL, 64, NULL, 0, NULL, 256, NULL, 29792)
      | vos_mldsa87_verify(NULL, 2592, NULL, 65537, NULL, 0, NULL, 4627)
      | vos_mldsa87_verify(NULL, 2592, NULL, 0, NULL, 256, NULL, 4627)
      | vos_mldsa87_verify_mu(NULL, 2592, NULL, 65, NULL, 4627)
      | (vos_boot_slh256s_verify(NULL, NULL, VOS_BOOT_SIGNED_BYTES+1, NULL, NULL) == VOS_SIG_ACCEPT);
    printf("%d\n", accepted);
    return 0;
  }
  if (argc == 4 && !strcmp(argv[1], "boot")) {
    size_t p = read_file(argv[2], pk, sizeof pk);
    size_t n = read_file(argv[3], image, sizeof image);
    if (p != 64 || n == (size_t)-1) return 2;
    vos_rot_inputs inputs = {VOS_LIFECYCLE_PRODUCTION, 1, 0, 2};
    vos_rot_policy policy = {0};
    policy.root[VOS_LIFECYCLE_PRODUCTION] = pk;
    policy.verify = vos_boot_slh256s_verify;
    policy.load_base = VOS_BRINGUP_MMODE_LOAD_BASE;
    policy.region_bytes = sizeof window;
    vos_sram_windows sram = {window, sizeof window, handoff, sizeof handoff};
    vos_boot_result result;
    unsigned releases = 0, nonzero = 0, changed = 0;
    memset(window, 0xa5, sizeof window);
    memset(handoff, 0xa5, sizeof handoff);
    vos_boot_verdict verdict = vos_rot_boot_mmode(image, n, &inputs, &policy, &sram, release, &releases, &result);
    for (unsigned i = 0; i < sizeof window; i++) nonzero += window[i] != 0;
    for (unsigned i = 0; i < sizeof handoff; i++) changed += handoff[i] != 0xa5;
    int placed = n >= VOS_BOOT_HEADER_BYTES && result.payload_length <= sizeof window
      && n - VOS_BOOT_HEADER_BYTES >= result.payload_length
      && !memcmp(window, image + VOS_BOOT_HEADER_BYTES, (size_t)result.payload_length);
    printf("%s %u %u %u %d %u\n", vos_boot_verdict_name(verdict), releases, nonzero, changed, placed, result.measured.count);
    return 0;
  }
  if (argc != 6) return 2;
  size_t p = read_file(argv[2], pk, sizeof pk);
  size_t m = read_file(argv[3], message, sizeof message);
  size_t c = read_file(argv[4], context, sizeof context);
  size_t s = read_file(argv[5], signature, sizeof signature);
  if (p == (size_t)-1 || m == (size_t)-1 || c == (size_t)-1 || s == (size_t)-1) return 2;
  int valid;
  if (!strcmp(argv[1], "slh")) valid = vos_slh256s_verify(pk,p,message,m,context,c,signature,s);
  else if (!strcmp(argv[1], "slh-internal")) valid = vos_slh256s_verify_internal(pk,p,message,m,signature,s);
  else if (!strcmp(argv[1], "mldsa")) valid = vos_mldsa87_verify(pk,p,message,m,context,c,signature,s);
  else if (!strcmp(argv[1], "mldsa-internal")) valid = vos_mldsa87_verify_internal(pk,p,message,m,signature,s);
  else if (!strcmp(argv[1], "mldsa-mu")) valid = vos_mldsa87_verify_mu(pk,p,message,m,signature,s);
  else return 2;
  printf("%d\n", valid);
  return 0;
}
