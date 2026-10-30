# SPDX-License-Identifier: Apache-2.0
"""Pinned ordinary Markdown link validation; project assurance stays at its caller."""

import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from vos import jsonutil, receipts

VERSION = "0.24.2"
BASE = f"https://github.com/lycheeverse/lychee/releases/download/lychee-v{VERSION}"


@dataclass(frozen=True)
class Asset:
    target: str
    archive_hash: str
    executable_hash: str

    @property
    def windows(self) -> bool:
        return self.target.endswith("windows-msvc")

    @property
    def executable(self) -> str:
        return "lychee.exe" if self.windows else "lychee"


ASSETS: dict[str, Asset] = {
    "windows": Asset("x86_64-pc-windows-msvc",
                     "32975d1493ee1a975d6bb41e4fb56fe419cb442ded628bb772ba2e614acfacad",
                     "2d15a3f78ac680103720b0c59667dc6f1da7de35f7e9c95171bdf4b76fb6829b"),
    "linux-x64": Asset("x86_64-unknown-linux-gnu",
                       "1f4e0ef7f6554a6ed33dd7ac144fb2e1bbed98598e7af973042fc5cd43951c9a",
                       "87e6e75195df5753f08c53b5c0a13694b8328edd8df009914ae9e29b5000162d"),
    "linux-arm64": Asset("aarch64-unknown-linux-gnu",
                         "91a7bd65685da41b90ccb9bc867a3d649a7818042dae04ff405e55a25bddee4c",
                         "7674d743f60997b0f2c6d6dbf4e02b50b311d8fe6c0051b11ad085c3f244e98a"),
}


def asset_for(system: str, machine: str) -> Asset:
    architecture = machine.lower()
    if architecture not in {"amd64", "x86_64", "arm64", "aarch64"}:
        raise ValueError(f"Lychee has no reviewed executable for {system}/{machine}")
    if system == "win32":
        return ASSETS["windows"]
    if system == "linux":
        return ASSETS["linux-arm64" if architecture in {"arm64", "aarch64"} else "linux-x64"]
    raise ValueError(f"Lychee has no reviewed executable for {system}/{machine}")


def executable() -> Path:
    """Keep pinned bytes in the managed environment shared by mutant processes."""
    if sys.prefix == sys.base_prefix:
        raise ValueError("Lychee requires the project's managed Python environment")
    asset = asset_for(sys.platform, platform.machine())
    home = Path(sys.prefix) / f"lychee-{VERSION}"
    target = home / asset.executable
    if target.exists():
        if receipts.digest(target) != asset.executable_hash:
            raise ValueError(f"{target}: installed Lychee executable hash differs from its pin")
        return target
    extension = "zip" if asset.windows else "tar.gz"
    archive = home / f"lychee-{asset.target}.{extension}"
    receipts.download(f"{BASE}/{archive.name}", archive, asset.archive_hash)
    member = f"lychee-{asset.target}/{asset.executable}"
    if asset.windows:
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
        if receipts.digest(pending) != asset.executable_hash:
            raise ValueError(f"{archive}: extracted Lychee executable hash differs from its pin")
        if not asset.windows:
            pending.chmod(0o755)
    return target


def findings(root: Path, names: list[str], gitlinks: dict[str, str]) -> list[str]:
    """Validate explicit indexed inputs, including hidden and Git-ignored paths."""
    if not names:
        raise ValueError("the index carries no Markdown document to validate")
    inputs = [(root / name).resolve(strict=True) for name in names]
    if any("\n" in str(path) or "\r" in str(path) for path in inputs):
        raise ValueError("Lychee's line-delimited input inventory cannot represent a newline in a path")
    # A gitlink names a tracked repository even when its contents are not populated.
    # Only its root is exempt; a nonexistent child must still be diagnosed.
    exclusions = [part for name in sorted(gitlinks)
                  for part in ("--exclude", "^" + re.escape((root / name).as_uri()) + r"/?(?:#.*)?$")]
    # An explicit empty configuration prevents ambient/user exclusions or preprocessors.
    command = [str(executable()), "--config", os.devnull,
               "--offline", "--include-fragments", "--no-progress", "--no-ignore",
               "--hidden", "--cache=false", "--threads", "2", "--format", "json",
               *exclusions, "--files-from", "-"]
    done = subprocess.run(command, cwd=root, input="\n".join(str(path) for path in inputs) + "\n",
                          capture_output=True, text=True, encoding="utf-8", check=False,
                          timeout=120)
    return read_result(root, done.returncode, done.stdout, done.stderr)


def read_result(root: Path, code: int, output: str, error: str) -> list[str]:
    """Accept only a complete structured success or a reported link finding."""
    if code not in {0, 2}:
        raise ValueError(f"Lychee exited {code}: {(error or output).strip()[:500]}")
    data = json.loads(output, object_pairs_hook=jsonutil.unique_object)
    if not isinstance(data, dict) or not isinstance(data.get("error_map"), dict):
        raise ValueError("Lychee returned no error map")
    results: list[str] = []
    for source, entries in data["error_map"].items():
        if not isinstance(source, str) or not isinstance(entries, list):
            raise ValueError("Lychee returned an invalid source diagnostic")
        path = Path(source)
        source = path.relative_to(root).as_posix() if path.is_relative_to(root) else source
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("Lychee returned an invalid link diagnostic")
            status, span, url = item.get("status"), item.get("span"), item.get("url")
            if (not isinstance(status, dict) or not isinstance(status.get("text"), str)
                    or not isinstance(span, dict) or type(span.get("line")) is not int
                    or not isinstance(url, str)):
                raise ValueError("Lychee returned an incomplete link diagnostic")
            results.append(f"{source}:{span['line']} {url}: {status['text']}")
    if (type(data.get("errors")) is not int or data["errors"] != len(results)
            or (code == 0) != (not results)):
        raise ValueError("Lychee's exit status and diagnostic counts disagree")
    return sorted(results)
