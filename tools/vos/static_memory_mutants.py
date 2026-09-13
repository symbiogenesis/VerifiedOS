# SPDX-License-Identifier: Apache-2.0
"""Constructed invalid candidates for the research placement oracle, and their verdicts.

Every operator builds a candidate or an optimality receipt whose stated constraint is
violated by arithmetic alone. Nothing here asks the checker what to build, so a verdict
is a statement about the checker and not about the construction. A site whose
construction cannot guarantee a violation is stillborn and decides nothing.

Killed, miskilled, survived and stillborn are counted apart. A survivor is the finding:
the checker accepted a constructed violation. A miskill is a refusal by an unrelated
clause, which is a finding about the error typing rather than about soundness.

The subject is the declared finite model in `static_memory.py` alone. Feasibility and
optimality stay separate subjects here as they are there: `check_placement` decides one
candidate, and `verify_optimality` additionally replays a bound argument. No admission
checker, CHERI representability, island or bank constraint is exercised or implied.
"""

import math
import random
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, TypedDict

from vos import static_memory as memory
from vos import static_memory_corpus as witnesses
from vos import static_memory_scale as scale

SCHEMA = "static-memory-mutants-v1"
GENERATOR = "tools/vos/static_memory_mutants.py"

KILLED = "killed"
MISKILLED = "miskilled"
SURVIVED = "survived"
STILLBORN = "stillborn"
VERDICTS = (KILLED, MISKILLED, SURVIVED, STILLBORN)

# The constraint a checker finding names is the word before its first colon.
CHECKER_TAGS = ("schema", "identity", "ownership", "alignment", "capacity", "overlap")

# What a refused optimality replay must have refused: the arena row's own bound claim,
# the witness the checker reads, or the exhaustion argument's own fields.
RECEIPT_BOUND = "receipt-bound"
RECEIPT_WITNESS = "receipt-witness"
RECEIPT_CERTIFICATE = "receipt-certificate"

KINDS = ("placement", "case", "certificate")
DEFAULT_SEED = 20260912
DEFAULT_MAX_SITES = 6
DEFAULT_WORK_BUDGET = 100_000

# The generated family stays tiny on purpose: every applicable site of every operator is
# mutated, so breadth is bought with sites rather than with object counts.
GENERATED_SIZES = (4,)

type Checker = Callable[[memory.Case, object], list[str]]


class Operator(TypedDict):
    """One declared mutation: what it moves, where it applies and what must refuse it."""

    name: str
    kind: str
    site_class: str
    targets: str
    construction: str


class Outcome(TypedDict):
    """One mutant's verdict, or the reason no mutant could be constructed at a site."""

    case: str
    operator: str
    kind: str
    site_class: str
    site: str
    targets: str
    verdict: str
    findings: list[str]
    reason: str | None


OPERATORS: tuple[Operator, ...] = (
    {"name": "overlap-collide", "kind": "placement", "site_class": "object-pair",
     "targets": "overlap",
     "construction": "give an interfering same-arena peer this object's own base, so "
                     "both slots contain that byte while both are live"},
    {"name": "alignment-shift", "kind": "placement", "site_class": "object",
     "targets": "alignment",
     "construction": "the first base above every extent in the arena that the declared "
                     "alignment does not divide"},
    {"name": "capacity-overflow", "kind": "placement", "site_class": "object",
     "targets": "capacity",
     "construction": "the first aligned base at or above the arena's occupied span "
                     "whose slot ends past the declared capacity"},
    {"name": "ownership-reassign", "kind": "placement", "site_class": "object",
     "targets": "ownership",
     "construction": "name another declared arena in the candidate row while the "
                     "contract keeps its own, so the two field sets disagree"},
    {"name": "identity-duplicate", "kind": "placement", "site_class": "object",
     "targets": "identity",
     "construction": "repeat one object's row, so the candidate names it twice"},
    {"name": "identity-drop", "kind": "placement", "site_class": "object",
     "targets": "identity",
     "construction": "remove one object's row, so the candidate places fewer objects "
                     "than the contract declares"},
    {"name": "lifetime-extend", "kind": "case", "site_class": "object-pair",
     "targets": "overlap",
     "construction": "hold a predecessor's extent one tick past its successor's first "
                     "instant on one shared slot"},
    {"name": "reuse-before-sweep", "kind": "case", "site_class": "object-pair",
     "targets": "overlap",
     "construction": "start the successor at the predecessor's sweep_end, inside the "
                     "initialization the contract still charges"},
    {"name": "reuse-before-authority", "kind": "case", "site_class": "object-pair",
     "targets": "overlap",
     "construction": "start the successor at the predecessor's authority_end, inside "
                     "the quarantine the contract still charges"},
    {"name": "bound-raise-load", "kind": "certificate", "site_class": "arena",
     "targets": RECEIPT_BOUND,
     "construction": "claim a charged load above the span the receipt's own witness "
                     "attains"},
    {"name": "bound-lower-span", "kind": "certificate", "site_class": "arena",
     "targets": RECEIPT_BOUND,
     "construction": "claim a best span below the one the receipt's own placement "
                     "attains"},
    {"name": "witness-refused", "kind": "certificate", "site_class": "object",
     "targets": RECEIPT_WITNESS,
     "construction": "move the witness past its arena, so the optimality claim carries "
                     "a candidate the placement checker refuses"},
    {"name": "certificate-argument", "kind": "certificate", "site_class": "arena",
     "targets": RECEIPT_CERTIFICATE,
     "construction": "change the height the exhaustion argument challenges, or claim "
                     "exhaustion where the receipt argued load equality"},
)

