# SPDX-License-Identifier: Apache-2.0
"""Evidence identities reject changed, new and missing inputs; writes are atomic."""

import hashlib
import io
import json
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
            Case("atomic-failure", _atomic_failure),
            Case("manifest-boundaries", _manifest_boundaries)]
