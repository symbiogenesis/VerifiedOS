# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracle and native C17 ASan/UBSan + Clang + mutation controls for device-generation/."""

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
DGEN_DIR = ROOT / "device-generation"
DGEN_H = DGEN_DIR / "include" / "vos_device_gen.h"
DGEN_C = DGEN_DIR / "src" / "device_gen.c"
DGEN_TEST_C = DGEN_DIR / "test" / "test_device_gen.c"
DGEN_README = DGEN_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "DeviceGeneration.v"

ORIGIN_LOCAL_AUTHORED = 1
ORIGIN_FETCHED_LOGGED = 2
MODE_NORMAL = 0
MODE_COMPOSITION = 1


@dataclass(frozen=True, slots=True)
class _OracleContext:
    spec_version: int = 1
    model_version: int = 1
    checker_id: int = 2
    tier: int = 2
    policy_epoch: int = 1
    resource_epoch: int = 1

    def encode(self) -> bytes:
        return b"".join(
            v.to_bytes(8, "little")
            for v in (
                self.spec_version,
                self.model_version,
                self.checker_id,
                self.tier,
                self.policy_epoch,
                self.resource_epoch,
            )
        )


@dataclass(frozen=True, slots=True)
class _OracleClosureMember:
    member_id: int
    origin: int
    has_publisher: bool
    logged_in_checkpoint: bool = False
    consistent_with_pin: bool = False
    inclusion_ok: bool = False


@dataclass(frozen=True, slots=True)
class _OraclePackage:
    pkg_id: int
    is_base_image: bool
    locally_composed: bool
    has_publisher: bool
    package_logged: bool
    source_digest: bytes
    contract_digest: bytes
    code_bytes: bytes
    init_digest: bytes
    proof_digest: bytes
    expected_base_digest: bytes
    proof_steps: int
    proof_workset_bytes: int
    proof_ok: bool
    closure: tuple[_OracleClosureMember, ...]

    @property
    def code_digest(self) -> bytes:
        return hashlib.sha256(self.code_bytes).digest()

    def artifact_digest(self, ctx: _OracleContext) -> bytes:
        payload = (
            b"VOSDGENP"
            + self.pkg_id.to_bytes(8, "little")
            + (1 if self.is_base_image else 0).to_bytes(4, "little")
            + self.source_digest
            + self.contract_digest
            + self.code_digest
            + self.init_digest
            + self.proof_digest
            + ctx.encode()
        )
        return hashlib.sha256(payload).digest()


@dataclass(frozen=True, slots=True)
class _OracleCheckedEntry:
    pkg_id: int
    artifact_digest: bytes
    source_digest: bytes
    contract_digest: bytes
    proof_digest: bytes
    context: _OracleContext


@dataclass(frozen=True, slots=True)
class _OraclePrompt:
    roster_hash: bytes
    gen_root: bytes
    nonce: int
    roster_name: bytes


@dataclass(slots=True)
class _OracleConsent:
    credential_present: bool
    user_consented: bool
    prompt: _OraclePrompt
    consumed: bool = False


