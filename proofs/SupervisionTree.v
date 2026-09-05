(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   SupervisionTree.v

   The init system's supervision tree, as the register fixes it: R-12-073's
   static tree of declarative units with no ambient authority, whose
   start-order, crash detection, restart-with-backoff and capability
   re-grant are deterministic, bounded and hidden-state-free by
   construction; R-12-074's re-grant that re-instantiates and never mints;
   R-07-026's reading of the same sentence from the authority side;
   R-07-027's capDL-class manifest and R-07-028's initialisation-refinement
   obligation over it; R-10-026's signed, content-addressed configuration
   generation as the only origin of the component graph; R-12-087's closed
   detector and action enumerations and R-12-088's per-signal detection;
   R-12-089's five criticality classes; R-16-027's declared thresholds,
   dwell, window limit and backoff; R-16-007's boot count into a bounded
   downtime; and R-16-001 with R-08-043a and R-10-037 on what a restart may
   not carry across.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity the register
   leaves to composition is a field of the Machine record rather than a
   literal or a top-level Parameter, which is what keeps the R-05-163
   assumption gate green while leaving the decision where its owner can make
   it. Nothing is admitted and nothing is axiomatized: the Print Assumptions
   block at the end reports every shipped constant closed under the global
   context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere.
   The computed checks are decided inside the kernel by conversion and print
   nothing.

   What is deferred, and to which item. R-05-052 and R-12-002 put this
   control plane in Lustre compiled by Velus, and M6.1b is that lowering.
   Nothing below is a Lustre node, states a WCET, or claims a compilation
   property; what is here is the state machine the plan's section 8 keeps
   host-side, and the lowering's structural determinism and causality
   argument is M6.1b's to make. The authoring constraint this file does keep
   is the restricted subset a Rupicola-class compiler admits: no general
   recursion, every recursive function structural over a list or a finite
   index, and records and finite indices wherever a datatype is not owed.
   Three inductives are owed, because the register itself closes their
   enumerations, and each costs a compilation lemma per constructor on any
   such route. That is a price recorded rather than a claim made: the S12 reconnaissance item records that the purecap
   Bedrock2 backend does not exist, so nothing here
   is asserted to be Rupicola-compilable and the CompCert-C/VST route stays
   the default.

   No Require. Nothing beyond the Rocq prelude is reachable, so Classical
   and FunctionalExtensionality are unavailable and every equality below is
   stated pointwise or over a decidable boolean for that reason. A Require
   naming a sibling artifact would be admissible, and there is none to name:
   PartitionContext.v's switch cost is R-15-220's constant inside R-11-006's
   interval arithmetic, CyclicExecutive.v's admission algebra is a frame's,
   and DischargeSequence.v's dwell is R-15-247g's mode-transition constant.
   None of the three meets this file's quantities, so a Require here would
   be a citation rather than a dependency.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. A unit is a finite index and not an abstract type. R-12-001 makes each
      server its own compartment with its own manifest and R-10-026 fixes
      the roster in the signed generation, so the roster is a count and a
      unit is an index below it. That is the Rupicola-subset choice as well
      as the modelling one: an abstract carrier with a decidable-equality
      field would carry its own laws as record fields and would put a
      datatype where a finite index does the work.
   2. A manifest edge is directed from the holder to the designated unit.
      `manifest u v = true` reads "unit u holds a capability designating
      unit v", which is R-07-027's capDL-class edge with R-07-027a's three
      object classes left where that entry closes them: nothing below names
      an object class, and the edge set is the only structure taken.
   3. The start order's obligation is the manifest's own edges read as a
      precedence. Bring-up grants a unit its manifest edges when it starts,
      so a unit that names another is started after it; that is what
      "ordered capability-granting bring-up" fixes, and it makes the start
      order a topological order of the edge relation rather than a schedule
      this file invents.
   4. The re-grant is stated as two independent obligations and not one.
      R-12-074 says the re-grant re-instantiates exactly the edges the
      manifest already fixed, which bounds it above. R-10-037's acceptance
      clause says authority is re-derived at restart from the manifest and
      the *current revocation epoch*, so no restore resurrects an authority
      a revocation retired, which bounds it below. Read as one equality the
      two contradict each other, and the file states them apart: gap b
      records that no entry chooses, and
      `the_regrant_extent_is_observable` machine-checks that the choice is
      not free.
   5. Detection reads one signal and the reaction reads the composition.
      R-12-087's criterion has two halves, that no detector searches the
      component graph and that no action computes a victim score at run
      time, and R-12-088 adds that collection performs no scan proportional
      to the number of compartments. So a detection is stated over an
      arbitrary signal map and required to depend on its own detector's
      signal alone, and a policy is stated over an arbitrary observation and
      required not to vary with it. Both halves are refuted by construction
      rather than asserted.
   6. Hidden state is state outside R-16-027's own enumeration. That entry
      closes what a detector/action pair declares: assertion and clear
      thresholds, a minimum dwell, a maximum number of interventions per
      window, a backoff, and the escalation past the limit. A reaction keyed
      on anything else is what R-12-073's "hidden-state-free by
      construction" excludes, so State below carries the declared record and
      one further accumulation standing for whatever an implementation
      keeps, and the obligation quantifies over states agreeing on the
      declared half.
   7. The backoff is a declared schedule and a ceiling, not a formula. R-16-
      027 has each pair declare its backoff and R-16-007 bounds the worst
      case to downtime rather than permanent denial, and neither states a
      growth law, so the schedule is a list field, the delay past its end is
      the ceiling, and the ceiling obligation is stated of an arbitrary
      schedule.
   8. Boolean rather than propositional wherever the witnesses must compute:
      the bring-up check, the edge predicates and the admission tests are
      decidable, so the generated weakening families below are checked by
      conversion in the silent Example form rather than by a proof per
      member.
   9. The order is stated over positions rather than over a rank function
      built into the list's shape, so a start order out of order is
      expressible and the theorems have something to exclude. `precedes` is
      false where either unit is absent, which is what makes a deletion a
      refusal rather than a silence.

   The literals taken from the design, and there are four. R-12-087's
   detector enumeration is eight and its action enumeration is ten, so
   `all_detectors` and `all_actions` are those two lists written out and
   `there_are_eight_detectors` and `there_are_ten_actions` are the counts
   checked by conversion. R-12-089's criticality enumeration is five, so
   `all_classes` is that list and `there_are_five_criticality_classes` is
   its count. And a unit is started exactly once on a bring-up pass, so
   `each_unit_once` compares an occurrence count against 1. Every other
   magnitude is a field: the roster size, the start order, the manifest and
   the retired set, every threshold, the dwell, the window limit, the
   declared escalation past that limit, the backoff schedule and its
   ceiling, the boot bound, the detector-to-action map, the criticality
   assignment, the per-class ladder and the declared victim. In particular
   R-16-027 has each pair declare its own escalation action and R-16-024
   makes the victim manifest-declared, so neither is written out here as a
   constructor: the demo machine names RoT reset and unit 1 respectively,
   and R-16-005 is what authorizes the first.

   How the refutations are generated. A refutation is a seeded weakening the
   theorem must reject, so four generators produce families of them
   mechanically rather than a person authoring each, which is
   DischargeSequence.v's method taken to a different order. Over the
   specification's own start order: `swap_at` transposes an adjacent pair
   and yields one weakening per adjacent position; `drop_at` deletes a unit
   and yields one per position; `suffix_at` re-enters the order at a proper
   suffix, which is what a partial bring-up after a subtree restart would
   be, and yields one per position; and `insert_at` starts one unit a second
   time and yields one per position. The four families are 20 weakenings,
   every one refused, checked as one conversion. Beside them the generic
   theorems quantify over the index rather than enumerating. The
   hand-authored refutations below are the ones no index generates, being
   alternative constructions rather than mutations of a list.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. What a supervised unit's own lifecycle states are. R-16-026 gives a
      pool member a monotone lifecycle its pool declares and R-12-093 gives
      a request a closed status set, and neither is the supervised unit's.
      Nothing below carries a unit state at all: a unit is started or not
      started by its position in the bring-up order, and no `Running`,
      `Crashed` or `Quarantined` constructor is invented. Owed at R-12-073.
   b. Whether the restart re-grant is the manifest or the manifest filtered
      by the current revocation epoch. R-12-074 says "exactly the edges the
      capDL-class manifest already fixed"; R-10-037's acceptance clause says
      authority is re-derived from the manifest *and the current revocation
      epoch* so that no restore resurrects an authority a revocation
      retired; R-08-043a makes user retraction a fourth revocation trigger
      beside restart itself. The two readings differ observably on any
      machine with a retired manifest edge, which
      `the_regrant_extent_is_observable` checks. Owed at R-12-074 or
      R-10-037.
   c. What "no residue crosses the restart" quantifies over. R-16-001 makes
      eager-zeroize the mechanism and states the consequence, and no entry
      says whether the residue in question is the unit's private state, its
      grant slots, or both. This file states the authority half alone,
      because that is the half the manifest and the retired set decide;
      nothing below models memory. Owed at R-16-001.
   d. The minimal recovery state R-16-007 counts boots into. That entry
      bounds the worst case to downtime and R-09-028 makes boot counting an
      RoT duty, and no entry enumerates what the recovery state contains or
      which units its roster holds. `spec_boot_admit` therefore answers
      whether the ordinary generation is admitted and says nothing about
      what runs when it is not. Owed at R-16-007.
   e. Whether a restart's backoff index is per unit, per subtree, or per
      window. R-16-027 declares a backoff per detector/action pair, R-12-073
      states restart-with-backoff of the tree, and R-16-024 makes a complete
      supervised subtree one victim. The declared record below carries one
      attempt count and the file states the obligation over it; which unit
      it belongs to is the register's to say. Owed at R-16-027 or R-12-073.
   f. Whether R-12-087's ten actions are ordered as a ladder in themselves
      or only within a criticality class. R-16-025 states a default order
      over nine of the ten and R-12-089 gives each class its own permitted
      ordered ladder, and the two are not the same list. The ladder is a
      field, the demo instantiates it, and no order over the ten is
      asserted. Owed at R-12-089 or R-16-025.
   g. Whether a detector/action pair may declare a clear threshold equal to
      its assertion threshold. R-16-027 requires both to be declared and
      says nothing about the width between them, and a zero-width band is a
      pair that re-asserts the moment it clears, which is the oscillation
      the same entry's criterion is about. `the_degenerate_band_is_admitted`
      takes the weaker reading, which is the one the entry's words carry.
      Owed at R-16-027.
   h. Every composition magnitude. The roster, the start order, the
      manifest, the retired set, the thresholds, the dwell, the window
      limit, the escalation, the backoff schedule, the ceiling, the boot
      bound, the detector-to-action map, the criticality assignment, the
      ladder and the victim are fields; the demo machine at the end
      instantiates them with arbitrary witness values that carry no
      composition claim.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary supervisor, bring-up order, loader, detection,
   policy, re-grant map, backoff schedule or admission test, proved of the
   specification, and refuted of an alternative construction the register's
   own sentence excludes. Inhabitation is concrete: a demo machine whose
   roster, manifest and retired set are inhabited, signals on which the
   specification's detector fires and signals on which it does not, and a
   bring-up order that passes beside twenty that do not, so no theorem is
   proved from a premise nothing satisfies and none from one everything
   satisfies.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   List and boolean helpers, defined here rather than imported: the prelude
   carries the list type and not the library over it, and importing a module
   to save a dozen lines would put its assumptions inside the R-05-163
   gate's reach for no gain.
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

(* 0 through n-1, in that order: the index set the roster and the generators
   below range over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

(* The nth member of a list, or the declared fallback past its end. This is
   what makes the backoff a declared schedule rather than a formula
   (reading 7): the ceiling is the fallback, so an attempt past the last
   declared step waits the ceiling and never more. *)
Fixpoint at_index (l : list nat) (n : nat) (dflt : nat) : nat :=
  match l with
  | nil => dflt
  | cons x r => match n with 0 => x | S k => at_index r k dflt end
  end.

(* Implication as a boolean, written out rather than taken from a library
   for the reason above. *)
Definition only_if (a b : bool) : bool := orb (negb a) b.

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma only_if_elim :
  forall a b : bool, only_if a b = true -> a = true -> b = true.
Proof.
  intros a b H Ha. unfold only_if in H. rewrite Ha in H. simpl in H. exact H.
Qed.

Lemma all_of_true : forall (A : Type) (l : list A), all_of (fun _ => true) l = true.
Proof.
  intros A l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. exact IH.
Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

(* Whatever holds of every declared step and of the fallback holds of the
   delay at every attempt: the lemma R-16-007's bounded downtime rests on,
   stated once over an arbitrary predicate so the ceiling theorem below is
   an instance rather than a second induction. *)
Lemma at_index_holds :
  forall (p : nat -> bool) (l : list nat) (dflt : nat),
    all_of p l = true -> p dflt = true ->
    forall n : nat, p (at_index l n dflt) = true.
Proof.
  intros p l dflt Hl Hd. induction l as [ | x r IH ]; intros n.
  - simpl. exact Hd.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hx Hr ].
    destruct n as [ | k ]; simpl.
    + exact Hx.
    + exact (IH Hr k).
Qed.

(* The helpers' own floors, so that the day one of them stops deciding is
   the day it says so. Each is a base case no other check below reaches. *)
Example the_empty_conjunction_holds : all_of (fun _ : nat => false) nil = true := eq_refl.

Example the_empty_disjunction_fails : any_of (fun _ : nat => true) nil = false := eq_refl.

Example nothing_has_length_zero : count_of (nil : list nat) = 0 := eq_refl.

Example before_last_of_nothing : before_last 0 = 0 := eq_refl.

Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.

Example only_if_is_implication :
  cons (only_if true true) (cons (only_if true false)
  (cons (only_if false true) (cons (only_if false false) nil)))
  = cons true (cons false (cons true (cons true nil))) := eq_refl.

(* =========================================================================
   The three closed enumerations, and only these three. Each is closed
   because the register itself closes it: a fourth inductive here would be
   this file inventing an enumeration where the register leaves a
   composition, which is exactly the line a statement artifact does not
   cross.
   ========================================================================= *)

(* R-12-087's eight admitted detectors, in the entry's own order. *)
Inductive Detector : Type :=
| PoolLow                      (* the pool's remaining members past a bound *)
| PoolExhausted                (* no member left to bind                    *)
| OldestWaiterPastBound        (* R-12-088's oldest-waiter age              *)
| QuarantineBacklogPastBound   (* quarantined-but-not-reusable count        *)
| ReleaseMissedDeadline        (* completion age of teardown or sweep work  *)
| RestartRatePastBound         (* R-16-027's rate limit reached             *)
| PopulationCeilingReached     (* the population rung's own ceiling         *)
| CheckpointSpaceUnavailable.  (* R-10-036's checkpoint has nowhere to go   *)

(* R-12-087's ten admitted actions, in the entry's own order. The ladder
   runs from declining one request through fail-stop of the owning
   subsystem, each spending availability of the owner's own service. *)
Inductive Action : Type :=
| RefuseTheNewRequest
| ShedOwnerLocalState               (* R-12-090's one optional owner-local shed *)
| SuspendNamedTenant
| CheckpointAndTerminateNamedTenant
| TerminateOwnershipClosedGroup     (* R-16-024's ownership-closed victim       *)
| StepDownPopulationRung
| DisableNonessentialService
| RestartOwningSubtree              (* R-12-073's own restart                   *)
| FailStopOwningSubsystem
| EscalateToRotReset.               (* only where R-16-005 authorizes it        *)

(* R-12-089's five composition-fixed criticality classes. *)
Inductive Criticality : Type :=
| NonSacrificable
| Suspendable
| CheckpointAndTerminable
| RestartableWithoutCheckpoint
| Discardable.

Definition all_detectors : list Detector :=
  cons PoolLow (cons PoolExhausted (cons OldestWaiterPastBound
  (cons QuarantineBacklogPastBound (cons ReleaseMissedDeadline
  (cons RestartRatePastBound (cons PopulationCeilingReached
  (cons CheckpointSpaceUnavailable nil))))))).

Definition all_actions : list Action :=
  cons RefuseTheNewRequest (cons ShedOwnerLocalState (cons SuspendNamedTenant
  (cons CheckpointAndTerminateNamedTenant (cons TerminateOwnershipClosedGroup
  (cons StepDownPopulationRung (cons DisableNonessentialService
  (cons RestartOwningSubtree (cons FailStopOwningSubsystem
  (cons EscalateToRotReset nil))))))))).

Definition all_classes : list Criticality :=
  cons NonSacrificable (cons Suspendable (cons CheckpointAndTerminable
  (cons RestartableWithoutCheckpoint (cons Discardable nil)))).

(* The three counts, checked by conversion rather than claimed. These are
   three of this file's four literals from the design, and the day an entry
   admits a ninth detector is the day one of them stops holding. *)
Example there_are_eight_detectors : count_of all_detectors = 8 := eq_refl.

Example there_are_ten_actions : count_of all_actions = 10 := eq_refl.

Example there_are_five_criticality_classes : count_of all_classes = 5 := eq_refl.

Definition detector_eqb (d e : Detector) : bool :=
  match d, e with
  | PoolLow, PoolLow => true
  | PoolExhausted, PoolExhausted => true
  | OldestWaiterPastBound, OldestWaiterPastBound => true
  | QuarantineBacklogPastBound, QuarantineBacklogPastBound => true
  | ReleaseMissedDeadline, ReleaseMissedDeadline => true
  | RestartRatePastBound, RestartRatePastBound => true
  | PopulationCeilingReached, PopulationCeilingReached => true
  | CheckpointSpaceUnavailable, CheckpointSpaceUnavailable => true
  | _, _ => false
  end.

Lemma detector_eqb_refl : forall d : Detector, detector_eqb d d = true.
Proof. intros d. destruct d; reflexivity. Qed.

Lemma detector_eqb_true : forall d e : Detector, detector_eqb d e = true -> d = e.
Proof.
  intros d e. destruct d; destruct e; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition action_eqb (a b : Action) : bool :=
  match a, b with
  | RefuseTheNewRequest, RefuseTheNewRequest => true
  | ShedOwnerLocalState, ShedOwnerLocalState => true
  | SuspendNamedTenant, SuspendNamedTenant => true
  | CheckpointAndTerminateNamedTenant, CheckpointAndTerminateNamedTenant => true
  | TerminateOwnershipClosedGroup, TerminateOwnershipClosedGroup => true
  | StepDownPopulationRung, StepDownPopulationRung => true
  | DisableNonessentialService, DisableNonessentialService => true
  | RestartOwningSubtree, RestartOwningSubtree => true
  | FailStopOwningSubsystem, FailStopOwningSubsystem => true
  | EscalateToRotReset, EscalateToRotReset => true
  | _, _ => false
  end.

Lemma action_eqb_refl : forall a : Action, action_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma action_eqb_true : forall a b : Action, action_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* Which of the ten end a unit rather than costing it capacity. R-16-024
   makes a complete supervised subtree an ownership-closed victim whose
   termination is total, and a restart of the owning subtree runs that
   teardown, so the restart is on this side of the line and the shed, the
   suspension, the rung step and the refusal are not. *)
Definition terminates (a : Action) : bool :=
  match a with
  | RefuseTheNewRequest => false
  | ShedOwnerLocalState => false
  | SuspendNamedTenant => false
  | CheckpointAndTerminateNamedTenant => true
  | TerminateOwnershipClosedGroup => true
  | StepDownPopulationRung => false
  | DisableNonessentialService => false
  | RestartOwningSubtree => true
  | FailStopOwningSubsystem => true
  | EscalateToRotReset => true
  end.

Example which_actions_terminate :
  map_over terminates all_actions
  = cons false (cons false (cons false (cons true (cons true (cons false
    (cons false (cons true (cons true (cons true nil))))))))) := eq_refl.

(* =========================================================================
   The machine: everything the register leaves to composition. Fields rather
   than Parameters, because a top-level Parameter prints as an assumption
   and fails the R-05-163 gate.
   ========================================================================= *)

Record Machine : Type := {

  (* --- R-12-001's roster: each server its own compartment, fixed in
         R-10-026's signed generation, so a unit is an index below this
         count (reading 1) ------------------------------------------------- *)

  unit_count : nat;

  (* --- R-12-073's start order over that roster, and R-07-027's
         capDL-class manifest read as a directed edge from the holder to
         the unit it designates (reading 2) -------------------------------- *)

  start_order : list nat;
  manifest : nat -> nat -> bool;

  (* --- the edges a revocation has retired at the current epoch: grant
         expiry, session close, restart, and R-08-043a's user retraction,
         which R-10-037's acceptance clause puts between the manifest and
         what a restart re-derives ---------------------------------------- *)

  retired : nat -> nat -> bool;

  (* --- R-16-027's declared quantities, per detector where the entry makes
         them per pair and per machine where it does not ------------------- *)

  threshold : Detector -> nat;
  clear_threshold : Detector -> nat;
  min_dwell : nat;
  max_interventions : nat;
  escalation : Action;

  (* --- R-12-073's restart-with-backoff as a declared schedule and a
         ceiling, with R-16-007's boot count beside it (reading 7) --------- *)

  backoff_schedule : list nat;
  backoff_ceiling : nat;
  boot_bound : nat;

  (* --- R-12-087's finite composition-time mapping, and R-12-089's
         composition-fixed class with the ordered ladder permitted for it -- *)

  respond : Detector -> Action;
  criticality : nat -> Criticality;
  ladder : Criticality -> list Action;

  (* --- R-16-024's victim: a manifest-declared ownership-closed unit, never
         an arbitrary thread and never one chosen at run time ------------- *)

  victim : nat
}.

(* =========================================================================
   Where a unit stands in a bring-up order.
   ========================================================================= *)

Fixpoint pos_from (u : nat) (l : list nat) (i : nat) : option nat :=
  match l with
  | nil => None
  | cons v r => if Nat.eqb u v then Some i else pos_from u r (S i)
  end.

Definition pos (u : nat) (l : list nat) : option nat := pos_from u l 0.

Definition occurs (u : nat) (l : list nat) : bool :=
  match pos u l with Some _ => true | None => false end.

Fixpoint occurrences (u : nat) (l : list nat) : nat :=
  match l with
  | nil => 0
  | cons v r => if Nat.eqb u v then S (occurrences u r) else occurrences u r
  end.

(* False where either unit is absent, which is what makes a deletion a
   refusal rather than a silence (reading 9). *)
Definition precedes (u v : nat) (l : list nat) : bool :=
  match pos u l, pos v l with
  | Some i, Some j => Nat.ltb i j
  | _, _ => false
  end.

(* =========================================================================
   The bring-up order and its three obligations.
   ========================================================================= *)

(* R-12-073's start order: every unit of the roster started exactly once.
   The 1 is the fourth of this file's four literals. *)
Definition each_unit_once (m : Machine) (l : list nat) : bool :=
  all_of (fun u => Nat.eqb (occurrences u l) 1) (upto m.(unit_count)).

(* Nothing outside the roster is started at all, R-10-026's generation being
   the only origin of the component graph. *)
Definition no_stranger (m : Machine) (l : list nat) : bool :=
  all_of (fun u => Nat.ltb u m.(unit_count)) l.

(* Reading 3: a unit that names another is started after it, so no unit is
   handed a capability designating a unit that is not yet up. *)
Definition grants_ok_for (m : Machine) (l : list nat) (u : nat) : bool :=
  all_of (fun v => only_if (m.(manifest) u v) (precedes v u l))
         (upto m.(unit_count)).

Definition grants_nothing_early (m : Machine) (l : list nat) : bool :=
  all_of (grants_ok_for m l) (upto m.(unit_count)).

Definition bringup_ok (m : Machine) (l : list nat) : bool :=
  andb (each_unit_once m l)
  (andb (no_stranger m l) (grants_nothing_early m l)).

Definition BroughtUpInOrder (m : Machine) (l : list nat) : Prop :=
  each_unit_once m l = true
  /\ no_stranger m l = true
  /\ grants_nothing_early m l = true.

Lemma bringup_ok_sound :
  forall (m : Machine) (l : list nat), bringup_ok m l = true -> BroughtUpInOrder m l.
Proof.
  intros m l H. unfold bringup_ok in H.
  destruct (andb_split _ _ H) as [ H1 R1 ].
  destruct (andb_split _ _ R1) as [ H2 H3 ].
  exact (conj H1 (conj H2 H3)).
Qed.

Lemma bringup_ok_complete :
  forall (m : Machine) (l : list nat), BroughtUpInOrder m l -> bringup_ok m l = true.
Proof.
  intros m l [ H1 [ H2 H3 ] ]. unfold bringup_ok.
  apply andb_join; [ exact H1 | ]. apply andb_join; [ exact H2 | exact H3 ].
Qed.

(* -------------------------------------------------------------------------
   Reading a conjunction over the roster back at one of its members. Three
   small lemmas the prelude does not carry, so that the bring-up obligation
   below is stated of an arbitrary pair of units rather than only computed
   over a demo roster.
   ------------------------------------------------------------------------- *)

Lemma all_of_app :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p (app l r) = true -> all_of p l = true /\ all_of p r = true.
Proof.
  intros A p l r. induction l as [ | x s IH ]; intros H.
  - split; [ reflexivity | exact H ].
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hs ].
    destruct (IH Hs) as [ Hl Hr ]. split; [ | exact Hr ].
    simpl. apply andb_join; [ exact Hx | exact Hl ].
Qed.

Lemma leb_split : forall v k : nat, Nat.leb v k = true -> Nat.ltb v k = true \/ v = k.
Proof.
  intros v. induction v as [ | a IH ]; intros k H.
  - destruct k as [ | b ]; [ right; reflexivity | left; reflexivity ].
  - destruct k as [ | b ].
    + discriminate H.
    + simpl in H. destruct (IH b H) as [ Hlt | Heq ].
      * left. exact Hlt.
      * right. rewrite Heq. reflexivity.
Qed.

Lemma all_of_upto :
  forall (p : nat -> bool) (n v : nat),
    all_of p (upto n) = true -> Nat.ltb v n = true -> p v = true.
Proof.
  intros p n. induction n as [ | k IH ]; intros v H Hv.
  - discriminate Hv.
  - simpl in H. destruct (all_of_app nat p (upto k) (cons k nil) H) as [ Hk Hlast ].
    simpl in Hlast. destruct (andb_split _ _ Hlast) as [ Hpk _ ].
    simpl in Hv. destruct (leb_split v k Hv) as [ Hlt | Heq ].
    + exact (IH v Hk Hlt).
    + rewrite Heq. exact Hpk.
Qed.

(* S1 (R-12-073's start-order clause, R-07-027, R-07-028): the obligation
   read at an arbitrary pair of an arbitrary order, which is what lets the
   specification's order be one witness among the orders this file exhibits
   rather than the only expressible list. No unit is handed a
   capability designating a unit the order has not already started. *)
Theorem an_ordered_bringup_starts_the_grantee_first :
  forall (m : Machine) (l : list nat) (u v : nat),
    grants_nothing_early m l = true ->
    Nat.ltb u m.(unit_count) = true ->
    Nat.ltb v m.(unit_count) = true ->
    m.(manifest) u v = true ->
    precedes v u l = true.
Proof.
  intros m l u v Hall Hu Hv Hedge.
  assert (Hu' : grants_ok_for m l u = true) by
    exact (all_of_upto (grants_ok_for m l) m.(unit_count) u Hall Hu).
  assert (Hv' : only_if (m.(manifest) u v) (precedes v u l) = true) by
    exact (all_of_upto (fun w => only_if (m.(manifest) u w) (precedes w u l))
             m.(unit_count) v Hu' Hv).
  exact (only_if_elim _ _ Hv' Hedge).
Qed.

(* =========================================================================
   Where the component graph comes from (R-10-026, R-10-028, R-12-087).

   The signed, content-addressed generation is the only origin, so the order
   a loader produces is the machine's own field and is not a function of
   anything observed at run time. Stating it over an arbitrary loader is
   what makes a graph discovered under load exhibitable rather than merely
   different from an implementation this file chose.
   ========================================================================= *)

Definition Signals : Type := Detector -> nat.

Definition Loader (m : Machine) : Type := Signals -> list nat.

Definition spec_loader (m : Machine) : Loader m := fun _ => m.(start_order).

Definition IsTheSignedComposition (m : Machine) (ld : Loader m) : Prop :=
  forall sig : Signals, ld sig = m.(start_order).

(* S2 (R-10-026). *)
Theorem the_specification_loads_the_signed_composition :
  forall m : Machine, IsTheSignedComposition m (spec_loader m).
Proof. intros m sig. reflexivity. Qed.

(* =========================================================================
   The restart re-grant (R-12-074, R-07-026, R-16-001, R-08-043a, R-10-037).
   ========================================================================= *)

Definition Regrant (m : Machine) : Type := nat -> nat -> bool.

(* Reading 4: the manifest above and the current revocation epoch below. *)
Definition spec_regrant (m : Machine) : Regrant m :=
  fun u v => andb (m.(manifest) u v) (negb (m.(retired) u v)).

(* R-12-074's own sentence: the tree is an authority re-instantiator and
   never a minter, and R-07-026 reads the same clause from the authority
   side, no operation adding a node or a label to the composed graph. *)
Definition MintsNothing (m : Machine) (g : Regrant m) : Prop :=
  forall u v : nat, g u v = true -> m.(manifest) u v = true.

(* R-10-037's acceptance clause: no restore resurrects an authority a
   revocation retired, with R-08-043a's user retraction the fourth trigger
   and R-16-001's eager-zeroize the reason nothing else crosses. *)
Definition CarriesNoRetiredAuthority (m : Machine) (g : Regrant m) : Prop :=
  forall u v : nat, g u v = true -> m.(retired) u v = false.

(* S3 (R-12-074). *)
Theorem the_specification_regrant_mints_nothing :
  forall m : Machine, MintsNothing m (spec_regrant m).
Proof.
  intros m u v H. unfold spec_regrant in H.
  destruct (andb_split _ _ H) as [ Hm _ ]. exact Hm.
Qed.

(* S4 (R-10-037, R-08-043a). *)
Theorem the_specification_regrant_carries_no_retired_authority :
  forall m : Machine, CarriesNoRetiredAuthority m (spec_regrant m).
Proof.
  intros m u v H. unfold spec_regrant in H.
  destruct (andb_split _ _ H) as [ _ Hr ].
  destruct (m.(retired) u v); [ discriminate Hr | reflexivity ].
Qed.

(* =========================================================================
   Detection (R-12-087's first criterion half, R-12-088).

   A detection is stated over an arbitrary signal map, and the obligation is
   that a detector's verdict is a function of its own signal alone: that is
   R-12-088's "no scan proportional to the number of compartments" and
   R-12-087's "no detector searches the component graph", read as the one
   property a statement can carry.
   ========================================================================= *)

Definition Detection (m : Machine) : Type := Signals -> Detector -> bool.

Definition spec_detect (m : Machine) : Detection m :=
  fun sig d => Nat.leb (m.(threshold) d) (sig d).

Definition ReadsOnlyItsOwnSignal (m : Machine) (dec : Detection m) : Prop :=
  forall (s1 s2 : Signals) (d : Detector), s1 d = s2 d -> dec s1 d = dec s2 d.

(* S5 (R-12-087, R-12-088). *)
Theorem the_specification_detector_reads_only_its_own_signal :
  forall m : Machine, ReadsOnlyItsOwnSignal m (spec_detect m).
Proof. intros m s1 s2 d H. unfold spec_detect. rewrite H. reflexivity. Qed.

(* R-16-027's clear threshold beside its assertion threshold: a pair whose
   clear threshold sits above its assertion threshold declares a band that
   never clears, which is the oscillation the entry's criterion is about. *)
Definition DeclaresAHysteresisBand (clear assert : Detector -> nat) : Prop :=
  all_of (fun d => Nat.leb (clear d) (assert d)) all_detectors = true.

(* =========================================================================
   The reaction (R-12-087's second criterion half, R-12-089).

   A policy is stated over an arbitrary observation and required not to vary
   with it, which is "no action computes a victim score at runtime" as a
   property rather than as an absence; and a victim selection is required to
   stay inside one criticality class, which is R-12-089's equivalence-class
   clause with the score adjustment deleted rather than ported.
   ========================================================================= *)

Definition Policy (m : Machine) : Type := Detector -> Signals -> Action.

Definition spec_policy (m : Machine) : Policy m := fun d _ => m.(respond) d.

Definition IsCompositionFixed (m : Machine) (p : Policy m) : Prop :=
  forall (d : Detector) (s1 s2 : Signals), p d s1 = p d s2.

(* S6 (R-12-087). *)
Theorem the_specification_policy_is_composition_fixed :
  forall m : Machine, IsCompositionFixed m (spec_policy m).
Proof. intros m d s1 s2. reflexivity. Qed.

Definition Selector (m : Machine) : Type := Signals -> nat.

Definition SelectsInsideOneClass (m : Machine) (sel : Selector m) : Prop :=
  forall s1 s2 : Signals, m.(criticality) (sel s1) = m.(criticality) (sel s2).

(* An action is admitted only where the class's own ladder carries it. *)
Definition ladder_permits (m : Machine) (c : Criticality) (a : Action) : bool :=
  any_of (fun b => action_eqb b a) (m.(ladder) c).

(* R-12-089's criterion, read on the ladder: the class the entry calls
   non-sacrificable declares no action that ends a unit, so no principal
   reaches a termination of it by consuming a shared pool. Stated of an
   arbitrary ladder, which is what lets one that does be exhibited. *)
Definition SparesTheNonSacrificable (l : Criticality -> list Action) : Prop :=
  all_of (fun a => negb (terminates a)) (l NonSacrificable) = true.

(* =========================================================================
   Restart with backoff (R-12-073, R-16-027, R-16-007).
   ========================================================================= *)

Definition Backoff : Type := nat -> nat.

Definition delay_at (s : list nat) (ceiling n : nat) : nat := at_index s n ceiling.

Definition spec_backoff (m : Machine) : Backoff :=
  delay_at m.(backoff_schedule) m.(backoff_ceiling).

Definition BoundedSchedule (ceiling : nat) (s : list nat) : Prop :=
  all_of (fun d => Nat.leb d ceiling) s = true.

Definition WithinTheCeiling (ceiling : nat) (b : Backoff) : Prop :=
  forall n : nat, Nat.leb (b n) ceiling = true.

(* S7 (R-16-007, R-16-027): a declared schedule within the ceiling bounds
   every attempt, including every attempt past the last declared step, which
   is where a formula-shaped backoff runs away. Stated of an arbitrary
   schedule and an arbitrary ceiling. *)
Theorem a_bounded_schedule_bounds_every_attempt :
  forall (s : list nat) (c : nat),
    BoundedSchedule c s -> WithinTheCeiling c (delay_at s c).
Proof.
  intros s c H n. unfold delay_at.
  exact (at_index_holds (fun d => Nat.leb d c) s c H (nat_leb_refl c) n).
Qed.

(* =========================================================================
   The rate limit, the dwell, and the boot count (R-16-027, R-16-007).
   ========================================================================= *)

(* R-16-027's own enumeration of what a detector/action pair declares is
   what fixes this record: an attempt count for the backoff, an intervention
   count for the window, a dwell since the last intervention, and a boot
   count. Anything a reaction reads beyond these four is hidden state
   (reading 6). *)
Record Declared : Type := {
  attempts : nat;
  interventions : nat;
  dwell : nat;
  boots : nat
}.

Definition declared_at (a i d b : nat) : Declared :=
  {| attempts := a; interventions := i; dwell := d; boots := b |}.

Definition Admission (m : Machine) : Type := Declared -> bool.

Definition spec_admits (m : Machine) : Admission m := fun s =>
  andb (Nat.leb m.(min_dwell) s.(dwell))
       (Nat.ltb s.(interventions) m.(max_interventions)).

Definition RespectsTheDwell (m : Machine) (adm : Admission m) : Prop :=
  forall s : Declared,
    Nat.leb m.(min_dwell) s.(dwell) = false -> adm s = false.

Definition RespectsTheWindow (m : Machine) (adm : Admission m) : Prop :=
  forall s : Declared,
    Nat.ltb s.(interventions) m.(max_interventions) = false -> adm s = false.

(* S8 and S9 (R-16-027): a workload oscillating at a threshold reaches
   neither an intervention inside the dwell nor one past the window's count,
   so it manufactures no unbounded restart, checkpoint, sweep or eviction
   loop. The two are separate obligations because one construction can
   satisfy either and fail the other. *)
Theorem the_specification_respects_the_dwell :
  forall m : Machine, RespectsTheDwell m (spec_admits m).
Proof. intros m s H. unfold spec_admits. rewrite H. reflexivity. Qed.

Theorem the_specification_respects_the_window :
  forall m : Machine, RespectsTheWindow m (spec_admits m).
Proof.
  intros m s H. unfold spec_admits. rewrite H.
  destruct (Nat.leb m.(min_dwell) s.(dwell)); reflexivity.
Qed.

(* R-16-027's escalation past the rate limit, which is what keeps the refusal
   from being a silence: past the window's count the pair's declared
   escalation runs rather than the ordinary action. *)
Definition Limiter (m : Machine) : Type := Declared -> Action -> Action.

Definition spec_limiter (m : Machine) : Limiter m := fun s a =>
  if Nat.ltb s.(interventions) m.(max_interventions) then a else m.(escalation).

Definition EscalatesPastTheRateLimit (m : Machine) (lim : Limiter m) : Prop :=
  forall (s : Declared) (a : Action),
    Nat.ltb s.(interventions) m.(max_interventions) = false ->
    lim s a = m.(escalation).

(* S10 (R-16-027). Which action the escalation is stays the composition's,
   because R-16-027 has each pair declare it; the demo machine names RoT
   reset, which R-16-005 is what authorizes. *)
Theorem the_specification_escalates_past_the_rate_limit :
  forall m : Machine, EscalatesPastTheRateLimit m (spec_limiter m).
Proof. intros m s a H. unfold spec_limiter. rewrite H. reflexivity. Qed.

(* R-16-007: boot counting into a minimal recovery state, so the worst case
   is bounded downtime. What the recovery state holds is gap d; what is
   stated here is that the ordinary generation is refused past the bound. *)
Definition BootAdmission (m : Machine) : Type := Declared -> bool.

Definition spec_boot_admit (m : Machine) : BootAdmission m :=
  fun s => Nat.ltb s.(boots) m.(boot_bound).

Definition BootCounted (m : Machine) (adm : BootAdmission m) : Prop :=
  forall s : Declared,
    Nat.ltb s.(boots) m.(boot_bound) = false -> adm s = false.

(* S11 (R-16-007, R-09-028). *)
Theorem the_specification_counts_boots :
  forall m : Machine, BootCounted m (spec_boot_admit m).
Proof. intros m s H. unfold spec_boot_admit. exact H. Qed.

(* =========================================================================
   Hidden state (R-12-073's criterion, reading 6).
   ========================================================================= *)

(* What an implementation may carry: the declared record R-16-027 closes,
   and one further accumulation standing for whatever else it keeps. The
   obligation quantifies over states agreeing on the declared half, so a
   reaction that reads the second is refused and one that does not is
   admitted whatever the second holds. *)
Record State : Type := {
  declared : Declared;
  trace : list Detector
}.

Definition Supervisor : Type := State -> Detector -> Action.

Definition HiddenStateFree (q : Supervisor) : Prop :=
  forall (s1 s2 : State) (d : Detector),
    s1.(declared) = s2.(declared) -> q s1 d = q s2 d.

Definition spec_supervisor (m : Machine) : Supervisor := fun s d =>
  spec_limiter m s.(declared) (m.(respond) d).

(* S12 (R-12-073): the reaction is a function of the declared state and the
   detector, and of nothing else the machine happens to be carrying. *)
Theorem the_specification_supervisor_is_hidden_state_free :
  forall m : Machine, HiddenStateFree (spec_supervisor m).
Proof. intros m s1 s2 d H. unfold spec_supervisor. rewrite H. reflexivity. Qed.

(* =========================================================================
   The generated weakenings of a bring-up order (R-05-166). A refutation is
   a seeded weakening the theorem must reject, so these four generators
   produce families of them from the specification's own order rather than a
   person authoring each. The theorems quantify over the index; the Examples
   check the whole family by conversion and print nothing.
   ========================================================================= *)

(* Transpose the adjacent pair at n: the natural wrong move on an ordered
   bring-up, and one weakening per adjacent position. *)
Fixpoint swap_at (n : nat) (l : list nat) : list nat :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

(* Delete the unit at n: a member of the roster never started. *)
Fixpoint drop_at (n : nat) (l : list nat) : list nat :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

(* Re-enter the order at the suffix beginning at n, which is what a bring-up
   resumed after a subtree restart would be if the tree were not static. *)
Fixpoint suffix_at (n : nat) (l : list nat) : list nat :=
  match n, l with
  | 0, _ => l
  | S k, cons _ r => suffix_at k r
  | S _, nil => nil
  end.

(* Start one unit a second time, one weakening per position. *)
Fixpoint insert_at (n : nat) (u : nat) (l : list nat) : list nat :=
  match n, l with
  | 0, _ => cons u l
  | S k, cons a r => cons a (insert_at k u r)
  | S _, nil => cons u nil
  end.

Definition transpositions (l : list nat) : list (list nat) :=
  map_over (fun n => swap_at n l) (upto (before_last (count_of l))).

Definition deletions (l : list nat) : list (list nat) :=
  map_over (fun n => drop_at n l) (upto (count_of l)).

Definition proper_suffixes (l : list nat) : list (list nat) :=
  map_over (fun n => suffix_at (S n) l) (upto (count_of l)).

Definition duplicate_starts (l : list nat) : list (list nat) :=
  map_over (fun n => insert_at n 0 l) (upto (S (count_of l))).

Definition generated_weakenings (l : list nat) : list (list nat) :=
  app (transpositions l)
      (app (deletions l) (app (proper_suffixes l) (duplicate_starts l))).

(* How many units of the roster are handed a capability designating a unit
   the order has not started yet. R-12-073's start-order clause is one
   conjunct per manifest edge, and this is the measure that says which of
   them a weakening breaks rather than that some of them did. *)
Definition units_granted_early (m : Machine) (l : list nat) : nat :=
  count_of (filter_of (fun u => negb (grants_ok_for m l u))
                      (upto m.(unit_count))).

(* =========================================================================
   The demo machine, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Five units in a chain, each naming the one before
   it, exercise every case the clauses distinguish: an order that grants
   after its grantee, twenty that do not, one retired edge, and two
   criticality classes. Every figure below is an arbitrary witness value and
   carries no composition claim (gap h).
   ------------------------------------------------------------------------- *)

Definition spec_order : list nat :=
  cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))).

Definition spec_ladder (c : Criticality) : list Action :=
  match c with
  | NonSacrificable =>
      cons RefuseTheNewRequest (cons ShedOwnerLocalState nil)
  | Suspendable =>
      cons RefuseTheNewRequest (cons ShedOwnerLocalState
      (cons SuspendNamedTenant nil))
  | CheckpointAndTerminable =>
      cons RefuseTheNewRequest (cons ShedOwnerLocalState
      (cons SuspendNamedTenant (cons CheckpointAndTerminateNamedTenant nil)))
  | RestartableWithoutCheckpoint =>
      cons RefuseTheNewRequest (cons ShedOwnerLocalState
      (cons RestartOwningSubtree nil))
  | Discardable =>
      cons RefuseTheNewRequest (cons ShedOwnerLocalState
      (cons TerminateOwnershipClosedGroup nil))
  end.

Definition demo_respond (d : Detector) : Action :=
  match d with
  | PoolLow => RefuseTheNewRequest
  | PoolExhausted => ShedOwnerLocalState
  | OldestWaiterPastBound => SuspendNamedTenant
  | QuarantineBacklogPastBound => StepDownPopulationRung
  | ReleaseMissedDeadline => DisableNonessentialService
  | RestartRatePastBound => FailStopOwningSubsystem
  | PopulationCeilingReached => StepDownPopulationRung
  | CheckpointSpaceUnavailable => CheckpointAndTerminateNamedTenant
  end.

Definition demo : Machine := {|
  unit_count := 5;
  start_order := spec_order;
  manifest := fun u v => Nat.eqb u (S v);
  retired := fun u v => andb (Nat.eqb u 4) (Nat.eqb v 3);
  threshold := fun _ => 3;
  clear_threshold := fun _ => 1;
  min_dwell := 2;
  max_interventions := 3;
  escalation := EscalateToRotReset;
  backoff_schedule := cons 1 (cons 2 (cons 3 (cons 5 nil)));
  backoff_ceiling := 5;
  boot_bound := 3;
  respond := demo_respond;
  criticality := fun u =>
    if Nat.eqb u 0 then NonSacrificable else RestartableWithoutCheckpoint;
  ladder := spec_ladder;
  victim := 1
|}.

(* The demo's declared quantities, computed rather than described, so that a
   figure edited on one side of the file and read on the other is a failed
   conversion instead of a silent disagreement. *)
Example the_demo_machine_declares :
  demo.(unit_count) = 5
  /\ demo.(min_dwell) = 2
  /\ demo.(max_interventions) = 3
  /\ demo.(backoff_ceiling) = 5
  /\ demo.(boot_bound) = 3
  /\ demo.(victim) = 1
  /\ demo.(escalation) = EscalateToRotReset
  /\ demo.(backoff_schedule) = cons 1 (cons 2 (cons 3 (cons 5 nil)))
  /\ demo.(start_order) = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))).

Example the_demo_thresholds :
  map_over demo.(threshold) all_detectors
  = cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 nil)))))))
  /\ map_over demo.(clear_threshold) all_detectors
  = cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 nil))))))) :=
  conj eq_refl eq_refl.

Example the_demo_manifest_is_a_chain :
  demo.(manifest) 1 0 = true /\ demo.(manifest) 0 1 = false
  /\ demo.(manifest) 4 3 = true /\ demo.(manifest) 4 2 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* One retired edge, which is what makes gap b observable rather than
   hypothetical: the manifest fixes (4,3) and the current epoch has retired
   it. *)
Example the_demo_has_one_retired_edge :
  demo.(retired) 4 3 = true /\ demo.(retired) 3 2 = false
  /\ demo.(retired) 4 2 = false :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_demo_criticality_assignment :
  map_over demo.(criticality) (upto 5)
  = cons NonSacrificable (cons RestartableWithoutCheckpoint
    (cons RestartableWithoutCheckpoint (cons RestartableWithoutCheckpoint
    (cons RestartableWithoutCheckpoint nil)))) := eq_refl.

Example the_demo_responds_to_every_detector :
  map_over demo.(respond) all_detectors
  = cons RefuseTheNewRequest (cons ShedOwnerLocalState (cons SuspendNamedTenant
    (cons StepDownPopulationRung (cons DisableNonessentialService
    (cons FailStopOwningSubsystem (cons StepDownPopulationRung
    (cons CheckpointAndTerminateNamedTenant nil))))))) := eq_refl.

Example the_non_sacrificable_ladder_and_the_discardable_one :
  ladder_permits demo NonSacrificable RefuseTheNewRequest = true
  /\ ladder_permits demo NonSacrificable TerminateOwnershipClosedGroup = false
  /\ ladder_permits demo Discardable TerminateOwnershipClosedGroup = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   The specification's own order, and the twenty weakenings of it.
   ------------------------------------------------------------------------- *)

