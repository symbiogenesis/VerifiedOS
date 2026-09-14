(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ModuleAdmission.v: Q24c/Q24d typed source candidate.
   Contract: docs/hardware/immutable-module-admission.md, committed before this
   implementation. R-12-085g, R-12-085h, R-12-085i, R-12-085j,
   R-15-228f, R-15-228g, R-15-228h and R-15-228i own the obligations.

   The arbitrary-card theorem is over the digital host transition, assuming
   bounded detection/isolation, connector sequencing, current/inrush/backfeed,
   short/overvoltage/thermal protection, independent host rails/reset, and module
   clocks terminating at bounded endpoint FIFOs. R-15-228i/Q24f must qualify
   these electrical assumptions; arbitrary physical sabotage is outside them.

   Manifest identities below denote exact immutable byte artifacts. Equality is
   symbolic identity, not a cryptographic hash theorem or a canonical byte parser.
   Kernel receipts and authenticated issuance are trusted host inputs, not card
   claims. No CIC checker, signature, TLS implementation or entropy source is
   implemented here. The model states the binding each must refine. Freshness
   histories survive modeled reset; a real bounded reset-safe construction is
   owed. Unit-key compromise or corrupt issuance invalidates authentication.

   The socket emits proposals into precomposed host-selected endpoint objects.
   It never changes host memory, capabilities, schedule or quota. The later broker
   mover must refine this relation with capability checks and a completion barrier.
   These statements are not a Sail/RTL, whole-path, honest-card erasure or
   fabrication theorem. All constants below are fixtures, not platform values.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-12-085g R-12-085h R-12-085i R-12-085j R-15-228f R-15-228g R-15-228h R-15-228i
   SHA256: 83f8e77138c6f17d1393d14504b6e968f082e7479c892b8e8876decd5b5aafd5
   (*| END derived |*)
   ========================================================================= *)

Open Scope list_scope.

Fixpoint count {A : Type} (xs : list A) : nat :=
  match xs with nil => 0 | _ :: ys => S (count ys) end.
Fixpoint every (xs : list bool) : bool :=
  match xs with nil => true | x :: ys => andb x (every ys) end.
Fixpoint member (x : nat) (xs : list nat) : bool :=
  match xs with nil => false | y :: ys => orb (Nat.eqb x y) (member x ys) end.
Fixpoint included (xs ys : list nat) : bool :=
  match xs with nil => true | x :: rest => andb (member x ys) (included rest ys) end.
Fixpoint same (xs ys : list nat) : bool :=
  match xs, ys with
  | nil, nil => true
  | x :: xt, y :: yt => andb (Nat.eqb x y) (same xt yt)
  | _, _ => false
  end.
Fixpoint below (limit : nat) (xs : list nat) : bool :=
  match xs with nil => true | x :: ys => andb (Nat.ltb x limit) (below limit ys) end.
Fixpoint bool_at (n : nat) (xs : list bool) : bool :=
  match n, xs with _, nil => true | 0, x :: _ => x | S k, _ :: ys => bool_at k ys end.

Lemma every_at : forall xs n, every xs = true -> bool_at n xs = true.
Proof.
  induction xs as [|x xs IH]; intros n H; destruct n; simpl in *; auto.
  - destruct x; simpl in H; congruence.
  - destruct x; simpl in H; try discriminate. apply IH. exact H.
Qed.
Lemma andb_split : forall a b, andb a b = true -> a = true /\ b = true.
Proof. destruct a, b; simpl; intros; try discriminate; split; reflexivity. Qed.
Lemma eqb_equal : forall x y, Nat.eqb x y = true -> x = y.
Proof. induction x; destruct y; simpl; intros H; try discriminate; auto. Qed.
Lemma same_equal : forall xs ys, same xs ys = true -> xs = ys.
Proof.
  induction xs as [|x xs IH]; destruct ys as [|y ys]; simpl; intros H;
    try discriminate; auto.
  destruct (Nat.eqb x y) eqn:E; simpl in H; try discriminate.
  apply eqb_equal in E. apply IH in H. subst. reflexivity.
Qed.

Record Manifest := {
  graph_id : nat; weights_id : nat; arithmetic_id : nat; tokenizer_id : nat;
  vocabulary_id : nat; circuit_id : nat; implementation_id : nat;
  schema_id : nat; protocol_id : nat; footprint_id : nat; envelope_id : nat;
  propositions_id : nat
}.
Definition identity (m : Manifest) : list nat :=
  graph_id m :: weights_id m :: arithmetic_id m :: tokenizer_id m ::
  vocabulary_id m :: circuit_id m :: implementation_id m :: schema_id m ::
  protocol_id m :: footprint_id m :: envelope_id m :: propositions_id m :: nil.

