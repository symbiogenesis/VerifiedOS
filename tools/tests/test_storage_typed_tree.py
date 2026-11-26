# SPDX-License-Identifier: Apache-2.0
"""Independent complete-tuple byte trees for bounded typed routing and update."""

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


def _insert(binary: Path, tree: Tree, key: Key, extent: bytes, *, fan: int,
            generation: int, free: int = 8, visits: int = 4096, depth: int = 16,
            used: int | None = None, invalid_extent: bool = False) -> subprocess.CompletedProcess[bytes]:
    blocks, generations, root, height = tree
    size = 32 + 144 * fan
    arguments = [fan, len(blocks) + free, size, root, height, depth, visits, *key,
                 len(blocks) if used is None else used, generation, *generations, *([0] * free)]
    return subprocess.run([str(binary), "--insert-invalid-extent" if invalid_extent else "--insert",
                           *(str(value) for value in arguments)],
                          input=b"".join(blocks) + bytes(size * free) + extent,
                          capture_output=True, timeout=5, check=False)


def _delete(binary: Path, tree: Tree, key: Key, *, fan: int, generation: int,
            free: int = 8, visits: int = 4096, depth: int = 16,
            used: int | None = None) -> subprocess.CompletedProcess[bytes]:
    blocks, generations, root, height = tree
    size = 32 + 144 * fan
    arguments = [fan, len(blocks) + free, size, root, height, depth, visits, *key,
                 len(blocks) if used is None else used, generation, *generations, *([0] * free)]
    return subprocess.run([str(binary), "--delete", *(str(value) for value in arguments)],
                          input=b"".join(blocks) + bytes(size * free),
                          capture_output=True, timeout=5, check=False)


def _insert_batch(binary: Path, tree: Tree, entries: list[tuple[Key, bytes]], *, fan: int,
                  generation: int, free: int = 32, visits: int = 4096, depth: int = 16,
                  used: int | None = None, invalid_extent: bool = False) -> subprocess.CompletedProcess[bytes]:
    blocks, generations, root, height = tree
    size = 32 + 144 * fan
    arguments = [fan, len(blocks) + free, size, root, height, depth, visits,
                 0, 0, 0, 0, 0, 0, len(blocks) if used is None else used,
                 generation, *generations, *([0] * free)]
    records = b"".join(_key(key) + extent for key, extent in entries)
    payload = b"".join(blocks) + bytes(size * free) + struct.pack("<I", len(entries)) + records
    flag = "--insert-batch-invalid-extent" if invalid_extent else "--insert-batch"
    return subprocess.run([str(binary), flag, *(str(value) for value in arguments)],
                          input=payload, capture_output=True, timeout=5, check=False)


def _compact(binary: Path, tree: Tree, *, fan: int, generation: int,
             free: int = 64, visits: int = 4096, depth: int = 16,
             used: int | None = None) -> subprocess.CompletedProcess[bytes]:
    blocks, generations, root, height = tree
    size = 32 + 144 * fan
    arguments = [fan, len(blocks) + free, size, root, height, depth, visits,
                 0, 0, 0, 0, 0, 0, len(blocks) if used is None else used,
                 generation, *generations, *([0] * free)]
    return subprocess.run([str(binary), "--compact", *(str(value) for value in arguments)],
                          input=b"".join(blocks) + bytes(size * free),
                          capture_output=True, timeout=5, check=False)


def _accepted_update(result: subprocess.CompletedProcess[bytes], tree: Tree, *,
                     fan: int, generation: int) -> Tree:
    ensure(result.returncode == 0, f"valid typed update failed: {result.returncode} {result.stderr!r}")
    header, generation_line, appended = result.stdout.split(b"\n", 2)
    root, used, height = map(int, header.split())
    prior_blocks, prior_generations, _, _ = tree
    appended_count = used - len(prior_blocks)
    size = 32 + 144 * fan
    ensure(appended_count > 0 and root == used - 1 and len(appended) == size * appended_count,
           "candidate root or prefix length disagrees")
    generations = list(map(int, generation_line.split()))
    ensure(generations == [generation] * appended_count, "candidate generations disagree")
    blocks = [appended[i:i + size] for i in range(0, len(appended), size)]
    return prior_blocks + blocks, prior_generations + generations, root, height


def _update_refusal(result: subprocess.CompletedProcess[bytes], *, staged: bool | None = None) -> None:
    expected = (b"0\n", b"1\n") if staged is None else ((b"1\n",) if staged else (b"0\n",))
    ensure(result.returncode == 2 and result.stdout in expected,
           f"typed update refusal, prefix preservation or staging disagrees: {result.returncode}, {result.stdout!r}")


def _candidate_map(tree: Tree, *, fan: int) -> tuple[dict[Key, bytes], set[int]]:
    blocks, generations, root, height = tree
    referenced: set[int] = set()

    def walk(node: int, depth: int, lower: Key | None, upper: Key | None) -> dict[Key, bytes]:
        ensure(0 <= node < len(blocks), "candidate reaches outside its prefix")
        referenced.add(node)
        raw = blocks[node]
        kind, count, identity, generation = struct.unpack_from("<IIQQ", raw, 8)
        ensure(identity == node and generation == generations[node] and count <= fan,
               "candidate node identity, generation or occupancy disagrees")
        if depth == 0:
            keys = [struct.unpack_from(">6Q", raw, 32 + 144 * i) for i in range(count)]
            extents = [raw[80 + 144 * i:176 + 144 * i] for i in range(count)]
            ensure(kind == 0 and keys == sorted(set(keys)) and
                   all((lower is None or lower <= key) and (upper is None or key < upper) for key in keys),
                   "candidate leaf order, range or depth disagrees")
            ensure(raw == _block(node, generation, keys, extents, fan=fan), "noncanonical candidate leaf")
            return dict(zip(keys, extents, strict=True))
        ensure(kind == 1 and count > 0, "candidate branch depth or occupancy disagrees")
        keys = [struct.unpack_from(">6Q", raw, 32 + 48 * i) for i in range(count - 1)]
        children = list(struct.unpack_from(f"<{count}Q", raw, 32 + 48 * (count - 1)))
        ensure(keys == sorted(set(keys)) and
               all((lower is None or lower < key) and (upper is None or key < upper) for key in keys),
               "candidate separator order or range disagrees")
        ensure(raw == _block(node, generation, keys, children, fan=fan, branch=True),
               "noncanonical candidate branch")
        bounds = [lower, *keys, upper]
        answers: dict[Key, bytes] = {}
        for index, child in enumerate(children):
            answers.update(walk(child, depth - 1, bounds[index], bounds[index + 1]))
        return answers

    return walk(root, height, None, None), referenced


