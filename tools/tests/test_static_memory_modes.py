# SPDX-License-Identifier: Apache-2.0
"""Independent finite tests of the three mode-family placement models."""

import itertools
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory as memory
from vos import static_memory_modes as modes

EDGES = tuple(itertools.combinations(range(4), 2))


def _contract(name: str, sizes: tuple[int, ...],
              mode_rows: list[tuple[str, list[tuple[str, int, int]]]],
              rule: str = "dead-at-switch",
              transitions: list[dict[str, Any]] | None = None,
              capacity: int | None = None,
              arena_of: dict[str, str] | None = None) -> dict[str, Any]:
    """One private fixture; the module's own witness builder is not used here.

    `arena_of` names the arena of an identity that does not sit in the default one,
    so a fixture can declare two arenas. Each arena's capacity is its own identities'
    charged bytes unless one is passed for all of them.
    """
    first = mode_rows[0][0]
    home = {f"v{index}": (arena_of or {}).get(f"v{index}", "arena")
            for index in range(len(sizes))}
    room = {arena_id: sum(size for index, size in enumerate(sizes)
                          if home[f"v{index}"] == arena_id)
            for arena_id in sorted(set(home.values()))}
    return {
        "name": name, "provenance": "private finite fixture",
        "arenas": [{"id": arena_id, "owner": "owner",
                    "capacity": capacity if capacity is not None else room[arena_id]}
                   for arena_id in sorted(room)],
        "identities": [{"id": f"v{index}", "arena": home[f"v{index}"], "size": size,
                        "payload": size, "alignment": 1}
                       for index, size in enumerate(sizes)],
        "modes": [{"name": mode_name,
                   "lifetimes": [{"id": identifier, "start": start, "payload_end": end,
                                  "authority_end": end, "sweep_end": end, "reuse": end}
                                 for identifier, start, end in rows]}
                  for mode_name, rows in mode_rows],
        "binding": {"rule": rule, "transitions": transitions if transitions is not None else
                    [{"source": first, "target": first, "at_source": 9, "at_target": 9,
                      "retained": []}]},
    }


def _graph_contract(chosen: tuple[tuple[int, int], ...], sizes: tuple[int, ...]) -> dict[str, Any]:
    """A family whose all-mode relation is exactly `chosen`: one mode per edge."""
    rows = [(f"m{left}{right}", [(f"v{left}", 0, 2), (f"v{right}", 0, 2)])
            for left, right in chosen]
    covered = {index for edge in chosen for index in edge}
    rows.extend((f"s{index}", [(f"v{index}", 0, 2)])
                for index in range(len(sizes)) if index not in covered)
    return _contract(f"graph-{len(chosen)}", sizes, rows)


def _minimum_span(chosen: tuple[tuple[int, int], ...], sizes: tuple[int, ...]) -> int:
    """Independent enumeration of every legal base tuple; no search code is called."""
    capacity = sum(sizes)
    best = capacity
    for bases in itertools.product(*[range(capacity - size + 1) for size in sizes]):
        if any(max(bases[left], bases[right])
               < min(bases[left] + sizes[left], bases[right] + sizes[right])
               for left, right in chosen):
            continue
        best = min(best, max(base + size for base, size in zip(bases, sizes, strict=True)))
    return best


def _exact_against_enumeration() -> None:
    for sizes in ((1, 1, 1, 1), (1, 2, 1, 2)):
        for count in range(len(EDGES) + 1):
            for chosen in itertools.combinations(EDGES, count):
                family = modes.parse_family(_graph_contract(chosen, sizes))
                nodes = modes.variables(family, "conservative")
                found = {tuple(sorted(pair)) for pair in modes.interference(family, nodes)}
                ensure(found == {(f"v{left}", f"v{right}") for left, right in chosen},
                       "the all-mode relation must be exactly the declared edge set")
                receipt = modes.solve_model(family, "conservative")
                ensure(receipt["status"] == "optimal", "small graph search must complete")
                span = receipt["arenas"][0]["best_span"]
                ensure(span == _minimum_span(chosen, sizes),
                       f"graph optimum {span} differs from independent enumeration on {chosen}")
                bases = receipt["bases"]
                if bases is None:
                    raise AssertionError("a complete optimum must carry its witness")
                placement = [{"id": node.name, "arena": node.arena, "base": bases[node.name]}
                             for node in nodes]
                ensure(not modes.check_single_layout(family, placement)
                       and not modes.replay_by_mode(family, placement),
                       "every searched witness must pass both independent checkers")


