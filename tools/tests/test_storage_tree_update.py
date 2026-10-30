# SPDX-License-Identifier: Apache-2.0
"""Independent maps and retained-root controls for numeric C tree updates."""

import json
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import toolenv

ROOT = TOOLS.parent
MAXIMUM = (1 << 64) - 1


@dataclass(frozen=True)
class Arena:
    fan: int
    blocks: bytes
    generations: list[int]
    used: int = 1
    root: int = 0
    height: int = 0


def _leaf(fan: int, keys: list[int], values: list[int]) -> bytes:
    return (b"VOSNODE1" + struct.pack("<IIQQ", 0, len(keys), 0, 0) +
            b"".join(struct.pack("<QQ", key, value)
                     for key, value in zip(keys, values, strict=True))).ljust(32 + 16 * fan, b"\0")


def _empty(fan: int, capacity: int = 2048) -> Arena:
    size = 32 + 16 * fan
    return Arena(fan, _leaf(fan, [], []) + b"\0" * (size * (capacity - 1)), [0] * capacity)


def _build(directory: Path, source: str | None = None) -> Path:
    compiler = shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        raise AssertionError("native C compiler missing")
    directory.mkdir(parents=True, exist_ok=True)
    updater = ROOT / "storage" / "src" / "tree_update.c"
    if source is not None:
        updater = directory / "tree_update.c"
        updater.write_text(source, encoding="utf-8", newline="")
    binary = directory / "tree-update"
    command = [compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-pedantic",
               "-I", str(ROOT / "storage" / "include"), str(updater),
               *(str(ROOT / "storage" / "src" / name) for name in ("node_image.c", "tree_image.c")),
               str(ROOT / "storage" / "host" / "tree_update.c"), "-o", str(binary)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    ensure(result.returncode == 0, f"compile failure is not a mutation kill: {result.stderr}")
    return binary


def _invoke(binary: Path, arena: Arena, key: int, value: int, *, generation: int = 1,
            depth: int = 16, visits: int = 4096,
            untouched: bool = False) -> subprocess.CompletedProcess[bytes]:
    arguments = [arena.fan, len(arena.generations), 32 + 16 * arena.fan, arena.used,
                 arena.root, arena.height, depth, visits, generation, key, value,
                 int(untouched), *arena.generations]
    return subprocess.run([str(binary), *(str(part) for part in arguments)], input=arena.blocks,
                          capture_output=True, timeout=10, check=False)


def _accepted(result: subprocess.CompletedProcess[bytes], old: Arena, generation: int) -> Arena:
    ensure(result.returncode == 0, f"valid update refused or changed retained state: {result.stderr!r}")
    header, data = result.stdout.split(b"\n", 1)
    record = json.loads(header)
    new = Arena(old.fan, data, record["generations"], record["used"], record["root"], record["height"])
    size = 32 + 16 * old.fan
    ensure(old.used < new.used <= len(old.generations) and new.root < new.used,
           "allocation did not stay within the append-only arena")
    ensure(data[:old.used * size] == old.blocks[:old.used * size] and
           new.generations[:old.used] == old.generations[:old.used], "retained prefix changed")
    ensure(new.generations[old.used:new.used] == [generation] * (new.used - old.used),
           "appended nodes have the wrong expected generation")
    return new


def _map(arena: Arena, root: int | None = None, height: int | None = None) -> dict[int, int]:
    # Decode bytes independently; the C codec and routing supply no expected map.
    def visit(node_id: int, level: int, lower: int | None, upper: int | None) -> list[tuple[int, int]]:
        ensure(0 <= node_id < arena.used, "output child outside allocated prefix")
        size = 32 + 16 * arena.fan
        block = arena.blocks[node_id * size:(node_id + 1) * size]
        kind, count, identity, generation = struct.unpack("<IIQQ", block[8:32])
        ensure(block[:8] == b"VOSNODE1" and identity == node_id and
               generation == arena.generations[node_id], "bad output node identity")
        ensure(count <= arena.fan, "overflowed output node")
        if kind == 0:
            ensure(level == 0, "unequal output leaf depth")
            entries = [struct.unpack("<QQ", block[32 + 16 * i:48 + 16 * i]) for i in range(count)]
            keys = [key for key, _ in entries]
            ensure(keys == sorted(set(keys)) and all((lower is None or key >= lower) and
                   (upper is None or key < upper) for key in keys), "output key/range order")
            ensure(not any(block[32 + 16 * count:]), "noncanonical leaf padding")
            return entries
        ensure(kind == 1 and count > 0 and level > 0, "output branch shape/depth")
        words = list(struct.unpack("<" + "Q" * (2 * count - 1), block[32:32 + 8 * (2 * count - 1)]))
        separators, children = words[:count - 1], words[count - 1:]
        ensure(separators == sorted(set(separators)) and all(
            (lower is None or key > lower) and (upper is None or key < upper)
            for key in separators), "output separator/range order")
        ensure(not any(block[32 + 8 * (2 * count - 1):]), "noncanonical branch padding")
        entries = []
        for at, child in enumerate(children):
            entries.extend(visit(child, level - 1, lower if at == 0 else separators[at - 1],
                                 upper if at + 1 == count else separators[at]))
        return entries

    entries = visit(arena.root if root is None else root, arena.height if height is None else height, None, None)
    ensure(len(dict(entries)) == len(entries), "duplicate output map keys")
    return dict(entries)


def _population(binary: Path) -> None:
    for fan in (2, 3, 4, 16):
        count = min(80, 2 * fan * fan + 3)
        keys = [3 * index for index in range(count)] + [MAXIMUM]
        for domain, ordering in ((1, keys), (2, list(reversed(keys)))):
            arena = _empty(fan)
            expected: dict[int, int] = {}
            retained: list[tuple[int, int, dict[int, int]]] = []
            for at, key in enumerate(ordering + ordering[::3]):
                retained.append((arena.root, arena.height, expected.copy()))
                value = (MAXIMUM - at if domain == 2 else at * 1009) & MAXIMUM
                arena = _accepted(_invoke(binary, arena, key, value, generation=at + domain), arena, at + domain)
                expected[key] = value
                ensure(_map(arena) == expected, "update differs from independent dictionary insertion/replacement")
                # Every retained root remains readable with its original exact map.
                for root, height, snapshot in retained:
                    ensure(_map(arena, root, height) == snapshot, "an update changed a retained root")
            ensure(arena.height >= (1 if fan == 16 else 2),
                   "population did not exercise its declared leaf/internal/root split boundary")


def _refusals(binary: Path) -> None:
    def refused(arena: Arena, *, depth: int = 16, visits: int = 4096,
                untouched: bool = False) -> None:
        result = _invoke(binary, arena, 9, 90, depth=depth, visits=visits, untouched=untouched)
        ensure(result.returncode == 2 and not result.stdout,
               "refusal accepted, crashed, changed retained prefix or published output")

    refused(_empty(2, capacity=1))
    full_leaf = _leaf(2, [1, 5], [10, 50])
    # Left/right appends can succeed before root allocation or depth refuses.
    for capacity in (2, 3):
        refused(Arena(2, full_leaf + b"\0" * (64 * (capacity - 1)), [0] * capacity))
    refused(Arena(2, full_leaf + b"\0" * (64 * 7), [0] * 8), depth=0)
    refused(_empty(2), depth=17, untouched=True)
    refused(_empty(2), visits=0, untouched=True)
    refused(_empty(2), visits=4097, untouched=True)
    # Candidate requires three visits although input is one valid full leaf.
    refused(Arena(2, full_leaf + b"\0" * (64 * 7), [0] * 8), visits=2)
    malformed = bytearray(_empty(2).blocks)
    malformed[0] ^= 1
    refused(Arena(2, bytes(malformed), [0] * 2048), untouched=True)
    # An otherwise valid branch cannot name an unallocated suffix block.
    root = (b"VOSNODE1" + struct.pack("<IIQQQ", 1, 1, 0, 0, 1)).ljust(64, b"\0")
    leaf = (b"VOSNODE1" + struct.pack("<IIQQ", 0, 0, 1, 0)).ljust(64, b"\0")
    refused(Arena(2, root + leaf, [0, 0], used=1, height=1), untouched=True)
    # Off-route corruption must refuse before any prefix is rebuilt.
    arena = _accepted(_invoke(binary, Arena(2, full_leaf + b"\0" * (64 * 7), [0] * 8), 9, 90),
                      Arena(2, full_leaf + b"\0" * (64 * 7), [0] * 8), 1)
    broken = bytearray(arena.blocks)
    broken[64] ^= 1
    refused(Arena(2, bytes(broken), arena.generations, arena.used, arena.root, arena.height), untouched=True)


def _native_campaign() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-update-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as temporary:
        binary = _build(Path(temporary))
        _population(binary)
        _refusals(binary)


def _compiled_controls() -> None:
    source = (ROOT / "storage" / "src" / "tree_update.c").read_text(encoding="utf-8")
    full = Arena(2, _leaf(2, [1, 5], [10, 50]) + b"\0" * (64 * 7), [0] * 8)
    mutants = [
        ("replacement-value", "values[route] = update->value;", "values[route] = 0u;", _empty(2), 9, 90),
        ("copy-on-write-prefix", "node->node_id = update->next;", "update->next = 0u; node->node_id = update->next;", _empty(2), 9, 90),
        ("leaf-split-separator", "keys[kind == VOS_NODE_LEAF ? cut : cut - 1u]", "keys[cut - 1u]", full, 9, 90),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-update-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="controls-", dir=work) as temporary:
        directory = Path(temporary)
        pristine = _build(directory / "pristine")
        for name, needle, replacement, arena, key, value in mutants:
            ensure(source.count(needle) == 1, f"ambiguous update mutation site: {name}")
            good = _accepted(_invoke(pristine, arena, key, value), arena, 1)
            expected = _map(arena)
            expected[key] = value
            ensure(_map(good) == expected, f"pristine {name} witness failed")
            mutated = _build(directory / name, source.replace(needle, replacement))
            result = _invoke(mutated, arena, key, value)
            ensure(result.returncode in (2, 4), f"compiled {name} defect escaped its update witness")


def _byte_oracle() -> None:
    block = _leaf(2, [0, MAXIMUM], [MAXIMUM, 0])
    ensure(len(block) == 64 and struct.unpack("<QQQQ", block[32:]) == (0, MAXIMUM, MAXIMUM, 0),
           "independent update fixture lost its full-width byte boundary")
    left = _leaf(2, [1, 2], [10, 20])
    right = (b"VOSNODE1" + struct.pack("<IIQQQQ", 0, 1, 1, 7, 5, 50)).ljust(64, b"\0")
    root = (b"VOSNODE1" + struct.pack("<IIQQQQQ", 1, 2, 2, 9, 5, 0, 1)).ljust(64, b"\0")
    arena = Arena(2, left + right + root, [0, 7, 9], used=3, root=2, height=1)
    ensure(_map(arena) == {1: 10, 2: 20, 5: 50} and _map(arena, 0, 0) == {1: 10, 2: 20},
           "independent tree parser lost mixed-generation or retained-root map semantics")


def cases() -> list[Case]:
    return [Case("independent update byte boundaries", _byte_oracle),
            Case("compiled insertion, replacement, split and retained-map population", _native_campaign, lane="guest"),
            Case("compiled copy-on-write and split defect controls", _compiled_controls, lane="guest")]
