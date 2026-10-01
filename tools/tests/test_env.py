# SPDX-License-Identifier: Apache-2.0
"""The build environment's host-testable seams.

`vos/env.py` runs its loops in the guest, but it is imported on both lanes, so what
is held here is everything that must be true before a loop starts: the module
imports cleanly on win32 and `load()` refuses the lane by name, `lane_of` derives the
lane from the checkout's `.git` shape, `_jobs` sizes from cores under the memory
guard, the proof gate's kernel budget stands at or above the runner peaks
`proof_jobs` records, and the overrides wave 1 moved to validated call-time reads
take effect when set after the import, which is the hook a test like this one
stands on.

One case here runs real `git` over a throwaway checkout rather than reading a
function's return, because what `git_env` is for is a *child's* answer: the overlay
is correct exactly when the `git describe` cmake runs at configure reports a clean
lane clean and an edited one edited, and no assertion about a dictionary decides that.

One case is guest-only, and it is the arm the host cannot reach at all: `load()` on
win32 returns at the platform refusal before it gets to the preparations, so what
`toolchain=False` skips is decidable only where a toolchain could have been prepared.
"""

import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, with_env
from vos import env


def _refuses_win32() -> None:
    # The import above already proves the module loads on this lane; load() itself
    # must refuse with the command that works rather than fail on a POSIX import.
    try:
        env.load()
    except SystemExit as err:
        ensure("python tools/run.py model" in str(err),
               f"the win32 refusal must name the guest spelling, said {err}")
        return
    raise AssertionError("env.load() on win32 must refuse rather than load")


def _expect_exit(fn: Callable[[], object], fragment: str, what: str) -> None:
    try:
        fn()
    except SystemExit as err:
        ensure(fragment in str(err), f"{what}: the refusal said {err}")
        return
    raise AssertionError(f"{what}: expected a SystemExit naming {fragment}")


def _lane_shapes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        # the primary shape: .git is a directory, so there is no pointer to read
        (root / ".git").mkdir()
        ensure(env.lane_of(root) == "", "a .git directory is the primary lane")

    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        dot_git = root / ".git"
        # a linked worktree: the pointer names a directory under .git/worktrees/,
        # and git on Windows writes it with either separator
        dot_git.write_text("gitdir: C:/repo/.git/worktrees/LaneX\n", encoding="utf-8")
        ensure(env.lane_of(root) == "lanex",
               f"a worktree pointer must yield its lowercased name, got {env.lane_of(root)!r}")
        dot_git.write_text("gitdir: C:\\repo\\.git\\worktrees\\Mixed\n", encoding="utf-8")
        ensure(env.lane_of(root) == "mixed",
               "a backslash pointer must normalize before it is parsed")
        # a submodule's .git is a file too, pointing into .git/modules/ instead,
        # which is why the parent component and not the file kind decides
        dot_git.write_text("gitdir: ../../.git/modules/sub\n", encoding="utf-8")
        ensure(env.lane_of(root) == "", "a submodule pointer is not a lane")
        dot_git.write_text("not a pointer at all\n", encoding="utf-8")
        ensure(env.lane_of(root) == "", "a .git file with no gitdir: line is not a lane")


def _lane_override() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        with_env("VOS_LANE", " MyLane ", lambda: ensure(
            env.lane_of(root) == "mylane",
            "VOS_LANE set after import must win, stripped and lowercased"))
        with_env("VOS_LANE", "", lambda: ensure(
            env.lane_of(root) == "",
            "an empty VOS_LANE names the primary lane explicitly"))
        # the handoff reads past the declaration to the checkout's own pointer, so a
        # parent's shell cannot name every lane it hands out after itself
        with_env("VOS_LANE", "declared", lambda: ensure(
            env.lane_of(root, declared=False) == "",
            "declared=False must read the checkout rather than VOS_LANE"))


