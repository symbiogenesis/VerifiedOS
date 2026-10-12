// SPDX-License-Identifier: Apache-2.0
// Private pipe endpoint for the development entropy checkpoint. Never run with
// stdout redirected to a file: capture frames carry transient conditioned words.
#include "file_utils.h"
#include "sail_riscv_model.h"
#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <jsoncons/json.hpp>
#include <sail_config.h>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

class Refused final : public std::exception {};

class ControlledModel final : public hart::Model {
public:
  bool replay;
  uint64_t point = 0;
  explicit ControlledModel(bool is_replay) : replay(is_replay) {
  }

  void frame(const char *kind) {
    // This is a call-level coordinate: no instruction retirement is claimed.
    std::printf("%s %" PRIu64 " %" PRIu64 " 0 0\n", kind, point, zmhartid);
    std::fflush(stdout);
  }
  std::string reply() {
    std::string response;
    char next;
    while (std::cin.get(next)) {
      if (next == '\n') {
        return response;
      }
      if (response.size() == 16) {
        throw Refused();
      }
      response.push_back(next);
    }
    throw Refused();
  }
  void admit() {
    if (reply() != "go") {
      throw Refused();
    }
  }

  unit entropy_draw_begin_callback(unit) override {
    frame("B");
    admit();
    return UNIT;
  }
  unit entropy_draw_callback(bool available, uint64_t value) override {
    if (!available && value != 0) {
      throw Refused();
    }
    std::printf("E %" PRIu64 " %" PRIu64 " 0 0 %d", point, zmhartid, available ? 1 : 0);
    if (!replay && available) {
      std::printf(" %016" PRIx64, value);
    }
    std::puts("");
    std::fflush(stdout);
    admit();
    return UNIT;
  }
  uint64_t entropy_draw_value_callback(uint64_t value) override {
    if (!replay) {
      return value;
    }
    frame("V");
    const std::string word = reply();
    if (word.size() != 16 || word.find_first_not_of("0123456789abcdef") != std::string::npos) {
      throw Refused();
    }
    return std::stoull(word, nullptr, 16);
  }
  std::vector<uint64_t> source_state() const {
    return {zrot_source_state.data, zrot_source_state.data + zrot_source_state.len};
  }
};

int main(int argc, char **argv) {
  if (argc != 3 || (std::strcmp(argv[1], "capture") && std::strcmp(argv[1], "replay"))) {
    return 2;
  }
  const struct rlimit no_core{0, 0};
  if (setrlimit(RLIMIT_CORE, &no_core)) {
    return 2;
  }
  struct stat in{}, out{};
  if (fstat(STDIN_FILENO, &in) || fstat(STDOUT_FILENO, &out) || !S_ISFIFO(in.st_mode) || !S_ISFIFO(out.st_mode)) {
    return 2;
  }
  try {
    const std::string config = jsoncons::json::parse(read_file_to_string(argv[2])).to_string();
    sail_config_set_string(config.c_str());
    ControlledModel model(!std::strcmp(argv[1], "replay"));
    model.model_init();
    auto before = model.source_state();
    try {
      std::printf("O before-startup %d\n", model.zreplay_test_direct_draw(UNIT));
      std::printf("O startup %d\n", model.zrot_run_startup_tests(UNIT));
      model.point = 1;
      before = model.source_state();
      std::printf("O direct %d\n", model.zreplay_test_direct_draw(UNIT));
      model.point = 2;
      before = model.source_state();
      std::printf("O mmio %d\n", model.zreplay_test_mmio_draw(UNIT));
      model.point = 3;
      before = model.source_state();
      model.zwatchdog_arm(UNIT);
      std::printf("O arm %d\n", !model.zwatchdog_bitten && model.zwatchdog_nonce != 0);
      model.point = 4;
      before = model.source_state();
      std::printf("O accepted-pet %d\n", model.zreplay_test_accepted_pet(UNIT));
      model.point = 5;
      before = model.source_state();
      std::printf("O rejected-pet %d\n", model.zreplay_test_rejected_pet(UNIT));
      std::printf("O bitten %d\n", model.zwatchdog_bitten);
      model.zrot_entropy_fail_stop = true;
      model.point = 6;
      std::printf("O latched-refusal %d\n", model.zreplay_test_direct_draw(UNIT));
      std::puts("Z");
      std::fflush(stdout);
      model.model_fini();
      return 0;
    } catch (const Refused &) {
      // No source words are disclosed. Only preflight refusals promise equality.
      std::printf("A %d\n", model.source_state() == before);
      std::fflush(stdout);
      model.model_fini();
      return 3;
    }
  } catch (...) {
    // Do not format an exception whose diagnostic might contain a secret frame.
    std::fputs("entropy checkpoint failed\n", stderr);
    return 1;
  }
}
