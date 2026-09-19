// SPDX-License-Identifier: Apache-2.0
// Finite reset-boundary evidence for the actual generated Sail block device.
#include <sail_config.h>
#include "config_utils.h"
#include "sail_riscv_model.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Bytes = std::vector<uint64_t>;
using Buffer = Bytes;
std::string context;

void require(bool condition, const char *message) {
  if (!condition) throw std::runtime_error(context + ": " + message);
}

struct Integer {
  // The generated Sail API takes non-const integer handles, even for inputs.
  mutable mpz_t value;
  explicit Integer(unsigned long n) { mpz_init_set_ui(value, n); }
  explicit Integer(const sail_int n) { mpz_init_set(value, n); }
  ~Integer() { mpz_clear(value); }
  Integer(const Integer &) = delete;
  Integer &operator=(const Integer &) = delete;
};

std::string decimal(const sail_int n) {
  std::string text(mpz_sizeinbase(n, 10) + 2, '\0');
  mpz_get_str(text.data(), 10, n);
  text.resize(std::strlen(text.c_str()));
  return text;
}

size_t count(const sail_int n) {
  require(mpz_fits_ulong_p(n), "fixture count must fit the host enumeration");
  return mpz_get_ui(n);
}

Bytes bytes(const hart::zz5vecz8z5bv8z9 &v) {
  return Bytes(v.data, v.data + v.len);
}

hart::zz5vecz8z5bv8z9 view(Buffer &b) {
  hart::zz5vecz8z5bv8z9 result{};
  result.len = b.size();
  result.data = b.data();
  return result;
}

hart::zoptionzIbzK none() {
  hart::zoptionzIbzK result{};
  result.kind = hart::Kind_zNonezIbzK;
  result.variants.zNonezIbzK = UNIT;
  return result;
}

// Capture all device state, including the association token. No model object is
// shallow-copied: Sail vectors and integers have separately managed storage.
struct Snapshot {
  Bytes medium, staging, payload;
  std::string written, remaining, epoch;
  int64_t status, result, command;
  uint64_t block, pending;
  explicit Snapshot(const hart::Model &m)
      : medium(bytes(m.zblkdev_medium)), staging(bytes(m.zblkdev_staging)),
        payload(bytes(m.zblkdev_payload)), written(decimal(*m.zblkdev_written.bits)),
        remaining(decimal(m.zblkdev_remaining)), epoch(decimal(m.zblkdev_epoch)),
        status(m.zblkdev_status), result(m.zblkdev_result), command(m.zblkdev_command),
        block(m.zblkdev_block), pending(m.zblkdev_pending_block) {}

  void compare(const hart::Model &m) const {
    const Snapshot after(m);
    require(medium == after.medium, "stale response changed medium");
    require(staging == after.staging && payload == after.payload && written == after.written,
            "stale response changed staging or pending bytes");
    require(remaining == after.remaining && epoch == after.epoch && status == after.status &&
            result == after.result && command == after.command && block == after.block &&
            pending == after.pending, "stale response changed volatile controls or epoch");
  }
};

enum class Boundary { Before, Pending, Simultaneous, Completed, Observed };

class ResetModel final : public hart::Model {
public:
  bool device_dispatch_enabled() { return zplat_have_blkdev && !get_config_rvfi(UNIT); }
};

class Campaign {
  ResetModel &m;
  size_t block_bytes, block_count;
  std::array<size_t, 4> steps;
  Buffer zero;
  bool negative_byte, negative_volatile;
  size_t cases = 0, stale_events = 0;

  void write(size_t offset, uint64_t value) {
    Integer at(static_cast<unsigned long>(offset));
    m.zblk_test_write(at.value, value);
  }

  uint64_t read(size_t offset) {
    Integer at(static_cast<unsigned long>(offset));
    return m.zblk_test_read(at.value);
  }

  Buffer mask(unsigned pattern) const {
    Buffer out(zero.size());
    for (size_t i = 0; i < out.size(); ++i)
      out[i] = pattern == 0 ? 0 : pattern == 1 ? 255 : (i % 2 ? 0x5a : 0xa5);
    return out;
  }

  Buffer prepare(size_t block) {
    Buffer payload(zero.size());
    const size_t start = block * block_bytes;
    for (size_t i = 0; i < block_bytes; ++i) payload[i] = m.zblkdev_medium.data[start + i] ^ 255;
    write(40, block);
    for (size_t i = 0; i < block_bytes; i += 8) {
      uint64_t word = 0;
      for (size_t j = 0; j < 8; ++j) word |= payload[i + j] << (8 * j);
      write(256 + i, word);
    }
    return payload;
  }

  void progress(const Integer &epoch, bool error, Buffer &tear) {
    m.zblkdev_progress(epoch.value, error, none(), view(tear));
  }

