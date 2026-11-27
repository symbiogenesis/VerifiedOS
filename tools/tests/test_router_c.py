# SPDX-License-Identifier: Apache-2.0
"""Pure-Python oracle and native C17 ASan/UBSan + mutation controls for router/."""

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.corpus import find_root

HEADER = "router/include/vos_router.h"
SOURCE = "router/src/router.c"
FIXTURE = "router/test/test_router.c"


@dataclass(frozen=True)
class OracleExtent:
    base: int
    span: int
    domain: int
    space: int

    def contains(self, addr: int) -> bool:
        return self.span > 0 and self.base <= addr < self.base + self.span

    def overlaps(self, other: "OracleExtent") -> bool:
        if self.span <= 0 or other.span <= 0:
            return False
        return self.base < other.base + other.span and other.base < self.base + self.span


@dataclass(frozen=True)
class OracleCredential:
    role: int
    principal: int
    scope_mask: int
    op_mask: int
    transcript: int
    use_ceiling: int
    expiry: int
    account_id: int


def _oracle_extents_separated(extents: tuple[OracleExtent, ...]) -> bool:
    for i, a in enumerate(extents):
        if a.span <= 0:
            return False
        for b in extents[i + 1 :]:
            if a.domain != b.domain and a.overlaps(b):
                return False
    return True


def _oracle_publish(
    queue_bound: int, phase: str, queue: tuple[tuple[str, int], ...],
    committed: bool, deltas: tuple[tuple[str, int], ...],
) -> tuple[str, tuple[tuple[str, int], ...]]:
    if not committed or phase == "rescan_required":
        return phase, queue
    combined = queue + deltas
    if len(combined) <= queue_bound:
        return "live", combined
    prefix = combined[: queue_bound - 1]
    return "rescan_required", (*prefix, ("rescan", 0))


def _oracle_delegates(parent: OracleCredential, child: OracleCredential) -> bool:
    return (
        child.role == parent.role
        and child.principal == parent.principal
        and (child.scope_mask & parent.scope_mask) == child.scope_mask
        and (child.op_mask & parent.op_mask) == child.op_mask
        and child.transcript == parent.transcript
        and child.use_ceiling <= parent.use_ceiling
        and child.expiry <= parent.expiry
        and child.account_id == parent.account_id
    )


def oracle_router_model() -> None:
    """Verify pure-Python reference semantics matching ObjectRouter.v and CredentialHandles.v."""
    extents = (
        OracleExtent(10, 40, 0, 0),
        OracleExtent(50, 40, 1, 0),
        OracleExtent(90, 20, 0, 1),
    )
    ensure(_oracle_extents_separated(extents), "valid disjoint extents rejected")
    ensure(not _oracle_extents_separated((extents[0], OracleExtent(40, 40, 1, 2))),
           "cross-domain overlapping extents accepted")
    ensure(not _oracle_extents_separated((OracleExtent(10, 0, 0, 0),)),
           "zero-span extent accepted")

    init_q: tuple[tuple[str, int], ...] = (("added", 11), ("removed", 12))
    ensure(_oracle_publish(4, "live", init_q, False, (("added", 13),)) == ("live", init_q),
           "uncommitted transaction published deltas")
    fit_phase, fit_q = _oracle_publish(4, "live", init_q, True, (("added", 13), ("added", 14)))
    ensure(fit_phase == "live" and len(fit_q) == 4, "exact-bound publication failed")
    ov_phase, ov_q = _oracle_publish(
        4, "live", init_q, True, (("added", 13), ("added", 14), ("added", 15)),
    )
    ensure(ov_phase == "rescan_required" and len(ov_q) == 4
           and sum(1 for k, _ in ov_q if k == "rescan") == 1
           and ov_q[-1] == ("rescan", 0),
           "overflow did not emit exact-one rescan marker")
    ensure(_oracle_publish(4, ov_phase, ov_q, True, (("added", 16),)) == (ov_phase, ov_q),
           "post-marker publication mutated queue")

    parent = OracleCredential(1, 2, 0b110, 0b110, 3, 2, 20, 7)
    child = OracleCredential(1, 2, 0b010, 0b010, 3, 1, 15, 7)
    ensure(_oracle_delegates(parent, child), "monotone delegation rejected")
    for bad in (
        replace(child, role=2),
        replace(child, principal=3),
        replace(child, scope_mask=0b111),
        replace(child, op_mask=0b111),
        replace(child, transcript=4),
        replace(child, use_ceiling=3),
        replace(child, expiry=21),
        replace(child, account_id=8),
    ):
        ensure(not _oracle_delegates(parent, bad), f"widened delegation accepted: {bad}")


