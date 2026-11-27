(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   CombinedReduction.v

   R-17-058d combined fault-and-probing reduction theorem over
   [ProbingModel.v](ProbingModel.v)'s finite-mass probing semantics and
   [protected-sequence-fault-model.md](../docs/hardware/protected-sequence-fault-model.md)'s
   single-fault-per-activation transition relation (R-17-058d, R-16-008f,
   R-15-053a, R-05-004a, R-17-058a, R-17-058b, R-17-058c, R-05-163,
   R-05-164, R-05-165, R-05-166).

   What this file formalizes and proves:
   1. Single-fault-per-activation transition relation (`FaultStep`,
      `FaultDerivation`) with budget `b <= 1` (`FaultFree` vs single in-region
      `SingleFault`), structurally excluding multi-fault derivations at budget
      `0` and out-of-region faults (`R-16-008f`).
   2. Share-domain-separated `(d + 1)`-share probing security (`ShareLocalized`)
      under any `LocalExpansion` (`ex_stable`, `ex_glitch`, `ex_transition`,
      `ex_robust`) at unreduced probing order `d` (`R-15-053a`, `R-05-004a`).
   3. The combined reduction theorem (`combined_single_fault_reduction`): for
      every conforming `(d + 1)`-share masked activation under the
      single-fault-per-activation hypothesis and every admissible `d`-probe
      set, either (a) the fault is effective and detected with acceptance token
      withheld (`EffectiveDetectedArm`, `R-16-008f`), or (b) the fault is
      share-confined to at most one share's computation and the simultaneous
      `(fault, d-probe)` observation distribution remains secret-independent at
      unreduced probing order `d` (`ShareConfinedProbingArm`, `R-15-053a`).
   4. Parametric `(d + 1)`-share positive witness (`instantiated_masked_activation`)
      with fine-grained share-local checking satisfying all hypotheses for
      arbitrary `d`, plus closed `witness_*` inhabitants for every record
      (`R-05-166`).
   5. Three refuting constructions (`R-05-165`, `R-05-166`, `R-17-058b`,
      `R-17-058c`): (i) cross-share and two-fault injections break unreduced
      `d`-probing and detection; (ii) missing token withholding on an effective
      fault violates the detection arm; (iii) a weakened `(d - 1)`-order claim
      fails the unreduced-order predicate.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-163 R-05-164 R-05-165 R-05-166 R-15-053a R-16-008f R-17-058a
      R-17-058b R-17-058c R-17-058d
   SHA256: 587fb0fd1efc1416b390a8da90679f38dcfac9057e37187cc37a5dbfb8cdd501
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Arith Lia Bool.
Require ProofSupport ProbingModel.
Import ProbingModel.

(* =========================================================================
   1. Single-fault-per-activation execution model (R-16-008f).
   ========================================================================= *)

Inductive FaultAction (F : Type) : Type :=
  | fault_skip : FaultAction F
  | fault_corrupt : F -> FaultAction F.

Arguments fault_skip {F}.
Arguments fault_corrupt {F} _.

Record FaultStepSystem (S F : Type) : Type := {
  fs_in_region : S -> bool;
  fs_step : S -> S;
  fs_fault : S -> FaultAction F -> S
}.

Arguments fs_in_region {S F} _ _.
Arguments fs_step {S F} _ _.
Arguments fs_fault {S F} _ _ _.

Definition witness_FaultStepSystem : FaultStepSystem nat bool := {|
  fs_in_region := fun s => Nat.leb s 1;
  fs_step := S;
  fs_fault := fun s _ => S s
|}.

Inductive FaultStep {S F : Type} (sys : FaultStepSystem S F)
    : (S * nat) -> option (FaultAction F) -> (S * nat) -> Prop :=
  | fs_step_rule : forall (s : S) (b : nat),
      FaultStep sys (s, b) None (fs_step sys s, b)
  | fs_fault_rule : forall (s : S) (act : FaultAction F),
      fs_in_region sys s = true ->
      FaultStep sys (s, 1) (Some act) (fs_fault sys s act, 0).

Inductive FaultDerivation {S F : Type} (sys : FaultStepSystem S F)
    : (S * nat) -> list (option (FaultAction F)) -> (S * nat) -> Prop :=
  | fd_nil : forall cfg, FaultDerivation sys cfg nil cfg
  | fd_cons : forall cfg1 opt cfg2 tr cfg3,
      FaultStep sys cfg1 opt cfg2 ->
      FaultDerivation sys cfg2 tr cfg3 ->
      FaultDerivation sys cfg1 (opt :: tr) cfg3.

Fixpoint fault_count {F : Type} (tr : list (option (FaultAction F))) : nat :=
  match tr with
  | nil => 0
  | None :: r => fault_count r
  | Some _ :: r => S (fault_count r)
  end.

Lemma fault_step_budget_conservation :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s s' : S) (b b' : nat) (opt : option (FaultAction F)),
    FaultStep sys (s, b) opt (s', b') ->
    b <= 1 ->
    b' <= 1 /\
    (match opt with None => 0 | Some _ => 1 end) + b' = b.
Proof.
  intros S F sys s s' b b' opt Hstep Hb.
  inversion Hstep; subst; lia.
Qed.

