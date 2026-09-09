(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   CredentialHandles.v

   Source-level request guards and delegation for M6.3b's credential-handle
   package, read against R-12-015a, R-12-015b and their sealing-service prose.
   The seven bindings are a protocol role, principal, peer/origin scope,
   permitted operation, transcript/domain separator, use count and expiry.
   Scope and operation authority are finite sets; this package narrows those
   sets while retaining the same role, principal and transcript. It chooses
   no hierarchy between roles, principals or transcript identifiers.

   A schema supplies the finite identifier bounds, protocol-specific operation
   relation and request bound. Their numeric values below are fixtures, not a
   credential IDL or a declaration of the platform's protocol vocabulary.
   Expiry validity and attenuation are supplied by policy; the general
   attenuation theorem explicitly requires their monotonicity. The fixture's
   half-open natural-number clock makes no claim about the platform's clock,
   units, unknown-time handling or selected expiry policy.

   ServerState is a trusted input, separate from ClientRequest. Its consent
   callback is indexed by the credential, request and shared use ordinal.
   A client request contains no approval bit. The guard theorem is conditional
   on this callback being the powerbox/trusted-path decision required by
   R-12-015b; callback authenticity and freshness are target integration
   obligations. A boolean answer is not itself a proof of either property.

   Delegation retains the same server-owned account, and its use count is an
   absolute ceiling on that account's consumed operations. Both handles spend
   that one counter. This is a concrete conservative candidate: delegating a
   ceiling already reached yields an unusable handle, and delegation creates
   no independently spendable quota. The serial transition below charges one
   authorized invocation. Atomicity under concurrent clients and the point at
   which a real protocol operation consumes its use are separate join inputs.

   The input credential is the authority the service obtains after authentic
   sealed-handle lookup. Gallina record construction models no CHERI sealing
   or unforgeability. No key bytes or generic sign/decrypt/derive operation
   are introduced here, and no cryptographic result is implemented. The finite
   schema must still be instantiated by the reviewed protocol IDL, the lookup
   and counter must join the actual service, and M6.3b's ring/storage target
   acceptance remains open. No whole-entry discharge is claimed.

   All functions terminate structurally. The computed examples distinguish
   weakened guards, widened delegations, cloned counters and client-supplied
   consent from the reference candidate. R-05-163's native assumption audit
   and R-05-166's closed record witnesses apply to this source artifact.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-166 R-12-015a R-12-015b
   SHA256: 5bc1c50fd80b3ac41cf1936783a1638b8e9dd0762b0bbc5d3300a0af3e3aeb03
   (*| END derived |*)
   ========================================================================= *)

Open Scope list_scope.

Fixpoint every (xs : list bool) : bool :=
  match xs with nil => true | x :: rest => andb x (every rest) end.

Fixpoint member (x : nat) (xs : list nat) : bool :=
  match xs with
  | nil => false
  | y :: rest => orb (Nat.eqb x y) (member x rest)
  end.

Fixpoint included (xs ys : list nat) : bool :=
  match xs with
  | nil => true
  | x :: rest => andb (member x ys) (included rest ys)
  end.

Fixpoint byte_length (xs : list nat) : nat :=
  match xs with nil => 0 | _ :: rest => S (byte_length rest) end.

Fixpoint bytes_valid (xs : list nat) : bool :=
  match xs with
  | nil => true
  | x :: rest => andb (Nat.ltb x 256) (bytes_valid rest)
  end.

Lemma andb_split : forall a b, andb a b = true -> a = true /\ b = true.
Proof. destruct a, b; simpl; intros; try discriminate; split; reflexivity. Qed.

Lemma eqb_refl : forall n, Nat.eqb n n = true.
Proof. induction n; simpl; auto. Qed.

Lemma eqb_equal : forall x y, Nat.eqb x y = true -> x = y.
Proof.
  induction x; destruct y; simpl; intros H; try discriminate; auto.
Qed.

