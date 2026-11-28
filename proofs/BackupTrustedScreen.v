(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   BackupTrustedScreen.v

   Trusted-path UI state machines, one-time `RecoverySecret-v1` display
   lifecycle, mandatory caveat gates, non-truncated quoted receiver-root
   confirmation, and one-use bound consent witnesses for backup export,
   user-data restore, and device migration (see
   [backup-migration.md](../docs/implementation/contracts/backup-migration.md#3-backup-key-and-trusted-holder-actions)),
   reusing [BackupObject.v](BackupObject.v#encode_recovery_secret) and
   [MigrationSession.v](MigrationSession.v#confirm_roots).

   Scope and obligations (R-10-038, R-10-039, R-10-040, R-17-054a):
   - Distinct trusted-path flows (`ScreenBackupExport`, `ScreenUserRestore`,
     `ScreenDeviceMigration`) separate from `ScreenSystemRollback`.
   - Primary-credential verification and trusted-path hardware latch gating,
     refusing app-originated prompts and locked devices.
   - One-time `RecoverySecret-v1` display lifecycle: single display window,
     16x4 uppercase hex group formatting, canonical 64-char decode on restore
     entry, mandatory zeroization of secret and display buffers on every exit
     (`ExitComplete`, `ExitCancel`, `ExitLock`, `ExitFault`), no redisplay,
     and zero leakage to app, clipboard, screenshot, or log channels.
   - Mandatory `R-17-054a` off-device trade caveat on export, and explicit
     surrendered-freshness and discard-loss caveats on restore.
   - Complete non-truncated quoted receiver-root confirmation on migration,
     refusing unappraised peers, empty or oversized root sets, and truncated
     or substituted confirmations.
   - One-use consent witnesses bound to `(flow, unlocked_profile,
     generation, object_or_snapshot, destination, plan, root_set)` that
     expire on lock, restart, profile/generation/plan/destination change, or
     consumption, and cannot be forged by an application.
   - Closed axiom-free proofs, closed inhabitation witnesses for every
     `Record`, inhabited positive traces, and explicit refutation witnesses
     (R-05-163, R-05-164, R-05-165, R-05-166).
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-10-038 R-10-039 R-10-040 R-17-054a
   SHA256: 109e40606132082b65bb6435a2cb51ba4e7bbc9adf30d0eaa6857689b8a53e0b
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Require ProofSupport BackupObject MigrationSession.
Import ListNotations.

(* =========================================================================
   1. Distinct screen flows, caveats, and trusted-path gate
   ========================================================================= *)

Inductive ScreenFlow : Type :=
| ScreenBackupExport
| ScreenUserRestore
| ScreenDeviceMigration
| ScreenSystemRollback.

Definition flow_code (f : ScreenFlow) : nat :=
  match f with
  | ScreenBackupExport => 1
  | ScreenUserRestore => 2
  | ScreenDeviceMigration => 3
  | ScreenSystemRollback => 4
  end.

Definition screen_flow_eqb (a b : ScreenFlow) : bool :=
  match a, b with
  | ScreenBackupExport, ScreenBackupExport => true
  | ScreenUserRestore, ScreenUserRestore => true
  | ScreenDeviceMigration, ScreenDeviceMigration => true
  | ScreenSystemRollback, ScreenSystemRollback => true
  | _, _ => false
  end.

Lemma screen_flow_eqb_refl : forall f, screen_flow_eqb f f = true.
Proof. intros [| | |]; reflexivity. Qed.

Lemma screen_flow_eqb_sound : forall a b,
  screen_flow_eqb a b = true -> a = b.
Proof. intros [| | |] [| | |] H; try discriminate H; reflexivity. Qed.

Definition is_backup_or_migration_flow (f : ScreenFlow) : bool :=
  match f with
  | ScreenBackupExport => true
  | ScreenUserRestore => true
  | ScreenDeviceMigration => true
  | ScreenSystemRollback => false
  end.

Theorem flow_distinct_from_rollback : forall f,
  is_backup_or_migration_flow f = true ->
  f <> ScreenSystemRollback /\ flow_code f <> flow_code ScreenSystemRollback.
Proof.
  intros [| | |] H; simpl in H; try discriminate H;
    split; intro Heq; discriminate Heq.
Qed.

Record CaveatAck : Type := {
  ca_off_device_trade : bool;
  ca_surrendered_freshness : bool;
  ca_discard_loss : bool;
  ca_migration_roots : bool;
  ca_not_rollback : bool
}.

Definition caveats_satisfied (f : ScreenFlow) (needs_discard : bool)
    (ca : CaveatAck) : bool :=
  ca_not_rollback ca &&
  match f with
  | ScreenBackupExport => ca_off_device_trade ca
  | ScreenUserRestore =>
      ca_surrendered_freshness ca &&
      (if needs_discard then ca_discard_loss ca else true)
  | ScreenDeviceMigration => ca_migration_roots ca
  | ScreenSystemRollback => false
  end.

Record TrustedPathEnv : Type := {
  tp_unlocked : bool;
  tp_hw_latch : bool;
  tp_primary_cred_live : bool;
  tp_receiver_cred_live : bool;
  tp_app_originated : bool;
  tp_epoch : nat;
  tp_active_profile : nat;
  tp_generation : nat
}.

Definition trusted_gate_ok (env : TrustedPathEnv) : bool :=
  tp_unlocked env &&
  tp_hw_latch env &&
  tp_primary_cred_live env &&
  negb (tp_app_originated env).

Definition advance_epoch (env : TrustedPathEnv) : TrustedPathEnv :=
  {| tp_unlocked := false;
     tp_hw_latch := false;
     tp_primary_cred_live := false;
     tp_receiver_cred_live := false;
     tp_app_originated := false;
     tp_epoch := S (tp_epoch env);
     tp_active_profile := tp_active_profile env;
     tp_generation := tp_generation env |}.

Lemma advance_epoch_closes_gate : forall env,
  trusted_gate_ok (advance_epoch env) = false /\
  tp_epoch (advance_epoch env) <> tp_epoch env.
Proof.
  intro env. split; [reflexivity | simpl; lia].
Qed.

(* =========================================================================
   2. One-time RecoverySecret-v1 display formatting and lifecycle
   ========================================================================= *)

Fixpoint format_hex_groups_aux (pos : nat) (hex : list nat) : list nat :=
  match hex with
  | [] => []
  | a :: b :: c :: d :: rest =>
      match rest with
      | [] => [a; b; c; d]
      | _ :: _ => a :: b :: c :: d :: 32 :: format_hex_groups_aux (pos + 4) rest
      end
  | _ => []
  end.

Definition format_display_groups (hex : list nat) : option (list nat) :=
  if Nat.eqb (ProofSupport.count_of hex) 64 then
    Some (format_hex_groups_aux 0 hex)
  else None.

Fixpoint strip_spaces (cs : list nat) : list nat :=
  match cs with
  | [] => []
  | c :: rest => if Nat.eqb c 32 then strip_spaces rest else c :: strip_spaces rest
  end.

Lemma format_hex_groups_aux_no_spaces_roundtrip : forall k a b c d rest pos,
  BackupObject.decode_hex_bytes (a :: b :: c :: d :: rest) <> None ->
  ProofSupport.count_of (a :: b :: c :: d :: rest) = 4 * S k ->
  strip_spaces (format_hex_groups_aux pos (a :: b :: c :: d :: rest)) =
    a :: b :: c :: d :: rest.
Proof.
  induction k as [|k IH]; intros a b c d rest pos Hdec Hcnt.
  - destruct rest as [|x xs].
    + simpl in Hdec.
      destruct (BackupObject.decode_nibble_upper a) as [ha|] eqn:Ea; [|contradiction].
      destruct (BackupObject.decode_nibble_upper b) as [hb|] eqn:Eb; [|contradiction].
      destruct (BackupObject.decode_nibble_upper c) as [hc|] eqn:Ec; [|contradiction].
      destruct (BackupObject.decode_nibble_upper d) as [hd|] eqn:Ed; [|contradiction].
      apply BackupObject.encode_decode_nibble_upper in Ea as [Ha Hla].
      apply BackupObject.encode_decode_nibble_upper in Eb as [Hb Hlb].
      apply BackupObject.encode_decode_nibble_upper in Ec as [Hc Hlc].
      apply BackupObject.encode_decode_nibble_upper in Ed as [Hd Hld].
      assert (Hneq32 : forall n, n < 16 -> Nat.eqb (BackupObject.encode_nibble_upper n) 32 = false).
      { intros n Hn. unfold BackupObject.encode_nibble_upper.
        destruct (Nat.ltb n 10); apply Nat.eqb_neq; lia. }
      simpl.
      rewrite <- Ha, <- Hb, <- Hc, <- Hd.
      rewrite !Hneq32 by assumption. reflexivity.
    + simpl in Hcnt. lia.
  - destruct rest as [|a2 rest1]; [simpl in Hcnt; lia |].
    destruct rest1 as [|b2 rest2]; [simpl in Hcnt; lia |].
    destruct rest2 as [|c2 rest3]; [simpl in Hcnt; lia |].
    destruct rest3 as [|d2 rest4]; [simpl in Hcnt; lia |].
    assert (Hlen2 : ProofSupport.count_of (a2 :: b2 :: c2 :: d2 :: rest4) = 4 * S k).
    { simpl in Hcnt. simpl. lia. }
    assert (Hdec2 : BackupObject.decode_hex_bytes (a2 :: b2 :: c2 :: d2 :: rest4) <> None).
    { intro Hn. apply Hdec. simpl.
      destruct (BackupObject.decode_nibble_upper a),
               (BackupObject.decode_nibble_upper b),
               (BackupObject.decode_nibble_upper c),
               (BackupObject.decode_nibble_upper d);
        try reflexivity.
      simpl in Hn. rewrite Hn.
      destruct (BackupObject.decode_nibble_upper a2),
               (BackupObject.decode_nibble_upper b2); reflexivity. }
    simpl in Hdec.
    destruct (BackupObject.decode_nibble_upper a) as [ha|] eqn:Ea; [|contradiction].
    destruct (BackupObject.decode_nibble_upper b) as [hb|] eqn:Eb; [|contradiction].
    destruct (BackupObject.decode_nibble_upper c) as [hc|] eqn:Ec; [|contradiction].
    destruct (BackupObject.decode_nibble_upper d) as [hd|] eqn:Ed; [|contradiction].
    apply BackupObject.encode_decode_nibble_upper in Ea as [Ha Hla].
    apply BackupObject.encode_decode_nibble_upper in Eb as [Hb Hlb].
    apply BackupObject.encode_decode_nibble_upper in Ec as [Hc Hlc].
    apply BackupObject.encode_decode_nibble_upper in Ed as [Hd Hld].
    assert (Hneq32 : forall n, n < 16 -> Nat.eqb (BackupObject.encode_nibble_upper n) 32 = false).
    { intros n Hn. unfold BackupObject.encode_nibble_upper.
      destruct (Nat.ltb n 10); apply Nat.eqb_neq; lia. }
    cbn [format_hex_groups_aux].
    cbn [strip_spaces].
    rewrite <- Ha, <- Hb, <- Hc, <- Hd.
    rewrite !Hneq32 by assumption.
    simpl.
    f_equal. f_equal. f_equal. f_equal.
    exact (IH a2 b2 c2 d2 rest4 (pos + 4) Hdec2 Hlen2).
Qed.

Theorem display_groups_round_trip_canonical : forall rs hex disp,
  BackupObject.encode_recovery_secret rs = Some hex ->
  format_display_groups hex = Some disp ->
  strip_spaces disp = hex /\
  BackupObject.decode_recovery_secret (strip_spaces disp) = Some rs.
Proof.
  intros rs hex disp Henc Hfmt.
  pose proof (BackupObject.recovery_secret_decode_of_encode rs hex Henc) as Hdec.
  unfold BackupObject.encode_recovery_secret in Henc.
  destruct (BackupObject.rs_wf rs) eqn:Hwf; [|discriminate].
  injection Henc as Hhex.
  unfold format_display_groups in Hfmt.
  destruct (Nat.eqb (ProofSupport.count_of hex) 64) eqn:Hlen; [|discriminate].
  injection Hfmt as Hdisp.
  apply ProofSupport.nat_eqb_true in Hlen.
  unfold BackupObject.rs_wf in Hwf. apply ProofSupport.andb_split in Hwf.
  destruct Hwf as [_ Hok].
  pose proof (BackupObject.decode_hex_bytes_encode (BackupObject.rs_bytes rs) Hok) as Hdb.
  rewrite Hhex in Hdb.
  destruct hex as [|a hex1]; [simpl in Hlen; discriminate |].
  destruct hex1 as [|b hex2]; [simpl in Hlen; discriminate |].
  destruct hex2 as [|c hex3]; [simpl in Hlen; discriminate |].
  destruct hex3 as [|d rest]; [simpl in Hlen; discriminate |].
  assert (Hdec_bytes : BackupObject.decode_hex_bytes (a :: b :: c :: d :: rest) <> None).
  { rewrite Hdb. discriminate. }
  assert (Hstrip : strip_spaces disp = a :: b :: c :: d :: rest).
  { subst disp.
    apply (format_hex_groups_aux_no_spaces_roundtrip 15 a b c d rest 0 Hdec_bytes).
    exact Hlen. }
  split.
  - exact Hstrip.
  - rewrite Hstrip. exact Hdec.
Qed.

Inductive DisplayPhase : Type :=
| DispInit
| DispShowing
| DispCleared.

Inductive DisplayExitEvent : Type :=
| ExitComplete
| ExitCancel
| ExitLock
| ExitFault.

Record DisplayState : Type := {
  ds_phase : DisplayPhase;
  ds_shown_once : bool;
  ds_secret_buf : option (list nat);
  ds_display_buf : option (list nat);
  ds_app_visible : list nat;
  ds_clipboard_buf : list nat;
  ds_screenshot_buf : list nat;
  ds_log_buf : list nat
}.

Definition disp_init : DisplayState :=
  {| ds_phase := DispInit;
     ds_shown_once := false;
     ds_secret_buf := None;
     ds_display_buf := None;
     ds_app_visible := [];
     ds_clipboard_buf := [];
     ds_screenshot_buf := [];
     ds_log_buf := [] |}.

Definition disp_begin (env : TrustedPathEnv) (ca : CaveatAck)
    (rs : BackupObject.RecoverySecret) (st : DisplayState) : option DisplayState :=
  match ds_phase st with
  | DispInit =>
      if negb (ds_shown_once st) &&
         trusted_gate_ok env &&
         caveats_satisfied ScreenBackupExport false ca then
        match BackupObject.encode_recovery_secret rs with
        | None => None
        | Some hex =>
            match format_display_groups hex with
            | None => None
            | Some disp =>
                Some {| ds_phase := DispShowing;
                        ds_shown_once := true;
                        ds_secret_buf := Some (BackupObject.rs_bytes rs);
                        ds_display_buf := Some disp;
                        ds_app_visible := [];
                        ds_clipboard_buf := [];
                        ds_screenshot_buf := [];
                        ds_log_buf := [] |}
            end
        end
      else None
  | _ => None
  end.

Definition disp_exit (st : DisplayState) (_ev : DisplayExitEvent) : DisplayState :=
  {| ds_phase := DispCleared;
     ds_shown_once := ds_shown_once st;
     ds_secret_buf := None;
     ds_display_buf := None;
     ds_app_visible := [];
     ds_clipboard_buf := [];
     ds_screenshot_buf := [];
     ds_log_buf := [] |}.

(*| discharges: R-10-038 |*)
Theorem display_exit_clears_all_buffers : forall st ev,
  let nxt := disp_exit st ev in
  ds_phase nxt = DispCleared /\
  ds_secret_buf nxt = None /\
  ds_display_buf nxt = None /\
  ds_app_visible nxt = [] /\
  ds_clipboard_buf nxt = [] /\
  ds_screenshot_buf nxt = [] /\
  ds_log_buf nxt = [].
Proof.
  intros st ev. repeat split; reflexivity.
Qed.

(*| discharges: R-10-038 |*)
Theorem display_once_blocks_redisplay : forall env ca rs st,
  ds_shown_once st = true ->
  disp_begin env ca rs st = None /\
  forall ev, disp_begin env ca rs (disp_exit st ev) = None.
Proof.
  intros env ca rs st Hshown.
  split.
  - unfold disp_begin. rewrite Hshown. destruct (ds_phase st); reflexivity.
  - intro ev. reflexivity.
Qed.

Theorem display_never_leaks_to_side_channels : forall env ca rs st nxt,
  disp_begin env ca rs st = Some nxt ->
  ds_app_visible nxt = [] /\
  ds_clipboard_buf nxt = [] /\
  ds_screenshot_buf nxt = [] /\
  ds_log_buf nxt = [].
Proof.
  intros env ca rs st nxt H.
  unfold disp_begin in H.
  destruct (ds_phase st); [|discriminate|discriminate].
  destruct (negb (ds_shown_once st) && trusted_gate_ok env &&
            caveats_satisfied ScreenBackupExport false ca); [|discriminate].
  destruct (BackupObject.encode_recovery_secret rs); [|discriminate].
  destruct (format_display_groups _); [|discriminate].
  injection H as H. subst nxt. repeat split; reflexivity.
Qed.

(* =========================================================================
   3. Complete non-truncated quoted receiver-root confirmation on migration
   ========================================================================= *)

Record RootConfirmationScreen : Type := {
  rcs_max_renderable : nat;
  rcs_appraised : bool;
  rcs_channel_id : nat;
  rcs_receiver_gen : nat;
  rcs_receiving_profile : nat;
  rcs_schema_plan : nat;
  rcs_quoted_roots : list nat;
  rcs_displayed_roots : list nat;
  rcs_truncated : bool
}.

Definition prepare_root_confirmation (max_roots : nat)
    (att : MigrationSession.MigrationAttempt) : option RootConfirmationScreen :=
  match MigrationSession.att_phase att,
        MigrationSession.att_accepted_recv_quote att,
        MigrationSession.att_accepted_src_quote att with
  | MigrationSession.PhMutuallyAppraised, Some rq, Some _ =>
      let roots := MigrationSession.ev_roots rq in
      if (0 <? max_roots) &&
         (0 <? length roots) &&
         (length roots <=? max_roots) then
        Some {| rcs_max_renderable := max_roots;
                rcs_appraised := true;
                rcs_channel_id := MigrationSession.ctx_channel (MigrationSession.att_src_ctx att);
                rcs_receiver_gen := MigrationSession.ev_generation rq;
                rcs_receiving_profile := MigrationSession.att_profile_map att;
                rcs_schema_plan := MigrationSession.att_schema_plan att;
                rcs_quoted_roots := roots;
                rcs_displayed_roots := roots;
                rcs_truncated := false |}
      else None
  | _, _, _ => None
  end.

Definition confirm_migration_roots (env : TrustedPathEnv) (ca : CaveatAck)
    (rcs : RootConfirmationScreen) (entered_roots : list nat)
    : option (list nat) :=
  if trusted_gate_ok env &&
     tp_receiver_cred_live env &&
     caveats_satisfied ScreenDeviceMigration false ca &&
     rcs_appraised rcs &&
     negb (rcs_truncated rcs) &&
     (0 <? length (rcs_quoted_roots rcs)) &&
     (length (rcs_quoted_roots rcs) <=? rcs_max_renderable rcs) &&
     ProofSupport.list_eqb Nat.eqb entered_roots (rcs_quoted_roots rcs) &&
     ProofSupport.list_eqb Nat.eqb (rcs_displayed_roots rcs) (rcs_quoted_roots rcs) then
    Some (rcs_quoted_roots rcs)
  else None.

(*| discharges: R-10-040 |*)
Theorem migration_screen_refuses_unappraised : forall max_roots att,
  MigrationSession.att_phase att <> MigrationSession.PhMutuallyAppraised ->
  prepare_root_confirmation max_roots att = None.
Proof.
  intros max_roots att Hneq.
  unfold prepare_root_confirmation.
  destruct (MigrationSession.att_phase att) eqn:Eph;
    try reflexivity.
  contradiction Hneq. reflexivity.
Qed.

(*| discharges: R-10-040 |*)
Theorem migration_screen_refuses_oversize_or_empty_roots : forall max_roots att rq,
  MigrationSession.att_accepted_recv_quote att = Some rq ->
  (MigrationSession.ev_roots rq = [] \/ max_roots < length (MigrationSession.ev_roots rq)) ->
  prepare_root_confirmation max_roots att = None.
Proof.
  intros max_roots att rq Hrq [Hempty | Hbig].
  - unfold prepare_root_confirmation.
    destruct (MigrationSession.att_phase att); try reflexivity.
    rewrite Hrq. destruct (MigrationSession.att_accepted_src_quote att); [|reflexivity].
    rewrite Hempty. simpl. rewrite andb_false_r. reflexivity.
  - unfold prepare_root_confirmation.
    destruct (MigrationSession.att_phase att); try reflexivity.
    rewrite Hrq. destruct (MigrationSession.att_accepted_src_quote att); [|reflexivity].
    assert (Hle : (length (MigrationSession.ev_roots rq) <=? max_roots) = false).
    { apply Nat.leb_gt. exact Hbig. }
    rewrite Hle. rewrite andb_false_r. reflexivity.
Qed.

(*| discharges: R-10-040 |*)
Theorem migration_confirm_refuses_truncated_or_substituted :
  forall env ca rcs entered out,
  confirm_migration_roots env ca rcs entered = Some out ->
  entered = rcs_quoted_roots rcs /\
  out = rcs_quoted_roots rcs /\
  rcs_appraised rcs = true /\
  rcs_truncated rcs = false.
Proof.
  intros env ca rcs entered out H.
  unfold confirm_migration_roots in H.
  destruct (trusted_gate_ok env && tp_receiver_cred_live env &&
            caveats_satisfied ScreenDeviceMigration false ca &&
            rcs_appraised rcs && negb (rcs_truncated rcs) &&
            (0 <? length (rcs_quoted_roots rcs)) &&
            (length (rcs_quoted_roots rcs) <=? rcs_max_renderable rcs) &&
            ProofSupport.list_eqb Nat.eqb entered (rcs_quoted_roots rcs) &&
            ProofSupport.list_eqb Nat.eqb (rcs_displayed_roots rcs) (rcs_quoted_roots rcs))
    eqn:Ec; [|discriminate].
  injection H as H. subst out.
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[[[[[_ _] _] Happ] Hnt] _] _] Heq] _].
  apply negb_true_iff in Hnt.
  apply (ProofSupport.list_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Heq.
  repeat split; assumption || reflexivity.
Qed.

(* =========================================================================
   4. One-use bound consent witnesses
   ========================================================================= *)

Record ScreenConsentWitness : Type := {
  scw_id : nat;
  scw_flow : ScreenFlow;
  scw_trusted_issued : bool;
  scw_epoch : nat;
  scw_profile : nat;
  scw_generation : nat;
  scw_object_or_snapshot : nat;
  scw_destination : nat;
  scw_plan : nat;
  scw_root_set : list nat;
  scw_has_discard : bool;
  scw_consumed : bool
}.

Definition issue_consent_witness (env : TrustedPathEnv) (flow : ScreenFlow)
    (obj_id dst plan : nat) (roots : list nat) (has_discard : bool)
    (ca : CaveatAck) (next_id : nat)
    : option (ScreenConsentWitness * nat) :=
  let mig_roots_ok :=
    match flow with
    | ScreenDeviceMigration => 0 <? length roots
    | _ => true
    end in
  let mig_cred_ok :=
    match flow with
    | ScreenDeviceMigration => tp_receiver_cred_live env
    | _ => true
    end in
  if trusted_gate_ok env &&
     mig_cred_ok &&
     is_backup_or_migration_flow flow &&
     caveats_satisfied flow has_discard ca &&
     mig_roots_ok then
    Some ({| scw_id := next_id;
             scw_flow := flow;
             scw_trusted_issued := true;
             scw_epoch := tp_epoch env;
             scw_profile := tp_active_profile env;
             scw_generation := tp_generation env;
             scw_object_or_snapshot := obj_id;
             scw_destination := dst;
             scw_plan := plan;
             scw_root_set := roots;
             scw_has_discard := has_discard;
             scw_consumed := false |}, S next_id)
  else None.

Definition mark_consumed (w : ScreenConsentWitness) : ScreenConsentWitness :=
  {| scw_id := scw_id w;
     scw_flow := scw_flow w;
     scw_trusted_issued := scw_trusted_issued w;
     scw_epoch := scw_epoch w;
     scw_profile := scw_profile w;
     scw_generation := scw_generation w;
     scw_object_or_snapshot := scw_object_or_snapshot w;
     scw_destination := scw_destination w;
     scw_plan := scw_plan w;
     scw_root_set := scw_root_set w;
     scw_has_discard := scw_has_discard w;
     scw_consumed := true |}.

Definition consume_consent_witness (env : TrustedPathEnv) (expected_flow : ScreenFlow)
    (obj_id dst plan : nat) (roots : list nat) (w : ScreenConsentWitness)
    : option ScreenConsentWitness :=
  if scw_trusted_issued w &&
     negb (scw_consumed w) &&
     trusted_gate_ok env &&
     is_backup_or_migration_flow expected_flow &&
     screen_flow_eqb (scw_flow w) expected_flow &&
     (scw_epoch w =? tp_epoch env) &&
     (scw_profile w =? tp_active_profile env) &&
     (scw_generation w =? tp_generation env) &&
     (scw_object_or_snapshot w =? obj_id) &&
     (scw_destination w =? dst) &&
     (scw_plan w =? plan) &&
     ProofSupport.list_eqb Nat.eqb (scw_root_set w) roots then
    Some (mark_consumed w)
  else None.

(*| discharges: R-10-038, R-17-054a |*)
Theorem no_witness_without_cred_latch_and_caveats :
  forall env flow obj_id dst plan roots has_discard ca next_id w nxt,
  issue_consent_witness env flow obj_id dst plan roots has_discard ca next_id = Some (w, nxt) ->
  tp_unlocked env = true /\
  tp_hw_latch env = true /\
  tp_primary_cred_live env = true /\
  tp_app_originated env = false /\
  is_backup_or_migration_flow flow = true /\
  caveats_satisfied flow has_discard ca = true /\
  scw_trusted_issued w = true /\
  scw_consumed w = false.
Proof.
  intros env flow obj_id dst plan roots has_discard ca next_id w nxt H.
  unfold issue_consent_witness in H.
  match type of H with (if ?c then _ else _) = _ => destruct c eqn:Ec end;
    [|discriminate].
  injection H as Hw Hn. subst w.
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[Hgate _] Hflow] Hcav] _].
  unfold trusted_gate_ok in Hgate.
  repeat rewrite andb_true_iff in Hgate.
  destruct Hgate as [[[Hun Hlat] Hcred] Hnapp].
  apply negb_true_iff in Hnapp.
  repeat split; assumption || reflexivity.
