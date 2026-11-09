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
from vos import env, proof_staging, toolenv

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
    command = [compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
               "-Wstrict-prototypes", "-Werror", "-pedantic",
               "-I", str(ROOT / "storage" / "include"), str(updater),
               *(str(ROOT / "storage" / "src" / name) for name in ("node_image.c", "tree_image.c")),
               str(ROOT / "storage" / "host" / "tree_update.c"), "-o", str(binary)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    ensure(result.returncode == 0, f"compile failure is not a mutation kill: {result.stderr}")
    return binary


def _invoke(binary: Path, arena: Arena, key: int, value: int, *, generation: int = 1,
            depth: int = 16, visits: int = 4096,
            untouched: bool = False,
            mode: str | None = None,
            batch: list[tuple[int, int]] | None = None) -> subprocess.CompletedProcess[bytes]:
    prefix = [f"--{mode}"] if mode is not None else []
    if mode in ("batch", "batch-path"):
        if batch is None:
            raise AssertionError("batch mode requires batch entries")
        flat = [word for pair in batch for word in pair]
        arguments = [arena.fan, len(arena.generations), 32 + 16 * arena.fan, arena.used,
                     arena.root, arena.height, depth, visits, generation, len(batch),
                     int(untouched), *flat, *arena.generations]
    else:
        arguments = [arena.fan, len(arena.generations), 32 + 16 * arena.fan, arena.used,
                     arena.root, arena.height, depth, visits, generation, key, value,
                     int(untouched), *arena.generations]
    return subprocess.run([str(binary), *prefix, *(str(part) for part in arguments)],
                          input=arena.blocks, capture_output=True, timeout=10, check=False)


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


def _tree_signature(arena: Arena) -> list[tuple[int, int, int, bytes]]:
    """Extract canonical node payloads in DFS order with relative child indices."""
    size = 32 + 16 * arena.fan
    order: dict[int, int] = {}
    nodes: list[tuple[int, int, int, bytes]] = []

    def walk(node_id: int, level: int) -> int:
        if node_id not in order:
            order[node_id] = len(order)
            block = arena.blocks[node_id * size:(node_id + 1) * size]
            kind, count, _, _ = struct.unpack("<IIQQ", block[8:32])
            if kind == 0:
                payload = block[32:32 + 16 * count]
            else:
                words = list(struct.unpack("<" + "Q" * (2 * count - 1),
                                           block[32:32 + 8 * (2 * count - 1)]))
                seps = words[:count - 1]
                children = [walk(c, level - 1) for c in words[count - 1:]]
                payload = struct.pack("<" + "Q" * (2 * count - 1), *seps, *children)
            nodes.append((level, kind, count, payload))
        return order[node_id]

    walk(arena.root, arena.height)
    return nodes


def _batch_delete_and_compact(binary: Path) -> None:
    for fan in (2, 3, 4, 16):
        count = min(48, 2 * fan * fan + 2)
        keys = [5 * i + 1 for i in range(count)]
        expected = {k: k * 17 for k in keys}
        # Compare single-pass sorted batch against sequential single-key insertions.
        seq_arena = _empty(fan)
        for k in keys[:2 * fan]:
            seq_arena = _accepted(_invoke(binary, seq_arena, k, expected[k], generation=1),
                                  seq_arena, 1)
        batch_entries = [(k, expected[k]) for k in keys[:2 * fan]]
        batch_arena = _accepted(
            _invoke(binary, _empty(fan), 0, 0, generation=1, mode="batch", batch=batch_entries),
            _empty(fan), 1)
        ensure(_map(batch_arena) == _map(seq_arena),
               "sorted-batch CoW update disagrees with sequential insertions")
        ensure(batch_arena.used < seq_arena.used,
               "sorted-batch CoW update must allocate fewer nodes than sequential single-key path copies")
        # Exercise multi-batch growth, replacements, and Rodeh lazy deletion.
        rest = [(k, expected[k]) for k in keys[2 * fan:]]
        grown = _accepted(
            _invoke(binary, batch_arena, 0, 0, generation=2, mode="batch", batch=rest),
            batch_arena, 2)
        ensure(_map(grown) == expected and _map(grown, batch_arena.root, batch_arena.height) == dict(batch_entries),
               "multi-batch update must preserve retained root")
        # Build a second tree with the same final map via reverse insertions + lazy deletions.
        alt = _empty(fan)
        extra_keys = [5 * i + 3 for i in range(fan + 2)]
        for step, k in enumerate(reversed(keys + extra_keys), start=1):
            alt = _accepted(_invoke(binary, alt, k, expected.get(k, 999), generation=step), alt, step)
        for step, k in enumerate(extra_keys, start=200):
            before_del = _map(alt)
            before_root, before_height = alt.root, alt.height
            alt = _accepted(_invoke(binary, alt, k, 0, generation=step, mode="delete"), alt, step)
            del before_del[k]
            ensure(_map(alt) == before_del, "lazy CoW delete disagrees with expected map")
            ensure(_map(alt, before_root, before_height)[k] == 999,
                   "lazy CoW delete mutated retained snapshot root")
        ensure(_map(alt) == expected, "divergent histories must reach identical logical map")
        # Compact both trees and verify strict history-independent canonical layout!
        comp1 = _accepted(_invoke(binary, grown, 1, 5, generation=500, mode="compact"), grown, 500)
        comp2 = _accepted(_invoke(binary, alt, 1, 500, generation=500, mode="compact"), alt, 500)
        ensure(_map(comp1) == expected and _map(comp2) == expected,
               "compaction must preserve exact logical map")
        ensure(comp1.height == comp2.height and _tree_signature(comp1) == _tree_signature(comp2),
               "compacted B+ trees must be strictly history-independent (canonical)")
        # Verify O(1) birth-generation snapshot reclamation flag and deadlist classifier.
        hdr_split = json.loads(_invoke(binary, grown, 1, 1, generation=500, mode="compact").stdout.split(b"\n", 1)[0])
        hdr1 = json.loads(_invoke(binary, grown, 1, 499, generation=500, mode="compact").stdout.split(b"\n", 1)[0])
        hdr2 = json.loads(_invoke(binary, grown, 1, 500, generation=500, mode="compact").stdout.split(b"\n", 1)[0])
        ensure(hdr1["reclaimable"] is True and hdr2["reclaimable"] is False,
               "birth-generation deadlist check must distinguish gen > snap from gen <= snap")
        ensure(bool(hdr_split["reclaimed"]) and bool(hdr_split["deadlist"]) and
               set(hdr_split["reclaimed"]).isdisjoint(hdr_split["deadlist"]) and
               all(grown.generations[n] > 1 for n in hdr_split["reclaimed"]) and
               all(grown.generations[n] <= 1 for n in hdr_split["deadlist"]),
               "vos_tree_classify_reclaim must partition unlinked nodes into reclaimed (gen > snap) and deadlist (gen <= snap)")
        # Exercise O(log_B N) path-local CoW updates under tight visit_limit = height + 2.
        path_visits = grown.height + 2
        ensure(_invoke(binary, grown, keys[0], 777, generation=3, visits=path_visits).returncode == 2,
               "whole-tree insert must refuse when visit_limit is smaller than total tree nodes")
        path_ins = _accepted(_invoke(binary, grown, keys[0], 777, generation=3,
                                     visits=path_visits, mode="insert-path"), grown, 3)
        ensure(_map(path_ins)[keys[0]] == 777, "insert-path must update target key in O(height) visits")
        path_batch = _accepted(
            _invoke(binary, grown, 0, 0, generation=3, visits=path_visits,
                    mode="batch-path", batch=[(keys[0], 888)]), grown, 3)
        ensure(_map(path_batch)[keys[0]] == 888, "batch-path must update batch keys in O(height) visits")
        path_del = _accepted(_invoke(binary, grown, keys[0], 0, generation=3,
                                     visits=path_visits, mode="delete-path"), grown, 3)
        ensure(keys[0] not in _map(path_del), "delete-path must remove target key in O(height) visits")
        # Delete all remaining keys down to an empty tree at height 0.
        cur = comp1
        remaining = expected.copy()
        for idx, k in enumerate(keys, start=600):
            cur = _accepted(_invoke(binary, cur, k, 0, generation=idx, mode="delete"), cur, idx)
            del remaining[k]
            ensure(_map(cur) == remaining, "lazy delete down to empty must preserve remaining keys")
        ensure(cur.height == 0 and _map(cur) == {}, "empty tree after lazy deletion must collapse to height 0")
    # Batch refusal checks: empty, duplicate, and unsorted batches must refuse cleanly.
    for bad_batch in ([], [(5, 50), (5, 60)], [(9, 90), (2, 20)]):
        res = _invoke(binary, _empty(2), 0, 0, mode="batch", batch=bad_batch, untouched=True)
        ensure(res.returncode == 2 and not res.stdout,
               "malformed batch must refuse without mutating arena")


def _native_campaign() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-update-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as temporary:
        binary = _build(Path(temporary))
        _population(binary)
        _refusals(binary)
        _batch_delete_and_compact(binary)


def _compiled_controls() -> None:
    source = (ROOT / "storage" / "src" / "tree_update.c").read_text(encoding="utf-8")
    full = Arena(2, _leaf(2, [1, 5], [10, 50]) + b"\0" * (64 * 7), [0] * 8)
    mutants = [
        ("replacement-value", "values[route] = update->value;", "values[route] = 0u;", _empty(2), 9, 90),
        ("copy-on-write-prefix", "const uint64_t next_id = reused ? update->reuse->ids[update->reused] : update->next;", "const uint64_t next_id = 0u;", _empty(2), 9, 90),
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
        # Additional compiled controls for lazy deletion, sorted-batch order, path-local pruning, and deadlist classification.
        del_target = "if (node.keys[i] == update->key)"
        ensure(source.count(del_target) == 1, "ambiguous delete mutation site")
        del_mutant = _build(directory / "delete-skip", source.replace(del_target, "if (0)"))
        seeded = _accepted(_invoke(pristine, _empty(2), 9, 90), _empty(2), 1)
        ensure(_invoke(del_mutant, seeded, 9, 0, generation=2, mode="delete").returncode in (2, 4),
               "compiled delete defect escaped candidate lookup check")
        batch_target = "if (entries[i - 1u].key >= entries[i].key)"
        ensure(source.count(batch_target) == 1, "ambiguous batch-order mutation site")
        batch_mutant = _build(directory / "batch-order", source.replace(batch_target, "if (0)"))
        ensure(_invoke(batch_mutant, _empty(2), 0, 0, mode="batch",
                       batch=[(9, 90), (2, 20)]).returncode in (2, 4),
               "compiled unsorted-batch defect escaped candidate admission")
        path_target = "? vos_tree_lookup_path(&update.input, limits, root, key, &checked)"
        ensure(source.count(path_target) == 1, "ambiguous insert-path mutation site")
        path_mutant = _build(
            directory / "insert-path-pruning",
            source.replace(path_target, "? vos_tree_lookup(&update.input, limits, root, key, &checked)"))
        split_tree = _accepted(_invoke(pristine, full, 9, 90), full, 1)
        ensure(_invoke(pristine, split_tree, 1, 100, generation=2,
                       visits=2, mode="insert-path").returncode == 0,
               "pristine insert-path failed under tight height + 1 visits")
        ensure(_invoke(path_mutant, split_tree, 1, 100, generation=2,
                       visits=2, mode="insert-path").returncode == 2,
               "insert-path mutant did not fail when visiting off-route sibling")
        reclaim_target = "output->deadlist_ids[output->deadlist_count] = id;\n            ++output->deadlist_count;"
        ensure(source.count(reclaim_target) == 1, "ambiguous reclaim-classify mutation site")
        reclaim_mutant = _build(
            directory / "reclaim-classify",
            source.replace(reclaim_target,
                           "output->reclaimed_ids[output->reclaimed_count] = id;\n            ++output->reclaimed_count;"))
        ensure(_invoke(reclaim_mutant, split_tree, 1, 1, generation=5, mode="compact").returncode == 4,
               "compiled deadlist classification defect escaped host witness")


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


def _nat_list(values: list[int]) -> str:
    text = "nil"
    for value in reversed(values):
        text = f"(cons {value} {text})"
    return text


def _pair_list(pairs: list[tuple[int, int]]) -> str:
    text = "nil"
    for k, v in reversed(pairs):
        text = f"(cons ({k}, {v}) {text})"
    return text


def _arena_to_gallina(arena: Arena) -> str:
    """Translate raw VOSNODE1 blocks into an ExecutableIndex.v Arena nat_keys term."""
    size = 32 + 16 * arena.fan
    nodes: list[str] = []
    for node_id in range(arena.used):
        block = arena.blocks[node_id * size:(node_id + 1) * size]
        kind, count, identity, generation = struct.unpack("<IIQQ", block[8:32])
        ensure(block[:8] == b"VOSNODE1" and identity == node_id and
               generation == arena.generations[node_id],
               "corrupt VOSNODE1 block header during Gallina translation")
        if kind == 0:
            entries = [struct.unpack("<QQ", block[32 + 16 * i:48 + 16 * i])
                       for i in range(count)]
            nodes.append(f"(leaf_of nat_keys {_pair_list(entries)})")
        else:
            ensure(kind == 1 and count > 0, "invalid branch block in Gallina translation")
            words = list(struct.unpack("<" + "Q" * (2 * count - 1),
                                       block[32:32 + 8 * (2 * count - 1)]))
            seps, children = words[:count - 1], words[count - 1:]
            nodes.append(f"(branch_of nat_keys {_nat_list(seps)} {_nat_list(children)})")
    text = "nil"
    for node in reversed(nodes):
        text = f"(cons {node} {text})"
    return text


def _gallina_comparison_source(steps: list[Arena], alt_comp: Arena) -> str:
    """Emit a Rocq source binding C VOSNODE1 outputs to ExecutableIndex.v by eq_refl."""
    ensure(len(steps) == 11, "expected 11 C update steps for Gallina comparison")
    lines = [
        "(* SPDX-License-Identifier: Apache-2.0 *)",
        "From Stdlib Require Import List.",
        "Require Import JournalIndex.",
        "Require Import ExecutableIndex.",
        "",
        "Definition cmp_geom : Geometry := {| arena_cap := 64; fan := 2; depth := 8 |}.",
        "Definition tight_geom : Geometry := {| arena_cap := 4; fan := 2; depth := 8 |}.",
        "Definition g_init : option (prod (Arena nat_keys) (prod nat nat)) :=",
        "  Some (pair (cons (leaf_of nat_keys nil) nil) (pair 0 0)).",
        "Definition g_ins (st : option (prod (Arena nat_keys) (prod nat nat))) (k : nat) (v : nat) :=",
        "  match st with",
        "  | Some (pair ar (pair r h)) => insert_gate nat_keys cmp_geom ar h None None r k v",
        "  | None => None",
        "  end.",
        "Definition g_del (st : option (prod (Arena nat_keys) (prod nat nat))) (k : nat) :=",
        "  match st with",
        "  | Some (pair ar (pair r h)) => delete_gate nat_keys cmp_geom ar h None None r k",
        "  | None => None",
        "  end.",
        "Definition g_batch (st : option (prod (Arena nat_keys) (prod nat nat))) (b : Index nat_keys) :=",
        "  match st with",
        "  | Some (pair ar (pair r h)) => insert_batch_gate nat_keys cmp_geom ar h None None r b",
        "  | None => None",
        "  end.",
        "Definition g_compact (st : option (prod (Arena nat_keys) (prod nat nat))) :=",
        "  match st with",
        "  | Some (pair ar (pair r h)) => compact_gate nat_keys cmp_geom ar h None None r",
        "  | None => None",
        "  end.",
        "Definition probe_keys : list nat :=",
        f"  {_nat_list([0, 5, 10, 12, 15, 18, 20, 25, 30, 35, 40, 99])}.",
        "",
        "Definition g_st_0 := g_ins g_init 10 100.",
        "Definition g_st_1 := g_ins g_st_0 20 200.",
        "Definition g_st_2 := g_ins g_st_1 30 300.",
        "Definition g_st_3 := g_ins g_st_2 15 150.",
        "Definition g_st_4 := g_ins g_st_3 25 250.",
        "Definition g_st_5 := g_ins g_st_4 35 350.",
        "Definition g_st_6 := g_ins g_st_5 20 202.",
        "Definition g_st_7 := g_del g_st_6 15.",
        "Definition g_st_8 := g_del g_st_7 99.",
        f"Definition g_st_9 := g_batch g_st_8 {_pair_list([(5, 50), (12, 120), (40, 400)])}.",
        "Definition g_st_10 := g_compact g_st_9.",
        "",
        "Definition g_alt_0 := g_ins (g_ins (g_ins (g_ins (g_ins (g_ins (g_ins (g_ins (g_ins g_init"
        " 40 400) 35 350) 30 300) 25 250) 20 202) 18 180) 12 120) 10 100) 5 50.",
        "Definition g_alt_del := g_del g_alt_0 18.",
        "Definition g_alt_comp := g_compact g_alt_del.",
        "",
    ]
    for idx, ar in enumerate(steps):
        lines.append(f"Definition c_ar_{idx} : Arena nat_keys := {_arena_to_gallina(ar)}.")
        lines.append(
            f"Example c_published_{idx} : "
            f"published nat_keys cmp_geom c_ar_{idx} {ar.height} None None {ar.root} = true := eq_refl.")
        lines.append(
            f"Example c_flatten_{idx} : "
            f"option_map (fun p => flatten nat_keys (fst p) (snd (snd p)) (fst (snd p))) g_st_{idx} = "
            f"Some (flatten nat_keys c_ar_{idx} {ar.height} {ar.root}) := eq_refl.")
        lines.append(
            f"Example c_reads_{idx} : "
            f"option_map (fun p => map (read_gate nat_keys cmp_geom (fst p) (snd (snd p)) (fst (snd p))) probe_keys) g_st_{idx} = "
            f"Some (map (read_gate nat_keys cmp_geom c_ar_{idx} {ar.height} {ar.root}) probe_keys) := eq_refl.")
    # Retained snapshots in step 9 preserve earlier C roots from steps 2 and 6.
    lines.append(
        f"Example c_retained_2_in_9 : "
        f"flatten nat_keys c_ar_9 {steps[2].height} {steps[2].root} = "
        f"flatten nat_keys c_ar_2 {steps[2].height} {steps[2].root} := eq_refl.")
    lines.append(
        f"Example c_retained_6_in_9 : "
        f"flatten nat_keys c_ar_9 {steps[6].height} {steps[6].root} = "
        f"flatten nat_keys c_ar_6 {steps[6].height} {steps[6].root} := eq_refl.")
    # History-independent compaction across divergent C and Gallina histories.
    lines.append(f"Definition c_ar_alt_comp : Arena nat_keys := {_arena_to_gallina(alt_comp)}.")
    lines.append(
        f"Example c_alt_comp_published : "
        f"published nat_keys cmp_geom c_ar_alt_comp {alt_comp.height} None None {alt_comp.root} = true := eq_refl.")
    lines.append(
        f"Example c_alt_comp_flatten : "
        f"flatten nat_keys c_ar_alt_comp {alt_comp.height} {alt_comp.root} = "
        f"flatten nat_keys c_ar_10 {steps[10].height} {steps[10].root} := eq_refl.")
    lines.append("Example g_comp_history_independent : g_alt_comp = g_st_10 := eq_refl.")
    # Refusal correspondence for unsorted batch and arena exhaustion.
    lines.append(
        f"Example g_refuses_unsorted_batch : "
        f"g_batch g_init {_pair_list([(9, 90), (2, 20)])} = None := eq_refl.")
    lines.append(
        "Example g_refuses_exhausted_arena : "
        "match g_st_1 with Some (pair ar (pair r h)) => insert_gate nat_keys tight_geom ar h None None r 30 300 | None => None end = None := eq_refl.")
    return "\n".join(lines) + "\n"


def _gallina_translation_unit() -> None:
    left = _leaf(2, [10], [100])
    right = (b"VOSNODE1" + struct.pack("<IIQQQQ", 0, 1, 1, 1, 20, 200)).ljust(64, b"\0")
    root = (b"VOSNODE1" + struct.pack("<IIQQQQQ", 1, 2, 2, 1, 20, 0, 1)).ljust(64, b"\0")
    sample = Arena(2, left + right + root, [0, 1, 1], used=3, root=2, height=1)
    rendered = _arena_to_gallina(sample)
    ensure("leaf_of nat_keys (cons (10, 100) nil)" in rendered and
           "branch_of nat_keys (cons 20 nil) (cons 0 (cons 1 nil))" in rendered,
           "Gallina arena translation lost leaf or branch structure")
    source = _gallina_comparison_source([sample] * 11, sample)
    ensure("Require Import ExecutableIndex." in source and
           "Example g_comp_history_independent : g_alt_comp = g_st_10 := eq_refl." in source,
           "Gallina comparison source lost ExecutableIndex.v equalities")


def _gallina_comparison() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "storage-update-tests"
    stage_dir = work / "gallina-stage"
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged = proof_staging.stage(ROOT, stage_dir, ("ExecutableIndex.v",))
    for artifact in staged.sources:
        vo = artifact.with_suffix(".vo")
        if not vo.is_file():
            done = subprocess.run([*env.rocq_command(), "-q", "-Q", str(stage_dir), "", str(artifact)],
                                  cwd=stage_dir, capture_output=True, text=True, timeout=180, check=False)
            ensure(done.returncode == 0, f"failed to compile staged {artifact.name}: {done.stderr}")
    with tempfile.TemporaryDirectory(prefix="gallina-", dir=work) as temporary:
        temp = Path(temporary)
        binary = _build(temp)
        ar = _empty(2, capacity=64)
        steps: list[Arena] = []
        for gen, (k, v) in enumerate([(10, 100), (20, 200), (30, 300), (15, 150),
                                      (25, 250), (35, 350), (20, 202)], start=1):
            ar = _accepted(_invoke(binary, ar, k, v, generation=gen), ar, gen)
            steps.append(ar)
        ar = _accepted(_invoke(binary, ar, 15, 0, generation=8, mode="delete"), ar, 8)
        steps.append(ar)
        ar = _accepted(_invoke(binary, ar, 99, 0, generation=9, mode="delete"), ar, 9)
        steps.append(ar)
        ar = _accepted(_invoke(binary, ar, 0, 0, generation=10, mode="batch",
                               batch=[(5, 50), (12, 120), (40, 400)]), ar, 10)
        steps.append(ar)
        comp1 = _accepted(_invoke(binary, ar, 1, 0, generation=11, mode="compact"), ar, 11)
        steps.append(comp1)
        # Build divergent C history and compact it.
        alt = _empty(2, capacity=64)
        for gen, (k, v) in enumerate([(40, 400), (35, 350), (30, 300), (25, 250), (20, 202),
                                      (18, 180), (12, 120), (10, 100), (5, 50)], start=20):
            alt = _accepted(_invoke(binary, alt, k, v, generation=gen), alt, gen)
        alt = _accepted(_invoke(binary, alt, 18, 0, generation=30, mode="delete"), alt, 30)
        alt_comp = _accepted(_invoke(binary, alt, 1, 0, generation=31, mode="compact"), alt, 31)
        ensure(_tree_signature(comp1) == _tree_signature(alt_comp),
               "C compacted trees from divergent histories must have identical canonical structure")
        source = _gallina_comparison_source(steps, alt_comp)
        comparison = temp / "ExecutableIndexComparison.v"
        comparison.write_text(source, encoding="utf-8", newline="")
        compiled = subprocess.run(
            [*env.rocq_command(), "-q", "-Q", str(stage_dir), "", "-Q", str(temp), "", str(comparison)],
            cwd=temp, capture_output=True, text=True, timeout=180, check=False)
        ensure(compiled.returncode == 0,
               f"locked Rocq rejected C-to-ExecutableIndex.v comparison: {compiled.stderr}")
        checked = subprocess.run(
            [*env.rocqchk_command(), "-silent", "-Q", str(stage_dir), "", "-Q", str(temp), "",
             "ExecutableIndexComparison"],
            cwd=temp, capture_output=True, text=True, timeout=180, check=False)
        ensure(checked.returncode == 0,
               f"rocqchk rejected ExecutableIndexComparison closure: {checked.stderr}")
        # Negative control: perturbing a translated C value must fail locked Rocq conversion.
        tampered = temp / "ExecutableIndexTampered.v"
        tampered.write_text(source.replace("(10, 100)", "(10, 101)", 1), encoding="utf-8", newline="")
        bad = subprocess.run(
            [*env.rocq_command(), "-q", "-Q", str(stage_dir), "", "-Q", str(temp), "", str(tampered)],
            cwd=temp, capture_output=True, text=True, timeout=180, check=False)
        ensure(bad.returncode != 0, "tampered C answer passed locked Rocq ExecutableIndex.v comparison")
    staged.validate(ROOT)


def cases() -> list[Case]:
    return [Case("independent update byte boundaries", _byte_oracle),
            Case("Gallina ExecutableIndex translation syntax", _gallina_translation_unit),
            Case("compiled insertion, replacement, split and retained-map population", _native_campaign, lane="guest"),
            Case("compiled copy-on-write and split defect controls", _compiled_controls, lane="guest"),
            Case("compiled Gallina ExecutableIndex conversion and rocqchk comparison",
                 _gallina_comparison, lane="toolchain")]
