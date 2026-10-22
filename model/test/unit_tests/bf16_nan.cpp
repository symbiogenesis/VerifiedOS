// SPDX-License-Identifier: BSD-2-Clause
// Check the vendored classifier against the BF16 representation, without
// depending on a floating-point conversion or the generated Sail model.
#include "internals.h"
#include <cstdint>
#include <cstdio>

static bool check(std::uint16_t bits, bool expected) {
  const bool observed = isNaNBF16UI(bits);
  if (observed != expected) {
    std::fprintf(
      stderr,
      "BF16 NaN: FAIL bits=0x%04x expected=%u observed=%u\n",
      static_cast<unsigned>(bits),
      static_cast<unsigned>(expected),
      static_cast<unsigned>(observed)
    );
    return false;
  }
  return true;
}

int main() {
  // These signaling NaNs lack the quiet bit that the preceding macro required.
  if (!check(0x7f81, true) || !check(0xff81, true)) {
    return 1;
  }
  unsigned nan_count = 0;
  for (std::uint32_t raw = 0; raw < 65536; ++raw) {
    // BF16 has one sign bit, eight exponent bits and seven fraction bits.
    const unsigned exponent = (raw / 128) % 256;
    const unsigned fraction = raw % 128;
    const bool expected = exponent == 255 && fraction != 0;
    nan_count += expected;
    if (!check(static_cast<std::uint16_t>(raw), expected)) {
      return 1;
    }
  }
  std::printf("BF16 NaN: PASS representations=65536 NaNs=%u\n", nan_count);
  return 0;
}
