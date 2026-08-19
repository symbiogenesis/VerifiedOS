(* =========================================================================
   SeamWitnesses.v

   Per-seam non-vacuity witnesses: the R-05-165 / R-05-166 discipline that
   ApexTheorem.v applies to T, applied to each of R-05-160's nine seam
   lemmas and to the composition meta-lemma, one distinguishing instance
   each. A companion to the statement artifact, not part of it: this file
   imports ApexTheorem.v, adds no Prop to the Vocabulary record, no seam,
   no obligation, and no axiom, and everything here is proved outright.
   Crown-jewel row 1 is unchanged by this file's existence.

   Why per-seam. ApexTheorem.v's two global witnesses show that T is
   satisfiable in one model and refutable in another, which closes
   R-05-165's three vacuity modes for T itself. But the seam lemmas are
   the units that proof workstreams will discharge and that refactoring
   re-opens, and each is an implication that could be weakened to a
   tautology without T's witnesses noticing until the linking theorem,
   R-18-031(b), which is staged last, the worst place to learn it. So
   each seam gets its own distinguishing instance: a model in which the
   seam's premises hold and its conclusion fails, so the seam statement
   is refutable and therefore excludes something. A future edit that
   makes some seam's conclusion trivially derivable from its premises
   (collapsing an interface, weakening a field to True by definition)
   breaks that seam's witness here, and the failure lands at this file's
   compile rather than at the capstone.

   The same instance is built for the composition meta-lemma over
   leaky_vocabulary: every substrate invariant, seam, and tower rung
   holds there and T fails, so the meta-lemma is refutable, which is the
   machine-checked form of "the linking theorem has content": the seam
   conclusions alone do not entail T, and R-18-031(b) is a real
   obligation rather than an unfolding.

   Inhabitation is also stated per family: the nine seams, the substrate,
   the tower, and the meta-lemma are each provable at trivial_vocabulary,
   so no witness below refutes a statement that was unsatisfiable to
   begin with.

   The construction is one parameterized model, the one-point machine of
   trivial_vocabulary with the nine seam-conclusion fields exposed as
   parameters. Refuting seam k is instantiating conclusion k at False and
   the rest at True: every premise field stays True, so the implication
   fails on the conclusion alone. Where a conclusion is also another
   seam's premise (composed_schedulability feeds seam 6, ae_ind_cca_int_ctxt
   feeds seam 5), the witness claims nothing about that other seam.
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
  consent_correctness := True;
  Ax_machine := True;
  Ax_hardness := True;
  Ax_human := True;
  ax_machine_carries_die_matches_rtl := fun _ => I;
  ax_hardness_carries_conjectures := fun _ => I;
  ax_human_carries_consent := fun _ => I
|}.

(* -------------------------------------------------------------------------
   Inhabitation: each statement family is provable at trivial_vocabulary,
   so the refutations below are of satisfiable statements. The seam case
   covers all nine at once because seam_lemmas is their conjunction.
   ------------------------------------------------------------------------- *)

Lemma seam_lemmas_inhabitation : seam_lemmas trivial_vocabulary.
Proof. repeat split; intro H; exact I. Qed.

Lemma substrate_and_tower_inhabitation :
  substrate_invariants trivial_vocabulary /\ refinement_tower trivial_vocabulary.
Proof. repeat split. Qed.

Lemma composition_meta_lemma_inhabitation :
  composition_meta_lemma trivial_vocabulary.
Proof. intros _. exact statement_inhabitation_witness. Qed.

(* -------------------------------------------------------------------------
   The nine distinguishing instances, in R-05-160's order. Each vocabulary
   sets exactly one conclusion to False; each proof applies the seam's
   implication to its trivially satisfied premises.
   ------------------------------------------------------------------------- *)

(* 1. NI joins timing: partition_guarantee refused. *)
Definition refutes_seam_ni_timing : Vocabulary :=
  conclusion_witness_vocabulary False True True True True True True True True.

Lemma seam_ni_timing_distinguishing :
  ~ seam_ni_timing refutes_seam_ni_timing.
Proof. exact (fun H => H (conj I I)). Qed.

(* 2. WCET joins isolation: composed_schedulability refused. *)
Definition refutes_seam_wcet_isolation : Vocabulary :=
  conclusion_witness_vocabulary True False True True True True True True True.

Lemma seam_wcet_isolation_distinguishing :
  ~ seam_wcet_isolation refutes_seam_wcet_isolation.
Proof. exact (fun H => H (conj I I)). Qed.

