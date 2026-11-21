# SPDX-License-Identifier: Apache-2.0
"""Check authenticated resident admission, reuse and predecessor refusal."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "storage/src/storage_publish.c"


def _variants(source: str) -> list[tuple[str, str, str]]:
    def changed(before: str, after: str) -> str:
        ensure(source.count(before) == 1, "resident receipt mutation anchor must be unique")
        return source.replace(before, after, 1)

    return [
        ("pristine", source, ""),
        ("no-admitted-pin", changed(
            "        !checkpoint_retains_snapshot(old, old->generation) ||\n", ""),
         "!vos_storage_verify_retained_resident(&unpinned"),
        ("no-admitted-mac", changed(
            "        !verify_checkpoint_mac(store->crypto, store->crypto_slot, store->domain_id,\n"
            "                               store->key_epoch, store->medium->geometry.arena_nodes, old) ||\n",
            ""),
         "!old_mac_valid"),
        ("no-current-object", changed(
            "    uint64_t current_value = 0u;\n"
            "    return vos_storage_lookup(store, receipt->identity.domain, receipt->identity.object,\n"
            "                              &current_value) == VOS_TREE_FOUND;",
            "    return 1;"),
         "!released_deleted_object"),
        ("allow-previous-system", changed(
            "if (receipt->identity.kind != VOS_RESIDENT_USER ||\n"
            "        receipt->identity.generation != old->generation ||",
            "if (receipt->identity.generation != old->generation ||"),
         "!invalid_predecessor"),
        ("allow-fresh-predecessor", changed(
            "        old->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE ||\n"
            "        current->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE ||\n"
            "        old->sealed_epoch != 0u || current->sealed_epoch != 0u ||\n"
            "        (store->crypto->epoch_sealed_mask & (1u << store->crypto_slot)) != 0u ||\n",
            ""),
         "!invalid_predecessor"),
    ]


def resident_receipt() -> None:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "resident receipt checks require a native C compiler")
    if compiler is None:
        raise RuntimeError("no native C compiler")
    work = toolenv.environment(ROOT, sys.platform).parent / "resident-receipt-tests"
    work.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / "storage/src" / f"{name}.c" for name in (
        "crypto_core", "node_image", "tree_image", "tree_update", "resident_reads"
    )]
    with tempfile.TemporaryDirectory(prefix="receipt-", dir=work) as directory:
        scratch = Path(directory)
        for name, candidate, expected in _variants(SOURCE.read_text(encoding="utf-8")):
            source = scratch / f"{name}.c"
            source.write_text(candidate, encoding="utf-8", newline="\n")
            binary = scratch / name
            compiled = subprocess.run([
                compiler, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wstrict-prototypes", "-pedantic", "-I" + str(ROOT / "storage/include"),
                *map(str, sources), str(source), str(ROOT / "storage/host/resident_receipt.c"),
                "-o", str(binary),
            ], capture_output=True, text=True, timeout=60, check=False)
            ensure(compiled.returncode == 0,
                   f"{name}: stillborn compilation is not an executed rejection: {compiled.stderr}")
            if compiled.returncode != 0:
                raise RuntimeError(f"{name} did not compile")
            result = subprocess.run([str(binary)], capture_output=True, text=True,
                                    timeout=60, check=False)
            if name == "pristine":
                ensure(result.returncode == 0, result.stderr or result.stdout)
                ensure("resident receipt: ok" in result.stdout, "resident receipt verdict missing")
            else:
                ensure(result.returncode != 0 and expected in result.stderr,
                       f"{name}: compiled control survived or missed its assertion: {result.stderr}")


def cases() -> list[Case]:
    return [Case("resident receipt authenticates admission, reuse and predecessor checks",
                 resident_receipt, lane="guest")]