(* S13 (R-12-073, R-07-027): the composed order passes all three conjuncts. *)
Theorem the_specification_order_is_a_bringup :
  BroughtUpInOrder demo spec_order.
Proof. apply bringup_ok_sound. reflexivity. Qed.

Example the_specification_order_grants_nothing_early :
  units_granted_early demo spec_order = 0 := eq_refl.

Example the_first_unit_stands_at_the_first_position :
  pos 0 spec_order = Some 0 /\ pos 4 spec_order = Some 4
  /\ pos 9 spec_order = None := conj eq_refl (conj eq_refl eq_refl).

Example no_unit_precedes_itself : precedes 0 0 spec_order = false := eq_refl.

(* Reading 9 as a computation: a unit the order omits precedes nothing and is
   preceded by nothing, which is what makes a deletion a refusal rather than
   a silence. Neither arm of `precedes` is reachable from `bringup_ok` on the
   generated families, the occurrence check refusing a deletion first, so the
   absent case is stated here or nowhere. *)
Example a_unit_the_order_omits_precedes_nothing :
  precedes 0 9 spec_order = false /\ precedes 9 0 spec_order = false
  /\ precedes 9 8 spec_order = false := conj eq_refl (conj eq_refl eq_refl).

Example the_roster_is_started_and_a_stranger_is_not :
  occurs 0 spec_order = true /\ occurs 9 spec_order = false :=
  conj eq_refl eq_refl.

