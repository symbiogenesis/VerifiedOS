// SPDX-License-Identifier: BSD-2-Clause
// The RoT's boot-control window (sys/rot.sail, R-09-028, R-09-029, R-09-006),
// executed against the actual generated Sail model under the RoT composition
// (model/config/verifiedos-rot.json) and under configuration variants of it.
//
// **What the Sail properties cannot supply on their own.** unit_tests/
// test_rot.sail states the doors: the latch, the slot and the count read their
// power-on values, the slot and the count take writes and survive a die reset,
// a slot above 1 and a release word other than 1 fault, a release latches and a
// die reset does not clear it, and every other class and every narrower width
// is refused. The `unit_tests` harness runs them under the default
// configuration, whose latch, slot and count are all zero, and there a door that
// answered zero for everything would pass. So this harness runs the same
// properties under the shipped RoT composition and under a variant whose three
// values are not zero, and holds the model's power-on state against the values
// the variant wrote, which makes "the latch reads the configuration" a
// comparison rather than two zeros agreeing.
//
// **And the validator's four refusals** (boot-handoff.md section 9.4): a latch
// above 1, a slot above 1, a window narrower than its doors, and a window placed
// over another aperture each make the composition invalid, while the shipped
// file and the variant validate.
//
// The `--negative-latch` arm inverts one expectation, so a harness that could
// not see a latch read back wrong fails visibly rather than passing.
#include <sail_config.h>

#include "file_utils.h"
#include "sail_riscv_model.h"

#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <jsoncons/json.hpp>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

std::string context;

void require(bool condition, const char *message) {
  if (!condition) {
    throw std::runtime_error(context + ": " + message);
  }
}

// One composition: the RoT file with its boot-control row's three power-on
// values and, where a case asks, the window's own placement replaced.
struct Composition {
  uint64_t boot_target = 0;
  uint64_t active_slot = 0;
  uint64_t attempts = 0;
  bool resize = false;
  uint64_t size = 0;
  bool rebase_onto_watchdog = false;
};

// The file is parsed the way the emulator parses it, comments and all, and
// handed to the model as plain JSON.
std::string compose(const jsoncons::json &shipped, const Composition &c) {
  jsoncons::json config = shipped;
  const jsoncons::json watchdog_base = shipped.at("platform").at("watchdog").at("base");
  jsoncons::json &window = config["platform"]["boot_control"];
  window["boot_target"] = c.boot_target;
  window["active_slot"] = c.active_slot;
  window["attempts"] = c.attempts;
  if (c.resize) {
    window["size"] = c.size;
  }
  if (c.rebase_onto_watchdog) {
    window["base"] = watchdog_base;
  }
  std::ostringstream os;
  os << config;
  return os.str();
}

// One die for the length of one check, brought up as `init_model` brings it up
// once a configuration is accepted. Whether the composition is valid is the
// caller's question, so it is not asserted here.
class Die {
public:
  Die(hart::Model &model, const std::string &json) : m_model(model) {
    sail_config_set_string(json.c_str());
    m_model.model_init();
    m_model.zblkdev_initializze(UNIT);
    m_model.zreset(UNIT);
  }
  ~Die() {
    m_model.model_fini();
  }
  Die(const Die &) = delete;
  Die &operator=(const Die &) = delete;

private:
  hart::Model &m_model;
};

// The Sail properties, each on a die of its own: the release property latches
// `rot_released` and nothing clears it, so no property may follow it on the die
// it ran on.
struct Property {
  const char *name;
  void (*run)(hart::Model &);
};

const Property PROPERTIES[] = {
  {"power-on values", [](hart::Model &m) { m.ztest_the_boot_control_doors_read_their_power_on_values(UNIT); }},
  {"writes and die reset",
   [](hart::Model &m) { m.ztest_the_boot_slot_and_count_take_writes_and_survive_a_die_reset(UNIT); }},
  {"refusals and release",
   [](hart::Model &m) { m.ztest_a_slot_outside_the_pair_and_a_release_word_other_than_one_fault(UNIT); }},
  {"requester and width",
   [](hart::Model &m) { m.ztest_the_boot_control_window_answers_the_rot_alone_and_doublewords_only(UNIT); }},
};

