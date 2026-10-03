// SPDX-License-Identifier: Apache-2.0
// Q35f: the SoftFloat 3e side of the fpcompare differential.
//
// Reads the vector file `run.py oracle vectors --spec fpcompare` writes and
// prints each line again with its answer recomputed by SoftFloat 3e, called as
// the emulator's wrappers in model/c_emulator/riscv_softfloat.cpp call it: the
// exception flags cleared, the comparison called, the flags read back. Linked
// against the libsoftfloat.a the model's own CMake target `softfloat` builds,
// so the library, its RISC-V specialization and its compile definitions are the
// emulator's. Commentary lines pass through, so the two files compare line for
// line. A line it cannot read stops it with exit 2.
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "softfloat.h"

int main(void) {
  char line[256];
  unsigned long n = 0;
  while (fgets(line, sizeof line, stdin)) {
    n++;
    if (line[0] == '#') {
      fputs(line, stdout);
      continue;
    }
    char kind[16];
    unsigned long long a, b;
    if (sscanf(line, "%15s %llx %llx ->", kind, &a, &b) != 3) {
      fprintf(stderr, "line %lu is not a vector: %s", n, line);
      return 2;
    }
    const char *op = kind[0] == 'r' ? kind + 2 : kind + 1;
    char width = kind[0] == 'r' ? kind[1] : kind[0];
    float32_t sa = {(uint32_t)a}, sb = {(uint32_t)b};
    float64_t da = {(uint64_t)a}, db = {(uint64_t)b};
    bool r;
    softfloat_exceptionFlags = 0;
    if (width == 's' && !strcmp(op, "lt")) r = f32_lt(sa, sb);
    else if (width == 's' && !strcmp(op, "ltq")) r = f32_lt_quiet(sa, sb);
    else if (width == 's' && !strcmp(op, "le")) r = f32_le(sa, sb);
    else if (width == 's' && !strcmp(op, "eq")) r = f32_eq(sa, sb);
    else if (width == 'd' && !strcmp(op, "lt")) r = f64_lt(da, db);
    else if (width == 'd' && !strcmp(op, "ltq")) r = f64_lt_quiet(da, db);
    else if (width == 'd' && !strcmp(op, "le")) r = f64_le(da, db);
    else if (width == 'd' && !strcmp(op, "eq")) r = f64_eq(da, db);
    else {
      fprintf(stderr, "line %lu has an unknown kind %s\n", n, kind);
      return 2;
    }
    if (width == 's')
      printf("%s %08llx %08llx -> %02x %d\n", kind, a, b, (unsigned)softfloat_exceptionFlags, r ? 1 : 0);
    else
      printf("%s %016llx %016llx -> %02x %d\n", kind, a, b, (unsigned)softfloat_exceptionFlags, r ? 1 : 0);
  }
  return 0;
}