def _not_an_interval_graph() -> None:
    ring = tuple((index, (index + 1) % 5) for index in range(5))
    family = modes.parse_family(_graph_contract(ring, (1, 1, 1, 1, 1)))
    nodes = modes.variables(family, "conservative")
    edges = modes.interference(family, nodes)
    certificate = modes.chordless_cycle(nodes, edges)
    ensure(certificate["status"] == "induced-cycle" and len(certificate["cycle"]) == 5,
           "the five-cycle relation must expose its induced cycle")
    ensure(modes.solve_model(family, "conservative")["arenas"][0]["best_span"] == 3,
           "a five-cycle needs three units where every mode's peak is two")
    for mode in family.modes:
        ensure(memory.solve_exact(mode.case)["arenas"][0]["best_span"] == 2,
               "every single mode of that family costs two")
    triangle = modes.parse_family(_graph_contract(((0, 1), (0, 2), (1, 2)), (1, 1, 1)))
    corners = modes.variables(triangle, "conservative")
    chordal = modes.chordless_cycle(corners, modes.interference(triangle, corners))
    ensure(chordal["status"] == "none-found" and chordal["cycle"] is None,
           "a triangle carries no induced cycle of length four")
    exhausted = modes.chordless_cycle(nodes, edges, max_subsets=1)
    ensure(exhausted["status"] == "incomplete" and exhausted["cycle"] is None,
           "a cutoff must never become a decision")
    for invalid in (0, -1, True):
        try:
            modes.chordless_cycle(nodes, edges, invalid)
        except memory.CaseError:
            continue
        raise AssertionError("invalid subset budget accepted")


def _wrong_checkers_are_caught() -> None:
    raw = _contract("two-modes", (1, 1, 1),
                    [("m0", [("v0", 0, 2), ("v1", 0, 2)]),
                     ("m1", [("v0", 0, 2), ("v2", 0, 2)])])
    family = modes.parse_family(raw)
    overlapping = [{"id": "v0", "arena": "arena", "base": 0},
                   {"id": "v1", "arena": "arena", "base": 1},
                   {"id": "v2", "arena": "arena", "base": 0}]
    first_mode_only = memory.check_placement(
        family.modes[0].case, modes.projections(family, overlapping)["m0"])
    ensure(not first_mode_only, "the wrong checker must accept the defective layout")
    pairwise = modes.check_single_layout(family, overlapping)
    by_mode = modes.replay_by_mode(family, overlapping)
    ensure(any("overlap" in finding and "m1" in finding for finding in pairwise),
           f"the pairwise checker must name the second mode's overlap: {pairwise}")
    ensure(any("overlap" in finding for finding in by_mode),
           "the per-mode replay must refuse the same layout")
    legal = [{"id": "v0", "arena": "arena", "base": 0},
             {"id": "v1", "arena": "arena", "base": 1},
             {"id": "v2", "arena": "arena", "base": 1}]
    ensure(not modes.check_single_layout(family, legal) and not modes.replay_by_mode(family, legal),
           "both readings must accept a layout legal in every mode")
    ensure(modes.charge(family, modes.projections(family, legal)) == {"arena": 2},
           "the accepted layout charges two units")
    mutants: list[tuple[object, str]] = [
        ({"id": "v0"}, "schema"),
        ([{"id": "v0", "arena": "arena", "base": 0}], "identity: missing object v1"),
        ([*legal, {"id": "v0", "arena": "arena", "base": 0}], "identity: duplicate object v0"),
        ([{"id": "v0", "arena": "other", "base": 0}, legal[1], legal[2]], "ownership"),
        ([{"id": "v0", "arena": "arena", "base": 7}, legal[1], legal[2]], "capacity"),
        ([{"id": "ghost", "arena": "arena", "base": 0}, *legal], "identity: unknown object ghost"),
    ]
    for candidate, expected in mutants:
        findings = modes.check_single_layout(family, candidate)
        ensure(any(expected in finding for finding in findings),
               f"expected {expected} among {findings}")


