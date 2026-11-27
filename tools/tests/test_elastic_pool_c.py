# SPDX-License-Identifier: Apache-2.0
"""Pure-Python oracle and native ASan/UBSan C + mutant controls for pool/."""

import shutil
import subprocess
import sys
import tempfile
from itertools import product
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import elastic_pool as ep
from vos import memplan, toolenv

STD_CLASSES: tuple[int, ...] = tuple(16 << i for i in range(13))


def _round_up_granule(req: int, granule: int) -> int:
    rem = req % granule
    return req if rem == 0 else req + (granule - rem)


def std_size_classes_and_granule_narrowing_oracle() -> None:
    """Verify the 16..65536 StdSizeClass table and exact granule narrowing without CRRL/CRAM."""
    ensure(STD_CLASSES == (16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536),
           "unexpected StdSizeClass ladder")
    for length in STD_CLASSES:
        sc = ep.SizeClass(length, length)
        ensure(sc.exact(), f"std class {length} failed exact()")
        granule = memplan.representable_granule(length)
        ensure(length % granule == 0, f"std class {length} not divisible by granule {granule}")
        samples = {1, max(1, granule - 1), granule, min(length, granule + 1), length}
        for req in samples:
            rounded = _round_up_granule(req, granule)
            ensure(req <= rounded <= length, f"narrowed {req} -> {rounded} out of bounds for {length}")
            narrowed_granule = memplan.representable_granule(rounded)
            ensure(rounded % narrowed_granule == 0 and length % narrowed_granule == 0,
                   f"narrowed {rounded} lost representable exactness")


def reference_quarantine_and_domain_oracle() -> None:
    """Check reference two-generation quarantine, exhausted-class refusal, and granule separation."""
    pool = ep.fixture()
    g0 = pool.allocate(1, 0, 0)
    g1 = pool.allocate(2, 0, 0)
    try:
        pool.allocate(3, 0, 0)
    except ep.PoolError as exc:
        ensure("exhausted" in str(exc), f"unexpected exhaustion message: {exc}")
    else:
        raise AssertionError("exhausted class 0 borrowed from class 1")
    pool.release(g0)
    pool.clear_registers(g0.slot)
    pool.barrier()
    pool.sweep_begin()
    pool.release(g1)
    pool.clear_registers(g1.slot)
    pool.barrier()
    pool.sweep_end()
    ensure(pool.slots[g1.slot].phase == "barrier", "two-gen quarantine failed")
    pool.sweep_begin()
    pool.sweep_end()
    ensure(pool.allocate(4, 0, 0).base in (g0.base, g1.base), "second sweep failed to free")


def _parse_c_trace(stdout: str) -> list[ep.Event]:
    events: list[ep.Event] = []
    for raw in stdout.splitlines():
        parts = raw.split()
        if not parts:
            continue
        kind = parts[0]
        args = tuple(int(tok) for tok in parts[1:])
        events.append((kind, args))
    return events


def _variants(source: str) -> list[tuple[str, str, str]]:
    def replaced(before: str, after: str) -> str:
        ensure(source.count(before) == 1, f"pool mutation anchor missing or non-unique: {before}")
        return source.replace(before, after, 1)

    return [
        ("pristine", source, ""),
        ("skip-zeroing",
         replaced("zero_bytes(pool->backing + offset, sc->length);",
                  "zero_bytes(pool->backing + offset, 0u);"),
         "eager zeroing missing"),
        ("borrow-larger-class",
         replaced("if (pool->plan.slots[i].cls == cls && pool->slots[i].phase == VOS_SLOT_FREE)",
                  "if (pool->plan.slots[i].cls >= cls && pool->slots[i].phase == VOS_SLOT_FREE)"),
         "exhausted class must refuse without borrowing larger class"),
        ("ignore-stale-reg",
         replaced("if (he->kind == VOS_HOLDER_REG &&",
                  "if (0 && he->kind == VOS_HOLDER_REG &&"),
         "stale register holder must block barrier"),
        ("ignore-stale-saved-ctx",
         replaced("if (he->kind == VOS_HOLDER_SAVED_CTX &&",
                  "if (0 && he->kind == VOS_HOLDER_SAVED_CTX &&"),
         "stale saved-ctx holder must block barrier"),
        ("ignore-stale-stored-cell",
         replaced("if (he->kind == VOS_HOLDER_STORED_CELL &&",
                  "if (0 && he->kind == VOS_HOLDER_STORED_CELL &&"),
         "stale stored-cell holder must block barrier"),
        ("early-reuse-active-sweep",
         replaced("if (pool->slots[i].phase == VOS_SLOT_SWEEPING && pool->slots[i].in_sweep)",
                  "if ((pool->slots[i].phase == VOS_SLOT_SWEEPING && pool->slots[i].in_sweep) || "
                  "pool->slots[i].phase == VOS_SLOT_BARRIER)"),
         "early reuse during active sweep"),
        ("skip-descendant-invalidation",
         replaced("if (vos_pool_grant_live(cur->parent, &cur->parent_grant, 0) != VOS_POOL_OK)",
                  "if (0 && vos_pool_grant_live(cur->parent, &cur->parent_grant, 0) != VOS_POOL_OK)"),
         "after parent"),
        ("shared-granule-accepted",
         replaced("if (!extents_granules_disjoint(b1, l1, b2, l2))",
                  "if (0 && !extents_granules_disjoint(b1, l1, b2, l2))"),
         "8-byte revocation granule must be refused"),
    ]


