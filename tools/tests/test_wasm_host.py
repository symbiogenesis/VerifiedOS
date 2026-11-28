# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracle and native C17 ASan/UBSan + Clang + mutation controls for wasm-host/."""

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
WHOST_DIR = ROOT / "wasm-host"
WHOST_H = WHOST_DIR / "include" / "vos_wasm_host.h"
WHOST_C = WHOST_DIR / "src" / "wasm_host.c"
WHOST_TEST_C = WHOST_DIR / "test" / "test_wasm_host.c"
WHOST_README = WHOST_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "WasmAppHost.v"

PHASE_FREE = 0
PHASE_PREPARED = 1
PHASE_ACTIVE = 2
PHASE_CANCELLING = 3
PHASE_SWEEPING = 4
PHASE_SANITIZED = 5
PHASE_REUSABLE = 6


@dataclass(frozen=True, slots=True)
class _OraclePolicy:
    abi_version: int = 1
    profile_id: int = 10
    generation: int = 4
    mem_page_ceiling: int = 64
    table_ceiling: int = 256
    stack_ceiling: int = 128
    import_ceiling_mask: int = 0x07
    max_epoch: int = 3


@dataclass(frozen=True, slots=True)
class _OracleBundle:
    module_bytes: bytes
    assets_bytes: bytes
    ui_label: bytes
    abi_version: int
    init_mem_pages: int
    max_mem_pages: int
    table_limit: int
    stack_limit: int
    schema_id: int
    requested_imports_mask: int
    closure_valid: bool = True
    descriptor_valid: bool = True
    core30_valid: bool = True
    has_start_fn: bool = True
    uses_fs_path_authority: bool = False
    override_closure_digest: bytes | None = None
    override_bundle_digest: bytes | None = None

    @property
    def closure_digest(self) -> bytes:
        if self.override_closure_digest is not None:
            return self.override_closure_digest
        payload = (
            b"VOSWHCL1"
            + len(self.module_bytes).to_bytes(4, "little")
            + self.module_bytes
            + len(self.assets_bytes).to_bytes(4, "little")
            + self.assets_bytes
        )
        return hashlib.sha256(payload).digest()

    @property
    def bundle_digest(self) -> bytes:
        if self.override_bundle_digest is not None:
            return self.override_bundle_digest
        payload = (
            b"VOSWHBD1"
            + self.closure_digest
            + self.abi_version.to_bytes(4, "little")
            + self.init_mem_pages.to_bytes(4, "little")
            + self.max_mem_pages.to_bytes(4, "little")
            + self.table_limit.to_bytes(4, "little")
            + self.stack_limit.to_bytes(4, "little")
            + self.schema_id.to_bytes(4, "little")
            + self.requested_imports_mask.to_bytes(4, "little")
        )
        return hashlib.sha256(payload).digest()


@dataclass(frozen=True, slots=True)
class _OracleConsent:
    user_consented: bool
    credential_ok: bool
    trusted_digest: bytes
    ui_label_shown: bytes
    nonce: int


@dataclass(frozen=True, slots=True)
class _OracleCheckpoint:
    bundle_digest: bytes
    abi_version: int
    profile_id: int
    schema_id: int
    generation: int
    durable_digest: bytes
    embedded_old_grants_mask: int
    embedded_tagged_mem: bool
    embedded_session_key: int
    mac: bytes


@dataclass(slots=True)
class _OracleSlot:
    slot_id: int
    group_id: int
    phase: int = PHASE_FREE
    act_id: int = 0
    epoch: int = 0
    epoch_retired: bool = False
    prepared: _OracleBundle | None = None
    active_bundle: _OracleBundle | None = None
    active_grants_mask: int = 0
    session_key: int = 0
    tagged_mem: bool = False
    start_executed: bool = False
    new_grants_spent: bool = False
    exec_stopped: bool = True
    ingress_stopped: bool = True
    pending_imports: int = 0
    sweep_done: bool = True
    zeroized: bool = True
    durable_bundle_digest: bytes | None = None
    durable_schema_id: int = 0
    durable_digest: bytes | None = None
    durable_acked: bool = False