def _lane_roots_compose() -> None:
    """One composition for the three readers of where a lane's outputs land, and the
    log root beside it, both read at call time like every other override here."""
    with_env("VOS_BUILD_ROOT", None, lambda: ensure(
        env.lane_root("").as_posix() == "/root/build"
        and env.lane_root("lanex").as_posix() == "/root/build/lane-lanex",
        "the primary builds at the root and a linked lane under lane-<name>"))
    with_env("VOS_BUILD_ROOT", "/root/elsewhere", lambda: ensure(
        env.lane_root("lanex").as_posix() == "/root/elsewhere/lane-lanex",
        "VOS_BUILD_ROOT set after import must move every lane with it"))
    ensure(env.lane_dir(Path("/b"), "x") == Path("/b/lane-x")
           and env.lane_dir(Path("/b"), "") == Path("/b"),
           "the composition is the same function the Environment property reads")
    with_env("VOS_LOG_DIR", None, lambda: ensure(
        env.log_root().as_posix() == "/root/logs",
        "logs live under /root and never /tmp, which does not outlive the instance"))
    with_env("VOS_LOG_DIR", "/root/logs-elsewhere", lambda: ensure(
        env.log_root().as_posix() == "/root/logs-elsewhere",
        "VOS_LOG_DIR set after import must win"))


# A mount table in the kernel's own shape: the root on ext4, the Windows drive over 9p
# as WSL 2 mounts it, tmpfs at /tmp, a mount point carrying an escaped space, and a
# share whose mount point shares a prefix with the drive's without being under it.
_MOUNTINFO = r"""
84 69 8:48 / / rw,relatime - ext4 /dev/sdd rw,discard,errors=remount-ro
133 84 0:71 / /mnt/c rw,noatime - 9p C:\134 rw,aname=drvfs;path=C:\;uid=0;gid=0
137 84 0:73 / /tmp rw,nosuid,nodev - tmpfs tmpfs rw,size=8058820k
140 84 0:74 / /mnt/with\040space rw,relatime - xfs /dev/sde rw
141 84 0:75 / /mnt/cd rw,noatime shared:5 - cifs //share/cd rw,vers=3.1.1
"""


def _mount_type_reads_the_table() -> None:
    """The placement rule's one reader, held over a table it did not read off this
    machine: the longest mount point wins, at a separator, escapes decoded."""
    # the tmpfs path is a fixture read against the table above and never a file this
    # test touches, which is what the lint the noqa names is for
    volatile = "/tmp/vos"  # noqa: S108
    for path, kind in (("/root/build/lane-x", "ext4"), ("/mnt/c", "9p"),
                       ("/mnt/c/Users/x/VerifiedOS", "9p"), (volatile, "tmpfs"),
                       ("/mnt/cd/x", "cifs"), ("/mnt/cdrom", "ext4"),
                       ("/mnt/with space/log", "xfs")):
        ensure(env.mount_type(_MOUNTINFO, path) == kind,
               f"{path} must read {kind}, got {env.mount_type(_MOUNTINFO, path)!r}")
    ensure(env.mount_type(_MOUNTINFO, "relative/path") == "",
           "a relative path is under no mount point")
    ensure(env.mount_type("", "/root") == "", "an empty table names no filesystem")
    ensure("9p" in env.CROSS_OS_FILESYSTEMS and "tmpfs" in env.VOLATILE_FILESYSTEMS
           and not (env.CROSS_OS_FILESYSTEMS & env.VOLATILE_FILESYSTEMS),
           "the two verdicts a reader draws are over disjoint sets")
    # the live reader: the win32 lane has no mount table and says so with an empty
    # answer, and the guest answers with the type under its own working directory
    kind = env.filesystem(Path.cwd())
    ensure(kind == "" if sys.platform == "win32" else kind != "",
           f"filesystem() must answer empty on win32 and non-empty in the guest, got "
           f"{kind!r}")


