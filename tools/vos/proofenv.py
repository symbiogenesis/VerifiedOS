# SPDX-License-Identifier: Apache-2.0
"""The share of the build environment the proof gate runs on, kept out of env.py.

The gate's implementation identity is every checkout module Python runs to import it,
which [cli/proofs.py](cli/proofs.py)'s `_gate_modules` derives from import statements,
and a change to any of those modules invalidates every cached proof object and kernel
verdict. [env.py](env.py) changes for model, opam and CI reasons the gate never reads,
so what the gate calls, directly and through [receipts.py](receipts.py) and
[corpus.py](corpus.py), lives here instead: where a lane's guest outputs land and on
which filesystem, the prover and its kernel re-checker, the git overlay a lane needs,
and the worker limits sized from cores and memory. This module imports nothing from
`vos`, and env.py binds every public name here as its own, so env.py's readers reach
each one there unchanged.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

# Where every lane's build trees live, a constant rather than a literal at its use
# because `run.py provision` wants it without standing env.py's `Environment` up.
BUILD_ROOT = Path("/root/build")

# The filesystem types that reach across the OS boundary: a Windows drive mounted into
# the guest, which is 9p under WSL 2, drvfs under WSL 1 and virtiofs where a newer WSL is
# told to use it, and a network share. A path on one of these is read or written across
# the boundary on every call, which env.py's module docstring measures, so a guest
# loop's output may not sit on one: that is the placement rule tools/README.md states,
# which `run.py provision` probes.
CROSS_OS_FILESYSTEMS: frozenset[str] = frozenset({"9p", "drvfs", "virtiofs", "cifs", "smb3"})

# The filesystems that do not outlive the instance, so a build tree or a log on one is
# gone when the guest idle-terminates: the ground env.py's `LOG_ROOT` gives for never
# being /tmp.
VOLATILE_FILESYSTEMS: frozenset[str] = frozenset({"tmpfs", "ramfs"})

# Where the kernel says what is mounted where, read by `filesystem`.
MOUNTINFO = Path("/proc/self/mountinfo")

# The OCaml release every project switch builds on, which env.py's findlib pin holds
# there, and the lock snapshots the switches import.
OCAML_VERSION = "5.4.1"
OPAM_LOCKS = Path(__file__).resolve().parents[1] / "opam"

# The prover the gate compiles and checks with, and the project switch holding it;
# env.py states what holds the release where it is.
ROCQ_VERSION = "9.3.0"
ROCQ_SWITCH = f"verifiedos-rocq-{ROCQ_VERSION}-ocaml-{OCAML_VERSION}"

# What creates that switch, as the argv a tool runs rather than as the sentence a person
# reads: `rocq_command` prints it to a caller that has no prover and `run.py provision`
# runs it, and a recipe stated twice is the defect these tools exist to catch.
ROCQ_INSTALL: tuple[tuple[str, ...], ...] = (
    ("opam", "switch", "create", ROCQ_SWITCH, "--repos=rocq-released,default",
     "--empty", "--no-switch", "-y"),
    ("opam", "switch", "import", str(OPAM_LOCKS / "rocq.lock"),
     f"--switch={ROCQ_SWITCH}", "-y"),
)


def install_line(steps: tuple[tuple[str, ...], ...]) -> str:
    """A recipe as a person types it, composed from the argv a tool would run.

    One owner and two readers: the message that names an absent switch, and the
    provisioner that stands one up. Written the other way round, a message and a
    command are two copies of one recipe and only one of them is ever run.
    """
    return " && ".join(shlex.join(step) for step in steps)


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ[name]) if os.environ.get(name) else default


def _gitdir_pointer(root: Path) -> str | None:
    """The target a linked checkout's `.git` pointer file names, `None` where `.git`
    is a directory, absent, or unreadable. The raw spelling is returned rather than a
    parsed path, because the two readers want different halves of it: `lane_of` the
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


