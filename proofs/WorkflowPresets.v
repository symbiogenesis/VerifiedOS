(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   WorkflowPresets.v

   Q32c-i formalization of workflow preset recipes, the explicit reachable
   graph of power/profile/focus combinations and transition certificates,
   standing-service preservation, exact steady/transition byte ledgers with
   `Reusable`-gated physical overlap credit, reclamation-strategy comparison
   (`FrozenResident`, `SemanticHibernation`, `FixedPoolReuse`), and
   repeated-toggling dwell, quarantine, and storage endurance bounds.

   Requirements cited:
   - R-05-163, R-05-164: zero axioms under assumption audit and `rocqchk`.
   - R-05-165, R-05-166: non-vacuous `witness_<Record>` inhabitants for every
     declared record, plus positive witnesses and distinguishing refutations.
   - R-08-046: bounded static pools with monotone member lifecycle and
     quarantine/reuse bounds.
   - R-11-018, R-11-018a: explicit reachable mode/profile/rung graph and
     certified transitions (never Cartesian-product assumption), local vs
     RoT-attested global mode switches, no implicit authority, and the six
     product preset recipes.
   - R-13-027a: development build distinction (elastic domain member vs
     composition mode) and successor-generation execution only.
   - R-18-004, R-18-004a: browser deferral gate and laptop product floor
     preservation without silent floor enlargement or composition borrowing.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-08-046 R-11-018 R-11-018a R-13-027a
      R-18-004 R-18-004a
   SHA256: 5ecd0bd29563b5ac22d5c07103202143ee8f484f741a6b21e6def76e6e0829f3
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport.
Import ProofSupport.Tactics.

Open Scope list_scope.

(* =========================================================================
   S0. Prelude-only numeric comparison helpers.
   ========================================================================= *)

Lemma nat_leb_le_iff : forall a b : nat, Nat.leb a b = true <-> a <= b.
Proof.
  intro a. induction a as [| a IH]; intro b; destruct b as [| b]; split; intro H.
  - apply le_0_n.
  - reflexivity.
  - apply le_0_n.
  - reflexivity.
  - discriminate H.
  - inversion H.
  - apply le_n_S. exact (proj1 (IH b) H).
  - apply (proj2 (IH b)). exact (le_S_n _ _ H).
Qed.

Lemma nat_ltb_lt_iff : forall a b : nat, Nat.ltb a b = true <-> a < b.
Proof.
  intros a b. exact (nat_leb_le_iff (S a) b).
Qed.

Lemma only_if_true_iff : forall a b : bool,
  ProofSupport.only_if a b = true <-> (a = true -> b = true).
Proof.
  intros [] []; split; intro H; try reflexivity; try discriminate H; auto.
Qed.

Lemma nat_leb_sub_le : forall a b : nat, Nat.leb (a - b) a = true.
Proof.
  intro a. induction a as [| a IH]; intro b.
  - reflexivity.
  - destruct b as [| b]; simpl.
    + exact (ProofSupport.nat_leb_refl (S a)).
    + exact (ProofSupport.nat_leb_succ_r (a - b) a (IH b)).
Qed.

(* =========================================================================
   S1. Preset recipes, separate selections, standing services, and overlap.
   ========================================================================= *)

Inductive PresetRecipe : Type :=
| Everyday
| Writing
| Browsing
| ImageEditing
| Messaging
| Development.

Definition recipe_eqb (a b : PresetRecipe) : bool :=
  match a, b with
  | Everyday, Everyday => true
  | Writing, Writing => true
  | Browsing, Browsing => true
  | ImageEditing, ImageEditing => true
  | Messaging, Messaging => true
  | Development, Development => true
  | _, _ => false
  end.

Lemma recipe_eqb_refl : forall r : PresetRecipe, recipe_eqb r r = true.
Proof. intros []; reflexivity. Qed.

Lemma recipe_eqb_true : forall a b : PresetRecipe, recipe_eqb a b = true -> a = b.
Proof. intros [] [] H; try discriminate H; reflexivity. Qed.

Definition all_recipes : list PresetRecipe :=
  cons Everyday (cons Writing (cons Browsing
    (cons ImageEditing (cons Messaging (cons Development nil))))).

Lemma all_recipes_complete : forall r : PresetRecipe,
  ProofSupport.any_of (recipe_eqb r) all_recipes = true.
Proof. intros []; reflexivity. Qed.

Inductive PowerMode : Type :=
| PowerBalanced
| PowerPerformance
| PowerLowPower.

Definition power_mode_eqb (a b : PowerMode) : bool :=
  match a, b with
  | PowerBalanced, PowerBalanced => true
  | PowerPerformance, PowerPerformance => true
  | PowerLowPower, PowerLowPower => true
  | _, _ => false
  end.

Lemma power_mode_eqb_refl : forall p : PowerMode, power_mode_eqb p p = true.
Proof. intros []; reflexivity. Qed.

Lemma power_mode_eqb_true : forall a b : PowerMode, power_mode_eqb a b = true -> a = b.
Proof. intros [] [] H; try discriminate H; reflexivity. Qed.

Inductive FocusRung : Type :=
| RungCompact
| RungStandard
| RungExpanded.

Definition rung_eqb (a b : FocusRung) : bool :=
  match a, b with
  | RungCompact, RungCompact => true
  | RungStandard, RungStandard => true
  | RungExpanded, RungExpanded => true
  | _, _ => false
  end.

Lemma rung_eqb_refl : forall r : FocusRung, rung_eqb r r = true.
Proof. intros []; reflexivity. Qed.

Lemma rung_eqb_true : forall a b : FocusRung, rung_eqb a b = true -> a = b.
Proof. intros [] [] H; try discriminate H; reflexivity. Qed.

Record SelectionTriple : Type := {
  sel_power : PowerMode;
  sel_profile : PresetRecipe;
  sel_rung : FocusRung
}.

Definition witness_SelectionTriple : SelectionTriple := {|
  sel_power := PowerBalanced;
  sel_profile := Everyday;
  sel_rung := RungStandard
|}.

Definition selection_eqb (a b : SelectionTriple) : bool :=
  andb (power_mode_eqb (sel_power a) (sel_power b))
       (andb (recipe_eqb (sel_profile a) (sel_profile b))
             (rung_eqb (sel_rung a) (sel_rung b))).

Lemma selection_eqb_refl : forall s : SelectionTriple, selection_eqb s s = true.
Proof.
  intros [p r f]. unfold selection_eqb; simpl.
  rewrite power_mode_eqb_refl, recipe_eqb_refl, rung_eqb_refl. reflexivity.
Qed.

Lemma selection_eqb_true : forall a b : SelectionTriple,
  selection_eqb a b = true -> a = b.
Proof.
  intros [p1 r1 f1] [p2 r2 f2] H. unfold selection_eqb in H; simpl in H.
  destruct (ProofSupport.andb_split _ _ H) as [Hp Hrf].
  destruct (ProofSupport.andb_split _ _ Hrf) as [Hr Hf].
  rewrite (power_mode_eqb_true _ _ Hp).
  rewrite (recipe_eqb_true _ _ Hr).
  rewrite (rung_eqb_true _ _ Hf).
  reflexivity.
Qed.

Inductive DevBuildMode : Type :=
| DevElastic
| DevComposition.

Definition dev_mode_eqb (a b : DevBuildMode) : bool :=
  match a, b with
  | DevElastic, DevElastic => true
  | DevComposition, DevComposition => true
  | _, _ => false
  end.

Inductive ReclamationStrategy : Type :=
| FrozenResident
| SemanticHibernation
| FixedPoolReuse.

Definition strategy_eqb (a b : ReclamationStrategy) : bool :=
  match a, b with
  | FrozenResident, FrozenResident => true
  | SemanticHibernation, SemanticHibernation => true
  | FixedPoolReuse, FixedPoolReuse => true
  | _, _ => false
  end.

(* Standing services that must remain reserved whenever the product contract
   requires them; dropping one to manufacture a memory saving is refused. *)
Record StandingServices : Type := {
  svc_audio : bool;
  svc_radio : bool;
  svc_display : bool;
  svc_storage : bool;
  svc_revocation : bool;
  svc_consent : bool;
  svc_inference : bool
}.

Definition required_standing_default : StandingServices := {|
  svc_audio := true;
  svc_radio := true;
  svc_display := true;
  svc_storage := true;
  svc_revocation := true;
  svc_consent := true;
  svc_inference := true
|}.

Definition witness_StandingServices : StandingServices := required_standing_default.

Definition standing_intact (req actual : StandingServices) : bool :=
  andb (ProofSupport.only_if (svc_audio req) (svc_audio actual))
  (andb (ProofSupport.only_if (svc_radio req) (svc_radio actual))
  (andb (ProofSupport.only_if (svc_display req) (svc_display actual))
  (andb (ProofSupport.only_if (svc_storage req) (svc_storage actual))
  (andb (ProofSupport.only_if (svc_revocation req) (svc_revocation actual))
  (andb (ProofSupport.only_if (svc_consent req) (svc_consent actual))
        (ProofSupport.only_if (svc_inference req) (svc_inference actual))))))).

Definition StandingIntact (req actual : StandingServices) : Prop :=
  (svc_audio req = true -> svc_audio actual = true) /\
  (svc_radio req = true -> svc_radio actual = true) /\
  (svc_display req = true -> svc_display actual = true) /\
  (svc_storage req = true -> svc_storage actual = true) /\
  (svc_revocation req = true -> svc_revocation actual = true) /\
  (svc_consent req = true -> svc_consent actual = true) /\
  (svc_inference req = true -> svc_inference actual = true).

Lemma standing_intact_iff : forall req actual : StandingServices,
  standing_intact req actual = true <-> StandingIntact req actual.
Proof.
  intros req actual. unfold standing_intact, StandingIntact. split.
  - intro H.
    destruct (ProofSupport.andb_split _ _ H) as [H1 R1].
    destruct (ProofSupport.andb_split _ _ R1) as [H2 R2].
    destruct (ProofSupport.andb_split _ _ R2) as [H3 R3].
    destruct (ProofSupport.andb_split _ _ R3) as [H4 R4].
    destruct (ProofSupport.andb_split _ _ R4) as [H5 R5].
    destruct (ProofSupport.andb_split _ _ R5) as [H6 H7].
    repeat split; intro Ha;
      [ exact (proj1 (only_if_true_iff _ _) H1 Ha)
      | exact (proj1 (only_if_true_iff _ _) H2 Ha)
      | exact (proj1 (only_if_true_iff _ _) H3 Ha)
      | exact (proj1 (only_if_true_iff _ _) H4 Ha)
      | exact (proj1 (only_if_true_iff _ _) H5 Ha)
      | exact (proj1 (only_if_true_iff _ _) H6 Ha)
      | exact (proj1 (only_if_true_iff _ _) H7 Ha) ].
  - intros [H1 [H2 [H3 [H4 [H5 [H6 H7]]]]]].
    repeat apply ProofSupport.andb_join;
      apply (proj2 (only_if_true_iff _ _)); assumption.
Qed.

(* Exact byte ledger and `Reusable`-gated physical overlap credit. *)
Definition raw_ram_demand (perm live_frozen cp_ws quar meta : nat) : nat :=
  perm + live_frozen + cp_ws + quar + meta.

Definition overlap_credit_valid
    (reusable_proved : bool) (credit private_bytes : nat) : bool :=
  andb (ProofSupport.only_if (Nat.ltb 0 credit) reusable_proved)
       (Nat.leb credit private_bytes).

Definition OverlapCreditValid
    (reusable_proved : bool) (credit private_bytes : nat) : Prop :=
  (0 < credit -> reusable_proved = true) /\ credit <= private_bytes.

Lemma overlap_credit_valid_iff :
  forall (reusable_proved : bool) (credit private_bytes : nat),
    overlap_credit_valid reusable_proved credit private_bytes = true <->
    OverlapCreditValid reusable_proved credit private_bytes.
Proof.
  intros r c p. unfold overlap_credit_valid, OverlapCreditValid. split.
  - intro H. destruct (ProofSupport.andb_split _ _ H) as [H1 H2].
    split.
    + intro Hlt. exact (proj1 (only_if_true_iff _ _) H1 (proj2 (nat_ltb_lt_iff 0 c) Hlt)).
    + exact (proj1 (nat_leb_le_iff c p) H2).
  - intros [H1 H2]. apply ProofSupport.andb_join.
    + apply (proj2 (only_if_true_iff _ _)). intro Hlt.
      exact (H1 (proj1 (nat_ltb_lt_iff 0 c) Hlt)).
    + exact (proj2 (nat_leb_le_iff c p) H2).
Qed.

Definition effective_ram_demand
    (perm live_frozen cp_ws quar meta : nat)
    (reusable_proved : bool) (credit : nat) : nat :=
  raw_ram_demand perm live_frozen cp_ws quar meta -
  (if reusable_proved then credit else 0).

(* =========================================================================
   S2. Preset recipe catalog and product-policy checks (`R-11-018a`,
       `R-13-027a`, `R-18-004`, `R-18-004a`).
   ========================================================================= *)

Record RecipeSpec : Type := {
  rec_kind : PresetRecipe;
  rec_enabled : bool;
  rec_port_available : bool;
  rec_browser_port_qualified : bool;
  rec_dev_mode : DevBuildMode;
  rec_dev_exec_successor_only : bool;
  rec_borrows_composition_for_floor : bool;
  rec_laptop_floor_ok : bool;
  rec_standing : StandingServices;
  rec_companions_admitted : bool;
  rec_implicit_authority : bool;
  rec_strategy : ReclamationStrategy;
  rec_useful_state_bytes : nat;
  rec_perm_bytes : nat;
  rec_live_or_frozen_bytes : nat;
  rec_cp_ws_bytes : nat;
  rec_quarantined_bytes : nat;
  rec_metadata_bytes : nat;
  rec_store_cp_bytes : nat;
  rec_store_scratch_bytes : nat;
  rec_reusable_proved : bool;
  rec_overlap_credit_bytes : nat;
  rec_ram_budget : nat;
  rec_store_budget : nat
}.

Definition recipe_effective_ram (r : RecipeSpec) : nat :=
  effective_ram_demand
    (rec_perm_bytes r) (rec_live_or_frozen_bytes r) (rec_cp_ws_bytes r)
    (rec_quarantined_bytes r) (rec_metadata_bytes r)
    (rec_reusable_proved r) (rec_overlap_credit_bytes r).

Definition recipe_store_demand (r : RecipeSpec) : nat :=
  rec_store_cp_bytes r + rec_store_scratch_bytes r.

Definition recipe_browser_gate_ok (r : RecipeSpec) : bool :=
  match rec_kind r with
  | Browsing => ProofSupport.only_if (rec_enabled r) (rec_browser_port_qualified r)
  | _ => true
  end.

Definition recipe_dev_gate_ok (r : RecipeSpec) : bool :=
  match rec_kind r with
  | Development =>
      ProofSupport.only_if (rec_enabled r)
        (andb (rec_dev_exec_successor_only r)
              (negb (rec_borrows_composition_for_floor r)))
  | _ => negb (rec_borrows_composition_for_floor r)
  end.

Definition recipe_admitted (req : StandingServices) (r : RecipeSpec) : bool :=
  andb (recipe_browser_gate_ok r)
  (andb (recipe_dev_gate_ok r)
  (andb (ProofSupport.only_if (rec_enabled r) (rec_port_available r))
  (andb (ProofSupport.only_if (rec_enabled r)
          (andb (rec_laptop_floor_ok r) (rec_companions_admitted r)))
  (andb (negb (rec_implicit_authority r))
  (andb (standing_intact req (rec_standing r))
  (andb (overlap_credit_valid (rec_reusable_proved r)
            (rec_overlap_credit_bytes r) (rec_live_or_frozen_bytes r))
        (ProofSupport.only_if (rec_enabled r)
          (andb (Nat.leb (recipe_effective_ram r) (rec_ram_budget r))
                (Nat.leb (recipe_store_demand r) (rec_store_budget r)))))))))).

Definition catalog_covers_all_recipes (cat : list RecipeSpec) : bool :=
  ProofSupport.all_of
    (fun k => ProofSupport.any_of (fun r => recipe_eqb k (rec_kind r)) cat)
    all_recipes.

Definition catalog_admitted (req : StandingServices) (cat : list RecipeSpec) : bool :=
  andb (catalog_covers_all_recipes cat)
       (ProofSupport.all_of (recipe_admitted req) cat).

Definition recipe_everyday : RecipeSpec := {|
  rec_kind := Everyday;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := SemanticHibernation;
  rec_useful_state_bytes := 64;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 64;
  rec_cp_ws_bytes := 16;
  rec_quarantined_bytes := 16;
  rec_metadata_bytes := 8;
  rec_store_cp_bytes := 32;
  rec_store_scratch_bytes := 16;
  rec_reusable_proved := true;
  rec_overlap_credit_bytes := 32;
  rec_ram_budget := 160;
  rec_store_budget := 64
|}.

Definition witness_RecipeSpec : RecipeSpec := recipe_everyday.

Definition recipe_writing : RecipeSpec := {|
  rec_kind := Writing;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := SemanticHibernation;
  rec_useful_state_bytes := 96;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 96;
  rec_cp_ws_bytes := 24;
  rec_quarantined_bytes := 16;
  rec_metadata_bytes := 8;
  rec_store_cp_bytes := 48;
  rec_store_scratch_bytes := 16;
  rec_reusable_proved := true;
  rec_overlap_credit_bytes := 48;
  rec_ram_budget := 192;
  rec_store_budget := 80
|}.

(* Browsing is explicitly deferred under R-18-004 unless its port is qualified. *)
Definition recipe_browsing_deferred : RecipeSpec := {|
  rec_kind := Browsing;
  rec_enabled := false;
  rec_port_available := false;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := FrozenResident;
  rec_useful_state_bytes := 128;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 128;
  rec_cp_ws_bytes := 0;
  rec_quarantined_bytes := 0;
  rec_metadata_bytes := 12;
  rec_store_cp_bytes := 0;
  rec_store_scratch_bytes := 0;
  rec_reusable_proved := false;
  rec_overlap_credit_bytes := 0;
  rec_ram_budget := 256;
  rec_store_budget := 64
|}.

Definition recipe_image_editing : RecipeSpec := {|
  rec_kind := ImageEditing;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := SemanticHibernation;
  rec_useful_state_bytes := 128;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 128;
  rec_cp_ws_bytes := 32;
  rec_quarantined_bytes := 24;
  rec_metadata_bytes := 12;
  rec_store_cp_bytes := 64;
  rec_store_scratch_bytes := 24;
  rec_reusable_proved := true;
  rec_overlap_credit_bytes := 64;
  rec_ram_budget := 224;
  rec_store_budget := 96
|}.

Definition recipe_messaging : RecipeSpec := {|
  rec_kind := Messaging;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := FixedPoolReuse;
  rec_useful_state_bytes := 48;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 48;
  rec_cp_ws_bytes := 0;
  rec_quarantined_bytes := 16;
  rec_metadata_bytes := 8;
  rec_store_cp_bytes := 0;
  rec_store_scratch_bytes := 0;
  rec_reusable_proved := true;
  rec_overlap_credit_bytes := 16;
  rec_ram_budget := 128;
  rec_store_budget := 32
|}.

Definition recipe_development_elastic : RecipeSpec := {|
  rec_kind := Development;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := FixedPoolReuse;
  rec_useful_state_bytes := 128;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 128;
  rec_cp_ws_bytes := 16;
  rec_quarantined_bytes := 24;
  rec_metadata_bytes := 12;
  rec_store_cp_bytes := 32;
  rec_store_scratch_bytes := 16;
  rec_reusable_proved := true;
  rec_overlap_credit_bytes := 32;
  rec_ram_budget := 224;
  rec_store_budget := 64
|}.

Definition default_catalog : list RecipeSpec :=
  cons recipe_everyday (cons recipe_writing (cons recipe_browsing_deferred
    (cons recipe_image_editing (cons recipe_messaging
      (cons recipe_development_elastic nil))))).

(*| discharges: R-11-018a |*)
Theorem default_catalog_admitted :
  catalog_admitted required_standing_default default_catalog = true.
Proof. vm_reflexivity. Qed.

(*| discharges: R-18-004 |*)
Theorem enabled_browser_requires_qualified_port :
  forall (req : StandingServices) (r : RecipeSpec),
    recipe_admitted req r = true ->
    rec_kind r = Browsing ->
    rec_enabled r = true ->
    rec_browser_port_qualified r = true.
Proof.
  intros req r Hadm Hkind Hen.
  unfold recipe_admitted in Hadm.
  destruct (ProofSupport.andb_split _ _ Hadm) as [Hbr _].
  unfold recipe_browser_gate_ok in Hbr. rewrite Hkind in Hbr.
  exact (ProofSupport.only_if_elim _ _ Hbr Hen).
Qed.

(*| discharges: R-13-027a |*)
Theorem enabled_development_requires_successor_exec_and_no_floor_borrow :
  forall (req : StandingServices) (r : RecipeSpec),
    recipe_admitted req r = true ->
    rec_kind r = Development ->
    rec_enabled r = true ->
    rec_dev_exec_successor_only r = true /\
    rec_borrows_composition_for_floor r = false.
Proof.
  intros req r Hadm Hkind Hen.
  unfold recipe_admitted in Hadm.
  destruct (ProofSupport.andb_split _ _ Hadm) as [_ Hrest].
  destruct (ProofSupport.andb_split _ _ Hrest) as [Hdev _].
  unfold recipe_dev_gate_ok in Hdev. rewrite Hkind in Hdev.
  pose proof (ProofSupport.only_if_elim _ _ Hdev Hen) as Hpair.
  destruct (ProofSupport.andb_split _ _ Hpair) as [Hsucc Hnb].
  split; [exact Hsucc | exact (ProofSupport.negb_true _ Hnb)].
Qed.

(* =========================================================================
   S3. Reachable graph of steady states and directed transition edges
       (`R-11-018`, `R-11-018a`).
   ========================================================================= *)

Record SteadyNode : Type := {
  node_id : nat;
  node_sel : SelectionTriple;
  node_standing : StandingServices;
  node_implicit_authority : bool;
  node_floor_ok : bool;
  node_perm_bytes : nat;
  node_private_bytes : nat;
  node_cp_ws_bytes : nat;
  node_quarantined_bytes : nat;
  node_metadata_bytes : nat;
  node_store_bytes : nat
}.

Definition node_ram (n : SteadyNode) : nat :=
  raw_ram_demand (node_perm_bytes n) (node_private_bytes n)
    (node_cp_ws_bytes n) (node_quarantined_bytes n) (node_metadata_bytes n).

Definition witness_SteadyNode : SteadyNode := {|
  node_id := 0;
  node_sel := witness_SelectionTriple;
  node_standing := required_standing_default;
  node_implicit_authority := false;
  node_floor_ok := true;
  node_perm_bytes := 48;
  node_private_bytes := 64;
  node_cp_ws_bytes := 0;
  node_quarantined_bytes := 0;
  node_metadata_bytes := 8;
  node_store_bytes := 32
|}.

Record TransitionEdge : Type := {
  edge_src_id : nat;
  edge_dst_id : nat;
  edge_local_only : bool;
  edge_power_unchanged : bool;
  edge_root_attested : bool;
  edge_explicit_authority : bool;
  edge_standing : StandingServices;
  edge_reusable_proved : bool;
  edge_overlap_credit : nat;
  edge_perm_bytes : nat;
  edge_private_bytes : nat;
  edge_cp_ws_bytes : nat;
  edge_quarantined_bytes : nat;
  edge_metadata_bytes : nat;
  edge_store_bytes : nat;
  edge_old_last_gap : nat;
  edge_mid_gap : nat;
  edge_new_first_gap : nat;
  edge_continuing_deadline : nat;
  edge_work_cost : nat;
  edge_deadline : nat;
  edge_recovery_reserved : bool;
  edge_cert_valid : bool
}.

Definition edge_effective_ram (e : TransitionEdge) : nat :=
  effective_ram_demand (edge_perm_bytes e) (edge_private_bytes e)
    (edge_cp_ws_bytes e) (edge_quarantined_bytes e) (edge_metadata_bytes e)
    (edge_reusable_proved e) (edge_overlap_credit e).

Definition edge_service_chain (e : TransitionEdge) : nat :=
  edge_old_last_gap e + edge_mid_gap e + edge_new_first_gap e.

Definition witness_TransitionEdge : TransitionEdge := {|
  edge_src_id := 0;
  edge_dst_id := 1;
  edge_local_only := true;
  edge_power_unchanged := true;
  edge_root_attested := false;
  edge_explicit_authority := true;
  edge_standing := required_standing_default;
  edge_reusable_proved := true;
  edge_overlap_credit := 32;
  edge_perm_bytes := 48;
  edge_private_bytes := 64;
  edge_cp_ws_bytes := 16;
  edge_quarantined_bytes := 16;
  edge_metadata_bytes := 8;
  edge_store_bytes := 48;
  edge_old_last_gap := 2;
  edge_mid_gap := 4;
  edge_new_first_gap := 2;
  edge_continuing_deadline := 8;
  edge_work_cost := 10;
  edge_deadline := 12;
  edge_recovery_reserved := true;
  edge_cert_valid := true
|}.

Record ModeGraph : Type := {
  mg_required_standing : StandingServices;
  mg_nodes : list SteadyNode;
  mg_edges : list TransitionEdge;
  mg_ram_capacity : nat;
  mg_store_capacity : nat
}.

Fixpoint find_node (id : nat) (nodes : list SteadyNode) : option SteadyNode :=
  match nodes with
  | nil => None
  | cons n rest => if Nat.eqb id (node_id n) then Some n else find_node id rest
  end.

Fixpoint distinct_node_ids (nodes : list SteadyNode) : bool :=
  match nodes with
  | nil => true
  | cons n rest =>
      andb (negb (ProofSupport.any_of (fun m => Nat.eqb (node_id n) (node_id m)) rest))
           (distinct_node_ids rest)
  end.

Definition node_admitted (g : ModeGraph) (n : SteadyNode) : bool :=
  andb (negb (node_implicit_authority n))
  (andb (standing_intact (mg_required_standing g) (node_standing n))
  (andb (node_floor_ok n)
  (andb (Nat.leb (node_ram n) (mg_ram_capacity g))
        (Nat.leb (node_store_bytes n) (mg_store_capacity g))))).

Definition edge_endpoints_ok (g : ModeGraph) (e : TransitionEdge) : bool :=
  match find_node (edge_src_id e) (mg_nodes g),
        find_node (edge_dst_id e) (mg_nodes g) with
  | Some src, Some dst =>
      if edge_local_only e
      then andb (edge_power_unchanged e)
                (power_mode_eqb (sel_power (node_sel src)) (sel_power (node_sel dst)))
      else edge_root_attested e
  | _, _ => false
  end.

Definition edge_admitted (g : ModeGraph) (e : TransitionEdge) : bool :=
  andb (edge_cert_valid e)
  (andb (edge_explicit_authority e)
  (andb (edge_endpoints_ok g e)
  (andb (standing_intact (mg_required_standing g) (edge_standing e))
  (andb (overlap_credit_valid (edge_reusable_proved e)
            (edge_overlap_credit e) (edge_private_bytes e))
  (andb (Nat.leb (edge_service_chain e) (edge_continuing_deadline e))
  (andb (Nat.leb (edge_work_cost e) (edge_deadline e))
  (andb (edge_recovery_reserved e)
  (andb (Nat.leb (edge_effective_ram e) (mg_ram_capacity g))
        (Nat.leb (edge_store_bytes e) (mg_store_capacity g)))))))))).

Definition graph_admitted (g : ModeGraph) : bool :=
  andb (distinct_node_ids (mg_nodes g))
  (andb (ProofSupport.all_of (node_admitted g) (mg_nodes g))
        (ProofSupport.all_of (edge_admitted g) (mg_edges g))).

Definition graph_steady_peak_ram (g : ModeGraph) : nat :=
  ProofSupport.fold_over (fun acc n => Nat.max acc (node_ram n)) 0 (mg_nodes g).

Definition graph_transition_peak_ram (g : ModeGraph) : nat :=
  ProofSupport.fold_over (fun acc e => Nat.max acc (edge_effective_ram e)) 0 (mg_edges g).

Definition graph_peak_ram (g : ModeGraph) : nat :=
  Nat.max (graph_steady_peak_ram g) (graph_transition_peak_ram g).

Definition graph_steady_peak_store (g : ModeGraph) : nat :=
  ProofSupport.fold_over (fun acc n => Nat.max acc (node_store_bytes n)) 0 (mg_nodes g).

Definition graph_transition_peak_store (g : ModeGraph) : nat :=
  ProofSupport.fold_over (fun acc e => Nat.max acc (edge_store_bytes e)) 0 (mg_edges g).

Definition graph_peak_store (g : ModeGraph) : nat :=
  Nat.max (graph_steady_peak_store g) (graph_transition_peak_store g).

Definition edge_matches_selections
    (g : ModeGraph) (src dst : SelectionTriple) (e : TransitionEdge) : bool :=
  match find_node (edge_src_id e) (mg_nodes g),
        find_node (edge_dst_id e) (mg_nodes g) with
  | Some sn, Some dn =>
      andb (selection_eqb (node_sel sn) src)
           (andb (selection_eqb (node_sel dn) dst) (edge_admitted g e))
  | _, _ => false
  end.

Definition selection_edge_reachable
    (g : ModeGraph) (src dst : SelectionTriple) : bool :=
  ProofSupport.any_of (edge_matches_selections g src dst) (mg_edges g).

Lemma fold_max_bound : forall (A : Type) (f : A -> nat) (l : list A) (init cap : nat),
  Nat.leb init cap = true ->
  ProofSupport.all_of (fun x => Nat.leb (f x) cap) l = true ->
  Nat.leb (ProofSupport.fold_over (fun acc x => Nat.max acc (f x)) init l) cap = true.
Proof.
  intros A f l. induction l as [| x rest IH]; intros init cap Hinit Hall.
  - exact Hinit.
  - simpl in Hall. destruct (ProofSupport.andb_split _ _ Hall) as [Hx Hrest].
    simpl. apply IH.
    + exact (ProofSupport.nat_max_upper init (f x) cap Hinit Hx).
    + exact Hrest.
Qed.

Lemma fold_max_member : forall (A : Type) (f : A -> nat) (l : list A) (init : nat) (x : A),
  ProofSupport.Member x l ->
  Nat.leb (f x) (ProofSupport.fold_over (fun acc y => Nat.max acc (f y)) init l) = true.
Proof.
  intros A f l. induction l as [| y rest IH]; intros init x Hmem.
  - contradiction Hmem.
  - simpl. destruct Hmem as [Heq | Hrest].
    + subst y.
      assert (Hacc : Nat.leb (f x) (Nat.max init (f x)) = true)
        by exact (ProofSupport.nat_max_right init (f x)).
      clear IH. revert Hacc.
      generalize (Nat.max init (f x)) as cur.
      induction rest as [| z zs IHz]; intros cur Hcur.
      * exact Hcur.
      * simpl. apply IHz.
        exact (ProofSupport.nat_leb_trans (f x) cur (Nat.max cur (f z))
                 Hcur (ProofSupport.nat_max_left cur (f z))).
    + exact (IH (Nat.max init (f y)) x Hrest).
Qed.

(*| discharges: R-11-018, R-11-018a |*)
Theorem admitted_graph_peak_fits_capacity : forall g : ModeGraph,
  graph_admitted g = true ->
  graph_peak_ram g <= mg_ram_capacity g /\
  graph_peak_store g <= mg_store_capacity g.
Proof.
  intros g Hadm.
  unfold graph_admitted in Hadm.
  destruct (ProofSupport.andb_split _ _ Hadm) as [_ Hne].
  destruct (ProofSupport.andb_split _ _ Hne) as [Hnodes Hedges].
  assert (Hns_ram : ProofSupport.all_of
    (fun n => Nat.leb (node_ram n) (mg_ram_capacity g)) (mg_nodes g) = true).
  { apply (ProofSupport.all_of_mono _ (node_admitted g)).
    - intros n Hn. unfold node_admitted in Hn.
      destruct (ProofSupport.andb_split _ _ Hn) as [_ H1].
      destruct (ProofSupport.andb_split _ _ H1) as [_ H2].
      destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
      destruct (ProofSupport.andb_split _ _ H3) as [Hram _]. exact Hram.
    - exact Hnodes. }
  assert (Hes_ram : ProofSupport.all_of
    (fun e => Nat.leb (edge_effective_ram e) (mg_ram_capacity g)) (mg_edges g) = true).
  { apply (ProofSupport.all_of_mono _ (edge_admitted g)).
    - intros e He. unfold edge_admitted in He.
      destruct (ProofSupport.andb_split _ _ He) as [_ H1].
      destruct (ProofSupport.andb_split _ _ H1) as [_ H2].
      destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
      destruct (ProofSupport.andb_split _ _ H3) as [_ H4].
      destruct (ProofSupport.andb_split _ _ H4) as [_ H5].
      destruct (ProofSupport.andb_split _ _ H5) as [_ H6].
      destruct (ProofSupport.andb_split _ _ H6) as [_ H7].
      destruct (ProofSupport.andb_split _ _ H7) as [_ H8].
      destruct (ProofSupport.andb_split _ _ H8) as [Hram _]. exact Hram.
    - exact Hedges. }
  assert (Hns_store : ProofSupport.all_of
    (fun n => Nat.leb (node_store_bytes n) (mg_store_capacity g)) (mg_nodes g) = true).
  { apply (ProofSupport.all_of_mono _ (node_admitted g)).
    - intros n Hn. unfold node_admitted in Hn.
      destruct (ProofSupport.andb_split _ _ Hn) as [_ H1].
      destruct (ProofSupport.andb_split _ _ H1) as [_ H2].
      destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
      destruct (ProofSupport.andb_split _ _ H3) as [_ Hstore]. exact Hstore.
    - exact Hnodes. }
  assert (Hes_store : ProofSupport.all_of
    (fun e => Nat.leb (edge_store_bytes e) (mg_store_capacity g)) (mg_edges g) = true).
  { apply (ProofSupport.all_of_mono _ (edge_admitted g)).
    - intros e He. unfold edge_admitted in He.
      destruct (ProofSupport.andb_split _ _ He) as [_ H1].
      destruct (ProofSupport.andb_split _ _ H1) as [_ H2].
      destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
      destruct (ProofSupport.andb_split _ _ H3) as [_ H4].
      destruct (ProofSupport.andb_split _ _ H4) as [_ H5].
      destruct (ProofSupport.andb_split _ _ H5) as [_ H6].
      destruct (ProofSupport.andb_split _ _ H6) as [_ H7].
      destruct (ProofSupport.andb_split _ _ H7) as [_ H8].
      destruct (ProofSupport.andb_split _ _ H8) as [_ Hstore]. exact Hstore.
    - exact Hedges. }
  split; apply nat_leb_le_iff.
  - unfold graph_peak_ram, graph_steady_peak_ram, graph_transition_peak_ram.
    exact (ProofSupport.nat_max_upper _ _ (mg_ram_capacity g)
      (fold_max_bound _ node_ram (mg_nodes g) 0 (mg_ram_capacity g) eq_refl Hns_ram)
      (fold_max_bound _ edge_effective_ram (mg_edges g) 0 (mg_ram_capacity g) eq_refl Hes_ram)).
  - unfold graph_peak_store, graph_steady_peak_store, graph_transition_peak_store.
    exact (ProofSupport.nat_max_upper _ _ (mg_store_capacity g)
      (fold_max_bound _ node_store_bytes (mg_nodes g) 0 (mg_store_capacity g) eq_refl Hns_store)
      (fold_max_bound _ edge_store_bytes (mg_edges g) 0 (mg_store_capacity g) eq_refl Hes_store)).
Qed.

Theorem admitted_graph_preserves_standing_services : forall g : ModeGraph,
  graph_admitted g = true ->
  (forall n : SteadyNode, ProofSupport.Member n (mg_nodes g) ->
    StandingIntact (mg_required_standing g) (node_standing n) /\
    node_implicit_authority n = false /\
    node_floor_ok n = true) /\
  (forall e : TransitionEdge, ProofSupport.Member e (mg_edges g) ->
    StandingIntact (mg_required_standing g) (edge_standing e) /\
    edge_cert_valid e = true /\
    edge_explicit_authority e = true).
Proof.
  intros g Hadm.
  unfold graph_admitted in Hadm.
  destruct (ProofSupport.andb_split _ _ Hadm) as [_ Hne].
  destruct (ProofSupport.andb_split _ _ Hne) as [Hnodes Hedges].
  split.
  - intros n Hmem.
    pose proof (ProofSupport.all_of_member _ _ _ n Hnodes Hmem) as Hn.
    unfold node_admitted in Hn.
    destruct (ProofSupport.andb_split _ _ Hn) as [Himp H1].
    destruct (ProofSupport.andb_split _ _ H1) as [Hst H2].
    destruct (ProofSupport.andb_split _ _ H2) as [Hfl _].
    split; [apply standing_intact_iff; exact Hst | ].
    split; [exact (ProofSupport.negb_true _ Himp) | exact Hfl].
  - intros e Hmem.
    pose proof (ProofSupport.all_of_member _ _ _ e Hedges Hmem) as He.
    unfold edge_admitted in He.
    destruct (ProofSupport.andb_split _ _ He) as [Hcert H1].
    destruct (ProofSupport.andb_split _ _ H1) as [Hauth H2].
    destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
    destruct (ProofSupport.andb_split _ _ H3) as [Hst _].
    split; [apply standing_intact_iff; exact Hst | ].
    split; [exact Hcert | exact Hauth].
Qed.

Theorem reachable_node_and_edge_within_graph_peak : forall g : ModeGraph,
  (forall n : SteadyNode, ProofSupport.Member n (mg_nodes g) ->
    node_ram n <= graph_peak_ram g /\ node_store_bytes n <= graph_peak_store g) /\
  (forall e : TransitionEdge, ProofSupport.Member e (mg_edges g) ->
    edge_effective_ram e <= graph_peak_ram g /\ edge_store_bytes e <= graph_peak_store g).
Proof.
  intro g. split.
  - intros n Hmem. split; apply nat_leb_le_iff.
    + exact (ProofSupport.nat_leb_trans _ (graph_steady_peak_ram g) (graph_peak_ram g)
        (fold_max_member _ node_ram (mg_nodes g) 0 n Hmem)
        (ProofSupport.nat_max_left (graph_steady_peak_ram g) (graph_transition_peak_ram g))).
    + exact (ProofSupport.nat_leb_trans _ (graph_steady_peak_store g) (graph_peak_store g)
        (fold_max_member _ node_store_bytes (mg_nodes g) 0 n Hmem)
        (ProofSupport.nat_max_left (graph_steady_peak_store g) (graph_transition_peak_store g))).
  - intros e Hmem. split; apply nat_leb_le_iff.
    + exact (ProofSupport.nat_leb_trans _ (graph_transition_peak_ram g) (graph_peak_ram g)
        (fold_max_member _ edge_effective_ram (mg_edges g) 0 e Hmem)
        (ProofSupport.nat_max_right (graph_steady_peak_ram g) (graph_transition_peak_ram g))).
    + exact (ProofSupport.nat_leb_trans _ (graph_transition_peak_store g) (graph_peak_store g)
        (fold_max_member _ edge_store_bytes (mg_edges g) 0 e Hmem)
        (ProofSupport.nat_max_right (graph_steady_peak_store g) (graph_transition_peak_store g))).
Qed.

Definition node_writing_std : SteadyNode := {|
  node_id := 1;
  node_sel := {| sel_power := PowerBalanced; sel_profile := Writing; sel_rung := RungStandard |};
  node_standing := required_standing_default;
  node_implicit_authority := false;
  node_floor_ok := true;
  node_perm_bytes := 48;
  node_private_bytes := 96;
  node_cp_ws_bytes := 0;
  node_quarantined_bytes := 0;
  node_metadata_bytes := 8;
  node_store_bytes := 48
|}.

Definition node_perf_dev : SteadyNode := {|
  node_id := 2;
  node_sel := {| sel_power := PowerPerformance; sel_profile := Development; sel_rung := RungExpanded |};
  node_standing := required_standing_default;
  node_implicit_authority := false;
  node_floor_ok := true;
  node_perm_bytes := 48;
  node_private_bytes := 128;
  node_cp_ws_bytes := 0;
  node_quarantined_bytes := 0;
  node_metadata_bytes := 12;
  node_store_bytes := 48
|}.

Definition edge_writing_to_perf_dev : TransitionEdge := {|
  edge_src_id := 1;
  edge_dst_id := 2;
  edge_local_only := false;
  edge_power_unchanged := false;
  edge_root_attested := true;
  edge_explicit_authority := true;
  edge_standing := required_standing_default;
  edge_reusable_proved := true;
  edge_overlap_credit := 48;
  edge_perm_bytes := 48;
  edge_private_bytes := 96;
  edge_cp_ws_bytes := 24;
  edge_quarantined_bytes := 16;
  edge_metadata_bytes := 12;
  edge_store_bytes := 64;
  edge_old_last_gap := 2;
  edge_mid_gap := 4;
  edge_new_first_gap := 2;
  edge_continuing_deadline := 8;
  edge_work_cost := 12;
  edge_deadline := 14;
  edge_recovery_reserved := true;
  edge_cert_valid := true
|}.

Definition pos_mode_graph : ModeGraph := {|
  mg_required_standing := required_standing_default;
  mg_nodes := cons witness_SteadyNode (cons node_writing_std (cons node_perf_dev nil));
  mg_edges := cons witness_TransitionEdge (cons edge_writing_to_perf_dev nil);
  mg_ram_capacity := 192;
  mg_store_capacity := 64
|}.

Definition witness_ModeGraph : ModeGraph := pos_mode_graph.

(* =========================================================================
   S4. Reclamation-economics comparison across `FrozenResident`,
       `SemanticHibernation`, and `FixedPoolReuse` (`R-08-046`, `R-11-018a`).
   ========================================================================= *)

Record StrategyMeasurement : Type := {
  sm_strategy : ReclamationStrategy;
  sm_useful_state_bytes : nat;
  sm_perm_bytes : nat;
  sm_steady_private_bytes : nat;
  sm_trans_private_bytes : nat;
  sm_trans_cp_ws_bytes : nat;
  sm_trans_quarantined_bytes : nat;
  sm_metadata_bytes : nat;
  sm_store_bytes : nat;
  sm_reusable_proved : bool;
  sm_overlap_credit : nat;
  sm_endurance_writes_per_switch : nat;
  sm_resume_latency : nat
}.

Definition strategy_steady_ram (m : StrategyMeasurement) : nat :=
  raw_ram_demand (sm_perm_bytes m) (sm_steady_private_bytes m) 0 0 (sm_metadata_bytes m).

Definition strategy_peak_ram (m : StrategyMeasurement) : nat :=
  Nat.max (strategy_steady_ram m)
    (effective_ram_demand (sm_perm_bytes m) (sm_trans_private_bytes m)
       (sm_trans_cp_ws_bytes m) (sm_trans_quarantined_bytes m) (sm_metadata_bytes m)
       (sm_reusable_proved m) (sm_overlap_credit m)).

Definition strategy_measurement_valid (m : StrategyMeasurement) : bool :=
  overlap_credit_valid (sm_reusable_proved m) (sm_overlap_credit m) (sm_trans_private_bytes m).

Definition witness_StrategyMeasurement : StrategyMeasurement := {|
  sm_strategy := FrozenResident;
  sm_useful_state_bytes := 64;
  sm_perm_bytes := 48;
  sm_steady_private_bytes := 128;
  sm_trans_private_bytes := 128;
  sm_trans_cp_ws_bytes := 0;
  sm_trans_quarantined_bytes := 0;
  sm_metadata_bytes := 8;
  sm_store_bytes := 0;
  sm_reusable_proved := false;
  sm_overlap_credit := 0;
  sm_endurance_writes_per_switch := 0;
  sm_resume_latency := 1
|}.

Record StrategyComparison : Type := {
  sc_useful_state_bytes : nat;
  sc_frozen : StrategyMeasurement;
  sc_hibernation : StrategyMeasurement;
  sc_fixed_pool : StrategyMeasurement
}.

Definition comparison_valid (c : StrategyComparison) : bool :=
  andb (strategy_eqb (sm_strategy (sc_frozen c)) FrozenResident)
  (andb (strategy_eqb (sm_strategy (sc_hibernation c)) SemanticHibernation)
  (andb (strategy_eqb (sm_strategy (sc_fixed_pool c)) FixedPoolReuse)
  (andb (Nat.eqb (sm_useful_state_bytes (sc_frozen c)) (sc_useful_state_bytes c))
  (andb (Nat.eqb (sm_useful_state_bytes (sc_hibernation c)) (sc_useful_state_bytes c))
  (andb (Nat.eqb (sm_useful_state_bytes (sc_fixed_pool c)) (sc_useful_state_bytes c))
  (andb (strategy_measurement_valid (sc_frozen c))
  (andb (strategy_measurement_valid (sc_hibernation c))
        (strategy_measurement_valid (sc_fixed_pool c))))))))).

Definition pos_hibernation_meas : StrategyMeasurement := {|
  sm_strategy := SemanticHibernation;
  sm_useful_state_bytes := 64;
  sm_perm_bytes := 48;
  sm_steady_private_bytes := 64;
  sm_trans_private_bytes := 64;
  sm_trans_cp_ws_bytes := 16;
  sm_trans_quarantined_bytes := 16;
  sm_metadata_bytes := 12;
  sm_store_bytes := 48;
  sm_reusable_proved := true;
  sm_overlap_credit := 32;
  sm_endurance_writes_per_switch := 1;
  sm_resume_latency := 6
|}.

Definition pos_fixed_pool_meas : StrategyMeasurement := {|
  sm_strategy := FixedPoolReuse;
  sm_useful_state_bytes := 64;
  sm_perm_bytes := 48;
  sm_steady_private_bytes := 96;
  sm_trans_private_bytes := 96;
  sm_trans_cp_ws_bytes := 0;
  sm_trans_quarantined_bytes := 24;
  sm_metadata_bytes := 10;
  sm_store_bytes := 0;
  sm_reusable_proved := true;
  sm_overlap_credit := 32;
  sm_endurance_writes_per_switch := 0;
  sm_resume_latency := 2
|}.

Definition pos_strategy_comparison : StrategyComparison := {|
  sc_useful_state_bytes := 64;
  sc_frozen := witness_StrategyMeasurement;
  sc_hibernation := pos_hibernation_meas;
  sc_fixed_pool := pos_fixed_pool_meas
|}.

Definition witness_StrategyComparison : StrategyComparison := pos_strategy_comparison.

(*| discharges: R-08-046, R-11-018a |*)
Theorem strategy_comparison_valid_identical_state : forall c : StrategyComparison,
  comparison_valid c = true ->
  sm_strategy (sc_frozen c) = FrozenResident /\
  sm_strategy (sc_hibernation c) = SemanticHibernation /\
  sm_strategy (sc_fixed_pool c) = FixedPoolReuse /\
  sm_useful_state_bytes (sc_frozen c) = sc_useful_state_bytes c /\
  sm_useful_state_bytes (sc_hibernation c) = sc_useful_state_bytes c /\
  sm_useful_state_bytes (sc_fixed_pool c) = sc_useful_state_bytes c.
Proof.
  intros c H. unfold comparison_valid in H.
  destruct (ProofSupport.andb_split _ _ H) as [Hf H1].
  destruct (ProofSupport.andb_split _ _ H1) as [Hh H2].
  destruct (ProofSupport.andb_split _ _ H2) as [Hp H3].
  destruct (ProofSupport.andb_split _ _ H3) as [Huf H4].
  destruct (ProofSupport.andb_split _ _ H4) as [Huh H5].
  destruct (ProofSupport.andb_split _ _ H5) as [Hup _].
  repeat split.
  - destruct (sm_strategy (sc_frozen c)); try discriminate Hf; reflexivity.
  - destruct (sm_strategy (sc_hibernation c)); try discriminate Hh; reflexivity.
  - destruct (sm_strategy (sc_fixed_pool c)); try discriminate Hp; reflexivity.
  - exact (ProofSupport.nat_eqb_true _ _ Huf).
  - exact (ProofSupport.nat_eqb_true _ _ Huh).
  - exact (ProofSupport.nat_eqb_true _ _ Hup).
Qed.

(* =========================================================================
   S5. Repeated-toggling dwell, quarantine high-water, and storage endurance
       bounds (`R-08-046`, `R-11-018`).
   ========================================================================= *)

Record TogglePolicy : Type := {
  tp_min_dwell : nat;
  tp_quarantine_cap : nat;
  tp_endurance_limit : nat;
  tp_cp_store_cap : nat;
  tp_fg_service_floor : nat;
  tp_sweep_rate : nat
}.

Definition witness_TogglePolicy : TogglePolicy := {|
  tp_min_dwell := 2;
  tp_quarantine_cap := 48;
  tp_endurance_limit := 4;
  tp_cp_store_cap := 96;
  tp_fg_service_floor := 2;
  tp_sweep_rate := 16
|}.

Record ToggleSimState : Type := {
  ts_ticks_since_switch : nat;
  ts_quarantined_bytes : nat;
  ts_quarantine_high_water : nat;
  ts_endurance_writes : nat;
  ts_cp_store_used : nat;
  ts_fg_served : nat;
  ts_switches_completed : nat;
  ts_refused_count : nat
}.

Definition witness_ToggleSimState : ToggleSimState := {|
  ts_ticks_since_switch := 2;
  ts_quarantined_bytes := 0;
  ts_quarantine_high_water := 0;
  ts_endurance_writes := 0;
  ts_cp_store_used := 0;
  ts_fg_served := 0;
  ts_switches_completed := 0;
  ts_refused_count := 0
|}.

Inductive ToggleStep : Type :=
| ToggleTick (fg_work : nat)
| ToggleSwitch (retire_bytes cp_bytes writes_needed fg_work : nat).

Definition toggle_state_ok (pol : TogglePolicy) (st : ToggleSimState) : bool :=
  andb (Nat.leb (ts_quarantined_bytes st) (ts_quarantine_high_water st))
  (andb (Nat.leb (ts_quarantine_high_water st) (tp_quarantine_cap pol))
  (andb (Nat.leb (ts_endurance_writes st) (tp_endurance_limit pol))
        (Nat.leb (ts_cp_store_used st) (tp_cp_store_cap pol)))).

Definition toggle_switch_admitted
    (pol : TogglePolicy) (st : ToggleSimState)
    (retire_bytes cp_bytes writes_needed fg_work : nat) : bool :=
  andb (Nat.leb (tp_min_dwell pol) (ts_ticks_since_switch st))
  (andb (Nat.leb (ts_quarantined_bytes st + retire_bytes) (tp_quarantine_cap pol))
  (andb (Nat.leb (ts_endurance_writes st + writes_needed) (tp_endurance_limit pol))
  (andb (Nat.leb (ts_cp_store_used st + cp_bytes) (tp_cp_store_cap pol))
        (Nat.leb (tp_fg_service_floor pol) fg_work)))).

Definition toggle_step_checked
    (pol : TogglePolicy) (st : ToggleSimState) (ev : ToggleStep)
    : ToggleSimState * bool :=
  match ev with
  | ToggleTick fg_work =>
      let q_after := ts_quarantined_bytes st - tp_sweep_rate pol in
      ({| ts_ticks_since_switch := S (ts_ticks_since_switch st);
          ts_quarantined_bytes := q_after;
          ts_quarantine_high_water := ts_quarantine_high_water st;
          ts_endurance_writes := ts_endurance_writes st;
          ts_cp_store_used := ts_cp_store_used st;
          ts_fg_served := ts_fg_served st + fg_work;
          ts_switches_completed := ts_switches_completed st;
          ts_refused_count := ts_refused_count st |}, true)
  | ToggleSwitch retire_bytes cp_bytes writes_needed fg_work =>
      if toggle_switch_admitted pol st retire_bytes cp_bytes writes_needed fg_work
      then let q_new := ts_quarantined_bytes st + retire_bytes in
           ({| ts_ticks_since_switch := 0;
               ts_quarantined_bytes := q_new;
               ts_quarantine_high_water := Nat.max (ts_quarantine_high_water st) q_new;
               ts_endurance_writes := ts_endurance_writes st + writes_needed;
               ts_cp_store_used := ts_cp_store_used st + cp_bytes;
               ts_fg_served := ts_fg_served st + fg_work;
               ts_switches_completed := S (ts_switches_completed st);
               ts_refused_count := ts_refused_count st |}, true)
      else ({| ts_ticks_since_switch := ts_ticks_since_switch st;
               ts_quarantined_bytes := ts_quarantined_bytes st;
               ts_quarantine_high_water := ts_quarantine_high_water st;
               ts_endurance_writes := ts_endurance_writes st;
               ts_cp_store_used := ts_cp_store_used st;
               ts_fg_served := ts_fg_served st;
               ts_switches_completed := ts_switches_completed st;
               ts_refused_count := S (ts_refused_count st) |}, false)
  end.

Definition toggle_step (pol : TogglePolicy) (st : ToggleSimState) (ev : ToggleStep)
    : ToggleSimState :=
  fst (toggle_step_checked pol st ev).

Fixpoint toggle_run (pol : TogglePolicy) (st : ToggleSimState) (evs : list ToggleStep)
    : ToggleSimState :=
  match evs with
  | nil => st
  | cons ev rest => toggle_run pol (toggle_step pol st ev) rest
  end.

(*| discharges: R-08-046, R-11-018 |*)
Theorem toggle_step_preserves_bounds :
  forall (pol : TogglePolicy) (st : ToggleSimState) (ev : ToggleStep),
    toggle_state_ok pol st = true ->
    toggle_state_ok pol (toggle_step pol st ev) = true.
Proof.
  intros pol st ev Hst.
  unfold toggle_state_ok in *.
  destruct (ProofSupport.andb_split _ _ Hst) as [Hqhw H1].
  destruct (ProofSupport.andb_split _ _ H1) as [Hhwcap H2].
  destruct (ProofSupport.andb_split _ _ H2) as [Hend Hcp].
  destruct ev as [fg | retire cp writes fg]; unfold toggle_step, toggle_step_checked; simpl.
  - repeat apply ProofSupport.andb_join; try assumption.
    exact (ProofSupport.nat_leb_trans _ (ts_quarantined_bytes st) (ts_quarantine_high_water st)
      (nat_leb_sub_le (ts_quarantined_bytes st) (tp_sweep_rate pol)) Hqhw).
  - destruct (toggle_switch_admitted pol st retire cp writes fg) eqn:Eadm; simpl.
    + unfold toggle_switch_admitted in Eadm.
      destruct (ProofSupport.andb_split _ _ Eadm) as [_ Ha1].
      destruct (ProofSupport.andb_split _ _ Ha1) as [Hqcap Ha2].
      destruct (ProofSupport.andb_split _ _ Ha2) as [Hecap Ha3].
      destruct (ProofSupport.andb_split _ _ Ha3) as [Hcpcap _].
      repeat apply ProofSupport.andb_join.
      * exact (ProofSupport.nat_max_right (ts_quarantine_high_water st)
          (ts_quarantined_bytes st + retire)).
      * exact (ProofSupport.nat_max_upper (ts_quarantine_high_water st)
          (ts_quarantined_bytes st + retire) (tp_quarantine_cap pol) Hhwcap Hqcap).
      * exact Hecap.
      * exact Hcpcap.
    + repeat apply ProofSupport.andb_join; assumption.
Qed.

Theorem toggle_run_preserves_bounds :
  forall (evs : list ToggleStep) (pol : TogglePolicy) (st : ToggleSimState),
    toggle_state_ok pol st = true ->
    toggle_state_ok pol (toggle_run pol st evs) = true.
Proof.
  intro evs. induction evs as [| ev rest IH]; intros pol st Hst; simpl.
  - exact Hst.
  - apply IH. exact (toggle_step_preserves_bounds pol st ev Hst).
Qed.

(* =========================================================================
   S6. Concrete positive witnesses and refutations (`R-05-165`, `R-05-166`).
   ========================================================================= *)

Example pos_graph_admitted :
  graph_admitted pos_mode_graph = true /\
  graph_steady_peak_ram pos_mode_graph = 188 /\
  graph_transition_peak_ram pos_mode_graph = 148 /\
  graph_peak_ram pos_mode_graph = 188 /\
  graph_peak_store pos_mode_graph = 64 /\
  selection_edge_reachable pos_mode_graph
    {| sel_power := PowerBalanced; sel_profile := Writing; sel_rung := RungStandard |}
    {| sel_power := PowerPerformance; sel_profile := Development; sel_rung := RungExpanded |}
    = true.
Proof. vm_compute; repeat split; reflexivity. Qed.

Example pos_comparison_valid :
  comparison_valid pos_strategy_comparison = true /\
  strategy_steady_ram witness_StrategyMeasurement = 184 /\
  strategy_steady_ram pos_hibernation_meas = 124 /\
  strategy_peak_ram pos_hibernation_meas = 124 /\
  strategy_steady_ram pos_fixed_pool_meas = 154 /\
  strategy_peak_ram pos_fixed_pool_meas = 154.
Proof. vm_compute; repeat split; reflexivity. Qed.

Definition pos_toggle_trace : list ToggleStep :=
  cons (ToggleSwitch 24 16 1 3)
  (cons (ToggleTick 2)
  (cons (ToggleTick 2)
  (cons (ToggleSwitch 24 16 1 3) nil))).

Example pos_toggle_burst_bounded :
  let out := toggle_run witness_TogglePolicy witness_ToggleSimState pos_toggle_trace in
  toggle_state_ok witness_TogglePolicy out = true /\
  ts_switches_completed out = 2 /\
  ts_refused_count out = 0 /\
  ts_quarantine_high_water out = 24 /\
  ts_endurance_writes out = 2.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 1. Cartesian-product pair missing an admitted transition edge. *)
