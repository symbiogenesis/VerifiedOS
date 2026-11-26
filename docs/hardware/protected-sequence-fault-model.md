# The Protected-Sequence Fault Model

*Normative as a **crown-jewel specification**. This document is the artifact **R-16-008f** mandates and R-16-008c and R-17-058b depend on: the single-fault transition relation the signature-and-token detection theorem is proved over, stated over the frozen profile's semantics. It is [the crown-jewel inventory](../assurance/crown-jewels.md)'s row 24.*

> **Precedence.** Where this document and [the requirements register](../requirements-register.md) disagree, **the register wins and this document is defective.** This document states the relation. It states no obligation the register does not, and it narrows nothing the register admits.

## Why this document exists

R-16-008f requires the three R-16-008c sequences to carry their detection *"as a theorem over a stated fault model rather than as coverage alone"*, and names that model *"at most one skipped or corrupted instruction per protected region per activation, stated as a transition relation over the frozen profile's semantics"*. The register states the model's size and says where it lives; it does not state the relation. [The unassigned proof map](../assurance/unassigned-proof-map.md)'s U-19 starts from *"Q3c's accepted relation"* and must quantify over *"every in-model fault of the model instance"*. Without the relation that quantifier has no set, and R-16-008f's acceptance criterion, which distinguishes quantifying from sampling, is not decidable.

The relation is therefore the premise of a software theorem. R-17-016 defines the crown-jewel status by the failure a wrong specification produces: a correct proof of the wrong property, which no amount of proof effort beneath it detects. A fault model is that shape exactly, since it is the hypothesis every detection claim is conditional on, so what this document owes above all is that its exclusions are named rather than assumed and that its statement is strong enough to be wrong.

## 1. What this model is, and what it is not

**It is an axiom about the silicon in the R-06-011 sense.** Nothing in this repository proves that the die's fault behaviour lies inside the relation below. R-17-058b states the consequence: within the model the mode is proved and the axiom is the model's, and outside it no row, mode, or requirement states a detection *probability* or claims a mode above *detected*. R-16-008a is the reason the axiom is needed at all: an injected fault puts the machine outside its own semantics, so no theorem stated over the Sail model reaches it, and a model of the fault is how a theorem is recovered on the far side of that break.

**It is not a hardware obligation.** R-16-008f's acceptance criterion holds R-16-008d and R-16-008e unamended, *"the model being the premise of a software theorem and never a hardware, voting, or RTL ⊑ Sail obligation"*. Nothing here asks for a comparator, a third instance, a masking argument, or a rung of the refinement tower. R-16-008e in particular stands: no control-flow-signature hardware, no landing-pad or shadow-stack mechanism, and no ISA surface of any kind, so the signature register named throughout is a compiler-allocated general-purpose register of the merged file and the decode surface is the frozen profile's unchanged.

**It is not the detection theorem, and it decides nothing the theorem must prove.** U-19 owns the construction as a model, the region's control-flow graph, the signature fold, the doubled comparison, the token, and the proof. The R-16-008f theorem on the final binary, the compiler-emitted instrumentation, the countermeasure construction and the R-17-058d reduction are booked where the unassigned proof map and the plan's post-M10 cells book them. The binary-level check where a sequence passes admission is artifact-admission's, the split R-16-008c already takes.

**It is not a second transcription of the instruction set.** The relation perturbs the curated Sail model's own step function at two named sites and reuses every definition below them. Anything this document restated would be a second holder of a fact [model/](../../model/) owns.

## 2. The subject: the exact Sail definitions the relation perturbs

The subject is one function. `try_step(step_no : nat, exit_wait : bool) -> bool` in [postlude/step.sail](../../model/model/postlude/step.sail) is the model's fetch-decode-execute step, and the relation below is a perturbation of that function at two sites inside the `HART_ACTIVE()` arm it dispatches to: the word the `F_Base(w)` arm binds, and the `ExecutionResult` that arm carries into `Step_Execute`. A site is a binding rather than one of its uses, which is the distinction the `corrupt` definition below turns on.

| Definition | Where | What this relation does with it |
| --- | --- | --- |
| `try_step` | [postlude/step.sail](../../model/model/postlude/step.sail) | the step the relation perturbs; one call is one transition |
| `hart_state : HartState` | [postlude/step.sail](../../model/model/postlude/step.sail), the type in [postlude/step_common.sail](../../model/model/postlude/step_common.sail) | the relation is defined on the `HART_ACTIVE()` arm; the waiting arm is unperturbed |
| `run_hart_active` | [postlude/step.sail](../../model/model/postlude/step.sail) | carries both perturbation sites |
| `fetch()`, `FetchResult`, the `F_Base(w : word)` arm | [postlude/fetch.sail](../../model/model/postlude/fetch.sail), [postlude/step_common.sail](../../model/model/postlude/step_common.sail) | supplies `w`, the fetched 32-bit word; the arm's binding of `w` is the corruption site, taken after `fetch()` returns and the fetch's own checks have passed |
| `ext_decode(w)` | [postlude/decode_ext.sail](../../model/model/postlude/decode_ext.sail), which is the `encdec` mapping | consumes the perturbed word unchanged |
| the `instbits` binding, the `Step_Execute(Illegal_Instruction(), instbits)` arm, and `handle_exception`'s `xtval` parameter | [postlude/step.sail](../../model/model/postlude/step.sail), [sys/sys_control.sail](../../model/model/sys/sys_control.sail) | binds the fetched word one line above `ext_decode` and carries it to `mtval` on the illegal-encoding path, which is why the corruption site is the arm's binding and not `ext_decode`'s argument |
| `execute : instruction -> ExecutionResult` and the arms of `ExecutionResult` | [sys/insts_begin.sail](../../model/model/sys/insts_begin.sail) | consumes the decoded instruction unchanged; the `Retire_Success()` arm is what the skip perturbation substitutes |
| `nextPC = PC + 4`, `set_next_pc` | [postlude/step.sail](../../model/model/postlude/step.sail), [core/pc_access.sail](../../model/model/core/pc_access.sail) | unperturbed; the sequential advance is installed before `execute` runs, so a perturbed control transfer redirects exactly as a genuine one does |
| `tick_pc()`, `PC`, `nextPC`, `PCC`, `nextPCC` | [core/pc_access.sail](../../model/model/core/pc_access.sail), [core/regs.sail](../../model/model/core/regs.sail), [core/cap_regs.sail](../../model/model/core/cap_regs.sail) | the commit point; a transition of this relation is a call of `try_step` that reaches it |

