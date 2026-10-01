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

**The compile and audit phase's schedule** is held here too, over stand-in checks: a
module starts once every module it Requires has finished and waits for no module it
does not Require, ready modules start by the chain they head, a failed prerequisite
blocks its consumers with the verdicts a wave-by-wave reading gives, each module's
start and end are logged from the phase's start, and the wave schedule's replay is a
list schedule per wave in the wave's order.
"""

import contextlib
import io
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

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

_MACHINE = "Record Machine : Type := { unit_count : nat }.\n"
_COUNTED = ("Lemma counted : forall m : Machine, unit_count m = unit_count m.\n"
            "Proof. reflexivity. Qed.\n")
_WITNESSED = "Definition witness_Machine : Machine := {| unit_count := 2 |}.\n"
# What may decorate a head: an attribute, a legacy attribute, a control flag, and a
# bullet or brace, after which the pinned Rocq 9.3.0 compiles a declaration in a proof.
_DECORATIONS = ("#[local]", "Local", "Polymorphic", "Cumulative Polymorphic",
                "#[projections(primitive)]", "Time", "Fail", "- ", "{ ", "1: {")
# Every keyword the pinned Rocq 9.3.0 states a theorem with, its grammar's `thm_token`,
# spelled here rather than read from the gate's table, and `Example`; each compiles
# under the gate's flags over a record.
_THEOREMS = ("Theorem", "Lemma", "Fact", "Remark", "Corollary", "Proposition", "Property",
             "Example")

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


def _a_decorated_record_still_demands_its_witness() -> None:
    """Missing a record removes every demand made over it, so a decoration the head
    reading could not see was fail-open, and reading through it only demands more."""
    for decoration in (*_DECORATIONS, "Program", "#[universes(polymorphic)]"):
        text = f"{decoration} {_MACHINE}{_COUNTED}"
        found = gate.scan_witnesses(text)
        ensure(found.quantified == {"Machine": 1} and found.unbuilt == ["Machine"],
               f"a record under {decoration!r} demanded no witness, got {found!r}")
        ensure(not gate.scan_witnesses(text + _WITNESSED).unbuilt,
               f"the named witness did not inhabit a record under {decoration!r}")
        structure = gate.scan_witnesses(text.replace("Record", "Structure"))
        ensure(structure.unbuilt == ["Machine"],
               f"a Structure under {decoration!r} demanded no witness, got {structure!r}")


def _a_decorated_statement_still_quantifies() -> None:
    # An attribute's quoted value may hold a bracket, which does not close the attribute,
    # or a full stop, which does not end the sentence, a line break after it or not.
    for decoration in (*_DECORATIONS, "Program", "Program Local", "Local Program",
                       '#[deprecated(since="1", note="see [x]")]',
                       '#[deprecated(since="1", note="see x. y")]',
                       '#[deprecated(since="1", note="see x.\ny")]'):
        for keyword in _THEOREMS:
            statement = _COUNTED.replace("Lemma", f"{decoration} {keyword}")
            found = gate.scan_witnesses(_MACHINE + statement)
            ensure(found.quantified == {"Machine": 1} and found.unbuilt == ["Machine"],
                   f"a {keyword} under {decoration!r} quantified nothing, got {found!r}")
    sectioned = _SECTIONED.replace("Variable", "Polymorphic Variable")
    found = gate.scan_witnesses(sectioned)
    ensure(found.quantified == {"Plan": 1} and found.unbuilt == ["Plan"],
           f"a decorated section variable quantified nothing, got {found!r}")
    found = gate.scan_witnesses(sectioned.replace("Polymorphic Variable p : Plan",
                                                  "#[local] Context (p : Plan)"))
    ensure(found.quantified == {"Plan": 1},
           f"a decorated Context quantified nothing, got {found!r}")


def _every_theorem_keyword_quantifies() -> None:
    """A statement under a keyword the definer table lacked never quantified, so its
    record's witness demand went away; a definition over the record still demands none."""
    for keyword in _THEOREMS:
        found = gate.scan_witnesses(_MACHINE + _COUNTED.replace("Lemma", keyword))
        ensure(found.quantified == {"Machine": 1} and found.unbuilt == ["Machine"],
               f"a {keyword} quantified nothing, got {found!r}")
    ensure(set(gate.STATEMENTS) <= set(gate.DEFINERS),
           "a statement keyword is missing from the definer table")
    for keyword in ("Definition", "Instance"):
        found = gate.scan_witnesses(_MACHINE + _COUNTED.replace("Lemma", keyword))
        ensure(found.quantified == {}, f"a {keyword} quantified over its binders: {found!r}")


