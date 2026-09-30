# SPDX-License-Identifier: Apache-2.0
"""The shared Rust pin has one owner, a strict shape, and both native consumers read it."""

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import env, rust_toolchain, sailisla
from vos import memory_planner_candidates as candidates

ROOT = TOOLS.parent
TARGET = "aarch64-unknown-linux-gnu"


def _pin(version: str = "9.9.9") -> dict[str, Any]:
    return {"version": version,
            "components": {target: {component: f"{index:064x}"
                                    for index, component in enumerate(rust_toolchain.COMPONENTS)}
                           for target in rust_toolchain.TARGETS}}


def _refused(call: Callable[[], object]) -> None:
    try:
        call()
    except ValueError:
        return
    raise AssertionError("a malformed or unpinned Rust toolchain was accepted")


def one_owner() -> None:
    pin = rust_toolchain.load(ROOT)
    ensure(set(pin["components"]) == set(rust_toolchain.TARGETS),
           "the tracked pin must cover every supported target")
    for copy in ("tools/memory-planner/idealloc.json", "tools/sail-isla/lock.json"):
        ensure("rust" not in json.loads((ROOT / copy).read_text(encoding="utf-8")),
               f"{copy} must not carry a second Rust pin that could drift from the owner")
    urls = [url for _, url, _ in rust_toolchain.archives(pin, TARGET)]
    ensure(urls == [f"https://static.rust-lang.org/dist/{component}-{pin['version']}-{TARGET}.tar.xz"
                    for component in rust_toolchain.COMPONENTS],
           "archive URLs derive from the pinned release, target and component")


def strict_shape() -> None:
    good = _pin()
    malformed: list[dict[str, Any]] = [
        {**good, "extra": 1},
        {**good, "version": "1.98"},
        {**good, "version": "1.98.1-beta.1"},
        {**good, "components": {TARGET: good["components"][TARGET]}},
        {**good, "components": {**good["components"], "riscv64gc-unknown-linux-gnu": {}}},
        {**good, "components": {**good["components"],
                                TARGET: {**good["components"][TARGET], "clippy": "0" * 64}}},
        {**good, "components": {**good["components"],
                                TARGET: {**good["components"][TARGET], "rustc": "0" * 63}}},
        {**good, "components": {**good["components"],
                                TARGET: {**good["components"][TARGET], "rustc": "A" * 64}}},
    ]
    with sandbox_tree({rust_toolchain.PATH: json.dumps(good)}) as root:
        ensure(rust_toolchain.load(root) == good, "a well-formed pin must load unchanged")
        for value in malformed:
            (root / rust_toolchain.PATH).write_text(json.dumps(value), encoding="utf-8")
            _refused(lambda: rust_toolchain.load(root))


def consumers_read_the_owner() -> None:
    """Point both installers at a different owner: each must request that owner's archive."""
    expected = f"https://static.rust-lang.org/dist/rustc-9.9.9-{TARGET}.tar.xz"
    with sandbox_tree({rust_toolchain.PATH: json.dumps(_pin())}) as root:
        output = root / "idealloc"
        requested: list[str] = []

        def fetch(url: str, **_: object) -> io.BytesIO:
            requested.append(url)
            return io.BytesIO(b"not the pinned archive")

        with (patch.object(candidates.platform, "system", return_value="Linux"),
              patch.object(candidates.platform, "machine", return_value="aarch64"),
              patch.object(candidates, "urlopen", side_effect=fetch),
              patch.object(candidates.subprocess, "run") as run):
            _refused(lambda: candidates.rust_environment(root, output))
            ensure(not run.called, "an installer ran before its archive matched the pin")
        ensure(requested == [expected], "the idealloc build must install the shared owner's Rust")
        requested.clear()
        environment = env.Environment(root=root, model=root / "model", build_root=root / "native",
                                      log_root=root / "logs", lane="", cpus=1, mem_available_mb=1024,
                                      jobs=1, test_jobs=1)
        runner = sailisla.Runner(environment, "test")
        base = root / "isla"
        with (patch.object(sailisla.urllib.request, "urlopen", side_effect=fetch),
              patch.object(sailisla.Runner, "run") as run):
            _refused(lambda: sailisla._install_rust(root, base, TARGET, runner))
            ensure(not run.called, "an installer ran before its archive matched the pin")
        ensure(requested == [expected], "the Isla tools must install the shared owner's Rust")
        ensure(not list(Path(base).glob("*.part")), "a mismatched archive must not remain")


def owner_moves_the_isla_stamp() -> None:
    """The stamp digest reads the checkout in place, so a changed owner is a patched read."""
    owner = ROOT / rust_toolchain.PATH
    real = Path.read_bytes
    before = sailisla.asset_digest(ROOT)

    def read(path: Path) -> bytes:
        return real(path) + b" " if path == owner else real(path)

    with patch.object(Path, "read_bytes", read):
        after = sailisla.asset_digest(ROOT)
    ensure(before != after, "a Rust pin change must invalidate the Isla provision stamp")


def cases() -> list[Case]:
    return [Case("rust-pin-has-one-owner", one_owner),
            Case("rust-pin-shape-is-strict", strict_shape),
            Case("both-native-consumers-read-the-owner", consumers_read_the_owner),
            Case("rust-pin-change-invalidates-isla-stamp", owner_moves_the_isla_stamp)]
