(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   StaticMemoryLaminar.v

   The laminar placement theorem of the static-memory research baseline
   (docs/implementation/static-memory-baseline.md, "A complete laminar
   special case"), mechanized. A companion to that research document and
   to MemoryPlan.v and part of neither: it changes no admission criterion,
   accepts no requirement, confers no landing credit, adds no field to
   MemoryPlan.v's Plan record and no axiom, and everything here is proved
   outright. It cites the entries the theorem argues from and carries no
   discharge annotation, because a result about an idealized model claims
   to answer no register entry.

   The model. An object is an identity, a weight (its charged contiguous
   extent) and a half-open reservation interval [lo, hi) over nat. A
   family is a list of objects; it is well formed when every weight is
   positive, every interval has lo < hi and the identities are distinct.
   The family is laminar when every pair of intervals is disjoint or one
   contains the other, equal intervals counting as nested. The charged
   load at an instant is the sum of the weights live then, and the load
   of a family is the maximum of that sum over the family's own start
   endpoints; `load_at_starts_suffices` shows the maximum over every
   instant is no larger. A placement is a function from identities to
   bases; it is feasible when every pair of distinct objects with
   overlapping intervals has disjoint extents [base, base + weight), and
   its span is the largest extent top. One arena at origin zero, unit
   alignment, every natural number a legal base, no pinning and no
   ownership, bank, guard or bounds constraint: these are the baseline
   theorem's premises and the whole of what the statements below assume.

   The construction. Order the family by start ascending, then end
   descending, then identity; `LexLt j i` is that order. Object i is
   placed at the total weight of the objects that precede it in that
   order and whose intervals contain its own, which is what "above its
   active ancestor stack" computes: a strict ancestor precedes every
   object it contains, and objects with equal intervals precede one
   another in identity order, so a group of equal intervals lands
   consecutively. The definition is a filtered sum over the family and
   neither sorts nor enumerates addresses. Agreement with the stack replay
   in tools/vos/static_memory_structure.py requires numeric identities
   to preserve the replay's string ordering; the concrete family below is
   its receipt's `equal-nested-disjoint` contract with that ordering. The
   agreement of that replay with this definition on every laminar family
   is not mechanized here; the concrete family is one point of it.

   The theorems. `construction_feasible`: on a well-formed laminar family
   the constructed placement is feasible. `construction_span_le_load`:
   the constructed span is at most the load, on any well-formed family,
   laminar or not. `feasible_span_ge_load`: every feasible placement
   spans at least the load, which is the simultaneous-load lower bound
   and needs no laminarity. Together, `construction_attains_load` and
   `laminar_optimum`: on a well-formed laminar family the construction is
   feasible with span exactly the load, and no feasible placement spans
   less, which is OPT = L under the premises above.

   The bridge. MemoryPlan.v states R-08-014's interference side condition
   as `NoInterference`, slot disjointness over overlapping live ranges
   (its reading 7), over a Plan whose regions carry R-08-011's
   `live_from`, `live_to` and `length_of`. `plan_family` reads those
   three fields over the regions below `region_count` as a family, and
   the three bridge theorems say: where that family is well formed and
   laminar, the constructed `Placement` satisfies `NoInterference` and
   its span is the family's load, and every `Placement` satisfying
   `NoInterference` spans at least that load. The bridge speaks to
   `NoInterference` and to nothing else the Plan carries: island
   containment, quantization, class placement and the placement-list
   charge are neither assumed nor concluded, and the constructed
   placement is not the plan's own `base_of`, about which nothing is
   said. The load is R-08-012's proven simultaneous peak; that the peak
   is the minimum any non-moving scheme can use is `feasible_span_ge_load`
   under this file's premises, and that a placement reaches it is proved
   here for laminar families only, which is the nested special case
   R-08-013 names and no wider claim.

   What is not proved here, and where it lives. That a source language's
   exported intervals are the actual reservation lifetimes of every
   admitted execution is the source-lifetime bridge the baseline names as
   open; the intervals here are inputs, as they are in MemoryPlan.v.
   Alignment, islands, quantization, pinning, multiple executions and any
   constraint beyond interference are outside the premises, and the
   baseline's small witnesses show each of them can break peak equality.
   Nothing here is a complexity result: R-08-013's polynomial-time clause
   is about an algorithm, and this file states a placement and proves its
   properties.

   Non-vacuity (R-05-165, R-05-166). `witness_Obj` inhabits the one
   record this file declares; the Plan the bridge quantifies over is
   inhabited by MemoryPlan.v's `witness_Plan`, whose own family is
   checked below to be well formed and laminar, so the bridge's
   hypotheses are satisfied by the companion's reference plan. A
   four-object laminar family has its bases, span and load computed by
   `vm_compute` and checked by reflexivity, and the general theorem is
   instantiated at it. A two-object crossing family is refused by the
   laminar predicate and the construction collides on it, so the premise
   excludes something and the feasibility theorem needs it. A padded
   placement of the laminar family is feasible with span above its load,
   so feasibility alone does not force the equality the theorem proves.
   And a seven-object crossing family, found by a scratch search and
   confirmed by `run.py static-memory compare` over an unshipped
   hand-written contract and mechanized here by finite
   case analysis, has an optimum strictly above its load: every placement
   whose bases lie below the load is enumerated and refused by
   computation, a completeness lemma places every placement of span at
   most the load in that enumeration, and a placement of span one above
   the load is exhibited. So the laminar premise is not decoration: its
   absence can cost, and the lower bound `feasible_span_ge_load` is not
   attained in general.

   The R-05-163 gate applies as to every artifact: the Print Assumptions
   block at the end reports every named theorem closed under the global
   context, and `run.py proofs` checks the same of every constant the
   module defines.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-165 R-05-166 R-08-011 R-08-012 R-08-013 R-08-014
   SHA256: 2c33529a46cb87a430553f6a374a6a0a2ddd2f2ef579515a841fc7b33c843d59
   (*| END derived |*)
   ========================================================================= *)

Require Import MemoryPlan.
From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.

(* -------------------------------------------------------------------------
   Objects, families and the interval predicates. Each predicate is stated
   as a Prop over nat and decided by a boolean twin, so a theorem is read
   in the Prop and a witness is computed in the boolean.
   ------------------------------------------------------------------------- *)

Record Obj : Type := {
  oid : nat;     (* identity *)
  weight : nat;  (* charged contiguous extent *)
  lo : nat;      (* reservation start, inclusive *)
  hi : nat       (* reservation end, exclusive *)
}.

Definition wf_obj (o : Obj) : bool :=
  andb (Nat.ltb 0 (weight o)) (Nat.ltb (lo o) (hi o)).

Fixpoint distinct_ids (f : list Obj) : bool :=
  match f with
  | [] => true
  | o :: r => andb (negb (existsb (fun j => Nat.eqb (oid j) (oid o)) r))
                   (distinct_ids r)
  end.

Definition family_ok (f : list Obj) : bool :=
  andb (forallb wf_obj f) (distinct_ids f).

Definition FamilyOk (f : list Obj) : Prop :=
  (forall o, In o f -> 0 < weight o /\ lo o < hi o) /\ NoDup (map oid f).

Definition Disjoint (i j : Obj) : Prop := hi i <= lo j \/ hi j <= lo i.
Definition Contains (j i : Obj) : Prop := lo j <= lo i /\ hi i <= hi j.
Definition Overlap (i j : Obj) : Prop := lo i < hi j /\ lo j < hi i.

Definition Laminar (f : list Obj) : Prop :=
  forall i j, In i f -> In j f -> Disjoint i j \/ Contains i j \/ Contains j i.

Definition disjoint_b (i j : Obj) : bool :=
  orb (Nat.leb (hi i) (lo j)) (Nat.leb (hi j) (lo i)).
Definition contains_b (j i : Obj) : bool :=
  andb (Nat.leb (lo j) (lo i)) (Nat.leb (hi i) (hi j)).
Definition overlap_b (i j : Obj) : bool :=
  andb (Nat.ltb (lo i) (hi j)) (Nat.ltb (lo j) (hi i)).
Definition pair_ok_b (i j : Obj) : bool :=
  orb (disjoint_b i j) (orb (contains_b i j) (contains_b j i)).
Definition laminar_b (f : list Obj) : bool :=
  forallb (fun i => forallb (fun j => pair_ok_b i j) f) f.

(* Closing a reflection goal after the comparisons have been case-split:
   the true side is arithmetic, the false side is a contradiction or a
   boolean mismatch. *)
Ltac refl_close :=
  split; intro H;
  [ first [ lia | exfalso; lia | discriminate ]
  | first [ reflexivity | exfalso; lia ] ].

Lemma disjoint_b_iff : forall i j, disjoint_b i j = true <-> Disjoint i j.
Proof.
  intros i j. unfold disjoint_b, Disjoint.
  destruct (Nat.leb_spec0 (hi i) (lo j)); destruct (Nat.leb_spec0 (hi j) (lo i));
    simpl; refl_close.
Qed.

Lemma contains_b_iff : forall j i, contains_b j i = true <-> Contains j i.
Proof.
  intros j i. unfold contains_b, Contains.
  destruct (Nat.leb_spec0 (lo j) (lo i)); destruct (Nat.leb_spec0 (hi i) (hi j));
    simpl; refl_close.
Qed.

Lemma overlap_b_iff : forall i j, overlap_b i j = true <-> Overlap i j.
Proof.
  intros i j. unfold overlap_b, Overlap.
  destruct (Nat.ltb_spec0 (lo i) (hi j)); destruct (Nat.ltb_spec0 (lo j) (hi i));
    simpl; refl_close.
Qed.

Lemma pair_ok_b_iff :
  forall i j, pair_ok_b i j = true <-> Disjoint i j \/ Contains i j \/ Contains j i.
Proof.
  intros i j. unfold pair_ok_b. split.
  - intro H. apply Bool.orb_true_iff in H. destruct H as [H | H].
    + left. apply disjoint_b_iff. exact H.
    + apply Bool.orb_true_iff in H. destruct H as [H | H]; right;
        [left | right]; apply contains_b_iff; exact H.
  - intro H. apply Bool.orb_true_iff. destruct H as [H | [H | H]].
    + left. apply disjoint_b_iff. exact H.
    + right. apply Bool.orb_true_iff. left. apply contains_b_iff. exact H.
    + right. apply Bool.orb_true_iff. right. apply contains_b_iff. exact H.
Qed.

Lemma laminar_b_iff : forall f, laminar_b f = true <-> Laminar f.
Proof.
  intros f. unfold laminar_b, Laminar. split.
  - intros H i j Hi Hj. apply pair_ok_b_iff.
    rewrite forallb_forall in H. specialize (H i Hi). cbv beta in H.
    rewrite forallb_forall in H. exact (H j Hj).
  - intros H. apply forallb_forall. intros i Hi. apply forallb_forall. intros j Hj.
    apply pair_ok_b_iff. exact (H i j Hi Hj).
Qed.

Lemma distinct_ids_nodup : forall f, distinct_ids f = true -> NoDup (map oid f).
Proof.
  induction f as [| o r IH]; simpl; intros H.
  - constructor.
  - apply Bool.andb_true_iff in H. destruct H as [H1 H2]. constructor.
    + intro Hin. apply in_map_iff in Hin. destruct Hin as [j [Hj Hjr]].
      assert (Hex : existsb (fun j => Nat.eqb (oid j) (oid o)) r = true).
      { apply existsb_exists. exists j. split; [exact Hjr | apply Nat.eqb_eq; exact Hj]. }
      rewrite Hex in H1. discriminate.
    + apply IH. exact H2.
Qed.

Lemma family_ok_sound : forall f, family_ok f = true -> FamilyOk f.
Proof.
  intros f H. apply Bool.andb_true_iff in H. destruct H as [H1 H2]. split.
  - intros o Ho. rewrite forallb_forall in H1. specialize (H1 o Ho). unfold wf_obj in H1.
    apply Bool.andb_true_iff in H1. destruct H1 as [Ha Hb].
    split; apply Nat.ltb_lt; assumption.
  - apply distinct_ids_nodup. exact H2.
Qed.

(* -------------------------------------------------------------------------
   Charged load, placements, feasibility and span.
   ------------------------------------------------------------------------- *)

Fixpoint wsum (l : list Obj) : nat :=
  match l with [] => 0 | o :: r => weight o + wsum r end.

Definition live_b (t : nat) (j : Obj) : bool :=
  andb (Nat.leb (lo j) t) (Nat.ltb t (hi j)).

Lemma live_b_iff : forall t j, live_b t j = true <-> lo j <= t /\ t < hi j.
Proof.
  intros t j. unfold live_b.
  destruct (Nat.leb_spec0 (lo j) t); destruct (Nat.ltb_spec0 t (hi j)); simpl; refl_close.
Qed.

Definition load_at (f : list Obj) (t : nat) : nat := wsum (filter (live_b t) f).

Fixpoint max_list (l : list nat) : nat :=
  match l with [] => 0 | x :: r => Nat.max x (max_list r) end.

(* The load: the maximum charged sum over the family's own start
   endpoints. `load_at_starts_suffices` below is what makes this the
   maximum over every instant. *)
Definition load (f : list Obj) : nat := max_list (map (fun i => load_at f (lo i)) f).

Definition ExtDisjoint (a : nat -> nat) (i j : Obj) : Prop :=
  a (oid i) + weight i <= a (oid j) \/ a (oid j) + weight j <= a (oid i).
Definition ext_disjoint_b (a : nat -> nat) (i j : Obj) : bool :=
  orb (Nat.leb (a (oid i) + weight i) (a (oid j)))
      (Nat.leb (a (oid j) + weight j) (a (oid i))).

(* The interference obligation of the baseline, and of MemoryPlan.v's
   `NoInterference`: distinct objects with overlapping intervals have
   disjoint extents. Nothing is asked of objects whose intervals do not
   overlap, which is the sharing the plan exists to permit. *)
Definition Feasible (f : list Obj) (a : nat -> nat) : Prop :=
  forall i j, In i f -> In j f -> oid i <> oid j -> Overlap i j -> ExtDisjoint a i j.
Definition feasible_b (f : list Obj) (a : nat -> nat) : bool :=
  forallb (fun i => forallb (fun j =>
    orb (Nat.eqb (oid i) (oid j))
        (orb (negb (overlap_b i j)) (ext_disjoint_b a i j))) f) f.

Definition span (f : list Obj) (a : nat -> nat) : nat :=
  max_list (map (fun i => a (oid i) + weight i) f).

Lemma ext_disjoint_b_iff :
  forall a i j, ext_disjoint_b a i j = true <-> ExtDisjoint a i j.
Proof.
  intros a i j. unfold ext_disjoint_b, ExtDisjoint.
  destruct (Nat.leb_spec0 (a (oid i) + weight i) (a (oid j)));
    destruct (Nat.leb_spec0 (a (oid j) + weight j) (a (oid i))); simpl; refl_close.
Qed.

Lemma feasible_b_sound : forall f a, feasible_b f a = true -> Feasible f a.
Proof.
  intros f a H i j Hi Hj Hne Hov. unfold feasible_b in H.
  rewrite forallb_forall in H. specialize (H i Hi). cbv beta in H.
  rewrite forallb_forall in H. specialize (H j Hj). cbv beta in H.
  apply Bool.orb_true_iff in H. destruct H as [H | H].
  - apply Nat.eqb_eq in H. contradiction.
  - apply Bool.orb_true_iff in H. destruct H as [H | H].
    + apply overlap_b_iff in Hov. rewrite Hov in H. discriminate.
    + apply ext_disjoint_b_iff. exact H.
Qed.

(* -------------------------------------------------------------------------
   The construction: the order, the ancestor predicate and the base.
   ------------------------------------------------------------------------- *)

(* Start ascending, then end descending, then identity. *)
Definition LexLt (j i : Obj) : Prop :=
  lo j < lo i \/ (lo j = lo i /\ (hi i < hi j \/ (hi j = hi i /\ oid j < oid i))).
Definition lex_lt_b (j i : Obj) : bool :=
  orb (Nat.ltb (lo j) (lo i))
      (andb (Nat.eqb (lo j) (lo i))
            (orb (Nat.ltb (hi i) (hi j))
                 (andb (Nat.eqb (hi j) (hi i)) (Nat.ltb (oid j) (oid i))))).

Lemma lex_lt_b_iff : forall j i, lex_lt_b j i = true <-> LexLt j i.
Proof.
  intros j i. unfold lex_lt_b, LexLt.
  destruct (Nat.ltb_spec0 (lo j) (lo i)); destruct (Nat.eqb_spec (lo j) (lo i));
    destruct (Nat.ltb_spec0 (hi i) (hi j)); destruct (Nat.eqb_spec (hi j) (hi i));
    destruct (Nat.ltb_spec0 (oid j) (oid i)); simpl; refl_close.
Qed.

(* j is on i's ancestor stack: it precedes i in the order and its interval
   contains i's. *)
Definition below_b (j i : Obj) : bool := andb (contains_b j i) (lex_lt_b j i).

Lemma below_b_iff : forall j i, below_b j i = true <-> Contains j i /\ LexLt j i.
Proof.
  intros j i. unfold below_b. split.
  - intro H. apply Bool.andb_true_iff in H. destruct H as [H1 H2].
    split; [apply contains_b_iff | apply lex_lt_b_iff]; assumption.
  - intros [H1 H2]. apply Bool.andb_true_iff.
    split; [apply contains_b_iff | apply lex_lt_b_iff]; assumption.
Qed.

Definition base (f : list Obj) (i : Obj) : nat :=
  wsum (filter (fun j => below_b j i) f).

(* The constructed placement, read by identity. *)
Definition build (f : list Obj) : nat -> nat :=
  fun id => match find (fun o => Nat.eqb (oid o) id) f with
            | Some i => base f i
            | None => 0
            end.

Lemma lexlt_irrefl : forall i, ~ LexLt i i.
Proof. unfold LexLt. intros i. lia. Qed.

Lemma lexlt_trans : forall j i k, LexLt j i -> LexLt i k -> LexLt j k.
Proof. unfold LexLt. intros. lia. Qed.

Lemma lexlt_total : forall i k, oid i <> oid k -> LexLt i k \/ LexLt k i.
Proof. unfold LexLt. intros. lia. Qed.

Lemma contains_trans : forall j i k, Contains j i -> Contains i k -> Contains j k.
Proof. unfold Contains. intros. lia. Qed.

Lemma overlap_sym : forall i k, Overlap i k -> Overlap k i.
Proof. unfold Overlap. intros. lia. Qed.

(* Two overlapping members of a laminar family lie on one ancestor chain,
   and the one the order places first is the one that contains the other. *)
Lemma overlap_laminar_lexlt_contains : forall i k,
  Overlap i k -> Disjoint i k \/ Contains i k \/ Contains k i -> LexLt i k -> Contains i k.
Proof. unfold Overlap, Disjoint, Contains, LexLt. intros. lia. Qed.

(* -------------------------------------------------------------------------
   List arithmetic.
   ------------------------------------------------------------------------- *)

Lemma wsum_app : forall l1 l2, wsum (l1 ++ l2) = wsum l1 + wsum l2.
Proof.
  induction l1 as [| o r IH]; intros l2; simpl; [reflexivity | rewrite IH; lia].
Qed.

Lemma wsum_filter_mono : forall (p q : Obj -> bool) (f : list Obj),
  (forall j, In j f -> p j = true -> q j = true) ->
  wsum (filter p f) <= wsum (filter q f).
Proof.
  intros p q f. induction f as [| o r IH]; intros H; simpl.
  - lia.
  - assert (IH' : wsum (filter p r) <= wsum (filter q r)).
    { apply IH. intros j Hj Hp. apply H; [right; exact Hj | exact Hp]. }
    destruct (p o) eqn:Ep.
    + rewrite (H o (or_introl eq_refl) Ep). simpl. lia.
    + destruct (q o); simpl; lia.
Qed.

Lemma wsum_filter_orb : forall (p q : Obj -> bool) (f : list Obj),
  (forall j, In j f -> p j = true -> q j = false) ->
  wsum (filter (fun j => orb (p j) (q j)) f) = wsum (filter p f) + wsum (filter q f).
Proof.
  intros p q f. induction f as [| o r IH]; intros H; simpl.
  - reflexivity.
  - assert (IH' : wsum (filter (fun j => orb (p j) (q j)) r)
                  = wsum (filter p r) + wsum (filter q r)).
    { apply IH. intros j Hj Hp. apply H; [right; exact Hj | exact Hp]. }
    destruct (p o) eqn:Ep.
    + rewrite (H o (or_introl eq_refl) Ep). simpl. lia.
    + destruct (q o); simpl; lia.
Qed.

Lemma filter_none : forall (p : Obj -> bool) (l : list Obj),
  (forall x, In x l -> p x = false) -> filter p l = [].
Proof.
  induction l as [| o r IH]; intros H; simpl; [reflexivity |].
  rewrite (H o (or_introl eq_refl)). apply IH. intros x Hx. apply H. right. exact Hx.
Qed.

Lemma max_list_ge : forall l x, In x l -> x <= max_list l.
Proof.
  induction l as [| y r IH]; intros x Hx; simpl.
  - destruct Hx.
  - destruct Hx as [Hx | Hx].
    + subst. apply Nat.le_max_l.
    + apply Nat.le_trans with (max_list r); [apply IH; exact Hx | apply Nat.le_max_r].
Qed.

Lemma max_list_le : forall l b, (forall x, In x l -> x <= b) -> max_list l <= b.
Proof.
  induction l as [| y r IH]; intros b H; simpl.
  - lia.
  - apply Nat.max_lub; [apply H; left; reflexivity |].
    apply IH. intros x Hx. apply H. right. exact Hx.
Qed.

Lemma exists_max_by : forall (key : Obj -> nat) (l : list Obj), l <> [] ->
  exists m, In m l /\ forall x, In x l -> key x <= key m.
Proof.
  intros key l. induction l as [| a r IH]; intros Hne.
  - exfalso. apply Hne. reflexivity.
  - destruct r as [| b r'].
    + exists a. split; [left; reflexivity |]. intros x [Hx | Hx]; [subst; lia | destruct Hx].
    + assert (Hne' : b :: r' <> []) by discriminate.
      destruct (IH Hne') as [m [Hm Hmax]].
      destruct (le_lt_dec (key m) (key a)) as [Hle | Hlt].
      * exists a. split; [left; reflexivity |].
        intros x [Hx | Hx]; [subst; lia | specialize (Hmax x Hx); lia].
      * exists m. split; [right; exact Hm |].
        intros x [Hx | Hx]; [subst; lia | exact (Hmax x Hx)].
Qed.

Lemma in_app_skip : forall (A : Type) (l1 l2 : list A) (m x : A),
  In x (l1 ++ l2) -> In x (l1 ++ m :: l2).
Proof.
  intros A l1 l2 m x H. apply in_app_or in H. apply in_or_app.
  destruct H as [H | H]; [left; exact H | right; right; exact H].
Qed.

(* -------------------------------------------------------------------------
   Identities.
   ------------------------------------------------------------------------- *)

Lemma oid_inj : forall f x y,
  NoDup (map oid f) -> In x f -> In y f -> oid x = oid y -> x = y.
Proof.
  induction f as [| o r IH]; intros x y Hnd Hx Hy Heq.
  - destruct Hx.
  - simpl in Hnd. apply NoDup_cons_iff in Hnd. destruct Hnd as [Hno Hnd].
    destruct Hx as [Hx | Hx]; destruct Hy as [Hy | Hy].
    + subst. reflexivity.
    + subst. exfalso. apply Hno. rewrite Heq. apply in_map. exact Hy.
    + subst. exfalso. apply Hno. rewrite <- Heq. apply in_map. exact Hx.
    + apply IH; assumption.
Qed.

Lemma filter_same_id : forall f i, NoDup (map oid f) -> In i f ->
  filter (fun j => Nat.eqb (oid j) (oid i)) f = [i].
Proof.
  induction f as [| o r IH]; intros i Hnd Hi.
  - destruct Hi.
  - simpl in Hnd. apply NoDup_cons_iff in Hnd. destruct Hnd as [Hno Hnd].
    simpl. destruct (Nat.eqb_spec (oid o) (oid i)) as [Heq | Hne].
    + assert (Hoi : o = i).
      { destruct Hi as [Hi | Hi]; [exact Hi |].
        exfalso. apply Hno. rewrite Heq. apply in_map. exact Hi. }
      subst. f_equal. apply filter_none. intros x Hx.
      apply Nat.eqb_neq. intro E. apply Hno. rewrite <- E. apply in_map. exact Hx.
    + destruct Hi as [Hi | Hi].
      * exfalso. apply Hne. rewrite Hi. reflexivity.
      * apply IH; assumption.
Qed.

Lemma find_own_id : forall f i, NoDup (map oid f) -> In i f ->
  find (fun o => Nat.eqb (oid o) (oid i)) f = Some i.
Proof.
  intros f i Hnd Hi.
  destruct (find (fun o => Nat.eqb (oid o) (oid i)) f) as [x |] eqn:E.
  - apply find_some in E. destruct E as [Hx Heq]. apply Nat.eqb_eq in Heq.
    f_equal. apply (oid_inj f); assumption.
  - pose proof (find_none _ _ E i Hi) as E'. cbv beta in E'.
    rewrite Nat.eqb_refl in E'. discriminate.
Qed.

Lemma build_base : forall f i, NoDup (map oid f) -> In i f -> build f (oid i) = base f i.
Proof. intros f i Hnd Hi. unfold build. rewrite (find_own_id f i Hnd Hi). reflexivity. Qed.

Lemma nodup_ids_filter : forall (p : Obj -> bool) (f : list Obj),
  NoDup (map oid f) -> NoDup (map oid (filter p f)).
Proof.
  intros p f. induction f as [| o r IH]; intros Hnd; simpl.
  - constructor.
  - simpl in Hnd. apply NoDup_cons_iff in Hnd. destruct Hnd as [Hno Hnd].
    destruct (p o); simpl.
    + constructor.
      * intro Hin. apply Hno. apply in_map_iff in Hin. destruct Hin as [x [Hx Hxin]].
        apply filter_In in Hxin. destruct Hxin as [Hxin _].
        rewrite <- Hx. apply in_map. exact Hxin.
      * apply IH. exact Hnd.
    + apply IH. exact Hnd.
Qed.

(* -------------------------------------------------------------------------
   The lower bound: objects with pairwise disjoint extents inside [0, bound)
   weigh at most bound. Induction on the object with the highest base.
   ------------------------------------------------------------------------- *)

Lemma packing : forall (n : nat) (l : list Obj) (a : nat -> nat) (bound : nat),
  length l <= n ->
  NoDup (map oid l) ->
  (forall j, In j l -> 0 < weight j) ->
  (forall j, In j l -> a (oid j) + weight j <= bound) ->
  (forall x y, In x l -> In y l -> oid x <> oid y -> ExtDisjoint a x y) ->
  wsum l <= bound.
Proof.
  induction n as [| n IH]; intros l a bound Hlen Hnd Hpos Hbound Hdis.
  - destruct l as [| o l0]; simpl in *; lia.
  - destruct l as [| o l0]; [simpl; lia |].
    assert (Hne : o :: l0 <> []) by discriminate.
    destruct (exists_max_by (fun j => a (oid j)) (o :: l0) Hne) as [m [Hm Hmax]].
    destruct (in_split m (o :: l0) Hm) as [l1 [l2 Heq]].
    rewrite Heq in *.
    assert (Hmid : In m (l1 ++ m :: l2)) by apply in_elt.
    rewrite map_app in Hnd. simpl in Hnd.
    assert (Hnd' : NoDup (map oid (l1 ++ l2))).
    { rewrite map_app. apply (NoDup_remove_1 _ _ _ Hnd). }
    assert (Hnotin : ~ In (oid m) (map oid (l1 ++ l2))).
    { rewrite map_app. apply (NoDup_remove_2 _ _ _ Hnd). }
    assert (Hrest : wsum (l1 ++ l2) <= a (oid m)).
    { apply (IH (l1 ++ l2) a (a (oid m))).
      - rewrite length_app in *. simpl in Hlen. lia.
      - exact Hnd'.
      - intros j Hj. apply Hpos. apply in_app_skip. exact Hj.
      - intros j Hj.
        assert (Hj' : In j (l1 ++ m :: l2)) by (apply in_app_skip; exact Hj).
        assert (Hneq : oid j <> oid m).
        { intro E. apply Hnotin. rewrite <- E. apply in_map. exact Hj. }
        destruct (Hdis j m Hj' Hmid Hneq) as [H1 | H1]; [exact H1 |].
        specialize (Hmax j Hj'). cbv beta in Hmax. specialize (Hpos m Hmid). lia.
      - intros x y Hx Hy Hxy. apply Hdis; try assumption; apply in_app_skip; assumption. }
    specialize (Hbound m Hmid).
    rewrite wsum_app in *. simpl. lia.
Qed.

Lemma feasible_load_at_le_span : forall f a t,
  FamilyOk f -> Feasible f a -> load_at f t <= span f a.
Proof.
  intros f a t [Hwf Hnd] Hfeas. unfold load_at.
  apply (packing (length (filter (live_b t) f)) (filter (live_b t) f) a (span f a)).
  - apply Nat.le_refl.
  - apply nodup_ids_filter. exact Hnd.
  - intros j Hj. apply filter_In in Hj. destruct Hj as [Hj _]. apply Hwf. exact Hj.
  - intros j Hj. apply filter_In in Hj. destruct Hj as [Hj _]. unfold span.
    apply max_list_ge. apply in_map_iff. exists j. split; [reflexivity | exact Hj].
  - intros x y Hx Hy Hxy. apply filter_In in Hx. apply filter_In in Hy.
    destruct Hx as [Hx Hlx]. destruct Hy as [Hy Hly].
    apply live_b_iff in Hlx. apply live_b_iff in Hly.
    apply Hfeas; try assumption. unfold Overlap. lia.
Qed.

(* -------------------------------------------------------------------------
   The load over start endpoints is the load over every instant.
   ------------------------------------------------------------------------- *)

Lemma load_at_lo_le_load : forall f i, In i f -> load_at f (lo i) <= load f.
Proof.
  intros f i Hi. unfold load. apply max_list_ge. apply in_map_iff.
  exists i. split; [reflexivity | exact Hi].
Qed.

Theorem load_at_starts_suffices : forall f t, load_at f t <= load f.
Proof.
  intros f t.
  destruct (filter (live_b t) f) as [| o l0] eqn:El.
  - unfold load_at. rewrite El. simpl. lia.
  - assert (Hne : filter (live_b t) f <> []) by (rewrite El; discriminate).
    destruct (exists_max_by lo (filter (live_b t) f) Hne) as [m [Hm Hmax]].
    apply filter_In in Hm. destruct Hm as [Hmf Hlm]. apply live_b_iff in Hlm.
    apply Nat.le_trans with (load_at f (lo m)).
    + unfold load_at. apply wsum_filter_mono. intros j Hj Hlj.
      assert (Hjf : In j (filter (live_b t) f)) by (apply filter_In; split; assumption).
      specialize (Hmax j Hjf). apply live_b_iff in Hlj. apply live_b_iff. lia.
    + apply load_at_lo_le_load. exact Hmf.
Qed.

(* -------------------------------------------------------------------------
   The construction's two bounds.
   ------------------------------------------------------------------------- *)

(* An object's extent top is the weight of its ancestor stack and itself. *)
Lemma base_top_eq : forall f i, NoDup (map oid f) -> In i f ->
  base f i + weight i
  = wsum (filter (fun j => orb (below_b j i) (Nat.eqb (oid j) (oid i))) f).
Proof.
  intros f i Hnd Hi. unfold base.
  assert (Hsplit := wsum_filter_orb (fun j => below_b j i)
                                    (fun j => Nat.eqb (oid j) (oid i)) f).
  cbv beta in Hsplit. rewrite Hsplit.
  - rewrite (filter_same_id f i Hnd Hi). simpl. lia.
  - intros j Hj Hb. apply below_b_iff in Hb. destruct Hb as [_ Hb].
    destruct (Nat.eqb_spec (oid j) (oid i)) as [Heq | Hne]; [| reflexivity].
    exfalso. assert (Hji : j = i) by (apply (oid_inj f); assumption).
    subst. apply (lexlt_irrefl i). exact Hb.
Qed.

(* Feasibility's core: an object's stack, and the object itself, sit on the
   stack of every object it contains and precedes. *)
Lemma base_step : forall f i k,
  FamilyOk f -> In i f -> In k f -> Contains i k -> LexLt i k ->
  base f i + weight i <= base f k.
Proof.
  intros f i k [Hwf Hnd] Hi Hk Hc Hl.
  rewrite (base_top_eq f i Hnd Hi). unfold base.
  apply wsum_filter_mono. intros j Hj Hb. apply Bool.orb_true_iff in Hb. apply below_b_iff.
  destruct Hb as [Hb | Hb].
  - apply below_b_iff in Hb. destruct Hb as [Hc' Hl']. split.
    + exact (contains_trans j i k Hc' Hc).
    + exact (lexlt_trans j i k Hl' Hl).
  - apply Nat.eqb_eq in Hb. assert (Hji : j = i) by (apply (oid_inj f); assumption).
    subst. split; assumption.
Qed.

Theorem construction_feasible : forall f, FamilyOk f -> Laminar f -> Feasible f (build f).
Proof.
  intros f Hok Hlam i k Hi Hk Hne Hov.
  destruct Hok as [Hwf Hnd].
  unfold ExtDisjoint. rewrite (build_base f i Hnd Hi). rewrite (build_base f k Hnd Hk).
  destruct (lexlt_total i k Hne) as [Hl | Hl].
  - left. apply (base_step f i k (conj Hwf Hnd) Hi Hk); [| exact Hl].
    exact (overlap_laminar_lexlt_contains i k Hov (Hlam i k Hi Hk) Hl).
  - right. apply (base_step f k i (conj Hwf Hnd) Hk Hi); [| exact Hl].
    exact (overlap_laminar_lexlt_contains k i (overlap_sym i k Hov) (Hlam k i Hk Hi) Hl).
Qed.

(* The span bound: every object on i's stack is live at i's start, and so
   is i, so the extent top is at most the load there. Laminarity is not
   used. *)
Lemma base_top_le_load_at : forall f i,
  FamilyOk f -> In i f -> base f i + weight i <= load_at f (lo i).
Proof.
  intros f i [Hwf Hnd] Hi. rewrite (base_top_eq f i Hnd Hi). unfold load_at.
  apply wsum_filter_mono. intros j Hj Hb. apply live_b_iff.
  destruct (Hwf i Hi) as [_ Hii].
  apply Bool.orb_true_iff in Hb. destruct Hb as [Hb | Hb].
  - apply below_b_iff in Hb. destruct Hb as [[Hc1 Hc2] _]. lia.
  - apply Nat.eqb_eq in Hb. assert (Hji : j = i) by (apply (oid_inj f); assumption).
    subst. lia.
Qed.

Theorem construction_span_le_load : forall f, FamilyOk f -> span f (build f) <= load f.
Proof.
  intros f Hok. unfold span. apply max_list_le. intros x Hx.
  apply in_map_iff in Hx. destruct Hx as [i [Hxi Hi]]. subst x.
  assert (Hnd : NoDup (map oid f)) by (destruct Hok; assumption).
  rewrite (build_base f i Hnd Hi).
  apply Nat.le_trans with (load_at f (lo i)).
  - apply base_top_le_load_at; assumption.
  - apply load_at_lo_le_load. exact Hi.
Qed.

(* -------------------------------------------------------------------------
   The theorem: OPT = L on a well-formed laminar family.
   ------------------------------------------------------------------------- *)

Theorem feasible_span_ge_load : forall f a, FamilyOk f -> Feasible f a -> load f <= span f a.
Proof.
  intros f a Hok Hfeas. unfold load. apply max_list_le. intros x Hx.
  apply in_map_iff in Hx. destruct Hx as [i [Hxi Hi]]. subst x.
  apply feasible_load_at_le_span; assumption.
Qed.

Theorem construction_attains_load : forall f,
  FamilyOk f -> Laminar f -> span f (build f) = load f.
Proof.
  intros f Hok Hlam. apply Nat.le_antisymm.
  - apply construction_span_le_load. exact Hok.
  - apply feasible_span_ge_load; [exact Hok | apply construction_feasible; assumption].
Qed.

Theorem laminar_optimum : forall f a,
  FamilyOk f -> Laminar f -> Feasible f a -> span f (build f) <= span f a.
Proof.
  intros f a Hok Hlam Hfeas. rewrite (construction_attains_load f Hok Hlam).
  apply feasible_span_ge_load; assumption.
Qed.

(* -------------------------------------------------------------------------
   The bridge to MemoryPlan.v: a Plan's (live_from, live_to, length_of)
   family over the regions below region_count, and NoInterference.
   ------------------------------------------------------------------------- *)

Definition region_obj (p : Plan) (r : nat) : Obj :=
  {| oid := r; weight := p.(length_of) r; lo := p.(live_from) r; hi := p.(live_to) r |}.

Definition plan_family (p : Plan) : list Obj := map (region_obj p) (upto p.(region_count)).

(* Positive lengths and nonempty live ranges below the roster count. *)
Definition PlanFamilyOk (p : Plan) : Prop :=
  forall r, r < p.(region_count) -> 0 < p.(length_of) r /\ p.(live_from) r < p.(live_to) r.

Definition plan_placement (p : Plan) : Placement := build (plan_family p).

Lemma In_upto : forall n r, In r (upto n) <-> r < n.
Proof.
  induction n as [| n IH]; intros r; simpl.
  - split; [intros [] | lia].
  - split.
    + intros H. apply in_app_or in H. destruct H as [H | [H | []]].
      * apply IH in H. lia.
      * lia.
    + intros H. apply in_or_app. destruct (Nat.eq_dec r n) as [E | Hne].
      * right. left. symmetry. exact E.
      * left. apply IH. lia.
Qed.

Lemma NoDup_app_single : forall (l : list nat) (x : nat),
  NoDup l -> ~ In x l -> NoDup (l ++ [x]).
Proof.
  induction l as [| y r IH]; intros x Hnd Hnin; simpl.
  - constructor; [intros [] | constructor].
  - apply NoDup_cons_iff in Hnd. destruct Hnd as [Hy Hr]. constructor.
    + intro H. apply in_app_or in H. destruct H as [H | [H | []]].
      * apply Hy. exact H.
      * apply Hnin. left. symmetry. exact H.
    + apply IH; [exact Hr |]. intro H. apply Hnin. right. exact H.
Qed.

Lemma NoDup_upto : forall n, NoDup (upto n).
Proof.
  induction n as [| n IH]; simpl.
  - constructor.
  - apply NoDup_app_single; [exact IH |]. intro H. apply In_upto in H. lia.
Qed.

Lemma plan_family_ids : forall p, map oid (plan_family p) = upto p.(region_count).
Proof. intros p. unfold plan_family. rewrite map_map. simpl. apply map_id. Qed.

Lemma plan_family_in : forall p i,
  In i (plan_family p) <-> exists r, r < p.(region_count) /\ i = region_obj p r.
Proof.
  intros p i. unfold plan_family. rewrite in_map_iff. split.
  - intros [r [Hr Hin]]. exists r. split; [apply In_upto; exact Hin | symmetry; exact Hr].
  - intros [r [Hr Hi]]. exists r. split; [symmetry; exact Hi | apply In_upto; exact Hr].
Qed.

Lemma plan_family_ok : forall p, PlanFamilyOk p -> FamilyOk (plan_family p).
Proof.
  intros p H. split.
  - intros o Ho. apply plan_family_in in Ho. destruct Ho as [r [Hr Ho]]. subst o.
    simpl. apply H. exact Hr.
  - rewrite plan_family_ids. apply NoDup_upto.
Qed.

Lemma plan_family_ok_inv : forall p, FamilyOk (plan_family p) -> PlanFamilyOk p.
Proof.
  intros p [Hwf _] r Hr. apply (Hwf (region_obj p r)).
  apply plan_family_in. exists r. split; [exact Hr | reflexivity].
Qed.

Lemma live_overlap_iff : forall p r s,
  live_overlap p r s = true <-> Overlap (region_obj p r) (region_obj p s).
Proof.
  intros p r s.
  change (live_overlap p r s) with (overlap_b (region_obj p r) (region_obj p s)).
  apply overlap_b_iff.
Qed.

Lemma slots_disjoint_iff : forall p place r s,
  slots_disjoint p place r s = true <-> ExtDisjoint place (region_obj p r) (region_obj p s).
Proof.
  intros p place r s.
  change (slots_disjoint p place r s)
    with (ext_disjoint_b place (region_obj p r) (region_obj p s)).
  apply ext_disjoint_b_iff.
Qed.

Theorem laminar_plan_does_not_interfere : forall p : Plan,
  PlanFamilyOk p -> Laminar (plan_family p) -> NoInterference p (plan_placement p).
Proof.
  intros p Hok Hlam r s Hr Hs Hne Hov.
  apply Nat.ltb_lt in Hr. apply Nat.ltb_lt in Hs. apply Nat.eqb_neq in Hne.
  apply live_overlap_iff in Hov. apply slots_disjoint_iff.
  apply (construction_feasible (plan_family p) (plan_family_ok p Hok) Hlam).
  - apply plan_family_in. exists r. split; [exact Hr | reflexivity].
  - apply plan_family_in. exists s. split; [exact Hs | reflexivity].
  - simpl. exact Hne.
  - exact Hov.
Qed.

Theorem laminar_plan_attains_load : forall p : Plan,
  PlanFamilyOk p -> Laminar (plan_family p) ->
  span (plan_family p) (plan_placement p) = load (plan_family p).
Proof.
  intros p Hok Hlam. apply construction_attains_load; [apply plan_family_ok; exact Hok | exact Hlam].
Qed.

Theorem no_interference_spans_load : forall (p : Plan) (place : Placement),
  PlanFamilyOk p -> NoInterference p place ->
  load (plan_family p) <= span (plan_family p) place.
Proof.
  intros p place Hok Hni. apply feasible_span_ge_load; [apply plan_family_ok; exact Hok |].
  intros i k Hi Hk Hne Hov.
  apply plan_family_in in Hi. apply plan_family_in in Hk.
  destruct Hi as [r [Hr Hi]]. destruct Hk as [s [Hs Hk]]. subst i k.
  apply slots_disjoint_iff. apply Hni.
  - apply Nat.ltb_lt. exact Hr.
  - apply Nat.ltb_lt. exact Hs.
  - apply Nat.eqb_neq. simpl in Hne. exact Hne.
  - apply live_overlap_iff. exact Hov.
Qed.

(* -------------------------------------------------------------------------
   Non-vacuity (R-05-165, R-05-166).
   ------------------------------------------------------------------------- *)

(* The receipt's `equal-nested-disjoint` contract, with numeric identities
   in the receipt's identity order (equal, left, outer, right) and the
   list written in the contract's own order rather than the construction's. *)
Definition o_equal : Obj := {| oid := 0; weight := 3; lo := 0; hi := 10 |}.
Definition o_left  : Obj := {| oid := 1; weight := 4; lo := 1; hi := 4 |}.
Definition o_outer : Obj := {| oid := 2; weight := 2; lo := 0; hi := 10 |}.
Definition o_right : Obj := {| oid := 3; weight := 6; lo := 4; hi := 9 |}.
Definition demo_family : list Obj := [o_outer; o_equal; o_left; o_right].

Definition witness_Obj : Obj := o_outer.

Example demo_family_is_well_formed : family_ok demo_family = true.
Proof. vm_compute. reflexivity. Qed.

Example demo_family_is_laminar : laminar_b demo_family = true.
Proof. vm_compute. reflexivity. Qed.

(* The two equal intervals nest in identity order, so equal sits at the
   origin and outer directly above it; left and right share the addresses
   above the group because their intervals are disjoint. *)
Example demo_bases_computed :
  map (fun i => (oid i, build demo_family (oid i))) demo_family
  = [(2, 3); (0, 0); (1, 5); (3, 5)].
Proof. vm_compute. reflexivity. Qed.

Example demo_loads_at_starts : map (load_at demo_family) [0; 1; 4] = [5; 9; 11].
Proof. vm_compute. reflexivity. Qed.

Example demo_load_computed : load demo_family = 11.
Proof. vm_compute. reflexivity. Qed.

Example demo_span_computed : span demo_family (build demo_family) = 11.
Proof. vm_compute. reflexivity. Qed.

Example demo_construction_is_feasible : feasible_b demo_family (build demo_family) = true.
Proof. vm_compute. reflexivity. Qed.

(* The general theorem instantiated at the family whose hypotheses were
   decided above. *)
Lemma demo_family_attains_its_load : span demo_family (build demo_family) = load demo_family.
Proof.
  apply construction_attains_load.
  - apply family_ok_sound. exact demo_family_is_well_formed.
  - apply laminar_b_iff. exact demo_family_is_laminar.
Qed.

(* The distinguishing instance for the laminar premise: two crossing
   intervals. The predicate refuses the family, and the construction, which
   places neither above the other because neither contains the other,
   collides on it. *)
Definition o_cross_a : Obj := {| oid := 0; weight := 1; lo := 0; hi := 2 |}.
Definition o_cross_b : Obj := {| oid := 1; weight := 1; lo := 1; hi := 3 |}.
Definition crossing_family : list Obj := [o_cross_a; o_cross_b].

Example crossing_family_is_well_formed : family_ok crossing_family = true.
Proof. vm_compute. reflexivity. Qed.

Example crossing_family_is_refused : laminar_b crossing_family = false.
Proof. vm_compute. reflexivity. Qed.

Example crossing_construction_collides :
  feasible_b crossing_family (build crossing_family) = false.
Proof. vm_compute. reflexivity. Qed.

Lemma crossing_family_is_not_laminar : ~ Laminar crossing_family.
Proof.
  intro H. apply laminar_b_iff in H. rewrite crossing_family_is_refused in H. discriminate.
Qed.

(* Feasibility alone does not force the load: the laminar family shifted up
   by one unit is still feasible and spans one more than its load. *)
Definition padded_placement : nat -> nat := fun id => S (build demo_family id).

Example padded_placement_is_feasible : feasible_b demo_family padded_placement = true.
Proof. vm_compute. reflexivity. Qed.

Example padded_span_computed : span demo_family padded_placement = 12.
Proof. vm_compute. reflexivity. Qed.

Lemma feasibility_does_not_force_the_load :
  Feasible demo_family padded_placement
  /\ load demo_family < span demo_family padded_placement.
Proof.
  split.
  - apply feasible_b_sound. exact padded_placement_is_feasible.
  - rewrite demo_load_computed, padded_span_computed. lia.
Qed.

(* The companion's reference plan satisfies the bridge's hypotheses: its
   eight regions carry positive lengths and nonempty live ranges, and the
   two ranges that are not the whole horizon are disjoint from each other
   and nested in it. The constructed placement passes MemoryPlan.v's own
   colouring check, decided by computation, and its span is the load. *)
Example demo_plan_family_is_well_formed : family_ok (plan_family demo_plan) = true.
Proof. vm_compute. reflexivity. Qed.

Example demo_plan_family_is_laminar : laminar_b (plan_family demo_plan) = true.
Proof. vm_compute. reflexivity. Qed.

Example demo_plan_construction_colours : colouring_ok demo_plan (plan_placement demo_plan) = true.
Proof. vm_compute. reflexivity. Qed.

Example demo_plan_load_computed : load (plan_family demo_plan) = 2272.
Proof. vm_compute. reflexivity. Qed.

Example demo_plan_span_computed :
  span (plan_family demo_plan) (plan_placement demo_plan) = 2272.
Proof. vm_compute. reflexivity. Qed.

Lemma demo_plan_satisfies_the_bridge_hypotheses :
  PlanFamilyOk demo_plan /\ Laminar (plan_family demo_plan).
Proof.
  split.
  - apply plan_family_ok_inv. apply family_ok_sound. exact demo_plan_family_is_well_formed.
  - apply laminar_b_iff. exact demo_plan_family_is_laminar.
Qed.

(* -------------------------------------------------------------------------
   A crossing family whose optimum exceeds its load. Seven objects with
   identities equal to their positions, load five, and no feasible
   placement of span five: the bases of any such placement would lie below
   the load, every such tuple is enumerated, and each is refused. The
   contract was found by a scratch search and confirmed by `run.py
   static-memory compare`, whose exhaustive search reports the same
   verdict; the receipt is not quoted here, the computation is repeated.
   ------------------------------------------------------------------------- *)

Definition g0 : Obj := {| oid := 0; weight := 1; lo := 2; hi := 4 |}.
Definition g1 : Obj := {| oid := 1; weight := 2; lo := 3; hi := 5 |}.
Definition g2 : Obj := {| oid := 2; weight := 2; lo := 4; hi := 6 |}.
Definition g3 : Obj := {| oid := 3; weight := 1; lo := 2; hi := 5 |}.
Definition g4 : Obj := {| oid := 4; weight := 3; lo := 5; hi := 6 |}.
Definition g5 : Obj := {| oid := 5; weight := 3; lo := 0; hi := 3 |}.
Definition g6 : Obj := {| oid := 6; weight := 2; lo := 1; hi := 2 |}.
Definition gap_family : list Obj := [g0; g1; g2; g3; g4; g5; g6].

Example gap_family_is_well_formed : family_ok gap_family = true.
Proof. vm_compute. reflexivity. Qed.

Example gap_family_is_refused : laminar_b gap_family = false.
Proof. vm_compute. reflexivity. Qed.

Example gap_family_load_computed : load gap_family = 5.
Proof. vm_compute. reflexivity. Qed.

(* Every tuple whose k-th entry is at most the k-th bound. *)
Fixpoint tuples (bounds : list nat) : list (list nat) :=
  match bounds with
  | [] => [[]]
  | b :: rest => flat_map (fun x => map (fun t => x :: t) (tuples rest)) (seq 0 (S b))
  end.

Definition from_tuple (t : list nat) : nat -> nat := fun id => nth id t 0.

(* The load less each weight: the highest base a placement of span at most
   the load can give each object. *)
Definition gap_bounds : list nat := [4; 3; 3; 4; 2; 2; 3].

Example no_gap_placement_spans_the_load :
  forallb (fun t => negb (feasible_b gap_family (from_tuple t))) (tuples gap_bounds) = true.
Proof. vm_compute. reflexivity. Qed.

Lemma tuples_complete : forall bounds t,
  length t = length bounds ->
  (forall k, k < length bounds -> nth k t 0 <= nth k bounds 0) ->
  In t (tuples bounds).
Proof.
  induction bounds as [| b rest IH]; intros t Hlen Hb.
  - destruct t; [left; reflexivity | discriminate Hlen].
  - destruct t as [| x t']; [discriminate Hlen |].
    change (tuples (b :: rest))
      with (flat_map (fun x => map (fun t => x :: t) (tuples rest)) (seq 0 (S b))).
    apply in_flat_map. exists x. split.
    + apply in_seq. pose proof (Hb 0 ltac:(simpl; lia)) as H0. simpl in H0. lia.
    + apply (in_map (fun t => x :: t) (tuples rest) t'). apply IH.
      * simpl in Hlen. lia.
      * intros k Hk. pose proof (Hb (S k) ltac:(simpl; lia)) as Hk'. simpl in Hk'. exact Hk'.
Qed.

Lemma forallb_congr : forall (A : Type) (p q : A -> bool) (l : list A),
  (forall x, In x l -> p x = q x) -> forallb p l = forallb q l.
Proof.
  intros A p q l H. induction l as [| x r IH]; simpl; [reflexivity |].
  rewrite (H x (or_introl eq_refl)). rewrite IH; [reflexivity |].
  intros y Hy. apply H. right. exact Hy.
Qed.

(* The check reads a placement only at the family's own identities. *)
Lemma feasible_b_ext : forall f a a',
  (forall i, In i f -> a (oid i) = a' (oid i)) -> feasible_b f a = feasible_b f a'.
Proof.
  intros f a a' H. unfold feasible_b. apply forallb_congr. intros i Hi. cbv beta.
  apply forallb_congr. intros j Hj. cbv beta. unfold ext_disjoint_b.
  rewrite (H i Hi). rewrite (H j Hj). reflexivity.
Qed.

Lemma feasible_b_complete : forall f a, Feasible f a -> feasible_b f a = true.
Proof.
  intros f a H. unfold feasible_b. apply forallb_forall. intros i Hi. cbv beta.
  apply forallb_forall. intros j Hj. cbv beta.
  destruct (Nat.eqb_spec (oid i) (oid j)) as [E | Hne]; [reflexivity |]. simpl.
  destruct (overlap_b i j) eqn:Eo; simpl; [| reflexivity].
  apply ext_disjoint_b_iff. apply H; try assumption. apply overlap_b_iff. exact Eo.
Qed.

Definition gap_tuple (a : nat -> nat) : list nat := map (fun i => a (oid i)) gap_family.

Lemma gap_tuple_reads_back : forall a i,
  In i gap_family -> from_tuple (gap_tuple a) (oid i) = a (oid i).
Proof.
  intros a i Hi. simpl in Hi.
  repeat (destruct Hi as [Hi | Hi]; [subst; reflexivity |]). destruct Hi.
Qed.

Lemma gap_tuple_bounded : forall a, span gap_family a <= 5 ->
  length (gap_tuple a) = length gap_bounds
  /\ forall k, k < length gap_bounds -> nth k (gap_tuple a) 0 <= nth k gap_bounds 0.
Proof.
  intros a Hspan.
  assert (Hb : forall i, In i gap_family -> a (oid i) + weight i <= 5).
  { intros i Hi. apply Nat.le_trans with (span gap_family a); [| exact Hspan].
    unfold span. apply max_list_ge. apply in_map_iff. exists i. split; [reflexivity | exact Hi]. }
  pose proof (Hb g0 (or_introl eq_refl)) as H0.
  pose proof (Hb g1 (or_intror (or_introl eq_refl))) as H1.
  pose proof (Hb g2 (or_intror (or_intror (or_introl eq_refl)))) as H2.
  pose proof (Hb g3 (or_intror (or_intror (or_intror (or_introl eq_refl))))) as H3.
  pose proof (Hb g4 (or_intror (or_intror (or_intror (or_intror (or_introl eq_refl)))))) as H4.
  pose proof (Hb g5 (or_intror (or_intror (or_intror (or_intror (or_intror
                        (or_introl eq_refl))))))) as H5.
  pose proof (Hb g6 (or_intror (or_intror (or_intror (or_intror (or_intror (or_intror
                        (or_introl eq_refl)))))))) as H6.
  cbv [oid weight g0 g1 g2 g3 g4 g5 g6] in H0, H1, H2, H3, H4, H5, H6.
  split; [reflexivity |].
  intros k Hk. simpl in Hk.
  destruct k as [| [| [| [| [| [| [| k]]]]]]]; simpl; lia.
Qed.

Theorem gap_family_needs_more_than_its_load :
  forall a, Feasible gap_family a -> 6 <= span gap_family a.
Proof.
  intros a Hfeas.
  destruct (le_lt_dec 6 (span gap_family a)) as [Hle | Hlt]; [exact Hle |].
  exfalso.
  assert (Hspan : span gap_family a <= 5) by lia.
  destruct (gap_tuple_bounded a Hspan) as [Hlen Hbnd].
  assert (Hin : In (gap_tuple a) (tuples gap_bounds)) by (apply tuples_complete; assumption).
  pose proof (proj1 (forallb_forall _ _) no_gap_placement_spans_the_load (gap_tuple a) Hin)
    as Hno.
  cbv beta in Hno.
  assert (Hf : feasible_b gap_family (from_tuple (gap_tuple a)) = true).
  { rewrite (feasible_b_ext gap_family (from_tuple (gap_tuple a)) a).
    - apply feasible_b_complete. exact Hfeas.
    - intros i Hi. apply gap_tuple_reads_back. exact Hi. }
  rewrite Hf in Hno. discriminate.
Qed.

(* And one unit above the load is attained, so the optimum is exactly six. *)
Definition gap_placement : nat -> nat := from_tuple [4; 1; 3; 0; 0; 1; 4].

Example gap_placement_is_feasible : feasible_b gap_family gap_placement = true.
Proof. vm_compute. reflexivity. Qed.

Example gap_placement_span_computed : span gap_family gap_placement = 6.
Proof. vm_compute. reflexivity. Qed.

Theorem gap_family_optimum_exceeds_its_load :
  Feasible gap_family gap_placement
  /\ span gap_family gap_placement = load gap_family + 1
  /\ forall a, Feasible gap_family a -> load gap_family + 1 <= span gap_family a.
Proof.
  rewrite gap_family_load_computed. split; [| split].
  - apply feasible_b_sound. exact gap_placement_is_feasible.
  - exact gap_placement_span_computed.
  - intros a Ha. exact (gap_family_needs_more_than_its_load a Ha).
Qed.

(* -------------------------------------------------------------------------
   The R-05-163 gate: every theorem closed under the global context.
   ------------------------------------------------------------------------- *)

Print Assumptions load_at_starts_suffices.
Print Assumptions construction_feasible.
Print Assumptions construction_span_le_load.
Print Assumptions feasible_span_ge_load.
Print Assumptions construction_attains_load.
Print Assumptions laminar_optimum.
Print Assumptions laminar_plan_does_not_interfere.
Print Assumptions laminar_plan_attains_load.
Print Assumptions no_interference_spans_load.
Print Assumptions demo_family_attains_its_load.
Print Assumptions crossing_family_is_not_laminar.
Print Assumptions feasibility_does_not_force_the_load.
Print Assumptions demo_plan_satisfies_the_bridge_hypotheses.
Print Assumptions gap_family_needs_more_than_its_load.
Print Assumptions gap_family_optimum_exceeds_its_load.