Record Bounds := {
  evidence_bytes : nat; checking_fuel : nat; scratch_bytes : nat;
  verdict_ticks : nat; identifier_bound : nat
}.
Record KernelReceipt := {
  checked_subject : list nat; checked_evidence : list nat;
  checked_assumptions : list nat; checked_checker : nat; checked_profile : nat;
  spent_fuel : nat; spent_scratch : nat; spent_ticks : nat
}.
(* A receipt is produced only after the trusted kernel accepted these exact
   evidence bytes. Passing an arbitrary record here is not an executable checker. *)
Definition design_checks (b : Bounds) (expected offered : Manifest)
    (evidence allowed : list nat) (checker profile : nat) (r : KernelReceipt)
    : list bool :=
  same (identity offered) (identity expected) ::
  below (identifier_bound b) (identity offered) ::
  below 256 evidence :: Nat.ltb 0 (count evidence) ::
  Nat.leb (count evidence) (evidence_bytes b) ::
  same (checked_subject r) (identity expected) ::
  same (checked_evidence r) evidence ::
  included (checked_assumptions r) allowed ::
  Nat.eqb (checked_checker r) checker :: Nat.eqb (checked_profile r) profile ::
  Nat.leb (spent_fuel r) (checking_fuel b) ::
  Nat.leb (spent_scratch r) (scratch_bytes b) ::
  Nat.leb (spent_ticks r) (verdict_ticks b) :: nil.
Definition admit_design b expected offered evidence allowed checker profile r :=
  every (design_checks b expected offered evidence allowed checker profile r).

Theorem admitted_manifest_exact : forall b expected offered evidence allowed c p r,
  admit_design b expected offered evidence allowed c p r = true ->
  identity offered = identity expected.
Proof.
  intros b expected offered evidence allowed c p r H.
  apply same_equal. exact (every_at _ 0 H).
Qed.
Theorem admitted_assumptions_allowed : forall b e m bytes allowed c p r,
  admit_design b e m bytes allowed c p r = true ->
  included (checked_assumptions r) allowed = true.
Proof. intros. exact (every_at _ 7 H). Qed.
Theorem admitted_receipt_exact : forall b e m bytes allowed c p r,
  admit_design b e m bytes allowed c p r = true -> checked_evidence r = bytes.
Proof. intros. apply same_equal. exact (every_at _ 6 H). Qed.

Record SessionContext := {
  host_role : nat; unit_role : nat; endpoint : nat; unit_key : nat;
  design : nat; model : nat; generation_policy : nat; schedule : nat;
  activation_epoch : nat; session_epoch : nat; suite : nat; protocol : nat;
  host_nonce : nat; unit_nonce : nat; host_ephemeral : nat; unit_ephemeral : nat
}.
Definition context_identity (c : SessionContext) : list nat :=
  host_role c :: unit_role c :: endpoint c :: unit_key c :: design c :: model c ::
  generation_policy c :: schedule c :: activation_epoch c :: session_epoch c ::
  suite c :: protocol c :: host_nonce c :: unit_nonce c :: host_ephemeral c ::
  unit_ephemeral c :: nil.
Record AuthenticatedReply := {
  issued_context : SessionContext; actual_signing_key : nat;
  endorsed_design : nat; endorsed_model : nat; endorsed_lifecycle : nat
}.
Record AdmissionCache := {
  cached_design : nat; cached_model : nat; admitted_units : list nat;
  production_lifecycle : nat; design_checked : bool;
  prior_nonces : list nat; prior_ephemerals : list nat
}.
Definition insertion_checks (cache : AdmissionCache) (expected : SessionContext)
    (r : AuthenticatedReply) : list bool :=
  design_checked cache ::
  same (context_identity (issued_context r)) (context_identity expected) ::
  Nat.eqb (actual_signing_key r) (unit_key expected) ::
  member (unit_key expected) (admitted_units cache) ::
  Nat.eqb (design expected) (cached_design cache) ::
  Nat.eqb (model expected) (cached_model cache) ::
  Nat.eqb (endorsed_design r) (cached_design cache) ::
  Nat.eqb (endorsed_model r) (cached_model cache) ::
  Nat.eqb (endorsed_lifecycle r) (production_lifecycle cache) ::
  negb (Nat.eqb (host_role expected) (unit_role expected)) ::
  negb (member (host_nonce expected) (prior_nonces cache)) ::
  negb (member (unit_nonce expected) (prior_nonces cache)) ::
  negb (Nat.eqb (host_nonce expected) (unit_nonce expected)) ::
  negb (member (host_ephemeral expected) (prior_ephemerals cache)) ::
  negb (member (unit_ephemeral expected) (prior_ephemerals cache)) ::
  negb (Nat.eqb (host_ephemeral expected) (unit_ephemeral expected)) :: nil.
Definition insert_unit cache expected (reply : option AuthenticatedReply) :=
  match reply with None => false | Some r => every (insertion_checks cache expected r) end.