def _exercise_update(binary: Path, *, generated: bool) -> None:
    left: Key = (8, 9, 0, 1 << 63, MAXIMUM, 1)
    pivot: Key = (8, 9, 0, 1 << 63, MAXIMUM, 1 << 32)
    inserted: Key = (8, 9, 0, 1 << 63, MAXIMUM, 1 << 63)
    right: Key = (8, 9, 0, 1 << 63, MAXIMUM, MAXIMUM)
    fan = 2
    generation = MAXIMUM
    blocks = [_block(0, 3, [left], [_extent(1)], fan=fan),
              _block(1, 5, [pivot, right], [_extent(2), _extent(3)], fan=fan),
              _block(2, 7, [pivot], [0, 1], fan=fan, branch=True)]
    prior = (blocks, [3, 5, 7], 2, 1)
    updated = _accepted_update(_insert(binary, prior, inserted, _extent(4), fan=fan,
                                      generation=generation, free=5, visits=6, depth=2),
                               prior, fan=fan, generation=generation)
    expected = [
        _block(3, generation, [pivot], [_extent(2)], fan=fan),
        _block(4, generation, [inserted, right], [_extent(4), _extent(3)], fan=fan),
        _block(5, generation, [], [0], fan=fan, branch=True),
        _block(6, generation, [inserted], [3, 4], fan=fan, branch=True),
        _block(7, generation, [pivot], [5, 6], fan=fan, branch=True),
    ]
    ensure(updated == (blocks + expected, [3, 5, 7] + [generation] * 5, 7, 2),
           "exact leaf, branch and root split bytes disagree")
    expected_map = {left: _extent(1), pivot: _extent(2), inserted: _extent(4), right: _extent(3)}
    ensure(_candidate_map(updated, fan=fan) == (expected_map, {0, 3, 4, 5, 6, 7}),
           "candidate map or unchanged sibling reference disagrees")
    _answer(_read(binary, (updated[0], updated[1], 2, 1), inserted, fan=fan), None)
    replacement = _accepted_update(_insert(binary, updated, pivot, _extent(5), fan=fan,
                                            generation=0, free=3),
                                   updated, fan=fan, generation=0)
    replacement_blocks = [
        _block(8, 0, [pivot], [_extent(5)], fan=fan),
        _block(9, 0, [inserted], [8, 4], fan=fan, branch=True),
        _block(10, 0, [pivot], [5, 9], fan=fan, branch=True),
    ]
    ensure(replacement == (updated[0] + replacement_blocks, updated[1] + [0] * 3, 10, 2),
           "separator-equal replacement or unchanged sibling references disagree")
    _answer(_read(binary, (replacement[0], replacement[1], 7, 2), pivot, fan=fan), _extent(2))
    _answer(_read(binary, replacement, pivot, fan=fan), _extent(5))

    empty = ([_block(0, 1, [], [], fan=fan),
              _block(1, 2, [pivot], [0, 0], fan=fan, branch=True)], [1, 2], 1, 1)
    shared = _accepted_update(_insert(binary, empty, pivot, _extent(6), fan=fan, generation=3),
                              empty, fan=fan, generation=3)
    ensure(shared[0][3] == _block(3, 3, [pivot], [0, 2], fan=fan, branch=True),
           "updating one inherited interval replaced both references to an empty node")
    ensure(_candidate_map(shared, fan=fan) == ({pivot: _extent(6)}, {0, 2, 3}),
           "shared empty subtree was changed or lost")

    for free, visits, depth in ((4, 6, 2), (5, 5, 2), (5, 3, 2), (5, 6, 1)):
        _update_refusal(_insert(binary, prior, inserted, _extent(4), fan=fan,
                                generation=generation, free=free, visits=visits, depth=depth))
    _update_refusal(_insert(binary, prior, inserted, _extent(4), fan=fan,
                            generation=generation, invalid_extent=True), staged=False)
    # A valid node in the suffix is named by a branch outside the update path.
    # The parent and selected branch have locally valid references.
    outside_blocks = [*updated[0], _block(8, 11, [left], [_extent(1)], fan=fan)]
    outside_blocks[5] = _block(5, generation, [], [8], fan=fan, branch=True)
    outside = (outside_blocks, [*updated[1], 11], 7, 2)
    _update_refusal(_insert(binary, outside, inserted, _extent(4), fan=fan,
                            generation=generation, used=8), staged=False)

    if generated:
        keys: list[Key] = []
        for word in range(6):
            for value in (0, 1 << 32, MAXIMUM):
                fields = [7] * 6
                fields[word] = value
                keys.append((fields[0], fields[1], fields[2], fields[3], fields[4], fields[5]))
        for fan in (2, 3, 4, 16):
            answers: dict[Key, bytes] = {}
            current = ([_block(0, 0, [], [], fan=fan)], [0], 0, 0)
            # Descending order stresses first-child shifts, opposite the exact
            # right-child split above. A second population mixes all orders.
            order = sorted(keys, reverse=True) if fan % 2 == 0 else keys[::2] + keys[1::2]
            for i, key in enumerate(order + keys[::2], 1):
                answers[key] = _extent(i)
                result = _insert(binary, current, key, answers[key], fan=fan, generation=i, free=32)
                previous = current
                current = _accepted_update(result, previous, fan=fan, generation=i)
                actual, referenced = _candidate_map(current, fan=fan)
                ensure(actual == answers, "update disagrees with independent tuple-to-extent map")
                ensure(all(node in referenced for node in range(len(previous[0]), len(current[0]))),
                       "candidate appended unreachable nodes")
                _answer(_read(binary, current, key, fan=fan), answers[key])


