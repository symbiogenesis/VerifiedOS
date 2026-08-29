(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   DischargeSequence.v

   The RoT discharge and admission sequence, as the register fixes it:
   R-15-247d's ordered authority invalidation before residue sanitization,
   R-15-247e's drain through the cells' own write devices, R-15-247f's
   fixed worst-corner dwell followed by a single fail-stop completion read
   with no poll and no retry, R-15-247q's relocation of the discharge to
   the mode-exit path, R-15-247h's requesters held in reset, and R-15-198's
   sequence table, which R-15-247d rides rather than standing beside.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity the register
   leaves to composition or to a measurement is a field of the Machine
   record rather than a literal or a top-level Parameter, which is what
   keeps the R-05-163 assumption gate green while leaving the decision
   where its owner can make it. Nothing is admitted and nothing is
   axiomatized: the Print Assumptions block at the end reports every
   shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere.
   The computed checks are decided inside the kernel by conversion and
   print nothing.

   What is deferred, and to which item. R-15-247f states two acceptance
   clauses. The first, that no path admits a partially sanitized bank
   (R-15-247d), is stated and refuted here. The second, that no timing on
   either the success or the timeout path varies with discharge speed, is
   not stated here at all: it quantifies over a discharge speed, which is a
   measured magnitude R-15-247m puts on a repaired megabit-class macro and
   which no artifact in this repository carries, so there is nothing to
   vary it against. That clause is checklist item M3.6b, and nothing below
   introduces a speed, a rate, or a leakage-derived quantity that would
   stand in for one. What is stated of the dwell here is step 3's shape
   alone: the dwell term is the machine's declared composition constant
   (R-15-247g's mode-transition dwell constant) rather than a function of
   what the sweep found. The whole-path invariance is M3.6b's.

   No Require. Nothing beyond the Coq prelude is reachable, so Classical
   and FunctionalExtensionality are unavailable and every state equality
   below is stated pointwise for that reason. A Require naming a sibling
   artifact would be admissible, and there is none to name. PartitionContext
   .v's switch_cost is R-15-220's partition-switch constant, which R-11-009
   puts inside R-11-006's interval arithmetic, where this file's dwell is
   R-15-247g's mode-transition constant entering the R-15-189i transition
   budget. The two budgets do not meet, so a Require here would be a
   citation rather than a dependency, which is the thing CyclicExecutive.v's
   own Require is not.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. The ordered sequence is one order across two paths. R-15-247d fixes
      "tag discharge confirmed, then requester addressability, then data
      sanitization confirmed, then measured execution", and R-15-247q puts
      the discharge on the exit path rather than the next entry. So the
      first four phases below sit on the path a domain leaves a mode by and
      the last three on the path it is admitted by, and the order spans the
      power transition between them. That is also what R-15-189j reads from
      the other side when it says what a bulk domain owes on the way in is
      the confirmation R-15-247d orders and not a regeneration sweep.
   2. The fail-stop is an arm of the read and not a phase of the success
      path. R-15-247f's fail-closed line stops the transition rather than
      repeating it, so the sequencer is a function of the single reading:
      on the positive reading it continues to addressability, and on the
      negative one it reaches the arm and stops. Modelling it as a function
      of that one boolean is what lets both paths be stated at once and
      what makes a sequencer that admits on a negative reading exhibitable
      rather than merely different.
   3. The unit of the discharge is the bank and the unit of a bank's sweep
      is the interface's write. R-15-247e realizes the drain through the
      cells' existing write devices, R-15-247p makes banks whole-bound and
      composition-fixed, and R-15-247b makes data, tag validity and both
      ECC planes commit atomically at the granule, a write that does not
      commit being a fail-stop sentinel event rather than a half-written
      granule. So a sweep here is a per-bank, per-chunk record of what
      committed, a bank is drained when every chunk of it committed, and a
      bank is partially sanitized when some chunk committed and some did
      not.
   4. The completion read is stated as an arbitrary Reader over that sweep.
      R-15-247f states a single read of a fail-stop completion indication
      and does not state the indication's arity against R-15-247g's bank
      staggering, so the reader is a parameter, the specification's reader
      is the one that answers for every bank, and a per-domain reader is
      exhibited and refuted rather than assumed away.
   5. Requesters are a list and the hold is a predicate over it.
      R-15-247h names three classes held in reset, every application core,
      every DMA engine, and every capability-bearing fabric initiator, and
      does not say whether the hold is die-wide or scoped to the
      discharging domain's requesters. Which list `requesters` names is
      therefore the register's to say and not this file's, and the
      obligation is stated over whatever it names.
   6. The order is stated over positions rather than over a rank function
      built into the sequence's shape, so a sequence out of order is
      expressible and the theorems have something to exclude. `precedes`
      is false where either phase is absent, which is what makes a deletion
      a refusal rather than a silence.
   7. Boolean rather than propositional wherever the witnesses must
      compute: the order check, the read count, and the bank predicates are
      decidable, so the generated weakening families below are checked by
      conversion in the silent Example form rather than by a proof per
      member.

   The literals taken from the design, and there are three. R-15-247d's
   Accept clause fixes the phase order, so `admission_sequence` is that
   order written out and is this file's one structural literal. R-15-247f
   fixes the completion read at one, so `single_read_ok` compares against
   1. And R-15-247f fixes the retry count at zero, so
   `NeverRepeatsTheDischarge` compares against 1 occurrence of the
   discharge on either arm. Every other magnitude is a field: the dwell
   length, because R-15-247m measures it on a repaired macro and R-15-247g
   folds it into the transition budget; the bank set, because R-15-247p
   puts the per-class bank count in R-15-014a's frozen parameter set; the
   chunk decomposition of a bank, because R-15-247e makes the drain the
   interface's own write and the chunk width is that interface's; and the
   requester roster, per reading 5.

   How the refutations are generated. A refutation is a seeded weakening
   the theorem must reject, so four generators produce families of them
   mechanically rather than a person authoring each. Over the
   specification's own sequence: `swap_at` transposes an adjacent pair and
   yields one weakening per adjacent position; `drop_at` deletes a phase
   and yields one per position; `suffix_at` re-enters the table at a proper
   suffix, which is R-15-198's own phrase for what a wake and a standby
   exit are, and yields one per position; and `insert_at CompletionRead`
   adds a second read and yields one per position. The four families are 28
   weakenings, every one refused, checked as one conversion. Beside them
   the generic theorems quantify over the index rather than enumerating,
   and the early-release family quantifies over the phase rather than over
   an index at all. The hand-authored refutations below are the ones no
   index generates, being alternative constructions rather than mutations
   of a list.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. Whether the data plane's sanitization carries its own dwell and its
      own single read. R-15-247d states the data plane is "deterministically
      cleared or its discharge confirmed", a disjunction with no arm
      selected, while R-15-247b commits both planes atomically at the
      granule, which one pass would satisfy, and R-17-024a insists the two
      are "two boundaries and not one". The §11 mode-transition budget
      reads one dwell on one arm and two on the other. Owed at R-15-247d or
      R-15-247f. Nothing below decides it: DataSanitization is one phase
      whose internal shape is unstated.
   b. The completion indication's arity against the bank staggering.
      R-15-247f says a single read; R-15-247g stages the discharge in
      phases over banks. One read per transition, one per phase, and one
      per bank are three different §11 terms and three different degrees of
      partiality visibility, and no entry chooses.
      `the_reader_arity_is_observable` machine-checks that the choice is
      not free. Owed at R-15-247f or R-15-247g.
   c. Whether R-15-247h's reset hold is die-wide or scoped to the
      discharging domain. R-15-190 keeps exactly one island live across
      standby with R-15-192 running a paging hard task on it, and R-15-190a
      admits a bulk domain taken OFF at that transition, so a die-wide hold
      and that hard task cannot both hold as written. Owed at R-15-247h.
      Reading 5 is how this file declines to choose.
   d. Where the fail-stop latch lives. R-15-247f and R-15-189n both latch
      on a negative reading and neither says in which power domain the
      latch sits, which matters because R-15-247q puts the discharge on the
      path that collapses the rail. Owed at R-15-247f. The sequencer here
      carries the arm and not the latch's location.
   e. Every composition magnitude. The dwell, the bank set, the chunk
      decomposition and the requester roster are fields; the demo machine
      at the end instantiates them with arbitrary witness values that carry
      no composition claim.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary sequencer, reader, dwell length, reset hold or
   release schedule, proved of the specification, and refuted of an
   alternative construction the register's own sentence excludes.
   Inhabitation is concrete: a demo machine whose every domain is
   inhabited, a sweep on which the specification's reader confirms, and a
   sweep on which it refuses, so no theorem is proved from a premise
   nothing satisfies and none from one everything satisfies.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   The machine: everything the register leaves to composition or to a
   measurement. Fields rather than Parameters, because a top-level
   Parameter prints as an assumption and fails the R-05-163 gate.
   ------------------------------------------------------------------------- *)

Record Machine : Type := {

  (* --- R-15-247h's requester classes, held in reset while the sequencer
         runs; whether the roster is die-wide or the domain's is the
         register's to say (reading 5, gap c) ----------------------------- *)

  Requester : Type;
  requesters : list Requester;

  (* --- R-15-247p's banks: composition-fixed, whole-bound to islands, and
         never varying with occupancy or load, so the set is read out of
         the composition rather than counted at run time ------------------ *)

  Bank : Type;
  banks : list Bank;

  (* --- the unit the drain is issued in. R-15-247e realizes discharge
         through the cells' existing write devices, so a bank's sweep is a
         run of ordinary writes and the chunk width is the memory
         interface's business rather than this file's ---------------------- *)

  Chunk : Type;
  chunks_of : Bank -> list Chunk;

  (* --- R-15-247f's fixed worst-corner dwell, entering §11 as R-15-247g's
         mode-transition dwell constant. The magnitude is R-15-247m's,
         measured on a repaired megabit-class macro, so it is a field and
         no number here ---------------------------------------------------- *)

  dwell_cycles : nat
}.

(* -------------------------------------------------------------------------
   List helpers, defined here rather than imported: the prelude carries the
   list type and not the library over it, and importing a module to save a
   dozen lines would put its assumptions inside the R-05-163 gate's reach
   for no gain.
   ------------------------------------------------------------------------- *)

Fixpoint all_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => true
  | cons x r => andb (p x) (all_of p r)
  end.

Fixpoint any_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => false
  | cons x r => orb (p x) (any_of p r)
  end.

Fixpoint count_of {A : Type} (l : list A) : nat :=
  match l with nil => 0 | cons _ r => S (count_of r) end.

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

(* 0 through n-1, in that order: the index set the generators below range
   over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma all_of_mono :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    all_of p l = true -> all_of q l = true.
Proof.
  intros A p q l Himp. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split (p x) (all_of p r) H) as [ Hx Hr ].
    simpl. apply andb_join.
    + exact (Himp x Hx).
    + exact (IH Hr).
Qed.

Lemma all_of_true : forall (A : Type) (l : list A), all_of (fun _ => true) l = true.
Proof.
  intros A l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. exact IH.
Qed.

(* =========================================================================
   The phases, and the order R-15-247d fixes over them.
   ========================================================================= *)

(* Exactly the steps R-15-247d's Accept clause and R-15-247f name, and no
   others. This is a list of what the sequence does and not an inventory of
   platform events: the fail-stop arm is here because R-15-247f's
   fail-closed line makes it a destination of the read, and nothing else
   about the R-17-030n detector class is. *)
Inductive Phase : Type :=
| RequestersInReset      (* R-15-247h: cores, DMA engines, fabric initiators *)
| TagPlaneDischarge      (* R-15-247e, taken at mode exit per R-15-247q      *)
| WorstCornerDwell       (* R-15-247f's fixed dwell, R-15-247g's constant    *)
| CompletionRead         (* R-15-247f's one read of the indication           *)
| FailStopArm            (* R-15-247f fail-closed, R-17-030n                 *)
| DomainAddressable      (* R-15-247d: a requester may now name the domain   *)
| DataSanitization       (* R-15-247d's separately admitted second boundary  *)
| MeasuredExecution.     (* R-15-247d: what the second boundary precedes     *)

Definition phase_eqb (p q : Phase) : bool :=
  match p, q with
  | RequestersInReset, RequestersInReset => true
  | TagPlaneDischarge, TagPlaneDischarge => true
  | WorstCornerDwell, WorstCornerDwell => true
  | CompletionRead, CompletionRead => true
  | FailStopArm, FailStopArm => true
  | DomainAddressable, DomainAddressable => true
  | DataSanitization, DataSanitization => true
  | MeasuredExecution, MeasuredExecution => true
  | _, _ => false
  end.

Lemma phase_eqb_refl : forall p : Phase, phase_eqb p p = true.
Proof. intros p. destruct p; reflexivity. Qed.

Lemma phase_eqb_true : forall p q : Phase, phase_eqb p q = true -> p = q.
Proof.
  intros p q. destruct p; destruct q; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition all_phases : list Phase :=
  cons RequestersInReset (cons TagPlaneDischarge (cons WorstCornerDwell
  (cons CompletionRead (cons FailStopArm (cons DomainAddressable
  (cons DataSanitization (cons MeasuredExecution nil))))))).

(* Where a phase first stands, and how often it stands anywhere. The first
   occurrence is what an order reads and the count is what a retry moves,
   which is why the two obligations below are separate and why one
   construction can satisfy either and fail the other. *)
Fixpoint pos_from (p : Phase) (l : list Phase) (i : nat) : option nat :=
  match l with
  | nil => None
  | cons q r => if phase_eqb p q then Some i else pos_from p r (S i)
  end.

Definition pos (p : Phase) (l : list Phase) : option nat := pos_from p l 0.

Definition occurs (p : Phase) (l : list Phase) : bool :=
  match pos p l with Some _ => true | None => false end.

Fixpoint occurrences (p : Phase) (l : list Phase) : nat :=
  match l with
  | nil => 0
  | cons q r => if phase_eqb p q then S (occurrences p r) else occurrences p r
  end.

(* False where either phase is absent, which is what makes a deletion a
   refusal rather than a silence (reading 6). *)
Definition precedes (p q : Phase) (l : list Phase) : bool :=
  match pos p l, pos q l with
  | Some i, Some j => Nat.ltb i j
  | _, _ => false
  end.

(* -------------------------------------------------------------------------
   The specification. The first four phases sit on the exit path R-15-247q
   relocates the discharge to; the reading decides which of the two arms
   follows, and the last three sit on the entry path (reading 1).
   ------------------------------------------------------------------------- *)

Definition admission_sequence (confirmed : bool) : list Phase :=
  cons RequestersInReset
  (cons TagPlaneDischarge
  (cons WorstCornerDwell
  (cons CompletionRead
    (if confirmed
     then cons DomainAddressable (cons DataSanitization (cons MeasuredExecution nil))
     else cons FailStopArm nil)))).

(* R-15-247d's order, as six precedences read off its Accept clause and
   R-15-247f's sentence, and as the boolean the generated families are
   checked against. *)
Definition ordered_ok (l : list Phase) : bool :=
  andb (precedes RequestersInReset TagPlaneDischarge l)
  (andb (precedes TagPlaneDischarge WorstCornerDwell l)
  (andb (precedes WorstCornerDwell CompletionRead l)
  (andb (precedes CompletionRead DomainAddressable l)
  (andb (precedes DomainAddressable DataSanitization l)
        (precedes DataSanitization MeasuredExecution l))))).

Definition Ordered (l : list Phase) : Prop :=
  precedes RequestersInReset TagPlaneDischarge l = true
  /\ precedes TagPlaneDischarge WorstCornerDwell l = true
  /\ precedes WorstCornerDwell CompletionRead l = true
  /\ precedes CompletionRead DomainAddressable l = true
  /\ precedes DomainAddressable DataSanitization l = true
  /\ precedes DataSanitization MeasuredExecution l = true.

Lemma ordered_ok_sound : forall l : list Phase, ordered_ok l = true -> Ordered l.
Proof.
  intros l H. unfold ordered_ok in H.
  destruct (andb_split _ _ H) as [ H1 R1 ].
  destruct (andb_split _ _ R1) as [ H2 R2 ].
  destruct (andb_split _ _ R2) as [ H3 R3 ].
  destruct (andb_split _ _ R3) as [ H4 R4 ].
  destruct (andb_split _ _ R4) as [ H5 H6 ].
  exact (conj H1 (conj H2 (conj H3 (conj H4 (conj H5 H6))))).
Qed.

Lemma ordered_ok_complete : forall l : list Phase, Ordered l -> ordered_ok l = true.
Proof.
  intros l [ H1 [ H2 [ H3 [ H4 [ H5 H6 ] ] ] ] ]. unfold ordered_ok.
  apply andb_join; [ exact H1 | ].
  apply andb_join; [ exact H2 | ].
  apply andb_join; [ exact H3 | ].
  apply andb_join; [ exact H4 | ].
  apply andb_join; [ exact H5 | exact H6 ].
Qed.

(* D1 (R-15-247d). *)
Theorem specification_is_ordered : Ordered (admission_sequence true).
Proof. apply ordered_ok_sound. reflexivity. Qed.

(* D1a (R-15-247d, R-17-024a, R-17-058f): the two boundaries are separated
   by name rather than reconciled. The authority boundary is reached, or
   refused, without the residue boundary being reached at all, which is
   what "precedes and is independent of" asks of the pair; the second half
   is the fail-stop arm read at this question. *)
Theorem authority_invalidation_is_independent_of_residue_sanitization :
  precedes CompletionRead DataSanitization (admission_sequence true) = true
  /\ occurs DataSanitization (admission_sequence false) = false
  /\ occurs CompletionRead (admission_sequence false) = true.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* =========================================================================
   The generated weakenings (R-05-166). A refutation is a seeded weakening
   the theorem must reject, so these four generators produce families of
   them from the specification's own sequence rather than a person
   authoring each. The theorems quantify over the index; the Examples check
   the whole family by conversion and print nothing.
   ========================================================================= *)

(* Transpose the adjacent pair at n: the natural wrong move on an ordered
   sequence, and one weakening per adjacent position. *)
Fixpoint swap_at (n : nat) (l : list Phase) : list Phase :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

(* Delete the phase at n: a step omitted rather than reordered. *)
Fixpoint drop_at (n : nat) (l : list Phase) : list Phase :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

(* Re-enter the table at the suffix beginning at n. R-15-198's Accept makes
   mode transitions, standby entry and exit, and deep-sleep wake
   "re-entries into suffixes of the same table", and R-15-247d requires its
   order on every one of those, so a suffix is the weakening that phrase
   invites and the family below is what refuses it. *)
Fixpoint suffix_at (n : nat) (l : list Phase) : list Phase :=
  match n, l with
  | 0, _ => l
  | S k, cons _ r => suffix_at k r
  | S _, nil => nil
  end.

(* Insert a phase at n: with CompletionRead, the poll-until-done loop and
   the retry R-15-247f refuses, one weakening per position. *)
Fixpoint insert_at (n : nat) (p : Phase) (l : list Phase) : list Phase :=
  match n, l with
  | 0, _ => cons p l
  | S k, cons a r => cons a (insert_at k p r)
  | S _, nil => cons p nil
  end.

(* R-15-247f's literal: one read. *)
Definition single_read_ok (l : list Phase) : bool :=
  Nat.eqb (occurrences CompletionRead l) 1.

Definition transpositions (l : list Phase) : list (list Phase) :=
  map_over (fun n => swap_at n l) (upto (before_last (count_of l))).

Definition deletions (l : list Phase) : list (list Phase) :=
  map_over (fun n => drop_at n l) (upto (count_of l)).

Definition proper_suffixes (l : list Phase) : list (list Phase) :=
  map_over (fun n => suffix_at (S n) l) (upto (count_of l)).

Definition extra_reads (l : list Phase) : list (list Phase) :=
  map_over (fun n => insert_at n CompletionRead l) (upto (S (count_of l))).

Definition generated_weakenings (l : list Phase) : list (list Phase) :=
  app (transpositions l)
      (app (deletions l) (app (proper_suffixes l) (extra_reads l))).

(* The family's size is computed rather than claimed: six transpositions,
   seven deletions, seven proper suffixes, and eight extra reads. *)
Example generated_family_size :
  count_of (generated_weakenings (admission_sequence true)) = 28 := eq_refl.

(* D2: every generated weakening fails the order or the single read. One
   conversion over the whole family. *)
Example every_generated_weakening_is_refused :
  all_of (fun w => negb (andb (ordered_ok w) (single_read_ok w)))
         (generated_weakenings (admission_sequence true)) = true := eq_refl.

(* D2a: and per family, so a family that stopped biting is visible rather
   than absorbed by the conjunction above. *)
Example every_transposition_is_out_of_order :
  all_of (fun w => negb (ordered_ok w))
         (transpositions (admission_sequence true)) = true := eq_refl.

Example every_deletion_is_out_of_order :
  all_of (fun w => negb (ordered_ok w))
         (deletions (admission_sequence true)) = true := eq_refl.

Example every_proper_suffix_is_out_of_order :
  all_of (fun w => negb (ordered_ok w))
         (proper_suffixes (admission_sequence true)) = true := eq_refl.

Example every_extra_read_is_not_a_single_read :
  all_of (fun w => negb (single_read_ok w))
         (extra_reads (admission_sequence true)) = true := eq_refl.

(* D2b: the same content as a quantifier over the index rather than an
   enumeration, so the family is refused for a reason rather than by a
   computation over the six, seven and eight members it happens to have. *)
Theorem no_adjacent_transposition_is_ordered :
  forall n : nat, Nat.ltb n 6 = true ->
    ordered_ok (swap_at n (admission_sequence true)) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_deletion_is_ordered :
  forall n : nat, Nat.ltb n 7 = true ->
    ordered_ok (drop_at n (admission_sequence true)) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_proper_suffix_is_ordered :
  forall n : nat, Nat.ltb n 7 = true ->
    ordered_ok (suffix_at (S n) (admission_sequence true)) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_extra_read_is_a_single_read :
  forall n : nat, Nat.ltb n 8 = true ->
    single_read_ok (insert_at n CompletionRead (admission_sequence true)) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* -------------------------------------------------------------------------
   No conjunct of the order is dead. M0.16's finding is that a validator
   arm placed after another inherits what that one already refuses, so a
   message it repeats is unreachable rather than redundant; the same defect
   in a conjunction is a clause that decides nothing. Each of the six
   adjacent transpositions breaks exactly one conjunct, which is that
   property computed rather than asserted.
   ------------------------------------------------------------------------- *)

Definition failing_conjuncts (l : list Phase) : nat :=
  (if precedes RequestersInReset TagPlaneDischarge l then 0 else 1)
  + (if precedes TagPlaneDischarge WorstCornerDwell l then 0 else 1)
  + (if precedes WorstCornerDwell CompletionRead l then 0 else 1)
  + (if precedes CompletionRead DomainAddressable l then 0 else 1)
  + (if precedes DomainAddressable DataSanitization l then 0 else 1)
  + (if precedes DataSanitization MeasuredExecution l then 0 else 1).

Example each_conjunct_of_the_order_decides :
  map_over failing_conjuncts (transpositions (admission_sequence true))
  = cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 nil))))) := eq_refl.

