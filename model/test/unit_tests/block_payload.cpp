// SPDX-License-Identifier: Apache-2.0
// M5.3a: finite payload evidence on the actual generated Sail PIO device.
#include <sail_config.h>
#include "config_utils.h"
#include "sail_riscv_model.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

using Bytes = std::vector<uint64_t>;

static void require(bool condition, const std::string &message) {
  if (!condition) throw std::runtime_error(message);
}

class Campaign {
  hart::Model model;
  size_t block_bytes = 0, blocks = 0, words = 0;
  size_t pairs = 0, refusals = 0, progress_events = 0, returned_bytes = 0;
  bool wrong_expected_byte;
  std::string context;

  void write(size_t offset, uint64_t value) {
    sail_int address;
    mpz_init_set_ui(address, offset);
    model.zblk_test_write(address, value);
    mpz_clear(address);
  }

  uint64_t read(size_t offset) {
    sail_int address;
    mpz_init_set_ui(address, offset);
    // The Sail helper calls mem_read_meta through device dispatch and asserts
    // both successful data and a cleared returned capability tag on every load.
    uint64_t value = model.zblk_test_read(address);
    mpz_clear(address);
    return value;
  }

  Bytes medium() const {
    return Bytes(model.zblkdev_medium.data,
                 model.zblkdev_medium.data + model.zblkdev_medium.len);
  }

  void compare(const Bytes &actual, const Bytes &expected, const char *what) {
    require(actual.size() == expected.size(), context + ": comparison length");
    for (size_t i = 0; i < actual.size(); ++i) {
      require(actual[i] == expected[i], context + ": " + what + " byte " +
              std::to_string(i) + " expected " + std::to_string(expected[i]) +
              " got " + std::to_string(actual[i]));
    }
  }

  void clear_staging() {
    require(mpz_sgn(*model.zblkdev_written.bits) == 0,
            context + ": staging bitmap must clear");
    for (size_t i = 0; i < model.zblkdev_staging.len; ++i)
      require(model.zblkdev_staging.data[i] == 0,
              context + ": staging byte must clear");
  }

  static uint64_t word(const Bytes &payload, size_t index) {
    uint64_t value = 0;
    for (size_t byte = 0; byte < 8; ++byte)
      value |= payload[8 * index + byte] << (8 * byte);
    return value;
  }

  std::vector<size_t> shuffled(size_t seed) const {
    std::vector<size_t> order(words);
    std::iota(order.begin(), order.end(), 0);
    uint32_t state = static_cast<uint32_t>(seed) + 0x9e3779b9U;
    for (size_t i = order.size(); i > 1; --i) {
      state ^= state << 13;
      state ^= state >> 17;
      state ^= state << 5;
      std::swap(order[i - 1], order[state % i]);
    }
    return order;
  }

  void stage(const Bytes &payload, size_t seed, size_t omitted) {
    const size_t replaced = seed % words;
    for (size_t i : shuffled(seed)) {
      if (i == omitted) continue;
      const uint64_t value = word(payload, i);
      write(256 + 8 * i, i == replaced ? ~value : value);
    }
    if (replaced != omitted) write(256 + 8 * replaced, word(payload, replaced));
  }

  void complete(uint64_t steps, const Bytes &before, const Bytes &after) {
    require(steps > 0, "service bound must be positive");
    require(model.zblkdev_status == 1, context + ": submitted command must be busy");
    compare(medium(), before, "submission medium");
    Bytes mask(static_cast<size_t>(model.zblkdev_max_block_bytes), 0);
    hart::zz5vecz8z5bv8z9 sail_mask{mask.size(), mask.data()};
    hart::zoptionzIbzK none{};
    none.kind = hart::Kind_zNonezIbzK;
    none.variants.zNonezIbzK = UNIT;
    for (uint64_t event = 0; event < steps; ++event) {
      require(model.zblkdev_status == 1, context + ": early completion");
      compare(medium(), before, "precompletion medium");
      model.zblkdev_progress(model.zblkdev_epoch, false, none, sail_mask);
      ++progress_events;
      if (event + 1 < steps) {
        require(model.zblkdev_status == 1, context + ": nonfinal progress must be busy");
        compare(medium(), before, "nonfinal medium");
      }
    }
    // Observe the full medium before polling terminal STATUS.
    compare(medium(), after, "completed medium");
    require(read(24) == 2 && read(32) == 0, context + ": completion must be DONE/OK");
  }

  void incomplete(const Bytes &before) {
    write(48, 2);
    require(read(24) == 3 && read(32) == 3,
            context + ": incomplete WRITE must be ERROR/INCOMPLETE");
    require(mpz_sgn(model.zblkdev_remaining) == 0,
            context + ": refused command must not be pending");
    clear_staging();
    compare(medium(), before, "refused-write medium");
    ++refusals;
    write(56, 1);
  }

public:
  explicit Campaign(bool wrong) : wrong_expected_byte(wrong) { model.model_init(); }
  ~Campaign() { model.model_fini(); }