def _exercise_delete(binary: Path, *, generated: bool) -> None:
    k0: Key = (8, 9, 0, 1 << 63, MAXIMUM, 1)
    k1: Key = (8, 9, 0, 1 << 63, MAXIMUM, 2)
    k2: Key = (8, 9, 0, 1 << 63, MAXIMUM, 1 << 32)
    k3: Key = (8, 9, 0, 1 << 63, MAXIMUM, MAXIMUM)
    missing: Key = (8, 9, 0, 1 << 63, MAXIMUM, 3)

    fan = 3
    blocks = [
        _block(0, 10, [k0, k1], [_extent(1), _extent(2)], fan=fan),
        _block(1, 11, [k2], [_extent(3)], fan=fan),
        _block(2, 12, [k3], [_extent(4)], fan=fan),
        _block(3, 13, [k2, k3], [0, 1, 2], fan=fan, branch=True),
    ]
    base = (blocks, [10, 11, 12, 13], 3, 1)
    _update_refusal(_delete(binary, base, missing, fan=fan, generation=20), staged=False)

    # Non-empty leaf shrink preserves sibling leaves and retained root.
    shrink = _accepted_update(_delete(binary, base, k0, fan=fan, generation=20), base, fan=fan, generation=20)
    shrink_expected = [
        _block(4, 20, [k1], [_extent(2)], fan=fan),
        _block(5, 20, [k2, k3], [4, 1, 2], fan=fan, branch=True),
    ]
    ensure(shrink == (blocks + shrink_expected, [10, 11, 12, 13, 20, 20], 5, 1),
           "exact non-empty leaf shrink bytes disagree")
    ensure(_candidate_map(shrink, fan=fan) == ({k1: _extent(2), k2: _extent(3), k3: _extent(4)}, {1, 2, 4, 5}),
           "leaf shrink candidate map or sibling references disagree")
    _answer(_read(binary, (shrink[0], shrink[1], 3, 1), k0, fan=fan), _extent(1))
    _answer(_read(binary, shrink, k0, fan=fan), None)

    # Empty-leaf pruning at route == 0 drops keys[0] (k2) and keeps k3.
    prune_r0 = _accepted_update(_delete(binary, shrink, k1, fan=fan, generation=21), shrink, fan=fan, generation=21)
    prune_r0_expected = [_block(6, 21, [k3], [1, 2], fan=fan, branch=True)]
    ensure(prune_r0 == (shrink[0] + prune_r0_expected, shrink[1] + [21], 6, 1),
           "exact route == 0 empty-leaf pruning bytes disagree")
    ensure(_candidate_map(prune_r0, fan=fan) == ({k2: _extent(3), k3: _extent(4)}, {1, 2, 6}),
           "route == 0 pruning map or sibling references disagree")
    _answer(_read(binary, (prune_r0[0], prune_r0[1], 5, 1), k1, fan=fan), _extent(2))
    _answer(_read(binary, prune_r0, k2, fan=fan), _extent(3))

    # Empty-leaf pruning at route > 0 drops keys[route - 1] (interior and last child).
    prune_r1 = _accepted_update(_delete(binary, base, k2, fan=fan, generation=30), base, fan=fan, generation=30)
    ensure(prune_r1 == ([*blocks, _block(4, 30, [k3], [0, 2], fan=fan, branch=True)], [10, 11, 12, 13, 30], 4, 1),
           "exact route == 1 empty-leaf pruning bytes disagree")
    prune_r2 = _accepted_update(_delete(binary, base, k3, fan=fan, generation=31), base, fan=fan, generation=31)
    ensure(prune_r2 == ([*blocks, _block(4, 31, [k2], [0, 1], fan=fan, branch=True)], [10, 11, 12, 13, 31], 4, 1),
           "exact route == 2 empty-leaf pruning bytes disagree")

    # Multi-level single-child root collapse (height 2 -> 1 -> 0) promotes retained leaf into suffix.
    h2_blocks = [
        _block(0, 1, [k0], [_extent(1)], fan=2),
        _block(1, 2, [k3], [_extent(4)], fan=2),
        _block(2, 3, [], [0], fan=2, branch=True),
        _block(3, 4, [], [1], fan=2, branch=True),
        _block(4, 5, [k3], [2, 3], fan=2, branch=True),
    ]
    h2 = (h2_blocks, [1, 2, 3, 4, 5], 4, 2)
    collapsed = _accepted_update(_delete(binary, h2, k0, fan=2, generation=9), h2, fan=2, generation=9)
    ensure(collapsed == ([*h2_blocks, _block(5, 9, [k3], [_extent(4)], fan=2)], [1, 2, 3, 4, 5, 9], 5, 0),
           "multi-level single-child root collapse bytes disagree")
    ensure(_candidate_map(collapsed, fan=2) == ({k3: _extent(4)}, {5}),
           "collapsed root map or reachable node set disagrees")
    _answer(_read(binary, (collapsed[0], collapsed[1], 4, 2), k0, fan=2), _extent(1))
    _answer(_read(binary, (collapsed[0], collapsed[1], 4, 2), k3, fan=2), _extent(4))
    _answer(_read(binary, collapsed, k3, fan=2), _extent(4))

    # Final deletion yields an empty leaf root at height 0 while preserving prior roots.
    emptied = _accepted_update(_delete(binary, collapsed, k3, fan=2, generation=10), collapsed, fan=2, generation=10)
    ensure(emptied == ([*collapsed[0], _block(6, 10, [], [], fan=2)], [1, 2, 3, 4, 5, 9, 10], 6, 0),
           "final deletion to empty leaf root disagrees")
    ensure(_candidate_map(emptied, fan=2) == ({}, {6}), "empty leaf root map disagrees")
    _answer(_read(binary, (emptied[0], emptied[1], 5, 0), k3, fan=2), _extent(4))
    _answer(_read(binary, (emptied[0], emptied[1], 4, 2), k3, fan=2), _extent(4))
    _answer(_read(binary, emptied, k3, fan=2), None)
    _update_refusal(_delete(binary, emptied, k3, fan=2, generation=11), staged=False)

    # Exhaustion and off-route suffix-reference refusals.
    for free, visits, depth in ((0, 4096, 16), (1, 4096, 16), (8, 3, 16), (8, 4096, 0)):
        _update_refusal(_delete(binary, base, k0, fan=fan, generation=20, free=free, visits=visits, depth=depth))
    outside_blocks = [*h2_blocks, _block(5, 11, [k3], [_extent(4)], fan=2)]
    outside_blocks[0] = _block(0, 1, [k0, k1], [_extent(1), _extent(2)], fan=2)
    outside_blocks[3] = _block(3, 4, [], [5], fan=2, branch=True)
    outside = (outside_blocks, [1, 2, 3, 4, 5, 11], 4, 2)
    _update_refusal(_delete(binary, outside, k0, fan=2, generation=9, used=5, free=4), staged=False)

    if generated:
        keys: list[Key] = []
        for word in range(6):
            for value in (0, 1 << 32, MAXIMUM):
                fields = [7] * 6
                fields[word] = value
                keys.append((fields[0], fields[1], fields[2], fields[3], fields[4], fields[5]))
        unique_keys = sorted(set(keys))
        for fan in (2, 3, 4, 16):
            answers: dict[Key, bytes] = {}
            current = ([_block(0, 0, [], [], fan=fan)], [0], 0, 0)
            insert_order = list(reversed(unique_keys)) if fan == 2 else list(unique_keys)
            for i, key in enumerate(insert_order, 1):
                answers[key] = _extent(i)
                current = _accepted_update(
                    _insert(binary, current, key, answers[key], fan=fan, generation=i, free=32),
                    current, fan=fan, generation=i)
            if fan == 2:
                del_order = list(unique_keys)
            elif fan == 3:
                del_order = list(reversed(unique_keys))
            elif fan == 4:
                del_order = unique_keys[::2] + list(reversed(unique_keys[1::2]))
            else:
                del_order = unique_keys[1::2] + unique_keys[::2]
            for step, key in enumerate(del_order, len(unique_keys) + 1):
                deleted_extent = answers.pop(key)
                previous = current
                current = _accepted_update(
                    _delete(binary, previous, key, fan=fan, generation=step, free=32),
                    previous, fan=fan, generation=step)
                actual, referenced = _candidate_map(current, fan=fan)
                ensure(actual == answers, "delete disagrees with independent tuple-to-extent map")
                ensure(all(node in referenced for node in range(len(previous[0]), len(current[0]))),
                       "delete candidate appended unreachable nodes")
                _answer(_read(binary, (current[0], current[1], previous[2], previous[3]), key, fan=fan),
                        deleted_extent)
                _answer(_read(binary, current, key, fan=fan), None)
            ensure(current[3] == 0 and answers == {}, "deleting every key must collapse to empty leaf at height 0")


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


