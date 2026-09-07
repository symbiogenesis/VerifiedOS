# SPDX-License-Identifier: Apache-2.0
"""The proof gate's witness half, held on the host where no Rocq switch is needed.

`run.py proofs` compiles in the guest, but what it decides about R-05-166 is a reading
of the source text: which records a file's statements quantify over, and whether the
file names a witness for each. That reading is a pure function over a string and is
held here directly, against sentences shaped like the shipped artifacts' own: a carrier
record with its named witness, a record whose only construction is a `Build_` or a
literal, a record family whose witness is ascribed at an application of it, a witness
ascribed at the wrong record, and a record inhabited by a companion the file Requires.

**Three of these cases are the change R-05-166's decidable half needed**, and they are
the ones that read as inverted against the gate's earlier reading: a `Build_` anywhere
in the text, a record literal anywhere in the text, and a closed definition that
happens to be typed at the record no longer inhabit anything, because each of the three
matched terms that were never closed inhabitants and a non-vacuity gate that
over-approximates goes false green. The last case reads the live tree: every shipped
artifact names a witness for every record it quantifies over, which is the fact the
gate's green line reports.
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
Definition witness_Machine : Machine := demo.
Example the_demo_machine_declares : demo.(unit_count) = 2 := eq_refl.
Print Assumptions every_unit_is_below_the_count.
"""

_ARROW_WITNESS = """
Record Machine : Type := { unit_count : nat }.
Definition witness_Machine : Machine -> Prop := fun _ => True.
Theorem counted : forall m : Machine, unit_count m = unit_count m.
Proof. reflexivity. Qed.
"""

_TAKES_AN_ARGUMENT = """
Record Machine : Type := { unit_count : nat }.
Definition witness_Machine (n : nat) : Machine := {| unit_count := n |}.
Theorem counted : forall m : Machine, unit_count m = unit_count m.
Proof. reflexivity. Qed.
"""

_MISASCRIBED = """
Record Ghost : Type := { haunt : nat -> bool }.
Record Seen : Type := { glimpse : nat }.
Definition witness_Ghost : Seen := {| glimpse := 1 |}.
Theorem nothing_haunts : forall g : Ghost, haunt g 0 = true -> True.
Proof. intros. exact I. Qed.
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

_UNNAMED = """
Record Machine : Type := { unit_count : nat }.
Definition demo : Machine := {| unit_count := 2 |}.
Theorem counted : forall m : Machine, unit_count m = unit_count m.
Proof. reflexivity. Qed.
"""

_FAMILY = """
Record Machine : Type := { unit_count : nat }.
Record Installed (m : Machine) : Type := { ins_seen : nat -> bool }.
Definition demo : Machine := {| unit_count := 2 |}.
Definition witness_Machine : Machine := demo.
Definition witness_Installed : Installed demo := {| ins_seen := fun _ => false |}.
Theorem installed_is_installed :
  forall (m : Machine) (st : Installed m), ins_seen m st 0 = ins_seen m st 0.
