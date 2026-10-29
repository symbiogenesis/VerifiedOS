# SPDX-License-Identifier: Apache-2.0
"""Independent byte and compiled refusal controls for the bounded node codec."""

import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import toolenv

ROOT = TOOLS.parent
MAXIMUM = (1 << 64) - 1


def _image(kind: int, node_id: int, generation: int,
           keys: list[int], values: list[int], block_bytes: int) -> bytes:
    """The test's independently constructed format, never C-encoded input."""
    count = len(values)
    header = b"VOSNODE1" + struct.pack("<IIQQ", kind, count, node_id, generation)
    words = ([part for pair in zip(keys, values, strict=True) for part in pair]
             if kind == 0 else keys + values)
    payload = b"".join(struct.pack("<Q", word) for word in words)
    ensure(len(header + payload) <= block_bytes, "invalid oracle fixture")
    return (header + payload).ljust(block_bytes, b"\0")


def _oracle_boundaries() -> None:
    leaf = _image(0, 7, MAXIMUM, [0, MAXIMUM], [MAXIMUM, 1], 64)
    ensure(leaf[:8] == b"VOSNODE1" and leaf[16:24] == b"\x07" + b"\0" * 7,
           "independent header endian boundary changed")
    ensure(leaf[24:32] == b"\xff" * 8 and leaf[32:48] == b"\0" * 8 + b"\xff" * 8,
           "independent full-width payload boundary changed")
    branch = _image(1, 0, 0, [9], [0, 1], 64)
    ensure(struct.unpack("<QQQ", branch[32:56]) == (9, 0, 1) and branch[56:] == b"\0" * 8,
           "independent branch/padding boundary changed")


def _build(directory: Path, *, source: str | None = None) -> Path:
    compiler = shutil.which("clang") or shutil.which("gcc")
    ensure(compiler is not None, "native C compiler missing")
    if compiler is None:
        raise AssertionError("native C compiler missing")
    directory.mkdir(parents=True, exist_ok=True)
    codec = ROOT / "storage" / "src" / "node_image.c"
    if source is not None:
        codec = directory / "node_image.c"
        codec.write_text(source, encoding="utf-8", newline="")
    binary = directory / "node-image"
    built = subprocess.run([compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-pedantic",
                            "-I", str(ROOT / "storage" / "include"), str(codec),
                            str(ROOT / "storage" / "host" / "node_image.c"), "-o", str(binary)],
                           capture_output=True, text=True, timeout=60, check=False)
    ensure(built.returncode == 0, f"C compilation failed (not a mutation kill): {built.stderr}")
    return binary


def _encode(binary: Path, fan: int, arena: int, block_bytes: int, kind: int,
            node_id: int, generation: int, keys: list[int], values: list[int]) -> subprocess.CompletedProcess[bytes]:
    args = ["encode", fan, arena, block_bytes, kind, len(values), node_id, generation, *keys, *values]
    return subprocess.run([str(binary), *(str(arg) for arg in args)],
                          capture_output=True, timeout=5, check=False)


