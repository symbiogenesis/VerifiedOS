# SPDX-License-Identifier: Apache-2.0
"""The two selected attestation-session constructions, with ideal authenticated evidence.

Q22c's part is the TLS 1.3 application binding; Q23c's is the ensemble link session
R-12-015d states. Both are experiments, not protocol implementations, crypto primitives
or proofs. Context and core objects stand for protected local handles; each ledger
stands for unforgeable evidence and its trust chain. Ghost provenance is used only by
each experiment's property oracle, never by a verifier.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from itertools import product
from typing import Literal, override

Scope = Literal["software", "unit"]
DOMAIN = "VerifiedOS/Q22c/TLS-attestation/v1"
ROLE = "tls-attesting-client"
OPERATION = "attest-local-session"


class SessionBindingError(ValueError):
    """A refused transition, with no authenticated-service fallback."""


@dataclass
class Lifecycle:
    authentication_started: bool = False


@dataclass(frozen=True)
class Channel:
    name: str
    unit: str                 # Ghost/local custody, never transmitted as a claim.
    principal: str
    origin: str
    binding: str              # Ideal RFC 9266 tls-exporter value, not a secret.
    complete: bool = True
    server_authenticated: bool = True
    early_data: bool = False
    resumed: bool = False
    lifecycle: Lifecycle = field(default_factory=Lifecycle, compare=False)

    def usable(self) -> bool:
        return (self.complete and self.server_authenticated
                and not self.early_data and not self.resumed)


@dataclass(frozen=True)
class Challenge:
    nonce: str
    origin: str
    scope: Scope
    domain: str = DOMAIN


@dataclass
class Credential:
    unit: str
    principal: str
    origin: str
    scope: Scope
    role: str = ROLE
    operation: str = OPERATION
    domain: str = DOMAIN
    remaining: int = 1
    expires: int = 10          # Fixture-local monotonic tick, not a wall clock.


@dataclass(frozen=True)
class Claims:
    generation: str
    binding: str
    challenge: Challenge
    principal: str
    role: str
    unit_alias: str | None


@dataclass(frozen=True)
class Quote:
    claims: Claims
    seal: int                 # Abstract authenticator; no on-wire format is defined.


@dataclass(frozen=True)
class Issuance:
    quote: Quote
    channel: Channel          # Ghost event provenance, unavailable to the verifier.


class Broker:
    """Only this transition can create authentic evidence in the honest model."""

    def __init__(self, generations: dict[str, str],
                 aliases: dict[tuple[str, str], str]) -> None:
        self.generations = generations
        self.aliases = aliases
        self.ledger: list[Issuance] = []

    def issue(self, credential: Credential, channel: Channel,
              challenge: Challenge, now: int = 0) -> Quote:
        if not channel.usable():
            raise SessionBindingError("ineligible TLS context")
        if (credential.unit, credential.principal) != (channel.unit, channel.principal):
            raise SessionBindingError("credential does not own this local TLS context")
        if (credential.origin != channel.origin or challenge.origin != channel.origin
                or credential.scope != challenge.scope or not challenge.nonce
                or credential.role != ROLE or credential.operation != OPERATION
                or credential.domain != DOMAIN or challenge.domain != DOMAIN):
            raise SessionBindingError("credential scope or protocol context")
        if credential.remaining < 1 or now >= credential.expires:
            raise SessionBindingError("credential use or expiry bound")
        generation = self.generations.get(channel.unit)
        if generation is None:
            raise SessionBindingError("measured state unavailable")
        alias = None
        if challenge.scope == "unit":
            alias = self.aliases.get((channel.origin, channel.unit))
            if alias is None:
                raise SessionBindingError("origin-scoped unit enrollment unavailable")
        claims = Claims(generation, channel.binding, challenge, channel.principal,
                        credential.role, alias)
        quote = Quote(claims, len(self.ledger))
        self.ledger.append(Issuance(quote, channel))
        credential.remaining -= 1
        return quote

    def authentic(self, quote: Quote) -> bool:
        return (0 <= quote.seal < len(self.ledger)
                and self.ledger[quote.seal].quote == quote)


@dataclass(frozen=True)
class Policy:
    scope: Scope
    generations: frozenset[str]
    principal: str = "service-client"
    expected_alias: str | None = None


class Appraisal:
    """One challenge and one decision for one TLS connection/application lifecycle."""

    def __init__(self, channel: Channel, policy: Policy, nonce: str,
                 deadline: int = 5) -> None:
        if not channel.usable() or not nonce or deadline <= 0:
            raise SessionBindingError("cannot open challenge")
        if ((policy.scope == "unit") != (policy.expected_alias is not None)
                or not policy.generations):
            raise SessionBindingError("incomplete or inconsistent appraisal policy")
        if channel.lifecycle.authentication_started:
            raise SessionBindingError("TLS context already owns an authentication lifecycle")
        channel.lifecycle.authentication_started = True
        self.channel = channel
        self.policy = policy
        self.challenge = Challenge(nonce, channel.origin, policy.scope)
        self.deadline = deadline
        self.phase = "waiting"

    def decide(self, quote: Quote | None, broker: Broker, now: int = 1) -> str:
        if self.phase != "waiting":
            return "already-decided"
        self.phase = "closed"  # Every failed check consumes the connection's attempt.
        if now >= self.deadline:
            return "freshness-expired"
        if quote is None or not broker.authentic(quote):
            return "evidence-invalid"
        claims = quote.claims
        if claims.challenge != self.challenge:
            return "challenge-or-context"
        if claims.binding != self.channel.binding:
            return "channel-binding"
        if (claims.role != ROLE or claims.principal != self.policy.principal
                or claims.generation not in self.policy.generations):
            return "appraisal-policy"
        if claims.unit_alias != self.policy.expected_alias:
            return "identity-scope"
        self.phase = "authenticated"
        return "accepted"

    def close(self) -> None:
        self.phase = "closed"


class TrafficKeys:
    """Ideal application-record authentication, separate from public exporter data."""

    def __init__(self, channel: Channel) -> None:
        self.channel = channel.name
        self.holders = {channel.unit}

    def expose_to(self, unit: str) -> None:
        self.holders.add(unit)

    def record_accepted(self, appraisal: Appraisal, sender: str) -> bool:
        return (appraisal.phase == "authenticated" and self.channel == appraisal.channel.name
                and sender in self.holders)


def fixture() -> tuple[Broker, list[Channel]]:
    """Finite names denote different local holders and fresh TLS exporter outputs."""
    units = ("A", "B", "X")
    origins = ("service.example", "other.example")
    aliases = {(origin, unit): f"enrollment-{i}"
               for i, (origin, unit) in enumerate(product(origins, units))}
    broker = Broker({"A": "approved", "B": "approved", "X": "unapproved"}, aliases)
    channels = [Channel(f"connection-{i}", unit, "service-client", origin,
                        f"exporter-{i}")
                for i, (unit, origin, _) in enumerate(product(units, origins, range(2)))]
    return broker, channels


def credential(channel: Channel, scope: Scope = "software") -> Credential:
    return Credential(channel.unit, channel.principal, channel.origin, scope)


def policy(broker: Broker, channel: Channel, scope: Scope) -> Policy:
    # Unit policy enrolls A, even when B or X is the actual TLS endpoint.
    alias = broker.aliases[(channel.origin, "A")] if scope == "unit" else None
    return Policy(scope, frozenset({"approved"}), expected_alias=alias)


@dataclass(frozen=True)
class Scenario:
    name: str
    observed: str
    expected: str
    meaning: str

    @property
    def passed(self) -> bool:
        return self.observed == self.expected


@dataclass(frozen=True)
class Experiment:
    substitutions: int
    accepted: int
    refused: int
    replay_refusals: int
    reopen_refusals: int
    relation_failures: tuple[str, ...]
    scenarios: tuple[Scenario, ...]

    @property
    def passed(self) -> bool:
        return not self.relation_failures and all(case.passed for case in self.scenarios)


def _relation(event: Issuance, target: Appraisal) -> bool:
    """Independent event-level oracle: peer/session agreement, not verifier predicates.

    It reads the issuer's actual unit against the fixture's approved-unit population;
    the verifier has only authenticated claims and its local TLS context.
    """
    return (event.channel.name == target.channel.name
            and event.channel.unit in {"A", "B"}
            and event.quote.claims.challenge == target.challenge
            and (target.policy.scope == "software" or event.channel.unit == "A"))


def _scenarios() -> tuple[Scenario, ...]:
    out: list[Scenario] = []

    def run(name: str, expected: str, meaning: str, *, unit: str = "A",
            scope: Scope = "software", action: str = "honest") -> None:
        broker, channels = fixture()
        a = next(c for c in channels if c.unit == "A")
        ch = next(c for c in channels if c.unit == unit)
        pending = Appraisal(ch, policy(broker, ch, scope), "fresh")
        handle = credential(ch, scope)
        if action == "borrow-context":
            try:
                broker.issue(credential(a, scope), ch, pending.challenge)
                observed = "issued"
            except SessionBindingError:
                observed = "local-custody-refused"
        else:
            issued_challenge = (replace(pending.challenge, nonce="old-fresh")
                                if action == "old-challenge" else pending.challenge)
            quote = broker.issue(handle, ch, issued_challenge)
            now = 1
            if action == "tamper":
                quote = replace(quote, claims=replace(quote.claims, generation="forged"))
            elif action == "expired":
                now = pending.deadline
            elif action == "missing":
                quote = None
            elif action == "compromised-issuer":
                # Outside the honest model: trusted evidence issuance is compromised.
                if quote is None:
                    raise SessionBindingError("compromised-issuer fixture has no quote")
                quote = replace(quote, claims=replace(quote.claims, generation="approved"))
                broker.ledger[quote.seal] = Issuance(quote, ch)
            elif action == "caller-exporter":
                # Deliberately broken API: a healthy A signs X's public exporter.
                if quote is None:
                    raise SessionBindingError("caller-exporter fixture has no quote")
                fake = replace(quote.claims, generation="approved")
                quote = Quote(fake, len(broker.ledger))
                broker.ledger.append(Issuance(quote, a))
            observed = pending.decide(quote, broker, now)
            if action == "key-stolen" and observed == "accepted":
                keys = TrafficKeys(ch)
                if keys.record_accepted(pending, "X"):
                    raise SessionBindingError("attacker held traffic keys before exposure")
                keys.expose_to("X")
                observed = ("attacker-record-accepted" if keys.record_accepted(pending, "X")
                            else "attacker-record-refused")
            if action == "live-exploit" and observed == "accepted":
                # Compromised admitted code uses its legitimate protected key handle.
                keys = TrafficKeys(ch)
                observed = ("compromised-holder-record-accepted"
                            if keys.record_accepted(pending, ch.unit) else "record-refused")
        out.append(Scenario(name, observed, expected, meaning))

    run("direct-software", "accepted", "Approved local key holder authenticates.")
    run("identical-software-other-unit", "accepted", "Software policy admits B.", unit="B")
    run("unit-enrolled", "accepted", "Origin enrollment selects A.", scope="unit")
    run("unit-substitution", "identity-scope", "B cannot meet A's enrollment.",
        unit="B", scope="unit")
    run("transparent-relay", "accepted", "Forwarding preserves A as key holder.")
    run("two-leg-relay", "local-custody-refused", "A cannot attest X's TLS context.",
        unit="X", action="borrow-context")
    run("stale-evidence", "challenge-or-context", "Old quote misses fresh challenge.",
        action="old-challenge")
    run("deadline", "freshness-expired", "Delay consumes this session's availability.",
        action="expired")
    run("withheld-evidence", "evidence-invalid", "No fallback authenticated service.",
        action="missing")
    run("changed-claims", "evidence-invalid", "Authenticated evidence is immutable.",
        action="tamper")
    run("unapproved-generation", "appraisal-policy", "Valid quote can fail policy.", unit="X")
    run("public-exporter-injection", "accepted", "Broken issuer API admits substitution.",
        unit="X", action="caller-exporter")
    run("attestation-key-compromise", "accepted", "False claims survive compromised issuer.",
        unit="X", action="compromised-issuer")
    run("traffic-key-compromise", "attacker-record-accepted",
        "Post-issuance key theft defeats exclusive-holder inference.", action="key-stolen")
    run("measured-code-runtime-exploit", "compromised-holder-record-accepted",
        "A generation measurement is not a live compromise detector.", action="live-exploit")
    return tuple(out)


def experiment() -> Experiment:
    """Enumerate quote delivery across local sessions, origins, scopes and challenges."""
    broker, channels = fixture()
    scopes: tuple[Scope, ...] = ("software", "unit")
    nonces = ("challenge-0", "challenge-1")
    for channel, scope, nonce in product(channels, scopes, nonces):
        broker.issue(credential(channel, scope), channel,
                     Challenge(nonce, channel.origin, scope))
    total = accepted = refused = replays = reopens = 0
    failures: list[str] = []
    for event, channel, scope, nonce in product(broker.ledger, channels, scopes, nonces):
        # Each delivery is an independent run from a fresh pre-appraisal state.
        target_channel = replace(channel, lifecycle=Lifecycle())
        target = Appraisal(target_channel, policy(broker, channel, scope), nonce)
        expected = _relation(event, target)
        verdict = target.decide(event.quote, broker)
        actual = verdict == "accepted"
        total += 1
        accepted += actual
        refused += not actual
        if actual != expected:
            failures.append(f"quote {event.quote.seal} -> {channel.name}/{scope}/{nonce}: {verdict}")
        if target.decide(event.quote, broker) == "already-decided":
            replays += 1
        else:
            failures.append(f"quote {event.quote.seal}: repeated decision accepted")
        try:
            Appraisal(target_channel, target.policy, nonce)
        except SessionBindingError:
            reopens += 1
        else:
            failures.append(f"quote {event.quote.seal}: reconstructed appraisal accepted")
    return Experiment(total, accepted, refused, replays, reopens,
                      tuple(failures), _scenarios())


# ---------------------------------------------------------------------------
# Q23c's ensemble link session (R-12-015d), the second member of inventory row 27.
# ---------------------------------------------------------------------------

ENSEMBLE_DOMAIN = "VerifiedOS/Q23c/ensemble-link-session/v1"
ADMISSIBLE_SUITE = "hybrid-kem-plus-classical/v1"   # R-12-043a's one configuration.
SECOND_SUITE = "classical-only/v1"                  # Offered only to be terminated.
COMPOSITION = "ensemble-identity-1"
PRIOR_COMPOSITION = "ensemble-identity-0"
FOREIGN_COMPOSITION = "ensemble-identity-2"
APPROVED_GENERATIONS = frozenset({"generation-1"})
LINK = "link-ab"
TABLE_AB = "slot-table-digest-ab"
TABLE_MISMATCHED = "slot-table-digest-mismatched"


def device_secret(unit: str) -> str:
    """R-09-022's device-identity secret. Ghost state: no claim ever carries it."""
    return f"device-identity-secret/{unit}"


