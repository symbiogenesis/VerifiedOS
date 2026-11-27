# SPDX-License-Identifier: Apache-2.0
"""Independent reference oracle and proof audit for `MigrationSession`."""

import re
from dataclasses import dataclass, replace
from typing import Literal

from tests.harness import TOOLS, Case, ensure

INDEPENDENT_CASES = True

ROOT = TOOLS.parent
MIGRATION_V_PATH = ROOT / "proofs" / "MigrationSession.v"

MigrationRole = Literal[
    "migration-source",
    "migration-receiver",
    "backup-key-enrollment",
]
SessionMode = Literal["migration", "enrollment"]
MigrationPhase = Literal[
    "idle",
    "opened",
    "receiver-appraised",
    "mutually-appraised",
    "roots-confirmed",
    "transferred",
    "restore-prepared",
    "published",
    "wrapped",
    "closed",
]
MigrationEventKind = Literal[
    "Open",
    "Quote",
    "Appraise",
    "ConfirmRoots",
    "Transfer",
    "PrepareRestore",
    "Publish",
    "Close",
]

ALL_EVENTS: tuple[MigrationEventKind, ...] = (
    "Open",
    "Quote",
    "Appraise",
    "ConfirmRoots",
    "Transfer",
    "PrepareRestore",
    "Publish",
    "Close",
)


@dataclass(frozen=True)
class ProtectedContext:
    ctx_id: int
    channel: int
    unit: int
    role: MigrationRole
    principal: int
    origin: int
    exporter: int
    handshake_complete: bool = True
    server_authenticated: bool = True
    early_data: bool = False
    resumed: bool = False
    config_fixed: bool = True

    def usable(self) -> bool:
        return (
            self.handshake_complete
            and self.server_authenticated
            and (not self.early_data)
            and (not self.resumed)
            and self.config_fixed
        )


@dataclass(frozen=True)
class MigrationProfile:
    domain: int
    request_bound: int
    evidence_bound: int
    manifest_bound: int
    object_bound: int
    volatile_cap: int
    max_roots: int


@dataclass(frozen=True)
class LocalRuntime:
    measured_gen: dict[int, int]
    ref_manifest: dict[int, int]
    roots: dict[int, tuple[int, ...]]
    enrolled_recipient: dict[tuple[int, int], int]


@dataclass(frozen=True)
class MigrationChallenge:
    nonce: int
    origin: int
    domain: int
    challenger_role: MigrationRole
    target_role: MigrationRole
    source_profile: int
    profile_map: int
    schema_plan: int
    unit_scope: bool


@dataclass(frozen=True)
class MigrationQuote:
    quote_id: int
    role: MigrationRole
    generation: int
    ref_manifest: int
    exporter: int
    challenge: MigrationChallenge
    principal: int
    roots: tuple[int, ...]
    bound_receiver_quote: int | None
    enrolled_recipient: int | None


@dataclass(frozen=True)
class MigrationIssuance:
    quote: MigrationQuote
    issuer_ctx: ProtectedContext


@dataclass(frozen=True)
class MigrationPolicy:
    approved_gens: frozenset[int]
    approved_manifests: frozenset[int]
    required_principal: int
    unit_scope: bool
    expected_enrolled_recipient: int | None
    expected_unit: int


@dataclass(frozen=True)
class ConsentWitness:
    channel_id: int
    roots: tuple[int, ...]
    source_profile: int
    profile_map: int
    schema_plan: int
    source_cred: bool
    receiver_cred: bool


@dataclass(frozen=True)
class VolatileBuffer:
    allocated: bool
    bytes_used: int
    object_id: int | None


@dataclass(frozen=True)
class StorageState:
    current_profile_gen: int
    current_regions_digest: int
    unreachable_staging_digest: int | None
    retained_backup_objects: int
    retained_key_capsules: int
    fresh_epoch_current: bool


@dataclass(frozen=True)
class WrappedKeyHandle:
    recipient: int
    object_id: int
    use_restore_only: bool
    locally_sealed: bool


@dataclass(frozen=True)
class RestorePayload:
    manifest_auth: bool
    source_profile: int
    profile_map: int
    schema_plan: int
    all_schemas_decided: bool
    chunks_verified: bool
    coverage_complete: bool
    staged_digest: int


@dataclass(frozen=True)
class MigrationAttempt:
    mode: SessionMode
    src_ctx: ProtectedContext
    recv_ctx: ProtectedContext
    phase: MigrationPhase
    recv_challenge: MigrationChallenge
    src_challenge: MigrationChallenge
    recv_deadline: int
    src_deadline: int
    used_nonces: tuple[int, ...]
    used_contexts: tuple[int, ...]
    source_profile: int
    profile_map: int
    schema_plan: int
    accepted_recv_quote: MigrationQuote | None
    accepted_src_quote: MigrationQuote | None
    confirmed_roots: tuple[int, ...] | None
    source_cred: bool
    receiver_cred: bool
    consent: ConsentWitness | None
    volatile: VolatileBuffer
    storage: StorageState
    wrapped_key: WrappedKeyHandle | None


@dataclass(frozen=True)
class ByteForwardingRelay:
    hops: tuple[int, ...]
    source: ProtectedContext
    target: ProtectedContext
    quote: MigrationQuote

    def forward_bytes(self, quote: MigrationQuote) -> MigrationQuote:
        return quote

    def same_holder(self) -> bool:
        return same_key_holder(self.source, self.target)


def expected_recv_role(mode: SessionMode) -> MigrationRole:
    return "migration-receiver" if mode == "migration" else "backup-key-enrollment"


def same_key_holder(a: ProtectedContext, b: ProtectedContext) -> bool:
    return (
        a.ctx_id == b.ctx_id
        and a.channel == b.channel
        and a.unit == b.unit
        and a.role == b.role
        and a.principal == b.principal
        and a.origin == b.origin
    )


def empty_volatile() -> VolatileBuffer:
    return VolatileBuffer(allocated=False, bytes_used=0, object_id=None)


def make_idle_attempt(
    mode: SessionMode,
    src_ctx: ProtectedContext,
    recv_ctx: ProtectedContext,
    storage: StorageState,
    used_nonces: tuple[int, ...] = (),
    used_contexts: tuple[int, ...] = (),
) -> MigrationAttempt:
    zero_recv = MigrationChallenge(
        nonce=0,
        origin=src_ctx.origin,
        domain=1,
        challenger_role="migration-source",
        target_role=expected_recv_role(mode),
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        unit_scope=(mode == "enrollment"),
    )
    zero_src = MigrationChallenge(
        nonce=0,
        origin=recv_ctx.origin,
        domain=1,
        challenger_role=expected_recv_role(mode),
        target_role="migration-source",
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        unit_scope=False,
    )
    return MigrationAttempt(
        mode=mode,
        src_ctx=src_ctx,
        recv_ctx=recv_ctx,
        phase="idle",
        recv_challenge=zero_recv,
        src_challenge=zero_src,
        recv_deadline=0,
        src_deadline=0,
        used_nonces=used_nonces,
        used_contexts=used_contexts,
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        accepted_recv_quote=None,
        accepted_src_quote=None,
        confirmed_roots=None,
        source_cred=False,
        receiver_cred=False,
        consent=None,
        volatile=empty_volatile(),
        storage=storage,
        wrapped_key=None,
    )


