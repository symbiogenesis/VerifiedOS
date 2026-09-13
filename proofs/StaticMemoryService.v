(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   StaticMemoryService.v

   The frame service of the static-memory transformation experiment
   (tools/vos/static_memory_transform.py), at the level of list functions:
   the value specification `reference`, the byte arithmetic the emitted
   map instruction uses, a functional model of each emitted variant's data
   flow, and the theorem that every model returns `reference` on every
   input list, under the one hypothesis the chunk variants carry, that
   their chunk starts partition the index interval.

   What this file is. A machine-checked form of the elementary algorithm
   argument docs/implementation/static-memory-transformations.md states in
   prose: modular addition is associative, so reducing consecutive chunks
   gives the whole-list checksum; the shift/add/mask map equals the
   multiply/mod map on every byte; and an in-place pass that overwrites
   element i after reading it, then XORs only after the reduction is
   complete, emits the same bytes in index order. Everything below is
   proved outright over Rocq's standard library: nothing is admitted and
   no axiom is declared. The Print Assumptions block at the end reports
   the theorems and the named examples closed under the global context;
   it is a reader's check and not the inventory, since `run.py proofs`
   enumerates every constant of the file itself, which is the R-05-163
   gate.

   What this file is not. It does not model the interpreter. The Python
   `execute` walks an instruction list over a flat byte array with base
   offsets, bounded views, descriptor reads, reserve and retire scrubs,
   the control-workspace checksum byte and the erasure check after return;
   the functions here take a list of naturals and return one. That the
   program `emit_program` writes for a variant computes the function its
   model names is the executable-test claim `equivalence_findings` makes
   over the report's frames, and it stays an executable claim: no
   refinement from the emitted schedule to these functions is stated here,
   and authority, index checks, zeroization, staging copies and DMA are
   outside every theorem in this file. The chunk models place a chunk's
   outputs by chunk order where the schedule writes them at their start
   offsets, which agree under the partition hypothesis and not otherwise.
   The costs the experiment compares (reservations, traffic, operation
   counts) are not modelled at all; the file decides only that the
   candidates agree on their output.

   The models, six over the seven rows of the emitted variant table,
   because two rows share one data flow:
   - `retained` maps, folds the checksum, then maps the XOR over the kept
     mapped list (lexical-cache and phased-cache, which differ in
     retirement and not in data flow).
   - `early_release chunks` maps and reduces the input slice by slice
     into one mapped list and XORs over that whole list
     (early-input-release, whose input arrives in chunks while its mapped
     buffer and its XOR pass are whole-length).
   - `chunked chunks` maps and reduces slice by slice, then XORs each kept
     mapped chunk and concatenates the chunk outputs (chunked-cache; the
     stage copy is a pure move and leaves no functional trace).
   - `tiled chunks` recomputes the map of the input slice in the second
     pass instead of reading a kept mapped chunk (tiled-rematerialized).
   - `fused` folds the checksum over the map applied on the fly and
     recomputes the map again under the XOR (fused-rematerialized).
   - `in_place` is a sequential state machine over a memory function:
     `map_sum_step` reads element i, overwrites it with its mapped value
     and accumulates the checksum over that value; `xor_step` runs only
     after the whole reduction; the readout reads the memory back in
     index order, as the emit instructions do (in-place-phased).
   The three chunk models are one function up to a reassociation of maps:
   `early_release_is_chunked` is `concat_finish` and `tiled_is_chunked`
   is `map_map`. That is the whole functional content of the two
   observations that a stage copy is a pure move and that recomputing a
   pure map returns what was stored; the models are stated separately
   because each mirrors a different emitted schedule, and none of them
   carries anything about what the recomputation or the copy costs.
   `generator_chunks tile len` is the chunk list `emit_program` builds,
   the starts of `range(0, length, tile)` with `min(tile, length - start)`
   counts; `generator_chunks_clamp` shows the generator's clamp of the
   tile to the length changes no chunk, and `generator_chunks_partition`
   proves the list satisfies `partitions` for every positive tile, so the
   chunk theorems apply to every program the generator emits.
   `partitions` is a sufficient condition and not a necessary one:
   `single_chunk_agrees` shows one chunk reaching past the end of the
   list still returns the reference, because a slice truncates there, and
   `partitions_not_necessary` names such a chunk list on the demo frame.
   What the hypothesis excludes is the defect a wrong chunk list
   introduces: one that drops an index or repeats one fails it and, on
   the demo frame, returns a different list.

   Byte representation. Bytes are naturals below 256, `is_byte`. The
   equivalences are stated for every list of naturals, because every
   model uses the same total functions and no theorem needs the bound;
   `reference_bytes` shows the specification returns bytes on any input,
   which is the closure the Python `bytes` type takes for granted, and
   `emitted_map_is_map_byte` is proved algebraically for every natural,
   with `emitted_map_checked_over_every_byte` re-deciding it by
   computation over the 256 byte values, the domain the emitted
   instruction actually sees.

   Why R-08-019e. It is cited and not claimed. Its subject, a peak too
   large and the three levers that act on the artifact, is not modelled
   here: no reservation, no peak and no cost appears in this file. The
   contact is the second lever, recompute rather than store, which the
   tiled and fused variants exercise and which acts on the artifact only
   where recomputation returns the same output; `tiled_correct` and
   `fused_correct` are that equality for this service, and at this level
   the equality is a reassociation of maps rather than a fact about the
   trade. The certificate that prices the trade in space and time is not
   touched here, so no entry about that certificate is cited, and whether
   the entry governs this artifact is the review gate's reading.

   Non-vacuity (R-05-165, R-05-166). `demo_frame` is a concrete frame
   whose outputs every model computes by `vm_compute`,
   `witness_InPlaceState` inhabits the one record theorems quantify over,
   and three wrong variants are refuted on that frame: the XOR pass
   replaced by a copy, which mirrors the mutant the Python tests apply, a
   chunk list missing the last two indices, and one repeating the first
   two in their place, both defects no generator path produces and the
   hypothesis exists to exclude. The copy and the repetition return lists
   of the reference's length with different values, and the omission
   differs already on the prefix the two outputs share, so each
   refutation is by value and not by length alone; the two chunk lists
   also fail `partitions`.

   No landing credit. This file is research evidence for the backlog item
   it answers; the requirements register remains authoritative, nothing
   here accepts a requirement, and the ledger rows it generates are
   citations rather than claims except where a witness lemma says so.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-165 R-05-166 R-08-019e
   SHA256: 40d3879b85c7a80b847798a8fe377e06bc29b5267c19594f22e20b26c016fd4f
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Lia PeanoNat.
Import ListNotations.

(* -------------------------------------------------------------------------
   Bytes and the two spellings of the map. The reference multiplies and
   reduces mod 256; the emitted instruction shifts, adds and masks with
   255, which is what `execute`'s `mapped` does. `byte_mask` is kept as a
   constant so the mask reads as the literal the interpreter writes.
   ------------------------------------------------------------------------- *)

Definition is_byte (b : nat) : Prop := b < 256.

Definition byte_mask : nat := 255.

Lemma byte_mask_is_ones : byte_mask = Nat.ones 8.
Proof. vm_compute. reflexivity. Qed.

Lemma land_mask_mod : forall a, Nat.land a byte_mask = a mod 256.
Proof. intro a. rewrite byte_mask_is_ones, Nat.land_ones. reflexivity. Qed.

Definition map_byte (b : nat) : nat := (3 * b + 1) mod 256.

Definition emitted_map (b : nat) : nat := Nat.land (Nat.shiftl b 1 + b + 1) byte_mask.

Theorem emitted_map_is_map_byte : forall b, emitted_map b = map_byte b.
Proof.
  intro b. unfold emitted_map, map_byte.
  rewrite land_mask_mod, Nat.shiftl_mul_pow2.
  f_equal. replace (2 ^ 1) with 2 by reflexivity. lia.
Qed.

(* The same fact re-decided by computation over the byte domain alone. *)
Example emitted_map_checked_over_every_byte :
  forallb (fun b => emitted_map b =? map_byte b) (seq 0 256) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The checksum. `step` is the `sum` instruction's `(control + value) & 255`;
   the reference takes the whole-list sum mod 256. Associativity of modular
   addition is `reduce_from`, stated for any starting accumulator below 256
   so that a chunk's fold can continue another chunk's.
   ------------------------------------------------------------------------- *)

