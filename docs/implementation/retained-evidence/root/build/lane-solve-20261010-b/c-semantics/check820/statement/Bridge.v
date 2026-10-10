(* SPDX-License-Identifier: Apache-2.0 *)
From Coq Require Import ZArith List String.
From Stock.cfrontend Require Clight.
From Contained.cfrontend Require Clight.

Module S := Stock.cfrontend.Clight.
Module T := Contained.cfrontend.Clight.
Module ST := Stock.cfrontend.Ctypes.
Module TT := Contained.cfrontend.Ctypes.
Module SI := Stock.lib.Integers.
Module TI := Contained.lib.Integers.
Module SA := Stock.common.AST.
Module TA := Contained.common.AST.
Module SV := Stock.common.Values.
Module TV := Contained.common.Values.
Module SM := Stock.common.Memory.
Module TM := Contained.common.Memory.
Module SO := Stock.cfrontend.Cop.
Module TO := Contained.cfrontend.Cop.
Import ListNotations.
Open Scope Z_scope.

(* These maps are syntax, not a third C operational semantics. *)
Definition map_attr (a : ST.attr) : TT.attr :=
  TT.mk_attr (ST.attr_volatile a) (ST.attr_alignas a).
Definition map_size (s : ST.intsize) : TT.intsize :=
  match s with ST.I8 => TT.I8 | ST.I16 => TT.I16
  | ST.I32 => TT.I32 | ST.IBool => TT.IBool end.
Definition map_sign (s : ST.signedness) : TT.signedness :=
  match s with ST.Signed => TT.Signed | ST.Unsigned => TT.Unsigned end.
Definition map_cc (c : SA.calling_convention) : TA.calling_convention :=
  TA.mkcallconv (SA.cc_vararg c) (SA.cc_unproto c) (SA.cc_structret c).
Fixpoint map_type (t : ST.type) : TT.type :=
  match t with
  | ST.Tvoid => TT.Tvoid
  | ST.Tint sz sg a => TT.Tint (map_size sz) (map_sign sg) (map_attr a)
  | ST.Tlong sg a => TT.Tlong (map_sign sg) (map_attr a)
  | ST.Tfloat sz a => TT.Tfloat
      (match sz with ST.F32 => TT.F32 | ST.F64 => TT.F64 end) (map_attr a)
  | ST.Tpointer t a => TT.Tpointer (map_type t) (map_attr a)
  | ST.Tarray t n a => TT.Tarray (map_type t) n (map_attr a)
  | ST.Tfunction args ret cc => TT.Tfunction (map map_type args) (map_type ret) (map_cc cc)
  | ST.Tstruct id a => TT.Tstruct id (map_attr a)
  | ST.Tunion id a => TT.Tunion id (map_attr a)
  end.
Fixpoint type_ok (t : ST.type) : bool :=
  match t with
  | ST.Tvoid => true
  | ST.Tint _ _ a | ST.Tlong _ a | ST.Tstruct _ a => negb (ST.attr_volatile a)
  | ST.Tpointer elt a | ST.Tarray elt _ a =>
      negb (ST.attr_volatile a) && type_ok elt
  | ST.Tfunction args ret cc => forallb type_ok args && type_ok ret &&
      match SA.cc_vararg cc with Some _ => false | None =>
        negb (SA.cc_unproto cc || SA.cc_structret cc) end
  | _ => false
  end.
Definition map_unop (op : SO.unary_operation) : TO.unary_operation :=
  match op with SO.Onotbool => TO.Onotbool | SO.Onotint => TO.Onotint
  | SO.Oneg => TO.Oneg | SO.Oabsfloat => TO.Oabsfloat end.
Definition map_binop (op : SO.binary_operation) : TO.binary_operation :=
  match op with
  | SO.Oadd => TO.Oadd | SO.Osub => TO.Osub | SO.Omul => TO.Omul
  | SO.Odiv => TO.Odiv | SO.Omod => TO.Omod | SO.Oand => TO.Oand
  | SO.Oor => TO.Oor | SO.Oxor => TO.Oxor | SO.Oshl => TO.Oshl
  | SO.Oshr => TO.Oshr | SO.Oeq => TO.Oeq | SO.One => TO.One
  | SO.Olt => TO.Olt | SO.Ogt => TO.Ogt | SO.Ole => TO.Ole | SO.Oge => TO.Oge
  end.
