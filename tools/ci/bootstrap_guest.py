#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Install the guest gate's toolchains in one private, native Linux directory."""

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

TOOLS = Path(__file__).resolve().parents[1]
PYTHON_VERSION = tomllib.loads((TOOLS / "ty.toml").read_text(encoding="utf-8"))[
    "environment"]["python-version"]
if f"{sys.version_info.major}.{sys.version_info.minor}" != PYTHON_VERSION:
    raise SystemExit(f"guest bootstrap requires Python {PYTHON_VERSION}; found {platform.python_version()}")
sys.path.insert(0, str(TOOLS))

from vos import (  # noqa: E402  (standalone bootstrap precedes the locked environment)
    cli,
    env,
    opam_client,
    receipts,
)
from vos.cli import rtl  # noqa: E402

# The opam root's own prerequisites come from the client's owner, which states why
# `opam init` needs each; the rest are the toolchains' build and run dependencies.
PACKAGES: tuple[str, ...] = tuple(dict.fromkeys((
    "build-essential", *opam_client.ROOT_PREREQUISITES, "patch",
    "pkg-config", "m4", "cmake", "ninja-build", "libgmp-dev", "clang", "ccache",
    "device-tree-compiler", "git", "time", *rtl.VERILATOR_PACKAGES,
)))
MARKER = ".verifiedos-guest-root"
# Installation order; the Sail entry includes its solver.
TOOLCHAINS: tuple[str, ...] = ("sail", "rocq", "rtl")


def prepare_root(root: Path) -> Path:
    """Reject accidental reuse of a developer's directory or non-native storage."""
    if not root.is_absolute():
        raise ValueError("--root must be an absolute path")
    if any(character in str(root) for character in "\r\n\0"):
        raise ValueError("--root must not contain line breaks or NUL bytes")
    root = root.resolve()
    checkout = TOOLS.parent.resolve()
    if root == Path(root.anchor) or root == Path.home().resolve() or root.is_relative_to(checkout):
        raise ValueError("--root must be a private directory outside the checkout and home root")
    # These paths are rejected, never used for a temporary file.
    if root.is_relative_to(Path("/tmp")) or root.is_relative_to(Path("/var/tmp")):  # noqa: S108
        raise ValueError("--root must preserve logs outside temporary storage")
    kind = env.filesystem(root)
    if not kind or kind in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS:
        raise ValueError(f"--root must be on a native persistent filesystem, found {kind}")
    return claim_root(root)


def claim_root(root: Path) -> Path:
    """An empty directory becomes owned; a previous successful claim can resume."""
    marker = root / MARKER
    if marker.is_symlink():
        raise ValueError(f"bootstrap ownership marker must not be a symlink: {marker}")
    if marker.exists():
        if not marker.is_file() or marker.read_text(encoding="utf-8") != "1\n":
            raise ValueError(f"unrecognized bootstrap ownership marker: {marker}")
        return root
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"refusing nonempty unowned bootstrap directory {root}")
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("1\n", encoding="utf-8", newline="")
    return root


def environment(root: Path, jobs: int) -> dict[str, str]:
    return {
        "VOS_GUEST_ROOT": str(root), "VOS_LANE": "",
        "VOS_ROOT": str(TOOLS.parent), "VOS_MODEL": str(TOOLS.parent / "model"),
        "VOS_BUILD_DIR": str(root / "build" / env.MODEL_TREE),
        "VOS_ROCQ": str(root / "opam" / env.ROCQ_SWITCH / "bin" / "rocq"),
        "VOS_ROCQCHK": str(root / "opam" / env.ROCQ_SWITCH / "bin" / "rocqchk"),
        "OPAMROOT": str(root / "opam"), "OPAMJOBS": str(jobs),
        "VOS_BUILD_ROOT": str(root / "build"), "VOS_LOG_DIR": str(root / "logs"),
        "VOS_Z3_BIN": str(root / "z3" / "bin"), "CCACHE_DIR": str(root / "ccache"),
        "VOS_JOBS": str(jobs), "VOS_TEST_JOBS": str(jobs), "TMPDIR": str(root / "tmp"),
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(root / "uv-cache")),
        "VOS_KEEPALIVE_HOURS": "0", "OPAMYES": "1",
    }


