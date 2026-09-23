// SPDX-License-Identifier: Apache-2.0
// The boot-handoff harness's host driver for the RoT stage. Not firmware.
//
// It runs firmware/rot/boot_verify.c compiled for the host, standing in for
// the RoT hart until the purecap backend and M1.7's target path can build that
// file for the RoT composition. Main SRAM is two host buffers, release is a
// flag, and the verdict is printed as key=value lines that
// tools/vos/boot_handoff.py reads.
//
// **The fixture signature verifier below is not a signature scheme.** It
// accepts exactly SHAKE256(FIXTURE_DOMAIN || public key || message) at the
// SLH-DSA-SHAKE-256s signature size, which anyone holding the public key can
// compute. It exists so the harness can exercise the verdict path a real
// verifier's accept and reject would take; the production binding is the
// SLH-DSA-SHAKE-256s verifier the contract assigns to M3.4.
//
// The racing arm of the same verifier stands for another requester writing the
// caller's input while the release runs: when called, it first writes a given
// security version into the caller's image buffer, then checks the message it
// was handed. A release that verified the buffer rather than its own copy of
// the signed prefix would verify the rewritten bytes.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vos_boot.h"
#include "vos_keccak.h"

#define FIXTURE_DOMAIN "VOS-FIXTURE-SIG1"

static uint8_t fixture_expected[VOS_BOOT_SIGNATURE_BYTES];

typedef struct {
  uint8_t *image;
  uint64_t version;
} race_context;

static vos_sig_result fixture_verify(void *context, const uint8_t *message,
                                     size_t message_len, const uint8_t *signature,
                                     const uint8_t *public_key) {
  if (context != NULL) {
    race_context *race = context;
    for (unsigned i = 0; i < 8; i++) {
      race->image[VOS_BOOT_HDR_SECURITY_VERSION + i] = (uint8_t)(race->version >> (8u * i));
    }
  }
  vos_shake256_ctx ctx;
  vos_shake256_init(&ctx);
  (void)vos_shake256_absorb(&ctx, (const uint8_t *)FIXTURE_DOMAIN, 16);
  (void)vos_shake256_absorb(&ctx, public_key, VOS_BOOT_PUBLIC_KEY_BYTES);
  (void)vos_shake256_absorb(&ctx, message, message_len);
  vos_shake256_squeeze(&ctx, fixture_expected, VOS_BOOT_SIGNATURE_BYTES);
  return memcmp(fixture_expected, signature, VOS_BOOT_SIGNATURE_BYTES) == 0
    ? VOS_SIG_ACCEPT : VOS_SIG_REJECT;
}

static int released;

static void on_release(void *context) {
  (void)context;
  released++;
}

static void print_hex(const char *key, const uint8_t *bytes, size_t len) {
  printf("%s=", key);
  for (size_t i = 0; i < len; i++) {
    printf("%02x", bytes[i]);
  }
  printf("\n");
}

static int parse_hex(const char *text, uint8_t *out, size_t len) {
  if (strlen(text) != 2 * len) {
    return 0;
  }
  for (size_t i = 0; i < len; i++) {
    unsigned value;
    if (sscanf(text + 2 * i, "%2x", &value) != 1) {
      return 0;
    }
    out[i] = (uint8_t)value;
  }
  return 1;
}

static uint8_t *read_file(const char *path, uint64_t *len) {
  FILE *f = fopen(path, "rb");
  if (f == NULL) {
    return NULL;
  }
  size_t capacity = 1 << 16, used = 0;
  uint8_t *buffer = malloc(capacity);
  while (buffer != NULL) {
    size_t got = fread(buffer + used, 1, capacity - used, f);
    used += got;
    if (used < capacity) {
      break;
    }
    capacity *= 2;
    uint8_t *grown = realloc(buffer, capacity);
    if (grown == NULL) {
      free(buffer);
    }
    buffer = grown;
  }
  fclose(f);
  *len = used;
  return buffer;
}

static int write_file(const char *path, const uint8_t *bytes, size_t len) {
  FILE *f = fopen(path, "wb");
  if (f == NULL) {
    return 0;
  }
  size_t put = fwrite(bytes, 1, len, f);
  return fclose(f) == 0 && put == len;
}

static const char *argument(int argc, char **argv, const char *key) {
  size_t n = strlen(key);
  for (int i = 2; i < argc; i++) {
    if (strncmp(argv[i], key, n) == 0 && argv[i][n] == '=') {
      return argv[i] + n + 1;
    }
  }
  return NULL;
}