Lemma member_included : forall xs ys x,
  included xs ys = true -> member x xs = true -> member x ys = true.
Proof.
  induction xs as [|a rest IH]; intros ys x Hsub Hin; simpl in *.
  - discriminate.
  - apply andb_split in Hsub as [Ha Hr].
    destruct (Nat.eqb x a) eqn:E.
    + apply eqb_equal in E. subst x. exact Ha.
    + simpl in Hin. exact (IH ys x Hr Hin).
Qed.

Lemma below_smaller_ceiling : forall used child parent,
  Nat.leb child parent = true -> Nat.ltb used child = true ->
  Nat.ltb used parent = true.
Proof.
  induction used; destruct child, parent; simpl; intros Hle Hlt;
    try discriminate; eauto.
Qed.

Record Credential : Type := mk_credential {
  credential_role : nat;
  credential_principal : nat;
  credential_scopes : list nat;
  credential_operations : list nat;
  credential_transcript : nat;
  credential_use_ceiling : nat;
  credential_expiry : nat;
  credential_account : nat
}.

Record ClientRequest : Type := mk_request {
  request_role : nat;
  request_principal : nat;
  request_scope : nat;
  request_operation : nat;
  request_transcript : nat;
  request_bytes : list nat
}.

Record CredentialPolicy : Type := mk_policy {
  role_count : nat;
  principal_count : nat;
  scope_count : nat;
  operation_count : nat;
  transcript_count : nat;
  request_limit : nat -> nat -> nat;
  protocol_operation : nat -> nat -> bool;
  needs_approval : nat -> nat -> bool;
  expiry_valid : nat -> nat -> bool;
  expiry_narrower : nat -> nat -> bool
}.

Record ServerState : Type := mk_server {
  account_used : nat -> nat;
  server_now : nat;
  consent_allows : Credential -> ClientRequest -> nat -> bool
}.

Definition expiry_is_monotone (p : CredentialPolicy) : Prop :=
  forall child parent now,
    expiry_narrower p child parent = true ->
    expiry_valid p child now = true -> expiry_valid p parent now = true.

(* These are identifiers in the composition's typed schema. The operation
   relation is checked in addition to the separate identifier bounds. *)
Definition schema_accepts (p : CredentialPolicy) (r : ClientRequest) : bool :=
  every (Nat.ltb (request_role r) (role_count p) ::
         Nat.ltb (request_principal r) (principal_count p) ::
         Nat.ltb (request_scope r) (scope_count p) ::
         Nat.ltb (request_operation r) (operation_count p) ::
         Nat.ltb (request_transcript r) (transcript_count p) ::
         protocol_operation p (request_role r) (request_operation r) ::
         Nat.leb (byte_length (request_bytes r))
                 (request_limit p (request_role r) (request_operation r)) ::
         bytes_valid (request_bytes r) :: nil).

Theorem admitted_schema_values_are_inside_their_declared_bounds : forall p r,
  schema_accepts p r = true ->
  Nat.ltb (request_role r) (role_count p) = true /\
  Nat.ltb (request_principal r) (principal_count p) = true /\
  Nat.ltb (request_scope r) (scope_count p) = true /\
  Nat.ltb (request_operation r) (operation_count p) = true /\
  Nat.ltb (request_transcript r) (transcript_count p) = true /\
  protocol_operation p (request_role r) (request_operation r) = true /\
  Nat.leb (byte_length (request_bytes r))
          (request_limit p (request_role r) (request_operation r)) = true /\
  bytes_valid (request_bytes r) = true.
Proof.
  intros p r H. unfold schema_accepts, every in H.
  repeat match goal with
  | H : andb _ _ = true |- _ => apply andb_split in H as [? ?]
  end.
  repeat split; assumption.
Qed.

