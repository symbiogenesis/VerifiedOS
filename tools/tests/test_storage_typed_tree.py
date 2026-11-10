# SPDX-License-Identifier: Apache-2.0
"""Independent complete-tuple byte trees for bounded typed storage routing."""

import random
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv

ROOT = Path(__file__).resolve().parents[2]
MAXIMUM = (1 << 64) - 1
type Key = tuple[int, int, int, int, int, int]
type Tree = tuple[list[bytes], list[int], int, int]


def _key(key: Key) -> bytes:
    return struct.pack(">6Q", *key)


def _extent(index: int) -> bytes:
    return (b"VOSEXT01" + struct.pack("<4Q2I", MAXIMUM - index, index + 1,
                                      index, MAXIMUM - 3 * index, index % 128, index % 2)
            + bytes((index + i) % 256 for i in range(16))
            + bytes((3 * index + i + 1) % 256 for i in range(32)))


def _block(node: int, generation: int, keys: list[Key], values: list[bytes] | list[int],
           *, fan: int, branch: bool = False) -> bytes:
    content = b"VOSTYP01" + struct.pack("<IIQQ", int(branch), len(values), node, generation)
    if branch:
        content += b"".join(_key(key) for key in keys)
        for child in values:
            if not isinstance(child, int):
                raise TypeError("branch oracle needs integer child identities")
            content += struct.pack("<Q", child)
    else:
        for key, extent in zip(keys, values, strict=True):
            if not isinstance(extent, bytes):
                raise TypeError("leaf oracle needs complete extent bytes")
            content += _key(key) + extent
    size = 32 + 144 * fan
    ensure(len(content) <= size, "independent typed block overflows geometry")
    return content.ljust(size, b"\0")


def _tree(keys: list[Key], answers: dict[Key, bytes], *, fan: int) -> Tree:
    blocks: list[bytes] = []
    generations: list[int] = []
    layer: list[tuple[Key, int]] = []
    for start in range(0, len(keys), fan):
        chunk = keys[start:start + fan]
        identity = len(blocks)
        generation = MAXIMUM - identity % 7
        generations.append(generation)
        blocks.append(_block(identity, generation, chunk, [answers[key] for key in chunk], fan=fan))
        layer.append((chunk[0], identity))
    height = 0
    while len(layer) > 1:
        following: list[tuple[Key, int]] = []
        for start in range(0, len(layer), fan):
            chunk = layer[start:start + fan]
            identity = len(blocks)
            generation = MAXIMUM - identity % 7
            generations.append(generation)
            blocks.append(_block(identity, generation, [key for key, _ in chunk[1:]],
                                 [child for _, child in chunk], fan=fan, branch=True))
            following.append((chunk[0][0], identity))
        layer = following
        height += 1
    return blocks, generations, layer[0][1], height


def _build(directory: Path, source: str | None = None) -> Path:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "typed tree checks require a native C compiler")
    if compiler is None:
        raise RuntimeError("no native C compiler")
    directory.mkdir(parents=True, exist_ok=True)
    reader = ROOT / "storage/src/typed_tree.c"
    if source is not None:
        reader = directory / "typed_tree.c"
        reader.write_text(source, encoding="utf-8", newline="")
    binary = directory / "typed-tree"
    result = subprocess.run([
        compiler, "-std=c17", "-O1", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes",
        "-pedantic", "-I" + str(ROOT / "storage/include"), str(reader),
        str(ROOT / "storage/src/typed_entry.c"), str(ROOT / "storage/host/typed_tree.c"),
        "-o", str(binary)
    ], capture_output=True, text=True, timeout=60, check=False)
    ensure(result.returncode == 0, f"typed tree compile failure is not a mutant kill: {result.stderr}")
    return binary


def _read(binary: Path, tree: Tree, key: Key, *, fan: int = 4, path: bool = False,
          visits: int = 4096, depth: int = 16, size: int | None = None) -> subprocess.CompletedProcess[bytes]:
    blocks, generations, root, height = tree
    arguments = [fan, len(blocks), 32 + 144 * fan if size is None else size,
                 root, height, depth, visits, *key, *generations]
    return subprocess.run([str(binary), *( ["--path"] if path else []),
                           *(str(value) for value in arguments)], input=b"".join(blocks),
                          capture_output=True, timeout=5, check=False)


