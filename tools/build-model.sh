#!/bin/bash
# M0.6a: build the curated model (model/, vendored from sail-riscv @ 8f91355e) out-of-tree
# on the WSL filesystem, and run its bundled suite. Exit criterion is parity with the M0.3
# baseline: 664/664 green under ctest.
#
# Sail 0.20.2's C++ emission overflows the default 8MB OCaml native stack on the full model
# (M0.3 finding, twice reproduced); raise the limit for the whole build.
#
# FAST=1 selects the iterate profile: a separate build dir whose only divergence from the
# canonical build is dropping `-g` from RelWithDebInfo. Debug info on the machine-generated
# model translation unit is the single largest compile cost (measured 314s of the build's
# ~7min serial spine) and is never used; optimization level, assertions, and the test suite
# are identical. The canonical build (FAST unset) remains the exit criterion for every batch.
ulimit -s 131072
eval $(opam env --switch=default)
SRC=/mnt/c/Users/symbi/source/repos/VerifiedOS/model
if [ "${FAST:-0}" = "1" ]; then
  BLD=/root/build/verifiedos-model-fast
  LOG=/root/logs/model-build-fast.log
  FLAGS=("-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG" "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG")
  # Seed the pre-downloaded test ELFs from the canonical build dir so the fast
  # dir's first configure doesn't re-download the tarball.
  if [ ! -d "$BLD/test/2026-06-10" ] && [ -d /root/build/verifiedos-model/test/2026-06-10 ]; then
    mkdir -p "$BLD/test"
    cp -r /root/build/verifiedos-model/test/2026-06-10 "$BLD/test/2026-06-10"
  fi
  # Seed the Sail SMT memo cache likewise: a cold cache re-discharges every Z3
  # obligation and turns the ~2min emission into ~25min (measured once). The
  # cache is content-keyed, so a stale copy only costs misses.
  if [ ! -f "$BLD/model/sail_smt_cache" ] && [ -f /root/build/verifiedos-model/model/sail_smt_cache ]; then
    mkdir -p "$BLD/model"
    cp /root/build/verifiedos-model/model/sail_smt_cache "$BLD/model/sail_smt_cache"
  fi
else
  BLD=/root/build/verifiedos-model
  LOG=/root/logs/model-build.log
  FLAGS=()
fi
mkdir -p /root/logs
rm -f "$LOG"
{
  echo "== sail: $(sail --version)"
  cmake -S "$SRC" -B "$BLD" -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_GMP=FALSE -DENABLE_RISCV_TESTS=TRUE "${FLAGS[@]}"
  echo "CONFIGURE_EXIT=$?"
  cmake --build "$BLD"
  echo "BUILD_EXIT=$?"
  ctest --test-dir "$BLD" -j12 2>&1 | tail -40
  echo "TEST_EXIT=${PIPESTATUS[0]}"
} >> "$LOG" 2>&1
echo "ALL_DONE" >> "$LOG"