static int shake_command(int argc, char **argv) {
  if (argc != 3) {
    fprintf(stderr, "usage: rot-stage shake256 OUT_BYTES < input\n");
    return 2;
  }
  size_t out_len = (size_t)strtoull(argv[2], NULL, 10);
  size_t capacity = 1 << 16, used = 0;
  uint8_t *in = malloc(capacity);
  size_t got;
  while (in != NULL && (got = fread(in + used, 1, capacity - used, stdin)) > 0) {
    used += got;
    if (used == capacity) {
      capacity *= 2;
      uint8_t *grown = realloc(in, capacity);
      if (grown == NULL) {
        free(in);
      }
      in = grown;
    }
  }
  uint8_t *out = malloc(out_len > 0 ? out_len : 1);
  if (in == NULL || out == NULL) {
    fprintf(stderr, "out of memory\n");
    return 2;
  }
  vos_shake256(out, out_len, in, used);
  print_hex("shake256", out, out_len);
  free(in);
  free(out);
  return 0;
}

// One SHAKE256 per input line "OUT_BYTES HEX_INPUT", one hex answer per line, so
// a comparison campaign costs one process rather than one per pair.
static int shake_lines_command(void) {
  static char line[1 << 17];
  static uint8_t in[1 << 16];
  static uint8_t out[1 << 12];
  while (fgets(line, sizeof line, stdin) != NULL) {
    char *space = strchr(line, ' ');
    if (space == NULL) {
      fprintf(stderr, "a line is OUT_BYTES HEX_INPUT\n");
      return 2;
    }
    *space = '\0';
    size_t out_len = (size_t)strtoull(line, NULL, 10);
    char *hex = space + 1;
    size_t hex_len = strcspn(hex, "\r\n");
    hex[hex_len] = '\0';
    if (out_len > sizeof out || hex_len % 2 != 0 || hex_len / 2 > sizeof in
        || !parse_hex(hex, in, hex_len / 2)) {
      fprintf(stderr, "a line exceeds the batch buffers or is not hex\n");
      return 2;
    }
    vos_shake256(out, out_len, in, hex_len / 2);
    for (size_t i = 0; i < out_len; i++) {
      printf("%02x", out[i]);
    }
    printf("\n");
  }
  return 0;
}

static const char *const root_keys[VOS_LIFECYCLE_COUNT] = {
  "root.raw", "root.test", "root.development", "root.production", "root.rma",
};

