(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   HmacDrbg.v

   HMAC_DRBG over SHA-256 as NIST SP 800-90A Rev. 1 states it, s10.1.2's
   four algorithms and the s9 envelope around them, written in Gallina over
   Sha256.v's `hmac_sha256` and checked against NIST's own validation corpus;
   and R-15-241d's seeding discipline, stated as the explicit hypothesis that
   entry's acceptance asks for rather than as a uniform seed assumed by
   silence.

   What this file is, and what it is not. It is a **functional reference**
   and a **statement**: the transcription of the standard's algorithms, the
   discipline the register puts on how they are seeded and reseeded as a
   record every theorem below quantifies over, and a machine that runs the
   envelope under that discipline so that the discipline's clauses are
   things the machine does rather than sentences beside it. It is not an
   implementation, no binary corresponds to it, it is not the crypto core's
   DRBG, and it discharges no acceptance clause of any entry. It does not
   carry the FCF security proof the plan's cell names beside VST's
   `hmacdrbg/`, and nothing here reads or copies that tree: the acquisition
   route the plan left to M3.4c is taken in THIRD-PARTY.md, and the arm
   taken there is authoring against the standard.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing here executes on either
   emulator. The computed checks are decided inside the kernel, the light ones
   by conversion in the silent `Example ... := eq_refl` form and the ones that
   run a draw by the bytecode machine, which contributes nothing to the
   Print Assumptions block at the end.

   The three assurance layers, and which one this is. What is here is the
   **functional layer** and a **statement of the seeding hypothesis**, and
   neither of the other two. No constant-time property is claimed (R-05-062,
   R-05-067); no masking claim is made (R-05-004a). **No reduction and no
   distributional claim is made**, and this file is where that sentence has
   to be read most carefully, because the register's two words for what a
   DRBG carries, prediction resistance across a reseed and backtracking
   resistance across a draw, are ordinarily stated as indistinguishability
   games over a uniformly drawn seed. R-05-077a puts that reduction where
   the root is and not in the layer that consumes it. So what this file
   states under those two names is what a transcription can state and
   compute: an **ordering** property of the transcribed functions, that a
   draw's output is produced from the state before the post-draw update and
   the returned state is the update after it, so the state that leaves a
   draw contains no block of that draw's output; and a **freshness**
   property of the envelope, that a reseed takes entropy the discipline's
   pool has not supplied before and the state it leaves is a function of
   that entropy. Each is computed at the published answers and each is
   refuted of a construction that breaks it, and neither is a claim about
   any distribution.

   One Require, and what it reaches. `Require Import Sha256.` is a sibling
   artifact under proofs/ and nothing else: it carries no Require of its own,
   so the reach of this file is the prelude, that file and this one, and
   every constant enumerated at the end of both is closed under the global
   context. The list helpers below are that file's, and the ones this file
   adds are authored in the same idiom.

   The representation, which no register entry fixes and which is therefore
   a reading of this file:

   1. **Bit strings are Sha256.v's**, bytes most significant bit first, and
      every published input and answer is byte-aligned.
   2. **The DRBG's internal state is the standard's**, a record of the key
      K, the value V and the reseed counter (s10.1.2.1), with the security
      strength and the prediction-resistance flag carried by the discipline
      rather than by the state, which is where s9.1 says an instantiation
      reads them from.
   3. **The entropy source is a pool**: a list of the strings the
      conditioner (R-15-241c) has made available, consumed in order, one per
      instantiation or reseed, each checked to the discipline's seed length.
      A pool with nothing left to give halts the run, which is R-15-241b's
      fail-stop read at this layer: no draw happens on a reseed that could
      not take entropy, and no last-known-good arm exists.
   4. **Lengths are in bits**, as the standard's `requested_number_of_bits`
      and `outlen` are.

   The readings of the register this file takes:

   1. **R-15-241d's acceptance is met by a hypothesis and this is that
      hypothesis.** The entry wants the DRBG instantiated from conditioned
      root output at a stated seed length, reseeding on stated draw-count
      and interval bounds and on every RoT lifecycle or lock-state
      transition, carrying prediction resistance across a reseed and
      backtracking resistance across a draw, and its acceptance is that the
      refinement statement takes this discipline as an explicit hypothesis
      rather than assuming a uniform seed. `SeedingDiscipline` below is that
      record: the seed and nonce lengths, the draw bound, the interval
      bound, the reseed map over every transition and the
      prediction-resistance flag are its fields, `Disciplined` is the
      premise, and every theorem stated of a disciplined machine takes it.
      **No field carries a figure the register has not fixed.** The entry
      says *stated* and states none, so the seed length, the bounds and the
      strength are parameters here and the witness below takes its figures
      from the validation corpus's own case rather than from this file's
      opinion of what the platform's should be. Reported at R-15-241d, not
      closed.
   2. **The transitions are R-09-032's edges and R-09-017 through R-09-019's,
      read from RotFirmware.v's shape rather than Required from it.**
      R-09-032 fixes five lifecycle states under a fixed acyclic relation,
      raw to test, test to development or production, development and
      production to RMA, RMA terminal, and RotFirmware.v enumerates the
      states in that order; R-09-017 names the two lock states, before and
      after first unlock, R-09-018 the credential-gated transition up and
      R-09-019 the scheduled transition down. `all_transitions` is those
      five edges and those two, and a discipline is disciplined only where
      its reseed map is true on every one of them. A Require of
      RotFirmware.v would buy no theorem here, that file's Machine carrying
      a lifecycle state and no DRBG, so the enumeration is repeated by
      reading and the two files owe each other a re-reading if either moves.
   3. **The seed is never assumed uniform, anywhere.** Every theorem below
      quantifies over the entropy strings as arbitrary bit strings of the
      discipline's length, and the two published families that reseed are
      run with the corpus's own strings. What separates a fresh reseed from
      a reused one is the pool's freshness, which `fresh_pool` decides over
      the strings themselves.
   4. **The standard's envelope is transcribed and not simplified.** s9.3.1
      reseeds before a draw when the counter has passed the interval or
      prediction resistance is requested, hands the draw's additional input
      to that reseed and gives the draw none, which is the order the
      prediction-resistance family of the corpus exercises; s10.1.2.5's own
      step 1 stays as `generate`, which refuses a draw past the interval,
      and the envelope is what turns that refusal into a reseed.
   5. **The oracle enters no trust base.** Every published answer below is a
      constant inside an `Example`'s own statement, never a `Definition`;
      the corpus's inputs are definitions because they are inputs.

   What is deliberately absent, with the entry that owes each decision. A
   register gap is reported, not closed:

   a. **No figure for the seed length, the nonce length, the draw bound, the
      interval bound or the security strength.** R-15-241d says stated and
      states none; R-05-058a's Category 5 is a strength of the asymmetric
      suite and reading a DRBG strength off it would be the yardstick read
      as the measurement, which is AesGcm.v's gap (a) one primitive over.
      Owed at R-15-241d.
   b. **The standard's own maxima are not stated.** SP 800-90A Table 2
      bounds the reseed interval at 2^48 draws, one request at 2^19 bits
      and the entropy input at 2^35 bits; the prelude's `nat` cannot carry
      the first or the third and the register has not taken any of them, so
      the discipline's bounds are fields with no ceiling here. Owed at
      R-15-241d.
   c. **Which hash the DRBG rides is the plan's sentence and not an entry's**
      (Sha256.v reading 1). Owed at R-15-241d or in the plan.
   d. **The FCF security proof is not here**, and neither is any proof that
      HMAC is a pseudorandom function; both are R-05-077a's reduction layer
      and the plan's cell names VST's `hmacfcf/` as the object that would
      later carry the first. What this file's seeding hypothesis buys that
      layer is a stated premise to be discharged where the root is.
   e. **What the personalization string and the additional input carry on
      this platform is unstated**; both are parameters of every function
      below and every published case here runs with them empty.
   f. **No constant-time claim, no masking claim, no reduction** (above).

   The literals taken from the standard, and there are no others. s10.1.2.2's
   two separator bytes 0x00 and 0x01; s10.1.2.3's initial key of 0x00 bytes
   and initial value of 0x01 bytes, each outlen long; the reseed counter
   starting at one on instantiation and on reseed; and outlen, which Table 2
   gives HMAC_DRBG over SHA-256 as the digest length and which is read from
   Sha256.v rather than written again. R-09-032's five states and five edges
   and the two lock states and two edges are the register's and are
   enumerated as lists whose lengths are computed. The witness discipline's
   figures are the corpus's, read from its own strings.

   Non-vacuity (R-05-165, R-05-166). The discipline is inhabited by `demo`,
   whose premise is discharged by conversion, and the three published
   families are run through the machine under it; three disciplines the
   premise refuses are built and refuted, one silent on the lock edge, one
   whose seed is shorter than its strength and one with no interval; three
   runs the discipline refuses are built and refuted, a draw past the bound,
   a pool that reuses an entropy string and a reseed from an empty pool;
   and four constructions the standard's own sentences exclude are built
   and refuted at the published answers, an update whose second pass is
   taken on the wrong branch, a draw that updates before it emits, a reseed
   that ignores its entropy, and a counter that starts at zero. Each is
   held to its single difference: the draw that updates first still returns
   the requested length, the reseed that ignores its entropy still resets
   the counter, and the counter at zero admits exactly one draw the standard
   refuses. Inhabitation is the published answers themselves, so no check
   below holds of everything and none holds of nothing.

   Where each published answer came from, and under what instrument. The
   three cases are `COUNT = 0` of the `[SHA-256]` section with no
   personalization string and no additional input in each of
   `drbgvectors_no_reseed/HMAC_DRBG.rsp`, `drbgvectors_pr_false/HMAC_DRBG.rsp`
   and `drbgvectors_pr_true/HMAC_DRBG.rsp` (each headed "CAVS 14.3",
   generated 2013-04-02), inside NIST's CAVP archive `drbgtestvectors.zip`
   under
   csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/drbg/,
   read on 2026-09-05. The instrument is the one Sha256.v records for the
   same corpus and it is read as that file reads it: NIST's page at
   nist.gov/oism/copyrights carries three paragraphs that could each reach a
   `.rsp` file and they do not agree, the Software disclaimer stating the
   same three conditions the ACVP repository's README states before it says
   that software developed by NIST employees is not subject to copyright
   protection within the United States, so what is done here is to meet the
   strictest of them: the archive, its CAVS header line and NIST as the
   source are named above, the answers are quoted unmodified, and no change
   notice is owed because nothing was changed.
   **Every answer was recomputed on 2026-09-05 by a second and independent
   transcription of s10.1.2 in Python over the host's `hmac` before it was
   written down here**, so each reached this file by two routes. Neither
   instrument is pinned, neither enters any trust base, and nothing above the
   answers depends on them.
   ========================================================================= *)

