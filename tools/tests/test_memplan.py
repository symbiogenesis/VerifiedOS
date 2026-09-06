# SPDX-License-Identifier: Apache-2.0
"""The memory plan's reader, its exact check and its enumerator, held to the proof file.

K-88 decides that the tracked export is the bytes the reader writes, so what is worth
pinning here is what a byte comparison cannot see, in four claims.

**The reader reads the file and refuses a shape it does not read.** A regex over
Gallina that stopped matching would yield an empty roster and a green report about
nothing, so the first cases hand the reader the live file and hold the roster, the
literals and the lists to what the `.v`'s own `the_demo_plan_declares` states, and then
hand it shapes with a list missing, a chain malformed and a kind unknown and require
`PlanError` each time.

**The port agrees with the proof file on every plan the file decides.** The `.v` ships
one admitted plan and fifteen variants each moving one declared quantity, and states in
`Example` form which check refuses which. Those verdicts are the oracle here: a port
that drifted from the file would admit a plan the file refutes or refuse the one it
admits. The granule port is held separately, against R-15-007c's own figures the file
states at `the_two_regimes_meet_at_the_threshold` and against every declared granule
count of the demo plan.

**The enumerator is complete over what it declares.** On a two-region toy the grid is
counted by hand and every point is decided, pruned or admitted, with the standing point
among them.

**The export is the tracked artifact.** The one case over the real tree, as
`test_socmap.py` keeps one: the emitter reads the live file and the bytes it writes are
the bytes tracked, or the repair command is named.
"""

from tests.harness import Case, ensure
from vos import corpus as corpus_mod
from vos import memplan

# R-15-007c's two regimes as the `.v` states them at
# `the_two_regimes_meet_at_the_threshold`: byte-exact to 128, then the coarsest power
# of two whose 2^6 multiple fits.
_GRANULES = ((1, 1), (128, 1), (129, 2), (192, 2), (384, 4), (512, 8), (1024, 16))

# Which check refuses which variant, as the `.v`'s own Examples decide it. A plan
# absent here is admitted by every check the search can move.
_REFUSALS = {
    "island_escaping_plan": ["containment_ok"],
    "island_underflow_plan": ["containment_ok"],
    "overlapping_live_plan": ["colouring_ok"],
    "unquantized_plan": ["slot_bases_quantized"],
    "off_by_one_plan": ["slot_bases_quantized"],
    "odd_base_plan": ["slot_bases_quantized"],
    "unquantized_length_plan": ["slot_lengths_quantized"],
}

# The two-region toy: one island of 64 bytes, a 16-byte region and a 32-byte region
# whose live ranges overlap, the first at the island's base and the second right after
# it in the standing plan, so that the quantum reads as sixteen and the enumerated grid
# is every sixteenth byte while the finer grid at every byte is counted beside it.
_TOY = """
Inductive RegionKind : Type :=
| ScalarWorkingSet
| BulkByVolume.

Definition placed_by_name (k : RegionKind) : option MemClass :=
  match k with
  | ScalarWorkingSet => Some FirstClass
  | BulkByVolume => Some SecondClass
  end.

Definition criterion_class (critical : bool) : MemClass :=
  if critical then FirstClass else SecondClass.

Definition toy_kinds : list RegionKind := cons ScalarWorkingSet (cons BulkByVolume nil).
Definition toy_critical : list bool := cons false (cons false nil).
Definition toy_lengths : list nat := cons 16 (cons 32 nil).
Definition toy_bases : list nat := cons 0 (cons 16 nil).
Definition toy_base_granules : list nat := cons 0 (cons 16 nil).
Definition toy_length_granules : list nat := cons 16 (cons 32 nil).
Definition toy_islands : list nat := cons 0 (cons 0 nil).
Definition toy_island_bases : list nat := cons 0 nil.
Definition toy_island_spans : list nat := cons 64 nil.
Definition toy_live_starts : list nat := cons 0 (cons 0 nil).
Definition toy_live_ends : list nat := cons 10 (cons 10 nil).
Definition toy_fetch_counts : list nat := cons 0 (cons 3 nil).
Definition toy_slots : list nat := cons 0 (cons 0 nil).
Definition toy_placed : list nat := cons 0 (cons 1 nil).
Definition toy_origin_regions : list nat := cons 1 nil.

Definition toy_kind_of (r : nat) : RegionKind := at_list toy_kinds r BulkByVolume.

Definition toy_cycle_critical (r : nat) : bool := at_list toy_critical r false.

Definition toy_class_of (r : nat) : MemClass :=
  match placed_by_name (toy_kind_of r) with
  | Some c => c
  | None => criterion_class (toy_cycle_critical r)
  end.

Definition build_plan (lengths bases bgran lgran slots : list nat)
                      (second : nat) : Plan := {|
  region_count := 2;
  kind_of := toy_kind_of;
  cycle_critical := toy_cycle_critical;
  class_of := toy_class_of;
  base_of := fun r => at_list bases r 0;
  length_of := fun r => at_list lengths r 0;
  live_from := fun r => at_list toy_live_starts r 0;
  live_to := fun r => at_list toy_live_ends r 0;
  base_granules := fun r => at_list bgran r 0;
  length_granules_of := fun r => at_list lgran r 0;
  island_of := fun r => at_list toy_islands r 0;
  island_base := fun i => at_list toy_island_bases i 0;
  island_span := fun i => at_list toy_island_spans i 0;
  first_fetch := 10;
  second_fetch := second;
  fetch_count := fun r => at_list toy_fetch_counts r 0;
  slot_of := fun r => at_list slots r 0;
  placed := toy_placed;
  origin_regions := toy_origin_regions;
  fixed_first_class := 8;
  first_budget := 64
|}.

Definition demo_plan : Plan :=
  build_plan toy_lengths toy_bases toy_base_granules toy_length_granules
             toy_slots 12.
"""


