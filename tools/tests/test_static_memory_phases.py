# SPDX-License-Identifier: Apache-2.0
"""Independent checks of the phase model, its candidate rules and its witnesses."""

import math
from dataclasses import replace
from itertools import pairwise
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory_phases as phases

RULES = (*phases.RULES, *phases.MUTANTS)

# The clearing services each rule's own words name, written here and not read from the
# module, so that a rule mapped to the wrong services there disagrees with this oracle.
SERVICES: dict[str, tuple[str, ...]] = {
    "R0": (),
    "R1": (),
    "R2": ("await-completions", "clear-roots", "post-barrier-pass"),
    "R2-skip-device": ("clear-roots", "post-barrier-pass"),
    "R2-skip-pass": ("await-completions", "clear-roots"),
}


def _completions(comp: phases.Composition, offsets: dict[str, int]) -> dict[str, int]:
    """Resolve acceptance independently, chained acceptance included."""
    declared = {transfer.name: (component, transfer)
                for component in comp.components for transfer in component.transfers}
    done: dict[str, int] = {}
    for _round in range(len(declared) + 1):
        for name, (component, transfer) in declared.items():
            if name in done:
                continue
            if transfer.depends_on is None:
                done[name] = component.phase_bounds[transfer.accept_phase] + offsets[name]
            elif transfer.depends_on in done:
                done[name] = done[transfer.depends_on] + offsets[name]
    ensure(len(done) == len(declared), "acceptance did not resolve")
    return done


def _owners(comp: phases.Composition) -> dict[str, list[str | None]]:
    """One holder per extent per tick, read from the declared starts alone."""
    starts = {obj.id: component.phase_bounds[obj.live_phases[0]]
              for component in comp.components for obj in component.objects}
    extents = {obj.id: obj.extent
               for component in comp.components for obj in component.objects}
    table: dict[str, list[str | None]] = {}
    for chain in comp.chains:
        ticks: list[str | None] = [None] * comp.horizon
        for position, name in enumerate(chain):
            last = starts[chain[position + 1]] if position + 1 < len(chain) else comp.horizon
            for tick in range(starts[name], min(last, comp.horizon)):
                ticks[tick] = name
        table[extents[chain[0]]] = ticks
    return table


def _oracle(comp: phases.Composition, offsets: dict[str, int], rule: str) -> list[str]:
    """A tick machine over the same model, written apart from the interval checker."""
    completions = _completions(comp, offsets)
    owners = _owners(comp)
    found: list[str] = []
    for component in comp.components:
        bounds = component.phase_bounds
        for obj in component.objects:
            ticks = owners[obj.extent]
            start = bounds[obj.live_phases[0]]
            live_end = bounds[obj.live_phases[-1] + 1]
            occupancy = (live_end if obj.retained_through is None
                         else bounds[obj.retained_through + 1])
            mine = tuple(completions[transfer.name] for transfer in component.transfers
                         if transfer.object_id == obj.id)
            for tick in range(start, min(occupancy, comp.horizon)):
                if ticks[tick] not in (None, obj.id):
                    found.append(f"occupancy-overlap:{obj.id}:{tick}")
                    break
            found.extend(f"device-completion:{obj.id}:{landing}" for landing in sorted(mine)
                         if landing < comp.horizon and ticks[landing] not in (None, obj.id))
            if obj.stale_holder:
                for tick in _exposure_ticks(comp, rule, occupancy, live_end, mine):
                    if ticks[tick] not in (None, obj.id):
                        found.append(f"stale-representation:{obj.id}:{tick}")
                        break
    return found