(* And the specification breaks none of them, so the count above is a
   measure of the weakening rather than of the check. *)
Example the_specification_breaks_no_conjunct :
  failing_conjuncts (admission_sequence true) = 0 := eq_refl.

(* =========================================================================
   The sequencer: a function of the single reading (reading 2). The
   obligations are stated of an arbitrary one, so an alternative
   construction can be exhibited and refuted rather than merely differing
   from the specification.
   ========================================================================= *)

Definition Sequencer : Type := bool -> list Phase.

Definition spec_sequencer : Sequencer := admission_sequence.

(* R-15-247d, on both arms. *)
Definition KeepsTheOrder (q : Sequencer) : Prop :=
  Ordered (q true).

(* R-15-247f fail-closed, and R-15-247d's "before any requester may name
   the domain": on a negative reading the domain is never addressable, is
   never sanitized, and never enters measured execution. *)
Definition StopsOnNegativeReading (q : Sequencer) : Prop :=
  occurs DomainAddressable (q false) = false
  /\ occurs DataSanitization (q false) = false
  /\ occurs MeasuredExecution (q false) = false.

(* R-17-030n: the negative reading reaches the arm, and the positive one
   does not. Both halves, because a sequencer that latches on every reading
   satisfies the first alone and is not a fail-stop. *)