Definition bindings_match (c : Credential) (r : ClientRequest) : bool :=
  andb (Nat.eqb (request_role r) (credential_role c))
  (andb (Nat.eqb (request_principal r) (credential_principal c))
  (andb (member (request_scope r) (credential_scopes c))
  (andb (member (request_operation r) (credential_operations c))
        (Nat.eqb (request_transcript r) (credential_transcript c))))).

Definition consent_gate (p : CredentialPolicy) (c : Credential)
           (s : ServerState) (r : ClientRequest) : bool :=
  if needs_approval p (request_role r) (request_operation r)
  then consent_allows s c r (account_used s (credential_account c))
  else true.

(* The executable guards and their serial state transition. *)
Definition authorization_checks (p : CredentialPolicy) (c : Credential)
           (s : ServerState) (r : ClientRequest) : list bool :=
  bindings_match c r :: schema_accepts p r ::
  Nat.ltb (account_used s (credential_account c)) (credential_use_ceiling c) ::
  expiry_valid p (credential_expiry c) (server_now s) ::
  consent_gate p c s r :: nil.

Definition authorized (p : CredentialPolicy) (c : Credential)
           (s : ServerState) (r : ClientRequest) : bool :=
  every (authorization_checks p c s r).

Definition delegation_checks (p : CredentialPolicy)
           (parent child : Credential) : list bool :=
  Nat.eqb (credential_role child) (credential_role parent) ::
  Nat.eqb (credential_principal child) (credential_principal parent) ::
  included (credential_scopes child) (credential_scopes parent) ::
  included (credential_operations child) (credential_operations parent) ::
  Nat.eqb (credential_transcript child) (credential_transcript parent) ::
  Nat.leb (credential_use_ceiling child) (credential_use_ceiling parent) ::
  expiry_narrower p (credential_expiry child) (credential_expiry parent) ::
  Nat.eqb (credential_account child) (credential_account parent) :: nil.

Definition delegates (p : CredentialPolicy) (parent child : Credential) : bool :=
  every (delegation_checks p parent child).

Definition charge (s : ServerState) (account : nat) : ServerState :=
  mk_server (fun n => if Nat.eqb n account
                     then S (account_used s n) else account_used s n)
            (server_now s) (consent_allows s).

Definition authorize_and_charge (p : CredentialPolicy) (c : Credential)
           (s : ServerState) (r : ClientRequest) : option ServerState :=
  if authorized p c s r then Some (charge s (credential_account c)) else None.

Theorem delegated_bindings_are_parent_bindings : forall p parent child r,
  delegates p parent child = true -> bindings_match child r = true ->
  bindings_match parent r = true.
Proof.
  intros p parent child r Hd Hb.
  unfold delegates, delegation_checks, every in Hd.
  unfold bindings_match in *.
  repeat match goal with
  | H : andb _ _ = true |- _ => apply andb_split in H as [? ?]
  end.
  repeat match goal with
  | H : Nat.eqb _ _ = true |- _ => apply eqb_equal in H
  end.
  match goal with
  | Hr : request_role r = credential_role child,
    Hc : credential_role child = credential_role parent |- _ =>
      rewrite Hr, Hc, eqb_refl
  end.
  match goal with
  | Hr : request_principal r = credential_principal child,
    Hc : credential_principal child = credential_principal parent |- _ =>
      rewrite Hr, Hc, eqb_refl
  end.
  match goal with
  | Hs : included (credential_scopes child) (credential_scopes parent) = true,
    Hm : member (request_scope r) (credential_scopes child) = true |- _ =>
      rewrite (member_included _ _ _ Hs Hm)
  end.
  match goal with
  | Hs : included (credential_operations child) (credential_operations parent) = true,
    Hm : member (request_operation r) (credential_operations child) = true |- _ =>
      rewrite (member_included _ _ _ Hs Hm)
  end.
  match goal with
  | Hr : request_transcript r = credential_transcript child,
    Hc : credential_transcript child = credential_transcript parent |- _ =>
      rewrite Hr, Hc, eqb_refl
  end.
  reflexivity.
