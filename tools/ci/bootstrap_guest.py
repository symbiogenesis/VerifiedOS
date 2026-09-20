#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Install the guest gate's toolchains in one private, native Linux directory."""

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from vos import env  # noqa: E402  (standalone bootstrap precedes the locked environment)
from vos.cli import rtl  # noqa: E402

OPAM_VERSION = "2.5.2"
OPAM_HASHES = {
    "aarch64": ("arm64", "c4106ece84bcb60c68342573d2d6b4f0d6770ee088015c2216adc83d8854dcf9"),
    "x86_64": ("x86_64", "edfca2630c373b44b7ee1c2f81cd8dcf67468d0db57d6c02158de553ac63dbd4"),
}
PACKAGES = tuple(dict.fromkeys((
    "build-essential", "bubblewrap", "ca-certificates", "curl", "unzip", "patch",
    "pkg-config", "m4", "cmake", "ninja-build", "libgmp-dev", "clang", "ccache",
    "device-tree-compiler", "git", "time", *rtl.VERILATOR_PACKAGES,
)))
MARKER = ".verifiedos-guest-root"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url: str, target: Path, expected: str) -> None:
    """Verify both newly downloaded bytes and reused downloads before executing."""
    if target.exists():
        if digest(target) != expected:
            raise ValueError(f"{target}: cached download SHA-256 does not match {expected}")
        return
    pending = target.with_suffix(".download")
    try:
        # Callers supply an HTTPS release URL, never input from a workflow expression.
        with (urllib.request.urlopen(url, timeout=120) as response,  # noqa: S310
              pending.open("wb") as stream):
            shutil.copyfileobj(response, stream)
        if digest(pending) != expected:
            raise ValueError(f"{url}: downloaded SHA-256 does not match {expected}")
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)


def prepare_root(root: Path) -> Path:
    """Reject accidental reuse of a developer's directory or non-native storage."""
    if not root.is_absolute():
        raise ValueError("--root must be an absolute path")
    root = root.resolve()
    checkout = TOOLS.parent.resolve()
    if root == Path(root.anchor) or root == Path.home().resolve() or root.is_relative_to(checkout):
        raise ValueError("--root must be a private directory outside the checkout and home root")
    # These paths are rejected, never used for a temporary file.
    if root.is_relative_to(Path("/tmp")) or root.is_relative_to(Path("/var/tmp")):  # noqa: S108
        raise ValueError("--root must preserve logs outside temporary storage")
    kind = env.filesystem(root)
    if kind is None or kind in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS:
        raise ValueError(f"--root must be on a native persistent filesystem, found {kind}")
    marker = root / MARKER
    if root.exists() and any(root.iterdir()) and not marker.is_file():
        raise ValueError(f"refusing nonempty unowned bootstrap directory {root}")
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("1\n", encoding="utf-8", newline="")
    return root


def environment(root: Path, jobs: int) -> dict[str, str]:
    return {
        "VOS_GUEST_ROOT": str(root), "VOS_LANE": "",
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
    absent: list[str] = []
    for package in PACKAGES:
        done = subprocess.run(("dpkg-query", "-W", "-f=${Status}", package),
                              capture_output=True, text=True, check=False)
        if done.returncode or done.stdout.strip() != "install ok installed":
            absent.append(package)
    return absent


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
                              capture_output=True, text=True, check=True).stdout.splitlines()
    for argv in steps:
        if argv[:3] == ("opam", "switch", "create") and argv[3] in existing:
            continue
        run(argv, log)


def export_environment(values: dict[str, str], binary_dir: Path,
                       github_env: Path | None, github_path: Path | None) -> None:
    if any("\n" in value or "\r" in value for value in (*values.values(), str(binary_dir))):
        raise ValueError("environment paths must not contain line breaks")
    if github_env:
        with github_env.open("a", encoding="utf-8", newline="") as stream:
            stream.writelines(f"{key}={value}\n" for key, value in values.items())
    if github_path:
        with github_path.open("a", encoding="utf-8", newline="") as stream:
            stream.write(f"{binary_dir}\n")


def activation(values: dict[str, str], binary_dir: Path) -> str:
    """A sourceable shell file; values cannot become shell syntax."""
    exports = [f"export {key}={shlex.quote(value)}" for key, value in values.items()]
    exports.append(f"export PATH={shlex.quote(str(binary_dir))}:\"$PATH\"")
    return "\n".join(exports) + "\n"