Definition step (acc t : nat) : nat := Nat.land (acc + t) byte_mask.

Lemma step_mod : forall acc t, step acc t = (acc + t) mod 256.
Proof. intros. unfold step. apply land_mask_mod. Qed.

Lemma reduce_from : forall ts a, a < 256 -> fold_left step ts a = (a + list_sum ts) mod 256.
Proof.
  induction ts as [| t ts IH]; intros a Ha.
  - change (fold_left step [] a) with a. change (list_sum []) with 0.
    rewrite Nat.add_0_r. symmetry. apply Nat.mod_small. exact Ha.
  - change (fold_left step (t :: ts) a) with (fold_left step ts (step a t)).
    change (list_sum (t :: ts)) with (t + list_sum ts).
    rewrite step_mod.
    rewrite IH by (apply Nat.mod_upper_bound; discriminate).
    rewrite Nat.Div0.add_mod_idemp_l. f_equal. lia.
Qed.

Definition reduce (ts : list nat) : nat := fold_left step ts 0.

Lemma reduce_is_checksum : forall ts, reduce ts = list_sum ts mod 256.
Proof. intro ts. unfold reduce. rewrite reduce_from by lia. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The reference and the shared phases. `mapped` is the map pass with the
   emitted arithmetic, `finish c` the XOR pass against a fixed checksum.
   ------------------------------------------------------------------------- *)