Qed.

(*| discharges: R-10-038 |*)
Theorem witness_cannot_be_replayed :
  forall env flow obj_id dst plan roots w w',
  consume_consent_witness env flow obj_id dst plan roots w = Some w' ->
  consume_consent_witness env flow obj_id dst plan roots w' = None.
Proof.
  intros env flow obj_id dst plan roots w w' H.
  unfold consume_consent_witness in *.
  match type of H with (if ?c then _ else _) = _ => destruct c eqn:Ec end;
    [|discriminate].
  injection H as H. subst w'.
  simpl. rewrite andb_false_r. reflexivity.
Qed.

(*| discharges: R-10-038 |*)
Theorem witness_cannot_be_forged_by_app :
  forall env flow obj_id dst plan roots w,
  scw_trusted_issued w = false ->
  consume_consent_witness env flow obj_id dst plan roots w = None.
Proof.
  intros env flow obj_id dst plan roots w Hf.
  unfold consume_consent_witness. rewrite Hf. reflexivity.
Qed.

(*| discharges: R-10-038 |*)
Theorem witness_expires_on_lock_or_restart :
  forall env env' flow obj_id dst plan roots w,
  tp_epoch env' <> scw_epoch w ->
  consume_consent_witness env flow obj_id dst plan roots w = Some (mark_consumed w) ->
  consume_consent_witness env' flow obj_id dst plan roots w = None /\
  consume_consent_witness (advance_epoch env) flow obj_id dst plan roots w = None.