Fixpoint map_expr (e : S.expr) : T.expr :=
  match e with
  | S.Econst_int i ty => T.Econst_int (TI.Int.repr (SI.Int.unsigned i)) (map_type ty)
  | S.Econst_long i ty => T.Econst_long (TI.Int64.repr (SI.Int64.unsigned i)) (map_type ty)
  | S.Evar id ty => T.Evar id (map_type ty)
  | S.Etempvar id ty => T.Etempvar id (map_type ty)
  | S.Ederef e ty => T.Ederef (map_expr e) (map_type ty)
  | S.Eaddrof e ty => T.Eaddrof (map_expr e) (map_type ty)
  | S.Eunop op e ty => T.Eunop (map_unop op) (map_expr e) (map_type ty)
  | S.Ebinop op a b ty => T.Ebinop (map_binop op) (map_expr a) (map_expr b) (map_type ty)
  | S.Ecast e ty => T.Ecast (map_expr e) (map_type ty)
  | S.Efield e id ty => T.Efield (map_expr e) id (map_type ty)
  | S.Esizeof t ty => T.Esizeof (map_type t) (map_type ty)
  | S.Ealignof t ty => T.Ealignof (map_type t) (map_type ty)
  (* Rejected constructors have no correspondence in the fragment. *)
  | _ => T.Econst_int TI.Int.zero TT.Tvoid
  end.
Fixpoint expr_ok (e : S.expr) : bool :=
  type_ok (S.typeof e) &&
  match e with
  | S.Econst_int _ _ | S.Econst_long _ _ | S.Evar _ _ | S.Etempvar _ _ => true
  | S.Ederef e _ | S.Eaddrof e _ | S.Ecast e _ | S.Efield e _ _ => expr_ok e
  | S.Eunop op e _ =>
      (match op with SO.Oabsfloat => false | _ => true end) && expr_ok e
  | S.Ebinop _ a b _ => expr_ok a && expr_ok b
  | S.Esizeof t _ | S.Ealignof t _ => type_ok t
  | _ => false
  end.
Fixpoint map_stmt (s : S.statement) : T.statement :=
  match s with
  | S.Sskip => T.Sskip
  | S.Sassign a b => T.Sassign (map_expr a) (map_expr b)
  | S.Sset id a => T.Sset id (map_expr a)
  | S.Scall ret fn args => T.Scall ret (map_expr fn) (map map_expr args)
  | S.Ssequence a b => T.Ssequence (map_stmt a) (map_stmt b)
  | S.Sifthenelse e a b => T.Sifthenelse (map_expr e) (map_stmt a) (map_stmt b)
  | S.Sloop a b => T.Sloop (map_stmt a) (map_stmt b)
  | S.Sbreak => T.Sbreak | S.Scontinue => T.Scontinue
  | S.Sreturn e => T.Sreturn (option_map map_expr e)
  | _ => T.Sskip
  end.
Fixpoint stmt_ok (s : S.statement) : bool :=
  match s with
  | S.Sskip | S.Sbreak | S.Scontinue => true
  | S.Sassign a b => expr_ok a && expr_ok b
  | S.Sset _ e => expr_ok e
  | S.Scall _ e args => expr_ok e && forallb expr_ok args
  | S.Ssequence a b | S.Sloop a b => stmt_ok a && stmt_ok b
  | S.Sifthenelse e a b => expr_ok e && stmt_ok a && stmt_ok b
  | S.Sreturn None => true | S.Sreturn (Some e) => expr_ok e
  | _ => false
  end.
Definition map_vars := map (fun v : SA.ident * ST.type => (fst v, map_type (snd v))).
Definition map_function (cp : TA.COMP.compartment) (f : S.function) : T.function :=
  T.mkfunction cp (map_type (S.fn_return f)) (map_cc (S.fn_callconv f))
    (map_vars (S.fn_params f)) (map_vars (S.fn_vars f))
    (map_vars (S.fn_temps f)) (map_stmt (S.fn_body f)).
Definition function_ok (f : S.function) : bool :=
  type_ok (S.fn_return f) &&
  forallb (fun v => type_ok (snd v))
    (S.fn_params f ++ S.fn_vars f ++ S.fn_temps f) &&
  stmt_ok (S.fn_body f) &&
  match SA.cc_vararg (S.fn_callconv f) with Some _ => false | None =>
    negb (SA.cc_unproto (S.fn_callconv f) || SA.cc_structret (S.fn_callconv f)) end.
Definition map_member (m : ST.member) : TT.member :=
  match m with
  | ST.Member_plain id ty => TT.Member_plain id (map_type ty)
  | ST.Member_bitfield id sz sg a n pad =>
      TT.Member_bitfield id (map_size sz) (map_sign sg) (map_attr a) n pad
  end.