def rooted_identity(secret: str) -> str:
    """The premise: exactly one signing identity speaks for one device-identity secret.

    Which construction makes that true is undecided in the register, so this stands for
    the relation and derives nothing. The qualification states it as the model's first
    obligation and names its realization as owed.
    """
    return f"quote-signing-identity/{secret}"


def alias_identity(unit: str) -> str:
    """A signing identity a member holds that is rooted in no device-identity secret."""
    return f"alias-signing-identity/{unit}"


@dataclass(frozen=True)
class GenerationRegister:
    """R-09-025a's generation register: what the generation's source determines."""

    generation: str
    ensemble_identity: str      # R-13-001d fixes it at composition.


@dataclass(frozen=True)
class DeviceRegister:
    """R-09-025a's device register, read here for the unit identity alone."""

    unit: str


@dataclass(frozen=True)
class Member:
    """One machine of an ensemble (R-02-003a), with its own die and its own registers."""

    name: str
    generation_register: GenerationRegister
    device_register: DeviceRegister
    slot_digest: str            # Q23d's table, taken here as an opaque digest.

    @property
    def secret(self) -> str:
        return device_secret(self.device_register.unit)


@dataclass(frozen=True)
class EnsembleChallenge:
    """One end's fresh challenge. Each direction supplies its own (R-12-015d)."""

    nonce: str
    link: str
    challenger_unit: str
    domain: str = ENSEMBLE_DOMAIN