def _switch_rule_refusals() -> None:
    rows = [("m0", [("v0", 0, 4), ("v1", 2, 6)]), ("m1", [("v1", 0, 4), ("v0", 2, 6)])]
    live = _contract("live-at-switch", (1, 1), rows, transitions=[
        {"source": "m0", "target": "m1", "at_source": 3, "at_target": 0, "retained": []}])
    findings = modes.check_switch_rule(modes.parse_family(live))
    ensure(any("v0 is live" in finding for finding in findings)
           and any("v1 is live" in finding for finding in findings),
           f"a live identity at a switch that retains nothing is a refusal: {findings}")
    refused = modes.binding_model(modes.parse_family(live))
    ensure(refused["status"] == "refused" and refused["charge"] is None
           and refused["layouts"] is None,
           "a refused switch rule must carry no layout family and no charge")
    dead = _contract("dead-at-switch", (1, 1), rows, transitions=[
        {"source": "m0", "target": "m1", "at_source": 6, "at_target": 6, "retained": []}])
    family = modes.parse_family(dead)
    ensure(not modes.check_switch_rule(family), "nothing is live once both reservations end")
    admitted = modes.binding_model(family)
    ensure(admitted["status"] == "checked" and admitted["charge"] == {"arena": 2},
           "a family dead at its switch keeps each mode's own optimum")
    absent = _contract("retained-is-dead", (1, 1), rows, rule="retained-bases-equal",
                       transitions=[{"source": "m0", "target": "m1", "at_source": 6,
                                     "at_target": 6, "retained": ["v0"]}])
    ensure(any("retained v0 is dead" in finding
               for finding in modes.check_switch_rule(modes.parse_family(absent))),
           "a retained identity that is dead at the switch retains nothing")
    keeping = _contract("retained", (1, 1), rows, rule="retained-bases-equal",
                        transitions=[{"source": "m0", "target": "m1", "at_source": 5,
                                      "at_target": 1, "retained": ["v1"]}])
    kept = modes.parse_family(keeping)
    ensure(not modes.check_switch_rule(kept), f"the retained rule holds: {keeping}")
    moved = {"m0": [{"id": "v0", "arena": "arena", "base": 0},
                    {"id": "v1", "arena": "arena", "base": 1}],
             "m1": [{"id": "v0", "arena": "arena", "base": 1},
                    {"id": "v1", "arena": "arena", "base": 0}]}
    ensure(any("retained v1 moves from 1 to 0" in finding
               for finding in modes.check_binding_family(kept, moved)),
           "a retained identity may not change base across the switch")
    still = {name: [dict(row) for row in plan] for name, plan in moved.items()}
    still["m1"] = [{"id": "v0", "arena": "arena", "base": 0},
                   {"id": "v1", "arena": "arena", "base": 1}]
    ensure(not modes.check_binding_family(kept, still),
           "equal retained bases and legal per-mode layouts are accepted")
    ensure(modes.check_binding_family(kept, {"m0": still["m0"]})
           == ["schema: one placement is required for each admitted mode"],
           "a binding family needs one layout per admitted mode")


