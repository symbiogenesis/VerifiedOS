#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The lane this repository builds in, stated as an executable fact list.

Every loop here runs against a machine that is a particular thing: two opam switches
for the model and the prover, two more for the Gallina front, a pinned solver ahead of
the distribution's, two pinned checkers, and an interpreter floor. Nothing wrote that
down as anything a machine could act on, so standing the lane up anywhere else was a
reading of prose scattered across a plan, a README and half a dozen modules. This is
that list, one row per fact, each row naming the loop that wants it, the artifact that
owns it, a probe that says what is actually there, and the command that would put it
there.

**It reads its facts rather than restating them.** Every version, switch name and pin
below is imported from the module or the document that fixes it, so this file is a
table of *rows* and not a second copy of the tree's pins. The one figure written here
as a literal is the interpreter floor; K-75 holds this explicit restatement against
`tools/ty.toml`. Python packages are synchronized from tools/uv.lock before dispatch,
so their rows probe the settled environment and carry no separate install recipes.

**Native rather than containerized, which is what makes it arch-agnostic.** I8's
exclusion was that the prover's published image is amd64-only; an opam build from
source is not, and neither is the pinned solver, which arrives as a manylinux wheel
built for both architectures. This box is aarch64 and a hosted runner is amd64, and one
fact list serves both.

**What it does not reach is named rather than absorbed.** I1's two standing clauses are
`[experimental] autoMemoryReclaim` in `%USERPROFILE%\\.wslconfig`, which is global to
every distribution and permanent until a human deletes it, and the Remote-WSL working
posture, which is a setting on a person's editor. Neither is in this tree and no
provisioner reaches either, so both are printed as not reached and neither is counted
into the verdict. It is the same boundary [vos/env.py](../env.py) already draws around
the idle timer.

**A row installs only what an artifact here states as a command.** Two routes have
owners this file cannot import as an argument vector: uv's own installation, and the
CertiRocq oracle's switch, whose recipe lives in
[tools/wasm-oracle/README.md](../../wasm-oracle/README.md) as prose for a person.
Inventing a command for either would be the unowned derived fact the working rules
refuse, so their rows, `uv` and the oracle switch, report and plan nothing. Other rows
carry no command for reasons of their own, among them the interpreter floor, which is
the interpreter taking the probe and which nothing it runs can replace, and the cache
invariant, whose repair is to give a lane a copy rather than to delete somebody's warm
cache. The `opam` row's command installs the reviewed client by the route guest
bootstrap takes, only on a machine with no client on PATH, and creates a root by the
root-creation route bootstrap runs, `opam_client.CREATE_ROOT`, only where no root
stands, so the switch recipes planned after it in one pass find a root. The rows ahead
of it probe and install the distribution packages that route needs,
`opam_client.ROOT_PREREQUISITES`, and the command refuses, naming each one absent,
rather than start a root `opam init` would refuse to create. It alters
nothing that exists but a root in the shape that route leaves after its leading steps,
which `opam_client.root_resumable` recognizes and the route's remaining steps,
`opam_client.remaining_route`, complete by adding the owner's remaining repositories
unselected, without running `opam init` over it. Replacing a developer's client,
or installing one where none stands over a root in a format older than the reviewed
client writes, can upgrade that root's format one way, which is a recorded step rather
than a repair, so a client at another release and a missing client over an older root
are reported and never planned, and neither is any other standing root with a gap
`opam_client.root_gaps` names: no stated format or one newer than the reviewed client
writes, or an owned repository absent, at another URL or with its stamp unread. While a
root stands in an older format, no switch row plans its recipe either, because the
reviewed client rewrites that root one way at its first write, or at its first read
where the upgrade cannot be made in memory, and where opam lists no switch without
upgrading that root, a switch row reports one the root's config lists as unread rather
than absent; nor does a switch row plan its recipe while a client at another release
is on PATH, which would build the switch as a client this tree has not reviewed. Every
figure any document states about this
table is a count over `FACTS`, held by K-24 rather than by care.

    python tools/run.py provision                # what is here and what is not
    python tools/run.py provision --apply        # and install what is not
    python tools/run.py provision --only gate    # the rows the host gates alone want
    python tools/run.py provision --install-opam # the opam row's command alone

