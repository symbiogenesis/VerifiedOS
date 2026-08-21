# SPDX-License-Identifier: Apache-2.0
"""The build environment every model loop needs, read rather than assumed.

This module tunes the *build*, never the VM. Nothing here writes `%USERPROFILE%\\.wslconfig`,
which is the only place WSL2's CPU and RAM allocation can be set and which applies to
every distribution at once. The measurements below say that file would not help anyway.
The single thing here that outlives a build is the keepalive, and it is a bounded
background process rather than a line in that global file for exactly the same reason:
it buys the effect this repository needs, scoped to the work, and expires on its own.

Four invariants every loop needs, and used to carry its own copy of:

  1. Sail's C++ emission overflows the default 8 MB stack on the full model (the M0.3
     finding, twice reproduced). The limit is raised here, in the parent, and every
     child inherits it.
  2. The Sail toolchain lives in the opam `default` switch, which a bare
     `wsl -e python3 tools/model.py` does not put on PATH.
  3. The Z3 that discharges Sail's typechecking obligations is the pinned one, not the
     distribution's. This is the one invariant whose absence is silent rather than
     loud, which is why it is announced: see `_prepend_z3_path`.
  4. Where the repository and the build trees are. Both are derived from this file's
     own location, which is the one thing a module always knows, so a checkout
     anywhere else, or by anyone else, builds the tree it is actually in.

What the numbers say (measured 2026-08-18, 12-core Snapdragon X Elite, 31.6 GB host,
WSL2 default allocation of 12 CPUs and 15.7 GB). Cores are already fully exposed; the
guest sees all 12. Raising the CPU count is therefore not available, and would not help
if it were, because the build's critical path is two strictly single-threaded stages
back to back: the Sail C++ emission (107 s warm) followed by the one generated
translation unit it produces (13.3 MB, 423,101 lines, 150 s wall and 136 s CPU at -O2
-g when compiled alone). That is a ~4.3 min floor no amount of parallelism reduces.
Memory is not binding either: the heaviest single compile peaks at 1.43 GB against
15.7 GB available. The source tree's residence on /mnt/c was tested and rejected as a
suspect: it is 1.3 MB across 114 files, and reading it over 9p costs ~0.4 s warm versus
an ext4 copy. The build tree already lives on ext4 under /root/build.
"""

import contextlib
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# The OCaml native stack Sail's emission needs, in bytes (the shell loops spelled it
# `ulimit -s 131072`, which is the same number in kilobytes).
STACK_BYTES = 131072 * 1024

# `/tmp` and not a private directory, deliberately: the lease is one per distribution
# rather than one per user, and a second tool has to find the first one's pidfile to
# know a lease is already held. Overridable for a test that must not touch the real one.
KEEPALIVE_PIDFILE = Path(
    os.environ.get("VOS_KEEPALIVE_PIDFILE", "/tmp/vos-keepalive.pid"))  # noqa: S108
KEEPALIVE_HOURS = int(os.environ.get("VOS_KEEPALIVE_HOURS", "8"))

# The M0.4 oracle's build tree, carrying the upstream pin in its name. Both the tree and
# the simulator inside it derive from this, so the pin is written once.
ORACLE_TREE = "sail-cheri-riscv-bb07488d"

# The prover, in a switch of its own and carrying its pin in the name for the same reason
# ORACLE_TREE does. It cannot share the Sail switch: `rocq-core` caps dune below the
# version the Sail packages are built against, so installing it into `default` wants dune
# downgraded from 3.24.2 to 3.23.1 and all twenty-seven of them rebuilt.
#
# 9.1.1 rather than the newer 9.2.0 because every consumer of a Rocq artifact here
# converges on 9.1: CertiRocq constrains `rocq >= 9.1 & < 9.2~`, SECOMP states 9.1, and
# sail-riscv's own Rocq lane pins `rocq_core_version` 9.1.1. One prover version serves the
# host gate and the M1.5 container both.
ROCQ_SWITCH = "rocq-9.1.1"