def _retention_costs_the_single_layout() -> None:
    raw = _contract("retained-cycle", (1, 1, 1),
                    [("m1", [("v1", 0, 4), ("v0", 2, 6)]), ("m2", [("v0", 0, 4), ("v2", 2, 6)]),
                     ("m3", [("v2", 0, 4), ("v1", 2, 6)])],
                    rule="retained-bases-equal",
                    transitions=[{"source": "m1", "target": "m2", "at_source": 4,
                                  "at_target": 0, "retained": ["v0"]},
                                 {"source": "m2", "target": "m3", "at_source": 4,
                                  "at_target": 0, "retained": ["v2"]},
                                 {"source": "m3", "target": "m1", "at_source": 4,
                                  "at_target": 0, "retained": ["v1"]}])
    family = modes.parse_family(raw)
    ensure(not modes.check_switch_rule(family), "the declared retentions are consistent")
    ensure(len(modes.variables(family, "binding")) == 3,
           "three retained cycles leave three bases to choose")
    binding = modes.binding_model(family)
    conservative = modes.conservative_model(family)
    per_mode = modes.per_mode_model(family)
    ensure(per_mode["charge"] == {"arena": 2}, "every single mode still costs two")
    ensure(binding["status"] == "checked" and binding["charge"] == {"arena": 3},
           "retention around the cycle costs the single-layout span")
    ensure(conservative["charge"] == {"arena": 3}, "one layout costs three")
    ensure(binding["optimality_replay"]["status"] == "verified",
           "the binding optimum must replay independently")


def _charges_stay_inside_each_arena() -> None:
    """Two arenas with different separations: nothing crosses and nothing is summed."""
    triangle = ((0, 1), (0, 2), (1, 2))
    raw = _contract("two-arenas", (1, 1, 1, 2, 2, 2),
                    [("m0", [("v0", 0, 2), ("v1", 0, 2), ("v3", 0, 2), ("v4", 0, 2)]),
                     ("m1", [("v0", 0, 2), ("v2", 0, 2), ("v3", 0, 2), ("v5", 0, 2)]),
                     ("m2", [("v1", 0, 2), ("v2", 0, 2), ("v4", 0, 2), ("v5", 0, 2)])],
                    arena_of={"v3": "slow", "v4": "slow", "v5": "slow"})
    family = modes.parse_family(raw)
    nodes = modes.variables(family, "conservative")
    home = {node.name: node.arena for node in nodes}
    ensure(all(home[left] == home[right] for left, right in modes.interference(family, nodes)),
           "the all-mode relation must never join two arenas")
    receipt = modes.solve_model(family, "conservative")
    spans = {row["arena"]: row["best_span"] for row in receipt["arenas"]}
    ensure(spans == {"arena": _minimum_span(triangle, (1, 1, 1)),
                     "slow": _minimum_span(triangle, (2, 2, 2))},
           f"each arena's span must equal its own independent enumeration: {spans}")
    conservative = modes.conservative_model(family)
    per_mode = modes.per_mode_model(family)
    binding = modes.binding_model(family)
    ensure(conservative["charge"] == {"arena": 3, "slow": 6}
           and per_mode["charge"] == {"arena": 2, "slow": 4}
           and binding["charge"] == {"arena": 2, "slow": 4},
           "every charge carries one span per arena, and the arenas differ")
    ensure(per_mode["graph_cross_check"]["agrees"],
           "the graph search must agree with the single-trace oracle in both arenas")
    ensure(conservative["optimality_replay"]["status"] == "verified"
           and binding["optimality_replay"]["status"] == "verified",
           "the per-arena replay must verify where the relation crosses no arena")
    ensure(modes.compare(family, per_mode, conservative, binding)["ordering_holds"] is True,
           "the ordering is read inside each arena")
    legal = [{"id": "v0", "arena": "arena", "base": 0},
             {"id": "v1", "arena": "arena", "base": 1},
             {"id": "v2", "arena": "arena", "base": 2},
             {"id": "v3", "arena": "slow", "base": 0},
             {"id": "v4", "arena": "slow", "base": 2},
             {"id": "v5", "arena": "slow", "base": 4}]
    ensure(not modes.check_single_layout(family, legal)
           and not modes.replay_by_mode(family, legal),
           "both readings must accept a layout legal in every mode of both arenas")
    crossed = [dict(row) for row in legal]
    crossed[5]["base"] = 3
    ensure(any("overlap" in finding and "v4/v5" in finding
               for finding in modes.check_single_layout(family, crossed)),
           "an overlap confined to one arena is still a finding")
    over = [dict(row) for row in legal]
    over[0]["base"] = 3
    ensure(any("capacity" in finding and "v0" in finding
               for finding in modes.check_single_layout(family, over)),
           "free bytes in another arena do not pay for this one")


