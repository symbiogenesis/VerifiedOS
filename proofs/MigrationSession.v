(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MigrationSession.v

   Symbolic mutual-attestation reference model (`MigrationSession`) and
   agreement proofs for `MutualMigrationTLS-v1` (see
   [backup-migration.md](../docs/implementation/contracts/backup-migration.md#6-selected-device-migration-session-and-reference-model)),
   reusing [CredentialHandles.v](CredentialHandles.v#authorize_and_charge) for
   R-12-015a's bounded protocol-credential operations and
   [ProofSupport.v](ProofSupport.v#list_eqb) for constructive sequence
   comparisons.

   Scope and obligations (R-10-040, R-12-015a, R-12-015c):
   - Models all eight `MigrationSession` lifecycle events (`Open`, `Quote`,
     `Appraise`, `ConfirmRoots`, `Transfer`, `PrepareRestore`, `Publish`,
     `Close`) and the three distinct roles (`MigrationSource`,
     `MigrationReceiver`, `BackupKeyEnrollment`).
   - Enforces protected local context readings (no caller-supplied exporter,
     measurement, reference manifest, or root set), fixed mutual appraisal
     order (receiver quoted and appraised first; source quote binds accepted
     receiver quote identity), dual primary-credential witnesses, source-side
     confirmation of the complete quoted receiver root set, volatile-only
     transfer buffers (zero retained backup objects or key capsules written to
     storage), and atomic `Publish`.
   - Proves `BackupKeyEnrollment` can wrap a recovery key for an enrolled
     recipient (`enrollment_key_wrap_agreement`) and can never authorize region
     transfer (`enrollment_role_cannot_authorize_transfer`).
   - Proves conditional mutual session-agreement theorems
     (`migration_transfer_agreement`, `migration_publish_agreement`,
     `enrollment_key_wrap_agreement`) under explicit named premises
     (`ExporterSecurity`, `EvidenceAuthenticity`, `LocalContextIntegrity`,
     `RootSetFaithfulness`, `HonestTrustedPath`, `UncompromisedKeys`) with
     zero axioms (R-05-163, R-05-164).
   - Provides jointly inhabited positive traces and distinguishing refusal /
     relay / broken-premise witnesses for every section 6 case
     (R-05-165, R-05-166).
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-10-040 R-12-015a R-12-015c
   SHA256: 6cade5a5181d38325831f569c6784bc98b684dc5e420fc82dee81a097da4c1d4
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Bool Arith Lia.
Require ProofSupport CredentialHandles.
Import ListNotations.

(* =========================================================================
   1. Roles, modes, contexts, and composition-bounded profile
   ========================================================================= *)

Inductive MigrationRole : Type :=
| MigrationSource
| MigrationReceiver
| BackupKeyEnrollment.

Definition role_code (r : MigrationRole) : nat :=
  match r with
  | MigrationSource => 1
  | MigrationReceiver => 2
  | BackupKeyEnrollment => 3
  end.

Definition role_eqb (a b : MigrationRole) : bool :=
  match a, b with
  | MigrationSource, MigrationSource => true
  | MigrationReceiver, MigrationReceiver => true
  | BackupKeyEnrollment, BackupKeyEnrollment => true
  | _, _ => false
  end.

Lemma role_eqb_refl : forall r, role_eqb r r = true.
Proof. intros [| |]; reflexivity. Qed.

Lemma role_eqb_sound : forall a b, role_eqb a b = true -> a = b.
Proof. intros [| |] [| |] H; try discriminate H; reflexivity. Qed.

Inductive SessionMode : Type :=
| ModeMigration
| ModeEnrollment.

Definition mode_eqb (a b : SessionMode) : bool :=
  match a, b with
  | ModeMigration, ModeMigration => true
  | ModeEnrollment, ModeEnrollment => true
  | _, _ => false
  end.

Definition expected_recv_role (m : SessionMode) : MigrationRole :=
  match m with
  | ModeMigration => MigrationReceiver
  | ModeEnrollment => BackupKeyEnrollment
  end.

Record ProtectedContext : Type := {
  ctx_id : nat;
  ctx_channel : nat;    (* Cryptographic TLS 1.3 connection identity. *)
  ctx_unit : nat;       (* Ghost identity of the actual traffic-key holder. *)
  ctx_role : MigrationRole;
  ctx_principal : nat;
  ctx_origin : nat;
  ctx_exporter : nat;   (* Protected local RFC 9266 exporter value. *)
  ctx_handshake_complete : bool;
  ctx_server_authenticated : bool;
  ctx_early_data : bool;
  ctx_resumed : bool;
  ctx_config_fixed : bool
}.

Definition context_usable (c : ProtectedContext) : bool :=
  ctx_handshake_complete c &&
  ctx_server_authenticated c &&
  negb (ctx_early_data c) &&
  negb (ctx_resumed c) &&
  ctx_config_fixed c.

Theorem context_requires_full_non_resumed_fixed_tls : forall c,
  context_usable c = true ->
  ctx_handshake_complete c = true /\
  ctx_server_authenticated c = true /\
  ctx_early_data c = false /\
  ctx_resumed c = false /\
  ctx_config_fixed c = true.
Proof.
  intros c H. unfold context_usable in H. repeat rewrite andb_true_iff in H.
  destruct H as [[[[Hc Hs] He] Hr] Hf].
  apply negb_true_iff in He. apply negb_true_iff in Hr.
  repeat split; assumption.
Qed.

Record MigrationProfile : Type := {
  mp_domain : nat;
  mp_attest_op : nat;
  mp_wrap_op : nat;
  mp_request_bound : nat;
  mp_evidence_bound : nat;
  mp_manifest_bound : nat;
  mp_object_bound : nat;
  mp_volatile_cap : nat;
  mp_max_roots : nat
}.

Definition profile_bounded (p : MigrationProfile) : bool :=
  (0 <? mp_domain p) &&
  (0 <? mp_attest_op p) &&
  (0 <? mp_wrap_op p) &&
  (negb (mp_attest_op p =? mp_wrap_op p)) &&
  (0 <? mp_request_bound p) &&
  (0 <? mp_evidence_bound p) &&
  (0 <? mp_manifest_bound p) &&
  (0 <? mp_object_bound p) &&
  (0 <? mp_volatile_cap p) &&
  (0 <? mp_max_roots p).

(* =========================================================================
   2. Protected local runtime, challenges, quotes, and broker issuance
   ========================================================================= *)

Record LocalRuntime : Type := {
  rt_measured_gen : nat -> option nat;
  rt_ref_manifest : nat -> option nat;
  rt_roots : nat -> option (list nat);
  rt_enrolled_recipient : nat -> nat -> option nat
}.

Record MigrationChallenge : Type := {
  ch_nonce : nat;
  ch_origin : nat;
  ch_domain : nat;
  ch_challenger_role : MigrationRole;
  ch_target_role : MigrationRole;
  ch_source_profile : nat;
  ch_profile_map : nat;
  ch_schema_plan : nat;
  ch_unit_scope : bool
}.

Definition challenge_eqb (a b : MigrationChallenge) : bool :=
  (ch_nonce a =? ch_nonce b) &&
  (ch_origin a =? ch_origin b) &&
  (ch_domain a =? ch_domain b) &&
  role_eqb (ch_challenger_role a) (ch_challenger_role b) &&
  role_eqb (ch_target_role a) (ch_target_role b) &&
  (ch_source_profile a =? ch_source_profile b) &&
  (ch_profile_map a =? ch_profile_map b) &&
  (ch_schema_plan a =? ch_schema_plan b) &&
  Bool.eqb (ch_unit_scope a) (ch_unit_scope b).

Lemma challenge_eqb_refl : forall c, challenge_eqb c c = true.
Proof.
  intros c. unfold challenge_eqb.
  rewrite !Nat.eqb_refl, !role_eqb_refl, Bool.eqb_reflx. reflexivity.
Qed.

Lemma challenge_eqb_sound : forall a b, challenge_eqb a b = true -> a = b.
Proof.
  intros [n1 o1 d1 cr1 tr1 sp1 pm1 pl1 u1] [n2 o2 d2 cr2 tr2 sp2 pm2 pl2 u2] H.
  unfold challenge_eqb in H. cbn in H.
  repeat rewrite andb_true_iff in H.
  destruct H as [[[[[[[[Hn Ho] Hd] Hcr] Htr] Hsp] Hpm] Hpl] Hu].
  apply Nat.eqb_eq in Hn. apply Nat.eqb_eq in Ho. apply Nat.eqb_eq in Hd.
  apply role_eqb_sound in Hcr. apply role_eqb_sound in Htr.
  apply Nat.eqb_eq in Hsp. apply Nat.eqb_eq in Hpm. apply Nat.eqb_eq in Hpl.
  apply Bool.eqb_prop in Hu. subst. reflexivity.
Qed.

Record MigrationQuote : Type := {
  ev_id : nat;
  ev_role : MigrationRole;
  ev_generation : nat;
  ev_ref_manifest : nat;
  ev_exporter : nat;
  ev_challenge : MigrationChallenge;
  ev_principal : nat;
  ev_roots : list nat;
  ev_bound_receiver_quote : option nat;
  ev_enrolled_recipient : option nat
}.

Definition quote_eqb (a b : MigrationQuote) : bool :=
  (ev_id a =? ev_id b) &&
  role_eqb (ev_role a) (ev_role b) &&
  (ev_generation a =? ev_generation b) &&
  (ev_ref_manifest a =? ev_ref_manifest b) &&
  (ev_exporter a =? ev_exporter b) &&
  challenge_eqb (ev_challenge a) (ev_challenge b) &&
  (ev_principal a =? ev_principal b) &&
  ProofSupport.list_eqb Nat.eqb (ev_roots a) (ev_roots b) &&
  ProofSupport.option_eqb Nat.eqb (ev_bound_receiver_quote a) (ev_bound_receiver_quote b) &&
  ProofSupport.option_eqb Nat.eqb (ev_enrolled_recipient a) (ev_enrolled_recipient b).

Lemma quote_eqb_refl : forall q, quote_eqb q q = true.
Proof.
  intros q. unfold quote_eqb.
  rewrite !Nat.eqb_refl, role_eqb_refl, challenge_eqb_refl.
  rewrite (ProofSupport.list_eqb_refl nat Nat.eqb ProofSupport.nat_eqb_refl).
  rewrite !(ProofSupport.option_eqb_refl nat Nat.eqb ProofSupport.nat_eqb_refl).
  reflexivity.
Qed.

Lemma quote_eqb_sound : forall a b, quote_eqb a b = true -> a = b.
Proof.
  intros [i1 r1 g1 m1 e1 c1 p1 rt1 b1 er1] [i2 r2 g2 m2 e2 c2 p2 rt2 b2 er2] H.
  unfold quote_eqb in H. cbn in H.
  repeat rewrite andb_true_iff in H.
  destruct H as [[[[[[[[[Hi Hr] Hg] Hm] He] Hc] Hp] Hrt] Hb] Her].
  apply Nat.eqb_eq in Hi. apply role_eqb_sound in Hr.
  apply Nat.eqb_eq in Hg. apply Nat.eqb_eq in Hm.
  apply Nat.eqb_eq in He. apply challenge_eqb_sound in Hc.
  apply Nat.eqb_eq in Hp.
  apply (ProofSupport.list_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hrt.
  apply (ProofSupport.option_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hb.
  apply (ProofSupport.option_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Her.
  subst. reflexivity.
Qed.

Record MigrationIssuance : Type := {
  mi_quote : MigrationQuote;
  mi_issuer_ctx : ProtectedContext
}.

Definition role_operation (p : MigrationProfile) (r : MigrationRole) : nat :=
  match r with
  | BackupKeyEnrollment => mp_wrap_op p
  | MigrationSource | MigrationReceiver => mp_attest_op p
  end.

Definition local_request_matches (p : MigrationProfile) (c : ProtectedContext)
    (q : MigrationChallenge) (r : CredentialHandles.ClientRequest) : bool :=
  (CredentialHandles.request_role r =? role_code (ctx_role c)) &&
  (CredentialHandles.request_principal r =? ctx_principal c) &&
  (CredentialHandles.request_scope r =? if ch_unit_scope q then 1 else 0) &&
  (CredentialHandles.request_operation r =? role_operation p (ctx_role c)) &&
  (CredentialHandles.request_transcript r =? mp_domain p) &&
  (length (CredentialHandles.request_bytes r) <=? mp_request_bound p) &&
  (ch_origin q =? ctx_origin c) &&
  (ch_domain q =? mp_domain p) &&
  role_eqb (ch_target_role q) (ctx_role c) &&
  (0 <? ch_nonce q).

(* Protected local quote issuance: reads exporter, measured generation,
   reference manifest, enrolled roots, and recipient identity exclusively
   from the local ProtectedContext and LocalRuntime; never accepts a
   caller-supplied exporter or root list. Source quotes must bind an accepted
   receiver quote identity (`Some recv_qid`). *)
Definition quote_local (p : MigrationProfile) (cp : CredentialHandles.CredentialPolicy)
    (cred : CredentialHandles.Credential) (srv : CredentialHandles.ServerState)
    (req : CredentialHandles.ClientRequest) (c : ProtectedContext) (qid : nat)
    (chal : MigrationChallenge) (rt : LocalRuntime) (bound_recv_q : option nat)
    : option (MigrationIssuance * CredentialHandles.ServerState) :=
  if profile_bounded p && context_usable c && (0 <? qid) &&
     local_request_matches p c chal req then
    match rt_measured_gen rt (ctx_unit c), rt_ref_manifest rt (ctx_unit c) with
    | Some gen, Some ref_m =>
      let role_ok :=
        match ctx_role c, bound_recv_q with
        | MigrationReceiver, None => true
        | MigrationSource, Some _ => true
        | BackupKeyEnrollment, None => true
        | _, _ => false
        end in
      if negb role_ok then None else
      match ctx_role c with
      | MigrationSource =>
        match CredentialHandles.authorize_and_charge cp cred srv req with
        | None => None
        | Some next_srv =>
          Some ({| mi_quote := {| ev_id := qid; ev_role := MigrationSource;
                                  ev_generation := gen; ev_ref_manifest := ref_m;
                                  ev_exporter := ctx_exporter c; ev_challenge := chal;
                                  ev_principal := ctx_principal c; ev_roots := [];
                                  ev_bound_receiver_quote := bound_recv_q;
                                  ev_enrolled_recipient := None |};
                   mi_issuer_ctx := c |}, next_srv)
        end
      | MigrationReceiver =>
        match rt_roots rt (ctx_unit c) with
        | None => None
        | Some roots =>
          if (0 <? length roots) && (length roots <=? mp_max_roots p) then
            match CredentialHandles.authorize_and_charge cp cred srv req with
            | None => None
            | Some next_srv =>
              Some ({| mi_quote := {| ev_id := qid; ev_role := MigrationReceiver;
                                      ev_generation := gen; ev_ref_manifest := ref_m;
                                      ev_exporter := ctx_exporter c; ev_challenge := chal;
                                      ev_principal := ctx_principal c; ev_roots := roots;
                                      ev_bound_receiver_quote := None;
                                      ev_enrolled_recipient := None |};
                       mi_issuer_ctx := c |}, next_srv)
            end
          else None
        end
      | BackupKeyEnrollment =>
        match rt_roots rt (ctx_unit c), rt_enrolled_recipient rt (ctx_origin c) (ctx_unit c) with
        | Some roots, Some rec_id =>
          if (0 <? length roots) && (length roots <=? mp_max_roots p) then
            match CredentialHandles.authorize_and_charge cp cred srv req with
            | None => None
            | Some next_srv =>
              Some ({| mi_quote := {| ev_id := qid; ev_role := BackupKeyEnrollment;
                                      ev_generation := gen; ev_ref_manifest := ref_m;
                                      ev_exporter := ctx_exporter c; ev_challenge := chal;
                                      ev_principal := ctx_principal c; ev_roots := roots;
                                      ev_bound_receiver_quote := None;
                                      ev_enrolled_recipient := Some rec_id |};
                       mi_issuer_ctx := c |}, next_srv)
            end
          else None
        | _, _ => None
        end
      end
    | _, _ => None
    end
  else None.

Theorem local_quote_reads_context_and_charges_credential :
  forall p cp cred srv req c qid chal rt bound iss next_srv,
  quote_local p cp cred srv req c qid chal rt bound = Some (iss, next_srv) ->
  mi_issuer_ctx iss = c /\
  ev_exporter (mi_quote iss) = ctx_exporter c /\
  rt_measured_gen rt (ctx_unit c) = Some (ev_generation (mi_quote iss)) /\
  rt_ref_manifest rt (ctx_unit c) = Some (ev_ref_manifest (mi_quote iss)) /\
  CredentialHandles.authorize_and_charge cp cred srv req = Some next_srv.
Proof.
  intros p cp cred srv req c qid chal rt bound iss next_srv H.
  unfold quote_local in H.
  destruct (profile_bounded p && context_usable c && (0 <? qid) &&
            local_request_matches p c chal req); [|discriminate].
  destruct (rt_measured_gen rt (ctx_unit c)) as [gen|] eqn:Hg; [|discriminate].
  destruct (rt_ref_manifest rt (ctx_unit c)) as [ref_m|] eqn:Hm; [|discriminate].
  destruct (ctx_role c) eqn:Er; destruct bound as [bid|];
    try (cbn in H; discriminate H).
  - destruct (CredentialHandles.authorize_and_charge cp cred srv req) as [ns|] eqn:Ha;
      [|discriminate].
    inversion H; subst. repeat split; assumption || reflexivity.
  - destruct (rt_roots rt (ctx_unit c)) as [roots|]; [|discriminate].
    destruct ((0 <? length roots) && (length roots <=? mp_max_roots p)); [|discriminate].
    destruct (CredentialHandles.authorize_and_charge cp cred srv req) as [ns|] eqn:Ha;
      [|discriminate].
    inversion H; subst. repeat split; assumption || reflexivity.
  - destruct (rt_roots rt (ctx_unit c)) as [roots|]; [|discriminate].
    destruct (rt_enrolled_recipient rt (ctx_origin c) (ctx_unit c)) as [rec_id|];
      [|discriminate].
    destruct ((0 <? length roots) && (length roots <=? mp_max_roots p)); [|discriminate].
    destruct (CredentialHandles.authorize_and_charge cp cred srv req) as [ns|] eqn:Ha;
      [|discriminate].
    inversion H; subst. repeat split; assumption || reflexivity.
Qed.

(* =========================================================================
   3. MigrationSession state machine (8 events + recovery-key wrapping)
   ========================================================================= *)

Record MigrationPolicy : Type := {
  pol_approved_gen : nat -> bool;
  pol_approved_manifest : nat -> bool;
  pol_required_principal : nat;
  pol_unit_scope : bool;
  pol_expected_enrolled_recipient : option nat;
  pol_expected_unit : nat
}.

Record ConsentWitness : Type := {
  cw_channel_id : nat;
  cw_roots : list nat;
  cw_source_profile : nat;
  cw_profile_map : nat;
  cw_schema_plan : nat;
  cw_source_cred : bool;
  cw_receiver_cred : bool
}.

Record VolatileBuffer : Type := {
  vb_object_bytes : nat;
  vb_has_object : bool;
  vb_has_object_key : bool
}.

Definition empty_volatile : VolatileBuffer :=
  {| vb_object_bytes := 0; vb_has_object := false; vb_has_object_key := false |}.

Record StorageState : Type := {
  st_current_profile_gen : nat;
  st_current_regions_digest : nat;
  st_unreachable_staging_digest : option nat;
  st_retained_backup_objects : nat;
  st_retained_key_capsules : nat;
  st_fresh_epoch_current : bool
}.

Definition clear_staging (s : StorageState) : StorageState :=
  {| st_current_profile_gen := st_current_profile_gen s;
     st_current_regions_digest := st_current_regions_digest s;
     st_unreachable_staging_digest := None;
     st_retained_backup_objects := st_retained_backup_objects s;
     st_retained_key_capsules := st_retained_key_capsules s;
     st_fresh_epoch_current := st_fresh_epoch_current s |}.

Record WrappedKeyHandle : Type := {
  wk_recipient : nat;
  wk_object_id : nat;
  wk_use_restore_only : bool;
  wk_locally_sealed : bool
}.

Record RestorePayload : Type := {
  rp_manifest_auth : bool;
  rp_source_profile : nat;
  rp_profile_map : nat;
  rp_schema_plan : nat;
  rp_all_schemas_decided : bool;
  rp_chunks_verified : bool;
  rp_coverage_complete : bool;
  rp_staged_digest : nat
}.

Inductive AttemptPhase : Type :=
| PhIdle
| PhOpened
| PhReceiverAppraised
| PhMutuallyAppraised
| PhRootsConfirmed
| PhTransferred
| PhRestorePrepared
| PhPublished
| PhWrapped
| PhClosed.

Inductive MigrationEventKind : Type :=
| Open
| Quote
| Appraise
| ConfirmRoots
| Transfer
| PrepareRestore
| Publish
| Close.

Record MigrationAttempt : Type := {
  att_mode : SessionMode;
  att_src_ctx : ProtectedContext;
  att_recv_ctx : ProtectedContext;
  att_phase : AttemptPhase;
  att_recv_challenge : MigrationChallenge;
  att_src_challenge : MigrationChallenge;
  att_recv_deadline : nat;
  att_src_deadline : nat;
  att_used_nonces : list nat;
  att_used_contexts : list nat;
  att_source_profile : nat;
  att_profile_map : nat;
  att_schema_plan : nat;
  att_accepted_recv_quote : option MigrationQuote;
  att_accepted_src_quote : option MigrationQuote;
  att_confirmed_roots : option (list nat);
  att_source_cred : bool;
  att_receiver_cred : bool;
  att_consent : option ConsentWitness;
  att_volatile : VolatileBuffer;
  att_storage : StorageState;
  att_wrapped_key : option WrappedKeyHandle
}.

(* Event 8: Close — clears transient volatile buffers, unpublished staging,
   consent witness, and credential witnesses while keeping used nonces, used
   contexts, current profile digest, and zero retained migration objects. *)
Definition close_attempt (att : MigrationAttempt) : MigrationAttempt :=
  {| att_mode := att_mode att;
     att_src_ctx := att_src_ctx att;
     att_recv_ctx := att_recv_ctx att;
     att_phase := PhClosed;
     att_recv_challenge := att_recv_challenge att;
     att_src_challenge := att_src_challenge att;
     att_recv_deadline := att_recv_deadline att;
     att_src_deadline := att_src_deadline att;
     att_used_nonces := att_used_nonces att;
     att_used_contexts := att_used_contexts att;
     att_source_profile := att_source_profile att;
     att_profile_map := att_profile_map att;
     att_schema_plan := att_schema_plan att;
     att_accepted_recv_quote := att_accepted_recv_quote att;
     att_accepted_src_quote := att_accepted_src_quote att;
     att_confirmed_roots := att_confirmed_roots att;
     att_source_cred := false;
     att_receiver_cred := false;
     att_consent := None;
     att_volatile := empty_volatile;
     att_storage := clear_staging (att_storage att);
     att_wrapped_key := att_wrapped_key att |}.

(* Event 1: Open — admissible TLS contexts sharing channel, origin, and
   exporter; creates fresh distinct non-zero challenges and records spent
   nonces and context IDs. *)
Definition open_attempt (p : MigrationProfile) (mode : SessionMode)
    (att : MigrationAttempt) (recv_nonce src_nonce now recv_dl src_dl : nat)
    : MigrationAttempt :=
  match att_phase att with
  | PhIdle =>
    let sctx := att_src_ctx att in
    let rctx := att_recv_ctx att in
    let rrole := expected_recv_role mode in
    if profile_bounded p &&
       context_usable sctx && context_usable rctx &&
       role_eqb (ctx_role sctx) MigrationSource &&
       role_eqb (ctx_role rctx) rrole &&
       (ctx_channel sctx =? ctx_channel rctx) &&
       (ctx_origin sctx =? ctx_origin rctx) &&
       (ctx_exporter sctx =? ctx_exporter rctx) &&
       negb (ctx_id sctx =? ctx_id rctx) &&
       (0 <? recv_nonce) && (0 <? src_nonce) && negb (recv_nonce =? src_nonce) &&
       (now <? recv_dl) && (now <? src_dl) &&
       negb (ProofSupport.mem_nat recv_nonce (att_used_nonces att)) &&
       negb (ProofSupport.mem_nat src_nonce (att_used_nonces att)) &&
       negb (ProofSupport.mem_nat (ctx_id sctx) (att_used_contexts att)) &&
       negb (ProofSupport.mem_nat (ctx_id rctx) (att_used_contexts att))
    then
      {| att_mode := mode;
         att_src_ctx := sctx;
         att_recv_ctx := rctx;
         att_phase := PhOpened;
         att_recv_challenge := {|
           ch_nonce := recv_nonce;
           ch_origin := ctx_origin rctx;
           ch_domain := mp_domain p;
           ch_challenger_role := MigrationSource;
           ch_target_role := rrole;
           ch_source_profile := att_source_profile att;
           ch_profile_map := att_profile_map att;
           ch_schema_plan := att_schema_plan att;
           ch_unit_scope := mode_eqb mode ModeEnrollment
         |};
         att_src_challenge := {|
           ch_nonce := src_nonce;
           ch_origin := ctx_origin sctx;
           ch_domain := mp_domain p;
           ch_challenger_role := rrole;
           ch_target_role := MigrationSource;
           ch_source_profile := att_source_profile att;
           ch_profile_map := att_profile_map att;
           ch_schema_plan := att_schema_plan att;
           ch_unit_scope := false
         |};
         att_recv_deadline := recv_dl;
         att_src_deadline := src_dl;
         att_used_nonces := recv_nonce :: src_nonce :: att_used_nonces att;
         att_used_contexts := ctx_id sctx :: ctx_id rctx :: att_used_contexts att;
         att_source_profile := att_source_profile att;
         att_profile_map := att_profile_map att;
         att_schema_plan := att_schema_plan att;
         att_accepted_recv_quote := None;
         att_accepted_src_quote := None;
         att_confirmed_roots := None;
         att_source_cred := false;
         att_receiver_cred := false;
         att_consent := None;
         att_volatile := empty_volatile;
         att_storage := clear_staging (att_storage att);
         att_wrapped_key := None |}
    else close_attempt att
  | _ => close_attempt att
  end.

(* Restart/reconnection preserves used_nonces and used_contexts and refuses
   reusing any spent context ID. *)
Definition restart_attempt (att : MigrationAttempt)
    (new_src new_recv : ProtectedContext) : MigrationAttempt :=
  let spent := ctx_id (att_src_ctx att) :: ctx_id (att_recv_ctx att) :: att_used_contexts att in
  if ProofSupport.mem_nat (ctx_id new_src) spent ||
     ProofSupport.mem_nat (ctx_id new_recv) spent ||
     (ctx_id new_src =? ctx_id new_recv)
  then close_attempt att
  else
    {| att_mode := att_mode att;
       att_src_ctx := new_src;
       att_recv_ctx := new_recv;
       att_phase := PhIdle;
       att_recv_challenge := att_recv_challenge att;
       att_src_challenge := att_src_challenge att;
       att_recv_deadline := 0;
       att_src_deadline := 0;
       att_used_nonces := att_used_nonces att;
       att_used_contexts := spent;
       att_source_profile := att_source_profile att;
       att_profile_map := att_profile_map att;
       att_schema_plan := att_schema_plan att;
       att_accepted_recv_quote := None;
       att_accepted_src_quote := None;
       att_confirmed_roots := None;
       att_source_cred := false;
       att_receiver_cred := false;
       att_consent := None;
       att_volatile := empty_volatile;
       att_storage := clear_staging (att_storage att);
       att_wrapped_key := None |}.

(* Event 3: Appraise — fixed mutual order:
   1. PhOpened + expected_recv_role (MigrationReceiver or BackupKeyEnrollment)
   2. PhReceiverAppraised + MigrationSource binding accepted receiver quote ID. *)
Definition receiver_appraisal_checks (p : MigrationProfile) (pol : MigrationPolicy)
    (auth : MigrationQuote -> bool) (att : MigrationAttempt)
    (target_role : MigrationRole) (now wire_bytes : nat) (q : MigrationQuote) : bool :=
  let rrole := expected_recv_role (att_mode att) in
  role_eqb target_role rrole &&
  context_usable (att_src_ctx att) &&
  (now <? att_recv_deadline att) &&
  (wire_bytes <=? mp_evidence_bound p) &&
  auth q &&
  challenge_eqb (ev_challenge q) (att_recv_challenge att) &&
  (ev_exporter q =? ctx_exporter (att_src_ctx att)) &&
  role_eqb (ev_role q) rrole &&
  (ev_principal q =? pol_required_principal pol) &&
  pol_approved_gen pol (ev_generation q) &&
  pol_approved_manifest pol (ev_ref_manifest q) &&
  (0 <? length (ev_roots q)) &&
  (length (ev_roots q) <=? mp_max_roots p) &&
  match ev_bound_receiver_quote q with None => true | Some _ => false end &&
  match att_mode att with
  | ModeMigration =>
    match ev_enrolled_recipient q with None => true | Some _ => false end
  | ModeEnrollment =>
    match pol_expected_enrolled_recipient pol with
    | None => false
    | Some exp => ProofSupport.option_eqb Nat.eqb (ev_enrolled_recipient q) (Some exp)
    end
  end.

Definition source_appraisal_checks (p : MigrationProfile) (pol : MigrationPolicy)
    (auth : MigrationQuote -> bool) (att : MigrationAttempt)
    (recv_q : MigrationQuote) (now wire_bytes : nat) (q : MigrationQuote) : bool :=
  context_usable (att_recv_ctx att) &&
  (now <? att_src_deadline att) &&
  (wire_bytes <=? mp_evidence_bound p) &&
  auth q &&
  challenge_eqb (ev_challenge q) (att_src_challenge att) &&
  (ev_exporter q =? ctx_exporter (att_recv_ctx att)) &&
  role_eqb (ev_role q) MigrationSource &&
  (ev_principal q =? pol_required_principal pol) &&
  pol_approved_gen pol (ev_generation q) &&
  pol_approved_manifest pol (ev_ref_manifest q) &&
  ProofSupport.option_eqb Nat.eqb (ev_bound_receiver_quote q) (Some (ev_id recv_q)).

Definition appraise_peer (p : MigrationProfile) (pol : MigrationPolicy)
    (auth : MigrationQuote -> bool) (att : MigrationAttempt)
    (target_role : MigrationRole) (q : MigrationQuote) (now wire_bytes : nat)
    : MigrationAttempt * bool :=
  match att_phase att with
  | PhOpened =>
    if receiver_appraisal_checks p pol auth att target_role now wire_bytes q then
      ({| att_mode := att_mode att;
          att_src_ctx := att_src_ctx att;
          att_recv_ctx := att_recv_ctx att;
          att_phase := PhReceiverAppraised;
          att_recv_challenge := att_recv_challenge att;
          att_src_challenge := att_src_challenge att;
          att_recv_deadline := att_recv_deadline att;
          att_src_deadline := att_src_deadline att;
          att_used_nonces := att_used_nonces att;
          att_used_contexts := att_used_contexts att;
          att_source_profile := att_source_profile att;
          att_profile_map := att_profile_map att;
          att_schema_plan := att_schema_plan att;
          att_accepted_recv_quote := Some q;
          att_accepted_src_quote := None;
          att_confirmed_roots := None;
          att_source_cred := false;
          att_receiver_cred := false;
          att_consent := None;
          att_volatile := att_volatile att;
          att_storage := att_storage att;
          att_wrapped_key := att_wrapped_key att |}, true)
    else (close_attempt att, false)
  | PhReceiverAppraised =>
    match role_eqb target_role MigrationSource, att_accepted_recv_quote att with
    | true, Some recv_q =>
      if source_appraisal_checks p pol auth att recv_q now wire_bytes q then
        ({| att_mode := att_mode att;
            att_src_ctx := att_src_ctx att;
            att_recv_ctx := att_recv_ctx att;
            att_phase := PhMutuallyAppraised;
            att_recv_challenge := att_recv_challenge att;
            att_src_challenge := att_src_challenge att;
            att_recv_deadline := att_recv_deadline att;
            att_src_deadline := att_src_deadline att;
            att_used_nonces := att_used_nonces att;
            att_used_contexts := att_used_contexts att;
            att_source_profile := att_source_profile att;
            att_profile_map := att_profile_map att;
            att_schema_plan := att_schema_plan att;
            att_accepted_recv_quote := Some recv_q;
            att_accepted_src_quote := Some q;
            att_confirmed_roots := None;
            att_source_cred := false;
            att_receiver_cred := false;
            att_consent := None;
            att_volatile := att_volatile att;
            att_storage := att_storage att;
            att_wrapped_key := att_wrapped_key att |}, true)
      else (close_attempt att, false)
    | _, _ => (close_attempt att, false)
    end
  | _ => (close_attempt att, false)
  end.

(* Event 4: ConfirmRoots — requires prior mutual appraisal, dual primary
   credentials, and exact complete receiver root set confirmation on source. *)
Definition confirm_roots (p : MigrationProfile) (att : MigrationAttempt)
    (confirmed : list nat) (cw : ConsentWitness) : MigrationAttempt * bool :=
  match att_phase att, att_accepted_recv_quote att, att_accepted_src_quote att with
  | PhMutuallyAppraised, Some recv_q, Some src_q =>
    if cw_source_cred cw && cw_receiver_cred cw &&
       (cw_channel_id cw =? ctx_channel (att_src_ctx att)) &&
       (cw_source_profile cw =? att_source_profile att) &&
       (cw_profile_map cw =? att_profile_map att) &&
       (cw_schema_plan cw =? att_schema_plan att) &&
       ProofSupport.list_eqb Nat.eqb confirmed (ev_roots recv_q) &&
       ProofSupport.list_eqb Nat.eqb (cw_roots cw) (ev_roots recv_q) &&
       (0 <? length confirmed) && (length confirmed <=? mp_max_roots p)
    then
      ({| att_mode := att_mode att;
          att_src_ctx := att_src_ctx att;
          att_recv_ctx := att_recv_ctx att;
          att_phase := PhRootsConfirmed;
          att_recv_challenge := att_recv_challenge att;
          att_src_challenge := att_src_challenge att;
          att_recv_deadline := att_recv_deadline att;
          att_src_deadline := att_src_deadline att;
          att_used_nonces := att_used_nonces att;
          att_used_contexts := att_used_contexts att;
          att_source_profile := att_source_profile att;
          att_profile_map := att_profile_map att;
          att_schema_plan := att_schema_plan att;
          att_accepted_recv_quote := Some recv_q;
          att_accepted_src_quote := Some src_q;
          att_confirmed_roots := Some confirmed;
          att_source_cred := true;
          att_receiver_cred := true;
          att_consent := Some cw;
          att_volatile := att_volatile att;
          att_storage := att_storage att;
          att_wrapped_key := att_wrapped_key att |}, true)
    else (close_attempt att, false)
  | _, _, _ => (close_attempt att, false)
  end.

(* Event 5: Transfer — admissible ONLY in ModeMigration with confirmed roots,
   dual credentials, MigrationReceiver + MigrationSource quotes, and volatile
   transfer buffer within mp_volatile_cap. Zero storage writes. *)
Definition transfer_backup (p : MigrationProfile) (att : MigrationAttempt)
    (obj_bytes : nat) : MigrationAttempt * bool :=
  match att_phase att, att_mode att, att_accepted_recv_quote att,
        att_accepted_src_quote att, att_confirmed_roots att, att_consent att with
  | PhRootsConfirmed, ModeMigration, Some recv_q, Some src_q, Some croots, Some cw =>
    if role_eqb (ev_role recv_q) MigrationReceiver &&
       role_eqb (ev_role src_q) MigrationSource &&
       att_source_cred att && att_receiver_cred att &&
       cw_source_cred cw && cw_receiver_cred cw &&
       (cw_channel_id cw =? ctx_channel (att_src_ctx att)) &&
       ProofSupport.list_eqb Nat.eqb croots (ev_roots recv_q) &&
       ProofSupport.list_eqb Nat.eqb (cw_roots cw) croots &&
       (0 <? obj_bytes) && (obj_bytes <=? mp_object_bound p) &&
       (obj_bytes <=? mp_volatile_cap p)
    then
      ({| att_mode := att_mode att;
          att_src_ctx := att_src_ctx att;
          att_recv_ctx := att_recv_ctx att;
          att_phase := PhTransferred;
          att_recv_challenge := att_recv_challenge att;
          att_src_challenge := att_src_challenge att;
          att_recv_deadline := att_recv_deadline att;
          att_src_deadline := att_src_deadline att;
          att_used_nonces := att_used_nonces att;
          att_used_contexts := att_used_contexts att;
          att_source_profile := att_source_profile att;
          att_profile_map := att_profile_map att;
          att_schema_plan := att_schema_plan att;
          att_accepted_recv_quote := Some recv_q;
          att_accepted_src_quote := Some src_q;
          att_confirmed_roots := Some croots;
          att_source_cred := att_source_cred att;
          att_receiver_cred := att_receiver_cred att;
          att_consent := Some cw;
          att_volatile := {| vb_object_bytes := obj_bytes;
                             vb_has_object := true;
                             vb_has_object_key := true |};
          att_storage := att_storage att;
          att_wrapped_key := None |}, true)
    else (close_attempt att, false)
  | _, _, _, _, _, _ => (close_attempt att, false)
  end.

(* Event 6: PrepareRestore — authenticates manifest, plan, chunks, and
   complete canonical coverage; writes ONLY into unreachable staging. *)
Definition prepare_restore (att : MigrationAttempt) (rp : RestorePayload)
    : MigrationAttempt * bool :=
  match att_phase att, att_mode att with
  | PhTransferred, ModeMigration =>
    if vb_has_object (att_volatile att) &&
       vb_has_object_key (att_volatile att) &&
       rp_manifest_auth rp &&
       (rp_source_profile rp =? att_source_profile att) &&
       (rp_profile_map rp =? att_profile_map att) &&
       (rp_schema_plan rp =? att_schema_plan att) &&
       rp_all_schemas_decided rp &&
       rp_chunks_verified rp &&
       rp_coverage_complete rp
    then
      let st := att_storage att in
      ({| att_mode := att_mode att;
          att_src_ctx := att_src_ctx att;
          att_recv_ctx := att_recv_ctx att;
          att_phase := PhRestorePrepared;
          att_recv_challenge := att_recv_challenge att;
          att_src_challenge := att_src_challenge att;
          att_recv_deadline := att_recv_deadline att;
          att_src_deadline := att_src_deadline att;
          att_used_nonces := att_used_nonces att;
          att_used_contexts := att_used_contexts att;
          att_source_profile := att_source_profile att;
          att_profile_map := att_profile_map att;
          att_schema_plan := att_schema_plan att;
          att_accepted_recv_quote := att_accepted_recv_quote att;
          att_accepted_src_quote := att_accepted_src_quote att;
          att_confirmed_roots := att_confirmed_roots att;
          att_source_cred := att_source_cred att;
          att_receiver_cred := att_receiver_cred att;
          att_consent := att_consent att;
          att_volatile := att_volatile att;
          att_storage := {|
            st_current_profile_gen := st_current_profile_gen st;
            st_current_regions_digest := st_current_regions_digest st;
            st_unreachable_staging_digest := Some (rp_staged_digest rp);
            st_retained_backup_objects := st_retained_backup_objects st;
            st_retained_key_capsules := st_retained_key_capsules st;
            st_fresh_epoch_current := st_fresh_epoch_current st
          |};
          att_wrapped_key := None |}, true)
    else (close_attempt att, false)
  | _, _ => (close_attempt att, false)
  end.

(* Event 7: Publish — atomic restore commit consuming transfer authorization
   and clearing volatile transfer buffer and unreachable staging. *)
Definition publish_restore (att : MigrationAttempt) : MigrationAttempt * bool :=
  match att_phase att, att_mode att,
        st_unreachable_staging_digest (att_storage att), att_consent att with
  | PhRestorePrepared, ModeMigration, Some staged, Some cw =>
    if att_source_cred att && att_receiver_cred att &&
       (cw_channel_id cw =? ctx_channel (att_src_ctx att)) &&
       st_fresh_epoch_current (att_storage att)
    then
      let st := att_storage att in
      ({| att_mode := att_mode att;
          att_src_ctx := att_src_ctx att;
          att_recv_ctx := att_recv_ctx att;
          att_phase := PhPublished;
          att_recv_challenge := att_recv_challenge att;
          att_src_challenge := att_src_challenge att;
          att_recv_deadline := att_recv_deadline att;
          att_src_deadline := att_src_deadline att;
          att_used_nonces := att_used_nonces att;
          att_used_contexts := att_used_contexts att;
          att_source_profile := att_source_profile att;
          att_profile_map := att_profile_map att;
          att_schema_plan := att_schema_plan att;
          att_accepted_recv_quote := att_accepted_recv_quote att;
          att_accepted_src_quote := att_accepted_src_quote att;
          att_confirmed_roots := att_confirmed_roots att;
          att_source_cred := false;
          att_receiver_cred := false;
          att_consent := None;
          att_volatile := empty_volatile;
          att_storage := {|
            st_current_profile_gen := st_current_profile_gen st;
            st_current_regions_digest := staged;
            st_unreachable_staging_digest := None;
            st_retained_backup_objects := st_retained_backup_objects st;
            st_retained_key_capsules := st_retained_key_capsules st;
            st_fresh_epoch_current := st_fresh_epoch_current st
          |};
          att_wrapped_key := None |}, true)
    else (close_attempt att, false)
  | _, _, _, _ => (close_attempt att, false)
  end.

(* Enrolled recovery-key wrapping: admissible ONLY in ModeEnrollment with
   BackupKeyEnrollment quote, matching enrolled recipient, and confirmed
   roots. Produces a locally sealed WrappedKeyHandle with zero storage
   capsules and zero region transfer. *)
Definition wrap_recovery_key (att : MigrationAttempt) (object_id expected_rec : nat)
    : MigrationAttempt * bool :=
  match att_phase att, att_mode att, att_accepted_recv_quote att,
        att_accepted_src_quote att, att_confirmed_roots att, att_consent att with
  | PhRootsConfirmed, ModeEnrollment, Some recv_q, Some _, Some croots, Some cw =>
    if role_eqb (ev_role recv_q) BackupKeyEnrollment &&
       ProofSupport.option_eqb Nat.eqb (ev_enrolled_recipient recv_q) (Some expected_rec) &&
       att_source_cred att && att_receiver_cred att &&
       cw_source_cred cw && cw_receiver_cred cw &&
       (cw_channel_id cw =? ctx_channel (att_src_ctx att)) &&
       ProofSupport.list_eqb Nat.eqb croots (ev_roots recv_q) &&
       ProofSupport.list_eqb Nat.eqb (cw_roots cw) croots &&
       (0 <? object_id)
    then
      ({| att_mode := att_mode att;
          att_src_ctx := att_src_ctx att;
          att_recv_ctx := att_recv_ctx att;
          att_phase := PhWrapped;
          att_recv_challenge := att_recv_challenge att;
          att_src_challenge := att_src_challenge att;
          att_recv_deadline := att_recv_deadline att;
          att_src_deadline := att_src_deadline att;
          att_used_nonces := att_used_nonces att;
          att_used_contexts := att_used_contexts att;
          att_source_profile := att_source_profile att;
          att_profile_map := att_profile_map att;
          att_schema_plan := att_schema_plan att;
          att_accepted_recv_quote := att_accepted_recv_quote att;
          att_accepted_src_quote := att_accepted_src_quote att;
          att_confirmed_roots := att_confirmed_roots att;
          att_source_cred := false;
          att_receiver_cred := false;
          att_consent := None;
          att_volatile := empty_volatile;
          att_storage := att_storage att;
          att_wrapped_key := Some {| wk_recipient := expected_rec;
                                    wk_object_id := object_id;
                                    wk_use_restore_only := true;
                                    wk_locally_sealed := true |} |}, true)
    else (close_attempt att, false)
  | _, _, _, _, _, _ => (close_attempt att, false)
  end.

(* =========================================================================
   4. Core state-machine safety and role-separation theorems
   ========================================================================= *)

(*| discharges: R-10-040, R-12-015a |*)
Theorem enrollment_role_cannot_authorize_transfer :
  forall p att obj_bytes,
  att_mode att = ModeEnrollment \/
  (exists recv_q, att_accepted_recv_quote att = Some recv_q /\
                  ev_role recv_q = BackupKeyEnrollment) ->
  snd (transfer_backup p att obj_bytes) = false.
Proof.
  intros p att obj_bytes [Hmode | [recv_q [Hacc Hrole]]];
    unfold transfer_backup;
    destruct (att_phase att); try reflexivity;
    destruct (att_mode att); try reflexivity;
    try discriminate Hmode;
    destruct (att_accepted_recv_quote att) as [rq|]; try reflexivity;
    destruct (att_accepted_src_quote att) as [sq|]; try reflexivity;
    destruct (att_confirmed_roots att) as [cr|]; try reflexivity;
    destruct (att_consent att) as [cw|]; try reflexivity.
  inversion Hacc; subst. rewrite Hrole. reflexivity.
Qed.

Theorem transfer_uses_volatile_buffer_only_and_zero_storage :
  forall p att obj_bytes next_att,
  transfer_backup p att obj_bytes = (next_att, true) ->
  att_storage next_att = att_storage att /\
  vb_has_object (att_volatile next_att) = true /\
  vb_has_object_key (att_volatile next_att) = true /\
  vb_object_bytes (att_volatile next_att) = obj_bytes /\
  0 < obj_bytes /\ obj_bytes <= mp_volatile_cap p.
Proof.
  intros p att obj_bytes next_att H.
  unfold transfer_backup in H.
  destruct (att_phase att); try discriminate;
    destruct (att_mode att); try discriminate;
    destruct (att_accepted_recv_quote att); try discriminate;
    destruct (att_accepted_src_quote att); try discriminate;
    destruct (att_confirmed_roots att); try discriminate;
    destruct (att_consent att); try discriminate.
  match type of H with (if ?c then _ else _) = _ => destruct c eqn:Ec end;
    [|discriminate].
  inversion H; subst. cbn.
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[[[[[[[[_ _] _] _] _] _] _] _] _] Hpos] _] Hcap].
  apply Nat.ltb_lt in Hpos. apply Nat.leb_le in Hcap.
  repeat split; assumption || reflexivity.
Qed.

Theorem close_clears_volatile_buffers_and_revokes_authority :
  forall att,
  att_phase (close_attempt att) = PhClosed /\
  att_volatile (close_attempt att) = empty_volatile /\
  att_consent (close_attempt att) = None /\
  att_source_cred (close_attempt att) = false /\
  att_receiver_cred (close_attempt att) = false /\
  st_unreachable_staging_digest (att_storage (close_attempt att)) = None /\
  st_current_regions_digest (att_storage (close_attempt att)) =
    st_current_regions_digest (att_storage att) /\
  st_retained_backup_objects (att_storage (close_attempt att)) =
    st_retained_backup_objects (att_storage att) /\
  st_retained_key_capsules (att_storage (close_attempt att)) =
    st_retained_key_capsules (att_storage att).
Proof.
  intro att. repeat split; reflexivity.
Qed.

Theorem failed_prepare_or_publish_preserves_current_profile :
  forall att rp,
  (snd (prepare_restore att rp) = false ->
   st_current_regions_digest (att_storage (fst (prepare_restore att rp))) =
     st_current_regions_digest (att_storage att)) /\
  (snd (publish_restore att) = false ->
   st_current_regions_digest (att_storage (fst (publish_restore att))) =
     st_current_regions_digest (att_storage att)).
Proof.
  intros att rp. split; intro H.
  - unfold prepare_restore in *.
    destruct (att_phase att); try reflexivity;
      destruct (att_mode att); try reflexivity.
    match type of H with snd (if ?c then _ else _) = _ => destruct c end;
      [discriminate | reflexivity].
  - unfold publish_restore in *.
    destruct (att_phase att); try reflexivity;
      destruct (att_mode att); try reflexivity;
      destruct (st_unreachable_staging_digest (att_storage att)); try reflexivity;
      destruct (att_consent att); try reflexivity.
    match type of H with snd (if ?c then _ else _) = _ => destruct c end;
      [discriminate | reflexivity].
Qed.

Theorem any_step_preserves_zero_retained_migration_objects :
  forall p pol auth att mode rn sn now rdl sdl role q sz cr cw ob rp oid rec,
  st_retained_backup_objects (att_storage att) = 0 /\
  st_retained_key_capsules (att_storage att) = 0 ->
  (st_retained_backup_objects (att_storage (open_attempt p mode att rn sn now rdl sdl)) = 0 /\
   st_retained_key_capsules (att_storage (open_attempt p mode att rn sn now rdl sdl)) = 0) /\
  (st_retained_backup_objects (att_storage (fst (appraise_peer p pol auth att role q now sz))) = 0 /\
   st_retained_key_capsules (att_storage (fst (appraise_peer p pol auth att role q now sz))) = 0) /\
  (st_retained_backup_objects (att_storage (fst (confirm_roots p att cr cw))) = 0 /\
   st_retained_key_capsules (att_storage (fst (confirm_roots p att cr cw))) = 0) /\
  (st_retained_backup_objects (att_storage (fst (transfer_backup p att ob))) = 0 /\
   st_retained_key_capsules (att_storage (fst (transfer_backup p att ob))) = 0) /\
  (st_retained_backup_objects (att_storage (fst (prepare_restore att rp))) = 0 /\
   st_retained_key_capsules (att_storage (fst (prepare_restore att rp))) = 0) /\
  (st_retained_backup_objects (att_storage (fst (publish_restore att))) = 0 /\
   st_retained_key_capsules (att_storage (fst (publish_restore att))) = 0) /\
  (st_retained_backup_objects (att_storage (fst (wrap_recovery_key att oid rec))) = 0 /\
   st_retained_key_capsules (att_storage (fst (wrap_recovery_key att oid rec))) = 0) /\
  (st_retained_backup_objects (att_storage (close_attempt att)) = 0 /\
   st_retained_key_capsules (att_storage (close_attempt att)) = 0).
Proof.
  intros p pol auth att mode rn sn now rdl sdl role q sz cr cw ob rp oid rec [Ho Hc].
  repeat split.
  - unfold open_attempt. destruct (att_phase att); try (cbn; exact Ho).
    match goal with |- st_retained_backup_objects (att_storage (if ?c then _ else _)) = 0 =>
      destruct c; cbn; exact Ho end.
  - unfold open_attempt. destruct (att_phase att); try (cbn; exact Hc).
    match goal with |- st_retained_key_capsules (att_storage (if ?c then _ else _)) = 0 =>
      destruct c; cbn; exact Hc end.
  - unfold appraise_peer. destruct (att_phase att); try (cbn; exact Ho).
    + match goal with |- st_retained_backup_objects (att_storage (fst (if ?c then _ else _))) = 0 =>
        destruct c; cbn; exact Ho end.
    + destruct (role_eqb role MigrationSource); try (cbn; exact Ho).
      destruct (att_accepted_recv_quote att); try (cbn; exact Ho).
      match goal with |- st_retained_backup_objects (att_storage (fst (if ?c then _ else _))) = 0 =>
        destruct c; cbn; exact Ho end.
  - unfold appraise_peer. destruct (att_phase att); try (cbn; exact Hc).
    + match goal with |- st_retained_key_capsules (att_storage (fst (if ?c then _ else _))) = 0 =>
        destruct c; cbn; exact Hc end.
    + destruct (role_eqb role MigrationSource); try (cbn; exact Hc).
      destruct (att_accepted_recv_quote att); try (cbn; exact Hc).
      match goal with |- st_retained_key_capsules (att_storage (fst (if ?c then _ else _))) = 0 =>
        destruct c; cbn; exact Hc end.
  - unfold confirm_roots.
    destruct (att_phase att); try (cbn; exact Ho);
      destruct (att_accepted_recv_quote att); try (cbn; exact Ho);
      destruct (att_accepted_src_quote att); try (cbn; exact Ho).
    match goal with |- st_retained_backup_objects (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Ho end.
  - unfold confirm_roots.
    destruct (att_phase att); try (cbn; exact Hc);
      destruct (att_accepted_recv_quote att); try (cbn; exact Hc);
      destruct (att_accepted_src_quote att); try (cbn; exact Hc).
    match goal with |- st_retained_key_capsules (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Hc end.
  - unfold transfer_backup.
    destruct (att_phase att); try (cbn; exact Ho);
      destruct (att_mode att); try (cbn; exact Ho);
      destruct (att_accepted_recv_quote att); try (cbn; exact Ho);
      destruct (att_accepted_src_quote att); try (cbn; exact Ho);
      destruct (att_confirmed_roots att); try (cbn; exact Ho);
      destruct (att_consent att); try (cbn; exact Ho).
    match goal with |- st_retained_backup_objects (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Ho end.
  - unfold transfer_backup.
    destruct (att_phase att); try (cbn; exact Hc);
      destruct (att_mode att); try (cbn; exact Hc);
      destruct (att_accepted_recv_quote att); try (cbn; exact Hc);
      destruct (att_accepted_src_quote att); try (cbn; exact Hc);
      destruct (att_confirmed_roots att); try (cbn; exact Hc);
      destruct (att_consent att); try (cbn; exact Hc).
    match goal with |- st_retained_key_capsules (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Hc end.
  - unfold prepare_restore.
    destruct (att_phase att); try (cbn; exact Ho);
      destruct (att_mode att); try (cbn; exact Ho).
    match goal with |- st_retained_backup_objects (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Ho end.
  - unfold prepare_restore.
    destruct (att_phase att); try (cbn; exact Hc);
      destruct (att_mode att); try (cbn; exact Hc).
    match goal with |- st_retained_key_capsules (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Hc end.
  - unfold publish_restore.
    destruct (att_phase att); try (cbn; exact Ho);
      destruct (att_mode att); try (cbn; exact Ho);
      destruct (st_unreachable_staging_digest (att_storage att)); try (cbn; exact Ho);
      destruct (att_consent att); try (cbn; exact Ho).
    match goal with |- st_retained_backup_objects (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Ho end.
  - unfold publish_restore.
    destruct (att_phase att); try (cbn; exact Hc);
      destruct (att_mode att); try (cbn; exact Hc);
      destruct (st_unreachable_staging_digest (att_storage att)); try (cbn; exact Hc);
      destruct (att_consent att); try (cbn; exact Hc).
    match goal with |- st_retained_key_capsules (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Hc end.
  - unfold wrap_recovery_key.
    destruct (att_phase att); try (cbn; exact Ho);
      destruct (att_mode att); try (cbn; exact Ho);
      destruct (att_accepted_recv_quote att); try (cbn; exact Ho);
      destruct (att_accepted_src_quote att); try (cbn; exact Ho);
      destruct (att_confirmed_roots att); try (cbn; exact Ho);
      destruct (att_consent att); try (cbn; exact Ho).
    match goal with |- st_retained_backup_objects (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Ho end.
  - unfold wrap_recovery_key.
    destruct (att_phase att); try (cbn; exact Hc);
      destruct (att_mode att); try (cbn; exact Hc);
      destruct (att_accepted_recv_quote att); try (cbn; exact Hc);
      destruct (att_accepted_src_quote att); try (cbn; exact Hc);
      destruct (att_confirmed_roots att); try (cbn; exact Hc);
      destruct (att_consent att); try (cbn; exact Hc).
    match goal with |- st_retained_key_capsules (att_storage (fst (if ?c then _ else _))) = 0 =>
      destruct c; cbn; exact Hc end.
  - cbn; exact Ho.
  - cbn; exact Hc.
Qed.

Theorem root_confirmation_requires_mutual_appraisal :
  forall p att roots cw,
  att_phase att <> PhMutuallyAppraised ->
  snd (confirm_roots p att roots cw) = false.
Proof.
  intros p att roots cw Hneq. unfold confirm_roots.
  destruct (att_phase att); try reflexivity. contradiction.
Qed.

Theorem post_restart_context_or_nonce_reuse_is_refused :
  forall p mode att new_src new_recv rn sn now rdl sdl,
  let r := restart_attempt att new_src new_recv in
  (In (ctx_id new_src) (ctx_id (att_src_ctx att) :: ctx_id (att_recv_ctx att) :: att_used_contexts att) \/
   In rn (att_used_nonces att) \/ In sn (att_used_nonces att)) ->
  att_phase (open_attempt p mode r rn sn now rdl sdl) = PhClosed.
Proof.
  intros p mode att new_src new_recv rn sn now rdl sdl r H.
  unfold r, restart_attempt.
  destruct (ProofSupport.mem_nat (ctx_id new_src)
              (ctx_id (att_src_ctx att) :: ctx_id (att_recv_ctx att) :: att_used_contexts att) ||
            ProofSupport.mem_nat (ctx_id new_recv)
              (ctx_id (att_src_ctx att) :: ctx_id (att_recv_ctx att) :: att_used_contexts att) ||
            (ctx_id new_src =? ctx_id new_recv)) eqn:Er.
  - unfold open_attempt. cbn. reflexivity.
  - repeat rewrite orb_false_iff in Er. destruct Er as [[Es _] _].
    unfold open_attempt. cbn [att_phase att_used_nonces].
    destruct H as [Hin | [Hrn | Hsn]].
    + assert (Hm : ProofSupport.mem_nat (ctx_id new_src)
                     (ctx_id (att_src_ctx att) :: ctx_id (att_recv_ctx att) :: att_used_contexts att) = true).
      { unfold ProofSupport.mem_nat. apply (ProofSupport.member_any_eqb nat Nat.eqb ProofSupport.nat_eqb_refl).
        clear -Hin. induction (ctx_id (att_src_ctx att) :: ctx_id (att_recv_ctx att) :: att_used_contexts att);
          cbn in *; destruct Hin; [left; symmetry; assumption | right; auto]. }
      rewrite Hm in Es. discriminate.
    + assert (Hm : ProofSupport.mem_nat rn (att_used_nonces att) = true).
      { unfold ProofSupport.mem_nat. apply (ProofSupport.member_any_eqb nat Nat.eqb ProofSupport.nat_eqb_refl).
        clear -Hrn. induction (att_used_nonces att); cbn in *; destruct Hrn;
          [left; symmetry; assumption | right; auto]. }
      rewrite Hm. cbn. rewrite !andb_false_r. reflexivity.
    + assert (Hm : ProofSupport.mem_nat sn (att_used_nonces att) = true).
      { unfold ProofSupport.mem_nat. apply (ProofSupport.member_any_eqb nat Nat.eqb ProofSupport.nat_eqb_refl).
        clear -Hsn. induction (att_used_nonces att); cbn in *; destruct Hsn;
          [left; symmetry; assumption | right; auto]. }
      rewrite Hm. cbn. rewrite !andb_false_r. reflexivity.
Qed.

(* =========================================================================
   5. Named security premises and trace semantics
   ========================================================================= *)

Definition SameKeyHolder (a b : ProtectedContext) : Prop :=
  ctx_id a = ctx_id b /\
  ctx_channel a = ctx_channel b /\
  ctx_unit a = ctx_unit b /\
  ctx_role a = ctx_role b /\
  ctx_principal a = ctx_principal b /\
  ctx_origin a = ctx_origin b.

(* ExporterSecurity: on a given TLS 1.3 connection, an exporter value and
   endpoint role uniquely determine the local ProtectedContext holder. *)
Definition ExporterSecurity (custody : ProtectedContext -> Prop) : Prop :=
  forall a b,
  context_usable a = true -> context_usable b = true ->
  custody a -> custody b ->
  ctx_exporter a = ctx_exporter b ->
  ctx_role a = ctx_role b ->
  SameKeyHolder a b.

Definition EvidenceAuthenticity (auth : MigrationQuote -> bool)
    (ledger : list MigrationIssuance) (signing_keys_intact : Prop) : Prop :=
  signing_keys_intact -> forall q, auth q = true ->
  exists iss, In iss ledger /\ mi_quote iss = q.

Definition LocalContextIntegrity (p : MigrationProfile)
    (ledger : list MigrationIssuance) (rt : LocalRuntime) : Prop :=
  forall iss, In iss ledger ->
  let q := mi_quote iss in
  let c := mi_issuer_ctx iss in
  context_usable c = true /\
  0 < ev_id q /\
  ev_exporter q = ctx_exporter c /\
  rt_measured_gen rt (ctx_unit c) = Some (ev_generation q) /\
  rt_ref_manifest rt (ctx_unit c) = Some (ev_ref_manifest q) /\
  ev_principal q = ctx_principal c /\
  ev_role q = ctx_role c /\
  ch_origin (ev_challenge q) = ctx_origin c /\
  ch_domain (ev_challenge q) = mp_domain p /\
  (ev_role q = MigrationReceiver ->
    rt_roots rt (ctx_unit c) = Some (ev_roots q) /\
    ev_bound_receiver_quote q = None) /\
  (ev_role q = BackupKeyEnrollment ->
    rt_roots rt (ctx_unit c) = Some (ev_roots q) /\
    rt_enrolled_recipient rt (ctx_origin c) (ctx_unit c) = ev_enrolled_recipient q /\
    ev_bound_receiver_quote q = None) /\
  (ev_role q = MigrationSource ->
    ev_bound_receiver_quote q <> None).

Definition RootSetFaithfulness (rt : LocalRuntime)
    (actual_roots : nat -> list nat) : Prop :=
  forall u roots, rt_roots rt u = Some roots -> roots = actual_roots u.

Definition UncompromisedKeys (custody : ProtectedContext -> Prop)
    (ledger : list MigrationIssuance) (src_ctx recv_ctx : ProtectedContext) : Prop :=
  custody src_ctx /\ custody recv_ctx /\
  forall iss, In iss ledger -> custody (mi_issuer_ctx iss).

Definition EnrollmentPolicyBinding (pol : MigrationPolicy) (rt : LocalRuntime)
    (ctx : ProtectedContext) : Prop :=
  forall exp,
  pol_expected_enrolled_recipient pol = Some exp ->
  rt_enrolled_recipient rt (ctx_origin ctx) (ctx_unit ctx) = Some exp ->
  ctx_unit ctx = pol_expected_unit pol.

Inductive MigrationTraceEvent : Type :=
| EvOpen : MigrationAttempt -> nat -> nat -> MigrationTraceEvent
| EvQuote : MigrationIssuance -> MigrationTraceEvent
| EvAppraise : MigrationAttempt -> MigrationRole -> MigrationQuote -> nat -> nat -> MigrationTraceEvent
| EvConfirmRoots : MigrationAttempt -> list nat -> ConsentWitness -> MigrationTraceEvent
| EvTransfer : MigrationAttempt -> nat -> nat -> MigrationTraceEvent
| EvPrepareRestore : MigrationAttempt -> RestorePayload -> MigrationTraceEvent
| EvPublish : MigrationAttempt -> MigrationTraceEvent
| EvWrapKey : MigrationAttempt -> nat -> nat -> MigrationTraceEvent
| EvClose : MigrationAttempt -> MigrationTraceEvent
| EvKeyExposed : ProtectedContext -> nat -> MigrationTraceEvent
| EvIssuerCompromised : nat -> MigrationTraceEvent
| EvTrustedPathCompromised : nat -> MigrationTraceEvent.

Definition MigrationTrace : Type := list MigrationTraceEvent.

Definition event_kind (e : MigrationTraceEvent) : option MigrationEventKind :=
  match e with
  | EvOpen _ _ _ => Some Open
  | EvQuote _ => Some Quote
  | EvAppraise _ _ _ _ _ => Some Appraise
  | EvConfirmRoots _ _ _ => Some ConfirmRoots
  | EvTransfer _ _ _ => Some Transfer
  | EvPrepareRestore _ _ => Some PrepareRestore
  | EvPublish _ => Some Publish
  | EvClose _ => Some Close
  | EvWrapKey _ _ _ | EvKeyExposed _ _ | EvIssuerCompromised _ | EvTrustedPathCompromised _ => None
  end.

Fixpoint trace_issuances (tr : MigrationTrace) : list MigrationIssuance :=
  match tr with
  | [] => []
  | EvQuote iss :: rest => iss :: trace_issuances rest
  | _ :: rest => trace_issuances rest
  end.

Lemma trace_issuances_in_tr : forall tr iss,
  In iss (trace_issuances tr) <-> In (EvQuote iss) tr.
Proof.
  induction tr as [|e rest IH]; intro iss; split; intro H.
  - destruct H.
  - destruct H.
  - destruct e; cbn in H; try (right; apply IH; exact H).
    destruct H as [Heq|Hin]; [subst; left; reflexivity | right; apply IH; exact Hin].
  - destruct H as [Heq|Hin].
    + subst. left. reflexivity.
    + destruct e; cbn; try (apply IH; exact Hin). right. apply IH. exact Hin.
Qed.

Definition trace_issuer_compromised (tr : MigrationTrace) (u : nat) : Prop :=
  In (EvIssuerCompromised u) tr.

Definition trace_tp_compromised (tr : MigrationTrace) (u : nat) : Prop :=
  In (EvTrustedPathCompromised u) tr.

Definition NoKeyExposure (tr : MigrationTrace) : Prop :=
  forall ctx sender, ~ In (EvKeyExposed ctx sender) tr.

Definition NoIssuerCompromise (tr : MigrationTrace) : Prop :=
  forall u, ~ In (EvIssuerCompromised u) tr.

Definition NoTrustedPathCompromise (tr : MigrationTrace) : Prop :=
  forall u, ~ In (EvTrustedPathCompromised u) tr.

(* HonestTrustedPath: when trusted-path integrity holds for a ConfirmRoots
   event, the source trusted path genuinely verified dual primary credentials
   and presented the exact confirmed root list and plan to the holder. *)
Definition HonestTrustedPath (tp_intact : Prop) (tr : MigrationTrace) : Prop :=
  tp_intact ->
  forall att roots cw,
  In (EvConfirmRoots att roots cw) tr ->
  cw_source_cred cw = true /\ cw_receiver_cred cw = true /\
  cw_roots cw = roots /\
  att_accepted_recv_quote att <> None /\
  match att_accepted_recv_quote att with
  | Some rq => roots = ev_roots rq
  | None => False
  end.

Record MigrationEnv : Type := {
  me_profile : MigrationProfile;
  me_runtime : LocalRuntime;
  me_actual_roots : nat -> list nat;
  me_auth : MigrationQuote -> bool;
  me_custody : ProtectedContext -> Prop;
  me_recv_pol : MigrationPolicy;
  me_src_pol : MigrationPolicy
}.

Definition role_policy (env : MigrationEnv) (role : MigrationRole) : MigrationPolicy :=
  match role with
  | MigrationSource => me_src_pol env
  | MigrationReceiver | BackupKeyEnrollment => me_recv_pol env
  end.

Definition bundle_fresh (tr : MigrationTrace) (att : MigrationAttempt) (rn sn : nat) : Prop :=
  0 < rn /\ 0 < sn /\ rn <> sn /\
  exists i_open : nat,
    nth_error tr i_open = Some (EvOpen att rn sn) /\
    (forall j att' rn' sn',
      nth_error tr j = Some (EvOpen att' rn' sn') ->
      (rn' = rn \/ sn' = sn \/
       ctx_id (att_src_ctx att') = ctx_id (att_src_ctx att) \/
       ctx_id (att_recv_ctx att') = ctx_id (att_recv_ctx att)) ->
      j = i_open /\ att' = att /\ rn' = rn /\ sn' = sn) /\
    (forall m iss,
      nth_error tr m = Some (EvQuote iss) ->
      ~ trace_issuer_compromised tr (ctx_unit (mi_issuer_ctx iss)) ->
      (ev_challenge (mi_quote iss) = att_recv_challenge att \/
       ev_challenge (mi_quote iss) = att_src_challenge att) ->
      i_open < m).

Definition TraceSound (env : MigrationEnv) (tr : MigrationTrace) : Prop :=
  (forall i att rn sn,
    nth_error tr i = Some (EvOpen att rn sn) ->
    att_phase att = PhOpened /\
    context_usable (att_src_ctx att) = true /\
    context_usable (att_recv_ctx att) = true /\
    ctx_role (att_src_ctx att) = MigrationSource /\
    ctx_role (att_recv_ctx att) = expected_recv_role (att_mode att) /\
    ctx_channel (att_src_ctx att) = ctx_channel (att_recv_ctx att) /\
    ctx_origin (att_src_ctx att) = ctx_origin (att_recv_ctx att) /\
    ctx_exporter (att_src_ctx att) = ctx_exporter (att_recv_ctx att) /\
    me_custody env (att_src_ctx att) /\
    me_custody env (att_recv_ctx att) /\
    ch_nonce (att_recv_challenge att) = rn /\
    ch_nonce (att_src_challenge att) = sn /\
    bundle_fresh tr att rn sn) /\
  (forall iss,
    In (EvQuote iss) tr ->
    ~ trace_issuer_compromised tr (ctx_unit (mi_issuer_ctx iss)) ->
    LocalContextIntegrity (me_profile env) [iss] (me_runtime env) /\
    me_custody env (mi_issuer_ctx iss)) /\
  (forall k att role q now sz,
    nth_error tr k = Some (EvAppraise att role q now sz) ->
    snd (appraise_peer (me_profile env) (role_policy env role) (me_auth env) att role q now sz) = true /\
    (role = expected_recv_role (att_mode att) ->
      exists i_open rn sn,
        i_open < k /\
        nth_error tr i_open = Some (EvOpen att rn sn)) /\
    (role = MigrationSource ->
      exists i_ra att_r q_r now_r sz_r,
        i_ra < k /\
        nth_error tr i_ra = Some (EvAppraise att_r (expected_recv_role (att_mode att)) q_r now_r sz_r) /\
        att_src_ctx att = att_src_ctx att_r /\
        att_recv_ctx att = att_recv_ctx att_r /\
        att_mode att = att_mode att_r /\
        att_accepted_recv_quote att = Some q_r /\
        att_src_challenge att = att_src_challenge att_r)) /\
  (forall i_c att roots cw,
    nth_error tr i_c = Some (EvConfirmRoots att roots cw) ->
    snd (confirm_roots (me_profile env) att roots cw) = true /\
    exists i_sa att_s q_s now_s sz_s,
      i_sa < i_c /\
      nth_error tr i_sa = Some (EvAppraise att_s MigrationSource q_s now_s sz_s) /\
      att_src_ctx att = att_src_ctx att_s /\
      att_recv_ctx att = att_recv_ctx att_s /\
      att_mode att = att_mode att_s /\
      att_source_profile att = att_source_profile att_s /\
      att_profile_map att = att_profile_map att_s /\
      att_schema_plan att = att_schema_plan att_s /\
      att_accepted_recv_quote att = att_accepted_recv_quote att_s /\
      att_accepted_src_quote att = Some q_s) /\
  (forall i_tr att oid obytes,
    nth_error tr i_tr = Some (EvTransfer att oid obytes) ->
    snd (transfer_backup (me_profile env) att obytes) = true /\
    st_retained_backup_objects (att_storage att) = 0 /\
    st_retained_key_capsules (att_storage att) = 0 /\
    exists i_c att_c roots cw,
      i_c < i_tr /\
      nth_error tr i_c = Some (EvConfirmRoots att_c roots cw) /\
      att_src_ctx att = att_src_ctx att_c /\
      att_recv_ctx att = att_recv_ctx att_c /\
      att_mode att = att_mode att_c /\
      att_source_profile att = att_source_profile att_c /\
      att_profile_map att = att_profile_map att_c /\
      att_schema_plan att = att_schema_plan att_c /\
      att_accepted_recv_quote att = att_accepted_recv_quote att_c /\
      att_accepted_src_quote att = att_accepted_src_quote att_c /\
      att_confirmed_roots att = Some roots /\
      att_consent att = Some cw /\
      att_source_cred att = true /\
      att_receiver_cred att = true) /\
  (forall i_pr att rp,
    nth_error tr i_pr = Some (EvPrepareRestore att rp) ->
    snd (prepare_restore att rp) = true /\
    st_retained_backup_objects (att_storage att) = 0 /\
    st_retained_key_capsules (att_storage att) = 0 /\
    exists i_tr att_t oid obytes,
      i_tr < i_pr /\
      nth_error tr i_tr = Some (EvTransfer att_t oid obytes) /\
      att_src_ctx att = att_src_ctx att_t /\
      att_recv_ctx att = att_recv_ctx att_t /\
      att_mode att = att_mode att_t /\
      att_source_profile att = att_source_profile att_t /\
      att_profile_map att = att_profile_map att_t /\
      att_schema_plan att = att_schema_plan att_t /\
      att_accepted_recv_quote att = att_accepted_recv_quote att_t /\
      att_accepted_src_quote att = att_accepted_src_quote att_t /\
      att_confirmed_roots att = att_confirmed_roots att_t /\
      att_consent att = att_consent att_t /\
      att_source_cred att = true /\
      att_receiver_cred att = true) /\
  (forall i_pub att,
    nth_error tr i_pub = Some (EvPublish att) ->
    snd (publish_restore att) = true /\
    st_retained_backup_objects (att_storage att) = 0 /\
    st_retained_key_capsules (att_storage att) = 0 /\
    exists i_pr att_p rp,
      i_pr < i_pub /\
      nth_error tr i_pr = Some (EvPrepareRestore att_p rp) /\
      att_src_ctx att = att_src_ctx att_p /\
      att_recv_ctx att = att_recv_ctx att_p /\
      att_mode att = att_mode att_p /\
      att_source_profile att = att_source_profile att_p /\
      att_profile_map att = att_profile_map att_p /\
      att_schema_plan att = att_schema_plan att_p /\
      att_accepted_recv_quote att = att_accepted_recv_quote att_p /\
      att_accepted_src_quote att = att_accepted_src_quote att_p /\
      att_confirmed_roots att = att_confirmed_roots att_p /\
      att_consent att = att_consent att_p /\
      st_unreachable_staging_digest (att_storage att) = Some (rp_staged_digest rp)) /\
  (forall i_w att oid rec,
    nth_error tr i_w = Some (EvWrapKey att oid rec) ->
    snd (wrap_recovery_key att oid rec) = true /\
    st_retained_backup_objects (att_storage att) = 0 /\
    st_retained_key_capsules (att_storage att) = 0 /\
    exists i_c att_c roots cw,
      i_c < i_w /\
      nth_error tr i_c = Some (EvConfirmRoots att_c roots cw) /\
      att_src_ctx att = att_src_ctx att_c /\
      att_recv_ctx att = att_recv_ctx att_c /\
      att_mode att = att_mode att_c /\
      att_source_profile att = att_source_profile att_c /\
      att_profile_map att = att_profile_map att_c /\
      att_schema_plan att = att_schema_plan att_c /\
      att_accepted_recv_quote att = att_accepted_recv_quote att_c /\
      att_accepted_src_quote att = att_accepted_src_quote att_c /\
      att_confirmed_roots att = Some roots /\
      att_consent att = Some cw /\
      att_source_cred att = true /\
      att_receiver_cred att = true) /\
  (forall k m att role q now sz iss,
    nth_error tr k = Some (EvAppraise att role q now sz) ->
    nth_error tr m = Some (EvQuote iss) ->
    ~ trace_issuer_compromised tr (ctx_unit (mi_issuer_ctx iss)) ->
    mi_quote iss = q ->
    m < k) /\
  (forall m iss qid i_ra att_r q_r now_r sz_r,
    nth_error tr m = Some (EvQuote iss) ->
    ~ trace_issuer_compromised tr (ctx_unit (mi_issuer_ctx iss)) ->
    ev_bound_receiver_quote (mi_quote iss) = Some qid ->
    nth_error tr i_ra = Some (EvAppraise att_r (expected_recv_role (att_mode att_r)) q_r now_r sz_r) ->
    ev_id q_r = qid ->
    i_ra < m).

(* =========================================================================
   6. Conditional mutual session-agreement theorems (zero axioms)
   ========================================================================= *)

Lemma in_nth_error_witness : forall (A : Type) (xs : list A) (x : A),
  In x xs -> exists idx, nth_error xs idx = Some x.
Proof.
  intros A xs x Hin. apply In_nth_error in Hin. exact Hin.
Qed.

Lemma trace_sound_local_integrity : forall env tr,
  TraceSound env tr -> NoIssuerCompromise tr ->
  LocalContextIntegrity (me_profile env) (trace_issuances tr) (me_runtime env) /\
  (forall iss, In iss (trace_issuances tr) -> me_custody env (mi_issuer_ctx iss)).
Proof.
  intros env tr [_ [Hquotes _]] Hnoiss.
  split.
  - intros iss Hin. apply trace_issuances_in_tr in Hin.
    destruct (Hquotes iss Hin (Hnoiss (ctx_unit (mi_issuer_ctx iss)))) as [Hloc _].
    apply Hloc. left. reflexivity.
  - intros iss Hin. apply trace_issuances_in_tr in Hin.
    destruct (Hquotes iss Hin (Hnoiss (ctx_unit (mi_issuer_ctx iss)))) as [_ Hcust].
    exact Hcust.
Qed.

Lemma receiver_appraisal_checks_ok :
  forall p pol auth att role now sz q,
  att_phase att = PhOpened ->
  snd (appraise_peer p pol auth att role q now sz) = true ->
  role = expected_recv_role (att_mode att) /\
  context_usable (att_src_ctx att) = true /\
  auth q = true /\
  ev_challenge q = att_recv_challenge att /\
  ev_exporter q = ctx_exporter (att_src_ctx att) /\
  ev_role q = expected_recv_role (att_mode att) /\
  ev_principal q = pol_required_principal pol /\
  pol_approved_gen pol (ev_generation q) = true /\
  pol_approved_manifest pol (ev_ref_manifest q) = true /\
  0 < length (ev_roots q) /\
  length (ev_roots q) <= mp_max_roots p /\
  ev_bound_receiver_quote q = None /\
  (att_mode att = ModeEnrollment ->
    exists exp, pol_expected_enrolled_recipient pol = Some exp /\
                ev_enrolled_recipient q = Some exp).
Proof.
  intros p pol auth att role now sz q Hph H.
  unfold appraise_peer in H. rewrite Hph in H.
  destruct (receiver_appraisal_checks p pol auth att role now sz q) eqn:Ec; [|discriminate].
  unfold receiver_appraisal_checks in Ec.
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[[[[[[[[[[[Hrole Hctx] _] _] Hauth] Hchal] Hexp] Her] Hpr] Hg] Hm] Hrl] Hrm] Hbr] Henr].
  apply role_eqb_sound in Hrole. apply challenge_eqb_sound in Hchal.
  apply Nat.eqb_eq in Hexp. apply role_eqb_sound in Her. apply Nat.eqb_eq in Hpr.
  apply Nat.ltb_lt in Hrl. apply Nat.leb_le in Hrm.
  assert (Hbr_none : ev_bound_receiver_quote q = None).
  { destruct (ev_bound_receiver_quote q); [discriminate|reflexivity]. }
  repeat split; try assumption.
  intro Hmode. rewrite Hmode in Henr.
  destruct (pol_expected_enrolled_recipient pol) as [exp|] eqn:Eexp; [|discriminate].
  apply (ProofSupport.option_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Henr.
  exists exp. split; [reflexivity | exact Henr].
Qed.

Lemma source_appraisal_checks_ok :
  forall p pol auth att role now sz q,
  att_phase att = PhReceiverAppraised ->
  snd (appraise_peer p pol auth att role q now sz) = true ->
  exists recv_q,
    att_accepted_recv_quote att = Some recv_q /\
    role = MigrationSource /\
    context_usable (att_recv_ctx att) = true /\
    auth q = true /\
    ev_challenge q = att_src_challenge att /\
    ev_exporter q = ctx_exporter (att_recv_ctx att) /\
    ev_role q = MigrationSource /\
    ev_principal q = pol_required_principal pol /\
    pol_approved_gen pol (ev_generation q) = true /\
    pol_approved_manifest pol (ev_ref_manifest q) = true /\
    ev_bound_receiver_quote q = Some (ev_id recv_q).
Proof.
  intros p pol auth att role now sz q Hph H.
  unfold appraise_peer in H. rewrite Hph in H.
  destruct (role_eqb role MigrationSource) eqn:Er; [|discriminate].
  destruct (att_accepted_recv_quote att) as [recv_q|] eqn:Earq; [|discriminate].
  destruct (source_appraisal_checks p pol auth att recv_q now sz q) eqn:Ec; [|discriminate].
  unfold source_appraisal_checks in Ec.
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[[[[[[[Hctx _] _] Hauth] Hchal] Hexp] Her] Hpr] Hg] Hm] Hb].
  apply role_eqb_sound in Er. apply challenge_eqb_sound in Hchal.
  apply Nat.eqb_eq in Hexp. apply role_eqb_sound in Her. apply Nat.eqb_eq in Hpr.
  apply (ProofSupport.option_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hb.
  exists recv_q. repeat split; assumption || reflexivity.
Qed.

Lemma transfer_checks_ok :
  forall p att obytes,
  snd (transfer_backup p att obytes) = true ->
  exists recv_q src_q croots cw,
    att_phase att = PhRootsConfirmed /\
    att_mode att = ModeMigration /\
    att_accepted_recv_quote att = Some recv_q /\
    att_accepted_src_quote att = Some src_q /\
    att_confirmed_roots att = Some croots /\
    att_consent att = Some cw /\
    ev_role recv_q = MigrationReceiver /\
    ev_role src_q = MigrationSource /\
    att_source_cred att = true /\
    att_receiver_cred att = true /\
    cw_source_cred cw = true /\
    cw_receiver_cred cw = true /\
    cw_channel_id cw = ctx_channel (att_src_ctx att) /\
    croots = ev_roots recv_q /\
    cw_roots cw = croots /\
    0 < obytes /\ obytes <= mp_object_bound p /\ obytes <= mp_volatile_cap p.
Proof.
  intros p att obytes H. unfold transfer_backup in H.
  destruct (att_phase att) eqn:Eph; try discriminate;
    destruct (att_mode att) eqn:Emd; try discriminate;
    destruct (att_accepted_recv_quote att) as [rq|] eqn:Erq; try discriminate;
    destruct (att_accepted_src_quote att) as [sq|] eqn:Esq; try discriminate;
    destruct (att_confirmed_roots att) as [cr|] eqn:Ecr; try discriminate;
    destruct (att_consent att) as [cw|] eqn:Ecw; try discriminate.
  match type of H with snd (if ?c then _ else _) = _ => destruct c eqn:Ec end; [|discriminate].
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[[[[[[[[Hrr Hsr] Hsc] Hrc] Hcsc] Hcrc] Hch] Hrcr] Hcwr] Hpos] Hobj] Hcap].
  apply role_eqb_sound in Hrr. apply role_eqb_sound in Hsr.
  apply Nat.eqb_eq in Hch.
  apply (ProofSupport.list_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hrcr.
  apply (ProofSupport.list_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hcwr.
  apply Nat.ltb_lt in Hpos. apply Nat.leb_le in Hobj. apply Nat.leb_le in Hcap.
  exists rq, sq, cr, cw. repeat split; assumption || reflexivity.
Qed.

Lemma prepare_checks_ok :
  forall att rp,
  snd (prepare_restore att rp) = true ->
  att_phase att = PhTransferred /\
  att_mode att = ModeMigration /\
  vb_has_object (att_volatile att) = true /\
  vb_has_object_key (att_volatile att) = true /\
  rp_manifest_auth rp = true /\
  rp_source_profile rp = att_source_profile att /\
  rp_profile_map rp = att_profile_map att /\
  rp_schema_plan rp = att_schema_plan att /\
  rp_all_schemas_decided rp = true /\
  rp_chunks_verified rp = true /\
  rp_coverage_complete rp = true.
Proof.
  intros att rp H. unfold prepare_restore in H.
  destruct (att_phase att) eqn:Eph; try discriminate;
    destruct (att_mode att) eqn:Emd; try discriminate.
  match type of H with snd (if ?c then _ else _) = _ => destruct c eqn:Ec end; [|discriminate].
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[[[[[Hvo Hvk] Hma] Hsp] Hpm] Hpl] Hsd] Hcv] Hcc].
  apply Nat.eqb_eq in Hsp. apply Nat.eqb_eq in Hpm. apply Nat.eqb_eq in Hpl.
  repeat split; assumption || reflexivity.
Qed.

Lemma publish_checks_ok :
  forall att,
  snd (publish_restore att) = true ->
  exists staged cw,
    att_phase att = PhRestorePrepared /\
    att_mode att = ModeMigration /\
    st_unreachable_staging_digest (att_storage att) = Some staged /\
    att_consent att = Some cw /\
    att_source_cred att = true /\
    att_receiver_cred att = true /\
    cw_channel_id cw = ctx_channel (att_src_ctx att) /\
    st_fresh_epoch_current (att_storage att) = true.
Proof.
  intros att H. unfold publish_restore in H.
  destruct (att_phase att) eqn:Eph; try discriminate;
    destruct (att_mode att) eqn:Emd; try discriminate;
    destruct (st_unreachable_staging_digest (att_storage att)) as [st|] eqn:Est; try discriminate;
    destruct (att_consent att) as [cw|] eqn:Ecw; try discriminate.
  match type of H with snd (if ?c then _ else _) = _ => destruct c eqn:Ec end; [|discriminate].
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[Hsc Hrc] Hch] Hfr].
  apply Nat.eqb_eq in Hch.
  exists st, cw. repeat split; assumption || reflexivity.
Qed.

Lemma wrap_checks_ok :
  forall att oid rec,
  snd (wrap_recovery_key att oid rec) = true ->
  exists recv_q src_q croots cw,
    att_phase att = PhRootsConfirmed /\
    att_mode att = ModeEnrollment /\
    att_accepted_recv_quote att = Some recv_q /\
    att_accepted_src_quote att = Some src_q /\
    att_confirmed_roots att = Some croots /\
    att_consent att = Some cw /\
    ev_role recv_q = BackupKeyEnrollment /\
    ev_enrolled_recipient recv_q = Some rec /\
    att_source_cred att = true /\
    att_receiver_cred att = true /\
    cw_source_cred cw = true /\
    cw_receiver_cred cw = true /\
    cw_channel_id cw = ctx_channel (att_src_ctx att) /\
    croots = ev_roots recv_q /\
    cw_roots cw = croots /\
    0 < oid.
Proof.
  intros att oid rec H. unfold wrap_recovery_key in H.
  destruct (att_phase att) eqn:Eph; try discriminate;
    destruct (att_mode att) eqn:Emd; try discriminate;
    destruct (att_accepted_recv_quote att) as [rq|] eqn:Erq; try discriminate;
    destruct (att_accepted_src_quote att) as [sq|] eqn:Esq; try discriminate;
    destruct (att_confirmed_roots att) as [cr|] eqn:Ecr; try discriminate;
    destruct (att_consent att) as [cw|] eqn:Ecw; try discriminate.
  match type of H with snd (if ?c then _ else _) = _ => destruct c eqn:Ec end; [|discriminate].
  repeat rewrite andb_true_iff in Ec.
  destruct Ec as [[[[[[[[[Hrr Hrec] Hsc] Hrc] Hcsc] Hcrc] Hch] Hrcr] Hcwr] Hpos].
  apply role_eqb_sound in Hrr.
  apply (ProofSupport.option_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hrec.
  apply Nat.eqb_eq in Hch.
  apply (ProofSupport.list_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hrcr.
  apply (ProofSupport.list_eqb_sound nat Nat.eqb ProofSupport.nat_eqb_true) in Hcwr.
  apply Nat.ltb_lt in Hpos.
  exists rq, sq, cr, cw. repeat split; assumption || reflexivity.
Qed.

(*| discharges: R-10-040, R-12-015c |*)
Theorem migration_transfer_agreement :
  forall env tr signing_keys_intact tp_intact att oid obytes i_tr,
  TraceSound env tr ->
  NoKeyExposure tr ->
  NoIssuerCompromise tr ->
  ExporterSecurity (me_custody env) ->
  EvidenceAuthenticity (me_auth env) (trace_issuances tr) signing_keys_intact ->
  signing_keys_intact ->
  LocalContextIntegrity (me_profile env) (trace_issuances tr) (me_runtime env) ->
  RootSetFaithfulness (me_runtime env) (me_actual_roots env) ->
  HonestTrustedPath tp_intact tr ->
  tp_intact ->
  UncompromisedKeys (me_custody env) (trace_issuances tr) (att_src_ctx att) (att_recv_ctx att) ->
  nth_error tr i_tr = Some (EvTransfer att oid obytes) ->
  exists iss_recv iss_src i_open i_rq i_ra i_sq i_sa i_c recv_q src_q croots cw,
    i_open < i_rq /\ i_rq < i_ra /\ i_ra < i_sq /\ i_sq < i_sa /\ i_sa < i_c /\ i_c < i_tr /\
    att_mode att = ModeMigration /\
    mi_quote iss_recv = recv_q /\
    mi_quote iss_src = src_q /\
    ev_role recv_q = MigrationReceiver /\
    ev_role src_q = MigrationSource /\
    ev_bound_receiver_quote src_q = Some (ev_id recv_q) /\
    SameKeyHolder (mi_issuer_ctx iss_recv) (att_recv_ctx att) /\
    SameKeyHolder (mi_issuer_ctx iss_src) (att_src_ctx att) /\
    rt_measured_gen (me_runtime env) (ctx_unit (att_recv_ctx att)) = Some (ev_generation recv_q) /\
    rt_measured_gen (me_runtime env) (ctx_unit (att_src_ctx att)) = Some (ev_generation src_q) /\
    pol_approved_gen (me_recv_pol env) (ev_generation recv_q) = true /\
    pol_approved_gen (me_src_pol env) (ev_generation src_q) = true /\
    croots = me_actual_roots env (ctx_unit (att_recv_ctx att)) /\
    cw_roots cw = croots /\
    cw_source_cred cw = true /\
    cw_receiver_cred cw = true /\
    0 < obytes /\ obytes <= mp_volatile_cap (me_profile env) /\
    st_retained_backup_objects (att_storage att) = 0 /\
    st_retained_key_capsules (att_storage att) = 0.
Proof.
  intros env tr signing_keys_intact tp_intact att oid obytes i_tr
    Hsound _ Hnoiss Hex Hauth Hsign Hlocal Hroots Htp Htp_ok Hkeys Hnth_tr.
  pose proof Hsound as [Hopen [_ [Happ [Hconf [Htrans [_ [_ [_ [Hcausal Hsrc_after]]]]]]]]].
  destruct (Htrans i_tr att oid obytes Hnth_tr)
    as [Htr_ok [Hret0 [Hcap0 [i_c [att_c [roots [cw [Hlt_c_tr [Hnth_c
       [Hcs [Hcr [Hcm [Hcp [Hpm [Hpl [Harq [Hasq [Hacr [Hacw [Hsc Hrc]]]]]]]]]]]]]]]]]]]].
  destruct (transfer_checks_ok (me_profile env) att obytes Htr_ok)
    as [recv_q [src_q [croots [cw' [_ [Hmode [Harq2 [Hasq2 [Hacr2 [Hacw2
       [Hrr [Hsr [_ [_ [_ [_ [_ [_ [_ [Hpos [_ Hcap]]]]]]]]]]]]]]]]]]]]].
  rewrite Harq2 in Harq. rewrite Hasq2 in Hasq.
  rewrite Hacr2 in Hacr. inversion Hacr; subst croots.
  rewrite Hacw2 in Hacw. inversion Hacw; subst cw'.
  destruct (Hconf i_c att_c roots cw Hnth_c)
    as [_ [i_sa [att_s [q_s [now_s [sz_s [Hlt_sa_c [Hnth_sa
       [Hss [Hsr2 [Hsm [_ [_ [_ [Harq_s Hasq_s]]]]]]]]]]]]]]].
  rewrite <- Hasq in Hasq_s. inversion Hasq_s; subst q_s.
  destruct (Happ i_sa att_s MigrationSource src_q now_s sz_s Hnth_sa)
    as [Hsa_ok [_ Hsrc_prev]].
  destruct (att_phase att_s) eqn:Eph_s.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
  - exfalso.
    destruct (receiver_appraisal_checks_ok (me_profile env) (role_policy env MigrationSource)
                (me_auth env) att_s MigrationSource now_s sz_s src_q Eph_s Hsa_ok)
      as [Hrole _].
    rewrite <- Hsm, <- Hcm, Hmode in Hrole. discriminate Hrole.
  - destruct (source_appraisal_checks_ok (me_profile env) (role_policy env MigrationSource)
                (me_auth env) att_s MigrationSource now_s sz_s src_q Eph_s Hsa_ok)
      as [rq_s [Harq2_eq [_ [_ [Hauth_s [Hchal_s [Hexp_s [_ [_ [Hgen_s [_ Hbound_sq]]]]]]]]]]].
    destruct (Hsrc_prev eq_refl)
      as [i_ra [att_r [q_r [now_r [sz_r [Hlt_ra_sa [Hnth_ra [Hrs [Hrr3 [Hrm [Harq_r Hschal]]]]]]]]]]].
    rewrite <- Harq_s, <- Harq in Harq2_eq. inversion Harq2_eq; subst rq_s.
    rewrite <- Harq_s, <- Harq in Harq_r. inversion Harq_r; subst q_r.
    destruct (Happ i_ra att_r (expected_recv_role (att_mode att_s)) recv_q now_r sz_r Hnth_ra)
      as [Hra_ok [Hrecv_prev _]].
    destruct (att_phase att_r) eqn:Eph_r.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
    + destruct (Hrecv_prev (f_equal expected_recv_role Hrm)) as [i_open [rn [sn [Hlt_o_ra Hnth_o]]]].
      destruct (Hopen i_open att_r rn sn Hnth_o)
        as [_ [Hus_s [Hus_r [Hsr_role [Hrr_role [Hch_sr [Hor_sr [Hex_sr
           [Hcust_s [Hcust_r [_ [_ Hfresh]]]]]]]]]]]].
      destruct (receiver_appraisal_checks_ok (me_profile env)
                  (role_policy env (expected_recv_role (att_mode att_s)))
                  (me_auth env) att_r (expected_recv_role (att_mode att_s)) now_r sz_r recv_q
                  Eph_r Hra_ok)
        as [_ [_ [Hauth_r [Hchal_r [Hexp_r [_ [_ [Hgen_r [_ [_ [_ [_ _]]]]]]]]]]]].
      (* Authenticate both issuances *)
      destruct (Hauth Hsign recv_q Hauth_r) as [iss_recv [Hin_rq Hev_rq]].
      destruct (Hauth Hsign src_q Hauth_s) as [iss_src [Hin_sq Hev_sq]].
      pose proof (trace_issuances_in_tr tr iss_recv) as Htr_rq. apply Htr_rq in Hin_rq.
      pose proof (trace_issuances_in_tr tr iss_src) as Htr_sq. apply Htr_sq in Hin_sq.
      destruct (in_nth_error_witness _ _ _ Hin_rq) as [i_rq Hnth_rq].
      destruct (in_nth_error_witness _ _ _ Hin_sq) as [i_sq Hnth_sq].
      apply trace_issuances_in_tr in Hin_rq.
      apply trace_issuances_in_tr in Hin_sq.
      pose proof (Hlocal iss_recv Hin_rq) as Hloc_r.
      pose proof (Hlocal iss_src Hin_sq) as Hloc_s.
      cbn in Hloc_r, Hloc_s.
      rewrite Hev_rq in Hloc_r. rewrite Hev_sq in Hloc_s.
      destruct Hloc_r as [Hus_ir [_ [Hexp_ir [Hmg_ir [_ [_ [Hr_ir [_ [_ [Hrt_r _]]]]]]]]]].
      destruct Hloc_s as [Hus_is [_ [Hexp_is [Hmg_is [_ [_ [Hr_is _]]]]]]].
      destruct Hkeys as [_ [_ Hcust_all]].
      pose proof (Hcust_all iss_recv Hin_rq) as Hcust_ir.
      pose proof (Hcust_all iss_src Hin_sq) as Hcust_is.
      (* ExporterSecurity on receiver and source *)
      assert (Hholder_r : SameKeyHolder (mi_issuer_ctx iss_recv) (att_recv_ctx att)).
      { apply Hex; try assumption.
        - rewrite Hcr, Hsr2, Hrr3. exact Hus_r.
        - rewrite Hcr, Hsr2, Hrr3. exact Hcust_r.
        - rewrite <- Hexp_ir, Hexp_r, Hex_sr, <- Hrr3, <- Hsr2, <- Hcr. reflexivity.
        - rewrite <- Hr_ir, Hrr, Hcr, Hsr2, Hrr3, Hrr_role, <- Hrm, <- Hsm, <- Hcm, Hmode. reflexivity. }
      assert (Hholder_s : SameKeyHolder (mi_issuer_ctx iss_src) (att_src_ctx att)).
      { apply Hex; try assumption.
        - rewrite Hcs, Hss, Hrs. exact Hus_s.
        - rewrite Hcs, Hss, Hrs. exact Hcust_s.
        - rewrite <- Hexp_is, Hexp_s, Hrr3, <- Hex_sr, <- Hrs, <- Hss, <- Hcs. reflexivity.
        - rewrite <- Hr_is, Hsr, Hcs, Hss, Hrs, Hsr_role. reflexivity. }
      (* Causal ordering *)
      destruct Hfresh as [_ [_ [_ [i_o2 [Hnth_o2 [Huniq Hq_after]]]]]].
      destruct (Huniq i_open att_r rn sn Hnth_o (or_introl eq_refl)) as [Heq_io _].
      subst i_o2.
      assert (Hlt_o_rq : i_open < i_rq).
      { apply (Hq_after i_rq iss_recv Hnth_rq (Hnoiss (ctx_unit (mi_issuer_ctx iss_recv)))).
        left. rewrite Hev_rq. exact Hchal_r. }
      assert (Hlt_rq_ra : i_rq < i_ra).
      { apply (Hcausal i_ra i_rq att_r (expected_recv_role (att_mode att_s)) recv_q now_r sz_r iss_recv
                 Hnth_ra Hnth_rq (Hnoiss (ctx_unit (mi_issuer_ctx iss_recv))) Hev_rq). }
      assert (Hlt_ra_sq : i_ra < i_sq).
      { refine (Hsrc_after i_sq iss_src (ev_id recv_q) i_ra att_r recv_q now_r sz_r
                  Hnth_sq (Hnoiss (ctx_unit (mi_issuer_ctx iss_src))) _ _ eq_refl).
        - rewrite Hev_sq. exact Hbound_sq.
        - rewrite <- Hrm. exact Hnth_ra. }
      assert (Hlt_sq_sa : i_sq < i_sa).
      { apply (Hcausal i_sa i_sq att_s MigrationSource src_q now_s sz_s iss_src
                 Hnth_sa Hnth_sq (Hnoiss (ctx_unit (mi_issuer_ctx iss_src))) Hev_sq). }
      (* HonestTrustedPath and RootSetFaithfulness *)
      assert (Hin_c : In (EvConfirmRoots att_c roots cw) tr).
      { eapply nth_error_In. exact Hnth_c. }
      destruct (Htp Htp_ok att_c roots cw Hin_c) as [Htp_sc [Htp_rc [Htp_cwr [_ Htp_rq]]]].
      rewrite <- Harq in Htp_rq.
      assert (Hroots_actual : roots = me_actual_roots env (ctx_unit (att_recv_ctx att))).
      { rewrite Htp_rq.
        destruct (Hrt_r Hrr) as [Hrt_some _].
        destruct Hholder_r as [_ [_ [Hu_r _]]].
        rewrite <- Hu_r. apply (Hroots _ _ Hrt_some). }
      (* Assemble witness *)
      destruct Hholder_r as [Hr1 [Hr2 [Hr3 [Hr4 [Hr5 Hr6]]]]].
      destruct Hholder_s as [Hs1 [Hs2 [Hs3 [Hs4 [Hs5 Hs6]]]]].
      rewrite <- Hsm, <- Hcm, Hmode in Hgen_r. cbn in Hgen_r.
      exists iss_recv, iss_src, i_open, i_rq, i_ra, i_sq, i_sa, i_c, recv_q, src_q, roots, cw.
      repeat split; try assumption; try reflexivity.
      * rewrite <- Hr3. exact Hmg_ir.
      * rewrite <- Hs3. exact Hmg_is.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok.
      destruct (role_eqb (expected_recv_role (att_mode att_s)) MigrationSource) eqn:Er;
        [|discriminate Hra_ok].
      apply role_eqb_sound in Er. rewrite <- Hsm, <- Hcm, Hmode in Er. discriminate Er.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok. discriminate Hra_ok.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
  - exfalso. unfold appraise_peer in Hsa_ok. rewrite Eph_s in Hsa_ok. discriminate Hsa_ok.
Qed.

  (*| discharges: R-10-040, R-12-015c |*)
Theorem migration_publish_agreement :
  forall env tr signing_keys_intact tp_intact att i_pub,
  TraceSound env tr ->
  NoKeyExposure tr ->
  NoIssuerCompromise tr ->
  ExporterSecurity (me_custody env) ->
  EvidenceAuthenticity (me_auth env) (trace_issuances tr) signing_keys_intact ->
  signing_keys_intact ->
  LocalContextIntegrity (me_profile env) (trace_issuances tr) (me_runtime env) ->
  RootSetFaithfulness (me_runtime env) (me_actual_roots env) ->
  HonestTrustedPath tp_intact tr ->
  tp_intact ->
  UncompromisedKeys (me_custody env) (trace_issuances tr) (att_src_ctx att) (att_recv_ctx att) ->
  nth_error tr i_pub = Some (EvPublish att) ->
  exists att_t att_p oid obytes rp iss_recv iss_src i_open i_rq i_ra i_sq i_sa i_c i_tr i_pr
         recv_q src_q croots next_att,
    i_open < i_rq /\ i_rq < i_ra /\ i_ra < i_sq /\ i_sq < i_sa /\
    i_sa < i_c /\ i_c < i_tr /\ i_tr < i_pr /\ i_pr < i_pub /\
    nth_error tr i_tr = Some (EvTransfer att_t oid obytes) /\
    nth_error tr i_pr = Some (EvPrepareRestore att_p rp) /\
    att_src_ctx att_t = att_src_ctx att /\
    att_recv_ctx att_t = att_recv_ctx att /\
    publish_restore att = (next_att, true) /\
    mi_quote iss_recv = recv_q /\
    mi_quote iss_src = src_q /\
    SameKeyHolder (mi_issuer_ctx iss_recv) (att_recv_ctx att) /\
    SameKeyHolder (mi_issuer_ctx iss_src) (att_src_ctx att) /\
    croots = me_actual_roots env (ctx_unit (att_recv_ctx att)) /\
    rp_manifest_auth rp = true /\
    rp_source_profile rp = att_source_profile att /\
    rp_profile_map rp = att_profile_map att /\
    rp_schema_plan rp = att_schema_plan att /\
    rp_all_schemas_decided rp = true /\
    rp_chunks_verified rp = true /\
    rp_coverage_complete rp = true /\
    st_current_regions_digest (att_storage next_att) = rp_staged_digest rp /\
    st_unreachable_staging_digest (att_storage next_att) = None /\
    att_volatile next_att = empty_volatile /\
    att_consent next_att = None /\
    st_retained_backup_objects (att_storage next_att) = 0 /\
    st_retained_key_capsules (att_storage next_att) = 0.
Proof.
  intros env tr signing_keys_intact tp_intact att i_pub
    Hsound Hnke Hnoiss Hex Hauth Hsign Hlocal Hroots Htp Htp_ok Hkeys Hnth_pub.
  pose proof Hsound as [_ [_ [_ [_ [_ [Hprep [Hpub _]]]]]]].
  destruct (Hpub i_pub att Hnth_pub)
    as [Hpub_ok [Hret0 [Hcap0 [i_pr [att_p [rp [Hlt_pr_pub [Hnth_pr
       [Hps [Hpr [Hpm [Hpsp [Hppm [Hppl [Hparq [Hpasq [Hpacr [Hpacw Hstg]]]]]]]]]]]]]]]]]].
  destruct (Hprep i_pr att_p rp Hnth_pr)
    as [Hprep_ok [_ [_ [i_tr [att_t [oid [obytes [Hlt_tr_pr [Hnth_tr
       [Hts [Htr [Htm [Htsp [Htpm [Htpl [Htarq [Htasq [Htacr [Htacw [Htsc Htrc]]]]]]]]]]]]]]]]]]]].
  destruct (prepare_checks_ok att_p rp Hprep_ok)
    as [_ [_ [_ [_ [Hma [Hpsp_eq [Hppm_eq [Hppl_eq [Hsd [Hcv Hcc]]]]]]]]]].
  assert (Hkeys_t : UncompromisedKeys (me_custody env) (trace_issuances tr)
                      (att_src_ctx att_t) (att_recv_ctx att_t)).
  { destruct Hkeys as [Hs [Hr Hall]].
    repeat split; [rewrite <- Hts, <- Hps; exact Hs | rewrite <- Htr, <- Hpr; exact Hr | exact Hall]. }
  destruct (migration_transfer_agreement env tr signing_keys_intact tp_intact
              att_t oid obytes i_tr
              Hsound Hnke Hnoiss Hex Hauth Hsign Hlocal Hroots Htp Htp_ok Hkeys_t Hnth_tr)
    as [iss_recv [iss_src [i_open [i_rq [i_ra [i_sq [i_sa [i_c [recv_q [src_q [croots [_
       [H1 [H2 [H3 [H4 [H5 [H6 [_ [Hrq [Hsq [_ [_ [_ [Hhold_r [Hhold_s
       [_ [_ [_ [_ [Hroots_eq _]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]].
  destruct (publish_checks_ok att Hpub_ok)
    as [staged [cw_p [Eph_att [Hmd_att [Hstg_att [Hcw_att [Hsc_att [Hrc_att [Hch_att Hfr_att]]]]]]]]].
  destruct (publish_restore att) as [next_att b] eqn:Epub.
  cbn in Hpub_ok. subst b.
  rewrite Hstg in Hstg_att. inversion Hstg_att; subst staged.
  assert (Hnext : st_current_regions_digest (att_storage next_att) = rp_staged_digest rp /\
                  st_unreachable_staging_digest (att_storage next_att) = None /\
                  att_volatile next_att = empty_volatile /\
                  att_consent next_att = None /\
                  st_retained_backup_objects (att_storage next_att) = 0 /\
                  st_retained_key_capsules (att_storage next_att) = 0).
  { unfold publish_restore in Epub.
    rewrite Eph_att, Hmd_att, Hstg, Hcw_att, Hsc_att, Hrc_att, Hch_att, Nat.eqb_refl, Hfr_att in Epub.
    cbn in Epub. inversion Epub; subst next_att.
    cbn. repeat split; assumption || reflexivity. }
  destruct Hnext as [Hn1 [Hn2 [Hn3 [Hn4 [Hn5 Hn6]]]]].
  exists att_t, att_p, oid, obytes, rp, iss_recv, iss_src,
         i_open, i_rq, i_ra, i_sq, i_sa, i_c, i_tr, i_pr,
         recv_q, src_q, croots, next_att.
  repeat match goal with |- _ /\ _ => split end;
    try assumption; try reflexivity.
  - rewrite Hps, Hts. reflexivity.
  - rewrite Hpr, Htr. reflexivity.
  - rewrite <- Htr, <- Hpr in Hhold_r. exact Hhold_r.
  - rewrite <- Hts, <- Hps in Hhold_s. exact Hhold_s.
  - rewrite <- Htr, <- Hpr in Hroots_eq. exact Hroots_eq.
  - rewrite Hpsp, Hpsp_eq. reflexivity.
  - rewrite Hppm, Hppm_eq. reflexivity.
  - rewrite Hppl, Hppl_eq. reflexivity.
Qed.

(*| discharges: R-10-040, R-12-015c |*)
Theorem enrollment_key_wrap_agreement :
  forall env tr signing_keys_intact tp_intact att oid rec i_w,
  TraceSound env tr ->
  NoKeyExposure tr ->
  NoIssuerCompromise tr ->
  ExporterSecurity (me_custody env) ->
  EvidenceAuthenticity (me_auth env) (trace_issuances tr) signing_keys_intact ->
  signing_keys_intact ->
  LocalContextIntegrity (me_profile env) (trace_issuances tr) (me_runtime env) ->
  RootSetFaithfulness (me_runtime env) (me_actual_roots env) ->
  HonestTrustedPath tp_intact tr ->
  tp_intact ->
  EnrollmentPolicyBinding (me_recv_pol env) (me_runtime env) (att_recv_ctx att) ->
  UncompromisedKeys (me_custody env) (trace_issuances tr) (att_src_ctx att) (att_recv_ctx att) ->
  nth_error tr i_w = Some (EvWrapKey att oid rec) ->
  exists iss_recv iss_src i_open i_rq i_ra i_sq i_sa i_c recv_q src_q croots cw next_att,
    i_open < i_rq /\ i_rq < i_ra /\ i_ra < i_sq /\ i_sq < i_sa /\ i_sa < i_c /\ i_c < i_w /\
    att_mode att = ModeEnrollment /\
    wrap_recovery_key att oid rec = (next_att, true) /\
    mi_quote iss_recv = recv_q /\
    mi_quote iss_src = src_q /\
    ev_role recv_q = BackupKeyEnrollment /\
    ev_role src_q = MigrationSource /\
    ev_bound_receiver_quote src_q = Some (ev_id recv_q) /\
    ev_enrolled_recipient recv_q = Some rec /\
    ctx_unit (att_recv_ctx att) = pol_expected_unit (me_recv_pol env) /\
    SameKeyHolder (mi_issuer_ctx iss_recv) (att_recv_ctx att) /\
    SameKeyHolder (mi_issuer_ctx iss_src) (att_src_ctx att) /\
    croots = me_actual_roots env (ctx_unit (att_recv_ctx att)) /\
    cw_roots cw = croots /\
    att_wrapped_key next_att = Some {| wk_recipient := rec; wk_object_id := oid;
                                       wk_use_restore_only := true; wk_locally_sealed := true |} /\
    st_retained_backup_objects (att_storage next_att) = 0 /\
    st_retained_key_capsules (att_storage next_att) = 0.
Proof.
  intros env tr signing_keys_intact tp_intact att oid rec i_w
    Hsound _ Hnoiss Hex Hauth Hsign Hlocal Hroots Htp Htp_ok Henroll Hkeys Hnth_w.
  pose proof Hsound as [Hopen [_ [Happ [Hconf [_ [_ [_ [Hwrap [Hcausal Hsrc_after]]]]]]]]].
  destruct (Hwrap i_w att oid rec Hnth_w)
    as [Hw_ok [Hret0 [Hcap0 [i_c [att_c [roots [cw [Hlt_c_w [Hnth_c
       [Hcs [Hcr [Hcm [Hcp [Hpm [Hpl [Harq [Hasq [Hacr [Hacw [Hsc Hrc]]]]]]]]]]]]]]]]]]]].
  destruct (wrap_checks_ok att oid rec Hw_ok)
    as [recv_q [src_q [croots [cw' [Eph_att [Hmode [Harq2 [Hasq2 [Hacr2 [Hacw2
       [Hrr [Hrec [Hsc2 [Hrc2 [Hcw_sc [Hcw_rc [Hcw_ch [Hcr_eq [Hcw_r Hpos]]]]]]]]]]]]]]]]]]].
  rewrite Harq2 in Harq. rewrite Hasq2 in Hasq.
  rewrite Hacr2 in Hacr. inversion Hacr; subst croots.
  rewrite Hacw2 in Hacw. inversion Hacw; subst cw'.
  destruct (Hconf i_c att_c roots cw Hnth_c)
    as [_ [i_sa [att_s [q_s [now_s [sz_s [Hlt_sa_c [Hnth_sa
       [Hss [Hsr2 [Hsm [_ [_ [_ [Harq_s Hasq_s]]]]]]]]]]]]]]].
  rewrite <- Hasq in Hasq_s. inversion Hasq_s; subst q_s.
  destruct (Happ i_sa att_s MigrationSource src_q now_s sz_s Hnth_sa)
    as [Hsa_ok [_ Hsrc_prev]].
  destruct (att_phase att_s) eqn:Eph_s; try (exfalso; unfold appraise_peer in Hsa_ok; rewrite Eph_s in Hsa_ok; discriminate Hsa_ok).
  - exfalso.
    destruct (receiver_appraisal_checks_ok (me_profile env) (role_policy env MigrationSource)
                (me_auth env) att_s MigrationSource now_s sz_s src_q Eph_s Hsa_ok)
      as [Hrole _].
    rewrite <- Hsm, <- Hcm, Hmode in Hrole. discriminate Hrole.
  - destruct (source_appraisal_checks_ok (me_profile env) (role_policy env MigrationSource)
                (me_auth env) att_s MigrationSource now_s sz_s src_q Eph_s Hsa_ok)
      as [rq_s [Harq2_eq [_ [_ [Hauth_s [Hchal_s [Hexp_s [Hsr [_ [_ [_ Hbound_sq]]]]]]]]]]].
    destruct (Hsrc_prev eq_refl)
      as [i_ra [att_r [q_r [now_r [sz_r [Hlt_ra_sa [Hnth_ra [Hrs [Hrr3 [Hrm [Harq_r Hschal]]]]]]]]]]].
    rewrite <- Harq_s, <- Harq in Harq2_eq. inversion Harq2_eq; subst rq_s.
    rewrite <- Harq_s, <- Harq in Harq_r. inversion Harq_r; subst q_r.
    destruct (Happ i_ra att_r (expected_recv_role (att_mode att_s)) recv_q now_r sz_r Hnth_ra)
      as [Hra_ok [Hrecv_prev _]].
    destruct (att_phase att_r) eqn:Eph_r; try (exfalso; unfold appraise_peer in Hra_ok; rewrite Eph_r in Hra_ok; discriminate Hra_ok).
    + destruct (Hrecv_prev (f_equal expected_recv_role Hrm)) as [i_open [rn [sn [Hlt_o_ra Hnth_o]]]].
      destruct (Hopen i_open att_r rn sn Hnth_o)
        as [_ [Hus_s [Hus_r [Hsr_role [Hrr_role [Hch_sr [Hor_sr [Hex_sr
           [Hcust_s [Hcust_r [_ [_ Hfresh]]]]]]]]]]]].
      destruct (receiver_appraisal_checks_ok (me_profile env)
                  (role_policy env (expected_recv_role (att_mode att_s)))
                  (me_auth env) att_r (expected_recv_role (att_mode att_s)) now_r sz_r recv_q
                  Eph_r Hra_ok)
        as [_ [_ [Hauth_r [Hchal_r [Hexp_r [_ [_ [_ [_ [_ [_ [_ Hpol_rec]]]]]]]]]]]].
      rewrite <- Hrm, <- Hsm, <- Hcm, Hmode in Hpol_rec.
      destruct (Hpol_rec eq_refl) as [exp [Hexp_pol Hrec_q]].
      rewrite Hrec in Hrec_q. inversion Hrec_q; subst exp.
      destruct (Hauth Hsign recv_q Hauth_r) as [iss_recv [Hin_rq Hev_rq]].
      destruct (Hauth Hsign src_q Hauth_s) as [iss_src [Hin_sq Hev_sq]].
      pose proof (trace_issuances_in_tr tr iss_recv) as Htr_rq. apply Htr_rq in Hin_rq.
      pose proof (trace_issuances_in_tr tr iss_src) as Htr_sq. apply Htr_sq in Hin_sq.
      destruct (in_nth_error_witness _ _ _ Hin_rq) as [i_rq Hnth_rq].
      destruct (in_nth_error_witness _ _ _ Hin_sq) as [i_sq Hnth_sq].
      apply trace_issuances_in_tr in Hin_rq.
      apply trace_issuances_in_tr in Hin_sq.
      pose proof (Hlocal iss_recv Hin_rq) as Hloc_r.
      pose proof (Hlocal iss_src Hin_sq) as Hloc_s.
      cbn in Hloc_r, Hloc_s.
      rewrite Hev_rq in Hloc_r. rewrite Hev_sq in Hloc_s.
      destruct Hloc_r as [Hus_ir [_ [Hexp_ir [_ [_ [_ [Hr_ir [_ [_ [_ [Hrt_r _]]]]]]]]]]].
      destruct Hloc_s as [Hus_is [_ [Hexp_is [_ [_ [_ [Hr_is _]]]]]]].
      destruct Hkeys as [_ [_ Hcust_all]].
      pose proof (Hcust_all iss_recv Hin_rq) as Hcust_ir.
      pose proof (Hcust_all iss_src Hin_sq) as Hcust_is.
      assert (Hholder_r : SameKeyHolder (mi_issuer_ctx iss_recv) (att_recv_ctx att)).
      { apply Hex; try assumption.
        - rewrite Hcr, Hsr2, Hrr3. exact Hus_r.
        - rewrite Hcr, Hsr2, Hrr3. exact Hcust_r.
        - rewrite <- Hexp_ir, Hexp_r, Hex_sr, <- Hrr3, <- Hsr2, <- Hcr. reflexivity.
        - rewrite <- Hr_ir, Hrr, Hcr, Hsr2, Hrr3, Hrr_role, <- Hrm, <- Hsm, <- Hcm, Hmode. reflexivity. }
      assert (Hholder_s : SameKeyHolder (mi_issuer_ctx iss_src) (att_src_ctx att)).
      { apply Hex; try assumption.
        - rewrite Hcs, Hss, Hrs. exact Hus_s.
        - rewrite Hcs, Hss, Hrs. exact Hcust_s.
        - rewrite <- Hexp_is, Hexp_s, Hrr3, <- Hex_sr, <- Hrs, <- Hss, <- Hcs. reflexivity.
        - rewrite <- Hr_is, Hsr, Hcs, Hss, Hrs, Hsr_role. reflexivity. }
      destruct Hfresh as [_ [_ [_ [i_o2 [Hnth_o2 [Huniq Hq_after]]]]]].
      destruct (Huniq i_open att_r rn sn Hnth_o (or_introl eq_refl)) as [Heq_io _].
      subst i_o2.
      assert (Hlt_o_rq : i_open < i_rq).
      { apply (Hq_after i_rq iss_recv Hnth_rq (Hnoiss (ctx_unit (mi_issuer_ctx iss_recv)))).
        left. rewrite Hev_rq. exact Hchal_r. }
      assert (Hlt_rq_ra : i_rq < i_ra).
      { apply (Hcausal i_ra i_rq att_r (expected_recv_role (att_mode att_s)) recv_q now_r sz_r iss_recv
                 Hnth_ra Hnth_rq (Hnoiss (ctx_unit (mi_issuer_ctx iss_recv))) Hev_rq). }
      assert (Hlt_ra_sq : i_ra < i_sq).
      { refine (Hsrc_after i_sq iss_src (ev_id recv_q) i_ra att_r recv_q now_r sz_r
                  Hnth_sq (Hnoiss (ctx_unit (mi_issuer_ctx iss_src))) _ _ eq_refl).
        - rewrite Hev_sq. exact Hbound_sq.
        - rewrite <- Hrm. exact Hnth_ra. }
      assert (Hlt_sq_sa : i_sq < i_sa).
      { apply (Hcausal i_sa i_sq att_s MigrationSource src_q now_s sz_s iss_src
                 Hnth_sa Hnth_sq (Hnoiss (ctx_unit (mi_issuer_ctx iss_src))) Hev_sq). }
      assert (Hin_c : In (EvConfirmRoots att_c roots cw) tr).
      { eapply nth_error_In. exact Hnth_c. }
      destruct (Htp Htp_ok att_c roots cw Hin_c) as [_ [_ [Htp_cwr [_ Htp_rq]]]].
      rewrite <- Harq in Htp_rq.
      destruct (Hrt_r Hrr) as [Hrt_some [Hrec_rt _]].
      assert (Hroots_actual : roots = me_actual_roots env (ctx_unit (att_recv_ctx att))).
      { rewrite Htp_rq. destruct Hholder_r as [_ [_ [Hu_r _]]].
        rewrite <- Hu_r. apply (Hroots _ _ Hrt_some). }
      assert (Hunit_enrolled : ctx_unit (att_recv_ctx att) = pol_expected_unit (me_recv_pol env)).
      { apply (Henroll rec Hexp_pol).
        destruct Hholder_r as [_ [_ [Hu_r [_ [_ Ho_r]]]]].
        rewrite <- Hu_r, <- Ho_r, Hrec_rt, Hrec. reflexivity. }
      destruct (wrap_recovery_key att oid rec) as [next_att b] eqn:Ewrap.
      cbn in Hw_ok. subst b.
      assert (Hnext : att_wrapped_key next_att = Some {| wk_recipient := rec; wk_object_id := oid;
                                                         wk_use_restore_only := true;
                                                         wk_locally_sealed := true |} /\
                      st_retained_backup_objects (att_storage next_att) = 0 /\
                      st_retained_key_capsules (att_storage next_att) = 0).
      { unfold wrap_recovery_key in Ewrap.
        rewrite Eph_att, Hmode, Harq2, Hasq2, Hacr2, Hacw2 in Ewrap.
        rewrite Hrr, role_eqb_refl, Hrec in Ewrap.
        rewrite (ProofSupport.option_eqb_refl nat Nat.eqb ProofSupport.nat_eqb_refl) in Ewrap.
        rewrite Hsc2, Hrc2, Hcw_sc, Hcw_rc, Hcw_ch, Nat.eqb_refl in Ewrap.
        rewrite Hcw_r, !(ProofSupport.list_eqb_refl nat Nat.eqb ProofSupport.nat_eqb_refl) in Ewrap.
        apply Nat.ltb_lt in Hpos. rewrite Hpos in Ewrap.
        cbn in Ewrap. inversion Ewrap; subst next_att.
        cbn. repeat split; assumption || reflexivity. }
      destruct Hnext as [Hn1 [Hn2 Hn3]].
      exists iss_recv, iss_src, i_open, i_rq, i_ra, i_sq, i_sa, i_c, recv_q, src_q, roots, cw, next_att.
      repeat match goal with |- _ /\ _ => split end;
        try assumption; try reflexivity; rewrite Hcw_r, H0; reflexivity.
    + exfalso. unfold appraise_peer in Hra_ok. rewrite Eph_r in Hra_ok.
      destruct (role_eqb (expected_recv_role (att_mode att_s)) MigrationSource) eqn:Er;
        [|discriminate Hra_ok].
      apply role_eqb_sound in Er. rewrite <- Hsm, <- Hcm, Hmode in Er. discriminate Er.
Qed.

(* =========================================================================
   7. Concrete inhabited positive traces (mutual migration & enrollment)
   ========================================================================= *)

Definition ex_profile : MigrationProfile :=
  {| mp_domain := 1;
     mp_attest_op := 2;
     mp_wrap_op := 3;
     mp_request_bound := 4;
     mp_evidence_bound := 16;
     mp_manifest_bound := 8;
     mp_object_bound := 24;
     mp_volatile_cap := 16;
     mp_max_roots := 4 |}.

Definition ex_ctx (id ch unit : nat) (role : MigrationRole) (exp : nat) : ProtectedContext :=
  {| ctx_id := id;
     ctx_channel := ch;
     ctx_unit := unit;
     ctx_role := role;
     ctx_principal := 5;
     ctx_origin := 6;
     ctx_exporter := exp;
     ctx_handshake_complete := true;
     ctx_server_authenticated := true;
     ctx_early_data := false;
     ctx_resumed := false;
     ctx_config_fixed := true |}.

(* Session 1 (Migration): Source unit 1, Receiver unit 2, channel 1, exporter 11 *)
Definition ctx_s1 : ProtectedContext := ex_ctx 1 1 1 MigrationSource 11.
Definition ctx_r1 : ProtectedContext := ex_ctx 2 1 2 MigrationReceiver 11.

(* Session 2 (Parallel migration): Source unit 1, Receiver unit 2, channel 2, exporter 12 *)
Definition ctx_s2 : ProtectedContext := ex_ctx 3 2 1 MigrationSource 12.
Definition ctx_r2 : ProtectedContext := ex_ctx 4 2 2 MigrationReceiver 12.

(* Session 3 (Recovery-key enrollment): Source unit 1, Receiver unit 2, channel 3, exporter 13 *)
Definition ctx_s_enr : ProtectedContext := ex_ctx 5 3 1 MigrationSource 13.
Definition ctx_r_enr : ProtectedContext := ex_ctx 6 3 2 BackupKeyEnrollment 13.

(* Wrong enrolled recipient unit 3 and two-leg MITM unit 4 / leg 2 *)
Definition ctx_r_wrong_enr : ProtectedContext := ex_ctx 7 3 3 BackupKeyEnrollment 13.
Definition ctx_mitm_leg1_recv : ProtectedContext := ex_ctx 8 1 4 MigrationReceiver 11.
Definition ctx_r_mitm_leg2 : ProtectedContext := ex_ctx 9 4 2 MigrationReceiver 14.

Definition ex_actual_roots (u : nat) : list nat :=
  match u with
  | 1 => [1; 2]
  | 2 => [3; 4]
  | 3 => [5; 6]
  | 4 => [7; 8]
  | _ => []
  end.

Definition ex_runtime : LocalRuntime :=
  {| rt_measured_gen := fun u => match u with 1 | 2 | 3 | 4 => Some 7 | _ => None end;
     rt_ref_manifest := fun u => match u with 1 | 2 | 3 | 4 => Some 8 | _ => None end;
     rt_roots := fun u => match u with
       | 1 => Some [1; 2]
       | 2 => Some [3; 4]
       | 3 => Some [5; 6]
       | 4 => Some [7; 8]
       | _ => None
       end;
     rt_enrolled_recipient := fun origin u =>
       if origin =? 6 then
         match u with 2 => Some 11 | 3 => Some 12 | _ => None end
       else None |}.

Definition ex_mig_pol : MigrationPolicy :=
  {| pol_approved_gen := fun g => g =? 7;
     pol_approved_manifest := fun m => m =? 8;
     pol_required_principal := 5;
     pol_unit_scope := false;
     pol_expected_enrolled_recipient := None;
     pol_expected_unit := 2 |}.

Definition ex_enr_recv_pol : MigrationPolicy :=
  {| pol_approved_gen := fun g => g =? 7;
     pol_approved_manifest := fun m => m =? 8;
     pol_required_principal := 5;
     pol_unit_scope := true;
     pol_expected_enrolled_recipient := Some 11;
     pol_expected_unit := 2 |}.

Definition ex_storage_init : StorageState :=
  {| st_current_profile_gen := 1;
     st_current_regions_digest := 7;
     st_unreachable_staging_digest := None;
     st_retained_backup_objects := 0;
     st_retained_key_capsules := 0;
     st_fresh_epoch_current := true |}.

Definition ex_storage_staged : StorageState :=
  {| st_current_profile_gen := 1;
     st_current_regions_digest := 7;
     st_unreachable_staging_digest := Some 8;
     st_retained_backup_objects := 0;
     st_retained_key_capsules := 0;
     st_fresh_epoch_current := true |}.

Definition ex_storage_published : StorageState :=
  {| st_current_profile_gen := 1;
     st_current_regions_digest := 8;
     st_unreachable_staging_digest := None;
     st_retained_backup_objects := 0;
     st_retained_key_capsules := 0;
     st_fresh_epoch_current := true |}.

Definition make_challenge (nonce : nat) (crole trole : MigrationRole) (uscope : bool) : MigrationChallenge :=
  {| ch_nonce := nonce;
     ch_origin := 6;
     ch_domain := 1;
     ch_challenger_role := crole;
     ch_target_role := trole;
     ch_source_profile := 1;
     ch_profile_map := 1;
     ch_schema_plan := 1;
     ch_unit_scope := uscope |}.

Definition make_idle_attempt (mode : SessionMode) (sctx rctx : ProtectedContext) : MigrationAttempt :=
  {| att_mode := mode;
     att_src_ctx := sctx;
     att_recv_ctx := rctx;
     att_phase := PhIdle;
     att_recv_challenge := make_challenge 0 MigrationSource (expected_recv_role mode) (mode_eqb mode ModeEnrollment);
     att_src_challenge := make_challenge 0 (expected_recv_role mode) MigrationSource false;
     att_recv_deadline := 0;
     att_src_deadline := 0;
     att_used_nonces := [];
     att_used_contexts := [];
     att_source_profile := 1;
     att_profile_map := 1;
     att_schema_plan := 1;
     att_accepted_recv_quote := None;
     att_accepted_src_quote := None;
     att_confirmed_roots := None;
     att_source_cred := false;
     att_receiver_cred := false;
     att_consent := None;
     att_volatile := empty_volatile;
     att_storage := ex_storage_init;
     att_wrapped_key := None |}.

Definition mig_att_opened : MigrationAttempt :=
  {| att_mode := ModeMigration;
     att_src_ctx := ctx_s1;
     att_recv_ctx := ctx_r1;
     att_phase := PhOpened;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10;
     att_src_deadline := 10;
     att_used_nonces := [1; 2];
     att_used_contexts := [1; 2];
     att_source_profile := 1;
     att_profile_map := 1;
     att_schema_plan := 1;
     att_accepted_recv_quote := None;
     att_accepted_src_quote := None;
     att_confirmed_roots := None;
     att_source_cred := false;
     att_receiver_cred := false;
     att_consent := None;
     att_volatile := empty_volatile;
     att_storage := ex_storage_init;
     att_wrapped_key := None |}.

Definition ex_cred_policy : CredentialHandles.CredentialPolicy :=
  CredentialHandles.mk_policy 4 8 2 5 4 (fun _ _ => 4)
    (fun role op => ((role =? 1) && (op =? 2)) || ((role =? 2) && (op =? 2)) || ((role =? 3) && (op =? 3)))
    (fun _ _ => false) (fun exp now => now <? exp) Nat.leb.

Definition ex_cred_src : CredentialHandles.Credential :=
  CredentialHandles.mk_credential 1 5 [0] [2] 1 1 20 1.
Definition ex_cred_recv : CredentialHandles.Credential :=
  CredentialHandles.mk_credential 2 5 [0] [2] 1 1 20 2.
Definition ex_cred_enr : CredentialHandles.Credential :=
  CredentialHandles.mk_credential 3 5 [1] [3] 1 1 20 3.
Definition ex_cred_srv : CredentialHandles.ServerState :=
  CredentialHandles.mk_server (fun _ => 0) 1 (fun _ _ _ => true).

Definition ex_req_src : CredentialHandles.ClientRequest :=
  CredentialHandles.mk_request 1 5 0 2 1 [1].
Definition ex_req_recv : CredentialHandles.ClientRequest :=
  CredentialHandles.mk_request 2 5 0 2 1 [1].
Definition ex_req_enr : CredentialHandles.ClientRequest :=
  CredentialHandles.mk_request 3 5 1 3 1 [1].

Definition mig_iss_recv : MigrationIssuance :=
  {| mi_quote := {| ev_id := 1; ev_role := MigrationReceiver; ev_generation := 7;
                    ev_ref_manifest := 8; ev_exporter := 11;
                    ev_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
                    ev_principal := 5; ev_roots := [3; 4];
                    ev_bound_receiver_quote := None; ev_enrolled_recipient := None |};
     mi_issuer_ctx := ctx_r1 |}.

Definition mig_iss_src : MigrationIssuance :=
  {| mi_quote := {| ev_id := 2; ev_role := MigrationSource; ev_generation := 7;
                    ev_ref_manifest := 8; ev_exporter := 11;
                    ev_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
                    ev_principal := 5; ev_roots := [];
                    ev_bound_receiver_quote := Some 1; ev_enrolled_recipient := None |};
     mi_issuer_ctx := ctx_s1 |}.

Example broker_issues_migration_and_enrollment_quotes_and_consumes_uses :
  quote_local ex_profile ex_cred_policy ex_cred_recv ex_cred_srv ex_req_recv ctx_r1 1
    (att_recv_challenge mig_att_opened) ex_runtime None =
    Some (mig_iss_recv, CredentialHandles.charge ex_cred_srv 2) /\
  quote_local ex_profile ex_cred_policy ex_cred_src ex_cred_srv ex_req_src ctx_s1 2
    (att_src_challenge mig_att_opened) ex_runtime (Some 1) =
    Some (mig_iss_src, CredentialHandles.charge ex_cred_srv 1) /\
  quote_local ex_profile ex_cred_policy ex_cred_recv
    (CredentialHandles.charge ex_cred_srv 2) ex_req_recv ctx_r1 1
    (att_recv_challenge mig_att_opened) ex_runtime None = None /\
  quote_local ex_profile ex_cred_policy ex_cred_enr ex_cred_srv ex_req_enr ctx_r1 1
    (att_recv_challenge mig_att_opened) ex_runtime None = None.
Proof. vm_compute; repeat split; reflexivity. Qed.

Definition ledger_auth (ledger : list MigrationIssuance) (q : MigrationQuote) : bool :=
  existsb (fun iss => quote_eqb (mi_quote iss) q) ledger.

Theorem ledger_auth_is_inhabited : forall ledger,
  EvidenceAuthenticity (ledger_auth ledger) ledger True.
Proof.
  intros ledger _ q H. apply existsb_exists in H as [iss [Hin Heq]].
  apply quote_eqb_sound in Heq. exists iss. split; assumption.
Qed.

Definition mig_auth := ledger_auth [mig_iss_recv; mig_iss_src].

Definition mig_cw : ConsentWitness :=
  {| cw_channel_id := 1; cw_roots := [3; 4]; cw_source_profile := 1;
     cw_profile_map := 1; cw_schema_plan := 1;
     cw_source_cred := true; cw_receiver_cred := true |}.

Definition mig_restore_payload : RestorePayload :=
  {| rp_manifest_auth := true; rp_source_profile := 1; rp_profile_map := 1;
     rp_schema_plan := 1; rp_all_schemas_decided := true;
     rp_chunks_verified := true; rp_coverage_complete := true;
     rp_staged_digest := 8 |}.

Definition mig_att_recv_app : MigrationAttempt :=
  {| att_mode := ModeMigration; att_src_ctx := ctx_s1; att_recv_ctx := ctx_r1;
     att_phase := PhReceiverAppraised;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [1; 2]; att_used_contexts := [1; 2];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote mig_iss_recv);
     att_accepted_src_quote := None; att_confirmed_roots := None;
     att_source_cred := false; att_receiver_cred := false; att_consent := None;
     att_volatile := empty_volatile; att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition mig_att_mut_app : MigrationAttempt :=
  {| att_mode := ModeMigration; att_src_ctx := ctx_s1; att_recv_ctx := ctx_r1;
     att_phase := PhMutuallyAppraised;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [1; 2]; att_used_contexts := [1; 2];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote mig_iss_recv);
     att_accepted_src_quote := Some (mi_quote mig_iss_src);
     att_confirmed_roots := None;
     att_source_cred := false; att_receiver_cred := false; att_consent := None;
     att_volatile := empty_volatile; att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition mig_att_confirmed : MigrationAttempt :=
  {| att_mode := ModeMigration; att_src_ctx := ctx_s1; att_recv_ctx := ctx_r1;
     att_phase := PhRootsConfirmed;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [1; 2]; att_used_contexts := [1; 2];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote mig_iss_recv);
     att_accepted_src_quote := Some (mi_quote mig_iss_src);
     att_confirmed_roots := Some [3; 4];
     att_source_cred := true; att_receiver_cred := true; att_consent := Some mig_cw;
     att_volatile := empty_volatile; att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition mig_att_transferred : MigrationAttempt :=
  {| att_mode := ModeMigration; att_src_ctx := ctx_s1; att_recv_ctx := ctx_r1;
     att_phase := PhTransferred;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [1; 2]; att_used_contexts := [1; 2];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote mig_iss_recv);
     att_accepted_src_quote := Some (mi_quote mig_iss_src);
     att_confirmed_roots := Some [3; 4];
     att_source_cred := true; att_receiver_cred := true; att_consent := Some mig_cw;
     att_volatile := {| vb_object_bytes := 12; vb_has_object := true; vb_has_object_key := true |};
     att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition mig_att_prepared : MigrationAttempt :=
  {| att_mode := ModeMigration; att_src_ctx := ctx_s1; att_recv_ctx := ctx_r1;
     att_phase := PhRestorePrepared;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [1; 2]; att_used_contexts := [1; 2];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote mig_iss_recv);
     att_accepted_src_quote := Some (mi_quote mig_iss_src);
     att_confirmed_roots := Some [3; 4];
     att_source_cred := true; att_receiver_cred := true; att_consent := Some mig_cw;
     att_volatile := {| vb_object_bytes := 12; vb_has_object := true; vb_has_object_key := true |};
     att_storage := ex_storage_staged; att_wrapped_key := None |}.

Definition mig_att_published : MigrationAttempt :=
  {| att_mode := ModeMigration; att_src_ctx := ctx_s1; att_recv_ctx := ctx_r1;
     att_phase := PhPublished;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [1; 2]; att_used_contexts := [1; 2];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote mig_iss_recv);
     att_accepted_src_quote := Some (mi_quote mig_iss_src);
     att_confirmed_roots := Some [3; 4];
     att_source_cred := false; att_receiver_cred := false; att_consent := None;
     att_volatile := empty_volatile; att_storage := ex_storage_published; att_wrapped_key := None |}.

Example mig_transition_chain_matches_executable_steps :
  open_attempt ex_profile ModeMigration (make_idle_attempt ModeMigration ctx_s1 ctx_r1) 1 2 0 10 10 = mig_att_opened /\
  appraise_peer ex_profile ex_mig_pol mig_auth mig_att_opened MigrationReceiver (mi_quote mig_iss_recv) 1 8 = (mig_att_recv_app, true) /\
  appraise_peer ex_profile ex_mig_pol mig_auth mig_att_recv_app MigrationSource (mi_quote mig_iss_src) 1 8 = (mig_att_mut_app, true) /\
  confirm_roots ex_profile mig_att_mut_app [3; 4] mig_cw = (mig_att_confirmed, true) /\
  transfer_backup ex_profile mig_att_confirmed 12 = (mig_att_transferred, true) /\
  prepare_restore mig_att_transferred mig_restore_payload = (mig_att_prepared, true) /\
  publish_restore mig_att_prepared = (mig_att_published, true).
Proof. vm_compute; repeat split; reflexivity. Qed.

Definition honest_migration_trace : MigrationTrace := [
  EvOpen mig_att_opened 1 2;
  EvQuote mig_iss_recv;
  EvAppraise mig_att_opened MigrationReceiver (mi_quote mig_iss_recv) 1 8;
  EvQuote mig_iss_src;
  EvAppraise mig_att_recv_app MigrationSource (mi_quote mig_iss_src) 1 8;
  EvConfirmRoots mig_att_mut_app [3; 4] mig_cw;
  EvTransfer mig_att_confirmed 5 12;
  EvPrepareRestore mig_att_transferred mig_restore_payload;
  EvPublish mig_att_prepared;
  EvClose mig_att_published
].

(* Positive enrollment session concrete reduced records *)
Definition enr_att_opened : MigrationAttempt :=
  {| att_mode := ModeEnrollment;
     att_src_ctx := ctx_s_enr;
     att_recv_ctx := ctx_r_enr;
     att_phase := PhOpened;
     att_recv_challenge := make_challenge 3 MigrationSource BackupKeyEnrollment true;
     att_src_challenge := make_challenge 4 BackupKeyEnrollment MigrationSource false;
     att_recv_deadline := 10;
     att_src_deadline := 10;
     att_used_nonces := [3; 4];
     att_used_contexts := [5; 6];
     att_source_profile := 1;
     att_profile_map := 1;
     att_schema_plan := 1;
     att_accepted_recv_quote := None;
     att_accepted_src_quote := None;
     att_confirmed_roots := None;
     att_source_cred := false;
     att_receiver_cred := false;
     att_consent := None;
     att_volatile := empty_volatile;
     att_storage := ex_storage_init;
     att_wrapped_key := None |}.

Definition enr_iss_recv : MigrationIssuance :=
  {| mi_quote := {| ev_id := 3; ev_role := BackupKeyEnrollment; ev_generation := 7;
                    ev_ref_manifest := 8; ev_exporter := 13;
                    ev_challenge := make_challenge 3 MigrationSource BackupKeyEnrollment true;
                    ev_principal := 5; ev_roots := [3; 4];
                    ev_bound_receiver_quote := None; ev_enrolled_recipient := Some 11 |};
     mi_issuer_ctx := ctx_r_enr |}.

Definition enr_iss_src : MigrationIssuance :=
  {| mi_quote := {| ev_id := 4; ev_role := MigrationSource; ev_generation := 7;
                    ev_ref_manifest := 8; ev_exporter := 13;
                    ev_challenge := make_challenge 4 BackupKeyEnrollment MigrationSource false;
                    ev_principal := 5; ev_roots := [];
                    ev_bound_receiver_quote := Some 3; ev_enrolled_recipient := None |};
     mi_issuer_ctx := ctx_s_enr |}.

Definition enr_auth := ledger_auth [enr_iss_recv; enr_iss_src].

Definition enr_cw : ConsentWitness :=
  {| cw_channel_id := 3; cw_roots := [3; 4]; cw_source_profile := 1;
     cw_profile_map := 1; cw_schema_plan := 1;
     cw_source_cred := true; cw_receiver_cred := true |}.

Definition enr_att_recv_app : MigrationAttempt :=
  {| att_mode := ModeEnrollment; att_src_ctx := ctx_s_enr; att_recv_ctx := ctx_r_enr;
     att_phase := PhReceiverAppraised;
     att_recv_challenge := make_challenge 3 MigrationSource BackupKeyEnrollment true;
     att_src_challenge := make_challenge 4 BackupKeyEnrollment MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [3; 4]; att_used_contexts := [5; 6];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote enr_iss_recv);
     att_accepted_src_quote := None; att_confirmed_roots := None;
     att_source_cred := false; att_receiver_cred := false; att_consent := None;
     att_volatile := empty_volatile; att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition enr_att_mut_app : MigrationAttempt :=
  {| att_mode := ModeEnrollment; att_src_ctx := ctx_s_enr; att_recv_ctx := ctx_r_enr;
     att_phase := PhMutuallyAppraised;
     att_recv_challenge := make_challenge 3 MigrationSource BackupKeyEnrollment true;
     att_src_challenge := make_challenge 4 BackupKeyEnrollment MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [3; 4]; att_used_contexts := [5; 6];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote enr_iss_recv);
     att_accepted_src_quote := Some (mi_quote enr_iss_src);
     att_confirmed_roots := None;
     att_source_cred := false; att_receiver_cred := false; att_consent := None;
     att_volatile := empty_volatile; att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition enr_att_confirmed : MigrationAttempt :=
  {| att_mode := ModeEnrollment; att_src_ctx := ctx_s_enr; att_recv_ctx := ctx_r_enr;
     att_phase := PhRootsConfirmed;
     att_recv_challenge := make_challenge 3 MigrationSource BackupKeyEnrollment true;
     att_src_challenge := make_challenge 4 BackupKeyEnrollment MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [3; 4]; att_used_contexts := [5; 6];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote enr_iss_recv);
     att_accepted_src_quote := Some (mi_quote enr_iss_src);
     att_confirmed_roots := Some [3; 4];
     att_source_cred := true; att_receiver_cred := true; att_consent := Some enr_cw;
     att_volatile := empty_volatile; att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition enr_att_wrapped : MigrationAttempt :=
  {| att_mode := ModeEnrollment; att_src_ctx := ctx_s_enr; att_recv_ctx := ctx_r_enr;
     att_phase := PhWrapped;
     att_recv_challenge := make_challenge 3 MigrationSource BackupKeyEnrollment true;
     att_src_challenge := make_challenge 4 BackupKeyEnrollment MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [3; 4]; att_used_contexts := [5; 6];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := Some (mi_quote enr_iss_recv);
     att_accepted_src_quote := Some (mi_quote enr_iss_src);
     att_confirmed_roots := Some [3; 4];
     att_source_cred := false; att_receiver_cred := false; att_consent := None;
     att_volatile := empty_volatile; att_storage := ex_storage_init;
     att_wrapped_key := Some {| wk_recipient := 11; wk_object_id := 5;
                                wk_use_restore_only := true; wk_locally_sealed := true |} |}.

Example enr_transition_chain_matches_executable_steps :
  open_attempt ex_profile ModeEnrollment (make_idle_attempt ModeEnrollment ctx_s_enr ctx_r_enr) 3 4 0 10 10 = enr_att_opened /\
  appraise_peer ex_profile ex_enr_recv_pol enr_auth enr_att_opened BackupKeyEnrollment (mi_quote enr_iss_recv) 1 8 = (enr_att_recv_app, true) /\
  appraise_peer ex_profile ex_mig_pol enr_auth enr_att_recv_app MigrationSource (mi_quote enr_iss_src) 1 8 = (enr_att_mut_app, true) /\
  confirm_roots ex_profile enr_att_mut_app [3; 4] enr_cw = (enr_att_confirmed, true) /\
  wrap_recovery_key enr_att_confirmed 5 11 = (enr_att_wrapped, true).
Proof. vm_compute; repeat split; reflexivity. Qed.

Definition honest_enrollment_trace : MigrationTrace := [
  EvOpen enr_att_opened 3 4;
  EvQuote enr_iss_recv;
  EvAppraise enr_att_opened BackupKeyEnrollment (mi_quote enr_iss_recv) 1 8;
  EvQuote enr_iss_src;
  EvAppraise enr_att_recv_app MigrationSource (mi_quote enr_iss_src) 1 8;
  EvConfirmRoots enr_att_mut_app [3; 4] enr_cw;
  EvWrapKey enr_att_confirmed 5 11;
  EvClose enr_att_wrapped
].

Definition ex_custody (c : ProtectedContext) : Prop :=
  c = ctx_s1 \/ c = ctx_r1 \/ c = ctx_s2 \/ c = ctx_r2 \/
  c = ctx_s_enr \/ c = ctx_r_enr \/ c = ctx_r_mitm_leg2.

Theorem ex_exporter_security : ExporterSecurity ex_custody.
Proof.
  intros a b Ha Hb Hca Hcb Hexp Hrole.
  destruct Hca as [H|[H|[H|[H|[H|[H|H]]]]]]; subst a;
    destruct Hcb as [H2|[H2|[H2|[H2|[H2|[H2|H2]]]]]]; subst b;
      try discriminate Hexp; try discriminate Hrole;
      unfold SameKeyHolder; repeat split; reflexivity.
Qed.

Theorem ex_root_faithfulness : RootSetFaithfulness ex_runtime ex_actual_roots.
Proof.
  intros u roots H. unfold ex_runtime in H. cbn in H.
  destruct u as [|[|[|[|[|u]]]]]; try discriminate H;
    inversion H; reflexivity.
Qed.

Definition env_honest_mig : MigrationEnv :=
  {| me_profile := ex_profile;
     me_runtime := ex_runtime;
     me_actual_roots := ex_actual_roots;
     me_auth := mig_auth;
     me_custody := ex_custody;
     me_recv_pol := ex_mig_pol;
     me_src_pol := ex_mig_pol |}.

Definition env_honest_enr : MigrationEnv :=
  {| me_profile := ex_profile;
     me_runtime := ex_runtime;
     me_actual_roots := ex_actual_roots;
     me_auth := enr_auth;
     me_custody := ex_custody;
     me_recv_pol := ex_enr_recv_pol;
     me_src_pol := ex_mig_pol |}.

Lemma honest_mig_bundle_fresh :
  bundle_fresh honest_migration_trace mig_att_opened 1 2.
Proof.
  split; [lia|]. split; [lia|]. split; [lia|].
  exists 0. split; [reflexivity|]. split.
  - intros j att' rn' sn' Hj _.
    destruct j as [|j]; [cbn [nth_error honest_migration_trace] in Hj; inversion Hj; repeat split; reflexivity|].
    do 9 (destruct j as [|j]; [cbn [nth_error honest_migration_trace] in Hj; discriminate Hj|]).
    cbn [nth_error honest_migration_trace] in Hj. destruct j; discriminate Hj.
  - intros m iss Hm _ Hor.
    do 10 (destruct m as [|m]; [cbn [nth_error honest_migration_trace] in Hm; try discriminate Hm; inversion Hm; subst;
      try lia; destruct Hor as [Hc|Hc]; discriminate Hc|]).
    cbn [nth_error honest_migration_trace] in Hm. destruct m; discriminate Hm.
Qed.

Lemma honest_enr_bundle_fresh :
  bundle_fresh honest_enrollment_trace enr_att_opened 3 4.
Proof.
  split; [lia|]. split; [lia|]. split; [lia|].
  exists 0. split; [reflexivity|]. split.
  - intros j att' rn' sn' Hj _.
    destruct j as [|j]; [cbn [nth_error honest_enrollment_trace] in Hj; inversion Hj; repeat split; reflexivity|].
    do 7 (destruct j as [|j]; [cbn [nth_error honest_enrollment_trace] in Hj; discriminate Hj|]).
    cbn [nth_error honest_enrollment_trace] in Hj. destruct j; discriminate Hj.
  - intros m iss Hm _ Hor.
    do 8 (destruct m as [|m]; [cbn [nth_error honest_enrollment_trace] in Hm; try discriminate Hm; inversion Hm; subst;
      try lia; destruct Hor as [Hc|Hc]; discriminate Hc|]).
    cbn [nth_error honest_enrollment_trace] in Hm. destruct m; discriminate Hm.
Qed.

Lemma ex_lci_mig_recv : LocalContextIntegrity ex_profile [mig_iss_recv] ex_runtime.
Proof.
  intros e [He|[]]; subst e.
  unfold LocalContextIntegrity. cbn.
  repeat match goal with |- _ /\ _ => split end;
    try reflexivity; try lia; intro Hr;
    try discriminate Hr; [cbn; split; reflexivity].
Qed.

Lemma ex_lci_mig_src : LocalContextIntegrity ex_profile [mig_iss_src] ex_runtime.
Proof.
  intros e [He|[]]; subst e.
  unfold LocalContextIntegrity. cbn.
  repeat match goal with |- _ /\ _ => split end;
    try reflexivity; try lia; intro Hr;
    try discriminate Hr; intro Hn; discriminate Hn.
Qed.

Lemma ex_lci_enr_recv : LocalContextIntegrity ex_profile [enr_iss_recv] ex_runtime.
Proof.
  intros e [He|[]]; subst e.
  unfold LocalContextIntegrity. cbn.
  repeat match goal with |- _ /\ _ => split end;
    try reflexivity; try lia; intro Hr;
    try discriminate Hr; [cbn; repeat split; reflexivity].
Qed.

Lemma ex_lci_enr_src : LocalContextIntegrity ex_profile [enr_iss_src] ex_runtime.
Proof.
  intros e [He|[]]; subst e.
  unfold LocalContextIntegrity. cbn.
  repeat match goal with |- _ /\ _ => split end;
    try reflexivity; try lia; intro Hr;
    try discriminate Hr; intro Hn; discriminate Hn.
Qed.

Theorem honest_migration_trace_is_sound :
  TraceSound env_honest_mig honest_migration_trace /\
  NoKeyExposure honest_migration_trace /\
  NoIssuerCompromise honest_migration_trace /\
  HonestTrustedPath True honest_migration_trace /\
  LocalContextIntegrity ex_profile (trace_issuances honest_migration_trace) ex_runtime /\
  UncompromisedKeys ex_custody (trace_issuances honest_migration_trace) ctx_s1 ctx_r1.
Proof.
  unfold TraceSound, UncompromisedKeys.
  repeat match goal with |- _ /\ _ => split end.
  - intros i att rn sn H.
    destruct i as [|i]; [cbn [nth_error honest_migration_trace] in H; inversion H; subst;
      repeat match goal with |- _ /\ _ => split end;
      try (vm_compute; reflexivity);
      try (cbn [me_custody env_honest_mig att_src_ctx att_recv_ctx]; unfold ex_custody; auto 8);
      exact honest_mig_bundle_fresh|].
    do 9 (destruct i as [|i]; [cbn [nth_error honest_migration_trace] in H; discriminate H|]).
    cbn [nth_error honest_migration_trace] in H. destruct i; discriminate H.
  - intros iss H _. cbn [In honest_migration_trace] in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]]]; try discriminate H;
      inversion H; subst;
      [split; [exact ex_lci_mig_recv | cbn [me_custody env_honest_mig mi_issuer_ctx]; unfold ex_custody; auto 8]
      |split; [exact ex_lci_mig_src | cbn [me_custody env_honest_mig mi_issuer_ctx]; unfold ex_custody; auto 8]].
  - intros k att role q now sz H.
    destruct k as [|[|[|[|[|[|[|[|[|[|k]]]]]]]]]];
      cbn [nth_error honest_migration_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|].
      split; [intro; exists 0, 1, 2; split; [lia|reflexivity]|].
      intro Hd; discriminate Hd.
    + inversion H; subst. split; [vm_compute; reflexivity|].
      split; [intro Hd; discriminate Hd|].
      intro; exists 2, mig_att_opened, (mi_quote mig_iss_recv), 1, 8.
      repeat split; try reflexivity; lia.
    + destruct k; discriminate H.
  - intros i_c att roots cw H.
    destruct i_c as [|[|[|[|[|[|[|[|[|[|i_c]]]]]]]]]];
      cbn [nth_error honest_migration_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|].
      exists 4, mig_att_recv_app, (mi_quote mig_iss_src), 1, 8.
      repeat split; try reflexivity; lia.
    + destruct i_c; discriminate H.
  - intros i_tr att oid obytes H.
    destruct i_tr as [|[|[|[|[|[|[|[|[|[|i_tr]]]]]]]]]];
      cbn [nth_error honest_migration_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|]. split; [reflexivity|]. split; [reflexivity|].
      exists 5, mig_att_mut_app, [3; 4], mig_cw. repeat split; try reflexivity; lia.
    + destruct i_tr; discriminate H.
  - intros i_pr att rp H.
    destruct i_pr as [|[|[|[|[|[|[|[|[|[|i_pr]]]]]]]]]];
      cbn [nth_error honest_migration_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|]. split; [reflexivity|]. split; [reflexivity|].
      exists 6, mig_att_confirmed, 5, 12. repeat split; try reflexivity; lia.
    + destruct i_pr; discriminate H.
  - intros i_pub att H.
    destruct i_pub as [|[|[|[|[|[|[|[|[|[|i_pub]]]]]]]]]];
      cbn [nth_error honest_migration_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|]. split; [reflexivity|]. split; [reflexivity|].
      exists 7, mig_att_transferred, mig_restore_payload. repeat split; try reflexivity; lia.
    + destruct i_pub; discriminate H.
  - intros i_w att oid rec H.
    destruct i_w as [|[|[|[|[|[|[|[|[|[|i_w]]]]]]]]]];
      cbn [nth_error honest_migration_trace] in H; try discriminate H.
    destruct i_w; discriminate H.
  - intros k m att role q now sz iss Hk Hm _ Hev. subst q.
    destruct k as [|[|[|[|[|k]]]]]; try (cbn [nth_error honest_migration_trace] in Hk; discriminate Hk).
    + cbn [nth_error honest_migration_trace] in Hk.
      destruct m as [|[|[|[|m]]]]; cbn [nth_error honest_migration_trace] in Hm; try discriminate Hm.
      * lia.
      * inversion Hm; subst iss. inversion Hk.
      * destruct m as [|[|[|[|[|[|m]]]]]]; cbn [nth_error honest_migration_trace] in Hm;
          try discriminate Hm; destruct m; discriminate Hm.
    + cbn [nth_error honest_migration_trace] in Hk.
      destruct m as [|[|[|[|m]]]]; cbn [nth_error honest_migration_trace] in Hm; try discriminate Hm.
      * inversion Hm; subst iss. inversion Hk.
      * lia.
      * destruct m as [|[|[|[|[|[|m]]]]]]; cbn [nth_error honest_migration_trace] in Hm;
          try discriminate Hm; destruct m; discriminate Hm.
    + destruct k as [|[|[|[|[|k]]]]]; cbn [nth_error honest_migration_trace] in Hk;
        try discriminate Hk; destruct k; discriminate Hk.
  - intros m iss qid i_ra att_r q_r now_r sz_r Hm _ Hbound Hra Hid.
    destruct m as [|[|[|[|[|[|[|[|[|[|m]]]]]]]]]];
      cbn [nth_error honest_migration_trace] in Hm; try discriminate Hm.
    + inversion Hm; subst iss. discriminate Hbound.
    + inversion Hm; subst iss. inversion Hbound.
      destruct i_ra as [|[|[|[|[|[|[|[|[|[|i_ra]]]]]]]]]];
        cbn [nth_error honest_migration_trace] in Hra; try discriminate Hra.
      * lia.
      * inversion Hra; subst att_r.
        match goal with Heq : MigrationSource = expected_recv_role (att_mode mig_att_recv_app) |- _ =>
          vm_compute in Heq; discriminate Heq end.
      * destruct i_ra; discriminate Hra.
    + destruct m; discriminate Hm.
  - intros ctx sender H.
    cbn [In honest_migration_trace] in H. destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]]]; discriminate H.
  - intros u H.
    cbn [In honest_migration_trace] in H. destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]]]; discriminate H.
  - intros _ att roots cw H.
    cbn [In honest_migration_trace] in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]]]; try discriminate H;
      inversion H; subst; repeat split; try reflexivity; discriminate.
  - intros iss Hin. cbn [trace_issuances In honest_migration_trace] in Hin.
    destruct Hin as [H|[H|[]]]; subst iss;
      [apply (ex_lci_mig_recv mig_iss_recv (or_introl eq_refl))
      |apply (ex_lci_mig_src mig_iss_src (or_introl eq_refl))].
  - unfold ex_custody. auto 8.
  - unfold ex_custody. auto 8.
  - intros iss Hin. cbn [trace_issuances In honest_migration_trace] in Hin.
    destruct Hin as [H|[H|[]]]; subst iss; unfold ex_custody; auto 8.
Qed.

Theorem honest_enrollment_trace_is_sound :
  TraceSound env_honest_enr honest_enrollment_trace /\
  NoKeyExposure honest_enrollment_trace /\
  NoIssuerCompromise honest_enrollment_trace /\
  HonestTrustedPath True honest_enrollment_trace /\
  LocalContextIntegrity ex_profile (trace_issuances honest_enrollment_trace) ex_runtime /\
  EnrollmentPolicyBinding ex_enr_recv_pol ex_runtime ctx_r_enr /\
  UncompromisedKeys ex_custody (trace_issuances honest_enrollment_trace) ctx_s_enr ctx_r_enr.
Proof.
  unfold TraceSound, UncompromisedKeys.
  repeat match goal with |- _ /\ _ => split end.
  - intros i att rn sn H.
    destruct i as [|i]; [cbn [nth_error honest_enrollment_trace] in H; inversion H; subst;
      repeat match goal with |- _ /\ _ => split end;
      try (vm_compute; reflexivity);
      try (cbn [me_custody env_honest_enr att_src_ctx att_recv_ctx]; unfold ex_custody; auto 8);
      exact honest_enr_bundle_fresh|].
    do 7 (destruct i as [|i]; [cbn [nth_error honest_enrollment_trace] in H; discriminate H|]).
    cbn [nth_error honest_enrollment_trace] in H. destruct i; discriminate H.
  - intros iss H _. cbn [In honest_enrollment_trace] in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; try discriminate H;
      inversion H; subst;
      [split; [exact ex_lci_enr_recv | cbn [me_custody env_honest_enr mi_issuer_ctx]; unfold ex_custody; auto 8]
      |split; [exact ex_lci_enr_src | cbn [me_custody env_honest_enr mi_issuer_ctx]; unfold ex_custody; auto 8]].
  - intros k att role q now sz H.
    destruct k as [|[|[|[|[|[|[|[|k]]]]]]]];
      cbn [nth_error honest_enrollment_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|].
      split; [intro; exists 0, 3, 4; split; [lia|reflexivity]|].
      intro Hd; discriminate Hd.
    + inversion H; subst. split; [vm_compute; reflexivity|].
      split; [intro Hd; discriminate Hd|].
      intro; exists 2, enr_att_opened, (mi_quote enr_iss_recv), 1, 8.
      repeat split; try reflexivity; lia.
    + destruct k; discriminate H.
  - intros i_c att roots cw H.
    destruct i_c as [|[|[|[|[|[|[|[|i_c]]]]]]]];
      cbn [nth_error honest_enrollment_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|].
      exists 4, enr_att_recv_app, (mi_quote enr_iss_src), 1, 8.
      repeat split; try reflexivity; lia.
    + destruct i_c; discriminate H.
  - intros i_tr att oid obytes H.
    destruct i_tr as [|[|[|[|[|[|[|[|i_tr]]]]]]]];
      cbn [nth_error honest_enrollment_trace] in H; try discriminate H.
    destruct i_tr; discriminate H.
  - intros i_pr att rp H.
    destruct i_pr as [|[|[|[|[|[|[|[|i_pr]]]]]]]];
      cbn [nth_error honest_enrollment_trace] in H; try discriminate H.
    destruct i_pr; discriminate H.
  - intros i_pub att H.
    destruct i_pub as [|[|[|[|[|[|[|[|i_pub]]]]]]]];
      cbn [nth_error honest_enrollment_trace] in H; try discriminate H.
    destruct i_pub; discriminate H.
  - intros i_w att oid rec H.
    destruct i_w as [|[|[|[|[|[|[|[|i_w]]]]]]]];
      cbn [nth_error honest_enrollment_trace] in H; try discriminate H.
    + inversion H; subst. split; [vm_compute; reflexivity|]. split; [reflexivity|]. split; [reflexivity|].
      exists 5, enr_att_mut_app, [3; 4], enr_cw. repeat split; try reflexivity; lia.
    + destruct i_w; discriminate H.
  - intros k m att role q now sz iss Hk Hm _ Hev. subst q.
    destruct k as [|[|[|[|[|k]]]]]; try (cbn [nth_error honest_enrollment_trace] in Hk; discriminate Hk).
    + cbn [nth_error honest_enrollment_trace] in Hk.
      destruct m as [|[|[|[|m]]]]; cbn [nth_error honest_enrollment_trace] in Hm; try discriminate Hm.
      * lia.
      * inversion Hm; subst iss. inversion Hk.
      * destruct m as [|[|[|[|m]]]]; cbn [nth_error honest_enrollment_trace] in Hm;
          try discriminate Hm; destruct m; discriminate Hm.
    + cbn [nth_error honest_enrollment_trace] in Hk.
      destruct m as [|[|[|[|m]]]]; cbn [nth_error honest_enrollment_trace] in Hm; try discriminate Hm.
      * inversion Hm; subst iss. inversion Hk.
      * lia.
      * destruct m as [|[|[|[|m]]]]; cbn [nth_error honest_enrollment_trace] in Hm;
          try discriminate Hm; destruct m; discriminate Hm.
    + destruct k as [|[|[|k]]]; cbn [nth_error honest_enrollment_trace] in Hk;
        try discriminate Hk; destruct k; discriminate Hk.
  - intros m iss qid i_ra att_r q_r now_r sz_r Hm _ Hbound Hra Hid.
    destruct m as [|[|[|[|[|[|[|[|m]]]]]]]];
      cbn [nth_error honest_enrollment_trace] in Hm; try discriminate Hm.
    + inversion Hm; subst iss. discriminate Hbound.
    + inversion Hm; subst iss. inversion Hbound.
      destruct i_ra as [|[|[|[|[|[|[|[|i_ra]]]]]]]];
        cbn [nth_error honest_enrollment_trace] in Hra; try discriminate Hra.
      * lia.
      * inversion Hra; subst att_r.
        match goal with Heq : MigrationSource = expected_recv_role (att_mode enr_att_recv_app) |- _ =>
          vm_compute in Heq; discriminate Heq end.
      * destruct i_ra; discriminate Hra.
    + destruct m; discriminate Hm.
  - intros ctx sender H. cbn [In honest_enrollment_trace] in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; discriminate H.
  - intros u H. cbn [In honest_enrollment_trace] in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; discriminate H.
  - intros _ att roots cw H. cbn [In honest_enrollment_trace] in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; try discriminate H;
      inversion H; subst; repeat split; try reflexivity; discriminate.
  - intros iss Hin. cbn [trace_issuances In honest_enrollment_trace] in Hin.
    destruct Hin as [H|[H|[]]]; subst iss;
      [apply (ex_lci_enr_recv enr_iss_recv (or_introl eq_refl))
      |apply (ex_lci_enr_src enr_iss_src (or_introl eq_refl))].
  - intros exp Hexp Hrt. cbn in Hexp, Hrt. inversion Hexp; subst exp. reflexivity.
  - unfold ex_custody. auto 8.
  - unfold ex_custody. auto 8.
  - intros iss Hin. cbn [trace_issuances In honest_enrollment_trace] in Hin.
    destruct Hin as [H|[H|[]]]; subst iss; unfold ex_custody; auto 8.
Qed.

Theorem inhabited_migration_discharges_transfer_and_publish_agreement :
  (exists iss_recv iss_src i_open i_rq i_ra i_sq i_sa i_c,
     i_open < i_rq /\ i_rq < i_ra /\ i_ra < i_sq /\ i_sq < i_sa /\ i_sa < i_c /\ i_c < 6 /\
     SameKeyHolder (mi_issuer_ctx iss_recv) ctx_r1 /\
     SameKeyHolder (mi_issuer_ctx iss_src) ctx_s1 /\
     st_retained_backup_objects (att_storage mig_att_confirmed) = 0 /\
     st_retained_key_capsules (att_storage mig_att_confirmed) = 0) /\
  (st_current_regions_digest (att_storage mig_att_published) = 8 /\
   st_unreachable_staging_digest (att_storage mig_att_published) = None /\
   att_volatile mig_att_published = empty_volatile /\
   att_consent mig_att_published = None /\
   st_retained_backup_objects (att_storage mig_att_published) = 0 /\
   st_retained_key_capsules (att_storage mig_att_published) = 0) /\
  (exists iss_recv iss_src,
     ev_role (mi_quote iss_recv) = BackupKeyEnrollment /\
     ev_role (mi_quote iss_src) = MigrationSource /\
     ev_enrolled_recipient (mi_quote iss_recv) = Some 11 /\
     att_wrapped_key enr_att_wrapped =
       Some {| wk_recipient := 11; wk_object_id := 5;
               wk_use_restore_only := true; wk_locally_sealed := true |} /\
     snd (transfer_backup ex_profile enr_att_confirmed 12) = false).
Proof.
  destruct honest_migration_trace_is_sound as [Hs [Hnk [Hni [Htp [Hloc Hkeys]]]]].
  destruct honest_enrollment_trace_is_sound as [Hs_e [Hnk_e [Hni_e [Htp_e [Hloc_e [Henr_e Hkeys_e]]]]]].
  split.
  - destruct (migration_transfer_agreement env_honest_mig honest_migration_trace
                True True mig_att_confirmed 5 12 6
                Hs Hnk Hni ex_exporter_security
                (ledger_auth_is_inhabited _) I Hloc ex_root_faithfulness Htp I Hkeys eq_refl)
      as [ir [isrc [io [irq [ira [isq [isa [ic [rq [sq [cr [cw Hrem]]]]]]]]]]]].
    destruct Hrem as [H1 [H2 [H3 [H4 [H5 [H6 [_ [_ [_ [_ [_ [_ [Hhr [Hhs [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [Hr0 Hc0]]]]]]]]]]]]]]]]]]]]]]]]].
    exists ir, isrc, io, irq, ira, isq, isa, ic.
    split; [exact H1|split; [exact H2|split; [exact H3|split; [exact H4|split; [exact H5|split; [exact H6|split; [exact Hhr|split; [exact Hhs|split; [exact Hr0|exact Hc0]]]]]]]]].
  - split.
    + destruct (migration_publish_agreement env_honest_mig honest_migration_trace
                  True True mig_att_prepared 8
                  Hs Hnk Hni ex_exporter_security
                  (ledger_auth_is_inhabited _) I Hloc ex_root_faithfulness Htp I
                  (conj (proj1 Hkeys) (conj (proj1 (proj2 Hkeys)) (proj2 (proj2 Hkeys))))
                  eq_refl)
        as [attt [attp [oid [obytes [rp [ir [isrc [io [irq [ira [isq [isa [ic [it [ip [rq [sq [cr [next_att Hrem_p]]]]]]]]]]]]]]]]]]].
      destruct Hrem_p as [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [Hp1 [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [Hst2 [Hv [Hc [Hr0 Hc0]]]]]]]]]]]]]]]]]]]]]]]]]]]]]].
      destruct mig_transition_chain_matches_executable_steps
        as [_ [_ [_ [_ [_ [_ Hpub_eq]]]]]].
      rewrite Hpub_eq in Hp1. inversion Hp1; subst next_att.
      split; [vm_compute; reflexivity|split; [exact Hst2|split; [exact Hv|split; [exact Hc|split; [exact Hr0|exact Hc0]]]]].
    + destruct (enrollment_key_wrap_agreement env_honest_enr honest_enrollment_trace
                  True True enr_att_confirmed 5 11 6
                  Hs_e Hnk_e Hni_e ex_exporter_security
                  (ledger_auth_is_inhabited _) I Hloc_e ex_root_faithfulness Htp_e I
                  Henr_e Hkeys_e eq_refl)
        as [ir [isrc [io_e [irq_e [ira_e [isq_e [isa_e [ic_e [rq [sq [cr [cw [next_att Hrem_e]]]]]]]]]]]]].
      destruct Hrem_e as [_ [_ [_ [_ [_ [_ [_ [Hwe [Hir [His [Her_r [Her_s [_ [Her_rec [_ [_ [_ [_ [_ [Hwk _]]]]]]]]]]]]]]]]]]]].
      exists ir, isrc.
      split; [rewrite Hir; exact Her_r|
      split; [rewrite His; exact Her_s|
      split; [rewrite Hir; exact Her_rec|
      split; [destruct enr_transition_chain_matches_executable_steps as [_ [_ [_ [_ Hwrap_eq]]]];
              rewrite Hwrap_eq in Hwe; inversion Hwe; subst next_att; exact Hwk|
              apply enrollment_role_cannot_authorize_transfer; left; reflexivity]]]].