class MigrationOracle:
    """Independent executable model of MutualMigrationTLS-v1 transitions."""

    def __init__(
        self,
        profile: MigrationProfile,
        src_policy: MigrationPolicy,
        recv_policy: MigrationPolicy,
        runtime: LocalRuntime,
        actual_roots: dict[int, tuple[int, ...]],
        custody: frozenset[ProtectedContext],
    ) -> None:
        self.profile = profile
        self.src_policy = src_policy
        self.recv_policy = recv_policy
        self.runtime = runtime
        self.actual_roots = actual_roots
        self.custody = custody
        self.ledger: list[MigrationIssuance] = []
        self.events: list[tuple[MigrationEventKind, object]] = []

    def open_attempt(
        self,
        attempt: MigrationAttempt,
        recv_nonce: int,
        src_nonce: int,
        now: int,
        ttl_recv: int,
        ttl_src: int,
    ) -> tuple[MigrationAttempt, bool]:
        if attempt.phase != "idle":
            return attempt, False
        if not attempt.src_ctx.usable() or not attempt.recv_ctx.usable():
            return attempt, False
        if attempt.src_ctx.role != "migration-source":
            return attempt, False
        if attempt.recv_ctx.role != expected_recv_role(attempt.mode):
            return attempt, False
        if attempt.src_ctx.channel != attempt.recv_ctx.channel:
            return attempt, False
        if attempt.src_ctx.origin != attempt.recv_ctx.origin:
            return attempt, False
        if attempt.src_ctx.exporter != attempt.recv_ctx.exporter:
            return attempt, False
        if (
            recv_nonce <= 0
            or src_nonce <= 0
            or recv_nonce == src_nonce
            or recv_nonce in attempt.used_nonces
            or src_nonce in attempt.used_nonces
        ):
            return attempt, False
        if (
            attempt.src_ctx.ctx_id == attempt.recv_ctx.ctx_id
            or attempt.src_ctx.ctx_id in attempt.used_contexts
            or attempt.recv_ctx.ctx_id in attempt.used_contexts
        ):
            return attempt, False
        if ttl_recv <= 0 or ttl_src <= 0:
            return attempt, False
        r_ch = MigrationChallenge(
            nonce=recv_nonce,
            origin=attempt.src_ctx.origin,
            domain=self.profile.domain,
            challenger_role="migration-source",
            target_role=expected_recv_role(attempt.mode),
            source_profile=attempt.source_profile,
            profile_map=attempt.profile_map,
            schema_plan=attempt.schema_plan,
            unit_scope=(attempt.mode == "enrollment"),
        )
        s_ch = MigrationChallenge(
            nonce=src_nonce,
            origin=attempt.recv_ctx.origin,
            domain=self.profile.domain,
            challenger_role=expected_recv_role(attempt.mode),
            target_role="migration-source",
            source_profile=attempt.source_profile,
            profile_map=attempt.profile_map,
            schema_plan=attempt.schema_plan,
            unit_scope=False,
        )
        nxt = replace(
            attempt,
            phase="opened",
            recv_challenge=r_ch,
            src_challenge=s_ch,
            recv_deadline=now + ttl_recv,
            src_deadline=now + ttl_src,
            used_nonces=(*attempt.used_nonces, recv_nonce, src_nonce),
            used_contexts=(
                *attempt.used_contexts,
                attempt.src_ctx.ctx_id,
                attempt.recv_ctx.ctx_id,
            ),
        )
        self.events.append(("Open", nxt))
        return nxt, True

    def quote_local(
        self,
        ctx: ProtectedContext,
        quote_id: int,
        challenge: MigrationChallenge,
        bound_recv_quote: int | None,
        *,
        record_in_ledger: bool = True,
    ) -> MigrationIssuance | None:
        if not ctx.usable() or quote_id <= 0:
            return None
        if (
            challenge.origin != ctx.origin
            or challenge.domain != self.profile.domain
            or challenge.target_role != ctx.role
        ):
            return None
        gen = self.runtime.measured_gen.get(ctx.unit)
        manifest = self.runtime.ref_manifest.get(ctx.unit)
        if gen is None or manifest is None:
            return None
        roots: tuple[int, ...] = ()
        enrolled_rec: int | None = None
        if ctx.role == "migration-receiver":
            rt_roots = self.runtime.roots.get(ctx.unit)
            if rt_roots is None or len(rt_roots) == 0 or bound_recv_quote is not None:
                return None
            roots = rt_roots
        elif ctx.role == "backup-key-enrollment":
            rt_roots = self.runtime.roots.get(ctx.unit)
            enrolled_rec = self.runtime.enrolled_recipient.get((ctx.origin, ctx.unit))
            if (
                rt_roots is None
                or len(rt_roots) == 0
                or enrolled_rec is None
                or bound_recv_quote is not None
            ):
                return None
            roots = rt_roots
        else:
            if bound_recv_quote is None or bound_recv_quote <= 0:
                return None
        quote = MigrationQuote(
            quote_id=quote_id,
            role=ctx.role,
            generation=gen,
            ref_manifest=manifest,
            exporter=ctx.exporter,
            challenge=challenge,
            principal=ctx.principal,
            roots=roots,
            bound_receiver_quote=bound_recv_quote,
            enrolled_recipient=enrolled_rec,
        )
        issuance = MigrationIssuance(quote=quote, issuer_ctx=ctx)
        if record_in_ledger:
            self.ledger.append(issuance)
            self.events.append(("Quote", issuance))
        return issuance

    def ledger_authenticates(self, quote: MigrationQuote) -> bool:
        return any(iss.quote == quote for iss in self.ledger)

    def appraise_peer(
        self,
        attempt: MigrationAttempt,
        role: MigrationRole,
        quote: MigrationQuote,
        now: int,
        evidence_size: int,
        *,
        accept_all: bool = False,
    ) -> tuple[MigrationAttempt, bool]:
        auth_ok = True if accept_all else self.ledger_authenticates(quote)
        if attempt.phase == "opened":
            pol = self.recv_policy
            ok = (
                role == expected_recv_role(attempt.mode)
                and attempt.src_ctx.usable()
                and now <= attempt.recv_deadline
                and evidence_size <= self.profile.evidence_bound
                and auth_ok
                and quote.challenge == attempt.recv_challenge
                and quote.exporter == attempt.src_ctx.exporter
                and quote.role == expected_recv_role(attempt.mode)
                and quote.principal == pol.required_principal
                and quote.generation in pol.approved_gens
                and quote.ref_manifest in pol.approved_manifests
                and 0 < len(quote.roots) <= self.profile.max_roots
                and quote.bound_receiver_quote is None
                and (
                    attempt.mode != "enrollment"
                    or (
                        pol.expected_enrolled_recipient is not None
                        and quote.enrolled_recipient == pol.expected_enrolled_recipient
                    )
                )
            )
            if not ok:
                closed, _ = self.close_attempt(attempt)
                return closed, False
            nxt = replace(
                attempt,
                phase="receiver-appraised",
                accepted_recv_quote=quote,
            )
            self.events.append(("Appraise", nxt))
            return nxt, True

        if attempt.phase == "receiver-appraised" and attempt.accepted_recv_quote is not None:
            pol = self.src_policy
            ok = (
                role == "migration-source"
                and attempt.recv_ctx.usable()
                and now <= attempt.src_deadline
                and evidence_size <= self.profile.evidence_bound
                and auth_ok
                and quote.challenge == attempt.src_challenge
                and quote.exporter == attempt.recv_ctx.exporter
                and quote.role == "migration-source"
                and quote.principal == pol.required_principal
                and quote.generation in pol.approved_gens
                and quote.ref_manifest in pol.approved_manifests
                and quote.bound_receiver_quote == attempt.accepted_recv_quote.quote_id
            )
            if not ok:
                closed, _ = self.close_attempt(attempt)
                return closed, False
            nxt = replace(
                attempt,
                phase="mutually-appraised",
                accepted_src_quote=quote,
            )
            self.events.append(("Appraise", nxt))
            return nxt, True

        closed, _ = self.close_attempt(attempt)
        return closed, False

    def confirm_roots(
        self,
        attempt: MigrationAttempt,
        roots: tuple[int, ...],
        consent: ConsentWitness,
    ) -> tuple[MigrationAttempt, bool]:
        if (
            attempt.phase != "mutually-appraised"
            or attempt.accepted_recv_quote is None
            or attempt.accepted_src_quote is None
        ):
            return attempt, False
        recv_q = attempt.accepted_recv_quote
        src_q = attempt.accepted_src_quote
        ok = (
            recv_q.role == expected_recv_role(attempt.mode)
            and src_q.role == "migration-source"
            and consent.source_cred
            and consent.receiver_cred
            and consent.source_profile == attempt.source_profile
            and consent.profile_map == attempt.profile_map
            and consent.schema_plan == attempt.schema_plan
            and consent.channel_id == attempt.src_ctx.channel
            and roots == recv_q.roots
            and consent.roots == roots
            and len(roots) > 0
        )
        if not ok:
            return attempt, False
        nxt = replace(
            attempt,
            phase="roots-confirmed",
            confirmed_roots=roots,
            source_cred=True,
            receiver_cred=True,
            consent=consent,
        )
        self.events.append(("ConfirmRoots", nxt))
        return nxt, True

    def transfer_backup(
        self,
        attempt: MigrationAttempt,
        object_id: int,
        obytes: int,
    ) -> tuple[MigrationAttempt, bool]:
        if (
            attempt.phase != "roots-confirmed"
            or attempt.mode != "migration"
            or attempt.accepted_recv_quote is None
            or attempt.accepted_src_quote is None
            or attempt.confirmed_roots is None
            or attempt.consent is None
        ):
            return attempt, False
        recv_q = attempt.accepted_recv_quote
        src_q = attempt.accepted_src_quote
        ok = (
            recv_q.role == "migration-receiver"
            and src_q.role == "migration-source"
            and attempt.source_cred
            and attempt.receiver_cred
            and attempt.consent.source_cred
            and attempt.consent.receiver_cred
            and attempt.consent.channel_id == attempt.src_ctx.channel
            and attempt.confirmed_roots == recv_q.roots
            and 0 < obytes <= self.profile.volatile_cap
            and attempt.storage.retained_backup_objects == 0
            and attempt.storage.retained_key_capsules == 0
        )
        if not ok:
            return attempt, False
        nxt = replace(
            attempt,
            phase="transferred",
            volatile=VolatileBuffer(allocated=True, bytes_used=obytes, object_id=object_id),
        )
        self.events.append(("Transfer", nxt))
        return nxt, True

    def prepare_restore(
        self,
        attempt: MigrationAttempt,
        payload: RestorePayload,
    ) -> tuple[MigrationAttempt, bool]:
        if (
            attempt.phase != "transferred"
            or attempt.mode != "migration"
            or attempt.accepted_recv_quote is None
            or attempt.accepted_src_quote is None
            or attempt.confirmed_roots is None
            or attempt.consent is None
            or not attempt.volatile.allocated
        ):
            return attempt, False
        ok = (
            attempt.source_cred
            and attempt.receiver_cred
            and payload.manifest_auth
            and payload.source_profile == attempt.source_profile
            and payload.profile_map == attempt.profile_map
            and payload.schema_plan == attempt.schema_plan
            and payload.all_schemas_decided
            and payload.chunks_verified
            and payload.coverage_complete
            and attempt.storage.retained_backup_objects == 0
            and attempt.storage.retained_key_capsules == 0
        )
        if not ok:
            return attempt, False
        nxt = replace(
            attempt,
            phase="restore-prepared",
            storage=replace(
                attempt.storage,
                unreachable_staging_digest=payload.staged_digest,
                retained_backup_objects=0,
                retained_key_capsules=0,
            ),
        )
        self.events.append(("PrepareRestore", nxt))
        return nxt, True

    def publish_restore(self, attempt: MigrationAttempt) -> tuple[MigrationAttempt, bool]:
        if (
            attempt.phase != "restore-prepared"
            or attempt.mode != "migration"
            or attempt.storage.unreachable_staging_digest is None
            or attempt.consent is None
            or not attempt.source_cred
            or not attempt.receiver_cred
            or not attempt.storage.fresh_epoch_current
        ):
            return attempt, False
        staged = attempt.storage.unreachable_staging_digest
        nxt = replace(
            attempt,
            phase="published",
            source_cred=False,
            receiver_cred=False,
            consent=None,
            volatile=empty_volatile(),
            storage=replace(
                attempt.storage,
                current_regions_digest=staged,
                unreachable_staging_digest=None,
                retained_backup_objects=0,
                retained_key_capsules=0,
            ),
        )
        self.events.append(("Publish", nxt))
        return nxt, True

    def wrap_recovery_key(
        self,
        attempt: MigrationAttempt,
        object_id: int,
        recipient: int,
    ) -> tuple[MigrationAttempt, bool]:
        if (
            attempt.phase != "roots-confirmed"
            or attempt.mode != "enrollment"
            or attempt.accepted_recv_quote is None
            or attempt.accepted_src_quote is None
            or attempt.confirmed_roots is None
            or attempt.consent is None
        ):
            return attempt, False
        recv_q = attempt.accepted_recv_quote
        ok = (
            recv_q.role == "backup-key-enrollment"
            and attempt.accepted_src_quote.role == "migration-source"
            and recv_q.enrolled_recipient == recipient
            and attempt.source_cred
            and attempt.receiver_cred
            and attempt.consent.source_cred
            and attempt.consent.receiver_cred
            and attempt.consent.channel_id == attempt.src_ctx.channel
            and attempt.confirmed_roots == recv_q.roots
            and object_id > 0
        )
        if not ok:
            return attempt, False
        nxt = replace(
            attempt,
            phase="wrapped",
            wrapped_key=WrappedKeyHandle(
                recipient=recipient,
                object_id=object_id,
                use_restore_only=True,
                locally_sealed=True,
            ),
        )
        return nxt, True

    def close_attempt(self, attempt: MigrationAttempt) -> tuple[MigrationAttempt, bool]:
        nxt = replace(
            attempt,
            phase="closed",
            source_cred=False,
            receiver_cred=False,
            consent=None,
            volatile=empty_volatile(),
            wrapped_key=None,
        )
        self.events.append(("Close", nxt))
        return nxt, True


