## Test Suites

The simulator supports multiple test suites that are downloaded on-demand during the CMake configure step. Precompiled binaries are downloaded from [sail-riscv-tests releases](https://github.com/riscv-software-src/sail-riscv-tests/releases/). Only their RV64 programs are read, because RV32 is not a configuration of this model.

- **Standard RISC-V Tests** from the [`riscv-tests`](https://github.com/riscv-software-src/riscv-tests) repository: Basic pre-compiled ELFs with fundamental ISA tests, downloaded with `-DENABLE_RISCV_TESTS=ON` (off in [CMakeLists.txt](CMakeLists.txt), on in `build_simulator.sh` and the project's model build). None of them is registered as a test: each addresses memory through an integer written into a base register, which on this purecap machine is an untagged capability, so its first load or store faults. The profile sweep runs the downloaded programs instead.

- **RISC-V Vector Extension Tests** from the [`riscv-vector-tests`](https://github.com/chipsalliance/riscv-vector-tests) repository: Vector extension tests enabled with CMake options like `-DENABLE_RISCV_VECTOR_TESTS_V256_E64=ON` for specific VLEN/ELEN configurations (supported combinations: V64_E64, V128_E64, V256_E64, V512_E64).

- **RISC-V Architectural Certification Tests** from the [`riscv-arch-test`](https://github.com/riscv/riscv-arch-test) repository: Tests designed to certify that a design faithfully implements the RISC-V specification (can be enabled with `-DENABLE_RISCV_ARCH_TESTS=TRUE`).

The vector and architectural tests are stock programs registered without the exclusion `riscv-tests` receives, so they are not a passing suite on this machine, and no project tool enables them. The model's own `$[test]` harness and native harnesses under [`unit_tests`](unit_tests/README.md) are the tests `ctest` runs.
