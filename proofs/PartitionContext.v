(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   PartitionContext.v

   Statement and reference model for the partition context, inter-slot partition
   switch, and intra-slot rotation, expressed in
   [ApexTheorem.v](ApexTheorem.v)'s parameterized record style.

   Governing obligations:
   - Partition context and total restore: 32 merged 64+1-bit capability/data
     registers with no separate capability bank (R-15-007i), the CSR bank
     enclosed by [isa-profile.md](../docs/hardware/isa-profile.md) Section 5.1
     (R-15-001b), and interrupt-file pending bits (R-07-039, R-07-044), with no
     vector/matrix save area (R-07-014a) and no privilege mode to switch
     (R-07-018). Every inter-slot switch restores all nameable restorable CSRs
     and registers (including validity tags) and zeroizes vector CSRs via
     `vmclear` (R-07-014c, R-07-015).
   - Intra-slot rotation and three-term switch cost: intra-slot rotation swaps
     the register and partition context (including the pending component on
     R-07-044's swap arm, R-07-037c) within a same-label group sharing one
     confidentiality domain (R-07-037d; timing bounds in R-11-027) while
     omitting `fence.t`, eager zeroize (`vmclear`), and OPP relock (R-07-037b).
     `switch_cost` sums those three platform constants (`fence_t_cost`,
     `vmclear_cost`, `opp_relock_cost`, with store-buffer drain padding covered
     by R-15-098, R-15-218, and R-15-219), sitting beside R-15-220a's context
     term inside R-07-040 and R-11-009's padded boundary constant (R-15-220,
     R-18-009; see [BoundaryCost.v](BoundaryCost.v)).
   - Layer boundaries: synchronous rendezvous-or-refusal endpoints, poll-site
     yields, the five-invocation frozen ABI, and the three kernel object classes
     beside the two non-object tables (R-07-007, R-07-027, R-07-027a, R-07-029,
     R-07-029a, R-07-031, R-07-031a, R-07-031b, R-07-037a, R-08-004d, R-12-096)
     are governed by their respective kernel and IPC specifications.

   Key readings:
   1. `csr_nameable` and `csr_zeroized` parameterize the CSR bank from
      [isa-profile.md](../docs/hardware/isa-profile.md) without duplicating its
      table; `csr_totality_is_vacuous_where_nothing_is_nameable` exhibits why the
      register file half is stated over the literal 32-register domain.
   2. Both arms of R-07-044's pending-bit disjunction (swapped vs. statically
      partitioned, `pending_swapped`) and R-07-037c's rotation pending-bit swap
      (`rotation_swaps_pending`) are exhibited and proved observably distinct
      (`the_two_pending_arms_differ`, `rotation_pending_arm_is_observable`).
   3. `switch_discharges_every_rotation_obligation` bridges the full inter-slot
      switch and the intra-slot rotation.

   Non-vacuity (R-05-163, R-05-165, R-05-166):
   - Every state, action, and cost obligation is proved for the specification
     and refuted on alternative step relations, action predicates, and cost
     functions over canonically and concretely inhabited machines.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-07-007 R-07-014a R-07-014c R-07-015
      R-07-016 R-07-018 R-07-027 R-07-027a R-07-029 R-07-029a R-07-031 R-07-031a R-07-031b
      R-07-037a R-07-037b R-07-037c R-07-037d R-07-039 R-07-040 R-07-044 R-08-004d R-11-006b
      R-11-009 R-11-027 R-12-096 R-15-001b R-15-007i R-15-098 R-15-214 R-15-218 R-15-219
      R-15-220 R-15-220a R-18-009
   SHA256: cbe593d96a06b1d4ed0865f4423cf7e9faa7cb7c710f8fbfc63b44e9b425bffa
   (*| END derived |*)
   ========================================================================= *)

(* -------------------------------------------------------------------------
   The machine: everything the register leaves to composition or to another
   artifact. Fields rather than Parameters, because a top-level Parameter
   prints as an assumption and fails the R-05-163 gate.
   ------------------------------------------------------------------------- *)