Proof. reflexivity. Qed.
"""

_UNBUILT = """
Record Ghost : Type := { haunt : nat -> bool }.
Record Seen : Type := { glimpse : nat }.
Definition witness_Seen : Seen := {| glimpse := 1 |}.
Theorem nothing_haunts : forall (g : Ghost) (s : Seen), haunt g (glimpse s) = true -> True.
Proof. intros. exact I. Qed.
"""

_COMMENTED_WITNESS = """
Record Ghost : Type := { haunt : nat -> bool }.
(* Definition witness_Ghost : Ghost := {| haunt := fun _ => true |}, commented out. *)
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
Definition witness_Vocabulary : Vocabulary := trivial_vocabulary.
"""


def _carrier_is_quantified_and_witnessed() -> None:
    found = gate.scan_witnesses(_CARRIER)
    ensure(found.quantified == {"Machine": 1},
           f"one statement ranges over Machine, got {found.quantified!r}")
    ensure(found.witnesses.get("Machine") == ["witness_Machine"],
           f"the named witness is the witness, got {found.witnesses!r}")
    ensure(found.witness_count == 1, f"one witness is counted, got {found.witness_count}")
    ensure(not found.unbuilt, f"nothing is unbuilt, got {found.unbuilt!r}")


def _an_unnamed_instance_is_no_witness() -> None:
    """The defect the named convention closed, at its smallest: `demo` inhabits Machine
    and says so to a reader, and the gate is no longer the thing deciding that."""
    found = gate.scan_witnesses(_UNNAMED)
    ensure(found.unbuilt == ["Machine"],
           f"a closed definition typed at Machine is not a claim to witness it, "
           f"got {found.unbuilt!r}")


def _an_arrow_typed_witness_is_no_witness() -> None:
    found = gate.scan_witnesses(_ARROW_WITNESS)
    ensure(found.unbuilt == ["Machine"],
           f"`witness_Machine : Machine -> Prop` constructs no Machine, "
           f"got {found.unbuilt!r}")


def _a_witness_taking_an_argument_is_no_witness() -> None:
    found = gate.scan_witnesses(_TAKES_AN_ARGUMENT)
    ensure(found.unbuilt == ["Machine"],
           f"a witness with a binder is a family and not an inhabitant, "
           f"got {found.unbuilt!r}")


def _a_misascribed_witness_witnesses_nothing() -> None:
    found = gate.scan_witnesses(_MISASCRIBED)
    ensure(found.unbuilt == ["Ghost"],
           f"`witness_Ghost : Seen` names Ghost and inhabits Seen, got {found.unbuilt!r}")
    ensure(found.witnesses == {}, f"and it witnesses neither, got {found.witnesses!r}")


def _a_theorem_ranging_over_a_function_is_no_quantifier() -> None:
    text = _CARRIER + "\nLemma over_a_map : forall (f : Machine -> nat), f demo = f demo.\n" \
                      "Proof. reflexivity. Qed.\n"
    found = gate.scan_witnesses(text)
    ensure(found.quantified == {"Machine": 1},
           f"a binder over `Machine -> nat` ranges over no Machine, got {found.quantified!r}")


def _a_constructor_application_is_no_witness() -> None:
    found = gate.scan_witnesses(_BUILT_ONLY)
    ensure(found.quantified == {"Population": 1}, f"got {found.quantified!r}")
    ensure(found.unbuilt == ["Population"],
           f"a Build_ inside a function body constructs nothing closed, "
           f"got {found.unbuilt!r}")


def _a_record_literal_is_no_witness() -> None:
    found = gate.scan_witnesses(_LITERAL_ONLY)
    ensure(found.quantified == {"Epoch": 1}, f"got {found.quantified!r}")
    ensure(found.unbuilt == ["Epoch"],
           f"a literal inside a list is not a named inhabitant, got {found.unbuilt!r}")


def _a_family_is_witnessed_at_an_application() -> None:
    found = gate.scan_witnesses(_FAMILY)
    ensure(found.quantified == {"Machine": 1, "Installed": 1},
           f"both the machine and the family it indexes, got {found.quantified!r}")
    ensure(found.witnesses.get("Installed") == ["witness_Installed"],
           f"`witness_Installed : Installed demo` witnesses the family by its head, "
           f"got {found.witnesses!r}")
    ensure(not found.unbuilt, f"got {found.unbuilt!r}")


def _a_quantified_record_with_no_witness_is_the_finding() -> None:
    found = gate.scan_witnesses(_UNBUILT)
    ensure(found.unbuilt == ["Ghost"],
           f"Ghost is quantified and unwitnessed, Seen is witnessed, got {found.unbuilt!r}")


def _a_witness_inside_a_comment_witnesses_nothing() -> None:
    found = gate.scan_witnesses(_COMMENTED_WITNESS)
    ensure(found.unbuilt == ["Ghost"],
           f"a commented-out witness_Ghost witnesses nothing, got {found.unbuilt!r}")


def _a_section_variable_quantifies() -> None:
    found = gate.scan_witnesses(_SECTIONED)
    ensure(found.quantified == {"Plan": 1},
           f"a Variable ranges the section's lemmas over Plan, got {found.quantified!r}")
    ensure(found.unbuilt == ["Plan"], f"and nothing witnesses one, got {found.unbuilt!r}")


def _a_companion_witness_inhabits_an_imported_record() -> None:
    alone = gate.scan_witnesses(_COMPANION)
    ensure(alone.quantified == {},
           f"a record no visible source declares is not held, got {alone.quantified!r}")
    together = gate.scan_witnesses(_COMPANION, (_APEX,))
    ensure(together.quantified == {"Vocabulary": 1}, f"got {together.quantified!r}")
    ensure(together.witnesses.get("Vocabulary") == ["witness_Vocabulary"],
           f"the companion's witness counts, got {together.witnesses!r}")
    ensure(not together.unbuilt, f"got {together.unbuilt!r}")


def _a_comment_is_not_read() -> None:
    text = "(* Record Phantom : Type := { f : nat }. Theorem t : forall p : Phantom, True. *)\n"
    found = gate.scan_witnesses(text + _CARRIER)
    ensure("Phantom" not in found.quantified, "a commented-out theorem quantifies nothing")


def _every_shipped_artifact_names_a_witness() -> None:
    sources = sorted((_ROOT / gate.PROOFS).glob("*.v"))
    ensure(bool(sources), f"no proof under {gate.PROOFS}/")
    findings: list[str] = []
    for source in sources:
        found = gate.scan_witnesses(source.read_text(encoding="utf-8"),
                                    gate._imported(source, sources))
        findings.extend(f"{source.name}: {record}" for record in found.unbuilt)
    ensure(not findings, f"a shipped artifact quantifies over a record it never "
                         f"witnesses: {findings!r}")


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
        Case("unnamed-instance-is-no-witness", _an_unnamed_instance_is_no_witness),
        Case("arrow-typed-witness-is-no-witness", _an_arrow_typed_witness_is_no_witness),
        Case("witness-taking-an-argument-is-no-witness",
             _a_witness_taking_an_argument_is_no_witness),
        Case("misascribed-witness-witnesses-nothing", _a_misascribed_witness_witnesses_nothing),
        Case("function-binder-is-no-quantifier",
             _a_theorem_ranging_over_a_function_is_no_quantifier),
        Case("constructor-application-is-no-witness", _a_constructor_application_is_no_witness),
        Case("record-literal-is-no-witness", _a_record_literal_is_no_witness),
        Case("family-witnessed-at-an-application", _a_family_is_witnessed_at_an_application),
        Case("unwitnessed-record-is-the-finding",
             _a_quantified_record_with_no_witness_is_the_finding),
        Case("section-variable-quantifies", _a_section_variable_quantifies),
        Case("companion-witness-inhabits", _a_companion_witness_inhabits_an_imported_record),
        Case("comment-is-not-read", _a_comment_is_not_read),
        Case("commented-witness-witnesses-nothing", _a_witness_inside_a_comment_witnesses_nothing),
        Case("shipped-artifacts-name-a-witness", _every_shipped_artifact_names_a_witness),
        Case("imports-follow-require-closure", _imports_follow_the_require_closure),
    ]