Example a_unit_outside_the_roster_is_refused :
  no_stranger demo (cons 5 nil) = false /\ no_stranger demo (cons 4 nil) = true :=
  conj eq_refl eq_refl.

(* The four families, written out rather than described: any change to a
   generator, to the index set it walks, or to the order it walks over moves
   one of these four conversions. *)
Example the_transpositions_of_the_start_order :
  transpositions spec_order
  = cons (cons 1 (cons 0 (cons 2 (cons 3 (cons 4 nil)))))
    (cons (cons 0 (cons 2 (cons 1 (cons 3 (cons 4 nil)))))
    (cons (cons 0 (cons 1 (cons 3 (cons 2 (cons 4 nil)))))
    (cons (cons 0 (cons 1 (cons 2 (cons 4 (cons 3 nil))))) nil))) := eq_refl.

Example the_deletions_of_the_start_order :
  deletions spec_order
  = cons (cons 1 (cons 2 (cons 3 (cons 4 nil))))
    (cons (cons 0 (cons 2 (cons 3 (cons 4 nil))))
    (cons (cons 0 (cons 1 (cons 3 (cons 4 nil))))
    (cons (cons 0 (cons 1 (cons 2 (cons 4 nil))))
    (cons (cons 0 (cons 1 (cons 2 (cons 3 nil)))) nil)))) := eq_refl.

