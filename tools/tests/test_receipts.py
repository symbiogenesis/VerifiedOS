# SPDX-License-Identifier: Apache-2.0
"""Evidence identities reject changed, new and missing inputs; writes are atomic."""

import hashlib
import io
import json
import subprocess
import tempfile
from pathlib import Path
from typing import IO
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import receipts


def _download_integrity() -> None:
    payload = b"verified release bytes"
    expected = hashlib.sha256(payload).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "client"
        with patch("urllib.request.urlopen", return_value=io.BytesIO(payload)):
            receipts.download("https://example.invalid/client", target, expected)
        ensure(target.read_bytes() == payload, "verified bytes were not published")
        with patch("urllib.request.urlopen") as network:
            receipts.download("https://example.invalid/client", target, expected)
            ensure(not network.called, "a verified cached archive should require no download")
        target.write_bytes(b"corrupt")
        with patch("urllib.request.urlopen") as network:
            try:
                receipts.download("https://example.invalid/client", target, expected)
            except ValueError:
                pass
            else:
                raise AssertionError("a corrupt cached executable was accepted")
            ensure(not network.called, "corrupt cache must be refused explicitly")


def _bad_download_never_published() -> None:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "client"
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"bad")):
            try:
                receipts.download("https://example.invalid/client", target, "0" * 64)
            except ValueError:
                pass
            else:
                raise AssertionError("a corrupt download was accepted")
        ensure(not list(target.parent.iterdir()),
               "a failed download left executable or partial bytes behind")


def _atomic_replace_failure() -> None:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "artifact"
        target.write_bytes(b"previous")
        with patch.object(Path, "replace", side_effect=PermissionError("busy target")):
            try:
                with receipts.atomic_path(target) as pending:
                    pending.write_bytes(b"replacement")
            except PermissionError:
                pass
            else:
                raise AssertionError("failed publication was accepted")
        ensure(target.read_bytes() == b"previous", "failed replacement changed the old artifact")
        ensure(list(target.parent.iterdir()) == [target], "failed replacement left temporary bytes")


def _interrupted_download() -> None:
    def interrupted(source: io.BytesIO, destination: IO[bytes]) -> None:
        destination.write(b"partial")
        raise OSError("connection interrupted")

    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "archive"
        with (patch("urllib.request.urlopen", return_value=io.BytesIO(b"release")),
              patch.object(receipts.shutil, "copyfileobj", side_effect=interrupted)):
            try:
                receipts.download("https://example.invalid/archive", target, "0" * 64)
            except OSError:
                pass
            else:
                raise AssertionError("interrupted download was published")
        ensure(not list(target.parent.iterdir()), "interrupted download left partial bytes")


def _input_changes() -> None:
    with sandbox_tree({"source/a.py": "one\n"}) as root:
        before = receipts.inputs(root, "source")
        (root / "source/a.py").write_text("two\n", encoding="utf-8")
        ensure(receipts.inputs(root, "source") != before, "working edits invalidate evidence")
        (root / "source/a.py").write_text("one\n", encoding="utf-8")
        (root / "source/b.py").write_text("new\n", encoding="utf-8")
        ensure(receipts.inputs(root, "source") != before, "new inputs invalidate evidence")
        (root / "source/a.py").unlink()
        try:
            receipts.inputs(root, "source")
        except FileNotFoundError:
            return
        raise AssertionError("a missing tracked input must not disappear from evidence")