Require Import Sha256.

Open Scope list_scope.

(* -------------------------------------------------------------------------
   Helpers this file adds to Sha256.v's, in the same idiom.
   ------------------------------------------------------------------------- *)

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. induction n as [| n IH]. reflexivity. simpl. exact IH. Qed.

Lemma andb_left : forall a b : bool, andb a b = true -> a = true.
Proof. intros a b H. destruct a. reflexivity. simpl in H. discriminate H. Qed.

Lemma andb_right : forall a b : bool, andb a b = true -> b = true.
Proof. intros a b H. destruct a. exact H. simpl in H. discriminate H. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
  match provided with
  | nil => pair k1 v1
  | _ :: _ => let k2 := hmac_sha256 k1 (v1 ++ separator_one ++ provided) in
              pair k2 (hmac_sha256 k2 v1)
  end.

(* The second pass taken on the wrong branch: run when provided_data is
   empty and skipped when it is not. It is an update in every other respect
   and every published case here provides nothing, so it is the defect the
   corpus's empty additional inputs exist to catch. *)
Definition update_with_its_branch_inverted (provided k v : list bool) : list bool * list bool :=
  let k1 := hmac_sha256 k (v ++ separator_zero ++ provided) in
  let v1 := hmac_sha256 k1 v in
  match provided with
  | nil => let k2 := hmac_sha256 k1 (v1 ++ separator_one ++ provided) in
           pair k2 (hmac_sha256 k2 v1)
  | _ :: _ => pair k1 v1
  end.

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
Proof. vm_compute. reflexivity. Qed.

Definition update_on (additional : list bool) (k v : list bool) : list bool * list bool :=
  match additional with
  | nil => pair k v
  | _ :: _ => hmac_drbg_update additional k v
  end.

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
Proof. vm_compute. reflexivity. Qed.

(* The seven edges all differ from each other in **both** endpoints, so
   they cannot tell an equality that joins its two comparisons with `and`
   from one that joins them with `or`. Two self-edges, which are not
   transitions and are here only as probes, are what separate the two. *)
Definition transition_probes : list Transition :=
  all_transitions ++ (LockEdge BeforeFirstUnlock BeforeFirstUnlock
                      :: LifecycleEdge Raw Raw :: nil).

Example the_transition_equality_decides_a_wider_probe_than_the_edges :
  eqb_decides transition_eqb transition_probes = true.
Proof. vm_compute. reflexivity. Qed.

(* An equality that is reflexive on every edge and still wrong, so that both
   halves of the test above are load-bearing: this one says every lock edge
   equals everything, which no reflexivity check catches and which the count
   catches. *)
Definition lax_transition_eqb (a b : Transition) : bool :=
  match a with
  | LockEdge _ _ => true
  | _ => transition_eqb a b
  end.

Example a_reflexive_equality_can_still_be_wrong :
  andb (all_of (fun t => lax_transition_eqb t t) all_transitions)
       (negb (eqb_decides lax_transition_eqb all_transitions)) = true.
Proof. vm_compute. reflexivity. Qed.

Example there_are_five_lifecycle_edges_and_two_lock_edges :
  andb (Nat.eqb (length_of lifecycle_edges) 5) (Nat.eqb (length_of lock_edges) 2) = true.
Proof. vm_compute. reflexivity. Qed.

Example no_edge_leaves_rma_and_none_joins_development_to_production :
  all_of (fun t => match t with
                   | LifecycleEdge Rma _ => false
                   | LifecycleEdge Development Production => false
                   | LifecycleEdge Production Development => false
                   | _ => true
                   end) all_transitions = true.
Proof. vm_compute. reflexivity. Qed.

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
           Some {| state := snd out; pool := pool r; outputs := outputs r ++ (fst out :: nil) |}
  | Reseed additional =>
      match take_entropy d (pool r) with
      | None => None
      | Some er => Some {| state := reseed (state r) (fst er) additional; pool := snd er;
                           outputs := outputs r |}
      end
  | Cross t =>
      if reseed_on d t
      then match take_entropy d (pool r) with
           | None => None
           | Some er => Some {| state := reseed (state r) (fst er) nil; pool := snd er;
                                outputs := outputs r |}
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
  match r with None => false | Some _ => true end.

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
        (all_of (fun op => match op with
                           | Draw bits _ => Nat.leb bits (draw_bound d)
                           | _ => true
                           end) ops))).