Qed.

(* The trusted consent decision may deliberately distinguish a delegated
   handle from its parent. Authority monotonicity therefore stops at the
   binding, schema, account and expiry guards. Consent is independently
   rechecked on whichever actual handle is invoked. *)
Definition authority_allows (p : CredentialPolicy) (c : Credential)
           (s : ServerState) (r : ClientRequest) : bool :=
  andb (bindings_match c r)
  (andb (schema_accepts p r)
  (andb (Nat.ltb (account_used s (credential_account c))
                 (credential_use_ceiling c))
        (expiry_valid p (credential_expiry c) (server_now s)))).

Theorem authority_requires_binding_budget_and_expiry : forall p c s r,
  authority_allows p c s r = true ->
  bindings_match c r = true /\ schema_accepts p r = true /\
  Nat.ltb (account_used s (credential_account c)) (credential_use_ceiling c) = true /\
  expiry_valid p (credential_expiry c) (server_now s) = true.
Proof.
  intros p c s r H. unfold authority_allows in H.
  repeat match goal with
  | H : andb _ _ = true |- _ => apply andb_split in H as [? ?]
  end.
  repeat split; assumption.
Qed.

Theorem authorization_checks_the_authority : forall p c s r,
  authorized p c s r = true -> authority_allows p c s r = true.
Proof.
  intros p c s r H.
  unfold authorized, authorization_checks, every in H.
  unfold authority_allows.
  destruct (bindings_match c r), (schema_accepts p r),
    (Nat.ltb (account_used s (credential_account c)) (credential_use_ceiling c)),
    (expiry_valid p (credential_expiry c) (server_now s));
    simpl in *; try discriminate; reflexivity.
Qed.

Theorem delegated_authority_is_monotone : forall p parent child s r,
  expiry_is_monotone p -> delegates p parent child = true ->
  authority_allows p child s r = true -> authority_allows p parent s r = true.
Proof.
  intros p parent child s r Hexpiry Hd Ha.
  assert (Hb : bindings_match parent r = true).
  { unfold authority_allows in Ha. apply andb_split in Ha as [Hb _].
    exact (delegated_bindings_are_parent_bindings p parent child r Hd Hb). }
  unfold delegates, delegation_checks, every in Hd.
  unfold authority_allows in *.
  repeat match goal with
  | H : andb _ _ = true |- _ => apply andb_split in H as [? ?]
  end.
  rewrite Hb.
  match goal with H : schema_accepts p r = true |- _ => rewrite H end.
  match goal with
  | Haccount : Nat.eqb (credential_account child) (credential_account parent) = true,
    Hlimit : Nat.leb (credential_use_ceiling child) (credential_use_ceiling parent) = true,
    Hused : Nat.ltb (account_used s (credential_account child))
                    (credential_use_ceiling child) = true |- _ =>
      apply eqb_equal in Haccount; rewrite Haccount in Hused;
      rewrite (below_smaller_ceiling _ _ _ Hlimit Hused)
  end.
  match goal with
  | Hn : expiry_narrower p (credential_expiry child) (credential_expiry parent) = true,
    Hv : expiry_valid p (credential_expiry child) (server_now s) = true |- _ =>
      rewrite (Hexpiry _ _ _ Hn Hv)
  end.
  reflexivity.
Qed.

Theorem authorization_checks_trusted_consent : forall p c s r,
  authorized p c s r = true ->
  needs_approval p (request_role r) (request_operation r) = true ->
  consent_allows s c r (account_used s (credential_account c)) = true.
Proof.
  intros p c s r H Hrequired.
  unfold authorized, authorization_checks, every in H.
  repeat match goal with
  | H : andb _ _ = true |- _ => apply andb_split in H as [? ?]
  end.
  match goal with H : consent_gate p c s r = true |- _ =>
    unfold consent_gate in H; rewrite Hrequired in H; exact H
  end.
Qed.

