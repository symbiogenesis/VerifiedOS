# SPDX-License-Identifier: Apache-2.0
"""Independent checks of the phase model, its candidate rules and its witnesses."""

from dataclasses import replace
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory_phases as phases

RULES = (*phases.RULES, *phases.MUTANTS)


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
                first, last = _exposure(comp, rule, occupancy, live_end, mine)
                for tick in range(first, min(last, comp.horizon)):
                    if ticks[tick] not in (None, obj.id):
                        found.append(f"stale-representation:{obj.id}:{tick}")
                        break
    return found


def _exposure(comp: phases.Composition, rule: str, occupancy: int, live_end: int,
              completions: tuple[int, ...]) -> tuple[int, int]:
    """The clearing service each rule supplies, re-derived from the rule's own words."""
    if rule == "R0":
        return live_end, comp.horizon
    if rule == "R1":
        return occupancy, comp.horizon
    waited = occupancy if rule == "R2-skip-device" else max((occupancy, *completions))
    barrier = waited + comp.root_clear
    if rule == "R2-skip-pass":
        return barrier, comp.horizon
    return barrier, barrier + comp.sweep


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
    ensure(low["padded_reuse"] == high["padded_reuse"]
           and witness["padded_runs_safe"] and witness["padded_reuse_equal"],
           "padding to one public bound must equalize that observation safely")
    ensure(low["padded_reuse"] > low["event_gated_reuse"],
           "the padding cost must be visible in the run that needed nothing")


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
    ensure(all(row["compositional"]["reads_component_product"] is False
               for row in receipt["agreements"]), "no verdict may enumerate component states")
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
        Case("phases barrier mutants are caught", _barrier_mutants_are_caught),
        Case("phases certificate is the compositional input", _certificate_is_the_whole_input),
        Case("phases adversarial out-of-window timing", _adversarial_timing_is_reported),
        Case("phases secret-dependent selection witness", _secret_phase_selection),
        Case("phases malformed model refusals", _refusals),
        Case("phases replayable scoped report", _report_replays),
    ]
