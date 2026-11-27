(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   AttestedSession.v

   Symbolic session-agreement model for the attested source-object-fetch
   protocol (see
   [attested-tls-protocol.md](../docs/implementation/attested-tls-protocol.md)),
   reusing [CredentialHandles.v](CredentialHandles.v#authorize_and_charge) for
   R-12-015a's seven authority bindings. R-12-015c binds measured state,
   challenge, protocol, peer policy, and the holder of TLS traffic keys;
   R-09-025a keeps software-only policy distinct from a relying-party-specific
   unit pseudonym.

   Model and explicit premises:
   - Broker-local exporter binding: `issue_local` takes a credential request and
     challenge while reading the holder, principal, origin, measured generation,
     and exporter directly from `ProtectedContext`
     (`local_issuance_reads_the_exporter_from_its_own_context`). Single-attempt
     appraisal (`begin_appraisal`, `decide`) and bounded object fetch
     (`fetch_one`) enforce positive bounds, nonce/context freshness, and
     fail-closed session closure on any malformed, absent, or unauthenticated
     input.
   - Conditional agreement theorems: `ExporterSecurity`,
     `EvidenceAuthenticity` (scoped to received evidence and an issuance-event
     ledger), `LocalContextIntegrity`, `UncompromisedSessionKeys`, and
     `AuthenticatedUnitPseudonyms` enter as explicit premises, inhabited for
     both software and unit policies and paired with concrete attacks when key
     custody, exporter integrity, or unit-alias checks are weakened.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-09-025a R-12-015a R-12-015c
   SHA256: 12f1a3c97c11a7a5e7923c7d8c3d270b012e3a706514017a84da445ad7173f5c
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Bool Arith Lia.
Require CredentialHandles.
Import ListNotations.

Record ProtectedContext : Type := {
  context_id : nat;
  context_unit : nat; (* Ghost identity of the actual traffic-key holder. *)
  context_principal : nat;
  context_origin : nat;
  context_exporter : nat;
  handshake_complete : bool;
  server_authenticated : bool;
  early_data : bool;
  resumed : bool
}.

Definition context_usable (c : ProtectedContext) : bool :=
  handshake_complete c && server_authenticated c && negb (early_data c) && negb (resumed c).

Record AttestationProfile : Type := {
  protocol_domain : nat;
  attester_role : nat;
  attest_operation : nat;
  request_bound : nat;
  evidence_bound : nat;
  manifest_bound : nat;
  object_bound : nat
}.

Definition profile_bounded (p : AttestationProfile) : bool :=
  (0 <? request_bound p) && (0 <? evidence_bound p) &&
  (0 <? manifest_bound p) && (0 <? object_bound p).

Theorem all_context_prerequisites_are_required : forall c,
  context_usable c = true -> handshake_complete c = true /\
  server_authenticated c = true /\ early_data c = false /\ resumed c = false.
Proof.
  intros c H. unfold context_usable in H. repeat rewrite andb_true_iff in H.
  destruct H as [[[Hcomplete Hserver] Hearly] Hresumed].
  apply negb_true_iff in Hearly. apply negb_true_iff in Hresumed.
  repeat split; assumption.
Qed.

Theorem precisely_positive_composition_bounds_are_usable : forall p,
  profile_bounded p = true <-> 0 < request_bound p /\ 0 < evidence_bound p /\
    0 < manifest_bound p /\ 0 < object_bound p.
Proof.
  intros p. unfold profile_bounded. repeat rewrite andb_true_iff.
  repeat rewrite Nat.ltb_lt. tauto.
Qed.

Record Challenge : Type := {
  challenge_nonce : nat;
  challenge_origin : nat;
  challenge_unit_scope : bool;
  challenge_domain : nat
}.

Definition challenge_eq_dec : forall a b : Challenge, {a = b} + {a <> b}.
Proof. decide equality; try apply Nat.eq_dec; decide equality. Defined.

Definition challenge_equalb (a b : Challenge) : bool :=
  if challenge_eq_dec a b then true else false.

Record Evidence : Type := {
  evidence_generation : nat;
  evidence_exporter : nat;
  evidence_challenge : Challenge;
  evidence_principal : nat;
  evidence_role : nat;
  evidence_alias : option nat
}.

Definition evidence_eq_dec : forall a b : Evidence, {a = b} + {a <> b}.
Proof.
  decide equality; try apply Nat.eq_dec; try apply challenge_eq_dec.
  decide equality. apply Nat.eq_dec.
Defined.

Definition evidence_equalb (a b : Evidence) : bool :=
  if evidence_eq_dec a b then true else false.

Definition option_nat_equalb (a b : option nat) : bool :=
  match a, b with
  | None, None => true
  | Some x, Some y => x =? y
  | _, _ => false
  end.

Lemma option_nat_equalb_exact : forall a b, option_nat_equalb a b = true -> a = b.
Proof.
  intros [a|] [b|] H; cbn in H; try discriminate; try reflexivity.
  apply Nat.eqb_eq in H. subst. reflexivity.
Qed.

Definition Measurement : Type := nat -> option nat.
Definition UnitAliases : Type := nat -> nat -> option nat.

Record Issuance : Type := {
  issued_evidence : Evidence;
  issuer_context : ProtectedContext
}.

(* The protected runtime supplies measured and aliases. The request contains
   no exporter. Numeric scope atoms 0/1 encode software/unit policy, rather
   than choosing any deployment magnitude. *)
Definition local_request_matches (p : AttestationProfile) (c : ProtectedContext)
    (q : Challenge) (r : CredentialHandles.ClientRequest) : bool :=
  (CredentialHandles.request_role r =? attester_role p) &&
  (CredentialHandles.request_principal r =? context_principal c) &&
  (CredentialHandles.request_scope r =? if challenge_unit_scope q then 1 else 0) &&
  (CredentialHandles.request_operation r =? attest_operation p) &&
  (CredentialHandles.request_transcript r =? protocol_domain p) &&
  (length (CredentialHandles.request_bytes r) <=? request_bound p) &&
  (challenge_origin q =? context_origin c) &&
  (challenge_domain q =? protocol_domain p) && (0 <? challenge_nonce q).

Definition make_evidence (p : AttestationProfile) (c : ProtectedContext)
    (q : Challenge) (generation : nat) (alias : option nat) : Evidence :=
  {| evidence_generation := generation; evidence_exporter := context_exporter c;
     evidence_challenge := q; evidence_principal := context_principal c;
     evidence_role := attester_role p; evidence_alias := alias |}.

Definition issue_local (p : AttestationProfile) (cp : CredentialHandles.CredentialPolicy)
    (credential : CredentialHandles.Credential) (server : CredentialHandles.ServerState)
    (request : CredentialHandles.ClientRequest) (c : ProtectedContext)
    (q : Challenge) (measured : Measurement) (aliases : UnitAliases)
    : option (Issuance * CredentialHandles.ServerState) :=
  if profile_bounded p && context_usable c && local_request_matches p c q request then
    match measured (context_unit c) with
    | None => None
    | Some generation =>
      let alias := if challenge_unit_scope q
                   then aliases (context_origin c) (context_unit c) else None in
      if challenge_unit_scope q &&
         match alias with None => true | Some _ => false end then None else
      match CredentialHandles.authorize_and_charge cp credential server request with
      | None => None
      | Some charged => Some
          ({| issued_evidence := make_evidence p c q generation alias;
              issuer_context := c |}, charged)
      end
    end
  else None.

Theorem local_issuance_reads_the_exporter_from_its_own_context :
  forall p cp cr s r c q measured aliases event charged,
  issue_local p cp cr s r c q measured aliases = Some (event, charged) ->
  evidence_exporter (issued_evidence event) = context_exporter c /\
  issuer_context event = c /\
  measured (context_unit c) = Some (evidence_generation (issued_evidence event)) /\
  CredentialHandles.authorize_and_charge cp cr s r = Some charged.
Proof.
  intros p cp cr s r c q measured aliases event charged H.
  unfold issue_local in H.
  destruct (profile_bounded p && context_usable c && local_request_matches p c q r); [|discriminate].
  destruct (measured (context_unit c)) as [generation|] eqn:Hg; [|discriminate].
  destruct (challenge_unit_scope q &&
    match if challenge_unit_scope q then aliases (context_origin c) (context_unit c) else None
    with None => true | Some _ => false end); [discriminate|].
  destruct (CredentialHandles.authorize_and_charge cp cr s r) as [next|] eqn:Ha;
    [|discriminate].
  inversion H; subst. repeat split; assumption || reflexivity.
Qed.

Record AppraisalPolicy : Type := {
  approved_generation : nat -> bool;
  required_principal : nat;
  unit_policy : bool;
  expected_alias : nat;
  expected_unit : nat (* Ghost target of authenticated origin-specific enrollment. *)
}.

Definition policy_alias (p : AppraisalPolicy) : option nat :=
  if unit_policy p then Some (expected_alias p) else None.

Inductive Phase : Type := Fresh | Waiting | Open | Closed.

Record Connection : Type := {
  protected_context : ProtectedContext;
  phase : Phase;
  pending_challenge : Challenge;
  pending_deadline : nat;
  used_nonces : list nat;
  used_contexts : list nat
}.

Definition with_phase (c : Connection) (ph : Phase) : Connection :=
  {| protected_context := protected_context c; phase := ph;
     pending_challenge := pending_challenge c; pending_deadline := pending_deadline c;
     used_nonces := used_nonces c; used_contexts := used_contexts c |}.

Definition begin_appraisal (profile : AttestationProfile) (policy : AppraisalPolicy)
    (c : Connection) (nonce now deadline : nat) : Connection :=
  match phase c with
  | Fresh =>
    if profile_bounded profile && context_usable (protected_context c) && (0 <? nonce) && (now <? deadline) &&
       negb (existsb (Nat.eqb nonce) (used_nonces c)) &&
       negb (existsb (Nat.eqb (context_id (protected_context c))) (used_contexts c)) then
    {| protected_context := protected_context c; phase := Waiting;
       pending_challenge := {| challenge_nonce := nonce;
         challenge_origin := context_origin (protected_context c);
         challenge_unit_scope := unit_policy policy; challenge_domain := protocol_domain profile |};
       pending_deadline := deadline; used_nonces := nonce :: used_nonces c;
       used_contexts := context_id (protected_context c) :: used_contexts c |}
    else with_phase c Closed
  | _ => c
  end.

Definition appraisal_checks (profile : AttestationProfile) (policy : AppraisalPolicy)
    (authentic : Evidence -> bool) (c : Connection) (now wire_bytes : nat) (q : Evidence) : bool :=
  context_usable (protected_context c) && (now <? pending_deadline c) &&
  (wire_bytes <=? evidence_bound profile) && authentic q &&
  challenge_equalb (evidence_challenge q) (pending_challenge c) &&
  (evidence_exporter q =? context_exporter (protected_context c)) &&
  (evidence_role q =? attester_role profile) &&
  (evidence_principal q =? required_principal policy) &&
  approved_generation policy (evidence_generation q) &&
  option_nat_equalb (evidence_alias q) (policy_alias policy).

(* One terminal decision consumes the waiting attempt even for malformed,
   absent, stale or unauthentic evidence. There is no weaker fallback. *)
Definition decide (profile : AttestationProfile) (policy : AppraisalPolicy)
    (authentic : Evidence -> bool) (c : Connection) (now wire_bytes : nat)
    (received : option Evidence) : Connection * bool :=
  match phase c with
  | Waiting =>
    match received with
    | Some q => if appraisal_checks profile policy authentic c now wire_bytes q
                then (with_phase c Open, true) else (with_phase c Closed, false)
    | None => (with_phase c Closed, false)
    end
  | _ => (with_phase c Closed, false)
  end.

Theorem absent_evidence_never_authenticates : forall p policy auth c now size,
  snd (decide p policy auth c now size None) = false.
Proof. intros. unfold decide. destruct (phase c); reflexivity. Qed.

(* One bounded fetch follows authentication. The reference-manifest and
   object-identity verifiers are protected adapter results, not request
   fields. Every result closes the connection, including malformed input. *)
Definition fetch_one (profile : AttestationProfile) (c : Connection)
    (identity_bytes manifest_bytes object_bytes : nat)
    (manifest_authenticated object_matches : bool) : Connection * bool :=
  (with_phase c Closed,
   match phase c with
   | Open => profile_bounded profile &&
      (identity_bytes <=? request_bound profile) &&
      (manifest_bytes <=? manifest_bound profile) &&
      (object_bytes <=? object_bound profile) && manifest_authenticated && object_matches
   | _ => false
   end).

Theorem fetch_requires_authentication_bounds_and_verified_content :
  forall profile c id_bytes manifest_bytes object_bytes manifest_auth object_auth,
  snd (fetch_one profile c id_bytes manifest_bytes object_bytes manifest_auth object_auth) = true ->
  phase c = Open /\ id_bytes <= request_bound profile /\
  manifest_bytes <= manifest_bound profile /\ object_bytes <= object_bound profile /\
  manifest_auth = true /\ object_auth = true.
Proof.
  intros profile c id_bytes manifest_bytes object_bytes manifest_auth object_auth H.
  unfold fetch_one in H. cbn in H. destruct (phase c) eqn:E; try discriminate.
  repeat rewrite andb_true_iff in H.
  destruct H as [[[[[Hbounded Hid] Hmanifest] Hobject] Hma] Hoa].
  apply Nat.leb_le in Hid. apply Nat.leb_le in Hmanifest. apply Nat.leb_le in Hobject.
  repeat split; assumption || reflexivity.
Qed.

Theorem every_fetch_consumes_its_connection : forall p c i m o ma oa,
  phase (fst (fetch_one p c i m o ma oa)) = Closed.
Proof. reflexivity. Qed.

(* Reconnection preserves the used-challenge history and requires another
   protected session identity. There is no reset-to-Fresh for the old handle. *)
Definition reconnect (c : Connection) (new_context : ProtectedContext) : Connection :=
  if (context_id new_context =? context_id (protected_context c)) ||
     existsb (Nat.eqb (context_id new_context)) (used_contexts c) then with_phase c Closed
  else {| protected_context := new_context; phase := Fresh;
          pending_challenge := pending_challenge c; pending_deadline := 0;
          used_nonces := used_nonces c; used_contexts := used_contexts c |}.

Theorem reconnecting_keeps_challenge_history : forall c new_context,
  used_nonces (reconnect c new_context) = used_nonces c.
Proof. intros. unfold reconnect. destruct ((context_id new_context =? context_id (protected_context c)) || existsb (Nat.eqb (context_id new_context)) (used_contexts c)); reflexivity. Qed.

Theorem reconnecting_the_same_session_cannot_reopen_it : forall c new_context,
  context_id new_context = context_id (protected_context c) ->
  phase (reconnect c new_context) = Closed.
Proof. intros c new_context H. unfold reconnect. rewrite H, Nat.eqb_refl. reflexivity. Qed.

Theorem every_decision_consumes_the_waiting_attempt : forall p policy auth c now size q,
  phase (fst (decide p policy auth c now size q)) <> Waiting /\
  phase (fst (decide p policy auth c now size q)) <> Fresh.
Proof.
  intros. unfold decide. destruct (phase c); try (cbn; split; discriminate).
  destruct q as [q|]; [|cbn; split; discriminate].
  destruct (appraisal_checks p policy auth c now size q); cbn; split; discriminate.
Qed.

Theorem authentication_cannot_run_twice_on_one_connection : forall p policy auth c t n q t2 n2 q2,
  snd (decide p policy auth (fst (decide p policy auth c t n q)) t2 n2 q2) = false.
Proof.
  intros. unfold decide at 2. destruct (phase c); try reflexivity.
  destruct q as [q|]; [|reflexivity].
  destruct (appraisal_checks p policy auth c t n q); reflexivity.
Qed.

Theorem a_used_context_cannot_begin_another_lifecycle : forall p policy c nonce now deadline,
  phase c <> Fresh -> begin_appraisal p policy c nonce now deadline = c.
Proof. intros. unfold begin_appraisal. destruct (phase c); contradiction || reflexivity. Qed.

Theorem a_spent_context_is_refused_even_in_a_fresh_record : forall p policy c nonce now deadline,
  phase c = Fresh -> In (context_id (protected_context c)) (used_contexts c) ->
  phase (begin_appraisal p policy c nonce now deadline) = Closed.
Proof.
  intros p policy c nonce now deadline Hfresh Hused.
  assert (E : existsb (Nat.eqb (context_id (protected_context c))) (used_contexts c) = true).
  { apply existsb_exists. exists (context_id (protected_context c)).
    split; [exact Hused|apply Nat.eqb_refl]. }
  unfold begin_appraisal. rewrite Hfresh, E. cbn. rewrite andb_false_r. reflexivity.
Qed.
Theorem any_failed_guard_refuses_and_closes : forall p policy auth c now size q,
  phase c = Waiting -> appraisal_checks p policy auth c now size q = false ->
  decide p policy auth c now size (Some q) = (with_phase c Closed, false).
Proof. intros p policy auth c now size q Hphase Hcheck. unfold decide. rewrite Hphase, Hcheck. reflexivity. Qed.

Definition SameKeyHolder (a b : ProtectedContext) : Prop :=
  context_id a = context_id b /\ context_unit a = context_unit b /\
  context_principal a = context_principal b /\ context_origin a = context_origin b.

Definition ExporterSecurity (custody : ProtectedContext -> Prop) : Prop :=
  forall a b, context_usable a = true -> context_usable b = true ->
  custody a -> custody b -> context_exporter a = context_exporter b -> SameKeyHolder a b.

Definition EvidenceAuthenticity (authentic : Evidence -> bool) (ledger : list Issuance)
    (signing_keys_intact : Prop) : Prop :=
  signing_keys_intact -> forall received, authentic received = true ->
  exists event, In event ledger /\ issued_evidence event = received.

Definition LocalContextIntegrity (profile : AttestationProfile) (ledger : list Issuance)
    (measured : Measurement) (aliases : UnitAliases) : Prop :=
  forall event, In event ledger ->
  let q := issued_evidence event in let c := issuer_context event in
  context_usable c = true /\ evidence_exporter q = context_exporter c /\
  measured (context_unit c) = Some (evidence_generation q) /\
  evidence_principal q = context_principal c /\
  evidence_role q = attester_role profile /\
  challenge_origin (evidence_challenge q) = context_origin c /\
  evidence_alias q = if challenge_unit_scope (evidence_challenge q)
                     then aliases (context_origin c) (context_unit c) else None.

Definition UncompromisedSessionKeys (custody : ProtectedContext -> Prop)
    (ledger : list Issuance) (target : ProtectedContext) : Prop :=
  custody target /\ forall event, In event ledger -> custody (issuer_context event).

Definition AuthenticatedUnitPseudonyms (aliases : UnitAliases) : Prop :=
  forall origin a b alias, aliases origin a = Some alias -> aliases origin b = Some alias -> a = b.

Definition UnitEnrollment (policy : AppraisalPolicy) (c : ProtectedContext)
    (aliases : UnitAliases) : Prop :=
  unit_policy policy = true -> aliases (context_origin c) (expected_unit policy) =
                             Some (expected_alias policy).

Definition PendingBinding (profile : AttestationProfile) (policy : AppraisalPolicy)
    (c : Connection) : Prop :=
  challenge_origin (pending_challenge c) = context_origin (protected_context c) /\
  challenge_unit_scope (pending_challenge c) = unit_policy policy /\
  challenge_domain (pending_challenge c) = protocol_domain profile /\
  0 < challenge_nonce (pending_challenge c).

Theorem issued_events_have_protected_context_provenance :
  forall p cp credential server request c q measured aliases event charged,
  issue_local p cp credential server request c q measured aliases = Some (event, charged) ->
  LocalContextIntegrity p [event] measured aliases.
Proof.
  intros p cp credential server request c q measured aliases event charged H other Hin.
  cbn in Hin. destruct Hin as [Heq|[]]. subst other.
  unfold issue_local in H.
  destruct (profile_bounded p && context_usable c && local_request_matches p c q request) eqn:E;
    [|discriminate].
  apply andb_true_iff in E as [E Hrequest]. apply andb_true_iff in E as [_ Husable].
  unfold local_request_matches in Hrequest. repeat rewrite andb_true_iff in Hrequest.
  destruct Hrequest as [[[[[[[[Hrole Hprincipal] Hscope] Hop] Hdomain] Hsize] Horigin] Hcdomain] Hnonce].
  apply Nat.eqb_eq in Horigin.
  destruct (measured (context_unit c)) as [generation|] eqn:Hg; [|discriminate].
  destruct (challenge_unit_scope q &&
    match if challenge_unit_scope q then aliases (context_origin c) (context_unit c) else None
    with None => true | Some _ => false end); [discriminate|].
  destruct (CredentialHandles.authorize_and_charge cp credential server request) as [next|];
    [|discriminate].
  inversion H; subst event. cbn. repeat split; assumption || reflexivity.
Qed.

Theorem beginning_an_attempt_binds_its_pending_context : forall p policy c nonce now deadline,
  phase (begin_appraisal p policy c nonce now deadline) = Waiting ->
  phase c = Fresh -> PendingBinding p policy (begin_appraisal p policy c nonce now deadline).
Proof.
  intros p policy c nonce now deadline Hwait Hfresh.
  unfold begin_appraisal in *. rewrite Hfresh in *.
  destruct (profile_bounded p && context_usable (protected_context c) &&
    (0 <? nonce) && (now <? deadline) && negb (existsb (Nat.eqb nonce) (used_nonces c)) &&
    negb (existsb (Nat.eqb (context_id (protected_context c))) (used_contexts c))) eqn:E;
    [|discriminate].
  repeat rewrite andb_true_iff in E. destruct E as [[[[[_ _] Hnonce] _] _] _].
  apply Nat.ltb_lt in Hnonce. unfold PendingBinding. cbn. repeat split; assumption || reflexivity.
Qed.

Lemma accepted_checks : forall p policy auth c now size q,
  snd (decide p policy auth c now size (Some q)) = true ->
  context_usable (protected_context c) = true /\ auth q = true /\
  evidence_challenge q = pending_challenge c /\
  evidence_exporter q = context_exporter (protected_context c) /\
  evidence_principal q = required_principal policy /\
  approved_generation policy (evidence_generation q) = true /\
  evidence_alias q = policy_alias policy.
Proof.
  intros p policy auth c now size q H. unfold decide in H.
  destruct (phase c); try discriminate.
  destruct (appraisal_checks p policy auth c now size q) eqn:E; [|discriminate].
  unfold appraisal_checks in E.
  repeat rewrite andb_true_iff in E.
  destruct E as [[[[[[[[[Hctx Htime] Hsize] Hauth] Hchallenge] Hexporter] Hrole] Hprincipal] Hg] Ha].
  unfold challenge_equalb in Hchallenge.
  destruct (challenge_eq_dec (evidence_challenge q) (pending_challenge c)); [|discriminate].
  apply Nat.eqb_eq in Hexporter. apply Nat.eqb_eq in Hprincipal.
  apply option_nat_equalb_exact in Ha. repeat split; assumption.
Qed.

Theorem replay_with_a_different_challenge_is_refused : forall p policy auth c t size q,
  evidence_challenge q <> pending_challenge c ->
  snd (decide p policy auth c t size (Some q)) = false.
Proof.
  intros p policy auth c t size q Hneq.
  destruct (snd (decide p policy auth c t size (Some q))) eqn:E; [|reflexivity].
  destruct (accepted_checks p policy auth c t size q E) as [_ [_ [H _]]]. contradiction.
Qed.

Theorem concurrent_session_exporter_substitution_is_refused : forall p policy auth c t size q,
  evidence_exporter q <> context_exporter (protected_context c) ->
  snd (decide p policy auth c t size (Some q)) = false.
Proof.
  intros p policy auth c t size q Hneq.
  destruct (snd (decide p policy auth c t size (Some q))) eqn:E; [|reflexivity].
  destruct (accepted_checks p policy auth c t size q E) as [_ [_ [_ [H _]]]]. contradiction.
Qed.

Theorem a_different_unit_alias_is_refused : forall p policy auth c t size q,
  evidence_alias q <> policy_alias policy ->
  snd (decide p policy auth c t size (Some q)) = false.
Proof.
  intros p policy auth c t size q Hneq.
  destruct (snd (decide p policy auth c t size (Some q))) eqn:E; [|reflexivity].
  destruct (accepted_checks p policy auth c t size q E) as [_ [_ [_ [_ [_ [_ H]]]]]]. contradiction.
Qed.

(* Every foundational premise is scoped and used. Signing-key compromise
   releases EvidenceAuthenticity; session-key compromise releases exporter
   security's custody premise. Neither is silently excluded by an axiom. *)
(*| discharges: R-12-015c, R-09-025a |*)
Theorem attested_session_binding :
  forall profile policy auth ledger measured aliases custody signing_keys_intact c now size q,
  ExporterSecurity custody -> EvidenceAuthenticity auth ledger signing_keys_intact ->
  signing_keys_intact -> LocalContextIntegrity profile ledger measured aliases ->
  UncompromisedSessionKeys custody ledger (protected_context c) ->
  AuthenticatedUnitPseudonyms aliases -> UnitEnrollment policy (protected_context c) aliases ->
  PendingBinding profile policy c ->
  snd (decide profile policy auth c now size (Some q)) = true ->
  exists event, In event ledger /\ issued_evidence event = q /\
    SameKeyHolder (issuer_context event) (protected_context c) /\
    measured (context_unit (protected_context c)) = Some (evidence_generation q) /\
    approved_generation policy (evidence_generation q) = true /\
    context_principal (protected_context c) = required_principal policy /\
    evidence_challenge q = pending_challenge c /\
    (unit_policy policy = true -> context_unit (protected_context c) = expected_unit policy).
Proof.
  intros profile policy auth ledger measured aliases custody signing_keys_intact c now size q
    Hex Hauth Hsign Hlocal [Htarget Hkeys] Halias Henroll Hpending Haccept.
  destruct (accepted_checks profile policy auth c now size q Haccept)
    as [Hctx [Hverified [Hchallenge [Hexporter [Hprincipal [Hg Hqa]]]]]].
  destruct (Hauth Hsign q Hverified) as [event [Hin Hevent]].
  specialize (Hlocal event Hin). cbn in Hlocal. rewrite Hevent in Hlocal.
  destruct Hlocal as [Hi [Heb [Hm [Hp [Hr [Ho Ha]]]]]].
  assert (Hholder : SameKeyHolder (issuer_context event) (protected_context c)).
  { apply Hex; try assumption; [apply Hkeys; exact Hin|congruence]. }
  destruct Hholder as [Hid [Hu [Hpr Horigin]]].
  exists event. split; [exact Hin|]. split; [exact Hevent|].
  split; [repeat split; assumption|].
  split; [rewrite <- Hu; exact Hm|]. split; [exact Hg|].
  split; [congruence|]. split; [exact Hchallenge|]. intros Hunit.
  destruct Hpending as [_ [Hscope _]].
  rewrite Hchallenge, Hscope, Hunit in Ha.
  unfold policy_alias in Hqa. rewrite Hunit in Hqa.
  specialize (Henroll Hunit).
  apply (Halias (context_origin (protected_context c))
     (context_unit (protected_context c)) (expected_unit policy) (expected_alias policy));
    [rewrite <- Hu, <- Horigin; congruence|exact Henroll].
Qed.

(* A forwarding path changes neither bytes nor the intended holder. The
   transport topology is deliberately absent from the appraisal predicate. *)
Definition forward_bytes (_route : list nat) (q : Evidence) : Evidence := q.

Theorem forwarding_preserves_the_same_appraisal : forall route profile policy auth c t size q,
  decide profile policy auth c t size (Some (forward_bytes route q)) =
  decide profile policy auth c t size (Some q).
Proof. reflexivity. Qed.

Definition records_open (c : Connection) (holders : list nat) (sender : nat) : bool :=
  match phase c with Open => existsb (Nat.eqb sender) holders | _ => false end.

Theorem forwarding_does_not_grant_record_authority : forall c holders sender,
  ~ In sender holders -> records_open c holders sender = false.
Proof.
  intros c holders sender H. unfold records_open. destruct (phase c); try reflexivity.
  destruct (existsb (Nat.eqb sender) holders) eqn:E; [|reflexivity].
  apply existsb_exists in E as [x [Hin Heq]]. apply Nat.eqb_eq in Heq. subst. contradiction.
Qed.

(* =========================================================================
   Concrete inhabited model and substitution probes. Numeric atoms below
   are fixtures, not composition constants or wire-format choices.
   ========================================================================= *)

Definition example_context (id unit principal origin exporter : nat) : ProtectedContext :=
  {| context_id := id; context_unit := unit; context_principal := principal;
     context_origin := origin; context_exporter := exporter;
     handshake_complete := true; server_authenticated := true; early_data := false; resumed := false |}.
Definition context_a := example_context 1 1 3 4 11.
Definition context_b := example_context 2 2 3 4 22.
Definition context_a_concurrent := example_context 3 1 3 4 33.
Definition example_profile : AttestationProfile :=
  {| protocol_domain := 5; attester_role := 1; attest_operation := 2;
     request_bound := 4; evidence_bound := 8; manifest_bound := 4; object_bound := 16 |}.
Definition software_policy : AppraisalPolicy :=
  {| approved_generation := fun n => n =? 7; required_principal := 3;
     unit_policy := false; expected_alias := 9; expected_unit := 1 |}.
Definition unit_specific_policy : AppraisalPolicy :=
  {| approved_generation := fun n => n =? 7; required_principal := 3;
     unit_policy := true; expected_alias := 9; expected_unit := 1 |}.
Definition example_challenge (unit_scope : bool) (nonce : nat) : Challenge :=
  {| challenge_nonce := nonce; challenge_origin := 4;
     challenge_unit_scope := unit_scope; challenge_domain := 5 |}.
Definition example_fresh (ctx : ProtectedContext) : Connection :=
  {| protected_context := ctx; phase := Fresh; pending_challenge := example_challenge false 0;
     pending_deadline := 0; used_nonces := []; used_contexts := [] |}.
Definition waiting_for (policy : AppraisalPolicy) (ctx : ProtectedContext) (nonce : nat) :=
  begin_appraisal example_profile policy (example_fresh ctx) nonce 0 10.
Definition example_measured : Measurement := fun _ => Some 7.
Definition example_aliases : UnitAliases := fun origin unit =>
  if origin =? 4 then Some (8 + unit) else None.
Definition example_issuance (ctx : ProtectedContext) (unit_scope : bool) (nonce : nat) : Issuance :=
  {| issued_evidence := make_evidence example_profile ctx (example_challenge unit_scope nonce)
       7 (if unit_scope then example_aliases (context_origin ctx) (context_unit ctx) else None);
     issuer_context := ctx |}.
Definition event_a := example_issuance context_a false 6.
Definition event_b := example_issuance context_b false 6.
Definition event_concurrent := example_issuance context_a_concurrent false 6.
Definition event_a_unit := example_issuance context_a true 6.
Definition event_b_unit := example_issuance context_b true 6.
Definition example_ledger := [event_a; event_b; event_concurrent; event_a_unit; event_b_unit].
Definition ledger_authentic (ledger : list Issuance) (q : Evidence) : bool :=
  existsb (fun e => evidence_equalb (issued_evidence e) q) ledger.
Definition example_auth := ledger_authentic example_ledger.

Definition example_credential_policy : CredentialHandles.CredentialPolicy :=
  CredentialHandles.mk_policy 2 4 2 3 6 (fun _ _ => 4)
    (fun role operation => (role =? 1) && (operation =? 2))
    (fun _ _ => false) (fun expiry now => now <? expiry) Nat.leb.
Definition example_credential : CredentialHandles.Credential :=
  CredentialHandles.mk_credential 1 3 [0; 1] [2] 5 1 10 0.
Definition example_credential_state : CredentialHandles.ServerState :=
  CredentialHandles.mk_server (fun _ => 0) 1 (fun _ _ _ => true).
Definition example_request (unit_scope : bool) : CredentialHandles.ClientRequest :=
  CredentialHandles.mk_request 1 3 (if unit_scope then 1 else 0) 2 5 [6].

Example the_broker_issues_the_concrete_events_and_charges_the_shared_account :
  issue_local example_profile example_credential_policy example_credential example_credential_state
    (example_request false) context_a (example_challenge false 6) example_measured example_aliases =
    Some (event_a, CredentialHandles.charge example_credential_state 0) /\
  issue_local example_profile example_credential_policy example_credential example_credential_state
    (example_request true) context_a (example_challenge true 6) example_measured example_aliases =
    Some (event_a_unit, CredentialHandles.charge example_credential_state 0) /\
  issue_local example_profile example_credential_policy example_credential
    (CredentialHandles.charge example_credential_state 0)
    (example_request false) context_a (example_challenge false 6) example_measured example_aliases = None.
Proof. repeat split; reflexivity. Qed.

Example the_broker_admits_its_request_bound_and_the_first_nonempty_nonce :
  local_request_matches example_profile context_a (example_challenge false 1)
    (CredentialHandles.mk_request 1 3 0 2 5 [0; 1; 2; 3]) = true /\
  local_request_matches example_profile context_a (example_challenge false 0)
    (example_request false) = false.
Proof. split; reflexivity. Qed.

Theorem ledger_authenticity_is_inhabited : forall ledger,
  EvidenceAuthenticity (ledger_authentic ledger) ledger True.
Proof.
  intros ledger _ q H. apply existsb_exists in H as [event [Hin Heq]].
  unfold evidence_equalb in Heq. destruct (evidence_eq_dec (issued_evidence event) q);
    [exists event; split; assumption|discriminate].
Qed.

Definition example_custody (ctx : ProtectedContext) : Prop :=
  ctx = context_a \/ ctx = context_b \/ ctx = context_a_concurrent.

Theorem example_exporters_bind_their_actual_key_holders : ExporterSecurity example_custody.
Proof.
  intros a b Ha Hb [Ha' | [Ha' | Ha']] [Hb' | [Hb' | Hb']] E; subst a; subst b;
    try discriminate E; unfold SameKeyHolder; repeat split; reflexivity.
Qed.

Theorem example_local_context_integrity :
  LocalContextIntegrity example_profile example_ledger example_measured example_aliases.
Proof.
  intros event H. cbn in H. destruct H as [H | [H | [H | [H | [H | []]]]]]; subst event;
    repeat split; reflexivity.
Qed.

Theorem example_unit_aliases_are_authenticated_and_distinct :
  AuthenticatedUnitPseudonyms example_aliases.
Proof.
  intros origin a b alias Ha Hb. unfold example_aliases in *.
  destruct (origin =? 4); [|discriminate]. inversion Ha. inversion Hb. lia.
Qed.

Theorem example_keys_are_uncompromised : forall ctx,
  example_custody ctx -> UncompromisedSessionKeys example_custody example_ledger ctx.
Proof.
  intros ctx H. split; [exact H|]. intros event Hin.
  cbn in Hin. destruct Hin as [Hin | [Hin | [Hin | [Hin | [Hin | []]]]]]; subst event;
    unfold example_custody; cbn; auto.
Qed.

Example software_and_unit_appraisals_both_accept :
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 6) 1 8 (Some (issued_evidence event_a))) = true /\
  snd (decide example_profile unit_specific_policy example_auth
       (waiting_for unit_specific_policy context_a 6) 1 8 (Some (issued_evidence event_a_unit))) = true.
Proof. split; reflexivity. Qed.

(* Correctly measured unit B is allowed by software policy on its OWN TLS
   session. B's quote is refused on A's session, and B's own session is also
   refused by a policy enrolled for A. These are distinct decisions. *)
Example another_approved_unit_does_not_substitute_for_an_existing_endpoint :
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_b 6) 1 8 (Some (issued_evidence event_b))) = true /\
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 6) 1 8 (Some (issued_evidence event_b))) = false /\
  snd (decide example_profile unit_specific_policy example_auth
       (waiting_for unit_specific_policy context_b 6) 1 8 (Some (issued_evidence event_b_unit))) = false.