def bootstrap(args: argparse.Namespace) -> int:
    if sys.platform != "linux":
        raise ValueError("guest bootstrap runs on Linux; invoke it inside the assigned guest lane")
    if args.jobs < 1:
        raise ValueError("--jobs must be positive")
    if platform.machine() not in OPAM_HASHES:
        raise ValueError(f"no reviewed opam binary for {platform.machine()}")
    manifest = tomllib.loads((TOOLS / "pyproject.toml").read_text(encoding="utf-8"))
    uv_version = manifest["tool"]["uv"]["required-version"].removeprefix("==")
    found_uv = subprocess.run(("uv", "--version"), capture_output=True, text=True,
                              check=True).stdout.split()
    if len(found_uv) < 2 or found_uv[1] != uv_version:
        raise ValueError(f"bootstrap requires uv {uv_version} from tools/pyproject.toml")
    root = prepare_root(args.root)
    values = environment(root, args.jobs)
    for name in ("VOS_BUILD_ROOT", "VOS_LOG_DIR", "TMPDIR", "CCACHE_DIR", "UV_CACHE_DIR"):
        Path(values[name]).mkdir(parents=True, exist_ok=True)
    binary_dir = root / "bin"
    binary_dir.mkdir(exist_ok=True)
    os.environ.update(values)
    os.environ["PATH"] = str(binary_dir) + os.pathsep + os.environ.get("PATH", "")
    (root / "logs" / "environment.json").write_text(json.dumps(values, indent=2) + "\n",
                                                     encoding="utf-8", newline="")
    started = time.monotonic()
    record: dict[str, object] = {
        "schema": 1, "started_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(), "python": sys.version,
        "source_revision": subprocess.run(
            ("git", "-C", str(TOOLS.parent), "rev-parse", "HEAD"), capture_output=True,
            text=True, check=True, env=os.environ | env.git_env(TOOLS.parent)).stdout.strip(),
        "bootstrap_sha256": digest(Path(__file__)),
        "uv": uv_version, "opam": OPAM_VERSION, "sail": env.SAIL_VERSION,
        "rocq": env.ROCQ_VERSION, "z3": env.Z3_VERSION, "verilator": rtl.VERILATOR_PIN,
        "snapshots": {name: digest(TOOLS / "opam" / f"{name}.lock")
                      for name in ("sail", "rocq")}, "exit_code": 1,
    }
    log_path = root / "logs" / "bootstrap.log"
    print(f"Bootstrap log: {log_path}", flush=True)
    with env.hold_lock(root / "bootstrap", "guest bootstrap"), log_path.open(
            "w", encoding="utf-8", newline="") as log:
        try:
            system_packages(args.install_system, log)
            architecture, expected = OPAM_HASHES[platform.machine()]
            opam = binary_dir / "opam"
            download(f"https://github.com/ocaml/opam/releases/download/{OPAM_VERSION}/"
                     f"opam-{OPAM_VERSION}-{architecture}-linux", opam, expected)
            opam.chmod(0o755)
            run(("opam", "init", "--bare", "--no-setup", "--no-opamrc", "-y",
                 "default", "https://opam.ocaml.org"), log)
            run(("opam", "repository", "add", "rocq-released",
                 "https://rocq-prover.org/opam/released", "--dont-select", "-y"), log)
            install_switch(env.SAIL_INSTALL, log)
            install_switch(env.ROCQ_INSTALL, log)
            run(("uv", "pip", "install", "--python", sys.executable, "--target",
                 str(root / "z3"), f"z3-solver=={env.Z3_VERSION}.0"), log)
            run((sys.executable, str(TOOLS / "run.py"), "rtl", "install",
                 "--jobs", str(args.jobs)), log)
            run((str(opam), "exec", f"--switch={env.SAIL_SWITCH}", "--", "sail", "--version"), log)
            run((str(env.opam_root() / env.ROCQ_SWITCH / "bin" / "rocq"), "--version"), log)
            run((str(root / "z3" / "bin" / "z3"), "--version"), log)
            export_environment(values, binary_dir, args.github_env, args.github_path)
            (root / "environment.sh").write_text(activation(values, binary_dir),
                                                  encoding="utf-8", newline="")
            record["exit_code"] = 0
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            record["error"] = str(error)
            log.write(f"FAIL bootstrap: {error}\n")
            print(f"FAIL bootstrap: {error}; see {log_path}", file=sys.stderr)
        finally:
            record["seconds"] = round(time.monotonic() - started, 2)
            (root / "logs" / "bootstrap.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
    return 0 if record["exit_code"] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="private persistent native directory outside the source checkout")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--install-system", action="store_true",
                        help="install absent Ubuntu packages using root or passwordless sudo")
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--github-path", type=Path)
    args = parser.parse_args(argv)
    try:
        return bootstrap(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL bootstrap: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