(* -------------------------------------------------------------------------
   What is stated of an arbitrary discipline, an arbitrary state and an
   arbitrary run.
   ------------------------------------------------------------------------- *)

Theorem a_reseed_resets_the_counter :
  forall (s : DrbgState) (entropy additional : list bool),
    reseed_counter (reseed s entropy additional) = 1.
Proof. intros. reflexivity. Qed.

Theorem a_draw_advances_the_counter :
  forall (s : DrbgState) (bits : nat) (additional : list bool),
    reseed_counter (snd (generate_core s bits additional)) = S (reseed_counter s).
Proof. intros. reflexivity. Qed.

(* The ordering the standard fixes and backtracking resistance rests on: the
   output of a draw is the leftmost bits of the blocks drawn from the state
   before the post-draw update, and the state that leaves is that update
   over the last drawn value. Stated by unfolding, so that the alternative
   below has an order to invert. *)
Theorem a_draw_emits_before_it_updates :
  forall (s : DrbgState) (bits : nat) (additional : list bool),
    let kv0 := update_on additional (key s) (value s) in
    let drawn := draw_blocks (blocks_for bits) (fst kv0) (snd kv0) nil in
    fst (generate_core s bits additional) = take_of bits (fst drawn)
    /\ key (snd (generate_core s bits additional))
       = fst (hmac_drbg_update additional (fst kv0) (snd drawn))
    /\ value (snd (generate_core s bits additional))
       = snd (hmac_drbg_update additional (fst kv0) (snd drawn)).
