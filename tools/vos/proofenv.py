# SPDX-License-Identifier: Apache-2.0
"""Build-environment subset imported by the proof gate.

The proof gate's implementation identity includes every checkout module imported by
[cli/proofs.py](cli/proofs.py#_gate_modules). Keeping proof-gate environment helpers
here avoids invalidating cached proof objects and kernel verdicts when [env.py](env.py)
changes for model, opam, or CI reasons.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

BUILD_ROOT = Path("/root/build")

# Cross-OS and network filesystems unsuitable for guest build outputs.
CROSS_OS_FILESYSTEMS: frozenset[str] = frozenset({"9p", "drvfs", "virtiofs", "cifs", "smb3"})

# Volatile filesystems that do not survive WSL idle termination.
VOLATILE_FILESYSTEMS: frozenset[str] = frozenset({"tmpfs", "ramfs"})

MOUNTINFO = Path("/proc/self/mountinfo")

OCAML_VERSION = "5.4.1"
OPAM_LOCKS = Path(__file__).resolve().parents[1] / "opam"

ROCQ_VERSION = "9.3.0"
ROCQ_SWITCH = f"verifiedos-rocq-{ROCQ_VERSION}-ocaml-{OCAML_VERSION}"

ROCQ_INSTALL: tuple[tuple[str, ...], ...] = (
    ("opam", "switch", "create", ROCQ_SWITCH, "--repos=rocq-released,default",
     "--empty", "--no-switch", "-y"),
    ("opam", "switch", "import", str(OPAM_LOCKS / "rocq.lock"),
     f"--switch={ROCQ_SWITCH}", "-y"),
)


def install_line(steps: tuple[tuple[str, ...], ...]) -> str:
    """Format an opam installation step sequence as a shell command line."""
    return " && ".join(shlex.join(step) for step in steps)


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ[name]) if bool(os.environ.get(name)) else default


def _gitdir_pointer(root: Path) -> str | None:
    """Return the `gitdir:` target from `root/.git` if `.git` is a pointer file."""
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
    """Return the build lane name for `root` (`""` for the primary checkout).

    A linked worktree's `.git` file points into `<primary>/.git/worktrees/<name>`,
    whereas a submodule's `.git` file points into `.git/modules/`. When `declared`
    is true, `$VOS_LANE` overrides `.git` discovery.
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
    """Return the number of CPUs available to the current process."""
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
    except OSError, ValueError:
        return None
    return None


PROOF_RESERVE_MIB = 2048
PROOF_COMPILE_WORKER_MIB = 1024
PROOF_KERNEL_WORKER_MIB = 2048
PROOF_KERNEL_HEAVY_WORKER_MIB = 10240
PROOF_KERNEL_MODULE_MIB: Mapping[str, int] = MappingProxyType({
    "HmacDrbg": PROOF_KERNEL_HEAVY_WORKER_MIB,
})


@dataclass(frozen=True)
class Workers:
    """Worker limit and the CPU and `MemAvailable` readings used to compute it."""

    jobs: int
    cpus: int
    mem_available_mb: int | None


def kernel_batch_memory_mb(stems: Iterable[str]) -> int:
    """Return the MiB budget required for a kernel worker checking `stems`."""
    return max(
        (PROOF_KERNEL_MODULE_MIB.get(stem, PROOF_KERNEL_WORKER_MIB) for stem in stems),
        default=PROOF_KERNEL_WORKER_MIB,
    )


def kernel_memory_budget_mb(mem_available_mb: int | None) -> int | None:
    """Return the usable MiB budget for concurrent kernel workers after reserving headroom."""
    if mem_available_mb is None:
        return None
    return max(0, mem_available_mb - PROOF_RESERVE_MIB)