def _exposure_ticks(comp: phases.Composition, rule: str, occupancy: int, live_end: int,
                    completions: tuple[int, ...]) -> list[int]:
    """Every tick a retained representation survives, walked service by service.

    This is a forward walk over the services `SERVICES` assigns the rule, not a pair
    of endpoints: the clock advances past each accepted completion, then over the root
    clearing, and the representation is gone only once a full pass has run. A rule
    that names no pass never loses it, which is why R0, R1 and the pass-skipping
    mutant expose every later tick.
    """
    clock = live_end if rule == "R0" else occupancy
    schedule = SERVICES[rule]
    for service in schedule:
        if service == "await-completions":
            clock = max((clock, *completions))
        elif service == "clear-roots":
            clock += comp.root_clear
    if "post-barrier-pass" not in schedule:
        return list(range(clock, comp.horizon))
    return list(range(clock, min(clock + comp.sweep, comp.horizon)))


def _expected_timings(comp: phases.Composition, delta: int) -> int:
    """The admitted timing space's size, counted apart from the module that builds it."""
    windows = [transfer.window for component in comp.components
               for transfer in component.transfers]
    if not windows:
        return 1
    return math.prod(windows) if delta == 0 else len(windows)


def _enumeration_agrees() -> None:
    seen: set[str] = set()
    for comp in phases.fixtures():
        for rule in RULES:
            for delta in (0, 1, 4):
                space = phases.timing_space(comp, delta)
                expected = any(_oracle(comp, offsets, rule) for offsets in space)
                observed = phases.exhaustive_check(comp, rule, delta)
                ensure(observed["verdict"] == ("unsafe" if expected else "safe"),
                       f"{comp.name}/{rule}/{delta}: interval checker and tick oracle differ")
                ensure(len(space) == _expected_timings(comp, delta),
                       f"{comp.name}/{delta}: the enumerated space is not the whole product")
                ensure(observed["timings"] == len(space), "enumeration size must be reported")
                seen.add(observed["verdict"])
    ensure(seen == {"safe", "unsafe"}, "the enumeration must decide both ways")


def _soundness_over_the_fixture() -> None:
    cells: set[str] = set()
    for comp in phases.fixtures():
        for summary in phases.SUMMARIES:
            for rule in RULES:
                row = phases.agreement(comp, rule, summary)
                cells.add(row["classification"])
                if summary != "honest" or rule != "R2":
                    continue
                ensure(row["classification"] != "unsound-acceptance",
                       f"{comp.name}: R2 accepted what the enumeration refutes")
                if row["compositional"]["accept"]:
                    ensure(not any(_oracle(comp, offsets, rule)
                                   for offsets in phases.timing_space(comp)),
                           f"{comp.name}: the tick oracle refutes an R2 acceptance")
    ensure(cells == {"sound-acceptance", "unsound-acceptance",
                     "necessary-refusal", "conservative-refusal"},
           f"the comparison must populate every cell, not only {sorted(cells)}")


def _rules_are_separated() -> None:
    by_rule: dict[str, set[str]] = {rule: set() for rule in RULES}
    for comp in phases.fixtures():
        for rule in RULES:
            by_rule[rule].add(phases.agreement(comp, rule)["classification"])
    for rule in ("R0", "R1", "R2-skip-device", "R2-skip-pass"):
        ensure("unsound-acceptance" in by_rule[rule],
               f"{rule} must be refuted by some composition")
    ensure("unsound-acceptance" not in by_rule["R2"], "R2 must survive the fixture")
    ensure("sound-acceptance" in by_rule["R2"], "R2 must accept something")


def _counterexamples_reproduce() -> None:
    fixtures = {comp.name: comp for comp in phases.fixtures()}
    for summary, name, _reason in phases.COUNTEREXAMPLES:
        comp = fixtures[name]
        honest = phases.agreement(comp, "R2", "honest")
        broken = phases.agreement(comp, "R2", summary)
        ensure(not honest["compositional"]["accept"],
               f"{name}: the honest certificate must refuse this plan")
        ensure(broken["compositional"]["accept"],
               f"{name}: the {summary} summary must accept it")
        ensure(broken["exhaustive"]["verdict"] == "unsafe",
               f"{name}: the enumeration must refute the accepted plan")
        witness = broken["exhaustive"]["witness"]
        ensure(bool(_oracle(comp, witness["offsets"], "R2")),
               f"{name}: the reported witness must reproduce independently")
    ensure(len({name for _s, name, _r in phases.COUNTEREXAMPLES}) == 3,
           "each summary needs its own counterexample")