def _per_mode_limits_agree() -> None:
    raw = _contract("limits", (1, 2, 1),
                    [("m0", [("v0", 0, 4), ("v1", 1, 3)]),
                     ("m1", [("v1", 0, 2), ("v2", 1, 4)]),
                     ("m2", [("v0", 0, 2), ("v2", 0, 3)])])
    family = modes.parse_family(raw)
    receipt = modes.solve_model(family, "per-mode")
    nodes = modes.variables(family, "per-mode")
    ensure(receipt["bases"] is not None, "the per-mode limit must complete")
    plans = modes.layouts(family, nodes, receipt["bases"])
    ensure(not modes.check_layout_family(family, plans), "each mode's layout must check")
    oracle = {mode.name: memory.solve_exact(mode.case)["arenas"][0]["best_span"]
              for mode in family.modes}
    ensure(modes.charge(family, plans) == {"arena": max(oracle.values())},
           "the graph search at the per-mode limit must agree with the single-trace oracle")
    ensure(modes.per_mode_model(family)["graph_cross_check"]["agrees"],
           "the model's own cross-check must record that agreement")


def _budget_never_becomes_a_verdict() -> None:
    family = modes.parse_family(_graph_contract(((0, 1), (0, 2), (1, 2)), (1, 1, 1, 1)))
    cut = modes.solve_model(family, "conservative", work_budget=1)
    ensure(cut["status"] == "incomplete" and cut["bases"] is None,
           "an exhausted budget is not an optimum")
    ensure(all(row["certificate"] is None for row in cut["arenas"]
               if row["status"] == "incomplete"),
           "an incomplete arena carries no certificate")
    nodes = modes.variables(family, "conservative")
    ensure(modes.replay_optimum(nodes, cut, lambda _: [])["status"] == "not-claimed",
           "there is nothing to replay without a claimed optimum")
    whole = modes.solve_model(family, "conservative")
    short = modes.replay_optimum(nodes, whole,
                                lambda trial: modes.check_single_layout(
                                    family, [{"id": node.name, "arena": node.arena,
                                              "base": trial[node.name]} for node in nodes]),
                                work_budget=2)
    ensure(short["status"] == "incomplete" and short["findings"],
           "a replay cutoff leaves the optimality claim unchecked")
    ensure(modes.replay_optimum(nodes, whole, lambda _: ["planted finding"])["status"]
           == "rejected", "a witness the checker refuses is a rejected receipt")
    for invalid in (0, -1, True):
        try:
            modes.solve_model(family, "conservative", invalid)
        except memory.CaseError:
            continue
        raise AssertionError("invalid work budget accepted")
    try:
        modes.variables(family, "interval")
    except memory.CaseError:
        pass
    else:
        raise AssertionError("unknown sharing model accepted")


def _parse_refusals() -> None:
    base = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    ensure(modes.parse_family(base).name == "parse", "the positive fixture must parse")
    mutations: list[dict[str, Any]] = []
    unknown = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    unknown["objective"] = "smallest"
    mutations.append(unknown)
    missing = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    del missing["provenance"]
    mutations.append(missing)
    field = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    field["identities"][0]["pinned"] = True
    mutations.append(field)
    duplicate = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    duplicate["identities"][1]["id"] = "v0"
    mutations.append(duplicate)
    ghost = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    ghost["modes"][0]["lifetimes"][1]["id"] = "v9"
    mutations.append(ghost)
    twice = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    twice["modes"][0]["lifetimes"][1]["id"] = "v0"
    mutations.append(twice)
    idle = _contract("parse", (1, 1), [("m0", [("v0", 0, 2)])])
    mutations.append(idle)
    order = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    order["modes"][0]["lifetimes"][0]["reuse"] = 0
    mutations.append(order)
    empty = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    empty["modes"] = []
    mutations.append(empty)
    rule = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    rule["binding"]["rule"] = "best-effort"
    mutations.append(rule)
    retained = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    retained["binding"]["transitions"][0]["retained"] = ["v0"]
    mutations.append(retained)
    stranger = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    stranger["binding"]["transitions"][0]["source"] = "m9"
    mutations.append(stranger)
    repeated = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    repeated["binding"]["transitions"].append(dict(repeated["binding"]["transitions"][0]))
    mutations.append(repeated)
    negative = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])])
    negative["binding"]["transitions"][0]["at_source"] = -1
    mutations.append(negative)
    nothing = _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 2)])],
                        rule="retained-bases-equal")
    mutations.append(nothing)
    for mutant in mutations:
        try:
            modes.parse_family(mutant)
        except memory.CaseError:
            continue
        raise AssertionError(f"malformed family accepted: {mutant}")
    ensure(modes.family_hash(modes.parse_family(base))
           != modes.family_hash(modes.parse_family(
               _contract("parse", (1, 1), [("m0", [("v0", 0, 2), ("v1", 0, 3)])]))),
           "the receipt hash must bind a changed lifetime")


