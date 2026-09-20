(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ModuleFormats.v: Q24c's canonical manifest and proof-certificate formats.

   The subject is ModuleAdmission.v's Manifest record and the certificate
   container that carries it, stated over the entries that own them:
   R-12-085g's one canonical manifest per admitted design, carried with the
   certificate transport as a bounded non-recursive record format with
   explicit total byte and field limits, which R-05-042's inventory and
   R-05-046's derivation rule own as descriptors; R-05-051a's canonicity
   theorem for a descriptor whose encoding is an input to a name or an
   equality test, with R-05-051b's no-slack rule and R-05-051c's refusal to
   give that role to a descriptor carrying no such theorem; R-12-085h's
   design admission against host-selected propositions, permitted
   assumptions and checker/profile versions inside R-06-015a's predeclared
   bounds; R-04-010b's reading that manifest and proof bytes are data and
   not an option ROM; and the scope R-12-085f, R-12-085l and R-15-228h keep
   for every artifact this file does not author.

   What this file is. One wire format written twice over, as a serializer
   and as a parser. Both are total functions into `option`: every refusal is
   an explicit `None`, no input reaches a default, and no fuel argument
   escapes into a statement. Parsing a serialized value returns that value,
   and serializing a parsed byte string returns that byte string. Those are
   R-05-051a's two directions, and the second is the one that makes a
   manifest an identity rather than one of several, because it gives each
   value exactly one admissible encoding.

   The format. A byte is a natural below the declared radix. A numeral is a
   digit-count byte followed by that many least-significant-first digits, in
   the one minimal form: a digit list whose last digit is zero is refused
   rather than normalized, which is R-05-051b's pinned subset, and zero is
   the empty digit list. A manifest record is the manifest tag followed by
   the twelve identity numerals in the record's own field order, and nothing
   else; a certificate container is the container tag, that same field body
   for its subject, the checker and profile numerals, the length-prefixed
   evidence bytes and the length-prefixed assumption list. Neither
   production refers to itself, so the grammar is non-recursive and its
   nesting depth is one; the recursions below are over flat byte lists and
   over a field count, never over the format.

   Every magnitude is a field of FormatBounds: the byte radix, a numeral's
   digit bound, the manifest's field count, the two record tags, the
   evidence byte budget, the assumption entry budget and the two total-size
   budgets. The only magnitude a definition reads outside a witness is the
   radix floor of two in `format_wf`, which is positional notation's domain
   condition and not a format maximum; the remaining numerals below are
   positions in a check list, read by a proof script. The identities are
   opaque: nothing here computes, compares or checks a digest, and an
   identity is a bounded numeral that stands for one.

   What the gate's green line means, and what it does not. These definitions
   compile, are axiom-free, and are enumerated. No cryptography is
   implemented: no hash, signature, key exchange or transport is computed,
   and a certificate's bytes are opaque evidence that this file moves and
   bounds without inspecting. No kernel receipt is synthesized from card
   bytes; `admit_encoded` below parses a container and hands the parsed
   evidence to ModuleAdmission's design gate together with a receipt the
   host supplies, because a card-supplied success assertion is never a
   receipt (R-12-085h).

   What remains open for Q24c, and it is most of the item. The executable
   proof checker and the checked design-admission path; the cryptographic
   implementations R-12-085i's selected construction needs, and the session
   binding over them; the physical binding from a unit key to actual
   circuitry, which R-17-058i retains; and the Narcissus derivation and its
   correspondence to this hand-authored reference codec, which R-05-046 and
   R-05-042's inventory own and which no theorem below supplies. A format
   theorem admits no card: it decides which byte strings name which values,
   and it decides nothing about a design, a unit, a session or a part.
   InferenceAdmission.v states the same two R-05-051a directions over a
   fixed-width field schema; this file states them over a variable-length
   minimal form, where R-05-051b's no-slack rule is carried by the pinned
   digit form rather than by a constant length.

   Non-vacuity, in R-05-165's and R-05-166's terms. Every obligation is
   stated of an arbitrary FormatBounds, an arbitrary value and an arbitrary
   byte string, and each carrier record has a closed witness. The witness
   bounds record is the only place a magnitude is chosen, and beside every
   accepting case is a refusing neighbour computed on the contract's Design
   row: malformed bytes, an over-budget length, a trailing byte, a
   non-canonical length form, a subject naming another design or model, and
   an assumption the host did not permit. R-05-163's assumption gate is
   answered by the Print Assumptions block at the end, which reports each
   shipped theorem closed under the global context.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-04-010b R-05-042 R-05-046 R-05-051a R-05-051b R-05-051c R-05-163 R-05-165
      R-05-166 R-06-015a R-12-085f R-12-085g R-12-085h R-12-085i R-12-085l R-15-228h R-17-058i
   SHA256: c0d2ab0ecca2fbc486d951960f109608689e5ab937fe7418d66d356f3ada8630
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Require Import ModuleAdmission.

Open Scope list_scope.

(* -------------------------------------------------------------------------
   Shared readings, each stated once so that no proof below depends on a
   reduction tactic expanding the radix into a numeral.
   ------------------------------------------------------------------------- *)

Lemma some_pair_eq : forall (A B : Type) (a c : A) (b d : B),
  Some (a, b) = Some (c, d) -> a = c /\ b = d.
Proof. intros A B a c b d H. injection H as H1 H2. split; assumption. Qed.

Lemma app_assoc_left : forall l m n : list nat, (l ++ m) ++ n = l ++ (m ++ n).
Proof. intros l m n. symmetry. apply app_assoc. Qed.

Lemma count_cons : forall (x : nat) (l : list nat), count (x :: l) = S (count l).
Proof. intros x l. reflexivity. Qed.

Lemma below_cons : forall limit x xs,
  below limit (x :: xs) = andb (Nat.ltb x limit) (below limit xs).
Proof. intros limit x xs. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The numeral: one minimal least-significant-first digit list per value.
   ------------------------------------------------------------------------- *)

Fixpoint le_digits (fuel radix n : nat) : list nat :=
  match fuel with
  | 0 => nil
  | S k => if Nat.eqb n 0 then nil else (n mod radix) :: le_digits k radix (n / radix)
  end.

Fixpoint le_value (radix : nat) (ds : list nat) : nat :=
  match ds with nil => 0 | d :: rest => d + le_value radix rest * radix end.

