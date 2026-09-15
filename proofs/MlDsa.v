(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MlDsa.v

   Functional ML-DSA-87, FIPS 204 (2024-08-13), under the acceptance contract
   docs/assurance/pq-reference-contract.md. This authored implementation uses
   PqArith's complete transform and Keccak's bit-oriented SHAKE. No upstream
   implementation is incorporated.

   Algorithms 6-8 and their sampling, rounding and encoding helpers are
   specialized to k=8, l=7, eta=2, tau=60, beta=120, gamma1=2^19,
   gamma2=(q-1)/32, omega=75, d=13 and lambda=256. The public pure wrapper
   binds context and accepts explicit hedging bytes from its trusted caller.
   Internal message inputs remain bit strings, including a final partial byte.
   External-mu adapters are testing/composition interfaces, not evidence that
   a caller supplied an authentic message representative.

   Appendix C budgets: 894 matrix bytes, 481 secret bytes, 221 challenge bytes
   and 821 signing attempts (2026-07-31 potential-update correction). Exhaustion returns no partial output. Smaller
   signing fuel is exposed only by the explicitly named test helper. List
   arithmetic is only reached after exact public byte lengths, canonical
   signed fields and complete sampler outputs have been checked.

   The general transform and byte-codec inverse theorems are in PqArith.
   Here theorems cover checked refusal and response boundaries. Official
   ACVP campaigns compare the extracted exact source, including local SHAKE,
   with published bytes; extraction/compiler execution is evidence, not a
   kernel proof of every vector or a computational security reduction.
   The selected parameter set is R-05-058a; functional-reference assurance is
   R-05-059. This does not supply R-05-004a production randomness or masking.
   No pre-hash dispatch, randomness-quality, constant-time, masking, target
   lowering or production key-storage claim is made by this functional file.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-058a R-05-059
   SHA256: db4682e3eb8fcd86f3d5da4b0ca956c05f5af3143057a2d00e383773411edae3
   (*| END derived |*)
   ========================================================================= *)
From Stdlib Require Import ZArith List Bool Arith Lia.
Require Import PqArith.
Require Keccak.
Import ListNotations.
Open Scope Z_scope.

Definition dsa_q : Z := 8380417.
Definition dsa_gamma1 : Z := 524288.
Definition dsa_gamma2 : Z := 261888.
Definition dsa_beta : Z := 120.
Definition dsa_bytes := list Z.
Definition dsa_poly := list Z.
Definition dsa_vector := list dsa_poly.

Inductive DsaResult (A : Type) : Type :=
| DsaOk : A -> DsaResult A
| DsaInvalid : DsaResult A
| DsaExhausted : DsaResult A.
Arguments DsaOk {A} _.
Arguments DsaInvalid {A}.
Arguments DsaExhausted {A}.

Definition dsa_bytes_ok (n : nat) (bs : dsa_bytes) : bool :=
  Nat.eqb (length bs) n && forallb (fun b => (0 <=? b) && (b <? 256)) bs.
Definition dsa_any_bytes (bs : dsa_bytes) : bool :=
  forallb (fun b => (0 <=? b) && (b <? 256)) bs.
Definition dsa_bits (bs : dsa_bytes) : list bool := Keccak.bits_of_bytes (map Z.to_nat bs).
Definition dsa_xof_bits (strength out_bytes : nat) (input : list bool) : dsa_bytes :=
  map Z.of_nat (Keccak.bytes_of (Keccak.shake strength (8 * out_bytes) input)).
Definition dsa_h (n : nat) (bs : dsa_bytes) : dsa_bytes := dsa_xof_bits 256 n (dsa_bits bs).
Definition dsa_g (n : nat) (bs : dsa_bytes) : dsa_bytes := dsa_xof_bits 128 n (dsa_bits bs).
Definition dsa_nonce (n : nat) : dsa_bytes :=
  [Z.of_nat n mod 256; (Z.of_nat n / 256) mod 256].

Fixpoint dsa_traverse {A B : Type} (f : A -> option B) (xs : list A) : option (list B) :=
  match xs with
  | [] => Some []
  | x :: rest => match f x, dsa_traverse f rest with
                | Some y, Some ys => Some (y :: ys)
                | _, _ => None
                end
  end.