Example the_proper_suffixes_of_the_start_order :
  proper_suffixes spec_order
  = cons (cons 1 (cons 2 (cons 3 (cons 4 nil))))
    (cons (cons 2 (cons 3 (cons 4 nil)))
    (cons (cons 3 (cons 4 nil))
    (cons (cons 4 nil) (cons nil nil)))) := eq_refl.

Example the_duplicate_starts_of_the_start_order :
  duplicate_starts spec_order
  = cons (cons 0 (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))))
    (cons (cons 0 (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))))
    (cons (cons 0 (cons 1 (cons 0 (cons 2 (cons 3 (cons 4 nil))))))
    (cons (cons 0 (cons 1 (cons 2 (cons 0 (cons 3 (cons 4 nil))))))
    (cons (cons 0 (cons 1 (cons 2 (cons 3 (cons 0 (cons 4 nil))))))
    (cons (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 0 nil)))))) nil)))))
  := eq_refl.

(* The family's size is computed rather than claimed: four transpositions,
   five deletions, five proper suffixes and six duplicate starts. *)
Example the_generated_family_size :
  count_of (generated_weakenings spec_order) = 20 := eq_refl.

(* S14: every generated weakening fails the bring-up check. One conversion
   over the whole family. *)
Example every_generated_weakening_is_refused :
  all_of (fun w => negb (bringup_ok demo w)) (generated_weakenings spec_order)
  = true := eq_refl.