Definition map_composite (d : ST.composite_definition) : TT.composite_definition :=
  match d with ST.Composite id su members a =>
    TT.Composite id (match su with ST.Struct => TT.Struct | ST.Union => TT.Union end)
      (map map_member members) (map_attr a) end.
Definition composite_ok (d : ST.composite_definition) : bool :=
  match d with ST.Composite _ ST.Struct members a =>
    negb (ST.attr_volatile a) && forallb
      (fun m => match m with ST.Member_plain _ ty => type_ok ty | _ => false end) members
  | _ => false end.

Inductive definition_pair (cp : TA.COMP.compartment) :
    (SA.ident * SA.globdef S.fundef ST.type) ->
    (TA.ident * TA.globdef T.fundef TT.type) -> Prop :=
| internal_pair : forall id f,
    function_ok f = true ->
    definition_pair cp (id, SA.Gfun (ST.Internal f))
      (id, TA.Gfun (TT.Internal (map_function cp f))).

(* RV64 selects ptr64=true in the extracted compiler, but the imported Coq
   Archi module leaves it a Parameter. State that premise exactly where the
   source uses memory/pointers, rather than silently replacing the parameter.
   A register-only closed witness remains inhabited without that assumption. *)
Definition register_type (ty : ST.type) : bool :=
  match ty with ST.Tvoid | ST.Tint _ _ _ | ST.Tlong _ _ => true | _ => false end.
Fixpoint register_expr (e : S.expr) : bool :=
  register_type (S.typeof e) &&
  match e with
  | S.Econst_int _ _ | S.Econst_long _ _ | S.Etempvar _ _ => true
  | S.Eunop _ e _ | S.Ecast e _ => register_expr e
  | S.Ebinop _ a b _ => register_expr a && register_expr b
  | _ => false
  end.
Fixpoint register_stmt (s : S.statement) : bool :=
  match s with
  | S.Sskip | S.Sbreak | S.Scontinue => true
  | S.Sset _ e => register_expr e
  | S.Ssequence a b | S.Sloop a b => register_stmt a && register_stmt b
  | S.Sifthenelse e a b => register_expr e && register_stmt a && register_stmt b
  | S.Sreturn None => true | S.Sreturn (Some e) => register_expr e
  | _ => false
  end.
Definition register_function (f : S.function) : bool :=
  (match S.fn_vars f with [] => true | _ => false end) &&
  register_type (S.fn_return f) &&
  forallb (fun v => register_type (snd v)) (S.fn_params f ++ S.fn_temps f) &&
  register_stmt (S.fn_body f).
Definition register_program (p : S.program) : bool :=
  forallb (fun d => match snd d with SA.Gfun (ST.Internal f) => register_function f
           | _ => false end) (ST.prog_defs p).

Definition program_pair (cp : TA.COMP.compartment) (p : S.program) (q : T.program) : Prop :=
  Forall2 (definition_pair cp) (ST.prog_defs p) (TT.prog_defs q) /\
  ST.prog_public p = TT.prog_public q /\ ST.prog_main p = TT.prog_main q /\
  forallb composite_ok (ST.prog_types p) = true /\
  TT.prog_types q = map map_composite (ST.prog_types p) /\
  (register_program p = false -> Contained.riscV.Archi.ptr64 = true).

(* A premise about actual producer outputs, independently of execution. The
   two relations are fixed by the consumer to its pinned producers, never to
   a simulation relation. Hand AST input is allowed; clightgen requires its
   separate license and source/output binding under F-489. *)
Inductive InputProducer := HandAuthored | LicensedClightgen.
Record FrontendCorrespondence
    (producer : InputProducer)
    (stock_produces : string -> S.program -> Prop)
    (contained_parses : string -> T.program -> Prop) : Type := {
  source_closure : string;
  source_program : S.program;
  contained_program : T.program;
  executive_compartment : TA.COMP.compartment;
  stock_output : stock_produces source_closure source_program;
  contained_output : contained_parses source_closure contained_program;
  corresponding_outputs : program_pair executive_compartment source_program contained_program
}.

Definition cap_free (v : TV.val) : Prop :=
  match v with TV.Vcap _ _ _ => False | _ => True end.
Definition memory_cap_free (m : TM.Mem.mem) : Prop :=
  forall chunk b ofs cp v,
    TM.Mem.load chunk m b ofs cp = Some v -> cap_free v.
Definition temps_cap_free (temps : T.temp_env) : Prop :=
  forall id v, Contained.lib.Maps.PTree.get id temps = Some v -> cap_free v.
Fixpoint continuation_cap_free (k : T.cont) : Prop :=
  match k with
  | T.Kstop => True
  | T.Kseq _ k | T.Kloop1 _ _ k | T.Kloop2 _ _ k | T.Kswitch k =>
      continuation_cap_free k
  | T.Kcall _ _ _ temps k => temps_cap_free temps /\ continuation_cap_free k
  end.
