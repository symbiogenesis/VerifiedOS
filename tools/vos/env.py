# SPDX-License-Identifier: Apache-2.0
"""The build environment every model loop needs, read rather than assumed.

This module tunes the *build*, never the VM. Nothing here writes `%USERPROFILE%\\.wslconfig`,
which is the only place WSL2's CPU and RAM allocation can be set and which applies to
every distribution at once. The measurements below say that file would not help anyway.
The single thing here that outlives a build is the keepalive, and it is a bounded
background process rather than a line in that global file for exactly the same reason:
it buys the effect this repository needs, scoped to the work, and expires on its own.

Five invariants every loop needs, and used to carry its own copy of:

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
  5. Which *lane* those trees belong to. One toolchain serves as many checkouts as
     there are worktrees, and everything downstream of a build reads the simulator
     back out of the build tree, so a tree two checkouts share is a checkout reading
     the other one's answers. `_lane` derives the lane from the checkout, and
     `build_lock` holds it for one build at a time.

What the numbers say (measured 2026-08-18, 12-core Snapdragon X Elite, 31.6 GB host,
WSL2 default allocation of 12 CPUs and 15.7 GB). Cores are already fully exposed; the
guest sees all 12. Raising the CPU count is therefore not available, and would not help
if it were, because the build's critical path is two strictly single-threaded stages
back to back: the Sail C++ emission followed by the one generated translation unit it
produces. Both figures move as the curation deletes surface, so both are dated. The
emission is 41.2 s at the C-class freeze against a warm memo cache, and 34.4 s
remeasured clean 2026-08-22 (I6's stock arm). The unit, remeasured
clean 2026-08-22 on a quiet toolchain at 10,835,851 bytes over 344,963 lines, compiles
alone at -O2 -g in 81.8 s wall and 71 s CPU with a 1.20 GB peak under gcc 15.2.0, and
in 38.7 s under clang 21.1.8 accepting the same command verbatim (I5's sweep); the
139.1 s this docstring carried before was taken with a sibling lane building, so
roughly 40% of it was contention rather than compiler. Against the 13.3 MB,
423,101-line, 150 s unit recorded at M0.3 the direction is what matters: the floor is
roughly 2 min and it is falling, and no amount of parallelism reduces it. Memory is
not binding: the heaviest single compile is that unit.

The source tree's residence on /mnt/c is a suspect for exactly one stage, and the
rejection that stood here measured a stage that is not it. Reading the 1.19 MB of Sail
sources across 125 files does cost only ~0.4 s over 9p; `configure` walks the whole
824-file cmake project and pays per stat rather than per byte. Measured 2026-08-22 on a
quiet toolchain with the arms alternated, a re-configure costs 17.0/17.4/20.4 s at
10-12% of a core from /mnt/c against 0.9/1.0/1.1 s at 47-48% from a byte-identical ext4
copy, and a fresh one, downloads already in the tree, 26.7/29.5/34.9 s against
11.3/7.3/7.6 s. CPU is 1.7-2.4 s against 0.4-0.5 s, so most of the gap is wait and the
rest is 9p syscall overhead, and the arms do not overlap at any repeat. That is about
17 s of every build, and it is still not a reason to move: the host lane pays the same
tax in reverse, `tools/check.py` costing 1.0/1.1/1.6 s over the NTFS checkout against
11.4/13.5/18.5 s over the same tree on the wsl.localhost share, on the loop that runs
after every document edit rather than once per build. The build tree already lives on
ext4 under /root/build.
"""

import contextlib
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import IO, Protocol, runtime_checkable

# The OCaml native stack Sail's emission needs, in bytes (the shell loops spelled it
# `ulimit -s 131072`, which is the same number in kilobytes).
STACK_BYTES = 131072 * 1024

# The canonical build tree's name, written here because two things need it: the lane's
# own tree is named for it, and a new lane is seeded from the primary worktree's, which
# is that name under the build root rather than under a lane.
MODEL_TREE = "verifiedos-model"