def source_discipline_check() -> None:
    """Verify SPDX headers and GC-free C17 constraints across router/ sources."""
    root = find_root()
    for rel in (HEADER, SOURCE, FIXTURE):
        text = (root / rel).read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(first_line == "// SPDX-License-Identifier: Apache-2.0",
               f"{rel}: missing // SPDX-License-Identifier: Apache-2.0 header")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"{rel}: forbidden heap allocator {forbidden}")


def _variants(source: str) -> list[tuple[str, str, str]]:
    def changed(before: str, after: str) -> str:
        ensure(source.count(before) == 1, f"router mutation anchor must be unique: {before!r}")
        return source.replace(before, after, 1)

    return [
        ("pristine", source, ""),
        ("tagged-key-accepted",
         changed("static int word_has_tag(const vos_router_word *word)\n{\n    return word->tag != 0U;\n}",
                 "static int word_has_tag(const vos_router_word *word)\n{\n    (void)word;\n    return 0;\n}"),
         "tagged key"),
        ("cross-domain-accepted",
         changed("if (extents[i].domain != extents[j].domain\n"
                 "                && vos_router_extents_overlap(&extents[i], &extents[j])) {\n"
                 "                return 0;\n"
                 "            }",
                 "if (extents[i].domain != extents[j].domain\n"
                 "                && vos_router_extents_overlap(&extents[i], &extents[j])) {\n"
                 "                continue;\n"
                 "            }"),
         "cross-domain"),
        ("cross-domain-write-accepted",
         changed("if (address_hits_foreign_domain(comp, domain, records[i].address)) {\n"
                 "            return VOS_ROUTER_ERR_CROSS_DOMAIN;\n"
                 "        }",
                 "if (address_hits_foreign_domain(comp, domain, records[i].address)) {\n"
                 "            return VOS_ROUTER_OK;\n"
                 "        }"),
         "cross-domain"),
        ("twin-rescan-marker",
         changed("    const size_t prefix = qbound - 1U;\n"
                 "    if (sub->count < prefix) {\n"
                 "        const size_t copy_n = prefix - sub->count;\n"
                 "        for (size_t i = 0U; i < copy_n; ++i) {\n"
                 "            sub->queue[sub->count + i] = deltas[i];\n"
                 "        }\n"
                 "    }\n"
                 "    sub->queue[prefix].kind = VOS_DELTA_RESCAN;",
                 "    const size_t prefix = qbound - 1U;\n"
                 "    if (prefix > 0U) {\n"
                 "        sub->queue[prefix - 1U].kind = VOS_DELTA_RESCAN;\n"
                 "        sub->queue[prefix - 1U].object_id = 0U;\n"
                 "    }\n"
                 "    sub->queue[prefix].kind = VOS_DELTA_RESCAN;"),
         "twin rescan marker"),
        ("post-marker-delta-resumed",
         changed("    if (sub->phase == VOS_SUB_RESCAN_REQUIRED) {\n        return VOS_ROUTER_OK;\n    }",
                 "    if (sub->phase == VOS_SUB_RESCAN_REQUIRED) {\n        sub->count = 0U;\n        sub->phase = VOS_SUB_LIVE;\n    }"),
         "further delta added"),
        ("pre-commit-delta-published",
         changed("    if (txn->committed == 0U) {\n        return VOS_ROUTER_OK;\n    }",
                 "    (void)txn;"),
         "pre-commit delta published"),
        ("backpressuring-commit",
         changed("    (void)subs;\n    (void)sub_count;\n    (void)ring_status;\n    txn.committed = 1U;",
                 "    (void)subs;\n    (void)sub_count;\n"
                 "    if (ring_status == VOS_SUBMIT_WOULD_BLOCK) {\n"
                 "        txn.committed = 0U;\n"
                 "        return txn;\n"
                 "    }\n    txn.committed = 1U;"),
         "backpressuring commit"),
        ("reboot-survival",
         changed("        subs[i].active = 0U;\n"
                 "        subs[i].phase = VOS_SUB_RESCAN_REQUIRED;\n"
                 "        subs[i].count = 0U;",
                 "        subs[i].active = 1U;\n"
                 "        continue;"),
         "reboot survival"),
        ("raw-export-accepted",
         changed("    if (req->kind == VOS_HANDLE_REQ_EXPORT_SECRET) {\n        return VOS_ROUTER_ERR_DENIED;\n    }",
                 "    if (req->kind == VOS_HANDLE_REQ_EXPORT_SECRET) {\n        return VOS_ROUTER_OK;\n    }"),
         "raw export"),
        ("unsealed-raw-handle-accepted",
         changed("    if (handle->kind != VOS_HANDLE_SEALED) {\n        return VOS_ROUTER_ERR_DENIED;\n    }",
                 "    if (handle->kind != VOS_HANDLE_SEALED && handle->kind != VOS_HANDLE_RAW) {\n        return VOS_ROUTER_ERR_DENIED;\n    }"),
         "raw export"),
        ("widened-delegation-role",
         changed("    if (child->role != parent->role || child->principal != parent->principal) {\n        return 0;\n    }",
                 "    if (child->principal != parent->principal) {\n        return 0;\n    }"),
         "widened delegation of role"),
        ("widened-delegation-scope",
         changed("    if ((child->scope_mask & parent->scope_mask) != child->scope_mask) {\n        return 0;\n    }",
                 "    (void)0;"),
         "widened delegation of scope"),
        ("widened-delegation-op",
         changed("    if ((child->op_mask & parent->op_mask) != child->op_mask) {\n        return 0;\n    }",
                 "    (void)0;"),
         "widened delegation of operation"),
        ("cloned-account-counter",
         changed("    if (child->account_id != parent->account_id) {\n        return 0;\n    }",
                 "    (void)0;"),
         "cloned account counter"),
        ("stale-epoch-accepted",
         changed("        if (sessions[i].active != 0U\n"
                 "            && sessions[i].id == sid\n"
                 "            && sessions[i].epoch == comp->live_epoch) {",
                 "        if (sessions[i].active != 0U\n"
                 "            && sessions[i].id == sid) {"),
         "stale epoch"),
    ]


