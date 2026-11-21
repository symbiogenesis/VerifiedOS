# SPDX-License-Identifier: Apache-2.0
"""Independent archive-layout and cache-ownership controls for pinned validator binaries."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from filelock import Timeout

from tests.harness import TOOLS, Case, ensure
from vos import pinned_binary, receipts

WINDOWS = "x86_64-pc-windows-msvc"
LINUX = "x86_64-unknown-linux-gnu"


_INSTALLER = """
import json
import os
import sys
import time
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])
from vos import pinned_binary, receipts

adapter = import_module(sys.argv[6])

root, source = Path(sys.argv[2]), Path(sys.argv[3])
asset = adapter.Asset('x86_64-pc-windows-msvc', receipts.digest(source), sys.argv[4])
pinned_binary.sys = SimpleNamespace(prefix=str(root / 'cache'),
                                    base_prefix='other', platform='win32')
adapter.ASSETS['windows'] = asset
atomic_path = receipts.atomic_path

@contextmanager
def counted_publication(path):
    with atomic_path(path) as pending:
        yield pending
    if path.name == asset.executable:
        (root / f'published-{os.getpid()}').write_text(str(path), encoding='utf-8')

def download(url, target, expected):
    if target.exists():
        if receipts.digest(target) != expected:
            raise ValueError('cached fixture archive differs from its pin')
        return
    (root / f'download-{os.getpid()}').write_text(url, encoding='utf-8')
    if receipts.digest(source) != expected:
        raise AssertionError('fixture archive differs from its pin')
    if sys.argv[5] == 'hold':
        print('holding', flush=True)
        if input() != 'release':
            raise AssertionError('missing owner release')
    # Hold the cold path open while the other ready processes enter it.
    time.sleep(0.25)
    with atomic_path(target) as pending:
        pending.write_bytes(source.read_bytes())

receipts.atomic_path = counted_publication
if sys.argv[5] != 'cached':
    receipts.download = download
if sys.argv[5] == 'timeout':
    original_lock = pinned_binary.FileLock
    def impatient_lock(*args, **kwargs):
        return original_lock(*args, **(kwargs | {'timeout': 0.1}))
    pinned_binary.FileLock = impatient_lock
print('ready', flush=True)
if input() != 'start':
    raise AssertionError('missing simultaneous start')
try:
    target = adapter.executable()
except ValueError as exc:
    if sys.argv[5] not in ('failure', 'cached'):
        raise
    print(json.dumps({'error': str(exc)}), flush=True)
    # Remain alive: recovery must not depend on process exit releasing the lock.
    input()
else:
    print(json.dumps({'path': str(target),
                      'digest': receipts.digest(target)}), flush=True)