def native_pool_c_and_mutant_controls() -> None:
    """Compile pool C with clang ASan/UBSan, run differential traces, and kill all 8 mutants."""
    if sys.platform == "win32":
        return
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "native pool C tests require a C compiler")
    if compiler is None:
        return
    clang = shutil.which("clang")
    root = TOOLS.parent
    work = toolenv.environment(root, sys.platform).parent / "elastic-pool-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    pool_src = (root / "pool/src/elastic_pool.c").read_text(encoding="utf-8")
    support_sources = (
        str(root / "pool/test/test_elastic_pool.c"),
        str(root / "kernel/src/effects.c"),
        str(root / "kernel/src/context.c"),
        str(root / "supervisor/src/supervisor.c"),
        str(root / "supervisor/src/manifest.c"),
    )
    includes = ("-I", str(root / "pool/include"),
                "-I", str(root / "kernel/include"),
                "-I", str(root / "supervisor/include"))

    with tempfile.TemporaryDirectory(prefix="pool-c-", dir=work) as tmp:
        scratch = Path(tmp)
        pristine_bin = scratch / "pristine"
        for name, candidate, expected in _variants(pool_src):
            src_path = scratch / f"{name}.c"
            src_path.write_text(candidate, encoding="utf-8", newline="\n")
            exe = scratch / name
            flags = [
                compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
                "-Wstrict-prototypes", "-Werror", "-pedantic",
                "-DVOS_HOST_MODEL", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                *includes, str(src_path), *support_sources, "-o", str(exe),
            ]
            built = subprocess.run(flags, cwd=scratch, capture_output=True, text=True,
                                   check=False, timeout=60)
            ensure(built.returncode == 0,
                   f"{name}: stillborn compilation: {built.stdout}{built.stderr}")
            ran = subprocess.run([str(exe)], cwd=scratch, capture_output=True, text=True,
                                 check=False, timeout=30)
            if name == "pristine":
                ensure(ran.returncode == 0, f"pristine failed: {ran.stdout}{ran.stderr}")
                ensure("ok elastic_pool " in ran.stdout, f"missing verdict: {ran.stdout}")
                ensure(not ran.stderr, f"sanitizer diagnostics: {ran.stderr}")
                if clang is not None:
                    clang_obj = scratch / "pristine_clang.o"
                    cbuilt = subprocess.run(
                        [clang, "-std=c17", "-O1", "-Wall", "-Wextra", "-Wstrict-prototypes",
                         "-Werror", "-pedantic", "-DVOS_HOST_MODEL", *includes,
                         "-c", str(src_path), "-o", str(clang_obj)],
                        cwd=scratch, capture_output=True, text=True, check=False, timeout=60)
                    ensure(cbuilt.returncode == 0,
                           f"clang strict C17 check failed: {cbuilt.stdout}{cbuilt.stderr}")
            else:
                ensure(ran.returncode != 0 and expected in ran.stderr,
                       f"mutant {name} survived or missed expected oracle ({expected!r}): {ran.stderr}")

        # Differential trace comparison against tools/vos/elastic_pool.py.
        words: list[tuple[int, ...]] = []
        words.extend(product(range(ep.COMMANDS), repeat=2))
        words.extend((
            (0, 2, 3, 4, 5, 6),
            (0, 0, 2, 3, 4, 5, 2, 3, 4, 6, 0, 0),
            (0, 0, 2, 3, 4, 5, 2, 3, 4, 6, 5, 6, 0),
            (1, 2, 4, 3, 4, 5, 6, 1),
            (0, 1, 2, 2, 3, 4, 5, 6, 0, 1),
        ))
        for word in words:
            digits = "".join(str(c) for c in word)
            py_pool = ep.fixture()
            for cmd in word:
                ep.apply_command(py_pool, cmd)
            c_ran = subprocess.run([str(pristine_bin), "--trace", digits],
                                   cwd=scratch, capture_output=True, text=True,
                                   check=False, timeout=15)
            ensure(c_ran.returncode == 0, f"trace {digits} failed: {c_ran.stderr}")
            c_events = _parse_c_trace(c_ran.stdout)
            ensure(c_events == py_pool.history,
                   f"differential mismatch on {digits}: C={c_events} vs Py={py_pool.history}")
            ensure(not ep.history_errors(py_pool.plan, c_events),
                   f"C trace violated history_errors on {digits}: {c_events}")


def cases() -> list[Case]:
    return [
        Case("std size classes and granule narrowing oracle",
             std_size_classes_and_granule_narrowing_oracle),
        Case("reference two-gen quarantine and exhaustion oracle",
             reference_quarantine_and_domain_oracle),
        Case("native ASan/UBSan pool C, differential traces, and 8 mutant kills",
             native_pool_c_and_mutant_controls, lane="guest"),
    ]
