// SPDX-License-Identifier: BSD-2-Clause
// The RoT watchdog's asynchronous platform join, executed against the actual
// generated Sail model through the emulator's own platform-layer source
// (c_emulator/rot_slow_clock.h).
//
// **What a direct transition test cannot supply.** unit_tests/test_rot.sail
// already states the deadline, the inclusive bound, the saturating reading and
// the absorbing latch, and it states them by calling `watchdog_advance` from
// inside the model. That establishes what the transition does and leaves open
// the thing R-15-240 is about: whether anything drives the transition once the
// machine has stopped driving itself. So the clock here is outside the model,
// the ticks are produced by a host-side source that is handed no quantity the
// core moves, and one of the two required cases advances that clock with the
// model's step function never called at all.
//
// **The two cases are the two ways the machine dies** (R-15-240). A stopped
// petter is a core that runs and never answers the challenge, which is the case
// a one-sided timeout was built for; a stopped main clock is a core that
// retires nothing at all, which is the case that kills any timeout derived from
// retirement. Both must reach the bite, and the bite must reach the die reset,
// which is R-16-005's equality between the bite and a reset. R-15-198's reset
// sequence table is a separate obligation this harness does not exercise: the
// die reset here is the generated model's `reset()` and no sequencer runs it.
//
// **The control is what makes the two positives mean anything.** A third case
// runs exactly the same core activity with the external clock never firing and
// requires that nothing bites, so the bites above are attributable to the
// external source rather than to the harness's own stepping; and the two
// `--negative-` arms invert one expectation apiece, so a harness that could not
// see a missing bite or a missing reset fails visibly.
#include <sail_config.h>

#include "config_utils.h"
#include "rot_slow_clock.h"
#include "sail_riscv_model.h"

#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>

namespace {

std::string context;

void require(bool condition, const char *message) {
  if (!condition) throw std::runtime_error(context + ": " + message);
}

// The die's reset vector, and where the harness places the die before the bite
// so that the reset is observable as a move rather than as a value that
// happened to be right already. Both are inside the configured main memory, so
// a step fetches a real word rather than leaving the machine's address space.
constexpr uint64_t RESET_VECTOR = 0x80000000;
constexpr uint64_t ELSEWHERE = 0x80001234;

// The shipped adapter, wrapped so the harness can see each call. Wrapping
// rather than reimplementing is deliberate: what is under test is the platform
// layer's own device and die-reset path, not a second copy of it.
class observed_device final : public rot::watchdog_device {
public:
  explicit observed_device(hart::Model &model) : m_model(model), m_inner(model) {}

  bool watchdog_present() override { return m_inner.watchdog_present(); }

  void watchdog_advance(uint64_t ticks) override {
    ++advances;
    delivered += ticks;
    m_inner.watchdog_advance(ticks);
  }

  bool watchdog_bitten() override { return m_inner.watchdog_bitten(); }

  void reset_die() override {
    ++resets;
    pc_before = m_model.zPC;
    bitten_before = m_inner.watchdog_bitten();
    m_inner.reset_die();
    pc_after = m_model.zPC;
    bitten_after = m_inner.watchdog_bitten();
  }

  uint64_t advances = 0;
  uint64_t delivered = 0;
  uint64_t resets = 0;
  uint64_t pc_before = 0;
  uint64_t pc_after = 0;
  bool bitten_before = false;
  bool bitten_after = false;

private:
  hart::Model &m_model;
  rot::model_watchdog m_inner;
};

// A step number for the generated step function, which takes the model's own
// arbitrary-precision integer.
class step_number {
public:
  step_number() { mpz_init_set_ui(m_value, 0); }
  ~step_number() { mpz_clear(m_value); }
  step_number(const step_number &) = delete;
  step_number &operator=(const step_number &) = delete;
  void next() { mpz_add_ui(m_value, m_value, 1); }

