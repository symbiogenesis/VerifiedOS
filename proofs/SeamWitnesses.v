(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   SeamWitnesses.v

   Distinguishing witnesses for R-05-160's nine seam statements and the
   composition meta-lemma, following R-05-165 and R-05-166. Each witness
   satisfies a seam's premises and refutes its conclusion. This catches
   weakening a seam into a tautology even when T's global witnesses survive.

   The parameterized model uses trivial_vocabulary's one-point machine with
   nine independently chosen seam conclusions. To refute seam k, conclusion
   k is False and the rest are True. A conclusion may also be another seam's
   premise: composed_schedulability feeds seam 6 and ae_ind_cca_int_ctxt
   feeds seam 5. The witness makes no claim about those other seams.

   At leaky_vocabulary, the substrate invariants, seams and tower rungs hold
   while T fails. This refutes the ledger-only implication and shows why
   R-18-031(b)'s linking theorem needs actual semantic transports. Each statement
   family is also inhabited at trivial_vocabulary, so the refutations do not
   rely on unsatisfiable statements.

   This companion imports ApexTheorem without changing Vocabulary, the
   seam statements or crown-jewel row 1. It adds no axioms or obligations.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-160 R-05-163 R-05-164 R-05-165 R-05-166 R-18-031
   SHA256: 775dfecaaa575f3e8a7f0d8c9925b7edfe61b3a3effb15cffe0423c886f7d36e
   (*| END derived |*)
   ========================================================================= *)

Require Import ApexTheorem.

