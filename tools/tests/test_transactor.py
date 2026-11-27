# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracles and native C17 controls for `ObjectTransactor.v` and `transactor/`."""

import hashlib
import hmac
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tests.harness import Case, ensure
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
TRANSACTOR_DIR = ROOT / "transactor"
TRANSACTOR_H = TRANSACTOR_DIR / "include" / "vos_transactor.h"
TRANSACTOR_C = TRANSACTOR_DIR / "src" / "transactor.c"
TRANSACTOR_TEST_C = TRANSACTOR_DIR / "test" / "test_transactor.c"
TRANSACTOR_README = TRANSACTOR_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "ObjectTransactor.v"


@dataclass(frozen=True)
class _JournalRec:
    txn: int
    block: int
    value: int
    closes: bool
    intact: bool


@dataclass
class _TrieNode:
    marked: bool = False
    zero: _TrieNode | None = None
    one: _TrieNode | None = None


def _txn_id_bits(txn: int) -> list[int]:
    """Encode `txn` as `JournalIndex.txn_id_of_nat`: binary path for `txn + 1`, LSB first, 1-terminated."""
    n = txn + 1
    bits: list[int] = []
    while n > 1:
        bits.append(n & 1)
        n >>= 1
    return bits


def _trie_mark(root: _TrieNode | None, bits: list[int]) -> _TrieNode:
    node = root if root is not None else _TrieNode()
    curr = node
    for bit in bits:
        if bit == 0:
            if curr.zero is None:
                curr.zero = _TrieNode()
            curr = curr.zero
        else:
            if curr.one is None:
                curr.one = _TrieNode()
            curr = curr.one
    curr.marked = True
    return node


def _trie_member(root: _TrieNode | None, bits: list[int]) -> bool:
    curr = root
    for bit in bits:
        if curr is None:
            return False
        curr = curr.zero if bit == 0 else curr.one
    return curr is not None and curr.marked


def _trie_depth_and_nodes(node: _TrieNode | None) -> tuple[int, int]:
    if node is None:
        return 0, 0
    dz, nz = _trie_depth_and_nodes(node.zero)
    do, no = _trie_depth_and_nodes(node.one)
    return 1 + max(dz, do), 1 + nz + no


def _scan(journal: list[_JournalRec]) -> list[_JournalRec]:
    out: list[_JournalRec] = []
    for rec in journal:
        if not rec.intact:
            break
        out.append(rec)
    return out


def _sieve(journal: list[_JournalRec]) -> list[_JournalRec]:
    return [rec for rec in journal if rec.intact]


def _commits_linear(prefix: list[_JournalRec], txn: int) -> bool:
    return any(rec.txn == txn and rec.closes for rec in prefix)


def _apply_all(prefix: list[_JournalRec], is_committed: dict[int, bool], base: dict[int, int]) -> dict[int, int]:
    store = dict(base)
    for rec in prefix:
        if is_committed.get(rec.txn, False):
            store[rec.block] = rec.value
    return store


def _canonical_obj_hash(payload: bytes, kids: list[bytes]) -> bytes:
    buf = bytearray(b"VOSTXOB1")
    buf += len(payload).to_bytes(4, "little")
    buf += len(kids).to_bytes(4, "little")
    buf += payload
    for kid in kids:
        buf += kid
    return hashlib.sha256(bytes(buf)).digest()


def _sign_root_bytes(hmac_key: bytes, root_hash: bytes, version: int,
                     declared_floor: int, key_id: int) -> tuple[bytes, bytes]:
    enc = (
        b"VOSTXRT1"
        + root_hash
        + version.to_bytes(8, "little")
        + declared_floor.to_bytes(8, "little")
        + key_id.to_bytes(8, "little")
    )
    checksum = hashlib.sha256(enc).digest()
    sig = hmac.new(hmac_key, enc, hashlib.sha256).digest()
    return sig, checksum


def _path_read_oracle(store: dict[bytes, tuple[bytes, list[bytes]]],
                      attested_root: bytes,
                      target: bytes,
                      witness: list[bytes],
                      walk_depth: int) -> bytes | None:
    if len(witness) > walk_depth:
        return None
    visited: set[bytes] = set()
    curr = attested_root
    for step in range(len(witness) + 1):
        if curr in visited:
            return None
        visited.add(curr)
        entry = store.get(curr)
        if entry is None:
            return None
        payload, kids = entry
        if _canonical_obj_hash(payload, kids) != curr:
            return None
        if step == len(witness):
            return payload if curr == target else None
        nxt = witness[step]
        if nxt not in kids:
            return None
        curr = nxt
    return None