Exit 0 clean, 1 on any absent fact, which is the convention every tool here keeps.
"""

import argparse
import contextvars
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from importlib import metadata
from pathlib import Path

from vos import cli, env, gallina, opam_client
from vos.cli import quickchick, rtl, typecheck
from vos.corpus import find_root
from vos.report import Reporter

# K-75 holds this probe's floor against the checker targets and project requirement.
INTERPRETER_FLOOR = "3.14"

# The bound a probe must answer within. Every one of these is a version query or a
# directory listing, so a run that reaches this is hung rather than slow, and a hung
# probe has to become a finding rather than a command that never returns.
TIMEOUT = 60

# How this lane installs a distribution package. The route is stated once here, and it
# is the provisioner's own: no artifact in this tree owned the apt prerequisite set
# before this file did, which is why every row below names a consumer already in the
# tree and a row that cannot name one is not written.
APT: tuple[str, ...] = ("apt-get", "install", "-y")

# Where the opam row's command puts the reviewed client on a machine with none: ahead
# of /usr/bin on a Debian or Ubuntu PATH, where opam's own installer puts a client.
OPAM_DESTINATION = Path("/usr/local/bin/opam")

# The two groups, and what separates them. `gate` is what the three host gates and the
# tools' own tests want and nothing more, which is the split I8 already drew between
# quick checks and canonical ones; `toolchain` is everything a model, RTL, oracle or
# prover loop drives. The split is a narrowing rather than a schedule: nothing here
# decides what runs where, S14 having declined the workflow that would have, so this
# makes the question askable and leaves it open.
GATE = "gate"
TOOLCHAIN = "toolchain"
GROUPS: tuple[str, ...] = (GATE, TOOLCHAIN)

# What no provisioner reaches, printed at the end of a run and counted into nothing.
NOT_REACHED: tuple[tuple[str, str], ...] = (
    ("[experimental] autoMemoryReclaim in %USERPROFILE%\\.wslconfig",
     "global to every distribution and permanent until a human deletes it, which is "
     "the boundary vos/env.py draws around the idle timer beside it"),
    ("the Remote-WSL working posture",
     "a setting on a person's editor rather than a fact of any machine, and the one "
     "that decides which side of the OS boundary the checkout sits on; the placement "
     "rule tools/README.md states reads the same either way"),
)


@dataclass(frozen=True)
class Found:
    """What a probe saw: whether the fact holds, and the answer it actually got.

    `saw` is what was there rather than a restatement of what was wanted, so a wrong
    version reports the number it read and an absent thing reports where it looked.
    Reporting absent what is present is the one failure a pinned-version gate must not
    have, which is [typecheck.py](typecheck.py)'s own words about the same hazard; a
    probe that reports *present* on a wrong version is the other half of it.

    `repairable` is false where the row's command must not run over what the probe
    found, as the opam row's installs a client only where none is on PATH and no root
    stands in a format older than that client's, and creates a root only where none
    stands or completes one in the shape its route leaves after its leading steps.
    """

    present: bool
    saw: str
    repairable: bool = True


@dataclass(frozen=True)
class Fact:
    """One thing this lane is, and what would make a machine be it.

    `install` is the argument vectors that would satisfy the fact, in order, and it is
    empty where no artifact here states a command. A fact with no command still probes
    and still fails a run: what it cannot do is repair itself.
    """

    name: str
    group: str
    needs: str
    owner: str
    probe: Callable[[], Found]
    install: tuple[tuple[str, ...], ...] = ()


def _say(argv: Sequence[str]) -> str:
    """One probe's subprocess, reduced to its standard output.

    Standard output alone, and that is the load-bearing part: opam prints
    `[WARNING] Running as root is not recommended` on standard error, so every switch
    probe below would otherwise read that warning as an answer about a package. A
    command that is absent, that fails, or that does not answer inside the bound comes
    back empty and its caller reports it as absent.

    No standard input either, and the environment `env.declining_environment` gives, so
    a probe never answers a question. opam asks before it writes a root-format upgrade,
    yes by default, and a read such as `opam switch list` writes one where the upgrade
    cannot be done in memory. A probe reading the caller's terminal would wait there,
    its question captured out of sight, and an empty line would answer yes, as would
    the caller's own `env.OPAM_ANSWERS`; without either, opam declines and exits.
    """
    try:
        done = subprocess.run(list(argv), capture_output=True, encoding="utf-8",
                              errors="replace", check=False, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL, env=env.declining_environment())
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


# A version inside whatever else a tool prints around it. Dotted rather than merely
# numeric, and that is load-bearing: `Z3 version 5.1.0 - 64 bit` opens with a digit
# inside the tool's own name, and a pattern reading the first number would answer 3.
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)+")


def _number(text: str) -> str:
    """The dotted version in a tool's own greeting, empty where it states none.

    `Z3 version 5.1.0 - 64 bit`, `Verilator 5.032 2025-01-01 rev (Debian 5.032-1)` and
    a bare `0.20.3` from opam are the three shapes this reads, and `0.9.1+9.1` reduces
    to the part before opam's own build suffix.
    """
    found = _NUMBER_RE.search(text)
    return found.group(0) if found else ""


@dataclass
class _Asked:
    """What one `take` asks once for every row it probes: the opam client on PATH and
    the release it answers, unasked until a row first wants it."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    client: tuple[str | None, str] | None = None


# The `_Asked` of the `take` this probe runs under, and none outside a `take`.
_ASKED: contextvars.ContextVar[_Asked | None] = contextvars.ContextVar("provision_asked",
                                                                      default=None)


def _client() -> tuple[str | None, str]:
    """Where the opam client on PATH is and the release `_release` reads from its
    answer, empty where it answers none, or no path and no release where no client is on
    PATH.

    Asked once per `take`, so the opam row and every switch row read one answer and the
    client is run once for all of them; a probe outside a `take` asks afresh."""
    asked = _ASKED.get()
    if asked is None:
        return _ask_client()
    with asked.lock:
        if asked.client is None:
            asked.client = _ask_client()
        return asked.client


def _ask_client() -> tuple[str | None, str]:
    where = shutil.which("opam")
    return where, _release(_say(("opam", "--version"))) if where else ""


def _release(text: str) -> str:
    """The release an opam client's `--version` answers, read exactly: its first
    whitespace-separated word, empty where it answers nothing.

    opam prints its release bare, and a prerelease or build suffix such as `~beta1` or
    `+dev` is part of it, so a prerelease or a development build of the reviewed release
    is another client than that release rather than the dotted number `_number` would
    reduce it to."""
    words = text.split()
    return words[0] if words else ""


def _floor() -> tuple[int, ...]:
    return tuple(int(part) for part in INTERPRETER_FLOOR.split("."))


def _interpreter() -> Found:
    """The running interpreter against the floor this directory is written to.

    At or above rather than equal: the floor is what the two checkers admit and what
    every module here may say, and a later interpreter satisfies both. The host and the
    guest are held at one version by decision rather than by this probe, which is
    [tools/README.md](../../README.md)'s sentence and not a fact a machine can enforce.
    """
    want = _floor()
    # named rather than sliced off `sys.version_info`, whose tail carries a release
    # level that is a string: a slice of it is not a tuple of numbers to compare
    running = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    return Found(running[:len(want)] >= want,
                 ".".join(str(part) for part in running))


def _on_path(name: str) -> Found:
    where = shutil.which(name)
    return Found(where is not None, where or f"no {name} on PATH")