def lane_of(root: Path, *, declared: bool = True) -> str:
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

    `VOS_LANE` declares a lane outright, which is how a container lane with no `.git`
    pointer gets one, and `declared=False` reads past it: `run.py worktree` reports
    the identity git gives a checkout, and an override set in the parent's shell would
    otherwise name every lane it hands out after itself.
    """
    if declared:
        override = os.environ.get("VOS_LANE")
        if override is not None:
            return override.strip().lower()
    target = _gitdir_pointer(root)
    if target is None:
        return ""
    admin = PurePosixPath(target.replace("\\", "/"))
    return admin.name.lower() if admin.parent.name == "worktrees" else ""


def _cpus() -> int:
    """The cores this process may actually run on, which is what a job count wants.
    `os.process_cpu_count` honours the affinity mask on every platform that has one, so
    the guest's twelve stay twelve and a pinned run sees only what it was given."""
    return os.process_cpu_count() or 1


def _read_mem_available_mb() -> int | None:
    """Guest memory available without swapping, in MiB; None when unreadable."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                fields = line.split()
                if len(fields) == 3 and fields[2] == "kB":
                    value = int(fields[1])
                    if value >= 0:
                        return value // 1024
                return None
    except (OSError, ValueError):
        return None
    return None


# The proof gate's per-worker planning budgets in MiB, which `proof_jobs` states the
# basis of.
PROOF_COMPILE_WORKER_MIB = 1024
PROOF_KERNEL_WORKER_MIB = 10240


def proof_jobs(*, kernel: bool = False) -> int:
    """Use available cores subject to a phase-specific memory planning budget.

    Reserve 2 GiB of headroom, then budget 1 GiB per compile/audit worker or 10 GiB
    per kernel worker. Sample in the guest just before each phase, after the workspace
    lock has been acquired.

    The compile/audit budget is an estimate: the historical toolchain-residency
    report records compilation below 1 GiB per module.

    The kernel budget is set at or above the largest kernel worker peak measured.
    Guest CI's proofs runner, one x86_64 `ubuntu-26.04` VM of 4 vCPUs and 16 GB,
    checks every module in one kernel worker. GNU time's `maxrss_kb`, the peak
    resident memory of the gate's largest process, read in three full rechecks of
    the same 57 sources:

        run 36812890026 at 1045acb9    10,029,668 KiB
        run 36814984495 at 2728d4a6    10,030,124 KiB
        run 36819172207 at ae25ee8f    10,029,820 KiB

    The three agree within 456 KiB, so the peak the budget rests on repeats, where
    small `rocqchk` processes' peaks on the profiling guest did not (F-587).

    Beside them, Q38i's per-module rechecks on the profiling guest, a WSL2 aarch64
    VM, each module checked alone with its closure admitted, peaked by `wait4` at
    9,312,124 KiB for HmacDrbg.v and 1,626,180 KiB for Sha256.v, then 864 MiB for
    PqArith.v, 767 for MlKem.v, 707 for Keccak.v and 568 for RomVerifier.v, and at
    most 363 MiB for every other module.

    The 10 GiB budget, 10,485,760 KiB, sits 455,636 KiB (445 MiB, 4.3% of the
    budget) above the largest of these peaks. A second kernel worker needs 22,528
    MiB available, which a 16 GB runner never has, so that runner runs one kernel
    worker; its four compile/audit workers need 6,144 MiB.

    The peak HmacDrbg.v's literals would save admits no second worker there either
    (F-581). Literals for its `pr_true_run` and `first_draw` lowered its per-module
    recheck peak by 1,186,644 KiB. Two workers at the largest runner peak less that
    saving would need 17,686,960 KiB, and 19,784,112 KiB with the reserve, above the
    runner's 16 GB even read as 16 GiB, 16,777,216 KiB. So HmacDrbg.v keeps no
    literal for them.
    """
    return worker_jobs(PROOF_KERNEL_WORKER_MIB if kernel else PROOF_COMPILE_WORKER_MIB,
                       fallback=1 if kernel else 4,
                       label="kernel" if kernel else "compile/audit")


def worker_jobs(memory_mb: int, *, fallback: int = 1, label: str = "worker") -> int:
    """Limit workers to usable CPUs and a per-worker MiB budget after a 2 GiB reserve."""
    cpus = _cpus()
    available = _read_mem_available_mb()
    if available is None:
        jobs = min(cpus, fallback)
        print(f"WARNING no MemAvailable figure from /proc/meminfo: automatic {label} "
              f"jobs limited to {jobs}; use --jobs to override", file=sys.stderr)
        return jobs
    return min(cpus, max(1, (available - 2048) // memory_mb))


def build_root() -> Path:
    """Where every lane's build trees live.

    Public because `run.py provision` asks the layout a question without standing an
    `Environment` up: env.py's `load` raises the stack limit, applies the opam
    environment and prepends the pinned solver, none of which a probe of where the
    caches are has any business doing.
    """
    return _env_path("VOS_BUILD_ROOT", BUILD_ROOT)


def lane_dir(root: Path, lane: str) -> Path:
    """One lane's directory under a build root: the root itself for the primary
    worktree, `lane-<name>` beneath it for a linked one. The composition is written
    here once, for env.py's `Environment.lane_root` and for the two readers that have
    no `Environment`: `run.py rtl install` standing a toolchain up, and `run.py
    worktree` naming where a lane's guest outputs will land before the lane has built
    anything."""
    return root / f"lane-{lane}" if lane else root


def lane_root(lane: str) -> Path:
    """Where the named lane's guest outputs land, under this machine's build root."""
    return lane_dir(build_root(), lane)


def mount_type(mountinfo: str, path: PurePosixPath | str) -> str:
    """The filesystem type of the mount holding `path`, read out of one mountinfo
    text, or `""` where no mount point is a prefix of it.

    Pure, so a test can hand it the text of a machine it is not running on. The
    longest mount point that is a prefix of the path wins, which is the kernel's own
    resolution, and a mount point matches only at a separator so `/mnt/c` does not
    claim `/mnt/cd`. The path need not exist: a build root no build has created yet is
    still on the mount that will hold it. A mount point carrying a space or a backslash
    arrives octal-escaped in mountinfo and is decoded before the comparison.
    """
    wanted = PurePosixPath(path).as_posix()
    best, kind = -1, ""
    for line in mountinfo.splitlines():
        head, sep, tail = line.partition(" - ")
        fields = head.split()
        if not sep or len(fields) < 5:
            continue
        point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[4])
        holds = (wanted == point or (point == "/" and wanted.startswith("/"))
                 or wanted.startswith(point.rstrip("/") + "/"))
        if holds and len(point) > best:
            kinds = tail.split()
            best, kind = len(point), kinds[0] if kinds else ""
    return kind


def filesystem(path: Path | str) -> str:
    """The filesystem type under `path` on this machine, `""` where the kernel's mount
    table cannot be read, which is the win32 lane's answer and the right one: the
    question is which side of the OS boundary a guest path sits on, and only the guest
    can say. `CROSS_OS_FILESYSTEMS` and `VOLATILE_FILESYSTEMS` are what a reader holds
    the answer against."""
    try:
        text = MOUNTINFO.read_text(encoding="utf-8")
    except OSError:
        return ""
    return mount_type(text, Path(path).as_posix())


def opam_root() -> Path:
    """Where the switches live. Public because more than one prover switch is reached
    from this repository now: the proof gate's, and the CertiRocq oracle's that
    [vos/gallina.py](gallina.py) compiles the Gallina front in."""
    return _env_path("OPAMROOT", Path.home() / ".opam")


def rocq_command() -> list[str]:
    """The prover as an argument list, for the proof gate rather than for a model loop.

    Both halves are resolved here rather than assumed by the caller. Rocq 9 ships no
    `coqc` at any version, its switch holding `rocq`, `rocq.byte`, and `rocqchk` and
    nothing else, so compilation is spelled `rocq c`; and ROCQ_SWITCH is not the switch
    env.py's `_apply_opam_env` puts on PATH, so a bare `rocq` finds nothing.
    """
    override = os.environ.get("VOS_ROCQ")
    if override:
        return [override, "c"]
    pinned = opam_root() / ROCQ_SWITCH / "bin" / "rocq"
    if pinned.is_file():
        return [str(pinned), "c"]
    found = shutil.which("rocq")
    if found:
        return [found, "c"]
    raise SystemExit(f"no prover: neither $VOS_ROCQ, nor {pinned}, nor rocq on PATH. "
                     f"{install_line(ROCQ_INSTALL)}")


def rocqchk_command() -> list[str]:
    """The prover's own kernel re-checker, as an argument list.

    Resolved the three ways `rocq_command` resolves the compiler and separately from
    it, so a lane that overrides one may override the other: `$VOS_ROCQCHK`, then the
    pinned switch, then PATH. It ships in ROCQ_SWITCH beside `rocq` rather than in a
    package of its own, which is why an absence is answered with that switch's install
    line: a tree with `rocq` and no `rocqchk` is a switch built some other way, not a
    missing dependency this repository states a second recipe for.

    It takes no subcommand where `rocq c` takes one: the binary still announces itself
    as `coqchk` and its usage is `coqchk <options> modules`.
    """
    override = os.environ.get("VOS_ROCQCHK")
    if override:
        return [override]
    pinned = opam_root() / ROCQ_SWITCH / "bin" / "rocqchk"
    if pinned.is_file():
        return [str(pinned)]
    found = shutil.which("rocqchk")
    if found:
        return [found]
    raise SystemExit(f"no kernel re-checker: neither $VOS_ROCQCHK, nor {pinned}, nor "
                     f"rocqchk on PATH. {install_line(ROCQ_INSTALL)}")


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
    `run.py model reference` is the gate that catches it, and in a lane it caught it.

    `wslpath` does the translation rather than a rule about `/mnt`, because the mount
    root is configurable and the tool that knows it ships with the guest. A pointer that
    is already usable, a primary worktree, and a lane with no `wslpath` to ask all
    answer `None`, which leaves the behaviour exactly as it was.

    The pointer is read through `_gitdir_pointer` rather than parsed again here, which
    is what makes that function's *two readers* true of `lane_of` and of this: written out
    twice, the file test, the read and the `gitdir:` prefix were one fact in two places
    and the pair could have stopped agreeing about which files are pointers at all.

    `VOS_GIT_DIR` names the directory outright and is read at call time like every
    other override here. It is the route left open where the translation cannot be
    made, a guest with no `wslpath` answering `None` above and every `git` in that lane
    then failing, and it is how a test drives `git_env` below over a checkout that
    needs no translating.
    """
    override = os.environ.get("VOS_GIT_DIR")
    if override:
        return Path(override)
    target = _gitdir_pointer(root)
    if target is None:
        return None
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