  mpz_t m_value;
};

// Whether the core is running at all. `Stopped` is the stopped main clock: the
// model's step function is never called and its retirement-driven platform
// tick never fires, so nothing inside the machine moves between external
// events.
enum class Core { Stopped, Running };

// Whether the capability holder answers the challenge inside the window.
enum class Petter { Stopped, Answering };

struct Outcome {
  uint64_t rounds = 0;
  uint64_t steps = 0;
  uint64_t retired = 0;
  uint64_t main_clock_ticks = 0;
  uint64_t external_ticks = 0;
  // What the join had delivered after the absorbing-latch probe below, which
  // fires one more event than the measured loop did. Reported separately so
  // that `external_ticks` is exactly the schedule the case ran on and neither
  // figure has to be read as standing for the other.
  uint64_t external_ticks_after_probe = 0;
  uint64_t pets = 0;
  uint64_t resets = 0;
  uint64_t ticks_at_end = 0;
  bool bitten = false;
  bool exception_seen = false;
  bool die_reset_observed = false;
};

// One die, brought up and reset, for the length of one case. The latch has no
// clearing mechanism anywhere in the model, so a case that bites cannot be
// followed by another on the same die; each case gets its own.
class Harness {
public:
  explicit Harness(hart::Model &model) : m_model(model) {
    m_model.model_init();
    m_model.zset_pc_reset_address(RESET_VECTOR);
    // The two acts `init_model` performs once the configuration has been
    // accepted. The configuration assert is not repeated here: the build
    // validates every shipped configuration against the regenerated schema,
    // and what this harness needs is the die in its reset state.
    m_model.zblkdev_initializze(UNIT);
    m_model.zreset(UNIT);
    // Running-clock controls execute real NOPs. An uninitialized word would
    // now enter the independently specified second-trap fail-stop path and
    // intentionally bite without waiting for a slow-clock timeout.
    for (uint64_t address : {RESET_VECTOR, ELSEWHERE}) {
      constexpr uint32_t nop = 0x00000013;
      for (unsigned byte = 0; byte < 4; ++byte) {
        write_mem(address + byte, static_cast<uint8_t>(nop >> (8 * byte)));
      }
    }
    require(m_model.zPC == RESET_VECTOR, "the die did not come up at its reset vector");
    require(m_model.zrot_run_startup_tests(UNIT), "the entropy root must pass its start-up tests");
    m_model.zwatchdog_arm(UNIT);
    require(m_model.zwatchdog_nonce != 0, "an armed watchdog must hold an outstanding challenge");
    require(!m_model.zwatchdog_bitten && m_model.zwatchdog_ticks == 0, "arming did not open the window");
  }

  ~Harness() { m_model.model_fini(); }
  Harness(const Harness &) = delete;
  Harness &operator=(const Harness &) = delete;

  uint64_t early() { return static_cast<uint64_t>(m_model.zplat_rot_watchdog_early); }
  uint64_t late() { return static_cast<uint64_t>(m_model.zplat_rot_watchdog_late); }
  hart::Model &model() { return m_model; }

