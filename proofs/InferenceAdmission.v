(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   InferenceAdmission.v

   The inference server's session-open arithmetic as the register fixes it:
   R-12-084b's shape applied to R-12-085, the canonical model shape
   descriptor R-12-085 requires and R-05-051a, R-05-051b and R-05-051c
   govern, R-15-171's all-experts-resident condition with the fixed top-k
   work argument and its storage-boundary refusal, R-15-247p's bank grant as
   an explicit ceiling term with the admitted token rate derived from it,
   R-15-188's composition-time operating point read as a rate that follows
   no load signal, R-08-046 and R-08-047's bounded session pool with its
   typed exhausted verdict, R-12-085f's refusal to re-route an unqualified
   inference destination, and R-15-171a's per-member reading of the same
   rate on an ensemble.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not an
   implementation and not a measurement. Every quantity the register leaves
   to composition or to a design-space exploration is a field of a record
   rather than a literal: the field widths of the descriptor, the seven
   terms of the declared ceiling, the server's slot, worker set and pools,
   the per-token work constants, the residency declaration, and the bank
   grant itself. Nothing is admitted and nothing is axiomatized.

   composition_opening is the complete finite-residency and resource admission
   entry point; opening is its ceiling/resource core. checked_routed_work
   rejects invalid routes. No executable target server or measured rate is
   supplied by these Gallina definitions.

   What this file does not do. It performs no target run or measurement.
   The computed checks below are decided inside the kernel by conversion and
   print nothing; the gate's green line means compiled, axiom-free and
   enumerated rather than verified. No figure here is a performance claim,
   and the demo composition's magnitudes are arbitrary witness values.

   Every rate this file derives is symbolic. R-15-247p's bank grant is an
   output of the R-15-108 design-space exploration, which has not run, and
   the latency and density constants beneath it are measured at part
   qualification and not before. A grant is therefore a field, an admitted
   rate is arithmetic over a field, and symbolic arithmetic settles no
   physical admission. R-18-004a's floor and R-18-004b's supply figures are
   those entries' and this file carries none of them.

   Readings of the register this statement takes, each a reviewable judgment
   rather than a neutral transcription:

   1. The declared ceiling has exactly seven terms and they are R-12-085's
      own: the resident bytes, the context length, the quantization formats,
      the expert count, top-k, the KV footprint per token, and the
      R-15-247p bank grant. Six of them bound the model and the seventh is a
      supply term the composition declares, which is why the descriptor
      below carries six fields and the Ceiling record seven. No entry states
      that split; it is read from what a model can carry and reported.
   2. Top-k is an equality and the expert count is a bound. R-15-171 admits
      a mixture of experts only with every expert resident and top-k fixed,
      so the ceiling's top-k term is tested with equality and its
      expert-count term with an inequality, the residency condition being
      what bounds the count.
   3. Work per token is constant because the routed experts cost the same,
      and R-15-171 states the residency half of that and not the uniformity
      half. So the constancy theorem below is stated over an arbitrary
      per-expert cost and proved of a uniform one, all-residency is proved
      to make the specified cost uniform, and a mixture whose experts differ
      in width, every one of them resident, is exhibited and refuted. The
      second refutation is a gap this file reports rather than closes
      (gap d).
   4. R-12-085 says a model above the ceiling is answered when the session
      opens, where R-12-084b, whose shape it applies, says refused. This
      file takes the answer to be a typed refusal on R-12-084b's shape and
      checks that inherited refusal contract at the session boundary.
   5. Which class the KV cache sits on is undecided, so the per-token byte
      count the rate is derived from is a parameter and both arms are
      exhibited: the weight stream alone and the weight stream with the
      cache. R-18-004a places the model on the second class and fixes
      nothing about the cache, and the placement is the whole-program memory
      plan's (R-08-012a). Neither arm is normative here and the admitted
      rate differs between them.
   6. Above the grant is refused and never degraded. R-15-247p makes the
      token rate a composition-time constant of the bank grant a server is
      given rather than a performance property of the machine, and
      R-12-084b refuses at the session boundary rather than admitting
      against a slot no schedulability proof covers. That an admitted
      session runs at the composition constant and never at a reduced rate
      follows their combined session and fixed-rate contract.
   7. The rate reads the grant and the shape and no load signal. R-15-188
      makes each partition's operating point a composition-time constant and
      lets the shared resources never scale, so a rate moving with prompt
      length, queue depth or utilization would be the load-following that
      entry excludes.
   8. The reference descriptor codec has local round-trip and canonicity
      proofs. It is not a Narcissus-derived parser, which remains required
      by R-12-085 at the executable parser join. The model stays untrusted
      data. Every field of the Shape record below is a number, so nothing
      the decoder produces is code, and R-12-085's reading that
      proof-carrying weights are a category error needs no theorem here:
      what carries obligations is the server's kernels, which this file does
      not author.

   What this file deliberately does not author, with the entry that owes
   each decision:

   a. The Narcissus schema and generated parser correspondence to this
      bounded reference codec. No library derivation is claimed here.
   b. The executable server's correspondence to composition_opening and
      its symbolic fixed-rate resource contract.
   c. Which class the KV cache sits on, and so which arm of the per-token
      byte count the rate is derived from (reading 5). Owed at R-08-012a's
      plan or at a register act beside R-12-085.
   d. That a mixture's experts are of one declared width, which R-15-171's
      constant-work conclusion needs and its sentence does not state
      (reading 3). Owed at R-15-171.
   e. Whether a declared shape may state zero bytes per token. No entry
      forbids it and the derived rate would divide by zero, so the decision
      below refuses such a shape with a cause of its own, which is the
      arithmetic's domain condition and not an eighth ceiling term. No new
      register policy is needed to decline an undefined resource request.
   f. Every composition magnitude: the descriptor's field widths, the
      ceiling's seven values, the server's slot, worker set and pools, the
      session capacity, the per-token work constants, the residency
      declaration and the bank grant. The demo composition instantiates them
      with arbitrary witness values that carry no composition claim.
   g. The server's GEMM and attention kernels, their WCET derivation and
      their placement in an admitted slot. R-11-015's timing-annotation
      specification is not authored, so a slot's cost is a declared input
      here and never derived.
   h. The exhaustion action R-12-087 maps a full session pool to. This file
      states R-08-047's typed refusal at the binding and takes no
      detector-to-action mapping.
   i. Every measured quantity. R-18-004b's supply floors, R-15-247m's
      qualification constants and the R-15-108 exploration's outputs are
      their owners' and none is restated here.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary codec, cost function, opening step, rate
   function, dispatch or ensemble reduction, proved of the specification and
   refuted of an alternative construction the register's own sentence
   excludes. Inhabitation is concrete: a demo composition whose descriptor
   round-trips, whose model sits inside the declared ceiling and whose
   requested rate sits inside the derived one, with computed checks in the
   silent Example form for the admitting case, for each refusing case, and
   for the descriptor a trailing byte makes inadmissible.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-051a R-05-051b R-05-051c R-05-163 R-05-165 R-05-166 R-08-012a R-08-046
      R-08-047 R-11-015 R-12-087 R-12-084b R-12-085 R-12-085f R-15-108 R-15-171 R-15-171a
      R-15-172 R-15-247m R-15-247p R-15-188 R-15-238c R-18-004a R-18-004b
   SHA256: 76e74bc74bd94adad27f0848c35cd73611f372b7017a7c18343331e70d0bb83b
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.

(* -------------------------------------------------------------------------
   Arithmetic the codec and the rate derivation rest on. Each is proved here
   rather than imported under a name that moves between prover releases.
   ------------------------------------------------------------------------- *)

Lemma mod_256_lt : forall v : nat, v mod 256 < 256.
Proof. intro v. apply Nat.mod_upper_bound. discriminate. Qed.

Lemma split_256 : forall b u : nat,
  b < 256 -> (b + 256 * u) mod 256 = b /\ (b + 256 * u) / 256 = u.
Proof.
  intros b u Hb.
  pose proof (Nat.div_mod_eq (b + 256 * u) 256) as Hd.
  pose proof (mod_256_lt (b + 256 * u)) as Hm.
  split; lia.
Qed.

Lemma div_step : forall v p : nat, v < 256 * p -> v / 256 < p.
Proof.
  intros v p H.
  pose proof (Nat.div_mod_eq v 256) as Hd.
  pose proof (mod_256_lt v) as Hm.
  lia.
Qed.

Lemma pow_256_succ : forall w : nat, 256 ^ (S w) = 256 * 256 ^ w.
Proof. intro w. reflexivity. Qed.

(* The one fact the grant-to-rate derivation rests on: spending the derived
   rate's worth of bytes spends no more than the grant. *)
Lemma div_mul_le : forall g b : nat, 0 < b -> (g / b) * b <= g.
Proof.
  intros g b Hb.
  pose proof (Nat.div_mod_eq g b) as Hd.
  rewrite Nat.mul_comm. lia.
Qed.

(* =========================================================================
   Part 1. The wire, and the canonicity R-05-051a requires of a descriptor
   that serves an identity role.
   ========================================================================= *)

Definition Byte : Type := nat.

Definition byte_ok (b : Byte) : bool := b <? 256.

Definition bytes_ok (bs : list Byte) : bool := forallb byte_ok bs.

(* R-05-051b's schema, and the whole of this format's freedom: a finite list
   of field widths in a fixed order. There is no length form to choose, no
   presence encoding, no reserved run and no field a decoder may accept and
   ignore, because the schema carries nowhere to put one. *)
Definition Schema : Type := list nat.

Definition schema_bytes (sch : Schema) : nat := list_sum sch.

(* One field at its declared width, least significant byte first. The
   recursion is on the width, which is a schema constant, so the format is
   non-recursive in the sense R-12-085 asks for: no production of this
   grammar refers to itself and no parse step is selected by the input. *)
Fixpoint field_encode (w v : nat) : list Byte :=
  match w with
  | 0 => []
  | S w' => (v mod 256) :: field_encode w' (v / 256)
  end.

Fixpoint field_decode (w : nat) (bs : list Byte) : option (nat * list Byte) :=
  match w with
  | 0 => Some (0, bs)
  | S w' =>
      match bs with
      | [] => None
      | b :: t =>
          match field_decode w' t with
          | None => None
          | Some (v, r) => Some (b + 256 * v, r)
          end
      end
  end.

Definition field_fits (w v : nat) : bool := v <? 256 ^ w.

Fixpoint fields_encode (sch : Schema) (vs : list nat) : list Byte :=
  match sch, vs with
  | [], _ => []
  | w :: ws, v :: rest => field_encode w v ++ fields_encode ws rest
  | _ :: _, [] => []
  end.

Fixpoint fields_decode (sch : Schema) (bs : list Byte)
  : option (list nat * list Byte) :=
  match sch with
  | [] => Some ([], bs)
  | w :: ws =>
      match field_decode w bs with
      | None => None
      | Some (v, r) =>
          match fields_decode ws r with
          | None => None
          | Some (vs, r') => Some (v :: vs, r')
          end
      end
  end.

Fixpoint fields_fit (sch : Schema) (vs : list nat) : bool :=
  match sch, vs with
  | [], [] => true
  | w :: ws, v :: rest => field_fits w v && fields_fit ws rest
  | _, _ => false
  end.

(* The unfolding steps, each a conversion this file states once. They are
   written as rewrites rather than taken with a reduction tactic because a
   reduction over this format expands the base's numeral and turns a
   three-symbol goal into a thousand-symbol one. *)

Lemma field_encode_succ : forall w v : nat,
  field_encode (S w) v = (v mod 256) :: field_encode w (v / 256).
Proof. intros w v. reflexivity. Qed.

Lemma field_decode_zero : forall bs : list Byte,
  field_decode 0 bs = Some (0, bs).
Proof. intro bs. reflexivity. Qed.

Lemma field_decode_succ : forall (w b : nat) (t : list Byte),
  field_decode (S w) (b :: t)
  = match field_decode w t with
    | None => None
    | Some (v, r) => Some (b + 256 * v, r)
    end.
Proof. intros w b t. reflexivity. Qed.

(* `injection` normalizes the equations it produces, which over this format
   expands the base's numeral. These two read a constructor equality apart
   without touching either side. *)
Lemma some_pair_eq : forall (A B : Type) (a c : A) (b d : B),
  Some (a, b) = Some (c, d) -> a = c /\ b = d.
Proof. intros A B a c b d H. injection H as H1 H2. split; assumption. Qed.

Lemma field_decode_succ_some :
  forall (w b : nat) (t : list Byte) (v : nat) (r : list Byte),
    field_decode w t = Some (v, r) ->
    field_decode (S w) (b :: t) = Some (b + 256 * v, r).
Proof.
  intros w b t v r H. rewrite field_decode_succ. rewrite H. reflexivity.
Qed.

(* Both list identities are stated at Byte rather than taken polymorphically,
   because a polymorphic instance resolves at nat and leaves the rewritten
   goal spelling one list type where every other term spells the other. *)
Lemma cons_app : forall (x : Byte) (l r : list Byte),
  (x :: l) ++ r = x :: (l ++ r).
Proof. intros x l r. reflexivity. Qed.

Lemma app_assoc_byte : forall l m n : list Byte,
  (l ++ m) ++ n = l ++ (m ++ n).
Proof. intros l m n. symmetry. apply app_assoc. Qed.

Lemma fields_encode_cons :
  forall (w : nat) (ws : Schema) (v : nat) (vs : list nat),
    fields_encode (w :: ws) (v :: vs) = field_encode w v ++ fields_encode ws vs.
Proof. intros w ws v vs. reflexivity. Qed.

Lemma fields_decode_nil : forall bs : list Byte,
  fields_decode [] bs = Some ([], bs).
Proof. intro bs. reflexivity. Qed.

Lemma fields_decode_cons : forall (w : nat) (ws : Schema) (bs : list Byte),
  fields_decode (w :: ws) bs
  = match field_decode w bs with
    | None => None
    | Some (v, r) =>
        match fields_decode ws r with
        | None => None
        | Some (vs, r') => Some (v :: vs, r')
        end
    end.
Proof. intros w ws bs. reflexivity. Qed.

Lemma fields_fit_cons :
  forall (w : nat) (ws : Schema) (v : nat) (vs : list nat),
    fields_fit (w :: ws) (v :: vs) = andb (field_fits w v) (fields_fit ws vs).
Proof. intros w ws v vs. reflexivity. Qed.

Lemma schema_bytes_cons : forall (w : nat) (ws : Schema),
  schema_bytes (w :: ws) = w + schema_bytes ws.
Proof. intros w ws. reflexivity. Qed.

Lemma field_encode_length : forall w v : nat, length (field_encode w v) = w.
Proof.
  induction w as [ | w' IH ]; intro v.
  - reflexivity.
  - rewrite field_encode_succ. cbn [length]. rewrite IH. reflexivity.
Qed.

Lemma byte_ok_mod : forall v : nat, byte_ok (v mod 256) = true.
Proof. intro v. unfold byte_ok. apply Nat.ltb_lt. apply mod_256_lt. Qed.

Lemma field_encode_bytes_ok : forall w v : nat, bytes_ok (field_encode w v) = true.
Proof.
  induction w as [ | w' IH ]; intro v.
  - reflexivity.
  - unfold bytes_ok in *. rewrite field_encode_succ. cbn [forallb].
    rewrite byte_ok_mod. cbn [andb]. apply IH.
Qed.

Lemma field_decode_encode : forall (w v : nat) (r : list Byte),
  field_fits w v = true -> field_decode w (field_encode w v ++ r) = Some (v, r).
Proof.
  induction w as [ | w' IH ]; intros v r H.
  - unfold field_fits in H. apply Nat.ltb_lt in H.
    cbn [Nat.pow] in H.
    assert (Hz : v = 0) by lia. rewrite Hz. reflexivity.
  - unfold field_fits in H. apply Nat.ltb_lt in H.
    rewrite pow_256_succ in H.
    assert (Hq : field_fits w' (v / 256) = true).
    { unfold field_fits. apply Nat.ltb_lt. apply div_step. exact H. }
    assert (Hstep : field_decode (S w') (field_encode (S w') v ++ r)
                    = Some (v mod 256 + 256 * (v / 256), r)).
    { rewrite field_encode_succ. rewrite cons_app.
      apply field_decode_succ_some. apply IH. exact Hq. }
    pose proof (Nat.div_mod_eq v 256) as Hd.
    assert (Hv : v mod 256 + 256 * (v / 256) = v) by lia.
    rewrite Hstep. rewrite Hv. reflexivity.
Qed.

Lemma field_decode_rest_ok :
  forall (w : nat) (bs : list Byte) (v : nat) (r : list Byte),
    bytes_ok bs = true -> field_decode w bs = Some (v, r) -> bytes_ok r = true.
Proof.
  induction w as [ | w' IH ]; intros bs v r Hok Hdec.
  - rewrite field_decode_zero in Hdec.
    destruct (some_pair_eq _ _ _ _ _ _ Hdec) as [ _ Hr ].
    rewrite <- Hr. exact Hok.
  - destruct bs as [ | b t ]; [ discriminate | ].
    unfold bytes_ok in Hok. cbn [forallb] in Hok.
    apply andb_prop in Hok. destruct Hok as [ _ Htok ].
    rewrite field_decode_succ in Hdec.
    destruct (field_decode w' t) as [ [ u r' ] | ] eqn:E; [ | discriminate ].
    destruct (some_pair_eq _ _ _ _ _ _ Hdec) as [ _ Hr ]. rewrite <- Hr.
    exact (IH t u r' Htok E).
Qed.

(* Canonicity at one field: re-encoding a decoded field reproduces the bytes
   it was decoded from. *)
Lemma field_encode_decode :
  forall (w : nat) (bs : list Byte) (v : nat) (r : list Byte),
    bytes_ok bs = true -> field_decode w bs = Some (v, r) ->
    field_encode w v ++ r = bs.
Proof.
  induction w as [ | w' IH ]; intros bs v r Hok Hdec.
  - rewrite field_decode_zero in Hdec.
    destruct (some_pair_eq _ _ _ _ _ _ Hdec) as [ Hv Hr ].
    rewrite <- Hv. rewrite <- Hr. reflexivity.
  - destruct bs as [ | b t ]; [ discriminate | ].
    unfold bytes_ok in Hok. cbn [forallb] in Hok.
    apply andb_prop in Hok. destruct Hok as [ Hb Htok ].
    unfold byte_ok in Hb. apply Nat.ltb_lt in Hb.
    rewrite field_decode_succ in Hdec.
    destruct (field_decode w' t) as [ [ u r' ] | ] eqn:E; [ | discriminate ].
    destruct (some_pair_eq _ _ _ _ _ _ Hdec) as [ Hv Hr ].
    destruct (split_256 b u Hb) as [ Hm Hq ].
    rewrite field_encode_succ. rewrite cons_app.
    rewrite <- Hv. rewrite Hm. rewrite Hq.
    rewrite <- Hr. rewrite (IH t u r' Htok E). reflexivity.
Qed.

Lemma fields_encode_length : forall (sch : Schema) (vs : list nat),
  fields_fit sch vs = true -> length (fields_encode sch vs) = schema_bytes sch.
Proof.
  induction sch as [ | w ws IH ]; intros vs H.
  - reflexivity.
  - destruct vs as [ | v rest ]; [ discriminate | ].
    rewrite fields_fit_cons in H. apply andb_prop in H. destruct H as [ _ H2 ].
    rewrite fields_encode_cons. rewrite schema_bytes_cons.
    rewrite length_app. rewrite field_encode_length.
    rewrite (IH rest H2). reflexivity.
Qed.

Lemma fields_encode_bytes_ok : forall (sch : Schema) (vs : list nat),
  bytes_ok (fields_encode sch vs) = true.
Proof.
  induction sch as [ | w ws IH ]; intro vs.
  - reflexivity.
  - destruct vs as [ | v rest ]; [ reflexivity | ].
    rewrite fields_encode_cons. unfold bytes_ok. rewrite forallb_app.
    apply andb_true_iff. split.
    + apply field_encode_bytes_ok.
    + apply (IH rest).
Qed.

Lemma fields_decode_encode :
  forall (sch : Schema) (vs : list nat) (r : list Byte),
    fields_fit sch vs = true ->
    fields_decode sch (fields_encode sch vs ++ r) = Some (vs, r).
Proof.
  induction sch as [ | w ws IH ]; intros vs r H.
  - destruct vs as [ | v rest ]; [ reflexivity | discriminate ].
  - destruct vs as [ | v rest ]; [ discriminate | ].
    rewrite fields_fit_cons in H. apply andb_prop in H. destruct H as [ H1 H2 ].
    rewrite fields_encode_cons. rewrite app_assoc_byte.
    rewrite fields_decode_cons.
    rewrite (field_decode_encode w v (fields_encode ws rest ++ r) H1).
    rewrite (IH rest r H2). reflexivity.
Qed.

Lemma fields_encode_decode :
  forall (sch : Schema) (bs : list Byte) (vs : list nat) (r : list Byte),
    bytes_ok bs = true -> fields_decode sch bs = Some (vs, r) ->
    fields_encode sch vs ++ r = bs.
Proof.
  induction sch as [ | w ws IH ]; intros bs vs r Hok Hdec.
  - rewrite fields_decode_nil in Hdec.
    destruct (some_pair_eq _ _ _ _ _ _ Hdec) as [ Hv Hr ].
    rewrite <- Hv. rewrite <- Hr. reflexivity.
  - rewrite fields_decode_cons in Hdec.
    destruct (field_decode w bs) as [ [ v0 r0 ] | ] eqn:E1; [ | discriminate ].
    destruct (fields_decode ws r0) as [ [ vs0 r1 ] | ] eqn:E2; [ | discriminate ].
    destruct (some_pair_eq _ _ _ _ _ _ Hdec) as [ Hv Hr ].
    pose proof (field_decode_rest_ok w bs v0 r0 Hok E1) as Hr0.
    rewrite <- Hv. rewrite <- Hr. rewrite fields_encode_cons.
    rewrite app_assoc_byte. rewrite (IH r0 vs0 r1 Hr0 E2).
    exact (field_encode_decode w bs v0 r0 Hok E1).
Qed.

(* -------------------------------------------------------------------------
   R-05-051a's obligations, stated of an arbitrary codec so that a codec
   admitting slack can be exhibited and refuted rather than merely differing
   from the one this file defines.
   ------------------------------------------------------------------------- *)

Record Codec : Type := {
  cod_admissible : list Byte -> bool;
  cod_encode : list nat -> list Byte;
  cod_decode : list Byte -> option (list nat)
}.

(* R-05-051a's own sentence: re-encoding a decoded input returns that input
   unchanged. R-05-051b's rule that a non-canonical input is never
   normalized into the canonical encoding of the same value is that property
   read from the other side, a normalizing decoder being one that accepts an
   input it does not reproduce. *)
Definition ReEncodesItsBytes (c : Codec) : Prop :=
  forall (bs : list Byte) (vs : list nat),
    cod_admissible c bs = true -> cod_decode c bs = Some vs ->
    cod_encode c vs = bs.

Definition DecodeInjective (c : Codec) : Prop :=
  forall (bs1 bs2 : list Byte) (vs : list nat),
    cod_admissible c bs1 = true -> cod_admissible c bs2 = true ->
    cod_decode c bs1 = Some vs -> cod_decode c bs2 = Some vs -> bs1 = bs2.

Definition DecodesWhatItEncodes (c : Codec) (wf : list nat -> bool) : Prop :=
  forall vs : list nat, wf vs = true -> cod_decode c (cod_encode c vs) = Some vs.

(* R-05-051b's schema bound, as the property that decides it: the encoded
   length is a constant of the schema and not of the value. *)
Definition LengthIsASchemaConstant (c : Codec) (wf : list nat -> bool) : Prop :=
  forall vs1 vs2 : list nat,
    wf vs1 = true -> wf vs2 = true ->
    length (cod_encode c vs1) = length (cod_encode c vs2).

(*| discharges: R-05-051a |*)
Theorem re_encoding_its_bytes_gives_decode_injectivity :
  forall c : Codec, ReEncodesItsBytes c -> DecodeInjective c.
Proof.
  intros c H bs1 bs2 vs Ha1 Ha2 Hd1 Hd2.
  rewrite <- (H bs1 vs Ha1 Hd1). rewrite <- (H bs2 vs Ha2 Hd2). reflexivity.
Qed.

Definition schema_codec (sch : Schema) : Codec := {|
  cod_admissible := fun bs => bytes_ok bs && (length bs =? schema_bytes sch);
  cod_encode := fields_encode sch;
  cod_decode := fun bs =>
    match fields_decode sch bs with
    | Some (vs, []) => Some vs
    | _ => None
    end
|}.

(*| discharges: R-05-051a, R-05-051b |*)
Theorem the_schema_codec_re_encodes_its_bytes :
  forall sch : Schema, ReEncodesItsBytes (schema_codec sch).
Proof.
  intros sch bs vs Hadm Hdec. cbn [cod_admissible cod_decode schema_codec] in *.
  apply andb_prop in Hadm. destruct Hadm as [ Hok _ ].
  destruct (fields_decode sch bs) as [ [ vs0 rest ] | ] eqn:E; [ | discriminate ].
  destruct rest as [ | b t ]; [ | discriminate ].
  injection Hdec as Hv. cbn [cod_encode schema_codec]. rewrite <- Hv.
  pose proof (fields_encode_decode sch bs vs0 [] Hok E) as Hre.
  rewrite app_nil_r in Hre. exact Hre.
Qed.

(*| discharges: R-05-051a |*)
Theorem the_schema_codec_decode_is_injective :
  forall sch : Schema, DecodeInjective (schema_codec sch).
Proof.
  intro sch. apply re_encoding_its_bytes_gives_decode_injectivity.
  apply the_schema_codec_re_encodes_its_bytes.
Qed.

(*| discharges: R-05-051a |*)
Theorem the_schema_codec_decodes_what_it_encodes :
  forall sch : Schema, DecodesWhatItEncodes (schema_codec sch) (fields_fit sch).
Proof.
  intros sch vs H. cbn [cod_decode cod_encode schema_codec].
  pose proof (fields_decode_encode sch vs [] H) as Hd.
  rewrite app_nil_r in Hd. rewrite Hd. reflexivity.
Qed.

(*| discharges: R-05-051b |*)
Theorem the_schema_codec_length_is_a_schema_constant :
  forall sch : Schema, LengthIsASchemaConstant (schema_codec sch) (fields_fit sch).
Proof.
  intros sch vs1 vs2 H1 H2. cbn [cod_encode schema_codec].
  rewrite (fields_encode_length sch vs1 H1).
  rewrite (fields_encode_length sch vs2 H2). reflexivity.
Qed.

(*| discharges: R-05-051a, R-05-051b |*)
Theorem the_schema_codec_emits_admissible_bytes :
  forall (sch : Schema) (vs : list nat),
    fields_fit sch vs = true ->
    cod_admissible (schema_codec sch) (cod_encode (schema_codec sch) vs) = true.
Proof.
  intros sch vs H. cbn [cod_admissible cod_encode schema_codec].
  apply andb_true_iff. split.
  - apply fields_encode_bytes_ok.
  - apply Nat.eqb_eq. apply fields_encode_length. exact H.
Qed.

(* =========================================================================
   Part 2. The model shape descriptor, and the ceiling R-12-085 declares in
   its terms.
   ========================================================================= *)

(* The six terms a model carries. Every field is a number, so nothing the
   decoder produces is code and the model stays untrusted data (reading 8). *)
Record Shape : Type := {
  shape_resident_bytes : nat;
  shape_context_length : nat;
  shape_format : nat;
  shape_expert_count : nat;
  shape_top_k : nat;
  shape_kv_bytes_per_token : nat
}.

(* The field widths are a composition input and not a literal of this file. *)
Record Widths : Type := {
  w_resident_bytes : nat;
  w_context_length : nat;
  w_format : nat;
  w_expert_count : nat;
  w_top_k : nat;
  w_kv_bytes_per_token : nat
}.

Definition shape_schema (w : Widths) : Schema :=
  [ w_resident_bytes w; w_context_length w; w_format w;
    w_expert_count w; w_top_k w; w_kv_bytes_per_token w ].

Definition shape_fields (s : Shape) : list nat :=
  [ shape_resident_bytes s; shape_context_length s; shape_format s;
    shape_expert_count s; shape_top_k s; shape_kv_bytes_per_token s ].

Definition shape_of_fields (vs : list nat) : option Shape :=
  match vs with
  | [ a1; a2; a3; a4; a5; a6 ] => Some (Build_Shape a1 a2 a3 a4 a5 a6)
  | _ => None
  end.

Definition encode_shape (w : Widths) (s : Shape) : list Byte :=
  fields_encode (shape_schema w) (shape_fields s).

Definition decode_shape (w : Widths) (bs : list Byte) : option Shape :=
  match fields_decode (shape_schema w) bs with
  | Some (vs, []) => shape_of_fields vs
  | _ => None
  end.

Definition shape_fits (w : Widths) (s : Shape) : bool :=
  fields_fit (shape_schema w) (shape_fields s).

Lemma shape_of_fields_inverts : forall (vs : list nat) (s : Shape),
  shape_of_fields vs = Some s -> shape_fields s = vs.
Proof.
  intros vs s H.
  destruct vs as [ | a1 [ | a2 [ | a3 [ | a4 [ | a5 [ | a6 [ | a7 tl ]]]]]]];
    cbn [shape_of_fields] in H; try discriminate.
  injection H as H. rewrite <- H. reflexivity.
Qed.

(* The descriptor's canonicity theorem, which is what lets it name a model
   on an identity-consuming path at all (R-05-051c). *)
(*| discharges: R-05-051a, R-12-085 |*)
Theorem the_shape_descriptor_re_encodes_its_bytes :
  forall (w : Widths) (bs : list Byte) (s : Shape),
    bytes_ok bs = true -> decode_shape w bs = Some s -> encode_shape w s = bs.
Proof.
  intros w bs s Hok Hdec. unfold decode_shape in Hdec.
  destruct (fields_decode (shape_schema w) bs) as [ [ vs rest ] | ] eqn:E;
    [ | discriminate ].
  destruct rest as [ | b t ]; [ | discriminate ].
  unfold encode_shape. rewrite (shape_of_fields_inverts vs s Hdec).
  pose proof (fields_encode_decode (shape_schema w) bs vs [] Hok E) as Hre.
  rewrite app_nil_r in Hre. exact Hre.
Qed.

(*| discharges: R-05-051a, R-12-085 |*)
Theorem the_shape_descriptor_decode_is_injective :
  forall (w : Widths) (bs1 bs2 : list Byte) (s : Shape),
    bytes_ok bs1 = true -> bytes_ok bs2 = true ->
    decode_shape w bs1 = Some s -> decode_shape w bs2 = Some s -> bs1 = bs2.
Proof.
  intros w bs1 bs2 s H1 H2 D1 D2.
  rewrite <- (the_shape_descriptor_re_encodes_its_bytes w bs1 s H1 D1).
  rewrite <- (the_shape_descriptor_re_encodes_its_bytes w bs2 s H2 D2).
  reflexivity.
Qed.

(*| discharges: R-05-051a |*)
Theorem the_shape_descriptor_decodes_what_it_encodes :
  forall (w : Widths) (s : Shape),
    shape_fits w s = true -> decode_shape w (encode_shape w s) = Some s.
Proof.
  intros w s H. unfold decode_shape, encode_shape, shape_fits in *.
  pose proof (fields_decode_encode (shape_schema w) (shape_fields s) [] H) as Hd.
  rewrite app_nil_r in Hd. rewrite Hd. destruct s. reflexivity.
Qed.

(*| discharges: R-05-051b |*)
Theorem the_shape_descriptor_length_is_a_schema_constant :
  forall (w : Widths) (s1 s2 : Shape),
    shape_fits w s1 = true -> shape_fits w s2 = true ->
    length (encode_shape w s1) = length (encode_shape w s2).
Proof.
  intros w s1 s2 H1 H2. unfold encode_shape, shape_fits in *.
  rewrite (fields_encode_length (shape_schema w) (shape_fields s1) H1).
  rewrite (fields_encode_length (shape_schema w) (shape_fields s2) H2).
  reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The declared ceiling: R-12-085's seven terms, six bounding the model and
   the seventh the supply the composition grants (reading 1).
   ------------------------------------------------------------------------- *)

Record Ceiling : Type := {
  max_resident_bytes : nat;
  max_context_length : nat;
  admitted_formats : list nat;
  max_expert_count : nat;
  fixed_top_k : nat;
  max_kv_bytes_per_token : nat;
  ceiling_grant : nat
}.

(* The typed verdict's causes. A refusal names its term, which is what makes
   R-08-047's verdict a verdict rather than a bit. *)
Inductive Refusal : Type :=
| DescriptorNotCanonical
| ResidentBytesAboveCeiling
| ContextAboveCeiling
| FormatNotAdmitted
| ExpertCountAboveCeiling
| TopKNotTheFixedValue
| KvPerTokenAboveCeiling
| PerTokenBytesNotDeclared
| SessionPoolExhausted
| TokenRateAboveGrant
| ExpertNotResident
| RoutedFetchAcrossStorage
| RouteNotQualified.

Inductive Verdict : Type :=
| Admitted : nat -> Verdict
| Refused : Refusal -> Verdict.

Definition format_admitted (cl : Ceiling) (f : nat) : bool :=
  existsb (Nat.eqb f) (admitted_formats cl).

(* Top-k is tested with equality and the expert count with an inequality
   (reading 2). *)
Definition inside_ceiling (cl : Ceiling) (s : Shape) : bool :=
  (shape_resident_bytes s <=? max_resident_bytes cl)
  && (shape_context_length s <=? max_context_length cl)
  && format_admitted cl (shape_format s)
  && (shape_expert_count s <=? max_expert_count cl)
  && (shape_top_k s =? fixed_top_k cl)
  && (shape_kv_bytes_per_token s <=? max_kv_bytes_per_token cl).

Definition why_refused (cl : Ceiling) (s : Shape) : option Refusal :=
  if shape_resident_bytes s <=? max_resident_bytes cl
  then if shape_context_length s <=? max_context_length cl
  then if format_admitted cl (shape_format s)
  then if shape_expert_count s <=? max_expert_count cl
  then if shape_top_k s =? fixed_top_k cl
  then if shape_kv_bytes_per_token s <=? max_kv_bytes_per_token cl
  then None
  else Some KvPerTokenAboveCeiling
  else Some TopKNotTheFixedValue
  else Some ExpertCountAboveCeiling
  else Some FormatNotAdmitted
  else Some ContextAboveCeiling
  else Some ResidentBytesAboveCeiling.

(*| discharges: R-12-085 |*)
Theorem the_ceiling_verdict_names_its_term : forall (cl : Ceiling) (s : Shape),
  why_refused cl s = None <-> inside_ceiling cl s = true.
Proof.
  intros cl s. unfold why_refused, inside_ceiling.
  destruct (shape_resident_bytes s <=? max_resident_bytes cl),
           (shape_context_length s <=? max_context_length cl),
           (format_admitted cl (shape_format s)),
           (shape_expert_count s <=? max_expert_count cl),
           (shape_top_k s =? fixed_top_k cl),
           (shape_kv_bytes_per_token s <=? max_kv_bytes_per_token cl);
    cbn; split; intros H; try discriminate; reflexivity.
Qed.

(* =========================================================================
   Part 3. Residency, the fixed top-k work argument, and the storage
   boundary (R-15-171).
   ========================================================================= *)

Definition Residency : Type := nat -> bool.

Definition Routing : Type := list nat.

Definition ExpertCost : Type := nat -> nat.

Record Costs : Type := {
  dense_work_per_token : nat;   (* the shared trunk, which routing does not select *)
  expert_work_per_token : nat;  (* one routed expert's work *)
  fetch_penalty : nat           (* what a non-resident expert would add *)
}.

Definition AllExpertsResident (s : Shape) (res : Residency) : Prop :=
  forall e : nat, e < shape_expert_count s -> res e = true.

Definition routing_ok (s : Shape) (r : Routing) : bool :=
  (length r =? shape_top_k s)
  && forallb (fun e => e <? shape_expert_count s) r.

Fixpoint routed_work (cost : ExpertCost) (r : Routing) : nat :=
  match r with
  | [] => 0
  | e :: t => cost e + routed_work cost t
  end.

Definition work_per_token (co : Costs) (cost : ExpertCost) (r : Routing) : nat :=
  dense_work_per_token co + routed_work cost r.

(* The cost the specification gives a routed expert: its work, plus what a
   fetch would add if the composition had not declared it resident. *)
Definition resident_cost (co : Costs) (res : Residency) : ExpertCost :=
  fun e => expert_work_per_token co + (if res e then 0 else fetch_penalty co).

Definition UniformOver (s : Shape) (cost : ExpertCost) : Prop :=
  forall e1 e2 : nat,
    e1 < shape_expert_count s -> e2 < shape_expert_count s -> cost e1 = cost e2.

(* R-15-171's own conclusion: work per token is constant regardless of which
   experts route. *)
Definition WorkIsRoutingBlind (s : Shape) (W : Routing -> nat) : Prop :=
  forall r1 r2 : Routing,
    routing_ok s r1 = true -> routing_ok s r2 = true -> W r1 = W r2.

Lemma routed_work_uniform :
  forall (s : Shape) (cost : ExpertCost) (k : nat) (r : Routing),
    (forall e : nat, e < shape_expert_count s -> cost e = k) ->
    forallb (fun e => e <? shape_expert_count s) r = true ->
    routed_work cost r = length r * k.
Proof.
  intros s cost k r Hk. induction r as [ | e t IH ]; intro Hall.
  - reflexivity.
  - cbn [forallb] in Hall. apply andb_prop in Hall.
    destruct Hall as [ He Ht ]. apply Nat.ltb_lt in He.
    change (routed_work cost (e :: t)) with (cost e + routed_work cost t).
    change (length (e :: t)) with (S (length t)).
    rewrite (Hk e He). rewrite (IH Ht).
    rewrite Nat.mul_succ_l. apply Nat.add_comm.
Qed.

(*| discharges: R-15-171 |*)
Theorem a_uniform_expert_cost_makes_work_per_token_constant :
  forall (co : Costs) (s : Shape) (cost : ExpertCost),
    0 < shape_expert_count s -> UniformOver s cost ->
    WorkIsRoutingBlind s (work_per_token co cost).
Proof.
  intros co s cost Hpos Hu r1 r2 H1 H2.
  assert (Hk : forall e : nat, e < shape_expert_count s -> cost e = cost 0).
  { intros e He. apply Hu; [ exact He | exact Hpos ]. }
  unfold routing_ok in H1, H2.
  apply andb_prop in H1. destruct H1 as [ Hlen1 Hall1 ].
  apply andb_prop in H2. destruct H2 as [ Hlen2 Hall2 ].
  apply Nat.eqb_eq in Hlen1. apply Nat.eqb_eq in Hlen2.
  unfold work_per_token.
  rewrite (routed_work_uniform s cost (cost 0) r1 Hk Hall1).
  rewrite (routed_work_uniform s cost (cost 0) r2 Hk Hall2).
  rewrite Hlen1. rewrite Hlen2. reflexivity.
Qed.

(*| discharges: R-15-171 |*)
Theorem all_experts_resident_makes_the_cost_uniform :
  forall (co : Costs) (s : Shape) (res : Residency),
    AllExpertsResident s res -> UniformOver s (resident_cost co res).
Proof.
  intros co s res Hres e1 e2 H1 H2. unfold resident_cost.
  rewrite (Hres e1 H1). rewrite (Hres e2 H2). reflexivity.
Qed.

(* R-15-171 read whole: every expert resident and top-k fixed make work per
   token a constant of the composition. *)
(*| discharges: R-15-171, R-12-085 |*)
Theorem residency_and_fixed_top_k_make_work_per_token_constant :
  forall (co : Costs) (s : Shape) (res : Residency),
    0 < shape_expert_count s -> AllExpertsResident s res ->
    WorkIsRoutingBlind s (work_per_token co (resident_cost co res)).
Proof.
  intros co s res Hpos Hres.
  apply a_uniform_expert_cost_makes_work_per_token_constant; [ exact Hpos | ].
  apply all_experts_resident_makes_the_cost_uniform. exact Hres.
Qed.

(* -------------------------------------------------------------------------
   The storage boundary. R-15-171 refuses a routed fetch across it, an
   input-dependent fill schedule being a timing channel and an unbounded
   admission term at once.
   ------------------------------------------------------------------------- *)

Inductive Fetch : Type :=
| FromResidentBank : nat -> Fetch
| FetchRefused : Refusal -> Fetch
| FromStorage : nat -> Fetch.   (* the construction R-15-171 excludes *)

Definition serve (res : Residency) (e : nat) : Fetch :=
  if res e then FromResidentBank e else FetchRefused RoutedFetchAcrossStorage.

Definition NoRoutedFetchCrossesStorage (f : nat -> Fetch) : Prop :=
  forall e a : nat, f e <> FromStorage a.

(*| discharges: R-15-171 |*)
Theorem routed_fetch_across_the_storage_boundary_is_refused :
  forall res : Residency, NoRoutedFetchCrossesStorage (serve res).
Proof.
  intros res e a. unfold serve. destruct (res e); discriminate.
Qed.

(* The refusal is typed and names its cause, which a boolean verdict cannot
   do. That a verdict cannot then be dropped is R-08-047's obligation on the
   binding path and is not stated here. *)
Definition forgets_the_cause (f : Fetch) : bool :=
  match f with FromResidentBank _ => true | _ => false end.

(*| discharges: R-08-047 |*)
Theorem a_boolean_verdict_loses_the_refusal_cause :
  forgets_the_cause (FetchRefused RoutedFetchAcrossStorage)
    = forgets_the_cause (FetchRefused ExpertNotResident)
  /\ FetchRefused RoutedFetchAcrossStorage <> FetchRefused ExpertNotResident.
Proof. split; [ reflexivity | discriminate ]. Qed.

(* =========================================================================
   Part 4. The bank grant, and the admitted token rate derived from it
   (R-15-247p).
   ========================================================================= *)

(* Which class the KV cache sits on is undecided, so the per-token byte
   count is a parameter and both arms are exhibited below (reading 5). *)
Definition PerTokenBytes : Type := Shape -> nat.

Definition weights_and_cache : PerTokenBytes :=
  fun s => shape_resident_bytes s + shape_kv_bytes_per_token s.

Definition weights_only : PerTokenBytes :=
  fun s => shape_resident_bytes s.

(* R-15-247p: the token rate is a composition-time constant of the grant. *)
Definition admitted_rate (bpt : PerTokenBytes) (cl : Ceiling) (s : Shape) : nat :=
  ceiling_grant cl / bpt s.

Definition WithinTheGrant (bpt : PerTokenBytes) (cl : Ceiling) (s : Shape)
                          (r : nat) : Prop :=
  r * bpt s <= ceiling_grant cl.

(*| discharges: R-15-247p |*)
Theorem the_derived_rate_spends_no_more_than_the_grant :
  forall (bpt : PerTokenBytes) (cl : Ceiling) (s : Shape),
    0 < bpt s -> WithinTheGrant bpt cl s (admitted_rate bpt cl s).
Proof.
  intros bpt cl s H. unfold WithinTheGrant, admitted_rate.
  apply div_mul_le. exact H.
Qed.

(* Both arms of reading 5 satisfy the same bound and they are not the same
   rate; neither is normative here. *)
(*| discharges: R-15-247p |*)
Theorem both_cache_placements_stay_inside_the_grant :
  forall (cl : Ceiling) (s : Shape),
    0 < weights_only s -> 0 < weights_and_cache s ->
    WithinTheGrant weights_only cl s (admitted_rate weights_only cl s)
    /\ WithinTheGrant weights_and_cache cl s
         (admitted_rate weights_and_cache cl s).
Proof.
  intros cl s H1 H2.
  split; apply the_derived_rate_spends_no_more_than_the_grant; assumption.
Qed.

(* R-15-188's operating point read onto the rate: no load signal reaches it. *)
Record Load : Type := {
  load_prompt_tokens : nat;
  load_queue_depth : nat;
  load_utilization : nat
}.

Definition RateIsLoadBlind (rate : Ceiling -> Shape -> Load -> nat) : Prop :=
  forall (cl : Ceiling) (s : Shape) (l1 l2 : Load), rate cl s l1 = rate cl s l2.

Definition composed_rate (bpt : PerTokenBytes)
  : Ceiling -> Shape -> Load -> nat :=
  fun cl s _ => admitted_rate bpt cl s.

(*| discharges: R-15-188, R-15-247p |*)
Theorem the_admitted_rate_follows_no_load_signal :
  forall bpt : PerTokenBytes, RateIsLoadBlind (composed_rate bpt).
Proof. intros bpt cl s l1 l2. reflexivity. Qed.

(* =========================================================================
   Part 5. The session-open decision: R-12-084b's shape applied to R-12-085.
   ========================================================================= *)

(* Fixed at composition. R-15-172 books the pooling tax that makes these
   sized to their peak rather than to an average. *)
Record Server : Type := {
  server_slot : nat;
  server_workers : list nat;
  server_pool_bytes : nat;
  server_session_capacity : nat   (* R-08-046's declared fixed capacity *)
}.

(* The one runtime-varying quantity: the bounded pool's occupancy. *)
Record Sessions : Type := { sessions_open : nat }.

Record Request : Type := {
  req_descriptor : list Byte;
  req_tokens_per_second : nat
}.

Record Composition : Type := {
  comp_widths : Widths;
  comp_ceiling : Ceiling;
  comp_costs : Costs;
  comp_residency : Residency;
  comp_bytes_per_token : PerTokenBytes
}.

Record Step : Type := {
  step_server : Server;
  step_sessions : Sessions;
  step_verdict : Verdict
}.

Definition Opening : Type := Server -> Sessions -> Request -> Step.

Definition opening (c : Composition) : Opening :=
  fun srv st q =>
    match decode_shape (comp_widths c) (req_descriptor q) with
    | None => Build_Step srv st (Refused DescriptorNotCanonical)
    | Some s =>
        match why_refused (comp_ceiling c) s with
        | Some why => Build_Step srv st (Refused why)
        | None =>
            if 0 <? comp_bytes_per_token c s
            then
              if sessions_open st <? server_session_capacity srv
              then
                if req_tokens_per_second q
                     <=? admitted_rate (comp_bytes_per_token c) (comp_ceiling c) s
                then Build_Step srv (Build_Sessions (S (sessions_open st)))
                       (Admitted (admitted_rate (comp_bytes_per_token c)
                                                (comp_ceiling c) s))
                else Build_Step srv st (Refused TokenRateAboveGrant)
              else Build_Step srv st (Refused SessionPoolExhausted)
            else Build_Step srv st (Refused PerTokenBytesNotDeclared)
        end
    end.

(* The obligations the three items put on that step. *)

Definition FixedAtComposition (step : Opening) : Prop :=
  forall (srv : Server) (st : Sessions) (q : Request),
    step_server (step srv st q) = srv.

Definition RefusesAboveCeiling (c : Composition) (step : Opening) : Prop :=
  forall (srv : Server) (st : Sessions) (q : Request) (s : Shape),
    decode_shape (comp_widths c) (req_descriptor q) = Some s ->
    inside_ceiling (comp_ceiling c) s = false ->
    exists why : Refusal, step_verdict (step srv st q) = Refused why.

Definition NeverDegrades (step : Opening) : Prop :=
  forall (srv : Server) (st : Sessions) (q : Request) (r : nat),
    step_verdict (step srv st q) = Admitted r ->
    req_tokens_per_second q <= r.

Definition GrantBounded (c : Composition) (step : Opening) : Prop :=
  forall (srv : Server) (st : Sessions) (q : Request) (s : Shape) (r : nat),
    decode_shape (comp_widths c) (req_descriptor q) = Some s ->
    step_verdict (step srv st q) = Admitted r ->
    r * comp_bytes_per_token c s <= ceiling_grant (comp_ceiling c).

Definition PoolBounded (step : Opening) : Prop :=
  forall (srv : Server) (st : Sessions) (q : Request),
    sessions_open st <= server_session_capacity srv ->
    sessions_open (step_sessions (step srv st q)) <= server_session_capacity srv.

Definition FullPoolDeclines (c : Composition) (step : Opening) : Prop :=
  forall (srv : Server) (st : Sessions) (q : Request) (s : Shape),
    decode_shape (comp_widths c) (req_descriptor q) = Some s ->
    inside_ceiling (comp_ceiling c) s = true ->
    0 < comp_bytes_per_token c s ->
    server_session_capacity srv <= sessions_open st ->
    step_verdict (step srv st q) = Refused SessionPoolExhausted.

(* S1 (R-12-084b, R-12-085, R-15-172): the slot, the worker set and the
   pools are what the composition fixed, and opening a session moves none of
   them. Nothing is elastic. *)
(*| discharges: R-12-084b, R-12-085, R-15-172 |*)
Theorem the_server_is_fixed_at_composition :
  forall c : Composition, FixedAtComposition (opening c).
Proof.
  intros c srv st q. unfold opening.
  destruct (decode_shape (comp_widths c) (req_descriptor q)) as [ s | ];
    [ | reflexivity ].
  destruct (why_refused (comp_ceiling c) s) as [ why | ]; [ reflexivity | ].
  destruct (0 <? comp_bytes_per_token c s); [ | reflexivity ].
  destruct (sessions_open st <? server_session_capacity srv); [ | reflexivity ].
  destruct (req_tokens_per_second q
            <=? admitted_rate (comp_bytes_per_token c) (comp_ceiling c) s);
    reflexivity.
Qed.

(* S2 (R-12-084b, R-12-085, R-15-238c): a model above the declared ceiling
   is answered at the session boundary, with the term it missed. *)
(*| discharges: R-12-084b, R-12-085, R-15-238c |*)
Theorem a_model_above_the_ceiling_is_refused_when_the_session_opens :
  forall c : Composition, RefusesAboveCeiling c (opening c).
Proof.
  intros c srv st q s Hdec Hout. unfold opening. rewrite Hdec.
  destruct (why_refused (comp_ceiling c) s) as [ why | ] eqn:E.
  - exists why. reflexivity.
  - apply (the_ceiling_verdict_names_its_term (comp_ceiling c) s) in E.
    rewrite E in Hout. discriminate.
Qed.

(* S3 (R-15-247p): a session above the grant is refused and never admitted
   at a reduced rate. *)
(*| discharges: R-15-247p, R-12-084b |*)
Theorem a_rate_above_the_grant_is_refused_and_not_degraded :
  forall c : Composition, NeverDegrades (opening c).
Proof.
  intros c srv st q r H. unfold opening in H.
  destruct (decode_shape (comp_widths c) (req_descriptor q)) as [ s | ];
    [ | cbn [step_verdict] in H; discriminate ].
  destruct (why_refused (comp_ceiling c) s) as [ why | ];
    [ cbn [step_verdict] in H; discriminate | ].
  destruct (0 <? comp_bytes_per_token c s);
    [ | cbn [step_verdict] in H; discriminate ].
  destruct (sessions_open st <? server_session_capacity srv);
    [ | cbn [step_verdict] in H; discriminate ].
  destruct (req_tokens_per_second q
            <=? admitted_rate (comp_bytes_per_token c) (comp_ceiling c) s) eqn:E;
    [ | cbn [step_verdict] in H; discriminate ].
  cbn [step_verdict] in H. injection H as H. rewrite <- H.
  apply Nat.leb_le. exact E.
Qed.

(* S4 (R-15-247p): the rate an admitted session receives is the one the
   grant derives, so no admitted session spends more than the grant. *)
(*| discharges: R-15-247p |*)
Theorem no_admitted_session_spends_more_than_the_grant :
  forall c : Composition, GrantBounded c (opening c).
Proof.
  intros c srv st q s r Hdec H. unfold opening in H. rewrite Hdec in H.
  destruct (why_refused (comp_ceiling c) s) as [ why | ];
    [ cbn [step_verdict] in H; discriminate | ].
  destruct (0 <? comp_bytes_per_token c s) eqn:Eb;
    [ | cbn [step_verdict] in H; discriminate ].
  destruct (sessions_open st <? server_session_capacity srv);
    [ | cbn [step_verdict] in H; discriminate ].
  destruct (req_tokens_per_second q
            <=? admitted_rate (comp_bytes_per_token c) (comp_ceiling c) s);
    [ | cbn [step_verdict] in H; discriminate ].
  cbn [step_verdict] in H. injection H as H. rewrite <- H.
  apply the_derived_rate_spends_no_more_than_the_grant.
  apply Nat.ltb_lt. exact Eb.
Qed.

(* S5 (R-08-046, R-08-047): the session pool is bounded, and a full pool
   declines the binding rather than borrowing or overcommitting. *)
(*| discharges: R-08-046, R-08-047 |*)
Theorem the_session_pool_never_exceeds_its_declared_capacity :
  forall c : Composition, PoolBounded (opening c).
Proof.
  intros c srv st q Hst. unfold opening.
  destruct (decode_shape (comp_widths c) (req_descriptor q)) as [ s | ];
    [ | exact Hst ].
  destruct (why_refused (comp_ceiling c) s) as [ why | ]; [ exact Hst | ].
  destruct (0 <? comp_bytes_per_token c s); [ | exact Hst ].
  destruct (sessions_open st <? server_session_capacity srv) eqn:Ef;
    [ | exact Hst ].
  destruct (req_tokens_per_second q
            <=? admitted_rate (comp_bytes_per_token c) (comp_ceiling c) s);
    [ | exact Hst ].
  cbn [step_sessions sessions_open].
  apply Nat.ltb_lt in Ef. lia.
Qed.

(*| discharges: R-08-046, R-08-047 |*)
Theorem a_full_session_pool_declines_the_binding :
  forall c : Composition, FullPoolDeclines c (opening c).
Proof.
  intros c srv st q s Hdec Hin Hpos Hfull. unfold opening. rewrite Hdec.
  destruct (why_refused (comp_ceiling c) s) as [ why | ] eqn:E.
  - apply (the_ceiling_verdict_names_its_term (comp_ceiling c) s) in Hin.
    rewrite Hin in E. discriminate.
  - destruct (0 <? comp_bytes_per_token c s) eqn:Eb.
    + destruct (sessions_open st <? server_session_capacity srv) eqn:Ef.
      * apply Nat.ltb_lt in Ef. lia.
      * reflexivity.
    + apply Nat.ltb_lt in Hpos. rewrite Hpos in Eb. discriminate.
Qed.

(* =========================================================================
   Part 6. The inference routes (R-12-085f): an unqualified destination is
   refused and the request reaches no other one implicitly.
   ========================================================================= *)

Inductive Route : Type := SoftwareServer | ModuleBroker | RemoteEndpoint.

Definition Qualified : Type := Route -> bool.

Definition dispatch (qual : Qualified) (rt : Route) : option Route :=
  if qual rt then Some rt else None.

Definition NoImplicitFallback (d : Route -> option Route) : Prop :=
  forall rt served : Route, d rt = Some served -> served = rt.

(*| discharges: R-12-085f |*)
Theorem an_unqualified_route_reaches_no_other_destination :
  forall qual : Qualified, NoImplicitFallback (dispatch qual).
Proof.
  intros qual rt served H. unfold dispatch in H.
  destruct (qual rt); [ injection H as H; symmetry; exact H | discriminate ].
Qed.

(* =========================================================================
   Part 7. The same rate on an ensemble (R-15-171a): a constant of each
   member's own grant, never of their sum.
   ========================================================================= *)

Record Member : Type := {
  member_grant : nat;
  member_bytes_per_token : nat
}.

Definition member_rate (m : Member) : nat :=
  member_grant m / member_bytes_per_token m.

Fixpoint ensemble_rate (ms : list Member) : option nat :=
  match ms with
  | [] => None
  | m :: t =>
      match ensemble_rate t with
      | None => Some (member_rate m)
      | Some r => Some (Nat.min (member_rate m) r)
      end
  end.

Definition NoAboveAnyMember (f : list Member -> option nat) : Prop :=
  forall (ms : list Member) (m : Member) (r : nat),
    In m ms -> f ms = Some r -> r <= member_rate m.

Lemma ensemble_rate_none : forall ms : list Member,
  ensemble_rate ms = None -> ms = [].
Proof.
  intros ms H. destruct ms as [ | m t ]; [ reflexivity | ].
  cbn [ensemble_rate] in H. destruct (ensemble_rate t); discriminate.
Qed.

(*| discharges: R-15-171a |*)
Theorem an_ensemble_rate_exceeds_no_member_rate :
  NoAboveAnyMember ensemble_rate.
Proof.
  intro ms. induction ms as [ | m0 t IH ]; intros m r Hin Hrate.
  - destruct Hin.
  - cbn [ensemble_rate] in Hrate. cbn [In] in Hin.
    destruct (ensemble_rate t) as [ rt | ] eqn:E.
    + injection Hrate as Hrate. destruct Hin as [ Heq | Hin ].
      * rewrite <- Hrate. rewrite Heq. lia.
      * pose proof (IH m rt Hin eq_refl) as Hle. rewrite <- Hrate. lia.
    + injection Hrate as Hrate. destruct Hin as [ Heq | Hin ].
      * rewrite <- Hrate. rewrite Heq. lia.
      * apply ensemble_rate_none in E. rewrite E in Hin. destruct Hin.
Qed.

(* =========================================================================
   The demo composition, and the computed checks. Every magnitude is an
   arbitrary witness value and carries no composition claim (gap f); the
   grant in particular is symbolic, R-15-108's exploration having no cell
   for it.
   ========================================================================= *)

Definition demo_widths : Widths := {|
  w_resident_bytes := 2;
  w_context_length := 2;
  w_format := 2;
  w_expert_count := 2;
  w_top_k := 2;
  w_kv_bytes_per_token := 2
|}.

Definition demo_shape : Shape := {|
  shape_resident_bytes := 40;
  shape_context_length := 64;
  shape_format := 4;
  shape_expert_count := 8;
  shape_top_k := 2;
  shape_kv_bytes_per_token := 10
|}.

Definition demo_ceiling : Ceiling := {|
  max_resident_bytes := 50;
  max_context_length := 64;
  admitted_formats := [ 4; 5 ];
  max_expert_count := 8;
  fixed_top_k := 2;
  max_kv_bytes_per_token := 16;
  ceiling_grant := 200
|}.

Definition demo_costs : Costs := {|
  dense_work_per_token := 10;
  expert_work_per_token := 3;
  fetch_penalty := 5
|}.

Definition all_resident : Residency := fun _ => true.

Definition demo : Composition := {|
  comp_widths := demo_widths;
  comp_ceiling := demo_ceiling;
  comp_costs := demo_costs;
  comp_residency := all_resident;
  comp_bytes_per_token := weights_and_cache
|}.

Definition demo_server : Server := {|
  server_slot := 40;
  server_workers := [0; 1];
  server_pool_bytes := 60;
  server_session_capacity := 1
|}.

Definition demo_idle : Sessions := {| sessions_open := 0 |}.
Definition demo_full : Sessions := {| sessions_open := 1 |}.

(* Written from the codec rather than transcribed, so the bytes have one
   owner. *)
Definition demo_descriptor : list Byte := encode_shape demo_widths demo_shape.

Definition demo_request : Request := {|
  req_descriptor := demo_descriptor;
  req_tokens_per_second := 4
|}.

Definition greedy_request : Request := {|
  req_descriptor := demo_descriptor;
  req_tokens_per_second := 5
|}.

Definition over_shape : Shape := {|
  shape_resident_bytes := 90;
  shape_context_length := 64;
  shape_format := 4;
  shape_expert_count := 8;
  shape_top_k := 2;
  shape_kv_bytes_per_token := 10
|}.

Definition over_request : Request := {|
  req_descriptor := encode_shape demo_widths over_shape;
  req_tokens_per_second := 1
|}.

Definition loose_top_k_shape : Shape := {|
  shape_resident_bytes := 40;
  shape_context_length := 64;
  shape_format := 4;
  shape_expert_count := 8;
  shape_top_k := 1;
  shape_kv_bytes_per_token := 10
|}.

Definition loose_top_k_request : Request := {|
  req_descriptor := encode_shape demo_widths loose_top_k_shape;
  req_tokens_per_second := 1
|}.

Definition trailing_byte_request : Request := {|
  req_descriptor := demo_descriptor ++ [ 0 ];
  req_tokens_per_second := 1
|}.

(* The descriptor round-trips, so the statements above are not proved of a
   descriptor nothing satisfies. *)
Example the_demo_descriptor_fits :
  shape_fits demo_widths demo_shape = true := eq_refl.

Example the_demo_descriptor_round_trips :
  decode_shape demo_widths demo_descriptor = Some demo_shape := eq_refl.

Example the_demo_descriptor_is_its_schema_length :
  length demo_descriptor = schema_bytes (shape_schema demo_widths) := eq_refl.

(* A trailing byte is a decode failure and not an ignored field, which is
   R-05-051b's rule against an accept-and-ignore field as a computed check. *)
Example a_trailing_byte_is_not_ignored :
  decode_shape demo_widths (demo_descriptor ++ [ 0 ]) = None := eq_refl.

(* The arms of the session-open decision. *)

Example a_model_inside_the_ceiling_opens_at_the_derived_rate :
  step_verdict (opening demo demo_server demo_idle demo_request)
    = Admitted 4 := eq_refl.

Example an_admitted_session_takes_one_pool_slot :
  sessions_open (step_sessions (opening demo demo_server demo_idle demo_request))
    = 1 := eq_refl.

Example a_model_above_the_resident_ceiling_is_refused :
  step_verdict (opening demo demo_server demo_idle over_request)
    = Refused ResidentBytesAboveCeiling := eq_refl.

Example a_top_k_that_is_not_the_fixed_value_is_refused :
  step_verdict (opening demo demo_server demo_idle loose_top_k_request)
    = Refused TopKNotTheFixedValue := eq_refl.

Example a_non_canonical_descriptor_is_refused :
  step_verdict (opening demo demo_server demo_idle trailing_byte_request)
    = Refused DescriptorNotCanonical := eq_refl.

Example a_requested_rate_above_the_grant_is_refused :
  step_verdict (opening demo demo_server demo_idle greedy_request)
    = Refused TokenRateAboveGrant := eq_refl.

Example a_full_pool_declines_the_binding :
  step_verdict (opening demo demo_server demo_full demo_request)
    = Refused SessionPoolExhausted := eq_refl.

(* The grant term is live rather than dead: a composition differing in the
   grant alone moves the verdict, which is what makes R-15-247p's term an
   explicit ceiling term here. *)
Definition leaner_ceiling : Ceiling := {|
  max_resident_bytes := 50;
  max_context_length := 64;
  admitted_formats := [ 4; 5 ];
  max_expert_count := 8;
  fixed_top_k := 2;
  max_kv_bytes_per_token := 16;
  ceiling_grant := 150
|}.

Definition leaner : Composition := {|
  comp_widths := demo_widths;
  comp_ceiling := leaner_ceiling;
  comp_costs := demo_costs;
  comp_residency := all_resident;
  comp_bytes_per_token := weights_and_cache
|}.

Example the_grant_term_decides :
  step_verdict (opening demo demo_server demo_idle demo_request) = Admitted 4
  /\ step_verdict (opening leaner demo_server demo_idle demo_request)
     = Refused TokenRateAboveGrant :=
  conj eq_refl eq_refl.

(* The two arms of reading 5 are two different rates over one shape and one
   grant, which is why neither is written into the decision. *)
Example the_cache_placement_moves_the_rate :
  admitted_rate weights_and_cache demo_ceiling demo_shape = 4
  /\ admitted_rate weights_only demo_ceiling demo_shape = 5 :=
  conj eq_refl eq_refl.

(* Residency and the routing cases. *)

Definition demo_routing_a : Routing := [ 0; 1 ].
Definition demo_routing_b : Routing := [ 1; 2 ].

Example both_routings_are_admissible :
  routing_ok demo_shape demo_routing_a = true
  /\ routing_ok demo_shape demo_routing_b = true :=
  conj eq_refl eq_refl.

Theorem the_demo_composition_is_all_resident :
  AllExpertsResident demo_shape all_resident.
Proof. intros e _. reflexivity. Qed.

Example work_per_token_is_one_value_under_full_residency :
  work_per_token demo_costs (resident_cost demo_costs all_resident) demo_routing_a
    = work_per_token demo_costs (resident_cost demo_costs all_resident)
        demo_routing_b := eq_refl.

Example the_resident_route_serves_from_a_bank :
  serve all_resident 3 = FromResidentBank 3 := eq_refl.

Definition one_expert_missing : Residency := fun e => negb (e =? 0).

Example a_non_resident_expert_is_refused_rather_than_fetched :
  serve one_expert_missing 0 = FetchRefused RoutedFetchAcrossStorage := eq_refl.

(* An ensemble whose rate is its slowest member's and not their sum. *)
Definition demo_members : list Member :=
  [ {| member_grant := 200; member_bytes_per_token := 50 |};
    {| member_grant := 180; member_bytes_per_token := 60 |} ].

Example the_ensemble_runs_at_its_slowest_member :
  ensemble_rate demo_members = Some 3 := eq_refl.

(* =========================================================================
   Refutation witnesses (R-05-166). Each is an alternative construction the
   register's own sentence excludes, so the theorems above exclude something
   rather than agreeing with this file's definitions.
   ========================================================================= *)

(* -- The descriptor -- *)

(* A format carrying a reserved byte the decoder accepts and ignores, which
   R-05-051b forbids by name. Two admissible strings carry one value, so
   decode is not injective and re-encoding does not reproduce the bytes. *)
Definition reserved_field_codec : Codec := {|
  cod_admissible := fun bs => bytes_ok bs && (length bs =? 2);
  cod_encode := fun vs => match vs with v :: _ => [ v; 0 ] | [] => [ 0; 0 ] end;
  cod_decode := fun bs => match bs with b :: _ :: [] => Some [ b ] | _ => None end
|}.

Theorem an_accept_and_ignore_field_is_refuted :
  ~ ReEncodesItsBytes reserved_field_codec.
Proof.
  intro H.
  assert (Hb : cod_encode reserved_field_codec [ 7 ] = [ 7; 1 ]).
  { apply H; reflexivity. }
  cbv in Hb. discriminate Hb.
Qed.

Theorem an_accept_and_ignore_field_breaks_injectivity :
  ~ DecodeInjective reserved_field_codec.
Proof.
  intro H.
  assert (Hb : [ 7; 0 ] = [ 7; 1 ]).
  { apply (H [ 7; 0 ] [ 7; 1 ] [ 7 ]); reflexivity. }
  discriminate Hb.
Qed.

(* A format with two admissible length forms of one value, the long one
   normalized into the short one, which R-05-051b forbids twice over. *)
Definition two_form_codec : Codec := {|
  cod_admissible := fun bs =>
    bytes_ok bs && ((length bs =? 1) || (length bs =? 2));
  cod_encode := fun vs => match vs with v :: _ => [ v ] | [] => [ 0 ] end;
  cod_decode := fun bs =>
    match bs with
    | [ b ] => Some [ b ]
    | [ b; 0 ] => Some [ b ]
    | _ => None
    end
|}.

Theorem a_normalizing_decoder_is_refuted :
  ~ ReEncodesItsBytes two_form_codec.
Proof.
  intro H.
  assert (Hb : cod_encode two_form_codec [ 7 ] = [ 7; 0 ]).
  { apply H; reflexivity. }
  cbv in Hb. discriminate Hb.
Qed.

Theorem two_admissible_length_forms_break_injectivity :
  ~ DecodeInjective two_form_codec.
Proof.
  intro H.
  assert (Hb : [ 7 ] = [ 7; 0 ]).
  { apply (H [ 7 ] [ 7; 0 ] [ 7 ]); reflexivity. }
  discriminate Hb.
Qed.

(* A self-describing format whose encoded length is the value's and not the
   schema's, which is the unbounded parse R-05-051b's schema bound and
   R-15-171's objection to an unbounded admission term both exclude. *)
Definition tally_codec : Codec := {|
  cod_admissible := fun bs => bytes_ok bs;
  cod_encode := fun vs =>
    match vs with v :: _ => repeat 1 v ++ [ 0 ] | [] => [ 0 ] end;
  cod_decode := fun bs => Some [ length bs - 1 ]
|}.

Definition one_field_fits (vs : list nat) : bool :=
  match vs with [ v ] => v <? 256 | _ => false end.

Theorem a_self_describing_length_is_refuted :
  ~ LengthIsASchemaConstant tally_codec one_field_fits.
Proof.
  intro H.
  assert (Hb : length (cod_encode tally_codec [ 0 ])
               = length (cod_encode tally_codec [ 1 ])).
  { apply H; reflexivity. }
  cbv in Hb. discriminate Hb.
Qed.

(* -- Residency and the fixed top-k work argument -- *)

(* A residency declaration one expert short. R-15-171's premise is
   load-bearing: the same top-k, two routings, two costs. *)
Theorem a_non_resident_expert_makes_work_per_token_vary :
  ~ WorkIsRoutingBlind demo_shape
      (work_per_token demo_costs (resident_cost demo_costs one_expert_missing)).
Proof.
  intro H.
  assert (Hb : work_per_token demo_costs
                 (resident_cost demo_costs one_expert_missing) demo_routing_a
               = work_per_token demo_costs
                 (resident_cost demo_costs one_expert_missing) demo_routing_b).
  { apply H; reflexivity. }
  cbv in Hb. discriminate Hb.
Qed.

(* A mixture whose experts differ in width, every one of them resident.
   R-15-171's conclusion needs this premise and its sentence does not state
   it (reading 3, gap d). *)
Definition sized_cost : ExpertCost := fun e => 3 * (1 + e).

Theorem experts_of_unequal_width_make_work_per_token_vary :
  AllExpertsResident demo_shape all_resident
  /\ ~ WorkIsRoutingBlind demo_shape (work_per_token demo_costs sized_cost).
Proof.
  split.
  - exact the_demo_composition_is_all_resident.
  - intro H.
    assert (Hb : work_per_token demo_costs sized_cost demo_routing_a
                 = work_per_token demo_costs sized_cost demo_routing_b).
    { apply H; reflexivity. }
    cbv in Hb. discriminate Hb.
Qed.

(* -- The storage boundary -- *)

(* A server that fills a non-resident expert from storage on the routing
   decision, which is the input-dependent fill schedule R-15-171 refuses. *)
Definition serve_paging (res : Residency) (e : nat) : Fetch :=
  if res e then FromResidentBank e else FromStorage e.

Theorem a_routed_fetch_across_storage_is_refuted :
  ~ NoRoutedFetchCrossesStorage (serve_paging one_expert_missing).
Proof.
  intro H. specialize (H 0 0). cbv in H. apply H. reflexivity.
Qed.

(* -- The server's shape -- *)

(* A server that grows its pool to fit whatever model asks, which is the
   elasticity R-12-084b excludes: the alternative to refusing is a session
   admitted against a slot no schedulability proof covers. *)
Definition elastic_opening (c : Composition) : Opening :=
  fun srv st q =>
    match decode_shape (comp_widths c) (req_descriptor q) with
    | None => Build_Step srv st (Refused DescriptorNotCanonical)
    | Some s =>
        Build_Step
          (Build_Server (server_slot srv) (server_workers srv)
                        (server_pool_bytes srv + shape_resident_bytes s)
                        (server_session_capacity srv))
          (Build_Sessions (S (sessions_open st)))
          (Admitted (req_tokens_per_second q))
    end.

Theorem an_elastic_server_is_refuted :
  ~ FixedAtComposition (elastic_opening demo).
Proof.
  intro H.
  assert (Hp : server_pool_bytes
                 (step_server (elastic_opening demo demo_server demo_idle
                                               demo_request))
               = server_pool_bytes demo_server).
  { rewrite (H demo_server demo_idle demo_request). reflexivity. }
  cbv in Hp. discriminate Hp.
Qed.

Theorem an_elastic_server_admits_a_model_above_the_ceiling :
  ~ RefusesAboveCeiling demo (elastic_opening demo).
Proof.
  intro H.
  destruct (H demo_server demo_idle over_request over_shape eq_refl eq_refl)
    as [ why Hw ].
  cbv in Hw. discriminate Hw.
Qed.

(* -- The grant and the rate -- *)

(* A server that admits an above-grant session at the rate the grant can
   carry, which is the graceful degradation R-12-084b and R-15-238c refuse
   in favour of a refusal at the session boundary. *)
Definition degrading_opening (c : Composition) : Opening :=
  fun srv st q =>
    match decode_shape (comp_widths c) (req_descriptor q) with
    | None => Build_Step srv st (Refused DescriptorNotCanonical)
    | Some s =>
        Build_Step srv (Build_Sessions (S (sessions_open st)))
          (Admitted (Nat.min (req_tokens_per_second q)
                             (admitted_rate (comp_bytes_per_token c)
                                            (comp_ceiling c) s)))
    end.

Theorem a_degraded_admission_is_refuted :
  ~ NeverDegrades (degrading_opening demo).
Proof.
  intro H.
  assert (Hle : req_tokens_per_second greedy_request <= 4).
  { apply (H demo_server demo_idle greedy_request 4). reflexivity. }
  cbv in Hle. lia.
Qed.

(* A ceiling with no grant term: the session is admitted at whatever rate it
   asked for, which is the reading R-15-247p's composition-time constant
   excludes. *)
Definition grantless_opening (c : Composition) : Opening :=
  fun srv st q =>
    match decode_shape (comp_widths c) (req_descriptor q) with
    | None => Build_Step srv st (Refused DescriptorNotCanonical)
    | Some _ =>
        Build_Step srv (Build_Sessions (S (sessions_open st)))
          (Admitted (req_tokens_per_second q))
    end.

Definition extravagant_request : Request := {|
  req_descriptor := demo_descriptor;
  req_tokens_per_second := 10
|}.

Theorem a_ceiling_with_no_grant_term_is_refuted :
  ~ GrantBounded demo (grantless_opening demo).
Proof.
  intro H.
  assert (Hle : 10 * comp_bytes_per_token demo demo_shape
                <= ceiling_grant (comp_ceiling demo)).
  { apply (H demo_server demo_idle extravagant_request demo_shape 10);
      reflexivity. }
  cbv in Hle. lia.
Qed.

(* A rate that grows to meet the request, which is the performance property
   R-15-247p says the token rate is not. *)
Definition elastic_rate (bpt : PerTokenBytes)
  : Ceiling -> Shape -> Load -> nat :=
  fun cl s l => Nat.max (admitted_rate bpt cl s) (load_prompt_tokens l).

Definition quiet_load : Load :=
  {| load_prompt_tokens := 0; load_queue_depth := 0; load_utilization := 0 |}.

Definition prefill_load : Load :=
  {| load_prompt_tokens := 99; load_queue_depth := 0; load_utilization := 0 |}.

Theorem a_load_following_rate_is_refuted :
  ~ RateIsLoadBlind (elastic_rate weights_and_cache).
Proof.
  intro H.
  assert (Hb : elastic_rate weights_and_cache demo_ceiling demo_shape quiet_load
               = elastic_rate weights_and_cache demo_ceiling demo_shape
                   prefill_load) by apply H.
  cbv in Hb. discriminate Hb.
Qed.

(* -- The session pool -- *)

(* A pool that binds past its declared capacity, which is the overcommit
   R-08-047 refuses in favour of the typed exhausted verdict. *)
Definition overcommitting_opening (c : Composition) : Opening :=
  fun srv st q =>
    match decode_shape (comp_widths c) (req_descriptor q) with
    | None => Build_Step srv st (Refused DescriptorNotCanonical)
    | Some _ =>
        Build_Step srv (Build_Sessions (S (sessions_open st))) (Admitted 1)
    end.

Theorem an_overcommitting_pool_is_refuted :
  ~ PoolBounded (overcommitting_opening demo).
Proof.
  intro H.
  assert (Hle : sessions_open
                  (step_sessions (overcommitting_opening demo demo_server
                                    demo_full demo_request))
                <= server_session_capacity demo_server).
  { apply H. cbv. lia. }
  cbv in Hle. lia.
Qed.

(* -- The routes -- *)

(* A broker that answers an unqualified module socket by sending the request
   to the software server, which R-12-085f's fail-closed clause excludes: no
   alternate inference destination receives the request implicitly. *)
Definition dispatch_with_fallback (qual : Qualified) (rt : Route) : option Route :=
  if qual rt then Some rt else Some SoftwareServer.

Definition nothing_qualified : Qualified := fun _ => false.

Theorem an_implicit_route_fallback_is_refuted :
  ~ NoImplicitFallback (dispatch_with_fallback nothing_qualified).
Proof.
  intro H.
  assert (Hb : SoftwareServer = ModuleBroker).
  { apply (H ModuleBroker). reflexivity. }
  discriminate Hb.
Qed.

(* -- The ensemble -- *)

(* An ensemble rate taken as the sum of its members' rates, which is the
   pooled-memory reading R-15-171a excludes: what an ensemble adds is
   capacity and aggregate throughput by member count and never a single
   session's rate above what one member's grants fix. *)
Fixpoint pooled_rate (ms : list Member) : option nat :=
  match ms with
  | [] => None
  | m :: t =>
      match pooled_rate t with
      | None => Some (member_rate m)
      | Some r => Some (member_rate m + r)
      end
  end.

Definition slow_member : Member :=
  {| member_grant := 180; member_bytes_per_token := 60 |}.

Theorem a_pooled_ensemble_rate_is_refuted : ~ NoAboveAnyMember pooled_rate.
Proof.
  intro H.
  assert (Hin : In slow_member demo_members).
  { unfold demo_members, slow_member. simpl. right. left. reflexivity. }
  assert (Hle : 7 <= member_rate slow_member).
  { apply (H demo_members slow_member 7 Hin). reflexivity. }
  cbv in Hle. lia.
Qed.

(* =========================================================================
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at it.
   ========================================================================= *)

Definition witness_Ceiling : Ceiling := demo_ceiling.
Definition witness_Codec : Codec := schema_codec (shape_schema demo_widths).
Definition witness_Composition : Composition := demo.
Definition witness_Costs : Costs := demo_costs.
Definition witness_Load : Load := quiet_load.
Definition witness_Member : Member := slow_member.
Definition witness_Request : Request := demo_request.
Definition witness_Server : Server := demo_server.
Definition witness_Sessions : Sessions := demo_idle.
Definition witness_Shape : Shape := demo_shape.
Definition witness_Step : Step := opening demo demo_server demo_idle demo_request.
Definition witness_Widths : Widths := demo_widths.

(* =========================================================================
   R-05-163's assumption gate, as in the artifacts beside this one.
   ========================================================================= *)

Print Assumptions field_decode_encode.
Print Assumptions field_encode_decode.
Print Assumptions fields_decode_encode.
Print Assumptions fields_encode_decode.
Print Assumptions re_encoding_its_bytes_gives_decode_injectivity.
Print Assumptions the_schema_codec_re_encodes_its_bytes.
Print Assumptions the_schema_codec_decode_is_injective.
Print Assumptions the_schema_codec_decodes_what_it_encodes.
Print Assumptions the_schema_codec_length_is_a_schema_constant.
Print Assumptions the_schema_codec_emits_admissible_bytes.
Print Assumptions the_shape_descriptor_re_encodes_its_bytes.
Print Assumptions the_shape_descriptor_decode_is_injective.
Print Assumptions the_shape_descriptor_decodes_what_it_encodes.
Print Assumptions the_shape_descriptor_length_is_a_schema_constant.
Print Assumptions the_ceiling_verdict_names_its_term.
Print Assumptions a_uniform_expert_cost_makes_work_per_token_constant.
Print Assumptions all_experts_resident_makes_the_cost_uniform.
Print Assumptions residency_and_fixed_top_k_make_work_per_token_constant.
Print Assumptions routed_fetch_across_the_storage_boundary_is_refused.
Print Assumptions a_boolean_verdict_loses_the_refusal_cause.
Print Assumptions the_derived_rate_spends_no_more_than_the_grant.
Print Assumptions both_cache_placements_stay_inside_the_grant.
Print Assumptions the_admitted_rate_follows_no_load_signal.
Print Assumptions the_server_is_fixed_at_composition.
Print Assumptions a_model_above_the_ceiling_is_refused_when_the_session_opens.
Print Assumptions a_rate_above_the_grant_is_refused_and_not_degraded.
Print Assumptions no_admitted_session_spends_more_than_the_grant.
Print Assumptions the_session_pool_never_exceeds_its_declared_capacity.
Print Assumptions a_full_session_pool_declines_the_binding.
Print Assumptions an_unqualified_route_reaches_no_other_destination.
Print Assumptions an_ensemble_rate_exceeds_no_member_rate.
Print Assumptions an_accept_and_ignore_field_is_refuted.
Print Assumptions an_accept_and_ignore_field_breaks_injectivity.
Print Assumptions a_normalizing_decoder_is_refuted.
Print Assumptions two_admissible_length_forms_break_injectivity.
Print Assumptions a_self_describing_length_is_refuted.
Print Assumptions a_non_resident_expert_makes_work_per_token_vary.
Print Assumptions experts_of_unequal_width_make_work_per_token_vary.
Print Assumptions a_routed_fetch_across_storage_is_refuted.
Print Assumptions an_elastic_server_is_refuted.
Print Assumptions an_elastic_server_admits_a_model_above_the_ceiling.
Print Assumptions a_degraded_admission_is_refuted.
Print Assumptions a_ceiling_with_no_grant_term_is_refuted.
Print Assumptions a_load_following_rate_is_refuted.
Print Assumptions an_overcommitting_pool_is_refuted.
Print Assumptions an_implicit_route_fallback_is_refuted.
Print Assumptions a_pooled_ensemble_rate_is_refuted.

(* Complete admission entry point. `opening` is the resource/ceiling core;
   this wrapper additionally decides the composition's finite residency map.
   The worker identifiers are a fixed list in Server, not merely a count. *)
Definition all_experts_resident (s : Shape) (res : Residency) : bool :=
  forallb res (seq 0 (shape_expert_count s)).
Lemma finite_residency_is_complete : forall s res,
  all_experts_resident s res = true <-> AllExpertsResident s res.
Proof.
  intros s res; unfold all_experts_resident, AllExpertsResident.
  rewrite forallb_forall; split; intros H e He.
  - apply H; apply in_seq; lia.
  - apply H; apply in_seq in He; lia.
Qed.
Definition composition_opening (c : Composition) : Opening :=
  fun srv st q =>
    match decode_shape (comp_widths c) (req_descriptor q) with
    | None => Build_Step srv st (Refused DescriptorNotCanonical)
    | Some s =>
        if all_experts_resident s (comp_residency c)
        then if shape_top_k s <=? shape_expert_count s
             then opening c srv st q
             else Build_Step srv st (Refused TopKNotTheFixedValue)
        else Build_Step srv st (Refused ExpertNotResident)
    end.
Theorem full_admission_preserves_server_resources : forall c,
  FixedAtComposition (composition_opening c).
Proof.
  intros c srv st q. unfold composition_opening.
  destruct (decode_shape (comp_widths c) (req_descriptor q)) as [s|]; [ | reflexivity ].
  destruct (all_experts_resident s (comp_residency c)); [ | reflexivity ].
  destruct (shape_top_k s <=? shape_expert_count s); [ | reflexivity ].
  apply the_server_is_fixed_at_composition.
Qed.
Theorem admitted_composition_uses_the_ceiling_and_resource_core : forall c srv st q rate,
  step_verdict (composition_opening c srv st q) = Admitted rate ->
  composition_opening c srv st q = opening c srv st q.
Proof.
  intros c srv st q rate H. unfold composition_opening in H |- *.
  destruct (decode_shape (comp_widths c) (req_descriptor q)) as [s|]; [ | discriminate H ].
  destruct (all_experts_resident s (comp_residency c)); [ | discriminate H ].
  destruct (shape_top_k s <=? shape_expert_count s); [ reflexivity | discriminate H ].
Qed.
Theorem admitted_composition_has_every_expert_resident : forall c srv st q rate s,
  decode_shape (comp_widths c) (req_descriptor q) = Some s ->
  step_verdict (composition_opening c srv st q) = Admitted rate ->
  AllExpertsResident s (comp_residency c).
Proof.
  intros c srv st q rate s Hd Ha. unfold composition_opening in Ha. rewrite Hd in Ha.
  destruct (all_experts_resident s (comp_residency c)) eqn:Hres; [ | discriminate Ha ].
  apply finite_residency_is_complete. exact Hres.
Qed.
Definition checked_routed_work (s : Shape) (co : Costs) (res : Residency)
                              (route : Routing) : option nat :=
  if routing_ok s route
  then if all_experts_resident s res
       then Some (work_per_token co (resident_cost co res) route)
       else None
  else None.
Theorem invalid_expert_routes_are_refused : forall s co res route,
  routing_ok s route = false -> checked_routed_work s co res route = None.
Proof. intros s co res route H; unfold checked_routed_work; rewrite H; reflexivity. Qed.
Definition missing_expert_composition : Composition := {|
  comp_widths := demo_widths; comp_ceiling := demo_ceiling; comp_costs := demo_costs;
  comp_residency := one_expert_missing; comp_bytes_per_token := weights_and_cache |}.
Example full_resident_admission_and_missing_expert_refusal :
  step_verdict (composition_opening demo demo_server demo_idle demo_request) = Admitted 4 /\
  step_verdict (composition_opening missing_expert_composition demo_server demo_idle demo_request)
    = Refused ExpertNotResident.
Proof. vm_compute; split; reflexivity. Qed.
Example invalid_routing_has_no_work_result :
  checked_routed_work demo_shape demo_costs all_resident [0; 8] = None.
Proof. vm_compute; reflexivity. Qed.
Example admitted_fixed_top_k_routes_have_the_same_work :
  checked_routed_work demo_shape demo_costs all_resident demo_routing_a = Some 16 /\
  checked_routed_work demo_shape demo_costs all_resident demo_routing_b = Some 16.
Proof. vm_compute; split; reflexivity. Qed.
Definition boundary_shape : Shape := Build_Shape 50 64 5 8 2 16.
Example every_ceiling_boundary_is_admitted :
  why_refused demo_ceiling boundary_shape = None.
Proof. vm_compute; reflexivity. Qed.
Example every_over_boundary_has_its_typed_refusal :
  map (why_refused demo_ceiling)
    [Build_Shape 51 64 5 8 2 16; Build_Shape 50 65 5 8 2 16;
     Build_Shape 50 64 6 8 2 16; Build_Shape 50 64 5 9 2 16;
     Build_Shape 50 64 5 8 3 16; Build_Shape 50 64 5 8 2 17]
  = [Some ResidentBytesAboveCeiling; Some ContextAboveCeiling;
     Some FormatNotAdmitted; Some ExpertCountAboveCeiling;
     Some TopKNotTheFixedValue; Some KvPerTokenAboveCeiling].
Proof. vm_compute; reflexivity. Qed.
Print Assumptions finite_residency_is_complete.
Print Assumptions full_admission_preserves_server_resources.
Print Assumptions admitted_composition_uses_the_ceiling_and_resource_core.
Print Assumptions admitted_composition_has_every_expert_resident.
Print Assumptions invalid_expert_routes_are_refused.