Proof. repeat split; reflexivity. Qed.

Example replay_concurrency_expiry_and_oversize_are_refused :
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 8) 1 8 (Some (issued_evidence event_a))) = false /\
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 6) 1 8 (Some (issued_evidence event_concurrent))) = false /\
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 6) 10 8 (Some (issued_evidence event_a))) = false /\
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 6) 1 9 (Some (issued_evidence event_a))) = false.
Proof. repeat split; reflexivity. Qed.

Definition relayed_acceptance := fst (decide example_profile software_policy example_auth
  (waiting_for software_policy context_a 6) 1 8 (Some (forward_bytes [90; 91] (issued_evidence event_a)))).

Example forwarding_and_substituting_are_distinct :
  phase relayed_acceptance = Open /\ records_open relayed_acceptance [1] 90 = false /\
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 6) 1 8 (Some (issued_evidence event_b))) = false.
Proof. repeat split; reflexivity. Qed.

Example exposure_after_appraisal_grants_record_authority :
  records_open relayed_acceptance [1] 90 = false /\
  records_open relayed_acceptance [1; 90] 90 = true.
Proof. split; reflexivity. Qed.

Definition ExclusiveTrafficKeys (ctx : ProtectedContext) (holders : list nat) : Prop :=
  forall holder, In holder holders -> holder = context_unit ctx.

