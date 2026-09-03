# SPDX-License-Identifier: Apache-2.0
"""The proof gate's witness half, held on the host where no Rocq switch is needed.

`run.py proofs` compiles in the guest, but what it decides about R-05-166 is a reading
of the source text: which records a file's statements quantify over, and whether the
file constructs one. That reading is a pure function over a string and is held here
directly, against sentences shaped like the shipped artifacts' own: a carrier record
with its `demo`, a data record built only through `Build_`, a record literal, a record
inhabited by a companion the file Requires, and the finding itself, a quantified record
nobody builds. The last case reads the live tree: every shipped artifact constructs
every record it quantifies over, which is the fact the gate's green line reports.
"""

from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos.cli import proofs as gate

_ROOT = TOOLS.parent

_CARRIER = """
(* The machine: fields rather than Parameters, so (* nested *) comments too. *)
Record Machine : Type := {
  unit_count : nat;
  manifest : nat -> nat -> bool
}.

Definition Reachable (m : Machine) (u : nat) : Prop := m.(manifest) 0 u = true.

Theorem every_unit_is_below_the_count :
  forall (m : Machine) (u : nat), Reachable m u -> u < m.(unit_count) \\/ True.
Proof. intros. right. exact I. Qed.

Definition demo : Machine := {| unit_count := 2; manifest := fun _ _ => true |}.
Definition demo_empty : Machine := {| unit_count := 0; manifest := fun _ _ => false |}.
Definition not_a_witness : Machine -> Prop := fun _ => True.
Example the_demo_machine_declares : demo.(unit_count) = 2 := eq_refl.
Print Assumptions every_unit_is_below_the_count.
"""

_BUILT_ONLY = """
Record Population : Type := { live_count : nat; queue_depth : nat }.
Definition bump (p : Population) : Population :=
  Build_Population (S (live_count p)) (queue_depth p).
Lemma bump_counts : forall p : Population, live_count (bump p) = S (live_count p).
Proof. reflexivity. Qed.
"""

_LITERAL_ONLY = """
Record Epoch : Type := { ep_sealed : bool; ep_index : nat }.
Definition all_epochs : list Epoch :=
  cons {| ep_sealed := true; ep_index := 0 |} nil.
Lemma sealed_or_not : forall e : Epoch, ep_sealed e = true \\/ ep_sealed e = false.
Proof. intro e. destruct (ep_sealed e); auto. Qed.
"""

_UNBUILT = """
Record Ghost : Type := { haunt : nat -> bool }.
Record Seen : Type := { glimpse : nat }.
Definition seen_once : Seen := {| glimpse := 1 |}.
Theorem nothing_haunts : forall (g : Ghost) (s : Seen), haunt g (glimpse s) = true -> True.
Proof. intros. exact I. Qed.
"""

_COMMENTED_BUILD = """
Record Ghost : Type := { haunt : nat -> bool }.
(* Build_Ghost, and a literal {| haunt := fun _ => true |}, both commented out. *)
Theorem nothing_haunts : forall g : Ghost, haunt g 0 = true -> True.
Proof. intros. exact I. Qed.
"""

_SECTIONED = """
Record Plan : Type := { region_count : nat }.
Section Over.
  Variable p : Plan.
  Lemma counted : region_count p = region_count p.
  Proof. reflexivity. Qed.
End Over.
"""

_COMPANION = """
Require Import Apex.
Lemma at_the_trivial_point : forall v : Vocabulary, v = v.
Proof. reflexivity. Qed.
"""

_APEX = """
Record Vocabulary : Type := { Input : Type; policy : Input -> bool }.
Definition trivial_vocabulary : Vocabulary := {| Input := unit; policy := fun _ => true |}.
"""


def _carrier_is_quantified_and_witnessed() -> None:
    found = gate.scan_witnesses(_CARRIER)
    ensure(found.quantified == {"Machine": 1},
           f"one statement ranges over Machine, got {found.quantified!r}")
    ensure(found.witnesses.get("Machine") == ["demo", "demo_empty"],
           f"the two closed definitions typed at Machine are its witnesses, got "
           f"{found.witnesses!r}")
    ensure(found.witness_count == 2, f"two witnesses are counted, got {found.witness_count}")
    ensure(not found.unbuilt, f"nothing is unbuilt, got {found.unbuilt!r}")


def _an_arrow_typed_definition_is_no_witness() -> None:
    found = gate.scan_witnesses(_CARRIER)
    ensure("not_a_witness" not in found.witnesses.get("Machine", []),
           "a definition typed `Machine -> Prop` constructs no Machine")


def _a_theorem_ranging_over_a_function_is_no_quantifier() -> None:
    text = _CARRIER + "\nLemma over_a_map : forall (f : Machine -> nat), f demo = f demo.\n" \
                      "Proof. reflexivity. Qed.\n"
    found = gate.scan_witnesses(text)
    ensure(found.quantified == {"Machine": 1},
           f"a binder over `Machine -> nat` ranges over no Machine, got {found.quantified!r}")


