#!/bin/bash
# Shared environment prelude for every WSL-side build loop in this repository:
# tools/check-model.sh, tools/emit-model.sh, tools/build-model.sh. Source it, do
# not execute it.
#
# SCOPE. This file tunes the *build*, never the VM. Nothing here writes
# %USERPROFILE%\.wslconfig, which is the only place WSL2's CPU and RAM
# allocation can be set and which applies to every distribution at once. The
# measurements below say that file would not help anyway; see "what the numbers
# say" at the bottom. The single thing here that outlives a build is the
# keepalive near the bottom, and it is a bounded background process rather than
# a line in that global file for exactly the same reason: it buys the effect
# this repository needs, scoped to the work, and expires on its own.
#
# Two invariants every loop needs, previously copied into each script by hand:
#
#   1. Sail 0.20.2's C++ emission overflows the default 8MB OCaml native stack
#      on the full model (M0.3 finding, twice reproduced).
#   2. The Sail toolchain lives in the opam `default` switch, which a bare
#      `wsl -e bash script.sh` does not put on PATH.
ulimit -s 131072
# Guarded because the Docker lanes source this prelude too, only for the
# keepalive at the bottom, and they have no opam. Nothing is masked by the
# guard: a Sail loop without the switch fails loudly at `sail --version`.
command -v opam >/dev/null 2>&1 && eval $(opam env --switch=default)

# ---------------------------------------------------------------------------
# What the VM actually has
# ---------------------------------------------------------------------------
# Read, never assumed. WSL2 grants the guest every host core by default (12 on
# this machine) and half of host RAM, but .wslconfig can change both without
# this repository knowing, and the scripts should follow the VM rather than
# carry a number that silently stops matching it. This replaces the hardcoded
# `ctest -j12`.
VOS_CPUS=$(nproc)
VOS_MEM_AVAIL_MB=$(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo)

# ---------------------------------------------------------------------------
# Compile parallelism
# ---------------------------------------------------------------------------
# CPUs+2 is Ninja's own default and the right shape for this tree: 366 of the
# 367 translation units are small (softfloat and jsoncons supply most of them)
# and oversubscribing by two keeps cores busy across process startup.
VOS_JOBS=${VOS_JOBS:-$(( VOS_CPUS + 2 ))}

# Memory guard, which does not bind on a default-sized VM and exists so that it
# would bind on a shrunken one. Sized from measurement rather than a rule of
# thumb: the generated model TU peaks at 1.43 GB resident, and it is the only
# large one, so reserve 2 GB for it outright and budget a slim 512 MB for each
# other concurrent job. At 15.7 GB available this yields 24 and the guard is
# inert; under a 4 GB .wslconfig cap it yields 4 and prevents the thrash.
if [ -n "$VOS_MEM_AVAIL_MB" ] && [ "$VOS_MEM_AVAIL_MB" -gt 2048 ]; then
  vos_mem_jobs=$(( (VOS_MEM_AVAIL_MB - 2048) / 512 ))
  [ "$vos_mem_jobs" -lt 1 ] && vos_mem_jobs=1
  [ "$VOS_JOBS" -gt "$vos_mem_jobs" ] && VOS_JOBS=$vos_mem_jobs
fi

# Test parallelism. Each ctest case is one single-threaded sim process with a
# small footprint, so the core count is the whole story and the memory guard
# above does not apply.
VOS_TEST_JOBS=${VOS_TEST_JOBS:-$VOS_CPUS}

# ---------------------------------------------------------------------------
# Compiler cache
# ---------------------------------------------------------------------------
# Opt-in and absent by default: this array stays empty unless ccache is
# actually installed, so sourcing this file changes nothing until you run
# `sudo apt install ccache` inside the distribution.
#
# The win it buys is specific. 366 of the 367 TUs are third-party and do not
# change across a deletion batch, yet the canonical and FAST build trees each
# compile all of them from scratch, and so does any fresh build directory. A
# shared cache makes the second tree's 366 free. The generated TU also hits
# whenever a batch is reverted or re-run unchanged.
#
# Deliberately no CCACHE_SLOPPINESS. The loose settings (include_file_mtime and
# friends) trade a correctness margin for hit rate, and a false hit in a build
# whose output is a verification oracle is not a trade this project should take.
# ccache hashes the preprocessed source, so the default configuration is sound.
#
# NOTE: adding the launcher to an already-configured tree changes every compile
# command, so the first build after you enable it recompiles everything once
# and populates the cache. The saving starts with the build after that.
if command -v ccache >/dev/null 2>&1; then
  export CCACHE_DIR=${CCACHE_DIR:-/root/.ccache}
  export CCACHE_MAXSIZE=${CCACHE_MAXSIZE:-25G}
  VOS_CMAKE_CCACHE=(
    -DCMAKE_C_COMPILER_LAUNCHER=ccache
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
  )