(*| discharges: R-05-165, R-05-166 |*)
Theorem refute_cartesian_edge_without_certificate :
  let sel_everyday := {| sel_power := PowerBalanced; sel_profile := Everyday; sel_rung := RungStandard |} in
  let sel_perf_dev := {| sel_power := PowerPerformance; sel_profile := Development; sel_rung := RungExpanded |} in
  graph_admitted pos_mode_graph = true /\
  selection_edge_reachable pos_mode_graph sel_everyday sel_perf_dev = false.
Proof. vm_compute; split; reflexivity. Qed.

(* 2. Standing-service drop to manufacture a memory saving is refused. *)
Definition dropped_audio_standing : StandingServices := {|
  svc_audio := false;
  svc_radio := true;
  svc_display := true;
  svc_storage := true;
  svc_revocation := true;
  svc_consent := true;
  svc_inference := true
|}.

Definition bad_recipe_dropped_audio : RecipeSpec := {|
  rec_kind := Writing;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := dropped_audio_standing;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := SemanticHibernation;
  rec_useful_state_bytes := 96;
  rec_perm_bytes := 32;
  rec_live_or_frozen_bytes := 96;
  rec_cp_ws_bytes := 24;
  rec_quarantined_bytes := 16;
  rec_metadata_bytes := 8;
  rec_store_cp_bytes := 48;
  rec_store_scratch_bytes := 16;
  rec_reusable_proved := true;
  rec_overlap_credit_bytes := 48;
  rec_ram_budget := 192;
  rec_store_budget := 80
|}.