def _a_constructor_application_counts_as_built() -> None:
    found = gate.scan_witnesses(_BUILT_ONLY)
    ensure(found.quantified == {"Population": 1}, f"got {found.quantified!r}")
    ensure(found.witness_count == 0, "a parameterized builder is not a closed witness")
    ensure(not found.unbuilt, f"Build_Population constructs one, got {found.unbuilt!r}")


def _a_record_literal_counts_as_built() -> None:
    found = gate.scan_witnesses(_LITERAL_ONLY)
    ensure(found.quantified == {"Epoch": 1}, f"got {found.quantified!r}")
    ensure(not found.unbuilt,
           f"a literal opening with ep_sealed constructs an Epoch, got {found.unbuilt!r}")


def _a_quantified_record_nobody_builds_is_the_finding() -> None:
    found = gate.scan_witnesses(_UNBUILT)
    ensure(found.unbuilt == ["Ghost"],
           f"Ghost is quantified and never built, Seen is built, got {found.unbuilt!r}")


def _a_construction_inside_a_comment_builds_nothing() -> None:
    found = gate.scan_witnesses(_COMMENTED_BUILD)
    ensure(found.unbuilt == ["Ghost"],
           f"a commented Build_Ghost and record literal construct nothing, got {found.unbuilt!r}")


def _a_section_variable_quantifies() -> None:
    found = gate.scan_witnesses(_SECTIONED)
    ensure(found.quantified == {"Plan": 1},
           f"a Variable ranges the section's lemmas over Plan, got {found.quantified!r}")
    ensure(found.unbuilt == ["Plan"], f"and nothing builds one, got {found.unbuilt!r}")


def _a_companion_witness_inhabits_an_imported_record() -> None:
    alone = gate.scan_witnesses(_COMPANION)
    ensure(alone.quantified == {},
           f"a record no visible source declares is not held, got {alone.quantified!r}")
    together = gate.scan_witnesses(_COMPANION, (_APEX,))
    ensure(together.quantified == {"Vocabulary": 1}, f"got {together.quantified!r}")
    ensure(together.witnesses.get("Vocabulary") == ["trivial_vocabulary"],
           f"the companion's witness counts, got {together.witnesses!r}")
    ensure(not together.unbuilt, f"got {together.unbuilt!r}")


def _a_comment_is_not_read() -> None:
    text = "(* Record Phantom : Type := { f : nat }. Theorem t : forall p : Phantom, True. *)\n"
    found = gate.scan_witnesses(text + _CARRIER)
    ensure("Phantom" not in found.quantified, "a commented-out theorem quantifies nothing")


def _every_shipped_artifact_constructs_what_it_quantifies() -> None:
    sources = sorted((_ROOT / gate.PROOFS).glob("*.v"))
    ensure(bool(sources), f"no proof under {gate.PROOFS}/")
    findings: list[str] = []
    for source in sources:
        found = gate.scan_witnesses(source.read_text(encoding="utf-8"),
                                    gate._imported(source, sources))
        findings.extend(f"{source.name}: {record}" for record in found.unbuilt)
    ensure(not findings, f"a shipped artifact quantifies over a record it never builds: "
                         f"{findings!r}")


def _imports_follow_the_require_closure() -> None:
    sources = sorted((_ROOT / gate.PROOFS).glob("*.v"))
    seam = _ROOT / gate.PROOFS / "SeamWitnesses.v"
    ensure(seam in sources, "SeamWitnesses.v is a shipped artifact")
    imported = gate._imported(seam, sources)
    ensure(len(imported) == 1 and "Record Vocabulary" in imported[0],
           "SeamWitnesses reaches the apex statement and nothing else")
    ensure(gate._imported(Path(_ROOT / gate.PROOFS / "ApexTheorem.v"), sources) == (),
           "the apex statement Requires no local proof")


def cases() -> list[Case]:
    return [
        Case("carrier-quantified-and-witnessed", _carrier_is_quantified_and_witnessed),
        Case("arrow-typed-definition-is-no-witness", _an_arrow_typed_definition_is_no_witness),
        Case("function-binder-is-no-quantifier",
             _a_theorem_ranging_over_a_function_is_no_quantifier),
        Case("constructor-application-builds", _a_constructor_application_counts_as_built),
        Case("record-literal-builds", _a_record_literal_counts_as_built),
        Case("unbuilt-record-is-the-finding", _a_quantified_record_nobody_builds_is_the_finding),
        Case("section-variable-quantifies", _a_section_variable_quantifies),
        Case("companion-witness-inhabits", _a_companion_witness_inhabits_an_imported_record),
        Case("comment-is-not-read", _a_comment_is_not_read),
        Case("commented-construction-builds-nothing",
             _a_construction_inside_a_comment_builds_nothing),
        Case("shipped-artifacts-build-what-they-quantify",
             _every_shipped_artifact_constructs_what_it_quantifies),
        Case("imports-follow-require-closure", _imports_follow_the_require_closure),
    ]