@dataclass(slots=True)
class _OraclePool:
    policy: _OraclePolicy
    ckpt_auth_key: bytes
    avail_pages: int = 64
    staging_avail: bool = True
    next_act_id: int = 100
    slots: tuple[_OracleSlot, ...] = ()

    def __post_init__(self) -> None:
        if not self.slots:
            self.slots = tuple(_OracleSlot(i, 7000 + i) for i in range(4))

    def seal_checkpoint(
        self,
        bundle_digest: bytes,
        abi_version: int,
        profile_id: int,
        schema_id: int,
        generation: int,
        durable_digest: bytes,
        embedded_old_grants_mask: int,
        embedded_tagged_mem: bool,
        embedded_session_key: int,
    ) -> _OracleCheckpoint:
        payload = (
            b"VOSWHCK1"
            + bundle_digest
            + abi_version.to_bytes(4, "little")
            + profile_id.to_bytes(4, "little")
            + schema_id.to_bytes(4, "little")
            + generation.to_bytes(4, "little")
            + durable_digest
        )
        mac = hmac.new(self.ckpt_auth_key, payload, hashlib.sha256).digest()
        return _OracleCheckpoint(
            bundle_digest=bundle_digest,
            abi_version=abi_version,
            profile_id=profile_id,
            schema_id=schema_id,
            generation=generation,
            durable_digest=durable_digest,
            embedded_old_grants_mask=embedded_old_grants_mask,
            embedded_tagged_mem=embedded_tagged_mem,
            embedded_session_key=embedded_session_key,
            mac=mac,
        )

    def _validate(self, bundle: _OracleBundle) -> str | None:
        if bundle.uses_fs_path_authority:
            return "FS_PATH_AUTHORITY"
        expected_cl = _OracleBundle(
            bundle.module_bytes,
            bundle.assets_bytes,
            bundle.ui_label,
            bundle.abi_version,
            bundle.init_mem_pages,
            bundle.max_mem_pages,
            bundle.table_limit,
            bundle.stack_limit,
            bundle.schema_id,
            bundle.requested_imports_mask,
        ).closure_digest
        if not bundle.closure_valid or not hmac.compare_digest(bundle.closure_digest, expected_cl):
            return "FORGED_CLOSURE"
        expected_bd = _OracleBundle(
            bundle.module_bytes,
            bundle.assets_bytes,
            bundle.ui_label,
            bundle.abi_version,
            bundle.init_mem_pages,
            bundle.max_mem_pages,
            bundle.table_limit,
            bundle.stack_limit,
            bundle.schema_id,
            bundle.requested_imports_mask,
        ).bundle_digest
        if (
            not bundle.descriptor_valid
            or not bundle.core30_valid
            or not bundle.ui_label
            or not hmac.compare_digest(bundle.bundle_digest, expected_bd)
        ):
            return "FORGED_DESCRIPTOR"
        if bundle.abi_version != self.policy.abi_version:
            return "INCOMPATIBLE_ABI"
        if (
            bundle.init_mem_pages > bundle.max_mem_pages
            or bundle.max_mem_pages > self.policy.mem_page_ceiling
            or bundle.init_mem_pages > self.avail_pages
            or bundle.table_limit > self.policy.table_ceiling
            or bundle.stack_limit > self.policy.stack_ceiling
        ):
            return "OVERSIZED_RESERVATION"
        if bundle.requested_imports_mask & ~self.policy.import_ceiling_mask:
            return "OVER_SCOPED_GRANT"
        return None

    def _group_collision(self, slot_id: int) -> bool:
        gid = self.slots[slot_id].group_id
        return any(
            s.slot_id != slot_id
            and s.phase not in (PHASE_FREE, PHASE_REUSABLE)
            and s.group_id == gid
            for s in self.slots
        )

    def prepare(self, slot_id: int, bundle: _OracleBundle) -> str:
        slot = self.slots[slot_id]
        if slot.phase not in (PHASE_FREE, PHASE_REUSABLE):
            return "BAD_PHASE"
        if not self.staging_avail:
            return "NO_STAGING"
        err = self._validate(bundle)
        if err is not None:
            return err
        slot.phase = PHASE_PREPARED
        slot.prepared = bundle
        slot.active_bundle = None
        slot.active_grants_mask = 0
        slot.session_key = 0
        slot.tagged_mem = False
        slot.start_executed = False
        slot.new_grants_spent = False
        slot.exec_stopped = True
        slot.ingress_stopped = True
        slot.pending_imports = 0
        return "OK"

    def launch(
        self,
        slot_id: int,
        consent: _OracleConsent | None,
        initial_grants_mask: int,
        uses_fs_path: bool,
        session_key: int,
    ) -> str:
        if uses_fs_path:
            return "FS_PATH_AUTHORITY"
        slot = self.slots[slot_id]
        if slot.phase != PHASE_PREPARED or slot.prepared is None:
            return "BAD_PHASE"
        if slot.epoch_retired or slot.epoch >= self.policy.max_epoch:
            slot.epoch_retired = True
            return "EPOCH_EXHAUSTED"
        if self._group_collision(slot_id):
            return "GROUP_COLLISION"
        bd = slot.prepared
        if consent is None or not consent.user_consented or not consent.credential_ok:
            return "NO_CONSENT"
        if not hmac.compare_digest(consent.trusted_digest, bd.bundle_digest):
            return "CONSENT_DIGEST_MISMATCH"
        if (initial_grants_mask & ~bd.requested_imports_mask) or (
            initial_grants_mask & ~self.policy.import_ceiling_mask
        ):
            return "OVER_SCOPED_GRANT"
        if bd.init_mem_pages > self.avail_pages:
            return "NO_CAPACITY"
        self.avail_pages -= bd.init_mem_pages
        slot.phase = PHASE_ACTIVE
        slot.act_id = self.next_act_id
        self.next_act_id += 1
        slot.epoch += 1
        slot.active_bundle = bd
        slot.prepared = None
        slot.active_grants_mask = initial_grants_mask
        slot.session_key = session_key
        slot.tagged_mem = False
        slot.start_executed = bd.has_start_fn
        slot.new_grants_spent = True
        slot.exec_stopped = False
        slot.ingress_stopped = False
        slot.pending_imports = 0
        slot.sweep_done = False
        slot.zeroized = False
        return "OK"

    def invoke_import(
        self,
        slot_id: int,
        act_id: int,
        epoch: int,
        group_id: int,
        import_bit: int,
        scope_ok: bool,
        exports_pool_cap: bool,
        tagged_transport: bool,
        reply_epoch: int,
        yield_bounded: bool,
    ) -> tuple[str, int]:
        slot = self.slots[slot_id]
        if slot.phase != PHASE_ACTIVE or slot.exec_stopped or slot.ingress_stopped:
            return "BAD_PHASE", 0
        if (
            act_id != slot.act_id
            or epoch != slot.epoch
            or group_id != slot.group_id
            or not scope_ok
        ):
            return "HANDLE_SCOPE", 0
        if import_bit == 0 or (import_bit & (import_bit - 1)) != 0 or (
            import_bit & ~slot.active_grants_mask
        ):
            return "OVER_SCOPED_GRANT", 0
        if exports_pool_cap:
            return "POOL_CAP_EXPORT", 0
        if tagged_transport:
            return "TAGGED_TRANSPORT", 0
        if reply_epoch != slot.epoch:
            return "EPOCH_MISMATCH", 0
        if not yield_bounded:
            return "YIELD_BOUND", 0
        return "OK", slot.epoch

    def replace(
        self,
        slot_id: int,
        candidate: _OracleBundle,
        consent: _OracleConsent | None,
        new_grants_mask: int,
        transition_reserved: bool,
        commit_authorized: bool,
        durable_policy_ok: bool,
        post_commit_ok: bool,
        acked_durable_digest: bytes,
        uses_fs_path: bool,
        new_session_key: int,
    ) -> str:
        slot = self.slots[slot_id]
        if slot.phase != PHASE_ACTIVE or slot.active_bundle is None:
            return "BAD_PHASE"
        if uses_fs_path:
            return "FS_PATH_AUTHORITY"
        if not transition_reserved:
            return "NO_CAPACITY"
        if not durable_policy_ok:
            return "COMMIT_UNAUTHORIZED"
        err = self._validate(candidate)
        if err is not None:
            return err
        if slot.epoch_retired or slot.epoch >= self.policy.max_epoch:
            return "EPOCH_EXHAUSTED"
        if consent is None or not consent.user_consented or not consent.credential_ok:
            return "NO_CONSENT"
        if not hmac.compare_digest(consent.trusted_digest, candidate.bundle_digest):
            return "CONSENT_DIGEST_MISMATCH"
        if (new_grants_mask & ~candidate.requested_imports_mask) or (
            new_grants_mask & ~self.policy.import_ceiling_mask
        ):
            return "OVER_SCOPED_GRANT"
        if not commit_authorized:
            return "COMMIT_UNAUTHORIZED"
        old_pages = slot.active_bundle.init_mem_pages
        if self.avail_pages + old_pages < candidate.init_mem_pages:
            return "NO_CAPACITY"

        self.avail_pages += old_pages
        slot.act_id = self.next_act_id
        self.next_act_id += 1
        slot.epoch += 1
        slot.durable_bundle_digest = candidate.bundle_digest
        slot.durable_schema_id = candidate.schema_id
        slot.durable_digest = acked_durable_digest
        slot.durable_acked = True
        if post_commit_ok:
            self.avail_pages -= candidate.init_mem_pages
            slot.phase = PHASE_ACTIVE
            slot.active_bundle = candidate
            slot.active_grants_mask = new_grants_mask
            slot.session_key = new_session_key
            slot.tagged_mem = False
            slot.start_executed = candidate.has_start_fn
            slot.new_grants_spent = True
            slot.exec_stopped = False
            slot.ingress_stopped = False
            slot.pending_imports = 0
            slot.sweep_done = False
            slot.zeroized = False
            return "OK"
        slot.phase = PHASE_SANITIZED
        slot.active_bundle = None
        slot.active_grants_mask = 0
        slot.session_key = 0
        slot.tagged_mem = False
        slot.start_executed = False
        slot.new_grants_spent = False
        slot.exec_stopped = True
        slot.ingress_stopped = True
        slot.pending_imports = 0
        slot.sweep_done = True
        slot.zeroized = True
        return "POST_COMMIT_CLOSED"

    def cancel_begin(self, slot_id: int) -> str:
        slot = self.slots[slot_id]
        if slot.phase != PHASE_ACTIVE:
            return "BAD_PHASE"
        slot.phase = PHASE_CANCELLING
        slot.exec_stopped = True
        slot.ingress_stopped = True
        slot.sweep_done = False
        slot.zeroized = False
        return "OK"

    def drain_imports(self, slot_id: int) -> str:
        slot = self.slots[slot_id]
        if slot.phase != PHASE_CANCELLING:
            return "BAD_PHASE"
        slot.pending_imports = 0
        return "OK"

    def enter_sweeping(self, slot_id: int) -> str:
        slot = self.slots[slot_id]
        if slot.phase != PHASE_CANCELLING or not slot.exec_stopped or not slot.ingress_stopped:
            return "BAD_PHASE"
        if slot.pending_imports != 0:
            return "PENDING_IMPORTS"
        slot.phase = PHASE_SWEEPING
        return "OK"

    def sweep_and_zeroize(self, slot_id: int) -> str:
        slot = self.slots[slot_id]
        if slot.phase != PHASE_SWEEPING:
            return "BAD_PHASE"
        if slot.active_bundle is not None:
            self.avail_pages += slot.active_bundle.init_mem_pages
        slot.prepared = None
        slot.active_bundle = None
        slot.active_grants_mask = 0
        slot.session_key = 0
        slot.tagged_mem = False
        slot.start_executed = False
        slot.new_grants_spent = False
        slot.exec_stopped = True
        slot.ingress_stopped = True
        slot.pending_imports = 0
        slot.sweep_done = True
        slot.zeroized = True
        slot.phase = PHASE_SANITIZED
        return "OK"

    def complete_reuse(self, slot_id: int) -> str:
        slot = self.slots[slot_id]
        if slot.phase != PHASE_SANITIZED or not slot.sweep_done or not slot.zeroized:
            return "NOT_SANITIZED"
        if slot.pending_imports != 0:
            return "PENDING_IMPORTS"
        slot.phase = PHASE_REUSABLE
        return "OK"

    def restore(
        self,
        slot_id: int,
        bundle: _OracleBundle,
        ckpt: _OracleCheckpoint,
        current_grants_mask: int,
        new_session_key: int,
    ) -> str:
        slot = self.slots[slot_id]
        if slot.phase not in (PHASE_FREE, PHASE_REUSABLE):
            return "BAD_PHASE"
        expected = self.seal_checkpoint(
            ckpt.bundle_digest,
            ckpt.abi_version,
            ckpt.profile_id,
            ckpt.schema_id,
            ckpt.generation,
            ckpt.durable_digest,
            ckpt.embedded_old_grants_mask,
            ckpt.embedded_tagged_mem,
            ckpt.embedded_session_key,
        )
        if not hmac.compare_digest(expected.mac, ckpt.mac):
            return "UNAUTH_CHECKPOINT"
        err = self._validate(bundle)
        if err is not None:
            return err
        if not hmac.compare_digest(ckpt.bundle_digest, bundle.bundle_digest):
            return "FORGED_DESCRIPTOR"
        if ckpt.abi_version != self.policy.abi_version:
            return "INCOMPATIBLE_ABI"
        if ckpt.profile_id != self.policy.profile_id or ckpt.generation != self.policy.generation:
            return "INCOMPATIBLE_GEN"
        if ckpt.schema_id != bundle.schema_id:
            return "STALE_SCHEMA"
        if slot.epoch_retired or slot.epoch >= self.policy.max_epoch:
            slot.epoch_retired = True
            return "EPOCH_EXHAUSTED"
        if self._group_collision(slot_id):
            return "GROUP_COLLISION"
        if (current_grants_mask & ~bundle.requested_imports_mask) or (
            current_grants_mask & ~self.policy.import_ceiling_mask
        ):
            return "OVER_SCOPED_GRANT"
        if bundle.init_mem_pages > self.avail_pages:
            return "NO_CAPACITY"
        self.avail_pages -= bundle.init_mem_pages
        slot.phase = PHASE_ACTIVE
        slot.act_id = self.next_act_id
        self.next_act_id += 1
        slot.epoch += 1
        slot.active_bundle = bundle
        slot.prepared = None
        slot.active_grants_mask = current_grants_mask
        slot.session_key = new_session_key
        slot.tagged_mem = False
        slot.start_executed = bundle.has_start_fn
        slot.new_grants_spent = True
        slot.exec_stopped = False
        slot.ingress_stopped = False
        slot.pending_imports = 0
        slot.sweep_done = False
        slot.zeroized = False
        slot.durable_bundle_digest = bundle.bundle_digest
        slot.durable_schema_id = ckpt.schema_id
        slot.durable_digest = ckpt.durable_digest
        slot.durable_acked = True
        return "OK"


