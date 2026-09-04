# SPDX-License-Identifier: Apache-2.0
"""The build environment's host-testable seams.

`vos/env.py` runs its loops in the guest, but it is imported on both lanes, so what
is held here is everything that must be true before a loop starts: the module
imports cleanly on win32 and `load()` refuses the lane by name, `_lane` derives the
lane from the checkout's `.git` shape, `_jobs` sizes from cores under the memory
guard, and the overrides wave 1 moved to validated call-time reads take effect when
set after the import, which is the hook a test like this one stands on.

One case here runs real `git` over a throwaway checkout rather than reading a
function's return, because what `git_env` is for is a *child's* answer: the overlay
is correct exactly when the `git describe` cmake runs at configure reports a clean
lane clean and an edited one edited, and no assertion about a dictionary decides that.

One case is guest-only, and it is the arm the host cannot reach at all: `load()` on
win32 returns at the platform refusal before it gets to the preparations, so what
`toolchain=False` skips is decidable only where a toolchain could have been prepared.
"""

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

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
        ensure(env._lane(root) == "", "a .git directory is the primary lane")

    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        dot_git = root / ".git"
        # a linked worktree: the pointer names a directory under .git/worktrees/,
        # and git on Windows writes it with either separator
        dot_git.write_text("gitdir: C:/repo/.git/worktrees/LaneX\n", encoding="utf-8")
        ensure(env._lane(root) == "lanex",
               f"a worktree pointer must yield its lowercased name, got {env._lane(root)!r}")
        dot_git.write_text("gitdir: C:\\repo\\.git\\worktrees\\Mixed\n", encoding="utf-8")
        ensure(env._lane(root) == "mixed",
               "a backslash pointer must normalize before it is parsed")
        # a submodule's .git is a file too, pointing into .git/modules/ instead,
        # which is why the parent component and not the file kind decides
        dot_git.write_text("gitdir: ../../.git/modules/sub\n", encoding="utf-8")
        ensure(env._lane(root) == "", "a submodule pointer is not a lane")
        dot_git.write_text("not a pointer at all\n", encoding="utf-8")
        ensure(env._lane(root) == "", "a .git file with no gitdir: line is not a lane")


def _lane_override() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        with_env("VOS_LANE", " MyLane ", lambda: ensure(
            env._lane(root) == "mylane",
            "VOS_LANE set after import must win, stripped and lowercased"))
        with_env("VOS_LANE", "", lambda: ensure(
            env._lane(root) == "",
            "an empty VOS_LANE names the primary lane explicitly"))


def _jobs_arithmetic() -> None:
    # cpus+2 with 2 GB reserved for the generated unit and 512 MB per other job:
    # inert at the default VM size, binding under a shrunken one.
    ensure(env._jobs(12, 15700) == 14, "at 15.7 GB the guard is inert: cpus+2")
    ensure(env._jobs(12, 4096) == 4, "under a 4 GB cap the guard binds: (4096-2048)//512")
    ensure(env._jobs(4, 0) == 6, "with no memory figure the guard cannot bind")
    ensure(env._jobs(1, 2560) == 1, "the guard floors at one job, never zero")
    ensure(env._jobs(2, 2048) == 4, "at exactly 2048 MB the guard does not engage")


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
    ensure(env.SAIL_SWITCH == "default",
           f"the Sail switch is opam's own default, got {env.SAIL_SWITCH!r}")
    ensure(env.ROCQ_SWITCH == "rocq-9.1.1",
           f"the prover switch carries its pin in its name, got {env.ROCQ_SWITCH!r}")
    with_env("VOS_BUILD_ROOT", None, lambda: ensure(
        str(env.build_root()).replace("\\", "/") == "/root/build",
        f"the build root is where every lane's tree lives, got {env.build_root()}"))
    with_env("VOS_BUILD_ROOT", "/root/build-elsewhere", lambda: ensure(
        str(env.build_root()).replace("\\", "/") == "/root/build-elsewhere",
        "VOS_BUILD_ROOT set after import must win, like every other override here"))


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
    ensure(f"rocq-core.{env.ROCQ_VERSION}" in line,
           f"the prover is asked for at its pin, said {line!r}")
    ensure(env.install_line(env.SAIL_INSTALL)
           == f"opam install -y --switch=default sail.{env.SAIL_VERSION}",
           f"the Sail install spells the pin M0.2 found is dropped without it, said "
           f"{env.install_line(env.SAIL_INSTALL)!r}")
    ensure(env.install_line(()) == "", "no steps compose to no sentence")


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
        Case("lane-shapes", _lane_shapes),
        Case("lane-override", _lane_override),
        Case("jobs-arithmetic", _jobs_arithmetic),
        Case("jobs-env-reads", _jobs_env_reads),
        Case("keepalive-hours-reads", _keepalive_hours_reads),
        Case("keepalive-pidfile-read", _keepalive_pidfile_read),
        Case("git-env-names-the-work-tree", _git_env_names_the_work_tree),
        Case("git-env-empty-where-nothing-needs-saying",
             _git_env_is_empty_where_nothing_needs_saying),
        # guest-only for the reason the first case here is host-only, and the other way
        # round: on win32 load() refuses before it reaches the guard under test
        Case("host-lane-reading-drives-no-toolchain",
             _host_lane_reading_drives_no_toolchain, lane="guest"),
    ]