Definition state_cap_free (s : T.state) : Prop :=
  match s with
  | T.State _ _ k _ temps m => memory_cap_free m /\
      temps_cap_free temps /\ continuation_cap_free k
  | T.Callstate _ args k m => memory_cap_free m /\
      Forall cap_free args /\ continuation_cap_free k
  | T.Returnstate v k m _ _ => memory_cap_free m /\ cap_free v /\ continuation_cap_free k
  end.

(* The target must take at least one step for each source step. This finite
   fragment has no external/volatile events, so both traces are exactly E0.
   No simulation, expression-preservation, or memory-preservation result is
   a premise. A proof must construct the relation and discharge every clause. *)
Definition silent_forward_simulation (p : S.program) (q : T.program) : Prop :=
  exists relates : S.state -> T.state -> Prop,
    (forall s, S.initial_state p s ->
      exists t, T.initial_state q t /\ relates s t) /\
    (forall s t, relates s t -> state_cap_free t) /\
    (forall s t r, relates s t -> S.final_state s r ->
      exists r', T.final_state t r' /\ SI.Int.unsigned r = TI.Int.unsigned r') /\
    (forall s t trace s', relates s t ->
      S.step2 (S.globalenv p) s trace s' ->
      trace = Stock.common.Events.E0 /\ exists t',
      Contained.common.Smallstep.plus
        (T.step2 (T.comp_of_main q)) (T.globalenv q)
        t Contained.common.Events.E0 t' /\ relates s' t').

Definition bridge_statement : Prop :=
  forall producer stock_produces contained_parses
    (input : FrontendCorrespondence producer stock_produces contained_parses),
    silent_forward_simulation
      (source_program producer stock_produces contained_parses input)
      (contained_program producer stock_produces contained_parses input).

(* Closed input witness: a hand-authored AST pair for the same complete C
   source. This tests the correspondence premise, not the real parser. *)
Definition zero_source : string := "int main(void) { return 0; }"%string.
Definition zero_function : S.function :=
  S.mkfunction (ST.Tint ST.I32 ST.Signed ST.noattr) SA.cc_default [] [] []
    (S.Sreturn (Some (S.Econst_int SI.Int.zero (ST.Tint ST.I32 ST.Signed ST.noattr)))).
Definition zero_stock : S.program :=
  {| ST.prog_defs := [(1%positive, SA.Gfun (ST.Internal zero_function))];
     ST.prog_public := [1%positive]; ST.prog_main := 1%positive;
     ST.prog_types := []; ST.prog_comp_env := Stock.lib.Maps.PTree.empty _;
     ST.prog_comp_env_eq := eq_refl |}.
Lemma zero_names_norepet : Contained.lib.Coqlib.list_norepet [1%positive].
Proof. repeat constructor; simpl; tauto. Qed.
Definition zero_contained_result :=
  TT.make_program []
    [(1%positive, TA.Gfun (TT.Internal (map_function TA.COMP.bottom zero_function)))]
    [1%positive] 1%positive TA.Policy.empty_pol zero_names_norepet.
Definition zero_contained : T.program.
Proof.
  exact (match zero_contained_result as r return
           (match r with Contained.common.Errors.OK _ => T.program | _ => unit end)
         with Contained.common.Errors.OK p => p | _ => tt end).
Defined.
Definition zero_stock_produces c p : Prop := c = zero_source /\ p = zero_stock.
Definition zero_contained_parses c p : Prop := c = zero_source /\ p = zero_contained.
Definition witness_FrontendCorrespondence :
  FrontendCorrespondence HandAuthored zero_stock_produces zero_contained_parses.
Proof.
  refine {| source_closure := zero_source; source_program := zero_stock;
            contained_program := zero_contained; executive_compartment := TA.COMP.bottom;
            stock_output := conj eq_refl eq_refl; contained_output := conj eq_refl eq_refl |}.
  split.
  - repeat constructor.
  - repeat split; try reflexivity. intros H. discriminate H.
Defined.

(* An actual function copies a declared capability-valued caller argument into
   a new temporary. Function entry and sequence entry reach the copy step;
   its result cannot belong to the fragment. This is not integer forgery. *)
Definition bad_meta : TV.capmeta := TV.mkcapmeta true TI.Int64.zero TI.Int64.zero
  TI.Int64.zero TI.Int64.zero TI.Int64.zero.
Definition bad_cap : TV.val := TV.Vcap 1%positive TI.Ptrofs.zero bad_meta.
Definition bad_pointer_type := TT.Tpointer (TT.Tint TT.I32 TT.Signed TT.noattr) TT.noattr.
Definition bad_expr := T.Etempvar 2%positive bad_pointer_type.
Definition bad_rest :=
  T.Sreturn (Some (T.Econst_int TI.Int.zero (TT.Tint TT.I32 TT.Signed TT.noattr))).
Definition bad_function := T.mkfunction TA.COMP.bottom
  (TT.Tint TT.I32 TT.Signed TT.noattr) TA.cc_default
  [(2%positive, bad_pointer_type)] [] [(3%positive, bad_pointer_type)]
  (T.Ssequence (T.Sset 3%positive bad_expr) bad_rest).
Definition bad_program_result := TT.make_program []
  [(1%positive, TA.Gfun (TT.Internal bad_function))]
  [1%positive] 1%positive TA.Policy.empty_pol zero_names_norepet.
Definition bad_program : T.program.
Proof.
  exact (match bad_program_result as r return
           (match r with Contained.common.Errors.OK _ => T.program | _ => unit end)
         with Contained.common.Errors.OK p => p | _ => tt end).
Defined.
Definition bad_temps := Contained.lib.Maps.PTree.set 2%positive bad_cap
  (T.create_undef_temps (T.fn_temps bad_function)).
Definition bad_call := T.Callstate (TT.Internal bad_function) [bad_cap] T.Kstop TM.Mem.empty.
Definition bad_entry := T.State bad_function (T.fn_body bad_function)
  T.Kstop T.empty_env bad_temps TM.Mem.empty.
Definition bad_before : T.state :=
  T.State bad_function (T.Sset 3%positive bad_expr) (T.Kseq bad_rest T.Kstop)
    T.empty_env bad_temps TM.Mem.empty.
Definition bad_after : T.state :=
  T.State bad_function T.Sskip (T.Kseq bad_rest T.Kstop) T.empty_env
    (Contained.lib.Maps.PTree.set 3%positive bad_cap bad_temps) TM.Mem.empty.
Lemma capability_call_entry_step :
  T.step2 TA.COMP.bottom (T.globalenv bad_program)
    bad_call Contained.common.Events.E0 bad_entry.
Proof.
  apply T.step_internal_function. constructor.
  - constructor.
  - repeat constructor; simpl; tauto.
  - unfold Contained.lib.Coqlib.list_disjoint; simpl; intros x H1 H2; intuition congruence.
  - constructor.
  - reflexivity.
Qed.
Lemma capability_body_entry_step :
  T.step2 TA.COMP.bottom (T.globalenv bad_program)
    bad_entry Contained.common.Events.E0 bad_before.
Proof. apply T.step_seq. Qed.
Lemma capability_producing_step :
  T.step2 TA.COMP.bottom (T.globalenv bad_program)
    bad_before Contained.common.Events.E0 bad_after.
Proof.
  apply T.step_set. apply T.eval_Etempvar.
  apply Contained.lib.Maps.PTree.gss.
Qed.
Lemma capability_instance_refuted : ~ state_cap_free bad_after.
Proof.
  intros [_ [H _]]. specialize (H 3%positive bad_cap (Contained.lib.Maps.PTree.gss _ _ _)).
  exact H.
Qed.
Lemma witness_source_return_step :
  S.eval_expr (S.globalenv zero_stock) S.empty_env
    (Stock.lib.Maps.PTree.empty SV.val) SM.Mem.empty
    (S.Econst_int SI.Int.zero (ST.Tint ST.I32 ST.Signed ST.noattr)) (SV.Vint SI.Int.zero).
Proof. constructor. Qed.
Lemma witness_target_return_value :
  T.eval_expr (T.globalenv zero_contained) T.empty_env TA.COMP.bottom
    (Contained.lib.Maps.PTree.empty TV.val) TM.Mem.empty
    (T.Econst_int TI.Int.zero (TT.Tint TT.I32 TT.Signed TT.noattr)) (TV.Vint TI.Int.zero).
Proof. constructor. Qed.

About bridge_statement. Print Assumptions bridge_statement.
About witness_FrontendCorrespondence. Print Assumptions witness_FrontendCorrespondence.
About capability_call_entry_step. Print Assumptions capability_call_entry_step.
About capability_body_entry_step. Print Assumptions capability_body_entry_step.
About capability_producing_step. Print Assumptions capability_producing_step.
About capability_instance_refuted. Print Assumptions capability_instance_refuted.
About witness_source_return_step. Print Assumptions witness_source_return_step.
About witness_target_return_value. Print Assumptions witness_target_return_value.