def _live() -> memplan.Source:
    return memplan.read(corpus_mod.find_root())


def _refused(text: str, why: str) -> None:
    try:
        memplan.parse(text)
    except memplan.PlanError:
        return
    raise AssertionError(why)


def _the_reader_reads_the_live_file() -> None:
    src = _live()
    plan = memplan.plan_of(src, memplan.STANDING)
    # `the_demo_plan_declares`, MemoryPlan.v
    ensure(plan.region_count == 8 and plan.first_fetch == 10 and plan.second_fetch == 15
           and plan.fixed_first_class == 1024 and plan.first_budget == 2048,
           f"the demo plan's declared literals are not what the .v states: {plan}")
    ensure(memplan.plan_of(src, "over_margin_plan").second_fetch == 16,
           "over_margin_plan moves the second class's constant by one and nothing else")
    ensure(len(src.plans) >= 16,
           f"the .v builds sixteen plans from build_plan and the reader found "
           f"{len(src.plans)}")
    ensure(set(memplan.LITERAL_FIELDS) == set(src.literals),
           f"every literal field of build_plan is read and no other: {src.literals}")
    ensure(len(plan.island_ids()) == 2, f"two islands: {plan.island_ids()}")
    ensure(all(len(t) == plan.region_count for t in (
        plan.kinds, plan.critical, plan.lengths, plan.bases, plan.live_starts,
        plan.live_ends, plan.base_granules, plan.length_granules, plan.islands,
        plan.fetch_counts, plan.slots)),
        "every per-region list of the demo plan carries exactly the roster")


def _a_shape_the_reader_does_not_read_is_refused() -> None:
    ensure(memplan.plan_of(memplan.parse(_TOY), "demo_plan").region_count == 2,
           "the toy must parse before its mutants can be refused")
    _refused(_TOY.replace("Definition toy_lengths : list nat := cons 16 (cons 32 nil).",
                          ""),
             "a list build_plan reads was absent and the reader did not refuse")
    _refused(_TOY.replace("cons 16 (cons 32 nil)", "cons 16 (cons 32)"),
             "a chain not ending in nil was read rather than refused")
    _refused(_TOY.replace("cons ScalarWorkingSet (cons BulkByVolume nil)",
                          "cons ScalarWorkingSet (cons Framebuffers nil)"),
             "a kind no constructor spells was read rather than refused")
    _refused(_TOY.replace("region_count := 2;", ""),
             "build_plan stating no region_count was read rather than refused")
    _refused(_TOY.replace("| BulkByVolume => Some SecondClass\n", ""),
             "placed_by_name deciding fewer kinds than the inductive carries was read")
    _refused(_TOY.replace("Definition demo_plan : Plan :=", "Definition other : Plan :="),
             "the standing plan absent was read rather than refused")
    # `app` of two lists is a shape the .v writes and the reader leaves unread, which
    # is a refusal only where build_plan reads such a list
    src = memplan.parse(_TOY + "\nDefinition joined : list nat := app toy_lengths toy_bases.\n")
    ensure(src.unread == ("joined",), f"an `app` list is named unread: {src.unread}")