def _answer(result: subprocess.CompletedProcess[bytes], expected: bytes | None) -> None:
    ensure(result.returncode == 0, f"valid typed read failed: {result.stderr!r} {result.returncode}")
    ensure(result.stdout == (b"1\n" if expected is None else b"2\n" + expected),
           "complete typed key routing, extent metadata or miss preservation disagrees")


def _refusal(result: subprocess.CompletedProcess[bytes]) -> None:
    ensure(result.returncode == 2 and not result.stdout,
           f"typed tree defect was accepted, crashed or changed output: {result.returncode}")


def _exercise(binary: Path, *, generated: bool) -> None:
    # Hold all preceding words equal at every component boundary. This catches
    # comparison by object/version alone and accidental truncation to 32 bits.
    keys: set[Key] = set()
    for field in range(6):
        for value in (0, 1, 255, 256, 1 << 32, MAXIMUM):
            row = [7, 7, 7, 7, 7, 7]
            row[field] = value
            keys.add((row[0], row[1], row[2], row[3], row[4], row[5]))
    if generated:
        rng = random.Random(0x1053D)  # noqa: S311 - reproducible public tuple vectors
        keys.update((rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64),
                     rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64))
                    for _ in range(64))
    ordered = sorted(keys)
    answers = {key: _extent(i) for i, key in enumerate(ordered)}
    for fan in ((2, 4, 16) if generated else (4,)):
        tree = _tree(ordered, answers, fan=fan)
        for key in ordered:
            _answer(_read(binary, tree, key, fan=fan), answers[key])
            _answer(_read(binary, tree, key, fan=fan, path=True), answers[key])
        missing_keys: list[Key] = [(0, 0, 0, 0, 0, 0),
                                   (MAXIMUM, MAXIMUM, MAXIMUM, MAXIMUM, MAXIMUM, MAXIMUM),
                                   (7, 7, 7, 7, 7, 8)]
        for missing in missing_keys:
            _answer(_read(binary, tree, missing, fan=fan), None)
        _refusal(_read(binary, tree, ordered[0], fan=fan, visits=1))
        _refusal(_read(binary, tree, ordered[0], fan=fan, depth=0))
        # Retained roots select different immutable leaf payloads, while each
        # expected generation is independent of serialized node metadata.
        first = _block(0, 9, [ordered[0]], [_extent(1)], fan=fan)
        second = _block(1, 10, [ordered[0]], [_extent(2)], fan=fan)
        _answer(_read(binary, ([first, second], [9, 10], 0, 0), ordered[0], fan=fan), _extent(1))
        _answer(_read(binary, ([first, second], [9, 10], 1, 0), ordered[0], fan=fan), _extent(2))

    left: Key = (1, 2, 3, 4, 5, 6)
    pivot: Key = (1, 2, 3, 4, 5, 7)
    right: Key = (1, 2, 3, 4, 5, 8)
    blocks = [_block(0, 3, [left], [_extent(3)], fan=4),
              _block(1, 5, [pivot, right], [_extent(4), _extent(5)], fan=4),
              _block(2, 9, [pivot], [0, 1], fan=4, branch=True)]
    tree = (blocks, [3, 5, 9], 2, 1)
    _answer(_read(binary, tree, pivot, visits=3), _extent(4))
    _answer(_read(binary, tree, pivot, path=True, visits=2), _extent(4))
    _refusal(_read(binary, tree, pivot, visits=2))
    _refusal(_read(binary, tree, pivot, path=True, visits=1))
    _refusal(_read(binary, (blocks, [4, 5, 9], 2, 1), pivot))
    for index, offset, value in ((0, 0, 0), (0, 8, 2), (0, 16, 2), (0, 24, 4),
                                  (0, 31, 1), (0, len(blocks[0]) - 1, 1), (0, 32 + 48 + 40, 128),
                                  (2, 32 + 48, 3)):
        damaged = list(blocks)
        changed = bytearray(damaged[index])
        changed[offset] = value
        damaged[index] = bytes(changed)
        _refusal(_read(binary, (damaged, [3, 5, 9], 2, 1), pivot))
    damaged = list(blocks)
    changed = bytearray(damaged[0])
    changed[-1] = 1
    damaged[0] = bytes(changed)
    # Full admission refuses even after the selected branch could answer;
    # path mode intentionally does not admit the unrelated damaged subtree.
    _refusal(_read(binary, (damaged, [3, 5, 9], 2, 1), pivot))
    _answer(_read(binary, (damaged, [3, 5, 9], 2, 1), pivot, path=True), _extent(4))
    for malformed in ([right, pivot], [pivot, pivot]):
        damaged = list(blocks)
        damaged[1] = _block(1, 5, malformed, [_extent(4), _extent(5)], fan=4)
        _refusal(_read(binary, (damaged, [3, 5, 9], 2, 1), pivot))
    damaged = list(blocks)
    damaged[0] = _block(0, 3, [pivot], [_extent(3)], fan=4)
    _refusal(_read(binary, (damaged, [3, 5, 9], 2, 1), pivot))
    damaged = list(blocks)
    damaged[1] = _block(1, 5, [left], [_extent(3)], fan=4)
    _refusal(_read(binary, (damaged, [3, 5, 9], 2, 1), left))
    damaged = list(blocks)
    damaged[2] = _block(2, 9, [pivot, pivot], [0, 1, 1], fan=4, branch=True)
    _refusal(_read(binary, (damaged, [3, 5, 9], 2, 1), pivot))
    cycle = [_block(0, 1, [], [0], fan=4, branch=True)]
    _refusal(_read(binary, (cycle, [1], 0, 16), left))
    _refusal(_read(binary, (blocks, [3, 5, 9], 2, 0), pivot))
    empty = [_block(0, 1, [], [], fan=4),
             _block(1, 2, [pivot], [0, 0], fan=4, branch=True)]
    _answer(_read(binary, (empty, [1, 2], 1, 1), pivot, visits=3), None)
    _refusal(_read(binary, (empty, [1, 2], 1, 1), pivot, visits=2))
    # Reject the numeric instance even when its byte count resembles a node.
    numeric = b"VOSNODE1" + blocks[0][8:]
    _refusal(_read(binary, ([numeric], [3], 0, 0), left))
    small = blocks[0][:128]
    _refusal(_read(binary, ([small], [3], 0, 0), left, size=128))


