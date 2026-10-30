# SPDX-License-Identifier: Apache-2.0
"""Sibling-temporary publication without caller-specific filesystem policy."""

import tempfile
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path


@contextmanager
def atomic_path(path: Path) -> Generator[Path]:
    """Replace on success and preserve the primary failure while cleaning up.

    The caller owns containment, parent creation, serialization and synchronization.
    Close every handle to the yielded path before returning, including on Windows.
    Cleanup is best effort after failure; the original exception always propagates.
    """
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.",
                                     suffix=".tmp", delete=False) as stream:
        pending = Path(stream.name)
    try:
        yield pending
        pending.replace(path)
    except BaseException:
        with suppress(OSError):
            pending.unlink(missing_ok=True)
        raise
