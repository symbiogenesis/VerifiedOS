# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracle and native C17 ASan/UBSan + Clang + mutation controls for compat-workflow/."""

import hashlib
import hmac
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
COMPAT_DIR = ROOT / "compat-workflow"
COMPAT_H = COMPAT_DIR / "include" / "vos_compat_workflow.h"
COMPAT_C = COMPAT_DIR / "src" / "compat_workflow.c"
COMPAT_TEST_C = COMPAT_DIR / "test" / "test_compat_workflow.c"
COMPAT_README = COMPAT_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "CompatibilityWorkflow.v"

LC_FREE = 0
LC_BOUND = 1
LC_QUIESCING = 2
LC_REVOKED = 3
LC_SWEEPING = 4
LC_REUSABLE = 5

DIAG_TRUNCATED_MARKER = 0x5452554E


def _digest(tag: int) -> bytes:
    return bytes((tag ^ (i * 5 + 3)) & 0xFF for i in range(32))


@dataclass(frozen=True, slots=True)
class _OracleEditorAuth:
    private_source_ep: bool = True
    private_result_ep: bool = True
    holds_exec_staged: bool = False
    holds_signing_key: bool = False
    holds_mint_cap: bool = False
    holds_sealing_cap: bool = False
    holds_wiring_cap: bool = False
    holds_boot_select_cap: bool = False

    def is_valid(self) -> bool:
        return (
            self.private_source_ep
            and self.private_result_ep
            and not self.holds_exec_staged
            and not self.holds_signing_key
            and not self.holds_mint_cap
            and not self.holds_sealing_cap
            and not self.holds_wiring_cap
            and not self.holds_boot_select_cap
        )


@dataclass(frozen=True, slots=True)
class _OracleBuilderAuth:
    immutable_closure_ok: bool = True
    output_reservation_ok: bool = True
    diagnostics_ep_ok: bool = True
    holds_exec_staged: bool = False
    holds_sealing_cap: bool = False
    holds_wiring_cap: bool = False
    holds_signing_key: bool = False

    def is_valid(self) -> bool:
        return (
            self.immutable_closure_ok
            and self.output_reservation_ok
            and self.diagnostics_ep_ok
            and not self.holds_exec_staged
            and not self.holds_sealing_cap
            and not self.holds_wiring_cap
            and not self.holds_signing_key
        )


@dataclass(frozen=True, slots=True)
class _OraclePoolDecl:
    kind: int
    max_capacity: int
    has_all_r08_046_fields: bool = True

    def is_valid(self, expected_kind: int) -> bool:
        return self.kind == expected_kind and self.max_capacity > 0 and self.has_all_r08_046_fields


@dataclass(frozen=True, slots=True)
class _OracleProfile:
    profile_id: int = 1
    predeclared: bool = True
    toolchain_id: int = 10
    config_id: int = 20
    step_budget: int = 1000
    pools: tuple[_OraclePoolDecl, ...] = (
        _OraclePoolDecl(0, 16),
        _OraclePoolDecl(1, 1024),
        _OraclePoolDecl(2, 4),
        _OraclePoolDecl(3, 8192),
        _OraclePoolDecl(4, 4),
        _OraclePoolDecl(5, 8),
        _OraclePoolDecl(6, 16),
        _OraclePoolDecl(7, 4),
    )
    max_source_edges: int = 32
    max_source_depth: int = 8
    max_chunk_bytes: int = 128
    max_partial_objects: int = 2
    epoch_limit: int = 5
    max_diag_record_bytes: int = 64
    max_diag_bytes: int = 128
    max_checking_steps: int = 2000
    max_result_bytes: int = 256
    ordinary_borrows_comp: bool = False

    def is_valid(self) -> bool:
        if not self.predeclared or self.step_budget <= 0 or self.ordinary_borrows_comp:
            return False
        if len(self.pools) != 8:
            return False
        if not all(self.pools[i].is_valid(i) for i in range(8)):
            return False
        return (
            self.max_source_edges > 0
            and self.max_source_depth > 0
            and self.max_chunk_bytes > 0
            and self.max_partial_objects > 0
            and self.epoch_limit > 0
            and self.max_diag_record_bytes > 0
            and self.max_diag_bytes > 0
            and self.max_checking_steps > 0
            and self.max_result_bytes > 0
        )


@dataclass(frozen=True, slots=True)
class _OracleCacheIdentity:
    source_digest: bytes
    dep_closure_digest: bytes
    imported_lemma_digest: bytes
    semantics_digest: bytes
    config_digest: bytes
    assumption_digest: bytes
    profile_id: int

    def key_digest(self) -> bytes:
        payload = (
            b"VOSCPKEY"
            + self.source_digest
            + self.dep_closure_digest
            + self.imported_lemma_digest
            + self.semantics_digest
            + self.config_digest
            + self.assumption_digest
            + self.profile_id.to_bytes(8, "little")
        )
        return hashlib.sha256(payload).digest()


