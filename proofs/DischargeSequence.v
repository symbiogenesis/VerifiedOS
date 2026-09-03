(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   DischargeSequence.v

   The RoT discharge and admission sequence, as the register fixes it:
   R-15-247d's ordered authority invalidation before residue sanitization,
   resolved to one pass over both planes, R-15-247e's drain through the
   cells' own write devices, R-15-247g's phases staggered over banks by the
   composition-time schedule, R-15-247f's fixed worst-corner dwell and
   single fail-stop completion read taken once per phase with no poll and
   no retry and the latch in the RoT domain, R-15-247q's relocation of the
   discharge to the mode-exit path, R-15-247h's requesters held in reset,
   and R-15-198's sequence table, which R-15-247d rides rather than
   standing beside.

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

   What is deferred, and to which item. R-15-247f's timing clause, that no
   timing on either the success or the timeout path varies with discharge
   speed, is not stated here at all: it quantifies over a discharge speed,
   which is a measured magnitude R-15-247m puts on a repaired
   megabit-class macro and which no artifact in this repository carries,
   so there is nothing to vary it against. That clause is checklist item
   M3.6b, and nothing below introduces a speed, a rate, or a
   leakage-derived quantity that would stand in for one. What is stated of
   the dwell here is its shape alone: the dwell term is the machine's
   declared composition constant (R-15-247g's mode-transition dwell
   constant) rather than a function of what the sweep found. The
   whole-path invariance is M3.6b's.

   No Require. Nothing beyond the Rocq prelude is reachable, so Classical
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
      sanitization confirmed, then measured execution", R-15-247q puts the
      discharge on the exit path rather than the next entry, and R-15-247g
      stages the discharge in phases the composition-time schedule fixes.
      So the exit path below is the requesters held in reset and then, in
      schedule order, each phase's discharge, dwell and read, and the entry
      path is addressability, the residue boundary and measured execution,
      with the order spanning the power transition between them. That is
      also what R-15-189j reads from the other side when it says what a
      bulk domain owes on the way in is the confirmation R-15-247d orders
      and not a regeneration sweep.
   2. The fail-stop is an arm of each phase's read and not a phase of the
      success path. R-15-247f's fail-closed line stops the transition
      rather than repeating it, so the sequencer is a function of the
      readings, one per phase: on a positive reading it continues to the
      next phase or, after the last, to addressability, and on a negative
      one it reaches the latch and stops where it stands, no later phase
      being begun. R-15-247f puts that latch in the always-on
      root-of-trust domain because R-15-247q's exit path is the one that
      collapses the rail the domain sits on; the step below is named for
      where it sits, and nothing here computes over power domains, which
      is a fact about where a flop is placed rather than about the
      sequence.
   3. The unit of the read is the phase, and the phase's fact is composed
      from its banks. R-15-247f makes "single" single per phase because a
      phase either drained the banks R-15-247g names for it or did not;
      R-15-247e realizes the drain through the cells' existing write
      devices, R-15-247p makes banks whole-bound and composition-fixed,
      and R-15-247b makes data, tag validity and both ECC planes commit
      atomically at the granule, a write that does not commit being a
      fail-stop sentinel event rather than a half-written granule. So a
      sweep here is a per-bank, per-chunk record of what committed, a bank
      is drained when every chunk of it committed, a phase is drained when
      every bank it names is, and a bank is partially sanitized when some
      chunk committed and some did not.
   4. The transition's admission is stated as an arbitrary Reader over the
      sweep, and the specification's reader is the conjunction of the
      phase reads. That is what lets a reader of another arity be exhibited
      and refuted rather than assumed away: the per-transition reader
      R-15-247f refuses is constructed below and shown to admit a domain
      one of whose phases reached nothing, and the per-bank reader that
      entry calls sound is shown to agree with the per-phase one on every
      sweep.
   5. Requesters are a list and the hold is a predicate over it. R-15-247h
      names three classes held in reset, every application core, every DMA
      engine, and every capability-bearing fabric initiator, and scopes the
      hold to the requesters that can address the domain being discharged,
      a roster read from the same map R-15-228 fixes. That roster is the
      `requesters` field, and the obligation is stated over whatever it
      names.
   6. The order is stated over first occurrences: `precedes p q l` walks l
      and answers at whichever of p and q it meets first, so a sequence out
      of order is expressible and the theorems have something to exclude.
      It is false where either step is absent, which is what makes a
      deletion a refusal rather than a silence, and it is what makes an
      early addressability refused even when a later one is in order.
   7. Boolean rather than propositional wherever the witnesses must
      compute: the order check, the counts, and the bank predicates are
      decidable, so the generated weakening families below are checked by
      conversion in the silent Example form rather than by a proof per
      member.
   8. The domain's banks are the phases' banks. R-15-247g fixes every
      phase's bank membership at composition, so the bank roster is read
      off the schedule rather than carried beside it, and the per-phase
      read reaches every bank the domain has by construction. A bank the
      schedule names in no phase would be a composition defect and not a
      state this file can reach; a coverage obligation, if the register
      wants one stated, belongs at R-15-247g.

   The literals taken from the design, and there are three. R-15-247d's
   Accept clause and R-15-247g's schedule fix the step order, so
   `admission_sequence` is that order written out over the phase list and
   is this file's one structural literal. R-15-247f fixes the completion
   read at one per phase, so `single_read_ok` compares each phase's read
   count against 1. And R-15-247f fixes the retry count at zero and
   R-15-247d the pass count at one, so `NoStepStandsTwice` bounds every
   step's occurrences by 1 on every reading. Every other magnitude is a
   field: the dwell length, because R-15-247m measures it on a repaired
   macro and R-15-247g folds it into the transition budget; the phase count
   and each phase's banks, because R-15-247g fixes them at composition and
   R-15-247p puts the per-class bank count in R-15-014a's frozen parameter
   set; the chunk decomposition of a bank, because R-15-247e makes the
   drain the interface's own write and the chunk width is that interface's;
   and the requester roster, per reading 5.

   How the refutations are generated. A refutation is a seeded weakening
   the theorem must reject, so four generators produce families of them
   mechanically rather than a person authoring each, over the
   specification's own success path at the demo machine's two phases,
   which is ten steps long. `swap_at` transposes an adjacent pair and
   yields one weakening per adjacent position; `drop_at` deletes a step and
   yields one per position; `suffix_at` re-enters the table at a proper
   suffix, which is R-15-198's own phrase for what a wake and a standby
   exit are, and yields one per position; and `insert_at` adds a second
   read of a phase and yields one per position per phase. Every member is
   refused, checked as one conversion whose size `generated_family_size`
   computes. Beside them the generic theorems quantify over the index
   rather than enumerating, the obligations of the specification itself
   are proved for every phase count rather than for the demo's, and the
   early-release family quantifies over the step rather than over an index
   at all. The hand-authored refutations below are the ones no index
   generates, being alternative constructions rather than mutations of a
   list.

   What the register decides and this file takes as given, with the entry
   that decides each:

   a. The data plane's sanitization is the same pass. R-15-247d resolves
      its disjunction to one pass over both planes, so the transition
      carries one dwell and one read per phase and not two of each, and
      the residue boundary R-15-247d still names is crossed on the
      confirmation already held rather than by a second drain.
      `ResidueConfirmed` is that boundary and carries no discharge, dwell
      or read of its own; a sequencer that runs the drain again at that
      boundary is exhibited and refuted by the count.
   b. The completion read is per phase. R-15-247f makes one dwell and one
      read for each of R-15-247g's staggered phases, refuses per
      transition on this file's own construction, and refuses per bank on
      cost. The sequencer below reads once per phase; the per-transition
      sequencer and reader are exhibited and shown to admit a domain one
      of whose phases reached nothing; and the per-bank reader is shown to
      agree with the per-phase reader on every sweep, which is the
      soundness R-15-247f grants it.
   c. The reset hold is scoped to the requesters that can address the
      domain being discharged (R-15-247h), and the roster is a composition
      constant. Reading 5 is how this file states it.
   d. The fail-stop latch sits in the always-on root-of-trust domain
      (R-15-247f). Reading 2 is how this file names it.
   e. Every composition magnitude. The dwell, the phase count, each
      phase's banks, the chunk decomposition and the requester roster are
      fields; the demo machine at the end instantiates them with arbitrary
      witness values that carry no composition claim.

   Readings the register could state and does not, each taken here by the
   narrowest construction and reported rather than closed:

   f. Whether a phase after a negative reading is begun at all. R-15-247f
      stops the transition; the sequencer below stops where it stands and
      begins nothing after the latch. A sequencer that drains the
      remaining phases before latching would keep every obligation stated
      here except the latch's position.
   g. Whether the dwell is one magnitude for every phase or one per phase.
      `dwell_cycles` is one field and the dwell obligation is stated per
      read, so a per-phase dwell table would be a second field and would
      change nothing stated here.
   h. R-15-189n's one-bit confirmation read once beside R-15-247f's read
      per phase. The RoT's gate on the transition is read here as the
      conjunction of the phase readings, which is what
      `admission_is_the_readers_confirmation` states.

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
         runs, scoped to the requesters that can address the domain and
         read from R-15-228's map (reading 5) --------------------------- *)

  Requester : Type;
  requesters : list Requester;

  (* --- R-15-247g's staggered phases, fixed at composition with their
         bank membership: a phase is an index below the count, and the
         banks it names are R-15-247p's, composition-fixed, whole-bound to
         islands, and never varying with occupancy or load (reading 8) --- *)

  Bank : Type;
  phase_count : nat;
  banks_of : nat -> list Bank;

  (* --- the unit the drain is issued in. R-15-247e realizes discharge
         through the cells' existing write devices, so a bank's sweep is a
         run of ordinary writes and the chunk width is the memory
         interface's business rather than this file's ---------------------- *)

  Chunk : Type;
  chunks_of : Bank -> list Chunk;

  (* --- R-15-247f's fixed worst-corner dwell, one per phase, the whole
         entering §11 as R-15-247g's mode-transition dwell constant. The
         magnitude is R-15-247m's, measured on a repaired megabit-class
         macro, so it is a field and no number here (reading g) --------- *)

  dwell_cycles : nat
}.