_PAIR_INTERFERING = ("overlap-collide",)
_PAIR_SUCCESSIVE = ("lifetime-extend", "reuse-before-sweep", "reuse-before-authority")
_ARENA_SITES = ("bound-raise-load", "bound-lower-span", "certificate-argument")


@dataclass(frozen=True)
class Refused:
    """The construction cannot guarantee a violation here, so the site decides nothing."""

    reason: str


@dataclass(frozen=True)
class Candidate:
    """A contract and a placement whose named constraint is violated by construction."""

    case: memory.Case
    placement: list[dict[str, Any]]


@dataclass(frozen=True)
class Claim:
    """An optimality receipt whose stated evidence is false by construction."""

    case: memory.Case
    receipt: dict[str, Any]


@dataclass(frozen=True)
class Subject:
    """One contract under sweep, with its checked standing plan and per-arena figures."""

    case: memory.Case
    placement: list[dict[str, Any]]
    spans: dict[str, int]
    capacity: dict[str, int]


def tag(finding: str) -> str:
    """The constraint a checker finding names, which is the word before its colon."""
    head, _, _ = finding.partition(":")
    return head


def dropping(clause: str) -> Checker:
    """A deliberately weakened checker with one clause's findings removed.

    The checker is a pure findings function, so discarding every finding a clause can
    produce is exactly that clause not deciding. This exists so a sweep can be run
    against a checker already known to be weak: a sweep reporting no survivor there
    would be measuring its own operators rather than the checker.
    """
    def weakened(case: memory.Case, placement: object) -> list[str]:
        return [item for item in memory.check_placement(case, placement)
                if tag(item) != clause]
    return weakened


def _align_up(value: int, alignment: int) -> int:
    """The least multiple of `alignment` at or above `value`; this module's one spelling."""
    return (value + alignment - 1) // alignment * alignment


def _base_of(placement: list[dict[str, Any]], identifier: str) -> int:
    for row in placement:
        if row["id"] == identifier:
            return int(row["base"])
    raise memory.CaseError(f"{identifier} is absent from the placement")


def _arena_row(receipt: dict[str, Any], arena_id: str) -> dict[str, Any]:
    for row in receipt["arenas"]:
        if row["arena"] == arena_id:
            return row
    raise memory.CaseError(f"the receipt carries no row for arena {arena_id}")


def _relocate(placement: list[dict[str, Any]], identifier: str,
              base: int) -> list[dict[str, Any]]:
    return [{**row, "base": base} if row["id"] == identifier else dict(row)
            for row in placement]


def _overflow_base(span: int, capacity: int, obj: memory.Object) -> int:
    """An aligned base at or above `span` whose slot provably ends past `capacity`.

    At or above the arena's occupied span every other slot ends at or below that span,
    so this base overlaps nothing. It satisfies the declared alignment, and it is at
    least `capacity - size + 1`, so the slot's own end exceeds the capacity.
    """
    return _align_up(max(span, capacity - obj.size + 1), obj.alignment)


