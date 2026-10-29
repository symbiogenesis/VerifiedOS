# SPDX-License-Identifier: Apache-2.0
"""Independent tree/map witnesses for the bounded C node-image read path."""

import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from tests.harness import TOOLS, Case, ensure
from vos import toolenv

ROOT = TOOLS.parent
MAXIMUM = (1 << 64) - 1
SENTINEL = MAXIMUM - 17


class ReadOptions(TypedDict, total=False):
    fan: int
    height: int
    depth: int
    visits: int
    block_bytes: int


def _block(node_id: int, generation: int, keys: list[int], values: list[int],
           *, branch: bool = False, fan: int = 4) -> bytes:
    words = (keys + values if branch else
             [word for pair in zip(keys, values, strict=True) for word in pair])
    content = (b"VOSNODE1" + struct.pack("<IIQQ", int(branch), len(values), node_id, generation)
               + b"".join(struct.pack("<Q", word) for word in words))
    return content.ljust(32 + 16 * fan, b"\0")


def _build(directory: Path, *, source: str | None = None) -> Path:
    compiler = shutil.which("clang") or shutil.which("gcc")
    ensure(compiler is not None, "native C compiler missing")
    if compiler is None:
        raise AssertionError("native C compiler missing")
    directory.mkdir(parents=True, exist_ok=True)
    reader = ROOT / "storage" / "src" / "tree_image.c"
    if source is not None:
        reader = directory / "tree_image.c"
        reader.write_text(source, encoding="utf-8", newline="")
    binary = directory / "tree-image"
    built = subprocess.run([compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-pedantic",
                            "-I", str(ROOT / "storage" / "include"), str(reader),
                            str(ROOT / "storage" / "src" / "node_image.c"),
                            str(ROOT / "storage" / "host" / "tree_image.c"), "-o", str(binary)],
                           capture_output=True, text=True, timeout=60, check=False)
    ensure(built.returncode == 0, f"C compilation failed (not a mutation kill): {built.stderr}")
    return binary


def _read(binary: Path, blocks: list[bytes], generations: list[int], root: int,
          key: int, *, fan: int = 4, height: int = 1, depth: int = 16,
          visits: int = 4096, data: bytes | None = None,
          block_bytes: int | None = None) -> subprocess.CompletedProcess[bytes]:
    size = 32 + 16 * fan if block_bytes is None else block_bytes
    arguments = [fan, len(blocks), size, root, height, depth, visits, key, *generations]
    return subprocess.run([str(binary), *(str(part) for part in arguments)],
                          input=b"".join(blocks) if data is None else data,
                          capture_output=True, timeout=5, check=False)


def _answer(result: subprocess.CompletedProcess[bytes], expected: int | None) -> None:
    ensure(result.returncode == 0, f"valid tree read refused or changed output: {result.stderr!r}")
    ensure(json.loads(result.stdout) == {"found": expected is not None,
                                       "value": SENTINEL if expected is None else expected},
           "independent key/map answer or missing-output preservation disagrees")


def _refused(result: subprocess.CompletedProcess[bytes]) -> None:
    ensure(result.returncode == 2 and not result.stdout,
           "tree defect was accepted, crashed or changed output before refusal")


def _demo() -> tuple[list[bytes], list[int]]:
    return ([_block(0, 0, [1, 2], [10, 20]),
             _block(1, 1, [5, 7], [50, 70]),
             _block(2, 2, [5], [0, 1], branch=True)], [0, 1, 2])


def _tree(keys: list[int], expected: dict[int, int], fan: int
          ) -> tuple[list[bytes], list[int], int, int]:
    blocks: list[bytes] = []
    generations: list[int] = []
    layer: list[tuple[int, int]] = []
    for at in range(0, max(1, len(keys)), fan):
        chunk = keys[at:at + fan]
        node_id = len(blocks)
        generation = node_id % 3
        generations.append(generation)
        blocks.append(_block(node_id, generation, chunk, [expected[key] for key in chunk], fan=fan))
        layer.append((node_id, chunk[0] if chunk else 0))
    height = 0
    while len(layer) > 1:
        following: list[tuple[int, int]] = []
        for at in range(0, len(layer), fan):
            children = layer[at:at + fan]
            node_id = len(blocks)
            generation = node_id % 3
            generations.append(generation)
            blocks.append(_block(node_id, generation, [minimum for _, minimum in children[1:]],
                                 [child for child, _ in children], branch=True, fan=fan))
            following.append((node_id, children[0][1]))
        layer = following
        height += 1
    return blocks, generations, layer[0][0], height