Write `Sigma` for the model's architectural state: the merged register file, `PC`, `nextPC`, `PCC`, `nextPCC`, `hart_state`, the present CSR bank of [the profile's §5.1](isa-profile.md#51-present), and memory with its tag plane. Write `step(s)` for the state after one call `try_step(n, true)` from `s`, and `w(s)` for the word `fetch()` returns in its `F_Base` arm when the fetch succeeds. `step` is the fault-free transition, and it is the model's, not this document's.

Two perturbations are defined, each at a named site of `run_hart_active`. Write `step_f(s)` for the state after one call `try_step(n, true)` from `s` with the perturbation `f` applied at the site it names, so `step_f` differs from `step` at that site and nowhere else. Where the site is not reached the perturbation applies nowhere and `step_f(s)` is `step(s)`: at a state whose `hart_state` is `HART_WAITING` the active arm does not run, and at a step whose `fetch()` returns an error the `F_Base` arm is not taken. Those transitions are in the relation and are architecturally empty. That is not a defect of the rules but the extreme case of an effect-preserving fault under R-16-008f's effective-fault disjunction, and saying it is what keeps the index set the one the rules actually generate rather than the one a reader supplies.

- **`corrupt(w')`**, for a word `w' : bits(32)`: the step proceeds as `step` except that the `F_Base` arm is evaluated with `w'` in place of the word it binds, so every use inside that arm moves with it, `sail_instr_announce`, `fetch_callback`, the `instbits` binding and `ext_decode` alike. Substituting at the binding rather than at `ext_decode`'s argument is what the relation must say, because `instbits` is bound from the fetched word one line above the decode and is what the `Step_Execute(Illegal_Instruction(), instbits)` arm hands to `handle_exception` as `xtval`: a perturbation taken later would leave an unallocated `w'` trapping with the *unperturbed* word in `mtval`, and `mtval` is a present-bank CSR and so a component of the `Sigma` above, so the in-model faulted state would differ architecturally from the physical fault it models. Everything downstream is then the model's own: the decode of `w'` is `encdec`'s, an unallocated `w'` reaches `ILLEGAL` through the wildcard clause and traps with the whole word in `mtval` as [the fetch's own note](../../model/model/postlude/fetch.sail) records, a `w'` whose execution raises a capability or address fault raises the model's fault, and a `w'` that is a control transfer redirects through `set_next_pc`.
- **`skip`**: the step proceeds as `step` except that `execute` is not applied and the `ExecutionResult` the arm carries into `Step_Execute` is `Retire_Success()`. The fetched word is unperturbed, so `instbits` is the model's and the trap paths are unreached. The sequential advance `nextPC = PC + 4` has already been installed and `nextPCC` is untouched, so `tick_pc()` commits the next sequential instruction and no other architectural state moves.

As a transition on `Sigma`, `skip` coincides with `corrupt` at the canonical no-op encoding, because a no-op's execution also changes nothing but the committed PC. Both are named because R-16-008f names both and because their physical origins differ: an instruction-skip and a corrupted instruction word are distinct injection mechanisms on the die, and whether the coincidence holds there is a question for the characterization named at the end of this document, not for the relation.

**The perturbation is applied to the fetched word and to nothing else.** That single sentence is the fault domain, and the exclusions below are its consequences rather than carve-outs added to it.

## 3. Protected regions and activations

A **protected region** `R` is a finite set of instruction addresses with a distinguished entry `a_in` **in** `R` and exit `a_out` **outside** it, closed up to that exit under the control-flow graph the compose-time instrumentation predicts its exit signature from, and reachable under one code capability. Membership is a property of the emitted image, fixed at compose time, and is not a runtime predicate the machine evaluates: R-16-008e forbids any ISA surface that could evaluate one.

`a_out` sitting outside `R` is the whole of what makes the activation rule below and [the run's termination rule](#4-the-relation) one rule rather than two, and it decides a boundary case on its own: the step that consumes the region's decision is outside the model rather than inside it, which is where R-17-058b's safe-error limit and not this relation answers for it. The witness's entry condition, a `PCC` authorizing `[a_in, a_out)`, is that same membership read off one instance.

The **region predicate** is taken on the committed program counter at the fetch point: `in_region(s)` holds when `PC(s)` is in `R` and `PCC(s)` is the region's code capability. Taking it on `PCC` as well as on `PC` is what makes it a statement about the region rather than about an address, since the profile's single physical address space is shared and the authority is what distinguishes one image's region from another's.

An **activation** is one traversal of `R`: a maximal run of transitions beginning at the step whose `PC` is `a_in` and ending at the first later step whose committed `PC` is `a_out`, or whose committed `PC` leaves `R` by any other route. A region entered twice is two activations, and the fault budget is per activation because R-16-008f's phrase is *"per protected region per activation"*.

R-16-008c's three sequence classes are the regions this model is about, and each is an ordinary instruction sequence on a composed hart:

| Class | What bounds the region | Why it needs no special surface |
| --- | --- | --- |
| The measured-boot chain's per-stage verify-then-transfer | entry at the stage's verification prologue; the transfer of control to the verified stage is the last in-region step and `a_out` is the stage it transfers to | ordinary loads, arithmetic and a control transfer |
| The credential comparison at the RoT gate | entry at the comparison's prologue; the token's computation is the last in-region work and `a_out` is where the gate's decision is consumed | the RoT's fuse bank, entropy root, counter file and watchdog are reached by ordinary loads and stores through capabilities, with no instruction, no access type, no CSR and nothing on the decode surface ([sys/rot.sail](../../model/model/sys/rot.sail)) |
| The lifecycle transition over one-way fuse state | entry at the transition's guard; the store committing the new fuse state is the last in-region step and `a_out` is the address after it | the same fuse window, read and written as memory |

**The three rows put `a_out` on one side of the boundary and their named acts on different ones, which is a fact about the classes and not a slip in the convention.** `a_out` is the first committed address outside `R` in all three. At the boot chain and at the lifecycle guard the act the row names is the last in-region step, so the transfer of control and the fuse commitment are each in the model and a fault on either is in the relation's range. At the credential gate the last in-region work is the token's computation and the act the row names, the consumption of the decision, is at `a_out` and outside. Naming the side is not decoration: reading any row the other way moves that class's decisive instruction across the boundary, and for the lifecycle transition the instruction that moves is the irreversible one.

The split R-16-008c takes between a sequence that passes admission and one that lives in the boot ROM decides **where the theorem is checked**, on the final binary in the first case and fixed at tapeout in the second. It does not decide where the region is, and this relation is the same relation in both cases.

## 4. The relation

A faulted execution of one activation is indexed by a **budget** `b`, which is `1` at `a_in` and is never replenished within the activation. Two rules generate the relation on configurations `(s, b)`.

```
                                                        in_region(s)      f in { skip } U { corrupt(w') : w' in bits(32) }
  ------------------------------- (STEP)               ------------------------------------------------------------------ (FAULT)
   (s, b)  -->  (step(s), b)                                        (s, 1)  -->  (step_f(s), 0)
```

An **execution of the activation** is the maximal run of these rules from `(s_in, 1)`, where `s_in` is a state with `PC = a_in`: the finite derivation ending at the first configuration whose committed `PC` is outside `R`, or, where no configuration commits such a `PC`, the infinite sequence of configurations the rules generate. The relation is the set of those runs. The second case is not a formality: [the classification below](#5-fault-free-in-model-faulted-and-excluded) names it and says where it is absorbed.

**The step bound is a premise on the region instance, and is not a property of the rules.** A region instance enters this model carrying a fixed `N`: its fault-free traversal from `a_in` commits a `PC` outside `R` within `N` transitions, `N` being determined at compose time from the region's control-flow graph and the loop bounds the instrumentation already needs in order to predict the exit signature. Neither `STEP` nor `FAULT` supplies that bound, and a faulted run can outlive it, a single in-region `skip` of a loop-counter increment leaving the fault-free continuation circling inside `R` at budget `0` with no exit. Stating `N` as a premise on the instance is what makes the index set below a set; no reading of the rules alone supplies it, and a region whose loop bounds are not fixed at compose time is not a region this model admits.

Four properties of the statement are the ones the acceptance predicate asks about, and each is a property of the rules and that one premise rather than a remark beside them.

- **A second fault in one activation is rejected by the absence of a rule.** `FAULT` requires budget `1` and produces budget `0`, and there is no rule with budget `0` in its premise other than `STEP`. A run carrying two perturbations therefore has no derivation. It is not excluded by a side condition that a later reading could soften, and it is not excluded by a predicate over the run: it is not generated.
- **An out-of-region fault is rejected the same way.** `FAULT` carries `in_region(s)` as a premise, so a perturbation at a step whose `PC` lies outside `R` has no derivation either. This reaches the case a reader is most likely to lose: a region that calls out to a helper spends its steps at addresses the region's control-flow graph does not contain, and a fault there is outside the model. Whether a given helper is inside `R` is a compose-time fact about the emitted image, and a construction that leaves the decision's work outside the region it protects is not covered by the theorem however short the region reads.
- **The fault index is finite and decidable.** For one activation of one region instance the index is the position of the faulted step, crossed with the alternatives at that position: `skip`, or `corrupt(w')` for each of the 2^32 words. The position is at most `N`, because `FAULT` fires only at budget `1` and a configuration at budget `1` sits on the fault-free traversal the premise above bounds. So *every in-model fault of each protected region* is a quantification over a set the rules and that premise exhibit the shape of, which is what R-16-008f's acceptance criterion asks of the statement when it distinguishes quantifying from sampling. Nothing here says the quantification is cheap; it says it is a quantification, and a region instance admitted without an `N` does not supply one.
- **The relation is the strongest hypothesis on the adversary that R-16-008f's words admit, and one choice in it is a judgment the register does not make.** R-16-008f says *"skipped or corrupted"* and stops. This document reads *corrupted* as **arbitrary replacement of the fetched word**, rather than as a bounded number of bit flips or as replacement of the instruction's effect, because that is the weakest assumption about what an attacker can achieve and R-16-008f's acceptance criterion forbids making the theorem easier. A reader who would narrow it should note that the scope test below does not depend on the choice: its witness uses `skip`, which is the half of R-16-008f's phrase that admits no reading at all.

## 5. Fault-free, in-model faulted, and excluded

**The first two classes partition the derivations, and the third is what the rules do not generate.** Every execution the rules derive carries either no `FAULT` or exactly one, because `FAULT` fires only at budget `1` and leaves budget `0`, so *fault-free* and *in-model faulted* are exhaustive and disjoint over the derivations by that arithmetic and by nothing else. *Excluded* is the complement of the relation's range rather than a third kind of derivation: an excluded member has no derivation at all, which is why each is named by the physical scenario it is and by the entry that books it. The machine spends most of its time outside any protected region, where this classification says nothing at all.

**Fault-free.** Every transition of the activation is `STEP`. The budget is unspent. This is the curated Sail model's own semantics with nothing added, which is why the relation is a perturbation and not a second model.

**In-model faulted.** Exactly one transition is `FAULT`, at a step whose `PC` is in `R`, within one activation. This is the set R-16-008f's theorem quantifies over, and it contains the runs that never leave `R`: a `skip` of a loop-counter increment leaves the continuation circling inside the region at budget `0`, a run `STEP` extends without end. Such a run is in the model rather than excluded from it, which is the reading R-16-008f's acceptance criterion forces, and the conclusion holds of it: no configuration of it commits the acceptance token at all. What ends it on the machine is not this relation. A wedged or runaway core is the layered watchdogs' case (R-16-005, R-16-006, the tier R-16-008b names as reaching it), and what a bite costs the decision the region carried is R-17-058b's evidence question in the way a second fault is.

**Excluded.** Everything else, and each member is named here rather than left as a remainder.

| Excluded | Why it is outside | Where it is booked |
| --- | --- | --- |
| Two or more faults in one activation | no derivation at budget `0` | R-17-058b, as evidence rather than theorem, with region brevity, the doubled comparison, the RoT attempt counter, excursion sensors and the watchdog tier named as the division of labour |
| Any fault at a step whose `PC` is outside `R`, a called helper and the code the region returns into included | `FAULT` requires `in_region(s)` | R-16-008f's own acceptance clause, which names any fault outside a protected region among what the model excludes, and the opening sentence of R-17-058b that carries it |
| The transient datapath strike: a wrong arithmetic result, a flipped bit in the merged register file including the signature register, a corrupted operand delivered by a load, a corrupted value on a store's write path, a flipped capability tag, or a combinational strike on the fetch path's capability, alignment, or PMA checks | the perturbation applies to the fetched instruction word alone, so none of these is in the relation's range | R-16-008b and R-17-058b (explicitly enumerating combinational fetch-path check strikes within the transient datapath strike class); unclaimed at consumer grade, its answer deployment-graded software redundancy |
| A fault in stored state | corrected by the pervasive ECC, and a fail-stop event where uncorrectable | R-16-008b, R-15-175, R-15-177, which is a different case from the line above and is reached by a mechanism rather than left open |
| A fault on the fetch path's own checks, making a failing capability, alignment or PMA check pass | the perturbation applies to `w` after `fetch()` has returned `F_Base`, so the checks in [postlude/fetch.sail](../../model/model/postlude/fetch.sail) are the fault-free ones | R-16-008b and R-17-058b, enumerated explicitly as combinational fetch-path check strikes within the transient datapath strike class |
| A fault below the canonical instruction level, in the resident dictionary-format image (R-15-036a, R-15-036b), including a header escape-start bit strike perturbing two slots at once | the relation perturbs the 32-bit canonical word the Sail model fetches, and the dictionary encoding sits below that level | the named R-16-008f first-silicon bring-up characterization (recorded alongside physical silicon faithfulness in R-17-058b), which establishes the physical-to-canonical correspondence |

The two rows about the datapath are separated on purpose, because they are the two cases a reader most often merges. A fault in **stored** state is R-16-008b's, it has a mechanism, and the mechanism is ECC with a fail-stop where correction fails. A **transient** strike in the datapath itself has no mechanism here at all: R-16-008b enumerates the mechanism catching each injection, states that the transient datapath strike—explicitly including combinational fetch-path check strikes on capability, alignment, or PMA logic alongside arithmetic datapath strikes—is reached by neither of the two detector positions, and books it at R-17-058b, where it is unclaimed at consumer grade. Neither is in this relation, and the reason differs in each case.

The fetch-path row above them is a member of that same transient datapath strike class rather than a fourth class: a strike on a capability, alignment or PMA check is a combinational transient strike in the fetch unit's own logic, so it is booked where the transient strike is booked (R-16-008b and R-17-058b), and it is listed on its own line because what puts it outside *this relation* is the relation's post-`fetch()` site choice rather than the absence of a mechanism.

## 6. Witnesses

The witnesses are stated over one concrete conforming region instance, `W`, a credential comparison at the RoT gate carrying every element R-16-008c's construction sentence names: per-block CFG signature folds including not-taken connectors, data-reduction completeness via a collision-resistant 64-bit keyed absorb over the credential words, a doubled comparison with the signature check between the two, and a 64-bit compose-time acceptance token `T` unconstructible by any single instruction of the frozen profile from an immediate or from live non-comparison register state. Mnemonics and the `c12`/`c13`/`c14` capability spelling are [the differential corpus](../assurance/differential-corpus.md)'s, as its purecap programs write them (keeping data capabilities distinct from `a0` under the merged register file); `s1`, `s2`, `a0` and the temporaries are ABI register names, named here for their roles rather than cited from a program.

```
    ; Conforming region W: entry a_in = 0x80000100, instructions in [0x80000100, 0x800001e8),
    ; read-only .L_consts literal pool in [0x80000200, 0x80000258), exit a_out = 0x80000260.
    ; s1 is the 64-bit signature register, s2 the 64-bit keyed-absorb comparison state,
    ; a0 the 64-bit token register. c12 and c13 authorize the stored (A0, A1) and presented
    ; (B0, B1) credentials, two 64-bit words each. c14 is derived from PCC to .L_consts.
    ; Entry conditions: s1 = 0, s2 != M_cmp, a0 != T, PCC authorizes [a_in, a_out).
    ; Compose-time 64-bit constants in .L_consts:
    ;   0(c14) K1    = 0x517cc1b727220a95    8(c14) K2    = 0x3b9aca002f6e2b1d
    ;  16(c14) K5    = 0x7f4a7c159e3779b9   24(c14) K3    = 0x243f6a8885a308d3
    ;  32(c14) S_ok  = 0x6ae60bb7084c2188   40(c14) S_end = 0x31931d2a13d850e2
    ;  48(c14) M_cmp = 0x589af74de06499f7   56(c14) K_iv  = 0x6a09e667f3bcc908
    ;  64(c14) P1    = 0x9e3779b97f4a7c15   72(c14) K4    = 0x13198a2e03707344
    ;  80(c14) K6    = 0xa4093822299f31d0
    ; Accepting token: T = S_end xor M_cmp = 0x6909ea67f3bcc915 (unreachable by any single
    ; 12-bit signed immediate, 20-bit upper-shifted immediate, or non-comparison register).

B1:  0x80000100  auipcc c14, 0          ; derive read-only capability to PCC base
     0x80000104  cincoffsetimm c14, c14, 0x100  ; c14 -> .L_consts (0x80000200)
     0x80000108  ld   t1, 0(c14)        ; load K1
     0x8000010c  xor  s1, s1, t1        ; B1 folds its constant
     0x80000110  ld   s2, 48(c14)       ; s2 = M_cmp
     0x80000114  ld   t6, 64(c14)       ; t6 = P1 (odd 64-bit mixing multiplier)
     0x80000118  ld   t3, 56(c14)       ; t3 = K_iv
     0x8000011c  ld   t0, 0(c13)        ; presented word 0 (B0)
     0x80000120  xor  t3, t3, t0
     0x80000124  mul  t3, t3, t6
     0x80000128  srli t2, t3, 32
     0x8000012c  xor  t3, t3, t2
     0x80000130  ld   t1, 8(c13)        ; presented word 1 (B1)
     0x80000134  xor  t3, t3, t1
     0x80000138  mul  t3, t3, t6
     0x8000013c  srli t2, t3, 32
     0x80000140  xor  t3, t3, t2        ; t3 = h_K(B0, B1)
     0x80000144  xor  s2, s2, t3        ; s2 = M_cmp xor h_K(B0, B1)
     0x80000148  ld   t6, 64(c14)       ; reload P1 independently
     0x8000014c  ld   t3, 56(c14)       ; reset t3 = K_iv (overwrites h_K(B0, B1))
     0x80000150  ld   t4, 0(c12)        ; stored word 0 (A0)
     0x80000154  xor  t3, t3, t4
     0x80000158  mul  t3, t3, t6
     0x8000015c  srli t2, t3, 32
     0x80000160  xor  t3, t3, t2
     0x80000164  ld   t5, 8(c12)        ; stored word 1 (A1)
     0x80000168  xor  t3, t3, t5
     0x8000016c  mul  t3, t3, t6
     0x80000170  srli t2, t3, 32
     0x80000174  xor  t3, t3, t2        ; t3 = h_K(A0, A1)
     0x80000178  xor  s2, s2, t3        ; s2 = M_cmp xor h_K(B0, B1) xor h_K(A0, A1)
     0x8000017c  ld   t0, 48(c14)       ; load M_cmp
     0x80000180  xor  t0, s2, t0        ; t0 = 0 iff s2 == M_cmp (clears M_cmp from t0)
     0x80000184  beqz t0, B2            ; comparison, first of the two
B1': 0x80000188  ld   t1, 72(c14)       ; load K4
     0x8000018c  xor  s1, s1, t1        ; the not-taken connector folds too
     0x80000190  j    B3
B2:  0x80000194  ld   t1, 8(c14)        ; load K2
     0x80000198  xor  s1, s1, t1        ; B2 folds its constant -> S_ok
     0x8000019c  ld   t3, 32(c14)       ; load S_ok
     0x800001a0  xor  t3, s1, t3        ; the signature check between the two
     0x800001a4  bnez t3, B3
B2': 0x800001a8  ld   t1, 16(c14)       ; load K5
     0x800001ac  xor  s1, s1, t1        ; the not-taken connector folds too
     0x800001b0  ld   t0, 48(c14)       ; load M_cmp
     0x800001b4  xor  t0, s2, t0        ; t0 = 0 iff s2 == M_cmp (clears M_cmp from t0)
     0x800001b8  beqz t0, B4            ; comparison, second of the two
     0x800001bc  j    B3
B4:  0x800001c0  ld   t1, 24(c14)       ; load K3
     0x800001c4  xor  s1, s1, t1        ; B4 folds its constant -> S_end
     0x800001c8  ld   t4, 40(c14)       ; load S_end
     0x800001cc  xor  t4, s1, t4        ; the exit comparison against the graph (clears S_end)
     0x800001d0  bnez t4, B3
     0x800001d4  xor  a0, s1, s2        ; a0 = S_end xor M_cmp = T (64-bit unforgeable token)
     0x800001d8  j    a_out
B3:  0x800001dc  ld   t1, 80(c14)       ; load K6
     0x800001e0  xor  s1, s1, t1        ; the fail-stop entry folds too
     0x800001e4  ...                    ; the fail-stop class R-17-030n names
```

`W` meets R-16-008c's construction sentence clause by clause: *each* basic block folds a compose-time constant into `s1` (connectors `B1'` and `B2'` included); the exit compares `s1` against `S_end` and a mismatch raises the fail-stop class; the credential reduction absorbs every input word through a collision-resistant keyed absorb `h_K` into `s2` against `M_cmp` (`s2` reaching `M_cmp` iff `h_K(B0, B1) = h_K(A0, A1)`); the comparison is performed twice (`0x80000184` and `0x800001b8`) with the signature check (`0x800001a0`) between the two; and acceptance is the 64-bit token `T = S_end xor M_cmp = 0x6909ea67f3bcc915`, which neither a single instruction with a 12-bit signed immediate or 20-bit upper-shifted immediate nor a single operation over live non-comparison register state can form (`t4` and `t0` having cleared `S_end` and `M_cmp` before `0x800001d4`, and `s1` holding `S_end != T` while `s2` holds `M_cmp != T`). The accepting path is `B1`, `B2`, `B2'`, `B4`, and its folds are `K1`, `K2`, `K5`, `K3`; `B1'` and `B3` fold on the rejecting path, which reaches no comparison and no exit.

**Witness N, fault-free.** The budget is unspent, so every transition is `STEP` and the trace is the model's own. With `(A0, A1) = (B0, B1)`, `h_K(B0, B1) = h_K(A0, A1)` so `s2 = M_cmp`, and `t0 = 0` at `0x80000184`; the run takes `B2`, falls through `B2'` and takes `B4`, and `s1` holds `K1 = 0x517cc1b727220a95` after `0x8000010c`, `S_ok = 0x6ae60bb7084c2188` after `0x80000198`, `0x15ac77a2967b5831` after `0x800001ac`, and `S_end = 0x31931d2a13d850e2` after `0x800001c4`. Both signature checks (`0x800001a0` and `0x800001cc`) and both credential comparisons (`0x80000184` and `0x800001b8`) pass, and `0x800001d4` commits `a0 = S_end xor M_cmp = 0x6909ea67f3bcc915 = T`. The activation ends at `a_out` with the token produced and the decision reached correctly.

**Witness F, one fault, token withheld.** Budget `1` is spent by `FAULT` with `f = skip` at the step whose `PC` is `0x80000198`, which is in `R`. `s1` therefore stays at `K1 = 0x517cc1b727220a95` rather than reaching `S_ok`. At `0x800001a0` the signature check computes `t3 = K1 xor S_ok = K2 = 0x3b9aca002f6e2b1d`, which is not zero, so `0x800001a4` transfers to `B3` and the activation ends in the fail-stop class. Every later transition is `STEP`, the budget being `0`. `a0` is untouched and is not `T` by the entry condition, so the token is withheld. This is a member of the relation, and the only member's-eye difference from witness N is the one transition that used the budget.

**Witness C, one fault, the corruption arm.** Budget `1` is spent by `FAULT` with `f = corrupt(w')` at the step whose `PC` is `0x80000198`, which is in `R`, for a `w'` the frozen profile allocates no encoding to. The perturbation is taken at the `F_Base` arm's binding, so `instbits` moves with it: `ext_decode(w')` reaches `ILLEGAL` through the wildcard `encdec` clause, `execute` returns `Illegal_Instruction()`, and `try_step` hands `zero_extend(instbits)` to `handle_exception`, so `mtval` carries `w'` and not the word the image holds at `0x80000198`. That is the difference the site choice in [§2](#2-the-subject-the-exact-sail-definitions-the-relation-perturbs) buys, and it is architectural rather than cosmetic, `mtval` being a present-bank CSR. The trap installs `MTCC` through `nextPCC` and the handler's address through `set_next_pc`, so the faulted step itself commits a `PC` outside `R` and the activation ends there by the second of its two exit routes, with `a0` untouched and the token withheld. An allocated `w'` exercises the same arm without the trap: `addi s1, s1, 1` leaves `s1 = 0x517cc1b727220a96`, so `0x800001a0` computes `t3 = 0x3b9aca002f6e2b1e != 0`, `0x800001a4` transfers to `B3`, and the activation ends in the fail-stop class as witness F's does.

**Witness X, two faults, a non-member.** Take witness F's fault at `0x80000198` and add a second at `0x800001a0`, replacing `xor t3, s1, t3` with `xor t3, s1, s1` so that `t3` is zero and the run falls through `B2'` into `B4`. There is no derivation: after the first `FAULT` the configuration carries budget `0`, and `FAULT` requires budget `1` in its premise, so the second perturbation is generated by no rule. That is the clause rejecting it, and naming it is the point. Whether the excluded run reaches the token is R-17-058b's evidence question and is not this relation's business.

**A fault outside `R`.** A perturbation at a step whose `PC` is `a_out` or beyond, or inside a helper the region calls, fails `FAULT`'s `in_region(s)` premise and has no derivation either. The entry conditions above are the visible consequence: `s1 = 0`, `s2 != M_cmp` and `a0 != T` at `a_in` are assumptions about state this relation does not govern, and a fault that established them is outside the model rather than silently inside the fault-free class.

**Refuting witness `W_or` (naive word-wise OR accumulator).** To see why R-16-008c's data-reduction completeness obligation is load-bearing independently of token width, replace `W`'s keyed absorb (`0x80000110`–`0x80000180`) with a naive word-wise difference accumulator while retaining the 64-bit CFG constants (`K1..K6`, `S_ok`, `S_end`), doubled comparison and 64-bit token `T = S_end`:

```
    ; Refuting witness W_or: naive word-wise OR reduction (s2 = 0 on match, T = S_end).
    0x80000310  li   s2, 0              ; accepting value installed up front
    0x80000314  ld   t0, 0(c12)         ; stored word 0
    0x80000318  ld   t1, 0(c13)         ; presented word 0
    0x8000031c  xor  t2, t0, t1
    0x80000320  or   s2, s2, t2         ; word 0 of the difference
    0x80000324  ld   t0, 8(c12)         ; stored word 1
    0x80000328  ld   t1, 8(c13)         ; presented word 1
    0x8000032c  xor  t2, t0, t1
    0x80000330  or   s2, s2, t2         ; word 1 of the difference
    0x80000334  beqz s2, B2             ; comparison, first of the two
```

`W_or` satisfies CFG folding, doubled comparison, intermediate signature check, and 64-bit token unforgeability, yet fails R-16-008c's data-reduction completeness obligation as shown in [§7](#7-the-scope-test-and-what-it-returns).

## 7. The scope test, and what it returns

R-16-008f's conclusion is that *"for every in-model fault of a protected region, either the region's committed architectural effect equals the fault-free execution's effect, or the acceptance token is withheld, so the decision the sequence reaches is withheld rather than reached wrongly"*. The scope test checks both the epilogue boundary and the data-reduction paths of all three R-16-008c sequence classes against this relation, without inferring a harmless-fault exception or excluding any comparison or token step.

**Epilogue boundary reconciliation.** R-17-058b's second limit says a fault inside the compare-and-fail-stop epilogue is not caught *by that epilogue*, and R-16-008f's exclusions do not remove the epilogue from `R`. Under `W`, both reconcile: (1) a single perturbation of either comparison (`0x80000184` or `0x800001b8`) leaves the other standing, with `B2`'s signature check (`0x800001a0`) confirming `B1 -> B2`; (2) a single perturbation of any signature fold moves `s1` off `S_ok` or `S_end` and diverts to `B3` (or withholds `T`); and (3) at the token-computation step (`0x800001d4`, `xor a0, s1, s2`), `R-16-008c`'s **token unforgeability** obligation blocks single-instruction immediate synthesis (`addi`/`lui`) and synthesis from live non-comparison register state, while a `corrupt(w')` that merely re-encodes `s1 xor s2` on a matching credential preserves the fault-free committed architectural effect under R-16-008f's effective-fault disjunction. Multi-fault epilogue strikes remain outside the model at R-17-058b.

**Why data-reduction completeness is load-bearing (refuting test on `W_or`).** On the refuting witness `W_or`, take `FAULT` with `f = skip` at `PC = 0x80000320`, which is in `R`, and let the presented credential differ from the stored one in word 0 alone while matching in word 1:

| Step | Effect under the fault | Effect under no fault |
| --- | --- | --- |
| `0x80000320` | skipped: word 0's difference never enters `s2` | `s2` takes word 0's difference, which is non-zero |
| `0x80000330` | `s2` takes word 1's difference, which is zero | `s2` stays non-zero |
| `0x80000334` | `s2` is zero, so the run takes `B2` | the run takes `B1'` and `B3` |
| `B2`, `B2'`, `B4` folds | folded correctly; budget is `0` and every later transition is `STEP` | n/a |
| `B2`, `B4` signature checks | both pass: `B1 -> B2 -> B2' -> B4` is a legal CFG path and `s1` reaches `S_end` | n/a |
| token commit | `a0 = S_end xor 0 = T` (wrong credential accepted) | n/a |

One in-region `skip`, in budget, with no datapath strike and no register bit flip, produces `T` for a mismatching credential because a running control-flow signature proves only that the path is legal in the CFG, not that the path was warranted by the data. R-16-008c closes this gap by mandating **data-reduction completeness**: omitting or corrupting any single in-region instruction cannot leave the compared value at its accepting point. On the conforming witness `W`, skipping or corrupting any load or mixing step in `h_K(B0, B1)` or `h_K(A0, A1)`—or skipping either XOR into `s2`—leaves `h_K(B0, B1) != h_K(A0, A1)` (up to 64-bit collision resistance of the keyed absorb) or omits `M_cmp`, so `s2 != M_cmp` and one of the two comparisons (`0x80000184` or `0x800001b8`) diverts to `B3`; moreover, `h_K(B0, B1)` is overwritten before `h_K(A0, A1)` runs, `P1` is reloaded independently, and `M_cmp` is cleared from `t0` before the comparisons pass, so no single `corrupt(mv)` can copy the target value across halves.

**Data-reduction completeness readings across all three R-16-008c sequence classes.** Every R-16-008c sequence class satisfies data-reduction completeness and token unforgeability within its own region boundary:

1. **Measured-boot chain's per-stage verify-then-transfer.** *Boundary:* `a_in` is the stage verification prologue; the control transfer to the verified stage is the last in-region step, and `a_out` is the entry address of the target stage (so the transfer itself is in-region and any single fault on it is in-model; any called hash or signature helper must be inlined or closed inside `R` under `PCC`). *Completeness reading:* the verification sequentially absorbs every word of the stage payload (and its measurement extension) into a cryptographic digest and verifies the stage signature against the expected root/manifest key. Because every payload word nonlinearly updates a multi-bit hash/sponge chain toward an expected non-trivial digest (never a zero-initialized OR difference), skipping or corrupting a single absorb, round, or load step shifts the computed digest away from the expected digest by preimage/collision resistance. The digest/signature check reduces to a multi-bit unforgeable comparison state and token (never a single-bit flag) verified twice with the CFG signature check between the two checks, and the control transfer to `a_out` consumes both the completed CFG signature and comparison token so no single fault can bypass verification and reach `a_out` with a valid accepting state.
2. **Credential comparison at the RoT gate.** *Boundary:* `a_in` is the comparison prologue; computation of the 64-bit acceptance token (`a0 = T`) is the last in-region work, and `a_out` is where the gate's decision is consumed. *Completeness reading:* exhibited by `W` versus `W_or` above—every credential word is folded through a collision-resistant keyed absorb against a non-trivial 64-bit target `M_cmp` before the doubled comparison and intermediate signature check.
3. **Lifecycle transition over one-way fuse state.** *Boundary:* `a_in` is the transition guard; the irreversible store committing the new fuse state to the RoT OTP window ([sys/rot.sail](../../model/model/sys/rot.sail)) is the **last in-region step**, and `a_out` is the instruction immediately after that store (keeping the irreversible commit inside `R` rather than beyond `a_out`). *Completeness reading:* the guard must fold every input that authorizes the burn—the current OTP lifecycle/fuse-word reads, the requested target state, the acyclic `lifecycle_admits` edge-admissibility check, and every word of the transition authorization/credential—into a single collision-resistant keyed reduction against a non-trivial multi-bit target (never separate boolean flags or an OR-accumulated check), checked twice with the CFG signature check between the two checks before reaching the fuse-commit store. Any single skipped or corrupted read, fold, or edge check moves the reduced state off its accepting point and diverts to `B3` before the store is reached; a single fault on the fuse-commit store itself either suppresses the store (`skip`) or traps (`corrupt`), withholding the post-commit acceptance token in either case.

## 8. What this model does not establish

**Sampled injections and satisfiability witnesses do not establish detection.** They refute. A campaign that injects faults at a sample of positions, and a solver run that finds no satisfying assignment within a bound, each establish that the positions tried did not defeat the construction. R-16-008f's acceptance criterion requires the proof to quantify over every in-model fault of each protected region rather than sampling them, and the gap between the two is the whole reason the relation is written down: a quantifier over the index set of the rules above is a different object from a set of trials, and no number of trials converts into one. Where a campaign finds a fault that violates the effective-fault disjunction it is a counterexample and decides the matter; where it finds none it decides nothing.

**No harmless-fault exception is taken, and none may be read into this document.** The relation admits every single perturbation at every in-region step, including perturbations that change nothing architecturally (such as replacing an instruction with an equivalent encoding of the same architectural effect). R-16-008f answers this not by excluding effect-preserving perturbations from the model, but by proving the **effective-fault disjunction**: for every in-model fault of a protected region, either the region's committed architectural effect equals the fault-free execution's effect, or the acceptance token is withheld, so the decision the sequence reaches is never reached wrongly.

**No comparison or token step is excluded.** The compare-and-fail-stop epilogue is in-region and in-model, and `FAULT` applies at every one of its steps. R-17-058b's limit that a fault inside that epilogue is not caught *by that epilogue* is a statement about which mechanism catches it, not a licence to remove those steps from the model, and this document does not remove them; single-instruction immediate token synthesis is closed by R-16-008c's token-unforgeability obligation while multi-fault epilogue strikes remain outside the model at R-17-058b.

**The other limits stay where they are booked.** Under R-17-058b, single-fault legal-path divergences are closed in-model by R-16-008c's data-reduction completeness obligation, while a second fault in one activation or a multi-fault-induced divergence landing the signature register on its predicted value sits outside the model as coverage evidence (absorbed by region brevity, doubled comparison, RoT attempt counters, excursion sensors and the watchdog tier). The safe-error oracle, the acceptance token's trip-or-no-trip outcome being itself observable, is R-17-058b's and is bounded at the credential gate by the RoT attempt counter and elsewhere by the restart a trip costs. The lockstep decision for the S-class core alone is R-16-008d's. The combined adversary who probes and faults in one execution is R-17-058c's, and no conjunction of this axiom with R-15-053a's covers him until R-17-058d's reduction checks on the artifact.

## 9. The silicon assumption, accepted boundaries, and downstream obligations

**Silicon-axiom status and named first-silicon characterization.** R-16-008f makes this model *"an axiom about the silicon in the R-06-011 sense"*. Nothing in this repository proves that physical silicon lies inside the single-fault canonical transition relation above, and outside it no row, mode, or requirement states a detection *probability* or claims a mode above *detected* (R-17-058b). Both R-16-008f and R-17-058b therefore book physical silicon faithfulness—explicitly including the correspondence between physical faults on resident dictionary-format bundles (R-15-036a, R-15-036b, where a single bundle header escape-start bit strike can perturb two canonical slots at once) and this canonical-level single-instruction relation—to the **named R-16-008f first-silicon bring-up characterization** and independent review rather than an assumed fit, taking the same shape R-15-053a takes for leakage (rehearsed on FPGA to validate the harness, never the silicon axiom, and executed at first silicon).

**Accepted independent-review boundaries.** The independent review separated the region-boundary review from the corruption-relation review, reconciled their witnesses (`N`, `F`, `C`, `X`, and `W_or`), and settled three boundaries carried into the register:

1. **The corruption relation stands at arbitrary replacement of the fetched 32-bit word.** That is the weakest assumption about what an attacker achieves, R-16-008f forbids making the theorem easier, and the refuting scope test does not rest on the choice, its witness being a `skip`.
2. **The region predicate stands on `PCC` as well as on `PC`.** The profile's single physical address space is shared, so an address alone does not name a region, and the `PCC` conjunct is also what ends an activation at a trap, which is the second of the two exit routes [witness C](#6-witnesses) exercises.
3. **Scope counterexamples are answered by R-16-008c construction obligations rather than narrowing the fault model.** Data-reduction completeness and 64-bit token unforgeability close single-fault omission and epilogue-synthesis counterexamples inside the construction, while R-16-008f's effective-fault disjunction states the theorem cleanly over all in-model faults without carving out effect-preserving encodings.

**Register-settled boundaries and downstream owners.** All seven scope and boundary findings surfaced during the relation's review are resolved across `R-16-008b`, `R-16-008c`, `R-16-008f`, and `R-17-058b`: data-reduction completeness (`R-16-008c`), token unforgeability (`R-16-008c`), effective-fault disjunction (`R-16-008f`), dictionary-bundle physical-to-canonical correspondence (`R-16-008f`, `R-17-058b`), the named `R-16-008f` first-silicon bring-up characterization (`R-16-008f`, `R-17-058b`), explicit enumeration of combinational fetch-path check strikes within the transient datapath strike class (`R-16-008b`, `R-17-058b`), and narrowing of `R-17-058b`'s signature-collision residual to multi-fault-induced divergences. With this relation accepted, downstream obligations remain at their assigned owners:

- **U-19** ([the unassigned proof map](../assurance/unassigned-proof-map.md)) owns authoring the signature-and-token construction model and the detection theorem quantifying over every in-model fault of this accepted relation under R-16-008f's effective-fault disjunction.
- **Toolchain, admission, and ROM tapeout** own compiler-emitted signature instrumentation, the binary-level check at `artifact-admission` (R-05-029), and fixed ROM measurement at tapeout (R-09-002).
- **The post-M10 combined-adversary cell** owns the R-17-058d reduction over accepted R-15-053a and R-16-008f premises alongside the crypto core's ineffective-fault countermeasure.
- **First-silicon bring-up characterization** owns discharging the named R-16-008f physical faithfulness and dictionary-bundle correspondence evidence (`R-17-058b`).