# The Z3 the Sail typechecker calls, unpacked beside the build trees and named for its
# version. Ubuntu 26.04 packages 4.13.3 and Sail invokes `z3` by name from PATH, so this
# directory has to precede /usr/bin or the distribution's answers are the ones cached.
Z3_BIN = Path(os.environ.get("VOS_Z3_BIN", "/root/z3-5.1.0/bin"))


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ[name]) if os.environ.get(name) else default


@dataclass
class Environment:
    """Where everything is, how much of the machine there is, and how much to use."""

    root: Path
    model: Path
    build_root: Path
    log_dir: Path
    cpus: int
    mem_available_mb: int
    jobs: int
    test_jobs: int
    ccache: list[str] = field(default_factory=list)

    @property
    def build_dir(self) -> Path:
        """The canonical build tree. Three loops named it and each spelled the path out,
        which is one fact in three places; it is spelled here."""
        return _env_path("VOS_BUILD_DIR", self.build_root / "verifiedos-model")

    @property
    def fast_build_dir(self) -> Path:
        return self.build_root / "verifiedos-model-fast"

    @property
    def typecheck_cache(self) -> Path:
        return self.build_root / "verifiedos-typecheck-smt-cache"

    @property
    def simulator(self) -> Path:
        return self.build_dir / "c_emulator" / "sail_riscv_sim"

    @property
    def oracle_root(self) -> Path:
        """The tree the M0.4 oracle is built in. Named separately from the binary
        because `VOS_ORACLE` may point at a simulator built anywhere, and the tree it
        came from is then no longer derivable from it."""
        return _env_path("VOS_ORACLE_ROOT", self.build_root / ORACLE_TREE)

    @property
    def oracle(self) -> Path:
        """The M0.4 differential reference: upstream sail-cheri-riscv at the pinned
        commit, which implements the same ISAv9 capability format the transplant
        carries. It is evidence, never authority."""
        return _env_path("VOS_ORACLE",
                         self.oracle_root / "c_emulator" / "cheri_riscv_sim_RV64")


def _cpus() -> int:
    """The cores this process may actually run on, which is what a job count wants.
    `os.process_cpu_count` honours the affinity mask on every platform that has one, so
    the guest's twelve stay twelve and a pinned run sees only what it was given."""
    return os.process_cpu_count() or 1


def _mem_available_mb() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


