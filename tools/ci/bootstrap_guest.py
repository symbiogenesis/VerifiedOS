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
    receipts,
)
from vos.cli import rtl  # noqa: E402

OPAM_VERSION = "2.5.2"
OPAM_HASHES: dict[str, tuple[str, str]] = {
    "aarch64": ("arm64", "c4106ece84bcb60c68342573d2d6b4f0d6770ee088015c2216adc83d8854dcf9"),
    "x86_64": ("x86_64", "edfca2630c373b44b7ee1c2f81cd8dcf67468d0db57d6c02158de553ac63dbd4"),
}
PACKAGES: tuple[str, ...] = tuple(dict.fromkeys((
    "build-essential", "bubblewrap", "ca-certificates", "curl", "unzip", "patch",
    "pkg-config", "m4", "cmake", "ninja-build", "libgmp-dev", "clang", "ccache",
    "device-tree-compiler", "git", "time", *rtl.VERILATOR_PACKAGES,
)))
MARKER = ".verifiedos-guest-root"


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


def run(argv: tuple[str, ...], log: IO[str]) -> None:
    command = shlex.join(argv)
    print(f"== {command}", flush=True)
    log.write(f"\n== {command}\n")
    log.flush()
    started = time.monotonic()
    done = subprocess.run(argv, stdout=log, stderr=log, check=False)
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
    prefix = () if os.geteuid() == 0 else ("sudo", "-n")
    run((*prefix, "apt-get", "update"), log)
    run((*prefix, "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y",
         "--no-upgrade", "--no-install-recommends", *missing), log)
    if missing := missing_packages():
        raise ValueError("packages still absent after installation: " + " ".join(missing))


def install_switch(steps: tuple[tuple[str, ...], ...], log: IO[str]) -> None:
    existing = subprocess.run(("opam", "switch", "list", "--short"),
                              stdout=subprocess.PIPE, stderr=log, text=True,
                              check=True, timeout=60).stdout.splitlines()
    for argv in steps:
        if argv[:3] == ("opam", "switch", "create") and argv[3] in existing:
            continue
        run(argv, log)


def install_toolchains(root: Path, jobs: int, log: IO[str]) -> None:
    """Provide Sail's solver at startup and probe each tool before building the next."""
    run(("uv", "pip", "install", "--python", sys.executable, "--target",
         str(root / "z3"), f"z3-solver=={env.Z3_VERSION}.0"), log)
    # Sail initializes its solver even for --version. VOS_Z3_BIN is consumed by
    # run.py's environment setup, which does not run in this bootstrap process.
    solver_bin = root / "z3" / "bin"
    os.environ["PATH"] = str(solver_bin) + os.pathsep + os.environ.get("PATH", "")
    run((str(solver_bin / "z3"), "--version"), log)
    install_switch(env.SAIL_INSTALL, log)
    run((str(root / "bin" / "opam"), "exec", f"--switch={env.SAIL_SWITCH}",
         "--", "sail", "--version"), log)
    install_switch(env.ROCQ_INSTALL, log)
    run((str(root / "opam" / env.ROCQ_SWITCH / "bin" / "rocq"), "--version"), log)
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
    if platform.machine() not in OPAM_HASHES:
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
        "bootstrap_sha256": receipts.digest(Path(__file__)),
        "uv": uv_version, "opam": OPAM_VERSION, "sail": env.SAIL_VERSION,
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
            architecture, expected = OPAM_HASHES[platform.machine()]
            opam = binary_dir / "opam"
            receipts.download(f"https://github.com/ocaml/opam/releases/download/{OPAM_VERSION}/"
                              f"opam-{OPAM_VERSION}-{architecture}-linux", opam, expected)
            opam.chmod(0o755)
            run(("opam", "init", "--bare", "--no-setup", "--no-opamrc", "-y",
                 "default", "https://opam.ocaml.org"), log)
            run(("opam", "repository", "add", "rocq-released",
                 "https://rocq-prover.org/opam/released", "--dont-select", "-y"), log)
            install_toolchains(root, jobs, log)
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