Definition reference (xs : list nat) : list nat :=
  map (fun t => Nat.lxor t (list_sum (map map_byte xs) mod 256)) (map map_byte xs).

Definition mapped (xs : list nat) : list nat := map emitted_map xs.

Definition finish (c : nat) (ts : list nat) : list nat := map (fun t => Nat.lxor t c) ts.

Lemma mapped_is_map_byte : forall xs, mapped xs = map map_byte xs.
Proof. intro xs. apply map_ext. exact emitted_map_is_map_byte. Qed.

(* -------------------------------------------------------------------------
   Variant 1: the retained mapped list (lexical-cache, phased-cache).
   ------------------------------------------------------------------------- *)

Definition retained (xs : list nat) : list nat := finish (reduce (mapped xs)) (mapped xs).

Theorem retained_correct : forall xs, retained xs = reference xs.
Proof.
  intro xs. unfold retained, reference, finish.
  rewrite mapped_is_map_byte, reduce_is_checksum. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Chunks. A chunk is a (start, count) pair over the index interval;
   `covers from chunks len` says the chunks are consecutive from `from` and
   end exactly at `len`, and `partitions` is that from index 0. `slice` is
   the bounded view a chunk instruction reads through.
   ------------------------------------------------------------------------- *)

Definition slice (xs : list nat) (c : nat * nat) : list nat :=
  firstn (snd c) (skipn (fst c) xs).

Fixpoint covers (from : nat) (chunks : list (nat * nat)) (len : nat) : Prop :=
  match chunks with
  | [] => from = len
  | c :: rest => fst c = from /\ covers (from + snd c) rest len
  end.

Definition partitions (chunks : list (nat * nat)) (len : nat) : Prop :=
  covers 0 chunks len.

Lemma concat_slices : forall xs chunks from,
  covers from chunks (length xs) -> concat (map (slice xs) chunks) = skipn from xs.
Proof.
  intros xs chunks. induction chunks as [| [s k] rest IH]; intros from Hc.
  - simpl in Hc. subst from. symmetry. apply skipn_all.
  - simpl in Hc. destruct Hc as [Hs Hc]. subst s.
    change (concat (map (slice xs) ((from, k) :: rest)))
      with (slice xs (from, k) ++ concat (map (slice xs) rest)).
    rewrite (IH _ Hc). unfold slice. cbn [fst snd].
    rewrite (Nat.add_comm from k), <- skipn_skipn. apply firstn_skipn.
Qed.

Lemma fold_chunks : forall (chunks : list (list nat)) a,
  fold_left (fun acc ch => fold_left step ch acc) chunks a = fold_left step (concat chunks) a.
Proof.
  induction chunks as [| ch rest IH]; intro a.
  - reflexivity.
  - change (fold_left (fun acc ch => fold_left step ch acc) (ch :: rest) a)
      with (fold_left (fun acc ch => fold_left step ch acc) rest (fold_left step ch a)).
    change (concat (ch :: rest)) with (ch ++ concat rest).
    rewrite fold_left_app. apply IH.
Qed.

Lemma concat_finish : forall c (chunks : list (list nat)),
  concat (map (finish c) chunks) = finish c (concat chunks).
Proof. intros. unfold finish. rewrite concat_map. reflexivity. Qed.

Lemma concat_mapped : forall (segments : list (list nat)),
  concat (map mapped segments) = mapped (concat segments).
Proof. intros. unfold mapped. rewrite concat_map. reflexivity. Qed.

Lemma mapped_chunks : forall xs chunks,
  map (fun c => mapped (slice xs c)) chunks = map mapped (map (slice xs) chunks).
Proof. intros. rewrite map_map. reflexivity. Qed.

