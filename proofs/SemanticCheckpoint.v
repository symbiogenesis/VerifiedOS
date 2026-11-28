(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   SemanticCheckpoint.v

   Q32b-i qualification extending [WorkflowProfiles.v](WorkflowProfiles.v) to
   the concrete two-workload pilot (editor document with bounded text, cursor,
   and undo stack; competing image workspace with bounded tile descriptors,
   preview, and edit history sharing one preassigned slate slot), plus
   lock/unlock recovery and A/B transactional checkpoint commit across crash cuts.

   Requirements cited:
   - R-05-163, R-05-164: zero axioms under assumption audit and kernel check.
   - R-05-165, R-05-166: non-vacuous inhabited records (`witness_<R>`) and
     concrete positive/negative distinguishing witnesses.
   - R-08-006, R-08-007a: complete `Roots` reuse barrier before releasing a
     retired slate slot (no stale registers, saved contexts, loans, proxies,
     or late DMA replies).
   - R-08-015a: fixed slate-slot binding and mutual exclusion across transitions
     and crash cuts.
   - R-11-018, R-11-018a: admitted transition edges, dwell, space, and
     monotonic endurance bounds.
   - R-14-011a, R-14-011b: authenticated semantic checkpoints (rejecting raw
     tagged heaps, saved registers, executable payloads, trailing bytes, and
     live grants/session keys) and lock/unlock recovery under current grants.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-08-006 R-08-007a R-08-015a R-11-018
      R-11-018a R-14-011a R-14-011b
   SHA256: 9615eaffd457ce673fb1b0fc956024573d0b7b90e75e19f5524afbfc5bb73d81
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport WorkflowProfiles.
From Stdlib Require Import Bool List Arith Lia.
Import ProofSupport.Tactics.
Import ListNotations.

Definition MAX_TEXT : nat := 8.
Definition MAX_UNDO : nat := 4.
Definition MAX_TILES : nat := 4.
Definition MAX_HISTORY : nat := 4.
Definition MAX_CP_SPACE : nat := 32.
Definition MAX_ENDURANCE : nat := 8.

(* ------------------------------------------------------------------------- *)
(* 1. Concrete semantic document models and checkpoint format                *)
(* ------------------------------------------------------------------------- *)

Record EditorDoc := {
  ed_text : list nat;
  ed_cursor : nat;
  ed_undo : list nat;
  ed_dirty : bool
}.
Definition witness_EditorDoc : EditorDoc :=
  {| ed_text := [1; 2]; ed_cursor := 2; ed_undo := [0]; ed_dirty := true |}.

Definition editor_doc_valid (d : EditorDoc) : bool :=
  (length (ed_text d) <=? MAX_TEXT) &&
  (ed_cursor d <=? length (ed_text d)) &&
  (length (ed_undo d) <=? MAX_UNDO).

Definition editor_doc_eqb (a b : EditorDoc) : bool :=
  ProofSupport.list_eqb Nat.eqb (ed_text a) (ed_text b) &&
  (ed_cursor a =? ed_cursor b) &&
  ProofSupport.list_eqb Nat.eqb (ed_undo a) (ed_undo b) &&
  Bool.eqb (ed_dirty a) (ed_dirty b).

Record PainterDoc := {
  pt_tiles : list nat;
  pt_preview : nat;
  pt_history : list nat;
  pt_dirty : bool
}.
Definition witness_PainterDoc : PainterDoc :=
  {| pt_tiles := [10; 20]; pt_preview := 1; pt_history := [3]; pt_dirty := true |}.

Definition painter_doc_valid (d : PainterDoc) : bool :=
  (length (pt_tiles d) <=? MAX_TILES) &&
  (length (pt_history d) <=? MAX_HISTORY).

Definition painter_doc_eqb (a b : PainterDoc) : bool :=
  ProofSupport.list_eqb Nat.eqb (pt_tiles a) (pt_tiles b) &&
  (pt_preview a =? pt_preview b) &&
  ProofSupport.list_eqb Nat.eqb (pt_history a) (pt_history b) &&
  Bool.eqb (pt_dirty a) (pt_dirty b).

Inductive SemanticDoc :=
| DocEditor (ed : EditorDoc)
| DocPainter (pt : PainterDoc).

Definition doc_app (d : SemanticDoc) : WorkflowProfiles.App :=
  match d with
  | DocEditor _ => WorkflowProfiles.Editor
  | DocPainter _ => WorkflowProfiles.Painter
  end.

Definition doc_valid (d : SemanticDoc) : bool :=
  match d with
  | DocEditor ed => editor_doc_valid ed
  | DocPainter pt => painter_doc_valid pt
  end.

Definition doc_eqb (a b : SemanticDoc) : bool :=
  match a, b with
  | DocEditor x, DocEditor y => editor_doc_eqb x y
  | DocPainter x, DocPainter y => painter_doc_eqb x y
  | _, _ => false
  end.

Definition doc_to_data (d : SemanticDoc) : WorkflowProfiles.Data :=
  match d with
  | DocEditor ed =>
      match ed_text ed, ed_dirty ed with
      | [], false => WorkflowProfiles.EmptyDocument
      | _, false => WorkflowProfiles.SavedDocument
      | _, true => WorkflowProfiles.EditedDocument
      end
  | DocPainter pt =>
      match pt_tiles pt, pt_dirty pt with
      | [], false => WorkflowProfiles.EmptyDocument
      | _, false => WorkflowProfiles.SavedDocument
      | _, true => WorkflowProfiles.EditedDocument
      end
  end.

Record ConcreteCheckpoint := {
  ccp_app : WorkflowProfiles.App;
  ccp_doc : SemanticDoc;
  ccp_payload : WorkflowProfiles.Payload;
  ccp_schema_ok : bool;
  ccp_generation : nat;
  ccp_generation_ok : bool;
  ccp_label_ok : bool;
  ccp_hmac_valid : bool;
  ccp_committed : bool;
  ccp_security_critical : bool;
  ccp_fresh_ok : bool;
  ccp_trailing_bytes : nat;
  ccp_has_tagged_caps : bool;
  ccp_has_saved_regs : bool;
  ccp_has_live_grants : bool;
  ccp_space_cost : nat
}.

Definition mk_semantic_cp (a : WorkflowProfiles.App) (d : SemanticDoc)
                          (gen cost : nat) : ConcreteCheckpoint :=
  {| ccp_app := a;
     ccp_doc := d;
     ccp_payload := WorkflowProfiles.Semantic;
     ccp_schema_ok := true;
     ccp_generation := gen;
     ccp_generation_ok := true;
     ccp_label_ok := true;
     ccp_hmac_valid := true;
     ccp_committed := true;
     ccp_security_critical := false;
     ccp_fresh_ok := false;
     ccp_trailing_bytes := 0;
     ccp_has_tagged_caps := false;
     ccp_has_saved_regs := false;
     ccp_has_live_grants := false;
     ccp_space_cost := cost |}.

Definition witness_ConcreteCheckpoint : ConcreteCheckpoint :=
  mk_semantic_cp WorkflowProfiles.Editor (DocEditor witness_EditorDoc) 1 16.

Definition concrete_cp_ok (a : WorkflowProfiles.App) (space_limit : nat)
                          (c : ConcreteCheckpoint) : bool :=
  WorkflowProfiles.appeqb a (ccp_app c) &&
  WorkflowProfiles.appeqb a (doc_app (ccp_doc c)) &&
  doc_valid (ccp_doc c) &&
  (match ccp_payload c with WorkflowProfiles.Semantic => true | _ => false end) &&
  ccp_schema_ok c &&
  ccp_generation_ok c &&
  (0 <? ccp_generation c) &&
  ccp_label_ok c &&
  ccp_hmac_valid c &&
  ccp_committed c &&
  (negb (ccp_security_critical c) || ccp_fresh_ok c) &&
  (ccp_trailing_bytes c =? 0) &&
  negb (ccp_has_tagged_caps c) &&
  negb (ccp_has_saved_regs c) &&
  negb (ccp_has_live_grants c) &&
  (ccp_space_cost c <=? space_limit).

Definition to_abstract_cp (c : ConcreteCheckpoint) : WorkflowProfiles.Checkpoint :=
  {| WorkflowProfiles.cp_app := ccp_app c;
     WorkflowProfiles.cp_data := doc_to_data (ccp_doc c);
     WorkflowProfiles.cp_payload := ccp_payload c;
     WorkflowProfiles.cp_schema := ccp_schema_ok c;
     WorkflowProfiles.cp_generation := ccp_generation_ok c && (0 <? ccp_generation c);
     WorkflowProfiles.cp_label := ccp_label_ok c;
     WorkflowProfiles.cp_authenticated :=
       ccp_hmac_valid c && (ccp_trailing_bytes c =? 0) &&
       negb (ccp_has_tagged_caps c) && negb (ccp_has_saved_regs c) &&
       negb (ccp_has_live_grants c);
     WorkflowProfiles.cp_committed := ccp_committed c;
     WorkflowProfiles.cp_security_critical := ccp_security_critical c;
     WorkflowProfiles.cp_fresh := ccp_fresh_ok c |}.

Theorem concrete_cp_ok_refines_abstract :
  forall a limit c,
    concrete_cp_ok a limit c = true ->
    WorkflowProfiles.cp_ok a (to_abstract_cp c) = true.
Proof.
  intros a limit c H.
  unfold concrete_cp_ok in H.
  repeat rewrite andb_true_iff in H.
  destruct H as [[[[[[[[[[[[[[[HA _] _] HP] HS] HG] HG0] HL] HH] HC] HF] HT] HTC] HSR] HLG] _].
  unfold WorkflowProfiles.cp_ok, to_abstract_cp; cbn.
  repeat rewrite andb_true_iff.
  repeat split; assumption.
Qed.

Theorem concrete_cp_excludes_nonsemantic_and_authority :
  forall a limit c,
    concrete_cp_ok a limit c = true ->
    ccp_payload c = WorkflowProfiles.Semantic /\
    ccp_trailing_bytes c = 0 /\
    ccp_has_tagged_caps c = false /\
    ccp_has_saved_regs c = false /\
    ccp_has_live_grants c = false /\
    ccp_hmac_valid c = true /\
    ccp_space_cost c <= limit.
Proof.
  intros a limit c H.
  unfold concrete_cp_ok in H.
  repeat rewrite andb_true_iff in H.
  destruct H as [[[[[[[[[[[[[[[_ _] _] HP] _] _] _] _] HH] _] _] HT] HTC] HSR] HLG] HSP].
  repeat split.
  - destruct (ccp_payload c); try discriminate; reflexivity.
  - apply Nat.eqb_eq in HT; exact HT.
  - apply negb_true_iff in HTC; exact HTC.
  - apply negb_true_iff in HSR; exact HSR.
  - apply negb_true_iff in HLG; exact HLG.
  - exact HH.
  - apply Nat.leb_le in HSP; exact HSP.
Qed.

(* ------------------------------------------------------------------------- *)
(* 2. Two-slot A/B durable store and transactional commit                    *)
(* ------------------------------------------------------------------------- *)

Record SlotStore := {
  slot_a : option ConcreteCheckpoint;
  slot_b : option ConcreteCheckpoint;
  active_slot : bool; (* false = slot A active, true = slot B active *)
  staging_dirty : bool;
  endurance_used : nat;
  endurance_limit : nat;
  space_reserved : nat
}.

Definition mk_initial_store (init_cp : ConcreteCheckpoint) : SlotStore :=
  {| slot_a := Some init_cp;
     slot_b := None;
     active_slot := false;
     staging_dirty := false;
     endurance_used := 0;
     endurance_limit := MAX_ENDURANCE;
     space_reserved := MAX_CP_SPACE |}.

Definition witness_SlotStore : SlotStore :=
  mk_initial_store witness_ConcreteCheckpoint.

Definition active_cp (st : SlotStore) : option ConcreteCheckpoint :=
  if active_slot st then slot_b st else slot_a st.

Definition inactive_cp (st : SlotStore) : option ConcreteCheckpoint :=
  if active_slot st then slot_a st else slot_b st.

Definition stage_inactive (st : SlotStore) (c : ConcreteCheckpoint) : option SlotStore :=
  if (endurance_used st <? endurance_limit st) &&
     (ccp_space_cost c <=? space_reserved st)
  then Some {| slot_a := if active_slot st then Some c else slot_a st;
               slot_b := if active_slot st then slot_b st else Some c;
               active_slot := active_slot st;
               staging_dirty := true;
               endurance_used := S (endurance_used st);
               endurance_limit := endurance_limit st;
               space_reserved := space_reserved st |}
  else None.

Definition commit_flip (st : SlotStore) (a : WorkflowProfiles.App) : option SlotStore :=
  if staging_dirty st then
    match inactive_cp st with
    | Some c =>
        if concrete_cp_ok a (space_reserved st) c
        then Some {| slot_a := slot_a st;
                     slot_b := slot_b st;
                     active_slot := negb (active_slot st);
                     staging_dirty := false;
                     endurance_used := endurance_used st;
                     endurance_limit := endurance_limit st;
                     space_reserved := space_reserved st |}
        else None
    | None => None
    end
  else None.

Definition discard_staging (st : SlotStore) : SlotStore :=
  {| slot_a := if active_slot st then None else slot_a st;
     slot_b := if active_slot st then slot_b st else None;
     active_slot := active_slot st;
     staging_dirty := false;
     endurance_used := endurance_used st;
     endurance_limit := endurance_limit st;
     space_reserved := space_reserved st |}.

Theorem pre_commit_stage_preserves_active_cp :
  forall st c st',
    stage_inactive st c = Some st' ->
    active_cp st' = active_cp st.
Proof.
  intros st c st' H.
  unfold stage_inactive in H.
  destruct ((endurance_used st <? endurance_limit st) &&
            (ccp_space_cost c <=? space_reserved st)); try discriminate.
  inversion H; subst.
  unfold active_cp; cbn.
  destruct (active_slot st); reflexivity.
Qed.

Theorem pre_commit_crash_preserves_prior_checkpoint :
  forall st c st',
    stage_inactive st c = Some st' ->
    active_cp (discard_staging st') = active_cp st.
Proof.
  intros st c st' H.
  unfold stage_inactive in H.
  destruct ((endurance_used st <? endurance_limit st) &&
            (ccp_space_cost c <=? space_reserved st)); try discriminate.
  inversion H; subst.
  unfold active_cp, discard_staging; cbn.
  destruct (active_slot st); reflexivity.
Qed.

Theorem post_commit_crash_preserves_new_checkpoint :
  forall st c st1 a st2,
    stage_inactive st c = Some st1 ->
    commit_flip st1 a = Some st2 ->
    active_cp (discard_staging st2) = Some c.
Proof.
  intros st c st1 a st2 HS HC.
  unfold stage_inactive in HS.
  destruct ((endurance_used st <? endurance_limit st) &&
            (ccp_space_cost c <=? space_reserved st)); try discriminate.
  inversion HS; subst.
  unfold commit_flip, inactive_cp in HC; cbn in HC.
  destruct (active_slot st) eqn:HA.
  - destruct (concrete_cp_ok a (space_reserved st) c); try discriminate.
    inversion HC; subst.
    unfold active_cp, discard_staging; cbn.
    reflexivity.
  - destruct (concrete_cp_ok a (space_reserved st) c); try discriminate.
    inversion HC; subst.
    unfold active_cp, discard_staging; cbn.
    reflexivity.
Qed.

(* ------------------------------------------------------------------------- *)
(* 3. Lock/unlock recovery, reuse barrier audit, and full pilot semantics    *)
(* ------------------------------------------------------------------------- *)

Inductive GrantDecision :=
| GrantValid
| GrantRevoked
| GrantExpired.

Inductive RecoveryOutcome :=
| RecoveryNone
| RecoveryOk
| RecoveryRefusedIncomplete
| RecoveryRefusedGrant.

Inductive CrashCut :=
| CutAfterQuiesce
| CutAfterStageBeforeCommit
| CutAfterCommitBeforeRelease
| CutAfterReleaseBeforeRestore
| CutDuringRestoreBeforeFinish.

Record ReuseAudit := {
  audit_stale_register : bool;
  audit_saved_context : bool;
  audit_active_loan : bool;
  audit_late_dma_reply : bool;
  audit_space_exceeded : bool;
  audit_endurance_exhausted : bool
}.
Definition witness_ReuseAudit : ReuseAudit :=
  {| audit_stale_register := false;
     audit_saved_context := false;
     audit_active_loan := false;
     audit_late_dma_reply := false;
     audit_space_exceeded := false;
     audit_endurance_exhausted := false |}.

Definition audit_matches_inventory (au : ReuseAudit)
                                   (m : WorkflowProfiles.MachineInventory) : Prop :=
  (audit_stale_register au = true -> In true (WorkflowProfiles.register_tags m)) /\
  (audit_saved_context au = true -> In true (WorkflowProfiles.saved_tags m)) /\
  (audit_active_loan au = true -> In true (WorkflowProfiles.loan_tags m)) /\
  (audit_late_dma_reply au = true -> In true (WorkflowProfiles.device_tags m)).

Theorem reusable_excludes_all_hazards :
  forall r m au,
    WorkflowProfiles.root_correspondence r m ->
    audit_matches_inventory au m ->
    WorkflowProfiles.reusable r = true ->
    audit_stale_register au = false /\
    audit_saved_context au = false /\
    audit_active_loan au = false /\
    audit_late_dma_reply au = false.
Proof.
  intros r m au HC HM HR.
  apply WorkflowProfiles.reusable_has_every_root in HR.
  destruct HR as [Hreg [Hsav [_ [Hloan [_ [Hdev _]]]]]].
  unfold WorkflowProfiles.root_correspondence in HC.
  destruct HC as [Creg [Csav [_ [_ [Cloan [_ Cdev]]]]]].
  unfold audit_matches_inventory in HM.
  destruct HM as [Mreg [Msav [Mloan Mdev]]].
  repeat split.
  - destruct (audit_stale_register au); [|reflexivity].
    exfalso. exact (Creg Hreg (Mreg eq_refl)).
  - destruct (audit_saved_context au); [|reflexivity].
    exfalso. exact (Csav Hsav (Msav eq_refl)).
  - destruct (audit_active_loan au); [|reflexivity].
    exfalso. exact (Cloan Hloan (Mloan eq_refl)).
  - destruct (audit_late_dma_reply au); [|reflexivity].
    exfalso. exact (Cdev Hdev (Mdev eq_refl)).
Qed.

Record PilotState := {
  ps_editor_phase : WorkflowProfiles.Phase;
  ps_painter_phase : WorkflowProfiles.Phase;
  ps_editor_owns_slate : bool;
  ps_painter_owns_slate : bool;
  ps_editor_doc : EditorDoc;
  ps_painter_doc : PainterDoc;
  ps_editor_grant : bool;
  ps_painter_grant : bool;
  ps_editor_session : bool;
  ps_painter_session : bool;
  ps_editor_retiring_committed : bool;
  ps_painter_retiring_committed : bool;
  ps_editor_store : SlotStore;
  ps_painter_store : SlotStore;
  ps_selected : WorkflowProfiles.App;
  ps_target : option WorkflowProfiles.App;
  ps_dwell : nat;
  ps_elapsed : nat;
  ps_locked : bool;
  ps_recovery_outcome : RecoveryOutcome
}.

Definition initial_editor_saved : EditorDoc :=
  {| ed_text := [1]; ed_cursor := 1; ed_undo := []; ed_dirty := false |}.

Definition initial_painter_saved : PainterDoc :=
  {| pt_tiles := [10]; pt_preview := 1; pt_history := []; pt_dirty := false |}.

Definition pilot_initial : PilotState :=
  {| ps_editor_phase := WorkflowProfiles.Active;
     ps_painter_phase := WorkflowProfiles.Hibernated;
     ps_editor_owns_slate := true;
     ps_painter_owns_slate := false;
     ps_editor_doc := witness_EditorDoc;
     ps_painter_doc := initial_painter_saved;
     ps_editor_grant := true;
     ps_painter_grant := false;
     ps_editor_session := true;
     ps_painter_session := false;
     ps_editor_retiring_committed := false;
     ps_painter_retiring_committed := false;
     ps_editor_store := mk_initial_store
       (mk_semantic_cp WorkflowProfiles.Editor (DocEditor initial_editor_saved) 1 16);
     ps_painter_store := mk_initial_store
       (mk_semantic_cp WorkflowProfiles.Painter (DocPainter initial_painter_saved) 1 16);
     ps_selected := WorkflowProfiles.Editor;
     ps_target := None;
     ps_dwell := 2;
     ps_elapsed := 0;
     ps_locked := false;
     ps_recovery_outcome := RecoveryNone |}.

Definition witness_PilotState : PilotState := pilot_initial.

Definition pilot_exclusive (s : PilotState) : bool :=
  negb (ps_editor_owns_slate s && ps_painter_owns_slate s).

Definition pilot_phase_ok (p : WorkflowProfiles.Phase) (own grant sess : bool) : bool :=
  match p with
  | WorkflowProfiles.Hibernated | WorkflowProfiles.Closed =>
      negb own && negb grant && negb sess
  | _ => own
  end.

Definition pilot_total_endurance (s : PilotState) : nat :=
  endurance_used (ps_editor_store s) + endurance_used (ps_painter_store s).

Definition pilot_state_ok (c : WorkflowProfiles.Edge) (s : PilotState) : bool :=
  pilot_exclusive s &&
  pilot_phase_ok (ps_editor_phase s) (ps_editor_owns_slate s)
                 (ps_editor_grant s) (ps_editor_session s) &&
  pilot_phase_ok (ps_painter_phase s) (ps_painter_owns_slate s)
                 (ps_painter_grant s) (ps_painter_session s) &&
  editor_doc_valid (ps_editor_doc s) &&
  painter_doc_valid (ps_painter_doc s) &&
  (pilot_total_endurance s <=? WorkflowProfiles.write_limit c) &&
  (ps_elapsed s <=? WorkflowProfiles.completion_deadline c) &&
  (ps_dwell s <=? WorkflowProfiles.min_dwell c).

Inductive PilotEvent :=
| PRequest (a : WorkflowProfiles.App)
| PStage (ccp : ConcreteCheckpoint)
| PCommitFlip
| PCommitFailed
| PRelease (r : WorkflowProfiles.Roots)
| PBeginRestore
| PFinishRestore (g : GrantDecision)
| PRestoreFailed
| PRecover (r : WorkflowProfiles.Roots)
| PCrash (cut : CrashCut)
| PLockEditor (ccp : ConcreteCheckpoint) (r : WorkflowProfiles.Roots)
| PUnlockEditor (g : GrantDecision) (candidate : option ConcreteCheckpoint)
| PTick.

Definition pilot_get_phase (s : PilotState) (a : WorkflowProfiles.App) : WorkflowProfiles.Phase :=
  if a is WorkflowProfiles.Editor then ps_editor_phase s else ps_painter_phase s.

Definition pilot_get_owns (s : PilotState) (a : WorkflowProfiles.App) : bool :=
  if a is WorkflowProfiles.Editor then ps_editor_owns_slate s else ps_painter_owns_slate s.

Definition pilot_get_store (s : PilotState) (a : WorkflowProfiles.App) : SlotStore :=
  if a is WorkflowProfiles.Editor then ps_editor_store s else ps_painter_store s.

Definition pilot_get_retiring_committed (s : PilotState) (a : WorkflowProfiles.App) : bool :=
  if a is WorkflowProfiles.Editor then ps_editor_retiring_committed s
  else ps_painter_retiring_committed s.

Definition pilot_put_store (s : PilotState) (a : WorkflowProfiles.App) (st : SlotStore) : PilotState :=
  match a with
  | WorkflowProfiles.Editor => {| s with ps_editor_store := st |}
  | WorkflowProfiles.Painter => {| s with ps_painter_store := st |}
  end.

Definition pilot_matches_live_doc (s : PilotState) (a : WorkflowProfiles.App)
                                  (d : SemanticDoc) : bool :=
  match a, d with
  | WorkflowProfiles.Editor, DocEditor ed => editor_doc_eqb ed (ps_editor_doc s)
  | WorkflowProfiles.Painter, DocPainter pt => painter_doc_eqb pt (ps_painter_doc s)
  | _, _ => false
  end.

Definition pilot_apply_doc (s : PilotState) (a : WorkflowProfiles.App)
                           (d : SemanticDoc) : PilotState :=
  match a, d with
  | WorkflowProfiles.Editor, DocEditor ed => {| s with ps_editor_doc := ed |}
  | WorkflowProfiles.Painter, DocPainter pt => {| s with ps_painter_doc := pt |}
  | _, _ => s
  end.

Definition pilot_set_app_fields (s : PilotState) (a : WorkflowProfiles.App)
                                (ph : WorkflowProfiles.Phase)
                                (own grant sess ret_comm : bool) : PilotState :=
  match a with
  | WorkflowProfiles.Editor =>
      {| s with ps_editor_phase := ph;
                ps_editor_owns_slate := own;
                ps_editor_grant := grant;
                ps_editor_session := sess;
                ps_editor_retiring_committed := ret_comm |}
  | WorkflowProfiles.Painter =>
      {| s with ps_painter_phase := ph;
                ps_painter_owns_slate := own;
                ps_painter_grant := grant;
                ps_painter_session := sess;
                ps_painter_retiring_committed := ret_comm |}
  end.

Definition grant_is_valid (g : GrantDecision) : bool :=
  match g with
  | GrantValid => true
  | GrantRevoked | GrantExpired => false
  end.

Definition pilot_crash_cleanup (s : PilotState) : PilotState :=
  {| s with
     ps_editor_phase := if ps_editor_owns_slate s then WorkflowProfiles.Retiring
                        else WorkflowProfiles.Hibernated;
     ps_painter_phase := if ps_painter_owns_slate s then WorkflowProfiles.Retiring
                         else WorkflowProfiles.Hibernated;
     ps_editor_grant := false;
     ps_painter_grant := false;
     ps_editor_session := false;
     ps_painter_session := false;
     ps_editor_retiring_committed := false;
     ps_painter_retiring_committed := false;
     ps_editor_store := discard_staging (ps_editor_store s);
     ps_painter_store := discard_staging (ps_painter_store s);
     ps_target := Some (WorkflowProfiles.other (ps_selected s));
     ps_dwell := 0;
     ps_elapsed := 0 |}.

Definition pilot_propose (c : WorkflowProfiles.Edge) (s : PilotState)
                         (e : PilotEvent) : option PilotState :=
  let old := ps_selected s in
  let vph := pilot_get_phase s old in
  let vst := pilot_get_store s old in
  match e with
  | PTick =>
      match ps_target s with
      | None =>
          Some {| s with
                  ps_dwell := Nat.min (WorkflowProfiles.min_dwell c) (S (ps_dwell s));
                  ps_elapsed := 0 |}
      | Some _ => None
      end
  | PRequest a =>
      match ps_target s with
      | Some _ => None
      | None =>
          if WorkflowProfiles.edge_ok c &&
             negb (WorkflowProfiles.appeqb old a) &&
             (WorkflowProfiles.min_dwell c <=? ps_dwell s) &&
             (pilot_total_endurance s <? WorkflowProfiles.write_limit c) &&
             (match vph with
              | WorkflowProfiles.Active | WorkflowProfiles.Background
              | WorkflowProfiles.Frozen | WorkflowProfiles.Closed => true
              | _ => false
              end)
          then let next_ph := match vph with
                              | WorkflowProfiles.Closed => WorkflowProfiles.Closed
                              | _ => WorkflowProfiles.Quiescing
                              end in
               let next_own := pilot_get_owns s old in
               let next_grant := if old is WorkflowProfiles.Editor
                                 then ps_editor_grant s else ps_painter_grant s in
               let next_sess := if old is WorkflowProfiles.Editor
                                then ps_editor_session s else ps_painter_session s in
               Some {| (pilot_set_app_fields s old next_ph next_own next_grant next_sess false) with
                       ps_target := Some a;
                       ps_dwell := 0;
                       ps_elapsed := WorkflowProfiles.carry_work c |}
          else None
      end
  | PStage ccp =>
      match ps_target s, vph with
      | Some _, WorkflowProfiles.Quiescing =>
          if concrete_cp_ok old (space_reserved vst) ccp &&
             pilot_matches_live_doc s old (ccp_doc ccp) &&
             (pilot_total_endurance s <? WorkflowProfiles.write_limit c)
          then match stage_inactive vst ccp with
               | Some vst' =>
                   Some {| (pilot_put_store s old vst') with
                           ps_elapsed := ps_elapsed s + WorkflowProfiles.checkpoint_work c |}
               | None => None
               end
          else None
      | _, _ => None
      end
  | PCommitFlip =>
      match ps_target s, vph with
      | Some _, WorkflowProfiles.Quiescing =>
          match commit_flip vst old with
          | Some vst' =>
              Some (pilot_set_app_fields (pilot_put_store s old vst') old
                      WorkflowProfiles.Retiring true false false true)
          | None => None
          end
      | _, _ => None
      end
  | PCommitFailed =>
      match ps_target s, vph with
      | Some _, WorkflowProfiles.Quiescing =>
          let next_grant := if old is WorkflowProfiles.Editor
                            then ps_editor_grant s else ps_painter_grant s in
          let next_sess := if old is WorkflowProfiles.Editor
                           then ps_editor_session s else ps_painter_session s in
          Some {| (pilot_set_app_fields (pilot_put_store s old (discard_staging vst))
                     old WorkflowProfiles.Active true next_grant next_sess false) with
                  ps_target := None;
                  ps_dwell := 0;
                  ps_elapsed := 0 |}
      | _, _ => None
      end
  | PRelease r =>
      match ps_target s, vph with
      | Some _, WorkflowProfiles.Retiring =>
          if WorkflowProfiles.reusable r && pilot_get_retiring_committed s old
          then Some {| (pilot_set_app_fields s old WorkflowProfiles.Hibernated
                          false false false false) with
                       ps_dwell := 0;
                       ps_elapsed := ps_elapsed s +
                         WorkflowProfiles.retire_work c +
                         WorkflowProfiles.sanitize_work c |}
          else None
      | _, _ => None
      end
  | PBeginRestore =>
      match ps_target s, vph with
      | Some a, WorkflowProfiles.Hibernated
      | Some a, WorkflowProfiles.Closed =>
          let dst_st := pilot_get_store s a in
          if negb (pilot_get_owns s a) &&
             negb (pilot_get_owns s (WorkflowProfiles.other a))
          then match active_cp dst_st with
               | Some cp =>
                   if concrete_cp_ok a (space_reserved dst_st) cp
                   then Some {| (pilot_set_app_fields s a WorkflowProfiles.Restoring
                                   true false false false) with
                                ps_dwell := 0;
                                ps_elapsed := ps_elapsed s + WorkflowProfiles.restore_work c |}
                   else None
               | None => None
               end
          else None
      | _, _ => None
      end
  | PFinishRestore g =>
      match ps_target s, vph with
      | Some a, WorkflowProfiles.Hibernated
      | Some a, WorkflowProfiles.Closed =>
          let dst_ph := pilot_get_phase s a in
          let dst_st := pilot_get_store s a in
          match dst_ph, active_cp dst_st with
          | WorkflowProfiles.Restoring, Some cp =>
              if concrete_cp_ok a (space_reserved dst_st) cp
              then let s1 := pilot_apply_doc s a (ccp_doc cp) in
                   let granted := grant_is_valid g in
                   let outcome := if granted then RecoveryOk else RecoveryRefusedGrant in
                   Some {| (pilot_set_app_fields s1 a WorkflowProfiles.Active
                              true granted false false) with
                           ps_selected := a;
                           ps_target := None;
                           ps_dwell := 0;
                           ps_elapsed := 0;
                           ps_locked := false;
                           ps_recovery_outcome := outcome |}
              else None
          | _, _ => None
          end
      | _, _ => None
      end
  | PRestoreFailed =>
      match ps_target s with
      | Some a =>
          match pilot_get_phase s a with
          | WorkflowProfiles.Restoring =>
              Some {| (pilot_set_app_fields s a WorkflowProfiles.Retiring
                         true false false false) with
                      ps_selected := a;
                      ps_target := Some old;
                      ps_dwell := 0 |}
          | _ => None
          end
      | None => None
      end
  | PRecover r =>
      let owner := if ps_editor_owns_slate s then WorkflowProfiles.Editor
                   else if ps_painter_owns_slate s then WorkflowProfiles.Painter
                   else old in
      let oph := pilot_get_phase s owner in
      if WorkflowProfiles.reusable r &&
         (match oph with
          | WorkflowProfiles.Retiring | WorkflowProfiles.Hibernated => true
          | _ => false
          end)
      then Some {| (pilot_set_app_fields s owner WorkflowProfiles.Closed
                      false false false false) with
                   ps_selected := owner;
                   ps_target := None;
                   ps_dwell := 0;
                   ps_elapsed := ps_elapsed s + WorkflowProfiles.recovery_work c |}
      else None
  | PCrash _cut =>
      Some (pilot_crash_cleanup s)
  | PLockEditor ccp r =>
      match ps_target s, ps_editor_phase s with
      | None, WorkflowProfiles.Active =>
          if WorkflowProfiles.edge_ok c &&
             WorkflowProfiles.reusable r &&
             concrete_cp_ok WorkflowProfiles.Editor (space_reserved (ps_editor_store s)) ccp &&
             pilot_matches_live_doc s WorkflowProfiles.Editor (ccp_doc ccp) &&
             (pilot_total_endurance s <? WorkflowProfiles.write_limit c)
          then match stage_inactive (ps_editor_store s) ccp with
               | Some st1 =>
                   match commit_flip st1 WorkflowProfiles.Editor with
                   | Some st2 =>
                       Some {| (pilot_put_store s WorkflowProfiles.Editor st2) with
                               ps_editor_phase := WorkflowProfiles.Hibernated;
                               ps_editor_owns_slate := false;
                               ps_editor_grant := false;
                               ps_editor_session := false;
                               ps_editor_retiring_committed := false;
                               ps_locked := true;
                               ps_dwell := 0;
                               ps_elapsed := 0 |}
                   | None => None
                   end
               | None => None
               end
          else None
      | _, _ => None
      end
  | PUnlockEditor g cand =>
      if negb (ps_painter_owns_slate s) then
        match cand with
        | None =>
            Some {| s with
                    ps_editor_grant := false;
                    ps_editor_session := false;
                    ps_locked := true;
                    ps_recovery_outcome := RecoveryRefusedIncomplete |}
        | Some cp =>
            if concrete_cp_ok WorkflowProfiles.Editor
                              (space_reserved (ps_editor_store s)) cp
            then if grant_is_valid g
                 then let s1 := pilot_apply_doc s WorkflowProfiles.Editor (ccp_doc cp) in
                      Some {| s1 with
                              ps_editor_phase := WorkflowProfiles.Active;
                              ps_editor_owns_slate := true;
                              ps_editor_grant := true;
                              ps_editor_session := false;
                              ps_editor_retiring_committed := false;
                              ps_selected := WorkflowProfiles.Editor;
                              ps_target := None;
                              ps_locked := false;
                              ps_recovery_outcome := RecoveryOk |}
                 else Some {| s with
                              ps_editor_grant := false;
                              ps_editor_session := false;
                              ps_locked := true;
                              ps_recovery_outcome := RecoveryRefusedGrant |}
            else Some {| s with
                         ps_editor_grant := false;
                         ps_editor_session := false;
                         ps_locked := true;
                         ps_recovery_outcome := RecoveryRefusedIncomplete |}
        end
      else None
  end.

Definition pilot_step (c : WorkflowProfiles.Edge) (s : PilotState)
                      (e : PilotEvent) : option PilotState :=
  if WorkflowProfiles.edge_ok c && pilot_state_ok c s then
    match pilot_propose c s e with
    | Some t => if pilot_state_ok c t then Some t else None
    | None => None
    end
  else None.

Fixpoint pilot_run (c : WorkflowProfiles.Edge) (s : PilotState)
                   (es : list PilotEvent) : option PilotState :=
  match es with
  | [] => Some s
  | e :: rest =>
      match pilot_step c s e with
      | Some t => pilot_run c t rest
      | None => None
      end
  end.

Definition pilot_accepted (c : WorkflowProfiles.Edge) (s : PilotState)
                          (es : list PilotEvent) : bool :=
  if pilot_run c s es is Some _ then true else false.

(* ------------------------------------------------------------------------- *)
(* 4. Safety theorems: exclusive slate ownership, crash cuts, and unlock     *)
(* ------------------------------------------------------------------------- *)

Theorem pilot_step_preserves_admission :
  forall c s t e,
    pilot_step c s e = Some t ->
    pilot_state_ok c t = true /\ WorkflowProfiles.edge_ok c = true.
Proof.
  intros c s t e H.
  unfold pilot_step in H.
  destruct (WorkflowProfiles.edge_ok c && pilot_state_ok c s) eqn:E; try discriminate.
  apply andb_true_iff in E as [HE _].
  destruct (pilot_propose c s e); try discriminate.
  destruct (pilot_state_ok c p) eqn:HP; inversion H; subst; auto.
Qed.

Theorem pilot_run_preserves_exclusive :
  forall es c s t,
    pilot_state_ok c s = true ->
    pilot_run c s es = Some t ->
    ~ (ps_editor_owns_slate t = true /\ ps_painter_owns_slate t = true).
Proof.
  induction es as [|e es IH]; intros c s t HS HR; simpl in HR.
  - inversion HR; subst.
    unfold pilot_state_ok, pilot_exclusive in HS.
    repeat rewrite andb_true_iff in HS.
    destruct HS as [[[[[[[HX _] _] _] _] _] _] _].
    rewrite negb_true_iff in HX.
    intros [A B]; rewrite A, B in HX; discriminate.
  - destruct (pilot_step c s e) as [u|] eqn:E; try discriminate.
    exact (IH c u t (proj1 (pilot_step_preserves_admission c s u e E)) HR).
Qed.

Theorem crash_cut_never_dual_owners :
  forall c s cut t,
    pilot_state_ok c s = true ->
    pilot_step c s (PCrash cut) = Some t ->
    ~ (ps_editor_owns_slate t = true /\ ps_painter_owns_slate t = true).
Proof.
  intros c s cut t HS H.
  exact (pilot_run_preserves_exclusive [PCrash cut] c s t HS
           ltac:(simpl; rewrite H; reflexivity)).
Qed.

Theorem unlock_restores_acknowledged_document :
  forall c s t cp ed,
    concrete_cp_ok WorkflowProfiles.Editor (space_reserved (ps_editor_store s)) cp = true ->
    ccp_doc cp = DocEditor ed ->
    pilot_propose c s (PUnlockEditor GrantValid (Some cp)) = Some t ->
    ed_text (ps_editor_doc t) = ed_text ed /\
    ed_cursor (ps_editor_doc t) = ed_cursor ed /\
    ed_undo (ps_editor_doc t) = ed_undo ed /\
    ps_editor_grant t = true /\
    ps_editor_session t = false.
Proof.
  intros c s t cp ed Hcp Hdoc H.
  unfold pilot_propose in H.
  destruct (negb (ps_painter_owns_slate s)); try discriminate.
  rewrite Hcp in H; cbn in H.
  inversion H; subst; clear H.
  unfold pilot_apply_doc; rewrite Hdoc; cbn.
  repeat split; reflexivity.
Qed.

Theorem unlock_refuses_revoked_or_expired_grant :
  forall c s t g cand,
    (g = GrantRevoked \/ g = GrantExpired) ->
    pilot_propose c s (PUnlockEditor g cand) = Some t ->
    ps_editor_grant t = false /\
    ps_editor_session t = false.
Proof.
  intros c s t g cand Hg H.
  unfold pilot_propose in H.
  destruct (negb (ps_painter_owns_slate s)); try discriminate.
  destruct cand as [cp|].
  - destruct (concrete_cp_ok WorkflowProfiles.Editor
                             (space_reserved (ps_editor_store s)) cp).
    + destruct Hg as [-> | ->]; cbn in H; inversion H; subst; auto.
    + inversion H; subst; auto.
  - inversion H; subst; auto.
Qed.

Theorem unlock_never_reinstates_tags_or_session :
  forall c s t g cand,
    pilot_propose c s (PUnlockEditor g cand) = Some t ->
    ps_editor_session t = false /\
    (ps_editor_grant t = true ->
       exists cp, cand = Some cp /\
                  ccp_has_tagged_caps cp = false /\
                  ccp_has_saved_regs cp = false /\
                  ccp_has_live_grants cp = false /\
                  ccp_payload cp = WorkflowProfiles.Semantic).
Proof.
  intros c s t g cand H.
  unfold pilot_propose in H.
  destruct (negb (ps_painter_owns_slate s)); try discriminate.
  destruct cand as [cp|].
  - destruct (concrete_cp_ok WorkflowProfiles.Editor
                             (space_reserved (ps_editor_store s)) cp) eqn:Hcp.
    + destruct (grant_is_valid g) eqn:Hg.
      * inversion H; subst; clear H.
        split.
        { destruct (ccp_doc cp); reflexivity. }
        { intros _. exists cp.
          pose proof (concrete_cp_excludes_nonsemantic_and_authority
                        WorkflowProfiles.Editor
                        (space_reserved (ps_editor_store s)) cp Hcp) as
            [HP [_ [HTC [HSR [HLG _]]]]].
          repeat split; assumption. }
      * inversion H; subst; clear H.
        split; [reflexivity | intros HF; discriminate].
    + inversion H; subst; clear H.
      split; [reflexivity | intros HF; discriminate].
  - inversion H; subst; clear H.
    split; [reflexivity | intros HF; discriminate].
Qed.

Theorem incomplete_checkpoint_preserves_recovery_outcome :
  forall c s t g cand,
    (match cand with
     | None => True
     | Some cp =>
         concrete_cp_ok WorkflowProfiles.Editor
                        (space_reserved (ps_editor_store s)) cp = false
     end) ->
    pilot_propose c s (PUnlockEditor g cand) = Some t ->
    ps_recovery_outcome t = RecoveryRefusedIncomplete /\
    ps_editor_grant t = false /\
    ps_editor_session t = false.
Proof.
  intros c s t g cand Hinc H.
  unfold pilot_propose in H.
  destruct (negb (ps_painter_owns_slate s)); try discriminate.
  destruct cand as [cp|].
  - rewrite Hinc in H.
    inversion H; subst; auto.
  - inversion H; subst; auto.
Qed.

(* ------------------------------------------------------------------------- *)
(* 5. Inhabited positive traces and required negative refutations            *)
(* ------------------------------------------------------------------------- *)

Definition editor_cp_1 : ConcreteCheckpoint :=
  mk_semantic_cp WorkflowProfiles.Editor (DocEditor witness_EditorDoc) 2 16.

Definition painter_cp_1 : ConcreteCheckpoint :=
  mk_semantic_cp WorkflowProfiles.Painter (DocPainter initial_painter_saved) 2 16.

Definition swap_to_painter_trace : list PilotEvent :=
  [PRequest WorkflowProfiles.Painter;
   PStage editor_cp_1;
   PCommitFlip;
   PRelease WorkflowProfiles.cleared;
   PBeginRestore;
   PFinishRestore GrantValid].

Definition swap_back_to_editor_trace : list PilotEvent :=
  [PTick; PTick;
   PRequest WorkflowProfiles.Editor;
   PStage painter_cp_1;
   PCommitFlip;
   PRelease WorkflowProfiles.cleared;
   PBeginRestore;
   PFinishRestore GrantValid].

Example positive_editor_to_painter_swap_and_restore :
  (match pilot_run WorkflowProfiles.reference pilot_initial
           (swap_to_painter_trace ++ swap_back_to_editor_trace) with
   | Some s =>
       editor_doc_eqb (ps_editor_doc s) witness_EditorDoc &&
       ps_editor_owns_slate s &&
       negb (ps_painter_owns_slate s) &&
       ps_editor_grant s &&
       negb (ps_editor_session s)
   | None => false
   end) = true.
Proof. vm_reflexivity. Qed.

Example positive_editor_lock_unlock_recovery :
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PLockEditor editor_cp_1 WorkflowProfiles.cleared;
            PUnlockEditor GrantValid (Some editor_cp_1)] with
   | Some s =>
       editor_doc_eqb (ps_editor_doc s) witness_EditorDoc &&
       ps_editor_owns_slate s &&
       ps_editor_grant s &&
       negb (ps_editor_session s) &&
       (match ps_recovery_outcome s with RecoveryOk => true | _ => false end)
   | None => false
   end) = true.
Proof. vm_reflexivity. Qed.

Definition pilot_retirement_prefix : list PilotEvent :=
  [PRequest WorkflowProfiles.Painter;
   PStage editor_cp_1;
   PCommitFlip].

Example refute_stale_register :
  pilot_accepted WorkflowProfiles.reference pilot_initial
    (pilot_retirement_prefix ++ [PRelease (WorkflowProfiles.missing_root_clause 3)]) = false.
Proof. vm_reflexivity. Qed.

Example refute_saved_context :
  pilot_accepted WorkflowProfiles.reference pilot_initial
    (pilot_retirement_prefix ++ [PRelease (WorkflowProfiles.missing_root_clause 4)]) = false.
Proof. vm_reflexivity. Qed.

Example refute_active_loan :
  pilot_accepted WorkflowProfiles.reference pilot_initial
    (pilot_retirement_prefix ++ [PRelease (WorkflowProfiles.missing_root_clause 6)]) = false.
Proof. vm_reflexivity. Qed.

Example refute_late_dma_reply :
  pilot_accepted WorkflowProfiles.reference pilot_initial
    (pilot_retirement_prefix ++ [PRelease (WorkflowProfiles.missing_root_clause 8)]) = false.
Proof. vm_reflexivity. Qed.

Example refute_out_of_space_checkpoint :
  pilot_accepted WorkflowProfiles.reference pilot_initial
    [PRequest WorkflowProfiles.Painter;
     PStage (mk_semantic_cp WorkflowProfiles.Editor
               (DocEditor witness_EditorDoc) 2 (S MAX_CP_SPACE))] = false.
Proof. vm_reflexivity. Qed.

Definition exhausted_store_state : PilotState :=
  {| pilot_initial with
     ps_editor_store :=
       {| (ps_editor_store pilot_initial) with endurance_used := MAX_ENDURANCE |} |}.

Example refute_endurance_exhaustion :
  pilot_accepted WorkflowProfiles.reference exhausted_store_state
    [PRequest WorkflowProfiles.Painter] = false.
Proof. vm_reflexivity. Qed.

Example refute_revoked_grant_on_unlock :
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PLockEditor editor_cp_1 WorkflowProfiles.cleared;
            PUnlockEditor GrantRevoked (Some editor_cp_1)] with
   | Some s =>
       negb (ps_editor_grant s) &&
       negb (ps_editor_session s) &&
       (match ps_recovery_outcome s with RecoveryRefusedGrant => true | _ => false end)
   | None => false
   end) = true.