def git_overlay(admin: Path, root: Path) -> dict[str, str]:
    """What a child must be told before it can run `git` in a checkout whose
    administrative directory is `admin`. Laid over the child's own environment and
    never exported globally, for the reason env.py's `stage` states of its `add_env`.

    **`GIT_DIR` alone is half an answer and the missing half is not cosmetic.** With no
    `GIT_WORK_TREE`, git takes the child's own working directory as the tree, and a
    child asking about this repository rarely stands at its root: cmake runs
    `git describe --tags --always --dirty --broken` in `model/cmake`, which is
    `project_version.cmake`'s own `WORKING_DIRECTORY`. The index is then read against
    that directory, every tracked path in it is missing, and `--dirty` fires whatever
    the lane's state is. Measured from that directory over a checkout `git status
    --porcelain` reports empty: the pair answers the commit alone, `GIT_DIR` by itself
    answers the same commit with `-dirty` appended and lists every tracked path as
    ` D`, and no environment at all answers the commit alone because git's own
    discovery finds the tree the child is standing in.

    An always-on marker is not a conservative one. The emulator's revision is what
    every downstream artifact records itself against, and a suffix that cannot be
    absent cannot report the lane that is genuinely edited, which is the only thing it
    is there to say.

    The work tree is the repository root rather than the model tree, because the
    revision being stamped is this repository's: a curation edit outside `model/` moves
    it exactly as one inside does.

    Separate from `git_env` below because this half is a composition over two paths and
    that half is a reading of a checkout: a case can decide the composition against
    real `git` over a throwaway tree, where deciding it through the reading would mean
    setting a process-global override while the rest of the suite runs in threads
    beside it.
    """
    return {"GIT_DIR": str(admin), "GIT_WORK_TREE": str(root)}


def git_env(root: Path) -> dict[str, str]:
    """The overlay this checkout needs, empty where it needs none.

    Empty is the primary worktree's answer and the host's, where git's own discovery
    finds the tree from the directory the child stands in; a lane read from the guest
    is where it is not, and `git_dir` above states why.
    """
    admin = git_dir(root)
    return {} if admin is None else git_overlay(admin, root)