Theorem operations_without_approval_skip_the_callback : forall p c s r,
  needs_approval p (request_role r) (request_operation r) = false ->
  consent_gate p c s r = true.
Proof. intros p c s r H. unfold consent_gate. rewrite H. reflexivity. Qed.

Theorem a_charge_increments_the_shared_account : forall s account,
  account_used (charge s account) account = S (account_used s account).
Proof. intros. simpl. rewrite eqb_refl. reflexivity. Qed.

Theorem a_charge_preserves_other_accounts : forall s account other,
  Nat.eqb other account = false ->
  account_used (charge s account) other = account_used s other.
Proof. intros s account other H. simpl. rewrite H. reflexivity. Qed.

Theorem a_delegated_charge_is_visible_to_the_parent : forall p parent child s,
  delegates p parent child = true ->
  account_used (charge s (credential_account child)) (credential_account parent) =
  S (account_used s (credential_account parent)).
Proof.
  intros p parent child s H. unfold delegates, delegation_checks, every in H.
  repeat match goal with
  | H : andb _ _ = true |- _ => apply andb_split in H as [? ?]
  end.
  match goal with
  | H : Nat.eqb (credential_account child) (credential_account parent) = true |- _ =>
    apply eqb_equal in H; rewrite H
  end.
  apply a_charge_increments_the_shared_account.
Qed.

Theorem a_refused_request_changes_no_state : forall p c s r,
  authorized p c s r = false -> authorize_and_charge p c s r = None.
Proof. intros p c s r H. unfold authorize_and_charge. rewrite H. reflexivity. Qed.

(* Fixtures inhabit the policies without selecting the deployment's values.
   All role/operation pairs in this fixture require fresh trusted consent. *)
Definition demo_policy : CredentialPolicy :=
  mk_policy 3 4 5 3 6 (fun _ _ => 4)
    (fun role op => Nat.eqb role op) (fun _ _ => true)
    (fun expiry now => Nat.ltb now expiry) Nat.leb.

Definition demo_parent : Credential :=
  mk_credential 1 2 (1 :: 2 :: nil) (1 :: 2 :: nil) 3 2 20 7.

Definition demo_child : Credential :=
  mk_credential 1 2 (1 :: nil) (1 :: nil) 3 1 15 7.

Definition demo_request : ClientRequest := mk_request 1 2 1 1 3 (17 :: 23 :: nil).

Definition approved_state : ServerState :=
  mk_server (fun _ => 0) 10 (fun _ _ _ => true).

Definition denied_state : ServerState :=
  mk_server (fun _ => 0) 10 (fun _ _ _ => false).

Definition consent_once_state : ServerState :=
  mk_server (fun _ => 0) 10 (fun _ _ ordinal => Nat.eqb ordinal 0).

Definition state_after (p : CredentialPolicy) (c : Credential)
           (s : ServerState) (r : ClientRequest) : ServerState :=
  match authorize_and_charge p c s r with Some next => next | None => s end.

Example the_fixture_expiry_relation_is_monotone : expiry_is_monotone demo_policy.
Proof.
  intros child parent now Hle Hlt.
  exact (below_smaller_ceiling now child parent Hle Hlt).
Qed.

Example the_reference_delegation_and_request_are_admitted :
  every (delegates demo_policy demo_parent demo_child ::
         authorized demo_policy demo_parent approved_state demo_request ::
         authorized demo_policy demo_child approved_state demo_request :: nil) = true.
Proof. vm_compute; reflexivity. Qed.

(* One altered request for each identity/set binding, generated by the field
   index. Use and expiry depend on trusted state and are varied separately. *)
Definition alter_request (field : nat) (r : ClientRequest) : ClientRequest :=
  mk_request
    (if Nat.eqb field 0 then S (request_role r) else request_role r)
    (if Nat.eqb field 1 then S (request_principal r) else request_principal r)
    (if Nat.eqb field 2 then S (request_scope r) else request_scope r)
    (if Nat.eqb field 3 then S (request_operation r) else request_operation r)
    (if Nat.eqb field 4 then S (request_transcript r) else request_transcript r)
    (request_bytes r).