Qed.

(* =========================================================================
   8. Section 6 refusal, relay, and broken-premise compromise witnesses
   ========================================================================= *)

(* 8a. Replayed, expired, and already-decided evidence are refused and close *)
Definition stale_recv_quote : MigrationQuote :=
  {| ev_id := 6; ev_role := MigrationReceiver; ev_generation := 7;
     ev_ref_manifest := 8; ev_exporter := 11;
     ev_challenge := make_challenge 9 MigrationSource MigrationReceiver false;
     ev_principal := 5; ev_roots := [3; 4];
     ev_bound_receiver_quote := None; ev_enrolled_recipient := None |}.

(*| discharges: R-12-015c |*)
Example replay_expiry_oversize_and_double_appraisal_are_refused :
  snd (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_opened
         MigrationReceiver stale_recv_quote 1 8) = false /\
  att_phase (fst (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_opened
                    MigrationReceiver stale_recv_quote 1 8)) = PhClosed /\
  snd (appraise_peer ex_profile ex_mig_pol mig_auth mig_att_opened
         MigrationReceiver (mi_quote mig_iss_recv) 10 8) = false /\
  snd (appraise_peer ex_profile ex_mig_pol mig_auth mig_att_opened
         MigrationReceiver (mi_quote mig_iss_recv) 1 17) = false /\
  snd (appraise_peer ex_profile ex_mig_pol mig_auth mig_att_recv_app
         MigrationReceiver (mi_quote mig_iss_recv) 1 8) = false.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8b. Post-restart challenge reuse and spent-context reuse are refused *)
