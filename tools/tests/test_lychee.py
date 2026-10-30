# SPDX-License-Identifier: Apache-2.0
"""The maintained local-link checker preserves the indexed corpus's boundaries."""

import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from filelock import Timeout

from tests.harness import TOOLS, Case, ensure
from vos import lychee


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
        factory = Mock(wraps=lychee.FileLock)
        with (patch.object(lychee, "sys", SimpleNamespace(prefix=str(root),
                                                         base_prefix="other", platform="win32")),
              patch.object(lychee, "asset_for", return_value=asset),
              patch.object(lychee, "FileLock", factory),
              patch.object(lychee.receipts, "download", download)):
            ensure(lychee.executable() == target, "verified cached bytes must be reused")
            factory.assert_called_once_with(home / ".install.lock", timeout=180,
                                            fallback_to_soft=False, preserve_lock_file=True)
            target.write_bytes(b"substituted executable")
            try:
                lychee.executable()
            except ValueError:
                pass
            else:
                raise AssertionError("a changed cached executable must refuse")
            download.assert_not_called()


_INSTALLER = """
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])
from vos import lychee

root, source = Path(sys.argv[2]), Path(sys.argv[3])
asset = lychee.Asset('x86_64-pc-windows-msvc',
                     lychee.receipts.digest(source), sys.argv[4])
lychee.sys = SimpleNamespace(prefix=str(root / 'cache'),
                            base_prefix='other', platform='win32')
lychee.ASSETS['windows'] = asset
atomic_path = lychee.receipts.atomic_path

@contextmanager
def counted_publication(path):
    with atomic_path(path) as pending:
        yield pending
    if path.name == asset.executable:
        (root / f'published-{os.getpid()}').write_text(str(path), encoding='utf-8')

def download(url, target, expected):
    if target.exists():
        if lychee.receipts.digest(target) != expected:
            raise ValueError('cached fixture archive differs from its pin')
        return
    (root / f'download-{os.getpid()}').write_text(url, encoding='utf-8')
    if lychee.receipts.digest(source) != expected:
        raise AssertionError('fixture archive differs from its pin')
    if sys.argv[5] == 'hold':
        print('holding', flush=True)
        if input() != 'release':
            raise AssertionError('missing owner release')
    # Hold the cold path open while the other ready processes enter it.
    time.sleep(0.25)
    with atomic_path(target) as pending:
        pending.write_bytes(source.read_bytes())

lychee.receipts.atomic_path = counted_publication
if sys.argv[5] != 'cached':
    lychee.receipts.download = download
if sys.argv[5] == 'timeout':
    original_lock = lychee.FileLock
    def impatient_lock(*args, **kwargs):
        return original_lock(*args, **(kwargs | {'timeout': 0.1}))
    lychee.FileLock = impatient_lock
print('ready', flush=True)
if input() != 'start':
    raise AssertionError('missing simultaneous start')
try:
    target = lychee.executable()
except ValueError as exc:
    if sys.argv[5] not in ('failure', 'cached'):
        raise
    print(json.dumps({'error': str(exc)}), flush=True)
    # Remain alive: recovery must not depend on process exit releasing the lock.
    input()
else:
    print(json.dumps({'path': str(target),
                      'digest': lychee.receipts.digest(target)}), flush=True)
"""


def _installer_archive(root: Path, payload: bytes, name: str) -> Path:
    archive = root / name
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("lychee-x86_64-pc-windows-msvc/lychee.exe", payload)
    return archive


