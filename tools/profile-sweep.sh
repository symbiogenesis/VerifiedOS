#!/bin/bash
# Run the downloaded riscv-tests physical-variant ELFs against the *profile*
# configuration (model/config/verifiedos.json) rather than the max configuration
# the bundled ctest suite uses, and classify each one.
#
# The two runs answer different questions. ctest asks whether the curated model
# is still a correct RISC-V implementation of everything it still implements;
# this sweep asks what the frozen profile refuses, which is the number each
# M0.6c/M0.6d batch reports and every refusal is owed an explanation.
#
#   PASS   the test runs to completion and signals success
#   REFUSE the sim exits non-zero: the test executes surface the profile deletes
#   HANG   the test neither passes nor exits within the timeout, which is a
#          refusal that blocks rather than fails (c3's `si-p-dirty` finding), so
#          it is classified rather than left to a ctest timeout
#
# Usage: tools/profile-sweep.sh [xlen] [output]      (defaults: 64, stdout)
VOS_TOOLS=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)
[ -f "$VOS_TOOLS/wsl-env.sh" ] || VOS_TOOLS=/mnt/c/Users/symbi/source/repos/VerifiedOS/tools
. "$VOS_TOOLS/wsl-env.sh"

SRC=/mnt/c/Users/symbi/source/repos/VerifiedOS/model
BLD=${VOS_BUILD_DIR:-/root/build/verifiedos-model}
SIM=$BLD/c_emulator/sail_riscv_sim
CONFIG=$SRC/config/verifiedos.json
XLEN=${1:-64}
TESTS=$(ls -d "$BLD"/test/*/riscv-tests 2>/dev/null | head -1)
TIMEOUT=${VOS_SWEEP_TIMEOUT:-10}

[ -x "$SIM" ] || { echo "no simulator at $SIM; run tools/build-model.sh first" >&2; exit 1; }
[ -d "$TESTS" ] || { echo "no downloaded riscv-tests under $BLD/test" >&2; exit 1; }

pass=0 refuse=0 hang=0
for elf in "$TESTS"/rv${XLEN}*-p-*; do
  case "$elf" in *.dump) continue;; esac
  name=$(basename "$elf")
  if timeout "$TIMEOUT" "$SIM" --config "$CONFIG" "$elf" >/dev/null 2>&1; then
    echo "PASS $name"; pass=$((pass + 1))
  else
    rc=$?
    if [ "$rc" = 124 ]; then echo "HANG $name"; hang=$((hang + 1))
    else echo "REFUSE $name rc=$rc"; refuse=$((refuse + 1)); fi
  fi
done
echo "TOTAL pass=$pass refuse=$refuse hang=$hang of $((pass + refuse + hang))"