Example post_restart_challenge_and_context_reuse_are_refused :
  att_phase (restart_attempt mig_att_published ctx_s1 ctx_r2) = PhClosed /\
  att_phase (open_attempt ex_profile ModeMigration
               (restart_attempt mig_att_published ctx_s2 ctx_r2) 1 5 0 10 10) = PhClosed /\
  att_phase (open_attempt ex_profile ModeMigration
               (restart_attempt mig_att_published ctx_s2 ctx_r2) 5 6 0 10 10) = PhOpened.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8c. Parallel sessions with repeated nonce symbols:
       Session 2 runs concurrently using the same nonce numbers 1/2 on its
       own fresh channel/exporter (12), while cross-session quote delivery
       between session 1 (exporter 11) and session 2 (exporter 12) is refused. *)
Definition mig2_att_opened : MigrationAttempt :=
  {| att_mode := ModeMigration; att_src_ctx := ctx_s2; att_recv_ctx := ctx_r2;
     att_phase := PhOpened;
     att_recv_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
     att_src_challenge := make_challenge 2 MigrationReceiver MigrationSource false;
     att_recv_deadline := 10; att_src_deadline := 10;
     att_used_nonces := [1; 2]; att_used_contexts := [3; 4];
     att_source_profile := 1; att_profile_map := 1; att_schema_plan := 1;
     att_accepted_recv_quote := None; att_accepted_src_quote := None;
     att_confirmed_roots := None; att_source_cred := false; att_receiver_cred := false;
     att_consent := None; att_volatile := empty_volatile;
     att_storage := ex_storage_init; att_wrapped_key := None |}.