def _both_on_path(first: str, second: str) -> Found:
    """Two executables one preference wants together, because half of a C and C++ pair
    is not a compiler choice: `env._compiler_args` passes clang for both or neither."""
    where = [name for name in (first, second) if shutil.which(name) is None]
    if where:
        return Found(False, f"no {' and no '.join(where)} on PATH")
    return Found(True, _number(_say((first, "--version"))) or "present")


def _at_version(argv: Sequence[str], pin: str) -> Found:
    found = _number(_say(argv))
    return Found(found == pin, found or f"{argv[0]} answered with no version")


def _checker(name: str, pin: str) -> Found:
    """Probe the environment-local checker selected by the gate."""
    exe = typecheck._tool(name)
    if exe is None:
        return Found(False, f"no {name} in this interpreter's environment")
    try:
        found = typecheck._version(exe)
    except (OSError, subprocess.SubprocessError):
        return Found(False, f"{exe} could not be asked its version")
    return Found(found == pin, f"{found} at {exe}")


def _verilator() -> Found:
    """Probe the same project-local simulator that every RTL loop selects."""
    binary = rtl._verilator()
    if binary is None:
        return Found(False, "no project Verilator or verilator on PATH")
    return _at_version((binary, "--version"), rtl.VERILATOR_PIN)


def _importable(module: str, distribution: str) -> Found:
    """A library this directory imports, in the environment the interpreter and ty both
    resolve against. Presence is the import path and the number is the distribution's
    metadata, because those are two questions: a package ty cannot resolve is an
    unresolved-import whatever its metadata says.
    """
    if importlib.util.find_spec(module) is None:
        return Found(False, f"no {module} in the environment this interpreter resolves "
                            "against")
    try:
        return Found(True, f"{module} {metadata.version(distribution)}")
    except metadata.PackageNotFoundError:
        return Found(True, f"{module} present, at a version its metadata does not state")


def switches() -> tuple[str, ...]:
    """Every opam switch this machine carries, empty where it carries no opam at all.

    Public because the tools' test runner asks the same question: a case marked for the
    toolchain lane runs only where the Sail switch stands, and that is decided here
    rather than by a second probe, on the ground `_installed` states for the switch
    probes, that the question is what a run would compile against."""
    return tuple(line.strip()
                 for line in _say(("opam", "switch", "list", "--short")).splitlines()
                 if line.strip())


def _installed(switch: str, package: str) -> str:
    """The version one switch carries a package at, empty where it carries none. Asked
    of opam rather than of the filesystem, because the question is what a run would
    compile against and that is the switch's answer and not a directory's."""
    return _say(("opam", "list", "--switch", switch, "--installed", "--short",
                 "--columns=version", package))


def _switch_at(switch: str, package: str, pin: str) -> Found:
    """A switch carrying one package at the version an owner in this tree fixes.

    Not repairable where `--apply` would build the switch over a root the reviewed
    client rewrites, or as a client this tree has not reviewed. While the opam root
    stands in a format older than the reviewed client's, that client rewrites it one way
    at its first write, or at its first read where the upgrade cannot be made in memory,
    the deliberate, recorded step `_opam_client` reports. While a client at another
    release is on PATH, that client would build the switch, and a Sail switch names the
    client that built it in its version string. Where no client is on PATH the switch
    stays repairable, because the opam row ahead of it installs the reviewed client in
    the same pass."""
    older = _older_root()
    found = _switch_found(switch, package, pin, older=bool(older))
    if found.present:
        return found
    if older:
        return Found(False, f"{found.saw}; {older}, so no switch is planned over it",
                     repairable=False)
    where, version = _client()
    if where is not None and version != opam_client.OPAM_VERSION:
        return Found(False, f"{found.saw}; opam {version or 'answering no version'} at "
                            f"{where} would build it, and the reviewed client is "
                            f"{opam_client.OPAM_VERSION}, so no switch is planned",
                     repairable=False)
    return found


def _switch_found(switch: str, package: str, pin: str, *, older: bool) -> Found:
    """One switch's package at the version opam answers for it.

    Over a root in an older format, where `older` holds, opam lists no switch at all when
    it would have to upgrade the root to read it and declines to. Where it lists none
    there and the root's own config lists this switch, `opam_client.root_switches`, the
    row says opam did not read the switch rather than that the switch is absent."""
    listed = switches()
    if switch not in listed:
        if older and not listed and switch in opam_client.root_switches(env.opam_root()):
            return Found(False, "opam listed no switches without upgrading the root, whose "
                                f"config lists the {switch} switch")
        return Found(False, f"opam has no {switch} switch")
    found = _installed(switch, package)
    if not found:
        return Found(False, f"the {switch} switch carries no {package}")
    return Found(found == pin, f"{package} {found} in {switch}")


def _older_root() -> str:
    """Where the opam root stands in a format older than the reviewed client's, what that
    client does to it, as a clause; empty where no root stands or its format is not
    older."""
    root = env.opam_root()
    fmt = opam_client.root_format(root)
    if not (opam_client.root_exists(root) and opam_client.older_than_reviewed(fmt)):
        return ""
    return (f"the reviewed client {opam_client.OPAM_VERSION} rewrites the opam root at "
            f"{root} from format {fmt} to {opam_client.OPAM_ROOT_FORMAT} one way at its "
            "first write, or at its first read where the upgrade cannot be made in "
            "memory, a deliberate, recorded step rather than a repair")


def _moving_the_root(fmt: str) -> str:
    """What moving a root of format `fmt` to the reviewed client does to it, as a clause,
    empty where the root is already in that client's format, states none, or states a
    newer one, which the root's gaps already report."""
    if not opam_client.older_than_reviewed(fmt):
        return ""
    return (f", and moving to it upgrades this root's format from {fmt} to "
            f"{opam_client.OPAM_ROOT_FORMAT} one way, a deliberate, recorded step rather "
            "than a repair")