Definition LatchesOnNegativeReading (q : Sequencer) : Prop :=
  occurs FailStopArm (q false) = true /\ occurs FailStopArm (q true) = false.

(* R-15-247f's "a single read", the file's second literal. *)
Definition ReadsOnce (q : Sequencer) : Prop :=
  forall b : bool, occurrences CompletionRead (q b) = 1.

(* R-15-247f's "no retry", the file's third: the negative reading stops the
   transition rather than repeating it, so the discharge stands once on
   either arm. *)
Definition NeverRepeatsTheDischarge (q : Sequencer) : Prop :=
  forall b : bool, occurrences TagPlaneDischarge (q b) = 1.

(* R-15-247f's "a fixed worst-corner dwell followed by a single read", as
   an order on both arms. *)
Definition ReadFollowsTheDwell (q : Sequencer) : Prop :=
  forall b : bool, precedes WorstCornerDwell CompletionRead (q b) = true.

(* D3 through D7: the specification meets all five. *)
Theorem specification_keeps_the_order : KeepsTheOrder spec_sequencer.
Proof. exact specification_is_ordered. Qed.

Theorem specification_stops_on_a_negative_reading :
  StopsOnNegativeReading spec_sequencer.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Theorem specification_latches_on_a_negative_reading :
  LatchesOnNegativeReading spec_sequencer.