def run(argv: tuple[str, ...], log: IO[str], *, declining: bool = False) -> None:
    """Run one step into the log, failing where it fails.

    A step inherits this process's input and environment, whose `OPAMYES` answers the
    questions the installing steps ask. One marked `declining` is a read of the private
    root and answers none: it runs with no standard input and in
    `env.declining_environment`. The root stands in the reviewed client's format before
    any read, so a read asks nothing; one that did, such as a root-format upgrade, is
    declined and fails the step rather than being answered yes out of sight."""
    command = shlex.join(argv)
    print(f"== {command}", flush=True)
    log.write(f"\n== {command}\n")
    log.flush()
    started = time.monotonic()
    done = subprocess.run(argv, stdout=log, stderr=log, check=False,
                          stdin=subprocess.DEVNULL if declining else None,
                          env=env.declining_environment() if declining else None)
    log.write(f"exit={done.returncode}, seconds={time.monotonic() - started:.1f}\n")
    log.flush()
    done.check_returncode()


def missing_packages() -> list[str]:
    """Read the package database once; exit 1 means some requested names are absent."""
    done = subprocess.run(
        ("dpkg-query", "-W", "-f=${Package}\t${Status}\n", *PACKAGES),
        capture_output=True, text=True, check=False, timeout=60)
    if done.returncode not in (0, 1):
        done.check_returncode()
    statuses: dict[str, list[str]] = {}
    for line in done.stdout.splitlines():
        name, separator, status = line.partition("\t")
        if not separator:
            raise ValueError(f"unrecognized dpkg-query output: {line!r}")
        statuses.setdefault(name, []).append(status)
    # Preserve the individual query's refusal of ambiguous multiarch results.
    return [name for name in PACKAGES if statuses.get(name) != ["install ok installed"]]


def system_packages(install: bool, log: IO[str]) -> None:
    missing = missing_packages()
    if not missing:
        return
    if not install:
        raise ValueError("missing Ubuntu packages: " + " ".join(missing)
                         + "; use --install-system to install them")
    if sys.platform != "linux":
        raise ValueError("system packages are installed on Linux, inside the guest lane")
    prefix = () if os.geteuid() == 0 else ("sudo", "-n")
    run((*prefix, "apt-get", "update"), log)
    run((*prefix, "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y",
         "--no-upgrade", "--no-install-recommends", *missing), log)
    if missing := missing_packages():
        raise ValueError("packages still absent after installation: " + " ".join(missing))


def install_switch(steps: tuple[tuple[str, ...], ...], log: IO[str]) -> None:
    """Run a switch's steps, skipping the creation of a switch the root already lists,
    which a failed import left registered. The listing is a read, and declines any
    question as `run`'s declining steps do."""
    existing = subprocess.run(("opam", "switch", "list", "--short"),
                              stdout=subprocess.PIPE, stderr=log, text=True,
                              check=True, timeout=60, stdin=subprocess.DEVNULL,
                              env=env.declining_environment()).stdout.splitlines()
    for argv in steps:
        if argv[:3] == ("opam", "switch", "create") and argv[3] in existing:
            continue
        run(argv, log)


def initialize_repositories(opam: Path, log: IO[str]) -> str:
    """Leave the private root at `opam` standing on the opam client owner's repositories,
    and say how: `created` by the owner's one route, `CREATE_ROOT`, where no root stands,
    initialized on its default repository with the rest added unselected, each switch
    naming the repositories it resolves from; `finished` by the route's remaining steps,
    `opam_client.remaining_route`, never `opam init` over it, where `root_resumable`
    reads a root in the shape the route's leading steps leave, one whose last addition
    was stopped during its fetch among them; and `kept` where
    a root stands complete, the reviewed client's format with exactly the owner's
    repositories at their URLs and every stamp read, as one the route made.

    The route is not run over a complete root, such as the one Guest CI restores with
    its installed switches: the reviewed client's `repository add` of a repository the
    root already carries at that URL fetches it again, so the root would carry a stamp
    the restored switches were not resolved against, and removes that repository where
    the fetch fails. Any other standing root is refused and left as it is, and the
    refusal names, beside the first check the root fails, each further gap
    `opam_client.root_gaps` reads that the failure does not already state, such as an
    unread stamp of the first repository behind a missing later one.
    """
    if not opam_client.root_exists(opam):
        how = "created"
    elif opam_client.root_resumable(opam):
        how = "finished"
    else:
        try:
            opam_client.initialized_format(opam)
            opam_client.initialized_repositories(opam)
        except ValueError as error:
            gaps = [gap for gap in opam_client.root_gaps(opam) if gap not in str(error)]
            further = f"; the root {' and '.join(gaps)}" if gaps else ""
            raise ValueError(f"{error}{further}; bootstrap creates a root where none stands "
                             "and finishes one only in the shape the root-creation route "
                             "leaves after its leading steps, so this root is left as it "
                             "is") from error
        kept = f"the opam root at {opam} stands complete; the root-creation route is not run"
        print(f"== {kept}", flush=True)
        log.write(f"\n== {kept}\n")
        log.flush()
        return "kept"
    for argv in opam_client.remaining_route(opam):
        run(argv, log)
    return how