  void expect_medium(const Bytes &expected) const {
    require(bytes(m.zblkdev_medium) == expected, "whole-medium byte comparison failed");
  }

  void mix(Bytes &expected, size_t block, const Buffer &payload, const Buffer &tear) const {
    for (size_t i = 0; i < block_bytes; ++i) {
      auto &old = expected[block * block_bytes + i];
      old = (old & (255 ^ tear[i])) | (payload[i] & tear[i]);
    }
  }

  void reset_state(const Integer &old_epoch, const Bytes &expected) const {
    expect_medium(expected);
    require(m.zblkdev_status == 0 && m.zblkdev_result == 0 && m.zblkdev_block == 0 &&
            m.zblkdev_pending_block == 0 && m.zblkdev_command == 0 &&
            mpz_cmp_ui(m.zblkdev_remaining, 0) == 0 &&
            mpz_cmp_ui(*m.zblkdev_written.bits, 0) == 0,
            "reset left a volatile control or written bit");
    for (const auto *buffer : {&m.zblkdev_staging, &m.zblkdev_payload})
      for (size_t i = 0; i < buffer->len; ++i)
        require(buffer->data[i] == 0, "reset left a volatile buffer byte");
    Integer next(old_epoch.value);
    mpz_add_ui(next.value, next.value, 1);
    require(mpz_cmp(m.zblkdev_epoch, next.value) == 0, "reset did not advance epoch exactly once");
  }

  void stale_pair(const Integer &canceled) {
    const Snapshot before(m);
    Buffer full = mask(1);
    for (bool error : {false, true}) {
      progress(canceled, error, full);
      before.compare(m);
      ++stale_events;
    }
  }

  void check_canceled(const Integer &canceled) {
    stale_pair(canceled); // reset IDLE
    for (unsigned command = 1; command <= 3; ++command) {
      const size_t target = block_count - 1;
      const Buffer payload = prepare(target);
      Bytes expected = bytes(m.zblkdev_medium);
      write(48, command);
      const Integer fresh(m.zblkdev_epoch);
      require(mpz_cmp(fresh.value, canceled.value) > 0, "new command reused canceled epoch");
      stale_pair(canceled); // newly accepted command
      for (size_t i = 1; i < steps[command]; ++i) progress(fresh, false, zero);
      stale_pair(canceled); // last BUSY boundary: an unfenced response would complete
      progress(fresh, false, zero);
      if (command == 2) mix(expected, target, payload, mask(1));
      expect_medium(expected);
      require(m.zblkdev_status == 2 && m.zblkdev_result == 0, "fresh command did not succeed");
      stale_pair(canceled); // completed new command, before ACK
      write(56, 1);
    }
  }

  void finish_reset(const Integer &epoch, Bytes expected, Buffer &tear, bool simultaneous,
                    bool error) {
    m.zblkdev_boundary(true, simultaneous, epoch.value, error, none(), view(tear));
    if (negative_byte) expected[0] ^= 1;
    if (negative_volatile) m.zblkdev_payload.data[m.zblkdev_payload.len - 1] = 1;
    reset_state(epoch, expected);
    ++cases;
    check_canceled(epoch);
  }

