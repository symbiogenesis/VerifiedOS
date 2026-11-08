# SPDX-License-Identifier: Apache-2.0
"""The maintained table rules cover widths, pipes, pragmas and binary installation."""

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

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import corpus, markdownlint
from vos.markdownlint import table_findings

CONFIG = TOOLS.parent / ".rumdl.toml"


def _table_rules() -> None:
    header = "| a | b |\n| --- | --- |\n"
    for row in ("| 1 |", "| 1 | 2 | 3 |"):
        findings = table_findings(header + row + "\n", CONFIG)
        ensure(any("MD056" in finding for finding in findings),
               f"ragged table escaped the maintained width rule: {findings}")
    ensure(not table_findings(header + "| a\\|b | `value` |\n", CONFIG),
           "an escaped pipe inside a cell must not add a column")
    ensure(not table_findings("```md\n" + header + "| 1 |\n```\n", CONFIG),
           "a displayed example is not a table declaration")


def _pragmas_cannot_disable_validation() -> None:
    table = "| a | b |\n| --- | --- |\n| 1 |\n"
    directives = (
        "<!-- pyml disable md056 -->",
        "<!-- rumdl-disable MD056 -->",
        "<!-- rumdl-disable -->",
        "<!-- markdownlint-disable MD056 -->",
        '<!-- markdownlint-configure-file { "MD056": false } -->',
        '<!-- rumdl-configure-file { "MD056": false } -->',
        "<!-- prettier-ignore -->",
        "> <!-- rumdl-disable MD056 -->",
        "<!--\nrumdl-disable MD056\n-->",
    )
    for directive in directives:
        raw = f"{directive}\n\n{table}"
        findings = table_findings(raw, CONFIG)
        expected_line = raw.count("\n")
        ensure(any(finding.startswith(f"{expected_line}: MD056 ") for finding in findings),
               f"document directive suppressed or shifted table validation ({directive!r}): {findings}")


def _pipe_style() -> None:
    raw = "a | b\n--- | ---\n1 | 2\n"
    ensure(any("MD055" in finding for finding in table_findings(raw, CONFIG)),
           "machine-read tables must keep their leading and trailing pipes")


def _serial(documents: list[corpus.Document], config: Path) -> list[str]:
    findings: list[str] = []
    for doc in documents:
        try:
            findings.extend(f"{doc.name}:{finding}" for finding in table_findings(doc.raw, config))
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            findings.append(f"{doc.name}: Markdown validation failed: {exc}")
    return findings


def _batch_preserves_complete_ordered_findings() -> None:
    header = "| 标题 | b |\n| --- | --- |\n"
    inputs = [header + "| 1 |\n", "```md\n" + header + "| 1 |\n```\n",
              "<!-- rumdl-disable MD056 -->\n\n" + header + "| 1 | 2 | 3 |\n",
              "a | b\n--- | ---\n1 | 2", "```md\n| unclosed fence",
              header + "| 合法 | `x` |\n", header + "| a\\|b | x |\n",
              "> " + header.replace("\n", "\n> ") + "| 1 |\n", "", "| ordinary text"]
    documents = [corpus.from_text(raw, f"{len(inputs) - i:02d} ü.md")
                 for i, raw in enumerate(inputs)]
    expected = _serial(documents, CONFIG)
    with (patch.object(markdownlint, "_batch", wraps=markdownlint._batch) as batch,
          patch.object(markdownlint, "table_findings", wraps=table_findings) as strings):
        actual = markdownlint.document_findings(documents, CONFIG)
    ensure(batch.call_count == 1 and strings.call_count == 1 and actual == expected,
           f"batched documents changed ordered findings: {actual!r} != {expected!r}")
    ensure(any("MD055" in line for line in actual) and any("MD056" in line for line in actual),
           "the comparison must include both rule refusals")