def install_toolchains(root: Path, jobs: int, log: IO[str],
                       selected: tuple[str, ...] = TOOLCHAINS) -> None:
    """Provide Sail's solver at startup and probe each tool before building the next."""
    if "sail" in selected:
        for step in env.z3_install(root / "z3", sys.executable):
            run(step, log)
        # Sail initializes its solver even for --version. VOS_Z3_BIN is consumed by
        # run.py's environment setup, which does not run in this bootstrap process.
        solver_bin = root / "z3" / "bin"
        os.environ["PATH"] = str(solver_bin) + os.pathsep + os.environ.get("PATH", "")
        run((str(solver_bin / "z3"), "--version"), log)
        install_switch(env.SAIL_INSTALL, log)
        run((str(root / "bin" / "opam"), "exec", f"--switch={env.SAIL_SWITCH}",
             "--", "sail", "--version"), log, declining=True)
    if "rocq" in selected:
        install_switch(env.ROCQ_INSTALL, log)
        run((str(root / "opam" / env.ROCQ_SWITCH / "bin" / "rocq"), "--version"), log)
    if "rtl" in selected:
        run(tuple(cli.entry("rtl", "install", "--jobs", str(jobs))), log)


def export_environment(values: dict[str, str], paths: tuple[Path, ...],
                       github_env: Path | None, github_path: Path | None) -> None:
    validate_environment(values, paths)
    if github_env:
        with github_env.open("a", encoding="utf-8", newline="") as stream:
            stream.writelines(f"{key}={value}\n" for key, value in values.items())
    if github_path:
        with github_path.open("a", encoding="utf-8", newline="") as stream:
            # GitHub prepends entries; reverse them to match the shell activation.
            stream.writelines(f"{path}\n" for path in reversed(paths))


def validate_environment(values: dict[str, str], paths: tuple[Path, ...]) -> None:
    if any(character in value for value in (*values.values(), *map(str, paths))
           for character in "\r\n\0"):
        raise ValueError("environment paths must not contain line breaks or NUL bytes")


def activation(values: dict[str, str], paths: tuple[Path, ...]) -> str:
    """A sourceable shell file; values cannot become shell syntax."""
    validate_environment(values, paths)
    exports = [f"export {key}={shlex.quote(value)}" for key, value in values.items()]
    exports.append(f"export PATH={shlex.quote(':'.join(map(str, paths)))}:\"$PATH\"")
    return "\n".join(exports) + "\n"


def retain_logs(root: Path) -> None:
    """Only diagnostic text leaves build directories; never tools or their sources."""
    destination = root / "logs"
    verilator = root / "build" / f"verilator-{rtl.VERILATOR_PIN}-source" / "build.log"
    if verilator.is_file():
        shutil.copyfile(verilator, destination / "verilator-install.log")
    (destination / "opam").mkdir(exist_ok=True)
    for path in (root / "opam" / "log").glob("*"):
        if path.suffix in {".out", ".info"} and path.is_file():
            shutil.copyfile(path, destination / "opam" / path.name)


def bootstrap(args: argparse.Namespace) -> int:
    if sys.platform != "linux":
        raise ValueError("guest bootstrap runs on Linux; invoke it inside the assigned guest lane")
    if platform.machine() not in opam_client.OPAM_HASHES:
        raise ValueError(f"no reviewed opam binary for {platform.machine()}")
    manifest = tomllib.loads((TOOLS / "pyproject.toml").read_text(encoding="utf-8"))
    uv_version = manifest["tool"]["uv"]["required-version"].removeprefix("==")
    found_uv = subprocess.run(("uv", "--version"), capture_output=True, text=True,
                              check=True, timeout=60).stdout.split()
    if len(found_uv) < 2 or found_uv[1] != uv_version:
        raise ValueError(f"bootstrap requires uv {uv_version} from tools/pyproject.toml")
    root = prepare_root(args.root)
    with env.hold_lock(root / "bootstrap", "guest bootstrap"):
        return install(args, root, uv_version)


