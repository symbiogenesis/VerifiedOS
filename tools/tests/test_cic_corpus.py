# SPDX-License-Identifier: Apache-2.0
"""The corpus reading's predicates, each against text Rocq actually prints.

Every fixture here is a transcription of output the pinned Rocq 9.3.0 produced for a
probe of the same shape, because a parse held against text nobody printed is a parse of
an imagined format. Each case pairs the positive reading with the shape that must not
satisfy it: a non-dependent `match` beside a dependent one, a single `fix` beside a
mutual block, a closure with a transparent member beside one without.
"""

from collections.abc import Callable

from tests.harness import Case, ensure
from vos import cic_corpus
from vos.cli import cic_corpus as cic_cli

# `Print All Dependencies usesax.` in the module declaring `myax` and `usesax`, where
# each entry's type goes to a line of its own without indentation, and a foreign member
# prints by its shortest unambiguous name.
_DEPENDENCIES = """\
Transparent constants:
Nat.add :
forall (_ : nat) (_ : nat), nat
Axioms:
myax : nat
Opaque constants:
usesax :
@eq nat myax myax
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
Declared in library AdmissionPath, line 2, characters 10-14
"""

# The third universe sentence, taken from `About AdmissionPath.Build_Generation` in this
# lane's compiled corpus. It is a suffix of neither of the other two and must not read
# as either.
_ABOUT_TEMPLATE = """\
AdmissionPath.Build_Generation : forall (D : Type) (_ : list (AdmissionPath.Package D)) \
(_ : list nat), AdmissionPath.Generation D

AdmissionPath.Build_Generation is template universe polymorphic
Arguments AdmissionPath.Build_Generation D%_type_scope (gen_image gen_synthesized)%_list_scope
Expands to: Constructor AdmissionPath.Build_Generation
Declared in library AdmissionPath, line 2557, characters 7-17
"""

# Two transparent members of `Print All Dependencies
# AdmissionPath.every_refusal_rule_fires_on_a_witness.` in this lane's compiled corpus:
# a type on one line of its own, and a type whose match arms wrap onto lines indented
# under the match, none of which may become a dependency.
_ARM = " " * 204
_WRAPPED = (
    "Transparent constants:\nAdmissionPath.rule_eqb :\n"
    "forall (_ : AdmissionPath.RuleId) (_ : AdmissionPath.RuleId), bool\n"
    "AdmissionPath.every_refusal_rule_fires_on_a_witness :\n"
    "@eq bool (@AdmissionPath.all_of AdmissionPath.RuleId (fun r : AdmissionPath.RuleId => "
    "@AdmissionPath.any_of (AdmissionPath.Package AdmissionPath.Cert) "
    "(fun p : AdmissionPath.Package AdmissionPath.Cert => match AdmissionPath.rule_of "
    "(AdmissionPath.demo_check p) return bool with\n"
    f"{_ARM}| @Some _ r2 => AdmissionPath.rule_eqb r r2\n"
    f"{_ARM}| @None _ => false\n"
    f"{_ARM}end) AdmissionPath.refusal_witnesses) AdmissionPath.all_rules) true\n")

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

Arguments ev n%_nat_scope
"""

_NESTED = """\
nested = fix nested (l : list nat) : nat := match l return nat with
                                            | @nil _ => O
                                            | @cons _ x r => (fix inner (k : nat) : nat := match k return nat with
                                                                                           | O => nested r
                                                                                           | S j => S (inner j)
                                                                                           end) x
                                            end
     : forall _ : list nat, nat

Arguments nested l%_list_scope
"""

_DEPENDENT = """\
dep = fun n : nat => match n as k return match k return Set with
                                         | O => bool
                                         | S _ => nat
                                         end with
                     | O => true
                     | S _ => O
                     end
     : forall n : nat, match n return Set with
                       | O => bool
                       | S _ => nat
                       end

Arguments dep n%_nat_scope
"""

_PLAIN = """\
plain = fun n : nat => match n return bool with
                       | O => true
                       | S _ => false
                       end
     : forall _ : nat, bool

Arguments plain n%_nat_scope
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
    ensure(found["transparent"] == ["Nat.add"],
           f"a qualified foreign member: {found['transparent']}")
    ensure(found["variables"] == [], "an unprinted heading contributes nothing")
    closed = cic_corpus.parse_dependencies(cic_corpus.CLOSED)
    ensure(not any(closed.values()), "a closed constant has an empty closure")
    # A transparent constant's own type wraps, indented and not, and no line of it may
    # become a dependency.
    wrapped = cic_corpus.parse_dependencies(_WRAPPED)
    ensure(wrapped["transparent"]
           == ["AdmissionPath.rule_eqb", "AdmissionPath.every_refusal_rule_fires_on_a_witness"],
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


def _source_reading_reads_past_decorations() -> None:
    # Every decoration before a vernacular is read past, however many there are, and a
    # counted modifier is counted however it is spelled: as a legacy attribute, or as the
    # quoted attribute that replaces it.
    text = ("#[local] #[program] Definition d := tt.\n"
            "#[universes(polymorphic, cumulative)] Inductive I := C.\n"
            "#[universes(polymorphic=no)]\nInductive J := D.\n"
            "Polymorphic Cumulative Inductive K := E.\n"
            "Local Program Fixpoint f (n : nat) : nat := n.\n"
            '#[deprecated(note="program")] Fixpoint g (n : nat) : nat := n.\n'
            "Time Fixpoint h (n : nat) : nat := n.\n"
            "#[universes(cumulative=no)] Inductive L := F.\n"
            "#[program=no] Fixpoint p (n : nat) : nat := n.\n")
    counts = cic_corpus.source_declarations(text)
    want = {"Inductive": 4, "Fixpoint": 4, "Program": 2, "Polymorphic": 2,
            "Cumulative": 2, "Monomorphic": 1, "NonCumulative": 1}
    ensure({key: counts[key] for key in want} == want,
           f"the vernaculars under decorations and the modifiers they spell: {counts}")
    # `Fail` and `Succeed` keep nothing a sentence declares, on its line or the line
    # above, so neither its vernacular nor any modifier around the flag is counted
    void = cic_corpus.source_declarations(
        "Fail Inductive I := C.\nSucceed\nFixpoint f (n : nat) : nat := n.\n"
        "#[local] Fail Polymorphic Inductive J := D.\n"
        "#[program]\nSucceed Cumulative Inductive K := E.\n")
    ensure(not any(void.values()), f"a sentence under a void flag was counted: {void}")


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


def _marker_goals_open_with_proof() -> None:
    # The pinned Rocq 9.3 reports an interactive proof that Proof does not open, and
    # _query refuses any diagnostic, so a marker goal without Proof fails every query.
    for bodies, count in ((True, 1), (False, 2)):
        query = cic_cli._reading_query("M", ["M.a"], bodies=bodies)
        ensure(query.count("Goal True.") == count and query.count("Goal True. Proof. ") == count,
               f"a generated marker goal opened without Proof: {query!r}")


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
        Case("source-reading-reads-past-decorations",
             _source_reading_reads_past_decorations),
        Case("closure-names-split-by-ownership", _closure_names_split_by_ownership),
        Case("marker-goals-open-with-proof", _marker_goals_open_with_proof),
    ]