(* -------------------------------------------------------------------------
   List helpers, defined here rather than imported: the prelude carries the
   list type and not the library over it, and importing a module to save a
   few dozen lines would put its assumptions inside the R-05-163 gate's
   reach for no gain.
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

Fixpoint flatten {A : Type} (ls : list (list A)) : list A :=
  match ls with nil => nil | cons l r => app l (flatten r) end.

(* 0 through n-1, in that order: the phase indices of a machine with n
   phases, and the index set the generators below range over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

(* Consecutive pairs of a list, in order. *)
Fixpoint adjacent_pairs {A : Type} (l : list A) : list (A * A) :=
  match l with
  | nil => nil
  | cons x r =>
      match r with
      | nil => nil
      | cons y _ => cons (x, y) (adjacent_pairs r)
      end
  end.

(* Membership and distinctness over nat, by Nat.eqb. *)
Fixpoint mem_nat (k : nat) (l : list nat) : bool :=
  match l with nil => false | cons j r => orb (Nat.eqb k j) (mem_nat k r) end.

Fixpoint nodup_nat (l : list nat) : bool :=
  match l with
  | nil => true
  | cons k r => andb (negb (mem_nat k r)) (nodup_nat r)
  end.

(* -------------------------------------------------------------------------
   Boolean, list and nat lemmas, all proved from the prelude alone.
   ------------------------------------------------------------------------- *)

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma orb_split : forall a b : bool, orb a b = false -> a = false /\ b = false.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma negb_true : forall b : bool, negb b = true -> b = false.
Proof. intros b H. destruct b. discriminate H. reflexivity. Qed.

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

Lemma all_of_app :
  forall (A : Type) (p : A -> bool) (a b : list A),
    all_of p (app a b) = andb (all_of p a) (all_of p b).
Proof.
  intros A p a b. induction a as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite IH. destruct (p x); reflexivity.
Qed.

Lemma any_of_app :
  forall (A : Type) (p : A -> bool) (a b : list A),
    any_of p (app a b) = orb (any_of p a) (any_of p b).
Proof.
  intros A p a b. induction a as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite IH. destruct (p x); reflexivity.
Qed.

Lemma all_of_flatten_map :
  forall (A B : Type) (p : B -> bool) (f : A -> list B) (l : list A),
    all_of p (flatten (map_over f l)) = all_of (fun x => all_of p (f x)) l.
Proof.
  intros A B p f l. induction l as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite all_of_app. rewrite IH. reflexivity.
Qed.

Lemma app_snoc :
  forall (A : Type) (a : list A) (x : A) (l : list A),
    app (app a (cons x nil)) l = app a (cons x l).
Proof.
  intros A a x l. induction a as [ | y r IH ]; simpl.
  - reflexivity.
  - rewrite IH. reflexivity.
Qed.

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. induction n as [ | k IH ]; simpl. reflexivity. exact IH. Qed.

Lemma nat_eqb_true : forall i j : nat, Nat.eqb i j = true -> i = j.
Proof.
  induction i as [ | i IH ]; destruct j; simpl; intros H; try discriminate H.
  - reflexivity.
  - f_equal. exact (IH j H).
Qed.

Lemma nat_eqb_sym : forall i j : nat, Nat.eqb i j = Nat.eqb j i.
Proof.
  induction i as [ | i IH ]; destruct j; simpl; try reflexivity. exact (IH j).
Qed.

Lemma nat_leb_split : forall i j : nat, Nat.leb i j = orb (Nat.ltb i j) (Nat.eqb i j).
Proof.
  unfold Nat.ltb. induction i as [ | i IH ]; destruct j; simpl; try reflexivity.
  exact (IH j).
Qed.

Lemma nat_ltb_S : forall i j : nat, Nat.ltb i (S j) = orb (Nat.ltb i j) (Nat.eqb i j).
Proof. intros i j. exact (nat_leb_split i j). Qed.

Lemma nat_ltb_irrefl : forall n : nat, Nat.ltb n n = false.
Proof. unfold Nat.ltb. induction n as [ | k IH ]; simpl. reflexivity. exact IH. Qed.

Lemma mem_nat_app :
  forall (k : nat) (a b : list nat), mem_nat k (app a b) = orb (mem_nat k a) (mem_nat k b).
Proof.
  intros k a b. induction a as [ | j r IH ]; simpl.
  - reflexivity.
  - rewrite IH. destruct (Nat.eqb k j); reflexivity.
Qed.

(* The phase indices below n are exactly the k with k < n. *)
Lemma mem_upto : forall k n : nat, mem_nat k (upto n) = Nat.ltb k n.
Proof.
  intros k n. induction n as [ | n IH ]; simpl.
  - reflexivity.
  - rewrite mem_nat_app. rewrite IH. rewrite nat_ltb_S. simpl.
    destruct (Nat.ltb k n); destruct (Nat.eqb k n); reflexivity.
Qed.

Lemma nodup_nat_snoc :
  forall (a : list nat) (k : nat),
    nodup_nat (app a (cons k nil)) = andb (nodup_nat a) (negb (mem_nat k a)).
Proof.
  intros a k. induction a as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite mem_nat_app. rewrite IH. simpl. rewrite (nat_eqb_sym k x).
    destruct (mem_nat x r); destruct (Nat.eqb x k);
      destruct (nodup_nat r); destruct (mem_nat k r); reflexivity.
Qed.

(* And they are distinct, which is what makes a phase index a name. *)
Lemma nodup_upto : forall n : nat, nodup_nat (upto n) = true.
Proof.
  induction n as [ | k IH ]; simpl.
  - reflexivity.
  - rewrite nodup_nat_snoc. rewrite IH. rewrite mem_upto. rewrite nat_ltb_irrefl.
    reflexivity.
Qed.

(* =========================================================================
   The steps, and the order R-15-247d and R-15-247g fix over them.
   ========================================================================= *)

(* Exactly the steps R-15-247d's Accept clause, R-15-247f and R-15-247g
   name, and no others. This is a list of what the sequence does and not
   an inventory of platform events: the fail-stop latch is here because
   R-15-247f's fail-closed line makes it a destination of the read, and
   nothing else about the R-17-030n detector class is. The three phase
   steps carry the phase's index, so a sequence over n phases is a list
   over one closed type and every check below computes. *)
Inductive Step : Type :=
| RequestersInReset        (* R-15-247h: cores, DMA engines, fabric initiators *)
| PhaseDischarge (k : nat) (* R-15-247e, one pass over both planes (R-15-247d),
                              taken at mode exit per R-15-247q, phase k        *)
| PhaseDwell (k : nat)     (* R-15-247f's fixed dwell for phase k              *)
| PhaseRead (k : nat)      (* R-15-247f's one read of phase k's indication     *)
| FailStopLatch            (* R-15-247f fail-closed, in the RoT domain, R-17-030n *)
| DomainAddressable        (* R-15-247d: a requester may now name the domain   *)
| ResidueConfirmed         (* R-15-247d's second boundary, crossed on the
                              confirmation already held, no pass of its own    *)
| MeasuredExecution.       (* R-15-247d: what the second boundary precedes     *)

Definition step_eqb (p q : Step) : bool :=
  match p, q with
  | RequestersInReset, RequestersInReset => true
  | PhaseDischarge i, PhaseDischarge j => Nat.eqb i j
  | PhaseDwell i, PhaseDwell j => Nat.eqb i j
  | PhaseRead i, PhaseRead j => Nat.eqb i j
  | FailStopLatch, FailStopLatch => true
  | DomainAddressable, DomainAddressable => true
  | ResidueConfirmed, ResidueConfirmed => true
  | MeasuredExecution, MeasuredExecution => true
  | _, _ => false
  end.

Lemma step_eqb_refl : forall p : Step, step_eqb p p = true.
Proof. intros p. destruct p; simpl; try reflexivity; apply nat_eqb_refl. Qed.

Lemma step_eqb_true : forall p q : Step, step_eqb p q = true -> p = q.
Proof.
  intros p q. destruct p; destruct q; simpl; intros H;
    try discriminate H; try reflexivity;
    rewrite (nat_eqb_true _ _ H); reflexivity.
Qed.

Lemma step_eqb_sym : forall p q : Step, step_eqb p q = step_eqb q p.
Proof.
  intros p q. destruct p; destruct q; simpl; try reflexivity; apply nat_eqb_sym.
Qed.

(* Which phase a step belongs to, if any. *)
Definition phase_index (s : Step) : option nat :=
  match s with
  | PhaseDischarge k => Some k
  | PhaseDwell k => Some k
  | PhaseRead k => Some k
  | _ => None
  end.

(* Whether a step belongs to one of the listed phases. *)
Definition names_a_phase (ks : list nat) (s : Step) : bool :=
  match phase_index s with Some k => mem_nat k ks | None => false end.

Definition is_entry_step (s : Step) : bool :=
  match s with
  | DomainAddressable => true
  | ResidueConfirmed => true
  | MeasuredExecution => true
  | _ => false
  end.

(* Whether a step stands anywhere, how often, and which of two stands first.
   The first occurrence is what an order reads and the count is what a
   retry or a second pass moves, which is why the obligations below are
   separate and why one construction can satisfy either and fail the
   other. *)
Fixpoint occurs (s : Step) (l : list Step) : bool :=
  match l with
  | nil => false
  | cons x r => orb (step_eqb s x) (occurs s r)
  end.

Fixpoint occurrences (s : Step) (l : list Step) : nat :=
  match l with
  | nil => 0
  | cons x r => if step_eqb s x then S (occurrences s r) else occurrences s r
  end.

(* Answers at whichever of p and q the walk meets first; false where either
   is absent, which is what makes a deletion a refusal rather than a
   silence (reading 6). *)
Fixpoint precedes (p q : Step) (l : list Step) : bool :=
  match l with
  | nil => false
  | cons x r =>
      if step_eqb q x then false
      else if step_eqb p x then occurs q r
      else precedes p q r
  end.

Fixpoint nodup_steps (l : list Step) : bool :=
  match l with
  | nil => true
  | cons x r => andb (negb (occurs x r)) (nodup_steps r)
  end.

Lemma occurs_app :
  forall (s : Step) (a b : list Step), occurs s (app a b) = orb (occurs s a) (occurs s b).
Proof.
  intros s a b. induction a as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite IH. destruct (step_eqb s x); reflexivity.
Qed.

Lemma occurs_false_occurrences :
  forall (s : Step) (l : list Step), occurs s l = false -> occurrences s l = 0.
Proof.
  intros s l. induction l as [ | x r IH ]; simpl; intros H.
  - reflexivity.
  - destruct (orb_split _ _ H) as [ Hx Hr ]. rewrite Hx. exact (IH Hr).
Qed.

(* A list without repeats carries every step at most once, and every step
   it carries exactly once. *)
Lemma nodup_at_most_once :
  forall (l : list Step) (s : Step),
    nodup_steps l = true -> Nat.leb (occurrences s l) 1 = true.
Proof.
  intros l s. induction l as [ | x r IH ]; simpl; intros H.
  - reflexivity.
  - destruct (andb_split _ _ H) as [ Hx Hr ]. apply negb_true in Hx.
    destruct (step_eqb s x) eqn:E.
    + rewrite (step_eqb_true s x E). rewrite (occurs_false_occurrences x r Hx).
      reflexivity.
    + exact (IH Hr).
Qed.

Lemma nodup_once :
  forall (l : list Step) (s : Step),
    nodup_steps l = true -> occurs s l = true -> occurrences s l = 1.
Proof.
  intros l s. induction l as [ | x r IH ]; simpl; intros H Ho.
  - discriminate Ho.
  - destruct (andb_split _ _ H) as [ Hx Hr ]. apply negb_true in Hx.
    destruct (step_eqb s x) eqn:E.
    + rewrite (step_eqb_true s x E). rewrite (occurs_false_occurrences x r Hx).
      reflexivity.
    + exact (IH Hr Ho).
Qed.

Lemma precedes_irrefl : forall (p : Step) (l : list Step), precedes p p l = false.
Proof.
  intros p l. induction l as [ | x r IH ]; simpl.
  - reflexivity.
  - destruct (step_eqb p x). reflexivity. exact IH.
Qed.

(* -------------------------------------------------------------------------
   The specification. The exit path is the requesters in reset and then
   each phase's discharge, dwell and read in schedule order; each reading
   decides whether the next phase follows or the latch does; and the entry
   path is addressability, the residue boundary and measured execution
   (readings 1 and 2).
   ------------------------------------------------------------------------- *)

Definition Readings : Type := nat -> bool.

Definition all_positive : Readings := fun _ => true.

Definition entry_path : list Step :=
  cons DomainAddressable (cons ResidueConfirmed (cons MeasuredExecution nil)).

(* The staggered phases over their readings: a positive reading admits the
   next phase, a negative one reaches the latch and ends the sequence. *)
Fixpoint staggered (r : Readings) (ks : list nat) (tail : list Step) : list Step :=
  match ks with
  | nil => tail
  | cons k rest =>
      cons (PhaseDischarge k) (cons (PhaseDwell k) (cons (PhaseRead k)
        (if r k then staggered r rest tail else cons FailStopLatch nil)))
  end.

Definition admission_sequence (ks : list nat) (r : Readings) : list Step :=
  cons RequestersInReset (staggered r ks entry_path).

(* The same phases with every reading positive: the success path, which is
   the shape the order is read off. *)
Fixpoint phase_chain (ks : list nat) (tail : list Step) : list Step :=
  match ks with
  | nil => tail
  | cons k rest =>
      cons (PhaseDischarge k) (cons (PhaseDwell k) (cons (PhaseRead k)
        (phase_chain rest tail)))
  end.

Definition success_path (ks : list nat) : list Step :=
  cons RequestersInReset (phase_chain ks entry_path).

Lemma staggered_positive :
  forall (r : Readings) (ks : list nat) (tail : list Step),
    all_of r ks = true -> staggered r ks tail = phase_chain ks tail.
Proof.
  intros r ks tail. induction ks as [ | k rest IH ]; simpl; intros H.
  - reflexivity.
  - destruct (andb_split _ _ H) as [ Hk Hr ]. rewrite Hk. rewrite (IH Hr). reflexivity.
Qed.

Lemma admission_sequence_positive :
  forall ks : list nat, admission_sequence ks all_positive = success_path ks.
Proof.
  intros ks. unfold admission_sequence, success_path.
  rewrite (staggered_positive all_positive ks entry_path (all_of_true nat ks)).
  reflexivity.
Qed.

(* -------------------------------------------------------------------------
   R-15-247d's order over R-15-247g's phases, as the precedences read off
   the Accept clause and R-15-247f's sentence: the reset hold before the
   first discharge; within each phase the discharge, then the dwell, then
   the read; each phase's read before the next phase's discharge; the last
   read before addressability; and addressability, the residue boundary
   and measured execution in that order. `prev` is the step a phase's
   discharge waits on and `next` is what the last read precedes.
   ------------------------------------------------------------------------- *)

Fixpoint phase_pairs (prev : Step) (ks : list nat) (next : Step) : list (Step * Step) :=
  match ks with
  | nil => cons (prev, next) nil
  | cons k rest =>
      cons (prev, PhaseDischarge k)
      (cons (PhaseDischarge k, PhaseDwell k)
      (cons (PhaseDwell k, PhaseRead k)
            (phase_pairs (PhaseRead k) rest next)))
  end.

Definition entry_pairs : list (Step * Step) :=
  cons (DomainAddressable, ResidueConfirmed)
  (cons (ResidueConfirmed, MeasuredExecution) nil).

Definition required_order (ks : list nat) : list (Step * Step) :=
  app (phase_pairs RequestersInReset ks DomainAddressable) entry_pairs.

Definition pair_precedes (l : list Step) (pq : Step * Step) : bool :=
  precedes (fst pq) (snd pq) l.

Definition ordered_ok (ks : list nat) (l : list Step) : bool :=
  all_of (pair_precedes l) (required_order ks).

Definition Ordered (ks : list nat) (l : list Step) : Prop := ordered_ok ks l = true.

(* The order is the success path's own adjacency: what the register's
   sentence lists pair by pair is exactly consecutive steps of the path it
   describes, computed rather than asserted. *)
Lemma adjacent_pairs_cons :
  forall (A : Type) (x y : A) (l : list A),
    adjacent_pairs (cons x (cons y l)) = cons (x, y) (adjacent_pairs (cons y l)).
Proof. intros A x y l. reflexivity. Qed.

Lemma required_order_is_adjacency :
  forall (ks : list nat) (prev : Step),
    adjacent_pairs (cons prev (phase_chain ks entry_path))
    = app (phase_pairs prev ks DomainAddressable) entry_pairs.
Proof.
  intros ks. induction ks as [ | k rest IH ]; intros prev.
  - reflexivity.
  - change (phase_chain (cons k rest) entry_path)
      with (cons (PhaseDischarge k) (cons (PhaseDwell k)
             (cons (PhaseRead k) (phase_chain rest entry_path)))).
    rewrite adjacent_pairs_cons. rewrite adjacent_pairs_cons. rewrite adjacent_pairs_cons.
    rewrite (IH (PhaseRead k)). reflexivity.
Qed.

(* In a list without repeats, every consecutive pair is in order. *)
Lemma precedes_prefix :
  forall (p q : Step) (a l : list Step),
    occurs p a = false -> occurs q a = false ->
    precedes p q l = true -> precedes p q (app a l) = true.
Proof.
  intros p q a. induction a as [ | x a' IH ]; intros l Hp Hq H.
  - exact H.
  - simpl in Hp. simpl in Hq.
    destruct (orb_split _ _ Hp) as [ Hpx Hp' ].
    destruct (orb_split _ _ Hq) as [ Hqx Hq' ].
    simpl. rewrite Hqx. rewrite Hpx. exact (IH l Hp' Hq' H).
Qed.

Lemma precedes_head :
  forall (p q : Step) (l : list Step),
    step_eqb q p = false -> occurs q l = true -> precedes p q (cons p l) = true.
Proof.
  intros p q l Hqp Hq. simpl. rewrite Hqp. rewrite step_eqb_refl. exact Hq.
Qed.

Lemma nodup_steps_suffix :
  forall a l : list Step, nodup_steps (app a l) = true -> nodup_steps l = true.
Proof.
  intros a. induction a as [ | x a' IH ]; intros l H.
  - exact H.
  - simpl in H. destruct (andb_split _ _ H) as [ _ H' ]. exact (IH l H').
Qed.

Lemma nodup_steps_head_absent :
  forall (a l : list Step) (x : Step),
    nodup_steps (app a (cons x l)) = true -> occurs x a = false.
Proof.
  intros a. induction a as [ | z a' IH ]; intros l x H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hz Hrest ].
    apply negb_true in Hz. rewrite occurs_app in Hz.
    destruct (orb_split _ _ Hz) as [ _ Hzx ]. simpl in Hzx.
    destruct (orb_split _ _ Hzx) as [ Hzx' _ ].
    simpl. rewrite (step_eqb_sym x z). rewrite Hzx'. rewrite (IH l x Hrest).
    reflexivity.
Qed.

Lemma adjacent_precede_from :
  forall (l a : list Step),
    nodup_steps (app a l) = true ->
    all_of (pair_precedes (app a l)) (adjacent_pairs l) = true.
Proof.
  intros l. induction l as [ | x r IH ]; intros a H.
  - reflexivity.
  - destruct r as [ | y r' ].
    + reflexivity.
    + simpl. apply andb_join.
      * unfold pair_precedes. simpl. apply precedes_prefix.
        -- exact (nodup_steps_head_absent a (cons y r') x H).
        -- rewrite <- (app_snoc Step a x (cons y r')) in H.
           assert (Hy : occurs y (app a (cons x nil)) = false)
             by exact (nodup_steps_head_absent (app a (cons x nil)) r' y H).
           rewrite occurs_app in Hy. destruct (orb_split _ _ Hy) as [ Hy' _ ]. exact Hy'.
        -- apply precedes_head.
           ++ assert (Hs : nodup_steps (cons x (cons y r')) = true)
                by exact (nodup_steps_suffix a (cons x (cons y r')) H).
              simpl in Hs. destruct (andb_split _ _ Hs) as [ Hx _ ].
              apply negb_true in Hx. destruct (orb_split _ _ Hx) as [ Hxy _ ].
              rewrite (step_eqb_sym y x). exact Hxy.
           ++ simpl. rewrite step_eqb_refl. reflexivity.
      * rewrite <- (app_snoc Step a x (cons y r')). apply IH.
        rewrite (app_snoc Step a x (cons y r')). exact H.
Qed.

Lemma adjacent_precede :
  forall l : list Step,
    nodup_steps l = true -> all_of (pair_precedes l) (adjacent_pairs l) = true.
Proof. intros l H. exact (adjacent_precede_from l nil H). Qed.

(* -------------------------------------------------------------------------
   What the specification's list carries. A step of a phase the list does
   not name stands in it only where the tail or the latch puts it, and a
   list over distinct phases repeats nothing.
   ------------------------------------------------------------------------- *)

Lemma occurs_staggered_absent :
  forall (s : Step) (r : Readings) (ks : list nat) (tail : list Step),
    names_a_phase ks s = false ->
    occurs s (staggered r ks tail)
    = (if all_of r ks then occurs s tail else occurs s (cons FailStopLatch nil)).
Proof.
  intros s r ks tail. induction ks as [ | k rest IH ]; intros H.
  - reflexivity.
  - destruct s; simpl in H; simpl;
      try (destruct (orb_split _ _ H) as [ Hk Hr ]; rewrite Hk);
      destruct (r k); simpl; first [ exact (IH Hr) | exact (IH H) | reflexivity ].
Qed.

Lemma nodup_staggered :
  forall (r : Readings) (ks : list nat),
    nodup_nat ks = true -> nodup_steps (staggered r ks entry_path) = true.
Proof.
  intros r ks. induction ks as [ | k rest IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hk Hrest ]. apply negb_true in Hk.
    simpl. destruct (r k).
    + rewrite (occurs_staggered_absent (PhaseDischarge k) r rest entry_path Hk).
      rewrite (occurs_staggered_absent (PhaseDwell k) r rest entry_path Hk).
      rewrite (occurs_staggered_absent (PhaseRead k) r rest entry_path Hk).
      rewrite (IH Hrest). destruct (all_of r rest); reflexivity.
    + reflexivity.
Qed.

Lemma nodup_admission_sequence :
  forall (ks : list nat) (r : Readings),
    nodup_nat ks = true -> nodup_steps (admission_sequence ks r) = true.
Proof.
  intros ks r H. unfold admission_sequence. simpl.
  rewrite (occurs_staggered_absent RequestersInReset r ks entry_path eq_refl).
  rewrite (nodup_staggered r ks H). destruct (all_of r ks); reflexivity.
Qed.

Lemma nodup_success_path : forall n : nat, nodup_steps (success_path (upto n)) = true.
Proof.
  intros n. rewrite <- admission_sequence_positive.
  exact (nodup_admission_sequence (upto n) all_positive (nodup_upto n)).
Qed.

(* A phase the list names has each of its three steps on the success path. *)
Lemma occurs_phase_step_chain :
  forall (j : nat) (ks : list nat) (tail : list Step),
    mem_nat j ks = true ->
    occurs (PhaseDischarge j) (phase_chain ks tail) = true
    /\ occurs (PhaseDwell j) (phase_chain ks tail) = true
    /\ occurs (PhaseRead j) (phase_chain ks tail) = true.
Proof.
  intros j ks tail. induction ks as [ | k rest IH ]; simpl; intros H.
  - discriminate H.
  - destruct (Nat.eqb j k) eqn:E.
    + split; [ reflexivity | split; reflexivity ].
    + simpl in H. destruct (IH H) as [ H1 [ H2 H3 ] ].
      rewrite H1. rewrite H2. rewrite H3.
      split; [ reflexivity | split; reflexivity ].
Qed.

(* An entry step stands on the exit path exactly where every reading was
   positive: this is the sequencer's half of the meeting below. *)
Lemma occurs_entry_staggered :
  forall (s : Step) (r : Readings) (ks : list nat) (tail : list Step),
    is_entry_step s = true ->
    occurs s (staggered r ks tail) = andb (all_of r ks) (occurs s tail).
Proof.
  intros s r ks tail Hs. induction ks as [ | k rest IH ]; simpl.
  - reflexivity.
  - destruct s; try discriminate Hs; simpl;
      destruct (r k); simpl; first [ exact IH | reflexivity ].
Qed.

Lemma occurs_latch_staggered :
  forall (r : Readings) (ks : list nat) (tail : list Step),
    occurs FailStopLatch (staggered r ks tail)
    = (if all_of r ks then occurs FailStopLatch tail else true).
Proof.
  intros r ks tail. induction ks as [ | k rest IH ]; simpl.
  - reflexivity.
  - destruct (r k); simpl. exact IH. reflexivity.
Qed.

(* The same two facts at the sequence: an entry step stands on the
   specification's sequence exactly where every reading was positive, and
   the latch exactly where one was not. *)
Lemma occurs_entry_admission :
  forall (s : Step) (r : Readings) (ks : list nat),
    is_entry_step s = true -> occurs s (admission_sequence ks r) = all_of r ks.
Proof.
  intros s r ks Hs. unfold admission_sequence.
  destruct s; try discriminate Hs; simpl;
    rewrite (occurs_entry_staggered _ r ks entry_path Hs);
    destruct (all_of r ks); reflexivity.
Qed.

Lemma occurs_latch_admission :
  forall (r : Readings) (ks : list nat),
    occurs FailStopLatch (admission_sequence ks r) = negb (all_of r ks).
Proof.
  intros r ks. unfold admission_sequence. simpl.
  rewrite (occurs_latch_staggered r ks entry_path).
  destruct (all_of r ks); reflexivity.
Qed.

(* Wherever a phase is read, its read follows its dwell and its dwell its
   discharge, on every reading and whatever the phase list. *)
Lemma staggered_phase_shape :
  forall (r : Readings) (k : nat) (ks : list nat),
    occurs (PhaseRead k) (staggered r ks entry_path) = true ->
    precedes (PhaseDischarge k) (PhaseDwell k) (staggered r ks entry_path) = true
    /\ precedes (PhaseDwell k) (PhaseRead k) (staggered r ks entry_path) = true.
Proof.
  intros r k ks. induction ks as [ | k' rest IH ]; intros H.
  - discriminate H.
  - simpl in H. simpl. destruct (Nat.eqb k k') eqn:E.
    + split; reflexivity.
    + simpl in H. simpl. destruct (r k').
      * exact (IH H).
      * discriminate H.
Qed.

(* D1 (R-15-247d, R-15-247g): the specification is ordered at every phase
   count, and not only at the demo's. *)
Theorem specification_is_ordered :
  forall n : nat, Ordered (upto n) (admission_sequence (upto n) all_positive).
Proof.
  intros n. unfold Ordered, ordered_ok, required_order.
  rewrite admission_sequence_positive. unfold success_path.
  rewrite <- (required_order_is_adjacency (upto n) RequestersInReset).
  apply adjacent_precede. exact (nodup_success_path n).
Qed.

(* D1a (R-15-247d, R-17-024a, R-17-058f): the two boundaries are separated
   by name rather than reconciled. The authority boundary is read, and on
   a negative reading refused, without the residue boundary or
   addressability being reached at all: whatever phase the schedule begins
   at, its read stands on the negative arm and neither entry step does. *)
Theorem authority_invalidation_is_independent_of_residue_sanitization :
  forall (k : nat) (rest : list nat),
    occurs (PhaseRead k) (admission_sequence (cons k rest) (fun _ => false)) = true
    /\ occurs ResidueConfirmed (admission_sequence (cons k rest) (fun _ => false)) = false
    /\ occurs DomainAddressable (admission_sequence (cons k rest) (fun _ => false)) = false.
Proof.
  intros k rest. split; [ | split ]; simpl.
  - rewrite nat_eqb_refl. reflexivity.
  - reflexivity.
  - reflexivity.
Qed.

(* D1b (R-15-247d's one pass): on the success path the residue boundary is
   crossed on the confirmation already held, addressability, the boundary
   and measured execution standing in that order with no discharge, dwell
   or read between them; that is the order's own last two conjuncts, and
   the second-pass sequencer below is what the count refuses. *)
Theorem the_success_path_carries_no_second_pass :
  forall n : nat,
    precedes DomainAddressable ResidueConfirmed (admission_sequence (upto n) all_positive)
    = true
    /\ precedes ResidueConfirmed MeasuredExecution (admission_sequence (upto n) all_positive)
       = true.
Proof.
  intros n.
  assert (H := specification_is_ordered n). unfold Ordered, ordered_ok, required_order in H.
  rewrite all_of_app in H. destruct (andb_split _ _ H) as [ _ He ].
  unfold entry_pairs in He. simpl in He. destruct (andb_split _ _ He) as [ H1 H2 ].
  destruct (andb_split _ _ H2) as [ H3 _ ].
  split; [ exact H1 | exact H3 ].
Qed.

(* =========================================================================
   The generated weakenings (R-05-166). A refutation is a seeded weakening
   the theorem must reject, so these four generators produce families of
   them from the specification's own success path rather than a person
   authoring each. The theorems quantify over the index; the Examples check
   the whole family by conversion and print nothing. The families are
   generated at the demo machine's two phases, whose success path is ten
   steps long; the specification's own obligations above and below are
   proved at every phase count.
   ========================================================================= *)

(* Transpose the adjacent pair at n: the natural wrong move on an ordered
   sequence, and one weakening per adjacent position. *)
Fixpoint swap_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

(* Delete the step at n: a step omitted rather than reordered. *)
Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
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
Fixpoint suffix_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => l
  | S k, cons _ r => suffix_at k r
  | S _, nil => nil
  end.

(* Insert a step at n: with a phase's read, the poll-until-done loop and
   the retry R-15-247f refuses, one weakening per position per phase. *)
Fixpoint insert_at {A : Type} (n : nat) (p : A) (l : list A) : list A :=
  match n, l with
  | 0, _ => cons p l
  | S k, cons a r => cons a (insert_at k p r)
  | S _, nil => cons p nil
  end.

(* R-15-247f's literal: one read, per phase. *)
Definition single_read_ok (ks : list nat) (l : list Step) : bool :=
  all_of (fun k => Nat.eqb (occurrences (PhaseRead k) l) 1) ks.

(* And R-15-247f's shape within a phase, as the boolean the refuters'
   keeps-theorems are checked against. *)
Definition phase_shape_ok (ks : list nat) (l : list Step) : bool :=
  all_of (fun k => andb (precedes (PhaseDischarge k) (PhaseDwell k) l)
                        (precedes (PhaseDwell k) (PhaseRead k) l)) ks.

Lemma all_of_by_mem :
  forall (p : nat -> bool) (ks : list nat),
    (forall k : nat, mem_nat k ks = true -> p k = true) -> all_of p ks = true.
Proof.
  intros p ks. induction ks as [ | k rest IH ]; intros H.
  - reflexivity.
  - simpl. apply andb_join.
    + apply H. simpl. rewrite nat_eqb_refl. reflexivity.
    + apply IH. intros j Hj. apply H. simpl. rewrite Hj.
      destruct (Nat.eqb j k); reflexivity.
Qed.

(* The specification is a single read at every phase count, which is what
   makes the extra-read family below a refusal of the weakening rather
   than of the check: a comparison against any count but one would refuse
   the specification too. *)
Theorem specification_is_a_single_read :
  forall n : nat,
    single_read_ok (upto n) (admission_sequence (upto n) all_positive) = true.
Proof.
  intros n. unfold single_read_ok. rewrite admission_sequence_positive.
  apply all_of_by_mem. intros k Hk. cbv beta.
  rewrite (nodup_once (success_path (upto n)) (PhaseRead k) (nodup_success_path n)).
  - reflexivity.
  - destruct (occurs_phase_step_chain k (upto n) entry_path Hk) as [ _ [ _ H3 ] ].
    unfold success_path. simpl. exact H3.
Qed.

Definition transpositions (l : list Step) : list (list Step) :=
  map_over (fun n => swap_at n l) (upto (before_last (count_of l))).

Definition deletions (l : list Step) : list (list Step) :=
  map_over (fun n => drop_at n l) (upto (count_of l)).

Definition proper_suffixes (l : list Step) : list (list Step) :=
  map_over (fun n => suffix_at (S n) l) (upto (count_of l)).

Definition extra_reads (ks : list nat) (l : list Step) : list (list Step) :=
  flatten (map_over (fun k => map_over (fun n => insert_at n (PhaseRead k) l)
                                       (upto (S (count_of l))))
                    ks).

Definition generated_weakenings (ks : list nat) (l : list Step) : list (list Step) :=
  app (transpositions l)
      (app (deletions l) (app (proper_suffixes l) (extra_reads ks l))).

Definition demo_phases : list nat := upto 2.

Definition demo_sequence : list Step := admission_sequence demo_phases all_positive.

(* The family's size is computed rather than claimed: nine transpositions,
   ten deletions, ten proper suffixes, and eleven extra reads for each of
   two phases. *)
Example generated_family_size :
  count_of (generated_weakenings demo_phases demo_sequence) = 51 := eq_refl.

(* And a family is empty where the sequence has nothing for it to weaken:
   a sequence of no steps or of one has no adjacent pair, so the
   transposition family over it is empty rather than a list carrying the
   sequence itself, which is what keeps every member a weakening. *)
Example no_transposition_of_a_sequence_with_no_adjacent_pair :
  transpositions nil = nil
  /\ transpositions (cons RequestersInReset nil) = nil := conj eq_refl eq_refl.

(* D2: every generated weakening fails the order or the single read. One
   conversion over the whole family. *)
Example every_generated_weakening_is_refused :
  all_of (fun w => negb (andb (ordered_ok demo_phases w) (single_read_ok demo_phases w)))
         (generated_weakenings demo_phases demo_sequence) = true := eq_refl.

(* D2a: and per family, so a family that stopped biting is visible rather
   than absorbed by the conjunction above. *)
Example every_transposition_is_out_of_order :
  all_of (fun w => negb (ordered_ok demo_phases w))
         (transpositions demo_sequence) = true := eq_refl.

Example every_deletion_is_out_of_order :
  all_of (fun w => negb (ordered_ok demo_phases w))
         (deletions demo_sequence) = true := eq_refl.

Example every_proper_suffix_is_out_of_order :
  all_of (fun w => negb (ordered_ok demo_phases w))
         (proper_suffixes demo_sequence) = true := eq_refl.

Example every_extra_read_is_not_a_single_read :
  all_of (fun w => negb (single_read_ok demo_phases w))
         (extra_reads demo_phases demo_sequence) = true := eq_refl.

(* D2b: the same content as a quantifier over the index rather than an
   enumeration, so the family is refused for a reason rather than by a
   computation over the nine, ten and eleven members it happens to have. *)
Theorem no_adjacent_transposition_is_ordered :
  forall n : nat, Nat.ltb n 9 = true ->
    ordered_ok demo_phases (swap_at n demo_sequence) = false.
Proof.
  intros n.
  destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_deletion_is_ordered :
  forall n : nat, Nat.ltb n 10 = true ->
    ordered_ok demo_phases (drop_at n demo_sequence) = false.
Proof.
  intros n.
  destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_proper_suffix_is_ordered :
  forall n : nat, Nat.ltb n 10 = true ->
    ordered_ok demo_phases (suffix_at (S n) demo_sequence) = false.
Proof.
  intros n.
  destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_extra_read_is_a_single_read :
  forall k n : nat, Nat.ltb k 2 = true -> Nat.ltb n 11 = true ->
    single_read_ok demo_phases (insert_at n (PhaseRead k) demo_sequence) = false.
Proof.
  intros k n. destruct k as [ | [ | k ] ]; intros Hk; try discriminate Hk;
    destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* -------------------------------------------------------------------------
   No conjunct of the order is dead. M0.16's finding is that a validator
   arm placed after another inherits what that one already refuses, so a
   message it repeats is unreachable rather than redundant; the same defect
   in a conjunction is a clause that decides nothing. Each of the nine
   adjacent transpositions breaks exactly one conjunct, which is that
   property computed rather than asserted.
   ------------------------------------------------------------------------- *)

Definition failing_conjuncts (ks : list nat) (l : list Step) : nat :=
  count_of (filter_of (fun pq => negb (pair_precedes l pq)) (required_order ks)).

Example each_conjunct_of_the_order_decides :
  map_over (failing_conjuncts demo_phases) (transpositions demo_sequence)
  = cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 nil))))))))
  := eq_refl.

(* And the specification breaks none of them, so the count above is a
   measure of the weakening rather than of the check. *)
Example the_specification_breaks_no_conjunct :
  failing_conjuncts demo_phases demo_sequence = 0 := eq_refl.

(* =========================================================================
   The sequencer: a function of the phase list and the readings (reading
   2). The obligations are stated of an arbitrary one, so an alternative
   construction can be exhibited and refuted rather than merely differing
   from the specification.
   ========================================================================= *)

Definition Sequencer : Type := list nat -> Readings -> list Step.

Definition spec_sequencer : Sequencer := admission_sequence.

(* R-15-247d and R-15-247g, at every phase count. *)
Definition KeepsTheOrder (q : Sequencer) : Prop :=
  forall n : nat, Ordered (upto n) (q (upto n) all_positive).

(* R-15-247f fail-closed, and R-15-247d's "before any requester may name
   the domain": on a negative reading at any phase the domain is never
   addressable, never crosses the residue boundary, and never enters
   measured execution. *)
Definition StopsOnNegativeReading (q : Sequencer) : Prop :=
  forall (ks : list nat) (r : Readings), all_of r ks = false ->
    occurs DomainAddressable (q ks r) = false
    /\ occurs ResidueConfirmed (q ks r) = false
    /\ occurs MeasuredExecution (q ks r) = false.

(* R-17-030n: a negative reading reaches the latch, and none does
   otherwise. Both halves, because a sequencer that latches on every
   reading satisfies the first alone and is not a fail-stop. *)
Definition LatchesOnNegativeReading (q : Sequencer) : Prop :=
  (forall (ks : list nat) (r : Readings),
      all_of r ks = false -> occurs FailStopLatch (q ks r) = true)
  /\ (forall (ks : list nat) (r : Readings),
      all_of r ks = true -> occurs FailStopLatch (q ks r) = false).

(* R-15-247f's "a single read" and "no retry" and R-15-247d's one pass, as
   one bound on every reading: no discharge, dwell, read or boundary stands
   twice, the negative reading stopping the transition rather than
   repeating any part of it. *)
Definition NoStepStandsTwice (q : Sequencer) : Prop :=
  forall (n : nat) (r : Readings) (s : Step),
    Nat.leb (occurrences s (q (upto n) r)) 1 = true.

(* And on the positive reading every phase's discharge, dwell and read
   stands exactly once, which is what refuses a sequencer that reads one
   phase for the whole transition. *)
Definition EveryPhaseStepStandsOnce (q : Sequencer) : Prop :=
  forall (n : nat) (s : Step) (j : nat),
    phase_index s = Some j -> Nat.ltb j n = true ->
    occurrences s (q (upto n) all_positive) = 1.

(* R-15-247f's "a fixed worst-corner dwell followed by a single read", as
   an order within every phase that is read, on every reading. *)
Definition ReadFollowsTheDwell (q : Sequencer) : Prop :=
  forall (ks : list nat) (r : Readings) (k : nat),
    occurs (PhaseRead k) (q ks r) = true ->
    precedes (PhaseDischarge k) (PhaseDwell k) (q ks r) = true
    /\ precedes (PhaseDwell k) (PhaseRead k) (q ks r) = true.

(* D3 through D8: the specification meets all six, at every phase count. *)
Theorem specification_keeps_the_order : KeepsTheOrder spec_sequencer.
Proof. exact specification_is_ordered. Qed.

Theorem specification_stops_on_a_negative_reading :
  StopsOnNegativeReading spec_sequencer.
Proof.
  intros ks r H. unfold spec_sequencer. split; [ | split ].
  - rewrite (occurs_entry_admission DomainAddressable r ks eq_refl). exact H.
  - rewrite (occurs_entry_admission ResidueConfirmed r ks eq_refl). exact H.
  - rewrite (occurs_entry_admission MeasuredExecution r ks eq_refl). exact H.
Qed.

Theorem specification_latches_on_a_negative_reading :
  LatchesOnNegativeReading spec_sequencer.
Proof.
  split; intros ks r H; unfold spec_sequencer;
    rewrite (occurs_latch_admission r ks); rewrite H; reflexivity.
Qed.

Theorem specification_stands_no_step_twice : NoStepStandsTwice spec_sequencer.
Proof.
  intros n r s.
  exact (nodup_at_most_once _ s (nodup_admission_sequence (upto n) r (nodup_upto n))).
Qed.

Theorem specification_stands_each_phase_step_once :
  EveryPhaseStepStandsOnce spec_sequencer.
Proof.
  intros n s j Hs Hj. unfold spec_sequencer. rewrite admission_sequence_positive.
  apply (nodup_once (success_path (upto n)) s (nodup_success_path n)).
  assert (Hm : mem_nat j (upto n) = true) by (rewrite mem_upto; exact Hj).
  destruct (occurs_phase_step_chain j (upto n) entry_path Hm) as [ H1 [ H2 H3 ] ].
  unfold success_path.
  destruct s; try discriminate Hs; inversion Hs; subst; simpl; assumption.
Qed.

Theorem specification_reads_after_the_dwell : ReadFollowsTheDwell spec_sequencer.
Proof.
  intros ks r k H. unfold spec_sequencer, admission_sequence in *.
  simpl in H. simpl. exact (staggered_phase_shape r k ks H).
Qed.

(* =========================================================================
   Refutation witnesses over the sequencer (R-05-166). Each is an
   alternative construction the register's own sentence excludes, and each
   is shown to satisfy the obligations it does not break, so what refutes
   it is the named defect rather than the shape of the construction. Where
   a refuter's keeps-fact is checked at the demo's two phases rather than
   proved at every count, it is a closed computation and says so.
   ========================================================================= *)

(* A sequence that reads each phase's completion before its dwell has
   elapsed. R-15-247f puts the read after a fixed worst-corner dwell, so
   this one reads an indication whose settling the dwell exists to
   guarantee. *)
Fixpoint eager_staggered (r : Readings) (ks : list nat) (tail : list Step) : list Step :=
  match ks with
  | nil => tail
  | cons k rest =>
      cons (PhaseDischarge k) (cons (PhaseRead k) (cons (PhaseDwell k)
        (if r k then eager_staggered r rest tail else cons FailStopLatch nil)))
  end.

Definition eager_read_sequencer : Sequencer := fun ks r =>
  cons RequestersInReset (eager_staggered r ks entry_path).

Theorem eager_read_refutes_the_dwell_order :
  ~ ReadFollowsTheDwell eager_read_sequencer.
Proof.
  intros H. destruct (H (upto 1) all_positive 0 eq_refl) as [ _ H2 ]. discriminate H2.
Qed.

(* And it repeats nothing and admits exactly on the positive reading, so
   what refutes it is the position of the read and not its count: the two
   obligations are independent. Checked at the demo's two phases over every
   reading. *)
Theorem eager_read_still_reads_once_and_stops :
  forall r : Readings,
    nodup_steps (eager_read_sequencer demo_phases r) = true
    /\ occurs DomainAddressable (eager_read_sequencer demo_phases r) = all_of r demo_phases.
Proof.
  intros r. simpl. destruct (r 0); destruct (r 1); split; reflexivity.
Qed.

(* The same refutation in the boolean form the keeps-facts are checked
   against, and it is what makes `phase_shape_ok` a conjunction rather
   than a disjunction: the eager read keeps the discharge before the dwell
   and breaks the dwell before the read, so a check answering on either
   conjunct alone would admit it. *)
Example eager_read_breaks_the_phase_shape :
  precedes (PhaseDischarge 0) (PhaseDwell 0)
           (eager_read_sequencer demo_phases all_positive) = true
  /\ phase_shape_ok demo_phases (eager_read_sequencer demo_phases all_positive) = false
  := conj eq_refl eq_refl.

(* A sequence that polls rather than reading once. R-15-247f admits no
   poll-until-done loop; its Accept clause says why, a poll making
   transition time a function of temperature, charge state, and what the
   bank held. *)
Fixpoint polling_staggered (r : Readings) (ks : list nat) (tail : list Step) : list Step :=
  match ks with
  | nil => tail
  | cons k rest =>
      cons (PhaseDischarge k) (cons (PhaseDwell k)
      (cons (PhaseRead k) (cons (PhaseRead k) (cons (PhaseRead k)
        (if r k then polling_staggered r rest tail else cons FailStopLatch nil)))))
  end.

Definition polling_sequencer : Sequencer := fun ks r =>
  cons RequestersInReset (polling_staggered r ks entry_path).

Theorem polling_refutes_the_single_read : ~ NoStepStandsTwice polling_sequencer.
Proof. intros H. specialize (H 1 all_positive (PhaseRead 0)). discriminate H. Qed.

(* The poll keeps the order and reads after the dwell, so the order alone
   does not carry R-15-247f's single-read rule and the count is doing work
   the position cannot do. *)
Example polling_still_keeps_the_order_and_reads_after_the_dwell :
  ordered_ok demo_phases (polling_sequencer demo_phases all_positive) = true
  /\ phase_shape_ok demo_phases (polling_sequencer demo_phases all_positive) = true
  := conj eq_refl eq_refl.

(* A sequence that retries: on a negative reading it discharges the phase
   again, dwells again, reads again, and continues as though the second
   reading were positive. R-15-247f's fail-closed line stops the
   transition rather than repeating it. *)
Fixpoint retrying_staggered (r : Readings) (ks : list nat) (tail : list Step) : list Step :=
  match ks with
  | nil => tail
  | cons k rest =>
      cons (PhaseDischarge k) (cons (PhaseDwell k) (cons (PhaseRead k)
        (if r k then retrying_staggered r rest tail
         else cons (PhaseDischarge k) (cons (PhaseDwell k) (cons (PhaseRead k)
                (retrying_staggered r rest tail))))))
  end.

Definition retrying_sequencer : Sequencer := fun ks r =>
  cons RequestersInReset (retrying_staggered r ks entry_path).

Theorem retrying_refutes_the_no_retry_rule :
  ~ NoStepStandsTwice retrying_sequencer.
Proof.
  intros H. specialize (H 1 (fun _ => false) (PhaseDischarge 0)). discriminate H.
Qed.

Theorem retrying_refutes_the_fail_stop_arm :
  ~ StopsOnNegativeReading retrying_sequencer
  /\ ~ LatchesOnNegativeReading retrying_sequencer.
Proof.
  split.
  - intros H. destruct (H (upto 1) (fun _ => false) eq_refl) as [ H1 _ ]. discriminate H1.
  - intros [ H _ ]. specialize (H (upto 1) (fun _ => false) eq_refl). discriminate H.
Qed.

(* The retry is invisible to the order, both arms of it being ordered on
   first occurrences, so R-15-247d's ordering does not carry R-15-247f's
   no-retry rule and the two are separate obligations rather than one
   stated twice. *)
Theorem the_retry_is_ordered_and_still_refused :
  Ordered demo_phases (retrying_sequencer demo_phases (fun _ => false))
  /\ ~ NoStepStandsTwice retrying_sequencer.
Proof.
  split.
  - reflexivity.
  - exact retrying_refutes_the_no_retry_rule.
Qed.

(* A sequence that admits the domain whatever the readings: the arm
   R-15-247f's fail-closed line and R-17-030n exist to remove. *)
Definition optimistic_sequencer : Sequencer := fun ks _ => success_path ks.

Theorem optimistic_refutes_the_fail_stop_arm :
  ~ StopsOnNegativeReading optimistic_sequencer
  /\ ~ LatchesOnNegativeReading optimistic_sequencer.
Proof.
  split.
  - intros H. destruct (H (upto 1) (fun _ => false) eq_refl) as [ H1 _ ]. discriminate H1.
  - intros [ H _ ]. specialize (H (upto 1) (fun _ => false) eq_refl). discriminate H.
Qed.

(* It is ordered, repeats nothing, stands each phase step once, and reads
   after the dwell, at every phase count, so every other obligation in
   this file is silent about it and the arm is the only thing that refuses
   it. That is what makes the arm content. *)
Theorem the_optimistic_sequencer_passes_everything_else :
  KeepsTheOrder optimistic_sequencer
  /\ NoStepStandsTwice optimistic_sequencer
  /\ EveryPhaseStepStandsOnce optimistic_sequencer
  /\ ReadFollowsTheDwell optimistic_sequencer.
Proof.
  split; [ | split; [ | split ] ].
  - intros n. unfold optimistic_sequencer. rewrite <- admission_sequence_positive.
    exact (specification_is_ordered n).
  - intros n r s. unfold optimistic_sequencer.
    exact (nodup_at_most_once _ s (nodup_success_path n)).
  - intros n s j Hs Hj. unfold optimistic_sequencer.
    rewrite <- admission_sequence_positive.
    exact (specification_stands_each_phase_step_once n s j Hs Hj).
  - intros ks r k H. unfold optimistic_sequencer in *.
    rewrite <- admission_sequence_positive in *.
    exact (specification_reads_after_the_dwell ks all_positive k H).
Qed.

(* A sequencer that names one boundary and not two, reaching measured
   execution with no residue boundary at all. R-17-024a and R-15-247d make
   those two boundaries and not one, one pass notwithstanding: the pass is
   one act and the guarantees it discharges are owed at two points. *)
Definition one_confirmation_sequencer : Sequencer := fun ks r =>
  cons RequestersInReset
    (staggered r ks (cons DomainAddressable (cons MeasuredExecution nil))).

Theorem one_confirmation_refutes_the_two_boundaries :
  ~ KeepsTheOrder one_confirmation_sequencer.
Proof. intros H. specialize (H 1). discriminate H. Qed.

(* It stops and latches exactly as the specification does, at every phase
   count, so what refuses it is the missing boundary alone. *)
Theorem one_confirmation_still_stops_and_latches :
  StopsOnNegativeReading one_confirmation_sequencer
  /\ LatchesOnNegativeReading one_confirmation_sequencer.
Proof.
  split.
  - intros ks r H. unfold one_confirmation_sequencer. split; [ | split ]; simpl.
    + rewrite (occurs_entry_staggered DomainAddressable r ks _ eq_refl). rewrite H.
      reflexivity.
    + rewrite (occurs_entry_staggered ResidueConfirmed r ks _ eq_refl). rewrite H.
      reflexivity.
    + rewrite (occurs_entry_staggered MeasuredExecution r ks _ eq_refl). rewrite H.
      reflexivity.
  - split; intros ks r H; unfold one_confirmation_sequencer; simpl;
      rewrite (occurs_latch_staggered r ks _); rewrite H; reflexivity.
Qed.

(* A sequencer that runs the drain again at the residue boundary: a second
   discharge, dwell and read of every phase for the data plane after the
   domain is addressable. R-15-247d resolves its disjunction to one pass
   over both planes, so the transition carries one dwell and one read per
   phase and not two of each. *)
Definition second_pass_tail (r : Readings) (ks : list nat) : list Step :=
  cons DomainAddressable
    (staggered r ks (cons ResidueConfirmed (cons MeasuredExecution nil))).

Definition second_pass_sequencer : Sequencer := fun ks r =>
  cons RequestersInReset (staggered r ks (second_pass_tail r ks)).

Theorem second_pass_refutes_the_one_pass :
  ~ NoStepStandsTwice second_pass_sequencer
  /\ ~ EveryPhaseStepStandsOnce second_pass_sequencer.
Proof.
  split.
  - intros H. specialize (H 1 all_positive (PhaseDischarge 0)). discriminate H.
  - intros H. specialize (H 1 (PhaseDischarge 0) 0 eq_refl eq_refl). discriminate H.
Qed.

(* The second pass is ordered on first occurrences, and it stops and
   latches as the specification does, so what refutes it is the count and
   nothing else: R-15-247d's one pass is content of its own beside
   R-15-247d's order. *)
Theorem the_second_pass_is_ordered_and_stops :
  Ordered demo_phases (second_pass_sequencer demo_phases all_positive)
  /\ StopsOnNegativeReading second_pass_sequencer
  /\ LatchesOnNegativeReading second_pass_sequencer.
Proof.
  split; [ reflexivity | split ].
  - intros ks r H. unfold second_pass_sequencer. split; [ | split ].
    + change (occurs DomainAddressable (staggered r ks (second_pass_tail r ks)) = false).
      rewrite (occurs_entry_staggered DomainAddressable r ks (second_pass_tail r ks) eq_refl).
      rewrite H. reflexivity.
    + change (occurs ResidueConfirmed (staggered r ks (second_pass_tail r ks)) = false).
      rewrite (occurs_entry_staggered ResidueConfirmed r ks (second_pass_tail r ks) eq_refl).
      rewrite H. reflexivity.
    + change (occurs MeasuredExecution (staggered r ks (second_pass_tail r ks)) = false).
      rewrite (occurs_entry_staggered MeasuredExecution r ks (second_pass_tail r ks) eq_refl).
      rewrite H. reflexivity.
  - split; intros ks r H; unfold second_pass_sequencer.
    + change (occurs FailStopLatch (staggered r ks (second_pass_tail r ks)) = true).
      rewrite (occurs_latch_staggered r ks (second_pass_tail r ks)). rewrite H.
      reflexivity.
    + change (occurs FailStopLatch (staggered r ks (second_pass_tail r ks)) = false).
      rewrite (occurs_latch_staggered r ks (second_pass_tail r ks)). rewrite H.
      change (occurs FailStopLatch
                (staggered r ks (cons ResidueConfirmed (cons MeasuredExecution nil))) = false).
      rewrite (occurs_latch_staggered r ks (cons ResidueConfirmed (cons MeasuredExecution nil))).
      rewrite H. reflexivity.
Qed.

(* A sequencer that latches on every reading rather than on the negative
   one, which is a stopped machine and not a fail-stop: it satisfies the
   first half of the arm and fails the second, which is why the arm is
   stated as a pair. *)
Definition always_latching_sequencer : Sequencer := fun ks _ =>
  cons RequestersInReset (staggered (fun _ => false) ks entry_path).

Theorem always_latching_refutes_the_second_half_of_the_arm :
  (forall (ks : list nat) (r : Readings),
      all_of r ks = false -> occurs FailStopLatch (always_latching_sequencer ks r) = true)
  /\ ~ LatchesOnNegativeReading always_latching_sequencer.
Proof.
  split.
  - intros ks r H. destruct ks as [ | k rest ].
    + discriminate H.
    + reflexivity.
  - intros [ _ H ]. specialize (H (upto 1) all_positive eq_refl). discriminate H.
Qed.

(* A sequencer that discharges every phase and then dwells once and reads
   once for the whole transition, taking the domain's indication off the
   phase the schedule began at. This is the per-transition read R-15-247f
   refuses: the read is single per phase and not per transition, because
   the phase is the unit that has a completion fact. *)
Definition per_transition_sequencer : Sequencer := fun ks r =>
  cons RequestersInReset
    (app (map_over PhaseDischarge ks)
         (match ks with
          | nil => entry_path
          | cons k _ =>
              cons (PhaseDwell k) (cons (PhaseRead k)
                (if r k then entry_path else cons FailStopLatch nil))
          end)).

Theorem per_transition_refutes_the_read_per_phase :
  ~ EveryPhaseStepStandsOnce per_transition_sequencer
  /\ ~ KeepsTheOrder per_transition_sequencer.
Proof.
  split.
  - intros H. specialize (H 2 (PhaseRead 1) 1 eq_refl eq_refl). discriminate H.
  - intros H. specialize (H 2). discriminate H.
Qed.

(* It repeats nothing and stops on a negative reading of the phase it does
   read, so what refutes it is the phase it never reads. Checked at the
   demo's two phases over every reading. *)
Theorem the_per_transition_sequencer_reads_the_first_phase_once :
  forall r : Readings,
    nodup_steps (per_transition_sequencer demo_phases r) = true
    /\ occurs DomainAddressable (per_transition_sequencer demo_phases r) = r 0.
Proof.
  intros r. simpl. destruct (r 0); split; reflexivity.
Qed.

(* =========================================================================
   The sweep over banks, the phase reads composed from it, and R-15-247d's
   acceptance clause: no path admits a partially sanitized bank.
   ========================================================================= *)

Definition phases (m : Machine) : list nat := upto m.(phase_count).

(* The domain's banks, read off the schedule (reading 8). *)
Definition banks (m : Machine) : list m.(Bank) :=
  flatten (map_over m.(banks_of) (phases m)).

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

(* What phase k's read returns: the phase drained the banks it names. This
   is R-15-247f's completion indication at the arity that entry fixes, and
   it is the readings the sequencer above runs over. *)
Definition phase_drained (m : Machine) (sw : Sweep m) (k : nat) : bool :=
  all_of (bank_drained m sw) (m.(banks_of) k).

Definition phase_read (m : Machine) (sw : Sweep m) : Readings := phase_drained m sw.

Definition domain_drained (m : Machine) (sw : Sweep m) : bool :=
  all_of (bank_drained m sw) (banks m).

Definition no_partial_bank (m : Machine) (sw : Sweep m) : bool :=
  all_of (fun b => negb (bank_partial m sw b)) (banks m).

(* The transition's admission, as an arbitrary reader over the sweep
   (reading 4). The domain is addressable exactly where the reader
   confirms, so a reader is an admission judgment. *)
Definition Reader (m : Machine) : Type := Sweep m -> bool.

(* The specification's: every phase confirmed, each on its own read. *)
Definition spec_reader (m : Machine) : Reader m := fun sw =>
  all_of (phase_drained m sw) (phases m).

(* The reader R-15-247f calls sound and refuses on cost: one bit per bank. *)
Definition per_bank_reader (m : Machine) : Reader m := domain_drained m.

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

Lemma drained_domain_has_no_partial_bank :
  forall (m : Machine) (sw : Sweep m),
    domain_drained m sw = true -> no_partial_bank m sw = true.
Proof.
  intros m sw H. unfold no_partial_bank.
  apply (all_of_mono m.(Bank) (bank_drained m sw)
           (fun b => negb (bank_partial m sw b)) (banks m)).
  - intros b Hb. rewrite (drained_is_not_partial m sw b Hb). reflexivity.
  - exact H.
Qed.

(* D9 (R-15-247f): per phase and per bank agree on every sweep of every
   machine, which is the soundness that entry grants the per-bank read
   before refusing it on cost. The domain's banks being the phases' banks
   is what carries it (reading 8). *)
Theorem the_per_phase_reader_is_the_per_bank_reader :
  forall (m : Machine) (sw : Sweep m), spec_reader m sw = per_bank_reader m sw.
Proof.
  intros m sw. unfold spec_reader, per_bank_reader, domain_drained, banks.
  rewrite all_of_flatten_map. reflexivity.
Qed.

(* D10 (R-15-247d's acceptance clause), on the reader side: a reader
   answering for every phase admits no bank the pass reached and did not
   finish, and admits only drained domains. *)
Theorem specification_reader_admits_no_partially_sanitized_bank :
  forall m : Machine, AdmitsNoPartiallySanitizedBank m (spec_reader m).
Proof.
  intros m sw H. rewrite the_per_phase_reader_is_the_per_bank_reader in H.
  exact (drained_domain_has_no_partial_bank m sw H).
Qed.

Theorem specification_reader_admits_only_drained_domains :
  forall m : Machine, AdmitsOnlyDrainedDomains m (spec_reader m).
Proof.
  intros m sw H. rewrite the_per_phase_reader_is_the_per_bank_reader in H. exact H.
Qed.

(* -------------------------------------------------------------------------
   Where the sequencer and the reader meet. The path a machine takes on a
   sweep is the specification's sequencer run over that sweep's phase
   reads; the domain is addressable on it exactly where the specification's
   reader confirms; and so no path admits a partially sanitized bank, which
   is R-15-247d's acceptance clause stated of the sequence rather than of a
   reader alone, at every machine and every sweep.
   ------------------------------------------------------------------------- *)

Definition path (m : Machine) (q : Sequencer) (sw : Sweep m) : list Step :=
  q (phases m) (phase_read m sw).

Definition spec_path (m : Machine) (sw : Sweep m) : list Step :=
  path m spec_sequencer sw.

(* D11 (R-15-247f, R-15-189n): the RoT's gate on the transition is the
   conjunction of the phase readings (reading h). *)
Theorem admission_is_the_readers_confirmation :
  forall (m : Machine) (sw : Sweep m),
    occurs DomainAddressable (spec_path m sw) = spec_reader m sw.
Proof.
  intros m sw. unfold spec_path, path, spec_sequencer.
  rewrite (occurs_entry_admission DomainAddressable (phase_read m sw) (phases m) eq_refl).
  reflexivity.
Qed.

Theorem execution_is_the_readers_confirmation :
  forall (m : Machine) (sw : Sweep m),
    occurs MeasuredExecution (spec_path m sw) = spec_reader m sw.
Proof.
  intros m sw. unfold spec_path, path, spec_sequencer.
  rewrite (occurs_entry_admission MeasuredExecution (phase_read m sw) (phases m) eq_refl).
  reflexivity.
Qed.

(* D12 (R-15-247d, R-15-247f). The file's load-bearing theorem: on every
   machine and every sweep, a path that makes the domain addressable is
   one on which every bank drained and no bank was left half-swept. *)
Theorem no_path_admits_a_partially_sanitized_bank :
  forall (m : Machine) (sw : Sweep m),
    occurs DomainAddressable (spec_path m sw) = true ->
    domain_drained m sw = true /\ no_partial_bank m sw = true.
Proof.
  intros m sw H. rewrite admission_is_the_readers_confirmation in H.
  rewrite the_per_phase_reader_is_the_per_bank_reader in H.
  split.
  - exact H.
  - exact (drained_domain_has_no_partial_bank m sw H).
Qed.

Theorem no_path_executes_over_a_partially_sanitized_bank :
  forall (m : Machine) (sw : Sweep m),
    occurs MeasuredExecution (spec_path m sw) = true ->
    domain_drained m sw = true /\ no_partial_bank m sw = true.
Proof.
  intros m sw H. rewrite execution_is_the_readers_confirmation in H.
  rewrite <- admission_is_the_readers_confirmation in H.
  exact (no_path_admits_a_partially_sanitized_bank m sw H).
Qed.

(* -------------------------------------------------------------------------
   The demo machine, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Two phases of one bank each and two chunks per
   bank exercise every case the clauses distinguish: a bank drained, a
   bank the pass reached and did not finish, and a bank the pass never
   reached, that last being also a phase that read nothing. The dwell
   figure and the rosters are arbitrary witness values and carry no
   composition claim (item e).
   ------------------------------------------------------------------------- *)

Definition demo : Machine := {|
  Requester := bool;
  requesters := cons true (cons false nil);
  Bank := bool;
  phase_count := 2;
  banks_of := fun k => match k with 0 => cons true nil | _ => cons false nil end;
  Chunk := bool;
  chunks_of := fun _ => cons true (cons false nil);
  dwell_cycles := 9
|}.

(* Every chunk of every bank committed. *)
Definition sweep_clean : Sweep demo := fun _ _ => true.

(* The second phase's bank reached and not finished: one chunk committed
   and one did not, which is R-15-247d's partially sanitized bank. *)
Definition sweep_partial : Sweep demo := fun b c => if b then true else c.

(* The second phase's bank never reached at all: a phase that did not run
   rather than one that stopped halfway. *)
Definition sweep_missed : Sweep demo := fun b _ => b.

Example the_three_sweeps_are_distinguished :
  domain_drained demo sweep_clean = true
  /\ no_partial_bank demo sweep_clean = true
  /\ domain_drained demo sweep_partial = false
  /\ no_partial_bank demo sweep_partial = false
  /\ domain_drained demo sweep_missed = false
  /\ no_partial_bank demo sweep_missed = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* D12a (R-05-165): the specification's reader confirms on one sweep and
   refuses on another, so neither theorem above is proved from an empty
   antecedent and neither is a property every reader has. And the paths
   are the readings made visible: the clean sweep's path admits, the other
   two latch at the second phase. *)
Theorem the_specification_reader_confirms_and_refuses :
  spec_reader demo sweep_clean = true
  /\ spec_reader demo sweep_partial = false
  /\ spec_reader demo sweep_missed = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Example the_demo_paths_are_the_readings :
  spec_path demo sweep_clean = success_path demo_phases
  /\ spec_path demo sweep_partial
     = cons RequestersInReset (cons (PhaseDischarge 0) (cons (PhaseDwell 0)
       (cons (PhaseRead 0) (cons (PhaseDischarge 1) (cons (PhaseDwell 1)
       (cons (PhaseRead 1) (cons FailStopLatch nil)))))))
  /\ spec_path demo sweep_missed = spec_path demo sweep_partial :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   Refutation witnesses over the reader (R-05-166).
   ========================================================================= *)

(* A discharge confirmed per transition rather than per phase: the reader
   takes the domain's indication off the phase the schedule began at.
   R-15-247f refuses it by name, and this is the construction it refuses
   it on: the reader confirms exactly where the per-phase and per-bank
   readers refuse, so it admits a domain one of whose phases reached
   nothing. *)
Definition per_domain_reader (m : Machine) : Reader m := fun sw =>
  match phases m with
  | nil => true
  | cons k _ => phase_drained m sw k
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

(* And the per-transition sequencer above is that reader run as a
   sequence, at every machine and every sweep: its path makes the domain
   addressable exactly where the per-domain reader confirms, a schedule
   with no phase admitting on both sides, so the two are one construction
   stated twice rather than two constructions that happen to agree on the
   demo. *)
Lemma occurs_entry_discharges :
  forall (s : Step) (ks : list nat),
    is_entry_step s = true -> occurs s (map_over PhaseDischarge ks) = false.
Proof.
  intros s ks Hs. induction ks as [ | k rest IH ]; simpl.
  - reflexivity.
  - destruct s; try discriminate Hs; simpl; exact IH.
Qed.

Theorem the_per_transition_path_is_the_per_domain_reader :
  forall (m : Machine) (sw : Sweep m),
    occurs DomainAddressable (path m per_transition_sequencer sw)
    = per_domain_reader m sw.
Proof.
  intros m sw. unfold path, per_transition_sequencer, per_domain_reader, phase_read.
  destruct (phases m) as [ | k rest ].
  - reflexivity.
  - simpl. rewrite occurs_app.
    rewrite (occurs_entry_discharges DomainAddressable rest eq_refl).
    destruct (phase_drained m sw k); reflexivity.
Qed.

(* On the sweep that reached one phase and not the other, that path makes
   the domain addressable over an undrained bank, where the
   specification's path latches. This is the meeting theorem's refutation
   side. *)
Theorem the_per_transition_path_admits_an_undrained_bank :
  occurs DomainAddressable (path demo per_transition_sequencer sweep_missed) = true
  /\ domain_drained demo sweep_missed = false
  /\ occurs DomainAddressable (spec_path demo sweep_missed) = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* A reader that confirms as soon as every bank was reached rather than
   drained: the construction R-15-247d's acceptance clause names by its
   consequence. It is refuted by the same sweep at both clauses, so what
   refutes it is the bank left half-swept and not the reader's shape. *)
Definition touch_reader (m : Machine) : Reader m := fun sw =>
  all_of (bank_touched m sw) (banks m).

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
   R-15-247f's arity, made checkable rather than asserted. One read per
   transition, one per phase and one per bank are not observationally
   equal: on a sweep that reached one phase and not the other, the
   per-transition reader confirms where the per-phase reader refuses, and
   the per-phase and per-bank readers agree, here as everywhere.
   ------------------------------------------------------------------------- *)

Theorem the_reader_arity_is_observable :
  per_domain_reader demo sweep_missed = true
  /\ spec_reader demo sweep_missed = false
  /\ per_bank_reader demo sweep_missed = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* -------------------------------------------------------------------------
   And R-15-247d's second reading made checkable. Its acceptance clause is
   stated of a *partially* sanitized bank, which is a necessary condition
   and not the criterion: the reader that is exactly that clause admits a
   bank nothing reached, because a bank nothing reached is not partially
   sanitized. What excludes that admission is the completion read's own
   domain, so the clause and the read are two obligations and the clause
   alone does not carry the second.
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
   The dwell's shape: the dwell term is the machine's declared constant.

   What is stated here is where the number comes from and nothing about how
   either path's timing behaves. R-15-247f's timing clause quantifies over
   a discharge speed, a measured magnitude R-15-247m puts on a repaired
   megabit-class macro that no artifact here carries, and over the whole of
   the success and timeout paths rather than the dwell term alone. That
   clause is M3.6b and is not stated below; nothing here introduces a
   speed, a rate, or any quantity derived from leakage, which R-15-247c
   forbids a containment guarantee from resting on in any case.

   A dwell length is stated per read: a function of the sweep and of the
   reading the phase's read is about to return, which is the pair a
   construction could illegitimately consult. Whether the constant is one
   for every phase or one per phase is reading g.
   ========================================================================= *)

Definition DwellLength (m : Machine) : Type := Sweep m -> bool -> nat.

Definition spec_dwell (m : Machine) : DwellLength m := fun _ _ => m.(dwell_cycles).

Definition IsTheDeclaredConstant (m : Machine) (d : DwellLength m) : Prop :=
  forall (sw : Sweep m) (b : bool), d sw b = m.(dwell_cycles).

(* D13 (R-15-247f, R-15-247g): the dwell entering the transition budget is
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

(* A dwell that differs between the reading that will succeed and the one
   that will time out. It reads nothing of the array, so what refutes it is
   the arm alone, which is the half of R-15-247f's shape a construction can
   break without ever touching the sweep. *)
Definition arm_dependent_dwell (m : Machine) : DwellLength m :=
  fun _ b => if b then m.(dwell_cycles) else S m.(dwell_cycles).

Theorem arm_dependent_dwell_is_refuted :
  ~ IsTheDeclaredConstant demo (arm_dependent_dwell demo).
Proof.
  intros H. specialize (H sweep_clean false). discriminate H.
Qed.

(* =========================================================================
   The requesters, held in reset for the whole of the pass and released no
   earlier than addressability (R-15-247h, R-15-247d).
   ========================================================================= *)

Definition ResetHold (m : Machine) : Type := m.(Requester) -> bool.

Definition spec_hold (m : Machine) : ResetHold m := fun _ => true.

Definition HoldsEveryRequester (m : Machine) (h : ResetHold m) : Prop :=
  all_of h m.(requesters) = true.

(* D14 (R-15-247h): every requester the roster names, and R-15-247h names
   three classes rather than one (reading 5). *)
Theorem specification_holds_every_requester :
  forall m : Machine, HoldsEveryRequester m (spec_hold m).
Proof. intros m. apply all_of_true. Qed.

(* A reset that reaches one class and not another. R-15-247h's enumeration
   is every application core, every DMA engine, and every
   capability-bearing fabric initiator that can address the domain, so a
   hold exempting one of them is not the hold that entry states. *)
Definition class_exempt_hold : ResetHold demo := fun r => r.

Theorem class_exempt_hold_is_refuted :
  ~ HoldsEveryRequester demo class_exempt_hold.
Proof. intros H. discriminate H. Qed.

(* And it does reach one: the exempting hold holds some requester the
   roster names and not every one, so what refutes it is the class it
   exempts and not a hold that holds nothing. *)
Example the_class_exempt_hold_reaches_one_class :
  any_of class_exempt_hold demo.(requesters) = true := eq_refl.

(* Release, stated against the specification's own order: no requester is
   released at a step the success path puts before addressability. This is
   R-15-247d's "before any requester may name the domain" read as a
   constraint on the release schedule rather than on the sequence. *)
Definition ReleaseSchedule (m : Machine) : Type := m.(Requester) -> Step.

Definition spec_release (m : Machine) : ReleaseSchedule m := fun _ => DomainAddressable.

Definition NoRequesterNamesTheDomainEarly
    (m : Machine) (rel : ReleaseSchedule m) : Prop :=
  forall r : m.(Requester),
    precedes (rel r) DomainAddressable (success_path (phases m)) = false.

(* D15 (R-15-247d, R-15-247h), at every machine. *)
Theorem specification_releases_no_requester_early :
  forall m : Machine, NoRequesterNamesTheDomainEarly m (spec_release m).
Proof. intros m r. unfold spec_release. apply precedes_irrefl. Qed.

(* The early-release family, generated by quantifying over the step rather
   than by enumerating a mutation: every step the success path puts before
   addressability is a release schedule this refuses, and which steps
   those are is computed rather than listed. *)
Example the_steps_that_would_release_early_are_the_seven_before_addressability :
  filter_of (fun s => precedes s DomainAddressable (success_path (phases demo)))
            (success_path (phases demo))
  = cons RequestersInReset (cons (PhaseDischarge 0) (cons (PhaseDwell 0)
    (cons (PhaseRead 0) (cons (PhaseDischarge 1) (cons (PhaseDwell 1)
    (cons (PhaseRead 1) nil)))))) := eq_refl.

Theorem every_early_release_schedule_is_refused :
  forall s : Step,
    precedes s DomainAddressable (success_path (phases demo)) = true ->
    ~ NoRequesterNamesTheDomainEarly demo (fun _ => s).
Proof.
  intros s Hs Hno. specialize (Hno true). cbv beta in Hno.
  rewrite Hs in Hno. discriminate Hno.
Qed.

(* The concrete member of that family R-15-247h names outright: a requester
   released while a phase's discharge is still running. *)
Theorem a_requester_released_at_the_discharge_is_refused :
  ~ NoRequesterNamesTheDomainEarly demo (fun _ => PhaseDischarge 1).
Proof.
  apply every_early_release_schedule_is_refused. reflexivity.
Qed.

(* And the family is not everything: a release at the residue boundary or
   at measured execution is later than addressability and is admitted, so
   the obligation excludes something rather than refusing every schedule. *)
Theorem a_late_release_is_admitted :
  NoRequesterNamesTheDomainEarly demo (fun _ => ResidueConfirmed)
  /\ NoRequesterNamesTheDomainEarly demo (fun _ => MeasuredExecution).
Proof. split; intros r; reflexivity. Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`
   (tools/vos/cli/proofs.py): every shipped constant's enumerated
   assumption set is compared against the declared set R-05-164 currently
   makes empty, so "Closed under the global context" is that emptiness
   checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions admission_sequence.
Print Assumptions success_path.
Print Assumptions required_order.
Print Assumptions ordered_ok.
Print Assumptions Ordered.
Print Assumptions precedes.
Print Assumptions occurs.
Print Assumptions occurrences.
Print Assumptions single_read_ok.
Print Assumptions phase_shape_ok.
Print Assumptions all_of_by_mem.
Print Assumptions specification_is_a_single_read.
Print Assumptions generated_weakenings.
Print Assumptions failing_conjuncts.
Print Assumptions Sweep.
Print Assumptions bank_partial.
Print Assumptions no_partial_bank.
Print Assumptions phase_read.
Print Assumptions spec_reader.
Print Assumptions per_bank_reader.
Print Assumptions path.
Print Assumptions spec_path.
Print Assumptions AdmitsOnlyDrainedDomains.
Print Assumptions AdmitsNoPartiallySanitizedBank.
Print Assumptions spec_dwell.
Print Assumptions spec_hold.
Print Assumptions spec_release.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions orb_split.
Print Assumptions negb_true.
Print Assumptions all_of_mono.
Print Assumptions all_of_true.
Print Assumptions all_of_app.
Print Assumptions any_of_app.
Print Assumptions all_of_flatten_map.
Print Assumptions app_snoc.
Print Assumptions nat_eqb_refl.
Print Assumptions nat_eqb_true.
Print Assumptions nat_eqb_sym.
Print Assumptions nat_leb_split.
Print Assumptions nat_ltb_S.
Print Assumptions nat_ltb_irrefl.
Print Assumptions mem_nat_app.
Print Assumptions mem_upto.
Print Assumptions nodup_nat_snoc.
Print Assumptions nodup_upto.
Print Assumptions step_eqb_refl.
Print Assumptions step_eqb_true.
Print Assumptions step_eqb_sym.
Print Assumptions occurs_app.
Print Assumptions occurs_false_occurrences.
Print Assumptions nodup_at_most_once.
Print Assumptions nodup_once.
Print Assumptions precedes_irrefl.
Print Assumptions staggered_positive.
Print Assumptions admission_sequence_positive.
Print Assumptions adjacent_pairs_cons.
Print Assumptions required_order_is_adjacency.
Print Assumptions precedes_prefix.
Print Assumptions precedes_head.
Print Assumptions nodup_steps_suffix.
Print Assumptions nodup_steps_head_absent.
Print Assumptions adjacent_precede_from.
Print Assumptions adjacent_precede.
Print Assumptions occurs_staggered_absent.
Print Assumptions nodup_staggered.
Print Assumptions nodup_admission_sequence.
Print Assumptions nodup_success_path.
Print Assumptions occurs_phase_step_chain.
Print Assumptions occurs_entry_staggered.
Print Assumptions occurs_latch_staggered.
Print Assumptions occurs_entry_admission.
Print Assumptions occurs_latch_admission.
Print Assumptions staggered_phase_shape.
Print Assumptions specification_is_ordered.
Print Assumptions authority_invalidation_is_independent_of_residue_sanitization.
Print Assumptions the_success_path_carries_no_second_pass.
Print Assumptions generated_family_size.
Print Assumptions no_transposition_of_a_sequence_with_no_adjacent_pair.
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
Print Assumptions specification_stands_no_step_twice.
Print Assumptions specification_stands_each_phase_step_once.
Print Assumptions specification_reads_after_the_dwell.
Print Assumptions eager_read_refutes_the_dwell_order.
Print Assumptions eager_read_still_reads_once_and_stops.
Print Assumptions eager_read_breaks_the_phase_shape.
Print Assumptions polling_refutes_the_single_read.
Print Assumptions polling_still_keeps_the_order_and_reads_after_the_dwell.
Print Assumptions retrying_refutes_the_no_retry_rule.
Print Assumptions retrying_refutes_the_fail_stop_arm.
Print Assumptions the_retry_is_ordered_and_still_refused.
Print Assumptions optimistic_refutes_the_fail_stop_arm.
Print Assumptions the_optimistic_sequencer_passes_everything_else.
Print Assumptions one_confirmation_refutes_the_two_boundaries.
Print Assumptions one_confirmation_still_stops_and_latches.
Print Assumptions second_pass_refutes_the_one_pass.
Print Assumptions the_second_pass_is_ordered_and_stops.
Print Assumptions always_latching_refutes_the_second_half_of_the_arm.
Print Assumptions per_transition_refutes_the_read_per_phase.
Print Assumptions the_per_transition_sequencer_reads_the_first_phase_once.
Print Assumptions drained_is_not_partial.
Print Assumptions drained_domain_has_no_partial_bank.
Print Assumptions the_per_phase_reader_is_the_per_bank_reader.
Print Assumptions specification_reader_admits_no_partially_sanitized_bank.
Print Assumptions specification_reader_admits_only_drained_domains.
Print Assumptions admission_is_the_readers_confirmation.
Print Assumptions execution_is_the_readers_confirmation.
Print Assumptions no_path_admits_a_partially_sanitized_bank.
Print Assumptions no_path_executes_over_a_partially_sanitized_bank.
Print Assumptions the_three_sweeps_are_distinguished.
Print Assumptions the_specification_reader_confirms_and_refuses.
Print Assumptions the_demo_paths_are_the_readings.
Print Assumptions per_domain_reader_admits_an_undrained_bank.
Print Assumptions per_domain_reader_admits_a_partially_sanitized_bank.
Print Assumptions occurs_entry_discharges.
Print Assumptions the_per_transition_path_is_the_per_domain_reader.
Print Assumptions the_per_transition_path_admits_an_undrained_bank.
Print Assumptions touch_reader_admits_a_partially_sanitized_bank.
Print Assumptions the_touch_reader_still_refuses_an_unreached_bank.
Print Assumptions the_reader_arity_is_observable.
Print Assumptions the_acceptance_clause_is_not_the_criterion.
Print Assumptions specification_dwell_is_the_declared_constant.
Print Assumptions charge_dependent_dwell_is_refuted.
Print Assumptions arm_dependent_dwell_is_refuted.
Print Assumptions specification_holds_every_requester.
Print Assumptions class_exempt_hold_is_refuted.
Print Assumptions the_class_exempt_hold_reaches_one_class.
Print Assumptions specification_releases_no_requester_early.
Print Assumptions the_steps_that_would_release_early_are_the_seven_before_addressability.
Print Assumptions every_early_release_schedule_is_refused.
Print Assumptions a_requester_released_at_the_discharge_is_refused.
Print Assumptions a_late_release_is_admitted.