Proof. intros. split. reflexivity. split. reflexivity. reflexivity. Qed.

Theorem a_draw_past_the_interval_is_refused_by_the_algorithm :
  forall (interval : nat) (s : DrbgState) (bits : nat) (additional : list bool),
    Nat.ltb interval (reseed_counter s) = true -> generate interval s bits additional = None.
Proof. intros interval s bits additional H. unfold generate. rewrite H. reflexivity. Qed.

Theorem a_draw_past_the_bound_is_refused :
  forall (d : SeedingDiscipline) (r : Run) (bits : nat) (additional : list bool),
    Nat.ltb (draw_bound d) bits = true -> step d r (Draw bits additional) = None.
Proof. intros d r bits additional H. unfold step. rewrite H. reflexivity. Qed.

Theorem every_transition_reseeds_under_a_disciplined_discipline :
  forall d : SeedingDiscipline, Disciplined d -> all_of (reseed_on d) all_transitions = true.
Proof.
  intros d H. unfold Disciplined, disciplined_b in H.
  apply andb_right in H. apply andb_right in H. apply andb_right in H. apply andb_right in H.
  exact H.
Qed.

Theorem the_lock_edge_reseeds_under_a_disciplined_discipline :
  forall d : SeedingDiscipline, Disciplined d -> reseed_on d the_lock_edge = true.
Proof.
  intros d H. apply every_transition_reseeds_under_a_disciplined_discipline in H.
  simpl in H.
  apply andb_right in H. apply andb_right in H. apply andb_right in H.
  apply andb_right in H. apply andb_right in H. apply andb_right in H.
  apply andb_left in H. exact H.
Qed.

(* A lock transition under a disciplined discipline takes the next string of
   the pool and leaves the state reseeded from it. *)
Theorem a_lock_transition_takes_fresh_entropy :
  forall (d : SeedingDiscipline) (r : Run) (e : list bool) (rest : list (list bool)),
    Disciplined d ->
    Nat.eqb (length_of e) (seed_length d) = true ->
    pool r = e :: rest ->
    step d r (Cross the_lock_edge)
    = Some {| state := reseed (state r) e nil; pool := rest; outputs := outputs r |}.
Proof.
  intros d r e rest HD HL HP. unfold step.
  rewrite (the_lock_edge_reseeds_under_a_disciplined_discipline d HD).
  unfold take_entropy. rewrite HP. rewrite HL. reflexivity.
Qed.

(* A draw past the interval under a disciplined discipline takes fresh
   entropy before it draws, and the state that leaves has counted one draw
   since a reseed. *)
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
  intros d r bits additional e rest HB HI HL HP. unfold step. rewrite HB. rewrite HI.
  destruct (prediction_resistance d); simpl; unfold take_entropy; rewrite HP; rewrite HL;
  (eexists; split; [reflexivity | split; [reflexivity | reflexivity]]).
Qed.

(* A pool with nothing left halts a reseed rather than reseeding with
   nothing, for every discipline and every state. *)
