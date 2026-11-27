# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracles and native C17 controls for `AttestedSession.v` and `attested-tls/`."""

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
ATLS_DIR = ROOT / "attested-tls"
ATLS_H = ATLS_DIR / "include" / "vos_attested_tls.h"
ATLS_C = ATLS_DIR / "src" / "attested_tls.c"
ATLS_TEST_C = ATLS_DIR / "test" / "test_attested_tls.c"
ATLS_README = ATLS_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "AttestedSession.v"

DOMAIN = b"VerifiedOS/Q22c/TLS-attestation/v1"
ROLE = b"tls-attesting-client"
OP_ATTEST_LOCAL = 1


@dataclass(frozen=True, slots=True)
class _OracleProfile:
    domain: bytes = DOMAIN
    attester_role: bytes = ROLE
    attest_operation: int = OP_ATTEST_LOCAL
    challenge_bound: int = 175
    request_bound: int = 128
    evidence_bound: int = 512
    manifest_bound: int = 256
    object_bound: int = 256

    def bounded(self) -> bool:
        return (
            0 < len(self.domain) <= 64
            and 0 < len(self.attester_role) <= 32
            and 0 < self.challenge_bound <= 175
            and 0 < self.request_bound <= 128
            and 0 < self.evidence_bound <= 512
            and 0 < self.manifest_bound <= 256
            and 0 < self.object_bound <= 256
        )


@dataclass(frozen=True, slots=True)
class _OracleContext:
    context_id: int
    unit_id: int
    principal: bytes
    origin: bytes
    exporter: bytes
    handshake_complete: bool = True
    server_authenticated: bool = True
    early_data: bool = False
    resumed: bool = False

    def usable(self) -> bool:
        return (
            self.context_id > 0
            and self.unit_id > 0
            and 0 < len(self.principal) <= 64
            and 0 < len(self.origin) <= 64
            and len(self.exporter) == 32
            and self.handshake_complete
            and self.server_authenticated
            and not self.early_data
            and not self.resumed
        )


@dataclass(frozen=True, slots=True)
class _OracleChallenge:
    unit_scope: int
    nonce: bytes
    origin: bytes
    domain: bytes = DOMAIN


@dataclass(frozen=True, slots=True)
class _OracleEvidence:
    generation: int
    exporter: bytes
    challenge: _OracleChallenge
    principal: bytes
    role: bytes
    alias: bytes | None
    seal_mac: bytes


@dataclass(frozen=True, slots=True)
class _OracleCredential:
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


@dataclass(frozen=True, slots=True)
class _OracleRequest:
    role: bytes
    principal: bytes
    scope: int
    operation: int
    domain: bytes
    request_bytes: bytes


@dataclass(frozen=True, slots=True)
class _OraclePolicy:
    approved_generations: frozenset[int]
    required_principal: bytes
    unit_policy: bool
    expected_alias: bytes | None
    expected_unit: int

    def valid(self) -> bool:
        return (
            bool(self.approved_generations)
            and 0 < len(self.required_principal) <= 64
            and (self.unit_policy == (self.expected_alias is not None))
        )


@dataclass(slots=True)
class _OracleBroker:
    hmac_key: bytes
    server_now: int
    measured: dict[int, int]
    aliases: dict[tuple[bytes, int], bytes]
    account_used: dict[int, int] = field(default_factory=dict)

    def issue_local(
        self,
        profile: _OracleProfile,
        cred: _OracleCredential,
        req: _OracleRequest,
        ctx: _OracleContext,
        chal: _OracleChallenge,
        *,
        request_limit: int = 16,
    ) -> tuple[_OracleEvidence, bytes] | None:
        if not profile.bounded() or not ctx.usable() or not cred.sealed:
            return None
        if (
            req.scope not in (0, 1)
            or req.role != profile.attester_role
            or req.principal != ctx.principal
            or req.scope != chal.unit_scope
            or req.operation != profile.attest_operation
            or req.domain != profile.domain
            or len(req.request_bytes) > profile.request_bound
            or chal.origin != ctx.origin
            or chal.domain != profile.domain
            or not chal.nonce
        ):
            return None
        scope_bit = 2 if req.scope == 1 else 1
        op_bit = 1 << req.operation
        used = self.account_used.get(cred.account_id, 0)
        if (
            cred.unit_id != ctx.unit_id
            or cred.origin != ctx.origin
            or cred.role != req.role
            or cred.principal != req.principal
            or cred.domain != req.domain
            or (cred.scope_mask & scope_bit) == 0
            or (cred.operation_mask & op_bit) == 0
            or len(req.request_bytes) > request_limit
            or used >= cred.use_ceiling
            or self.server_now >= cred.expiry
        ):
            return None
        generation = self.measured.get(ctx.unit_id)
        if generation is None:
            return None
        alias: bytes | None = None
        if chal.unit_scope == 1:
            alias = self.aliases.get((ctx.origin, ctx.unit_id))
            if alias is None:
                return None
        body = _encode_evidence_body(
            profile,
            generation,
            ctx.exporter,
            chal,
            ctx.principal,
            profile.attester_role,
            alias,
        )
        if body is None or len(body) + 32 > profile.evidence_bound:
            return None
        seal_mac = _compute_seal_mac(self.hmac_key, body)
        self.account_used[cred.account_id] = used + 1
        ev = _OracleEvidence(
            generation=generation,
            exporter=ctx.exporter,
            challenge=chal,
            principal=ctx.principal,
            role=profile.attester_role,
            alias=alias,
            seal_mac=seal_mac,
        )
        return ev, body + seal_mac