Theorem insertion_binds_authenticated_context : forall cache c r,
  insert_unit cache c (Some r) = true ->
  context_identity (issued_context r) = context_identity c.
Proof. intros. apply same_equal. exact (every_at _ 1 H). Qed.
Theorem insertion_requires_possession : forall cache c r,
  insert_unit cache c (Some r) = true -> actual_signing_key r = unit_key c.
Proof. intros. apply eqb_equal. exact (every_at _ 2 H). Qed.
Theorem insertion_uses_finite_set : forall cache c r,
  insert_unit cache c (Some r) = true -> member (unit_key c) (admitted_units cache) = true.
Proof. intros. exact (every_at _ 3 H). Qed.
Theorem copied_identifier_without_key : forall cache c, insert_unit cache c None = false.
Proof. reflexivity. Qed.
Definition record_insertion (cache : AdmissionCache) (c : SessionContext) : AdmissionCache :=
  {| cached_design:=cached_design cache; cached_model:=cached_model cache;
     admitted_units:=admitted_units cache; production_lifecycle:=production_lifecycle cache;
     design_checked:=design_checked cache;
     prior_nonces:=host_nonce c :: unit_nonce c :: prior_nonces cache;
     prior_ephemerals:=host_ephemeral c :: unit_ephemeral c :: prior_ephemerals cache |}.
Definition accept_and_record cache c reply : option AdmissionCache :=
  if insert_unit cache c reply then Some (record_insertion cache c) else None.
Lemma eqb_self : forall n, Nat.eqb n n = true.
Proof. induction n; simpl; auto. Qed.
Theorem decided_insertion_cannot_reopen : forall cache c reply,
  insert_unit (record_insertion cache c) c reply = false.
Proof.
  intros. destruct reply as [r|]; try reflexivity.
  destruct (insert_unit (record_insertion cache c) c (Some r)) eqn:E; try reflexivity.
  pose proof (every_at _ 10 E) as H.
  cbn [bool_at insertion_checks record_insertion prior_nonces member] in H.
  rewrite eqb_self in H. discriminate.
Qed.

Inductive SocketState := Absent | Isolated | Detected | Reset |
  Authenticated | Active | Quiescing.
Definition transition (a b : SocketState) : bool :=
  match a, b with
  | Absent, Detected | Detected, Reset | Reset, Authenticated
  | Authenticated, Active | Active, Quiescing | Authenticated, Quiescing
  | Quiescing, Isolated | Active, Isolated | Detected, Isolated
  | Reset, Isolated | Authenticated, Isolated | Isolated, Absent
  | Isolated, Reset => true
  | _, _ => false
  end.
Inductive Operation := IdRecord | HsInit | HsReply | InfOpen | InfInput |
  InfDraw | InfAbort | InfOutput | InfEnd | MgmtQuiesce | MgmtQuiesceEnd |
  MgmtScrub | MgmtScrubEnd | Idle.
Definition admitting_state (op : Operation) (s : SocketState) : bool :=
  match op, s with
  | IdRecord, Reset | HsInit, Reset | HsReply, Reset
  | InfOpen, Active | InfInput, Active
  | InfDraw, Active | InfDraw, Quiescing
  | InfAbort, Active | InfAbort, Quiescing
  | InfOutput, Active | InfOutput, Quiescing
  | InfEnd, Active | InfEnd, Quiescing
  | MgmtQuiesce, Authenticated | MgmtQuiesce, Active
  | MgmtQuiesceEnd, Quiescing | MgmtScrub, Quiescing | MgmtScrubEnd, Quiescing
  | Idle, Authenticated | Idle, Active | Idle, Quiescing => true
  | _, _ => false
  end.
Record Grant := {
  grant_principal : nat; grant_endpoint : nat; grant_unit : nat;
  grant_design : nat; grant_model : nat; grant_inputs : list nat;
  grant_destination : nat; grant_operation : nat; grant_start : nat;
  grant_expiry : nat; grant_session : nat; grant_activation : nat
}.
Record Request := {
  request_principal : nat; request_input : nat; request_destination : nat;
  request_operation : nat; request_secret : bool; request_drawn : nat
}.
(* Consent is the host trusted-path decision for this exact grant and request,
   including revocation. There is no card-supplied approval field. *)
Definition grant_checks (c : SessionContext) (g : Grant) (q : Request)
    (now : nat) (consent : Grant -> Request -> bool) : list bool :=
  consent g q :: Nat.eqb (grant_principal g) (request_principal q) ::
  Nat.eqb (grant_endpoint g) (endpoint c) :: Nat.eqb (grant_unit g) (unit_key c) ::
  Nat.eqb (grant_design g) (design c) :: Nat.eqb (grant_model g) (model c) ::
  member (request_input q) (grant_inputs g) ::
  Nat.eqb (grant_destination g) (request_destination q) ::
  Nat.eqb (grant_operation g) (request_operation q) ::
  Nat.leb (grant_start g) now :: Nat.ltb now (grant_expiry g) ::
  Nat.eqb (grant_session g) (session_epoch c) ::
  Nat.eqb (grant_activation g) (activation_epoch c) :: negb (request_secret q) :: nil.
