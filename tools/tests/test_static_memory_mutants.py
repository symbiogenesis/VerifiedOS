# SPDX-License-Identifier: Apache-2.0
"""Independent evidence that each operator constructs a violation and the sweep sees it."""

from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import static_memory as memory
from vos import static_memory_mutants as mutants
from vos.cli import static_memory as cli


def _object(identifier: str, *, arena: str = "a", size: int = 4, base: int = 0,
            alignment: int = 4, start: int = 0, payload_end: int = 1,
            authority_end: int = 2, sweep_end: int = 3,
            reuse: int = 4) -> dict[str, Any]:
    return {"id": identifier, "arena": arena, "size": size, "payload": size,
            "alignment": alignment, "start": start, "payload_end": payload_end,
            "authority_end": authority_end, "sweep_end": sweep_end, "reuse": reuse,
            "base": base}


def _fixture() -> dict[str, Any]:
    """One contract giving every operator at least one applicable site.

    Arena `a` holds an interfering pair and a successor rebound to the first object's
    declared slot after its whole barrier; arena `b` exists so a candidate can name a
    foreign arena, and holds the one unit-aligned object.
    """
    return {"name": "mutant-fixture", "mode": "single-fixed-trace",
            "provenance": "synthetic test fixture; no product measurement",
            "arenas": [{"id": "a", "owner": "owner-a", "capacity": 64},
                       {"id": "b", "owner": "owner-b", "capacity": 16}],
            "objects": [
                _object("x"),
                _object("y", base=4),
                _object("z", base=0, start=4, payload_end=5, authority_end=6,
                        sweep_end=7, reuse=8),
                _object("w", arena="b", alignment=1, payload_end=1, authority_end=1,
                        sweep_end=1, reuse=2),
            ]}


def _tiny() -> dict[str, Any]:
    """Two two-byte slots, the second rebound to the first at its reuse boundary."""
    return {"name": "tiny", "mode": "single-fixed-trace",
            "provenance": "synthetic test fixture; no product measurement",
            "arenas": [{"id": "a", "owner": "owner-a", "capacity": 8}],
            "objects": [
                _object("p", size=2, alignment=2, payload_end=1, authority_end=1,
                        sweep_end=1, reuse=2),
                _object("q", size=2, alignment=2, start=2, payload_end=3,
                        authority_end=3, sweep_end=3, reuse=4),
            ]}


def _independently_invalid(case: memory.Case, placement: list[dict[str, Any]], *,
                           hold_until: str = "reuse") -> bool:
    """Decide one candidate by enumerating declared bytes and ticks, not intervals."""
    identifiers = [row["id"] for row in placement]
    if sorted(identifiers) != sorted(obj.id for obj in case.objects):
        return True
    rows = {row["id"]: row for row in placement}
    capacities = {arena.id: arena.capacity for arena in case.arenas}
    for obj in case.objects:
        row = rows[obj.id]
        if row["arena"] != obj.arena or row["base"] % obj.alignment:
            return True
        if row["base"] + obj.size > capacities[obj.arena]:
            return True
    for tick in range(max(obj.reuse for obj in case.objects)):
        held: set[tuple[str, int]] = set()
        for obj in case.objects:
            if not obj.start <= tick < getattr(obj, hold_until):
                continue
            cells = {(obj.arena, byte) for byte
                     in range(rows[obj.id]["base"], rows[obj.id]["base"] + obj.size)}
            if held & cells:
                return True
            held |= cells
    return False


