(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Finite workflow qualification for Q32a. R-08-015a keeps fixed placement;
   R-11-018 and R-11-018a require admitted edges and continuing service;
   R-14-011a and R-14-011b require semantic checkpoints and complete reuse.
   This is a source-level two-app, one-arena contract, not runtime evidence.
   Root receipts denote the complete Q22a inventory, including minting roots,
   narrowed bases, saved state, loans, proxies and devices. Storage receipts
   denote authenticated durable commits under the existing Fresh policy.
   Timing numbers are abstract units supplied by the schedule adapter.
   No physical fact follows merely from constructing one of these records.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-08-015a R-11-018 R-11-018a R-14-011a R-14-011b
   SHA256: 2d06c97c6f21e96cfdb86b009a9b62bf07efc8f05dfe672ba1b23487aff612ad
   (*| END derived |*)
   ========================================================================= *)
From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.

Inductive App := Editor | Painter.
Definition appeqb (a b : App) : bool :=
  match a, b with Editor, Editor | Painter, Painter => true | _, _ => false end.
Definition other (a : App) : App := match a with Editor => Painter | Painter => Editor end.
Inductive Phase := Active | Background | Frozen | Quiescing | Retiring |
                   Hibernated | Restoring | Closed.
Inductive Data := EmptyDocument | SavedDocument | EditedDocument.
Definition dataeqb (a b : Data) : bool :=
  match a, b with EmptyDocument, EmptyDocument | SavedDocument, SavedDocument |
    EditedDocument, EditedDocument => true | _, _ => false end.
Inductive Payload := Semantic | RawHeap | Executable | SessionKey.

Record Checkpoint := {
  cp_app : App; cp_data : Data; cp_payload : Payload;
  cp_schema : bool; cp_generation : bool; cp_label : bool;
  cp_authenticated : bool; cp_committed : bool;
  cp_security_critical : bool; cp_fresh : bool
}.
Definition cp_ok (a : App) (c : Checkpoint) : bool :=
  appeqb a (cp_app c) &&
  (match cp_payload c with Semantic => true | _ => false end) &&
  cp_schema c && cp_generation c && cp_label c && cp_authenticated c &&
  cp_committed c && (negb (cp_security_critical c) || cp_fresh c).
Definition checkpoint (a : App) (d : Data) : Checkpoint :=
  {| cp_app := a; cp_data := d; cp_payload := Semantic; cp_schema := true;
     cp_generation := true; cp_label := true; cp_authenticated := true;
     cp_committed := true; cp_security_critical := false; cp_fresh := false |}.
Definition witness_Checkpoint : Checkpoint := checkpoint Editor SavedDocument.