(* R-05-051b's pinned subset: the empty list, or one whose last digit is not
   zero. Least significant first, so the last element is the numeral's
   high-order digit: a redundant high-order zero is a decode failure and is
   never rewritten into the value's canonical form. *)
Fixpoint minimalb (ds : list nat) : bool :=
  match ds with
  | nil => true
  | d :: rest => match rest with nil => negb (Nat.eqb d 0) | _ :: _ => minimalb rest end
  end.

Lemma le_digits_succ : forall k radix n,
  le_digits (S k) radix n =
    if Nat.eqb n 0 then nil else (n mod radix) :: le_digits k radix (n / radix).
Proof. intros k radix n. reflexivity. Qed.

Lemma le_value_cons : forall radix d ds,
  le_value radix (d :: ds) = d + le_value radix ds * radix.
Proof. intros radix d ds. reflexivity. Qed.

Lemma minimalb_cons : forall a ds, ds <> nil -> minimalb (a :: ds) = minimalb ds.
Proof. intros a ds H. destruct ds as [|b l]; [contradiction | reflexivity]. Qed.

Lemma digits_nil_inv : forall fuel radix n,
  le_digits fuel radix n = nil -> fuel = 0 \/ n = 0.
Proof.
  intros fuel radix n H. destruct fuel as [|k]; [left; reflexivity | right].
  rewrite le_digits_succ in H. destruct (Nat.eqb n 0) eqn:E.
  - apply eqb_equal in E. exact E.
  - discriminate.
Qed.

Lemma digits_count : forall fuel radix n, count (le_digits fuel radix n) <= fuel.
Proof.
  induction fuel as [|k IH]; intros radix n.
  - apply Nat.le_0_l.
  - rewrite le_digits_succ. destruct (Nat.eqb n 0).
    + apply Nat.le_0_l.
    + rewrite count_cons. apply le_n_S. apply IH.
Qed.

Lemma digits_below : forall fuel radix n,
  2 <= radix -> below radix (le_digits fuel radix n) = true.
Proof.
  induction fuel as [|k IH]; intros radix n Hr.
  - reflexivity.
  - rewrite le_digits_succ. destruct (Nat.eqb n 0).
    + reflexivity.
    + rewrite below_cons.
      assert (Hm : Nat.ltb (n mod radix) radix = true).
      { apply Nat.ltb_lt. apply Nat.mod_upper_bound. lia. }
      rewrite Hm. rewrite (IH radix (n / radix) Hr). reflexivity.
Qed.

Lemma digits_exact : forall fuel radix n,
  2 <= radix -> count (le_digits fuel radix n) < fuel ->
  le_value radix (le_digits fuel radix n) = n.
Proof.
  induction fuel as [|k IH]; intros radix n Hr Hc.
  - cbn [le_digits count] in Hc. lia.
  - rewrite le_digits_succ in Hc |- *. destruct (Nat.eqb n 0) eqn:E.
    + apply eqb_equal in E. cbn [le_value]. symmetry. exact E.
    + rewrite count_cons in Hc. rewrite le_value_cons.
      assert (Hk : count (le_digits k radix (n / radix)) < k) by lia.
      rewrite (IH radix (n / radix) Hr Hk).
      pose proof (Nat.div_mod_eq n radix) as Hd. rewrite Nat.mul_comm in Hd. lia.
Qed.

Lemma digits_minimal : forall fuel radix n,
  2 <= radix -> count (le_digits fuel radix n) < fuel ->
  minimalb (le_digits fuel radix n) = true.
Proof.
  induction fuel as [|k IH]; intros radix n Hr Hc.
  - cbn [le_digits count] in Hc. lia.
  - rewrite le_digits_succ in Hc |- *. destruct (Nat.eqb n 0) eqn:E.
    + reflexivity.
    + rewrite count_cons in Hc.
      destruct (le_digits k radix (n / radix)) as [|d rest] eqn:D.
      * cbn [count] in Hc.
        assert (Hq : n / radix = 0).
        { destruct (digits_nil_inv k radix (n / radix) D) as [Hk0 | Hq0].
          - subst k. lia.
          - exact Hq0. }
        assert (Hmod : n mod radix = n).
        { pose proof (Nat.div_mod_eq n radix) as Hd. rewrite Hq in Hd. lia. }
        cbn [minimalb]. rewrite Hmod. rewrite E. reflexivity.
      * rewrite minimalb_cons by discriminate. rewrite <- D.
        apply IH; [exact Hr |]. rewrite D. cbn [count] in Hc |- *. lia.
Qed.

Lemma minimal_value_nonzero : forall radix ds,
  2 <= radix -> minimalb ds = true -> ds <> nil -> le_value radix ds <> 0.
Proof.
  intros radix ds. induction ds as [|d rest IH]; intros Hr Hm Hn.
  - contradiction.
  - destruct rest as [|e l].
    + cbn [minimalb] in Hm. cbn [le_value].
      destruct d as [|d']; [cbn in Hm; discriminate | lia].
    + assert (Hrest : le_value radix (e :: l) <> 0).
      { apply IH; [exact Hr | | discriminate].
        rewrite <- (minimalb_cons d (e :: l)); [exact Hm | discriminate]. }
      rewrite le_value_cons. intros Hz.
      assert (Hp : le_value radix (e :: l) * radix = 0) by lia.
      apply Nat.mul_eq_0 in Hp. destruct Hp as [Hp | Hp]; [contradiction | lia].
Qed.

Lemma minimal_cons_value_nonzero : forall radix d rest,
  2 <= radix -> minimalb (d :: rest) = true -> d + le_value radix rest * radix <> 0.
Proof.
  intros radix d rest Hr Hm. destruct rest as [|e l].
  - cbn [minimalb] in Hm. cbn [le_value].
    destruct d as [|d']; [cbn in Hm; discriminate | lia].
  - assert (Hrest : le_value radix (e :: l) <> 0).
    { apply minimal_value_nonzero; [exact Hr | | discriminate].
      rewrite <- (minimalb_cons d (e :: l)); [exact Hm | discriminate]. }
    intros Hz. assert (Hp : le_value radix (e :: l) * radix = 0) by lia.
    apply Nat.mul_eq_0 in Hp. destruct Hp as [Hp | Hp]; [contradiction | lia].
Qed.

(* The canonicity core: a minimal digit list is the encoding of its own
   value, so no second digit list carries that value. *)
Lemma digits_of_value : forall ds fuel radix,
  2 <= radix -> below radix ds = true -> minimalb ds = true -> count ds <= fuel ->
  le_digits fuel radix (le_value radix ds) = ds.
Proof.
  induction ds as [|d rest IH]; intros fuel radix Hr Hb Hm Hc.
  - cbn [le_value]. destruct fuel as [|k]; [reflexivity |].
    rewrite le_digits_succ. reflexivity.
  - destruct fuel as [|k]; [rewrite count_cons in Hc; lia |].
    rewrite count_cons in Hc. rewrite le_value_cons. rewrite le_digits_succ.
    assert (Hd : d < radix).
    { rewrite below_cons in Hb. apply andb_split in Hb. destruct Hb as [Hb1 _].
      apply Nat.ltb_lt. exact Hb1. }
    assert (Hbrest : below radix rest = true).
    { rewrite below_cons in Hb. apply andb_split in Hb. destruct Hb as [_ Hb2].
      exact Hb2. }
    assert (Hmrest : minimalb rest = true).
    { destruct rest as [|e l]; [reflexivity |].
      rewrite <- (minimalb_cons d (e :: l)); [exact Hm | discriminate]. }
    pose proof (minimal_cons_value_nonzero radix d rest Hr Hm) as Hnz.
    destruct (Nat.eqb (d + le_value radix rest * radix) 0) eqn:EZ.
    { apply eqb_equal in EZ. contradiction. }
    assert (Hmod : (d + le_value radix rest * radix) mod radix = d).
    { rewrite Nat.Div0.mod_add. apply Nat.mod_small. exact Hd. }
    assert (Hdiv : (d + le_value radix rest * radix) / radix = le_value radix rest).
    { rewrite Nat.div_add by lia. rewrite Nat.div_small by exact Hd. reflexivity. }
    rewrite Hmod. rewrite Hdiv.
    rewrite (IH k radix Hr Hbrest Hmrest ltac:(lia)). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The declared magnitudes. Every maximum this format enforces is a field
   here; nothing below reads a literal bound.
   ------------------------------------------------------------------------- *)

Record FormatBounds := {
  byte_values : nat; numeral_digits : nat; manifest_fields : nat;
  manifest_tag : nat; certificate_tag : nat; evidence_bytes_max : nat;
  assumption_entries_max : nat; manifest_bytes_max : nat; container_bytes_max : nat
}.

Definition manifest_arity : nat := count (identity manifest_fixture).

Lemma arity_of : forall m : Manifest, count (identity m) = manifest_arity.
Proof. intros m. reflexivity. Qed.

Definition format_wf (f : FormatBounds) : bool :=
  every (Nat.leb 2 (byte_values f) ::
         Nat.ltb (numeral_digits f) (byte_values f) ::
         Nat.ltb (manifest_tag f) (byte_values f) ::
         Nat.ltb (certificate_tag f) (byte_values f) ::
         negb (Nat.eqb (manifest_tag f) (certificate_tag f)) ::
         Nat.eqb (manifest_fields f) manifest_arity :: nil).

Lemma wf_radix : forall f, format_wf f = true -> 2 <= byte_values f.
Proof. intros f H. apply Nat.leb_le. exact (every_at _ 0 H). Qed.

Lemma wf_fields : forall f, format_wf f = true -> manifest_fields f = manifest_arity.
Proof. intros f H. apply eqb_equal. exact (every_at _ 5 H). Qed.

Lemma wf_tags_differ : forall f,
  format_wf f = true -> Nat.eqb (manifest_tag f) (certificate_tag f) = false.
Proof.
  intros f H. pose proof (every_at _ 4 H) as E.
  change (negb (Nat.eqb (manifest_tag f) (certificate_tag f)) = true) in E.
  destruct (Nat.eqb (manifest_tag f) (certificate_tag f)); [discriminate | reflexivity].
Qed.

(* -------------------------------------------------------------------------
   The numeral on the wire, and the byte-list reader both records share.
   ------------------------------------------------------------------------- *)

Definition digits_of (f : FormatBounds) (n : nat) : list nat :=
  le_digits (S (numeral_digits f)) (byte_values f) n.

Definition fits (f : FormatBounds) (n : nat) : bool :=
  Nat.leb (count (digits_of f n)) (numeral_digits f).

Definition write_numeral (f : FormatBounds) (n : nat) : option (list nat) :=
  if fits f n then Some (count (digits_of f n) :: digits_of f n) else None.

Fixpoint take (n : nat) (bs : list nat) : option (list nat * list nat) :=
  match n with
  | 0 => Some (nil, bs)
  | S k =>
      match bs with
      | nil => None
      | b :: rest =>
          match take k rest with
          | None => None
          | Some (front, back) => Some (b :: front, back)
          end
      end
  end.

Definition read_numeral (f : FormatBounds) (bs : list nat) : option (nat * list nat) :=
  match bs with
  | nil => None
  | k :: rest =>
      if Nat.leb k (numeral_digits f) then
        match take k rest with
        | None => None
        | Some (ds, back) =>
            if andb (below (byte_values f) ds) (minimalb ds)
            then Some (le_value (byte_values f) ds, back)
            else None
        end
      else None
  end.

Lemma fits_leb : forall f n,
  fits f n = true -> Nat.leb (count (digits_of f n)) (numeral_digits f) = true.
Proof. intros f n H. exact H. Qed.

Lemma fits_count : forall f n,
  fits f n = true -> count (digits_of f n) < S (numeral_digits f).
Proof. intros f n H. unfold fits in H. apply Nat.leb_le in H. lia. Qed.

Lemma digits_of_below : forall f n,
  2 <= byte_values f -> below (byte_values f) (digits_of f n) = true.
Proof. intros f n H. unfold digits_of. apply digits_below. exact H. Qed.

Lemma digits_of_minimal : forall f n,
  2 <= byte_values f -> fits f n = true -> minimalb (digits_of f n) = true.
Proof.
  intros f n Hr Hf. unfold digits_of. apply digits_minimal; [exact Hr |].
  exact (fits_count f n Hf).
Qed.

Lemma digits_of_exact : forall f n,
  2 <= byte_values f -> fits f n = true ->
  le_value (byte_values f) (digits_of f n) = n.
Proof.
  intros f n Hr Hf. unfold digits_of. apply digits_exact; [exact Hr |].
  exact (fits_count f n Hf).
Qed.

Lemma take_exact : forall xs ys, take (count xs) (xs ++ ys) = Some (xs, ys).
Proof.
  induction xs as [|x xs IH]; intros ys.
  - reflexivity.
  - rewrite count_cons. cbn [take app]. rewrite IH. reflexivity.
Qed.

Lemma take_split : forall n bs xs ys,
  take n bs = Some (xs, ys) -> bs = xs ++ ys /\ count xs = n.
Proof.
  induction n as [|k IH]; intros bs xs ys H.
  - cbn [take] in H. destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2].
    rewrite <- H1. rewrite <- H2. split; reflexivity.
  - destruct bs as [|b rest]; [discriminate |].
    cbn [take] in H. destruct (take k rest) as [[front back]|] eqn:E; [|discriminate].
    destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2].
    destruct (IH rest front back E) as [Hb Hc].
    rewrite <- H1. rewrite <- H2. split.
    + cbn [app]. rewrite <- Hb. reflexivity.
    + rewrite count_cons. rewrite Hc. reflexivity.