Definition mig2_iss_recv : MigrationIssuance :=
  {| mi_quote := {| ev_id := 5; ev_role := MigrationReceiver; ev_generation := 7;
                    ev_ref_manifest := 8; ev_exporter := 12;
                    ev_challenge := make_challenge 1 MigrationSource MigrationReceiver false;
                    ev_principal := 5; ev_roots := [3; 4];
                    ev_bound_receiver_quote := None; ev_enrolled_recipient := None |};
     mi_issuer_ctx := ctx_r2 |}.

(*| discharges: R-12-015c |*)
Theorem parallel_session_substitution_is_refused :
  forall p pol auth att1 att2 iss2 now sz,
  ctx_exporter (att_src_ctx att1) <> ctx_exporter (att_recv_ctx att2) ->
  ev_exporter (mi_quote iss2) = ctx_exporter (att_recv_ctx att2) ->
  snd (appraise_peer p pol auth att1 (expected_recv_role (att_mode att1)) (mi_quote iss2) now sz) = false.
Proof.
  intros p pol auth att1 att2 iss2 now sz Hneq Hex.
  destruct (snd (appraise_peer p pol auth att1 (expected_recv_role (att_mode att1)) (mi_quote iss2) now sz))
    eqn:E; [|reflexivity].
  destruct (att_phase att1) eqn:Eph.
  - unfold appraise_peer in E. rewrite Eph in E. discriminate E.
  - destruct (receiver_appraisal_checks_ok p pol auth att1 (expected_recv_role (att_mode att1))
                now sz (mi_quote iss2) Eph E) as [_ [_ [_ [_ [Hexp _]]]]].
    exfalso. apply Hneq. rewrite <- Hexp, Hex. reflexivity.
  - destruct (source_appraisal_checks_ok p pol auth att1 (expected_recv_role (att_mode att1))
                now sz (mi_quote iss2) Eph E) as [rq [_ [Hrole _]]].
    destruct (att_mode att1); discriminate Hrole.
  - unfold appraise_peer in E; rewrite Eph in E; discriminate E.
  - unfold appraise_peer in E; rewrite Eph in E; discriminate E.
  - unfold appraise_peer in E; rewrite Eph in E; discriminate E.
  - unfold appraise_peer in E; rewrite Eph in E; discriminate E.
  - unfold appraise_peer in E; rewrite Eph in E; discriminate E.
  - unfold appraise_peer in E; rewrite Eph in E; discriminate E.
  - unfold appraise_peer in E; rewrite Eph in E; discriminate E.