Proof. split; reflexivity. Qed.

Theorem specification_reads_once : ReadsOnce spec_sequencer.
Proof. intros b. destruct b; reflexivity. Qed.

Theorem specification_never_repeats_the_discharge :
  NeverRepeatsTheDischarge spec_sequencer.
Proof. intros b. destruct b; reflexivity. Qed.

Theorem specification_reads_after_the_dwell : ReadFollowsTheDwell spec_sequencer.
Proof. intros b. destruct b; reflexivity. Qed.

(* =========================================================================
   Refutation witnesses over the sequencer (R-05-166). Each is an
   alternative construction the register's own sentence excludes, and each
   is shown to satisfy the obligations it does not break, so what refutes
   it is the named defect rather than the shape of the construction.
   ========================================================================= *)

(* A sequence that reads completion before the dwell has elapsed.
   R-15-247f puts the read after a fixed worst-corner dwell, so this one
   reads an indication whose settling the dwell exists to guarantee. *)
Definition eager_read_sequencer : Sequencer := fun confirmed =>
  cons RequestersInReset
  (cons TagPlaneDischarge
  (cons CompletionRead
  (cons WorstCornerDwell
    (if confirmed
     then cons DomainAddressable (cons DataSanitization (cons MeasuredExecution nil))
     else cons FailStopArm nil)))).