def _batch_refusal_retains_each_string_error() -> None:
    documents = [corpus.from_text("| a | b |\n| --- | --- |\n| 1 |\n", name)
                 for name in ("a.md", "b.md")]
    expected = _serial(documents, CONFIG)
    for error in (OSError("placement denied"), ValueError("population mismatch"),
                  subprocess.TimeoutExpired(["rumdl"], 120)):
        with patch.object(markdownlint, "_batch", side_effect=error):
            ensure(markdownlint.document_findings(documents, CONFIG) == expected,
                   f"a refused batch must replay every original string: {error}")
    with (patch.object(markdownlint, "_batch", side_effect=ValueError("refused")),
          patch.object(markdownlint, "table_findings", side_effect=[OSError("denied"), ["finding"]])):
        ensure(markdownlint.document_findings(documents, CONFIG)
               == ["a.md: Markdown validation failed: denied", "b.md:finding"],
               "a document error must not hide the following document's findings")


def _batch_preserves_index_membership_and_edits() -> None:
    raw = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    with sandbox_tree({".rumdl.toml": CONFIG.read_text(encoding="utf-8"),
                       "a.md": raw, "b.md": raw}) as root:
        (root / "ignored.md").write_text(raw.replace("1 | 2", "1"), encoding="utf-8")
        ensure(not markdownlint.run(root).findings, "untracked Markdown entered the batch")
        (root / "a.md").write_text(raw.replace("1 | 2", "1"), encoding="utf-8", newline="")
        ensure(markdownlint.run(root).findings == 1, "a changed source reused a prior verdict")
        config = root / ".rumdl.toml"
        config.write_text(CONFIG.read_text(encoding="utf-8") + '\nexclude = ["*.md"]\n', encoding="utf-8")
        expected = _serial(corpus.load(root).docs, config)
        report = markdownlint.run(root)
        ensure(report.findings == len(expected) and report.out[2:] == [f"       {f}" for f in expected],
               "unreviewed configuration keys must refuse rather than hiding indexed inputs")
        config.write_text("[global\n", encoding="utf-8")
        expected = _serial(corpus.load(root).docs, config)
        report = markdownlint.run(root)
        ensure(report.findings == len(expected) and report.out[2:] == [f"       {f}" for f in expected],
               "malformed configuration must retain the per-document decisions and diagnostics")


def _structured_verdicts() -> None:
    ensure(markdownlint.read_result(2, 0, "[]", "") == [[], []],
           "a complete structured success must pass")
    valid = json.dumps([{"file": "00000001.md", "line": 3, "rule": "MD056", "message": "width"}])
    ensure(markdownlint.read_result(2, 1, valid, "") == [[], ["3: MD056 width"]],
           "a valid diagnostic must map back to its ordinal document")
    invalid = [
        (0, "{}"),
        (0, valid),
        (1, "[]"),
        (2, "[]"),
        (1, '[{"file":"00000000.md","file":"00000000.md","line":1,"rule":"MD056","message":"x"}]'),
        (1, json.dumps([{"file": "unknown.md", "line": 1, "rule": "MD056", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": 0, "rule": "MD056", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": True, "rule": "MD056", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": 1, "rule": "MD013", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": 1, "rule": "MD056", "message": ""}])),
    ]
    for code, output in invalid:
        try:
            markdownlint.read_result(1, code, output, "stopped")
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"an incomplete or failed tool verdict passed: {code}, {output}")


def _carriage_returns_and_unencodable_sources() -> None:
    for ending in ("\r\n", "\r"):
        documents = [corpus.from_text(("| a | b |\n| --- | --- |\n| 1 |\n").replace("\n", ending),
                                      name) for name in ("a.md", "b.md")]
        expected = _serial(documents, CONFIG)
        actual = markdownlint.document_findings(documents, CONFIG)
        ensure(actual == expected and len(actual) == 2
               and all(":3: MD056 " in line for line in actual),
               f"carriage-return content must preserve line numbers and width diagnostics: {actual}")
    for bad in ("| \ud800 | b |\n| --- | --- |\n| 1 |\n", "| a | \x00 |\n| --- | --- |\n| 1 |\n"):
        documents = [corpus.from_text(bad, "bad.md"),
                     corpus.from_text("| a | b |\n| --- | --- |\n| 1 |\n", "good.md")]
        expected = _serial(documents, CONFIG)
        actual = markdownlint.document_findings(documents, CONFIG)
        ensure(actual == expected and len(actual) == 2
               and actual[0].startswith("bad.md: Markdown validation failed:")
               and actual[1].startswith("good.md:3: MD056 "),
               f"unencodable or NUL-containing input must fail closed without hiding peers: {actual}")


