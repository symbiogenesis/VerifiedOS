# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracle and native C17 ASan/UBSan + Clang + mutation controls for resident-toolchain/."""

import hashlib
import hmac
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
RTC_DIR = ROOT / "resident-toolchain"
RTC_H = RTC_DIR / "include" / "vos_resident_tc.h"
RTC_C = RTC_DIR / "src" / "resident_tc.c"
RTC_TEST_C = RTC_DIR / "test" / "test_resident_tc.c"
RTC_README = RTC_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "ResidentToolchain.v"

ROUTE_INDEPENDENT_IMPL = 1
ROUTE_COMMERCIAL_GRANT = 2
ROUTE_DUAL_LICENSED_SUBSET = 3
ROUTE_NONCOMMERCIAL_ONLY = 4

DISP_CLEAN = 1
DISP_DELETED = 2
DISP_VERIFIED_HAL_OR_PROOF = 3
DISP_NAMED_SUBPORT = 4
DISP_UNSAFE_EXCEPTION = 5
DISP_UNRESOLVED_AMBIENT = 6

ROLE_TYPE_CHECKER = 0
ROLE_PROVER = 1
ROLE_COMPILER = 2
ROLE_COMPOSER = 3
ROLE_PACKAGE_BUILDER = 4

POOL_FREE = 0
POOL_BOUND = 1
POOL_QUIESCING = 2
POOL_REVOKED = 3
POOL_SWEEPING = 4
POOL_REUSABLE = 5

READING_A = 1
READING_B = 2

ROOT_RELOCATED = 1
ROOT_CLOSED = 2


@dataclass(frozen=True, slots=True)
class _OracleLicense:
    comp_id: int
    route: int
    read_at_incorporation: bool
    has_noncommercial_pass: bool
    has_commercial_grant: bool
    dual_subset_only: bool
    provides_required_backend: bool


@dataclass(frozen=True, slots=True)
class _OracleClosureUnit:
    unit_id: int
    unsafe_sites: int
    unsafe_hal_or_proof_ok: bool
    ambient_authority: bool
    has_filesystem: bool
    has_subprocess: bool
    has_host_allocator: bool
    disposition: int
    subport_id: int = 0
    subport_estimated: bool = False

    def has_host_assumption(self) -> bool:
        return self.has_filesystem or self.has_subprocess or self.has_host_allocator


@dataclass(frozen=True, slots=True)
class _OracleCompartment:
    comp_id: int
    role: int
    exec_over_own_output: bool = False
    sealing_auth: bool = False
    wiring_auth: bool = False
    store_consent_grant: bool = True


@dataclass(slots=True)
class _OraclePool:
    pool_id: int
    owner_id: int
    capacity_bytes: int
    low_threshold: int
    exhausted_threshold: int
    used_bytes: int = 0
    peak_bytes: int = 0
    lifecycle: int = POOL_FREE


@dataclass(frozen=True, slots=True)
class _OracleActivation:
    pass_id: int
    role: int
    pool_id: int
    step_budget: int
    steps_used: int
    alloc_bytes: int
    pass_peak_bytes: int
    resumable: bool = True
    checkpoint_saved: bool = False


@dataclass(frozen=True, slots=True)
class _OracleSharingProof:
    disjoint_live_ranges: bool
    frame_or_region_proven: bool
    assumed_correlation_only: bool
    temporal_barrier_ok: bool

    def can_share(self) -> bool:
        return (
            self.disjoint_live_ranges
            and self.frame_or_region_proven
            and not self.assumed_correlation_only
            and self.temporal_barrier_ok
        )


@dataclass(frozen=True, slots=True)
class _OracleResidencySpec:
    reading: int
    ordinary_bytes: int
    compiler_peak_bytes: int
    prover_peak_bytes: int
    first_class_cap_bytes: int
    sharing: _OracleSharingProof


@dataclass(frozen=True, slots=True)
class _OracleBuildReceipt:
    source_digest: bytes
    switch_digest: bytes
    artifact_digest: bytes
    tal_admitted: bool
    cic_admitted: bool
    ddc_checked: bool
    rot_measured: bool
    root_status: int

    def receipt_digest(self) -> bytes:
        payload = (
            b"VOSRTCR1"
            + self.source_digest
            + self.switch_digest
            + self.artifact_digest
            + (1 if self.tal_admitted else 0).to_bytes(4, "little")
            + (1 if self.cic_admitted else 0).to_bytes(4, "little")
            + (1 if self.ddc_checked else 0).to_bytes(4, "little")
            + (1 if self.rot_measured else 0).to_bytes(4, "little")
            + self.root_status.to_bytes(4, "little")
        )
        return hashlib.sha256(payload).digest()