def _binary_id_trie_oracle() -> None:
    """Verify binary-ID radix-2 trie equality with `commits`, `apply_all`, and bit-depth space bounds."""
    journal = [
        _JournalRec(txn=1, block=0, value=11, closes=False, intact=True),
        _JournalRec(txn=1, block=1, value=12, closes=True, intact=True),
        _JournalRec(txn=2, block=2, value=21, closes=True, intact=True),
        _JournalRec(txn=2, block=3, value=22, closes=True, intact=True),
        _JournalRec(txn=3, block=4, value=31, closes=False, intact=True),
        _JournalRec(txn=3, block=5, value=32, closes=False, intact=True),
        _JournalRec(txn=1023, block=6, value=99, closes=True, intact=True),
        _JournalRec(txn=100000, block=7, value=77, closes=True, intact=True),
    ]
    probe_ids = [0, 1, 2, 3, 4, 1023, 2048, 99999, 100000, 100001]
    base_store = {b: b * 10 for b in range(8)}

    # Check sparse bit-depth space bound: ID 100000 takes <= 17 nodes, never 100001 slots.
    sparse_trie = _trie_mark(None, _txn_id_bits(100000))
    depth, nodes = _trie_depth_and_nodes(sparse_trie)
    bit_len = len(_txn_id_bits(100000)) + 1
    ensure(depth == bit_len and nodes == bit_len and nodes < 32,
           f"sparse ID bit-depth space bound failed: depth={depth}, nodes={nodes}")

    # Check every crash prefix (`cuts`) and every torn record position (`tear_at`) under both arms.
    variants = [journal[:k] for k in range(len(journal) + 1)]
    for k in range(len(journal)):
        torn = [
            _JournalRec(r.txn, r.block, r.value, r.closes, intact=(idx != k))
            for idx, r in enumerate(journal)
        ]
        variants.append(torn)

    for variant in variants:
        for discipline in (_scan, _sieve):
            prefix = discipline(variant)
            trie: _TrieNode | None = None
            max_bits = 0
            sum_bits = 0
            for rec in prefix:
                if rec.closes:
                    bits = _txn_id_bits(rec.txn)
                    trie = _trie_mark(trie, bits)
                    max_bits = max(max_bits, len(bits) + 1)
                    sum_bits += len(bits) + 1
            d_actual, n_actual = _trie_depth_and_nodes(trie)
            ensure(d_actual <= max_bits and n_actual <= sum_bits,
                   f"trie depth/space bound violated: {(d_actual, max_bits, n_actual, sum_bits)}")

            trie_decisions: dict[int, bool] = {}
            linear_decisions: dict[int, bool] = {}
            for tid in probe_ids:
                t_ok = _trie_member(trie, _txn_id_bits(tid))
                l_ok = _commits_linear(prefix, tid)
                ensure(t_ok == l_ok, f"lookup mismatch for txn={tid}: trie={t_ok}, linear={l_ok}")
                trie_decisions[tid] = t_ok
                linear_decisions[tid] = l_ok

            ensure(
                _apply_all(prefix, trie_decisions, base_store)
                == _apply_all(prefix, linear_decisions, base_store),
                "apply_all store mismatch between trie and linear commits",
            )


def _path_reader_and_ab_oracle() -> None:
    """Verify canonical hashing, path-local reader independence, and signed-root encodings."""
    leaf_a = b"leaf-alpha"
    leaf_b = b"leaf-beta"
    stray = b"stray-leaf"
    h_a = _canonical_obj_hash(leaf_a, [])
    h_b = _canonical_obj_hash(leaf_b, [])
    h_stray = _canonical_obj_hash(stray, [])
    mid_payload = b"mid-node"
    h_mid = _canonical_obj_hash(mid_payload, [h_a, h_b])
    root_payload = b"root-node"
    h_root = _canonical_obj_hash(root_payload, [h_mid])

    store: dict[bytes, tuple[bytes, list[bytes]]] = {
        h_a: (leaf_a, []),
        h_b: (leaf_b, []),
        h_stray: (stray, []),
        h_mid: (mid_payload, [h_a, h_b]),
        h_root: (root_payload, [h_mid]),
    }

    ensure(_path_read_oracle(store, h_root, h_root, [], 2) == root_payload, "root read")
    ensure(_path_read_oracle(store, h_root, h_a, [h_mid, h_a], 2) == leaf_a, "leaf_a read")

    # Unavailable sibling does not affect valid sibling read
    no_sib = {k: v for k, v in store.items() if k != h_b}
    ensure(_path_read_oracle(no_sib, h_root, h_a, [h_mid, h_a], 2) == leaf_a,
           "unavailable sibling should not block valid path")

    # Refusals: unauthenticated parent, bad link, wrong target, hash mismatch, exhausted depth
    bad_parent = dict(store)
    bad_parent[h_mid] = (b"Xid-node", [h_a, h_b])
    ensure(_path_read_oracle(bad_parent, h_root, h_a, [h_mid, h_a], 2) is None,
           "unauthenticated parent must refuse")
    ensure(_path_read_oracle(store, h_root, h_stray, [h_mid, h_stray], 2) is None,
           "unlinked stray object must refuse")
    ensure(_path_read_oracle(store, h_root, h_b, [h_mid, h_a], 2) is None,
           "wrong final target must refuse")
    bad_leaf = dict(store)
    bad_leaf[h_a] = (b"Z", [])
    ensure(_path_read_oracle(bad_leaf, h_root, h_a, [h_mid, h_a], 2) is None,
           "leaf hash mismatch must refuse")
    ensure(_path_read_oracle(store, h_root, h_a, [h_mid, h_a], 1) is None,
           "exhausted walk depth must refuse")

    # Root signing vector sanity
    hmac_key = bytes(range(0xA0, 0xC0))
    sig, csum = _sign_root_bytes(hmac_key, h_root, 5, 4, 3)
    ensure(len(sig) == 32 and len(csum) == 32 and sig != csum, "signed root MAC/checksum distinct")