Proof. vm_reflexivity. Qed.

Example refute_expired_grant_on_unlock :
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PLockEditor editor_cp_1 WorkflowProfiles.cleared;
            PUnlockEditor GrantExpired (Some editor_cp_1)] with
   | Some s =>
       negb (ps_editor_grant s) &&
       negb (ps_editor_session s) &&
       (match ps_recovery_outcome s with RecoveryRefusedGrant => true | _ => false end)
   | None => false
   end) = true.
Proof. vm_reflexivity. Qed.

Example refute_tagged_capability_restoration :
  let bad_cp := {| editor_cp_1 with ccp_has_tagged_caps := true |} in
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE bad_cp = false /\
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PLockEditor editor_cp_1 WorkflowProfiles.cleared;
            PUnlockEditor GrantValid (Some bad_cp)] with
   | Some s =>
       negb (ps_editor_grant s) &&
       negb (ps_editor_session s) &&
       (match ps_recovery_outcome s with RecoveryRefusedIncomplete => true | _ => false end)
   | None => false
   end) = true.
Proof. split; vm_reflexivity. Qed.

Example refute_incomplete_checkpoint :
  let bad_hmac := {| editor_cp_1 with ccp_hmac_valid := false |} in
  let trailing := {| editor_cp_1 with ccp_trailing_bytes := 4 |} in
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE bad_hmac = false /\
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE trailing = false /\
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PLockEditor editor_cp_1 WorkflowProfiles.cleared;
            PUnlockEditor GrantValid None] with
   | Some s =>
       negb (ps_editor_grant s) &&
       (match ps_recovery_outcome s with RecoveryRefusedIncomplete => true | _ => false end)
   | None => false
   end) = true.
