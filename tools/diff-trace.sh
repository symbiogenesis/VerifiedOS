#!/bin/bash
# M0.6e (e5): the differential rig. Run the curated model and the M0.4 oracle
# over the same programs and adjudicate their traces against each other.
#
# The two executors are the transplant's whole check until the purecap corpus of
# M0.12 exists: the oracle (`cheri_riscv_sim_RV64`, upstream sail-cheri-riscv at
# the pinned commit) implements the same ISAv9 capability format and the same
# capability instructions, so over a program both machines can run they must
# retire the same instructions and write the same values. The Sail model this
# repository curates is the reference on every divergence; the oracle is
# evidence, never authority.
#
# What the rig can and cannot say today is set by the corpus, not by the rig.
# `riscv-tests` is integer-addressed, exercises no capability instruction, and
# runs on two machines that differ in privilege modes, CSR bank, and boot path,
# so agreement over it is evidence about the *base* the transplant did not
# disturb and nothing more. The capability surface is exercised by the model's
# own `$[test]` properties (model/model/unit_tests/test_cheri_insts.sail) until
# M0.12 versions programs that both executors can run and that use it.
#
# The figure each member reports is the **agreeing prefix**, and over
# `riscv-tests` it is bounded by the corpus rather than by the transplant: the
# tests' own prologue writes `medeleg`, which is an illegal instruction here and
# retires on the oracle, and the tests guard exactly that by pointing `mtvec` at
# the instruction after the group, so both machines reach the same result by
# different routes. The regression is therefore that the prefix must not
# *shorten*, which `--floor` enforces.
#
# Usage: tools/diff-trace.sh [--floor N] [elf ...]
#        tools/diff-trace.sh [--floor N] --corpus   (every rv64ui-p-* in the suite)
#
# Exit status is 0 when every member's prefix reached the floor and 1 otherwise.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wsl-env.sh"

BLD=${VOS_BUILD_DIR:-$VOS_BUILD_ROOT/verifiedos-model}
SIM=$BLD/c_emulator/sail_riscv_sim
CONFIG=$VOS_MODEL/config/verifiedos.json
ORACLE=${VOS_ORACLE:-$VOS_BUILD_ROOT/sail-cheri-riscv-bb07488d/c_emulator/cheri_riscv_sim_RV64}
LIMIT=${VOS_DIFF_LIMIT:-100000}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

[ -x "$SIM" ]    || { echo "no curated simulator at $SIM; run tools/build-model.sh first" >&2; exit 1; }
[ -x "$ORACLE" ] || { echo "no M0.4 oracle at $ORACLE; see checklist M0.4" >&2; exit 1; }

FLOOR=0
if [ "${1:-}" = "--floor" ]; then FLOOR=$2; shift 2; fi

if [ "${1:-}" = "--corpus" ]; then
  TESTS=$(ls -d "$BLD"/test/*/riscv-tests 2>/dev/null | head -1)
  [ -d "$TESTS" ] || { echo "no downloaded riscv-tests under $BLD/test" >&2; exit 1; }
  set -- $(ls "$TESTS"/rv64ui-p-* | grep -v '\.dump$')
fi
[ "$#" -gt 0 ] || { echo "usage: $0 [--corpus] [elf ...]" >&2; exit 1; }

agree=0 prefix=0 short=0 skip=0
shortest=
for elf in "$@"; do
  name=$(basename "$elf")

  "$SIM" --config "$CONFIG" --trace-instr --trace-gpr --trace-mem \
         --inst-limit "$LIMIT" "$elf" > "$WORK/curated.raw" 2>&1
  "$ORACLE" -v -l "$LIMIT" "$elf" > "$WORK/oracle.raw" 2>&1

  python3 "$VOS_TOOLS/trace-normalize.py" --dialect curated "$WORK/curated.raw" > "$WORK/curated.norm"
  python3 "$VOS_TOOLS/trace-normalize.py" --dialect oracle  "$WORK/oracle.raw"  > "$WORK/oracle.norm"

  if [ ! -s "$WORK/curated.norm" ]; then
    # The profile refuses the program outright, which tools/profile-sweep.sh
    # already classifies; there is no trace to adjudicate.
    echo "SKIP    $name (curated model retired nothing)"
    skip=$((skip + 1))
    continue
  fi

  if out=$(python3 "$VOS_TOOLS/diff-trace.py" "$WORK/curated.norm" "$WORK/oracle.norm" --quiet 2>&1); then
    echo "AGREE   $name ($out)"
    agree=$((agree + 1))
    continue
  fi

  n=$(echo "$out" | sed -n 's/^prefix \([0-9]*\) .*/\1/p')
  if [ -z "$shortest" ] || [ "$n" -lt "$shortest" ]; then shortest=$n; fi
  if [ "$n" -lt "$FLOOR" ]; then
    echo "SHORT   $name ($out, below the floor of $FLOOR)"
    python3 "$VOS_TOOLS/diff-trace.py" "$WORK/curated.norm" "$WORK/oracle.norm" | tail -n +2 | sed 's/^/        /'
    short=$((short + 1))
  else
    echo "PREFIX  $name ($out)"
    prefix=$((prefix + 1))
  fi
done

echo "TOTAL agree=$agree prefix=$prefix short=$short skip=$skip of $((agree + prefix + short + skip)); shortest prefix ${shortest:-n/a}"
[ "$short" = 0 ]