Definition dsa_mod (p : dsa_poly) := map (fun x => x mod dsa_q) p.
Definition dsa_ntt (p : dsa_poly) := ntt mldsa_ring (dsa_mod p).
Definition dsa_intt (p : dsa_poly) := intt mldsa_ring p.
Definition dsa_vec_add (a b : dsa_vector) :=
  map (fun p => vadd dsa_q (fst p) (snd p)) (combine a b).
Definition dsa_vec_sub (a b : dsa_vector) :=
  map (fun p => vsub dsa_q (fst p) (snd p)) (combine a b).
Definition dsa_dot (row v : dsa_vector) : dsa_poly :=
  fold_left (vadd dsa_q)
    (map (fun p => mul_ntt_pointwise mldsa_ring (fst p) (snd p)) (combine row v))
    (zero_poly 256).
Definition dsa_matmul (a : list dsa_vector) (v : dsa_vector) := map (fun row => dsa_dot row v) a.
Definition dsa_challenge_product (chat : dsa_poly) (vhat : dsa_vector) :=
  map (fun p => dsa_intt (mul_ntt_pointwise mldsa_ring chat p)) vhat.

Definition dsa_coeff3 (bs : list Z) : option Z :=
  match bs with
  | [a;b;c] => let x := a + 256*b + 65536*(c mod 128) in
              if x <? dsa_q then Some x else None
  | _ => None
  end.
Definition dsa_coeff_half (b : Z) : option Z :=
  if b <? 15 then Some (2 - b mod 5) else None.
Fixpoint dsa_collect {A B : Type} (f : A -> option B) (xs : list A) : list B :=
  match xs with [] => [] | x::rest =>
    match f x with Some y => y :: dsa_collect f rest | None => dsa_collect f rest end
  end.
Definition dsa_take_poly (xs : list Z) : option dsa_poly :=
  if Nat.leb 256 (length xs) then Some (firstn 256 xs) else None.
Definition dsa_rej_ntt (seed : dsa_bytes) : option dsa_poly :=
  dsa_take_poly (dsa_collect dsa_coeff3 (chunk_of 298 3 (dsa_g 894 seed))).
Definition dsa_rej_small (seed : dsa_bytes) : option dsa_poly :=
  dsa_take_poly (dsa_collect dsa_coeff_half
    (concat (map (fun b => [b mod 16; b / 16]) (dsa_h 481 seed)))).
Definition dsa_expand_a (rho : dsa_bytes) : option (list dsa_vector) :=
  dsa_traverse (fun r => dsa_traverse
    (fun s => dsa_rej_ntt (rho ++ [Z.of_nat s; Z.of_nat r])) (seq 0 7)) (seq 0 8).
Definition dsa_expand_s (rho : dsa_bytes) : option dsa_vector :=
  dsa_traverse (fun r => dsa_rej_small (rho ++ dsa_nonce r)) (seq 0 15).

Definition dsa_pack_signed (width : nat) (bound : Z) (p : dsa_poly) : dsa_bytes :=
  byte_encode width (map (fun x => bound - centred dsa_q x) p).
Definition dsa_unpack_signed (width : nat) (bound : Z) (bs : dsa_bytes) : dsa_poly :=
  map (fun x => bound - x) (byte_decode width bs).
Definition dsa_pack_vec (width : nat) (v : dsa_vector) :=
  concat (map (byte_encode width) v).
Definition dsa_pack_signed_vec (width : nat) (bound : Z) (v : dsa_vector) :=
  concat (map (dsa_pack_signed width bound) v).
Definition dsa_unpack_vec (count width : nat) (bs : dsa_bytes) : dsa_vector :=
  map (byte_decode width) (chunk_of count (32 * width) bs).
Definition dsa_unpack_signed_vec (count width : nat) (bound : Z) (bs : dsa_bytes) : dsa_vector :=
  map (dsa_unpack_signed width bound) (chunk_of count (32 * width) bs).
Definition dsa_expand_mask (rho : dsa_bytes) (kappa : nat) : dsa_vector :=
  map (fun r => dsa_unpack_signed 20 dsa_gamma1
    (dsa_h 640 (rho ++ dsa_nonce (kappa + r)))) (seq 0 7).