def _tree_signature(tree: Tree, *, fan: int) -> tuple[int, tuple[object, ...]]:
    blocks, generations, root, height = tree

    def walk(node: int, depth: int) -> tuple[object, ...]:
        raw = blocks[node]
        kind, count, identity, generation = struct.unpack_from("<IIQQ", raw, 8)
        ensure(identity == node and generation == generations[node] and count <= fan,
               "signature node identity, generation or occupancy disagrees")
        if depth == 0:
            ensure(kind == 0, "expected leaf at depth 0")
            keys = tuple(struct.unpack_from(">6Q", raw, 32 + 144 * i) for i in range(count))
            extents = tuple(raw[80 + 144 * i:176 + 144 * i] for i in range(count))
            return ("L", keys, extents)
        ensure(kind == 1 and count > 0, "expected branch above depth 0")
        keys = tuple(struct.unpack_from(">6Q", raw, 32 + 48 * i) for i in range(count - 1))
        children = struct.unpack_from(f"<{count}Q", raw, 32 + 48 * (count - 1))
        return ("B", keys, tuple(walk(child, depth - 1) for child in children))

    return height, walk(root, height)


def _full_width_keys(extra_seed: int | None = None) -> list[Key]:
    keys: set[Key] = set()
    for word in range(6):
        for value in (0, 1, 1 << 32, MAXIMUM):
            fields = [7] * 6
            fields[word] = value
            keys.add((fields[0], fields[1], fields[2], fields[3], fields[4], fields[5]))
    if extra_seed is not None:
        rng = random.Random(extra_seed)  # noqa: S311 - reproducible public tuple vectors
        keys.update((rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64),
                     rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64))
                    for _ in range(46))
    return sorted(keys)