Qed.

Lemma read_write_numeral : forall f n enc back,
  format_wf f = true -> write_numeral f n = Some enc ->
  read_numeral f (enc ++ back) = Some (n, back).
Proof.
  intros f n enc back Hwf Hw. pose proof (wf_radix f Hwf) as Hr.
  unfold write_numeral in Hw. destruct (fits f n) eqn:EF; [|discriminate].
  injection Hw as Hw. rewrite <- Hw. cbn [app]. unfold read_numeral.
  rewrite (fits_leb f n EF). rewrite take_exact.
  rewrite (digits_of_below f n Hr). rewrite (digits_of_minimal f n Hr EF).
  cbn [andb]. rewrite (digits_of_exact f n Hr EF). reflexivity.
Qed.

Lemma write_read_numeral : forall f bs n back,
  format_wf f = true -> read_numeral f bs = Some (n, back) ->
  exists enc, bs = enc ++ back /\ write_numeral f n = Some enc.
Proof.
  intros f bs n back Hwf H. pose proof (wf_radix f Hwf) as Hr.
  destruct bs as [|k rest]; [discriminate |].
  unfold read_numeral in H.
  destruct (Nat.leb k (numeral_digits f)) eqn:EK; [|discriminate].
  destruct (take k rest) as [[ds tail]|] eqn:ET; [|discriminate].
  destruct (andb (below (byte_values f) ds) (minimalb ds)) eqn:EB; [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hv Hb].
  apply andb_split in EB. destruct EB as [EB1 EB2].
  destruct (take_split k rest ds tail ET) as [Hr1 Hr2].
  assert (EKle : k <= numeral_digits f) by (apply Nat.leb_le; exact EK).
  assert (Hds : digits_of f n = ds).
  { unfold digits_of. rewrite <- Hv. apply digits_of_value;
      [exact Hr | exact EB1 | exact EB2 | lia]. }
  exists (k :: ds). split.
  - cbn [app]. rewrite <- Hb. rewrite <- Hr1. reflexivity.
  - unfold write_numeral. unfold fits. rewrite Hds. rewrite Hr2.
    rewrite EK. reflexivity.
Qed.

(*| discharges: R-05-051b |*)
Theorem a_numeral_has_one_admissible_form : forall f bs1 bs2 n back,
  format_wf f = true ->
  read_numeral f bs1 = Some (n, back) -> read_numeral f bs2 = Some (n, back) ->
  bs1 = bs2.
Proof.
  intros f bs1 bs2 n back Hwf H1 H2.
  destruct (write_read_numeral f bs1 n back Hwf H1) as [e1 [Hb1 Hw1]].
  destruct (write_read_numeral f bs2 n back Hwf H2) as [e2 [Hb2 Hw2]].
  rewrite Hw1 in Hw2. injection Hw2 as Hw2.
  rewrite Hb1. rewrite Hb2. rewrite Hw2. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The three compound readers: a fixed count of numerals, a length-prefixed
   byte string, and a length-prefixed numeral list. Each bound is a caller's
   declared field.
   ------------------------------------------------------------------------- *)

Fixpoint write_numerals (f : FormatBounds) (ns : list nat) : option (list nat) :=
  match ns with
  | nil => Some nil
  | n :: rest =>
      match write_numeral f n with
      | None => None
      | Some head =>
          match write_numerals f rest with
          | None => None
          | Some tail => Some (head ++ tail)
          end
      end
  end.

Fixpoint read_numerals (f : FormatBounds) (k : nat) (bs : list nat)
  : option (list nat * list nat) :=
  match k with
  | 0 => Some (nil, bs)
  | S j =>
      match read_numeral f bs with
      | None => None
      | Some (n, rest) =>
          match read_numerals f j rest with
          | None => None
          | Some (ns, back) => Some (n :: ns, back)
          end
      end
  end.

Lemma read_write_numerals : forall f ns enc back,
  format_wf f = true -> write_numerals f ns = Some enc ->
  read_numerals f (count ns) (enc ++ back) = Some (ns, back).