def _population(binary: Path) -> None:
    # Build bytes directly from independently chosen maps, never via the C codec.
    for fan in (2, 3, 4, 16):
        for count in (0, 1, fan, fan + 1, fan * fan + 1):
            keys = [3 * index for index in range(count)]
            if keys:
                keys[-1] = MAXIMUM
            for domain in (1, 2):
                expected = {key: (domain * 1009 + index) & MAXIMUM for index, key in enumerate(keys)}
                if keys:
                    expected[keys[0]] = 0 if domain == 1 else MAXIMUM
                blocks, generations, root, height = _tree(keys, expected, fan)
                queries = sorted({0, 1, 2, MAXIMUM - 1, MAXIMUM, *keys,
                                  *(key + 1 for key in keys if key < MAXIMUM)})
                for query in queries:
                    _answer(_read(binary, blocks, generations, root, query, fan=fan,
                                  height=height, visits=len(blocks)), expected.get(query))
                _refused(_read(binary, blocks, generations, root, 0, fan=fan,
                               height=height, visits=max(0, len(blocks) - 1)))
    # Old and successor roots coexist, retaining old generation nodes and values.
    blocks, generations = _demo()
    blocks += [_block(3, 4, [1, 2], [99, 20]),
               _block(4, 4, [5], [3, 1], branch=True)]
    generations += [4, 4]
    _answer(_read(binary, blocks, generations, 2, 1), 10)
    _answer(_read(binary, blocks, generations, 4, 1), 99)
    _answer(_read(binary, blocks, generations, 4, 5), 50)
    # Shared empty children are admitted by the reference, which has no unique-parent rule.
    shared = [_block(0, 1, [], []), _block(1, 2, [5], [0, 0], branch=True)]
    _answer(_read(binary, shared, [1, 2], 1, 5, visits=3), None)
    _refused(_read(binary, shared, [1, 2], 1, 5, visits=2))
    # Unreachable bytes are not part of a root's tree predicate.
    _answer(_read(binary, [*shared, b"\xff" * 96], [1, 2, 0], 1, 0), None)
    # The maximum supported height remains usable by a chain of single-child branches.
    chain = [_block(0, 0, [0, MAXIMUM], [MAXIMUM, 0])]
    chain.extend(_block(node_id, node_id, [], [node_id - 1], branch=True) for node_id in range(1, 17))
    _answer(_read(binary, chain, list(range(17)), 16, 0, height=16, visits=17), MAXIMUM)
    _answer(_read(binary, chain, list(range(17)), 16, MAXIMUM, height=16, visits=17), 0)


def _refusals(binary: Path) -> None:
    blocks, generations = _demo()
    options: list[ReadOptions] = [{"height": 0}, {"height": 2}, {"depth": 0}, {"depth": 17},
                                 {"height": 17}, {"visits": 0}, {"visits": 2}, {"visits": 4097},
                                 {"fan": 1}, {"fan": 17}, {"block_bytes": 0}, {"block_bytes": 95}]
    for arguments in options:
        _refused(_read(binary, blocks, generations, 2, 1, **arguments))
    _refused(_read(binary, blocks, generations, 3, 1))
    for data in (b"".join(blocks)[:-1], b"".join(blocks) + b"\0"):
        _refused(_read(binary, blocks, generations, 2, 1, data=data))
    bad_nodes = [
        (0, _block(0, 0, [2, 1], [20, 10])),
        (0, _block(0, 0, [1, 1], [10, 11])),
        (0, _block(0, 0, [1, 5], [10, 50])),
        (1, _block(1, 1, [4, 7], [40, 70])),
        (1, _block(1, 1, [7, 5], [70, 50])),
        (1, _block(1, 9, [5, 7], [50, 70])),
        (1, _block(0, 1, [5, 7], [50, 70])),
        (1, blocks[1][:-1] + b"\x01"),
        (2, _block(2, 2, [5], [0, 3], branch=True)),
        (2, _block(2, 2, [5], [0, 2], branch=True)),
    ]
    for node_id, changed in bad_nodes:
        candidate = blocks.copy()
        candidate[node_id] = changed
        for query in (1, 5, 4):
            _refused(_read(binary, candidate, generations, 2, query))
    duplicate_separator = [blocks[0], blocks[1], _block(2, 2, [], []),
                           _block(3, 3, [5, 5], [0, 2, 1], branch=True)]
    _refused(_read(binary, duplicate_separator, [0, 1, 2, 3], 3, 1))
    skew = [*blocks, _block(3, 3, [21, 22], [210, 220]),
            _block(4, 4, [21], [2, 3], branch=True)]
    _refused(_read(binary, skew, list(range(5)), 4, 1, height=2))
    cycle = [_block(0, 0, [], [0], branch=True)]
    _refused(_read(binary, cycle, [0], 0, 0, height=16))
    _refused(_read(binary, [_block(0, 0, [], [])], [0], 0, 0, height=1))