def typed_tree() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "typed-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="typed-", dir=work) as directory:
        _exercise(_build(Path(directory)), generated=True)


def typed_tree_mutants() -> None:
    source = (ROOT / "storage/src/typed_tree.c").read_text(encoding="utf-8")
    mutations = [
        ("omit version comparison", "i < 6u", "i < 5u"),
        ("route equality left", "compare(&node.keys[route], walk->key) <= 0",
         "compare(&node.keys[route], walk->key) < 0"),
        ("drop upper range", "(!range.has_upper || compare(key, &range.upper) < 0)", "1"),
        ("skip unrelated subtrees", "if (walk->path_only && i != route) continue;", "if (i != route) continue;"),
        ("drop nonzero expected generation", "node.generation != expected_generation",
         "(expected_generation == 0u && node.generation != expected_generation)"),
        ("lose digest metadata", "walk->extent = node.extents[i];",
         "walk->extent = node.extents[i]; walk->extent.content_digest[31] = 0u;"),
        ("accept duplicate leaf keys", "compare(&node.keys[i - 1u], &node.keys[i]) >= 0",
         "compare(&node.keys[i - 1u], &node.keys[i]) > 0"),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "typed-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="typed-mutants-", dir=work) as directory:
        scratch = Path(directory)
        for index, (label, old, new) in enumerate(mutations):
            ensure(source.count(old) == 1, f"mutation site drift: {label}")
            binary = _build(scratch / str(index), source.replace(old, new))
            caught = False
            try:
                _exercise(binary, generated=False)
            except AssertionError:
                caught = True
            ensure(caught, f"compiled and executed typed tree mutant survived: {label}")


def cases() -> list[Case]:
    return [Case("complete typed nodes route full tuples and retain inline authenticated extents", typed_tree, lane="guest"),
            Case("compiled typed routing and admission defects are detected", typed_tree_mutants, lane="guest")]
