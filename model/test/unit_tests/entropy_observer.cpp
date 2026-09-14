// SPDX-License-Identifier: Apache-2.0
// Execute the actual generated Sail root and watchdog tests through an observer.
#include <sail_config.h>
#include "config_utils.h"
#include "sail_riscv_model.h"
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <utility>
#include <vector>

static void require(bool condition) {
  if (!condition) std::abort();
}

class ObservedModel final : public hart::Model {
public:
  std::vector<std::pair<bool, uint64_t>> draws;
  bool refuse = false;

  unit entropy_draw_callback(bool available, uint64_t value) override {
    if (refuse) throw std::runtime_error("capture refused");
    require(available || value == 0);
    draws.emplace_back(available, value);
    return UNIT;
  }
};

int main() {
  sail_config_set_string(get_default_config());
  ObservedModel model;
  model.model_init();
  model.ztest_the_root_tests_every_source_before_the_first_draw(UNIT);
  require(model.draws.size() == 3);
  require(!model.draws[0].first && model.draws[1].first && model.draws[2].first);
  require(model.draws[1].second != model.draws[2].second);
  model.model_fini();

  model.draws.clear();
  model.model_init();
  model.ztest_a_pet_is_a_challenge_response_and_the_challenge_moves(UNIT);
  require(model.draws.size() == 2); // arm and accepted pet; unmatched pet draws nothing
  require(model.draws[0].first && model.draws[1].first);
  require(model.draws[0].second != model.draws[1].second);
  model.model_fini();

  model.draws.clear();
  model.model_init();
  model.ztest_a_pet_outside_the_window_bites_at_either_end(UNIT);
  require(model.draws.size() == 2); // only the two arms, no early/late/bitten pet
  model.model_fini();

  model.draws.clear();
  model.model_init();
  model.ztest_a_stopped_entropy_root_leaves_the_watchdog_no_challenge(UNIT);
  require(model.draws.size() == 2 && model.draws[0].first && !model.draws[1].first);
  model.model_fini();

  // A fresh run reproduces the seed's result; observing did not perturb it.
  const auto first = model.draws[0];
  model.draws.clear();
  model.model_init();
  require(model.zrot_run_startup_tests(UNIT));
  model.zwatchdog_arm(UNIT);
  require(model.draws.size() == 1 && model.draws[0] == first);
  model.refuse = true;
  bool caught = false;
  try { model.zwatchdog_arm(UNIT); }
  catch (const std::runtime_error &) { caught = true; }
  require(caught && model.draws.size() == 1);
  model.model_fini();
  hart::Model unobserved;
  unobserved.model_init();
  require(unobserved.zrot_run_startup_tests(UNIT));
  unobserved.zwatchdog_arm(UNIT);
  require(unobserved.zwatchdog_nonce == (first.second == 0 ? UINT64_MAX : first.second));
  unobserved.model_fini();
  std::puts("entropy observer: direct/refused/watchdog/ordering/abort PASS");
}