Definition dsa_power2round (r : Z) : Z * Z :=
  let rp := r mod dsa_q in let low := centred 8192 rp in ((rp-low)/8192, low).
Definition dsa_decompose (r : Z) : Z * Z :=
  let rp := r mod dsa_q in let low := centred (2*dsa_gamma2) rp in
  if rp-low =? dsa_q-1 then (0,low-1) else ((rp-low)/(2*dsa_gamma2),low).
Definition dsa_high (r : Z) := fst (dsa_decompose r).
Definition dsa_low (r : Z) := snd (dsa_decompose r).
Definition dsa_make_hint (z r : Z) := negb (Z.eqb (dsa_high r) (dsa_high (r+z))).
Definition dsa_use_hint (h : bool) (r : Z) :=
  let '(hi,lo) := dsa_decompose r in
  if h then if 0 <? lo then (hi+1) mod 16 else (hi-1) mod 16 else hi.

Fixpoint dsa_set (i : nat) (x : Z) (p : dsa_poly) : dsa_poly :=
  match i,p with
  | O,_::rest => x::rest
  | S j,y::rest => y::dsa_set j x rest
  | _,[] => []
  end.
Fixpoint dsa_pick (i : Z) (bs : dsa_bytes) : option (Z * dsa_bytes) :=
  match bs with
  | [] => None
  | b::rest => if b <=? i then Some (b,rest) else dsa_pick i rest
  end.
Fixpoint dsa_ball_go (signs : list bool) (i : nat) (bs : dsa_bytes) (p : dsa_poly) : option dsa_poly :=
  match signs with
  | [] => Some p
  | sign::rest => match dsa_pick (Z.of_nat i) bs with
    | None => None
    | Some (j,tail) => dsa_ball_go rest (S i) tail
      (dsa_set (Z.to_nat j) (if sign then -1 else 1) (dsa_set i (coeff p (Z.to_nat j)) p))
    end
  end.
Definition dsa_sample_ball (seed : dsa_bytes) : option dsa_poly :=
  let stream := dsa_h 221 seed in
  dsa_ball_go (firstn 60 (dsa_bits (firstn 8 stream))) 196 (skipn 8 stream) (zero_poly 256).

Definition dsa_hint_indices (p : list bool) : list Z :=
  map (fun e => Z.of_nat (fst e)) (filter (fun e => snd e) (combine (seq 0 256) p)).
Fixpoint dsa_hint_ends (hs : list (list Z)) (offset : Z) : list Z :=
  match hs with [] => [] | h::rest => let n := offset + Z.of_nat (length h) in
    n :: dsa_hint_ends rest n end.
Definition dsa_hint_pack (h : list (list bool)) : dsa_bytes :=
  let positions := map dsa_hint_indices h in
  let flat := concat positions in
  flat ++ repeat 0 (75 - length flat) ++ dsa_hint_ends positions 0.
Fixpoint dsa_sorted_after (previous : option Z) (xs : list Z) : bool :=
  match xs with
  | [] => true
  | x::rest => (match previous with None => true | Some p => p <? x end)
              && dsa_sorted_after (Some x) rest
  end.
Fixpoint dsa_hint_parse (ends : list Z) (positions : dsa_bytes) (previous : nat) : option (list (list bool)) :=
  match ends with
  | [] => if forallb (Z.eqb 0) (skipn previous positions) then Some [] else None
  | endpoint::rest =>
      let e := Z.to_nat endpoint in
      if Nat.leb previous e && Nat.leb e 75 then
        let indexes := firstn (e-previous) (skipn previous positions) in
        if dsa_sorted_after None indexes then
          match dsa_hint_parse rest positions e with
          | Some hs => Some (map (fun j => existsb (Z.eqb (Z.of_nat j)) indexes) (seq 0 256) :: hs)
          | None => None
          end
        else None
      else None
  end.
Definition dsa_hint_unpack (bs : dsa_bytes) : option (list (list bool)) :=
  if dsa_bytes_ok 83 bs then dsa_hint_parse (skipn 75 bs) (firstn 75 bs) 0 else None.
Definition dsa_hint_weight (h : list (list bool)) : nat :=
  length (filter (fun b => b) (concat h)).

