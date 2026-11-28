(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ReplayRecord.v

   Machine-checked specification and non-vacuity evidence for the §16
   deterministic-replay nondeterminism record (R-15-241, R-16-013,
   R-16-015 through R-16-023).

   What this module formalizes:
   1. The closed four-source set (R-16-015) and fixed source-determined
      classification: secret entropy root draws are represented strictly as
      opaque sealed commitments (R-15-241, R-16-017) never recoverable from the
      record (R-16-020), while link-layer addresses, time-service reads, and
      physical events are recorded verbatim (R-16-016) and never selectable by
      the caller.
   2. Strictly monotonic logical ordering coordinates `(slot, core, retire,
      ordinal)`, per-core non-regressing `retire`, and contiguous 0-based `seq`
      indices across every recorded event (R-15-241, R-16-015).
   3. Pre-invocation worst-case capacity reservation: maximum payload plus
      framing is reserved before invoking any side-effectful producer, unused
      margin is released only after an accepted event (or declined draw), and
      capacity exhaustion refuses before consumption and routes to the terminal
      fault path without evicting, wrapping, or losing draws (R-16-023).
   4. Sticky failure latching and reentrancy refusal: any refusal, invalid
      result, or reentrant call permanently latches the recorder failed so an
      uncertain prefix can never be finalized (R-16-013, R-16-023).
   5. Independent expected binding `(base_image_root, composition, input_trace)`
      and independent expected event count verification (R-16-013, R-16-022).
   6. Strict demand-cursor replay semantics matching `(point, source, interface)`
      at each boundary, refusing exhaustion and trailing events, proving
      non-recoverability of secret draws from commitments (R-16-017, R-16-020),
      and proving CT-scope deterministic replay equivalence under substituted
      secret entropy while distinguishing draw-dependent faults (R-16-018,
      R-16-019, R-16-021, R-16-022).

   Assumptions and non-vacuity (R-05-163, R-05-164, R-05-165, R-05-166):
   This module depends only on `ProofSupport` (prelude-only), introduces no
   axioms, parameters, or admitted terms, provides a closed `witness_<R>`
   inhabitant for every quantified `Record`, an inhabited four-source capture
   and replay witness, and explicit computed refutations for each violation.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-15-241 R-16-013 R-16-015 R-16-016
      R-16-017 R-16-018 R-16-019 R-16-020 R-16-021 R-16-022 R-16-023
   SHA256: 31324ee2f1ce9ecbcfa1d5c2e4b45367b1da0d04ec7c3c4930a27afeddb59304
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport.
Import ProofSupport.Tactics.
Open Scope list_scope.

(* =========================================================================
   Part 1. Closed four-source set and fixed payload classification.
   ========================================================================= *)

Inductive Source : Type :=
| SrcEntropy : Source
| SrcLinkAddress : Source
| SrcTimeRead : Source
| SrcPhysicalEvent : Source.

Definition source_eqb (a b : Source) : bool :=
  match a, b with
  | SrcEntropy, SrcEntropy => true
  | SrcLinkAddress, SrcLinkAddress => true
  | SrcTimeRead, SrcTimeRead => true
  | SrcPhysicalEvent, SrcPhysicalEvent => true
  | _, _ => false
  end.

Lemma source_eqb_refl : forall s : Source, source_eqb s s = true.
Proof. intros [| | |]; reflexivity. Qed.

Lemma source_eqb_true : forall a b : Source, source_eqb a b = true -> a = b.
Proof.
  intros [| | |] [| | |] H; try discriminate H; reflexivity.
Qed.

Inductive PayloadClass : Type :=
| SecretCommitment : PayloadClass
| PublicVerbatim : PayloadClass.

Definition payload_class_eqb (a b : PayloadClass) : bool :=
  match a, b with
  | SecretCommitment, SecretCommitment => true
  | PublicVerbatim, PublicVerbatim => true
  | _, _ => false
  end.

Definition source_class (s : Source) : PayloadClass :=
  match s with
  | SrcEntropy => SecretCommitment
  | SrcLinkAddress => PublicVerbatim
  | SrcTimeRead => PublicVerbatim
  | SrcPhysicalEvent => PublicVerbatim
  end.

Definition source_is_public (s : Source) : bool :=
  match s with
  | SrcEntropy => false
  | _ => true
  end.

Inductive Payload : Type :=
| PayCommitment : list nat -> Payload
| PayPublic : list nat -> Payload.

Definition payload_class (p : Payload) : PayloadClass :=
  match p with
  | PayCommitment _ => SecretCommitment
  | PayPublic _ => PublicVerbatim
  end.

Definition payload_bytes (p : Payload) : list nat :=
  match p with
  | PayCommitment bs => bs
  | PayPublic bs => bs
  end.

Definition payload_eqb (a b : Payload) : bool :=
  match a, b with
  | PayCommitment x, PayCommitment y => ProofSupport.list_eqb Nat.eqb x y
  | PayPublic x, PayPublic y => ProofSupport.list_eqb Nat.eqb x y
  | _, _ => false
  end.

Theorem closed_four_sources : forall s : Source,
  s = SrcEntropy \/ s = SrcLinkAddress \/ s = SrcTimeRead \/ s = SrcPhysicalEvent.
Proof.
  intros [| | |].
  - left. reflexivity.
  - right. left. reflexivity.
  - right. right. left. reflexivity.
  - right. right. right. reflexivity.
Qed.

(*| discharges: R-15-241, R-16-015, R-16-016, R-16-017 |*)
Theorem source_class_secret_iff_entropy : forall s : Source,
  source_class s = SecretCommitment <-> s = SrcEntropy.
Proof.
  intros [| | |]; split; intro H; try reflexivity; discriminate H.
Qed.

Theorem source_class_public_iff_not_entropy : forall s : Source,
  source_class s = PublicVerbatim <-> s <> SrcEntropy.
Proof.
  intros [| | |]; split; intro H.
  - discriminate H.
  - contradiction H. reflexivity.
  - intro E. discriminate E.
  - reflexivity.
  - intro E. discriminate E.
  - reflexivity.
  - intro E. discriminate E.
  - reflexivity.
Qed.

(* =========================================================================
   Part 2. Coordinates, bindings, interface profiles, events, and limits.
   ========================================================================= *)

Record Point : Type := {
  pt_slot : nat;
  pt_core : nat;
  pt_retire : nat;
  pt_ordinal : nat
}.

Definition witness_Point : Point :=
  {| pt_slot := 0; pt_core := 0; pt_retire := 0; pt_ordinal := 0 |}.

Definition point_eqb (a b : Point) : bool :=
  andb (Nat.eqb (pt_slot a) (pt_slot b))
    (andb (Nat.eqb (pt_core a) (pt_core b))
      (andb (Nat.eqb (pt_retire a) (pt_retire b))
            (Nat.eqb (pt_ordinal a) (pt_ordinal b)))).

Lemma point_eqb_refl : forall p : Point, point_eqb p p = true.
Proof.
  intros [s c r o]. unfold point_eqb. simpl.
  rewrite (ProofSupport.nat_eqb_refl s), (ProofSupport.nat_eqb_refl c),
          (ProofSupport.nat_eqb_refl r), (ProofSupport.nat_eqb_refl o).
  reflexivity.
Qed.

Lemma point_eqb_true : forall a b : Point, point_eqb a b = true -> a = b.
Proof.
  intros [s1 c1 r1 o1] [s2 c2 r2 o2] H. unfold point_eqb in H. simpl in H.
  destruct (ProofSupport.andb_split _ _ H) as [Hs H1].
  destruct (ProofSupport.andb_split _ _ H1) as [Hc H2].
  destruct (ProofSupport.andb_split _ _ H2) as [Hr Ho].
  rewrite (ProofSupport.nat_eqb_true _ _ Hs),
          (ProofSupport.nat_eqb_true _ _ Hc),
          (ProofSupport.nat_eqb_true _ _ Hr),
          (ProofSupport.nat_eqb_true _ _ Ho).
  reflexivity.
Qed.

Definition point_lt (a b : Point) : bool :=
  if Nat.ltb (pt_slot a) (pt_slot b) then true
  else if negb (Nat.eqb (pt_slot a) (pt_slot b)) then false
  else if Nat.ltb (pt_core a) (pt_core b) then true
  else if negb (Nat.eqb (pt_core a) (pt_core b)) then false
  else if Nat.ltb (pt_retire a) (pt_retire b) then true
  else if negb (Nat.eqb (pt_retire a) (pt_retire b)) then false
  else Nat.ltb (pt_ordinal a) (pt_ordinal b).

Lemma nat_ltb_irrefl : forall n : nat, Nat.ltb n n = false.
Proof.
  induction n as [|k IH]; [reflexivity | exact IH].
Qed.

Lemma nat_ltb_asym : forall a b : nat,
  Nat.ltb a b = true -> Nat.ltb b a = false.
Proof.
  induction a as [|x IH]; intros [|y] H; try discriminate H; try reflexivity.
  simpl in *. exact (IH y H).
Qed.

Lemma nat_ltb_trans : forall a b c : nat,
  Nat.ltb a b = true -> Nat.ltb b c = true -> Nat.ltb a c = true.
Proof.
  intros a b c Hab Hbc.
  exact (ProofSupport.nat_leb_trans (S a) (S b) c
           (ProofSupport.nat_leb_succ_r (S a) b Hab) Hbc).
Qed.

Lemma nat_ltb_not_eq : forall a b : nat,
  Nat.ltb a b = true -> Nat.eqb a b = false.
Proof.
  induction a as [|x IH]; intros [|y] H; try discriminate H; try reflexivity.
  simpl in *. exact (IH y H).
Qed.

Lemma point_lt_irrefl : forall p : Point, point_lt p p = false.
Proof.
  intros [s c r o]. unfold point_lt. simpl.
  rewrite (nat_ltb_irrefl s), (ProofSupport.nat_eqb_refl s),
          (nat_ltb_irrefl c), (ProofSupport.nat_eqb_refl c),
          (nat_ltb_irrefl r), (ProofSupport.nat_eqb_refl r),
          (nat_ltb_irrefl o).
  reflexivity.
Qed.

Lemma point_lt_asym : forall a b : Point,
  point_lt a b = true -> point_lt b a = false.
Proof.
  intros [s1 c1 r1 o1] [s2 c2 r2 o2] H. unfold point_lt in *. simpl in *.
  destruct (Nat.ltb s1 s2) eqn:Es.
  - rewrite (nat_ltb_asym s1 s2 Es).
    rewrite ProofSupport.nat_eqb_sym, (nat_ltb_not_eq s1 s2 Es). reflexivity.
  - destruct (Nat.eqb s1 s2) eqn:Eseq; [|discriminate H].
    rewrite (ProofSupport.nat_eqb_true _ _ Eseq) in *.
    rewrite (nat_ltb_irrefl s2), (ProofSupport.nat_eqb_refl s2). simpl.
    destruct (Nat.ltb c1 c2) eqn:Ec.
    + rewrite (nat_ltb_asym c1 c2 Ec).
      rewrite ProofSupport.nat_eqb_sym, (nat_ltb_not_eq c1 c2 Ec). reflexivity.
    + destruct (Nat.eqb c1 c2) eqn:Eceq; [|discriminate H].
      rewrite (ProofSupport.nat_eqb_true _ _ Eceq) in *.
      rewrite (nat_ltb_irrefl c2), (ProofSupport.nat_eqb_refl c2). simpl.
      destruct (Nat.ltb r1 r2) eqn:Er.
      * rewrite (nat_ltb_asym r1 r2 Er).
        rewrite ProofSupport.nat_eqb_sym, (nat_ltb_not_eq r1 r2 Er). reflexivity.
      * destruct (Nat.eqb r1 r2) eqn:Ereq; [|discriminate H].
        rewrite (ProofSupport.nat_eqb_true _ _ Ereq) in *.
        rewrite (nat_ltb_irrefl r2), (ProofSupport.nat_eqb_refl r2). simpl.
        exact (nat_ltb_asym o1 o2 H).
Qed.

Lemma point_lt_trans : forall a b c : Point,
  point_lt a b = true -> point_lt b c = true -> point_lt a c = true.
Proof.
  intros [s1 c1 r1 o1] [s2 c2 r2 o2] [s3 c3 r3 o3] Hab Hbc.
  unfold point_lt in *. simpl in *.
  destruct (Nat.ltb s1 s2) eqn:Es12.
  - destruct (Nat.ltb s2 s3) eqn:Es23.
    + rewrite (nat_ltb_trans s1 s2 s3 Es12 Es23). reflexivity.
    + destruct (Nat.eqb s2 s3) eqn:Ese23; [|discriminate Hbc].
      rewrite (ProofSupport.nat_eqb_true _ _ Ese23) in *.
      rewrite Es12. reflexivity.
  - destruct (Nat.eqb s1 s2) eqn:Ese12; [|discriminate Hab].
    rewrite (ProofSupport.nat_eqb_true _ _ Ese12) in *.
    destruct (Nat.ltb s2 s3) eqn:Es23; [reflexivity|].
    destruct (Nat.eqb s2 s3) eqn:Ese23; [|discriminate Hbc].
    rewrite (ProofSupport.nat_eqb_true _ _ Ese23) in *.
    simpl in *.
    destruct (Nat.ltb c1 c2) eqn:Ec12.
    + destruct (Nat.ltb c2 c3) eqn:Ec23.
      * rewrite (nat_ltb_trans c1 c2 c3 Ec12 Ec23). reflexivity.
      * destruct (Nat.eqb c2 c3) eqn:Ece23; [|discriminate Hbc].
        rewrite (ProofSupport.nat_eqb_true _ _ Ece23) in *.
        rewrite Ec12. reflexivity.
    + destruct (Nat.eqb c1 c2) eqn:Ece12; [|discriminate Hab].
      rewrite (ProofSupport.nat_eqb_true _ _ Ece12) in *.
      destruct (Nat.ltb c2 c3) eqn:Ec23; [reflexivity|].
      destruct (Nat.eqb c2 c3) eqn:Ece23; [|discriminate Hbc].
      rewrite (ProofSupport.nat_eqb_true _ _ Ece23) in *.
      simpl in *.
      destruct (Nat.ltb r1 r2) eqn:Er12.
      * destruct (Nat.ltb r2 r3) eqn:Er23.
        -- rewrite (nat_ltb_trans r1 r2 r3 Er12 Er23). reflexivity.
        -- destruct (Nat.eqb r2 r3) eqn:Ere23; [|discriminate Hbc].
           rewrite (ProofSupport.nat_eqb_true _ _ Ere23) in *.
           rewrite Er12. reflexivity.
      * destruct (Nat.eqb r1 r2) eqn:Ere12; [|discriminate Hab].
        rewrite (ProofSupport.nat_eqb_true _ _ Ere12) in *.
        destruct (Nat.ltb r2 r3) eqn:Er23; [reflexivity|].
        destruct (Nat.eqb r2 r3) eqn:Ere23; [|discriminate Hbc].
        rewrite (ProofSupport.nat_eqb_true _ _ Ere23) in *.
        simpl in *.
        exact (nat_ltb_trans o1 o2 o3 Hab Hbc).
Qed.

Record Binding : Type := {
  bind_base_image_root : nat;
  bind_composition : nat;
  bind_input_trace : nat
}.

Definition witness_Binding : Binding :=
  {| bind_base_image_root := 1; bind_composition := 2; bind_input_trace := 3 |}.

Definition binding_eqb (a b : Binding) : bool :=
  andb (Nat.eqb (bind_base_image_root a) (bind_base_image_root b))
    (andb (Nat.eqb (bind_composition a) (bind_composition b))
          (Nat.eqb (bind_input_trace a) (bind_input_trace b))).

Lemma binding_eqb_refl : forall b : Binding, binding_eqb b b = true.
Proof.
  intros [r c t]. unfold binding_eqb. simpl.
  rewrite (ProofSupport.nat_eqb_refl r), (ProofSupport.nat_eqb_refl c),
          (ProofSupport.nat_eqb_refl t).
  reflexivity.
Qed.

Lemma binding_eqb_true : forall a b : Binding, binding_eqb a b = true -> a = b.
Proof.
  intros [r1 c1 t1] [r2 c2 t2] H. unfold binding_eqb in H. simpl in H.
  destruct (ProofSupport.andb_split _ _ H) as [Hr H1].
  destruct (ProofSupport.andb_split _ _ H1) as [Hc Ht].
  rewrite (ProofSupport.nat_eqb_true _ _ Hr),
          (ProofSupport.nat_eqb_true _ _ Hc),
          (ProofSupport.nat_eqb_true _ _ Ht).
  reflexivity.
Qed.

Record Limits : Type := {
  lim_max_bytes : nat;
  lim_max_events : nat;
  lim_base_bytes : nat
}.

Definition witness_Limits : Limits :=
  {| lim_max_bytes := 1024; lim_max_events := 8; lim_base_bytes := 80 |}.

Record InterfaceProfile : Type := {
  if_id : nat;
  if_source : Source;
  if_max_payload : nat;
  if_framing : nat
}.

Definition witness_InterfaceProfile : InterfaceProfile :=
  {| if_id := 1; if_source := SrcEntropy; if_max_payload := 32; if_framing := 84 |}.

Fixpoint find_interface (id : nat) (l : list InterfaceProfile) : option InterfaceProfile :=
  match l with
  | nil => None
  | cons p rest => if Nat.eqb (if_id p) id then Some p else find_interface id rest
  end.

Definition event_cost (prof : InterfaceProfile) (payload_len : nat) : nat :=
  if_framing prof + 2 * payload_len.

Definition worst_case_cost (prof : InterfaceProfile) : nat :=
  event_cost prof (if_max_payload prof).

Lemma event_cost_le_worst : forall prof len,
  Nat.leb len (if_max_payload prof) = true ->
  Nat.leb (event_cost prof len) (worst_case_cost prof) = true.
Proof.
  intros prof len Hle. unfold worst_case_cost, event_cost.
  apply ProofSupport.nat_leb_add_left.
  unfold Nat.mul. rewrite ProofSupport.nat_add_zero, ProofSupport.nat_add_zero.
  exact (ProofSupport.nat_leb_add_mono len (if_max_payload prof) len (if_max_payload prof) Hle Hle).
Qed.

Record Event : Type := {
  ev_seq : nat;
  ev_point : Point;
  ev_source : Source;
  ev_interface : nat;
  ev_payload : Payload
}.

Definition witness_Event : Event :=
  {| ev_seq := 0;
     ev_point := witness_Point;
     ev_source := SrcEntropy;
     ev_interface := 1;
     ev_payload := PayCommitment (cons 1 nil) |}.

(* =========================================================================
   Part 3. Structural body validator (decode_record) and ordering invariants.
   ========================================================================= *)

Record RawRecord : Type := {
  raw_schema : nat;
  raw_binding : Binding;
  raw_events : list Event;
  raw_body_bytes : nat
}.

Definition witness_RawRecord : RawRecord :=
  {| raw_schema := 1;
     raw_binding := witness_Binding;
     raw_events := nil;
     raw_body_bytes := 80 |}.

Record ValidatedRecord : Type := {
  val_binding : Binding;
  val_events : list Event;
  val_body_bytes : nat
}.

Definition witness_ValidatedRecord : ValidatedRecord :=
  {| val_binding := witness_Binding;
     val_events := nil;
     val_body_bytes := 80 |}.

Definition replay_schema_v1 : nat := 1.

Fixpoint last_core_retire (core : nat) (seen : list (nat * nat)) : nat :=
  match seen with
  | nil => 0
  | cons (c, r) rest => if Nat.eqb c core then r else last_core_retire core rest
  end.

Definition update_core_retire (core ret : nat) (seen : list (nat * nat))
  : list (nat * nat) :=
  cons (pair core ret) seen.

Definition event_wellformed (prof : InterfaceProfile) (e : Event) : bool :=
  andb (source_eqb (ev_source e) (if_source prof))
    (andb (payload_class_eqb (payload_class (ev_payload e))
                             (source_class (ev_source e)))
      (let len := ProofSupport.count_of (payload_bytes (ev_payload e)) in
       andb (Nat.leb 1 len) (Nat.leb len (if_max_payload prof)))).

Fixpoint validate_events_loop
    (allowlist : list InterfaceProfile)
    (next_seq : nat)
    (prev_pt : option Point)
    (retired : list (nat * nat))
    (events : list Event) : bool :=
  match events with
  | nil => true
  | cons e rest =>
      match find_interface (ev_interface e) allowlist with
      | None => false
      | Some prof =>
          let seq_ok := Nat.eqb (ev_seq e) next_seq in
          let pt_ok :=
            match prev_pt with
            | None => true
            | Some p => point_lt p (ev_point e)
            end in
          let ret_ok :=
            Nat.leb (last_core_retire (pt_core (ev_point e)) retired)
                    (pt_retire (ev_point e)) in
          let wf_ok := event_wellformed prof e in
          andb seq_ok (andb pt_ok (andb ret_ok (andb wf_ok
            (validate_events_loop allowlist (S next_seq) (Some (ev_point e))
              (update_core_retire (pt_core (ev_point e)) (pt_retire (ev_point e)) retired)
              rest))))
      end
  end.

Definition limits_valid (l : Limits) : bool :=
  andb (Nat.leb 1 (lim_max_bytes l))
       (Nat.leb (lim_base_bytes l) (lim_max_bytes l)).

Definition profiles_valid (allowlist : list InterfaceProfile) : bool :=
  ProofSupport.all_of (fun p => Nat.leb 1 (if_max_payload p)) allowlist.

Definition decode_record
    (raw : RawRecord)
    (expected : Binding)
    (expected_count : nat)
    (limits : Limits)
    (allowlist : list InterfaceProfile) : option ValidatedRecord :=
  if andb (limits_valid limits)
       (andb (profiles_valid allowlist)
         (andb (Nat.eqb (raw_schema raw) replay_schema_v1)
           (andb (Nat.leb (raw_body_bytes raw) (lim_max_bytes limits))
             (andb (Nat.leb expected_count (lim_max_events limits))
               (andb (Nat.eqb (ProofSupport.count_of (raw_events raw)) expected_count)
                 (andb (binding_eqb (raw_binding raw) expected)
                       (validate_events_loop allowlist 0 None nil (raw_events raw))))))))
  then Some {| val_binding := raw_binding raw;
               val_events := raw_events raw;
               val_body_bytes := raw_body_bytes raw |}
  else None.

Lemma validate_events_loop_seq : forall allowlist next_seq prev_pt retired events,
  validate_events_loop allowlist next_seq prev_pt retired events = true ->
  forall e, ProofSupport.Member e events ->
    Nat.leb next_seq (ev_seq e) = true.
Proof.
  intros allowlist next_seq prev_pt retired events.
  revert next_seq prev_pt retired.
  induction events as [|x xs IH]; intros next_seq prev_pt retired H e Hin.
  - contradiction Hin.
  - simpl in H.
    destruct (find_interface (ev_interface x) allowlist) as [prof|]; [|discriminate H].
    destruct (ProofSupport.andb_split _ _ H) as [Hseq H1].
    destruct (ProofSupport.andb_split _ _ H1) as [_ H2].
    destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
    destruct (ProofSupport.andb_split _ _ H3) as [_ Hrest].
    destruct Hin as [Heq | Hin].
    + rewrite Heq. rewrite (ProofSupport.nat_eqb_true _ _ Hseq).
      apply ProofSupport.nat_leb_refl.
    + exact (ProofSupport.nat_leb_pred next_seq (ev_seq e)
               (IH (S next_seq) (Some (ev_point x))
                   (update_core_retire (pt_core (ev_point x)) (pt_retire (ev_point x)) retired)
                   Hrest e Hin)).
Qed.

Lemma validate_events_loop_class : forall allowlist next_seq prev_pt retired events,
  validate_events_loop allowlist next_seq prev_pt retired events = true ->
  forall e, ProofSupport.Member e events ->
    payload_class (ev_payload e) = source_class (ev_source e).
Proof.
  intros allowlist next_seq prev_pt retired events.
  revert next_seq prev_pt retired.
  induction events as [|x xs IH]; intros next_seq prev_pt retired H e Hin.
  - contradiction Hin.
  - simpl in H.
    destruct (find_interface (ev_interface x) allowlist) as [prof|]; [|discriminate H].
    destruct (ProofSupport.andb_split _ _ H) as [_ H1].
    destruct (ProofSupport.andb_split _ _ H1) as [_ H2].
    destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
    destruct (ProofSupport.andb_split _ _ H3) as [Hwf Hrest].
    destruct Hin as [Heq | Hin].
    + subst e. unfold event_wellformed in Hwf.
      destruct (ProofSupport.andb_split _ _ Hwf) as [_ Hwf1].
      destruct (ProofSupport.andb_split _ _ Hwf1) as [Hcls _].
      destruct (payload_class (ev_payload x)), (source_class (ev_source x));
        try discriminate Hcls; reflexivity.
    + exact (IH (S next_seq) (Some (ev_point x))
                (update_core_retire (pt_core (ev_point x)) (pt_retire (ev_point x)) retired)
                Hrest e Hin).
Qed.

Lemma validate_events_loop_points_lt : forall allowlist next_seq p retired events,
  validate_events_loop allowlist next_seq (Some p) retired events = true ->
  match events with
  | nil => True
  | cons e _ => point_lt p (ev_point e) = true
  end.
Proof.
  intros allowlist next_seq p retired [|e rest] H; [exact I |].
  simpl in H. destruct (find_interface (ev_interface e) allowlist); [|discriminate H].
  destruct (ProofSupport.andb_split _ _ H) as [_ H1].
  destruct (ProofSupport.andb_split _ _ H1) as [Hpt _].
  exact Hpt.
Qed.

(*| discharges: R-15-241, R-16-016, R-16-017 |*)
Theorem source_determines_classification : forall raw exp cnt lim allowlist vr,
  decode_record raw exp cnt lim allowlist = Some vr ->
  forall e, ProofSupport.Member e (val_events vr) ->
    payload_class (ev_payload e) = source_class (ev_source e).
Proof.
  intros raw exp cnt lim allowlist vr Hdec e Hin.
  unfold decode_record in Hdec.
  destruct (andb (limits_valid lim) _) eqn:E; [|discriminate Hdec].
  injection Hdec as Hvr. subst vr. simpl in Hin.
  repeat match type of E with
  | andb _ _ = true => apply ProofSupport.andb_split in E; destruct E as [_ E]
  end.
  exact (validate_events_loop_class allowlist 0 None nil (raw_events raw) E e Hin).
Qed.

(*| discharges: R-16-013, R-16-022 |*)
Theorem decode_accepts_only_expected_binding_and_count :
  forall raw exp cnt lim allowlist vr,
    decode_record raw exp cnt lim allowlist = Some vr ->
    val_binding vr = exp /\ ProofSupport.count_of (val_events vr) = cnt.
Proof.
  intros raw exp cnt lim allowlist vr Hdec.
  unfold decode_record in Hdec.
  destruct (andb (limits_valid lim) _) eqn:E; [|discriminate Hdec].
  injection Hdec as Hvr. subst vr. simpl.
  apply ProofSupport.andb_split in E as [_ E].
  apply ProofSupport.andb_split in E as [_ E].
  apply ProofSupport.andb_split in E as [_ E].
  apply ProofSupport.andb_split in E as [_ E].
  apply ProofSupport.andb_split in E as [_ E].
  apply ProofSupport.andb_split in E as [Hcnt E].
  apply ProofSupport.andb_split in E as [Hbind _].
  split.
  - exact (binding_eqb_true _ _ Hbind).
  - exact (ProofSupport.nat_eqb_true _ _ Hcnt).
Qed.

Lemma andb_false_r_local : forall b : bool, andb b false = false.
Proof. intros [|]; reflexivity. Qed.

Theorem decode_refuses_mismatched_binding : forall raw exp cnt lim allowlist,
  binding_eqb (raw_binding raw) exp = false ->
  decode_record raw exp cnt lim allowlist = None.
Proof.
  intros raw exp cnt lim allowlist Hne. unfold decode_record.
  rewrite Hne.
  repeat rewrite andb_false_r_local. reflexivity.
Qed.

Theorem decode_refuses_wrong_count : forall raw exp cnt lim allowlist,
  Nat.eqb (ProofSupport.count_of (raw_events raw)) cnt = false ->
  decode_record raw exp cnt lim allowlist = None.
Proof.
  intros raw exp cnt lim allowlist Hne. unfold decode_record.
  rewrite Hne.
  destruct (limits_valid lim); destruct (profiles_valid allowlist);
    destruct (Nat.eqb (raw_schema raw) replay_schema_v1);
    destruct (Nat.leb (raw_body_bytes raw) (lim_max_bytes lim));
    destruct (Nat.leb cnt (lim_max_events lim)); reflexivity.
Qed.

Fixpoint nth_ev_idx (n : nat) (events : list Event) : option Event :=
  match events with
  | nil => None
  | cons e rest => match n with 0 => Some e | S k => nth_ev_idx k rest end
  end.

Lemma validate_events_loop_contiguous_seq :
  forall allowlist next_seq prev_pt retired events idx e,
    validate_events_loop allowlist next_seq prev_pt retired events = true ->
    nth_ev_idx idx events = Some e ->
    ev_seq e = next_seq + idx.
Proof.
  intros allowlist next_seq prev_pt retired events.
  revert next_seq prev_pt retired.
  induction events as [|x xs IH]; intros next_seq prev_pt retired idx e H Hnth.
  - destruct idx; discriminate Hnth.
  - simpl in H. destruct (find_interface (ev_interface x) allowlist); [|discriminate H].
    destruct (ProofSupport.andb_split _ _ H) as [Hseq H1].
    destruct (ProofSupport.andb_split _ _ H1) as [_ H2].
    destruct (ProofSupport.andb_split _ _ H2) as [_ H3].
    destruct (ProofSupport.andb_split _ _ H3) as [_ Hrest].
    destruct idx as [|k].
    + simpl in Hnth. injection Hnth as Hnth. subst x.
      rewrite ProofSupport.nat_add_zero.
      exact (ProofSupport.nat_eqb_true _ _ Hseq).
    + simpl in Hnth.
      rewrite (IH (S next_seq) (Some (ev_point x))
                  (update_core_retire (pt_core (ev_point x)) (pt_retire (ev_point x)) retired)
                  k e Hrest Hnth).
      simpl. rewrite ProofSupport.nat_add_succ. reflexivity.
Qed.

Theorem decoded_events_contiguous_seq : forall raw exp cnt lim allowlist vr idx e,
  decode_record raw exp cnt lim allowlist = Some vr ->
  nth_ev_idx idx (val_events vr) = Some e ->
  ev_seq e = idx.
Proof.
  intros raw exp cnt lim allowlist vr idx e Hdec Hnth.
  unfold decode_record in Hdec.
  destruct (andb (limits_valid lim) _) eqn:E; [|discriminate Hdec].
  injection Hdec as Hvr. subst vr. simpl in Hnth.
  repeat match type of E with
  | andb _ _ = true => apply ProofSupport.andb_split in E; destruct E as [_ E]
  end.
  exact (validate_events_loop_contiguous_seq allowlist 0 None nil (raw_events raw) idx e E Hnth).
Qed.

(* =========================================================================
   Part 4. Recorder state machine: pre-invocation reservation, sealing seam,
           sticky failure latch, reentrancy refusal, and terminal fault path.
   ========================================================================= *)

Record RecorderState : Type := {
  rec_binding : Binding;
  rec_limits : Limits;
  rec_interfaces : list InterfaceProfile;
  rec_events : list Event;
  rec_used_bytes : nat;
  rec_busy : bool;
  rec_failed : bool;
  rec_finished : bool;
  rec_fault_routed : bool
}.

Definition witness_RecorderState : RecorderState :=
  {| rec_binding := witness_Binding;
     rec_limits := witness_Limits;
     rec_interfaces := cons witness_InterfaceProfile nil;
     rec_events := nil;
     rec_used_bytes := 80;
     rec_busy := false;
     rec_failed := false;
     rec_finished := false;
     rec_fault_routed := false |}.

Definition recorder_init (b : Binding) (l : Limits) (ifs : list InterfaceProfile)
  : option RecorderState :=
  if andb (limits_valid l) (profiles_valid ifs)
  then Some {| rec_binding := b;
               rec_limits := l;
               rec_interfaces := ifs;
               rec_events := nil;
               rec_used_bytes := lim_base_bytes l;
               rec_busy := false;
               rec_failed := false;
               rec_finished := false;
               rec_fault_routed := false |}
  else None.

Fixpoint last_event_point (events : list Event) : option Point :=
  match events with
  | nil => None
  | cons e nil => Some (ev_point e)
  | cons _ rest => last_event_point rest
  end.

Fixpoint max_core_retire (core : nat) (events : list Event) : nat :=
  match events with
  | nil => 0
  | cons e rest =>
      let prev := max_core_retire core rest in
      if Nat.eqb (pt_core (ev_point e)) core
      then Nat.max (pt_retire (ev_point e)) prev
      else prev
  end.

Definition recorder_ready (st : RecorderState) : bool :=
  andb (negb (rec_failed st))
       (andb (negb (rec_finished st)) (negb (rec_busy st))).

Definition admit_reserve (st : RecorderState) (pt : Point) (iface_id : nat)
  : option InterfaceProfile :=
  if negb (recorder_ready st) then None
  else
    match find_interface iface_id (rec_interfaces st) with
    | None => None
    | Some prof =>
        let pt_ok :=
          match last_event_point (rec_events st) with
          | None => true
          | Some prev => point_lt prev pt
          end in
        let ret_ok :=
          Nat.leb (max_core_retire (pt_core pt) (rec_events st)) (pt_retire pt) in
        let seq_ok :=
          Nat.ltb (ProofSupport.count_of (rec_events st)) (lim_max_events (rec_limits st)) in
        let cap_ok :=
          Nat.leb (rec_used_bytes st + worst_case_cost prof)
                  (lim_max_bytes (rec_limits st)) in
        if andb pt_ok (andb ret_ok (andb seq_ok cap_ok))
        then Some prof
        else None
    end.

Definition latch_fault (st : RecorderState) : RecorderState :=
  {| rec_binding := rec_binding st;
     rec_limits := rec_limits st;
     rec_interfaces := rec_interfaces st;
     rec_events := rec_events st;
     rec_used_bytes := rec_used_bytes st;
     rec_busy := false;
     rec_failed := true;
     rec_finished := rec_finished st;
     rec_fault_routed := true |}.

Inductive ProducerOutcome : Type :=
| ProdDeclined : ProducerOutcome
| ProdBytes : list nat -> bool -> bool -> ProducerOutcome
| ProdError : ProducerOutcome.
(* In `ProdBytes raw pub_ok nested_latch`, `raw` is either raw entropy draw
   bytes (to be sealed by `seal` without entering the record) or public verbatim
   bytes checked by `pub_ok`; `nested_latch` models an in-callback abort or
   swallowed nested refusal. *)

Definition record_step
    (seal : list nat -> list nat)
    (st : RecorderState)
    (pt : Point)
    (iface_id : nat)
    (outcome : ProducerOutcome)
  : option Event * RecorderState :=
  match admit_reserve st pt iface_id with
  | None => (None, latch_fault st)
  | Some prof =>
      match outcome with
      | ProdError => (None, latch_fault st)
      | ProdDeclined =>
          (* Declined draw releases reservation and advances neither seq nor bytes. *)
          (None, st)
      | ProdBytes raw pub_ok nested_latch =>
          if nested_latch then (None, latch_fault st)
          else
            let produced :=
              match if_source prof with
              | SrcEntropy => seal raw
              | _ => raw
              end in
            let len := ProofSupport.count_of produced in
            let bounds_ok :=
              andb (Nat.leb 1 len) (Nat.leb len (if_max_payload prof)) in
            let sem_ok :=
              if source_is_public (if_source prof) then pub_ok else true in
            if andb bounds_ok sem_ok then
              let ev := {| ev_seq := ProofSupport.count_of (rec_events st);
                           ev_point := pt;
                           ev_source := if_source prof;
                           ev_interface := if_id prof;
                           ev_payload :=
                             match if_source prof with
                             | SrcEntropy => PayCommitment produced
                             | _ => PayPublic produced
                             end |} in
              let st' := {| rec_binding := rec_binding st;
                            rec_limits := rec_limits st;
                            rec_interfaces := rec_interfaces st;
                            rec_events := app (rec_events st) (cons ev nil);
                            rec_used_bytes := rec_used_bytes st + event_cost prof len;
                            rec_busy := false;
                            rec_failed := false;
                            rec_finished := false;
                            rec_fault_routed := false |} in
              (Some ev, st')
            else (None, latch_fault st)
      end
  end.

Definition finish_recorder
    (st : RecorderState)
    (expected : Binding)
    (expected_count : nat)
  : option ValidatedRecord * RecorderState :=
  if negb (recorder_ready st) then (None, latch_fault st)
  else
    let raw := {| raw_schema := replay_schema_v1;
                  raw_binding := rec_binding st;
                  raw_events := rec_events st;
                  raw_body_bytes := rec_used_bytes st |} in
    match decode_record raw expected expected_count (rec_limits st) (rec_interfaces st) with
    | None => (None, latch_fault st)
    | Some vr =>
        let st' := {| rec_binding := rec_binding st;
                      rec_limits := rec_limits st;
                      rec_interfaces := rec_interfaces st;
                      rec_events := rec_events st;
                      rec_used_bytes := rec_used_bytes st;
                      rec_busy := false;
                      rec_failed := false;
                      rec_finished := true;
                      rec_fault_routed := false |} in
        (Some vr, st')
    end.

(*| discharges: R-16-023 |*)
Theorem pre_invocation_capacity_checks_worst_case :
  forall seal st pt iface_id prof outcome,
    find_interface iface_id (rec_interfaces st) = Some prof ->
    Nat.leb (rec_used_bytes st + worst_case_cost prof)
            (lim_max_bytes (rec_limits st)) = false ->
    record_step seal st pt iface_id outcome = (None, latch_fault st) /\
    rec_events (latch_fault st) = rec_events st /\
    rec_used_bytes (latch_fault st) = rec_used_bytes st /\
    rec_fault_routed (latch_fault st) = true.
Proof.
  intros seal st pt iface_id prof outcome Hfind Hcap.
  unfold record_step, admit_reserve.
  destruct (negb (recorder_ready st)) eqn:Hready.
  - repeat split; reflexivity.
  - rewrite Hfind, Hcap.
    destruct (match last_event_point (rec_events st) with
              | Some prev => point_lt prev pt
              | None => true
              end);
      destruct (Nat.leb (max_core_retire (pt_core pt) (rec_events st)) (pt_retire pt));
      destruct (Nat.ltb (ProofSupport.count_of (rec_events st)) (lim_max_events (rec_limits st)));
      repeat split; reflexivity.
Qed.

Theorem accepted_step_releases_unused_margin :
  forall seal st pt iface_id raw pub_ok ev st' prof,
    find_interface iface_id (rec_interfaces st) = Some prof ->
    record_step seal st pt iface_id (ProdBytes raw pub_ok false) = (Some ev, st') ->
    Nat.leb (rec_used_bytes st')
            (rec_used_bytes st + worst_case_cost prof) = true.
Proof.
  intros seal st pt iface_id raw pub_ok ev st' prof Hfind Hstep.
  unfold record_step, admit_reserve in Hstep.
  destruct (negb (recorder_ready st)); [discriminate Hstep|].
  rewrite Hfind in Hstep.
  destruct (andb (match last_event_point (rec_events st) with
                   | Some prev => point_lt prev pt
                   | None => true
                   end) _); [|discriminate Hstep].
  destruct (andb (andb (Nat.leb 1 _) (Nat.leb _ (if_max_payload prof))) _) eqn:Hchk;
    [|discriminate Hstep].
  apply ProofSupport.andb_split in Hchk as [Hbounds _].
  apply ProofSupport.andb_split in Hbounds as [_ Hlen].
  injection Hstep as _ Hst. subst st'. simpl.
  apply ProofSupport.nat_leb_add_left.
  apply event_cost_le_worst. exact Hlen.
Qed.

(*| discharges: R-16-013, R-16-023 |*)
Theorem sticky_failure_blocks_record : forall seal st pt iface_id outcome,
  rec_failed st = true ->
  fst (record_step seal st pt iface_id outcome) = None /\
  rec_failed (snd (record_step seal st pt iface_id outcome)) = true /\
  rec_fault_routed (snd (record_step seal st pt iface_id outcome)) = true.
Proof.
  intros seal st pt iface_id outcome Hfail.
  unfold record_step, admit_reserve, recorder_ready.
  rewrite Hfail. simpl. repeat split; reflexivity.
Qed.

Theorem sticky_failure_blocks_finish : forall st exp cnt,
  rec_failed st = true ->
  fst (finish_recorder st exp cnt) = None /\
  rec_failed (snd (finish_recorder st exp cnt)) = true.
Proof.
  intros st exp cnt Hfail.
  unfold finish_recorder, recorder_ready.
  rewrite Hfail. simpl. split; reflexivity.
Qed.

Theorem reentrancy_latches_failure : forall seal st pt iface_id outcome exp cnt,
  rec_busy st = true ->
  fst (record_step seal st pt iface_id outcome) = None /\
  rec_failed (snd (record_step seal st pt iface_id outcome)) = true /\
  fst (finish_recorder st exp cnt) = None /\
  rec_failed (snd (finish_recorder st exp cnt)) = true.
Proof.
  intros seal st pt iface_id outcome exp cnt Hbusy.
  unfold record_step, admit_reserve, finish_recorder, recorder_ready.
  rewrite Hbusy.
  destruct (rec_failed st); destruct (rec_finished st);
    repeat split; reflexivity.
Qed.

Theorem finish_requires_expected_binding_and_count :
  forall st exp cnt vr st',
    finish_recorder st exp cnt = (Some vr, st') ->
    val_binding vr = exp /\ ProofSupport.count_of (val_events vr) = cnt.
Proof.
  intros st exp cnt vr st' Hfin.
  unfold finish_recorder in Hfin.
  destruct (negb (recorder_ready st)); [discriminate Hfin|].
  destruct (decode_record _ exp cnt (rec_limits st) (rec_interfaces st)) eqn:Hdec;
    [|discriminate Hfin].
  injection Hfin as Hvr _. subst v.
  exact (decode_accepts_only_expected_binding_and_count _ _ _ _ _ _ Hdec).
Qed.

(* =========================================================================
   Part 5. Demand-cursor verifier, commitment hiding, and CT-scope replay.
   ========================================================================= *)

Record CursorState : Type := {
  cur_events : list Event;
  cur_pos : nat;
  cur_failed : bool;
  cur_finished : bool
}.

Definition witness_CursorState : CursorState :=
  {| cur_events := nil; cur_pos := 0; cur_failed := false; cur_finished := false |}.

Definition cursor_init (vr : ValidatedRecord) : CursorState :=
  {| cur_events := val_events vr;
     cur_pos := 0;
     cur_failed := false;
     cur_finished := false |}.

Fixpoint nth_event (n : nat) (events : list Event) : option Event :=
  match events with
  | nil => None
  | cons e rest => match n with 0 => Some e | S k => nth_event k rest end
  end.

Definition cursor_fail (c : CursorState) : CursorState :=
  {| cur_events := cur_events c;
     cur_pos := cur_pos c;
     cur_failed := true;
     cur_finished := cur_finished c |}.

Definition cursor_consume (c : CursorState) (pt : Point) (src : Source) (iface_id : nat)
  : option Event * CursorState :=
  if orb (cur_failed c) (cur_finished c) then (None, cursor_fail c)
  else
    match nth_event (cur_pos c) (cur_events c) with
    | None => (None, cursor_fail c)
    | Some e =>
        if andb (point_eqb (ev_point e) pt)
             (andb (source_eqb (ev_source e) src)
                   (Nat.eqb (ev_interface e) iface_id))
        then (Some e, {| cur_events := cur_events c;
                         cur_pos := S (cur_pos c);
                         cur_failed := false;
                         cur_finished := false |})
        else (None, cursor_fail c)
    end.

Definition cursor_finish (c : CursorState) : bool * CursorState :=
  if orb (cur_failed c) (cur_finished c) then (false, cursor_fail c)
  else if Nat.eqb (cur_pos c) (ProofSupport.count_of (cur_events c))
       then (true, {| cur_events := cur_events c;
                      cur_pos := cur_pos c;
                      cur_failed := false;
                      cur_finished := true |})
       else (false, cursor_fail c).

Lemma nth_event_none_ge : forall events pos,
  Nat.leb (ProofSupport.count_of events) pos = true ->
  nth_event pos events = None.
Proof.
  induction events as [|e rest IH]; intros [|pos] H.
  - reflexivity.
  - reflexivity.
  - discriminate H.
  - simpl in *. exact (IH pos H).
Qed.

Lemma nth_event_some_lt : forall events pos,
  Nat.ltb pos (ProofSupport.count_of events) = true ->
  exists e, nth_event pos events = Some e.
Proof.
  induction events as [|e rest IH]; intros [|pos] H.
  - discriminate H.
  - discriminate H.
  - exists e. reflexivity.
  - simpl in *. exact (IH pos H).
Qed.

Theorem cursor_consume_exact_match : forall c pt src iface_id e c',
  cursor_consume c pt src iface_id = (Some e, c') ->
  ev_point e = pt /\
  ev_source e = src /\
  ev_interface e = iface_id /\
  cur_pos c' = S (cur_pos c) /\
  cur_failed c' = false.
Proof.
  intros c pt src iface_id e c' H.
  unfold cursor_consume in H.
  destruct (orb (cur_failed c) (cur_finished c)); [discriminate H|].
  destruct (nth_event (cur_pos c) (cur_events c)) as [ev|]; [|discriminate H].
  destruct (andb (point_eqb (ev_point ev) pt) _) eqn:Hm; [|discriminate H].
  apply ProofSupport.andb_split in Hm as [Hp H1].
  apply ProofSupport.andb_split in H1 as [Hs Hi].
  injection H as He Hc. subst ev c'.
  repeat split.
  - exact (point_eqb_true _ _ Hp).
  - exact (source_eqb_true _ _ Hs).
  - exact (ProofSupport.nat_eqb_true _ _ Hi).
Qed.

Theorem cursor_refuses_exhaustion : forall c pt src iface_id,
  Nat.leb (ProofSupport.count_of (cur_events c)) (cur_pos c) = true ->
  fst (cursor_consume c pt src iface_id) = None /\
  cur_failed (snd (cursor_consume c pt src iface_id)) = true.
Proof.
  intros c pt src iface_id Hge.
  unfold cursor_consume.
  destruct (orb (cur_failed c) (cur_finished c)); [split; reflexivity|].
  rewrite (nth_event_none_ge _ _ Hge). split; reflexivity.
Qed.

Theorem cursor_refuses_trailing_events : forall c,
  Nat.ltb (cur_pos c) (ProofSupport.count_of (cur_events c)) = true ->
  fst (cursor_finish c) = false /\
  cur_failed (snd (cursor_finish c)) = true.
Proof.
  intros c Hlt.
  unfold cursor_finish.
  destruct (orb (cur_failed c) (cur_finished c)); [split; reflexivity|].
  rewrite (nat_ltb_not_eq _ _ Hlt). split; reflexivity.
Qed.

(* No secret draw value is recoverable from an opaque commitment payload:
   a sealing primitive maps distinct secret draws into opaque commitment bytes,
   and `PayCommitment` retains only those commitment bytes. *)
(*| discharges: R-16-017, R-16-020 |*)
Theorem commitment_hides_secret_draw :
  forall (seal : list nat -> list nat) (recover : Payload -> list nat),
    (exists d1 d2, d1 <> d2 /\ seal d1 = seal d2) ->
    exists d1 d2,
      d1 <> d2 /\
      PayCommitment (seal d1) = PayCommitment (seal d2) /\
      (recover (PayCommitment (seal d1)) <> d1 \/
       recover (PayCommitment (seal d2)) <> d2).
Proof.
  intros seal recover [d1 [d2 [Hne Hcol]]].
  exists d1, d2. split; [exact Hne|].
  rewrite Hcol. split; [reflexivity|].
  destruct (ProofSupport.list_eqb Nat.eqb (recover (PayCommitment (seal d2))) d1) eqn:E.
  - right. intro Heq.
    apply ProofSupport.list_eqb_sound in E; [|exact ProofSupport.nat_eqb_true].
    rewrite E in Heq. apply Hne. exact Heq.
  - left. intro Heq.
    rewrite Heq in E. rewrite (ProofSupport.list_eqb_refl _ Nat.eqb ProofSupport.nat_eqb_refl) in E.
    discriminate E.
Qed.

(* CT-scope deterministic replay equivalence (R-16-018, R-16-019, R-16-021, R-16-022). *)
Record CTStep : Type := {
  ct_insn : nat;
  ct_addr : nat;
  ct_cap_op : nat;
  ct_sched : nat;
  ct_ct_fault : nat;
  ct_pub_out : list nat
}.

Definition witness_CTStep : CTStep :=
  {| ct_insn := 1; ct_addr := 100; ct_cap_op := 2; ct_sched := 0;
     ct_ct_fault := 0; ct_pub_out := cons 7 nil |}.

Record ReplayObs : Type := {
  obs_ct : CTStep;
  obs_draw_fault : nat
}.

Definition witness_ReplayObs : ReplayObs :=
  {| obs_ct := witness_CTStep; obs_draw_fault := 0 |}.

(* Within the CT-verified scope, each execution step's control flow, addresses,
   capability ops, schedule, CT faults, and public-cone values are functions of
   the authenticated initial state, ordinary input trace, and public
   nondeterminism, independent of substituted secret entropy draws. *)
Fixpoint run_ct_trace
    (step_obs : nat -> list nat -> list nat -> ReplayObs)
    (state : nat)
    (public_inputs : list (list nat))
    (secret_draws : list (list nat)) : list CTStep :=
  match public_inputs, secret_draws with
  | cons pub pubs, cons draw draws =>
      cons (obs_ct (step_obs state pub draw))
           (run_ct_trace step_obs (S state) pubs draws)
  | _, _ => nil
  end.

(*| discharges: R-16-018, R-16-019 |*)
Theorem ct_scope_deterministic_replay_equivalence :
  forall (step_obs : nat -> list nat -> list nat -> ReplayObs)
         (state : nat)
         (public_inputs draws1 draws2 : list (list nat)),
    (forall st pub d1 d2, obs_ct (step_obs st pub d1) = obs_ct (step_obs st pub d2)) ->
    ProofSupport.count_of draws1 = ProofSupport.count_of draws2 ->
    run_ct_trace step_obs state public_inputs draws1 =
    run_ct_trace step_obs state public_inputs draws2.
Proof.
  intros step_obs state public_inputs. revert state.
  induction public_inputs as [|pub pubs IH]; intros state draws1 draws2 Hct Hlen.
  - destruct draws1; destruct draws2; reflexivity.
  - destruct draws1 as [|d1 ds1]; destruct draws2 as [|d2 ds2];
      try discriminate Hlen; [reflexivity|].
    simpl in *. injection Hlen as Hlen'.
    rewrite (Hct state pub d1 d2), (IH (S state) ds1 ds2 Hct Hlen').
    reflexivity.
Qed.

(* =========================================================================
   Part 6. Non-vacuity: inhabited 4-source capture/replay and refutations.
   ========================================================================= *)

Definition ex_binding : Binding :=
  {| bind_base_image_root := 11;
     bind_composition := 22;
     bind_input_trace := 33 |}.

Definition ex_limits : Limits :=
  {| lim_max_bytes := 512;
     lim_max_events := 4;
     lim_base_bytes := 80 |}.

Definition ex_interfaces : list InterfaceProfile :=
  cons {| if_id := 101; if_source := SrcEntropy; if_max_payload := 4; if_framing := 84 |}
  (cons {| if_id := 102; if_source := SrcLinkAddress; if_max_payload := 4; if_framing := 84 |}
  (cons {| if_id := 103; if_source := SrcTimeRead; if_max_payload := 4; if_framing := 84 |}
  (cons {| if_id := 104; if_source := SrcPhysicalEvent; if_max_payload := 4; if_framing := 84 |}
        nil))).

Definition ex_seal (draw : list nat) : list nat :=
  match draw with
  | nil => cons 170 nil
  | cons x _ => cons (170 + x) nil
  end.

Definition ex_capture_four_sources : option ValidatedRecord :=
  match recorder_init ex_binding ex_limits ex_interfaces with
  | None => None
  | Some s0 =>
      let p0 := {| pt_slot := 0; pt_core := 0; pt_retire := 0; pt_ordinal := 0 |} in
      let p1 := {| pt_slot := 0; pt_core := 0; pt_retire := 1; pt_ordinal := 0 |} in
      let p2 := {| pt_slot := 0; pt_core := 0; pt_retire := 1; pt_ordinal := 1 |} in
      let p3 := {| pt_slot := 1; pt_core := 0; pt_retire := 1; pt_ordinal := 0 |} in
      let (_, s1) := record_step ex_seal s0 p0 101 (ProdBytes (cons 5 nil) true false) in
      let (_, s2) := record_step ex_seal s1 p1 102 (ProdBytes (cons 6 (cons 7 nil)) true false) in
      let (_, s3) := record_step ex_seal s2 p2 103 (ProdBytes (cons 8 nil) true false) in
      let (_, s4) := record_step ex_seal s3 p3 104 (ProdBytes (cons 9 nil) true false) in
      fst (finish_recorder s4 ex_binding 4)
  end.

Definition ex_replay_four_sources (vr : ValidatedRecord) : bool :=
  let c0 := cursor_init vr in
  let p0 := {| pt_slot := 0; pt_core := 0; pt_retire := 0; pt_ordinal := 0 |} in
  let p1 := {| pt_slot := 0; pt_core := 0; pt_retire := 1; pt_ordinal := 0 |} in
  let p2 := {| pt_slot := 0; pt_core := 0; pt_retire := 1; pt_ordinal := 1 |} in
  let p3 := {| pt_slot := 1; pt_core := 0; pt_retire := 1; pt_ordinal := 0 |} in
  match cursor_consume c0 p0 SrcEntropy 101 with
  | (None, _) => false
  | (Some _, c1) =>
      match cursor_consume c1 p1 SrcLinkAddress 102 with
      | (None, _) => false
      | (Some _, c2) =>
          match cursor_consume c2 p2 SrcTimeRead 103 with
          | (None, _) => false
          | (Some _, c3) =>
              match cursor_consume c3 p3 SrcPhysicalEvent 104 with
              | (None, _) => false
              | (Some _, c4) => fst (cursor_finish c4)
              end
          end
      end
  end.

Example positive_four_source_trace_accepted :
  ProofSupport.is_some ex_capture_four_sources = true.
Proof. vm_reflexivity. Qed.

Example positive_four_source_cursor_replayed :
  match ex_capture_four_sources with
  | None => false
  | Some vr => ex_replay_four_sources vr
  end = true.
Proof. vm_reflexivity. Qed.

(* Refutation 1: malformed schema *)
Example refute_unknown_schema :
  decode_record
    {| raw_schema := 99; raw_binding := ex_binding; raw_events := nil; raw_body_bytes := 80 |}
    ex_binding 0 ex_limits ex_interfaces = None.
Proof. vm_reflexivity. Qed.

(* Refutation 2: secret commitment placed on a public source *)
Example refute_secret_in_public :
  decode_record
    {| raw_schema := 1;
       raw_binding := ex_binding;
       raw_events := cons {| ev_seq := 0;
                             ev_point := witness_Point;
                             ev_source := SrcLinkAddress;
                             ev_interface := 102;
                             ev_payload := PayCommitment (cons 1 nil) |} nil;
       raw_body_bytes := 166 |}
    ex_binding 1 ex_limits ex_interfaces = None.
Proof. vm_reflexivity. Qed.

(* Refutation 3: public verbatim payload placed on entropy source *)
Example refute_public_in_entropy :
  decode_record
    {| raw_schema := 1;
       raw_binding := ex_binding;
       raw_events := cons {| ev_seq := 0;
                             ev_point := witness_Point;
                             ev_source := SrcEntropy;
                             ev_interface := 101;
                             ev_payload := PayPublic (cons 1 nil) |} nil;
       raw_body_bytes := 166 |}
    ex_binding 1 ex_limits ex_interfaces = None.
Proof. vm_reflexivity. Qed.

(* Refutation 4: regressing coordinate (slot/core/retire/ordinal) and local retire regression *)
Example refute_regressing_coordinate :
  decode_record
    {| raw_schema := 1;
       raw_binding := ex_binding;
       raw_events :=
         cons {| ev_seq := 0;
                 ev_point := {| pt_slot := 1; pt_core := 0; pt_retire := 5; pt_ordinal := 0 |};
                 ev_source := SrcEntropy; ev_interface := 101;
                 ev_payload := PayCommitment (cons 1 nil) |}
         (cons {| ev_seq := 1;
                  ev_point := {| pt_slot := 0; pt_core := 0; pt_retire := 6; pt_ordinal := 0 |};
                  ev_source := SrcTimeRead; ev_interface := 103;
                  ev_payload := PayPublic (cons 2 nil) |} nil);
       raw_body_bytes := 252 |}
    ex_binding 2 ex_limits ex_interfaces = None.
Proof. vm_reflexivity. Qed.

Example refute_regressing_retire :
  decode_record
    {| raw_schema := 1;
       raw_binding := ex_binding;
       raw_events :=
         cons {| ev_seq := 0;
                 ev_point := {| pt_slot := 0; pt_core := 0; pt_retire := 5; pt_ordinal := 0 |};
                 ev_source := SrcEntropy; ev_interface := 101;
                 ev_payload := PayCommitment (cons 1 nil) |}
         (cons {| ev_seq := 1;
                  ev_point := {| pt_slot := 1; pt_core := 0; pt_retire := 4; pt_ordinal := 0 |};
                  ev_source := SrcTimeRead; ev_interface := 103;
                  ev_payload := PayPublic (cons 2 nil) |} nil);
       raw_body_bytes := 252 |}
    ex_binding 2 ex_limits ex_interfaces = None.
Proof. vm_reflexivity. Qed.

(* Refutation 5: non-contiguous seq *)
Example refute_seq_gap :
  decode_record
    {| raw_schema := 1;
       raw_binding := ex_binding;
       raw_events :=
         cons {| ev_seq := 1;
                 ev_point := witness_Point;
                 ev_source := SrcEntropy; ev_interface := 101;
                 ev_payload := PayCommitment (cons 1 nil) |} nil;
       raw_body_bytes := 166 |}
    ex_binding 1 ex_limits ex_interfaces = None.
Proof. vm_reflexivity. Qed.

(* Refutation 6: pre-invocation worst-case capacity overflow refuses even a 1-byte payload *)
Example refute_capacity_overflow :
  let tight := {| lim_max_bytes := 171; lim_max_events := 1; lim_base_bytes := 80 |} in
  match recorder_init ex_binding tight ex_interfaces with
  | None => false
  | Some s0 =>
      let res := record_step ex_seal s0 witness_Point 101 (ProdBytes (cons 1 nil) true false) in
      andb (negb (ProofSupport.is_some (fst res)))
           (andb (rec_failed (snd res)) (rec_fault_routed (snd res)))
  end = true.
Proof. vm_reflexivity. Qed.

(* Refutation 7: sticky failure latch prevents uncertain-prefix finalization *)
Example refute_uncertain_prefix :
  match recorder_init ex_binding ex_limits ex_interfaces with
  | None => false
  | Some s0 =>
      let (_, s1) := record_step ex_seal s0 witness_Point 101 (ProdBytes (cons 5 nil) true false) in
      let p1 := {| pt_slot := 0; pt_core := 0; pt_retire := 0; pt_ordinal := 1 |} in
      let (_, s2) := record_step ex_seal s1 p1 102 (ProdBytes (cons 6 nil) false false) in
      andb (rec_failed s2) (negb (ProofSupport.is_some (fst (finish_recorder s2 ex_binding 1))))
  end = true.
Proof. vm_reflexivity. Qed.

(* Refutation 8 & 9: cursor exhaustion and trailing events *)
Example refute_cursor_exhaustion :
  match ex_capture_four_sources with
  | None => false
  | Some vr =>
      let c0 := {| cur_events := val_events vr; cur_pos := 4;
                   cur_failed := false; cur_finished := false |} in
      let res := cursor_consume c0 witness_Point SrcEntropy 101 in
      andb (negb (ProofSupport.is_some (fst res))) (cur_failed (snd res))
  end = true.
Proof. vm_reflexivity. Qed.

Example refute_cursor_trailing :
  match ex_capture_four_sources with
  | None => false
  | Some vr =>
      let c0 := cursor_init vr in
      let res := cursor_finish c0 in
      andb (negb (fst res)) (cur_failed (snd res))
  end = true.
Proof. vm_reflexivity. Qed.

(* Refutation 10: substituted binding and wrong expected count *)
Example refute_substituted_binding :
  let bad_binding := {| bind_base_image_root := 99; bind_composition := 22; bind_input_trace := 33 |} in
  match recorder_init ex_binding ex_limits ex_interfaces with
  | None => false
  | Some s0 =>
      let (_, s1) := record_step ex_seal s0 witness_Point 101 (ProdBytes (cons 5 nil) true false) in
      let (res, s2) := finish_recorder s1 bad_binding 1 in
      andb (negb (ProofSupport.is_some res)) (rec_failed s2)
  end = true.
Proof. vm_reflexivity. Qed.

Example refute_wrong_expected_count :
  match recorder_init ex_binding ex_limits ex_interfaces with
  | None => false
  | Some s0 =>
      let (_, s1) := record_step ex_seal s0 witness_Point 101 (ProdBytes (cons 5 nil) true false) in
      let (res, s2) := finish_recorder s1 ex_binding 2 in
      andb (negb (ProofSupport.is_some res)) (rec_failed s2)
  end = true.
Proof. vm_reflexivity. Qed.

(* Refutation 11: draw-dependent fault outside CT scope can diverge under substituted draws *)
Example refute_draw_dependent_fault_diverges :
  let step_obs (_st : nat) (pub draw : list nat) : ReplayObs :=
    {| obs_ct := {| ct_insn := 1; ct_addr := 10; ct_cap_op := 1;
                    ct_sched := 0; ct_ct_fault := 0; ct_pub_out := pub |};
       obs_draw_fault := match draw with cons 42 _ => 1 | _ => 0 end |} in
  let o1 := step_obs 0 (cons 1 nil) (cons 42 nil) in
  let o2 := step_obs 0 (cons 1 nil) (cons 7 nil) in
  andb (Nat.eqb (ct_insn (obs_ct o1)) (ct_insn (obs_ct o2)))
       (negb (Nat.eqb (obs_draw_fault o1) (obs_draw_fault o2))) = true.
Proof. vm_reflexivity. Qed.

(* Non-vacuity witness for commitment_hides_secret_draw *)
Example commitment_collision_witness :
  let const_seal (_d : list nat) : list nat := cons 1 nil in
  let d1 := cons 1 nil in
  let d2 := cons 2 nil in
  d1 <> d2 /\ const_seal d1 = const_seal d2.
Proof.
  split; [intro H; discriminate H | reflexivity].
Qed.