@dataclass(slots=True)
class _OraclePartial:
    slot_id: int
    declared_total: int
    next_seq: int = 0
    buf: bytearray = field(default_factory=bytearray)


@dataclass(slots=True)
class _OracleJob:
    slot: int
    epoch: int
    lifecycle: int
    stage: str
    step_budget: int
    steps_used: int = 0
    diags: list[bytes] = field(default_factory=list)
    diag_bytes: int = 0
    diag_truncated: bool = False
    output_executable: bool = False


@dataclass(slots=True)
class _OracleWorkflow:
    editor_auth: _OracleEditorAuth
    builder_auth: _OracleBuilderAuth
    profile: _OracleProfile
    running_gen_root: bytes
    running_roster_hash: bytes
    boot_epoch: int = 1
    next_job_epoch: int = 1
    epoch_retired: bool = False
    partials: dict[int, _OraclePartial] = field(default_factory=dict)
    staged: list[tuple[int, bytes, bool]] = field(default_factory=list)
    jobs: dict[int, _OracleJob] = field(default_factory=dict)
    proof_cache: dict[bytes, tuple[_OracleCacheIdentity, bytes]] = field(default_factory=dict)
    admitted: tuple[bytes, bytes] | None = None
    consent_granted: bool = False
    consent_outstanding: int = 0
    successor_booted: bool = False

    def _auth_ok(self) -> bool:
        return self.editor_auth.is_valid() and self.builder_auth.is_valid()

    def read_source_slice(
        self,
        src_id: int,
        src_ver: int,
        src_bytes: bytes,
        grant_ok: bool,
        req_id: int,
        req_ver: int,
        offset: int,
        length: int,
        index_objs: int,
        index_edges: int,
        index_depth: int,
    ) -> tuple[str, bytes | None]:
        if not self._auth_ok():
            return "AUTHORITY", None
        if not self.profile.is_valid():
            return "INVALID_PROFILE", None
        if not grant_ok:
            return "MISSING_GRANT", None
        if req_id != src_id or req_ver != src_ver:
            return "WRONG_OBJECT_OR_VERSION", None
        if offset < 0 or length < 0 or offset + length > len(src_bytes):
            return "OUT_OF_RANGE", None
        if (
            index_objs > self.profile.pools[0].max_capacity
            or index_edges > self.profile.max_source_edges
            or index_depth > self.profile.max_source_depth
        ):
            return "INDEX_EXHAUSTED", None
        return "OK", src_bytes[offset : offset + length]

    def stage_edited_source(
        self,
        reservation_ok: bool,
        slot_id: int,
        seq: int,
        declared_total: int,
        chunk: bytes,
        expected_digest: bytes,
        is_final: bool,
    ) -> str:
        if not self._auth_ok():
            return "AUTHORITY"
        if not reservation_ok:
            return "MISSING_GRANT"
        max_bytes = self.profile.pools[1].max_capacity
        if declared_total <= 0 or declared_total > max_bytes or len(chunk) > self.profile.max_chunk_bytes:
            self.partials.pop(slot_id, None)
            return "STAGING_OVER_BUDGET"
        ps = self.partials.get(slot_id)
        if ps is None:
            if len(self.partials) >= self.profile.max_partial_objects:
                return "STAGING_OVER_BUDGET"
            if seq != 0 or len(chunk) > declared_total:
                return "STAGING_SEQUENCE"
            ps = _OraclePartial(slot_id=slot_id, declared_total=declared_total)
            self.partials[slot_id] = ps
        elif (
            seq != ps.next_seq
            or declared_total != ps.declared_total
            or len(ps.buf) + len(chunk) > ps.declared_total
        ):
            self.partials.pop(slot_id, None)
            return "STAGING_SEQUENCE"
        ps.buf.extend(chunk)
        ps.next_seq += 1
        if not is_final:
            return "OK"
        self.partials.pop(slot_id, None)
        if len(ps.buf) != ps.declared_total:
            return "STAGING_INCOMPLETE"
        actual = hashlib.sha256(bytes(ps.buf)).digest()
        if not hmac.compare_digest(actual, expected_digest):
            return "STAGING_DIGEST"
        self.staged.append((slot_id, actual, False))
        return "OK"

    def submit_build(
        self,
        closure_ok: bool,
        comp_ep_ok: bool,
        closure_objs: int,
        closure_edges: int,
        closure_depth: int,
        profile: _OracleProfile,
    ) -> tuple[str, tuple[int, int] | None]:
        if not self._auth_ok():
            return "AUTHORITY", None
        if not closure_ok:
            return "MISSING_CLOSURE", None
        if not comp_ep_ok:
            return "COMP_SERVICE", None
        if not profile.is_valid() or profile.profile_id != self.profile.profile_id:
            return "INVALID_PROFILE", None
        if (
            closure_objs > profile.pools[0].max_capacity
            or closure_edges > profile.max_source_edges
            or closure_depth > profile.max_source_depth
        ):
            return "INDEX_EXHAUSTED", None
        if self.epoch_retired or self.next_job_epoch >= profile.epoch_limit:
            self.epoch_retired = True
            return "EPOCH_EXHAUSTED", None
        active = [j for j in self.jobs.values() if j.lifecycle not in (LC_FREE, LC_REUSABLE)]
        if len(active) >= profile.pools[2].max_capacity:
            return "JOB_POOL_EXHAUSTED", None
        slot = next(
            (i for i in range(profile.pools[2].max_capacity)
             if i not in self.jobs or self.jobs[i].lifecycle in (LC_FREE, LC_REUSABLE)),
            len(self.jobs),
        )
        epoch = self.next_job_epoch
        self.next_job_epoch += 1
        self.jobs[slot] = _OracleJob(
            slot=slot,
            epoch=epoch,
            lifecycle=LC_BOUND,
            stage="RUNNING",
            step_budget=profile.step_budget,
        )
        return "OK", (slot, epoch)

    def advance_build(
        self,
        slot: int,
        epoch: int,
        steps_req: int,
        workset_bytes: int,
        diag_msg: bytes,
        finish: bool,
    ) -> str:
        if not self._auth_ok():
            return "AUTHORITY"
        jb = self.jobs.get(slot)
        if jb is None or jb.epoch != epoch:
            return "STALE_HANDLE"
        if jb.lifecycle != LC_BOUND or jb.stage != "RUNNING":
            return "JOB_NOT_ACTIVE"
        if jb.steps_used + steps_req > jb.step_budget:
            return "BUDGET_EXPANSION"
        if workset_bytes > self.profile.pools[3].max_capacity:
            jb.stage = "FAILED"
            return "PASS_ARENA_EXHAUSTED"
        jb.steps_used += steps_req
        if diag_msg:
            if len(diag_msg) > self.profile.max_diag_record_bytes:
                jb.diag_truncated = True
                rec = diag_msg[: self.profile.max_diag_record_bytes]
            else:
                rec = diag_msg
            if (
                len(jb.diags) >= self.profile.pools[4].max_capacity
                or jb.diag_bytes + len(rec) > self.profile.max_diag_bytes
            ):
                jb.diag_truncated = True
            else:
                jb.diags.append(rec)
                jb.diag_bytes += len(rec)
        if finish:
            jb.stage = "COMPLETED"
            jb.output_executable = False
        return "OK"

    def read_diagnostics(
        self,
        slot: int,
        epoch: int,
        result_ep_ok: bool,
        max_records: int,
        max_bytes: int,
    ) -> tuple[str, tuple[list[bytes], bool, int] | None]:
        if not self._auth_ok():
            return "AUTHORITY", None
        if not result_ep_ok:
            return "MISSING_GRANT", None
        jb = self.jobs.get(slot)
        if jb is None or jb.epoch != epoch:
            return "STALE_HANDLE", None
        eff_recs = min(max_records, self.profile.pools[4].max_capacity)
        eff_bytes = min(max_bytes, self.profile.max_diag_bytes)
        trunc = jb.diag_truncated or max_records > self.profile.pools[4].max_capacity or max_bytes > self.profile.max_diag_bytes
        out: list[bytes] = []
        used = 0
        for d in jb.diags:
            if len(out) >= eff_recs or used + len(d) > eff_bytes:
                trunc = True
                break
            out.append(d)
            used += len(d)
        marker = DIAG_TRUNCATED_MARKER if trunc else 0
        return "OK", (out, trunc, marker)

    def cancel_build(
        self,
        slot: int,
        epoch: int,
        cancel_cap_ok: bool,
        interrupt_mid_sweep: bool,
    ) -> str:
        if not self._auth_ok():
            return "AUTHORITY"
        if not cancel_cap_ok:
            return "MISSING_GRANT"
        jb = self.jobs.get(slot)
        if jb is None or jb.epoch != epoch:
            return "STALE_HANDLE"
        if jb.lifecycle != LC_BOUND:
            return "JOB_NOT_ACTIVE"
        jb.stage = "CANCELLED"
        jb.lifecycle = LC_SWEEPING
        if interrupt_mid_sweep:
            return "LIFECYCLE_INTERRUPTED"
        jb.lifecycle = LC_REUSABLE
        return "OK"

    def submit_successor_admission(
        self,
        slot: int,
        epoch: int,
        *,
        proof_complete: bool,
        checking_arena_ok: bool,
        checking_steps: int,
        roster_entries: int,
        roster_valid: bool,
        tal_ok: bool,
        source_corr_ok: bool,
        cache_hit_used: bool,
        cache_id: _OracleCacheIdentity,
        candidate_root: bytes,
        candidate_roster: bytes,
    ) -> str:
        if not self._auth_ok():
            return "AUTHORITY"
        jb = self.jobs.get(slot)
        if jb is None or jb.epoch != epoch:
            return "STALE_HANDLE"
        if jb.stage != "COMPLETED":
            return "JOB_NOT_ACTIVE"
        if not proof_complete:
            return "PROOF_INCOMPLETE"
        if not checking_arena_ok:
            return "CHECKING_ARENA"
        if roster_entries > self.profile.pools[6].max_capacity or checking_steps > self.profile.max_checking_steps:
            return "CHECKING_STEPS"
        if not roster_valid:
            return "INADMISSIBLE_ROSTER"
        if not (tal_ok and source_corr_ok):
            return "TAL_OR_CORR"
        key = cache_id.key_digest()
        if cache_hit_used and key not in self.proof_cache:
            return "CACHE_MISS"
        self.proof_cache[key] = (cache_id, candidate_root)
        self.admitted = (candidate_root, candidate_roster)
        self.consent_granted = False
        self.successor_booted = False
        return "OK"

    def request_generation_consent(
        self,
        candidate_root: bytes,
        roster_hash: bytes,
        *,
        user_consented: bool,
        on_die_cred_ok: bool,
        external_roaming_key: bool,
    ) -> str:
        if external_roaming_key:
            return "EXTERNAL_AUTH_DECLINED"
        if not self._auth_ok():
            return "AUTHORITY"
        if self.consent_outstanding >= self.profile.pools[7].max_capacity:
            return "CONSENT_POOL_EXHAUSTED"
        if self.admitted is None:
            return "NO_ADMITTED"
        if self.admitted != (candidate_root, roster_hash):
            return "CONSENT_MISMATCH"
        if not on_die_cred_ok:
            return "ON_DIE_CRED_ABSENT"
        if not user_consented:
            return "CONSENT_MISMATCH"
        self.consent_granted = True
        self.consent_outstanding += 1
        return "OK"

    def boot_successor(self) -> str:
        if not self._auth_ok():
            return "AUTHORITY"
        if self.admitted is None or not self.consent_granted:
            return "NO_ADMITTED"
        self.running_gen_root, self.running_roster_hash = self.admitted
        self.boot_epoch += 1
        self.consent_granted = False
        self.consent_outstanding = 0
        self.successor_booted = True
        return "OK"

    def read_successor_test_result(
        self,
        grant_ok: bool,
        cand_root: bytes,
        test_id: int,
        boot_epoch: int,
        result_bytes: int,
        expected_root: bytes,
        expected_test_id: int,
    ) -> str:
        if not self._auth_ok():
            return "AUTHORITY"
        if not self.successor_booted:
            return "NOT_BOOTED"
        if not grant_ok:
            return "MISSING_GRANT"
        if result_bytes > self.profile.max_result_bytes:
            return "RESULT_OVER_BUDGET"
        if (
            cand_root != expected_root
            or cand_root != self.running_gen_root
            or test_id != expected_test_id
            or boot_epoch != self.boot_epoch
        ):
            return "RESULT_UNBOUND"
        return "OK"

    def attempt_forbidden_op(self, op: str) -> str:
        return f"REFUSED_{op}"