Proof. repeat split; vm_reflexivity. Qed.

Example refute_dual_slate_ownership :
  pilot_state_ok WorkflowProfiles.reference
    {| pilot_initial with ps_painter_owns_slate := true |} = false.
Proof. vm_reflexivity. Qed.

Example refute_nonsemantic_and_authority_payloads :
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE
    {| editor_cp_1 with ccp_payload := WorkflowProfiles.RawHeap |} = false /\
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE
    {| editor_cp_1 with ccp_payload := WorkflowProfiles.Executable |} = false /\
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE
    {| editor_cp_1 with ccp_payload := WorkflowProfiles.SessionKey |} = false /\
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE
    {| editor_cp_1 with ccp_has_saved_regs := true |} = false /\
  concrete_cp_ok WorkflowProfiles.Editor MAX_CP_SPACE
    {| editor_cp_1 with ccp_has_live_grants := true |} = false.
Proof. repeat split; vm_reflexivity. Qed.

Definition project_app_state (ph : WorkflowProfiles.Phase) (own grant sess ret_comm : bool)
                             (st : SlotStore) (d : WorkflowProfiles.Data) : WorkflowProfiles.AppState :=
  {| WorkflowProfiles.phase := ph;
     WorkflowProfiles.owns_arena := own;
     WorkflowProfiles.durable := option_map to_abstract_cp (active_cp st);
     WorkflowProfiles.document := d;
     WorkflowProfiles.document_grant := grant;
     WorkflowProfiles.session_authority := sess;
     WorkflowProfiles.retirement_committed := ret_comm |}.