@dataclass(slots=True)
class _OracleConnection:
    ctx: _OracleContext
    phase: str = "Fresh"
    pending_challenge: _OracleChallenge | None = None
    pending_deadline: int = 0
    used_nonces: list[bytes] = field(default_factory=list)
    used_contexts: list[int] = field(default_factory=list)

    def begin_appraisal(
        self,
        profile: _OracleProfile,
        policy: _OraclePolicy,
        nonce: bytes,
        now: int,
        deadline: int,
    ) -> bytes | None:
        if self.phase != "Fresh":
            return None
        if (
            not profile.bounded()
            or not policy.valid()
            or not self.ctx.usable()
            or not (1 <= len(nonce) <= 32)
            or now >= deadline
            or nonce in self.used_nonces
            or self.ctx.context_id in self.used_contexts
        ):
            self.phase = "Closed"
            return None
        chal = _OracleChallenge(
            unit_scope=1 if policy.unit_policy else 0,
            nonce=nonce,
            origin=self.ctx.origin,
            domain=profile.domain,
        )
        wire = _encode_challenge(profile, chal)
        if wire is None:
            self.phase = "Closed"
            return None
        self.used_nonces.append(nonce)
        self.used_contexts.append(self.ctx.context_id)
        self.pending_challenge = chal
        self.pending_deadline = deadline
        self.phase = "Waiting"
        return wire

    def decide(
        self,
        profile: _OracleProfile,
        policy: _OraclePolicy,
        hmac_key: bytes,
        now: int,
        evidence_wire: bytes | None,
    ) -> bool:
        if self.phase != "Waiting":
            self.phase = "Closed"
            return False
        self.phase = "Closed"
        if (
            not profile.bounded()
            or not policy.valid()
            or not self.ctx.usable()
            or now >= self.pending_deadline
            or evidence_wire is None
            or len(evidence_wire) > profile.evidence_bound
        ):
            return False
        ev = _decode_evidence(profile, evidence_wire)
        if ev is None:
            return False
        body = evidence_wire[:-32]
        if not hmac.compare_digest(_compute_seal_mac(hmac_key, body), ev.seal_mac):
            return False
        if ev.challenge != self.pending_challenge:
            return False
        if not hmac.compare_digest(ev.exporter, self.ctx.exporter):
            return False
        if (
            ev.role != profile.attester_role
            or ev.principal != policy.required_principal
            or ev.generation not in policy.approved_generations
        ):
            return False
        if ev.alias != policy.expected_alias:
            return False
        self.phase = "Open"
        return True

    def fetch_one(
        self,
        profile: _OracleProfile,
        now: int,
        req_wire: bytes,
        manifest_auth: bool,
        object_matches: bool,
        object_bytes: bytes,
    ) -> bytes | None:
        prev = self.phase
        self.phase = "Closed"
        if prev != "Open" or not profile.bounded() or not self.ctx.usable():
            return None
        if now >= self.pending_deadline:
            return None
        req = _decode_fetch_request(profile, req_wire)
        if req is None or len(object_bytes) > profile.object_bound:
            return None
        if not manifest_auth or not object_matches:
            return None
        obj_id, _, expected_digest = req
        digest = hashlib.sha256(object_bytes).digest()
        if not hmac.compare_digest(digest, expected_digest):
            return None
        return _encode_fetch_reply(profile, 0, obj_id, object_bytes, digest)

    def reconnect(self, new_ctx: _OracleContext) -> bool:
        if new_ctx.context_id == self.ctx.context_id or new_ctx.context_id in self.used_contexts:
            self.phase = "Closed"
            return False
        self.ctx = new_ctx
        self.phase = "Fresh"
        self.pending_deadline = 0
        return True


