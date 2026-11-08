# SPDX-License-Identifier: Apache-2.0
"""Guest build environment, toolchain paths, lane build locks, stage timing, and WSL keepalive for Sail model loops.

Configures:
1. A 128 MiB native stack limit (`STACK_BYTES`) for Sail C++ emission.
2. The dedicated Sail opam switch (`SAIL_SWITCH`) and pinned Z3 solver (`Z3_PREFIX`)
   ahead of system `PATH`.
3. Per-worktree lane build and log paths on the native Linux filesystem (`BUILD_ROOT`,
   `LOG_ROOT`) and `flock`-based lane concurrency locks ([`build_lock`](#build_lock),
   [`hold_lock`](#hold_lock)).
4. Compiler (`clang`/`clang++`), `ccache`, and parallel job sizing ([`_jobs`](#_jobs)).

Proof-gate environment helpers live in [proofenv.py](proofenv.py) (and are re-exported
here) so editing model-build helpers does not perturb the proof gate's implementation
identity.
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
from typing import IO, Protocol, cast, runtime_checkable

from vos import proofenv

# 128 MiB stack limit (`ulimit -s 131072`) required by Sail C++ emission on the full model.
STACK_BYTES = 131072 * 1024

MODEL_TREE = "verifiedos-model"

# Re-export proof-environment symbols from `proofenv.py` (`proofenv.py` has no reverse
# dependency on `env.py`, preserving the proof gate's implementation hash).
BUILD_ROOT = proofenv.BUILD_ROOT
CROSS_OS_FILESYSTEMS = proofenv.CROSS_OS_FILESYSTEMS
VOLATILE_FILESYSTEMS = proofenv.VOLATILE_FILESYSTEMS
MOUNTINFO = proofenv.MOUNTINFO
OCAML_VERSION = proofenv.OCAML_VERSION
OPAM_LOCKS = proofenv.OPAM_LOCKS
ROCQ_VERSION = proofenv.ROCQ_VERSION
ROCQ_SWITCH = proofenv.ROCQ_SWITCH
ROCQ_INSTALL = proofenv.ROCQ_INSTALL
PROOF_COMPILE_WORKER_MIB = proofenv.PROOF_COMPILE_WORKER_MIB
PROOF_KERNEL_WORKER_MIB = proofenv.PROOF_KERNEL_WORKER_MIB
Workers = proofenv.Workers
install_line = proofenv.install_line
lane_of = proofenv.lane_of
proof_jobs = proofenv.proof_jobs
proof_workers = proofenv.proof_workers
worker_jobs = proofenv.worker_jobs
size_workers = proofenv.size_workers
build_root = proofenv.build_root
lane_dir = proofenv.lane_dir
lane_root = proofenv.lane_root
mount_type = proofenv.mount_type
filesystem = proofenv.filesystem
opam_root = proofenv.opam_root
rocq_command = proofenv.rocq_command
rocqchk_command = proofenv.rocqchk_command
git_dir = proofenv.git_dir
git_overlay = proofenv.git_overlay
git_env = proofenv.git_env
_env_path = proofenv._env_path
_cpus = proofenv._cpus
_read_mem_available_mb = proofenv._read_mem_available_mb

# Sail SMT memo cache filename within each lane's build root.
TYPECHECK_CACHE = "verifiedos-typecheck-smt-cache"

# Persistent log directory on the guest ext4 root (survives WSL idle restarts unlike `/tmp`).
LOG_ROOT = Path("/root/logs")

PROFILE_CONFIG = "config/verifiedos.json"
BUILD_LOCK_HELD = "VOS_BUILD_LOCK_HELD"
ORACLE_TREE = "sail-cheri-riscv-cf36cfd4"

OCAMLFIND_VERSION = "1.9.8"
SAIL_VERSION = "0.20.3"
SAIL_SWITCH = f"verifiedos-sail-{SAIL_VERSION}-ocaml-{OCAML_VERSION}"
SAIL_INSTALL: tuple[tuple[str, ...], ...] = (
    ("opam", "switch", "create", SAIL_SWITCH, "--empty", "--no-switch", "-y"),
    ("opam", "switch", "import", str(OPAM_LOCKS / "sail.lock"),
     f"--switch={SAIL_SWITCH}", "-y"),
)

Z3_VERSION = "5.3.3"
Z3_PREFIX = Path(f"/root/z3-{Z3_VERSION}")
Z3_DISTRIBUTION = "4.13.3"
Z3_REQUIREMENTS = Path(__file__).resolve().parents[1] / "z3-requirements.txt"


def z3_install(target: Path, python: str = sys.executable) -> tuple[tuple[str, ...], ...]:
    """Return the hash-verified `--no-build` `uv pip install` command for the pinned Z3 wheel."""
    return (("uv", "pip", "install", "--no-build", "--require-hashes", "--python", python,
             "--target", str(target), "-r", str(Z3_REQUIREMENTS)),)


Z3_INSTALL = z3_install(Z3_PREFIX)


@dataclass
class Environment:
    """Paths, hardware resources, and build concurrency settings for a Sail model lane."""

    root: Path
    model: Path
    build_root: Path
    log_root: Path
    lane: str
    cpus: int
    mem_available_mb: int
    jobs: int
    test_jobs: int
    compilers: list[str] = field(default_factory=list)
    ccache: list[str] = field(default_factory=list)
    model_offline: bool = False

    @property
    def lane_root(self) -> Path:
        """Build directory root for this checkout's lane (`build_root` on primary, `build_root/lanes/<lane>` on linked worktrees)."""
        return lane_dir(self.build_root, self.lane)

    @property
    def primary_build_dir(self) -> Path:
        """Primary worktree's canonical model build directory (`build_root / MODEL_TREE`)."""
        return self.build_root / MODEL_TREE

    @property
    def build_dir(self) -> Path:
        """This lane's canonical model build directory (`VOS_BUILD_DIR` or `lane_root / MODEL_TREE`)."""
        return _env_path("VOS_BUILD_DIR", self.lane_root / MODEL_TREE)

    @property
    def fast_build_dir(self) -> Path:
        return self.lane_root / f"{MODEL_TREE}-fast"

    @property
    def typecheck_cache(self) -> Path:
        """Per-lane Sail SMT memo cache path (`lane_root / TYPECHECK_CACHE`)."""
        return self.lane_root / TYPECHECK_CACHE

    @property
    def primary_typecheck_cache(self) -> Path:
        """Primary worktree's Sail SMT memo cache path (`build_root / TYPECHECK_CACHE`)."""
        return self.build_root / TYPECHECK_CACHE

    @property
    def build_budget_mb(self) -> int:
        """Memory budget in MiB for a model build running `self.jobs` parallel jobs."""
        return GENERATED_UNIT_MB + JOB_MB * self.jobs

    @property
    def simulator(self) -> Path:
        return self.build_dir / "c_emulator" / "sail_riscv_sim"

    @property
    def profile(self) -> Path:
        """Frozen profile configuration (`model/config/verifiedos.json`)."""
        return self.model / PROFILE_CONFIG

    @property
    def log_dir(self) -> Path:
        return self.log_root

    def log(self, name: str) -> Path:
        """Return the lane-scoped log file path (`<name>.log` on primary, `<name>-<lane>.log` in a worktree)."""
        return self.log_root / (f"{name}.log" if not self.lane else f"{name}-{self.lane}.log")

    @property
    def oracle_root(self) -> Path:
        """Shared build directory for the pinned `sail-cheri-riscv` differential oracle (`VOS_ORACLE_ROOT` or `oracle_tree(build_root)`)."""
        return _env_path("VOS_ORACLE_ROOT", oracle_tree(self.build_root))

    @property
    def oracle(self) -> Path:
        """Path to the built `cheri_riscv_sim_RV64` differential oracle binary."""
        return _env_path("VOS_ORACLE",
                         self.oracle_root / "c_emulator" / "cheri_riscv_sim_RV64")


