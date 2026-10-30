# SPDX-License-Identifier: Apache-2.0
"""The maintained local-link checker preserves the indexed corpus's boundaries."""

import hashlib
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from filelock import Timeout

from tests.harness import Case, ensure
from vos import lychee

_TOOLS = Path(__file__).resolve().parents[1]
_FIXTURE_EXECUTABLE = b"reviewed fixture executable"
_INSTALL_WORKER = r'''
import json, sys, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from vos import lychee
root, mode = Path(sys.argv[2]), sys.argv[3]
config = json.loads((root / "asset.json").read_text())
asset = lychee.Asset("fixture-windows-msvc", config["archive"], config["executable"])
native_platform = sys.platform
lychee.sys = SimpleNamespace(prefix=str(root / "environment"), base_prefix="other",
                            platform=native_platform)
lychee.asset_for = lambda system, machine: asset
lychee.BASE = (root / "release").as_uri()
original = lychee.receipts.download
def download(url, target, expected):
    with (root / "downloads").open("a", encoding="utf-8") as output:
        output.write("download\n")
    if mode == "fail":
        raise ValueError("fixture provider failed")
    if mode == "hold":
        (root / "entered").write_text("ready")
        deadline = time.monotonic() + 10
        while not (root / "release-owner").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("fixture owner was not released")
            time.sleep(0.02)
    original(url, target, expected)
lychee.receipts.download = download
if mode == "timeout":
    original_lock = lychee.FileLock
    def impatient_lock(*args, **kwargs):
        return original_lock(*args, **(kwargs | {"timeout": 0.1}))
    lychee.FileLock = impatient_lock
(root / ("ready-" + mode)).write_text("ready")
print(lychee.executable(), flush=True)
'''


def _installation_fixture(root: Path) -> Path:
    release = root / "release"
    release.mkdir()
    archive = release / "lychee-fixture-windows-msvc.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("lychee-fixture-windows-msvc/lychee.exe", _FIXTURE_EXECUTABLE)
    (root / "asset.json").write_text(json.dumps({
        "archive": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "executable": hashlib.sha256(_FIXTURE_EXECUTABLE).hexdigest(),
    }), encoding="utf-8")
    return root / "environment" / f"lychee-{lychee.VERSION}" / "lychee.exe"


def _installer(root: Path, mode: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, "-c", _INSTALL_WORKER, str(_TOOLS), str(root), mode],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _wait_for(path: Path) -> None:
    deadline = time.monotonic() + 10
    while not path.exists():
        if time.monotonic() >= deadline:
            raise AssertionError(f"installer fixture did not reach {path.name}")
        time.sleep(0.02)


def _finish(process: subprocess.Popen[bytes], *, success: bool) -> bytes:
    _, error = process.communicate(timeout=15)
    ensure((process.returncode == 0) is success,
           f"installer exit {process.returncode}: {error.decode('utf-8', 'replace')}")
    return error


def _shared_cold_install() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-install-") as temporary:
        root = Path(temporary)
        target = _installation_fixture(root)
        with _installer(root, "hold") as first:
            _wait_for(root / "entered")
            with _installer(root, "normal") as second:
                try:
                    _wait_for(root / "ready-normal")
                    time.sleep(0.2)
                    ensure(second.poll() is None,
                           "a second cold installer bypassed the existing owner")
                finally:
                    (root / "release-owner").write_text("release", encoding="utf-8")
                _finish(first, success=True)
                _finish(second, success=True)
        ensure(target.read_bytes() == _FIXTURE_EXECUTABLE,
               "the shared installation published different executable bytes")
        ensure((root / "downloads").read_text().splitlines() == ["download"],
               "the waiting installer did not recheck the published executable")


def _failed_install_releases_ownership() -> None:
    for mode in ("fail", "hold"):
        with tempfile.TemporaryDirectory(prefix="vos-lychee-release-") as temporary:
            root = Path(temporary)
            target = _installation_fixture(root)
            with _installer(root, mode) as first:
                if mode == "hold":
                    _wait_for(root / "entered")
                    first.terminate()
                _finish(first, success=False)
            ensure(not target.exists(), "a failed installer published an executable")
            with _installer(root, "normal") as second:
                _finish(second, success=True)
            ensure(target.read_bytes() == _FIXTURE_EXECUTABLE,
                   "installation could not resume after its owner stopped")