def _reductions_are_searched() -> None:
    """The size of a counterexample is a search result here, not an adjective."""
    fixtures = {comp.name: comp for comp in phases.fixtures()}
    shrank = False
    for summary, name, _reason in phases.COUNTEREXAMPLES:
        row = phases.reduction_report(fixtures[name], summary)
        reduced, _applied = phases.reduce_counterexample(fixtures[name], summary)
        ensure(phases.is_counterexample(reduced, summary),
               f"{summary}: the reduced witness must still be a counterexample")
        witness = row["reduced_exhaustive"]["witness"]
        ensure(bool(_oracle(reduced, witness["offsets"], "R2")),
               f"{summary}: the reduced witness must reproduce through the tick oracle")
        ensure(all(row["reduced_size"][key] <= row["source_size"][key]
                   for key in row["source_size"]),
               f"{summary}: a reduction may not grow the composition")
        ensure(all(operator in phases.REDUCTIONS for operator in row["applied"]),
               f"{summary}: an undeclared reduction was applied")
        shrank = shrank or row["reduced_size"] != row["source_size"]
        ensure(not phases.reduce_counterexample(reduced, summary)[1],
               f"{summary}: the search must reach a fixpoint")
    ensure(shrank, "the reduction search must actually shrink some counterexample")
    for summary in ("drop-retained", "drop-completion-bound"):
        name = next(row[1] for row in phases.COUNTEREXAMPLES if row[0] == summary)
        reduced, _applied = phases.reduce_counterexample(fixtures[name], summary)
        ensure(len(reduced.components) == 1,
               f"{summary}: this defect needs no composition, so the claim is not minimality")


def _one_component_can_chain_transfers() -> None:
    """A dependency need not cross the component boundary a reduction preserves."""
    component = phases.Component(
        "local-chain", (0, 2, 11, 16), ("source", "wait", "successor"),
        (phases.Obj("old", "e", (0,)), phases.Obj("new", "e", (2,))),
        (phases.Transfer("first", "old", 0, 6),
         phases.Transfer("second", "old", 0, 6, depends_on="first")),
        declared_window=6, declared_outstanding=10)
    comp = phases.Composition("one-component-chain", (component,), (("old", "new"),), 16)
    phases.validate(comp)
    ensure(phases.is_counterexample(comp, "chain-local-window"),
           "a local transfer chain must refute the per-transfer window summary")
    witness = phases.exhaustive_check(comp, "R2")["witness"]
    ensure(bool(_oracle(comp, witness["offsets"], "R2")),
           "the one-component hazard must reproduce through the independent tick oracle")


def _barrier_mutants_are_caught() -> None:
    for mutant, hazard in (("R2-skip-device", "device-completion"),
                           ("R2-skip-pass", "stale-representation")):
        rows = [phases.agreement(comp, mutant) for comp in phases.fixtures()]
        caught = [row for row in rows if row["classification"] == "unsound-acceptance"]
        ensure(bool(caught), f"{mutant} was not caught by any composition")
        kinds = {item["kind"] for row in caught
                 for item in row["exhaustive"]["witness"]["hazards"]}
        ensure(hazard in kinds, f"{mutant} must be caught by its own hazard, not {kinds}")
        honest = [phases.agreement(comp, "R2") for comp in phases.fixtures()]
        for mutated, correct in zip(rows, honest, strict=True):
            ensure(mutated["compositional"]["accept"] or not correct["compositional"]["accept"],
                   f"{mutant} removes an obligation, so it cannot refuse what R2 accepts")


