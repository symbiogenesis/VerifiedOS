#!/bin/bash
# Typecheck the curated model without emitting code. The fast inner loop for the
# M0.6c deletion campaign: Sail reports every dangling reference a cut leaves behind,
# in seconds rather than the minutes a full C++ emission and compile take.
# The full build (tools/build-model.sh) remains the exit criterion for each batch.
VOS_TOOLS=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)
[ -f "$VOS_TOOLS/wsl-env.sh" ] || VOS_TOOLS=/mnt/c/Users/symbi/source/repos/VerifiedOS/tools
. "$VOS_TOOLS/wsl-env.sh"
cd /mnt/c/Users/symbi/source/repos/VerifiedOS/model/model || exit 1
exec sail \
  --strict-var --strict-bitvector --strict-exponentials \
  --memo-z3 --memo-z3-path /root/build/verifiedos-typecheck-smt-cache \
  --just-check \
  --all-modules riscv.sail_project