def _mutate_field(case: memory.Case, identifier: str, field: str,
                  value: int) -> memory.Case | Refused:
    """Rebuild the contract through its own parser, so a mutant stays a legal contract."""
    raw = {"name": case.name, "provenance": case.provenance, "mode": case.mode,
           "arenas": [asdict(arena) for arena in case.arenas],
           "objects": [{**asdict(obj), field: value} if obj.id == identifier
                       else asdict(obj) for obj in case.objects]}
    try:
        parsed = memory.parse_case(raw)
    except memory.CaseError as error:
        return Refused(f"the mutated contract is not legal: {error}")
    return parsed


def _colocate(subject: Subject, left: memory.Object,
              right: memory.Object) -> list[dict[str, Any]] | Refused:
    """Put two non-interfering objects on one extent without moving any other row.

    A pair the contract already rebinds to one declared base needs no move. Otherwise
    both rows go to the first base at or above the arena's occupied span that satisfies
    both alignments, which overlaps nothing because every other slot ends at or below
    that span. Either placement is legal while the two lifetimes stay disjoint.
    """
    if _base_of(subject.placement, left.id) == _base_of(subject.placement, right.id):
        return [dict(row) for row in subject.placement]
    stride = math.lcm(left.alignment, right.alignment)
    base = _align_up(subject.spans[left.arena], stride)
    if base + max(left.size, right.size) > subject.capacity[left.arena]:
        return Refused("no shared aligned extent above the occupied span fits the arena")
    return _relocate(_relocate(subject.placement, left.id, base), right.id, base)


def construct(name: str, subject: Subject,
              site: tuple[memory.Object, ...]) -> Candidate | Refused:
    """Build one placement or contract mutant, or say why this site admits none."""
    obj = site[0]
    if name == "overlap-collide":
        peer = site[1]
        base = _base_of(subject.placement, obj.id)
        if base % peer.alignment:
            return Refused("the peer's alignment does not divide this object's base")
        if base + peer.size > subject.capacity[peer.arena]:
            return Refused("the peer's slot does not fit at this object's base")
        return Candidate(subject.case, _relocate(subject.placement, peer.id, base))
    if name == "alignment-shift":
        if obj.alignment == 1:
            return Refused("unit alignment admits every base")
        span = subject.spans[obj.arena]
        # Two consecutive integers cannot both be multiples of an alignment above one.
        base = span + 1 if (span + 1) % obj.alignment else span + 2
        if base + obj.size > subject.capacity[obj.arena]:
            return Refused("no misaligned base above the occupied span fits the arena")
        return Candidate(subject.case, _relocate(subject.placement, obj.id, base))
    if name == "capacity-overflow":
        base = _overflow_base(subject.spans[obj.arena], subject.capacity[obj.arena], obj)
        return Candidate(subject.case, _relocate(subject.placement, obj.id, base))
    if name == "ownership-reassign":
        others = [arena.id for arena in subject.case.arenas if arena.id != obj.arena]
        if not others:
            return Refused("the contract declares one arena")
        return Candidate(subject.case,
                         [{**row, "arena": others[0]} if row["id"] == obj.id else dict(row)
                          for row in subject.placement])
    if name == "identity-duplicate":
        rows = [dict(row) for row in subject.placement]
        return Candidate(subject.case,
                         [*rows, dict(next(row for row in rows if row["id"] == obj.id))])
    if name == "identity-drop":
        return Candidate(subject.case,
                         [dict(row) for row in subject.placement if row["id"] != obj.id])
    if name not in _PAIR_SUCCESSIVE:
        raise memory.CaseError(f"unknown placement operator {name}")
    peer = site[1]
    if name in ("reuse-before-sweep", "reuse-before-authority"):
        field = "sweep_end" if name == "reuse-before-sweep" else "authority_end"
        boundary = obj.sweep_end if field == "sweep_end" else obj.authority_end
        if boundary >= obj.reuse:
            return Refused(f"the predecessor charges no extent after its {field}")
        moved = _colocate(subject, obj, peer)
        if isinstance(moved, Refused):
            return moved
        mutated = _mutate_field(subject.case, peer.id, "start", boundary)
        return mutated if isinstance(mutated, Refused) else Candidate(mutated, moved)
    shared = _colocate(subject, obj, peer)
    if isinstance(shared, Refused):
        return shared
    extended = _mutate_field(subject.case, obj.id, "reuse", peer.start + 1)
    return extended if isinstance(extended, Refused) else Candidate(extended, shared)