(* S14a: and per family, so a family that stopped biting is visible rather
   than absorbed by the conjunction above. Each family fails a different
   conjunct, which is what makes the three conjuncts of `bringup_ok`
   independent rather than one stated three ways. *)
Example every_transposition_grants_early :
  all_of (fun w => negb (grants_nothing_early demo w))
         (transpositions spec_order) = true := eq_refl.

Example every_deletion_leaves_a_unit_unstarted :
  all_of (fun w => negb (each_unit_once demo w)) (deletions spec_order)
  = true := eq_refl.

Example every_proper_suffix_leaves_a_unit_unstarted :
  all_of (fun w => negb (each_unit_once demo w)) (proper_suffixes spec_order)
  = true := eq_refl.

Example every_duplicate_start_starts_a_unit_twice :
  all_of (fun w => negb (each_unit_once demo w)) (duplicate_starts spec_order)
  = true := eq_refl.

(* No conjunct of the start order is dead. Each of the four adjacent
   transpositions breaks exactly one manifest edge, which is that property
   computed rather than asserted; and the specification breaks none, so the
   count is a measure of the weakening rather than of the check. *)
Example each_transposition_breaks_exactly_one_edge :
  map_over (units_granted_early demo) (transpositions spec_order)
  = cons 1 (cons 1 (cons 1 (cons 1 nil))) := eq_refl.

