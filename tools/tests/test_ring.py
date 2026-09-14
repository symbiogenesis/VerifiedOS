# SPDX-License-Identifier: Apache-2.0
"""The ring emitter's two owners, and K-89's fail-closed reading of them.

`vos/cli/ring.py` is the only tool in this directory whose output a rule holds byte
for byte, so what is worth pinning here is not the bytes, which K-89 already decides,
but the four claims the emitter makes about *where they came from*.

The first is that the states the artifact carries are read out of the register's own
sentences rather than off positions in its chain: a figure computed as an ordinal
difference is true of today's register and stays true of one it no longer describes,
which is this repository's *computation that encodes its own answer*. The first two
cases move a state and require the figure to move with it.

The second is that an owner the emitter cannot read is refused rather than
mis-emitted, at each of the shapes `owned()` and `declaration()` name. A world's DMA
declaration is part of that surface: it is refused where it disagrees with the world
it sits in rather than emitted into a campaign that then decides nothing.

The third is that each world takes a scope of its own and states the whole campaign at
its own constants, so a second world is a second instantiation and never a second
generator.

The fourth is K-89's own: a generator that raises is that rule's finding and never that
rule's crash. `checks/ring.py` catches the emitter's refusal and every other exception
alike, and a test injects an unexpected emitter failure to exercise that last arm.
"""

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos.checks import Context
from vos.checks import ring as rule
from vos.cli import ring
from vos.jsonc import Json
from vos.register import Register, read_artifacts
from vos.report import Reporter

# The lifecycle chain the register states, and the same chain with one state inserted
# between the two ends of the malformed step. Every skip case below is that pair.
_CHAIN = "Free → Writing → Submitted → Accepted → Terminal → Reclaimed"
_LONGER = "Free → Writing → Submitted → Accepted → Failed → Terminal → Reclaimed"

_ANSWERS = "`cancelled`, `too_late` and `not_live`"


def _register(chain: str = _CHAIN, malformed: str = "Submitted", to: str = "Terminal",
              unstarted: str = "Submitted", cancels: str = _ANSWERS) -> Register:
    """A register carrying exactly the four entries `owned()` reads."""
    return Register(body={
        ring.STATUS_ENTRY: "a status from the closed common set (`ok`, `refused`, "
                           "`invalid`, `cancelled`)",
        ring.LIFECYCLE_ENTRY: f"the monotone lifecycle {chain}: a malformed request "
                              f"moves from {malformed} directly to {to} without "
                              f"acquiring device authority",
        ring.FULL_RING_ENTRY: "submission against a full request ring has the sole "
                              "typed result `would_block`",
        ring.CANCEL_ENTRY: f"a target still {unstarted} completes cancelled unstarted; "
                           f"the answers are {cancels}",
    })


def _declaration() -> dict[str, Any]:
    """The tracked declaration, so the shape cases mutate the real one."""
    root = corpus_mod.find_root()
    text = (root / ring.DECLARATION).read_text(encoding="utf-8")
    parsed: dict[str, Any] = json.loads(text)
    return parsed


def _dma_world(base: dict[str, Any]) -> dict[str, Any]:
    """The first world of `base` that declares DMA, which the coherence cases mutate."""
    for world in base["worlds"]:
        if world["dma"] is not None:
            return world
    raise AssertionError("the tracked declaration carries no world declaring DMA")


def _refused(fn: Callable[[], object], why: str) -> None:
    """`fn` must raise the emitter's own refusal and not anything else."""
    try:
        fn()
    except ring.RingError:
        return
    raise AssertionError(why)


def _a_state_inserted_moves_the_skip() -> None:
    # The defect this case exists for: `states.index(states[4]) - states.index(states[2])`
    # is 4 - 2 for any chain of distinct states, so it answers 2 whatever the register
    # says. With a state inserted before the terminal one, the true skip is 3.
    short = ring.owned(_register())
    ensure(ring._skip(short) == 2,
           f"the register's own chain gives a skip of 2, got {ring._skip(short)}")
    longer = ring.owned(_register(chain=_LONGER))
    ensure(ring._skip(longer) == 3,
           f"a state inserted between the two the entry names must move the skip to "
           f"3, got {ring._skip(longer)}")