Qed.

Example parallel_sessions_repeated_nonce_symbols_distinguished :
  open_attempt ex_profile ModeMigration (make_idle_attempt ModeMigration ctx_s2 ctx_r2) 1 2 0 10 10 = mig2_att_opened /\
  snd (appraise_peer ex_profile ex_mig_pol (ledger_auth [mig2_iss_recv]) mig2_att_opened
         MigrationReceiver (mi_quote mig2_iss_recv) 1 8) = true /\
  snd (appraise_peer ex_profile ex_mig_pol (ledger_auth [mig2_iss_recv]) mig_att_opened
         MigrationReceiver (mi_quote mig2_iss_recv) 1 8) = false.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8d. Reflected source/receiver roles and misordered appraisal are refused *)
(*| discharges: R-10-040, R-12-015c |*)
Example role_reflection_and_misordered_appraisal_are_refused :
  snd (appraise_peer ex_profile ex_mig_pol mig_auth mig_att_opened
         MigrationSource (mi_quote mig_iss_src) 1 8) = false /\
  snd (appraise_peer ex_profile ex_mig_pol mig_auth mig_att_opened
         MigrationReceiver (mi_quote mig_iss_src) 1 8) = false /\
  snd (appraise_peer ex_profile ex_mig_pol mig_auth mig_att_recv_app
         MigrationSource (mi_quote mig_iss_recv) 1 8) = false /\
  snd (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_recv_app
         MigrationSource
         {| ev_id := 7; ev_role := MigrationSource; ev_generation := 7;
            ev_ref_manifest := 8; ev_exporter := 11;
            ev_challenge := att_src_challenge mig_att_opened;
            ev_principal := 5; ev_roots := [];
            ev_bound_receiver_quote := Some 9; ev_enrolled_recipient := None |} 1 8) = false.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8e. Substituted exporter is refused *)
