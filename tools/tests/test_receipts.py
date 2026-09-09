# SPDX-License-Identifier: Apache-2.0
"""Evidence identities reject changed, new and missing inputs; writes are atomic."""

import json
import tempfile
from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import receipts


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
    return [Case("input-changes", _input_changes),
            Case("atomic-failure", _atomic_failure),
            Case("manifest-boundaries", _manifest_boundaries)]
