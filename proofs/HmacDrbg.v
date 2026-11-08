(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   HmacDrbg.v

   Functional reference for HMAC_DRBG over SHA-256 (NIST SP 800-90A Rev. 1,
   s10.1.2 and s9) over [Sha256.v](Sha256.v#hmac_sha256), with the explicit
   seeding-discipline hypothesis required by R-15-241d.

   Scope and assurance boundary:
   - Functional layer and seeding-hypothesis statement only: no binary
     corresponds to this file, no constant-time property is claimed (R-05-062,
     R-05-067), no masking claim is made (R-05-004a), and no computational
     reduction or distributional claim is made (R-05-077a; see
     [THIRD-PARTY.md](../THIRD-PARTY.md) for the upstream VST `hmacdrbg/` and
     `hmacfcf/` disposition).
   - Under the names prediction resistance and backtracking resistance, this
     file states the computational ordering and freshness properties of the
     transcribed functions: a draw emits output from the pre-update state and
     returns the post-draw updated state; a reseed consumes an unused entropy
     string from the pool and updates the state from it.
   - `Require Import Sha256.` brings in [Sha256.v](Sha256.v) and its shared
     [ProofSupport.v](ProofSupport.v) and [CryptoLists.v](CryptoLists.v) laws.

   Representation and register readings:
   1. Bit strings follow [Sha256.v](Sha256.v) (bytes MSB-first); lengths are in
      bits (`requested_number_of_bits`, `outlen`).
   2. `DrbgState` carries `key`, `value`, and `reseed_counter` (s10.1.2.1),
      while security strength and prediction resistance live on
      `SeedingDiscipline` (s9.1).
   3. The entropy source is an ordered pool of conditioned root outputs
      (R-15-241c), consumed one string per instantiation or reseed at the
      discipline's `seed_length`. Pool exhaustion halts the run fail-stop
      (R-15-241b) with no last-known-good fallback.
   4. `SeedingDiscipline` and `Disciplined` encode R-15-241d's explicit
      seeding hypothesis: seed and nonce lengths, draw and interval bounds,
      transition reseed map, and prediction-resistance flag. Concrete platform
      figures and SP 800-90A Table 2 ceilings (2^48 draws, 2^19 bits per
      request, 2^35 entropy bits) are left open at R-15-241d rather than
      inferred from R-05-058a's asymmetric Category 5 strength (compare
      [AesGcm.v](AesGcm.v)).
   5. Lifecycle and lock-state transitions match [RotFirmware.v](RotFirmware.v#Lifecycle):
      five acyclic lifecycle edges (R-09-032) and two lock-state edges
      (R-09-017, R-09-018, R-09-019).
   6. The s9.3.1 envelope reseeds before a draw when the counter exceeds the
      interval or prediction resistance is requested, passing additional input
      to the reseed while `generate` (s10.1.2.5 step 1) refuses out-of-interval
      draws directly.

   Non-vacuity and validation vectors (R-05-165, R-05-166):
   - `demo` inhabits `Disciplined`; four disciplines violating individual
     clauses, three runs violating pool/draw constraints, and four mutated
     constructions (inverted update branch, pre-draw update, entropy-ignoring
     reseed, zero-initialized counter) are refuted.
   - The three validation vectors (`no_reseed`, `pr_false`, `pr_true`) are
     `COUNT = 0` of `[SHA-256]` from NIST CAVP `drbgtestvectors.zip` (CAVS
     14.3, generated 2013-04-02), cross-checked against an independent Python
     transcription.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-058a R-05-062 R-05-067 R-05-077a R-05-163 R-05-165 R-05-166
      R-09-017 R-09-018 R-09-019 R-09-032 R-15-241b R-15-241c R-15-241d
   SHA256: b460e1da2b3f53336ee43a641e39ab47b1dec7cfaad66c9a9944bfefbd0bb364
   (*| END derived |*)
   ========================================================================= *)

Require Import Sha256.

Open Scope list_scope.

(* Casts eq_refl to the goal unevaluated so only Qed evaluates it. *)
Local Ltac vm_reflexivity :=
  intros; lazymatch goal with |- _ = ?b => vm_cast_no_check (@eq_refl _ b) end.

(* -------------------------------------------------------------------------
   Helpers this file adds to Sha256.v's, in the same idiom.
   ------------------------------------------------------------------------- *)

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. induction n as [| n IH]; [reflexivity | exact IH]. Qed.

Lemma andb_left : forall a b : bool, andb a b = true -> a = true.
Proof. intros a b H. destruct a; [reflexivity | discriminate H]. Qed.

Lemma andb_right : forall a b : bool, andb a b = true -> b = true.
Proof. intros a b H. destruct a; [exact H | discriminate H]. Qed.

Fixpoint fresh_pool (p : list (list bool)) : bool :=
  match p with
  | nil => true
  | e :: rest => andb (all_of (fun f => negb (bits_eqb e f)) rest) (fresh_pool rest)
  end.

(* -------------------------------------------------------------------------
   The sizes, which are the standard's (Table 2 for SHA-256) read from
   Sha256.v, and the four literals of s10.1.2.2 and s10.1.2.3.
   ------------------------------------------------------------------------- *)

Definition outlen_bits : nat := digest_bits.
Definition outlen_bytes : nat := Nat.div outlen_bits byte_bits.

Definition zero_key : list bool := bytes_from (repeat_of outlen_bytes 0x00).
Definition one_value : list bool := bytes_from (repeat_of outlen_bytes 0x01).
Definition separator_zero : list bool := bits_of_byte 0x00.
Definition separator_one : list bool := bits_of_byte 0x01.

Example the_initial_key_and_value_are_outlen_long :
  andb (Nat.eqb (length_of zero_key) outlen_bits) (Nat.eqb (length_of one_value) outlen_bits) = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The internal state, s10.1.2.1, and HMAC_DRBG_Update, s10.1.2.2: two
   passes, the second taken only when provided_data is not empty.
   ------------------------------------------------------------------------- *)

Record DrbgState : Type := {
  key : list bool;
  value : list bool;
  reseed_counter : nat
}.

Definition hmac_drbg_update (provided k v : list bool) : list bool * list bool :=
  let k1 := hmac_sha256 k (v ++ separator_zero ++ provided) in
  let v1 := hmac_sha256 k1 v in
  if provided is nil then pair k1 v1
  else let k2 := hmac_sha256 k1 (v1 ++ separator_one ++ provided) in
       pair k2 (hmac_sha256 k2 v1).

