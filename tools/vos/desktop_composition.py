# SPDX-License-Identifier: Apache-2.0
"""Q34i's desktop placement and supplemental-pool accounting reference.

Inputs are composition declarations, not measurements or native admission
certificates. No input defaults supply missing resident bytes. A manifest's
isolation bit and the holder's declaration are combined by OR; clearing either
cannot override the other. All returned objects are immutable.
"""

import hashlib
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

GB = 1_000_000_000


class CompositionError(ValueError):
    """A composition declaration fails a desktop admission predicate."""


@dataclass(frozen=True)
class DesktopPolicy:
    first_floor: int
    second_floor: int
    general_pool_floor: int
    exclusivity_ceiling: Fraction
    owner_sha256: str


def policy_from_text(text: str) -> DesktopPolicy:
    """Read only supported normative shapes; missing/ambiguous shapes refuse.

    The first-class floor is the pessimistic payload end of R-15-173a's
    ungraded band, as R-18-004b requires. Decimal GB remains the owner's unit.
    This reader has no fallback policy and never silently accepts a rewording.
    """
    entries: list[str] = []
    for rid in ("R-15-173a", "R-18-004a", "R-18-004b"):
        matches = list(re.finditer(rf"^\*\*{re.escape(rid)}\*\* (?:IS|MUST): .+$",
                                  text, re.MULTILINE))
        if len(matches) != 1:
            raise CompositionError(f"policy owner: missing or ambiguous {rid}")
        entries.append(matches[0].group(0))

    def unique(pattern: str, entry: str, field: str) -> str:
        values = list(re.finditer(pattern, entry))
        if len(values) != 1:
            raise CompositionError(f"policy owner: unsupported or ambiguous {field}")
        value = values[0].group(1)
        if not isinstance(value, str):
            raise CompositionError(f"policy owner: unsupported capture for {field}")
        return value

    def payload(number: str) -> int:
        value = Fraction(number) * GB
        if value <= 0 or value.denominator != 1:
            raise CompositionError("policy owner: nonintegral or nonpositive payload")
        return int(value)

    number = r"[0-9]+(?:\.[0-9]+)?"
    band = unique(rf"single planar tier at order ({number}–{number}) GB", entries[0],
                  "first-class ungraded band")
    lower, upper = band.split("–")
    first = payload(lower)
    if first > payload(upper):
        raise CompositionError("policy owner: reversed first-class band")
    if "pessimistic end of R-15-173a's ungraded-branch budget stated as **payload**" not in entries[2]:
        raise CompositionError("policy owner: first-class floor no longer binds its source")
    second = payload(unique(rf"usable second-class capacity of at least ({number}) GB of payload",
                            entries[2], "second-class payload floor"))
    general = payload(unique(rf"its second-class pool at least ({number}) GB of payload",
                             entries[1], "general pool payload floor"))
    ceiling = Fraction(unique(rf"each class's declared τ \([^)]*\) at most ({number})%",
                              entries[2], "exclusivity ceiling")) / 100
    if not 0 <= ceiling <= 1:
        raise CompositionError("policy owner: exclusivity outside [0,1]")
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return DesktopPolicy(first, second, general, ceiling, digest)


