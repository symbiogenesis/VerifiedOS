(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ElasticDomain.v

   The elastic-domain contract, crown-jewel row 31 (CJ-ELASTIC), as the
   register fixes it: R-07-037e's envelope and its confinement, with
   R-07-037f's fixed-tier floor and R-07-037i's launch by activation;
   R-07-037g's earliest-eligible-virtual-deadline-first dispatch with the
   tentative yield R-07-031b records, the boundary rule and the share
   bound; R-07-037h's yield-bound obligation; R-08-047b's four pool-service
   guarantees and the heap library's per-allocation narrowing, drawn from
   R-15-007k's composition-fixed size-class table; and R-08-047c's
   confinement of every pool-derived capability to the domain.

   The Requires are load-bearing. PartitionContext.v's Rotation is the
   intra-slot step R-07-037g extends with the inter-application clear, and
   its Action and constants_paid price it; CyclicExecutive.v's Slot, Frame
   and slot_index_at are the envelope's geometry, so a runtime width choice
   is refuted by moving an instant another tenant owns; MemoryPlan.v's
   MemClass indexes the pool extents and its representable_granule decides
   whether a size class narrows exactly.

   What this file is. A statement artifact in PartitionContext.v's idiom,
   not a proof development and not an implementation. Every quantity the
   register leaves to composition is a field of a record. Nothing is
   admitted and nothing is axiomatized: the Print Assumptions block at the
   end reports every shipped constant closed under the global context.
   What the proof gate's green line means for it: compiled, axiom-free,
   witnessed and enumerated, and not verified. Nothing here executes on
   either emulator, and no kernel, pool service, heap library or toolchain
   pass is proved against it here.

   What is stated, and what consumes it.

   S1  The envelope (R-07-037e, R-07-037f, R-07-037i, R-08-047a). A
       Domain carries one label, an enumerated member list, a manifest per
       compartment, its cores, its placed dormant contexts and one extent
       per memory class; envelope_admits checks the one label, the
       fixed-tier floor and a placed context per member, and launch_ok
       activates only a placed context.
   S2  Confinement of the runtime choices (R-07-037e, R-07-037g, R-07-032).
       ReadsOnlyItsLabel over a Global state whose frame and other labels
       are separate from the domain's own state, and MovesNothingOutside
       over domain transitions.
   S3  The dispatch rule (R-07-037g, R-07-031b, R-07-027a). The fields the
       register names (active bit, pending, eligible time, virtual
       deadline, virtual time, focus), Selects as earliest eligible
       virtual deadline with the enumeration order breaking ties, a
       reference select proved to choose exactly that, the tentative-yield
       reply, the boundary rule, the charge at a real yield, and Run as one
       dispatch with its invocations, answered replies and sink.
   S4  The intra-slot step (R-07-037g, R-07-037d, R-07-014c). ElasticStep
       is PartitionContext.v's Rotation, plus the zeroize of the
       zeroize-class state whenever the two members belong to different
       applications, priced at one vmclear.
   S5  The share bound (R-07-037g, R-11-006c). Stints of served and idle
       time, the lag each member accrues against its weight's share of the
       competing set, LagBounded and ShortfallBounded, ShareBound at the
       register's bound, and the proof that the instant half carries the
       interval half, so Q34b owes the instant half alone.
   S6  The yield-bound obligation (R-07-037h). Poll sites on back-edges
       and recursive entries over a control-flow graph, reactions as
       poll-free paths, YieldBoundAdmits, and the counter protocol whose
       gaps between invocations are proved within the call bound.
   S7  The pool service (R-08-047b, R-15-007k). An allocation history over
       an arena, and the four guarantees stated over it: live chunks
       disjoint, bounds exact at a size class of the table, zeroed at
       handoff, reuse only after R-08-006's barrier and a whole sweep
       begun after it (R-08-007a).
   S8  The heap library's narrowing (R-08-047b). The same arena and
       history one level down, a member's own chunk being the arena: every
       returned capability narrowed exactly to its allocation, live
       allocations disjoint, and in-chunk reuse behind the same gate.
   S9  Capability confinement (R-08-047c). Declared edges, what each kind
       can carry, edges_confine, and the proof that no sequence of
       transfers along the declared edges puts a pool-derived capability
       outside the domain.

   Q34b consumes S2, S3, S4 and S5: its kernel statement refines select,
   reply, charge and ElasticStep over PartitionContext.v's contexts and
   proves LagBounded at the register's bound, which finding F1 below shows
   it cannot do as the register now states it. Q34c
   consumes S7, S8 and S9: the chunk service and heap library refine
   PoolGuarantees and HeapNarrows, and the composition's size-class table
   discharges class_exact. Q34d consumes S6. Q34e consumes S1 and S3's
   admission side (decl_admits) for the demonstration composition.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. Virtual time is exact rational EEVDF arithmetic. R-07-037g names the
      published algorithm, whose eligible times and deadlines are the
      running sums of service over weight; Q is that arithmetic exactly,
      and a fixed-point kernel refines this rule only if Q34b's proof
      covers its rounding. No representation is chosen for the kernel.
   2. The fixed tie order is the member enumeration order. Any fixed order
      is an enumeration order, so no generality is lost.
   3. The request lasts while the service since this dispatch is below the
      effective request, and the kernel answers a tentative call at the
      virtual time that service has advanced.
   4. A run is one dispatch: invocations of (iii) at most one call bound
      apart, every one but the last answered continue, and the last either
      the member's own real yield or a tentative call answered
      switch-requested followed by the sink, whose next invocation is
      enacted as the real yield whatever its flag (R-07-037g's backstop).
   5. Lag is service lag: the member's weight share of served time while it
      competes (live with work pending), less the service it received. A
      member outside the competing set accrues nothing, which is the lag
      preservation R-07-037g asks of a leave, and a rebalance places a
      joining or reweighted member at the eligible time its preserved lag
      fixes. A real yield with nothing pending leaves the eligible set and
      moves no other member's accounting. Both are the literal rule; F3
      reports what the literal rule does.
   6. The time base of the share bound is a parameter, ServedTime or
      SlotTime, because R-07-037g's "the domain's time on its core" does not
      say whether the idle tail the boundary rule leaves is in it; F2.
   7. The intra-slot step's zeroize-class state is PartitionContext.v's
      zeroized CSR class, R-07-014a having deleted the save area, so the
      inter-application vmclear is a write of zero_word to that class.
   8. Poll sites sit at block entries, and "a poll site on every loop
      back-edge" is a poll site at the target of every back-edge.
   9. A chunk's bytes, its capability and the memory it is handed out
      over are an observable history of events, and the four guarantees
      are stated over that history; Q34c relates the history to the
      service's state.
  10. An edge carries a capability exactly when R-08-047c's rule says it
      can: a register endpoint with a capability slot or tagged registers,
      a shared window with capability-store permission, a sentry, or a
      device window. A ring never does.

   Findings. None is closed here; each is a register question for its
   owner. F1 to F3 are exhibited by the constructions named, as computed
   facts; F4 is the reading this statement takes, recorded as a question:

   F1. R-07-037g's lag bound omits the sink. The criterion bounds lag by
       the largest declared request plus one call bound, but a conforming
       member runs up to one call bound past its last continue and then up
       to one yield bound for its sink, which the boundary rule itself
       budgets. the_register_s_lag_bound_is_refuted exhibits a two-member
       trace every step of which the rule forces or permits, ending with
       both lags of magnitude 22/5 against a bound of 4; the same trace sits
       inside the request plus a call bound plus a yield bound, which
       sink_inclusive_lag_bound names without adopting.
   F2. The share bound's time base is unstated. Read over the domain's slot
       time, the boundary rule's own idle tails accrue shortfall slot after
       slot: the_slot_time_reading_is_refuted exhibits one member alone at
       lag 8 against a bound of 4 after two slots. Read over served time,
       the bound holds of that trace and says nothing about idling (F3).
   F3. "Joins, leaves and reweights preserve lag under EEVDF's published
       rules" does not say whose lag. Taken literally, a member leaving
       with positive lag moves no other accounting, and
       the_literal_leave_rule_is_not_work_conserving exhibits a member with
       work pending that is never eligible again, the core idling slot
       after slot, while its served-time lag stays inside the register's
       bound. The published remedy adjusts virtual time at the leave, which
       shifts every other member's accounting lag away from its service
       lag, so the choice decides what the share bound quantifies. charge
       and rebalance implement the literal reading and change with the
       register's answer.
   F4. "Each live member's lag" is read over the competing set. A live
       member with nothing pending accrues entitlement it never uses under
       the launched-set reading, which no dispatch can bound.

   What this file deliberately does not author, with the owner of each:

   a. The kernel's representation of the fields over PartitionContext.v's
      contexts, the request cell, the label-internal unwinding case and
      the proof of the share bound: Q34b.
   b. The chunk service, the heap library, their refinement of S7 and S8,
      per-island pools and the quarantine's shape and sizing (R-08-047e):
      Q34c.
   c. The yield-point pass, the static counter and the per-function cost
      triple a reaction crossing a call carries (R-05-102): Q34d. S6
      states the obligation over a graph the pass would produce.
   d. R-08-047d's exhaustion ladder and R-11-006c's focus dispatch bound:
      the ladder is not among row 31's statements, and the bound's
      derivation is admission arithmetic over constants Q34e composes.
   e. Every composition magnitude. The demonstration declarations below
      carry arbitrary witness values and no composition claim.

   Non-vacuity (R-05-165, R-05-166). Every obligation is stated as a
   property of an arbitrary dispatch, step, run, graph, history or
   distribution, proved of the specification where a proof belongs here,
   and refuted of a construction the register's own sentence excludes. The
   seven refutations the Check names are exhibited: a dispatch reading
   outside state (leaky_choice), a member cut by the boundary
   (thin_boundary, no_boundary and the backstop alone), two live chunks
   sharing a byte, a chunk wider than its allocation, a chunk handed out
   unzeroed, a chunk reused ahead of the sweep (and a sweep begun before
   the barrier), and a pool capability held outside the domain (a
   capability-carrying endpoint and a store-permitted window). Each pool
   refutation breaks exactly one guarantee and is shown to keep the other
   three. Every record carries a named witness.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-102 R-05-163 R-05-165 R-05-166 R-07-014a R-07-014c R-07-027a R-07-031b
      R-07-032 R-07-036 R-07-037b R-07-037c R-07-037d R-07-037e R-07-037f R-07-037g R-07-037h
      R-07-037i R-08-006 R-08-007a R-08-047a R-08-047b R-08-047c R-08-047d R-08-047e R-11-006c
      R-12-007 R-15-007c R-15-007k
   SHA256: f3d86d7923ec5aecdaaf1746648524bbd09d521a56e783288cecac7696cae3f0
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia QArith Qabs Lqa.
Require Import PartitionContext.
Require Import CyclicExecutive.
Require Import MemoryPlan.

Local Open Scope nat_scope.

(* -------------------------------------------------------------------------
   Helpers. The list and arithmetic helpers CyclicExecutive.v and
   MemoryPlan.v define (all_of, any_of, upto, all_of_upto,
   any_of_upto_intro) are consumed, not restated.
   ------------------------------------------------------------------------- *)

Definition qn (n : nat) : Q := inject_Z (Z.of_nat n).

Definition qltb (x y : Q) : bool := negb (Qle_bool y x).

Lemma qltb_lt : forall x y : Q, qltb x y = true -> (x < y)%Q.
Proof.
  intros x y H. unfold qltb in H. apply Qnot_le_lt. intros Hle.
  apply Qle_bool_iff in Hle. rewrite Hle in H. discriminate H.
Qed.

Lemma lt_qltb : forall x y : Q, (x < y)%Q -> qltb x y = true.
Proof.
  intros x y H. unfold qltb. destruct (Qle_bool y x) eqn:E; [ | reflexivity ].
  apply Qle_bool_iff in E. exfalso. exact (Qlt_not_le x y H E).
Qed.

Fixpoint sum_list (l : list nat) : nat :=
  match l with nil => 0 | cons x r => x + sum_list r end.

Fixpoint sum_nat (f : nat -> nat) (l : list nat) : nat :=
  match l with nil => 0 | cons x r => f x + sum_nat f r end.

Fixpoint max_over (f : nat -> nat) (l : list nat) : nat :=
  match l with nil => 0 | cons x r => Nat.max (f x) (max_over f r) end.

Fixpoint mem_nat (x : nat) (l : list nat) : bool :=
  match l with nil => false | cons y r => Nat.eqb x y || mem_nat x r end.

Lemma mem_nat_in : forall x l, mem_nat x l = true -> In x l.
Proof.
  intros x l. induction l as [ | y r IH ]; intros H.
  - discriminate H.
  - simpl in H. apply orb_true_iff in H. destruct H as [ H | H ].
    + left. apply Nat.eqb_eq in H. symmetry. exact H.
    + right. exact (IH H).
Qed.

Lemma all_of_in : forall (A : Type) (p : A -> bool) (l : list A) (x : A),
  all_of p l = true -> In x l -> p x = true.
Proof.
  intros A p l x. induction l as [ | y r IH ]; intros H Hin.
  - destruct Hin.
  - simpl in H. apply andb_prop in H. destruct H as [ Hy Hr ].
    destruct Hin as [ Heq | Hin ].
    + subst y. exact Hy.
    + exact (IH Hr Hin).
Qed.

Lemma any_of_in : forall (A : Type) (p : A -> bool) (l : list A),
  any_of p l = true -> exists x, In x l /\ p x = true.
Proof.
  intros A p l. induction l as [ | y r IH ]; intros H.
  - discriminate H.
  - simpl in H. apply orb_true_iff in H. destruct H as [ H | H ].
    + exists y. split; [ left; reflexivity | exact H ].
    + destruct (IH H) as [ x [ Hx Hp ] ]. exists x. split; [ right; exact Hx | exact Hp ].
Qed.

Lemma in_upto : forall n v : nat, v < n -> In v (upto n).
Proof.
  intros n. induction n as [ | k IH ]; intros v H.
  - lia.
  - simpl. apply in_or_app. destruct (Nat.eq_dec v k) as [ Heq | Hne ].
    + right. left. symmetry. exact Heq.
    + left. apply IH. lia.
Qed.

Lemma upto_in : forall n v : nat, In v (upto n) -> v < n.
Proof.
  intros n. induction n as [ | k IH ]; intros v H.
  - destruct H.
  - simpl in H. apply in_app_or in H. destruct H as [ H | [ H | [] ] ].
    + specialize (IH v H). lia.
    + lia.
Qed.

Lemma mod_through_a_multiple : forall a b g : nat,
  a mod b = 0 -> b mod g = 0 -> a mod g = 0.
Proof.
  intros a b g Ha Hb.
  apply Nat.Div0.mod_divides in Ha. apply Nat.Div0.mod_divides in Hb.
  destruct Ha as [ c1 Ha ]. destruct Hb as [ c2 Hb ]. subst a. subst b.
  apply Nat.Div0.mod_divides. exists (c2 * c1). lia.
Qed.

(* =========================================================================
   S1. The envelope (R-07-037e, R-07-037f, R-07-037i, R-08-047a).
   ========================================================================= *)

(* R-07-037f's named kinds. The three shapes that generate the list, two
   labels served, a deadline owed, a platform secret held, are manifest
   declarations below, so a component the list does not name is placed by
   the same test. *)
Inductive FixedKind : Type :=
| KernelPath | RootOfTrust | CryptoCore | SentinelOrWatchdog | LinkStack
| PowerboxOrTrustedPath | LockStatePath | AdmissionChecker
| IntegrityReaderOrTransactor | StorageServer | SupervisionTreeNode
| DeviceDriver.

(* What R-07-037f's acceptance says a manifest declares: the labels a
   component serves, the deadlines it owes, the secret classes it holds
   and the device authority it carries, beside the application whose
   manifest places it and the label it carries. *)
Record Manifest : Type := {
  mf_app : nat;
  mf_label : nat;
  mf_labels_served : nat;
  mf_owes_deadline : bool;
  mf_holds_secret : bool;
  mf_device_authority : bool;
  mf_kind : option FixedKind
}.

Definition fixed_tier_shape (m : Manifest) : bool :=
  Nat.leb 2 (mf_labels_served m) || mf_owes_deadline m || mf_holds_secret m.

Definition fixed_tier (m : Manifest) : bool :=
  fixed_tier_shape m || mf_device_authority m
  || match mf_kind m with Some _ => true | None => false end.

(* The composition-fixed envelope. The slots are the frame's and are read
   through Global below; the grants and endpoints are S9's edges. *)
Record Domain : Type := {
  dom_label : nat;
  dom_members : list nat;
  dom_manifest : nat -> Manifest;
  dom_cores : list nat;
  dom_dormant : nat -> nat -> bool;
  dom_extent : MemClass -> nat * nat
}.

Definition member_admitted (d : Domain) (m : nat) : bool :=
  Nat.eqb (mf_label (dom_manifest d m)) (dom_label d)
  && negb (fixed_tier (dom_manifest d m))
  && any_of (dom_dormant d m) (dom_cores d).

(* R-08-047a's second acceptance: each class's extent is its own constant,
   so the two classes neither borrow from nor overlap each other. *)
Definition extents_separate (d : Domain) : bool :=
  let (b1, s1) := dom_extent d FirstClass in
  let (b2, s2) := dom_extent d SecondClass in
  Nat.leb (b1 + s1) b2 || Nat.leb (b2 + s2) b1.

Definition envelope_admits (d : Domain) : bool :=
  all_of (member_admitted d) (dom_members d) && extents_separate d.

Definition EveryMemberCarriesTheLabel (d : Domain) : Prop :=
  forall m, In m (dom_members d) -> mf_label (dom_manifest d m) = dom_label d.

Definition NoMemberIsFixedTier (d : Domain) : Prop :=
  forall m, In m (dom_members d) -> fixed_tier (dom_manifest d m) = false.

(*| discharges: R-07-037e, R-07-037f |*)
Theorem an_admitted_envelope_has_one_label_and_no_fixed_tier_member :
  forall d : Domain, envelope_admits d = true ->
    EveryMemberCarriesTheLabel d /\ NoMemberIsFixedTier d.
Proof.
  intros d H. unfold envelope_admits in H. apply andb_prop in H.
  destruct H as [ Hm _ ].
  split; intros m Hin; pose proof (all_of_in _ _ _ _ Hm Hin) as Hok;
    unfold member_admitted in Hok; apply andb_prop in Hok;
    destruct Hok as [ Hok _ ]; apply andb_prop in Hok; destruct Hok as [ Hl Hf ].
  - apply Nat.eqb_eq. exact Hl.
  - apply negb_true_iff. exact Hf.
Qed.

(* R-07-037i: a launch activates a dormant context the composition placed
   for an enumerated member on one of the domain's cores, and never
   creates one. *)
Definition launch_ok (d : Domain) (m core : nat) : bool :=
  mem_nat m (dom_members d) && mem_nat core (dom_cores d) && dom_dormant d m core.

Definition ActivatesOnlyPlaced (d : Domain) (launch : nat -> nat -> bool) : Prop :=
  forall m core, launch m core = true ->
    In m (dom_members d) /\ In core (dom_cores d) /\ dom_dormant d m core = true.

(*| discharges: R-07-037i |*)
Theorem launch_activates_only_placed_contexts :
  forall d : Domain, ActivatesOnlyPlaced d (launch_ok d).
Proof.
  intros d m core H. unfold launch_ok in H.
  apply andb_prop in H. destruct H as [ H Hd ]. apply andb_prop in H.
  destruct H as [ Hm Hc ].
  split; [ exact (mem_nat_in _ _ Hm) | split; [ exact (mem_nat_in _ _ Hc) | exact Hd ] ].
Qed.

(* =========================================================================
   S3. The dispatch state and the declarations (R-07-037g, R-07-027a,
   R-07-037h, R-11-006c). Stated before S2 because S2's Global carries it.
   ========================================================================= *)

(* R-07-037g's fourth acceptance: per member its active bit, weight,
   request, eligible time and virtual deadline in its own placed context,
   the weight and request being the composition's declarations below, and
   its pending component (R-07-037c), which decides whether it competes. *)
Record PcFields : Type := {
  pc_active : bool;
  pc_pending : bool;
  pc_eligible : Q;
  pc_deadline : Q
}.

(* Per domain and core: the virtual time and the focus index, held in the
   session manager's context. *)
Record DState : Type := {
  ds_vtime : Q;
  ds_focus : option nat;
  ds_member : nat -> PcFields
}.

(* The composition's declarations for one domain on one core. Members are
   the indices below dc_count, whose order is the fixed tie order
   (reading 2). The call bound is R-07-037h's definition, the call
   interval plus one yield bound, and is derived rather than declared. *)
Record Decl : Type := {
  dc_count : nat;
  dc_weight : nat -> nat;
  dc_request : nat -> nat;
  dc_focus_weight : nat;
  dc_focus_request : nat;
  dc_call_interval : nat;
  dc_yield_bound : nat;
  dc_step : nat;                 (* the intra-slot step with its clear     *)
  dc_widths : list nat;          (* the domain's slot widths on this core  *)
  dc_app : nat -> nat;           (* each member's application manifest     *)
  dc_machine : Machine           (* PartitionContext.v's platform terms    *)
}.

Definition call_bound (d : Decl) : nat := dc_call_interval d + dc_yield_bound d.

(* R-07-037g: one call bound, one yield bound for the sink, and the step. *)
Definition boundary_need (d : Decl) : nat :=
  call_bound d + dc_yield_bound d + dc_step d.

Definition boundary_ok (d : Decl) (rem : nat) : bool := Nat.leb (boundary_need d) rem.

(* Admission's side of the rule: positive weights, R-11-006c's shortest
   domain slot fitting the boundary, and R-07-037g's clear charged in the
   per-visit step. *)
Definition decl_admits (d : Decl) : bool :=
  all_of (fun i => Nat.ltb 0 (dc_weight d i)) (upto (dc_count d))
  && Nat.ltb 0 (dc_focus_weight d)
  && all_of (fun w => Nat.leb (boundary_need d) w) (dc_widths d)
  && Nat.leb (vmclear_cost (dc_machine d)) (dc_step d).

Definition is_focus (s : DState) (i : nat) : bool :=
  match ds_focus s with Some f => Nat.eqb f i | None => false end.

(* The focused member takes the composition's focus weight and request. *)
Definition eff_weight (d : Decl) (s : DState) (i : nat) : nat :=
  if is_focus s i then dc_focus_weight d else dc_weight d i.

Definition eff_request (d : Decl) (s : DState) (i : nat) : nat :=
  if is_focus s i then dc_focus_request d else dc_request d i.

(* A member competes while it is live and its pending component shows
   work; one that yields with nothing pending leaves (reading 5). *)
Definition competing (d : Decl) (s : DState) (i : nat) : bool :=
  Nat.ltb i (dc_count d) && pc_active (ds_member s i) && pc_pending (ds_member s i).

Definition total_weight (d : Decl) (s : DState) : nat :=
  sum_nat (fun j => if competing d s j then eff_weight d s j else 0) (upto (dc_count d)).

Definition eligible (d : Decl) (s : DState) (i : nat) : bool :=
  competing d s i && Qle_bool (pc_eligible (ds_member s i)) (ds_vtime s).

Definition deadline_of (s : DState) (i : nat) : Q := pc_deadline (ds_member s i).

(* The EEVDF order: an earlier virtual deadline, or the same one and an
   earlier place in the fixed order. *)
Definition preferred (s : DState) (i j : nat) : bool :=
  qltb (deadline_of s i) (deadline_of s j)
  || (Qeq_bool (deadline_of s i) (deadline_of s j) && Nat.leb i j).

(* R-07-037g's selection, stated as a relation: the chosen member is
   eligible and preferred to every eligible member. *)
Definition Selects (d : Decl) (s : DState) (i : nat) : Prop :=
  eligible d s i = true /\ forall j, eligible d s j = true -> preferred s i j = true.

Lemma preferred_refl : forall s i, preferred s i i = true.
Proof.
  intros s i. unfold preferred. rewrite Qeq_bool_refl, Nat.leb_refl.
  apply orb_true_r.
Qed.

Lemma preferred_total : forall s i j, preferred s i j = false -> preferred s j i = true.
Proof.
  intros s i j H. unfold preferred in *.
  apply orb_false_iff in H. destruct H as [ Hlt Heq ].
  unfold qltb in Hlt. apply negb_false_iff in Hlt. apply Qle_bool_iff in Hlt.
  apply Qle_lteq in Hlt. destruct Hlt as [ Hlt | Hq ].
  - rewrite (lt_qltb _ _ Hlt). reflexivity.
  - assert (Hb : Qeq_bool (deadline_of s i) (deadline_of s j) = true).
    { apply Qeq_bool_iff. apply Qeq_sym. exact Hq. }
    rewrite Hb in Heq. simpl in Heq.
    apply orb_true_intro. right. apply andb_true_intro. split.
    + apply Qeq_bool_iff. exact Hq.
    + apply Nat.leb_le. apply Nat.leb_gt in Heq. lia.
Qed.

Lemma preferred_trans : forall s i j k,
  preferred s i j = true -> preferred s j k = true -> preferred s i k = true.
Proof.
  intros s i j k Hij Hjk. unfold preferred in *.
  apply orb_true_iff in Hij. apply orb_true_iff in Hjk.
  destruct Hij as [ Hij | Hij ]; destruct Hjk as [ Hjk | Hjk ].
  - apply orb_true_intro. left. apply lt_qltb.
    exact (Qlt_trans _ _ _ (qltb_lt _ _ Hij) (qltb_lt _ _ Hjk)).
  - apply andb_prop in Hjk. destruct Hjk as [ Hq _ ]. apply Qeq_bool_iff in Hq.
    apply orb_true_intro. left. apply lt_qltb.
    apply (Qlt_le_trans _ (deadline_of s j) _ (qltb_lt _ _ Hij)).
    apply Qle_lteq. right. exact Hq.
  - apply andb_prop in Hij. destruct Hij as [ Hq _ ]. apply Qeq_bool_iff in Hq.
    apply orb_true_intro. left. apply lt_qltb.
    apply (Qle_lt_trans _ (deadline_of s j) _).
    + apply Qle_lteq. right. exact Hq.
    + exact (qltb_lt _ _ Hjk).
  - apply andb_prop in Hij. destruct Hij as [ Hq1 Hl1 ].
    apply andb_prop in Hjk. destruct Hjk as [ Hq2 Hl2 ].
    apply Qeq_bool_iff in Hq1. apply Qeq_bool_iff in Hq2.
    apply orb_true_intro. right. apply andb_true_intro. split.
    + apply Qeq_bool_iff. exact (Qeq_trans _ _ _ Hq1 Hq2).
    + apply Nat.leb_le. apply Nat.leb_le in Hl1. apply Nat.leb_le in Hl2. lia.
Qed.

(* A reference selection over the enumeration, the one Q34b's kernel
   statement refines. *)
Fixpoint best (d : Decl) (s : DState) (l : list nat) (acc : option nat) : option nat :=
  match l with
  | nil => acc
  | cons j r =>
      if eligible d s j
      then match acc with
           | None => best d s r (Some j)
           | Some i => if preferred s i j then best d s r (Some i) else best d s r (Some j)
           end
      else best d s r acc
  end.

Definition select (d : Decl) (s : DState) : option nat := best d s (upto (dc_count d)) None.

Lemma eligible_competing : forall d s j, eligible d s j = true -> competing d s j = true.
Proof.
  intros d s j H. unfold eligible in H. apply andb_prop in H. destruct H as [ H _ ]. exact H.
Qed.

Lemma competing_lt : forall d s j, competing d s j = true -> j < dc_count d.
Proof.
  intros d s j H. unfold competing in H. apply andb_prop in H. destruct H as [ H _ ].
  apply andb_prop in H. destruct H as [ H _ ]. apply Nat.ltb_lt. exact H.
Qed.

Lemma best_spec : forall d s l acc i,
  best d s l acc = Some i ->
  (forall a, acc = Some a -> eligible d s a = true) ->
  eligible d s i = true
  /\ (forall a, acc = Some a -> preferred s i a = true)
  /\ (forall j, In j l -> eligible d s j = true -> preferred s i j = true).
Proof.
  intros d s l. induction l as [ | j r IH ]; intros acc i H Hacc.
  - simpl in H. subst acc. split; [ exact (Hacc i eq_refl) | split ].
    + intros a Ha. injection Ha as Ha. subst a. apply preferred_refl.
    + intros x [].
  - simpl in H. destruct (eligible d s j) eqn:Ej.
    + destruct acc as [ a | ].
      * destruct (preferred s a j) eqn:Paj.
        -- destruct (IH (Some a) i H Hacc) as [ Hi [ Ha Hr ] ].
           split; [ exact Hi | split; [ exact Ha | ] ].
           intros x Hx Ex. destruct Hx as [ Hx | Hx ].
           ++ subst x. exact (preferred_trans s i a j (Ha a eq_refl) Paj).
           ++ exact (Hr x Hx Ex).
        -- assert (Hj : forall b, Some j = Some b -> eligible d s b = true).
           { intros b Hb. injection Hb as Hb. subst b. exact Ej. }
           destruct (IH (Some j) i H Hj) as [ Hi [ Hjp Hr ] ].
           split; [ exact Hi | split ].
           ++ intros b Hb. injection Hb as Hb. subst b.
              exact (preferred_trans s i j a (Hjp j eq_refl) (preferred_total s a j Paj)).
           ++ intros x Hx Ex. destruct Hx as [ Hx | Hx ].
              ** subst x. exact (Hjp j eq_refl).
              ** exact (Hr x Hx Ex).
      * assert (Hj : forall b, Some j = Some b -> eligible d s b = true).
        { intros b Hb. injection Hb as Hb. subst b. exact Ej. }
        destruct (IH (Some j) i H Hj) as [ Hi [ Hjp Hr ] ].
        split; [ exact Hi | split ].
        -- intros b Hb. discriminate Hb.
        -- intros x Hx Ex. destruct Hx as [ Hx | Hx ].
           ++ subst x. exact (Hjp j eq_refl).
           ++ exact (Hr x Hx Ex).
    + destruct (IH acc i H Hacc) as [ Hi [ Ha Hr ] ].
      split; [ exact Hi | split; [ exact Ha | ] ].
      intros x Hx Ex. destruct Hx as [ Hx | Hx ].
      * subst x. rewrite Ej in Ex. discriminate Ex.
      * exact (Hr x Hx Ex).
Qed.

Lemma best_none : forall d s l acc,
  best d s l acc = None -> acc = None /\ forall j, In j l -> eligible d s j = false.
Proof.
  intros d s l. induction l as [ | j r IH ]; intros acc H.
  - simpl in H. split; [ exact H | intros x [] ].
  - simpl in H. destruct (eligible d s j) eqn:Ej.
    + destruct acc as [ a | ].
      * destruct (preferred s a j); destruct (IH _ H) as [ Hc _ ]; discriminate Hc.
      * destruct (IH _ H) as [ Hc _ ]. discriminate Hc.
    + destruct (IH acc H) as [ Ha Hr ]. split; [ exact Ha | ].
      intros x Hx. destruct Hx as [ Hx | Hx ]; [ subst x; exact Ej | exact (Hr x Hx) ].
Qed.

(*| discharges: R-07-037g |*)
Theorem select_is_the_eevdf_choice :
  forall d s i, select d s = Some i -> Selects d s i.
Proof.
  intros d s i H. unfold select in H.
  assert (Hn : forall a, (None : option nat) = Some a -> eligible d s a = true).
  { intros a Ha. discriminate Ha. }
  destruct (best_spec d s _ None i H Hn) as [ Hi [ _ Hr ] ].
  split; [ exact Hi | ].
  intros j Ej. apply Hr; [ | exact Ej ].
  apply in_upto. exact (competing_lt d s j (eligible_competing d s j Ej)).
Qed.

(*| discharges: R-07-037g |*)
Theorem select_idles_only_when_nothing_is_eligible :
  forall d s, select d s = None -> forall j, eligible d s j = false.
Proof.
  intros d s H j. destruct (eligible d s j) eqn:Ej; [ | reflexivity ].
  destruct (best_none d s _ None H) as [ _ Hr ].
  pose proof (Hr j (in_upto _ _ (competing_lt d s j (eligible_competing d s j Ej)))) as Hf.
  rewrite Ej in Hf. discriminate Hf.
Qed.

Theorem a_selection_exists_whenever_a_member_is_eligible :
  forall d s j, eligible d s j = true -> exists i, Selects d s i.
Proof.
  intros d s j Ej. destruct (select d s) as [ i | ] eqn:E.
  - exists i. apply select_is_the_eevdf_choice. exact E.
  - pose proof (select_idles_only_when_nothing_is_eligible d s E j) as Hf.
    rewrite Ej in Hf. discriminate Hf.
Qed.

(* =========================================================================
   S2. Confinement of the runtime choices (R-07-037e, R-07-037g,
   R-07-032, R-07-036).
   ========================================================================= *)

(* A core's state split at the domain's edge: the composed frame, with the
   domain one tenant of it (CyclicExecutive.v), the domain's own label
   state, and every other label's state. *)
Record Global : Type := {
  g_frame : Frame nat;
  g_domain : DState;
  g_others : nat -> nat
}.

Definition ReadsOnlyItsLabel {X : Type} (choice : Global -> X) : Prop :=
  forall g1 g2 : Global, g_domain g1 = g_domain g2 -> choice g1 = choice g2.

Definition spec_choice (d : Decl) (g : Global) : option nat := select d (g_domain g).

(*| discharges: R-07-037g |*)
Theorem the_dispatch_reads_only_its_label :
  forall d : Decl, ReadsOnlyItsLabel (spec_choice d).
Proof. intros d g1 g2 H. unfold spec_choice. rewrite H. reflexivity. Qed.

(* The construction R-07-037g's first acceptance excludes: a dispatch that
   defers to another label's activity. *)
Definition leaky_choice (d : Decl) (g : Global) : option nat :=
  if Nat.eqb (g_others g 0) 0 then select d (g_domain g) else None.

Definition DomainStep : Type := Global -> Global -> Prop.

Definition MovesNothingOutside (step : DomainStep) : Prop :=
  forall g g', step g g' -> g_frame g' = g_frame g /\ g_others g' = g_others g.

(* Any transition of the domain's own state, lifted: definitional on this
   side, its content being the refutation below. *)
Definition within_the_envelope (t : DState -> DState -> Prop) : DomainStep :=
  fun g g' => t (g_domain g) (g_domain g') /\ g_frame g' = g_frame g
              /\ g_others g' = g_others g.

Theorem every_domain_transition_stays_inside :
  forall t, MovesNothingOutside (within_the_envelope t).
Proof. intros t g g' [ _ [ Hf Ho ] ]. split; assumption. Qed.

(* A frame with the domain (tenant 7) and one other tenant (3), and the
   runtime width choice R-07-032's second acceptance names as a finding. *)
Definition env_domain_slot (w : nat) : Slot nat := Build_Slot nat w 0 0 100 7.
Definition env_other_slot : Slot nat := Build_Slot nat 40 40 0 100 3.

Definition env_frame (w : nat) : Frame nat :=
  Build_Frame nat 100 0 nil (Build_Band nat (env_domain_slot w) (cons env_other_slot nil)).

Definition widening_step : DomainStep := fun g g' =>
  g_frame g' = env_frame 50 /\ g_domain g' = g_domain g /\ g_others g' = g_others g.

Definition quiet_member : PcFields :=
  {| pc_active := false; pc_pending := false; pc_eligible := 0%Q; pc_deadline := 0%Q |}.

Definition quiet_state : DState :=
  {| ds_vtime := 0%Q; ds_focus := None; ds_member := fun _ => quiet_member |}.

Definition env_before : Global :=
  {| g_frame := env_frame 40; g_domain := quiet_state; g_others := fun _ => 0 |}.

Definition env_after : Global :=
  {| g_frame := env_frame 50; g_domain := quiet_state; g_others := fun _ => 0 |}.

Theorem a_runtime_width_choice_moves_another_tenant_s_instant :
  slot_index_at (frame_slots (env_frame 40)) 0 45 = Some 1
  /\ slot_index_at (frame_slots (env_frame 50)) 0 45 = Some 0
  /\ widening_step env_before env_after
  /\ ~ MovesNothingOutside widening_step.
Proof.
  assert (Hstep : widening_step env_before env_after).
  { split; [ reflexivity | split; reflexivity ]. }
  split; [ reflexivity | split; [ reflexivity | split; [ exact Hstep | ] ] ].
  intros H. destruct (H env_before env_after Hstep) as [ Hf _ ].
  assert (Hi : slot_index_at (frame_slots (g_frame env_after)) 0 45
               = slot_index_at (frame_slots (g_frame env_before)) 0 45).
  { rewrite Hf. reflexivity. }
  simpl in Hi. discriminate Hi.
Qed.

(* =========================================================================
   S3, continued. The tentative-yield reply, the boundary rule, the
   charge, and one dispatch (R-07-037g, R-07-031b, R-07-037h).
   ========================================================================= *)

Inductive Reply : Type := Continue | SwitchRequested.

(* Virtual time advanced by u units of service over the competing set. *)
Definition advance (d : Decl) (s : DState) (u : nat) : DState :=
  {| ds_vtime := Qplus (ds_vtime s) (Qdiv (qn u) (qn (total_weight d s)));
     ds_focus := ds_focus s; ds_member := ds_member s |}.

Definition earlier_eligible (d : Decl) (s : DState) (i : nat) : bool :=
  any_of (fun j => negb (Nat.eqb j i) && eligible d s j
                   && qltb (deadline_of s j) (deadline_of s i))
         (upto (dc_count d)).

(* Invocation (iii) with its tentative flag: continue while the running
   member's request lasts, no eligible member has an earlier virtual
   deadline, and the boundary test passes; switch-requested otherwise.
   The boundary test is a parameter so the constructions that weaken it can
   be stated beside the rule (reading 3). *)
Definition reply_with (bok : nat -> bool) (d : Decl) (s : DState) (i used rem : nat) : Reply :=
  if Nat.ltb used (eff_request d s i)
     && negb (earlier_eligible d (advance d s used) i) && bok rem
  then Continue else SwitchRequested.

Definition reply (d : Decl) (s : DState) (i used rem : nat) : Reply :=
  reply_with (boundary_ok d) d s i used rem.

Definition set_member (s : DState) (i : nat) (f : PcFields) : DState :=
  {| ds_vtime := ds_vtime s; ds_focus := ds_focus s;
     ds_member := fun j => if Nat.eqb j i then f else ds_member s j |}.

(* The published per-request rule at a real yield: virtual time advances
   by the service over the competing weight, the member's eligible time by
   its service over its weight, and its next deadline is one request past
   that. A yield with nothing pending leaves the competing set. *)
Definition charge (d : Decl) (s : DState) (i u : nat) (pending : bool) : DState :=
  let w := qn (eff_weight d s i) in
  let ve := Qplus (pc_eligible (ds_member s i)) (Qdiv (qn u) w) in
  set_member (advance d s u) i
    {| pc_active := pc_active (ds_member s i); pc_pending := pending;
       pc_eligible := ve; pc_deadline := Qplus ve (Qdiv (qn (eff_request d s i)) w) |}.

(* One dispatch (reading 4). *)
Record Run : Type := {
  run_member : nat;
  run_gaps : list nat;
  run_sink : option nat;
  run_pending : bool
}.

Definition sink_len (r : Run) : nat := match run_sink r with None => 0 | Some k => k end.

Definition run_service (r : Run) : nat := sum_list (run_gaps r) + sink_len r.

(* The member side is what R-07-037h's checker admits: no gap between
   invocations longer than the call bound, and a sink no longer than
   sink_bound, the yield bound for a checked member. *)
Fixpoint calls_with (bok : nat -> bool) (sink_bound : nat) (d : Decl) (s : DState)
    (i rem used : nat) (gaps : list nat) (sink : option nat) : Prop :=
  match gaps with
  | nil => False
  | cons g rest =>
      g <= call_bound d /\
      match rest with
      | nil =>
          match sink with
          | None => True
          | Some k => reply_with bok d s i (used + g) (rem - (used + g)) = SwitchRequested
                      /\ k <= sink_bound
          end
      | cons _ _ =>
          reply_with bok d s i (used + g) (rem - (used + g)) = Continue
          /\ calls_with bok sink_bound d s i rem (used + g) rest sink
      end
  end.

Definition RunConformsWith (bok : nat -> bool) (sink_bound : nat) (d : Decl)
    (s : DState) (rem : nat) (r : Run) : Prop :=
  Selects d s (run_member r) /\ bok rem = true
  /\ calls_with bok sink_bound d s (run_member r) rem 0 (run_gaps r) (run_sink r).

Definition RunConforms (d : Decl) (s : DState) (rem : nat) (r : Run) : Prop :=
  RunConformsWith (boundary_ok d) (dc_yield_bound d) d s rem r.

(* The boundary rule's purpose, as a property of a kernel test and a sink
   bound: every conforming dispatch ends, sink and step included, before
   the slot boundary, so the timer never cuts a member. *)
Definition NeverCuts (bok : nat -> bool) (sink_bound : nat) (d : Decl) : Prop :=
  forall s rem r, RunConformsWith bok sink_bound d s rem r -> run_service r + dc_step d <= rem.

Lemma calls_fit : forall d s i rem gaps used sink,
  used + boundary_need d <= rem ->
  calls_with (boundary_ok d) (dc_yield_bound d) d s i rem used gaps sink ->
  used + sum_list gaps + (match sink with None => 0 | Some k => k end) + dc_step d <= rem.
Proof.
  intros d s i rem gaps. induction gaps as [ | g rest IH ]; intros used sink Hroom H.
  - destruct H.
  - destruct H as [ Hg Hrest ].
    destruct rest as [ | g2 rest2 ].
    + unfold boundary_need, call_bound in *. simpl.
      destruct sink as [ k | ].
      * destruct Hrest as [ _ Hk ]. lia.
      * lia.
    + destruct Hrest as [ Hc Hcall ].
      assert (Hb : boundary_ok d (rem - (used + g)) = true).
      { unfold reply_with in Hc.
        destruct (Nat.ltb (used + g) (eff_request d s i)
                  && negb (earlier_eligible d (advance d s (used + g)) i)
                  && boundary_ok d (rem - (used + g))) eqn:E; [ | discriminate Hc ].
        apply andb_prop in E. destruct E as [ _ E ]. exact E. }
      unfold boundary_ok in Hb. apply Nat.leb_le in Hb.
      assert (Hroom2 : used + g + boundary_need d <= rem).
      { unfold boundary_need, call_bound in *. lia. }
      specialize (IH (used + g) sink Hroom2 Hcall).
      simpl sum_list. simpl sum_list in IH. lia.
Qed.

(*| discharges: R-07-037g |*)
Theorem the_boundary_rule_leaves_no_member_cut :
  forall d : Decl, NeverCuts (boundary_ok d) (dc_yield_bound d) d.
Proof.
  intros d s rem r [ _ [ Hb Hc ] ]. unfold boundary_ok in Hb. apply Nat.leb_le in Hb.
  assert (H0 : 0 + boundary_need d <= rem) by lia.
  pose proof (calls_fit d s (run_member r) rem (run_gaps r) 0 (run_sink r) H0 Hc) as H.
  unfold run_service, sink_len. lia.
Qed.

(* A member that invokes (iii) tentatively after an unanswered
   switch-requested is enacted as a real yield, so even an unchecked member
   stops within one call bound of the reply. That is the backstop, and
   stated with the backstop's bound in place of the yield bound it does not
   keep the boundary (backstop_alone_cuts below). *)
Theorem the_backstop_bounds_an_unchecked_sink :
  forall d s rem r, RunConformsWith (boundary_ok d) (call_bound d) d s rem r ->
    run_service r <= rem + dc_call_interval d.
Proof.
  intros d s rem r [ _ [ Hb Hc ] ]. unfold boundary_ok in Hb. apply Nat.leb_le in Hb.
  assert (Hgen : forall gaps used sink,
    used + boundary_need d <= rem ->
    calls_with (boundary_ok d) (call_bound d) d s (run_member r) rem used gaps sink ->
    used + sum_list gaps + (match sink with None => 0 | Some k => k end)
      <= rem + dc_call_interval d).
  { intros gaps. induction gaps as [ | g rest IH ]; intros used sink Hroom H.
    - destruct H.
    - destruct H as [ Hg Hrest ]. destruct rest as [ | g2 rest2 ].
      + unfold boundary_need, call_bound in *. simpl.
        destruct sink as [ k | ]; [ destruct Hrest as [ _ Hk ]; lia | lia ].
      + destruct Hrest as [ Hcn Hcall ].
        assert (Hb2 : boundary_ok d (rem - (used + g)) = true).
        { unfold reply_with in Hcn.
          destruct (Nat.ltb (used + g) (eff_request d s (run_member r))
                    && negb (earlier_eligible d (advance d s (used + g)) (run_member r))
                    && boundary_ok d (rem - (used + g))) eqn:E; [ | discriminate Hcn ].
          apply andb_prop in E. destruct E as [ _ E ]. exact E. }
        unfold boundary_ok in Hb2. apply Nat.leb_le in Hb2.
        assert (Hroom2 : used + g + boundary_need d <= rem).
        { unfold boundary_need, call_bound in *. lia. }
        specialize (IH (used + g) sink Hroom2 Hcall).
        simpl sum_list. simpl sum_list in IH. lia. }
  assert (H0 : 0 + boundary_need d <= rem) by lia.
  pose proof (Hgen (run_gaps r) 0 (run_sink r) H0 Hc) as H.
  unfold run_service, sink_len. lia.
Qed.

(* =========================================================================
   S4. The intra-slot step (R-07-037g, R-07-037b, R-07-037c, R-07-037d,
   R-07-014a, R-07-014c).
   ========================================================================= *)

Definition elastic_performs (same_app : bool) (a : Action) : bool :=
  match a with
  | Restore => true
  | FenceT => false
  | Vmclear => negb same_app
  | OppRelock => false
  end.

(* PartitionContext.v's rotation, plus the clear of the zeroize class
   whenever the two members belong to different applications (reading 7). *)
Definition ElasticStep (m : Machine) (same_app : bool) : Step m := fun succ pre post =>
  Rotation m succ pre post
  /\ (if same_app then True
      else forall c, csr_nameable m c = true -> csr_zeroized m c = true ->
                     ctx_csr post c = zero_word m).

(*| discharges: R-07-037g |*)
Theorem a_cross_application_step_clears_the_zeroize_class :
  forall m : Machine, RestoresNameableCsrs m (ElasticStep m false).
Proof.
  intros m succ pre post [ [ _ [ Hr _ ] ] Hz ] c Hn.
  destruct (csr_zeroized m c) eqn:E.
  - exact (Hz c Hn E).
  - exact (Hr c Hn E).
Qed.

(*| discharges: R-07-037g |*)
Theorem a_cross_application_step_leaves_no_residue :
  forall m : Machine, rotation_swaps_pending m = true -> NoResidue m (ElasticStep m false).
Proof.
  intros m Hswap succ pre1 post1 pre2 post2 H1 H2.
  pose proof (a_cross_application_step_clears_the_zeroize_class m succ pre1 post1 H1) as C1.
  pose proof (a_cross_application_step_clears_the_zeroize_class m succ pre2 post2 H2) as C2.
  destruct H1 as [ [ Hr1 [ _ Hp1 ] ] _ ]. destruct H2 as [ [ Hr2 [ _ Hp2 ] ] _ ].
  rewrite Hswap in Hp1, Hp2.
  split; [ | split ].
  - intros r Hr. rewrite (Hr1 r Hr), (Hr2 r Hr). reflexivity.
  - intros c Hc. rewrite (C1 c Hc), (C2 c Hc). reflexivity.
  - rewrite Hp1, Hp2. reflexivity.
Qed.

Theorem a_same_application_step_is_the_rotation :
  forall (m : Machine) succ pre post,
    ElasticStep m true succ pre post <-> Rotation m succ pre post.
Proof.
  intros m succ pre post. split.
  - intros [ H _ ]. exact H.
  - intros H. split; [ exact H | exact I ].
Qed.

(*| discharges: R-07-037g |*)
Theorem the_clear_costs_one_vmclear_and_nothing_else :
  forall m : Machine,
    constants_paid m (elastic_performs false) = vmclear_cost m
    /\ constants_paid m (elastic_performs true) = 0.
Proof. intros m. unfold constants_paid. simpl. split; lia. Qed.

(* A kernel that saves the zeroize class across the switch and restores it
   for the incoming member, which R-07-037g's third acceptance excludes. *)
Definition saving_step (m : Machine) : Step m := fun succ pre post =>
  Rotation m succ pre post
  /\ forall c, csr_nameable m c = true -> csr_zeroized m c = true ->
               ctx_csr post c = ctx_csr succ c.

Theorem a_rotation_across_applications_leaves_vector_state_standing :
  Rotation demo_rotation_swaps demo_succ demo_succ unzeroed_post
  /\ ~ ElasticStep demo_rotation_swaps false demo_succ demo_succ unzeroed_post.
Proof.
  split.
  - apply (proj1 rotation_omits_the_zeroize_at_state_level).
  - intros [ _ Hz ]. specialize (Hz true eq_refl eq_refl). cbv in Hz. discriminate Hz.
Qed.

Theorem a_kernel_saving_vector_state_is_refuted :
  saving_step demo_rotation_swaps demo_succ demo_succ unzeroed_post
  /\ ~ ElasticStep demo_rotation_swaps false demo_succ demo_succ unzeroed_post
  /\ ~ RestoresNameableCsrs demo_rotation_swaps (saving_step demo_rotation_swaps).
Proof.
  assert (Hs : saving_step demo_rotation_swaps demo_succ demo_succ unzeroed_post).
  { split.
    - apply (proj1 rotation_omits_the_zeroize_at_state_level).
    - intros c _ _. reflexivity. }
  split; [ exact Hs | split ].
  - exact (proj2 a_rotation_across_applications_leaves_vector_state_standing).
  - intros H. specialize (H demo_succ demo_succ unzeroed_post Hs true eq_refl).
    cbv in H. discriminate H.
Qed.

(* =========================================================================
   S5. The share bound (R-07-037g, R-11-006c).
   ========================================================================= *)

(* A stretch of the domain's time on its core: the member served, or none
   for an idle stretch, its length, and each member's weight share of the
   competing set during it. *)
Record Stint : Type := {
  st_served : option nat;
  st_len : nat;
  st_share : nat -> Q
}.

Definition share_of (d : Decl) (s : DState) (i : nat) : Q :=
  if competing d s i then Qdiv (qn (eff_weight d s i)) (qn (total_weight d s)) else 0%Q.

Definition stint_of_run (d : Decl) (s : DState) (r : Run) : Stint :=
  {| st_served := Some (run_member r); st_len := run_service r; st_share := share_of d s |}.

Definition idle_stint (d : Decl) (s : DState) (rem : nat) : Stint :=
  {| st_served := None; st_len := rem; st_share := share_of d s |}.

(* Reading 6: whether an idle stretch is part of "the domain's time on its
   core". *)
Inductive TimeBase : Type := ServedTime | SlotTime.

Definition accrues (tb : TimeBase) (st : Stint) : bool :=
  match st_served st, tb with
  | Some _, _ => true
  | None, SlotTime => true
  | None, ServedTime => false
  end.

Definition stint_lag (tb : TimeBase) (i : nat) (st : Stint) : Q :=
  Qminus (if accrues tb st then Qmult (st_share st i) (qn (st_len st)) else 0%Q)
         (match st_served st with
          | Some j => if Nat.eqb j i then qn (st_len st) else 0%Q
          | None => 0%Q
          end).

(* Service lag (reading 5): entitlement accrued while competing, less
   service received. *)
Fixpoint lag (tb : TimeBase) (i : nat) (l : list Stint) : Q :=
  match l with nil => 0%Q | cons st r => Qplus (stint_lag tb i st) (lag tb i r) end.

(* A join, a launch, a close, a reweight or a focus change, enacted at a
   dispatch point: the new live and pending bits and the focus the session
   manager's request cell names, every member placed at the eligible time
   its preserved lag fixes (reading 5). *)
Definition relaunch (live pend : nat -> bool) (f : option nat) (s : DState) : DState :=
  {| ds_vtime := ds_vtime s; ds_focus := f;
     ds_member := fun j => {| pc_active := live j; pc_pending := pend j;
                              pc_eligible := pc_eligible (ds_member s j);
                              pc_deadline := pc_deadline (ds_member s j) |} |}.

Definition rebalance (d : Decl) (s : DState) (past : list Stint)
    (live pend : nat -> bool) (f : option nat) : DState :=
  let s1 := relaunch live pend f s in
  {| ds_vtime := ds_vtime s1; ds_focus := f;
     ds_member := fun j =>
       let w := qn (eff_weight d s1 j) in
       let ve := Qminus (ds_vtime s1) (Qdiv (lag ServedTime j past) w) in
       {| pc_active := live j; pc_pending := pend j; pc_eligible := ve;
          pc_deadline := Qplus ve (Qdiv (qn (eff_request d s1 j)) w) |} |}.

(* A dispatch point may add work and name a focus inside the enumeration;
   it may not take pending work from a member it keeps live, and only a
   live member can be pending. *)
Definition rebalance_ok (d : Decl) (s : DState) (live pend : nat -> bool) (f : option nat) : bool :=
  all_of (fun j => implb (pc_pending (ds_member s j) && live j) (pend j)
                   && implb (pend j) (live j)) (upto (dc_count d))
  && match f with Some j => Nat.ltb j (dc_count d) | None => true end.

Inductive DStep : Type :=
| DSlot (w : nat)
| DRebalance (live pend : nat -> bool) (f : option nat)
| DRun (r : Run)
| DIdle.

Record Config : Type := {
  cf_state : DState;
  cf_rem : nat;
  cf_past : list Stint
}.

Definition exec (d : Decl) (c : Config) (st : DStep) : Config :=
  match st with
  | DSlot w => {| cf_state := cf_state c; cf_rem := w; cf_past := cf_past c |}
  | DRebalance live pend f =>
      {| cf_state := rebalance d (cf_state c) (cf_past c) live pend f;
         cf_rem := cf_rem c; cf_past := cf_past c |}
  | DRun r =>
      {| cf_state := charge d (cf_state c) (run_member r) (run_service r) (run_pending r);
         cf_rem := cf_rem c - (run_service r + dc_step d);
         cf_past := cf_past c ++ cons (stint_of_run d (cf_state c) r) nil |}
  | DIdle =>
      {| cf_state := cf_state c; cf_rem := 0;
         cf_past := cf_past c ++ cons (idle_stint d (cf_state c) (cf_rem c)) nil |}
  end.

(* The core idles to the boundary only when nothing is eligible or the
   boundary rule forbids a dispatch. *)
Definition idle_permitted (d : Decl) (s : DState) (rem : nat) : bool :=
  match select d s with None => true | Some _ => negb (boundary_ok d rem) end.

Definition step_ok (d : Decl) (c : Config) (st : DStep) : Prop :=
  match st with
  | DSlot w => cf_rem c = 0 /\ mem_nat w (dc_widths d) = true
  | DRebalance live pend f => rebalance_ok d (cf_state c) live pend f = true
  | DRun r => RunConforms d (cf_state c) (cf_rem c) r
  | DIdle => idle_permitted d (cf_state c) (cf_rem c) = true
  end.

Fixpoint Conforming (d : Decl) (c : Config) (steps : list DStep) : Prop :=
  match steps with
  | nil => True
  | cons st rest => step_ok d c st /\ Conforming d (exec d c st) rest
  end.

Fixpoint exec_all (d : Decl) (c : Config) (steps : list DStep) : Config :=
  match steps with nil => c | cons st rest => exec_all d (exec d c st) rest end.

Definition start (s : DState) : Config := {| cf_state := s; cf_rem := 0; cf_past := nil |}.

(* A declared start: virtual time zero and every competing member at zero
   lag with its first request's deadline. *)
Definition fresh (d : Decl) (s : DState) : bool :=
  Qeq_bool (ds_vtime s) 0
  && all_of (fun i => implb (competing d s i)
                        (Qeq_bool (pc_eligible (ds_member s i)) 0
                         && Qeq_bool (pc_deadline (ds_member s i))
                              (Qdiv (qn (eff_request d s i)) (qn (eff_weight d s i)))))
            (upto (dc_count d)).

(* Every stint boundary of every conforming trace; between two boundaries
   a lag is linear in time, so the endpoints bound every instant. *)
Definition LagBounded (tb : TimeBase) (d : Decl) (B : Q) : Prop :=
  forall (s0 : DState) (steps : list DStep),
    fresh d s0 = true -> Conforming d (start s0) steps ->
    forall i, Nat.ltb i (dc_count d) = true ->
      (Qabs (lag tb i (cf_past (exec_all d (start s0) steps))) <= B)%Q.

(* The interval half: a member's shortfall against its weight's share
   over the stretch mid covers. *)
Definition ShortfallBounded (tb : TimeBase) (d : Decl) (B : Q) : Prop :=
  forall (s0 : DState) (pre mid : list DStep),
    fresh d s0 = true -> Conforming d (start s0) (pre ++ mid) ->
    forall i, Nat.ltb i (dc_count d) = true ->
      (lag tb i (cf_past (exec_all d (start s0) (pre ++ mid)))
       - lag tb i (cf_past (exec_all d (start s0) pre)) <= 2 * B)%Q.

Definition max_request (d : Decl) : nat :=
  Nat.max (dc_focus_request d) (max_over (dc_request d) (upto (dc_count d))).

(* R-07-037g's second acceptance, word for word: the largest declared
   request plus one call bound, and twice that over any interval. *)
Definition register_lag_bound (d : Decl) : Q := qn (max_request d + call_bound d).

Definition ShareBound (tb : TimeBase) (d : Decl) : Prop :=
  LagBounded tb d (register_lag_bound d) /\ ShortfallBounded tb d (register_lag_bound d).

(* The figure F1 points at, named and not adopted. *)
Definition sink_inclusive_lag_bound (d : Decl) : Q :=
  qn (max_request d + call_bound d + dc_yield_bound d).

Lemma conforming_app : forall d c pre mid,
  Conforming d c (pre ++ mid) -> Conforming d c pre.
Proof.
  intros d c pre. revert c. induction pre as [ | st rest IH ]; intros c mid H.
  - exact I.
  - simpl in H. destruct H as [ Hs Hr ]. split; [ exact Hs | exact (IH _ mid Hr) ].
Qed.

Theorem an_instant_bound_bounds_every_interval :
  forall tb d B, LagBounded tb d B -> ShortfallBounded tb d B.
Proof.
  intros tb d B H s0 pre mid Hf Hc i Hi.
  pose proof (H s0 (pre ++ mid) Hf Hc i Hi) as Hend.
  pose proof (H s0 pre Hf (conforming_app d (start s0) pre mid Hc) i Hi) as Hstart.
  apply Qabs_Qle_condition in Hend. apply Qabs_Qle_condition in Hstart.
  destruct Hend, Hstart. lra.
Qed.

(* So Q34b owes the instant half alone. *)
Theorem the_share_bound_is_its_instant_half :
  forall tb d, LagBounded tb d (register_lag_bound d) -> ShareBound tb d.
Proof.
  intros tb d H. split; [ exact H | exact (an_instant_bound_bounds_every_interval tb d _ H) ].
Qed.

(* -------------------------------------------------------------------------
   F1's construction. Member 0 is light (weight 1) and member 1 heavy
   (weight 9), both with a request of 1; call interval 1 and yield bound
   2, so a call bound of 3. Member 1's earlier deadline wins the first
   dispatch; it uses its request and yields with work still pending, which
   leaves it ahead of virtual time and ineligible. Member 0 is then the
   only eligible member: it runs one call bound to its first invocation,
   is answered switch-requested because its request is spent, and sinks
   for one yield bound. Every step is the rule's; both lags end at 22/5.
   ------------------------------------------------------------------------- *)

Definition fields (a p : bool) (ve vd : Q) : PcFields :=
  {| pc_active := a; pc_pending := p; pc_eligible := ve; pc_deadline := vd |}.

Definition cx_decl : Decl := {|
  dc_count := 2;
  dc_weight := fun i => if Nat.eqb i 0 then 1 else 9;
  dc_request := fun _ => 1;
  dc_focus_weight := 1;
  dc_focus_request := 1;
  dc_call_interval := 1;
  dc_yield_bound := 2;
  dc_step := 5;
  dc_widths := cons 100 nil;
  dc_app := fun i => i;
  dc_machine := demo_rotation_swaps
|}.

Definition cx_start : DState := {|
  ds_vtime := 0%Q;
  ds_focus := None;
  ds_member := fun i => if Nat.eqb i 0 then fields true true 0 1 else fields true true 0 (1 # 9)
|}.

Definition cx_heavy : Run :=
  {| run_member := 1; run_gaps := cons 1 nil; run_sink := Some 0; run_pending := true |}.

Definition cx_light : Run :=
  {| run_member := 0; run_gaps := cons 3 nil; run_sink := Some 2; run_pending := true |}.

Definition cx_steps : list DStep := cons (DSlot 100) (cons (DRun cx_heavy) (cons (DRun cx_light) nil)).

Example cx_is_admitted : decl_admits cx_decl = true := eq_refl.
Example cx_starts_fresh : fresh cx_decl cx_start = true := eq_refl.

Theorem cx_trace_conforms : Conforming cx_decl (start cx_start) cx_steps.
Proof.
  split; [ split; reflexivity | ].
  split.
  - split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. split; [ unfold call_bound; simpl; lia | split; [ reflexivity | lia ] ].
  - split; [ | exact I ].
    split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. split; [ unfold call_bound; simpl; lia | split; [ reflexivity | lia ] ].
Qed.

Example cx_lags :
  Qeq_bool (lag ServedTime 0 (cf_past (exec_all cx_decl (start cx_start) cx_steps))) (-22 # 5) = true
  /\ Qeq_bool (lag ServedTime 1 (cf_past (exec_all cx_decl (start cx_start) cx_steps))) (22 # 5) = true
  /\ Qeq_bool (register_lag_bound cx_decl) 4 = true
  /\ Qle_bool (Qabs (lag ServedTime 0 (cf_past (exec_all cx_decl (start cx_start) cx_steps))))
       (sink_inclusive_lag_bound cx_decl) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_register_s_lag_bound_is_refuted :
  ~ LagBounded ServedTime cx_decl (register_lag_bound cx_decl).
Proof.
  intros H.
  pose proof (H cx_start cx_steps eq_refl cx_trace_conforms 0 eq_refl) as Hb.
  apply Qle_bool_iff in Hb.
  assert (E : Qle_bool (Qabs (lag ServedTime 0 (cf_past (exec_all cx_decl (start cx_start) cx_steps))))
                       (register_lag_bound cx_decl) = false) by reflexivity.
  rewrite E in Hb. discriminate Hb.
Qed.

(* The trace has no idle stretch, so the slot-time reading gives the same
   lags and refutes the bound too. *)
Theorem the_register_s_lag_bound_is_refuted_over_slot_time :
  ~ LagBounded SlotTime cx_decl (register_lag_bound cx_decl).
Proof.
  intros H.
  pose proof (H cx_start cx_steps eq_refl cx_trace_conforms 0 eq_refl) as Hb.
  apply Qle_bool_iff in Hb.
  assert (E : Qle_bool (Qabs (lag SlotTime 0 (cf_past (exec_all cx_decl (start cx_start) cx_steps))))
                       (register_lag_bound cx_decl) = false) by reflexivity.
  rewrite E in Hb. discriminate Hb.
Qed.

(* So the share bound as the register states it is not a theorem Q34b can
   prove, at either time base. *)
Theorem the_register_s_share_bound_is_refuted :
  ~ ShareBound ServedTime cx_decl /\ ~ ShareBound SlotTime cx_decl.
Proof.
  split; intros [ H _ ].
  - exact (the_register_s_lag_bound_is_refuted H).
  - exact (the_register_s_lag_bound_is_refuted_over_slot_time H).
Qed.

(* -------------------------------------------------------------------------
   F2's construction. One member alone, request 1, a call bound of 3, a
   step of 5 and a slot of 12: each slot runs one dispatch of 3 and then
   the boundary rule idles the remaining 4. Over slot time the member's
   shortfall grows by 4 a slot; over served time it is zero.
   ------------------------------------------------------------------------- *)

Definition tail_decl : Decl := {|
  dc_count := 1;
  dc_weight := fun _ => 1;
  dc_request := fun _ => 1;
  dc_focus_weight := 1;
  dc_focus_request := 1;
  dc_call_interval := 1;
  dc_yield_bound := 2;
  dc_step := 5;
  dc_widths := cons 12 nil;
  dc_app := fun i => i;
  dc_machine := demo_rotation_swaps
|}.

Definition solo_start : DState :=
  {| ds_vtime := 0%Q; ds_focus := None; ds_member := fun _ => fields true true 0 1 |}.

Definition tail_run : Run :=
  {| run_member := 0; run_gaps := cons 3 nil; run_sink := Some 0; run_pending := true |}.

Definition tail_steps : list DStep :=
  cons (DSlot 12) (cons (DRun tail_run) (cons DIdle
  (cons (DSlot 12) (cons (DRun tail_run) (cons DIdle nil))))).

Example tail_is_admitted : decl_admits tail_decl = true := eq_refl.
Example tail_starts_fresh : fresh tail_decl solo_start = true := eq_refl.

Theorem tail_trace_conforms : Conforming tail_decl (start solo_start) tail_steps.
Proof.
  split; [ split; reflexivity | ].
  split.
  - split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. split; [ unfold call_bound; simpl; lia | split; [ reflexivity | lia ] ].
  - split; [ reflexivity | ].
    split; [ split; reflexivity | ].
    split.
    + split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
      simpl. split; [ unfold call_bound; simpl; lia | split; [ reflexivity | lia ] ].
    + split; [ reflexivity | exact I ].
Qed.

Example tail_lags :
  Qeq_bool (lag SlotTime 0 (cf_past (exec_all tail_decl (start solo_start) tail_steps))) 8 = true
  /\ Qeq_bool (lag ServedTime 0 (cf_past (exec_all tail_decl (start solo_start) tail_steps))) 0 = true
  /\ Qeq_bool (register_lag_bound tail_decl) 4 = true :=
  conj eq_refl (conj eq_refl eq_refl).

Theorem the_slot_time_reading_is_refuted :
  ~ LagBounded SlotTime tail_decl (register_lag_bound tail_decl).
Proof.
  intros H.
  pose proof (H solo_start tail_steps eq_refl tail_trace_conforms 0 eq_refl) as Hb.
  apply Qle_bool_iff in Hb.
  assert (E : Qle_bool (Qabs (lag SlotTime 0 (cf_past (exec_all tail_decl (start solo_start) tail_steps))))
                       (register_lag_bound tail_decl) = false) by reflexivity.
  rewrite E in Hb. discriminate Hb.
Qed.

(* -------------------------------------------------------------------------
   F3's construction. Two members of weight 1 and request 10. Member 0
   wins the tie, runs four call bounds and its sink, and is ahead of
   virtual time; member 1 runs one unit and yields with nothing pending,
   leaving owed service behind. Member 0 then competes alone, never
   eligible again, and the core idles slot after slot with its work
   pending, while its served-time lag stays inside the register's bound.
   ------------------------------------------------------------------------- *)

Definition wc_decl : Decl := {|
  dc_count := 2;
  dc_weight := fun _ => 1;
  dc_request := fun _ => 10;
  dc_focus_weight := 1;
  dc_focus_request := 10;
  dc_call_interval := 1;
  dc_yield_bound := 2;
  dc_step := 5;
  dc_widths := cons 100 nil;
  dc_app := fun i => i;
  dc_machine := demo_rotation_swaps
|}.

Definition wc_start : DState :=
  {| ds_vtime := 0%Q; ds_focus := None; ds_member := fun _ => fields true true 0 10 |}.

Definition wc_first : Run :=
  {| run_member := 0; run_gaps := cons 3 (cons 3 (cons 3 (cons 3 nil)));
     run_sink := Some 2; run_pending := true |}.

Definition wc_second : Run :=
  {| run_member := 1; run_gaps := cons 1 nil; run_sink := None; run_pending := false |}.

Definition wc_steps : list DStep :=
  cons (DSlot 100) (cons (DRun wc_first) (cons (DRun wc_second)
  (cons DIdle (cons (DSlot 100) (cons DIdle nil))))).

Definition IdlesOnlyWithoutWork (d : Decl) : Prop :=
  forall (s0 : DState) (steps : list DStep),
    fresh d s0 = true -> Conforming d (start s0) steps ->
    forall j, competing d (cf_state (exec_all d (start s0) steps)) j = true ->
      boundary_ok d (cf_rem (exec_all d (start s0) steps)) = true ->
      select d (cf_state (exec_all d (start s0) steps)) <> None.

Definition wc_prefix : list DStep :=
  cons (DSlot 100) (cons (DRun wc_first) (cons (DRun wc_second) nil)).

Example wc_is_admitted : decl_admits wc_decl = true := eq_refl.
Example wc_starts_fresh : fresh wc_decl wc_start = true := eq_refl.

Theorem wc_trace_conforms : Conforming wc_decl (start wc_start) wc_steps.
Proof.
  split; [ split; reflexivity | ].
  split.
  - split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. unfold call_bound. simpl.
    split; [ lia | split; [ reflexivity | ] ].
    split; [ lia | split; [ reflexivity | ] ].
    split; [ lia | split; [ reflexivity | ] ].
    split; [ lia | split; [ reflexivity | lia ] ].
  - split.
    + split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
      simpl. unfold call_bound. simpl. split; [ lia | exact I ].
    + split; [ reflexivity | ].
      split; [ split; reflexivity | ].
      split; [ reflexivity | exact I ].
Qed.

Theorem wc_prefix_conforms : Conforming wc_decl (start wc_start) wc_prefix.
Proof.
  exact (conforming_app wc_decl (start wc_start) wc_prefix
           (cons DIdle (cons (DSlot 100) (cons DIdle nil))) wc_trace_conforms).
Qed.

Example wc_starves_member_0 :
  competing wc_decl (cf_state (exec_all wc_decl (start wc_start) wc_prefix)) 0 = true
  /\ boundary_ok wc_decl (cf_rem (exec_all wc_decl (start wc_start) wc_prefix)) = true
  /\ select wc_decl (cf_state (exec_all wc_decl (start wc_start) wc_prefix)) = None
  /\ select wc_decl (cf_state (exec_all wc_decl (start wc_start) wc_steps)) = None
  /\ Qle_bool (Qabs (lag ServedTime 0 (cf_past (exec_all wc_decl (start wc_start) wc_steps))))
       (register_lag_bound wc_decl) = true
  /\ Qle_bool (Qabs (lag ServedTime 1 (cf_past (exec_all wc_decl (start wc_start) wc_steps))))
       (register_lag_bound wc_decl) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Theorem the_literal_leave_rule_is_not_work_conserving : ~ IdlesOnlyWithoutWork wc_decl.
Proof.
  intros H.
  destruct wc_starves_member_0 as [ Hc [ Hb [ Hs _ ] ] ].
  exact (H wc_start wc_prefix eq_refl wc_prefix_conforms 0 Hc Hb Hs).
Qed.

(* -------------------------------------------------------------------------
   The boundary rule's refutations: a kernel whose test is one call bound,
   a kernel with no test, and the backstop standing in for the checked
   sink. Each lets a conforming run end past the slot boundary.
   ------------------------------------------------------------------------- *)

Definition thin_boundary (d : Decl) (rem : nat) : bool := Nat.leb (call_bound d) rem.

Definition no_boundary (rem : nat) : bool := true.

Definition cut_decl : Decl := {|
  dc_count := 1;
  dc_weight := fun _ => 1;
  dc_request := fun _ => 10;
  dc_focus_weight := 1;
  dc_focus_request := 10;
  dc_call_interval := 1;
  dc_yield_bound := 2;
  dc_step := 5;
  dc_widths := cons 12 nil;
  dc_app := fun i => i;
  dc_machine := demo_rotation_swaps
|}.

Definition cut_start : DState :=
  {| ds_vtime := 0%Q; ds_focus := None; ds_member := fun _ => fields true true 0 10 |}.

Definition cut_sinking : Run :=
  {| run_member := 0; run_gaps := cons 3 nil; run_sink := Some 2; run_pending := true |}.

Definition cut_continuing : Run :=
  {| run_member := 0; run_gaps := cons 3 (cons 3 nil); run_sink := None; run_pending := true |}.

Definition cut_backstopped : Run :=
  {| run_member := 0; run_gaps := cons 3 nil; run_sink := Some 3; run_pending := true |}.

Theorem a_call_bound_test_cuts_a_member_mid_sink :
  RunConformsWith (thin_boundary cut_decl) (dc_yield_bound cut_decl) cut_decl cut_start 3 cut_sinking
  /\ run_service cut_sinking + dc_step cut_decl > 3
  /\ ~ NeverCuts (thin_boundary cut_decl) (dc_yield_bound cut_decl) cut_decl.
Proof.
  assert (Hr : RunConformsWith (thin_boundary cut_decl) (dc_yield_bound cut_decl)
                 cut_decl cut_start 3 cut_sinking).
  { split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. split; [ unfold call_bound; simpl; lia | split; [ reflexivity | lia ] ]. }
  split; [ exact Hr | split; [ simpl; lia | ] ].
  intros H. specialize (H cut_start 3 cut_sinking Hr). simpl in H. lia.
Qed.

Theorem dropping_the_boundary_rule_cuts_a_member :
  RunConformsWith no_boundary (dc_yield_bound cut_decl) cut_decl cut_start 3 cut_continuing
  /\ ~ NeverCuts no_boundary (dc_yield_bound cut_decl) cut_decl.
Proof.
  assert (Hr : RunConformsWith no_boundary (dc_yield_bound cut_decl)
                 cut_decl cut_start 3 cut_continuing).
  { split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. unfold call_bound. simpl.
    split; [ lia | split; [ reflexivity | split; [ lia | exact I ] ] ]. }
  split; [ exact Hr | ].
  intros H. specialize (H cut_start 3 cut_continuing Hr). simpl in H. lia.
Qed.

Theorem the_backstop_alone_cuts_a_member :
  RunConformsWith (boundary_ok cut_decl) (call_bound cut_decl) cut_decl cut_start 10 cut_backstopped
  /\ ~ NeverCuts (boundary_ok cut_decl) (call_bound cut_decl) cut_decl.
Proof.
  assert (Hr : RunConformsWith (boundary_ok cut_decl) (call_bound cut_decl)
                 cut_decl cut_start 10 cut_backstopped).
  { split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. unfold call_bound. simpl. split; [ lia | split; [ reflexivity | lia ] ]. }
  split; [ exact Hr | ].
  intros H. specialize (H cut_start 10 cut_backstopped Hr). simpl in H. lia.
Qed.

(* The dispatch that reads outside state, refuted at F1's declaration. *)
Definition leak_calm : Global :=
  {| g_frame := env_frame 40; g_domain := cx_start; g_others := fun _ => 0 |}.

Definition leak_busy : Global :=
  {| g_frame := env_frame 40; g_domain := cx_start; g_others := fun _ => 1 |}.

Theorem a_dispatch_reading_another_label_is_refuted :
  leaky_choice cx_decl leak_calm = Some 1
  /\ leaky_choice cx_decl leak_busy = None
  /\ ~ ReadsOnlyItsLabel (leaky_choice cx_decl).
Proof.
  split; [ reflexivity | split; [ reflexivity | ] ].
  intros H. specialize (H leak_calm leak_busy eq_refl).
  assert (E : leaky_choice cx_decl leak_calm = Some 1) by reflexivity.
  assert (F : leaky_choice cx_decl leak_busy = None) by reflexivity.
  rewrite E, F in H. discriminate H.
Qed.

(* Admission refuses a domain slot narrower than the boundary's need and a
   step that does not carry the clear. *)
Example admission_refuses_a_narrow_slot_and_an_uncharged_clear :
  decl_admits {| dc_count := 1; dc_weight := fun _ => 1; dc_request := fun _ => 1;
                 dc_focus_weight := 1; dc_focus_request := 1; dc_call_interval := 1;
                 dc_yield_bound := 2; dc_step := 5; dc_widths := cons 9 nil;
                 dc_app := fun i => i; dc_machine := demo_rotation_swaps |} = false
  /\ decl_admits {| dc_count := 1; dc_weight := fun _ => 1; dc_request := fun _ => 1;
                    dc_focus_weight := 1; dc_focus_request := 1; dc_call_interval := 1;
                    dc_yield_bound := 2; dc_step := 4; dc_widths := cons 12 nil;
                    dc_app := fun i => i; dc_machine := demo_rotation_swaps |} = false :=
  conj eq_refl eq_refl.

(* =========================================================================
   S6. The yield-bound obligation (R-07-037h).
   ========================================================================= *)

Record Cfg : Type := {
  cfg_edge : nat -> nat -> bool;
  cfg_back : nat -> nat -> bool;
  cfg_recursive_entry : nat -> bool;
  cfg_poll : nat -> bool;
  cfg_entry : nat;
  cfg_exit : nat -> bool;
  cfg_cost : nat -> nat
}.

Fixpoint chain (g : Cfg) (x : nat) (l : list nat) : bool :=
  match l with nil => true | cons y r => cfg_edge g x y && chain g y r end.

(* A reaction runs from the entry or a poll site to the next poll site or
   an exit through blocks that carry none (reading 8). *)
Definition Reaction (g : Cfg) (from : nat) (inner : list nat) (to : nat) : Prop :=
  (Nat.eqb from (cfg_entry g) || cfg_poll g from) = true
  /\ (cfg_exit g to || cfg_poll g to) = true
  /\ all_of (fun v => negb (cfg_poll g v)) inner = true
  /\ chain g from (inner ++ cons to nil) = true.

Definition reaction_cost (g : Cfg) (from : nat) (inner : list nat) : nat :=
  cfg_cost g from + sum_list (map (cfg_cost g) inner).

Definition PollsEveryBackEdge (g : Cfg) : Prop :=
  forall u v, cfg_back g u v = true -> cfg_poll g v = true.

Definition PollsEveryRecursiveEntry (g : Cfg) : Prop :=
  forall v, cfg_recursive_entry g v = true -> cfg_poll g v = true.

Definition ReactionsWithin (g : Cfg) (Y : nat) : Prop :=
  forall from inner to, Reaction g from inner to -> reaction_cost g from inner <= Y.

Definition YieldBoundAdmits (g : Cfg) (Y : nat) : Prop :=
  PollsEveryBackEdge g /\ PollsEveryRecursiveEntry g /\ ReactionsWithin g Y.

(* A loop: entry 0, header 1 carrying the poll site, body 2, exit 3. *)
Definition loop_edge (u v : nat) : bool :=
  match u, v with
  | 0, 1 => true | 1, 2 => true | 2, 1 => true | 1, 3 => true
  | _, _ => false
  end.

Definition loop_back (u v : nat) : bool :=
  match u, v with 2, 1 => true | _, _ => false end.

Definition loop_cost (v : nat) : nat :=
  match v with 0 => 2 | 1 => 1 | 2 => 5 | _ => 1 end.

Definition loop_cfg : Cfg := {|
  cfg_edge := loop_edge; cfg_back := loop_back; cfg_recursive_entry := fun _ => false;
  cfg_poll := fun v => Nat.eqb v 1; cfg_entry := 0; cfg_exit := fun v => Nat.eqb v 3;
  cfg_cost := loop_cost
|}.

(* The same loop with its poll site removed. *)
Definition unpolled_cfg : Cfg := {|
  cfg_edge := loop_edge; cfg_back := loop_back; cfg_recursive_entry := fun _ => false;
  cfg_poll := fun _ => false; cfg_entry := 0; cfg_exit := fun v => Nat.eqb v 3;
  cfg_cost := loop_cost
|}.

Theorem the_polled_loop_is_admitted_at_its_longest_reaction :
  YieldBoundAdmits loop_cfg 6.
Proof.
  split; [ | split ].
  - intros u v H. destruct u as [ | [ | [ | u ] ] ]; destruct v as [ | [ | v ] ];
      simpl in H; try discriminate H; reflexivity.
  - intros v H. cbn in H. discriminate H.
  - intros from inner to [ Hs [ Ht [ Hi Hc ] ] ]. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + destruct from as [ | [ | from ] ]; cbn; [ lia | lia | ].
      cbn in Hs. discriminate Hs.
    + destruct from as [ | [ | from ] ]; [ | | cbn in Hs; discriminate Hs ];
        destruct x as [ | [ | [ | [ | x ] ] ] ]; cbn in Hi, Hc |- *;
        try discriminate Hi; try discriminate Hc; lia.
    + destruct from as [ | [ | from ] ]; [ | | cbn in Hs; discriminate Hs ];
        destruct x as [ | [ | [ | [ | x ] ] ] ]; destruct y as [ | [ | [ | [ | y ] ] ] ];
        cbn in Hi, Hc; try discriminate Hi; try discriminate Hc.
Qed.

(* A reaction above the declared bound is refused. *)
Theorem a_reaction_above_the_bound_is_refused : ~ YieldBoundAdmits loop_cfg 5.
Proof.
  intros [ _ [ _ H ] ].
  assert (Hr : Reaction loop_cfg 1 (cons 2 nil) 1).
  { split; [ reflexivity | split; [ reflexivity | split; reflexivity ] ]. }
  specialize (H 1 (cons 2 nil) 1 Hr). unfold reaction_cost in H. cbn in H. lia.
Qed.

Fixpoint pump (k : nat) : list nat :=
  match k with 0 => nil | S j => cons 2 (cons 1 (pump j)) end.

Lemma pump_chain : forall k, chain unpolled_cfg 1 (pump k ++ cons 3 nil) = true.
Proof. intros k. induction k as [ | j IH ]; [ reflexivity | simpl; exact IH ]. Qed.

Lemma pump_cost : forall k, sum_list (map (cfg_cost unpolled_cfg) (pump k)) = 6 * k.
Proof.
  intros k. induction k as [ | j IH ]; [ reflexivity | ].
  change (sum_list (map (cfg_cost unpolled_cfg) (pump (S j))))
    with (5 + (1 + sum_list (map (cfg_cost unpolled_cfg) (pump j)))).
  rewrite IH. lia.
Qed.

(* A back-edge without a poll site is refused, and at every bound: the loop
   pumps a reaction past any yield bound whatever. *)
Theorem an_unpolled_back_edge_admits_no_yield_bound :
  ~ PollsEveryBackEdge unpolled_cfg /\ forall Y, ~ ReactionsWithin unpolled_cfg Y.
Proof.
  split.
  - intros H. specialize (H 2 1 eq_refl). discriminate H.
  - intros Y H.
    assert (Hr : Reaction unpolled_cfg 0 (cons 1 (pump Y)) 3).
    { split; [ reflexivity | split; [ reflexivity | split ] ].
      - apply all_of_const. intros v. reflexivity.
      - simpl. exact (pump_chain Y). }
    specialize (H 0 (cons 1 (pump Y)) 3 Hr).
    unfold reaction_cost in H.
    change (2 + (1 + sum_list (map (cfg_cost unpolled_cfg) (pump Y))) <= Y) in H.
    rewrite pump_cost in H. lia.
Qed.

(* R-07-037h's counter: a poll site invokes (iii) once the cost since the
   last invocation reaches the call interval. The gaps between invocations
   of an execution whose every reaction is within the yield bound are within
   the call bound, which is why the call bound is the interval plus one
   yield bound. *)
Fixpoint invocation_gaps (interval acc : nat) (reactions : list nat) : list nat :=
  match reactions with
  | nil => nil
  | cons r rest =>
      if Nat.leb interval (acc + r)
      then cons (acc + r) (invocation_gaps interval 0 rest)
      else invocation_gaps interval (acc + r) rest
  end.

Lemma invocation_gaps_bounded : forall I Y reactions acc,
  acc <= I -> all_of (fun r => Nat.leb r Y) reactions = true ->
  forall g, In g (invocation_gaps I acc reactions) -> g <= I + Y.
Proof.
  intros I Y reactions. induction reactions as [ | r rest IH ]; intros acc Hacc Hall g Hg.
  - destruct Hg.
  - simpl in Hall. apply andb_prop in Hall. destruct Hall as [ Hr Hrest ].
    apply Nat.leb_le in Hr. simpl in Hg.
    destruct (Nat.leb I (acc + r)) eqn:E.
    + destruct Hg as [ Hg | Hg ].
      * subst g. lia.
      * apply (IH 0); [ lia | exact Hrest | exact Hg ].
    + apply Nat.leb_gt in E. apply (IH (acc + r)); [ lia | exact Hrest | exact Hg ].
Qed.

(*| discharges: R-07-037h |*)
Theorem the_counter_bounds_every_path_between_invocations :
  forall (d : Decl) reactions,
    all_of (fun r => Nat.leb r (dc_yield_bound d)) reactions = true ->
    forall g, In g (invocation_gaps (dc_call_interval d) 0 reactions) -> g <= call_bound d.
Proof.
  intros d reactions Hall g Hg. unfold call_bound.
  exact (invocation_gaps_bounded _ _ reactions 0 (Nat.le_0_l _) Hall g Hg).
Qed.

(* A counter compiled at twice the interval admits a longer path. *)
Example a_miscompiled_counter_exceeds_the_call_bound :
  mem_nat 5 (invocation_gaps 4 0 (cons 2 (cons 1 (cons 2 nil)))) = true
  /\ Nat.ltb (2 + 2) 5 = true := conj eq_refl eq_refl.

(* =========================================================================
   S7. The pool service's four guarantees (R-08-047b, R-08-006, R-08-007a,
   R-15-007c, R-15-007k).
   ========================================================================= *)

Record SizeClass : Type := { sc_length : nat; sc_align : nat }.

(* R-15-007k's table obligation: the class's length and its alignment are
   whole multiples of the granule R-15-007c fixes for that length, so a
   class-aligned base narrows exactly with no runtime rounding. *)
Definition class_exact (c : SizeClass) : bool :=
  let g := representable_granule (sc_length c) in
  Nat.ltb 0 (sc_length c) && Nat.ltb 0 (sc_align c)
  && Nat.eqb (sc_length c mod g) 0 && Nat.eqb (sc_align c mod g) 0.

Record Cap : Type := { cap_base : nat; cap_length : nat; cap_store : bool }.

(* The observable history (reading 9): a grant hands a holder a chunk of a
   class at a base with a capability; a release returns one; a member's
   store writes a byte; the service zeroes a range; R-08-006's barrier
   completes; a sweep pass begins and ends. *)
Inductive AllocEvent : Type :=
| Grant (holder cls base : nat) (cap : Cap)
| Release (base cls : nat)
| Write (addr value : nat)
| Zero (base len : nat)
| BarrierDone
| SweepBegin
| SweepEnd.

(* Where grants are drawn from: a domain's pool, or one member's chunk. *)
Record Arena : Type := {
  ar_base : nat;
  ar_span : nat;
  ar_classes : list SizeClass;
  ar_initial : nat -> nat
}.

Definition class_len (a : Arena) (cls : nat) : nat :=
  match nth_error (ar_classes a) cls with Some c => sc_length c | None => 0 end.

Definition overlaps (b1 l1 b2 l2 : nat) : bool := Nat.ltb b1 (b2 + l2) && Nat.ltb b2 (b1 + l1).

Definition is_release_of (b : nat) (e : option AllocEvent) : bool :=
  match e with Some (Release b' _) => Nat.eqb b b' | _ => false end.

Definition released_between (h : list AllocEvent) (b p q : nat) : bool :=
  any_of (fun k => Nat.ltb p k && Nat.ltb k q && is_release_of b (nth_error h k)) (upto q).

(* (i) Chunks live at the same time are disjoint. *)
Definition disjoint_at (a : Arena) (h : list AllocEvent) (q : nat) : bool :=
  match nth_error h q with
  | Some (Grant _ c2 b2 _) =>
      all_of (fun p => match nth_error h p with
                       | Some (Grant _ c1 b1 _) =>
                           released_between h b1 p q
                           || negb (overlaps b1 (class_len a c1) b2 (class_len a c2))
                       | _ => true
                       end) (upto q)
  | _ => true
  end.

Definition LiveChunksDisjoint (a : Arena) (h : list AllocEvent) : Prop :=
  forall q, Nat.ltb q (length h) = true -> disjoint_at a h q = true.

(* (ii) A chunk's capability is bounded exactly to it, at a class of the
   table, aligned to the class, inside the arena. *)
Definition grant_exact (a : Arena) (e : AllocEvent) : bool :=
  match e with
  | Grant _ cls b k =>
      match nth_error (ar_classes a) cls with
      | Some c => class_exact c && Nat.eqb (b mod sc_align c) 0
                  && Nat.eqb (cap_base k) b && Nat.eqb (cap_length k) (sc_length c)
                  && Nat.leb (ar_base a) b && Nat.leb (b + sc_length c) (ar_base a + ar_span a)
      | None => false
      end
  | _ => true
  end.

Definition exact_at (a : Arena) (h : list AllocEvent) (q : nat) : bool :=
  match nth_error h q with Some e => grant_exact a e | None => true end.

Definition BoundedExactly (a : Arena) (h : list AllocEvent) : Prop :=
  forall q, Nat.ltb q (length h) = true -> exact_at a h q = true.

(* (iii) A chunk is zeroed before it is handed out. *)
Definition apply_event (m : nat -> nat) (e : AllocEvent) : nat -> nat :=
  match e with
  | Write addr v => fun x => if Nat.eqb x addr then v else m x
  | Zero b l => fun x => if Nat.leb b x && Nat.ltb x (b + l) then 0 else m x
  | _ => m
  end.

Definition memory_before (a : Arena) (h : list AllocEvent) (q : nat) : nat -> nat :=
  fold_left apply_event (firstn q h) (ar_initial a).

Definition zeroed_at (a : Arena) (h : list AllocEvent) (q : nat) : bool :=
  match nth_error h q with
  | Some (Grant _ c b _) =>
      all_of (fun off => Nat.eqb (memory_before a h q (b + off)) 0) (upto (class_len a c))
  | _ => true
  end.

Definition ZeroedAtHandoff (a : Arena) (h : list AllocEvent) : Prop :=
  forall q, Nat.ltb q (length h) = true -> zeroed_at a h q = true.

(* (iv) A released chunk's bytes return to service only after R-08-006's
   barrier and a whole sweep pass begun after that barrier (R-08-007a). *)
Definition is_barrier (e : option AllocEvent) : bool :=
  match e with Some BarrierDone => true | _ => false end.
Definition is_sweep_begin (e : option AllocEvent) : bool :=
  match e with Some SweepBegin => true | _ => false end.
Definition is_sweep_end (e : option AllocEvent) : bool :=
  match e with Some SweepEnd => true | _ => false end.

Definition begun_between (h : list AllocEvent) (sp ep : nat) : bool :=
  any_of (fun k => Nat.ltb sp k && Nat.ltb k ep && is_sweep_begin (nth_error h k)) (upto ep).

Definition gate_passed (h : list AllocEvent) (p q : nat) : bool :=
  any_of (fun bp => Nat.ltb p bp && is_barrier (nth_error h bp) &&
    any_of (fun sp => Nat.ltb bp sp && is_sweep_begin (nth_error h sp) &&
      any_of (fun ep => Nat.ltb sp ep && is_sweep_end (nth_error h ep)
                        && negb (begun_between h sp ep)) (upto q))
      (upto q)) (upto q).

Definition reuse_ok_at (a : Arena) (h : list AllocEvent) (q : nat) : bool :=
  match nth_error h q with
  | Some (Grant _ c2 b2 _) =>
      all_of (fun p => match nth_error h p with
                       | Some (Release b1 c1) =>
                           negb (overlaps b1 (class_len a c1) b2 (class_len a c2))
                           || gate_passed h p q
                       | _ => true
                       end) (upto q)
  | _ => true
  end.

Definition ReusedOnlyAfterTheSweep (a : Arena) (h : list AllocEvent) : Prop :=
  forall q, Nat.ltb q (length h) = true -> reuse_ok_at a h q = true.

Definition PoolGuarantees (a : Arena) (h : list AllocEvent) : Prop :=
  LiveChunksDisjoint a h /\ BoundedExactly a h /\ ZeroedAtHandoff a h
  /\ ReusedOnlyAfterTheSweep a h.

(* What each guarantee says about bytes, capabilities and positions. *)

(*| discharges: R-08-047b |*)
Theorem live_chunks_share_no_byte :
  forall a h, LiveChunksDisjoint a h ->
  forall p q w1 c1 b1 k1 w2 c2 b2 k2 x,
    p < q -> q < length h ->
    nth_error h p = Some (Grant w1 c1 b1 k1) -> nth_error h q = Some (Grant w2 c2 b2 k2) ->
    released_between h b1 p q = false ->
    ~ (b1 <= x < b1 + class_len a c1 /\ b2 <= x < b2 + class_len a c2).
Proof.
  intros a h H p q w1 c1 b1 k1 w2 c2 b2 k2 x Hpq Hq Ep Eq Hrel [ Hx1 Hx2 ].
  assert (Hql : Nat.ltb q (length h) = true) by (apply Nat.ltb_lt; exact Hq).
  pose proof (H q Hql) as Hd. unfold disjoint_at in Hd. rewrite Eq in Hd.
  assert (Hpl : Nat.ltb p q = true) by (apply Nat.ltb_lt; exact Hpq).
  pose proof (all_of_upto _ q p Hd Hpl) as Hp. simpl in Hp. rewrite Ep in Hp.
  rewrite Hrel in Hp. simpl in Hp. apply negb_true_iff in Hp.
  unfold overlaps in Hp. apply andb_false_iff in Hp.
  destruct Hp as [ Hp | Hp ]; apply Nat.ltb_ge in Hp; lia.
Qed.

(*| discharges: R-08-047b, R-15-007k |*)
Theorem an_exact_grant_needs_no_rounding :
  forall a w cls b k, grant_exact a (Grant w cls b k) = true ->
    exists c, nth_error (ar_classes a) cls = Some c
      /\ cap_base k = b /\ cap_length k = sc_length c
      /\ b mod representable_granule (sc_length c) = 0
      /\ sc_length c mod representable_granule (sc_length c) = 0.
Proof.
  intros a w cls b k H. unfold grant_exact in H.
  destruct (nth_error (ar_classes a) cls) as [ c | ] eqn:E; [ | discriminate H ].
  exists c. split; [ reflexivity | ].
  apply andb_prop in H. destruct H as [ H _ ].
  apply andb_prop in H. destruct H as [ H _ ].
  apply andb_prop in H. destruct H as [ H Hlen ].
  apply andb_prop in H. destruct H as [ H Hbase ].
  apply andb_prop in H. destruct H as [ Hc Hal ].
  unfold class_exact in Hc. cbv zeta in Hc.
  apply andb_prop in Hc. destruct Hc as [ Hc Hag ].
  apply andb_prop in Hc. destruct Hc as [ _ Hlg ].
  apply Nat.eqb_eq in Hal. apply Nat.eqb_eq in Hbase. apply Nat.eqb_eq in Hlen.
  apply Nat.eqb_eq in Hag. apply Nat.eqb_eq in Hlg.
  split; [ exact Hbase | split; [ exact Hlen | split ] ].
  - exact (mod_through_a_multiple b (sc_align c) _ Hal Hag).
  - exact Hlg.
Qed.

(*| discharges: R-08-047b |*)
Theorem every_byte_is_zero_at_handoff :
  forall a h, ZeroedAtHandoff a h ->
  forall q w c b k x, q < length h -> nth_error h q = Some (Grant w c b k) ->
    b <= x < b + class_len a c -> memory_before a h q x = 0.
Proof.
  intros a h H q w c b k x Hq Eq Hx.
  assert (Hql : Nat.ltb q (length h) = true) by (apply Nat.ltb_lt; exact Hq).
  pose proof (H q Hql) as Hz. unfold zeroed_at in Hz. rewrite Eq in Hz.
  assert (Ho : Nat.ltb (x - b) (class_len a c) = true) by (apply Nat.ltb_lt; lia).
  pose proof (all_of_upto _ _ (x - b) Hz Ho) as Hb. simpl in Hb.
  apply Nat.eqb_eq in Hb. replace (b + (x - b)) with x in Hb by lia. exact Hb.
Qed.

(*| discharges: R-08-047b, R-08-007a |*)
Theorem a_passed_gate_is_a_barrier_then_a_whole_sweep_begun_after_it :
  forall h p q, gate_passed h p q = true ->
    exists bp sp ep, p < bp /\ bp < sp /\ sp < ep /\ ep < q
      /\ nth_error h bp = Some BarrierDone
      /\ nth_error h sp = Some SweepBegin
      /\ nth_error h ep = Some SweepEnd
      /\ begun_between h sp ep = false.
Proof.
  intros h p q H.
  destruct (any_of_in _ _ _ H) as [ bp [ Hbp Hb ] ].
  apply andb_prop in Hb. destruct Hb as [ Hb Hs ]. apply andb_prop in Hb.
  destruct Hb as [ Hpb Hbar ].
  destruct (any_of_in _ _ _ Hs) as [ sp [ Hsp Hs2 ] ].
  apply andb_prop in Hs2. destruct Hs2 as [ Hs2 He ]. apply andb_prop in Hs2.
  destruct Hs2 as [ Hbs Hbeg ].
  destruct (any_of_in _ _ _ He) as [ ep [ Hep He2 ] ].
  apply andb_prop in He2. destruct He2 as [ He2 Hnb ]. apply andb_prop in He2.
  destruct He2 as [ Hse Hend ].
  exists bp, sp, ep.
  apply Nat.ltb_lt in Hpb. apply Nat.ltb_lt in Hbs. apply Nat.ltb_lt in Hse.
  apply upto_in in Hep.
  split; [ exact Hpb | split; [ exact Hbs | split; [ exact Hse | split; [ exact Hep | ] ] ] ].
  unfold is_barrier in Hbar. unfold is_sweep_begin in Hbeg. unfold is_sweep_end in Hend.
  split; [ destruct (nth_error h bp) as [ [ ] | ]; try discriminate Hbar; reflexivity | ].
  split; [ destruct (nth_error h sp) as [ [ ] | ]; try discriminate Hbeg; reflexivity | ].
  split; [ destruct (nth_error h ep) as [ [ ] | ]; try discriminate Hend; reflexivity | ].
  apply negb_true_iff. exact Hnb.
Qed.

(* A pool extent of 1024 bytes at 1024 with two classes, bytes before the
   history set to 9 so that the zeroing is what zeroes them. *)
Definition pool_arena : Arena := {|
  ar_base := 1024; ar_span := 1024;
  ar_classes := cons {| sc_length := 64; sc_align := 64 |}
                 (cons {| sc_length := 256; sc_align := 256 |} nil);
  ar_initial := fun _ => 9
|}.

Definition chunk_cap (b l : nat) : Cap := {| cap_base := b; cap_length := l; cap_store := true |}.

(* Member 1 takes a chunk, member 2 the next, member 1 writes and releases,
   the barrier completes, a sweep runs, the service zeroes the chunk and
   hands it to member 2. *)
Definition good_history : list AllocEvent :=
  Zero 1024 64 :: Grant 1 0 1024 (chunk_cap 1024 64)
  :: Zero 1088 64 :: Grant 2 0 1088 (chunk_cap 1088 64)
  :: Write 1028 7 :: Release 1024 0
  :: BarrierDone :: SweepBegin :: SweepEnd
  :: Zero 1024 64 :: Grant 2 0 1024 (chunk_cap 1024 64) :: nil.

(* Each guarantee is a property at every position of the history; at a
   concrete history it is decided by computing the check at every position
   below its length. *)
Ltac by_check :=
  let q := fresh "q" in let Hq := fresh "Hq" in
  intros q Hq; refine (all_of_upto _ _ q _ Hq); reflexivity.

Theorem the_pool_history_keeps_all_four_guarantees : PoolGuarantees pool_arena good_history.
Proof.
  split; [ | split; [ | split ] ]; by_check.
Qed.

(* (c) Two live chunks sharing a byte: member 2 is handed member 1's live
   chunk. Its capability is exact, the bytes are zeroed and nothing was
   released, so the other three guarantees hold. *)
Definition shared_history : list AllocEvent :=
  Zero 1024 64 :: Grant 1 0 1024 (chunk_cap 1024 64)
  :: Zero 1024 64 :: Grant 2 0 1024 (chunk_cap 1024 64) :: nil.

Theorem two_live_chunks_sharing_a_byte_are_refuted :
  ~ LiveChunksDisjoint pool_arena shared_history
  /\ BoundedExactly pool_arena shared_history
  /\ ZeroedAtHandoff pool_arena shared_history
  /\ ReusedOnlyAfterTheSweep pool_arena shared_history.
Proof.
  split; [ | split; [ | split ]; by_check ].
  intros H. specialize (H 3 eq_refl). discriminate H.
Qed.

(* (d) A chunk wider than its allocation: the first grant's capability
   covers twice its class. *)
Definition wide_history : list AllocEvent :=
  Zero 1024 64 :: Grant 1 0 1024 (chunk_cap 1024 128)
  :: Zero 1088 64 :: Grant 2 0 1088 (chunk_cap 1088 64)
  :: Write 1028 7 :: Release 1024 0
  :: BarrierDone :: SweepBegin :: SweepEnd
  :: Zero 1024 64 :: Grant 2 0 1024 (chunk_cap 1024 64) :: nil.

Theorem a_chunk_wider_than_its_allocation_is_refuted :
  LiveChunksDisjoint pool_arena wide_history
  /\ ~ BoundedExactly pool_arena wide_history
  /\ ZeroedAtHandoff pool_arena wide_history
  /\ ReusedOnlyAfterTheSweep pool_arena wide_history.
Proof.
  split; [ by_check | split; [ | split; by_check ] ].
  intros H. specialize (H 1 eq_refl). discriminate H.
Qed.

(* (e) A chunk handed out unzeroed: the reuse skips the zeroing, so member
   2 receives member 1's byte. *)
Definition unzeroed_history : list AllocEvent :=
  Zero 1024 64 :: Grant 1 0 1024 (chunk_cap 1024 64)
  :: Zero 1088 64 :: Grant 2 0 1088 (chunk_cap 1088 64)
  :: Write 1028 7 :: Release 1024 0
  :: BarrierDone :: SweepBegin :: SweepEnd
  :: Grant 2 0 1024 (chunk_cap 1024 64) :: nil.

Theorem a_chunk_handed_out_unzeroed_is_refuted :
  LiveChunksDisjoint pool_arena unzeroed_history
  /\ BoundedExactly pool_arena unzeroed_history
  /\ ~ ZeroedAtHandoff pool_arena unzeroed_history
  /\ ReusedOnlyAfterTheSweep pool_arena unzeroed_history
  /\ memory_before pool_arena unzeroed_history 9 1028 = 7.
Proof.
  split; [ by_check | split; [ by_check | split ] ].
  - intros H. specialize (H 9 eq_refl). discriminate H.
  - split; [ by_check | reflexivity ].
Qed.

(* (f) A chunk reused ahead of the sweep: the grant precedes the sweep's
   end. *)
Definition early_history : list AllocEvent :=
  Zero 1024 64 :: Grant 1 0 1024 (chunk_cap 1024 64)
  :: Zero 1088 64 :: Grant 2 0 1088 (chunk_cap 1088 64)
  :: Write 1028 7 :: Release 1024 0
  :: BarrierDone :: SweepBegin
  :: Zero 1024 64 :: Grant 2 0 1024 (chunk_cap 1024 64) :: SweepEnd :: nil.

Theorem a_chunk_reused_ahead_of_the_sweep_is_refuted :
  LiveChunksDisjoint pool_arena early_history
  /\ BoundedExactly pool_arena early_history
  /\ ZeroedAtHandoff pool_arena early_history
  /\ ~ ReusedOnlyAfterTheSweep pool_arena early_history.
Proof.
  split; [ by_check | split; [ by_check | split ] ].
  - by_check.
  - intros H. specialize (H 9 eq_refl). discriminate H.
Qed.

(* And the order R-08-007a names: a sweep begun before the barrier does not
   count, even when it ends after it. *)
Definition presweep_history : list AllocEvent :=
  Zero 1024 64 :: Grant 1 0 1024 (chunk_cap 1024 64)
  :: Zero 1088 64 :: Grant 2 0 1088 (chunk_cap 1088 64)
  :: Write 1028 7 :: Release 1024 0
  :: SweepBegin :: BarrierDone :: SweepEnd
  :: Zero 1024 64 :: Grant 2 0 1024 (chunk_cap 1024 64) :: nil.

Theorem a_sweep_begun_before_the_barrier_is_refuted :
  LiveChunksDisjoint pool_arena presweep_history
  /\ BoundedExactly pool_arena presweep_history
  /\ ZeroedAtHandoff pool_arena presweep_history
  /\ ~ ReusedOnlyAfterTheSweep pool_arena presweep_history.
Proof.
  split; [ by_check | split; [ by_check | split ] ].
  - by_check.
  - intros H. specialize (H 10 eq_refl). discriminate H.
Qed.

(* R-15-007k's refusal at the table: a class whose length is off its own
   granule, and one whose alignment is. *)
Example the_table_refuses_classes_that_would_round :
  representable_granule 129 = 2
  /\ class_exact {| sc_length := 129; sc_align := 2 |} = false
  /\ class_exact {| sc_length := 256; sc_align := 2 |} = false
  /\ class_exact {| sc_length := 256; sc_align := 256 |} = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   S8. The heap library's narrowing (R-08-047b's third acceptance).
   ========================================================================= *)

(* One level down, a member's own chunk is the arena and each allocation a
   grant: every returned capability is narrowed exactly to its allocation
   at a class of the same composition-fixed table, live allocations are
   disjoint, and reuse inside the chunk meets the same gate. *)
Definition HeapNarrows (a : Arena) (h : list AllocEvent) : Prop :=
  BoundedExactly a h /\ LiveChunksDisjoint a h /\ ReusedOnlyAfterTheSweep a h.

Definition chunk_arena : Arena := {|
  ar_base := 2048; ar_span := 256;
  ar_classes := cons {| sc_length := 16; sc_align := 16 |}
                 (cons {| sc_length := 32; sc_align := 32 |} nil);
  ar_initial := fun _ => 0
|}.

Definition heap_history : list AllocEvent :=
  Grant 1 0 2048 (chunk_cap 2048 16) :: Grant 1 1 2080 (chunk_cap 2080 32)
  :: Release 2048 0 :: BarrierDone :: SweepBegin :: SweepEnd
  :: Grant 1 0 2048 (chunk_cap 2048 16) :: nil.

Theorem the_heap_history_narrows_every_allocation : HeapNarrows chunk_arena heap_history.
Proof. split; [ | split ]; by_check. Qed.

(* An allocator returning a capability wider than its allocation, one
   handing application code the chunk-wide capability, and one drawing an
   allocation from outside the table. *)
Definition wider_allocation : list AllocEvent :=
  Grant 1 0 2048 (chunk_cap 2048 32) :: nil.

Definition chunk_wide_allocation : list AllocEvent :=
  Grant 1 0 2048 (chunk_cap 2048 256) :: nil.

Definition untabled_allocation : list AllocEvent :=
  Grant 1 5 2048 (chunk_cap 2048 16) :: nil.

Theorem every_non_narrowing_allocator_is_refuted :
  ~ HeapNarrows chunk_arena wider_allocation
  /\ ~ HeapNarrows chunk_arena chunk_wide_allocation
  /\ ~ HeapNarrows chunk_arena untabled_allocation.
Proof.
  split; [ | split ]; intros [ H _ ]; specialize (H 0 eq_refl); discriminate H.
Qed.

(* =========================================================================
   S9. Capability confinement (R-08-047c, R-12-007).
   ========================================================================= *)

Inductive EdgeKind : Type :=
| RingEdge
| RegisterEndpoint (cap_slot tagged : bool)
| SharedWindow (store_cap : bool)
| SentryInto
| DeviceWindow.

(* Reading 10. *)
Definition carries (k : EdgeKind) : bool :=
  match k with
  | RingEdge => false
  | RegisterEndpoint slot tagged => slot || tagged
  | SharedWindow store => store
  | SentryInto => true
  | DeviceWindow => true
  end.

Record Edge : Type := { e_from : nat; e_to : nat; e_kind : EdgeKind }.

(* The composed distribution around one domain: which partitions are its
   members, the declared edges (a shared window listed in each direction
   it can be written), and the pool extent. *)
Record Distribution : Type := {
  cd_in_domain : nat -> bool;
  cd_edges : list Edge;
  cd_pool_base : nat;
  cd_pool_span : nat
}.

Definition pool_derived (cd : Distribution) (k : Cap) : bool :=
  Nat.leb (cd_pool_base cd) (cap_base k) && Nat.ltb (cap_base k) (cd_pool_base cd + cd_pool_span cd).

Definition crosses (cd : Distribution) (e : Edge) : bool :=
  xorb (cd_in_domain cd (e_from e)) (cd_in_domain cd (e_to e)).

(* R-08-047c, decided against the composition: no edge crossing the
   domain's boundary can carry a capability. *)
Definition edges_confine (cd : Distribution) : bool :=
  all_of (fun e => negb (crosses cd e && carries (e_kind e))) (cd_edges cd).

Definition Holdings : Type := list (nat * Cap).

Definition PoolConfined (cd : Distribution) (hs : Holdings) : Prop :=
  forall h k, In (h, k) hs -> pool_derived cd k = true -> cd_in_domain cd h = true.

(* A capability copied along a declared edge that can carry one. *)
Inductive Transfer (cd : Distribution) : Holdings -> Holdings -> Prop :=
| transfer_along : forall hs e k,
    In e (cd_edges cd) -> carries (e_kind e) = true -> In (e_from e, k) hs ->
    Transfer cd hs (cons (e_to e, k) hs).

Inductive Reach (cd : Distribution) : Holdings -> Holdings -> Prop :=
| reach_here : forall hs, Reach cd hs hs
| reach_step : forall hs hs' hs'', Transfer cd hs hs' -> Reach cd hs' hs'' -> Reach cd hs hs''.

(*| discharges: R-08-047c |*)
Theorem confinement_survives_every_transfer :
  forall cd hs hs', edges_confine cd = true -> PoolConfined cd hs -> Reach cd hs hs' ->
    PoolConfined cd hs'.
Proof.
  intros cd hs hs' Hok Hc Hr. induction Hr as [ hs | hs hs' hs'' Ht Hr IH ].
  - exact Hc.
  - apply IH. destruct Ht as [ hs e k He Hcarry Hin ].
    intros h k' Hin' Hpool. destruct Hin' as [ Heq | Hin' ].
    + injection Heq as Hh Hk. subst h. subst k'.
      pose proof (Hc (e_from e) k Hin Hpool) as Hfrom.
      pose proof (all_of_in _ _ _ _ Hok He) as Hedge. simpl in Hedge.
      rewrite Hcarry in Hedge. rewrite andb_true_r in Hedge.
      apply negb_true_iff in Hedge. unfold crosses in Hedge. rewrite Hfrom in Hedge.
      destruct (cd_in_domain cd (e_to e)); [ reflexivity | discriminate Hedge ].
    + exact (Hc h k' Hin' Hpool).
Qed.

(* So every holder a revocation sweep over the pool must reach is a member,
   and the sweep runs over the domain's own footprint. *)
Theorem the_pool_s_holders_are_the_domain_s_footprint :
  forall cd hs0 hs, edges_confine cd = true -> PoolConfined cd hs0 -> Reach cd hs0 hs ->
    forall h k, In (h, k) hs -> pool_derived cd k = true -> cd_in_domain cd h = true.
Proof.
  intros cd hs0 hs Hok Hc Hr. exact (confinement_survives_every_transfer cd hs0 hs Hok Hc Hr).
Qed.

(* Partitions 0 (the pool service), 1 and 2 are the domain; 9 is a
   fixed-tier server. The pool service holds the root; member 1 a chunk. *)
Definition pool_root : Cap := chunk_cap 1024 1024.
Definition member_chunk : Cap := chunk_cap 1024 64.

Definition initial_holdings : Holdings := cons (0, pool_root) (cons (1, member_chunk) nil).

Definition sealed_distribution : Distribution := {|
  cd_in_domain := fun p => Nat.ltb p 3;
  cd_edges := {| e_from := 1; e_to := 9; e_kind := RingEdge |}
              :: {| e_from := 1; e_to := 9; e_kind := RegisterEndpoint false false |}
              :: {| e_from := 9; e_to := 1; e_kind := SharedWindow false |}
              :: {| e_from := 1; e_to := 9; e_kind := SharedWindow false |}
              :: {| e_from := 1; e_to := 2; e_kind := RegisterEndpoint true true |} :: nil;
  cd_pool_base := 1024; cd_pool_span := 1024
|}.

Theorem the_sealed_distribution_confines_the_pool :
  edges_confine sealed_distribution = true
  /\ PoolConfined sealed_distribution initial_holdings
  /\ Reach sealed_distribution initial_holdings (cons (2, member_chunk) initial_holdings)
  /\ PoolConfined sealed_distribution (cons (2, member_chunk) initial_holdings).
Proof.
  assert (Hc : PoolConfined sealed_distribution initial_holdings).
  { intros h k Hin _. destruct Hin as [ Hin | [ Hin | [] ] ];
      injection Hin as Hh _; subst h; reflexivity. }
  assert (Hr : Reach sealed_distribution initial_holdings (cons (2, member_chunk) initial_holdings)).
  { apply (reach_step _ _ (cons (2, member_chunk) initial_holdings)); [ | apply reach_here ].
    apply (transfer_along sealed_distribution initial_holdings
             {| e_from := 1; e_to := 2; e_kind := RegisterEndpoint true true |} member_chunk).
    - simpl. right. right. right. right. left. reflexivity.
    - reflexivity.
    - simpl. right. left. reflexivity. }
  split; [ reflexivity | split; [ exact Hc | split; [ exact Hr | ] ] ].
  exact (confinement_survives_every_transfer sealed_distribution _ _ eq_refl Hc Hr).
Qed.

(* (g) A pool capability held outside the domain: an endpoint with a
   capability slot to the fixed-tier server, and, separately, an inbound
   surface carrying capability-store permission. *)
Definition slotted_distribution : Distribution := {|
  cd_in_domain := fun p => Nat.ltb p 3;
  cd_edges := {| e_from := 1; e_to := 9; e_kind := RegisterEndpoint true false |} :: nil;
  cd_pool_base := 1024; cd_pool_span := 1024
|}.

Definition storable_surface : Distribution := {|
  cd_in_domain := fun p => Nat.ltb p 3;
  cd_edges := {| e_from := 1; e_to := 9; e_kind := SharedWindow true |} :: nil;
  cd_pool_base := 1024; cd_pool_span := 1024
|}.

Theorem a_pool_capability_held_outside_the_domain_is_refuted :
  edges_confine slotted_distribution = false
  /\ PoolConfined slotted_distribution initial_holdings
  /\ Reach slotted_distribution initial_holdings (cons (9, member_chunk) initial_holdings)
  /\ ~ PoolConfined slotted_distribution (cons (9, member_chunk) initial_holdings)
  /\ edges_confine storable_surface = false
  /\ Reach storable_surface initial_holdings (cons (9, member_chunk) initial_holdings)
  /\ ~ PoolConfined storable_surface (cons (9, member_chunk) initial_holdings).
Proof.
  assert (Hc : PoolConfined slotted_distribution initial_holdings).
  { intros h k Hin _. destruct Hin as [ Hin | [ Hin | [] ] ];
      injection Hin as Hh _; subst h; reflexivity. }
  assert (Hr1 : Reach slotted_distribution initial_holdings (cons (9, member_chunk) initial_holdings)).
  { apply (reach_step _ _ (cons (9, member_chunk) initial_holdings)); [ | apply reach_here ].
    apply (transfer_along slotted_distribution initial_holdings
             {| e_from := 1; e_to := 9; e_kind := RegisterEndpoint true false |} member_chunk).
    - left. reflexivity.
    - reflexivity.
    - right. left. reflexivity. }
  assert (Hr2 : Reach storable_surface initial_holdings (cons (9, member_chunk) initial_holdings)).
  { apply (reach_step _ _ (cons (9, member_chunk) initial_holdings)); [ | apply reach_here ].
    apply (transfer_along storable_surface initial_holdings
             {| e_from := 1; e_to := 9; e_kind := SharedWindow true |} member_chunk).
    - left. reflexivity.
    - reflexivity.
    - right. left. reflexivity. }
  split; [ reflexivity | split; [ exact Hc | split; [ exact Hr1 | split ] ] ].
  - intros H. specialize (H 9 member_chunk (or_introl eq_refl) eq_refl). discriminate H.
  - split; [ reflexivity | split; [ exact Hr2 | ] ].
    intros H. specialize (H 9 member_chunk (or_introl eq_refl) eq_refl). discriminate H.
Qed.

(* =========================================================================
   The envelope's refutations and its admitted instance.
   ========================================================================= *)

Definition plain_manifest (app label : nat) : Manifest := {|
  mf_app := app; mf_label := label; mf_labels_served := 1; mf_owes_deadline := false;
  mf_holds_secret := false; mf_device_authority := false; mf_kind := None
|}.

Definition demo_domain : Domain := {|
  dom_label := 3;
  dom_members := cons 0 (cons 1 nil);
  dom_manifest := fun m => plain_manifest m 3;
  dom_cores := cons 0 nil;
  dom_dormant := fun m c => Nat.ltb m 2 && Nat.eqb c 0;
  dom_extent := fun c => match c with FirstClass => (0, 1024) | SecondClass => (1024, 2048) end
|}.

Theorem the_demo_envelope_is_admitted :
  envelope_admits demo_domain = true
  /\ EveryMemberCarriesTheLabel demo_domain /\ NoMemberIsFixedTier demo_domain.
Proof.
  assert (H : envelope_admits demo_domain = true) by reflexivity.
  split; [ exact H | exact (an_admitted_envelope_has_one_label_and_no_fixed_tier_member _ H) ].
Qed.

(* A second label inside one domain. *)
Definition two_label_domain : Domain := {|
  dom_label := 3;
  dom_members := cons 0 (cons 1 nil);
  dom_manifest := fun m => plain_manifest m (if Nat.eqb m 1 then 4 else 3);
  dom_cores := cons 0 nil;
  dom_dormant := fun m c => Nat.ltb m 2 && Nat.eqb c 0;
  dom_extent := fun c => match c with FirstClass => (0, 1024) | SecondClass => (1024, 2048) end
|}.

(* A member holding device authority, which R-07-037f keeps fixed-tier. *)
Definition driver_domain : Domain := {|
  dom_label := 3;
  dom_members := cons 0 (cons 1 nil);
  dom_manifest := fun m =>
    {| mf_app := m; mf_label := 3; mf_labels_served := 1; mf_owes_deadline := false;
       mf_holds_secret := false; mf_device_authority := Nat.eqb m 1; mf_kind := None |};
  dom_cores := cons 0 nil;
  dom_dormant := fun m c => Nat.ltb m 2 && Nat.eqb c 0;
  dom_extent := fun c => match c with FirstClass => (0, 1024) | SecondClass => (1024, 2048) end
|}.

(* Both classes over one extent. *)
Definition shared_extent_domain : Domain := {|
  dom_label := 3;
  dom_members := cons 0 (cons 1 nil);
  dom_manifest := fun m => plain_manifest m 3;
  dom_cores := cons 0 nil;
  dom_dormant := fun m c => Nat.ltb m 2 && Nat.eqb c 0;
  dom_extent := fun _ => (0, 1024)
|}.

Theorem the_envelope_refuses_what_r_07_037e_names :
  envelope_admits two_label_domain = false
  /\ ~ EveryMemberCarriesTheLabel two_label_domain
  /\ envelope_admits driver_domain = false
  /\ ~ NoMemberIsFixedTier driver_domain
  /\ envelope_admits shared_extent_domain = false.
Proof.
  split; [ reflexivity | split; [ | split; [ reflexivity | split; [ | reflexivity ] ] ] ].
  - intros H. specialize (H 1 (or_intror (or_introl eq_refl))). discriminate H.
  - intros H. specialize (H 1 (or_intror (or_introl eq_refl))). discriminate H.
Qed.

(* A launch that creates: it activates any identity it is asked for,
   including one the composition never enumerated. *)
Definition creating_launch (m core : nat) : bool := true.

Theorem a_launch_that_creates_is_refuted :
  ~ ActivatesOnlyPlaced demo_domain creating_launch.
Proof.
  intros H. destruct (H 5 0 eq_refl) as [ Hin _ ].
  destruct Hin as [ Hin | [ Hin | [] ] ]; discriminate Hin.
Qed.

(* =========================================================================
   R-05-166's inhabitation witnesses: one closed definition per record this
   file declares, named for that record and ascribed at it. Records reached
   through a Require are witnessed in the files that declare them.
   ========================================================================= *)

Definition witness_Manifest : Manifest := plain_manifest 0 3.
Definition witness_Domain : Domain := demo_domain.
Definition witness_PcFields : PcFields := fields true true 0 1.
Definition witness_DState : DState := cx_start.
Definition witness_Decl : Decl := cx_decl.
Definition witness_Global : Global := leak_calm.
Definition witness_Run : Run := cx_light.
Definition witness_Stint : Stint := idle_stint cx_decl cx_start 4.
Definition witness_Config : Config := start cx_start.
Definition witness_Cfg : Cfg := loop_cfg.
Definition witness_SizeClass : SizeClass := {| sc_length := 64; sc_align := 64 |}.
Definition witness_Cap : Cap := member_chunk.
Definition witness_Arena : Arena := pool_arena.
Definition witness_Edge : Edge := {| e_from := 1; e_to := 9; e_kind := RingEdge |}.
Definition witness_Distribution : Distribution := sealed_distribution.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`.
   ------------------------------------------------------------------------- *)

Print Assumptions select.
Print Assumptions reply.
Print Assumptions charge.
Print Assumptions rebalance.
Print Assumptions an_admitted_envelope_has_one_label_and_no_fixed_tier_member.
Print Assumptions launch_activates_only_placed_contexts.
Print Assumptions preferred_total.
Print Assumptions preferred_trans.
Print Assumptions select_is_the_eevdf_choice.
Print Assumptions select_idles_only_when_nothing_is_eligible.
Print Assumptions a_selection_exists_whenever_a_member_is_eligible.
Print Assumptions the_dispatch_reads_only_its_label.
Print Assumptions every_domain_transition_stays_inside.
Print Assumptions a_runtime_width_choice_moves_another_tenant_s_instant.
Print Assumptions the_boundary_rule_leaves_no_member_cut.
Print Assumptions the_backstop_bounds_an_unchecked_sink.
Print Assumptions a_cross_application_step_clears_the_zeroize_class.
Print Assumptions a_cross_application_step_leaves_no_residue.
Print Assumptions a_same_application_step_is_the_rotation.
Print Assumptions the_clear_costs_one_vmclear_and_nothing_else.
Print Assumptions a_rotation_across_applications_leaves_vector_state_standing.
Print Assumptions a_kernel_saving_vector_state_is_refuted.
Print Assumptions an_instant_bound_bounds_every_interval.
Print Assumptions the_share_bound_is_its_instant_half.
Print Assumptions cx_trace_conforms.
Print Assumptions cx_lags.
Print Assumptions the_register_s_lag_bound_is_refuted.
Print Assumptions the_register_s_lag_bound_is_refuted_over_slot_time.
Print Assumptions the_register_s_share_bound_is_refuted.
Print Assumptions tail_trace_conforms.
Print Assumptions tail_lags.
Print Assumptions the_slot_time_reading_is_refuted.
Print Assumptions wc_trace_conforms.
Print Assumptions wc_starves_member_0.
Print Assumptions the_literal_leave_rule_is_not_work_conserving.
Print Assumptions a_call_bound_test_cuts_a_member_mid_sink.
Print Assumptions dropping_the_boundary_rule_cuts_a_member.
Print Assumptions the_backstop_alone_cuts_a_member.
Print Assumptions a_dispatch_reading_another_label_is_refuted.
Print Assumptions admission_refuses_a_narrow_slot_and_an_uncharged_clear.
Print Assumptions the_polled_loop_is_admitted_at_its_longest_reaction.
Print Assumptions a_reaction_above_the_bound_is_refused.
Print Assumptions an_unpolled_back_edge_admits_no_yield_bound.
Print Assumptions the_counter_bounds_every_path_between_invocations.
Print Assumptions a_miscompiled_counter_exceeds_the_call_bound.
Print Assumptions live_chunks_share_no_byte.
Print Assumptions an_exact_grant_needs_no_rounding.
Print Assumptions every_byte_is_zero_at_handoff.
Print Assumptions a_passed_gate_is_a_barrier_then_a_whole_sweep_begun_after_it.
Print Assumptions the_pool_history_keeps_all_four_guarantees.
Print Assumptions two_live_chunks_sharing_a_byte_are_refuted.
Print Assumptions a_chunk_wider_than_its_allocation_is_refuted.
Print Assumptions a_chunk_handed_out_unzeroed_is_refuted.
Print Assumptions a_chunk_reused_ahead_of_the_sweep_is_refuted.
Print Assumptions a_sweep_begun_before_the_barrier_is_refuted.
Print Assumptions the_table_refuses_classes_that_would_round.
Print Assumptions the_heap_history_narrows_every_allocation.
Print Assumptions every_non_narrowing_allocator_is_refuted.
Print Assumptions confinement_survives_every_transfer.
Print Assumptions the_pool_s_holders_are_the_domain_s_footprint.
Print Assumptions the_sealed_distribution_confines_the_pool.
Print Assumptions a_pool_capability_held_outside_the_domain_is_refuted.
Print Assumptions the_demo_envelope_is_admitted.
Print Assumptions the_envelope_refuses_what_r_07_037e_names.
Print Assumptions a_launch_that_creates_is_refuted.