def _jobs_arithmetic() -> None:
    # cpus+2 with 2 GB reserved for the generated unit and 512 MB per other job:
    # inert at the default VM size, binding under a shrunken one.
    ensure(env._jobs(12, 15700) == 14, "at 15.7 GB the guard is inert: cpus+2")
    ensure(env._jobs(12, 4096) == 4, "under a 4 GB cap the guard binds: (4096-2048)//512")
    ensure(env._jobs(4, 0) == 6, "with no memory figure the guard cannot bind")
    ensure(env._jobs(1, 2560) == 1, "the guard floors at one job, never zero")
    ensure(env._jobs(12, 2048) == 1, "at the reserve the guard permits only one job")
    ensure(env._jobs(12, 1024) == 1, "below the reserve the guard must stay engaged")
    counts = [env._jobs(12, memory) for memory in (1, 1024, 2048, 2049, 2560, 4096)]
    ensure(counts == sorted(counts), "less available memory must never admit more jobs")


def _jobs_env_reads() -> None:
    # VOS_JOBS is read at call time and validated by name; garbage and non-positive
    # counts alike would otherwise land on ninja's command line as -j.
    with_env("VOS_JOBS", "7", lambda: ensure(
        env._jobs(12, 15700) == 7, "VOS_JOBS set after import must win"))
    with_env("VOS_JOBS", "junk", lambda: _expect_exit(
        lambda: env._jobs(12, 15700), "VOS_JOBS", "garbage VOS_JOBS"))
    with_env("VOS_JOBS", "0", lambda: _expect_exit(
        lambda: env._jobs(12, 15700), "not a positive count", "zero VOS_JOBS"))
    with_env("VOS_JOBS", "-3", lambda: _expect_exit(
        lambda: env._jobs(12, 15700), "not a positive count", "negative VOS_JOBS"))


def _proof_jobs_use_phase_resources() -> None:
    samples = ((12, 128 * 1024, 12, 12), (64, 128 * 1024, 64, 12),
               (2, 128 * 1024, 2, 2), (12, 16 * 1024, 12, 1),
               (12, 32 * 1024, 12, 3), (12, 2048, 1, 1),
               (12, 0, 1, 1), (None, 64 * 1024, 1, 1),
               (12, None, 4, 1), (None, None, 1, 1))
    for cpus, memory, compilation, kernel in samples:
        with patch.object(env.os, "process_cpu_count", return_value=cpus), \
                patch.object(env, "_read_mem_available_mb", return_value=memory), \
                patch.dict(os.environ, {"VOS_JOBS": "99"}), \
                redirect_stderr(io.StringIO()) as warnings:
            ensure(env.proof_jobs() == compilation, "wrong automatic compile/audit limit")
            ensure(env.proof_jobs(kernel=True) == kernel, "wrong automatic kernel limit")
            ensure(bool(warnings.getvalue()) == (memory is None),
                   "only unavailable memory should produce a fallback diagnostic")


def _kernel_budget_holds_the_recorded_peaks() -> None:
    """The kernel budget stands at or above every runner peak `proof_jobs` records, and
    the margin, the second worker's threshold and the runner's worker counts it states
    are what the budget and the reserve give."""
    doc = env.proof_jobs.__doc__ or ""
    peaks = [int(kib.replace(",", "")) for kib in re.findall(
        r"^\s*run \d{11} at [0-9a-f]{8}\s+([\d,]+) KiB$", doc, re.MULTILINE)]
    ensure(len(peaks) == 3, f"proof_jobs records three runner peaks, read {peaks}")
    budget = env.PROOF_KERNEL_WORKER_MIB * 1024
    ensure(all(peak <= budget for peak in peaks),
           f"a recorded kernel peak exceeds the {budget} KiB budget: {peaks}")
    margin = budget - max(peaks)
    ensure(f"{budget:,} KiB, sits {margin:,} KiB ({round(margin / 1024)} MiB, "
           f"{100 * margin / budget:.1f}% of the" in " ".join(doc.split()),
           "the stated margin is not the budget less the largest recorded peak")
    second = 2048 + 2 * env.PROOF_KERNEL_WORKER_MIB
    ensure(f"needs {second:,} MiB available" in " ".join(doc.split()),
           "the stated second-worker threshold is not the reserve and two budgets")
    # The runner's four vCPUs: four compile/audit workers and one kernel worker over
    # every MemAvailable a 16 GB machine can report, two kernel workers only past it.
    for memory, compilation, kernel in ((6144, 4, 1), (6143, 3, 1), (16 * 1024, 4, 1),
                                        (second - 1, 4, 1), (second, 4, 2)):
        with patch.object(env.os, "process_cpu_count", return_value=4), \
                patch.object(env, "_read_mem_available_mb", return_value=memory), \
                redirect_stderr(io.StringIO()):
            ensure((env.proof_jobs(), env.proof_jobs(kernel=True)) == (compilation, kernel),
                   f"wrong runner worker counts at {memory} MiB available")


