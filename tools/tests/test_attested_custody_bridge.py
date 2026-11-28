# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracles, proof-surface checks, and C17 controls for `AttestedCustodyBridge.v` and `session-custody/`."""

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
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
SC_DIR = ROOT / "session-custody"
SC_H = SC_DIR / "include" / "vos_session_custody.h"
SC_C = SC_DIR / "src" / "session_custody.c"
SC_TEST_C = SC_DIR / "test" / "test_session_custody.c"
SC_README = SC_DIR / "README.md"
ATLS_INCLUDE = ROOT / "attested-tls" / "include"
ATLS_SOURCE = ROOT / "attested-tls" / "src" / "attested_tls.c"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
BRIDGE_V = ROOT / "proofs" / "AttestedCustodyBridge.v"

DOMAIN = b"VerifiedOS/Q22c/TLS-attestation/v1"
ROLE = b"tls-attesting-client"
EXPORTER_LABEL = b"EXPORTER-Channel-Binding\x00\x00"


def _derive_channel_binding(traffic_key: bytes) -> bytes:
    """Derive 32-byte EXPORTER-Channel-Binding (empty context) from traffic-key custody."""
    return hmac.new(traffic_key, EXPORTER_LABEL, hashlib.sha256).digest()


def _seal_mac(hmac_key: bytes, body: bytes) -> bytes:
    digest = hashlib.sha256(body).digest()
    return hmac.new(hmac_key, digest, hashlib.sha256).digest()


@dataclass(frozen=True, slots=True)
class _TLSReg:
    unit_id: int
    principal: bytes
    origin: bytes
    config_digest: bytes
    traffic_key: bytes
    handshake_complete: bool = True
    server_authenticated: bool = True
    early_data: bool = False
    resumed: bool = False

    def eligible(self, expected_config_digest: bytes) -> bool:
        return (
            self.unit_id > 0
            and 0 < len(self.principal) <= 64
            and 0 < len(self.origin) <= 64
            and len(self.config_digest) == 32
            and hmac.compare_digest(self.config_digest, expected_config_digest)
            and len(self.traffic_key) == 32
            and any(self.traffic_key)
            and self.handshake_complete
            and self.server_authenticated
            and not self.early_data
            and not self.resumed
        )


@dataclass(frozen=True, slots=True)
class _OpaqueContextHandle:
    slot: int
    context_id: int
    lifecycle_epoch: int
    sealed: bool
    handle_mac: bytes


@dataclass(frozen=True, slots=True)
class _OpaqueCredHandle:
    slot: int
    cred_id: int
    lifecycle_epoch: int
    sealed: bool
    handle_mac: bytes


@dataclass(frozen=True, slots=True)
class _CredentialSpec:
    sealed: bool
    unit_id: int
    role: bytes
    principal: bytes
    origin: bytes
    scope_mask: int
    operation_mask: int
    domain: bytes
    use_ceiling: int
    expiry: int
    account_id: int


@dataclass(slots=True)
class _ContextSlot:
    active: bool
    retired: bool
    key_exposed: bool
    context_id: int
    lifecycle_epoch: int
    unit_id: int
    principal: bytes
    origin: bytes
    config_digest: bytes
    traffic_key: bytes
    derived_exporter: bytes
    handshake_complete: bool
    server_authenticated: bool
    early_data: bool
    resumed: bool


@dataclass(slots=True)
class _CredSlot:
    active: bool
    cred_id: int
    lifecycle_epoch: int
    cred: _CredentialSpec