def _a_comment_separates_a_decoration_from_its_head() -> None:
    """Rocq's lexer reads a comment as a separator, and the pinned Rocq 9.3.0 compiles
    `Local(* c *)Lemma`, so a comment with no space beside it joins nothing."""
    for decoration in ("Local(* c *)", "Time(* c *)", "Local(* a *)Program(* b *)",
                       '(* "(*" *)'):
        statement = _COUNTED.replace("Lemma", f"{decoration}Lemma")
        found = gate.scan_witnesses(_MACHINE + statement)
        ensure(found.quantified == {"Machine": 1} and found.unbuilt == ["Machine"],
               f"a statement after {decoration!r} quantified nothing, got {found!r}")
        found = gate.scan_witnesses(f"{decoration}{_MACHINE}{_COUNTED}")
        ensure(found.unbuilt == ["Machine"],
               f"a record after {decoration!r} demanded no witness, got {found!r}")
    found = gate.scan_witnesses(_SECTIONED.replace("Variable", "Polymorphic(* c *)Variable"))
    ensure(found.unbuilt == ["Plan"], f"a section variable after a comment was lost: {found!r}")


def _a_token_ending_in_two_full_stops_ends_no_statement() -> None:
    """stdpp's telescope binder `∀..` is one token to Rocq's lexer, and `..` ends no
    sentence there; the pinned Rocq 9.3.0 compiles this statement under the gate's flags
    with stdpp's telescopes imported and its scope open, so the Machine after the binder
    is quantified."""
    statement = ("Lemma counted : (∀.. (x : TeleO), True) -> forall m : Machine, "
                 "unit_count m = unit_count m.\nProof. intros _ m. reflexivity. Qed.\n")
    found = gate.scan_witnesses(_MACHINE + statement)
    ensure(found.quantified == {"Machine": 1} and found.unbuilt == ["Machine"],
           f"a statement after a telescope binder quantified nothing, got {found!r}")


def _a_tight_control_prefix_still_decorates() -> None:
    """Rocq's lexer needs no blank after a control word before `#[`, nor around a quoted
    Redirect or Profile target: the pinned Rocq 9.3.0 compiles `Time#[local]Lemma` and,
    once its output warning is silenced, `Redirect"o"Record`. So a head after one is
    read, still demands a witness, and still names none."""
    for decoration in ("Time#[local]", "Instructions#[local]", "Succeed#[local]",
                       'Redirect"o"', 'Redirect "a""b" ', 'Profile"p"', "Timeout 5"):
        statement = _COUNTED.replace("Lemma", f"{decoration}Lemma")
        found = gate.scan_witnesses(_MACHINE + statement)
        ensure(found.quantified == {"Machine": 1} and found.unbuilt == ["Machine"],
               f"a statement after {decoration!r} quantified nothing, got {found!r}")
        found = gate.scan_witnesses(f"{decoration}{_MACHINE}{_COUNTED}")
        ensure(found.unbuilt == ["Machine"],
               f"a record after {decoration!r} demanded no witness, got {found!r}")
        found = gate.scan_witnesses(_MACHINE + _COUNTED + f"{decoration}{_WITNESSED}")
        ensure(found.unbuilt == ["Machine"],
               f"a witness after {decoration!r} inhabited the record, got {found!r}")