@dataclass(slots=True)
class _OracleDevice:
    key_id: int
    signing_key: bytes
    checked_set_key: bytes
    ctx: _OracleContext
    live_root: bytes
    live_version: int
    floor: int
    step_budget: int = 10000
    workset_budget: int = 65536
    enrolled: bool = True
    exportable: bool = False
    composer_holds_key: bool = False
    composer_has_mint_cap: bool = False
    mode: int = MODE_NORMAL
    priv_active: bool = False
    used_nonces: set[int] = field(default_factory=set)
    checked_entries: tuple[_OracleCheckedEntry, ...] = ()
    checked_hmac: bytes = b""
    retained_root: bytes | None = None
    retained_version: int = 0

    def __post_init__(self) -> None:
        if not self.checked_hmac:
            self.checked_hmac = self.seal_checked_set(self.checked_entries)

    def seal_checked_set(self, entries: tuple[_OracleCheckedEntry, ...]) -> bytes:
        buf = bytearray(b"VOSDGENC" + len(entries).to_bytes(4, "little"))
        for entry in entries:
            buf += entry.pkg_id.to_bytes(8, "little")
            buf += entry.artifact_digest
            buf += entry.source_digest
            buf += entry.contract_digest
            buf += entry.proof_digest
            buf += entry.context.encode()
        return hmac.new(self.checked_set_key, bytes(buf), hashlib.sha256).digest()

    def export_key(self) -> str:
        return "EXPORT_FORBIDDEN"

    def trusted_path_mint(
        self,
        roster_hash: bytes,
        gen_root: bytes,
        consent: _OracleConsent | None,
    ) -> tuple[str, bytes | None]:
        if self.exportable:
            return "EXPORT_FORBIDDEN", None
        if not self.enrolled:
            return "INVALID_ARG", None
        if self.composer_holds_key or self.composer_has_mint_cap:
            return "COMPOSER_PRIVILEGED", None
        if consent is None or not consent.user_consented:
            return "NO_CONSENT", None
        if not consent.credential_present:
            return "CREDENTIAL_ABSENT", None
        if consent.consumed or consent.prompt.nonce in self.used_nonces:
            return "NONCE_REPLAY", None
        if not consent.prompt.roster_name or len(consent.prompt.roster_name) > 64:
            return "CONSENT_MISMATCH", None
        if (
            not hmac.compare_digest(consent.prompt.roster_hash, roster_hash)
            or not hmac.compare_digest(consent.prompt.gen_root, gen_root)
        ):
            return "CONSENT_MISMATCH", None
        msg = (
            b"VOSDGENM"
            + self.key_id.to_bytes(8, "little")
            + roster_hash
            + gen_root
            + consent.prompt.nonce.to_bytes(8, "little")
        )
        mac = hmac.new(self.signing_key, msg, hashlib.sha256).digest()
        consent.consumed = True
        self.used_nonces.add(consent.prompt.nonce)
        return "OK", mac

    def compose_and_admit(
        self,
        packages: tuple[_OraclePackage, ...],
        version: int,
        declared_floor: int,
        consent: _OracleConsent | None,
        *,
        tal_fresh: bool = True,
        wiring_fresh: bool = True,
        global_ok: bool = True,
        cic_available: bool = True,
        mode_cert: bool = True,
        mode_guard: bool = True,
        mode_dwell: bool = True,
        mode_recovery: bool = True,
    ) -> tuple[str, dict[str, int] | None]:
        if self.mode != MODE_NORMAL or self.priv_active:
            self.mode = MODE_NORMAL
            self.priv_active = False
            return "MODE_LOCKED", None
        if not (mode_cert and mode_guard and mode_dwell and mode_recovery):
            return "MODE_CERT", None
        self.mode = MODE_COMPOSITION
        self.priv_active = True
        try:
            if version < self.floor or version < declared_floor:
                return "ROLLBACK_FLOOR", None
            expected_hmac = self.seal_checked_set(self.checked_entries)
            if not hmac.compare_digest(expected_hmac, self.checked_hmac):
                return "TAMPERED_CHECKED_SET", None

            reused_count = 0
            fresh_count = 0
            total_steps = 0
            max_workset = 0
            next_entries: list[_OracleCheckedEntry] = []

            for pkg in packages:
                if pkg.locally_composed:
                    if pkg.has_publisher:
                        return "PUBLISHER_PRESENT", None
                elif not pkg.package_logged:
                    return "UNLOGGED_FETCH", None
                for member in pkg.closure:
                    if member.origin == ORIGIN_LOCAL_AUTHORED:
                        if member.has_publisher:
                            return "PUBLISHER_PRESENT", None
                    elif member.origin == ORIGIN_FETCHED_LOGGED:
                        if not member.logged_in_checkpoint:
                            return "UNLOGGED_FETCH", None
                        if not (member.consistent_with_pin and member.inclusion_ok):
                            return "CONSISTENCY", None
                    else:
                        return "INVALID_ARG", None

                art = pkg.artifact_digest(self.ctx)
                if pkg.is_base_image and not hmac.compare_digest(
                    pkg.expected_base_digest, pkg.code_digest
                ):
                    return "BASE_NOT_REPRODUCIBLE", None

                entry = _OracleCheckedEntry(
                    pkg.pkg_id,
                    art,
                    pkg.source_digest,
                    pkg.contract_digest,
                    pkg.proof_digest,
                    self.ctx,
                )
                if entry in self.checked_entries:
                    reused_count += 1
                else:
                    if not cic_available or not pkg.proof_ok:
                        return "PROOF_FAILED", None
                    if (
                        total_steps + pkg.proof_steps > self.step_budget
                        or pkg.proof_workset_bytes > self.workset_budget
                    ):
                        return "BUDGET_EXCEEDED", None
                    total_steps += pkg.proof_steps
                    max_workset = max(max_workset, pkg.proof_workset_bytes)
                    fresh_count += 1
                next_entries.append(entry)

            if not tal_fresh:
                return "TAL_STALE", None
            if not (wiring_fresh and global_ok):
                return "GLOBAL_CHECK_FAILED", None

            roster_hash = _oracle_roster_hash(packages, self.ctx)
            gen_root = _oracle_gen_root(version, declared_floor, roster_hash, self.ctx)
            mint_status, _mac = self.trusted_path_mint(roster_hash, gen_root, consent)
            if mint_status != "OK":
                return mint_status, None

            self.retained_root = self.live_root
            self.retained_version = self.live_version
            self.live_root = gen_root
            self.live_version = version
            self.checked_entries = tuple(next_entries)
            self.checked_hmac = self.seal_checked_set(self.checked_entries)
            return "OK", {
                "reused": reused_count,
                "fresh": fresh_count,
                "steps": total_steps,
                "workset": max_workset,
            }
        finally:
            self.mode = MODE_NORMAL
            self.priv_active = False

    def health_check(self, healthy: bool) -> str:
        if healthy:
            return "OK"
        if self.retained_root is None:
            return "NO_RETAINED"
        if self.retained_version < self.floor:
            return "ROLLBACK_FLOOR"
        self.live_root = self.retained_root
        self.live_version = self.retained_version
        self.retained_root = None
        return "UNHEALTHY_ROLLBACK"


