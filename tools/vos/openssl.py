# SPDX-License-Identifier: Apache-2.0
"""One private, source-built OpenSSL oracle and the identity every consumer reads."""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

from vos import receipts

VERSION = "3.5.9"
REVISION = "45e844fa2a14ec92d146bd8f5778ac130b6625fb"
URL = (f"https://github.com/openssl/openssl/releases/download/openssl-{VERSION}/"
       f"openssl-{VERSION}.tar.gz")
ARCHIVE_SHA256 = "603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a"
LICENSE_SHA256 = "7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a"
SCHEMA = "verifiedos-openssl-source-build/1"
MANIFEST = "build-manifest.json"
MARKER = ".verifiedos-openssl"
ARTIFACTS = ("bin/openssl", "lib/libcrypto.so.3", "lib/libssl.so.3", "ssl/openssl.cnf")


def pin() -> dict[str, str]:
    return {"version": VERSION, "revision": REVISION, "url": URL,
            "archive_sha256": ARCHIVE_SHA256, "license_sha256": LICENSE_SHA256,
            "license": "Apache-2.0"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def root() -> Path:
    value = os.environ.get("VOS_OPENSSL_ROOT", "")
    if not value or not Path(value).is_absolute():
        raise ValueError("set VOS_OPENSSL_ROOT to a private bootstrap_openssl.py installation")
    path = Path(value)
    if path.is_symlink() or path.resolve() != path:
        raise ValueError("VOS_OPENSSL_ROOT must name the installation directly")
    return path


def environment(prefix: Path) -> dict[str, str]:
    return {"VOS_OPENSSL_ROOT": str(prefix), "OPENSSL_CONF": str(prefix / "ssl/openssl.cnf"),
            "OPENSSL_MODULES": str(prefix / "lib/ossl-modules")}


def _run(argv: list[str], work: Path) -> str:
    result = subprocess.run(argv, cwd=work, capture_output=True, text=True,
                            check=False, timeout=60)
    if result.returncode:
        raise ValueError(f"OpenSSL identity command failed: {argv[0]}: {result.stderr[-1000:]}")
    return result.stdout.strip()


def identity(prefix: Path | None = None) -> dict[str, Any]:
    """Refuse stale source/build records, binaries or a foreign loaded library."""
    prefix = root() if prefix is None else prefix
    if not prefix.is_absolute() or prefix.is_symlink() or prefix.resolve() != prefix:
        raise ValueError("OpenSSL installation must be an absolute direct path")
    if (prefix / MARKER).read_text(encoding="utf-8") != "1\n":
        raise ValueError("OpenSSL installation is not owned by its bootstrap")
    for key, wanted in environment(prefix).items():
        if key != "VOS_OPENSSL_ROOT" and os.environ.get(key, wanted) != wanted:
            raise ValueError(f"foreign OpenSSL configuration: {key}")
    manifest = prefix / MANIFEST
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("passed") is not True
            or record.get("source") != pin() or record.get("prefix") != str(prefix)):
        raise ValueError("OpenSSL source/build identity is not the selected release")
    steps = record.get("steps")
    if (not isinstance(steps, list) or len(steps) != 3
            or any(not isinstance(step, dict) for step in steps)
            or [step.get("name") for step in steps] != ["configure", "build", "install"]
            or any(step.get("exit") != 0 for step in steps)):
        raise ValueError("OpenSSL source build did not complete")
    bindings = record.get("bindings")
    required = {*ARTIFACTS, "source/LICENSE.txt", "configure.log", "build.log", "install.log"}
    if not isinstance(bindings, dict) or set(bindings) != required:
        raise ValueError("OpenSSL build bindings are incomplete")
    for relative, digest in bindings.items():
        path = prefix / relative
        if (path.is_symlink() or not path.resolve().is_relative_to(prefix)
                or not path.is_file() or _sha(path) != digest):
            raise ValueError(f"stale OpenSSL build identity: {relative}")
    if bindings["source/LICENSE.txt"] != LICENSE_SHA256:
        raise ValueError("OpenSSL source license differs from the selected release")
    executable = prefix / "bin/openssl"
    version = _run([str(executable), "version", "-a"], prefix)
    if (not version.startswith(f"OpenSSL {VERSION} ")
            or f"(Library: OpenSSL {VERSION} " not in version.splitlines()[0]):
        raise ValueError("OpenSSL executable is not the selected release")
    linkage = _run(["ldd", str(executable)], prefix)
    pairs = re.findall(r"(lib(?:crypto|ssl)\.so\.3) => (\S+)", linkage)
    loaded = dict(pairs)
    if len(pairs) != 2 or set(loaded) != {"libcrypto.so.3", "libssl.so.3"}:
        raise ValueError("OpenSSL loaded-library identity incomplete")
    for name, path in loaded.items():
        if Path(path).resolve() != prefix / "lib" / name:
            raise ValueError(f"foreign OpenSSL loaded library: {name}: {path}")
    return {"version": version, "source": pin(), "build_manifest": str(manifest),
            "build_manifest_sha256": _sha(manifest), "binaries": {
                str(prefix / name): bindings[name] for name in ARTIFACTS[:3]},
            "configuration_sha256": bindings["ssl/openssl.cnf"]}


