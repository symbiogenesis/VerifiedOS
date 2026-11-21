# SPDX-License-Identifier: Apache-2.0
"""Install one reviewed validator executable in the managed Python environment."""

import platform
import sys
import tarfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Self

from filelock import FileLock

from vos import receipts


@dataclass(frozen=True)
class Asset:
    name: ClassVar[str]
    target: str
    archive_hash: str
    executable_hash: str

    @property
    def windows(self) -> bool:
        return self.target.endswith("windows-msvc")

    @property
    def executable(self) -> str:
        return self.name.lower() + (".exe" if self.windows else "")

    @classmethod
    def for_platform(cls, assets: Mapping[str, Self], system: str, machine: str) -> Self:
        arch = machine.lower()
        if arch in {"amd64", "x86_64", "arm64", "aarch64"}:
            if system == "win32":
                return assets["windows"]
            if system == "linux":
                return assets["linux-arm64" if arch in {"arm64", "aarch64"} else "linux-x64"]
        raise ValueError(f"{cls.name} has no reviewed executable for {system}/{machine}")

    @classmethod
    def install(cls, assets: Mapping[str, Self], *, version: str, base_url: str,
                archive_prefix: str, nested: bool) -> Path:
        if sys.prefix == sys.base_prefix:
            raise ValueError(f"{cls.name} requires the project's managed Python environment")
        asset = cls.for_platform(assets, sys.platform, platform.machine())
        home = Path(sys.prefix) / f"{cls.name.lower()}-{version}"
        home.mkdir(parents=True, exist_ok=True)
        with FileLock(home / ".install.lock", timeout=180,
                      fallback_to_soft=False, preserve_lock_file=True):
            return asset._install(home, base_url, archive_prefix, nested)

    def _install(self, home: Path, base_url: str, archive_prefix: str, nested: bool) -> Path:
        target = home / self.executable
        if target.exists():
            if receipts.digest(target) != self.executable_hash:
                raise ValueError(f"{target}: installed {self.name} executable hash differs from its pin")
            return target
        stem = f"{archive_prefix}-{self.target}"
        extension = "zip" if self.windows else "tar.gz"
        archive = home / f"{stem}.{extension}"
        receipts.download(f"{base_url}/{archive.name}", archive, self.archive_hash)
        member = f"{stem}/{self.executable}" if nested else self.executable
        if self.windows:
            with zipfile.ZipFile(archive) as bundle:
                contents = bundle.read(member)
        else:
            with tarfile.open(archive, "r:gz") as bundle:
                entry = bundle.getmember(member)
                if not entry.isfile() or (stream := bundle.extractfile(entry)) is None:
                    raise ValueError(f"{archive}: pinned executable is not an ordinary file")
                with stream:
                    contents = stream.read()
        with receipts.atomic_path(target) as pending:
            pending.write_bytes(contents)
            if receipts.digest(pending) != self.executable_hash:
                raise ValueError(f"{archive}: extracted {self.name} executable hash differs from its pin")
            if not self.windows:
                pending.chmod(0o755)
        return target
