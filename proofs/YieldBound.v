(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   YieldBound.v

   Q34d yield-point placement, strip-mining, sink-before-yield lowering,
   compositional per-function reaction-cost verification, static cost-counter
   protocol, and TAL-014 cost-facet expressiveness extending
   [ElasticDomain.v](ElasticDomain.v) (`R-07-037h`, `R-05-102`, `R-11-015`).

   Non-vacuity and assumption discipline (`R-05-163`, `R-05-164`, `R-05-165`,
   `R-05-166`):
   - Every record declared here is inhabited by a closed top-level
     `Definition witness_<Record> : <Record> := ...`.
   - Every obligation is paired with concrete multi-function witnesses and
     distinguishing refutations.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-102 R-05-163 R-05-164 R-05-165 R-05-166 R-07-037h R-11-015
   SHA256: cbfa1b9fefb80bccd4a9db98e847f3b7df6b1948465e8926ec28e517494b43a5
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia PeanoNat.
Require Import PartitionContext CyclicExecutive MemoryPlan ElasticDomain.
Import ListNotations.

Local Open Scope nat_scope.

(* =========================================================================
   S1. Poll-site placement and strip-mining (`R-07-037h`, `R-05-102`).
   ========================================================================= *)

(* The CFG poll-placement pass marks every loop back-edge target (over the
   enumerated node list `nodes`) and every recursive-call entry as a poll site,
   while preserving existing poll sites. *)
Definition place_polls (g : Cfg) (nodes : list nat) : Cfg := {|
  cfg_edge := cfg_edge g;
  cfg_back := cfg_back g;
  cfg_recursive_entry := cfg_recursive_entry g;
  cfg_poll := fun v =>
    cfg_poll g v || any_of (fun u => cfg_back g u v) nodes || cfg_recursive_entry g v;
  cfg_yield := cfg_yield g;
  cfg_sink := cfg_sink g;
  cfg_entry := cfg_entry g;
  cfg_exit := cfg_exit g;
  cfg_cost := cfg_cost g
|}.

Lemma any_of_in_intro : forall (A : Type) (p : A -> bool) (l : list A) (x : A),
  In x l -> p x = true -> any_of p l = true.
Proof.
  intros A p l x. induction l as [ | y r IH ]; intros Hin Hp.
  - destruct Hin.
  - simpl. apply orb_true_intro. destruct Hin as [ Heq | Hin ].
    + left. subst y. exact Hp.
    + right. exact (IH Hin Hp).
Qed.

(*| discharges: R-07-037h |*)
Theorem place_polls_covers_back_edges :
  forall (g : Cfg) (nodes : list nat),
    (forall u v, cfg_back g u v = true -> In u nodes) ->
    PollsEveryBackEdge (place_polls g nodes).
Proof.
  intros g nodes Hcov u v Hback. simpl.
  apply orb_true_intro. left. apply orb_true_intro. right.
  exact (any_of_in_intro nat (fun w => cfg_back g w v) nodes u (Hcov u v Hback) Hback).
Qed.

(*| discharges: R-07-037h |*)
Theorem place_polls_covers_recursive_entries :
  forall (g : Cfg) (nodes : list nat),
    PollsEveryRecursiveEntry (place_polls g nodes).
Proof.
  intros g nodes v Hrec. simpl.
  apply orb_true_intro. right. exact Hrec.
Qed.

Record StripMineSpec : Type := {
  sm_k : nat;
  sm_body_cost : nat;
  sm_poll_cost : nat;
  sm_yield_bound : nat
}.

Definition strip_mine_reaction_cost (s : StripMineSpec) : nat :=
  sm_k s * sm_body_cost s + sm_poll_cost s.

Definition strip_mine_admits (s : StripMineSpec) : bool :=
  Nat.leb 1 (sm_k s) && Nat.leb (strip_mine_reaction_cost s) (sm_yield_bound s).

Definition StripMineAdmits (s : StripMineSpec) : Prop :=
  1 <= sm_k s /\ strip_mine_reaction_cost s <= sm_yield_bound s.

Lemma strip_mine_admits_iff : forall s : StripMineSpec,
  strip_mine_admits s = true <-> StripMineAdmits s.
Proof.
  intros s. unfold strip_mine_admits, StripMineAdmits.
  rewrite andb_true_iff, !Nat.leb_le. reflexivity.
Qed.

Record LoopSpec : Type := {
  lp_strip : StripMineSpec;
  lp_entry_cost : nat;
  lp_exit_cost : nat;
  lp_sink_cost : nat;
  lp_yield_site_cost : nat
}.

(* Concrete strip-mined loop CFG:
   0 = entry, 1 = loop header (tentative poll), 2 = unrolled body (k * body_cost),
   3 = exit, 4 = sink, 5 = real yield resuming at 1. *)
Definition strip_mine_edge (u v : nat) : bool :=
  match u, v with
  | 0, 1 => true | 1, 2 => true | 2, 1 => true | 1, 3 => true
  | 1, 4 => true | 4, 5 => true | 5, 1 => true
  | _, _ => false
  end.

Definition strip_mine_back (u v : nat) : bool :=
  match u, v with 2, 1 => true | 5, 1 => true | _, _ => false end.

Definition strip_mine_cost (ls : LoopSpec) (v : nat) : nat :=
  match v with
  | 0 => lp_entry_cost ls
  | 1 => sm_poll_cost (lp_strip ls)
  | 2 => sm_k (lp_strip ls) * sm_body_cost (lp_strip ls)
  | 3 => lp_exit_cost ls
  | 4 => lp_sink_cost ls
  | 5 => lp_yield_site_cost ls
  | _ => 0
  end.

Definition strip_mine_cfg (ls : LoopSpec) : Cfg := {|
  cfg_edge := strip_mine_edge;
  cfg_back := strip_mine_back;
  cfg_recursive_entry := fun _ => false;
  cfg_poll := fun v => Nat.eqb v 1 || Nat.eqb v 5;
  cfg_yield := fun v => Nat.eqb v 5;
  cfg_sink := fun v => Nat.eqb v 4;
  cfg_entry := 0;
  cfg_exit := fun v => Nat.eqb v 3;
  cfg_cost := strip_mine_cost ls
|}.

Lemma strip_mine_sinks_yield : forall ls : LoopSpec,
  SinksYieldWithinOneReaction (strip_mine_cfg ls).
Proof.
  intros ls. split.
  - intros v Hs Hp. cbn in Hs, Hp. apply Nat.eqb_eq in Hs. subst v. discriminate Hp.
  - intros v inner [ Hs [ _ [ Hc Hi ] ] ]. cbn in Hs. apply Nat.eqb_eq in Hs. subst v.
    destruct inner as [ | x rest ].
    + split; [ reflexivity | ]. intros w Hw Hp.
      destruct w as [ | [ | [ | [ | [ | [ | w ] ] ] ] ] ];
        cbn in Hw, Hp |- *; try discriminate Hw; try discriminate Hp; reflexivity.
    + exfalso. destruct (path_head _ _ _ _ Hc Hi) as [ Hx4 Hx ].
      destruct x as [ | [ | [ | [ | [ | [ | x ] ] ] ] ] ];
        cbn in Hx4, Hx; try discriminate Hx4; discriminate Hx.
Qed.

Theorem strip_mine_cfg_admitted :
  forall ls : LoopSpec,
    StripMineAdmits (lp_strip ls) ->
    lp_entry_cost ls <= sm_yield_bound (lp_strip ls) ->
    sm_poll_cost (lp_strip ls) + lp_exit_cost ls <= sm_yield_bound (lp_strip ls) ->
    sm_poll_cost (lp_strip ls) + lp_sink_cost ls <= sm_yield_bound (lp_strip ls) ->
    lp_yield_site_cost ls <= sm_yield_bound (lp_strip ls) ->
    YieldBoundAdmits (strip_mine_cfg ls) (sm_yield_bound (lp_strip ls)).
Proof.
  intros ls [ Hk Hbody ] Hent Hext Hsnk Hyld.
  unfold strip_mine_reaction_cost in Hbody.
  split; [ | split; [ | split ] ].
  - intros u v H.
    destruct u as [ | [ | [ | [ | [ | [ | u ] ] ] ] ] ]; destruct v as [ | [ | v ] ];
      cbn in H; try discriminate H; reflexivity.
  - intros v H. cbn in H. discriminate H.
  - apply paths_within_reactions. intros from inner Hc Hi. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + destruct from as [ | [ | [ | [ | [ | [ | from ] ] ] ] ] ]; cbn; lia.
    + destruct (path_head _ _ _ _ Hc Hi) as [ Hfx Hx ].
      destruct from as [ | [ | [ | [ | [ | [ | from ] ] ] ] ] ];
        destruct x as [ | [ | [ | [ | [ | [ | x ] ] ] ] ] ];
        cbn in Hfx, Hx |- *; try discriminate Hfx; try discriminate Hx; lia.
    + exfalso. destruct (path_pair _ _ _ _ _ Hc Hi) as [ Hxy [ Hx Hy ] ].
      destruct x as [ | [ | [ | [ | [ | [ | x ] ] ] ] ] ];
        destruct y as [ | [ | [ | [ | [ | [ | y ] ] ] ] ] ];
        cbn in Hxy, Hx, Hy; try discriminate Hxy; try discriminate Hx; discriminate Hy.
  - exact (strip_mine_sinks_yield ls).
Qed.

Definition total_polls (iters k : nat) : nat :=
  if Nat.eqb k 0 then 0 else (iters + (k - 1)) / k.

Definition strip_mine_poll_overhead (iters k poll_cost : nat) : nat :=
  total_polls iters k * poll_cost.

Theorem strip_mining_reduces_poll_overhead :
  forall iters k poll_cost : nat,
    1 <= k ->
    strip_mine_poll_overhead iters k poll_cost <= iters * poll_cost.
Proof.
  intros iters k poll_cost Hk.
  unfold strip_mine_poll_overhead, total_polls.
  destruct (Nat.eqb k 0) eqn:Ek.
  - apply Nat.eqb_eq in Ek. lia.
  - apply Nat.mul_le_mono_r. destruct iters as [ | m ].
    + simpl. rewrite Nat.div_small; lia.
    + apply Nat.Div0.div_le_upper_bound. nia.
Qed.

(* =========================================================================
   S2. Sink-before-yield lowering on `switch-requested` (`R-07-037h`).
   ========================================================================= *)

(* Given a sink node `s`, a fresh real-yield node `y` (`s <> y`), and a
   resume target `resume`, route `s -> y -> resume`, marking `s` as non-poll,
   non-exit sink and `y` as a real yield. *)
Definition lower_sink_before_yield
    (g : Cfg) (s y resume y_cost : nat) : Cfg := {|
  cfg_edge := fun u v =>
    if Nat.eqb u s then Nat.eqb v y
    else if Nat.eqb u y then Nat.eqb v resume
    else cfg_edge g u v;
  cfg_back := fun u v =>
    if Nat.eqb u s then false
    else if Nat.eqb u y then cfg_back g s v && Nat.eqb v resume
    else cfg_back g u v;
  cfg_recursive_entry := cfg_recursive_entry g;
  cfg_poll := fun v =>
    if Nat.eqb v y then true
    else if Nat.eqb v s then false
    else cfg_poll g v;
  cfg_yield := fun v =>
    if Nat.eqb v y then true else cfg_yield g v;
  cfg_sink := fun v => Nat.eqb v s;
  cfg_entry := cfg_entry g;
  cfg_exit := fun v =>
    if Nat.eqb v s || Nat.eqb v y then false else cfg_exit g v;
  cfg_cost := fun v => if Nat.eqb v y then y_cost else cfg_cost g v
|}.

(*| discharges: R-07-037h |*)
Theorem lower_sink_establishes_sinks_yield :
  forall (g : Cfg) (s y resume y_cost : nat),
    s <> y ->
    SinksYieldWithinOneReaction (lower_sink_before_yield g s y resume y_cost).
Proof.
  intros g s y resume y_cost Hne. split.
  - intros v Hs Hp. cbn in Hs, Hp. apply Nat.eqb_eq in Hs. subst v.
    destruct (Nat.eqb s y) eqn:Esy.
    + apply Nat.eqb_eq in Esy. contradiction.
    + rewrite Nat.eqb_refl in Hp. discriminate Hp.
  - intros v inner [ Hs [ _ [ Hc Hi ] ] ]. cbn in Hs. apply Nat.eqb_eq in Hs. subst v.
    destruct inner as [ | x rest ].
    + split.
      * cbn. rewrite Nat.eqb_refl. reflexivity.
      * intros w Hw Hp. cbn in Hw. rewrite Nat.eqb_refl in Hw.
        apply Nat.eqb_eq in Hw. subst w. cbn. rewrite Nat.eqb_refl. reflexivity.
    + exfalso. destruct (path_head _ _ _ _ Hc Hi) as [ Hsx Hx ].
      cbn in Hsx, Hx. rewrite Nat.eqb_refl in Hsx. apply Nat.eqb_eq in Hsx. subst x.
      rewrite Nat.eqb_refl in Hx. discriminate Hx.
Qed.

Theorem lower_sink_preserves_polls :
  forall (g : Cfg) (s y resume y_cost : nat),
    s <> y ->
    cfg_recursive_entry g s = false ->
    PollsEveryBackEdge g ->
    PollsEveryRecursiveEntry g ->
    (forall u v, cfg_back g u v = true -> v <> s) ->
    PollsEveryBackEdge (lower_sink_before_yield g s y resume y_cost)
    /\ PollsEveryRecursiveEntry (lower_sink_before_yield g s y resume y_cost).
Proof.
  intros g s y resume y_cost Hne Hrec Hback Hrec_ok Hnot_s. split.
  - intros u v Hb. cbn in Hb |- *.
    destruct (Nat.eqb u s) eqn:Eus; [ discriminate Hb | ].
    destruct (Nat.eqb u y) eqn:Euy.
    + apply andb_prop in Hb. destruct Hb as [ Hbs _ ].
      assert (Hvne : v <> s) by exact (Hnot_s s v Hbs).
      destruct (Nat.eqb v y) eqn:Evy; [ reflexivity | ].
      destruct (Nat.eqb v s) eqn:Evs; [ apply Nat.eqb_eq in Evs; contradiction | ].
      exact (Hback s v Hbs).
    + assert (Hvne : v <> s) by exact (Hnot_s u v Hb).
      destruct (Nat.eqb v y) eqn:Evy; [ reflexivity | ].
      destruct (Nat.eqb v s) eqn:Evs; [ apply Nat.eqb_eq in Evs; contradiction | ].
      exact (Hback u v Hb).
  - intros v Hr. cbn in Hr |- *.
    destruct (Nat.eqb v y) eqn:Evy; [ reflexivity | ].
    destruct (Nat.eqb v s) eqn:Evs.
    + apply Nat.eqb_eq in Evs. subst v. rewrite Hrec in Hr. discriminate Hr.
    + exact (Hrec_ok v Hr).
Qed.

(* =========================================================================
   S3. Per-function cost triple and compositional soundness (`R-07-037h`,
   `R-05-102`, `R-11-015`).
   ========================================================================= *)

Record FnCostTriple : Type := {
  fn_entry_to_first_poll : nat;
  fn_poll_to_poll : nat;
  fn_last_poll_to_exit : nat;
  fn_has_internal_poll : bool
}.

Definition fn_full_cost (t : FnCostTriple) : nat := fn_entry_to_first_poll t.

Definition fn_triple_within (t : FnCostTriple) (Y : nat) : bool :=
  Nat.leb (fn_entry_to_first_poll t) Y
  && Nat.leb (fn_poll_to_poll t) Y
  && Nat.leb (fn_last_poll_to_exit t) Y.

Record CallSiteCheck : Type := {
  cs_pre_cost : nat;
  cs_callee : FnCostTriple;
  cs_post_cost : nat;
  cs_recursive : bool
}.

Definition call_site_admits (cs : CallSiteCheck) (Y : nat) : bool :=
  let t := cs_callee cs in
  if fn_has_internal_poll t
  then Nat.leb (cs_pre_cost cs + fn_entry_to_first_poll t) Y
       && Nat.leb (fn_poll_to_poll t) Y
       && Nat.leb (fn_last_poll_to_exit t + cs_post_cost cs) Y
  else negb (cs_recursive cs)
       && Nat.leb (cs_pre_cost cs + fn_full_cost t + cs_post_cost cs) Y.

Definition CallSiteAdmits (cs : CallSiteCheck) (Y : nat) : Prop :=
  let t := cs_callee cs in
  if fn_has_internal_poll t
  then cs_pre_cost cs + fn_entry_to_first_poll t <= Y
       /\ fn_poll_to_poll t <= Y
       /\ fn_last_poll_to_exit t + cs_post_cost cs <= Y
  else cs_recursive cs = false
       /\ cs_pre_cost cs + fn_full_cost t + cs_post_cost cs <= Y.

Lemma call_site_admits_iff : forall (cs : CallSiteCheck) (Y : nat),
  call_site_admits cs Y = true <-> CallSiteAdmits cs Y.
Proof.
  intros cs Y. unfold call_site_admits, CallSiteAdmits.
  destruct (fn_has_internal_poll (cs_callee cs)).
  - rewrite !andb_true_iff, !Nat.leb_le. tauto.
  - rewrite andb_true_iff, negb_true_iff, Nat.leb_le. reflexivity.
Qed.

Record FnSummary : Type := {
  fn_intra_reactions : list nat;
  fn_calls : list CallSiteCheck;
  fn_triple : FnCostTriple
}.

(* Inductive whole-program expanded trace across multi-function calls. *)
Inductive CallExpandedTrace : Type :=
| TrNoPoll (full_cost : nat)
| TrWithPoll (e_cost : nat) (mid_reactions : list nat) (x_cost : nat).

Definition TraceMatchesTriple (tr : CallExpandedTrace) (t : FnCostTriple) : Prop :=
  match tr with
  | TrNoPoll full_cost =>
      fn_has_internal_poll t = false /\ full_cost <= fn_full_cost t
  | TrWithPoll e_cost mid_reactions x_cost =>
      fn_has_internal_poll t = true
      /\ e_cost <= fn_entry_to_first_poll t
      /\ all_of (fun r => Nat.leb r (fn_poll_to_poll t)) mid_reactions = true
      /\ x_cost <= fn_last_poll_to_exit t
  end.

Definition expand_call_reactions (cs : CallSiteCheck) (tr : CallExpandedTrace) : list nat :=
  match tr with
  | TrNoPoll full_cost => (cs_pre_cost cs + full_cost + cs_post_cost cs) :: nil
  | TrWithPoll e_cost mid_reactions x_cost =>
      (cs_pre_cost cs + e_cost) :: mid_reactions ++ (x_cost + cs_post_cost cs) :: nil
  end.

Inductive ProgStep : Type :=
| StepIntra (cost : nat)
| StepCall (cs : CallSiteCheck) (tr : CallExpandedTrace).

Definition step_reactions (st : ProgStep) : list nat :=
  match st with
  | StepIntra r => r :: nil
  | StepCall cs tr => expand_call_reactions cs tr
  end.

Fixpoint prog_reactions (steps : list ProgStep) : list nat :=
  match steps with
  | nil => nil
  | st :: rest => step_reactions st ++ prog_reactions rest
  end.

Definition StepAdmitted (Y : nat) (st : ProgStep) : Prop :=
  match st with
  | StepIntra r => r <= Y
  | StepCall cs tr => TraceMatchesTriple tr (cs_callee cs) /\ CallSiteAdmits cs Y
  end.

Lemma all_of_app_true : forall (A : Type) (p : A -> bool) (l1 l2 : list A),
  all_of p l1 = true -> all_of p l2 = true -> all_of p (l1 ++ l2) = true.
Proof.
  intros A p l1 l2 H1 H2. induction l1 as [ | x r IH ]; [ exact H2 | ].
  simpl in *. apply andb_prop in H1. destruct H1 as [ Hx Hr ].
  apply andb_true_intro. split; [ exact Hx | exact (IH Hr) ].
Qed.

Lemma step_reactions_bounded : forall (Y : nat) (st : ProgStep),
  StepAdmitted Y st ->
  forall r, In r (step_reactions st) -> r <= Y.
Proof.
  intros Y [ cost | cs tr ] Hadm r Hr.
  - destruct Hr as [ Heq | [] ]. subst r. exact Hadm.
  - destruct Hadm as [ Hmatch Hadm ].
    destruct tr as [ full_cost | e_cost mid_reactions x_cost ].
    + destruct Hmatch as [ Hno Hfull ].
      unfold CallSiteAdmits in Hadm. simpl in Hadm, Hr. rewrite Hno in Hadm.
      destruct Hadm as [ _ Hbd ]. destruct Hr as [ Heq | [] ].
      subst r. lia.
    + destruct Hmatch as [ Hpoll [ He [ Hmid Hx ] ] ].
      unfold CallSiteAdmits in Hadm. simpl in Hadm. rewrite Hpoll in Hadm.
      destruct Hadm as [ Hpre [ Hmid_b Hpost ] ].
      simpl in Hr. destruct Hr as [ Heq | Hr ].
      * subst r. lia.
      * apply in_app_or in Hr. destruct Hr as [ Hrm | Hrx ].
        -- pose proof (all_of_in _ _ _ _ Hmid Hrm) as Hle.
           apply Nat.leb_le in Hle. lia.
        -- destruct Hrx as [ Heq | [] ]. subst r. lia.
Qed.

(*| discharges: R-07-037h, R-05-102 |*)
Theorem compositional_soundness :
  forall (Y : nat) (steps : list ProgStep),
    (forall st, In st steps -> StepAdmitted Y st) ->
    forall r, In r (prog_reactions steps) -> r <= Y.
Proof.
  intros Y steps Hall r Hr. induction steps as [ | st rest IH ].
  - destruct Hr.
  - simpl in Hr. apply in_app_or in Hr. destruct Hr as [ Hst | Hrest ].
    + exact (step_reactions_bounded Y st (Hall st (or_introl eq_refl)) r Hst).
    + apply IH; [ | exact Hrest ].
      intros st' Hin. exact (Hall st' (or_intror Hin)).