(* The checksum folded chunk by chunk, each chunk continuing the previous
   chunk's accumulator. *)
Definition chunk_reduce (chunks : list (list nat)) : nat :=
  fold_left (fun acc ch => fold_left step ch acc) chunks 0.

(* -------------------------------------------------------------------------
   Variant 2: input in chunks, one mapped list (early-input-release). The
   map and the reduction walk the input slice by slice and fill one
   whole-length mapped list; the XOR pass reads that list end to end.
   ------------------------------------------------------------------------- *)

Definition early_release (chunks : list (nat * nat)) (xs : list nat) : list nat :=
  finish (chunk_reduce (map (fun c => mapped (slice xs c)) chunks))
         (concat (map (fun c => mapped (slice xs c)) chunks)).

Theorem early_release_correct : forall chunks xs,
  partitions chunks (length xs) -> early_release chunks xs = reference xs.
Proof.
  intros chunks xs Hp. rewrite <- retained_correct.
  unfold early_release, chunk_reduce, retained, reduce.
  rewrite mapped_chunks, fold_chunks, concat_mapped.
  rewrite (concat_slices xs chunks 0 Hp). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Variant 3: mapped chunks kept until their XOR (chunked-cache). The
   checksum folds chunk by chunk as above; the XOR pass reads each kept
   chunk and the outputs are concatenated in chunk order.
   ------------------------------------------------------------------------- *)

Definition chunked (chunks : list (nat * nat)) (xs : list nat) : list nat :=
  concat (map (finish (chunk_reduce (map (fun c => mapped (slice xs c)) chunks)))
              (map (fun c => mapped (slice xs c)) chunks)).

Theorem chunked_correct : forall chunks xs,
  partitions chunks (length xs) -> chunked chunks xs = reference xs.
Proof.
  intros chunks xs Hp. rewrite <- retained_correct.
  unfold chunked, chunk_reduce, retained, reduce.
  rewrite mapped_chunks, concat_finish, fold_chunks, concat_mapped.
  rewrite (concat_slices xs chunks 0 Hp). reflexivity.
Qed.

(* The two models are one function up to `concat_finish`: XORing the whole
   mapped list against the checksum and XORing each kept chunk against it
   give the same list, which is what makes the stage copy a pure move. *)
Lemma early_release_is_chunked : forall chunks xs,
  early_release chunks xs = chunked chunks xs.
Proof. intros. unfold early_release, chunked. symmetry. apply concat_finish. Qed.

(* -------------------------------------------------------------------------
   Variant 4: tiled recomputation (tiled-rematerialized). The second pass
   maps the input slice again into the tile before the XOR, rather than
   reading a kept mapped chunk. Up to `map_map` this is `chunked`: at the
   functional level, recomputing a pure map is reading what it stored.
   ------------------------------------------------------------------------- *)

Definition tiled (chunks : list (nat * nat)) (xs : list nat) : list nat :=
  concat (map (fun c => finish (chunk_reduce (map (fun c => mapped (slice xs c)) chunks))
                               (mapped (slice xs c))) chunks).

Lemma tiled_is_chunked : forall chunks xs, tiled chunks xs = chunked chunks xs.
Proof. intros. unfold tiled, chunked. rewrite map_map. reflexivity. Qed.

Theorem tiled_correct : forall chunks xs,
  partitions chunks (length xs) -> tiled chunks xs = reference xs.
Proof. intros chunks xs Hp. rewrite tiled_is_chunked. apply chunked_correct. exact Hp. Qed.

(* -------------------------------------------------------------------------
   Variant 5: fused recomputation (fused-rematerialized). No mapped list
   exists: the reduction applies the map on the fly and the XOR pass
   applies it a second time.
   ------------------------------------------------------------------------- *)

Definition fused (xs : list nat) : list nat :=
  map (fun x => Nat.lxor (emitted_map x)
                         (fold_left (fun acc x => step acc (emitted_map x)) xs 0)) xs.

Lemma fold_map_step : forall (f : nat -> nat) xs a,
  fold_left (fun acc x => step acc (f x)) xs a = fold_left step (map f xs) a.
Proof.
  intros f xs. induction xs as [| x xs IH]; intro a.
  - reflexivity.
  - cbn [fold_left map]. apply IH.
Qed.

Theorem fused_correct : forall xs, fused xs = reference xs.
Proof.
  intro xs. rewrite <- retained_correct.
  unfold fused, retained, reduce, finish, mapped.
  rewrite (fold_map_step emitted_map), map_map. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Variant 6: in place (in-place-phased). Memory is a function from index
   to value, loaded from the frame by ingress. Phase one visits the indices
   in order: each step reads element i, overwrites it with its mapped value
   and accumulates the checksum over that value. Phase two, which starts
   only after the reduction is complete, overwrites each element with its
   XOR against the final checksum. The readout reads the memory back in
   index order, as the emit instructions do.
   ------------------------------------------------------------------------- *)

Definition load (xs : list nat) : nat -> nat := fun i => nth i xs 0.

