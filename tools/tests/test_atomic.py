# SPDX-License-Identifier: Apache-2.0
"""Shared publication keeps old bytes until completion and leaves policy to callers."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import compiler_build, coread, receipts, timings
from vos.atomic import atomic_path


def _successful_publication() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-atomic-") as td:
        target = Path(td) / "artifact"
        target.write_bytes(b"previous")
        with atomic_path(target) as pending:
            ensure(pending.parent == target.parent and pending != target,
                   "temporary output must be a distinct sibling")
            pending.write_bytes(b"replacement")
            ensure(target.read_bytes() == b"previous", "publication must wait for successful exit")
        ensure(target.read_bytes() == b"replacement", "successful exit must replace the artifact")
        ensure(list(target.parent.iterdir()) == [target], "publication must leave no temporary file")


def _failed_publication() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-atomic-") as td:
        target = Path(td) / "artifact"
        target.write_bytes(b"previous")
        failure = RuntimeError("writer stopped")
        try:
            with atomic_path(target) as pending:
                pending.write_bytes(b"partial")
                raise failure
        except RuntimeError as error:
            ensure(error is failure, "publication must preserve the writer's original exception")
        else:
            raise AssertionError("failed writer returned success")
        ensure(target.read_bytes() == b"previous", "failed writer must preserve predecessor bytes")
        ensure(list(target.parent.iterdir()) == [target], "failed writer must remove temporary bytes")
        with patch.object(Path, "replace", side_effect=PermissionError("busy destination")):
            try:
                with atomic_path(target) as pending:
                    pending.write_bytes(b"replacement")
            except PermissionError:
                pass
            else:
                raise AssertionError("failed replacement returned success")
        ensure(target.read_bytes() == b"previous", "failed replacement must preserve predecessor bytes")
        ensure(list(target.parent.iterdir()) == [target], "failed replacement must remove temporary bytes")


def _compiler_sync_and_containment() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-atomic-") as td:
        target = Path(td).resolve() / "index.json"
        target.write_bytes(b"previous")
        with patch.object(compiler_build.os, "fsync", side_effect=OSError("sync refused")) as sync:
            try:
                compiler_build._atomic(target, {"complete": True})
            except OSError:
                pass
            else:
                raise AssertionError("compiler publication ignored a synchronization failure")
        ensure(sync.call_count == 1, "compiler publication must request synchronization")
        ensure(target.read_bytes() == b"previous", "failed synchronization must preserve predecessor bytes")
        ensure(list(target.parent.iterdir()) == [target], "failed synchronization must clean temporary bytes")
        with patch.object(compiler_build, "contained", side_effect=ValueError("outside root")):
            try:
                compiler_build._atomic(target, {"complete": True})
            except ValueError:
                pass
            else:
                raise AssertionError("compiler publication skipped containment")
        ensure(target.read_bytes() == b"previous", "containment refusal must preserve predecessor bytes")


def _caller_policies() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-atomic-") as td:
        root = Path(td)
        target = root / "missing" / "artifact.json"
        timings.write(target, [])
        ensure(not target.parent.exists(), "diagnostic publication must not create parent directories")
        try:
            coread.write_ledger(root, {})
        except OSError:
            pass
        else:
            raise AssertionError("ledger publication must propagate a missing-parent failure")
        ensure(not (root / "tools").exists(), "ledger publication must not create parent directories")
        receipts.write(target, {"complete": True})
        ensure(target.is_file(), "receipt publication must retain explicit parent creation")
        before = target.read_bytes()
        with patch.object(timings.os, "fsync", side_effect=AssertionError("unexpected synchronization")):
            timings.write(target, [])
        ensure(target.read_bytes() == b"[]\n", "diagnostic publication must remain unsynchronized")
        target.write_bytes(before)
        with patch.object(Path, "replace", side_effect=PermissionError("busy destination")):
            timings.write(target, [])
            try:
                receipts.write(target, {"complete": False})
            except PermissionError:
                pass
            else:
                raise AssertionError("receipt publication ignored replacement failure")
        ensure(target.read_bytes() == before, "failed publications must preserve predecessor bytes")
        ensure(list(target.parent.iterdir()) == [target], "caller failures must remove temporary bytes")


def cases() -> list[Case]:
    return [Case("successful-publication", _successful_publication),
            Case("failed-publication", _failed_publication),
            Case("compiler-sync-and-containment", _compiler_sync_and_containment),
            Case("caller-policies", _caller_policies)]