Theorem an_empty_pool_halts_a_reseed :
  forall (d : SeedingDiscipline) (r : Run) (additional : list bool),
    pool r = nil -> step d r (Reseed additional) = None.
Proof. intros d r additional H. unfold step. unfold take_entropy. rewrite H. reflexivity. Qed.

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
  {| security_strength := security_strength demo;
     seed_length := seed_length demo;
     nonce_length := nonce_length demo;
     draw_bound := draw_bound demo;
     interval_bound := interval_bound demo;
     reseed_on := reseed_on demo;
     prediction_resistance := true |}.

Example the_witness_is_disciplined : Disciplined demo.
Proof. vm_compute. reflexivity. Qed.

Example the_prediction_resistant_witness_is_disciplined : Disciplined demo_pr.
Proof. vm_compute. reflexivity. Qed.

(* Three disciplines the premise refuses, each the witness with one field
   moved. *)
Definition silent_on_the_lock_edge : SeedingDiscipline :=
  {| security_strength := security_strength demo;
     seed_length := seed_length demo;
     nonce_length := nonce_length demo;
     draw_bound := draw_bound demo;
     interval_bound := interval_bound demo;
     reseed_on := fun t => negb (transition_eqb t the_lock_edge);
     prediction_resistance := false |}.

Definition seeded_below_its_strength : SeedingDiscipline :=
  {| security_strength := security_strength demo;
     seed_length := security_strength demo - 1;
     nonce_length := nonce_length demo;
     draw_bound := draw_bound demo;
     interval_bound := interval_bound demo;
     reseed_on := reseed_on demo;
     prediction_resistance := false |}.

Definition with_no_interval : SeedingDiscipline :=
  {| security_strength := security_strength demo;
     seed_length := seed_length demo;
     nonce_length := nonce_length demo;
     draw_bound := draw_bound demo;
     interval_bound := 0;
     reseed_on := reseed_on demo;
     prediction_resistance := false |}.

Example the_discipline_silent_on_the_lock_edge_is_refused :
  disciplined_b silent_on_the_lock_edge = false.
Proof. vm_compute. reflexivity. Qed.

Example the_discipline_silent_on_the_lock_edge_reseeds_on_every_other_edge :
  all_of (fun t => orb (transition_eqb t the_lock_edge) (reseed_on silent_on_the_lock_edge t))
         all_transitions = true.
Proof. vm_compute. reflexivity. Qed.

Example the_discipline_seeded_below_its_strength_is_refused :
  disciplined_b seeded_below_its_strength = false.
Proof. vm_compute. reflexivity. Qed.

Example the_discipline_with_no_interval_is_refused :
  disciplined_b with_no_interval = false.
Proof. vm_compute. reflexivity. Qed.

(* A fourth, whose nonce is one bit shorter than the witness's, which is the
   only clause of s8.6.7 the three above leave undecided. *)
Definition nonced_below_half_its_strength : SeedingDiscipline :=
  {| security_strength := security_strength demo;
     seed_length := seed_length demo;
     nonce_length := nonce_length demo - 1;
     draw_bound := draw_bound demo;
     interval_bound := interval_bound demo;
     reseed_on := reseed_on demo;
     prediction_resistance := false |}.

Example the_discipline_nonced_below_half_its_strength_is_refused :
  disciplined_b nonced_below_half_its_strength = false.
Proof. vm_compute. reflexivity. Qed.