def _the_named_states_are_read_not_counted() -> None:
    own = ring.owned(_register(chain=_LONGER))
    ensure(own.malformed_from == "Submitted" and own.malformed_to == "Terminal",
           f"the step's ends read back as {own.malformed_from} -> {own.malformed_to}, "
           f"where the entry's own sentence names Submitted and Terminal")
    ensure(ring._live(own) == "Accepted",
           f"the live-and-started state is the successor of the state the cancellation "
           f"entry names, got {ring._live(own)}")
    moved = ring.owned(_register(chain=_LONGER, unstarted="Accepted"))
    ensure(ring._live(moved) == "Failed",
           f"moving the state that entry names must move the successor, got "
           f"{ring._live(moved)}")


def _owned_fails_closed_on_each_shape() -> None:
    shapes = {
        "no arrow chain": _register(chain="Free, Writing, Submitted"),
        "no malformed step": _register(malformed="", to=""),
        "a step naming a state off the chain": _register(malformed="Drafting"),
        "a step that skips nothing": _register(malformed="Accepted", to="Terminal"),
        "two cancellation answers": _register(cancels="`cancelled` and `not_live`"),
        "no entries at all": Register(body={}),
    }
    for why, reg in shapes.items():
        _refused(lambda held=reg: ring.owned(held),
                 f"owned() accepted a register with {why}")