Theorem the_exposure_violates_exclusive_key_custody :
  ExclusiveTrafficKeys context_a [1] /\ ~ ExclusiveTrafficKeys context_a [1; 90].
Proof.
  split.
  - intros holder [H|[]]. subst. reflexivity.
  - intros H. specialize (H 90 (or_intror (or_introl eq_refl))). discriminate H.
Qed.

Example only_one_authenticated_bounded_fetch_is_served :
  snd (fetch_one example_profile relayed_acceptance 4 4 16 true true) = true /\
  snd (fetch_one example_profile relayed_acceptance 4 4 17 true true) = false /\
  snd (fetch_one example_profile relayed_acceptance 4 4 16 false true) = false /\
  snd (fetch_one example_profile
    (fst (fetch_one example_profile relayed_acceptance 4 4 16 true true)) 4 4 16 true true) = false.
Proof. repeat split; reflexivity. Qed.

Example fresh_contexts_cannot_reuse_challenges_or_reconstruct_the_old_lifecycle :
  phase (begin_appraisal example_profile software_policy
    (reconnect relayed_acceptance context_a_concurrent) 6 1 10) = Closed /\
  phase (reconnect relayed_acceptance context_a) = Closed /\
  phase (begin_appraisal example_profile software_policy
    (reconnect relayed_acceptance context_a_concurrent) 8 1 10) = Waiting.