def _installation_wait_refuses_at_budget() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-wait-") as temporary:
        root = Path(temporary)
        target = _installation_fixture(root)
        with _installer(root, "hold") as first:
            _wait_for(root / "entered")
            try:
                with _installer(root, "timeout") as second:
                    error = _finish(second, success=False)
                ensure(b"Timeout:" in error and b".install.lock" in error,
                       "lock contention did not produce a bounded refusal")
                ensure(not target.exists(), "a timed-out waiter published an executable")
            finally:
                (root / "release-owner").write_text("release", encoding="utf-8")
            _finish(first, success=True)


def _corrupt_archive_is_not_replaced() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-corrupt-") as temporary:
        root = Path(temporary)
        target = _installation_fixture(root)
        target.parent.mkdir(parents=True)
        archive = target.parent / "lychee-fixture-windows-msvc.zip"
        archive.write_bytes(b"substituted archive")
        with _installer(root, "normal") as process:
            error = _finish(process, success=False)
        ensure(b"cached download SHA256 does not match" in error,
               "a corrupt archive was not refused by its recorded hash")
        ensure(not target.exists() and archive.read_bytes() == b"substituted archive",
               "the refusal replaced corrupt cached bytes or published an executable")


def _installation_lock_policy() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-policy-") as temporary:
        root = Path(temporary)
        target = _installation_fixture(root)
        target.parent.mkdir(parents=True)
        target.write_bytes(_FIXTURE_EXECUTABLE)
        config = json.loads((root / "asset.json").read_text())
        asset = lychee.Asset("fixture-windows-msvc", config["archive"], config["executable"])
        factory = Mock(wraps=lychee.FileLock)
        with (patch.object(lychee, "sys", SimpleNamespace(prefix=str(root / "environment"),
                                                         base_prefix="other", platform=sys.platform)),
              patch.object(lychee, "asset_for", return_value=asset),
              patch.object(lychee, "FileLock", factory)):
            ensure(lychee.executable() == target, "verified reuse selected another executable")
        factory.assert_called_once_with(target.parent / ".install.lock", timeout=180,
                                        fallback_to_soft=False, preserve_lock_file=True)


