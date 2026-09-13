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


def _independently_invalid(case: memory.Case, placement: list[dict[str, Any]]) -> bool:
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
            if not obj.start <= tick < obj.reuse:
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
    result = mutants.sweep([_fixture()], max_sites=1000, kinds=("certificate",))
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


def _tiny_classification_is_exact() -> None:
    result = mutants.sweep([_tiny()], max_sites=1000)
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
        "bound-raise-load": {mutants.KILLED: 1},
        "bound-lower-span": {mutants.KILLED: 1},
        "witness-refused": {mutants.KILLED: 2},
        "certificate-argument": {mutants.KILLED: 1},
    }
    ensure(_verdicts(result["outcomes"]) == expected,
           f"the tiny contract classified differently: {_verdicts(result['outcomes'])}")
    ensure(result["totals"] == {mutants.KILLED: 16, mutants.MISKILLED: 0,
                               mutants.SURVIVED: 0, mutants.STILLBORN: 3},
           f"unexpected tiny totals: {result['totals']}")
    ensure(not result["errors"], f"the tiny sweep reported {result['errors']}")


def _weakening_isolates_its_own_operators() -> None:
    fixture = _fixture()
    ensure(not mutants.sweep([fixture], max_sites=1000)["survivors"],
           "the complete checker must refuse every constructed violation")
    for clause, expected in (("alignment", ["alignment-shift"]),
                             ("overlap", ["lifetime-extend", "overlap-collide",
                                          "reuse-before-authority", "reuse-before-sweep"])):
        weak = mutants.sweep([fixture], checker=mutants.dropping(clause), max_sites=1000)
        survivors = sorted({item["operator"] for item in weak["survivors"]})
        ensure(survivors == expected,
               f"dropping {clause} left survivors {survivors}, expected {expected}")
        ensure(not weak["miskills"],
               f"dropping {clause} turned a kill into a miskill: {weak['miskills']}")
        ensure(bool(weak["errors"]), "a sweep with survivors must report them as errors")
    restored = mutants.sweep([fixture], max_sites=1000)
    ensure(not restored["survivors"] and not restored["errors"],
           f"restoring the clause must refuse every mutant again: {restored['errors']}")


def _sampling_is_reproducible_and_bounded() -> None:
    contracts = [_fixture(), _tiny()]
    first = mutants.sweep(contracts, seed=7, max_sites=1)
    ensure(first == mutants.sweep(contracts, seed=7, max_sites=1),
           "the sweep must reproduce under its own seed")
    counted = Counter((item["case"], item["operator"]) for item in first["outcomes"])
    ensure(max(counted.values()) == 1, "the site cap must bound each operator per contract")
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
    ensure(receipt["control"]["observed_survivor_operators"] == ["alignment-shift"],
           f"the weakened control did not isolate its clause: {receipt['control']}")
    ensure(receipt["certificates"]["feasibility_mutants"] > 0
           and receipt["certificates"]["optimality_mutants"] > 0,
           "both certificate kinds must carry mutants of their own")
    ensure(receipt["sweep"]["settings"]["seed"] == mutants.DEFAULT_SEED,
           "the receipt must record the seed it ran")


def _a_survivor_fails_the_command() -> None:
    weakened = mutants.sweep([_fixture()], checker=mutants.dropping("alignment"),
                             max_sites=1000)
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
        Case("mutants tiny classification is exact", _tiny_classification_is_exact),
        Case("mutants weakened clause isolates its operators",
             _weakening_isolates_its_own_operators),
        Case("mutants sampling is reproducible and bounded",
             _sampling_is_reproducible_and_bounded),
        Case("mutants replayable scoped report",
             _report_is_replayable_and_separates_the_two_certificates),
        Case("mutants survivor fails the command", _a_survivor_fails_the_command),
    ]