Proof. repeat split; reflexivity. Qed.

Theorem reconnecting_preserves_all_spent_contexts : forall c new_context,
  used_contexts (reconnect c new_context) = used_contexts c.
Proof.
  intros. unfold reconnect. destruct ((context_id new_context =? context_id (protected_context c)) ||
    existsb (Nat.eqb (context_id new_context)) (used_contexts c)); reflexivity.
Qed.

Theorem any_previously_spent_context_is_refused : forall c new_context,
  In (context_id new_context) (used_contexts c) ->
  phase (reconnect c new_context) = Closed.
Proof.
  intros c ctx H. unfold reconnect.
  assert (E : existsb (Nat.eqb (context_id ctx)) (used_contexts c) = true).
  { apply existsb_exists. exists (context_id ctx). split; [exact H|apply Nat.eqb_refl]. }
  rewrite E, orb_true_r. reflexivity.
Qed.

Example a_context_cycle_cannot_reopen_the_first_tls_connection :
  phase (reconnect (reconnect relayed_acceptance context_b) context_a) = Closed /\
  phase (begin_appraisal example_profile software_policy
    (reconnect (reconnect relayed_acceptance context_b) context_a) 8 1 10) = Closed /\
  phase (begin_appraisal example_profile software_policy
    (reconnect (reconnect relayed_acceptance context_b) context_a_concurrent) 8 1 10) = Waiting.
Proof. repeat split; reflexivity. Qed.

Definition colliding_context := example_context 2 2 3 4 11.
Definition colliding_event := example_issuance colliding_context false 6.
Definition colliding_custody (ctx : ProtectedContext) : Prop := ctx = context_a \/ ctx = colliding_context.

Example an_exporter_collision_permits_endpoint_substitution :
  snd (decide example_profile software_policy (ledger_authentic [colliding_event])
    (waiting_for software_policy context_a 6) 1 8 (Some (issued_evidence colliding_event))) = true /\
  context_unit (issuer_context colliding_event) <> context_unit context_a.
Proof. split; [reflexivity|discriminate]. Qed.

Theorem the_collision_violates_exporter_security : ~ ExporterSecurity colliding_custody.
Proof.
  intros H. specialize (H context_a colliding_context eq_refl eq_refl
    (or_introl eq_refl) (or_intror eq_refl) eq_refl).
  destruct H as [H _]. discriminate H.
Qed.