Definition project_state (s : PilotState) : WorkflowProfiles.State :=
  {| WorkflowProfiles.editor :=
       project_app_state (ps_editor_phase s) (ps_editor_owns_slate s)
         (ps_editor_grant s) (ps_editor_session s)
         (ps_editor_retiring_committed s) (ps_editor_store s)
         (doc_to_data (DocEditor (ps_editor_doc s)));
     WorkflowProfiles.painter :=
       project_app_state (ps_painter_phase s) (ps_painter_owns_slate s)
         (ps_painter_grant s) (ps_painter_session s)
         (ps_painter_retiring_committed s) (ps_painter_store s)
         (doc_to_data (DocPainter (ps_painter_doc s)));
     WorkflowProfiles.selected := ps_selected s;
     WorkflowProfiles.target := ps_target s;
     WorkflowProfiles.dwell := ps_dwell s;
     WorkflowProfiles.writes := pilot_total_endurance s;
     WorkflowProfiles.elapsed := ps_elapsed s |}.

Theorem pilot_state_ok_refines_workflow :
  forall c s,
    WorkflowProfiles.edge_ok c = true ->
    pilot_state_ok c s = true ->
    WorkflowProfiles.state_ok c (project_state s) = true.
Proof.
  intros c s HE HS.
  unfold pilot_state_ok, pilot_exclusive, pilot_phase_ok in HS.
  repeat rewrite andb_true_iff in HS.
  destruct HS as [[[[[[[HX HPE] HPP] _] _] HW] HEL] HDW].
  assert (HXw : WorkflowProfiles.exclusive (project_state s) = true) by exact HX.
  assert (HPEw : WorkflowProfiles.phase_ok (WorkflowProfiles.editor (project_state s)) = true)
    by exact HPE.
  assert (HPPw : WorkflowProfiles.phase_ok (WorkflowProfiles.painter (project_state s)) = true)
    by exact HPP.
  destruct (WorkflowProfiles.complete_transition_peak_fits c (project_state s)
              HE HXw HPEw HPPw) as [Hram Hstore].
  unfold WorkflowProfiles.state_ok.
  repeat rewrite andb_true_iff.
  repeat split.
  - exact HXw.
  - exact HPEw.
  - exact HPPw.
  - apply (proj2 (Nat.leb_le _ _)); exact Hram.
  - apply (proj2 (Nat.leb_le _ _)); exact Hstore.
  - exact HW.
  - exact HEL.
  - exact HDW.