def read_policy() -> DesktopPolicy:
    """Fresh normative operands from this module's own assigned checkout."""
    owner = Path(__file__).resolve().parents[2] / "docs/requirements-register.md"
    try:
        return policy_from_text(owner.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise CompositionError(f"cannot read desktop policy owner: {exc}") from exc


def _name(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CompositionError(f"{field}: nonempty identifier required")


def _nat(value: int, field: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < int(positive):
        raise CompositionError(f"{field}: {'positive' if positive else 'nonnegative'} integer required")


@dataclass(frozen=True)
class Application:
    id: str
    profile: str
    members: tuple[str, ...]
    manifest_isolated: bool = False
    holder_isolated: bool = False
    labels_served: int = 1
    owes_deadline: bool = False
    holds_platform_secret: bool = False
    device_authority: bool = False
    fixed_kind: str | None = None
    browser_origin: bool = False

    @property
    def isolated(self) -> bool:
        return self.manifest_isolated or self.holder_isolated

    @property
    def fixed(self) -> bool:
        return (self.labels_served >= 2 or self.owes_deadline
                or self.holds_platform_secret or self.device_authority
                or self.fixed_kind is not None)


@dataclass(frozen=True)
class PoolExtent:
    base: int
    payload_bytes: int


@dataclass(frozen=True)
class Reservation:
    core: int
    start: int
    width: int
    period: int


@dataclass(frozen=True)
class Domain:
    id: str
    profile: str
    label: str
    isolated_app: str | None
    members: tuple[str, ...]
    session_manager: str
    first_pool: PoolExtent
    second_pool: PoolExtent
    reservations: tuple[Reservation, ...]


@dataclass(frozen=True)
class Endpoint:
    source: str
    target: str
    kind: str
    carries_back: bool = False
    capability_slot: bool = False


@dataclass(frozen=True)
class Composition:
    applications: tuple[Application, ...]
    domains: tuple[Domain, ...]
    edges: tuple[Endpoint, ...]
    fixed_members: tuple[str, ...] = ()


def _unique(values: tuple[str, ...], field: str) -> None:
    for value in values:
        _name(value, field)
    if len(set(values)) != len(values):
        raise CompositionError(f"{field}: duplicate identity")


def _overlap(a: PoolExtent, b: PoolExtent) -> bool:
    return a.base < b.base + b.payload_bytes and b.base < a.base + a.payload_bytes


def _admit(c: Composition, policy: DesktopPolicy) -> None:
    """Refuse wrong placement, cross-domain edges or overlapping envelopes.

    Every application's compartments share its manifest; an isolated application
    may therefore have several compartments without admitting another manifest.
    Session managers are enumerated domain compartments. Fixed-tier members are
    explicit and kept outside every elastic domain.
    """
    application_keys = {(a.profile, a.id) for a in c.applications}
    if len(application_keys) != len(c.applications):
        raise CompositionError("applications: duplicate identity within profile")
    _unique(tuple(d.id for d in c.domains), "domains")
    _unique(tuple(d.label for d in c.domains), "domain labels")
    _unique(c.fixed_members, "fixed members")
    owner: dict[str, Application] = {}
    for a in c.applications:
        _name(a.id, "application")
        _name(a.profile, "profile")
        _unique(a.members, "application members")
        if not a.members:
            raise CompositionError("application has no compartments")
        _nat(a.labels_served, "labels served", positive=True)
        for flag in (a.manifest_isolated, a.holder_isolated, a.owes_deadline,
                     a.holds_platform_secret, a.device_authority, a.browser_origin):
            if type(flag) is not bool:
                raise CompositionError("manifest flag: boolean required")
        if a.fixed_kind is not None:
            _name(a.fixed_kind, "fixed kind")
        for m in a.members:
            if m in owner:
                raise CompositionError("compartment belongs to two manifests")
            owner[m] = a
    if any(m not in owner for m in c.fixed_members):
        raise CompositionError("unknown fixed member")
    placed: dict[str, Domain] = {}
    general: dict[str, Domain] = {}
    isolated: dict[tuple[str, str], Domain] = {}
    managers: set[str] = set()
    for d in c.domains:
        _name(d.profile, "domain profile")
        _unique(d.members, "domain members")
        _name(d.session_manager, "session manager")
        if d.session_manager not in d.members:
            raise CompositionError("session manager outside domain")
        if d.session_manager in managers:
            raise CompositionError("session manager shared across domains")
        managers.add(d.session_manager)
        if d.isolated_app is None:
            if d.profile in general:
                raise CompositionError("two general domains for one profile")
            general[d.profile] = d
            if d.second_pool.payload_bytes < policy.general_pool_floor:
                raise CompositionError("general second-class pool below floor")
        else:
            _name(d.isolated_app, "isolated application")
            key = (d.profile, d.isolated_app)
            if key in isolated:
                raise CompositionError("two isolated domains for one application")
            isolated[key] = d
        for pool in (d.first_pool, d.second_pool):
            _nat(pool.base, "pool base")
            _nat(pool.payload_bytes, "pool payload", positive=True)
        if _overlap(d.first_pool, d.second_pool):
            raise CompositionError("memory-class extents overlap")
        if not d.reservations:
            raise CompositionError("domain has no fixed reservation")
        if len(set(d.reservations)) != len(d.reservations):
            raise CompositionError("duplicate domain reservation")
        for r in d.reservations:
            _nat(r.core, "reservation core")
            _nat(r.start, "reservation start")
            _nat(r.width, "reservation width", positive=True)
            _nat(r.period, "reservation period", positive=True)
            if r.start + r.width > r.period:
                raise CompositionError("reservation crosses frame boundary")
        for m in d.members:
            if m not in owner:
                raise CompositionError("unknown domain compartment")
            if m in placed or m in c.fixed_members:
                raise CompositionError("compartment placed more than once")
            a = owner[m]
            if a.fixed or a.browser_origin:
                raise CompositionError("fixed-tier shape or browser origin in desktop domain")
            if a.profile != d.profile:
                raise CompositionError("application in another profile")
            if a.isolated and d.isolated_app != a.id:
                raise CompositionError("declared-isolated application in wrong domain")
            if not a.isolated and d.isolated_app is not None:
                raise CompositionError("ordinary application in isolated domain")
            if d.isolated_app is not None and a.id != d.isolated_app:
                raise CompositionError("second manifest in isolated domain")
            placed[m] = d
    profiles = {a.profile for a in c.applications} | {d.profile for d in c.domains}
    if set(general) != profiles:
        raise CompositionError("profile lacks its one general domain")
    expected_isolated = {(a.profile, a.id) for a in c.applications
                         if a.isolated and not a.fixed and not a.browser_origin}
    if set(isolated) != expected_isolated:
        raise CompositionError("missing or surplus isolated domain")
    for a in c.applications:
        for m in a.members:
            if a.fixed:
                if m not in c.fixed_members:
                    raise CompositionError("fixed-tier shape lacks fixed placement")
            elif a.browser_origin:
                if m not in c.fixed_members:
                    raise CompositionError("browser origin lacks separate non-desktop placement")
            elif m not in placed:
                raise CompositionError("installed application lacks domain placement")
    for i, d in enumerate(c.domains):
        for other in c.domains[i + 1:]:
            for p in (d.first_pool, d.second_pool):
                for q in (other.first_pool, other.second_pool):
                    if _overlap(p, q):
                        raise CompositionError("pools shared across domains")
        for ri, r in enumerate(d.reservations):
            for j in range(i, len(c.domains)):
                other = c.domains[j]
                for si, s in enumerate(other.reservations):
                    if i == j and ri >= si:
                        continue
                    if r.core == s.core:
                        if r.period != s.period:
                            raise CompositionError("shared core has inconsistent frame period")
                        if r.start < s.start + s.width and s.start < r.start + r.width:
                            raise CompositionError("domain reservations overlap on core")
    requests: set[tuple[str, str]] = set()
    for e in c.edges:
        _name(e.source, "endpoint source")
        _name(e.target, "endpoint target")
        _name(e.kind, "endpoint kind")
        if type(e.carries_back) is not bool or type(e.capability_slot) is not bool:
            raise CompositionError("endpoint flag: boolean required")
        if e.source not in owner or e.target not in owner:
            raise CompositionError("unknown endpoint member")
        source = placed.get(e.source)
        target = placed.get(e.target)
        if source is None or target is None or source.id == target.id:
            continue
        allowed = (source.isolated_app is None and target.isolated_app is not None
                   and source.profile == target.profile
                   and e.source == source.session_manager
                   and e.target == target.session_manager
                   and e.kind == "session_requests" and not e.carries_back
                   and not e.capability_slot)
        if not allowed:
            raise CompositionError("forbidden edge between desktop domains")
        pair = (source.id, target.id)
        if pair in requests:
            raise CompositionError("duplicate session-manager endpoint")
        requests.add(pair)
    expected = {(general[d.profile].id, d.id) for d in c.domains if d.isolated_app is not None}
    if requests != expected:
        raise CompositionError("missing one-way session-manager endpoint")


def admit(c: Composition) -> None:
    """Check desktop placement against freshly read register policy operands."""
    _admit(c, read_policy())


def compose(applications: tuple[Application, ...], envelopes: tuple[Domain, ...],
            edges: tuple[Endpoint, ...], fixed_members: tuple[str, ...] = ()) -> Composition:
    """Bind manifests to supplied empty envelopes; refuse a missing declaration.

    Envelope labels, extents and reservations come from the static composition.
    No runtime placement or generated memory capacity is introduced here.
    """
    domains = []
    for d in envelopes:
        if d.members:
            raise CompositionError("compose requires empty envelope member lists")
        members = tuple(m for a in applications if a.profile == d.profile
                        and not a.fixed and not a.browser_origin
                        and ((a.isolated and a.id == d.isolated_app)
                             or (not a.isolated and d.isolated_app is None))
                        for m in a.members)
        domains.append(Domain(d.id, d.profile, d.label, d.isolated_app, members,
                              d.session_manager, d.first_pool, d.second_pool,
                              d.reservations))
    result = Composition(applications, tuple(domains), edges, fixed_members)
    admit(result)
    return result


@dataclass(frozen=True)
class ClassSupply:
    payload_bytes: int
    exclusivity: Fraction


@dataclass(frozen=True)
class RosterDemand:
    # Complete roster demand outside all desktop domain extents. The caller
    # includes code, contexts, metadata, managers, quarantine and service heaps.
    first_outside_pools: int
    second_outside_pools: int
    first_supply: ClassSupply
    second_supply: ClassSupply


@dataclass(frozen=True)
class CapacityComparison:
    demand_bytes: int
    usable_payload_bytes: int
    exclusivity: Fraction
    available_bytes: Fraction
    headroom_bytes: Fraction
    meets_floor: bool
    fits: bool


@dataclass(frozen=True)
class PoolPrice:
    first: CapacityComparison
    second: CapacityComparison
    isolated_first_bytes: int
    isolated_second_bytes: int
    general_second_bytes: int
    policy_owner_sha256: str


def price_pools(c: Composition, demand: RosterDemand,
                baseline_general: tuple[tuple[str, PoolExtent, PoolExtent], ...]) -> PoolPrice:
    """Compare declared roster residency with R-18-004b's per-class budget.

    The baseline is the preceding general-domain pool declaration. Both extents
    must remain exactly unchanged, preventing a pool split from taking its bytes.
    This computes two capacity and exclusivity comparisons only. It supplies no
    bandwidth, area, yield, cost, supply qualification or roster truth claim.
    """
    policy = read_policy()
    _admit(c, policy)
    _nat(demand.first_outside_pools, "first-class outside-pool demand")
    _nat(demand.second_outside_pools, "second-class outside-pool demand")
    current = tuple((d.id, d.first_pool, d.second_pool) for d in c.domains
                    if d.isolated_app is None)
    if len({row[0] for row in baseline_general}) != len(baseline_general):
        raise CompositionError("duplicate general baseline")
    if set(current) != set(baseline_general):
        raise CompositionError("general pool changed from baseline")

    def comparison(total: int, supply: ClassSupply, floor: int) -> CapacityComparison:
        _nat(supply.payload_bytes, "supply payload", positive=True)
        if not isinstance(supply.exclusivity, Fraction) or not 0 <= supply.exclusivity <= 1:
            raise CompositionError("exclusivity must be an exact fraction in [0,1]")
        available = supply.payload_bytes * (1 - supply.exclusivity)
        floor_met = supply.payload_bytes >= floor
        fits = floor_met and supply.exclusivity <= policy.exclusivity_ceiling and total <= available
        return CapacityComparison(total, supply.payload_bytes, supply.exclusivity,
                                  available, available - total, floor_met, fits)

    first = demand.first_outside_pools + sum(d.first_pool.payload_bytes for d in c.domains)
    second = demand.second_outside_pools + sum(d.second_pool.payload_bytes for d in c.domains)
    return PoolPrice(comparison(first, demand.first_supply, policy.first_floor),
                     comparison(second, demand.second_supply, policy.second_floor),
                     sum(d.first_pool.payload_bytes for d in c.domains if d.isolated_app is not None),
                     sum(d.second_pool.payload_bytes for d in c.domains if d.isolated_app is not None),
                     sum(d.second_pool.payload_bytes for d in c.domains if d.isolated_app is None),
                     policy.owner_sha256)