(* A broken issuer taking a caller's exporter creates signed evidence from
   B that matches A's session. Such an event violates LocalContextIntegrity. *)
Definition caller_exporter_event : Issuance :=
  {| issued_evidence := issued_evidence event_a; issuer_context := context_b |}.

Example a_caller_supplied_exporter_would_accept_substitution :
  snd (decide example_profile software_policy (ledger_authentic [caller_exporter_event])
       (waiting_for software_policy context_a 6) 1 8
       (Some (issued_evidence caller_exporter_event))) = true /\
  context_unit (issuer_context caller_exporter_event) <> context_unit context_a.
Proof. split; [reflexivity|discriminate]. Qed.

Theorem the_caller_exporter_event_breaks_local_context_integrity :
  ~ LocalContextIntegrity example_profile [caller_exporter_event] example_measured example_aliases.
Proof.
  intros H. specialize (H caller_exporter_event (or_introl eq_refl)).
  destruct H as [_ [H _]]. discriminate H.
Qed.

(* A compromised evidence verifier accepts a quote for which no issuance
   exists. The exception does not enlarge the theorem's global axiom set. *)
Theorem an_accept_all_verifier_has_no_evidence_authenticity_on_an_empty_ledger :
  ~ EvidenceAuthenticity (fun _ => true) [] True.
Proof.
  intros H. destruct (H I (issued_evidence event_a) eq_refl) as [event [Hin _]]. exact Hin.
Qed.

Example compromised_evidence_authentication_would_open_without_an_issuer :
  snd (decide example_profile software_policy (fun _ => true)
    (waiting_for software_policy context_a 6) 1 8 (Some (issued_evidence event_a))) = true.
Proof. reflexivity. Qed.

Theorem software_policy_premises_have_a_complete_inhabitant :
  ExporterSecurity example_custody /\
  EvidenceAuthenticity example_auth example_ledger True /\ True /\
  LocalContextIntegrity example_profile example_ledger example_measured example_aliases /\
  UncompromisedSessionKeys example_custody example_ledger context_a /\
  AuthenticatedUnitPseudonyms example_aliases /\
  UnitEnrollment software_policy context_a example_aliases /\
  PendingBinding example_profile software_policy (waiting_for software_policy context_a 6) /\
  snd (decide example_profile software_policy example_auth
       (waiting_for software_policy context_a 6) 1 8 (Some (issued_evidence event_a))) = true.
Proof.
  split; [exact example_exporters_bind_their_actual_key_holders|].
  split; [apply ledger_authenticity_is_inhabited|]. split; [exact I|].
  split; [exact example_local_context_integrity|].
  split; [apply example_keys_are_uncompromised; left; reflexivity|].
  split; [exact example_unit_aliases_are_authenticated_and_distinct|].
  split; [intros H; discriminate H|]. split; [repeat split; cbn; lia|reflexivity].
Qed.

Theorem unit_policy_premises_have_a_complete_inhabitant :
  UnitEnrollment unit_specific_policy context_a example_aliases /\
  PendingBinding example_profile unit_specific_policy (waiting_for unit_specific_policy context_a 6) /\
  snd (decide example_profile unit_specific_policy example_auth
       (waiting_for unit_specific_policy context_a 6) 1 8 (Some (issued_evidence event_a_unit))) = true.
Proof. split; [intros _; reflexivity|]. split; [repeat split; cbn; lia|reflexivity]. Qed.

(* Apply the quantified theorem to the concrete models; record construction
   by itself is not evidence that all the theorem's premises coexist. *)
Theorem the_inhabited_software_policy_establishes_session_agreement :
  exists event, In event example_ledger /\ issued_evidence event = issued_evidence event_a /\
  SameKeyHolder (issuer_context event) context_a.
Proof.
  destruct software_policy_premises_have_a_complete_inhabitant
    as [Hex [Ha [Hs [Hl [Hk [Hu [He [Hp Haccept]]]]]]]].
  destruct (attested_session_binding example_profile software_policy example_auth example_ledger
    example_measured example_aliases example_custody True
    (waiting_for software_policy context_a 6) 1 8 (issued_evidence event_a)
    Hex Ha Hs Hl Hk Hu He Hp Haccept) as [event [Hin [Heq [Hholder _]]]].
  exists event. split; [exact Hin|]. split; [exact Heq|exact Hholder].
Qed.

Theorem the_inhabited_unit_policy_establishes_the_enrolled_unit :
  context_unit (protected_context (waiting_for unit_specific_policy context_a 6)) =
  expected_unit unit_specific_policy.
Proof.
  destruct software_policy_premises_have_a_complete_inhabitant
    as [Hex [Ha [Hs [Hl [Hk [Hu _]]]]]].
  destruct unit_policy_premises_have_a_complete_inhabitant as [He [Hp Haccept]].
  destruct (attested_session_binding example_profile unit_specific_policy example_auth example_ledger
    example_measured example_aliases example_custody True
    (waiting_for unit_specific_policy context_a 6) 1 8 (issued_evidence event_a_unit)
    Hex Ha Hs Hl Hk Hu He Hp Haccept)
    as [event [_ [_ [_ [_ [_ [_ [_ Hunit]]]]]]]].
  apply Hunit. reflexivity.
Qed.

Definition witness_ProtectedContext : ProtectedContext := context_a.
Definition witness_AttestationProfile : AttestationProfile := example_profile.
Definition witness_Challenge : Challenge := example_challenge false 6.
Definition witness_Evidence : Evidence := issued_evidence event_a.
Definition witness_Issuance : Issuance := event_a.
Definition witness_AppraisalPolicy : AppraisalPolicy := software_policy.
Definition witness_Connection : Connection := waiting_for software_policy context_a 6.

(* =========================================================================
   M6.9c-i Multi-Session Strand/Trace Extension

   Models interleaved multi-session handshakes, challenge issuances,
   broker-local quote issuances, single-attempt appraisals, session-key
   exposures, and broker compromises as finite ordered strand traces with
   StrandsRocq-style bundle-relative freshness (`bundle_fresh`).
   ========================================================================= *)

Inductive StrandEvent : Type :=
| EvHandshakeComplete : ProtectedContext -> StrandEvent
| EvChallengeIssued : Connection -> Challenge -> StrandEvent
| EvBrokerQuoteIssued : Issuance -> StrandEvent
| EvAppraisalAccepted : Connection -> AppraisalPolicy -> Evidence -> nat -> nat -> StrandEvent
| EvKeyExposed : ProtectedContext -> nat -> StrandEvent
| EvBrokerCompromised : nat -> StrandEvent.

Definition SessionTrace : Type := list StrandEvent.

Record MultiSessionEnv : Type := {
  ms_profile : AttestationProfile;
  ms_measured : Measurement;
  ms_aliases : UnitAliases;
  ms_auth : Evidence -> bool;
  ms_custody : ProtectedContext -> Prop
}.

Record ByteForwardingRelay : Type := {
  relay_hops : list nat;
  relay_source : ProtectedContext;
  relay_target : ProtectedContext;
  relay_evidence : Evidence;
  relay_same_holder : SameKeyHolder relay_source relay_target
}.

Fixpoint trace_issuances (tr : SessionTrace) : list Issuance :=
  match tr with
  | [] => []
  | EvBrokerQuoteIssued iss :: rest => iss :: trace_issuances rest
  | _ :: rest => trace_issuances rest
  end.

Lemma trace_issuances_in_tr : forall tr iss,
  In iss (trace_issuances tr) <-> In (EvBrokerQuoteIssued iss) tr.
Proof.
  induction tr as [|e rest IH]; intro iss; split; intro H.
  - destruct H.
  - destruct H.
  - destruct e; cbn in H; try (right; apply IH; exact H).
    destruct H as [Heq|Hin].
    + subst. left. reflexivity.
    + right. apply IH. exact Hin.
  - destruct H as [Heq|Hin].
    + subst. left. reflexivity.
    + destruct e; cbn; try (apply IH; exact Hin).
      right. apply IH. exact Hin.
Qed.

Definition trace_key_exposed (tr : SessionTrace) (ctx : ProtectedContext) : Prop :=
  exists sender, In (EvKeyExposed ctx sender) tr.

Definition trace_broker_compromised (tr : SessionTrace) (u : nat) : Prop :=
  In (EvBrokerCompromised u) tr.

Definition NoKeyExposure (tr : SessionTrace) : Prop :=
  forall ctx sender, ~ In (EvKeyExposed ctx sender) tr.

Definition NoBrokerCompromise (tr : SessionTrace) : Prop :=
  forall u, ~ In (EvBrokerCompromised u) tr.

(* StrandsRocq-style bundle-relative freshness: the challenge originates at a
   unique strand event index `i` in `tr` with positive nonce, distinct from
   every other challenge-issuance nonce and context identity in the bundle, and
   precedes every matching quote issuance and appraisal acceptance. *)
Definition bundle_fresh (tr : SessionTrace) (conn : Connection) (q : Challenge) : Prop :=
  0 < challenge_nonce q /\
  exists i : nat,
    nth_error tr i = Some (EvChallengeIssued conn q) /\
    (forall j conn' q',
      nth_error tr j = Some (EvChallengeIssued conn' q') ->
      challenge_nonce q' = challenge_nonce q ->
      j = i /\ conn' = conn /\ q' = q) /\
    (forall j conn' q',
      nth_error tr j = Some (EvChallengeIssued conn' q') ->
      context_id (protected_context conn') = context_id (protected_context conn) ->
      j = i /\ conn' = conn /\ q' = q) /\
    (forall k conn_a pol_a ev_a now_a sz_a,
      nth_error tr k = Some (EvAppraisalAccepted conn_a pol_a ev_a now_a sz_a) ->
      (evidence_challenge ev_a = q \/
       context_id (protected_context conn_a) = context_id (protected_context conn)) ->
      i < k) /\
    (forall m iss,
      nth_error tr m = Some (EvBrokerQuoteIssued iss) ->
      ~ trace_broker_compromised tr (context_unit (issuer_context iss)) ->
      evidence_challenge (issued_evidence iss) = q ->
      i < m).

Definition TraceSound (env : MultiSessionEnv) (tr : SessionTrace) : Prop :=
  (forall ctx, In (EvHandshakeComplete ctx) tr ->
    context_usable ctx = true /\ ms_custody env ctx) /\
  (forall conn q, In (EvChallengeIssued conn q) tr ->
    phase conn = Waiting /\ pending_challenge conn = q /\
    context_usable (protected_context conn) = true /\
    In (EvHandshakeComplete (protected_context conn)) tr) /\
  (forall iss, In (EvBrokerQuoteIssued iss) tr ->
    ~ trace_broker_compromised tr (context_unit (issuer_context iss)) ->
    LocalContextIntegrity (ms_profile env) [iss] (ms_measured env) (ms_aliases env) /\
    ms_custody env (issuer_context iss)) /\
  (forall conn policy ev now sz,
    In (EvAppraisalAccepted conn policy ev now sz) tr ->
    snd (decide (ms_profile env) policy (ms_auth env) conn now sz (Some ev)) = true /\
    PendingBinding (ms_profile env) policy conn /\
    In (EvHandshakeComplete (protected_context conn)) tr /\
    bundle_fresh tr conn (pending_challenge conn)) /\
  (forall k m conn policy ev now sz iss,
    nth_error tr k = Some (EvAppraisalAccepted conn policy ev now sz) ->
    nth_error tr m = Some (EvBrokerQuoteIssued iss) ->
    ~ trace_broker_compromised tr (context_unit (issuer_context iss)) ->
    issued_evidence iss = ev ->
    m < k).

Lemma trace_sound_local_integrity : forall env tr,
  TraceSound env tr -> NoBrokerCompromise tr ->
  LocalContextIntegrity (ms_profile env) (trace_issuances tr) (ms_measured env) (ms_aliases env) /\
  (forall iss, In iss (trace_issuances tr) -> ms_custody env (issuer_context iss)).
Proof.
  intros env tr [_ [_ [Hquotes _]]] Hnobrk.
  split.
  - intros iss Hin. apply trace_issuances_in_tr in Hin.
    destruct (Hquotes iss Hin (Hnobrk (context_unit (issuer_context iss)))) as [Hloc _].
    apply Hloc. left. reflexivity.
  - intros iss Hin. apply trace_issuances_in_tr in Hin.
    destruct (Hquotes iss Hin (Hnobrk (context_unit (issuer_context iss)))) as [_ Hcust].
    exact Hcust.
Qed.

Lemma in_nth_error_witness : forall (A : Type) (xs : list A) (x : A),
  In x xs -> exists idx, nth_error xs idx = Some x.
Proof.
  intros A xs x Hin. apply In_nth_error in Hin. exact Hin.
Qed.

(*| discharges: R-12-015c, R-09-025a |*)
Theorem multi_session_software_agreement :
  forall env tr conn policy ev now sz,
  TraceSound env tr ->
  NoKeyExposure tr ->
  NoBrokerCompromise tr ->
  ExporterSecurity (ms_custody env) ->
  EvidenceAuthenticity (ms_auth env) (trace_issuances tr) (NoBrokerCompromise tr) ->
  AuthenticatedUnitPseudonyms (ms_aliases env) ->
  UnitEnrollment policy (protected_context conn) (ms_aliases env) ->
  unit_policy policy = false ->
  In (EvAppraisalAccepted conn policy ev now sz) tr ->
  exists iss i_ch i_q i_app,
    i_ch < i_q /\ i_q < i_app /\
    nth_error tr i_ch = Some (EvChallengeIssued conn (pending_challenge conn)) /\
    nth_error tr i_q = Some (EvBrokerQuoteIssued iss) /\
    nth_error tr i_app = Some (EvAppraisalAccepted conn policy ev now sz) /\
    issued_evidence iss = ev /\
    SameKeyHolder (issuer_context iss) (protected_context conn) /\
    ms_measured env (context_unit (protected_context conn)) = Some (evidence_generation ev) /\
    approved_generation policy (evidence_generation ev) = true /\
    context_principal (protected_context conn) = required_principal policy /\
    evidence_challenge ev = pending_challenge conn.
Proof.
  intros env tr conn policy ev now sz Hsound _ Hnobrk Hex Hauth Halias Henroll Hsw Hacc.
  pose proof Hsound as [Hh [Hch [Hquotes [Happs Hcausal]]]].
  destruct (Happs conn policy ev now sz Hacc) as [Hdec [Hpend [Hhs Hfresh]]].
  destruct (Hh (protected_context conn) Hhs) as [_ Htarget_cust].
  destruct (trace_sound_local_integrity env tr Hsound Hnobrk) as [Hlocal Hiss_cust].
  assert (Hkeys : UncompromisedSessionKeys (ms_custody env) (trace_issuances tr) (protected_context conn)).
  { split; [exact Htarget_cust|exact Hiss_cust]. }
  destruct (attested_session_binding (ms_profile env) policy (ms_auth env)
    (trace_issuances tr) (ms_measured env) (ms_aliases env) (ms_custody env)
    (NoBrokerCompromise tr) conn now sz ev
    Hex Hauth Hnobrk Hlocal Hkeys Halias Henroll Hpend Hdec)
    as [iss [Hin_iss [Hev [Hholder [Hmeas [Hgen [Hprin [Hchal _]]]]]]]].
  apply trace_issuances_in_tr in Hin_iss.
  destruct (in_nth_error_witness _ _ _ Hin_iss) as [i_q Hq].
  destruct (in_nth_error_witness _ _ _ Hacc) as [i_app Happ].
  destruct Hfresh as [_ [i_ch [Hch_nth [_ [_ [_ Hq_after]]]]]].
  assert (Hlt_ch_q : i_ch < i_q).
  { apply (Hq_after i_q iss Hq (Hnobrk (context_unit (issuer_context iss)))).
    rewrite Hev. exact Hchal. }
  assert (Hlt_q_app : i_q < i_app).
  { apply (Hcausal i_app i_q conn policy ev now sz iss Happ Hq
             (Hnobrk (context_unit (issuer_context iss))) Hev). }
  exists iss, i_ch, i_q, i_app.
  split; [exact Hlt_ch_q|]. split; [exact Hlt_q_app|].
  split; [exact Hch_nth|]. split; [exact Hq|].
  split; [exact Happ|]. split; [exact Hev|].
  split; [exact Hholder|]. split; [exact Hmeas|].
  split; [exact Hgen|]. split; [exact Hprin|exact Hchal].
Qed.

(*| discharges: R-12-015c, R-09-025a |*)
Theorem multi_session_unit_agreement :
  forall env tr conn policy ev now sz,
  TraceSound env tr ->
  NoKeyExposure tr ->
  NoBrokerCompromise tr ->
  ExporterSecurity (ms_custody env) ->
  EvidenceAuthenticity (ms_auth env) (trace_issuances tr) (NoBrokerCompromise tr) ->
  AuthenticatedUnitPseudonyms (ms_aliases env) ->
  UnitEnrollment policy (protected_context conn) (ms_aliases env) ->
  unit_policy policy = true ->
  In (EvAppraisalAccepted conn policy ev now sz) tr ->
  exists iss i_ch i_q i_app,
    i_ch < i_q /\ i_q < i_app /\
    nth_error tr i_ch = Some (EvChallengeIssued conn (pending_challenge conn)) /\
    nth_error tr i_q = Some (EvBrokerQuoteIssued iss) /\
    nth_error tr i_app = Some (EvAppraisalAccepted conn policy ev now sz) /\
    issued_evidence iss = ev /\
    SameKeyHolder (issuer_context iss) (protected_context conn) /\
    ms_measured env (context_unit (protected_context conn)) = Some (evidence_generation ev) /\
    approved_generation policy (evidence_generation ev) = true /\
    context_principal (protected_context conn) = required_principal policy /\
    evidence_challenge ev = pending_challenge conn /\
    context_unit (protected_context conn) = expected_unit policy /\
    evidence_alias ev = Some (expected_alias policy).
Proof.
  intros env tr conn policy ev now sz Hsound _ Hnobrk Hex Hauth Halias Henroll Hunit Hacc.
  pose proof Hsound as [Hh [Hch [Hquotes [Happs Hcausal]]]].
  destruct (Happs conn policy ev now sz Hacc) as [Hdec [Hpend [Hhs Hfresh]]].
  destruct (Hh (protected_context conn) Hhs) as [_ Htarget_cust].
  destruct (trace_sound_local_integrity env tr Hsound Hnobrk) as [Hlocal Hiss_cust].
  assert (Hkeys : UncompromisedSessionKeys (ms_custody env) (trace_issuances tr) (protected_context conn)).
  { split; [exact Htarget_cust|exact Hiss_cust]. }
  destruct (attested_session_binding (ms_profile env) policy (ms_auth env)
    (trace_issuances tr) (ms_measured env) (ms_aliases env) (ms_custody env)
    (NoBrokerCompromise tr) conn now sz ev
    Hex Hauth Hnobrk Hlocal Hkeys Halias Henroll Hpend Hdec)
    as [iss [Hin_iss [Hev [Hholder [Hmeas [Hgen [Hprin [Hchal Hunit_eq]]]]]]]].
  destruct (accepted_checks (ms_profile env) policy (ms_auth env) conn now sz ev Hdec)
    as [_ [_ [_ [_ [_ [_ Halias_eq]]]]]].
  unfold policy_alias in Halias_eq. rewrite Hunit in Halias_eq.
  apply trace_issuances_in_tr in Hin_iss.
  destruct (in_nth_error_witness _ _ _ Hin_iss) as [i_q Hq].
  destruct (in_nth_error_witness _ _ _ Hacc) as [i_app Happ].
  destruct Hfresh as [_ [i_ch [Hch_nth [_ [_ [_ Hq_after]]]]]].
  assert (Hlt_ch_q : i_ch < i_q).
  { apply (Hq_after i_q iss Hq (Hnobrk (context_unit (issuer_context iss)))).
    rewrite Hev. exact Hchal. }
  assert (Hlt_q_app : i_q < i_app).
  { apply (Hcausal i_app i_q conn policy ev now sz iss Happ Hq
             (Hnobrk (context_unit (issuer_context iss))) Hev). }
  exists iss, i_ch, i_q, i_app.
  split; [exact Hlt_ch_q|]. split; [exact Hlt_q_app|].
  split; [exact Hch_nth|]. split; [exact Hq|].
  split; [exact Happ|]. split; [exact Hev|].
  split; [exact Hholder|]. split; [exact Hmeas|].
  split; [exact Hgen|]. split; [exact Hprin|].
  split; [exact Hchal|]. split; [apply Hunit_eq; exact Hunit|exact Halias_eq].
Qed.

(* Byte-forwarding relay vs. parallel-session and foreign-unit substitution. *)
(*| discharges: R-12-015c, R-09-025a |*)
Theorem byte_forwarding_relay_satisfies_endpoint_agreement :
  forall env tr conn policy hops ev now sz,
  TraceSound env tr ->
  NoKeyExposure tr ->
  NoBrokerCompromise tr ->
  ExporterSecurity (ms_custody env) ->
  EvidenceAuthenticity (ms_auth env) (trace_issuances tr) (NoBrokerCompromise tr) ->
  AuthenticatedUnitPseudonyms (ms_aliases env) ->
  UnitEnrollment policy (protected_context conn) (ms_aliases env) ->
  In (EvAppraisalAccepted conn policy (forward_bytes hops ev) now sz) tr ->
  exists iss (relay : ByteForwardingRelay),
    In (EvBrokerQuoteIssued iss) tr /\
    relay_hops relay = hops /\
    relay_source relay = issuer_context iss /\
    relay_target relay = protected_context conn /\
    relay_evidence relay = ev /\
    ms_measured env (context_unit (protected_context conn)) = Some (evidence_generation ev) /\
    approved_generation policy (evidence_generation ev) = true /\
    evidence_challenge ev = pending_challenge conn /\
    (unit_policy policy = true -> context_unit (protected_context conn) = expected_unit policy) /\
    (forall h, In h hops -> h <> context_unit (protected_context conn) ->
      records_open (fst (decide (ms_profile env) policy (ms_auth env) conn now sz
                                (Some (forward_bytes hops ev))))
                   [context_unit (protected_context conn)] h = false).
Proof.
  intros env tr conn policy hops ev now sz Hsound _ Hnobrk Hex Hauth Halias Henroll Hacc.
  pose proof Hsound as [Hh [_ [_ [Happs _]]]].
  destruct (Happs conn policy (forward_bytes hops ev) now sz Hacc) as [Hdec [Hpend [Hhs _]]].
  destruct (Hh (protected_context conn) Hhs) as [_ Htarget_cust].
  destruct (trace_sound_local_integrity env tr Hsound Hnobrk) as [Hlocal Hiss_cust].
  assert (Hkeys : UncompromisedSessionKeys (ms_custody env) (trace_issuances tr) (protected_context conn)).
  { split; [exact Htarget_cust|exact Hiss_cust]. }
  unfold forward_bytes in *.
  destruct (attested_session_binding (ms_profile env) policy (ms_auth env)
    (trace_issuances tr) (ms_measured env) (ms_aliases env) (ms_custody env)
    (NoBrokerCompromise tr) conn now sz ev
    Hex Hauth Hnobrk Hlocal Hkeys Halias Henroll Hpend Hdec)
    as [iss [Hin_iss [Hev [Hholder [Hmeas [Hgen [_ [Hchal Hunit_eq]]]]]]]].
  apply trace_issuances_in_tr in Hin_iss.
  exists iss, {| relay_hops := hops;
                 relay_source := issuer_context iss;
                 relay_target := protected_context conn;
                 relay_evidence := ev;
                 relay_same_holder := Hholder |}.
  repeat split; try assumption; try reflexivity.
  intros h _ Hneq.
  apply forwarding_does_not_grant_record_authority.
  intros [Hin|[]]. apply Hneq. symmetry. exact Hin.
Qed.

(*| discharges: R-12-015c |*)
Theorem parallel_session_substitution_is_refused :
  forall env tr conn1 conn2 iss2 policy now sz,
  TraceSound env tr ->
  NoBrokerCompromise tr ->
  In (EvBrokerQuoteIssued iss2) tr ->
  context_id (protected_context conn1) <> context_id (protected_context conn2) ->
  issuer_context iss2 = protected_context conn2 ->
  (context_exporter (protected_context conn1) <> context_exporter (protected_context conn2) \/
   evidence_challenge (issued_evidence iss2) <> pending_challenge conn1) ->
  snd (decide (ms_profile env) policy (ms_auth env) conn1 now sz
               (Some (issued_evidence iss2))) = false.
Proof.
  intros env tr conn1 conn2 iss2 policy now sz [_ [_ [Hquotes _]]] Hnobrk Hin2 _ Hctx2 Hsep.
  destruct (Hquotes iss2 Hin2 (Hnobrk (context_unit (issuer_context iss2)))) as [Hloc _].
  specialize (Hloc iss2 (or_introl eq_refl)).
  cbn in Hloc. destruct Hloc as [_ [Hex_eq _]].
  destruct Hsep as [Hexp_neq | Hchal_neq].
  - destruct (snd (decide (ms_profile env) policy (ms_auth env) conn1 now sz
                     (Some (issued_evidence iss2)))) eqn:E; [|reflexivity].
    destruct (accepted_checks (ms_profile env) policy (ms_auth env) conn1 now sz
                (issued_evidence iss2) E) as [_ [_ [_ [Hacc_exp _]]]].
    exfalso. apply Hexp_neq. rewrite <- Hctx2, <- Hex_eq, <- Hacc_exp. reflexivity.
  - apply replay_with_a_different_challenge_is_refused. exact Hchal_neq.
Qed.

(*| discharges: R-09-025a, R-12-015c |*)
Theorem foreign_correctly_measured_unit_substitution_is_refused :
  forall env tr policy target_ctx conn_foreign iss_foreign now sz gen,
  TraceSound env tr ->
  NoBrokerCompromise tr ->
  unit_policy policy = true ->
  AuthenticatedUnitPseudonyms (ms_aliases env) ->
  UnitEnrollment policy target_ctx (ms_aliases env) ->
  context_origin (protected_context conn_foreign) = context_origin target_ctx ->
  context_unit (protected_context conn_foreign) <> expected_unit policy ->
  ms_measured env (context_unit (protected_context conn_foreign)) = Some gen ->
  approved_generation policy gen = true ->
  In (EvBrokerQuoteIssued iss_foreign) tr ->
  SameKeyHolder (issuer_context iss_foreign) (protected_context conn_foreign) ->
  PendingBinding (ms_profile env) policy conn_foreign ->
  snd (decide (ms_profile env) policy (ms_auth env) conn_foreign now sz
               (Some (issued_evidence iss_foreign))) = false.
Proof.
  intros env tr policy target_ctx conn_foreign iss_foreign now sz gen
    [_ [_ [Hquotes _]]] Hnobrk Hunit Halias Henroll Horig Hneq_unit _ _ Hin_iss Hholder Hpend.
  destruct (Hquotes iss_foreign Hin_iss
              (Hnobrk (context_unit (issuer_context iss_foreign)))) as [Hloc _].
  specialize (Hloc iss_foreign (or_introl eq_refl)).
  cbn in Hloc. destruct Hloc as [_ [_ [_ [_ [_ [_ Halias_iss]]]]]].
  destruct (snd (decide (ms_profile env) policy (ms_auth env) conn_foreign now sz
                   (Some (issued_evidence iss_foreign)))) eqn:E; [|reflexivity].
  destruct (accepted_checks (ms_profile env) policy (ms_auth env) conn_foreign now sz
              (issued_evidence iss_foreign) E)
    as [_ [_ [Hchal [_ [_ [_ Halias_acc]]]]]].
  unfold policy_alias in Halias_acc. rewrite Hunit in Halias_acc.
  destruct Hpend as [_ [Hscope _]].
  rewrite Hchal, Hscope, Hunit in Halias_iss.
  destruct Hholder as [_ [Hu [_ Ho]]].
  specialize (Henroll Hunit).
  assert (Hsame_u : context_unit (protected_context conn_foreign) = expected_unit policy).
  { apply (Halias (context_origin target_ctx)
             (context_unit (protected_context conn_foreign))
             (expected_unit policy) (expected_alias policy)).
    - rewrite <- Hu, <- Horig, <- Ho, <- Halias_iss. exact Halias_acc.
    - exact Henroll. }
  contradiction.
Qed.

(*| discharges: R-12-015c |*)
Theorem cross_session_replay_is_refused :
  forall env tr conn1 conn2 q1 q2 policy ev1 now sz,
  bundle_fresh tr conn1 q1 ->
  bundle_fresh tr conn2 q2 ->
  context_id (protected_context conn1) <> context_id (protected_context conn2) ->
  pending_challenge conn2 = q2 ->
  evidence_challenge ev1 = q1 ->
  snd (decide (ms_profile env) policy (ms_auth env) conn2 now sz (Some ev1)) = false.
Proof.
  intros env tr conn1 conn2 q1 q2 policy ev1 now sz
    [_ [i1 [Hnth1 [Hnonce_uniq _]]]] [_ [i2 [Hnth2 _]]] Hneq_ctx Hp2 Hev1.
  apply replay_with_a_different_challenge_is_refused.
  rewrite Hp2, Hev1. intro Heq.
  assert (Hsame_nonce : challenge_nonce q2 = challenge_nonce q1) by (rewrite Heq; reflexivity).
  destruct (Hnonce_uniq i2 conn2 q2 Hnth2 Hsame_nonce) as [_ [Hconn_eq _]].
  apply Hneq_ctx. rewrite Hconn_eq. reflexivity.
Qed.

(* =========================================================================
   Complete Adversary Compromise Matrix (Inhabited Multi-Session Traces)
   ========================================================================= *)

Definition conn_a_sw : Connection := waiting_for software_policy context_a 6.
Definition conn_b_sw : Connection := waiting_for software_policy context_b 7.
Definition conn_a_unit : Connection := waiting_for unit_specific_policy context_a 8.
Definition conn_b_unit : Connection := waiting_for unit_specific_policy context_b 9.

Definition event_b_sw_7 : Issuance := example_issuance context_b false 7.
Definition event_a_unit_8 : Issuance := example_issuance context_a true 8.
Definition event_b_unit_9 : Issuance := example_issuance context_b true 9.

Definition ms_multi_ledger : list Issuance :=
  [event_a; event_b_sw_7; event_a_unit_8; event_b_unit_9].

(* 1. Honest multi-session trace exercising both software-only (context_a and
   correctly measured foreign unit context_b on its own session) and unit-
   specific (context_a) appraisals with bundle-relative freshness. *)
Definition honest_multi_session_trace : SessionTrace := [
  EvHandshakeComplete context_a;
  EvHandshakeComplete context_b;
  EvChallengeIssued conn_a_sw (example_challenge false 6);
  EvChallengeIssued conn_b_sw (example_challenge false 7);
  EvBrokerQuoteIssued event_a;
  EvBrokerQuoteIssued event_b_sw_7;
  EvAppraisalAccepted conn_a_sw software_policy (issued_evidence event_a) 1 8;
  EvAppraisalAccepted conn_b_sw software_policy (issued_evidence event_b_sw_7) 1 8
].

Definition honest_unit_multi_session_trace : SessionTrace := [
  EvHandshakeComplete context_a;
  EvHandshakeComplete context_b;
  EvChallengeIssued conn_a_unit (example_challenge true 8);
  EvBrokerQuoteIssued event_a_unit_8;
  EvAppraisalAccepted conn_a_unit unit_specific_policy (issued_evidence event_a_unit_8) 1 8
].

Lemma honest_trace_bundle_fresh_a :
  bundle_fresh honest_multi_session_trace conn_a_sw (example_challenge false 6).
Proof.
  split; [cbn; lia|].
  exists 2. split; [reflexivity|].
  split.
  - intros j conn' q' Hj Hn.
    do 8 (destruct j as [|j]; [cbn in Hj; try discriminate; inversion Hj; subst;
      cbn in Hn; try discriminate; repeat split; reflexivity|]).
    cbn in Hj. destruct j; discriminate.
  - split.
    + intros j conn' q' Hj Hc.
      do 8 (destruct j as [|j]; [cbn in Hj; try discriminate; inversion Hj; subst;
        cbn in Hc; try discriminate; repeat split; reflexivity|]).
      cbn in Hj. destruct j; discriminate.
    + split.
      * intros k ca pa ea na sa Hk Hor.
        do 8 (destruct k as [|k]; [cbn in Hk; try discriminate; inversion Hk; subst;
          try lia; destruct Hor as [Hc|Hc]; cbn in Hc; discriminate|]).
        cbn in Hk. destruct k; discriminate.
      * intros m iss Hm _ Hc.
        do 8 (destruct m as [|m]; [cbn in Hm; try discriminate; inversion Hm; subst;
          try lia; cbn in Hc; discriminate|]).
        cbn in Hm. destruct m; discriminate.
Qed.

Lemma honest_trace_bundle_fresh_b :
  bundle_fresh honest_multi_session_trace conn_b_sw (example_challenge false 7).
Proof.
  split; [cbn; lia|].
  exists 3. split; [reflexivity|].
  split.
  - intros j conn' q' Hj Hn.
    do 8 (destruct j as [|j]; [cbn in Hj; try discriminate; inversion Hj; subst;
      cbn in Hn; try discriminate; repeat split; reflexivity|]).
    cbn in Hj. destruct j; discriminate.
  - split.
    + intros j conn' q' Hj Hc.
      do 8 (destruct j as [|j]; [cbn in Hj; try discriminate; inversion Hj; subst;
        cbn in Hc; try discriminate; repeat split; reflexivity|]).
      cbn in Hj. destruct j; discriminate.
    + split.
      * intros k ca pa ea na sa Hk Hor.
        do 8 (destruct k as [|k]; [cbn in Hk; try discriminate; inversion Hk; subst;
          try lia; destruct Hor as [Hc|Hc]; cbn in Hc; discriminate|]).
        cbn in Hk. destruct k; discriminate.
      * intros m iss Hm _ Hc.
        do 8 (destruct m as [|m]; [cbn in Hm; try discriminate; inversion Hm; subst;
          try lia; cbn in Hc; discriminate|]).
        cbn in Hm. destruct m; discriminate.
Qed.

Lemma honest_unit_trace_bundle_fresh_a :
  bundle_fresh honest_unit_multi_session_trace conn_a_unit (example_challenge true 8).
Proof.
  split; [cbn; lia|].
  exists 2. split; [reflexivity|].
  split.
  - intros j conn' q' Hj Hn.
    do 5 (destruct j as [|j]; [cbn in Hj; try discriminate; inversion Hj; subst;
      cbn in Hn; try discriminate; repeat split; reflexivity|]).
    cbn in Hj. destruct j; discriminate.
  - split.
    + intros j conn' q' Hj Hc.
      do 5 (destruct j as [|j]; [cbn in Hj; try discriminate; inversion Hj; subst;
        cbn in Hc; try discriminate; repeat split; reflexivity|]).
      cbn in Hj. destruct j; discriminate.
    + split.
      * intros k ca pa ea na sa Hk _.
        do 5 (destruct k as [|k]; [cbn in Hk; try discriminate; inversion Hk; subst; lia|]).
        cbn in Hk. destruct k; discriminate.
      * intros m iss Hm _ _.
        do 5 (destruct m as [|m]; [cbn in Hm; try discriminate; inversion Hm; subst; lia|]).
        cbn in Hm. destruct m; discriminate.
Qed.

Definition env_honest_sw : MultiSessionEnv := {|
  ms_profile := example_profile;
  ms_measured := example_measured;
  ms_aliases := example_aliases;
  ms_auth := ledger_authentic (trace_issuances honest_multi_session_trace);
  ms_custody := example_custody
|}.

Definition env_honest_unit : MultiSessionEnv := {|
  ms_profile := example_profile;
  ms_measured := example_measured;
  ms_aliases := example_aliases;
  ms_auth := ledger_authentic (trace_issuances honest_unit_multi_session_trace);
  ms_custody := example_custody
|}.

Theorem honest_split_traces_are_sound :
  TraceSound env_honest_sw honest_multi_session_trace /\
  TraceSound env_honest_unit honest_unit_multi_session_trace /\
  NoKeyExposure honest_multi_session_trace /\
  NoBrokerCompromise honest_multi_session_trace /\
  NoKeyExposure honest_unit_multi_session_trace /\
  NoBrokerCompromise honest_unit_multi_session_trace.
Proof.
  unfold TraceSound; repeat match goal with |- _ /\ _ => split end.
  - intros ctx H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; try discriminate;
      inversion H; subst; (split; [reflexivity|cbn; unfold example_custody; auto]).
  - intros conn q H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; try discriminate;
      inversion H; subst; repeat split; try reflexivity; cbn; auto.
  - intros iss H _. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; try discriminate;
      inversion H; subst;
      (split; [intros e [He|[]]; subst; repeat split; reflexivity|cbn; unfold example_custody; auto]).
  - intros conn pol ev now sz H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; try discriminate;
      inversion H; subst.
    + split; [reflexivity|]. split; [repeat split; cbn; lia|].
      split; [cbn; auto|exact honest_trace_bundle_fresh_a].
    + split; [reflexivity|]. split; [repeat split; cbn; lia|].
      split; [cbn; auto|exact honest_trace_bundle_fresh_b].
  - intros k m conn pol ev now sz iss Hk Hm _ Hev.
    do 8 (destruct k as [|k]; [cbn in Hk; try discriminate; inversion Hk; subst;
      do 8 (destruct m as [|m]; [cbn in Hm; try discriminate; inversion Hm; subst;
        try lia; cbn in Hev; discriminate|]);
      cbn in Hm; destruct m; discriminate|]).
    cbn in Hk. destruct k; discriminate.
  - intros ctx H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[]]]]]]; try discriminate;
      inversion H; subst; (split; [reflexivity|cbn; unfold example_custody; auto]).
  - intros conn q H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[]]]]]]; try discriminate;
      inversion H; subst; repeat split; try reflexivity; cbn; auto.
  - intros iss H _. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[]]]]]]; try discriminate;
      inversion H; subst;
      (split; [intros e [He|[]]; subst; repeat split; reflexivity|cbn; unfold example_custody; auto]).
  - intros conn pol ev now sz H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[]]]]]]; try discriminate;
      inversion H; subst.
    split; [reflexivity|]. split; [repeat split; cbn; lia|].
    split; [cbn; auto|exact honest_unit_trace_bundle_fresh_a].
  - intros k m conn pol ev now sz iss Hk Hm _ Hev.
    do 5 (destruct k as [|k]; [cbn in Hk; try discriminate; inversion Hk; subst;
      do 5 (destruct m as [|m]; [cbn in Hm; try discriminate; inversion Hm; subst;
        try lia; cbn in Hev; discriminate|]);
      cbn in Hm; destruct m; discriminate|]).
    cbn in Hk. destruct k; discriminate.
  - intros ctx sender H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; discriminate.
  - intros u H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[H|[H|[H|[]]]]]]]]]; discriminate.
  - intros ctx sender H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[]]]]]]; discriminate.
  - intros u H. cbn in H.
    destruct H as [H|[H|[H|[H|[H|[]]]]]]; discriminate.