(* S14b: the same content as a quantifier over the index rather than an
   enumeration, so a family is refused for a reason rather than by a
   computation over the four, five, five and six members it happens to
   have. *)
Theorem no_adjacent_transposition_is_a_bringup :
  forall n : nat, Nat.ltb n 4 = true ->
    bringup_ok demo (swap_at n spec_order) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_deletion_is_a_bringup :
  forall n : nat, Nat.ltb n 5 = true ->
    bringup_ok demo (drop_at n spec_order) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_proper_suffix_is_a_bringup :
  forall n : nat, Nat.ltb n 5 = true ->
    bringup_ok demo (suffix_at (S n) spec_order) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_duplicate_start_is_a_bringup :
  forall n : nat, Nat.ltb n 6 = true ->
    bringup_ok demo (insert_at n 0 spec_order) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* =========================================================================
   Refutation witnesses over the bring-up order (R-05-166). Each is an
   alternative construction no index above generates, and each is shown to
   satisfy the obligations it does not break, so what refutes it is the
   named defect rather than the shape of the construction.
   ========================================================================= *)

(* A bring-up that starts every unit exactly once, in the order the manifest
   forbids: every unit is handed a capability designating one the order has
   not started. It is the whole of R-12-073's start-order clause read
   backwards, and nothing else in this file refuses it. *)
Definition reverse_bringup : list nat :=
  cons 4 (cons 3 (cons 2 (cons 1 (cons 0 nil)))).

Theorem the_reverse_bringup_grants_before_the_grantee_is_up :
  each_unit_once demo reverse_bringup = true
  /\ no_stranger demo reverse_bringup = true
  /\ grants_nothing_early demo reverse_bringup = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Example the_reverse_bringup_grants_four_units_early :
  units_granted_early demo reverse_bringup = 4 := eq_refl.

(* A bring-up that starts a unit the signed generation does not name.
   R-10-026 makes the generation the only origin of the roster, so a unit
   reached at bring-up and absent from it is an addition to the composed
   graph, which R-07-026's criterion refuses in the same words. It keeps the
   order and starts every roster member, so the stranger check is the only
   thing that refuses it. *)
Definition stranger_bringup : list nat := app spec_order (cons 9 nil).

Theorem the_stranger_bringup_adds_a_unit_to_the_graph :
  each_unit_once demo stranger_bringup = true
  /\ grants_nothing_early demo stranger_bringup = true
  /\ no_stranger demo stranger_bringup = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Example the_stranger_the_witness_names :
  occurs 9 stranger_bringup = true /\ count_of stranger_bringup = 6 :=
  conj eq_refl eq_refl.

(* =========================================================================
   Refutation witnesses over the loader (R-10-026).
   ========================================================================= *)

Definition sig_quiet : Signals := fun _ => 0.

Definition sig_pressure : Signals := fun _ => 7.

Definition sig_backlog : Signals := fun d =>
  if detector_eqb d QuarantineBacklogPastBound then 9 else 0.

Example the_probe_signals :
  sig_quiet PoolLow = 0 /\ sig_pressure PoolLow = 7
  /\ sig_backlog QuarantineBacklogPastBound = 9 /\ sig_backlog PoolLow = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* A component graph discovered at run time rather than read out of the
   signed generation: under pressure it brings up a shorter roster. This is
   the construction R-10-026 and R-10-028 exclude, no runtime text parsing
   and no mutable overlay standing between the generation and the tree. *)
Definition discovered_loader (m : Machine) : Loader m := fun sig =>
  if Nat.ltb 0 (sig PoolLow) then nil else m.(start_order).

Theorem the_discovered_loader_is_refuted :
  ~ IsTheSignedComposition demo (discovered_loader demo).
Proof. intros H. specialize (H sig_pressure). discriminate H. Qed.

(* And it agrees with the specification wherever nothing is observed, so
   what refutes it is the runtime dependence and not a different roster. *)
Example the_discovered_loader_agrees_under_no_pressure :
  discovered_loader demo sig_quiet = demo.(start_order)
  /\ discovered_loader demo (fun _ => 1) = nil := conj eq_refl eq_refl.

(* =========================================================================
   Refutation witnesses over the re-grant (R-12-074, R-10-037).
   ========================================================================= *)

(* A re-grant that hands a restarting unit the reverse of every edge it
   holds, on the ground that a restarted server needs to be reachable. It
   respects the revocation epoch and mints an edge the manifest does not
   fix, which is R-12-074's own distinction between a re-instantiator and a
   minter. *)
Definition helpful_regrant (m : Machine) : Regrant m := fun u v =>
  andb (orb (m.(manifest) u v) (m.(manifest) v u)) (negb (m.(retired) u v)).

Theorem the_helpful_regrant_mints :
  ~ MintsNothing demo (helpful_regrant demo).
Proof. intros H. specialize (H 3 4 eq_refl). discriminate H. Qed.

Theorem the_helpful_regrant_still_respects_the_epoch :
  CarriesNoRetiredAuthority demo (helpful_regrant demo).
Proof.
  intros u v H. unfold helpful_regrant in H.
  destruct (andb_split _ _ H) as [ _ Hr ].
  destruct (demo.(retired) u v); [ discriminate Hr | reflexivity ].
Qed.

(* R-12-074's sentence read as the equality its word "exactly" invites: the
   re-grant is the manifest. It mints nothing, and it resurrects the grant
   the current revocation epoch retired, which R-10-037's acceptance clause
   is what forbids. This is gap b as a construction rather than as a
   remark. *)
Definition faithful_regrant (m : Machine) : Regrant m := m.(manifest).

Theorem the_faithful_regrant_mints_nothing :
  MintsNothing demo (faithful_regrant demo).
Proof. intros u v H. exact H. Qed.

Theorem the_faithful_regrant_resurrects_a_retired_grant :
  ~ CarriesNoRetiredAuthority demo (faithful_regrant demo).
Proof. intros H. specialize (H 4 3 eq_refl). discriminate H. Qed.

(* Gap b, made checkable rather than asserted: the two readings of the same
   sentence differ on the one edge the epoch retired, so the choice is not
   free and no entry makes it. *)
Theorem the_regrant_extent_is_observable :
  spec_regrant demo 4 3 = false /\ faithful_regrant demo 4 3 = true.
Proof. split; reflexivity. Qed.

(* =========================================================================
   Refutation witnesses over detection and reaction (R-12-087, R-12-088,
   R-12-089).
   ========================================================================= *)

(* A detector that answers by looking at every other detector's signal,
   which is R-12-087's "searches the component graph" and R-12-088's scan
   proportional to the number of compartments. *)
Definition graph_searching_detect (m : Machine) : Detection m := fun sig _ =>
  any_of (fun e => Nat.leb (m.(threshold) e) (sig e)) all_detectors.

Theorem the_graph_searching_detector_is_refuted :
  ~ ReadsOnlyItsOwnSignal demo (graph_searching_detect demo).
Proof.
  intros H. specialize (H sig_quiet sig_backlog PoolLow eq_refl). discriminate H.
Qed.

(* Both detectors fire at the declared threshold and not below it, so the
   two differ in what they read and not in where they cut. *)
Example both_detectors_fire_at_the_declared_threshold :
  graph_searching_detect demo (fun _ => 3) PoolLow = true
  /\ graph_searching_detect demo (fun _ => 2) PoolLow = false :=
  conj eq_refl eq_refl.

(* The specification's detector reads the same two signals and answers the
   same way at the detector they agree on, so what refutes the construction
   above is the scan and not the signals. *)
Theorem the_specification_detector_separates_the_two_signals :
  spec_detect demo sig_quiet PoolLow = spec_detect demo sig_backlog PoolLow
  /\ spec_detect demo sig_backlog QuarantineBacklogPastBound = true
  /\ spec_detect demo sig_quiet QuarantineBacklogPastBound = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* The detector fires at its threshold and not below it, which is the
   boundary R-16-027's assertion threshold names. *)
Example the_detector_fires_at_the_declared_threshold :
  spec_detect demo (fun _ => 3) PoolLow = true
  /\ spec_detect demo (fun _ => 2) PoolLow = false := conj eq_refl eq_refl.

(* R-16-027's band, and the same pair read backwards. A clear threshold
   above the assertion threshold declares a band that never clears, which is
   the oscillation the entry exists to bound. *)
Theorem the_demo_declares_a_hysteresis_band :
  DeclaresAHysteresisBand demo.(clear_threshold) demo.(threshold).
Proof. reflexivity. Qed.

Theorem the_reversed_band_is_refuted :
  ~ DeclaresAHysteresisBand demo.(threshold) demo.(clear_threshold).
Proof. intros H. discriminate H. Qed.

(* The band's own boundary, and gap g: a pair whose clear threshold equals
   its assertion threshold declares no hysteresis at all, and R-16-027
   requires both to be declared without saying whether they may coincide.
   This file admits the degenerate band, which is the weaker reading and the
   one the entry's words carry; a rewrite that refused it would be this
   statement deciding what the register left open. *)