def _exercise_insert_batch(binary: Path, *, generated: bool) -> None:
    k0: Key = (1, 0, 0, 0, 0, 1)
    k1: Key = (1, 0, 0, 0, 0, 1 << 32)
    k2: Key = (1, 0, 0, 0, 1, 0)
    k3: Key = (1, 0, 0, 1, 0, 0)
    k4: Key = (1, 0, MAXIMUM, 0, 0, 0)
    k5: Key = (MAXIMUM, 0, 0, 0, 0, 1)

    fan = 2
    base_blocks = [
        _block(0, 3, [k0], [_extent(1)], fan=fan),
        _block(1, 5, [k2, k4], [_extent(2), _extent(3)], fan=fan),
        _block(2, 7, [k2], [0, 1], fan=fan, branch=True),
    ]
    base: Tree = (base_blocks, [3, 5, 7], 2, 1)
    # Mixed replace + insert on the right subtree only: left sibling (node 0, gen 3) is preserved.
    batch = [(k2, _extent(10)), (k3, _extent(11)), (k5, _extent(12))]
    updated = _accepted_update(
        _insert_batch(binary, base, batch, fan=fan, generation=9, free=16, visits=16, depth=4),
        base, fan=fan, generation=9)
    expected_map = {k0: _extent(1), k2: _extent(10), k3: _extent(11), k4: _extent(3), k5: _extent(12)}
    actual_map, referenced = _candidate_map(updated, fan=fan)
    ensure(actual_map == expected_map and 0 in referenced and 1 not in referenced,
           "batch insert+replace must preserve untouched sibling subtree and update right subtree")
    ensure(all(node in referenced for node in range(len(base_blocks), len(updated[0]))),
           "batch insert appended unreachable nodes")
    _answer(_read(binary, (updated[0], updated[1], 2, 1), k2, fan=fan), _extent(2))
    _answer(_read(binary, (updated[0], updated[1], 2, 1), k3, fan=fan), None)
    _answer(_read(binary, updated, k2, fan=fan), _extent(10))

    # Multi-level root growth from a single empty leaf in one pass (height 0 -> 2 at fan 2).
    empty: Tree = ([_block(0, 1, [], [], fan=fan)], [1], 0, 0)
    six = [(k0, _extent(1)), (k1, _extent(2)), (k2, _extent(3)),
           (k3, _extent(4)), (k4, _extent(5)), (k5, _extent(6))]
    grown = _accepted_update(
        _insert_batch(binary, empty, six, fan=fan, generation=2, free=16, visits=32, depth=4),
        empty, fan=fan, generation=2)
    ensure(grown[3] == 2 and _candidate_map(grown, fan=fan)[0] == dict(six),
           "single-pass multi-level batch growth failed")

    # Empty, unsorted, duplicate, oversized, and invalid-extent batch refusals (staged=False).
    _update_refusal(_insert_batch(binary, base, [], fan=fan, generation=10), staged=False)
    _update_refusal(_insert_batch(binary, base, [(k3, _extent(1)), (k1, _extent(2))],
                                  fan=fan, generation=10), staged=False)
    _update_refusal(_insert_batch(binary, base, [(k1, _extent(1)), (k1, _extent(2))],
                                  fan=fan, generation=10), staged=False)
    oversized = [((1, 0, 0, 0, 0, i + 1), _extent(i)) for i in range(65)]
    _update_refusal(_insert_batch(binary, empty, oversized, fan=fan, generation=10, free=256), staged=False)
    _update_refusal(_insert_batch(binary, base, batch, fan=fan, generation=10, invalid_extent=True),
                    staged=False)

    # Bounded allocation, depth, prior visit, and candidate visit exhaustion refusals.
    _update_refusal(_insert_batch(binary, empty, six, fan=fan, generation=10, free=2))
    _update_refusal(_insert_batch(binary, empty, six, fan=fan, generation=10, free=16, depth=1))
    _update_refusal(_insert_batch(binary, base, batch, fan=fan, generation=10, visits=2), staged=False)
    _update_refusal(_insert_batch(binary, base, batch, fan=fan, generation=10, visits=3))

    # Reachable off-route suffix reference refuses before any suffix write.
    off_blocks = [*base_blocks, _block(3, 11, [k0], [_extent(1)], fan=fan)]
    off_blocks[2] = _block(2, 7, [k2], [3, 1], fan=fan, branch=True)
    off_route: Tree = (off_blocks, [3, 5, 7, 11], 2, 1)
    _update_refusal(_insert_batch(binary, off_route, [(k5, _extent(20))], fan=fan,
                                  generation=12, used=3, free=8), staged=False)

    if generated:
        all_keys = _full_width_keys(0x53DB)
        for cur_fan in (2, 3, 4, 16):
            sample = all_keys[:min(40, 2 * cur_fan * cur_fan + 4)]
            seq_tree: Tree = ([_block(0, 0, [], [], fan=cur_fan)], [0], 0, 0)
            for idx, key in enumerate(sample, 1):
                seq_tree = _accepted_update(
                    _insert(binary, seq_tree, key, _extent(idx), fan=cur_fan, generation=1, free=32),
                    seq_tree, fan=cur_fan, generation=1)
            batch_entries = [(key, _extent(idx)) for idx, key in enumerate(sample, 1)]
            batch_tree = _accepted_update(
                _insert_batch(binary, ([_block(0, 0, [], [], fan=cur_fan)], [0], 0, 0),
                              batch_entries, fan=cur_fan, generation=1, free=128),
                ([_block(0, 0, [], [], fan=cur_fan)], [0], 0, 0), fan=cur_fan, generation=1)
            ensure(_candidate_map(batch_tree, fan=cur_fan)[0] == _candidate_map(seq_tree, fan=cur_fan)[0],
                   "batch insert disagrees with sequential insertions")
            ensure(len(batch_tree[0]) < len(seq_tree[0]),
                   "single-pass sorted batch must allocate fewer nodes than sequential inserts")

            # Multi-batch with mixed replacements and new keys.
            first_half = [(key, _extent(idx)) for idx, key in enumerate(all_keys[:32], 1)]
            second_half = sorted(
                [(key, _extent(idx + 100)) for idx, key in enumerate(all_keys[:32:2], 1)]
                + [(key, _extent(idx + 200)) for idx, key in enumerate(all_keys[32:64], 1)],
                key=lambda item: item[0],
            )
            t1 = _accepted_update(
                _insert_batch(binary, ([_block(0, 0, [], [], fan=cur_fan)], [0], 0, 0),
                              first_half, fan=cur_fan, generation=10, free=128),
                ([_block(0, 0, [], [], fan=cur_fan)], [0], 0, 0), fan=cur_fan, generation=10)
            t2 = _accepted_update(
                _insert_batch(binary, t1, second_half, fan=cur_fan, generation=20, free=128),
                t1, fan=cur_fan, generation=20)
            expected_multi = dict(first_half)
            expected_multi.update(dict(second_half))
            actual_multi, referenced_multi = _candidate_map(t2, fan=cur_fan)
            ensure(actual_multi == expected_multi, "multi-batch insert+replace map disagrees")
            ensure(all(node in referenced_multi for node in range(len(t1[0]), len(t2[0]))),
                   "multi-batch appended unreachable nodes")
            for key, extent in first_half[:4]:
                _answer(_read(binary, (t2[0], t2[1], t1[2], t1[3]), key, fan=cur_fan), extent)
            for key, extent in list(expected_multi.items())[::5]:
                _answer(_read(binary, t2, key, fan=cur_fan), extent)

        # Maximum 64-entry batch on fan=2 (single-pass height 0 -> 5).
        max_batch = [(key, _extent(idx)) for idx, key in enumerate(all_keys[:64], 1)]
        max_tree = _accepted_update(
            _insert_batch(binary, ([_block(0, 0, [], [], fan=2)], [0], 0, 0),
                          max_batch, fan=2, generation=55, free=128),
            ([_block(0, 0, [], [], fan=2)], [0], 0, 0), fan=2, generation=55)
        max_actual, max_ref = _candidate_map(max_tree, fan=2)
        ensure(max_actual == dict(max_batch) and max_tree[3] == 5 and len(max_tree[0]) == 64,
               "max-size 64-entry fan=2 batch failed expected layout")
        ensure(all(node in max_ref for node in range(1, len(max_tree[0]))),
               "max-size batch appended unreachable nodes")