(* The second pass taken on the wrong branch: run when provided_data is
   empty and skipped when it is not. It is an update in every other respect
   and every published case here provides nothing, so it is the defect the
   corpus's empty additional inputs exist to catch. *)
Definition update_with_its_branch_inverted (provided k v : list bool) : list bool * list bool :=
  let k1 := hmac_sha256 k (v ++ separator_zero ++ provided) in
  let v1 := hmac_sha256 k1 v in
  if provided is nil
  then let k2 := hmac_sha256 k1 (v1 ++ separator_one ++ provided) in
       pair k2 (hmac_sha256 k2 v1)
  else pair k1 v1.

(* -------------------------------------------------------------------------
   Instantiate (s10.1.2.3) and reseed (s10.1.2.4), each parameterized over
   the update it runs, and instantiate over the counter it starts at, so
   that each alternative is the standard's with one thing exchanged.
   ------------------------------------------------------------------------- *)

Definition instantiate_over (update : list bool -> list bool -> list bool -> list bool * list bool)
                            (counter : nat) (entropy nonce personalization : list bool)
  : DrbgState :=
  let kv := update (entropy ++ nonce ++ personalization) zero_key one_value in
  {| key := fst kv; value := snd kv; reseed_counter := counter |}.

Definition instantiate : list bool -> list bool -> list bool -> DrbgState :=
  instantiate_over hmac_drbg_update 1.

Definition instantiate_with_the_counter_at_zero : list bool -> list bool -> list bool -> DrbgState :=
  instantiate_over hmac_drbg_update 0.

Definition instantiate_with_the_inverted_update : list bool -> list bool -> list bool -> DrbgState :=
  instantiate_over update_with_its_branch_inverted 1.

Definition reseed (s : DrbgState) (entropy additional : list bool) : DrbgState :=
  let kv := hmac_drbg_update (entropy ++ additional) (key s) (value s) in
  {| key := fst kv; value := snd kv; reseed_counter := 1 |}.

(* A reseed that reads its additional input and not its entropy, which
   resets the counter like the standard's and leaves the state a function
   of the old state alone. *)
Definition reseed_ignoring_its_entropy (s : DrbgState) (entropy additional : list bool) : DrbgState :=
  let kv := hmac_drbg_update additional (key s) (value s) in
  {| key := fst kv; value := snd kv; reseed_counter := 1 |}.

(* -------------------------------------------------------------------------
   Generate, s10.1.2.5. Steps 2 through 7 are `generate_core`: the optional
   update on the additional input, the blocks drawn until the request is
   met, the leftmost requested bits, and then the update that leaves the
   state, with the counter advanced. Step 1, the refusal past the interval,
   is `generate`.
   ------------------------------------------------------------------------- *)

Fixpoint draw_blocks (fuel : nat) (k v acc : list bool) : list bool * list bool :=
  match fuel with
  | 0 => pair acc v
  | S f => let v' := hmac_sha256 k v in draw_blocks f k v' (acc ++ v')
  end.

Definition blocks_for (bits : nat) : nat := Nat.div (bits + outlen_bits - 1) outlen_bits.

(* Checked where it rounds and not only at the corpus's 1024 bits, which is
   four whole blocks and so is the one request that cannot go wrong: a
   request of one bit still costs a block, and a request one bit past a
   block costs another. *)
Example a_partial_block_still_costs_a_block :
  andb (andb (Nat.eqb (blocks_for 0) 0) (Nat.eqb (blocks_for 1) 1))
       (andb (Nat.eqb (blocks_for outlen_bits) 1)
             (Nat.eqb (blocks_for (S outlen_bits)) 2)) = true.
Proof. vm_reflexivity. Qed.

Definition update_on (additional : list bool) (k v : list bool) : list bool * list bool :=
  if additional is nil then pair k v else hmac_drbg_update additional k v.

Definition generate_core (s : DrbgState) (bits : nat) (additional : list bool)
  : list bool * DrbgState :=
  let kv0 := update_on additional (key s) (value s) in
  let drawn := draw_blocks (blocks_for bits) (fst kv0) (snd kv0) nil in
  let kv1 := hmac_drbg_update additional (fst kv0) (snd drawn) in
  pair (take_of bits (fst drawn))
       {| key := fst kv1; value := snd kv1; reseed_counter := S (reseed_counter s) |}.

(* Step 6 run before step 4: the state is updated and the blocks are then
   drawn from it, so the value that leaves the draw is the last block that
   left it too. It returns the requested length and advances the counter
   like the standard's. *)
Definition generate_core_updating_before_it_emits (s : DrbgState) (bits : nat)
                                                   (additional : list bool)
  : list bool * DrbgState :=
  let kv0 := update_on additional (key s) (value s) in
  let kv1 := hmac_drbg_update additional (fst kv0) (snd kv0) in
  let drawn := draw_blocks (blocks_for bits) (fst kv1) (snd kv1) nil in
  pair (take_of bits (fst drawn))
       {| key := fst kv1; value := snd drawn; reseed_counter := S (reseed_counter s) |}.

Definition generate (interval : nat) (s : DrbgState) (bits : nat) (additional : list bool)
  : option (list bool * DrbgState) :=
  if Nat.ltb interval (reseed_counter s) then None else Some (generate_core s bits additional).

(* -------------------------------------------------------------------------
   The transitions R-15-241d reseeds on: R-09-032's lifecycle edges and
   R-09-017 through R-09-019's lock-state edges, read from RotFirmware.v's
   enumeration of the states and the register's sentences on the edges.
   ------------------------------------------------------------------------- *)

Inductive Lifecycle : Type :=
| Raw
| TestState
| Development
| Production
| Rma.

Inductive LockState : Type :=
| BeforeFirstUnlock
| AfterFirstUnlock.

Inductive Transition : Type :=
| LifecycleEdge (from to : Lifecycle)
| LockEdge (from to : LockState).

Definition lifecycle_eqb (a b : Lifecycle) : bool :=
  match a, b with
  | Raw, Raw => true
  | TestState, TestState => true
  | Development, Development => true
  | Production, Production => true
  | Rma, Rma => true
  | _, _ => false
  end.

Definition lock_eqb (a b : LockState) : bool :=
  match a, b with
  | BeforeFirstUnlock, BeforeFirstUnlock => true
  | AfterFirstUnlock, AfterFirstUnlock => true
  | _, _ => false
  end.

Definition transition_eqb (a b : Transition) : bool :=
  match a, b with
  | LifecycleEdge f1 t1, LifecycleEdge f2 t2 => andb (lifecycle_eqb f1 f2) (lifecycle_eqb t1 t2)
  | LockEdge f1 t1, LockEdge f2 t2 => andb (lock_eqb f1 f2) (lock_eqb t1 t2)
  | _, _ => false
  end.

Definition lifecycle_edges : list Transition :=
  LifecycleEdge Raw TestState :: LifecycleEdge TestState Development ::
  LifecycleEdge TestState Production :: LifecycleEdge Development Rma ::
  LifecycleEdge Production Rma :: nil.

Definition lock_edges : list Transition :=
  LockEdge BeforeFirstUnlock AfterFirstUnlock :: LockEdge AfterFirstUnlock BeforeFirstUnlock :: nil.

Definition all_transitions : list Transition := lifecycle_edges ++ lock_edges.

Definition the_lock_edge : Transition := LockEdge AfterFirstUnlock BeforeFirstUnlock.

Definition all_lifecycles : list Lifecycle :=
  Raw :: TestState :: Development :: Production :: Rma :: nil.

Definition all_lock_states : list LockState :=
  BeforeFirstUnlock :: AfterFirstUnlock :: nil.

(* The three decidable equalities are decided rather than assumed: each is
   reflexive on every constructor of its own type and matches exactly one
   member of its enumeration, which catches a diagonal arm answering false
   of a thing and itself and an arm answering true of two different things.
   `transition_eqb` is checked over the seven edges the discipline reseeds
   on, so an arm making a lifecycle edge equal to a lock edge is caught
   there and not left to the reseed map. *)
Definition eqb_decides {A : Type} (eqb : A -> A -> bool) (l : list A) : bool :=
  all_of (fun x => andb (eqb x x) (Nat.eqb (count_where (eqb x) l) 1)) l.

Example the_three_equalities_decide_their_own_enumerations :
  andb (eqb_decides lifecycle_eqb all_lifecycles)
  (andb (eqb_decides lock_eqb all_lock_states)
        (eqb_decides transition_eqb all_transitions)) = true.
Proof. vm_reflexivity. Qed.

(* The seven edges all differ from each other in **both** endpoints, so
   they cannot tell an equality that joins its two comparisons with `and`
   from one that joins them with `or`. Two self-edges, which are not
   transitions and are here only as probes, are what separate the two. *)
Definition transition_probes : list Transition :=
  all_transitions ++ (LockEdge BeforeFirstUnlock BeforeFirstUnlock
                      :: LifecycleEdge Raw Raw :: nil).

Example the_transition_equality_decides_a_wider_probe_than_the_edges :
  eqb_decides transition_eqb transition_probes = true.
Proof. vm_reflexivity. Qed.

(* An equality that is reflexive on every edge and still wrong, so that both
   halves of the test above are load-bearing: this one says every lock edge
   equals everything, which no reflexivity check catches and which the count
   catches. *)
Definition lax_transition_eqb (a b : Transition) : bool :=
  if a is LockEdge _ _ then true else transition_eqb a b.

Example a_reflexive_equality_can_still_be_wrong :
  andb (all_of (fun t => lax_transition_eqb t t) all_transitions)
       (negb (eqb_decides lax_transition_eqb all_transitions)) = true.
Proof. vm_reflexivity. Qed.

Example there_are_five_lifecycle_edges_and_two_lock_edges :
  andb (Nat.eqb (length_of lifecycle_edges) 5) (Nat.eqb (length_of lock_edges) 2) = true.
Proof. vm_reflexivity. Qed.

Example no_edge_leaves_rma_and_none_joins_development_to_production :
  all_of (fun t => match t with
                   | LifecycleEdge Rma _ => false
                   | LifecycleEdge Development Production => false
                   | LifecycleEdge Production Development => false
                   | _ => true
                   end) all_transitions = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   R-15-241d's seeding discipline as a record, and the premise every
   theorem below takes. The three inequalities are the standard's own on an
   instantiation (s8.6.7: entropy input and nonce sized to the strength) and
   on the bounds being bounds at all; the fourth clause is the entry's, that
   every lifecycle or lock-state transition reseeds.
   ------------------------------------------------------------------------- *)

Record SeedingDiscipline : Type := {
  security_strength : nat;
  seed_length : nat;
  nonce_length : nat;
  draw_bound : nat;
  interval_bound : nat;
  reseed_on : Transition -> bool;
  prediction_resistance : bool
}.

Definition disciplined_b (d : SeedingDiscipline) : bool :=
  andb (Nat.leb (security_strength d) (seed_length d))
  (andb (Nat.leb (security_strength d) (2 * nonce_length d))
  (andb (Nat.leb 1 (draw_bound d))
  (andb (Nat.leb 1 (interval_bound d))
        (all_of (reseed_on d) all_transitions)))).

Definition Disciplined (d : SeedingDiscipline) : Prop := disciplined_b d = true.

(* The ordered executable conjunction has one named logical projection per
   condition. Its consumers do not depend on conjunction depth. *)
Record DisciplineConditions (d : SeedingDiscipline) : Prop := {
  discipline_seed_sufficient : Nat.leb (security_strength d) (seed_length d) = true;
  discipline_nonce_sufficient : Nat.leb (security_strength d) (2 * nonce_length d) = true;
  discipline_draw_positive : Nat.leb 1 (draw_bound d) = true;
  discipline_interval_positive : Nat.leb 1 (interval_bound d) = true;
  discipline_transitions_reseed : all_of (reseed_on d) all_transitions = true
}.

Lemma disciplined_conditions : forall d : SeedingDiscipline,
  Disciplined d -> DisciplineConditions d.
Proof.
  intros d H. unfold Disciplined, disciplined_b in H.
  apply ProofSupport.andb_split in H as [Hseed H].
  apply ProofSupport.andb_split in H as [Hnonce H].
  apply ProofSupport.andb_split in H as [Hdraw H].
  apply ProofSupport.andb_split in H as [Hinterval Htransitions].
  constructor; assumption.
Qed.

Lemma discipline_conditions_suffice : forall d : SeedingDiscipline,
  DisciplineConditions d -> Disciplined d.
Proof.
  intros d [Hseed Hnonce Hdraw Hinterval Htransitions].
  unfold Disciplined, disciplined_b.
  rewrite Hseed, Hnonce, Hdraw, Hinterval, Htransitions. reflexivity.
Qed.

Lemma disciplined_transition_reseeds : forall (d : SeedingDiscipline) (t : Transition),
  Disciplined d -> ProofSupport.Member t all_transitions -> reseed_on d t = true.
Proof.
  intros d t H Hmember.
  exact (ProofSupport.all_of_member Transition (reseed_on d) all_transitions t
    (discipline_transitions_reseed d (disciplined_conditions d H)) Hmember).
Qed.

Lemma the_lock_edge_is_a_transition : ProofSupport.Member the_lock_edge all_transitions.
Proof. simpl. right. right. right. right. right. right. left. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The s9 envelope as a machine over a pool of conditioned root output. A
   draw past the discipline's bound is refused; a draw when the counter has
   passed the interval, or under prediction resistance, reseeds first with
   the draw's additional input and then draws with none (s9.3.1); a
   transition the discipline reseeds on takes entropy; and a pool with
   nothing to give halts the run.
   ------------------------------------------------------------------------- *)

Inductive Op : Type :=
| Draw (bits : nat) (additional : list bool)
| Reseed (additional : list bool)
| Cross (t : Transition).

Record Run : Type := {
  state : DrbgState;
  pool : list (list bool);
  outputs : list (list bool)
}.

Definition take_entropy (d : SeedingDiscipline) (p : list (list bool))
  : option (list bool * list (list bool)) :=
  match p with
  | nil => None
  | e :: rest => if Nat.eqb (length_of e) (seed_length d) then Some (pair e rest) else None
  end.

Definition step (d : SeedingDiscipline) (r : Run) (op : Op) : option Run :=
  match op with
  | Draw bits additional =>
      if Nat.ltb (draw_bound d) bits then None
      else if orb (prediction_resistance d) (Nat.ltb (interval_bound d) (reseed_counter (state r)))
      then match take_entropy d (pool r) with
           | None => None
           | Some er =>
               let out := generate_core (reseed (state r) (fst er) additional) bits nil in
               Some {| state := snd out; pool := snd er; outputs := outputs r ++ (fst out :: nil) |}
           end
      else let out := generate_core (state r) bits additional in
           Some {| r with state := snd out; outputs := outputs r ++ (fst out :: nil) |}
  | Reseed additional =>
      match take_entropy d (pool r) with
      | None => None
      | Some er => Some {| r with state := reseed (state r) (fst er) additional; pool := snd er |}
      end
  | Cross t =>
      if reseed_on d t
      then match take_entropy d (pool r) with
           | None => None
           | Some er => Some {| r with state := reseed (state r) (fst er) nil; pool := snd er |}
           end
      else Some r
  end.

Definition run (d : SeedingDiscipline) (ops : list Op) (r : Run) : option Run :=
  fold_over (fun acc op => match acc with None => None | Some r => step d r op end)
            (Some r) ops.

Definition start (d : SeedingDiscipline) (entropy nonce personalization : list bool)
                 (p : list (list bool)) : option Run :=
  if andb (Nat.eqb (length_of entropy) (seed_length d))
          (Nat.eqb (length_of nonce) (nonce_length d))
  then Some {| state := instantiate entropy nonce personalization; pool := p; outputs := nil |}
  else None.

Definition run_from (d : SeedingDiscipline) (entropy nonce personalization : list bool)
                    (p : list (list bool)) (ops : list Op) : option Run :=
  match start d entropy nonce personalization p with
  | None => None
  | Some r => run d ops r
  end.

Definition completed (r : option Run) : bool :=
  if r is None then false else true.

Definition outputs_of (r : option Run) : list (list bool) :=
  match r with None => nil | Some r => outputs r end.

Definition output_at (r : option Run) (i : nat) : list bool := nth_of i (outputs_of r) nil.

Definition pool_left (r : option Run) : nat :=
  match r with None => 0 | Some r => length_of (pool r) end.

Definition state_of (r : option Run) : DrbgState :=
  match r with
  | None => {| key := nil; value := nil; reseed_counter := 0 |}
  | Some r => state r
  end.

(* What the discipline asks of a run beyond the machine's own refusals: a
   fresh pool of strings at the seed length, and no request past the bound. *)
Definition disciplined_run_b (d : SeedingDiscipline) (p : list (list bool)) (ops : list Op) : bool :=
  andb (disciplined_b d)
  (andb (fresh_pool p)
  (andb (all_of (fun e => Nat.eqb (length_of e) (seed_length d)) p)
        (all_of (fun op => if op is Draw bits _ then Nat.leb bits (draw_bound d) else true)
                ops))).

(* -------------------------------------------------------------------------
   What is stated of an arbitrary discipline, an arbitrary state and an
   arbitrary run.
   ------------------------------------------------------------------------- *)

(*| discharges: R-15-241d |*)
Theorem a_reseed_resets_the_counter :
  forall (s : DrbgState) (entropy additional : list bool),
    reseed_counter (reseed s entropy additional) = 1.
Proof. intros. reflexivity. Qed.

(*| discharges: R-15-241d |*)
Theorem a_draw_advances_the_counter :
  forall (s : DrbgState) (bits : nat) (additional : list bool),
    reseed_counter (snd (generate_core s bits additional)) = S (reseed_counter s).
Proof. intros. reflexivity. Qed.

(* The ordering the standard fixes and backtracking resistance rests on: the
   output of a draw is the leftmost bits of the blocks drawn from the state
   before the post-draw update, and the state that leaves is that update
   over the last drawn value. Stated by unfolding, so that the alternative
   below has an order to invert. *)
(*| discharges: R-15-241d |*)
Theorem a_draw_emits_before_it_updates :
  forall (s : DrbgState) (bits : nat) (additional : list bool),
    let kv0 := update_on additional (key s) (value s) in
    let drawn := draw_blocks (blocks_for bits) (fst kv0) (snd kv0) nil in
    fst (generate_core s bits additional) = take_of bits (fst drawn)
    /\ key (snd (generate_core s bits additional))
       = fst (hmac_drbg_update additional (fst kv0) (snd drawn))
    /\ value (snd (generate_core s bits additional))
       = snd (hmac_drbg_update additional (fst kv0) (snd drawn)).
Proof. intros. repeat split; reflexivity. Qed.

(*| discharges: R-15-241d |*)
Theorem a_draw_past_the_interval_is_refused_by_the_algorithm :
  forall (interval : nat) (s : DrbgState) (bits : nat) (additional : list bool),
    Nat.ltb interval (reseed_counter s) = true -> generate interval s bits additional = None.
Proof. intros interval s bits additional H. unfold generate. rewrite H. reflexivity. Qed.

(*| discharges: R-15-241d |*)
Theorem a_draw_past_the_bound_is_refused :
  forall (d : SeedingDiscipline) (r : Run) (bits : nat) (additional : list bool),
    Nat.ltb (draw_bound d) bits = true -> step d r (Draw bits additional) = None.
Proof. intros d r bits additional H. unfold step. rewrite H. reflexivity. Qed.

(*| discharges: R-15-241d |*)
Theorem every_transition_reseeds_under_a_disciplined_discipline :
  forall d : SeedingDiscipline, Disciplined d -> all_of (reseed_on d) all_transitions = true.
Proof.
  intros d H. exact (discipline_transitions_reseed d (disciplined_conditions d H)).
Qed.

(*| discharges: R-15-241d |*)
Theorem the_lock_edge_reseeds_under_a_disciplined_discipline :
  forall d : SeedingDiscipline, Disciplined d -> reseed_on d the_lock_edge = true.
Proof.
  intros d H. exact (disciplined_transition_reseeds d the_lock_edge H
    the_lock_edge_is_a_transition).
Qed.

(* A lock transition under a disciplined discipline takes the next string of
   the pool and leaves the state reseeded from it. *)
(*| discharges: R-15-241d |*)
Theorem a_lock_transition_takes_fresh_entropy :
  forall (d : SeedingDiscipline) (r : Run) (e : list bool) (rest : list (list bool)),
    Disciplined d ->
    Nat.eqb (length_of e) (seed_length d) = true ->
    pool r = e :: rest ->
    step d r (Cross the_lock_edge)
    = Some {| r with state := reseed (state r) e nil; pool := rest |}.
Proof.
  intros d r e rest HD HL HP. unfold step, take_entropy.
  rewrite (the_lock_edge_reseeds_under_a_disciplined_discipline d HD), HP, HL. reflexivity.
Qed.

(* A draw past the interval under a disciplined discipline takes fresh
   entropy before it draws, and the state that leaves has counted one draw
   since a reseed. *)
(*| discharges: R-15-241d |*)
Theorem a_draw_past_the_interval_reseeds_first :
  forall (d : SeedingDiscipline) (r : Run) (bits : nat) (additional e : list bool)
         (rest : list (list bool)),
    Nat.ltb (draw_bound d) bits = false ->
    Nat.ltb (interval_bound d) (reseed_counter (state r)) = true ->
    Nat.eqb (length_of e) (seed_length d) = true ->
    pool r = e :: rest ->
    exists r' : Run,
      step d r (Draw bits additional) = Some r'
      /\ pool r' = rest
      /\ reseed_counter (state r') = 2.
Proof.
  intros d r bits additional e rest HB HI HL HP. unfold step, take_entropy.
  rewrite HB, HI, HP, HL. destruct (prediction_resistance d);
  (eexists; split; [reflexivity | split; reflexivity]).
Qed.

(* A pool with nothing left halts a reseed rather than reseeding with
   nothing, for every discipline and every state. *)
(*| discharges: R-15-241d |*)
Theorem an_empty_pool_halts_a_reseed :
  forall (d : SeedingDiscipline) (r : Run) (additional : list bool),
    pool r = nil -> step d r (Reseed additional) = None.
Proof. intros d r additional H. unfold step, take_entropy. rewrite H. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The corpus's inputs. Each is a definition because it is an input; the
   answers are inside the Examples that decide against them.
   ------------------------------------------------------------------------- *)

Definition no_reseed_entropy : list bool := bytes_from (
  0xCA :: 0x85 :: 0x19 :: 0x11 :: 0x34 :: 0x93 :: 0x84 :: 0xBF ::
  0xFE :: 0x89 :: 0xDE :: 0x1C :: 0xBD :: 0xC4 :: 0x6E :: 0x68 ::
  0x31 :: 0xE4 :: 0x4D :: 0x34 :: 0xA4 :: 0xFB :: 0x93 :: 0x5E ::
  0xE2 :: 0x85 :: 0xDD :: 0x14 :: 0xB7 :: 0x1A :: 0x74 :: 0x88 :: nil).

Definition no_reseed_nonce : list bool := bytes_from (
  0x65 :: 0x9B :: 0xA9 :: 0x6C :: 0x60 :: 0x1D :: 0xC6 :: 0x9F ::
  0xC9 :: 0x02 :: 0x94 :: 0x08 :: 0x05 :: 0xEC :: 0x0C :: 0xA8 :: nil).

Definition pr_false_entropy : list bool := bytes_from (
  0x06 :: 0x03 :: 0x2C :: 0xD5 :: 0xEE :: 0xD3 :: 0x3F :: 0x39 ::
  0x26 :: 0x5F :: 0x49 :: 0xEC :: 0xB1 :: 0x42 :: 0xC5 :: 0x11 ::
  0xDA :: 0x9A :: 0xFF :: 0x2A :: 0xF7 :: 0x12 :: 0x03 :: 0xBF ::
  0xFA :: 0xF3 :: 0x4A :: 0x9C :: 0xA5 :: 0xBD :: 0x9C :: 0x0D :: nil).

Definition pr_false_nonce : list bool := bytes_from (
  0x0E :: 0x66 :: 0xF7 :: 0x1E :: 0xDC :: 0x43 :: 0xE4 :: 0x2A ::
  0x45 :: 0xAD :: 0x3C :: 0x6F :: 0xC6 :: 0xCD :: 0xC4 :: 0xDF :: nil).

Definition pr_false_reseed_entropy : list bool := bytes_from (
  0x01 :: 0x92 :: 0x0A :: 0x4E :: 0x66 :: 0x9E :: 0xD3 :: 0xA8 ::
  0x5A :: 0xE8 :: 0xA3 :: 0x3B :: 0x35 :: 0xA7 :: 0x4A :: 0xD7 ::
  0xFB :: 0x2A :: 0x6B :: 0xB4 :: 0xCF :: 0x39 :: 0x5C :: 0xE0 ::
  0x03 :: 0x34 :: 0xA9 :: 0xC9 :: 0xA5 :: 0xA5 :: 0xD5 :: 0x52 :: nil).

Definition pr_true_entropy : list bool := bytes_from (
  0x99 :: 0x69 :: 0xE5 :: 0x4B :: 0x47 :: 0x03 :: 0xFF :: 0x31 ::
  0x78 :: 0x5B :: 0x87 :: 0x9A :: 0x7E :: 0x5C :: 0x0E :: 0xAE ::
  0x0D :: 0x3E :: 0x30 :: 0x95 :: 0x59 :: 0xE9 :: 0xFE :: 0x96 ::
  0xB0 :: 0x67 :: 0x6D :: 0x49 :: 0xD5 :: 0x91 :: 0xEA :: 0x4D :: nil).

Definition pr_true_nonce : list bool := bytes_from (
  0x07 :: 0xD2 :: 0x0D :: 0x46 :: 0xD0 :: 0x64 :: 0x75 :: 0x7D ::
  0x30 :: 0x23 :: 0xCA :: 0xC2 :: 0x37 :: 0x61 :: 0x27 :: 0xAB :: nil).

Definition pr_true_first_reseed_entropy : list bool := bytes_from (
  0xC6 :: 0x0F :: 0x29 :: 0x99 :: 0x10 :: 0x0F :: 0x73 :: 0x8C ::
  0x10 :: 0xF7 :: 0x47 :: 0x92 :: 0x67 :: 0x6A :: 0x3F :: 0xC4 ::
  0xA2 :: 0x62 :: 0xD1 :: 0x37 :: 0x21 :: 0x79 :: 0x80 :: 0x46 ::
  0xE2 :: 0x9A :: 0x29 :: 0x51 :: 0x81 :: 0x56 :: 0x9F :: 0x54 :: nil).

Definition pr_true_second_reseed_entropy : list bool := bytes_from (
  0xC1 :: 0x1D :: 0x45 :: 0x24 :: 0xC9 :: 0x07 :: 0x1B :: 0xD3 ::
  0x09 :: 0x60 :: 0x15 :: 0xFC :: 0xF7 :: 0xBC :: 0x24 :: 0xA6 ::
  0x07 :: 0xF2 :: 0x2F :: 0xA0 :: 0x65 :: 0xC9 :: 0x37 :: 0x65 ::
  0x8A :: 0x2A :: 0x77 :: 0xA8 :: 0x69 :: 0x90 :: 0x89 :: 0xF4 :: nil).

(* -------------------------------------------------------------------------
   The witness discipline, whose figures are the corpus's own: the entropy
   input, nonce and returned lengths are read off its strings, the strength
   is the highest Table 2 admits for HMAC_DRBG over SHA-256, which is its
   outlen, and the interval is the corpus's two draws. Every transition
   reseeds. `demo_pr` is the same discipline with prediction resistance
   requested, which is the third family's.
   ------------------------------------------------------------------------- *)

Definition corpus_draw_bits : nat := 1024.

Definition demo : SeedingDiscipline :=
  {| security_strength := outlen_bits;
     seed_length := length_of no_reseed_entropy;
     nonce_length := length_of no_reseed_nonce;
     draw_bound := corpus_draw_bits;
     interval_bound := 2;
     reseed_on := fun _ => true;
     prediction_resistance := false |}.

Definition demo_pr : SeedingDiscipline :=
  {| demo with prediction_resistance := true |}.

Example the_witness_is_disciplined : Disciplined demo.
Proof. vm_compute. reflexivity. Qed.

Definition witness_DisciplineConditions : DisciplineConditions demo :=
  disciplined_conditions demo the_witness_is_disciplined.

Example the_prediction_resistant_witness_is_disciplined : Disciplined demo_pr.
Proof. vm_compute. reflexivity. Qed.

(* Three disciplines the premise refuses, each the witness with one field
   moved. *)
Definition silent_on_the_lock_edge : SeedingDiscipline :=
  {| demo with reseed_on := fun t => negb (transition_eqb t the_lock_edge);
               prediction_resistance := false |}.

Definition seeded_below_its_strength : SeedingDiscipline :=
  {| demo with seed_length := security_strength demo - 1;
               prediction_resistance := false |}.

Definition with_no_interval : SeedingDiscipline :=
  {| demo with interval_bound := 0;
               prediction_resistance := false |}.

Example the_discipline_silent_on_the_lock_edge_is_refused :
  disciplined_b silent_on_the_lock_edge = false.
Proof. vm_reflexivity. Qed.

Example the_discipline_silent_on_the_lock_edge_reseeds_on_every_other_edge :
  all_of (fun t => orb (transition_eqb t the_lock_edge) (reseed_on silent_on_the_lock_edge t))
         all_transitions = true.
Proof. vm_reflexivity. Qed.

Example the_discipline_seeded_below_its_strength_is_refused :
  disciplined_b seeded_below_its_strength = false.
Proof. vm_reflexivity. Qed.

Example the_discipline_with_no_interval_is_refused :
  disciplined_b with_no_interval = false.
Proof. vm_reflexivity. Qed.

(* A fourth, whose nonce is one bit shorter than the witness's, which is the
   only clause of s8.6.7 the three above leave undecided. *)
Definition nonced_below_half_its_strength : SeedingDiscipline :=
  {| demo with nonce_length := nonce_length demo - 1;
               prediction_resistance := false |}.

Example the_discipline_nonced_below_half_its_strength_is_refused :
  disciplined_b nonced_below_half_its_strength = false.
Proof. vm_reflexivity. Qed.

(* Each of the four is refused at a boundary and not somewhere past one: the
   short seed is one bit under the strength, the short nonce one bit under
   the witness's, and one more bit of either is what the witness has. *)
Example the_two_short_lengths_are_short_by_one_bit :
  andb (andb (Nat.eqb (S (seed_length seeded_below_its_strength)) (security_strength demo))
             (Nat.leb (security_strength demo) (seed_length demo)))
       (andb (Nat.eqb (S (nonce_length nonced_below_half_its_strength)) (nonce_length demo))
             (Nat.leb (security_strength demo) (2 * nonce_length demo))) = true.
Proof. vm_reflexivity. Qed.

(* Each of the four is the witness with one field moved and no other, which
   is what "held to its single difference" means here: the flag none of them
   is about stays where the witness put it, and so does the strength. *)
Example the_four_refused_disciplines_move_one_field_each :
  all_of (fun d => andb (negb (prediction_resistance d))
                        (Nat.eqb (security_strength d) (security_strength demo)))
         (silent_on_the_lock_edge :: seeded_below_its_strength :: with_no_interval
          :: nonced_below_half_its_strength :: nil) = true.
Proof. vm_reflexivity. Qed.

(* The bounds are bounds and not thresholds, and the flag beside them is a
   request and not an admission condition. The witness's own figures stay
   out of the definition: what is decided is which pairs of bounds the
   premise admits, so the numbers live inside the statements that decide. *)
Definition bounded_at (draw interval : nat) (pr : bool) : SeedingDiscipline :=
  {| demo with draw_bound := draw; interval_bound := interval;
               prediction_resistance := pr |}.

Example one_is_the_smallest_bound_and_zero_is_refused_on_either :
  andb (disciplined_b (bounded_at 1 1 false))
  (andb (negb (disciplined_b (bounded_at 0 1 false)))
        (negb (disciplined_b (bounded_at 1 0 false)))) = true.
Proof. vm_reflexivity. Qed.

Example prediction_resistance_is_requested_and_not_required :
  andb (disciplined_b (bounded_at 1 1 false))
       (disciplined_b (bounded_at 1 1 true)) = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The three published families, run through the envelope. Each is two
   draws of 1024 bits with nothing personalized and nothing additional; the
   second family reseeds once between instantiation and the first draw, and
   the third reseeds before each draw because prediction resistance is
   requested. The corpus publishes the second draw.
   ------------------------------------------------------------------------- *)

Definition two_draws : list Op :=
  Draw corpus_draw_bits nil :: Draw corpus_draw_bits nil :: nil.

Definition no_reseed_run : option Run :=
  run_from demo no_reseed_entropy no_reseed_nonce nil nil two_draws.

Definition pr_false_run : option Run :=
  run_from demo pr_false_entropy pr_false_nonce nil (pr_false_reseed_entropy :: nil)
           (Reseed nil :: two_draws).

Definition pr_true_run : option Run :=
  run_from demo_pr pr_true_entropy pr_true_nonce nil
           (pr_true_first_reseed_entropy :: pr_true_second_reseed_entropy :: nil) two_draws.

(* Pre-evaluated literal for `no_reseed_run`, shared across six examples to
   avoid redundant VM evaluation during Qed rechecking. *)
Definition no_reseed_run_literal : option Run := Eval vm_compute in no_reseed_run.

Lemma no_reseed_run_is_its_literal : no_reseed_run = no_reseed_run_literal.
Proof. unfold no_reseed_run_literal. vm_reflexivity. Qed.

Example the_three_families_complete_and_use_their_whole_pool :
  andb (andb (completed no_reseed_run) (Nat.eqb (pool_left no_reseed_run) 0))
  (andb (andb (completed pr_false_run) (Nat.eqb (pool_left pr_false_run) 0))
        (andb (completed pr_true_run) (Nat.eqb (pool_left pr_true_run) 0))) = true.
Proof. rewrite no_reseed_run_is_its_literal. vm_reflexivity. Qed.

Example the_three_families_are_disciplined_runs :
  andb (disciplined_run_b demo nil two_draws)
  (andb (disciplined_run_b demo (pr_false_reseed_entropy :: nil) (Reseed nil :: two_draws))
        (disciplined_run_b demo_pr
           (pr_true_first_reseed_entropy :: pr_true_second_reseed_entropy :: nil) two_draws)) = true.
Proof. vm_reflexivity. Qed.

Example the_second_draw_without_a_reseed :
  bytes_of (output_at no_reseed_run 1) =
  0xE5 :: 0x28 :: 0xE9 :: 0xAB :: 0xF2 :: 0xDE :: 0xCE :: 0x54 ::
  0xD4 :: 0x7C :: 0x7E :: 0x75 :: 0xE5 :: 0xFE :: 0x30 :: 0x21 ::
  0x49 :: 0xF8 :: 0x17 :: 0xEA :: 0x9F :: 0xB4 :: 0xBE :: 0xE6 ::
  0xF4 :: 0x19 :: 0x96 :: 0x97 :: 0xD0 :: 0x4D :: 0x5B :: 0x89 ::
  0xD5 :: 0x4F :: 0xBB :: 0x97 :: 0x8A :: 0x15 :: 0xB5 :: 0xC4 ::
  0x43 :: 0xC9 :: 0xEC :: 0x21 :: 0x03 :: 0x6D :: 0x24 :: 0x60 ::
  0xB6 :: 0xF7 :: 0x3E :: 0xBA :: 0xD0 :: 0xDC :: 0x2A :: 0xBA ::
  0x6E :: 0x62 :: 0x4A :: 0xBF :: 0x07 :: 0x74 :: 0x5B :: 0xC1 ::
  0x07 :: 0x69 :: 0x4B :: 0xB7 :: 0x54 :: 0x7B :: 0xB0 :: 0x99 ::
  0x5F :: 0x70 :: 0xDE :: 0x25 :: 0xD6 :: 0xB2 :: 0x9E :: 0x2D ::
  0x30 :: 0x11 :: 0xBB :: 0x19 :: 0xD2 :: 0x76 :: 0x76 :: 0xC0 ::
  0x71 :: 0x62 :: 0xC8 :: 0xB5 :: 0xCC :: 0xDE :: 0x06 :: 0x68 ::
  0x96 :: 0x1D :: 0xF8 :: 0x68 :: 0x03 :: 0x48 :: 0x2C :: 0xB3 ::
  0x7E :: 0xD6 :: 0xD5 :: 0xC0 :: 0xBB :: 0x8D :: 0x50 :: 0xCF ::
  0x1F :: 0x50 :: 0xD4 :: 0x76 :: 0xAA :: 0x04 :: 0x58 :: 0xBD ::
  0xAB :: 0xA8 :: 0x06 :: 0xF4 :: 0x8B :: 0xE9 :: 0xDC :: 0xB8 :: nil.
Proof. rewrite no_reseed_run_is_its_literal. vm_reflexivity. Qed.

Example the_second_draw_after_one_reseed :
  bytes_of (output_at pr_false_run 1) =
  0x76 :: 0xFC :: 0x79 :: 0xFE :: 0x9B :: 0x50 :: 0xBE :: 0xCC ::
  0xC9 :: 0x91 :: 0xA1 :: 0x1B :: 0x56 :: 0x35 :: 0x78 :: 0x3A ::
  0x83 :: 0x53 :: 0x6A :: 0xDD :: 0x03 :: 0xC1 :: 0x57 :: 0xFB ::
  0x30 :: 0x64 :: 0x5E :: 0x61 :: 0x1C :: 0x28 :: 0x98 :: 0xBB ::
  0x2B :: 0x1B :: 0xC2 :: 0x15 :: 0x00 :: 0x02 :: 0x09 :: 0x20 ::
  0x8C :: 0xD5 :: 0x06 :: 0xCB :: 0x28 :: 0xDA :: 0x2A :: 0x51 ::
  0xBD :: 0xB0 :: 0x38 :: 0x26 :: 0xAA :: 0xF2 :: 0xBD :: 0x23 ::
  0x35 :: 0xD5 :: 0x76 :: 0xD5 :: 0x19 :: 0x16 :: 0x08 :: 0x42 ::
  0xE7 :: 0x15 :: 0x8A :: 0xD0 :: 0x94 :: 0x9D :: 0x1A :: 0x9E ::
  0xC3 :: 0xE6 :: 0x6E :: 0xA1 :: 0xB1 :: 0xA0 :: 0x64 :: 0xB0 ::
  0x05 :: 0xDE :: 0x91 :: 0x4E :: 0xAC :: 0x2E :: 0x9D :: 0x4F ::
  0x2D :: 0x72 :: 0xA8 :: 0x61 :: 0x6A :: 0x80 :: 0x22 :: 0x54 ::
  0x22 :: 0x91 :: 0x82 :: 0x50 :: 0xFF :: 0x66 :: 0xA4 :: 0x1B ::
  0xD2 :: 0xF8 :: 0x64 :: 0xA6 :: 0xA3 :: 0x8C :: 0xC5 :: 0xB6 ::
  0x49 :: 0x9D :: 0xC4 :: 0x3F :: 0x7F :: 0x2B :: 0xD0 :: 0x9E ::
  0x1E :: 0x0F :: 0x8F :: 0x58 :: 0x85 :: 0x93 :: 0x51 :: 0x24 :: nil.
Proof. vm_reflexivity. Qed.

Example the_second_draw_under_prediction_resistance :
  bytes_of (output_at pr_true_run 1) =
  0xAB :: 0xC0 :: 0x15 :: 0x85 :: 0x60 :: 0x94 :: 0x80 :: 0x3A ::
  0x93 :: 0x8D :: 0xFF :: 0xD2 :: 0x0D :: 0xA9 :: 0x48 :: 0x43 ::
  0x87 :: 0x0E :: 0xF9 :: 0x35 :: 0xB8 :: 0x2C :: 0xFE :: 0xC1 ::
  0x77 :: 0x06 :: 0xB8 :: 0xF5 :: 0x51 :: 0xB8 :: 0x38 :: 0x50 ::
  0x44 :: 0x23 :: 0x5D :: 0xD4 :: 0x4B :: 0x59 :: 0x9F :: 0x94 ::
  0xB3 :: 0x9B :: 0xE7 :: 0x8D :: 0xD4 :: 0x76 :: 0xE0 :: 0xCF ::
  0x11 :: 0x30 :: 0x9C :: 0x99 :: 0x5A :: 0x73 :: 0x34 :: 0xE0 ::
  0xA7 :: 0x8B :: 0x37 :: 0xBC :: 0x95 :: 0x86 :: 0x23 :: 0x50 ::
  0x86 :: 0xFA :: 0x3B :: 0x63 :: 0x7B :: 0xA9 :: 0x1C :: 0xF8 ::
  0xFB :: 0x65 :: 0xEF :: 0xA2 :: 0x2A :: 0x58 :: 0x9C :: 0x13 ::
  0x75 :: 0x31 :: 0xAA :: 0x7B :: 0x2D :: 0x4E :: 0x26 :: 0x07 ::
  0xAA :: 0xC2 :: 0x72 :: 0x92 :: 0xB0 :: 0x1C :: 0x69 :: 0x8E ::
  0x6E :: 0x01 :: 0xAE :: 0x67 :: 0x9E :: 0xB8 :: 0x7C :: 0x01 ::
  0xA8 :: 0x9C :: 0x74 :: 0x22 :: 0xD4 :: 0x37 :: 0x2D :: 0x6D ::
  0x75 :: 0x4A :: 0xBA :: 0xBB :: 0x4B :: 0xF8 :: 0x96 :: 0xFC ::
  0xB1 :: 0xCD :: 0x09 :: 0xD6 :: 0x92 :: 0xD0 :: 0x28 :: 0x3F :: nil.
Proof. vm_reflexivity. Qed.

Example the_two_draws_of_a_run_differ :
  bits_eqb (output_at no_reseed_run 0) (output_at no_reseed_run 1) = false.
Proof. rewrite no_reseed_run_is_its_literal. vm_reflexivity. Qed.

(* The algorithm alone, without the envelope, reaches the same first family:
   two calls of generate under the corpus's interval and none refused. *)
Example the_algorithm_alone_reaches_the_first_family :
  let s0 := instantiate no_reseed_entropy no_reseed_nonce nil in
  match generate (interval_bound demo) s0 corpus_draw_bits nil with
  | None => false
  | Some r1 => match generate (interval_bound demo) (snd r1) corpus_draw_bits nil with
               | None => false
               | Some r2 => bits_eqb (fst r2) (output_at no_reseed_run 1)
               end
  end = true.
Proof. rewrite no_reseed_run_is_its_literal. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   Backtracking resistance across a draw, as a computed property: no block
   of a draw's output is the value or the key of the state that leaves it,
   where the draw that updates first leaves its last block as its value.
   ------------------------------------------------------------------------- *)

Definition first_draw : list bool * DrbgState :=
  generate_core (instantiate no_reseed_entropy no_reseed_nonce nil) corpus_draw_bits nil.

Definition first_draw_updating_first : list bool * DrbgState :=
  generate_core_updating_before_it_emits (instantiate no_reseed_entropy no_reseed_nonce nil)
                                         corpus_draw_bits nil.

Definition blocks_of_output (out : list bool) : list (list bool) :=
  chunks_of (blocks_for (length_of out)) outlen_bits out.

Example the_state_that_leaves_a_draw_carries_no_block_of_its_output :
  all_of (fun b => andb (negb (bits_eqb b (value (snd first_draw))))
                        (negb (bits_eqb b (key (snd first_draw)))))
         (blocks_of_output (fst first_draw)) = true.
Proof. vm_reflexivity. Qed.

Example the_draw_that_updates_first_leaves_its_last_block_as_its_value :
  bits_eqb (last_of (blocks_of_output (fst first_draw_updating_first)) nil)
           (value (snd first_draw_updating_first)) = true.
Proof. vm_reflexivity. Qed.

Example the_draw_that_updates_first_keeps_the_length_and_the_counter :
  andb (Nat.eqb (length_of (fst first_draw_updating_first)) corpus_draw_bits)
       (Nat.eqb (reseed_counter (snd first_draw_updating_first))
                (reseed_counter (snd first_draw))) = true.
Proof. vm_reflexivity. Qed.

Example the_draw_that_updates_first_misses_the_published_answer :
  bits_eqb (fst first_draw_updating_first) (output_at no_reseed_run 0) = false.
Proof. rewrite no_reseed_run_is_its_literal. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   Prediction resistance across a reseed, as a computed property: two
   fresh strings leave two states, where the reseed that ignores its
   entropy leaves one; and the freshness the envelope asks of its pool.
   ------------------------------------------------------------------------- *)