Definition bad_exporter_quote : MigrationQuote :=
  {| ev_id := 8; ev_role := MigrationReceiver; ev_generation := 7;
     ev_ref_manifest := 8; ev_exporter := 15;
     ev_challenge := att_recv_challenge mig_att_opened;
     ev_principal := 5; ev_roots := [3; 4];
     ev_bound_receiver_quote := None; ev_enrolled_recipient := None |}.

Example substituted_exporter_is_refused :
  snd (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_opened
         MigrationReceiver bad_exporter_quote 1 8) = false.
Proof. vm_compute; reflexivity. Qed.

(* 8f. Truncated, substituted, empty, and unrenderable-oversize roots are refused *)
Definition oversize_roots_quote : MigrationQuote :=
  {| ev_id := 9; ev_role := MigrationReceiver; ev_generation := 7;
     ev_ref_manifest := 8; ev_exporter := 11;
     ev_challenge := att_recv_challenge mig_att_opened;
     ev_principal := 5; ev_roots := [3; 4; 5; 6; 7];
     ev_bound_receiver_quote := None; ev_enrolled_recipient := None |}.

(*| discharges: R-10-040 |*)
Example truncated_substituted_and_oversize_roots_are_refused :
  snd (confirm_roots ex_profile mig_att_mut_app [3] mig_cw) = false /\
  snd (confirm_roots ex_profile mig_att_mut_app [3; 9]
         {| cw_channel_id := 1; cw_roots := [3; 9]; cw_source_profile := 1;
            cw_profile_map := 1; cw_schema_plan := 1;
            cw_source_cred := true; cw_receiver_cred := true |}) = false /\
  snd (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_opened
         MigrationReceiver oversize_roots_quote 1 8) = false.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8g. Wrong enrolled recipient is refused, and enrollment role cannot transfer *)