@dataclass(slots=True)
class _CustodyVaultOracle:
    hmac_key: bytes
    custody_key: bytes
    expected_config_digest: bytes
    server_now: int
    lifecycle_epoch: int = 1
    next_context_id: int = 1
    next_cred_id: int = 1
    contexts: dict[int, _ContextSlot] = field(default_factory=dict)
    creds: dict[int, _CredSlot] = field(default_factory=dict)
    measurements: dict[int, int] = field(default_factory=dict)
    aliases: dict[tuple[bytes, int], bytes] = field(default_factory=dict)
    account_used: dict[int, int] = field(default_factory=dict)
    spent_contexts: set[int] = field(default_factory=set)

    def _ctx_mac(self, slot_idx: int, slot: _ContextSlot) -> bytes:
        msg = (
            b"VOSSCCH1"
            + slot_idx.to_bytes(4, "little")
            + slot.context_id.to_bytes(8, "little")
            + slot.lifecycle_epoch.to_bytes(8, "little")
            + slot.unit_id.to_bytes(8, "little")
            + slot.config_digest
        )
        return hmac.new(self.custody_key, msg, hashlib.sha256).digest()

    def _cred_mac(self, slot_idx: int, slot: _CredSlot) -> bytes:
        msg = (
            b"VOSSCKH1"
            + slot_idx.to_bytes(4, "little")
            + slot.cred_id.to_bytes(8, "little")
            + slot.lifecycle_epoch.to_bytes(8, "little")
            + slot.cred.unit_id.to_bytes(8, "little")
            + slot.cred.account_id.to_bytes(4, "little")
        )
        return hmac.new(self.custody_key, msg, hashlib.sha256).digest()

    def set_measurement(self, unit_id: int, generation: int) -> None:
        self.measurements[unit_id] = generation

    def set_alias(self, origin: bytes, unit_id: int, alias: bytes) -> bool:
        for (orig, uid), existing in self.aliases.items():
            if orig == origin and uid != unit_id and existing == alias:
                return False
        self.aliases[(origin, unit_id)] = alias
        return True

    def register_tls_context(self, reg: _TLSReg) -> _OpaqueContextHandle | None:
        if not reg.eligible(self.expected_config_digest):
            return None
        free_idx: int | None = None
        for idx in range(16):
            existing = self.contexts.get(idx)
            if existing is None or not existing.active:
                free_idx = idx
                break
        if free_idx is None:
            return None
        cid = self.next_context_id
        self.next_context_id += 1
        exporter = _derive_channel_binding(reg.traffic_key)
        slot = _ContextSlot(
            active=True,
            retired=False,
            key_exposed=False,
            context_id=cid,
            lifecycle_epoch=self.lifecycle_epoch,
            unit_id=reg.unit_id,
            principal=reg.principal,
            origin=reg.origin,
            config_digest=reg.config_digest,
            traffic_key=reg.traffic_key,
            derived_exporter=exporter,
            handshake_complete=reg.handshake_complete,
            server_authenticated=reg.server_authenticated,
            early_data=reg.early_data,
            resumed=reg.resumed,
        )
        self.contexts[free_idx] = slot
        return _OpaqueContextHandle(
            slot=free_idx,
            context_id=cid,
            lifecycle_epoch=self.lifecycle_epoch,
            sealed=True,
            handle_mac=self._ctx_mac(free_idx, slot),
        )

    def register_credential(self, cred: _CredentialSpec) -> _OpaqueCredHandle | None:
        if not cred.sealed or cred.unit_id == 0 or cred.account_id >= 8:
            return None
        free_idx: int | None = None
        for idx in range(8):
            existing = self.creds.get(idx)
            if existing is None or not existing.active:
                free_idx = idx
                break
        if free_idx is None:
            return None
        kid = self.next_cred_id
        self.next_cred_id += 1
        slot = _CredSlot(
            active=True,
            cred_id=kid,
            lifecycle_epoch=self.lifecycle_epoch,
            cred=cred,
        )
        self.creds[free_idx] = slot
        return _OpaqueCredHandle(
            slot=free_idx,
            cred_id=kid,
            lifecycle_epoch=self.lifecycle_epoch,
            sealed=True,
            handle_mac=self._cred_mac(free_idx, slot),
        )

    def resolve_context(self, h: _OpaqueContextHandle) -> _ContextSlot | None:
        if not h.sealed or h.lifecycle_epoch != self.lifecycle_epoch:
            return None
        slot = self.contexts.get(h.slot)
        if slot is None or slot.retired or not slot.active or slot.key_exposed:
            return None
        if slot.context_id != h.context_id or slot.lifecycle_epoch != self.lifecycle_epoch:
            return None
        if not hmac.compare_digest(slot.config_digest, self.expected_config_digest):
            return None
        if not slot.handshake_complete or not slot.server_authenticated or slot.early_data or slot.resumed:
            return None
        if not hmac.compare_digest(h.handle_mac, self._ctx_mac(h.slot, slot)):
            return None
        return slot

    def resolve_cred(self, h: _OpaqueCredHandle) -> _CredSlot | None:
        if not h.sealed or h.lifecycle_epoch != self.lifecycle_epoch:
            return None
        slot = self.creds.get(h.slot)
        if slot is None or not slot.active or slot.cred_id != h.cred_id:
            return None
        if not hmac.compare_digest(h.handle_mac, self._cred_mac(h.slot, slot)):
            return None
        return slot

    def teardown_context(self, h: _OpaqueContextHandle) -> bool:
        slot = self.resolve_context(h)
        if slot is None:
            return False
        self.spent_contexts.add(slot.context_id)
        slot.traffic_key = b"\x00" * 32
        slot.derived_exporter = b"\x00" * 32
        slot.active = False
        slot.retired = True
        return True

    def advance_lifecycle(self) -> None:
        for slot in self.contexts.values():
            if slot.active:
                self.spent_contexts.add(slot.context_id)
                slot.traffic_key = b"\x00" * 32
                slot.derived_exporter = b"\x00" * 32
                slot.active = False
                slot.retired = True
        for cslot in self.creds.values():
            cslot.active = False
        self.lifecycle_epoch += 1

    def retire_unit_generation(self, unit_id: int, new_generation: int) -> None:
        self.measurements[unit_id] = new_generation
        for slot in self.contexts.values():
            if slot.active and slot.unit_id == unit_id:
                self.spent_contexts.add(slot.context_id)
                slot.traffic_key = b"\x00" * 32
                slot.derived_exporter = b"\x00" * 32
                slot.active = False
                slot.retired = True

    def mark_key_exposed(self, h: _OpaqueContextHandle) -> bool:
        slot = self.resolve_context(h)
        if slot is None:
            return False
        slot.key_exposed = True
        return True

    def quote_session(
        self,
        cred_h: _OpaqueCredHandle,
        ctx_h: _OpaqueContextHandle,
        unit_scope: int,
        nonce: bytes,
        origin: bytes,
        principal: bytes,
    ) -> tuple[int, bytes, bytes] | None:
        """Issue evidence using ONLY protected context custody; takes no exporter arg."""
        slot = self.resolve_context(ctx_h)
        cslot = self.resolve_cred(cred_h)
        if slot is None or cslot is None:
            return None
        cred = cslot.cred
        if cred.unit_id != slot.unit_id or cred.origin != slot.origin or cred.principal != slot.principal:
            return None
        if principal != slot.principal or origin != slot.origin or not nonce:
            return None
        scope_bit = 2 if unit_scope == 1 else 1
        if (cred.scope_mask & scope_bit) == 0 or (cred.operation_mask & 2) == 0:
            return None
        used = self.account_used.get(cred.account_id, 0)
        if used >= cred.use_ceiling or self.server_now >= cred.expiry:
            return None
        gen = self.measurements.get(slot.unit_id)
        if gen is None:
            return None
        alias: bytes | None = None
        if unit_scope == 1:
            alias = self.aliases.get((slot.origin, slot.unit_id))
            if alias is None:
                return None
        self.account_used[cred.account_id] = used + 1
        body = (
            gen.to_bytes(8, "little")
            + slot.derived_exporter
            + bytes([unit_scope])
            + nonce
            + origin
            + principal
            + (alias if alias is not None else b"")
        )
        return gen, slot.derived_exporter, _seal_mac(self.hmac_key, body)