def install(args: argparse.Namespace, root: Path, uv_version: str) -> int:
    """Mutate an owned root only while the caller holds its bootstrap lock."""
    jobs = args.jobs if args.jobs is not None else env.worker_jobs(2048, label="toolchain")
    selected = tuple(name for name in TOOLCHAINS if name in (args.toolchains or TOOLCHAINS))
    values = environment(root, jobs)
    paths = (root / "z3" / "bin", root / "bin")
    validate_environment(values, paths)
    for name in ("VOS_BUILD_ROOT", "VOS_LOG_DIR", "TMPDIR", "CCACHE_DIR", "UV_CACHE_DIR"):
        Path(values[name]).mkdir(parents=True, exist_ok=True)
    binary_dir = root / "bin"
    binary_dir.mkdir(exist_ok=True)
    os.environ.update(values)
    os.environ["PATH"] = str(binary_dir) + os.pathsep + os.environ.get("PATH", "")
    logs = root / "logs"
    receipts.write(logs / "environment.json", values)
    # A resumed installation cannot publish verdicts or activation from its prior run.
    for path in (root / "environment.sh", logs / "evidence.json", logs / "proof-evidence.json",
                 logs / "results.json", logs / "bootstrap.json"):
        path.unlink(missing_ok=True)
    started = time.monotonic()
    record: dict[str, object] = {
        "schema": 1, "started_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(), "python": sys.version, "jobs": jobs,
        "toolchains": list(selected), "bootstrap_sha256": receipts.digest(Path(__file__)),
        "uv": uv_version, "opam": opam_client.OPAM_VERSION, "sail": env.SAIL_VERSION,
        "rocq": env.ROCQ_VERSION, "z3": env.Z3_VERSION, "verilator": rtl.VERILATOR_PIN,
        "snapshots": {name: receipts.digest(TOOLS / "opam" / f"{name}.lock")
                      for name in ("sail", "rocq")}, "exit_code": 1,
    }
    record_path = logs / "bootstrap.json"
    receipts.write(record_path, record)
    log_path = logs / "bootstrap.log"
    print(f"Bootstrap log: {log_path}; jobs: {jobs}", flush=True)
    with log_path.open("w", encoding="utf-8", newline="") as log:
        try:
            system_packages(args.install_system, log)
            record["source_revision"] = subprocess.run(
                ("git", "-C", str(TOOLS.parent), "rev-parse", "HEAD"), capture_output=True,
                text=True, check=True, timeout=60,
                env=os.environ | env.git_env(TOOLS.parent)).stdout.strip()
            opam_client.install(binary_dir / "opam", platform.machine())
            record["opam_root_action"] = initialize_repositories(root / "opam", log)
            # The metadata the snapshots are resolved against, which the locks do not fix,
            # refused rather than recorded where the root's own files cannot say it.
            record["opam_repositories"] = opam_client.initialized_repositories(root / "opam")
            record["opam_root_format"] = opam_client.initialized_format(root / "opam")
            install_toolchains(root, jobs, log, selected)
            (root / "environment.sh").write_text(activation(values, paths),
                                                  encoding="utf-8", newline="")
            export_environment(values, paths, args.github_env, args.github_path)
            record["exit_code"] = 0
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            record["error"] = str(error)
            log.write(f"FAIL bootstrap: {error}\n")
            log.flush()
            print(f"FAIL bootstrap: {error}; see {log_path}", file=sys.stderr)
        finally:
            try:
                retain_logs(root)
            except OSError as error:
                record["diagnostic_error"] = str(error)
                record["exit_code"] = 1
                print(f"FAIL retaining bootstrap logs: {error}", file=sys.stderr)
            record["seconds"] = round(time.monotonic() - started, 2)
            receipts.write(record_path, record)
    if record["exit_code"] != 0:
        with log_path.open(encoding="utf-8", errors="replace") as failed:
            print("".join(deque(failed, maxlen=40)), end="", file=sys.stderr)
    return 0 if record["exit_code"] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="private persistent native directory outside the source checkout")
    parser.add_argument("--jobs", type=cli.positive_int,
                        help="worker override (default: available CPUs limited by memory)")
    parser.add_argument("--toolchain", action="append", choices=TOOLCHAINS, dest="toolchains",
                        help="install only this toolchain; repeat to select several (default: all)")
    parser.add_argument("--install-system", action="store_true",
                        help="install absent Ubuntu packages using root or passwordless sudo")
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--github-path", type=Path)
    args = parser.parse_args(argv)
    try:
        return bootstrap(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"FAIL bootstrap: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
