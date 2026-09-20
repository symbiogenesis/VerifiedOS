// SPDX-License-Identifier: BSD-2-Clause
// The RoT watchdog's external slow clock, and the die reset its bite asserts.
//
// This is the executable half of sys/rot.sail's windowed watchdog (R-15-240).
// The model carries the transition, `watchdog_advance`, and carries no caller
// for it: advancing it from the machine's own instruction tick would make the
// timeout a function of retirement, which is the coupling an independent clock
// exists to remove. What is here is the caller, placed in the emulator's
// platform layer, and the consumer of the latch it produces.
//
// **The event source is the host's and never the machine's** (R-15-196). A
// source below answers one question, how many ticks its own clock has produced,
// and neither reads nor is given an instruction count, a retired step, the
// emulator's `instructions_per_tick`, or any other quantity the core moves. No
// ratio between the spine and this counter is declared anywhere in this file,
// in the model, or in the attested devicetree: the RoT's slow clock is one of
// R-15-196's exactly three genuinely asynchronous boundaries and none of the
// three is modeled as fixed-latency, so a `slow_clock_divisor` beside the two
// window bounds would be precisely the fixed-latency model that entry refuses.
// The host period a `host_time_slow_clock` is built with is an emulation fact
// of the same kind as the entropy seed: it is supplied on the command line,
// reaches no attested structure, and is absent unless a run asks for it.
//
// **The bite's consumer is the die reset and nothing else** (R-16-005): the RoT
// watchdog is the last resort and its bite equals a reset, so the join below
// calls the model's own `reset()` and not a fault, a trap, or a report. That
// equality is R-16-005's alone. R-15-198 is cited nowhere here as authority,
// because it says something this file does not model: reset sequencing is a
// fixed composition-time sequence table in the attested devicetree, executed by
// the verified RoT firmware as the only sequencer, and the join calls a
// generated `reset()` with no table and no sequencer behind it. R-15-198 is
// what the still-owed firmware lowering has to satisfy, not what this join
// satisfies. Two consequences are worth stating because they are properties
// rather than choices. The die reset does not clear `watchdog_bitten`, the
// watchdog living in a failure domain disjoint from the cores (R-15-240), so
// the RoT's record of why the die was reset survives the reset it caused; and
// nothing in the model clears that latch, so the join asserts the die reset
// exactly once and the model stays bitten.
#pragma once

#include <chrono>
#include <cstdint>

namespace hart {
class Model;
}

namespace rot {

// The watchdog and the die reset as the platform layer reaches them. It is an
// interface because the emulator reaches the model through `ModelImpl`, whose
// derivation from the generated class is private, while a harness holds the
// generated class directly; both drive the same join.
class watchdog_device {
public:
  virtual ~watchdog_device() = default;

  // Whether the composition declares the device at all. A composition without
  // one leaves the join inert rather than advancing a device that is not there.
  virtual bool watchdog_present() = 0;

  // The external slow-clock transition (sys/rot.sail).
  virtual void watchdog_advance(uint64_t ticks) = 0;

  // The latch.
  virtual bool watchdog_bitten() = 0;

  // The die reset the bite asserts: the model's own `reset()`.
  virtual void reset_die() = 0;
};

// The generated model behind that interface.
class model_watchdog final : public watchdog_device {
public:
  explicit model_watchdog(hart::Model &model) : m_model(model) {}

  bool watchdog_present() override;
  void watchdog_advance(uint64_t ticks) override;
  bool watchdog_bitten() override;
  void reset_die() override;

private:
  hart::Model &m_model;
};

// An external clock. `ticks_elapsed` is the total this clock has produced since
// the die left reset and is nondecreasing; the join delivers differences.
class slow_clock_source {
public:
  virtual ~slow_clock_source() = default;
  virtual uint64_t ticks_elapsed() = 0;
};

// The harness's source: explicit events, each carrying its own tick count. This
// is the deterministic arm, and it is what lets a test advance the slow clock
// with the core stopped, which no amount of host wall time can be made to do
// reproducibly.
class injected_slow_clock final : public slow_clock_source {
public:
  // One external event.
  void fire(uint64_t ticks) { m_total += ticks; }
  uint64_t ticks_elapsed() override { return m_total; }

private:
  uint64_t m_total = 0;
};

// The emulator's source: host wall time over a host period. Host time passes
// whether the emulator retires an instruction, spins in a trap loop, or waits,
// so the quantity this returns is a function of the host clock alone.
class host_time_slow_clock final : public slow_clock_source {
public:
  explicit host_time_slow_clock(uint64_t period_ns);
  uint64_t ticks_elapsed() override;

private:
  uint64_t m_period_ns;
  std::chrono::steady_clock::time_point m_start;
};

// The join: deliver what the external clock produced, then sample the latch and
// assert the die reset on the edge.
class watchdog_join {
public:
  watchdog_join(watchdog_device &device, slow_clock_source &source) : m_device(device), m_source(source) {}

  // Deliver the ticks the external clock has produced since the last delivery,
  // then sample the latch. Returns true on the one pump that asserted the die
  // reset. The latch is sampled even when no tick was due, because a pet
  // outside the window or against the wrong challenge bites too, and the die
  // reset is the latch's consumer rather than the clock's.
  bool pump();

  // Total external ticks handed to the model.
  uint64_t delivered() const { return m_delivered; }

  // How many times the die reset was asserted. The latch is absorbing and
  // nothing clears it, so this saturates at one.
  uint64_t die_resets() const { return m_die_resets; }

private:
  watchdog_device &m_device;
  slow_clock_source &m_source;
  uint64_t m_delivered = 0;
  uint64_t m_die_resets = 0;
  bool m_latched = false;
};

} // namespace rot