def _decode(binary: Path, data: bytes, *, fan: int = 4, arena: int = 19,
            block_bytes: int = 112, node_id: int = 7, generation: int = MAXIMUM
            ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([str(binary), "decode", str(fan), str(arena), str(block_bytes),
                           str(node_id), str(generation)], input=data,
                          capture_output=True, timeout=5, check=False)


def _population(binary: Path) -> None:
    for fan in (2, 4, 16):
        block_bytes = 32 + 16 * fan + 8
        for kind in (0, 1):
            for count in range(kind, fan + 1):
                for node_id, generation in ((0, 0), (18, MAXIMUM)):
                    key_count = count if kind == 0 else count - 1
                    keys = [MAXIMUM - offset for offset in range(key_count)]
                    values = ([0 if offset % 2 else MAXIMUM for offset in range(count)]
                              if kind == 0 else list(range(count)))
                    expected = _image(kind, node_id, generation, keys, values, block_bytes)
                    encoded = _encode(binary, fan, 19, block_bytes, kind, node_id, generation, keys, values)
                    ensure(encoded.returncode == 0 and encoded.stdout == expected,
                           f"independent byte oracle disagrees for {fan}/{kind}/{count}")
                    decoded = _decode(binary, expected, fan=fan, block_bytes=block_bytes,
                                      node_id=node_id, generation=generation)
                    ensure(decoded.returncode == 0, f"valid independent image refused: {decoded.stderr!r}")
                    ensure(json.loads(decoded.stdout) == {"kind": kind, "count": count, "id": node_id,
                           "generation": generation, "keys": keys + [0] * (16 - key_count),
                           "values": values + [0] * (16 - count)}, "decoded structure differs")
    # This is a structural codec: even a well-framed changed payload is not authenticated.
    original = _image(0, 7, MAXIMUM, [1], [2], 112)
    changed = bytearray(original)
    changed[40] ^= 1
    accepted = _decode(binary, bytes(changed))
    ensure(accepted.returncode == 0 and json.loads(accepted.stdout)["values"][0] == 3,
           "codec confused framing with payload authentication")


def _refusals(binary: Path) -> None:
    leaf = _image(0, 7, MAXIMUM, [3, 9], [MAXIMUM, 2], 112)
    branch = _image(1, 7, MAXIMUM, [9], [1, 18], 112)
    malformed: list[bytes] = [leaf[:-1], leaf + b"\0", _image(1, 7, MAXIMUM, [], [], 112)]
    for at, value in ((0, 0), (7, ord("2")), (8, 2), (12, 5), (12, 255), (16, 8), (24, 0), (111, 1)):
        changed = bytearray(leaf)
        changed[at] = value
        malformed.append(bytes(changed))
    changed = bytearray(branch)
    changed[48:56] = struct.pack("<Q", 19)
    malformed.append(bytes(changed))
    for data in malformed:
        refused = _decode(binary, data)
        ensure(refused.returncode == 2 and not refused.stdout,
               "malformed image was accepted, crashed or changed output before refusal")
    for change in ({"fan": 0}, {"fan": 1}, {"fan": 17}, {"arena": 0}, {"arena": 7},
                   {"block_bytes": 111}, {"node_id": 8}, {"generation": 0}):
        refused = _decode(binary, leaf, **change)
        ensure(refused.returncode == 2, "invalid composition or expected binding did not preserve output")
    for fan, arena, size, kind, node_id, keys, values in (
            (1, 19, 112, 0, 7, [1], [2]), (17, 19, 112, 0, 7, [1], [2]),
            (4, 0, 112, 0, 7, [], []), (4, 19, 95, 0, 7, [1], [2]),
            (4, 19, 112, 2, 7, [1], [2]), (4, 19, 112, 0, 19, [1], [2]),
            (4, 19, 112, 0, 7, list(range(5)), list(range(5))),
            (4, 19, 112, 1, 7, [], []), (4, 19, 112, 1, 7, [1], [0, 19])):
        refused = _encode(binary, fan, arena, size, kind, node_id, MAXIMUM, keys, values)
        ensure(refused.returncode == 2 and not refused.stdout,
               "invalid encode changed output, crashed or was accepted")


def _native_campaign() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-node-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as temporary:
        binary = _build(Path(temporary))
        _population(binary)
        _refusals(binary)


def _compiled_controls() -> None:
    source = (ROOT / "storage" / "src" / "node_image.c").read_text(encoding="utf-8")
    leaf = _image(0, 7, MAXIMUM, [3], [5], 112)
    branch = bytearray(_image(1, 7, MAXIMUM, [9], [1, 18], 112))
    branch[48:56] = struct.pack("<Q", 19)
    mutants = [
        ("magic", "bytes[i] != magic[i]", "bytes[i] != magic[i] && i != 0u", bytes([0]) + leaf[1:], {}),
        ("node-binding", "decoded.node_id != expected_id",
         "(decoded.node_id != expected_id && decoded.node_id > expected_id)", leaf, {"node_id": 8}),
        ("generation-binding", "decoded.generation != expected_generation",
         "(decoded.generation != expected_generation && decoded.generation < expected_generation)",
         leaf, {"generation": 0}),
        ("child-range", "node->values[i] >= geometry->arena_nodes", "node->values[i] > geometry->arena_nodes",
         bytes(branch), {}),
        ("padding", "bytes[padding] != 0u", "bytes[padding] > 1u", leaf[:-1] + b"\x01", {}),
    ]
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-node-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="controls-", dir=work) as temporary:
        directory = Path(temporary)
        pristine = _build(directory / "pristine")
        for name, needle, replacement, data, arguments in mutants:
            ensure(source.count(needle) == 1, f"ambiguous mutation site: {name}")
            ensure(_decode(pristine, data, **arguments).returncode == 2,
                   f"pristine did not refuse {name} control")
            binary = _build(directory / name, source=source.replace(needle, replacement))
            # A killed control must execute and demonstrate the specific bad acceptance.
            ensure(_decode(binary, data, **arguments).returncode == 0,
                   f"{name} mutant did not execute the expected accepted defect")


def cases() -> list[Case]:
    return [Case("independent format boundary oracle", _oracle_boundaries),
            Case("compiled codec byte population and refusal preservation", _native_campaign, lane="guest"),
            Case("compiled framing and identity defect controls", _compiled_controls, lane="guest")]