(* -------------------------------------------------------------------------
   The parameterized model: trivial_vocabulary with the nine seam
   conclusions as parameters, in seam order (R-05-160's order, which
   ApexTheorem.v's definitions follow).
   ------------------------------------------------------------------------- *)

Definition conclusion_witness_vocabulary
  (w_partition_guarantee
   w_composed_schedulability
   w_constant_time_on_die
   w_admitted_binaries_safe
   w_verifiable_encryption
   w_progress_guarantee
   w_declassified_flows_authorized
   w_ae_ind_cca_int_ctxt
   w_image_binding : Prop) : Vocabulary := {|
  Input := unit;
  Trace := unit;
  exec := fun _ => tt;
  Compartment := unit;
  tcb := fun _ => False;
  graph_permits := fun _ => True;
  Policy := unit;
  policy := tt;
  indist := fun _ _ _ _ => True;
  ValueObs := unit;
  TimingObs := unit;
  ArchObs := unit;
  observe_value := fun _ _ => tt;
  observe_timing := fun _ _ => tt;
  observe_arch := fun _ _ => tt;
  Declass := unit;
  D := tt;
  release_value := fun _ o => o;
  release_timing := fun _ o => o;
  release_arch := fun _ o => o;
  spatial_safety := True;
  temporal_safety := True;
  wx_exclusivity := True;
  write_before_read := True;
  source_refines_spec := True;
  binary_refines_source_robustly := True;
  binary_against_sail := True;
  rtl_refines_sail := True;
  explicit_flow_noninterference := True;
  timing_isolation := True;
  partition_guarantee := w_partition_guarantee;
  wcet_bounds_sound := True;
  composed_schedulability := w_composed_schedulability;
  constant_time_typed := True;
  constant_time_on_die := w_constant_time_on_die;
  cheri_tal_soundness := True;
  admission_type_check := True;
  admitted_binaries_safe := w_admitted_binaries_safe;
  crypto_reductions := True;
  ae_ind_cca_int_ctxt := w_ae_ind_cca_int_ctxt;
  storage_noninterference := True;
  verifiable_encryption := w_verifiable_encryption;
  kernel_liveness := True;
  progress_guarantee := w_progress_guarantee;
  declassified_flows_authorized := w_declassified_flows_authorized;
  init_realizes_topology := True;
  attestation_chain := True;
  image_binding := w_image_binding;
  die_matches_rtl := True;
  hardness_conjectures := True;
  idealized_model_assumptions := True;
  consent_correctness := True;
  Ax_machine := True;
  Ax_hardness := True;
  Ax_model := True;
  Ax_estimate := True;
  Ax_human := True;
  ax_machine_carries_die_matches_rtl := fun _ => I;
  ax_hardness_carries_conjectures := fun _ => I;
  ax_model_carries_assumptions := fun _ => I;
  ax_human_carries_consent := fun _ => I
|}.

(* -------------------------------------------------------------------------
   Inhabitation: each statement family is provable at trivial_vocabulary,
   so the refutations below are of satisfiable statements. The seam case
   covers all nine at once because seam_lemmas is their conjunction.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_lemmas_inhabitation : seam_lemmas trivial_vocabulary.
Proof. repeat split; intro H; exact I. Qed.

(*| discharges: R-05-165, R-05-166 |*)
Lemma substrate_and_tower_inhabitation :
  substrate_invariants trivial_vocabulary /\ refinement_tower trivial_vocabulary.
Proof. repeat split. Qed.

(*| discharges: R-05-165, R-05-166 |*)
Lemma composition_meta_lemma_inhabitation :
  composition_meta_lemma trivial_vocabulary trivial_vocabulary.
Proof. exact (semantic_composition_meta_lemma trivial_vocabulary trivial_vocabulary). Qed.

(* -------------------------------------------------------------------------
   The nine distinguishing instances, in R-05-160's order. Each vocabulary
   sets exactly one conclusion to False; each proof applies the seam's
   implication to its trivially satisfied premises.
   ------------------------------------------------------------------------- *)

(* 1. NI joins timing: partition_guarantee refused. *)
Definition refutes_seam_ni_timing : Vocabulary :=
  conclusion_witness_vocabulary False True True True True True True True True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_ni_timing_distinguishing :
  ~ seam_ni_timing refutes_seam_ni_timing.
Proof. exact (fun H => H (conj I I)). Qed.

(* 2. WCET joins isolation: composed_schedulability refused. *)
Definition refutes_seam_wcet_isolation : Vocabulary :=
  conclusion_witness_vocabulary True False True True True True True True True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_wcet_isolation_distinguishing :
  ~ seam_wcet_isolation refutes_seam_wcet_isolation.
Proof. exact (fun H => H (conj I I)). Qed.

(* 3. CT joins RTL and Sail: constant_time_on_die refused; the
      rtl_refines_sail premise, the tower's own rung, stays True. *)
Definition refutes_seam_ct_rtl_sail : Vocabulary :=
  conclusion_witness_vocabulary True True False True True True True True True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_ct_rtl_sail_distinguishing :
  ~ seam_ct_rtl_sail refutes_seam_ct_rtl_sail.
Proof. exact (fun H => H (conj I I)). Qed.

(* 4. CHERI-TAL joins Sail: admitted_binaries_safe refused. *)
Definition refutes_seam_cheri_tal_sail : Vocabulary :=
  conclusion_witness_vocabulary True True True False True True True True True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_cheri_tal_sail_distinguishing :
  ~ seam_cheri_tal_sail refutes_seam_cheri_tal_sail.
Proof. exact (fun H => H (conj I I)). Qed.

(* 5. AE joins non-interference: verifiable_encryption refused; the
      ae_ind_cca_int_ctxt premise stays True here. *)
Definition refutes_seam_ae_noninterference : Vocabulary :=
  conclusion_witness_vocabulary True True True True False True True True True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_ae_noninterference_distinguishing :
  ~ seam_ae_noninterference refutes_seam_ae_noninterference.
Proof. exact (fun H => H (conj I I)). Qed.

(* 6. Liveness joins schedulability: progress_guarantee refused; the
      composed_schedulability premise stays True here. *)
Definition refutes_seam_liveness_schedulability : Vocabulary :=
  conclusion_witness_vocabulary True True True True True False True True True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_liveness_schedulability_distinguishing :
  ~ seam_liveness_schedulability refutes_seam_liveness_schedulability.
Proof. exact (fun H => H (conj I I)). Qed.

(* 7. Consent joins declassification: declassified_flows_authorized
      refused under a satisfied consent_correctness. *)
Definition refutes_seam_consent_declassification : Vocabulary :=
  conclusion_witness_vocabulary True True True True True True False True True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_consent_declassification_distinguishing :
  ~ seam_consent_declassification refutes_seam_consent_declassification.
Proof. exact (fun H => H I). Qed.

(* 8. Crypto joins hardness: ae_ind_cca_int_ctxt refused. In this model
      seam 5's premise is thereby False too; nothing is claimed of it. *)
Definition refutes_seam_crypto_hardness : Vocabulary :=
  conclusion_witness_vocabulary True True True True True True True False True.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_crypto_hardness_distinguishing :
  ~ seam_crypto_hardness refutes_seam_crypto_hardness.
Proof. exact (fun H => H (conj I (conj I I))). Qed.

(* 9. Attestation joins capability safety: image_binding refused under
      all three premises, the initialisation refinement included. *)
Definition refutes_seam_attestation_capability_safety : Vocabulary :=
  conclusion_witness_vocabulary True True True True True True True True False.

(*| discharges: R-05-165, R-05-166 |*)
Lemma seam_attestation_capability_safety_distinguishing :
  ~ seam_attestation_capability_safety refutes_seam_attestation_capability_safety.
Proof. exact (fun H => H (conj I (conj I I))). Qed.

(* -------------------------------------------------------------------------
   The meta-lemma's own distinguishing instance: at leaky_vocabulary every
   substrate invariant, every seam, and every tower rung holds (each field
   is True there), and T is refutable, so the ledger-only implication is
   refutable. The ledger is a coverage checklist and supplies no transport:
   the seam conclusions alone do not entail T.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-165, R-05-166 |*)
Lemma composition_meta_lemma_distinguishing :
  ~ ledger_only_composition leaky_vocabulary.
Proof.
  intro H.
  apply statement_distinguishing_instance.
  apply H.
  repeat split; intro K; exact I.
Qed.

(* R-05-163 and R-05-164: `run.py proofs` audits the complete native inventory. *)


(* Semantic transport controls for [R-05-161](../docs/spec.md#r-05-161).
   The examples distinguish public input from secret input. The positive
   source keeps only the public bit; the target also stores the secret bit
   in its trace but exposes only public observations. Their traces differ
   in type and contents, so the source theorem is not T of the target under
   another name. No example instantiates a production coverage field. *)

Definition semantic_witness_vocabulary (TraceType : Type)
    (run : (bool * bool)%type -> TraceType)
    (value timing : TraceType -> bool) (architectural : TraceType -> (bool * bool)%type)
    (inputs : (bool * bool)%type -> (bool * bool)%type -> Prop)
    (contexts : (unit -> Prop) -> Prop) (released : bool -> bool) : Vocabulary := {|
  Input := (bool * bool)%type;
  Trace := TraceType;
  exec := run;
  Compartment := unit;
  tcb := fun _ => False;
  graph_permits := contexts;
  Policy := unit;
  policy := tt;
  indist := fun _ _ => inputs;
  ValueObs := bool;
  TimingObs := bool;
  ArchObs := (bool * bool)%type;
  observe_value := fun _ => value;
  observe_timing := fun _ => timing;
  observe_arch := fun _ => architectural;
  Declass := unit;
  D := tt;
  release_value := fun _ => released;
  release_timing := fun _ o => o;
  release_arch := fun _ o => o;
  spatial_safety := True;
  temporal_safety := True;
  wx_exclusivity := True;
  write_before_read := True;
  source_refines_spec := True;
  binary_refines_source_robustly := True;
  binary_against_sail := True;
  rtl_refines_sail := True;
  explicit_flow_noninterference := True;
  timing_isolation := True;
  partition_guarantee := True;
  wcet_bounds_sound := True;
  composed_schedulability := True;
  constant_time_typed := True;
  constant_time_on_die := True;
  cheri_tal_soundness := True;
  admission_type_check := True;
  admitted_binaries_safe := True;
  crypto_reductions := True;
  ae_ind_cca_int_ctxt := True;
  storage_noninterference := True;
  verifiable_encryption := True;
  kernel_liveness := True;
  progress_guarantee := True;
  declassified_flows_authorized := True;
  init_realizes_topology := True;
  attestation_chain := True;
  image_binding := True;
  die_matches_rtl := True;
  hardness_conjectures := True;
  idealized_model_assumptions := True;
  consent_correctness := True;
  Ax_machine := True;
  Ax_hardness := True;
  Ax_model := True;
  Ax_estimate := True;
  Ax_human := True;
  ax_machine_carries_die_matches_rtl := fun _ => I;
  ax_hardness_carries_conjectures := fun _ => I;
  ax_model_carries_assumptions := fun _ => I;
  ax_human_carries_consent := fun _ => I
|}.

Definition semantic_source : Vocabulary :=
  semantic_witness_vocabulary bool (@fst bool bool)
    (fun p => p) negb (fun p => (p, true))
    (fun i1 i2 => fst i1 = fst i2) (fun _ => True) (fun o => o).

Definition semantic_target : Vocabulary :=
  semantic_witness_vocabulary (bool * bool)%type (fun i => i)
    (@fst bool bool) (fun i => negb (fst i)) (fun i => (fst i, true))
    (fun i1 i2 => fst i1 = fst i2) (fun _ => True) (fun o => o).

Lemma semantic_source_secure : T semantic_source.
Proof.
  intros _ C _ i1 i2 Hpublic.
  change (fst i1 = fst i2 /\ negb (fst i1) = negb (fst i2) /\
    (fst i1, true) = (fst i2, true)).
  change (fst i1 = fst i2) in Hpublic.
  rewrite Hpublic; repeat split.
Qed.

Definition semantic_positive_binding : SemanticTransport semantic_source semantic_target.
Proof.
  refine (@Build_SemanticTransport semantic_source semantic_target
    (fun i => i) (fun C => C) (fun o => o) (fun o => o) (fun o => o)
    (fun H => H) (fun _ H => H) (fun _ _ _ _ _ H => H) _ _ _);
    intros; reflexivity.
Defined.

Lemma semantic_target_secure : T semantic_target.
Proof.
  exact (transport_T semantic_source semantic_target semantic_positive_binding
    semantic_source_secure).
Qed.

Lemma semantic_witness_inputs_are_distinct :
  (false, true) <> (false, false) /\
  semantic_target.(indist) semantic_target.(policy) (fun _ => True)
    (false, true) (false, false) /\
  semantic_target.(observe_value) (fun _ => True) (semantic_target.(exec) (true, false)) <>
    semantic_target.(observe_value) (fun _ => True) (semantic_target.(exec) (false, false)).
Proof. split; [discriminate | split; [reflexivity | discriminate]]. Qed.

Definition semantic_identity_binding : SemanticTransport semantic_target semantic_target.
Proof.
  refine {| transport_input := fun i => i;
    transport_context := fun C => C;
    transport_value := fun o => o;
    transport_timing := fun o => o;
    transport_arch := fun o => o;
    transport_ax := fun H => H;
    transport_admissible := fun _ H => H;
    transport_indist := fun _ _ _ _ _ H => H |};
    intros; reflexivity.
Defined.

Lemma semantic_composed_target_secure : T semantic_target.
Proof.
  exact (transport_T semantic_source semantic_target
    (compose_transport semantic_source semantic_target semantic_target
      semantic_positive_binding semantic_identity_binding) semantic_source_secure).
Qed.

Definition semantic_timing_leak : Vocabulary :=
  semantic_witness_vocabulary (bool * bool)%type (fun i => i)
    (@fst bool bool) (@snd bool bool) (fun i => (fst i, true))
    (fun i1 i2 => fst i1 = fst i2) (fun _ => True) (fun o => o).

Lemma omitted_timing_value_and_arch_agree : forall C i,
  semantic_timing_leak.(observe_value) C (semantic_timing_leak.(exec) i) =
    semantic_source.(observe_value) C (semantic_source.(exec) i) /\
  semantic_timing_leak.(observe_arch) C (semantic_timing_leak.(exec) i) =
    semantic_source.(observe_arch) C (semantic_source.(exec) i).
Proof. intros; split; reflexivity. Qed.

Lemma omitted_timing_is_rejected : ~ T semantic_timing_leak.
Proof.
  intro H.
  destruct (H (conj I (conj I (conj I (conj I I)))) (fun _ => True)
    (conj I (fun _ _ contra => contra)) (false, true) (false, false) eq_refl)
    as [_ [Htiming _]].
  discriminate Htiming.
Qed.

Lemma omitted_timing_has_no_secure_binding :
  SemanticTransport semantic_source semantic_timing_leak -> False.
Proof.
  intro binding; apply omitted_timing_is_rejected.
  exact (transport_T semantic_source semantic_timing_leak binding semantic_source_secure).
Qed.

Definition semantic_arch_leak : Vocabulary :=
  semantic_witness_vocabulary (bool * bool)%type (fun i => i)
    (@fst bool bool) (fun i => negb (fst i)) (fun i => (fst i, snd i))
    (fun i1 i2 => fst i1 = fst i2) (fun _ => True) (fun o => o).

Lemma omitted_arch_is_rejected : ~ T semantic_arch_leak.
Proof.
  intro H.
  destruct (H (conj I (conj I (conj I (conj I I)))) (fun _ => True)
    (conj I (fun _ _ contra => contra)) (false, true) (false, false) eq_refl)
    as [_ [_ Harch]].
  discriminate Harch.
Qed.

Lemma omitted_arch_has_no_secure_binding :
  SemanticTransport semantic_source semantic_arch_leak -> False.
Proof.
  intro binding; apply omitted_arch_is_rejected.
  exact (transport_T semantic_source semantic_arch_leak binding semantic_source_secure).
Qed.

Lemma incompatible_input_map_is_rejected :
  ~ (forall (i1 i2 : (bool * bool)%type),
    semantic_target.(indist) semantic_target.(policy) (fun _ => True) i1 i2 ->
    semantic_source.(indist) semantic_source.(policy) (fun _ => True)
      (snd i1, fst i1) (snd i2, fst i2)).
Proof.
  intro H.
  specialize (H (false, true) (false, false) eq_refl).
  discriminate H.
Qed.

Definition semantic_restricted_context : Vocabulary :=
  semantic_witness_vocabulary bool (@fst bool bool)
    (fun p => p) negb (fun p => (p, true))
    (fun i1 i2 => fst i1 = fst i2) (fun C => ~ C tt) (fun o => o).

Lemma incompatible_context_map_is_rejected :
  ~ (forall C, admissible semantic_target C -> admissible semantic_restricted_context C).
Proof.
  intro H.
  destruct (H (fun _ => True) (conj I (fun _ _ contra => contra))) as [Hcontext _].
  exact (Hcontext I).
Qed.

Definition semantic_redacted_source : Vocabulary :=
  semantic_witness_vocabulary (bool * bool)%type (fun i => i)
    (@snd bool bool) (fun i => negb (fst i)) (fun i => (fst i, true))
    (fun i1 i2 => fst i1 = fst i2) (fun _ => True) (fun _ => false).

Definition semantic_value_leak : Vocabulary :=
  semantic_witness_vocabulary (bool * bool)%type (fun i => i)
    (@snd bool bool) (fun i => negb (fst i)) (fun i => (fst i, true))
    (fun i1 i2 => fst i1 = fst i2) (fun _ => True) (fun o => o).

Lemma redacted_source_secure : T semantic_redacted_source.
Proof.
  intros _ C _ i1 i2 Hpublic.
  change (false = false /\ negb (fst i1) = negb (fst i2) /\
    (fst i1, true) = (fst i2, true)).
  change (fst i1 = fst i2) in Hpublic.
  rewrite Hpublic; repeat split.
Qed.

Lemma raw_values_agree_despite_incompatible_declassification : forall C i,
  semantic_redacted_source.(observe_value) C (semantic_redacted_source.(exec) i) =
  semantic_value_leak.(observe_value) C (semantic_value_leak.(exec) i).
Proof. intros; reflexivity. Qed.

Lemma incompatible_declassification_is_rejected : ~ T semantic_value_leak.
Proof.
  intro H.
  destruct (H (conj I (conj I (conj I (conj I I)))) (fun _ => True)
    (conj I (fun _ _ contra => contra)) (false, true) (false, false) eq_refl)
    as [Hvalue _].
  discriminate Hvalue.
Qed.

Lemma incompatible_declassification_has_no_secure_binding :
  SemanticTransport semantic_redacted_source semantic_value_leak -> False.
Proof.
  intro binding; apply incompatible_declassification_is_rejected.
  exact (transport_T semantic_redacted_source semantic_value_leak binding
    redacted_source_secure).
Qed.

Lemma leaky_ledger_has_no_secure_binding (source : Vocabulary) :
  T source -> SemanticTransport source leaky_vocabulary -> False.
Proof.
  intros Hsource binding; apply statement_distinguishing_instance.
  exact (transport_T source leaky_vocabulary binding Hsource).
Qed.