@dataclass(slots=True)
class _CustodySessionOracle:
    vault: _CustodyVaultOracle
    bound_handle: _OpaqueContextHandle
    bound_slot: _ContextSlot
    expected_config_digest: bytes
    bound_epoch: int
    phase: str = "Fresh"
    attested_open: bool = False
    pending_nonce: bytes = b""
    pending_unit_scope: int = 0
    pending_deadline: int = 0
    used_nonces: set[bytes] = field(default_factory=set)
    spent_contexts: set[int] = field(default_factory=set)

    @classmethod
    def open(
        cls,
        vault: _CustodyVaultOracle,
        h: _OpaqueContextHandle,
        expected_config_digest: bytes,
    ) -> _CustodySessionOracle | None:
        slot = vault.resolve_context(h)
        if slot is None:
            return None
        if not hmac.compare_digest(expected_config_digest, vault.expected_config_digest):
            return None
        if slot.context_id in vault.spent_contexts:
            return None
        return cls(
            vault=vault,
            bound_handle=h,
            bound_slot=slot,
            expected_config_digest=expected_config_digest,
            bound_epoch=vault.lifecycle_epoch,
        )

    def begin(self, unit_scope: int, nonce: bytes, now: int, deadline: int) -> bool:
        if self.phase != "Fresh":
            return False
        slot = self.vault.resolve_context(self.bound_handle)
        if (
            slot is None
            or self.bound_epoch != self.vault.lifecycle_epoch
            or not hmac.compare_digest(self.expected_config_digest, self.vault.expected_config_digest)
            or not nonce
            or now >= deadline
            or nonce in self.used_nonces
            or slot.context_id in self.spent_contexts
            or slot.context_id in self.vault.spent_contexts
        ):
            self.phase = "Closed"
            return False
        self.used_nonces.add(nonce)
        self.spent_contexts.add(slot.context_id)
        self.vault.spent_contexts.add(slot.context_id)
        self.pending_nonce = nonce
        self.pending_unit_scope = unit_scope
        self.pending_deadline = deadline
        self.phase = "Waiting"
        return True

    def decide(
        self,
        now: int,
        gen: int,
        ev_exporter: bytes,
        ev_unit_scope: int,
        ev_nonce: bytes,
        ev_origin: bytes,
        ev_principal: bytes,
        ev_alias: bytes | None,
        ev_mac: bytes,
        approved_gens: set[int],
        required_principal: bytes,
        unit_policy: bool,
        expected_alias: bytes | None,
    ) -> bool:
        if self.phase != "Waiting":
            self.phase = "Closed"
            self.attested_open = False
            return False
        self.phase = "Closed"
        self.attested_open = False
        slot = self.vault.resolve_context(self.bound_handle)
        if (
            slot is None
            or self.bound_epoch != self.vault.lifecycle_epoch
            or not hmac.compare_digest(self.expected_config_digest, self.vault.expected_config_digest)
            or now >= self.pending_deadline
        ):
            return False
        body = (
            gen.to_bytes(8, "little")
            + ev_exporter
            + bytes([ev_unit_scope])
            + ev_nonce
            + ev_origin
            + ev_principal
            + (ev_alias if ev_alias is not None else b"")
        )
        if not hmac.compare_digest(ev_mac, _seal_mac(self.vault.hmac_key, body)):
            return False
        if (
            ev_unit_scope != self.pending_unit_scope
            or ev_nonce != self.pending_nonce
            or ev_origin != slot.origin
            or not hmac.compare_digest(ev_exporter, slot.derived_exporter)
            or ev_principal != required_principal
            or gen not in approved_gens
        ):
            return False
        if unit_policy and ev_alias != expected_alias:
            return False
        if not unit_policy and ev_alias is not None:
            return False
        self.phase = "Open"
        self.attested_open = True
        return True

    def fetch_one(self, manifest_auth: bool, object_match: bool) -> bool:
        was_open = self.attested_open and self.phase == "Open"
        self.phase = "Closed"
        self.attested_open = False
        if not was_open:
            return False
        if self.vault.resolve_context(self.bound_handle) is None:
            return False
        return manifest_auth and object_match

    def reconnect(self, new_h: _OpaqueContextHandle, expected_cfg: bytes) -> bool:
        self.attested_open = False
        slot = self.vault.resolve_context(new_h)
        if (
            slot is None
            or not hmac.compare_digest(expected_cfg, self.vault.expected_config_digest)
            or slot.context_id == self.bound_slot.context_id
            or slot.context_id in self.spent_contexts
            or slot.context_id in self.vault.spent_contexts
        ):
            self.phase = "Closed"
            return False
        self.bound_handle = new_h
        self.bound_slot = slot
        self.expected_config_digest = expected_cfg
        self.bound_epoch = self.vault.lifecycle_epoch
        self.phase = "Fresh"
        self.pending_deadline = 0
        return True