def _toolchain_jobs_use_resources() -> None:
    for cpus, memory, expected in ((4, 16384, 4), (64, 8192, 3), (64, 262144, 64),
                                   (12, 0, 1), (None, 16384, 1), (12, None, 1)):
        with (patch.object(env.os, "process_cpu_count", return_value=cpus),
              patch.object(env, "_read_mem_available_mb", return_value=memory),
              redirect_stderr(io.StringIO())):
            ensure(env.worker_jobs(2048) == expected, "wrong CPU or memory worker limit")


def _memory_reading_distinguishes_exhaustion_from_unknown() -> None:
    samples = (("MemAvailable: 1048576 kB\n", 1024), ("MemAvailable: 0 kB\n", 0),
               ("MemAvailable: -1024 kB\n", None), ("MemAvailable: invalid kB\n", None),
               ("MemAvailable:\n", None), ("MemAvailable: 1024 MB\n", None),
               ("MemTotal: 1048576 kB\n", None))
    for text, expected in samples:
        with patch.object(env.Path, "read_text", return_value=text):
            ensure(env._read_mem_available_mb() == expected, "wrong memory availability reading")
    with patch.object(env.Path, "read_text", side_effect=OSError("unavailable")):
        ensure(env._read_mem_available_mb() is None, "unreadable memory must be unknown")


def _keepalive_hours_reads() -> None:
    with_env("VOS_KEEPALIVE_HOURS", None, lambda: ensure(
        env.keepalive_hours() == 8, "unset, the lease defaults to eight hours"))
    with_env("VOS_KEEPALIVE_HOURS", "3", lambda: ensure(
        env.keepalive_hours() == 3, "VOS_KEEPALIVE_HOURS set after import must win"))
    with_env("VOS_KEEPALIVE_HOURS", "0", lambda: ensure(
        env.keepalive_hours() == 0, "zero is valid and turns the lease off"))
    with_env("VOS_KEEPALIVE_HOURS", "soon", lambda: _expect_exit(
        env.keepalive_hours, "VOS_KEEPALIVE_HOURS", "garbage VOS_KEEPALIVE_HOURS"))


def _keepalive_pidfile_read() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        override = Path(td) / "lease.pid"
        with_env("VOS_KEEPALIVE_PIDFILE", str(override), lambda: ensure(
            env._keepalive_pidfile() == override,
            "VOS_KEEPALIVE_PIDFILE set after import must name the test's file"))
    with_env("VOS_KEEPALIVE_PIDFILE", None, lambda: ensure(
        env._keepalive_pidfile().name == "vos-keepalive.pid",
        "unset, the lease keeps its one shared name"))


def _hoisted_lane_constants() -> None:
    """The three literals the loops used to spell inline, held at the paths and names
    a live loop depends on.

    `_prepend_z3_path` is the one invariant here whose absence is silent rather than
    loud: a wrong prefix does not fail a build, it typechecks against the
    distribution's solver and caches that solver's answers. So a typo in the composed
    path is not caught by anything a build does, and this is what catches it.
    """
    with_env("VOS_Z3_BIN", None, lambda: ensure(
        str(env.Z3_PREFIX / "bin").replace("\\", "/") == "/root/z3-5.1.0/bin",
        f"the pinned solver's prefix must compose to the unpacked one, got "
        f"{env.Z3_PREFIX}"))
    ensure(env.SAIL_SWITCH == "verifiedos-sail-0.20.3-ocaml-5.4.1",
           f"the Sail switch is project-specific and versioned, got {env.SAIL_SWITCH!r}")
    ensure(env.ROCQ_SWITCH == "verifiedos-rocq-9.3.0-ocaml-5.4.1",
           f"the prover switch carries its pin in its name, got {env.ROCQ_SWITCH!r}")
    with_env("VOS_BUILD_ROOT", None, lambda: ensure(
        str(env.build_root()).replace("\\", "/") == "/root/build",
        f"the build root is where every lane's tree lives, got {env.build_root()}"))
    with_env("VOS_BUILD_ROOT", "/root/build-elsewhere", lambda: ensure(
        str(env.build_root()).replace("\\", "/") == "/root/build-elsewhere",
        "VOS_BUILD_ROOT set after import must win, like every other override here"))