Theorem refute_standing_service_drop :
  standing_intact required_standing_default dropped_audio_standing = false /\
  recipe_admitted required_standing_default bad_recipe_dropped_audio = false.
Proof. vm_compute; split; reflexivity. Qed.

(* 3. Premature overlap credit before `Reusable` completes is refused. *)
Definition bad_recipe_premature_overlap : RecipeSpec := {|
  rec_kind := ImageEditing;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := SemanticHibernation;
  rec_useful_state_bytes := 128;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 128;
  rec_cp_ws_bytes := 32;
  rec_quarantined_bytes := 24;
  rec_metadata_bytes := 12;
  rec_store_cp_bytes := 64;
  rec_store_scratch_bytes := 24;
  rec_reusable_proved := false;
  rec_overlap_credit_bytes := 64;
  rec_ram_budget := 224;
  rec_store_budget := 96
|}.

Theorem refute_premature_overlap_credit :
  overlap_credit_valid false 64 128 = false /\
  recipe_admitted required_standing_default bad_recipe_premature_overlap = false /\
  recipe_effective_ram bad_recipe_premature_overlap = 244.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 4. Toggle-burst endurance exhaustion, quarantine overflow, and dwell bypass refused. *)
Definition burst_overflow_trace : list ToggleStep :=
  cons (ToggleSwitch 32 16 2 3)
  (cons (ToggleSwitch 32 16 2 3)
  (cons (ToggleTick 2)
  (cons (ToggleTick 2)
  (cons (ToggleSwitch 32 16 2 3)
  (cons (ToggleTick 2)
  (cons (ToggleTick 2)
  (cons (ToggleSwitch 32 16 2 3) nil))))))).