def _input_record_boundaries() -> None:
    # POSIX filenames may contain tabs, including a prefix that resembles Git's
    # stage header. Exact Git records exercise this boundary on Windows as well.
    tracked = "source/tracked\tfile.py"
    new = "source/new\tfile.py"
    header_like = f"100644 {'b' * 40} 0\tnew.py"
    staged = f"100644 {'a' * 40} 0\t{tracked}\0"
    staged += f"160000 {'c' * 40} 0\tupstream/pin\0"
    untracked = f"{new}\0{header_like}\0"
    contents = {tracked: b"tracked", new: b"new", header_like: b"header-like"}
    expected = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    expected["upstream/pin"] = "gitlink:" + "c" * 40

    def listing(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        output = (staged if "--stage" in argv else "") + (untracked if "--others" in argv else "")
        return subprocess.CompletedProcess(argv, 0, stdout=output.encode("utf-8"), stderr=b"")

    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)

        def digest(path: Path) -> str:
            return hashlib.sha256(contents[path.relative_to(root).as_posix()]).hexdigest()

        with (patch.object(receipts.subprocess, "run", side_effect=listing),
              patch.object(receipts, "digest", side_effect=digest)):
            ensure(receipts.inputs(root) == dict(sorted(expected.items())),
                   "tracked and untracked filenames must retain their exact record boundaries")


def _input_conflicts() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        for stage in (1, 2, 3):
            output = f"100644 {'a' * 40} {stage}\tsource/conflict\0".encode("utf-8")
            done = subprocess.CompletedProcess(["git"], 0, stdout=output, stderr=b"")
            with patch.object(receipts.subprocess, "run", return_value=done):
                try:
                    receipts.inputs(root)
                except ValueError as error:
                    ensure(str(error) == "unmerged input: source/conflict",
                           "an unmerged index record must identify the conflicted path")
                else:
                    raise AssertionError("an unmerged index record entered the input manifest")


def _atomic_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "evidence.json"
        receipts.write(path, {"exit_code": 0})
        before = path.read_bytes()
        try:
            receipts.write(path, {"not_json": object()})
        except TypeError:
            pass
        else:
            raise AssertionError("invalid data must fail serialization")
        ensure(path.read_bytes() == before, "failed publication must preserve the prior record")
        ensure(list(path.parent.iterdir()) == [path], "failed publication must remove its temp")
        ensure(json.loads(before) == {"exit_code": 0}, "the published record is complete JSON")


def _nonfinite_values_refuse() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "evidence.json"
        previous = {"seconds": 1.25, "samples": [0.0, -2.5]}
        receipts.write(path, previous)
        before = path.read_bytes()
        ensure(json.loads(before) == previous, "finite receipt values must round-trip")
        for value in (float("nan"), float("inf"), float("-inf")):
            for payload in (value, {"nested": [value]}):
                for existing in (True, False):
                    if existing:
                        path.write_bytes(before)
                    else:
                        path.unlink(missing_ok=True)
                    try:
                        receipts.write(path, payload)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("a non-JSON number was published in a receipt")
                    ensure(path.read_bytes() == before if existing else not path.exists(),
                           "failed serialization must preserve the destination state")
                    ensure(list(path.parent.iterdir()) == ([path] if existing else []),
                           "failed serialization must remove temporary bytes")


def _manifest_boundaries() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        path = root / "source"
        path.write_bytes(b"source")
        before = receipts.snapshot(root, [path])
        ensure(receipts.snapshot(root, [path, path]) == before, "duplicate paths do not drift")
        path.write_bytes(b"changed")
        ensure(receipts.snapshot(root, [path]) != before, "changed bytes must change identity")
        try:
            receipts.snapshot(root / "child", [path])
        except ValueError:
            return
        raise AssertionError("a manifest cannot escape its declared root")


def cases() -> list[Case]:
    return [Case("download-integrity", _download_integrity),
            Case("corrupt-download", _bad_download_never_published),
            Case("interrupted-download", _interrupted_download),
            Case("atomic-replace-failure", _atomic_replace_failure),
            Case("input-changes", _input_changes),
            Case("input-record-boundaries", _input_record_boundaries),
            Case("input-conflicts", _input_conflicts),
            Case("atomic-failure", _atomic_failure),
            Case("nonfinite-values-refuse", _nonfinite_values_refuse),
            Case("manifest-boundaries", _manifest_boundaries)]