def _a_decorated_witness_is_no_witness() -> None:
    """Reading decorated heads widens the demands and not the inhabitants: the witness
    convention names an undecorated `Definition`, `Program` aside as it always was, and
    `Fail Definition witness_Machine : Machine := tt` compiles because it inhabits nothing."""
    for decoration in (*_DECORATIONS, "Succeed", "#[program]", "Program Local"):
        text = _MACHINE + _COUNTED + f"{decoration} {_WITNESSED}"
        found = gate.scan_witnesses(text)
        ensure(found.unbuilt == ["Machine"] and found.witnesses == {},
               f"a witness under {decoration!r} was accepted, got {found!r}")
    for decoration in ("Program", "Program\n "):
        found = gate.scan_witnesses(_MACHINE + _COUNTED + f"{decoration} {_WITNESSED}")
        ensure(found.witnesses == {"Machine": ["witness_Machine"]} and not found.unbuilt,
               f"a Program witness stopped counting under {decoration!r}, got {found!r}")


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
    with patch.object(gate, "_witness_facts", wraps=gate._witness_facts) as parse:
        analysis = gate.ProofAnalysis.read(sources)
    ensure(parse.call_count == len(sources), "the proof analysis reparsed imported declarations")
    for source in sources:
        found = gate.scan_witnesses(source.read_text(encoding="utf-8"),
                                    gate._imported(source, sources))
        ensure(analysis.witnesses[source] == found,
               f"shared analysis changed witness decisions for {source.name}")
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


def _delimiter_scan_preserves_lexical_boundaries() -> None:
    fixtures = {
        "(x : nat) : Machine := demo": ("(x : nat) ", " Machine := demo"),
        "{x : nat} [y : nat] : Machine": ("{x : nat} [y : nat] ", " Machine"),
        "value := [1; 2]": None,
        "value :> Type": None,
        "value :: nil": ("value :", " nil"),
        '"literal : colon"': ('"literal ', ' colon"'),
        "(unclosed : Type": None,
        ")extra : Type": None,
        ")extra( : Type": (")extra( ", " Type"),
    }
    for text, expected in fixtures.items():
        ensure(gate._split_top(text, ":") == expected,
               f"delimiter candidate scanning changed the lexical boundary for {text!r}")
    for text, expected in (("Machine -> Prop", True), ("(Machine -> Prop)", False),
                           ("family (nat -> nat)", False), (") ->", False),
                           ('"->"', True), ("[x] -> Y", True)):
        ensure(gate._has_top_arrow(text) == expected,
               f"top-level arrow changed for {text!r}")
    ensure(gate._split_top("(x := 1) : Machine := demo", ":=")
           == ("(x := 1) : Machine ", " demo"), "a nested assignment became the body")


type _Graph = tuple[tuple[tuple[Path, ...], ...], dict[Path, frozenset[Path]], dict[str, Path]]


def _graph(folder: Path, texts: dict[str, str]) -> _Graph:
    """The waves and requirements the gate reads from these sources, and each by stem."""
    for name, text in texts.items():
        (folder / f"{name}.v").write_text(text, encoding="utf-8")
    sources = sorted(folder.glob("*.v"))
    index = gate.proofs_mod.SourceIndex.read(sources)
    return index.ordered, dict(index.needs), {source.stem: source for source in sources}


def _schedule(graph: _Graph, check: Callable[[Path], gate.Checked], jobs: int, *,
              started: float = 0.0, quiet: frozenset[Path] = frozenset(),
              by_wave: bool = False, clock: Callable[[], float] | None = None
              ) -> tuple[list[gate.Checked], dict[Path, gate.Span], str]:
    waves, needs, _ = graph
    with contextlib.redirect_stdout(io.StringIO()) as said:
        if clock is None:
            checked, spans = gate._schedule(waves, needs, check, jobs, started=started,
                                            quiet=quiet, by_wave=by_wave)
        else:
            checked, spans = gate._schedule(waves, needs, check, jobs, started=started,
                                            quiet=quiet, by_wave=by_wave, clock=clock)
    return checked, spans, said.getvalue()


