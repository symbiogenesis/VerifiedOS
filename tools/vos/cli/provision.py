#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Executable fact list for the repository's host and guest build lanes.

Each row in `FACTS` names the consumer that requires the dependency, the owning
artifact or module that pins its version, a probe that checks what is installed, and
optional install commands (`--apply`). Versions, switch names, and pins are imported
from their owning modules rather than duplicated here.

    python tools/run.py provision                # report present and absent facts
    python tools/run.py provision --apply        # install repairable absent facts
    python tools/run.py provision --only gate    # probe only host-gate facts
    python tools/run.py provision --install-opam # install the reviewed opam client and root
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
import tarfile
import threading
import zlib
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from importlib import metadata
from pathlib import Path

from vos import cli, compiler_component, env, gallina, opam_client, pyversion
from vos.cli import quickchick, rtl, typecheck
from vos.corpus import find_root
from vos.report import Reporter

# Bound version queries and directory listings so a stalled probe becomes a finding.
TIMEOUT = 60

# Shared package-install command; each prerequisite row below must name a consumer.
APT: tuple[str, ...] = ("apt-get", "install", "-y")

OPAM_DESTINATION = Path("/usr/local/bin/opam")

# `gate` covers host checks and tool tests; `toolchain` covers model, RTL, oracle, and prover dependencies.
GATE = "gate"
TOOLCHAIN = "toolchain"
GROUPS: tuple[str, ...] = (GATE, TOOLCHAIN)

# Host/editor settings outside any provisioner's reach, reported as informational context.
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
    """Result of probing a single `Fact`: presence, observed state, and whether `--apply` may repair it."""

    present: bool
    saw: str
    repairable: bool = True


@dataclass(frozen=True)
class Fact:
    """A single lane dependency, its owning pin source, probe function, and optional install commands."""

    name: str
    group: str
    needs: str
    owner: str
    probe: Callable[[], Found]
    install: tuple[tuple[str, ...], ...] = ()


def _say(argv: Sequence[str]) -> str:
    """Run `argv` with stdin closed and `declining_environment`, returning stripped stdout on exit 0."""
    try:
        done = subprocess.run(list(argv), capture_output=True, encoding="utf-8",
                              errors="replace", check=False, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL, env=env.declining_environment())
    except OSError, subprocess.SubprocessError:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


# Require a dotted version so `Z3 version 5.1.0 - 64 bit` yields 5.1.0, not 3.
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)+")


def _number(text: str) -> str:
    """Extract the first dotted version number from `text`, or return `""`."""
    found = _NUMBER_RE.search(text)
    return found.group(0) if found else ""


@dataclass
class _Asked:
    """Cached `(path, release)` for the `opam` client on `PATH` within a single `take` call."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    client: tuple[str | None, str] | None = None


# Per-`take` shared probe state; unset outside that run.
_ASKED: contextvars.ContextVar[_Asked | None] = contextvars.ContextVar("provision_asked",
                                                                      default=None)


def _client() -> tuple[str | None, str]:
    """Return `(executable_path, release)` for `opam` on `PATH`, cached per `take` run."""
    asked = _ASKED.get()
    if asked is None:
        return _ask_client()
    with asked.lock:
        if asked.client is None:
            asked.client = _ask_client()
        return asked.client


def _ask_client() -> tuple[str | None, str]:
    where = shutil.which("opam")
    return where, _release(_say(("opam", "--version"))) if bool(where) else ""


def _release(text: str) -> str:
    """Return the first whitespace-delimited token of `opam --version` (preserving suffixes like `~beta1`)."""
    words = text.split()
    return words[0] if words else ""


def _interpreter() -> Found:
    """Check the running Python interpreter against the project's supported minor version."""
    want = tuple(int(part) for part in pyversion.supported_minor(find_root()).split("."))
    running = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    return Found(running[:2] == want, ".".join(str(part) for part in running))


def _on_path(name: str) -> Found:
    where = shutil.which(name)
    return Found(where is not None, where or f"no {name} on PATH")


def _cmake_minimum(owner: Path) -> str:
    versions = list(re.finditer(r"(?m)^cmake_minimum_required\(VERSION ([0-9]+(?:\.[0-9]+){1,2})\)$",
                                owner.read_text(encoding="utf-8")))
    if len(versions) != 1:
        raise ValueError("expected one literal cmake_minimum_required VERSION")
    version = versions[0].group(1)
    if not isinstance(version, str):
        raise TypeError("CMake minimum version must be text")
    return version