  // One case. `ticks_per_round` is what the external source produces between
  // pumps; zero is the detached clock the control case uses.
  Outcome run(Core core, Petter petter, uint64_t ticks_per_round, uint64_t round_cap) {
    observed_device device(m_model);
    rot::injected_slow_clock clock;
    rot::watchdog_join join(device, clock);
    Outcome out;

    require(device.watchdog_present(), "the composition must declare a watchdog");

    const uint64_t retired_before = m_model.zretire_count;

    for (uint64_t round = 0; round < round_cap; ++round) {
      ++out.rounds;

      if (core == Core::Running) {
        // The core runs. The model's own step function is called, and the
        // retirement-driven platform tick fires beside it, which is the clock
        // the emulator advances once per `instructions_per_tick` retired
        // instructions. Neither is an input to the external source below.
        if (!m_model.have_exception) {
          ++out.steps;
          m_model.ztry_step(m_step.m_value, true);
          m_step.next();
        }
        out.exception_seen = out.exception_seen || m_model.have_exception;
        m_model.ztick_clock(UNIT);
        ++out.main_clock_ticks;
      }

      if (petter == Petter::Answering && !m_model.zwatchdog_bitten
          && m_model.zwatchdog_ticks >= early()) {
        // Answer inside the window, which needs the counter past the early
        // bound: an early pet is a bite too (R-15-240).
        ++out.pets;
        require(m_model.zwatchdog_pet(m_model.zwatchdog_nonce) == hart::zPet_Accepted,
                "a pet inside the window against the outstanding challenge was refused");
      }

      // Place the die away from its reset vector, so that the reset a bite
      // asserts is a move this harness can see rather than a value that was
      // right already. It is written each round because a core that runs is a
      // core that moves its own PC, and after a fetch that faults at the
      // address above the model puts it back at the reset vector on its own.
      // Writing the register is the harness acting on the machine, exactly as
      // test_rot.sail's properties clear a latch the machine cannot clear.
      m_model.zPC = ELSEWHERE;
      m_model.znextPC = ELSEWHERE;

      // The external event. It carries its own tick count and is produced by
      // the host, so it is the same in every case above.
      if (ticks_per_round > 0) {
        clock.fire(ticks_per_round);
      }

      if (join.pump()) {
        out.die_reset_observed = true;
        break;
      }
    }

    out.retired = m_model.zretire_count - retired_before;
    out.external_ticks = join.delivered();
    out.resets = join.die_resets();
    out.bitten = m_model.zwatchdog_bitten;
    out.ticks_at_end = m_model.zwatchdog_ticks;

    require(out.external_ticks == device.delivered, "the join delivered a count the device did not see");
    require(out.resets == device.resets, "the join counted a die reset the device did not take");

    if (out.resets > 0) {
      require(device.pc_before == ELSEWHERE, "the die was already at its reset vector before the bite");
      require(device.pc_after == RESET_VECTOR, "the bite did not put the die back at its reset vector");
      // The watchdog is a failure domain disjoint from the cores (R-15-240),
      // so the die reset it asserts does not clear its own record of why.
      require(device.bitten_before && device.bitten_after,
              "the die reset cleared the RoT's latch, which is not the RoT's domain to reset");
    }

    // The latch is absorbing and nothing clears it, so a further external
    // event neither advances a bitten watchdog nor asserts a second reset.
    // This probe is outside the measured schedule: it fires one event even in
    // the detached-clock case, whose loop fired none, so its delivery is
    // reported as its own figure rather than folded into `external_ticks`.
    const uint64_t ticks_before_extra = m_model.zwatchdog_ticks;
    clock.fire(ticks_per_round + 1);
    require(!join.pump(), "a second pump asserted the die reset again");
    require(join.die_resets() == out.resets, "the die reset is not asserted exactly once");
    if (out.bitten) {
      require(m_model.zwatchdog_ticks == ticks_before_extra, "a bitten watchdog kept counting");
    }
    out.external_ticks_after_probe = join.delivered();
    require(out.external_ticks_after_probe == out.external_ticks + ticks_per_round + 1,
            "the absorbing-latch probe did not deliver its own event");

    return out;
  }

private:
  hart::Model &m_model;
  step_number m_step;
};

// The two cases the platform join owes, the control beside them, and the case
// that shows the die reset is the latch's consumer rather than the clock's.
void campaign(bool negative_retirement_bites, bool negative_no_reset) {
  hart::Model model;

  uint64_t early = 0;
  uint64_t late = 0;
  context = "window";
  {
    Harness probe(model);
    early = probe.early();
    late = probe.late();
  }
  require(early > 0 && late > early, "the composition must declare a window");

  // An advance that never crosses the late bound on its own, so the bite is
  // reached by accumulation rather than by one oversized event.
  const uint64_t per_round = early;
  const uint64_t expected_rounds = late / per_round + 1;
  const uint64_t cap = expected_rounds + 8;

  context = "stopped petter";
  Outcome petter;
  {
    Harness h(model);
    petter = h.run(Core::Running, Petter::Stopped, per_round, cap);
  }
  require(petter.bitten, "a core that never answers the challenge was not bitten");
  require(petter.die_reset_observed && petter.resets == 1, "the bite did not assert the die reset");
  require(petter.pets == 0, "the stopped-petter case answered a challenge");
  require(petter.steps > 0, "the core did not run");
  require(petter.main_clock_ticks == petter.rounds, "the main clock did not run beside the core");
  require(petter.rounds == expected_rounds, "the bite did not land at the first round past the late bound");
  require(petter.external_ticks == per_round * expected_rounds, "the external tick count is not the schedule's");
  require(petter.external_ticks > late, "the bite landed inside the window");
  require(petter.ticks_at_end == late + 1, "the expired reading did not saturate at the first tick outside");

  context = "stopped main clock";
  Outcome stalled;
  {
    Harness h(model);
    stalled = h.run(Core::Stopped, Petter::Stopped, per_round, cap);
  }
  require(stalled.bitten, "a core that retires nothing was not bitten");
  require(stalled.die_reset_observed, "the bite was not seen with the core stopped");
  require(negative_no_reset ? stalled.resets == 0 : stalled.resets == 1,
          "the bite did not assert the die reset with the core stopped");
  require(stalled.steps == 0 && stalled.retired == 0 && stalled.main_clock_ticks == 0,
          "the stopped-main-clock case moved the machine");
  require(stalled.rounds == expected_rounds && stalled.external_ticks == petter.external_ticks,
          "the external schedule differed between the two cases");
  require(stalled.ticks_at_end == late + 1, "the expired reading did not saturate with the core stopped");

  // The control: the same core activity, no external clock. If retirement
  // could bite, it would bite here.
  context = "no external clock";
  Outcome control;
  {
    Harness h(model);
    control = h.run(Core::Running, Petter::Stopped, 0, cap);
  }
  require(negative_retirement_bites ? control.bitten : !control.bitten,
          "retirement alone moved the watchdog");
  require(control.resets == 0 && control.external_ticks == 0, "a detached clock asserted a die reset");
  require(control.rounds == cap && control.steps > 0, "the control case did not run the core");
  require(control.ticks_at_end == 0, "a detached clock advanced the counter");
  // The one event the absorbing-latch probe fires after the measured loop, and
  // the only external tick this case ever sees. Its counter reading above is
  // taken before it, which is why both figures are printed below.
  require(control.external_ticks_after_probe == 1, "the control case ran on more than the probe's event");

  // The die stays alive as long as the challenge is answered inside the
  // window, so the join is not biting whatever it is given. The first round
  // opens with the counter at zero, which is inside the early bound and so is
  // not a round the petter may answer in.
  context = "answered challenge";
  Outcome alive;
  {
    Harness h(model);
    alive = h.run(Core::Running, Petter::Answering, early + 1, cap);
  }
  require(!alive.bitten && alive.resets == 0, "an answered challenge still bit");
  require(alive.pets == cap - 1, "the petter did not answer every round it was able to");
  require(alive.external_ticks == (early + 1) * cap, "the external clock did not run under an answered challenge");

  // The die reset is the latch's consumer and not the clock's: a pet against
  // the wrong challenge bites, and the next pump takes the reset with no
  // external tick due at all.
  context = "unmatched pet";
  {
    Harness h(model);
    observed_device device(h.model());
    rot::injected_slow_clock detached;
    rot::watchdog_join join(device, detached);
    h.model().zPC = ELSEWHERE;
    h.model().znextPC = ELSEWHERE;
    require(!join.pump(), "an armed watchdog asserted a die reset");
    require(h.model().zwatchdog_pet(~h.model().zwatchdog_nonce) == hart::zPet_Unmatched,
            "a response that is not the outstanding challenge was accepted");
    require(join.pump(), "a bite from the pet path did not reach the die reset");
    require(join.delivered() == 0 && join.die_resets() == 1, "the pet-path reset needed an external tick");
    require(device.pc_after == RESET_VECTOR && device.bitten_after, "the pet-path bite did not reset the die");
  }

  // Every count below is the measured schedule's, taken before the
  // absorbing-latch probe that follows each case; the control's probe figure is
  // printed beside it because that case's only external event is the probe's.
  std::printf("watchdog join: window=[%" PRIu64 ",%" PRIu64 "] per_round=%" PRIu64
              " stopped_petter{rounds=%" PRIu64 " steps=%" PRIu64 " retired=%" PRIu64
              " main_ticks=%" PRIu64 " external=%" PRIu64 " resets=%" PRIu64 "}"
              " stopped_main_clock{rounds=%" PRIu64 " steps=0 main_ticks=0 external=%" PRIu64
              " resets=%" PRIu64 "} control{rounds=%" PRIu64 " steps=%" PRIu64
              " external=%" PRIu64 " after_probe=%" PRIu64 " resets=%" PRIu64
              "} answered{pets=%" PRIu64 " external=%" PRIu64
              " resets=0} unmatched_pet{external=0 resets=1} sail_exception=%d PASS\n",
              early, late, per_round, petter.rounds, petter.steps, petter.retired,
              petter.main_clock_ticks, petter.external_ticks, petter.resets, stalled.rounds,
              stalled.external_ticks, stalled.resets, control.rounds, control.steps,
              control.external_ticks, control.external_ticks_after_probe, control.resets,
              alive.pets, alive.external_ticks,
              (petter.exception_seen || control.exception_seen || alive.exception_seen) ? 1 : 0);
}

} // namespace

int main(int argc, char **argv) {
  const bool negative_retirement_bites = argc == 2 && std::strcmp(argv[1], "--negative-retirement-bites") == 0;
  const bool negative_no_reset = argc == 2 && std::strcmp(argv[1], "--negative-no-reset") == 0;
  if (argc != 1 && !negative_retirement_bites && !negative_no_reset) return 2;
  sail_config_set_string(get_default_config());
  try {
    campaign(negative_retirement_bites, negative_no_reset);
  } catch (const std::exception &e) {
    std::fprintf(stderr, "watchdog join: FAIL %s\n", e.what());
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