def _a_module_starts_once_its_requirements_finish() -> None:
    """Consumer waits for Base alone. Slow, in Base's wave, holds its worker until
    Consumer has finished, which a wave schedule would never let happen."""
    with tempfile.TemporaryDirectory(prefix="vos-proof-schedule-") as temporary:
        graph = _graph(Path(temporary), {"Slow": "", "Base": "", "Consumer": "Require Base.",
                                         "Tail": "Require Consumer. Require Slow."})
        _, needs, _ = graph
        lock = threading.Lock()
        events: list[tuple[str, str]] = []
        consumer_done = threading.Event()
        waited: list[bool] = []

        def check(source: Path) -> gate.Checked:
            with lock:
                events.append(("start", source.stem))
            if source.stem == "Slow":
                waited.append(consumer_done.wait(timeout=5))
            with lock:
                events.append(("end", source.stem))
            if source.stem == "Consumer":
                consumer_done.set()
            return gate.Checked(source)

        checked, spans, _ = _schedule(graph, check, 2)
        ensure(waited == [True], "a ready module waited for a module it does not Require")
        ensure(sorted(item.source.stem for item in checked) == ["Base", "Consumer", "Slow", "Tail"]
               and not any(item.error for item in checked) and len(spans) == 4,
               f"every module is checked once, got {checked!r}")
        for source, required in needs.items():
            for prerequisite in required:
                ensure(events.index(("end", prerequisite.stem))
                       < events.index(("start", source.stem)),
                       f"{source.stem} started before {prerequisite.stem} finished: {events}")


def _ready_modules_start_by_the_chain_they_head() -> None:
    """Z heads the chain Z, B, C; A and M head nothing. The wave order would be A, M, Z."""
    with tempfile.TemporaryDirectory(prefix="vos-proof-priority-") as temporary:
        graph = _graph(Path(temporary), {"A": "", "M": "", "Z": "", "B": "Require Z.",
                                         "C": "Require B."})
        started: list[str] = []

        def check(source: Path) -> gate.Checked:
            started.append(source.stem)
            return gate.Checked(source)

        _schedule(graph, check, 1)
        ensure(started == ["Z", "B", "A", "M", "C"],
               f"ready modules started out of chain, wave and name order: {started}")


def _wave_reading(graph: _Graph, failing: set[str]) -> dict[str, str]:
    """The verdicts the wave schedule gave: each wave in turn, a module with a failed or
    blocked requirement blocked by name, every other module checked."""
    waves, needs, _ = graph
    failed: set[str] = set()
    verdicts: dict[str, str] = {}
    for wave in waves:
        for source in wave:
            blocked = {required.stem for required in needs[source]} & failed
            verdicts[source.stem] = ("blocked by failed dependencies: " + ", ".join(sorted(blocked))
                                     if blocked else "seeded failure" if source.stem in failing
                                     else "")
            if verdicts[source.stem]:
                failed.add(source.stem)
    return verdicts


def _a_failed_prerequisite_blocks_its_consumers() -> None:
    """Under Requires alone and under `by_wave`, which a wrapped Require selects."""
    texts = {"Base": "", "Other": "", "Consumer": "Require Base.", "Deep": "Require Consumer.",
             "Mixed": "Require Base. Require Other.", "Fine": "Require Other."}
    for failing in (set(), {"Base"}, {"Base", "Other"}, {"Deep"}, {"Consumer"}):
        for by_wave in (False, True):
            with tempfile.TemporaryDirectory(prefix="vos-proof-blocked-") as temporary:
                graph = _graph(Path(temporary), texts)
                for name in texts:
                    (Path(temporary) / f"{name}.vo").write_bytes(b"previous run")
                lock = threading.Lock()
                called: list[str] = []

                def check(source: Path, failing: set[str] = failing, called: list[str] = called,
                          lock: threading.Lock = lock) -> gate.Checked:
                    with lock:
                        called.append(source.stem)
                    return gate.Checked(
                        source, error="seeded failure" if source.stem in failing else "")

                checked, spans, _ = _schedule(graph, check, 2, by_wave=by_wave)
                case = f"failing {failing}, by_wave {by_wave}"
                expected = _wave_reading(graph, failing)
                verdicts = {item.source.stem: item.error for item in checked}
                ensure(verdicts == expected and len(checked) == len(texts),
                       f"{case}: verdicts {verdicts} differ from the wave schedule's {expected}")
                blocked = {stem for stem, error in expected.items() if error.startswith("blocked")}
                ensure(sorted(called) == sorted(set(texts) - blocked)
                       and {source.stem for source in spans} == set(texts) - blocked,
                       f"{case}: a blocked module was checked, or a ready one was not: {called}")
                stale = sorted(stem for stem in blocked
                               if (Path(temporary) / f"{stem}.vo").exists())
                ensure(not stale, f"{case}: blocked modules kept stale objects: {stale}")


