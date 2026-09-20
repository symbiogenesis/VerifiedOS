# SPDX-License-Identifier: Apache-2.0
"""Content identities, verified downloads and atomic publication of tool artifacts.

A receipt records a run; it never substitutes for the checker that produced it.
Consumers compare the complete input and output manifests before reusing evidence.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from vos import env


def digest(path: Path) -> str:
    """Hash the bytes of one artifact, failing when it is absent or unreadable."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def atomic_path(path: Path) -> Iterator[Path]:
    """Publish only on successful exit; callers close all handles before returning."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.",
                                     suffix=".tmp", delete_on_close=False) as stream:
        stream.close()  # Windows must release the handle before replace.
        pending = Path(stream.name)
        yield pending
        pending.replace(path)


def download(url: str, target: Path, expected: str) -> None:
    """Authenticate cached bytes and publish new downloads only after verification."""
    import urllib.request  # noqa: PLC0415  (ordinary receipt paths need no HTTP stack)

    if target.exists():
        if digest(target) != expected:
            raise ValueError(f"{target}: cached download SHA256 does not match {expected}")
        return
    with atomic_path(target) as pending:
        # Callers supply owned HTTPS release URLs, never workflow expressions.
        with (urllib.request.urlopen(url, timeout=120) as response,  # noqa: S310
              pending.open("wb") as stream):
            shutil.copyfileobj(response, stream)
        if digest(pending) != expected:
            raise ValueError(f"{url}: downloaded SHA256 does not match {expected}")


def snapshot(root: Path, paths: Iterable[Path]) -> dict[str, str]:
    """A deterministic manifest of files relative to their declared root."""
    base = root.resolve()
    named = {path.resolve().relative_to(base).as_posix(): path for path in paths}
    return {name: digest(named[name]) for name in sorted(named)}


def executables(*names: str) -> dict[str, str]:
    """Identify the actual executables selected by PATH, not only version labels."""
    found: dict[str, str] = {}
    for name in names:
        path = shutil.which(name)
        if path is None:
            raise FileNotFoundError(f"required executable is missing: {name}")
        found[str(Path(path).resolve())] = digest(Path(path))
    return found


def inputs(root: Path, *pathspecs: str) -> dict[str, str]:
    """Working bytes of tracked and new inputs, plus pinned gitlink identities.

Ignored build products are excluded. Deleted tracked inputs fail instead of
disappearing from the manifest. Git's own pathspecs select each command's closure.
"""
    done = subprocess.run(
        ["git", "ls-files", "--stage", "--others", "--exclude-standard", "-z",
         "--", *pathspecs], cwd=root, capture_output=True, check=False,
        env={**os.environ, **env.git_env(root)}, timeout=60)
    if done.returncode:
        raise RuntimeError(done.stderr.decode("utf-8", errors="replace").strip())
    manifest: dict[str, str] = {}
    for entry in done.stdout.decode("utf-8").split("\0"):
        if not entry:
            continue
        head, sep, rel = entry.partition("\t")
        if not sep:
            rel = head
        elif head.split()[2] != "0":
            raise ValueError(f"unmerged input: {rel}")
        elif head.startswith("160000 "):
            manifest[rel] = "gitlink:" + head.split()[1]
            continue
        manifest[rel] = digest(root / rel)
    if not manifest:
        raise ValueError("no inputs were found for the evidence record")
    return dict(sorted(manifest.items()))


def write(path: Path, payload: object) -> None:
    """Replace a complete receipt atomically, preserving the old one on failure."""
    with (atomic_path(path) as pending,
          pending.open("w", encoding="utf-8", newline="") as stream):
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