Theorem the_degenerate_band_is_admitted :
  DeclaresAHysteresisBand demo.(threshold) demo.(threshold).
Proof. reflexivity. Qed.

(* An action computed from what was observed rather than read out of the
   composition: past its threshold the pool's response becomes a
   termination. R-12-087's criterion names this by its consequence, and
   R-12-089 names the mechanism it deletes rather than ports. *)
Definition scoring_policy (m : Machine) : Policy m := fun d sig =>
  if Nat.ltb (m.(threshold) d) (sig d)
  then TerminateOwnershipClosedGroup else m.(respond) d.

Theorem the_scoring_policy_is_refuted :
  ~ IsCompositionFixed demo (scoring_policy demo).
Proof.
  intros H. specialize (H PoolLow sig_quiet sig_pressure). discriminate H.
Qed.

(* It agrees with the specification below the threshold, so what refutes it
   is the runtime dependence and not a different table. *)
Example the_scoring_policy_agrees_below_the_threshold :
  scoring_policy demo PoolLow sig_quiet = demo.(respond) PoolLow
  /\ scoring_policy demo PoolLow (fun _ => 3) = demo.(respond) PoolLow
  /\ scoring_policy demo PoolLow sig_pressure = TerminateOwnershipClosedGroup :=
  conj eq_refl (conj eq_refl eq_refl).

(* R-12-089's equivalence class: the victim is composition-fixed, so the
   class it belongs to does not vary with what was observed. *)
Definition declared_victim (m : Machine) : Selector m := fun _ => m.(victim).

Theorem the_declared_victim_stays_inside_one_class :
  forall m : Machine, SelectsInsideOneClass m (declared_victim m).
Proof. intros m s1 s2. reflexivity. Qed.

Example the_declared_victim_is_a_manifest_unit :
  declared_victim demo sig_quiet = 1 := eq_refl.

