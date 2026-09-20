# SPDX-License-Identifier: Apache-2.0
"""The corpus reading's predicates, each against text Rocq actually prints.

Every fixture here is a transcription of output the pinned Rocq 9.2.0 produced for a
probe of the same shape, because a parse held against text nobody printed is a parse of
an imagined format. Each case pairs the positive reading with the shape that must not
satisfy it: a non-dependent `match` beside a dependent one, a single `fix` beside a
mutual block, a closure with a transparent member beside one without.
"""

from collections.abc import Callable

from tests.harness import Case, ensure
from vos import cic_corpus

# `Print All Dependencies usesax.` at Rocq 9.2.0, where the entry's type went to a line
# of its own without indentation. Both entry shapes the command prints are here.
_DEPENDENCIES = """\
Axioms:
myax : nat
Opaque constants:
usesax :
@eq nat myax myax
Transparent constants:
Corelib.Init.Nat.add : forall (_ : nat) (_ : nat), nat
"""

_ABOUT_OPAQUE = """\
op : @eq nat (S O) (S O)

op is not universe polymorphic
op is opaque
Expands to: Constant AdmissionPath.op
Declared in library AdmissionPath, line 1, characters 6-8
"""

_ABOUT_INDUCTIVE = """\
tree : Set

tree is not universe polymorphic
Expands to: Inductive AdmissionPath.tree
"""

# The third universe sentence, taken from `About AdmissionPath.Build_Generation` in this
# lane's compiled corpus. It is a suffix of neither of the other two and must not read
# as either.
_ABOUT_TEMPLATE = """\
AdmissionPath.Build_Generation :
forall (D : Type) (_ : list (AdmissionPath.Package D)) (_ : list nat),
AdmissionPath.Generation D

AdmissionPath.Build_Generation is template universe polymorphic
Expands to: Constructor AdmissionPath.Build_Generation
"""

# `Print ev.` for a mutual block, and `Print nested.` for a body carrying two binders.
_MUTUAL = """\
ev = fix ev (n : nat) : bool := match n return bool with
                                | O => true
                                | S m => od m
                                end
     with od (n : nat) : bool := match n return bool with
                                 | O => false
                                 | S m => ev m
                                 end
     for ev
     : forall _ : nat, bool
"""

_NESTED = """\
nested = fix nested (l : list nat) : nat := match l return nat with
   | @nil _ => O
   | @cons _ x r => (fix inner (k : nat) : nat := match k return nat with
                                                  | O => nested r
                                                  | S j => S (inner j)
                                                  end) x
   end
"""

_DEPENDENT = """\
dep = fun n : nat => match n as k return match k return Set with
                                         | O => bool
                                         | S _ => nat
                                         end with
                     | O => true
                     | S _ => O
                     end
"""

_PLAIN = """\
plain = fun n : nat => match n return bool with
                       | O => true
                       | S _ => false
                       end
"""


def _refused(action: Callable[[], object], why: str) -> None:
    try:
        action()
    except cic_corpus.ParseError:
        return
    raise AssertionError(why)


def _dependencies_read_both_entry_shapes() -> None:
    found = cic_corpus.parse_dependencies(_DEPENDENCIES)
    ensure(found["axioms"] == ["myax"], f"the axiom heading's member: {found['axioms']}")
    ensure(found["opaque"] == ["usesax"],
           f"an entry whose type went to its own line: {found['opaque']}")
    ensure(found["transparent"] == ["Corelib.Init.Nat.add"],
           f"a qualified foreign member: {found['transparent']}")
    ensure(found["variables"] == [], "an unprinted heading contributes nothing")
    closed = cic_corpus.parse_dependencies(cic_corpus.CLOSED)
    ensure(not any(closed.values()), "a closed constant has an empty closure")
    # A transparent constant's own type wraps, indented and not, and no line of it may
    # become a dependency. Both shapes are taken from this lane's compiled corpus.
    wrapped = cic_corpus.parse_dependencies(
        "Transparent constants:\nAdmissionPath.rule_eqb :\n"
        "forall (_ : AdmissionPath.Rule) (_ : AdmissionPath.Rule), bool\n"
        "   | @Some _ r2 => AdmissionPath.rule_eqb r r2\n")
    ensure(wrapped["transparent"] == ["AdmissionPath.rule_eqb"],
           f"a wrapped type contributes no dependency: {wrapped['transparent']}")


def _dependencies_refuse_what_they_cannot_place() -> None:
    _refused(lambda: cic_corpus.parse_dependencies(""),
             "a silent query cannot read as an empty closure")
    _refused(lambda: cic_corpus.parse_dependencies("Opaque constants:\n"),
             "a heading with no entry is a parse this module did not make")
    _refused(lambda: cic_corpus.parse_dependencies("Primitives:\nfoo : nat\n"),
             "a heading Rocq gained is a change to see, not to skip")
    _refused(lambda: cic_corpus.parse_dependencies("myax : nat\n"),
             "an entry before every heading has no category")
    _refused(lambda: cic_corpus.parse_dependencies("@eq nat myax myax\n"),
             "a continuation before every heading belongs to no entry")