def _cached_executable_identity() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-rumdl-cache-") as directory:
        root = Path(directory)
        home = root / f"rumdl-{markdownlint.VERSION}"
        home.mkdir()
        target = home / "rumdl.exe"
        target.write_bytes(b"reviewed executable")
        asset = markdownlint.Asset("x86_64-pc-windows-msvc", "0" * 64,
                                   hashlib.sha256(target.read_bytes()).hexdigest())
        download = Mock()
        factory = Mock(wraps=markdownlint.FileLock)
        with (patch.object(markdownlint, "sys", SimpleNamespace(prefix=str(root),
                                                                base_prefix="other", platform="win32")),
              patch.object(markdownlint, "asset_for", return_value=asset),
              patch.object(markdownlint, "FileLock", factory),
              patch.object(markdownlint.receipts, "download", download)):
            ensure(markdownlint.executable() == target, "verified cached bytes must be reused")
            factory.assert_called_once_with(home / ".install.lock", timeout=180,
                                            fallback_to_soft=False, preserve_lock_file=True)
            target.write_bytes(b"substituted executable")
            try:
                markdownlint.executable()
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
from vos import markdownlint

root, source = Path(sys.argv[2]), Path(sys.argv[3])
asset = markdownlint.Asset('x86_64-pc-windows-msvc',
                           markdownlint.receipts.digest(source), sys.argv[4])
markdownlint.sys = SimpleNamespace(prefix=str(root / 'cache'),
                                   base_prefix='other', platform='win32')
markdownlint.ASSETS['windows'] = asset
atomic_path = markdownlint.receipts.atomic_path

@contextmanager
def counted_publication(path):
    with atomic_path(path) as pending:
        yield pending
    if path.name == asset.executable:
        (root / f'published-{os.getpid()}').write_text(str(path), encoding='utf-8')

def download(url, target, expected):
    if target.exists():
        if markdownlint.receipts.digest(target) != expected:
            raise ValueError('cached fixture archive differs from its pin')
        return
    (root / f'download-{os.getpid()}').write_text(url, encoding='utf-8')
    if markdownlint.receipts.digest(source) != expected:
        raise AssertionError('fixture archive differs from its pin')
    if sys.argv[5] == 'hold':
        print('holding', flush=True)
        if input() != 'release':
            raise AssertionError('missing owner release')
    time.sleep(0.25)
    with atomic_path(target) as pending:
        pending.write_bytes(source.read_bytes())

markdownlint.receipts.atomic_path = counted_publication
if sys.argv[5] != 'cached':
    markdownlint.receipts.download = download
if sys.argv[5] == 'timeout':
    original_lock = markdownlint.FileLock
    def impatient_lock(*args, **kwargs):
        return original_lock(*args, **(kwargs | {'timeout': 0.1}))
    markdownlint.FileLock = impatient_lock
print('ready', flush=True)
if input() != 'start':
    raise AssertionError('missing simultaneous start')
try:
    target = markdownlint.executable()
except ValueError as exc:
    if sys.argv[5] not in ('failure', 'cached'):
        raise
    print(json.dumps({'error': str(exc)}), flush=True)
    input()
else:
    print(json.dumps({'path': str(target),
                      'digest': markdownlint.receipts.digest(target)}), flush=True)