Definition store (m : nat -> nat) (i v : nat) : nat -> nat :=
  fun j => if j =? i then v else m j.

Record InPlaceState : Type := { mem : nat -> nat; acc : nat }.

Definition map_sum_step (st : InPlaceState) (i : nat) : InPlaceState :=
  let v := emitted_map (mem st i) in
  {| mem := store (mem st) i v; acc := step (acc st) v |}.

Definition xor_step (c : nat) (m : nat -> nat) (i : nat) : nat -> nat :=
  store m i (Nat.lxor (m i) c).

Definition entry (xs : list nat) : InPlaceState := {| mem := load xs; acc := 0 |}.

Definition phase1_upto (xs : list nat) (k : nat) : InPlaceState :=
  fold_left map_sum_step (seq 0 k) (entry xs).

Definition phase1 (xs : list nat) : InPlaceState := phase1_upto xs (length xs).

Definition in_place (xs : list nat) : list nat :=
  map (fold_left (xor_step (acc (phase1 xs))) (seq 0 (length xs)) (mem (phase1 xs)))
      (seq 0 (length xs)).

Lemma map_sum_step_mem : forall (st : InPlaceState) i j,
  mem (map_sum_step st i) j = if j =? i then emitted_map (mem st i) else mem st j.
Proof. reflexivity. Qed.

Lemma map_sum_step_acc : forall (st : InPlaceState) i,
  acc (map_sum_step st i) = step (acc st) (emitted_map (mem st i)).
Proof. reflexivity. Qed.

Lemma xor_step_at : forall c m i j,
  xor_step c m i j = if j =? i then Nat.lxor (m i) c else m j.
Proof. reflexivity. Qed.

Lemma fold_left_single : forall (A B : Type) (f : A -> B -> A) (a : A) (b : B),
  fold_left f [b] a = f a b.
Proof. reflexivity. Qed.

Lemma phase1_upto_S : forall xs k, phase1_upto xs (S k) = map_sum_step (phase1_upto xs k) k.
Proof. intros. unfold phase1_upto. rewrite seq_S, fold_left_app. reflexivity. Qed.

(* After k steps, indices below k hold their mapped value and the rest are
   untouched input: element i is overwritten only after it is read, and
   later steps read distinct indices. *)
Lemma phase1_mem : forall xs k j,
  mem (phase1_upto xs k) j = if j <? k then emitted_map (nth j xs 0) else nth j xs 0.
Proof.
  intros xs k. induction k as [| k IH]; intro j.
  - reflexivity.
  - rewrite phase1_upto_S, map_sum_step_mem, !IH.
    destruct (Nat.eqb_spec j k) as [-> | Hne].
    + destruct (Nat.ltb_spec0 k k) as [Hkk | _]; [exfalso; lia |].
      destruct (Nat.ltb_spec0 k (S k)) as [_ | Hks]; [reflexivity | exfalso; lia].
    + destruct (Nat.ltb_spec0 j k) as [Hjk | Hjk];
        destruct (Nat.ltb_spec0 j (S k)) as [Hjs | Hjs];
        try reflexivity; exfalso; lia.
Qed.

(* The accumulator after k steps is the fold over the mapped values read
   so far, in index order. *)
Lemma phase1_acc : forall xs k,
  acc (phase1_upto xs k) = fold_left step (map (fun j => emitted_map (nth j xs 0)) (seq 0 k)) 0.
Proof.
  intros xs k. induction k as [| k IH].
  - reflexivity.
  - rewrite phase1_upto_S, map_sum_step_acc, IH, phase1_mem, seq_S, map_app, fold_left_app.
    destruct (Nat.ltb_spec0 k k) as [Hkk | _]; [exfalso; lia | reflexivity].
Qed.

(* The XOR pass touches each index below k exactly once, against the fixed
   checksum, and nothing else. *)
Lemma phase2_mem : forall c (m : nat -> nat) k j,
  fold_left (xor_step c) (seq 0 k) m j = if j <? k then Nat.lxor (m j) c else m j.
Proof.
  intros c m k. induction k as [| k IH]; intro j.
  - reflexivity.
  - rewrite seq_S, fold_left_app, fold_left_single, xor_step_at, !IH, Nat.add_0_l.
    destruct (Nat.eqb_spec j k) as [-> | Hne].
    + destruct (Nat.ltb_spec0 k k) as [Hkk | _]; [exfalso; lia |].
      destruct (Nat.ltb_spec0 k (S k)) as [_ | Hks]; [reflexivity | exfalso; lia].
    + destruct (Nat.ltb_spec0 j k) as [Hjk | Hjk];
        destruct (Nat.ltb_spec0 j (S k)) as [Hjs | Hjs];
        try reflexivity; exfalso; lia.