def _mem_available_mb() -> int:
    available = _read_mem_available_mb()
    if available is not None:
        return available
    print("WARNING no MemAvailable figure from /proc/meminfo: the memory guard is "
          "blind and jobs are sized from cores alone", file=sys.stderr)
    return 0


GENERATED_UNIT_MB = 2048
JOB_MB = 512


def _jobs(cpus: int, mem_mb: int) -> int:
    """Compute Ninja job count (`VOS_JOBS` override, or `cpus + 2` bounded by `mem_mb`)."""
    raw = os.environ.get("VOS_JOBS")
    if bool(raw):
        try:
            jobs = int(raw)
        except ValueError:
            jobs = 0
        if jobs < 1:
            raise SystemExit(f"VOS_JOBS={raw!r} is not a positive count of jobs")
        return jobs
    jobs = cpus + 2
    if mem_mb > 0:
        jobs = min(jobs, max(1, (mem_mb - GENERATED_UNIT_MB) // JOB_MB))
    return jobs


def _ccache_args() -> list[str]:
    """Return CMake compiler-launcher flags when `ccache` is installed on `PATH`."""
    if not bool(shutil.which("ccache")):
        return []
    os.environ.setdefault("CCACHE_DIR", "/root/.ccache")
    os.environ.setdefault("CCACHE_MAXSIZE", "25G")
    return ["-DCMAKE_C_COMPILER_LAUNCHER=ccache", "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache"]


def _compiler_args() -> list[str]:
    """Return CMake flags selecting `clang`/`clang++` when available on `PATH`."""
    if bool(shutil.which("clang")) and bool(shutil.which("clang++")):
        return ["-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++"]
    return []


def _raise_stack_limit() -> None:
    if sys.platform == "win32":
        raise RuntimeError("the stack limit is raised in the guest")
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    want = STACK_BYTES if hard == resource.RLIM_INFINITY else min(STACK_BYTES, hard)
    if soft == resource.RLIM_INFINITY or soft >= want:
        return
    resource.setrlimit(resource.RLIMIT_STACK, (want, hard))


def _prepend_z3_path() -> None:
    """Prepend `VOS_Z3_BIN` (default `Z3_PREFIX / "bin"`) to `PATH`, warning if absent."""
    z3_bin = _env_path("VOS_Z3_BIN", Z3_PREFIX / "bin")
    if z3_bin.is_dir():
        prefix = str(z3_bin)
        entries = [entry for entry in os.environ.get("PATH", "").split(os.pathsep)
                   if entry != prefix]
        os.environ["PATH"] = os.pathsep.join([prefix, *entries])
    else:
        print(f"WARNING {z3_bin} is absent: typechecking will use the z3 on PATH and "
              f"cache its answers", file=sys.stderr)


def log_root() -> Path:
    """Return the log directory (`VOS_LOG_DIR` or `LOG_ROOT`)."""
    return _env_path("VOS_LOG_DIR", LOG_ROOT)


def oracle_tree(root: Path) -> Path:
    """Return the shared `sail-cheri-riscv` oracle build path under `root`, scoped by `SAIL_VERSION`."""
    return root / f"sail-{SAIL_VERSION}" / ORACLE_TREE


OPAM_ANSWERS: tuple[str, ...] = ("OPAMYES", "OPAMCONFIRMLEVEL")


def declining_environment() -> dict[str, str]:
    """Return `os.environ` without `OPAMYES`/`OPAMCONFIRMLEVEL` so read-only `opam` calls never auto-confirm root upgrades."""
    return {key: value for key, value in os.environ.items()
            if key.upper() not in OPAM_ANSWERS}


def _apply_opam_env() -> None:
    """Export `opam env --switch=SAIL_SWITCH` into `os.environ` when `opam` is installed."""
    if not bool(shutil.which("opam")):
        return
    proc = subprocess.run(["opam", "env", f"--switch={SAIL_SWITCH}", "--shell=sh"],
                          capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL, env=declining_environment())
    if proc.returncode != 0:
        return
    for name, value in re.findall(r"^(\w+)='(.*)';\s*export", proc.stdout, re.MULTILINE):
        os.environ[name] = value.replace("'\\''", "'")


def model_offline() -> bool:
    """Select acquisition without network; malformed policy never enables fetching."""
    value = os.environ.get("VOS_MODEL_OFFLINE", "0")
    if value not in {"0", "1"}:
        raise ValueError("VOS_MODEL_OFFLINE must be 0 or 1")
    return value == "1"


def load(*, toolchain: bool = True) -> Environment:
    """Load the model [`Environment`](#Environment), preparing the guest toolchain (`stack`, `opam`, `z3`) when `toolchain=True`."""
    if sys.platform == "win32" and toolchain:
        raise SystemExit("the model loops run inside WSL: "
                         "python tools/run.py model <command>")
    if sys.platform == "win32":
        tools = Path(__file__).resolve().parent.parent
        root = _env_path("VOS_ROOT", tools.parent)
        return Environment(
            root=root,
            model=_env_path("VOS_MODEL", root / "model"),
            build_root=build_root(),
            log_root=log_root(),
            lane=lane_of(root),
            cpus=_cpus(),
            mem_available_mb=0,
            jobs=1,
            test_jobs=1,
            model_offline=model_offline(),
        )

    if toolchain:
        _raise_stack_limit()
        _apply_opam_env()
        _prepend_z3_path()

    tools = Path(__file__).resolve().parent.parent
    root = _env_path("VOS_ROOT", tools.parent)
    cpus = _cpus()
    mem = _mem_available_mb()

    # The build trees and the logs live on the guest's own filesystem rather than under
    # the source tree: /mnt/c is a 9p mount, and a build directory on it is slow enough
    # to matter. `LOG_ROOT` says why the logs are under /root and never /tmp.
    return Environment(
        root=root,
        model=_env_path("VOS_MODEL", root / "model"),
        build_root=build_root(),
        log_root=log_root(),
        lane=lane_of(root),
        cpus=cpus,
        mem_available_mb=mem,
        jobs=_jobs(cpus, mem),
        # Each ctest case is one single-threaded process with a small footprint, so the
        # core count is the whole story and the memory guard does not apply.
        test_jobs=int(os.environ.get("VOS_TEST_JOBS", cpus)),
        compilers=_compiler_args(),
        ccache=_ccache_args(),
        model_offline=model_offline(),
    )


def _lock_path(build_dir: Path) -> Path:
    """Return the sibling lockfile path (`<build_dir>.lock`) outside `build_dir`."""
    return build_dir.parent / f"{build_dir.name}.lock"


def _flock(handle: IO[str], *, blocking: bool, shared: bool = False) -> bool:
    """Acquire an `flock` on `handle` (shared or exclusive), returning False if non-blocking and already held."""
    if sys.platform == "win32":
        raise RuntimeError("build locks are taken in the guest")
    import fcntl
    kind = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
    flags = kind if blocking else kind | fcntl.LOCK_NB
    try:
        fcntl.flock(handle.fileno(), flags)
    except OSError:
        return False
    return True


def _unlock(handle: IO[str]) -> None:
    if sys.platform == "win32":
        raise RuntimeError("build locks are released in the guest")
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _open_lock(build_dir: Path) -> IO[str]:
    path = _lock_path(build_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a+", encoding="utf-8")


def _try_lock(target: Path, *, reader: str = "") -> tuple[IO[str] | None, str]:
    """Try to acquire the lock beside `target`, returning `(handle, "")` on success or `(None, holder)` on contention."""
    handle = _open_lock(target)
    if _flock(handle, blocking=False, shared=bool(reader)):
        record_lock_holder(handle, os.getpid(), reader)
        return handle, ""
    handle.seek(0)
    holder = handle.read().strip() or "unknown"
    handle.close()
    return None, holder


def build_lock(build_dir: Path) -> IO[str] | None:
    """Acquire an exclusive `flock` on `build_dir` for this process, or exit naming the current holder (`None` if `BUILD_LOCK_HELD` is set)."""
    if bool(os.environ.get(BUILD_LOCK_HELD)):
        return None
    handle, holder = _try_lock(build_dir)
    if handle is None:
        raise SystemExit(f"a build already holds {build_dir} (pid {holder}); wait on it "
                         f"with `run.py model wait`, or build in a worktree of your own")
    return handle


def hold_lock(target: Path, what: str, *, shared: bool = False) -> IO[str]:
    """Acquire an exclusive or shared `flock` on `target`, or exit naming the current holder."""
    handle, holder = _try_lock(target, reader=(what or "a reader") if shared else "")
    if handle is not None:
        return handle
    pid, _, reader = holder.splitlines()[-1].partition(" ")
    if shared:
        raise SystemExit(f"{what} cannot read {target} while a run that can replace it "
                         f"holds it (pid {pid}); wait for it to finish")
    if reader:
        raise SystemExit(f"{what} cannot hold {target} while {reader} reads it "
                         f"(pid {pid}); wait for it to finish")
    raise SystemExit(f"{what} already holds {target} (pid {holder}); "
                     f"wait for it to finish")


def record_lock_holder(handle: IO[str], pid: int, reader: str = "") -> None:
    """Write `pid` (and optional `reader` label) into the open lockfile `handle`."""
    handle.seek(0)
    handle.truncate()
    handle.write(f"{pid} {reader}\n" if reader else f"{pid}\n")
    handle.flush()


def build_holder(build_dir: Path) -> str | None:
    """Return the holder string of `build_dir`'s lock if currently held, or `None`."""
    if not _lock_path(build_dir).exists():
        return None
    with _open_lock(build_dir) as handle:
        if _flock(handle, blocking=False):
            _unlock(handle)
            return None
        handle.seek(0)
        return handle.read().strip() or "unknown"


def wait_for_build(build_dir: Path) -> IO[str] | None:
    """Block until `build_dir`'s lock is free and return the locked handle (or `None` if no lockfile exists)."""
    if not _lock_path(build_dir).exists():
        return None
    handle = _open_lock(build_dir)
    _flock(handle, blocking=True)
    return handle


@runtime_checkable
class Writable(Protocol):
    """Stream protocol supporting `write` and `flush` for stage timing output."""

    def write(self, s: str, /) -> object: ...
    def flush(self) -> object: ...


def stage(name: str, argv: list[str], report_to: Writable | None = None, *,
          cwd: Path | None = None, stdout: IO[str] | None = None,
          stderr: IO[str] | None = None, add_env: dict[str, str] | None = None) -> int:
    """Run `argv` as a build stage, print its wall/CPU/maxrss usage line via `os.wait4`, and return its exit code."""
    if sys.platform == "win32":
        raise RuntimeError("build stages run in the guest")
    started = time.perf_counter()
    proc = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr,
                            env=None if add_env is None else {**os.environ, **add_env})
    _, status, usage = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(status)

    print(stage_line(name, time.perf_counter() - started, usage.ru_utime + usage.ru_stime,
                     usage.ru_maxrss),
          file=_report_stream(report_to, stderr), flush=True)
    return proc.returncode


def stage_line(name: str, wall: float, cpu_seconds: float, maxrss_kb: int, *,
               start: float | None = None) -> str:
    """Format a `STAGE <name> ...` resource usage line."""
    cpu = cpu_seconds / wall * 100 if wall > 0 else 0
    began = "" if start is None else f" start=+{start:.1f}s"
    return f"STAGE {name}{began} wall={wall:.1f}s cpu={cpu:.0f}% maxrss={maxrss_kb}kB"


def _report_stream(report_to: Writable | None, child_stderr: object) -> Writable:
    """Return the first `Writable` stream among `report_to`, `child_stderr`, or `sys.stderr`."""
    for candidate in (report_to, child_stderr):
        if isinstance(candidate, Writable):
            return candidate
    return cast("Writable", sys.stderr)


def _keepalive_pidfile() -> Path:
    """Return the WSL keepalive pidfile path (`VOS_KEEPALIVE_PIDFILE` or `/tmp/vos-keepalive.pid`)."""
    return _env_path("VOS_KEEPALIVE_PIDFILE", Path("/tmp/vos-keepalive.pid"))  # noqa: S108


def keepalive_hours() -> int:
    """Return the WSL keepalive duration in hours (`VOS_KEEPALIVE_HOURS`, default `8`; `<= 0` disables)."""
    raw = os.environ.get("VOS_KEEPALIVE_HOURS", "8")
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(
            f"VOS_KEEPALIVE_HOURS={raw!r} is not a whole number of hours") from None


def keepalive(hours: int | None = None) -> None:
    """Ensure a detached `sleep` process is running so WSL2 does not idle-terminate between commands."""
    hours = keepalive_hours() if hours is None else hours
    if hours <= 0:
        return
    if _lease_sleep() is not None:
        return
    pidfile = _keepalive_pidfile()
    proc = subprocess.Popen(["sleep", str(hours * 3600)], cwd=pidfile.parent, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    scratch = pidfile.with_name(f"{pidfile.name}.{os.getpid()}")
    scratch.write_text(f"{proc.pid}\n")
    scratch.replace(pidfile)
    print(f"KEEPALIVE pid={proc.pid} hours={hours} pidfile={pidfile}",
          file=sys.stderr)


def _lease_sleep() -> int | None:
    """Return the PID recorded in `_keepalive_pidfile()` if it is still a live `sleep` process, else `None`."""
    try:
        pid = int(_keepalive_pidfile().read_text().strip())
    except OSError, ValueError:
        return None
    try:
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return None
    return pid if argv[:1] == [b"sleep"] else None


def keepalive_stop() -> None:
    """Terminate the active keepalive `sleep` process (if any) and remove its pidfile."""
    pid = _lease_sleep()
    if pid is not None:
        with contextlib.suppress(OSError):
            os.kill(pid, 15)
    _keepalive_pidfile().unlink(missing_ok=True)