def _report_replays() -> None:
    receipt = modes.report("test-revision")
    ensure(not receipt["errors"], f"declared witness replay failed: {receipt['errors']}")
    ensure(receipt == modes.report("test-revision"), "the report must reproduce")
    charges = {case["contract"]["name"]: case["comparison"]["charges"]
               for case in receipt["cases"]}
    ensure(charges["pairwise-modes-ab-ac-bc"] == {"per_mode": {"arena": 2},
                                                  "binding": {"arena": 2},
                                                  "conservative": {"arena": 3}},
           "the pairwise witness needs three units for one layout against a peak of two")
    ensure(charges["induced-five-cycle"]["conservative"] == {"arena": 3}
           and charges["induced-five-cycle"]["per_mode"] == {"arena": 2},
           "the five-cycle witness exceeds every per-mode optimum")
    ensure(charges["retained-cycle-rebinds"] == {"per_mode": {"arena": 2},
                                                 "binding": {"arena": 3},
                                                 "conservative": {"arena": 3}},
           "retention across the switch returns the binding family to one layout's cost")
    ensure(charges["live-identity-at-switch"]["binding"] is None,
           "a refused binding family carries no charge")
    ensure(charges["two-arena-separation"] == {"per_mode": {"arena": 2, "slow": 4},
                                               "binding": {"arena": 2, "slow": 4},
                                               "conservative": {"arena": 3, "slow": 6}},
           "two arenas carry separate charges and neither is summed into the other")
    by_name = {case["contract"]["name"]: case for case in receipt["cases"]}
    refused = by_name["live-identity-at-switch"]["binding"]
    ensure(refused["optimality_replay"] is None and refused["charge"] is None
           and by_name["live-identity-at-switch"]["comparison"]["ordering_holds"] is None,
           "a family refused at its switch rule searches no optimum, so it replays none "
           "and exhibits no ordering")
    separated = by_name["two-arena-separation"]
    ensure(separated["conservative"]["optimality_replay"]["status"] == "verified"
           and separated["binding"]["optimality_replay"]["status"] == "verified",
           "the per-arena replay must verify on a two-arena witness")
    ensure(all(case["comparison"]["ordering_holds"] is not False for case in receipt["cases"]),
           "the three charges must stay ordered wherever all three exist")


def cases() -> list[Case]:
    return [
        Case("modes exact search against independent enumeration", _exact_against_enumeration),
        Case("modes conservative relation without an interval model", _not_an_interval_graph),
        Case("modes independent checkers catch a wrong one", _wrong_checkers_are_caught),
        Case("modes switch-rule refusals and retained bases", _switch_rule_refusals),
        Case("modes retention costs the single layout", _retention_costs_the_single_layout),
        Case("modes charges stay inside each arena", _charges_stay_inside_each_arena),
        Case("modes per-mode limit agrees with the single-trace oracle", _per_mode_limits_agree),
        Case("modes budget cutoffs and invalid settings", _budget_never_becomes_a_verdict),
        Case("modes family parse refusals", _parse_refusals),
        Case("modes replayable declared witnesses", _report_replays),
    ]