Definition instantiated_for_pr : DrbgState := instantiate pr_true_entropy pr_true_nonce nil.

Example two_fresh_strings_leave_two_states :
  andb (negb (bits_eqb (key (reseed instantiated_for_pr pr_true_first_reseed_entropy nil))
                       (key (reseed instantiated_for_pr pr_true_second_reseed_entropy nil))))
       (negb (bits_eqb (value (reseed instantiated_for_pr pr_true_first_reseed_entropy nil))
                       (value (reseed instantiated_for_pr pr_true_second_reseed_entropy nil))))
  = true.
Proof. vm_reflexivity. Qed.

Example the_reseed_that_ignores_its_entropy_leaves_one_state :
  andb (bits_eqb (key (reseed_ignoring_its_entropy instantiated_for_pr pr_true_first_reseed_entropy nil))
                 (key (reseed_ignoring_its_entropy instantiated_for_pr pr_true_second_reseed_entropy nil)))
       (Nat.eqb (reseed_counter (reseed_ignoring_its_entropy instantiated_for_pr
                                                             pr_true_first_reseed_entropy nil)) 1)
  = true.
Proof. vm_reflexivity. Qed.

Example a_pool_that_reuses_a_string_is_not_fresh :
  andb (negb (fresh_pool (pr_true_first_reseed_entropy :: pr_true_first_reseed_entropy :: nil)))
       (fresh_pool (pr_true_first_reseed_entropy :: pr_true_second_reseed_entropy :: nil)) = true.
