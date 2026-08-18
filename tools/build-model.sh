#!/bin/bash
# M0.6a: build the curated model (model/, vendored from sail-riscv @ 8f91355e) out-of-tree
# on the WSL filesystem, and run its bundled suite. Exit criterion is parity with the M0.3
# baseline: 664/664 green under ctest.
#
# Sail 0.20.2's C++ emission overflows the default 8MB OCaml native stack on the full model
# (M0.3 finding, twice reproduced); raise the limit for the whole build.
ulimit -s 131072
eval $(opam env --switch=default)
SRC=/mnt/c/Users/symbi/source/repos/VerifiedOS/model
BLD=/root/build/verifiedos-model
LOG=/root/logs/model-build.log
mkdir -p /root/logs
rm -f "$LOG"
{
  echo "== sail: $(sail --version)"
  cmake -S "$SRC" -B "$BLD" -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_GMP=FALSE -DENABLE_RISCV_TESTS=TRUE
  echo "CONFIGURE_EXIT=$?"
  cmake --build "$BLD"
  echo "BUILD_EXIT=$?"
  ctest --test-dir "$BLD" -j12 2>&1 | tail -40
  echo "TEST_EXIT=${PIPESTATUS[0]}"
} >> "$LOG" 2>&1
echo "ALL_DONE" >> "$LOG"