def proof_jobs(*, kernel: bool = False) -> int:
    """Use available cores subject to a phase-specific memory planning budget.

    Reserve 2 GiB of headroom (`PROOF_RESERVE_MIB`), then budget 1 GiB per
    compile/audit worker or per-batch kernel budgets: 2 GiB (`PROOF_KERNEL_WORKER_MIB`)
    for ordinary kernel batches and 10 GiB (`PROOF_KERNEL_HEAVY_WORKER_MIB`) for any
    batch containing `HmacDrbg`. Sample in the guest just before each phase, after the
    workspace lock has been acquired.

    The compile/audit budget is an estimate: the historical toolchain-residency
    report records compilation below 1 GiB per module.

    The heavy kernel budget is set at or above the largest whole-set kernel peak
    measured. Guest CI's proofs runner, one x86_64 `ubuntu-26.04` VM of 4 vCPUs and
    16 GB, peaked in GNU time's `maxrss_kb` across three full rechecks of the same
    57 sources at:

        run 36812890026 at 1045acb9    10,029,668 KiB
        run 36814984495 at 2728d4a6    10,030,124 KiB
        run 36819172207 at ae25ee8f    10,029,820 KiB

    The three agree within 456 KiB, so the peak the heavy budget rests on repeats,
    where small `rocqchk` processes' peaks on the profiling guest did not (F-587).

    Beside them, Q38i's per-module rechecks on the profiling guest, a WSL2 aarch64
    VM, each module checked alone with its closure admitted, peaked by `wait4` at
    9,312,124 KiB for HmacDrbg.v and 1,626,180 KiB for Sha256.v, then 864 MiB for
    PqArith.v, 767 for MlKem.v, 707 for Keccak.v and 568 for RomVerifier.v, and at
    most 363 MiB for every other module.

    The 10 GiB heavy budget, 10,485,760 KiB, sits 455,636 KiB (445 MiB, 4.3% of the
    budget) above the largest of these peaks, while the 2 GiB ordinary kernel budget,
    2,097,152 KiB, sits 470,972 KiB (460 MiB, 22.5% of the budget) above `Sha256.v`'s
    peak. Because `HmacDrbg` is isolated into its own kernel batch, a 4-vCPU 16 GB
    runner admits up to 4 ordinary kernel workers (`PROOF_RESERVE_MIB + 4 * 2048 =
    10,240 MiB`), and the memory-aware scheduler runs ordinary batches alongside the
    isolated `HmacDrbg` batch only while active budgets stay within `MemAvailable -
    PROOF_RESERVE_MIB` (e.g., 1 ordinary batch when `MemAvailable >= 14,336 MiB`, or
    `HmacDrbg` alone when lower).

    Two `HmacDrbg` workers at the runner's peak less the literal saving F-581 explored
    (1,186,644 KiB) would still need 19,784,112 KiB with the reserve, above 16 GB,
    so isolating `HmacDrbg` rather than adding literals for `pr_true_run` and
    `first_draw` is what unlocks parallel kernel checking on 16 GB runners.
    """
    return proof_workers(kernel=kernel).jobs


def proof_workers(*, kernel: bool = False) -> Workers:
    """Return the worker limit and resource readings for a proof compile or kernel phase."""
    return size_workers(PROOF_KERNEL_WORKER_MIB if kernel else PROOF_COMPILE_WORKER_MIB,
                        fallback=1 if kernel else 4,
                        label="kernel" if kernel else "compile/audit")


def worker_jobs(memory_mb: int, *, fallback: int = 1, label: str = "worker") -> int:
    """Limit workers to usable CPUs and a per-worker MiB budget after a 2 GiB reserve."""
    return size_workers(memory_mb, fallback=fallback, label=label).jobs