def construct_claim(name: str, subject: Subject, receipt: dict[str, Any],
                    spans: dict[str, int], site: str) -> Claim | Refused:
    """Build one optimality-receipt mutant, or say why this site admits none."""
    mutant = deepcopy(receipt)
    if name == "witness-refused":
        obj = next(item for item in subject.case.objects if item.id == site)
        base = _overflow_base(spans[obj.arena], subject.capacity[obj.arena], obj)
        moved = _relocate(mutant["best_placement"], obj.id, base)
        mutant["best_placement"] = moved
        mutant["placement"] = [dict(row) for row in moved]
        return Claim(subject.case, mutant)
    row = _arena_row(mutant, site)
    if name == "bound-raise-load":
        # A feasible placement's span is at least the load it charges, so a claim above
        # that span cannot be the independently computed bound.
        row["charged_load_lower_bound"] = int(row["best_span"]) + 1
        return Claim(subject.case, mutant)
    if name == "bound-lower-span":
        if spans[site] < 1:
            return Refused("the arena holds no placed slot, so no smaller span exists")
        row["best_span"] = spans[site] - 1
        return Claim(subject.case, mutant)
    if name != "certificate-argument":
        raise memory.CaseError(f"unknown certificate operator {name}")
    certificate = row["certificate"]
    if certificate["infeasible_through"] is None:
        certificate["method"] = "exhaustive"
    else:
        certificate["infeasible_through"] = int(certificate["infeasible_through"]) + 1
    return Claim(subject.case, mutant)


def subject_of(case: memory.Case) -> Subject:
    """The swept form of one contract: its checked standing plan, spans and capacities."""
    placement = memory.standing_placement(case)
    findings = memory.check_placement(case, placement)
    if findings:
        raise memory.CaseError("the standing plan is not a valid baseline: "
                               + "; ".join(findings))
    return Subject(case, placement, memory.placement_spans(case, placement),
                   {arena.id: arena.capacity for arena in case.arenas})


def sites(operator: Operator, case: memory.Case) -> list[tuple[memory.Object, ...]]:
    """Every site of this contract the operator applies to, in contract order."""
    name = operator["name"]
    if name in _PAIR_INTERFERING:
        # The model's own interference predicate, imported rather than respelled.
        return [(left, right) for left in case.objects for right in case.objects
                if left.id != right.id and left.arena == right.arena
                and memory._interferes(left, right)]
    if name in _PAIR_SUCCESSIVE:
        # A predecessor releases its extent at `reuse`, and the boundary is half-open.
        return [(left, right) for left in case.objects for right in case.objects
                if left.id != right.id and left.arena == right.arena
                and left.reuse <= right.start]
    return [(obj,) for obj in case.objects]


def _label(site: tuple[memory.Object, ...]) -> str:
    return "/".join(item.id for item in site)


def _sample[T](seed: int | str, case_name: str, operator: str, sites: list[T],
               max_sites: int) -> list[T]:
    """A reproducible subset of the applicable sites, chosen by the run's own seed."""
    if len(sites) <= max_sites:
        return sites
    rng = random.Random(f"{seed}:{case_name}:{operator}")  # noqa: S311 - reproducible site choice, no security use
    return rng.sample(sites, max_sites)


def _outcome(operator: Operator, case_name: str, site: str, verdict: str,
             findings: list[str], reason: str | None) -> Outcome:
    return {"case": case_name, "operator": operator["name"], "kind": operator["kind"],
            "site_class": operator["site_class"], "site": site,
            "targets": operator["targets"], "verdict": verdict,
            "findings": findings, "reason": reason}


def _classify(operator: Operator, findings: list[str]) -> str:
    if not findings:
        return SURVIVED
    return KILLED if operator["targets"] in {tag(item) for item in findings} else MISKILLED


def _classify_replay(operator: Operator, answer: dict[str, Any],
                     site: str) -> tuple[str, str | None]:
    findings = answer["findings"]
    if answer["status"] == "verified":
        return SURVIVED, None
    if answer["status"] != "rejected":
        return STILLBORN, f"the replay is {answer['status']}: {'; '.join(findings)}"
    expected = operator["targets"]
    if expected == RECEIPT_BOUND:
        matched = any(item.startswith(f"{site}: ") for item in findings)
    elif expected == RECEIPT_WITNESS:
        matched = any(tag(item) in CHECKER_TAGS for item in findings)
    else:
        matched = any("certificate" in item for item in findings)
    return (KILLED if matched else MISKILLED), None