def _each_module_logs_its_start_and_end() -> None:
    """With one worker and a clock each check advances by its module's seconds, the
    lines and spans are exact: A from 0.5 s, R reused and silent, then B."""
    with tempfile.TemporaryDirectory(prefix="vos-proof-spans-") as temporary:
        graph = _graph(Path(temporary), {"A": "", "R": "", "B": "Require A."})
        _, _, by_stem = graph
        now = [100.0]
        seconds = {"A": 2.0, "R": 0.0, "B": 0.25}

        def check(source: Path) -> gate.Checked:
            now[0] += seconds[source.stem]
            return gate.Checked(source)

        _, spans, said = _schedule(graph, check, 1, started=99.5,
                                   quiet=frozenset({by_stem["R"]}), clock=lambda: now[0])
        ensure(said.splitlines() == ["  compile/audit A.v: 0.50s to 2.50s",
                                     "  compile/audit B.v: 2.50s to 2.75s"],
               f"wrong per-module timing lines: {said!r}")
        ensure({source.stem: (span.start, span.end) for source, span in spans.items()}
               == {"A": (0.5, 2.5), "R": (2.5, 2.5), "B": (2.5, 2.75)},
               f"wrong per-module spans: {spans!r}")


def _the_wave_makespan_replays_each_wave_in_order() -> None:
    samples: tuple[tuple[list[list[float]], int, float], ...] = (
        ([[3, 1, 1, 1], [2]], 2, 5.0), ([[3, 1, 1, 1], [2]], 1, 8.0),
        ([[3, 1, 1, 1], [2]], 8, 5.0),
        # The queue hands the third member to the first worker free, not to the
        # packing that would finish at 3.
        ([[1, 1, 3]], 2, 4.0), ([[2, 0, 0]], 2, 2.0), ([], 3, 0.0), ([[]], 3, 0.0))
    for waves, jobs, expected in samples:
        found = gate.wave_makespan(waves, jobs)
        ensure(found == expected, f"wave_makespan({waves}, {jobs}) is {found}, not {expected}")
    for waves, jobs in (([[1.0]], 0), ([[1.0, -0.5]], 2)):
        try:
            gate.wave_makespan(waves, jobs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"wave_makespan({waves}, {jobs}) replayed an impossible schedule")


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
        Case("decorated-record-demands-a-witness", _a_decorated_record_still_demands_its_witness),
        Case("decorated-statement-quantifies", _a_decorated_statement_still_quantifies),
        Case("every-theorem-keyword-quantifies", _every_theorem_keyword_quantifies),
        Case("comment-separates-decoration-from-head",
             _a_comment_separates_a_decoration_from_its_head),
        Case("tight-control-prefix-still-decorates", _a_tight_control_prefix_still_decorates),
        Case("two-full-stops-end-no-statement",
             _a_token_ending_in_two_full_stops_ends_no_statement),
        Case("decorated-witness-is-no-witness", _a_decorated_witness_is_no_witness),
        Case("companion-witness-inhabits", _a_companion_witness_inhabits_an_imported_record),
        Case("comment-is-not-read", _a_comment_is_not_read),
        Case("commented-witness-witnesses-nothing", _a_witness_inside_a_comment_witnesses_nothing),
        Case("shipped-artifacts-name-a-witness", _every_shipped_artifact_names_a_witness),
        Case("imports-follow-require-closure", _imports_follow_the_require_closure),
        Case("delimiter-scan-preserves-lexical-boundaries", _delimiter_scan_preserves_lexical_boundaries),
        Case("module-starts-once-its-requirements-finish",
             _a_module_starts_once_its_requirements_finish),
        Case("ready-modules-start-by-the-chain-they-head",
             _ready_modules_start_by_the_chain_they_head),
        Case("failed-prerequisite-blocks-its-consumers",
             _a_failed_prerequisite_blocks_its_consumers),
        Case("each-module-logs-its-start-and-end", _each_module_logs_its_start_and_end),
        Case("wave-makespan-replays-each-wave-in-order",
             _the_wave_makespan_replays_each_wave_in_order),
    ]