def _encode_challenge(profile: _OracleProfile, chal: _OracleChallenge) -> bytes | None:
    if not profile.bounded():
        return None
    if (
        chal.unit_scope not in (0, 1)
        or not (1 <= len(chal.nonce) <= 32)
        or not (1 <= len(chal.origin) <= 64)
        or not (1 <= len(chal.domain) <= 64)
    ):
        return None
    wire = (
        b"VOSATLC1"
        + bytes([chal.unit_scope])
        + len(chal.nonce).to_bytes(2, "little")
        + len(chal.origin).to_bytes(2, "little")
        + len(chal.domain).to_bytes(2, "little")
        + chal.nonce
        + chal.origin
        + chal.domain
    )
    return wire if len(wire) <= profile.challenge_bound else None


def _decode_challenge(profile: _OracleProfile, wire: bytes) -> _OracleChallenge | None:
    if not profile.bounded() or len(wire) < 15 or len(wire) > profile.challenge_bound:
        return None
    if wire[:8] != b"VOSATLC1":
        return None
    unit_scope = wire[8]
    n_len = int.from_bytes(wire[9:11], "little")
    o_len = int.from_bytes(wire[11:13], "little")
    d_len = int.from_bytes(wire[13:15], "little")
    if (
        unit_scope not in (0, 1)
        or not (1 <= n_len <= 32)
        or not (1 <= o_len <= 64)
        or not (1 <= d_len <= 64)
    ):
        return None
    expected = 15 + n_len + o_len + d_len
    if expected > profile.challenge_bound or len(wire) != expected:
        return None
    off = 15
    nonce = wire[off : off + n_len]
    off += n_len
    origin = wire[off : off + o_len]
    off += o_len
    domain = wire[off : off + d_len]
    return _OracleChallenge(unit_scope, nonce, origin, domain)


def _encode_evidence_body(
    profile: _OracleProfile,
    generation: int,
    exporter: bytes,
    chal: _OracleChallenge,
    principal: bytes,
    role: bytes,
    alias: bytes | None,
) -> bytes | None:
    chal_wire = _encode_challenge(profile, chal)
    if chal_wire is None or len(exporter) != 32:
        return None
    if not (1 <= len(principal) <= 64) or not (1 <= len(role) <= 32):
        return None
    if alias is not None and not (1 <= len(alias) <= 64):
        return None
    has_alias = 1 if alias is not None else 0
    alias_bytes = alias if alias is not None else b""
    body = (
        b"VOSATLE1"
        + generation.to_bytes(8, "little")
        + exporter
        + chal_wire
        + len(principal).to_bytes(2, "little")
        + principal
        + len(role).to_bytes(2, "little")
        + role
        + bytes([has_alias])
        + len(alias_bytes).to_bytes(2, "little")
        + alias_bytes
    )
    return body if len(body) + 32 <= profile.evidence_bound else None


def _decode_evidence(profile: _OracleProfile, wire: bytes) -> _OracleEvidence | None:
    if not profile.bounded() or len(wire) > profile.evidence_bound or len(wire) > 512:
        return None
    if len(wire) < 48 + 18 + 2 + 2 + 3 + 32 or wire[:8] != b"VOSATLE1":
        return None
    generation = int.from_bytes(wire[8:16], "little")
    exporter = wire[16:48]
    off = 48
    if len(wire) - off < 15:
        return None
    n_len = int.from_bytes(wire[off + 9 : off + 11], "little")
    o_len = int.from_bytes(wire[off + 11 : off + 13], "little")
    d_len = int.from_bytes(wire[off + 13 : off + 15], "little")
    chal_len = 15 + n_len + o_len + d_len
    if off + chal_len > len(wire):
        return None
    chal = _decode_challenge(profile, wire[off : off + chal_len])
    if chal is None:
        return None
    off += chal_len
    if off + 2 > len(wire):
        return None
    p_len = int.from_bytes(wire[off : off + 2], "little")
    off += 2
    if not (1 <= p_len <= 64) or off + p_len > len(wire):
        return None
    principal = wire[off : off + p_len]
    off += p_len
    if off + 2 > len(wire):
        return None
    r_len = int.from_bytes(wire[off : off + 2], "little")
    off += 2
    if not (1 <= r_len <= 32) or off + r_len > len(wire):
        return None
    role = wire[off : off + r_len]
    off += r_len
    if off + 3 > len(wire):
        return None
    has_alias = wire[off]
    a_len = int.from_bytes(wire[off + 1 : off + 3], "little")
    off += 3
    if has_alias not in (0, 1):
        return None
    if (has_alias == 0 and a_len != 0) or (has_alias == 1 and not (1 <= a_len <= 64)):
        return None
    if off + a_len + 32 != len(wire):
        return None
    alias = wire[off : off + a_len] if has_alias == 1 else None
    off += a_len
    seal_mac = wire[off : off + 32]
    return _OracleEvidence(generation, exporter, chal, principal, role, alias, seal_mac)