def _cmake() -> Found:
    """Check installed CMake against the minimum version in `model/CMakeLists.txt`."""
    owner = Path(__file__).resolve().parents[3] / "model/CMakeLists.txt"
    try:
        minimum = _cmake_minimum(owner)
    except (OSError, ValueError, TypeError) as err:
        return Found(False, f"cannot read CMake floor from {owner}: {err}", repairable=False)
    executable = shutil.which("cmake")
    if executable is None:
        return Found(False, f"no cmake on PATH; model requires {minimum} or newer")
    version = _number(_say((executable, "--version")))
    if not version:
        return Found(False, f"{executable} answered with no CMake version")
    current = tuple(int(part) for part in version.split("."))
    required = tuple(int(part) for part in minimum.split("."))
    return Found(current >= required, f"CMake {version}; model requires {minimum} or newer")


def _both_on_path(first: str, second: str) -> Found:
    """Verify both `first` and `second` executables are on `PATH`."""
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
    except OSError, subprocess.SubprocessError:
        return Found(False, f"{exe} could not be asked its version")
    return Found(found == pin, f"{found} at {exe}")


def _verilator() -> Found:
    """Probe the same project-local simulator that every RTL loop selects."""
    binary = rtl._verilator()
    if binary is None:
        return Found(False, "no project Verilator or verilator on PATH")
    return _at_version((binary, "--version"), rtl.VERILATOR_PIN)


def _importable(module: str, distribution: str) -> Found:
    """Verify `module` is importable in the running environment and report `distribution`'s version."""
    if importlib.util.find_spec(module) is None:
        return Found(False, f"no {module} in the environment this interpreter resolves "
                            "against")
    try:
        return Found(True, f"{module} {metadata.version(distribution)}")
    except metadata.PackageNotFoundError:
        return Found(True, f"{module} present, at a version its metadata does not state")


def switches() -> tuple[str, ...]:
    """Return all opam switches reported by `opam switch list --short`."""
    return tuple(line.strip()
                 for line in _say(("opam", "switch", "list", "--short")).splitlines()
                 if line.strip())


def _installed(switch: str, package: str) -> str:
    """Return the installed version of `package` in `switch`, or `""`."""
    return _say(("opam", "list", "--switch", switch, "--installed", "--short",
                 "--columns=version", package))


def _switch_at(switch: str, package: str, pin: str, *, pinned: bool = False) -> Found:
    """Probe whether `switch` has `package` at `pin`, marking unrepairable if root/client differs."""
    older = _older_root()
    client = _client()
    found = _switch_found(switch, package, pin, older=bool(older), client=client,
                          pinned=pinned)
    if found.present:
        return found
    if older:
        return Found(False, f"{found.saw}; {older}, so no switch is planned over it",
                     repairable=False)
    where, version = client
    if where is not None and version != opam_client.OPAM_VERSION:
        return Found(False, f"{found.saw}; opam {version or 'answering no version'} at "
                            f"{where} would build it, and the reviewed client is "
                            f"{opam_client.OPAM_VERSION}, so no switch is planned",
                     repairable=False)
    return found


def _switch_found(switch: str, package: str, pin: str, *, older: bool,
                  client: tuple[str | None, str], pinned: bool = False) -> Found:
    """Check whether `switch` is listed and holds `package` at version or source `pin`."""
    listed = switches()
    if switch not in listed:
        root = env.opam_root()
        if older and not listed and switch in opam_client.root_switches(root):
            return Found(False, _unlisted(switch, root, client))
        return Found(False, f"opam has no {switch} switch")
    if pinned:
        return _pinned_source(switch, package, pin)
    found = _installed(switch, package)
    if not found:
        return Found(False, f"the {switch} switch carries no {package}")
    return Found(found == pin, f"{package} {found} in {switch}")