def _about_states_kind_opacity_and_universes() -> None:
    opaque = cic_corpus.parse_about(_ABOUT_OPAQUE)
    ensure(opaque.kind == "Constant" and opaque.opacity == "opaque",
           f"an opaque constant: {opaque}")
    ensure(opaque.universes == "monomorphic" and not opaque.universe_polymorphic,
           f"the fixture's universe sentence: {opaque.universes}")
    ensure(opaque.expands_to == "AdmissionPath.op", f"the expansion: {opaque.expands_to}")
    inductive = cic_corpus.parse_about(_ABOUT_INDUCTIVE)
    ensure(inductive.kind == "Inductive" and inductive.opacity == "n/a",
           f"an inductive carries no opacity: {inductive}")
    polymorphic = cic_corpus.parse_about(
        _ABOUT_OPAQUE.replace("is not universe polymorphic", "is universe polymorphic"))
    ensure(polymorphic.universes == "polymorphic" and polymorphic.universe_polymorphic,
           f"the quantified universe reading: {polymorphic.universes}")
    template = cic_corpus.parse_about(_ABOUT_TEMPLATE)
    ensure(template.universes == "template" and template.kind == "Constructor",
           f"template polymorphism is its own answer: {template}")
    ensure(template.universe_polymorphic,
           "a template-polymorphic symbol does not read as monomorphic")
    _refused(lambda: cic_corpus.parse_about("op : nat\n"),
             "About with no expansion names no kind")
    _refused(lambda: cic_corpus.parse_about(
        _ABOUT_OPAQUE.replace("op is not universe polymorphic\n", "")),
        "About with no universe sentence cannot be read as monomorphic")
    _refused(lambda: cic_corpus.parse_about(_ABOUT_OPAQUE.replace("op is opaque\n", "")),
             "a constant with no opacity sentence cannot default to transparent")


def _term_features_separate_the_shapes() -> None:
    mutual = cic_corpus.term_features(_MUTUAL)
    ensure("fix-binder" in mutual and "fix-binder-mutual" in mutual,
           f"a mutual block prints one fix and a for selector: {mutual}")
    ensure("fix-binders-multiple" not in mutual,
           f"a mutual block is not two binders: {mutual}")
    nested = cic_corpus.term_features(_NESTED)
    ensure("fix-binders-multiple" in nested and "fix-binder-mutual" not in nested,
           f"two binders and no selector: {nested}")
    dependent = cic_corpus.term_features(_DEPENDENT)
    ensure("match-dependent-return" in dependent, f"an as clause is dependent: {dependent}")
    plain = cic_corpus.term_features(_PLAIN)
    ensure("match" in plain and "match-dependent-return" not in plain,
           f"a return with no as or in clause is not dependent: {plain}")
    ensure(cic_corpus.dependent_matches(_DEPENDENT) == 1,
           "the inner return predicate's own match is not a second dependent head")
    ensure(not cic_corpus.term_features("prefix = fun n : nat => fixed_point n"),
           "fix inside an identifier is not a binder")


def _primitives_are_found_in_either_reading() -> None:
    ensure(cic_corpus.primitive_features("x = Uint63.add") == ["primitive-int63"],
           "a primitive named in the declaration")
    ensure(cic_corpus.primitive_features("x = f", "Corelib.Floats.PrimFloat.mul")
           == ["primitive-float64"],
           "a primitive reached only through the closure still counts")
    ensure(cic_corpus.primitive_features("x = plain") == [],
           "a declaration naming none reports none")