Definition route_allowed c (grant : option Grant) q now consent :=
  match grant with None => false | Some g => every (grant_checks c g q now consent) end.
Theorem route_has_consent : forall c g q now consent,
  route_allowed c (Some g) q now consent = true -> consent g q = true.
Proof. intros. exact (every_at _ 0 H). Qed.
Theorem route_binds_principal : forall c g q now consent,
  route_allowed c (Some g) q now consent = true -> grant_principal g = request_principal q.
Proof. intros. apply eqb_equal. exact (every_at _ 1 H). Qed.
Theorem route_excludes_secrets : forall c g q now consent,
  route_allowed c (Some g) q now consent = true -> request_secret q = false.
Proof.
  intros. pose proof (every_at _ 13 H) as E.
  change (negb (request_secret q) = true) in E.
  destruct (request_secret q); simpl in E; try discriminate; reflexivity.
Qed.

Record Composition := {
  host_memory : list nat; host_capabilities : list nat; host_schedule : list nat;
  endpoint_objects : list nat; output_ceiling : nat; per_frame_ceiling : nat;
  fixed_frame_bytes : nat; management_ceiling : nat
}.
Record HostState := {
  composition : Composition; socket_state : SocketState; current_context : SessionContext;
  host_grant : option Grant; outstanding : option Request;
  next_sequence : nat; output_used : nat; host_slot : nat; host_now : nat;
  mover_barrier_complete : bool
}.
Record Frame := {
  frame_operation : Operation; frame_session : nat; frame_activation : nat;
  frame_sequence : nat; frame_slot : nat; frame_count : nat; frame_bytes : nat;
  frame_payload : list nat; forbidden_destination : option nat
}.
(* Successful crypto validation yields this typed frame. None represents silence
   or authentication/parse failure. An arbitrary dishonest authenticated card can
   supply every Frame value; all guards below still apply. *)
Definition frame_checks (s : HostState) (f : Frame) : list bool :=
  admitting_state (frame_operation f) (socket_state s) ::
  (match frame_operation f with InfOutput => true | _ => false end) ::
  Nat.eqb (frame_session f) (session_epoch (current_context s)) ::
  Nat.eqb (frame_activation f) (activation_epoch (current_context s)) ::
  Nat.eqb (frame_sequence f) (next_sequence s) ::
  Nat.eqb (frame_slot f) (host_slot s) ::
  Nat.eqb (frame_bytes f) (fixed_frame_bytes (composition s)) ::
  Nat.eqb (frame_count f) (count (frame_payload f)) ::
  Nat.leb (frame_count f) (per_frame_ceiling (composition s)) ::
  Nat.leb (output_used s + frame_count f) (output_ceiling (composition s)) ::
  (match forbidden_destination f with None => true | Some _ => false end) ::
  below 256 (frame_payload f) :: nil.
Definition deliverable (s : HostState) (f : Frame) consent :=
  match outstanding s with
  | None => false
  | Some q => andb (route_allowed (current_context s) (host_grant s) q (host_now s) consent)
      (andb (member (request_destination q) (endpoint_objects (composition s)))
            (andb (Nat.leb (frame_count f) (request_drawn q)) (every (frame_checks s f))))
  end.
Inductive Effect := NoDelivery | Proposal (destination : nat) (payload : list nat).
Definition receive (s : HostState) (wire : option Frame) consent : Effect :=
  match wire, outstanding s with
  | Some f, Some q => if deliverable s f consent
      then Proposal (request_destination q) (frame_payload f) else NoDelivery
  | _, _ => NoDelivery
  end.
Definition fail_stop (s : HostState) : HostState :=
  {| composition := composition s; socket_state := Isolated;
     current_context := current_context s; host_grant := None; outstanding := None;
     next_sequence := next_sequence s; output_used := output_used s;
     host_slot := host_slot s; host_now := host_now s;
     mover_barrier_complete := mover_barrier_complete s |}.
Definition finish_output (s : HostState) (f : Frame) : HostState :=
  {| composition := composition s; socket_state := socket_state s;
     current_context := current_context s; host_grant := host_grant s;
     outstanding := None; next_sequence := S (next_sequence s);
     output_used := output_used s + frame_count f;
     host_slot := host_slot s; host_now := host_now s;
     mover_barrier_complete := mover_barrier_complete s |}.
