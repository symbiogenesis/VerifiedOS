(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   First bounded reservation reference for Q44, R-10-006a and R-10-006b.

   One charged immutable backing, exactly two independent holder slots, and one
   outstanding request per holder. Admission, current authority, boot/generation,
   expiry, exact identity/window and finite request sequences are executable checks.
   Completion invokes an abstract verifier on the actual retained bytes and root;
   no verifier correctness or digest injectivity is assumed. A positive fixture
   verifier compares against independently specified byte/root values.

   Journals enumerate abstract stored-cell writes, including repeated-value stores.
   They are not concrete target memory traces. This source has no correspondence
   theorem to the Python reference, scalar effects, SHA-256 or storage. The modeled
   completion barrier is a declared external input, never physical reuse evidence.
   The first increment has no CoW replacement, renewal, crash or target WCET claim.
   No theorem in this file discharges an entire cited requirement.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-10-006a R-10-006b
   SHA256: 85f17ff41c76f5c615207dadeeea5de186f839aebc9785a8680033d6f38f91b2
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.
Local Open Scope nat_scope.

Inductive RootKind : Type := SystemImage | UserData.

Record Identity : Type := {
  owner : nat; domain : nat; object_id : nat; version : nat;
  root_kind : RootKind; generation : nat; root_digest : list nat
}.
Record Resident : Type := {
  resident_identity : Identity; resident_bytes : list nat; accepting : bool
}.
Record Handle : Type := {
  token : nat; boot_epoch : nat; holder : nat; handle_identity : Identity;
  window_start : nat; window_length : nat
}.
Record Reservation : Type := { reserved_handle : Handle; expires : nat }.
Record Request : Type := {
  request_handle : Handle; caller_domain : nat; supplied_identity : Identity;
  offset : nat; count : nat; request_sequence : nat
}.
Record Session : Type := {
  sequence : nat; pending : option Request; response : option (list nat);
  reads : nat; authentications : nat
}.
Record Common : Type := {
  backing : option Resident;
  reservations : nat -> option Reservation;
  authority : nat -> bool;
  next_token : nat; clock : nat; current_boot : nat; current_generation : nat;
  common_counter : nat
}.
Record State : Type := { common : Common; sessions : nat -> Session }.
Record Bounds : Type := {
  byte_bound : nat; read_bound : nat; retention_bound : nat; counter_bound : nat
}.

Definition identity_eq_dec (x y : Identity) : {x = y} + {x <> y}.
Proof. repeat decide equality. Defined.
Definition handle_eq_dec (x y : Handle) : {x = y} + {x <> y}.
Proof. decide equality; try apply identity_eq_dec; repeat decide equality. Defined.

Definition set {A : Type} (f : nat -> A) (i : nat) (v : A) : nat -> A :=
  fun j => if Nat.eq_dec j i then v else f j.
Definition set_session (s : State) (h : nat) (v : Session) : State :=
  {| common := common s; sessions := set (sessions s) h v |}.
Definition set_common (s : State) (c : Common) : State :=
  {| common := c; sessions := sessions s |}.
Definition with_response (s : Session) (r : option (list nat)) : Session :=
  {| sequence := sequence s; pending := pending s; response := r;
     reads := reads s; authentications := authentications s |}.
Definition clear_pending (s : Session) : Session :=
  {| sequence := sequence s; pending := None; response := None;
     reads := reads s; authentications := authentications s |}.
Definition interval (start length total : nat) : bool :=
  (start + length <=? total).
Definition slice (bytes : list nat) (start length : nat) : list nat :=
  firstn length (skipn start bytes).
Definition current_root (c : Common) (id : Identity) : bool :=
  match root_kind id with
  | SystemImage => generation id =? current_generation c
  | UserData => true
  end.
Definition bounds_ok (b : Bounds) : bool :=
  (0 <? byte_bound b) && (byte_bound b <=? 64) &&
  (0 <? read_bound b) && (read_bound b <=? byte_bound b) &&
  (0 <? retention_bound b) && (retention_bound b <=? counter_bound b) &&
  (counter_bound b <=? 255).

(* Invalid/unpublished backing has no read path. This is one backing slot, not
   an uncharged predecessor list or an allocator. Byte values are range checked. *)
Definition resident_ok (b : Bounds) (r : Resident) : bool :=
  bounds_ok b && accepting r && (0 <? length (resident_bytes r)) &&
  (length (resident_bytes r) <=? byte_bound b) &&
  forallb (fun byte => byte <? 256) (resident_bytes r).

Definition live (c : Common) (h : Handle) (d : nat) (id : Identity) : bool :=
  match reservations c (holder h), backing c with
  | Some held, Some r =>
      if handle_eq_dec h (reserved_handle held) then
      if identity_eq_dec (handle_identity h) (resident_identity r) then
      if identity_eq_dec id (handle_identity h) then
        (holder h <? 2) && accepting r && authority c (holder h) &&
        (d =? domain (handle_identity h)) &&
        (boot_epoch h =? current_boot c) && (clock c <? expires held) &&
        current_root c (handle_identity h)
      else false else false else false
  | _, _ => false
  end.

Definition admit (b : Bounds) (s : State) (h d : nat) (id : Identity)
                 (start length : nat) : State * option Handle :=
  let c := common s in
  match backing c, reservations c h with
  | Some r, None =>
    if identity_eq_dec id (resident_identity r) then
    if resident_ok b r && (h <? 2) && authority c h && (d =? domain id) &&
       current_root c id && (0 <? length) &&
       interval start length (List.length (resident_bytes r)) &&
       (clock c + retention_bound b <=? counter_bound b) &&
       (next_token c <? counter_bound b) then
      let handle := {| token := S (next_token c); boot_epoch := current_boot c;
        holder := h; handle_identity := id; window_start := start;
        window_length := length |} in
      let held := {| reserved_handle := handle;
                     expires := clock c + retention_bound b |} in
      (set_common s {| backing := backing c;
        reservations := set (reservations c) h (Some held);
        authority := authority c; next_token := S (next_token c);
        clock := clock c; current_boot := current_boot c;
        current_generation := current_generation c; common_counter := common_counter c |},
       Some handle)
    else (s, None) else (s, None)
  | _, _ => (s, None)
  end.

Inductive Cell : Type :=
  | CommonCounter | CommonReservation (h : nat) | CommonBacking
  | PrivateSequence (h : nat) | PrivatePending (h : nat)
  | PrivateReads (h : nat) | PrivateAuthentications (h : nat)
  | RequestPublication (h : nat) | ResponsePublication (h : nat).
Definition is_common (cell : Cell) : bool :=
  match cell with
  | CommonCounter | CommonReservation _ | CommonBacking => true
  | _ => false
  end.
Definition no_common (writes : list Cell) : Prop :=
  Forall (fun cell => is_common cell = false) writes.
Record Outcome : Type := {
  after : State; payload : option (list nat); journal : list Cell
}.
Record Begun : Type := {
  begun_state : State; accepted : bool; begin_journal : list Cell
}.

Definition begin_read (b : Bounds) (s : State) (h : Handle) (d : nat)
                      (id : Identity) (off len : nat) : Begun :=
  if holder h <? 2 then
    let p := sessions s (holder h) in
    let cleared := set_session s (holder h) (with_response p None) in
    let writes := [ResponsePublication (holder h)] in
    match pending p with
    | Some _ => {| begun_state := cleared; accepted := false; begin_journal := writes |}
    | None =>
      if live (common s) h d id && (len <=? read_bound b) &&
         interval off len (window_length h) && (sequence p <? counter_bound b) then
        let q := {| request_handle := h; caller_domain := d; supplied_identity := id;
                    offset := off; count := len; request_sequence := S (sequence p) |} in
        {| begun_state := set_session s (holder h)
            {| sequence := S (sequence p); pending := Some q; response := None;
               reads := reads p; authentications := authentications p |};
           accepted := true;
           begin_journal := writes ++ [PrivateSequence (holder h); PrivatePending (holder h);
                                       RequestPublication (holder h)] |}
      else {| begun_state := cleared; accepted := false; begin_journal := writes |}
    end
  else {| begun_state := s; accepted := false; begin_journal := [] |}.

(* verify is a total executable seam called on current backing at every matched
   completion. Its contract/implementation and target refinement are not assumed. *)
Definition complete (verify : list nat -> list nat -> bool)
                    (s : State) (h seq : nat) : Outcome :=
  let unchanged := {| after := s; payload := None; journal := [] |} in
  if h <? 2 then
    let p := sessions s h in
    match pending p with
    | None => unchanged
    | Some q =>
      if seq =? request_sequence q then
        let cleared := set_session s h (clear_pending p) in
        let writes := [ResponsePublication h; PrivatePending h; RequestPublication h] in
        let refused := {| after := cleared; payload := None; journal := writes |} in
        if live (common s) (request_handle q) (caller_domain q) (supplied_identity q) &&
           (holder (request_handle q) =? h) then
          match backing (common s) with
          | None => refused
          | Some r =>
            let checked := {| sequence := sequence p; pending := None; response := None;
               reads := reads p; authentications := S (authentications p) |} in
            if verify (resident_bytes r) (root_digest (resident_identity r)) then
              let bytes := slice (resident_bytes r)
                (window_start (request_handle q) + offset q) (count q) in
              {| after := set_session s h
                   {| sequence := sequence p; pending := None; response := Some bytes;
                      reads := S (reads p); authentications := S (authentications p) |};
                 payload := Some bytes;
                 journal := writes ++ [PrivateAuthentications h; PrivateReads h;
                                        ResponsePublication h] |}
            else {| after := set_session s h checked; payload := None;
                    journal := writes ++ [PrivateAuthentications h] |}
          end
        else refused
      else unchanged
    end
  else unchanged.

Definition read_once (verify : list nat -> list nat -> bool) (b : Bounds)
                     (s : State) (h : Handle) (d : nat) (id : Identity)
                     (off len : nat) : Outcome :=
  let begun := begin_read b s h d id off len in
  if accepted begun then
    let done := complete verify (begun_state begun) (holder h)
                 (sequence (sessions (begun_state begun) (holder h))) in
    {| after := after done; payload := payload done;
       journal := begin_journal begun ++ journal done |}
  else {| after := begun_state begun; payload := None; journal := begin_journal begun |}.

Fixpoint repeat_reads (verify : list nat -> list nat -> bool) (b : Bounds)
                      (n : nat) (s : State) (h : Handle) : State * list Cell :=
  match n with
  | 0 => (s, [])
  | S k =>
    let done := read_once verify b s h (domain (handle_identity h))
                  (handle_identity h) 0 (window_length h) in
    let rest := repeat_reads verify b k (after done) h in
    (fst rest, journal done ++ snd rest)
  end.

Definition revoke (s : State) (h : nat) : State :=
  let c := common s in
  set_common s {| backing := backing c; reservations := reservations c;
    authority := set (authority c) h false; next_token := next_token c;
    clock := clock c; current_boot := current_boot c;
    current_generation := current_generation c; common_counter := common_counter c |}.
Definition at_clock (s : State) (now : nat) : State :=
  let c := common s in
  set_common s {| backing := backing c; reservations := reservations c;
    authority := authority c; next_token := next_token c; clock := now;
    current_boot := current_boot c; current_generation := current_generation c;
    common_counter := common_counter c |}.

(* Explicit lifecycle boundary: close admission, then cancel both holders before
   release. Failed modeled barrier retains closed backing and its capacity charge. *)
Definition cancel_reservations (s : State) : State :=
  let c := common s in
  {| common := {| backing := option_map (fun r =>
        {| resident_identity := resident_identity r; resident_bytes := resident_bytes r;
           accepting := false |}) (backing c);
       reservations := fun _ => None; authority := authority c;
       next_token := next_token c; clock := clock c; current_boot := current_boot c;
       current_generation := current_generation c; common_counter := common_counter c |};
     sessions := fun h => clear_pending (sessions s h) |}.
Definition retire (s : State) (barrier_completed : bool) : State :=
  let closed := cancel_reservations s in
  if barrier_completed then
    let c := common closed in
    set_common closed {| backing := None; reservations := reservations c;
      authority := authority c; next_token := next_token c; clock := clock c;
      current_boot := current_boot c; current_generation := current_generation c;
      common_counter := common_counter c |}
  else closed.

(* Read-only lifetime observation, supplied an independent admission-time byte
   expectation. Changing bytes while identity stays fixed must still fail it. *)
Definition retained_identity (c : Common) (id : Identity) (expected : list nat) : Prop :=
  exists r, backing c = Some r /\ resident_identity r = id /\ resident_bytes r = expected.
Definition retains (s : State) (expected : list nat) : Prop :=
  (forall h held, h < 2 -> reservations (common s) h = Some held ->
     retained_identity (common s) (handle_identity (reserved_handle held)) expected) /\
  (forall h q, h < 2 -> pending (sessions s h) = Some q ->
     retained_identity (common s) (handle_identity (request_handle q)) expected).
Definition window_inside (c : Common) (h : Handle) : Prop :=
  exists r, backing c = Some r /\ resident_identity r = handle_identity h /\
    window_start h + window_length h <= length (resident_bytes r).

(* Frozen first-increment targets. The intended proofs use only the executable
   definitions above. No record field contains a preservation/safety premise.

   begin_common_frame: common (begun_state (begin_read b s h d id off len)) = common s.
   complete_common_frame: common (after (complete verify s h seq)) = common s.
   begin_no_common_writes: no_common (begin_journal (begin_read b s h d id off len)).
   complete_no_common_writes: no_common (journal (complete verify s h seq)).
   repeat_fixed_reservation: common (fst (repeat_reads verify b n s h)) = common s
                            /\ no_common (snd (repeat_reads verify b n s h)).
   completion_exact: an accepted completion has a matching pending request,
     live current authority/identity, matching holder and request sequence,
     verifier acceptance on actual backing, and exactly its requested slice.
   stale_completion_unchanged: unmatched request sequence changes no state/writes.
   refused_authority_and_authentication: failed live/verifier checks return None.
   finite_sequence: accepted begin increments the previous private sequence by one
                    and keeps it <= counter_bound; exhaustion refuses.
   retirement_cancels: both modeled holder reservations and requests are absent,
                      independently of any holder acknowledgment or barrier result.
   unavailable_barrier_retains: closed backing still contains the same bytes.
   completion_retains: completion preserves reservation and in-flight byte retention.
*)
Lemma set_same : forall (A : Type) (f : nat -> A) h v, set f h v h = v.
Proof. intros. unfold set. destruct (Nat.eq_dec h h); congruence. Qed.
Lemma set_other : forall (A : Type) (f : nat -> A) h v k,
  k <> h -> set f h v k = f k.
Proof. intros. unfold set. destruct (Nat.eq_dec k h); congruence. Qed.

Theorem begin_common_frame : forall b s h d id off len,
  common (begun_state (begin_read b s h d id off len)) = common s.
Proof.
  intros. unfold begin_read. destruct (holder h <? 2); [|reflexivity].
  destruct (pending (sessions s (holder h)));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    reflexivity.
Qed.
Theorem complete_common_frame : forall verify s h seq,
  common (after (complete verify s h seq)) = common s.
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  destruct (pending (sessions s h)); [|reflexivity].
  repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    destruct (backing (common s));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end; reflexivity.
Qed.

Theorem begin_no_common_writes : forall b s h d id off len,
  no_common (begin_journal (begin_read b s h d id off len)).
Proof.
  intros. unfold begin_read. destruct (holder h <? 2);
    [destruct (pending (sessions s (holder h)))|];
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    repeat constructor.
Qed.
Theorem complete_no_common_writes : forall verify s h seq,
  no_common (journal (complete verify s h seq)).
Proof.
  intros. unfold complete. destruct (h <? 2);
    [destruct (pending (sessions s h))|];
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    try destruct (backing (common s));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    repeat constructor.
Qed.
Theorem read_common_frame : forall verify b s h d id off len,
  common (after (read_once verify b s h d id off len)) = common s.
Proof.
  intros. unfold read_once. destruct (accepted (begin_read b s h d id off len)); simpl.
  - rewrite complete_common_frame. apply begin_common_frame.
  - apply begin_common_frame.
Qed.
Theorem read_no_common_writes : forall verify b s h d id off len,
  no_common (journal (read_once verify b s h d id off len)).
Proof.
  intros. unfold read_once. destruct (accepted (begin_read b s h d id off len)); simpl.
  - apply Forall_app. split; [apply begin_no_common_writes|apply complete_no_common_writes].
  - apply begin_no_common_writes.
Qed.
Theorem repeat_fixed_reservation : forall verify b n s h,
  common (fst (repeat_reads verify b n s h)) = common s /\
  no_common (snd (repeat_reads verify b n s h)).
Proof.
  intros verify b n. induction n as [|n IH]; intros s h; simpl.
  - split; [reflexivity|constructor].
  - destruct (IH (after (read_once verify b s h (domain (handle_identity h))
                      (handle_identity h) 0 (window_length h))) h) as [Hframe Hwrites].
    split.
    + rewrite Hframe. apply read_common_frame.
    + apply Forall_app. split; [apply read_no_common_writes|exact Hwrites].
Qed.

Theorem admission_installs_exact_window : forall b s h d id start len s' handle,
  admit b s h d id start len = (s', Some handle) ->
  exists r held,
    backing (common s') = Some r /\ resident_identity r = id /\
    handle_identity handle = id /\ holder handle = h /\
    window_start handle = start /\ window_length handle = len /\
    start + len <= length (resident_bytes r) /\ 0 < len /\
    h < 2 /\ d = domain id /\ authority (common s') h = true /\
    reservations (common s') h = Some held /\ reserved_handle held = handle /\
    token handle <= counter_bound b /\ expires held <= counter_bound b /\
    window_inside (common s') handle.
Proof.
  intros b s h d id start len s' handle H.
  unfold admit in H. destruct (backing (common s)) as [r|] eqn:Hr;
    [|discriminate]. destruct (reservations (common s) h); [discriminate|].
  destruct (identity_eq_dec id (resident_identity r)) as [Hid|Hid]; [|discriminate].
  match type of H with context [if ?test then _ else _] => destruct test eqn:Hadmit end;
    [|discriminate].
  inversion H; subst s' handle; clear H. repeat rewrite andb_true_iff in Hadmit.
  destruct Hadmit as [[[[[[[[Hresident Hholder] Hauth] Hdomain] Hroot] Hlen] Hwindow] Hexpiry] Htoken].
  apply Nat.ltb_lt in Hholder. apply Nat.ltb_lt in Hlen.
  apply Nat.ltb_lt in Htoken. apply Nat.eqb_eq in Hdomain.
  apply Nat.leb_le in Hexpiry. unfold interval in Hwindow. apply Nat.leb_le in Hwindow.
  exists r, {| reserved_handle := {| token := S (next_token (common s));
    boot_epoch := current_boot (common s); holder := h; handle_identity := id;
    window_start := start; window_length := len |};
    expires := clock (common s) + retention_bound b |}.
  simpl. rewrite set_same. repeat split; auto; try lia.
  exists r. repeat split; auto.
Qed.

Theorem begin_stores_bounded_request : forall b s h d id off len,
  accepted (begin_read b s h d id off len) = true ->
  exists q,
    pending (sessions (begun_state (begin_read b s h d id off len)) (holder h)) = Some q /\
    request_handle q = h /\ caller_domain q = d /\ supplied_identity q = id /\
    offset q = off /\ count q = len /\ off + len <= window_length h /\
    len <= read_bound b /\ live (common s) h d id = true /\
    request_sequence q = S (sequence (sessions s (holder h))) /\
    request_sequence q <= counter_bound b /\
    sequence (sessions (begun_state (begin_read b s h d id off len)) (holder h)) =
      request_sequence q.
Proof.
  intros b s h d id off len H. unfold begin_read in *.
  destruct (holder h <? 2); [|discriminate].
  destruct (pending (sessions s (holder h))); [discriminate|].
  match type of H with context [if ?test then _ else _] => destruct test eqn:Hok end;
    [|discriminate].
  apply andb_true_iff in Hok. destruct Hok as [Hok Hseq].
  apply andb_true_iff in Hok. destruct Hok as [Hok Hrange].
  apply andb_true_iff in Hok. destruct Hok as [Hlive Hlen].
  apply Nat.ltb_lt in Hseq. apply Nat.leb_le in Hlen.
  unfold interval in Hrange. apply Nat.leb_le in Hrange.
  exists {| request_handle := h; caller_domain := d; supplied_identity := id;
    offset := off; count := len; request_sequence := S (sequence (sessions s (holder h))) |}.
  simpl. rewrite set_same. simpl. repeat split; auto; lia.
Qed.

Theorem sequence_exhaustion_refuses : forall b s h d id off len,
  counter_bound b <= sequence (sessions s (holder h)) ->
  accepted (begin_read b s h d id off len) = false.
Proof.
  intros b s h d id off len H. destruct (accepted (begin_read b s h d id off len)) eqn:Hbegin;
    [|reflexivity]. apply begin_stores_bounded_request in Hbegin.
  destruct Hbegin as [q [_ [_ [_ [_ [_ [_ [_ [_ [_ [Hseq [Hbound _]]]]]]]]]]]]. lia.
Qed.

Theorem completion_exact : forall verify s h seq bytes,
  payload (complete verify s h seq) = Some bytes ->
  exists q r,
    pending (sessions s h) = Some q /\ seq = request_sequence q /\ h < 2 /\
    holder (request_handle q) = h /\
    live (common s) (request_handle q) (caller_domain q) (supplied_identity q) = true /\
    backing (common s) = Some r /\
    verify (resident_bytes r) (root_digest (resident_identity r)) = true /\
    bytes = slice (resident_bytes r) (window_start (request_handle q) + offset q) (count q).
Proof.
  intros verify s h seq bytes H. unfold complete in H.
  destruct (h <? 2) eqn:Hholder; [|discriminate].
  destruct (pending (sessions s h)) as [q|] eqn:Hpending; [|discriminate].
  destruct (seq =? request_sequence q) eqn:Hseq; [|discriminate].
  destruct (live (common s) (request_handle q) (caller_domain q) (supplied_identity q) &&
            (holder (request_handle q) =? h)) eqn:Hlive; [|discriminate].
  destruct (backing (common s)) as [r|] eqn:Hr; [|discriminate].
  destruct (verify (resident_bytes r) (root_digest (resident_identity r))) eqn:Hverify;
    [|discriminate]. inversion H; subst bytes.
  apply Nat.ltb_lt in Hholder. apply Nat.eqb_eq in Hseq.
  apply andb_true_iff in Hlive. destruct Hlive as [Hlive Heq].
  apply Nat.eqb_eq in Heq. exists q, r. repeat split; auto.
Qed.

Theorem stale_completion_unchanged : forall verify s h seq q,
  pending (sessions s h) = Some q -> seq <> request_sequence q ->
  after (complete verify s h seq) = s /\
  payload (complete verify s h seq) = None /\ journal (complete verify s h seq) = [].
Proof.
  intros. unfold complete. destruct (h <? 2); [|repeat split; reflexivity].
  rewrite H. destruct (seq =? request_sequence q) eqn:Hseq;
    [apply Nat.eqb_eq in Hseq; contradiction|repeat split; reflexivity].
Qed.

Theorem current_authority_refuses : forall verify s h seq q,
  pending (sessions s h) = Some q ->
  live (common s) (request_handle q) (caller_domain q) (supplied_identity q) = false ->
  payload (complete verify s h seq) = None.
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  rewrite H. destruct (seq =? request_sequence q); [|reflexivity].
  rewrite H0. reflexivity.
Qed.
Theorem failed_authentication_refuses : forall verify s h seq r,
  backing (common s) = Some r ->
  verify (resident_bytes r) (root_digest (resident_identity r)) = false ->
  payload (complete verify s h seq) = None.
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  destruct (pending (sessions s h)); [|reflexivity].
  repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    rewrite ?H, ?H0; reflexivity.
Qed.

Theorem retirement_cancels : forall s barrier h,
  reservations (common (retire s barrier)) h = None /\
  pending (sessions (retire s barrier) h) = None /\
  sequence (sessions (retire s barrier) h) = sequence (sessions s h).
Proof. intros. unfold retire. destruct barrier; repeat split; reflexivity. Qed.
Theorem unavailable_barrier_keeps_backing : forall s r,
  backing (common s) = Some r ->
  backing (common (retire s false)) =
    Some {| resident_identity := resident_identity r; resident_bytes := resident_bytes r;
            accepting := false |}.
Proof. intros. unfold retire, cancel_reservations, set_common; simpl. rewrite H. reflexivity. Qed.

(* A matched completion can only remove its holder's pending request. Other
   sessions and the entire common state remain framed, even on refusal. *)
Theorem completion_removes_or_preserves_pending : forall verify s h seq k,
  pending (sessions (after (complete verify s h seq)) k) = None \/
  pending (sessions (after (complete verify s h seq)) k) = pending (sessions s k).
Proof.
  intros. unfold complete. destruct (h <? 2); [|right; reflexivity].
  destruct (pending (sessions s h)); [|right; reflexivity].
  destruct (seq =? request_sequence r); [|right; reflexivity].
  destruct (Nat.eq_dec k h) as [Heq|Hneq].
  - subst k. repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      destruct (backing (common s));
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      simpl; rewrite set_same; simpl;
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      left; reflexivity.
  - repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      destruct (backing (common s));
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      simpl; rewrite set_other by exact Hneq;
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      right; reflexivity.
Qed.
Theorem completion_retains : forall verify s h seq expected,
  retains s expected -> retains (after (complete verify s h seq)) expected.
Proof.
  intros verify s h seq expected [Hheld Hpending]. split.
  - intros. rewrite complete_common_frame in *. eapply Hheld; eauto.
  - intros k q Hk Hq. destruct (completion_removes_or_preserves_pending verify s h seq k)
      as [Hnone|Hsame].
    + rewrite Hnone in Hq. discriminate.
    + rewrite Hsame in Hq. unfold retained_identity.
      rewrite complete_common_frame. apply (Hpending k q Hk Hq).
Qed.
Theorem begun_request_within_backing : forall b s h d id off len,
  window_inside (common s) h ->
  accepted (begin_read b s h d id off len) = true ->
  exists q r,
    pending (sessions (begun_state (begin_read b s h d id off len)) (holder h)) = Some q /\
    backing (common (begun_state (begin_read b s h d id off len))) = Some r /\
    resident_identity r = handle_identity (request_handle q) /\
    window_start (request_handle q) + offset q + count q <= length (resident_bytes r).
Proof.
  intros b s h d id off len [r [Hr [Hid Hwindow]]] Hbegin.
  destruct (begin_stores_bounded_request b s h d id off len Hbegin)
    as [q [Hq [Hhandle [_ [_ [Hoff [Hlen [Hrange _]]]]]]]].
  exists q, r. rewrite begin_common_frame. repeat split; auto.
  - rewrite Hhandle. exact Hid.
  - rewrite Hhandle, Hoff, Hlen. lia.
Qed.

(* The exact completion theorem is about any state. This corollary supplies its
   non-forged pending-request provenance from executable begin, and admission's
   window theorem supplies window_inside. It assumes no preservation conclusion. *)
Theorem admitted_completion_within_window : forall verify b s h d id off len seq bytes,
  window_inside (common s) h ->
  accepted (begin_read b s h d id off len) = true ->
  payload (complete verify (begun_state (begin_read b s h d id off len)) (holder h) seq) = Some bytes ->
  exists r,
    backing (common s) = Some r /\ resident_identity r = handle_identity h /\
    window_start h + off + len <= length (resident_bytes r) /\
    bytes = slice (resident_bytes r) (window_start h + off) len.
Proof.
  intros verify b s h d id off len seq bytes Hwindow Hbegin Hdone.
  destruct (begin_stores_bounded_request b s h d id off len Hbegin)
    as [q [Hq [Hhandle [_ [_ [Hoff [Hlen [Hrange _]]]]]]]].
  destruct (completion_exact verify (begun_state (begin_read b s h d id off len))
             (holder h) seq bytes Hdone)
    as [actual [r [Hactual [_ [_ [_ [_ [Hr [_ Hbytes]]]]]]]]].
  rewrite Hq in Hactual. inversion Hactual; subst actual.
  rewrite begin_common_frame in Hr.
  destruct Hwindow as [old [Hold [Hid Hbound]]].
  rewrite Hr in Hold. inversion Hold; subst old.
  exists r. repeat split; auto.
  - lia.
  - rewrite Hhandle, Hoff, Hlen in Hbytes. exact Hbytes.
Qed.

Definition fixture_bounds : Bounds :=
  {| byte_bound := 8; read_bound := 3; retention_bound := 4; counter_bound := 15 |}.
Definition fixture_identity (kind : RootKind) : Identity :=
  {| owner := 1; domain := 7; object_id := 1; version := 1;
     root_kind := kind; generation := 1; root_digest := [11; 22] |}.
Definition fixture_resident (kind : RootKind) : Resident :=
  {| resident_identity := fixture_identity kind; resident_bytes := [97; 98; 99]; accepting := true |}.
Definition empty_session : Session :=
  {| sequence := 0; pending := None; response := None; reads := 0; authentications := 0 |}.
Definition initial (kind : RootKind) : State :=
  {| common := {| backing := Some (fixture_resident kind); reservations := fun _ => None;
     authority := fun _ => true; next_token := 0; clock := 0; current_boot := 0;
     current_generation := 1; common_counter := 0 |}; sessions := fun _ => empty_session |}.
Definition fixture_handle (kind : RootKind) (h : nat) : Handle :=
  {| token := S h; boot_epoch := 0; holder := h; handle_identity := fixture_identity kind;
     window_start := h; window_length := 3 - h |}.
Definition fixture_reservation (kind : RootKind) (h : nat) : Reservation :=
  {| reserved_handle := fixture_handle kind h; expires := 4 |}.
Definition one_holder (kind : RootKind) : State :=
  fst (admit fixture_bounds (initial kind) 0 7 (fixture_identity kind) 0 3).
Definition two_holders (kind : RootKind) : State :=
  fst (admit fixture_bounds (one_holder kind) 1 7 (fixture_identity kind) 1 2).
Definition fixture_verify (bytes digest : list nat) : bool :=
  if list_eq_dec Nat.eq_dec bytes [97; 98; 99] then
    if list_eq_dec Nat.eq_dec digest [11; 22] then true else false else false.
Definition read_fixture (kind : RootKind) (s : State) (h off len : nat) : Outcome :=
  read_once fixture_verify fixture_bounds s (fixture_handle kind h) 7 (fixture_identity kind) off len.
Definition two_pending (kind : RootKind) : State :=
  begun_state (begin_read fixture_bounds
    (begun_state (begin_read fixture_bounds (two_holders kind)
      (fixture_handle kind 0) 7 (fixture_identity kind) 0 3))
    (fixture_handle kind 1) 7 (fixture_identity kind) 0 2).
Definition with_bytes (s : State) (bytes : list nat) : State :=
  let c := common s in
  set_common s {| backing := option_map (fun r => {| resident_identity := resident_identity r;
    resident_bytes := bytes; accepting := accepting r |}) (backing c);
    reservations := reservations c; authority := authority c; next_token := next_token c;
    clock := clock c; current_boot := current_boot c; current_generation := current_generation c;
    common_counter := common_counter c |}.

Definition witness_Identity : Identity := fixture_identity UserData.
Definition witness_Resident : Resident := fixture_resident UserData.
Definition witness_Handle : Handle := fixture_handle UserData 0.
Definition witness_Reservation : Reservation := fixture_reservation UserData 0.
Definition witness_Request : Request := {| request_handle := witness_Handle;
  caller_domain := 7; supplied_identity := witness_Identity; offset := 0; count := 3;
  request_sequence := 1 |}.
Definition witness_Session : Session := empty_session.
Definition witness_Common : Common := common (two_holders UserData).
Definition witness_State : State := two_holders UserData.
Definition witness_Bounds : Bounds := fixture_bounds.
Definition witness_Outcome : Outcome := read_fixture UserData (two_holders UserData) 0 0 3.
Definition witness_Begun : Begun := begin_read fixture_bounds (two_holders UserData)
  (fixture_handle UserData 0) 7 (fixture_identity UserData) 0 3.

(* Both root kinds use the same transitions. The fixture verifier has explicit
   independent expected bytes and root; it is not a SHA-256 implementation. *)
Example two_independent_admissions : forall kind,
  admit fixture_bounds (initial kind) 0 7 (fixture_identity kind) 0 3 =
    (one_holder kind, Some (fixture_handle kind 0)) /\
  admit fixture_bounds (one_holder kind) 1 7 (fixture_identity kind) 1 2 =
    (two_holders kind, Some (fixture_handle kind 1)).
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example exact_independent_payloads : forall kind,
  payload (read_fixture kind (two_holders kind) 0 0 3) = Some [97; 98; 99] /\
  payload (read_fixture kind (two_holders kind) 1 0 2) = Some [98; 99] /\
  payload (read_fixture kind (two_holders kind) 0 3 0) = Some [].
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.
Example two_accepted_transfers : forall kind,
  payload (complete fixture_verify (two_pending kind) 0 1) = Some [97; 98; 99] /\
  payload (complete fixture_verify (two_pending kind) 1 1) = Some [98; 99].
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example repeated_reads_with_fixed_admissions : forall kind,
  let s := fst (repeat_reads fixture_verify fixture_bounds 3 (two_holders kind) (fixture_handle kind 0)) in
  let t := fst (repeat_reads fixture_verify fixture_bounds 3 s (fixture_handle kind 1)) in
  reads (sessions t 0) = 3 /\ reads (sessions t 1) = 3 /\
  response (sessions t 0) = Some [97; 98; 99] /\ response (sessions t 1) = Some [98; 99] /\
  next_token (common t) = 2.
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.
Example revoked_inflight_read_refuses : forall kind,
  payload (complete fixture_verify (revoke (two_pending kind) 0) 0 1) = None /\
  payload (complete fixture_verify (revoke (two_pending kind) 0) 1 1) = Some [98; 99].
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example expired_inflight_read_refuses : forall kind,
  payload (complete fixture_verify (at_clock (two_pending kind) 4) 0 1) = None.
Proof. intros []; vm_compute; reflexivity. Qed.
Example corrupt_retained_bytes_refuse_authentication : forall kind,
  payload (complete fixture_verify (with_bytes (two_pending kind) [0; 0; 0]) 0 1) = None /\
  payload (complete fixture_verify (with_bytes (two_pending kind) [0; 0; 0]) 1 1) = None.
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example omitted_authentication_serves_wrong_bytes : forall kind,
  payload (complete (fun _ _ => true) (with_bytes (two_pending kind) [0; 0; 0]) 0 1) = Some [0; 0; 0].
Proof. intros []; vm_compute; reflexivity. Qed.
Example wrong_domain_refuses : forall kind,
  payload (read_once fixture_verify fixture_bounds (two_holders kind)
    (fixture_handle kind 0) 8 (fixture_identity kind) 0 3) = None.
Proof. intros []; vm_compute; reflexivity. Qed.
Example wrong_version_and_root_refuse : forall kind,
  let wrong_version := {| owner := 1; domain := 7; object_id := 1; version := 2;
    root_kind := kind; generation := 1; root_digest := [11; 22] |} in
  let wrong_root := {| owner := 1; domain := 7; object_id := 1; version := 1;
    root_kind := kind; generation := 1; root_digest := [22; 11] |} in
  payload (read_once fixture_verify fixture_bounds (two_holders kind)
    (fixture_handle kind 0) 7 wrong_version 0 3) = None /\
  payload (read_once fixture_verify fixture_bounds (two_holders kind)
    (fixture_handle kind 0) 7 wrong_root 0 3) = None.
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example outside_window_refuses : forall kind,
  payload (read_fixture kind (two_holders kind) 1 1 2) = None.
Proof. intros []; vm_compute; reflexivity. Qed.
Example stale_completion_keeps_successor : forall kind,
  let first := read_fixture kind (two_holders kind) 0 0 3 in
  let successor := begun_state (begin_read fixture_bounds (after first)
    (fixture_handle kind 0) 7 (fixture_identity kind) 0 3) in
  after (complete fixture_verify successor 0 1) = successor /\
  journal (complete fixture_verify successor 0 1) = [] /\
  payload (complete fixture_verify successor 0 2) = Some [97; 98; 99].
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.
Example expired_system_generation_refuses :
  let s := two_pending SystemImage in
  let c := common s in
  let changed := set_common s {| backing := backing c; reservations := reservations c;
    authority := authority c; next_token := next_token c; clock := clock c;
    current_boot := current_boot c; current_generation := 2; common_counter := common_counter c |} in
  payload (complete fixture_verify changed 0 1) = None.
Proof. vm_compute; reflexivity. Qed.
Example retirement_does_not_wait_for_holders : forall kind,
  payload (complete fixture_verify (retire (two_pending kind) false) 0 1) = None /\
  payload (complete fixture_verify (retire (two_pending kind) false) 1 1) = None /\
  backing (common (retire (two_pending kind) false)) =
    Some {| resident_identity := fixture_identity kind; resident_bytes := [97; 98; 99]; accepting := false |}.
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.

Lemma fixture_retains_reservations_and_transfers : forall kind,
  retains (two_pending kind) [97; 98; 99].
Proof.
  intros kind. split; intros h value Hh Hvalue;
    assert (h = 0 \/ h = 1) as Hcases by lia; destruct Hcases; subst h;
    destruct kind; vm_compute in Hvalue; inversion Hvalue; subst value;
    unfold retained_identity; eexists; repeat split; vm_compute; reflexivity.
Qed.
Theorem same_identity_mutation_breaks_live_retention : forall kind,
  ~ retains (with_bytes (two_pending kind) [0; 0; 0]) [97; 98; 99].
Proof.
  intros kind [Hheld _].
  assert (reservations (common (with_bytes (two_pending kind) [0; 0; 0])) 0 =
          Some (fixture_reservation kind 0)) as Hreservation.
  { destruct kind; vm_compute; reflexivity. }
  specialize (Hheld 0 (fixture_reservation kind 0) ltac:(lia) Hreservation).
  destruct Hheld as [r [Hr [_ Hbytes]]]. destruct kind; vm_compute in Hr;
    inversion Hr; subst r; discriminate Hbytes.
Qed.
Theorem retained_transfer_mutation_is_detected_without_reservation : forall kind,
  let changed := with_bytes (two_pending kind) [0; 0; 0] in
  let c := common changed in
  let no_reservations := set_common changed {| backing := backing c;
    reservations := fun _ => None; authority := authority c; next_token := next_token c;
    clock := clock c; current_boot := current_boot c; current_generation := current_generation c;
    common_counter := common_counter c |} in
  ~ retains no_reservations [97; 98; 99].
Proof.
  intros kind changed c no_reservations [_ Hpending].
  specialize (Hpending 0 {| request_handle := fixture_handle kind 0; caller_domain := 7;
    supplied_identity := fixture_identity kind; offset := 0; count := 3; request_sequence := 1 |} ltac:(lia)).
  destruct kind; vm_compute in Hpending.
  -
    specialize (Hpending (eq_refl _)). destruct Hpending as [r [Hr [_ Hbytes]]].
    inversion Hr; subst r; discriminate Hbytes.
  - specialize (Hpending (eq_refl _)). destruct Hpending as [r [Hr [_ Hbytes]]].
    inversion Hr; subst r; discriminate Hbytes.
Qed.
Theorem common_increment_then_decrement_is_rejected : forall writes,
  ~ no_common ([CommonCounter; CommonCounter] ++ writes).
Proof. intros writes H. inversion H. discriminate. Qed.
Theorem refused_begin_preserves_pending : forall b s h d id off len q,
  pending (sessions s (holder h)) = Some q ->
  pending (sessions (begun_state (begin_read b s h d id off len)) (holder h)) = Some q.
Proof.
  intros. unfold begin_read. destruct (holder h <? 2); [|exact H].
  rewrite H. simpl. rewrite set_same. exact H.
Qed.
Theorem complete_preserves_sequences : forall verify s h seq k,
  sequence (sessions (after (complete verify s h seq)) k) = sequence (sessions s k).
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  destruct (pending (sessions s h)); [|reflexivity].
  destruct (seq =? request_sequence r); [|reflexivity].
  repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    destruct (backing (common s));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    simpl; unfold set; destruct (Nat.eq_dec k h); subst; reflexivity.
Qed.