Record DsaSecret : Type := {
  dsa_rho : dsa_bytes; dsa_key : dsa_bytes; dsa_tr : dsa_bytes;
  dsa_s1 : dsa_vector; dsa_s2 : dsa_vector; dsa_t0 : dsa_vector
}.
Definition dsa_pk_encode (rho : dsa_bytes) (t1 : dsa_vector) :=
  rho ++ dsa_pack_vec 10 t1.
Definition dsa_sk_encode (s : DsaSecret) :=
  dsa_rho s ++ dsa_key s ++ dsa_tr s ++
  dsa_pack_signed_vec 3 2 (dsa_s1 s) ++ dsa_pack_signed_vec 3 2 (dsa_s2 s) ++
  dsa_pack_signed_vec 13 4096 (dsa_t0 s).
Definition dsa_sk_decode (sk : dsa_bytes) : option DsaSecret :=
  if dsa_bytes_ok 4896 sk then
    let s1 := dsa_unpack_signed_vec 7 3 2 (firstn 672 (skipn 128 sk)) in
    let s2 := dsa_unpack_signed_vec 8 3 2 (firstn 768 (skipn 800 sk)) in
    if (norm_inf_vec dsa_q s1 <=? 2) && (norm_inf_vec dsa_q s2 <=? 2) then
      Some {| dsa_rho:=firstn 32 sk; dsa_key:=firstn 32 (skipn 32 sk);
              dsa_tr:=firstn 64 (skipn 64 sk); dsa_s1:=s1; dsa_s2:=s2;
              dsa_t0:=dsa_unpack_signed_vec 8 13 4096 (skipn 1568 sk) |}
    else None
  else None.
Definition dsa_pk_decode (pk : dsa_bytes) : option (dsa_bytes * dsa_vector) :=
  if dsa_bytes_ok 2592 pk then
    Some (firstn 32 pk, dsa_unpack_vec 8 10 (skipn 32 pk)) else None.

Definition dsa_sig_encode (ct : dsa_bytes) (z : dsa_vector) (h : list (list bool)) :=
  ct ++ dsa_pack_signed_vec 20 dsa_gamma1 z ++ dsa_hint_pack h.
Definition dsa_sig_decode (sig : dsa_bytes) : option (dsa_bytes * dsa_vector * list (list bool)) :=
  if dsa_bytes_ok 4627 sig then
    match dsa_hint_unpack (skipn 4544 sig) with
    | Some h => Some (firstn 64 sig, dsa_unpack_signed_vec 7 20 dsa_gamma1
                       (firstn 4480 (skipn 64 sig)), h)
    | None => None
    end
  else None.
Definition dsa_response_ok (z : dsa_vector) := norm_inf_vec dsa_q z <? dsa_gamma1-dsa_beta.

Definition dsa_keygen (seed : dsa_bytes) : DsaResult (dsa_bytes * dsa_bytes) :=
  if dsa_bytes_ok 32 seed then
    let expanded := dsa_h 128 (seed ++ [8;7]) in
    let rho := firstn 32 expanded in
    let rhoprime := firstn 64 (skipn 32 expanded) in
    let key := skipn 96 expanded in
    match dsa_expand_a rho, dsa_expand_s rhoprime with
    | Some a,Some secrets =>
      let s1:=firstn 7 secrets in let s2:=skipn 7 secrets in
      let t:=dsa_vec_add (map dsa_intt (dsa_matmul a (map dsa_ntt s1))) s2 in
      let t1:=map (map (fun r => fst (dsa_power2round r))) t in
      let t0:=map (map (fun r => snd (dsa_power2round r))) t in
      let pk:=dsa_pk_encode rho t1 in
      DsaOk (pk,dsa_sk_encode {| dsa_rho:=rho; dsa_key:=key; dsa_tr:=dsa_h 64 pk;
                                  dsa_s1:=s1; dsa_s2:=s2; dsa_t0:=t0 |})
    | _,_ => DsaExhausted
    end
  else DsaInvalid.