def _the_granule_port_is_the_entry_s_own_figures() -> None:
    for length, expected in _GRANULES:
        got = memplan.representable_granule(length)
        ensure(got == expected,
               f"representable_granule {length} = {got}, the .v states {expected}")
    plan = memplan.plan_of(_live(), memplan.STANDING)
    for r in plan.regions():
        g = memplan.granule_of(plan, r)
        ensure(g * plan.base_granules_of(r) == plan.base_of(r),
               f"region {r}: granule {g} times the declared base count is not the base")
        ensure(g * plan.length_granules_of(r) == plan.length_of(r),
               f"region {r}: granule {g} times the declared length count is not the "
               f"length")


def _the_port_agrees_with_the_proof_file_on_every_plan() -> None:
    src = _live()
    for name in src.plans:
        plan = memplan.plan_of(src, name)
        got = memplan.refused_by(plan)
        ensure(got == _REFUSALS.get(name, []),
               f"{name}: the port refuses {got} where the .v decides "
               f"{_REFUSALS.get(name, [])}")
    shared = memplan.plan_of(src, "shared_slot_plan")
    overlapping = memplan.plan_of(src, "overlapping_live_plan")
    # reading 7 and the inversion gap f reports: the literal reading refuses the shared
    # slot and admits the overlapping one, and the reading taken answers the other way
    ensure(not memplan.literal_colouring_ok(shared)
           and memplan.literal_colouring_ok(overlapping),
           "the literal reading must refuse shared_slot_plan and admit "
           "overlapping_live_plan")
    ensure(not memplan.live_overlap(shared, 2, 4)
           and not memplan.slots_disjoint(shared, 2, 4),
           "regions 2 and 4 of shared_slot_plan share a slot over disjoint live ranges")
    ensure(not memplan.strict_colouring_ok(shared),
           "the strict reading refuses the shared slot outright")
    escaping = memplan.plan_of(src, "slot_escaping_plan")
    demo = memplan.plan_of(src, memplan.STANDING)
    # `the_demo_plan_charges_only_slots_the_frames_hold`: the charged rung has 3 slots
    ensure(memplan.slot_indices_held(demo, 3) and not memplan.slot_indices_held(escaping, 3),
           "slot_escaping_plan charges a slot index a three-slot frame does not carry")
    fast = memplan.plan_of(src, "fast_second_plan")
    ensure(not memplan.second_class_is_no_faster(fast)
           and memplan.worst_case_timing(fast) == 0,
           "a faster second class breaks the side condition and the delta truncates")
    ensure(memplan.worst_case_timing(demo) == 5
           and memplan.worst_case_timing(memplan.plan_of(src, "over_margin_plan")) == 6
           and memplan.worst_case_timing(memplan.plan_of(src, "flat_plan")) == 0,
           "the delta ladder reads the second class's constant and the fetch counts")
    # the origin roster is regions 1 and 2, of which region 2 is first-class at 32
    # bytes, so 1024 + 32 n fits a 2048 budget up to n = 32 and not at 33
    ensure(memplan.member_first_class_cost(demo) == 32
           and memplan.pool_fits(demo, 32) and not memplan.pool_fits(demo, 33),
           "pool_fits reads the origin roster's first-class bytes against the budget")