@dataclass(slots=True)
class _OracleCoordinator:
    running_generation: int
    last_peak_bytes: int = 0
    admitted_runs: int = 0

    def screen_license(self, lic: _OracleLicense) -> str:
        if not lic.read_at_incorporation:
            return "LICENSE_UNREAD"
        if lic.route == ROUTE_INDEPENDENT_IMPL:
            return "NONCOMMERCIAL_NO_GRANT" if lic.has_noncommercial_pass else "OK"
        if lic.route == ROUTE_COMMERCIAL_GRANT:
            return "OK" if lic.has_commercial_grant else "MISSING_COMMERCIAL_GRANT"
        if lic.route == ROUTE_DUAL_LICENSED_SUBSET:
            if not lic.dual_subset_only or lic.has_noncommercial_pass or lic.provides_required_backend:
                return "OUTSIDE_DUAL_SUBSET"
            return "OK"
        if lic.route == ROUTE_NONCOMMERCIAL_ONLY:
            return "NONCOMMERCIAL_NO_GRANT"
        return "INVALID_ARG"

    def audit_closure(self, unit: _OracleClosureUnit) -> tuple[str, int]:
        if unit.ambient_authority:
            return "AMBIENT_AUTHORITY", 0
        if unit.disposition == DISP_UNSAFE_EXCEPTION:
            return "UNSAFE_EXCEPTION", 0
        if unit.disposition == DISP_UNRESOLVED_AMBIENT:
            return "AMBIENT_AUTHORITY", 0
        if unit.disposition == DISP_CLEAN:
            if unit.unsafe_sites != 0:
                return "UNCOVERED_UNSAFE", 0
            if unit.has_host_assumption():
                return "UNRESOLVED_HOST_ASSUMP", 0
            return "OK", 0
        if unit.disposition == DISP_DELETED:
            if unit.unsafe_sites != 0 and not unit.unsafe_hal_or_proof_ok:
                return "UNCOVERED_UNSAFE", 0
            return "OK", 0
        if unit.disposition == DISP_VERIFIED_HAL_OR_PROOF:
            if not unit.unsafe_hal_or_proof_ok:
                return "UNCOVERED_UNSAFE", 0
            if unit.has_host_assumption():
                return "UNRESOLVED_HOST_ASSUMP", 0
            return "OK", 0
        if unit.disposition == DISP_NAMED_SUBPORT:
            if unit.unsafe_sites != 0 and not unit.unsafe_hal_or_proof_ok:
                return "UNCOVERED_UNSAFE", 0
            if not unit.has_host_assumption():
                return "UNRESOLVED_HOST_ASSUMP", 0
            if unit.subport_id == 0 or not unit.subport_estimated:
                return "UNESTIMATED_SUBPORT", 0
            return "OK", unit.subport_id
        return "INVALID_ARG", 0

    def check_residency(self, spec: _OracleResidencySpec) -> tuple[str, int]:
        pool_charge = (
            max(spec.compiler_peak_bytes, spec.prover_peak_bytes)
            if spec.sharing.can_share()
            else spec.compiler_peak_bytes + spec.prover_peak_bytes
        )
        total = pool_charge if spec.reading == READING_A else spec.ordinary_bytes + pool_charge
        if total > spec.first_class_cap_bytes:
            return "RESIDENCY_EXCEEDED", total
        return "OK", total

    def compare_receipts(
        self, host: _OracleBuildReceipt, dev: _OracleBuildReceipt
    ) -> tuple[str, str]:
        if host.root_status != ROOT_RELOCATED or dev.root_status != ROOT_RELOCATED:
            return "CLOSED_DEBRUIJN_CLAIM", "CLOSED_BOOTSTRAP_CLAIMED"
        if not host.tal_admitted or not host.cic_admitted:
            return "BOOTSTRAP_DIVERGED", "HOST_ADMISSION_REFUSED"
        if not dev.tal_admitted or not dev.cic_admitted:
            return "BOOTSTRAP_DIVERGED", "DEVICE_ADMISSION_REFUSED"
        if not hmac.compare_digest(host.source_digest, dev.source_digest):
            return "BOOTSTRAP_DIVERGED", "SOURCE_MISMATCH"
        if not hmac.compare_digest(host.switch_digest, dev.switch_digest):
            return "BOOTSTRAP_DIVERGED", "SWITCH_MISMATCH"
        if not hmac.compare_digest(host.artifact_digest, dev.artifact_digest):
            return "BOOTSTRAP_DIVERGED", "ARTIFACT_MISMATCH"
        if not (host.ddc_checked and dev.ddc_checked and host.rot_measured and dev.rot_measured):
            return "BOOTSTRAP_DIVERGED", "DDC_OR_ROT_INCOMPLETE"
        return "OK", "REPRODUCED_RELOCATED"

    def run_cycle(
        self,
        licenses: tuple[_OracleLicense, ...],
        closure: tuple[_OracleClosureUnit, ...],
        compartments: tuple[_OracleCompartment, ...],
        pool: _OraclePool,
        activations: tuple[_OracleActivation, ...],
        residency: _OracleResidencySpec,
        host_receipt: _OracleBuildReceipt,
        dev_receipt: _OracleBuildReceipt,
    ) -> tuple[str, str]:
        for lic in licenses:
            st = self.screen_license(lic)
            if st != "OK":
                return st, ""
        for unit in closure:
            st, sp_id = self.audit_closure(unit)
            if st != "OK":
                return st, ""
            if sp_id != 0:
                return "UNRESOLVED_HOST_ASSUMP", ""
        has_checker = False
        min_rank = 0
        for comp in compartments:
            if comp.exec_over_own_output:
                return "EXEC_OWN_OUTPUT", ""
            if comp.sealing_auth or comp.wiring_auth or not comp.store_consent_grant:
                return "FORBIDDEN_AUTH", ""
            if comp.role == ROLE_TYPE_CHECKER:
                has_checker = True
            if comp.role < min_rank:
                return "ORDER_VIOLATION", ""
            min_rank = comp.role
        if not has_checker:
            return "ORDER_VIOLATION", ""

        res_st, _ = self.check_residency(residency)
        if res_st != "OK":
            return res_st, ""

        staged = replace(pool)
        max_peak = 0
        for act in activations:
            if staged.pool_id != act.pool_id:
                return "WRONG_POOL", ""
            if staged.lifecycle not in (POOL_FREE, POOL_BOUND, POOL_REUSABLE):
                return "POOL_LIFECYCLE", ""
            if not act.resumable:
                return "NOT_RESUMABLE", ""
            if act.steps_used > act.step_budget:
                return "STEP_BUDGET_EXCEEDED", ""
            next_used = staged.used_bytes + act.alloc_bytes
            cand_peak = max(next_used, act.pass_peak_bytes)
            if staged.exhausted_threshold > staged.capacity_bytes or cand_peak > staged.exhausted_threshold:
                return "CAPACITY_EXHAUSTED", ""
            staged.used_bytes = next_used
            staged.peak_bytes = max(staged.peak_bytes, cand_peak)
            staged.lifecycle = POOL_BOUND
            max_peak = max(max_peak, cand_peak)
        if max_peak > residency.compiler_peak_bytes:
            return "RESIDENCY_EXCEEDED", ""

        verdict, cause = self.compare_receipts(host_receipt, dev_receipt)
        if verdict != "OK":
            return verdict, cause

        self.running_generation += 1
        self.last_peak_bytes = max(staged.peak_bytes, max_peak)
        self.admitted_runs += 1
        return "OK", cause