Proof.
  intros env env' flow obj_id dst plan roots w Hneq _.
  split.
  - unfold consume_consent_witness.
    assert (He : (scw_epoch w =? tp_epoch env') = false).
    { apply Nat.eqb_neq. intro H. apply Hneq. symmetry. exact H. }
    rewrite He. repeat rewrite andb_false_r. reflexivity.
  - unfold consume_consent_witness, advance_epoch. simpl.
    repeat rewrite andb_false_r. reflexivity.
Qed.

(*| discharges: R-10-038, R-10-040 |*)
Theorem witness_expires_on_binding_change :
  forall env flow obj_id dst plan roots w,
  (scw_profile w <> tp_active_profile env \/
   scw_generation w <> tp_generation env \/
   scw_flow w <> flow \/
   scw_object_or_snapshot w <> obj_id \/
   scw_destination w <> dst \/
   scw_plan w <> plan \/
   scw_root_set w <> roots) ->
  consume_consent_witness env flow obj_id dst plan roots w = None.
Proof.
  intros env flow obj_id dst plan roots w
         [Hp | [Hg | [Hf | [Ho | [Hd | [Hpl | Hr]]]]]];
    unfold consume_consent_witness.
  - assert (E : (scw_profile w =? tp_active_profile env) = false)
      by (apply Nat.eqb_neq; exact Hp).
    rewrite E. repeat rewrite andb_false_r. reflexivity.
  - assert (E : (scw_generation w =? tp_generation env) = false)
      by (apply Nat.eqb_neq; exact Hg).
    rewrite E. repeat rewrite andb_false_r. reflexivity.
  - destruct (screen_flow_eqb (scw_flow w) flow) eqn:Ef.
    + apply screen_flow_eqb_sound in Ef. contradiction.
    + repeat rewrite andb_false_r. reflexivity.
  - assert (E : (scw_object_or_snapshot w =? obj_id) = false)
      by (apply Nat.eqb_neq; exact Ho).
    rewrite E. repeat rewrite andb_false_r. reflexivity.
  - assert (E : (scw_destination w =? dst) = false)
      by (apply Nat.eqb_neq; exact Hd).
    rewrite E. repeat rewrite andb_false_r. reflexivity.
  - assert (E : (scw_plan w =? plan) = false)
      by (apply Nat.eqb_neq; exact Hpl).
    rewrite E. repeat rewrite andb_false_r. reflexivity.
  - destruct (ProofSupport.list_eqb Nat.eqb (scw_root_set w) roots) eqn:Er.
    + apply (ProofSupport.list_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Er.
      contradiction.
    + rewrite andb_false_r. reflexivity.
Qed.

(* =========================================================================
   5. Closed top-level inhabitation witnesses for every Record (R-05-166)
   ========================================================================= *)

Definition ex_env : TrustedPathEnv :=
  {| tp_unlocked := true;
     tp_hw_latch := true;
     tp_primary_cred_live := true;
     tp_receiver_cred_live := true;
     tp_app_originated := false;
     tp_epoch := 1;
     tp_active_profile := 1;
     tp_generation := 7 |}.

Definition ex_caveats_all : CaveatAck :=
  {| ca_off_device_trade := true;
     ca_surrendered_freshness := true;
     ca_discard_loss := true;
     ca_migration_roots := true;
     ca_not_rollback := true |}.

Definition ex_caveats_export : CaveatAck :=
  {| ca_off_device_trade := true;
     ca_surrendered_freshness := false;
     ca_discard_loss := false;
     ca_migration_roots := false;
     ca_not_rollback := true |}.

Definition ex_caveats_restore_nodiscard : CaveatAck :=
  {| ca_off_device_trade := false;
     ca_surrendered_freshness := true;
     ca_discard_loss := false;
     ca_migration_roots := false;
     ca_not_rollback := true |}.

Definition ex_caveats_restore_discard : CaveatAck :=
  {| ca_off_device_trade := false;
     ca_surrendered_freshness := true;
     ca_discard_loss := true;
     ca_migration_roots := false;
     ca_not_rollback := true |}.

Definition ex_caveats_migration : CaveatAck :=
  {| ca_off_device_trade := false;
     ca_surrendered_freshness := false;
     ca_discard_loss := false;
     ca_migration_roots := true;
     ca_not_rollback := true |}.

Definition witness_CaveatAck : CaveatAck := ex_caveats_all.
Definition witness_TrustedPathEnv : TrustedPathEnv := ex_env.
Definition witness_DisplayState : DisplayState := disp_init.
Definition witness_RootConfirmationScreen : RootConfirmationScreen :=
  {| rcs_max_renderable := 4;
     rcs_appraised := true;
     rcs_channel_id := 1;
     rcs_receiver_gen := 7;
     rcs_receiving_profile := 1;
     rcs_schema_plan := 1;
     rcs_quoted_roots := [3; 4];
     rcs_displayed_roots := [3; 4];
     rcs_truncated := false |}.
Definition witness_ScreenConsentWitness : ScreenConsentWitness :=
  {| scw_id := 1;
     scw_flow := ScreenBackupExport;
     scw_trusted_issued := true;
     scw_epoch := 1;
     scw_profile := 1;
     scw_generation := 7;
     scw_object_or_snapshot := 42;
     scw_destination := 99;
     scw_plan := 1;
     scw_root_set := [];
     scw_has_discard := false;
     scw_consumed := false |}.

(* =========================================================================
   6. Inhabited positive traces and explicit refutation witnesses (R-05-165,
      R-05-166)
   ========================================================================= *)

(* Positive trace 1: Backup export screen with R-17-054a ack, one-time
   display of leading-zero RecoverySecret-v1, exit completion, and
   one-use witness consumption. *)
(*| discharges: R-05-165, R-05-166, R-10-038, R-17-054a |*)
Example inhabited_export_screen_trace :
  exists w nxt_id disp_st disp_bytes,
    issue_consent_witness ex_env ScreenBackupExport 42 99 1 [] false ex_caveats_export 1
      = Some (w, nxt_id) /\
    disp_begin ex_env ex_caveats_export BackupObject.witness_RecoverySecret disp_init
      = Some disp_st /\
    ds_display_buf disp_st = Some disp_bytes /\
    ProofSupport.count_of disp_bytes = 79 /\
    ds_phase (disp_exit disp_st ExitComplete) = DispCleared /\
    ds_secret_buf (disp_exit disp_st ExitComplete) = None /\
    ds_display_buf (disp_exit disp_st ExitComplete) = None /\
    disp_begin ex_env ex_caveats_export BackupObject.witness_RecoverySecret
      (disp_exit disp_st ExitComplete) = None /\
    consume_consent_witness ex_env ScreenBackupExport 42 99 1 [] w
      = Some (mark_consumed w).
Proof.
  eexists. eexists. eexists. eexists.
  repeat split; vm_compute; reflexivity.
Qed.

(* Positive trace 2: User-data restore screen (both ordinary and explicit discard). *)
(*| discharges: R-05-165, R-05-166, R-10-038, R-10-039 |*)
Example inhabited_restore_and_discard_screen_traces :
  (exists w1 nxt1,
     issue_consent_witness ex_env ScreenUserRestore 77 1 10 [] false ex_caveats_restore_nodiscard 2
       = Some (w1, nxt1) /\
     consume_consent_witness ex_env ScreenUserRestore 77 1 10 [] w1
       = Some (mark_consumed w1)) /\
  (exists w2 nxt2,
     issue_consent_witness ex_env ScreenUserRestore 78 1 11 [] true ex_caveats_restore_discard 3
       = Some (w2, nxt2) /\
     consume_consent_witness ex_env ScreenUserRestore 78 1 11 [] w2
       = Some (mark_consumed w2)).
Proof.
  split.
  - destruct (issue_consent_witness ex_env ScreenUserRestore 77 1 10 [] false ex_caveats_restore_nodiscard 2)
      as [[w1 nxt1]|] eqn:E1; [|vm_compute in E1; discriminate].
    exists w1, nxt1. vm_compute in E1. injection E1 as Hw Hn. subst.
    split; vm_compute; reflexivity.
  - destruct (issue_consent_witness ex_env ScreenUserRestore 78 1 11 [] true ex_caveats_restore_discard 3)
      as [[w2 nxt2]|] eqn:E2; [|vm_compute in E2; discriminate].
    exists w2, nxt2. vm_compute in E2. injection E2 as Hw Hn. subst.
    split; vm_compute; reflexivity.
Qed.

(* Positive trace 3: Device migration screen over MigrationSession's mutually
   appraised state, showing complete non-truncated quoted roots [3; 4]. *)
(*| discharges: R-05-165, R-05-166, R-10-040 |*)
Example inhabited_migration_screen_trace :
  exists rcs roots w nxt,
    prepare_root_confirmation 4 MigrationSession.mig_att_mut_app = Some rcs /\
    confirm_migration_roots ex_env ex_caveats_migration rcs [3; 4] = Some roots /\
    issue_consent_witness ex_env ScreenDeviceMigration 7 1 1 roots false ex_caveats_migration 4
      = Some (w, nxt) /\
    consume_consent_witness ex_env ScreenDeviceMigration 7 1 1 roots w
      = Some (mark_consumed w).
Proof.
  destruct (prepare_root_confirmation 4 MigrationSession.mig_att_mut_app)
    as [rcs|] eqn:Er; [|vm_compute in Er; discriminate].
  vm_compute in Er. injection Er as Er. subst rcs.
  eexists. exists [3; 4].
  destruct (issue_consent_witness ex_env ScreenDeviceMigration 7 1 1 [3; 4] false ex_caveats_migration 4)
    as [[w nxt]|] eqn:Ew; [|vm_compute in Ew; discriminate].
  exists w, nxt. vm_compute in Ew. injection Ew as Hw Hn. subst.
  repeat split; vm_compute; reflexivity.
Qed.

(* Refutation witnesses for spoof, replay, cancel, lock, fault, restart,
   profile/gen/plan/dest/obj change, truncation, missing caveats, rollback,
   and non-canonical recovery secret entry. *)
(*| discharges: R-05-166, R-10-038, R-10-040, R-17-054a |*)
Example screen_refutation_witnesses :
  let app_env := {| tp_unlocked := true; tp_hw_latch := true;
                    tp_primary_cred_live := true; tp_receiver_cred_live := true;
                    tp_app_originated := true; tp_epoch := 1;
                    tp_active_profile := 1; tp_generation := 7 |} in
  let forged_w := {| scw_id := 1; scw_flow := ScreenBackupExport;
                     scw_trusted_issued := false; scw_epoch := 1;
                     scw_profile := 1; scw_generation := 7;
                     scw_object_or_snapshot := 42; scw_destination := 99;
                     scw_plan := 1; scw_root_set := [];
                     scw_has_discard := false; scw_consumed := false |} in
  let no_r17_cav := {| ca_off_device_trade := false; ca_surrendered_freshness := true;
                       ca_discard_loss := true; ca_migration_roots := true;
                       ca_not_rollback := true |} in
  let no_discard_cav := {| ca_off_device_trade := true; ca_surrendered_freshness := true;
                           ca_discard_loss := false; ca_migration_roots := true;
                           ca_not_rollback := true |} in
  let no_fresh_cav := {| ca_off_device_trade := true; ca_surrendered_freshness := false;
                         ca_discard_loss := true; ca_migration_roots := true;
                         ca_not_rollback := true |} in
  (* 1. App spoof & forged witness refused *)
  issue_consent_witness app_env ScreenBackupExport 42 99 1 [] false ex_caveats_export 1 = None /\
  consume_consent_witness ex_env ScreenBackupExport 42 99 1 [] forged_w = None /\
  (* 2. Replay refused *)
  consume_consent_witness ex_env ScreenBackupExport 42 99 1 []
    (mark_consumed witness_ScreenConsentWitness) = None /\
  (* 3. Lock / restart expires witness *)
  consume_consent_witness (advance_epoch ex_env) ScreenBackupExport 42 99 1 []
    witness_ScreenConsentWitness = None /\
  (* 4. Profile, generation, destination, object, and plan changes expire witness *)
  consume_consent_witness
    {| tp_unlocked := true; tp_hw_latch := true; tp_primary_cred_live := true;
       tp_receiver_cred_live := true; tp_app_originated := false; tp_epoch := 1;
       tp_active_profile := 2; tp_generation := 7 |}
    ScreenBackupExport 42 99 1 [] witness_ScreenConsentWitness = None /\
  consume_consent_witness
    {| tp_unlocked := true; tp_hw_latch := true; tp_primary_cred_live := true;
       tp_receiver_cred_live := true; tp_app_originated := false; tp_epoch := 1;
       tp_active_profile := 1; tp_generation := 8 |}
    ScreenBackupExport 42 99 1 [] witness_ScreenConsentWitness = None /\
  consume_consent_witness ex_env ScreenBackupExport 43 99 1 [] witness_ScreenConsentWitness = None /\
  consume_consent_witness ex_env ScreenBackupExport 42 100 1 [] witness_ScreenConsentWitness = None /\
  consume_consent_witness ex_env ScreenBackupExport 42 99 2 [] witness_ScreenConsentWitness = None /\
  (* 5. Missing caveats & rollback flow refused *)
  issue_consent_witness ex_env ScreenBackupExport 42 99 1 [] false no_r17_cav 1 = None /\
  issue_consent_witness ex_env ScreenUserRestore 77 1 10 [] false no_fresh_cav 1 = None /\
  issue_consent_witness ex_env ScreenUserRestore 78 1 11 [] true no_discard_cav 1 = None /\
  issue_consent_witness ex_env ScreenSystemRollback 1 1 1 [] false ex_caveats_all 1 = None /\
  (* 6. Cancel / Lock / Fault all clear buffers and keep side channels empty *)
  (match disp_begin ex_env ex_caveats_export BackupObject.witness_RecoverySecret disp_init with
   | None => False
   | Some dst =>
       ds_secret_buf (disp_exit dst ExitCancel) = None /\
       ds_display_buf (disp_exit dst ExitCancel) = None /\
       ds_secret_buf (disp_exit dst ExitLock) = None /\
       ds_display_buf (disp_exit dst ExitLock) = None /\
       ds_secret_buf (disp_exit dst ExitFault) = None /\
       ds_display_buf (disp_exit dst ExitFault) = None /\
       ds_app_visible dst = [] /\ ds_clipboard_buf dst = [] /\
       ds_screenshot_buf dst = [] /\ ds_log_buf dst = []
   end) /\
  (* 7. Unappraised migration peer, oversize/truncated/substituted roots refused *)
  prepare_root_confirmation 4 MigrationSession.mig_att_opened = None /\
  prepare_root_confirmation 4 MigrationSession.mig_att_recv_app = None /\
  prepare_root_confirmation 1 MigrationSession.mig_att_mut_app = None /\
  confirm_migration_roots ex_env ex_caveats_migration witness_RootConfirmationScreen [3] = None /\
  confirm_migration_roots ex_env ex_caveats_migration witness_RootConfirmationScreen [3; 9] = None /\
  (* 8. Non-canonical recovery-secret entry refused *)
  BackupObject.decode_recovery_secret (ProofSupport.repeat_of 64 97) = None /\
  BackupObject.decode_recovery_secret (ProofSupport.repeat_of 63 48) = None.
Proof.
  vm_compute. repeat split; reflexivity.
Qed.