def _native_retirement_lock_compatibility() -> None:
    if sys.platform != "linux":
        return
    import fcntl

    with tempfile.TemporaryDirectory(prefix="vos-lychee-native-lock-") as temporary:
        path = Path(temporary) / ".install.lock"
        with (lychee.FileLock(path, timeout=0.1, fallback_to_soft=False, preserve_lock_file=True),
              path.open("a+b") as stream):
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("native retirement ignored an active installer lock")
        ensure(path.is_file(), "release removed the stable installation lock pathname")
        with path.open("a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            blocked = False
            try:
                with lychee.FileLock(path, timeout=0.1, fallback_to_soft=False,
                                     preserve_lock_file=True):
                    pass
            except Timeout:
                blocked = True
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            ensure(blocked, "installation bypassed native retirement's lock")


def _ordinary_links() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-links-") as directory:
        root = Path(directory)
        (root / "docs").mkdir()
        (root / "docs/target.md").write_text(
            '# Hello\n\n## caf\u00e9\n\n<a id="custom"></a>\n', encoding="utf-8")
        (root / "docs/a.md").write_text(
            '[relative](target.md#hello) [Unicode](target.md#caf%C3%A9)\n'
            '[explicit](target.md#custom) [reference][target]\n'
            '<a href="target.md#hello">HTML</a>\n'
            '[bad fragment](target.md#absent) [missing](absent.md)\n'
            '[network](https://never-contact.invalid/)\n'
            '```md\n[example](not-a-real-file.md)\n```\n\n'
            '[target]: target.md#hello\n', encoding="utf-8")
        found = lychee.findings(root, ["docs/a.md", "docs/target.md"], {})
        ensure(len(found) == 2 and any("#absent" in item for item in found)
               and any("/absent.md" in item for item in found),
               f"local file and fragment failures must be reported: {found}")


def _gitlink_roots() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-gitlinks-") as directory:
        root = Path(directory)
        (root / "README.md").write_text(
            '[pin](upstream/core) [fragment](upstream/core#section)\n'
            '[unfetched child](upstream/core/missing.md)\n', encoding="utf-8")
        found = lychee.findings(root, ["README.md"], {"upstream/core": "1" * 40})
        ensure(len(found) == 1 and "upstream/core/missing.md" in found[0],
               f"only the tracked gitlink root is checkout-independent: {found}")


def _explicit_inputs_ignore_ambient_policy() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-inputs-") as directory:
        root = Path(directory)
        (root / ".docs").mkdir()
        (root / ".docs/a.md").write_text("[broken](missing.md)\n", encoding="utf-8")
        (root / ".gitignore").write_text(".docs/\n", encoding="utf-8")
        (root / "lychee.toml").write_text('exclude = [".*"]\n', encoding="utf-8")
        found = lychee.findings(root, [".docs/a.md"], {})
        ensure(len(found) == 1 and "missing.md" in found[0],
               f"hidden/ignored indexed inputs cannot disappear behind ambient policy: {found}")
        try:
            lychee.findings(root, ["missing.md"], {})
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("a missing explicit input must refuse before dispatch")


def _structured_verdicts() -> None:
    root = Path.cwd()
    ensure(not lychee.read_result(root, 0, '{"errors":0,"error_map":{}}', ""),
           "a complete structured success must pass")
    invalid = [(0, "{}"), (0, '{"errors":1,"error_map":{}}'),
               (2, '{"errors":0,"error_map":{}}'),
               (0, '{"errors":0,"errors":0,"error_map":{}}'),
               (0, json.dumps({"errors": 1, "error_map": {"a.md": [{}]}})),
               (9, "")]
    for code, report in invalid:
        try:
            lychee.read_result(root, code, report, "stopped")
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"an incomplete or failed tool verdict passed: {code}, {report}")


def _cached_executable_identity() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-cache-") as directory:
        root = Path(directory)
        home = root / f"lychee-{lychee.VERSION}"
        home.mkdir()
        target = home / "lychee.exe"
        target.write_bytes(b"reviewed executable")
        asset = lychee.Asset("x86_64-pc-windows-msvc", "0" * 64,
                             hashlib.sha256(target.read_bytes()).hexdigest())
        download = Mock()
        with (patch.object(lychee, "sys", SimpleNamespace(prefix=str(root),
                                                         base_prefix="other", platform="win32")),
              patch.object(lychee, "asset_for", return_value=asset),
              patch.object(lychee.receipts, "download", download)):
            ensure(lychee.executable() == target, "verified cached bytes must be reused")
            target.write_bytes(b"substituted executable")
            try:
                lychee.executable()
            except ValueError:
                pass
            else:
                raise AssertionError("a changed cached executable must refuse")
            download.assert_not_called()


def cases() -> list[Case]:
    return [Case("relative/reference/HTML/Unicode links and offline boundaries", _ordinary_links),
            Case("uninitialized gitlinks exempt only the tracked root", _gitlink_roots),
            Case("explicit hidden inputs ignore ambient exclusions", _explicit_inputs_ignore_ambient_policy),
            Case("tool crashes and malformed verdicts refuse", _structured_verdicts),
            Case("cached executable bytes retain their reviewed identity", _cached_executable_identity),
            Case("independent cold installers share one verified publication", _shared_cold_install),
            Case("failed and interrupted installers release ownership", _failed_install_releases_ownership),
            Case("installation contention has a bounded refusal", _installation_wait_refuses_at_budget),
            Case("corrupt archives refuse without replacement", _corrupt_archive_is_not_replaced),
            Case("installation requires hard OS locks and a stable lock pathname", _installation_lock_policy),
            Case("native retirement and installation contend on the same lock",
                 _native_retirement_lock_compatibility)]