def _oracle_tree_keys_the_edition() -> None:
    """The shared oracle tree is named for its pin and filed under the Sail edition.

    The upstream Makefile regenerates C only when the Sail sources change, so a tree
    kept across a lock change would answer with the earlier compiler's emulator. The
    edition sits in a parent directory, and the tree's own name still ends in the pin,
    which is where the pin checks read it.
    """
    build = Path("/root/build")
    e = env.Environment(Path("/repo"), Path("/repo/model"), build, Path("/root/logs"),
                        "lanex", 4, 4096, 2, 2)
    edition = build / f"sail-{env.SAIL_VERSION}"
    ensure(env.oracle_tree(build) == edition / env.ORACLE_TREE,
           f"the tree sits under its edition, got {env.oracle_tree(build)}")
    with_env("VOS_ORACLE_ROOT", None, lambda: with_env("VOS_ORACLE", None, lambda: ensure(
        e.oracle_root == edition / env.ORACLE_TREE
        and e.oracle == edition / env.ORACLE_TREE / "c_emulator" / "cheri_riscv_sim_RV64",
        f"every lane reads the one edition-keyed tree, got {e.oracle_root}")))
    with_env("VOS_ORACLE_ROOT", "/elsewhere/tree", lambda: with_env("VOS_ORACLE", None,
        lambda: ensure(e.oracle_root == Path("/elsewhere/tree")
                       and e.oracle.parent.parent == Path("/elsewhere/tree"),
                       "VOS_ORACLE_ROOT still names the tree outright")))
    with_env("VOS_ORACLE", "/elsewhere/sim", lambda: ensure(
        e.oracle == Path("/elsewhere/sim"), "VOS_ORACLE still names the simulator outright"))