// A valid composition: it validates, the composed hart is the RoT, the model's
// power-on state holds what the composition wrote, nothing is released, and
// every property holds on it.
void run_valid(
  hart::Model &model,
  const jsoncons::json &shipped,
  const Composition &c,
  const char *name,
  uint64_t expected_latch
) {
  const std::string json = compose(shipped, c);
  context = name;
  {
    Die die(model, json);
    require(model.zconfig_is_valid(UNIT), "the composition does not validate");
    require(model.zrot_is_composed_hart(UNIT), "the composition does not compose the RoT");
    require(model.zplat_have_boot_control, "the composition declares no boot-control window");
    require(model.zboot_target_latch == expected_latch, "the latch is not its configured value");
    require(model.zboot_active_slot == c.active_slot, "the active slot is not its configured value");
    require(model.zboot_attempts == c.attempts, "the attempt count is not its configured value");
    require(!model.zrot_released, "a release is latched at power-on");
  }
  for (const Property &p : PROPERTIES) {
    context = std::string(name) + ": " + p.name;
    Die die(model, json);
    p.run(model);
    require(!model.have_exception, "the property raised a Sail exception");
  }
}

// An invalid composition: the validator refuses it.
void run_refused(hart::Model &model, const jsoncons::json &shipped, const Composition &c, const char *name) {
  context = name;
  Die die(model, compose(shipped, c));
  require(!model.zconfig_is_valid(UNIT), "the validator accepted it");
}

void campaign(const std::string &config_path, bool negative_latch) {
  context = config_path;
  const jsoncons::json shipped = jsoncons::json::parse(read_file_to_string(config_path));
  const jsoncons::json &row = shipped.at("platform").at("boot_control");

  // The shipped values are the contract's: latch 0, slot A, no attempts.
  Composition as_shipped;
  as_shipped.boot_target = row.at("boot_target").as<uint64_t>();
  as_shipped.active_slot = row.at("active_slot").as<uint64_t>();
  as_shipped.attempts = row.at("attempts").as<uint64_t>();
  require(
    as_shipped.boot_target == 0 && as_shipped.active_slot == 0 && as_shipped.attempts == 0,
    "the shipped boot-control values are not latch 0, slot A and no attempts"
  );

  hart::Model model;
  run_valid(model, shipped, as_shipped, "shipped", 0);

  Composition variant;
  variant.boot_target = 1;
  variant.active_slot = 1;
  variant.attempts = 2;
  run_valid(model, shipped, variant, "variant", negative_latch ? 0 : 1);

  Composition latch_two;
  latch_two.boot_target = 2;
  run_refused(model, shipped, latch_two, "boot_target 2");

  Composition slot_two;
  slot_two.active_slot = 2;
  run_refused(model, shipped, slot_two, "active_slot 2");

  Composition narrow;
  narrow.resize = true;
  narrow.size = 16;
  run_refused(model, shipped, narrow, "size 16");

  Composition overlapping;
  overlapping.rebase_onto_watchdog = true;
  run_refused(model, shipped, overlapping, "base on the watchdog");

  std::printf(
    "boot control: shipped{latch=0 slot=0 attempts=0} variant{latch=1 slot=1 attempts=2} "
    "properties=%zu per composition refused{boot_target=2 active_slot=2 size=16 overlap} PASS\n",
    sizeof(PROPERTIES) / sizeof(PROPERTIES[0])
  );
}

} // namespace

int main(int argc, char **argv) {
  std::string config_path;
  bool negative_latch = false;
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
      config_path = argv[++i];
    } else if (std::strcmp(argv[i], "--negative-latch") == 0) {
      negative_latch = true;
    } else {
      return 2;
    }
  }
  if (config_path.empty()) {
    return 2;
  }
  try {
    campaign(config_path, negative_latch);
  } catch (const std::exception &e) {
    std::fprintf(stderr, "boot control: FAIL %s\n", e.what());
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