(* 3. CT joins RTL and Sail: constant_time_on_die refused; the
      rtl_refines_sail premise, the tower's own rung, stays True. *)
Definition refutes_seam_ct_rtl_sail : Vocabulary :=
  conclusion_witness_vocabulary True True False True True True True True True.

Lemma seam_ct_rtl_sail_distinguishing :
  ~ seam_ct_rtl_sail refutes_seam_ct_rtl_sail.
Proof. exact (fun H => H (conj I I)). Qed.

(* 4. CHERI-TAL joins Sail: admitted_binaries_safe refused. *)
Definition refutes_seam_cheri_tal_sail : Vocabulary :=
  conclusion_witness_vocabulary True True True False True True True True True.

Lemma seam_cheri_tal_sail_distinguishing :
  ~ seam_cheri_tal_sail refutes_seam_cheri_tal_sail.
Proof. exact (fun H => H (conj I I)). Qed.

(* 5. AE joins non-interference: verifiable_encryption refused; the
      ae_ind_cca_int_ctxt premise stays True here. *)
Definition refutes_seam_ae_noninterference : Vocabulary :=
  conclusion_witness_vocabulary True True True True False True True True True.

Lemma seam_ae_noninterference_distinguishing :
  ~ seam_ae_noninterference refutes_seam_ae_noninterference.
Proof. exact (fun H => H (conj I I)). Qed.

(* 6. Liveness joins schedulability: progress_guarantee refused; the
      composed_schedulability premise stays True here. *)
Definition refutes_seam_liveness_schedulability : Vocabulary :=
  conclusion_witness_vocabulary True True True True True False True True True.

Lemma seam_liveness_schedulability_distinguishing :
  ~ seam_liveness_schedulability refutes_seam_liveness_schedulability.
Proof. exact (fun H => H (conj I I)). Qed.

(* 7. Consent joins declassification: declassified_flows_authorized
      refused under a satisfied consent_correctness. *)
Definition refutes_seam_consent_declassification : Vocabulary :=
  conclusion_witness_vocabulary True True True True True True False True True.

Lemma seam_consent_declassification_distinguishing :
  ~ seam_consent_declassification refutes_seam_consent_declassification.
Proof. exact (fun H => H I). Qed.

(* 8. Crypto joins hardness: ae_ind_cca_int_ctxt refused. In this model
      seam 5's premise is thereby False too; nothing is claimed of it. *)
Definition refutes_seam_crypto_hardness : Vocabulary :=
  conclusion_witness_vocabulary True True True True True True True False True.

Lemma seam_crypto_hardness_distinguishing :
  ~ seam_crypto_hardness refutes_seam_crypto_hardness.
Proof. exact (fun H => H (conj I I)). Qed.

(* 9. Attestation joins capability safety: image_binding refused under
      all three premises, the initialisation refinement included. *)
Definition refutes_seam_attestation_capability_safety : Vocabulary :=
  conclusion_witness_vocabulary True True True True True True True True False.

Lemma seam_attestation_capability_safety_distinguishing :
  ~ seam_attestation_capability_safety refutes_seam_attestation_capability_safety.
Proof. exact (fun H => H (conj I (conj I I))). Qed.

(* -------------------------------------------------------------------------
   The meta-lemma's own distinguishing instance: at leaky_vocabulary every
   substrate invariant, every seam, and every tower rung holds (each field
   is True there), and T is refutable, so the composition meta-lemma is
   refutable. The linking theorem R-18-031(b) therefore has content: the
   seam conclusions alone do not entail T.
   ------------------------------------------------------------------------- *)

Lemma composition_meta_lemma_distinguishing :
  ~ composition_meta_lemma leaky_vocabulary.
Proof.
  intro H.
  apply statement_distinguishing_instance.
  apply H.
  repeat split; intro K; exact I.
Qed.

(* -------------------------------------------------------------------------
   The R-05-163 gate, as in ApexTheorem.v: every constant closed under the
   global context, checked by tools/proof-gate.sh against the declared set
   R-05-164 currently makes empty.
   ------------------------------------------------------------------------- *)

Print Assumptions seam_lemmas_inhabitation.
Print Assumptions substrate_and_tower_inhabitation.
Print Assumptions composition_meta_lemma_inhabitation.
Print Assumptions seam_ni_timing_distinguishing.
Print Assumptions seam_wcet_isolation_distinguishing.
Print Assumptions seam_ct_rtl_sail_distinguishing.
Print Assumptions seam_cheri_tal_sail_distinguishing.
Print Assumptions seam_ae_noninterference_distinguishing.
Print Assumptions seam_liveness_schedulability_distinguishing.
Print Assumptions seam_consent_declassification_distinguishing.
Print Assumptions seam_attestation_capability_safety_distinguishing.
Print Assumptions seam_crypto_hardness_distinguishing.
Print Assumptions composition_meta_lemma_distinguishing.