  void run() {
    require(model.zplat_have_blkdev && model.zblkdev_claims(model.zplat_blkdev_base, 8),
            "payload evidence requires enabled device dispatch");
    model.zblkdev_initializze(UNIT);
    block_bytes = static_cast<size_t>(read(8));
    blocks = static_cast<size_t>(read(16));
    require(block_bytes > 0 && block_bytes % 8 == 0 && blocks >= 2,
            "payload fixture must contain at least two complete blocks");
    require(block_bytes <= static_cast<size_t>(model.zblkdev_max_block_bytes) &&
            blocks <= static_cast<size_t>(model.zblkdev_max_bytes) / block_bytes,
            "payload enumeration exceeds admitted model geometry");
    words = block_bytes / 8;
    require(read(24) == 0 && read(32) == 0, "fixture must begin IDLE/OK");

    const size_t locations = blocks * block_bytes;
    size_t address_bits = 0;
    while ((size_t{1} << address_bits) < locations) ++address_bits;
    // Across the family, location-bit planes distinguish every byte location,
    // and walking-one planes distinguish each bit within that byte. Endpoints
    // and the location planes also exercise uniform and nonuniform payloads.
    std::vector<Bytes> family(2 + 8 + address_bits, Bytes(locations));
    std::fill(family[1].begin(), family[1].end(), 255);
    for (size_t bit = 0; bit < 8; ++bit)
      std::fill(family[2 + bit].begin(), family[2 + bit].end(), uint64_t{1} << bit);
    for (size_t bit = 0; bit < address_bits; ++bit)
      for (size_t byte = 0; byte < locations; ++byte)
        family[10 + bit][byte] = (byte & (size_t{1} << bit)) ? 255 : 0;

    for (size_t pattern = 0; pattern < family.size(); ++pattern) {
      for (size_t block = 0; block < blocks; ++block) {
        context = "pattern " + std::to_string(pattern) + " block " + std::to_string(block);
        const auto first = family[pattern].begin() + block * block_bytes;
        Bytes payload(first, first + block_bytes);
        const Bytes before = medium();
        Bytes after = before;
        std::copy(payload.begin(), payload.end(), after.begin() + block * block_bytes);
        write(40, block);
        stage(payload, pattern * blocks + block, words);
        compare(medium(), before, "staged medium");
        write(48, 2);
        clear_staging();
        complete(sail_int_get_ui(model.zplat_blkdev_write_steps), before, after);
        write(56, 1);
        write(40, block);
        write(48, 1);
        complete(sail_int_get_ui(model.zplat_blkdev_read_steps), after, after);
        for (size_t repeat = 0; repeat < 2; ++repeat) {
          Bytes returned(block_bytes);
          for (size_t i = 0; i < words; ++i) {
            const uint64_t value = read(256 + 8 * i);
            for (size_t byte = 0; byte < 8; ++byte)
              returned[8 * i + byte] = (value >> (8 * byte)) & 255;
          }
          Bytes expected = payload;
          if (wrong_expected_byte && pattern == 0 && block == 0 && repeat == 0)
            expected[0] ^= 1;
          compare(returned, expected, "returned payload");
          returned_bytes += returned.size();
        }
        compare(medium(), after, "read-only medium");
        write(56, 1);
        ++pairs;
      }
    }

    // A selection boundary invalidates even complete previous preparation.
    // Exercise both the same block value and a different valid block value.
    for (size_t block = 0; block < blocks; ++block) {
      Bytes payload(block_bytes);
      for (size_t i = 0; i < block_bytes; ++i) payload[i] = (i * 37 + block + 1) & 255;
      for (size_t change = 0; change < 2; ++change) {
        context = "BLOCK rewrite " + std::to_string(change) + " block " + std::to_string(block);
        const Bytes before = medium();
        write(40, block);
        stage(payload, block, words);
        write(40, (block + change) % blocks);
        clear_staging();
        incomplete(before);
      }
      for (size_t omitted = 0; omitted < words; ++omitted) {
        context = "omitted word " + std::to_string(omitted) + " block " + std::to_string(block);
        const Bytes before = medium();
        write(40, block);
        stage(payload, block + omitted, omitted);
        incomplete(before);
      }
    }
    std::printf("block payload: B=%zu N=%zu patterns=%zu write/read-pairs=%zu "
                "refusals=%zu progress-events=%zu returned-bytes=%zu PASS\n",
                block_bytes, blocks, family.size(), pairs, refusals,
                progress_events, returned_bytes);
  }
};

int main(int argc, char **argv) {
  const bool wrong = argc == 2 && std::strcmp(argv[1], "--wrong-expected-byte") == 0;
  if (argc != 1 && !wrong) {
    std::fputs("usage: block_payload [--wrong-expected-byte]\n", stderr);
    return 2;
  }
  sail_config_set_string(get_default_config());
  try {
    Campaign campaign(wrong);
    campaign.run();
  } catch (const std::exception &error) {
    std::fprintf(stderr, "block payload: FAIL: %s\n", error.what());
    return 1;
  }
  return 0;
}