def _declaration_names_every_key_the_emitter_reads() -> None:
    # The gap this case closes: `label_levels` was read at emit time and named by no
    # guard, so a declaration without it raised KeyError out of the checker instead of
    # being refused. Each key the emitter reads is dropped in turn, at each of the three
    # levels the declaration now has.
    base = _declaration()
    with sandbox_tree({ring.DECLARATION: json.dumps(base)}) as root:
        path = root / ring.DECLARATION
        for key in ring.DECL_KEYS:
            path.write_text(json.dumps({k: v for k, v in base.items() if k != key}),
                            encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted a declaration with no `{key}`")
        for key in ring.WORLD_KEYS:
            short = dict(base)
            short["worlds"] = [{k: v for k, v in world.items() if k != key}
                               for world in base["worlds"]]
            path.write_text(json.dumps(short), encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted a world with no `{key}`")
        for key in ring.ENCODING_KEYS:
            short = json.loads(json.dumps(base))
            for world in short["worlds"]:
                world["encoding"] = {k: v for k, v in world["encoding"].items()
                                     if k != key}
            path.write_text(json.dumps(short), encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted a declaration with no encoding `{key}`")
        for key in ring.OP_KEYS:
            short = json.loads(json.dumps(base))
            for world in short["worlds"]:
                world["operations"] = [{k: v for k, v in op.items() if k != key}
                                       for op in world["operations"]]
            path.write_text(json.dumps(short), encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted an operation with no `{key}`")
        for key in ring.DMA_KEYS:
            short = json.loads(json.dumps(base))
            world = _dma_world(short)
            world["dma"] = {k: v for k, v in world["dma"].items() if k != key}
            path.write_text(json.dumps(short), encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted a DMA declaration with no `{key}`")
        for key in ring.OP_DMA_KEYS:
            short = json.loads(json.dumps(base))
            world = _dma_world(short)
            world["operations"] = [{**op, "dma": {k: v for k, v in op["dma"].items()
                                                  if k != key}}
                                   for op in world["operations"]]
            path.write_text(json.dumps(short), encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted an operation DMA record with no `{key}`")
        path.write_text("{ not json", encoding="utf-8")
        _refused(lambda: ring.declaration(root),
                 "declaration() accepted a file that is not JSON")


def _the_rule_reports_rather_than_crashes() -> None:
    # The schema now refuses malformed values itself. An unrelated emitter defect
    # still must be one red rule rather than a dead checker run.
    files = {
        ring.DECLARATION: json.dumps(_declaration()),
        ring.ARTIFACT: "(* whatever a person typed *)\n",
        "docs/requirements-register.md": "# R\n\n## 1\n\n**R-01-001** MUST x.\n"
                                         "· Trace: t\n",
    }
    with sandbox_tree(files) as root:
        corpus = corpus_mod.load(root)
        ctx = Context(root=root, corpus=corpus, reg=_register(),
                      art=read_artifacts(corpus), rep=Reporter())
        with patch.object(ring, "emit", side_effect=TypeError("unexpected emitter defect")):
            rule.run(ctx)
        said = "\n".join(ctx.rep.out)
    ensure("FAIL K-89" in said,
           f"a generator that raises must be this rule's finding; the rule said:\n{said}")
    # Named, so the case decides the arm it exists for: catching the emitter's own
    # RingError would satisfy the line above and leave the new arm untested.
    ensure("TypeError" in said,
           f"the finding must name the unexpected exception, and so "
           f"must come from the arm past RingError; got:\n{said}")


def _declaration_refuses_wrong_types() -> None:
    # Every malformed value must be refused at load time, before the emitter can
    # sum it, interpolate it as Gallina, or mistake truthiness for a boolean.
    malformed: list[tuple[tuple[str | int, ...], Json]] = [
        (("worlds",), {}),
        (("worlds",), []),
        (("worlds", 0), False),
        (("worlds", 0, "world"), 3),
        (("worlds", 0, "ring"), []),
        (("worlds", 0, "ring", "capacity"), True),
        (("worlds", 0, "encoding", "request_id_bytes"), "4"),
        (("worlds", 0, "label_levels"), 4.0),
        (("worlds", 0, "flags"), "notify"),
        (("worlds", 0, "directions", 0), 3),
        (("worlds", 0, "operations"), {}),
        (("worlds", 0, "operations"), []),
        (("worlds", 0, "operations", 0), False),
        (("worlds", 0, "operations", 0, "name"), 3),
        (("worlds", 0, "operations", 0, "scalars", 0, "width_bytes"), "four"),
        (("worlds", 0, "operations", 0, "scalars", 0, "width_bytes"), 4.0),
        (("worlds", 0, "operations", 0, "scalars", 0, "validated_at_use"), 1),
        (("worlds", 0, "operations", 0, "deadline"), 1),
        (("worlds", 0, "operations", 0, "labels", "integrity"), "2"),
        (("worlds", 0, "operations", 0, "record", 0), False),
        (("worlds", 0, "operations", 0, "record"), [1]),
        (("worlds", 0, "operations", 0, "cancellation"), {}),
        (("worlds", 0, "operations", 0, "cancellation", "points"), []),
        (("worlds", 0, "operations", 0, "refinement"), [0]),
        (("worlds", 0, "operations", 0, "fill"), "24"),
        (("worlds", 0, "dma"), {}),
        (("worlds", 0, "dma"), 1),
    ]
    with sandbox_tree({ring.DECLARATION: "null"}) as root:
        path = root / ring.DECLARATION
        for malformed_root in (None, [], "declaration", 1):
            path.write_text(json.dumps(malformed_root), encoding="utf-8")
            _refused(lambda: ring.declaration(root),
                     f"a non-object declaration was accepted: {malformed_root!r}")
        for keys, value in malformed:
            base = _declaration()
            node: Any = base  # Deliberately cross types while constructing invalid input.
            for key in keys[:-1]:
                node = node[key]
            node[keys[-1]] = value
            path.write_text(json.dumps(base), encoding="utf-8")
            _refused(lambda: ring.declaration(root),
                     f"a malformed value was accepted at {keys}: {value!r}")


def _a_world_is_refused_where_it_is_not_a_scope() -> None:
    # A world name is spelled into a Gallina scope, and two worlds are two scopes, so a
    # name the emitter cannot spell and a name used twice are each refused here rather
    # than emitted into a file that then fails to compile or silently collides.
    with sandbox_tree({ring.DECLARATION: "null"}) as root:
        path = root / ring.DECLARATION
        cases = {
            "a world name that is not an identifier": "Ring Reference",
            "a world name that starts with a digit": "2nd_world",
            "an empty world name": "",
        }
        for why, name in cases.items():
            base = _declaration()
            base["worlds"][0]["world"] = name
            path.write_text(json.dumps(base), encoding="utf-8")
            _refused(lambda: ring.declaration(root),
                     f"declaration() accepted {why}")
        base = _declaration()
        ensure(len(base["worlds"]) >= 2,
               "this case needs a declaration carrying a second world")
        base["worlds"][1]["world"] = base["worlds"][0]["world"]
        path.write_text(json.dumps(base), encoding="utf-8")
        _refused(lambda: ring.declaration(root),
                 "declaration() accepted one world name twice, where one world is one "
                 "scope of the artifact")
        base = _declaration()
        base["worlds"].append(json.loads(json.dumps(base["worlds"][1])))
        base["worlds"][1]["world"] = "ring_dma"
        base["worlds"][-1]["world"] = "ring__dma"
        path.write_text(json.dumps(base), encoding="utf-8")
        _refused(lambda: ring.declaration(root),
                 "different world names that emit the same module were accepted")


def _a_dma_declaration_is_refused_where_it_disagrees_with_its_world() -> None:
    # The defect this case exists for: a DMA block the emitter reads but does not hold
    # against the world it sits in emits a campaign that decides nothing. A permission
    # map that is not one member per declared direction, a member outside the declared
    # set, a world declaring DMA of some operations and not others, and a world where
    # nothing holds a capability are each refused instead.
    def _short_permission_map(base: dict[str, Any]) -> None:
        dma = _dma_world(base)["dma"]
        dma["direction_permission"] = dma["direction_permission"][:1]

    def _permission_outside_the_declared_set(base: dict[str, Any]) -> None:
        _dma_world(base)["dma"]["direction_permission"][0] = "execute"

    def _one_permission_declared_twice(base: dict[str, Any]) -> None:
        dma = _dma_world(base)["dma"]
        dma["permissions"] = [dma["permissions"][0]] * 2

    def _an_unspellable_permission(base: dict[str, Any]) -> None:
        _dma_world(base)["dma"]["permissions"][0] = "Load Data"

    def _one_direction_only(base: dict[str, Any]) -> None:
        world = _dma_world(base)
        world["directions"] = world["directions"][:1]

    def _no_content_type(base: dict[str, Any]) -> None:
        _dma_world(base)["content_types"] = []

    def _drop_one_operations_dma(base: dict[str, Any]) -> None:
        _dma_world(base)["operations"][0]["dma"] = None

    def _dma_on_a_world_declaring_none(base: dict[str, Any]) -> None:
        plain = next(w for w in base["worlds"] if w["dma"] is None)
        plain["operations"][0]["dma"] = _dma_world(base)["operations"][0]["dma"]

    def _nothing_holds_a_capability(base: dict[str, Any]) -> None:
        for op in _dma_world(base)["operations"]:
            op["dma"]["held_capabilities"] = 0

    edits: dict[str, Callable[[dict[str, Any]], None]] = {
        "a permission map shorter than the declared directions": _short_permission_map,
        "a direction requiring a permission the world does not declare":
            _permission_outside_the_declared_set,
        "a permission declared twice": _one_permission_declared_twice,
        "a permission that is not a name this emitter spells": _an_unspellable_permission,
        "one direction under a permission check that distinguishes two":
            _one_direction_only,
        "a DMA world with no inhabited buffer reference": _no_content_type,
        "a world declaring DMA of some operations and not others":
            _drop_one_operations_dma,
        "an operation declaring DMA inside a world that declares none":
            _dma_on_a_world_declaring_none,
        "a DMA world where no operation holds a capability": _nothing_holds_a_capability,
    }
    with sandbox_tree({ring.DECLARATION: "null"}) as root:
        path = root / ring.DECLARATION
        for why, edit in edits.items():
            base = _declaration()
            edit(base)
            path.write_text(json.dumps(base), encoding="utf-8")
            _refused(lambda: ring.declaration(root),
                     f"declaration() accepted {why}")


def _declaration_preserves_metadata() -> None:
    base = _declaration()
    base["extra_metadata"] = {"version": 1.5, "reviewed": False}
    base["worlds"][0]["operations"][0]["scalars"][0]["extra_metadata"] = ["unconsumed", 1.5]
    with sandbox_tree({ring.DECLARATION: json.dumps(base)}) as root:
        ensure(ring.declaration(root) == base,
               "validation must preserve fields the emitter does not consume")


def _the_lost_wakeup_exclusion_is_a_property_a_rule_can_fail() -> None:
    # The defect this case exists for: an exclusion stated as `implb (sleeps ..)
    # (negb (work_pending ..))` with `sleeps` defined as that very conjunction is true
    # of every input by construction, and a theorem over it labelled as the lost-wakeup
    # property decides nothing. What makes the exclusion a property is that it is stated
    # of a decision rule, one rule is proved to satisfy it, and a rule that sleeps on the
    # drain's read instead of the recheck is proved to fail it.
    root = corpus_mod.find_root()
    text = ring.emit(root)
    ensure("no_lost_wakeup (decide : nat -> nat -> nat -> bool -> bool) : Prop" in text,
           "the exclusion must be stated of a decision rule, not of one rule's body")
    ensure("~ no_lost_wakeup sleeps_without_recheck." in text,
           "the artifact must carry the refutation, a consumer that skips the recheck")
    ensure("implb (sleeps" not in text,
           "the exclusion must not be one rule's own conjunction implying its own "
           "conjunct, which is true of every input by construction")


def _the_dma_clauses_are_properties_a_declaration_can_fail() -> None:
    # The same reading applied to part 4. A clause stated of the one declaration that
    # satisfies it decides nothing, so each of the three added clauses carries the
    # instance it refuses: a capability released at reclamation rather than at terminal
    # completion, a validation short of the declared payload, and a capability granting
    # the permission the other direction requires.
    root = corpus_mod.find_root()
    text = ring.emit(root)
    ensure("dead_past_terminal_completion (hold : op -> slot_state -> nat) : Prop"
           in text,
           "the retention exclusion must be stated of a hold, not of one hold's body")
    ensure("~ dead_past_terminal_completion holds_until_reclaimed." in text,
           "the artifact must carry the refutation, a hold released at reclamation")
    ensure("the_two_holds_agree_before_terminal_completion" in text,
           "the refutation must isolate the release point, which is what the "
           "keeps-theorem beside it decides")
    ensure("a_validation_short_of_the_declared_payload_is_not_the_extent" in text,
           "the complete-extent clause must carry the validation it refuses")
    ensure("negb (direction_authorized" in text,
           "the permission check must refuse a permission the direction does not "
           "require, and not only admit the one it does")
    ensure("a_bad_segment_at_any_position_refuses_the_list" in text,
           "charging a cost per segment must accompany checking each segment")
    ensure("a_segment_extending_past_its_capability_is_refused" in text,
           "the segment campaign must reject an extent crossing its delegated bound")


def _each_world_past_the_first_takes_a_scope_of_its_own() -> None:
    # A Gallina file has one top-level scope, so a second world sharing it would
    # redefine `op` and fail to compile. The first world declared takes that scope and
    # every further world takes a module named from its own name.
    root = corpus_mod.find_root()
    worlds = ring.declaration(root)["worlds"]
    ensure(len(worlds) >= 2, "this case needs a declaration carrying a second world")
    text = ring.emit(root)
    ensure(text.index("Inductive op : Set :=") < text.index("\nModule "),
           "the first world declared must take the file's own scope, which is what the "
           "artifact's consumers name unqualified")
    for world in worlds[1:]:
        module = ring._module(world["world"])
        ensure(f"\nModule {module}.\n" in text and f"\nEnd {module}.\n" in text,
               f"world `{world['world']}` must be emitted into module `{module}`")
    # The campaign is one generator's, so a theorem of the file scope is a theorem of
    # every module too: a second world instantiating a smaller campaign would be a
    # second generator, which is exactly what the declaration exists to prevent.
    family_cases = (
        "ring_refuses_one_past_capacity",
        "an_unstarted_cancellable_target_is_cancelled",
        "a_target_before_its_commit_point_is_cancelled",
        "cancellation_outside_live_states_is_not_live",
        "reset_in_every_lifecycle_state_clears_the_indices_and_notification",
        "reset_without_quiescence_never_publishes_a_generation",
        "reset_in_every_lifecycle_state_refuses_the_old_generation",
        "a_duplicate_live_identifier_is_refused",
        "a_consumer_that_skips_the_recheck_loses_a_wakeup",
        "the_declared_batch_and_segment_maxima_are_attained",
    )
    for theorem in family_cases:
        ensure(text.count(f"Theorem {theorem} :") == len(worlds),
               f"every world must carry the campaign case `{theorem}`")


def cases() -> list[Case]:
    return [
        Case("the-lost-wakeup-exclusion-is-a-property-a-rule-can-fail",
             _the_lost_wakeup_exclusion_is_a_property_a_rule_can_fail),
        Case("the-dma-clauses-are-properties-a-declaration-can-fail",
             _the_dma_clauses_are_properties_a_declaration_can_fail),
        Case("each-world-past-the-first-takes-a-scope-of-its-own",
             _each_world_past_the_first_takes_a_scope_of_its_own),
        Case("a-state-inserted-moves-the-skip", _a_state_inserted_moves_the_skip),
        Case("the-named-states-are-read-not-counted",
             _the_named_states_are_read_not_counted),
        Case("owned-fails-closed-on-each-shape", _owned_fails_closed_on_each_shape),
        Case("declaration-names-every-key-the-emitter-reads",
             _declaration_names_every_key_the_emitter_reads),
        Case("declaration-refuses-wrong-types", _declaration_refuses_wrong_types),
        Case("a-world-is-refused-where-it-is-not-a-scope",
             _a_world_is_refused_where_it_is_not_a_scope),
        Case("a-dma-declaration-is-refused-where-it-disagrees-with-its-world",
             _a_dma_declaration_is_refused_where_it_disagrees_with_its_world),
        Case("declaration-preserves-metadata", _declaration_preserves_metadata),
        Case("the-rule-reports-rather-than-crashes",
             _the_rule_reports_rather_than_crashes),
    ]
