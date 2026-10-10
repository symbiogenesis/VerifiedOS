# SPDX-License-Identifier: Apache-2.0
"""Desktop domain placement, one-way wiring and exact pool pricing controls."""

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from functools import partial
from pathlib import Path

from tests.harness import Case, ensure
from vos import desktop_composition as d


def fixture() -> d.Composition:
    """Synthetic declarations: eight ordinary apps plus two isolated manifests."""
    apps = tuple(d.Application(f"app{i}", "holder", (f"part{i}",)) for i in range(8))
    apps += (d.Application("credentials", "holder", ("credential-manager", "credential-ui"),
                           manifest_isolated=True),
             d.Application("private-notes", "holder", ("notes-manager",),
                           holder_isolated=True))
    plans = (d.Domain("general", "holder", "general-label", None, (), "part0",
                      d.PoolExtent(0, 10_000_000), d.PoolExtent(d.GB, d.GB),
                      (d.Reservation(0, 0, 60, 100),)),
             d.Domain("credentials", "holder", "credential-label", "credentials", (),
                      "credential-manager", d.PoolExtent(10_000_000, 2_000_000),
                      d.PoolExtent(2 * d.GB, 100_000_000),
                      (d.Reservation(0, 60, 20, 100),)),
             d.Domain("notes", "holder", "notes-label", "private-notes", (), "notes-manager",
                      d.PoolExtent(12_000_000, 3_000_000),
                      d.PoolExtent(2 * d.GB + 100_000_000, 200_000_000),
                      (d.Reservation(0, 80, 20, 100),)))
    edges = (d.Endpoint("part0", "credential-manager", "session_requests"),
             d.Endpoint("part0", "notes-manager", "session_requests"))
    return d.compose(apps, plans, edges)


def refused(call: Callable[[], object], reason: str) -> None:
    try:
        call()
    except d.CompositionError as exc:
        ensure(reason in str(exc), f"wrong refusal: {exc}")
    else:
        raise AssertionError(f"accepted without {reason}")


def with_domain(c: d.Composition, index: int, value: d.Domain) -> d.Composition:
    return replace(c, domains=(*c.domains[:index], value, *c.domains[index + 1:]))


def both_declarations_place_the_manifest() -> None:
    c = fixture()
    ensure(len(c.domains[0].members) == 8, "general live-member floor changed")
    ensure(c.domains[1].members == ("credential-manager", "credential-ui"),
           "one manifest's multiple compartments lost")
    ensure(c.domains[2].members == ("notes-manager",), "holder declaration ignored")
    ensure(c.domains[0].second_pool.payload_bytes == d.GB, "general pool changed")
    apps = tuple(replace(a, holder_isolated=False) if a.id == "credentials" else a
                 for a in c.applications)
    d.admit(replace(c, applications=apps))


def required_placement_refusals() -> None:
    c = fixture()
    bad_general = replace(c.domains[0], members=(*c.domains[0].members, "credential-ui"))
    refused(lambda: d.admit(with_domain(c, 0, bad_general)), "declared-isolated")
    second_app = replace(c.domains[1], members=(*c.domains[1].members, "notes-manager"))
    refused(lambda: d.admit(with_domain(c, 1, second_app)), "declared-isolated")
    missing = replace(c.domains[0], members=c.domains[0].members[:-1])
    refused(lambda: d.admit(with_domain(c, 0, missing)), "lacks domain placement")
    duplicated = replace(c.domains[1], members=(*c.domains[1].members, "credential-ui"))
    refused(lambda: d.admit(with_domain(c, 1, duplicated)), "duplicate identity")
    refused(lambda: d.admit(replace(c, domains=c.domains[1:])), "general domain")
    # A wrong isolated-app declaration cannot sneak in a second manifest.
    wrong = replace(c.domains[1], isolated_app="private-notes")
    refused(lambda: d.admit(with_domain(c, 1, wrong)), "declared-isolated")