def check_exporter_security(custody: frozenset[ProtectedContext]) -> bool:
    ctx_list = list(custody)
    for a in ctx_list:
        for b in ctx_list:
            if (
                a.usable()
                and b.usable()
                and a.exporter == b.exporter
                and a.role == b.role
                and not same_key_holder(a, b)
            ):
                return False
    return True


def check_local_context_integrity(
    profile: MigrationProfile,
    ledger: list[MigrationIssuance],
    runtime: LocalRuntime,
) -> bool:
    for iss in ledger:
        q = iss.quote
        c = iss.issuer_ctx
        if not c.usable() or q.quote_id <= 0:
            return False
        if q.exporter != c.exporter:
            return False
        if runtime.measured_gen.get(c.unit) != q.generation:
            return False
        if runtime.ref_manifest.get(c.unit) != q.ref_manifest:
            return False
        if q.principal != c.principal or q.role != c.role:
            return False
        if q.challenge.origin != c.origin or q.challenge.domain != profile.domain:
            return False
        if q.role == "migration-receiver":
            if runtime.roots.get(c.unit) != q.roots or q.bound_receiver_quote is not None:
                return False
        elif q.role == "backup-key-enrollment":
            if (
                runtime.roots.get(c.unit) != q.roots
                or runtime.enrolled_recipient.get((c.origin, c.unit)) != q.enrolled_recipient
                or q.bound_receiver_quote is not None
            ):
                return False
        elif q.bound_receiver_quote is None:
            return False
    return True


