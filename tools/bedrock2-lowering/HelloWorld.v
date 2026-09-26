(* SPDX-License-Identifier: Apache-2.0 *)
(* M1.7's value component. The relation ends at Bedrock2; the C printer,
   purecap compiler, image composer and target execution are measured separately. *)
Require Import Rupicola.Lib.Api.
Require Import Rupicola.Lib.ToCString.
Require Import bedrock2.BasicC64Semantics.

Module HelloWorld.
  Import BasicC64Semantics.

  Definition hello_char (index : word) : word :=
    let/n is_char := word.eqb index (word.of_Z 0) in
    if is_char then let/n result := word.of_Z 72 in result else
    let/n is_char := word.eqb index (word.of_Z 1) in
    if is_char then let/n result := word.of_Z 101 in result else
    let/n is_char := word.eqb index (word.of_Z 2) in
    if is_char then let/n result := word.of_Z 108 in result else
    let/n is_char := word.eqb index (word.of_Z 3) in
    if is_char then let/n result := word.of_Z 108 in result else
    let/n is_char := word.eqb index (word.of_Z 4) in
    if is_char then let/n result := word.of_Z 111 in result else
    let/n is_char := word.eqb index (word.of_Z 5) in
    if is_char then let/n result := word.of_Z 44 in result else
    let/n is_char := word.eqb index (word.of_Z 6) in
    if is_char then let/n result := word.of_Z 32 in result else
    let/n is_char := word.eqb index (word.of_Z 7) in
    if is_char then let/n result := word.of_Z 119 in result else
    let/n is_char := word.eqb index (word.of_Z 8) in
    if is_char then let/n result := word.of_Z 111 in result else
    let/n is_char := word.eqb index (word.of_Z 9) in
    if is_char then let/n result := word.of_Z 114 in result else
    let/n is_char := word.eqb index (word.of_Z 10) in
    if is_char then let/n result := word.of_Z 108 in result else
    let/n is_char := word.eqb index (word.of_Z 11) in
    if is_char then let/n result := word.of_Z 100 in result else
    let/n is_char := word.eqb index (word.of_Z 12) in
    if is_char then let/n result := word.of_Z 33 in result else
    let/n is_char := word.eqb index (word.of_Z 13) in
    if is_char then let/n result := word.of_Z 10 in result else let/n result := word.of_Z 0 in result.

  #[global] Instance spec_of_hello_char : spec_of "hello_char" :=
    fnspec! "hello_char" index / R ~> result,
    { requires tr mem := R mem;
      ensures tr' mem' := tr' = tr /\ result = hello_char index /\ R mem' }.

  Derive hello_char_br2fn SuchThat
    (defn! "hello_char"("index") ~> "result" { hello_char_br2fn },
     implements hello_char) As hello_char_br2fn_ok.
  Proof. Time compile. Time Qed.

  Definition hello_char_c : string := Eval vm_compute in
    c_module [("hello_char", hello_char_br2fn)].
End HelloWorld.

Require Import Coq.Strings.String.
Goal True. idtac "=== ASSUMPTIONS ===". exact I. Qed.
Print Assumptions HelloWorld.hello_char_br2fn_ok.
Redirect "hello_char" Compute HelloWorld.hello_char_c.
