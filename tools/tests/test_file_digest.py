# SPDX-License-Identifier: Apache-2.0
"""Shared file identities retain exact bytes and unreadable-input failures."""

import hashlib
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import (
    copy_service,
    memory_planner_candidates,
    openssl,
    receipts,
    sailisla,
    saillsp,
    supervisor,
)

READERS: tuple[Callable[[Path], str], ...] = (
    receipts.digest, copy_service._digest, memory_planner_candidates.digest,
    openssl._sha, sailisla.sha, saillsp.sha256, supervisor._digest,
)


def exact_file_bytes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-file-digest-") as directory:
        path = Path(directory) / "artifact"
        for payload in (b"", b"\x00\xff\r\n\n\xc3\xa9", bytes(range(256)) * 4097):
            path.write_bytes(payload)
            expected = hashlib.sha256(payload).hexdigest()
            ensure(all(reader(path) == expected for reader in READERS),
                   "a file identity changed bytes or truncated a multi-chunk file")


def unreadable_files() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-file-digest-") as directory:
        missing = Path(directory) / "missing"
        for reader in READERS:
            try:
                reader(missing)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("a missing file received a digest")
        denied = PermissionError("unreadable artifact")
        with patch.object(Path, "open", side_effect=denied):
            for reader in READERS:
                try:
                    reader(missing)
                except PermissionError as error:
                    ensure(error is denied, "a file reader replaced the original I/O error")
                else:
                    raise AssertionError("an unreadable file received a digest")


def cases() -> list[Case]:
    return [Case("all file identity readers preserve exact bytes", exact_file_bytes),
            Case("all file identity readers preserve I/O failures", unreadable_files)]