Definition disable_route (s : HostState) : HostState :=
  {| composition := composition s; socket_state := socket_state s;
     current_context := current_context s; host_grant := None; outstanding := None;
     next_sequence := next_sequence s; output_used := output_used s;
     host_slot := host_slot s; host_now := host_now s;
     mover_barrier_complete := mover_barrier_complete s |}.
Definition socket_step (s : HostState) (wire : option Frame) consent : HostState :=
  match wire with
  | None => fail_stop s
  | Some f => if every (frame_checks s f) then
      match outstanding s with
      | None => fail_stop s
      | Some q => if route_allowed (current_context s) (host_grant s) q (host_now s) consent
          then if deliverable s f consent then finish_output s f else fail_stop s
          else disable_route s
      end
      else fail_stop s
  end.
Fixpoint run_frames (s : HostState) (frames : list (option Frame)) consent : HostState :=
  match frames with nil => s | f :: rest => run_frames (socket_step s f consent) rest consent end.
Theorem arbitrary_card_preserves_composition : forall s wire consent,
  composition (socket_step s wire consent) = composition s.
Proof.
  intros. unfold socket_step. destruct wire as [f|]; try reflexivity.
  destruct (every (frame_checks s f)); try reflexivity.
  destruct (outstanding s) as [q|]; try reflexivity.
  destruct (route_allowed (current_context s) (host_grant s) q (host_now s) consent); try reflexivity.
  destruct (deliverable s f consent); reflexivity.
Qed.
Theorem arbitrary_trace_preserves_host_authority : forall frames s consent,
  composition (run_frames s frames consent) = composition s.
Proof.
  induction frames as [|f rest IH]; intros; simpl; auto.
  rewrite IH. apply arbitrary_card_preserves_composition.
Qed.
Theorem delivery_uses_host_destination : forall s wire consent dest payload,
  receive s wire consent = Proposal dest payload ->
  exists q, outstanding s = Some q /\ dest = request_destination q.
Proof.
  intros s wire consent dest payload H. unfold receive in H.
  destruct wire as [f|]; destruct (outstanding s) as [q|] eqn:E; try discriminate.
  destruct (deliverable s f consent); inversion H; subst.
  exists q. split; reflexivity.
Qed.
Theorem replacement_inherits_no_grant : forall s,
  host_grant (fail_stop s) = None /\ outstanding (fail_stop s) = None.
Proof. intros; split; reflexivity. Qed.
Theorem isolated_route_never_delivers : forall s wire consent,
  receive (fail_stop s) wire consent = NoDelivery.
Proof. intros. destruct wire; reflexivity. Qed.
Theorem delivery_respects_all_frame_guards : forall s f consent n,
  deliverable s f consent = true -> bool_at n (frame_checks s f) = true.
Proof.
  intros s f consent n H. unfold deliverable in H.
  destruct (outstanding s); try discriminate.
  apply andb_split in H. destruct H as [_ H].
  apply andb_split in H. destruct H as [_ H].
  apply andb_split in H. destruct H as [_ H].
  exact (every_at _ n H).
Qed.
Theorem delivery_cannot_extend_quota : forall s f consent,
  deliverable s f consent = true ->
  Nat.leb (output_used s + frame_count f) (output_ceiling (composition s)) = true.
Proof. intros. exact (delivery_respects_all_frame_guards _ _ _ 9 H). Qed.
Theorem delivery_is_only_output : forall s f consent,
  deliverable s f consent = true -> frame_operation f = InfOutput.
Proof.
  intros. pose proof (delivery_respects_all_frame_guards _ _ _ 1 H) as E.
  cbn [bool_at frame_checks] in E.
  destruct (frame_operation f); try discriminate; reflexivity.
Qed.
Theorem output_charges_exact_count : forall s f,
  output_used (finish_output s f) = output_used s + frame_count f.
Proof. reflexivity. Qed.
Theorem delivery_cannot_name_address : forall s f consent,
  deliverable s f consent = true -> forbidden_destination f = None.
Proof.
  intros. pose proof (delivery_respects_all_frame_guards _ _ _ 10 H) as E.
  cbn [bool_at frame_checks] in E.
  destruct (forbidden_destination f); try discriminate; reflexivity.
Qed.
Definition reclaim_buffers (s : HostState) : bool :=
  match socket_state s with Isolated => mover_barrier_complete s | _ => false end.
Theorem reclamation_requires_host_barrier : forall s,
  reclaim_buffers s = true -> mover_barrier_complete s = true.
Proof. intros s H. unfold reclaim_buffers in H. destruct (socket_state s); try discriminate; exact H. Qed.

(* Closed witnesses and boundary cases. *)
Definition manifest_fixture : Manifest :=
  {| graph_id:=1; weights_id:=2; arithmetic_id:=3; tokenizer_id:=4;
     vocabulary_id:=5; circuit_id:=6; implementation_id:=7; schema_id:=8;
     protocol_id:=9; footprint_id:=10; envelope_id:=11; propositions_id:=12 |}.