Qed.

Theorem honest_multi_session_matrix_cell :
  (exists iss i_ch i_q i_app,
    i_ch < i_q /\ i_q < i_app /\
    issued_evidence iss = issued_evidence event_a /\
    SameKeyHolder (issuer_context iss) context_a) /\
  (exists iss i_ch i_q i_app,
    i_ch < i_q /\ i_q < i_app /\
    issued_evidence iss = issued_evidence event_a_unit_8 /\
    SameKeyHolder (issuer_context iss) context_a /\
    context_unit (protected_context conn_a_unit) = expected_unit unit_specific_policy).
Proof.
  destruct honest_split_traces_are_sound
    as [Hs1 [Hs2 [Hnk1 [Hnb1 [Hnk2 Hnb2]]]]].
  split.
  - destruct (multi_session_software_agreement env_honest_sw honest_multi_session_trace
      conn_a_sw software_policy (issued_evidence event_a) 1 8
      Hs1 Hnk1 Hnb1 example_exporters_bind_their_actual_key_holders
      (fun _ => ledger_authenticity_is_inhabited _ I)
      example_unit_aliases_are_authenticated_and_distinct
      (fun H => False_rect _ (Bool.diff_false_true H)) eq_refl)
      as [iss [i_ch [i_q [i_app [H1 [H2 [_ [_ [_ [Hev [Hholder _]]]]]]]]]]].
    + cbn. right. right. right. right. right. right. left. reflexivity.
    + exists iss, i_ch, i_q, i_app.
      split; [exact H1|]. split; [exact H2|]. split; [exact Hev|exact Hholder].
  - destruct (multi_session_unit_agreement env_honest_unit honest_unit_multi_session_trace
      conn_a_unit unit_specific_policy (issued_evidence event_a_unit_8) 1 8
      Hs2 Hnk2 Hnb2 example_exporters_bind_their_actual_key_holders
      (fun _ => ledger_authenticity_is_inhabited _ I)
      example_unit_aliases_are_authenticated_and_distinct
      (fun _ => eq_refl) eq_refl)
      as [iss [i_ch [i_q [i_app [H1 [H2 [_ [_ [_ [Hev [Hholder [_ [_ [_ [_ [Hu _]]]]]]]]]]]]]]]].
    + cbn. right. right. right. right. left. reflexivity.
    + exists iss, i_ch, i_q, i_app.
      split; [exact H1|]. split; [exact H2|]. split; [exact Hev|].
      split; [exact Hholder|exact Hu].
