# SPDX-License-Identifier: Apache-2.0
"""Q22c's finite TLS attestation boundary, with ideal authenticated evidence.

This is an experiment, not a TLS implementation, crypto primitive or proof. Context
objects stand for protected local handles; the ledger stands for unforgeable evidence
and its trust chain. Ghost provenance is used only by the experiment's property oracle.
"""

from dataclasses import dataclass, field, replace
from itertools import product
from typing import Literal

Scope = Literal["software", "unit"]
DOMAIN = "VerifiedOS/Q22c/TLS-attestation/v1"
ROLE = "tls-attesting-client"
OPERATION = "attest-local-session"


class Refusal(ValueError):
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
            raise Refusal("ineligible TLS context")
        if (credential.unit, credential.principal) != (channel.unit, channel.principal):
            raise Refusal("credential does not own this local TLS context")
        if (credential.origin != channel.origin or challenge.origin != channel.origin
                or credential.scope != challenge.scope or not challenge.nonce
                or credential.role != ROLE or credential.operation != OPERATION
                or credential.domain != DOMAIN or challenge.domain != DOMAIN):
            raise Refusal("credential scope or protocol context")
        if credential.remaining < 1 or now >= credential.expires:
            raise Refusal("credential use or expiry bound")
        generation = self.generations.get(channel.unit)
        if generation is None:
            raise Refusal("measured state unavailable")
        alias = None
        if challenge.scope == "unit":
            alias = self.aliases.get((channel.origin, channel.unit))
            if alias is None:
                raise Refusal("origin-scoped unit enrollment unavailable")
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
            raise Refusal("cannot open challenge")
        if ((policy.scope == "unit") != (policy.expected_alias is not None)
                or not policy.generations):
            raise Refusal("incomplete or inconsistent appraisal policy")
        if channel.lifecycle.authentication_started:
            raise Refusal("TLS context already owns an authentication lifecycle")
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
            except Refusal:
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
                assert quote is not None
                quote = replace(quote, claims=replace(quote.claims, generation="approved"))
                broker.ledger[quote.seal] = Issuance(quote, ch)
            elif action == "caller-exporter":
                # Deliberately broken API: a healthy A signs X's public exporter.
                assert quote is not None
                fake = replace(quote.claims, generation="approved")
                quote = Quote(fake, len(broker.ledger))
                broker.ledger.append(Issuance(quote, a))
            observed = pending.decide(quote, broker, now)
            if action == "key-stolen" and observed == "accepted":
                keys = TrafficKeys(ch)
                assert not keys.record_accepted(pending, "X")
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
        except Refusal:
            reopens += 1
        else:
            failures.append(f"quote {event.quote.seal}: reconstructed appraisal accepted")
    return Experiment(total, accepted, refused, replays, reopens,
                      tuple(failures), _scenarios())