def _certificate_is_the_whole_input() -> None:
    comp = next(c for c in phases.fixtures() if c.name == "long-window-outstanding")
    certs = phases.certificates(comp)
    before = phases.compositional_check(certs, comp.chains, "R2", comp.root_clear, comp.sweep)
    radio = comp.components[0]
    shorter = replace(radio, transfers=(replace(radio.transfers[0], window=1),))
    moved = replace(comp, components=(shorter, comp.components[1]))
    ensure(phases.certificates(moved) == certs,
           "a hidden timing change must not move the certificate")
    after = phases.compositional_check(phases.certificates(moved), moved.chains, "R2",
                                       moved.root_clear, moved.sweep)
    ensure(before == after, "the compositional verdict read something outside the certificate")
    ensure(phases.exhaustive_check(comp, "R2")["timings"]
           > phases.exhaustive_check(moved, "R2")["timings"],
           "the enumeration must be the side that grows with the timing space")
    for check in (before, after):
        ensure(check["comparisons"] == sum(max(len(chain) - 1, 0) for chain in comp.chains),
               "the compositional check is one comparison per adjacent chain pair")
    chained = next(c for c in phases.fixtures() if c.name == "chained-completion-windows")
    ensure(phases.compositional_check(phases.certificates(chained), chained.chains, "R2",
                                      chained.root_clear, chained.sweep)["comparisons"]
           < phases.exhaustive_check(chained, "R2")["timings"],
           "the compositional check must not grow with the product of component timings")


def _adversarial_timing_is_reported() -> None:
    comp = next(c for c in phases.fixtures() if c.name == "late-successor-safe")
    inside = phases.exhaustive_check(comp, "R2")
    ensure(inside["verdict"] == "safe" and phases.agreement(comp, "R2")[
        "classification"] == "sound-acceptance", "the declared windows must hold here")
    verdicts = {delta: phases.exhaustive_check(comp, "R2", delta)
                for delta in phases.OUT_OF_WINDOW_DELTAS}
    ensure(verdicts[1]["verdict"] == "safe" and verdicts[4]["verdict"] == "unsafe",
           "a violated certificate must void the conclusion at some overrun")
    ensure(verdicts[4]["timings"] == 1 and verdicts[4]["out_of_window_delta"] == 4,
           "the adversarial family holds the other transfers at their declared worst case")
    ensure(any(row["max_gated_start_shortfall"] > 0 and row["verdict"] == "safe"
               for row in verdicts.values()),
           "an event-gated implementation's shortfall is reported apart from the hazard")


def _declared_bounds_are_recomputed() -> None:
    """The one field R2's soundness rests on is derived, not taken on trust."""
    for comp in phases.fixtures():
        recomputed = phases.true_outstanding(comp)
        for component in comp.components:
            ensure(component.declared_outstanding == recomputed[component.name],
                   f"{comp.name}/{component.name}: the fixture must declare the bound "
                   "its own accepted transfers admit")
    comp = next(c for c in phases.fixtures() if c.name == "long-window-outstanding")
    radio, parse = comp.components
    lying = replace(comp, components=(replace(radio, declared_outstanding=0), parse))
    try:
        phases.exhaustive_check(lying, "R2")
    except ValueError:
        pass
    else:
        raise AssertionError("a certificate its own transfers falsify was admitted")
    generous = replace(comp, components=(replace(radio, declared_outstanding=9), parse))
    phases.validate(generous)
    ensure(phases.reuse_bound(phases.certificates(generous)["radio"], "a-rx", "R2", 1, 2)
           > phases.reuse_bound(phases.certificates(comp)["radio"], "a-rx", "R2", 1, 2),
           "an over-declared bound stays admissible and only delays reuse")