static int boot_command(int argc, char **argv) {
  const char *image_path = argument(argc, argv, "image");
  const char *lifecycle = argument(argc, argv, "lifecycle");
  const char *entropy = argument(argc, argv, "entropy");
  const char *target = argument(argc, argv, "target");
  const char *floor_text = argument(argc, argv, "floor");
  const char *verifier = argument(argc, argv, "verifier");
  const char *sram_path = argument(argc, argv, "sram");
  const char *handoff_path = argument(argc, argv, "handoff");
  const char *window_text = argument(argc, argv, "window");
  const char *race_text = argument(argc, argv, "race_version");
  if (!image_path || !lifecycle || !entropy || !target || !floor_text || !verifier
      || !sram_path || !handoff_path) {
    fprintf(stderr, "usage: rot-stage boot image= lifecycle= entropy= target= floor= "
                    "verifier=fixture|fixture-racing|absent sram= handoff= [window=BYTES] "
                    "[race_version=N] [root.STATE=HEX ...]\n");
    return 2;
  }
  static uint8_t roots[VOS_LIFECYCLE_COUNT][VOS_BOOT_PUBLIC_KEY_BYTES];
  vos_rot_policy policy;
  memset(&policy, 0, sizeof policy);
  for (unsigned s = 0; s < VOS_LIFECYCLE_COUNT; s++) {
    const char *hex = argument(argc, argv, root_keys[s]);
    if (hex != NULL) {
      if (!parse_hex(hex, roots[s], VOS_BOOT_PUBLIC_KEY_BYTES)) {
        fprintf(stderr, "%s is not %u hex bytes\n", root_keys[s], VOS_BOOT_PUBLIC_KEY_BYTES);
        return 2;
      }
      policy.root[s] = roots[s];
    }
  }
  race_context race = {NULL, 0};
  int racing = strcmp(verifier, "fixture-racing") == 0;
  if (strcmp(verifier, "fixture") == 0 || racing) {
    policy.verify = fixture_verify;
  } else if (strcmp(verifier, "absent") != 0) {
    fprintf(stderr, "verifier must be fixture, fixture-racing or absent\n");
    return 2;
  }
  if (racing != (race_text != NULL)) {
    fprintf(stderr, "race_version= goes with verifier=fixture-racing and only with it\n");
    return 2;
  }
  policy.load_base = VOS_BRINGUP_MMODE_LOAD_BASE;
  policy.region_bytes = VOS_BRINGUP_MMODE_REGION_BYTES;

  vos_rot_inputs inputs;
  inputs.lifecycle = (uint8_t)strtoul(lifecycle, NULL, 10);
  inputs.entropy_ok = (uint8_t)strtoul(entropy, NULL, 10);
  inputs.boot_target = (uint8_t)strtoul(target, NULL, 10);
  inputs.floor = strtoull(floor_text, NULL, 10);

  uint64_t image_len = 0;
  uint8_t *image = read_file(image_path, &image_len);
  if (image == NULL) {
    fprintf(stderr, "cannot read %s\n", image_path);
    return 2;
  }
  if (racing) {
    if (image_len < VOS_BOOT_SIGNED_BYTES) {
      fprintf(stderr, "a racing run needs the header's signed prefix\n");
      free(image);
      return 2;
    }
    race.image = image;
    race.version = strtoull(race_text, NULL, 10);
    policy.verify_context = &race;
  }
  // Main SRAM as the RoT's windows reach it, poisoned so a window the verifier
  // failed to scrub on refusal is visible below. `window=` hands the release a
  // shorter image window than the region, as a composition with too little
  // SRAM would.
  static uint8_t sram_image[VOS_BRINGUP_MMODE_REGION_BYTES];
  static uint8_t sram_handoff[VOS_HANDOFF_BYTES];
  uint64_t window = sizeof sram_image;
  if (window_text != NULL) {
    window = strtoull(window_text, NULL, 10);
    if (window > sizeof sram_image) {
      fprintf(stderr, "window= exceeds the region\n");
      free(image);
      return 2;
    }
  }
  memset(sram_image, 0xA5, sizeof sram_image);
  memset(sram_handoff, 0x5A, sizeof sram_handoff);
  vos_sram_windows sram = {sram_image, window, sram_handoff, sizeof sram_handoff};

  vos_boot_result result;
  vos_boot_verdict verdict = vos_rot_boot_mmode(image, image_len, &inputs, &policy, &sram,
                                                on_release, NULL, &result);
  free(image);

  // The window the release was handed is all zero; bytes past a short window
  // are not the release's to touch and must keep their poison.
  int image_zero = 1;
  for (size_t i = 0; i < sizeof sram_image; i++) {
    image_zero &= i < window ? sram_image[i] == 0 : sram_image[i] == 0xA5;
  }
  int handoff_untouched = 1;
  for (size_t i = 0; i < sizeof sram_handoff; i++) {
    handoff_untouched &= sram_handoff[i] == 0x5A;
  }

  printf("verdict=%s\n", vos_boot_verdict_name(verdict));
  printf("code=%d\n", (int)verdict);
  printf("released=%d\n", released);
  printf("security_version=%llu\n", (unsigned long long)result.security_version);
  printf("payload_length=%llu\n", (unsigned long long)result.payload_length);
  printf("digest_computed=%d\n", result.digest_computed);
  print_hex("image_digest", result.image_digest, VOS_BOOT_DIGEST_BYTES);
  print_hex("generation", result.measured.generation, VOS_MEASURE_BYTES);
  print_hex("device", result.measured.device, VOS_MEASURE_BYTES);
  print_hex("chain", result.chain, VOS_MEASURE_BYTES);
  printf("log=");
  for (unsigned i = 0; i < result.measured.count; i++) {
    printf(i ? ",%u" : "%u", result.measured.log[i]);
  }
  printf("\n");
  printf("image_window_zero=%d\n", image_zero);
  printf("handoff_window_untouched=%d\n", handoff_untouched);

  if (verdict == VOS_BOOT_RELEASE) {
    if (!write_file(sram_path, sram_image, sizeof sram_image)
        || !write_file(handoff_path, sram_handoff, sizeof sram_handoff)) {
      fprintf(stderr, "cannot write the placed windows\n");
      return 2;
    }
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc >= 2 && strcmp(argv[1], "shake256") == 0) {
    return shake_command(argc, argv);
  }
  if (argc == 2 && strcmp(argv[1], "shake256-lines") == 0) {
    return shake_lines_command();
  }
  if (argc >= 2 && strcmp(argv[1], "boot") == 0) {
    return boot_command(argc, argv);
  }
  fprintf(stderr, "usage: rot-stage shake256 OUT_BYTES | rot-stage shake256-lines | "
                  "rot-stage boot ...\n");
  return 2;
}