def _the_enumerator_is_complete_over_the_toy() -> None:
    plan = memplan.plan_of(memplan.parse(_TOY), "demo_plan")
    found = memplan.enumerate_island(plan, 0)
    # the standing bases' gcd is 16 and both granules are 1, so the step is 16 on both
    # and a 16-byte region has 4 bases in 64 bytes where a 32-byte one has 3; at every
    # byte, the finer grid the report counts and never walks, they have 49 and 33
    ensure(found.quantum == 16 and found.steps == (16, 16), f"the toy's grid: {found}")
    ensure(found.counts == (4, 3) and found.grid == 12, f"the toy's counts: {found}")
    ensure(found.granule_grid == 49 * 33, f"the finer grid is counted: {found}")
    ensure(found.pruned + found.leaves == found.grid,
           f"every grid point is decided, pruned or reached: {found}")
    # the two live ranges overlap, so the slots must be disjoint: the 16-byte region at
    # 0 leaves the 32-byte one 16 or 32, at 16 leaves it 32, at 32 leaves it 0, at 48
    # leaves it 0 and 16, which is six admitted points
    ensure(found.feasible == 6 and found.leaves == 6, f"six admitted: {found}")
    ensure(found.standing_admitted, "the standing toy plan is admitted")
    ensure(found.best is not None and found.best.score is not None
           and found.best.score.span_used == 48 and found.best.score.padding == 0,
           f"the best packs the two regions to 48 bytes: {found.best}")
    ensure(found.standing.span_used == 48 and found.standing.footprint == 48,
           f"the standing toy plan already packs tight: {found.standing}")
    capped = memplan.enumerate_island(plan, 0, max_leaves=2)
    ensure(capped.truncated and capped.leaves == 2,
           f"a capped walk says it was cut short: {capped}")


def _the_score_reads_what_a_base_can_move() -> None:
    plan = memplan.plan_of(_live(), memplan.STANDING)
    first, second = plan.island_ids()
    s0, s1 = memplan.score(plan, first), memplan.score(plan, second)
    # island 0: slots 0..64, 64..96, 96..224, 224..416 with regions 2 and 4 never live
    # together, so the peak is 64 + 128 + 192; island 1: 1888 bytes end 16 short of the
    # island's top with a 16-byte gap before the last slot
    ensure((s0.footprint, s0.span_used, s0.unused_reservation, s0.padding)
           == (384, 416, 32, 0), f"island {first}: {s0}")
    ensure((s1.footprint, s1.span_used, s1.unused_reservation, s1.padding)
           == (1888, 1904, 16, 16), f"island {second}: {s1}")
    moved = memplan.with_bases(plan, {6: 192})
    ensure(memplan.score(moved, first).span_used == 384
           and memplan.footprint(moved, tuple(r for r in moved.regions()
                                              if moved.island_of(r) == first)) == 384,
           "moving a base moves the span and never the footprint")
    ensure(memplan.base_is_quantized(moved, 6),
           "a moved base states its granule count and the check multiplies it back")
    odd = memplan.with_bases(plan, {6: 225})
    ensure(not memplan.base_is_quantized(odd, 6),
           "a base off its granule is refused by the check and not rounded by the move")


def _the_export_is_the_tracked_artifact() -> None:
    root = corpus_mod.find_root()
    text = memplan.emit(root)
    ensure('"standing": "demo_plan"' in text and '"lists_unread"' in text,
           "the export names its standing plan and what it left unread")
    ensure(text == (root / memplan.ARTIFACT).read_text(encoding="utf-8", newline=""),
           f"the tracked {memplan.ARTIFACT} is not what this emitter writes; "
           f"regenerate it with `{memplan.REPAIR}`")
    ensure("\r" not in text and text.endswith("\n"), "LF throughout and one at the end")


def cases() -> list[Case]:
    return [
        Case("the-reader-reads-the-live-file", _the_reader_reads_the_live_file),
        Case("a-shape-the-reader-does-not-read-is-refused",
             _a_shape_the_reader_does_not_read_is_refused),
        Case("the-granule-port-is-the-entrys-own-figures",
             _the_granule_port_is_the_entry_s_own_figures),
        Case("the-port-agrees-with-the-proof-file-on-every-plan",
             _the_port_agrees_with_the_proof_file_on_every_plan),
        Case("the-enumerator-is-complete-over-the-toy",
             _the_enumerator_is_complete_over_the_toy),
        Case("the-score-reads-what-a-base-can-move", _the_score_reads_what_a_base_can_move),
        Case("the-export-is-the-tracked-artifact", _the_export_is_the_tracked_artifact),
    ]