def _compat_workflow_oracle() -> None:
    """Exercise full positive workflow and every refusal/boundary in the independent oracle."""
    wf = _OracleWorkflow(
        editor_auth=_OracleEditorAuth(),
        builder_auth=_OracleBuilderAuth(),
        profile=_OracleProfile(),
        running_gen_root=_digest(0xA0),
        running_roster_hash=_digest(0xB0),
    )

    # Authority and profile validation controls
    ensure(not _OracleEditorAuth(holds_signing_key=True).is_valid(), "privileged editor accepted")
    ensure(not _OracleBuilderAuth(holds_exec_staged=True).is_valid(), "privileged builder accepted")
    ensure(
        not replace(_OracleProfile(), ordinary_borrows_comp=True).is_valid(),
        "ordinary borrowing profile accepted",
    )

    # Positive flow
    src = bytes((i + 7) & 0xFF for i in range(200))
    st, sl = wf.read_source_slice(101, 3, src, True, 101, 3, 10, 64, 4, 6, 3)
    ensure(st == "OK" and sl == src[10:74], "read_source_slice failed")

    edited = bytes((i * 3 + 1) & 0xFF for i in range(160))
    exp_dig = hashlib.sha256(edited).digest()
    ensure(wf.stage_edited_source(True, 7, 0, 160, edited[:100], exp_dig, False) == "OK",
           "stage chunk 0 failed")
    ensure(wf.stage_edited_source(True, 7, 1, 160, edited[100:], exp_dig, True) == "OK",
           "stage chunk 1 failed")
    ensure(all(not exe for _, _, exe in wf.staged), "staged object marked executable")

    bst, handle = wf.submit_build(True, True, 4, 6, 3, wf.profile)
    ensure(bst == "OK" and handle is not None, "submit_build failed")
    if handle is None:
        return
    slot, epoch = handle
    ensure(wf.advance_build(slot, epoch, 400, 4096, b"compile: ok", True) == "OK",
           "advance_build failed")
    dst, dv = wf.read_diagnostics(slot, epoch, True, 4, 128)
    ensure(dst == "OK" and dv == ([b"compile: ok"], False, 0), "read_diagnostics failed")

    cid = _OracleCacheIdentity(
        _digest(0x11), _digest(0x22), _digest(0x33), _digest(0x44), _digest(0x55), _digest(0x66), 1
    )
    cand_root, cand_roster = _digest(0xD1), _digest(0xE1)
    ensure(
        wf.submit_successor_admission(
            slot,
            epoch,
            proof_complete=True,
            checking_arena_ok=True,
            checking_steps=500,
            roster_entries=4,
            roster_valid=True,
            tal_ok=True,
            source_corr_ok=True,
            cache_hit_used=False,
            cache_id=cid,
            candidate_root=cand_root,
            candidate_roster=cand_roster,
        ) == "OK",
        "admission failed",
    )
    ensure(
        wf.request_generation_consent(
            cand_root, cand_roster, user_consented=True, on_die_cred_ok=True, external_roaming_key=False
        ) == "OK",
        "consent failed",
    )
    ensure(wf.boot_successor() == "OK" and wf.boot_epoch == 2, "boot_successor failed")
    ensure(
        wf.read_successor_test_result(True, cand_root, 42, 2, 32, cand_root, 42) == "OK",
        "read_successor_test_result failed",
    )

    # Negative controls
    ensure(wf.attempt_forbidden_op("EXEC_STAGED_NATIVE") == "REFUSED_EXEC_STAGED_NATIVE",
           "R-02-008 refusal failed")
    ensure(
        wf.request_generation_consent(
            cand_root, cand_roster, user_consented=True, on_die_cred_ok=True, external_roaming_key=True
        ) == "EXTERNAL_AUTH_DECLINED",
        "R-12-020 external roaming key accepted",
    )
    ensure(
        wf.read_successor_test_result(True, cand_root, 42, 1, 32, cand_root, 42) == "RESULT_UNBOUND",
        "old epoch test result accepted",
    )
    ensure(
        replace(cid, imported_lemma_digest=_digest(0x99)).key_digest() not in wf.proof_cache,
        "cache key collision on lemma change",
    )
    ensure(
        wf.submit_successor_admission(
            slot,
            epoch,
            proof_complete=True,
            checking_arena_ok=True,
            checking_steps=500,
            roster_entries=4,
            roster_valid=True,
            tal_ok=False,
            source_corr_ok=True,
            cache_hit_used=True,
            cache_id=cid,
            candidate_root=cand_root,
            candidate_roster=cand_roster,
        ) == "TAL_OR_CORR",
        "cache hit bypassed TAL check",
    )

    # Diagnostics overflow truncation & interrupted cancel + epoch exhaustion
    bst2, h2 = wf.submit_build(True, True, 4, 6, 3, wf.profile)
    ensure(bst2 == "OK" and h2 is not None, "submit_build 2 failed")
    if h2 is None:
        return
    s2, e2 = h2
    for _ in range(5):
        ensure(wf.advance_build(s2, e2, 50, 1024, b"x" * 40, False) == "OK", "diag fill failed")
    dst2, dv2 = wf.read_diagnostics(s2, e2, True, 4, 128)
    ensure(dst2 == "OK" and dv2 is not None and dv2[1] is True and dv2[2] == DIAG_TRUNCATED_MARKER,
           "diagnostics truncation marker missing")
    ensure(wf.cancel_build(s2, 999, True, False) == "STALE_HANDLE", "stale cancel accepted")
    ensure(wf.cancel_build(s2, e2, True, True) == "LIFECYCLE_INTERRUPTED",
           "interrupted cancel succeeded")
    ensure(wf.jobs[s2].lifecycle != LC_REUSABLE, "interrupted job became reusable")