else
  VOS_CMAKE_CCACHE=()
fi

# ---------------------------------------------------------------------------
# Stage timing
# ---------------------------------------------------------------------------
# Wrap a build stage so the log records what it cost. The breakdown of a full
# build is currently known only for its two serial stages; every future tuning
# decision wants the rest, and the cheapest way to get it is to have each green
# build write it down. Emits one line to stderr, which the callers already fold
# into their log, and propagates the wrapped command's exit status unchanged.
#
#   vos_stage emit cmake --build "$BLD" --target generated_sail_riscv_model
#
# yields: STAGE emit wall=107.4s cpu=99% maxrss=2411360kB
vos_stage() {
  local name=$1
  shift
  /usr/bin/time -f "STAGE $name wall=%es cpu=%P maxrss=%MkB" "$@"
}

# ---------------------------------------------------------------------------
# VM keepalive
# ---------------------------------------------------------------------------
# Why a process and not a setting. WSL2 starts its vmIdleTimeout only once
# every instance has stopped, and the default 60s is short enough that work
# left running between two `wsl -e` invocations loses the VM underneath it,
# taking the docker daemon and any container with it (the M1.5 finding). The
# switch that disables the timer, `[wsl2] vmIdleTimeout=-1`, exists in exactly
# one place, %USERPROFILE%\.wslconfig: global to every distribution, permanent
# until a human deletes it, and outside anything this repository should own. A
# detached bounded sleep buys the same effect from inside: while it lives the
# distribution has a running process, so no instance ever stops, so the timer
# never starts; when it expires the machine is back to stock with nothing left
# behind. It also covers the Docker lanes, which need the daemon's distribution
# alive rather than any build environment.
#
# Idempotent via the pidfile, so sourcing this prelude in every loop starts at
# most one. Set VOS_KEEPALIVE_HOURS=0 to opt out, or call vos_keepalive_stop to
# end one early.
VOS_KEEPALIVE_PIDFILE=${VOS_KEEPALIVE_PIDFILE:-/tmp/vos-keepalive.pid}

vos_keepalive() {
  local hours=${1:-${VOS_KEEPALIVE_HOURS:-8}}
  [ "$hours" -gt 0 ] 2>/dev/null || return 0
  if [ -r "$VOS_KEEPALIVE_PIDFILE" ] &&
     kill -0 "$(cat "$VOS_KEEPALIVE_PIDFILE" 2>/dev/null)" 2>/dev/null; then
    return 0
  fi
  nohup sleep $(( hours * 3600 )) >/dev/null 2>&1 &
  echo $! > "$VOS_KEEPALIVE_PIDFILE"
  echo "KEEPALIVE pid=$! hours=$hours pidfile=$VOS_KEEPALIVE_PIDFILE" >&2
}

vos_keepalive_stop() {
  [ -r "$VOS_KEEPALIVE_PIDFILE" ] || return 0
  kill "$(cat "$VOS_KEEPALIVE_PIDFILE" 2>/dev/null)" 2>/dev/null
  rm -f "$VOS_KEEPALIVE_PIDFILE"
}

vos_keepalive

# ---------------------------------------------------------------------------
# What the numbers say (measured 2026-08-18, 12-core Snapdragon X Elite,
# 31.6 GB host, WSL2 default allocation of 12 CPUs and 15.7 GB)
# ---------------------------------------------------------------------------
# Cores are already fully exposed; the guest sees all 12. Raising the CPU count
# is therefore not available, and would not help if it were, because the build's
# critical path is two strictly single-threaded stages back to back: the Sail
# C++ emission (107s warm) followed by the one generated TU it produces
# (sail_riscv_model.cpp, 13.3 MB, 423,101 lines, 150s wall and 136s CPU at
# -O2 -g when compiled alone). That is a ~4.3 min floor no amount of
# parallelism reduces. The 314s previously recorded for that TU was measured
# under 14-way contention, not in isolation.
#
# Memory is not binding either. The heaviest single compile peaks at 1.43 GB
# against 15.7 GB available, so the VM has roughly an order of magnitude of
# headroom on its worst step and a larger .wslconfig allocation would buy
# nothing. The one figure still unmeasured is the Sail emission's own peak RSS,
# which vos_stage will capture on the next green full build.
#
# The source tree's residence on /mnt/c was tested and rejected as a suspect:
# it is 1.3 MB across 114 files, and reading it over 9p costs ~0.4s warm versus
# an ext4 copy. The build tree already lives on ext4 under /root/build.