@dataclass(frozen=True)
class EnsembleClaims:
    generation_register: GenerationRegister
    device_register: DeviceRegister
    challenge: EnsembleChallenge
    slot_digest: str
    suite: str
    signing_identity: str


@dataclass(frozen=True)
class EnsembleQuote:
    claims: EnsembleClaims
    seal: int                   # Abstract authenticator; no on-wire format is defined.


@dataclass(frozen=True)
class EnsembleIssuance:
    quote: EnsembleQuote
    member: Member              # Ghost provenance: the die that actually signed.
    rooted: bool                # Ghost: signed under its own device-rooted identity.


class IdentityRegistry:
    """What an appraiser consults to decide the model's first obligation.

    It answers only whether a signing identity is the one rooted in a unit's
    device-identity secret. It is a premise of the model, not a mechanism this
    repository has selected.
    """

    def __init__(self, members: Iterable[Member]) -> None:
        self.rooted: dict[str, str] = {
            member.device_register.unit: rooted_identity(member.secret) for member in members}

    def speaks_for(self, unit: str, identity: str) -> bool:
        return self.rooted.get(unit) == identity


class EnsembleBroker:
    """The RoT-backed quote surface. Only this transition makes authentic evidence."""

    def __init__(self) -> None:
        self.ledger: list[EnsembleIssuance] = []

    def issue(self, member: Member, challenge: EnsembleChallenge, *,
              suite: str = ADMISSIBLE_SUITE, claimed_device: DeviceRegister | None = None,
              alias: bool = False) -> EnsembleQuote:
        """Issue a quote over both registers.

        The honest model's one constraint on an attacker: a member signs under the
        identity rooted in its own device-identity secret, or under an alias rooted in
        none. It cannot sign under another unit's rooted identity, so asserting a
        foreign device register forces the alias.
        """
        device = member.device_register if claimed_device is None else claimed_device
        if device != member.device_register and not alias:
            raise SessionBindingError(
                "a member cannot sign another unit's device register under a rooted identity")
        identity = (alias_identity(member.device_register.unit) if alias
                    else rooted_identity(member.secret))
        claims = EnsembleClaims(member.generation_register, device, challenge,
                                member.slot_digest, suite, identity)
        quote = EnsembleQuote(claims, len(self.ledger))
        self.ledger.append(EnsembleIssuance(quote, member, not alias))
        return quote

    def authentic(self, quote: EnsembleQuote) -> bool:
        return (0 <= quote.seal < len(self.ledger)
                and self.ledger[quote.seal].quote == quote)