Proof. vm_reflexivity. Qed.

Example a_run_over_a_reused_pool_is_refused_by_the_discipline :
  disciplined_run_b demo_pr (pr_true_first_reseed_entropy :: pr_true_first_reseed_entropy :: nil)
                    two_draws = false.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The discipline's clauses as things the machine does, at the witness.
   ------------------------------------------------------------------------- *)

Definition witness_run : Run :=
  {| state := instantiate no_reseed_entropy no_reseed_nonce nil;
     pool := pr_false_reseed_entropy :: nil;
     outputs := nil |}.

Example a_draw_past_the_bound_is_refused_at_the_witness :
  completed (step demo witness_run (Draw (S (draw_bound demo)) nil)) = false.
Proof. vm_reflexivity. Qed.

Example a_run_with_a_draw_past_the_bound_is_not_disciplined :
  disciplined_run_b demo nil (Draw (S (draw_bound demo)) nil :: nil) = false.
Proof. vm_reflexivity. Qed.

Example the_lock_edge_takes_a_string_from_the_pool :
  andb (Nat.eqb (pool_left (step demo witness_run (Cross the_lock_edge))) 0)
       (Nat.eqb (reseed_counter (state_of (step demo witness_run (Cross the_lock_edge)))) 1) = true.
Proof. vm_reflexivity. Qed.