def _verdicts(outcomes: list[mutants.Outcome]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for item in outcomes:
        result.setdefault(item["operator"], {})
        counts = result[item["operator"]]
        counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1
    return result


def _placement_operators_construct_violations() -> None:
    case = memory.parse_case(_fixture())
    subject = mutants.subject_of(case)
    for operator in mutants.OPERATORS:
        if operator["kind"] == "certificate":
            continue
        built = 0
        for site in mutants.sites(operator, case):
            mutant = mutants.construct(operator["name"], subject, site)
            if isinstance(mutant, mutants.Refused):
                ensure(bool(mutant.reason), "a stillborn site must state its reason")
                continue
            built += 1
            ensure(_independently_invalid(mutant.case, mutant.placement),
                   f"{operator['name']} emitted a candidate the byte oracle accepts")
            findings = memory.check_placement(mutant.case, mutant.placement)
            tags = {mutants.tag(item) for item in findings}
            ensure(operator["targets"] in tags,
                   f"{operator['name']} was not refused by its own constraint: {findings}")
            ensure(tags <= {operator["targets"]},
                   f"{operator['name']} violated more than its own constraint: {findings}")
        ensure(built > 0, f"{operator['name']} constructed no mutant on the fixture")


def _certificate_operators_refuse_false_optimality() -> None:
    result = mutants.sweep([_fixture()], kinds=("certificate",))
    ensure(not result["errors"], f"the fixture receipt sweep reported {result['errors']}")
    counts = _verdicts(result["outcomes"])
    for operator in mutants.OPERATORS:
        if operator["kind"] != "certificate":
            continue
        seen = counts.get(operator["name"], {})
        ensure(seen.get(mutants.KILLED, 0) > 0,
               f"{operator['name']} never moved the optimality replay: {seen}")
        ensure(not seen.get(mutants.SURVIVED) and not seen.get(mutants.MISKILLED),
               f"{operator['name']} produced a survivor or a miskill: {seen}")
    for item in result["outcomes"]:
        if item["verdict"] == mutants.KILLED:
            ensure(bool(item["findings"]),
                   f"a refused replay must state its finding: {item}")
    bound = next(operator for operator in mutants.OPERATORS
                 if operator["targets"] == mutants.RECEIPT_BOUND)
    for refusal, verdict in ((mutants.REPLAY_ROW_REFUSAL, mutants.KILLED),
                             (mutants.REPLAY_SEARCH_REFUSAL, mutants.MISKILLED)):
        answer: dict[str, Any] = {"status": "rejected", "findings": [f"a: {refusal}"]}
        classified, _ = mutants.classify_replay(bound, answer, "a")
        ensure(classified == verdict,
               f"'{refusal}' must classify a bound mutant as {verdict}, not {classified}")


def _barrier_mutants_reach_each_incomplete_stage() -> None:
    case = memory.parse_case(_fixture())
    subject = mutants.subject_of(case)
    predecessor, _, successor, _ = case.objects
    for name, boundary, premature in (
            ("reuse-before-authority", "authority_end", "payload_end"),
            ("reuse-before-sweep", "sweep_end", "authority_end"),
            ("reuse-before-initialization", "reuse", "sweep_end")):
        built = mutants.construct(name, subject, (predecessor, successor))
        ensure(isinstance(built, mutants.Candidate), f"{name}: the stage must have a witness")
        if not isinstance(built, mutants.Candidate):
            raise TypeError("expected a constructed candidate")
        moved = next(obj for obj in built.case.objects if obj.id == successor.id)
        ensure(moved.start == getattr(predecessor, boundary) - 1,
               f"{name}: the successor must arrive before completion, not at completion")
        ensure(_independently_invalid(built.case, built.placement),
               f"{name}: real safe reuse must refuse the candidate")
        ensure(not _independently_invalid(built.case, built.placement, hold_until=premature),
               f"{name}: this defect must escape a checker releasing at {premature}")
    raw = _tiny()
    raw["objects"][0].update(payload_end=0, authority_end=0, sweep_end=0)
    empty_stage = mutants.subject_of(memory.parse_case(raw))
    for name in ("reuse-before-authority", "reuse-before-sweep"):
        built = mutants.construct(name, empty_stage, tuple(empty_stage.case.objects))
        ensure(isinstance(built, mutants.Refused),
               f"{name}: no time before an immediate barrier may count as a mutant")


def _coherent_false_optimum_needs_actual_replay() -> None:
    case = memory.parse_case(_tiny())
    subject = mutants.subject_of(case)
    original = memory.solve_exact(case)
    spans = memory.placement_spans(case, original["best_placement"])
    claim = mutants.construct_claim("certificate-false-optimum", subject, original, spans, "a")
    if not isinstance(claim, mutants.Claim):
        raise TypeError("the tiny arena has room for a translated witness")
    witness = claim.receipt["best_placement"]
    ensure(not _independently_invalid(case, witness),
           "the false optimum must carry an independently feasible witness")
    height = max(row["base"] + obj.size
                 for row, obj in zip(witness, case.objects, strict=True))
    arena = claim.receipt["arenas"][0]
    ensure(height > spans["a"] and arena["best_span"] == height
           and arena["proven_lower_bound"] == height and arena["optimality_gap"] == 0
           and arena["certificate"] == {"method": "exhaustive", "infeasible_through": height - 1},
           "all reported fields must agree; only the optimality claim is false")
    answer = memory.verify_optimality(case, claim.receipt)
    ensure(answer["status"] == "rejected"
           and answer["findings"] == [f"a: {mutants.REPLAY_SEARCH_REFUSAL}"]
           and answer["nodes"] > 0,
           f"Cartesian replay must exhibit a smaller feasible candidate: {answer}")
    weakened = mutants.dropping_replay(mutants.RECEIPT_SEARCH)
    ensure(weakened(case, claim.receipt, 100_000)["status"] == "verified",
           "the coherent false optimum must escape a replay discarding its search refusal")
    ensure(weakened(case, claim.receipt, 0)["status"] == "incomplete",
           "even the weakened control must not turn missing evidence into acceptance")


def _replay_weakening_isolates_certificate_families() -> None:
    fixture = _fixture()
    for target in {operator["targets"] for operator in mutants.OPERATORS
                   if operator["kind"] == "certificate"}:
        expected = {operator["name"] for operator in mutants.OPERATORS
                    if operator["targets"] == target}
        weak = mutants.sweep([fixture], replay=mutants.dropping_replay(target),
                             kinds=("certificate",))
        ensure({item["operator"] for item in weak["survivors"]} == expected,
               f"removing {target} must expose precisely its certificate operators")
        ensure(not weak["miskills"], f"removing {target} must preserve unrelated refusals")


def _tiny_classification_is_exact() -> None:
    result = mutants.sweep([_tiny()])
    expected = {
        "overlap-collide": {mutants.STILLBORN: 1},
        "alignment-shift": {mutants.KILLED: 2},
        "capacity-overflow": {mutants.KILLED: 2},
        "ownership-reassign": {mutants.STILLBORN: 2},
        "identity-duplicate": {mutants.KILLED: 2},
        "identity-drop": {mutants.KILLED: 2},
        "lifetime-extend": {mutants.KILLED: 1},
        "reuse-before-sweep": {mutants.KILLED: 1},
        "reuse-before-authority": {mutants.KILLED: 1},
        "reuse-before-initialization": {mutants.KILLED: 1},
        "bound-raise-load": {mutants.KILLED: 1},
        "bound-lower-span": {mutants.KILLED: 1},
        "witness-refused": {mutants.KILLED: 2},
        "certificate-argument": {mutants.KILLED: 1},
        "certificate-false-optimum": {mutants.KILLED: 1},
    }
    ensure(_verdicts(result["outcomes"]) == expected,
           f"the tiny contract classified differently: {_verdicts(result['outcomes'])}")
    ensure(result["totals"] == {mutants.KILLED: 18, mutants.MISKILLED: 0,
                               mutants.SURVIVED: 0, mutants.STILLBORN: 3},
           f"unexpected tiny totals: {result['totals']}")
    ensure(not result["errors"], f"the tiny sweep reported {result['errors']}")
    coverage = result["coverage"]
    ensure(coverage["sites_unvisited"] == 0
           and coverage["sites_visited"] == coverage["applicable_sites"],
           f"an uncapped sweep must visit every applicable site: {coverage}")
    ensure(coverage["sites_visited"] == sum(1 for item in result["outcomes"]
                                            if item["site"] != "n/a"),
           f"the visited count must match the sites that carry an outcome: {coverage}")


def _weakening_isolates_its_own_operators() -> None:
    fixture = _fixture()
    ensure(not mutants.sweep([fixture])["survivors"],
           "the complete checker must refuse every constructed violation")
    for clause in mutants.control_clauses():
        expected = sorted(operator["name"] for operator in mutants.OPERATORS
                          if operator["kind"] != "certificate"
                          and operator["targets"] == clause)
        weak = mutants.sweep([fixture], checker=mutants.dropping(clause))
        survivors = sorted({item["operator"] for item in weak["survivors"]})
        ensure(survivors == expected,
               f"dropping {clause} left survivors {survivors}, expected {expected}")
        ensure(not weak["miskills"],
               f"dropping {clause} turned a kill into a miskill: {weak['miskills']}")
        ensure(bool(weak["errors"]), "a sweep with survivors must report them as errors")
    ensure(mutants.control_clauses() == ["alignment", "capacity", "identity",
                                         "overlap", "ownership"],
           "every clause an operator targets must carry a control")
    restored = mutants.sweep([fixture])
    ensure(not restored["survivors"] and not restored["errors"],
           f"restoring the clause must refuse every mutant again: {restored['errors']}")


def _sampling_is_reproducible_and_bounded() -> None:
    contracts = [_fixture(), _tiny()]
    first = mutants.sweep(contracts, seed=7, max_sites=1)
    ensure(first == mutants.sweep(contracts, seed=7, max_sites=1),
           "the sweep must reproduce under its own seed")
    counted = Counter((item["case"], item["operator"]) for item in first["outcomes"])
    ensure(max(counted.values()) == 1, "the site cap must bound each operator per contract")
    ensure(first["coverage"]["sites_unvisited"] > 0,
           "a cap that bites must report the sites it left unvisited")
    uncapped = mutants.sweep(contracts, seed=7)
    ensure(uncapped["coverage"]["sites_unvisited"] == 0
           and uncapped["coverage"]["applicable_sites"]
           == first["coverage"]["applicable_sites"],
           "the applicable population must not depend on the cap")
    ensure(uncapped["totals"][mutants.KILLED] > first["totals"][mutants.KILLED],
           "an uncapped sweep must decide the sites the cap withheld")
    other = mutants.sweep(contracts, seed=8, max_sites=1)
    chosen = [(item["case"], item["operator"], item["site"]) for item in first["outcomes"]]
    ensure(chosen != [(item["case"], item["operator"], item["site"])
                      for item in other["outcomes"]],
           "a different seed must reach a different site")
    ensure(not first["survivors"] and not other["survivors"],
           "sampling must not change the verdict of a site it does reach")
    for invalid in (0, -1):
        try:
            mutants.sweep(contracts, max_sites=invalid)
        except memory.CaseError:
            continue
        raise AssertionError("an empty site cap was accepted")


def _report_is_replayable_and_separates_the_two_certificates() -> None:
    receipt = mutants.report("test-revision")
    ensure(not receipt["errors"], f"the declared sweep reported {receipt['errors']}")
    ensure(receipt == mutants.report("test-revision"), "the report must reproduce")
    totals = receipt["sweep"]["totals"]
    ensure(totals[mutants.SURVIVED] == 0 and totals[mutants.MISKILLED] == 0,
           f"the declared corpus must refuse every constructed violation: {totals}")
    ensure(totals[mutants.KILLED] > 0, "a sweep that kills nothing decides nothing")
    control = receipt["control"]
    ensure([row["clause_removed"] for row in control["clauses"]]
           == mutants.control_clauses(),
           f"every clause an operator targets must carry a control: {control}")
    ensure(control["clauses_exercised"] == control["clauses_declared"],
           f"a clause whose operators are all stillborn controls nothing: {control}")
    for row in control["clauses"]:
        ensure(row["observed_survivor_operators"] == row["expected_survivor_operators"]
               and row["mutants_available"] > 0 and not row["weakened_miskills"],
               f"the {row['clause_removed']} control did not isolate its operators: {row}")
    replay_control = receipt["replay_control"]
    ensure(replay_control["refusals_exercised"] == replay_control["refusals_declared"],
           f"every replay refusal needs a completed control: {replay_control}")
    for row in replay_control["refusals"]:
        ensure(row["observed_survivor_operators"] == row["expected_survivor_operators"]
               and row["mutants_available"] > 0 and not row["weakened_miskills"],
               f"the {row['refusal_removed']} replay control did not isolate its operators")
    certificates = receipt["certificates"]
    ensure(certificates["feasibility_mutants"] > 0
           and certificates["optimality_mutants"] > 0
           and certificates["contract_side_mutants"] > 0
           and certificates["feasibility_mutants"] == certificates["candidate_side_mutants"]
           + certificates["contract_side_mutants"],
           f"the two deliverables must be counted apart and add up: {certificates}")
    coverage = receipt["sweep"]["coverage"]
    ensure(coverage["sites_unvisited"] == 0 and coverage["applicable_sites"] > 0,
           f"the declared run must decide every applicable site: {coverage}")
    ensure(receipt["sweep"]["settings"]["seed"] == mutants.DEFAULT_SEED,
           "the receipt must record the seed it ran")


def _a_survivor_fails_the_command() -> None:
    weakened = mutants.sweep([_fixture()], checker=mutants.dropping("alignment"))
    ensure(bool(weakened["survivors"]) and bool(weakened["errors"]),
           "the weakened fixture must carry both survivors and an error")
    receipt = {"scope": "weakened fixture", "errors": weakened["errors"]}
    with patch.object(cli.mutants, "report", return_value=receipt), \
            redirect_stdout(StringIO()):
        code = cli.main(["mutants"])
    ensure(code == 1, "a surviving mutant must reach the command's exit status")


def cases() -> list[Case]:
    return [
        Case("mutants placement operators construct violations",
             _placement_operators_construct_violations),
        Case("mutants certificate operators refuse false optimality",
             _certificate_operators_refuse_false_optimality),
        Case("mutants barrier defects precede each completion",
             _barrier_mutants_reach_each_incomplete_stage),
        Case("mutants coherent false optimum requires replay",
             _coherent_false_optimum_needs_actual_replay),
        Case("mutants weakened replay isolates certificate families",
             _replay_weakening_isolates_certificate_families),
        Case("mutants tiny classification is exact", _tiny_classification_is_exact),
        Case("mutants weakened clause isolates its operators",
             _weakening_isolates_its_own_operators),
        Case("mutants sampling is reproducible and bounded",
             _sampling_is_reproducible_and_bounded),
        Case("mutants replayable scoped report",
             _report_is_replayable_and_separates_the_two_certificates),
        Case("mutants survivor fails the command", _a_survivor_fails_the_command),
    ]