Qed.

(* Nested-call composition: calling an internal-poll callee inside a poll-free
   wrapper `pre_w` .. `post_w` preserves `TraceMatchesTriple` for the
   wrapper's own `FnCostTriple`, and similarly for a poll-free callee. *)
Theorem nested_polled_call_preserves_triple :
  forall (pre_w post_w : nat) (tc : FnCostTriple) (tr : CallExpandedTrace),
    fn_has_internal_poll tc = true ->
    TraceMatchesTriple tr tc ->
    exists tr_w,
      TraceMatchesTriple tr_w
        {| fn_entry_to_first_poll := pre_w + fn_entry_to_first_poll tc;
           fn_poll_to_poll := fn_poll_to_poll tc;
           fn_last_poll_to_exit := fn_last_poll_to_exit tc + post_w;
           fn_has_internal_poll := true |}.
Proof.
  intros pre_w post_w tc [ full | e mid x ] Hpoll Hmatch.
  - destruct Hmatch as [ Hno _ ]. rewrite Hno in Hpoll. discriminate Hpoll.
  - destruct Hmatch as [ _ [ He [ Hmid Hx ] ] ].
    exists (TrWithPoll (pre_w + e) mid (x + post_w)).
    cbn. repeat split; try assumption; lia.
Qed.

Theorem nested_direct_call_preserves_triple :
  forall (pre_w full_c post_w : nat) (tc : FnCostTriple) (tr : CallExpandedTrace),
    fn_has_internal_poll tc = false ->
    fn_full_cost tc = full_c ->
    TraceMatchesTriple tr tc ->
    exists tr_w,
      TraceMatchesTriple tr_w
        {| fn_entry_to_first_poll := pre_w + full_c + post_w;
           fn_poll_to_poll := 0;
           fn_last_poll_to_exit := pre_w + full_c + post_w;
           fn_has_internal_poll := false |}.
Proof.
  intros pre_w full_c post_w tc [ full | e mid x ] Hno Hfull Hmatch.
  - destruct Hmatch as [ _ Hle ].
    exists (TrNoPoll (pre_w + full + post_w)).
    cbn. unfold fn_full_cost. cbn. split; [ reflexivity | ].
    rewrite Hfull in Hle. lia.
  - destruct Hmatch as [ Hp _ ]. rewrite Hp in Hno. discriminate Hno.
Qed.

(* -------------------------------------------------------------------------
   Concrete CFG inlining (`inline_call_cfg`) and `YieldBoundAdmits` discharge.
   Caller node `u` maps to `2 * u`; callee node `v` maps to `2 * v + 1`.
   ------------------------------------------------------------------------- *)

Definition FnTripleSound (g : Cfg) (t : FnCostTriple) : Prop :=
  (cfg_poll g (cfg_entry g) = false ->
   forall inner to, Reaction g (cfg_entry g) inner to ->
     reaction_cost g (cfg_entry g) inner <= fn_entry_to_first_poll t)
  /\ (forall from inner to, cfg_poll g from = true -> Reaction g from inner to ->
        reaction_cost g from inner <= fn_poll_to_poll t)
  /\ (forall from inner, cfg_poll g from = true -> ExitReaction g from inner ->
        reaction_cost g from inner <= fn_last_poll_to_exit t)
  /\ (if fn_has_internal_poll t
      then cfg_poll g (cfg_entry g) = true
           \/ forall inner, ~ ExitReaction g (cfg_entry g) inner
      else (forall inner to, ~ Reaction g (cfg_entry g) inner to)
           /\ (forall inner, ExitReaction g (cfg_entry g) inner ->
                 reaction_cost g (cfg_entry g) inner <= fn_entry_to_first_poll t)
           /\ fn_last_poll_to_exit t = fn_entry_to_first_poll t).

Definition inline_call_cfg (caller : Cfg) (call_pre call_post : nat) (callee : Cfg) : Cfg := {|
  cfg_edge := fun x y =>
    if Nat.even x
    then if Nat.even y
         then cfg_edge caller (x / 2) (y / 2)
              && negb (Nat.eqb (x / 2) call_pre && Nat.eqb (y / 2) call_post)
         else Nat.eqb (x / 2) call_pre && Nat.eqb (y / 2) (cfg_entry callee)
    else if Nat.even y
         then cfg_exit callee (x / 2) && Nat.eqb (y / 2) call_post
         else cfg_edge callee (x / 2) (y / 2);
  cfg_back := fun x y =>
    if Nat.even x && Nat.even y then cfg_back caller (x / 2) (y / 2)
    else if negb (Nat.even x) && negb (Nat.even y) then cfg_back callee (x / 2) (y / 2)
    else false;
  cfg_recursive_entry := fun x =>
    if Nat.even x then cfg_recursive_entry caller (x / 2)
    else cfg_recursive_entry callee (x / 2);
  cfg_poll := fun x =>
    if Nat.even x then cfg_poll caller (x / 2) else cfg_poll callee (x / 2);
  cfg_yield := fun x =>
    if Nat.even x then cfg_yield caller (x / 2) else cfg_yield callee (x / 2);
  cfg_sink := fun x =>
    if Nat.even x then cfg_sink caller (x / 2) else cfg_sink callee (x / 2);
  cfg_entry := 2 * cfg_entry caller;
  cfg_exit := fun x =>
    if Nat.even x then cfg_exit caller (x / 2) else false;
  cfg_cost := fun x =>
    if Nat.even x then cfg_cost caller (x / 2) else cfg_cost callee (x / 2)
|}.

Lemma even_2n : forall n : nat, Nat.even (2 * n) = true.
Proof. intros n. rewrite Nat.even_mul. reflexivity. Qed.

Lemma even_2n_1 : forall n : nat, Nat.even (2 * n + 1) = false.
Proof. intros n. replace (2 * n + 1) with (S (2 * n)) by lia.
  rewrite Nat.even_succ, Nat.odd_mul. reflexivity.
Qed.

Lemma div2_2n : forall n : nat, (2 * n) / 2 = n.
Proof. intros n. rewrite Nat.mul_comm. apply Nat.div_mul. lia. Qed.

Lemma div2_2n_1 : forall n : nat, (2 * n + 1) / 2 = n.
Proof.
  intros n. replace (2 * n + 1) with (1 + n * 2) by lia.
  rewrite Nat.div_add; [ simpl; lia | lia ].
Qed.

Lemma even_decomp : forall x : nat,
  (exists n, x = 2 * n /\ Nat.even x = true /\ x / 2 = n)
  \/ (exists n, x = 2 * n + 1 /\ Nat.even x = false /\ x / 2 = n).
Proof.
  intros x. induction x as [ x IH ] using lt_wf_ind.
  destruct x as [ | [ | x' ] ].
  - left. exists 0. repeat split; reflexivity.
  - right. exists 0. repeat split; reflexivity.
  - destruct (IH x' ltac:(lia)) as [ [ n [ Hx [ He Hd ] ] ] | [ n [ Hx [ He Hd ] ] ] ].
    + left. exists (S n). repeat split; try lia.
      * replace (S (S x')) with (2 * S n) by lia. apply even_2n.
      * replace (S (S x')) with (2 * S n) by lia. apply div2_2n.
    + right. exists (S n). repeat split; try lia.
      * replace (S (S x')) with (2 * S n + 1) by lia. apply even_2n_1.
      * replace (S (S x')) with (2 * S n + 1) by lia. apply div2_2n_1.
Qed.

Definition CallContextSound
    (caller : Cfg) (call_pre call_post pre post : nat) : Prop :=
  cfg_poll caller call_pre = false
  /\ cfg_exit caller call_pre = false
  /\ (forall from inner,
        (Nat.eqb from (cfg_entry caller) || cfg_poll caller from) = true ->
        all_of (fun v => negb (cfg_poll caller v)) inner = true ->
        chain caller from inner = true ->
        last inner from = call_pre ->
        reaction_cost caller from inner <= pre)
  /\ (forall inner to,
        cfg_poll caller call_post = false ->
        all_of (fun v => negb (cfg_poll caller v)) inner = true ->
        chain caller call_post (inner ++ [to]) = true ->
        cfg_poll caller to = true ->
        reaction_cost caller call_post inner <= post)
  /\ (forall inner,
        cfg_poll caller call_post = false ->
        all_of (fun v => negb (cfg_poll caller v)) inner = true ->
        chain caller call_post inner = true ->
        cfg_exit caller (last inner call_post) = true ->
        reaction_cost caller call_post inner <= post)
  /\ (forall inner,
        chain caller call_post inner = true ->
        all_of (fun v => negb (cfg_poll caller v)) inner = true ->
        ~ In call_pre (call_post :: inner))
  /\ (forall v inner, SinkPath caller v inner -> ~ In call_pre (v :: inner)).

Lemma inline_preserves_polls :
  forall caller call_pre call_post callee,
    PollsEveryBackEdge caller -> PollsEveryBackEdge callee ->
    PollsEveryRecursiveEntry caller -> PollsEveryRecursiveEntry callee ->
    PollsEveryBackEdge (inline_call_cfg caller call_pre call_post callee)
    /\ PollsEveryRecursiveEntry (inline_call_cfg caller call_pre call_post callee).
Proof.
  intros caller call_pre call_post callee Hbc1 Hbc2 Hrc1 Hrc2. split.
  - intros x y Hb. cbn in Hb |- *.
    destruct (Nat.even x) eqn:Ex; destruct (Nat.even y) eqn:Ey; cbn in Hb.
    + exact (Hbc1 _ _ Hb).
    + discriminate Hb.
    + discriminate Hb.
    + exact (Hbc2 _ _ Hb).
  - intros x Hr. cbn in Hr |- *.
    destruct (Nat.even x) eqn:Ex; [ exact (Hrc1 _ Hr) | exact (Hrc2 _ Hr) ].
Qed.

(* Clean path-classification lemma for pure caller/callee paths in `inline_call_cfg`. *)
Lemma last_in : forall (A : Type) (l : list A) (d : A),
  l <> nil -> In (last l d) l.
Proof.
  intros A l d. induction l as [ | a r IH ]; intros Hne.
  - exfalso. apply Hne. reflexivity.
  - destruct r as [ | b r' ].
    + left. reflexivity.
    + right. apply IH. discriminate.
Qed.

Lemma last_app_nonnil : forall (A : Type) (l1 l2 : list A) (d : A),
  l2 <> nil -> last (l1 ++ l2) d = last l2 d.
Proof.
  intros A l1 l2 d Hne. induction l1 as [ | a r IH ]; [ reflexivity | ].
  simpl. destruct (r ++ l2) eqn:E.
  - destruct r; simpl in E; [ exfalso; apply Hne; exact E | discriminate E ].
  - exact IH.
Qed.

Ltac unfold_inline_in H :=
  cbn [cfg_edge cfg_back cfg_recursive_entry cfg_poll cfg_yield cfg_sink cfg_entry cfg_exit cfg_cost inline_call_cfg] in H.

Lemma chain_inline_caller_step :
  forall caller call_pre call_post callee u z,
    cfg_edge (inline_call_cfg caller call_pre call_post callee) (2 * u) z = true ->
    (exists u', z = 2 * u' /\ cfg_edge caller u u' = true
                /\ ~ (u = call_pre /\ u' = call_post))
    \/ (u = call_pre /\ z = 2 * cfg_entry callee + 1).
Proof.
  intros caller call_pre call_post callee u z He. unfold_inline_in He.
  rewrite even_2n, div2_2n in He.
  destruct (even_decomp z) as [ [ u' [ Hz [ Ez Dz ] ] ] | [ v' [ Hz [ Ez Dz ] ] ] ].
  - subst z. rewrite Ez, div2_2n in He.
    apply andb_prop in He. destruct He as [ Hce Hne ].
    apply negb_true_iff in Hne. apply andb_false_iff in Hne.
    left. exists u'. split; [ reflexivity | split; [ exact Hce | ] ].
    intros [ Hu Hu' ]. subst u u'. rewrite !Nat.eqb_refl in Hne.
    destruct Hne; discriminate.
  - subst z. rewrite Ez, div2_2n_1 in He.
    apply andb_prop in He. destruct He as [ Hu Hv ].
    apply Nat.eqb_eq in Hu. apply Nat.eqb_eq in Hv. subst u v'.
    right. split; reflexivity.
Qed.

Lemma chain_inline_callee_step :
  forall caller call_pre call_post callee v z,
    cfg_edge (inline_call_cfg caller call_pre call_post callee) (2 * v + 1) z = true ->
    (exists v', z = 2 * v' + 1 /\ cfg_edge callee v v' = true)
    \/ (cfg_exit callee v = true /\ z = 2 * call_post).
Proof.
  intros caller call_pre call_post callee v z He. unfold_inline_in He.
  rewrite even_2n_1, div2_2n_1 in He.
  destruct (even_decomp z) as [ [ u' [ Hz [ Ez Dz ] ] ] | [ v' [ Hz [ Ez Dz ] ] ] ].
  - subst z. rewrite Ez, div2_2n in He.
    apply andb_prop in He. destruct He as [ Hexit Hu ].
    apply Nat.eqb_eq in Hu. subst u'.
    right. split; [ exact Hexit | reflexivity ].
  - subst z. rewrite Ez, div2_2n_1 in He.
    left. exists v'. split; [ reflexivity | exact He ].
Qed.

Lemma last_default_irrel : forall (A : Type) (l : list A) (d1 d2 : A),
  l <> nil -> last l d1 = last l d2.
Proof.
  intros A l. induction l as [ | a [ | b r ] IH ]; intros d1 d2 Hne.
  - exfalso. apply Hne. reflexivity.
  - reflexivity.
  - exact (IH d1 d2 ltac:(discriminate)).
Qed.

Lemma last_cons_nonnil : forall (A : Type) (x : A) (l : list A) (d : A),
  l <> nil -> last (x :: l) d = last l d.
Proof. intros A x [ | y r ] d H; [ contradiction | reflexivity ]. Qed.

Lemma last_app_mid_cons : forall (A : Type) (l1 : list A) (mid : A) (l2 : list A) (d : A),
  last (l1 ++ [mid] ++ l2) d = last l2 mid.
Proof.
  intros A l1 mid l2 d. change ([mid] ++ l2) with (mid :: l2).
  rewrite (last_app_nonnil A l1 (mid :: l2) d ltac:(discriminate)).
  destruct l2 as [ | x r ]; [ reflexivity | ].
  rewrite (last_cons_nonnil A mid (x :: r) d ltac:(discriminate)).
  apply last_default_irrel. discriminate.
Qed.

Lemma chain_snoc : forall g x l y,
  chain g x l = true -> cfg_edge g (last l x) y = true -> chain g x (l ++ [y]) = true.
Proof.
  intros g x l y. revert x. induction l as [ | a r IH ]; intros x Hc He.
  - simpl in *. rewrite He. reflexivity.
  - simpl in Hc. apply andb_prop in Hc. destruct Hc as [ Hxa Hr ].
    simpl. apply andb_true_intro. split; [ exact Hxa | ].
    apply (IH a Hr). destruct r as [ | b r' ].
    + exact He.
    + simpl in He. rewrite (last_default_irrel nat (b :: r') a x ltac:(discriminate)).
      exact He.
Qed.

Lemma inline_caller_sink_stays_in_caller :
  forall caller call_pre call_post callee,
    (forall v inner, SinkPath caller v inner -> ~ In call_pre (v :: inner)) ->
    forall v prefix l,
      cfg_sink caller v = true -> cfg_poll caller v = false ->
      chain caller v prefix = true ->
      all_of (fun a => negb (cfg_poll caller a)) prefix = true ->
      chain (inline_call_cfg caller call_pre call_post callee) (2 * last prefix v) l = true ->
      all_of (fun z => negb (cfg_poll (inline_call_cfg caller call_pre call_post callee) z)) l = true ->
      exists l',
        l = map (fun a => 2 * a) l'
        /\ chain caller (last prefix v) l' = true
        /\ all_of (fun a => negb (cfg_poll caller a)) l' = true
        /\ last l (2 * last prefix v) = 2 * last l' (last prefix v).
Proof.
  intros caller call_pre call_post callee Hno v prefix l.
  revert prefix. induction l as [ | z rest IH ]; intros prefix Hs Hp Hcp Hip Hc Hi.
  - exists nil. repeat split; reflexivity.
  - cbn [chain all_of] in Hc, Hi. apply andb_prop in Hc. destruct Hc as [ Hxz Hrest ].
    apply andb_prop in Hi. destruct Hi as [ Hpz Hri ].
    destruct (chain_inline_caller_step caller call_pre call_post callee _ _ Hxz)
      as [ [ u' [ Hz [ Hedge _ ] ] ] | [ Hpre _ ] ].
    + subst z. unfold_inline_in Hpz. rewrite even_2n, div2_2n in Hpz.
      assert (Hcp' : chain caller v (prefix ++ [u']) = true)
        by exact (chain_snoc caller v prefix u' Hcp Hedge).
      assert (Hip' : all_of (fun a => negb (cfg_poll caller a)) (prefix ++ [u']) = true).
      { apply all_of_app_true; [ exact Hip | simpl; rewrite Hpz; reflexivity ]. }
      destruct (IH (prefix ++ [u']) Hs Hp Hcp' Hip') as [ l' [ Hl' [ Hcl' [ Hil' Hlast' ] ] ] ].
      * rewrite last_last. exact Hrest.
      * exact Hri.
      * rewrite last_last in Hcl', Hlast'. exists (u' :: l'). repeat split.
        -- simpl. rewrite Hl'. reflexivity.
        -- simpl. apply andb_true_intro. split; [ exact Hedge | exact Hcl' ].
        -- simpl. apply andb_true_intro. split; [ exact Hpz | exact Hil' ].
        -- destruct l' as [ | a r ].
           ++ simpl in Hl'. subst rest. reflexivity.
           ++ assert (Hrne : rest <> nil) by (rewrite Hl'; discriminate).
              rewrite (last_cons_nonnil nat (2 * u') rest (2 * last prefix v) Hrne).
              rewrite (last_default_irrel nat rest (2 * last prefix v) (2 * u') Hrne).
              rewrite Hlast'.
              rewrite (last_cons_nonnil nat u' (a :: r) (last prefix v) ltac:(discriminate)).
              rewrite (last_default_irrel nat (a :: r) (last prefix v) u' ltac:(discriminate)).
              reflexivity.
    + exfalso.
      assert (Hsp : SinkPath caller v prefix) by (repeat split; assumption).
      apply (Hno v prefix Hsp).
      destruct prefix as [ | a r ].
      * simpl in Hpre. left. exact Hpre.
      * right. rewrite <- Hpre. apply last_in. discriminate.
Qed.

Lemma inline_callee_sink_stays_in_callee :
  forall caller call_pre call_post callee,
    (forall v inner, SinkPath callee v inner -> cfg_exit callee (last inner v) = false) ->
    forall v prefix l,
      cfg_sink callee v = true -> cfg_poll callee v = false ->
      chain callee v prefix = true ->
      all_of (fun b => negb (cfg_poll callee b)) prefix = true ->
      chain (inline_call_cfg caller call_pre call_post callee) (2 * last prefix v + 1) l = true ->
      all_of (fun z => negb (cfg_poll (inline_call_cfg caller call_pre call_post callee) z)) l = true ->
      exists l',
        l = map (fun b => 2 * b + 1) l'
        /\ chain callee (last prefix v) l' = true
        /\ all_of (fun b => negb (cfg_poll callee b)) l' = true
        /\ last l (2 * last prefix v + 1) = 2 * last l' (last prefix v) + 1.
Proof.
  intros caller call_pre call_post callee Hno_exit v prefix l.
  revert prefix. induction l as [ | z rest IH ]; intros prefix Hs Hp Hcp Hip Hc Hi.
  - exists nil. repeat split; reflexivity.
  - cbn [chain all_of] in Hc, Hi. apply andb_prop in Hc. destruct Hc as [ Hxz Hrest ].
    apply andb_prop in Hi. destruct Hi as [ Hpz Hri ].
    destruct (chain_inline_callee_step caller call_pre call_post callee _ _ Hxz)
      as [ [ v' [ Hz Hedge ] ] | [ Hexit _ ] ].
    + subst z. unfold_inline_in Hpz. rewrite even_2n_1, div2_2n_1 in Hpz.
      assert (Hcp' : chain callee v (prefix ++ [v']) = true)
        by exact (chain_snoc callee v prefix v' Hcp Hedge).
      assert (Hip' : all_of (fun b => negb (cfg_poll callee b)) (prefix ++ [v']) = true).
      { apply all_of_app_true; [ exact Hip | simpl; rewrite Hpz; reflexivity ]. }
      destruct (IH (prefix ++ [v']) Hs Hp Hcp' Hip') as [ l' [ Hl' [ Hcl' [ Hil' Hlast' ] ] ] ].
      * rewrite last_last. exact Hrest.
      * exact Hri.
      * rewrite last_last in Hcl', Hlast'. exists (v' :: l'). repeat split.
        -- simpl. rewrite Hl'. reflexivity.
        -- simpl. apply andb_true_intro. split; [ exact Hedge | exact Hcl' ].
        -- simpl. apply andb_true_intro. split; [ exact Hpz | exact Hil' ].
        -- destruct l' as [ | a r ].
           ++ simpl in Hl'. subst rest. reflexivity.
           ++ assert (Hrne : rest <> nil) by (rewrite Hl'; discriminate).
              rewrite (last_cons_nonnil nat (2 * v' + 1) rest (2 * last prefix v + 1) Hrne).
              rewrite (last_default_irrel nat rest (2 * last prefix v + 1) (2 * v' + 1) Hrne).
              rewrite Hlast'.
              rewrite (last_cons_nonnil nat v' (a :: r) (last prefix v) ltac:(discriminate)).
              rewrite (last_default_irrel nat (a :: r) (last prefix v) v' ltac:(discriminate)).
              reflexivity.
    + exfalso.
      assert (Hsp : SinkPath callee v prefix) by (repeat split; assumption).
      pose proof (Hno_exit v prefix Hsp) as Hne. rewrite Hexit in Hne. discriminate Hne.
Qed.

Lemma inline_preserves_sinks_ok :
  forall caller call_pre call_post callee,
    SinksYieldWithinOneReaction caller ->
    SinksYieldWithinOneReaction callee ->
    (forall v inner, SinkPath caller v inner -> ~ In call_pre (v :: inner)) ->
    SinksYieldWithinOneReaction (inline_call_cfg caller call_pre call_post callee).
Proof.
  intros caller call_pre call_post callee [ Hs1a Hs1b ] [ Hs2a Hs2b ] Hno_pre.
  split.
  - intros x Hs Hp. cbn in Hs, Hp |- *.
    destruct (Nat.even x); [ exact (Hs1a _ Hs Hp) | exact (Hs2a _ Hs Hp) ].
  - intros x inner [ Hs [ Hp [ Hc Hi ] ] ].
    destruct (even_decomp x) as [ [ u [ Hx [ Ex Dx ] ] ] | [ v [ Hx [ Ex Dx ] ] ] ].
    + subst x. unfold_inline_in Hs. unfold_inline_in Hp. rewrite Ex, Dx in Hs, Hp.
      destruct (inline_caller_sink_stays_in_caller caller call_pre call_post callee Hno_pre
                  u nil inner Hs Hp eq_refl eq_refl Hc Hi)
        as [ inner' [ Hmap [ Hc' [ Hi' Hlast ] ] ] ].
      cbn [last] in Hc', Hlast.
      assert (Hsp : SinkPath caller u inner') by (repeat split; assumption).
      destruct (Hs1b u inner' Hsp) as [ Hext Hw ].
      rewrite Hlast. split.
      * cbn [cfg_exit inline_call_cfg]. rewrite even_2n, div2_2n. exact Hext.
      * intros w Hew Hpw.
        destruct (chain_inline_caller_step caller call_pre call_post callee _ _ Hew)
          as [ [ w' [ Hw_eq [ Hedge _ ] ] ] | [ Hpre _ ] ].
        -- subst w. unfold_inline_in Hpw. cbn [cfg_yield inline_call_cfg].
           rewrite even_2n, div2_2n in Hpw |- *.
           exact (Hw w' Hedge Hpw).
        -- exfalso. apply (Hno_pre u inner' Hsp).
           destruct inner' as [ | a r ]; [ left; exact Hpre | ].
           right. rewrite <- Hpre. apply last_in. discriminate.
    + subst x. unfold_inline_in Hs. unfold_inline_in Hp. rewrite Ex, Dx in Hs, Hp.
      assert (Hno_exit : forall w p, SinkPath callee w p -> cfg_exit callee (last p w) = false).
      { intros w p Hwp. exact (proj1 (Hs2b w p Hwp)). }
      destruct (inline_callee_sink_stays_in_callee caller call_pre call_post callee Hno_exit
                  v nil inner Hs Hp eq_refl eq_refl Hc Hi)
        as [ inner' [ Hmap [ Hc' [ Hi' Hlast ] ] ] ].
      cbn [last] in Hc', Hlast.
      assert (Hsp : SinkPath callee v inner') by (repeat split; assumption).
      destruct (Hs2b v inner' Hsp) as [ _ Hw ].
      rewrite Hlast. split; [ cbn [cfg_exit inline_call_cfg]; rewrite even_2n_1; reflexivity | ].
      intros w Hew Hpw.
      destruct (chain_inline_callee_step caller call_pre call_post callee _ _ Hew)
        as [ [ w' [ Hw_eq Hedge ] ] | [ Hexit _ ] ].
      * subst w. unfold_inline_in Hpw. cbn [cfg_yield inline_call_cfg].
        rewrite even_2n_1, div2_2n_1 in Hpw |- *.
        exact (Hw w' Hedge Hpw).
      * exfalso. rewrite (Hno_exit v inner' Hsp) in Hexit. discriminate Hexit.
Qed.

(* Path-splitting helpers for proving `ReactionsWithin (inline_call_cfg ...) Y`. *)

Lemma sum_map_cons : forall (A : Type) (f : A -> nat) (x : A) (l : list A),
  sum_list (map f (x :: l)) = f x + sum_list (map f l).
Proof. reflexivity. Qed.

Lemma inlined_cost_caller : forall caller call_pre call_post callee u,
  cfg_cost (inline_call_cfg caller call_pre call_post callee) (2 * u) = cfg_cost caller u.
Proof. intros. cbn [cfg_cost inline_call_cfg]. rewrite even_2n, div2_2n. reflexivity. Qed.

Lemma inlined_cost_callee : forall caller call_pre call_post callee v,
  cfg_cost (inline_call_cfg caller call_pre call_post callee) (2 * v + 1) = cfg_cost callee v.
Proof. intros. cbn [cfg_cost inline_call_cfg]. rewrite even_2n_1, div2_2n_1. reflexivity. Qed.

Lemma chain_caller_pure_or_call :
  forall caller call_pre call_post callee u l,
    chain (inline_call_cfg caller call_pre call_post callee) (2 * u) l = true ->
    all_of (fun z => negb (cfg_poll (inline_call_cfg caller call_pre call_post callee) z)) l = true ->
    (exists lu,
       l = map (fun a => 2 * a) lu
       /\ chain caller u lu = true
       /\ all_of (fun a => negb (cfg_poll caller a)) lu = true
       /\ sum_list (map (cfg_cost (inline_call_cfg caller call_pre call_post callee)) l)
          = sum_list (map (cfg_cost caller) lu)
       /\ last l (2 * u) = 2 * last lu u)
    \/ (exists l_pre l_post,
          l = map (fun a => 2 * a) l_pre ++ [2 * cfg_entry callee + 1] ++ l_post
          /\ chain caller u l_pre = true
          /\ all_of (fun a => negb (cfg_poll caller a)) l_pre = true
          /\ last l_pre u = call_pre
          /\ cfg_poll callee (cfg_entry callee) = false
          /\ chain (inline_call_cfg caller call_pre call_post callee)
                   (2 * cfg_entry callee + 1) l_post = true
          /\ all_of (fun z => negb (cfg_poll (inline_call_cfg caller call_pre call_post callee) z))
                    l_post = true
          /\ sum_list (map (cfg_cost (inline_call_cfg caller call_pre call_post callee)) l)
             = sum_list (map (cfg_cost caller) l_pre)
               + cfg_cost callee (cfg_entry callee)
               + sum_list (map (cfg_cost (inline_call_cfg caller call_pre call_post callee)) l_post)).
Proof.
  intros caller call_pre call_post callee u l. revert u.
  induction l as [ | z rest IH ]; intros u Hc Hi.
  - left. exists nil. repeat split; reflexivity.
  - cbn [chain all_of] in Hc, Hi. apply andb_prop in Hc. destruct Hc as [ Huz Hrest ].
    apply andb_prop in Hi. destruct Hi as [ Hpz Hri ].
    destruct (chain_inline_caller_step caller call_pre call_post callee u z Huz)
      as [ [ u' [ Hz [ Hedge _ ] ] ] | [ Hpre Hz ] ].
    + subst z. unfold_inline_in Hpz. rewrite even_2n, div2_2n in Hpz.
      destruct (IH u' Hrest Hri) as [ [ lu [ Hl [ Hcl [ Hil [ Hsum Hlast ] ] ] ] ]
                                   | [ l_pre [ l_post [ Hl [ Hcp [ Hip [ Hlp [ Hpe [ Hcr [ Hir Hsum ] ] ] ] ] ] ] ] ] ].
      * left. exists (u' :: lu). repeat split.
        -- simpl. rewrite Hl. reflexivity.
        -- simpl. apply andb_true_intro. split; [ exact Hedge | exact Hcl ].
        -- simpl. apply andb_true_intro. split; [ exact Hpz | exact Hil ].
        -- rewrite sum_map_cons, inlined_cost_caller, Hsum. reflexivity.
        -- destruct lu as [ | a r ].
           ++ simpl in Hl. subst rest. reflexivity.
           ++ assert (Hrne : rest <> nil) by (rewrite Hl; discriminate).
              rewrite (last_cons_nonnil nat (2 * u') rest (2 * u) Hrne).
              rewrite (last_default_irrel nat rest (2 * u) (2 * u') Hrne).
              rewrite Hlast.
              rewrite (last_cons_nonnil nat u' (a :: r) u ltac:(discriminate)).
              rewrite (last_default_irrel nat (a :: r) u u' ltac:(discriminate)).
              reflexivity.
      * right. exists (u' :: l_pre), l_post. repeat split.
        -- simpl. rewrite Hl. reflexivity.
        -- simpl. apply andb_true_intro. split; [ exact Hedge | exact Hcp ].
        -- simpl. apply andb_true_intro. split; [ exact Hpz | exact Hip ].
        -- simpl. destruct l_pre as [ | a r ]; [ simpl in Hlp; exact Hlp | rewrite (last_default_irrel nat (a :: r) u u' ltac:(discriminate)); exact Hlp ].
        -- exact Hpe.
        -- exact Hcr.
        -- exact Hir.
        -- rewrite sum_map_cons, inlined_cost_caller, Hsum. simpl. lia.
    + subst z. unfold_inline_in Hpz. rewrite even_2n_1, div2_2n_1 in Hpz.
      right. exists nil, rest. repeat split.
      * exact Hpre.
      * apply negb_true_iff; exact Hpz.
      * exact Hrest.
      * exact Hri.
      * rewrite sum_map_cons, inlined_cost_callee. simpl. lia.
Qed.

Lemma chain_inline_callee_pure_or_return :
  forall caller call_pre call_post callee v l,
    chain (inline_call_cfg caller call_pre call_post callee) (2 * v + 1) l = true ->
    all_of (fun z => negb (cfg_poll (inline_call_cfg caller call_pre call_post callee) z)) l = true ->
    (exists lv,
       l = map (fun b => 2 * b + 1) lv
       /\ chain callee v lv = true
       /\ all_of (fun b => negb (cfg_poll callee b)) lv = true
       /\ sum_list (map (cfg_cost (inline_call_cfg caller call_pre call_post callee)) l)
          = sum_list (map (cfg_cost callee) lv)
       /\ last l (2 * v + 1) = 2 * last lv v + 1)
    \/ (exists l_mid l_post,
          l = map (fun b => 2 * b + 1) l_mid ++ [2 * call_post] ++ l_post
          /\ chain callee v l_mid = true
          /\ all_of (fun b => negb (cfg_poll callee b)) l_mid = true
          /\ cfg_exit callee (last l_mid v) = true
          /\ cfg_poll caller call_post = false
          /\ chain (inline_call_cfg caller call_pre call_post callee) (2 * call_post) l_post = true
          /\ all_of (fun z => negb (cfg_poll (inline_call_cfg caller call_pre call_post callee) z))
                    l_post = true
          /\ sum_list (map (cfg_cost (inline_call_cfg caller call_pre call_post callee)) l)
             = sum_list (map (cfg_cost callee) l_mid)
               + cfg_cost caller call_post
               + sum_list (map (cfg_cost (inline_call_cfg caller call_pre call_post callee)) l_post)).
Proof.
  intros caller call_pre call_post callee v l. revert v.
  induction l as [ | z rest IH ]; intros v Hc Hi.
  - left. exists nil. repeat split; reflexivity.
  - cbn [chain all_of] in Hc, Hi. apply andb_prop in Hc. destruct Hc as [ Hvz Hrest ].
    apply andb_prop in Hi. destruct Hi as [ Hpz Hri ].
    destruct (chain_inline_callee_step caller call_pre call_post callee v z Hvz)
      as [ [ v' [ Hz Hedge ] ] | [ Hexit Hz ] ].
    + subst z. unfold_inline_in Hpz. rewrite even_2n_1, div2_2n_1 in Hpz.
      destruct (IH v' Hrest Hri) as [ [ lv [ Hl [ Hcl [ Hil [ Hsum Hlast ] ] ] ] ]
                                   | [ l_mid [ l_post [ Hl [ Hcm [ Him [ Hxm [ Hpc [ Hcr [ Hir Hsum ] ] ] ] ] ] ] ] ] ].
      * left. exists (v' :: lv). repeat split.
        -- simpl. rewrite Hl. reflexivity.
        -- simpl. apply andb_true_intro. split; [ exact Hedge | exact Hcl ].
        -- simpl. apply andb_true_intro. split; [ exact Hpz | exact Hil ].
        -- rewrite sum_map_cons, inlined_cost_callee, Hsum. reflexivity.
        -- destruct lv as [ | b r ].
           ++ simpl in Hl. subst rest. reflexivity.
           ++ assert (Hrne : rest <> nil) by (rewrite Hl; discriminate).
              rewrite (last_cons_nonnil nat (2 * v' + 1) rest (2 * v + 1) Hrne).
              rewrite (last_default_irrel nat rest (2 * v + 1) (2 * v' + 1) Hrne).
              rewrite Hlast.
              rewrite (last_cons_nonnil nat v' (b :: r) v ltac:(discriminate)).
              rewrite (last_default_irrel nat (b :: r) v v' ltac:(discriminate)).
              reflexivity.
      * right. exists (v' :: l_mid), l_post. repeat split.
        -- simpl. rewrite Hl. reflexivity.
        -- simpl. apply andb_true_intro. split; [ exact Hedge | exact Hcm ].
        -- simpl. apply andb_true_intro. split; [ exact Hpz | exact Him ].
        -- simpl. destruct l_mid as [ | b r ]; [ exact Hxm | rewrite (last_default_irrel nat (b :: r) v v' ltac:(discriminate)); exact Hxm ].
        -- exact Hpc.
        -- exact Hcr.
        -- exact Hir.
        -- rewrite sum_map_cons, inlined_cost_callee, Hsum. simpl. lia.
    + subst z. unfold_inline_in Hpz. rewrite even_2n, div2_2n in Hpz.
      right. exists nil, rest. repeat split.
      * exact Hexit.
      * apply negb_true_iff; exact Hpz.
      * exact Hrest.
      * exact Hri.
      * rewrite sum_map_cons, inlined_cost_caller. simpl. lia.
Qed.

Lemma last_app_single : forall (A : Type) (l : list A) (x y : A),
  last (l ++ [y]) x = y.
Proof. intros A l x y. apply last_last. Qed.

Lemma in_caller_chain_no_reentry :
  forall caller call_pre call_post callee u l,
    (forall inner,
       chain caller u inner = true ->
       all_of (fun v => negb (cfg_poll caller v)) inner = true ->
       ~ In call_pre (u :: inner)) ->
    chain (inline_call_cfg caller call_pre call_post callee) (2 * u) l = true ->
    all_of (fun z => negb (cfg_poll (inline_call_cfg caller call_pre call_post callee) z)) l = true ->
    exists lu,
      l = map (fun a => 2 * a) lu
      /\ chain caller u lu = true
      /\ all_of (fun a => negb (cfg_poll caller a)) lu = true
      /\ sum_list (map (cfg_cost (inline_call_cfg caller call_pre call_post callee)) l)
         = sum_list (map (cfg_cost caller) lu)
      /\ last l (2 * u) = 2 * last lu u.
Proof.
  intros caller call_pre call_post callee u l Hno Hc Hi.
  destruct (chain_caller_pure_or_call caller call_pre call_post callee u l Hc Hi)
    as [ Hpure | [ l_pre [ l_post [ _ [ Hcp [ Hip [ Hlp _ ] ] ] ] ] ] ].
  - exact Hpure.
  - exfalso. apply (Hno l_pre Hcp Hip).
    destruct l_pre as [ | a r ].
    + left. simpl in Hlp. exact Hlp.
    + right. rewrite <- Hlp. apply last_in. discriminate.
Qed.

Lemma chain_last_edge : forall g from inner to,
  chain g from (inner ++ [to]) = true ->
  cfg_edge g (last inner from) to = true.
Proof.
  intros g from inner to. revert from.
  induction inner as [ | a r IH ]; intros from Hc.
  - simpl in Hc. apply andb_prop in Hc. exact (proj1 Hc).
  - cbn [app chain] in Hc. apply andb_prop in Hc.
    pose proof (IH a (proj2 Hc)) as Hr.
    destruct r as [ | b r' ]; [ exact Hr | ].
    rewrite (last_cons_nonnil nat a (b :: r') from ltac:(discriminate)).
    rewrite (last_default_irrel nat (b :: r') from a ltac:(discriminate)). exact Hr.
Qed.

(*| discharges: R-07-037h, R-05-102 |*)
Theorem inline_call_cfg_admits :
  forall (caller callee : Cfg) (call_pre call_post pre post Y : nat)
         (t_callee : FnCostTriple) (is_rec : bool),
    YieldBoundAdmits caller Y ->
    YieldBoundAdmits callee Y ->
    FnTripleSound callee t_callee ->
    CallContextSound caller call_pre call_post pre post ->
    call_site_admits {| cs_pre_cost := pre; cs_callee := t_callee;
                        cs_post_cost := post; cs_recursive := is_rec |} Y = true ->
    YieldBoundAdmits (inline_call_cfg caller call_pre call_post callee) Y.
Proof.
  intros caller callee call_pre call_post pre post Y t_callee is_rec
         [ Hbc1 [ Hrc1 [ [ Hrx1 Hex1 ] Hs1 ] ] ]
         [ Hbc2 [ Hrc2 [ [ Hrx2 Hex2 ] Hs2 ] ] ]
         [ Ht_e [ Ht_p [ Ht_x Ht_flag ] ] ]
         [ Hpre_np [ Hpre_nx [ Hpre_b [ Hpost_rx [ Hpost_ex [ Hno_re Hno_sink ] ] ] ] ] ]
         Hcs.
  apply call_site_admits_iff in Hcs. unfold CallSiteAdmits in Hcs. cbn in Hcs.
  destruct (inline_preserves_polls caller call_pre call_post callee Hbc1 Hbc2 Hrc1 Hrc2)
    as [ Hbc_in Hrc_in ].
  split; [ exact Hbc_in | split; [ exact Hrc_in | split ] ].
  - split.
    + (* Reaction in inlined *)
      intros from inner to [ Hfrom [ Hi [ Hc Hto ] ] ].
      unfold reaction_cost.
      pose proof (chain_app _ from inner [to] Hc) as Hci.
      pose proof (chain_last_edge _ from inner to Hc) as Hedge_to.
      destruct (even_decomp from) as [ [ u [ Hf [ Ef Df ] ] ] | [ v [ Hf [ Ef Df ] ] ] ].
      * (* from = 2 * u in caller *)
        subst from. unfold_inline_in Hfrom. rewrite Ef, Df in Hfrom.
        rewrite inlined_cost_caller.
        assert (Hfrom' : (Nat.eqb u (cfg_entry caller) || cfg_poll caller u) = true).
        { clear - Hfrom. destruct (Nat.eqb (2 * u) (2 * cfg_entry caller)) eqn:E.
          - apply Nat.eqb_eq in E. apply orb_true_intro. left. apply Nat.eqb_eq. lia.
          - simpl in Hfrom. apply orb_true_intro. right. exact Hfrom. }
        destruct (chain_caller_pure_or_call caller call_pre call_post callee u inner Hci Hi)
          as [ [ lu [ Hmap [ Hclu [ Hilu [ Hsum Hlast ] ] ] ] ]
             | [ l_pre [ l_post [ Hmap [ Hcp [ Hip [ Hlp [ Hpe [ Hcr [ Hir Hsum ] ] ] ] ] ] ] ] ] ].
        -- (* Pure caller prefix lu *)
           rewrite Hsum, Hlast in *.
           destruct (chain_inline_caller_step caller call_pre call_post callee _ _ Hedge_to)
             as [ [ u' [ Ht_eq [ Htu' _ ] ] ] | [ Hpre_eq Ht_eq ] ].
           ++ subst to. unfold_inline_in Hto. rewrite even_2n, div2_2n in Hto.
              assert (Hrc : Reaction caller u lu u').
              { repeat split; [ exact Hfrom' | exact Hilu | exact (chain_snoc _ _ _ _ Hclu Htu') | exact Hto ]. }
              exact (Hrx1 u lu u' Hrc).
           ++ subst to. unfold_inline_in Hto. rewrite even_2n_1, div2_2n_1 in Hto.
              pose proof (Hpre_b u lu Hfrom' Hilu Hclu Hpre_eq) as Hle_pre.
              unfold reaction_cost in Hle_pre.
              destruct (fn_has_internal_poll t_callee) eqn:Eflag.
              ** destruct Hcs as [ Hcs1 _ ]. lia.
              ** destruct Hcs as [ _ Hcs1 ]. lia.
        -- (* Crosses into callee at cfg_entry callee *)
           pose proof (Hpre_b u l_pre Hfrom' Hip Hcp Hlp) as Hle_pre.
           unfold reaction_cost in Hle_pre.
           rewrite Hsum in *.
           rewrite Hmap, last_app_mid_cons in Hedge_to.
           destruct (chain_inline_callee_pure_or_return caller call_pre call_post callee
                       (cfg_entry callee) l_post Hcr Hir)
             as [ [ lv [ Hlv [ Hclv [ Hilv [ Hsum_v Hlast_v ] ] ] ] ]
                | [ l_mid [ l_tail [ Hml [ Hcm [ Him [ Hxm [ Hpc [ Hct [ Hit Hsum_m ] ] ] ] ] ] ] ] ] ].
           ++ (* Ends inside callee *)
              rewrite Hsum_v, Hlast_v in *.
              destruct (chain_inline_callee_step caller call_pre call_post callee _ _ Hedge_to)
                as [ [ v' [ Ht_eq Hedge_v ] ] | [ Hexit_v Ht_eq ] ].
              ** subst to. unfold_inline_in Hto. rewrite even_2n_1, div2_2n_1 in Hto.
                 assert (Hrc : Reaction callee (cfg_entry callee) lv v').
                 { repeat split; [ rewrite Nat.eqb_refl; reflexivity | exact Hilv
                                 | exact (chain_snoc _ _ _ _ Hclv Hedge_v) | exact Hto ]. }
                 destruct (fn_has_internal_poll t_callee) eqn:Eflag.
                 --- destruct Hcs as [ Hcs1 _ ].
                     pose proof (Ht_e Hpe lv v' Hrc) as Hce. unfold reaction_cost in Hce. lia.
                 --- destruct Ht_flag as [ Hno_r _ ]. exfalso. exact (Hno_r lv v' Hrc).
              ** subst to. unfold_inline_in Hto. rewrite even_2n, div2_2n in Hto.
                 assert (Hex : ExitReaction callee (cfg_entry callee) lv).
                 { repeat split; [ rewrite Nat.eqb_refl; reflexivity | exact Hilv | exact Hclv | exact Hexit_v ]. }
                 destruct (fn_has_internal_poll t_callee) eqn:Eflag.
                 --- destruct Ht_flag as [ Hent_p | Hno_ex ].
                     +++ rewrite Hent_p in Hpe. discriminate Hpe.
                     +++ exfalso. exact (Hno_ex lv Hex).
                 --- destruct Ht_flag as [ _ [ Hce _ ] ]. destruct Hcs as [ _ Hcs1 ].
                     pose proof (Hce lv Hex) as Hce'. unfold reaction_cost in Hce'.
                     unfold fn_full_cost in Hcs1. lia.
           ++ (* Exits callee to call_post, continues in caller along l_tail *)
              destruct (in_caller_chain_no_reentry caller call_pre call_post callee call_post l_tail
                          Hno_re Hct Hit) as [ lt [ Hlt [ Hclt [ Hilt [ Hsum_t Hlast_t ] ] ] ] ].
              assert (Hex : ExitReaction callee (cfg_entry callee) l_mid).
              { repeat split; [ rewrite Nat.eqb_refl; reflexivity | exact Him | exact Hcm | exact Hxm ]. }
              rewrite Hml, last_app_mid_cons, Hlast_t in Hedge_to.
              destruct (chain_inline_caller_step caller call_pre call_post callee _ _ Hedge_to)
                as [ [ u' [ Ht_eq [ Htu' _ ] ] ] | [ Hpre_eq _ ] ].
              ** subst to. unfold_inline_in Hto. rewrite even_2n, div2_2n in Hto.
                 pose proof (Hpost_rx lt u' Hpc Hilt (chain_snoc _ _ _ _ Hclt Htu') Hto) as Hle_post.
                 unfold reaction_cost in Hle_post.
                 destruct (fn_has_internal_poll t_callee) eqn:Eflag.
                 --- destruct Ht_flag as [ Hent_p | Hno_ex ].
                     +++ rewrite Hent_p in Hpe. discriminate Hpe.
                     +++ exfalso. exact (Hno_ex l_mid Hex).
                 --- destruct Ht_flag as [ _ [ Hce _ ] ]. destruct Hcs as [ _ Hcs1 ].
                     pose proof (Hce l_mid Hex) as Hce'. unfold reaction_cost in Hce'.
                     rewrite Hsum_m, Hsum_t. unfold fn_full_cost in Hcs1. lia.
              ** exfalso. apply (Hno_re lt Hclt Hilt).
                 destruct lt as [ | a r ]; [ left; exact Hpre_eq | ].
                 right. rewrite <- Hpre_eq. apply last_in. discriminate.
      * (* from = 2 * v + 1 in callee *)
        subst from. unfold_inline_in Hfrom. rewrite Ef, Df in Hfrom.
        rewrite inlined_cost_callee.
        assert (Hpoll_v : cfg_poll callee v = true).
        { apply orb_prop in Hfrom. destruct Hfrom as [ Heq | Hp ]; [ apply Nat.eqb_eq in Heq; lia | exact Hp ]. }
        destruct (chain_inline_callee_pure_or_return caller call_pre call_post callee v inner Hci Hi)
          as [ [ lv [ Hlv [ Hclv [ Hilv [ Hsum_v Hlast_v ] ] ] ] ]
             | [ l_mid [ l_tail [ Hml [ Hcm [ Him [ Hxm [ Hpc [ Hct [ Hit Hsum_m ] ] ] ] ] ] ] ] ] ].
        -- rewrite Hsum_v, Hlast_v in *.
           destruct (chain_inline_callee_step caller call_pre call_post callee _ _ Hedge_to)
             as [ [ v' [ Ht_eq Hedge_v ] ] | [ Hexit_v Ht_eq ] ].
           ++ subst to. unfold_inline_in Hto. rewrite even_2n_1, div2_2n_1 in Hto.
              assert (Hrc : Reaction callee v lv v').
              { repeat split; [ rewrite Hpoll_v, orb_true_r; reflexivity | exact Hilv
                              | exact (chain_snoc _ _ _ _ Hclv Hedge_v) | exact Hto ]. }
              exact (Hrx2 v lv v' Hrc).
           ++ subst to. unfold_inline_in Hto. rewrite even_2n, div2_2n in Hto.
              assert (Hex : ExitReaction callee v lv).
              { repeat split; [ rewrite Hpoll_v, orb_true_r; reflexivity | exact Hilv | exact Hclv | exact Hexit_v ]. }
              destruct (fn_has_internal_poll t_callee) eqn:Eflag.
              ** destruct Hcs as [ _ [ _ Hcs3 ] ].
                 pose proof (Ht_x v lv Hpoll_v Hex) as Hcx. unfold reaction_cost in Hcx. lia.
              ** pose proof (Hex2 v lv Hex) as Hcx. unfold reaction_cost in Hcx. lia.
        -- destruct (in_caller_chain_no_reentry caller call_pre call_post callee call_post l_tail
                       Hno_re Hct Hit) as [ lt [ Hlt [ Hclt [ Hilt [ Hsum_t Hlast_t ] ] ] ] ].
           assert (Hex : ExitReaction callee v l_mid).
           { repeat split; [ rewrite Hpoll_v, orb_true_r; reflexivity | exact Him | exact Hcm | exact Hxm ]. }
           rewrite Hml, last_app_mid_cons, Hlast_t in Hedge_to.
           destruct (chain_inline_caller_step caller call_pre call_post callee _ _ Hedge_to)
             as [ [ u' [ Ht_eq [ Htu' _ ] ] ] | [ Hpre_eq _ ] ].
           ++ subst to. unfold_inline_in Hto. rewrite even_2n, div2_2n in Hto.
              pose proof (Hpost_rx lt u' Hpc Hilt (chain_snoc _ _ _ _ Hclt Htu') Hto) as Hle_post.
              unfold reaction_cost in Hle_post.
              rewrite Hsum_m, Hsum_t.
              destruct (fn_has_internal_poll t_callee) eqn:Eflag.
              ** destruct Hcs as [ _ [ _ Hcs3 ] ].
                 pose proof (Ht_x v l_mid Hpoll_v Hex) as Hcx. unfold reaction_cost in Hcx. lia.
              ** pose proof (Ht_x v l_mid Hpoll_v Hex) as Hcx. unfold reaction_cost in Hcx.
                 destruct Ht_flag as [ _ [ _ Hxeq ] ]. destruct Hcs as [ _ Hcs1 ].
                 unfold fn_full_cost in Hcs1. rewrite Hxeq in Hcx. lia.
           ++ exfalso. apply (Hno_re lt Hclt Hilt).
              destruct lt as [ | a r ]; [ left; exact Hpre_eq | ].
              right. rewrite <- Hpre_eq. apply last_in. discriminate.
    + (* ExitReaction in inlined *)
      intros from inner [ Hfrom [ Hi [ Hc Hexit ] ] ].
      unfold reaction_cost.
      destruct (even_decomp from) as [ [ u [ Hf [ Ef Df ] ] ] | [ v [ Hf [ Ef Df ] ] ] ].
      * subst from. unfold_inline_in Hfrom. rewrite Ef, Df in Hfrom.
        rewrite inlined_cost_caller.
        assert (Hfrom' : (Nat.eqb u (cfg_entry caller) || cfg_poll caller u) = true).
        { clear - Hfrom. destruct (Nat.eqb (2 * u) (2 * cfg_entry caller)) eqn:E.
          - apply Nat.eqb_eq in E. apply orb_true_intro. left. apply Nat.eqb_eq. lia.
          - simpl in Hfrom. apply orb_true_intro. right. exact Hfrom. }
        destruct (chain_caller_pure_or_call caller call_pre call_post callee u inner Hc Hi)
          as [ [ lu [ Hmap [ Hclu [ Hilu [ Hsum Hlast ] ] ] ] ]
             | [ l_pre [ l_post [ Hmap [ Hcp [ Hip [ Hlp [ Hpe [ Hcr [ Hir Hsum ] ] ] ] ] ] ] ] ] ].
        -- rewrite Hsum, Hlast in *. unfold_inline_in Hexit. rewrite even_2n, div2_2n in Hexit.
           exact (Hex1 u lu (conj Hfrom' (conj Hilu (conj Hclu Hexit)))).
        -- pose proof (Hpre_b u l_pre Hfrom' Hip Hcp Hlp) as Hle_pre.
           unfold reaction_cost in Hle_pre.
           rewrite Hmap, last_app_mid_cons in Hexit.
           destruct (chain_inline_callee_pure_or_return caller call_pre call_post callee
                       (cfg_entry callee) l_post Hcr Hir)
             as [ [ lv [ Hlv [ Hclv [ Hilv [ Hsum_v Hlast_v ] ] ] ] ]
                | [ l_mid [ l_tail [ Hml [ Hcm [ Him [ Hxm [ Hpc [ Hct [ Hit Hsum_m ] ] ] ] ] ] ] ] ] ].
           ++ exfalso. rewrite Hlast_v in Hexit. unfold_inline_in Hexit. rewrite even_2n_1 in Hexit. discriminate Hexit.
           ++ destruct (in_caller_chain_no_reentry caller call_pre call_post callee call_post l_tail
                          Hno_re Hct Hit) as [ lt [ Hlt [ Hclt [ Hilt [ Hsum_t Hlast_t ] ] ] ] ].
              rewrite Hml, last_app_mid_cons, Hlast_t in Hexit. unfold_inline_in Hexit. rewrite even_2n, div2_2n in Hexit.
              pose proof (Hpost_ex lt Hpc Hilt Hclt Hexit) as Hle_post.
              unfold reaction_cost in Hle_post.
              assert (Hex : ExitReaction callee (cfg_entry callee) l_mid).
              { repeat split; [ rewrite Nat.eqb_refl; reflexivity | exact Him | exact Hcm | exact Hxm ]. }
              destruct (fn_has_internal_poll t_callee) eqn:Eflag.
              ** destruct Ht_flag as [ Hent_p | Hno_ex ].
                 --- rewrite Hent_p in Hpe. discriminate Hpe.
                 --- exfalso. exact (Hno_ex l_mid Hex).
              ** destruct Ht_flag as [ _ [ Hce _ ] ]. destruct Hcs as [ _ Hcs1 ].
                 pose proof (Hce l_mid Hex) as Hce'. unfold reaction_cost in Hce'.
                 rewrite Hsum, Hsum_m, Hsum_t. unfold fn_full_cost in Hcs1. lia.
      * subst from. unfold_inline_in Hfrom. rewrite Ef, Df in Hfrom.
        rewrite inlined_cost_callee.
        assert (Hpoll_v : cfg_poll callee v = true).
        { apply orb_prop in Hfrom. destruct Hfrom as [ Heq | Hp ]; [ apply Nat.eqb_eq in Heq; lia | exact Hp ]. }
        destruct (chain_inline_callee_pure_or_return caller call_pre call_post callee v inner Hc Hi)
          as [ [ lv [ Hlv [ Hclv [ Hilv [ Hsum_v Hlast_v ] ] ] ] ]
             | [ l_mid [ l_tail [ Hml [ Hcm [ Him [ Hxm [ Hpc [ Hct [ Hit Hsum_m ] ] ] ] ] ] ] ] ] ].
        -- exfalso. rewrite Hlast_v in Hexit. unfold_inline_in Hexit. rewrite even_2n_1 in Hexit. discriminate Hexit.
        -- destruct (in_caller_chain_no_reentry caller call_pre call_post callee call_post l_tail
                       Hno_re Hct Hit) as [ lt [ Hlt [ Hclt [ Hilt [ Hsum_t Hlast_t ] ] ] ] ].
           rewrite Hml, last_app_mid_cons, Hlast_t in Hexit. unfold_inline_in Hexit. rewrite even_2n, div2_2n in Hexit.
           pose proof (Hpost_ex lt Hpc Hilt Hclt Hexit) as Hle_post.
           unfold reaction_cost in Hle_post.
           assert (Hex : ExitReaction callee v l_mid).
           { repeat split; [ rewrite Hpoll_v, orb_true_r; reflexivity | exact Him | exact Hcm | exact Hxm ]. }
           rewrite Hsum_m, Hsum_t.
           destruct (fn_has_internal_poll t_callee) eqn:Eflag.
           ++ destruct Hcs as [ _ [ _ Hcs3 ] ].
              pose proof (Ht_x v l_mid Hpoll_v Hex) as Hcx. unfold reaction_cost in Hcx. lia.
           ++ pose proof (Ht_x v l_mid Hpoll_v Hex) as Hcx. unfold reaction_cost in Hcx.
              destruct Ht_flag as [ _ [ _ Hxeq ] ]. destruct Hcs as [ _ Hcs1 ].
              unfold fn_full_cost in Hcs1. rewrite Hxeq in Hcx. lia.
  - exact (inline_preserves_sinks_ok caller call_pre call_post callee Hs1 Hs2 Hno_sink).
Qed.

(* =========================================================================
   S4. Static cost-counter protocol (`R-07-037h`).
   ========================================================================= *)

Record CounterState : Type := {
  cs_acc : nat;
  cs_invocations : list nat
}.

Definition step_counter (interval : nat) (st : CounterState) (r : nat) : CounterState :=
  if Nat.leb interval (cs_acc st + r)
  then {| cs_acc := 0; cs_invocations := cs_invocations st ++ [cs_acc st + r] |}
  else {| cs_acc := cs_acc st + r; cs_invocations := cs_invocations st |}.

Definition run_counter (interval : nat) (reactions : list nat) : CounterState :=
  fold_left (step_counter interval) reactions {| cs_acc := 0; cs_invocations := nil |}.

Lemma run_counter_matches_invocation_gaps :
  forall interval reactions acc invs,
    cs_invocations (fold_left (step_counter interval) reactions
                      {| cs_acc := acc; cs_invocations := invs |})
    = invs ++ invocation_gaps interval acc reactions.
Proof.
  intros interval reactions. induction reactions as [ | r rest IH ]; intros acc invs.
  - simpl. rewrite app_nil_r. reflexivity.
  - simpl. unfold step_counter. simpl.
    destruct (Nat.leb interval (acc + r)).
    + rewrite IH. rewrite <- app_assoc. reflexivity.
    + exact (IH (acc + r) invs).
Qed.

Lemma in_all_of_leb : forall (l : list nat) (Y : nat),
  (forall r, In r l -> r <= Y) -> all_of (fun r => Nat.leb r Y) l = true.
Proof.
  intros l Y H. induction l as [ | x r IH ]; [ reflexivity | ].
  simpl. apply andb_true_intro. split.
  - apply Nat.leb_le. exact (H x (or_introl eq_refl)).
  - apply IH. intros y Hy. exact (H y (or_intror Hy)).
Qed.

(*| discharges: R-07-037h |*)
Theorem compositional_program_invocation_gaps_bounded :
  forall (call_interval Y : nat) (steps : list ProgStep),
    (forall st, In st steps -> StepAdmitted Y st) ->
    forall g, In g (cs_invocations (run_counter call_interval (prog_reactions steps))) ->
      g <= call_interval + Y.
Proof.
  intros call_interval Y steps Hadm g Hg.
  unfold run_counter in Hg.
  rewrite run_counter_matches_invocation_gaps in Hg. simpl in Hg.
  apply (invocation_gaps_bounded call_interval Y (prog_reactions steps) 0 (Nat.le_0_l _)).
  - apply in_all_of_leb. exact (compositional_soundness Y steps Hadm).
  - exact Hg.
Qed.

Theorem counter_protocol_decl_bridge :
  forall (d : Decl) (steps : list ProgStep),
    (forall st, In st steps -> StepAdmitted (dc_yield_bound d) st) ->
    forall g, In g (invocation_gaps (dc_call_interval d) 0 (prog_reactions steps)) ->
      g <= call_bound d.
Proof.
  intros d steps Hadm g Hg.
  apply (the_counter_bounds_every_path_between_invocations d (prog_reactions steps)).
  - apply in_all_of_leb. exact (compositional_soundness (dc_yield_bound d) steps Hadm).
  - exact Hg.
Qed.

(* =========================================================================
   S5. TAL-014 cost-facet expressiveness (`R-07-037h`, `R-05-102`).
   ========================================================================= *)

Inductive CostFacetSchema : Type :=
| ScalarReactionFacet
| TripleReactionFacet.

Definition ScalarCallAdmits (pre callee_scalar post Y : nat) : Prop :=
  pre + callee_scalar <= Y /\ callee_scalar + post <= Y /\ callee_scalar <= Y.

Definition TripleCallAdmits (pre : nat) (t : FnCostTriple) (post Y : nat) : Prop :=
  if fn_has_internal_poll t
  then pre + fn_entry_to_first_poll t <= Y
       /\ fn_poll_to_poll t <= Y
       /\ fn_last_poll_to_exit t + post <= Y
  else pre + fn_full_cost t + post <= Y.

Definition facet_can_express_call (schema : CostFacetSchema) (t : FnCostTriple) : bool :=
  match schema with
  | TripleReactionFacet => true
  | ScalarReactionFacet =>
      negb (fn_has_internal_poll t)
      || (Nat.eqb (fn_entry_to_first_poll t) (fn_poll_to_poll t)
          && Nat.eqb (fn_poll_to_poll t) (fn_last_poll_to_exit t))
  end.

Definition tal014_version_bump_required (schema : CostFacetSchema) (t : FnCostTriple) : bool :=
  negb (facet_can_express_call schema t).

Definition asymmetric_triple : FnCostTriple := {|
  fn_entry_to_first_poll := 1;
  fn_poll_to_poll := 6;
  fn_last_poll_to_exit := 1;
  fn_has_internal_poll := true
|}.

Theorem tal014_scalar_facet_is_insufficient_for_call_crossing :
  TripleCallAdmits 4 asymmetric_triple 4 6
  /\ tal014_version_bump_required ScalarReactionFacet asymmetric_triple = true
  /\ tal014_version_bump_required TripleReactionFacet asymmetric_triple = false
  /\ forall s, fn_poll_to_poll asymmetric_triple <= s -> ~ ScalarCallAdmits 4 s 4 6.
Proof.
  split; [ cbn; repeat split; lia | split; [ reflexivity | split; [ reflexivity | ] ] ].
  intros s Hs [ H1 _ ]. cbn in Hs. lia.
Qed.

Theorem tal014_scalar_naive_check_is_unsound_across_calls :
  let callee := {| fn_entry_to_first_poll := 4; fn_poll_to_poll := 5;
                   fn_last_poll_to_exit := 4; fn_has_internal_poll := true |} in
  4 <= 6 /\ fn_triple_within callee 6 = true
  /\ ~ TripleCallAdmits 4 callee 4 6.
Proof.
  split; [ lia | split; [ reflexivity | ] ].
  intros [ H _ ]. cbn in H. lia.
Qed.

Theorem tal014_triple_subsumes_uniform_scalar :
  forall pre s post Y,
    ScalarCallAdmits pre s post Y ->
    TripleCallAdmits pre
      {| fn_entry_to_first_poll := s; fn_poll_to_poll := s;
         fn_last_poll_to_exit := s; fn_has_internal_poll := true |}
      post Y.
Proof.
  intros pre s post Y [ H1 [ H2 H3 ] ]. cbn. lia.
Qed.

(* =========================================================================
   S6. Inhabited multi-function positive witnesses and explicit refutations
   (`R-05-165`, `R-05-166`).
   ========================================================================= *)

(* Positive witness 1: strip-mined loop (`k = 2`, `body = 2`, `poll = 1`, `Y = 6`). *)
Definition pos_strip_spec : StripMineSpec := {|
  sm_k := 2; sm_body_cost := 2; sm_poll_cost := 1; sm_yield_bound := 6
|}.

Definition pos_loop_spec : LoopSpec := {|
  lp_strip := pos_strip_spec;
  lp_entry_cost := 2; lp_exit_cost := 2; lp_sink_cost := 2; lp_yield_site_cost := 1
|}.

Theorem positive_strip_mined_loop_admitted :
  strip_mine_admits pos_strip_spec = true
  /\ YieldBoundAdmits (strip_mine_cfg pos_loop_spec) 6
  /\ strip_mine_poll_overhead 10 2 1 < strip_mine_poll_overhead 10 1 1.
Proof.
  split; [ reflexivity | split ].
  - apply strip_mine_cfg_admitted; cbn; try lia.
    split; cbn; lia.
  - cbn. lia.
Qed.

(* Positive witness 2: lowering `unyielding_cfg` sink-before-yield at `Y = 6`. *)
Definition lowered_unyielding_cfg : Cfg :=
  lower_sink_before_yield unyielding_cfg 4 5 1 1.

Lemma lowered_unyielding_paths_within : PathsWithin lowered_unyielding_cfg 6.
Proof.
  intros from inner Hc Hi. unfold reaction_cost.
  destruct inner as [ | x [ | y rest ] ].
  - destruct from as [ | [ | [ | [ | [ | [ | from ] ] ] ] ] ]; cbn; lia.
  - destruct (path_head _ _ _ _ Hc Hi) as [ Hfx Hx ].
    destruct from as [ | [ | [ | [ | [ | [ | from ] ] ] ] ] ];
      destruct x as [ | [ | [ | [ | [ | [ | x ] ] ] ] ] ];
      cbn in Hfx, Hx |- *; try discriminate Hfx; try discriminate Hx; lia.
  - exfalso. destruct (path_pair _ _ _ _ _ Hc Hi) as [ Hxy [ Hx Hy ] ].
    destruct x as [ | [ | [ | [ | [ | [ | x ] ] ] ] ] ];
      destruct y as [ | [ | [ | [ | [ | [ | y ] ] ] ] ] ];
      cbn in Hxy, Hx, Hy; try discriminate Hxy; try discriminate Hx; discriminate Hy.
Qed.

Theorem positive_lowered_sink_admitted :
  YieldBoundAdmits lowered_unyielding_cfg 6.
Proof.
  split; [ | split; [ | split ] ].
  - intros u v H.
    destruct u as [ | [ | [ | [ | [ | [ | u ] ] ] ] ] ]; destruct v as [ | [ | v ] ];
      cbn in H; try discriminate H; reflexivity.
  - intros v H. cbn in H. discriminate H.
  - apply paths_within_reactions. exact lowered_unyielding_paths_within.
  - apply lower_sink_establishes_sinks_yield. discriminate.
Qed.

(* Positive witness 3: multi-function caller + direct callee (no internal poll)
   + polled recursive callee, both as concrete `inline_call_cfg` and
   whole-program `ProgStep` trace with `run_counter` gap bound. *)

(* Caller: 0 (entry, cost 1) -> 1 (call_pre, cost 2), 2 (call_post, cost 1) -> 3 (exit, cost 1). *)
Definition mf_caller_cfg : Cfg := {|
  cfg_edge := fun u v =>
    match u, v with 0, 1 => true | 2, 3 => true | _, _ => false end;
  cfg_back := fun _ _ => false;
  cfg_recursive_entry := fun _ => false;
  cfg_poll := fun _ => false;
  cfg_yield := fun _ => false;
  cfg_sink := fun _ => false;
  cfg_entry := 0;
  cfg_exit := fun v => Nat.eqb v 3;
  cfg_cost := fun v => match v with 0 => 1 | 1 => 2 | 2 => 1 | 3 => 1 | _ => 0 end
|}.

(* Leaf callee with no internal poll: entry 0 (cost 1) -> exit 1 (cost 1), full cost = 2. *)
Definition mf_leaf_cfg : Cfg := {|
  cfg_edge := fun u v => Nat.eqb u 0 && Nat.eqb v 1;
  cfg_back := fun _ _ => false;
  cfg_recursive_entry := fun _ => false;
  cfg_poll := fun _ => false;
  cfg_yield := fun _ => false;
  cfg_sink := fun _ => false;
  cfg_entry := 0;
  cfg_exit := fun v => Nat.eqb v 1;
  cfg_cost := fun v => match v with 0 => 1 | 1 => 1 | _ => 0 end
|}.

Definition mf_leaf_triple : FnCostTriple := {|
  fn_entry_to_first_poll := 2;
  fn_poll_to_poll := 0;
  fn_last_poll_to_exit := 2;
  fn_has_internal_poll := false
|}.

(* Recursive callee with polled recursive entry 0 (cost 1) -> body 1 (cost 3) ->
   poll 2 (cost 1) -> exit 3 (cost 2). Triple = (0, 4, 3, true). *)
Definition mf_rec_cfg : Cfg := {|
  cfg_edge := fun u v =>
    match u, v with 0, 1 => true | 1, 2 => true | 2, 3 => true | _, _ => false end;
  cfg_back := fun _ _ => false;
  cfg_recursive_entry := fun v => Nat.eqb v 0;
  cfg_poll := fun v => Nat.eqb v 0 || Nat.eqb v 2;
  cfg_yield := fun _ => false;
  cfg_sink := fun _ => false;
  cfg_entry := 0;
  cfg_exit := fun v => Nat.eqb v 3;
  cfg_cost := fun v => match v with 0 => 1 | 1 => 3 | 2 => 1 | 3 => 2 | _ => 0 end
|}.

Definition mf_rec_triple : FnCostTriple := {|
  fn_entry_to_first_poll := 0;
  fn_poll_to_poll := 4;
  fn_last_poll_to_exit := 3;
  fn_has_internal_poll := true
|}.

Lemma mf_caller_admits : YieldBoundAdmits mf_caller_cfg 6.
Proof.
  split; [ | split; [ | split ] ].
  - intros u v H. cbn in H. discriminate H.
  - intros v H. cbn in H. discriminate H.
  - apply paths_within_reactions. intros from inner Hc Hi. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + destruct from as [ | [ | [ | [ | from ] ] ] ]; cbn; lia.
    + destruct (path_head _ _ _ _ Hc Hi) as [ Hfx _ ].
      destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ]; cbn in Hfx |- *; try discriminate Hfx; lia.
    + exfalso.
      destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ]; cbn in Hc; discriminate Hc.
  - split; [ intros v Hs; cbn in Hs; discriminate Hs
           | intros v inner [ Hs _ ]; cbn in Hs; discriminate Hs ].
Qed.

Lemma mf_caller_ctx_sound : CallContextSound mf_caller_cfg 1 2 3 2.
Proof.
  repeat split; try reflexivity.
  - intros from inner Hfrom _ Hc Hlast. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + cbn in Hlast. subst from. cbn in Hfrom. discriminate Hfrom.
    + destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ];
        cbn in Hfrom, Hc, Hlast |- *; try discriminate Hfrom; try discriminate Hc;
        try discriminate Hlast; lia.
    + exfalso.
      destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ]; cbn in Hc; discriminate Hc.
  - intros inner to _ _ Hc Hto.
    destruct inner as [ | x rest ].
    + cbn in Hto. discriminate Hto.
    + exfalso. simpl in Hc. apply andb_prop in Hc. destruct Hc as [ H2x Hc ].
      destruct x as [ | [ | [ | [ | x ] ] ] ]; cbn in H2x; try discriminate H2x.
      destruct rest as [ | y r ].
      * simpl in Hc. discriminate Hc.
      * simpl in Hc. discriminate Hc.
  - intros inner _ _ Hc Hext. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + cbn in Hext. discriminate Hext.
    + destruct x as [ | [ | [ | [ | x ] ] ] ]; cbn in Hc, Hext |- *;
        try discriminate Hc; try discriminate Hext; lia.
    + exfalso.
      destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ]; cbn in Hc; discriminate Hc.
  - intros inner Hc _ Hin.
    destruct inner as [ | x [ | y rest ] ].
    + destruct Hin as [ Heq | [] ]; discriminate Heq.
    + destruct x as [ | [ | [ | [ | x ] ] ] ]; cbn in Hc; try discriminate Hc.
      destruct Hin as [ Heq | [ Heq | [] ] ]; discriminate Heq.
    + destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ]; cbn in Hc; discriminate Hc.
  - intros v inner [ Hs _ ]. cbn in Hs. discriminate Hs.
Qed.

Lemma mf_leaf_admits : YieldBoundAdmits mf_leaf_cfg 6.
Proof.
  split; [ | split; [ | split ] ].
  - intros u v H. cbn in H. discriminate H.
  - intros v H. cbn in H. discriminate H.
  - apply paths_within_reactions. intros from inner Hc Hi. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + destruct from as [ | [ | from ] ]; cbn; lia.
    + destruct (path_head _ _ _ _ Hc Hi) as [ Hfx _ ].
      destruct from as [ | [ | from ] ]; destruct x as [ | [ | x ] ];
        cbn in Hfx |- *; try discriminate Hfx; lia.
    + exfalso.
      destruct from as [ | [ | from ] ];
        destruct x as [ | [ | x ] ];
        destruct y as [ | [ | y ] ]; cbn in Hc; discriminate Hc.
  - split; [ intros v Hs; cbn in Hs; discriminate Hs
           | intros v inner [ Hs _ ]; cbn in Hs; discriminate Hs ].
Qed.

Lemma mf_leaf_triple_sound : FnTripleSound mf_leaf_cfg mf_leaf_triple.
Proof.
  repeat split.
  - intros _ inner to [ _ [ _ [ _ Hto ] ] ]. cbn in Hto. discriminate Hto.
  - intros from inner to Hp _. cbn in Hp. discriminate Hp.
  - intros from inner Hp _. cbn in Hp. discriminate Hp.
  - intros inner to [ _ [ _ [ _ Hto ] ] ]. cbn in Hto. discriminate Hto.
  - intros inner [ _ [ _ [ Hc Hext ] ] ]. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + cbn in Hext. discriminate Hext.
    + destruct x as [ | [ | x ] ]; cbn in Hc, Hext |- *;
        try discriminate Hc; try discriminate Hext; lia.
    + exfalso.
      destruct x as [ | [ | x ] ]; destruct y as [ | [ | y ] ]; cbn in Hc; discriminate Hc.
Qed.

Lemma mf_rec_admits : YieldBoundAdmits mf_rec_cfg 6.
Proof.
  split; [ | split; [ | split ] ].
  - intros u v H. cbn in H. discriminate H.
  - intros v H. cbn in H. apply Nat.eqb_eq in H. subst v. reflexivity.
  - apply paths_within_reactions. intros from inner Hc Hi. unfold reaction_cost.
    destruct inner as [ | x [ | y [ | z rest ] ] ].
    + destruct from as [ | [ | [ | [ | from ] ] ] ]; cbn; lia.
    + destruct (path_head _ _ _ _ Hc Hi) as [ Hfx Hx ].
      destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ];
        cbn in Hfx, Hx |- *; try discriminate Hfx; try discriminate Hx; lia.
    + destruct (path_pair _ _ _ _ _ Hc Hi) as [ Hxy [ Hx Hy ] ].
      destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ];
        cbn in Hc, Hxy, Hx, Hy |- *;
        try discriminate Hc; try discriminate Hxy; try discriminate Hx; try discriminate Hy; lia.
    + exfalso.
      destruct (path_pair _ _ _ _ _ Hc Hi) as [ Hxy [ Hx Hy ] ].
      simpl in Hc, Hi. apply andb_prop in Hc. destruct Hc as [ _ Hc ].
      apply andb_prop in Hc. destruct Hc as [ _ Hc ].
      apply andb_prop in Hc. destruct Hc as [ Hyz _ ].
      apply andb_prop in Hi. destruct Hi as [ _ Hi ].
      apply andb_prop in Hi. destruct Hi as [ _ Hi ].
      apply andb_prop in Hi. destruct Hi as [ Hz _ ]. apply negb_true_iff in Hz.
      destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ];
        destruct z as [ | [ | [ | [ | z ] ] ] ];
        cbn in Hxy, Hyz, Hx, Hy, Hz;
        try discriminate Hxy; try discriminate Hyz; try discriminate Hx; try discriminate Hy; discriminate Hz.
  - split; [ intros v Hs; cbn in Hs; discriminate Hs
           | intros v inner [ Hs _ ]; cbn in Hs; discriminate Hs ].
Qed.

Lemma mf_rec_triple_sound : FnTripleSound mf_rec_cfg mf_rec_triple.
Proof.
  repeat split.
  - intros Hp0. cbn in Hp0. discriminate Hp0.
  - intros from inner to Hp [ _ [ Hi [ Hc Hto ] ] ]. unfold reaction_cost.
    destruct inner as [ | x [ | y rest ] ].
    + destruct from as [ | [ | [ | [ | from ] ] ] ]; cbn in Hp |- *; try discriminate Hp; lia.
    + destruct (path_head _ _ _ _ (chain_app _ _ _ _ Hc) Hi) as [ Hfx Hx ].
      destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ];
        cbn in Hp, Hfx, Hx |- *; try discriminate Hp; try discriminate Hfx; try discriminate Hx; lia.
    + exfalso. destruct (path_pair _ _ _ _ _ (chain_app _ _ _ _ Hc) Hi) as [ Hxy [ Hx Hy ] ].
      destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ];
        cbn in Hxy, Hx, Hy; try discriminate Hxy; try discriminate Hx; discriminate Hy.
  - intros from inner Hp [ _ [ Hi [ Hc Hext ] ] ]. unfold reaction_cost.
    destruct inner as [ | x [ | y [ | z rest ] ] ].
    + destruct from as [ | [ | [ | [ | from ] ] ] ]; cbn in Hp, Hext |- *;
        try discriminate Hp; try discriminate Hext; lia.
    + destruct from as [ | [ | [ | [ | from ] ] ] ];
        destruct x as [ | [ | [ | [ | x ] ] ] ];
        cbn in Hp, Hc, Hext |- *; try discriminate Hp; try discriminate Hc; try discriminate Hext; lia.
    + exfalso. destruct (path_pair _ _ _ _ _ Hc Hi) as [ Hxy [ Hx Hy ] ].
      destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ];
        cbn in Hxy, Hx, Hy, Hext;
        try discriminate Hxy; try discriminate Hx; try discriminate Hy; discriminate Hext.
    + exfalso. destruct (path_pair _ _ _ _ _ Hc Hi) as [ Hxy [ Hx Hy ] ].
      simpl in Hc, Hi. apply andb_prop in Hc. destruct Hc as [ _ Hc ].
      apply andb_prop in Hc. destruct Hc as [ _ Hc ].
      apply andb_prop in Hc. destruct Hc as [ Hyz _ ].
      apply andb_prop in Hi. destruct Hi as [ _ Hi ].
      apply andb_prop in Hi. destruct Hi as [ _ Hi ].
      apply andb_prop in Hi. destruct Hi as [ Hz _ ]. apply negb_true_iff in Hz.
      destruct x as [ | [ | [ | [ | x ] ] ] ];
        destruct y as [ | [ | [ | [ | y ] ] ] ];
        destruct z as [ | [ | [ | [ | z ] ] ] ];
        cbn in Hxy, Hyz, Hx, Hy, Hz;
        try discriminate Hxy; try discriminate Hyz; try discriminate Hx; try discriminate Hy; discriminate Hz.
  - left. reflexivity.
Qed.

(* Concrete inlined CFG theorems for BOTH direct and polled/recursive callees! *)
Lemma YieldBoundAdmits_weaken : forall g Y1 Y2,
  Y1 <= Y2 -> YieldBoundAdmits g Y1 -> YieldBoundAdmits g Y2.
Proof.
  intros g Y1 Y2 Hle [ Hb [ Hr [ [ Hrx Hex ] Hs ] ] ].
  split; [ exact Hb | split; [ exact Hr | split; [ split | exact Hs ] ] ].
  - intros from inner to H. pose proof (Hrx from inner to H). lia.
  - intros from inner H. pose proof (Hex from inner H). lia.
Qed.

Theorem positive_inlined_direct_and_recursive_callees_admitted :
  YieldBoundAdmits (inline_call_cfg mf_caller_cfg 1 2 mf_leaf_cfg) 7
  /\ YieldBoundAdmits (inline_call_cfg mf_caller_cfg 1 2 mf_rec_cfg) 6.
Proof.
  split.
  - apply (inline_call_cfg_admits mf_caller_cfg mf_leaf_cfg 1 2 3 2 7 mf_leaf_triple false).
    + exact (YieldBoundAdmits_weaken _ 6 7 ltac:(lia) mf_caller_admits).
    + exact (YieldBoundAdmits_weaken _ 6 7 ltac:(lia) mf_leaf_admits).
    + exact mf_leaf_triple_sound.
    + exact mf_caller_ctx_sound.
    + reflexivity.
  - apply (inline_call_cfg_admits mf_caller_cfg mf_rec_cfg 1 2 3 2 6 mf_rec_triple true).
    + exact mf_caller_admits.
    + exact mf_rec_admits.
    + exact mf_rec_triple_sound.
    + exact mf_caller_ctx_sound.
    + reflexivity.
Qed.

(* Multi-function whole-program trace combining loop, direct call, and recursive call. *)
Definition pos_cs_direct : CallSiteCheck := {|
  cs_pre_cost := 2; cs_callee := mf_leaf_triple; cs_post_cost := 2; cs_recursive := false
|}.

Definition pos_cs_rec : CallSiteCheck := {|
  cs_pre_cost := 3; cs_callee := mf_rec_triple; cs_post_cost := 2; cs_recursive := true
|}.

Definition pos_prog_steps : list ProgStep :=
  StepIntra 5
  :: StepCall pos_cs_direct (TrNoPoll 2)
  :: StepCall pos_cs_rec (TrWithPoll 0 [4] 3)
  :: nil.

Theorem positive_multifunction_trace_and_counter_admitted :
  prog_reactions pos_prog_steps = [5; 6; 3; 4; 5]
  /\ cs_invocations (run_counter 7 (prog_reactions pos_prog_steps)) = [11; 7]
  /\ forall g, In g (cs_invocations (run_counter 7 (prog_reactions pos_prog_steps))) -> g <= 7 + 6.
Proof.
  split; [ reflexivity | split; [ reflexivity | ] ].
  apply compositional_program_invocation_gaps_bounded.
  intros st Hin.
  destruct Hin as [ Heq | [ Heq | [ Heq | [] ] ] ]; subst st.
  - cbn. lia.
  - split; [ cbn; split; [ reflexivity | lia ] | apply call_site_admits_iff; reflexivity ].
  - split; [ cbn; repeat split; try reflexivity; lia | apply call_site_admits_iff; reflexivity ].
Qed.

(* -------------------------------------------------------------------------
   Explicit refutations (`R-05-165`, `R-05-166`).
   ------------------------------------------------------------------------- *)

(* 1. Unpolled back-edge. *)
Theorem refute_unpolled_back_edge :
  ~ PollsEveryBackEdge unpolled_cfg /\ ~ YieldBoundAdmits unpolled_cfg 6.
Proof.
  destruct an_unpolled_back_edge_admits_no_yield_bound as [ Hb _ ].
  split; [ exact Hb | intros [ H _ ]; exact (Hb H) ].
Qed.

(* 2. Unpolled recursive entry. *)
Definition unpolled_rec_cfg : Cfg := {|
  cfg_edge := fun u v => Nat.eqb u 0 && Nat.eqb v 1;
  cfg_back := fun _ _ => false;
  cfg_recursive_entry := fun v => Nat.eqb v 0;
  cfg_poll := fun _ => false;
  cfg_yield := fun _ => false;
  cfg_sink := fun _ => false;
  cfg_entry := 0;
  cfg_exit := fun v => Nat.eqb v 1;
  cfg_cost := fun _ => 1
|}.

Theorem refute_unpolled_recursive_entry :
  ~ PollsEveryRecursiveEntry unpolled_rec_cfg /\ ~ YieldBoundAdmits unpolled_rec_cfg 6.
Proof.
  assert (Hn : ~ PollsEveryRecursiveEntry unpolled_rec_cfg).
  { intros H. specialize (H 0 eq_refl). cbn in H. discriminate H. }
  split; [ exact Hn | intros [ _ [ H _ ] ]; exact (Hn H) ].
Qed.

(* 3. Over-bound intra-function reaction. *)
Theorem refute_overbound_intra_reaction :
  ~ ReactionsWithin loop_cfg 5 /\ ~ YieldBoundAdmits loop_cfg 5.
Proof.
  split.
  - intros [ H _ ].
    assert (Hr : Reaction loop_cfg 1 [2] 1).
    { repeat split; reflexivity. }
    specialize (H 1 [2] 1 Hr). unfold reaction_cost in H. cbn in H. lia.
  - exact a_reaction_above_the_bound_is_refused.
Qed.

(* 4. Over-bound cross-call reaction (`last_poll_to_exit + caller_post > Y`),
   refuted both by `call_site_admits` and by `YieldBoundAdmits` on `inline_call_cfg`. *)
Definition overbound_post_cs : CallSiteCheck := {|
  cs_pre_cost := 3;
  cs_callee := {| fn_entry_to_first_poll := 0; fn_poll_to_poll := 4;
                  fn_last_poll_to_exit := 5; fn_has_internal_poll := true |};
  cs_post_cost := 2;
  cs_recursive := true
|}.

Theorem refute_overbound_cross_call_last_poll_post :
  call_site_admits overbound_post_cs 6 = false
  /\ ~ CallSiteAdmits overbound_post_cs 6
  /\ ~ YieldBoundAdmits (inline_call_cfg mf_caller_cfg 1 2
         {| cfg_edge := cfg_edge mf_rec_cfg;
            cfg_back := cfg_back mf_rec_cfg;
            cfg_recursive_entry := cfg_recursive_entry mf_rec_cfg;
            cfg_poll := cfg_poll mf_rec_cfg;
            cfg_yield := cfg_yield mf_rec_cfg;
            cfg_sink := cfg_sink mf_rec_cfg;
            cfg_entry := cfg_entry mf_rec_cfg;
            cfg_exit := cfg_exit mf_rec_cfg;
            cfg_cost := fun v => if Nat.eqb v 3 then 4 else cfg_cost mf_rec_cfg v |}) 6.
Proof.
  split; [ reflexivity | split ].
  - intros H. apply call_site_admits_iff in H. discriminate H.
  - intros [ _ [ _ [ [ _ Hex ] _ ] ] ].
    set (bad_rec := {| cfg_edge := cfg_edge mf_rec_cfg;
                       cfg_back := cfg_back mf_rec_cfg;
                       cfg_recursive_entry := cfg_recursive_entry mf_rec_cfg;
                       cfg_poll := cfg_poll mf_rec_cfg;
                       cfg_yield := cfg_yield mf_rec_cfg;
                       cfg_sink := cfg_sink mf_rec_cfg;
                       cfg_entry := cfg_entry mf_rec_cfg;
                       cfg_exit := cfg_exit mf_rec_cfg;
                       cfg_cost := fun v => if Nat.eqb v 3 then 4 else cfg_cost mf_rec_cfg v |}).
    assert (He : ExitReaction (inline_call_cfg mf_caller_cfg 1 2 bad_rec)
                   (2 * 2 + 1) [2 * 3 + 1; 2 * 2; 2 * 3]).
    { repeat split; reflexivity. }
    specialize (Hex (2 * 2 + 1) [2 * 3 + 1; 2 * 2; 2 * 3] He).
    unfold reaction_cost in Hex. cbn in Hex. lia.
Qed.

(* 5. Sink returning to tentative poll without real yield. *)
Theorem refute_sink_returning_to_tentative_poll :
  ~ SinksYieldWithinOneReaction unyielding_cfg /\ ~ YieldBoundAdmits unyielding_cfg 6.
Proof.
  destruct a_sink_that_does_not_yield_is_refused as [ _ [ _ [ _ [ Hs Hy ] ] ] ].
  split; [ exact Hs | exact Hy ].
Qed.

(* 6. Misconfigured strip-mine factor (`k = 0` or `k * body_cost + poll_cost > Y`). *)
Definition bad_zero_strip : StripMineSpec := {|
  sm_k := 0; sm_body_cost := 2; sm_poll_cost := 1; sm_yield_bound := 6
|}.

Definition bad_over_strip : StripMineSpec := {|
  sm_k := 4; sm_body_cost := 2; sm_poll_cost := 1; sm_yield_bound := 6
|}.

Definition bad_over_loop : LoopSpec := {|
  lp_strip := bad_over_strip;
  lp_entry_cost := 1; lp_exit_cost := 1; lp_sink_cost := 1; lp_yield_site_cost := 1
|}.

Theorem refute_misconfigured_strip_mine_factor :
  strip_mine_admits bad_zero_strip = false
  /\ ~ StripMineAdmits bad_zero_strip
  /\ strip_mine_admits bad_over_strip = false
  /\ ~ StripMineAdmits bad_over_strip
  /\ ~ YieldBoundAdmits (strip_mine_cfg bad_over_loop) 6.
Proof.
  split; [ reflexivity | split; [ | split; [ reflexivity | split ] ] ].
  - intros [ H _ ]. cbn in H. lia.
  - intros [ _ H ]. unfold strip_mine_reaction_cost in H. cbn in H. lia.
  - intros [ _ [ _ [ [ Hrx _ ] _ ] ] ].
    assert (Hr : Reaction (strip_mine_cfg bad_over_loop) 1 [2] 1).
    { repeat split; reflexivity. }
    specialize (Hrx 1 [2] 1 Hr). unfold reaction_cost in Hrx. cbn in Hrx. lia.
Qed.

(* =========================================================================
   R-05-166 inhabitation witnesses for every local Record.
   ========================================================================= *)

Definition witness_StripMineSpec : StripMineSpec := pos_strip_spec.
Definition witness_LoopSpec : LoopSpec := pos_loop_spec.
Definition witness_FnCostTriple : FnCostTriple := mf_rec_triple.
Definition witness_CallSiteCheck : CallSiteCheck := pos_cs_rec.
Definition witness_FnSummary : FnSummary := {|
  fn_intra_reactions := [5; 4];
  fn_calls := [pos_cs_direct; pos_cs_rec];
  fn_triple := mf_rec_triple
|}.
Definition witness_CounterState : CounterState := run_counter 7 (prog_reactions pos_prog_steps).