"""


def _installer_archive(root: Path, payload: bytes, name: str) -> Path:
    archive = root / name
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("rumdl.exe", payload)
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
    with (tempfile.TemporaryDirectory(prefix="vos-rumdl-concurrent-") as directory,
          ExitStack() as processes):
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        children = [processes.enter_context(_installer(root, source, digest)) for _ in range(3)]
        for child in children:
            _start_installer(child)
        target = root / "cache" / f"rumdl-{markdownlint.VERSION}" / "rumdl.exe"
        for child in children:
            _installed(child, target, digest)
        ensure(target.read_bytes() == payload, "the shared executable must retain pinned bytes")
        ensure(len(list(root.glob("download-*"))) == 1,
               "simultaneous cold callers must download the shared release only once")
        ensure(len(list(root.glob("published-*"))) == 1,
               "simultaneous cold callers must publish the shared executable only once")


def _failed_install_releases_lock() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-rumdl-recovery-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        bad = _installer_archive(root, b"substituted executable", "bad.zip")
        good = _installer_archive(root, payload, "good.zip")
        target = root / "cache" / f"rumdl-{markdownlint.VERSION}" / "rumdl.exe"
        with _installer(root, bad, digest, "failure") as failed:
            _start_installer(failed)
            if failed.stdout is None:
                raise AssertionError("installer fixture requires a result pipe")
            refusal = json.loads(failed.stdout.readline())
            ensure("extracted rumdl executable hash differs" in refusal.get("error", ""),
                   f"substituted release bytes must refuse publication: {refusal}")
            ensure(not target.exists() and not list(root.glob("published-*")),
                   "a failed verification must publish no executable")
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
    with tempfile.TemporaryDirectory(prefix="vos-rumdl-wait-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        target = root / "cache" / f"rumdl-{markdownlint.VERSION}" / "rumdl.exe"
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
    with tempfile.TemporaryDirectory(prefix="vos-rumdl-termination-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        target = root / "cache" / f"rumdl-{markdownlint.VERSION}" / "rumdl.exe"
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
    with tempfile.TemporaryDirectory(prefix="vos-rumdl-corrupt-") as directory:
        root = Path(directory)
        payload = b"reviewed fixture executable"
        digest = hashlib.sha256(payload).hexdigest()
        source = _installer_archive(root, payload, "release.zip")
        home = root / "cache" / f"rumdl-{markdownlint.VERSION}"
        home.mkdir(parents=True)
        archive = home / f"rumdl-v{markdownlint.VERSION}-x86_64-pc-windows-msvc.zip"
        archive.write_bytes(b"substituted archive")
        with _installer(root, source, digest, "cached") as failed:
            _start_installer(failed)
            if failed.stdout is None:
                raise AssertionError("installer fixture requires a result pipe")
            refusal = json.loads(failed.stdout.readline())
            ensure("cached download SHA256 does not match" in refusal.get("error", ""),
                   f"corrupt cache bytes must refuse before download or publication: {refusal}")
        ensure(archive.read_bytes() == b"substituted archive"
               and not (home / "rumdl.exe").exists(),
               "the refusal replaced cached bytes or published an executable")


def _native_retirement_lock_compatibility() -> None:
    if sys.platform != "linux":
        return
    import fcntl

    with tempfile.TemporaryDirectory(prefix="vos-rumdl-native-lock-") as directory:
        path = Path(directory) / ".install.lock"
        with (markdownlint.FileLock(path, timeout=0.1, fallback_to_soft=False, preserve_lock_file=True),
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
                with markdownlint.FileLock(path, timeout=0.1, fallback_to_soft=False,
                                           preserve_lock_file=True):
                    pass
            except Timeout:
                blocked = True
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            ensure(blocked, "installation bypassed native retirement's lock")


def cases() -> list[Case]:
    return [Case("maintained Markdown table rules", _table_rules),
            Case("document pragmas cannot disable table validation", _pragmas_cannot_disable_validation),
            Case("table pipe style remains explicit", _pipe_style),
            Case("batch preserves complete ordered findings", _batch_preserves_complete_ordered_findings),
            Case("batch refusals retain string errors", _batch_refusal_retains_each_string_error),
            Case("batch preserves index membership and edits", _batch_preserves_index_membership_and_edits),
            Case("tool crashes and malformed verdicts refuse", _structured_verdicts),
            Case("carriage returns and unencodable sources retain exact diagnostics",
                 _carriage_returns_and_unencodable_sources),
            Case("cached executable bytes retain their reviewed identity", _cached_executable_identity),
            Case("simultaneous cold processes install one verified executable", _concurrent_cold_install),
            Case("failed installation releases the cache for another live process",
                 _failed_install_releases_lock),
            Case("installation contention has a bounded refusal", _bounded_installation_wait),
            Case("terminated installation releases OS ownership", _terminated_installer_releases_lock),
            Case("corrupt cached archives refuse without replacement", _corrupt_cached_archive_refuses),
            Case("native retirement and installation contend on the same lock",
                 _native_retirement_lock_compatibility)]