# The frozen profile configuration, relative to the model tree. Every loop below a
# build hands it to the simulator, so `Environment.profile` composes the path once.
PROFILE_CONFIG = "config/verifiedos.json"

# Set by `model.py build --background` on the child it detaches, which inherits the
# lock the parent already took rather than taking a second one. Internal, and named
# rather than spelled at both ends.
BUILD_LOCK_HELD = "VOS_BUILD_LOCK_HELD"

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


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ[name]) if os.environ.get(name) else default


def _gitdir_pointer(root: Path) -> str | None:
    """The target a linked checkout's `.git` pointer file names, `None` where `.git`
    is a directory, absent, or unreadable. The raw spelling is returned rather than a
    parsed path, because the two readers want different halves of it: `_lane` the
    worktree's name, `git_dir` the administrative path."""
    dot_git = root / ".git"
    if not dot_git.is_file():
        return None
    try:
        pointer = dot_git.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not pointer.startswith("gitdir:"):
        return None
    return pointer.removeprefix("gitdir:").strip()


def _lane(root: Path) -> str:
    """Which build lane this checkout owns, empty for the primary worktree.

    Four things collide when two checkouts drive one toolchain: the build tree, the
    log, the SMT memo cache, and the simulator every later loop reads back out of the
    build tree. The first is loud, cmake refusing outright to point an existing cache
    at a second source directory; the fourth is silent, and is the one that matters,
    because `sweep`, `corpus`, `trace-diff`, `devicetree` and `reference` all read
    `build_dir/c_emulator/sail_riscv_sim` and none of them can tell whose model it was
    generated from. A lane per checkout is what makes those answers this checkout's.

    A linked worktree is recognized by `.git` being a *file* whose `gitdir:` names a
    directory under the primary checkout's `.git/worktrees/`, and the lane is the last
    component of it, which is git's own name for the worktree and unique within the
    repository by construction. A submodule's `.git` is a file too and points into
    `.git/modules/` instead, which is why the test names the parent component rather
    than merely the file type. An absent `.git`, an exported tree, and the container
    lanes all answer the primary, which is the state every path here already assumed.

    The pointer is written with forward slashes by git on Windows and read here on
    both lanes, so it is parsed as a pure posix path after the other separator is
    normalized out rather than as this platform's `Path`.
    """
    override = os.environ.get("VOS_LANE")
    if override is not None:
        return override.strip().lower()
    target = _gitdir_pointer(root)
    if target is None:
        return ""
    admin = PurePosixPath(target.replace("\\", "/"))
    return admin.name.lower() if admin.parent.name == "worktrees" else ""