Example every_transition_takes_a_string_from_the_pool_at_the_witness :
  all_of (fun t => Nat.eqb (pool_left (step demo witness_run (Cross t))) 0) all_transitions = true.
Proof. vm_reflexivity. Qed.

Example the_discipline_silent_on_the_lock_edge_takes_nothing_there :
  Nat.eqb (pool_left (step silent_on_the_lock_edge witness_run (Cross the_lock_edge))) 1 = true.
Proof. vm_reflexivity. Qed.

Example a_lock_transition_from_an_empty_pool_halts :
  completed (step demo {| witness_run with pool := nil; outputs := nil |}
                  (Cross the_lock_edge)) = false.
Proof. vm_reflexivity. Qed.

(* The instantiation refuses an entropy input and a nonce of the wrong
   length separately, so neither length is carried by the other. *)
Example an_instantiation_refuses_each_wrong_length_on_its_own :
  andb (andb (completed (run_from demo no_reseed_entropy no_reseed_nonce nil nil nil))
             (negb (completed (run_from demo (take_of 8 no_reseed_entropy)
                                        no_reseed_nonce nil nil nil))))
       (negb (completed (run_from demo no_reseed_entropy
                                  (take_of 8 no_reseed_nonce) nil nil nil))) = true.
Proof. vm_reflexivity. Qed.