Theorem eager_read_refutes_the_dwell_order :
  ~ ReadFollowsTheDwell eager_read_sequencer.
Proof. intros H. specialize (H true). discriminate H. Qed.

(* And it reads exactly once, so what refutes it is the position of the
   read and not its count: the two obligations are independent. *)
Theorem eager_read_still_reads_once : ReadsOnce eager_read_sequencer.
Proof. intros b. destruct b; reflexivity. Qed.

(* A sequence that polls rather than reading once. R-15-247f admits no
   poll-until-done loop; its Accept clause says why, a poll making
   transition time a function of temperature, charge state, and what the
   bank held. *)
Definition polling_sequencer : Sequencer := fun confirmed =>
  cons RequestersInReset
  (cons TagPlaneDischarge
  (cons WorstCornerDwell
  (cons CompletionRead
  (cons CompletionRead
  (cons CompletionRead
    (if confirmed
     then cons DomainAddressable (cons DataSanitization (cons MeasuredExecution nil))
     else cons FailStopArm nil)))))).

Theorem polling_refutes_the_single_read : ~ ReadsOnce polling_sequencer.
Proof. intros H. specialize (H true). discriminate H. Qed.

(* The poll keeps the order and reads after the dwell, so the order alone
   does not carry R-15-247f's single-read rule and the count is doing work
   the position cannot do. *)
Theorem polling_still_keeps_the_order_and_reads_after_the_dwell :
  KeepsTheOrder polling_sequencer /\ ReadFollowsTheDwell polling_sequencer.
Proof.
  split.
  - apply ordered_ok_sound. reflexivity.
  - intros b. destruct b; reflexivity.
Qed.

(* A sequence that retries: on a negative reading it discharges again,
   dwells again, reads again, and admits. R-15-247f's fail-closed line
   stops the transition rather than repeating it. *)
Definition retrying_sequencer : Sequencer := fun confirmed =>
  if confirmed
  then admission_sequence true
  else
    cons RequestersInReset
    (cons TagPlaneDischarge
    (cons WorstCornerDwell
    (cons CompletionRead
    (cons TagPlaneDischarge
    (cons WorstCornerDwell
    (cons CompletionRead
    (cons DomainAddressable
    (cons DataSanitization (cons MeasuredExecution nil))))))))).

Theorem retrying_refutes_the_no_retry_rule :
  ~ NeverRepeatsTheDischarge retrying_sequencer.
Proof. intros H. specialize (H false). discriminate H. Qed.

Theorem retrying_refutes_the_fail_stop_arm :
  ~ StopsOnNegativeReading retrying_sequencer
  /\ ~ LatchesOnNegativeReading retrying_sequencer.
Proof.
  split.
  - intros [ H _ ]. discriminate H.
  - intros [ H _ ]. discriminate H.
Qed.

(* The retry is invisible to the order, both arms of it being ordered on
   first occurrences, so R-15-247d's ordering does not carry R-15-247f's
   no-retry rule and the two are separate obligations rather than one
   stated twice. *)
Theorem the_retry_is_ordered_and_still_refused :
  Ordered (retrying_sequencer false) /\ ~ ReadsOnce retrying_sequencer.
Proof.
  split.
  - apply ordered_ok_sound. reflexivity.
  - intros H. specialize (H false). discriminate H.
Qed.