@dataclass
class Environment:
    """Where everything is, how much of the machine there is, and how much to use."""

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

    @property
    def lane_root(self) -> Path:
        """Where this checkout's build trees live.

        The primary worktree keeps the paths it has always had and a linked one gets a
        directory of its own, so everything a lane knows sits under one path and a lane
        is retired by deleting it. The primary is deliberately not moved into a lane
        directory of its own: it is the tree that already exists, and renaming it would
        spend a cold rebuild on the day this landed to buy nothing but symmetry.
        """
        return self.build_root if not self.lane else self.build_root / f"lane-{self.lane}"

    @property
    def primary_build_dir(self) -> Path:
        """The primary worktree's canonical tree, which is where a lane standing up for
        the first time copies its warm state from. Equal to `build_dir` on the primary
        worktree, which is what makes a donor list that names both safe to write."""
        return self.build_root / MODEL_TREE

    @property
    def build_dir(self) -> Path:
        """The canonical build tree. Three loops named it and each spelled the path out,
        which is one fact in three places; it is spelled here."""
        return _env_path("VOS_BUILD_DIR", self.lane_root / MODEL_TREE)

    @property
    def fast_build_dir(self) -> Path:
        return self.lane_root / f"{MODEL_TREE}-fast"

    @property
    def typecheck_cache(self) -> Path:
        """Per lane, and not per machine, because Sail's memo cache is one file that
        every run rewrites whole: see `model.py`'s `_seed_smt_cache` for what two
        writers of it do to each other."""
        return self.lane_root / "verifiedos-typecheck-smt-cache"

    @property
    def simulator(self) -> Path:
        return self.build_dir / "c_emulator" / "sail_riscv_sim"

    @property
    def profile(self) -> Path:
        """The frozen profile configuration every loop hands to the simulator."""
        return self.model / PROFILE_CONFIG

    @property
    def log_dir(self) -> Path:
        """One directory for every lane's logs, because a human reading them wants them
        in one place; it is the file name that carries the lane. See `log`."""
        return self.log_root

    def log(self, name: str) -> Path:
        """Where a named loop's log goes in this lane.

        A build opens its log with `w`, so two lanes sharing one path means the second
        truncates the first's while the first is still writing into it, and a caller
        waiting on `ALL_DONE` reads the other lane's marker. The lane is in the file
        name rather than in a directory of its own so that the primary worktree's log
        keeps the path every earlier run wrote to.
        """
        return self.log_root / (f"{name}.log" if not self.lane else f"{name}-{self.lane}.log")

    @property
    def oracle_root(self) -> Path:
        """The tree the M0.4 oracle is built in. Named separately from the binary
        because `VOS_ORACLE` may point at a simulator built anywhere, and the tree it
        came from is then no longer derivable from it.

        Shared by every lane rather than one per lane, and it is the only build tree
        that is: the oracle is stock `sail-cheri-riscv` at a pinned commit, so every
        checkout of this repository would build the same bytes from it, and none of
        this repository's own curation reaches it.
        """
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
    # Announced rather than passed over: with no figure the memory guard in `_jobs`
    # cannot bind, and a silent zero would look like a policy instead of a blindness.
    print("WARNING no MemAvailable figure from /proc/meminfo: the memory guard is "
          "blind and jobs are sized from cores alone", file=sys.stderr)
    return 0