Proof.
  intros f ns. induction ns as [|n rest IH]; intros enc back Hwf Hw.
  - cbn [write_numerals] in Hw. injection Hw as Hw. rewrite <- Hw.
    reflexivity.
  - cbn [write_numerals] in Hw.
    destruct (write_numeral f n) as [head|] eqn:E1; [|discriminate].
    destruct (write_numerals f rest) as [tail|] eqn:E2; [|discriminate].
    injection Hw as Hw. rewrite <- Hw. rewrite count_cons.
    cbn [read_numerals]. rewrite app_assoc_left.
    rewrite (read_write_numeral f n head (tail ++ back) Hwf E1).
    rewrite (IH tail back Hwf eq_refl). reflexivity.
Qed.

Lemma write_read_numerals : forall f k bs ns back,
  format_wf f = true -> read_numerals f k bs = Some (ns, back) ->
  exists enc, bs = enc ++ back /\ write_numerals f ns = Some enc /\ count ns = k.
Proof.
  intros f k. induction k as [|j IH]; intros bs ns back Hwf H.
  - cbn [read_numerals] in H. destruct (some_pair_eq _ _ _ _ _ _ H) as [Hn Hb].
    exists nil. rewrite <- Hn. rewrite <- Hb.
    split; [reflexivity |]. split; reflexivity.
  - cbn [read_numerals] in H.
    destruct (read_numeral f bs) as [[n rest]|] eqn:E1; [|discriminate].
    destruct (read_numerals f j rest) as [[ns' back']|] eqn:E2; [|discriminate].
    destruct (some_pair_eq _ _ _ _ _ _ H) as [Hn Hb].
    destruct (write_read_numeral f bs n rest Hwf E1) as [e1 [Hb1 Hw1]].
    destruct (IH rest ns' back' Hwf E2) as [e2 [Hb2 [Hw2 Hc2]]].
    exists (e1 ++ e2). rewrite <- Hn. rewrite <- Hb. split.
    + rewrite Hb1. rewrite Hb2. rewrite app_assoc_left. reflexivity.
    + split.
      * cbn [write_numerals]. rewrite Hw1. rewrite Hw2. reflexivity.
      * rewrite count_cons. rewrite Hc2. reflexivity.
Qed.

Definition write_blob (f : FormatBounds) (limit : nat) (xs : list nat)
  : option (list nat) :=
  if andb (Nat.leb (count xs) limit) (below (byte_values f) xs)
  then match write_numeral f (count xs) with
       | None => None
       | Some head => Some (head ++ xs)
       end
  else None.

Definition read_blob (f : FormatBounds) (limit : nat) (bs : list nat)
  : option (list nat * list nat) :=
  match read_numeral f bs with
  | None => None
  | Some (n, rest) =>
      if Nat.leb n limit then
        match take n rest with
        | None => None
        | Some (payload, back) =>
            if below (byte_values f) payload then Some (payload, back) else None
        end
      else None
  end.

Lemma read_write_blob : forall f limit xs enc back,
  format_wf f = true -> write_blob f limit xs = Some enc ->
  read_blob f limit (enc ++ back) = Some (xs, back).
Proof.
  intros f limit xs enc back Hwf Hw. unfold write_blob in Hw.
  destruct (andb (Nat.leb (count xs) limit) (below (byte_values f) xs)) eqn:EG;
    [|discriminate].
  destruct (write_numeral f (count xs)) as [head|] eqn:E1; [|discriminate].
  injection Hw as Hw. rewrite <- Hw.
  apply andb_split in EG. destruct EG as [EG1 EG2].
  unfold read_blob. rewrite app_assoc_left.
  rewrite (read_write_numeral f (count xs) head (xs ++ back) Hwf E1).
  rewrite EG1. rewrite take_exact. rewrite EG2. reflexivity.
Qed.

Lemma write_read_blob : forall f limit bs xs back,
  format_wf f = true -> read_blob f limit bs = Some (xs, back) ->
  exists enc, bs = enc ++ back /\ write_blob f limit xs = Some enc.
Proof.
  intros f limit bs xs back Hwf H. unfold read_blob in H.
  destruct (read_numeral f bs) as [[n rest]|] eqn:E1; [|discriminate].
  destruct (Nat.leb n limit) eqn:EL; [|discriminate].
  destruct (take n rest) as [[payload tail]|] eqn:ET; [|discriminate].
  destruct (below (byte_values f) payload) eqn:EB; [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hp Hb].
  destruct (write_read_numeral f bs n rest Hwf E1) as [e1 [Hb1 Hw1]].
  destruct (take_split n rest payload tail ET) as [Hr1 Hr2].
  exists (e1 ++ payload). rewrite <- Hp. rewrite <- Hb. split.
  - rewrite Hb1. rewrite Hr1. rewrite app_assoc_left. reflexivity.
  - unfold write_blob. rewrite Hr2. rewrite EL. rewrite EB. cbn [andb].
    rewrite Hw1. reflexivity.
Qed.

Definition write_entries (f : FormatBounds) (limit : nat) (ns : list nat)
  : option (list nat) :=
  if Nat.leb (count ns) limit
  then match write_numeral f (count ns) with
       | None => None
       | Some head =>
           match write_numerals f ns with
           | None => None
           | Some body => Some (head ++ body)
           end
       end
  else None.

Definition read_entries (f : FormatBounds) (limit : nat) (bs : list nat)
  : option (list nat * list nat) :=
  match read_numeral f bs with
  | None => None
  | Some (n, rest) => if Nat.leb n limit then read_numerals f n rest else None
  end.

Lemma read_write_entries : forall f limit ns enc back,
  format_wf f = true -> write_entries f limit ns = Some enc ->
  read_entries f limit (enc ++ back) = Some (ns, back).
Proof.
  intros f limit ns enc back Hwf Hw. unfold write_entries in Hw.
  destruct (Nat.leb (count ns) limit) eqn:EL; [|discriminate].
  destruct (write_numeral f (count ns)) as [head|] eqn:E1; [|discriminate].
  destruct (write_numerals f ns) as [body|] eqn:E2; [|discriminate].
  injection Hw as Hw. rewrite <- Hw.
  unfold read_entries. rewrite app_assoc_left.
  rewrite (read_write_numeral f (count ns) head (body ++ back) Hwf E1).
  rewrite EL. exact (read_write_numerals f ns body back Hwf E2).
Qed.

Lemma write_read_entries : forall f limit bs ns back,
  format_wf f = true -> read_entries f limit bs = Some (ns, back) ->
  exists enc, bs = enc ++ back /\ write_entries f limit ns = Some enc.
Proof.
  intros f limit bs ns back Hwf H. unfold read_entries in H.
  destruct (read_numeral f bs) as [[n rest]|] eqn:E1; [|discriminate].
  destruct (Nat.leb n limit) eqn:EL; [|discriminate].
  destruct (write_read_numeral f bs n rest Hwf E1) as [e1 [Hb1 Hw1]].
  destruct (write_read_numerals f n rest ns back Hwf H) as [e2 [Hb2 [Hw2 Hc2]]].
  exists (e1 ++ e2). split.
  - rewrite Hb1. rewrite Hb2. rewrite app_assoc_left. reflexivity.
  - unfold write_entries. rewrite Hc2. rewrite EL. rewrite Hw1. rewrite Hw2.
    reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The manifest: the twelve identities of ModuleAdmission's record, in the
   record's own field order, with no presence encoding and no padding.
   ------------------------------------------------------------------------- *)

Definition manifest_of_identity (xs : list nat) : option Manifest :=
  match xs with
  | g :: w :: a :: t :: v :: c :: i :: s :: p :: fp :: e :: pr :: nil =>
      Some {| graph_id := g; weights_id := w; arithmetic_id := a;
              tokenizer_id := t; vocabulary_id := v; circuit_id := c;
              implementation_id := i; schema_id := s; protocol_id := p;
              footprint_id := fp; envelope_id := e; propositions_id := pr |}
  | _ => None
  end.