def _surface_and_proof_contract() -> None:
    """Verify SPDX headers, GC-free C17 surface, and CompatibilityWorkflow.v theorem/witness surface."""
    for path in (COMPAT_H, COMPAT_C, COMPAT_TEST_C, COMPAT_README, PROOFS_V):
        ensure(path.is_file(), f"missing compat-workflow artifact: {path}")

    for c_path in (COMPAT_H, COMPAT_C, COMPAT_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(first_line == "// SPDX-License-Identifier: Apache-2.0",
               f"missing // SPDX-License-Identifier: Apache-2.0 header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden heap allocator {forbidden} in {c_path}")

    c_src = COMPAT_C.read_text(encoding="utf-8")
    for fn in (
        "vos_compat_service_init",
        "vos_compat_profile_validate",
        "vos_compat_lifecycle_step",
        "vos_compat_compute_cache_key",
        "vos_compat_cache_lookup",
        "vos_compat_read_source_slice",
        "vos_compat_stage_edited_source",
        "vos_compat_submit_build",
        "vos_compat_advance_build",
        "vos_compat_read_diagnostics",
        "vos_compat_cancel_build",
        "vos_compat_submit_successor_admission",
        "vos_compat_request_generation_consent",
        "vos_compat_boot_successor",
        "vos_compat_read_successor_test_result",
        "vos_compat_attempt_forbidden_op",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    v_first = v_src.splitlines()[0] if v_src.splitlines() else ""
    ensure(v_first == "(* SPDX-License-Identifier: Apache-2.0 *)",
           "CompatibilityWorkflow.v must open with (* SPDX-License-Identifier: Apache-2.0 *)")
    ensure("Require ProofSupport." in v_src,
           "CompatibilityWorkflow.v must Require ProofSupport.")
    for sym in (
        "authority_separation_no_exec_sign_wire",
        "same_gen_native_exec_always_refused",
        "staged_list_all_non_executable",
        "staged_object_never_executable",
        "external_roaming_auth_always_declined",
        "lifecycle_interruption_never_reusable",
        "profile_rejects_ordinary_borrowing",
        "epoch_exhaustion_retires_without_wrap",
        "cache_identity_sensitive_to_every_field",
        "cache_hit_never_bypasses_admission",
        "refused_admission_preserves_running_generation",
        "diagnostics_overflow_emits_truncation_marker",
        "successor_test_result_bound_to_root_test_and_epoch",
        "positive_end_to_end_successor_generation_trace",
        "negative_controls_all_refused",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in CompatibilityWorkflow.v")

    v_clean = strip_comments(v_src)
    for banned in ("CoInductive", "CoFixpoint", "cofix", "Axiom", "Parameter",
                   "Admitted", "Conjecture", "admit", "Section"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in CompatibilityWorkflow.v",
        )
    ensure(re.search(r"\bModule\s+Type\b", v_clean) is None,
           "forbidden Module Type in CompatibilityWorkflow.v")
    for rec in re.findall(r"\bRecord\s+([\w']+)", v_clean):
        ensure(re.search(rf"\bDefinition\s+witness_{re.escape(rec)}\b", v_clean) is not None,
               f"missing witness_{rec} in CompatibilityWorkflow.v")


def _supports_flags(compiler: str, flags: list[str], scratch: Path) -> bool:
    probe_c = scratch / "_probe.c"
    probe_bin = scratch / "_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    built = subprocess.run(
        [compiler, *flags, str(probe_c), "-o", str(probe_bin)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if built.returncode != 0:
        return False
    ran = subprocess.run([str(probe_bin)], capture_output=True, text=True, timeout=30, check=False)
    return ran.returncode == 0


def _compile_and_link(compiler: str, flags: list[str], src_c: Path,
                      out_bin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            compiler,
            *flags,
            f"-I{COMPAT_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(src_c),
            str(CRYPTO_SOURCE),
            str(COMPAT_TEST_C),
            "-o",
            str(out_bin),
        ],
        capture_output=True, text=True, timeout=60, check=False,
    )


def _mutants(source: str) -> list[tuple[str, str, str]]:
    def replaced(before: str, after: str, label: str) -> str:
        ensure(source.count(before) == 1, f"mutant anchor missing or non-unique ({label}): {before!r}")
        return source.replace(before, after, 1)

    return [
        (
            "authority-editor-signing",
            replaced(
                "ea->holds_exec_staged != 0u || ea->holds_signing_key != 0u ||",
                "ea->holds_exec_staged != 0u || (0u && ea->holds_signing_key != 0u) ||",
                "authority-editor-signing",
            ),
            "editor holding signing key accepted",
        ),
        (
            "authority-builder-exec",
            replaced(
                "ba->diagnostics_ep_ok == 0u || ba->holds_exec_staged != 0u ||",
                "ba->diagnostics_ep_ok == 0u || (0u && ba->holds_exec_staged != 0u) ||",
                "authority-builder-exec",
            ),
            "builder holding execute authority accepted",
        ),
        (
            "profile-missing-recovery",
            replaced(
                "pd->has_recovery_reserve == 0u || pd->has_confidentiality == 0u ||",
                "(0u && pd->has_recovery_reserve == 0u) || pd->has_confidentiality == 0u ||",
                "profile-missing-recovery",
            ),
            "profile missing R-08-046 recovery reserve accepted",
        ),
        (
            "profile-ordinary-borrowing",
            replaced(
                "profile->step_budget == 0u || profile->ordinary_borrows_comp != 0u) {",
                "profile->step_budget == 0u || (0u && profile->ordinary_borrows_comp != 0u)) {",
                "profile-ordinary-borrowing",
            ),
            "ordinary mode borrowing composition slots accepted",
        ),
        (
            "read-slice-wrong-version",
            replaced(
                "if (req_obj_id != src->obj_id || req_version != src->version) {",
                "if (req_obj_id != src->obj_id || (0u && req_version != src->version)) {",
                "read-slice-wrong-version",
            ),
            "wrong source version accepted",
        ),
        (
            "stage-digest-mismatch",
            replaced(
                "    if (!equal_hashes(&actual, expected_digest)) {\n"
                "        abort_partial(ps);\n"
                "        return VOS_COMPAT_ERR_STAGING_DIGEST;\n"
                "    }",
                "    if (0 && !equal_hashes(&actual, expected_digest)) {\n"
                "        abort_partial(ps);\n"
                "        return VOS_COMPAT_ERR_STAGING_DIGEST;\n"
                "    }",
                "stage-digest-mismatch",
            ),
            "mismatched digest staging accepted",
        ),
        (
            "stage-mark-executable",
            replaced(
                "    dst->executable = 0u;",
                "    dst->executable = 1u;",
                "stage-mark-executable",
            ),
            "staged object executable or digest mismatch",
        ),
        (
            "epoch-wrap-instead-of-retire",
            replaced(
                "    if (svc->epoch_retired != 0u || svc->next_job_epoch >= req_profile->epoch_limit) {\n"
                "        svc->epoch_retired = 1u;\n"
                "        return VOS_COMPAT_ERR_EPOCH_EXHAUSTED;\n"
                "    }",
                "    if (0u && (svc->epoch_retired != 0u || svc->next_job_epoch >= req_profile->epoch_limit)) {\n"
                "        svc->epoch_retired = 1u;\n"
                "        return VOS_COMPAT_ERR_EPOCH_EXHAUSTED;\n"
                "    }",
                "epoch-wrap-instead-of-retire",
            ),
            "epoch exhaustion wrapped or failed to retire",
        ),
        (
            "advance-budget-expansion",
            replaced(
                "    if (steps_req > jb->step_budget || jb->steps_used > jb->step_budget - steps_req) {\n"
                "        return VOS_COMPAT_ERR_BUDGET_EXPANSION;\n"
                "    }",
                "    if (0u && (steps_req > jb->step_budget || jb->steps_used > jb->step_budget - steps_req)) {\n"
                "        return VOS_COMPAT_ERR_BUDGET_EXPANSION;\n"
                "    }",
                "advance-budget-expansion",
            ),
            "budget expansion accepted",
        ),
        (
            "advance-pass-arena-exhaustion",
            replaced(
                "    if (workset_bytes > arena_cap) {\n"
                "        jb->stage = VOS_COMPAT_JOB_FAILED;\n"
                "        memset(&jb->output_digest, 0, sizeof(jb->output_digest));\n"
                "        jb->output_executable = 0u;\n"
                "        return VOS_COMPAT_ERR_PASS_ARENA_EXHAUSTED;\n"
                "    }",
                "    if (0u && workset_bytes > arena_cap) {\n"
                "        jb->stage = VOS_COMPAT_JOB_FAILED;\n"
                "        memset(&jb->output_digest, 0, sizeof(jb->output_digest));\n"
                "        jb->output_executable = 0u;\n"
                "        return VOS_COMPAT_ERR_PASS_ARENA_EXHAUSTED;\n"
                "    }",
                "advance-pass-arena-exhaustion",
            ),
            "pass arena exhaustion accepted",
        ),
        (
            "diag-drop-truncation-marker",
            replaced(
                "        out_view->marker_code = VOS_COMPAT_DIAG_TRUNCATED_MARKER;",
                "        out_view->marker_code = 0u;",
                "diag-drop-truncation-marker",
            ),
            "diagnostics overflow missing truncation marker",
        ),
        (
            "cancel-interrupt-early-reusable",
            replaced(
                "    if (interrupt_mid_sweep != 0u) {\n"
                "        (void)vos_compat_lifecycle_step(lc, VOS_COMPAT_ACT_INTERRUPT, &lc);\n"
                "        jb->lifecycle = lc;\n"
                "        return VOS_COMPAT_ERR_LIFECYCLE_INTERRUPTED;\n"
                "    }",
                "    if (interrupt_mid_sweep != 0u) {\n"
                "        jb->lifecycle = VOS_COMPAT_LC_REUSABLE;\n"
                "        return VOS_COMPAT_ERR_LIFECYCLE_INTERRUPTED;\n"
                "    }",
                "cancel-interrupt-early-reusable",
            ),
            "interrupted cancel became reusable early",
        ),
        (
            "cache-bypass-tal-check",
            replaced(
                "    if (pkg->tal_ok == 0u || pkg->source_corr_ok == 0u) {\n"
                "        return VOS_COMPAT_ERR_TAL_OR_CORR;\n"
                "    }",
                "    if (pkg->cache_hit_used == 0u && (pkg->tal_ok == 0u || pkg->source_corr_ok == 0u)) {\n"
                "        return VOS_COMPAT_ERR_TAL_OR_CORR;\n"
                "    }",
                "cache-bypass-tal-check",
            ),
            "cache hit bypassed TAL check",
        ),
        (
            "consent-allow-external-roaming",
            replaced(
                "    if (req->external_roaming_key != 0u) {\n"
                "        return VOS_COMPAT_ERR_EXTERNAL_AUTH_DECLINED;\n"
                "    }",
                "    if (0u && req->external_roaming_key != 0u) {\n"
                "        return VOS_COMPAT_ERR_EXTERNAL_AUTH_DECLINED;\n"
                "    }",
                "consent-allow-external-roaming",
            ),
            "external roaming authenticator accepted",
        ),
        (
            "test-result-ignore-boot-epoch",
            replaced(
                "        res->test_id != expected_test_id ||\n"
                "        res->boot_epoch != svc->boot_epoch) {",
                "        res->test_id != expected_test_id ||\n"
                "        (0u && res->boot_epoch != svc->boot_epoch)) {",
                "test-result-ignore-boot-epoch",
            ),
            "old boot epoch test result accepted",
        ),
        (
            "forbid-allow-same-gen-native-exec",
            replaced(
                "    case VOS_COMPAT_FORBID_WASM_NATIVE_ESCAPE:\n"
                "        return VOS_COMPAT_ERR_SAME_GEN_NATIVE_EXEC;",
                "    case VOS_COMPAT_FORBID_WASM_NATIVE_ESCAPE:\n"
                "        return VOS_COMPAT_OK;",
                "forbid-allow-same-gen-native-exec",
            ),
            "same-gen native execution allowed",
        ),
    ]


def _native_c_and_mutation_controls() -> None:
    """Compile and run compat-workflow C17 tests under Clang + GCC ASan/UBSan and kill all mutants."""
    if sys.platform != "linux":
        return

    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None, "clang is required in Linux guest")
    ensure(gcc is not None, "gcc is required in Linux guest")
    if clang is None or gcc is None:
        return

    strict_flags = [
        "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes", "-pedantic",
    ]
    asan_flags = [*strict_flags, "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]

    work = toolenv.environment(ROOT, sys.platform).parent / "c-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compatwf-", dir=work) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime required")

        # 1. Strict Clang C17 build and run
        clang_bin = tmp / "test_compat_clang"
        clang_built = _compile_and_link(clang, strict_flags, COMPAT_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(clang_ran.returncode == 0 and "compat_workflow_test: ok" in clang_ran.stdout,
               f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}")

        # 2. Strict GCC C17 + ASan/UBSan build and run
        gcc_bin = tmp / "test_compat_gcc_san"
        gcc_built = _compile_and_link(gcc, asan_flags, COMPAT_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(gcc_ran.returncode == 0 and "compat_workflow_test: ok" in gcc_ran.stdout,
               f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}")

        # 3. Behavioral mutation controls under GCC ASan/UBSan
        source = COMPAT_C.read_text(encoding="utf-8")
        mutants = _mutants(source)
        ensure(len(mutants) >= 12, f"expected >= 12 mutants, got {len(mutants)}")
        for label, mutated_source, expected_diag in mutants:
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(mutated_source, encoding="utf-8", newline="\n")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = _compile_and_link(gcc, asan_flags, mutant_c, mutant_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mutant_bin)], capture_output=True, text=True, timeout=60, check=False,
            )
            ensure(
                m_ran.returncode != 0 and expected_diag in m_ran.stderr,
                f"mutant survived or missed expected diagnostic ({label}): {m_ran.stderr or m_ran.stdout}",
            )


def cases() -> list[Case]:
    return [
        Case("compat_workflow_oracle", _compat_workflow_oracle, lane="any"),
        Case("compat_workflow_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("compat_workflow_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