Definition dsa_attempt (a : list dsa_vector) (s1hat s2hat t0hat : dsa_vector)
    (mu rhoprime : dsa_bytes) (kappa : nat) : DsaResult (option dsa_bytes) :=
  let y:=dsa_expand_mask rhoprime kappa in
  let w:=map dsa_intt (dsa_matmul a (map dsa_ntt y)) in
  let w1:=map (map dsa_high) w in
  let ct:=dsa_h 64 (mu ++ dsa_pack_vec 4 w1) in
  match dsa_sample_ball ct with
  | None => DsaExhausted
  | Some c =>
    let chat:=dsa_ntt c in
    let cs1:=dsa_challenge_product chat s1hat in
    let cs2:=dsa_challenge_product chat s2hat in
    let z:=dsa_vec_add y cs1 in
    let residual:=dsa_vec_sub w cs2 in
    let low:=map (map dsa_low) residual in
    if dsa_response_ok z && (norm_inf_vec dsa_q low <? dsa_gamma2-dsa_beta) then
      let ct0:=dsa_challenge_product chat t0hat in
      let hint:=map (fun pair => map (fun p => dsa_make_hint (-fst p) (snd p))
          (combine (fst pair) (snd pair)))
        (combine ct0 (dsa_vec_add residual ct0)) in
      if (norm_inf_vec dsa_q ct0 <? dsa_gamma2) && Nat.leb (dsa_hint_weight hint) 75
      then DsaOk (Some (dsa_sig_encode ct z hint)) else DsaOk None
    else DsaOk None
  end.
Fixpoint dsa_sign_loop (fuel : nat) (a : list dsa_vector) (s1hat s2hat t0hat : dsa_vector)
    (mu rhoprime : dsa_bytes) (kappa : nat) : DsaResult dsa_bytes :=
  match fuel with
  | O => DsaExhausted
  | S f => match dsa_attempt a s1hat s2hat t0hat mu rhoprime kappa with
    | DsaOk (Some sig) => DsaOk sig
    | DsaOk None => dsa_sign_loop f a s1hat s2hat t0hat mu rhoprime (kappa+7)
    | DsaInvalid => DsaInvalid
    | DsaExhausted => DsaExhausted
    end
  end.
Definition dsa_sign_mu_test_fuel (fuel : nat) (sk mu rnd : dsa_bytes) : DsaResult dsa_bytes :=
  if dsa_bytes_ok 64 mu && dsa_bytes_ok 32 rnd then
    match dsa_sk_decode sk with
    | None => DsaInvalid
    | Some s => match dsa_expand_a (dsa_rho s) with
      | None => DsaExhausted
      | Some a => dsa_sign_loop (Nat.min fuel 821) a (map dsa_ntt (dsa_s1 s))
          (map dsa_ntt (dsa_s2 s)) (map dsa_ntt (dsa_t0 s))
          mu (dsa_h 64 (dsa_key s ++ rnd ++ mu)) 0
      end
    end
  else DsaInvalid.
Definition dsa_sign_mu (sk mu rnd : dsa_bytes) := dsa_sign_mu_test_fuel 821 sk mu rnd.
Definition dsa_sign_internal (sk : dsa_bytes) (message : list bool) (rnd : dsa_bytes) :=
  match dsa_sk_decode sk with
  | None => DsaInvalid
  | Some s => dsa_sign_mu sk (dsa_xof_bits 256 64 (dsa_bits (dsa_tr s) ++ message)) rnd
  end.

Definition dsa_verify_mu (pk mu sig : dsa_bytes) : bool :=
  if dsa_bytes_ok 64 mu then
    match dsa_pk_decode pk,dsa_sig_decode sig with
    | Some (rho,t1),Some (ct,z,h) =>
      if dsa_response_ok z then
        match dsa_expand_a rho,dsa_sample_ball ct with
        | Some a,Some c =>
          let az:=dsa_matmul a (map dsa_ntt z) in
          let ct1:=map (fun p => mul_ntt_pointwise mldsa_ring (dsa_ntt c)
            (dsa_ntt (vscale dsa_q 8192 p))) t1 in
          let w:=map dsa_intt (dsa_vec_sub az ct1) in
          let w1:=map (fun pair => map (fun p => dsa_use_hint (fst p) (snd p))
             (combine (fst pair) (snd pair))) (combine h w) in
          poly_eqb ct (dsa_h 64 (mu ++ dsa_pack_vec 4 w1))
        | _,_ => false
        end
      else false
    | _,_ => false
    end
  else false.