def _solver_install_is_hashed() -> None:
    """The solver installs only as a wheel whose bytes the requirements file names.

    uv takes hashes only from a requirements file, so the wheel pin is stated there
    beside its hashes and held here against `Z3_VERSION`, the release every other
    reader names: one requirement, at the release's wheel version, carrying one SHA-256
    per architecture a guest runs on and nothing weaker.
    """
    recipe = env.Z3_INSTALL
    ensure(len(recipe) == 1 and recipe == env.z3_install(env.Z3_PREFIX),
           "the provisioner's recipe is the one the bootstrap composes")
    argv = recipe[0]
    ensure(argv[:3] == ("uv", "pip", "install") and "--no-build" in argv
           and "--require-hashes" in argv,
           f"the recipe refuses source builds and unhashed wheels, got {argv}")
    ensure(argv[argv.index("--target") + 1] == str(env.Z3_PREFIX)
           and argv[argv.index("-r") + 1] == str(env.Z3_REQUIREMENTS)
           and env.Z3_REQUIREMENTS.is_absolute(),
           "the recipe installs the checkout's requirements into the pinned prefix")
    ensure(env.z3_install(Path("/private/z3"), "/usr/bin/python3")[0][-6:-2]
           == ("--python", "/usr/bin/python3", "--target", str(Path("/private/z3"))),
           "a caller names its own interpreter and prefix")
    text = env.Z3_REQUIREMENTS.read_text(encoding="utf-8")
    logical = [line.strip() for line in text.replace("\\\n", " ").splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    ensure(len(logical) == 1, f"one requirement and nothing else, got {logical}")
    fields = logical[0].split()
    ensure(fields[0] == f"z3-solver=={env.Z3_VERSION}.0",
           f"the wheel pin is Z3_VERSION's release, got {fields[0]}")
    hashes = fields[1:]
    ensure(len(hashes) == 2 and len(set(hashes)) == 2
           and all(re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", item) for item in hashes),
           f"one SHA-256 per guest architecture, got {hashes}")


def _install_recipes_compose() -> None:
    """A recipe is argv and the sentence is composed from it, never the other way.

    Two readers share each of these, a message that names an absent switch and the
    provisioner that stands one up, and the point of the hoist is that they cannot
    come to disagree. What is held is that the sentence still reads as one a person
    can paste, and that the prover's version reaches both halves of its own recipe.
    """
    line = env.install_line(env.ROCQ_INSTALL)
    ensure(line.startswith(f"opam switch create {env.ROCQ_SWITCH} "),
           f"the recipe opens by creating the switch, said {line!r}")
    ensure(" && " in line, "two steps compose into one line a person can paste")
    for recipe, lock, package in (
            (env.ROCQ_INSTALL, "rocq.lock", f"rocq-core.{env.ROCQ_VERSION}"),
            (env.SAIL_INSTALL, "sail.lock", f"sail.{env.SAIL_VERSION}")):
        ensure("--no-switch" in recipe[0], "provisioning must preserve the active switch")
        ensure(recipe[1][:3] == ("opam", "switch", "import"),
               "provisioning must restore the complete tested package closure")
        path = Path(recipe[1][3])
        ensure(path == env.OPAM_LOCKS / lock and path.is_absolute(),
               "the snapshot belongs to this checkout regardless of the caller's cwd")
        snapshot = path.read_text(encoding="utf-8")
        ensure(f'"{package}"' in snapshot,
               f"{lock} must contain the configured package pin {package}")
        ensure(f'"ocaml-base-compiler.{env.OCAML_VERSION}"' in snapshot,
               f"{lock} must contain the configured compiler pin")
    ensure(env.install_line(()) == "", "no steps compose to no sentence")
    spaced = ("opam", "switch", "import", "/a checkout/rocq.lock", "--switch=proofs")
    ensure(tuple(shlex.split(env.install_line((spaced,)))) == spaced,
           "a printed install recipe must preserve a checkout path containing spaces")


def _run_git(cwd: Path, *args: str, overlay: dict[str, str] | None = None) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          encoding="utf-8", errors="replace", check=False, timeout=60,
                          env=None if overlay is None else {**os.environ, **overlay})
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} exited {done.returncode}: "
                           f"{done.stderr.strip()}")
    return done.stdout.strip()


# What cmake asks git at configure, verbatim from model/cmake/project_version.cmake.
_DESCRIBE = ("describe", "--tags", "--always", "--dirty", "--broken")


@contextmanager
def _committed_checkout() -> Iterator[Path]:
    """A throwaway checkout with one commit and a subdirectory to ask from.

    The subdirectory is the whole point rather than scenery: cmake runs its
    `git describe` in `model/cmake`, its own `WORKING_DIRECTORY`, so the child asking
    about the revision never stands at the root of the tree it is asking about. The
    identity is passed per command because a runner with no global `user.email`
    cannot commit at all, and this tree's own configuration is not the subject.
    """
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td).resolve()
        (root / "sub").mkdir()
        (root / "tracked.txt").write_text("one\n", encoding="utf-8", newline="")
        (root / "sub" / "nested.txt").write_text("two\n", encoding="utf-8", newline="")
        _run_git(root, "init", "-q")
        _run_git(root, "add", "-A")
        _run_git(root, "-c", "user.name=vos", "-c", "user.email=vos@example.invalid",
                 "commit", "-q", "-m", "one")
        yield root


