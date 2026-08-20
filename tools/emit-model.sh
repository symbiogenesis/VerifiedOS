#!/bin/bash
# The middle loop for the M0.6c deletion campaign, between tools/check-model.sh
# (typecheck only, ~30s) and tools/build-model.sh (full build + ctest, ~15min):
# run the full C++ emission (~2min), which regenerates the config schema, then hand
# the fresh schema and the frozen profile to tools/validate-config.py, which states
# what the check decides and why. No C++ is compiled, so the full build stays the
# exit criterion for each batch.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wsl-env.sh"
SRC=$VOS_MODEL
BLD=$VOS_BUILD_ROOT/verifiedos-model
# Reuse build-model.sh's configured canonical build tree; configure if absent.
if [ ! -f "$BLD/build.ninja" ]; then
  cmake -S "$SRC" -B "$BLD" -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_GMP=FALSE -DENABLE_RISCV_TESTS=TRUE "${VOS_CMAKE_CCACHE[@]}" || exit 1
fi
# Single-threaded stage; -j is passed for uniformity, not for speed.
vos_stage emit cmake --build "$BLD" -j "$VOS_JOBS" --target generated_sail_riscv_model || exit 1
exec python3 "$VOS_TOOLS/validate-config.py" \
  "$BLD/sail_riscv_config_schema.json" "$SRC/config/verifiedos.json"
