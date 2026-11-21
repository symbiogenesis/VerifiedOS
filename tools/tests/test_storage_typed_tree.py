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
        binary = _build(Path(directory))
        _exercise(binary, generated=True)
        _exercise_update(binary, generated=True)


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


def cases() -> list[Case]:
    return [Case("complete typed nodes route and update full tuples and preserve inline extents", typed_tree, lane="guest"),
            Case("compiled typed routing and admission defects are detected", typed_tree_mutants, lane="guest"),
            Case("compiled typed candidate update defects are detected", typed_update_mutants, lane="guest")]
