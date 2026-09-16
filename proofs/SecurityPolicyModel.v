(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   SecurityPolicyModel.v

   The security policy model: crown-jewel inventory row 2, the specification
   R-08-028 confers the status on and R-17-012 names by its two halves, the
   delimited-release bound and the robust-declassification statement. The
   prose half is docs/assurance/security-policy-model.md; this file is the
   machine-checked side of the same specification, and where the two
   disagree the register wins and both are defective.

   A specification and finite reference examples, not a proof of the composed
   machine. PolicyModel instantiates ApexTheorem's policy interfaces; the
   first and seventh seam targets have concrete predicates. Other Vocabulary
   fields are True only in these examples and are not discharged workstreams.

   Decisions and remaining refinement obligations:
   - Levels form a nonempty finite lattice, with checked binary joins and
     meets. Domains are any sets of carried compartments; non-TCB membership
     is ApexTheorem.admissible's separate condition.
   - Ordinary external stimuli have separate content and cycle-arrival labels
     (R-05-156a). Authority to drive a site is separate from authority to
     observe it (R-05-156b). Labelling and input functions are total; indices
     beyond the checked finite region remain in the relation. Binding those
     total functions and the finite manifest to a real composition is open.
   - Typed consent evidence names an exact Grant. GrantState is a trusted
     lifecycle snapshot. Its freshness, revocation, one-shot consumption,
     unlock, compatibility, request and call-lifetime facts are input
     abstractions, not proofs of their producers. R-08-025's persistent-store
     freshness premise is explicit in the Persistent arm of live.
   - Robustness quantifies over arbitrary off-consent input variation with
     the authenticated consent and trusted lifecycle context fixed. Relating
     an interactive compromised strategy and its allowed revoke-only actions
     to this input-pair abstraction remains an implementation obligation.
   - The release relation equates only live named-object input content in
     addition to the base policy. Every output observation remains visible,
     so another secret cannot be smuggled through the named output slot. The compose-time timing alternative is exhibited below;
     the register must settle whether object release includes arrival time.
   - The reference progress observation depends on visible inputs. Its NI
     proof does not establish R-08-027b's stronger schedule-only statement.
     The concrete encoding of termination, restart, slot widths and repeated
     external events belongs to the trace refinement still owed.
   - T uses Leibniz equality. For this predicate-valued observation encoding,
     the bridge assumes functional extensionality at two arities and
     propositional extensionality as explicit premises. The proof declares
     no global axiom. This is conditional reference evidence, not an
     unconditional proof of T or a proof that other encodings cannot avoid
     these premises. R-05-164's declared global assumption set stays empty.

   The rejected examples establish that the model has content (R-05-165 and
   R-05-166); they do not replace independent R-08-028 specification review.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-01-002 R-05-156 R-05-156a R-05-156b R-05-160 R-05-161 R-05-163 R-05-164
      R-05-165 R-05-166 R-06-001 R-06-016 R-06-017 R-08-021 R-08-024 R-08-025 R-08-026 R-08-027a
      R-08-027b R-08-027c R-08-028 R-08-029 R-08-035 R-08-036 R-08-037 R-08-037b R-08-037c
      R-08-037e R-08-037g R-08-039 R-08-040 R-08-041 R-08-043a R-17-012
   SHA256: 50b78d0b15bed5335349bd7c48999f7420d7a8ac9e72a98cb6c8a12ca4bd48ac
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool Arith List.
Require Import ApexTheorem.

(* -------------------------------------------------------------------------
   1. The compose-time policy (R-08-021, R-08-024).

   Every field is a quantity one composition fixes. Levels, compartments and
   sites are indices below a count, which is the finite-index idiom the
   landed statement artifacts use; the labelling functions are total, per
   reading 3.
   ------------------------------------------------------------------------- *)

Record PolicyModel : Type := {

  (* --- the confidentiality lattice (R-08-024) --------------------------- *)

  levels : nat;                       (* levels are indices below this      *)
  flows : nat -> nat -> bool;         (* the lattice order, a flows into b  *)

  (* --- the domains (R-08-021, R-01-002, R-06-001) ----------------------- *)

  compartments : nat;                 (* compartments are indices below this *)
  clearance : nat -> nat;             (* the level a compartment sits at     *)
  trusted : nat -> bool;              (* the trusted set T's tcb reads       *)

  (* --- the observation sites and their two labels (R-05-156a; readings 2
         and 3) ----------------------------------------------------------- *)

  sites : nat;                        (* the checked region's site count     *)
  content_level : nat -> nat;         (* the label of what a site delivers   *)
  arrival_level : nat -> nat;         (* the label of when it delivers it    *)

  (* --- authority to place content at a site, which is not authority to
         read it (R-05-156b's second proviso; reading 4) ------------------ *)

  drives : nat -> nat -> bool;

  (* --- the compose-time declassification points (R-08-024, R-08-029) ---- *)

  manifest_channel : nat -> nat -> bool;   (* site s is channelled to c      *)

  (* --- the trusted consent path's own sites (R-06-016, R-06-017) -------- *)

  consent_site : nat -> bool
}.

Definition indices (n : nat) : list nat := seq 0 n.

(* What a compartment may read at a site: the lattice licenses it, or a
   compose-time channel does, which is R-08-029's first kind of
   declassification and needs no further mechanism. *)
Definition may_read (m : PolicyModel) (c s : nat) : bool :=
  orb (m.(flows) (m.(content_level) s) (m.(clearance) c))
      (m.(manifest_channel) s c).

(* What a compartment may observe of when a site delivered: the narrow arm
   of the question the header records as undecided. A compose-time channel
   releases the site's content and says nothing about its instant. *)
Definition may_time (m : PolicyModel) (c s : nat) : bool :=
  m.(flows) (m.(arrival_level) s) (m.(clearance) c).

(* The wide arm: a channel releases the instant with the content. Both are
   constructed so that the register's silence is visible and refutable. *)
Definition may_time_wide (m : PolicyModel) (c s : nat) : bool :=
  orb (m.(flows) (m.(arrival_level) s) (m.(clearance) c))
      (m.(manifest_channel) s c).

(* -------------------------------------------------------------------------
   2. Well-formedness, decided by conversion.

   A labelling this predicate refuses is a composition the policy model
   rejects, which is what makes the model exclude something rather than
   admit every graph handed to it.
   ------------------------------------------------------------------------- *)

Definition lattice_reflexive (m : PolicyModel) : bool :=
  forallb (fun a => m.(flows) a a) (indices m.(levels)).

Definition lattice_transitive (m : PolicyModel) : bool :=
  forallb (fun a =>
    forallb (fun b =>
      forallb (fun c =>
        implb (andb (m.(flows) a b) (m.(flows) b c)) (m.(flows) a c))
        (indices m.(levels)))
      (indices m.(levels)))
    (indices m.(levels)).

Definition lattice_antisymmetric (m : PolicyModel) : bool :=
  forallb (fun a =>
    forallb (fun b =>
      implb (andb (m.(flows) a b) (m.(flows) b a)) (Nat.eqb a b))
      (indices m.(levels)))
    (indices m.(levels)).

Definition lattice_bounds (m : PolicyModel) : bool :=
  andb (Nat.ltb 0 m.(levels))
    (forallb (fun a => forallb (fun b =>
      andb
        (existsb (fun j => andb (andb (m.(flows) a j) (m.(flows) b j))
          (forallb (fun u => implb (andb (m.(flows) a u) (m.(flows) b u))
                                  (m.(flows) j u)) (indices m.(levels))))
          (indices m.(levels)))
        (existsb (fun k => andb (andb (m.(flows) k a) (m.(flows) k b))
          (forallb (fun l => implb (andb (m.(flows) l a) (m.(flows) l b))
                                  (m.(flows) l k)) (indices m.(levels))))
          (indices m.(levels))))
      (indices m.(levels))) (indices m.(levels))).

(* Every compartment and every site of the checked region carries a level
   the lattice holds. A label outside the lattice is a label no flow
   question can be asked of. *)
Definition labels_in_range (m : PolicyModel) : bool :=
  andb
    (forallb (fun c => Nat.ltb (m.(clearance) c) m.(levels))
             (indices m.(compartments)))
    (forallb (fun s => andb (Nat.ltb (m.(content_level) s) m.(levels))
                            (Nat.ltb (m.(arrival_level) s) m.(levels)))
             (indices m.(sites))).

(* R-08-035 and R-08-036 as a condition on the labelling: an app never
   renders its own consent UI, so no untrusted compartment drives a site the
   powerbox reads a consent act from. *)
Definition consent_path_is_trusted (m : PolicyModel) : bool :=
  forallb (fun s =>
    implb (m.(consent_site) s)
          (forallb (fun c => implb (m.(drives) c s) (m.(trusted) c))
                   (indices m.(compartments))))
    (indices m.(sites)).

Definition wellformed (m : PolicyModel) : bool :=
  andb (andb (lattice_reflexive m)
             (andb (lattice_transitive m) (lattice_antisymmetric m)))
       (andb (lattice_bounds m)
         (andb (labels_in_range m) (consent_path_is_trusted m))).

(*| discharges: R-08-024 |*)
Theorem wellformed_requires_each_lattice_law :
  forall m : PolicyModel, wellformed m = true ->
    lattice_reflexive m = true /\ lattice_transitive m = true /\
    lattice_antisymmetric m = true /\ lattice_bounds m = true.
Proof.
  intros m H. unfold wellformed in H.
  repeat rewrite andb_true_iff in H. tauto.
Qed.

(* -------------------------------------------------------------------------
   3. The whole-system input and the composed execution (R-05-156a).
   ------------------------------------------------------------------------- *)

Inductive Scope : Type := OneShot | WhileActive | Persistent | EmergencyCall.

Record Grant : Type := {
  grantee : nat;                      (* the compartment minted for          *)
  named_object : nat;                 (* the site consent named              *)
  witness_site : nat;                 (* where the consent act was taken     *)
  issued : nat;                       (* the instant of that act             *)
  grant_scope : Scope;
  ceiling : nat                       (* the scope's expiry (R-08-040)       *)
}.

Record GrantState : Type := {
  unconsumed : bool;
  unrevoked : bool;
  record_fresh : bool;
  profile_unlocked : bool;
  record_compatible : bool;
  requested : bool;
  call_active : bool
}.

Definition ready_state : GrantState :=
  {| unconsumed := true; unrevoked := true; record_fresh := true;
     profile_unlocked := true; record_compatible := true;
     requested := true; call_active := true |}.
Definition witness_GrantState : GrantState := ready_state.

Definition scope_eqb (a b : Scope) : bool :=
  match a,b with
  | OneShot,OneShot | WhileActive,WhileActive | Persistent,Persistent
  | EmergencyCall,EmergencyCall => true
  | _,_ => false
  end.

Definition grant_eqb (a b : Grant) : bool :=
  Nat.eqb a.(grantee) b.(grantee) && Nat.eqb a.(named_object) b.(named_object)
  && Nat.eqb a.(witness_site) b.(witness_site) && Nat.eqb a.(issued) b.(issued)
  && Nat.eqb a.(ceiling) b.(ceiling) && scope_eqb a.(grant_scope) b.(grant_scope).

Definition state_eqb (a b : GrantState) : bool :=
  Bool.eqb a.(unconsumed) b.(unconsumed) && Bool.eqb a.(unrevoked) b.(unrevoked)
  && Bool.eqb a.(record_fresh) b.(record_fresh)
  && Bool.eqb a.(profile_unlocked) b.(profile_unlocked)
  && Bool.eqb a.(record_compatible) b.(record_compatible)
  && Bool.eqb a.(requested) b.(requested) && Bool.eqb a.(call_active) b.(call_active).

Lemma grant_eqb_refl : forall g, grant_eqb g g = true.
Proof. intros [c s w i k e]. destruct k; unfold grant_eqb; cbn;
  repeat rewrite Nat.eqb_refl; reflexivity. Qed.
Lemma state_eqb_refl : forall st, state_eqb st st = true.
Proof. intros [a b c d e f g]. destruct a,b,c,d,e,f,g; reflexivity. Qed.

Record SystemInput : Type := {
  delivers : nat -> nat;              (* the content a site carries          *)
  arrives : nat -> nat;               (* its cycle-level arrival instant     *)
  consent : nat -> option Grant;      (* authenticated act or fresh record   *)
  lifecycle : nat -> GrantState       (* trusted scope facts at witness site *)
}.

Record SystemTrace : Type := {
  received : nat -> nat -> nat;       (* what a compartment read at a site   *)
  observed_at : nat -> nat -> nat;    (* when it read it                     *)
  slot : nat -> nat;                  (* its composition-fixed slot instant  *)
  reached : nat -> nat;               (* how far it got (R-08-027a)          *)
  raised : nat -> nat;                (* the fault class it raised (R-08-027c) *)
  restarts : nat -> nat;              (* restart count at the observation cut *)
  width : nat -> nat;                 (* the slot width visible to this domain *)
  finished : nat -> bool             (* termination at the observation cut *)
}.

Definition Execution : Type := SystemInput -> SystemTrace.

(* The timing channel as a view of a trace. Reading 5: the slot instant is the
   channel's first index, progress its second, width its third, termination
   its fourth, and read instants thereafter. The architectural channel is the
   pair of fault class and restart count. No channel is erased by release. *)
Definition timing_view (t : SystemTrace) (c k : nat) : nat :=
  match k with
  | O => t.(slot) c
  | S O => t.(reached) c
  | S (S O) => t.(width) c
  | S (S (S O)) => if t.(finished) c then 1 else O
  | S (S (S (S s))) => t.(observed_at) c s
  end.

(* -------------------------------------------------------------------------
   4. The observation relation and indistinguishability (R-05-156, R-05-156a,
   R-05-156b).

   An adversary set observes a site when one of its members may. The
   relation equates the content of every site the set may read and the
   arrival instant of every site the set may time, and equates nothing else:
   that second conjunct is R-05-156a's device-observation clause, stated
   rather than defaulted.
   ------------------------------------------------------------------------- *)

Definition set_reads (m : PolicyModel) (C : nat -> Prop) (s : nat) : Prop :=
  exists c, C c /\ may_read m c s = true.

Definition set_times (m : PolicyModel) (C : nat -> Prop) (s : nat) : Prop :=
  exists c, C c /\ may_time m c s = true.

Definition set_times_wide (m : PolicyModel) (C : nat -> Prop) (s : nat) : Prop :=
  exists c, C c /\ may_time_wide m c s = true.

Definition indistinguishable (m : PolicyModel) (C : nat -> Prop)
    (i1 i2 : SystemInput) : Prop :=
  (forall s, set_reads m C s -> i1.(delivers) s = i2.(delivers) s)
  /\ (forall s, set_times m C s -> i1.(arrives) s = i2.(arrives) s).

(* The wide arm of the undecided question, as a second relation rather than
   as a variant of the first. *)
Definition indistinguishable_wide (m : PolicyModel) (C : nat -> Prop)
    (i1 i2 : SystemInput) : Prop :=
  (forall s, set_reads m C s -> i1.(delivers) s = i2.(delivers) s)
  /\ (forall s, set_times_wide m C s -> i1.(arrives) s = i2.(arrives) s).

(* The reading R-05-156b's second proviso rejects, constructed so that the
   rejection is a theorem rather than a sentence: two inputs are related when
   they agree at every site the set drives. *)
Definition control_indistinguishable (m : PolicyModel) (C : nat -> Prop)
    (i1 i2 : SystemInput) : Prop :=
  forall s, (exists c, C c /\ m.(drives) c s = true) ->
    i1.(delivers) s = i2.(delivers) s /\ i1.(arrives) s = i2.(arrives) s.

(* R-05-156a's cost, named: a site whose arrival instant every compartment
   may observe is equated across every pair the relation relates, so it is
   quantified out of T rather than covered by it. The predicate is stated so
   that a composition can be read for which of its device timings are inside
   T and which are outside it. *)
Definition arrival_quantified_out (m : PolicyModel) (s : nat) : bool :=
  forallb (fun c => may_time m c s) (indices m.(compartments)).

Definition arrival_inside_T (m : PolicyModel) (s : nat) : bool :=
  negb (arrival_quantified_out m s).

(* -------------------------------------------------------------------------
   5. Declassification (R-08-025, R-08-026, R-08-029, R-08-036, R-08-037).
   ------------------------------------------------------------------------- *)

(* Reading 6: the grant set and the instant the quotient is taken at are one
   value, so the temporal scope is inside T's modulo-D clause. *)
Record Release : Type := {
  grants : list Grant;
  states : nat -> GrantState;
  at_instant : nat
}.

(* R-08-037, R-08-037b, R-08-037c, R-08-037e, R-08-037g,
   R-08-039, R-08-040, R-08-041 and R-08-043a: all scope facts are
   trusted observations. Refinement must bind them to the actual lifecycle.
   A revoked grant cannot be restored by a later favourable focus signal. *)
Definition live (g : Grant) (rel : Release) : bool :=
  let st := rel.(states) g.(witness_site) in
  andb (Nat.leb g.(issued) rel.(at_instant))
    (andb st.(unrevoked) (andb st.(requested)
      (match g.(grant_scope) with
       | OneShot => andb st.(unconsumed) (Nat.leb rel.(at_instant) g.(ceiling))
       | WhileActive => Nat.leb rel.(at_instant) g.(ceiling)
       | Persistent => st.(record_fresh) && st.(profile_unlocked)
                       && st.(record_compatible)
       | EmergencyCall => st.(call_active)
       end))).

(* The release rule this model ships: a pair is released when some live grant
   names exactly that grantee and exactly that object. *)
Definition licensed (rel : Release) (c s : nat) : bool :=
  existsb (fun g => andb (andb (Nat.eqb g.(grantee) c)
                               (Nat.eqb g.(named_object) s))
                         (live g rel))
          rel.(grants).

Definition ReleaseRule : Type := Release -> nat -> nat -> bool.

(* Delimited release changes which INPUT pairs must agree: the recipient may
   learn the named object's content, but no other secret can be hidden in that
   output position. Output observations themselves are never erased. *)
Definition release_indistinguishable (m : PolicyModel) (rel : Release)
    (C : nat -> Prop) (i1 i2 : SystemInput) : Prop :=
  indistinguishable m C i1 i2 /\
  (forall c s, C c -> licensed rel c s = true ->
     i1.(delivers) s = i2.(delivers) s).

Definition released_flow_target (m : PolicyModel) (rel : Release)
    (x : Execution) : Prop :=
  forall C i1 i2 c s, C c -> release_indistinguishable m rel C i1 i2 ->
    (x i1).(received) c s = (x i2).(received) c s.

(* R-08-026 and R-17-012: the granted channel carries the object consent
   named and is no general high-to-low conduit. *)
Definition delimited (r : ReleaseRule) : Prop :=
  forall rel c s, r rel c s = true ->
    exists g, In g rel.(grants) /\ g.(grantee) = c /\ g.(named_object) = s.

(* R-08-037 and R-08-040: and it carries it only inside the scope of the act
   that created it, so an inter-level edge outliving its act is refused by
   the quotient rather than excused by it. *)
Definition scoped (r : ReleaseRule) : Prop :=
  forall rel c s, r rel c s = true ->
    exists g, In g rel.(grants) /\ g.(grantee) = c /\ g.(named_object) = s
              /\ live g rel = true.

(* R-06-017: the exact authenticated act, not merely a trusted site name,
   witnesses the grant. Scope state is the same snapshot the input carries. *)
Definition witnessed (m : PolicyModel) (i : SystemInput) (rel : Release) : bool :=
  forallb (fun g =>
    m.(consent_site) g.(witness_site) &&
    (match i.(consent) g.(witness_site) with
     | Some act => grant_eqb g act
     | None => false
     end) && state_eqb (rel.(states) g.(witness_site))
                       (i.(lifecycle) g.(witness_site))) rel.(grants).

(* -------------------------------------------------------------------------
   6. Robust declassification (R-08-025, R-06-016).

   The powerbox is the sole runtime declassifier, so the whole declassification
   set is one function of the whole-system input and the instant. The reference relation compares input pairs agreeing on trusted consent.
   Correspondence with interactive compromised strategies, including
   revoke-only actions, remains an implementation obligation.
   ------------------------------------------------------------------------- *)

Definition Powerbox : Type := SystemInput -> nat -> Release.

Definition consent_agrees (m : PolicyModel) (i1 i2 : SystemInput) : Prop :=
  forall s, m.(consent_site) s = true ->
    i1.(delivers) s = i2.(delivers) s /\ i1.(arrives) s = i2.(arrives) s
    /\ i1.(consent) s = i2.(consent) s
    /\ i1.(lifecycle) s = i2.(lifecycle) s.

Definition robust (m : PolicyModel) (p : Powerbox) : Prop :=
  forall i1 i2 now, consent_agrees m i1 i2 -> p i1 now = p i2 now.

(* R-08-025's three quantities, separately named so that a refutation can say
   which of them an attacker moved. *)
Definition whether (rel : Release) (c : nat) : bool :=
  existsb (fun g => Nat.eqb g.(grantee) c) rel.(grants).

Definition what (rel : Release) : list nat := map named_object rel.(grants).

Definition to_whom (rel : Release) : list nat := map grantee rel.(grants).

(* -------------------------------------------------------------------------
   7. The two theorem targets (R-05-160's first and seventh seams).

   These are the Props ApexTheorem.v's explicit_flow_noninterference and
   declassified_flows_authorized fields are instantiated by below. They are
   targets: this file proves them of the reference execution constructed to
   argue with, and of no composed image.
   ------------------------------------------------------------------------- *)

(* These are the base, no-runtime-release targets. The D-indexed value
   target used by the apex instance is released_flow_target.
   The compartment count bounds the adversary sets the quantifier ranges over,
   through graph_permits below, and it does that job once: the labelling is
   total over compartment indices exactly as reading 3 makes it total over
   site indices, so these three targets carry no second bound and say
   something at every index. *)
Definition flow_noninterference (m : PolicyModel) (x : Execution) : Prop :=
  forall (C : nat -> Prop) (i1 i2 : SystemInput) (c s : nat),
    C c -> indistinguishable m C i1 i2 ->
    (x i1).(received) c s = (x i2).(received) c s
    /\ (x i1).(observed_at) c s = (x i2).(observed_at) c s.

(* R-08-027a and R-08-027b: progress is an observation, and the slot instant
   it is read against is a composition constant. *)
Definition progress_noninterference (m : PolicyModel) (x : Execution) : Prop :=
  forall (C : nat -> Prop) (i1 i2 : SystemInput) (c : nat),
    C c -> indistinguishable m C i1 i2 ->
    (x i1).(slot) c = (x i2).(slot) c /\ (x i1).(reached) c = (x i2).(reached) c
    /\ (x i1).(width) c = (x i2).(width) c
    /\ (x i1).(finished) c = (x i2).(finished) c.

(* R-08-027c: the fault class is an observation, so the fault path carries a
   confidentiality obligation and not only an availability one. *)
Definition fault_noninterference (m : PolicyModel) (x : Execution) : Prop :=
  forall (C : nat -> Prop) (i1 i2 : SystemInput) (c : nat),
    C c -> indistinguishable m C i1 i2 ->
    (x i1).(raised) c = (x i2).(raised) c
    /\ (x i1).(restarts) c = (x i2).(restarts) c.

Definition explicit_flow_target (m : PolicyModel) (x : Execution) : Prop :=
  flow_noninterference m x
  /\ progress_noninterference m x
  /\ fault_noninterference m x.

(* The seventh seam requires authenticated, scoped consent for the release
   relation. Content confinement is the separate D-indexed first-seam target. *)
Definition authorized_release_target (m : PolicyModel) (p : Powerbox)
    (r : ReleaseRule) : Prop :=
  (forall i now, witnessed m i (p i now) = true /\ (p i now).(at_instant) = now)
  /\ delimited r
  /\ scoped r
  /\ robust m p.

(* -------------------------------------------------------------------------
   8. The reference composition.

   Three compartments and four sites, the smallest shape that carries every
   question this file answers: a low compartment and a high one, both
   untrusted, and the trusted consent path; a public site, a secret site, the
   consent site, and a port the low compartment drives and cannot read.
   ------------------------------------------------------------------------- *)

Definition ref_clearance (c : nat) : nat :=
  match c with O => O | _ => 1 end.

Definition ref_trusted (c : nat) : bool :=
  match c with S (S O) => true | _ => false end.

Definition ref_content_level (s : nat) : nat :=
  match s with O => O | _ => 1 end.

Definition ref_arrival_level (s : nat) : nat :=
  match s with O => O | _ => 1 end.

Definition ref_consent_site (s : nat) : bool :=
  match s with S (S O) => true | _ => false end.

Definition ref_drives (c s : nat) : bool :=
  match c, s with
  | S (S O), S (S O) => true                 (* the agent drives the prompt  *)
  | O, S (S (S O)) => true                   (* the app drives its own port  *)
  | _, _ => false
  end.

Definition reference : PolicyModel := {|
  levels := 2;
  flows := Nat.leb;
  compartments := 3;
  clearance := ref_clearance;
  trusted := ref_trusted;
  sites := 4;
  content_level := ref_content_level;
  arrival_level := ref_arrival_level;
  drives := ref_drives;
  manifest_channel := fun _ _ => false;
  consent_site := ref_consent_site
|}.

(* R-05-166's decidable half for every record this file's theorems quantify
   over: a closed top-level definition ascribed at the record. *)
Definition witness_PolicyModel : PolicyModel := reference.

Example reference_is_wellformed : wellformed reference = true := eq_refl.

(* The composition with one compose-time channel, R-08-029's first kind: the
   secret site's content is wired to the low compartment at build time. *)
Definition channelled : PolicyModel := {|
  levels := 2;
  flows := Nat.leb;
  compartments := 3;
  clearance := ref_clearance;
  trusted := ref_trusted;
  sites := 4;
  content_level := ref_content_level;
  arrival_level := ref_arrival_level;
  drives := ref_drives;
  manifest_channel := fun s c => andb (Nat.eqb s 1) (Nat.eqb c 0);
  consent_site := ref_consent_site
|}.

Example channelled_is_wellformed : wellformed channelled = true := eq_refl.

(* --- the labellings the model rejects --------------------------------- *)

(* A compartment labelled at a level the lattice does not carry. *)
Definition unlabelled_compartment : PolicyModel := {|
  levels := 2;
  flows := Nat.leb;
  compartments := 3;
  clearance := fun c => match c with O => O | _ => 2 end;
  trusted := ref_trusted;
  sites := 4;
  content_level := ref_content_level;
  arrival_level := ref_arrival_level;
  drives := ref_drives;
  manifest_channel := fun _ _ => false;
  consent_site := ref_consent_site
|}.

(* A lattice that is not transitive: the middle level passes a flow the ends
   do not, so "may not influence unless a channel exists" would not be a
   transitive relation and two hops would beat one. *)
Definition intransitive_lattice : PolicyModel := {|
  levels := 3;
  flows := fun a b =>
    match a, b with
    | O, O | S O, S O | S (S O), S (S O) => true
    | O, S O | S O, S (S O) => true
    | _, _ => false
    end;
  compartments := 3;
  clearance := ref_clearance;
  trusted := ref_trusted;
  sites := 4;
  content_level := ref_content_level;
  arrival_level := ref_arrival_level;
  drives := ref_drives;
  manifest_channel := fun _ _ => false;
  consent_site := ref_consent_site
|}.

(* An app that draws its own consent prompt (R-08-035). *)
Definition app_drives_the_prompt : PolicyModel := {|
  levels := 2;
  flows := Nat.leb;
  compartments := 3;
  clearance := ref_clearance;
  trusted := ref_trusted;
  sites := 4;
  content_level := ref_content_level;
  arrival_level := ref_arrival_level;
  drives := fun c s => match c, s with O, S (S O) => true | _, _ => false end;
  manifest_channel := fun _ _ => false;
  consent_site := ref_consent_site
|}.

(*| discharges: R-05-165, R-05-166 |*)
Theorem the_model_rejects_a_labelling :
  wellformed unlabelled_compartment = false
  /\ wellformed intransitive_lattice = false
  /\ wellformed app_drives_the_prompt = false.
Proof. repeat split. Qed.

(* -------------------------------------------------------------------------
   9. The two executions.

   Neither is the composed image. The first confines: a compartment reads a
   site only where the policy licenses it, gets as far as its own licensed
   inputs take it, and raises no fault of anything. The second copies the
   secret site into every licensed read, which is the implementation the
   specification has to exclude.
   ------------------------------------------------------------------------- *)

Fixpoint visible_progress_upto (m : PolicyModel) (i : SystemInput)
    (c n : nat) : nat :=
  match n with
  | O => O
  | S k => visible_progress_upto m i c k
           + (if may_read m c k then i.(delivers) k else O)
  end.

Definition visible_progress (m : PolicyModel) (i : SystemInput) (c : nat) : nat :=
  visible_progress_upto m i c m.(sites).

Definition confining (m : PolicyModel) : Execution :=
  fun i => {|
    received := fun c s => if may_read m c s then i.(delivers) s else O;
    observed_at := fun c s => if may_time m c s then i.(arrives) s else O;
    slot := fun c => c;
    reached := visible_progress m i;
    raised := fun _ => O; restarts := fun _ => O;
    width := fun _ => m.(sites); finished := fun _ => true
  |}.

Definition leaks_content (m : PolicyModel) : Execution :=
  fun i => {|
    received := fun c s => if may_read m c s then i.(delivers) 1 else O;
    observed_at := fun c s => if may_time m c s then i.(arrives) s else O;
    slot := fun c => c;
    reached := visible_progress m i;
    raised := fun _ => O; restarts := fun _ => O;
    width := fun _ => m.(sites); finished := fun _ => true
  |}.

Definition leaks_arrival (m : PolicyModel) : Execution :=
  fun i => {|
    received := fun c s => if may_read m c s then i.(delivers) s else O;
    observed_at := fun c s => if may_time m c s then i.(arrives) 1 else O;
    slot := fun c => c;
    reached := visible_progress m i;
    raised := fun _ => O; restarts := fun _ => O;
    width := fun _ => m.(sites); finished := fun _ => true
  |}.

Definition leaks_progress (m : PolicyModel) : Execution :=
  fun i => {|
    received := fun c s => if may_read m c s then i.(delivers) s else O;
    observed_at := fun c s => if may_time m c s then i.(arrives) s else O;
    slot := fun c => c;
    reached := fun _ => i.(delivers) 1;
    raised := fun _ => O; restarts := fun _ => O;
    width := fun _ => m.(sites); finished := fun _ => true
  |}.

Definition leaks_fault (m : PolicyModel) : Execution :=
  fun i => {|
    received := fun c s => if may_read m c s then i.(delivers) s else O;
    observed_at := fun c s => if may_time m c s then i.(arrives) s else O;
    slot := fun c => c;
    reached := visible_progress m i;
    raised := fun _ => i.(delivers) 1; restarts := fun _ => O;
    width := fun _ => m.(sites); finished := fun _ => true
  |}.

(* -------------------------------------------------------------------------
   10. The confining execution satisfies the target.
   ------------------------------------------------------------------------- *)

Lemma progress_upto_agrees :
  forall (m : PolicyModel) (i1 i2 : SystemInput) (c n : nat),
    (forall s, may_read m c s = true -> i1.(delivers) s = i2.(delivers) s) ->
    visible_progress_upto m i1 c n = visible_progress_upto m i2 c n.
Proof.
  intros m i1 i2 c n H.
  induction n as [|k IH]; cbn.
  - reflexivity.
  - rewrite IH. destruct (may_read m c k) eqn:E.
    + rewrite (H k E). reflexivity.
    + reflexivity.
Qed.

(*| discharges: R-08-021, R-08-027a, R-08-027b, R-08-027c |*)
Theorem the_confining_execution_is_noninterferent :
  forall m : PolicyModel, explicit_flow_target m (confining m).
Proof.
  intros m. split; [| split].
  - intros C i1 i2 c s Hc [Hread Htime]. split; cbn.
    + destruct (may_read m c s) eqn:E; [|reflexivity].
      apply Hread. exists c. split; assumption.
    + destruct (may_time m c s) eqn:E; [|reflexivity].
      apply Htime. exists c. split; assumption.
  - intros C i1 i2 c Hc [Hread Htime]. split; cbn.
    + reflexivity.
    + split.
      * unfold visible_progress. apply progress_upto_agrees.
        intros s E. apply Hread. exists c. split; assumption.
      * split; reflexivity.
  - intros C i1 i2 c Hc Hind. split; reflexivity.
Qed.

(* -------------------------------------------------------------------------
   11. The reference inputs, and what the low compartment cannot tell apart.
   ------------------------------------------------------------------------- *)

Definition quiet : SystemInput :=
  {| delivers := fun _ => O; arrives := fun _ => O ; consent := fun _ => None; lifecycle := fun _ => ready_state |}.

Definition secret_content : SystemInput :=
  {| delivers := fun s => if Nat.eqb s 1 then 1 else O; arrives := fun _ => O ; consent := fun _ => None; lifecycle := fun _ => ready_state |}.

Definition secret_arrival : SystemInput :=
  {| delivers := fun _ => O; arrives := fun s => if Nat.eqb s 1 then 1 else O ; consent := fun _ => None; lifecycle := fun _ => ready_state |}.

Definition port_content : SystemInput :=
  {| delivers := fun s => if Nat.eqb s 3 then 1 else O; arrives := fun _ => O ; consent := fun _ => None; lifecycle := fun _ => ready_state |}.

Definition public_content : SystemInput :=
  {| delivers := fun s => if Nat.eqb s O then 1 else O; arrives := fun _ => O ; consent := fun _ => None; lifecycle := fun _ => ready_state |}.

Definition witness_SystemInput : SystemInput := quiet.
Definition witness_SystemTrace : SystemTrace := confining reference quiet.

(* The victim-shaped set R-05-156b's first proviso asks the quantifier's
   domain to admit: the low compartment alone. *)
Definition victim (c : nat) : Prop := c = O.

Lemma victim_indistinguishable :
  forall i1 i2 : SystemInput,
    (forall s, may_read reference O s = true -> i1.(delivers) s = i2.(delivers) s) ->
    (forall s, may_time reference O s = true -> i1.(arrives) s = i2.(arrives) s) ->
    indistinguishable reference victim i1 i2.
Proof.
  intros i1 i2 Hr Ht. split; intros s [c [Hc Hmay]]; unfold victim in Hc; subst c.
  - exact (Hr s Hmay).
  - exact (Ht s Hmay).
Qed.

Lemma victim_reads_only_the_public_site :
  forall s, may_read reference O s = true -> s = O.
Proof. intros s H. destruct s as [|s']; [reflexivity | discriminate H]. Qed.

Lemma victim_times_only_the_public_site :
  forall s, may_time reference O s = true -> s = O.
Proof. intros s H. destruct s as [|s']; [reflexivity | discriminate H]. Qed.

Lemma quiet_and_secret_content_are_indistinguishable :
  indistinguishable reference victim quiet secret_content.
Proof.
  apply victim_indistinguishable.
  - intros s H. rewrite (victim_reads_only_the_public_site s H). reflexivity.
  - intros s H. rewrite (victim_times_only_the_public_site s H). reflexivity.
Qed.

Lemma quiet_and_secret_arrival_are_indistinguishable :
  indistinguishable reference victim quiet secret_arrival.
Proof.
  apply victim_indistinguishable.
  - intros s H. rewrite (victim_reads_only_the_public_site s H). reflexivity.
  - intros s H. rewrite (victim_times_only_the_public_site s H). reflexivity.
Qed.

Lemma quiet_and_port_content_are_indistinguishable :
  indistinguishable reference victim quiet port_content.
Proof.
  apply victim_indistinguishable.
  - intros s H. rewrite (victim_reads_only_the_public_site s H). reflexivity.
  - intros s H. rewrite (victim_times_only_the_public_site s H). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   12. R-05-156b's two provisos, discharged.
   ------------------------------------------------------------------------- *)

(* The first proviso: the quantifier's domain admits victim-shaped sets. The
   set is inside graph_permits, outside the TCB, and the relation holds of a
   pair varying only in what the attacker's site carries, which is the
   influence reading. *)
(*| discharges: R-05-156b |*)
Theorem the_domain_admits_victim_shaped_sets :
  (forall c, victim c -> Nat.ltb c reference.(compartments) = true)
  /\ (forall c, victim c -> reference.(trusted) c = false)
  /\ indistinguishable reference victim quiet secret_content
  /\ (forall c s, victim c -> may_read reference c s = true ->
        (confining reference quiet).(received) c s
        = (confining reference secret_content).(received) c s).
Proof.
  split; [| split; [| split]].
  - intros c Hc. unfold victim in Hc. subst c. reflexivity.
  - intros c Hc. unfold victim in Hc. subst c. reflexivity.
  - exact quiet_and_secret_content_are_indistinguishable.
  - intros c s Hc Hmay. unfold victim in Hc. subst c.
    destruct (the_confining_execution_is_noninterferent reference) as [Hflow _].
    destruct (Hflow victim quiet secret_content O s eq_refl
                quiet_and_secret_content_are_indistinguishable) as [Hv _].
    exact Hv.
Qed.

(* The second proviso: the relation is stated over what the set may observe
   and not over what it controls, and the two readings are incomparable, so
   taking one is a decision rather than a notation. The low compartment
   drives site 3 and cannot read it; it reads site 0 and drives nothing
   there. *)
(*| discharges: R-05-156b, R-05-166 |*)
Theorem observation_and_control_are_incomparable :
  (indistinguishable reference victim quiet port_content
   /\ ~ control_indistinguishable reference victim quiet port_content)
  /\ (control_indistinguishable reference victim quiet public_content
      /\ ~ indistinguishable reference victim quiet public_content).
Proof.
  split; split.
  - exact quiet_and_port_content_are_indistinguishable.
  - intros H. destruct (H 3 (ex_intro _ O (conj eq_refl eq_refl))) as [Hd _].
    discriminate Hd.
  - intros s [c [Hc Hd]]. unfold victim in Hc. subst c.
    destruct s as [|[|[|[|s']]]]; cbn in Hd; try discriminate Hd.
    split; reflexivity.
  - intros [Hread _].
    assert (Hbad := Hread O (ex_intro _ O (conj eq_refl eq_refl))).
    discriminate Hbad.
Qed.

(* -------------------------------------------------------------------------
   13. R-05-156a's device-observation clause, decided.
   ------------------------------------------------------------------------- *)

(* A site whose arrival every compartment may observe is equated across every
   pair the relation relates, so its timing is outside T. *)
(*| discharges: R-05-156a |*)
Theorem a_quantified_out_arrival_is_equated :
  forall (m : PolicyModel) (C : nat -> Prop) (c s : nat) (i1 i2 : SystemInput),
    C c -> Nat.ltb c m.(compartments) = true ->
    arrival_quantified_out m s = true ->
    indistinguishable m C i1 i2 ->
    i1.(arrives) s = i2.(arrives) s.
Proof.
  intros m C c s i1 i2 Hc Hbound Hall [_ Htime].
  apply Htime. exists c. split; [exact Hc |].
  unfold arrival_quantified_out in Hall.
  rewrite forallb_forall in Hall.
  apply Hall. unfold indices. apply in_seq. split.
  - apply Nat.le_0_l.
  - cbn. apply Nat.ltb_lt. exact Hbound.
Qed.

(* And the reference composition is read for which of its device timings sit
   inside T and which outside: the public site's arrival is quantified out,
   the secret site's is not, so the clause decides something. *)
(*| discharges: R-05-156a |*)
Theorem the_device_clause_decides_something :
  arrival_quantified_out reference O = true
  /\ arrival_inside_T reference 1 = true.
Proof. split; reflexivity. Qed.

(* R-05-156a speaks of an adversary set's indistinguishability classes, and a
   class is what an equivalence has. The relation is one. *)
(*| discharges: R-05-156a |*)
Theorem indistinguishability_has_classes :
  forall (m : PolicyModel) (C : nat -> Prop),
    (forall i, indistinguishable m C i i)
    /\ (forall i1 i2, indistinguishable m C i1 i2 -> indistinguishable m C i2 i1)
    /\ (forall i1 i2 i3, indistinguishable m C i1 i2 ->
          indistinguishable m C i2 i3 -> indistinguishable m C i1 i3).
Proof.
  intros m C. split; [| split].
  - intros i. split; intros s _; reflexivity.
  - intros i1 i2 [Hr Ht]. split; intros s Hs.
    + symmetry. exact (Hr s Hs).
    + symmetry. exact (Ht s Hs).
  - intros i1 i2 i3 [Hr1 Ht1] [Hr2 Ht2]. split; intros s Hs.
    + rewrite (Hr1 s Hs). exact (Hr2 s Hs).
    + rewrite (Ht1 s Hs). exact (Ht2 s Hs).
Qed.

(* R-08-029's compose-time kind is inside the base relation and not an
   exception beside it: a manifest channel widens what the adversary set may
   read, so the pair the reference composition relates is one the channelled
   composition separates. No further primitive is needed for it. *)
(*| discharges: R-08-024, R-08-029 |*)
Theorem a_compose_time_channel_is_inside_the_policy :
  may_read reference O 1 = false
  /\ may_read channelled O 1 = true
  /\ ~ indistinguishable channelled victim quiet secret_content.
Proof.
  split; [reflexivity | split; [reflexivity |]].
  intros [Hread _].
  assert (Hbad := Hread 1 (ex_intro _ O (conj eq_refl eq_refl))).
  discriminate Hbad.
Qed.

(* -------------------------------------------------------------------------
   14. The delimited-release bound and the temporal scope.
   ------------------------------------------------------------------------- *)

Definition no_grants : Release := {| grants := nil; states := fun _ => ready_state; at_instant := O |}.

(* One grant: the low compartment may read the secret site, witnessed at the
   consent site, from instant 5 to instant 9. *)
Definition consented_grant : Grant :=
  {| grantee := O; named_object := 1; witness_site := 2;
     issued := 5; grant_scope := WhileActive; ceiling := 9 |}.

Definition inside_scope : Release :=
  {| grants := consented_grant :: nil; states := fun _ => ready_state; at_instant := 7 |}.

Definition outside_scope : Release :=
  {| grants := consented_grant :: nil; states := fun _ => ready_state; at_instant := 11 |}.

Definition witness_Grant : Grant := consented_grant.
Definition witness_Release : Release := inside_scope.

(*| discharges: R-08-026, R-17-012 |*)
Theorem the_shipped_rule_is_delimited : delimited licensed.
Proof.
  intros rel c s H. unfold licensed in H.
  rewrite existsb_exists in H. destruct H as [g [Hin Hg]].
  exists g. split; [exact Hin |].
  apply andb_prop in Hg. destruct Hg as [Hnames _].
  apply andb_prop in Hnames. destruct Hnames as [Hc Hs].
  split; [exact (proj1 (Nat.eqb_eq _ _) Hc) | exact (proj1 (Nat.eqb_eq _ _) Hs)].
Qed.

(*| discharges: R-08-037 |*)
Theorem the_shipped_rule_is_scoped : scoped licensed.
Proof.
  intros rel c s H. unfold licensed in H.
  rewrite existsb_exists in H. destruct H as [g [Hin Hg]].
  exists g. split; [exact Hin |].
  apply andb_prop in Hg. destruct Hg as [Hnames Hlive].
  apply andb_prop in Hnames. destruct Hnames as [Hc Hs].
  split; [exact (proj1 (Nat.eqb_eq _ _) Hc) |].
  split; [exact (proj1 (Nat.eqb_eq _ _) Hs) | exact Hlive].
Qed.

(* The grant's own window decides, and the quotient reads it: inside the
   scope the named object is released, outside it nothing is. *)
(*| discharges: R-08-037 |*)
Theorem the_scope_decides_the_quotient :
  licensed inside_scope O 1 = true /\ licensed outside_scope O 1 = false.
Proof. split; reflexivity. Qed.

(* --- the two constructions the bound rejects --------------------------- *)

(* R-17-012's leak: a release bound that lets the powerbox mint wider than
   the user named, here every site sharing the named object's level. It
   verifies against the grant and releases a site no act named. *)
(*| discharges: R-05-166, R-08-040 |*)
Theorem both_lease_boundaries_are_live :
  live consented_grant
    {| grants := consented_grant :: nil; states := fun _ => ready_state;
       at_instant := 5 |} = true /\
  live consented_grant
    {| grants := consented_grant :: nil; states := fun _ => ready_state;
       at_instant := 9 |} = true.
Proof. split; reflexivity. Qed.

Definition release_by_level (m : PolicyModel) : ReleaseRule :=
  fun rel c s =>
    existsb (fun g => andb (Nat.eqb g.(grantee) c)
                           (andb (Nat.eqb (m.(content_level) g.(named_object))
                                          (m.(content_level) s))
                                 (live g rel)))
            rel.(grants).

(* An edge that outlives the act that created it: the same rule with the
   window dropped. *)
Definition release_without_scope : ReleaseRule :=
  fun rel c s =>
    existsb (fun g => andb (Nat.eqb g.(grantee) c) (Nat.eqb g.(named_object) s))
            rel.(grants).

(*| discharges: R-05-166, R-08-026, R-17-012 |*)
Theorem a_release_wider_than_the_named_object_is_refused :
  release_by_level reference inside_scope O 3 = true
  /\ ~ delimited (release_by_level reference).
Proof.
  split; [reflexivity |].
  intros H. destruct (H inside_scope O 3 eq_refl) as [g [Hin [_ Hs]]].
  destruct Hin as [Heq | Hfalse]; [| destruct Hfalse].
  subst g. discriminate Hs.
Qed.

(*| discharges: R-05-166, R-08-037 |*)
Theorem an_edge_outliving_its_act_is_refused :
  release_without_scope outside_scope O 1 = true
  /\ ~ scoped release_without_scope.
Proof.
  split; [reflexivity |].
  intros H. destruct (H outside_scope O 1 eq_refl) as [g [Hin [_ [_ Hlive]]]].
  destruct Hin as [Heq | Hfalse]; [| destruct Hfalse].
  subst g. discriminate Hlive.
Qed.

(* R-06-017's first clause, and the mint the model refuses: a grant whose
   witness site is not on the consent path. *)
Definition unwitnessed : Release :=
  {| grants := {| grantee := O; named_object := 1; witness_site := 1;
                  issued := 5; grant_scope := WhileActive; ceiling := 9 |} :: nil;
     states := fun _ => ready_state; at_instant := 7 |}.

(* The trusted state abstraction records scope decisions, not their
   implementation. Persistent freshness is R-08-025's explicit premise. *)
Definition used_state : GrantState :=
  {| unconsumed := false; unrevoked := true; record_fresh := true;
     profile_unlocked := true; record_compatible := true;
     requested := true; call_active := true |}.
Definition stale_state : GrantState :=
  {| unconsumed := true; unrevoked := true; record_fresh := false;
     profile_unlocked := true; record_compatible := true;
     requested := true; call_active := true |}.
Definition revoked_state : GrantState :=
  {| unconsumed := true; unrevoked := false; record_fresh := true;
     profile_unlocked := true; record_compatible := true;
     requested := true; call_active := true |}.
Definition ended_call : GrantState :=
  {| unconsumed := true; unrevoked := true; record_fresh := true;
     profile_unlocked := true; record_compatible := true;
     requested := true; call_active := false |}.
Definition grant_with_scope (k : Scope) : Grant :=
  {| grantee := O; named_object := 1; witness_site := 2;
     issued := 5; grant_scope := k; ceiling := 9 |}.
Definition release_with_state (k : Scope) (st : GrantState) : Release :=
  {| grants := grant_with_scope k :: nil;
     states := fun _ => st; at_instant := 7 |}.

(*| discharges: R-05-166, R-08-037 |*)
Theorem both_one_shot_boundaries_are_live :
  live (grant_with_scope OneShot)
    {| grants := grant_with_scope OneShot :: nil; states := fun _ => ready_state;
       at_instant := 5 |} = true /\
  live (grant_with_scope OneShot)
    {| grants := grant_with_scope OneShot :: nil; states := fun _ => ready_state;
       at_instant := 9 |} = true.
Proof. split; reflexivity. Qed.

(*| discharges: R-05-166, R-08-025, R-08-037, R-08-040 |*)
Theorem scope_state_decides_authority :
  licensed (release_with_state OneShot ready_state) O 1 = true /\
  licensed (release_with_state OneShot used_state) O 1 = false /\
  licensed (release_with_state Persistent ready_state) O 1 = true /\
  licensed (release_with_state Persistent stale_state) O 1 = false /\
  licensed (release_with_state WhileActive revoked_state) O 1 = false /\
  licensed (release_with_state EmergencyCall ended_call) O 1 = false.
Proof. repeat split; reflexivity. Qed.

Definition discrete_order : PolicyModel :=
  {| levels := 2; flows := Nat.eqb; compartments := 3;
     clearance := ref_clearance; trusted := ref_trusted;
     sites := 4; content_level := ref_content_level;
     arrival_level := ref_arrival_level; drives := ref_drives;
     manifest_channel := fun _ _ => false; consent_site := ref_consent_site |}.

(*| discharges: R-05-166, R-08-024 |*)
Theorem a_partial_order_without_bounds_is_not_a_lattice :
  lattice_reflexive discrete_order = true /\
  lattice_transitive discrete_order = true /\
  lattice_antisymmetric discrete_order = true /\
  wellformed discrete_order = false.
Proof. repeat split; reflexivity. Qed.

(* -------------------------------------------------------------------------
   15. Robust declassification, and the three quantities an attacker must not
   move.
   ------------------------------------------------------------------------- *)

(* The powerbox this model ships: the grant set is a function of the consent
   site alone. *)
Definition consent_powerbox : Powerbox :=
  fun i now =>
    {| grants := match i.(consent) 2 with
                  | Some g => if Nat.eqb g.(witness_site) 2 then g :: nil else nil
                  | None => nil
                  end;
       states := fun _ => i.(lifecycle) 2;
       at_instant := now |}.

Definition consent_input : SystemInput :=
  {| delivers := fun _ => O; arrives := fun _ => O;
     consent := fun s => if Nat.eqb s 2 then Some consented_grant else None;
     lifecycle := fun _ => ready_state |}.

(*| discharges: R-05-166, R-06-017 |*)
Theorem an_unwitnessed_mint_is_refused :
  witnessed reference consent_input inside_scope = true
  /\ witnessed reference consent_input unwitnessed = false.
Proof. split; reflexivity. Qed.

Definition substituted_object : Release :=
  {| grants := {| grantee := O; named_object := 3; witness_site := 2;
                  issued := 5; grant_scope := WhileActive; ceiling := 9 |} :: nil;
     states := fun _ => ready_state; at_instant := 7 |}.

(*| discharges: R-05-166, R-06-017, R-08-036 |*)
Theorem a_site_name_is_not_a_consent_witness :
  witnessed reference quiet inside_scope = false /\
  witnessed reference consent_input substituted_object = false /\
  witnessed reference consent_input inside_scope = true.
Proof. repeat split; reflexivity. Qed.

(*| discharges: R-08-025, R-06-016 |*)
Theorem the_shipped_powerbox_is_robust : robust reference consent_powerbox.
Proof.
  intros i1 i2 now H. unfold consent_powerbox.
  destruct (H 2 eq_refl) as [_ [_ [Ha Hs]]]. rewrite Ha, Hs. reflexivity.
Qed.

(* R-08-025's three quantities follow from the one equality, which is why the
   statement is one equality and not three. *)
(*| discharges: R-08-025 |*)
Theorem robustness_fixes_whether_what_and_to_whom :
  forall (m : PolicyModel) (p : Powerbox) (i1 i2 : SystemInput) (now c : nat),
    robust m p -> consent_agrees m i1 i2 ->
    whether (p i1 now) c = whether (p i2 now) c
    /\ what (p i1 now) = what (p i2 now)
    /\ to_whom (p i1 now) = to_whom (p i2 now).
Proof.
  intros m p i1 i2 now c Hrobust Hagree.
  rewrite (Hrobust i1 i2 now Hagree). repeat split.
Qed.

(* --- the three powerboxes an attacker drives -------------------------- *)

(* Whether: the attacker's own site decides that a grant exists at all. *)
Definition powerbox_whether : Powerbox :=
  fun i now =>
    if Nat.eqb (i.(delivers) 1) O
    then {| grants := nil; states := fun _ => ready_state; at_instant := now |}
    else {| grants := consented_grant :: nil; states := fun _ => ready_state; at_instant := now |}.

(* What: the attacker's site decides which object the grant names. *)
Definition powerbox_what : Powerbox :=
  fun i now =>
    {| grants := {| grantee := O;
                    named_object := if Nat.eqb (i.(delivers) 1) O then 1 else 3;
                    witness_site := 2; issued := 5; grant_scope := WhileActive; ceiling := 9 |} :: nil;
       states := fun _ => ready_state; at_instant := now |}.

(* To whom: the attacker's site decides who receives it. *)
Definition powerbox_to_whom : Powerbox :=
  fun i now =>
    {| grants := {| grantee := if Nat.eqb (i.(delivers) 1) O then O else 1;
                    named_object := 1;
                    witness_site := 2; issued := 5; grant_scope := WhileActive; ceiling := 9 |} :: nil;
       states := fun _ => ready_state; at_instant := now |}.

Lemma quiet_and_secret_content_agree_on_consent :
  consent_agrees reference quiet secret_content.
Proof.
  intros s Hs. destruct s as [|[|[|[|s']]]]; cbn in Hs; try discriminate Hs.
  repeat split; reflexivity.
Qed.

(*| discharges: R-05-165, R-05-166, R-08-025 |*)
Theorem an_attacker_driven_powerbox_is_refused :
  ~ robust reference powerbox_whether
  /\ ~ robust reference powerbox_what
  /\ ~ robust reference powerbox_to_whom.
Proof.
  split; [| split]; intros H;
    assert (Hbad := H quiet secret_content O
                      quiet_and_secret_content_agree_on_consent);
    discriminate Hbad.
Qed.

(*| discharges: R-05-165, R-06-017, R-08-025, R-08-026, R-08-037 |*)
Theorem the_shipped_release_is_authorized :
  authorized_release_target reference consent_powerbox licensed.
Proof.
  split; [| split; [| split]].
  - intros i now. split; [|reflexivity]. unfold consent_powerbox.
    destruct (i.(consent) 2) as [g|] eqn:E; [| reflexivity].
    destruct (Nat.eqb g.(witness_site) 2) eqn:W; [| reflexivity].
    apply Nat.eqb_eq in W. unfold witnessed. cbn -[grant_eqb state_eqb].
    rewrite W. cbn -[grant_eqb state_eqb]. rewrite E, grant_eqb_refl, state_eqb_refl.
    reflexivity.
  - exact the_shipped_rule_is_delimited.
  - exact the_shipped_rule_is_scoped.
  - exact the_shipped_powerbox_is_robust.
Qed.

Definition backdated_powerbox : Powerbox :=
  fun i now => consent_powerbox i 7.

(*| discharges: R-05-166, R-08-037 |*)
Theorem a_backdated_release_is_not_authorized :
  ~ authorized_release_target reference backdated_powerbox licensed.
Proof.
  intros [H _]. destruct (H consent_input 11) as [_ E]. discriminate E.
Qed.

(* -------------------------------------------------------------------------
   16. The executions the target refuses.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-166, R-08-021 |*)
Theorem a_leaked_value_is_refused :
  ~ flow_noninterference reference (leaks_content reference).
Proof.
  intros H.
  destruct (H victim quiet secret_content O O eq_refl
              quiet_and_secret_content_are_indistinguishable) as [Hv _].
  discriminate Hv.
Qed.

(*| discharges: R-05-166, R-05-156a |*)
Theorem a_leaked_arrival_is_refused :
  ~ flow_noninterference reference (leaks_arrival reference).
Proof.
  intros H.
  destruct (H victim quiet secret_arrival O O eq_refl
              quiet_and_secret_arrival_are_indistinguishable) as [_ Ht].
  discriminate Ht.
Qed.

(*| discharges: R-05-166, R-08-027a, R-08-027b |*)
Theorem a_leaked_progress_is_refused :
  ~ progress_noninterference reference (leaks_progress reference).
Proof.
  intros H.
  destruct (H victim quiet secret_content O eq_refl
              quiet_and_secret_content_are_indistinguishable) as [_ [Hbad _]].
  discriminate Hbad.
Qed.

(*| discharges: R-05-166, R-08-027c |*)
Theorem a_leaked_fault_class_is_refused :
  ~ fault_noninterference reference (leaks_fault reference).
Proof.
  intros H.
  assert (Hbad := H victim quiet secret_content O eq_refl
                    quiet_and_secret_content_are_indistinguishable).
  destruct Hbad as [Hfault _]. discriminate Hfault.
Qed.

Definition leaks_termination : Execution :=
  fun i => {| received := (confining reference i).(received);
              observed_at := (confining reference i).(observed_at);
              slot := (confining reference i).(slot);
              reached := (confining reference i).(reached);
              raised := (confining reference i).(raised);
              restarts := (confining reference i).(restarts);
              width := (confining reference i).(width);
              finished := fun _ => Nat.eqb (i.(delivers) 1) O |}.

Definition leaks_restart : Execution :=
  fun i => {| received := (confining reference i).(received);
              observed_at := (confining reference i).(observed_at);
              slot := (confining reference i).(slot);
              reached := (confining reference i).(reached);
              raised := (confining reference i).(raised);
              restarts := fun _ => i.(delivers) 1;
              width := (confining reference i).(width);
              finished := (confining reference i).(finished) |}.

(*| discharges: R-05-166, R-08-027a |*)
Theorem a_leaked_termination_is_refused :
  ~ progress_noninterference reference leaks_termination.
Proof.
  intros H. destruct (H victim quiet secret_content O eq_refl
    quiet_and_secret_content_are_indistinguishable) as [_ [_ [_ Hbad]]].
  discriminate Hbad.
Qed.

(*| discharges: R-05-166, R-08-027c |*)
Theorem a_leaked_restart_is_refused :
  ~ fault_noninterference reference leaks_restart.
Proof.
  intros H. destruct (H victim quiet secret_content O eq_refl
    quiet_and_secret_content_are_indistinguishable) as [_ Hbad].
  discriminate Hbad.
Qed.

(* -------------------------------------------------------------------------
   17. The arrival arm the register does not decide.

   With one compose-time channel the two arms are different policies: the
   narrow one relates a pair the wide one separates. Neither is refuted here
   and neither is adopted by argument; the vocabulary below ships the narrow
   one, and the act that would settle it is a register act.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-166 |*)
Theorem the_two_arrival_arms_are_different_policies :
  indistinguishable channelled victim quiet secret_arrival
  /\ ~ indistinguishable_wide channelled victim quiet secret_arrival.
Proof.
  split.
  - split; intros s [c [Hc Hmay]]; unfold victim in Hc; subst c.
    + destruct s as [|[|[|[|s']]]]; cbn in Hmay; try discriminate Hmay;
        reflexivity.
    + destruct s as [|s']; [reflexivity | discriminate Hmay].
  - intros [_ Htime].
    assert (Hbad := Htime 1 (ex_intro _ O (conj eq_refl eq_refl))).
    discriminate Hbad.
Qed.

(* -------------------------------------------------------------------------
   18. The apex instantiation (crown-jewel row 1's parameters).

   Policy, policy, indist, Declass, D and the three release quotients are the
   fields row 2 owes; every other Prop field is another row's and is True
   here, which claims nothing of it. explicit_flow_noninterference and
   declassified_flows_authorized are the two this file states, so the seam
   that consumes each reads a Prop with content rather than a placeholder.
   ------------------------------------------------------------------------- *)

Definition apex_vocabulary (m : PolicyModel) (x : Execution) (p : Powerbox)
    (r : ReleaseRule) (rel : Release) : Vocabulary := {|
  Input := SystemInput;
  Trace := SystemTrace;
  exec := x;
  Compartment := nat;
  tcb := fun c => m.(trusted) c = true;
  graph_permits := fun C => forall c : nat, C c -> Nat.ltb c m.(compartments) = true;
  Policy := PolicyModel;
  policy := m;
  indist := fun policy C i1 i2 => release_indistinguishable policy rel C i1 i2;
  ValueObs := nat -> nat -> nat -> Prop;
  TimingObs := nat -> nat -> nat -> Prop;
  ArchObs := nat -> (nat * nat) -> Prop;
  observe_value := fun C t c s v => C c /\ t.(received) c s = v;
  observe_timing := fun C t c k v => C c /\ timing_view t c k = v;
  observe_arch := fun C t c k => C c /\ (t.(raised) c, t.(restarts) c) = k;
  Declass := Release;
  D := rel;
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
  explicit_flow_noninterference := released_flow_target m rel x /\
    progress_noninterference m x /\ fault_noninterference m x /\
    (forall C i1 i2 c s, C c -> indistinguishable m C i1 i2 ->
       (x i1).(observed_at) c s = (x i2).(observed_at) c s);
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
  declassified_flows_authorized :=
    authorized_release_target m p r /\
    exists i, p i rel.(at_instant) = rel;
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

(* The two fields this file states are satisfiable at the reference
   composition, so neither seam reads an unsatisfiable premise. *)
(*| discharges: R-05-165 |*)
Theorem the_two_stated_fields_are_satisfiable :
  (apex_vocabulary reference (confining reference) consent_powerbox licensed
     inside_scope).(explicit_flow_noninterference)
  /\ (apex_vocabulary reference (confining reference) consent_powerbox licensed
        inside_scope).(declassified_flows_authorized).
Proof.
  split.
  - destruct (the_confining_execution_is_noninterferent reference)
      as [Hflow [Hprogress Hfault]].
    split.
    + intros C i1 i2 c s Hc [Hi _]. exact (proj1 (Hflow C i1 i2 c s Hc Hi)).
    + split; [exact Hprogress|]. split; [exact Hfault|].
      intros C i1 i2 c s Hc Hi. exact (proj2 (Hflow C i1 i2 c s Hc Hi)).
  - split; [exact the_shipped_release_is_authorized |].
    exists consent_input. reflexivity.
Qed.

Definition never_mints : Powerbox :=
  fun i now => {| grants := nil; states := fun _ => ready_state; at_instant := now |}.

(*| discharges: R-05-166, R-05-160 |*)
Theorem an_unrelated_D_is_not_authorized :
  ~ (apex_vocabulary reference (confining reference) never_mints licensed
       inside_scope).(declassified_flows_authorized).
Proof. intros [_ [i H]]. discriminate H. Qed.

Lemma the_victim_set_is_admissible :
  forall (x : Execution) (p : Powerbox) (r : ReleaseRule) (rel : Release),
    admissible (apex_vocabulary reference x p r rel) victim.
Proof.
  intros x p r rel. split.
  - intros c Hc. unfold victim in Hc. subst c. reflexivity.
  - intros c Hc Htcb. unfold victim in Hc. subst c. discriminate Htcb.
Qed.

(* -------------------------------------------------------------------------
   19. What reaching T costs, stated rather than assumed.

   observation_equal_modulo_D is Leibniz equality at the three observation
   types. An observation that masks by the adversary set is a function into
   Prop, because the set arrives as a Prop-valued predicate no function can
   decide, so pointwise agreement reaches equality only through functional
   and propositional extensionality. Both are premises here and neither is an
   axiom: R-05-164's declared set is empty and this file adds nothing to it.
   ------------------------------------------------------------------------- *)

Definition FunExt2 : Prop :=
  forall A : Type, forall f g : nat -> A -> Prop,
    (forall a b, f a b = g a b) -> f = g.

Definition FunExt3 : Prop :=
  forall f g : nat -> nat -> nat -> Prop,
    (forall a b c, f a b c = g a b c) -> f = g.

Definition PropExt : Prop :=
  forall P Q : Prop, (P <-> Q) -> P = Q.

(*| discharges: R-05-156, R-05-161 |*)
Theorem apex_from_pointwise :
  forall (m : PolicyModel) (x : Execution) (p : Powerbox) (rel : Release),
    FunExt2 -> FunExt3 -> PropExt ->
    (forall C i1 i2 c s, C c -> release_indistinguishable m rel C i1 i2 ->
        (x i1).(received) c s = (x i2).(received) c s) ->
    (forall C i1 i2 c k, C c -> indistinguishable m C i1 i2 ->
        timing_view (x i1) c k = timing_view (x i2) c k) ->
    (forall C i1 i2 c, C c -> indistinguishable m C i1 i2 ->
        ((x i1).(raised) c, (x i1).(restarts) c)
        = ((x i2).(raised) c, (x i2).(restarts) c)) ->
    T (apex_vocabulary m x p licensed rel).
Proof.
  intros m x p rel fe2 fe pe Hval Htim Harch _ C _ i1 i2 Hind.
  split; [| split].
  - apply fe. intros c s v. cbn -[licensed].
    apply pe. split; intros [Hc Heq]; split; try exact Hc.
    + rewrite <- (Hval C i1 i2 c s Hc Hind). exact Heq.
    + rewrite (Hval C i1 i2 c s Hc Hind). exact Heq.
  - apply fe. intros c k v. cbn -[licensed].
    apply pe. split; intros [Hc Heq]; split; try exact Hc.
    + rewrite <- (Htim C i1 i2 c k Hc (proj1 Hind)). exact Heq.
    + rewrite (Htim C i1 i2 c k Hc (proj1 Hind)). exact Heq.
  - apply (fe2 _). intros c k. cbn -[licensed].
    apply pe. split; intros [Hc Heq]; split; try exact Hc.
    + rewrite <- (Harch C i1 i2 c Hc (proj1 Hind)). exact Heq.
    + rewrite (Harch C i1 i2 c Hc (proj1 Hind)). exact Heq.
Qed.

Lemma confining_received_agrees :
  forall (m : PolicyModel) (C : nat -> Prop) (i1 i2 : SystemInput) (c s : nat),
    C c -> indistinguishable m C i1 i2 ->
    (confining m i1).(received) c s = (confining m i2).(received) c s.
Proof.
  intros m C i1 i2 c s Hc [Hread _]. cbn.
  destruct (may_read m c s) eqn:E; [| reflexivity].
  apply Hread. exists c. split; assumption.
Qed.

Lemma confining_timing_agrees :
  forall (m : PolicyModel) (C : nat -> Prop) (i1 i2 : SystemInput) (c k : nat),
    C c -> indistinguishable m C i1 i2 ->
    timing_view (confining m i1) c k = timing_view (confining m i2) c k.
Proof.
  intros m C i1 i2 c k Hc Hind. destruct Hind as [Hread Htime].
  destruct k as [|[|[|[|s]]]]; cbn.
  - reflexivity.
  - unfold visible_progress. apply progress_upto_agrees.
    intros s E. apply Hread. exists c. split; assumption.
  - reflexivity.
  - reflexivity.
  - destruct (may_time m c s) eqn:E; [| reflexivity].
    apply Htime. exists c. split; assumption.
Qed.

(*| discharges: R-05-165, R-05-166 |*)
Theorem the_reference_composition_reaches_T :
  forall rel : Release,
    FunExt2 -> FunExt3 -> PropExt ->
    T (apex_vocabulary reference (confining reference) consent_powerbox
         licensed rel).
Proof.
  intros rel fe2 fe pe.
  apply apex_from_pointwise.
  - exact fe2.
  - exact fe.
  - exact pe.
  - intros C i1 i2 c s Hc [Hind _].
    exact (confining_received_agrees reference C i1 i2 c s Hc Hind).
  - intros C i1 i2 c k Hc Hind.
    exact (confining_timing_agrees reference C i1 i2 c k Hc Hind).
  - intros C i1 i2 c Hc Hind. reflexivity.
Qed.

(* A runtime release actually widens the admitted behaviours: the recipient
   reads the named secret object. Other sites, arrival instants, progress and
   faults retain the confining execution's observations. *)
Definition releases_named_object : Execution :=
  fun i => {| received := fun c s =>
                if andb (Nat.eqb c O) (Nat.eqb s 1)
                then i.(delivers) 1 else (confining reference i).(received) c s;
              observed_at := (confining reference i).(observed_at);
              slot := (confining reference i).(slot);
              reached := (confining reference i).(reached);
              raised := (confining reference i).(raised);
              restarts := (confining reference i).(restarts);
              width := (confining reference i).(width);
              finished := (confining reference i).(finished) |}.

Theorem the_named_release_satisfies_its_flow_target :
  released_flow_target reference inside_scope releases_named_object.
Proof.
  intros C i1 i2 c s Hc [Hind Hreleased]. cbn -[confining].
  destruct (andb (Nat.eqb c O) (Nat.eqb s 1)) eqn:E.
  - apply andb_prop in E as [Ec Es].
    apply Nat.eqb_eq in Ec. apply Nat.eqb_eq in Es. subst c s.
    apply (Hreleased O 1 Hc). reflexivity.
  - exact (confining_received_agrees reference C i1 i2 c s Hc Hind).
Qed.

Theorem the_actual_named_release_inhabits_both_seams :
  (apex_vocabulary reference releases_named_object consent_powerbox licensed
     inside_scope).(explicit_flow_noninterference) /\
  (apex_vocabulary reference releases_named_object consent_powerbox licensed
     inside_scope).(declassified_flows_authorized).
Proof.
  split.
  - split; [exact the_named_release_satisfies_its_flow_target|].
    destruct (the_confining_execution_is_noninterferent reference)
      as [Hflow [Hprogress Hfault]].
    split; [exact Hprogress|]. split; [exact Hfault|].
    intros C i1 i2 c s Hc Hi. exact (proj2 (Hflow C i1 i2 c s Hc Hi)).
  - split; [exact the_shipped_release_is_authorized|].
    exists consent_input. reflexivity.
Qed.

(* The rejected construction puts object 3's secret into the output slot
   consent named for object 1. Output-slot erasure would hide this conduit. *)
Definition smuggles_another_object : Execution :=
  fun i => {| received := fun c s =>
                if andb (Nat.eqb c O) (Nat.eqb s 1)
                then i.(delivers) 3 else (confining reference i).(received) c s;
              observed_at := (confining reference i).(observed_at);
              slot := (confining reference i).(slot);
              reached := (confining reference i).(reached);
              raised := (confining reference i).(raised);
              restarts := (confining reference i).(restarts);
              width := (confining reference i).(width);
              finished := (confining reference i).(finished) |}.

Lemma other_object_variation_stays_inside_the_release_relation :
  release_indistinguishable reference inside_scope victim quiet port_content.
Proof.
  split; [exact quiet_and_port_content_are_indistinguishable|].
  intros c s Hc Hlive. unfold victim in Hc. subst c.
  destruct s as [|[|s]]; cbn in Hlive; try discriminate; reflexivity.
Qed.

Theorem a_named_output_cannot_smuggle_another_objects_content :
  ~ T (apex_vocabulary reference smuggles_another_object consent_powerbox
         licensed inside_scope).
Proof.
  intros H. destruct (H (conj I (conj I (conj I (conj I I)))) victim
    (the_victim_set_is_admissible smuggles_another_object consent_powerbox licensed inside_scope)
    quiet port_content other_object_variation_stays_inside_the_release_relation) as [Hv _].
  pose proof (f_equal (fun k : nat -> nat -> nat -> Prop => k O 1 O) Hv) as E.
  cbn in E. assert (A : victim O /\ O = O) by (split; reflexivity).
  change ((O = O /\ O = O) = (O = O /\ 1 = O)) in E.
  unfold victim in A. rewrite E in A. destruct A as [_ B]. discriminate B.
Qed.

Example actual_named_content_is_released_but_not_an_arbitrary_slot :
  (releases_named_object quiet).(received) O 1 = O /\
  (releases_named_object secret_content).(received) O 1 = 1 /\
  ~ release_indistinguishable reference inside_scope victim quiet secret_content.
Proof.
  split; [reflexivity|]. split; [reflexivity|].
  intros [_ H]. specialize (H O 1 eq_refl eq_refl). discriminate H.
Qed.

(*| discharges: R-05-166, R-08-025, R-08-026 |*)
Theorem a_named_release_is_inside_T :
  FunExt2 -> FunExt3 -> PropExt ->
  T (apex_vocabulary reference releases_named_object consent_powerbox
       licensed inside_scope).
Proof.
  intros fe2 fe pe. apply apex_from_pointwise; try assumption.
  - intros C i1 i2 c s Hc [Hind Hreleased]. cbn -[confining].
    destruct (andb (Nat.eqb c O) (Nat.eqb s 1)) eqn:E.
    + apply andb_prop in E. destruct E as [Ec Es].
      apply Nat.eqb_eq in Ec. apply Nat.eqb_eq in Es. subst c s.
      apply (Hreleased O 1 Hc). reflexivity.
    + exact (confining_received_agrees reference C i1 i2 c s Hc Hind).
  - intros C i1 i2 c k Hc Hind.
    exact (confining_timing_agrees reference C i1 i2 c k Hc Hind).
  - intros C i1 i2 c Hc Hind. reflexivity.
Qed.

(*| discharges: R-05-166, R-08-037 |*)
Theorem the_same_release_after_expiry_is_outside_T :
  ~ T (apex_vocabulary reference releases_named_object consent_powerbox
         licensed outside_scope).
Proof.
  intros H.
  assert (Hi : release_indistinguishable reference outside_scope victim quiet secret_content).
  { split; [exact quiet_and_secret_content_are_indistinguishable|].
    intros c s Hc Hl. unfold licensed in Hl. cbn in Hl.
    rewrite andb_false_r in Hl. discriminate Hl. }
  destruct (H (conj I (conj I (conj I (conj I I)))) victim
    (the_victim_set_is_admissible releases_named_object consent_powerbox
      licensed outside_scope) quiet secret_content
    Hi) as [Hv _].
  pose proof (f_equal (fun k : nat -> nat -> nat -> Prop => k O 1 O) Hv) as E.
  cbn in E.
  assert (A : victim O /\ O = O) by (split; reflexivity).
  change ((O = O /\ O = O) = (O = O /\ 1 = O)) in E.
  unfold victim in A. rewrite E in A. destruct A as [_ B]. discriminate B.
Qed.

(* The distinguishing instance R-05-166 asks for, at the apex statement
   itself and not only at this file's own targets: the leaking composition is
   one T rejects. It needs neither extensionality premise, which is the
   asymmetry the header reports. *)
(*| discharges: R-05-165, R-05-166 |*)
Theorem the_leaking_composition_is_rejected_by_T :
  ~ T (apex_vocabulary reference (leaks_content reference) consent_powerbox
         licensed no_grants).
Proof.
  intros H.
  destruct (H (conj I (conj I (conj I (conj I I)))) victim
              (the_victim_set_is_admissible (leaks_content reference)
                 consent_powerbox licensed no_grants)
              quiet secret_content
              (conj quiet_and_secret_content_are_indistinguishable
                (fun c s _ H => False_rect _ (Bool.diff_false_true H)))) as [Hvalue _].
  assert (Hpoint := f_equal (fun k : nat -> nat -> nat -> Prop => k O O O) Hvalue).
  cbn in Hpoint.
  assert (Hholds : victim O /\ (leaks_content reference quiet).(received) O O = O).
  { split; reflexivity. }
  cbn in Hholds. rewrite Hpoint in Hholds.
  destruct Hholds as [_ Hbad]. discriminate Hbad.
Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: the enumerated
   assumption set of every constant above is compared against the declared set
   R-05-164 reads from the register, which is empty today. "Closed under the
   global context" is that emptiness, checked mechanically; the two
   extensionality principles above are premises of the theorems that use them
   and therefore appear in no assumption set.
   ------------------------------------------------------------------------- *)

Print Assumptions the_model_rejects_a_labelling.
Print Assumptions the_confining_execution_is_noninterferent.
Print Assumptions the_domain_admits_victim_shaped_sets.
Print Assumptions observation_and_control_are_incomparable.
Print Assumptions a_quantified_out_arrival_is_equated.
Print Assumptions the_device_clause_decides_something.
Print Assumptions indistinguishability_has_classes.
Print Assumptions a_compose_time_channel_is_inside_the_policy.
Print Assumptions the_shipped_rule_is_delimited.
Print Assumptions the_shipped_rule_is_scoped.
Print Assumptions the_scope_decides_the_quotient.
Print Assumptions a_release_wider_than_the_named_object_is_refused.
Print Assumptions an_edge_outliving_its_act_is_refused.
Print Assumptions an_unwitnessed_mint_is_refused.
Print Assumptions the_shipped_powerbox_is_robust.
Print Assumptions robustness_fixes_whether_what_and_to_whom.
Print Assumptions an_attacker_driven_powerbox_is_refused.
Print Assumptions the_shipped_release_is_authorized.
Print Assumptions a_leaked_value_is_refused.
Print Assumptions a_leaked_arrival_is_refused.
Print Assumptions a_leaked_progress_is_refused.
Print Assumptions a_leaked_fault_class_is_refused.
Print Assumptions the_two_arrival_arms_are_different_policies.
Print Assumptions the_two_stated_fields_are_satisfiable.
Print Assumptions apex_from_pointwise.
Print Assumptions the_reference_composition_reaches_T.
Print Assumptions the_leaking_composition_is_rejected_by_T.

Print Assumptions scope_state_decides_authority.
Print Assumptions a_partial_order_without_bounds_is_not_a_lattice.
Print Assumptions a_site_name_is_not_a_consent_witness.
Print Assumptions an_unrelated_D_is_not_authorized.
Print Assumptions a_named_release_is_inside_T.
Print Assumptions the_same_release_after_expiry_is_outside_T.

Print Assumptions both_lease_boundaries_are_live.

Print Assumptions wellformed_requires_each_lattice_law.
Print Assumptions both_one_shot_boundaries_are_live.
Print Assumptions a_leaked_termination_is_refused.
Print Assumptions a_leaked_restart_is_refused.

Print Assumptions a_backdated_release_is_not_authorized.