def _compute_seal_mac(hmac_key: bytes, body: bytes) -> bytes:
    claims_digest = hashlib.sha256(body).digest()
    return hmac.new(hmac_key, claims_digest, hashlib.sha256).digest()


def _encode_fetch_request(
    profile: _OracleProfile, obj_id: bytes, manifest_ref: bytes, expected_digest: bytes
) -> bytes | None:
    if not profile.bounded() or len(expected_digest) != 32:
        return None
    if not (1 <= len(obj_id) <= min(64, profile.request_bound)):
        return None
    if not (1 <= len(manifest_ref) <= min(256, profile.manifest_bound)):
        return None
    return (
        b"VOSATLR1"
        + len(obj_id).to_bytes(2, "little")
        + len(manifest_ref).to_bytes(2, "little")
        + expected_digest
        + obj_id
        + manifest_ref
    )


def _decode_fetch_request(
    profile: _OracleProfile, wire: bytes
) -> tuple[bytes, bytes, bytes] | None:
    if not profile.bounded() or len(wire) < 44 or len(wire) > 364 or wire[:8] != b"VOSATLR1":
        return None
    obj_id_len = int.from_bytes(wire[8:10], "little")
    man_len = int.from_bytes(wire[10:12], "little")
    if not (1 <= obj_id_len <= min(64, profile.request_bound)):
        return None
    if not (1 <= man_len <= min(256, profile.manifest_bound)):
        return None
    if len(wire) != 44 + obj_id_len + man_len:
        return None
    return wire[44 : 44 + obj_id_len], wire[44 + obj_id_len :], wire[12:44]


def _encode_fetch_reply(
    profile: _OracleProfile, status: int, obj_id: bytes, obj_bytes: bytes, obj_digest: bytes
) -> bytes | None:
    if not profile.bounded() or status not in (0, 1) or len(obj_digest) != 32:
        return None
    if not (1 <= len(obj_id) <= min(64, profile.request_bound)):
        return None
    if len(obj_bytes) > min(256, profile.object_bound):
        return None
    if status == 1 and (obj_bytes or obj_digest != b"\x00" * 32):
        return None
    return (
        b"VOSATLP1"
        + bytes([status])
        + len(obj_id).to_bytes(2, "little")
        + len(obj_bytes).to_bytes(4, "little")
        + obj_digest
        + obj_id
        + obj_bytes
    )


def _decode_fetch_reply(
    profile: _OracleProfile, wire: bytes
) -> tuple[int, bytes, bytes, bytes] | None:
    if not profile.bounded() or len(wire) < 47 or len(wire) > 367 or wire[:8] != b"VOSATLP1":
        return None
    status = wire[8]
    obj_id_len = int.from_bytes(wire[9:11], "little")
    obj_len = int.from_bytes(wire[11:15], "little")
    digest = wire[15:47]
    if status not in (0, 1) or not (1 <= obj_id_len <= min(64, profile.request_bound)):
        return None
    if obj_len > min(256, profile.object_bound):
        return None
    if status == 1 and (obj_len != 0 or digest != b"\x00" * 32):
        return None
    if len(wire) != 47 + obj_id_len + obj_len:
        return None
    obj_id = wire[47 : 47 + obj_id_len]
    obj_bytes = wire[47 + obj_id_len :]
    if status == 0 and not hmac.compare_digest(hashlib.sha256(obj_bytes).digest(), digest):
        return None
    return status, obj_id, obj_bytes, digest


def _oracle_wire_codecs() -> None:
    """Verify canonical wire codecs, positive bounds, trailing-byte, and length rejections."""
    profile = _OracleProfile()
    ensure(profile.bounded(), "default profile bounded")
    ensure(not replace(profile, challenge_bound=0).bounded(), "zero challenge bound rejected")
    ensure(not replace(profile, request_bound=0).bounded(), "zero request bound rejected")
    ensure(not replace(profile, evidence_bound=0).bounded(), "zero evidence bound rejected")
    ensure(not replace(profile, manifest_bound=0).bounded(), "zero manifest bound rejected")
    ensure(not replace(profile, object_bound=0).bounded(), "zero object bound rejected")

    chal = _OracleChallenge(0, b"n-001", b"service.example", DOMAIN)
    cwire = _encode_challenge(profile, chal)
    ensure(cwire is not None and _decode_challenge(profile, cwire) == chal, "challenge round-trip")
    if cwire is None:
        raise AssertionError("unreachable")
    ensure(_decode_challenge(profile, cwire + b"\x00") is None, "trailing challenge byte rejected")
    ensure(_decode_challenge(profile, cwire[:-1]) is None, "truncated challenge rejected")
    ensure(
        _decode_challenge(profile, cwire[:8] + b"\x02" + cwire[9:]) is None,
        "non-canonical challenge unit_scope rejected",
    )

    payload = b"hello-world"
    digest = hashlib.sha256(payload).digest()
    req_w = _encode_fetch_request(profile, b"obj-1", b"man-v1", digest)
    ensure(req_w is not None and _decode_fetch_request(profile, req_w) is not None, "req round-trip")
    if req_w is None:
        raise AssertionError("unreachable")
    ensure(_decode_fetch_request(profile, req_w + b"\x01") is None, "req trailing byte rejected")

    rep_w = _encode_fetch_reply(profile, 0, b"obj-1", payload, digest)
    ensure(rep_w is not None and _decode_fetch_reply(profile, rep_w) is not None, "rep round-trip")
    if rep_w is None:
        raise AssertionError("unreachable")
    ensure(_decode_fetch_reply(profile, rep_w + b"\x01") is None, "rep trailing byte rejected")
    tampered_rep = rep_w[:-1] + bytes([rep_w[-1] ^ 1])
    ensure(_decode_fetch_reply(profile, tampered_rep) is None, "rep tampered digest rejected")