def _native_campaign() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as temporary:
        binary = _build(Path(temporary))
        _population(binary)
        _refusals(binary)


def _compiled_controls() -> None:
    source = (ROOT / "storage" / "src" / "tree_image.c").read_text(encoding="utf-8")
    blocks, generations = _demo()
    reversed_right = blocks.copy()
    reversed_right[1] = _block(1, 1, [7, 5], [70, 50])
    duplicate_left = blocks.copy()
    duplicate_left[0] = _block(0, 0, [1, 1], [10, 11])
    upper_key = blocks.copy()
    upper_key[0] = _block(0, 0, [1, 5], [10, 50])
    duplicate_separator = [blocks[0], blocks[1], _block(2, 2, [], []),
                           _block(3, 3, [5, 5], [0, 2, 1], branch=True)]
    # Each tuple names a compiled defect and a witness it specifically spoils.
    mutants: list[tuple[str, str, str, list[bytes], list[int], int, int, ReadOptions, int | None]] = [
        ("separator-equality-route", "node.keys[route] <= walk->key", "node.keys[route] < walk->key",
         blocks, generations, 2, 5, {}, 50),
        ("duplicate-leaf-key", "node.keys[i - 1u] >= node.keys[i]", "node.keys[i - 1u] > node.keys[i]",
         duplicate_left, generations, 2, 1, {}, None),
        ("exclusive-upper-bound", "key < range.upper", "key <= range.upper",
         upper_key, generations, 2, 1, {}, None),
        ("strict-separator", "within(separators, node.keys[i], 1)", "within(separators, node.keys[i], 0)",
         duplicate_separator, [0, 1, 2, 3], 3, 1, {}, None),
        ("off-route-admission", "if (!walk_node(walk,", "if ((selected && i == route) && !walk_node(walk,",
         reversed_right, generations, 2, 1, {}, None),
        ("exact-leaf-depth", "if (height != 0u)", "if (height > 1u)",
         [_block(0, 0, [1], [10])], [0], 0, 1, {"height": 1}, None),
        ("visit-consumption", "--walk->remaining;", "(void)walk->remaining;",
         blocks, generations, 2, 1, {"visits": 2}, None),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-tree-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="controls-", dir=work) as temporary:
        directory = Path(temporary)
        pristine = _build(directory / "pristine")
        for name, needle, replacement, nodes, versions, root, key, arguments, expected in mutants:
            ensure(source.count(needle) == 1, f"ambiguous mutation site: {name}")
            result = _read(pristine, nodes, versions, root, key, **arguments)
            if expected is None:
                _refused(result)
            else:
                _answer(result, expected)
            binary = _build(directory / name, source=source.replace(needle, replacement))
            bad = _read(binary, nodes, versions, root, key, **arguments)
            ensure(bad.returncode == 0, f"{name} mutant did not execute its accepted defect")
            if expected is not None:
                ensure(json.loads(bad.stdout)["found"] is False,
                       f"{name} mutant did not spoil the specific map witness")


def _independent_boundaries() -> None:
    left = _block(0, 0, [0, MAXIMUM], [MAXIMUM, 0])
    ensure(struct.unpack("<QQQQ", left[32:64]) == (0, MAXIMUM, MAXIMUM, 0),
           "independent full-width key/value byte witness changed")
    nodes, versions = _demo()
    ensure(versions == [0, 1, 2] and struct.unpack("<QQQ", nodes[2][32:56]) == (5, 0, 1),
           "independent root routing witness changed")


def cases() -> list[Case]:
    return [Case("independent tree byte and routing boundaries", _independent_boundaries),
            Case("compiled tree/map population, retained roots and refusals", _native_campaign, lane="guest"),
            Case("compiled tree admission and routing defect controls", _compiled_controls, lane="guest")]