(* A sequence that admits the domain on a negative completion reading:
   the arm R-15-247f's fail-closed line and R-17-030n exist to remove. *)
Definition optimistic_sequencer : Sequencer := fun _ => admission_sequence true.

Theorem optimistic_refutes_the_fail_stop_arm :
  ~ StopsOnNegativeReading optimistic_sequencer
  /\ ~ LatchesOnNegativeReading optimistic_sequencer.
Proof.
  split.
  - intros [ H _ ]. discriminate H.
  - intros [ H _ ]. discriminate H.
Qed.

(* It is ordered, reads once, reads after the dwell, and repeats nothing,
   so every other obligation in this file is silent about it and the arm is
   the only thing that refuses it. That is what makes the arm content. *)
Theorem the_optimistic_sequencer_passes_everything_else :
  KeepsTheOrder optimistic_sequencer
  /\ ReadsOnce optimistic_sequencer
  /\ NeverRepeatsTheDischarge optimistic_sequencer
  /\ ReadFollowsTheDwell optimistic_sequencer.
Proof.
  split; [ exact specification_is_ordered | ].
  split; [ intros b; destruct b; reflexivity | ].
  split; intros b; destruct b; reflexivity.
Qed.

(* A sequencer that treats the tag-plane confirmation as the data-plane
   confirmation too, reaching measured execution with no separately
   admitted sanitization step. R-17-024a and R-15-247d make those two
   boundaries and not one. *)
Definition one_confirmation_sequencer : Sequencer := fun confirmed =>
  cons RequestersInReset
  (cons TagPlaneDischarge
  (cons WorstCornerDwell
  (cons CompletionRead
    (if confirmed
     then cons DomainAddressable (cons MeasuredExecution nil)
     else cons FailStopArm nil)))).

Theorem one_confirmation_refutes_the_two_boundaries :
  ~ KeepsTheOrder one_confirmation_sequencer.
Proof.
  intros [ _ [ _ [ _ [ _ [ H _ ] ] ] ] ]. discriminate H.
Qed.

(* A sequencer that latches on every reading rather than on the negative
   one, which is a stopped machine and not a fail-stop: it satisfies the
   first half of the arm and fails the second, which is why the arm is
   stated as a pair. *)
Definition always_latching_sequencer : Sequencer := fun _ =>
  cons RequestersInReset
  (cons TagPlaneDischarge
  (cons WorstCornerDwell
  (cons CompletionRead (cons FailStopArm nil)))).

Theorem always_latching_refutes_the_second_half_of_the_arm :
  occurs FailStopArm (always_latching_sequencer false) = true
  /\ ~ LatchesOnNegativeReading always_latching_sequencer.
Proof.
  split; [ reflexivity | ]. intros [ _ H ]. discriminate H.
Qed.

(* =========================================================================
   The sweep over banks, and R-15-247d's acceptance clause: no path admits
   a partially sanitized bank.
   ========================================================================= *)

(* What committed, per bank and per chunk. R-15-247b makes data, tag
   validity and both ECC planes commit atomically at the granule, a write
   that does not commit being a fail-stop sentinel event rather than a
   half-written granule, so a chunk is a boolean and the partiality this
   file is about is a bank's and not a granule's (reading 3). *)
Definition Sweep (m : Machine) : Type := m.(Bank) -> m.(Chunk) -> bool.

Definition bank_drained (m : Machine) (sw : Sweep m) (b : m.(Bank)) : bool :=
  all_of (sw b) (m.(chunks_of) b).

Definition bank_touched (m : Machine) (sw : Sweep m) (b : m.(Bank)) : bool :=
  any_of (sw b) (m.(chunks_of) b).

(* R-15-247d's own words: a bank the pass reached and did not finish. *)
Definition bank_partial (m : Machine) (sw : Sweep m) (b : m.(Bank)) : bool :=
  andb (bank_touched m sw b) (negb (bank_drained m sw b)).

Definition domain_drained (m : Machine) (sw : Sweep m) : bool :=
  all_of (bank_drained m sw) m.(banks).

Definition no_partial_bank (m : Machine) (sw : Sweep m) : bool :=
  all_of (fun b => negb (bank_partial m sw b)) m.(banks).

(* R-15-247f's completion indication, as an arbitrary reader over the sweep
   (reading 4). The domain is addressable exactly where the reader
   confirms, so a reader is an admission judgment. *)
Definition Reader (m : Machine) : Type := Sweep m -> bool.

Definition spec_reader (m : Machine) : Reader m := domain_drained m.

Definition AdmitsOnlyDrainedDomains (m : Machine) (r : Reader m) : Prop :=
  forall sw : Sweep m, r sw = true -> domain_drained m sw = true.

Definition AdmitsNoPartiallySanitizedBank (m : Machine) (r : Reader m) : Prop :=
  forall sw : Sweep m, r sw = true -> no_partial_bank m sw = true.

Lemma drained_is_not_partial :
  forall (m : Machine) (sw : Sweep m) (b : m.(Bank)),
    bank_drained m sw b = true -> bank_partial m sw b = false.
Proof.
  intros m sw b H. unfold bank_partial. rewrite H.
  destruct (bank_touched m sw b); reflexivity.
Qed.

(* D8 (R-15-247d's acceptance clause). The file's load-bearing theorem: a
   reader answering for every bank admits no bank the pass reached and did
   not finish. *)
Theorem specification_admits_no_partially_sanitized_bank :
  forall m : Machine, AdmitsNoPartiallySanitizedBank m (spec_reader m).
Proof.
  intros m sw H. unfold no_partial_bank.
  apply (all_of_mono m.(Bank) (bank_drained m sw)
           (fun b => negb (bank_partial m sw b)) m.(banks)).
  - intros b Hb. rewrite (drained_is_not_partial m sw b Hb). reflexivity.
  - exact H.
Qed.

(* D8a. Definitional on this side, the specification's reader being the
   drained predicate itself; its content sits in the refutations beside it,
   which is also where the two clauses are shown to differ. *)
Theorem specification_admits_only_drained_domains :
  forall m : Machine, AdmitsOnlyDrainedDomains m (spec_reader m).
Proof. intros m sw H. exact H. Qed.

(* -------------------------------------------------------------------------
   The demo machine, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Two banks and two chunks per bank exercise every
   case the clauses distinguish: a bank drained, a bank the pass reached
   and did not finish, and a bank the pass never reached. The dwell figure
   and the rosters are arbitrary witness values and carry no composition
   claim (gap e).
   ------------------------------------------------------------------------- *)

Definition demo : Machine := {|
  Requester := bool;
  requesters := cons true (cons false nil);
  Bank := bool;
  banks := cons true (cons false nil);
  Chunk := bool;
  chunks_of := fun _ => cons true (cons false nil);
  dwell_cycles := 9
|}.

(* Every chunk of every bank committed. *)
Definition sweep_clean : Sweep demo := fun _ _ => true.

(* The second bank reached and not finished: one chunk committed and one
   did not, which is R-15-247d's partially sanitized bank. *)
Definition sweep_partial : Sweep demo := fun b c => if b then true else c.

(* The second bank never reached at all: a phase that did not run rather
   than one that stopped halfway. *)
Definition sweep_missed : Sweep demo := fun b _ => b.

Example the_three_sweeps_are_distinguished :
  domain_drained demo sweep_clean = true
  /\ no_partial_bank demo sweep_clean = true
  /\ domain_drained demo sweep_partial = false
  /\ no_partial_bank demo sweep_partial = false
  /\ domain_drained demo sweep_missed = false
  /\ no_partial_bank demo sweep_missed = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* D8b (R-05-165): the specification's reader confirms on one sweep and
   refuses on another, so neither theorem above is proved from an empty
   antecedent and neither is a property every reader has. *)
Theorem the_specification_reader_confirms_and_refuses :
  spec_reader demo sweep_clean = true
  /\ spec_reader demo sweep_partial = false
  /\ spec_reader demo sweep_missed = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* =========================================================================
   Refutation witnesses over the reader (R-05-166).
   ========================================================================= *)

(* A discharge confirmed per domain rather than per bank: the sequencer
   takes the domain's indication off the bank its phase began at.
   R-15-247e asserts every write wordline in *the bank*, R-15-247p makes
   banks whole-bound and never dynamically allocated, and the Sail
   sequencer (model/model/sys/memory_sequencer.sail) makes the bank the
   unit of work because the walk over the banks is R-15-198's, so a
   domain-wide indication is a construction those sentences exclude. *)
Definition per_domain_reader (m : Machine) : Reader m := fun sw =>
  match m.(banks) with
  | nil => false
  | cons b _ => bank_drained m sw b
  end.

Theorem per_domain_reader_admits_an_undrained_bank :
  per_domain_reader demo sweep_missed = true
  /\ ~ AdmitsOnlyDrainedDomains demo (per_domain_reader demo).
Proof.
  split; [ reflexivity | ].
  intros H. specialize (H sweep_missed eq_refl). discriminate H.
Qed.

Theorem per_domain_reader_admits_a_partially_sanitized_bank :
  per_domain_reader demo sweep_partial = true
  /\ ~ AdmitsNoPartiallySanitizedBank demo (per_domain_reader demo).
Proof.
  split; [ reflexivity | ].
  intros H. specialize (H sweep_partial eq_refl). discriminate H.
Qed.

(* A reader that confirms as soon as every bank was reached rather than
   drained: the construction R-15-247d's acceptance clause names by its
   consequence. It is refuted by the same sweep at both clauses, so what
   refutes it is the bank left half-swept and not the reader's shape. *)
Definition touch_reader (m : Machine) : Reader m := fun sw =>
  all_of (bank_touched m sw) m.(banks).

Theorem touch_reader_admits_a_partially_sanitized_bank :
  touch_reader demo sweep_partial = true
  /\ ~ AdmitsNoPartiallySanitizedBank demo (touch_reader demo)
  /\ ~ AdmitsOnlyDrainedDomains demo (touch_reader demo).
Proof.
  split; [ reflexivity | ]. split.
  - intros H. specialize (H sweep_partial eq_refl). discriminate H.
  - intros H. specialize (H sweep_partial eq_refl). discriminate H.
Qed.

(* And the same reader on the sweep that reached nothing: it refuses, so
   the reader is not one that confirms everything and the refutation above
   is the partial bank rather than the construction's own permissiveness. *)
Theorem the_touch_reader_still_refuses_an_unreached_bank :
  touch_reader demo sweep_missed = false.
Proof. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Gap b, made checkable rather than asserted. R-15-247f states a single
   read of the completion indication and R-15-247g stages the discharge in
   phases over banks, and no entry says whether the indication is one bit
   per transition, one per phase, or one per bank. The three are not
   observationally equal: on a sweep that reached one bank and not the
   other, a per-domain reader confirms where the per-bank reader refuses.
   ------------------------------------------------------------------------- *)

Theorem the_reader_arity_is_observable :
  per_domain_reader demo sweep_missed = true
  /\ spec_reader demo sweep_missed = false.
Proof. split; reflexivity. Qed.

(* -------------------------------------------------------------------------
   And a second reading of R-15-247d made checkable. Its acceptance clause
   is stated of a *partially* sanitized bank, which is a necessary
   condition and not the criterion: the reader that is exactly that clause
   admits a bank nothing reached, because a bank nothing reached is not
   partially sanitized. What excludes that admission is the completion
   read's own domain, so the clause and the read are two obligations and
   the clause alone does not carry the second.
   ------------------------------------------------------------------------- *)

Theorem the_acceptance_clause_is_not_the_criterion :
  AdmitsNoPartiallySanitizedBank demo (no_partial_bank demo)
  /\ ~ AdmitsOnlyDrainedDomains demo (no_partial_bank demo).
Proof.
  split.
  - intros sw H. exact H.
  - intros H. specialize (H sweep_missed eq_refl). discriminate H.
Qed.

(* =========================================================================
   Step 3's shape: the dwell term is the machine's declared constant.

   What is stated here is where the number comes from and nothing about how
   either path's timing behaves. R-15-247f's timing clause quantifies over
   a discharge speed, a measured magnitude R-15-247m puts on a repaired
   megabit-class macro that no artifact here carries, and over the whole of
   the success and timeout paths rather than the dwell term alone. That
   clause is M3.6b and is not stated below; nothing here introduces a
   speed, a rate, or any quantity derived from leakage, which R-15-247c
   forbids a containment guarantee from resting on in any case.
   ========================================================================= *)

Definition DwellLength (m : Machine) : Type := Sweep m -> bool -> nat.

Definition spec_dwell (m : Machine) : DwellLength m := fun _ _ => m.(dwell_cycles).

Definition IsTheDeclaredConstant (m : Machine) (d : DwellLength m) : Prop :=
  forall (sw : Sweep m) (b : bool), d sw b = m.(dwell_cycles).

(* D9 (R-15-247f, R-15-247g): the dwell entering the transition budget is
   the composition constant and is not read off the array. *)
Theorem specification_dwell_is_the_declared_constant :
  forall m : Machine, IsTheDeclaredConstant m (spec_dwell m).
Proof. intros m sw b. reflexivity. Qed.

(* A dwell taken from what the sweep found: R-15-247f's Accept clause names
   this defect by its cause, a poll making the transition time a function
   of temperature, charge state, and what the bank held. *)
Definition charge_dependent_dwell (m : Machine) : DwellLength m :=
  fun sw _ => if domain_drained m sw then m.(dwell_cycles) else S m.(dwell_cycles).

Theorem charge_dependent_dwell_is_refuted :
  ~ IsTheDeclaredConstant demo (charge_dependent_dwell demo).
Proof.
  intros H. specialize (H sweep_partial true). discriminate H.
Qed.

(* A dwell that differs between the success arm and the timeout arm. It
   reads nothing of the array, so what refutes it is the arm alone, which
   is the half of R-15-247f's shape a construction can break without ever
   touching the sweep. *)
Definition arm_dependent_dwell (m : Machine) : DwellLength m :=
  fun _ b => if b then m.(dwell_cycles) else S m.(dwell_cycles).

Theorem arm_dependent_dwell_is_refuted :
  ~ IsTheDeclaredConstant demo (arm_dependent_dwell demo).
Proof.
  intros H. specialize (H sweep_clean false). discriminate H.
Qed.

(* =========================================================================
   Step 1 and step 6: the requesters, held in reset for the whole of the
   pass and released no earlier than addressability (R-15-247h, R-15-247d).
   ========================================================================= *)

Definition ResetHold (m : Machine) : Type := m.(Requester) -> bool.

Definition spec_hold (m : Machine) : ResetHold m := fun _ => true.

Definition HoldsEveryRequester (m : Machine) (h : ResetHold m) : Prop :=
  all_of h m.(requesters) = true.

(* D10 (R-15-247h): every requester the composition names, and R-15-247h
   names three classes rather than one (reading 5). *)
Theorem specification_holds_every_requester :
  forall m : Machine, HoldsEveryRequester m (spec_hold m).
Proof. intros m. apply all_of_true. Qed.

(* A reset that reaches one class and not another. R-15-247h's enumeration
   is every application core, every DMA engine, and every
   capability-bearing fabric initiator, so a hold exempting one of them is
   not the hold that entry states. *)
Definition class_exempt_hold : ResetHold demo := fun r => r.

Theorem class_exempt_hold_is_refuted :
  ~ HoldsEveryRequester demo class_exempt_hold.
Proof. intros H. discriminate H. Qed.

(* Release, stated against the specification's own order: no requester is
   released at a phase the sequence puts before addressability. This is
   R-15-247d's "before any requester may name the domain" read as a
   constraint on the release schedule rather than on the sequence. *)
Definition ReleaseSchedule (m : Machine) : Type := m.(Requester) -> Phase.

Definition spec_release (m : Machine) : ReleaseSchedule m := fun _ => DomainAddressable.

Definition NoRequesterNamesTheDomainEarly
    (m : Machine) (rel : ReleaseSchedule m) : Prop :=
  forall r : m.(Requester),
    precedes (rel r) DomainAddressable (admission_sequence true) = false.

(* D11 (R-15-247d, R-15-247h). *)
Theorem specification_releases_no_requester_early :
  forall m : Machine, NoRequesterNamesTheDomainEarly m (spec_release m).
Proof. intros m r. reflexivity. Qed.

(* The early-release family, generated by quantifying over the phase rather
   than by enumerating a mutation: every phase the specification puts
   before addressability is a release schedule this refuses, and which
   phases those are is computed rather than listed. *)
Example the_phases_that_would_release_early_are_the_four_before_addressability :
  filter_of (fun p => precedes p DomainAddressable (admission_sequence true)) all_phases
  = cons RequestersInReset (cons TagPlaneDischarge
    (cons WorstCornerDwell (cons CompletionRead nil))) := eq_refl.

Theorem every_early_release_schedule_is_refused :
  forall p : Phase,
    precedes p DomainAddressable (admission_sequence true) = true ->
    ~ NoRequesterNamesTheDomainEarly demo (fun _ => p).
Proof.
  intros p Hp Hno. specialize (Hno true). cbv beta in Hno.
  rewrite Hp in Hno. discriminate Hno.
Qed.

(* The concrete member of that family R-15-247h names outright: a requester
   released while the discharge is still running. *)
Theorem a_requester_released_at_the_discharge_is_refused :
  ~ NoRequesterNamesTheDomainEarly demo (fun _ => TagPlaneDischarge).
Proof.
  apply every_early_release_schedule_is_refused. reflexivity.
Qed.

(* And the family is not everything: a release at data sanitization or at
   measured execution is later than addressability and is admitted, so the
   obligation excludes something rather than refusing every schedule. *)
Theorem a_late_release_is_admitted :
  NoRequesterNamesTheDomainEarly demo (fun _ => DataSanitization)
  /\ NoRequesterNamesTheDomainEarly demo (fun _ => MeasuredExecution).
Proof. split; intros r; reflexivity. Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by tools/proof-gate.py: every shipped
   constant's enumerated assumption set is compared against the declared
   set R-05-164 currently makes empty, so "Closed under the global context"
   is that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions admission_sequence.
Print Assumptions ordered_ok.
Print Assumptions Ordered.
Print Assumptions precedes.
Print Assumptions single_read_ok.
Print Assumptions generated_weakenings.
Print Assumptions failing_conjuncts.
Print Assumptions Sweep.
Print Assumptions bank_partial.
Print Assumptions no_partial_bank.
Print Assumptions spec_reader.
Print Assumptions AdmitsOnlyDrainedDomains.
Print Assumptions AdmitsNoPartiallySanitizedBank.
Print Assumptions spec_dwell.
Print Assumptions spec_hold.
Print Assumptions spec_release.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions all_of_mono.
Print Assumptions all_of_true.
Print Assumptions phase_eqb_refl.
Print Assumptions phase_eqb_true.
Print Assumptions ordered_ok_sound.
Print Assumptions ordered_ok_complete.
Print Assumptions specification_is_ordered.
Print Assumptions authority_invalidation_is_independent_of_residue_sanitization.
Print Assumptions generated_family_size.
Print Assumptions every_generated_weakening_is_refused.
Print Assumptions every_transposition_is_out_of_order.
Print Assumptions every_deletion_is_out_of_order.
Print Assumptions every_proper_suffix_is_out_of_order.
Print Assumptions every_extra_read_is_not_a_single_read.
Print Assumptions no_adjacent_transposition_is_ordered.
Print Assumptions no_deletion_is_ordered.
Print Assumptions no_proper_suffix_is_ordered.
Print Assumptions no_extra_read_is_a_single_read.
Print Assumptions each_conjunct_of_the_order_decides.
Print Assumptions the_specification_breaks_no_conjunct.
Print Assumptions specification_keeps_the_order.
Print Assumptions specification_stops_on_a_negative_reading.
Print Assumptions specification_latches_on_a_negative_reading.
Print Assumptions specification_reads_once.
Print Assumptions specification_never_repeats_the_discharge.
Print Assumptions specification_reads_after_the_dwell.
Print Assumptions eager_read_refutes_the_dwell_order.
Print Assumptions eager_read_still_reads_once.
Print Assumptions polling_refutes_the_single_read.
Print Assumptions polling_still_keeps_the_order_and_reads_after_the_dwell.
Print Assumptions retrying_refutes_the_no_retry_rule.
Print Assumptions retrying_refutes_the_fail_stop_arm.
Print Assumptions the_retry_is_ordered_and_still_refused.
Print Assumptions optimistic_refutes_the_fail_stop_arm.
Print Assumptions the_optimistic_sequencer_passes_everything_else.
Print Assumptions one_confirmation_refutes_the_two_boundaries.
Print Assumptions always_latching_refutes_the_second_half_of_the_arm.
Print Assumptions drained_is_not_partial.
Print Assumptions specification_admits_no_partially_sanitized_bank.
Print Assumptions specification_admits_only_drained_domains.
Print Assumptions the_three_sweeps_are_distinguished.
Print Assumptions the_specification_reader_confirms_and_refuses.
Print Assumptions per_domain_reader_admits_an_undrained_bank.
Print Assumptions per_domain_reader_admits_a_partially_sanitized_bank.
Print Assumptions touch_reader_admits_a_partially_sanitized_bank.
Print Assumptions the_touch_reader_still_refuses_an_unreached_bank.
Print Assumptions the_reader_arity_is_observable.
Print Assumptions the_acceptance_clause_is_not_the_criterion.
Print Assumptions specification_dwell_is_the_declared_constant.
Print Assumptions charge_dependent_dwell_is_refuted.
Print Assumptions arm_dependent_dwell_is_refuted.
Print Assumptions specification_holds_every_requester.
Print Assumptions class_exempt_hold_is_refuted.
Print Assumptions specification_releases_no_requester_early.
Print Assumptions the_phases_that_would_release_early_are_the_four_before_addressability.
Print Assumptions every_early_release_schedule_is_refused.
Print Assumptions a_requester_released_at_the_discharge_is_refused.
Print Assumptions a_late_release_is_admitted.