def _digest(tag: int) -> bytes:
    return bytes((tag ^ (i * 5 + 3)) & 0xFF for i in range(32))


def _key(seed: int) -> bytes:
    return bytes(((seed + i * 7) | 1) & 0xFF for i in range(32))


def _make_bundle(
    tag: int,
    label: bytes,
    abi: int,
    init_p: int,
    max_p: int,
    schema_id: int,
    grants_mask: int,
) -> _OracleBundle:
    mod = bytes((tag + i) & 0xFF for i in range(32))
    ast = bytes((tag ^ (i + 0x20)) & 0xFF for i in range(16))
    return _OracleBundle(mod, ast, label, abi, init_p, max_p, 64, 32, schema_id, grants_mask)


def _oracle_wasm_host() -> None:
    """Exercise positive host lifecycle and all adversarial boundary controls in the independent oracle."""
    pool = _OraclePool(_OraclePolicy(), _key(0x31))
    app_a = _make_bundle(0x10, b"AppAlpha", 1, 8, 32, 1, 0x03)
    app_b = _make_bundle(0x40, b"AppAlpha", 1, 12, 48, 2, 0x06)

    ensure(pool.prepare(0, app_a) == "OK", "oracle prepare app_a failed")
    ensure(
        pool.slots[0].phase == PHASE_PREPARED
        and not pool.slots[0].start_executed
        and not pool.slots[0].new_grants_spent,
        "prepare executed start or spent grants",
    )

    ensure(
        pool.prepare(1, replace(app_a, override_closure_digest=_digest(0xFF))) == "FORGED_CLOSURE",
        "forged closure accepted",
    )
    ensure(
        pool.prepare(1, _make_bundle(0x20, b"BadAbi", 99, 8, 32, 1, 0x01)) == "INCOMPATIBLE_ABI",
        "bad ABI accepted",
    )
    ensure(
        pool.prepare(1, _make_bundle(0x21, b"TooBig", 1, 8, 128, 1, 0x01)) == "OVERSIZED_RESERVATION",
        "oversized reservation accepted",
    )
    ensure(
        pool.prepare(1, replace(app_a, uses_fs_path_authority=True)) == "FS_PATH_AUTHORITY",
        "fs path authority accepted in prepare",
    )

    spoof_consent = _OracleConsent(True, True, app_b.bundle_digest, b"AppAlpha", 1)
    ensure(
        pool.launch(0, spoof_consent, 0x01, False, 555) == "CONSENT_DIGEST_MISMATCH",
        "UI label spoof accepted",
    )
    consent_a = _OracleConsent(True, True, app_a.bundle_digest, b"AppAlpha", 2)
    ensure(
        pool.launch(0, consent_a, 0x01, True, 555) == "FS_PATH_AUTHORITY",
        "fs path authority accepted in launch",
    )
    ensure(pool.launch(0, consent_a, 0x01, False, 555) == "OK", "launch app_a failed")
    ensure(pool.slots[0].epoch == 1 and pool.avail_pages == 56, "launch accounting mismatch")

    ensure(pool.prepare(1, app_b) == "OK", "prepare slot 1 failed")
    pool.slots[1].group_id = pool.slots[0].group_id
    consent_b = _OracleConsent(True, True, app_b.bundle_digest, b"AppAlpha", 3)
    ensure(pool.launch(1, consent_b, 0x02, False, 777) == "GROUP_COLLISION", "group collision accepted")
    pool.slots[1].group_id = 7001
    ensure(pool.launch(1, consent_b, 0x02, False, 777) == "OK", "launch slot 1 failed")

    s0 = pool.slots[0]
    ensure(
        pool.invoke_import(0, s0.act_id, s0.epoch, s0.group_id, 0x01, True, False, False, 1, True)
        == ("OK", 1),
        "valid invoke failed",
    )
    ensure(
        pool.invoke_import(0, s0.act_id, s0.epoch, pool.slots[1].group_id, 0x01, True, False, False, 1, True)[0]
        == "HANDLE_SCOPE",
        "cross-instance handle accepted",
    )
    ensure(
        pool.invoke_import(0, s0.act_id, s0.epoch, s0.group_id, 0x01, True, True, False, 1, True)[0]
        == "POOL_CAP_EXPORT",
        "pool-cap export accepted",
    )
    ensure(
        pool.invoke_import(0, s0.act_id, s0.epoch, s0.group_id, 0x01, True, False, True, 1, True)[0]
        == "TAGGED_TRANSPORT",
        "tagged transport accepted",
    )
    ensure(
        pool.invoke_import(0, s0.act_id, s0.epoch, s0.group_id, 0x01, True, False, False, 0, True)[0]
        == "EPOCH_MISMATCH",
        "stale reply epoch accepted",
    )

    ensure(
        pool.replace(0, app_b, None, 0x04, True, True, True, True, _digest(0x71), False, 888)
        == "NO_CONSENT",
        "replace without consent accepted",
    )
    ensure(pool.slots[0].epoch == 1 and pool.slots[0].active_grants_mask == 0x01, "pre-commit mutated old")
    ensure(
        pool.replace(0, app_b, consent_b, 0x04, True, True, True, True, _digest(0x71), False, 888)
        == "OK",
        "valid replace failed",
    )
    ensure(
        pool.replace(1, app_b, consent_b, 0x04, True, True, True, False, _digest(0x72), False, 999)
        == "POST_COMMIT_CLOSED",
        "post-commit failure did not close",
    )
    ensure(
        pool.slots[1].phase == PHASE_SANITIZED
        and pool.slots[1].active_grants_mask == 0
        and pool.slots[1].durable_acked,
        "post-commit state invalid",
    )

    ensure(pool.cancel_begin(0) == "OK", "cancel_begin failed")
    pool.slots[0].pending_imports = 2
    ensure(pool.enter_sweeping(0) == "PENDING_IMPORTS", "sweeping entered with pending imports")
    ensure(pool.complete_reuse(0) == "NOT_SANITIZED", "reuse allowed before sanitize")
    ensure(pool.drain_imports(0) == "OK", "drain failed")
    ensure(pool.enter_sweeping(0) == "OK", "enter_sweeping failed")
    ensure(pool.sweep_and_zeroize(0) == "OK", "sweep failed")
    ensure(pool.complete_reuse(0) == "OK", "reuse failed")
    ensure(pool.avail_pages == 64 and pool.slots[0].epoch == 2, "reuse accounting mismatch")

    ckpt = pool.seal_checkpoint(app_b.bundle_digest, 1, 10, 2, 4, _digest(0x73), 0x07, True, 12345)
    ensure(
        pool.restore(0, app_b, replace(ckpt, mac=bytes([ckpt.mac[0] ^ 0xFF]) + ckpt.mac[1:]), 0x04, 321)
        == "UNAUTH_CHECKPOINT",
        "unauthenticated checkpoint accepted",
    )
    stale_ckpt = pool.seal_checkpoint(app_b.bundle_digest, 1, 10, 99, 4, _digest(0x73), 0x07, True, 12345)
    ensure(pool.restore(0, app_b, stale_ckpt, 0x04, 321) == "STALE_SCHEMA", "stale schema accepted")
    old_gen_ckpt = pool.seal_checkpoint(app_b.bundle_digest, 1, 10, 2, 3, _digest(0x73), 0x07, True, 12345)
    ensure(pool.restore(0, app_b, old_gen_ckpt, 0x04, 321) == "INCOMPATIBLE_GEN", "old gen accepted")

    ensure(pool.restore(0, app_b, ckpt, 0x04, 321) == "OK", "valid restore failed")
    ensure(
        pool.slots[0].active_grants_mask == 0x04
        and pool.slots[0].session_key == 321
        and not pool.slots[0].tagged_mem
        and pool.slots[0].epoch == 3,
        "restore leaked old grants/keys/tags",
    )

    ensure(pool.cancel_begin(0) == "OK", "cancel 2 failed")
    ensure(pool.enter_sweeping(0) == "OK", "sweep enter 2 failed")
    ensure(pool.sweep_and_zeroize(0) == "OK", "sweep 2 failed")
    ensure(pool.complete_reuse(0) == "OK", "reuse 2 failed")
    ensure(pool.prepare(0, app_a) == "OK", "prepare 2 failed")
    ensure(pool.launch(0, consent_a, 0x01, False, 111) == "EPOCH_EXHAUSTED", "epoch wrap allowed")
    ensure(pool.slots[0].epoch == 3 and pool.slots[0].epoch_retired, "exhausted epoch not retired")


