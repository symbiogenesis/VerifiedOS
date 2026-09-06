#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export the memory plan's placement problem, check its export, and search it.

    tools/run.py placement export            # writes tools/generated/memory-plan.json
    tools/run.py placement check             # re-emits and compares, byte for byte
    tools/run.py placement admit [--plan P]  # the exact check over one plan of the .v
    tools/run.py placement search            # enumerate, admit exactly, and report

Q5's first landing over M1.9's plan. The problem is read out of
[proofs/MemoryPlan.v](../../../proofs/MemoryPlan.v) by [vos/memplan.py](../memplan.py),
which is the one reader and the one exact check; this module is the command surface
over it and decides nothing of its own.

**What `search` claims and what it does not.** It enumerates every candidate the
declared predicate admits, per island, prunes a prefix only where the `.v`'s own
pairwise check refuses it, and hands every leaf to the exact check as a whole plan.
The report states the candidate count with its predicate, the leaf and feasible
counts, and the best admitted placement per island against the standing one, on span
used, unused reservation and padding, with the worst-case timing shown on both sides
because the class assignment is the register's and a base search cannot move it. The
status is *complete over the declared set* and never optimality outside it; a run
cut short by `--max-leaves` says so and is not infeasibility. No admitted-workload
comparison is taken: the plan's figures are witness values carrying no composition
claim, and the roster that comparison wants is owed elsewhere (Q1, R-18-004d).