def _digest(tag: int) -> bytes:
    return bytes((tag ^ (i * 5 + 3)) & 0xFF for i in range(32))


def _oracle_resident_toolchain() -> None:
    """Exercise positive resident toolchain admission/reproduction and all failure controls."""
    src_digest = _digest(0x11)
    sw_digest = _digest(0x22)
    code = bytes((0x40 + i) & 0xFF for i in range(32))
    art_digest = hashlib.sha256(
        b"VOSRTCA1"
        + (1).to_bytes(8, "little")
        + len(code).to_bytes(4, "little")
        + src_digest
        + code
    ).digest()

    licenses = (
        _OracleLicense(1, ROUTE_INDEPENDENT_IMPL, True, False, False, False, True),
        _OracleLicense(2, ROUTE_COMMERCIAL_GRANT, True, True, True, False, True),
        _OracleLicense(3, ROUTE_DUAL_LICENSED_SUBSET, True, False, False, True, False),
    )
    closure = (
        _OracleClosureUnit(10, 0, True, False, False, False, False, DISP_CLEAN),
        _OracleClosureUnit(11, 2, True, False, False, False, False, DISP_VERIFIED_HAL_OR_PROOF),
        _OracleClosureUnit(12, 0, True, False, True, True, True, DISP_DELETED),
    )
    compartments = (
        _OracleCompartment(101, ROLE_TYPE_CHECKER),
        _OracleCompartment(102, ROLE_PROVER),
        _OracleCompartment(103, ROLE_COMPILER),
    )
    pool = _OraclePool(1, 103, 64000, 48000, 60000)
    activations = (
        _OracleActivation(1, ROLE_TYPE_CHECKER, 1, 500, 120, 4096, 8192, True, True),
        _OracleActivation(2, ROLE_COMPILER, 1, 2000, 1500, 12288, 24576, True, False),
    )
    sharing_ok = _OracleSharingProof(True, True, False, True)
    residency = _OracleResidencySpec(READING_A, 40000, 24576, 38000, 60000, sharing_ok)
    host_rec = _OracleBuildReceipt(src_digest, sw_digest, art_digest, True, True, True, True, ROOT_RELOCATED)
    dev_rec = _OracleBuildReceipt(src_digest, sw_digest, art_digest, True, True, True, True, ROOT_RELOCATED)

    coord = _OracleCoordinator(running_generation=5)
    st, cause = coord.run_cycle(
        licenses, closure, compartments, pool, activations, residency, host_rec, dev_rec
    )
    ensure(
        st == "OK" and cause == "REPRODUCED_RELOCATED" and coord.running_generation == 6
        and coord.last_peak_bytes == 24576,
        f"positive oracle cycle failed: {st} {cause}",
    )

    # Named estimated subport succeeds at audit time, blocks active runnable cycle.
    sp_unit = _OracleClosureUnit(13, 0, True, False, True, False, True, DISP_NAMED_SUBPORT, 77, True)
    sp_st, sp_id = coord.audit_closure(sp_unit)
    ensure(sp_st == "OK" and sp_id == 77, "named estimated subport audit failed")

    # Adverse license screening controls
    ensure(
        coord.run_cycle(
            (replace(licenses[0], read_at_incorporation=False), *licenses[1:]),
            closure, compartments, pool, activations, residency, host_rec, dev_rec,
        )[0] == "LICENSE_UNREAD",
        "unread license accepted",
    )
    ensure(
        coord.run_cycle(
            (licenses[0], replace(licenses[1], route=ROUTE_NONCOMMERCIAL_ONLY, has_commercial_grant=False), licenses[2]),
            closure, compartments, pool, activations, residency, host_rec, dev_rec,
        )[0] == "NONCOMMERCIAL_NO_GRANT",
        "noncommercial pass without grant accepted",
    )
    ensure(
        coord.run_cycle(
            (*licenses[:2], replace(licenses[2], dual_subset_only=False)),
            closure, compartments, pool, activations, residency, host_rec, dev_rec,
        )[0] == "OUTSIDE_DUAL_SUBSET",
        "outside dual-licensed subset accepted",
    )

    # Adverse closure audit controls
    ensure(
        coord.run_cycle(
            licenses, (replace(closure[0], disposition=DISP_UNSAFE_EXCEPTION), *closure[1:]),
            compartments, pool, activations, residency, host_rec, dev_rec,
        )[0] == "UNSAFE_EXCEPTION",
        "unsafe exception accepted",
    )
    ensure(
        coord.run_cycle(
            licenses, (replace(closure[0], ambient_authority=True), *closure[1:]),
            compartments, pool, activations, residency, host_rec, dev_rec,
        )[0] == "AMBIENT_AUTHORITY",
        "ambient authority accepted",
    )
    ensure(
        coord.run_cycle(
            licenses, (replace(closure[0], has_filesystem=True), *closure[1:]),
            compartments, pool, activations, residency, host_rec, dev_rec,
        )[0] == "UNRESOLVED_HOST_ASSUMP",
        "unresolved host assumption accepted",
    )

    # Adverse authority and ordering controls
    ensure(
        coord.run_cycle(
            licenses, closure, (*compartments[:2], replace(compartments[2], exec_over_own_output=True)),
            pool, activations, residency, host_rec, dev_rec,
        )[0] == "EXEC_OWN_OUTPUT",
        "execute over own output accepted",
    )
    ensure(
        coord.run_cycle(
            licenses, closure, (compartments[2], compartments[0], compartments[1]),
            pool, activations, residency, host_rec, dev_rec,
        )[0] == "ORDER_VIOLATION",
        "compiler before type-checker accepted",
    )

    # Adverse sharing and ReadingA vs ReadingB controls
    ensure(
        coord.run_cycle(
            licenses, closure, compartments, pool, activations,
            replace(residency, sharing=replace(sharing_ok, assumed_correlation_only=True)),
            host_rec, dev_rec,
        )[0] == "RESIDENCY_EXCEEDED",
        "assumed correlation pool sharing accepted",
    )
    ensure(
        coord.run_cycle(
            licenses, closure, compartments, pool, activations,
            replace(residency, reading=READING_B),
            host_rec, dev_rec,
        )[0] == "RESIDENCY_EXCEEDED",
        "ReadingB fit accepted above capacity",
    )

    # Adverse pool exhaustion and step budget exhaustion preserve running generation
    saved_gen = coord.running_generation
    ensure(
        coord.run_cycle(
            licenses, closure, compartments, pool,
            (activations[0], replace(activations[1], pass_peak_bytes=60001)),
            replace(residency, compiler_peak_bytes=60001, first_class_cap_bytes=100000),
            host_rec, dev_rec,
        )[0] == "CAPACITY_EXHAUSTED" and coord.running_generation == saved_gen,
        "pool exhaustion accepted or mutated running generation",
    )
    ensure(
        coord.run_cycle(
            licenses, closure, compartments, pool,
            (activations[0], replace(activations[1], steps_used=2001)),
            residency, host_rec, dev_rec,
        )[0] == "STEP_BUDGET_EXCEEDED" and coord.running_generation == saved_gen,
        "step exhaustion accepted or mutated running generation",
    )

    # Adverse bootstrap divergence and Closed De Bruijn claim
    ensure(
        coord.run_cycle(
            licenses, closure, compartments, pool, activations, residency,
            host_rec, replace(dev_rec, artifact_digest=_digest(0x99)),
        ) == ("BOOTSTRAP_DIVERGED", "ARTIFACT_MISMATCH"),
        "diverged bootstrap artifact accepted",
    )
    ensure(
        coord.run_cycle(
            licenses, closure, compartments, pool, activations, residency,
            host_rec, replace(dev_rec, root_status=ROOT_CLOSED),
        ) == ("CLOSED_DEBRUIJN_CLAIM", "CLOSED_BOOTSTRAP_CLAIMED"),
        "closed De Bruijn root claim accepted",
    )