Lemma manifest_of_its_identity : forall m, manifest_of_identity (identity m) = Some m.
Proof. intros m. destruct m. reflexivity. Qed.

Lemma identity_of_manifest : forall xs m,
  manifest_of_identity xs = Some m -> identity m = xs.
Proof.
  intros xs m H.
  destruct xs as [|a1 xs]; [discriminate |].
  destruct xs as [|a2 xs]; [discriminate |].
  destruct xs as [|a3 xs]; [discriminate |].
  destruct xs as [|a4 xs]; [discriminate |].
  destruct xs as [|a5 xs]; [discriminate |].
  destruct xs as [|a6 xs]; [discriminate |].
  destruct xs as [|a7 xs]; [discriminate |].
  destruct xs as [|a8 xs]; [discriminate |].
  destruct xs as [|a9 xs]; [discriminate |].
  destruct xs as [|a10 xs]; [discriminate |].
  destruct xs as [|a11 xs]; [discriminate |].
  destruct xs as [|a12 xs]; [discriminate |].
  destruct xs as [|a13 xs]; [| discriminate].
  cbn [manifest_of_identity] in H. injection H as H. rewrite <- H. reflexivity.
Qed.

Definition write_manifest_body (f : FormatBounds) (m : Manifest) : option (list nat) :=
  write_numerals f (identity m).

Definition read_manifest_body (f : FormatBounds) (bs : list nat)
  : option (Manifest * list nat) :=
  match read_numerals f (manifest_fields f) bs with
  | None => None
  | Some (xs, back) =>
      match manifest_of_identity xs with
      | None => None
      | Some m => Some (m, back)
      end
  end.

Lemma read_write_manifest_body : forall f m enc back,
  format_wf f = true -> write_manifest_body f m = Some enc ->
  read_manifest_body f (enc ++ back) = Some (m, back).
Proof.
  intros f m enc back Hwf Hw. unfold write_manifest_body in Hw.
  unfold read_manifest_body. rewrite (wf_fields f Hwf). rewrite <- (arity_of m).
  rewrite (read_write_numerals f (identity m) enc back Hwf Hw).
  rewrite manifest_of_its_identity. reflexivity.
Qed.

Lemma write_read_manifest_body : forall f bs m back,
  format_wf f = true -> read_manifest_body f bs = Some (m, back) ->
  exists enc, bs = enc ++ back /\ write_manifest_body f m = Some enc.