def _opam_client() -> Found:
    """The opam client on PATH against the reviewed release, and its root against the
    one the owner's root-creation route makes.

    The fact is the client's release and the root's completeness: a root stands where
    its `config` does, and is complete where `opam_client.root_gaps` names nothing, a
    format stated and no newer than the reviewed client writes and each of
    `OPAM_REPOSITORIES` at its URL with its stamp read, because every switch recipe
    fails in a root that does not stand or that the client refuses to write to, and the
    prover's fails without its repository. The rest is what a
    reader needs to act on it: where the client and its root are, the root's format,
    and each repository's URL and metadata stamp, which the locks do not fix. The root
    is read from its files rather than through opam, because a client newer than the
    root's format upgrades the root to answer.

    Repairable only where `install_opam` can make the row hold without altering what
    exists: the reviewed client, or no client over no root or a root in a format no
    older than the reviewed client's, and no root, a complete one, or one in the shape
    the root-creation route leaves after its leading steps, which that route's
    remaining steps complete. Moving a developer's root to another client can rewrite
    its format one way, which the report says where the root's format is older than the
    reviewed client's, so replacing a client, or installing one where none stands over a
    root in an older format, is a recorded step and not a repair; any other standing
    root the command would leave incomplete is reported rather than planned. The
    reviewed client over a complete root in an older format holds the row, and the
    report says that client rewrites the root one way at its first write, or at its
    first read where the upgrade cannot be made in memory, which is why no switch row
    plans a recipe over it.
    """
    where, found = _client()
    client = f"opam {found or 'answering no version'} at {where}" if where else "no opam on PATH"
    reviewed = found == opam_client.OPAM_VERSION
    root = env.opam_root()
    fmt = opam_client.root_format(root)
    stands = opam_client.root_exists(root)
    gaps = opam_client.root_gaps(root) if stands else []
    resumable = opam_client.root_resumable(root)
    if stands:
        saw = f"{client} over {root} (format {fmt or 'unread'}; {_listing(root)})"
    else:
        saw = f"{client}; no opam root at {root}"
    if gaps:
        saw += f"; the root {' and '.join(gaps)}, {_standing(resumable)}"
    older = stands and opam_client.older_than_reviewed(fmt)
    if not reviewed:
        saw += f"; the reviewed client is {opam_client.OPAM_VERSION}{_moving_the_root(fmt)}"
    elif older:
        saw += (f"; that client rewrites this root from format {fmt} to "
                f"{opam_client.OPAM_ROOT_FORMAT} one way at its first write, or at its "
                "first read where the upgrade cannot be made in memory, a deliberate, "
                "recorded step rather than a repair, so no switch is planned over it")
    return Found(reviewed and stands and not gaps, saw,
                 repairable=(reviewed or (where is None and not older))
                 and (not gaps or resumable))


def _listing(root: Path) -> str:
    """Each repository a root configures with its URL and metadata stamp, as a report
    names them."""
    return ", ".join(f"{repo['name']} {repo['url']} at stamp {repo['stamp'] or 'unrecorded'}"
                     for repo in opam_client.repositories(root)) or "no repositories"


def _standing(resumable: bool) -> str:
    """What becomes of a standing root with gaps, as a clause: completed where it is in
    the shape the root-creation route leaves after its leading steps, and otherwise left
    as it is."""
    if resumable:
        return ("in the shape the root-creation route leaves after its leading steps, "
                "which that route's remaining steps complete")
    return ("and a standing root is left as it is unless it is in the shape the "
            "root-creation route leaves after its leading steps")


def install_opam(destination: Path = OPAM_DESTINATION) -> int:
    """The opam row's command: the reviewed client where no client is on PATH, and a
    root by `opam_client.CREATE_ROOT` where none stands or where one stands in the shape
    that route leaves after its leading steps.

    It installs only what is absent and alters nothing that exists but a root in that
    shape, and it decides every refusal, about the root, the machine and where the
    client would go, before it installs anything, so a run it refuses leaves the
    machine as it found it. A standing root is held to what the row reads: a complete
    one is left as it is, one `opam_client.root_resumable` reads in that shape is
    completed by the route's remaining steps, `opam_client.remaining_route`, which leave
    out `opam init`, and any other the row reads as incomplete is refused whatever the
    client. Where it would run the route, it first holds the machine to
    `opam_client.ROOT_PREREQUISITES` as the rows ahead of this one do, and
    refuses, naming each package absent, because `opam init` refuses to create a root
    without them. A client on PATH at another release is refused, because replacing one
    is the recorded step `_opam_client` describes, and so is installing a client where
    none stands over a root in a format older than the reviewed client's, which that
    client would rewrite one way; a client is installed by
    `opam_client.install`, which verifies the download before publishing it and refuses
    to replace a different file at the destination. Every switch recipe runs `opam` by
    name, so a destination whose directory this PATH does not search is refused before
    the client is installed rather than left to fail at the first switch; a client PATH
    still does not find once installed is reported as that command's failure. A root
    this command creates or completes is held to what guest bootstrap holds its own to,
    the reviewed client's format and exactly the owner's repositories with every stamp
    read.
    """
    root = env.opam_root()
    stands = opam_client.root_exists(root)
    resuming = opam_client.root_resumable(root)
    if stands and not resuming and (gaps := opam_client.root_gaps(root)):
        print(f"the opam root at {root} {' and '.join(gaps)}, {_standing(resuming)}",
              file=sys.stderr)
        return 1
    creating = resuming or not stands
    if creating and (missing := _missing_root_prerequisites()):
        print(f"the root-creation route cannot run at {root} without {', '.join(missing)}, "
              "which dpkg reports absent, since opam init refuses to create a root without "
              "them; the rows ahead of the opam row install them", file=sys.stderr)
        return 1
    present = shutil.which("opam")
    fmt = opam_client.root_format(root)
    if present is None and stands and opam_client.older_than_reviewed(fmt):
        print(f"the opam root at {root} is in format {fmt}, which the reviewed client "
              f"{opam_client.OPAM_VERSION} rewrites to {opam_client.OPAM_ROOT_FORMAT} one "
              "way, after which an earlier client cannot read it; moving this root to the "
              "reviewed client is a deliberate, recorded step, so this command installs no "
              "client over it", file=sys.stderr)
        return 1
    if present is None:
        if not _searched(destination.parent):
            print(f"opam {opam_client.OPAM_VERSION} would be at {destination}, which is not "
                  "on PATH, so no switch recipe could run it; nothing was installed",
                  file=sys.stderr)
            return 1
        try:
            opam_client.install(destination, platform.machine())
        except (OSError, ValueError) as err:
            print(f"the reviewed opam client was not installed at {destination}: {err}",
                  file=sys.stderr)
            return 1
        if shutil.which("opam") is None:
            print(f"opam {opam_client.OPAM_VERSION} is at {destination}, which is not on "
                  "PATH, so no switch recipe can run it", file=sys.stderr)
            return 1
        print(f"installed opam {opam_client.OPAM_VERSION} at {destination}")
    else:
        _, found = _client()
        if found != opam_client.OPAM_VERSION:
            print(f"opam {found or 'answering no version'} is already on PATH at "
                  f"{present}; the reviewed client {opam_client.OPAM_VERSION} is "
                  "installed only where there is none", file=sys.stderr)
            return 1
    if not creating:
        print(f"the opam root at {root} already stands complete")
        return 0
    return _create_root(root, resuming=resuming)