def _git_env_names_the_work_tree() -> None:
    """The overlay a lane's configure hands its child, decided by what git answers.

    `GIT_DIR` alone leaves the work tree to the child's own directory, so from the
    directory cmake actually asks in, a clean checkout stamps `-dirty` and `git status`
    reports every tracked path deleted. That marker is what an emulator carries as its
    revision, so always-on is not conservative: it is the state in which a genuinely
    edited lane cannot be told from a clean one.

    The composer is called with the directory rather than reached through `git_env`,
    which reads a checkout and would need a process-global override to be pointed at
    this one; the runner runs modules in a pool, so an override set here is set for
    every module reading the real corpus beside it.
    """
    with _committed_checkout() as root:
        sub, admin = root / "sub", root / ".git"
        alone = _run_git(sub, *_DESCRIBE, overlay={"GIT_DIR": str(admin)})
        ensure(alone.endswith("-dirty"),
               f"precondition: the directory alone reads the child's own tree, so a "
               f"clean checkout stamps dirty, got {alone!r}")
        deleted = _run_git(sub, "status", "--porcelain",
                           overlay={"GIT_DIR": str(admin)})
        ensure("D tracked.txt" in deleted and "D sub/nested.txt" in deleted,
               f"precondition: every tracked path reads as deleted against the "
               f"child's own directory, got {deleted!r}")

        overlay = env.git_overlay(admin, root)
        clean = _run_git(sub, *_DESCRIBE, overlay=overlay)
        ensure(clean == alone.removesuffix("-dirty"),
               f"the overlay must report the clean checkout clean, got {clean!r} "
               f"against {alone!r} from {overlay}")
        # accurate rather than merely switched off: an edited lane still says so
        (root / "tracked.txt").write_text("edited\n", encoding="utf-8", newline="")
        edited = _run_git(sub, *_DESCRIBE, overlay=overlay)
        ensure(edited.endswith("-dirty"),
               f"an edited checkout must stamp dirty, got {edited!r}")
        ensure(set(overlay) == {"GIT_DIR", "GIT_WORK_TREE"},
               f"and it says so by naming the tree as well as the directory, "
               f"got {sorted(overlay)}")


def _git_env_is_empty_where_nothing_needs_saying() -> None:
    # The primary worktree, and the host where the pointer is already usable: an
    # overlay there would be a claim about a tree git's own discovery already finds.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td).resolve()
        (root / ".git").mkdir()
        with_env("VOS_GIT_DIR", None, lambda: ensure(
            env.git_env(root) == {},
            f"a .git directory needs no overlay, got {env.git_env(root)}"))


def _opam_env_answers_no_question() -> None:
    """`opam env`, which every toolchain load runs with its output captured, reads no
    standard input and inherits no answer from the caller's environment, in any case
    the caller names it, so a format upgrade it would ask about is declined rather than
    left on a prompt the caller cannot see or answered by the caller's settings; the
    rest of the environment, the root among it, is passed on, and what it prints is
    applied."""
    answers = {"OPAMYES": "1", "OpamConfirmLevel": "unsafe-yes", "OPAMROOT": "/elsewhere"}
    printed = "OPAMSWITCH='verifiedos-sail'; export OPAMSWITCH;\n"
    with (patch.dict(os.environ, answers),
          patch.object(env, "shutil", SimpleNamespace(which=lambda name: f"/usr/bin/{name}")),
          patch.object(env.subprocess, "run",
                       return_value=subprocess.CompletedProcess(["opam"], 0, printed)) as run):
        env._apply_opam_env()
        applied = os.environ.get("OPAMSWITCH")
    passed = run.call_args.kwargs.get("env") or {}
    ensure(run.call_args.args[0][:2] == ["opam", "env"]
           and run.call_args.kwargs.get("stdin") is subprocess.DEVNULL,
           f"opam env's standard input is closed: {run.call_args}")
    ensure(not {key.upper() for key in passed} & set(env.OPAM_ANSWERS)
           and passed.get("OPAMROOT") == "/elsewhere",
           f"opam env is passed no answer and keeps the root: {sorted(passed)}")
    ensure(applied == "verifiedos-sail", f"what opam env prints is applied: {applied!r}")