(* The booleans are observable postconditions of named consumers, never timers.
   raw_saved_clear is checked independently of a bitmap's filtered load result. *)
Record Roots := {
  inventory_complete : bool; bases_closed : bool; ingress_closed : bool;
  live_registers_clear : bool; raw_saved_clear : bool; mint_roots_clear : bool;
  loans_closed : bool; proxy_acknowledged : bool; devices_completed : bool;
  barrier_complete : bool; sweep_after_barrier : bool;
  sweep_complete : bool; data_tags_sanitized : bool
}.
Definition reusable (r : Roots) : bool :=
  inventory_complete r && bases_closed r && ingress_closed r &&
  live_registers_clear r && raw_saved_clear r && mint_roots_clear r &&
  loans_closed r && proxy_acknowledged r && devices_completed r &&
  barrier_complete r && sweep_after_barrier r && sweep_complete r &&
  data_tags_sanitized r.
Definition cleared : Roots :=
  {| inventory_complete := true; bases_closed := true; ingress_closed := true;
     live_registers_clear := true; raw_saved_clear := true; mint_roots_clear := true;
     loans_closed := true; proxy_acknowledged := true; devices_completed := true;
     barrier_complete := true; sweep_after_barrier := true;
     sweep_complete := true; data_tags_sanitized := true |}.
Definition witness_Roots : Roots := cleared.

Theorem reusable_has_every_root : forall (r : Roots), reusable r = true ->
  live_registers_clear r = true /\ raw_saved_clear r = true /\
  mint_roots_clear r = true /\ loans_closed r = true /\
  proxy_acknowledged r = true /\ devices_completed r = true /\
  barrier_complete r = true /\ sweep_after_barrier r = true /\
  sweep_complete r = true /\ data_tags_sanitized r = true.
Proof. intros r H; unfold reusable in H; repeat rewrite andb_true_iff in H; tauto. Qed.

Record AppState := {
  phase : Phase; owns_arena : bool; durable : option Checkpoint;
  document : Data; document_grant : bool; session_authority : bool;
  retirement_committed : bool
}.
Definition appstate (p : Phase) (own : bool) (c : option Checkpoint)
                   (d : Data) (g session : bool) : AppState :=
  {| phase := p; owns_arena := own; durable := c; document := d;
     document_grant := g; session_authority := session; retirement_committed := false |}.
Definition committed_state (cp : Checkpoint) : AppState :=
  {| phase := Retiring; owns_arena := true; durable := Some cp;
     document := cp_data cp; document_grant := false; session_authority := false;
     retirement_committed := true |}.
Definition dormant (a : App) : AppState :=
  appstate Hibernated false (Some (checkpoint a SavedDocument)) SavedDocument false false.
Definition witness_AppState : AppState := dormant Editor.
Record State := {
  editor : AppState; painter : AppState; selected : App; target : option App;
  dwell : nat; writes : nat; elapsed : nat
}.
Definition get (s : State) (a : App) : AppState :=
  match a with Editor => editor s | Painter => painter s end.
Definition put (s : State) (a : App) (v : AppState) : State :=
  {| editor := match a with Editor => v | Painter => editor s end;
     painter := match a with Editor => painter s | Painter => v end;
     selected := selected s; target := target s; dwell := dwell s;
     writes := writes s; elapsed := elapsed s |}.
Definition control (s : State) (sel : App) (t : option App) (d w e : nat) : State :=
  {| editor := editor s; painter := painter s; selected := sel; target := t;
     dwell := d; writes := w; elapsed := e |}.
Definition initial : State :=
  {| editor := appstate Active true (Some (checkpoint Editor SavedDocument))
                        EditedDocument true true;
     painter := dormant Painter; selected := Editor; target := None;
     dwell := 2; writes := 0; elapsed := 0 |}.
Definition witness_State : State := initial.

(* Distinct candidate owners can both claim the same physical arena. *)
Definition exclusive (s : State) : bool := negb (owns_arena (editor s) && owns_arena (painter s)).
Definition workspace (a : AppState) : nat :=
  match phase a with Quiescing | Retiring | Restoring => 16 | _ => 0 end.
Definition private_bytes (a : AppState) : nat := if owns_arena a then 64 else 0.
Definition checkpoint_bytes (a : AppState) : nat := match durable a with Some _ => 16 | None => 0 end.
Definition ram (s : State) : nat :=
  40 + 8 + private_bytes (editor s) + private_bytes (painter s) +
  workspace (editor s) + workspace (painter s).
Definition store (s : State) : nat :=
  checkpoint_bytes (editor s) + checkpoint_bytes (painter s) +
  match target s with Some _ => 16 | None => 0 end.
Definition phase_ok (a : AppState) : bool :=
  match phase a with
  | Hibernated | Closed => negb (owns_arena a) && negb (document_grant a) && negb (session_authority a)
  | _ => owns_arena a
  end.

Record Edge := {
  edge_enabled : bool; user_authority : bool; observable_request : bool;
  global_change : bool; root_attested : bool; settings_equal : bool;
  fixed_binding : bool; protected_state : bool; bounded_operations : bool;
  ram_limit : nat; store_limit : nat; write_limit : nat;
  old_last_gap : nat; edge_service_gap : nat; new_first_gap : nat;
  continuing_deadline : nat; carry_work : nat; checkpoint_work : nat;
  retire_work : nat; sanitize_work : nat; restore_work : nat;
  recovery_work : nat;
  work_budget : nat; completion_deadline : nat;
  queue_limit : nat; min_dwell : nat; recovery_reserved : bool
}.
Definition work (c : Edge) : nat := carry_work c + checkpoint_work c +
  retire_work c + sanitize_work c + restore_work c + recovery_work c.
Definition chain (c : Edge) : nat := old_last_gap c + edge_service_gap c + new_first_gap c.
Definition edge_ok (c : Edge) : bool :=
  edge_enabled c && user_authority c && observable_request c &&
  (if global_change c then root_attested c else settings_equal c) &&
  fixed_binding c && negb (protected_state c) && bounded_operations c &&
  (128 <=? ram_limit c) && (48 <=? store_limit c) &&
  (1 <=? carry_work c) && (2 <=? checkpoint_work c) &&
  (2 <=? retire_work c) && (1 <=? sanitize_work c) &&
  (2 <=? restore_work c) && (4 <=? recovery_work c) &&
  (chain c <=? continuing_deadline c) && (work c <=? work_budget c) &&
  (work_budget c <=? completion_deadline c) && (1 <=? queue_limit c) &&
  (0 <? min_dwell c) && recovery_reserved c.
Definition state_ok (c : Edge) (s : State) : bool :=
  exclusive s && phase_ok (editor s) && phase_ok (painter s) &&
  (ram s <=? ram_limit c) && (store s <=? store_limit c) &&
  (writes s <=? write_limit c) && (elapsed s <=? completion_deadline c) &&
  (dwell s <=? min_dwell c).
Definition reference : Edge :=
  {| edge_enabled := true; user_authority := true; observable_request := true;
     global_change := false; root_attested := false; settings_equal := true;
     fixed_binding := true; protected_state := false; bounded_operations := true;
     ram_limit := 128; store_limit := 48; write_limit := 8;
     old_last_gap := 2; edge_service_gap := 4; new_first_gap := 2;
     continuing_deadline := 8; carry_work := 1; checkpoint_work := 2;
     retire_work := 2; sanitize_work := 1; restore_work := 2;
     recovery_work := 4; work_budget := 12; completion_deadline := 14;
     queue_limit := 1; min_dwell := 2; recovery_reserved := true |}.
Definition witness_Edge : Edge := reference.

Inductive Event :=
| Request (a : App) | Freeze | ServeBackground | Commit (c : Checkpoint)
| CommitFailed | Release (r : Roots) | BeginRestore
| FinishRestore (current_grant : bool) | RestoreFailed | Recover (r : Roots) | Crash | Tick.

Definition with_phase (v : AppState) (p : Phase) : AppState :=
  appstate p (owns_arena v) (durable v) (document v)
           (document_grant v) (session_authority v).
Definition stopped (v : AppState) (p : Phase) (own : bool) : AppState :=
  appstate p own (durable v) (document v) false false.
Definition checkpoint_present (a : App) (v : AppState) : bool :=
  match durable v with Some cp => cp_ok a cp | None => false end.

(* Each step is one bounded service quantum. Refusal returns None, so callers
   retain the source state. Destructive failures enter explicit recovery. *)
Definition propose (c : Edge) (s : State) (e : Event) : option State :=
  let old := selected s in let v := get s old in
  match e with
  | Tick => match target s with
            | None => Some (control s old None (Nat.min (min_dwell c) (S (dwell s))) (writes s) 0)
            | Some _ => None end
  | Request a => match target s with
    | Some _ => None
    | None => if edge_ok c && negb (appeqb old a) && (min_dwell c <=? dwell s) &&
                  (writes s <? write_limit c) &&
                  (match phase v with Active | Background | Frozen | Closed => true | _ => false end)
              then Some (control (put s old
                  (match phase v with Closed => v | _ => with_phase v Quiescing end)) old (Some a)
                       0 (writes s) (carry_work c))
              else None end
  | Freeze => match target s, phase v with
    | None, Active => Some (put s old (with_phase v Frozen)) | _, _ => None end
  | ServeBackground => match target s, phase v with
    | None, Active => Some (put s old (with_phase v Background)) | _, _ => None end
  | Commit cp => match target s, phase v with
    | Some a, Quiescing => if cp_ok old cp && dataeqb (cp_data cp) (document v)
      then Some (control (put s old (committed_state cp)) old (Some a) 0 (S (writes s))
          (elapsed s + checkpoint_work c))
      else None | _, _ => None end
  | CommitFailed => match target s, phase v with
    | Some _, Quiescing => Some (control (put s old (with_phase v Active)) old None 0 (writes s) 0)
    | _, _ => None end
  | Release r => match target s, phase v with
    | Some a, Retiring => if reusable r && retirement_committed v
      then Some (control (put s old (stopped v Hibernated false)) old (Some a)
                         0 (writes s) (elapsed s + retire_work c + sanitize_work c)) else None
    | _, _ => None end
  | BeginRestore => match target s, phase v with
    | Some a, Hibernated | Some a, Closed => let dst := get s a in
      if negb (owns_arena dst) && checkpoint_present a dst
      then Some (control (put s a (stopped dst Restoring true)) old (Some a)
                        0 (writes s) (elapsed s + restore_work c)) else None
    | _, _ => None end
  | FinishRestore grant => match target s, phase v with
    | Some a, Hibernated | Some a, Closed => let dst := get s a in
      match phase dst, durable dst with
      | Restoring, Some cp => if cp_ok a cp
        then Some (control (put s a (appstate Active true (Some cp) (cp_data cp) grant false))
                           a None 0 (writes s) 0) else None
      | _, _ => None end
    | _, _ => None end
  | RestoreFailed => match target s with
    | Some a => let dst := get s a in
      match phase dst with
      | Restoring => Some (control (put s a (stopped dst Retiring true)) a (Some old)
                          0 (writes s) (elapsed s))
      | _ => None end
    | None => None end
  | Recover r =>
      let owner := if owns_arena (editor s) then Editor else
                   if owns_arena (painter s) then Painter else old in
      let victim := get s owner in
      if reusable r &&
         (match phase victim with Retiring | Hibernated => true | _ => false end)
      then Some (control (put s owner (stopped victim Closed false)) owner None 0
                         (writes s) (elapsed s + recovery_work c)) else None
  | Crash =>
      (* A crash preserves durable records. Raw arena authority stays quarantined
         until the boot/kernel adapter establishes the same release receipt. *)
      Some (control
        (put (put s Editor (stopped (editor s)
          (if owns_arena (editor s) then Retiring else Hibernated) (owns_arena (editor s))))
          Painter (stopped (painter s)
          (if owns_arena (painter s) then Retiring else Hibernated) (owns_arena (painter s))))
        old (Some (other old)) 0 (writes s) 0)
  end.

Definition step (c : Edge) (s : State) (e : Event) : option State :=
  if edge_ok c && state_ok c s then
    match propose c s e with
    | Some t => if state_ok c t then Some t else None
    | None => None end
  else None.
Fixpoint run (c : Edge) (s : State) (es : list Event) : option State :=
  match es with [] => Some s | e :: rest =>
    match step c s e with Some t => run c t rest | None => None end end.

Theorem step_preserves_admission : forall (c : Edge) (s t : State) e,
  step c s e = Some t -> state_ok c t = true /\ edge_ok c = true.
Proof.
  intros c s t e H. unfold step in H.
  destruct (edge_ok c && state_ok c s) eqn:E; try discriminate.
  apply andb_true_iff in E as [E _]. destruct (propose c s e) as [u|]; try discriminate.
  destruct (state_ok c u) eqn:U; inversion H; subst; auto.
Qed.
Theorem run_preserves_admission : forall es (c : Edge) (s t : State),
  state_ok c s = true -> run c s es = Some t -> state_ok c t = true.
Proof.
  induction es as [|e es IH]; intros c s t HS H; simpl in H.
  - inversion H; subst; assumption.
  - destruct (step c s e) as [u|] eqn:E; try discriminate.
    eapply IH; [exact (proj1 (step_preserves_admission c s u e E)) | exact H].
Qed.
Theorem admitted_bounds : forall (c : Edge) (s : State), state_ok c s = true ->
  ~ (owns_arena (editor s) = true /\ owns_arena (painter s) = true) /\
  ram s <= ram_limit c /\ store s <= store_limit c /\
  writes s <= write_limit c /\ elapsed s <= completion_deadline c.
Proof.
  intros c s H. unfold state_ok, exclusive in H.
  repeat rewrite andb_true_iff in H. repeat rewrite Nat.leb_le in H.
  rewrite negb_true_iff in H. destruct H as [[[[[[[HX _] _] HR] HS] HW] HE] _].
  repeat split; try assumption. intros [A B]; rewrite A, B in HX; discriminate.
Qed.
Theorem reachable_exclusive_and_bounded : forall es (c : Edge) (s t : State),
  state_ok c s = true -> run c s es = Some t ->
  ~ (owns_arena (editor t) = true /\ owns_arena (painter t) = true) /\
  ram t <= ram_limit c /\ store t <= store_limit c /\
  writes t <= write_limit c /\ elapsed t <= completion_deadline c.
Proof. intros; apply admitted_bounds; eapply run_preserves_admission; eauto. Qed.
Theorem continuing_service_bound : forall (c : Edge), edge_ok c = true ->
  old_last_gap c + edge_service_gap c + new_first_gap c <= continuing_deadline c /\
  work c <= work_budget c /\ work_budget c <= completion_deadline c.
Proof.
  intros c H; unfold edge_ok, chain in H.
  repeat rewrite andb_true_iff in H; repeat rewrite Nat.leb_le in H; tauto.
Qed.

Lemma workspace_fits_owned_arena : forall (v : AppState), phase_ok v = true ->
  workspace v <= if owns_arena v then 16 else 0.
Proof.
  intros [p own cp d g key committed] H; destruct p, own;
    cbn in *; try discriminate; lia.
Qed.
Theorem complete_transition_peak_fits : forall (c : Edge) (s : State),
  edge_ok c = true -> exclusive s = true ->
  phase_ok (editor s) = true -> phase_ok (painter s) = true ->
  ram s <= ram_limit c /\ store s <= store_limit c.
Proof.
  intros c s HE HX HA HB.
  pose proof (workspace_fits_owned_arena (editor s) HA) as EA.
  pose proof (workspace_fits_owned_arena (painter s) HB) as EB.
  assert (HM : 128 <= ram_limit c) by
    (unfold edge_ok in HE; repeat rewrite andb_true_iff in HE;
     repeat rewrite Nat.leb_le in HE; tauto).
  assert (HD : 48 <= store_limit c) by
    (unfold edge_ok in HE; repeat rewrite andb_true_iff in HE;
     repeat rewrite Nat.leb_le in HE; tauto).
  split.
  - unfold ram, private_bytes, exclusive in *.
    destruct (owns_arena (editor s)), (owns_arena (painter s));
      cbn in *; try discriminate; lia.
  - unfold store, checkpoint_bytes.
    destruct (durable (editor s)), (durable (painter s)), (target s); lia.
Qed.

Theorem admitted_stage_costs_are_reserved : forall (c : Edge), edge_ok c = true ->
  1 <= carry_work c /\ 2 <= checkpoint_work c /\ 2 <= retire_work c /\
  1 <= sanitize_work c /\ 2 <= restore_work c /\ 4 <= recovery_work c /\
  carry_work c + checkpoint_work c + retire_work c + sanitize_work c +
    restore_work c + recovery_work c <= completion_deadline c.
Proof.
  intros c H; unfold edge_ok, work in H.
  repeat rewrite andb_true_iff in H; repeat rewrite Nat.leb_le in H.
  intuition lia.
Qed.

Lemma get_put_same : forall s a v, get (put s a v) a = v.
Proof. intros s []; reflexivity. Qed.
Lemma get_control : forall s a t d w e x, get (control s a t d w e) x = get s x.
Proof. intros s a t d w e []; reflexivity. Qed.
Theorem restore_uses_current_grant : forall (c : Edge) (s t : State) g a,
  target s = Some a -> propose c s (FinishRestore g) = Some t ->
  document_grant (get t a) = g /\ session_authority (get t a) = false.
Proof.
  intros c s t g a Ht H. cbn in H. rewrite Ht in H.
  destruct (phase (get s (selected s))); try discriminate;
    destruct (phase (get s a)); try discriminate;
    destruct (durable (get s a)) as [cp|]; try discriminate;
    destruct (cp_ok a cp); try discriminate; inversion H; subst;
    rewrite get_control, get_put_same; split; reflexivity.
Qed.
Theorem release_requires_complete_reuse : forall (c : Edge) (s t : State) r,
  propose c s (Release r) = Some t -> reusable r = true /\
  owns_arena (get t (selected s)) = false /\
  document_grant (get t (selected s)) = false /\
  session_authority (get t (selected s)) = false.
Proof.
  intros c s t r H; cbn in H. destruct (target s); try discriminate.
  destruct (phase (get s (selected s))); try discriminate.
  destruct (reusable r && retirement_committed (get s (selected s))) eqn:R; try discriminate.
  apply andb_true_iff in R as [R _]. inversion H; subst.
  rewrite get_control, get_put_same. repeat split; try reflexivity; assumption.
Qed.
Theorem failed_commit_preserves_acknowledged_data : forall (c : Edge) (s t : State),
  propose c s CommitFailed = Some t -> forall a, durable (get t a) = durable (get s a).
Proof.
  intros c s t H a; cbn in H. destruct (target s); try discriminate.
  destruct (phase (get s (selected s))); try discriminate. inversion H; subst.
  destruct a, (selected s); reflexivity.
Qed.
Theorem crash_preserves_acknowledged_data : forall (c : Edge) (s t : State),
  propose c s Crash = Some t -> forall a, durable (get t a) = durable (get s a).
Proof. intros c s t H a; inversion H; subst; destruct a; reflexivity. Qed.

Lemma dataeqb_sound : forall a b, dataeqb a b = true -> a = b.
Proof. destruct a, b; simpl; intros; congruence. Qed.
Theorem commit_preserves_declared_document : forall (c : Edge) (s t : State) cp,
  propose c s (Commit cp) = Some t ->
  cp_data cp = document (get s (selected s)) /\
  durable (get t (selected s)) = Some cp.
Proof.
  intros c s t cp H; cbn in H. destruct (target s); try discriminate.
  destruct (phase (get s (selected s))); try discriminate.
  destruct (cp_ok (selected s) cp && dataeqb (cp_data cp) (document (get s (selected s))))
    eqn:E; try discriminate.
  apply andb_true_iff in E as [_ E]. apply dataeqb_sound in E.
  inversion H; subst; rewrite get_control, get_put_same. auto.
Qed.

(* A consumer supplies a forward simulation of each actual accepted event.
   No implementation transition may hide behind a receipt constructor. *)
Inductive ImplementationTrace {C : Type} (advance : C -> Event -> C -> Prop) :
  C -> list Event -> C -> Prop :=
| TraceNil : forall x, ImplementationTrace advance x [] x
| TraceCons : forall x y z e es, advance x e y ->
    ImplementationTrace advance y es z -> ImplementationTrace advance x (e :: es) z.
Theorem consumer_refinement_preserves_admitted_invariants :
  forall (C : Type) (view : C -> State) (advance : C -> Event -> C -> Prop) (c : Edge),
  (forall x e y, advance x e y -> step c (view x) e = Some (view y)) ->
  forall x es y, ImplementationTrace advance x es y ->
  state_ok c (view x) = true -> state_ok c (view y) = true.
Proof.
  intros C view advance c SIM x es y H. induction H; intros HS; [exact HS|].
  apply IHImplementationTrace. exact (proj1 (step_preserves_admission c (view x) (view y) e (SIM x e y H))).
Qed.

(* Runtime join: every represented bit denotes old authority or a mint capable
   of recreating it. This is deliberately raw saved authority, not a filtered
   reload while the revocation bit remains set. The closure premise must cover
   future writes and asynchronous completions after the barrier. *)
Record MachineInventory := {
  register_tags : list bool; saved_tags : list bool; memory_tags : list bool;
  mint_tags : list bool;
  loan_tags : list bool; proxy_tags : list bool; device_tags : list bool
}.
Definition witness_MachineInventory : MachineInventory :=
  {| register_tags := [false]; saved_tags := [false]; memory_tags := [false; false];
     mint_tags := [false]; loan_tags := [false]; proxy_tags := [false];
     device_tags := [false] |}.
Definition raw_authority (m : MachineInventory) : list bool :=
  register_tags m ++ saved_tags m ++ memory_tags m ++ mint_tags m ++
  loan_tags m ++ proxy_tags m ++ device_tags m.
Definition root_correspondence (r : Roots) (m : MachineInventory) : Prop :=
  (live_registers_clear r = true -> ~ In true (register_tags m)) /\
  (raw_saved_clear r = true -> ~ In true (saved_tags m)) /\
  (sweep_complete r = true -> data_tags_sanitized r = true -> ~ In true (memory_tags m)) /\
  (mint_roots_clear r = true -> ~ In true (mint_tags m)) /\
  (loans_closed r = true -> ~ In true (loan_tags m)) /\
  (proxy_acknowledged r = true -> ~ In true (proxy_tags m)) /\
  (devices_completed r = true -> ~ In true (device_tags m)).
Definition stale_memory_inventory : MachineInventory :=
  {| register_tags := [false]; saved_tags := [false]; memory_tags := [false; true];
     mint_tags := [false]; loan_tags := [false]; proxy_tags := [false];
     device_tags := [false] |}.
Example nonempty_inventory_is_cleared : root_correspondence cleared witness_MachineInventory.
Proof. unfold root_correspondence, cleared, witness_MachineInventory; simpl; intuition discriminate. Qed.
Example stale_ordinary_memory_is_authority : In true (raw_authority stale_memory_inventory).
Proof. unfold raw_authority, stale_memory_inventory; simpl; auto. Qed.
Example stale_ordinary_memory_refuses_receipt : ~ root_correspondence cleared stale_memory_inventory.
Proof. unfold root_correspondence, cleared, stale_memory_inventory; simpl; intuition discriminate. Qed.
Theorem reusable_clears_inventory : forall (r : Roots) (m : MachineInventory),
  root_correspondence r m -> reusable r = true -> ~ In true (raw_authority m).
Proof.
  intros r m HC HR. apply reusable_has_every_root in HR.
  unfold root_correspondence in HC. unfold raw_authority.
  repeat rewrite in_app_iff. tauto.
Qed.
Theorem no_authority_resurrection_under_machine_premise :
  forall (c : Edge) (s t : State) r (m : MachineInventory)
         (old_authority_can_reappear : Prop),
  root_correspondence r m ->
  (old_authority_can_reappear -> In true (raw_authority m)) ->
  propose c s (Release r) = Some t -> ~ old_authority_can_reappear.
Proof.
  intros c s t r m P HC closure HR HP.
  apply (reusable_clears_inventory r m HC
    (proj1 (release_requires_complete_reuse c s t r HR))). exact (closure HP).
Qed.

Definition execution_slots (v : AppState) : nat :=
  match phase v with Active | Background => 1 | _ => 0 end.
Theorem hibernation_has_zero_private_work : forall (c : Edge) (s t : State) r,
  propose c s (Release r) = Some t ->
  private_bytes (get t (selected s)) = 0 /\ execution_slots (get t (selected s)) = 0.
Proof.
  intros c s t r H. cbn in H; destruct (target s); try discriminate.
  destruct (phase (get s (selected s))); try discriminate.
  destruct (reusable r && retirement_committed (get s (selected s))); try discriminate.
  inversion H; subst.
  rewrite get_control, get_put_same. split; reflexivity.
Qed.

Definition switch_to (a : App) : list Event :=
  [Request a; Commit (checkpoint (other a)
    (match a with Painter => EditedDocument | Editor => SavedDocument end)); Release cleared;
   BeginRestore; FinishRestore true].
Definition accepted (c : Edge) (s : State) (es : list Event) : bool :=
  match run c s es with Some _ => true | None => false end.
Example successful_switch : accepted reference initial (switch_to Painter) = true.
Proof. vm_compute; reflexivity. Qed.
Example immediate_repeated_switch_refused :
  accepted reference initial (switch_to Painter ++ switch_to Editor) = false.
Proof. vm_compute; reflexivity. Qed.
Example dwell_permits_repeated_switch :
  accepted reference initial (switch_to Painter ++ [Tick; Tick] ++ switch_to Editor) = true.
Proof. vm_compute; reflexivity. Qed.
Example overlap_candidate_refused :
  state_ok reference (put initial Painter (appstate Restoring true
                (durable (painter initial)) SavedDocument false false)) = false.
Proof. vm_compute; reflexivity. Qed.
Example restore_before_reuse_refused :
  accepted reference initial [Request Painter; Commit (checkpoint Editor EditedDocument); BeginRestore] = false.
Proof. vm_compute; reflexivity. Qed.
Example failed_commit_recovers_old_app :
  accepted reference initial [Request Painter; CommitFailed] = true.
Proof. vm_compute; reflexivity. Qed.
Example failed_restore_keeps_quarantine :
  match run reference initial [Request Painter; Commit (checkpoint Editor EditedDocument);
    Release cleared; BeginRestore; RestoreFailed] with
  | Some s => owns_arena (painter s) && match phase (painter s) with Retiring => true | _ => false end
  | None => false end = true.
Proof. vm_compute; reflexivity. Qed.

(* Fault constructors generate one failed Q22a clause at a time. *)
Definition missing_root_clause (n : nat) : Roots :=
  {| inventory_complete := negb (n =? 0); bases_closed := negb (n =? 1);
     ingress_closed := negb (n =? 2); live_registers_clear := negb (n =? 3);
     raw_saved_clear := negb (n =? 4); mint_roots_clear := negb (n =? 5);
     loans_closed := negb (n =? 6); proxy_acknowledged := negb (n =? 7);
     devices_completed := negb (n =? 8); barrier_complete := negb (n =? 9);
     sweep_after_barrier := negb (n =? 10); sweep_complete := negb (n =? 11);
     data_tags_sanitized := negb (n =? 12) |}.
Definition retirement_prefix : list Event :=
  [Request Painter; Commit (checkpoint Editor EditedDocument)].
Example every_incomplete_reuse_clause_refuses :
  forallb (fun n => negb (accepted reference initial
    (retirement_prefix ++ [Release (missing_root_clause n)]))) (seq 0 13) = true.
Proof. vm_compute; reflexivity. Qed.

(* Each altered certificate is otherwise the actual accepted pilot. *)
Definition budgets (memory disk gap budget cp_cost : nat) : Edge :=
  {| edge_enabled := true; user_authority := true; observable_request := true;
     global_change := false; root_attested := false; settings_equal := true;
     fixed_binding := true; protected_state := false; bounded_operations := true;
     ram_limit := memory; store_limit := disk; write_limit := 8;
     old_last_gap := 2; edge_service_gap := gap; new_first_gap := 2;
     continuing_deadline := 8; carry_work := 1; checkpoint_work := cp_cost;
     retire_work := 2; sanitize_work := 1; restore_work := 2;
     recovery_work := 4; work_budget := budget; completion_deadline := 14;
     queue_limit := 1; min_dwell := 2; recovery_reserved := true |}.
Example endpoint_safe_transition_ram_overload :
  state_ok (budgets 112 48 4 12 2) initial = true /\
  accepted (budgets 112 48 4 12 2) initial [Request Painter] = false.
Proof. vm_compute; auto. Qed.
Example endpoint_safe_transition_store_overload :
  state_ok (budgets 128 32 4 12 2) initial = true /\
  accepted (budgets 128 32 4 12 2) initial [Request Painter] = false.
Proof. vm_compute; auto. Qed.
Example continuing_service_gap_refused :
  accepted (budgets 128 48 5 12 2) initial [Request Painter] = false.
Proof. vm_compute; reflexivity. Qed.
Example work_overload_refused :
  accepted (budgets 128 48 4 11 2) initial [Request Painter] = false.
Proof. vm_compute; reflexivity. Qed.
Example unpriced_checkpoint_work_refused :
  accepted (budgets 128 48 4 12 0) initial [Request Painter] = false.
Proof. vm_compute; reflexivity. Qed.
Example pending_request_has_bounded_refusal :
  accepted reference initial [Request Painter; Request Editor] = false.
Proof. vm_compute; reflexivity. Qed.

Definition invalid_checkpoint (n : nat) : Checkpoint :=
  {| cp_app := if n =? 0 then Painter else Editor; cp_data := EditedDocument;
     cp_payload := if n =? 1 then RawHeap else if n =? 2 then Executable
                   else if n =? 3 then SessionKey else Semantic;
     cp_schema := negb (n =? 4); cp_generation := negb (n =? 5);
     cp_label := negb (n =? 6); cp_authenticated := negb (n =? 7);
     cp_committed := negb (n =? 8); cp_security_critical := n =? 9;
     cp_fresh := false |}.
Example checkpoint_binding_and_authority_neighbors_refused :
  forallb (fun n => negb (accepted reference initial
    [Request Painter; Commit (invalid_checkpoint n)])) (seq 0 10) = true.
Proof. vm_compute; reflexivity. Qed.
Example lost_unsaved_document_refused :
  accepted reference initial [Request Painter; Commit (checkpoint Editor SavedDocument)] = false.
Proof. vm_compute; reflexivity. Qed.
Example revoked_grant_and_old_session_not_restored :
  match run reference initial (retirement_prefix ++
    [Release cleared; BeginRestore; FinishRestore false]) with
  | Some s => negb (document_grant (painter s)) && negb (session_authority (painter s))
  | None => false end = true.
Proof. vm_compute; reflexivity. Qed.

Definition crash_prefixes : list (list Event) :=
  map (fun n => firstn n (switch_to Painter) ++ [Crash; Recover cleared]) (seq 0 6).
Definition recovered (s : State) : bool :=
  negb (owns_arena (editor s)) && negb (owns_arena (painter s)) &&
  match target s with None => true | Some _ => false end.
Example every_crash_boundary_reaches_reserved_recovery :
  forallb (fun es => match run reference initial es with
    Some s => recovered s && state_ok reference s | None => false end) crash_prefixes = true.
Proof. vm_compute; reflexivity. Qed.
Example failed_restore_can_finish_retirement :
  accepted reference initial (retirement_prefix ++ [Release cleared; BeginRestore;
     RestoreFailed; Recover cleared]) = true.
Proof. vm_compute; reflexivity. Qed.
Example recovery_is_not_successful_hibernation :
  accepted reference initial [Crash; Release cleared] = false.
Proof. vm_compute; reflexivity. Qed.
Example recovery_can_resume_durable_document :
  accepted reference initial (retirement_prefix ++ [Release cleared; BeginRestore;
     RestoreFailed; Recover cleared; Tick; Tick; Request Editor;
     BeginRestore; FinishRestore false]) = true.
Proof. vm_compute; reflexivity. Qed.

Definition round_trip : list Event :=
  switch_to Painter ++ [Tick; Tick] ++ switch_to Editor ++ [Tick; Tick].
Example repeated_switch_endurance_is_finite :
  accepted reference initial (concat (repeat round_trip 4)) = true /\
  accepted reference initial (concat (repeat round_trip 4) ++ [Request Painter]) = false.
Proof. vm_compute; auto. Qed.

Example exact_stage_and_storage_ledger :
  map (fun n => match run reference initial (firstn n (switch_to Painter)) with
    | Some s => (ram s, store s, elapsed s, dwell s)
    | None => (0, 0, 0, 0) end) (seq 0 6) =
  [(112, 32, 0, 2); (128, 48, 1, 0); (128, 48, 3, 0);
   (48, 48, 6, 0); (128, 48, 8, 0); (112, 32, 0, 0)].
Proof. vm_compute; reflexivity. Qed.
Example failed_commit_resets_request_dwell :
  match run reference initial [Request Painter; CommitFailed] with
  | Some s => dwell s | None => 99 end = 0.
Proof. vm_compute; reflexivity. Qed.
Example recovery_does_not_close_an_active_app :
  accepted reference initial [Recover cleared] = false.
Proof. vm_compute; reflexivity. Qed.
Example every_incomplete_recovery_clause_refuses :
  forallb (fun n => negb (accepted reference initial
    [Crash; Recover (missing_root_clause n)])) (seq 0 13) = true.
Proof. vm_compute; reflexivity. Qed.

Definition alphabet : list Event :=
  [Request Editor; Request Painter; Freeze; ServeBackground;
   Commit (checkpoint Editor EditedDocument); Commit (checkpoint Painter SavedDocument);
   CommitFailed; Release cleared; BeginRestore; FinishRestore true;
   FinishRestore false; RestoreFailed; Recover cleared; Crash; Tick].
Fixpoint generated_reachable (depth : nat) : list (list Event) :=
  match depth with
  | 0 => [[]]
  | S n => flat_map (fun es => filter (accepted reference initial)
        (map (fun e => es ++ [e]) alphabet)) (generated_reachable n)
  end.
Definition refuted_neighbors (es : list Event) : list (list Event) :=
  filter (fun trace => negb (accepted reference initial trace))
         (map (fun e => es ++ [e]) alphabet).
Definition generated_corpus := generated_reachable 5.
Definition generated_refusals := flat_map refuted_neighbors generated_corpus.
Theorem generated_reachable_is_accepted : forall n es,
  In es (generated_reachable n) -> accepted reference initial es = true.
Proof.
  intros n es H. destruct n as [|n].
  - change (In es [[]]) in H. simpl in H.
    destruct H as [H|H]; [subst; reflexivity | contradiction].
  - change (In es (flat_map (fun prefix => filter (accepted reference initial)
      (map (fun e => prefix ++ [e]) alphabet)) (generated_reachable n))) in H.
    apply in_flat_map in H as [prefix [_ H]].
    apply filter_In in H as [_ H]; exact H.
Qed.
Theorem generated_neighbor_is_refused : forall prefix es,
  In es (refuted_neighbors prefix) -> accepted reference initial es = false.
Proof.
  intros prefix es H. apply filter_In in H as [_ H].
  now apply negb_true_iff in H.
Qed.
Example generated_traces_preserve_resource_and_ownership_checks :
  forallb (fun es => match run reference initial es with
    Some s => state_ok reference s | None => false end) generated_corpus = true.
Proof.
  apply forallb_forall; intros es H.
  pose proof (generated_reachable_is_accepted 5 es H) as HA.
  unfold accepted in HA. destruct (run reference initial es) as [s|] eqn:E;
    try discriminate. exact (run_preserves_admission es reference initial s eq_refl E).
Qed.
Example generated_neighbors_are_refused :
  forallb (fun es => negb (accepted reference initial es)) generated_refusals = true.
Proof.
  apply forallb_forall; intros es H. apply in_flat_map in H as [prefix [_ H]].
  apply negb_true_iff. now apply (generated_neighbor_is_refused prefix es).
Qed.
Compute (length generated_corpus, length generated_refusals).

Print Assumptions reachable_exclusive_and_bounded.
Print Assumptions continuing_service_bound.
Print Assumptions restore_uses_current_grant.
Print Assumptions no_authority_resurrection_under_machine_premise.