def _oracle_protocol_matches_attested_session() -> None:
    """Independent Python oracle matching AttestedSession.v across honest and attack cases."""
    profile = _OracleProfile()
    hmac_key = bytes(range(0x70, 0x90))
    broker = _OracleBroker(
        hmac_key=hmac_key,
        server_now=1,
        measured={1: 7, 2: 7},
        aliases={(b"service.example", 1): b"enroll-A", (b"service.example", 2): b"enroll-B"},
    )
    ctx_a = _OracleContext(1, 1, b"service-client", b"service.example", bytes([0x11] * 32))
    ctx_b = _OracleContext(2, 2, b"service-client", b"service.example", bytes([0x22] * 32))
    ctx_a_conc = _OracleContext(3, 1, b"service-client", b"service.example", bytes([0x33] * 32))

    cred_a = _OracleCredential(
        True, 1, ROLE, b"service-client", b"service.example", 3, 2, DOMAIN, 16, 100, 0
    )
    cred_b = _OracleCredential(
        True, 2, ROLE, b"service-client", b"service.example", 3, 2, DOMAIN, 16, 100, 1
    )
    req_sw = _OracleRequest(ROLE, b"service-client", 0, OP_ATTEST_LOCAL, DOMAIN, b"req")
    req_unit = _OracleRequest(ROLE, b"service-client", 1, OP_ATTEST_LOCAL, DOMAIN, b"req")

    pol_sw = _OraclePolicy(frozenset({7}), b"service-client", False, None, 1)
    pol_unit_a = _OraclePolicy(frozenset({7}), b"service-client", True, b"enroll-A", 1)

    # Software policy accepts A, and accepts foreign unit B on B's own session.
    conn_a = _OracleConnection(ctx_a)
    cw_a = conn_a.begin_appraisal(profile, pol_sw, b"n-a", 1, 10)
    ensure(cw_a is not None and conn_a.phase == "Waiting", "begin A sw")
    chal_a = _decode_challenge(profile, cw_a) if cw_a is not None else None
    ensure(chal_a is not None, "decode A chal")
    if chal_a is None:
        raise AssertionError("unreachable")
    issued_a = broker.issue_local(profile, cred_a, req_sw, ctx_a, chal_a)
    ensure(issued_a is not None, "issue A sw")
    if issued_a is None:
        raise AssertionError("unreachable")
    ensure(conn_a.decide(profile, pol_sw, hmac_key, 2, issued_a[1]), "accept A sw")
    ensure(conn_a.phase == "Open", "open A sw")

    # Bounded single fetch then closed, no fallback.
    obj = b"kernel-object"
    req_w = _encode_fetch_request(profile, b"obj-a", b"man-a", hashlib.sha256(obj).digest())
    ensure(req_w is not None, "encode req")
    if req_w is None:
        raise AssertionError("unreachable")
    rep_w = conn_a.fetch_one(profile, 3, req_w, True, True, obj)
    ensure(rep_w is not None and conn_a.phase == "Closed", "single fetch opens and closes")
    ensure(conn_a.fetch_one(profile, 3, req_w, True, True, obj) is None, "second fetch refused")

    # A -> B -> A context reuse refused even with fresh nonce.
    ensure(conn_a.reconnect(ctx_b), "reconnect A -> B")
    ensure(not conn_a.reconnect(ctx_a) and conn_a.phase == "Closed", "A -> B -> A refused")

    # Foreign unit B: accepted under software policy on B's own session, refused under unit policy.
    conn_b_sw = _OracleConnection(ctx_b)
    cw_b_sw = conn_b_sw.begin_appraisal(profile, pol_sw, b"n-b-sw", 1, 10)
    chal_b_sw = _decode_challenge(profile, cw_b_sw) if cw_b_sw is not None else None
    ensure(chal_b_sw is not None, "decode B sw chal")
    if chal_b_sw is None:
        raise AssertionError("unreachable")
    issued_b_sw = broker.issue_local(profile, cred_b, req_sw, ctx_b, chal_b_sw)
    ensure(issued_b_sw is not None, "issue B sw")
    if issued_b_sw is None:
        raise AssertionError("unreachable")
    ensure(conn_b_sw.decide(profile, pol_sw, hmac_key, 2, issued_b_sw[1]), "sw policy admits B")

    conn_b_unit = _OracleConnection(ctx_b)
    cw_b_u = conn_b_unit.begin_appraisal(profile, pol_unit_a, b"n-b-u", 1, 10)
    chal_b_u = _decode_challenge(profile, cw_b_u) if cw_b_u is not None else None
    ensure(chal_b_u is not None, "decode B unit chal")
    if chal_b_u is None:
        raise AssertionError("unreachable")
    issued_b_u = broker.issue_local(profile, cred_b, req_unit, ctx_b, chal_b_u)
    ensure(issued_b_u is not None, "issue B unit")
    if issued_b_u is None:
        raise AssertionError("unreachable")
    ensure(
        not conn_b_unit.decide(profile, pol_unit_a, hmac_key, 2, issued_b_u[1])
        and conn_b_unit.phase == "Closed",
        "unit policy refuses foreign unit B",
    )

    # Parallel-session substitution refused.
    conn_par = _OracleConnection(ctx_a)
    cw_par = conn_par.begin_appraisal(profile, pol_sw, b"n-par", 1, 10)
    chal_par = _decode_challenge(profile, cw_par) if cw_par is not None else None
    if chal_par is None:
        raise AssertionError("unreachable")
    issued_conc = broker.issue_local(profile, cred_a, req_sw, ctx_a_conc, chal_par)
    ensure(issued_conc is not None, "issue concurrent A")
    if issued_conc is None:
        raise AssertionError("unreachable")
    ensure(
        not conn_par.decide(profile, pol_sw, hmac_key, 2, issued_conc[1])
        and conn_par.phase == "Closed",
        "parallel exporter substitution refused",
    )

    # Replay & caller-exporter substitution refusal.
    ensure(
        not _OracleConnection(ctx_a).decide(profile, pol_sw, hmac_key, 2, issued_a[1]),
        "decide outside Waiting refused",
    )
    conn_rep = _OracleConnection(ctx_a)
    conn_rep.begin_appraisal(profile, pol_sw, b"n-fresh-rep", 1, 10)
    ensure(not conn_rep.decide(profile, pol_sw, hmac_key, 2, issued_a[1]), "replay refused")

    # Early-data, resumed, and deadline equality/expiry refusals.
    for bad_ctx in (
        replace(ctx_a, early_data=True),
        replace(ctx_a, resumed=True),
        replace(ctx_a, handshake_complete=False),
        replace(ctx_a, server_authenticated=False),
    ):
        bad_conn = _OracleConnection(bad_ctx)
        ensure(
            bad_conn.begin_appraisal(profile, pol_sw, b"n-bad", 1, 10) is None
            and bad_conn.phase == "Closed",
            "ineligible TLS context refused",
        )
    conn_dl = _OracleConnection(ctx_a)
    cw_dl = conn_dl.begin_appraisal(profile, pol_sw, b"n-dl", 1, 10)
    chal_dl = _decode_challenge(profile, cw_dl) if cw_dl is not None else None
    if chal_dl is None:
        raise AssertionError("unreachable")
    issued_dl = broker.issue_local(profile, cred_a, req_sw, ctx_a, chal_dl)
    if issued_dl is None:
        raise AssertionError("unreachable")
    ensure(
        not conn_dl.decide(profile, pol_sw, hmac_key, 10, issued_dl[1])
        and conn_dl.phase == "Closed",
        "deadline equality refused",
    )

    # Broken caller-exporter substitution violates LocalContextIntegrity and is structurally absent
    # from honest issue_local.
    forged_body = _encode_evidence_body(
        profile, 7, ctx_a.exporter, chal_par, ctx_b.principal, ROLE, None
    )
    ensure(forged_body is not None, "forged body built")
    if forged_body is None:
        raise AssertionError("unreachable")
    forged_wire = forged_body + _compute_seal_mac(hmac_key, forged_body)
    forged_ev = _decode_evidence(profile, forged_wire)
    ensure(forged_ev is not None and forged_ev.exporter != ctx_b.exporter, "local integrity breaks")