Qed.

(* Reading a list back through its indices in order is the list. *)
Lemma map_over_indices : forall (h : nat -> nat) (xs : list nat),
  map (fun j => h (nth j xs 0)) (seq 0 (length xs)) = map h xs.
Proof.
  intros h xs. induction xs as [| x xs IH].
  - reflexivity.
  - cbn [length seq map nth]. f_equal.
    rewrite <- seq_shift, map_map. cbn [nth]. apply IH.
Qed.

Theorem in_place_correct : forall xs, in_place xs = reference xs.
Proof.
  intro xs. rewrite <- retained_correct.
  unfold in_place, phase1, retained, reduce, finish, mapped.
  rewrite phase1_acc, map_over_indices, map_map.
  rewrite <- (map_over_indices
                (fun x => Nat.lxor (emitted_map x) (fold_left step (map emitted_map xs) 0)) xs).
  apply map_ext_in. intros j Hj. apply in_seq in Hj.
  rewrite phase2_mem, phase1_mem.
  destruct (Nat.ltb_spec0 j (length xs)) as [_ | H]; [reflexivity | exfalso; lia].
Qed.

(* -------------------------------------------------------------------------
   The generator's chunk list, and that it partitions the interval. `tiles`
   is `range(0, length, tile)` with `min(tile, length - start)` counts,
   written with a fuel argument that the length itself bounds. The
   generator clamps the tile to the length first; `generator_chunks_clamp`
   shows that changes no chunk, so `generator_chunks (min tile len) len`
   is the Python list and every theorem below about `generator_chunks tile
   len` is a theorem about it.
   ------------------------------------------------------------------------- *)

Fixpoint tiles (fuel from len tile : nat) : list (nat * nat) :=
  match fuel with
  | 0 => []
  | S fuel' => if len <=? from then []
               else (from, Nat.min tile (len - from)) :: tiles fuel' (from + tile) len tile
  end.

Definition generator_chunks (tile len : nat) : list (nat * nat) := tiles len 0 len tile.

Lemma tiles_exhausted : forall fuel from len tile, len <= from -> tiles fuel from len tile = [].
Proof.
  intros fuel from len tile H. destruct fuel as [| fuel]; [reflexivity |].
  cbn [tiles]. apply Nat.leb_le in H. rewrite H. reflexivity.
Qed.

Lemma tiles_cover : forall fuel from len tile,
  1 <= tile -> from <= len -> len - from <= fuel -> covers from (tiles fuel from len tile) len.
Proof.
  induction fuel as [| fuel IH]; intros from len tile Ht Hf Hfuel.
  - cbn. lia.
  - cbn [tiles]. destruct (Nat.leb_spec0 len from) as [Hle | Hgt].
    + cbn. lia.
    + cbn [covers fst snd]. split; [reflexivity |].
      destruct (Nat.min_spec tile (len - from)) as [[Hlt Hmin] | [Hle Hmin]]; rewrite Hmin.
      * apply IH; lia.
      * rewrite tiles_exhausted by lia. cbn. lia.
Qed.

Theorem generator_chunks_partition : forall tile len,
  1 <= tile -> partitions (generator_chunks tile len) len.
Proof. intros tile len Ht. unfold partitions, generator_chunks. apply tiles_cover; lia. Qed.

(* A tile wider than the frame yields the one chunk the whole frame is,
   clamped or not. *)
Lemma generator_chunks_clamp : forall tile len,
  1 <= tile -> generator_chunks (Nat.min tile len) len = generator_chunks tile len.
Proof.
  intros tile len Ht. unfold generator_chunks.
  destruct (Nat.min_spec tile len) as [[_ Hmin] | [Hle Hmin]]; rewrite Hmin; [reflexivity |].
  destruct len as [| len]; [reflexivity |].
  cbn [tiles Nat.leb]. rewrite !tiles_exhausted by lia. rewrite !Nat.min_r by lia. reflexivity.
Qed.

Corollary generator_early_release_correct : forall tile xs,
  1 <= tile -> early_release (generator_chunks tile (length xs)) xs = reference xs.
Proof. intros. apply early_release_correct. apply generator_chunks_partition. assumption. Qed.

Corollary generator_chunked_correct : forall tile xs,
  1 <= tile -> chunked (generator_chunks tile (length xs)) xs = reference xs.
Proof. intros. apply chunked_correct. apply generator_chunks_partition. assumption. Qed.

Corollary generator_tiled_correct : forall tile xs,
  1 <= tile -> tiled (generator_chunks tile (length xs)) xs = reference xs.