def check_root_set_faithfulness(
    runtime: LocalRuntime,
    actual_roots: dict[int, tuple[int, ...]],
) -> bool:
    return all(actual_roots.get(unit) == roots for unit, roots in runtime.roots.items())


def _base_profile() -> MigrationProfile:
    return MigrationProfile(
        domain=1,
        request_bound=4,
        evidence_bound=16,
        manifest_bound=8,
        object_bound=24,
        volatile_cap=16,
        max_roots=4,
    )


def _base_runtime() -> LocalRuntime:
    return LocalRuntime(
        measured_gen={1: 7, 2: 7, 3: 7, 4: 7},
        ref_manifest={1: 8, 2: 8, 3: 8, 4: 8},
        roots={1: (1, 2), 2: (3, 4), 3: (5, 6), 4: (7, 8)},
        enrolled_recipient={(6, 2): 11, (6, 3): 12},
    )


def _base_actual_roots() -> dict[int, tuple[int, ...]]:
    return {1: (1, 2), 2: (3, 4), 3: (5, 6), 4: (7, 8)}


def _base_storage() -> StorageState:
    return StorageState(
        current_profile_gen=1,
        current_regions_digest=7,
        unreachable_staging_digest=None,
        retained_backup_objects=0,
        retained_key_capsules=0,
        fresh_epoch_current=True,
    )


def _mig_policy() -> MigrationPolicy:
    return MigrationPolicy(
        approved_gens=frozenset({7}),
        approved_manifests=frozenset({8}),
        required_principal=5,
        unit_scope=False,
        expected_enrolled_recipient=None,
        expected_unit=2,
    )


def _enr_policy() -> MigrationPolicy:
    return MigrationPolicy(
        approved_gens=frozenset({7}),
        approved_manifests=frozenset({8}),
        required_principal=5,
        unit_scope=True,
        expected_enrolled_recipient=11,
        expected_unit=2,
    )


def _ctx_s1() -> ProtectedContext:
    return ProtectedContext(
        ctx_id=1, channel=1, unit=1, role="migration-source", principal=5, origin=6, exporter=11
    )


def _ctx_r1() -> ProtectedContext:
    return ProtectedContext(
        ctx_id=2, channel=1, unit=2, role="migration-receiver", principal=5, origin=6, exporter=11
    )


def _ctx_s2() -> ProtectedContext:
    return ProtectedContext(
        ctx_id=3, channel=2, unit=1, role="migration-source", principal=5, origin=6, exporter=12
    )


def _ctx_r2() -> ProtectedContext:
    return ProtectedContext(
        ctx_id=4, channel=2, unit=2, role="migration-receiver", principal=5, origin=6, exporter=12
    )


def _ctx_s_enr() -> ProtectedContext:
    return ProtectedContext(
        ctx_id=5, channel=3, unit=1, role="migration-source", principal=5, origin=6, exporter=13
    )


def _ctx_r_enr() -> ProtectedContext:
    return ProtectedContext(
        ctx_id=6,
        channel=3,
        unit=2,
        role="backup-key-enrollment",
        principal=5,
        origin=6,
        exporter=13,
    )


def _make_oracle(recv_policy: MigrationPolicy | None = None) -> MigrationOracle:
    custody = frozenset(
        {
            _ctx_s1(),
            _ctx_r1(),
            _ctx_s2(),
            _ctx_r2(),
            _ctx_s_enr(),
            _ctx_r_enr(),
        }
    )
    return MigrationOracle(
        profile=_base_profile(),
        src_policy=_mig_policy(),
        recv_policy=_mig_policy() if recv_policy is None else recv_policy,
        runtime=_base_runtime(),
        actual_roots=_base_actual_roots(),
        custody=custody,
    )


def _run_to_confirmed_migration(
    oracle: MigrationOracle,
) -> tuple[MigrationAttempt, MigrationIssuance, MigrationIssuance]:
    att0 = make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage())
    att_open, ok = oracle.open_attempt(att0, recv_nonce=1, src_nonce=2, now=0, ttl_recv=10, ttl_src=10)
    ensure(ok, "open_attempt must succeed")
    iss_r = oracle.quote_local(_ctx_r1(), quote_id=1, challenge=att_open.recv_challenge, bound_recv_quote=None)
    ensure(iss_r is not None, "receiver quote must succeed")
    if iss_r is None:
        raise AssertionError("unreachable")
    att_ra, ok = oracle.appraise_peer(att_open, "migration-receiver", iss_r.quote, now=1, evidence_size=8)
    ensure(ok, "receiver appraisal must succeed")
    iss_s = oracle.quote_local(
        _ctx_s1(), quote_id=2, challenge=att_ra.src_challenge, bound_recv_quote=iss_r.quote.quote_id
    )
    ensure(iss_s is not None, "source quote must succeed")
    if iss_s is None:
        raise AssertionError("unreachable")
    att_ma, ok = oracle.appraise_peer(att_ra, "migration-source", iss_s.quote, now=2, evidence_size=8)
    ensure(ok, "source appraisal must succeed")
    cw = ConsentWitness(
        channel_id=1,
        roots=(3, 4),
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        source_cred=True,
        receiver_cred=True,
    )
    att_conf, ok = oracle.confirm_roots(att_ma, (3, 4), cw)
    ensure(ok, "confirm_roots must succeed")
    return att_conf, iss_r, iss_s


