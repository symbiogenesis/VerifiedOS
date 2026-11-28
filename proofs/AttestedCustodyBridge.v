(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   AttestedCustodyBridge.v

   Concrete implementation-to-model bridge connecting the bounded C17
   protected TLS-context and key-custody vault
   ([vos_session_custody.h](../session-custody/include/vos_session_custody.h))
   to [CredentialHandles.v](CredentialHandles.v#authorize_and_charge) (R-12-015a)
   and [AttestedSession.v](AttestedSession.v#attested_session_binding)
   (R-12-015c, R-09-025a) under
   [attested-tls-protocol.md](../docs/implementation/attested-tls-protocol.md).

   Assumption closure (R-05-163, R-05-164) and non-vacuity inhabitation and
   distinguishing refutation witnesses (R-05-165, R-05-166) are checked by the
   locked Rocq prover and `rocqchk` without adding axioms.

   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-09-025a R-12-015a R-12-015c
   SHA256: 45ce58aedcf2572d9846dce6d79160e4ed0a7e7164e7b11ee771d5ffadc28809
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport CredentialHandles AttestedSession.
From Stdlib Require Import List Bool Arith Lia.
Import ListNotations.

(* =========================================================================
   1. Concrete Protected Vault, Key Custody, and Opaque Handle Tables
   ========================================================================= *)

Record ConcreteConfig : Type := {
  cc_profile : AttestedSession.AttestationProfile;
  cc_cred_policy : CredentialHandles.CredentialPolicy;
  cc_config_digest : nat;
  cc_hmac_key : nat;
  cc_custody_key : nat;
  cc_max_contexts : nat;
  cc_max_creds : nat
}.

Record ConcreteTLSReg : Type := {
  reg_unit : nat;
  reg_principal : nat;
  reg_origin : nat;
  reg_config_digest : nat;
  reg_traffic_key : nat;
  reg_handshake_complete : bool;
  reg_server_authenticated : bool;
  reg_early_data : bool;
  reg_resumed : bool
}.

Record ConcreteContextSlot : Type := {
  slot_active : bool;
  slot_retired : bool;
  slot_key_exposed : bool;
  slot_context_id : nat;
  slot_epoch : nat;
  slot_unit : nat;
  slot_principal : nat;
  slot_origin : nat;
  slot_config_digest : nat;
  slot_traffic_key : nat;
  slot_handshake_complete : bool;
  slot_server_authenticated : bool;
  slot_early_data : bool;
  slot_resumed : bool
}.

Definition context_slot_eqb (a b : ConcreteContextSlot) : bool :=
  Bool.eqb (slot_active a) (slot_active b) &&
  Bool.eqb (slot_retired a) (slot_retired b) &&
  Bool.eqb (slot_key_exposed a) (slot_key_exposed b) &&
  (slot_context_id a =? slot_context_id b) &&
  (slot_epoch a =? slot_epoch b) &&
  (slot_unit a =? slot_unit b) &&
  (slot_principal a =? slot_principal b) &&
  (slot_origin a =? slot_origin b) &&
  (slot_config_digest a =? slot_config_digest b) &&
  (slot_traffic_key a =? slot_traffic_key b) &&
  Bool.eqb (slot_handshake_complete a) (slot_handshake_complete b) &&
  Bool.eqb (slot_server_authenticated a) (slot_server_authenticated b) &&
  Bool.eqb (slot_early_data a) (slot_early_data b) &&
  Bool.eqb (slot_resumed a) (slot_resumed b).

Lemma context_slot_eqb_eq : forall a b, context_slot_eqb a b = true -> a = b.
Proof.
  intros a b H.
  destruct a, b. unfold context_slot_eqb in H. cbn in H.
  repeat rewrite andb_true_iff in H.
  destruct H as [[[[[[[[[[[[[H1 H2] H3] H4] H5] H6] H7] H8] H9] H10] H11] H12] H13] H14].
  apply Bool.eqb_prop in H1, H2, H3, H11, H12, H13, H14.
  apply Nat.eqb_eq in H4, H5, H6, H7, H8, H9, H10.
  subst. reflexivity.
Qed.

(* Opaque, MAC-authenticated context handle: carries no traffic key, exporter,
   or mutable measurement field. *)
Record ConcreteContextHandle : Type := {
  ch_slot : nat;
  ch_context_id : nat;
  ch_epoch : nat;
  ch_sealed : bool;
  ch_mac : nat
}.

Record ConcreteCredEntry : Type := {
  ce_active : bool;
  ce_cred_id : nat;
  ce_epoch : nat;
  ce_unit : nat;
  ce_cred : CredentialHandles.Credential
}.

Record ConcreteCredHandle : Type := {
  crh_slot : nat;
  crh_cred_id : nat;
  crh_epoch : nat;
  crh_sealed : bool;
  crh_mac : nat
}.

Record ConcreteVault : Type := {
  cv_config : ConcreteConfig;
  cv_epoch : nat;
  cv_next_ctx_id : nat;
  cv_next_cred_id : nat;
  cv_contexts : list (nat * ConcreteContextSlot);
  cv_creds : list (nat * ConcreteCredEntry);
  cv_cred_state : CredentialHandles.ServerState;
  cv_measured : AttestedSession.Measurement;
  cv_aliases : AttestedSession.UnitAliases;
  cv_spent_contexts : list nat;
  (* Abstracted HMAC-SHA256 exporter derivation from traffic_key:
     EXPORTER-Channel-Binding (empty context, 32 bytes). *)
  cv_derive_exporter : nat -> nat;
  cv_ctx_mac : nat -> nat -> nat -> nat -> nat -> nat -> nat;
  cv_cred_mac : nat -> nat -> nat -> nat -> nat -> nat -> nat;
  cv_seal_mac : nat -> AttestedSession.Evidence -> nat
}.

Fixpoint assoc_lookup {A : Type} (k : nat) (xs : list (nat * A)) : option A :=
  match xs with
  | [] => None
  | (k', v) :: rest => if k =? k' then Some v else assoc_lookup k rest
  end.

Fixpoint assoc_set {A : Type} (k : nat) (v : A) (xs : list (nat * A)) : list (nat * A) :=
  match xs with
  | [] => [(k, v)]
  | (k', v') :: rest =>
    if k =? k' then (k, v) :: rest else (k', v') :: assoc_set k v rest
  end.

Lemma assoc_lookup_set_eq : forall A k (v : A) xs,
  assoc_lookup k (assoc_set k v xs) = Some v.
Proof.
  intros A k v xs. induction xs as [|[k' v'] rest IH]; cbn.
  - rewrite Nat.eqb_refl. reflexivity.
  - destruct (k =? k') eqn:E; cbn.
    + rewrite Nat.eqb_refl. reflexivity.
    + rewrite E. exact IH.
Qed.

Lemma assoc_lookup_set_neq : forall A k1 k2 (v : A) xs,
  k1 <> k2 ->
  assoc_lookup k1 (assoc_set k2 v xs) = assoc_lookup k1 xs.
Proof.
  intros A k1 k2 v xs Hneq. induction xs as [|[k' v'] rest IH]; cbn.
  - destruct (k1 =? k2) eqn:E; [apply Nat.eqb_eq in E; contradiction|reflexivity].
  - destruct (k2 =? k') eqn:E2; cbn.
    + apply Nat.eqb_eq in E2. subst k'.
      destruct (k1 =? k2) eqn:E1; [apply Nat.eqb_eq in E1; contradiction|reflexivity].
    + destruct (k1 =? k') eqn:E1; [reflexivity|exact IH].
Qed.

Definition tls_reg_eligible (cfg_digest : nat) (reg : ConcreteTLSReg) : bool :=
  (0 <? reg_unit reg) &&
  (reg_config_digest reg =? cfg_digest) &&
  (0 <? reg_traffic_key reg) &&
  reg_handshake_complete reg &&
  reg_server_authenticated reg &&
  negb (reg_early_data reg) &&
  negb (reg_resumed reg).

Definition slot_tls_eligible (cfg_digest : nat) (s : ConcreteContextSlot) : bool :=
  (0 <? slot_context_id s) &&
  (0 <? slot_unit s) &&
  (slot_config_digest s =? cfg_digest) &&
  (0 <? slot_traffic_key s) &&
  slot_handshake_complete s &&
  slot_server_authenticated s &&
  negb (slot_early_data s) &&
  negb (slot_resumed s).

Definition concrete_exporter (v : ConcreteVault) (s : ConcreteContextSlot) : nat :=
  cv_derive_exporter v (slot_traffic_key s).

Definition expected_ctx_mac (v : ConcreteVault) (slot_idx : nat) (s : ConcreteContextSlot) : nat :=
  cv_ctx_mac v (cc_custody_key (cv_config v)) slot_idx
             (slot_context_id s) (slot_epoch s) (slot_unit s) (slot_config_digest s).

Definition expected_cred_mac (v : ConcreteVault) (slot_idx : nat) (e : ConcreteCredEntry) : nat :=
  cv_cred_mac v (cc_custody_key (cv_config v)) slot_idx
              (ce_cred_id e) (ce_epoch e) (ce_unit e)
              (CredentialHandles.credential_account (ce_cred e)).

Definition resolve_context_handle (v : ConcreteVault) (h : ConcreteContextHandle)
    : option ConcreteContextSlot :=
  if ch_sealed h && (ch_epoch h =? cv_epoch v) then
    match assoc_lookup (ch_slot h) (cv_contexts v) with
    | None => None
    | Some s =>
      if slot_active s && negb (slot_retired s) && negb (slot_key_exposed s) &&
         (slot_context_id s =? ch_context_id h) &&
         (slot_epoch s =? cv_epoch v) &&
         slot_tls_eligible (cc_config_digest (cv_config v)) s &&
         (ch_mac h =? expected_ctx_mac v (ch_slot h) s)
      then Some s
      else None
    end
  else None.

Definition resolve_cred_handle (v : ConcreteVault) (h : ConcreteCredHandle)
    : option ConcreteCredEntry :=
  if crh_sealed h && (crh_epoch h =? cv_epoch v) then
    match assoc_lookup (crh_slot h) (cv_creds v) with
    | None => None
    | Some e =>
      if ce_active e &&
         (ce_cred_id e =? crh_cred_id h) &&
         (ce_epoch e =? cv_epoch v) &&
         (crh_mac h =? expected_cred_mac v (crh_slot h) e)
      then Some e
      else None
    end
  else None.

Definition with_vault_contexts (v : ConcreteVault) (ctxs : list (nat * ConcreteContextSlot))
    (next_cid : nat) (spent : list nat) : ConcreteVault :=
  {| cv_config := cv_config v;
     cv_epoch := cv_epoch v;
     cv_next_ctx_id := next_cid;
     cv_next_cred_id := cv_next_cred_id v;
     cv_contexts := ctxs;
     cv_creds := cv_creds v;
     cv_cred_state := cv_cred_state v;
     cv_measured := cv_measured v;
     cv_aliases := cv_aliases v;
     cv_spent_contexts := spent;
     cv_derive_exporter := cv_derive_exporter v;
     cv_ctx_mac := cv_ctx_mac v;
     cv_cred_mac := cv_cred_mac v;
     cv_seal_mac := cv_seal_mac v |}.

Definition with_vault_cred_state (v : ConcreteVault) (st : CredentialHandles.ServerState)
    : ConcreteVault :=
  {| cv_config := cv_config v;
     cv_epoch := cv_epoch v;
     cv_next_ctx_id := cv_next_ctx_id v;
     cv_next_cred_id := cv_next_cred_id v;
     cv_contexts := cv_contexts v;
     cv_creds := cv_creds v;
     cv_cred_state := st;
     cv_measured := cv_measured v;
     cv_aliases := cv_aliases v;
     cv_spent_contexts := cv_spent_contexts v;
     cv_derive_exporter := cv_derive_exporter v;
     cv_ctx_mac := cv_ctx_mac v;
     cv_cred_mac := cv_cred_mac v;
     cv_seal_mac := cv_seal_mac v |}.

Definition register_tls_context (v : ConcreteVault) (slot_idx : nat) (reg : ConcreteTLSReg)
    : option (ConcreteVault * ConcreteContextHandle) :=
  if (slot_idx <? cc_max_contexts (cv_config v)) &&
     tls_reg_eligible (cc_config_digest (cv_config v)) reg &&
     match assoc_lookup slot_idx (cv_contexts v) with
     | None => true
     | Some old => negb (slot_active old)
     end
  then
    let cid := cv_next_ctx_id v in
    let s := {| slot_active := true;
                slot_retired := false;
                slot_key_exposed := false;
                slot_context_id := cid;
                slot_epoch := cv_epoch v;
                slot_unit := reg_unit reg;
                slot_principal := reg_principal reg;
                slot_origin := reg_origin reg;
                slot_config_digest := reg_config_digest reg;
                slot_traffic_key := reg_traffic_key reg;
                slot_handshake_complete := reg_handshake_complete reg;
                slot_server_authenticated := reg_server_authenticated reg;
                slot_early_data := reg_early_data reg;
                slot_resumed := reg_resumed reg |} in
    let h := {| ch_slot := slot_idx;
                ch_context_id := cid;
                ch_epoch := cv_epoch v;
                ch_sealed := true;
                ch_mac := expected_ctx_mac v slot_idx s |} in
    Some (with_vault_contexts v (assoc_set slot_idx s (cv_contexts v)) (S cid)
                              (cv_spent_contexts v), h)
  else None.

Definition register_credential (v : ConcreteVault) (slot_idx unit_id : nat)
    (cred : CredentialHandles.Credential)
    : option (ConcreteVault * ConcreteCredHandle) :=
  if (slot_idx <? cc_max_creds (cv_config v)) && (0 <? unit_id) &&
     match assoc_lookup slot_idx (cv_creds v) with
     | None => true
     | Some old => negb (ce_active old)
     end
  then
    let kid := cv_next_cred_id v in
    let e := {| ce_active := true;
                ce_cred_id := kid;
                ce_epoch := cv_epoch v;
                ce_unit := unit_id;
                ce_cred := cred |} in
    let h := {| crh_slot := slot_idx;
                crh_cred_id := kid;
                crh_epoch := cv_epoch v;
                crh_sealed := true;
                crh_mac := expected_cred_mac v slot_idx e |} in
    Some ({| cv_config := cv_config v;
             cv_epoch := cv_epoch v;
             cv_next_ctx_id := cv_next_ctx_id v;
             cv_next_cred_id := S kid;
             cv_contexts := cv_contexts v;
             cv_creds := assoc_set slot_idx e (cv_creds v);
             cv_cred_state := cv_cred_state v;
             cv_measured := cv_measured v;
             cv_aliases := cv_aliases v;
             cv_spent_contexts := cv_spent_contexts v;
             cv_derive_exporter := cv_derive_exporter v;
             cv_ctx_mac := cv_ctx_mac v;
             cv_cred_mac := cv_cred_mac v;
             cv_seal_mac := cv_seal_mac v |}, h)
  else None.

Definition retire_slot (s : ConcreteContextSlot) : ConcreteContextSlot :=
  {| slot_active := false;
     slot_retired := true;
     slot_key_exposed := slot_key_exposed s;
     slot_context_id := slot_context_id s;
     slot_epoch := slot_epoch s;
     slot_unit := slot_unit s;
     slot_principal := slot_principal s;
     slot_origin := slot_origin s;
     slot_config_digest := slot_config_digest s;
     slot_traffic_key := 0;
     slot_handshake_complete := slot_handshake_complete s;
     slot_server_authenticated := slot_server_authenticated s;
     slot_early_data := slot_early_data s;
     slot_resumed := slot_resumed s |}.

Definition teardown_context (v : ConcreteVault) (h : ConcreteContextHandle)
    : option ConcreteVault :=
  match resolve_context_handle v h with
  | None => None
  | Some s =>
    let spent' := slot_context_id s :: cv_spent_contexts v in
    Some (with_vault_contexts v (assoc_set (ch_slot h) (retire_slot s) (cv_contexts v))
                              (cv_next_ctx_id v) spent')
  end.

Definition expose_context_key (v : ConcreteVault) (h : ConcreteContextHandle)
    : option ConcreteVault :=
  match resolve_context_handle v h with
  | None => None
  | Some s =>
    let s' := {| slot_active := slot_active s;
                 slot_retired := slot_retired s;
                 slot_key_exposed := true;
                 slot_context_id := slot_context_id s;
                 slot_epoch := slot_epoch s;
                 slot_unit := slot_unit s;
                 slot_principal := slot_principal s;
                 slot_origin := slot_origin s;
                 slot_config_digest := slot_config_digest s;
                 slot_traffic_key := slot_traffic_key s;
                 slot_handshake_complete := slot_handshake_complete s;
                 slot_server_authenticated := slot_server_authenticated s;
                 slot_early_data := slot_early_data s;
                 slot_resumed := slot_resumed s |} in
    Some (with_vault_contexts v (assoc_set (ch_slot h) s' (cv_contexts v))
                              (cv_next_ctx_id v) (cv_spent_contexts v))
  end.

Definition advance_lifecycle (v : ConcreteVault) : ConcreteVault :=
  {| cv_config := cv_config v;
     cv_epoch := S (cv_epoch v);
     cv_next_ctx_id := cv_next_ctx_id v;
     cv_next_cred_id := cv_next_cred_id v;
     cv_contexts := map (fun kv => (fst kv, retire_slot (snd kv))) (cv_contexts v);
     cv_creds := cv_creds v;
     cv_cred_state := cv_cred_state v;
     cv_measured := cv_measured v;
     cv_aliases := cv_aliases v;
     cv_spent_contexts := cv_spent_contexts v;
     cv_derive_exporter := cv_derive_exporter v;
     cv_ctx_mac := cv_ctx_mac v;
     cv_cred_mac := cv_cred_mac v;
     cv_seal_mac := cv_seal_mac v |}.

Definition retire_unit_generation (v : ConcreteVault) (unit_id new_gen : nat) : ConcreteVault :=
  let spent_unit :=
    flat_map (fun kv => if slot_active (snd kv) && (slot_unit (snd kv) =? unit_id)
                        then [slot_context_id (snd kv)] else [])
             (cv_contexts v) in
  let ctxs' :=
    map (fun kv => if slot_active (snd kv) && (slot_unit (snd kv) =? unit_id)
                   then (fst kv, retire_slot (snd kv)) else kv)
        (cv_contexts v) in
  {| cv_config := cv_config v;
     cv_epoch := cv_epoch v;
     cv_next_ctx_id := cv_next_ctx_id v;
     cv_next_cred_id := cv_next_cred_id v;
     cv_contexts := ctxs';
     cv_creds := cv_creds v;
     cv_cred_state := cv_cred_state v;
     cv_measured := fun u => if u =? unit_id then Some new_gen else cv_measured v u;
     cv_aliases := cv_aliases v;
     cv_spent_contexts := spent_unit ++ cv_spent_contexts v;
     cv_derive_exporter := cv_derive_exporter v;
     cv_ctx_mac := cv_ctx_mac v;
     cv_cred_mac := cv_cred_mac v;
     cv_seal_mac := cv_seal_mac v |}.

(* =========================================================================
   2. Concrete Wire Records and Abstraction Relation (`refine_*`)
   ========================================================================= *)

Record ConcreteWireChallenge : Type := {
  cwc_unit_scope : bool;
  cwc_nonce : nat;
  cwc_origin : nat;
  cwc_domain : nat;
  cwc_wire_len : nat
}.

Record ConcreteWireEvidence : Type := {
  cwe_generation : nat;
  cwe_exporter : nat;
  cwe_challenge : ConcreteWireChallenge;
  cwe_principal : nat;
  cwe_role : nat;
  cwe_alias : option nat;
  cwe_seal_mac : nat;
  cwe_wire_len : nat
}.

Record ConcreteAppraiser : Type := {
  ca_profile : AttestedSession.AttestationProfile;
  ca_policy : AttestedSession.AppraisalPolicy;
  ca_hmac_key : nat;
  ca_expected_config_digest : nat;
  ca_auth : AttestedSession.Evidence -> bool
}.

Record ConcreteSession : Type := {
  cs_bound_handle : ConcreteContextHandle;
  cs_bound_slot : ConcreteContextSlot;
  cs_config_digest : nat;
  cs_bound_epoch : nat;
  cs_phase : AttestedSession.Phase;
  cs_pending_challenge : AttestedSession.Challenge;
  cs_pending_deadline : nat;
  cs_used_nonces : list nat;
  cs_spent_contexts : list nat;
  cs_attested_open : bool
}.

Definition refine_slot (v : ConcreteVault) (s : ConcreteContextSlot)
    : AttestedSession.ProtectedContext :=
  {| AttestedSession.context_id := slot_context_id s;
     AttestedSession.context_unit := slot_unit s;
     AttestedSession.context_principal := slot_principal s;
     AttestedSession.context_origin := slot_origin s;
     AttestedSession.context_exporter := concrete_exporter v s;
     AttestedSession.handshake_complete :=
       slot_handshake_complete s && slot_active s && negb (slot_retired s);
     AttestedSession.server_authenticated := slot_server_authenticated s;
     AttestedSession.early_data := slot_early_data s;
     AttestedSession.resumed := slot_resumed s |}.

Definition refine_context (v : ConcreteVault) (h : ConcreteContextHandle)
    : option AttestedSession.ProtectedContext :=
  match resolve_context_handle v h with
  | None => None
  | Some s => Some (refine_slot v s)
  end.

Definition refine_challenge (cwc : ConcreteWireChallenge) : AttestedSession.Challenge :=
  {| AttestedSession.challenge_nonce := cwc_nonce cwc;
     AttestedSession.challenge_origin := cwc_origin cwc;
     AttestedSession.challenge_unit_scope := cwc_unit_scope cwc;
     AttestedSession.challenge_domain := cwc_domain cwc |}.

Definition refine_evidence (cwe : ConcreteWireEvidence) : AttestedSession.Evidence :=
  {| AttestedSession.evidence_generation := cwe_generation cwe;
     AttestedSession.evidence_exporter := cwe_exporter cwe;
     AttestedSession.evidence_challenge := refine_challenge (cwe_challenge cwe);
     AttestedSession.evidence_principal := cwe_principal cwe;
     AttestedSession.evidence_role := cwe_role cwe;
     AttestedSession.evidence_alias := cwe_alias cwe |}.

Definition refine_appraiser (app : ConcreteAppraiser)
    : AttestedSession.AppraisalPolicy * (AttestedSession.Evidence -> bool) :=
  (ca_policy app, ca_auth app).

Definition refine_session (v : ConcreteVault) (cs : ConcreteSession)
    : AttestedSession.Connection :=
  {| AttestedSession.protected_context := refine_slot v (cs_bound_slot cs);
     AttestedSession.phase := cs_phase cs;
     AttestedSession.pending_challenge := cs_pending_challenge cs;
     AttestedSession.pending_deadline := cs_pending_deadline cs;
     AttestedSession.used_nonces := cs_used_nonces cs;
     AttestedSession.used_contexts := cs_spent_contexts cs |}.

(* =========================================================================
   3. Authenticated Quote Issuance Bound to Protected Context & Credentials
   ========================================================================= *)

Definition concrete_quote (v : ConcreteVault) (ch : ConcreteCredHandle)
    (ctxh : ConcreteContextHandle) (req : CredentialHandles.ClientRequest)
    (cwc : ConcreteWireChallenge)
    : option (ConcreteWireEvidence * AttestedSession.Issuance * ConcreteVault) :=
  match resolve_context_handle v ctxh, resolve_cred_handle v ch with
  | Some s, Some ce =>
    if ce_unit ce =? slot_unit s then
      let pctx := refine_slot v s in
      let q := refine_challenge cwc in
      match AttestedSession.issue_local
              (cc_profile (cv_config v)) (cc_cred_policy (cv_config v))
              (ce_cred ce) (cv_cred_state v) req pctx q
              (cv_measured v) (cv_aliases v) with
      | None => None
      | Some (iss, charged) =>
        let ev := AttestedSession.issued_evidence iss in
        let cwe := {| cwe_generation := AttestedSession.evidence_generation ev;
                      cwe_exporter := AttestedSession.evidence_exporter ev;
                      cwe_challenge := cwc;
                      cwe_principal := AttestedSession.evidence_principal ev;
                      cwe_role := AttestedSession.evidence_role ev;
                      cwe_alias := AttestedSession.evidence_alias ev;
                      cwe_seal_mac := cv_seal_mac v (cc_hmac_key (cv_config v)) ev;
                      cwe_wire_len := AttestedSession.evidence_bound (cc_profile (cv_config v)) |} in
        Some (cwe, iss, with_vault_cred_state v charged)
      end
    else None
  | _, _ => None
  end.

(* Broken refutation construction taking a caller-supplied exporter instead of
   reading `concrete_exporter v s` from protected custody. *)
Definition broken_caller_exporter_quote (v : ConcreteVault) (s : ConcreteContextSlot)
    (caller_exporter : nat) (cwc : ConcreteWireChallenge) (gen : nat) (alias : option nat)
    : AttestedSession.Issuance :=
  let q := refine_challenge cwc in
  let ev := {| AttestedSession.evidence_generation := gen;
               AttestedSession.evidence_exporter := caller_exporter;
               AttestedSession.evidence_challenge := q;
               AttestedSession.evidence_principal := slot_principal s;
               AttestedSession.evidence_role := AttestedSession.attester_role (cc_profile (cv_config v));
               AttestedSession.evidence_alias := alias |} in
  {| AttestedSession.issued_evidence := ev;
     AttestedSession.issuer_context := refine_slot v s |}.

Lemma resolved_slot_is_usable : forall v h s,
  resolve_context_handle v h = Some s ->
  AttestedSession.context_usable (refine_slot v s) = true /\
  slot_active s = true /\
  slot_retired s = false /\
  slot_key_exposed s = false /\
  slot_epoch s = cv_epoch v /\
  slot_config_digest s = cc_config_digest (cv_config v).
Proof.
  intros v h s H. unfold resolve_context_handle in H.
  destruct (ch_sealed h && (ch_epoch h =? cv_epoch v)); [|discriminate].
  destruct (assoc_lookup (ch_slot h) (cv_contexts v)) as [s'|]; [|discriminate].
  destruct (slot_active s' && negb (slot_retired s') && negb (slot_key_exposed s') &&
            (slot_context_id s' =? ch_context_id h) &&
            (slot_epoch s' =? cv_epoch v) &&
            slot_tls_eligible (cc_config_digest (cv_config v)) s' &&
            (ch_mac h =? expected_ctx_mac v (ch_slot h) s')) eqn:E; [|discriminate].
  inversion H; subst s'. clear H.
  repeat rewrite andb_true_iff in E.
  destruct E as [[[[[[Hact Hnret] Hnexp] Hcid] Hep] Htls] Hmac].
  unfold slot_tls_eligible in Htls. repeat rewrite andb_true_iff in Htls.
  destruct Htls as [[[[[[[_ _] Hcfg] _] Hhs] Hsa] Hed] Hres].
  apply negb_true_iff in Hnret, Hnexp.
  apply Nat.eqb_eq in Hep, Hcfg.
  unfold AttestedSession.context_usable, refine_slot. cbn.
  rewrite Hhs, Hact, Hnret, Hsa, Hed, Hres. cbn.
  repeat split; assumption || reflexivity.
Qed.

(*| discharges: R-12-015a, R-12-015c |*)
Theorem concrete_quote_binds_custody_and_charges :
  forall v ch ctxh req cwc cwe iss v',
  concrete_quote v ch ctxh req cwc = Some (cwe, iss, v') ->
  exists s ce,
    resolve_context_handle v ctxh = Some s /\
    resolve_cred_handle v ch = Some ce /\
    ce_unit ce = slot_unit s /\
    cwe_exporter cwe = concrete_exporter v s /\
    refine_evidence cwe = AttestedSession.issued_evidence iss /\
    AttestedSession.issuer_context iss = refine_slot v s /\
    cv_measured v (slot_unit s) = Some (cwe_generation cwe) /\
    CredentialHandles.authorize_and_charge
      (cc_cred_policy (cv_config v)) (ce_cred ce) (cv_cred_state v) req =
      Some (cv_cred_state v') /\
    AttestedSession.LocalContextIntegrity
      (cc_profile (cv_config v)) [iss] (cv_measured v) (cv_aliases v).
Proof.
  intros v ch ctxh req cwc cwe iss v' H.
  unfold concrete_quote in H.
  destruct (resolve_context_handle v ctxh) as [s|] eqn:Hctx; [|discriminate].
  destruct (resolve_cred_handle v ch) as [ce|] eqn:Hcred; [|discriminate].
  destruct (ce_unit ce =? slot_unit s) eqn:Hunit; [|discriminate].
  apply Nat.eqb_eq in Hunit.
  destruct (AttestedSession.issue_local
              (cc_profile (cv_config v)) (cc_cred_policy (cv_config v))
              (ce_cred ce) (cv_cred_state v) req (refine_slot v s)
              (refine_challenge cwc) (cv_measured v) (cv_aliases v))
    as [[iss0 charged]|] eqn:Hiss; [|discriminate].
  inversion H; subst. clear H.
  pose proof (AttestedSession.local_issuance_reads_the_exporter_from_its_own_context
                _ _ _ _ _ _ _ _ _ _ _ Hiss) as [Hexp [Hic [Hmeas Hch]]].
  pose proof (AttestedSession.issued_events_have_protected_context_provenance
                _ _ _ _ _ _ _ _ _ _ _ Hiss) as Hloc.
  exists s, ce.
  split; [reflexivity|].
  split; [reflexivity|].
  split; [exact Hunit|].
  split; [cbn; exact Hexp|].
  split.
  { unfold AttestedSession.issue_local in Hiss.
    destruct (AttestedSession.profile_bounded (cc_profile (cv_config v)) &&
              AttestedSession.context_usable (refine_slot v s) &&
              AttestedSession.local_request_matches (cc_profile (cv_config v))
                (refine_slot v s) (refine_challenge cwc) req); [|discriminate].
    destruct (cv_measured v (AttestedSession.context_unit (refine_slot v s))); [|discriminate].
    destruct (AttestedSession.challenge_unit_scope (refine_challenge cwc) &&
              match if AttestedSession.challenge_unit_scope (refine_challenge cwc)
                    then cv_aliases v (AttestedSession.context_origin (refine_slot v s))
                                      (AttestedSession.context_unit (refine_slot v s))
                    else None
              with None => true | Some _ => false end); [discriminate|].
    destruct (CredentialHandles.authorize_and_charge (cc_cred_policy (cv_config v))
                (ce_cred ce) (cv_cred_state v) req); [|discriminate].
    inversion Hiss; subst iss. unfold refine_evidence. cbn.
    destruct cwc. reflexivity. }
  split; [exact Hic|].
  split; [exact Hmeas|].
  split; [exact Hch|exact Hloc].
Qed.

Theorem forged_or_foreign_handle_cannot_quote :
  forall v ch ctxh req cwc,
  (ch_sealed ctxh = false \/
   ch_epoch ctxh <> cv_epoch v \/
   resolve_context_handle v ctxh = None \/
   resolve_cred_handle v ch = None) ->
  concrete_quote v ch ctxh req cwc = None.
Proof.
  intros v ch ctxh req cwc [H|[H|[H|H]]]; unfold concrete_quote.
  - unfold resolve_context_handle. rewrite H. reflexivity.
  - unfold resolve_context_handle.
    destruct (Nat.eqb_spec (ch_epoch ctxh) (cv_epoch v)); [contradiction|].
    rewrite andb_false_r. reflexivity.
  - rewrite H. reflexivity.
  - destruct (resolve_context_handle v ctxh); [rewrite H; reflexivity|reflexivity].
Qed.

Theorem broken_caller_exporter_violates_integrity :
  forall v s caller_exp cwc gen alias,
  caller_exp <> concrete_exporter v s ->
  ~ AttestedSession.LocalContextIntegrity
      (cc_profile (cv_config v))
      [broken_caller_exporter_quote v s caller_exp cwc gen alias]
      (cv_measured v) (cv_aliases v).
Proof.
  intros v s caller_exp cwc gen alias Hneq Hloc.
  specialize (Hloc (broken_caller_exporter_quote v s caller_exp cwc gen alias)
                   (or_introl eq_refl)).
  cbn in Hloc. destruct Hloc as [_ [Heq _]]. exact (Hneq Heq).
Qed.

(* =========================================================================
   4. Concrete Session Transitions & Forward Simulation to `AttestedSession`
   ========================================================================= *)

Definition concrete_session_open (v : ConcreteVault) (h : ConcreteContextHandle)
    (expected_cfg : nat) : option ConcreteSession :=
  match resolve_context_handle v h with
  | None => None
  | Some s =>
    if (expected_cfg =? cc_config_digest (cv_config v)) &&
       negb (existsb (Nat.eqb (slot_context_id s)) (cv_spent_contexts v))
    then Some {| cs_bound_handle := h;
                 cs_bound_slot := s;
                 cs_config_digest := expected_cfg;
                 cs_bound_epoch := cv_epoch v;
                 cs_phase := AttestedSession.Fresh;
                 cs_pending_challenge := {| AttestedSession.challenge_nonce := 0;
                                            AttestedSession.challenge_origin := 0;
                                            AttestedSession.challenge_unit_scope := false;
                                            AttestedSession.challenge_domain := 0 |};
                 cs_pending_deadline := 0;
                 cs_used_nonces := [];
                 cs_spent_contexts := cv_spent_contexts v;
                 cs_attested_open := false |}
    else None
  end.

Definition close_concrete_session (cs : ConcreteSession) : ConcreteSession :=
  {| cs_bound_handle := cs_bound_handle cs;
     cs_bound_slot := cs_bound_slot cs;
     cs_config_digest := cs_config_digest cs;
     cs_bound_epoch := cs_bound_epoch cs;
     cs_phase := AttestedSession.Closed;
     cs_pending_challenge := cs_pending_challenge cs;
     cs_pending_deadline := cs_pending_deadline cs;
     cs_used_nonces := cs_used_nonces cs;
     cs_spent_contexts := cs_spent_contexts cs;
     cs_attested_open := false |}.

Definition concrete_begin_appraisal (v : ConcreteVault) (app : ConcreteAppraiser)
    (cs : ConcreteSession) (nonce now deadline : nat)
    : option (ConcreteVault * ConcreteSession * ConcreteWireChallenge) :=
  match cs_phase cs with
  | AttestedSession.Fresh =>
    match resolve_context_handle v (cs_bound_handle cs) with
    | None => None
    | Some s =>
      if (cs_bound_epoch cs =? cv_epoch v) &&
         (cs_config_digest cs =? ca_expected_config_digest app) &&
         (cs_config_digest cs =? cc_config_digest (cv_config v)) &&
         context_slot_eqb s (cs_bound_slot cs) &&
         AttestedSession.profile_bounded (ca_profile app) &&
         (0 <? nonce) && (now <? deadline) &&
         negb (existsb (Nat.eqb nonce) (cs_used_nonces cs)) &&
         negb (existsb (Nat.eqb (slot_context_id s)) (cs_spent_contexts cs)) &&
         negb (existsb (Nat.eqb (slot_context_id s)) (cv_spent_contexts v))
      then
        let pend := {| AttestedSession.challenge_nonce := nonce;
                       AttestedSession.challenge_origin := slot_origin s;
                       AttestedSession.challenge_unit_scope := AttestedSession.unit_policy (ca_policy app);
                       AttestedSession.challenge_domain := AttestedSession.protocol_domain (ca_profile app) |} in
        let cwc := {| cwc_unit_scope := AttestedSession.unit_policy (ca_policy app);
                      cwc_nonce := nonce;
                      cwc_origin := slot_origin s;
                      cwc_domain := AttestedSession.protocol_domain (ca_profile app);
                      cwc_wire_len := 1 |} in
        let cs' := {| cs_bound_handle := cs_bound_handle cs;
                      cs_bound_slot := cs_bound_slot cs;
                      cs_config_digest := cs_config_digest cs;
                      cs_bound_epoch := cs_bound_epoch cs;
                      cs_phase := AttestedSession.Waiting;
                      cs_pending_challenge := pend;
                      cs_pending_deadline := deadline;
                      cs_used_nonces := nonce :: cs_used_nonces cs;
                      cs_spent_contexts := slot_context_id s :: cs_spent_contexts cs;
                      cs_attested_open := false |} in
        let v' := with_vault_contexts v (cv_contexts v) (cv_next_ctx_id v)
                                      (slot_context_id s :: cv_spent_contexts v) in
        Some (v', cs', cwc)
      else None
    end
  | _ => None
  end.

Definition concrete_decide (v : ConcreteVault) (app : ConcreteAppraiser)
    (cs : ConcreteSession) (now : nat) (received : option ConcreteWireEvidence)
    : ConcreteSession * bool :=
  match cs_phase cs with
  | AttestedSession.Waiting =>
    match received with
    | None => (close_concrete_session cs, false)
    | Some cwe =>
      match resolve_context_handle v (cs_bound_handle cs) with
      | None => (close_concrete_session cs, false)
      | Some s =>
        let ev := refine_evidence cwe in
        if (cs_bound_epoch cs =? cv_epoch v) &&
           (cs_config_digest cs =? ca_expected_config_digest app) &&
           (cs_config_digest cs =? cc_config_digest (cv_config v)) &&
           context_slot_eqb s (cs_bound_slot cs) &&
           (cwe_seal_mac cwe =? cv_seal_mac v (ca_hmac_key app) ev) &&
           AttestedSession.appraisal_checks
             (ca_profile app) (ca_policy app) (ca_auth app)
             (refine_session v cs) now (cwe_wire_len cwe) ev
        then ({| cs_bound_handle := cs_bound_handle cs;
                 cs_bound_slot := cs_bound_slot cs;
                 cs_config_digest := cs_config_digest cs;
                 cs_bound_epoch := cs_bound_epoch cs;
                 cs_phase := AttestedSession.Open;
                 cs_pending_challenge := cs_pending_challenge cs;
                 cs_pending_deadline := cs_pending_deadline cs;
                 cs_used_nonces := cs_used_nonces cs;
                 cs_spent_contexts := cs_spent_contexts cs;
                 cs_attested_open := true |}, true)
        else (close_concrete_session cs, false)
      end
    end
  | _ => (close_concrete_session cs, false)
  end.

Definition concrete_fetch_one (v : ConcreteVault) (profile : AttestedSession.AttestationProfile)
    (cs : ConcreteSession) (id_bytes man_bytes obj_bytes : nat)
    (manifest_auth object_matches : bool) : ConcreteSession * bool :=
  let closed := close_concrete_session cs in
  match cs_phase cs, cs_attested_open cs, resolve_context_handle v (cs_bound_handle cs) with
  | AttestedSession.Open, true, Some s =>
    if (cs_bound_epoch cs =? cv_epoch v) &&
       context_slot_eqb s (cs_bound_slot cs) &&
       snd (AttestedSession.fetch_one profile (refine_session v cs)
              id_bytes man_bytes obj_bytes manifest_auth object_matches)
    then (closed, true)
    else (closed, false)
  | _, _, _ => (closed, false)
  end.

Definition concrete_reconnect (v : ConcreteVault) (cs : ConcreteSession)
    (new_h : ConcreteContextHandle) (expected_cfg : nat) : ConcreteSession * bool :=
  match resolve_context_handle v new_h with
  | None => (close_concrete_session cs, false)
  | Some s_new =>
    if (expected_cfg =? cc_config_digest (cv_config v)) &&
       negb (slot_context_id s_new =? slot_context_id (cs_bound_slot cs)) &&
       negb (existsb (Nat.eqb (slot_context_id s_new)) (cs_spent_contexts cs)) &&
       negb (existsb (Nat.eqb (slot_context_id s_new)) (cv_spent_contexts v))
    then ({| cs_bound_handle := new_h;
             cs_bound_slot := s_new;
             cs_config_digest := expected_cfg;
             cs_bound_epoch := cv_epoch v;
             cs_phase := AttestedSession.Fresh;
             cs_pending_challenge := cs_pending_challenge cs;
             cs_pending_deadline := 0;
             cs_used_nonces := cs_used_nonces cs;
             cs_spent_contexts := cs_spent_contexts cs;
             cs_attested_open := false |}, true)
    else (close_concrete_session cs, false)
  end.

Theorem concrete_begin_appraisal_refines :
  forall v app cs nonce now deadline v' cs' cwc,
  concrete_begin_appraisal v app cs nonce now deadline = Some (v', cs', cwc) ->
  cs_phase cs' = AttestedSession.Waiting /\
  refine_challenge cwc = cs_pending_challenge cs' /\
  In (slot_context_id (cs_bound_slot cs')) (cv_spent_contexts v') /\
  In (slot_context_id (cs_bound_slot cs')) (cs_spent_contexts cs') /\
  refine_session v' cs' =
    AttestedSession.begin_appraisal (ca_profile app) (ca_policy app)
      (refine_session v cs) nonce now deadline.
Proof.
  intros v app cs nonce now deadline v' cs' cwc H.
  unfold concrete_begin_appraisal in H.
  destruct (cs_phase cs) eqn:Hph; try discriminate.
  destruct (resolve_context_handle v (cs_bound_handle cs)) as [s|] eqn:Hres; [|discriminate].
  destruct ((cs_bound_epoch cs =? cv_epoch v) &&
            (cs_config_digest cs =? ca_expected_config_digest app) &&
            (cs_config_digest cs =? cc_config_digest (cv_config v)) &&
            context_slot_eqb s (cs_bound_slot cs) &&
            AttestedSession.profile_bounded (ca_profile app) &&
            (0 <? nonce) && (now <? deadline) &&
            negb (existsb (Nat.eqb nonce) (cs_used_nonces cs)) &&
            negb (existsb (Nat.eqb (slot_context_id s)) (cs_spent_contexts cs)) &&
            negb (existsb (Nat.eqb (slot_context_id s)) (cv_spent_contexts v))) eqn:E;
    [|discriminate].
  inversion H; subst. clear H.
  repeat rewrite andb_true_iff in E.
  destruct E as [[[[[[[[[_ _] _] Hslot] Hprof] Hnonce] Hdl] Hn_used] Hcs_spent] _].
  apply context_slot_eqb_eq in Hslot. subst s.
  pose proof (resolved_slot_is_usable v (cs_bound_handle cs) (cs_bound_slot cs) Hres)
    as [Husable _].
  split; [reflexivity|].
  split; [destruct (AttestedSession.unit_policy (ca_policy app)); reflexivity|].
  split; [left; reflexivity|].
  split; [left; reflexivity|].
  unfold refine_session, AttestedSession.begin_appraisal.
  cbn [AttestedSession.phase AttestedSession.protected_context
       AttestedSession.used_nonces AttestedSession.used_contexts].
  rewrite Hph, Hprof, Husable, Hnonce, Hdl, Hn_used.
  cbn [AttestedSession.context_id refine_slot].
  rewrite Hcs_spent. cbn. reflexivity.
Qed.

Theorem concrete_decide_refines :
  forall v app cs now rec cs' ok,
  concrete_decide v app cs now rec = (cs', ok) ->
  (ok = true ->
    exists s cwe,
      rec = Some cwe /\
      resolve_context_handle v (cs_bound_handle cs) = Some s /\
      s = cs_bound_slot cs /\
      cs_bound_epoch cs = cv_epoch v /\
      cs_config_digest cs = ca_expected_config_digest app /\
      cs_config_digest cs = cc_config_digest (cv_config v) /\
      cwe_seal_mac cwe = cv_seal_mac v (ca_hmac_key app) (refine_evidence cwe) /\
      cs_attested_open cs' = true /\
      cs_phase cs' = AttestedSession.Open /\
      snd (AttestedSession.decide (ca_profile app) (fst (refine_appraiser app))
             (snd (refine_appraiser app)) (refine_session v cs) now
             (cwe_wire_len cwe) (Some (refine_evidence cwe))) = true /\
      refine_session v cs' =
        fst (AttestedSession.decide (ca_profile app) (fst (refine_appraiser app))
               (snd (refine_appraiser app)) (refine_session v cs) now
               (cwe_wire_len cwe) (Some (refine_evidence cwe)))) /\
  (ok = false ->
    cs_phase cs' = AttestedSession.Closed /\ cs_attested_open cs' = false).
Proof.
  intros v app cs now rec cs' ok H.
  unfold concrete_decide in H.
  destruct (cs_phase cs) eqn:Hph.
  - inversion H; subst. split; [intro D; discriminate D|intros _; split; reflexivity].
  - destruct rec as [cwe|] eqn:Hrec.
    + destruct (resolve_context_handle v (cs_bound_handle cs)) as [s|] eqn:Hres.
      * destruct ((cs_bound_epoch cs =? cv_epoch v) &&
                  (cs_config_digest cs =? ca_expected_config_digest app) &&
                  (cs_config_digest cs =? cc_config_digest (cv_config v)) &&
                  context_slot_eqb s (cs_bound_slot cs) &&
                  (cwe_seal_mac cwe =? cv_seal_mac v (ca_hmac_key app) (refine_evidence cwe)) &&
                  AttestedSession.appraisal_checks (ca_profile app) (ca_policy app) (ca_auth app)
                    (refine_session v cs) now (cwe_wire_len cwe) (refine_evidence cwe)) eqn:E.
        { inversion H; subst. clear H.
          split; [|intro D; discriminate D]. intros _.
          repeat rewrite andb_true_iff in E.
          destruct E as [[[[[Hep Hcfg1] Hcfg2] Hslot] Hmac] Hchk].
          apply Nat.eqb_eq in Hep, Hcfg1, Hcfg2, Hmac.
          apply context_slot_eqb_eq in Hslot.
          exists s, cwe.
          split; [reflexivity|].
          split; [reflexivity|].
          split; [exact Hslot|].
          split; [exact Hep|].
          split; [exact Hcfg1|].
          split; [exact Hcfg2|].
          split; [exact Hmac|].
          split; [reflexivity|].
          split; [reflexivity|].
          split.
          - unfold AttestedSession.decide, refine_appraiser. cbn [fst snd].
            change (AttestedSession.phase (refine_session v cs)) with (cs_phase cs).
            rewrite Hph, Hchk. reflexivity.
          - unfold AttestedSession.decide, refine_appraiser. cbn [fst snd].
            change (AttestedSession.phase (refine_session v cs)) with (cs_phase cs).
            rewrite Hph, Hchk. unfold AttestedSession.with_phase, refine_session. cbn.
            reflexivity. }
        { inversion H; subst. split; [intro D; discriminate D|intros _; split; reflexivity]. }
      * inversion H; subst. split; [intro D; discriminate D|intros _; split; reflexivity].
    + inversion H; subst. split; [intro D; discriminate D|intros _; split; reflexivity].
  - inversion H; subst. split; [intro D; discriminate D|intros _; split; reflexivity].
  - inversion H; subst. split; [intro D; discriminate D|intros _; split; reflexivity].
Qed.

(*| discharges: R-12-015c, R-09-025a |*)
Theorem concrete_decide_establishes_session_agreement :
  forall v app cs now cwe cs' ledger custody signing_keys_intact,
  AttestedSession.ExporterSecurity custody ->
  AttestedSession.EvidenceAuthenticity (ca_auth app) ledger signing_keys_intact ->
  signing_keys_intact ->
  AttestedSession.LocalContextIntegrity (ca_profile app) ledger (cv_measured v) (cv_aliases v) ->
  AttestedSession.UncompromisedSessionKeys custody ledger (refine_slot v (cs_bound_slot cs)) ->
  AttestedSession.AuthenticatedUnitPseudonyms (cv_aliases v) ->
  AttestedSession.UnitEnrollment (ca_policy app) (refine_slot v (cs_bound_slot cs)) (cv_aliases v) ->
  AttestedSession.PendingBinding (ca_profile app) (ca_policy app) (refine_session v cs) ->
  concrete_decide v app cs now (Some cwe) = (cs', true) ->
  exists event,
    In event ledger /\
    AttestedSession.issued_evidence event = refine_evidence cwe /\
    AttestedSession.SameKeyHolder (AttestedSession.issuer_context event)
                                  (refine_slot v (cs_bound_slot cs)) /\
    cv_measured v (slot_unit (cs_bound_slot cs)) = Some (cwe_generation cwe) /\
    AttestedSession.approved_generation (ca_policy app) (cwe_generation cwe) = true /\
    slot_principal (cs_bound_slot cs) = AttestedSession.required_principal (ca_policy app) /\
    refine_challenge (cwe_challenge cwe) = cs_pending_challenge cs /\
    (AttestedSession.unit_policy (ca_policy app) = true ->
      slot_unit (cs_bound_slot cs) = AttestedSession.expected_unit (ca_policy app)).
Proof.
  intros v app cs now cwe cs' ledger custody signing_keys_intact
    Hex Hauth Hsign Hlocal Hkeys Halias Henroll Hpend Hdec.
  destruct (concrete_decide_refines _ _ _ _ _ _ _ Hdec) as [Hok _].
  destruct (Hok eq_refl)
    as [_ [cwe0 [Hcwe [_ [_ [_ [_ [_ [_ [_ [_ [Habs _]]]]]]]]]]]].
  inversion Hcwe; subst cwe0. clear Hcwe.
  unfold refine_appraiser in Habs. cbn in Habs.
  exact (AttestedSession.attested_session_binding
           (ca_profile app) (ca_policy app) (ca_auth app) ledger
           (cv_measured v) (cv_aliases v) custody signing_keys_intact
           (refine_session v cs) now (cwe_wire_len cwe) (refine_evidence cwe)
           Hex Hauth Hsign Hlocal Hkeys Halias Henroll Hpend Habs).
Qed.

Theorem concrete_fetch_one_refines :
  forall v profile cs id_b man_b obj_b ma oa cs' ok,
  concrete_fetch_one v profile cs id_b man_b obj_b ma oa = (cs', ok) ->
  cs_phase cs' = AttestedSession.Closed /\
  cs_attested_open cs' = false /\
  (ok = true ->
    cs_phase cs = AttestedSession.Open /\
    cs_attested_open cs = true /\
    snd (AttestedSession.fetch_one profile (refine_session v cs) id_b man_b obj_b ma oa) = true) /\
  refine_session v cs' =
    fst (AttestedSession.fetch_one profile (refine_session v cs) id_b man_b obj_b ma oa).
Proof.
  intros v profile cs id_b man_b obj_b ma oa cs' ok H.
  unfold concrete_fetch_one in H.
  destruct (cs_phase cs) eqn:Hph, (cs_attested_open cs) eqn:Hopen,
           (resolve_context_handle v (cs_bound_handle cs)) as [s|] eqn:Hres;
    try (inversion H; subst;
         split; [reflexivity|];
         split; [reflexivity|];
         split; [intro D; discriminate D|];
         unfold AttestedSession.fetch_one, AttestedSession.with_phase, refine_session;
         reflexivity).
  destruct ((cs_bound_epoch cs =? cv_epoch v) &&
            context_slot_eqb s (cs_bound_slot cs) &&
            snd (AttestedSession.fetch_one profile (refine_session v cs)
                   id_b man_b obj_b ma oa)) eqn:E.
  - inversion H; subst. clear H.
    repeat rewrite andb_true_iff in E. destruct E as [[_ _] Hf].
    split; [reflexivity|].
    split; [reflexivity|].
    split; [intros _; repeat split; assumption || reflexivity|].
    unfold AttestedSession.fetch_one, AttestedSession.with_phase, refine_session.
    reflexivity.
  - inversion H; subst.
    split; [reflexivity|].
    split; [reflexivity|].
    split; [intro D; discriminate D|].
    unfold AttestedSession.fetch_one, AttestedSession.with_phase, refine_session.
    reflexivity.
Qed.

Theorem concrete_reconnect_preserves_spent_history :
  forall v cs new_h cfg cs' ok,
  concrete_reconnect v cs new_h cfg = (cs', ok) ->
  cs_spent_contexts cs' = cs_spent_contexts cs /\
  cs_used_nonces cs' = cs_used_nonces cs /\
  (ok = true ->
    exists s_new,
      resolve_context_handle v new_h = Some s_new /\
      cfg = cc_config_digest (cv_config v) /\
      ~ In (slot_context_id s_new) (cs_spent_contexts cs) /\
      ~ In (slot_context_id s_new) (cv_spent_contexts v) /\
      refine_session v cs' = AttestedSession.reconnect (refine_session v cs) (refine_slot v s_new)) /\
  (ok = false -> cs_phase cs' = AttestedSession.Closed).
Proof.
  intros v cs new_h cfg cs' ok H.
  unfold concrete_reconnect in H.
  destruct (resolve_context_handle v new_h) as [s_new|] eqn:Hres.
  - destruct ((cfg =? cc_config_digest (cv_config v)) &&
              negb (slot_context_id s_new =? slot_context_id (cs_bound_slot cs)) &&
              negb (existsb (Nat.eqb (slot_context_id s_new)) (cs_spent_contexts cs)) &&
              negb (existsb (Nat.eqb (slot_context_id s_new)) (cv_spent_contexts v))) eqn:E.
    + inversion H; subst. clear H.
      repeat rewrite andb_true_iff in E.
      destruct E as [[[Hcfg Hdiff] Hcs_sp] Hcv_sp].
      apply Nat.eqb_eq in Hcfg.
      repeat split; try reflexivity; [|intro D; discriminate D].
      intros _. exists s_new.
      split; [reflexivity|].
      split; [exact Hcfg|].
      split.
      { intros Hin.
        assert (Htex : existsb (Nat.eqb (slot_context_id s_new)) (cs_spent_contexts cs) = true).
        { apply existsb_exists. exists (slot_context_id s_new). split; [exact Hin|apply Nat.eqb_refl]. }
        rewrite Htex in Hcs_sp. discriminate Hcs_sp. }
      split.
      { intros Hin.
        assert (Htex : existsb (Nat.eqb (slot_context_id s_new)) (cv_spent_contexts v) = true).
        { apply existsb_exists. exists (slot_context_id s_new). split; [exact Hin|apply Nat.eqb_refl]. }
        rewrite Htex in Hcv_sp. discriminate Hcv_sp. }
      unfold refine_session, AttestedSession.reconnect. cbn.
      apply negb_true_iff in Hdiff, Hcs_sp. rewrite Hdiff, Hcs_sp. reflexivity.
    + inversion H; subst. repeat split; try reflexivity.
      intro D; discriminate D.
  - inversion H; subst. repeat split; try reflexivity.
    intro D; discriminate D.
Qed.

Theorem a_to_b_to_a_concrete_cycle_is_refused :
  forall v app cs nonce now deadline v1 cs1 cwc h_b cfg cs2 cs3 ok3,
  concrete_begin_appraisal v app cs nonce now deadline = Some (v1, cs1, cwc) ->
  concrete_reconnect v1 cs1 h_b cfg = (cs2, true) ->
  concrete_reconnect v1 cs2 (cs_bound_handle cs) cfg = (cs3, ok3) ->
  ok3 = false /\ cs_phase cs3 = AttestedSession.Closed.
Proof.
  intros v app cs nonce now deadline v1 cs1 cwc h_b cfg cs2 cs3 ok3 Hbeg Hrec1 Hrec2.
  destruct (concrete_begin_appraisal_refines _ _ _ _ _ _ _ _ _ Hbeg)
    as [_ [_ [Hin_v1 [Hin_cs1 _]]]].
  destruct (concrete_reconnect_preserves_spent_history _ _ _ _ _ _ Hrec1)
    as [Hsp1 _].
  destruct (concrete_reconnect_preserves_spent_history _ _ _ _ _ _ Hrec2)
    as [_ [_ [Hok3 Hfail3]]].
  destruct ok3; [|split; [reflexivity|apply Hfail3; reflexivity]].
  exfalso.
  destruct (Hok3 eq_refl) as [s_back [Hres_back [_ [_ [Hnot_v1 _]]]]].
  unfold concrete_begin_appraisal in Hbeg.
  destruct (cs_phase cs); try discriminate.
  destruct (resolve_context_handle v (cs_bound_handle cs)) as [s_orig|] eqn:Horig;
    [|discriminate].
  destruct ((cs_bound_epoch cs =? cv_epoch v) &&
            (cs_config_digest cs =? ca_expected_config_digest app) &&
            (cs_config_digest cs =? cc_config_digest (cv_config v)) &&
            context_slot_eqb s_orig (cs_bound_slot cs) &&
            AttestedSession.profile_bounded (ca_profile app) &&
            (0 <? nonce) && (now <? deadline) &&
            negb (existsb (Nat.eqb nonce) (cs_used_nonces cs)) &&
            negb (existsb (Nat.eqb (slot_context_id s_orig)) (cs_spent_contexts cs)) &&
            negb (existsb (Nat.eqb (slot_context_id s_orig)) (cv_spent_contexts v))) eqn:E;
    [|discriminate].
  inversion Hbeg; subst v1 cs1 cwc.
  repeat rewrite andb_true_iff in E.
  destruct E as [[[[[[[[[_ _] _] Hslot] _] _] _] _] _] _].
  apply context_slot_eqb_eq in Hslot.
  assert (Heq_res :
    resolve_context_handle
      (with_vault_contexts v (cv_contexts v) (cv_next_ctx_id v)
         (slot_context_id s_orig :: cv_spent_contexts v))
      (cs_bound_handle cs) =
    resolve_context_handle v (cs_bound_handle cs)).
  { unfold resolve_context_handle, expected_ctx_mac. cbn. reflexivity. }
  rewrite Heq_res, Horig in Hres_back.
  inversion Hres_back; subst s_back.
  apply Hnot_v1. left. reflexivity.
Qed.

Theorem teardown_invalidates_handle :
  forall v h v',
  teardown_context v h = Some v' ->
  resolve_context_handle v' h = None.
Proof.
  intros v h v' H. unfold teardown_context in H.
  destruct (resolve_context_handle v h) as [s|]; [|discriminate].
  inversion H; subst v'. clear H.
  unfold resolve_context_handle. cbn.
  destruct (ch_sealed h && (ch_epoch h =? cv_epoch v)); [|reflexivity].
  rewrite assoc_lookup_set_eq. cbn. reflexivity.
Qed.

Lemma assoc_lookup_retire_map : forall k xs,
  assoc_lookup k (map (fun kv => (fst kv, retire_slot (snd kv))) xs) =
  match assoc_lookup k xs with
  | None => None
  | Some s => Some (retire_slot s)
  end.
Proof.
  intros k xs. induction xs as [|[k' s'] rest IH]; cbn.
  - reflexivity.
  - destruct (k =? k'); [reflexivity|exact IH].
Qed.

Theorem advance_lifecycle_invalidates_all_handles :
  forall v h,
  ch_epoch h <= cv_epoch v ->
  resolve_context_handle (advance_lifecycle v) h = None.
Proof.
  intros v h Hle. unfold resolve_context_handle, advance_lifecycle. cbn.
  destruct (ch_sealed h) eqn:Hs; [|reflexivity].
  destruct (Nat.eqb_spec (ch_epoch h) (S (cv_epoch v))); [lia|].
  reflexivity.
Qed.

Theorem retire_unit_generation_invalidates_unit_handles :
  forall v unit_id new_gen h s,
  resolve_context_handle v h = Some s ->
  slot_unit s = unit_id ->
  resolve_context_handle (retire_unit_generation v unit_id new_gen) h = None.
Proof.
  intros v unit_id new_gen h s Hres Hunit.
  unfold resolve_context_handle in Hres |- *.
  cbn [cv_epoch cv_contexts retire_unit_generation].
  destruct (ch_sealed h && (ch_epoch h =? cv_epoch v)) eqn:Hhd; [|discriminate Hres].
  cbn.
  assert (Hmap : forall k xs,
    assoc_lookup k (map (fun kv =>
      if slot_active (snd kv) && (slot_unit (snd kv) =? unit_id)
      then (fst kv, retire_slot (snd kv)) else kv) xs) =
    match assoc_lookup k xs with
    | None => None
    | Some s0 =>
      if slot_active s0 && (slot_unit s0 =? unit_id)
      then Some (retire_slot s0) else Some s0
    end).
  { intros k xs. induction xs as [|[k' s'] rest IH]; cbn.
    - reflexivity.
    - destruct (slot_active s' && (slot_unit s' =? unit_id)) eqn:E; cbn;
        destruct (k =? k'); try (rewrite E; reflexivity); exact IH. }
  rewrite Hmap.
  destruct (assoc_lookup (ch_slot h) (cv_contexts v)) as [s0|]; [|discriminate].
  destruct (slot_active s0 && negb (slot_retired s0) && negb (slot_key_exposed s0) &&
            (slot_context_id s0 =? ch_context_id h) &&
            (slot_epoch s0 =? cv_epoch v) &&
            slot_tls_eligible (cc_config_digest (cv_config v)) s0 &&
            (ch_mac h =? expected_ctx_mac v (ch_slot h) s0)) eqn:E; [|discriminate].
  inversion Hres; subst s0.
  apply andb_true_iff in E as [E _].
  repeat rewrite andb_true_iff in E.
  destruct E as [[[[[Hact _] _] _] _] _].
  rewrite Hact, Hunit, Nat.eqb_refl. cbn. reflexivity.
Qed.

Theorem expose_key_invalidates_handle :
  forall v h v',
  expose_context_key v h = Some v' ->
  resolve_context_handle v' h = None.
Proof.
  intros v h v' H. unfold expose_context_key in H.
  destruct (resolve_context_handle v h) as [s|]; [|discriminate].
  inversion H; subst v'. clear H.
  unfold resolve_context_handle. cbn.
  destruct (ch_sealed h && (ch_epoch h =? cv_epoch v)); [|reflexivity].
  rewrite assoc_lookup_set_eq. cbn.
  rewrite !andb_false_r. reflexivity.
Qed.

Inductive ConcreteStep (v : ConcreteVault) (app : ConcreteAppraiser)
    : ConcreteSession -> ConcreteSession -> Prop :=
| StepBegin : forall cs nonce now deadline v' cs' cwc,
    concrete_begin_appraisal v app cs nonce now deadline = Some (v', cs', cwc) ->
    ConcreteStep v app cs cs'
| StepDecideAccept : forall cs now cwe cs',
    concrete_decide v app cs now (Some cwe) = (cs', true) ->
    ConcreteStep v app cs cs'
| StepFetchAccept : forall cs id_b man_b obj_b ma oa cs',
    concrete_fetch_one v (ca_profile app) cs id_b man_b obj_b ma oa = (cs', true) ->
    ConcreteStep v app cs cs'
| StepReconnect : forall cs new_h cfg cs',
    concrete_reconnect v cs new_h cfg = (cs', true) ->
    ConcreteStep v app cs cs'.

Inductive AbstractStep (app : ConcreteAppraiser)
    : AttestedSession.Connection -> AttestedSession.Connection -> Prop :=
| AbsBegin : forall c nonce now deadline,
    AttestedSession.phase c = AttestedSession.Fresh ->
    AttestedSession.phase
      (AttestedSession.begin_appraisal (ca_profile app) (ca_policy app) c nonce now deadline) =
      AttestedSession.Waiting ->
    AbstractStep app c
      (AttestedSession.begin_appraisal (ca_profile app) (ca_policy app) c nonce now deadline)
| AbsDecide : forall c now sz ev,
    snd (AttestedSession.decide (ca_profile app) (fst (refine_appraiser app))
           (snd (refine_appraiser app)) c now sz (Some ev)) = true ->
    AbstractStep app c
      (fst (AttestedSession.decide (ca_profile app) (fst (refine_appraiser app))
              (snd (refine_appraiser app)) c now sz (Some ev)))
| AbsFetch : forall c id_b man_b obj_b ma oa,
    snd (AttestedSession.fetch_one (ca_profile app) c id_b man_b obj_b ma oa) = true ->
    AbstractStep app c
      (fst (AttestedSession.fetch_one (ca_profile app) c id_b man_b obj_b ma oa))
| AbsReconnect : forall c new_ctx,
    AttestedSession.phase (AttestedSession.reconnect c new_ctx) = AttestedSession.Fresh ->
    AbstractStep app c (AttestedSession.reconnect c new_ctx).

Theorem concrete_step_forward_simulation :
  forall v app cs cs',
  ConcreteStep v app cs cs' ->
  (forall nonce now deadline v1 cwc,
     concrete_begin_appraisal v app cs nonce now deadline = Some (v1, cs', cwc) ->
     refine_session v1 cs' = refine_session v cs') ->
  AbstractStep app (refine_session v cs) (refine_session v cs').
Proof.
  intros v app cs cs' Hstep Hsame.
  destruct Hstep.
  - destruct (concrete_begin_appraisal_refines _ _ _ _ _ _ _ _ _ H)
      as [Hwait [_ [_ [_ Href]]]].
    assert (Hfresh : AttestedSession.phase (refine_session v cs) = AttestedSession.Fresh).
    { unfold concrete_begin_appraisal in H.
      destruct (cs_phase cs) eqn:Hph; try discriminate.
      unfold refine_session. cbn. exact Hph. }
    rewrite <- (Hsame _ _ _ _ _ H). rewrite Href.
    apply AbsBegin; [exact Hfresh|].
    rewrite <- Href, (Hsame _ _ _ _ _ H).
    unfold refine_session. cbn. exact Hwait.
  - destruct (concrete_decide_refines _ _ _ _ _ _ _ H) as [Hok _].
    destruct (Hok eq_refl)
      as [_ [cwe0 [_ [_ [_ [_ [_ [_ [_ [_ [_ [Hacc Href]]]]]]]]]]]].
    rewrite Href. apply AbsDecide. exact Hacc.
  - destruct (concrete_fetch_one_refines _ _ _ _ _ _ _ _ _ _ H)
      as [_ [_ [Hok Href]]].
    destruct (Hok eq_refl) as [_ [_ Hf]].
    rewrite Href. apply AbsFetch. exact Hf.
  - destruct (concrete_reconnect_preserves_spent_history _ _ _ _ _ _ H)
      as [_ [_ [Hok _]]].
    destruct (Hok eq_refl) as [s_new [_ [_ [_ [_ Href]]]]].
    rewrite Href. apply AbsReconnect.
    rewrite <- Href.
    unfold concrete_reconnect in H.
    destruct (resolve_context_handle v new_h); [|discriminate].
    destruct ((cfg =? cc_config_digest (cv_config v)) &&
              negb (slot_context_id c =? slot_context_id (cs_bound_slot cs)) &&
              negb (existsb (Nat.eqb (slot_context_id c)) (cs_spent_contexts cs)) &&
              negb (existsb (Nat.eqb (slot_context_id c)) (cv_spent_contexts v)));
      [|discriminate].
    inversion H; subst. reflexivity.
Qed.

(* =========================================================================
   5. Inhabited Positive Traces and Refutation / Compromise Witnesses
   ========================================================================= *)

Definition bridge_config_digest : nat := 77.
Definition bridge_hmac_key : nat := 88.
Definition bridge_custody_key : nat := 99.

Definition bridge_config : ConcreteConfig := {|
  cc_profile := AttestedSession.example_profile;
  cc_cred_policy := AttestedSession.example_credential_policy;
  cc_config_digest := bridge_config_digest;
  cc_hmac_key := bridge_hmac_key;
  cc_custody_key := bridge_custody_key;
  cc_max_contexts := 8;
  cc_max_creds := 8
|}.

Definition bridge_derive_exporter (tk : nat) : nat := 1000 + tk.
Definition bridge_ctx_mac (ckey slot cid ep u cfg : nat) : nat :=
  ckey * 13 + slot * 17 + cid * 19 + ep * 23 + u * 29 + cfg.
Definition bridge_cred_mac (ckey slot kid ep u acc : nat) : nat :=
  ckey * 31 + slot * 37 + kid * 41 + ep * 43 + u * 47 + acc.
Definition bridge_seal_mac (hkey : nat) (ev : AttestedSession.Evidence) : nat :=
  hkey * 53 + AttestedSession.evidence_generation ev * 59 +
  AttestedSession.evidence_exporter ev * 61 +
  AttestedSession.challenge_nonce (AttestedSession.evidence_challenge ev) * 67.

Definition bridge_cred_a : CredentialHandles.Credential :=
  CredentialHandles.mk_credential 1 3 [0; 1] [2] 5 4 10 0.
Definition bridge_cred_b : CredentialHandles.Credential :=
  CredentialHandles.mk_credential 1 3 [0; 1] [2] 5 4 10 1.

Definition bridge_vault0 : ConcreteVault := {|
  cv_config := bridge_config;
  cv_epoch := 1;
  cv_next_ctx_id := 1;
  cv_next_cred_id := 1;
  cv_contexts := [];
  cv_creds := [];
  cv_cred_state := AttestedSession.example_credential_state;
  cv_measured := AttestedSession.example_measured;
  cv_aliases := AttestedSession.example_aliases;
  cv_spent_contexts := [];
  cv_derive_exporter := bridge_derive_exporter;
  cv_ctx_mac := bridge_ctx_mac;
  cv_cred_mac := bridge_cred_mac;
  cv_seal_mac := bridge_seal_mac
|}.

Definition bridge_reg (unit_id tk : nat) : ConcreteTLSReg := {|
  reg_unit := unit_id;
  reg_principal := 3;
  reg_origin := 4;
  reg_config_digest := bridge_config_digest;
  reg_traffic_key := tk;
  reg_handshake_complete := true;
  reg_server_authenticated := true;
  reg_early_data := false;
  reg_resumed := false
|}.

Definition bridge_slot (cid unit_id tk : nat) : ConcreteContextSlot := {|
  slot_active := true;
  slot_retired := false;
  slot_key_exposed := false;
  slot_context_id := cid;
  slot_epoch := 1;
  slot_unit := unit_id;
  slot_principal := 3;
  slot_origin := 4;
  slot_config_digest := bridge_config_digest;
  slot_traffic_key := tk;
  slot_handshake_complete := true;
  slot_server_authenticated := true;
  slot_early_data := false;
  slot_resumed := false
|}.

Definition bridge_ctx_handle (slot_idx cid unit_id : nat) : ConcreteContextHandle := {|
  ch_slot := slot_idx;
  ch_context_id := cid;
  ch_epoch := 1;
  ch_sealed := true;
  ch_mac := bridge_ctx_mac bridge_custody_key slot_idx cid 1 unit_id bridge_config_digest
|}.

Definition bridge_cred_handle (slot_idx kid unit_id acc : nat) : ConcreteCredHandle := {|
  crh_slot := slot_idx;
  crh_cred_id := kid;
  crh_epoch := 1;
  crh_sealed := true;
  crh_mac := bridge_cred_mac bridge_custody_key slot_idx kid 1 unit_id acc
|}.

Definition bridge_vault_populated : ConcreteVault := {|
  cv_config := bridge_config;
  cv_epoch := 1;
  cv_next_ctx_id := 4;
  cv_next_cred_id := 3;
  cv_contexts := [(0, bridge_slot 1 1 11); (1, bridge_slot 2 2 22); (2, bridge_slot 3 1 33)];
  cv_creds := [(0, {| ce_active := true; ce_cred_id := 1; ce_epoch := 1; ce_unit := 1; ce_cred := bridge_cred_a |});
               (1, {| ce_active := true; ce_cred_id := 2; ce_epoch := 1; ce_unit := 2; ce_cred := bridge_cred_b |})];
  cv_cred_state := AttestedSession.example_credential_state;
  cv_measured := AttestedSession.example_measured;
  cv_aliases := AttestedSession.example_aliases;
  cv_spent_contexts := [];
  cv_derive_exporter := bridge_derive_exporter;
  cv_ctx_mac := bridge_ctx_mac;
  cv_cred_mac := bridge_cred_mac;
  cv_seal_mac := bridge_seal_mac
|}.

Definition h_ctx_a : ConcreteContextHandle := bridge_ctx_handle 0 1 1.
Definition h_ctx_b : ConcreteContextHandle := bridge_ctx_handle 1 2 2.
Definition h_ctx_a_conc : ConcreteContextHandle := bridge_ctx_handle 2 3 1.
Definition h_cred_a : ConcreteCredHandle := bridge_cred_handle 0 1 1 0.
Definition h_cred_b : ConcreteCredHandle := bridge_cred_handle 1 2 2 1.

Definition bridge_app_sw : ConcreteAppraiser := {|
  ca_profile := AttestedSession.example_profile;
  ca_policy := AttestedSession.software_policy;
  ca_hmac_key := bridge_hmac_key;
  ca_expected_config_digest := bridge_config_digest;
  ca_auth := fun _ => true
|}.

Definition bridge_app_unit : ConcreteAppraiser := {|
  ca_profile := AttestedSession.example_profile;
  ca_policy := AttestedSession.unit_specific_policy;
  ca_hmac_key := bridge_hmac_key;
  ca_expected_config_digest := bridge_config_digest;
  ca_auth := fun _ => true
|}.

(* Inhabited positive end-to-end traces for software policy and unit policy. *)
Theorem inhabited_positive_software_and_unit_traces :
  (exists cs0 v1 cs1 cwc cwe iss v2 cs2 cs3,
     concrete_session_open bridge_vault_populated h_ctx_a bridge_config_digest = Some cs0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_sw cs0 6 1 10 = Some (v1, cs1, cwc) /\
     concrete_quote v1 h_cred_a h_ctx_a (AttestedSession.example_request false) cwc = Some (cwe, iss, v2) /\
     concrete_decide v2 bridge_app_sw cs1 2 (Some cwe) = (cs2, true) /\
     cs_phase cs2 = AttestedSession.Open /\
     concrete_fetch_one v2 AttestedSession.example_profile cs2 4 4 16 true true = (cs3, true) /\
     cs_phase cs3 = AttestedSession.Closed) /\
  (exists cs0 v1 cs1 cwc cwe iss v2 cs2 cs3,
     concrete_session_open bridge_vault_populated h_ctx_a bridge_config_digest = Some cs0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_unit cs0 8 1 10 = Some (v1, cs1, cwc) /\
     concrete_quote v1 h_cred_a h_ctx_a (AttestedSession.example_request true) cwc = Some (cwe, iss, v2) /\
     concrete_decide v2 bridge_app_unit cs1 2 (Some cwe) = (cs2, true) /\
     cs_phase cs2 = AttestedSession.Open /\
     concrete_fetch_one v2 AttestedSession.example_profile cs2 4 4 16 true true = (cs3, true) /\
     cs_phase cs3 = AttestedSession.Closed).
Proof.
  split.
  - repeat eexists; repeat split; reflexivity.
  - repeat eexists; repeat split; reflexivity.
Qed.

(* Refutation witness 1: Replay & parallel-session substitution refused. *)
Example refutation_replay_and_parallel_substitution :
  (exists cs0 v1 cs1 cwc cwe iss v2 cs_rep_0 v_r cs_rep_1 cwc_r cs_out,
     concrete_session_open bridge_vault_populated h_ctx_a bridge_config_digest = Some cs0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_sw cs0 6 1 10 = Some (v1, cs1, cwc) /\
     concrete_quote v1 h_cred_a h_ctx_a (AttestedSession.example_request false) cwc = Some (cwe, iss, v2) /\
     concrete_session_open bridge_vault_populated h_ctx_b bridge_config_digest = Some cs_rep_0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_sw cs_rep_0 7 1 10 = Some (v_r, cs_rep_1, cwc_r) /\
     concrete_decide v_r bridge_app_sw cs_rep_1 2 (Some cwe) = (cs_out, false) /\
     cs_phase cs_out = AttestedSession.Closed) /\
  (exists cs0 v1 cs1 cwc cwe iss v2 cs_out,
     concrete_session_open bridge_vault_populated h_ctx_a bridge_config_digest = Some cs0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_sw cs0 6 1 10 = Some (v1, cs1, cwc) /\
     concrete_quote v1 h_cred_a h_ctx_a_conc (AttestedSession.example_request false) cwc = Some (cwe, iss, v2) /\
     concrete_decide v2 bridge_app_sw cs1 2 (Some cwe) = (cs_out, false) /\
     cs_phase cs_out = AttestedSession.Closed).
Proof.
  split; repeat eexists; repeat split; reflexivity.
Qed.

(* Refutation witness 2: Foreign measured unit B accepted under software policy,
   refused under unit-specific policy for unit A. *)
Example refutation_foreign_unit_under_unit_policy :
  (exists cs0 v1 cs1 cwc cwe iss v2 cs2,
     concrete_session_open bridge_vault_populated h_ctx_b bridge_config_digest = Some cs0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_sw cs0 7 1 10 = Some (v1, cs1, cwc) /\
     concrete_quote v1 h_cred_b h_ctx_b (AttestedSession.example_request false) cwc = Some (cwe, iss, v2) /\
     concrete_decide v2 bridge_app_sw cs1 2 (Some cwe) = (cs2, true)) /\
  (exists cs0 v1 cs1 cwc cwe iss v2 cs2,
     concrete_session_open bridge_vault_populated h_ctx_b bridge_config_digest = Some cs0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_unit cs0 9 1 10 = Some (v1, cs1, cwc) /\
     concrete_quote v1 h_cred_b h_ctx_b (AttestedSession.example_request true) cwc = Some (cwe, iss, v2) /\
     concrete_decide v2 bridge_app_unit cs1 2 (Some cwe) = (cs2, false) /\
     cs_phase cs2 = AttestedSession.Closed).
Proof.
  split; repeat eexists; repeat split; reflexivity.
Qed.

(* Refutation witness 3: Resumed, early-data, incomplete, unauthenticated, and
   wrong-config-digest contexts are refused at registration. *)
Example refutation_ineligible_tls_contexts :
  register_tls_context bridge_vault0 0 {| reg_unit := 1; reg_principal := 3; reg_origin := 4;
    reg_config_digest := bridge_config_digest; reg_traffic_key := 11;
    reg_handshake_complete := true; reg_server_authenticated := true;
    reg_early_data := false; reg_resumed := true |} = None /\
  register_tls_context bridge_vault0 0 {| reg_unit := 1; reg_principal := 3; reg_origin := 4;
    reg_config_digest := bridge_config_digest; reg_traffic_key := 11;
    reg_handshake_complete := true; reg_server_authenticated := true;
    reg_early_data := true; reg_resumed := false |} = None /\
  register_tls_context bridge_vault0 0 {| reg_unit := 1; reg_principal := 3; reg_origin := 4;
    reg_config_digest := bridge_config_digest; reg_traffic_key := 11;
    reg_handshake_complete := false; reg_server_authenticated := true;
    reg_early_data := false; reg_resumed := false |} = None /\
  register_tls_context bridge_vault0 0 {| reg_unit := 1; reg_principal := 3; reg_origin := 4;
    reg_config_digest := bridge_config_digest; reg_traffic_key := 11;
    reg_handshake_complete := true; reg_server_authenticated := false;
    reg_early_data := false; reg_resumed := false |} = None /\
  register_tls_context bridge_vault0 0 {| reg_unit := 1; reg_principal := 3; reg_origin := 4;
    reg_config_digest := 999; reg_traffic_key := 11;
    reg_handshake_complete := true; reg_server_authenticated := true;
    reg_early_data := false; reg_resumed := false |} = None.
Proof. repeat split; reflexivity. Qed.

(* Refutation witness 4: Post-teardown handle use and A-to-B-to-A cycle refusal. *)
Example refutation_post_teardown_and_aba_cycle :
  (exists v_td,
     teardown_context bridge_vault_populated h_ctx_a = Some v_td /\
     resolve_context_handle v_td h_ctx_a = None /\
     concrete_quote v_td h_cred_a h_ctx_a (AttestedSession.example_request false)
       {| cwc_unit_scope := false; cwc_nonce := 6; cwc_origin := 4; cwc_domain := 5; cwc_wire_len := 1 |} = None) /\
  (exists cs0 v1 cs1 cwc cs2 cs3,
     concrete_session_open bridge_vault_populated h_ctx_a bridge_config_digest = Some cs0 /\
     concrete_begin_appraisal bridge_vault_populated bridge_app_sw cs0 6 1 10 = Some (v1, cs1, cwc) /\
     concrete_reconnect v1 cs1 h_ctx_b bridge_config_digest = (cs2, true) /\
     concrete_reconnect v1 cs2 h_ctx_a bridge_config_digest = (cs3, false) /\
     cs_phase cs3 = AttestedSession.Closed).
Proof.
  split; repeat eexists; repeat split; reflexivity.
Qed.

(* Refutation witness 5: Caller-supplied exporter forgery & explicit key/broker
   compromise witness. *)
Example refutation_caller_exporter_and_compromise :
  ~ AttestedSession.LocalContextIntegrity
      (cc_profile bridge_config)
      [broken_caller_exporter_quote bridge_vault_populated (bridge_slot 2 2 22)
         (bridge_derive_exporter 11)
         {| cwc_unit_scope := false; cwc_nonce := 6; cwc_origin := 4; cwc_domain := 5; cwc_wire_len := 1 |}
         7 None]
      (cv_measured bridge_vault_populated)
      (cv_aliases bridge_vault_populated) /\
  (exists v_exp,
     expose_context_key bridge_vault_populated h_ctx_a = Some v_exp /\
     resolve_context_handle v_exp h_ctx_a = None).
Proof.
  split.
  - apply broken_caller_exporter_violates_integrity. discriminate.
  - eexists. split; reflexivity.
Qed.

(* =========================================================================
   6. Closed Non-Vacuity Witnesses (`witness_<Record>`, R-05-166)
   ========================================================================= *)

Definition witness_ConcreteConfig : ConcreteConfig := bridge_config.
Definition witness_ConcreteTLSReg : ConcreteTLSReg := bridge_reg 1 11.
Definition witness_ConcreteContextSlot : ConcreteContextSlot := bridge_slot 1 1 11.
Definition witness_ConcreteContextHandle : ConcreteContextHandle := h_ctx_a.
Definition witness_ConcreteCredEntry : ConcreteCredEntry :=
  {| ce_active := true; ce_cred_id := 1; ce_epoch := 1; ce_unit := 1; ce_cred := bridge_cred_a |}.
Definition witness_ConcreteCredHandle : ConcreteCredHandle := h_cred_a.
Definition witness_ConcreteVault : ConcreteVault := bridge_vault_populated.
Definition witness_ConcreteWireChallenge : ConcreteWireChallenge :=
  {| cwc_unit_scope := false; cwc_nonce := 6; cwc_origin := 4; cwc_domain := 5; cwc_wire_len := 1 |}.
Definition witness_ConcreteWireEvidence : ConcreteWireEvidence :=
  {| cwe_generation := 7;
     cwe_exporter := bridge_derive_exporter 11;
     cwe_challenge := witness_ConcreteWireChallenge;
     cwe_principal := 3;
     cwe_role := 1;
     cwe_alias := None;
     cwe_seal_mac := 0;
     cwe_wire_len := 8 |}.
Definition witness_ConcreteAppraiser : ConcreteAppraiser := bridge_app_sw.
Definition witness_ConcreteSession : ConcreteSession :=
  {| cs_bound_handle := h_ctx_a;
     cs_bound_slot := witness_ConcreteContextSlot;
     cs_config_digest := bridge_config_digest;
     cs_bound_epoch := 1;
     cs_phase := AttestedSession.Fresh;
     cs_pending_challenge := AttestedSession.example_challenge false 0;
     cs_pending_deadline := 0;
     cs_used_nonces := [];
     cs_spent_contexts := [];
     cs_attested_open := false |}.
