# SPDX-License-Identifier: Apache-2.0
"""Pinned ordinary Markdown link validation; project assurance stays at its caller."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vos import jsonutil, pinned_binary

VERSION = "0.24.2"
BASE = f"https://github.com/lycheeverse/lychee/releases/download/lychee-v{VERSION}"


@dataclass(frozen=True)
class Asset(pinned_binary.Asset):
    name = "Lychee"


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
    return Asset.for_platform(ASSETS, system, machine)


def executable() -> Path:
    return Asset.install(ASSETS, version=VERSION, base_url=BASE,
                         archive_prefix="lychee", nested=True)


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
        raise TypeError("Lychee returned no error map")
    results: list[str] = []
    for source, entries in data["error_map"].items():
        if not isinstance(source, str) or not isinstance(entries, list):
            raise TypeError("Lychee returned an invalid source diagnostic")
        path = Path(source)
        label = path.relative_to(root).as_posix() if path.is_relative_to(root) else source
        for item in entries:
            if not isinstance(item, dict):
                raise TypeError("Lychee returned an invalid link diagnostic")
            status, span, url = item.get("status"), item.get("span"), item.get("url")
            if (not isinstance(status, dict) or not isinstance(status.get("text"), str)
                    or not isinstance(span, dict) or type(span.get("line")) is not int
                    or not isinstance(url, str)):
                raise ValueError("Lychee returned an incomplete link diagnostic")
            results.append(f"{label}:{span['line']} {url}: {status['text']}")
    if (type(data.get("errors")) is not int or data["errors"] != len(results)
            or (code == 0) != (not results)):
        raise ValueError("Lychee's exit status and diagnostic counts disagree")
    return sorted(results)
