# SPDX-License-Identifier: Apache-2.0
"""The build environment's host-testable seams.

`vos/env.py` runs its loops in the guest, but it is imported on both lanes, so what
is held here is everything that must be true before a loop starts: the module
imports cleanly on win32 and `load()` refuses the lane by name, `_lane` derives the
lane from the checkout's `.git` shape, `_jobs` sizes from cores under the memory
guard, and the overrides wave 1 moved to validated call-time reads take effect when
set after the import, which is the hook a test like this one stands on.
"""

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from tests.harness import Case, ensure
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


def _with_env(name: str, value: str | None, fn: Callable[[], None]) -> None:
    """Run `fn` with one environment override in place, restoring whatever stood."""
    was = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        fn()
    finally:
        if was is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = was


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
        _with_env("VOS_LANE", " MyLane ", lambda: ensure(
            env._lane(root) == "mylane",
            "VOS_LANE set after import must win, stripped and lowercased"))
        _with_env("VOS_LANE", "", lambda: ensure(
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
    _with_env("VOS_JOBS", "7", lambda: ensure(
        env._jobs(12, 15700) == 7, "VOS_JOBS set after import must win"))
    _with_env("VOS_JOBS", "junk", lambda: _expect_exit(
        lambda: env._jobs(12, 15700), "VOS_JOBS", "garbage VOS_JOBS"))
    _with_env("VOS_JOBS", "0", lambda: _expect_exit(
        lambda: env._jobs(12, 15700), "not a positive count", "zero VOS_JOBS"))
    _with_env("VOS_JOBS", "-3", lambda: _expect_exit(
        lambda: env._jobs(12, 15700), "not a positive count", "negative VOS_JOBS"))


def _keepalive_hours_reads() -> None:
    _with_env("VOS_KEEPALIVE_HOURS", None, lambda: ensure(
        env.keepalive_hours() == 8, "unset, the lease defaults to eight hours"))
    _with_env("VOS_KEEPALIVE_HOURS", "3", lambda: ensure(
        env.keepalive_hours() == 3, "VOS_KEEPALIVE_HOURS set after import must win"))
    _with_env("VOS_KEEPALIVE_HOURS", "0", lambda: ensure(
        env.keepalive_hours() == 0, "zero is valid and turns the lease off"))
    _with_env("VOS_KEEPALIVE_HOURS", "soon", lambda: _expect_exit(
        env.keepalive_hours, "VOS_KEEPALIVE_HOURS", "garbage VOS_KEEPALIVE_HOURS"))


def _keepalive_pidfile_read() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        override = Path(td) / "lease.pid"
        _with_env("VOS_KEEPALIVE_PIDFILE", str(override), lambda: ensure(
            env._keepalive_pidfile() == override,
            "VOS_KEEPALIVE_PIDFILE set after import must name the test's file"))
    _with_env("VOS_KEEPALIVE_PIDFILE", None, lambda: ensure(
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
    _with_env("VOS_Z3_BIN", None, lambda: ensure(
        str(env.Z3_PREFIX / "bin").replace("\\", "/") == "/root/z3-5.1.0/bin",
        f"the pinned solver's prefix must compose to the unpacked one, got "
        f"{env.Z3_PREFIX}"))
    ensure(env.SAIL_SWITCH == "default",
           f"the Sail switch is opam's own default, got {env.SAIL_SWITCH!r}")
    ensure(env.ROCQ_SWITCH == "rocq-9.1.1",
           f"the prover switch carries its pin in its name, got {env.ROCQ_SWITCH!r}")
    _with_env("VOS_BUILD_ROOT", None, lambda: ensure(
        str(env.build_root()).replace("\\", "/") == "/root/build",
        f"the build root is where every lane's tree lives, got {env.build_root()}"))
    _with_env("VOS_BUILD_ROOT", "/root/build-elsewhere", lambda: ensure(
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
    ]