Proof. intros. apply tiled_correct. apply generator_chunks_partition. assumption. Qed.

(* -------------------------------------------------------------------------
   The hypothesis is sufficient and not necessary. A slice truncates at the
   end of the list, so one chunk reaching past the end reads the whole list
   and returns the reference without partitioning the interval. The chunk
   theorems therefore do not characterise the chunk lists that agree; they
   cover the ones the generator emits.
   ------------------------------------------------------------------------- *)

Lemma single_chunk_agrees : forall n xs, length xs <= n -> chunked [(0, n)] xs = reference xs.
Proof.
  intros n xs Hn. rewrite <- retained_correct.
  unfold chunked, chunk_reduce, retained, reduce, slice.
  cbn [map concat fold_left fst snd skipn].
  rewrite firstn_all2 by exact Hn. rewrite app_nil_r. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Bytes in, bytes out. The map is a residue mod 256 and XOR of two values
   below a power of two stays below it, read off the bits.
   ------------------------------------------------------------------------- *)

Lemma bit_high_false : forall n a m, a < 2 ^ n -> n <= m -> Nat.testbit a m = false.
Proof.
  intros n a m Ha Hm. rewrite <- (Nat.mod_small a (2 ^ n) Ha).
  apply Nat.mod_pow2_bits_high. exact Hm.
Qed.

Lemma lxor_below_pow2 : forall n a b, a < 2 ^ n -> b < 2 ^ n -> Nat.lxor a b < 2 ^ n.
Proof.
  intros n a b Ha Hb.
  assert (E : Nat.lxor a b = Nat.lxor a b mod 2 ^ n).
  { apply Nat.bits_inj. intro m.
    destruct (Nat.le_gt_cases n m) as [Hnm | Hmn].
    - rewrite Nat.mod_pow2_bits_high by exact Hnm. rewrite Nat.lxor_spec.
      rewrite (bit_high_false n a m Ha Hnm), (bit_high_false n b m Hb Hnm). reflexivity.
    - rewrite Nat.mod_pow2_bits_low by exact Hmn. reflexivity. }
  rewrite E. apply Nat.mod_upper_bound. apply Nat.pow_nonzero. discriminate.
Qed.

Lemma lxor_byte : forall a b, is_byte a -> is_byte b -> is_byte (Nat.lxor a b).
Proof. intros a b. unfold is_byte. change 256 with (2 ^ 8). apply lxor_below_pow2. Qed.

Lemma map_byte_byte : forall b, is_byte (map_byte b).
Proof. intro b. unfold is_byte, map_byte. apply Nat.mod_upper_bound. discriminate. Qed.

Theorem reference_bytes : forall xs, Forall is_byte (reference xs).
Proof.
  intro xs. unfold reference. apply Forall_forall. intros y Hy.
  apply in_map_iff in Hy. destruct Hy as [t [<- Ht]].
  apply in_map_iff in Ht. destruct Ht as [x [<- _]].
  apply lxor_byte; [apply map_byte_byte |].
  unfold is_byte. apply Nat.mod_upper_bound. discriminate.
Qed.

(* -------------------------------------------------------------------------
   Non-vacuity. A concrete frame, its outputs by computation on every
   model, the record witness, and three wrong variants refuted on the same
   frame by value: the XOR pass replaced by a copy, a chunk list that drops
   the last two indices, and one that repeats the first two in their place.
   The two chunk lists fail `partitions`; a third, one chunk reaching past
   the end, fails it too and still returns the reference, which is the
   concrete form of the hypothesis being sufficient and not necessary.
   ------------------------------------------------------------------------- *)

Definition demo_frame : list nat := [0; 1; 255; 16].

Definition demo_output : list nat := [53; 48; 202; 5].

Definition witness_InPlaceState : InPlaceState := entry demo_frame.

(*| discharges: R-05-165, R-05-166 |*)
Example demo_reference : reference demo_frame = demo_output.
Proof. vm_compute. reflexivity. Qed.

(*| discharges: R-05-165, R-05-166 |*)
Example demo_variants_agree :
  retained demo_frame = demo_output
  /\ early_release (generator_chunks 3 (length demo_frame)) demo_frame = demo_output
  /\ chunked (generator_chunks 3 (length demo_frame)) demo_frame = demo_output
  /\ chunked (generator_chunks 8 (length demo_frame)) demo_frame = demo_output
  /\ tiled (generator_chunks 3 (length demo_frame)) demo_frame = demo_output
  /\ fused demo_frame = demo_output
  /\ in_place demo_frame = demo_output.
Proof. vm_compute. repeat split. Qed.

Example generator_chunks_of_the_demo :
  generator_chunks 3 (length demo_frame) = [(0, 3); (3, 1)].
