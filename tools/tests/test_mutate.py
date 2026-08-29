# SPDX-License-Identifier: Apache-2.0
"""The mutation engine's two masks and its operator population.

The masks are what separate a measurement from noise, and both of them fail silently
when they are wrong. A mutation landing in a comment produces a mutant that compiles
to the same program, so the oracle agrees and the run reports a survivor about
nothing; a mutation landing in a Coq proof script breaks the proof and reports a kill
that says nothing about whether the statement constrains the definition. Neither is
visible in a run's output, which is why both are pinned here.
"""

from tests.harness import Case, ensure
from vos import mutate


def _sites(text: str, lane: str, operator: str, **kw: object) -> list[mutate.Mutant]:
    found = mutate.mutants(text, lane, "f.sail" if lane == mutate.SAIL else "f.v",
                           **kw)  # ty: ignore[invalid-argument-type]
    return [m for m in found if m.operator == operator]


def _sail_line_comments_are_cut_out() -> None:
    text = ("function f(x : bits(4)) -> bool = {\n"
            "  // a <= b in a comment\n"
            "  unsigned(x) <= 3\n"
            "}\n")
    found = _sites(text, mutate.SAIL, "le-to-lt")
    ensure(len(found) == 1, f"{len(found)} sites where the code carries one")
    ensure(found[0].line == 3, f"the site landed on line {found[0].line}, not 3")


def _sail_block_comments_are_cut_out() -> None:
    text = "let a = 1\n/* 2 3 4 */\nfunction g() -> int = 5\n"
    found = _sites(text, mutate.SAIL, "const-inc")
    ensure({m.before for m in found} == {"1", "5"},
           f"the literals reached were {sorted(m.before for m in found)}")


def _coq_comments_nest() -> None:
    """Rocq comments nest, so a scan that stopped at the first `*)` would leave the
    tail of an outer comment mutable and produce mutants that are pure noise."""
    text = ("Definition f (n : nat) : nat :=\n"
            "  (* outer (* inner 7 *) still comment 8 *)\n"
            "  n + 1.\n")
    found = _sites(text, mutate.COQ, "const-inc")
    ensure([m.before for m in found] == ["1"],
           f"the literals reached were {[m.before for m in found]}")


def _string_literals_are_cut_out() -> None:
    text = 'function f() -> string = {\n  let s = "true 5";\n  if true then s else s\n}\n'
    found = _sites(text, mutate.SAIL, "true-to-false")
    ensure(len(found) == 1, f"{len(found)} sites where only the code carries one")
    ensure(found[0].line == 3, f"the site landed on line {found[0].line}, not 3")


def _coq_proofs_are_outside_the_default_region() -> None:
    """The whole ground of the Coq lane: a mutation inside a tactic script kills
    itself and decides nothing, so the default region is the definitional commands."""
    text = ("Definition f (n : nat) : bool := Nat.leb n 3.\n"
            "\n"
            "Lemma l : f 3 = true.\n"
            "Proof. unfold f. simpl. reflexivity. Qed.\n")
    found = _sites(text, mutate.COQ, "const-inc")
    ensure([m.line for m in found] == [1],
           f"the sites reached lines {[m.line for m in found]}, and only line 1 is a "
           "definition")


def _a_region_can_be_named() -> None:
    text = ("Definition a (n : nat) : nat := n + 1.\n"
            "Definition b (n : nat) : nat := n + 2.\n")
    found = _sites(text, mutate.COQ, "const-inc", named=("b",))
    ensure([m.before for m in found] == ["2"],
           f"naming one region reached {[m.before for m in found]}")


def _hex_and_bit_literals_are_not_arithmetic() -> None:
    """`0x1f` and `0b0101` are one token each and incrementing a digit inside one is a
    different constant in a different base, which is a mutation nobody asked for."""
    text = "function f() -> bits(8) = 0x1f | 0b0101_0000 | to_bits(8, 12)\n"
    found = _sites(text, mutate.SAIL, "const-inc")
    ensure({m.before for m in found} == {"8", "12"},
           f"the literals reached were {sorted(m.before for m in found)}")


def _a_slice_moves_as_a_whole() -> None:
    text = "function f(x : bits(64)) -> bits(4) = x[35 .. 32]\n"
    found = _sites(text, mutate.SAIL, "slice-down")
    ensure(len(found) == 1, f"{len(found)} slice sites in one slice")
    ensure(found[0].after == "[34 .. 31]", f"the slice became {found[0].after}")


def _applying_a_mutant_changes_one_span() -> None:
    text = "function f(x : bits(4)) -> bool = unsigned(x) <= 3\n"
    mutant = _sites(text, mutate.SAIL, "le-to-lt")[0]
    got = mutant.apply(text)
    ensure(got == "function f(x : bits(4)) -> bool = unsigned(x) < 3\n",
           f"the mutant produced {got!r}")
    ensure(len(got) == len(text) - 1, "more than the matched span moved")


def _the_population_is_deterministic() -> None:
    text = ("function f(x : bits(4), y : bits(4)) -> bool = {\n"
            "  let a = unsigned(x) + 1;\n"
            "  a <= unsigned(y) & true\n"
            "}\n")
    first = mutate.mutants(text, mutate.SAIL, "f.sail")
    again = mutate.mutants(text, mutate.SAIL, "f.sail")
    ensure([m.ident for m in first] == [m.ident for m in again],
           "two walks of one source produced different populations")
    ensure(len({m.ident for m in first}) == len(first), "two mutants share an id")


def _a_lane_is_read_off_the_path() -> None:
    ensure(mutate.lane_of("a/b.sail") == mutate.SAIL, "a .sail is not the Sail lane")
    ensure(mutate.lane_of("a/b.v") == mutate.COQ, "a .v is not the Coq lane")
    try:
        mutate.lane_of("a/b.py")
    except ValueError as err:
        ensure("two lanes" in str(err), f"the refusal said {err!r}")
        return
    raise AssertionError("a Python file was given a lane")


def _every_operator_names_a_lane_it_runs_on() -> None:
    """A table of callbacks nothing types is a table where a member with the wrong
    shape is found by running the corpus rather than by reading the module."""
    for op in mutate.OPERATORS:
        ensure(bool(op.lanes), f"{op.name} names no lane")
        ensure(all(lane in mutate.LANES for lane in op.lanes),
               f"{op.name} names a lane this engine does not carry")
        ensure(bool(op.what), f"{op.name} says nothing about what it seeds")
    names = [op.name for op in mutate.OPERATORS]
    ensure(len(set(names)) == len(names), "two operators share a name")


def cases() -> list[Case]:
    return [
        Case("a Sail line comment is not mutable", _sail_line_comments_are_cut_out),
        Case("a Sail block comment is not mutable", _sail_block_comments_are_cut_out),
        Case("a Rocq comment nests", _coq_comments_nest),
        Case("a string literal is not mutable", _string_literals_are_cut_out),
        Case("a Rocq proof script is outside the default region",
             _coq_proofs_are_outside_the_default_region),
        Case("a region can be named", _a_region_can_be_named),
        Case("a hex or bit literal is one token", _hex_and_bit_literals_are_not_arithmetic),
        Case("a bit slice moves as a whole", _a_slice_moves_as_a_whole),
        Case("applying a mutant changes one span", _applying_a_mutant_changes_one_span),
        Case("the population is deterministic", _the_population_is_deterministic),
        Case("a lane is read off the path", _a_lane_is_read_off_the_path),
        Case("every operator is whole", _every_operator_names_a_lane_it_runs_on),
    ]