Theorem refute_toggle_burst_overflow :
  let st_q := toggle_step witness_TogglePolicy
                (toggle_step witness_TogglePolicy witness_ToggleSimState
                  (ToggleSwitch 32 16 1 3))
                (ToggleSwitch 32 16 1 3) in
  let out := toggle_run witness_TogglePolicy witness_ToggleSimState burst_overflow_trace in
  toggle_switch_admitted witness_TogglePolicy
    (toggle_step witness_TogglePolicy witness_ToggleSimState (ToggleSwitch 32 16 1 3))
    32 16 1 3 = false /\
  toggle_state_ok witness_TogglePolicy st_q = true /\
  ts_quarantined_bytes st_q <= tp_quarantine_cap witness_TogglePolicy /\
  ts_refused_count out = 2 /\
  ts_endurance_writes out <= tp_endurance_limit witness_TogglePolicy.
Proof. vm_compute; repeat split; try reflexivity; apply nat_leb_le_iff; reflexivity. Qed.

(* 5. Deferred browser enabled without qualified port under R-18-004 is refused. *)
Definition bad_recipe_unqualified_browser : RecipeSpec := {|
  rec_kind := Browsing;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevElastic;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := false;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := FrozenResident;
  rec_useful_state_bytes := 128;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 128;
  rec_cp_ws_bytes := 0;
  rec_quarantined_bytes := 0;
  rec_metadata_bytes := 12;
  rec_store_cp_bytes := 0;
  rec_store_scratch_bytes := 0;
  rec_reusable_proved := false;
  rec_overlap_credit_bytes := 0;
  rec_ram_budget := 256;
  rec_store_budget := 64
|}.