Fixpoint request_refusals (count : nat) : list bool :=
  match count with
  | 0 => nil
  | S n => negb (authorized demo_policy demo_child approved_state
                           (alter_request n demo_request)) :: request_refusals n
  end.

Example every_changed_request_binding_is_refused : every (request_refusals 5) = true.
Proof. vm_compute; reflexivity. Qed.

Definition widen_credential (field : nat) (c : Credential) : Credential :=
  mk_credential
    (if Nat.eqb field 0 then S (credential_role c) else credential_role c)
    (if Nat.eqb field 1 then S (credential_principal c) else credential_principal c)
    (if Nat.eqb field 2 then 4 :: credential_scopes c else credential_scopes c)
    (if Nat.eqb field 3 then 0 :: credential_operations c else credential_operations c)
    (if Nat.eqb field 4 then S (credential_transcript c) else credential_transcript c)
    (if Nat.eqb field 5 then S (credential_use_ceiling c) else credential_use_ceiling c)
    (if Nat.eqb field 6 then S (credential_expiry c) else credential_expiry c)
    (if Nat.eqb field 7 then S (credential_account c) else credential_account c).

Fixpoint widening_refusals (count : nat) : list bool :=
  match count with
  | 0 => nil
  | S n => negb (delegates demo_policy demo_parent
                          (widen_credential n demo_parent)) :: widening_refusals n
  end.

Example every_widened_binding_and_cloned_account_is_refused :
  every (widening_refusals 8) = true.
Proof. vm_compute; reflexivity. Qed.

Definition skip_check (index : nat) (checks : list bool) : bool :=
  every (let fix skip (n : nat) (xs : list bool) : list bool :=
           match xs with
           | nil => nil
           | x :: rest => match n with 0 => true :: rest | S k => x :: skip k rest end
           end
         in skip index checks).

Fixpoint weakened_delegations (count : nat) : list bool :=
  match count with
  | 0 => nil
  | S n => skip_check n (delegation_checks demo_policy demo_parent
                             (widen_credential n demo_parent)) :: weakened_delegations n
  end.

Example each_missing_delegation_check_admits_its_own_widening :
  every (weakened_delegations 8) = true.
Proof. vm_compute; reflexivity. Qed.

Definition used_up_state : ServerState := mk_server (fun _ => 2) 10 (fun _ _ _ => true).
Definition expired_state : ServerState := mk_server (fun _ => 0) 20 (fun _ _ _ => true).
Definition invalid_schema_request : ClientRequest := mk_request 1 2 1 2 3 nil.
Definition invalid_binding_request : ClientRequest := alter_request 1 demo_request.

Example every_authorization_guard_has_a_distinguishing_refuter :
  every
    (andb (negb (authorized demo_policy demo_parent approved_state invalid_binding_request))
          (skip_check 0 (authorization_checks demo_policy demo_parent approved_state
                                               invalid_binding_request)) ::
     andb (negb (authorized demo_policy demo_parent approved_state invalid_schema_request))
          (skip_check 1 (authorization_checks demo_policy demo_parent approved_state
                                               invalid_schema_request)) ::
     andb (negb (authorized demo_policy demo_parent used_up_state demo_request))
          (skip_check 2 (authorization_checks demo_policy demo_parent used_up_state demo_request)) ::
     andb (negb (authorized demo_policy demo_parent expired_state demo_request))
          (skip_check 3 (authorization_checks demo_policy demo_parent expired_state demo_request)) ::
     andb (negb (authorized demo_policy demo_parent denied_state demo_request))
          (skip_check 4 (authorization_checks demo_policy demo_parent denied_state demo_request)) :: nil)
    = true.
Proof. vm_compute; reflexivity. Qed.