def _classification_states_the_conversion_reading() -> None:
    about = cic_corpus.parse_about(_ABOUT_OPAQUE)
    closed = cic_corpus.classify("M.op", "nat", about,
                                 cic_corpus.parse_dependencies(cic_corpus.CLOSED), _PLAIN)
    ensure("no-transparent-dependency" in closed.features,
           f"an empty closure cannot need delta reduction: {closed.features}")
    ensure("opaque-body" in closed.features, "About decided the opacity")
    full = cic_corpus.classify("M.op", "nat", about,
                               cic_corpus.parse_dependencies(_DEPENDENCIES), _PLAIN)
    ensure("transparent-constant-dependency" in full.features
           and "axiom-dependency" in full.features
           and "no-transparent-dependency" not in full.features,
           f"a closure with both kinds: {full.features}")
    absent = cic_corpus.classify("M.op", "nat", about,
                                 cic_corpus.parse_dependencies(_DEPENDENCIES), None)
    ensure("term-reading-unavailable" in absent.features and not absent.body_printed,
           f"a refused term reading is stated, not silently featureless: {absent.features}")
    ensure("match" not in absent.features,
           "a refused term reading reports no term feature at all")
    template = cic_corpus.classify(
        "M.Build_G", "nat", cic_corpus.parse_about(_ABOUT_TEMPLATE),
        cic_corpus.parse_dependencies(cic_corpus.CLOSED), _PLAIN)
    ensure("universes-template" in template.features
           and "universes-monomorphic" not in template.features,
           f"the universe feature names which of the three it is: {template.features}")
    ensure(not any(f.startswith("universes-") for f in closed.features),
           f"a monomorphic symbol carries no universe feature: {closed.features}")
    counted = cic_corpus.totals([closed, full, absent])
    ensure(counted["constants"] == 3 and counted["opacity:opaque"] == 3,
           f"the totals count records: {counted}")
    ensure(counted["universes:monomorphic"] == 3,
           f"the totals state the universe answer for every record: {counted}")
    ensure(counted["no-transparent-dependency"] == 1,
           f"a total is a count over the records carrying that feature: {counted}")


def _blocks_refuse_a_missing_or_extra_answer() -> None:
    marked = (f"{cic_corpus.MARKER}a\nfirst\n{cic_corpus.MARKER}b\nsecond\n")
    ensure(cic_corpus.blocks(marked, ["a", "b"]) == {"a": "first", "b": "second"},
           "each answer belongs to the marker that introduced it")
    _refused(lambda: cic_corpus.blocks(marked, ["a", "b", "c"]),
             "an unwritten answer is a refusal, not a shorter result")
    _refused(lambda: cic_corpus.blocks(marked, ["a"]),
             "an answer nobody asked for is a query this parse does not understand")
    _refused(lambda: cic_corpus.blocks("stray\n" + marked, ["a", "b"]),
             "output before the first marker belongs to no constant")


def _source_reading_counts_sentences() -> None:
    text = ("Section S.\nFixpoint f (n : nat) : nat := n with g (n : nat) : nat := n.\n"
            "Polymorphic Definition d := tt.\nEnd S.\n"
            "(* Fixpoint hidden in a comment. *)\n")
    counts = cic_corpus.source_declarations(text)
    ensure(counts["Section"] == 1 and counts["End"] == 1,
           f"section vernaculars are counted: {counts}")
    ensure(counts["Fixpoint"] == 1, f"one mutual block is one sentence: {counts}")
    ensure(counts["Polymorphic"] == 1, f"a modifier is counted at its head: {counts}")
    ensure("mutual-with" not in counts,
           "mutual recursion is the term reading's to decide, not this one's")
    ensure(cic_corpus.source_declarations("(* Fixpoint *)\n")["Fixpoint"] == 0,
           "a comment declares nothing")
    ensure(cic_corpus.source_declarations(
        "Definition d := match n with O => 0 | S _ => 1 end.\n")["Fixpoint"] == 0,
        "a vernacular named inside a sentence is not that sentence's head")


def _closure_names_split_by_ownership() -> None:
    local, foreign = cic_corpus.local_names(
        ["AdmissionPath.check_cert", "Corelib.Init.Nat.add"], {"AdmissionPath"})
    ensure(local == ["AdmissionPath.check_cert"] and foreign == ["Corelib.Init.Nat.add"],
           f"the corpus's own constants and everything else: {local} {foreign}")
    # The printer gives the shortest unambiguous name, so a foreign member arrives
    # unqualified and must not be read as a corpus constant on that account.
    short, outside = cic_corpus.local_names(["andb", "Nat.add", "MemoryPlan.plan"],
                                            {"AdmissionPath", "MemoryPlan"})
    ensure(short == ["MemoryPlan.plan"] and outside == ["andb", "Nat.add"],
           f"an unqualified foreign name stays foreign: {short} {outside}")


def cases() -> list[Case]:
    return [
        Case("dependencies-read-both-entry-shapes", _dependencies_read_both_entry_shapes),
        Case("dependencies-refuse-unplaceable-output",
             _dependencies_refuse_what_they_cannot_place),
        Case("about-states-kind-opacity-universes", _about_states_kind_opacity_and_universes),
        Case("term-features-separate-the-shapes", _term_features_separate_the_shapes),
        Case("primitives-in-either-reading", _primitives_are_found_in_either_reading),
        Case("classification-states-conversion-reading",
             _classification_states_the_conversion_reading),
        Case("blocks-refuse-missing-or-extra", _blocks_refuse_a_missing_or_extra_answer),
        Case("source-reading-counts-sentences", _source_reading_counts_sentences),
        Case("closure-names-split-by-ownership", _closure_names_split_by_ownership),
    ]