def test_positive_mutual_migration_lifecycle() -> None:
    oracle = _make_oracle()
    att_conf, iss_r, iss_s = _run_to_confirmed_migration(oracle)
    ensure(check_exporter_security(oracle.custody), "custody must satisfy ExporterSecurity")
    ensure(
        check_local_context_integrity(oracle.profile, oracle.ledger, oracle.runtime),
        "ledger must satisfy LocalContextIntegrity",
    )
    ensure(
        check_root_set_faithfulness(oracle.runtime, oracle.actual_roots),
        "runtime must satisfy RootSetFaithfulness",
    )
    ensure(iss_r.quote.role == "migration-receiver", "receiver role mismatch")
    ensure(iss_s.quote.role == "migration-source", "source role mismatch")
    ensure(
        iss_s.quote.bound_receiver_quote == iss_r.quote.quote_id,
        "source quote must bind accepted receiver quote id",
    )

    att_tr, ok = oracle.transfer_backup(att_conf, object_id=5, obytes=12)
    ensure(ok, "transfer_backup must succeed")
    ensure(att_tr.volatile == VolatileBuffer(allocated=True, bytes_used=12, object_id=5), "volatile expected")
    ensure(att_tr.storage.retained_backup_objects == 0, "transfer must write zero retained backup objects")
    ensure(att_tr.storage.retained_key_capsules == 0, "transfer must write zero retained key capsules")

    rp = RestorePayload(
        manifest_auth=True,
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        all_schemas_decided=True,
        chunks_verified=True,
        coverage_complete=True,
        staged_digest=8,
    )
    att_pr, ok = oracle.prepare_restore(att_tr, rp)
    ensure(ok, "prepare_restore must succeed")
    ensure(att_pr.storage.unreachable_staging_digest == 8, "staging digest must be unreachable")
    ensure(att_pr.storage.current_regions_digest == 7, "current profile must remain untouched until publish")

    att_pub, ok = oracle.publish_restore(att_pr)
    ensure(ok, "publish_restore must succeed")
    ensure(att_pub.phase == "published", "phase must be published")
    ensure(att_pub.storage.current_regions_digest == 8, "published regions digest expected")
    ensure(att_pub.storage.unreachable_staging_digest is None, "staging cleared on publish")
    ensure(att_pub.volatile == empty_volatile(), "volatile cleared on publish")
    ensure(att_pub.consent is None, "consent cleared on publish")
    ensure(att_pub.storage.retained_backup_objects == 0, "publish must leave zero retained objects")
    ensure(att_pub.storage.retained_key_capsules == 0, "publish must leave zero retained capsules")

    att_cl, ok = oracle.close_attempt(att_pub)
    ensure(ok and att_cl.phase == "closed", "close must succeed")
    seen_kinds = {kind for kind, _ in oracle.events}
    ensure(seen_kinds == set(ALL_EVENTS), "positive trace must exercise all 8 event kinds")


def test_positive_enrollment_wraps_key_and_refuses_transfer() -> None:
    oracle = _make_oracle(_enr_policy())
    att0 = make_idle_attempt("enrollment", _ctx_s_enr(), _ctx_r_enr(), _base_storage())
    att_open, ok = oracle.open_attempt(att0, recv_nonce=3, src_nonce=4, now=0, ttl_recv=10, ttl_src=10)
    ensure(ok, "enrollment open must succeed")
    iss_r = oracle.quote_local(_ctx_r_enr(), quote_id=3, challenge=att_open.recv_challenge, bound_recv_quote=None)
    ensure(iss_r is not None, "enrollment receiver quote must succeed")
    if iss_r is None:
        raise AssertionError("unreachable")
    ensure(iss_r.quote.role == "backup-key-enrollment", "enrollment role expected")
    ensure(iss_r.quote.enrolled_recipient == 11, "enrolled recipient must be read from runtime")
    att_ra, ok = oracle.appraise_peer(att_open, "backup-key-enrollment", iss_r.quote, now=1, evidence_size=8)
    ensure(ok, "enrollment appraisal must succeed")
    iss_s = oracle.quote_local(
        _ctx_s_enr(), quote_id=4, challenge=att_ra.src_challenge, bound_recv_quote=iss_r.quote.quote_id
    )
    ensure(iss_s is not None, "enrollment source quote must succeed")
    if iss_s is None:
        raise AssertionError("unreachable")
    att_ma, ok = oracle.appraise_peer(att_ra, "migration-source", iss_s.quote, now=2, evidence_size=8)
    ensure(ok, "enrollment source appraisal must succeed")
    cw = ConsentWitness(
        channel_id=3,
        roots=(3, 4),
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        source_cred=True,
        receiver_cred=True,
    )
    att_conf, ok = oracle.confirm_roots(att_ma, (3, 4), cw)
    ensure(ok, "enrollment root confirmation must succeed")

    _, tr_ok = oracle.transfer_backup(att_conf, object_id=5, obytes=12)
    ensure(not tr_ok, "BackupKeyEnrollment must never authorize region transfer")

    att_wrap, ok = oracle.wrap_recovery_key(att_conf, object_id=5, recipient=11)
    ensure(ok, "wrap_recovery_key must succeed for enrolled recipient")
    ensure(
        att_wrap.wrapped_key
        == WrappedKeyHandle(recipient=11, object_id=5, use_restore_only=True, locally_sealed=True),
        "wrapped key handle must bind enrolled recipient with restore-only seal",
    )
    ensure(att_wrap.storage.retained_key_capsules == 0, "no retained key capsules written to storage")


def test_replay_expiry_oversize_and_double_appraisal_refused() -> None:
    oracle = _make_oracle()
    att_conf, iss_r, _ = _run_to_confirmed_migration(oracle)
    att0 = make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage())
    att_open, _ = oracle.open_attempt(att0, recv_nonce=1, src_nonce=2, now=0, ttl_recv=10, ttl_src=10)

    stale_q = replace(iss_r.quote, quote_id=6, challenge=replace(iss_r.quote.challenge, nonce=9))
    att_c1, ok = oracle.appraise_peer(att_open, "migration-receiver", stale_q, now=1, evidence_size=8)
    ensure(not ok and att_c1.phase == "closed", "stale challenge quote must be refused and close")

    att_c2, ok = oracle.appraise_peer(att_open, "migration-receiver", iss_r.quote, now=11, evidence_size=8)
    ensure(not ok and att_c2.phase == "closed", "expired evidence must be refused and close")

    att_c3, ok = oracle.appraise_peer(att_open, "migration-receiver", iss_r.quote, now=1, evidence_size=17)
    ensure(not ok and att_c3.phase == "closed", "oversize evidence must be refused and close")

    att_c4, ok = oracle.appraise_peer(att_conf, "migration-receiver", iss_r.quote, now=1, evidence_size=8)
    ensure(not ok and att_c4.phase == "closed", "already-decided session must refuse re-appraisal and close")