def _searched(directory: Path) -> bool:
    """Whether `directory` is one this process's PATH searches for an executable, read
    as `os.get_exec_path` reads it, so a client installed there is one `opam` by name
    finds where no other client stands ahead of it."""
    try:
        wanted = directory.resolve()
    except OSError:
        return False
    for entry in os.get_exec_path():
        if not entry:
            continue
        try:
            if Path(entry).resolve() == wanted:
                return True
        except OSError:
            continue
    return False


def _missing_root_prerequisites() -> list[str]:
    """Each of `opam_client.ROOT_PREREQUISITES` dpkg does not report installed, read by
    the probe the rows ahead of the opam row take, so the command and the table agree."""
    return [package for package in opam_client.ROOT_PREREQUISITES
            if not _dpkg(package).present]


def _create_root(root: Path, *, resuming: bool = False) -> int:
    """Create the root at `root` by the owner's route, or complete one in the shape the
    route leaves after its leading steps by the steps `opam_client.remaining_route`
    names, which never run `opam init` over it, streamed to the caller's terminal as
    `_apply` streams a switch, and hold it to the reviewed client's format and the
    owner's repositories as guest bootstrap holds its own.

    A step that fails stops the route, and the report says what then stands at `root`
    and what remains of the route: the first step can leave a root behind it, which a
    later run completes where `opam_client.root_resumable` reads it in that shape and
    otherwise leaves as it is.
    """
    steps = opam_client.remaining_route(root)
    if resuming:
        print(f"the opam root at {root} is in the shape the root-creation route leaves "
              "after its leading steps; the route's remaining steps complete it")
    for index, argv in enumerate(steps):
        print(f"   {' '.join(argv)}", flush=True)
        try:
            code = subprocess.run(list(argv), check=False,
                                  env=os.environ | {"OPAMROOT": str(root)}).returncode
        except OSError as err:
            failed = f"`{' '.join(argv)}` could not be run: {err}"
        else:
            if code == 0:
                continue
            failed = f"`{' '.join(argv)}` exited {code}"
        print(f"{failed}, {_stopped(root, steps[index:])}", file=sys.stderr)
        return 1
    try:
        fmt = opam_client.initialized_format(root)
        opam_client.initialized_repositories(root)
    except ValueError as err:
        print(f"the opam root created at {root} is not the owner's: {err}", file=sys.stderr)
        return 1
    print(f"{'finished' if resuming else 'created'} the opam root at {root} in format {fmt}")
    return 0


def _stopped(root: Path, remaining: Sequence[Sequence[str]]) -> str:
    """What stands at `root` once the root-creation route stopped, with what remains of
    the route from the step that failed, as the clause a failure report ends in."""
    left = "; ".join(" ".join(argv) for argv in remaining)
    if not opam_client.root_exists(root):
        return f"so no opam root stands at {root}; what remains of the route is {left}"
    then = ("a later run of this command finishes it" if opam_client.root_resumable(root)
            else "a standing root in this state is left as it is")
    return (f"so the opam root at {root} stands in format "
            f"{opam_client.root_format(root) or 'unread'} with {_listing(root)}; what "
            f"remains of the route is {left}, and {then}")


def _pinned_z3() -> Found:
    """The solver Sail's typechecker discharges its obligations with.

    The one invariant in this lane whose absence is silent: `env._prepend_z3_path`
    warns and continues, so a machine without this prefix typechecks against the
    distribution's own solver and writes that solver's answers into a content-keyed
    cache the pinned one later reads back as its own. That is a difference no later run
    can see, which is why it is a row here rather than a warning in a log.
    """
    exe = env.Z3_PREFIX / "bin" / "z3"
    if not exe.is_file():
        return Found(False, f"{exe} is absent, so a typecheck would answer from the "
                            f"distribution's z3 {env.Z3_DISTRIBUTION} and cache that")
    found = _number(_say((str(exe), "--version")))
    return Found(found == env.Z3_VERSION, f"{found or 'no version'} at {exe}")