Theorem refute_deferred_browser_unqualified :
  recipe_admitted required_standing_default recipe_browsing_deferred = true /\
  recipe_admitted required_standing_default bad_recipe_unqualified_browser = false.
Proof. vm_compute; split; reflexivity. Qed.

(* 6. Development borrowing composition-mode grants for R-18-004a floor is refused. *)
Definition bad_recipe_dev_floor_borrow : RecipeSpec := {|
  rec_kind := Development;
  rec_enabled := true;
  rec_port_available := true;
  rec_browser_port_qualified := false;
  rec_dev_mode := DevComposition;
  rec_dev_exec_successor_only := true;
  rec_borrows_composition_for_floor := true;
  rec_laptop_floor_ok := true;
  rec_standing := required_standing_default;
  rec_companions_admitted := true;
  rec_implicit_authority := false;
  rec_strategy := FixedPoolReuse;
  rec_useful_state_bytes := 128;
  rec_perm_bytes := 48;
  rec_live_or_frozen_bytes := 128;
  rec_cp_ws_bytes := 16;
  rec_quarantined_bytes := 24;
  rec_metadata_bytes := 12;
  rec_store_cp_bytes := 32;
  rec_store_scratch_bytes := 16;
  rec_reusable_proved := true;
  rec_overlap_credit_bytes := 32;
  rec_ram_budget := 224;
  rec_store_budget := 64
|}.