Definition bounds_fixture : Bounds :=
  {| evidence_bytes:=4; checking_fuel:=10; scratch_bytes:=20;
     verdict_ticks:=30; identifier_bound:=32 |}.
Definition kernel_fixture (assumptions bytes : list nat) (fuel scratch ticks : nat) : KernelReceipt :=
  {| checked_subject:=identity manifest_fixture; checked_evidence:=bytes;
     checked_assumptions:=assumptions; checked_checker:=1; checked_profile:=2;
     spent_fuel:=fuel; spent_scratch:=scratch; spent_ticks:=ticks |}.
Definition kernel_witness : KernelReceipt := kernel_fixture nil (1::2::nil) 10 20 30.
Definition design_fixture bytes r := admit_design bounds_fixture manifest_fixture
  manifest_fixture bytes nil 1 2 r.
Example positive_design : design_fixture (1::2::nil) kernel_witness = true.
Proof. reflexivity. Qed.
Example positive_minimum_certificate : design_fixture (1::nil)
  (kernel_fixture nil (1::nil) 10 20 30) = true.
Proof. reflexivity. Qed.
Example positive_maximum_certificate : design_fixture (1::2::3::4::nil)
  (kernel_fixture nil (1::2::3::4::nil) 10 20 30) = true.
Proof. reflexivity. Qed.
Example empty_certificate_refused : design_fixture nil
  (kernel_fixture nil nil 10 20 30) = false.
Proof. reflexivity. Qed.
Example added_axiom_refused : design_fixture (1::2::nil)
  (kernel_fixture (99::nil) (1::2::nil) 10 20 30) = false.
Proof. reflexivity. Qed.
Example oversized_certificate_refused : design_fixture (1::2::3::4::5::nil)
  (kernel_fixture nil (1::2::3::4::5::nil) 10 20 30) = false.
Proof. reflexivity. Qed.
Example malformed_certificate_refused : design_fixture (256::nil)
  (kernel_fixture nil (256::nil) 10 20 30) = false.
Proof. reflexivity. Qed.
Example excessive_checker_fuel_refused : design_fixture (1::2::nil)
  (kernel_fixture nil (1::2::nil) 11 20 30) = false.
Proof. reflexivity. Qed.
Example excessive_checker_scratch_refused : design_fixture (1::2::nil)
  (kernel_fixture nil (1::2::nil) 10 21 30) = false.
Proof. reflexivity. Qed.
Example excessive_verdict_latency_refused : design_fixture (1::2::nil)
  (kernel_fixture nil (1::2::nil) 10 20 31) = false.
Proof. reflexivity. Qed.
Example wrong_evidence_receipt_refused : design_fixture (1::3::nil) kernel_witness = false.
Proof. reflexivity. Qed.
Example wrong_checker_refused : admit_design bounds_fixture manifest_fixture
  manifest_fixture (1::2::nil) nil 9 2 kernel_witness = false.
Proof. reflexivity. Qed.
Example wrong_profile_refused : admit_design bounds_fixture manifest_fixture
  manifest_fixture (1::2::nil) nil 1 9 kernel_witness = false.
Proof. reflexivity. Qed.
Definition different_model_manifest : Manifest :=
  {| graph_id:=2; weights_id:=2; arithmetic_id:=3; tokenizer_id:=4;
     vocabulary_id:=5; circuit_id:=6; implementation_id:=7; schema_id:=8;
     protocol_id:=9; footprint_id:=10; envelope_id:=11; propositions_id:=12 |}.
Example different_manifest_refused : admit_design bounds_fixture manifest_fixture
  different_model_manifest (1::2::nil) nil 1 2 kernel_witness = false.
Proof. reflexivity. Qed.

Definition context_fixture (key d m ep sn hn un he ue : nat) : SessionContext :=
  {| host_role:=1; unit_role:=2; endpoint:=3; unit_key:=key; design:=d; model:=m;
     generation_policy:=7; schedule:=8; activation_epoch:=ep; session_epoch:=sn;
     suite:=11; protocol:=12; host_nonce:=hn; unit_nonce:=un;
     host_ephemeral:=he; unit_ephemeral:=ue |}.
Definition context_witness : SessionContext := context_fixture 4 5 6 9 10 13 14 15 16.
Definition cache_fixture nonces ephemerals : AdmissionCache :=
  {| cached_design:=5; cached_model:=6; admitted_units:=4::44::nil;
     production_lifecycle:=1; design_checked:=true;
     prior_nonces:=nonces; prior_ephemerals:=ephemerals |}.
Definition cache_witness : AdmissionCache := cache_fixture (1::2::nil) (3::4::nil).
Definition reply_fixture c key d m : AuthenticatedReply :=
  {| issued_context:=c; actual_signing_key:=key; endorsed_design:=d;
     endorsed_model:=m; endorsed_lifecycle:=1 |}.