def _exercise_compact(binary: Path, *, generated: bool) -> None:
    k0: Key = (2, 0, 0, 0, 0, 1)
    k1: Key = (2, 0, 0, 0, 0, 2)
    k2: Key = (2, 0, 0, 0, 1, 0)
    k3: Key = (2, 0, 0, 1, 0, 0)
    fan = 2

    # Empty leaf compacts to a fresh empty leaf at height 0 in generation.
    empty: Tree = ([_block(0, 4, [], [], fan=fan)], [4], 0, 0)
    comp_empty = _accepted_update(_compact(binary, empty, fan=fan, generation=9, free=4),
                                  empty, fan=fan, generation=9)
    ensure(comp_empty == ([*empty[0], _block(1, 9, [], [], fan=fan)], [4, 9], 1, 0),
           "empty tree compaction disagrees")

    # Shared empty-leaf branch collapses to a single empty leaf at height 0.
    empty_branch: Tree = ([_block(0, 1, [], [], fan=fan),
                           _block(1, 2, [k1], [0, 0], fan=fan, branch=True)], [1, 2], 1, 1)
    comp_eb = _accepted_update(_compact(binary, empty_branch, fan=fan, generation=8, free=4),
                               empty_branch, fan=fan, generation=8)
    ensure(comp_eb[2:] == (2, 0) and _candidate_map(comp_eb, fan=fan) == ({}, {2}),
           "empty multi-node tree compaction must collapse to empty leaf at height 0")

    # Single-entry leaf compacts cleanly even at depth_limit == 0.
    single: Tree = ([_block(0, 3, [k0], [_extent(1)], fan=fan)], [3], 0, 0)
    comp_single = _accepted_update(_compact(binary, single, fan=fan, generation=7, free=4, depth=0),
                                   single, fan=fan, generation=7)
    ensure(comp_single[2:] == (1, 0) and _candidate_map(comp_single, fan=fan) == ({k0: _extent(1)}, {1}),
           "single-leaf compaction at depth 0 disagrees")

    # Sparse multi-level tree compacts to canonical full-left layout and preserves retained roots.
    sparse_blocks = [
        _block(0, 1, [k0], [_extent(1)], fan=fan),
        _block(1, 2, [k1], [_extent(2)], fan=fan),
        _block(2, 3, [k2], [_extent(3)], fan=fan),
        _block(3, 4, [k1], [0, 1], fan=fan, branch=True),
        _block(4, 5, [], [2], fan=fan, branch=True),
        _block(5, 6, [k2], [3, 4], fan=fan, branch=True),
    ]
    sparse: Tree = (sparse_blocks, [1, 2, 3, 4, 5, 6], 5, 2)
    comp_sparse = _accepted_update(_compact(binary, sparse, fan=fan, generation=15, free=8),
                                   sparse, fan=fan, generation=15)
    expected_sparse = [
        _block(6, 15, [k0, k1], [_extent(1), _extent(2)], fan=fan),
        _block(7, 15, [k2], [_extent(3)], fan=fan),
        _block(8, 15, [k2], [6, 7], fan=fan, branch=True),
    ]
    ensure(comp_sparse == (sparse_blocks + expected_sparse, [1, 2, 3, 4, 5, 6, 15, 15, 15], 8, 1),
           "sparse multi-level tree compaction bytes disagree")
    _answer(_read(binary, (comp_sparse[0], comp_sparse[1], 5, 2), k0, fan=fan), _extent(1))
    _answer(_read(binary, comp_sparse, k2, fan=fan), _extent(3))

    # Exhaustion and off-route suffix-reference refusals.
    _update_refusal(_compact(binary, sparse, fan=fan, generation=15, free=0))
    _update_refusal(_compact(binary, sparse, fan=fan, generation=15, free=2))
    _update_refusal(_compact(binary, sparse, fan=fan, generation=15, free=8, depth=0))
    _update_refusal(_compact(binary, sparse, fan=fan, generation=15, free=8, visits=2), staged=False)
    off_blocks = [*sparse_blocks, _block(6, 11, [k3], [_extent(4)], fan=fan)]
    off_blocks[4] = _block(4, 5, [], [6], fan=fan, branch=True)
    off_route: Tree = (off_blocks, [1, 2, 3, 4, 5, 6, 11], 5, 2)
    _update_refusal(_compact(binary, off_route, fan=fan, generation=15, used=6, free=8), staged=False)
    off_order_blocks = [
        _block(0, 1, [k0, k1], [_extent(1), _extent(2)], fan=fan),
        _block(1, 2, [k3, k2], [_extent(4), _extent(3)], fan=fan),
        _block(2, 3, [k2], [0, 1], fan=fan, branch=True),
    ]
    off_order: Tree = (off_order_blocks, [1, 2, 3], 2, 1)
    _update_refusal(_compact(binary, off_order, fan=fan, generation=15, free=8), staged=False)

    if generated:
        all_keys = _full_width_keys(0xC039AC7)
        for cur_fan in (2, 3, 4, 16):
            kept = all_keys[::2][:min(36, 2 * cur_fan * cur_fan + 3)]
            extra = all_keys[1::2][:cur_fan + 4]
            answers = {key: _extent(idx) for idx, key in enumerate(kept, 1)}

            # History A: sorted batch inserts with mixed replacements.
            tree_a: Tree = ([_block(0, 0, [], [], fan=cur_fan)], [0], 0, 0)
            mid = len(kept) // 2
            tree_a = _accepted_update(
                _insert_batch(binary, tree_a, [(k, _extent(999)) for k in kept[:mid]],
                              fan=cur_fan, generation=1, free=128),
                tree_a, fan=cur_fan, generation=1)
            tree_a = _accepted_update(
                _insert_batch(binary, tree_a, [(k, answers[k]) for k in kept],
                              fan=cur_fan, generation=2, free=128),
                tree_a, fan=cur_fan, generation=2)

            # History B: reverse single-key insertions with extra keys, then interleaved deletions.
            tree_b: Tree = ([_block(0, 0, [], [], fan=cur_fan)], [0], 0, 0)
            combined = sorted(kept + extra, reverse=True)
            for step, key in enumerate(combined, 1):
                ext = answers.get(key, _extent(700 + step))
                tree_b = _accepted_update(
                    _insert(binary, tree_b, key, ext, fan=cur_fan, generation=step, free=32),
                    tree_b, fan=cur_fan, generation=step)
            del_order = extra[1::2] + extra[::2]
            for step, key in enumerate(del_order, len(combined) + 1):
                tree_b = _accepted_update(
                    _delete(binary, tree_b, key, fan=cur_fan, generation=step, free=32),
                    tree_b, fan=cur_fan, generation=step)

            comp_a = _accepted_update(_compact(binary, tree_a, fan=cur_fan, generation=777, free=128),
                                      tree_a, fan=cur_fan, generation=777)
            comp_b = _accepted_update(_compact(binary, tree_b, fan=cur_fan, generation=777, free=128),
                                      tree_b, fan=cur_fan, generation=777)
            map_a, ref_a = _candidate_map(comp_a, fan=cur_fan)
            map_b, ref_b = _candidate_map(comp_b, fan=cur_fan)
            ensure(map_a == answers and map_b == answers,
                   "compaction must preserve exact tuple-to-extent map across histories")
            ensure(all(n in ref_a for n in range(len(tree_a[0]), len(comp_a[0]))) and
                   all(n in ref_b for n in range(len(tree_b[0]), len(comp_b[0]))),
                   "compaction appended unreachable nodes")
            ensure(_tree_signature(comp_a, fan=cur_fan) == _tree_signature(comp_b, fan=cur_fan),
                   "compacted typed trees must be strictly history-independent")
            for probe in (kept[0], kept[len(kept) // 2], kept[-1]):
                _answer(_read(binary, (comp_a[0], comp_a[1], tree_a[2], tree_a[3]), probe, fan=cur_fan),
                        answers[probe])
                _answer(_read(binary, (comp_b[0], comp_b[1], tree_b[2], tree_b[3]), probe, fan=cur_fan),
                        answers[probe])

            # Pad shorter arena prefix to equal used so newly appended VOSTYP01 bytes match verbatim.
            equal_used = max(len(tree_a[0]), len(tree_b[0]))
            pad_size = 32 + 144 * cur_fan
            eq_a: Tree = (tree_a[0] + [bytes(pad_size)] * (equal_used - len(tree_a[0])),
                          tree_a[1] + [0] * (equal_used - len(tree_a[1])), tree_a[2], tree_a[3])
            eq_b: Tree = (tree_b[0] + [bytes(pad_size)] * (equal_used - len(tree_b[0])),
                          tree_b[1] + [0] * (equal_used - len(tree_b[1])), tree_b[2], tree_b[3])
            eq_comp_a = _accepted_update(_compact(binary, eq_a, fan=cur_fan, generation=777, free=128),
                                         eq_a, fan=cur_fan, generation=777)
            eq_comp_b = _accepted_update(_compact(binary, eq_b, fan=cur_fan, generation=777, free=128),
                                         eq_b, fan=cur_fan, generation=777)
            ensure(eq_comp_a[2:] == eq_comp_b[2:] and
                   eq_comp_a[0][equal_used:] == eq_comp_b[0][equal_used:],
                   "compacted VOSTYP01 output bytes must be byte-identical across histories")


def typed_tree() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "typed-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="typed-", dir=work) as directory:
        binary = _build(Path(directory))
        _exercise(binary, generated=True)
        _exercise_update(binary, generated=True)
        _exercise_delete(binary, generated=True)
        _exercise_insert_batch(binary, generated=True)
        _exercise_compact(binary, generated=True)


def typed_tree_mutants() -> None:
    source = (ROOT / "storage/src/typed_tree.c").read_text(encoding="utf-8")
    mutations = [
        ("omit version comparison", "i < 6u", "i < 5u"),
        ("route equality left", "compare(&node->keys[route], key) <= 0",
         "compare(&node->keys[route], key) < 0"),
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


def typed_update_mutants() -> None:
    source = (ROOT / "storage/src/typed_tree.c").read_text(encoding="utf-8")
    mutations = [
        ("lose updated digest metadata", "draft.values.extents[at] = *update->extent;",
         "draft.values.extents[at] = *update->extent; draft.values.extents[at].content_digest[31] ^= 1u;"),
        ("overwrite retained prefix", ".next = arena->used", ".next = 0u"),
        ("use wrong appended generation", ".generation = update->generation\n",
         ".generation = update->generation - 1u\n"),
        ("promote left leaf split key", "draft->kind == VOS_NODE_LEAF ? cut : cut - 1u", "cut - 1u"),
        ("skip prior off-route admission", "vos_typed_tree_lookup(&update.input",
         "vos_typed_tree_lookup_path(&update.input"),
        ("skip candidate off-route admission", "vos_typed_tree_lookup(&image, &candidate_limits",
         "vos_typed_tree_lookup_path(&image, &candidate_limits"),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "typed-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="typed-update-mutants-", dir=work) as directory:
        for index, (label, old, new) in enumerate(mutations):
            ensure(source.count(old) == 1, f"mutation site drift: {label}")
            binary = _build(Path(directory) / str(index), source.replace(old, new))
            caught = False
            try:
                _exercise_update(binary, generated=False)
            except AssertionError:
                caught = True
            ensure(caught, f"compiled and executed typed update mutant survived: {label}")


def typed_delete_mutants() -> None:
    source = (ROOT / "storage/src/typed_tree.c").read_text(encoding="utf-8")
    mutations = [
        ("missing key accepted", "vos_typed_tree_lookup(&del.prior, limits, root, key, &checked) != VOS_TREE_FOUND",
         "vos_typed_tree_lookup(&del.prior, limits, root, key, &checked) == VOS_TREE_REFUSED"),
        ("skip key removal in leaf", "if (compare(&node->keys[i], del->key) == 0) continue;", "if (0) continue;"),
        ("skip empty-subtree pruning", "if (out.count == 0u)", "if (0)"),
        ("omit single-child root collapse", "while (candidate.height > 0u && candidate.root < arena->used)", "while (0)"),
        ("wrong separator shift on route == 0", "out.keys[i] = node->keys[i + 1u];",
         "out.keys[i] = node->keys[i];"),
        ("wrong separator shift on route > 0", "out.keys[i - 1u] = node->keys[i];",
         "out.keys[i - 1u] = node->keys[i - 1u];"),
        ("skip prior off-route admission", "vos_typed_tree_lookup(&del.prior",
         "vos_typed_tree_lookup_path(&del.prior"),
        ("overwrite retained prefix on delete", ".cursor = arena->used", ".cursor = 0u"),
        ("use wrong generation on delete", "node->generation = del->generation;",
         "node->generation = del->generation - 1u;"),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "typed-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="typed-delete-mutants-", dir=work) as directory:
        for index, (label, old, new) in enumerate(mutations):
            ensure(source.count(old) == 1, f"mutation site drift: {label}")
            binary = _build(Path(directory) / str(index), source.replace(old, new))
            caught = False
            try:
                _exercise_delete(binary, generated=False)
            except AssertionError:
                caught = True
            ensure(caught, f"compiled and executed typed delete mutant survived: {label}")


def typed_insert_batch_mutants() -> None:
    source = (ROOT / "storage/src/typed_tree.c").read_text(encoding="utf-8")
    mutations = [
        ("accept empty or oversized batch", "entry_count == 0u || entry_count > VOS_TREE_MAX_BATCH",
         "entry_count > VOS_TREE_MAX_BATCH + 1u"),
        ("accept unsorted batch keys", "compare(&entries[i - 1u].key, &entries[i].key) >= 0", "0"),
        ("drop extent metadata in batch leaf merge",
         "keys[total] = entries[j].key;\n            extents[total] = entries[j].extent;\n            ++j;",
         "keys[total] = entries[j].key;\n            extents[total] = entries[j].extent;\n"
         "            extents[total].content_digest[31] ^= 1u;\n            ++j;"),
        ("wrong branch split separator in publish_typed_batch",
         "keys[kind == VOS_NODE_LEAF ? offset : offset - 1u]", "keys[offset - 1u]"),
        ("skip prior off-route admission on batch",
         "vos_typed_tree_lookup(&batch.input, limits, root, &entries[0].key, &checked)",
         "vos_typed_tree_lookup_path(&batch.input, limits, root, &entries[0].key, &checked)"),
        ("skip candidate off-route admission on batch",
         "? vos_typed_tree_lookup(&batch_image, &batch_limits, candidate.root, &entries[i].key, &checked)",
         "? vos_typed_tree_lookup_path(&batch_image, &batch_limits, candidate.root, &entries[i].key, &checked)"),
        ("overwrite retained prefix on batch", ".append_at = arena->used", ".append_at = 0u"),
        ("use wrong generation on batch", ".generation = batch->generation",
         ".generation = batch->generation - 1u"),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "typed-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="typed-batch-mutants-", dir=work) as directory:
        for index, (label, old, new) in enumerate(mutations):
            ensure(source.count(old) == 1, f"mutation site drift: {label}")
            binary = _build(Path(directory) / str(index), source.replace(old, new))
            caught = False
            try:
                _exercise_insert_batch(binary, generated=False)
            except AssertionError:
                caught = True
            ensure(caught, f"compiled and executed typed insert-batch mutant survived: {label}")


def typed_compact_mutants() -> None:
    source = (ROOT / "storage/src/typed_tree.c").read_text(encoding="utf-8")
    mutations = [
        ("skip prior off-route admission on compact",
         "vos_typed_tree_lookup(&prior, limits, root, &zero_key, &checked)",
         "vos_typed_tree_lookup_path(&prior, limits, root, &zero_key, &checked)"),
        ("emit empty leaf with nonzero height on compact",
         "if (!compact_append(&builder, &empty_leaf, &candidate.root)) return 0;\n        candidate.height = 0u;",
         "if (!compact_append(&builder, &empty_leaf, &candidate.root)) return 0;\n        candidate.height = 1u;"),
        ("wrong branch separator in compact",
         "branch->keys[branch->count - 1u] = *child_min;",
         "branch->keys[branch->count - 1u] = builder->min_keys[level];"),
        ("skip leaf entry emission in compact",
         "if (!compact_emit_entry(builder, &node.keys[i], &node.extents[i])) return 0;",
         "if (i != 0u && !compact_emit_entry(builder, &node.keys[i], &node.extents[i])) return 0;"),
        ("overwrite retained prefix on compact", ".next_id = arena->used,", ".next_id = 0u,"),
        ("use wrong generation on compact", "node->generation = builder->generation;",
         "node->generation = builder->generation - 1u;"),
        ("wrong leaf key copy in compact",
         "leaf->keys[leaf->count] = *key;",
         "leaf->keys[leaf->count] = builder->min_keys[0];"),
        ("corrupt extent digest on compact",
         "leaf->extents[leaf->count] = *extent;",
         "leaf->extents[leaf->count] = *extent; leaf->extents[leaf->count].content_digest[0] ^= 1u;"),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "typed-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="typed-compact-mutants-", dir=work) as directory:
        for index, (label, old, new) in enumerate(mutations):
            ensure(source.count(old) == 1, f"mutation site drift: {label}")
            binary = _build(Path(directory) / str(index), source.replace(old, new))
            caught = False
            try:
                _exercise_compact(binary, generated=False)
            except AssertionError:
                caught = True
            ensure(caught, f"compiled and executed typed compact mutant survived: {label}")


def cases() -> list[Case]:
    return [Case("complete typed nodes route and update full tuples and preserve inline extents", typed_tree, lane="guest"),
            Case("compiled typed routing and admission defects are detected", typed_tree_mutants, lane="guest"),
            Case("compiled typed candidate update defects are detected", typed_update_mutants, lane="guest"),
            Case("compiled typed candidate delete defects are detected", typed_delete_mutants, lane="guest"),
            Case("compiled typed batch insert defects are detected", typed_insert_batch_mutants, lane="guest"),
            Case("compiled typed compact defects are detected", typed_compact_mutants, lane="guest")]