Theorem refute_dev_composition_borrowing_floor :
  recipe_admitted required_standing_default bad_recipe_dev_floor_borrow = false.
Proof. vm_reflexivity. Qed.

(* 7. Endpoint-safe transition overload (nodes fit, transition edge exceeds RAM). *)
Definition overloaded_graph : ModeGraph := {|
  mg_required_standing := required_standing_default;
  mg_nodes := cons witness_SteadyNode (cons node_writing_std nil);
  mg_edges := cons {|
    edge_src_id := 0;
    edge_dst_id := 1;
    edge_local_only := true;
    edge_power_unchanged := true;
    edge_root_attested := false;
    edge_explicit_authority := true;
    edge_standing := required_standing_default;
    edge_reusable_proved := false;
    edge_overlap_credit := 0;
    edge_perm_bytes := 48;
    edge_private_bytes := 96;
    edge_cp_ws_bytes := 24;
    edge_quarantined_bytes := 16;
    edge_metadata_bytes := 8;
    edge_store_bytes := 48;
    edge_old_last_gap := 2;
    edge_mid_gap := 4;
    edge_new_first_gap := 2;
    edge_continuing_deadline := 8;
    edge_work_cost := 10;
    edge_deadline := 12;
    edge_recovery_reserved := true;
    edge_cert_valid := true
  |} nil;
  mg_ram_capacity := 160;
  mg_store_capacity := 64
|}.

Theorem refute_endpoint_safe_transition_overload :
  ProofSupport.all_of (node_admitted overloaded_graph) (mg_nodes overloaded_graph) = true /\
  graph_admitted overloaded_graph = false.
Proof. vm_compute; split; reflexivity. Qed.