def _oracle_switch() -> Found:
    """Check the CertiRocq switch against both its package release and `tools/opam/certirocq.lock`."""
    found = _switch_at(gallina.ORACLE_SWITCH, "rocq-certirocq", gallina.CERTIROCQ_VERSION)
    if not found.present:
        return found
    exported = _say(("opam", "switch", "export", "--switch", gallina.ORACLE_SWITCH,
                     "--full", "--freeze", "-"))
    try:
        snapshot = (find_root() / "tools/opam/certirocq.lock").read_text(encoding="utf-8")
        matches = compiler_component.matches_oracle_snapshot(exported, snapshot)
        if matches:
            prefix = Path(_say(("opam", "var", "prefix", "--switch", gallina.ORACLE_SWITCH)))
            if not prefix.is_absolute():
                return Found(False, f"{found.saw}; frozen source provenance unread: "
                                    "the oracle switch supplied no absolute prefix", repairable=False)
            metadata = (prefix / ".opam-switch/packages"
                        / f"rocq-certirocq.{gallina.CERTIROCQ_VERSION}" / "opam")
            matches = compiler_component.matches_installed_oracle(
                metadata.read_text(encoding="utf-8"), snapshot, gallina.CERTIROCQ_VERSION)
    except (OSError, UnicodeError, ValueError) as err:
        return Found(False, f"{found.saw}; frozen source provenance unread: {err}", repairable=False)
    if not matches:
        return Found(False, f"{found.saw}; packages or frozen/installed CertiRocq recipe differ from "
                            "tools/opam/certirocq.lock", repairable=False)
    if compiler_component.legacy_oracle_snapshot(snapshot):
        return Found(True, f"{found.saw}; packages match the qualified legacy version-only snapshot")
    return Found(True, f"{found.saw}; frozen and installed CertiRocq recipes and packages match the snapshot")


def _pinned_source(switch: str, package: str, pin: str) -> Found:
    """Verify `package` in `switch` is built from pinned source `pin` (`git+URL#commit`)."""
    fields = _say(("opam", "list", "--switch", switch, "--installed", "--short",
                   "--columns=version,pin", package)).split()
    if not fields:
        return Found(False, f"the {switch} switch carries no {package}")
    if len(fields) < 2:
        return Found(False, f"{package} {fields[0]} in {switch}, from no pinned source")
    return Found(fields[-1] == pin, f"{package} built from {fields[-1]} in {switch}")


def _unlisted(switch: str, root: Path, client: tuple[str | None, str]) -> str:
    """Format diagnostic when `switch` is in `root`'s config but `opam switch list` returned empty."""
    where, version = client
    if where is None:
        return f"no opam on PATH lists switches; the root's config lists the {switch} switch"
    if version == opam_client.OPAM_VERSION and _upgrades_to_read(root):
        return ("opam listed no switches without upgrading the root, whose config lists "
                f"the {switch} switch")
    return (f"opam {version or 'answering no version'} listed no switches over this root "
            f"in format {opam_client.root_format(root)}, whose config lists the {switch} "
            "switch")


# Opam 2.6.1 hard-upgrade thresholds (`OpamFormatUpgrade.upgrades`).
_UPGRADES_READ: str = "2.6.1"
_HARD_BEFORE = "2.0~beta5"
_HARD_FROM: tuple[str, ...] = ("2.1~alpha", "2.1~alpha2")
_NESTED_BEFORE = "2.6~alpha"
_UNREAD_MEMBERS = frozenset((tarfile.LNKTYPE, tarfile.SYMTYPE, tarfile.CHRTYPE,
                             tarfile.BLKTYPE, tarfile.FIFOTYPE))


def _upgrades_to_read(root: Path) -> bool:
    """Return whether opam 2.6.1 requires a hard on-disk format upgrade before reading `root`."""
    fmt = opam_client.root_format(root)
    if (opam_client.OPAM_VERSION != _UPGRADES_READ or not opam_client.older_than_reviewed(fmt)
            or opam_client.compare_versions(fmt, _NESTED_BEFORE) >= 0):
        return False
    nested = _nested_repository(root)
    if nested is None:
        return False
    return (nested or opam_client.compare_versions(fmt, _HARD_BEFORE) < 0
            or any(opam_client.compare_versions(fmt, hard) == 0 for hard in _HARD_FROM))


def _nested_repository(root: Path) -> bool | None:
    """Return whether any repository archive under `root` uses a nested directory layout, or `None` on error."""
    names = dict.fromkeys(repo["name"] for repo in opam_client.repositories(root))
    read = [_archive_nested(root / "repo" / f"{name}.tar.gz") for name in names]
    return None if None in read else any(read)