(* The interval at the witness, and the one thing about it a reader gets
   wrong: the third draw finds the counter past two and takes the pool's one
   string to reseed, and the reseed puts the counter back to one, so the
   fourth draw is inside the interval again and it is the fifth that finds
   the pool empty and halts rather than drawing on. The refusal is one draw
   later than the pool's size alone would suggest. *)
Definition three_draws : list Op := Draw corpus_draw_bits nil :: two_draws.
Definition four_draws : list Op := Draw corpus_draw_bits nil :: three_draws.
Definition five_draws : list Op := Draw corpus_draw_bits nil :: four_draws.

Example the_third_draw_reseeds_from_the_pool_and_the_fifth_halts :
  andb (andb (completed (run demo three_draws witness_run))
             (Nat.eqb (pool_left (run demo three_draws witness_run)) 0))
  (andb (completed (run demo four_draws witness_run))
        (negb (completed (run demo five_draws witness_run)))) = true.
Proof. vm_reflexivity. Qed.

Example the_third_draw_leaves_a_counter_of_two :
  Nat.eqb (reseed_counter (state_of (run demo three_draws witness_run))) 2 = true.
Proof. vm_reflexivity. Qed.

(* A counter that starts at zero admits one draw more than the interval
   before the machine reseeds: from an empty pool the standard's third draw
   halts and the alternative's goes on. *)
Definition witness_run_without_a_pool : Run :=
  {| state := instantiate no_reseed_entropy no_reseed_nonce nil; pool := nil; outputs := nil |}.

Definition witness_run_counting_from_zero : Run :=
  {| state := instantiate_with_the_counter_at_zero no_reseed_entropy no_reseed_nonce nil;
     pool := nil; outputs := nil |}.

Example the_counter_at_zero_admits_a_third_draw_the_standard_halts :
  andb (negb (completed (run demo three_draws witness_run_without_a_pool)))
       (completed (run demo three_draws witness_run_counting_from_zero)) = true.
Proof. vm_reflexivity. Qed.

Example the_counter_at_zero_agrees_with_the_standard_on_the_outputs_it_shares :
  bits_eqb (output_at (run demo two_draws witness_run_counting_from_zero) 1)
           (output_at no_reseed_run 1) = true.
Proof. rewrite no_reseed_run_is_its_literal. vm_reflexivity. Qed.

(* A halted run reports nothing rather than the last thing it held, which is
   R-15-241b's fail-stop read at the reader: no pool, no counter, no output,
   and no last-known-good arm to read one off. *)
Example a_halted_run_reports_nothing :
  andb (andb (negb (completed (run demo three_draws witness_run_without_a_pool)))
             (Nat.eqb (pool_left (run demo three_draws witness_run_without_a_pool)) 0))
       (andb (Nat.eqb (reseed_counter (state_of (run demo three_draws
                                                     witness_run_without_a_pool))) 0)
             (Nat.eqb (length_of (outputs_of (run demo three_draws
                                                  witness_run_without_a_pool))) 0)) = true.
Proof. vm_reflexivity. Qed.

(* The inverted update misses the published answer at the empty
   personalization string every family here uses, which is the branch it
   inverts. *)
Example the_inverted_update_misses_the_published_answer :
  let s0 := instantiate_with_the_inverted_update no_reseed_entropy no_reseed_nonce nil in
  bits_eqb (fst (generate_core s0 corpus_draw_bits nil)) (output_at no_reseed_run 0) = false.
Proof. rewrite no_reseed_run_is_its_literal. vm_reflexivity. Qed.

(* Both alternative instantiations start their counter where the standard's
   does, except the one whose whole point is that it does not, so the update
   and the counter are two differences and not one thing. *)
Example the_alternative_instantiations_move_one_thing_each :
  andb (Nat.eqb (reseed_counter (instantiate_with_the_inverted_update
                                   no_reseed_entropy no_reseed_nonce nil))
                (reseed_counter (instantiate no_reseed_entropy no_reseed_nonce nil)))
       (Nat.eqb (S (reseed_counter (instantiate_with_the_counter_at_zero
                                      no_reseed_entropy no_reseed_nonce nil)))
                (reseed_counter (instantiate no_reseed_entropy no_reseed_nonce nil))) = true.
Proof. vm_reflexivity. Qed.

(* And it is held to that single difference on both branches, in opposite
   directions: where provided_data is not empty the standard's result is the
   alternative's with s10.1.2.2's second pass run over it, and where it is
   empty the alternative's is the standard's with that same pass run over
   it. The pass is the same pass in both places, so the branch is the whole
   of what separates the two. *)
Example the_inverted_update_is_one_pass_from_the_standard_on_each_branch :
  let p := pr_false_reseed_entropy in
  let inv := update_with_its_branch_inverted p zero_key one_value in
  let std := hmac_drbg_update p zero_key one_value in
  let inv0 := update_with_its_branch_inverted nil zero_key one_value in
  let std0 := hmac_drbg_update nil zero_key one_value in
  andb (andb (bits_eqb (fst std) (hmac_sha256 (fst inv) (snd inv ++ separator_one ++ p)))
             (bits_eqb (snd std) (hmac_sha256 (fst std) (snd inv))))
       (andb (bits_eqb (fst inv0) (hmac_sha256 (fst std0) (snd std0 ++ separator_one ++ nil)))
             (bits_eqb (snd inv0) (hmac_sha256 (fst inv0) (snd std0)))) = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   Inhabitation witnesses (R-05-166) for each record type in this file.
   ------------------------------------------------------------------------- *)

Definition witness_SeedingDiscipline : SeedingDiscipline := demo.

Definition witness_DrbgState : DrbgState := instantiated_for_pr.

Definition witness_Run : Run := witness_run.

(* R-05-163: `run.py proofs` audits the complete native inventory. *)