def _digest(tag: int) -> bytes:
    return bytes((tag ^ (i * 3 + 1)) & 0xFF for i in range(32))


def _key(seed: int) -> bytes:
    return bytes(((seed + i * 11) | 1) & 0xFF for i in range(32))


def _oracle_roster_hash(packages: tuple[_OraclePackage, ...], ctx: _OracleContext) -> bytes:
    buf = bytearray(b"VOSDGENR" + len(packages).to_bytes(4, "little"))
    for pkg in packages:
        buf += pkg.pkg_id.to_bytes(8, "little")
        buf += pkg.artifact_digest(ctx)
    return hashlib.sha256(bytes(buf)).digest()


def _oracle_gen_root(
    version: int,
    declared_floor: int,
    roster_hash: bytes,
    ctx: _OracleContext,
) -> bytes:
    buf = (
        b"VOSDGEN1"
        + version.to_bytes(8, "little")
        + declared_floor.to_bytes(8, "little")
        + roster_hash
        + ctx.encode()
    )
    return hashlib.sha256(buf).digest()


def _make_pkg(pkg_id: int, is_base: bool, tag: int, steps: int, workset: int) -> _OraclePackage:
    code = bytes((tag + i) & 0xFF for i in range(32))
    return _OraclePackage(
        pkg_id=pkg_id,
        is_base_image=is_base,
        locally_composed=True,
        has_publisher=False,
        package_logged=False,
        source_digest=_digest(0x10 + tag),
        contract_digest=_digest(0x20 + tag),
        code_bytes=code,
        init_digest=_digest(0x30 + tag),
        proof_digest=_digest(0x40 + tag),
        expected_base_digest=hashlib.sha256(code).digest(),
        proof_steps=steps,
        proof_workset_bytes=workset,
        proof_ok=True,
        closure=(_OracleClosureMember(100 + pkg_id, ORIGIN_LOCAL_AUTHORED, False),),
    )