def _surface_and_proof_contract() -> None:
    """Verify SPDX headers, GC-free C17 surface, README links, and WasmAppHost.v theorem/witness surface."""
    for path in (WHOST_H, WHOST_C, WHOST_TEST_C, WHOST_README, PROOFS_V):
        ensure(path.is_file(), f"missing wasm-host artifact: {path}")

    for c_path in (WHOST_H, WHOST_C, WHOST_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(
            first_line == "// SPDX-License-Identifier: Apache-2.0",
            f"missing // SPDX header in {c_path}",
        )
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden dynamic allocation {forbidden} in {c_path}")

    readme_text = WHOST_README.read_text(encoding="utf-8")
    for link_target in re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)", readme_text):
        if "://" not in link_target:
            resolved = (WHOST_README.parent / link_target).resolve()
            ensure(resolved.exists(), f"broken link in wasm-host/README.md: {link_target}")

    c_src = WHOST_C.read_text(encoding="utf-8")
    for fn in (
        "vos_whost_pool_init",
        "vos_whost_compute_closure_digest",
        "vos_whost_compute_bundle_digest",
        "vos_whost_seal_checkpoint",
        "vos_whost_prepare",
        "vos_whost_launch",
        "vos_whost_invoke_import",
        "vos_whost_replace",
        "vos_whost_cancel_begin",
        "vos_whost_drain_imports",
        "vos_whost_enter_sweeping",
        "vos_whost_sweep_and_zeroize",
        "vos_whost_complete_reuse",
        "vos_whost_restore",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    ensure(v_src.splitlines()[0] == "(* SPDX-License-Identifier: Apache-2.0 *)", "missing SPDX in WasmAppHost.v")
    ensure("Require ProofSupport." in v_src, "WasmAppHost.v must Require ProofSupport.")
    for sym in (
        "prepare_executes_no_start_and_spends_no_grants",
        "prepare_failure_preserves_slot_and_live_binding",
        "launch_refuses_ui_label_spoof_when_digest_differs",
        "launch_refuses_exhausted_epoch_without_wraparound",
        "launch_succeeds_with_fresh_epoch_distinct_group_and_exact_digest",
        "invoke_requires_active_matching_binding_epoch_and_tagfree_transport",
        "invoke_refuses_pool_cap_export",
        "reusable_requires_sanitized_sweep_and_zeroization",
        "invoke_refused_once_cancelling_or_beyond",
        "replace_precommit_failure_preserves_old_binding",
        "replace_postcommit_failure_closes_with_acked_durable_and_no_old_grants",
        "replace_commit_never_mixes_old_grants_with_candidate_execution",
        "restore_requires_auth_schema_abi_gen_and_uses_current_grants_only",
        "positive_full_lifecycle_prepare_launch_invoke_cancel_sweep_reuse",
        "positive_transactional_replace_and_checkpoint_restore",
        "negative_prepare_launch_invoke_replace_reuse_and_restore_controls",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in WasmAppHost.v")

    for rec in (
        "HostPolicy",
        "BundleDescriptor",
        "TrustedConsent",
        "ImportHandle",
        "ImportCall",
        "DurableState",
        "SemanticCheckpoint",
        "PoolResources",
        "HostSlot",
        "ReplaceRequest",
        "HostOutcome",
    ):
        ensure(f"Definition witness_{rec} : {rec} :=" in v_src, f"missing witness_{rec} in WasmAppHost.v")

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
            f"forbidden proof keyword {banned} in WasmAppHost.v",
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
    compiler: str,
    flags: list[str],
    src_c: Path,
    out_bin: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            compiler,
            *flags,
            f"-I{WHOST_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(src_c),
            str(CRYPTO_SOURCE),
            str(WHOST_TEST_C),
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
            "allow-forged-closure",
            replaced(
                "    if (!equal_hashes(&expected_cl, &bundle->closure_digest)) {\n"
                "        return VOS_WHOST_ERR_FORGED_CLOSURE;\n"
                "    }",
                "    if (0 && !equal_hashes(&expected_cl, &bundle->closure_digest)) {\n"
                "        return VOS_WHOST_ERR_FORGED_CLOSURE;\n"
                "    }",
                "allow-forged-closure",
            ),
            "forged closure",
        ),
        (
            "allow-bad-abi",
            replaced(
                "    if (bundle->abi_version != pool->policy.abi_version) {\n"
                "        return VOS_WHOST_ERR_INCOMPATIBLE_ABI;\n"
                "    }",
                "    if (0 && bundle->abi_version != pool->policy.abi_version) {\n"
                "        return VOS_WHOST_ERR_INCOMPATIBLE_ABI;\n"
                "    }",
                "allow-bad-abi",
            ),
            "incompatible ABI",
        ),
        (
            "allow-oversized-reservation",
            replaced(
                "        bundle->stack_limit > pool->policy.stack_ceiling) {\n"
                "        return VOS_WHOST_ERR_OVERSIZED_RESERVATION;\n"
                "    }",
                "        bundle->stack_limit > pool->policy.stack_ceiling) {\n"
                "        /* mutant: allow oversized */\n"
                "    }",
                "allow-oversized-reservation",
            ),
            "oversized reservation",
        ),
        (
            "allow-fs-path-prepare",
            replaced(
                "    if (bundle->uses_fs_path_authority != 0u) {\n"
                "        return VOS_WHOST_ERR_FS_PATH_AUTHORITY;\n"
                "    }",
                "    if (0 && bundle->uses_fs_path_authority != 0u) {\n"
                "        return VOS_WHOST_ERR_FS_PATH_AUTHORITY;\n"
                "    }",
                "allow-fs-path-prepare",
            ),
            "fs path authority accepted in prepare",
        ),
        (
            "allow-ui-label-spoof",
            replaced(
                "    if (!equal_hashes(&consent->trusted_digest, &bundle->bundle_digest)) {\n"
                "        return VOS_WHOST_ERR_CONSENT_DIGEST_MISMATCH;\n"
                "    }",
                "    if (0 && !equal_hashes(&consent->trusted_digest, &bundle->bundle_digest)) {\n"
                "        return VOS_WHOST_ERR_CONSENT_DIGEST_MISMATCH;\n"
                "    }",
                "allow-ui-label-spoof",
            ),
            "UI label spoof",
        ),
        (
            "allow-group-collision",
            replaced(
                "    if (group_collision(pool, slot_id)) {\n"
                "        return VOS_WHOST_ERR_GROUP_COLLISION;\n"
                "    }\n"
                "\n"
                "    const struct vos_whost_bundle *bd = &slot->prepared;",
                "    if (0 && group_collision(pool, slot_id)) {\n"
                "        return VOS_WHOST_ERR_GROUP_COLLISION;\n"
                "    }\n"
                "\n"
                "    const struct vos_whost_bundle *bd = &slot->prepared;",
                "allow-group-collision",
            ),
            "clear-group collision",
        ),
        (
            "allow-cross-instance-handle",
            replaced(
                "    if (call->handle.act_id != slot->act_id ||\n"
                "        call->handle.epoch != slot->epoch ||\n"
                "        call->handle.group_id != slot->group_id ||\n"
                "        call->handle.scope_ok == 0u) {\n"
                "        return VOS_WHOST_ERR_HANDLE_SCOPE;\n"
                "    }",
                "    if (call->handle.act_id != slot->act_id ||\n"
                "        call->handle.epoch != slot->epoch ||\n"
                "        call->handle.scope_ok == 0u) {\n"
                "        return VOS_WHOST_ERR_HANDLE_SCOPE;\n"
                "    }",
                "allow-cross-instance-handle",
            ),
            "cross-instance handle",
        ),
        (
            "allow-pool-cap-export",
            replaced(
                "    if (call->exports_pool_cap != 0u) {\n"
                "        return VOS_WHOST_ERR_POOL_CAP_EXPORT;\n"
                "    }",
                "    if (0 && call->exports_pool_cap != 0u) {\n"
                "        return VOS_WHOST_ERR_POOL_CAP_EXPORT;\n"
                "    }",
                "allow-pool-cap-export",
            ),
            "pool-cap export",
        ),
        (
            "allow-tagged-transport",
            replaced(
                "    if (call->tagged_transport != 0u) {\n"
                "        return VOS_WHOST_ERR_TAGGED_TRANSPORT;\n"
                "    }",
                "    if (0 && call->tagged_transport != 0u) {\n"
                "        return VOS_WHOST_ERR_TAGGED_TRANSPORT;\n"
                "    }",
                "allow-tagged-transport",
            ),
            "tagged transport",
        ),
        (
            "allow-stale-reply-epoch",
            replaced(
                "    if (call->reply_epoch != slot->epoch) {\n"
                "        return VOS_WHOST_ERR_EPOCH_MISMATCH;\n"
                "    }",
                "    if (0 && call->reply_epoch != slot->epoch) {\n"
                "        return VOS_WHOST_ERR_EPOCH_MISMATCH;\n"
                "    }",
                "allow-stale-reply-epoch",
            ),
            "stale reply epoch",
        ),
        (
            "allow-reuse-before-sanitize",
            replaced(
                "    if (slot->phase != VOS_WHOST_PHASE_SANITIZED ||\n"
                "        slot->sweep_done == 0u ||\n"
                "        slot->zeroized == 0u) {\n"
                "        return VOS_WHOST_ERR_NOT_SANITIZED;\n"
                "    }",
                "    if (0 && (slot->phase != VOS_WHOST_PHASE_SANITIZED ||\n"
                "              slot->sweep_done == 0u ||\n"
                "              slot->zeroized == 0u)) {\n"
                "        return VOS_WHOST_ERR_NOT_SANITIZED;\n"
                "    }",
                "allow-reuse-before-sanitize",
            ),
            "reuse allowed before sweep/sanitize",
        ),
        (
            "allow-unauth-checkpoint",
            replaced(
                "    if (!auth_ok) {\n"
                "        return VOS_WHOST_ERR_UNAUTH_CHECKPOINT;\n"
                "    }",
                "    if (0 && !auth_ok) {\n"
                "        return VOS_WHOST_ERR_UNAUTH_CHECKPOINT;\n"
                "    }",
                "allow-unauth-checkpoint",
            ),
            "unauthenticated checkpoint",
        ),
        (
            "allow-stale-schema-restore",
            replaced(
                "    if (ckpt->schema_id != bundle->schema_id) {\n"
                "        return VOS_WHOST_ERR_STALE_SCHEMA;\n"
                "    }",
                "    if (0 && ckpt->schema_id != bundle->schema_id) {\n"
                "        return VOS_WHOST_ERR_STALE_SCHEMA;\n"
                "    }",
                "allow-stale-schema-restore",
            ),
            "stale schema checkpoint",
        ),
        (
            "wrap-exhausted-epoch",
            replaced(
                "    if (slot->epoch_retired != 0u || slot->epoch >= pool->policy.max_epoch) {\n"
                "        slot->epoch_retired = 1u;\n"
                "        return VOS_WHOST_ERR_EPOCH_EXHAUSTED;\n"
                "    }\n"
                "    if (group_collision(pool, slot_id)) {\n"
                "        return VOS_WHOST_ERR_GROUP_COLLISION;\n"
                "    }\n"
                "\n"
                "    const struct vos_whost_bundle *bd = &slot->prepared;",
                "    if (slot->epoch_retired != 0u || slot->epoch >= pool->policy.max_epoch) {\n"
                "        slot->epoch = 0u;\n"
                "    }\n"
                "    if (group_collision(pool, slot_id)) {\n"
                "        return VOS_WHOST_ERR_GROUP_COLLISION;\n"
                "    }\n"
                "\n"
                "    const struct vos_whost_bundle *bd = &slot->prepared;",
                "wrap-exhausted-epoch",
            ),
            "epoch exhaustion",
        ),
    ]