Definition reply_witness : AuthenticatedReply := reply_fixture context_witness 4 5 6.
Example positive_insertion : insert_unit cache_witness context_witness (Some reply_witness) = true.
Proof. reflexivity. Qed.
Example positive_insertion_records_freshness : accept_and_record cache_witness context_witness
  (Some reply_witness) = Some (record_insertion cache_witness context_witness).
Proof. reflexivity. Qed.
Example copied_key_name_refused : insert_unit cache_witness context_witness
  (Some (reply_fixture context_witness 44 5 6)) = false.
Proof. reflexivity. Qed.
Example foreign_unit_refused : let c := context_fixture 99 5 6 9 10 13 14 15 16 in
  insert_unit cache_witness c (Some (reply_fixture c 99 5 6)) = false.
Proof. reflexivity. Qed.
Example foreign_circuit_endorsement_refused : insert_unit cache_witness context_witness
  (Some (reply_fixture context_witness 4 55 6)) = false.
Proof. reflexivity. Qed.
Example wrong_model_with_same_unit_refused : let c := context_fixture 4 5 66 9 10 13 14 15 16 in
  insert_unit cache_witness c (Some (reply_fixture c 4 5 66)) = false.
Proof. reflexivity. Qed.
Example wrong_design_with_same_unit_refused : let c := context_fixture 4 55 6 9 10 13 14 15 16 in
  insert_unit cache_witness c (Some (reply_fixture c 4 55 6)) = false.
Proof. reflexivity. Qed.
Example cross_session_refused : insert_unit cache_witness
  (context_fixture 4 5 6 9 11 13 14 15 16) (Some reply_witness) = false.
Proof. reflexivity. Qed.
Example replayed_challenge_refused : insert_unit
  (cache_fixture (13::nil) nil) context_witness (Some reply_witness) = false.
Proof. reflexivity. Qed.
Example reset_ephemeral_reuse_refused : insert_unit
  (cache_fixture nil (16::nil)) context_witness (Some reply_witness) = false.
Proof. reflexivity. Qed.
Example reset_unit_nonce_reuse_refused : insert_unit
  (cache_fixture (14::nil) nil) context_witness (Some reply_witness) = false.
Proof. reflexivity. Qed.
Example reset_host_ephemeral_reuse_refused : insert_unit
  (cache_fixture nil (15::nil)) context_witness (Some reply_witness) = false.
Proof. reflexivity. Qed.

Definition grant_fixture principal dest start expiry session activation : Grant :=
  {| grant_principal:=principal; grant_endpoint:=3; grant_unit:=4;
     grant_design:=5; grant_model:=6; grant_inputs:=20::nil;
     grant_destination:=dest; grant_operation:=1; grant_start:=start;
     grant_expiry:=expiry; grant_session:=session; grant_activation:=activation |}.
Definition grant_witness : Grant := grant_fixture 19 21 1 10 10 9.
Definition request_fixture principal input dest operation secret : Request :=
  {| request_principal:=principal; request_input:=input; request_destination:=dest;
     request_operation:=operation; request_secret:=secret; request_drawn:=2 |}.
Definition request_witness : Request := request_fixture 19 20 21 1 false.
Definition consent_yes (_ : Grant) (_ : Request) := true.
Definition consent_no (_ : Grant) (_ : Request) := false.
Example positive_grant : route_allowed context_witness (Some grant_witness)
  request_witness 5 consent_yes = true.
Proof. reflexivity. Qed.
Example grant_start_equality_accepted : route_allowed context_witness (Some grant_witness)
  request_witness 1 consent_yes = true.
Proof. reflexivity. Qed.
Example missing_grant_refused : route_allowed context_witness None request_witness 5 consent_yes = false.
Proof. reflexivity. Qed.
Example revoked_consent_refused : route_allowed context_witness (Some grant_witness)
  request_witness 5 consent_no = false.
Proof. reflexivity. Qed.
Example cross_client_refused : route_allowed context_witness (Some grant_witness)
  (request_fixture 99 20 21 1 false) 5 consent_yes = false.
Proof. reflexivity. Qed.
Example wrong_input_refused : route_allowed context_witness (Some grant_witness)
  (request_fixture 19 99 21 1 false) 5 consent_yes = false.
Proof. reflexivity. Qed.
Example redirected_output_refused : route_allowed context_witness (Some grant_witness)
  (request_fixture 19 20 99 1 false) 5 consent_yes = false.
Proof. reflexivity. Qed.
Example widened_operation_refused : route_allowed context_witness (Some grant_witness)
  (request_fixture 19 20 21 99 false) 5 consent_yes = false.