def _oracle_custody_bridge_controls() -> None:
    """Pure-Python reference oracle checking custody bridge invariants and refusals."""
    hmac_key = bytes(range(0x10, 0x30))
    custody_key = bytes(range(0x40, 0x60))
    cfg = bytes(range(0x80, 0xA0))
    wrong_cfg = bytes(range(0xA0, 0xC0))

    vault = _CustodyVaultOracle(hmac_key, custody_key, cfg, server_now=1)
    vault.set_measurement(1, 7)
    vault.set_measurement(2, 7)
    ensure(vault.set_alias(b"service.example", 1, b"enroll-A"), "alias A")
    ensure(vault.set_alias(b"service.example", 2, b"enroll-B"), "alias B")
    ensure(not vault.set_alias(b"service.example", 2, b"enroll-A"), "cross-unit alias collision refused")

    reg_a = _TLSReg(1, b"service-client", b"service.example", cfg, bytes([0x21] * 32))
    reg_a_conc = _TLSReg(1, b"service-client", b"service.example", cfg, bytes([0x22] * 32))
    reg_b = _TLSReg(2, b"service-client", b"service.example", cfg, bytes([0x61] * 32))

    # Ineligible TLS contexts refused.
    ensure(vault.register_tls_context(replace(reg_a, resumed=True)) is None, "resumed refused")
    ensure(vault.register_tls_context(replace(reg_a, early_data=True)) is None, "early_data refused")
    ensure(vault.register_tls_context(replace(reg_a, handshake_complete=False)) is None, "incomplete refused")
    ensure(vault.register_tls_context(replace(reg_a, server_authenticated=False)) is None, "unauth refused")
    ensure(vault.register_tls_context(replace(reg_a, config_digest=wrong_cfg)) is None, "bad cfg refused")

    h_a = vault.register_tls_context(reg_a)
    h_a_conc = vault.register_tls_context(reg_a_conc)
    h_b = vault.register_tls_context(reg_b)
    ensure(h_a is not None and h_a_conc is not None and h_b is not None, "registered A, A_conc, B")
    if h_a is None or h_a_conc is None or h_b is None:
        raise AssertionError("unreachable")

    kh_a = vault.register_credential(
        _CredentialSpec(True, 1, ROLE, b"service-client", b"service.example", 3, 2, DOMAIN, 2, 100, 0)
    )
    kh_b = vault.register_credential(
        _CredentialSpec(True, 2, ROLE, b"service-client", b"service.example", 3, 2, DOMAIN, 2, 100, 1)
    )
    ensure(kh_a is not None and kh_b is not None, "registered cred handles")
    if kh_a is None or kh_b is None:
        raise AssertionError("unreachable")

    # Foreign handle / forged handle MAC refused.
    forged_h = replace(h_a, handle_mac=bytes([h_a.handle_mac[0] ^ 1]) + h_a.handle_mac[1:])
    ensure(_CustodySessionOracle.open(vault, forged_h, cfg) is None, "forged handle refused")
    ensure(_CustodySessionOracle.open(vault, h_a, wrong_cfg) is None, "wrong config digest refused")

    # End-to-end software flow + unauthenticated fetch fallback refusal + single fetch.
    sess = _CustodySessionOracle.open(vault, h_a, cfg)
    ensure(sess is not None, "open A")
    if sess is None:
        raise AssertionError("unreachable")
    ensure(not sess.fetch_one(True, True), "unauthenticated fetch before begin refused")
    sess = _CustodySessionOracle.open(vault, h_a, cfg)
    ensure(sess is not None and sess.begin(0, b"n-1", 1, 10), "begin A")
    if sess is None:
        raise AssertionError("unreachable")
    quoted = vault.quote_session(kh_a, h_a, 0, b"n-1", b"service.example", b"service-client")
    ensure(quoted is not None, "quote A")
    if quoted is None:
        raise AssertionError("unreachable")
    gen, exp, mac = quoted
    ensure(vault.account_used[0] == 1, "credential charge incremented")
    # Parallel session quote fails decide on A.
    quoted_conc = vault.quote_session(kh_a, h_a_conc, 0, b"n-1", b"service.example", b"service-client")
    ensure(quoted_conc is not None, "quote A_conc")
    if quoted_conc is None:
        raise AssertionError("unreachable")
    ensure(
        sess.decide(2, gen, exp, 0, b"n-1", b"service.example", b"service-client", None, mac, {7}, b"service-client", False, None),
        "decide A ok",
    )
    ensure(sess.fetch_one(True, True), "fetch one ok")
    ensure(not sess.fetch_one(True, True), "second fetch refused")

    # A -> B -> A cycle refused.
    ensure(sess.reconnect(h_b, cfg), "reconnect A -> B")
    ensure(not sess.reconnect(h_a, cfg) and sess.phase == "Closed", "A -> B -> A refused")
    ensure(_CustodySessionOracle.open(vault, h_a, cfg) is None, "spent A open refused")

    # Foreign credential unit refused.
    ensure(vault.quote_session(kh_b, h_a_conc, 0, b"n-2", b"service.example", b"service-client") is None, "foreign cred unit refused")

    # Key exposure & teardown & lifecycle invalidation.
    ensure(vault.mark_key_exposed(h_b), "mark B exposed")
    ensure(vault.resolve_context(h_b) is None, "exposed handle invalidated")
    ensure(vault.teardown_context(h_a_conc), "teardown A_conc")
    ensure(vault.resolve_context(h_a_conc) is None, "post-teardown handle invalidated")
    vault.advance_lifecycle()
    ensure(vault.resolve_context(h_a) is None, "lifecycle advance invalidates handles")