def _baseline(subject: Subject,
              work_budget: int) -> tuple[dict[str, Any], dict[str, int]] | Refused:
    """The unmutated optimality receipt this contract's certificate mutants start from."""
    found = memory.solve_exact(subject.case, work_budget)
    if found["status"] != "optimal":
        return Refused(f"the bounded search is {found['status']}, so it claims no optimum")
    replay = memory.verify_optimality(subject.case, found, work_budget)
    if replay["status"] != "verified":
        return Refused(f"the unmutated receipt replays as {replay['status']}")
    return found, memory.placement_spans(subject.case, found["best_placement"])


def _placement_outcomes(subject: Subject, operator: Operator, checker: Checker,
                        seed: int | str, max_sites: int) -> list[Outcome]:
    name = subject.case.name
    applicable = sites(operator, subject.case)
    if not applicable:
        return [_outcome(operator, name, "n/a", STILLBORN, [],
                         "no applicable site in this contract")]
    results: list[Outcome] = []
    for site in _sample(seed, name, operator["name"], applicable, max_sites):
        built = construct(operator["name"], subject, site)
        if isinstance(built, Refused):
            results.append(_outcome(operator, name, _label(site), STILLBORN, [],
                                    built.reason))
            continue
        findings = checker(built.case, built.placement)
        results.append(_outcome(operator, name, _label(site),
                                _classify(operator, findings), findings, None))
    return results


def _certificate_outcomes(subject: Subject, operator: Operator,
                          baseline: tuple[dict[str, Any], dict[str, int]] | Refused,
                          seed: int | str, max_sites: int,
                          work_budget: int) -> list[Outcome]:
    name = subject.case.name
    if isinstance(baseline, Refused):
        return [_outcome(operator, name, "n/a", STILLBORN, [], baseline.reason)]
    receipt, spans = baseline
    applicable = ([arena.id for arena in subject.case.arenas]
                  if operator["name"] in _ARENA_SITES
                  else [obj.id for obj in subject.case.objects])
    results: list[Outcome] = []
    for site in _sample(seed, name, operator["name"], applicable, max_sites):
        built = construct_claim(operator["name"], subject, receipt, spans, site)
        if isinstance(built, Refused):
            results.append(_outcome(operator, name, site, STILLBORN, [], built.reason))
            continue
        answer = memory.verify_optimality(built.case, built.receipt, work_budget)
        verdict, reason = _classify_replay(operator, answer, site)
        results.append(_outcome(operator, name, site, verdict, answer["findings"], reason))
    return results