def _oracle_device_generation() -> None:
    """Exercise positive offline generations and all adverse mint/inclusion/reuse/budget/mode controls."""
    ctx = _OracleContext()
    base = _make_pkg(1, True, 1, 300, 2048)
    pkg_a = _make_pkg(2, False, 2, 250, 1024)
    pkg_b = replace(
        _make_pkg(3, False, 3, 120, 1024),
        closure=(
            _OracleClosureMember(103, ORIGIN_LOCAL_AUTHORED, False),
            _OracleClosureMember(202, ORIGIN_FETCHED_LOGGED, True, True, True, True),
        ),
    )
    initial_entries = tuple(
        _OracleCheckedEntry(
            p.pkg_id, p.artifact_digest(ctx), p.source_digest, p.contract_digest, p.proof_digest, ctx
        )
        for p in (base, pkg_a)
    )
    dev = _OracleDevice(
        key_id=3,
        signing_key=_key(0x21),
        checked_set_key=_key(0x73),
        ctx=ctx,
        live_root=_digest(0xA1),
        live_version=4,
        floor=4,
        checked_entries=initial_entries,
    )

    ensure(dev.export_key() == "EXPORT_FORBIDDEN", "key export must be forbidden")

    # 1. Offline package-change generation
    r1 = _oracle_roster_hash((base, pkg_a, pkg_b), ctx)
    g1 = _oracle_gen_root(5, 4, r1, ctx)
    c1 = _OracleConsent(True, True, _OraclePrompt(r1, g1, 1, b"offline-pkg-change"))
    st1, occ1 = dev.compose_and_admit((base, pkg_a, pkg_b), 5, 4, c1)
    ensure(st1 == "OK" and occ1 == {"reused": 2, "fresh": 1, "steps": 120, "workset": 1024},
           f"gen1 oracle mismatch: {st1} {occ1}")
    ensure(dev.mode == MODE_NORMAL and not dev.priv_active, "mode lingered after gen1")
    ensure(dev.health_check(True) == "OK", "healthy gen1 settle failed")

    # 2. Offline reproducible base-image rebuild + health rollback
    base2 = _make_pkg(1, True, 9, 300, 2048)
    r2 = _oracle_roster_hash((base2, pkg_a, pkg_b), ctx)
    g2 = _oracle_gen_root(6, 4, r2, ctx)
    c2 = _OracleConsent(True, True, _OraclePrompt(r2, g2, 2, b"offline-base-rebuild"))
    st2, occ2 = dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, c2)
    ensure(st2 == "OK" and occ2 == {"reused": 2, "fresh": 1, "steps": 300, "workset": 2048},
           f"gen2 oracle mismatch: {st2} {occ2}")
    ensure(dev.health_check(False) == "UNHEALTHY_ROLLBACK", "health rollback failed")
    ensure(dev.live_root == g1 and dev.live_version == 5, "rollback did not restore gen1")

    # 3. Adverse controls
    c_altered = _OracleConsent(True, True, _OraclePrompt(r2, _digest(0xEE), 3, b"altered"))
    c_nocred = _OracleConsent(False, True, _OraclePrompt(r2, g2, 4, b"nocred"))
    c_replay = _OracleConsent(True, True, _OraclePrompt(r2, g2, 1, b"replay"))
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, None)[0] == "NO_CONSENT",
           "mint without consent accepted")
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, c_altered)[0] == "CONSENT_MISMATCH",
           "mint with altered root accepted")
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, c_nocred)[0] == "CREDENTIAL_ABSENT",
           "mint with absent credential accepted")
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, c_replay)[0] == "NONCE_REPLAY",
           "replayed nonce accepted")

    pkg_unlogged = replace(
        pkg_b,
        closure=(
            _OracleClosureMember(103, ORIGIN_LOCAL_AUTHORED, False),
            _OracleClosureMember(202, ORIGIN_FETCHED_LOGGED, True, False, True, True),
        ),
    )
    ru = _oracle_roster_hash((base2, pkg_a, pkg_unlogged), ctx)
    gu = _oracle_gen_root(6, 4, ru, ctx)
    cu = _OracleConsent(True, True, _OraclePrompt(ru, gu, 5, b"unlogged"))
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_unlogged), 6, 4, cu)[0] == "UNLOGGED_FETCH",
           "unlogged fetched member accepted offline")
    ensure(dev.mode == MODE_NORMAL and not dev.priv_active, "mode leaked on failure")

    c_tal = _OracleConsent(True, True, _OraclePrompt(r2, g2, 6, b"stale-tal"))
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, c_tal, tal_fresh=False)[0] == "TAL_STALE",
           "stale TAL accepted")
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, c_tal, global_ok=False)[0] == "GLOBAL_CHECK_FAILED",
           "failed global check accepted")

    pkg_heavy = _make_pkg(3, False, 0x77, 10001, 1024)
    rh = _oracle_roster_hash((base2, pkg_a, pkg_heavy), ctx)
    gh = _oracle_gen_root(6, 4, rh, ctx)
    ch = _OracleConsent(True, True, _OraclePrompt(rh, gh, 7, b"overbudget"))
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_heavy), 6, 4, ch)[0] == "BUDGET_EXCEEDED",
           "budget exceeded accepted")

    saved_hmac = dev.checked_hmac
    dev.checked_hmac = bytes([saved_hmac[0] ^ 0xFF]) + saved_hmac[1:]
    ensure(dev.compose_and_admit((base2, pkg_a, pkg_b), 6, 4, c_tal)[0] == "TAMPERED_CHECKED_SET",
           "tampered checked set accepted")
    dev.checked_hmac = saved_hmac

    base_bad = replace(base2, expected_base_digest=_digest(0x99))
    rb = _oracle_roster_hash((base_bad, pkg_a, pkg_b), ctx)
    gb = _oracle_gen_root(6, 4, rb, ctx)
    cb = _OracleConsent(True, True, _OraclePrompt(rb, gb, 8, b"nonrepro"))
    ensure(dev.compose_and_admit((base_bad, pkg_a, pkg_b), 6, 4, cb)[0] == "BASE_NOT_REPRODUCIBLE",
           "non-reproducible base image accepted")
    ensure(dev.live_root == g1 and dev.mode == MODE_NORMAL and not dev.priv_active,
           "adverse failures mutated state")


