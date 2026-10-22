#include "cli_options.h"

#include <iostream>

// Link the same parse_cli implementation as the emulator, with no generated
// model or model initialization. Reaching this output proves parsing returned.
int main(int argc, char **argv) {
  const auto opts = parse_cli(argc, argv);
  std::cout << "inst-limit=" << opts.insn_limit << '\n'
            << "rot-slow-clock-ns=" << opts.rot_slow_clock_ns << '\n'
            << "stop-at-pc=";
  if (opts.stop_at_pc) {
    std::cout << *opts.stop_at_pc;
  } else {
    std::cout << "unset";
  }
  std::cout << '\n'
            << "signature-granularity=" << opts.signature_granularity << '\n'
            << "rvfi-dii=" << opts.rvfi_dii_port << '\n'
            << "gdb-server-port=" << opts.gdb_server_port << '\n';
  return 0;
}