(* Each of the four is refused at a boundary and not somewhere past one: the
   short seed is one bit under the strength, the short nonce one bit under
   the witness's, and one more bit of either is what the witness has. *)
Example the_two_short_lengths_are_short_by_one_bit :
  andb (andb (Nat.eqb (S (seed_length seeded_below_its_strength)) (security_strength demo))
             (Nat.leb (security_strength demo) (seed_length demo)))
       (andb (Nat.eqb (S (nonce_length nonced_below_half_its_strength)) (nonce_length demo))
             (Nat.leb (security_strength demo) (2 * nonce_length demo))) = true.
Proof. vm_compute. reflexivity. Qed.

(* Each of the four is the witness with one field moved and no other, which
   is what "held to its single difference" means here: the flag none of them
   is about stays where the witness put it, and so does the strength. *)
Example the_four_refused_disciplines_move_one_field_each :
  all_of (fun d => andb (negb (prediction_resistance d))
                        (Nat.eqb (security_strength d) (security_strength demo)))
         (silent_on_the_lock_edge :: seeded_below_its_strength :: with_no_interval
          :: nonced_below_half_its_strength :: nil) = true.
Proof. vm_compute. reflexivity. Qed.

(* The bounds are bounds and not thresholds, and the flag beside them is a
   request and not an admission condition. The witness's own figures stay
   out of the definition: what is decided is which pairs of bounds the
   premise admits, so the numbers live inside the statements that decide. *)
Definition bounded_at (draw interval : nat) (pr : bool) : SeedingDiscipline :=
  {| security_strength := security_strength demo;
     seed_length := seed_length demo;
     nonce_length := nonce_length demo;
     draw_bound := draw;
     interval_bound := interval;
     reseed_on := reseed_on demo;
     prediction_resistance := pr |}.

Example one_is_the_smallest_bound_and_zero_is_refused_on_either :
  andb (disciplined_b (bounded_at 1 1 false))
  (andb (negb (disciplined_b (bounded_at 0 1 false)))
        (negb (disciplined_b (bounded_at 1 0 false)))) = true.
Proof. vm_compute. reflexivity. Qed.

Example prediction_resistance_is_requested_and_not_required :
  andb (disciplined_b (bounded_at 1 1 false))
       (disciplined_b (bounded_at 1 1 true)) = true.
Proof. vm_compute. reflexivity. Qed.

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

Example the_three_families_complete_and_use_their_whole_pool :
  andb (andb (completed no_reseed_run) (Nat.eqb (pool_left no_reseed_run) 0))
  (andb (andb (completed pr_false_run) (Nat.eqb (pool_left pr_false_run) 0))
        (andb (completed pr_true_run) (Nat.eqb (pool_left pr_true_run) 0))) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_three_families_are_disciplined_runs :
  andb (disciplined_run_b demo nil two_draws)
  (andb (disciplined_run_b demo (pr_false_reseed_entropy :: nil) (Reseed nil :: two_draws))
        (disciplined_run_b demo_pr
           (pr_true_first_reseed_entropy :: pr_true_second_reseed_entropy :: nil) two_draws)) = true.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

Example the_two_draws_of_a_run_differ :
  bits_eqb (output_at no_reseed_run 0) (output_at no_reseed_run 1) = false.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

Example the_draw_that_updates_first_leaves_its_last_block_as_its_value :
  bits_eqb (last_of (blocks_of_output (fst first_draw_updating_first)) nil)
           (value (snd first_draw_updating_first)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_draw_that_updates_first_keeps_the_length_and_the_counter :
  andb (Nat.eqb (length_of (fst first_draw_updating_first)) corpus_draw_bits)
       (Nat.eqb (reseed_counter (snd first_draw_updating_first))
                (reseed_counter (snd first_draw))) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_draw_that_updates_first_misses_the_published_answer :
  bits_eqb (fst first_draw_updating_first) (output_at no_reseed_run 0) = false.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

Example the_reseed_that_ignores_its_entropy_leaves_one_state :
  andb (bits_eqb (key (reseed_ignoring_its_entropy instantiated_for_pr pr_true_first_reseed_entropy nil))
                 (key (reseed_ignoring_its_entropy instantiated_for_pr pr_true_second_reseed_entropy nil)))
       (Nat.eqb (reseed_counter (reseed_ignoring_its_entropy instantiated_for_pr
                                                             pr_true_first_reseed_entropy nil)) 1)
  = true.
Proof. vm_compute. reflexivity. Qed.

Example a_pool_that_reuses_a_string_is_not_fresh :
  andb (negb (fresh_pool (pr_true_first_reseed_entropy :: pr_true_first_reseed_entropy :: nil)))
       (fresh_pool (pr_true_first_reseed_entropy :: pr_true_second_reseed_entropy :: nil)) = true.
Proof. vm_compute. reflexivity. Qed.

Example a_run_over_a_reused_pool_is_refused_by_the_discipline :
  disciplined_run_b demo_pr (pr_true_first_reseed_entropy :: pr_true_first_reseed_entropy :: nil)
                    two_draws = false.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The discipline's clauses as things the machine does, at the witness.
   ------------------------------------------------------------------------- *)

Definition witness_run : Run :=
  {| state := instantiate no_reseed_entropy no_reseed_nonce nil;
     pool := pr_false_reseed_entropy :: nil;
     outputs := nil |}.

Example a_draw_past_the_bound_is_refused_at_the_witness :
  completed (step demo witness_run (Draw (S (draw_bound demo)) nil)) = false.
Proof. vm_compute. reflexivity. Qed.

Example a_run_with_a_draw_past_the_bound_is_not_disciplined :
  disciplined_run_b demo nil (Draw (S (draw_bound demo)) nil :: nil) = false.
Proof. vm_compute. reflexivity. Qed.

Example the_lock_edge_takes_a_string_from_the_pool :
  andb (Nat.eqb (pool_left (step demo witness_run (Cross the_lock_edge))) 0)
       (Nat.eqb (reseed_counter (state_of (step demo witness_run (Cross the_lock_edge)))) 1) = true.
Proof. vm_compute. reflexivity. Qed.

Example every_transition_takes_a_string_from_the_pool_at_the_witness :
  all_of (fun t => Nat.eqb (pool_left (step demo witness_run (Cross t))) 0) all_transitions = true.
Proof. vm_compute. reflexivity. Qed.

Example the_discipline_silent_on_the_lock_edge_takes_nothing_there :
  Nat.eqb (pool_left (step silent_on_the_lock_edge witness_run (Cross the_lock_edge))) 1 = true.
Proof. vm_compute. reflexivity. Qed.

Example a_lock_transition_from_an_empty_pool_halts :
  completed (step demo {| state := state witness_run; pool := nil; outputs := nil |}
                  (Cross the_lock_edge)) = false.
Proof. vm_compute. reflexivity. Qed.

(* The instantiation refuses an entropy input and a nonce of the wrong
   length separately, so neither length is carried by the other. *)
Example an_instantiation_refuses_each_wrong_length_on_its_own :
  andb (andb (completed (run_from demo no_reseed_entropy no_reseed_nonce nil nil nil))
             (negb (completed (run_from demo (take_of 8 no_reseed_entropy)
                                        no_reseed_nonce nil nil nil))))
       (negb (completed (run_from demo no_reseed_entropy
                                  (take_of 8 no_reseed_nonce) nil nil nil))) = true.
Proof. vm_compute. reflexivity. Qed.


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
Proof. vm_compute. reflexivity. Qed.

Example the_third_draw_leaves_a_counter_of_two :
  Nat.eqb (reseed_counter (state_of (run demo three_draws witness_run))) 2 = true.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

Example the_counter_at_zero_agrees_with_the_standard_on_the_outputs_it_shares :
  bits_eqb (output_at (run demo two_draws witness_run_counting_from_zero) 1)
           (output_at no_reseed_run 1) = true.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

(* The inverted update misses the published answer at the empty
   personalization string every family here uses, which is the branch it
   inverts. *)
Example the_inverted_update_misses_the_published_answer :
  let s0 := instantiate_with_the_inverted_update no_reseed_entropy no_reseed_nonce nil in
  bits_eqb (fst (generate_core s0 corpus_draw_bits nil)) (output_at no_reseed_run 0) = false.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The R-05-163 assumption gate reads this block. Every shipped constant is
   enumerated from its own proof term and held against the declared set: the
   one Require above is a sibling under proofs/ that Requires nothing, so
   there is no Admitted, no Axiom and no top-level Parameter reachable, and
   nothing is declared inside the development to make the gate pass.
   ------------------------------------------------------------------------- *)