Definition dsa_verify_internal (pk : dsa_bytes) (message : list bool) (sig : dsa_bytes) :=
  if dsa_bytes_ok 2592 pk && dsa_bytes_ok 4627 sig then
    dsa_verify_mu pk (dsa_xof_bits 256 64 (dsa_bits (dsa_h 64 pk) ++ message)) sig
  else false.
Definition dsa_context_ok (context : dsa_bytes) :=
  Nat.leb (length context) 255 && dsa_any_bytes context.
Definition dsa_format_pure (context : dsa_bytes) (message : list bool) :=
  dsa_bits ([0;Z.of_nat (length context)] ++ context) ++ message.
Definition dsa_sign (sk context : dsa_bytes) (message : list bool) (rnd : dsa_bytes) :=
  if dsa_context_ok context then dsa_sign_internal sk (dsa_format_pure context message) rnd
  else DsaInvalid.
Definition dsa_verify (pk context : dsa_bytes) (message : list bool) (sig : dsa_bytes) :=
  if dsa_context_ok context then dsa_verify_internal pk (dsa_format_pure context message) sig
  else false.

Theorem dsa_keygen_refuses_bad_seed : forall seed,
  dsa_bytes_ok 32 seed = false -> dsa_keygen seed = DsaInvalid.
Proof. intros seed H. unfold dsa_keygen. rewrite H. reflexivity. Qed.
Theorem dsa_secret_decode_refuses_bad_length : forall sk,
  dsa_bytes_ok 4896 sk = false -> dsa_sk_decode sk = None.
Proof. intros sk H. unfold dsa_sk_decode. rewrite H. reflexivity. Qed.
Theorem dsa_verifier_checks_response : forall pk mu sig ct z h,
  dsa_sig_decode sig = Some (ct,z,h) ->
  dsa_verify_mu pk mu sig = true -> norm_inf_vec dsa_q z < dsa_gamma1-dsa_beta.
Proof.
  intros pk mu sig ct z h Hsig H. unfold dsa_verify_mu in H.
  destruct (dsa_bytes_ok 64 mu); [|discriminate].
  destruct (dsa_pk_decode pk) as [[rho t1]|]; [|discriminate].
  rewrite Hsig in H. destruct (dsa_response_ok z) eqn:E; [|discriminate].
  apply Z.ltb_lt. exact E.
Qed.
Theorem dsa_context_overflow_refuses : forall pk context message sig,
  dsa_context_ok context = false -> dsa_verify pk context message sig = false.
Proof. intros. unfold dsa_verify. rewrite H. reflexivity. Qed.
Theorem dsa_zero_attempt_budget_exhausts : forall a s1 s2 t0 mu rho kappa,
  dsa_sign_loop 0 a s1 s2 t0 mu rho kappa = DsaExhausted.
Proof. reflexivity. Qed.
Example dsa_strict_response_boundary :
  dsa_response_ok [[524167]] = true /\ dsa_response_ok [[524168]] = false.
Proof. vm_compute. split; reflexivity. Qed.
Example dsa_decomposition_boundary :
  dsa_decompose (dsa_q-1) = (0,-1) /\ dsa_power2round 4096 = (0,4096).
Proof. vm_compute. split; reflexivity. Qed.
Example dsa_bad_hint_padding_refuses :
  dsa_hint_unpack (1 :: repeat 0 82) = None.
Proof. vm_compute. reflexivity. Qed.
Example dsa_duplicate_hint_refuses :
  dsa_hint_unpack ([4;4] ++ repeat 0 73 ++ repeat 2 8) = None.
Proof. vm_compute. reflexivity. Qed.
Definition dsa_zero_hints : list (list bool) := repeat (repeat false 256) 8.
Example dsa_empty_hint_set_roundtrips :
  dsa_hint_unpack (dsa_hint_pack dsa_zero_hints) = Some dsa_zero_hints.
Proof. vm_compute. reflexivity. Qed.
Definition witness_DsaSecret : DsaSecret :=
  {| dsa_rho:=repeat 0 32; dsa_key:=repeat 0 32; dsa_tr:=repeat 0 64;
     dsa_s1:=repeat (zero_poly 256) 7; dsa_s2:=repeat (zero_poly 256) 8;
     dsa_t0:=repeat (zero_poly 256) 8 |}.