def _jobs(cpus: int, mem_mb: int) -> int:
    """CPUs+2 is Ninja's own default and the right shape for this tree: 366 of the 367
    translation units are small and oversubscribing by two keeps cores busy across
    process startup.

    The memory guard does not bind on a default-sized VM and exists so that it would
    bind on a shrunken one. Sized from measurement rather than a rule of thumb: the
    generated model unit peaks at 1.43 GB and is the only large one, so reserve 2 GB for
    it outright and budget a slim 512 MB for each other concurrent job. At 15.7 GB
    available this yields 24 and the guard is inert; under a 4 GB cap it yields 4 and
    prevents the thrash.
    """
    if os.environ.get("VOS_JOBS"):
        return int(os.environ["VOS_JOBS"])
    jobs = cpus + 2
    if mem_mb > 2048:
        jobs = min(jobs, max(1, (mem_mb - 2048) // 512))
    return jobs


def _ccache_args() -> list[str]:
    """Opt-in and absent by default: this stays empty unless ccache is installed, so
    loading this module changes nothing until `apt install ccache` is run.

    The win it buys is specific. 366 of the 367 units are third-party and do not change
    across a deletion batch, yet the canonical and fast build trees each compile all of
    them from scratch, and so does any fresh build directory. A shared cache makes the
    second tree's 366 free.

    Deliberately no CCACHE_SLOPPINESS. The loose settings trade a correctness margin for
    hit rate, and a false hit in a build whose output is a verification oracle is not a
    trade this project should take. ccache hashes the preprocessed source, so the
    default configuration is sound.
    """
    if not shutil.which("ccache"):
        return []
    os.environ.setdefault("CCACHE_DIR", "/root/.ccache")
    os.environ.setdefault("CCACHE_MAXSIZE", "25G")
    return ["-DCMAKE_C_COMPILER_LAUNCHER=ccache", "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache"]


def _raise_stack_limit() -> None:
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    want = STACK_BYTES if hard == resource.RLIM_INFINITY else min(STACK_BYTES, hard)
    if soft == resource.RLIM_INFINITY or soft >= want:
        return
    resource.setrlimit(resource.RLIMIT_STACK, (want, hard))


def _prepend_z3_path() -> None:
    """Put the pinned solver ahead of the distribution's.

    Absence is announced rather than passed over, which is what separates this from the
    opam guard below. A missing opam switch makes a Sail loop fail at `sail --version`;
    a missing Z3 prefix makes nothing fail at all. It makes the loop typecheck against
    Ubuntu's 4.13.3 and write that solver's answers into a content-keyed cache the
    pinned solver then reads back as its own, which is a difference no later run can see.
    """
    if Z3_BIN.is_dir():
        os.environ["PATH"] = f"{Z3_BIN}{os.pathsep}{os.environ.get('PATH', '')}"
    else:
        print(f"WARNING {Z3_BIN} is absent: typechecking will use the z3 on PATH and "
              f"cache its answers", file=sys.stderr)


def _opam_root() -> Path:
    return _env_path("OPAMROOT", Path.home() / ".opam")


def rocq_command() -> list[str]:
    """The prover as an argument list, for the proof gate rather than for a model loop.

    Both halves are resolved here rather than assumed by the caller. Rocq 9 ships no
    `coqc` at any version, its switch holding `rocq`, `rocq.byte`, and `rocqchk` and
    nothing else, so compilation is spelled `rocq c`; and ROCQ_SWITCH is not the switch
    `_apply_opam_env` puts on PATH, so a bare `rocq` finds nothing.
    """
    override = os.environ.get("VOS_ROCQ")
    if override:
        return [override, "c"]
    pinned = _opam_root() / ROCQ_SWITCH / "bin" / "rocq"
    if pinned.is_file():
        return [str(pinned), "c"]
    found = shutil.which("rocq")
    if found:
        return [found, "c"]
    raise SystemExit(f"no prover: neither $VOS_ROCQ, nor {pinned}, nor rocq on PATH. "
                     f"opam switch create {ROCQ_SWITCH} ocaml-base-compiler.5.4.0 "
                     f"--no-switch && opam install --switch={ROCQ_SWITCH} rocq-core.9.1.1")


def _apply_opam_env() -> None:
    """Guarded, because the container lanes load this module too and have no opam.
    Nothing is masked by the guard: a Sail loop without the switch fails loudly at
    `sail --version`."""
    if not shutil.which("opam"):
        return
    proc = subprocess.run(["opam", "env", "--switch=default", "--shell=sh"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return
    for name, value in re.findall(r"^(\w+)='(.*)';\s*export", proc.stdout, re.MULTILINE):
        os.environ[name] = value.replace("'\\''", "'")


def load() -> Environment:
    """Prepare this process, and describe the machine it is preparing it on."""
    if sys.platform == "win32":
        raise SystemExit("the model loops run inside WSL: "
                         "wsl -u root -e python3 tools/model.py <command>")

    _raise_stack_limit()
    _apply_opam_env()
    _prepend_z3_path()

    tools = Path(__file__).resolve().parent.parent
    root = _env_path("VOS_ROOT", tools.parent)
    cpus = _cpus()
    mem = _mem_available_mb()

    # The build trees live on ext4 rather than under the source tree: /mnt/c is a 9p
    # mount and a build directory on it is slow enough to matter.
    return Environment(
        root=root,
        model=_env_path("VOS_MODEL", root / "model"),
        build_root=_env_path("VOS_BUILD_ROOT", Path("/root/build")),
        log_dir=_env_path("VOS_LOG_DIR", Path("/root/logs")),
        cpus=cpus,
        mem_available_mb=mem,
        jobs=_jobs(cpus, mem),
        # Each ctest case is one single-threaded process with a small footprint, so the
        # core count is the whole story and the memory guard does not apply.
        test_jobs=int(os.environ.get("VOS_TEST_JOBS", cpus)),
        ccache=_ccache_args(),
    )


@runtime_checkable
class Writable(Protocol):
    """Anything a stage can report onto. `hasattr(x, "write")` was the test before,
    and this is that test with a name: `isinstance` against a runtime-checkable
    protocol checks for the method exactly as the attribute lookup did, and the
    result is a value the caller can then actually write to."""

    # `-> object` rather than `-> int`, because the only thing done with a stream
    # here is hand it to `print(file=...)`, which asks for exactly this and never
    # looks at what `write` returned.
    def write(self, s: str, /) -> object: ...

    # required because the report is printed with `flush=True`: a stage line that sat
    # in a buffer would reach a killed build's log after the build, or not at all
    def flush(self) -> object: ...


def stage(name: str, argv: list[str], report_to: Writable | None = None,
          **kwargs: Any) -> int:
    """Run a build stage and record what it cost.

    The breakdown of a full build was known only for its two serial stages; every
    future tuning decision wants the rest, and the cheapest way to get it is to have
    each green build write it down. `os.wait4` reports the rusage of *this* child rather
    than the running maximum over every child so far, so a light stage after a heavy one
    reports its own peak and not the heavy one's.

        STAGE emit wall=107.4s cpu=99% maxrss=2411360kB
    """
    started = time.perf_counter()
    proc = subprocess.Popen(argv, **kwargs)
    _, status, usage = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(status)

    wall = time.perf_counter() - started
    cpu = (usage.ru_utime + usage.ru_stime) / wall * 100 if wall > 0 else 0
    print(f"STAGE {name} wall={wall:.1f}s cpu={cpu:.0f}% maxrss={usage.ru_maxrss}kB",
          file=_report_stream(report_to, kwargs.get("stderr")), flush=True)
    return proc.returncode


def _report_stream(report_to: Writable | None, child_stderr: object) -> Writable:
    """A stage reports beside its own output: where the child writes to a log, so does
    the line saying what the child cost.

    `child_stderr` is whatever was passed through to `Popen`, which may be a file, a
    pipe constant, or nothing at all, so it is `object` until the protocol test says
    otherwise."""
    for candidate in (report_to, child_stderr):
        if isinstance(candidate, Writable):
            return candidate
    # named rather than returned directly: `sys.stderr` is rebindable, so its inferred
    # type carries an `Any` arm, and the one place that is pinned down is here
    fallback: Writable = sys.stderr
    return fallback


def keepalive(hours: int | None = None) -> None:
    """Hold the distribution up for a bounded time, so a loop does not lose the VM.

    WSL2 starts its vmIdleTimeout only once every instance has stopped, and the default
    60 s is short enough that work left running between two `wsl -e` invocations loses
    the VM underneath it, taking the docker daemon and any container with it (the M1.5
    finding). The switch that disables the timer lives in exactly one place,
    `%USERPROFILE%\\.wslconfig`: global to every distribution, permanent until a human
    deletes it, and outside anything this repository should own. A detached bounded
    sleep buys the same effect from inside: while it lives the distribution has a
    running process, so no instance ever stops, so the timer never starts; when it
    expires the machine is back to stock with nothing left behind.

    Idempotent via the pidfile, so loading this in every loop starts at most one.
    """
    hours = KEEPALIVE_HOURS if hours is None else hours
    if hours <= 0:
        return
    if _keepalive_running():
        return
    proc = subprocess.Popen(["sleep", str(hours * 3600)], start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    KEEPALIVE_PIDFILE.write_text(f"{proc.pid}\n")
    print(f"KEEPALIVE pid={proc.pid} hours={hours} pidfile={KEEPALIVE_PIDFILE}",
          file=sys.stderr)


def _keepalive_running() -> bool:
    try:
        pid = int(KEEPALIVE_PIDFILE.read_text().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        # no pidfile, an unreadable one, or a process that has exited: all three mean
        # there is no lease, which is what the caller asked
        return False
    return True


def keepalive_stop() -> None:
    # Both errors mean the lease is already gone: no pidfile, an unreadable one, or a
    # process that has exited. The pidfile is removed either way, so suppressing is
    # the whole handling rather than a swallowed failure.
    with contextlib.suppress(OSError, ValueError):
        os.kill(int(KEEPALIVE_PIDFILE.read_text().strip()), 15)
    KEEPALIVE_PIDFILE.unlink(missing_ok=True)