  void run_case(unsigned command, size_t block, unsigned pattern, bool corrupt, bool error,
                Boundary boundary, size_t completed_steps) {
    context = "command=" + std::to_string(command) + " block=" + std::to_string(block) +
        " mask=" + std::to_string(pattern) + " corrupt=" + std::to_string(corrupt) +
        " error=" + std::to_string(error) + " boundary=" +
        std::to_string(static_cast<unsigned>(boundary)) + " steps=" + std::to_string(completed_steps);
    m.zblkdev_initializze(UNIT);
    const Buffer payload = prepare(block);
    Buffer tear = mask(pattern);
    if (boundary != Boundary::Before) write(48, command);
    const Integer epoch(m.zblkdev_epoch);
    Bytes expected = bytes(m.zblkdev_medium);
    for (size_t i = 0; i < completed_steps; ++i) {
      progress(epoch, error, tear);
      expect_medium(expected); // only nonfinal steps have occurred
      require(m.zblkdev_status == 1 && count(m.zblkdev_remaining) == steps[command] - i - 1,
              "nonfinal progress changed pending state incorrectly");
    }
    if (corrupt) {
      Buffer changed(zero.size());
      for (size_t i = 0; i < block_bytes; ++i) {
        changed[i] = expected[block * block_bytes + i] ^ 0x3c;
        expected[block * block_bytes + i] = changed[i];
      }
      m.zblkdev_corrupt(block, view(changed));
      expect_medium(expected);
    }
    if (boundary == Boundary::Completed || boundary == Boundary::Observed) {
      progress(epoch, error, tear);
      if (command == 2) mix(expected, block, payload, error ? tear : mask(1));
      expect_medium(expected);
      require(m.zblkdev_status == (error ? 3 : 2) && m.zblkdev_result == (error ? 4 : 0),
              "final outcome did not match the injected result");
      if (boundary == Boundary::Observed)
        require(read(24) == static_cast<uint64_t>(error ? 3 : 2) &&
                read(32) == static_cast<uint64_t>(error ? 4 : 0), "terminal status read differed");
    } else if (boundary != Boundary::Before && command == 2) {
      mix(expected, block, payload, tear);
    }
    finish_reset(epoch, expected, tear, boundary == Boundary::Simultaneous, error);
  }

public:
  Campaign(ResetModel &model, bool bad_byte, bool bad_volatile)
      : m(model), block_bytes(count(m.zplat_blkdev_block_bytes)),
        block_count(count(m.zplat_blkdev_block_count)),
        steps{0, count(m.zplat_blkdev_read_steps), count(m.zplat_blkdev_write_steps),
              count(m.zplat_blkdev_flush_steps)},
        zero(static_cast<size_t>(m.zblkdev_max_block_bytes)),
        negative_byte(bad_byte), negative_volatile(bad_volatile) {
    require(m.device_dispatch_enabled(), "device dispatch must be enabled");
    require(block_bytes > 0 && block_bytes <= zero.size() && block_bytes % 8 == 0 &&
            block_count >= 2 && block_count <= m.zblkdev_medium.len / block_bytes, "fixture geometry is inadmissible");
    for (unsigned command = 1; command <= 3; ++command)
      require(steps[command] > 0, "service bound must be positive");
  }

  void run() {
    for (unsigned command = 1; command <= 3; ++command)
      for (size_t block = 0; block < block_count; ++block)
        for (unsigned pattern = 0; pattern < 3; ++pattern)
          for (bool corrupt : {false, true})
            for (bool error : {false, true}) {
              run_case(command, block, pattern, corrupt, error, Boundary::Before, 0);
              for (size_t progress_count = 0; progress_count < steps[command]; ++progress_count)
                run_case(command, block, pattern, corrupt, error, Boundary::Pending, progress_count);
              for (Boundary boundary : {Boundary::Simultaneous, Boundary::Completed, Boundary::Observed})
                run_case(command, block, pattern, corrupt, error, boundary, steps[command] - 1);
            }
    const size_t boundary_cases = cases;
    for (unsigned pattern = 0; pattern < 3; ++pattern)
      for (unsigned failure = 0; failure <= 3; ++failure) {
        context = "idle/validation=" + std::to_string(failure) + " mask=" + std::to_string(pattern);
        m.zblkdev_initializze(UNIT);
        const Bytes expected = bytes(m.zblkdev_medium);
        if (failure == 1) write(48, 0); // BAD_COMMAND
        if (failure == 2) { write(40, block_count); write(48, 1); } // RANGE
        if (failure == 3) write(48, 2); // INCOMPLETE
        require(m.zblkdev_status == (failure ? 3 : 0) && m.zblkdev_result == failure,
                "validation fixture did not enter the intended state");
        const Integer epoch(m.zblkdev_epoch);
        Buffer tear = mask(pattern);
        finish_reset(epoch, expected, tear, false, false);
      }
    const size_t derived = block_count * 3 * 2 * 2 * (steps[1] + steps[2] + steps[3] + 12);
    require(boundary_cases == derived && cases == derived + 12 && stale_events == cases * 20,
            "generated boundary/callback counts do not match fixture bounds");
    std::printf("block reset: block_bytes=%zu blocks=%zu service_steps=%zu/%zu/%zu "
                "boundary_cases=%zu idle_validation_cases=12 resets=%zu stale_events=%zu PASS\n",
                block_bytes, block_count, steps[1], steps[2], steps[3], boundary_cases, cases, stale_events);
  }
};
} // namespace

int main(int argc, char **argv) {
  const bool bad_byte = argc == 2 && std::strcmp(argv[1], "--negative-byte") == 0;
  const bool bad_volatile = argc == 2 && std::strcmp(argv[1], "--negative-volatile") == 0;
  if (argc != 1 && !bad_byte && !bad_volatile) return 2;
  sail_config_set_string(get_default_config());
  ResetModel model;
  model.model_init();
  int result = EXIT_SUCCESS;
  try { Campaign(model, bad_byte, bad_volatile).run(); }
  catch (const std::exception &e) {
    std::fprintf(stderr, "block reset: FAIL %s\n", e.what());
    result = EXIT_FAILURE;
  }
  model.model_fini();
  return result;
}