def _dpkg(package: str) -> Found:
    """A distribution package, asked of dpkg rather than of a file it happens to drop:
    a development package is headers and a linker name, and no one path is the fact."""
    status = _say(("dpkg-query", "-W", "-f=${Status} ${Version}", package))
    return Found(status.startswith("install ok installed"),
                 status or f"dpkg knows no {package}")


def _caches_unshared() -> Found:
    """I2's rule as a probe rather than as a paragraph: no two lanes share one cache.

    Sail's SMT memo cache is one flat file of 17-byte records, read whole at startup
    and rewritten whole at exit with no lock and no atomic rename. Two writers of one
    file lose each other's records, and a reader arriving mid-rewrite can take Sail's
    invalid path and replace the file with its own entries alone, which I2 measured at
    77,260 of 83,436 records destroyed by a single byte. So a lane copies a warm cache
    on create and never points at one, and what makes that checkable after the fact is
    that every cache under the build root is a file of its own.

    Vacuously true on a machine with no build tree yet, and said so rather than passed
    over. There is no repair argv: the fix for two lanes sharing a cache is to give one
    of them a copy, and a tool that started deleting somebody's warm cache to satisfy
    its own probe would be worse than the finding.
    """
    root = env.build_root()
    if not root.is_dir():
        return Found(True, f"{root} holds no build tree yet, so no cache is shared")
    found = sorted(root.glob(env.TYPECHECK_CACHE)) + sorted(
        root.glob(f"*/{env.TYPECHECK_CACHE}"))
    seen: dict[int, Path] = {}
    shared: list[str] = []
    for path in found:
        node = path.stat().st_ino
        if node in seen:
            shared.append(f"{path} and {seen[node]} are one file")
        seen[node] = path
    if shared:
        return Found(False, "; ".join(shared))
    return Found(True, f"{len(found)} cache(s) under {root}, {len(seen)} distinct "
                       "inode(s), so no two lanes write one file")


def _outputs_on_the_guest() -> Found:
    """The placement rule tools/README.md states, as a probe: every guest output on the
    guest's own persistent filesystem.

    A build tree, a work directory or a log on a mount of the Windows filesystem is
    written across the OS boundary on every call, which vos/env.py's docstring
    measures, and one on tmpfs is gone when the instance idle-terminates. The two roots
    every guest loop writes under are probed, and the checkout is reported beside them
    and never counted: it is read across the boundary by decision, I1 having measured
    the move and refused it, so a probe that failed the lane for it would be failing a
    measurement the plan accepted. There is no repair argv, because where a root sits
    is what `VOS_BUILD_ROOT` and `VOS_LOG_DIR` declare, and the fix for a wrong one is
    to point it back at the guest.
    """
    seen: list[str] = []
    wrong: list[str] = []
    for what, path in (("build root", env.build_root()), ("log root", env.log_root())):
        kind = env.filesystem(path)
        if not kind:
            return Found(False, f"no mount table says where {path} sits, so the {what} "
                                "is undecided")
        seen.append(f"{what} {path} on {kind}")
        if kind in env.CROSS_OS_FILESYSTEMS:
            wrong.append(f"the {what} {path} is on {kind}, a mount of the other OS's "
                         "filesystem, so every guest write there crosses the boundary")
        elif kind in env.VOLATILE_FILESYSTEMS:
            wrong.append(f"the {what} {path} is on {kind}, which does not outlive the "
                         "instance")
    checkout = find_root()
    kind = env.filesystem(checkout)
    if kind in env.CROSS_OS_FILESYSTEMS:
        aside = (f"; the checkout {checkout} is read across the boundary over {kind}, "
                 "the one crossing the layout keeps")
    else:
        aside = f"; the checkout {checkout} is on {kind or 'an unread mount'} beside them"
    if wrong:
        return Found(False, "; ".join(wrong) + aside)
    return Found(True, ", ".join(seen) + aside)