def executable() -> Path:
    prefix = root()
    identity(prefix)
    return prefix / "bin/openssl"


def record(work: Path) -> dict[str, Any]:
    selected = identity()
    prefix = root()
    shutil.copyfile(prefix / "source/LICENSE.txt", work / "OpenSSL-LICENSE.txt")
    shutil.copyfile(prefix / MANIFEST, work / "OpenSSL-build-manifest.json")
    return selected


def install(prefix: Path, jobs: int) -> dict[str, Any]:
    """Build an exact archive in an owned native prefix; never replace system OpenSSL."""
    if sys.platform != "linux" or not prefix.is_absolute() or not 1 <= jobs <= 6:
        raise ValueError("OpenSSL bootstrap requires Linux, an absolute prefix and 1..6 jobs")
    if (prefix.is_symlink() or prefix.resolve() != prefix
            or str(prefix).startswith(("/mnt/", "/tmp/"))):  # noqa: S108 (rejecting volatile output)
        raise ValueError("OpenSSL bootstrap requires a direct persistent native prefix")
    if (prefix == Path("/") or prefix == Path.home()
            or prefix.is_relative_to(Path(__file__).resolve().parents[2])):
        raise ValueError("OpenSSL prefix must be private and outside the checkout")
    marker = prefix / MARKER
    if prefix.exists() and any(prefix.iterdir()):
        if marker.is_symlink() or not marker.is_file() or marker.read_text() != "1\n":
            raise ValueError("refusing a nonempty unowned OpenSSL prefix")
        if (prefix / MANIFEST).exists():
            return identity(prefix)
    prefix.mkdir(parents=True, exist_ok=True)
    marker.write_text("1\n", encoding="utf-8")
    # A process lock protects both a first build and a resumed incomplete installation.
    import fcntl
    with (prefix / ".install.lock").open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if (prefix / MANIFEST).exists():
            return identity(prefix)
        return _install(prefix, jobs)


def _install(prefix: Path, jobs: int) -> dict[str, Any]:
    targets = {"aarch64": "linux-aarch64", "arm64": "linux-aarch64", "x86_64": "linux-x86_64"}
    target = targets.get(platform.machine().lower())
    if target is None:
        raise ValueError(f"no reviewed OpenSSL source target for {platform.machine()}")
    archive = prefix / "source.tar.gz"
    receipts.download(URL, archive, ARCHIVE_SHA256)
    source = prefix / "source"
    if source.exists():
        if source.is_symlink() or source.resolve().parent != prefix:
            raise ValueError("OpenSSL source directory escaped its owned prefix")
        shutil.rmtree(source)
    staging = prefix / "unpack"
    if staging.exists():
        raise ValueError("incomplete OpenSSL unpack directory requires inspection")
    staging.mkdir()
    with tarfile.open(archive) as contents:
        contents.extractall(staging, filter="data")
    (staging / f"openssl-{VERSION}").rename(source)
    staging.rmdir()
    if _sha(source / "LICENSE.txt") != LICENSE_SHA256:
        raise ValueError("OpenSSL selected archive license mismatch")
    commands = [
        ("configure", ["perl", "Configure", target, f"--prefix={prefix}",
                       f"--openssldir={prefix / 'ssl'}", "--libdir=lib", "shared", "no-tests",
                       f"-Wl,-rpath,{prefix / 'lib'}"]),
        ("build", ["make", f"-j{jobs}", "build_sw"]),
        ("install", ["make", "install_sw", "install_ssldirs"]),
    ]
    record: dict[str, Any] = {"schema": SCHEMA, "passed": False, "source": pin(),
                              "prefix": str(prefix), "steps": [], "tools": {}}
    for name in ("gcc", "make", "perl"):
        path = shutil.which(name)
        if path is None:
            raise ValueError(f"OpenSSL bootstrap requires {name}")
        record["tools"][name] = {"path": path, "sha256": _sha(Path(path))}
    for name, argv in commands:
        print(f"OpenSSL {VERSION}: {name}", flush=True)
        started = time.monotonic()
        with (prefix / f"{name}.log").open("w") as log:
            done = subprocess.run(argv, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=False)
        record["steps"].append({"name": name, "argv": argv, "exit": done.returncode,
                                 "seconds": time.monotonic() - started})
        receipts.write(prefix / "build-progress.json", record)
        if done.returncode:
            raise ValueError(f"OpenSSL {name} failed; see {prefix / (name + '.log')}")
    record["bindings"] = {name: _sha(prefix / name) for name in (
        *ARTIFACTS, "source/LICENSE.txt", "configure.log", "build.log", "install.log")}
    record["passed"] = True
    receipts.write(prefix / MANIFEST, record)
    return identity(prefix)