def test_post_restart_challenge_and_context_reuse_refused() -> None:
    oracle = _make_oracle()
    idle_used_nonce = make_idle_attempt(
        "migration", _ctx_s1(), _ctx_r1(), _base_storage(), used_nonces=(1, 2), used_contexts=()
    )
    _, ok_n = oracle.open_attempt(idle_used_nonce, recv_nonce=1, src_nonce=3, now=0, ttl_recv=10, ttl_src=10)
    ensure(not ok_n, "reused nonce after restart must be refused")

    idle_used_ctx = make_idle_attempt(
        "migration", _ctx_s1(), _ctx_r1(), _base_storage(), used_nonces=(), used_contexts=(1, 2)
    )
    _, ok_c = oracle.open_attempt(idle_used_ctx, recv_nonce=3, src_nonce=4, now=0, ttl_recv=10, ttl_src=10)
    ensure(not ok_c, "reused protected context after restart must be refused")


def test_parallel_sessions_repeated_nonce_symbols_and_substitution_refused() -> None:
    oracle = _make_oracle()
    att1, ok1 = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage()),
        recv_nonce=1,
        src_nonce=2,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    att2, ok2 = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s2(), _ctx_r2(), _base_storage()),
        recv_nonce=1,
        src_nonce=2,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    ensure(ok1 and ok2, "two independent parallel sessions with nonce symbol (1, 2) must open")
    iss_r2 = oracle.quote_local(_ctx_r2(), quote_id=10, challenge=att2.recv_challenge, bound_recv_quote=None)
    ensure(iss_r2 is not None, "session 2 receiver quote must succeed")
    if iss_r2 is None:
        raise AssertionError("unreachable")
    _, ok_own = oracle.appraise_peer(att2, "migration-receiver", iss_r2.quote, now=1, evidence_size=8)
    ensure(ok_own, "session 2 accepts its own quote even with repeated nonce symbol")
    closed, ok_sub = oracle.appraise_peer(att1, "migration-receiver", iss_r2.quote, now=1, evidence_size=8)
    ensure(not ok_sub and closed.phase == "closed", "session 1 must refuse session 2 quote (exporter 12 != 11)")


def test_role_reflection_and_misordered_appraisal_refused() -> None:
    oracle = _make_oracle()
    att_open, _ = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage()),
        recv_nonce=1,
        src_nonce=2,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    iss_r = oracle.quote_local(_ctx_r1(), quote_id=1, challenge=att_open.recv_challenge, bound_recv_quote=None)
    ensure(iss_r is not None, "receiver quote must succeed")
    if iss_r is None:
        raise AssertionError("unreachable")
    iss_s = oracle.quote_local(
        _ctx_s1(), quote_id=2, challenge=att_open.src_challenge, bound_recv_quote=iss_r.quote.quote_id
    )
    ensure(iss_s is not None, "source quote must succeed")
    if iss_s is None:
        raise AssertionError("unreachable")

    _, ok_early_src = oracle.appraise_peer(att_open, "migration-source", iss_s.quote, now=1, evidence_size=8)
    ensure(not ok_early_src, "source appraisal before receiver appraisal must be refused")

    _, ok_refl = oracle.appraise_peer(att_open, "migration-receiver", iss_s.quote, now=1, evidence_size=8)
    ensure(not ok_refl, "source quote reflected into receiver slot must be refused")

    att_ra, ok_r = oracle.appraise_peer(att_open, "migration-receiver", iss_r.quote, now=1, evidence_size=8)
    ensure(ok_r, "receiver appraisal succeeds")
    _, ok_bad_bind = oracle.appraise_peer(
        att_ra,
        "migration-source",
        replace(iss_s.quote, bound_receiver_quote=99),
        now=2,
        evidence_size=8,
        accept_all=True,
    )
    ensure(not ok_bad_bind, "source quote without exact accepted receiver quote ID must be refused")


def test_substituted_exporter_refused() -> None:
    oracle = _make_oracle()
    att_open, _ = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage()),
        recv_nonce=1,
        src_nonce=2,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    bad_q = MigrationQuote(
        quote_id=8,
        role="migration-receiver",
        generation=7,
        ref_manifest=8,
        exporter=15,
        challenge=att_open.recv_challenge,
        principal=5,
        roots=(3, 4),
        bound_receiver_quote=None,
        enrolled_recipient=None,
    )
    _, ok = oracle.appraise_peer(att_open, "migration-receiver", bad_q, now=1, evidence_size=8, accept_all=True)
    ensure(not ok, "substituted exporter must be refused")


def test_truncated_substituted_and_oversize_roots_refused() -> None:
    oracle = _make_oracle()
    att_conf, _, _ = _run_to_confirmed_migration(oracle)
    cw_valid = ConsentWitness(
        channel_id=1,
        roots=(3, 4),
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        source_cred=True,
        receiver_cred=True,
    )
    att_open, _ = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage()),
        recv_nonce=5,
        src_nonce=6,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    # Use a fresh mutually appraised attempt by inspecting att_conf components
    att_ma = replace(
        att_conf,
        phase="mutually-appraised",
        confirmed_roots=None,
        source_cred=False,
        receiver_cred=False,
        consent=None,
    )
    _, ok_trunc = oracle.confirm_roots(att_ma, (3,), cw_valid)
    ensure(not ok_trunc, "truncated root set must be refused")

    cw_sub = replace(cw_valid, roots=(3, 9))
    _, ok_sub = oracle.confirm_roots(att_ma, (3, 9), cw_sub)
    ensure(not ok_sub, "substituted root set must be refused")

    oversize_q = MigrationQuote(
        quote_id=9,
        role="migration-receiver",
        generation=7,
        ref_manifest=8,
        exporter=11,
        challenge=att_open.recv_challenge,
        principal=5,
        roots=(3, 4, 5, 6, 7),
        bound_receiver_quote=None,
        enrolled_recipient=None,
    )
    _, ok_over = oracle.appraise_peer(
        att_open, "migration-receiver", oversize_q, now=1, evidence_size=8, accept_all=True
    )
    ensure(not ok_over, "oversize unrenderable root set must be refused")