def _native_c_and_mutation_controls() -> None:
    """Compile and run wasm-host C17 tests under Clang + GCC ASan/UBSan and kill all mutants."""
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

    lane_c_tests = toolenv.environment(ROOT, sys.platform).parent / "c-tests"
    lane_c_tests.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="whost-", dir=lane_c_tests) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime required")

        clang_bin = tmp / "test_whost_clang"
        clang_built = _compile_and_link(clang, strict_flags, WHOST_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        ensure(
            clang_ran.returncode == 0 and "wasm_host_test: ok" in clang_ran.stdout,
            f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}",
        )

        gcc_bin = tmp / "test_whost_gcc_san"
        gcc_built = _compile_and_link(gcc, asan_flags, WHOST_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        ensure(
            gcc_ran.returncode == 0 and "wasm_host_test: ok" in gcc_ran.stdout,
            f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}",
        )

        source = WHOST_C.read_text(encoding="utf-8")
        mutants = _mutants(source)
        ensure(len(mutants) >= 12, f"expected >= 12 mutants, got {len(mutants)}")
        for label, mutated_source, expected_diag in mutants:
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(mutated_source, encoding="utf-8", newline="\n")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = _compile_and_link(gcc, asan_flags, mutant_c, mutant_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mutant_bin)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            ensure(
                m_ran.returncode != 0 and expected_diag in m_ran.stderr,
                f"mutant survived or missed expected diagnostic ({label}): {m_ran.stderr or m_ran.stdout}",
            )


def cases() -> list[Case]:
    return [
        Case("wasm_host_oracle", _oracle_wasm_host, lane="any"),
        Case("wasm_host_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("wasm_host_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