@dataclass(frozen=True)
class EnsembleEndpoint:
    """One end of a link, with the constants its own attested devicetree names."""

    member: Member
    link: str
    expected_peer_unit: str
    expected_ensemble_identity: str
    approved_generations: frozenset[str] = APPROVED_GENERATIONS


class EnsembleAppraisal:
    """One end's challenge and one decision. Both ends must accept or the link is refused."""

    def __init__(self, end: EnsembleEndpoint, nonce: str, registry: IdentityRegistry,
                 *, bind_identity: bool = True) -> None:
        if not nonce:
            raise SessionBindingError("cannot open an ensemble challenge")
        self.end = end
        self.registry = registry
        self.bind_identity = bind_identity
        self.challenge = EnsembleChallenge(nonce, end.link, end.member.device_register.unit)
        self.phase = "waiting"

    def decide(self, quote: EnsembleQuote | None, broker: EnsembleBroker) -> str:
        if self.phase != "waiting":
            return "already-decided"
        self.phase = "closed"   # Every failed check consumes this establishment attempt.
        if quote is None or not broker.authentic(quote):
            return "evidence-invalid"
        claims = quote.claims
        if claims.challenge != self.challenge:
            return "challenge-or-link"
        if claims.suite != ADMISSIBLE_SUITE:
            return "key-configuration"
        if self.bind_identity and not self.registry.speaks_for(
                claims.device_register.unit, claims.signing_identity):
            return "device-identity-binding"
        if claims.generation_register.ensemble_identity != self.end.expected_ensemble_identity:
            return "ensemble-identity"
        if claims.generation_register.generation not in self.end.approved_generations:
            return "generation-policy"
        if claims.device_register.unit != self.end.expected_peer_unit:
            return "unit-identity"
        if claims.slot_digest != self.end.member.slot_digest:
            return "slot-table-digest"
        self.phase = "authenticated"
        return "accepted"