def test_wrong_enrolled_recipient_refused() -> None:
    oracle = _make_oracle(_enr_policy())
    att_open, _ = oracle.open_attempt(
        make_idle_attempt("enrollment", _ctx_s_enr(), _ctx_r_enr(), _base_storage()),
        recv_nonce=3,
        src_nonce=4,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    wrong_q = MigrationQuote(
        quote_id=10,
        role="backup-key-enrollment",
        generation=7,
        ref_manifest=8,
        exporter=13,
        challenge=att_open.recv_challenge,
        principal=5,
        roots=(5, 6),
        bound_receiver_quote=None,
        enrolled_recipient=12,
    )
    _, ok_app = oracle.appraise_peer(
        att_open, "backup-key-enrollment", wrong_q, now=1, evidence_size=8, accept_all=True
    )
    ensure(not ok_app, "wrong enrolled recipient must be refused during appraisal")

    iss_r = oracle.quote_local(_ctx_r_enr(), quote_id=11, challenge=att_open.recv_challenge, bound_recv_quote=None)
    ensure(iss_r is not None, "enrolled quote must succeed")
    if iss_r is None:
        raise AssertionError("unreachable")
    att_ra, _ = oracle.appraise_peer(att_open, "backup-key-enrollment", iss_r.quote, now=1, evidence_size=8)
    iss_s = oracle.quote_local(
        _ctx_s_enr(), quote_id=12, challenge=att_ra.src_challenge, bound_recv_quote=iss_r.quote.quote_id
    )
    ensure(iss_s is not None, "source quote must succeed")
    if iss_s is None:
        raise AssertionError("unreachable")
    att_ma, _ = oracle.appraise_peer(att_ra, "migration-source", iss_s.quote, now=2, evidence_size=8)
    cw = ConsentWitness(
        channel_id=3, roots=(3, 4), source_profile=1, profile_map=1, schema_plan=1, source_cred=True, receiver_cred=True
    )
    att_conf, _ = oracle.confirm_roots(att_ma, (3, 4), cw)
    _, ok_wrap = oracle.wrap_recovery_key(att_conf, object_id=5, recipient=12)
    ensure(not ok_wrap, "wrap_recovery_key must refuse wrong recipient")


def test_confirm_without_appraisal_missing_creds_and_oversize_volatile_refused() -> None:
    oracle = _make_oracle()
    att_conf, _, _ = _run_to_confirmed_migration(oracle)
    att_open, _ = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage()),
        recv_nonce=1,
        src_nonce=2,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    cw = ConsentWitness(
        channel_id=1, roots=(3, 4), source_profile=1, profile_map=1, schema_plan=1, source_cred=True, receiver_cred=True
    )
    _, ok_open = oracle.confirm_roots(att_open, (3, 4), cw)
    ensure(not ok_open, "confirm_roots before appraisal must fail")

    att_ma = replace(att_conf, phase="mutually-appraised", confirmed_roots=None, source_cred=False, receiver_cred=False, consent=None)
    _, ok_nocred = oracle.confirm_roots(att_ma, (3, 4), replace(cw, receiver_cred=False))
    ensure(not ok_nocred, "missing receiver credential must be refused")

    att_over, ok_over = oracle.transfer_backup(att_conf, object_id=5, obytes=17)
    ensure(not ok_over, "oversize volatile transfer must be refused")
    ensure(att_over.storage.retained_backup_objects == 0, "refused transfer writes zero storage objects")

    att_tr, ok_tr = oracle.transfer_backup(att_conf, object_id=5, obytes=8)
    ensure(ok_tr, "valid transfer succeeds")
    bad_rp = RestorePayload(
        manifest_auth=True,
        source_profile=1,
        profile_map=1,
        schema_plan=1,
        all_schemas_decided=False,
        chunks_verified=True,
        coverage_complete=True,
        staged_digest=8,
    )
    att_bad_pr, ok_pr = oracle.prepare_restore(att_tr, bad_rp)
    ensure(not ok_pr, "unverified/incomplete restore prepare must fail")
    ensure(att_bad_pr.storage.current_regions_digest == 7, "failed prepare preserves current regions digest")


def test_transparent_relay_vs_two_leg_mitm_relay() -> None:
    oracle = _make_oracle()
    att_conf, iss_r, _ = _run_to_confirmed_migration(oracle)
    relay = ByteForwardingRelay(hops=(4, 5), source=iss_r.issuer_ctx, target=att_conf.recv_ctx, quote=iss_r.quote)
    ensure(relay.same_holder(), "transparent relay binds end-to-end key holder")
    ensure(relay.forward_bytes(iss_r.quote) == iss_r.quote, "transparent relay preserves quote bytes")
    ensure(4 not in {att_conf.src_ctx.unit, att_conf.recv_ctx.unit}, "relay hop holds no session key authority")

    ctx_r_leg2 = ProtectedContext(
        ctx_id=9, channel=4, unit=2, role="migration-receiver", principal=5, origin=6, exporter=14
    )
    att_leg1, _ = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage()),
        recv_nonce=1,
        src_nonce=2,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    iss_leg2 = oracle.quote_local(ctx_r_leg2, quote_id=11, challenge=att_leg1.recv_challenge, bound_recv_quote=None)
    ensure(iss_leg2 is not None and iss_leg2.quote.exporter == 14, "leg-2 context binds exporter 14, never 11")
    if iss_leg2 is None:
        raise AssertionError("unreachable")
    _, ok_leg2_on_leg1 = oracle.appraise_peer(
        att_leg1, "migration-receiver", iss_leg2.quote, now=1, evidence_size=8, accept_all=True
    )
    ensure(not ok_leg2_on_leg1, "source leg-1 session must refuse leg-2 quote")

    mitm_q = MigrationQuote(
        quote_id=12,
        role="migration-receiver",
        generation=7,
        ref_manifest=8,
        exporter=11,
        challenge=att_leg1.recv_challenge,
        principal=5,
        roots=(7, 8),
        bound_receiver_quote=None,
        enrolled_recipient=None,
    )
    att_mitm_r, ok_m1 = oracle.appraise_peer(
        att_leg1, "migration-receiver", mitm_q, now=1, evidence_size=8, accept_all=True
    )
    ensure(ok_m1, "attacker MITM unit 4 quote accepted only with attacker's roots (7, 8)")
    iss_s1 = oracle.quote_local(_ctx_s1(), quote_id=13, challenge=att_mitm_r.src_challenge, bound_recv_quote=12)
    ensure(iss_s1 is not None, "source quote issued")
    if iss_s1 is None:
        raise AssertionError("unreachable")
    att_mitm_ma, ok_m2 = oracle.appraise_peer(att_mitm_r, "migration-source", iss_s1.quote, now=2, evidence_size=8)
    ensure(ok_m2, "source appraisal succeeds before root confirmation")
    cw_r = ConsentWitness(
        channel_id=1, roots=(3, 4), source_profile=1, profile_map=1, schema_plan=1, source_cred=True, receiver_cred=True
    )
    _, ok_mitm_conf = oracle.confirm_roots(att_mitm_ma, (3, 4), cw_r)
    ensure(not ok_mitm_conf, "confirming honest receiver roots (3, 4) rejects MITM roots (7, 8)")


def test_broken_premise_compromise_witnesses() -> None:
    colliding = ProtectedContext(
        ctx_id=19, channel=1, unit=4, role="migration-receiver", principal=5, origin=6, exporter=11
    )
    ensure(
        not check_exporter_security(frozenset({_ctx_r1(), colliding})),
        "ExporterSecurity fails when colliding context shares exporter 11",
    )

    oracle = _make_oracle()
    att_open, _ = oracle.open_attempt(
        make_idle_attempt("migration", _ctx_s1(), _ctx_r1(), _base_storage()),
        recv_nonce=1,
        src_nonce=2,
        now=0,
        ttl_recv=10,
        ttl_src=10,
    )
    forged_q = MigrationQuote(
        quote_id=15,
        role="migration-receiver",
        generation=7,
        ref_manifest=8,
        exporter=11,
        challenge=att_open.recv_challenge,
        principal=5,
        roots=(3, 4),
        bound_receiver_quote=None,
        enrolled_recipient=None,
    )
    ensure(not oracle.ledger_authenticates(forged_q), "empty ledger rejects forged quote under EvidenceAuthenticity")
    _, accept_all_ok = oracle.appraise_peer(
        att_open, "migration-receiver", forged_q, now=1, evidence_size=8, accept_all=True
    )
    ensure(accept_all_ok, "breaking EvidenceAuthenticity with accept-all verifier admits unissued quote")

    caller_ctx = ProtectedContext(
        ctx_id=18, channel=4, unit=4, role="migration-receiver", principal=5, origin=6, exporter=15
    )
    caller_iss = MigrationIssuance(quote=forged_q, issuer_ctx=caller_ctx)
    ensure(
        not check_local_context_integrity(_base_profile(), [caller_iss], _base_runtime()),
        "caller-supplied exporter breaks LocalContextIntegrity",
    )

    unfaithful_rt = replace(_base_runtime(), roots={**_base_runtime().roots, 2: (3,)})
    ensure(
        not check_root_set_faithfulness(unfaithful_rt, _base_actual_roots()),
        "truncated runtime root set breaks RootSetFaithfulness",
    )