Proof. reflexivity. Qed.
Example secret_input_refused : route_allowed context_witness (Some grant_witness)
  (request_fixture 19 20 21 1 true) 5 consent_yes = false.
Proof. reflexivity. Qed.
Example premature_grant_refused : route_allowed context_witness (Some grant_witness)
  request_witness 0 consent_yes = false.
Proof. reflexivity. Qed.
Example deadline_equality_refused : route_allowed context_witness (Some grant_witness)
  request_witness 10 consent_yes = false.
Proof. reflexivity. Qed.
Example replacement_grant_refused : route_allowed
  (context_fixture 44 5 6 10 11 17 18 19 20) (Some grant_witness)
  request_witness 5 consent_yes = false.
Proof. reflexivity. Qed.

Definition composition_witness : Composition :=
  {| host_memory:=1::2::nil; host_capabilities:=3::nil; host_schedule:=4::5::nil;
     endpoint_objects:=21::nil; output_ceiling:=4; per_frame_ceiling:=2;
     fixed_frame_bytes:=32; management_ceiling:=3 |}.
Definition state_fixture grant request state barrier : HostState :=
  {| composition:=composition_witness; socket_state:=state; current_context:=context_witness;
     host_grant:=grant; outstanding:=request; next_sequence:=0; output_used:=2;
     host_slot:=10; host_now:=5; mover_barrier_complete:=barrier |}.
Definition state_witness : HostState := state_fixture (Some grant_witness) (Some request_witness) Active false.
Definition frame_fixture sn ep seq slot count bytes payload dest : Frame :=
  {| frame_operation:=InfOutput; frame_session:=sn; frame_activation:=ep;
     frame_sequence:=seq; frame_slot:=slot; frame_count:=count; frame_bytes:=bytes;
     frame_payload:=payload; forbidden_destination:=dest |}.
Definition frame_witness : Frame := frame_fixture 10 9 0 10 2 32 (7::8::nil) None.
Example positive_delivery : receive state_witness (Some frame_witness) consent_yes =
  Proposal 21 (7::8::nil).
Proof. reflexivity. Qed.
Example address_injection_refused : receive state_witness
  (Some (frame_fixture 10 9 0 10 2 32 (7::8::nil) (Some 99))) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example wrong_slot_refused : receive state_witness
  (Some (frame_fixture 10 9 0 11 2 32 (7::8::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example stale_result_refused : receive state_witness
  (Some (frame_fixture 9 9 0 10 2 32 (7::8::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example quota_extension_refused : receive state_witness
  (Some (frame_fixture 10 9 0 10 3 32 (7::8::9::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example stale_activation_refused : receive state_witness
  (Some (frame_fixture 10 8 0 10 2 32 (7::8::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example wrong_sequence_refused : receive state_witness
  (Some (frame_fixture 10 9 1 10 2 32 (7::8::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example malformed_frame_bytes_refused : receive state_witness
  (Some (frame_fixture 10 9 0 10 2 31 (7::8::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example inconsistent_payload_count_refused : receive state_witness
  (Some (frame_fixture 10 9 0 10 1 32 (7::8::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example out_of_range_payload_refused : receive state_witness
  (Some (frame_fixture 10 9 0 10 2 32 (256::8::nil) None)) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example second_delivery_refused : receive
  (socket_step state_witness (Some frame_witness) consent_yes)
  (Some frame_witness) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example missing_authentication_refused : receive state_witness None consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example broker_consent_failure_preserves_session : socket_state
  (socket_step state_witness (Some frame_witness) consent_no) = Active.
Proof. reflexivity. Qed.
Example replacement_late_result_refused : receive (fail_stop state_witness)
  (Some frame_witness) consent_yes = NoDelivery.
Proof. reflexivity. Qed.
Example premature_reclamation_refused : reclaim_buffers (fail_stop state_witness) = false.
Proof. reflexivity. Qed.
Example completed_host_barrier_allows_reclamation : reclaim_buffers
  (state_fixture None None Isolated true) = true.
Proof. reflexivity. Qed.
Example cannot_skip_authentication : transition Reset Active = false.
Proof. reflexivity. Qed.
Example no_quiescence_resume : transition Quiescing Active = false.
Proof. reflexivity. Qed.

Definition witness_Manifest : Manifest := manifest_fixture.
Definition witness_Bounds : Bounds := bounds_fixture.
Definition witness_KernelReceipt : KernelReceipt := kernel_witness.
Definition witness_SessionContext : SessionContext := context_witness.
Definition witness_AuthenticatedReply : AuthenticatedReply := reply_witness.
Definition witness_AdmissionCache : AdmissionCache := cache_witness.
Definition witness_Grant : Grant := grant_witness.
Definition witness_Request : Request := request_witness.
Definition witness_Composition : Composition := composition_witness.
Definition witness_HostState : HostState := state_witness.
Definition witness_Frame : Frame := frame_witness.