@contextmanager
def _installer(root: Path, source: Path, expected: str,
               mode: str = "success") -> Generator[subprocess.Popen[str]]:
    with subprocess.Popen(
            [sys.executable, "-c", _INSTALLER, str(TOOLS), str(root), str(source), expected, mode],
            cwd=TOOLS.parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8") as child:
        try:
            if child.stdout is None or child.stdin is None:
                raise AssertionError("installer fixture requires command and result pipes")
            ensure(child.stdout.readline() == "ready\n", "installer fixture failed before start")
            yield child
        finally:
            if child.poll() is None:
                child.kill()


def _start_installer(child: subprocess.Popen[str]) -> None:
    if child.stdin is None:
        raise AssertionError("installer fixture requires a command pipe")
    child.stdin.write("start\n")
    child.stdin.flush()


def _installed(child: subprocess.Popen[str], expected: Path, digest: str) -> None:
    output, error = child.communicate(timeout=20)
    ensure(child.returncode == 0, f"installer process failed: {error}")
    ensure(json.loads(output) == {"path": str(expected), "digest": digest},
           f"every process must return the same verified executable: {output}")


def _concurrent_cold_install() -> None:
    with (tempfile.TemporaryDirectory(prefix="vos-lychee-concurrent-") as directory,
          ExitStack() as processes):
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        children = [processes.enter_context(_installer(root, source, digest)) for _ in range(3)]
        for child in children:
            _start_installer(child)
        target = root / "cache" / f"lychee-{lychee.VERSION}" / "lychee.exe"
        for child in children:
            _installed(child, target, digest)
        ensure(target.read_bytes() == payload, "the shared executable must retain pinned bytes")
        ensure(len(list(root.glob("download-*"))) == 1,
               "simultaneous cold callers must download the shared release only once")
        ensure(len(list(root.glob("published-*"))) == 1,
               "simultaneous cold callers must publish the shared executable only once")


def _failed_install_releases_lock() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-recovery-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        bad = _installer_archive(root, b"substituted executable", "bad.zip")
        good = _installer_archive(root, payload, "good.zip")
        target = root / "cache" / f"lychee-{lychee.VERSION}" / "lychee.exe"
        with _installer(root, bad, digest, "failure") as failed:
            _start_installer(failed)
            if failed.stdout is None:
                raise AssertionError("installer fixture requires a result pipe")
            refusal = json.loads(failed.stdout.readline())
            ensure("extracted Lychee executable hash differs" in refusal.get("error", ""),
                   f"substituted release bytes must refuse publication: {refusal}")
            ensure(not target.exists() and not list(root.glob("published-*")),
                   "a failed verification must publish no executable")
            # Remove the deliberately invalid release before trying a corrected fixture.
            archives = list(target.parent.glob("*.zip"))
            ensure(len(archives) == 1, "the refused release must leave its authenticated archive")
            archives[0].unlink()
            with _installer(root, good, digest) as recovered:
                _start_installer(recovered)
                _installed(recovered, target, digest)
            ensure(failed.poll() is None,
                   "recovery must acquire the cache while the failed caller is still alive")
        ensure(target.read_bytes() == payload, "a subsequent verified install must recover")
        ensure(len(list(root.glob("download-*"))) == 2
               and len(list(root.glob("published-*"))) == 1,
               "one refused release and one recovery must publish only the verified executable")


def _bounded_installation_wait() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-wait-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        target = root / "cache" / f"lychee-{lychee.VERSION}" / "lychee.exe"
        with _installer(root, source, digest, "hold") as owner:
            _start_installer(owner)
            if owner.stdout is None or owner.stdin is None:
                raise AssertionError("installer fixture requires command and result pipes")
            ensure(owner.stdout.readline() == "holding\n", "the provider never acquired its lock")
            with _installer(root, source, digest, "timeout") as waiter:
                _start_installer(waiter)
                _, error = waiter.communicate(timeout=20)
                ensure(waiter.returncode != 0 and "Timeout:" in error and ".install.lock" in error,
                       f"contention must refuse within its budget: {error}")
            ensure(not target.exists(), "a timed-out waiter published an executable")
            owner.stdin.write("release\n")
            owner.stdin.flush()
            _installed(owner, target, digest)


def _terminated_installer_releases_lock() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-termination-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        target = root / "cache" / f"lychee-{lychee.VERSION}" / "lychee.exe"
        with _installer(root, source, digest, "hold") as owner:
            _start_installer(owner)
            if owner.stdout is None:
                raise AssertionError("installer fixture requires a result pipe")
            ensure(owner.stdout.readline() == "holding\n", "the provider never acquired its lock")
            owner.kill()
            owner.communicate(timeout=20)
        ensure(not target.exists(), "a terminated provider published an executable")
        with _installer(root, source, digest) as recovered:
            _start_installer(recovered)
            _installed(recovered, target, digest)
        ensure(target.read_bytes() == payload, "the OS did not release terminated ownership")


def _corrupt_cached_archive_refuses() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-corrupt-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        home = root / "cache" / f"lychee-{lychee.VERSION}"
        home.mkdir(parents=True)
        archive = home / "lychee-x86_64-pc-windows-msvc.zip"
        archive.write_bytes(b"substituted archive")
        with _installer(root, source, digest, "cached") as failed:
            _start_installer(failed)
            if failed.stdout is None:
                raise AssertionError("installer fixture requires a result pipe")
            refusal = json.loads(failed.stdout.readline())
            ensure("cached download SHA256 does not match" in refusal.get("error", ""),
                   f"corrupt cache bytes must refuse before download or publication: {refusal}")
        ensure(archive.read_bytes() == b"substituted archive"
               and not (home / "lychee.exe").exists(),
               "the refusal replaced cached bytes or published an executable")


def _native_retirement_lock_compatibility() -> None:
    if sys.platform != "linux":
        return
    import fcntl

    with tempfile.TemporaryDirectory(prefix="vos-lychee-native-lock-") as directory:
        path = Path(directory) / ".install.lock"
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


def cases() -> list[Case]:
    return [Case("relative/reference/HTML/Unicode links and offline boundaries", _ordinary_links),
            Case("uninitialized gitlinks exempt only the tracked root", _gitlink_roots),
            Case("explicit hidden inputs ignore ambient exclusions", _explicit_inputs_ignore_ambient_policy),
            Case("tool crashes and malformed verdicts refuse", _structured_verdicts),
            Case("cached executable bytes retain their reviewed identity", _cached_executable_identity),
            Case("simultaneous cold processes install one verified executable", _concurrent_cold_install),
            Case("failed installation releases the cache for another live process",
                 _failed_install_releases_lock),
            Case("installation contention has a bounded refusal", _bounded_installation_wait),
            Case("terminated installation releases OS ownership", _terminated_installer_releases_lock),
            Case("corrupt cached archives refuse without replacement", _corrupt_cached_archive_refuses),
            Case("native retirement and installation contend on the same lock",
                 _native_retirement_lock_compatibility)]