def _covering_certificate_is_a_join() -> None:
    """The published certificate is computed from both branches and can refuse them."""
    comp = next(c for c in phases.fixtures() if c.name == "resident-authority-after-window")
    session = comp.components[0]
    plain = phases.certificate(replace(
        session, objects=(replace(session.objects[0], stale_holder=False),),
        transfers=(), declared_window=0, declared_outstanding=0))
    rich = phases.certificate(session)
    joined = phases.publish_covering(plain, rich)
    ensure(joined["retained_holders"] == rich["retained_holders"]
           and joined["declared_window"] == rich["declared_window"],
           "the join must take every field at its upper bound")
    retaining = phases.certificate(replace(session, objects=(
        replace(session.objects[0], retained_through=1),)))
    ensure(phases.publish_covering(plain, retaining)["retained_occupancy"]
           == retaining["retained_occupancy"],
           "the join must keep a retention only one branch declares")
    ensure(phases.reuse_bound(joined, "a-ctx", "R2", comp.root_clear, comp.sweep)
           >= max(phases.reuse_bound(plain, "a-ctx", "R2", comp.root_clear, comp.sweep),
                  phases.reuse_bound(rich, "a-ctx", "R2", comp.root_clear, comp.sweep)),
           "the published bound must cover both branches")
    for other in (replace(session, labels=("idle", "serve")),
                  replace(session, phase_bounds=(0, 5, 14))):
        try:
            phases.publish_covering(plain, phases.certificate(other))
        except ValueError:
            continue
        raise AssertionError("a join accepted two different public schedules")


def _secret_phase_selection() -> None:
    witness = phases.secret_phase_witness()
    low, high = witness["runs"]
    ensure(low["labels"] == high["labels"] and low["phase_bounds"] == high["phase_bounds"],
           "the two runs must be indistinguishable in their public labels")
    ensure(low["selected_occupancy_end"] != high["selected_occupancy_end"]
           and low["accepted_transfers"] != high["accepted_transfers"],
           "the secret must actually select a different phase content")
    ensure(low["event_gated_reuse"] != high["event_gated_reuse"],
           "the witness must exhibit a difference an observer can time")
    ensure(low["successor_start"] == high["successor_start"]
           and witness["successor_binding_equal"],
           "the binding this model does simulate is the same in both runs")
    ensure(low["own_reuse_bound"] < high["event_gated_reuse"],
           "coverage is not automatic: the cheaper branch's own bound covers only itself")
    ensure(witness["published_covers_both_runs"]
           and all(row["padded_reuse"] >= row["own_reuse_bound"] for row in witness["runs"]),
           "the published certificate must cover each branch's own bound")
    ensure(low["padded_reuse"] == high["padded_reuse"]
           and witness["padded_runs_safe"] and witness["padded_reuse_equal"],
           "padding to one published bound must equalize that observation safely")
    ensure(low["padded_reuse"] > low["event_gated_reuse"],
           "the padding cost must be visible in the run that needed nothing")
    ensure(set(witness["construction_guards"]) | set(witness["computed_observations"])
           <= {key for key, value in witness.items() if isinstance(value, bool)},
           "every named guard and observation must be a reported boolean")


def _refusals() -> None:
    comp = next(c for c in phases.fixtures() if c.name == "device-crosses-public-boundary")
    capture, init = comp.components
    obj = capture.objects[0]
    broken = [
        replace(comp, components=(replace(capture, phase_bounds=(0, 4, 4)), init)),
        replace(comp, components=(replace(capture, labels=("fill",)), init)),
        replace(comp, components=(replace(capture, objects=(replace(obj, live_phases=(0, 2)),)),
                                  init)),
        replace(comp, components=(replace(capture, objects=(replace(obj, retained_through=2),)),
                                  init)),
        replace(comp, chains=(("a-buf",),)),
        replace(comp, chains=(("a-buf", "b-buf", "a-buf"),)),
        replace(comp, chains=(("b-buf", "a-buf"),)),
        replace(comp, components=(replace(capture, declared_window=1), init)),
        replace(comp, components=(replace(capture, declared_outstanding=0), init)),
        replace(comp, components=(capture, replace(init, name="capture"))),
        replace(comp, horizon=0),
    ]
    for mutant in broken:
        try:
            phases.validate(mutant)
        except ValueError:
            continue
        raise AssertionError(f"a malformed composition was accepted: {mutant.name}")
    for bad in ("R3", "reuse-when-convenient"):
        try:
            phases.reuse_bound(phases.certificates(comp)["capture"], "a-buf", bad, 1, 2)
        except ValueError:
            continue
        raise AssertionError("an unknown rule produced a bound")
    try:
        phases.summarize(phases.certificates(comp), "drop-everything")
    except ValueError:
        return
    raise AssertionError("an unknown certificate summary was accepted")


