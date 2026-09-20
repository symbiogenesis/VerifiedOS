(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ExecutableIndex.v: M5.3d's executable L1 index, and only its index half.

   What this is. The explicitly admitted plain copy-on-write B+ tree that
   R-10-004 names beside the incumbent B^epsilon buffered-update refinement,
   written as an executable structure over a bounded arena: key and separator
   routing, lookup, insert with replacement, leaf and internal split,
   copy-on-write path copying, and a structural admission the writer
   re-decides on what it has just published. Its correspondence is stated
   against the ordered association list JournalIndex.v's L1 Index already is,
   and against that file's `look`, `ins` and `sorted` rather than against a
   second statement of the same map. R-10-002 makes L1 one of four verified layers
   on one prover and its acceptance clause is that each layer's proof is a
   Coq artifact; this file is that prover throughout and carries no foreign
   proof anchor.

   Why the fallback is implemented first, which is a sequencing judgment and
   not a selection. Q22f's bounded comparison retains B^epsilon provisionally
   and admits no target composition, and M5.3's executable-index obligation
   admits either that index or this explicitly admitted fallback. The two
   arms share everything below: the geometry, the arena and its refusal, the
   separator routing, the splits, the copy-on-write discipline and the
   structural admission. What the buffered arm adds is a per-node message log
   read before the entries beneath it and a flush that drains it, which
   JournalIndex.v already states as `blook`, `plain_look` and `flush`. That
   is a difference to add to this body, not a rewrite of it, so writing the
   fallback first buys the shared half now and costs the buffered arm
   nothing. Nothing here selects an index: R-10-004's selection predicate is
   a measurement under the actual geometry, batching, acknowledgement policy,
   authenticated block-service cost and NAND amplification, and no such
   measurement is taken below.

   What this file is the index half of. M5.3d owns the executable index,
   persistent backing and reopen, byte authentication, executable crypto, the
   recovery join and the two-instance target run. **Only the first is here.**
   No byte of this file reaches a device, a disk image, a reopen path, an
   authenticator, a cipher or an emulator; R-10-002a's complete authenticated
   prefix redo is StorageRecovery.v's and its byte decoder is still owed;
   nothing below is compiled, lowered or run, and R-10-009's whole stack
   staying outside the trust base is a property of the composition rather
   than of this statement. M5.1's sorted association list is the oracle here
   and this implementation is not: where the two disagree the association
   list is right, and the theorems below are the claim that they do not.

   The arena, and what a refusal is. A node lives at an index into a list
   whose declared capacity is a field of the Geometry record; `alloc` appends
   at the next address and refuses when the declared capacity is spent, so an
   exhausted arena is `None` and never a reused or wrapped address. A write
   appends and rewrites nothing, which is R-10-010's copy-on-write read as an
   arena discipline and is the single fact every retained-snapshot statement
   below rests on.

   Structural admission, in two layers, and where it actually runs. `spans`
   refuses an address outside the arena, a reference its walk bound does not
   reach, and a cycle; the cycle is refused because a cycle admits no finite
   walk and the walk is structural in the bound its caller passes, which is
   JournalIndex.v's `bounded_tree` argument over this arena. `admitted` adds
   the occupancy ceiling and the key order: each node holds no more entries
   and no more children than the declared fanout and carries exactly one
   separator fewer than its children, each leaf is sorted and inside its
   declared range, and each child is admitted between the separators that
   bound it. Both are booleans, so a witness is decided by conversion.

   **No operation runs either layer on its input before trusting it.**
   `lookup`, `flatten`, `insert`, `publish_leaf` and `publish_branch` call
   neither `spans` nor `admitted`; what bounds each of them is the fuel its
   own caller passes, which is why a walk that runs out of it answers `None`
   or `nil` rather than diverging, and why a cycle costs a bounded walk and
   not termination. The two admission calls in this file are both *after* a
   write, on what was just published: `insert_checked` re-decides
   `admitted_grown`, and `insert_root` re-decides `admitted` on a new root it
   allocated. Where a theorem below needs an admitted input it takes that as a
   hypothesis, and a composition that wants the check ahead of a read has to
   run it, since nothing here does.

   The fail-closed discipline, and the obligations it does not discharge.
   `insert_checked` re-decides `admitted` on what it published and refuses a
   result that does not decide true, so an admitted tree is followed by an
   admitted tree or by a refusal and never by a tree nothing checked. **That
   the check never refuses a well formed insert is a separate obligation and
   is owed at M5.3d**, stated here as owed and asserted nowhere as an
   admit, an axiom or a hypothesis: what is proved is that a checked result
   is admitted, and what is computed is that the check passes on the
   witnesses at the end of this file. Balance splits in two against this
   check. Its occupancy half is inside it: `node_fits` is a conjunct of
   `admitted`, `node_fits_everywhere` names that conjunct on its own down the
   walk, and `an_admitted_tree_fits_everywhere` is the reading between them.
   Its equal-leaf-depth half, which is the B+ property, is outside it:
   `admitted` does not decide it, so the check neither enforces nor repairs
   it, and the skew witness at the end of this file is admitted while one of
   its leaves sits a level above the others. What carries that half is
   `at_depth` and `leaves_share_one_depth` beside their two preservation
   theorems, which take equal leaf depth of the input as a hypothesis and
   return it of the output, at the same depth or, where the root split, at
   exactly one more.

   The read path's one asymmetry, named rather than repaired. `lookup`
   answers `None` for an address outside the arena, for a walk that runs out
   of bound and for a cycle, which is the same answer it gives for a key that
   is simply absent, so a reader cannot tell a structural refusal from a
   miss. The write path does distinguish them, since `insert` answers `None`
   only on a refusal. Making the read path distinguish them is a change to
   `lookup`'s result type and to every statement over it, and it is not made
   here; a composition that needs the distinction runs `spans` or `admitted`
   itself, which is the same call this file's theorems take as a hypothesis.

   Readings of the register this file takes, each a reviewable judgment.

   1. A separator is the first key of the child to its right, so a child
      holds the keys at or above its own left separator and strictly below
      the next one. R-10-003 fixes no routing convention, so this is chosen
      and stated rather than found; `route` and the range chain are two
      readings of the one convention and no third reading appears.
   2. Every walk below takes its bound as an argument rather than reading one
      from the geometry, and the tree's height is not assumed to stay put:
      the height a walk needs comes back with a result that split the root.
      Geometry's `depth` is the declared ceiling the composition will fix and
      no definition below reads it, so relating a call's bound to that
      declaration is owed at M5.3d with the rest of the geometry. R-10-003
      fixes neither quantity.
   3. A logical map is a list, so two of them are compared as lists and every
      equality below is an equality of lists or of a decidable boolean.
      `flatten` answers `nil` at a node it refuses, which conflates a refused
      subtree with an empty one, and that is why every statement below is
      gated on `spans` or on `admitted` and none is read off `flatten` alone.
   4. A leaf's entries are JournalIndex.v's Index and a leaf's insertion is
      that file's `ins`, so replacement, ordering and the two S12 half
      theorems are reused rather than restated. R-10-005's snapshot version
      inside the key is L2's and no key here carries one.
   5. R-10-003's "generic over key type, verified once" is a
      parameterization: every definition and every theorem below takes the
      KeyAlgebra record, no instance appears in any statement, and the demo
      instance at the end is a witness and not a second index.

   What is deliberately not authored, and where each is owed. A register gap
   is reported rather than closed, and an absent operation is named rather
   than implied.

   a. Deletion, merge and rebalancing on removal. R-10-003 states no minimum
      occupancy and the executable-index obligation names insertion,
      replacement and split, so `node_fits` states a ceiling and no floor and
      no removal path exists below. Owed at R-10-003, beside JournalIndex.v's
      gap b and gap g, which this file inherits unchanged.
   b. The buffered arm's multilevel flush, its message-order and duplicate
      precedence obligations, and the invariant joining buffered updates with
      recovery. Owed at R-10-004, and the comparison that decides between the
      arms is Q22f's to re-run under the actual composition.
   c. Every cost. No worst-case query or flush work, no write amplification,
      no barrier count and no WCET is stated or implied; `fan`, `depth` and
      `arena_cap` are declared magnitudes and not measured ones. Owed at
      R-10-004 and at the composition's own timing admission.
   d. Persistence. R-10-036 commits a checkpoint as a single L0 transaction
      and no transaction, journal record or commit appears below; the join
      between this index and JournalIndex.v's L0 is M5.3d's and is open.
   e. Concurrency. One writer, no reader visibility rule, no barrier.
   f. Equal leaf depth inside the check rather than beside it. `insert_root`
      re-decides `admitted`, which does not decide equal leaf depth, so the
      operation neither enforces nor repairs it; what this file proves is
      that an input whose leaves share a depth yields an output whose leaves
      share one. Adding `leaves_share_one_depth` to the published gate is a
      change to the operation and to every statement over its result, and is
      owed at M5.3d with the geometry if the composition wants it.

   Non-vacuity (R-05-165, R-05-166). Every obligation is stated of an
   arbitrary key algebra, geometry, arena, walk bound, subtree, key and
   query, proved there, and computed on a witness family at the end: an
   admitted three-node tree whose leaves share one depth, two inserts that
   split, one of them splitting a leaf and an internal node and publishing a
   new root and the other routing past every separator, one replacement that
   splits nothing, the same three read again for equal leaf depth, a skewed
   tree that is admitted and occupancy-fitting while its leaves share no
   depth together with the insert that does not repair it, and the four
   refusals, which are an arena whose declared capacity is spent, an address
   outside the arena, a reference past the walk bound, and a cycle among
   whole addressable nodes. The last is the case block completeness alone
   cannot decide, which is what the bounded walk is for. Nothing below is
   admitted, axiomatized or parameterized at top level: every composition
   magnitude is a field of the Geometry record. The Print Assumptions block
   at the end names the definitions and theorems this file exports and not
   every constant it holds; what enumerates every constant, local lemmas
   included, and queries each one's assumption set is the proof gate, and
   `Closed under the global context` is that emptiness checked there.

   Requires. JournalIndex.v, for the KeyAlgebra record and its five laws, the
   L1 Index, `look`, `ins`, `sorted` and the list helpers; and the Rocq
   standard library's List, Bool, Arith and Lia, on the precedent
   StorageRecovery.v sets for a sibling of that file.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-10-002 R-10-002a R-10-003 R-10-004
      R-10-005 R-10-009 R-10-010 R-10-036
   SHA256: d10a3eed5506c743e2423fa9ba4a1f79321f2addc6847fc8d4043849470ff00b
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Bool Arith Lia.
Require Import JournalIndex.
Import ListNotations.

(* -------------------------------------------------------------------------
   List helpers over JournalIndex's `take` and `drop`, which this file reuses
   rather than restating, and the two facts about `all_of` that the arena
   walks below need and that file does not carry.
   ------------------------------------------------------------------------- *)

Lemma all_of_drop :
  forall (A : Type) (p : A -> bool) (n : nat) (l : list A),
    all_of p l = true -> all_of p (drop n l) = true.
Proof.
  intros A p n. induction n as [ | m IH ]; intros l H.
  - exact H.
  - destruct l as [ | x r ]; [ reflexivity | ].
    simpl in H. apply andb_true_iff in H as [ _ Hr ]. simpl. exact (IH r Hr).
Qed.

Lemma take_length_le :
  forall (A : Type) (n : nat) (l : list A), length (take n l) <= n.
Proof.
  intros A n. induction n as [ | m IH ]; intros l; simpl.
  - apply Nat.le_0_l.
  - destruct l as [ | x r ]; simpl; [ apply Nat.le_0_l | ].
    apply le_n_S. exact (IH r).
Qed.

Lemma drop_length :
  forall (A : Type) (n : nat) (l : list A), length (drop n l) = length l - n.
Proof.
  intros A n. induction n as [ | m IH ]; intros l.
  - simpl. rewrite Nat.sub_0_r. reflexivity.
  - destruct l as [ | x r ]; simpl; [ reflexivity | exact (IH r) ].
Qed.

Lemma take_app_exact :
  forall (A : Type) (l r : list A) (n : nat), length l = n -> take n (l ++ r) = l.
Proof.
  intros A l. induction l as [ | x s IH ]; intros r n H.
  - simpl in H. rewrite <- H. reflexivity.
  - destruct n as [ | m ]; [ discriminate H | ].
    simpl in H. injection H as H. simpl. rewrite (IH r m H). reflexivity.
Qed.

Lemma drop_after :
  forall (A : Type) (l r : list A) (x : A) (n : nat),
    length l = n -> drop (S n) (l ++ x :: r) = r.
Proof.
  intros A l. induction l as [ | y s IH ]; intros r x n H.
  - simpl in H. rewrite <- H. reflexivity.
  - destruct n as [ | m ]; [ discriminate H | ].
    simpl in H. injection H as H. simpl. exact (IH r x m H).
Qed.

(* Halving, written out rather than taken from the library, so that the two
   facts the split needs are proved of the same definition the code runs. The
   numerals are the recursion's own base cases and no composition chooses
   them. *)
Fixpoint halve (n : nat) : nat :=
  match n with
  | 0 => 0
  | S 0 => 0
  | S (S m) => S (halve m)
  end.

Lemma halve_bounds : forall n : nat, halve n <= n /\ halve (S n) <= n.
Proof.
  intros n. induction n as [ | m [ IH1 IH2 ] ].
  - split; reflexivity.
  - split; [ lia | ]. simpl. apply le_n_S. exact IH1.
Qed.

Lemma halve_le : forall n : nat, halve n <= n.
Proof. intros n. exact (proj1 (halve_bounds n)). Qed.

Lemma halve_lt : forall n : nat, 0 < n -> halve n < n.
Proof.
  intros n H. destruct n as [ | m ]; [ lia | ].
  pose proof (proj2 (halve_bounds m)) as H2. lia.
Qed.

Lemma halve_pos : forall n : nat, 1 < n -> 0 < halve n.
Proof.
  intros n H. destruct n as [ | a ]; [ lia | ].
  destruct a as [ | b ]; [ lia | ]. simpl. lia.
Qed.

(* =========================================================================
   The geometry: every magnitude the register leaves to composition, as a
   field rather than as a literal, on JournalIndex.v's own convention.
   ========================================================================= *)

Record Geometry : Type := {
  (* The arena's declared node capacity. An allocation past it is a refusal
     and never a wraparound, which is what `alloc` below decides. *)
  arena_cap : nat;

  (* The maximum entries a leaf holds and the maximum children an internal
     node names. R-10-003 fixes no node capacity, so this is a field; the
     register states no minimum, so none is checked (JournalIndex.v gap b). *)
  fan : nat;

  (* The declared height ceiling the composition will fix. Every walk below
     is structural in the bound its caller passes rather than in this field,
     which no definition here reads; what that bound buys is the refusal of
     an over-deep or cyclic reference, and tying a call's bound to this
     declaration is owed at M5.3d. *)
  depth : nat
}.

(* The two floors a split needs: a fanout below two cannot be halved into two
   non-empty nodes, and an arena of no blocks holds no root. *)
Definition geometry_ok (g : Geometry) : bool :=
  andb (Nat.leb 2 (fan g)) (Nat.leb 1 (arena_cap g)).

(* =========================================================================
   The node and the arena.

   A node is a leaf when it names no child: its entries are then the ordered
   association list JournalIndex.v's L1 Index already is, so a leaf's logical
   content is that file's own type and a leaf insertion is that file's own
   `ins`. An internal node carries separators and children and no entries.
   ========================================================================= *)

Record ENode (ka : KeyAlgebra) : Type := {
  en_entries : Index ka;
  en_seps : list (Key ka);
  en_kids : list nat
}.

Arguments en_entries {ka} _.
Arguments en_seps {ka} _.
Arguments en_kids {ka} _.

Definition Arena (ka : KeyAlgebra) : Type := list (ENode ka).

Definition leaf_of (ka : KeyAlgebra) (ix : Index ka) : ENode ka :=
  {| en_entries := ix; en_seps := nil; en_kids := nil |}.

Definition branch_of (ka : KeyAlgebra) (ss : list (Key ka)) (cs : list nat)
  : ENode ka :=
  {| en_entries := nil; en_seps := ss; en_kids := cs |}.

(* R-10-010's copy-on-write allocation, read as an arena discipline: a node is
   appended at a fresh address and no address already handed out is rewritten,
   so a retained root keeps every node it reaches. Exhaustion is a refusal. *)
Definition alloc (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                 (nd : ENode ka) : option (prod nat (Arena ka)) :=
  if Nat.ltb (length ar) (arena_cap g)
  then Some (pair (length ar) (app ar (cons nd nil)))
  else None.

(* =========================================================================
   Keys, bounds and routing.
   ========================================================================= *)

Definition key_lt (ka : KeyAlgebra) (a b : Key ka) : bool :=
  andb (key_leb ka a b) (negb (key_eqb ka a b)).

Definition Bound (ka : KeyAlgebra) : Type := option (Key ka).

Definition above (ka : KeyAlgebra) (lo : Bound ka) (k : Key ka) : bool :=
  match lo with None => true | Some l => key_leb ka l k end.

Definition below (ka : KeyAlgebra) (hi : Bound ka) (k : Key ka) : bool :=
  match hi with None => true | Some h => key_lt ka k h end.

Definition within (ka : KeyAlgebra) (lo hi : Bound ka) (k : Key ka) : bool :=
  andb (above ka lo k) (below ka hi k).

Definition entries_within (ka : KeyAlgebra) (lo hi : Bound ka)
                          (ix : Index ka) : bool :=
  all_of (fun e => within ka lo hi (fst e)) ix.

Definition keys_below (ka : KeyAlgebra) (k : Key ka) (ix : Index ka) : bool :=
  all_of (fun e => key_lt ka (fst e) k) ix.

Definition keys_above (ka : KeyAlgebra) (k : Key ka) (ix : Index ka) : bool :=
  all_of (fun e => key_lt ka k (fst e)) ix.

(* Separator routing: a child at index i holds the keys at or above its own
   left separator and strictly below the next one, so the walk steps right
   while the separator is at or below the query. *)
Fixpoint route (ka : KeyAlgebra) (k : Key ka) (ss : list (Key ka)) : nat :=
  match ss with
  | nil => 0
  | cons s rest => if key_leb ka s k then S (route ka k rest) else 0
  end.

(* =========================================================================
   Structural admission, in two layers.

   `spans` is the weaker layer: an address outside the arena, a reference its
   walk bound does not reach, and a cycle are each refused, the cycle because
   a cycle has no finite walk and the walk below is structural in that bound.
   It mirrors JournalIndex.v's `bounded_tree` over this arena. No operation
   below calls it on its input; it is what the theorems take as a hypothesis,
   what the writer re-decides through `admitted` on what it published, and
   what the witnesses decide by conversion.
   ========================================================================= *)

Fixpoint spans (ka : KeyAlgebra) (ar : Arena ka) (fuel b : nat) : bool :=
  match nth_error ar b with
  | None => false
  | Some nd =>
      match en_kids nd with
      | nil => true
      | cons _ _ =>
          match fuel with
          | 0 => false
          | S f => all_of (spans ka ar f) (en_kids nd)
          end
      end
  end.

(* The occupancy shape R-10-003 leaves to composition: a ceiling and no
   floor, one separator fewer than children, and no node that is both. *)
Definition node_fits (ka : KeyAlgebra) (g : Geometry) (nd : ENode ka) : bool :=
  match en_kids nd with
  | nil => andb (Nat.leb (length (en_entries nd)) (fan g))
                (Nat.eqb (length (en_seps nd)) 0)
  | cons _ _ =>
      andb (Nat.leb (length (en_kids nd)) (fan g))
      (andb (Nat.eqb (length (en_kids nd)) (S (length (en_seps nd))))
            (Nat.eqb (length (en_entries nd)) 0))
  end.

(* The separators of one node, read as the chain of bounds they cut the
   node's range into: each is inside the node's own range and no earlier one
   is above a later one. *)
Fixpoint rising (ka : KeyAlgebra) (lo : Bound ka) (ss : list (Key ka))
                (hi : Bound ka) : bool :=
  match ss with
  | nil => true
  | cons s rest => andb (within ka lo hi s) (rising ka (Some s) rest hi)
  end.

(* The children against that same chain: child i is admitted between
   separator i and separator i+1, the first between `lo` and the first
   separator and the last between the last separator and `hi`. A child count
   that is not one more than the separator count is refused here. *)
Fixpoint chain (ka : KeyAlgebra)
               (rec : Bound ka -> Bound ka -> nat -> bool)
               (lo : Bound ka) (ss : list (Key ka)) (cs : list nat)
               (hi : Bound ka) : bool :=
  match ss, cs with
  | nil, cons c nil => rec lo hi c
  | cons s st, cons c ct =>
      andb (rec lo (Some s) c) (chain ka rec (Some s) st ct hi)
  | _, _ => false
  end.

(* The full admission predicate: `spans`'s three refusals, the occupancy
   ceiling, and the key order this index is an index for. *)
Fixpoint admitted (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                  (fuel : nat) (lo hi : Bound ka) (b : nat) : bool :=
  match nth_error ar b with
  | None => false
  | Some nd =>
      andb (node_fits ka g nd)
        (match en_kids nd with
         | nil => andb (sorted ka (en_entries nd))
                       (entries_within ka lo hi (en_entries nd))
         | cons _ _ =>
             match fuel with
             | 0 => false
             | S f =>
                 andb (rising ka lo (en_seps nd) hi)
                      (chain ka (admitted ka g ar f) lo (en_seps nd)
                             (en_kids nd) hi)
             end
         end)
  end.

(* The arena's own ceiling, which `alloc` keeps and nothing else may break. *)
Definition arena_ok (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka) : bool :=
  Nat.leb (length ar) (arena_cap g).

(* =========================================================================
   The two read operations: what the tree answers, and what it represents.
   ========================================================================= *)

Fixpoint lookup (ka : KeyAlgebra) (ar : Arena ka) (fuel b : nat)
                (k : Key ka) : option nat :=
  match nth_error ar b with
  | None => None
  | Some nd =>
      match en_kids nd with
      | nil => look ka k (en_entries nd)
      | cons _ _ =>
          match fuel with
          | 0 => None
          | S f =>
              match nth_error (en_kids nd) (route ka k (en_seps nd)) with
              | None => None
              | Some c => lookup ka ar f c k
              end
          end
      end
  end.

(* The logical map the subtree represents: its entries in key order, read as
   JournalIndex.v's L1 Index. A refused node contributes nothing, which is
   why every statement below is gated on `spans` or on `admitted` rather than
   read off this function alone. *)
Fixpoint flatten (ka : KeyAlgebra) (ar : Arena ka) (fuel b : nat)
  : Index ka :=
  match nth_error ar b with
  | None => nil
  | Some nd =>
      match en_kids nd with
      | nil => en_entries nd
      | cons _ _ =>
          match fuel with
          | 0 => nil
          | S f => flat_map (flatten ka ar f) (en_kids nd)
          end
      end
  end.

(* =========================================================================
   The write operation: copy-on-write insertion with replacement, leaf and
   internal split, and a bounded arena.

   A call answers with the address of the node that replaces the one it was
   given and, where that node overflowed, the separator promoted to the
   parent beside the address of its right half.
   ========================================================================= *)

Definition Grown (ka : KeyAlgebra) : Type :=
  prod nat (option (prod (Key ka) nat)).

(* The parent's rebuilt separator and child lists: the routed child's address
   is replaced, and a promoted separator is spliced in beside its right half.
   Nothing the parent already named is rewritten in place. *)
Definition splice (ka : KeyAlgebra) (j a : nat)
                  (sp : option (prod (Key ka) nat))
                  (ss : list (Key ka)) (cs : list nat)
  : prod (list (Key ka)) (list nat) :=
  match sp with
  | None => pair ss (app (take j cs) (cons a (drop (S j) cs)))
  | Some (pair s r) =>
      pair (app (take j ss) (cons s (drop j ss)))
           (app (take j cs) (cons a (cons r (drop (S j) cs))))
  end.

Definition head_key (ka : KeyAlgebra) (ix : Index ka) : option (Key ka) :=
  match ix with nil => None | cons e _ => Some (fst e) end.

(* One leaf, published whole or split in two. *)
Definition publish_leaf (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                        (ix : Index ka)
  : option (prod (Arena ka) (Grown ka)) :=
  if Nat.leb (length ix) (fan g)
  then match alloc ka g ar (leaf_of ka ix) with
       | None => None
       | Some (pair a ar1) => Some (pair ar1 (pair a None))
       end
  else
    let n := halve (length ix) in
    match head_key ka (drop n ix) with
    | None => None
    | Some s =>
        match alloc ka g ar (leaf_of ka (take n ix)) with
        | None => None
        | Some (pair al ar1) =>
            match alloc ka g ar1 (leaf_of ka (drop n ix)) with
            | None => None
            | Some (pair ap ar2) => Some (pair ar2 (pair al (Some (pair s ap))))
            end
        end
    end.

(* One internal node, published whole or split in two, the separator at the
   cut promoted to the caller. *)
Definition publish_branch (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                          (ss : list (Key ka)) (cs : list nat)
  : option (prod (Arena ka) (Grown ka)) :=
  if Nat.leb (length cs) (fan g)
  then match alloc ka g ar (branch_of ka ss cs) with
       | None => None
       | Some (pair a ar1) => Some (pair ar1 (pair a None))
       end
  else
    let n := halve (length cs) in
    match nth_error ss (Nat.pred n) with
    | None => None
    | Some s =>
        match alloc ka g ar (branch_of ka (take (Nat.pred n) ss) (take n cs)) with
        | None => None
        | Some (pair al ar1) =>
            match alloc ka g ar1 (branch_of ka (drop n ss) (drop n cs)) with
            | None => None
            | Some (pair ap ar2) => Some (pair ar2 (pair al (Some (pair s ap))))
            end
        end
    end.

Fixpoint insert (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                (fuel b : nat) (k : Key ka) (v : nat)
  : option (prod (Arena ka) (Grown ka)) :=
  match nth_error ar b with
  | None => None
  | Some nd =>
      match en_kids nd with
      | nil => publish_leaf ka g ar (ins ka k v (en_entries nd))
      | cons _ _ =>
          match fuel with
          | 0 => None
          | S f =>
              let j := route ka k (en_seps nd) in
              match nth_error (en_kids nd) j with
              | None => None
              | Some c =>
                  match insert ka g ar f c k v with
                  | None => None
                  | Some (pair ar1 (pair a sp)) =>
                      match splice ka j a sp (en_seps nd) (en_kids nd) with
                      | pair ss' cs' => publish_branch ka g ar1 ss' cs'
                      end
                  end
              end
          end
      end
  end.

(* What a grown result represents and answers, read as the concatenation of
   its halves: the caller either keeps one node or holds two beneath a
   separator it is about to place. *)
Definition flatten_grown (ka : KeyAlgebra) (ar : Arena ka) (fuel : nat)
                         (gr : Grown ka) : Index ka :=
  match gr with
  | pair a None => flatten ka ar fuel a
  | pair a (Some (pair _ r)) =>
      app (flatten ka ar fuel a) (flatten ka ar fuel r)
  end.

(* The read a parent makes of a result it has not yet placed: the promoted
   separator routes it, exactly as it will once the parent holds it. *)
Definition lookup_grown (ka : KeyAlgebra) (ar : Arena ka) (fuel : nat)
                        (gr : Grown ka) (k : Key ka) : option nat :=
  match gr with
  | pair a None => lookup ka ar fuel a k
  | pair a (Some (pair s r)) =>
      if key_leb ka s k then lookup ka ar fuel r k else lookup ka ar fuel a k
  end.

Definition admitted_grown (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                          (fuel : nat) (lo hi : Bound ka)
                          (gr : Grown ka) : bool :=
  match gr with
  | pair a None => admitted ka g ar fuel lo hi a
  | pair a (Some (pair s r)) =>
      andb (within ka lo hi s)
      (andb (admitted ka g ar fuel lo (Some s) a)
            (admitted ka g ar fuel (Some s) hi r))
  end.

(* The fail-closed discipline this file ships: the structural and order
   admission is re-decided on the published result, and a result that does
   not decide true is refused rather than returned. *)
Definition insert_checked (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                          (fuel : nat) (lo hi : Bound ka) (b : nat)
                          (k : Key ka) (v : nat)
  : option (prod (Arena ka) (Grown ka)) :=
  match insert ka g ar fuel b k v with
  | None => None
  | Some (pair ar' gr) =>
      if andb (arena_ok ka g ar') (admitted_grown ka g ar' fuel lo hi gr)
      then Some (pair ar' gr) else None
  end.

(* The root, which is the one node with no parent to take a promoted
   separator: a split there publishes a new root one level deeper, and the
   height that walk needs comes back with it. *)
Definition insert_root (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                       (fuel : nat) (lo hi : Bound ka) (b : nat)
                       (k : Key ka) (v : nat)
  : option (prod (Arena ka) (prod nat nat)) :=
  match insert_checked ka g ar fuel lo hi b k v with
  | None => None
  | Some (pair ar' (pair a None)) => Some (pair ar' (pair a fuel))
  | Some (pair ar' (pair a (Some (pair s r)))) =>
      match alloc ka g ar' (branch_of ka (cons s nil) (cons a (cons r nil))) with
      | None => None
      | Some (pair nr ar'') =>
          if andb (arena_ok ka g ar'')
                  (admitted ka g ar'' (S fuel) lo hi nr)
          then Some (pair ar'' (pair nr (S fuel))) else None
      end
  end.

(* =========================================================================
   Addresses, and the frame the append-only arena gives.
   ========================================================================= *)

Lemma nth_error_lt :
  forall (A : Type) (l : list A) (n : nat) (x : A),
    nth_error l n = Some x -> n < length l.
Proof.
  intros A l. induction l as [ | y r IH ]; intros n x H.
  - destruct n; discriminate H.
  - destruct n as [ | m ]; simpl; [ lia | ].
    simpl in H. apply IH in H. lia.
Qed.

Lemma nth_error_app_l :
  forall (A : Type) (l e : list A) (n : nat) (x : A),
    nth_error l n = Some x -> nth_error (app l e) n = Some x.
Proof.
  intros A l. induction l as [ | y r IH ]; intros e n x H.
  - destruct n; discriminate H.
  - destruct n as [ | m ]; simpl in *; [ exact H | exact (IH e m x H) ].
Qed.

Lemma nth_error_app_end :
  forall (A : Type) (l : list A) (x : A),
    nth_error (app l (cons x nil)) (length l) = Some x.
Proof.
  intros A l x. induction l as [ | y r IH ]; simpl; [ reflexivity | exact IH ].
Qed.

Lemma nth_error_mem :
  forall (l : list nat) (n x : nat), nth_error l n = Some x -> mem_of x l = true.
Proof.
  intros l. induction l as [ | y r IH ]; intros n x H.
  - destruct n; discriminate H.
  - destruct n as [ | m ]; simpl in H.
    + injection H as H. rewrite H. exact (mem_of_head x r).
    + exact (mem_of_tail x y r (IH m x H)).
Qed.

Lemma flat_map_agree :
  forall (A B : Type) (f h : A -> list B) (p : A -> bool) (l : list A),
    all_of p l = true -> (forall x : A, p x = true -> f x = h x) ->
    flat_map f l = flat_map h l.
Proof.
  intros A B f h p l. induction l as [ | x r IH ]; intros Hl Hp.
  - reflexivity.
  - simpl in Hl. apply andb_true_iff in Hl as [ Hx Hr ].
    simpl. rewrite (Hp x Hx). rewrite (IH Hr Hp). reflexivity.
Qed.

(* =========================================================================
   What a chain of children says about the children alone.
   ========================================================================= *)

Lemma chain_mono :
  forall (ka : KeyAlgebra) (r1 r2 : Bound ka -> Bound ka -> nat -> bool)
         (ss : list (Key ka)) (cs : list nat) (lo hi : Bound ka),
    (forall (l h : Bound ka) (c : nat), r1 l h c = true -> r2 l h c = true) ->
    chain ka r1 lo ss cs hi = true -> chain ka r2 lo ss cs hi = true.
Proof.
  intros ka r1 r2 ss. induction ss as [ | s st IH ]; intros cs lo hi Hm H.
  - destruct cs as [ | c rest ]; [ discriminate H | ].
    destruct rest as [ | y z ]; [ | discriminate H ].
    simpl in *. exact (Hm lo hi c H).
  - destruct cs as [ | c ct ]; [ discriminate H | ].
    simpl in *. apply andb_true_iff in H as [ H1 H2 ].
    apply andb_true_iff. split.
    + exact (Hm lo (Some s) c H1).
    + exact (IH ct (Some s) hi Hm H2).
Qed.

Lemma chain_all :
  forall (ka : KeyAlgebra) (r : Bound ka -> Bound ka -> nat -> bool)
         (q : nat -> bool) (ss : list (Key ka)) (cs : list nat)
         (lo hi : Bound ka),
    (forall (l h : Bound ka) (c : nat), r l h c = true -> q c = true) ->
    chain ka r lo ss cs hi = true -> all_of q cs = true.
Proof.
  intros ka r q ss. induction ss as [ | s st IH ]; intros cs lo hi Hm H.
  - destruct cs as [ | c rest ]; [ discriminate H | ].
    destruct rest as [ | y z ]; [ | discriminate H ].
    simpl in *. rewrite (Hm lo hi c H). reflexivity.
  - destruct cs as [ | c ct ]; [ discriminate H | ].
    simpl in *. apply andb_true_iff in H as [ H1 H2 ].
    rewrite (Hm lo (Some s) c H1). exact (IH ct (Some s) hi Hm H2).
Qed.

Lemma chain_length :
  forall (ka : KeyAlgebra) (r : Bound ka -> Bound ka -> nat -> bool)
         (ss : list (Key ka)) (cs : list nat) (lo hi : Bound ka),
    chain ka r lo ss cs hi = true -> length cs = S (length ss).
Proof.
  intros ka r ss. induction ss as [ | s st IH ]; intros cs lo hi H.
  - destruct cs as [ | c rest ]; [ discriminate H | ].
    destruct rest as [ | y z ]; [ reflexivity | discriminate H ].
  - destruct cs as [ | c ct ]; [ discriminate H | ].
    simpl in H. apply andb_true_iff in H as [ _ H2 ].
    simpl. rewrite (IH ct (Some s) hi H2). reflexivity.
Qed.

(* =========================================================================
   Admission implies the structural walk, and both survive an append.
   ========================================================================= *)

Lemma admitted_spans :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat),
    admitted ka g ar fuel lo hi b = true -> spans ka ar fuel b = true.
Proof.
  intros ka g fuel. induction fuel as [ | f IH ]; intros ar lo hi b H.
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    apply andb_true_iff in H as [ _ H ].
    destruct (en_kids nd) as [ | c cs ]; [ reflexivity | discriminate H ].
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    apply andb_true_iff in H as [ _ H ].
    destruct (en_kids nd) as [ | c cs ]; [ reflexivity | ].
    apply andb_true_iff in H as [ _ H ].
    exact (chain_all ka (admitted ka g ar f) (spans ka ar f) (en_seps nd)
             (cons c cs) lo hi (fun l h x Hx => IH ar l h x Hx) H).
Qed.

Lemma spans_frame :
  forall (ka : KeyAlgebra) (fuel : nat) (ar ext : Arena ka) (b : nat),
    spans ka ar fuel b = true -> spans ka (app ar ext) fuel b = true.
Proof.
  intros ka fuel. induction fuel as [ | f IH ]; intros ar ext b H.
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E).
    destruct (en_kids nd); [ reflexivity | discriminate H ].
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E).
    destruct (en_kids nd) as [ | c cs ]; [ reflexivity | ].
    apply (all_of_mono nat (spans ka ar f) (spans ka (app ar ext) f));
      [ intros x Hx; exact (IH ar ext x Hx) | exact H ].
Qed.

Lemma flatten_frame :
  forall (ka : KeyAlgebra) (fuel : nat) (ar ext : Arena ka) (b : nat),
    spans ka ar fuel b = true ->
    flatten ka (app ar ext) fuel b = flatten ka ar fuel b.
Proof.
  intros ka fuel. induction fuel as [ | f IH ]; intros ar ext b H.
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E).
    destruct (en_kids nd); [ reflexivity | discriminate H ].
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E).
    destruct (en_kids nd) as [ | c cs ]; [ reflexivity | ].
    exact (flat_map_agree nat (prod (Key ka) nat)
             (flatten ka (app ar ext) f) (flatten ka ar f)
             (spans ka ar f) (cons c cs) H
             (fun x Hx => IH ar ext x Hx)).
Qed.

Lemma lookup_frame :
  forall (ka : KeyAlgebra) (fuel : nat) (ar ext : Arena ka) (b : nat)
         (k : Key ka),
    spans ka ar fuel b = true ->
    lookup ka (app ar ext) fuel b k = lookup ka ar fuel b k.
Proof.
  intros ka fuel. induction fuel as [ | f IH ]; intros ar ext b k H.
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E).
    destruct (en_kids nd); [ reflexivity | discriminate H ].
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E).
    destruct (en_kids nd) as [ | c cs ]; [ reflexivity | ].
    destruct (nth_error (cons c cs) (route ka k (en_seps nd))) as [ x | ] eqn:Ec;
      [ | reflexivity ].
    apply IH.
    exact (all_of_elim (spans ka ar f) (cons c cs) x H
             (nth_error_mem (cons c cs) (route ka k (en_seps nd)) x Ec)).
Qed.

Lemma admitted_frame :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar ext : Arena ka)
         (lo hi : Bound ka) (b : nat),
    admitted ka g ar fuel lo hi b = true ->
    admitted ka g (app ar ext) fuel lo hi b = true.
Proof.
  intros ka g fuel. induction fuel as [ | f IH ]; intros ar ext lo hi b H.
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E). exact H.
  - simpl in H |- *. destruct (nth_error ar b) as [ nd | ] eqn:E;
      [ | discriminate H ].
    rewrite (nth_error_app_l _ ar ext b nd E).
    apply andb_true_iff in H as [ Hf H ]. apply andb_true_iff. split;
      [ exact Hf | ].
    destruct (en_kids nd) as [ | c cs ]; [ exact H | ].
    apply andb_true_iff in H as [ Hr H ]. apply andb_true_iff. split;
      [ exact Hr | ].
    exact (chain_mono ka (admitted ka g ar f) (admitted ka g (app ar ext) f)
             (en_seps nd) (cons c cs) lo hi
             (fun l h x Hx => IH ar ext l h x Hx) H).
Qed.

(* =========================================================================
   Copy-on-write, as the one fact every retained-root statement rests on:
   a write appends and rewrites nothing.
   ========================================================================= *)

Definition appended (ka : KeyAlgebra) (ar ar' : Arena ka) : Prop :=
  exists ext : Arena ka, ar' = app ar ext.

Lemma appended_refl : forall (ka : KeyAlgebra) (ar : Arena ka), appended ka ar ar.
Proof. intros ka ar. exists nil. rewrite app_nil_r. reflexivity. Qed.

Lemma appended_trans :
  forall (ka : KeyAlgebra) (a b c : Arena ka),
    appended ka a b -> appended ka b c -> appended ka a c.
Proof.
  intros ka a b c [ x Hx ] [ y Hy ]. exists (app x y).
  rewrite Hy. rewrite Hx. rewrite (app_assoc_of (ENode ka) a x y). reflexivity.
Qed.

Lemma alloc_appended :
  forall (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka) (nd : ENode ka)
         (a : nat) (ar' : Arena ka),
    alloc ka g ar nd = Some (pair a ar') ->
    appended ka ar ar' /\ a = length ar /\ ar' = app ar (cons nd nil).
Proof.
  intros ka g ar nd a ar' H. unfold alloc in H.
  destruct (Nat.ltb (length ar) (arena_cap g)); [ | discriminate H ].
  injection H as Ha Har. split; [ | split ].
  - exists (cons nd nil). congruence.
  - congruence.
  - congruence.
Qed.

Lemma publish_leaf_appended :
  forall (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka) (ix : Index ka)
         (ar' : Arena ka) (gr : Grown ka),
    publish_leaf ka g ar ix = Some (pair ar' gr) -> appended ka ar ar'.
Proof.
  intros ka g ar ix ar' gr H. unfold publish_leaf in H.
  destruct (Nat.leb (length ix) (fan g)).
  - destruct (alloc ka g ar (leaf_of ka ix)) as [ [ a ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2. apply alloc_appended in E1 as [ Hap _ ].
    rewrite <- H1. exact Hap.
  - destruct (head_key ka (drop (halve (length ix)) ix)) as [ s | ];
      [ | discriminate H ].
    destruct (alloc ka g ar (leaf_of ka (take (halve (length ix)) ix)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1 (leaf_of ka (drop (halve (length ix)) ix)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2.
    apply alloc_appended in E1 as [ Hap1 _ ].
    apply alloc_appended in E2 as [ Hap2 _ ].
    rewrite <- H1. exact (appended_trans ka ar ar1 ar2 Hap1 Hap2).
Qed.

Lemma publish_branch_appended :
  forall (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
         (ss : list (Key ka)) (cs : list nat) (ar' : Arena ka) (gr : Grown ka),
    publish_branch ka g ar ss cs = Some (pair ar' gr) -> appended ka ar ar'.
Proof.
  intros ka g ar ss cs ar' gr H. unfold publish_branch in H.
  destruct (Nat.leb (length cs) (fan g)).
  - destruct (alloc ka g ar (branch_of ka ss cs)) as [ [ a ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2. apply alloc_appended in E1 as [ Hap _ ].
    rewrite <- H1. exact Hap.
  - destruct (nth_error ss (Nat.pred (halve (length cs)))) as [ s | ];
      [ | discriminate H ].
    destruct (alloc ka g ar
                (branch_of ka (take (Nat.pred (halve (length cs))) ss)
                              (take (halve (length cs)) cs)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1
                (branch_of ka (drop (halve (length cs)) ss)
                              (drop (halve (length cs)) cs)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2.
    apply alloc_appended in E1 as [ Hap1 _ ].
    apply alloc_appended in E2 as [ Hap2 _ ].
    rewrite <- H1. exact (appended_trans ka ar ar1 ar2 Hap1 Hap2).
Qed.

(*| discharges: R-10-010 |*)
Lemma an_insert_only_appends :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (b : nat) (k : Key ka) (v : nat) (ar' : Arena ka) (gr : Grown ka),
    insert ka g ar fuel b k v = Some (pair ar' gr) -> appended ka ar ar'.
Proof.
  intros ka g fuel. induction fuel as [ | f IH ]; intros ar b k v ar' gr H;
    simpl in H; destruct (nth_error ar b) as [ nd | ]; try discriminate H.
  - destruct (en_kids nd) as [ | c cs ]; [ | discriminate H ].
    exact (publish_leaf_appended ka g ar _ ar' gr H).
  - destruct (en_kids nd) as [ | c cs ].
    + exact (publish_leaf_appended ka g ar _ ar' gr H).
    + destruct (nth_error (cons c cs) (route ka k (en_seps nd))) as [ x | ];
        [ | discriminate H ].
      destruct (insert ka g ar f x k v) as [ [ ar1 [ a sp ] ] | ] eqn:E1;
        [ | discriminate H ].
      destruct (splice ka (route ka k (en_seps nd)) a sp (en_seps nd)
                       (cons c cs)) as [ ss' cs' ] eqn:Esp.
      apply (appended_trans ka ar ar1 ar').
      * exact (IH ar x k v ar1 (pair a sp) E1).
      * exact (publish_branch_appended ka g ar1 ss' cs' ar' gr H).
Qed.

(* =========================================================================
   R-10-010's retained snapshot root: what a later write does to it, which
   is nothing. The root is read at its own admission, the write is an
   arbitrary insert anywhere in the same arena, and the query is arbitrary.
   ========================================================================= *)

(*| discharges: R-10-010 |*)
Theorem a_retained_root_survives_a_later_insert :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (snap b : nat) (k : Key ka) (v : nat)
         (ar' : Arena ka) (gr : Grown ka) (q : Key ka),
    admitted ka g ar fuel lo hi snap = true ->
    insert ka g ar fuel b k v = Some (pair ar' gr) ->
    lookup ka ar' fuel snap q = lookup ka ar fuel snap q
    /\ flatten ka ar' fuel snap = flatten ka ar fuel snap
    /\ admitted ka g ar' fuel lo hi snap = true.
Proof.
  intros ka g fuel ar lo hi snap b k v ar' gr q Hadm Hins.
  destruct (an_insert_only_appends ka g fuel ar b k v ar' gr Hins) as [ ext He ].
  rewrite He. split; [ | split ].
  - exact (lookup_frame ka fuel ar ext snap q
             (admitted_spans ka g fuel ar lo hi snap Hadm)).
  - exact (flatten_frame ka fuel ar ext snap
             (admitted_spans ka g fuel ar lo hi snap Hadm)).
  - exact (admitted_frame ka g fuel ar ext lo hi snap Hadm).
Qed.

(* =========================================================================
   The key order, derived from KeyAlgebra's five laws and from no carrier.
   ========================================================================= *)

Lemma key_leb_refl : forall (ka : KeyAlgebra) (a : Key ka), key_leb ka a a = true.
Proof.
  intros ka a. pose proof (key_leb_total ka a a) as H.
  destruct (key_leb ka a a); [ reflexivity | discriminate H ].
Qed.

Lemma key_lt_le :
  forall (ka : KeyAlgebra) (a b : Key ka),
    key_lt ka a b = true -> key_leb ka a b = true.
Proof.
  intros ka a b H. unfold key_lt in H. apply andb_true_iff in H as [ H _ ].
  exact H.
Qed.

Lemma key_lt_ne :
  forall (ka : KeyAlgebra) (a b : Key ka),
    key_lt ka a b = true -> key_eqb ka a b = false.
Proof.
  intros ka a b H. unfold key_lt in H. apply andb_true_iff in H as [ _ H ].
  apply negb_true_iff in H. exact H.
Qed.

Lemma key_lt_neq :
  forall (ka : KeyAlgebra) (a b : Key ka),
    key_lt ka a b = true -> key_eqb ka b a = false.
Proof.
  intros ka a b H. exact (key_eqb_false_sym ka a b (key_lt_ne ka a b H)).
Qed.

Lemma key_not_leb_lt :
  forall (ka : KeyAlgebra) (a b : Key ka),
    key_leb ka a b = false -> key_lt ka b a = true.
Proof.
  intros ka a b H. unfold key_lt. apply andb_true_iff. split.
  - exact (key_not_leb_gives_leb ka a b H).
  - apply negb_true_iff. destruct (key_eqb ka b a) eqn:E; [ | reflexivity ].
    rewrite (key_eqb_true ka b a E) in H.
    rewrite (key_leb_refl ka a) in H. discriminate H.
Qed.

Lemma key_lt_trans_le :
  forall (ka : KeyAlgebra) (a b c : Key ka),
    key_lt ka a b = true -> key_leb ka b c = true -> key_lt ka a c = true.
Proof.
  intros ka a b c H1 H2. unfold key_lt in H1 |- *.
  apply andb_true_iff in H1 as [ Hab Hne ]. apply negb_true_iff in Hne.
  apply andb_true_iff. split; [ exact (key_leb_trans ka a b c Hab H2) | ].
  apply negb_true_iff. destruct (key_eqb ka a c) eqn:E; [ | reflexivity ].
  assert (Hba : key_leb ka b a = true)
    by (rewrite (key_eqb_true ka a c E); exact H2).
  rewrite (key_leb_antisym ka a b Hab Hba) in Hne. discriminate Hne.
Qed.

Lemma key_le_lt_trans :
  forall (ka : KeyAlgebra) (a b c : Key ka),
    key_leb ka a b = true -> key_lt ka b c = true -> key_lt ka a c = true.
Proof.
  intros ka a b c H1 H2. unfold key_lt in H2 |- *.
  apply andb_true_iff in H2 as [ Hbc Hne ]. apply negb_true_iff in Hne.
  apply andb_true_iff. split; [ exact (key_leb_trans ka a b c H1 Hbc) | ].
  apply negb_true_iff. destruct (key_eqb ka a c) eqn:E; [ | reflexivity ].
  assert (Hba : key_leb ka b a = true)
    by (rewrite (key_eqb_true ka a c E); exact Hbc).
  assert (Hab : a = b) by exact (key_eqb_true ka a b (key_leb_antisym ka a b H1 Hba)).
  rewrite <- Hab in Hne. rewrite E in Hne. discriminate Hne.
Qed.

(* -------------------------------------------------------------------------
   Widening a subtree's declared range, and reading a range as a comparison
   with one key.
   ------------------------------------------------------------------------- *)

Lemma entries_within_widen_hi :
  forall (ka : KeyAlgebra) (lo hi : Bound ka) (s : Key ka) (ix : Index ka),
    below ka hi s = true ->
    entries_within ka lo (Some s) ix = true ->
    entries_within ka lo hi ix = true.
Proof.
  intros ka lo hi s ix Hs H. unfold entries_within in H |- *.
  apply (all_of_mono (prod (Key ka) nat)
           (fun e => within ka lo (Some s) (fst e))
           (fun e => within ka lo hi (fst e))); [ | exact H ].
  intros e He. unfold within in He |- *.
  apply andb_true_iff in He as [ H1 H2 ]. apply andb_true_iff. split;
    [ exact H1 | ].
  destruct hi as [ h | ]; [ | reflexivity ].
  simpl in H2 |- *. simpl in Hs.
  exact (key_lt_trans_le ka (fst e) s h H2 (key_lt_le ka s h Hs)).
Qed.

Lemma entries_within_widen_lo :
  forall (ka : KeyAlgebra) (lo hi : Bound ka) (s : Key ka) (ix : Index ka),
    above ka lo s = true ->
    entries_within ka (Some s) hi ix = true ->
    entries_within ka lo hi ix = true.
Proof.
  intros ka lo hi s ix Hs H. unfold entries_within in H |- *.
  apply (all_of_mono (prod (Key ka) nat)
           (fun e => within ka (Some s) hi (fst e))
           (fun e => within ka lo hi (fst e))); [ | exact H ].
  intros e He. unfold within in He |- *.
  apply andb_true_iff in He as [ H1 H2 ]. apply andb_true_iff. split;
    [ | exact H2 ].
  destruct lo as [ l | ]; [ | reflexivity ].
  simpl in H1 |- *. simpl in Hs. exact (key_leb_trans ka l s (fst e) Hs H1).
Qed.

Lemma bounds_give_keys_below :
  forall (ka : KeyAlgebra) (lo : Bound ka) (s k : Key ka) (ix : Index ka),
    entries_within ka lo (Some s) ix = true -> key_leb ka s k = true ->
    keys_below ka k ix = true.
Proof.
  intros ka lo s k ix H Hs. unfold entries_within in H. unfold keys_below.
  apply (all_of_mono (prod (Key ka) nat)
           (fun e => within ka lo (Some s) (fst e))
           (fun e => key_lt ka (fst e) k)); [ | exact H ].
  intros e He. unfold within in He. apply andb_true_iff in He as [ _ H2 ].
  simpl in H2. exact (key_lt_trans_le ka (fst e) s k H2 Hs).
Qed.

Lemma bounds_give_keys_above :
  forall (ka : KeyAlgebra) (hi : Bound ka) (s k : Key ka) (ix : Index ka),
    entries_within ka (Some s) hi ix = true -> key_lt ka k s = true ->
    keys_above ka k ix = true.
Proof.
  intros ka hi s k ix H Hs. unfold entries_within in H. unfold keys_above.
  apply (all_of_mono (prod (Key ka) nat)
           (fun e => within ka (Some s) hi (fst e))
           (fun e => key_lt ka k (fst e))); [ | exact H ].
  intros e He. unfold within in He. apply andb_true_iff in He as [ H1 _ ].
  simpl in H1. exact (key_lt_trans_le ka k s (fst e) Hs H1).
Qed.

(* -------------------------------------------------------------------------
   Reading a concatenation, which is what a routed walk past its siblings
   comes down to.
   ------------------------------------------------------------------------- *)

Lemma look_app :
  forall (ka : KeyAlgebra) (k : Key ka) (l r : Index ka),
    look ka k (app l r)
      = match look ka k l with Some v => Some v | None => look ka k r end.
Proof.
  intros ka k l. induction l as [ | e s IH ]; intros r; simpl.
  - reflexivity.
  - destruct (key_eqb ka k (fst e)); [ reflexivity | exact (IH r) ].
Qed.

Lemma look_none_below :
  forall (ka : KeyAlgebra) (k : Key ka) (ix : Index ka),
    keys_below ka k ix = true -> look ka k ix = None.
Proof.
  intros ka k ix. induction ix as [ | e r IH ]; intros H; [ reflexivity | ].
  unfold keys_below in H. simpl in H. apply andb_true_iff in H as [ He Hr ].
  simpl. rewrite (key_lt_neq ka (fst e) k He). exact (IH Hr).
Qed.

Lemma look_none_above :
  forall (ka : KeyAlgebra) (k : Key ka) (ix : Index ka),
    keys_above ka k ix = true -> look ka k ix = None.
Proof.
  intros ka k ix. induction ix as [ | e r IH ]; intros H; [ reflexivity | ].
  unfold keys_above in H. simpl in H. apply andb_true_iff in H as [ He Hr ].
  simpl. rewrite (key_lt_ne ka k (fst e) He). exact (IH Hr).
Qed.

(* -------------------------------------------------------------------------
   Inserting into a concatenation, which is what a routed write past its
   siblings comes down to. Neither lemma knows anything about a tree.
   ------------------------------------------------------------------------- *)

Lemma ins_into_left :
  forall (ka : KeyAlgebra) (k : Key ka) (v : nat) (l r : Index ka),
    keys_above ka k r = true ->
    ins ka k v (app l r) = app (ins ka k v l) r.
Proof.
  intros ka k v l. induction l as [ | e s IH ]; intros r H.
  - destruct r as [ | e0 r0 ]; [ reflexivity | ].
    unfold keys_above in H. simpl in H. apply andb_true_iff in H as [ He _ ].
    simpl. rewrite (key_lt_ne ka k (fst e0) He).
    rewrite (key_lt_le ka k (fst e0) He). reflexivity.
  - simpl. destruct (key_eqb ka k (fst e)); [ reflexivity | ].
    destruct (key_leb ka k (fst e)); [ reflexivity | ].
    simpl. rewrite (IH r H). reflexivity.
Qed.

Lemma ins_into_right :
  forall (ka : KeyAlgebra) (k : Key ka) (v : nat) (l r : Index ka),
    keys_below ka k l = true ->
    ins ka k v (app l r) = app l (ins ka k v r).
Proof.
  intros ka k v l. induction l as [ | e s IH ]; intros r H; [ reflexivity | ].
  unfold keys_below in H. simpl in H. apply andb_true_iff in H as [ He Hs ].
  simpl. rewrite (key_lt_neq ka (fst e) k He).
  assert (Hle : key_leb ka k (fst e) = false).
  { destruct (key_leb ka k (fst e)) eqn:E; [ | reflexivity ].
    unfold key_lt in He. apply andb_true_iff in He as [ H1 H2 ].
    rewrite (key_leb_antisym ka (fst e) k H1 E) in H2. discriminate H2. }
  rewrite Hle. rewrite (IH r Hs). reflexivity.
Qed.

(* =========================================================================
   What an admitted subtree says about the keys it holds, and where a routed
   walk lands. Both are stated over the chain of children, so an arbitrary
   separator list and an arbitrary child list answer them.
   ========================================================================= *)

Lemma chain_bounds_step :
  forall (ka : KeyAlgebra) (g : Geometry) (f : nat) (ar : Arena ka),
    (forall (lo hi : Bound ka) (b : nat), admitted ka g ar f lo hi b = true ->
       entries_within ka lo hi (flatten ka ar f b) = true) ->
    forall (ss : list (Key ka)) (cs : list nat) (lo hi : Bound ka),
      rising ka lo ss hi = true ->
      chain ka (admitted ka g ar f) lo ss cs hi = true ->
      entries_within ka lo hi (flat_map (flatten ka ar f) cs) = true.
Proof.
  intros ka g f ar IH ss. induction ss as [ | s st IHs ]; intros cs lo hi Hr Hc.
  - destruct cs as [ | c rest ]; [ discriminate Hc | ].
    destruct rest as [ | y z ]; [ | discriminate Hc ].
    simpl in Hc. simpl. rewrite app_nil_r. exact (IH lo hi c Hc).
  - destruct cs as [ | c ct ]; [ discriminate Hc | ].
    simpl in Hc. apply andb_true_iff in Hc as [ Hc1 Hc2 ].
    simpl in Hr. apply andb_true_iff in Hr as [ Hw Hr2 ].
    simpl. unfold entries_within. rewrite all_of_app. apply andb_true_iff. split.
    + apply (entries_within_widen_hi ka lo hi s).
      * unfold within in Hw. apply andb_true_iff in Hw as [ _ Hb ]. exact Hb.
      * exact (IH lo (Some s) c Hc1).
    + apply (entries_within_widen_lo ka lo hi s).
      * unfold within in Hw. apply andb_true_iff in Hw as [ Ha _ ]. exact Ha.
      * exact (IHs ct (Some s) hi Hr2 Hc2).
Qed.

Lemma admitted_bounds :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat),
    admitted ka g ar fuel lo hi b = true ->
    entries_within ka lo hi (flatten ka ar fuel b) = true.
Proof.
  intros ka g fuel. induction fuel as [ | f IH ]; intros ar lo hi b H;
    simpl in H |- *; destruct (nth_error ar b) as [ nd | ] eqn:E;
    try discriminate H; apply andb_true_iff in H as [ _ H ].
  - destruct (en_kids nd) as [ | c cs ]; [ | discriminate H ].
    apply andb_true_iff in H as [ _ H ]. exact H.
  - destruct (en_kids nd) as [ | c cs ].
    + apply andb_true_iff in H as [ _ H ]. exact H.
    + apply andb_true_iff in H as [ Hr Hc ].
      exact (chain_bounds_step ka g f ar (fun l h x Hx => IH ar l h x Hx)
               (en_seps nd) (cons c cs) lo hi Hr Hc).
Qed.

Lemma chain_splits :
  forall (ka : KeyAlgebra) (g : Geometry) (f : nat) (ar : Arena ka)
         (ss : list (Key ka)) (cs : list nat) (lo hi : Bound ka) (k : Key ka),
    rising ka lo ss hi = true ->
    chain ka (admitted ka g ar f) lo ss cs hi = true ->
    within ka lo hi k = true ->
    exists (P Q : list nat) (c : nat) (lo' hi' : Bound ka),
      cs = app P (cons c Q)
      /\ length P = route ka k ss
      /\ admitted ka g ar f lo' hi' c = true
      /\ within ka lo' hi' k = true
      /\ keys_below ka k (flat_map (flatten ka ar f) P) = true
      /\ keys_above ka k (flat_map (flatten ka ar f) Q) = true.
Proof.
  intros ka g f ar ss. induction ss as [ | s st IHs ];
    intros cs lo hi k Hr Hc Hw.
  - destruct cs as [ | c rest ]; [ discriminate Hc | ].
    destruct rest as [ | y z ]; [ | discriminate Hc ].
    simpl in Hc. exists nil, nil, c, lo, hi.
    repeat split; try reflexivity; assumption.
  - destruct cs as [ | c ct ]; [ discriminate Hc | ].
    simpl in Hc. apply andb_true_iff in Hc as [ Hc1 Hc2 ].
    simpl in Hr. apply andb_true_iff in Hr as [ Hws Hr2 ].
    unfold within in Hw. apply andb_true_iff in Hw as [ Hwa Hwb ].
    destruct (key_leb ka s k) eqn:Ek.
    + destruct (IHs ct (Some s) hi k Hr2 Hc2
                 (andb_true_intro (conj Ek Hwb)))
        as [ P [ Q [ c' [ lo' [ hi' [ H1 [ H2 [ H3 [ H4 [ H5 H6 ] ] ] ] ] ] ] ] ] ].
      exists (cons c P), Q, c', lo', hi'.
      repeat split; try assumption.
      * simpl. rewrite H1. reflexivity.
      * simpl. rewrite H2. simpl. rewrite Ek. reflexivity.
      * simpl. unfold keys_below. rewrite all_of_app. apply andb_true_iff. split.
        { exact (bounds_give_keys_below ka lo s k (flatten ka ar f c)
                   (admitted_bounds ka g f ar lo (Some s) c Hc1) Ek). }
        { exact H5. }
    + exists nil, ct, c, lo, (Some s).
      assert (Hks : key_lt ka k s = true) by exact (key_not_leb_lt ka s k Ek).
      repeat split; try assumption.
      * simpl. rewrite Ek. reflexivity.
      * unfold within. apply andb_true_iff. split; [ exact Hwa | exact Hks ].
      * exact (bounds_give_keys_above ka hi s k
                 (flat_map (flatten ka ar f) ct)
                 (chain_bounds_step ka g f ar
                    (fun l h x Hx => admitted_bounds ka g f ar l h x Hx)
                    st ct (Some s) hi Hr2 Hc2) Hks).
Qed.

Lemma nth_error_app_mid :
  forall (A : Type) (P Q : list A) (c : A),
    nth_error (app P (cons c Q)) (length P) = Some c.
Proof.
  intros A P. induction P as [ | x r IH ]; intros Q c; simpl;
    [ reflexivity | exact (IH Q c) ].
Qed.

(* =========================================================================
   S1, which states R-10-003's one parametric index for the B+ arm R-10-004
   names: a lookup on the tree is the lookup on the map it represents. The
   tree, the arena, the walk bound, the key algebra, the bounds and the query
   are all arbitrary; the hypothesis is the admission, which `lookup` does not
   run for itself and a caller supplies.
   ========================================================================= *)

(*| discharges: R-10-003 |*)
Theorem lookup_answers_the_logical_map :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat) (k : Key ka),
    admitted ka g ar fuel lo hi b = true ->
    within ka lo hi k = true ->
    lookup ka ar fuel b k = look ka k (flatten ka ar fuel b).
Proof.
  intros ka g fuel. induction fuel as [ | f IH ]; intros ar lo hi b k H Hw;
    simpl in H |- *; destruct (nth_error ar b) as [ nd | ] eqn:E;
    try discriminate H; apply andb_true_iff in H as [ _ H ].
  - destruct (en_kids nd) as [ | c cs ]; [ reflexivity | discriminate H ].
  - destruct (en_kids nd) as [ | c cs ]; [ reflexivity | ].
    apply andb_true_iff in H as [ Hr Hc ].
    destruct (chain_splits ka g f ar (en_seps nd) (cons c cs) lo hi k Hr Hc Hw)
      as [ P [ Q [ c' [ lo' [ hi' [ H1 [ H2 [ H3 [ H4 [ H5 H6 ] ] ] ] ] ] ] ] ] ].
    rewrite H1. rewrite <- H2. rewrite (nth_error_app_mid nat P Q c').
    rewrite flat_map_app. simpl. rewrite look_app.
    rewrite (look_none_below ka k (flat_map (flatten ka ar f) P) H5).
    rewrite look_app.
    rewrite (look_none_above ka k (flat_map (flatten ka ar f) Q) H6).
    rewrite (IH ar lo' hi' c' k H3 H4).
    destruct (look ka k (flatten ka ar f c')); reflexivity.
Qed.

(* =========================================================================
   What a published node is, read back through the arena that holds it.
   ========================================================================= *)

Lemma alloc_node :
  forall (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka) (nd : ENode ka)
         (a : nat) (ar' : Arena ka),
    alloc ka g ar nd = Some (pair a ar') -> nth_error ar' a = Some nd.
Proof.
  intros ka g ar nd a ar' H. apply alloc_appended in H as [ _ [ Ha Har ] ].
  rewrite Har. rewrite Ha. exact (nth_error_app_end (ENode ka) ar nd).
Qed.

Lemma appended_node :
  forall (ka : KeyAlgebra) (ar ar' : Arena ka) (a : nat) (nd : ENode ka),
    appended ka ar ar' -> nth_error ar a = Some nd -> nth_error ar' a = Some nd.
Proof.
  intros ka ar ar' a nd [ ext He ] H. rewrite He.
  exact (nth_error_app_l (ENode ka) ar ext a nd H).
Qed.

Lemma flatten_of_leaf :
  forall (ka : KeyAlgebra) (ar : Arena ka) (fuel a : nat) (ix : Index ka),
    nth_error ar a = Some (leaf_of ka ix) -> flatten ka ar fuel a = ix.
Proof.
  intros ka ar fuel a ix H. destruct fuel; simpl; rewrite H; reflexivity.
Qed.

Lemma flatten_of_branch :
  forall (ka : KeyAlgebra) (ar : Arena ka) (f a : nat) (ss : list (Key ka))
         (cs : list nat),
    nth_error ar a = Some (branch_of ka ss cs) ->
    flatten ka ar (S f) a = flat_map (flatten ka ar f) cs.
Proof.
  intros ka ar f a ss cs H. simpl. rewrite H.
  destruct cs as [ | c r ]; reflexivity.
Qed.

Lemma spans_of_leaf :
  forall (ka : KeyAlgebra) (ar : Arena ka) (fuel a : nat) (ix : Index ka),
    nth_error ar a = Some (leaf_of ka ix) -> spans ka ar fuel a = true.
Proof.
  intros ka ar fuel a ix H. destruct fuel; simpl; rewrite H; reflexivity.
Qed.

Lemma spans_of_branch :
  forall (ka : KeyAlgebra) (ar : Arena ka) (f a : nat) (ss : list (Key ka))
         (cs : list nat),
    nth_error ar a = Some (branch_of ka ss cs) ->
    all_of (spans ka ar f) cs = true -> spans ka ar (S f) a = true.
Proof.
  intros ka ar f a ss cs H Hc. simpl. rewrite H.
  destruct cs as [ | c r ]; [ reflexivity | exact Hc ].
Qed.

(* =========================================================================
   The published results span, which is what lets the next operation trust
   them and what carries the frame from one arena to the next.
   ========================================================================= *)

Lemma publish_leaf_spans :
  forall (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka) (ix : Index ka)
         (ar' : Arena ka) (a : nat) (sp : option (prod (Key ka) nat))
         (fuel : nat),
    publish_leaf ka g ar ix = Some (pair ar' (pair a sp)) ->
    spans ka ar' fuel a = true
    /\ (forall (s r : _), sp = Some (pair s r) -> spans ka ar' fuel r = true).
Proof.
  intros ka g ar ix ar' a sp fuel H. unfold publish_leaf in H.
  destruct (Nat.leb (length ix) (fan g)).
  - destruct (alloc ka g ar (leaf_of ka ix)) as [ [ a0 ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2 H3. split.
    + rewrite <- H1. rewrite <- H2.
      exact (spans_of_leaf ka ar1 fuel a0 ix
               (alloc_node ka g ar (leaf_of ka ix) a0 ar1 E1)).
    + intros s r Hc. rewrite <- H3 in Hc. discriminate Hc.
  - destruct (head_key ka (drop (halve (length ix)) ix)) as [ s0 | ] eqn:Es;
      [ | discriminate H ].
    destruct (alloc ka g ar (leaf_of ka (take (halve (length ix)) ix)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1 (leaf_of ka (drop (halve (length ix)) ix)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2 H3. split.
    + rewrite <- H1. rewrite <- H2.
      apply (spans_of_leaf ka ar2 fuel al (take (halve (length ix)) ix)).
      apply (appended_node ka ar1 ar2 al).
      * exact (proj1 (alloc_appended ka g ar1 _ ap ar2 E2)).
      * exact (alloc_node ka g ar _ al ar1 E1).
    + intros s r Hc. rewrite <- H3 in Hc. injection Hc as Hc1 Hc2.
      rewrite <- H1. rewrite <- Hc2.
      exact (spans_of_leaf ka ar2 fuel ap (drop (halve (length ix)) ix)
               (alloc_node ka g ar1 _ ap ar2 E2)).
Qed.

Lemma publish_branch_spans :
  forall (ka : KeyAlgebra) (g : Geometry) (f : nat) (ar : Arena ka)
         (ss : list (Key ka)) (cs : list nat) (ar' : Arena ka) (a : nat)
         (sp : option (prod (Key ka) nat)),
    all_of (spans ka ar f) cs = true ->
    publish_branch ka g ar ss cs = Some (pair ar' (pair a sp)) ->
    spans ka ar' (S f) a = true
    /\ (forall (s r : _), sp = Some (pair s r) -> spans ka ar' (S f) r = true).
Proof.
  intros ka g f ar ss cs ar' a sp Hcs H. unfold publish_branch in H.
  destruct (Nat.leb (length cs) (fan g)).
  - destruct (alloc ka g ar (branch_of ka ss cs)) as [ [ a0 ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2 H3.
    destruct (alloc_appended ka g ar (branch_of ka ss cs) a0 ar1 E1)
      as [ [ ext He ] _ ]. split.
    + rewrite <- H1. rewrite <- H2.
      apply (spans_of_branch ka ar1 f a0 ss cs
               (alloc_node ka g ar (branch_of ka ss cs) a0 ar1 E1)).
      rewrite He. apply (all_of_mono nat (spans ka ar f) (spans ka (app ar ext) f));
        [ intros x Hx; exact (spans_frame ka f ar ext x Hx) | exact Hcs ].
    + intros s r Hc. rewrite <- H3 in Hc. discriminate Hc.
  - destruct (nth_error ss (Nat.pred (halve (length cs)))) as [ s0 | ] eqn:Es;
      [ | discriminate H ].
    destruct (alloc ka g ar
                (branch_of ka (take (Nat.pred (halve (length cs))) ss)
                              (take (halve (length cs)) cs)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1
                (branch_of ka (drop (halve (length cs)) ss)
                              (drop (halve (length cs)) cs)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2 H3.
    destruct (alloc_appended ka g ar _ al ar1 E1) as [ Hap1 _ ].
    destruct (alloc_appended ka g ar1 _ ap ar2 E2) as [ Hap2 _ ].
    assert (Hall : all_of (spans ka ar2 f) cs = true).
    { destruct (appended_trans ka ar ar1 ar2 Hap1 Hap2) as [ ext He ].
      rewrite He.
      apply (all_of_mono nat (spans ka ar f) (spans ka (app ar ext) f));
        [ intros x Hx; exact (spans_frame ka f ar ext x Hx) | exact Hcs ]. }
    split.
    + rewrite <- H1. rewrite <- H2.
      apply (spans_of_branch ka ar2 f al
               (take (Nat.pred (halve (length cs))) ss)
               (take (halve (length cs)) cs)).
      * apply (appended_node ka ar1 ar2 al); [ exact Hap2 | ].
        exact (alloc_node ka g ar _ al ar1 E1).
      * exact (all_of_take nat (spans ka ar2 f) (halve (length cs)) cs Hall).
    + intros s r Hc. rewrite <- H3 in Hc. injection Hc as Hc1 Hc2.
      rewrite <- H1. rewrite <- Hc2.
      apply (spans_of_branch ka ar2 f ap (drop (halve (length cs)) ss)
               (drop (halve (length cs)) cs)).
      * exact (alloc_node ka g ar1 _ ap ar2 E2).
      * exact (all_of_drop nat (spans ka ar2 f) (halve (length cs)) cs Hall).
Qed.

Lemma splice_spans :
  forall (ka : KeyAlgebra) (f : nat) (ar1 : Arena ka) (j a : nat)
         (sp : option (prod (Key ka) nat)) (ss : list (Key ka))
         (cs : list nat) (ss' : list (Key ka)) (cs' : list nat),
    all_of (spans ka ar1 f) cs = true ->
    spans ka ar1 f a = true ->
    (forall (s r : _), sp = Some (pair s r) -> spans ka ar1 f r = true) ->
    splice ka j a sp ss cs = pair ss' cs' ->
    all_of (spans ka ar1 f) cs' = true.
Proof.
  intros ka f ar1 j a sp ss cs ss' cs' Hcs Ha Hr Hsp.
  destruct sp as [ [ s r ] | ]; simpl in Hsp; injection Hsp as H1 H2;
    rewrite <- H2; rewrite all_of_app; apply andb_true_iff; split;
    try exact (all_of_take nat (spans ka ar1 f) j cs Hcs); simpl; rewrite Ha.
  - rewrite (Hr s r eq_refl).
    exact (all_of_drop nat (spans ka ar1 f) (S j) cs Hcs).
  - exact (all_of_drop nat (spans ka ar1 f) (S j) cs Hcs).
Qed.

(*| discharges: R-10-003 |*)
Lemma an_insert_publishes_spanning_nodes :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (b : nat) (k : Key ka) (v : nat) (ar' : Arena ka) (a : nat)
         (sp : option (prod (Key ka) nat)),
    spans ka ar fuel b = true ->
    insert ka g ar fuel b k v = Some (pair ar' (pair a sp)) ->
    spans ka ar' fuel a = true
    /\ (forall (s r : _), sp = Some (pair s r) -> spans ka ar' fuel r = true).
Proof.
  intros ka g fuel. induction fuel as [ | f IH ];
    intros ar b k v ar' a sp Hs H; simpl in Hs, H;
    destruct (nth_error ar b) as [ nd | ] eqn:E; try discriminate H.
  - destruct (en_kids nd) as [ | c cs ]; [ | discriminate H ].
    exact (publish_leaf_spans ka g ar _ ar' a sp 0 H).
  - destruct (en_kids nd) as [ | c cs ].
    + exact (publish_leaf_spans ka g ar _ ar' a sp (S f) H).
    + destruct (nth_error (cons c cs) (route ka k (en_seps nd)))
        as [ x | ] eqn:Ex; [ | discriminate H ].
      destruct (insert ka g ar f x k v) as [ [ ar1 [ a0 sp0 ] ] | ] eqn:E1;
        [ | discriminate H ].
      destruct (splice ka (route ka k (en_seps nd)) a0 sp0 (en_seps nd)
                       (cons c cs)) as [ ss' cs' ] eqn:Esp.
      assert (Hx : spans ka ar f x = true)
        by exact (all_of_elim (spans ka ar f) (cons c cs) x Hs
                    (nth_error_mem (cons c cs) (route ka k (en_seps nd)) x Ex)).
      destruct (IH ar x k v ar1 a0 sp0 Hx E1) as [ Ha0 Hr0 ].
      destruct (an_insert_only_appends ka g f ar x k v ar1 (pair a0 sp0) E1)
        as [ ext He ].
      assert (Hkids : all_of (spans ka ar1 f) (cons c cs) = true).
      { rewrite He.
        apply (all_of_mono nat (spans ka ar f) (spans ka (app ar ext) f));
          [ intros y Hy; exact (spans_frame ka f ar ext y Hy) | exact Hs ]. }
      apply (publish_branch_spans ka g f ar1 ss' cs' ar' a sp); [ | exact H ].
      exact (splice_spans ka f ar1 (route ka k (en_seps nd)) a0 sp0
               (en_seps nd) (cons c cs) ss' cs' Hkids Ha0 Hr0 Esp).
Qed.

(* =========================================================================
   What a published result represents. A leaf's two halves concatenate to the
   entry list they were cut from, and a branch's two halves concatenate to
   the children it was cut from, so a split changes no map.
   ========================================================================= *)

Lemma flat_map_cons :
  forall (A B : Type) (f : A -> list B) (x : A) (l : list A),
    flat_map f (cons x l) = app (f x) (flat_map f l).
Proof. reflexivity. Qed.

Lemma flatten_grown_one :
  forall (ka : KeyAlgebra) (ar : Arena ka) (fuel a : nat),
    flatten_grown ka ar fuel (pair a None) = flatten ka ar fuel a.
Proof. reflexivity. Qed.

Lemma flatten_grown_two :
  forall (ka : KeyAlgebra) (ar : Arena ka) (fuel a r : nat) (s : Key ka),
    flatten_grown ka ar fuel (pair a (Some (pair s r)))
      = app (flatten ka ar fuel a) (flatten ka ar fuel r).
Proof. reflexivity. Qed.

Lemma publish_leaf_flattens :
  forall (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka) (ix : Index ka)
         (ar' : Arena ka) (gr : Grown ka) (fuel : nat),
    publish_leaf ka g ar ix = Some (pair ar' gr) ->
    flatten_grown ka ar' fuel gr = ix.
Proof.
  intros ka g ar ix ar' gr fuel H. unfold publish_leaf in H.
  destruct (Nat.leb (length ix) (fan g)).
  - destruct (alloc ka g ar (leaf_of ka ix)) as [ [ a0 ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2. rewrite <- H1. rewrite <- H2.
    rewrite flatten_grown_one.
    exact (flatten_of_leaf ka ar1 fuel a0 ix
             (alloc_node ka g ar (leaf_of ka ix) a0 ar1 E1)).
  - destruct (head_key ka (drop (halve (length ix)) ix)) as [ s0 | ] eqn:Es;
      [ | discriminate H ].
    destruct (alloc ka g ar (leaf_of ka (take (halve (length ix)) ix)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1 (leaf_of ka (drop (halve (length ix)) ix)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2. rewrite <- H1. rewrite <- H2.
    rewrite flatten_grown_two.
    assert (Hl : nth_error ar2 al
                 = Some (leaf_of ka (take (halve (length ix)) ix))).
    { apply (appended_node ka ar1 ar2 al);
        [ exact (proj1 (alloc_appended ka g ar1 _ ap ar2 E2))
        | exact (alloc_node ka g ar _ al ar1 E1) ]. }
    assert (Hr : nth_error ar2 ap
                 = Some (leaf_of ka (drop (halve (length ix)) ix)))
      by exact (alloc_node ka g ar1 _ ap ar2 E2).
    rewrite (flatten_of_leaf ka ar2 fuel al _ Hl).
    rewrite (flatten_of_leaf ka ar2 fuel ap _ Hr).
    exact (app_of_take_and_drop (prod (Key ka) nat) (halve (length ix)) ix).
Qed.

Lemma publish_branch_flattens :
  forall (ka : KeyAlgebra) (g : Geometry) (f : nat) (ar : Arena ka)
         (ss : list (Key ka)) (cs : list nat) (ar' : Arena ka) (gr : Grown ka),
    all_of (spans ka ar f) cs = true ->
    publish_branch ka g ar ss cs = Some (pair ar' gr) ->
    flatten_grown ka ar' (S f) gr = flat_map (flatten ka ar f) cs.
Proof.
  intros ka g f ar ss cs ar' gr Hcs H. unfold publish_branch in H.
  destruct (Nat.leb (length cs) (fan g)).
  - destruct (alloc ka g ar (branch_of ka ss cs)) as [ [ a0 ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2. rewrite <- H1. rewrite <- H2.
    rewrite flatten_grown_one.
    rewrite (flatten_of_branch ka ar1 f a0 ss cs
               (alloc_node ka g ar (branch_of ka ss cs) a0 ar1 E1)).
    destruct (alloc_appended ka g ar (branch_of ka ss cs) a0 ar1 E1)
      as [ [ ext He ] _ ].
    rewrite He.
    exact (flat_map_agree nat (prod (Key ka) nat)
             (flatten ka (app ar ext) f) (flatten ka ar f)
             (spans ka ar f) cs Hcs (fun x Hx => flatten_frame ka f ar ext x Hx)).
  - destruct (nth_error ss (Nat.pred (halve (length cs)))) as [ s0 | ] eqn:Es;
      [ | discriminate H ].
    destruct (alloc ka g ar
                (branch_of ka (take (Nat.pred (halve (length cs))) ss)
                              (take (halve (length cs)) cs)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1
                (branch_of ka (drop (halve (length cs)) ss)
                              (drop (halve (length cs)) cs)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2. rewrite <- H1. rewrite <- H2.
    rewrite flatten_grown_two.
    assert (Hl : nth_error ar2 al
                 = Some (branch_of ka (take (Nat.pred (halve (length cs))) ss)
                                      (take (halve (length cs)) cs))).
    { apply (appended_node ka ar1 ar2 al);
        [ exact (proj1 (alloc_appended ka g ar1 _ ap ar2 E2))
        | exact (alloc_node ka g ar _ al ar1 E1) ]. }
    assert (Hr : nth_error ar2 ap
                 = Some (branch_of ka (drop (halve (length cs)) ss)
                                      (drop (halve (length cs)) cs)))
      by exact (alloc_node ka g ar1 _ ap ar2 E2).
    rewrite (flatten_of_branch ka ar2 f al _ _ Hl).
    rewrite (flatten_of_branch ka ar2 f ap _ _ Hr).
    destruct (appended_trans ka ar ar1 ar2
                (proj1 (alloc_appended ka g ar _ al ar1 E1))
                (proj1 (alloc_appended ka g ar1 _ ap ar2 E2))) as [ ext He ].
    rewrite He.
    rewrite (flat_map_agree nat (prod (Key ka) nat)
               (flatten ka (app ar ext) f) (flatten ka ar f) (spans ka ar f)
               (take (halve (length cs)) cs)
               (all_of_take nat (spans ka ar f) (halve (length cs)) cs Hcs)
               (fun x Hx => flatten_frame ka f ar ext x Hx)).
    rewrite (flat_map_agree nat (prod (Key ka) nat)
               (flatten ka (app ar ext) f) (flatten ka ar f) (spans ka ar f)
               (drop (halve (length cs)) cs)
               (all_of_drop nat (spans ka ar f) (halve (length cs)) cs Hcs)
               (fun x Hx => flatten_frame ka f ar ext x Hx)).
    rewrite <- flat_map_app.
    rewrite (app_of_take_and_drop nat (halve (length cs)) cs). reflexivity.
Qed.

(* =========================================================================
   S2, which states R-10-003's index for the B+ arm R-10-004 names and no
   part of R-10-036's checkpoint transaction: an insert on the tree
   represents the logical map's insert, replacement included, and the two
   split cases change no map. Arbitrary key algebra, arena, geometry, walk
   bound, subtree, key and value; the hypothesis is the admission of the
   input, which `insert` does not run for itself and a caller supplies.
   ========================================================================= *)

(*| discharges: R-10-003 |*)
Theorem an_insert_represents_the_logical_map :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat) (k : Key ka) (v : nat)
         (ar' : Arena ka) (gr : Grown ka),
    admitted ka g ar fuel lo hi b = true ->
    within ka lo hi k = true ->
    insert ka g ar fuel b k v = Some (pair ar' gr) ->
    flatten_grown ka ar' fuel gr = ins ka k v (flatten ka ar fuel b).
Proof.
  intros ka g fuel. induction fuel as [ | f IH ];
    intros ar lo hi b k v ar' gr Hadm Hw H;
    simpl in Hadm, H |- *;
    destruct (nth_error ar b) as [ nd | ] eqn:E; try discriminate H;
    apply andb_true_iff in Hadm as [ _ Hadm ].
  - destruct (en_kids nd) as [ | c cs ]; [ | discriminate H ].
    exact (publish_leaf_flattens ka g ar _ ar' gr 0 H).
  - destruct (en_kids nd) as [ | c cs ].
    + exact (publish_leaf_flattens ka g ar _ ar' gr (S f) H).
    + apply andb_true_iff in Hadm as [ Hrise Hchain ].
      destruct (nth_error (cons c cs) (route ka k (en_seps nd)))
        as [ x | ] eqn:Ex; [ | discriminate H ].
      assert (Exm : mem_of x (cons c cs) = true)
        by exact (nth_error_mem (cons c cs) (route ka k (en_seps nd)) x Ex).
      destruct (insert ka g ar f x k v) as [ [ ar1 [ a0 sp0 ] ] | ] eqn:E1;
        [ | discriminate H ].
      destruct (splice ka (route ka k (en_seps nd)) a0 sp0 (en_seps nd)
                       (cons c cs)) as [ ss' cs' ] eqn:Esp.
      assert (Hkids : all_of (spans ka ar f) (cons c cs) = true)
        by exact (chain_all ka (admitted ka g ar f) (spans ka ar f)
                    (en_seps nd) (cons c cs) lo hi
                    (fun l h y Hy => admitted_spans ka g f ar l h y Hy) Hchain).
      destruct (an_insert_only_appends ka g f ar x k v ar1 (pair a0 sp0) E1)
        as [ ext He ].
      assert (Hkids1 : all_of (spans ka ar1 f) (cons c cs) = true).
      { rewrite He.
        apply (all_of_mono nat (spans ka ar f) (spans ka (app ar ext) f));
          [ intros y Hy; exact (spans_frame ka f ar ext y Hy) | exact Hkids ]. }
      destruct (an_insert_publishes_spanning_nodes ka g f ar x k v ar1 a0 sp0
                  (all_of_elim (spans ka ar f) (cons c cs) x Hkids Exm) E1)
        as [ Ha0 Hr0 ].
      rewrite (publish_branch_flattens ka g f ar1 ss' cs' ar' gr
                 (splice_spans ka f ar1 (route ka k (en_seps nd)) a0 sp0
                    (en_seps nd) (cons c cs) ss' cs' Hkids1 Ha0 Hr0 Esp) H).
      destruct (chain_splits ka g f ar (en_seps nd) (cons c cs) lo hi k
                  Hrise Hchain Hw)
        as [ P [ Q [ c' [ lo' [ hi' [ Hcat [ Hlen
             [ Hadm' [ Hw' [ Hbelow Habove ] ] ] ] ] ] ] ] ] ].
      assert (Hx : c' = x).
      { rewrite Hcat in Ex. rewrite <- Hlen in Ex.
        rewrite (nth_error_app_mid nat P Q c') in Ex.
        injection Ex as Ex. exact Ex. }
      rewrite Hx in Hcat. rewrite Hx in Hadm'.
      assert (HIH : flatten_grown ka ar1 f (pair a0 sp0)
                    = ins ka k v (flatten ka ar f x))
        by exact (IH ar lo' hi' x k v ar1 (pair a0 sp0) Hadm' Hw' E1).
      assert (Htake : take (route ka k (en_seps nd)) (cons c cs) = P).
      { rewrite Hcat. rewrite <- Hlen.
        exact (take_app_exact nat P (cons x Q) (length P) eq_refl). }
      assert (Hdrop : drop (S (route ka k (en_seps nd))) (cons c cs) = Q).
      { rewrite Hcat. rewrite <- Hlen.
        exact (drop_after nat P Q x (length P) eq_refl). }
      assert (Hdrop2 : drop (route ka k (en_seps nd)) cs = Q) by exact Hdrop.
      assert (Hsplit : all_of (spans ka ar f) P = true
                       /\ all_of (spans ka ar f) Q = true).
      { rewrite Hcat in Hkids. rewrite all_of_app in Hkids.
        apply andb_true_iff in Hkids as [ HA HB ]. simpl in HB.
        apply andb_true_iff in HB as [ _ HB ]. split; assumption. }
      destruct Hsplit as [ HPs HQs ].
      assert (HFP : flat_map (flatten ka ar1 f) P = flat_map (flatten ka ar f) P).
      { rewrite He. exact (flat_map_agree nat (prod (Key ka) nat)
          (flatten ka (app ar ext) f) (flatten ka ar f) (spans ka ar f) P HPs
          (fun y Hy => flatten_frame ka f ar ext y Hy)). }
      assert (HFQ : flat_map (flatten ka ar1 f) Q = flat_map (flatten ka ar f) Q).
      { rewrite He. exact (flat_map_agree nat (prod (Key ka) nat)
          (flatten ka (app ar ext) f) (flatten ka ar f) (spans ka ar f) Q HQs
          (fun y Hy => flatten_frame ka f ar ext y Hy)). }
      rewrite Hcat. rewrite flat_map_app. rewrite flat_map_cons.
      rewrite (ins_into_right ka k v (flat_map (flatten ka ar f) P)
                 (app (flatten ka ar f x) (flat_map (flatten ka ar f) Q))
                 Hbelow).
      rewrite (ins_into_left ka k v (flatten ka ar f x)
                 (flat_map (flatten ka ar f) Q) Habove).
      destruct sp0 as [ [ s1 r1 ] | ]; simpl in Esp, HIH;
        injection Esp as Es1 Es2; rewrite <- Es2; rewrite Htake; rewrite Hdrop2.
      * rewrite flat_map_app. rewrite flat_map_cons. rewrite flat_map_cons.
        rewrite HFP. rewrite HFQ. rewrite <- HIH.
        rewrite (app_assoc_of (prod (Key ka) nat) (flatten ka ar1 f a0)
                   (flatten ka ar1 f r1) (flat_map (flatten ka ar f) Q)).
        reflexivity.
      * rewrite flat_map_app. rewrite flat_map_cons.
        rewrite HFP. rewrite HFQ. rewrite <- HIH. reflexivity.
Qed.

(* =========================================================================
   The fail-closed discipline, and what it buys.

   `insert_checked` re-decides the structural and order admission on what it
   published and refuses a result that does not decide true, so an admitted
   tree is followed by an admitted tree or by a refusal and never by a tree
   nothing checked. That the check never fires on a well formed input is a
   separate obligation and is owed, not asserted, here.
   ========================================================================= *)

Lemma lookup_grown_one :
  forall (ka : KeyAlgebra) (ar : Arena ka) (fuel a : nat) (k : Key ka),
    lookup_grown ka ar fuel (pair a None) k = lookup ka ar fuel a k.
Proof. reflexivity. Qed.

Lemma lookup_grown_two :
  forall (ka : KeyAlgebra) (ar : Arena ka) (fuel a r : nat) (s k : Key ka),
    lookup_grown ka ar fuel (pair a (Some (pair s r))) k
      = if key_leb ka s k then lookup ka ar fuel r k else lookup ka ar fuel a k.
Proof. reflexivity. Qed.

Theorem a_checked_insert_publishes_an_admitted_result :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat) (k : Key ka) (v : nat)
         (ar' : Arena ka) (gr : Grown ka),
    insert_checked ka g ar fuel lo hi b k v = Some (pair ar' gr) ->
    arena_ok ka g ar' = true
    /\ admitted_grown ka g ar' fuel lo hi gr = true
    /\ insert ka g ar fuel b k v = Some (pair ar' gr).
Proof.
  intros ka g fuel ar lo hi b k v ar' gr H. unfold insert_checked in H.
  destruct (insert ka g ar fuel b k v) as [ [ ar1 gr1 ] | ] eqn:E1;
    [ | discriminate H ].
  destruct (andb (arena_ok ka g ar1) (admitted_grown ka g ar1 fuel lo hi gr1))
    eqn:E2; [ | discriminate H ].
  injection H as H1 H2. apply andb_true_iff in E2 as [ EA EB ].
  rewrite <- H1. rewrite <- H2. split; [ exact EA | split; [ exact EB | ] ].
  reflexivity.
Qed.

Lemma look_grown_agrees :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (gr : Grown ka) (q : Key ka),
    admitted_grown ka g ar fuel lo hi gr = true ->
    within ka lo hi q = true ->
    lookup_grown ka ar fuel gr q = look ka q (flatten_grown ka ar fuel gr).
Proof.
  intros ka g fuel ar lo hi gr q H Hq. destruct gr as [ a [ [ s r ] | ] ].
  - simpl in H. apply andb_true_iff in H as [ Hs H ].
    apply andb_true_iff in H as [ Ha Hr ].
    rewrite lookup_grown_two. rewrite flatten_grown_two. rewrite look_app.
    destruct (key_leb ka s q) eqn:Ek.
    + assert (HqR : within ka (Some s) hi q = true).
      { unfold within in Hq |- *. apply andb_true_iff in Hq as [ _ Hb ].
        apply andb_true_iff. split; [ exact Ek | exact Hb ]. }
      rewrite (look_none_below ka q (flatten ka ar fuel a)
                 (bounds_give_keys_below ka lo s q (flatten ka ar fuel a)
                    (admitted_bounds ka g fuel ar lo (Some s) a Ha) Ek)).
      exact (lookup_answers_the_logical_map ka g fuel ar (Some s) hi r q Hr HqR).
    + assert (Hlt : key_lt ka q s = true) by exact (key_not_leb_lt ka s q Ek).
      assert (HqL : within ka lo (Some s) q = true).
      { unfold within in Hq |- *. apply andb_true_iff in Hq as [ Hb _ ].
        apply andb_true_iff. split; [ exact Hb | exact Hlt ]. }
      rewrite (look_none_above ka q (flatten ka ar fuel r)
                 (bounds_give_keys_above ka hi s q (flatten ka ar fuel r)
                    (admitted_bounds ka g fuel ar (Some s) hi r Hr) Hlt)).
      rewrite (lookup_answers_the_logical_map ka g fuel ar lo (Some s) a q Ha HqL).
      destruct (look ka q (flatten ka ar fuel a)); reflexivity.
  - simpl in H. rewrite lookup_grown_one. rewrite flatten_grown_one.
    exact (lookup_answers_the_logical_map ka g fuel ar lo hi a q H Hq).
Qed.

(* S3, which states R-10-003's index for the B+ arm R-10-004 names and no
   part of R-10-036's checkpoint transaction: end to end, a checked insert
   answers at every key what the logical map's insert answers. *)
(*| discharges: R-10-003 |*)
Theorem a_checked_insert_answers_the_logical_map :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat) (k : Key ka) (v : nat)
         (ar' : Arena ka) (gr : Grown ka) (q : Key ka),
    admitted ka g ar fuel lo hi b = true ->
    within ka lo hi k = true ->
    within ka lo hi q = true ->
    insert_checked ka g ar fuel lo hi b k v = Some (pair ar' gr) ->
    lookup_grown ka ar' fuel gr q
      = look ka q (ins ka k v (flatten ka ar fuel b)).
Proof.
  intros ka g fuel ar lo hi b k v ar' gr q Hadm Hk Hq H.
  destruct (a_checked_insert_publishes_an_admitted_result ka g fuel ar lo hi b
              k v ar' gr H) as [ _ [ Hag Hins ] ].
  rewrite (look_grown_agrees ka g fuel ar' lo hi gr q Hag Hq).
  f_equal.
  exact (an_insert_represents_the_logical_map ka g fuel ar lo hi b k v ar' gr
           Hadm Hk Hins).
Qed.

(* =========================================================================
   The root, where a split publishes a new root one level deeper and the
   height that walk needs comes back with the result.
   ========================================================================= *)

(*| discharges: R-10-003, R-10-010 |*)
Theorem a_checked_root_insert_answers_the_logical_map :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat) (k : Key ka) (v : nat)
         (ar2 : Arena ka) (root height : nat) (q : Key ka),
    admitted ka g ar fuel lo hi b = true ->
    within ka lo hi k = true ->
    within ka lo hi q = true ->
    insert_root ka g ar fuel lo hi b k v = Some (pair ar2 (pair root height)) ->
    admitted ka g ar2 height lo hi root = true
    /\ flatten ka ar2 height root = ins ka k v (flatten ka ar fuel b)
    /\ lookup ka ar2 height root q
       = look ka q (ins ka k v (flatten ka ar fuel b)).
Proof.
  intros ka g fuel ar lo hi b k v ar2 root height q Hadm Hk Hq H.
  unfold insert_root in H.
  destruct (insert_checked ka g ar fuel lo hi b k v)
    as [ [ ar1 [ a [ [ s r ] | ] ] ] | ] eqn:E1; [ | | discriminate H ].
  - (* the root split: a new root is published above the two halves *)
    destruct (alloc ka g ar1 (branch_of ka (cons s nil) (cons a (cons r nil))))
      as [ [ nr ar3 ] | ] eqn:E2; [ | discriminate H ].
    destruct (andb (arena_ok ka g ar3)
                   (admitted ka g ar3 (S fuel) lo hi nr)) eqn:E3;
      [ | discriminate H ].
    injection H as H1 H2 H3.
    apply andb_true_iff in E3 as [ _ E3 ].
    destruct (a_checked_insert_publishes_an_admitted_result ka g fuel ar lo hi b
                k v ar1 (pair a (Some (pair s r))) E1) as [ _ [ Hag Hins ] ].
    simpl in Hag. apply andb_true_iff in Hag as [ _ Hag ].
    apply andb_true_iff in Hag as [ Ha Hr ].
    destruct (alloc_appended ka g ar1 _ nr ar3 E2) as [ [ ext He ] _ ].
    assert (Hflat : flatten ka ar3 (S fuel) nr
                    = ins ka k v (flatten ka ar fuel b)).
    { rewrite (flatten_of_branch ka ar3 fuel nr (cons s nil)
                 (cons a (cons r nil))
                 (alloc_node ka g ar1 _ nr ar3 E2)).
      rewrite flat_map_cons. rewrite flat_map_cons. simpl.
      rewrite app_nil_r. rewrite He.
      rewrite (flatten_frame ka fuel ar1 ext a
                 (admitted_spans ka g fuel ar1 lo (Some s) a Ha)).
      rewrite (flatten_frame ka fuel ar1 ext r
                 (admitted_spans ka g fuel ar1 (Some s) hi r Hr)).
      rewrite <- (flatten_grown_two ka ar1 fuel a r s).
      exact (an_insert_represents_the_logical_map ka g fuel ar lo hi b k v ar1
               (pair a (Some (pair s r))) Hadm Hk Hins). }
    rewrite <- H1. rewrite <- H2. rewrite <- H3.
    split; [ exact E3 | split; [ exact Hflat | ] ].
    rewrite (lookup_answers_the_logical_map ka g (S fuel) ar3 lo hi nr q E3 Hq).
    rewrite Hflat. reflexivity.
  - (* no root split: the published node is the new root at the same height *)
    injection H as H1 H2 H3.
    destruct (a_checked_insert_publishes_an_admitted_result ka g fuel ar lo hi b
                k v ar1 (pair a None) E1) as [ _ [ Hag Hins ] ].
    simpl in Hag.
    assert (Hflat : flatten ka ar1 fuel a = ins ka k v (flatten ka ar fuel b)).
    { rewrite <- (flatten_grown_one ka ar1 fuel a).
      exact (an_insert_represents_the_logical_map ka g fuel ar lo hi b k v ar1
               (pair a None) Hadm Hk Hins). }
    rewrite <- H1. rewrite <- H2. rewrite <- H3.
    split; [ exact Hag | split; [ exact Hflat | ] ].
    rewrite (lookup_answers_the_logical_map ka g fuel ar1 lo hi a q Hag Hq).
    rewrite Hflat. reflexivity.
Qed.

(* =========================================================================
   Balance, in the two readings this file keeps apart, because one of them is
   the B+ property and the other is not.

   Occupancy. Every node the walk reaches holds no more entries and no more
   children than the declared fanout and carries exactly one separator fewer
   than its children. `node_fits_everywhere` decides that and nothing else: it
   is `node_fits` applied down the walk, hence a conjunct of `admitted`, hence
   decided by the fail-closed check on every published result. It is named for
   what it decides rather than for balance, because it is blind to where a
   leaf sits.

   Equal leaf depth, which is the B+ property a reader of the word balance
   takes: every leaf sits at one common distance below the root. Neither
   `admitted` nor occupancy decides it. The skewed witness at the end of this
   file is admitted, occupancy-fitting and spanning while one of its leaves
   hangs a level above the others, and the fail-closed check does not repair
   it, because what `insert_root` re-decides is `admitted`, which that tree
   passes. `at_depth` decides equal leaf depth at a stated depth and
   `leaves_share_one_depth` searches the depths a bound admits.

   What carries the property is therefore not the check but the two theorems
   below: an insert from a subtree whose leaves share a depth publishes both
   halves at that same depth, and a root insert answers at that depth or at
   exactly one more, which is the only place a B+ tree's height moves. Equal
   leaf depth enters as a hypothesis, so a composition establishes it once, at
   the empty root where it is immediate, and these theorems carry it from
   there. Nothing below decides it inside `insert_root`, and the skew witness
   is what that costs.

   Still owed at M5.3d, here as everywhere in this file, and asserted nowhere
   as an admit: that the fail-closed check never refuses a well formed insert.
   ========================================================================= *)

Fixpoint node_fits_everywhere (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka)
                              (fuel b : nat) : bool :=
  match nth_error ar b with
  | None => false
  | Some nd =>
      andb (node_fits ka g nd)
        (match en_kids nd with
         | nil => true
         | cons c cs =>
             match fuel with
             | 0 => false
             | S f => all_of (node_fits_everywhere ka g ar f) (cons c cs)
             end
         end)
  end.

(*| discharges: R-10-003 |*)
Theorem an_admitted_tree_fits_everywhere :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (b : nat),
    admitted ka g ar fuel lo hi b = true ->
    node_fits_everywhere ka g ar fuel b = true.
Proof.
  intros ka g fuel. induction fuel as [ | f IH ]; intros ar lo hi b H;
    simpl in H |- *; destruct (nth_error ar b) as [ nd | ] eqn:E;
    try discriminate H; apply andb_true_iff in H as [ Hf H ];
    apply andb_true_iff; split; try exact Hf.
  - destruct (en_kids nd) as [ | c cs ]; [ reflexivity | discriminate H ].
  - destruct (en_kids nd) as [ | c cs ]; [ reflexivity | ].
    apply andb_true_iff in H as [ _ H ].
    exact (chain_all ka (admitted ka g ar f)
             (node_fits_everywhere ka g ar f) (en_seps nd)
             (cons c cs) lo hi (fun l h y Hy => IH ar l h y Hy) H).
Qed.

(* Equal leaf depth at a stated depth: a node is at depth zero exactly when it
   is a leaf, and at depth `S e` exactly when it names children and every one
   of them is at depth `e`. A leaf that sits higher than its siblings is
   refused at every depth, which is what the skew witness computes. *)
Fixpoint at_depth (ka : KeyAlgebra) (ar : Arena ka) (d b : nat) : bool :=
  match nth_error ar b with
  | None => false
  | Some nd =>
      match en_kids nd with
      | nil => match d with 0 => true | S _ => false end
      | cons _ _ =>
          match d with
          | 0 => false
          | S e => all_of (at_depth ka ar e) (en_kids nd)
          end
      end
  end.

(* The same question without naming the depth: is there one, at most `bound`
   levels deep, that every leaf shares. A tree answers at exactly one such
   depth, so the search decides the property rather than approximating it. *)
Fixpoint leaves_share_one_depth (ka : KeyAlgebra) (ar : Arena ka)
                                (bound b : nat) : bool :=
  match bound with
  | 0 => at_depth ka ar 0 b
  | S m => orb (at_depth ka ar (S m) b) (leaves_share_one_depth ka ar m b)
  end.

Lemma leaves_share_one_depth_intro :
  forall (ka : KeyAlgebra) (ar : Arena ka) (bound d b : nat),
    d <= bound -> at_depth ka ar d b = true ->
    leaves_share_one_depth ka ar bound b = true.
Proof.
  intros ka ar bound. induction bound as [ | m IH ]; intros d b Hle Hd;
    cbn [ leaves_share_one_depth ].
  - destruct d as [ | e ]; [ exact Hd | exfalso; lia ].
  - destruct (Nat.eq_dec d (S m)) as [ He | Hne ].
    + rewrite He in Hd. rewrite Hd. reflexivity.
    + assert (Hm : d <= m) by lia.
      rewrite (IH d b Hm Hd). apply orb_true_r.
Qed.

(* Equal leaf depth is the stronger of the two structural walks: a tree whose
   leaves share a depth spans at that depth. The converse fails, which is the
   skew witness. *)
Lemma at_depth_spans :
  forall (ka : KeyAlgebra) (ar : Arena ka) (d b : nat),
    at_depth ka ar d b = true -> spans ka ar d b = true.
Proof.
  intros ka ar d. induction d as [ | e IH ]; intros b H; simpl in H |- *;
    destruct (nth_error ar b) as [ nd | ] eqn:E; try discriminate H.
  - destruct (en_kids nd) as [ | c cs ]; [ reflexivity | discriminate H ].
  - destruct (en_kids nd) as [ | c cs ]; [ discriminate H | ].
    apply (all_of_mono nat (at_depth ka ar e) (spans ka ar e));
      [ intros x Hx; exact (IH x Hx) | exact H ].
Qed.

Lemma at_depth_frame :
  forall (ka : KeyAlgebra) (d : nat) (ar ext : Arena ka) (b : nat),
    at_depth ka ar d b = true -> at_depth ka (app ar ext) d b = true.
Proof.
  intros ka d. induction d as [ | e IH ]; intros ar ext b H; simpl in H |- *;
    destruct (nth_error ar b) as [ nd | ] eqn:E; try discriminate H;
    rewrite (nth_error_app_l _ ar ext b nd E).
  - destruct (en_kids nd); [ reflexivity | discriminate H ].
  - destruct (en_kids nd) as [ | c cs ]; [ discriminate H | ].
    apply (all_of_mono nat (at_depth ka ar e) (at_depth ka (app ar ext) e));
      [ intros x Hx; exact (IH ar ext x Hx) | exact H ].
Qed.

Lemma at_depth_of_leaf :
  forall (ka : KeyAlgebra) (ar : Arena ka) (a : nat) (ix : Index ka),
    nth_error ar a = Some (leaf_of ka ix) -> at_depth ka ar 0 a = true.
Proof.
  intros ka ar a ix H. simpl. rewrite H. reflexivity.
Qed.

Lemma at_depth_of_branch :
  forall (ka : KeyAlgebra) (ar : Arena ka) (e a : nat) (ss : list (Key ka))
         (cs : list nat),
    nth_error ar a = Some (branch_of ka ss cs) ->
    cs <> nil ->
    all_of (at_depth ka ar e) cs = true ->
    at_depth ka ar (S e) a = true.
Proof.
  intros ka ar e a ss cs H Hne Hall. simpl. rewrite H. simpl.
  destruct cs as [ | c r ]; [ exfalso; exact (Hne eq_refl) | exact Hall ].
Qed.

(* A split halves a child list, so the two halves must both be non-empty or a
   branch would be published as a leaf and the depth would move under it.
   Those are the two facts the geometry's fanout floor buys. *)
Lemma take_not_nil :
  forall (A : Type) (n : nat) (l : list A),
    0 < n -> l <> nil -> take n l <> nil.
Proof.
  intros A n l Hn Hl. destruct n as [ | m ]; [ exfalso; lia | ].
  destruct l as [ | x r ]; [ exfalso; exact (Hl eq_refl) | ].
  simpl. discriminate.
Qed.

Lemma drop_not_nil :
  forall (A : Type) (n : nat) (l : list A), n < length l -> drop n l <> nil.
Proof.
  intros A n. induction n as [ | m IH ]; intros l H.
  - destruct l as [ | x r ]; [ simpl in H; exfalso; lia | simpl; discriminate ].
  - destruct l as [ | x r ]; [ simpl in H; exfalso; lia | ].
    simpl in H. simpl. apply IH. lia.
Qed.

Lemma splice_not_nil :
  forall (ka : KeyAlgebra) (j a : nat) (sp : option (prod (Key ka) nat))
         (ss : list (Key ka)) (cs : list nat) (ss' : list (Key ka))
         (cs' : list nat),
    splice ka j a sp ss cs = pair ss' cs' -> cs' <> nil.
Proof.
  intros ka j a sp ss cs ss' cs' H.
  destruct sp as [ [ s r ] | ]; simpl in H; injection H as H1 H2;
    rewrite <- H2; destruct (take j cs); simpl; discriminate.
Qed.

Lemma publish_leaf_at_depth :
  forall (ka : KeyAlgebra) (g : Geometry) (ar : Arena ka) (ix : Index ka)
         (ar' : Arena ka) (a : nat) (sp : option (prod (Key ka) nat)),
    publish_leaf ka g ar ix = Some (pair ar' (pair a sp)) ->
    at_depth ka ar' 0 a = true
    /\ (forall (s r : _), sp = Some (pair s r) -> at_depth ka ar' 0 r = true).
Proof.
  intros ka g ar ix ar' a sp H. unfold publish_leaf in H.
  destruct (Nat.leb (length ix) (fan g)).
  - destruct (alloc ka g ar (leaf_of ka ix)) as [ [ a0 ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2 H3. split.
    + rewrite <- H1. rewrite <- H2.
      exact (at_depth_of_leaf ka ar1 a0 ix
               (alloc_node ka g ar (leaf_of ka ix) a0 ar1 E1)).
    + intros s r Hc. rewrite <- H3 in Hc. discriminate Hc.
  - destruct (head_key ka (drop (halve (length ix)) ix)) as [ s0 | ] eqn:Es;
      [ | discriminate H ].
    destruct (alloc ka g ar (leaf_of ka (take (halve (length ix)) ix)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1 (leaf_of ka (drop (halve (length ix)) ix)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2 H3. split.
    + rewrite <- H1. rewrite <- H2.
      apply (at_depth_of_leaf ka ar2 al (take (halve (length ix)) ix)).
      apply (appended_node ka ar1 ar2 al).
      * exact (proj1 (alloc_appended ka g ar1 _ ap ar2 E2)).
      * exact (alloc_node ka g ar _ al ar1 E1).
    + intros s r Hc. rewrite <- H3 in Hc. injection Hc as Hc1 Hc2.
      rewrite <- H1. rewrite <- Hc2.
      exact (at_depth_of_leaf ka ar2 ap (drop (halve (length ix)) ix)
               (alloc_node ka g ar1 _ ap ar2 E2)).
Qed.

Lemma publish_branch_at_depth :
  forall (ka : KeyAlgebra) (g : Geometry) (e : nat) (ar : Arena ka)
         (ss : list (Key ka)) (cs : list nat) (ar' : Arena ka) (a : nat)
         (sp : option (prod (Key ka) nat)),
    geometry_ok g = true ->
    cs <> nil ->
    all_of (at_depth ka ar e) cs = true ->
    publish_branch ka g ar ss cs = Some (pair ar' (pair a sp)) ->
    at_depth ka ar' (S e) a = true
    /\ (forall (s r : _), sp = Some (pair s r) ->
          at_depth ka ar' (S e) r = true).
Proof.
  intros ka g e ar ss cs ar' a sp Hg Hne Hcs H. unfold publish_branch in H.
  destruct (Nat.leb (length cs) (fan g)) eqn:Eb.
  - destruct (alloc ka g ar (branch_of ka ss cs)) as [ [ a0 ar1 ] | ] eqn:E1;
      [ | discriminate H ].
    injection H as H1 H2 H3.
    destruct (alloc_appended ka g ar (branch_of ka ss cs) a0 ar1 E1)
      as [ [ ext He ] _ ]. split.
    + rewrite <- H1. rewrite <- H2.
      apply (at_depth_of_branch ka ar1 e a0 ss cs
               (alloc_node ka g ar (branch_of ka ss cs) a0 ar1 E1) Hne).
      rewrite He.
      apply (all_of_mono nat (at_depth ka ar e) (at_depth ka (app ar ext) e));
        [ intros x Hx; exact (at_depth_frame ka e ar ext x Hx) | exact Hcs ].
    + intros s r Hc. rewrite <- H3 in Hc. discriminate Hc.
  - assert (Hlen : 1 < length cs).
    { apply Nat.leb_gt in Eb. unfold geometry_ok in Hg.
      apply andb_true_iff in Hg as [ Hf _ ]. apply Nat.leb_le in Hf. lia. }
    destruct (nth_error ss (Nat.pred (halve (length cs)))) as [ s0 | ] eqn:Es;
      [ | discriminate H ].
    destruct (alloc ka g ar
                (branch_of ka (take (Nat.pred (halve (length cs))) ss)
                              (take (halve (length cs)) cs)))
      as [ [ al ar1 ] | ] eqn:E1; [ | discriminate H ].
    destruct (alloc ka g ar1
                (branch_of ka (drop (halve (length cs)) ss)
                              (drop (halve (length cs)) cs)))
      as [ [ ap ar2 ] | ] eqn:E2; [ | discriminate H ].
    injection H as H1 H2 H3.
    destruct (alloc_appended ka g ar _ al ar1 E1) as [ Hap1 _ ].
    destruct (alloc_appended ka g ar1 _ ap ar2 E2) as [ Hap2 _ ].
    assert (Hall : all_of (at_depth ka ar2 e) cs = true).
    { destruct (appended_trans ka ar ar1 ar2 Hap1 Hap2) as [ ext He ].
      rewrite He.
      apply (all_of_mono nat (at_depth ka ar e) (at_depth ka (app ar ext) e));
        [ intros x Hx; exact (at_depth_frame ka e ar ext x Hx) | exact Hcs ]. }
    assert (Hpos : 0 < halve (length cs)) by exact (halve_pos (length cs) Hlen).
    assert (Hlt : halve (length cs) < length cs) by (apply halve_lt; lia).
    split.
    + rewrite <- H1. rewrite <- H2.
      apply (at_depth_of_branch ka ar2 e al
               (take (Nat.pred (halve (length cs))) ss)
               (take (halve (length cs)) cs)).
      * apply (appended_node ka ar1 ar2 al); [ exact Hap2 | ].
        exact (alloc_node ka g ar _ al ar1 E1).
      * apply take_not_nil; [ exact Hpos | exact Hne ].
      * exact (all_of_take nat (at_depth ka ar2 e) (halve (length cs)) cs Hall).
    + intros s r Hc. rewrite <- H3 in Hc. injection Hc as Hc1 Hc2.
      rewrite <- H1. rewrite <- Hc2.
      apply (at_depth_of_branch ka ar2 e ap (drop (halve (length cs)) ss)
               (drop (halve (length cs)) cs)).
      * exact (alloc_node ka g ar1 _ ap ar2 E2).
      * exact (drop_not_nil nat (halve (length cs)) cs Hlt).
      * exact (all_of_drop nat (at_depth ka ar2 e) (halve (length cs)) cs Hall).
Qed.

Lemma splice_at_depth :
  forall (ka : KeyAlgebra) (e : nat) (ar1 : Arena ka) (j a : nat)
         (sp : option (prod (Key ka) nat)) (ss : list (Key ka))
         (cs : list nat) (ss' : list (Key ka)) (cs' : list nat),
    all_of (at_depth ka ar1 e) cs = true ->
    at_depth ka ar1 e a = true ->
    (forall (s r : _), sp = Some (pair s r) -> at_depth ka ar1 e r = true) ->
    splice ka j a sp ss cs = pair ss' cs' ->
    all_of (at_depth ka ar1 e) cs' = true.
Proof.
  intros ka e ar1 j a sp ss cs ss' cs' Hcs Ha Hr Hsp.
  destruct sp as [ [ s r ] | ]; simpl in Hsp; injection Hsp as H1 H2;
    rewrite <- H2; rewrite all_of_app; apply andb_true_iff; split;
    try exact (all_of_take nat (at_depth ka ar1 e) j cs Hcs); simpl; rewrite Ha.
  - rewrite (Hr s r eq_refl).
    exact (all_of_drop nat (at_depth ka ar1 e) (S j) cs Hcs).
  - exact (all_of_drop nat (at_depth ka ar1 e) (S j) cs Hcs).
Qed.

(* The preservation the fail-closed check does not give: an insert into a
   subtree whose leaves share a depth publishes its one or two halves at that
   same depth. The walk bound the caller passes has only to reach that depth.
   ========================================================================= *)
(*| discharges: R-10-003 |*)
Theorem an_insert_keeps_the_leaves_at_one_depth :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (d b : nat) (k : Key ka) (v : nat) (ar' : Arena ka) (a : nat)
         (sp : option (prod (Key ka) nat)),
    geometry_ok g = true ->
    d <= fuel ->
    at_depth ka ar d b = true ->
    insert ka g ar fuel b k v = Some (pair ar' (pair a sp)) ->
    at_depth ka ar' d a = true
    /\ (forall (s r : _), sp = Some (pair s r) -> at_depth ka ar' d r = true).
Proof.
  intros ka g fuel. induction fuel as [ | f IH ];
    intros ar d b k v ar' a sp Hg Hle Hd H; simpl in H;
    destruct (nth_error ar b) as [ nd | ] eqn:E; try discriminate H.
  - assert (Hd0 : d = 0) by lia. subst d.
    destruct (en_kids nd) as [ | c cs ]; [ | discriminate H ].
    exact (publish_leaf_at_depth ka g ar _ ar' a sp H).
  - destruct d as [ | e ]; simpl in Hd; rewrite E in Hd.
    + destruct (en_kids nd) as [ | c cs ]; [ | discriminate Hd ].
      exact (publish_leaf_at_depth ka g ar _ ar' a sp H).
    + destruct (en_kids nd) as [ | c cs ]; [ discriminate Hd | ].
      destruct (nth_error (cons c cs) (route ka k (en_seps nd)))
        as [ x | ] eqn:Ex; [ | discriminate H ].
      destruct (insert ka g ar f x k v) as [ [ ar1 [ a0 sp0 ] ] | ] eqn:E1;
        [ | discriminate H ].
      destruct (splice ka (route ka k (en_seps nd)) a0 sp0 (en_seps nd)
                       (cons c cs)) as [ ss' cs' ] eqn:Esp.
      assert (Hx : at_depth ka ar e x = true)
        by exact (all_of_elim (at_depth ka ar e) (cons c cs) x Hd
                    (nth_error_mem (cons c cs) (route ka k (en_seps nd)) x Ex)).
      assert (Hef : e <= f) by lia.
      destruct (IH ar e x k v ar1 a0 sp0 Hg Hef Hx E1) as [ Ha0 Hr0 ].
      destruct (an_insert_only_appends ka g f ar x k v ar1 (pair a0 sp0) E1)
        as [ ext He ].
      assert (Hkids : all_of (at_depth ka ar1 e) (cons c cs) = true).
      { rewrite He.
        apply (all_of_mono nat (at_depth ka ar e) (at_depth ka (app ar ext) e));
          [ intros y Hy; exact (at_depth_frame ka e ar ext y Hy) | exact Hd ]. }
      apply (publish_branch_at_depth ka g e ar1 ss' cs' ar' a sp Hg);
        [ | | exact H ].
      * exact (splice_not_nil ka (route ka k (en_seps nd)) a0 sp0 (en_seps nd)
                 (cons c cs) ss' cs' Esp).
      * exact (splice_at_depth ka e ar1 (route ka k (en_seps nd)) a0 sp0
                 (en_seps nd) (cons c cs) ss' cs' Hkids Ha0 Hr0 Esp).
Qed.

(*| discharges: R-10-003 |*)
Lemma a_checked_insert_keeps_the_leaves_at_one_depth :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (d b : nat) (k : Key ka) (v : nat)
         (ar' : Arena ka) (a : nat) (sp : option (prod (Key ka) nat)),
    geometry_ok g = true ->
    d <= fuel ->
    at_depth ka ar d b = true ->
    insert_checked ka g ar fuel lo hi b k v = Some (pair ar' (pair a sp)) ->
    at_depth ka ar' d a = true
    /\ (forall (s r : _), sp = Some (pair s r) -> at_depth ka ar' d r = true).
Proof.
  intros ka g fuel ar lo hi d b k v ar' a sp Hg Hle Hd H.
  unfold insert_checked in H.
  destruct (insert ka g ar fuel b k v) as [ [ ar1 [ a1 sp1 ] ] | ] eqn:E1;
    [ | discriminate H ].
  destruct (andb (arena_ok ka g ar1)
                 (admitted_grown ka g ar1 fuel lo hi (pair a1 sp1)));
    [ | discriminate H ].
  injection H as H1 H2 H3. rewrite <- H1. rewrite <- H2. rewrite <- H3.
  exact (an_insert_keeps_the_leaves_at_one_depth ka g fuel ar d b k v ar1 a1 sp1
           Hg Hle Hd E1).
Qed.

(* The root, which is the one place a B+ tree's height moves: a checked root
   insert answers at the depth its input had, or at exactly one more where the
   root itself split. Both answers keep every leaf at one depth. *)
(*| discharges: R-10-003, R-10-010 |*)
Theorem a_root_insert_keeps_the_leaves_at_one_depth :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (d b : nat) (k : Key ka) (v : nat)
         (ar' : Arena ka) (nr h : nat),
    geometry_ok g = true ->
    d <= fuel ->
    at_depth ka ar d b = true ->
    insert_root ka g ar fuel lo hi b k v = Some (pair ar' (pair nr h)) ->
    (at_depth ka ar' d nr = true /\ h = fuel)
    \/ (at_depth ka ar' (S d) nr = true /\ h = S fuel).
Proof.
  intros ka g fuel ar lo hi d b k v ar' nr h Hg Hle Hd H.
  unfold insert_root in H.
  destruct (insert_checked ka g ar fuel lo hi b k v)
    as [ [ ar1 [ a sp ] ] | ] eqn:E1; [ | discriminate H ].
  destruct (a_checked_insert_keeps_the_leaves_at_one_depth ka g fuel ar lo hi d
              b k v ar1 a sp Hg Hle Hd E1) as [ Ha Hr ].
  destruct sp as [ [ s r ] | ].
  - destruct (alloc ka g ar1 (branch_of ka (cons s nil) (cons a (cons r nil))))
      as [ [ nr0 ar2 ] | ] eqn:E2; [ | discriminate H ].
    destruct (andb (arena_ok ka g ar2)
                   (admitted ka g ar2 (S fuel) lo hi nr0)); [ | discriminate H ].
    injection H as H1 H2 H3. right. split; [ | congruence ].
    rewrite <- H1. rewrite <- H2.
    destruct (alloc_appended ka g ar1 _ nr0 ar2 E2) as [ [ ext He ] _ ].
    apply (at_depth_of_branch ka ar2 d nr0 (cons s nil)
             (cons a (cons r nil))).
    + exact (alloc_node ka g ar1 _ nr0 ar2 E2).
    + discriminate.
    + rewrite He. simpl.
      rewrite (at_depth_frame ka d ar1 ext a Ha).
      rewrite (at_depth_frame ka d ar1 ext r (Hr s r eq_refl)).
      reflexivity.
  - injection H as H1 H2 H3. left. split; [ | congruence ].
    rewrite <- H1. rewrite <- H2. exact Ha.
Qed.

(*| discharges: R-10-003 |*)
Corollary a_root_insert_keeps_one_leaf_depth :
  forall (ka : KeyAlgebra) (g : Geometry) (fuel : nat) (ar : Arena ka)
         (lo hi : Bound ka) (d b : nat) (k : Key ka) (v : nat)
         (ar' : Arena ka) (nr h : nat),
    geometry_ok g = true ->
    d <= fuel ->
    at_depth ka ar d b = true ->
    insert_root ka g ar fuel lo hi b k v = Some (pair ar' (pair nr h)) ->
    leaves_share_one_depth ka ar' h nr = true.
Proof.
  intros ka g fuel ar lo hi d b k v ar' nr h Hg Hle Hd H.
  destruct (a_root_insert_keeps_the_leaves_at_one_depth ka g fuel ar lo hi d b k
              v ar' nr h Hg Hle Hd H) as [ [ Ha Hh ] | [ Ha Hh ] ].
  - rewrite Hh. exact (leaves_share_one_depth_intro ka ar' fuel d nr Hle Ha).
  - rewrite Hh.
    apply (leaves_share_one_depth_intro ka ar' (S fuel) (S d) nr);
      [ lia | exact Ha ].
Qed.

(* =========================================================================
   Inhabitation and the computed families.

   Every numeral below is a demo or probe witness value carrying no
   composition claim: the arena capacity, the fanout, the declared depth, the
   keys and the values are chosen small enough that a family is decided by
   conversion rather than by a proof per member, and none of them is read
   from the register.
   ========================================================================= *)

Definition demo_geometry : Geometry :=
  {| arena_cap := 12; fan := 2; depth := 2 |}.

Definition tight_geometry : Geometry :=
  {| arena_cap := 3; fan := 2; depth := 2 |}.

Definition thin_geometry : Geometry :=
  {| arena_cap := 4; fan := 1; depth := 2 |}.

Definition demo_leaf_left : ENode nat_keys :=
  leaf_of nat_keys (cons (pair 1 10) (cons (pair 2 20) nil)).

Definition demo_leaf_right : ENode nat_keys :=
  leaf_of nat_keys (cons (pair 5 50) (cons (pair 7 70) nil)).

Definition demo_branch : ENode nat_keys :=
  branch_of nat_keys (cons 5 nil) (cons 0 (cons 1 nil)).

(* Addresses 0 and 1 are the leaves and address 2 is the root. *)
Definition demo_arena : Arena nat_keys :=
  cons demo_leaf_left (cons demo_leaf_right (cons demo_branch nil)).

(* A node that names itself as a child: whole, addressable, and no tree. *)
Definition cyclic_arena : Arena nat_keys :=
  cons (branch_of nat_keys (cons 5 nil) (cons 0 (cons 0 nil))) nil.

(* The skew: the demo tree's two leaves under their branch at address 2, a
   third leaf at address 3, and a root at address 4 holding the branch beside
   that bare leaf. Every key is in order, every node fits, every reference is
   inside the arena and the walk terminates, so `admitted`, `spans` and
   `node_fits_everywhere` all decide true; the leaf at address 3 nevertheless
   sits one level above the other two. This is why occupancy is not called
   balance in this file and why `at_depth` is a separate decision. *)
Definition skew_geometry : Geometry :=
  {| arena_cap := 16; fan := 2; depth := 4 |}.

Definition skew_arena : Arena nat_keys :=
  cons demo_leaf_left
  (cons demo_leaf_right
  (cons demo_branch
  (cons (leaf_of nat_keys (cons (pair 21 210) (cons (pair 22 220) nil)))
  (cons (branch_of nat_keys (cons 21 nil) (cons 2 (cons 3 nil))) nil)))).

Definition demo_probe (k v : nat)
  : option (prod (prod (Index nat_keys) nat) (prod bool nat)) :=
  match insert_root nat_keys demo_geometry demo_arena 1 None None 2 k v with
  | None => None
  | Some (pair ar (pair root height)) =>
      Some (pair (pair (flatten nat_keys ar height root) height)
                 (pair (admitted nat_keys demo_geometry ar height None None root)
                       (length ar)))
  end.

Definition demo_probe_lookup (k v q : nat) : option (option nat) :=
  match insert_root nat_keys demo_geometry demo_arena 1 None None 2 k v with
  | None => None
  | Some (pair ar (pair root height)) => Some (lookup nat_keys ar height root q)
  end.

(* The same inserts read for equal leaf depth: whether the published root's
   leaves share a depth at all, and the depth they share. *)
Definition demo_probe_depth (k v : nat) : option (prod bool bool) :=
  match insert_root nat_keys demo_geometry demo_arena 1 None None 2 k v with
  | None => None
  | Some (pair ar (pair root height)) =>
      Some (pair (leaves_share_one_depth nat_keys ar height root)
                 (at_depth nat_keys ar height root))
  end.

(* The skewed root put through the same write path: what `insert_root`
   re-decides is `admitted`, so the write is published and the skew survives
   it. The second column is the decision the check does not make. *)
Definition skew_probe (k v : nat) : option (prod bool bool) :=
  match insert_root nat_keys skew_geometry skew_arena 4 None None 4 k v with
  | None => None
  | Some (pair ar (pair root height)) =>
      Some (pair (admitted nat_keys skew_geometry ar height None None root)
                 (leaves_share_one_depth nat_keys ar height root))
  end.

Example the_demo_tree_is_admitted_fitting_and_read_back :
  admitted nat_keys demo_geometry demo_arena 1 None None 2 = true
  /\ node_fits_everywhere nat_keys demo_geometry demo_arena 1 2 = true
  /\ arena_ok nat_keys demo_geometry demo_arena = true
  /\ geometry_ok demo_geometry = true
  /\ flatten nat_keys demo_arena 1 2
     = cons (pair 1 10) (cons (pair 2 20) (cons (pair 5 50) (cons (pair 7 70) nil)))
  /\ lookup nat_keys demo_arena 1 2 5 = Some 50
  /\ lookup nat_keys demo_arena 1 2 4 = None :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl))))).

(* Both of the demo tree's leaves sit one level below its root, which is the
   hypothesis the preservation theorems above take. *)
Example the_demo_tree_keeps_its_leaves_at_one_depth :
  at_depth nat_keys demo_arena 1 2 = true
  /\ at_depth nat_keys demo_arena 0 2 = false
  /\ leaves_share_one_depth nat_keys demo_arena 1 2 = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* A leaf split promoting a separator, an internal split promoting a second,
   and a new root above both: the tree grows one level, answers the logical
   map's insert, and decides its own admission true. *)
Example an_insert_that_splits_to_a_new_root_stays_admitted :
  demo_probe 3 30
    = Some (pair (pair (ins nat_keys 3 30 (flatten nat_keys demo_arena 1 2)) 2)
                 (pair true 8))
  /\ demo_probe_lookup 3 30 3 = Some (Some 30)
  /\ demo_probe_lookup 3 30 7 = Some (Some 70)
  /\ demo_probe_lookup 3 30 4 = Some None :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The same insert at the right edge of the keyspace, which routes through
   the last child rather than the first. *)
Example an_insert_past_every_separator_stays_admitted :
  demo_probe 9 90
    = Some (pair (pair (ins nat_keys 9 90 (flatten nat_keys demo_arena 1 2)) 2)
                 (pair true 8))
  /\ demo_probe_lookup 9 90 9 = Some (Some 90) :=
  conj eq_refl eq_refl.

(* Replacement: one value changes, no key moves, no node splits, and the
   height is the one the tree already had. *)
Example a_replacement_changes_one_value_and_no_key :
  demo_probe 5 99
    = Some (pair (pair (ins nat_keys 5 99 (flatten nat_keys demo_arena 1 2)) 1)
                 (pair true 5))
  /\ demo_probe_lookup 5 99 5 = Some (Some 99)
  /\ demo_probe_lookup 5 99 7 = Some (Some 70) :=
  conj eq_refl (conj eq_refl eq_refl).

(* The same three inserts read for equal leaf depth. Each publishes a root
   whose leaves share one depth, and that depth is the height the call
   returned: two for the pair that split, one for the replacement, against the
   demo tree's own depth of one. This is the computed half of the preservation
   theorem above, whose arbitrary half is proved of any key algebra, geometry,
   arena, walk bound, subtree, key and value. *)
Example the_inserts_keep_the_leaves_at_one_depth :
  demo_probe_depth 3 30 = Some (pair true true)
  /\ demo_probe_depth 9 90 = Some (pair true true)
  /\ demo_probe_depth 5 99 = Some (pair true true) :=
  conj eq_refl (conj eq_refl eq_refl).

(* The skew, computed: `admitted`, `spans` and `node_fits_everywhere` all
   decide true on a tree one of whose leaves sits a level above the other two,
   and that tree answers a lookup. No depth is shared, at one level or at two
   or at any level the walk bound admits, so occupancy is not equal leaf depth
   and the name `node_fits_everywhere` is the one that holds. *)
Example a_skewed_tree_is_admitted_and_fits_yet_shares_no_leaf_depth :
  geometry_ok skew_geometry = true
  /\ arena_ok nat_keys skew_geometry skew_arena = true
  /\ admitted nat_keys skew_geometry skew_arena 4 None None 4 = true
  /\ spans nat_keys skew_arena 4 4 = true
  /\ node_fits_everywhere nat_keys skew_geometry skew_arena 4 4 = true
  /\ lookup nat_keys skew_arena 4 4 21 = Some 210
  /\ at_depth nat_keys skew_arena 1 4 = false
  /\ at_depth nat_keys skew_arena 2 4 = false
  /\ leaves_share_one_depth nat_keys skew_arena 4 4 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))).

(* And what the fail-closed check does with it, which is nothing: the write is
   published, `insert_root` re-decides `admitted` true on what it published,
   and the skew is still there. The preservation theorem above is therefore
   not a consequence of the check; it is a statement about an input whose
   leaves already share a depth, and this is the tree that shows the
   difference. *)
Example an_insert_does_not_repair_a_skewed_tree :
  skew_probe 22 220 = Some (pair true false)
  /\ skew_probe 3 30 = Some (pair true false) :=
  conj eq_refl eq_refl.

(* The four refusals, each decided by conversion: an arena whose declared
   capacity is already spent, an address outside the arena, a reference the
   walk bound does not reach, and a cycle among whole addressable
   nodes. The last is the case block completeness alone cannot decide, which
   is why the walk is bounded rather than merely total. *)
Example the_refusals_compute :
  insert_root nat_keys tight_geometry demo_arena 1 None None 2 3 30 = None
  /\ alloc nat_keys tight_geometry demo_arena demo_leaf_left = None
  /\ spans nat_keys demo_arena 1 9 = false
  /\ admitted nat_keys demo_geometry demo_arena 1 None None 9 = false
  /\ spans nat_keys demo_arena 0 2 = false
  /\ admitted nat_keys demo_geometry demo_arena 0 None None 2 = false
  /\ lookup nat_keys demo_arena 0 2 5 = None
  /\ spans nat_keys cyclic_arena 5 0 = false
  /\ admitted nat_keys demo_geometry cyclic_arena 5 None None 0 = false
  /\ geometry_ok thin_geometry = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))))).

(* R-05-166's decidable half: one closed inhabitant per record this file's
   statements range over. *)
Definition witness_Geometry : Geometry := demo_geometry.
Definition witness_ENode : ENode nat_keys := demo_branch.

(* =========================================================================
   R-05-163's assumption gate: every shipped constant's enumerated assumption
   set is compared against the declared set R-05-164 makes empty, so `Closed
   under the global context` is that emptiness checked mechanically.
   ========================================================================= *)

Print Assumptions halve.
Print Assumptions Geometry.
Print Assumptions geometry_ok.
Print Assumptions ENode.
Print Assumptions Arena.
Print Assumptions leaf_of.
Print Assumptions branch_of.
Print Assumptions alloc.
Print Assumptions key_lt.
Print Assumptions within.
Print Assumptions route.
Print Assumptions spans.
Print Assumptions node_fits.
Print Assumptions rising.
Print Assumptions chain.
Print Assumptions admitted.
Print Assumptions arena_ok.
Print Assumptions lookup.
Print Assumptions flatten.
Print Assumptions Grown.
Print Assumptions splice.
Print Assumptions publish_leaf.
Print Assumptions publish_branch.
Print Assumptions insert.
Print Assumptions flatten_grown.
Print Assumptions lookup_grown.
Print Assumptions admitted_grown.
Print Assumptions insert_checked.
Print Assumptions insert_root.
Print Assumptions node_fits_everywhere.
Print Assumptions at_depth.
Print Assumptions leaves_share_one_depth.
Print Assumptions an_insert_only_appends.
Print Assumptions a_retained_root_survives_a_later_insert.
Print Assumptions lookup_answers_the_logical_map.
Print Assumptions an_insert_publishes_spanning_nodes.
Print Assumptions an_insert_represents_the_logical_map.
Print Assumptions a_checked_insert_publishes_an_admitted_result.
Print Assumptions a_checked_insert_answers_the_logical_map.
Print Assumptions a_checked_root_insert_answers_the_logical_map.
Print Assumptions an_admitted_tree_fits_everywhere.
Print Assumptions an_insert_keeps_the_leaves_at_one_depth.
Print Assumptions a_checked_insert_keeps_the_leaves_at_one_depth.
Print Assumptions a_root_insert_keeps_the_leaves_at_one_depth.
Print Assumptions a_root_insert_keeps_one_leaf_depth.
Print Assumptions the_demo_tree_is_admitted_fitting_and_read_back.
Print Assumptions the_demo_tree_keeps_its_leaves_at_one_depth.
Print Assumptions an_insert_that_splits_to_a_new_root_stays_admitted.
Print Assumptions an_insert_past_every_separator_stays_admitted.
Print Assumptions a_replacement_changes_one_value_and_no_key.
Print Assumptions the_inserts_keep_the_leaves_at_one_depth.
Print Assumptions a_skewed_tree_is_admitted_and_fits_yet_shares_no_leaf_depth.
Print Assumptions an_insert_does_not_repair_a_skewed_tree.
Print Assumptions the_refusals_compute.
Print Assumptions witness_Geometry.
Print Assumptions witness_ENode.