class CryptoCore:
    """R-15-202/R-05-070: the session keys and every frame operation live here."""

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def _tag(self, link: str, epoch: int, slot: int, payload: str) -> str:
        """An ideal tag over the frame's associated data. No AEAD is implemented."""
        return f"tag({self._secret}|{link}|{epoch}|{slot}|{payload})"

    def seal(self, link: str, epoch: int, slot: int, payload: str) -> LinkFrame:
        return LinkFrame(link, epoch, payload, self._tag(link, epoch, slot, payload), slot)

    def verify(self, frame: LinkFrame, link: str, epoch: int, slot: int) -> bool:
        return frame.tag == self._tag(link, epoch, slot, frame.payload)

    def export(self) -> str:
        """Keys do not leave the core (R-12-015a, R-15-202): there is no export path."""
        raise SessionBindingError("session keys do not leave the crypto core")


@dataclass(frozen=True)
class LinkFrame:
    link: str
    epoch: int
    payload: str
    tag: str
    wire_slot: int   # Ghost only: the established-session grammar carries no slot field.


class EnsembleSession:
    """An established session. Its anti-replay count comes from the schedule, not the wire."""

    def __init__(self, link: str, epoch: int, core: CryptoCore) -> None:
        self.link = link
        self.epoch = epoch
        self.core = core
        self.consumed: set[int] = set()
        self.stopped = False

    def slot_of(self, schedule_slot: int, frame: LinkFrame) -> int:
        """The schedule's own count of this link's slots since the epoch began."""
        return schedule_slot if frame.link == self.link else -1

    def receive(self, frame: LinkFrame, schedule_slot: int) -> str:
        if self.stopped:
            return "link-stopped"
        slot = self.slot_of(schedule_slot, frame)
        if slot in self.consumed:
            return "slot-consumed"      # The window admits at most one frame per slot.
        if not self.core.verify(frame, self.link, self.epoch, slot):
            self.stopped = True         # R-15-228e: a failed tag fail-stops the link.
            return "tag-failed"
        self.consumed.add(slot)
        return "delivered"


class WireCountedSession(EnsembleSession):
    """The counterexample: an endpoint taking the count from the frame, not the schedule."""

    @override
    def slot_of(self, schedule_slot: int, frame: LinkFrame) -> int:
        return frame.wire_slot if schedule_slot >= 0 else -1


@dataclass(frozen=True)
class PeerAct:
    """How one end's peer answers that end's challenge, honest variants and otherwise."""

    member: Member
    suite: str = ADMISSIBLE_SUITE
    claimed_device: DeviceRegister | None = None
    alias: bool = False
    stale: bool = False
    withhold: bool = False


@dataclass(frozen=True)
class Establishment:
    near_verdict: str
    far_verdict: str
    link: str
    epoch: int

    @property
    def outcome(self) -> str:
        if self.near_verdict == "accepted" and self.far_verdict == "accepted":
            return "established"
        failed = self.near_verdict if self.near_verdict != "accepted" else self.far_verdict
        return f"refused-{failed}"

    def session(self) -> EnsembleSession | None:
        if self.outcome != "established":
            return None
        return EnsembleSession(self.link, self.epoch,
                               CryptoCore(f"session-key/{self.link}/{self.epoch}"))


def _answer(broker: EnsembleBroker, act: PeerAct,
            challenge: EnsembleChallenge) -> EnsembleQuote | None:
    if act.withhold:
        return None
    answered = (replace(challenge, nonce="previous-fresh") if act.stale else challenge)
    return broker.issue(act.member, answered, suite=act.suite,
                        claimed_device=act.claimed_device, alias=act.alias)