Record Machine : Type := {

  (* --- the CSR bank, owned by isa-profile.md section 5.1 (reading 3) ---- *)

  Csr : Type;
  csr_nameable : Csr -> bool;    (* R-07-015's "a partition can name"        *)
  csr_zeroized : Csr -> bool;    (* section 5.1's "zeroizes and does not
                                    save" disposition                       *)

  (* --- the 64 data bits of a register and of a CSR (R-15-007i) ---------- *)

  Word : Type;
  zero_word : Word;              (* what R-07-014c's pass writes            *)

  (* --- R-07-044's interrupt-file pending bits (gap f) ------------------- *)

  Pending : Type;
  pending_swapped : bool;        (* R-07-044's disjunction: swapped at the
                                    switch, or statically identity-
                                    partitioned (gap g)                     *)
  pending_partition : Pending -> Pending;
                                 (* under the static arm, what the successor
                                    observes of its own bits; a composition
                                    constant R-07-044 does not further
                                    constrain, so no law is stated of it     *)
  rotation_swaps_pending : bool; (* R-07-037c swaps it on R-07-044's
                                    arm where a swap exists                 *)

  (* --- R-15-220's three constants, plus the drain the four-term reading
         would list beside the fence rather than inside it ---------------- *)

  fence_t_cost : nat;
  vmclear_cost : nat;
  opp_relock_cost : nat;
  drain_cost : nat
}.

(* R-15-007i states the file's width as an architectural fact, so 32 is a
   literal here and not a composition constant. *)
Definition register_count : nat := 32.

(* -------------------------------------------------------------------------
   The context, and the machine state, which are one shape: what a switch
   installs is what a switch reads. Three components, and reading 2 says
   why those three. The register component is one function into a value and
   its validity tag, R-15-007i's merged file rather than an integer file
   and a capability file read as two.
   ------------------------------------------------------------------------- *)

Record Context (m : Machine) : Type := {
  ctx_reg : nat -> m.(Word) * bool;
  ctx_csr : m.(Csr) -> m.(Word);
  ctx_pending : m.(Pending)
}.

Arguments ctx_reg {m} _ _.
Arguments ctx_csr {m} _ _.
Arguments ctx_pending {m} _.

(* The state a switch writes is the same shape as the context it writes
   from; naming it separately is what the theorems below quantify over. *)
Definition State (m : Machine) : Type := Context m.

(* -------------------------------------------------------------------------
   R-07-044's two arms, both of them a function of the successor context
   alone, which is what "no interrupt state is hidden or shared across a
   partition boundary" asks of either. Which arm a machine is on is
   pending_swapped's to say and not this file's (gap g).
   ------------------------------------------------------------------------- *)

Definition pending_written (m : Machine) (succ : Context m) : m.(Pending) :=
  if m.(pending_swapped)
  then ctx_pending succ
  else m.(pending_partition) (ctx_pending succ).

(* -------------------------------------------------------------------------
   The obligations, each stated of an arbitrary relation from a successor
   context and a predecessor state to a post-state. Stating them this way
   is what makes the theorems below assertions about the specification
   rather than about one implementation of it (reading 5), and it is what
   the refutation witnesses at the end instantiate.
   ------------------------------------------------------------------------- *)

Definition Step (m : Machine) : Type :=
  Context m -> State m -> State m -> Prop.

(* R-07-015 over the merged file (R-15-007i): every index below
   register_count holds the successor's value and its tag. *)
Definition RestoresRegisters (m : Machine) (R : Step m) : Prop :=
  forall succ pre post, R succ pre post ->
    forall r, Nat.ltb r register_count = true ->
      ctx_reg post r = ctx_reg succ r.

(* R-07-015 over the CSR bank R-15-001b encloses: every CSR the partition
   can name is written before the successor's first instruction, restored
   where section 5.1 restores it and written to zero where section 5.1
   zeroizes it (readings 3 and 4). *)
Definition RestoresNameableCsrs (m : Machine) (R : Step m) : Prop :=
  forall succ pre post, R succ pre post ->
    forall c, m.(csr_nameable) c = true ->
      ctx_csr post c =
        (if m.(csr_zeroized) c then m.(zero_word) else ctx_csr succ c).

(* The half of that obligation a step which omits R-07-014c's pass can
   still meet: the CSRs section 5.1 restores rather than zeroizes
   (reading 7). *)
Definition RestoresRestorableCsrs (m : Machine) (R : Step m) : Prop :=
  forall succ pre post, R succ pre post ->
    forall c, m.(csr_nameable) c = true -> m.(csr_zeroized) c = false ->
      ctx_csr post c = ctx_csr succ c.

(* R-07-015's criterion, "residue is impossible rather than cleared", and
   R-07-044's "no interrupt state is hidden or shared across a partition
   boundary". What is stated is the observable half: two post-states
   reached from one successor context agree on every component the
   obligation reaches, whatever their predecessors held. Whether a
   mechanism achieves that by never writing the predecessor's value or by
   clearing it afterwards is microarchitectural and outside what any
   statement over this context can see, which is the same boundary
   R-07-016 and R-15-214 argue across when they place the obligation here
   instead of in the fence.t flush set. *)
Definition NoResidue (m : Machine) (R : Step m) : Prop :=
  forall succ pre1 post1 pre2 post2,
    R succ pre1 post1 -> R succ pre2 post2 ->
    (forall r, Nat.ltb r register_count = true ->
       ctx_reg post1 r = ctx_reg post2 r)
    /\ (forall c, m.(csr_nameable) c = true ->
          ctx_csr post1 c = ctx_csr post2 c)
    /\ ctx_pending post1 = ctx_pending post2.

(* -------------------------------------------------------------------------
   The partition switch: the conjunction of its per-component write
   obligations, and nothing else.
   ------------------------------------------------------------------------- *)

Definition Switch (m : Machine) : Step m := fun succ pre post =>
  (forall r, Nat.ltb r register_count = true ->
     ctx_reg post r = ctx_reg succ r)
  /\ (forall c, m.(csr_nameable) c = true ->
        ctx_csr post c =
          (if m.(csr_zeroized) c then m.(zero_word) else ctx_csr succ c))
  /\ ctx_pending post = pending_written m succ.

(* R-07-037b's intra-slot step: the same register swap and the same restore
   of the restorable CSRs, with the zeroized class left where the omitted
   pass leaves it (reading 7) and the pending arm R-07-037c fixes to the
   swap the switch performs, the field keeping both arms so the
   observability theorem still exhibits them. *)
Definition Rotation (m : Machine) : Step m := fun succ pre post =>
  (forall r, Nat.ltb r register_count = true ->
     ctx_reg post r = ctx_reg succ r)
  /\ (forall c, m.(csr_nameable) c = true -> m.(csr_zeroized) c = false ->
        ctx_csr post c = ctx_csr succ c)
  /\ (if m.(rotation_swaps_pending)
      then ctx_pending post = pending_written m succ
      else True).

(* =========================================================================
   T1 through T4: totality, and the residue it makes impossible.
   ========================================================================= *)

(* T1 (R-07-015, R-15-007i). *)
(*| discharges: R-07-015, R-15-007i |*)
Theorem restore_total_over_registers :
  forall m : Machine, RestoresRegisters m (Switch m).
Proof.
  intros m succ pre post [Hreg _]. exact Hreg.
Qed.

(* T2 (R-07-015, R-15-001b, isa-profile.md section 5.1, R-07-014a,
   R-07-014c). *)
(*| discharges: R-07-015 |*)
Theorem restore_total_over_nameable_csrs :
  forall m : Machine, RestoresNameableCsrs m (Switch m).
Proof.
  intros m succ pre post [_ [Hcsr _]]. exact Hcsr.
Qed.

(* T3 (R-07-015's criterion). The file's load-bearing theorem: over the
   registers the architecture carries and the CSRs a partition can name, no
   predecessor value reaches the successor's view. *)
(*| discharges: R-07-015 |*)
Theorem no_residue : forall m : Machine, NoResidue m (Switch m).
Proof.
  intros m succ pre1 post1 pre2 post2 [Hr1 [Hc1 Hp1]] [Hr2 [Hc2 Hp2]].
  split; [ | split ].
  - intros r Hr. rewrite (Hr1 r Hr), (Hr2 r Hr). reflexivity.
  - intros c Hc. rewrite (Hc1 c Hc), (Hc2 c Hc). reflexivity.
  - rewrite Hp1, Hp2. reflexivity.
Qed.

(* T4 (R-07-044), a corollary of T3 read at its third component: the
   pending state the successor observes is fixed by the successor context,
   whatever the predecessor held. *)
(*| discharges: R-07-044 |*)
Theorem pending_carries_nothing_across :
  forall (m : Machine) (succ : Context m) (pre1 post1 pre2 post2 : State m),
    Switch m succ pre1 post1 -> Switch m succ pre2 post2 ->
    ctx_pending post1 = ctx_pending post2.
Proof.
  intros m succ pre1 post1 pre2 post2 H1 H2.
  destruct (no_residue m succ pre1 post1 pre2 post2 H1 H2) as [_ [_ Hp]].
  exact Hp.
Qed.

(* =========================================================================
   T5: R-15-220's arity, and the drain counted once.
   ========================================================================= *)

Definition switch_cost (m : Machine) : nat :=
  m.(fence_t_cost) + m.(vmclear_cost) + m.(opp_relock_cost).

(* The reading R-15-220 refuses: the fence and the store-buffer drain
   listed as separate terms. Written in that left-associated order so the
   four terms are visible and the identity below is the register's own
   sentence rather than a rearrangement. *)
Definition four_term_cost (m : Machine) : nat :=
  m.(fence_t_cost) + m.(vmclear_cost) + m.(opp_relock_cost) + m.(drain_cost).

Definition SumsExactlyTheThreeTerms (f : Machine -> nat) : Prop :=
  forall m : Machine,
    f m = m.(fence_t_cost) + m.(vmclear_cost) + m.(opp_relock_cost).

(* T5 (R-15-220): three terms, not four. *)
(*| discharges: R-15-220 |*)
Theorem cost_is_three_terms : SumsExactlyTheThreeTerms switch_cost.
Proof. intros m. reflexivity. Qed.

Lemma lt_add_pos : forall n k : nat, 0 < k -> n < n + k.
Proof.
  intros n k H. induction n as [ | n IH ].
  - exact H.
  - simpl. apply le_n_S. exact IH.
Qed.

(* T5a (R-15-220's criterion): listing the fence and the drain separately
   inflates every switch bound feeding section 11 by a full drain. *)
(*| discharges: R-15-220 |*)
Theorem drain_counted_once :
  forall m : Machine, 0 < m.(drain_cost) -> switch_cost m < four_term_cost m.
Proof.
  intros m H. apply lt_add_pos. exact H.
Qed.

(* =========================================================================
   T6 and T7: R-07-037b's intra-slot rotation, in the cost model and then
   in the state model. Reading 9 says why the two do not meet in the middle
   and what does join them.
   ========================================================================= *)

(* Exactly the four names R-07-037b's own sentence uses for what a switch
   does: it "swaps register and partition context and omits fence.t, eager
   zeroize, and OPP relock". This is a list of switch actions and not an
   object inventory (gap e). *)
Inductive Action : Type := Restore | FenceT | Vmclear | OppRelock.

Definition switch_performs (a : Action) : bool :=
  match a with
  | Restore => true | FenceT => true | Vmclear => true | OppRelock => true
  end.

Definition rotation_performs (a : Action) : bool :=
  match a with
  | Restore => true | FenceT => false | Vmclear => false | OppRelock => false
  end.

Definition PerformsNoMoreThan (p q : Action -> bool) : Prop :=
  forall a : Action, p a = true -> q a = true.

Definition PerformsStrictlyFewer (p q : Action -> bool) : Prop :=
  PerformsNoMoreThan p q /\ (exists a : Action, q a = true /\ p a = false).

Definition OmitsTheThreeConstants (p : Action -> bool) : Prop :=
  p FenceT = false /\ p Vmclear = false /\ p OppRelock = false.

(* R-15-220's three constants and what a step pays of them. The restore is
   absent from this sum because R-15-220 names three terms and the restore
   is not one of the three; R-15-220a puts the restore and the pending swap
   beside them in one context term, so this sum stays the platform three. *)
Definition constants_paid (m : Machine) (p : Action -> bool) : nat :=
  (if p FenceT then m.(fence_t_cost) else 0)
  + (if p Vmclear then m.(vmclear_cost) else 0)
  + (if p OppRelock then m.(opp_relock_cost) else 0).

Definition PaysNoneOfTheThree (p : Action -> bool) : Prop :=
  forall m : Machine, constants_paid m p = 0.

(* T6 (R-07-037b, R-11-006b). *)
(*| discharges: R-07-037b |*)
Theorem rotation_is_a_strict_subset :
  PerformsStrictlyFewer rotation_performs switch_performs.
Proof.
  split.
  - intros a _. destruct a; reflexivity.
  - exists FenceT. split; reflexivity.
Qed.

(* T6b (R-07-037b's own three omissions). *)
(*| discharges: R-07-037b |*)
Theorem rotation_omits_the_three_constants :
  OmitsTheThreeConstants rotation_performs.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* T6c: what the omission is worth. The switch pays R-15-220's three
   constants and the rotation pays none of them, which is R-07-037b's "all
   three return at the slot boundary" as arithmetic. *)
(*| discharges: R-15-220, R-07-037b |*)
Theorem switch_pays_all_three :
  forall m : Machine, constants_paid m switch_performs = switch_cost m.
Proof. intros m. reflexivity. Qed.

(*| discharges: R-07-037b |*)
Theorem rotation_pays_none_of_the_three :
  PaysNoneOfTheThree rotation_performs.
Proof. intros m. reflexivity. Qed.

(* T7 (R-07-037b, "swaps register and partition context"). The
   label-internal case inherits the register restore whole and the CSR
   restore over the restorable class, which is what a step omitting
   R-07-014c's pass can meet (reading 7). *)
(*| discharges: R-07-037b |*)
Theorem rotation_restore_is_total :
  forall m : Machine,
    RestoresRegisters m (Rotation m)
    /\ RestoresRestorableCsrs m (Rotation m).
Proof.
  intros m. split.
  - intros succ pre post [Hreg _]. exact Hreg.
  - intros succ pre post [_ [Hcsr _]]. exact Hcsr.
Qed.

(* The one bridge between the cost model and the state model (reading 9):
   whatever meets the switch's obligations meets the rotation's, so the
   rotation's obligations are the weaker set. The action inclusion of T6
   and this relational inclusion run in opposite directions, which is
   correct rather than a discrepancy: a step that performs fewer actions
   constrains fewer components. *)
(*| discharges: R-07-037b |*)
Theorem switch_discharges_every_rotation_obligation :
  forall (m : Machine) (succ : Context m) (pre post : State m),
    Switch m succ pre post -> Rotation m succ pre post.
Proof.
  intros m succ pre post [Hreg [Hcsr Hp]]. split; [ | split ].
  - exact Hreg.
  - intros c Hn Hz. rewrite (Hcsr c Hn), Hz. reflexivity.
  - destruct m.(rotation_swaps_pending); [ exact Hp | exact I ].
Qed.

(* =========================================================================
   Inhabitation (R-05-165's unsatisfiable-premise and uninhabited-domain
   modes). The specification is satisfiable at every machine, so no theorem
   above is proved from an empty antecedent at any instantiation.
   ========================================================================= *)

Definition canonical_post (m : Machine) (succ : Context m) : State m :=
  Build_Context m
    (ctx_reg succ)
    (fun c => if m.(csr_zeroized) c then m.(zero_word) else ctx_csr succ c)
    (pending_written m succ).

(* Discharge the register obligation shared by the canonical state constructions. *)
Local Ltac split_closing_the_registers :=
  split; [ intros r _; reflexivity | split ].

Theorem switch_is_satisfiable :
  forall (m : Machine) (succ : Context m) (pre : State m),
    Switch m succ pre (canonical_post m succ).
Proof.
  intros m succ pre. split_closing_the_registers.
  - intros c _. reflexivity.
  - reflexivity.
Qed.

Theorem rotation_is_satisfiable :
  forall (m : Machine) (succ : Context m) (pre : State m),
    Rotation m succ pre (canonical_post m succ).
Proof.
  intros m succ pre.
  apply switch_discharges_every_rotation_obligation.
  apply switch_is_satisfiable.
Qed.

(* =========================================================================
   Machines whose every domain is inhabited, for the concrete half of
   R-05-165. Two CSRs exercise both of section 5.1's dispositions: one is
   restored and one is zeroized. The cost figures and the static partition
   are arbitrary witness values and carry no composition claim (gap j).
   ========================================================================= *)

Definition demo (swapped rot_pending names : bool) : Machine := {|
  Csr := bool;
  csr_nameable := fun _ => names;
  csr_zeroized := fun c => c;
  Word := bool;
  zero_word := false;
  Pending := bool;
  pending_swapped := swapped;
  pending_partition := fun p => negb p;
  rotation_swaps_pending := rot_pending;
  fence_t_cost := 7;
  vmclear_cost := 5;
  opp_relock_cost := 3;
  drain_cost := 2
|}.

(* R-07-044's swapped arm, R-07-037b's pending question answered both ways,
   and a machine naming no CSR at all, which reading 3 refers to. *)
Definition demo_rotation_swaps : Machine := demo true true true.
Definition demo_rotation_keeps : Machine := demo true false true.
Definition demo_partitions_pending : Machine := demo false true true.
Definition demo_names_nothing : Machine := demo true true false.

Definition demo_succ : Context demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun _ => true) true.

Definition demo_post : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun c => if c then false else true) true.

Theorem demo_switch_holds :
  Switch demo_rotation_swaps demo_succ demo_succ demo_post.
Proof.
  split_closing_the_registers.
  - intros c _. destruct c; reflexivity.
  - reflexivity.
Qed.

(* T4b (R-07-044's disjunction, gap g): the two arms are not two spellings
   of one function, so covering both is not idle. *)
Definition demo_succ_partitioned : Context demo_partitions_pending :=
  Build_Context demo_partitions_pending
    (fun _ => (true, true)) (fun _ => true) true.

Theorem the_two_pending_arms_differ :
  pending_written demo_rotation_swaps demo_succ = ctx_pending demo_succ
  /\ pending_written demo_partitions_pending demo_succ_partitioned
     <> ctx_pending demo_succ_partitioned.
Proof.
  split.
  - reflexivity.
  - intro H. cbv in H. discriminate H.
Qed.

(* Reading 3, made checkable. Where a composition names no CSR, the CSR
   half of totality is discharged by a step that does nothing at all, while
   the register half, whose domain is the literal R-15-007i fixes, refuses
   the same step. This is R-07-015's own "a partition can name" and not a
   defect of the statement; it is why the two halves are stated over
   different kinds of domain. *)
Theorem csr_totality_is_vacuous_where_nothing_is_nameable :
  RestoresNameableCsrs demo_names_nothing (fun _ _ _ => True)
  /\ ~ RestoresRegisters demo_names_nothing (fun _ _ _ => True).
Proof.
  split.
  - intros succ pre post _ c Hc. discriminate Hc.
  - intros Htotal.
    specialize (Htotal
      (Build_Context demo_names_nothing
         (fun _ => (true, true)) (fun _ => true) true)
      (Build_Context demo_names_nothing
         (fun _ => (true, true)) (fun _ => true) true)
      (Build_Context demo_names_nothing
         (fun _ => (false, false)) (fun _ => true) true)
      I 0 eq_refl).
    cbv in Htotal. discriminate Htotal.
Qed.

(* =========================================================================
   Refutation witnesses (R-05-166). Each is an alternative construction
   that fails an obligation the specification discharges, so the obligation
   excludes something and the positive theorem above is not a change
   detector over this file's own definitions.
   ========================================================================= *)

(* A switch that restores only the low registers. R-07-015's criterion, "a
   register outside the restore set is a proof failure". *)
Definition truncated_switch (m : Machine) (bound : nat) : Step m :=
  fun succ pre post =>
    (forall r, Nat.ltb r bound = true -> ctx_reg post r = ctx_reg succ r)
    /\ (forall c, m.(csr_nameable) c = true ->
          ctx_csr post c =
            (if m.(csr_zeroized) c then m.(zero_word) else ctx_csr succ c))
    /\ ctx_pending post = pending_written m succ.

Definition truncated_reg (r : nat) : bool * bool :=
  if Nat.ltb r 16 then (true, true) else (false, false).

Definition truncated_post : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps truncated_reg
    (fun c => if c then false else true) true.

Theorem truncated_switch_refutes_register_totality :
  truncated_switch demo_rotation_swaps 16 demo_succ demo_succ truncated_post
  /\ ~ RestoresRegisters demo_rotation_swaps
         (truncated_switch demo_rotation_swaps 16).
Proof.
  assert (Hstep : truncated_switch demo_rotation_swaps 16
                    demo_succ demo_succ truncated_post).
  { split; [ | split ].
    - intros r Hr. change (ctx_reg truncated_post r) with (truncated_reg r).
      unfold truncated_reg. rewrite Hr. reflexivity.
    - intros c _. destruct c; reflexivity.
    - reflexivity. }
  split; [ exact Hstep | ].
  intros Htotal.
  specialize (Htotal demo_succ demo_succ truncated_post Hstep 20 eq_refl).
  cbv in Htotal. discriminate Htotal.
Qed.

(* A switch that restores each register's 64 data bits and drops its
   validity tag. R-15-007i's merged file is 64+1 bits, so the tag is inside
   the restore's domain and an integer-only restore is refused. *)
Definition tag_dropping_switch (m : Machine) : Step m :=
  fun succ pre post =>
    (forall r, Nat.ltb r register_count = true ->
       fst (ctx_reg post r) = fst (ctx_reg succ r))
    /\ (forall c, m.(csr_nameable) c = true ->
          ctx_csr post c =
            (if m.(csr_zeroized) c then m.(zero_word) else ctx_csr succ c))
    /\ ctx_pending post = pending_written m succ.

Definition tag_dropped_post : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, false)) (fun c => if c then false else true) true.

Theorem tag_dropping_switch_refutes_register_totality :
  tag_dropping_switch demo_rotation_swaps demo_succ demo_succ tag_dropped_post
  /\ ~ RestoresRegisters demo_rotation_swaps
         (tag_dropping_switch demo_rotation_swaps).
Proof.
  assert (Hstep : tag_dropping_switch demo_rotation_swaps
                    demo_succ demo_succ tag_dropped_post).
  { split_closing_the_registers.
    - intros c _. destruct c; reflexivity.
    - reflexivity. }
  split; [ exact Hstep | ].
  intros Htotal.
  specialize (Htotal demo_succ demo_succ tag_dropped_post Hstep 0 eq_refl).
  cbv in Htotal. discriminate Htotal.
Qed.

(* A switch that leaves one nameable CSR unconstrained. R-07-015's totality
   is over the whole nameable bank, so exempting a single row refutes it. *)
Definition partial_switch (m : Machine) (exempt : m.(Csr) -> bool) : Step m :=
  fun succ pre post =>
    (forall r, Nat.ltb r register_count = true ->
       ctx_reg post r = ctx_reg succ r)
    /\ (forall c, m.(csr_nameable) c = true -> exempt c = false ->
          ctx_csr post c =
            (if m.(csr_zeroized) c then m.(zero_word) else ctx_csr succ c))
    /\ ctx_pending post = pending_written m succ.

Definition partial_post : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun _ => false) true.

Theorem partial_switch_refutes_csr_totality :
  partial_switch demo_rotation_swaps negb demo_succ demo_succ partial_post
  /\ ~ RestoresNameableCsrs demo_rotation_swaps
         (partial_switch demo_rotation_swaps negb).
Proof.
  assert (Hstep : partial_switch demo_rotation_swaps negb
                    demo_succ demo_succ partial_post).
  { split_closing_the_registers.
    - intros c _ Hex. destruct c; [ reflexivity | discriminate Hex ].
    - reflexivity. }
  split; [ exact Hstep | ].
  intros Htotal.
  specialize (Htotal demo_succ demo_succ partial_post Hstep false eq_refl).
  cbv in Htotal. discriminate Htotal.
Qed.

(* A switch that carries one predecessor CSR across the boundary. Every
   component is pinned, so this is a complete and deterministic
   specification rather than an underspecified one, and what refutes
   NoResidue of it is the carried value itself: at leak = fun _ => false
   the same construction satisfies NoResidue, which is
   residue_needs_the_leak below. *)
Definition residue_switch (m : Machine) (leak : m.(Csr) -> bool) : Step m :=
  fun succ pre post =>
    (forall r, Nat.ltb r register_count = true ->
       ctx_reg post r = ctx_reg succ r)
    /\ (forall c, m.(csr_nameable) c = true ->
          ctx_csr post c =
            (if leak c then ctx_csr pre c
             else if m.(csr_zeroized) c then m.(zero_word)
             else ctx_csr succ c))
    /\ ctx_pending post = pending_written m succ.

Definition residue_pre_low : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun _ => false) true.

Definition residue_pre_high : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun _ => true) true.

Definition residue_post_low : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun _ => false) true.

Definition residue_post_high : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun c => if c then false else true) true.

Theorem residue_switch_refutes_no_residue :
  residue_switch demo_rotation_swaps negb
    demo_succ residue_pre_low residue_post_low
  /\ residue_switch demo_rotation_swaps negb
       demo_succ residue_pre_high residue_post_high
  /\ ~ NoResidue demo_rotation_swaps (residue_switch demo_rotation_swaps negb).
Proof.
  assert (Hlow : residue_switch demo_rotation_swaps negb
                   demo_succ residue_pre_low residue_post_low).
  { split_closing_the_registers.
    - intros c _. destruct c; reflexivity.
    - reflexivity. }
  assert (Hhigh : residue_switch demo_rotation_swaps negb
                    demo_succ residue_pre_high residue_post_high).
  { split_closing_the_registers.
    - intros c _. destruct c; reflexivity.
    - reflexivity. }
  split; [ exact Hlow | ]. split; [ exact Hhigh | ].
  intros Hno.
  destruct (Hno demo_succ residue_pre_low residue_post_low
                residue_pre_high residue_post_high Hlow Hhigh) as [_ [Hcsr _]].
  specialize (Hcsr false eq_refl). cbv in Hcsr. discriminate Hcsr.
Qed.

(* The carried value is what refutes it, not the shape of the construction:
   with nothing leaked the leak test reduces away and what is left is the
   switch itself, so T3 proves this relation residue-free unchanged. *)
Theorem residue_needs_the_leak :
  forall m : Machine, NoResidue m (residue_switch m (fun _ => false)).
Proof. exact no_residue. Qed.

(* A rotation that performs fence.t. R-07-037b omits all three constants,
   so a step that pays one of them is not that rotation. *)
Definition heavy_rotation (a : Action) : bool :=
  match a with
  | Restore => true | FenceT => true | Vmclear => false | OppRelock => false
  end.

Theorem heavy_rotation_refutes_the_omission :
  ~ OmitsTheThreeConstants heavy_rotation.
Proof. intros [H _]. discriminate H. Qed.

Theorem heavy_rotation_pays_a_constant : ~ PaysNoneOfTheThree heavy_rotation.
Proof.
  intros H. specialize (H demo_rotation_swaps). cbv in H. discriminate H.
Qed.

(* The containment conjunct of T6 excludes something: a step performing
   what the switch performs is not inside a step that omits three of them,
   so PerformsNoMoreThan is not a property everything has. *)
Theorem containment_conjunct_excludes_a_superset :
  ~ PerformsNoMoreThan switch_performs rotation_performs.
Proof. intros H. specialize (H FenceT eq_refl). discriminate H. Qed.

(* And the strictness conjunct excludes something: a rotation that performs
   everything the switch performs is not a strict subset of it. *)
Theorem full_rotation_refutes_strictness :
  ~ PerformsStrictlyFewer switch_performs switch_performs.
Proof.
  intros [_ [a [_ Hfalse]]]. destruct a; discriminate Hfalse.
Qed.

(* The four-term reading R-15-220 refuses is refutable rather than merely
   different: it is not a sum of the three terms. *)
Theorem four_term_reading_is_refuted :
  ~ SumsExactlyTheThreeTerms four_term_cost.
Proof.
  intros H. specialize (H demo_rotation_swaps). cbv in H. discriminate H.
Qed.

(* =========================================================================
   Gap i, made checkable rather than asserted. R-07-037b's rotation omits
   R-07-014c's pass, and section 5.1 makes the zeroized class zeroize and
   not save, so nothing is saved for the rotation to restore and nothing
   clears it: a same-label group member begins its reaction with the
   previous member's zeroized-class state. The rotation therefore does not
   discharge R-07-015's totality, and R-07-037b's ground for the omission,
   that every flow the three constants cut is internal to one label,
   decides confidentiality and not this.
   ========================================================================= *)

Definition unzeroed_post : State demo_rotation_swaps :=
  Build_Context demo_rotation_swaps
    (fun _ => (true, true)) (fun _ => true) true.

Theorem rotation_omits_the_zeroize_at_state_level :
  Rotation demo_rotation_swaps demo_succ demo_succ unzeroed_post
  /\ ~ Switch demo_rotation_swaps demo_succ demo_succ unzeroed_post
  /\ ~ RestoresNameableCsrs demo_rotation_swaps (Rotation demo_rotation_swaps).
Proof.
  assert (Hrot : Rotation demo_rotation_swaps demo_succ demo_succ unzeroed_post).
  { split_closing_the_registers.
    - intros c _ Hz. destruct c; [ discriminate Hz | reflexivity ].
    - reflexivity. }
  split; [ exact Hrot | ]. split.
  - intros [_ [Hcsr _]]. specialize (Hcsr true eq_refl).
    cbv in Hcsr. discriminate Hcsr.
  - intros Htotal.
    specialize (Htotal demo_succ demo_succ unzeroed_post Hrot true eq_refl).
    cbv in Htotal. discriminate Htotal.
Qed.

(* =========================================================================
   Gap h, made checkable the same way. R-07-037b does not say what the
   intra-slot rotation does with R-07-044's pending bits, and the two
   readings are not observationally equal: on the swapping arm the rotation
   carries nothing across in that component, and on the other arm two
   rotations from one successor context disagree on it.
   ========================================================================= *)

(*| discharges: R-07-037c |*)
Theorem rotation_pending_carries_nothing_on_the_swapping_arm :
  forall (m : Machine) (succ : Context m) (pre1 post1 pre2 post2 : State m),
    m.(rotation_swaps_pending) = true ->
    Rotation m succ pre1 post1 -> Rotation m succ pre2 post2 ->
    ctx_pending post1 = ctx_pending post2.
Proof.
  intros m succ pre1 post1 pre2 post2 Harm [_ [_ Hp1]] [_ [_ Hp2]].
  rewrite Harm in Hp1, Hp2. simpl in Hp1, Hp2.
  rewrite Hp1, Hp2. reflexivity.
Qed.

Definition rot_succ : Context demo_rotation_keeps :=
  Build_Context demo_rotation_keeps
    (fun _ => (true, true)) (fun _ => true) true.

Definition rot_post_low : State demo_rotation_keeps :=
  Build_Context demo_rotation_keeps
    (fun _ => (true, true)) (fun _ => true) false.

Definition rot_post_high : State demo_rotation_keeps :=
  Build_Context demo_rotation_keeps
    (fun _ => (true, true)) (fun _ => true) true.

Theorem rotation_pending_arm_is_observable :
  Rotation demo_rotation_keeps rot_succ rot_succ rot_post_low
  /\ Rotation demo_rotation_keeps rot_succ rot_succ rot_post_high
  /\ ctx_pending rot_post_low <> ctx_pending rot_post_high.
Proof.
  assert (Hlow : Rotation demo_rotation_keeps rot_succ rot_succ rot_post_low).
  { split_closing_the_registers.
    - intros c _ Hz. destruct c; [ discriminate Hz | reflexivity ].
    - exact I. }
  assert (Hhigh : Rotation demo_rotation_keeps rot_succ rot_succ rot_post_high).
  { split_closing_the_registers.
    - intros c _ Hz. destruct c; [ discriminate Hz | reflexivity ].
    - exact I. }
  split; [ exact Hlow | ]. split; [ exact Hhigh | ].
  intro H. cbv in H. discriminate H.
Qed.

(* -------------------------------------------------------------------------
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at it.
   The prover decides inhabitation by type-checking the ascription, so
   `run.py proofs` reads a name rather than approximating a type judgement.
   A record this file reaches through a Require is witnessed in the file that
   declares it.
   ------------------------------------------------------------------------- *)

Definition witness_Context : Context demo_rotation_swaps := demo_succ.
Definition witness_Machine : Machine := demo_rotation_swaps.

(* R-05-164: `run.py proofs` audits the complete native inventory. *)