def _archive_nested(archive: Path) -> bool | None:
    """Check whether `archive`'s first regular file sits outside top-level `repo` or `packages/`."""
    if not archive.is_file():
        return False
    try:
        with tarfile.open(archive, "r:gz") as members:
            for member in members:
                if member.type in _UNREAD_MEMBERS:
                    return None
                if member.isdir() or member.name.endswith("/"):
                    if member.size:
                        return None
                    continue
                members.fileobj.seek(member.offset_data)
                if len(members.fileobj.read(member.size)) != member.size:
                    return None
                return _named_nested(member.name)
            return _ended(members)
    except OSError, EOFError, tarfile.TarError, zlib.error:
        return None


def _ended(members: tarfile.TarFile) -> bool | None:
    """Return `False` if `members` ends with two zero blocks, else `None`."""
    members.fileobj.seek(members.offset)
    end = bytes(2 * tarfile.BLOCKSIZE)
    return False if members.fileobj.read(len(end)) == end else None


def _named_nested(name: str) -> bool | None:
    """Return whether canonical relative archive path `name` is outside `repo` and `packages/`."""
    segments = name.split("/")
    if (segments[0] == "" and len(segments) > 1) or segments[-1] == "" or ".." in segments:
        return None
    kept = [segment for segment in segments if segment not in ("", ".")]
    if not kept:
        return None
    return kept != ["repo"] and not (len(kept) > 1 and kept[0] == "packages")


def _older_root() -> str:
    """Return a warning clause if the opam root format is older than the reviewed client's, else `""`."""
    root = env.opam_root()
    fmt = opam_client.root_format(root)
    if not (opam_client.root_exists(root) and opam_client.older_than_reviewed(fmt)):
        return ""
    return (f"the reviewed client {opam_client.OPAM_VERSION} rewrites the opam root at "
            f"{root} from format {fmt} to {opam_client.OPAM_ROOT_FORMAT} one way at its "
            "first write, or at its first read where the upgrade cannot be made in "
            "memory, a deliberate, recorded step rather than a repair")


def _moving_the_root(fmt: str) -> str:
    """Return a clause describing the one-way format upgrade if `fmt` is older than reviewed, else `""`."""
    if not opam_client.older_than_reviewed(fmt):
        return ""
    return (f", and moving to it upgrades this root's format from {fmt} to "
            f"{opam_client.OPAM_ROOT_FORMAT} one way, a deliberate, recorded step rather "
            "than a repair")


def _opam_client() -> Found:
    """Probe the `opam` client on `PATH` and the opam root against `opam_client` pins."""
    where, found = _client()
    client = f"opam {found or 'answering no version'} at {where}" if bool(where) else "no opam on PATH"
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
    """Format configured repositories and their stamps for `root`."""
    return ", ".join(f"{repo['name']} {repo['url']} at stamp {repo['stamp'] or 'unrecorded'}"
                     for repo in opam_client.repositories(root)) or "no repositories"


def _standing(resumable: bool) -> str:
    """Describe whether an incomplete standing opam root can be resumed by `_create_root`."""
    if resumable:
        return ("in the shape the root-creation route leaves after its leading steps, "
                "which that route's remaining steps complete")
    return ("and a standing root is left as it is unless it is in the shape the "
            "root-creation route leaves after its leading steps")


def install_opam(destination: Path = OPAM_DESTINATION) -> int:
    """Install the reviewed `opam` client if absent and initialize or resume the opam root."""
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
    """Return whether `directory` is on `os.get_exec_path()`."""
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
    """Return packages in `opam_client.ROOT_PREREQUISITES` not reported installed by `dpkg`."""
    return [package for package in opam_client.ROOT_PREREQUISITES
            if not _dpkg(package).present]


def _create_root(root: Path, *, resuming: bool = False) -> int:
    """Create or resume the opam root at `root` using `opam_client.remaining_route`."""
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
    """Format diagnostic suffix when `_create_root` fails with `remaining` steps unrun."""
    left = "; ".join(" ".join(argv) for argv in remaining)
    if not opam_client.root_exists(root):
        return f"so no opam root stands at {root}; what remains of the route is {left}"
    then = ("a later run of this command finishes it" if opam_client.root_resumable(root)
            else "a standing root in this state is left as it is")
    return (f"so the opam root at {root} stands in format "
            f"{opam_client.root_format(root) or 'unread'} with {_listing(root)}; what "
            f"remains of the route is {left}, and {then}")