Print Assumptions nat_eqb_refl.
Print Assumptions andb_left.
Print Assumptions andb_right.
Print Assumptions fresh_pool.
Print Assumptions outlen_bits.
Print Assumptions outlen_bytes.
Print Assumptions zero_key.
Print Assumptions one_value.
Print Assumptions separator_zero.
Print Assumptions separator_one.
Print Assumptions the_initial_key_and_value_are_outlen_long.
Print Assumptions DrbgState.
Print Assumptions hmac_drbg_update.
Print Assumptions update_with_its_branch_inverted.
Print Assumptions instantiate_over.
Print Assumptions instantiate.
Print Assumptions instantiate_with_the_counter_at_zero.
Print Assumptions instantiate_with_the_inverted_update.
Print Assumptions reseed.
Print Assumptions reseed_ignoring_its_entropy.
Print Assumptions draw_blocks.
Print Assumptions blocks_for.
Print Assumptions a_partial_block_still_costs_a_block.
Print Assumptions update_on.
Print Assumptions generate_core.
Print Assumptions generate_core_updating_before_it_emits.
Print Assumptions generate.
Print Assumptions Lifecycle.
Print Assumptions LockState.
Print Assumptions Transition.
Print Assumptions lifecycle_eqb.
Print Assumptions lock_eqb.
Print Assumptions transition_eqb.
Print Assumptions lifecycle_edges.
Print Assumptions lock_edges.
Print Assumptions all_transitions.
Print Assumptions the_lock_edge.
Print Assumptions all_lifecycles.
Print Assumptions all_lock_states.
Print Assumptions eqb_decides.
Print Assumptions the_three_equalities_decide_their_own_enumerations.
Print Assumptions transition_probes.
Print Assumptions the_transition_equality_decides_a_wider_probe_than_the_edges.
Print Assumptions lax_transition_eqb.
Print Assumptions a_reflexive_equality_can_still_be_wrong.
Print Assumptions there_are_five_lifecycle_edges_and_two_lock_edges.
Print Assumptions no_edge_leaves_rma_and_none_joins_development_to_production.
Print Assumptions SeedingDiscipline.
Print Assumptions disciplined_b.
Print Assumptions Disciplined.
Print Assumptions Op.
Print Assumptions Run.
Print Assumptions take_entropy.
Print Assumptions step.
Print Assumptions run.
Print Assumptions start.
Print Assumptions run_from.
Print Assumptions completed.
Print Assumptions outputs_of.
Print Assumptions output_at.
Print Assumptions pool_left.
Print Assumptions state_of.
Print Assumptions disciplined_run_b.
Print Assumptions a_reseed_resets_the_counter.
Print Assumptions a_draw_advances_the_counter.
Print Assumptions a_draw_emits_before_it_updates.
Print Assumptions a_draw_past_the_interval_is_refused_by_the_algorithm.
Print Assumptions a_draw_past_the_bound_is_refused.
Print Assumptions every_transition_reseeds_under_a_disciplined_discipline.
Print Assumptions the_lock_edge_reseeds_under_a_disciplined_discipline.
Print Assumptions a_lock_transition_takes_fresh_entropy.
Print Assumptions a_draw_past_the_interval_reseeds_first.
Print Assumptions an_empty_pool_halts_a_reseed.
Print Assumptions no_reseed_entropy.
Print Assumptions no_reseed_nonce.
Print Assumptions pr_false_entropy.
Print Assumptions pr_false_nonce.
Print Assumptions pr_false_reseed_entropy.
Print Assumptions pr_true_entropy.
Print Assumptions pr_true_nonce.
Print Assumptions pr_true_first_reseed_entropy.
Print Assumptions pr_true_second_reseed_entropy.
Print Assumptions corpus_draw_bits.
Print Assumptions demo.
Print Assumptions demo_pr.
Print Assumptions the_witness_is_disciplined.
Print Assumptions the_prediction_resistant_witness_is_disciplined.
Print Assumptions silent_on_the_lock_edge.
Print Assumptions seeded_below_its_strength.
Print Assumptions with_no_interval.
Print Assumptions the_discipline_silent_on_the_lock_edge_is_refused.
Print Assumptions the_discipline_silent_on_the_lock_edge_reseeds_on_every_other_edge.
Print Assumptions the_discipline_seeded_below_its_strength_is_refused.
Print Assumptions the_discipline_with_no_interval_is_refused.
Print Assumptions nonced_below_half_its_strength.
Print Assumptions the_discipline_nonced_below_half_its_strength_is_refused.
Print Assumptions the_two_short_lengths_are_short_by_one_bit.
Print Assumptions the_four_refused_disciplines_move_one_field_each.
Print Assumptions bounded_at.
Print Assumptions one_is_the_smallest_bound_and_zero_is_refused_on_either.
Print Assumptions prediction_resistance_is_requested_and_not_required.
Print Assumptions two_draws.
Print Assumptions no_reseed_run.
Print Assumptions pr_false_run.
Print Assumptions pr_true_run.
Print Assumptions the_three_families_complete_and_use_their_whole_pool.
Print Assumptions the_three_families_are_disciplined_runs.
Print Assumptions the_second_draw_without_a_reseed.
Print Assumptions the_second_draw_after_one_reseed.
Print Assumptions the_second_draw_under_prediction_resistance.
Print Assumptions the_two_draws_of_a_run_differ.
Print Assumptions the_algorithm_alone_reaches_the_first_family.
Print Assumptions first_draw.
Print Assumptions first_draw_updating_first.
Print Assumptions blocks_of_output.
Print Assumptions the_state_that_leaves_a_draw_carries_no_block_of_its_output.
Print Assumptions the_draw_that_updates_first_leaves_its_last_block_as_its_value.
Print Assumptions the_draw_that_updates_first_keeps_the_length_and_the_counter.
Print Assumptions the_draw_that_updates_first_misses_the_published_answer.
Print Assumptions instantiated_for_pr.
Print Assumptions two_fresh_strings_leave_two_states.
Print Assumptions the_reseed_that_ignores_its_entropy_leaves_one_state.
Print Assumptions a_pool_that_reuses_a_string_is_not_fresh.
Print Assumptions a_run_over_a_reused_pool_is_refused_by_the_discipline.
Print Assumptions witness_run.
Print Assumptions a_draw_past_the_bound_is_refused_at_the_witness.
Print Assumptions a_run_with_a_draw_past_the_bound_is_not_disciplined.
Print Assumptions the_lock_edge_takes_a_string_from_the_pool.
Print Assumptions every_transition_takes_a_string_from_the_pool_at_the_witness.
Print Assumptions the_discipline_silent_on_the_lock_edge_takes_nothing_there.
Print Assumptions a_lock_transition_from_an_empty_pool_halts.
Print Assumptions an_instantiation_refuses_each_wrong_length_on_its_own.
Print Assumptions three_draws.
Print Assumptions four_draws.
Print Assumptions five_draws.
Print Assumptions the_third_draw_reseeds_from_the_pool_and_the_fifth_halts.
Print Assumptions the_third_draw_leaves_a_counter_of_two.
Print Assumptions witness_run_without_a_pool.
Print Assumptions witness_run_counting_from_zero.
Print Assumptions the_counter_at_zero_admits_a_third_draw_the_standard_halts.
Print Assumptions the_counter_at_zero_agrees_with_the_standard_on_the_outputs_it_shares.
Print Assumptions a_halted_run_reports_nothing.
Print Assumptions the_inverted_update_misses_the_published_answer.
Print Assumptions the_alternative_instantiations_move_one_thing_each.
Print Assumptions the_inverted_update_is_one_pass_from_the_standard_on_each_branch.