"""


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


def _native_retirement_lock_compatibility() -> None:
    if sys.platform != "linux":
        return
    import fcntl

    with tempfile.TemporaryDirectory(prefix="vos-validator-native-lock-") as directory:
        path = Path(directory) / ".install.lock"
        with (pinned_binary.FileLock(path, timeout=0.1, fallback_to_soft=False, preserve_lock_file=True),
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
                with pinned_binary.FileLock(path, timeout=0.1, fallback_to_soft=False,
                                            preserve_lock_file=True):
                    pass
            except Timeout:
                blocked = True
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            ensure(blocked, "installation bypassed native retirement's lock")


@dataclass(frozen=True)
class InstallerFixture:
    adapter: ModuleType
    label: str
    archive_stem: str
    member: str

    @property
    def windows_exe(self) -> str:
        return self.label.lower() + ".exe"

    @property
    def home(self) -> str:
        return f"{self.label.lower()}-{self.adapter.VERSION}"

    def _cached_executable_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-validator-cache-") as directory:
            root = Path(directory)
            home = root / self.home
            home.mkdir()
            target = home / self.windows_exe
            target.write_bytes(b"reviewed executable")
            asset = self.adapter.Asset(WINDOWS, "0" * 64,
                                      hashlib.sha256(target.read_bytes()).hexdigest())
            download = Mock()
            factory = Mock(wraps=pinned_binary.FileLock)
            with (patch.object(pinned_binary, "sys", SimpleNamespace(prefix=str(root),
                                                                    base_prefix="other", platform="win32")),
                  patch.dict(self.adapter.ASSETS, {"windows": asset}),
                  patch.object(pinned_binary, "FileLock", factory),
                  patch.object(receipts, "download", download)):
                ensure(self.adapter.executable() == target, "verified cached bytes must be reused")
                factory.assert_called_once_with(home / ".install.lock", timeout=180,
                                                fallback_to_soft=False, preserve_lock_file=True)
                target.write_bytes(b"substituted executable")
                try:
                    self.adapter.executable()
                except ValueError:
                    pass
                else:
                    raise AssertionError("a changed cached executable must refuse")
                download.assert_not_called()

    def _installer_archive(self, root: Path, payload: bytes, name: str) -> Path:
        archive = root / name
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(self.member.format(target=WINDOWS, exe=self.windows_exe), payload)
        return archive

    @contextmanager
    def _installer(self, root: Path, source: Path, expected: str,
                   mode: str = "success") -> Generator[subprocess.Popen[str]]:
        with subprocess.Popen(
                [sys.executable, "-c", _INSTALLER, str(TOOLS), str(root), str(source), expected, mode,
                 self.adapter.__name__],
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

    def _concurrent_cold_install(self) -> None:
        with (tempfile.TemporaryDirectory(prefix="vos-validator-concurrent-") as directory,
              ExitStack() as processes):
            root = Path(directory)
            payload = b"reviewed fixture executable"
            digest = hashlib.sha256(payload).hexdigest()
            source = self._installer_archive(root, payload, "release.zip")
            children = [processes.enter_context(self._installer(root, source, digest)) for _ in range(3)]
            for child in children:
                _start_installer(child)
            target = root / "cache" / self.home / self.windows_exe
            for child in children:
                _installed(child, target, digest)
            ensure(target.read_bytes() == payload, "the shared executable must retain pinned bytes")
            ensure(len(downloads := list(root.glob("download-*"))) == 1,
                   "simultaneous cold callers must download the shared release only once")
            expected_url = f"{self.adapter.BASE}/{self.archive_stem.format(target=WINDOWS)}.zip"
            ensure(downloads[0].read_text(encoding="utf-8") == expected_url, "wrong Windows release URL")
            ensure(len(list(root.glob("published-*"))) == 1,
                   "simultaneous cold callers must publish the shared executable only once")

    def _failed_install_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-validator-recovery-") as directory:
            root = Path(directory)
            payload = b"reviewed fixture executable"
            digest = hashlib.sha256(payload).hexdigest()
            bad = self._installer_archive(root, b"substituted executable", "bad.zip")
            good = self._installer_archive(root, payload, "good.zip")
            target = root / "cache" / self.home / self.windows_exe
            with self._installer(root, bad, digest, "failure") as failed:
                _start_installer(failed)
                if failed.stdout is None:
                    raise AssertionError("installer fixture requires a result pipe")
                refusal = json.loads(failed.stdout.readline())
                ensure(f"extracted {self.label} executable hash differs" in refusal.get("error", ""),
                       f"substituted release bytes must refuse publication: {refusal}")
                ensure(not target.exists() and not list(root.glob("published-*")),
                       "a failed verification must publish no executable")
                # Remove the deliberately invalid release before trying a corrected fixture.
                archives = list(target.parent.glob("*.zip"))
                ensure(len(archives) == 1, "the refused release must leave its authenticated archive")
                archives[0].unlink()
                with self._installer(root, good, digest) as recovered:
                    _start_installer(recovered)
                    _installed(recovered, target, digest)
                ensure(failed.poll() is None,
                       "recovery must acquire the cache while the failed caller is still alive")
            ensure(target.read_bytes() == payload, "a subsequent verified install must recover")
            ensure(len(list(root.glob("download-*"))) == 2
                   and len(list(root.glob("published-*"))) == 1,
                   "one refused release and one recovery must publish only the verified executable")

    def _bounded_installation_wait(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-validator-wait-") as directory:
            root = Path(directory)
            payload = b"reviewed fixture executable"
            digest = hashlib.sha256(payload).hexdigest()
            source = self._installer_archive(root, payload, "release.zip")
            target = root / "cache" / self.home / self.windows_exe
            with self._installer(root, source, digest, "hold") as owner:
                _start_installer(owner)
                if owner.stdout is None or owner.stdin is None:
                    raise AssertionError("installer fixture requires command and result pipes")
                ensure(owner.stdout.readline() == "holding\n", "the provider never acquired its lock")
                with self._installer(root, source, digest, "timeout") as waiter:
                    _start_installer(waiter)
                    _, error = waiter.communicate(timeout=20)
                    ensure(waiter.returncode != 0 and "Timeout:" in error and ".install.lock" in error,
                           f"contention must refuse within its budget: {error}")
                ensure(not target.exists(), "a timed-out waiter published an executable")
                owner.stdin.write("release\n")
                owner.stdin.flush()
                _installed(owner, target, digest)

    def _terminated_installer_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-validator-termination-") as directory:
            root = Path(directory)
            payload = b"reviewed fixture executable"
            digest = hashlib.sha256(payload).hexdigest()
            source = self._installer_archive(root, payload, "release.zip")
            target = root / "cache" / self.home / self.windows_exe
            with self._installer(root, source, digest, "hold") as owner:
                _start_installer(owner)
                if owner.stdout is None:
                    raise AssertionError("installer fixture requires a result pipe")
                ensure(owner.stdout.readline() == "holding\n", "the provider never acquired its lock")
                owner.kill()
                owner.communicate(timeout=20)
            ensure(not target.exists(), "a terminated provider published an executable")
            with self._installer(root, source, digest) as recovered:
                _start_installer(recovered)
                _installed(recovered, target, digest)
            ensure(target.read_bytes() == payload, "the OS did not release terminated ownership")

    def _corrupt_cached_archive_refuses(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-validator-corrupt-") as directory:
            root = Path(directory)
            payload = b"reviewed fixture executable"
            digest = hashlib.sha256(payload).hexdigest()
            source = self._installer_archive(root, payload, "release.zip")
            home = root / "cache" / self.home
            home.mkdir(parents=True)
            archive = home / (self.archive_stem.format(target=WINDOWS) + ".zip")
            archive.write_bytes(b"substituted archive")
            with self._installer(root, source, digest, "cached") as failed:
                _start_installer(failed)
                if failed.stdout is None:
                    raise AssertionError("installer fixture requires a result pipe")
                refusal = json.loads(failed.stdout.readline())
                ensure("cached download SHA256 does not match" in refusal.get("error", ""),
                       f"corrupt cache bytes must refuse before download or publication: {refusal}")
            ensure(archive.read_bytes() == b"substituted archive"
                   and not (home / self.windows_exe).exists(),
                   "the refusal replaced cached bytes or published an executable")

    def _linux_archive(self) -> None:
        for arch in ("AMD64", "x86_64", "arm64", "AARCH64"):
            ensure(self.adapter.asset_for("win32", arch).target == WINDOWS, "wrong Windows target")
            linux = LINUX if arch in {"AMD64", "x86_64"} else "aarch64-unknown-linux-gnu"
            ensure(self.adapter.asset_for("linux", arch).target == linux, "wrong Linux target")
        for system, arch in (("linux", "mips"), ("darwin", "arm64")):
            try:
                self.adapter.asset_for(system, arch)
            except ValueError as exc:
                ensure(str(exc) == f"{self.label} has no reviewed executable for {system}/{arch}",
                       f"unexpected platform refusal: {exc}")
            else:
                raise AssertionError("unsupported platform selected a reviewed binary")

        with tempfile.TemporaryDirectory(prefix="vos-validator-linux-") as directory:
            home = Path(directory) / self.home
            home.mkdir()
            archive = home / (self.archive_stem.format(target=LINUX) + ".tar.gz")
            exe = self.label.lower()
            member = tarfile.TarInfo(self.member.format(target=LINUX, exe=exe))
            payload = b"reviewed linux binary"
            target = home / exe
            for kind in (tarfile.SYMTYPE, tarfile.REGTYPE):
                member.type = kind
                member.size = len(payload) if kind == tarfile.REGTYPE else 0
                with tarfile.open(archive, "w:gz") as bundle:
                    bundle.addfile(member, io.BytesIO(payload))
                asset = self.adapter.Asset(LINUX, receipts.digest(archive), hashlib.sha256(payload).hexdigest())
                with (patch.object(pinned_binary, "sys", SimpleNamespace(prefix=directory,
                                                                        base_prefix="other", platform="linux")),
                      patch.object(pinned_binary.platform, "machine", return_value="amd64"),
                      patch.dict(self.adapter.ASSETS, {"linux-x64": asset})):
                    if kind == tarfile.SYMTYPE:
                        try:
                            self.adapter.executable()
                        except ValueError as exc:
                            ensure("pinned executable is not an ordinary file" in str(exc), str(exc))
                        else:
                            raise AssertionError("a linked archive member was accepted")
                        ensure(not target.exists(), "a rejected link was published")
                    else:
                        ensure(self.adapter.executable() == target and target.read_bytes() == payload,
                               "the reviewed Linux member was not published")
                        if sys.platform == "linux":
                            ensure(target.stat().st_mode & 0o777 == 0o755, "the Unix executable mode differs")

    def cases(self) -> list[Case]:
        return [
            Case("cached executable bytes retain their reviewed identity", self._cached_executable_identity),
            Case("simultaneous cold processes install one verified executable", self._concurrent_cold_install),
            Case("failed installation releases the cache for another live process",
                 self._failed_install_releases_lock),
            Case("installation contention has a bounded refusal", self._bounded_installation_wait),
            Case("terminated installation releases OS ownership", self._terminated_installer_releases_lock),
            Case("corrupt cached archives refuse without replacement", self._corrupt_cached_archive_refuses),
            Case("native retirement and installation contend on the same lock",
                 _native_retirement_lock_compatibility),
            Case("Linux archives and platform selection", self._linux_archive),
        ]
