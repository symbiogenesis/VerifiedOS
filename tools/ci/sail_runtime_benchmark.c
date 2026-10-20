/* SPDX-License-Identifier: Apache-2.0 */
/* CI-only focused runtime measurements, not whole-emulator performance. */
#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "rts.h"

void model_pre_exit(void) {}
void (*sail_rts_set_coverage_file)(const char *) = NULL;

#define BLOCK_SIZE UINT64_C(16777216)
#define MAX_SIZE ((size_t)1048576)
#define REGION_COUNT 8
#define HEAD_ADDRESS ((REGION_COUNT - 2) * 2 * BLOCK_SIZE)

static uint8_t input[MAX_SIZE + 4096];
static uint8_t output[MAX_SIZE];

static void fail(const char *message)
{
  fprintf(stderr, "%s\n", message);
  exit(EXIT_FAILURE);
}

static double now(void)
{
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) fail("clock_gettime failed");
  return (double)t.tv_sec + (double)t.tv_nsec / 1e9;
}

static void read_bytes(uint64_t address, uint8_t *buffer, size_t length)
{
#ifdef SAIL_BUFFER_API
  read_mem_bytes(address, buffer, length);
#else
  for (size_t i = 0; i < length; ++i) buffer[i] = (uint8_t)read_mem(address + i);
#endif
}

static void write_bytes(uint64_t address, const uint8_t *buffer, size_t length)
{
#ifdef SAIL_BUFFER_API
  write_mem_bytes(address, buffer, length);
#else
  for (size_t i = 0; i < length; ++i) write_mem(address + i, buffer[i]);
#endif
}

static uint8_t pattern(uint64_t address)
{
  return (uint8_t)((address * 29 + (address >> 8) * 7 + 19) & 255);
}

static uint64_t checksum(const uint8_t *buffer, size_t length)
{
  uint64_t value = 0;
  for (size_t i = 0; i < length; ++i) value = value * 31 + buffer[i];
  return value;
}

static void emit(const char *name, size_t size, size_t iterations, double seconds,
                 uint64_t value)
{
  if (seconds <= 0) fail("nonpositive measurement duration");
  printf("{\"case\":\"%s\",\"bytes\":%zu,\"iterations\":%zu,"
         "\"seconds\":%.9f,\"checksum\":\"%016" PRIx64 "\"}\n",
         name, size, iterations, seconds, value);
}

/* Allocate eight 16 MiB blocks, including an adjacent pair for boundary cases
 * and six sparsely placed regions. The measured region is at the
 * tail of the lookup list, making the linked-list cost explicit and repeatable.
 * Initialization, allocation and validation stay outside every timer. */
static void prepare(void)
{
  for (size_t i = 0; i < sizeof(input); ++i) input[i] = pattern(i);
  write_bytes(0, input, sizeof(input));
  for (size_t i = 0; i < sizeof(input); ++i) input[i] = pattern(BLOCK_SIZE - MAX_SIZE + i);
  write_bytes(BLOCK_SIZE - MAX_SIZE, input, sizeof(input));
  for (size_t i = 0; i < sizeof(input); ++i) input[i] = pattern(BLOCK_SIZE + i);
  write_bytes(BLOCK_SIZE, input, sizeof(input));
  for (uint64_t region = 1; region < REGION_COUNT - 1; ++region)
    write_mem(region * 2 * BLOCK_SIZE, region);
  for (size_t i = 0; i < sizeof(input); ++i) input[i] = pattern(i);
  write_bytes(HEAD_ADDRESS, input, sizeof(input));
}

static void buffers(size_t length, bool crossing, bool writing, bool head)
{
  const uint64_t base = head ? HEAD_ADDRESS : crossing ? BLOCK_SIZE - length / 2 : 0;
  size_t iterations = (32 * MAX_SIZE) / length;
  if (iterations > 250000) iterations = 250000;
  if (iterations < 8) iterations = 8;
  uint64_t last = base;
  double start = now();
  for (size_t i = 0; i < iterations; ++i) {
    last = base + (crossing ? 0 : (i * 64) & 4095);
    if (writing) write_bytes(last, input, length);
    else read_bytes(last, output, length);
  }
  double seconds = now() - start;
  if (writing) read_bytes(last, output, length);
  for (size_t i = 0; i < length; ++i)
    if (output[i] != (writing ? input[i] : pattern(last + i))) fail("buffer result differs");
  char name[80];
  snprintf(name, sizeof(name), "buffer_%s_%s_%zu", writing ? "write" : "read",
           head ? "head" : crossing ? "boundary" : "sparse8", length);
  emit(name, length, iterations, seconds, checksum(output, length));
}

static void scalar(size_t length, bool head)
{
  const size_t iterations = 250000;
  const uint64_t base = head ? HEAD_ADDRESS : 0;
  uint64_t observed = 0, expected = 0;
  for (size_t i = 0; i < iterations; ++i) {
    uint64_t address = base + ((i * 64) & 4095);
    uint64_t value = 0;
    for (size_t j = length; j > 0; --j) value = (value << 8) | pattern(address + j - 1);
    expected += value;
  }
  double start = now();
  for (size_t i = 0; i < iterations; ++i)
    observed += fast_read_ram((int64_t)length, base + ((i * 64) & 4095)).bits;
  double seconds = now() - start;
  if (observed != expected) fail("fast_read_ram result differs");
  char name[40];
  snprintf(name, sizeof(name), "fast_read_ram_%s_%zu", head ? "head" : "sparse8", length);
  emit(name, length, iterations, seconds, observed);
}

static void image(const char *path)
{
  const size_t size = 8 * MAX_SIZE;
  const size_t iterations = 4;
  double start = now();
  for (size_t i = 0; i < iterations; ++i) load_raw(4 * BLOCK_SIZE, path);
  double seconds = now() - start;
  uint64_t value = 0;
  for (size_t i = 0; i < size; ++i) {
    uint8_t byte = (uint8_t)read_mem(4 * BLOCK_SIZE + i);
    if (byte != pattern(i)) fail("load_raw image differs");
    value = value * 31 + byte;
  }
  emit("load_raw_8MiB", size, iterations, seconds, value);
}

int main(int argc, char **argv)
{
  if (argc != 2) fail("expected precreated image path");
  setup_rts();
  prepare();
  for (size_t size = 1; size <= 8; size *= 2) {
    scalar(size, false);
    scalar(size, true);
  }
  const size_t sizes[] = {1, 8, 16, 64, 4096, MAX_SIZE};
  /* Reads precede writes so their oracle is the original initialized pattern. */
  for (size_t i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
    buffers(sizes[i], false, false, false);
    if (sizes[i] >= 64) buffers(sizes[i], true, false, false);
  }
  buffers(8, false, false, true);
  buffers(4096, false, false, true);
  for (size_t i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
    buffers(sizes[i], false, true, false);
    if (sizes[i] >= 64) buffers(sizes[i], true, true, false);
  }
  buffers(8, false, true, true);
  buffers(4096, false, true, true);
  image(argv[1]);
  cleanup_rts();
  return EXIT_SUCCESS;
}