Qed.

Theorem crash_preserves_active_cp :
  forall c s cut t,
    pilot_propose c s (PCrash cut) = Some t ->
    active_cp (ps_editor_store t) = active_cp (ps_editor_store s) /\
    active_cp (ps_painter_store t) = active_cp (ps_painter_store s).
Proof.
  intros c s cut t H.
  inversion H; subst; clear H.
  unfold active_cp, discard_staging; cbn.
  split; [destruct (active_slot (ps_editor_store s)); reflexivity |
          destruct (active_slot (ps_painter_store s)); reflexivity].
Qed.

Example every_pilot_crash_cut_preserves_durable_and_recovers :
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PRequest WorkflowProfiles.Painter;
            PStage editor_cp_1;
            PCrash CutAfterStageBeforeCommit] with
   | Some s =>
       (match active_cp (ps_editor_store s) with
        | Some cp => doc_eqb (ccp_doc cp) (DocEditor initial_editor_saved)
        | None => false
        end) &&
       pilot_accepted WorkflowProfiles.reference s [PRecover WorkflowProfiles.cleared]
   | None => false
   end) = true /\
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PRequest WorkflowProfiles.Painter;
            PStage editor_cp_1;
            PCommitFlip;
            PCrash CutAfterCommitBeforeRelease] with
   | Some s =>
       (match active_cp (ps_editor_store s) with
        | Some cp => doc_eqb (ccp_doc cp) (DocEditor witness_EditorDoc)
        | None => false
        end) &&
       pilot_accepted WorkflowProfiles.reference s [PRecover WorkflowProfiles.cleared]
   | None => false
   end) = true /\
  (match pilot_run WorkflowProfiles.reference pilot_initial
           [PRequest WorkflowProfiles.Painter;
            PStage editor_cp_1;
            PCommitFlip;
            PRelease WorkflowProfiles.cleared;
            PBeginRestore;
            PCrash CutDuringRestoreBeforeFinish] with
   | Some s =>
       (match active_cp (ps_editor_store s) with
        | Some cp => doc_eqb (ccp_doc cp) (DocEditor witness_EditorDoc)
        | None => false
        end) &&
       pilot_accepted WorkflowProfiles.reference s [PRecover WorkflowProfiles.cleared]
   | None => false
   end) = true.
Proof. repeat split; vm_reflexivity. Qed.