def size_workers(memory_mb: int, *, fallback: int = 1, label: str = "worker") -> Workers:
    """Compute worker limits from usable CPUs and `MemAvailable`."""
    cpus = _cpus()
    available = _read_mem_available_mb()
    if available is None:
        jobs = min(cpus, fallback)
        print(f"WARNING no MemAvailable figure from /proc/meminfo: automatic {label} "
              f"jobs limited to {jobs}; use --jobs to override", file=sys.stderr)
        return Workers(jobs, cpus, None)
    return Workers(min(cpus, max(1, (available - PROOF_RESERVE_MIB) // memory_mb)), cpus, available)


def build_root() -> Path:
    """Return the guest build root (`$VOS_BUILD_ROOT` or `/root/build`)."""
    return _env_path("VOS_BUILD_ROOT", BUILD_ROOT)


def lane_dir(root: Path, lane: str) -> Path:
    """Return `root / f"lane-{lane}"` for a named lane, or `root` for the primary checkout."""
    return root / f"lane-{lane}" if lane else root


def lane_root(lane: str) -> Path:
    """Return the guest build directory for `lane`."""
    return lane_dir(build_root(), lane)


def mount_type(mountinfo: str, path: PurePosixPath | str) -> str:
    """Return the filesystem type of the longest mount-point prefix of `path` in `mountinfo`."""
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
    """Return the filesystem type mounted at `path` (`""` when `/proc/self/mountinfo` is unavailable)."""
    try:
        text = MOUNTINFO.read_text(encoding="utf-8")
    except OSError:
        return ""
    return mount_type(text, Path(path).as_posix())


def opam_root() -> Path:
    """Return the opam root directory (`$OPAMROOT` or `~/.opam`)."""
    return _env_path("OPAMROOT", Path.home() / ".opam")


def rocq_command() -> list[str]:
    """Resolve the `rocq c` compiler command from `$VOS_ROCQ`, `ROCQ_SWITCH`, or `PATH`."""
    override = os.environ.get("VOS_ROCQ")
    if bool(override):
        return [override, "c"]
    pinned = opam_root() / ROCQ_SWITCH / "bin" / "rocq"
    if pinned.is_file():
        return [str(pinned), "c"]
    found = shutil.which("rocq")
    if bool(found):
        return [found, "c"]
    raise SystemExit(f"no prover: neither $VOS_ROCQ, nor {pinned}, nor rocq on PATH. "
                     f"{install_line(ROCQ_INSTALL)}")


def rocqchk_command() -> list[str]:
    """Resolve the `rocqchk` kernel re-checker command from `$VOS_ROCQCHK`, `ROCQ_SWITCH`, or `PATH`."""
    override = os.environ.get("VOS_ROCQCHK")
    if bool(override):
        return [override]
    pinned = opam_root() / ROCQ_SWITCH / "bin" / "rocqchk"
    if pinned.is_file():
        return [str(pinned)]
    found = shutil.which("rocqchk")
    if bool(found):
        return [found]
    raise SystemExit(f"no kernel re-checker: neither $VOS_ROCQCHK, nor {pinned}, nor "
                     f"rocqchk on PATH. {install_line(ROCQ_INSTALL)}")


def git_dir(root: Path) -> Path | None:
    """Return the guest-translated git administrative directory when `root/.git` holds a Windows path.

    Linked worktrees created by Windows `git` store a Windows drive path in `.git`,
    which fails inside WSL unless translated with `wslpath` and passed via `GIT_DIR`.
    """
    override = os.environ.get("VOS_GIT_DIR")
    if bool(override):
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
    """Return `GIT_DIR` and `GIT_WORK_TREE` environment bindings for `admin` and `root`.

    Setting `GIT_DIR` without `GIT_WORK_TREE` causes `git` invocations in subdirectories
    (such as CMake's `git describe` in `model/cmake`) to treat the subdirectory as the
    working tree and falsely report `-dirty`.
    """
    return {"GIT_DIR": str(admin), "GIT_WORK_TREE": str(root)}


def git_env(root: Path) -> dict[str, str]:
    """Return the `GIT_DIR`/`GIT_WORK_TREE` overlay needed for `root` (`{}` if none)."""
    admin = git_dir(root)
    return {} if admin is None else git_overlay(admin, root)
