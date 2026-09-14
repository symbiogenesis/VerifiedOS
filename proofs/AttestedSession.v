(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   AttestedSession: symbolic session agreement for the source-object-fetch
   protocol fixed in docs/implementation/attested-tls-protocol.md before code.
   It reuses CredentialHandles.authorize_and_charge for the seven authority
   bindings of R-12-015a. R-12-015c joins measured state, challenge, protocol,
   peer policy and holder of TLS traffic keys; R-09-025a keeps software-only
   policy distinct from a relying-party-specific unit pseudonym.

   Q22c's finite experiment is generalized over arbitrary received evidence,
   issuer events, measured generations, policies and completed contexts.
   Exporters, origins, nonces and protocol identifiers are symbolic atoms.
   This is not a TLS, hash, signature, entropy or byte-parser proof. There is
   no admitted TLS implementation in the inspected pins. U-20 still owes the
   cryptographic foundation, and M6.9b owes its implementation connection.

   ExporterSecurity, EvidenceAuthenticity, LocalContextIntegrity,
   UncompromisedSessionKeys and AuthenticatedUnitPseudonyms are explicit
   premises. Evidence authenticity is scoped to actual received evidence and
   a ledger of issuance events. It never quantifies an authenticity flag over
   every freely constructible quote. The complete premise conjunction is
   inhabited below, for both software and unit policies, and the quantified
   theorem is applied to it. Removing key custody or exporter integrity has
   concrete accepted attacks. A byte-forwarding relay retains the intended
   key holder and adds no record authority; it is distinct from substitution.

   The interface makes the exporter structurally local to broker issuance:
   no exporter argument exists. A caller presents a credential request and
   challenge; the protected context contributes holder, principal, origin,
   measured generation and exporter. Atomic credential charge and the single
   appraisal lifecycle are explicit. Sizes/deadlines are composition inputs;
   nonempty fresh challenges are checked against trusted nonce history. Real
   context handles, nonces, canonical evidence bytes and durable state are
   adapter obligations, not consequences of the symbolic constructors.

   Acceptance: native compilation, complete empty assumption closure,
   rocqchk, named record witnesses and inhabited theorem premises, plus replay,
   concurrency, other approved unit, wrong unit alias, refusal, relay and
   compromise cases. Q22c's session-binding command remains finite supporting
   evidence. This artifact does not close the admitted-TLS implementation or
   computational session-key security portions of M6.9a/c.
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
  used_nonces : list nat
}.

Definition with_phase (c : Connection) (ph : Phase) : Connection :=
  {| protected_context := protected_context c; phase := ph;
     pending_challenge := pending_challenge c; pending_deadline := pending_deadline c;
     used_nonces := used_nonces c |}.

Definition begin_appraisal (profile : AttestationProfile) (policy : AppraisalPolicy)
    (c : Connection) (nonce now deadline : nat) : Connection :=
  match phase c with
  | Fresh =>
    if profile_bounded profile && context_usable (protected_context c) && (0 <? nonce) && (now <? deadline) &&
       negb (existsb (Nat.eqb nonce) (used_nonces c)) then
    {| protected_context := protected_context c; phase := Waiting;
       pending_challenge := {| challenge_nonce := nonce;
         challenge_origin := context_origin (protected_context c);
         challenge_unit_scope := unit_policy policy; challenge_domain := protocol_domain profile |};
       pending_deadline := deadline; used_nonces := nonce :: used_nonces c |}
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
  if context_id new_context =? context_id (protected_context c) then with_phase c Closed
  else {| protected_context := new_context; phase := Fresh;
          pending_challenge := pending_challenge c; pending_deadline := 0;
          used_nonces := used_nonces c |}.

Theorem reconnecting_keeps_challenge_history : forall c new_context,
  used_nonces (reconnect c new_context) = used_nonces c.
Proof. intros. unfold reconnect. destruct (context_id new_context =? context_id (protected_context c)); reflexivity. Qed.

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
    (0 <? nonce) && (now <? deadline) && negb (existsb (Nat.eqb nonce) (used_nonces c))) eqn:E;
    [|discriminate].
  repeat rewrite andb_true_iff in E. destruct E as [[[[_ _] Hnonce] _] _].
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
     pending_deadline := 0; used_nonces := [] |}.
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
