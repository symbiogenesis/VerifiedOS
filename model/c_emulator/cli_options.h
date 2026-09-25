#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

const unsigned DEFAULT_SIGNATURE_GRANULARITY = 4;

struct CLIOptions {
  bool do_show_times = false;
  bool do_print_version = false;
  bool do_print_build_info = false;
  bool do_print_default_config = false;
  bool do_print_config_schema = false;
  bool do_print_dts = false;
  bool do_validate_config = false;
  bool do_print_isa = false;
  std::string dump_memory_prefix = {};
  bool do_print_gdb_target_xml = false;
  bool disable_trap_loop_detection = false;
  std::string config_file = {};
  std::vector<std::string> config_overrides = {};
  std::string term_log = {};
  std::string trace_log_path = {};
  std::string dtb_file;
  unsigned rvfi_dii_port = 0;
  unsigned gdb_server_port = 0;
  std::vector<std::string> elfs;
  uint64_t insn_limit = 0;
  std::optional<uint64_t> stop_at_pc;

  // Host nanoseconds per RoT slow-clock tick (R-15-240, R-15-196). Zero, the
  // default, leaves the external clock absent and the watchdog unadvanced, so
  // an ordinary run is unchanged. This is a host emulation fact and not a
  // declared ratio between the two clocks: it reaches no configuration file and
  // no attested devicetree node, exactly as the entropy seed does not.
  //
  // It carries no lower bound on purpose, because the useful period depends on
  // the host and on the program: the emulator delivers ticks once per loop
  // iteration, so a period for which the window's late bound is shorter than
  // the host cost of a few emulated steps expires while the run is still
  // starting, and the bite reports a retired count in the low single digits
  // instead of a stalled core's. That is a true reading of a clock the core
  // cannot outrun rather than a bug, but it is not a timeout, so the bite line
  // prints the retired instruction count beside the tick count and a run
  // meaning to observe a wedged core should choose a period whose late bound is
  // longer than the program's own host running time.
  uint64_t rot_slow_clock_ns = 0;

  // The block device's host backing image (c_emulator/blkdev_image.h): an
  // existing image to open, or a new one to create from the configured
  // fixture, and an optional new receipt file for its events. Harness inputs;
  // no host path reaches the guest.
  std::string blkdev_image = {};
  std::string blkdev_image_create = {};
  std::string blkdev_receipt = {};

  std::string sig_file = {};
  unsigned signature_granularity = DEFAULT_SIGNATURE_GRANULARITY;

#ifdef SAILCOV
  std::string sailcov_file = {};
#endif

  bool config_print_instr = false;
  bool config_print_gpr = false;
  bool config_print_vreg = false;
  bool config_print_csr = false;
  bool config_print_mem_access = false;
  bool config_print_clint = false;
  bool config_print_exception = false;
  bool config_print_interrupt = false;
  bool config_print_htif = false;
  bool config_print_pma = false;
  bool config_print_rvfi = false;
  // The capability-widened commit trace of docs/assurance/differential-corpus.md (M0.12).
  bool config_print_commit = false;
  bool config_print_step = false;
  bool config_print_gdbserver = false;

  bool config_use_abi_names = false;

  bool config_enable_experimental_extensions = false;
};

// Parse CLI options. This calls `exit()` on failure.
CLIOptions parse_cli(int argc, char **argv);