# Both readings of `load` mutate the process they run in, the full one raising the
# stack limit, applying the opam switch and moving PATH, so each is asked in a child:
# done in the runner's own process, a case here would prepare a toolchain for every
# module in the pool beside it.
_LOAD_PROBE = """
import json
import os
import resource
import sys

from vos import env

before = dict(os.environ)
stack = resource.getrlimit(resource.RLIMIT_STACK)[0]
env.load(toolchain=(sys.argv[1] == "full"))
added = sorted(set(os.environ) - set(before))
print(json.dumps({
    "added": added,
    "opam": [n for n in added if n.startswith(("OPAM", "OCAML", "CAML"))],
    "path_moved": os.environ["PATH"] != before["PATH"],
    "stack_raised": resource.getrlimit(resource.RLIMIT_STACK)[0] != stack,
}))
"""


def _load_probe(which: str) -> dict[str, object]:
    done = subprocess.run([sys.executable, "-c", _LOAD_PROBE, which],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=120,
                          env={**os.environ, "PYTHONPATH": str(TOOLS)})
    ensure(done.returncode == 0,
           f"the {which} load must answer, got {done.returncode} and "
           f"{done.stderr[-400:]!r}")
    return dict(json.loads(done.stdout))


def _host_lane_reading_drives_no_toolchain() -> None:
    """`load(toolchain=False)` skips the three preparations on the machine that has them.

    The guard used to be the win32 refusal's arm, so the promise was true exactly where
    nothing could check it and false where a `host_ok` subcommand actually pays for it:
    inside the guest, a question about a JSON file raised the OCaml stack, shelled out
    for the opam switch and announced an absent solver prefix first. The full reading is
    run beside it so this is a difference and not an assertion about a machine that
    happens to have no opam.
    """
    lean = _load_probe("lean")
    ensure(lean["path_moved"] is False and lean["stack_raised"] is False
           and lean["opam"] == [],
           f"the host-lane reading must leave PATH and the stack limit alone and "
           f"apply no opam environment, got {lean}")

    full = _load_probe("full")
    ensure(full["path_moved"] is True and full["stack_raised"] is True
           and full["opam"] != [],
           f"precondition: the full reading does all three on this machine, or the "
           f"case above decides nothing, got {full}")


def cases() -> list[Case]:
    return [
        # host-only because on the guest load() would not refuse, it would load
        Case("refuses-win32", _refuses_win32, lane="host"),
        Case("hoisted-lane-constants", _hoisted_lane_constants),
        Case("install-recipes-compose", _install_recipes_compose),
        Case("oracle-tree-keys-the-edition", _oracle_tree_keys_the_edition),
        Case("solver-install-is-hashed", _solver_install_is_hashed),
        Case("lane-shapes", _lane_shapes),
        Case("lane-override", _lane_override),
        Case("lane-roots-compose", _lane_roots_compose),
        Case("mount-type-reads-the-table", _mount_type_reads_the_table),
        Case("jobs-arithmetic", _jobs_arithmetic),
        Case("jobs-env-reads", _jobs_env_reads),
        Case("proof-jobs-use-phase-resources", _proof_jobs_use_phase_resources),
        Case("kernel-budget-holds-the-recorded-peaks", _kernel_budget_holds_the_recorded_peaks),
        Case("toolchain-jobs-use-resources", _toolchain_jobs_use_resources),
        Case("memory-reading-distinguishes-exhaustion",
             _memory_reading_distinguishes_exhaustion_from_unknown),
        Case("keepalive-hours-reads", _keepalive_hours_reads),
        Case("keepalive-pidfile-read", _keepalive_pidfile_read),
        Case("git-env-names-the-work-tree", _git_env_names_the_work_tree),
        Case("git-env-empty-where-nothing-needs-saying",
             _git_env_is_empty_where_nothing_needs_saying),
        Case("opam-env-answers-no-question", _opam_env_answers_no_question),
        # toolchain-only, for the reason the first case here is host-only and the other
        # way round: on win32 load() refuses before it reaches the guard under test, and
        # on a guest with no opam switch the full reading has nothing to apply, so its
        # precondition fails about the machine rather than deciding about the guard
        Case("host-lane-reading-drives-no-toolchain",
             _host_lane_reading_drives_no_toolchain, lane="toolchain"),
    ]