def _supports_asan_ubsan(compiler: str, scratch: Path) -> bool:
    probe_c = scratch / "_probe.c"
    probe_exe = scratch / "_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    compiled = subprocess.run(
        [compiler, "-std=c17", "-fsanitize=address,undefined", str(probe_c), "-o", str(probe_exe)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if compiled.returncode != 0:
        return False
    ran = subprocess.run([str(probe_exe)], capture_output=True, text=True, timeout=30, check=False)
    return ran.returncode == 0


def native_router_controls() -> None:
    """Compile router/ C17 sources with ASan/UBSan and execute all behavioral mutation kills."""
    candidates = [path for name in ("clang", "cc", "gcc") if (path := shutil.which(name)) is not None]
    ensure(bool(candidates), "native router controls require clang, cc, or gcc")
    root = find_root()
    work = toolenv.environment(root, sys.platform).parent / "router-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    source = (root / SOURCE).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="router-", dir=work) as directory:
        scratch = Path(directory)
        san_compiler = next((c for c in candidates if _supports_asan_ubsan(c, scratch)), None)
        ensure(san_compiler is not None, "native router controls require an ASan/UBSan C17 compiler")
        if san_compiler is None:
            return
        clang_path = shutil.which("clang")
        if clang_path is not None and clang_path != san_compiler:
            clang_exe = scratch / "pristine-clang"
            clang_build = subprocess.run(
                [
                    clang_path, "-std=c17", "-O1", "-Wall", "-Wextra",
                    "-Wstrict-prototypes", "-Werror", "-pedantic",
                    "-I", str(root / "router" / "include"),
                    str(root / SOURCE), str(root / FIXTURE),
                    "-o", str(clang_exe),
                ],
                capture_output=True, text=True, timeout=30, check=False,
            )
            ensure(clang_build.returncode == 0, f"clang strict C17 compile failed: {clang_build.stderr}")
            clang_run = subprocess.run([str(clang_exe)], capture_output=True, text=True, timeout=30, check=False)
            ensure(clang_run.returncode == 0 and "ok router C controls" in clang_run.stderr,
                   f"clang pristine run failed: {clang_run.stderr}")
        for name, candidate, expected in _variants(source):
            c_path = scratch / f"{name}.c"
            c_path.write_text(candidate, encoding="utf-8", newline="\n")
            exe_path = scratch / name
            compiled = subprocess.run(
                [
                    san_compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
                    "-Wstrict-prototypes", "-Werror", "-pedantic",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-I", str(root / "router" / "include"),
                    str(c_path), str(root / FIXTURE),
                    "-o", str(exe_path),
                ],
                capture_output=True, text=True, timeout=30, check=False,
            )
            ensure(compiled.returncode == 0,
                   f"{name}: stillborn compilation is not an executed rejection: {compiled.stderr}")
            result = subprocess.run(
                [str(exe_path)], capture_output=True, text=True, timeout=30, check=False,
            )
            if name == "pristine":
                ensure(result.returncode == 0, f"pristine router C failed: {result.stderr}")
                ensure("ok router C controls" in result.stderr,
                       "pristine router controls did not print success verdict")
            else:
                ensure(result.returncode != 0 and expected in result.stderr,
                       f"{name}: mutant survived or missed oracle ({expected!r}): {result.stderr}")


def cases() -> list[Case]:
    return [
        Case("router pure-Python oracle model", oracle_router_model),
        Case("router C17 SPDX and GC-free source discipline", source_discipline_check),
        Case("router native C17 ASan/UBSan and mutation kills", native_router_controls, lane="guest"),
    ]