def required_wiring_refusals() -> None:
    c = fixture()
    for edge in (d.Endpoint("credential-ui", "part1", "ring"),
                 d.Endpoint("part1", "credential-ui", "session_requests"),
                 d.Endpoint("credential-manager", "notes-manager", "session_requests")):
        candidate = replace(c, edges=(*c.edges, edge))
        refused(partial(d.admit, candidate), "forbidden edge")
    for edge in (replace(c.edges[0], carries_back=True),
                 replace(c.edges[0], capability_slot=True),
                 replace(c.edges[0], kind="register")):
        candidate = replace(c, edges=(edge, c.edges[1]))
        refused(partial(d.admit, candidate), "forbidden edge")
    refused(lambda: d.admit(replace(c, edges=c.edges[:1])), "missing one-way")
    refused(lambda: d.admit(replace(c, edges=c.edges + c.edges[:1])), "duplicate session")


def envelopes_do_not_share_state_or_reservations() -> None:
    c = fixture()
    refused(lambda: d.admit(with_domain(c, 1, replace(c.domains[1], label="general-label"))),
            "domain labels")
    refused(lambda: d.admit(with_domain(c, 1, replace(c.domains[1],
                    first_pool=c.domains[0].first_pool))), "pools shared")
    refused(lambda: d.admit(with_domain(c, 1, replace(c.domains[1],
                    reservations=(d.Reservation(0, 59, 20, 100),)))), "reservations overlap")
    refused(lambda: d.admit(with_domain(c, 1, replace(c.domains[1],
                    reservations=(d.Reservation(0, 60, 20, 200),)))), "inconsistent frame")
    refused(lambda: d.admit(with_domain(c, 1, replace(c.domains[1],
                    reservations=c.domains[1].reservations * 2))), "duplicate domain reservation")
    shared = c.domains[0].reservations[0]
    refused(lambda: d.admit(with_domain(c, 1, replace(c.domains[1],
                    reservations=(shared,)))), "reservations overlap")
    refused(lambda: d.admit(with_domain(c, 0, replace(c.domains[0],
                    second_pool=d.PoolExtent(d.GB, d.GB - 1)))), "below floor")


def fixed_shapes_and_browser_exclusion() -> None:
    c = fixture()
    for app in (replace(c.applications[1], labels_served=2),
                replace(c.applications[1], owes_deadline=True),
                replace(c.applications[1], holds_platform_secret=True),
                replace(c.applications[1], device_authority=True),
                replace(c.applications[1], fixed_kind="DeviceDriver"),
                replace(c.applications[1], browser_origin=True)):
        candidate = replace(c, applications=(c.applications[0], app, *c.applications[2:]))
        refused(partial(d.admit, candidate), "fixed-tier shape or browser")
    fixed_app = d.Application("network", "holder", ("network",), owes_deadline=True)
    d.admit(replace(c, applications=(*c.applications, fixed_app), fixed_members=("network",)))
    refused(lambda: d.admit(replace(c, applications=(*c.applications, fixed_app))),
            "lacks fixed placement")