**What the validator is.** Development hygiene, as the item's own text puts it: the
trusted admission checks keep the proof status they owe in the `.v`, and nothing this
command prints is evidence about the machine.
"""

import argparse
from pathlib import Path

from vos import corpus as corpus_mod
from vos import memplan
from vos.cli import Table, dispatch

# The rules a reader of the report is pointed at, by name and never by a figure
# copied out of them: the register entries the checks decide for are in the export.
DOCUMENT = "docs/placement-search.md"


def _emit(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        src = memplan.read(root)
        text = memplan.render(memplan.export(src))
    except memplan.PlanError as exc:
        print(f"FAIL: {exc}")
        return 1
    path = root / memplan.ARTIFACT
    path.write_text(text, encoding="utf-8", newline="")
    lists = len(src.nat_lists) + len(src.bool_lists) + len(src.kind_lists)
    print(f"emitted {memplan.ARTIFACT} from {memplan.SOURCE} at md5 {src.md5}: "
          f"{src.literals['region_count']} regions of `{memplan.STANDING}`, "
          f"{lists} typed lists, {len(src.literals)} literal fields and "
          f"{len(src.plans)} plans read; {len(memplan.ABSENT)} fields declared absent "
          f"({len(text.splitlines())} lines)")
    return 0


def _check(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        text = memplan.emit(root)
    except memplan.PlanError as exc:
        print(f"FAIL: {exc}")
        return 1
    path = root / memplan.ARTIFACT
    if not path.is_file():
        print(f"FAIL: {memplan.ARTIFACT} is not in the working tree; "
              f"`{memplan.REPAIR}` writes it")
        return 1
    on_disk = path.read_text(encoding="utf-8", newline="")
    if on_disk != text:
        want, got = text.splitlines(), on_disk.splitlines()
        where = next((i for i, (a, b) in enumerate(zip(want, got, strict=False))
                      if a != b), min(len(want), len(got)))
        print(f"FAIL: {memplan.ARTIFACT} is not what `{memplan.REPAIR}` writes; the "
              f"first difference is at line {where + 1}")
        return 1
    print(f"ok: {memplan.ARTIFACT} is byte-identical to what `{memplan.REPAIR}` "
          f"writes from {memplan.SOURCE} ({len(text.encode('utf-8'))} bytes)")
    return 0


def _admit(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        src = memplan.read(root)
        plan = memplan.plan_of(src, args.plan)
    except memplan.PlanError as exc:
        print(f"FAIL: {exc}")
        return 1
    refused = memplan.refused_by(plan)
    print(f"{plan.name}: {plan.region_count} regions over "
          f"{len(plan.island_ids())} island(s)")
    for check, entry in memplan.CONSTRAINTS:
        if check == "slot_indices_held":
            verdict = "n/a here, the frame's slot count being CyclicExecutive.v's"
        elif check == "pool_fits":
            verdict = "n/a here, the population being an argument"
        else:
            verdict = "refused" if check in refused else "admitted"
        print(f"  {check:24s} {entry:10s} {verdict}")
    print(f"  worst-case timing: {memplan.worst_case_timing(plan)} over "
          f"{plan.region_count} regions, second class "
          f"{'no faster' if memplan.second_class_is_no_faster(plan) else 'faster'} "
          f"than the first")
    print(f"verdict: {'admitted' if not refused else 'refused by ' + ', '.join(refused)}"
          f"; this is the Python port and not the proof, which stays with "
          f"{memplan.SOURCE}")
    return 0


def _bases(plan: memplan.Plan, regions: tuple[int, ...]) -> str:
    return ", ".join(f"r{r}@{plan.base_of(r)}" for r in regions)


def _report(plan: memplan.Plan, src: memplan.Source, max_leaves: int | None) -> int:
    print(f"=== placement search over `{plan.name}` of {memplan.SOURCE} "
          f"(md5 {src.md5}) ===")
    print(f"regions: {plan.region_count} over {len(plan.island_ids())} islands; "
          f"first_fetch {plan.first_fetch}, second_fetch {plan.second_fetch}, both "
          f"witness values, and the plan carries no other cost input")
    print(f"candidate set: {memplan.PREDICATE}")
    print("admission: every leaf is the whole plan re-checked by the exact port of "
          "the .v's containment_ok, colouring_ok, slot_bases_quantized, "
          "slot_lengths_quantized, plan_ok and places_ok; a pruned prefix is one the "
          ".v's own pairwise colouring test refuses")
    print("degrees of freedom not taken: islands, classes, kinds, lengths, live "
          "ranges, fetch counts and charged slots are the plan's fields and stay "
          "where the .v declares them; no region crosses an island")
    print()

    shared = memplan.plan_of(src, "shared_slot_plan") if "shared_slot_plan" in src.plans \
        else None
    complete = True
    for found in memplan.search(plan, max_leaves):
        i = found.island
        print(f"island {i}: base {plan.island_base(i)}, span {plan.island_span(i)}, "
              f"regions {list(found.regions)}, quantum {found.quantum}, "
              f"steps {list(found.steps)}")
        print(f"  candidates: {found.grid} (predicate: the product of "
              f"{list(found.counts)} bases per region); the finer grid at every "
              f"multiple of each region's granule alone would be {found.granule_grid} "
              f"and is not enumerated")
        print(f"  decided: {found.pruned} pruned at a refused pair, {found.leaves} "
              f"leaves re-checked whole, {found.feasible} admitted"
              f"{', TRUNCATED at --max-leaves' if found.truncated else ''}")
        complete = complete and not found.truncated
        s = found.standing
        print(f"  standing: {_bases(plan, found.regions)}; footprint {s.footprint}, "
              f"span used {s.span_used}, unused reservation {s.unused_reservation}, "
              f"padding {s.padding}"
              f"{'' if found.standing_admitted else ' (REFUSED by the exact check)'}")
        if found.best is None or found.best.score is None:
            print("  best: none admitted")
            continue
        b = found.best.score
        print(f"  best: {', '.join(f'r{r}@{base}' for r, base in found.best.bases)}; "
              f"footprint {b.footprint}, span used {b.span_used}, unused reservation "
              f"{b.unused_reservation}, padding {b.padding}")
        moved = b.key() < s.key()
        print(f"  verdict: {'an admitted assignment tighter than the standing one on ' + ('span used' if b.span_used < s.span_used else 'padding') if moved else 'the standing assignment is not bettered inside the set'}"
              f"; footprint unmoved at {b.footprint} because it is a function of live "
              f"ranges and lengths and not of bases")
        if shared is not None:
            shared_bases = tuple((r, shared.base_of(r)) for r in found.regions)
            same = shared_bases == found.best.bases
            print(f"  shared_slot_plan: {'is' if same else 'is not'} the best found "
                  f"({_bases(shared, found.regions)})")
    print()
    timing = memplan.worst_case_timing(plan)
    print(f"worst-case timing: the sum of placement deltas is {timing} on both sides, "
          f"class_of being the register's placement and a base search moving no "
          f"class, fetch count or slot")
    print(f"status: {'complete enumeration over the declared set' if complete else 'INCOMPLETE, cut short by --max-leaves; not infeasibility'}"
          f"; not an optimality claim outside that set; admitted workload: n/a, no "
          f"composed roster (R-18-004d unauthored, Q1 open)")
    print("residuals: fields the plan does not carry, "
          + "; ".join(f"{name}: {why}" for name, why in memplan.ABSENT.items()))
    print("residuals: cost inputs, none read and none rounded; the two fetch "
          "constants above are witness values and the bank-count contract's "
          "coefficients are pending where that document states them")
    print("verdict: any gain above is over witness values that carry no composition "
          "claim and credits nothing to the product; the validator is development "
          "hygiene and the proof status stays with the .v; see "
          f"{DOCUMENT} for the contract")
    return 0


def _search(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        src = memplan.read(root)
        plan = memplan.plan_of(src, args.plan)
        return _report(plan, src, args.max_leaves)
    except memplan.PlanError as exc:
        print(f"FAIL: {exc}")
        return 1


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name in ("admit", "search"):
        sub.add_argument("--plan", default=memplan.STANDING, metavar="NAME",
                         help=f"which plan of the .v to read (default {memplan.STANDING})")
    if name == "search":
        sub.add_argument("--max-leaves", type=int, default=None, metavar="N",
                         help="stop an island's walk after N leaves and say so")


TABLE: Table = {
    "export": (_emit, "write the placement problem as generated data from the .v"),
    "check": (_check, "re-emit and compare, byte for byte"),
    "admit": (_admit, "the exact check over one plan of the .v, verdict per check"),
    "search": (_search, "enumerate the declared candidate set and report"),
}


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py placement")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