def _strip_rocq_comments(text: str) -> str:
    out: list[str] = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i] == "(" and text[i + 1] == "*":
            depth += 1
            i += 2
        elif depth > 0 and i + 1 < n and text[i] == "*" and text[i + 1] == ")":
            depth -= 1
            i += 2
        elif depth == 0:
            out.append(text[i])
            i += 1
        else:
            if text[i] == "\n":
                out.append("\n")
            i += 1
    return "".join(out)


def test_migration_session_v_structural_audit() -> None:
    ensure(MIGRATION_V_PATH.is_file(), f"missing {MIGRATION_V_PATH}")
    text = MIGRATION_V_PATH.read_text(encoding="utf-8")
    code = _strip_rocq_comments(text)
    lines = text.splitlines()
    ensure(
        lines[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
        "MigrationSession.v must open with Apache-2.0 SPDX line",
    )
    for req_id in (
        "R-05-163",
        "R-05-164",
        "R-05-165",
        "R-05-166",
        "R-10-040",
        "R-12-015a",
        "R-12-015c",
    ):
        ensure(req_id in text, f"MigrationSession.v missing requirement citation {req_id}")

    forbidden = (
        r"\bAxiom\b",
        r"\bParameter\b",
        r"\bAdmitted\b",
        r"\bSection\b",
        r"\bCoFixpoint\b",
        r"\bCoInductive\b",
        r"\bcofix\b",
        r"\bModule\s+Type\b",
        r"\bSProp\b",
        r"(?m)^\s*Set\s+[A-Z]",
    )
    for pat in forbidden:
        ensure(re.search(pat, code) is None, f"forbidden construct matched {pat}")

    records = re.findall(r"(?m)^Record\s+([A-Za-z0-9_]+)\b", text)
    ensure(len(records) >= 14, f"expected >= 14 Records, found {len(records)}")
    for rec in records:
        ensure(
            re.search(rf"(?m)^Definition\s+witness_{re.escape(rec)}\s*:\s*{re.escape(rec)}\b", text)
            is not None,
            f"missing closed witness_{rec} (R-05-166)",
        )

    proof_starts = len(re.findall(r"(?m)^\s*Proof\.\s*$", text))
    proof_ends = len(re.findall(r"(?m)^\s*(?:Qed|Defined)\.\s*$", text))
    ensure(
        proof_starts == proof_ends and proof_starts >= 45,
        f"mismatched Proof./Qed. counts: {proof_starts} vs {proof_ends}",
    )

    required_decls = (
        "MigrationRole",
        "MigrationEventKind",
        "MigrationTraceEvent",
        "ProtectedContext",
        "MigrationAttempt",
        "quote_local",
        "open_attempt",
        "appraise_peer",
        "confirm_roots",
        "transfer_backup",
        "prepare_restore",
        "publish_restore",
        "wrap_recovery_key",
        "close_attempt",
        "ExporterSecurity",
        "EvidenceAuthenticity",
        "LocalContextIntegrity",
        "RootSetFaithfulness",
        "HonestTrustedPath",
        "UncompromisedKeys",
        "enrollment_role_cannot_authorize_transfer",
        "transfer_uses_volatile_buffer_only_and_zero_storage",
        "close_clears_volatile_buffers_and_revokes_authority",
        "failed_prepare_or_publish_preserves_current_profile",
        "any_step_preserves_zero_retained_migration_objects",
        "root_confirmation_requires_mutual_appraisal",
        "post_restart_context_or_nonce_reuse_is_refused",
        "migration_transfer_agreement",
        "migration_publish_agreement",
        "enrollment_key_wrap_agreement",
        "honest_migration_trace_is_sound",
        "honest_enrollment_trace_is_sound",
        "inhabited_migration_discharges_transfer_and_publish_agreement",
        "replay_expiry_oversize_and_double_appraisal_are_refused",
        "post_restart_challenge_and_context_reuse_are_refused",
        "parallel_session_substitution_is_refused",
        "parallel_sessions_repeated_nonce_symbols_distinguished",
        "role_reflection_and_misordered_appraisal_are_refused",
        "substituted_exporter_is_refused",
        "truncated_substituted_and_oversize_roots_are_refused",
        "wrong_enrolled_recipient_and_transfer_on_enrollment_are_refused",
        "confirm_without_appraisal_missing_creds_and_oversize_volatile_refused",
        "transparent_relay_preserves_agreement_without_key_authority",
        "two_leg_mitm_relay_is_refused",
        "broken_exporter_security_witness",
        "broken_evidence_authenticity_witness",
        "broken_local_context_integrity_witness",
        "broken_root_set_faithfulness_witness",
        "broken_honest_trusted_path_witness",
        "broken_uncompromised_keys_witness",
    )
    for decl in required_decls:
        ensure(
            re.search(rf"\b{re.escape(decl)}\b", text) is not None,
            f"missing required declaration {decl}",
        )


def cases() -> list[Case]:
    return [
        Case("migration_positive_lifecycle", test_positive_mutual_migration_lifecycle),
        Case(
            "migration_enrollment_wrap_and_transfer_refusal",
            test_positive_enrollment_wraps_key_and_refuses_transfer,
        ),
        Case(
            "migration_replay_expiry_oversize_double_appraisal",
            test_replay_expiry_oversize_and_double_appraisal_refused,
        ),
        Case(
            "migration_post_restart_challenge_and_context_reuse",
            test_post_restart_challenge_and_context_reuse_refused,
        ),
        Case(
            "migration_parallel_sessions_and_substitution",
            test_parallel_sessions_repeated_nonce_symbols_and_substitution_refused,
        ),
        Case(
            "migration_role_reflection_and_misordered_appraisal",
            test_role_reflection_and_misordered_appraisal_refused,
        ),
        Case("migration_substituted_exporter_refused", test_substituted_exporter_refused),
        Case(
            "migration_truncated_substituted_oversize_roots",
            test_truncated_substituted_and_oversize_roots_refused,
        ),
        Case("migration_wrong_enrolled_recipient_refused", test_wrong_enrolled_recipient_refused),
        Case(
            "migration_confirm_creds_and_volatile_bounds",
            test_confirm_without_appraisal_missing_creds_and_oversize_volatile_refused,
        ),
        Case("migration_transparent_relay_vs_two_leg_mitm", test_transparent_relay_vs_two_leg_mitm_relay),
        Case("migration_broken_premise_compromise_witnesses", test_broken_premise_compromise_witnesses),
        Case("migration_session_v_structural_audit", test_migration_session_v_structural_audit),
    ]