Lemma zero_budget_permits_no_fault_cfg :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (cfg0 cfg1 : S * nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys cfg0 tr cfg1 ->
    snd cfg0 = 0 ->
    snd cfg1 = 0 /\ fault_count tr = 0.
Proof.
  intros S F sys cfg0 cfg1 tr Hder.
  induction Hder as [cfg | cfg1 opt cfg2 rest cfg3 Hstep Hrest IH]; intros Hb0.
  - split; [exact Hb0 | reflexivity].
  - inversion Hstep; subst; simpl in *; [|discriminate Hb0].
    exact (IH Hb0).
Qed.

(*| discharges: R-16-008f |*)
Theorem zero_budget_permits_no_fault :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s s' : S) (b' : nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys (s, 0) tr (s', b') ->
    b' = 0 /\ fault_count tr = 0.
Proof.
  intros S F sys s s' b' tr Hder.
  exact (zero_budget_permits_no_fault_cfg sys (s, 0) (s', b') tr Hder eq_refl).
Qed.

Lemma single_fault_budget_conservation_cfg :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (cfg0 cfg1 : S * nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys cfg0 tr cfg1 ->
    snd cfg0 <= 1 ->
    snd cfg1 <= 1 /\ fault_count tr + snd cfg1 = snd cfg0.
Proof.
  intros S F sys cfg0 cfg1 tr Hder.
  induction Hder as [cfg | cfg1 opt cfg2 rest cfg3 Hstep Hrest IH]; intros Hb0.
  - split; [exact Hb0 | reflexivity].
  - destruct cfg1 as [sa ba]. destruct cfg2 as [sb bb]. simpl in Hb0.
    destruct (fault_step_budget_conservation sys sa sb ba bb opt Hstep Hb0)
      as [Hbb Hstep_cons].
    destruct (IH Hbb) as [Hb1 Hrest_cons].
    split; [exact Hb1|].
    destruct opt as [act|]; simpl in *; lia.
Qed.

(*| discharges: R-16-008f |*)
Theorem single_fault_budget_conservation :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s s' : S) (b b' : nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys (s, b) tr (s', b') ->
    b <= 1 ->
    b' <= 1 /\ fault_count tr + b' = b.
Proof.
  intros S F sys s s' b b' tr Hder Hb.
  exact (single_fault_budget_conservation_cfg sys (s, b) (s', b') tr Hder Hb).
Qed.

(*| discharges: R-16-008f |*)
Theorem at_most_one_fault_per_activation :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s s' : S) (b' : nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys (s, 1) tr (s', b') ->
    fault_count tr <= 1.
Proof.
  intros S F sys s s' b' tr Hder.
  destruct (single_fault_budget_conservation sys s s' 1 b' tr Hder (le_n 1))
    as [_ Hcons].
  lia.
Qed.

(*| discharges: R-16-008f, R-17-058b |*)
Theorem two_faults_have_no_derivation :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s s' : S) (b' : nat) (tr : list (option (FaultAction F))),
    2 <= fault_count tr ->
    ~ FaultDerivation sys (s, 1) tr (s', b').
Proof.
  intros S F sys s s' b' tr Hge Hder.
  pose proof (at_most_one_fault_per_activation sys s s' b' tr Hder) as Hle.
  lia.
Qed.

(*| discharges: R-16-008f |*)
Theorem out_of_region_fault_excluded :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s : S) (b : nat) (act : FaultAction F) (cfg' : S * nat),
    fs_in_region sys s = false ->
    ~ FaultStep sys (s, b) (Some act) cfg'.
Proof.
  intros S F sys s b act cfg' Hout Hstep.
  inversion Hstep; subst. rewrite Hout in *. discriminate.
Qed.

Inductive ActivationFaultClass (F : Type) : Type :=
  | FaultFree : ActivationFaultClass F
  | SingleFault : nat -> FaultAction F -> ActivationFaultClass F.

Arguments FaultFree {F}.
Arguments SingleFault {F} _ _.

Fixpoint classify_trace_from {F : Type} (idx : nat)
    (tr : list (option (FaultAction F))) : ActivationFaultClass F :=
  match tr with
  | nil => FaultFree
  | None :: r => classify_trace_from (S idx) r
  | Some act :: _ => SingleFault idx act
  end.

Definition classify_trace {F : Type}
    (tr : list (option (FaultAction F))) : ActivationFaultClass F :=
  classify_trace_from 0 tr.

Lemma classify_trace_from_fault_free :
  forall {F : Type} (idx : nat) (tr : list (option (FaultAction F))),
    fault_count tr = 0 ->
    classify_trace_from idx tr = FaultFree.
Proof.
  intros F idx tr. revert idx.
  induction tr as [|[act|] r IH]; intros idx Hfc; simpl in *.
  - reflexivity.
  - discriminate Hfc.
  - exact (IH (S idx) Hfc).
Qed.

Lemma classify_trace_from_single_fault_cfg :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (cfg0 cfg1 : S * nat) (idx : nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys cfg0 tr cfg1 ->
    snd cfg0 <= 1 ->
    fault_count tr = 1 ->
    exists (k : nat) (act : FaultAction F),
      classify_trace_from idx tr = SingleFault k act /\
      idx <= k /\
      k - idx < length tr /\
      nth_error tr (k - idx) = Some (Some act).
Proof.
  intros St F sys cfg0 cfg1 idx tr Hder.
  revert idx.
  induction Hder as [cfg | cfg1 opt cfg2 rest cfg3 Hstep Hrest IH];
    intros idx Hb0 Hfc.
  - simpl in Hfc. discriminate Hfc.
  - destruct cfg1 as [sa ba]. destruct cfg2 as [sb bb]. simpl in Hb0.
    destruct opt as [act|].
    + exists idx, act. simpl.
      rewrite Nat.sub_diag. simpl.
      split; [reflexivity|]. split; [lia|]. split; [lia | reflexivity].
    + simpl in Hfc.
      destruct (fault_step_budget_conservation sys sa sb ba bb None Hstep Hb0)
        as [Hbb _].
      destruct (IH (S idx) Hbb Hfc)
        as [k [act [Hcl [Hge [Hlen Hnth]]]]].
      exists k, act. simpl. split; [exact Hcl|]. split; [lia|].
      assert (Hsub : k - idx = S (k - S idx)) by lia.
      rewrite Hsub. simpl. split; [lia | exact Hnth].
Qed.

Lemma classify_trace_from_single_fault :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s s' : S) (b b' idx : nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys (s, b) tr (s', b') ->
    b <= 1 ->
    fault_count tr = 1 ->
    exists (k : nat) (act : FaultAction F),
      classify_trace_from idx tr = SingleFault k act /\
      idx <= k /\
      k - idx < length tr /\
      nth_error tr (k - idx) = Some (Some act).
Proof.
  intros S F sys s s' b b' idx tr Hder Hb Hfc.
  exact (classify_trace_from_single_fault_cfg sys (s, b) (s', b') idx tr Hder Hb Hfc).
Qed.

(*| discharges: R-16-008f |*)
Theorem activation_derivation_partition :
  forall {S F : Type} (sys : FaultStepSystem S F)
         (s0 s_end : S) (b_end : nat) (tr : list (option (FaultAction F))),
    FaultDerivation sys (s0, 1) tr (s_end, b_end) ->
    (b_end = 1 /\ fault_count tr = 0 /\ classify_trace tr = FaultFree) \/
    (b_end = 0 /\ fault_count tr = 1 /\
     exists (idx : nat) (act : FaultAction F),
       classify_trace tr = SingleFault idx act /\
       idx < length tr /\
       nth_error tr idx = Some (Some act)).
Proof.
  intros S F sys s0 s_end b_end tr Hder.
  destruct (single_fault_budget_conservation sys s0 s_end 1 b_end tr Hder (le_n 1))
    as [Hb Hcons].
  destruct b_end as [|[|b_end]].
  - right. assert (Hfc : fault_count tr = 1) by lia.
    split; [reflexivity|]. split; [exact Hfc|].
    destruct (classify_trace_from_single_fault sys s0 s_end 1 0 0 tr Hder (le_n 1) Hfc)
      as [k [act [Hcl [_ [Hlen Hnth]]]]].
    rewrite Nat.sub_0_r in Hlen, Hnth.
    exists k, act. unfold classify_trace. repeat split; assumption.
  - left. assert (Hfc : fault_count tr = 0) by lia.
    split; [reflexivity|]. split; [exact Hfc|].
    unfold classify_trace. apply classify_trace_from_fault_free. exact Hfc.
  - lia.
Qed.

(* =========================================================================
   2. Share-localized (d + 1)-share probing security at unreduced order d
      (R-15-053a, R-05-004a).
   ========================================================================= *)

Definition ShareMaskTapes (m : Sharing) (Aux : Type) (aux_enum : list Aux)
    (d : nat) : Probability :=
  counting (list (Val m) * Aux) (list_prod (mask_tuples m d) aux_enum).

Lemma list_prod_nonempty :
  forall {A B : Type} (l1 : list A) (l2 : list B),
    l1 <> nil -> l2 <> nil -> list_prod l1 l2 <> nil.
Proof.
  intros A B [|a r1] [|b r2] H1 H2; try contradiction.
  unfold list_prod. simpl. discriminate.
Qed.

Theorem qualified_share_mask_tapes :
  forall (m : Sharing) (Aux : Type) (aux_enum : list Aux) (d : nat),
    aux_enum <> nil ->
    FiniteMassQualification (ShareMaskTapes m Aux aux_enum d).
Proof.
  intros m Aux aux_enum d Haux.
  unfold ShareMaskTapes. apply qualify_counting.
  apply list_prod_nonempty; [|exact Haux].
  intro E. destruct (mask_tuples_nonempty m d) as [xs Hxs].
  rewrite E in Hxs. contradiction.
Qed.

Definition mk_shared_experiment (m : Sharing) (Aux : Type) (aux_enum : list Aux)
    (d : nat) (c : Circuit) (ops : nat -> list (Val m) -> Val m)
    (in_fn : Val m -> list (Val m) * Aux -> nat -> nat -> Val m)
    (init_fn : Val m -> list (Val m) * Aux -> nat -> Val m)
    : Experiment := {|
  x_share := m;
  x_prob := ShareMaskTapes m Aux aux_enum d;
  x_circuit := c;
  x_ops := ops;
  x_secret := Val m;
  x_in := in_fn;
  x_init := init_fn;
  x_order := d
|}.

Record ShareLocalized (m : Sharing) (Aux : Type) (aux_enum : list Aux)
    (d : nat) (c : Circuit) (ops : nat -> list (Val m) -> Val m)
    (in_fn : Val m -> list (Val m) * Aux -> nat -> nat -> Val m)
    (init_fn : Val m -> list (Val m) * Aux -> nat -> Val m)
    (dom : nat -> nat) : Prop := {
  sl_wf : well_formed c = true;
  sl_dom_bound : forall w, w < wire_count c -> dom w < S d;
  sl_dom_gate : forall w,
    w < wire_count c ->
    match gate_at c w with
    | g_in _ => True
    | g_reg s => dom s = dom w
    | g_op _ args => all_of (fun a => Nat.eqb (dom a) (dom w)) args = true
    end;
  sl_in_dep : forall w i s1 s2 masks1 masks2 aux t,
    w < wire_count c ->
    gate_at c w = g_in i ->
    at_member (encode m s1 masks1) (dom w) (v_zero m) =
    at_member (encode m s2 masks2) (dom w) (v_zero m) ->
    in_fn s1 (masks1, aux) t i = in_fn s2 (masks2, aux) t i;
  sl_init_dep : forall w s1 s2 masks1 masks2 aux,
    w < wire_count c ->
    at_member (encode m s1 masks1) (dom w) (v_zero m) =
    at_member (encode m s2 masks2) (dom w) (v_zero m) ->
    init_fn s1 (masks1, aux) w = init_fn s2 (masks2, aux) w
}.

Definition witness_ShareLocalized :
  ShareLocalized gf2 unit (tt :: nil) 1 (g_in 0 :: g_in 1 :: nil) gf2_ops
    (fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false)
    (fun _ _ _ => false) (fun w => w).
Proof.
  constructor.
  - reflexivity.
  - intros w Hw. unfold wire_count in Hw. simpl in Hw. exact Hw.
  - intros w Hw. destruct w as [|[|w]]; simpl; [exact I | exact I | lia].
  - intros w i s1 s2 masks1 masks2 aux t Hw Eg Hshare.
    unfold wire_count, gate_at in Hw, Eg. simpl in Hw, Eg.
    destruct w as [|[|w]]; [| |lia]; inversion Eg; subst; exact Hshare.
  - intros w s1 s2 masks1 masks2 aux Hw Hshare. reflexivity.
Defined.

Definition UnreducedOrderSecure (x : Experiment) (E : Expansion) (d : nat) : Prop :=
  x_order x = d /\ ProbingSecure x E.

Lemma flat_map_over_is_flat_map :
  forall {A B : Type} (f : A -> list B) (l : list A),
    flat_map_over f l = flat_map f l.
Proof.
  intros A B f l. induction l as [|x r IH]; simpl; [reflexivity | rewrite IH; reflexivity].
Qed.

Lemma perm_list_prod_map_left :
  forall {A B : Type} (f : A -> A) (l1 : list A) (l2 : list B),
    Perm (map f l1) l1 ->
    Perm (map (fun '(a, b) => (f a, b)) (list_prod l1 l2)) (list_prod l1 l2).
Proof.
  intros A B f l1 l2 Hperm.
  unfold list_prod. rewrite flat_map_over_is_flat_map.
  replace (flat_map (fun a => map_over (fun b => (a, b)) l2) l1)
    with (flat_map (fun a => map (fun b => (a, b)) l2) l1)
    by (apply flat_map_ext; intros a; rewrite map_over_is_map; reflexivity).
  rewrite map_flatten.
  replace (flat_map (fun a => map (fun '(a0, b) => (f a0, b)) (map (fun b => (a, b)) l2)) l1)
    with (flat_map (fun a => map (fun b => (a, b)) l2) (map f l1)).
  - apply perm_flat_map_std. exact Hperm.
  - rewrite flat_map_mapped. apply flat_map_ext. intros a.
    rewrite map_map. apply map_ext. intros b. reflexivity.
Qed.

Lemma sl_eval_depends_only_on_share :
  forall (m : Sharing) (Aux : Type) (aux_enum : list Aux)
         (d : nat) (c : Circuit) (ops : nat -> list (Val m) -> Val m)
         (in_fn : Val m -> list (Val m) * Aux -> nat -> nat -> Val m)
         (init_fn : Val m -> list (Val m) * Aux -> nat -> Val m)
         (dom : nat -> nat)
         (Hsl : ShareLocalized m Aux aux_enum d c ops in_fn init_fn dom)
         (s1 s2 : Val m) (masks1 masks2 : list (Val m)) (aux : Aux)
         (fuel t w : nat),
    w < wire_count c ->
    at_member (encode m s1 masks1) (dom w) (v_zero m) =
    at_member (encode m s2 masks2) (dom w) (v_zero m) ->
    (forall u, u < wire_count c -> dom u = dom w ->
       regs_at m ops c (init_fn s1 (masks1, aux)) (in_fn s1 (masks1, aux)) t u =
       regs_at m ops c (init_fn s2 (masks2, aux)) (in_fn s2 (masks2, aux)) t u) ->
    eval_wire m ops c
      (regs_at m ops c (init_fn s1 (masks1, aux)) (in_fn s1 (masks1, aux)) t)
      (in_fn s1 (masks1, aux) t) fuel w =
    eval_wire m ops c
      (regs_at m ops c (init_fn s2 (masks2, aux)) (in_fn s2 (masks2, aux)) t)
      (in_fn s2 (masks2, aux) t) fuel w.
Proof.
  intros m Aux aux_enum d c ops in_fn init_fn dom Hsl s1 s2 masks1 masks2 aux fuel.
  induction fuel as [|f IH]; intros t w Hw Hshare Hregs; [reflexivity|].
  simpl. destruct (gate_at c w) as [i|s|o args] eqn:Eg.
  - exact (sl_in_dep _ _ _ _ _ _ _ _ _ Hsl w i s1 s2 masks1 masks2 aux t Hw Eg Hshare).
  - apply Hregs; [exact Hw | reflexivity].
  - f_equal. apply map_over_ext_nat. intros u Hu.
    pose proof (well_formed_gate_reads_earlier_wires c w o args
                  (sl_wf _ _ _ _ _ _ _ _ _ Hsl)
                  (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
    pose proof (all_of_mem_nat (fun x => Nat.ltb x w) args u Hargs Hu) as Huw.
    apply Nat.ltb_lt in Huw.
    pose proof (sl_dom_gate _ _ _ _ _ _ _ _ _ Hsl w Hw) as Hdomw.
    rewrite Eg in Hdomw.
    pose proof (all_of_mem_nat (fun x => Nat.eqb (dom x) (dom w)) args u Hdomw Hu) as Hudom.
    apply Nat.eqb_eq in Hudom.
    apply IH; [lia | rewrite Hudom; exact Hshare|].
    intros v Hv Hvd. apply Hregs; [exact Hv | rewrite Hvd; exact Hudom].
Qed.

Lemma sl_regs_depend_only_on_share :
  forall (m : Sharing) (Aux : Type) (aux_enum : list Aux)
         (d : nat) (c : Circuit) (ops : nat -> list (Val m) -> Val m)
         (in_fn : Val m -> list (Val m) * Aux -> nat -> nat -> Val m)
         (init_fn : Val m -> list (Val m) * Aux -> nat -> Val m)
         (dom : nat -> nat)
         (Hsl : ShareLocalized m Aux aux_enum d c ops in_fn init_fn dom)
         (s1 s2 : Val m) (masks1 masks2 : list (Val m)) (aux : Aux)
         (t w : nat),
    w < wire_count c ->
    at_member (encode m s1 masks1) (dom w) (v_zero m) =
    at_member (encode m s2 masks2) (dom w) (v_zero m) ->
    regs_at m ops c (init_fn s1 (masks1, aux)) (in_fn s1 (masks1, aux)) t w =
    regs_at m ops c (init_fn s2 (masks2, aux)) (in_fn s2 (masks2, aux)) t w.
Proof.
  intros m Aux aux_enum d c ops in_fn init_fn dom Hsl s1 s2 masks1 masks2 aux t.
  induction t as [|t IH]; intros w Hw Hshare.
  - simpl. exact (sl_init_dep _ _ _ _ _ _ _ _ _ Hsl w s1 s2 masks1 masks2 aux Hw Hshare).
  - simpl. unfold step_regs.
    destruct (gate_at c w) as [i|s|o args] eqn:Eg.
    + apply IH; assumption.
    + pose proof (well_formed_register_source_exists c w s
                    (sl_wf _ _ _ _ _ _ _ _ _ Hsl)
                    (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hs.
      apply Nat.ltb_lt in Hs.
      pose proof (sl_dom_gate _ _ _ _ _ _ _ _ _ Hsl w Hw) as Hdomw.
      rewrite Eg in Hdomw.
      apply (sl_eval_depends_only_on_share m Aux aux_enum d c ops in_fn init_fn dom Hsl
               s1 s2 masks1 masks2 aux (wire_count c) t s Hs).
      * rewrite Hdomw. exact Hshare.
      * intros u Hu Hud. apply IH; [exact Hu | rewrite Hud, Hdomw; exact Hshare].
    + apply IH; assumption.
Qed.

Lemma sl_value_depends_only_on_share :
  forall (m : Sharing) (Aux : Type) (aux_enum : list Aux)
         (d : nat) (c : Circuit) (ops : nat -> list (Val m) -> Val m)
         (in_fn : Val m -> list (Val m) * Aux -> nat -> nat -> Val m)
         (init_fn : Val m -> list (Val m) * Aux -> nat -> Val m)
         (dom : nat -> nat)
         (Hsl : ShareLocalized m Aux aux_enum d c ops in_fn init_fn dom)
         (s1 s2 : Val m) (masks1 masks2 : list (Val m)) (aux : Aux)
         (t w : nat),
    w < wire_count c ->
    at_member (encode m s1 masks1) (dom w) (v_zero m) =
    at_member (encode m s2 masks2) (dom w) (v_zero m) ->
    value_at m ops c (init_fn s1 (masks1, aux)) (in_fn s1 (masks1, aux)) t w =
    value_at m ops c (init_fn s2 (masks2, aux)) (in_fn s2 (masks2, aux)) t w.
Proof.
  intros m Aux aux_enum d c ops in_fn init_fn dom Hsl s1 s2 masks1 masks2 aux t w Hw Hshare.
  unfold value_at.
  apply (sl_eval_depends_only_on_share m Aux aux_enum d c ops in_fn init_fn dom Hsl
           s1 s2 masks1 masks2 aux (wire_count c) t w Hw Hshare).
  intros u Hu Hud.
  apply (sl_regs_depend_only_on_share m Aux aux_enum d c ops in_fn init_fn dom Hsl
           s1 s2 masks1 masks2 aux t u Hu).
  rewrite Hud. exact Hshare.
Qed.

Lemma encode_shift_share_agree :
  forall (m : Sharing) (s1 s2 : Val m) (d i j : nat) (masks : list (Val m)),
    length masks = d ->
    i < d ->
    j <= d ->
    j <> i ->
    at_member (encode m s2 (shift_mask m i (v_sub m s2 s1) masks)) j (v_zero m) =
    at_member (encode m s1 masks) j (v_zero m).
Proof.
  intros m s1 s2 d i j masks Hlen Hi Hj Hji.
  repeat rewrite at_member_is_nth.
  unfold encode. destruct (Nat.lt_ge_cases j d) as [Hjlt | Hjge].
  - repeat rewrite app_nth1; try (rewrite shift_mask_length, Hlen; lia); try lia.
    apply shift_mask_other. lia.
  - assert (E : j = d) by lia. subst j.
    rewrite app_nth2, app_nth2; try (rewrite shift_mask_length, Hlen; lia); try lia.
    rewrite shift_mask_length, Hlen, Nat.sub_diag. cbn [nth].
    rewrite shift_mask_sum by lia. apply v_sub_shift.
Qed.

Lemma encode_prefix_share_agree :
  forall (m : Sharing) (s1 s2 : Val m) (d j : nat) (masks : list (Val m)),
    length masks = d ->
    j < d ->
    at_member (encode m s1 masks) j (v_zero m) =
    at_member (encode m s2 masks) j (v_zero m).
Proof.
  intros m s1 s2 d j masks Hlen Hj.
  repeat rewrite at_member_is_nth. unfold encode.
  repeat rewrite app_nth1 by lia. reflexivity.
Qed.

(*| discharges: R-15-053a, R-05-004a |*)
Theorem share_localized_unreduced_probing_secure :
  forall (m : Sharing) (Aux : Type) (aux_enum : list Aux)
         (d : nat) (c : Circuit) (ops : nat -> list (Val m) -> Val m)
         (in_fn : Val m -> list (Val m) * Aux -> nat -> nat -> Val m)
         (init_fn : Val m -> list (Val m) * Aux -> nat -> Val m)
         (dom : nat -> nat) (E : Expansion),
    LocalExpansion E ->
    ShareLocalized m Aux aux_enum d c ops in_fn init_fn dom ->
    UnreducedOrderSecure (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E d.
Proof.
  intros m Aux aux_enum d c ops in_fn init_fn dom E Hloc Hsl.
  split; [reflexivity|].
  intros ps Hadm s1 s2.
  unfold admissible_probes in Hadm. apply andb_prop in Hadm.
  destruct Hadm as [Hord Hw].
  unfold mk_shared_experiment in Hord, Hw. cbn [x_order x_circuit] in Hord, Hw.
  apply Nat.leb_le in Hord.
  set (probed_doms := map (fun p => dom (p_wire p)) ps).
  assert (Hlen_doms : length probed_doms < S d).
  { unfold probed_doms. rewrite length_map, <- count_of_is_length. lia. }
  destruct (a_short_probe_list_misses_a_share (S d) probed_doms Hlen_doms)
    as [i [Hi Hmiss]].
  assert (Hobs_prop : forall o,
    ProofSupport.Member o (probe_set E c ps) ->
    obs_wire o < wire_count c /\ dom (obs_wire o) < S d /\ dom (obs_wire o) <> i).
  { intros o Ho. unfold probe_set in Ho.
    apply member_flat_map_over_inv in Ho. destruct Ho as [p [Hp Ho]].
    assert (Hpw : p_wire p < wire_count c).
    { clear -Hw Hp. unfold wires_exist in Hw.
      induction ps as [|q r IH]; simpl in *; [contradiction|].
      apply andb_prop in Hw. destruct Hw as [Hq Hr].
      destruct Hp as [->|Hp]; [apply Nat.ltb_lt; exact Hq | apply IH; assumption]. }
    destruct (le_domain E Hloc c dom p o (sl_wf _ _ _ _ _ _ _ _ _ Hsl) Hpw
                (sl_dom_gate _ _ _ _ _ _ _ _ _ Hsl) Ho) as [How Hdomo].
    split; [exact How|]. split; [exact (sl_dom_bound _ _ _ _ _ _ _ _ _ Hsl _ How)|].
    intro Eeq. apply Hmiss. unfold probed_doms. rewrite <- Eeq, Hdomo.
    apply (in_map (fun q => dom (p_wire q))). clear -Hp.
    induction ps as [|q r IH]; simpl in *; [contradiction|].
    destruct Hp as [->|Hp]; [left; reflexivity | right; exact (IH Hp)]. }
  assert (Henum_len : forall masks aux,
    In (masks, aux) (list_prod (mask_tuples m d) aux_enum) ->
    length masks = d).
  { intros masks aux Hin. unfold list_prod in Hin.
    rewrite flat_map_over_is_flat_map in Hin.
    apply in_flat_map in Hin. destruct Hin as [xs [Hxs Hin]].
    rewrite map_over_is_map in Hin. apply in_map_iff in Hin.
    destruct Hin as [b [Heq _]]. inversion Heq. subst xs.
    exact (mask_tuples_length m d masks Hxs). }
  destruct (Nat.lt_ge_cases i d) as [Hid | Hge].
  - set (sigma := fun t : list (Val m) * Aux =>
                    match t with (masks, aux) => (shift_mask m i (v_sub m s2 s1) masks, aux) end).
    apply equal_image_multisets_are_identically_distributed.
    repeat rewrite map_over_is_map.
    change (Perm
      (map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s1 t)
           (list_prod (mask_tuples m d) aux_enum))
      (map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s2 t)
           (list_prod (mask_tuples m d) aux_enum))).
    replace (map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s1 t)
                 (list_prod (mask_tuples m d) aux_enum))
      with (map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s2 (sigma t))
                (list_prod (mask_tuples m d) aux_enum)).
    + rewrite <- (map_map sigma
                    (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s2 t)
                    (list_prod (mask_tuples m d) aux_enum)).
      apply perm_map_std. unfold sigma.
      apply perm_list_prod_map_left.
      apply shift_mask_permutation. exact Hid.
    + apply map_ext_in. intros [masks aux] Hin.
      pose proof (Henum_len masks aux Hin) as Hlen.
      unfold sigma, x_view. cbn [x_share x_ops x_circuit x_init x_in].
      apply support_map_ext. intros o Ho.
      destruct (Hobs_prop o Ho) as [How [Hdom_lt Hdom_ne]].
      destruct o as [w cyc | w cyc]; simpl in *.
      * apply (sl_value_depends_only_on_share m Aux aux_enum d c ops in_fn init_fn dom Hsl
                 s2 s1 (shift_mask m i (v_sub m s2 s1) masks) masks aux cyc w How).
        apply (encode_shift_share_agree m s1 s2 d i (dom w) masks Hlen Hid ltac:(lia) Hdom_ne).
      * f_equal;
          apply (sl_value_depends_only_on_share m Aux aux_enum d c ops in_fn init_fn dom Hsl
                   s2 s1 (shift_mask m i (v_sub m s2 s1) masks) masks aux _ w How);
          apply (encode_shift_share_agree m s1 s2 d i (dom w) masks Hlen Hid ltac:(lia) Hdom_ne).
  - assert (Ei : i = d) by lia. subst i.
    apply equal_image_multisets_are_identically_distributed.
    repeat rewrite map_over_is_map.
    change (Perm
      (map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s1 t)
           (list_prod (mask_tuples m d) aux_enum))
      (map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s2 t)
           (list_prod (mask_tuples m d) aux_enum))).
    assert (Heq :
      map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s1 t)
          (list_prod (mask_tuples m d) aux_enum) =
      map (fun t => x_view (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E ps s2 t)
          (list_prod (mask_tuples m d) aux_enum)).
    { apply map_ext_in. intros [masks aux] Hin.
      pose proof (Henum_len masks aux Hin) as Hlen.
      unfold x_view. cbn [x_share x_ops x_circuit x_init x_in].
      apply support_map_ext. intros o Ho.
      destruct (Hobs_prop o Ho) as [How [Hdom_lt Hdom_ne]].
      destruct o as [w cyc | w cyc]; simpl in *.
      * apply (sl_value_depends_only_on_share m Aux aux_enum d c ops in_fn init_fn dom Hsl
                 s1 s2 masks masks aux cyc w How).
        apply (encode_prefix_share_agree m s1 s2 d (dom w) masks Hlen ltac:(lia)).
      * f_equal;
          apply (sl_value_depends_only_on_share m Aux aux_enum d c ops in_fn init_fn dom Hsl
                   s1 s2 masks masks aux _ w How);
          apply (encode_prefix_share_agree m s1 s2 d (dom w) masks Hlen ltac:(lia)). }
    rewrite Heq. apply perm_refl.
Qed.

(*| discharges: R-15-053a, R-05-004a |*)
Theorem share_localized_adaptive_probing_secure :
  forall (m : Sharing) (Aux : Type) (aux_enum : list Aux)
         (d : nat) (c : Circuit) (ops : nat -> list (Val m) -> Val m)
         (in_fn : Val m -> list (Val m) * Aux -> nat -> nat -> Val m)
         (init_fn : Val m -> list (Val m) * Aux -> nat -> Val m)
         (dom : nat -> nat) (E : Expansion),
    aux_enum <> nil ->
    LocalExpansion E ->
    ShareLocalized m Aux aux_enum d c ops in_fn init_fn dom ->
    AdaptiveProbingSecure (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E.
Proof.
  intros m Aux aux_enum d c ops in_fn init_fn dom E Haux Hloc Hsl.
  destruct (share_localized_unreduced_probing_secure m Aux aux_enum d c ops in_fn init_fn dom E Hloc Hsl)
    as [_ Hsec].
  apply (fixed_implies_adaptive_probing_secure
           (mk_shared_experiment m Aux aux_enum d c ops in_fn init_fn) E
           (qualified_share_mask_tapes m Aux aux_enum d Haux) Hsec).
Qed.

(* =========================================================================
   3. Masked activations, fine-grained detection, and the R-17-058d
      combined single-fault reduction theorem.
   ========================================================================= *)

Inductive FaultTarget : Type :=
  | TargetShareLocal : nat -> FaultTarget
  | TargetControlOrCheck : FaultTarget.

Record MaskedActivation : Type := {
  ma_state : Type;
  ma_fault : Type;
  ma_sys : FaultStepSystem ma_state ma_fault;
  ma_s0 : ma_state;
  ma_share : Sharing;
  ma_aux : Type;
  ma_aux_enum : list ma_aux;
  ma_aux_nonempty : ma_aux_enum <> nil;
  ma_order : nat;
  ma_token : Type;
  ma_token_eqb : ma_token -> ma_token -> bool;
  ma_token_eqb_refl : forall a, ma_token_eqb a a = true;
  ma_token_eqb_sound : forall a b, ma_token_eqb a b = true -> a = b;
  ma_accept_token : ma_token;
  ma_circuit : ActivationFaultClass ma_fault -> Circuit;
  ma_ops : ActivationFaultClass ma_fault -> nat -> list (Val ma_share) -> Val ma_share;
  ma_in : ActivationFaultClass ma_fault -> Val ma_share ->
          list (Val ma_share) * ma_aux -> nat -> nat -> Val ma_share;
  ma_init : ActivationFaultClass ma_fault -> Val ma_share ->
            list (Val ma_share) * ma_aux -> nat -> Val ma_share;
  ma_dom : ActivationFaultClass ma_fault -> nat -> nat;
  ma_emit_token : ActivationFaultClass ma_fault -> Val ma_share ->
                  list (Val ma_share) * ma_aux -> ma_token;
  ma_target_at : nat -> FaultAction ma_fault -> FaultTarget;
  ma_effective_fault : ActivationFaultClass ma_fault -> bool
}.

Definition ma_fault_exp (ma : MaskedActivation)
    (fc : ActivationFaultClass (ma_fault ma)) : Experiment :=
  mk_shared_experiment (ma_share ma) (ma_aux ma) (ma_aux_enum ma)
    (ma_order ma) (ma_circuit ma fc) (ma_ops ma fc) (ma_in ma fc) (ma_init ma fc).

Definition token_withheld (ma : MaskedActivation)
    (fc : ActivationFaultClass (ma_fault ma))
    (sec : Val (ma_share ma))
    (tape : list (Val (ma_share ma)) * ma_aux ma) : bool :=
  negb (ma_token_eqb ma (ma_emit_token ma fc sec tape) (ma_accept_token ma)).

Lemma token_withheld_iff_neq :
  forall (ma : MaskedActivation) (fc : ActivationFaultClass (ma_fault ma))
         (sec : Val (ma_share ma)) (tape : list (Val (ma_share ma)) * ma_aux ma),
    token_withheld ma fc sec tape = true <->
    ma_emit_token ma fc sec tape <> ma_accept_token ma.
Proof.
  intros ma fc sec tape. unfold token_withheld.
  destruct (ma_token_eqb ma (ma_emit_token ma fc sec tape) (ma_accept_token ma)) eqn:Eeq.
  - simpl. split; [intro H; discriminate H | intro Hne; exfalso; apply Hne;
      exact (ma_token_eqb_sound ma _ _ Eeq)].
  - simpl. split; [intros _ Heq; rewrite Heq in Eeq;
      rewrite (ma_token_eqb_refl ma _) in Eeq; discriminate Eeq | reflexivity].
Qed.

Definition ShareConfinedFault (ma : MaskedActivation)
    (fc : ActivationFaultClass (ma_fault ma)) (k_f : nat) : Prop :=
  k_f < S (ma_order ma) /\
  ShareLocalized (ma_share ma) (ma_aux ma) (ma_aux_enum ma) (ma_order ma)
    (ma_circuit ma fc) (ma_ops ma fc) (ma_in ma fc) (ma_init ma fc) (ma_dom ma fc) /\
  (forall w,
     w < wire_count (ma_circuit ma fc) ->
     ma_dom ma fc w <> k_f ->
     gate_at (ma_circuit ma fc) w = gate_at (ma_circuit ma FaultFree) w /\
     ma_dom ma fc w = ma_dom ma FaultFree w /\
     (forall sec tape t i,
        gate_at (ma_circuit ma fc) w = g_in i ->
        ma_in ma fc sec tape t i = ma_in ma FaultFree sec tape t i) /\
     (forall sec tape,
        ma_init ma fc sec tape w = ma_init ma FaultFree sec tape w)).

Record ConformingMaskedDatapath (ma : MaskedActivation) : Prop := {
  cmd_fault_free_not_effective :
    ma_effective_fault ma FaultFree = false;
  cmd_fault_free_localized :
    ShareLocalized (ma_share ma) (ma_aux ma) (ma_aux_enum ma) (ma_order ma)
      (ma_circuit ma FaultFree) (ma_ops ma FaultFree)
      (ma_in ma FaultFree) (ma_init ma FaultFree) (ma_dom ma FaultFree);
  cmd_effective_withheld :
    forall tr s_end b_end idx act,
      FaultDerivation (ma_sys ma) (ma_s0 ma, 1) tr (s_end, b_end) ->
      classify_trace tr = SingleFault idx act ->
      ma_effective_fault ma (SingleFault idx act) = true ->
      forall sec tape, token_withheld ma (SingleFault idx act) sec tape = true;
  cmd_ineffective_share_confined :
    forall tr s_end b_end idx act,
      FaultDerivation (ma_sys ma) (ma_s0 ma, 1) tr (s_end, b_end) ->
      classify_trace tr = SingleFault idx act ->
      ma_effective_fault ma (SingleFault idx act) = false ->
      exists k_f : nat,
        ma_target_at ma idx act = TargetShareLocal k_f /\
        ShareConfinedFault ma (SingleFault idx act) k_f
}.

Definition EffectiveDetectedArm (ma : MaskedActivation)
    (fc : ActivationFaultClass (ma_fault ma)) : Prop :=
  ma_effective_fault ma fc = true /\
  forall sec tape, token_withheld ma fc sec tape = true.

Definition ShareConfinedProbingArm (ma : MaskedActivation) (E : Expansion)
    (fc : ActivationFaultClass (ma_fault ma)) : Prop :=
  ma_effective_fault ma fc = false /\
  (exists k_f : nat, ShareConfinedFault ma fc k_f) /\
  UnreducedOrderSecure (ma_fault_exp ma fc) E (ma_order ma) /\
  AdaptiveProbingSecure (ma_fault_exp ma fc) E.

(*| discharges: R-17-058d, R-16-008f, R-15-053a, R-05-004a |*)
Theorem combined_single_fault_reduction :
  forall (ma : MaskedActivation) (E : Expansion)
         (tr : list (option (FaultAction (ma_fault ma))))
         (s_end : ma_state ma) (b_end : nat),
    LocalExpansion E ->
    ConformingMaskedDatapath ma ->
    FaultDerivation (ma_sys ma) (ma_s0 ma, 1) tr (s_end, b_end) ->
    EffectiveDetectedArm ma (classify_trace tr) \/
    ShareConfinedProbingArm ma E (classify_trace tr).
Proof.
  intros ma E tr s_end b_end Hloc Hcmd Hder.
  destruct (activation_derivation_partition (ma_sys ma) (ma_s0 ma) s_end b_end tr Hder)
    as [[_ [_ Hff]] | [_ [_ [idx [act [Hsf _]]]]]].
  - rewrite Hff. right.
    split; [exact (cmd_fault_free_not_effective ma Hcmd)|].
    split.
    + exists 0. unfold ShareConfinedFault.
      split; [lia|].
      split; [exact (cmd_fault_free_localized ma Hcmd)|].
      intros w _ _. repeat split; reflexivity.
    + split.
      * exact (share_localized_unreduced_probing_secure
                 (ma_share ma) (ma_aux ma) (ma_aux_enum ma) (ma_order ma)
                 (ma_circuit ma FaultFree) (ma_ops ma FaultFree)
                 (ma_in ma FaultFree) (ma_init ma FaultFree)
                 (ma_dom ma FaultFree) E Hloc (cmd_fault_free_localized ma Hcmd)).
      * exact (share_localized_adaptive_probing_secure
                 (ma_share ma) (ma_aux ma) (ma_aux_enum ma) (ma_order ma)
                 (ma_circuit ma FaultFree) (ma_ops ma FaultFree)
                 (ma_in ma FaultFree) (ma_init ma FaultFree)
                 (ma_dom ma FaultFree) E (ma_aux_nonempty ma) Hloc
                 (cmd_fault_free_localized ma Hcmd)).
  - rewrite Hsf.
    destruct (ma_effective_fault ma (SingleFault idx act)) eqn:Heff.
    + left. split; [exact Heff|].
      exact (cmd_effective_withheld ma Hcmd tr s_end b_end idx act Hder Hsf Heff).
    + right.
      destruct (cmd_ineffective_share_confined ma Hcmd tr s_end b_end idx act Hder Hsf Heff)
        as [k_f [_ Hconf]].
      pose proof Hconf as [_ [Hsl _]].
      split; [exact Heff|].
      split; [exists k_f; exact Hconf|].
      split.
      * exact (share_localized_unreduced_probing_secure
                 (ma_share ma) (ma_aux ma) (ma_aux_enum ma) (ma_order ma)
                 (ma_circuit ma (SingleFault idx act)) (ma_ops ma (SingleFault idx act))
                 (ma_in ma (SingleFault idx act)) (ma_init ma (SingleFault idx act))
                 (ma_dom ma (SingleFault idx act)) E Hloc Hsl).
      * exact (share_localized_adaptive_probing_secure
                 (ma_share ma) (ma_aux ma) (ma_aux_enum ma) (ma_order ma)
                 (ma_circuit ma (SingleFault idx act)) (ma_ops ma (SingleFault idx act))
                 (ma_in ma (SingleFault idx act)) (ma_init ma (SingleFault idx act))
                 (ma_dom ma (SingleFault idx act)) E (ma_aux_nonempty ma) Hloc Hsl).
Qed.

(*| discharges: R-17-058d, R-15-053a |*)
Theorem combined_reduction_preserves_unreduced_order :
  forall (ma : MaskedActivation) (E : Expansion)
         (tr : list (option (FaultAction (ma_fault ma))))
         (s_end : ma_state ma) (b_end : nat),
    1 <= ma_order ma ->
    LocalExpansion E ->
    ConformingMaskedDatapath ma ->
    FaultDerivation (ma_sys ma) (ma_s0 ma, 1) tr (s_end, b_end) ->
    EffectiveDetectedArm ma (classify_trace tr) \/
    (ShareConfinedProbingArm ma E (classify_trace tr) /\
     x_order (ma_fault_exp ma (classify_trace tr)) = ma_order ma /\
     x_order (ma_fault_exp ma (classify_trace tr)) <> ma_order ma - 1).
Proof.
  intros ma E tr s_end b_end Hord Hloc Hcmd Hder.
  destruct (combined_single_fault_reduction ma E tr s_end b_end Hloc Hcmd Hder)
    as [Hdet | Hconf].
  - left. exact Hdet.
  - right. split; [exact Hconf|].
    destruct Hconf as [_ [_ [[Hxord _] _]]].
    split; [exact Hxord | lia].
Qed.

(* =========================================================================
   4. Parametric (d + 1)-share positive witness with fine-grained check
      (R-05-166, R-17-058d, R-05-004a).
   ========================================================================= *)

Fixpoint checked_regs_circuit (k : nat) : Circuit :=
  match k with
  | 0 => nil
  | S m => app (checked_regs_circuit m) (cons (g_reg m) nil)
  end.

Definition checked_masked_circuit (d : nat) : Circuit :=
  app (input_wires_circuit (S d)) (checked_regs_circuit (S d)).

Fixpoint checked_regs_faulted (k idx : nat) : Circuit :=
  match k with
  | 0 => nil
  | S m =>
      app (checked_regs_faulted m idx)
          (cons (if Nat.eqb m idx then g_op 1 (m :: nil) else g_reg m) nil)
  end.

Definition checked_masked_circuit_faulted (d idx : nat) : Circuit :=
  app (input_wires_circuit (S d)) (checked_regs_faulted (S d) idx).

Lemma checked_regs_count :
  forall k : nat, count_of (checked_regs_circuit k) = k.
Proof.
  induction k as [|k IH]; simpl; [reflexivity|].
  rewrite count_of_is_length, length_app. simpl.
  rewrite <- count_of_is_length. lia.
Qed.

Lemma checked_regs_faulted_count :
  forall k idx : nat, count_of (checked_regs_faulted k idx) = k.
Proof.
  intros k idx. induction k as [|k IH]; simpl; [reflexivity|].
  rewrite count_of_is_length, length_app. simpl.
  rewrite <- count_of_is_length. lia.
Qed.

Lemma checked_masked_circuit_count :
  forall d : nat, wire_count (checked_masked_circuit d) = S d + S d.
Proof.
  intros d. unfold wire_count, checked_masked_circuit.
  rewrite count_of_is_length, length_app, <- !count_of_is_length.
  change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
  rewrite input_wires_count, checked_regs_count. reflexivity.
Qed.

Lemma checked_masked_circuit_faulted_count :
  forall d idx : nat, wire_count (checked_masked_circuit_faulted d idx) = S d + S d.
Proof.
  intros d idx. unfold wire_count, checked_masked_circuit_faulted.
  rewrite count_of_is_length, length_app, <- !count_of_is_length.
  change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
  rewrite input_wires_count, checked_regs_faulted_count. reflexivity.
Qed.

Lemma wf_from_app :
  forall (total i : nat) (l1 l2 : list Gate),
    wf_from total i (app l1 l2) =
    andb (wf_from total i l1) (wf_from total (Nat.add i (count_of l1)) l2).
Proof.
  intros total i l1. revert i. induction l1 as [|g r IH]; intros i l2; simpl.
  - rewrite add_zero_r_nat. reflexivity.
  - rewrite IH, add_succ_r_nat. destruct (gate_well_formed total i g); reflexivity.
Qed.

Lemma wf_from_checked_regs :
  forall total k i : nat,
    k <= total ->
    wf_from total i (checked_regs_circuit k) = true.
Proof.
  intros total k. induction k as [|k IH]; intros i Hle; simpl; [reflexivity|].
  rewrite wf_from_app, IH by lia. simpl.
  assert (Hlt : Nat.ltb k total = true) by (apply Nat.ltb_lt; lia).
  rewrite Hlt. reflexivity.
Qed.

Lemma wf_from_checked_regs_faulted :
  forall k idx i total : nat,
    k <= total ->
    k <= i ->
    wf_from total i (checked_regs_faulted k idx) = true.
Proof.
  intros k idx. induction k as [|k IH]; intros i total Hkt Hki; simpl; [reflexivity|].
  rewrite wf_from_app, IH by lia. simpl.
  rewrite checked_regs_faulted_count.
  destruct (Nat.eqb k idx); simpl.
  - assert (Hlt : Nat.ltb k (i + k) = true) by (apply Nat.ltb_lt; lia).
    rewrite Hlt. reflexivity.
  - assert (Hlt : Nat.ltb k total = true) by (apply Nat.ltb_lt; lia).
    rewrite Hlt. reflexivity.
Qed.

Lemma checked_masked_circuit_wf :
  forall d : nat, well_formed (checked_masked_circuit d) = true.
Proof.
  intros d. unfold well_formed.
  rewrite checked_masked_circuit_count.
  unfold checked_masked_circuit.
  rewrite wf_from_app, wf_from_input_wires. cbn [andb].
  apply wf_from_checked_regs. lia.
Qed.

Lemma checked_masked_circuit_faulted_wf :
  forall d idx : nat, well_formed (checked_masked_circuit_faulted d idx) = true.
Proof.
  intros d idx. unfold well_formed.
  rewrite checked_masked_circuit_faulted_count.
  unfold checked_masked_circuit_faulted.
  rewrite wf_from_app, wf_from_input_wires. cbn [andb].
  change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
  rewrite input_wires_count.
  apply wf_from_checked_regs_faulted; lia.
Qed.

Lemma at_member_app_r :
  forall {A : Type} (l1 l2 : list A) (i : nat) (d : A),
    count_of l1 <= i ->
    at_member (app l1 l2) i d = at_member l2 (i - count_of l1) d.
Proof.
  intros A l1. induction l1 as [|x r IH]; intros l2 i d Hi; simpl in *.
  - rewrite Nat.sub_0_r. reflexivity.
  - destruct i as [|k]; [lia|]. simpl. apply IH. lia.
Qed.

Lemma checked_regs_gate_at :
  forall k w : nat,
    w < k -> at_member (checked_regs_circuit k) w (g_in 0) = g_reg w.
Proof.
  induction k as [|k IH]; intros w Hw; [lia|].
  simpl. destruct (Nat.lt_ge_cases w k) as [Hlt | Hge].
  - rewrite at_member_app_l; [apply IH; exact Hlt|].
    rewrite checked_regs_count. apply Nat.ltb_lt. exact Hlt.
  - assert (E : w = k) by lia. subst w.
    pose proof (at_member_app_last (checked_regs_circuit k) (g_reg k) (g_in 0)) as Hlast.
    rewrite checked_regs_count in Hlast. exact Hlast.
Qed.

Lemma checked_regs_faulted_gate_at :
  forall k idx w : nat,
    w < k ->
    at_member (checked_regs_faulted k idx) w (g_in 0) =
    (if Nat.eqb w idx then g_op 1 (w :: nil) else g_reg w).
Proof.
  intros k idx. induction k as [|k IH]; intros w Hw; [lia|].
  simpl. destruct (Nat.lt_ge_cases w k) as [Hlt | Hge].
  - rewrite at_member_app_l; [apply IH; exact Hlt|].
    rewrite checked_regs_faulted_count. apply Nat.ltb_lt. exact Hlt.
  - assert (E : w = k) by lia. subst w.
    pose proof (at_member_app_last (checked_regs_faulted k idx)
                  (if Nat.eqb k idx then g_op 1 (k :: nil) else g_reg k) (g_in 0)) as Hlast.
    rewrite checked_regs_faulted_count in Hlast. exact Hlast.
Qed.

Definition checked_dom (d w : nat) : nat :=
  if Nat.ltb w (S d) then w else w - S d.

Lemma checked_masked_gate_at_low :
  forall d w : nat,
    w < S d -> gate_at (checked_masked_circuit d) w = g_in w.
Proof.
  intros d w Hw. unfold gate_at, checked_masked_circuit.
  rewrite at_member_app_l; [apply input_wires_gate_at; exact Hw|].
  change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
  rewrite input_wires_count. apply Nat.ltb_lt. exact Hw.
Qed.

Lemma checked_masked_gate_at_high :
  forall d w : nat,
    S d <= w -> w < S d + S d ->
    gate_at (checked_masked_circuit d) w = g_reg (w - S d).
Proof.
  intros d w Hlo Hhi. unfold gate_at, checked_masked_circuit.
  rewrite at_member_app_r.
  - change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
    rewrite input_wires_count. apply checked_regs_gate_at. lia.
  - change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
    rewrite input_wires_count. exact Hlo.
Qed.

Lemma checked_masked_faulted_gate_at_low :
  forall d idx w : nat,
    w < S d -> gate_at (checked_masked_circuit_faulted d idx) w = g_in w.
Proof.
  intros d idx w Hw. unfold gate_at, checked_masked_circuit_faulted.
  rewrite at_member_app_l; [apply input_wires_gate_at; exact Hw|].
  change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
  rewrite input_wires_count. apply Nat.ltb_lt. exact Hw.
Qed.

Lemma checked_masked_faulted_gate_at_high :
  forall d idx w : nat,
    S d <= w -> w < S d + S d ->
    gate_at (checked_masked_circuit_faulted d idx) w =
    (if Nat.eqb (w - S d) idx then g_op 1 ((w - S d) :: nil) else g_reg (w - S d)).
Proof.
  intros d idx w Hlo Hhi. unfold gate_at, checked_masked_circuit_faulted.
  rewrite at_member_app_r.
  - change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
    rewrite input_wires_count. apply checked_regs_faulted_gate_at. lia.
  - change (count_of (input_wires_circuit (S d))) with (wire_count (input_wires_circuit (S d))).
    rewrite input_wires_count. exact Hlo.
Qed.

Definition instantiated_sys (d : nat) : FaultStepSystem nat bool := {|
  fs_in_region := fun pc => Nat.leb pc (S d);
  fs_step := S;
  fs_fault := fun pc _ => S pc
|}.

Lemma instantiated_fault_index_in_region_cfg :
  forall d cfg0 cfg1 tr idx act,
    FaultDerivation (instantiated_sys d) cfg0 tr cfg1 ->
    snd cfg0 = 1 ->
    classify_trace_from (fst cfg0) tr = SingleFault idx act ->
    idx <= S d.
Proof.
  intros d cfg0 cfg1 tr idx act Hder.
  induction Hder as [cfg | cfg1 opt cfg2 rest cfg3 Hstep Hrest IH];
    intros Hb0 Hcl.
  - simpl in Hcl. discriminate Hcl.
  - inversion Hstep; subst; simpl in *.
    + exact (IH Hb0 Hcl).
    + inversion Hcl. subst idx. apply Nat.leb_le. assumption.
Qed.

Lemma instantiated_fault_index_in_region :
  forall d p tr s_end b_end idx act,
    FaultDerivation (instantiated_sys d) (p, 1) tr (s_end, b_end) ->
    classify_trace_from p tr = SingleFault idx act ->
    idx <= S d.
Proof.
  intros d p tr s_end b_end idx act Hder Hcl.
  exact (instantiated_fault_index_in_region_cfg d (p, 1) (s_end, b_end) tr idx act
           Hder eq_refl Hcl).
Qed.

Definition instantiated_masked_activation (d : nat) : MaskedActivation := {|
  ma_state := nat;
  ma_fault := bool;
  ma_sys := instantiated_sys d;
  ma_s0 := 0;
  ma_share := gf2;
  ma_aux := unit;
  ma_aux_enum := tt :: nil;
  ma_aux_nonempty := ltac:(discriminate);
  ma_order := d;
  ma_token := bool;
  ma_token_eqb := bool_eqb;
  ma_token_eqb_refl := fun a => match a with true => eq_refl | false => eq_refl end;
  ma_token_eqb_sound := fun a b H =>
    match a, b return bool_eqb a b = true -> a = b with
    | true, true => fun _ => eq_refl
    | false, false => fun _ => eq_refl
    | true, false => fun H0 => match Bool.diff_true_false (eq_sym H0) with end
    | false, true => fun H0 => match Bool.diff_true_false (eq_sym H0) with end
    end H;
  ma_accept_token := true;
  ma_circuit := fun fc =>
    match fc with
    | FaultFree => checked_masked_circuit d
    | SingleFault idx (fault_corrupt false) => checked_masked_circuit_faulted d idx
    | SingleFault _ _ => checked_masked_circuit d
    end;
  ma_ops := fun _ => gf2_ops;
  ma_in := fun _ s '(masks, _) _ i => at_member (encode gf2 s masks) i false;
  ma_init := fun _ s '(masks, _) w =>
    if Nat.ltb w (S d) then false else at_member (encode gf2 s masks) (w - S d) false;
  ma_dom := fun _ => checked_dom d;
  ma_emit_token := fun fc _ _ =>
    match fc with
    | FaultFree => true
    | SingleFault idx act =>
        if Nat.ltb idx (S d) then
          match act with fault_skip => false | fault_corrupt b => negb b end
        else false
    end;
  ma_target_at := fun idx _ =>
    if Nat.ltb idx (S d) then TargetShareLocal idx else TargetControlOrCheck;
  ma_effective_fault := fun fc =>
    match fc with
    | FaultFree => false
    | SingleFault idx act =>
        if Nat.ltb idx (S d) then
          match act with fault_skip => true | fault_corrupt b => b end
        else true
    end
|}.

Lemma checked_masked_localized :
  forall d : nat,
    ShareLocalized gf2 unit (tt :: nil) d (checked_masked_circuit d) gf2_ops
      (fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false)
      (fun s '(masks, _) w =>
         if Nat.ltb w (S d) then false else at_member (encode gf2 s masks) (w - S d) false)
      (checked_dom d).
Proof.
  intros d. constructor.
  - apply checked_masked_circuit_wf.
  - intros w Hw. rewrite checked_masked_circuit_count in Hw.
    unfold checked_dom. destruct (Nat.ltb w (S d)) eqn:Ew;
      [apply Nat.ltb_lt in Ew; exact Ew | apply Nat.ltb_ge in Ew; lia].
  - intros w Hw. rewrite checked_masked_circuit_count in Hw.
    unfold checked_dom. destruct (Nat.ltb w (S d)) eqn:Ew.
    + apply Nat.ltb_lt in Ew. rewrite (checked_masked_gate_at_low d w Ew). exact I.
    + apply Nat.ltb_ge in Ew. rewrite (checked_masked_gate_at_high d w Ew Hw).
      destruct (Nat.ltb (w - S d) (S d)) eqn:Esub;
        [reflexivity | apply Nat.ltb_ge in Esub; lia].
  - intros w i s1 s2 masks1 masks2 aux t Hw Eg Hshare.
    rewrite checked_masked_circuit_count in Hw.
    unfold checked_dom in Hshare. destruct (Nat.ltb w (S d)) eqn:Ew.
    + apply Nat.ltb_lt in Ew. rewrite (checked_masked_gate_at_low d w Ew) in Eg.
      inversion Eg. subst i. exact Hshare.
    + apply Nat.ltb_ge in Ew. rewrite (checked_masked_gate_at_high d w Ew Hw) in Eg.
      discriminate Eg.
  - intros w s1 s2 masks1 masks2 aux Hw Hshare.
    unfold checked_dom in Hshare. destruct (Nat.ltb w (S d)) eqn:Ew;
      [reflexivity | exact Hshare].
Qed.

Lemma checked_masked_faulted_localized :
  forall d idx : nat,
    ShareLocalized gf2 unit (tt :: nil) d (checked_masked_circuit_faulted d idx) gf2_ops
      (fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false)
      (fun s '(masks, _) w =>
         if Nat.ltb w (S d) then false else at_member (encode gf2 s masks) (w - S d) false)
      (checked_dom d).
Proof.
  intros d idx. constructor.
  - apply checked_masked_circuit_faulted_wf.
  - intros w Hw. rewrite checked_masked_circuit_faulted_count in Hw.
    unfold checked_dom. destruct (Nat.ltb w (S d)) eqn:Ew;
      [apply Nat.ltb_lt in Ew; exact Ew | apply Nat.ltb_ge in Ew; lia].
  - intros w Hw. rewrite checked_masked_circuit_faulted_count in Hw.
    unfold checked_dom. destruct (Nat.ltb w (S d)) eqn:Ew.
    + apply Nat.ltb_lt in Ew. rewrite (checked_masked_faulted_gate_at_low d idx w Ew). exact I.
    + apply Nat.ltb_ge in Ew. rewrite (checked_masked_faulted_gate_at_high d idx w Ew Hw).
      destruct (Nat.eqb (w - S d) idx).
      * simpl. assert (Hlt : Nat.ltb (w - S d) (S d) = true) by (apply Nat.ltb_lt; lia).
        rewrite Hlt, eqb_refl_nat. reflexivity.
      * destruct (Nat.ltb (w - S d) (S d)) eqn:Esub;
          [reflexivity | apply Nat.ltb_ge in Esub; lia].
  - intros w i s1 s2 masks1 masks2 aux t Hw Eg Hshare.
    rewrite checked_masked_circuit_faulted_count in Hw.
    unfold checked_dom in Hshare. destruct (Nat.ltb w (S d)) eqn:Ew.
    + apply Nat.ltb_lt in Ew. rewrite (checked_masked_faulted_gate_at_low d idx w Ew) in Eg.
      inversion Eg. subst i. exact Hshare.
    + apply Nat.ltb_ge in Ew. rewrite (checked_masked_faulted_gate_at_high d idx w Ew Hw) in Eg.
      destruct (Nat.eqb (w - S d) idx); discriminate Eg.
  - intros w s1 s2 masks1 masks2 aux Hw Hshare.
    unfold checked_dom in Hshare. destruct (Nat.ltb w (S d)) eqn:Ew;
      [reflexivity | exact Hshare].
Qed.

(*| discharges: R-17-058d, R-05-166 |*)
Theorem instantiated_masked_activation_conforming :
  forall d : nat, ConformingMaskedDatapath (instantiated_masked_activation d).
Proof.
  intros d. constructor.
  - reflexivity.
  - apply checked_masked_localized.
  - intros tr s_end b_end idx act Hder Hcl Heff sec [masks []].
    cbn [ma_effective_fault instantiated_masked_activation] in Heff.
    unfold token_withheld. cbn [ma_token_eqb ma_emit_token ma_accept_token instantiated_masked_activation].
    destruct (Nat.ltb idx (S d)); [|reflexivity].
    destruct act as [|[]]; simpl in *; try discriminate Heff; reflexivity.
  - intros tr s_end b_end idx act Hder Hcl Hineff.
    cbn [ma_effective_fault instantiated_masked_activation] in Hineff.
    destruct (Nat.ltb idx (S d)) eqn:Eidx; [|discriminate Hineff].
    apply Nat.ltb_lt in Eidx.
    destruct act as [|[]]; [discriminate Hineff | discriminate Hineff |].
    exists idx. split.
    + cbn [ma_target_at instantiated_masked_activation].
      assert (Hlt : Nat.ltb idx (S d) = true) by (apply Nat.ltb_lt; exact Eidx).
      rewrite Hlt. reflexivity.
    + unfold ShareConfinedFault.
      split; [exact Eidx|].
      split; [exact (checked_masked_faulted_localized d idx)|].
      intros w Hw Hdom_ne.
      cbn [ma_circuit ma_dom ma_in ma_init instantiated_masked_activation] in *.
      rewrite checked_masked_circuit_faulted_count in Hw.
      split.
      * unfold checked_dom in Hdom_ne. destruct (Nat.ltb w (S d)) eqn:Ew.
        { apply Nat.ltb_lt in Ew.
          rewrite (checked_masked_faulted_gate_at_low d idx w Ew).
          rewrite (checked_masked_gate_at_low d w Ew). reflexivity. }
        { apply Nat.ltb_ge in Ew.
          rewrite (checked_masked_faulted_gate_at_high d idx w Ew Hw).
          rewrite (checked_masked_gate_at_high d w Ew Hw).
          destruct (Nat.eqb (w - S d) idx) eqn:Eeq; [|reflexivity].
          apply Nat.eqb_eq in Eeq. contradiction. }
      * split; [reflexivity|].
        split; [intros sec tape t i _; reflexivity | intros sec tape; reflexivity].
Qed.

Definition witness_MaskedActivation : MaskedActivation :=
  instantiated_masked_activation 2.

Definition witness_ConformingMaskedDatapath :
  ConformingMaskedDatapath witness_MaskedActivation :=
  instantiated_masked_activation_conforming 2.

(*| discharges: R-17-058d, R-05-166 |*)
Theorem instantiated_combined_reduction :
  forall (d : nat) (E : Expansion)
         (tr : list (option (FaultAction bool)))
         (s_end : nat) (b_end : nat),
    LocalExpansion E ->
    FaultDerivation (instantiated_sys d) (0, 1) tr (s_end, b_end) ->
    EffectiveDetectedArm (instantiated_masked_activation d) (classify_trace tr) \/
    ShareConfinedProbingArm (instantiated_masked_activation d) E (classify_trace tr).
Proof.
  intros d E tr s_end b_end Hloc Hder.
  exact (combined_single_fault_reduction
           (instantiated_masked_activation d) E tr s_end b_end Hloc
           (instantiated_masked_activation_conforming d) Hder).
Qed.

(* Concrete positive exercise of both reduction arms at order d = 2 (3 shares). *)
Example concrete_order_two_effective_and_confined_arms :
  EffectiveDetectedArm witness_MaskedActivation
    (classify_trace (None :: Some (fault_skip : FaultAction bool) :: nil)) /\
  ShareConfinedProbingArm witness_MaskedActivation ex_robust
    (classify_trace (Some (fault_corrupt false : FaultAction bool) :: nil)).
Proof.
  assert (Hder1 : FaultDerivation (instantiated_sys 2) (0, 1)
                    (None :: Some (fault_skip : FaultAction bool) :: nil) (2, 0)).
  { eapply fd_cons; [apply fs_step_rule|].
    eapply fd_cons; [apply fs_fault_rule; reflexivity | apply fd_nil]. }
  assert (Hder2 : FaultDerivation (instantiated_sys 2) (0, 1)
                    (Some (fault_corrupt false : FaultAction bool) :: nil) (1, 0)).
  { eapply fd_cons; [apply fs_fault_rule; reflexivity | apply fd_nil]. }
  split.
  - destruct (instantiated_combined_reduction 2 ex_robust _ 2 0 ex_robust_is_local Hder1)
      as [Heff | [Hbad _]]; [exact Heff | discriminate Hbad].
  - destruct (instantiated_combined_reduction 2 ex_robust _ 1 0 ex_robust_is_local Hder2)
      as [[Hbad _] | Hconf]; [discriminate Hbad | exact Hconf].
Qed.

(* =========================================================================
   5. Three refuting constructions (R-05-165, R-05-166, R-17-058b, R-17-058c).
   ========================================================================= *)

(* --- (i-a) Cross-share fault breaks unreduced-order d-probing security --- *)

Definition cross_share_circuit : Circuit :=
  g_in 0 :: g_in 1 :: g_op 1 (0 :: 1 :: nil) :: nil.

Definition cross_share_exp : Experiment :=
  mk_shared_experiment gf2 unit (tt :: nil) 1 cross_share_circuit gf2_ops
    (fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false)
    (fun _ _ _ => false).

(*| discharges: R-05-166, R-17-058c |*)
Theorem cross_share_fault_breaks_unreduced_probing :
  well_formed cross_share_circuit = true /\
  x_order cross_share_exp = 1 /\
  Leaks cross_share_exp ex_stable /\
  Leaks cross_share_exp ex_robust /\
  ~ UnreducedOrderSecure cross_share_exp ex_stable 1.
Proof.
  split; [reflexivity|].
  split; [reflexivity|].
  split.
  - intros H.
    specialize (H (probe_of 2 0 :: nil) eq_refl false true (false :: nil)).
    vm_compute in H. discriminate H.
  - split.
    + intros H.
      specialize (H (probe_of 2 0 :: nil) eq_refl false true
                    (false :: false :: false :: false :: nil)).
      vm_compute in H. discriminate H.
    + intros [_ H].
      specialize (H (probe_of 2 0 :: nil) eq_refl false true (false :: nil)).
      vm_compute in H. discriminate H.
Qed.

(* --- (i-b) Two-fault injection is outside budget 1 and breaks detection -- *)

Inductive RelaxedFaultStep {S F : Type} (sys : FaultStepSystem S F)
    : (S * nat) -> option (FaultAction F) -> (S * nat) -> Prop :=
  | rfs_step : forall s b,
      RelaxedFaultStep sys (s, b) None (fs_step sys s, b)
  | rfs_fault : forall s b act,
      fs_in_region sys s = true ->
      1 <= b ->
      RelaxedFaultStep sys (s, b) (Some act) (fs_fault sys s act, b - 1).

Inductive RelaxedDerivation {S F : Type} (sys : FaultStepSystem S F)
    : (S * nat) -> list (option (FaultAction F)) -> (S * nat) -> Prop :=
  | rfd_nil : forall cfg, RelaxedDerivation sys cfg nil cfg
  | rfd_cons : forall cfg1 opt cfg2 tr cfg3,
      RelaxedFaultStep sys cfg1 opt cfg2 ->
      RelaxedDerivation sys cfg2 tr cfg3 ->
      RelaxedDerivation sys cfg1 (opt :: tr) cfg3.

Definition two_fault_trace : list (option (FaultAction bool)) :=
  Some (fault_corrupt true) :: Some (fault_corrupt true) :: nil.

(* A two-fault injection cancelling an effective first fault's parity check. *)
Definition two_fault_token_ok (tr : list (option (FaultAction bool))) : bool :=
  Nat.even (fault_count tr).

(*| discharges: R-16-008f, R-17-058b, R-05-166 |*)
Theorem two_fault_injection_breaks_reduction :
  (~ exists s_end b_end,
       FaultDerivation (instantiated_sys 1) (0, 1) two_fault_trace (s_end, b_end)) /\
  (exists s_end b_end,
     RelaxedDerivation (instantiated_sys 1) (0, 2) two_fault_trace (s_end, b_end) /\
     two_fault_token_ok two_fault_trace = true).
Proof.
  split.
  - intros [s_end [b_end Hder]].
    exact (two_faults_have_no_derivation (instantiated_sys 1) 0 s_end b_end
             two_fault_trace (le_n 2) Hder).
  - exists 2, 0. split; [|reflexivity].
    eapply rfd_cons; [apply rfs_fault; [reflexivity | lia]|].
    eapply rfd_cons; [apply rfs_fault; [reflexivity | lia]|].
    apply rfd_nil.
Qed.

(* --- (ii) Missing token withholding on an effective fault violates detection - *)

Definition unwithheld_fault_activation : MaskedActivation := {|
  ma_state := nat;
  ma_fault := bool;
  ma_sys := instantiated_sys 1;
  ma_s0 := 0;
  ma_share := gf2;
  ma_aux := unit;
  ma_aux_enum := tt :: nil;
  ma_aux_nonempty := ltac:(discriminate);
  ma_order := 1;
  ma_token := bool;
  ma_token_eqb := bool_eqb;
  ma_token_eqb_refl := fun a => match a with true => eq_refl | false => eq_refl end;
  ma_token_eqb_sound := fun a b H =>
    match a, b return bool_eqb a b = true -> a = b with
    | true, true => fun _ => eq_refl
    | false, false => fun _ => eq_refl
    | true, false => fun H0 => match Bool.diff_true_false (eq_sym H0) with end
    | false, true => fun H0 => match Bool.diff_true_false (eq_sym H0) with end
    end H;
  ma_accept_token := true;
  ma_circuit := ma_circuit (instantiated_masked_activation 1);
  ma_ops := ma_ops (instantiated_masked_activation 1);
  ma_in := ma_in (instantiated_masked_activation 1);
  ma_init := ma_init (instantiated_masked_activation 1);
  ma_dom := ma_dom (instantiated_masked_activation 1);
  ma_emit_token := fun _ _ _ => true;
  ma_target_at := ma_target_at (instantiated_masked_activation 1);
  ma_effective_fault := ma_effective_fault (instantiated_masked_activation 1)
|}.

(*| discharges: R-16-008f, R-17-058d, R-05-166 |*)
Theorem missing_token_withholding_violates_detection_arm :
  (exists tr s_end b_end,
     FaultDerivation (ma_sys unwithheld_fault_activation)
       (ma_s0 unwithheld_fault_activation, 1) tr (s_end, b_end) /\
     ma_effective_fault unwithheld_fault_activation (classify_trace tr) = true /\
     ~ EffectiveDetectedArm unwithheld_fault_activation (classify_trace tr) /\
     ~ ShareConfinedProbingArm unwithheld_fault_activation ex_stable (classify_trace tr)) /\
  ~ ConformingMaskedDatapath unwithheld_fault_activation.
Proof.
  assert (Hder : FaultDerivation (ma_sys unwithheld_fault_activation) (0, 1)
                   (Some (fault_skip : FaultAction bool) :: nil) (1, 0)).
  { eapply fd_cons; [apply fs_fault_rule; reflexivity | apply fd_nil]. }
  split.
  - exists (Some (fault_skip : FaultAction bool) :: nil), 1, 0.
    split; [exact Hder|].
    split; [reflexivity|].
    split.
    + intros [_ Hwith]. specialize (Hwith false (false :: nil, tt)).
      vm_compute in Hwith. discriminate Hwith.
    + intros [Hfalse _]. discriminate Hfalse.
  - intros Hcmd.
    pose proof (cmd_effective_withheld unwithheld_fault_activation Hcmd
                  (Some (fault_skip : FaultAction bool) :: nil) 1 0 0 fault_skip
                  Hder eq_refl eq_refl false (false :: nil, tt)) as Hwith.
    vm_compute in Hwith. discriminate Hwith.
Qed.

(* --- (iii) A weakened (d - 1)-order claim fails the unreduced-order predicate - *)

Definition weakened_order_exp (d : nat) : Experiment := {|
  x_share := gf2;
  x_prob := ShareMaskTapes gf2 unit (tt :: nil) d;
  x_circuit := checked_masked_circuit d;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false;
  x_init := fun s '(masks, _) w =>
    if Nat.ltb w (S d) then false else at_member (encode gf2 s masks) (w - S d) false;
  x_order := d - 1
|}.

Definition two_share_at_order_two_exp : Experiment := {|
  x_share := gf2;
  x_prob := ShareMaskTapes gf2 unit (tt :: nil) 1;
  x_circuit := input_wires_circuit 2;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false;
  x_init := fun _ _ _ => false;
  x_order := 2
|}.

(*| discharges: R-17-058d, R-15-053a, R-05-165, R-05-166 |*)
Theorem weakened_order_claim_fails_unreduced_predicate :
  (forall d : nat, 1 <= d -> ~ UnreducedOrderSecure (weakened_order_exp d) ex_stable d) /\
  (forall ps : list Probe,
     admissible_probes (x_circuit two_share_at_order_two_exp) 1 ps = true ->
     forall s1 s2 : bool,
       SameDistribution (x_prob two_share_at_order_two_exp) (list bool) (list_eqb bool_eqb)
         (x_view two_share_at_order_two_exp ex_stable ps s1)
         (x_view two_share_at_order_two_exp ex_stable ps s2)) /\
  ~ UnreducedOrderSecure two_share_at_order_two_exp ex_stable 2.
Proof.
  split.
  - intros d Hd [Hord _]. simpl in Hord. lia.
  - split.
    + intros ps Hadm s1 s2.
      assert (Hsl : ShareLocalized gf2 unit (tt :: nil) 1 (input_wires_circuit 2) gf2_ops
                      (fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false)
                      (fun _ _ _ => false) (fun w => w)).
      { constructor.
        - apply input_wires_well_formed.
        - intros w Hw. rewrite input_wires_count in Hw. exact Hw.
        - intros w Hw. rewrite input_wires_count in Hw.
          rewrite input_wires_gate_at by exact Hw. exact I.
        - intros w i a1 a2 masks1 masks2 aux t Hw Eg Hsh.
          rewrite input_wires_count in Hw. rewrite input_wires_gate_at in Eg by exact Hw.
          inversion Eg. subst i. exact Hsh.
        - intros w a1 a2 masks1 masks2 aux Hw Hsh. reflexivity. }
      destruct (share_localized_unreduced_probing_secure
                  gf2 unit (tt :: nil) 1 (input_wires_circuit 2) gf2_ops
                  (fun s '(masks, _) _ i => at_member (encode gf2 s masks) i false)
                  (fun _ _ _ => false) (fun w => w) ex_stable ex_stable_is_local Hsl)
        as [_ Hsec].
      exact (Hsec ps Hadm s1 s2).
    + intros [_ Hsec].
      specialize (Hsec (probe_of 0 0 :: probe_of 1 0 :: nil) eq_refl false true
                       (false :: false :: nil)).
      vm_compute in Hsec. discriminate Hsec.
Qed.