def _surface_and_proof_contract() -> None:
    """Verify SPDX headers, GC-free C17 surface, and ResidentToolchain.v theorem/witness surface."""
    for path in (RTC_H, RTC_C, RTC_TEST_C, RTC_README, PROOFS_V):
        ensure(path.is_file(), f"missing resident-toolchain artifact: {path}")

    for c_path in (RTC_H, RTC_C, RTC_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(
            first_line == "// SPDX-License-Identifier: Apache-2.0",
            f"missing // SPDX header in {c_path}",
        )
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden heap allocator {forbidden} in {c_path}")

    c_src = RTC_C.read_text(encoding="utf-8")
    for fn in (
        "vos_rtc_state_init",
        "vos_rtc_compute_artifact_digest",
        "vos_rtc_compute_receipt_digest",
        "vos_rtc_screen_license",
        "vos_rtc_audit_closure",
        "vos_rtc_check_compartment_caps",
        "vos_rtc_check_smallest_loop_first",
        "vos_rtc_pools_can_share",
        "vos_rtc_toolchain_pool_charge",
        "vos_rtc_check_residency",
        "vos_rtc_run_activation",
        "vos_rtc_compare_bootstrap_receipts",
        "vos_rtc_run_cycle",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    v_first = v_src.splitlines()[0] if v_src.splitlines() else ""
    ensure(
        v_first == "(* SPDX-License-Identifier: Apache-2.0 *)",
        "missing SPDX header in ResidentToolchain.v",
    )
    for sym in (
        "license_unread_at_incorporation_refused",
        "noncommercial_pass_without_grant_refused",
        "dual_licensed_subset_refuses_outside_files_or_backend_claim",
        "unsafe_exception_always_refused",
        "ambient_authority_always_refused",
        "unresolved_host_assumption_must_shed_or_become_estimated_subport",
        "compartment_exec_own_output_or_sealing_or_wiring_refused",
        "smallest_loop_first_refuses_compiler_before_checker",
        "pool_exhaustion_refuses_and_preserves_running_generation",
        "step_budget_exceeded_refuses_and_preserves_running_generation",
        "activation_success_keeps_peak_within_exhausted_threshold",
        "assumed_correlation_cannot_share_pools",
        "missing_disjoint_range_or_frame_proof_charges_sum",
        "reading_b_fit_implies_reading_a_fit",
        "reproduced_keeps_debruijn_root_relocated",
        "closed_bootstrap_claim_always_refused",
        "artifact_mismatch_produces_diverged_finding",
        "refused_toolchain_run_preserves_running_generation",
        "admitted_toolchain_run_establishes_all_gates",
        "positive_resident_toolchain_admits_and_reproduces",
        "adverse_license_refusals",
        "adverse_closure_refusals",
        "adverse_order_authority_sharing_and_reading_refusals",
        "adverse_budget_exhaustion_and_bootstrap_refusals",
        "witness_ComponentLicense",
        "witness_ClosureUnit",
        "witness_CompartmentCaps",
        "witness_BoundedPool",
        "witness_PassActivation",
        "witness_PoolSharingProof",
        "witness_BuildReceipt",
        "witness_ResidencySpec",
        "witness_ResidentToolchainReq",
        "witness_ResidentToolchainState",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in ResidentToolchain.v")

    v_clean = strip_comments(v_src)
    for banned in (
        "Admitted",
        "admit",
        "Axiom",
        "Parameter",
        "Conjecture",
        "CoInductive",
        "CoFixpoint",
        "cofix",
        "Section",
    ):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in ResidentToolchain.v",
        )
    ensure(
        re.search(r"\bModule\s+Type\b", v_clean) is None,
        "forbidden Module Type in ResidentToolchain.v",
    )


def _supports_flags(compiler: str, flags: list[str], scratch: Path) -> bool:
    probe_c = scratch / "_probe.c"
    probe_bin = scratch / "_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    built = subprocess.run(
        [compiler, *flags, str(probe_c), "-o", str(probe_bin)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if built.returncode != 0:
        return False
    ran = subprocess.run([str(probe_bin)], capture_output=True, text=True, timeout=30, check=False)
    return ran.returncode == 0


def _compile_and_link(
    compiler: str, flags: list[str], src_c: Path, out_bin: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            compiler,
            *flags,
            f"-I{RTC_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(src_c),
            str(CRYPTO_SOURCE),
            str(RTC_TEST_C),
            "-o",
            str(out_bin),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _mutants(source: str) -> list[tuple[str, str, str]]:
    def replaced(before: str, after: str, label: str) -> str:
        ensure(source.count(before) == 1, f"mutant anchor missing or non-unique ({label}): {before!r}")
        return source.replace(before, after, 1)

    return [
        (
            "accept-unread-license",
            replaced(
                "    if (lic->read_at_incorporation == 0u) {\n"
                "        return VOS_RTC_ERR_LICENSE_UNREAD;\n"
                "    }",
                "    if (0 && lic->read_at_incorporation == 0u) {\n"
                "        return VOS_RTC_ERR_LICENSE_UNREAD;\n"
                "    }",
                "accept-unread-license",
            ),
            "unread license accepted",
        ),
        (
            "accept-noncommercial-no-grant",
            replaced(
                "    if (lic->route == VOS_RTC_ROUTE_NONCOMMERCIAL_ONLY) {\n"
                "        return VOS_RTC_ERR_NONCOMMERCIAL_NO_GRANT;\n"
                "    }",
                "    if (lic->route == VOS_RTC_ROUTE_NONCOMMERCIAL_ONLY) {\n"
                "        return VOS_RTC_OK;\n"
                "    }",
                "accept-noncommercial-no-grant",
            ),
            "noncommercial pass without grant accepted",
        ),
        (
            "accept-outside-dual-subset",
            replaced(
                "        if (lic->dual_subset_only == 0u ||\n"
                "            lic->has_noncommercial_pass != 0u ||\n"
                "            lic->provides_required_backend != 0u) {\n"
                "            return VOS_RTC_ERR_OUTSIDE_DUAL_SUBSET;\n"
                "        }",
                "        if (0 && (lic->dual_subset_only == 0u ||\n"
                "                  lic->has_noncommercial_pass != 0u ||\n"
                "                  lic->provides_required_backend != 0u)) {\n"
                "            return VOS_RTC_ERR_OUTSIDE_DUAL_SUBSET;\n"
                "        }",
                "accept-outside-dual-subset",
            ),
            "outside dual-licensed subset accepted",
        ),
        (
            "accept-unsafe-exception",
            replaced(
                "    if (unit->disposition == VOS_RTC_DISP_UNSAFE_EXCEPTION) {\n"
                "        return VOS_RTC_ERR_UNSAFE_EXCEPTION;\n"
                "    }",
                "    if (unit->disposition == VOS_RTC_DISP_UNSAFE_EXCEPTION) {\n"
                "        return VOS_RTC_OK;\n"
                "    }",
                "accept-unsafe-exception",
            ),
            "unsafe exception accepted",
        ),
        (
            "accept-ambient-authority",
            replaced(
                "    if (unit->ambient_authority != 0u) {\n"
                "        return VOS_RTC_ERR_AMBIENT_AUTHORITY;\n"
                "    }",
                "    if (0 && unit->ambient_authority != 0u) {\n"
                "        return VOS_RTC_ERR_AMBIENT_AUTHORITY;\n"
                "    }",
                "accept-ambient-authority",
            ),
            "ambient authority accepted",
        ),
        (
            "accept-unresolved-host-assumption",
            replaced(
                "        if (unit_has_host_assumption(unit)) {\n"
                "            return VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP;\n"
                "        }\n"
                "        return VOS_RTC_OK;\n"
                "    }\n"
                "    if (unit->disposition == VOS_RTC_DISP_DELETED)",
                "        if (0 && unit_has_host_assumption(unit)) {\n"
                "            return VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP;\n"
                "        }\n"
                "        return VOS_RTC_OK;\n"
                "    }\n"
                "    if (unit->disposition == VOS_RTC_DISP_DELETED)",
                "accept-unresolved-host-assumption",
            ),
            "unresolved host assumption accepted",
        ),
        (
            "accept-exec-own-output",
            replaced(
                "    if (caps->exec_over_own_output != 0u) {\n"
                "        return VOS_RTC_ERR_EXEC_OWN_OUTPUT;\n"
                "    }",
                "    if (0 && caps->exec_over_own_output != 0u) {\n"
                "        return VOS_RTC_ERR_EXEC_OWN_OUTPUT;\n"
                "    }",
                "accept-exec-own-output",
            ),
            "execute over own output accepted",
        ),
        (
            "accept-compiler-before-checker",
            replaced(
                "        if (role < min_rank) {\n"
                "            return VOS_RTC_ERR_ORDER_VIOLATION;\n"
                "        }",
                "        if (0 && role < min_rank) {\n"
                "            return VOS_RTC_ERR_ORDER_VIOLATION;\n"
                "        }",
                "accept-compiler-before-checker",
            ),
            "compiler before type-checker accepted",
        ),
        (
            "share-on-assumed-correlation",
            replaced(
                "    if (proof->disjoint_live_ranges == 0u ||\n"
                "        proof->frame_or_region_proven == 0u ||\n"
                "        proof->assumed_correlation_only != 0u ||\n"
                "        proof->temporal_barrier_ok == 0u) {",
                "    if (proof->disjoint_live_ranges == 0u ||\n"
                "        proof->frame_or_region_proven == 0u ||\n"
                "        proof->temporal_barrier_ok == 0u) {",
                "share-on-assumed-correlation",
            ),
            "assumed correlation allowed pool sharing",
        ),
        (
            "reading-b-drops-ordinary-bytes",
            replaced(
                "    if (spec->reading == VOS_RTC_READING_B) {\n"
                "        if (spec->ordinary_bytes > UINT32_MAX - pool_charge) {\n"
                "            return VOS_RTC_ERR_RESIDENCY_EXCEEDED;\n"
                "        }\n"
                "        total_charge = spec->ordinary_bytes + pool_charge;\n"
                "    }",
                "    if (spec->reading == VOS_RTC_READING_B) {\n"
                "        total_charge = pool_charge;\n"
                "    }",
                "reading-b-drops-ordinary-bytes",
            ),
            "ReadingB ignored ordinary bytes",
        ),
        (
            "accept-pool-exhaustion",
            replaced(
                "    if (cand_peak > pool->exhausted_threshold) {\n"
                "        return VOS_RTC_ERR_CAPACITY_EXHAUSTED;\n"
                "    }",
                "    if (0 && cand_peak > pool->exhausted_threshold) {\n"
                "        return VOS_RTC_ERR_CAPACITY_EXHAUSTED;\n"
                "    }",
                "accept-pool-exhaustion",
            ),
            "pool exhaustion accepted",
        ),
        (
            "accept-step-budget-exceeded",
            replaced(
                "    if (act->steps_used > act->step_budget) {\n"
                "        return VOS_RTC_ERR_STEP_BUDGET_EXCEEDED;\n"
                "    }",
                "    if (0 && act->steps_used > act->step_budget) {\n"
                "        return VOS_RTC_ERR_STEP_BUDGET_EXCEEDED;\n"
                "    }",
                "accept-step-budget-exceeded",
            ),
            "step budget exceeded accepted",
        ),
        (
            "ignore-artifact-divergence",
            replaced(
                "    if (!equal_hashes(&host->artifact_digest, &dev->artifact_digest)) {\n"
                "        out_verdict->cause = VOS_RTC_CAUSE_ARTIFACT_MISMATCH;\n"
                "        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;\n"
                "    }",
                "    if (0 && !equal_hashes(&host->artifact_digest, &dev->artifact_digest)) {\n"
                "        out_verdict->cause = VOS_RTC_CAUSE_ARTIFACT_MISMATCH;\n"
                "        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;\n"
                "    }",
                "ignore-artifact-divergence",
            ),
            "diverged bootstrap artifact accepted",
        ),
        (
            "accept-closed-debruijn-claim",
            replaced(
                "    if (host->root_status != VOS_RTC_ROOT_RELOCATED ||\n"
                "        dev->root_status != VOS_RTC_ROOT_RELOCATED) {\n"
                "        out_verdict->cause = VOS_RTC_CAUSE_CLOSED_BOOTSTRAP_CLAIMED;\n"
                "        out_verdict->root_status = VOS_RTC_ROOT_CLOSED;\n"
                "        return VOS_RTC_ERR_CLOSED_DEBRUIJN_CLAIM;\n"
                "    }",
                "    if (0 && (host->root_status != VOS_RTC_ROOT_RELOCATED ||\n"
                "              dev->root_status != VOS_RTC_ROOT_RELOCATED)) {\n"
                "        out_verdict->cause = VOS_RTC_CAUSE_CLOSED_BOOTSTRAP_CLAIMED;\n"
                "        out_verdict->root_status = VOS_RTC_ROOT_CLOSED;\n"
                "        return VOS_RTC_ERR_CLOSED_DEBRUIJN_CLAIM;\n"
                "    }",
                "accept-closed-debruijn-claim",
            ),
            "closed De Bruijn root claim accepted",
        ),
    ]


def _native_c_and_mutation_controls() -> None:
    """Compile and run resident-toolchain C17 tests under Clang + GCC ASan/UBSan and kill all mutants."""
    if sys.platform == "win32":
        return

    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None, "clang is required in Linux guest")
    ensure(gcc is not None, "gcc is required in Linux guest")
    if clang is None or gcc is None:
        return

    strict_flags = [
        "-std=c17",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wstrict-prototypes",
        "-pedantic",
    ]
    asan_flags = [*strict_flags, "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]

    work = toolenv.environment(ROOT, sys.platform).parent / "c-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rtc-", dir=work) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime required")

        # 1. Strict Clang C17 build and run
        clang_bin = tmp / "test_rtc_clang"
        clang_built = _compile_and_link(clang, strict_flags, RTC_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, timeout=60, check=False
        )
        ensure(
            clang_ran.returncode == 0 and "resident_tc_test: ok" in clang_ran.stdout,
            f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}",
        )

        # 2. Strict GCC C17 + ASan/UBSan build and run
        gcc_bin = tmp / "test_rtc_gcc_san"
        gcc_built = _compile_and_link(gcc, asan_flags, RTC_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, timeout=60, check=False
        )
        ensure(
            gcc_ran.returncode == 0 and "resident_tc_test: ok" in gcc_ran.stdout,
            f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}",
        )

        # 3. Behavioral mutation controls under GCC ASan/UBSan
        source = RTC_C.read_text(encoding="utf-8")
        mutants = _mutants(source)
        ensure(len(mutants) >= 12, f"expected >= 12 mutants, got {len(mutants)}")
        for label, mutated_source, expected_diag in mutants:
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(mutated_source, encoding="utf-8", newline="\n")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = _compile_and_link(gcc, asan_flags, mutant_c, mutant_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mutant_bin)], capture_output=True, text=True, timeout=60, check=False
            )
            ensure(
                m_ran.returncode != 0 and expected_diag in m_ran.stderr,
                f"mutant survived or missed expected diagnostic ({label}): {m_ran.stderr or m_ran.stdout}",
            )


def cases() -> list[Case]:
    return [
        Case("resident_toolchain_oracle", _oracle_resident_toolchain, lane="any"),
        Case("resident_toolchain_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("resident_toolchain_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