def _surface_and_proof_contract() -> None:
    """Verify all 5 non-test deliverables, SPDX headers, C17 rules, and AttestedCustodyBridge.v symbols."""
    for path in (SC_H, SC_C, SC_TEST_C, SC_README, BRIDGE_V):
        ensure(path.is_file(), f"missing deliverable: {path}")

    for c_path in (SC_H, SC_C, SC_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        ensure(
            text.splitlines()[0] == "// SPDX-License-Identifier: Apache-2.0",
            f"missing // SPDX header in {c_path}",
        )
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden dynamic allocation {forbidden} in {c_path}")

    h_src = SC_H.read_text(encoding="utf-8")
    c_src = SC_C.read_text(encoding="utf-8")
    for fn in (
        "vos_sc_vault_init",
        "vos_sc_set_measurement",
        "vos_sc_set_alias",
        "vos_sc_register_tls_context",
        "vos_sc_register_credential",
        "vos_sc_delegate_credential",
        "vos_sc_quote_session",
        "vos_sc_teardown_context",
        "vos_sc_advance_lifecycle",
        "vos_sc_retire_unit_generation",
        "vos_sc_mark_key_exposed",
        "vos_sc_session_open",
        "vos_sc_session_begin",
        "vos_sc_session_decide",
        "vos_sc_session_fetch_one",
        "vos_sc_session_reconnect",
        "vos_sc_session_close",
    ):
        ensure(fn in h_src and fn in c_src, f"missing C entry point {fn}")

    sig_match = re.search(r"vos_sc_quote_session\s*\(([^)]*)\)", h_src, re.DOTALL)
    ensure(sig_match is not None, "vos_sc_quote_session prototype present")
    if sig_match is not None:
        ensure("exporter" not in sig_match.group(1), "quote_session must accept no exporter arg")

    ensure("main(void)" in SC_TEST_C.read_text(encoding="utf-8"), "explicit main(void)")

    v_src = BRIDGE_V.read_text(encoding="utf-8")
    ensure(
        v_src.splitlines()[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
        "missing Rocq SPDX header in AttestedCustodyBridge.v",
    )
    ensure(
        "Require ProofSupport CredentialHandles AttestedSession." in v_src,
        "AttestedCustodyBridge.v must Require ProofSupport CredentialHandles AttestedSession",
    )
    for req_id in ("R-05-163", "R-05-164", "R-05-165", "R-05-166", "R-09-025a", "R-12-015a", "R-12-015c"):
        ensure(req_id in v_src, f"missing requirement citation {req_id}")

    for sym in (
        "refine_context",
        "refine_challenge",
        "refine_evidence",
        "refine_appraiser",
        "refine_session",
        "concrete_quote",
        "concrete_quote_binds_custody_and_charges",
        "concrete_begin_appraisal_refines",
        "concrete_decide_refines",
        "concrete_decide_establishes_session_agreement",
        "concrete_fetch_one_refines",
        "concrete_reconnect_preserves_spent_history",
        "a_to_b_to_a_concrete_cycle_is_refused",
        "teardown_invalidates_handle",
        "advance_lifecycle_invalidates_all_handles",
        "retire_unit_generation_invalidates_unit_handles",
        "concrete_step_forward_simulation",
        "inhabited_positive_software_and_unit_traces",
        "refutation_replay_and_parallel_substitution",
        "refutation_foreign_unit_under_unit_policy",
        "refutation_ineligible_tls_contexts",
        "refutation_post_teardown_and_aba_cycle",
        "refutation_caller_exporter_and_compromise",
    ):
        ensure(sym in v_src, f"missing Rocq symbol {sym} in AttestedCustodyBridge.v")

    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in AttestedCustodyBridge.v",
        )

    records = re.findall(r"^\s*Record\s+([A-Za-z0-9_]+)\b", v_clean, re.MULTILINE)
    ensure(len(records) >= 8, "expected bridge Record declarations")
    for rec in records:
        ensure(
            re.search(rf"\bDefinition\s+witness_{rec}\s*:\s*{rec}\s*:=", v_clean) is not None,
            f"missing witness_{rec} definition",
        )


def _run_c_build_and_test(
    compiler: str, flags: list[str], source_c: Path, out_bin: Path
) -> subprocess.CompletedProcess[str]:
    cmd = [
        compiler,
        *flags,
        f"-I{SC_H.parent}",
        f"-I{ATLS_INCLUDE}",
        f"-I{CRYPTO_INCLUDE}",
        str(source_c),
        str(ATLS_SOURCE),
        str(CRYPTO_SOURCE),
        str(SC_TEST_C),
        "-o",
        str(out_bin),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)


def _native_c_and_mutation_controls() -> None:
    """Compile and run `session-custody` with Clang strict C17 + GCC ASan/UBSan and >= 10 mutants."""
    if sys.platform == "win32":
        return

    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None, "clang compiler must be available in Linux guest")
    ensure(gcc is not None, "gcc compiler must be available in Linux guest")
    if clang is None or gcc is None:
        return

    clang_flags = ["-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes", "-pedantic"]
    gcc_flags = [
        "-std=c17",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wstrict-prototypes",
        "-pedantic",
        "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer",
    ]

    with tempfile.TemporaryDirectory(prefix="vos-session-custody-c-") as td:
        tmp = Path(td)

        clang_bin = tmp / "test_session_custody_clang"
        clang_built = _run_c_build_and_test(clang, clang_flags, SC_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, check=False, timeout=60
        )
        ensure(
            clang_ran.returncode == 0 and "session_custody_test: ok" in clang_ran.stdout,
            f"clang binary failed: {clang_ran.stderr or clang_ran.stdout}",
        )

        gcc_bin = tmp / "test_session_custody_gcc"
        gcc_built = _run_c_build_and_test(gcc, gcc_flags, SC_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, check=False, timeout=60
        )
        ensure(
            gcc_ran.returncode == 0 and "session_custody_test: ok" in gcc_ran.stdout,
            f"gcc ASan/UBSan binary failed: {gcc_ran.stderr or gcc_ran.stdout}",
        )

        source = SC_C.read_text(encoding="utf-8")
        mutants: list[tuple[str, str, str]] = [
            (
                "accept-caller-supplied-exporter",
                "    /* Keep derived_exporter strictly from protected traffic-key custody. */\n"
                "    sc_copy_bytes(pctx.exporter, ctx_slot->derived_exporter, VOS_ATLS_EXPORTER_BYTES);",
                "    /* Mutant: accept 32-byte caller payload as exporter. */\n"
                "    sc_copy_bytes(pctx.exporter,\n"
                "                  (request->request_len == VOS_ATLS_EXPORTER_BYTES)\n"
                "                      ? request->request_bytes\n"
                "                      : ctx_slot->derived_exporter,\n"
                "                  VOS_ATLS_EXPORTER_BYTES);",
            ),
            (
                "allow-aba-context-reuse",
                "    if (sc_id_in_list(vault->spent_contexts, vault->spent_context_count, slot->context_id)) {\n"
                "        return VOS_SC_ERR_SPENT_CONTEXT;\n"
                "    }",
                "    if (0 && sc_id_in_list(vault->spent_contexts, vault->spent_context_count, slot->context_id)) {\n"
                "        return VOS_SC_ERR_SPENT_CONTEXT;\n"
                "    }",
            ),
            (
                "allow-post-teardown-handle-quote",
                "    if (slot->retired != 0u || slot->active != 1u) {\n"
                "        return VOS_SC_ERR_TEARDOWN;\n"
                "    }",
                "    if (0 && slot->retired != 0u && slot->active != 1u) {\n"
                "        return VOS_SC_ERR_TEARDOWN;\n"
                "    }",
            ),
            (
                "accept-resumed-context",
                "    if (reg->resumed != 0u) {\n"
                "        return 0;\n"
                "    }",
                "    if (0 && reg->resumed != 0u) {\n"
                "        return 0;\n"
                "    }",
            ),
            (
                "accept-early-data-context",
                "    if (reg->early_data != 0u) {\n"
                "        return 0;\n"
                "    }",
                "    if (0 && reg->early_data != 0u) {\n"
                "        return 0;\n"
                "    }",
            ),
            (
                "accept-incomplete-handshake",
                "    if (reg->handshake_complete != 1u || reg->server_authenticated != 1u) {\n"
                "        return 0;\n"
                "    }",
                "    if (0 && (reg->handshake_complete != 1u || reg->server_authenticated != 1u)) {\n"
                "        return 0;\n"
                "    }",
            ),
            (
                "skip-credential-use-charge",
                "    vault->account_charges[cred_slot->cred.account_id] += 1u;",
                "    (void)cred_slot;",
            ),
            (
                "accept-cross-unit-alias-collision",
                "            return VOS_SC_ERR_HANDLE_AUTH;\n"
                "        }\n"
                "    }\n"
                "\n"
                "    if (vos_atls_broker_set_alias(",
                "            /* Mutant: ignore cross-unit alias collision. */\n"
                "        }\n"
                "    }\n"
                "\n"
                "    if (vos_atls_broker_set_alias(",
            ),
            (
                "swap-parallel-session-exporter",
                "    const int ok = vos_hmac_sha256(traffic_key, VOS_SC_KEY_BYTES,\n"
                "                                   input, sizeof(input), out_exporter);",
                "    const uint8_t fixed_key[VOS_SC_KEY_BYTES] = { 1u };\n"
                "    (void)traffic_key;\n"
                "    const int ok = vos_hmac_sha256(fixed_key, VOS_SC_KEY_BYTES,\n"
                "                                   input, sizeof(input), out_exporter);",
            ),
            (
                "accept-foreign-handle-lookup",
                "    const enum vos_sc_status mst =\n"
                "        sc_compute_ctx_handle_mac(vault, handle->slot, slot, expected_mac);\n"
                "    if (mst != VOS_SC_OK) {\n"
                "        return mst;\n"
                "    }\n"
                "    if (!sc_equal_bytes_ct(expected_mac, handle->handle_mac, VOS_SC_DIGEST_BYTES)) {\n"
                "        sc_zero_bytes(expected_mac, sizeof(expected_mac));\n"
                "        return VOS_SC_ERR_HANDLE_AUTH;\n"
                "    }",
                "    const enum vos_sc_status mst =\n"
                "        sc_compute_ctx_handle_mac(vault, handle->slot, slot, expected_mac);\n"
                "    if (mst != VOS_SC_OK) {\n"
                "        return mst;\n"
                "    }\n"
                "    if (0 && !sc_equal_bytes_ct(expected_mac, handle->handle_mac, VOS_SC_DIGEST_BYTES)) {\n"
                "        sc_zero_bytes(expected_mac, sizeof(expected_mac));\n"
                "        return VOS_SC_ERR_HANDLE_AUTH;\n"
                "    }",
            ),
            (
                "allow-unauthenticated-fetch-fallback",
                "    if (was_attested_open != 1u) {\n"
                "        vos_atls_close(&session->conn);\n"
                "        return VOS_SC_ERR_CREDENTIAL_AUTH;\n"
                "    }",
                "    if (0 && was_attested_open != 1u) {\n"
                "        vos_atls_close(&session->conn);\n"
                "        return VOS_SC_ERR_CREDENTIAL_AUTH;\n"
                "    }",
            ),
            (
                "ignore-config-digest-mismatch",
                "    if (!sc_equal_bytes_ct(reg->config_digest, vault->expected_config_digest,\n"
                "                           VOS_SC_DIGEST_BYTES)) {\n"
                "        return VOS_SC_ERR_CONFIG_DIGEST;\n"
                "    }",
                "    if (0 && !sc_equal_bytes_ct(reg->config_digest, vault->expected_config_digest,\n"
                "                                VOS_SC_DIGEST_BYTES)) {\n"
                "        return VOS_SC_ERR_CONFIG_DIGEST;\n"
                "    }",
            ),
            (
                "accept-key-exposed-context",
                "    if (slot->key_exposed != 0u) {\n"
                "        return VOS_SC_ERR_KEY_CUSTODY;\n"
                "    }",
                "    if (0 && slot->key_exposed != 0u) {\n"
                "        return VOS_SC_ERR_KEY_CUSTODY;\n"
                "    }",
            ),
        ]

        ensure(len(mutants) >= 10, f"expected >= 10 mutants, got {len(mutants)}")
        for label, target, replacement in mutants:
            ensure(source.count(target) == 1, f"mutant target missing or non-unique: {label}")
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(source.replace(target, replacement, 1), encoding="utf-8")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = _run_c_build_and_test(gcc, gcc_flags, mutant_c, mutant_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mutant_bin)], capture_output=True, text=True, check=False, timeout=60
            )
            ensure(m_ran.returncode != 0, f"mutant survived: {label}")


def cases() -> list[Case]:
    return [
        Case("attested_custody_bridge_oracle", _oracle_custody_bridge_controls, lane="any"),
        Case("attested_custody_bridge_surface_and_proof", _surface_and_proof_contract, lane="any"),
        Case(
            "attested_custody_bridge_native_c_and_mutants",
            _native_c_and_mutation_controls,
            lane="guest",
        ),
    ]