def _surface_and_proof_contract() -> None:
    """Verify SPDX headers, GC-free C17 surface, and DeviceGeneration.v theorem/witness surface."""
    for path in (DGEN_H, DGEN_C, DGEN_TEST_C, DGEN_README, PROOFS_V):
        ensure(path.is_file(), f"missing device-generation artifact: {path}")

    for c_path in (DGEN_H, DGEN_C, DGEN_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(first_line == "// SPDX-License-Identifier: Apache-2.0",
               f"missing // SPDX header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden heap allocator {forbidden} in {c_path}")

    c_src = DGEN_C.read_text(encoding="utf-8")
    for fn in (
        "vos_dgen_device_init",
        "vos_dgen_compute_artifact_digest",
        "vos_dgen_compute_roster_hash",
        "vos_dgen_compute_gen_root",
        "vos_dgen_checked_set_seal",
        "vos_dgen_checked_set_verify",
        "vos_dgen_mode_enter",
        "vos_dgen_mode_exit",
        "vos_dgen_audit_offline_package",
        "vos_dgen_core_export_key",
        "vos_dgen_trusted_path_mint",
        "vos_dgen_compose_and_admit",
        "vos_dgen_health_check",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    for sym in (
        "mint_requires_unexportable_core_and_unprivileged_composer",
        "mint_refuses_no_consent",
        "mint_refuses_absent_credential",
        "mint_refuses_altered_root_or_roster",
        "mint_consumes_nonce_one_use",
        "enter_refuses_invalid_edge_and_preserves_normal_mode",
        "exit_always_restores_normal_mode_and_drops_privilege",
        "offline_local_closure_needs_no_network_and_carries_no_publisher",
        "fetched_unlogged_member_refuses_even_inside_local_offline_build",
        "reused_pkg_requires_authenticated_checked_set",
        "stale_tal_or_global_checks_refuse_even_when_all_packages_reused",
        "budget_exhaustion_refuses_generation",
        "base_image_non_reproducible_refuses",
        "every_run_exits_composition_mode_and_drops_privilege",
        "refused_run_preserves_running_ab_and_checked_set",
        "positive_offline_package_change_and_base_rebuild_both_admit_and_boot",
        "adverse_mint_cases_all_refused_and_preserve_running_state",
        "adverse_inclusion_reuse_budget_mode_and_repro_all_refused",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in DeviceGeneration.v")

    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in DeviceGeneration.v",
        )


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
            f"-I{DGEN_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(src_c),
            str(CRYPTO_SOURCE),
            str(DGEN_TEST_C),
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
            "mint-without-consent",
            replaced(
                "    if (consent == NULL || consent->user_consented == 0u) {\n"
                "        return VOS_DGEN_ERR_NO_CONSENT;\n"
                "    }",
                "    if (consent == NULL) {\n"
                "        return VOS_DGEN_ERR_NO_CONSENT;\n"
                "    }\n"
                "    if (0 && consent->user_consented == 0u) {\n"
                "        return VOS_DGEN_ERR_NO_CONSENT;\n"
                "    }",
                "mint-without-consent",
            ),
            "mint",
        ),
        (
            "mint-with-null-consent",
            replaced(
                "    if (consent == NULL || consent->user_consented == 0u) {\n"
                "        return VOS_DGEN_ERR_NO_CONSENT;\n"
                "    }",
                "    if (consent == NULL) {\n"
                "        memset(out_sig, 0, sizeof(*out_sig));\n"
                "        return VOS_DGEN_OK;\n"
                "    }",
                "mint-with-null-consent",
            ),
            "mint without consent",
        ),
        (
            "mint-altered-root",
            replaced(
                "    if (!equal_hashes(&consent->prompt.roster_hash, roster_hash) ||\n"
                "        !equal_hashes(&consent->prompt.gen_root, gen_root)) {\n"
                "        return VOS_DGEN_ERR_CONSENT_MISMATCH;\n"
                "    }",
                "    if (!equal_hashes(&consent->prompt.roster_hash, roster_hash)) {\n"
                "        return VOS_DGEN_ERR_CONSENT_MISMATCH;\n"
                "    }",
                "mint-altered-root",
            ),
            "altered root",
        ),
        (
            "mint-absent-credential",
            replaced(
                "    if (consent->credential_present == 0u) {\n"
                "        return VOS_DGEN_ERR_CREDENTIAL_ABSENT;\n"
                "    }",
                "    if (0 && consent->credential_present == 0u) {\n"
                "        return VOS_DGEN_ERR_CREDENTIAL_ABSENT;\n"
                "    }",
                "mint-absent-credential",
            ),
            "absent credential",
        ),
        (
            "unlogged-fetched-offline",
            replaced(
                "            if (m->logged_in_checkpoint == 0u) {\n"
                "                return VOS_DGEN_ERR_UNLOGGED_FETCH;\n"
                "            }",
                "            if (0 && m->logged_in_checkpoint == 0u) {\n"
                "                return VOS_DGEN_ERR_UNLOGGED_FETCH;\n"
                "            }",
                "unlogged-fetched-offline",
            ),
            "unlogged fetched",
        ),
        (
            "skip-fresh-tal-check",
            replaced(
                "    if (req->tal_layout_fresh_ok == 0u) {\n"
                "        vos_dgen_mode_exit(&dev->mode_guard);\n"
                "        return VOS_DGEN_ERR_TAL_STALE;\n"
                "    }",
                "    if (0 && req->tal_layout_fresh_ok == 0u) {\n"
                "        vos_dgen_mode_exit(&dev->mode_guard);\n"
                "        return VOS_DGEN_ERR_TAL_STALE;\n"
                "    }",
                "skip-fresh-tal-check",
            ),
            "stale TAL",
        ),
        (
            "skip-global-check",
            replaced(
                "    if (req->wiring_fresh_ok == 0u || req->global_resource_ok == 0u) {\n"
                "        vos_dgen_mode_exit(&dev->mode_guard);\n"
                "        return VOS_DGEN_ERR_GLOBAL_CHECK_FAILED;\n"
                "    }",
                "    if (0 && (req->wiring_fresh_ok == 0u || req->global_resource_ok == 0u)) {\n"
                "        vos_dgen_mode_exit(&dev->mode_guard);\n"
                "        return VOS_DGEN_ERR_GLOBAL_CHECK_FAILED;\n"
                "    }",
                "skip-global-check",
            ),
            "global resource",
        ),
        (
            "exceed-proof-budget",
            replaced(
                "            if (pkg->proof_steps > dev->step_budget ||\n"
                "                total_steps > dev->step_budget - pkg->proof_steps ||\n"
                "                pkg->proof_workset_bytes > dev->workset_budget) {\n"
                "                vos_dgen_mode_exit(&dev->mode_guard);\n"
                "                return VOS_DGEN_ERR_BUDGET_EXCEEDED;\n"
                "            }",
                "            if (0 && (pkg->proof_steps > dev->step_budget ||\n"
                "                      total_steps > dev->step_budget - pkg->proof_steps ||\n"
                "                      pkg->proof_workset_bytes > dev->workset_budget)) {\n"
                "                vos_dgen_mode_exit(&dev->mode_guard);\n"
                "                return VOS_DGEN_ERR_BUDGET_EXCEEDED;\n"
                "            }",
                "exceed-proof-budget",
            ),
            "budget exceeded",
        ),
        (
            "leak-composition-mode-on-failure",
            replaced(
                "    if (req->tal_layout_fresh_ok == 0u) {\n"
                "        vos_dgen_mode_exit(&dev->mode_guard);\n"
                "        return VOS_DGEN_ERR_TAL_STALE;\n"
                "    }",
                "    if (req->tal_layout_fresh_ok == 0u) {\n"
                "        return VOS_DGEN_ERR_TAL_STALE;\n"
                "    }",
                "leak-composition-mode-on-failure",
            ),
            "composition mode leaked",
        ),
        (
            "allow-key-export",
            replaced(
                "    if (out_key != NULL) {\n"
                "        zero_bytes(out_key, VOS_DGEN_KEY_BYTES);\n"
                "    }\n"
                "    return VOS_DGEN_ERR_EXPORT_FORBIDDEN;",
                "    if (core != NULL && out_key != NULL) {\n"
                "        memcpy(out_key, core->signing_key, VOS_DGEN_KEY_BYTES);\n"
                "        return VOS_DGEN_OK;\n"
                "    }\n"
                "    return VOS_DGEN_ERR_EXPORT_FORBIDDEN;",
                "allow-key-export",
            ),
            "key export",
        ),
        (
            "accept-tampered-checked-set",
            replaced(
                "    st = vos_dgen_checked_set_verify(&dev->core, &dev->checked_set);\n"
                "    if (st != VOS_DGEN_OK) {\n"
                "        vos_dgen_mode_exit(&dev->mode_guard);\n"
                "        return st;\n"
                "    }",
                "    st = vos_dgen_checked_set_verify(&dev->core, &dev->checked_set);\n"
                "    (void)st;",
                "accept-tampered-checked-set",
            ),
            "tampered checked set",
        ),
        (
            "skip-health-rollback",
            replaced(
                "    dev->ab.live_is_b = (dev->ab.live_is_b != 0u) ? 0u : 1u;\n"
                "    dev->ab.has_retained = 0u;\n"
                "    dev->ab.staged = 0u;\n"
                "    dev->ab.admitted = 0u;\n"
                "    return VOS_DGEN_ERR_UNHEALTHY_ROLLBACK;",
                "    dev->ab.has_retained = 0u;\n"
                "    dev->ab.staged = 0u;\n"
                "    dev->ab.admitted = 0u;\n"
                "    return VOS_DGEN_ERR_UNHEALTHY_ROLLBACK;",
                "skip-health-rollback",
            ),
            "health rollback did not restore",
        ),
        (
            "allow-nonreproducible-base",
            replaced(
                "        if (pkg->is_base_image != 0u &&\n"
                "            !equal_hashes(&pkg->expected_base_digest, &pkg->code_digest)) {\n"
                "            vos_dgen_mode_exit(&dev->mode_guard);\n"
                "            return VOS_DGEN_ERR_BASE_NOT_REPRODUCIBLE;\n"
                "        }",
                "        if (0 && pkg->is_base_image != 0u &&\n"
                "            !equal_hashes(&pkg->expected_base_digest, &pkg->code_digest)) {\n"
                "            vos_dgen_mode_exit(&dev->mode_guard);\n"
                "            return VOS_DGEN_ERR_BASE_NOT_REPRODUCIBLE;\n"
                "        }",
                "allow-nonreproducible-base",
            ),
            "non-reproducible base",
        ),
    ]


