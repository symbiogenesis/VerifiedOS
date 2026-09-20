// SPDX-License-Identifier: BSD-2-Clause
#include "rot_slow_clock.h"

#include "sail_riscv_model.h"

#include <stdexcept>

namespace rot {

namespace {

// The generated transition takes an arbitrary-precision integer, because the
// model's own bound is the unbounded sum it compares before narrowing: a single
// advance past 2^64 is a case sys/rot.sail states and unit_tests/test_rot.sail
// exercises, so the handle a host hands it must carry the whole range rather
// than a machine word. The two halves are set separately so the conversion is
// exact wherever `unsigned long` is at least 32 bits.
class tick_count {
public:
  explicit tick_count(uint64_t n) {
    mpz_init_set_ui(m_value, static_cast<unsigned long>(n >> 32));
    mpz_mul_2exp(m_value, m_value, 32);
    mpz_add_ui(m_value, m_value, static_cast<unsigned long>(n & 0xffffffffULL));
  }
  ~tick_count() { mpz_clear(m_value); }
  tick_count(const tick_count &) = delete;
  tick_count &operator=(const tick_count &) = delete;

  // The generated API takes non-const integer handles, even for inputs.
  mpz_t m_value;
};

} // namespace

bool model_watchdog::watchdog_present() {
  return m_model.zplat_have_watchdog;
}

void model_watchdog::watchdog_advance(uint64_t ticks) {
  // Not const: the generated API takes non-const integer handles, even for
  // inputs, and a const `mpz_t` does not convert to one.
  tick_count count(ticks);
  m_model.zwatchdog_advance(count.m_value);
}

bool model_watchdog::watchdog_bitten() {
  return m_model.zwatchdog_bitten;
}

void model_watchdog::reset_die() {
  m_model.zreset(UNIT);
}

host_time_slow_clock::host_time_slow_clock(uint64_t period_ns)
    : m_period_ns(period_ns), m_start(std::chrono::steady_clock::now()) {
  if (period_ns == 0) {
    throw std::invalid_argument("the external slow clock needs a nonzero host period");
  }
}

uint64_t host_time_slow_clock::ticks_elapsed() {
  const auto since = std::chrono::steady_clock::now() - m_start;
  const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(since).count();
  if (ns <= 0) {
    return 0;
  }
  return static_cast<uint64_t>(ns) / m_period_ns;
}

bool watchdog_join::pump() {
  if (!m_device.watchdog_present()) {
    return false;
  }

  const uint64_t total = m_source.ticks_elapsed();
  if (total < m_delivered) {
    // A source that ran backwards is a broken source, and swallowing it would
    // turn a lost deadline into a quiet extension of the window.
    throw std::logic_error("the external slow clock ran backwards");
  }
  const uint64_t due = total - m_delivered;
  m_delivered = total;
  if (due > 0) {
    m_device.watchdog_advance(due);
  }

  if (!m_device.watchdog_bitten() || m_latched) {
    return false;
  }
  m_latched = true;
  ++m_die_resets;
  m_device.reset_die();
  return true;
}

} // namespace rot