def _components_on_chains(comp: phases.Composition) -> int:
    """How many components a per-pair comparison has to consult, counted here."""
    home = {obj.id: component.name for component in comp.components
            for obj in component.objects}
    return len({home[name] for chain in comp.chains
                for pair in pairwise(chain) for name in pair})


def _report_replays() -> None:
    receipt: dict[str, Any] = phases.report("test-revision")
    ensure(not receipt["errors"], f"phase experiment replay failed: {receipt['errors']}")
    ensure(receipt == phases.report("test-revision"), "the phase report must reproduce")
    ensure(receipt["scope"] and receipt["open_obligations"]
           and receipt["conjecture"]["status"].startswith("conjecture"),
           "the receipt must carry its scope, obligations and conjecture status")
    ensure(len(receipt["agreements"])
           == len(phases.fixtures()) * len(phases.SUMMARIES) * len(RULES),
           "every composition, summary and rule is decided")
    for row in receipt["compositions"]:
        comp = next(c for c in phases.fixtures() if c.name == row["name"])
        ensure(row["certificates_read"] == _components_on_chains(comp),
               f"{row['name']}: the verdict must read one certificate per compared component")
        ensure(row["certificates_read"] <= row["components"]
               and row["compositional_comparisons"] <= row["objects"],
               f"{row['name']}: the compositional cost must not exceed the composition")
        ensure(all(bound["declared"] >= bound["recomputed"]
                   for bound in row["outstanding_bounds"].values()),
               f"{row['name']}: a declared bound below the recomputed one must not replay")
    honest = [row for row in receipt["agreements"] if row["summary"] == "honest"]
    ensure(sum(receipt["honest_census"].values()) == len(honest)
           and all(receipt["honest_census"][cell]
                   == sum(1 for row in honest if row["classification"] == cell)
                   for cell in receipt["honest_census"]),
           "the honest census must count the honest rows it reports")
    broken = phases.report("test-revision")
    broken["agreements"] = [row for row in broken["agreements"]
                            if not (row["summary"] == "honest" and row["rule"] == "R0")]
    ensure(bool(phases.invariants(broken["agreements"], broken["adversarial_timings"],
                                  broken["secret_phase_selection"])),
           "a missing refutation must fail the experiment's own invariants")


def cases() -> list[Case]:
    return [
        Case("phases enumeration against an independent tick oracle", _enumeration_agrees),
        Case("phases bounded soundness over the fixture", _soundness_over_the_fixture),
        Case("phases candidate rules are separated", _rules_are_separated),
        Case("phases naive summaries and counterexamples", _counterexamples_reproduce),
        Case("phases counterexample reduction search", _reductions_are_searched),
        Case("phases one-component transfer chain", _one_component_can_chain_transfers),
        Case("phases barrier mutants are caught", _barrier_mutants_are_caught),
        Case("phases certificate is the compositional input", _certificate_is_the_whole_input),
        Case("phases declared outstanding bounds are recomputed", _declared_bounds_are_recomputed),
        Case("phases adversarial out-of-window timing", _adversarial_timing_is_reported),
        Case("phases covering certificate is a join", _covering_certificate_is_a_join),
        Case("phases secret-dependent selection witness", _secret_phase_selection),
        Case("phases malformed model refusals", _refusals),
        Case("phases replayable scoped report", _report_replays),
    ]