def _tally(outcomes: list[Outcome], label: str,
           key: Callable[[Outcome], str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in dict.fromkeys(key(item) for item in outcomes):
        selected = [item for item in outcomes if key(item) == value]
        rows.append({label: value,
                     **{verdict: sum(1 for item in selected if item["verdict"] == verdict)
                        for verdict in VERDICTS},
                     "mutants": sum(1 for item in selected
                                    if item["verdict"] != STILLBORN)})
    return rows


def sweep(cases: list[dict[str, Any]], *, checker: Checker = memory.check_placement,
          seed: int | str = DEFAULT_SEED, max_sites: int = DEFAULT_MAX_SITES,
          work_budget: int = DEFAULT_WORK_BUDGET,
          kinds: tuple[str, ...] = KINDS) -> dict[str, Any]:
    """Apply every operator at every sampled applicable site and classify each result.

    Baseline validity is always decided by the unweakened checker, so weakening a clause
    changes which mutants are refused and never which contracts are swept.
    """
    if max_sites < 1:
        raise memory.CaseError("max_sites must be a positive integer")
    outcomes: list[Outcome] = []
    errors: list[str] = []
    for raw in cases:
        case = memory.parse_case(raw)
        try:
            subject = subject_of(case)
        except memory.CaseError as error:
            errors.append(f"{case.name}: {error}")
            continue
        baseline: tuple[dict[str, Any], dict[str, int]] | Refused | None = None
        for operator in OPERATORS:
            if operator["kind"] not in kinds:
                continue
            if operator["kind"] != "certificate":
                outcomes.extend(_placement_outcomes(subject, operator, checker, seed,
                                                    max_sites))
                continue
            if baseline is None:
                baseline = _baseline(subject, work_budget)
            outcomes.extend(_certificate_outcomes(subject, operator, baseline, seed,
                                                  max_sites, work_budget))
    survivors = [item for item in outcomes if item["verdict"] == SURVIVED]
    miskills = [item for item in outcomes if item["verdict"] == MISKILLED]
    if survivors:
        errors.append(f"{len(survivors)} constructed violations were accepted")
    stillborn: dict[tuple[str, str], int] = {}
    for item in outcomes:
        if item["verdict"] == STILLBORN and item["reason"] is not None:
            key = (item["operator"], item["reason"])
            stillborn[key] = stillborn.get(key, 0) + 1
    return {
        "settings": {"seed": seed, "max_sites_per_operator": max_sites,
                     "work_budget": work_budget, "kinds": list(kinds),
                     "cases": [item["name"] for item in cases]},
        "totals": {verdict: sum(1 for item in outcomes if item["verdict"] == verdict)
                   for verdict in VERDICTS},
        "by_operator": _tally(outcomes, "operator", lambda item: item["operator"]),
        "by_site_class": _tally(outcomes, "site_class", lambda item: item["site_class"]),
        "survivors": survivors, "miskills": miskills,
        "stillborn_reasons": [{"operator": operator, "reason": reason, "count": count}
                              for (operator, reason), count in sorted(stillborn.items())],
        "outcomes": outcomes, "errors": errors,
    }


def report(source_revision: str = "unspecified") -> dict[str, Any]:
    """Sweep the declared witnesses and one generated family, with a weakened control.

    The control removes the alignment clause and requires that exactly the operator
    targeting that clause survives. Without it, a sweep reporting no survivor would be
    consistent with a checker that decides nothing.
    """
    cases = [*witnesses.corpus(source_revision),
             *scale.corpus(source_revision, sizes=GENERATED_SIZES)]
    complete = sweep(cases)
    control = sweep(cases, checker=dropping("alignment"), kinds=("placement", "case"))
    observed = sorted({item["operator"] for item in control["survivors"]})
    errors = [*complete["errors"]]
    if observed != ["alignment-shift"]:
        errors.append("removing the alignment clause did not isolate its own operator: "
                      f"{observed}")
    certificate_names = {item["name"] for item in OPERATORS
                         if item["kind"] == "certificate"}
    feasibility = sum(row["mutants"] for row in complete["by_operator"]
                      if row["operator"] not in certificate_names)
    optimality = sum(row["mutants"] for row in complete["by_operator"]
                     if row["operator"] in certificate_names)
    for key in ("by_operator", "by_site_class", "outcomes", "errors"):
        control.pop(key)
    complete.pop("outcomes")
    return {
        "schema": SCHEMA, "generator": GENERATOR, "source_revision": source_revision,
        "scope": "constructed violations of one finite research model; no admission "
                 "checker, CHERI representability, island or bank constraint is tested",
        "operators": [dict(operator) for operator in OPERATORS],
        "verdicts": {
            KILLED: "refused by a finding that names the targeted constraint",
            MISKILLED: "refused, but only by an unrelated clause; the error typing is "
                       "imprecise at that site",
            SURVIVED: "accepted; the finding, because the violation was constructed",
            STILLBORN: "no mutant was emitted, or the replay reached no verdict, so the "
                       "site decides nothing about the checker",
        },
        "certificates": {
            "feasibility": "check_placement refuses one candidate against an unchanged "
                           "contract and decides nothing about optimality",
            "optimality": "verify_optimality additionally replays the bound argument, so "
                          "a refused witness and a false bound are separate findings",
            "feasibility_mutants": feasibility, "optimality_mutants": optimality,
        },
        "sweep": complete,
        "control": {"clause_removed": "alignment",
                    "expected_survivor_operators": ["alignment-shift"],
                    "observed_survivor_operators": observed,
                    "survivors_are_expected_here": True, "weakened": control},
        "open_obligations": [
            "operators for constraints outside the declared model: CHERI bounds "
            "representability, island and bank assignment, admission",
            "a generated family large enough to exercise the bounded search rather than "
            "the placement checker alone",
            "an independent oracle for the replay verifier itself, whose clauses these "
            "operators reach only through its refusals",
        ],
        "errors": errors,
    }