def _pinned_z3() -> Found:
    """Check that `env.Z3_PREFIX/bin/z3` exists and matches `env.Z3_VERSION`."""
    exe = env.Z3_PREFIX / "bin" / "z3"
    if not exe.is_file():
        return Found(False, f"{exe} is absent, so a typecheck would answer from the "
                            f"distribution's z3 {env.Z3_DISTRIBUTION} and cache that")
    found = _number(_say((str(exe), "--version")))
    return Found(found == env.Z3_VERSION, f"{found or 'no version'} at {exe}")


def _dpkg(package: str) -> Found:
    """Query `dpkg-query` for whether `package` is installed."""
    status = _say(("dpkg-query", "-W", "-f=${Status} ${Version}", package))
    return Found(status.startswith("install ok installed"),
                 status or f"dpkg knows no {package}")


def _caches_unshared() -> Found:
    """Verify no two lanes under `env.build_root()` share an inode for `TYPECHECK_CACHE`."""
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
    """Verify `env.build_root()` and `env.log_root()` sit on persistent guest filesystems."""
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


# Ordered fact table: host-gate rows first, then guest toolchain rows from opam root prerequisites outward.
FACTS: tuple[Fact, ...] = (
    Fact("the supported interpreter", GATE,
         "every command here, on both lanes",
         "tools/pyproject.toml project.requires-python, read through tools/vos/pyversion.py",
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
         "tools/vos/proofenv.py's ROCQ_SWITCH and ROCQ_VERSION",
         partial(_switch_at, env.ROCQ_SWITCH, "rocq-core", env.ROCQ_VERSION),
         env.ROCQ_INSTALL),
    Fact("the CertiRocq oracle switch", TOOLCHAIN,
         "the M1.5 Wasm oracle",
         "tools/vos/gallina.py's ORACLE_SWITCH and CERTIROCQ_VERSION, the switch "
         "tools/wasm-oracle/README.md's recipe imports from tools/opam/certirocq.lock",
         _oracle_switch),
    Fact("the QuickChick switch", TOOLCHAIN,
         "run.py quickchick check and properties, and run.py seed coq --quickchick",
         "tools/vos/gallina.py's QUICKCHICK_SWITCH and "
         "tools/vos/cli/quickchick.py's PACKAGE and INSTALL_PIN",
         partial(_switch_at, gallina.QUICKCHICK_SWITCH, quickchick.PACKAGE,
                 quickchick.INSTALL_PIN, pinned=True),
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
         _cmake,
         ((*APT, "cmake"),)),
    Fact("ninja", TOOLCHAIN,
         "run.py model build's build stage",
         "tools/vos/cli/model.py, which configures the Ninja generator",
         partial(_on_path, "ninja"),
         ((*APT, "ninja-build"),)),
    Fact("git", TOOLCHAIN,
         "cmake's git describe, which stamps the emulator's revision (M0.10, I7)",
         "tools/vos/proofenv.py's git_dir",
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
         "tools/vos/proofenv.py's BUILD_ROOT, tools/vos/env.py's LOG_ROOT, and the "
         "placement rule tools/README.md states",
         _outputs_on_the_guest),
)


def _guarded(fact: Fact) -> Found:
    """Run `fact.probe()`, converting `OSError` into a failed `Found`."""
    try:
        return fact.probe()
    except OSError as err:
        return Found(False, f"the probe could not be taken: {err}")


def take(facts: Sequence[Fact]) -> list[tuple[Fact, Found]]:
    """Run probes for `facts` concurrently and return `(fact, found)` pairs in table order."""
    if not facts:
        return []
    asked = _Asked()
    with ThreadPoolExecutor(max_workers=min(8, len(facts))) as pool:
        pending = [pool.submit(_guarded_under, asked, fact) for fact in facts]
        return [(fact, done.result())
                for fact, done in zip(facts, pending, strict=True)]


def _guarded_under(asked: _Asked, fact: Fact) -> Found:
    """Run `_guarded(fact)` with `_ASKED` bound to `asked`."""
    token = _ASKED.set(asked)
    try:
        return _guarded(fact)
    finally:
        _ASKED.reset(token)


def plan(results: Sequence[tuple[Fact, Found]]) -> list[tuple[Fact, tuple[tuple[str, ...], ...]]]:
    """Return `(fact, install_commands)` for absent, repairable facts with install commands."""
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
    """Execute planned install commands, reusing any opam switch already created."""
    for fact, commands in steps:
        for argv in commands:
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
    """Probe `table` (optionally filtered by `group`), apply repairs if requested, and return `Reporter`."""
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
        suggest_on_error=True, prog="run.py provision",
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