def _surface_and_proof_contract() -> None:
    """Verify deliverable files, SPDX headers, GC-free C17 rules, and AttestedSession.v symbols."""
    for path in (ATLS_H, ATLS_C, ATLS_TEST_C, ATLS_README, PROOFS_V):
        ensure(path.is_file(), f"missing attested-tls artifact: {path}")

    for c_path in (ATLS_H, ATLS_C, ATLS_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        ensure(
            text.splitlines()[0] == "// SPDX-License-Identifier: Apache-2.0",
            f"missing // SPDX header in {c_path}",
        )
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden dynamic allocation {forbidden} in {c_path}")

    h_src = ATLS_H.read_text(encoding="utf-8")
    c_src = ATLS_C.read_text(encoding="utf-8")
    for fn in (
        "vos_atls_encode_challenge",
        "vos_atls_decode_challenge",
        "vos_atls_encode_evidence",
        "vos_atls_decode_evidence",
        "vos_atls_encode_fetch_request",
        "vos_atls_decode_fetch_request",
        "vos_atls_encode_fetch_reply",
        "vos_atls_decode_fetch_reply",
        "vos_atls_issue_local",
        "vos_atls_begin_appraisal",
        "vos_atls_decide",
        "vos_atls_fetch_one",
        "vos_atls_reconnect",
    ):
        ensure(fn in h_src and fn in c_src, f"missing C entry point {fn}")

    # Verify vos_atls_issue_local signature takes NO caller-supplied exporter parameter.
    sig_match = re.search(r"vos_atls_issue_local\s*\(([^)]*)\)", h_src, re.DOTALL)
    ensure(sig_match is not None, "vos_atls_issue_local prototype present")
    if sig_match is not None:
        ensure("exporter" not in sig_match.group(1), "issue_local must accept no exporter arg")

    # Verify explicit (void) prototypes for zero-arg functions in C sources.
    ensure("main(void)" in ATLS_TEST_C.read_text(encoding="utf-8"), "explicit main(void)")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    ensure(
        v_src.splitlines()[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
        "missing Rocq SPDX header in AttestedSession.v",
    )
    for sym in (
        "issue_local",
        "begin_appraisal",
        "decide",
        "fetch_one",
        "reconnect",
        "attested_session_binding",
        "multi_session_software_agreement",
        "multi_session_unit_agreement",
        "a_context_cycle_cannot_reopen_the_first_tls_connection",
    ):
        ensure(sym in v_src, f"missing Rocq symbol {sym} in AttestedSession.v")
    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in AttestedSession.v",
        )


def _run_c_build_and_test(
    compiler: str, flags: list[str], source_c: Path, out_bin: Path
) -> subprocess.CompletedProcess[str]:
    cmd = [
        compiler,
        *flags,
        f"-I{ATLS_H.parent}",
        f"-I{CRYPTO_INCLUDE}",
        str(source_c),
        str(CRYPTO_SOURCE),
        str(ATLS_TEST_C),
        "-o",
        str(out_bin),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)


def _native_c_and_mutation_controls() -> None:
    """Compile and run `attested-tls` with Clang C17 strict + GCC ASan/UBSan and >= 10 mutants."""
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

    with tempfile.TemporaryDirectory(prefix="vos-attested-tls-c-") as td:
        tmp = Path(td)

        clang_bin = tmp / "test_attested_tls_clang"
        clang_built = _run_c_build_and_test(clang, clang_flags, ATLS_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, check=False, timeout=60
        )
        ensure(
            clang_ran.returncode == 0 and "attested_tls_test: ok" in clang_ran.stdout,
            f"clang binary failed: {clang_ran.stderr or clang_ran.stdout}",
        )

        gcc_bin = tmp / "test_attested_tls_gcc"
        gcc_built = _run_c_build_and_test(gcc, gcc_flags, ATLS_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, check=False, timeout=60
        )
        ensure(
            gcc_ran.returncode == 0 and "attested_tls_test: ok" in gcc_ran.stdout,
            f"gcc ASan/UBSan binary failed: {gcc_ran.stderr or gcc_ran.stdout}",
        )

        source = ATLS_C.read_text(encoding="utf-8")
        mutants: list[tuple[str, str, str]] = [
            (
                "accept-early-data",
                "    if (ctx->early_data != 0u) {\n        return 0;\n    }",
                "    if (0 && ctx->early_data != 0u) {\n        return 0;\n    }",
            ),
            (
                "accept-resumed",
                "    if (ctx->resumed != 0u) {\n        return 0;\n    }",
                "    if (0 && ctx->resumed != 0u) {\n        return 0;\n    }",
            ),
            (
                "accept-trailing-challenge-bytes",
                "    if (allow_prefix ? (wire_len < expected_len) : (wire_len != expected_len)) {",
                "    if (allow_prefix ? (wire_len < expected_len) : (wire_len < expected_len)) {",
            ),
            (
                "accept-trailing-evidence-bytes",
                "    if (off + parsed.alias_len + VOS_ATLS_DIGEST_BYTES != wire_len) {",
                "    if (off + parsed.alias_len + VOS_ATLS_DIGEST_BYTES > wire_len) {",
            ),
            (
                "skip-positive-bounds-check",
                "    if (profile->challenge_bound == 0u ||",
                "    if ((0 && profile->challenge_bound == 0u) ||",
            ),
            (
                "skip-hmac-verify",
                "    if (!equal_bytes_ct(expected_mac, ev.seal_mac, VOS_ATLS_DIGEST_BYTES)) {\n"
                "        return VOS_ATLS_ERR_AUTHENTICITY;\n"
                "    }",
                "    if (0 && !equal_bytes_ct(expected_mac, ev.seal_mac, VOS_ATLS_DIGEST_BYTES)) {\n"
                "        return VOS_ATLS_ERR_AUTHENTICITY;\n"
                "    }",
            ),
            (
                "skip-exporter-check",
                "    if (!equal_bytes_ct(ev.exporter, conn->ctx.exporter, VOS_ATLS_EXPORTER_BYTES)) {\n"
                "        return VOS_ATLS_ERR_EXPORTER_MISMATCH;\n"
                "    }",
                "    if (0 && !equal_bytes_ct(ev.exporter, conn->ctx.exporter, VOS_ATLS_EXPORTER_BYTES)) {\n"
                "        return VOS_ATLS_ERR_EXPORTER_MISMATCH;\n"
                "    }",
            ),
            (
                "skip-unit-alias-check",
                "        if (ev.has_alias != 1u ||\n"
                "            !bytes_equal_exact(ev.alias, ev.alias_len,\n"
                "                               policy->expected_alias, policy->expected_alias_len,\n"
                "                               VOS_ATLS_MAX_ALIAS_BYTES)) {\n"
                "            return VOS_ATLS_ERR_IDENTITY_SCOPE;\n"
                "        }",
                "        if (0 && ev.has_alias != 1u) {\n"
                "            return VOS_ATLS_ERR_IDENTITY_SCOPE;\n"
                "        }",
            ),
            (
                "accept-deadline-equality",
                "    if (now >= conn->pending_deadline) {\n"
                "        return VOS_ATLS_ERR_DEADLINE;\n"
                "    }\n"
                "    if (evidence_wire == NULL || evidence_wire_len == 0u) {",
                "    if (now > conn->pending_deadline) {\n"
                "        return VOS_ATLS_ERR_DEADLINE;\n"
                "    }\n"
                "    if (evidence_wire == NULL || evidence_wire_len == 0u) {",
            ),
            (
                "allow-retry-after-failure",
                "    /* Consume the single attempt before validating evidence; there is no retry. */\n"
                "    conn->phase = VOS_ATLS_PHASE_CLOSED;",
                "    /* Mutation: leave connection WAITING on failure. */\n"
                "    (void)conn;",
            ),
            (
                "allow-context-cycle-reconnect",
                "    if (new_ctx->context_id == conn->ctx.context_id ||\n"
                "        context_in_history(conn, new_ctx->context_id)) {\n"
                "        conn->phase = VOS_ATLS_PHASE_CLOSED;\n"
                "        return VOS_ATLS_ERR_SPENT_CONTEXT;\n"
                "    }",
                "    if (new_ctx->context_id == conn->ctx.context_id) {\n"
                "        conn->phase = VOS_ATLS_PHASE_CLOSED;\n"
                "        return VOS_ATLS_ERR_SPENT_CONTEXT;\n"
                "    }",
            ),
            (
                "allow-second-fetch",
                "    const enum vos_atls_phase prev_phase = conn->phase;\n"
                "    conn->phase = VOS_ATLS_PHASE_CLOSED;",
                "    const enum vos_atls_phase prev_phase = conn->phase;\n"
                "    (void)prev_phase;",
            ),
            (
                "skip-credential-charge",
                "    broker->account_used[credential->account_id] += 1u;",
                "    (void)credential;",
            ),
            (
                "skip-unsealed-credential-check",
                "    if (credential->sealed != 1u) {\n        return VOS_ATLS_ERR_CREDENTIAL_AUTH;\n    }",
                "    if (0 && credential->sealed != 1u) {\n        return VOS_ATLS_ERR_CREDENTIAL_AUTH;\n    }",
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
        Case("attested_tls_wire_codecs_oracle", _oracle_wire_codecs, lane="any"),
        Case(
            "attested_tls_protocol_oracle",
            _oracle_protocol_matches_attested_session,
            lane="any",
        ),
        Case("attested_tls_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case(
            "attested_tls_native_c_and_mutation_controls",
            _native_c_and_mutation_controls,
            lane="guest",
        ),
    ]