Proof.
  intros f bs m back Hwf H. unfold read_manifest_body in H.
  destruct (read_numerals f (manifest_fields f) bs) as [[xs tail]|] eqn:E1;
    [|discriminate].
  destruct (manifest_of_identity xs) as [m'|] eqn:E2; [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hm Hb].
  destruct (write_read_numerals f (manifest_fields f) bs xs tail Hwf E1)
    as [enc [Hb1 [Hw1 Hc1]]].
  exists enc. rewrite <- Hb. split; [exact Hb1 |].
  unfold write_manifest_body. rewrite <- Hm.
  rewrite (identity_of_manifest xs m' E2). exact Hw1.
Qed.

Definition write_manifest (f : FormatBounds) (m : Manifest) : option (list nat) :=
  match write_manifest_body f m with
  | None => None
  | Some body =>
      if Nat.leb (S (count body)) (manifest_bytes_max f)
      then Some (manifest_tag f :: body) else None
  end.

Definition read_manifest (f : FormatBounds) (bs : list nat) : option Manifest :=
  if Nat.leb (count bs) (manifest_bytes_max f) then
    match bs with
    | nil => None
    | tag :: rest =>
        if Nat.eqb tag (manifest_tag f) then
          match read_manifest_body f rest with
          | Some (m, nil) => Some m
          | _ => None
          end
        else None
    end
  else None.

(*| discharges: R-05-051a |*)
Theorem manifest_parse_of_serialize : forall f m enc,
  format_wf f = true -> write_manifest f m = Some enc -> read_manifest f enc = Some m.
Proof.
  intros f m enc Hwf Hw. unfold write_manifest in Hw.
  destruct (write_manifest_body f m) as [body|] eqn:E1; [|discriminate].
  destruct (Nat.leb (S (count body)) (manifest_bytes_max f)) eqn:E2; [|discriminate].
  injection Hw as Hw. rewrite <- Hw.
  unfold read_manifest. rewrite count_cons. rewrite E2. rewrite eqb_self.
  pose proof (read_write_manifest_body f m body nil Hwf E1) as Hr.
  rewrite app_nil_r in Hr. rewrite Hr. reflexivity.
Qed.

(*| discharges: R-05-051a, R-05-051b |*)
Theorem manifest_serialize_of_parse : forall f bs m,
  format_wf f = true -> read_manifest f bs = Some m -> write_manifest f m = Some bs.
Proof.
  intros f bs m Hwf H. unfold read_manifest in H.
  destruct (Nat.leb (count bs) (manifest_bytes_max f)) eqn:EB; [|discriminate].
  destruct bs as [|tag rest]; [discriminate |].
  destruct (Nat.eqb tag (manifest_tag f)) eqn:ET; [|discriminate].
  destruct (read_manifest_body f rest) as [[m' tail]|] eqn:E1; [|discriminate].
  destruct tail as [|x t]; [|discriminate].
  injection H as H.
  destruct (write_read_manifest_body f rest m' nil Hwf E1) as [enc [Hb1 Hw1]].
  rewrite app_nil_r in Hb1.
  unfold write_manifest. rewrite <- H. rewrite Hw1.
  rewrite Hb1 in EB. rewrite count_cons in EB. rewrite EB.
  rewrite (eqb_equal tag (manifest_tag f) ET). rewrite Hb1. reflexivity.
Qed.

(*| discharges: R-05-051a |*)
Theorem manifest_has_one_admissible_encoding : forall f bs1 bs2 m,
  format_wf f = true ->
  read_manifest f bs1 = Some m -> read_manifest f bs2 = Some m -> bs1 = bs2.
Proof.
  intros f bs1 bs2 m Hwf H1 H2.
  pose proof (manifest_serialize_of_parse f bs1 m Hwf H1) as A.
  pose proof (manifest_serialize_of_parse f bs2 m Hwf H2) as B.
  rewrite A in B. injection B as B. exact B.
Qed.

Theorem manifest_encoding_is_injective : forall f m1 m2 enc,
  format_wf f = true ->
  write_manifest f m1 = Some enc -> write_manifest f m2 = Some enc -> m1 = m2.
Proof.
  intros f m1 m2 enc Hwf H1 H2.
  pose proof (manifest_parse_of_serialize f m1 enc Hwf H1) as A.
  pose proof (manifest_parse_of_serialize f m2 enc Hwf H2) as B.
  rewrite A in B. injection B as B. exact B.
Qed.

(*| discharges: R-05-051b |*)
Theorem manifest_refuses_trailing_bytes : forall f m enc extra,
  format_wf f = true -> write_manifest f m = Some enc -> extra <> nil ->
  read_manifest f (enc ++ extra) = None.
Proof.
  intros f m enc extra Hwf Hw Hx. unfold write_manifest in Hw.
  destruct (write_manifest_body f m) as [body|] eqn:E1; [|discriminate].
  destruct (Nat.leb (S (count body)) (manifest_bytes_max f)) eqn:E2; [|discriminate].
  injection Hw as Hw. rewrite <- Hw. cbn [app]. unfold read_manifest.
  destruct (Nat.leb (count (manifest_tag f :: (body ++ extra)))
                    (manifest_bytes_max f)) eqn:EB; [|reflexivity].
  rewrite eqb_self.
  rewrite (read_write_manifest_body f m body extra Hwf E1).
  destruct extra as [|x t]; [exfalso; apply Hx; reflexivity | reflexivity].
Qed.

(* -------------------------------------------------------------------------
   The proof-certificate container. Its evidence is a bounded opaque byte
   string: nothing below inspects it, and no theorem here says it proves
   anything (R-12-085h owns the checker).
   ------------------------------------------------------------------------- *)

Record Certificate := {
  certificate_subject : Manifest; certificate_checker : nat;
  certificate_profile : nat; certificate_evidence : list nat;
  certificate_assumptions : list nat
}.

Definition certificate_body (subject checker profile evidence entries : list nat)
  : list nat := subject ++ checker ++ profile ++ evidence ++ entries.

Definition write_certificate (f : FormatBounds) (c : Certificate)
  : option (list nat) :=
  match write_manifest_body f (certificate_subject c) with
  | None => None
  | Some subject =>
      match write_numeral f (certificate_checker c) with
      | None => None
      | Some checker =>
          match write_numeral f (certificate_profile c) with
          | None => None
          | Some profile =>
              match write_blob f (evidence_bytes_max f) (certificate_evidence c) with
              | None => None
              | Some evidence =>
                  match write_entries f (assumption_entries_max f)
                                      (certificate_assumptions c) with
                  | None => None
                  | Some entries =>
                      if Nat.leb (S (count (certificate_body subject checker profile
                                                             evidence entries)))
                                 (container_bytes_max f)
                      then Some (certificate_tag f ::
                                 certificate_body subject checker profile evidence entries)
                      else None
                  end
              end
          end
      end
  end.

Definition read_certificate (f : FormatBounds) (bs : list nat) : option Certificate :=
  if Nat.leb (count bs) (container_bytes_max f) then
    match bs with
    | nil => None
    | tag :: rest =>
        if Nat.eqb tag (certificate_tag f) then
          match read_manifest_body f rest with
          | None => None
          | Some (subject, r1) =>
              match read_numeral f r1 with
              | None => None
              | Some (checker, r2) =>
                  match read_numeral f r2 with
                  | None => None
                  | Some (profile, r3) =>
                      match read_blob f (evidence_bytes_max f) r3 with
                      | None => None
                      | Some (evidence, r4) =>
                          match read_entries f (assumption_entries_max f) r4 with
                          | Some (entries, nil) =>
                              Some {| certificate_subject := subject;
                                      certificate_checker := checker;
                                      certificate_profile := profile;
                                      certificate_evidence := evidence;
                                      certificate_assumptions := entries |}
                          | _ => None
                          end
                      end
                  end
              end
          end
        else None
    end
  else None.

(*| discharges: R-05-051a |*)
Theorem certificate_parse_of_serialize : forall f c enc,
  format_wf f = true -> write_certificate f c = Some enc ->
  read_certificate f enc = Some c.
Proof.
  intros f c enc Hwf Hw. unfold write_certificate in Hw.
  destruct (write_manifest_body f (certificate_subject c)) as [subject|] eqn:E1;
    [|discriminate].
  destruct (write_numeral f (certificate_checker c)) as [checker|] eqn:E2;
    [|discriminate].
  destruct (write_numeral f (certificate_profile c)) as [profile|] eqn:E3;
    [|discriminate].
  destruct (write_blob f (evidence_bytes_max f) (certificate_evidence c))
    as [evidence|] eqn:E4; [|discriminate].
  destruct (write_entries f (assumption_entries_max f) (certificate_assumptions c))
    as [entries|] eqn:E5; [|discriminate].
  destruct (Nat.leb (S (count (certificate_body subject checker profile evidence entries)))
                    (container_bytes_max f)) eqn:EB; [|discriminate].
  injection Hw as Hw. rewrite <- Hw.
  unfold read_certificate. rewrite count_cons. rewrite EB. rewrite eqb_self.
  unfold certificate_body.
  rewrite (read_write_manifest_body f (certificate_subject c) subject
             (checker ++ profile ++ evidence ++ entries) Hwf E1).
  rewrite (read_write_numeral f (certificate_checker c) checker
             (profile ++ evidence ++ entries) Hwf E2).
  rewrite (read_write_numeral f (certificate_profile c) profile
             (evidence ++ entries) Hwf E3).
  rewrite (read_write_blob f (evidence_bytes_max f) (certificate_evidence c)
             evidence entries Hwf E4).
  pose proof (read_write_entries f (assumption_entries_max f)
                (certificate_assumptions c) entries nil Hwf E5) as H5.
  rewrite app_nil_r in H5. rewrite H5. destruct c. reflexivity.
Qed.

(*| discharges: R-05-051a, R-05-051b |*)
Theorem certificate_serialize_of_parse : forall f bs c,
  format_wf f = true -> read_certificate f bs = Some c ->
  write_certificate f c = Some bs.
Proof.
  intros f bs c Hwf H. unfold read_certificate in H.
  destruct (Nat.leb (count bs) (container_bytes_max f)) eqn:EB; [|discriminate].
  destruct bs as [|tag rest]; [discriminate |].
  destruct (Nat.eqb tag (certificate_tag f)) eqn:ET; [|discriminate].
  destruct (read_manifest_body f rest) as [[subj r1]|] eqn:E1; [|discriminate].
  destruct (read_numeral f r1) as [[chk r2]|] eqn:E2; [|discriminate].
  destruct (read_numeral f r2) as [[prof r3]|] eqn:E3; [|discriminate].
  destruct (read_blob f (evidence_bytes_max f) r3) as [[ev r4]|] eqn:E4;
    [|discriminate].
  destruct (read_entries f (assumption_entries_max f) r4) as [[asm r5]|] eqn:E5;
    [|discriminate].
  destruct r5 as [|x t]; [|discriminate].
  injection H as H.
  destruct (write_read_manifest_body f rest subj r1 Hwf E1) as [e1 [Hb1 Hw1]].
  destruct (write_read_numeral f r1 chk r2 Hwf E2) as [e2 [Hb2 Hw2]].
  destruct (write_read_numeral f r2 prof r3 Hwf E3) as [e3 [Hb3 Hw3]].
  destruct (write_read_blob f (evidence_bytes_max f) r3 ev r4 Hwf E4)
    as [e4 [Hb4 Hw4]].
  destruct (write_read_entries f (assumption_entries_max f) r4 asm nil Hwf E5)
    as [e5 [Hb5 Hw5]].
  rewrite app_nil_r in Hb5.
  assert (Hrest : rest = certificate_body e1 e2 e3 e4 e5).
  { unfold certificate_body. rewrite Hb1. rewrite Hb2. rewrite Hb3. rewrite Hb4.
    rewrite Hb5. reflexivity. }
  unfold write_certificate. rewrite <- H.
  cbn [certificate_subject certificate_checker certificate_profile
       certificate_evidence certificate_assumptions].
  rewrite Hw1. rewrite Hw2. rewrite Hw3. rewrite Hw4. rewrite Hw5.
  rewrite count_cons in EB. rewrite Hrest in EB. rewrite EB.
  rewrite <- Hrest. rewrite (eqb_equal tag (certificate_tag f) ET). reflexivity.
Qed.

(*| discharges: R-05-051a |*)
Theorem certificate_has_one_admissible_encoding : forall f bs1 bs2 c,
  format_wf f = true ->
  read_certificate f bs1 = Some c -> read_certificate f bs2 = Some c -> bs1 = bs2.
Proof.
  intros f bs1 bs2 c Hwf H1 H2.
  pose proof (certificate_serialize_of_parse f bs1 c Hwf H1) as A.
  pose proof (certificate_serialize_of_parse f bs2 c Hwf H2) as B.
  rewrite A in B. injection B as B. exact B.
Qed.

Theorem certificate_encoding_is_injective : forall f c1 c2 enc,
  format_wf f = true ->
  write_certificate f c1 = Some enc -> write_certificate f c2 = Some enc -> c1 = c2.
Proof.
  intros f c1 c2 enc Hwf H1 H2.
  pose proof (certificate_parse_of_serialize f c1 enc Hwf H1) as A.
  pose proof (certificate_parse_of_serialize f c2 enc Hwf H2) as B.
  rewrite A in B. injection B as B. exact B.
Qed.

(*| discharges: R-05-051b |*)
Theorem certificate_refuses_trailing_bytes : forall f c enc extra,
  format_wf f = true -> write_certificate f c = Some enc -> extra <> nil ->
  read_certificate f (enc ++ extra) = None.
Proof.
  intros f c enc extra Hwf Hw Hx. unfold write_certificate in Hw.
  destruct (write_manifest_body f (certificate_subject c)) as [subject|] eqn:E1;
    [|discriminate].
  destruct (write_numeral f (certificate_checker c)) as [checker|] eqn:E2;
    [|discriminate].
  destruct (write_numeral f (certificate_profile c)) as [profile|] eqn:E3;
    [|discriminate].
  destruct (write_blob f (evidence_bytes_max f) (certificate_evidence c))
    as [evidence|] eqn:E4; [|discriminate].
  destruct (write_entries f (assumption_entries_max f) (certificate_assumptions c))
    as [entries|] eqn:E5; [|discriminate].
  destruct (Nat.leb (S (count (certificate_body subject checker profile evidence entries)))
                    (container_bytes_max f)) eqn:EB; [|discriminate].
  injection Hw as Hw. rewrite <- Hw. cbn [app]. unfold read_certificate.
  destruct (Nat.leb (count (certificate_tag f ::
              (certificate_body subject checker profile evidence entries ++ extra)))
              (container_bytes_max f)) eqn:EC; [|reflexivity].
  rewrite eqb_self. unfold certificate_body.
  repeat rewrite app_assoc_left.
  rewrite (read_write_manifest_body f (certificate_subject c) subject
             (checker ++ profile ++ evidence ++ entries ++ extra) Hwf E1).
  rewrite (read_write_numeral f (certificate_checker c) checker
             (profile ++ evidence ++ entries ++ extra) Hwf E2).
  rewrite (read_write_numeral f (certificate_profile c) profile
             (evidence ++ entries ++ extra) Hwf E3).
  rewrite (read_write_blob f (evidence_bytes_max f) (certificate_evidence c)
             evidence (entries ++ extra) Hwf E4).
  rewrite (read_write_entries f (assumption_entries_max f)
             (certificate_assumptions c) entries extra Hwf E5).
  destruct extra as [|x t]; [exfalso; apply Hx; reflexivity | reflexivity].
Qed.

(* -------------------------------------------------------------------------
   The join to ModuleAdmission's design gate. The container supplies bytes
   and the host supplies the trusted kernel receipt; a card-declared
   checker, profile, subject or assumption list is checked against the
   host's and never believed (R-12-085h).
   ------------------------------------------------------------------------- *)

Definition encoded_checks (b : Bounds) (expected : Manifest) (allowed : list nat)
    (checker profile : nat) (c : Certificate) (r : KernelReceipt) : list bool :=
  same (identity (certificate_subject c)) (identity expected) ::
  Nat.eqb (certificate_checker c) checker ::
  Nat.eqb (certificate_profile c) profile ::
  included (certificate_assumptions c) allowed ::
  admit_design b expected (certificate_subject c) (certificate_evidence c)
    allowed checker profile r :: nil.

Definition admit_encoded (f : FormatBounds) (b : Bounds) (expected : Manifest)
    (allowed : list nat) (checker profile : nat) (bytes : list nat)
    (r : KernelReceipt) : bool :=
  match read_certificate f bytes with
  | None => false
  | Some c => every (encoded_checks b expected allowed checker profile c r)
  end.

Theorem unparsed_bytes_admit_nothing : forall f b expected allowed chk prof bytes r,
  read_certificate f bytes = None ->
  admit_encoded f b expected allowed chk prof bytes r = false.
Proof.
  intros f b expected allowed chk prof bytes r H.
  unfold admit_encoded. rewrite H. reflexivity.
Qed.

(*| discharges: R-12-085g |*)
Theorem encoded_admission_pins_its_bytes :
  forall f b expected allowed chk prof bytes r c,
  format_wf f = true -> read_certificate f bytes = Some c ->
  admit_encoded f b expected allowed chk prof bytes r = true ->
  write_certificate f c = Some bytes /\
  identity (certificate_subject c) = identity expected /\
  included (certificate_assumptions c) allowed = true /\
  checked_evidence r = certificate_evidence c.
Proof.
  intros f b expected allowed chk prof bytes r c Hwf Hp Ha.
  unfold admit_encoded in Ha. rewrite Hp in Ha.
  split; [exact (certificate_serialize_of_parse f bytes c Hwf Hp) |].
  split; [apply same_equal; exact (every_at _ 0 Ha) |].
  split; [exact (every_at _ 3 Ha) |].
  apply (admitted_receipt_exact b expected (certificate_subject c)
           (certificate_evidence c) allowed chk prof r).
  exact (every_at _ 4 Ha).
Qed.

Theorem a_different_subject_is_refused :
  forall f b expected allowed chk prof bytes r c,
  read_certificate f bytes = Some c ->
  identity (certificate_subject c) <> identity expected ->
  admit_encoded f b expected allowed chk prof bytes r = false.
Proof.
  intros f b expected allowed chk prof bytes r c Hp Hne.
  unfold admit_encoded. rewrite Hp.
  destruct (every (encoded_checks b expected allowed chk prof c r)) eqn:E;
    [|reflexivity].
  exfalso. apply Hne. apply same_equal. exact (every_at _ 0 E).
Qed.

Theorem an_added_assumption_is_refused :
  forall f b expected allowed chk prof bytes r c,
  read_certificate f bytes = Some c ->
  included (certificate_assumptions c) allowed = false ->
  admit_encoded f b expected allowed chk prof bytes r = false.
Proof.
  intros f b expected allowed chk prof bytes r c Hp Hi.
  unfold admit_encoded. rewrite Hp.
  destruct (every (encoded_checks b expected allowed chk prof c r)) eqn:E;
    [|reflexivity].
  pose proof (every_at _ 3 E) as H3.
  change (included (certificate_assumptions c) allowed = true) in H3.
  rewrite H3 in Hi. discriminate.
Qed.

(* -------------------------------------------------------------------------
   Closed witnesses, the exact bytes they encode to, and the refused
   neighbours of the contract's Design row. Every literal in this file is
   below this line.
   ------------------------------------------------------------------------- *)

Definition bounds_witness : FormatBounds :=
  {| byte_values := 256; numeral_digits := 4; manifest_fields := 12;
     manifest_tag := 1; certificate_tag := 2; evidence_bytes_max := 8;
     assumption_entries_max := 3; manifest_bytes_max := 64;
     container_bytes_max := 128 |}.

Definition tight_witness : FormatBounds :=
  {| byte_values := 256; numeral_digits := 4; manifest_fields := 12;
     manifest_tag := 1; certificate_tag := 2; evidence_bytes_max := 1;
     assumption_entries_max := 0; manifest_bytes_max := 8;
     container_bytes_max := 8 |}.

Example bounds_witness_is_well_formed : format_wf bounds_witness = true.
Proof. reflexivity. Qed.

Definition certificate_witness : Certificate :=
  {| certificate_subject := manifest_fixture; certificate_checker := 1;
     certificate_profile := 2; certificate_evidence := 1 :: 2 :: nil;
     certificate_assumptions := nil |}.

Definition manifest_tail_witness : list nat :=
  1::2:: 1::3:: 1::4:: 1::5:: 1::6:: 1::7:: 1::8:: 1::9:: 1::10:: 1::11::
  1::12:: nil.
Definition manifest_body_witness : list nat := 1 :: 1 :: manifest_tail_witness.
Definition manifest_bytes_witness : list nat :=
  manifest_tag bounds_witness :: manifest_body_witness.
Definition certificate_tail_witness : list nat :=
  1::1:: 1::2:: 1::2::1::2:: 0:: nil.
Definition certificate_bytes_witness : list nat :=
  certificate_tag bounds_witness :: (manifest_body_witness ++ certificate_tail_witness).

Example manifest_serializes_to_these_bytes :
  write_manifest bounds_witness manifest_fixture = Some manifest_bytes_witness.
Proof. reflexivity. Qed.

Example manifest_round_trips :
  read_manifest bounds_witness manifest_bytes_witness = Some manifest_fixture.
Proof. reflexivity. Qed.

Example certificate_serializes_to_these_bytes :
  write_certificate bounds_witness certificate_witness = Some certificate_bytes_witness.
Proof. reflexivity. Qed.

Example certificate_round_trips :
  read_certificate bounds_witness certificate_bytes_witness = Some certificate_witness.
Proof. reflexivity. Qed.

(* Malformed bytes: a digit outside the declared radix. *)
Example malformed_digit_refused :
  read_manifest bounds_witness
    (manifest_tag bounds_witness :: 1 :: 256 :: manifest_tail_witness) = None.
Proof. reflexivity. Qed.

(* A non-canonical length form: the value one written with a redundant
   high-order zero digit, refused rather than normalized. *)
Example noncanonical_numeral_refused :
  read_manifest bounds_witness
    (manifest_tag bounds_witness :: 2 :: 1 :: 0 :: manifest_tail_witness) = None.
Proof. reflexivity. Qed.

(* The same value in its one admissible form is accepted. *)
Example canonical_numeral_accepted :
  read_manifest bounds_witness
    (manifest_tag bounds_witness :: 1 :: 1 :: manifest_tail_witness)
  = Some manifest_fixture.
Proof. reflexivity. Qed.

(* An over-long numeral: more digits than the declared digit bound. *)
Example oversized_numeral_refused :
  read_manifest bounds_witness
    (manifest_tag bounds_witness :: 5 :: 1 :: 0 :: 0 :: 0 :: 1 ::
     manifest_tail_witness) = None.
Proof. reflexivity. Qed.

Example trailing_byte_refused :
  read_manifest bounds_witness (manifest_bytes_witness ++ (0 :: nil)) = None.
Proof. reflexivity. Qed.

Example truncated_manifest_refused :
  read_manifest bounds_witness (manifest_tag bounds_witness :: 1 :: 1 :: nil) = None.
Proof. reflexivity. Qed.

Example wrong_record_tag_refused :
  read_manifest bounds_witness
    (certificate_tag bounds_witness :: manifest_body_witness) = None.
Proof. reflexivity. Qed.

(* An over-budget total: the declared manifest byte budget is a field. *)
Example over_budget_manifest_refused :
  write_manifest tight_witness manifest_fixture = None /\
  read_manifest tight_witness manifest_bytes_witness = None.
Proof. split; reflexivity. Qed.

Example certificate_trailing_byte_refused :
  read_certificate bounds_witness (certificate_bytes_witness ++ (0 :: nil)) = None.
Proof. reflexivity. Qed.

Definition oversized_evidence_certificate : Certificate :=
  {| certificate_subject := manifest_fixture; certificate_checker := 1;
     certificate_profile := 2;
     certificate_evidence := 1::2::3::4::5::6::7::8::9::nil;
     certificate_assumptions := nil |}.

Example over_budget_evidence_refused :
  write_certificate bounds_witness oversized_evidence_certificate = None.
Proof. reflexivity. Qed.

Definition many_assumptions_certificate : Certificate :=
  {| certificate_subject := manifest_fixture; certificate_checker := 1;
     certificate_profile := 2; certificate_evidence := 1 :: 2 :: nil;
     certificate_assumptions := 7 :: 8 :: 9 :: 10 :: nil |}.

Example over_budget_assumption_list_refused :
  write_certificate bounds_witness many_assumptions_certificate = None.
Proof. reflexivity. Qed.

Example over_declared_evidence_length_refused :
  read_certificate bounds_witness
    (certificate_tag bounds_witness ::
     (manifest_body_witness ++
      (1::1:: 1::2:: 1::9::1::2::3::4::5::6::7::8::9:: 0:: nil))) = None.
Proof. reflexivity. Qed.

(* The admission join: the positive case, then the Design row's refusals. *)
Example positive_encoded_admission :
  admit_encoded bounds_witness bounds_fixture manifest_fixture nil 1 2
    certificate_bytes_witness kernel_witness = true.
Proof. reflexivity. Qed.

Definition other_design_bytes : list nat :=
  certificate_tag bounds_witness ::
  ((1 :: 2 :: manifest_tail_witness) ++ certificate_tail_witness).

Example different_design_refused :
  admit_encoded bounds_witness bounds_fixture manifest_fixture nil 1 2
    other_design_bytes kernel_witness = false.
Proof. reflexivity. Qed.

Definition added_assumption_bytes : list nat :=
  certificate_tag bounds_witness ::
  (manifest_body_witness ++ (1::1:: 1::2:: 1::2::1::2:: 1::1:: 1::99:: nil)).

Example added_assumption_refused :
  admit_encoded bounds_witness bounds_fixture manifest_fixture nil 1 2
    added_assumption_bytes kernel_witness = false.
Proof. reflexivity. Qed.

Definition wrong_checker_bytes : list nat :=
  certificate_tag bounds_witness ::
  (manifest_body_witness ++ (1::9:: 1::2:: 1::2::1::2:: 0:: nil)).

Example wrong_checker_refused :
  admit_encoded bounds_witness bounds_fixture manifest_fixture nil 1 2
    wrong_checker_bytes kernel_witness = false.
Proof. reflexivity. Qed.

Definition wrong_profile_bytes : list nat :=
  certificate_tag bounds_witness ::
  (manifest_body_witness ++ (1::1:: 1::9:: 1::2::1::2:: 0:: nil)).

Example wrong_profile_refused :
  admit_encoded bounds_witness bounds_fixture manifest_fixture nil 1 2
    wrong_profile_bytes kernel_witness = false.
Proof. reflexivity. Qed.

Definition malformed_evidence_bytes : list nat :=
  certificate_tag bounds_witness ::
  (manifest_body_witness ++ (1::1:: 1::2:: 1::2::1::256:: 0:: nil)).

Example malformed_certificate_refused :
  admit_encoded bounds_witness bounds_fixture manifest_fixture nil 1 2
    malformed_evidence_bytes kernel_witness = false.
Proof. reflexivity. Qed.

(* The two budgets are separate, and the separation is the point: these
   bytes are admissible to the format and over ModuleAdmission's declared
   evidence budget, so the format accepts them and the design gate refuses. *)
Definition long_evidence_bytes : list nat :=
  certificate_tag bounds_witness ::
  (manifest_body_witness ++ (1::1:: 1::2:: 1::5::1::2::3::4::5:: 0:: nil)).

Example a_format_budget_is_not_an_admission_budget :
  read_certificate bounds_witness long_evidence_bytes =
    Some {| certificate_subject := manifest_fixture; certificate_checker := 1;
            certificate_profile := 2;
            certificate_evidence := 1::2::3::4::5::nil;
            certificate_assumptions := nil |} /\
  admit_encoded bounds_witness bounds_fixture manifest_fixture nil 1 2
    long_evidence_bytes (kernel_fixture nil (1::2::3::4::5::nil) 10 20 30) = false.
Proof. split; reflexivity. Qed.

Definition witness_FormatBounds : FormatBounds := bounds_witness.
Definition witness_Certificate : Certificate := certificate_witness.

Print Assumptions manifest_parse_of_serialize.
Print Assumptions manifest_serialize_of_parse.
Print Assumptions manifest_has_one_admissible_encoding.
Print Assumptions manifest_encoding_is_injective.
Print Assumptions manifest_refuses_trailing_bytes.
Print Assumptions certificate_parse_of_serialize.
Print Assumptions certificate_serialize_of_parse.
Print Assumptions certificate_has_one_admissible_encoding.
Print Assumptions certificate_encoding_is_injective.
Print Assumptions certificate_refuses_trailing_bytes.
Print Assumptions a_numeral_has_one_admissible_form.
Print Assumptions encoded_admission_pins_its_bytes.
Print Assumptions a_different_subject_is_refused.
Print Assumptions an_added_assumption_is_refused.
Print Assumptions unparsed_bytes_admit_nothing.