def establish(near: EnsembleEndpoint, far: EnsembleEndpoint, broker: EnsembleBroker,
              registry: IdentityRegistry, near_answer: PeerAct, far_answer: PeerAct,
              *, offered: tuple[str, ...] = (ADMISSIBLE_SUITE,), bind_identity: bool = True,
              epoch: int = 1, nonces: tuple[str, str] = ("near-fresh", "far-fresh")
              ) -> Establishment:
    """Mutual establishment: two fresh challenges, and both appraisals must accept."""
    if offered != (ADMISSIBLE_SUITE,):
        # R-12-043a: an offered second configuration terminates rather than selecting.
        return Establishment("configuration-negotiated", "configuration-negotiated",
                             near.link, epoch)
    near_side = EnsembleAppraisal(near, nonces[0], registry, bind_identity=bind_identity)
    far_side = EnsembleAppraisal(far, nonces[1], registry, bind_identity=bind_identity)
    near_verdict = near_side.decide(_answer(broker, near_answer, near_side.challenge), broker)
    far_verdict = far_side.decide(_answer(broker, far_answer, far_side.challenge), broker)
    return Establishment(near_verdict, far_verdict, near.link, epoch)


def ensemble_fixture() -> tuple[EnsembleBroker, IdentityRegistry, dict[str, Member],
                                dict[str, EnsembleEndpoint]]:
    """The composition is die-A and die-B at one ensemble identity, joined by one link."""
    def member(name: str, unit: str, generation: str = "generation-1",
               identity: str = COMPOSITION, digest: str = TABLE_AB) -> Member:
        return Member(name, GenerationRegister(generation, identity),
                      DeviceRegister(unit), digest)

    members: dict[str, Member] = {
        "a": member("a", "die-A"),
        "b": member("b", "die-B"),
        "c": member("c", "die-C"),
        "b-prior": member("b-prior", "die-B", identity=PRIOR_COMPOSITION),
        "b-unapproved": member("b-unapproved", "die-B", generation="generation-0"),
        "b-other-table": member("b-other-table", "die-B", digest=TABLE_MISMATCHED),
        "d": member("d", "die-D", identity=FOREIGN_COMPOSITION),
    }
    ends: dict[str, EnsembleEndpoint] = {
        "a": EnsembleEndpoint(members["a"], LINK, "die-B", COMPOSITION),
        "b": EnsembleEndpoint(members["b"], LINK, "die-A", COMPOSITION),
    }
    return EnsembleBroker(), IdentityRegistry(members.values()), members, ends


@dataclass(frozen=True)
class EnsembleExperiment:
    deliveries: int
    accepted: int
    refused: int
    substituted_unit_refusals: int
    foreign_identity_refusals: int
    repeat_refusals: int
    relation_failures: tuple[str, ...]
    scenarios: tuple[Scenario, ...]

    @property
    def passed(self) -> bool:
        return not self.relation_failures and all(case.passed for case in self.scenarios)


def _ensemble_relation(event: EnsembleIssuance, target: EnsembleAppraisal) -> bool:
    """Independent event-level oracle over ghost provenance, not verifier predicates.

    It reads the die that actually signed, its actual registers and its actual slot
    table; the appraiser has only authenticated claims and its own devicetree constants.
    """
    end = target.end
    actual = event.member
    return (actual.device_register.unit == end.expected_peer_unit
            and actual.generation_register.ensemble_identity == end.expected_ensemble_identity
            and actual.generation_register.generation in end.approved_generations
            and actual.slot_digest == end.member.slot_digest
            and event.rooted
            and event.quote.claims.suite == ADMISSIBLE_SUITE
            and event.quote.claims.challenge == target.challenge)


def _ensemble_population() -> tuple[int, int, int, int, int, int, tuple[str, ...]]:
    """Every quote of the issuance population delivered to every candidate appraisal."""
    broker, registry, members, ends = ensemble_fixture()
    nonces = ("challenge-0", "challenge-1")
    suites = (ADMISSIBLE_SUITE, SECOND_SUITE)
    acts: list[PeerAct] = [PeerAct(member) for member in members.values()]
    # The substitution the binding obligation exists to exclude: die-C asserting die-B's
    # device register, which it can sign only under an identity rooted in no secret.
    acts.append(PeerAct(members["c"], claimed_device=DeviceRegister("die-B"), alias=True))
    for act, nonce, challenger, suite in product(acts, nonces, ("die-A", "die-B"), suites):
        broker.issue(act.member, EnsembleChallenge(nonce, LINK, challenger), suite=suite,
                     claimed_device=act.claimed_device, alias=act.alias)
    total = accepted = refused = substituted = foreign = repeats = 0
    failures: list[str] = []
    for event, end_name, nonce in product(broker.ledger, ends, nonces):
        target = EnsembleAppraisal(ends[end_name], nonce, registry)
        expected = _ensemble_relation(event, target)
        verdict = target.decide(event.quote, broker)
        actual = verdict == "accepted"
        total += 1
        accepted += actual
        refused += not actual
        where = f"quote {event.quote.seal} -> end-{end_name}/{nonce}"
        if actual != expected:
            failures.append(f"{where}: {verdict}")
        if event.member.device_register.unit != ends[end_name].expected_peer_unit:
            substituted += not actual
            if actual:
                failures.append(f"{where}: substituted unit accepted")
        if (event.member.generation_register.ensemble_identity
                != ends[end_name].expected_ensemble_identity):
            foreign += not actual
            if actual:
                failures.append(f"{where}: foreign ensemble identity accepted")
        if target.decide(event.quote, broker) == "already-decided":
            repeats += 1
        else:
            failures.append(f"{where}: repeated decision accepted")
    return total, accepted, refused, substituted, foreign, repeats, tuple(failures)