def _native_c_and_mutation_controls() -> None:
    """Compile and run device-generation C17 tests under Clang + GCC ASan/UBSan and kill all mutants."""
    if sys.platform == "win32":
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

    work = toolenv.environment(ROOT, sys.platform).parent / "device-generation-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dgen-", dir=work) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime required")

        # 1. Strict Clang C17 build and run
        clang_bin = tmp / "test_dgen_clang"
        clang_built = _compile_and_link(clang, strict_flags, DGEN_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(clang_ran.returncode == 0 and "device_gen_test: ok" in clang_ran.stdout,
               f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}")

        # 2. Strict GCC C17 + ASan/UBSan build and run
        gcc_bin = tmp / "test_dgen_gcc_san"
        gcc_built = _compile_and_link(gcc, asan_flags, DGEN_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(gcc_ran.returncode == 0 and "device_gen_test: ok" in gcc_ran.stdout,
               f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}")

        # 3. Behavioral mutation controls under GCC ASan/UBSan
        source = DGEN_C.read_text(encoding="utf-8")
        mutants = _mutants(source)
        ensure(len(mutants) >= 10, f"expected >= 10 mutants, got {len(mutants)}")
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
        Case("device_generation_oracle", _oracle_device_generation, lane="any"),
        Case("device_generation_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("device_generation_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