def pricing_operand_validation_and_exact_thresholds() -> None:
    c = fixture()
    policy = d.read_policy()
    baseline = (("general", c.domains[0].first_pool, c.domains[0].second_pool),)
    demand = d.RosterDemand(385_000_000, 1_900_000_000,
                           d.ClassSupply(policy.first_floor, policy.exclusivity_ceiling),
                           d.ClassSupply(policy.second_floor, policy.exclusivity_ceiling))
    price = d.price_pools(c, demand, baseline)
    ensure(price.first.demand_bytes == 400_000_000 and price.first.fits,
           "exact first-class equality failed")
    ensure(price.second.demand_bytes == 3_200_000_000 and price.second.fits,
           "exact second-class equality failed")
    ensure(price.isolated_first_bytes == 5_000_000
           and price.isolated_second_bytes == 300_000_000
           and price.general_second_bytes == d.GB, "isolated pools not additive")
    ensure(not d.price_pools(c, replace(demand, first_outside_pools=385_000_001), baseline)
           .first.fits, "one excess byte accepted")
    ensure(not d.price_pools(c, replace(demand, second_supply=d.ClassSupply(
        policy.second_floor, policy.exclusivity_ceiling + Fraction(1, 1_000_000_000))),
        baseline).second.fits,
        "exclusivity above 20 percent accepted")
    ensure(not d.price_pools(c, replace(demand, first_supply=d.ClassSupply(
        policy.first_floor - 1, Fraction(0))), baseline).first.fits, "supply floor ignored")
    changed = with_domain(c, 0, replace(c.domains[0], first_pool=d.PoolExtent(0, 9_000_000)))
    refused(lambda: d.price_pools(changed, demand, baseline), "general pool changed")
    refused(lambda: d.price_pools(c, replace(demand, first_outside_pools=True), baseline),
            "integer required")
    malformed_supply = replace(demand.first_supply, exclusivity=0.2)
    refused(lambda: d.price_pools(c, replace(demand, first_supply=malformed_supply), baseline),
            "exact fraction")


def malformed_and_cross_profile_compositions_are_refused() -> None:
    c = fixture()
    app = replace(c.applications[1], profile="another-holder")
    refused(lambda: d.admit(replace(c, applications=(c.applications[0], app,
                                                    *c.applications[2:]))), "another profile")
    bad = replace(c.applications[1], manifest_isolated=1)
    refused(lambda: d.admit(replace(c, applications=(c.applications[0], bad,
                                                    *c.applications[2:]))), "boolean required")
    refused(lambda: d.compose(c.applications, c.domains, c.edges), "empty envelope")


def owner_policy_is_derived_and_fails_closed() -> None:
    text = (Path(__file__).resolve().parents[2] / "docs/requirements-register.md")
    source = text.read_text(encoding="utf-8")
    policy = d.policy_from_text(source)
    changed = source.replace("usable second-class capacity of at least 4 GB of payload",
                             "usable second-class capacity of at least 5 GB of payload")
    raised = d.policy_from_text(changed)
    ensure(raised.second_floor == policy.second_floor + d.GB
           and raised.owner_sha256 != policy.owner_sha256, "owner edit did not move policy")
    refused(lambda: d.policy_from_text(source.replace("single planar tier at order", "tier at")),
            "unsupported or ambiguous")
    entry = next(line for line in source.splitlines() if line.startswith("**R-18-004b** "))
    refused(lambda: d.policy_from_text(source + "\n" + entry), "missing or ambiguous")
    refused(lambda: d.policy_from_text(source.replace("**R-18-004b**", "**R-18-999**")),
            "missing or ambiguous")


def independent_profiles_can_install_the_same_application() -> None:
    c = fixture()
    app = d.Application("app0", "other-holder", ("other-shell",))
    domain = d.Domain("other-general", "other-holder", "other-label", None,
                      ("other-shell",), "other-shell", d.PoolExtent(15_000_000, 2_000_000),
                      d.PoolExtent(3 * d.GB, d.GB), (d.Reservation(1, 0, 100, 100),))
    d.admit(replace(c, applications=(*c.applications, app), domains=(*c.domains, domain)))
    refused(lambda: d.admit(replace(c, applications=(*c.applications, c.applications[0]))),
            "duplicate identity within profile")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        both_declarations_place_the_manifest,
        required_placement_refusals,
        required_wiring_refusals,
        envelopes_do_not_share_state_or_reservations,
        fixed_shapes_and_browser_exclusion,
        pricing_operand_validation_and_exact_thresholds,
        malformed_and_cross_profile_compositions_are_refused,
        owner_policy_is_derived_and_fails_closed,
        independent_profiles_can_install_the_same_application,
    )]