def _ensemble_scenarios() -> tuple[Scenario, ...]:
    out: list[Scenario] = []
    members = ensemble_fixture()[2]

    def record(name: str, observed: str, expected: str, meaning: str) -> None:
        out.append(Scenario(name, observed, expected, meaning))

    def link(near_answer: PeerAct, far_answer: PeerAct | None = None, *,
             bind_identity: bool = True,
             offered: tuple[str, ...] = (ADMISSIBLE_SUITE,)) -> Establishment:
        broker, registry, fresh, ends = ensemble_fixture()
        answer = PeerAct(fresh["a"]) if far_answer is None else far_answer
        return establish(ends["a"], ends["b"], broker, registry, near_answer, answer,
                         offered=offered, bind_identity=bind_identity)

    def honest() -> PeerAct:
        return PeerAct(members["b"])

    def opened(result: Establishment) -> EnsembleSession:
        session = result.session()
        if session is None:
            raise SessionBindingError("this fixture requires an established session")
        return session

    def run(name: str, expected: str, meaning: str, near_answer: PeerAct,
            far_answer: PeerAct | None = None, *, bind_identity: bool = True,
            offered: tuple[str, ...] = (ADMISSIBLE_SUITE,)) -> None:
        result = link(near_answer, far_answer, bind_identity=bind_identity, offered=offered)
        record(name, result.outcome, expected, meaning)

    run("mutual-establishment", "established",
        "Both appraisals accept the unit and the ensemble identity the composition named.",
        honest())
    run("right-software-another-unit", "refused-unit-identity",
        "The substitution an ensemble exists to exclude, refused on the device register.",
        PeerAct(members["c"]))
    run("another-ensemble-identity", "refused-ensemble-identity",
        "A member of a different composition is refused on the generation register.",
        PeerAct(members["d"]))
    run("peer-at-the-previous-composition", "refused-ensemble-identity",
        "The right die still on the old composition is refused until it boots.",
        PeerAct(members["b-prior"]))
    run("unapproved-generation", "refused-generation-policy",
        "An authentic quote can still fail the end's generation policy.",
        PeerAct(members["b-unapproved"]))
    run("slot-table-digest-mismatch", "refused-slot-table-digest",
        "Two ends holding different tables are refused at establishment.",
        PeerAct(members["b-other-table"]))
    run("unbound-signing-identity", "refused-device-identity-binding",
        "A quote signed under an identity rooted in no device secret is refused by name.",
        PeerAct(members["b"], alias=True))
    run("substituted-unit-under-an-alias", "refused-device-identity-binding",
        "die-C asserting die-B's device register cannot present die-B's rooted identity.",
        PeerAct(members["c"], claimed_device=DeviceRegister("die-B"), alias=True))
    run("appraiser-taking-the-binding-on-faith", "established",
        "Dropping the first obligation admits a substituted unit: the counterexample.",
        PeerAct(members["c"], claimed_device=DeviceRegister("die-B"), alias=True),
        bind_identity=False)
    run("stale-challenge", "refused-challenge-or-link",
        "A quote answering an earlier challenge misses this end's fresh one.",
        PeerAct(members["b"], stale=True))
    run("withheld-evidence", "refused-evidence-invalid",
        "Silence opens no link and supplies no weaker peer claim.",
        PeerAct(members["b"], withhold=True))
    run("one-sided-acceptance", "refused-unit-identity",
        "One accepted direction is not a link; both appraisals must accept.",
        honest(), PeerAct(members["c"]))
    run("substituted-key-configuration", "refused-key-configuration",
        "A quote offering the classical-only configuration is refused.",
        PeerAct(members["b"], suite=SECOND_SUITE))
    run("negotiated-second-configuration", "refused-configuration-negotiated",
        "An offered second configuration terminates establishment (R-12-043a).",
        honest(), offered=(ADMISSIBLE_SUITE, SECOND_SUITE))
    run("two-leg-relay", "refused-unit-identity",
        "An intermediary terminating both legs is a unit the composition does not name.",
        PeerAct(members["c"]))

    # Frames, custody and the schedule-derived count.
    session = opened(link(honest()))
    first = session.core.seal(session.link, session.epoch, 3, "payload")
    record("frame-in-its-named-slot", session.receive(first, 3), "delivered",
           "A frame verifies in the slot the schedule names for it.")
    second = session.core.seal(session.link, session.epoch, 4, "payload")
    record("second-frame-in-one-slot", session.receive(second, 3), "slot-consumed",
           "The receive window admits at most one frame per slot.")

    delayed = opened(link(honest()))
    late = delayed.core.seal(delayed.link, delayed.epoch, 5, "payload")
    record("delay-inside-its-own-slot", delayed.receive(late, 5), "delivered",
           "Delay within the named slot keeps a valid tag; the count has not advanced.")

    replayed = opened(link(honest()))
    captured = replayed.core.seal(replayed.link, replayed.epoch, 3, "payload")
    record("replayed-into-another-slot", replayed.receive(captured, 7), "tag-failed",
           "A frame reordered or replayed into another slot fails its tag and stops the link.")
    record("link-stops-after-a-failed-tag", replayed.receive(captured, 3), "link-stopped",
           "R-15-228e's fail-stop holds for the rest of the session.")

    credulous = WireCountedSession(replayed.link, replayed.epoch, replayed.core)
    record("count-taken-from-the-wire", credulous.receive(captured, 7), "delivered",
           "An endpoint counting from the frame accepts the replay: the counterexample.")

    custody = opened(link(honest()))
    try:
        custody.core.export()
        exported = "key-exported"
    except SessionBindingError:
        exported = "no-export"
    record("key-custody", exported, "no-export",
           "The endpoint holds no key and no cipher; the core has no export path.")

    relayed = link(honest())
    relay_session = opened(relayed)
    intruder = CryptoCore("relay-own-key").seal(relay_session.link, relay_session.epoch, 2, "x")
    record("transparent-relay", f"{relayed.outcome}/{relay_session.receive(intruder, 2)}",
           "established/tag-failed",
           "Forwarding preserves the two intended cores; the relay acquires no key.")

    withheld = link(PeerAct(members["b"], withhold=True))
    record("withheld-wire",
           f"{withheld.outcome}/{members['a'].generation_register.generation}",
           "refused-evidence-invalid/generation-1",
           "The cost is the link's availability; the member boots and runs its own generation.")

    # Accepted attacks outside the honest relation.
    stolen_broker, _, stolen_members, stolen_ends = ensemble_fixture()
    stolen = Member("stolen-b", stolen_members["b"].generation_register,
                    DeviceRegister("die-B"), TABLE_AB)
    stolen_registry = IdentityRegistry(stolen_members.values())
    stolen_result = establish(stolen_ends["a"], stolen_ends["b"], stolen_broker, stolen_registry,
                              PeerAct(stolen), PeerAct(stolen_members["a"]))
    record("device-identity-secret-exposed", stolen_result.outcome, "established",
           "Exposure of the secret reproduces the rooted identity; the premise is lost.")

    forged_broker, forged_registry, forged_members, forged_ends = ensemble_fixture()
    forged_near = EnsembleAppraisal(forged_ends["a"], "near-fresh", forged_registry)
    forged_quote = forged_broker.issue(forged_members["c"], forged_near.challenge)
    forged_claims = replace(forged_quote.claims, device_register=DeviceRegister("die-B"),
                            signing_identity=rooted_identity(device_secret("die-B")))
    forged_quote = EnsembleQuote(forged_claims, forged_quote.seal)
    forged_broker.ledger[forged_quote.seal] = EnsembleIssuance(forged_quote,
                                                               forged_members["c"], True)
    record("compromised-root-of-trust", forged_near.decide(forged_quote, forged_broker),
           "accepted", "A compromised issuer authenticates false registers; evidence is a premise.")

    exposed = opened(link(honest()))
    outsider = CryptoCore("attacker-own-key")
    before = exposed.receive(outsider.seal(exposed.link, exposed.epoch, 1, "x"), 1)
    learned = CryptoCore(f"session-key/{exposed.link}/{exposed.epoch}")
    reopened = EnsembleSession(exposed.link, exposed.epoch, exposed.core)
    after = reopened.receive(learned.seal(exposed.link, exposed.epoch, 1, "x"), 1)
    record("session-key-exposed-after-establishment", f"{before}/{after}",
           "tag-failed/delivered",
           "Post-establishment key exposure yields frame authority the appraisal cannot revoke.")
    return tuple(out)


def ensemble_experiment() -> EnsembleExperiment:
    """Q23c's finite ensemble link session assessment."""
    total, accepted, refused, substituted, foreign, repeats, failures = _ensemble_population()
    return EnsembleExperiment(total, accepted, refused, substituted, foreign, repeats,
                              failures, _ensemble_scenarios())