Definition wrong_enr_quote : MigrationQuote :=
  {| ev_id := 10; ev_role := BackupKeyEnrollment; ev_generation := 7;
     ev_ref_manifest := 8; ev_exporter := 13;
     ev_challenge := att_recv_challenge enr_att_opened;
     ev_principal := 5; ev_roots := [5; 6];
     ev_bound_receiver_quote := None; ev_enrolled_recipient := Some 12 |}.

(*| discharges: R-10-040 |*)
Example wrong_enrolled_recipient_and_transfer_on_enrollment_are_refused :
  snd (appraise_peer ex_profile ex_enr_recv_pol (fun _ => true) enr_att_opened
         BackupKeyEnrollment wrong_enr_quote 1 8) = false /\
  snd (wrap_recovery_key enr_att_confirmed 5 12) = false /\
  snd (transfer_backup ex_profile enr_att_confirmed 12) = false.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8h. Root confirmation without mutual appraisal, missing credentials, and
       excessive volatile buffer size are refused *)
Example confirm_without_appraisal_missing_creds_and_oversize_volatile_refused :
  snd (confirm_roots ex_profile mig_att_opened [3; 4] mig_cw) = false /\
  snd (confirm_roots ex_profile mig_att_recv_app [3; 4] mig_cw) = false /\
  snd (confirm_roots ex_profile mig_att_mut_app [3; 4]
         {| cw_channel_id := 1; cw_roots := [3; 4]; cw_source_profile := 1;
            cw_profile_map := 1; cw_schema_plan := 1;
            cw_source_cred := true; cw_receiver_cred := false |}) = false /\
  snd (transfer_backup ex_profile mig_att_confirmed 17) = false /\
  st_retained_backup_objects (att_storage (fst (transfer_backup ex_profile mig_att_confirmed 17))) = 0.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8i. Transparent byte-forwarding relay (accepted without key authority) vs.
       two-leg terminating MITM relay (refused) *)