# The lane, row by row. Each row names the loop that wants the fact and the artifact
# that fixes it, and every version in it is read from that artifact rather than typed
# here. The order is the order a machine is built in and the order a report reads in:
# the gate's five, then the toolchain from the opam root's system packages outward, so
# `--apply` installs what `opam init` needs before the opam row's command runs it.
FACTS: tuple[Fact, ...] = (
    Fact("the interpreter floor", GATE,
         "every command here, on both lanes",
         "tools/ty.toml, whose python-version this file restates under K-75",
         _interpreter),
    Fact("uv", GATE,
            "run.py's locked Python environment",
            "tools/pyproject.toml's tool.uv.required-version, enforced by uv at startup",
         partial(_on_path, "uv")),
    Fact("ty", GATE,
         "run.py typecheck",
            f"tools/pyproject.toml's dependency-groups.dev (ty {typecheck.TY_VERSION})",
            partial(_checker, "ty", typecheck.TY_VERSION)),
    Fact("ruff", GATE,
         "run.py typecheck",
            f"tools/pyproject.toml's dependency-groups.dev (ruff {typecheck.RUFF_VERSION})",
            partial(_checker, "ruff", typecheck.RUFF_VERSION)),
    Fact("jsonschema", GATE,
         "run.py model validate-config, and ty on every lane",
            "tools/pyproject.toml's project.dependencies; synchronized by run.py",
            partial(_importable, "jsonschema", "jsonschema")),
    *(Fact(package, TOOLCHAIN,
           "the opam row's root creation, whose opam init refuses to create a root "
           "without it",
           "tools/vos/opam_client.py's ROOT_PREREQUISITES",
           partial(_dpkg, package),
           ((*APT, package),))
      for package in opam_client.ROOT_PREREQUISITES),
    Fact("opam", TOOLCHAIN,
         "every switch below, and vos/env.py's _apply_opam_env",
         "tools/vos/opam_client.py's OPAM_VERSION and OPAM_REPOSITORIES",
         _opam_client,
         (tuple(cli.entry("provision", "--install-opam")),)),
    Fact("the Sail switch", TOOLCHAIN,
         "run.py model typecheck, build, emit and bundle",
         f"tools/vos/env.py's SAIL_SWITCH and SAIL_VERSION (M0.2 pinned {env.SAIL_VERSION})",
         partial(_switch_at, env.SAIL_SWITCH, "sail", env.SAIL_VERSION),
         env.SAIL_INSTALL),
    Fact("the pinned z3", TOOLCHAIN,
         f"Sail's typechecker, ahead of the distribution's {env.Z3_DISTRIBUTION}",
         "tools/vos/env.py's Z3_VERSION and Z3_INSTALL, over the wheel hashes in "
         "tools/z3-requirements.txt",
         _pinned_z3,
         env.Z3_INSTALL),
    Fact("the prover switch", TOOLCHAIN,
         "run.py proofs, and the Stdlib-only Gallina harnesses of run.py quickchick "
         "vectors and freeze, run.py kernel vectors, check and mutants, and run.py seed "
         "coq's enumerative mode",
         "tools/vos/env.py's ROCQ_SWITCH and ROCQ_VERSION",
         partial(_switch_at, env.ROCQ_SWITCH, "rocq-core", env.ROCQ_VERSION),
         env.ROCQ_INSTALL),
    Fact("the CertiRocq oracle switch", TOOLCHAIN,
         "the M1.5 Wasm oracle, and run.py quickchick check and properties where "
         "QuickChick is installed there",
         "tools/vos/gallina.py's ORACLE_SWITCH, its recipe in tools/wasm-oracle/README.md",
         partial(_switch_at, gallina.ORACLE_SWITCH, "rocq-certirocq",
                 gallina.CERTIROCQ_VERSION)),
    Fact("the QuickChick switch", TOOLCHAIN,
         "run.py quickchick properties",
         "tools/vos/gallina.py's QUICKCHICK_SWITCH and "
         "tools/vos/cli/quickchick.py's PACKAGE and VERSION",
         partial(_switch_at, gallina.QUICKCHICK_SWITCH, quickchick.PACKAGE,
                 quickchick.VERSION),
         quickchick.INSTALL),
    Fact("verilator", TOOLCHAIN,
         "run.py rtl lint, elaborate and crosscheck",
         f"tools/vos/cli/rtl.py's VERILATOR_PIN, which is {rtl.VERILATOR_PIN} and "
         f"arrives by {rtl.VERILATOR_HOW}",
         _verilator,
         ((*APT, "--no-upgrade", "--no-install-recommends", *rtl.VERILATOR_PACKAGES),
          (sys.executable, str(Path(__file__).resolve().parents[2] / "run.py"),
           "rtl", "install"))),
    Fact("clang and clang++", TOOLCHAIN,
         "the model build's compiler, which I10 flipped to it",
         "tools/vos/env.py's _compiler_args",
         partial(_both_on_path, "clang", "clang++"),
         ((*APT, "clang"),)),
    Fact("ccache", TOOLCHAIN,
         "the model build's compiler launchers",
         "tools/vos/env.py's _ccache_args",
         partial(_on_path, "ccache"),
         ((*APT, "ccache"),)),
    Fact("cmake", TOOLCHAIN,
         "run.py model build's configure",
         "model/CMakeLists.txt, which run.py model configures",
         partial(_on_path, "cmake"),
         ((*APT, "cmake"),)),
    Fact("ninja", TOOLCHAIN,
         "run.py model build's build stage",
         "tools/vos/cli/model.py, which configures the Ninja generator",
         partial(_on_path, "ninja"),
         ((*APT, "ninja-build"),)),
    Fact("git", TOOLCHAIN,
         "cmake's git describe, which stamps the emulator's revision (M0.10, I7)",
         "tools/vos/env.py's git_dir",
         partial(_on_path, "git"),
         ((*APT, "git"),)),
    Fact("libgmp-dev", TOOLCHAIN,
         "the Sail C runtime's arbitrary-precision arithmetic",
         "THIRD-PARTY.md's GMP section, over model/CMakeLists.txt's find_package(GMP)",
         partial(_dpkg, "libgmp-dev"),
         ((*APT, "libgmp-dev"),)),
    Fact("one memo cache per lane", TOOLCHAIN,
         "every run.py model typecheck, which rewrites its lane's cache whole",
         "I2's decline, and tools/vos/cli/model.py's _seed_smt_cache",
         _caches_unshared),
    Fact("guest outputs on the guest's own filesystem", TOOLCHAIN,
         "run.py model build and every loop that writes a build tree, a work directory "
         "or a log",
         "tools/vos/env.py's BUILD_ROOT and LOG_ROOT, and the placement rule "
         "tools/README.md states",
         _outputs_on_the_guest),
)


def _guarded(fact: Fact) -> Found:
    """A probe's own failure is the fact's, and never the run's.

    Narrow on purpose: an unreachable path or an executable that will not run is a
    machine this lane is not on, where a `TypeError` in a row is a defect in this file
    and has to arrive as a traceback rather than as a tidy finding about a toolchain.
    """
    try:
        return fact.probe()
    except OSError as err:
        return Found(False, f"the probe could not be taken: {err}")


def take(facts: Sequence[Fact]) -> list[tuple[Fact, Found]]:
    """Every probe, concurrently, answered back in the table's own order.

    Concurrent because most of these are a subprocess waiting on a version banner and
    none of them reads another's answer; merged in table order because a report a
    person reads twice has to be the same report both times, and the order two probes
    finish in is not a property of the machine being described. What several rows read,
    the opam client `_client` answers for, is asked once for the whole run, so every
    row reads one answer, and afresh by the next run.
    """
    if not facts:
        return []
    asked = _Asked()
    with ThreadPoolExecutor(max_workers=min(8, len(facts))) as pool:
        pending = [pool.submit(_guarded_under, asked, fact) for fact in facts]
        return [(fact, done.result())
                for fact, done in zip(facts, pending, strict=True)]