Qed.

(* 2. Session-key compromise matrix cell: exposing context_a's key to peer 90
   falsifies NoKeyExposure, breaks ExclusiveTrafficKeys, and lets peer 90 send
   authenticated records on the opened session. *)
Definition key_compromise_trace : SessionTrace :=
  honest_multi_session_trace ++ [EvKeyExposed context_a 90].

Theorem session_key_compromise_matrix_cell :
  ~ NoKeyExposure key_compromise_trace /\
  trace_key_exposed key_compromise_trace context_a /\
  ~ ExclusiveTrafficKeys context_a [1; 90] /\
  records_open (fst (decide example_profile software_policy
                       (ledger_authentic (trace_issuances key_compromise_trace))
                       conn_a_sw 1 8 (Some (issued_evidence event_a))))
               [1; 90] 90 = true.
Proof.
  split.
  - intro H. apply (H context_a 90). unfold key_compromise_trace.
    apply in_or_app. right. left. reflexivity.
  - split.
    + exists 90. unfold key_compromise_trace. apply in_or_app. right. left. reflexivity.
    + split.
      * apply the_exposure_violates_exclusive_key_custody.
      * reflexivity.
Qed.

(* 3. Broker compromise matrix cell: compromising unit 2's broker allows a
   forged caller-exporter issuance (context_b claiming context_a's exporter),
   falsifying NoBrokerCompromise and LocalContextIntegrity while still passing
   decide on context_a's session. *)
Definition broker_compromise_trace : SessionTrace := [
  EvHandshakeComplete context_a;
  EvBrokerCompromised 2;
  EvChallengeIssued conn_a_sw (example_challenge false 6);
  EvBrokerQuoteIssued caller_exporter_event;
  EvAppraisalAccepted conn_a_sw software_policy (issued_evidence caller_exporter_event) 1 8
].

Theorem broker_compromise_matrix_cell :
  ~ NoBrokerCompromise broker_compromise_trace /\
  trace_broker_compromised broker_compromise_trace 2 /\
  ~ LocalContextIntegrity example_profile (trace_issuances broker_compromise_trace)
      example_measured example_aliases /\
  snd (decide example_profile software_policy
         (ledger_authentic (trace_issuances broker_compromise_trace))
         conn_a_sw 1 8 (Some (issued_evidence caller_exporter_event))) = true /\
  context_unit (issuer_context caller_exporter_event) <> context_unit context_a.
Proof.
  split; [intro H; apply (H 2); cbn; auto|].
  split; [cbn; auto|].
  split; [exact the_caller_exporter_event_breaks_local_context_integrity|].
  split; [reflexivity|discriminate].
Qed.

(* 4. Cross-session replay matrix cell: replaying event_a (nonce 6) onto
   conn_b_sw (nonce 7) or reusing context_a across reconnect fails. *)
Theorem cross_session_replay_matrix_cell :
  snd (decide example_profile software_policy
         (ledger_authentic (trace_issuances honest_multi_session_trace))
         conn_b_sw 1 8 (Some (issued_evidence event_a))) = false /\
  phase (reconnect (fst (decide example_profile software_policy
                           (ledger_authentic (trace_issuances honest_multi_session_trace))
                           conn_a_sw 1 8 (Some (issued_evidence event_a))))
                   context_a) = Closed.
Proof.
  split.
  - eapply (cross_session_replay_is_refused env_honest_sw).
    + exact honest_trace_bundle_fresh_a.
    + exact honest_trace_bundle_fresh_b.
    + discriminate.
    + reflexivity.
    + reflexivity.
  - reflexivity.
Qed.

(* 5. Foreign correctly measured unit substitution matrix cell: unit 2
   (context_b) has approved generation 7, succeeds under software_policy on
   its own session conn_b_sw, and is refused both on context_a's session and
   on its own session conn_b_unit under unit_specific_policy. *)
Definition foreign_unit_trace : SessionTrace := [
  EvHandshakeComplete context_a;
  EvHandshakeComplete context_b;
  EvChallengeIssued conn_a_unit (example_challenge true 8);
  EvChallengeIssued conn_b_unit (example_challenge true 9);
  EvBrokerQuoteIssued event_b_unit_9
].

Theorem foreign_unit_substitution_matrix_cell :
  example_measured (context_unit context_b) = Some 7 /\
  snd (decide example_profile software_policy
         (ledger_authentic (trace_issuances honest_multi_session_trace))
         conn_b_sw 1 8 (Some (issued_evidence event_b_sw_7))) = true /\
  snd (decide example_profile unit_specific_policy
         (ledger_authentic (trace_issuances foreign_unit_trace))
         conn_b_unit 1 8 (Some (issued_evidence event_b_unit_9))) = false /\
  snd (decide example_profile unit_specific_policy
         (ledger_authentic (trace_issuances foreign_unit_trace))
         conn_a_unit 1 8 (Some (issued_evidence event_b_unit_9))) = false.
Proof.
  repeat split; reflexivity.
Qed.

(* Quantified adversary compromise theorems for session-key and broker compromise. *)
(*| discharges: R-12-015c |*)
Theorem session_key_compromise_breaks_exclusivity_and_enables_impersonation :
  forall profile policy auth tr conn attacker now sz ev,
  In (EvKeyExposed (protected_context conn) attacker) tr ->
  attacker <> context_unit (protected_context conn) ->
  snd (decide profile policy auth conn now sz (Some ev)) = true ->
  ~ NoKeyExposure tr /\
  ~ ExclusiveTrafficKeys (protected_context conn) [context_unit (protected_context conn); attacker] /\
  records_open (fst (decide profile policy auth conn now sz (Some ev)))
               [context_unit (protected_context conn); attacker] attacker = true.
Proof.
  intros profile policy auth tr conn attacker now sz ev Hexp Hneq Hacc.
  split; [intro Hno; exact (Hno (protected_context conn) attacker Hexp)|].
  split.
  - intro Hexcl. apply Hneq.
    apply Hexcl. right. left. reflexivity.
  - unfold decide in Hacc |- *. destruct (phase conn); [discriminate| |discriminate|discriminate].
    destruct (appraisal_checks profile policy auth conn now sz ev); [|discriminate].
    cbn. rewrite Nat.eqb_refl, orb_true_r. reflexivity.
Qed.

(*| discharges: R-12-015c |*)
Theorem broker_compromise_breaks_integrity_and_permits_forged_binding :
  forall env tr iss,
  In (EvBrokerCompromised (context_unit (issuer_context iss))) tr ->
  In (EvBrokerQuoteIssued iss) tr ->
  evidence_exporter (issued_evidence iss) <> context_exporter (issuer_context iss) ->
  ~ NoBrokerCompromise tr /\
  ~ LocalContextIntegrity (ms_profile env) (trace_issuances tr) (ms_measured env) (ms_aliases env).
Proof.
  intros env tr iss Hbrk Hiss Hneq.
  split; [intro Hno; exact (Hno (context_unit (issuer_context iss)) Hbrk)|].
  intro Hloc. apply trace_issuances_in_tr in Hiss.
  destruct (Hloc iss Hiss) as [_ [Heq _]]. contradiction.
Qed.

Definition witness_MultiSessionEnv : MultiSessionEnv := env_honest_sw.

Definition witness_ByteForwardingRelay : ByteForwardingRelay := {|
  relay_hops := [90; 91];
  relay_source := context_a;
  relay_target := context_a;
  relay_evidence := issued_evidence event_a;
  relay_same_holder := conj eq_refl (conj eq_refl (conj eq_refl eq_refl))
|}.