Record ByteForwardingRelay : Type := {
  bfr_hops : list nat;
  bfr_source : ProtectedContext;
  bfr_target : ProtectedContext;
  bfr_quote : MigrationQuote;
  bfr_same_holder : SameKeyHolder bfr_source bfr_target
}.

Definition forward_bytes (_hops : list nat) (q : MigrationQuote) : MigrationQuote := q.

Definition records_open (att : MigrationAttempt) (holders : list nat) (sender : nat) : bool :=
  match att_phase att with
  | PhRootsConfirmed | PhTransferred | PhRestorePrepared =>
    ProofSupport.mem_nat sender holders
  | _ => false
  end.

(*| discharges: R-12-015c |*)
Theorem transparent_relay_preserves_agreement_without_key_authority :
  forall env tr signing_keys_intact tp_intact att oid obytes i_tr hops,
  TraceSound env tr ->
  NoKeyExposure tr ->
  NoIssuerCompromise tr ->
  ExporterSecurity (me_custody env) ->
  EvidenceAuthenticity (me_auth env) (trace_issuances tr) signing_keys_intact ->
  signing_keys_intact ->
  LocalContextIntegrity (me_profile env) (trace_issuances tr) (me_runtime env) ->
  RootSetFaithfulness (me_runtime env) (me_actual_roots env) ->
  HonestTrustedPath tp_intact tr ->
  tp_intact ->
  UncompromisedKeys (me_custody env) (trace_issuances tr) (att_src_ctx att) (att_recv_ctx att) ->
  nth_error tr i_tr = Some (EvTransfer att oid obytes) ->
  (forall h, In h hops -> h <> ctx_unit (att_src_ctx att) -> h <> ctx_unit (att_recv_ctx att) ->
    records_open att [ctx_unit (att_src_ctx att); ctx_unit (att_recv_ctx att)] h = false) /\
  (exists (relay : ByteForwardingRelay),
     bfr_hops relay = hops /\
     bfr_target relay = att_recv_ctx att /\
     forward_bytes hops (bfr_quote relay) = bfr_quote relay).
Proof.
  intros env tr sk tp att oid obytes i_tr hops Hs Hnk Hni Hex Ha Hsk Hl Hr Htp Htpok Hk Htr.
  destruct (migration_transfer_agreement env tr sk tp att oid obytes i_tr
              Hs Hnk Hni Hex Ha Hsk Hl Hr Htp Htpok Hk Htr)
    as [iss_recv [isrc [io [irq [ira [isq [isa [ic [recv_q [sq [cr [cw Hrem]]]]]]]]]]]].
  destruct Hrem as [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [_ [Hhold_r _]]]]]]]]]]]]].
  split.
  - intros h _ Hns Hnr.
    assert (Hmem : ProofSupport.mem_nat h [ctx_unit (att_src_ctx att); ctx_unit (att_recv_ctx att)] = false).
    { unfold ProofSupport.mem_nat. cbn.
      destruct (Nat.eqb h (ctx_unit (att_src_ctx att))) eqn:E1.
      { apply Nat.eqb_eq in E1. contradiction. }
      destruct (Nat.eqb h (ctx_unit (att_recv_ctx att))) eqn:E2.
      { apply Nat.eqb_eq in E2. contradiction. }
      reflexivity. }
    unfold records_open. destruct (att_phase att); try reflexivity; exact Hmem.
  - exists {| bfr_hops := hops;
              bfr_source := mi_issuer_ctx iss_recv;
              bfr_target := att_recv_ctx att;
              bfr_quote := recv_q;
              bfr_same_holder := Hhold_r |}.
    repeat split; reflexivity.
Qed.

(* Two-leg terminating MITM relay:
   (1) Honest receiver R's leg-2 context has exporter 14, so R cannot issue
       for leg-1 exporter 11, and R's leg-2 quote is refused on S's leg-1
       session (exporter 11 <> 14).
   (2) Attacker M's leg-1 context (unit 4) has roots [7; 8], failing when
       source holder confirms R's actual roots [3; 4]. *)
(*| discharges: R-10-040, R-12-015c |*)
Example two_leg_mitm_relay_is_refused :
  (match quote_local ex_profile ex_cred_policy ex_cred_recv ex_cred_srv ex_req_recv ctx_r_mitm_leg2 11
           (att_recv_challenge mig_att_opened) ex_runtime None with
   | Some (iss, _) => ev_exporter (mi_quote iss) = 14 /\ (ev_exporter (mi_quote iss) =? 11) = false
   | None => False
   end) /\
  snd (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_opened
         MigrationReceiver
         {| ev_id := 11; ev_role := MigrationReceiver; ev_generation := 7;
            ev_ref_manifest := 8; ev_exporter := 14;
            ev_challenge := att_recv_challenge mig_att_opened;
            ev_principal := 5; ev_roots := [3; 4];
            ev_bound_receiver_quote := None; ev_enrolled_recipient := None |} 1 8) = false /\
  let mitm_q := {| ev_id := 12; ev_role := MigrationReceiver; ev_generation := 7;
                   ev_ref_manifest := 8; ev_exporter := 11;
                   ev_challenge := att_recv_challenge mig_att_opened;
                   ev_principal := 5; ev_roots := [7; 8];
                   ev_bound_receiver_quote := None; ev_enrolled_recipient := None |} in
  let att_with_mitm :=
    fst (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_opened
           MigrationReceiver mitm_q 1 8) in
  snd (confirm_roots ex_profile
         (fst (appraise_peer ex_profile ex_mig_pol mig_auth att_with_mitm
                 MigrationSource
                 {| ev_id := 13; ev_role := MigrationSource; ev_generation := 7;
                    ev_ref_manifest := 8; ev_exporter := 11;
                    ev_challenge := att_src_challenge mig_att_opened;
                    ev_principal := 5; ev_roots := [];
                    ev_bound_receiver_quote := Some 12; ev_enrolled_recipient := None |} 1 8))
         [3; 4] mig_cw) = false.
Proof. vm_compute; repeat split; reflexivity. Qed.

(* 8j. Explicit broken-premise compromise witnesses for all six premises *)

(* (1) Broken ExporterSecurity: colliding context unit 4 shares exporter 11 *)
Definition colliding_ctx : ProtectedContext := ex_ctx 19 1 4 MigrationReceiver 11.
Definition colliding_custody (c : ProtectedContext) : Prop :=
  c = ctx_r1 \/ c = colliding_ctx.
Definition colliding_iss : MigrationIssuance :=
  {| mi_quote := {| ev_id := 14; ev_role := MigrationReceiver; ev_generation := 7;
                    ev_ref_manifest := 8; ev_exporter := 11;
                    ev_challenge := att_recv_challenge mig_att_opened;
                    ev_principal := 5; ev_roots := [3; 4];
                    ev_bound_receiver_quote := None; ev_enrolled_recipient := None |};
     mi_issuer_ctx := colliding_ctx |}.

Theorem broken_exporter_security_witness :
  ~ ExporterSecurity colliding_custody /\
  snd (appraise_peer ex_profile ex_mig_pol (ledger_auth [colliding_iss]) mig_att_opened
         MigrationReceiver (mi_quote colliding_iss) 1 8) = true /\
  ctx_unit (mi_issuer_ctx colliding_iss) <> ctx_unit ctx_r1.
Proof.
  split; [|split].
  - intros H. specialize (H ctx_r1 colliding_ctx eq_refl eq_refl
      (or_introl eq_refl) (or_intror eq_refl) eq_refl eq_refl).
    destruct H as [Hid _]. discriminate Hid.
  - vm_compute; reflexivity.
  - discriminate.
Qed.

(* (2) Broken EvidenceAuthenticity: accept-all verifier on empty ledger *)
Theorem broken_evidence_authenticity_witness :
  ~ EvidenceAuthenticity (fun _ => true) [] True /\
  snd (appraise_peer ex_profile ex_mig_pol (fun _ => true) mig_att_opened
         MigrationReceiver (mi_quote mig_iss_recv) 1 8) = true.
Proof.
  split.
  - intros H. destruct (H I (mi_quote mig_iss_recv) eq_refl) as [iss [Hin _]]. exact Hin.
  - vm_compute; reflexivity.
Qed.

(* (3) Broken LocalContextIntegrity: caller-supplied exporter binds unit 4 to 11 *)
Definition caller_exporter_iss : MigrationIssuance :=
  {| mi_quote := mi_quote mig_iss_recv; mi_issuer_ctx := ex_ctx 18 4 4 MigrationReceiver 15 |}.

Theorem broken_local_context_integrity_witness :
  ~ LocalContextIntegrity ex_profile [caller_exporter_iss] ex_runtime /\
  snd (appraise_peer ex_profile ex_mig_pol (ledger_auth [caller_exporter_iss]) mig_att_opened
         MigrationReceiver (mi_quote caller_exporter_iss) 1 8) = true.
Proof.
  split.
  - intros H. destruct (H caller_exporter_iss (or_introl eq_refl)) as [_ [_ [He _]]].
    discriminate He.
  - vm_compute; reflexivity.
Qed.

(* (4) Broken RootSetFaithfulness: runtime reports truncated roots [3] instead of [3; 4] *)
Definition unfaithful_runtime : LocalRuntime :=
  {| rt_measured_gen := rt_measured_gen ex_runtime;
     rt_ref_manifest := rt_ref_manifest ex_runtime;
     rt_roots := fun u => if u =? 2 then Some [3] else rt_roots ex_runtime u;
     rt_enrolled_recipient := rt_enrolled_recipient ex_runtime |}.

Theorem broken_root_set_faithfulness_witness :
  ~ RootSetFaithfulness unfaithful_runtime ex_actual_roots.
Proof.
  intros H. specialize (H 2 [3] eq_refl). discriminate H.
Qed.

(* (5) Broken HonestTrustedPath: forged ConfirmRoots event without receiver cred / matching roots *)
Definition forged_cw : ConsentWitness :=
  {| cw_channel_id := 1; cw_roots := [3]; cw_source_profile := 1;
     cw_profile_map := 1; cw_schema_plan := 1;
     cw_source_cred := true; cw_receiver_cred := false |}.

Definition compromised_tp_trace : MigrationTrace :=
  [EvConfirmRoots mig_att_mut_app [3; 4] forged_cw; EvTrustedPathCompromised 1].

Theorem broken_honest_trusted_path_witness :
  ~ HonestTrustedPath True compromised_tp_trace /\
  ~ NoTrustedPathCompromise compromised_tp_trace.
Proof.
  split.
  - intros H. destruct (H I mig_att_mut_app [3; 4] forged_cw (or_introl eq_refl)) as [_ [Hrc _]].
    discriminate Hrc.
  - intros H. apply (H 1). right. left. reflexivity.
Qed.

(* (6) Broken UncompromisedKeys / NoKeyExposure: attacker 4 steals session traffic key *)
Definition key_exposure_trace : MigrationTrace :=
  honest_migration_trace ++ [EvKeyExposed ctx_r1 4].

Definition ExclusiveTrafficKeys (src recv : ProtectedContext) (holders : list nat) : Prop :=
  forall h, In h holders -> h = ctx_unit src \/ h = ctx_unit recv.

Theorem broken_uncompromised_keys_witness :
  ~ NoKeyExposure key_exposure_trace /\
  ~ ExclusiveTrafficKeys ctx_s1 ctx_r1 [1; 2; 4] /\
  records_open mig_att_confirmed [1; 2; 4] 4 = true.
Proof.
  split; [|split].
  - intros H. apply (H ctx_r1 4). unfold key_exposure_trace. apply in_or_app. right. left. reflexivity.
  - intros H. destruct (H 4 ltac:(cbn; auto)) as [H1 | H2]; discriminate.
  - vm_compute; reflexivity.
Qed.

(* =========================================================================
   9. Closed top-level inhabitation witnesses for every Record (R-05-166)
   ========================================================================= *)

Definition witness_ProtectedContext : ProtectedContext := ctx_s1.
Definition witness_MigrationProfile : MigrationProfile := ex_profile.
Definition witness_LocalRuntime : LocalRuntime := ex_runtime.
Definition witness_MigrationChallenge : MigrationChallenge := att_recv_challenge mig_att_opened.
Definition witness_MigrationQuote : MigrationQuote := mi_quote mig_iss_recv.
Definition witness_MigrationIssuance : MigrationIssuance := mig_iss_recv.
Definition witness_MigrationPolicy : MigrationPolicy := ex_mig_pol.
Definition witness_ConsentWitness : ConsentWitness := mig_cw.
Definition witness_VolatileBuffer : VolatileBuffer := att_volatile mig_att_transferred.
Definition witness_StorageState : StorageState := ex_storage_init.
Definition witness_WrappedKeyHandle : WrappedKeyHandle :=
  {| wk_recipient := 11; wk_object_id := 5;
     wk_use_restore_only := true; wk_locally_sealed := true |}.
Definition witness_RestorePayload : RestorePayload := mig_restore_payload.
Definition witness_MigrationAttempt : MigrationAttempt := mig_att_published.
Definition witness_MigrationEnv : MigrationEnv := env_honest_mig.
Definition witness_ByteForwardingRelay : ByteForwardingRelay :=
  {| bfr_hops := [4; 5];
     bfr_source := ctx_r1;
     bfr_target := ctx_r1;
     bfr_quote := mi_quote mig_iss_recv;
     bfr_same_holder := conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))) |}.