def _guarded_under(asked: _Asked, fact: Fact) -> Found:
    """`_guarded`, with what its run has already asked, `asked`, read by `_client`."""
    token = _ASKED.set(asked)
    try:
        return _guarded(fact)
    finally:
        _ASKED.reset(token)


def plan(results: Sequence[tuple[Fact, Found]]) -> list[tuple[Fact, tuple[tuple[str, ...], ...]]]:
    """The commands `--apply` would run, derived from what the probes saw.

    Pure, and it is the whole of what idempotence means here: a fact whose probe
    reports present contributes nothing, so a second run against a lane this tool has
    already satisfied plans nothing and changes nothing. A fact with no stated command
    contributes nothing either and is reported instead, which is the difference between
    a plan that is empty because there is nothing to do and one that is empty because
    there is nothing this tool may do; so does a fact whose probe found something its
    command must not run over.
    """
    return [(fact, fact.install) for fact, found in results
            if not found.present and fact.install and found.repairable]


def _verdict(rep: Reporter, fact: Fact, found: Found) -> None:
    if found.present:
        rep.report(fact.name, "", [], f"{found.saw}, for {fact.needs}")
        return
    if not fact.install:
        repair = ("no artifact here states a command for it, so this run reports it and "
                  "plans nothing")
    elif not found.repairable:
        repair = (f"its command, {env.install_line(fact.install)}, does not run over what "
                  "is there, so this run plans nothing")
    else:
        repair = env.install_line(fact.install)
    rep.report(fact.name, "absent, or at a version this lane is not:",
               [f"{found.saw}; {fact.needs} wants it and {fact.owner} fixes it; "
                f"{repair}"])


def _apply(rep: Reporter, steps: Sequence[tuple[Fact, tuple[tuple[str, ...], ...]]]) -> None:
    """Run the plan, reusing any switch an earlier attempt already created.

    Streamed to the caller's own terminal rather than captured, because these are opam
    and apt installs that take minutes and a caller watching a silent process cannot
    tell a download from a hang. What is recorded here is the verdict per step; the
    re-probe afterwards is what decides whether the lane is the lane.

    **An absent installer is a verdict and not a traceback**, which is the one thing
    this loop learned from being pointed at a host that is not the lane: on a machine
    with no uv, the two commands that install the pinned checkers are exactly the plan
    this forms, and `uv` is not there to run them. That is a foreseeable state of the
    world rather than a defect in this file, so it is reported and the run goes on to
    re-probe, where the row it belongs to fails on its own terms.
    """
    for fact, commands in steps:
        for argv in commands:
            # A failed import leaves its empty or partial switch registered. On a
            # retry, restore the snapshot there instead of failing at creation.
            # Only a confirmed existing name skips creation; other failures stand.
            if (len(argv) > 3 and argv[:3] == ("opam", "switch", "create")
                    and argv[3] in switches()):
                rep.line(f"   {fact.name}: {argv[3]} already exists; restoring its snapshot")
                continue
            rep.line(f"   {fact.name}: {' '.join(argv)}")
            try:
                code = subprocess.run(list(argv), check=False).returncode
            except OSError as err:
                rep.line(f"   {fact.name}: {argv[0]} could not be run: {err}")
                break
            if code != 0:
                rep.line(f"   {fact.name}: exited {code}")
                break


def run(table: Sequence[Fact] = FACTS, *, group: str = "",
        apply: bool = False) -> Reporter:
    """One whole run, as data, on the convention `check.py` set.

    `table` is a parameter rather than a read of `FACTS` so that this is testable at
    all: the live table describes the machine the tests run on, where what has to be
    held is the mapping from probe results to a plan and to a verdict, which wants a
    table whose answers the test chose.
    """
    rep = Reporter()
    rep.line("=== provision: the lane this repository builds in ===")

    facts = tuple(f for f in table if not group or f.group == group)
    results = take(facts)

    if apply:
        steps = plan(results)
        if steps:
            rep.line(f"-- installing {len(steps)} absent fact(s)")
            _apply(rep, steps)
            rep.line()
            results = take(facts)
        else:
            rep.line("-- nothing to install: every probed fact is already satisfied")

    for fact, found in results:
        _verdict(rep, fact, found)

    if group:
        skipped = [f.name for f in table if f.group != group]
        rep.line(f"   {len(skipped)} row(s) outside the {group} group did not run and "
                 f"this verdict decides nothing about them: {', '.join(skipped)}")

    rep.line()
    rep.line("not reached by any provisioner, and standing rather than owed:")
    for what, why in NOT_REACHED:
        rep.line(f"   {what}: {why}")

    rep.line()
    if rep.findings:
        rep.line(f"{rep.findings} of {len(facts)} probed fact(s) are not what this lane "
                 "declares.")
    else:
        rep.line(f"all {len(facts)} probed fact(s) hold: this machine is the lane.")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py provision",
        description="The lane this repository builds in, as an executable fact list.")
    what = parser.add_mutually_exclusive_group()
    what.add_argument("--check", action="store_true",
                      help="report what is absent and change nothing (the default)")
    what.add_argument("--apply", action="store_true",
                      help="install every absent fact this tree states a command for")
    what.add_argument("--install-opam", action="store_true",
                      help="install the reviewed opam client where no client is on PATH "
                           "and create its root where none stands, or complete one in "
                           "the shape its route leaves after its leading steps, the opam "
                           "row's command")
    parser.add_argument("--only", choices=GROUPS, default="", metavar="GROUP",
                        help=f"narrow to one group of rows: {' or '.join(GROUPS)}")
    args = parser.parse_args(argv)
    if args.install_opam:
        return install_opam()

    report = run(group=args.only, apply=args.apply)
    print("\n".join(report.out))
    return 1 if report.findings else 0