Proof. vm_compute. reflexivity. Qed.

(* The XOR pass replaced by a copy of the mapped value: the reference's
   length, different values. *)
Definition copy_instead_of_xor (xs : list nat) : list nat := mapped xs.

(*| discharges: R-05-165, R-05-166 |*)
Example copy_variant_refuted : copy_instead_of_xor demo_frame <> reference demo_frame.
Proof. vm_compute. intro H. discriminate H. Qed.

Example copy_variant_same_length :
  length (copy_instead_of_xor demo_frame) = length (reference demo_frame).
Proof. vm_compute. reflexivity. Qed.

(* The last two indices dropped. The output is short, and the prefix it
   shares with the reference already differs, because the dropped values
   are missing from the checksum every element is XORed against. *)
Definition missing_chunk : list (nat * nat) := [(0, 2)].

(*| discharges: R-05-165, R-05-166 |*)
Example missing_chunk_refuted : chunked missing_chunk demo_frame <> reference demo_frame.
Proof. vm_compute. intro H. discriminate H. Qed.

(*| discharges: R-05-165, R-05-166 |*)
Example missing_chunk_prefix_refuted :
  chunked missing_chunk demo_frame
  <> firstn (length (chunked missing_chunk demo_frame)) (reference demo_frame).
Proof. vm_compute. intro H. discriminate H. Qed.

(* The first two indices twice, in place of the last two: the reference's
   length, different values. *)
Definition duplicate_chunk : list (nat * nat) := [(0, 2); (0, 2)].

(*| discharges: R-05-165, R-05-166 |*)
Example duplicate_chunk_refuted : chunked duplicate_chunk demo_frame <> reference demo_frame.
Proof. vm_compute. intro H. discriminate H. Qed.

Example duplicate_chunk_same_length :
  length (chunked duplicate_chunk demo_frame) = length (reference demo_frame).
Proof. vm_compute. reflexivity. Qed.

Example missing_chunk_is_no_partition : ~ partitions missing_chunk (length demo_frame).
Proof. cbn. intros [_ H]. discriminate H. Qed.

Example duplicate_chunk_is_no_partition : ~ partitions duplicate_chunk (length demo_frame).
Proof. cbn. intros [_ [H _]]. discriminate H. Qed.

(* One chunk reaching past the end: no partition, and the reference. *)
Definition overshoot_chunk : list (nat * nat) := [(0, 10)].

Example overshoot_chunk_is_no_partition : ~ partitions overshoot_chunk (length demo_frame).
Proof. cbn. intros [_ H]. discriminate H. Qed.

Theorem partitions_not_necessary :
  exists chunks, ~ partitions chunks (length demo_frame)
                 /\ chunked chunks demo_frame = reference demo_frame.
Proof.
  exists overshoot_chunk. split.
  - exact overshoot_chunk_is_no_partition.
  - apply single_chunk_agrees. cbn. lia.
Qed.

(* -------------------------------------------------------------------------
   The R-05-163 gate: every constant closed under the global context, which
   `run.py proofs` decides through its own inventory of the file. The
   lines below are the theorems and named examples, for a reader.
   ------------------------------------------------------------------------- *)

Print Assumptions emitted_map_is_map_byte.
Print Assumptions emitted_map_checked_over_every_byte.
Print Assumptions reduce_is_checksum.
Print Assumptions retained_correct.
Print Assumptions early_release_correct.
Print Assumptions chunked_correct.
Print Assumptions early_release_is_chunked.
Print Assumptions tiled_is_chunked.
Print Assumptions tiled_correct.
Print Assumptions fused_correct.
Print Assumptions in_place_correct.
Print Assumptions generator_chunks_partition.
Print Assumptions generator_chunks_clamp.
Print Assumptions generator_early_release_correct.
Print Assumptions generator_chunked_correct.
Print Assumptions generator_tiled_correct.
Print Assumptions single_chunk_agrees.
Print Assumptions reference_bytes.
Print Assumptions demo_reference.
Print Assumptions demo_variants_agree.
Print Assumptions generator_chunks_of_the_demo.
Print Assumptions copy_variant_refuted.
Print Assumptions copy_variant_same_length.
Print Assumptions missing_chunk_refuted.
Print Assumptions missing_chunk_prefix_refuted.
Print Assumptions duplicate_chunk_refuted.
Print Assumptions duplicate_chunk_same_length.
Print Assumptions missing_chunk_is_no_partition.
Print Assumptions duplicate_chunk_is_no_partition.
Print Assumptions overshoot_chunk_is_no_partition.
Print Assumptions partitions_not_necessary.