Definition request_with_bytes (payload : list nat) : ClientRequest :=
  mk_request 1 2 1 1 3 payload.

Example the_schema_accepts_its_bound_and_refuses_one_past :
  andb (authorized demo_policy demo_parent approved_state
                    (request_with_bytes (0 :: 1 :: 2 :: 255 :: nil)))
       (negb (authorized demo_policy demo_parent approved_state
                    (request_with_bytes (0 :: 1 :: 2 :: 255 :: 4 :: nil)))) = true.
Proof. vm_compute; reflexivity. Qed.

Example a_non_byte_is_refused_inside_the_length_bound :
  authorized demo_policy demo_parent approved_state (request_with_bytes (256 :: nil)) = false.
Proof. vm_compute; reflexivity. Qed.

Definition after_child : ServerState :=
  state_after demo_policy demo_child approved_state demo_request.
Definition after_parent_and_child : ServerState :=
  state_after demo_policy demo_parent after_child demo_request.

Example the_child_spends_the_shared_counter_without_copying_its_quota :
  every (Nat.eqb (account_used after_child 7) 1 ::
         negb (authorized demo_policy demo_child after_child demo_request) ::
         authorized demo_policy demo_parent after_child demo_request ::
         Nat.eqb (account_used after_parent_and_child 7) 2 ::
         negb (authorized demo_policy demo_parent after_parent_and_child demo_request) ::
         negb (authorized demo_policy demo_child after_parent_and_child demo_request) ::
         Nat.eqb (account_used after_parent_and_child 8) 0 :: nil) = true.
Proof. vm_compute; reflexivity. Qed.

Example unchanged_consent_for_an_old_ordinal_does_not_approve_the_next_use :
  let next := state_after demo_policy demo_parent consent_once_state demo_request in
  andb (authorized demo_policy demo_parent consent_once_state demo_request)
       (negb (authorized demo_policy demo_parent next demo_request)) = true.
Proof. vm_compute; reflexivity. Qed.

(* A refuter that lets a caller assert approval accepts the same request that
   the trusted callback refuses. There is no such argument on authorized. *)
Definition client_approval_refuter (asserted_approval : bool) : bool :=
  andb (authority_allows demo_policy demo_parent denied_state demo_request) asserted_approval.

Example a_client_approval_bit_is_a_distinguishing_weakening :
  andb (client_approval_refuter true)
       (negb (authorized demo_policy demo_parent denied_state demo_request)) = true.
Proof. vm_compute; reflexivity. Qed.

Definition witness_Credential : Credential := demo_parent.
Definition witness_ClientRequest : ClientRequest := demo_request.
Definition witness_CredentialPolicy : CredentialPolicy := demo_policy.
Definition witness_ServerState : ServerState := approved_state.

Print Assumptions delegated_bindings_are_parent_bindings.
Print Assumptions admitted_schema_values_are_inside_their_declared_bounds.
Print Assumptions authorization_checks_the_authority.
Print Assumptions authority_requires_binding_budget_and_expiry.
Print Assumptions delegated_authority_is_monotone.
Print Assumptions authorization_checks_trusted_consent.
Print Assumptions operations_without_approval_skip_the_callback.
Print Assumptions a_charge_increments_the_shared_account.
Print Assumptions a_charge_preserves_other_accounts.
Print Assumptions a_delegated_charge_is_visible_to_the_parent.
Print Assumptions a_refused_request_changes_no_state.
Print Assumptions the_fixture_expiry_relation_is_monotone.
Print Assumptions every_changed_request_binding_is_refused.
Print Assumptions every_widened_binding_and_cloned_account_is_refused.
Print Assumptions each_missing_delegation_check_admits_its_own_widening.
Print Assumptions every_authorization_guard_has_a_distinguishing_refuter.
Print Assumptions the_child_spends_the_shared_counter_without_copying_its_quota.
Print Assumptions unchanged_consent_for_an_old_ordinal_does_not_approve_the_next_use.