def _surface_and_proof_contract() -> None:
    """Verify deliverable surfaces, SPDX headers, heap-free C, and Rocq theorem names."""
    for path in (TRANSACTOR_H, TRANSACTOR_C, TRANSACTOR_TEST_C, TRANSACTOR_README, PROOFS_V):
        ensure(path.is_file(), f"missing transactor artifact: {path}")

    for c_path in (TRANSACTOR_H, TRANSACTOR_C, TRANSACTOR_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        ensure(text.splitlines()[0] == "// SPDX-License-Identifier: Apache-2.0",
               f"missing // SPDX header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden dynamic allocation {forbidden} in {c_path}")

    c_src = TRANSACTOR_C.read_text(encoding="utf-8")
    for fn in (
        "vos_tx_path_read",
        "vos_tx_select_root",
        "vos_tx_stage",
        "vos_tx_verify_and_flip",
        "vos_tx_health_check",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    ensure(v_src.splitlines()[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
           "missing Rocq SPDX header in ObjectTransactor.v")
    for sym in (
        "TxIndex",
        "tx_index_lookup_eq_commits",
        "tx_index_apply_all_eq",
        "tx_index_depth_bounded",
        "tx_index_space_bounded",
        "path_read_authenticates_visited_chain",
        "path_read_returns_exact_bytes",
        "path_read_ignores_unavailable_sibling_subtree",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in ObjectTransactor.v")
    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in ObjectTransactor.v",
        )


def _select_sanitizer_compiler(tmp_path: Path) -> tuple[str, list[str]]:
    """Select a C17 compiler supporting ASan/UBSan on Linux, checking clang as well."""
    cflags = ["-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes"]
    san_flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]

    # Probe compilers in preference order (`clang` first, then `cc`/`gcc`) for ASan/UBSan runtime support.
    probe_src = tmp_path / "probe.c"
    probe_src.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    probe_bin = tmp_path / "probe"

    for name in ("clang", "cc", "gcc"):
        compiler = shutil.which(name)
        if compiler is None:
            continue
        res = subprocess.run(
            [compiler, *cflags, *san_flags, str(probe_src), "-o", str(probe_bin)],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if res.returncode == 0:
            return compiler, [*cflags, *san_flags]

    raise AssertionError("no C17 compiler with ASan/UBSan runtime available in Linux guest")


def _native_c_and_mutation_controls() -> None:
    """Compile and run `transactor` tests with ASan/UBSan + Clang and kill all 6 behavioral mutants."""
    if sys.platform == "win32":
        return

    with tempfile.TemporaryDirectory(prefix="vos-transactor-c-") as td:
        tmp = Path(td)
        compiler, flags = _select_sanitizer_compiler(tmp)
        binary = tmp / "test_transactor"
        cmd = [
            compiler,
            *flags,
            f"-I{TRANSACTOR_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(TRANSACTOR_C),
            str(CRYPTO_SOURCE),
            str(TRANSACTOR_TEST_C),
            "-o",
            str(binary),
        ]
        built = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
        ensure(built.returncode == 0, f"transactor C build failed: {built.stderr}")
        ran = subprocess.run([str(binary)], capture_output=True, text=True, check=False, timeout=60)
        ensure(ran.returncode == 0 and "transactor_test: ok" in ran.stdout,
               f"transactor C test failed: {ran.stderr or ran.stdout}")

        # Also verify clean strict C17 compilation with Clang when available.
        clang = shutil.which("clang")
        if clang is not None and Path(clang).name != Path(compiler).name:
            clang_bin = tmp / "test_transactor_clang"
            clang_built = subprocess.run(
                [
                    clang, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes",
                    f"-I{TRANSACTOR_H.parent}", f"-I{CRYPTO_INCLUDE}",
                    str(TRANSACTOR_C), str(CRYPTO_SOURCE), str(TRANSACTOR_TEST_C),
                    "-o", str(clang_bin),
                ],
                capture_output=True, text=True, check=False, timeout=60,
            )
            ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
            clang_ran = subprocess.run([str(clang_bin)], capture_output=True, text=True, check=False, timeout=60)
            ensure(clang_ran.returncode == 0 and "transactor_test: ok" in clang_ran.stdout,
                   f"clang binary failed: {clang_ran.stderr or clang_ran.stdout}")

        source = TRANSACTOR_C.read_text(encoding="utf-8")
        mutants: list[tuple[str, str, str]] = [
            (
                "drop-hash-check",
                "        if (!equal_hashes(&computed, &curr)) {\n"
                "            return VOS_TX_ERR_HASH_MISMATCH;\n"
                "        }",
                "        if (0 && !equal_hashes(&computed, &curr)) {\n"
                "            return VOS_TX_ERR_HASH_MISMATCH;\n"
                "        }",
            ),
            (
                "follow-untrusted-slot-ptr",
                "    (void)untrusted_slot_ptr;",
                "    if (policy != NULL && copies != NULL && out_selected != NULL &&\n"
                "        untrusted_slot_ptr < copy_count &&\n"
                "        vos_tx_verify_root(policy, &copies[untrusted_slot_ptr])) {\n"
                "        *out_selected = copies[untrusted_slot_ptr];\n"
                "        return VOS_TX_OK;\n"
                "    }",
            ),
            (
                "fallback-below-floor",
                "    if (spare->version < rot_floor ||\n"
                "        spare->version < ab->floor_version ||\n"
                "        spare->version < spare->declared_floor) {\n"
                "        return VOS_TX_ERR_ROLLBACK_FLOOR;\n"
                "    }",
                "    if (0 && (spare->version < rot_floor ||\n"
                "        spare->version < ab->floor_version ||\n"
                "        spare->version < spare->declared_floor)) {\n"
                "        return VOS_TX_ERR_ROLLBACK_FLOOR;\n"
                "    }",
            ),
            (
                "write-floor-during-flip",
                "    ab->pinned_checkpoint = evidence->offered_checkpoint;",
                "    ab->pinned_checkpoint = evidence->offered_checkpoint;\n"
                "    ab->floor_version = spare->declared_floor;",
            ),
            (
                "mutate-running-slot-during-stage",
                "    if (ab->b_live != 0u) {\n"
                "        ab->slot_a = *candidate;\n"
                "    } else {\n"
                "        ab->slot_b = *candidate;\n"
                "    }",
                "    if (ab->b_live != 0u) {\n"
                "        ab->slot_b = *candidate;\n"
                "    } else {\n"
                "        ab->slot_a = *candidate;\n"
                "    }",
            ),
            (
                "accept-truncated-walk",
                "            if (depth == walk_depth) {\n"
                "                if (entry->obj.kid_count != 0u) {\n"
                "                    return VOS_TX_ERR_INCOMPLETE_DAG;\n"
                "                }\n"
                "            } else {",
                "            if (depth == walk_depth) {\n"
                "                (void)entry;\n"
                "            } else {",
            ),
        ]

        for label, target, replacement in mutants:
            ensure(source.count(target) == 1, f"mutant target missing or non-unique: {label}")
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(source.replace(target, replacement, 1), encoding="utf-8")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = subprocess.run(
                [
                    compiler, *flags,
                    f"-I{TRANSACTOR_H.parent}", f"-I{CRYPTO_INCLUDE}",
                    str(mutant_c), str(CRYPTO_SOURCE), str(TRANSACTOR_TEST_C),
                    "-o", str(mutant_bin),
                ],
                capture_output=True, text=True, check=False, timeout=60,
            )
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run([str(mutant_bin)], capture_output=True, text=True, check=False, timeout=60)
            ensure(m_ran.returncode != 0, f"mutant survived: {label}")


def cases() -> list[Case]:
    return [
        Case("transactor_binary_id_trie_oracle", _binary_id_trie_oracle, lane="any"),
        Case("transactor_path_reader_and_ab_oracle", _path_reader_and_ab_oracle, lane="any"),
        Case("transactor_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("transactor_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