(* A victim chosen by a runtime score, which under pressure reaches the unit
   the composition made non-sacrificable: the `oom_score_adj` analog
   R-12-089's criterion deletes. *)
Definition scoring_selector (m : Machine) : Selector m := fun sig =>
  if Nat.ltb (m.(threshold) PoolLow) (sig PoolLow) then 0 else 1.

Theorem the_scoring_selector_is_refuted :
  ~ SelectsInsideOneClass demo (scoring_selector demo).
Proof. intros H. specialize (H sig_pressure sig_quiet). discriminate H. Qed.

Example the_scoring_selector_crosses_the_class_boundary :
  scoring_selector demo sig_pressure = 0
  /\ scoring_selector demo (fun _ => 3) = 1
  /\ scoring_selector demo sig_quiet = 1 := conj eq_refl (conj eq_refl eq_refl).

(* R-12-089's ladder clause: the non-sacrificable class declares no action
   that ends a unit, and a ladder that puts one there is refused. *)
Theorem the_specification_ladder_spares_the_non_sacrificable :
  SparesTheNonSacrificable spec_ladder.
Proof. reflexivity. Qed.

Definition terminating_ladder (c : Criticality) : list Action :=
  cons TerminateOwnershipClosedGroup (spec_ladder c).

Theorem the_terminating_ladder_is_refuted :
  ~ SparesTheNonSacrificable terminating_ladder.
Proof. intros H. discriminate H. Qed.

(* And it spares nothing about the other four classes, whose ladders already
   carry a termination, so the obligation is about the class the register
   names and not about the ladder's shape. *)
Example the_discardable_ladder_already_terminates :
  all_of (fun a => negb (terminates a)) (spec_ladder Discardable) = false
  := eq_refl.

(* =========================================================================
   Refutation witnesses over the backoff, the rate limit and the boot count
   (R-16-007, R-16-027).
   ========================================================================= *)

Theorem the_demo_schedule_is_within_its_ceiling :
  BoundedSchedule demo.(backoff_ceiling) demo.(backoff_schedule).
Proof. reflexivity. Qed.

Example the_demo_backoff_schedule_and_its_ceiling :
  map_over (spec_backoff demo) (upto 6)
  = cons 1 (cons 2 (cons 3 (cons 5 (cons 5 (cons 5 nil))))) := eq_refl.

(* A backoff that grows without a declared ceiling: R-16-007 bounds the
   worst case to downtime, and a schedule whose steps run past the ceiling
   is the construction that makes the downtime unbounded instead. *)
Definition doubling_schedule : list nat :=
  cons 1 (cons 2 (cons 4 (cons 8 (cons 16 nil)))).

Theorem the_doubling_schedule_is_refuted :
  ~ BoundedSchedule demo.(backoff_ceiling) doubling_schedule.
Proof. intros H. discriminate H. Qed.

Example the_doubling_schedule_passes_the_ceiling_at_its_fourth_step :
  delay_at doubling_schedule demo.(backoff_ceiling) 3 = 8
  /\ Nat.leb (delay_at doubling_schedule demo.(backoff_ceiling) 3)
             demo.(backoff_ceiling) = false := conj eq_refl eq_refl.

(* The whole schedule as the delays it produces, so that every step is
   checked and not only the one that crosses: the fallback past the last
   declared step is still the ceiling, which is what makes the crossing a
   property of the schedule rather than of the fallback. *)
Example the_doubling_schedule_delays :
  map_over (delay_at doubling_schedule demo.(backoff_ceiling)) (upto 6)
  = cons 1 (cons 2 (cons 4 (cons 8 (cons 16 (cons 5 nil))))) := eq_refl.

(* The two admission obligations are independent: one construction ignores
   the dwell and keeps the window, the other keeps the dwell and ignores the
   window, and each is refuted by exactly the clause it drops. *)
Definition eager_admits (m : Machine) : Admission m := fun s =>
  Nat.ltb s.(interventions) m.(max_interventions).

Theorem the_eager_admission_ignores_the_dwell :
  ~ RespectsTheDwell demo (eager_admits demo)
  /\ RespectsTheWindow demo (eager_admits demo).
Proof.
  split.
  - intros H. specialize (H (declared_at 0 0 0 0) eq_refl). discriminate H.
  - intros s H. unfold eager_admits. exact H.
Qed.

Definition patient_admits (m : Machine) : Admission m := fun s =>
  Nat.leb m.(min_dwell) s.(dwell).

Theorem the_patient_admission_ignores_the_window :
  RespectsTheDwell demo (patient_admits demo)
  /\ ~ RespectsTheWindow demo (patient_admits demo).
Proof.
  split.
  - intros s H. unfold patient_admits. exact H.
  - intros H. specialize (H (declared_at 0 5 9 0) eq_refl). discriminate H.
Qed.

Example the_declared_bands_are_the_demo_machine_s :
  spec_admits demo (declared_at 0 0 1 0) = false
  /\ spec_admits demo (declared_at 0 0 2 0) = true
  /\ spec_admits demo (declared_at 0 2 9 0) = true
  /\ spec_admits demo (declared_at 0 3 9 0) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* A limiter that never escalates: past the window's count it repeats the
   ordinary action, which is R-16-027's "a mechanism reported as succeeding
   once per window, forever". *)
Definition unlimited_limiter (m : Machine) : Limiter m := fun _ a => a.

Theorem the_unlimited_limiter_is_refuted :
  ~ EscalatesPastTheRateLimit demo (unlimited_limiter demo).
Proof.
  intros H. specialize (H (declared_at 0 5 9 0) RefuseTheNewRequest eq_refl).
  discriminate H.
Qed.

Example the_specification_limiter_passes_the_action_below_the_limit :
  spec_limiter demo (declared_at 0 2 9 0) RefuseTheNewRequest
    = RefuseTheNewRequest
  /\ spec_limiter demo (declared_at 0 3 9 0) RefuseTheNewRequest
    = EscalateToRotReset := conj eq_refl eq_refl.

(* A boot admission with no count: R-16-007's reset loop, unbounded. *)
Definition unbounded_boot (m : Machine) : BootAdmission m := fun _ => true.

Theorem the_unbounded_boot_is_refuted :
  ~ BootCounted demo (unbounded_boot demo).
Proof.
  intros H. specialize (H (declared_at 0 0 0 7) eq_refl). discriminate H.
Qed.

Example the_boot_count_bound :
  spec_boot_admit demo (declared_at 0 0 0 2) = true
  /\ spec_boot_admit demo (declared_at 0 0 0 3) = false := conj eq_refl eq_refl.

(* =========================================================================
   Refutation witnesses over hidden state (R-12-073).
   ========================================================================= *)

Definition probe_declared : Declared := declared_at 0 0 9 0.

Definition probe_quiet : State :=
  {| declared := probe_declared; trace := nil |}.

Definition probe_seen : State :=
  {| declared := probe_declared; trace := cons PoolLow nil |}.

Example the_two_probe_states_declare_the_same_thing :
  probe_declared = declared_at 0 0 9 0
  /\ probe_quiet.(declared) = probe_seen.(declared)
  /\ probe_quiet.(trace) = nil := conj eq_refl (conj eq_refl eq_refl).

(* A supervisor whose reaction turns on an accumulation R-16-027 does not
   declare: on a machine that has seen nothing it refuses, and on one that
   has it responds. Both states declare the same thing, so the difference is
   state the composition cannot see, which is what "hidden-state-free by
   construction" excludes. *)
Definition trace_reading_supervisor (m : Machine) : Supervisor := fun s d =>
  match s.(trace) with
  | nil => RefuseTheNewRequest
  | cons _ _ => m.(respond) d
  end.

Theorem the_trace_reading_supervisor_carries_hidden_state :
  ~ HiddenStateFree (trace_reading_supervisor demo).
Proof.
  intros H. specialize (H probe_quiet probe_seen PoolExhausted eq_refl).
  discriminate H.
Qed.

(* And it agrees with the composition's own table wherever the undeclared
   accumulation is non-empty, so what refutes it is the read and not the
   table it reads. *)
Example the_trace_reading_supervisor_agrees_where_the_trace_is_not_empty :
  trace_reading_supervisor demo probe_seen PoolExhausted
    = demo.(respond) PoolExhausted
  /\ trace_reading_supervisor demo probe_quiet PoolExhausted
    = RefuseTheNewRequest := conj eq_refl eq_refl.

(* The specification's own supervisor on the same two states, so that the
   obligation above is not proved from a premise nothing satisfies: it
   answers the same on both, and it answers differently at two detectors, so
   it is neither constant nor state-reading. *)
Theorem the_specification_supervisor_is_inhabited_and_not_constant :
  spec_supervisor demo probe_quiet PoolExhausted
    = spec_supervisor demo probe_seen PoolExhausted
  /\ spec_supervisor demo probe_quiet PoolExhausted = ShedOwnerLocalState
  /\ spec_supervisor demo probe_quiet PoolLow = RefuseTheNewRequest.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so "Closed under the global context" is
   that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions all_of.
Print Assumptions any_of.
Print Assumptions count_of.
Print Assumptions map_over.
Print Assumptions filter_of.
Print Assumptions upto.
Print Assumptions before_last.
Print Assumptions at_index.
Print Assumptions only_if.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions only_if_elim.
Print Assumptions all_of_true.
Print Assumptions nat_leb_refl.
Print Assumptions at_index_holds.
Print Assumptions the_empty_conjunction_holds.
Print Assumptions the_empty_disjunction_fails.
Print Assumptions nothing_has_length_zero.
Print Assumptions before_last_of_nothing.
Print Assumptions the_index_set_of_three.
Print Assumptions only_if_is_implication.
Print Assumptions all_detectors.
Print Assumptions all_actions.
Print Assumptions all_classes.
Print Assumptions there_are_eight_detectors.
Print Assumptions there_are_ten_actions.
Print Assumptions there_are_five_criticality_classes.
Print Assumptions detector_eqb.
Print Assumptions detector_eqb_refl.
Print Assumptions detector_eqb_true.
Print Assumptions action_eqb.
Print Assumptions action_eqb_refl.
Print Assumptions action_eqb_true.
Print Assumptions terminates.
Print Assumptions which_actions_terminate.
Print Assumptions pos_from.
Print Assumptions pos.
Print Assumptions occurs.
Print Assumptions occurrences.
Print Assumptions precedes.
Print Assumptions each_unit_once.
Print Assumptions no_stranger.
Print Assumptions grants_ok_for.
Print Assumptions grants_nothing_early.
Print Assumptions bringup_ok.
Print Assumptions BroughtUpInOrder.
Print Assumptions bringup_ok_sound.
Print Assumptions bringup_ok_complete.
Print Assumptions all_of_app.
Print Assumptions leb_split.
Print Assumptions all_of_upto.
Print Assumptions an_ordered_bringup_starts_the_grantee_first.
Print Assumptions Signals.
Print Assumptions Loader.
Print Assumptions spec_loader.
Print Assumptions IsTheSignedComposition.
Print Assumptions the_specification_loads_the_signed_composition.
Print Assumptions Regrant.
Print Assumptions spec_regrant.
Print Assumptions MintsNothing.
Print Assumptions CarriesNoRetiredAuthority.
Print Assumptions the_specification_regrant_mints_nothing.
Print Assumptions the_specification_regrant_carries_no_retired_authority.
Print Assumptions Detection.
Print Assumptions spec_detect.
Print Assumptions ReadsOnlyItsOwnSignal.
Print Assumptions the_specification_detector_reads_only_its_own_signal.
Print Assumptions DeclaresAHysteresisBand.
Print Assumptions Policy.
Print Assumptions spec_policy.
Print Assumptions IsCompositionFixed.
Print Assumptions the_specification_policy_is_composition_fixed.
Print Assumptions Selector.
Print Assumptions SelectsInsideOneClass.
Print Assumptions ladder_permits.
Print Assumptions SparesTheNonSacrificable.
Print Assumptions Backoff.
Print Assumptions delay_at.
Print Assumptions spec_backoff.
Print Assumptions BoundedSchedule.
Print Assumptions WithinTheCeiling.
Print Assumptions a_bounded_schedule_bounds_every_attempt.
Print Assumptions declared_at.
Print Assumptions Admission.
Print Assumptions spec_admits.
Print Assumptions RespectsTheDwell.
Print Assumptions RespectsTheWindow.
Print Assumptions the_specification_respects_the_dwell.
Print Assumptions the_specification_respects_the_window.
Print Assumptions Limiter.
Print Assumptions spec_limiter.
Print Assumptions EscalatesPastTheRateLimit.
Print Assumptions the_specification_escalates_past_the_rate_limit.
Print Assumptions BootAdmission.
Print Assumptions spec_boot_admit.
Print Assumptions BootCounted.
Print Assumptions the_specification_counts_boots.
Print Assumptions Supervisor.
Print Assumptions HiddenStateFree.
Print Assumptions spec_supervisor.
Print Assumptions the_specification_supervisor_is_hidden_state_free.
Print Assumptions swap_at.
Print Assumptions drop_at.
Print Assumptions suffix_at.
Print Assumptions insert_at.
Print Assumptions transpositions.
Print Assumptions deletions.
Print Assumptions proper_suffixes.
Print Assumptions duplicate_starts.
Print Assumptions generated_weakenings.
Print Assumptions units_granted_early.
Print Assumptions spec_order.
Print Assumptions spec_ladder.
Print Assumptions demo_respond.
Print Assumptions demo.
Print Assumptions the_demo_machine_declares.
Print Assumptions the_demo_thresholds.
Print Assumptions the_demo_manifest_is_a_chain.
Print Assumptions the_demo_has_one_retired_edge.
Print Assumptions the_demo_criticality_assignment.
Print Assumptions the_demo_responds_to_every_detector.
Print Assumptions the_non_sacrificable_ladder_and_the_discardable_one.
Print Assumptions the_specification_order_is_a_bringup.
Print Assumptions the_specification_order_grants_nothing_early.
Print Assumptions the_first_unit_stands_at_the_first_position.
Print Assumptions no_unit_precedes_itself.
Print Assumptions a_unit_the_order_omits_precedes_nothing.
Print Assumptions the_roster_is_started_and_a_stranger_is_not.
Print Assumptions a_unit_outside_the_roster_is_refused.
Print Assumptions the_transpositions_of_the_start_order.
Print Assumptions the_deletions_of_the_start_order.
Print Assumptions the_proper_suffixes_of_the_start_order.
Print Assumptions the_duplicate_starts_of_the_start_order.
Print Assumptions the_generated_family_size.
Print Assumptions every_generated_weakening_is_refused.
Print Assumptions every_transposition_grants_early.
Print Assumptions every_deletion_leaves_a_unit_unstarted.
Print Assumptions every_proper_suffix_leaves_a_unit_unstarted.
Print Assumptions every_duplicate_start_starts_a_unit_twice.
Print Assumptions each_transposition_breaks_exactly_one_edge.
Print Assumptions no_adjacent_transposition_is_a_bringup.
Print Assumptions no_deletion_is_a_bringup.
Print Assumptions no_proper_suffix_is_a_bringup.
Print Assumptions no_duplicate_start_is_a_bringup.
Print Assumptions reverse_bringup.
Print Assumptions the_reverse_bringup_grants_before_the_grantee_is_up.
Print Assumptions the_reverse_bringup_grants_four_units_early.
Print Assumptions stranger_bringup.
Print Assumptions the_stranger_bringup_adds_a_unit_to_the_graph.
Print Assumptions the_stranger_the_witness_names.
Print Assumptions sig_quiet.
Print Assumptions sig_pressure.
Print Assumptions sig_backlog.
Print Assumptions the_probe_signals.
Print Assumptions discovered_loader.
Print Assumptions the_discovered_loader_is_refuted.
Print Assumptions the_discovered_loader_agrees_under_no_pressure.
Print Assumptions helpful_regrant.
Print Assumptions the_helpful_regrant_mints.
Print Assumptions the_helpful_regrant_still_respects_the_epoch.
Print Assumptions faithful_regrant.
Print Assumptions the_faithful_regrant_mints_nothing.
Print Assumptions the_faithful_regrant_resurrects_a_retired_grant.
Print Assumptions the_regrant_extent_is_observable.
Print Assumptions graph_searching_detect.
Print Assumptions the_graph_searching_detector_is_refuted.
Print Assumptions both_detectors_fire_at_the_declared_threshold.
Print Assumptions the_specification_detector_separates_the_two_signals.
Print Assumptions the_detector_fires_at_the_declared_threshold.
Print Assumptions the_demo_declares_a_hysteresis_band.
Print Assumptions the_reversed_band_is_refuted.
Print Assumptions the_degenerate_band_is_admitted.
Print Assumptions scoring_policy.
Print Assumptions the_scoring_policy_is_refuted.
Print Assumptions the_scoring_policy_agrees_below_the_threshold.
Print Assumptions declared_victim.
Print Assumptions the_declared_victim_stays_inside_one_class.
Print Assumptions the_declared_victim_is_a_manifest_unit.
Print Assumptions scoring_selector.
Print Assumptions the_scoring_selector_is_refuted.
Print Assumptions the_scoring_selector_crosses_the_class_boundary.
Print Assumptions the_specification_ladder_spares_the_non_sacrificable.
Print Assumptions terminating_ladder.
Print Assumptions the_terminating_ladder_is_refuted.
Print Assumptions the_discardable_ladder_already_terminates.
Print Assumptions the_demo_schedule_is_within_its_ceiling.
Print Assumptions the_demo_backoff_schedule_and_its_ceiling.
Print Assumptions doubling_schedule.
Print Assumptions the_doubling_schedule_is_refuted.
Print Assumptions the_doubling_schedule_passes_the_ceiling_at_its_fourth_step.
Print Assumptions the_doubling_schedule_delays.
Print Assumptions eager_admits.
Print Assumptions the_eager_admission_ignores_the_dwell.
Print Assumptions patient_admits.
Print Assumptions the_patient_admission_ignores_the_window.
Print Assumptions the_declared_bands_are_the_demo_machine_s.
Print Assumptions unlimited_limiter.
Print Assumptions the_unlimited_limiter_is_refuted.
Print Assumptions the_specification_limiter_passes_the_action_below_the_limit.
Print Assumptions unbounded_boot.
Print Assumptions the_unbounded_boot_is_refuted.
Print Assumptions the_boot_count_bound.
Print Assumptions probe_declared.
Print Assumptions probe_quiet.
Print Assumptions probe_seen.
Print Assumptions the_two_probe_states_declare_the_same_thing.
Print Assumptions trace_reading_supervisor.
Print Assumptions the_trace_reading_supervisor_carries_hidden_state.
Print Assumptions the_trace_reading_supervisor_agrees_where_the_trace_is_not_empty.
Print Assumptions the_specification_supervisor_is_inhabited_and_not_constant.