def _jobs(cpus: int, mem_mb: int) -> int:
    """CPUs+2 is Ninja's own default and the right shape for this tree: 366 of the 367
    translation units are small and oversubscribing by two keeps cores busy across
    process startup.

    The memory guard does not bind on a default-sized VM and exists so that it would
    bind on a shrunken one. Sized from measurement rather than a rule of thumb: the
    generated model unit is the only large one and its peak is a bit over 1 GB, which
    the module docstring measures and this reserve deliberately sits above, so reserve
    2 GB for it outright and budget a slim 512 MB for each other concurrent job. At
    15.7 GB available this yields 24 and the guard is inert; under a 4 GB cap it yields
    4 and prevents the thrash.
    """
    raw = os.environ.get("VOS_JOBS")
    if raw:
        # Garbage and non-positive counts alike are refused by name, because either
        # would otherwise go straight onto ninja's command line as `-j`.
        try:
            jobs = int(raw)
        except ValueError:
            jobs = 0
        if jobs < 1:
            raise SystemExit(f"VOS_JOBS={raw!r} is not a positive count of jobs")
        return jobs
    jobs = cpus + 2
    if mem_mb > 2048:
        jobs = min(jobs, max(1, (mem_mb - 2048) // 512))
    return jobs


def _ccache_args() -> list[str]:
    """Opt-in and absent by default: this stays empty unless ccache is installed, so
    loading this module changes nothing until `apt install ccache` is run.

    **What the shared cache buys, measured rather than assumed (I4).** ccache hashes the
    command line along with the source, so the six cases separate like this, each run
    against a private cache directory:

        the very same command again          HIT
        -g dropped (the --fast profile)      miss
        same flags, other -I directory       miss
        byte-identical source, other path    miss
        mtime touched, bytes unchanged       HIT

    Two of those decide the shape of the win. The last one is the one this cache is
    worth having for: an emission that reproduces the C++ it produced last time is a
    direct hit, so a regeneration costs a cache lookup instead of the compile. The two
    in the middle say what the cache does *not* reach: `CCACHE_DIR` is shared by every
    build tree, but the fast tree differs from the canonical one by `-g` and a second
    worktree differs by every `-I`, so neither shares a single entry with the other. At
    scale, a lane's first 367-unit build against a cache holding another lane's 939
    entries took 367 misses and no hits at all. The cache pays back within one tree and
    one build type, which is a narrower claim than the one this docstring used to make.

    `CCACHE_BASEDIR` is the lever that would make lanes share, and it is deliberately
    not pulled: it rewrites absolute paths before hashing, so the object a second lane
    gets back carries the first lane's directory in its debug info. That is not a wrong
    program but it is a wrong artifact, and the standard below applies to it.

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


def _compiler_args() -> list[str]:
    """Prefer clang for the model's C and C++ when the distribution carries one.

    Measured rather than assumed (I5, 2026-08-22): clang 21.1.8 compiles the generated
    unit in 38.7 s where gcc 15.2.0 takes 81.8 s from the same command verbatim, and
    that unit is the largest term of a real-edit build, so the preference buys about
    43 s per real regeneration. Found-or-absent like ccache above: a machine without
    clang builds under cmake's default compiler and nothing here pretends otherwise.

    cmake does not migrate a configured tree across a compiler change, so this flag
    decides only a tree configured fresh: an existing tree keeps the compiler it was
    born with until it is retired, which is a deletion, the lane idiom. The canonical
    and fast trees were retired and rebuilt at the flip (I10), with the canonical's
    memo cache saved aside and restored exactly as a lane seed would be.
    """
    if shutil.which("clang") and shutil.which("clang++"):
        return ["-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++"]
    return []


def _raise_stack_limit() -> None:
    # POSIX-only, and this module is read on the host as well as run in the guest.
    # Deferring the import is what keeps `import vos.env` from failing on Windows.
    import resource  # noqa: PLC0415
    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    want = STACK_BYTES if hard == resource.RLIM_INFINITY else min(STACK_BYTES, hard)
    if soft == resource.RLIM_INFINITY or soft >= want:
        return
    resource.setrlimit(resource.RLIMIT_STACK, (want, hard))


def _prepend_z3_path() -> None:
    """Put the pinned solver ahead of the distribution's.

    The Z3 the Sail typechecker calls is unpacked beside the build trees and named for
    its version. Ubuntu 26.04 packages 4.13.3 and Sail invokes `z3` by name from PATH,
    so the pinned directory has to precede /usr/bin or the distribution's answers are
    the ones cached. `VOS_Z3_BIN` is read here, at call time like every other override,
    so a test that sets it after importing this module is still honoured.

    Absence is announced rather than passed over, which is what separates this from the
    opam guard below. A missing opam switch makes a Sail loop fail at `sail --version`;
    a missing Z3 prefix makes nothing fail at all. It makes the loop typecheck against
    Ubuntu's 4.13.3 and write that solver's answers into a content-keyed cache the
    pinned solver then reads back as its own, which is a difference no later run can see.
    """
    z3_bin = _env_path("VOS_Z3_BIN", Path("/root/z3-5.1.0/bin"))
    if z3_bin.is_dir():
        os.environ["PATH"] = f"{z3_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    else:
        print(f"WARNING {z3_bin} is absent: typechecking will use the z3 on PATH and "
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
        # Logs under /root and never /tmp, which is the reverse of the keepalive pidfile
        # above and for the reason that decides both: WSL idle-terminates once the last
        # process exits, and Ubuntu clears /tmp on the restart. A lease that dies with
        # the distribution holding it is correct; the log of a fifteen-minute build,
        # started and left, has to be there when its caller comes back to read it.
        log_root=_env_path("VOS_LOG_DIR", Path("/root/logs")),
        lane=_lane(root),
        cpus=cpus,
        mem_available_mb=mem,
        jobs=_jobs(cpus, mem),
        # Each ctest case is one single-threaded process with a small footprint, so the
        # core count is the whole story and the memory guard does not apply.
        test_jobs=int(os.environ.get("VOS_TEST_JOBS", cpus)),
        compilers=_compiler_args(),
        ccache=_ccache_args(),
    )


def git_dir(root: Path) -> Path | None:
    """This checkout's git administrative directory, where a lane needs it translated
    before the guest can use it at all. `None` means there is nothing to translate.

    A linked worktree's `.git` is a file holding an absolute path to that directory, and
    one created by the *host's* git writes a Windows path into it. Inside the guest that
    path is not absolute, so git appends it to the worktree and looks for
    `/mnt/c/.../VerifiedOS-inst/C:/Users/.../worktrees/VerifiedOS-inst`, which is
    nowhere: every `git` run inside a lane fails with `not a git repository`, exit 128.

    What that costs is not cosmetic. cmake's `git describe` is one of those runs, so it
    fails at configure and the emulator stamps itself `unknown commit`, which is the
    exact state M0.10 exists to end and which building in a worktree silently restores.
    `model.py reference` is the gate that catches it, and in a lane it caught it.

    `wslpath` does the translation rather than a rule about `/mnt`, because the mount
    root is configurable and the tool that knows it ships with the guest. A pointer that
    is already usable, a primary worktree, and a lane with no `wslpath` to ask all
    answer `None`, which leaves the behaviour exactly as it was.
    """
    dot_git = root / ".git"
    if not dot_git.is_file():
        return None
    try:
        pointer = dot_git.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not pointer.startswith("gitdir:"):
        return None
    target = pointer.removeprefix("gitdir:").strip()
    if Path(target).is_dir():
        return None
    if not re.match(r"^[A-Za-z]:[/\\]", target):
        return None
    tool = shutil.which("wslpath")
    if tool is None:
        return None
    done = subprocess.run([tool, "-u", target], capture_output=True, text=True, check=False)
    translated = Path(done.stdout.strip())
    return translated if done.returncode == 0 and translated.is_dir() else None


def _lock_path(build_dir: Path) -> Path:
    """Beside the tree rather than inside it, because the lock has to exist before the
    first build creates the tree and has to survive the `rm -rf` that retires it."""
    return build_dir.parent / f"{build_dir.name}.lock"


def _flock(handle: IO[str], *, blocking: bool) -> bool:
    """Take an exclusive lock on an open file, or say that it is held.

    POSIX-only, and this module is read on the host as well as run in the guest, so
    the import is deferred for the reason `_raise_stack_limit`'s is. `flock` belongs to
    the open file description rather than to the process, which is what lets a detached
    build hold a lock its launcher took: see `build_lock`.
    """
    import fcntl  # noqa: PLC0415
    flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
    try:
        fcntl.flock(handle.fileno(), flags)
    except OSError:
        return False
    return True


def _unlock(handle: IO[str]) -> None:
    import fcntl  # noqa: PLC0415
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _open_lock(build_dir: Path) -> IO[str]:
    path = _lock_path(build_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a+", encoding="utf-8")


def _try_lock(target: Path) -> tuple[IO[str] | None, str]:
    """Take the lock beside `target`, or name who holds it.

    Exactly one half of the pair is meaningful: the open locked handle with this
    process recorded as holder, or, when the handle is `None`, the pid the holding
    run recorded in the lock file.
    """
    handle = _open_lock(target)
    if _flock(handle, blocking=False):
        record_lock_holder(handle, os.getpid())
        return handle, ""
    handle.seek(0)
    holder = handle.read().strip() or "unknown"
    handle.close()
    return None, holder


def build_lock(build_dir: Path) -> IO[str] | None:
    """Hold one lane's build tree for the life of this process, or refuse.

    Two builds in one tree is not slow, it is wrong: ninja writes one set of objects
    and cmake one cache, so the loser's emission lands in the winner's tree and the
    simulator that comes out belongs to neither run. The lock is what makes the plan's
    `Parallel` mark mean a lane rather than merely a second terminal.

    `flock` is used rather than a pidfile because it is released by the kernel when the
    holder's last descriptor closes: a build killed mid-run leaves no lock to break,
    and there is no liveness test to get wrong. The pid is written into the file all the
    same, so that the refusal can name who holds it rather than only that somebody does.

    The caller must keep the returned handle bound for as long as it means to hold the
    tree; dropping it closes the descriptor and releases the lock. `None` means the lock
    is already held on a descriptor this process inherited, which is the detached case.
    """
    if os.environ.get(BUILD_LOCK_HELD):
        return None
    handle, holder = _try_lock(build_dir)
    if handle is None:
        raise SystemExit(f"a build already holds {build_dir} (pid {holder}); wait on it "
                         f"with `model.py wait`, or build in a worktree of your own")
    return handle


def hold_lock(target: Path, what: str) -> IO[str]:
    """Hold `target` for the life of this process, or refuse naming the holder.

    `build_lock`'s machinery for the mutable state a build lock does not cover: the
    lane's typecheck SMT cache, which Sail rewrites whole at exit, and the oracle tree
    every lane shares. The lock file sits beside `target` rather than inside it, so it
    pre-exists whatever the run creates and survives whatever the run deletes. The
    caller must keep the returned handle bound for as long as it means to hold
    `target`; dropping it closes the descriptor and releases the lock.
    """
    handle, holder = _try_lock(target)
    if handle is None:
        raise SystemExit(f"{what} already holds {target} (pid {holder}); "
                         f"wait for it to finish")
    return handle


def record_lock_holder(handle: IO[str], pid: int) -> None:
    """Name the process the lock is being held for, which in the detached case is not
    the process that took it."""
    handle.seek(0)
    handle.truncate()
    handle.write(f"{pid}\n")
    handle.flush()


def build_holder(build_dir: Path) -> str | None:
    """Who is building in this tree, or `None` if nobody is.

    Asked without blocking and answered without disturbing anything: the probe takes
    the lock only to learn that it could, and gives it back in the same breath.
    """
    if not _lock_path(build_dir).exists():
        return None
    with _open_lock(build_dir) as handle:
        if _flock(handle, blocking=False):
            _unlock(handle)
            return None
        handle.seek(0)
        return handle.read().strip() or "unknown"


def wait_for_build(build_dir: Path) -> IO[str] | None:
    """Block until this lane's build tree is free, and keep it held for the caller.

    A build holds its lane's lock for exactly as long as it runs, so waiting for the
    lock is waiting for the build: `flock` blocks in the kernel and returns the moment
    the holder's last descriptor closes, which happens whether the build finished or
    was killed. There is no interval to guess, no marker to poll, and a build that died
    without writing `ALL_DONE` ends the wait rather than hanging it.

    The handle comes back still locked rather than released, so that the log the
    caller reads next still carries the run this wait ended on: released first, a new
    build's truncation lands between the wait and the read and the verdict reported is
    the wrong run's opening lines. The caller closes the handle to give the lane back.
    `None` means nothing has ever built here and there is nothing to hold.
    """
    if not _lock_path(build_dir).exists():
        return None
    handle = _open_lock(build_dir)
    _flock(handle, blocking=True)
    return handle


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


def stage(name: str, argv: list[str], report_to: Writable | None = None, *,
          cwd: Path | None = None, stdout: IO[str] | None = None,
          stderr: IO[str] | None = None, add_env: dict[str, str] | None = None) -> int:
    """Run a build stage and record what it cost.

    `add_env` is laid over this process's environment for the child alone, which is how
    `GIT_DIR` reaches cmake's `git describe` without reaching anything else: exported
    globally it would follow every later `git` into trees it does not describe, the
    oracle's among them, and answer for this repository there.

    The breakdown of a full build was known only for its two serial stages; every
    future tuning decision wants the rest, and the cheapest way to get it is to have
    each green build write it down. `os.wait4` reports the rusage of *this* child rather
    than the running maximum over every child so far, so a light stage after a heavy one
    reports its own peak and not the heavy one's.

        STAGE emit wall=107.4s cpu=99% maxrss=2411360kB
    """
    started = time.perf_counter()
    proc = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr,
                            env=None if add_env is None else {**os.environ, **add_env})
    _, status, usage = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(status)

    wall = time.perf_counter() - started
    cpu = (usage.ru_utime + usage.ru_stime) / wall * 100 if wall > 0 else 0
    print(f"STAGE {name} wall={wall:.1f}s cpu={cpu:.0f}% maxrss={usage.ru_maxrss}kB",
          file=_report_stream(report_to, stderr), flush=True)
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


def _keepalive_pidfile() -> Path:
    """`/tmp` and not a private directory, deliberately: the lease is one per
    distribution rather than one per user, and a second tool has to find the first
    one's pidfile to know a lease is already held. Read at call time like every other
    override, so a test's `VOS_KEEPALIVE_PIDFILE` names the file the test must not
    touch no matter when this module was first imported."""
    return _env_path("VOS_KEEPALIVE_PIDFILE", Path("/tmp/vos-keepalive.pid"))  # noqa: S108


def keepalive_hours() -> int:
    """The lease's duration: `VOS_KEEPALIVE_HOURS`, or eight hours unset. Zero and
    below turn the lease off. Read at call time like every other override, and
    garbage is refused by name rather than left to a traceback in whichever tool
    imported this module first."""
    raw = os.environ.get("VOS_KEEPALIVE_HOURS", "8")
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(
            f"VOS_KEEPALIVE_HOURS={raw!r} is not a whole number of hours") from None


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
    hours = keepalive_hours() if hours is None else hours
    if hours <= 0:
        return
    if _lease_sleep() is not None:
        return
    # Between the probe above and the replace below, two racers can both find no lease
    # and both spawn: the later write wins the name and the loser's sleep is orphaned
    # but expires on its own, so the lease's one job, that at least one lives, holds.
    proc = subprocess.Popen(["sleep", str(hours * 3600)], start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pidfile = _keepalive_pidfile()
    scratch = pidfile.with_name(f"{pidfile.name}.{os.getpid()}")
    scratch.write_text(f"{proc.pid}\n")
    # The rename is atomic, so a reader mid-write never parses half a pid as a whole one.
    scratch.replace(pidfile)
    print(f"KEEPALIVE pid={proc.pid} hours={hours} pidfile={pidfile}",
          file=sys.stderr)


def _lease_sleep() -> int | None:
    """The lease's pid, or `None` where no lease is alive. The pidfile is the lease's
    one record, so this is the one place it is read.

    Liveness alone is not the test, because a pid outlives its process only as a
    number: once the sleep exits, the kernel hands the number to whatever process
    comes next, and a dead lease would read as alive for hours. The recorded process
    is the lease only while it is still this module's detached `sleep`, which its own
    argv says.
    """
    try:
        pid = int(_keepalive_pidfile().read_text().strip())
    except (OSError, ValueError):
        # no pidfile, an unreadable one, or garbage in it: there is no lease
        return None
    try:
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return None
    return pid if argv[:1] == [b"sleep"] else None


def keepalive_stop() -> None:
    # Only the lease's own sleep is signalled: a recorded pid that is anything else by
    # now belongs to a stranger. The pidfile is removed either way, so a stale lease
    # is cleared rather than left to read as one.
    pid = _lease_sleep()
    if pid is not None:
        with contextlib.suppress(OSError):
            os.kill(pid, 15)
    _keepalive_pidfile().unlink(missing_ok=True)
