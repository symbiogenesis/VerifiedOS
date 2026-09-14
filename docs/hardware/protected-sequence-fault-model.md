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

**It is not a second transcription of the instruction set.** The relation perturbs the curated Sail model's own step function at two named points and reuses every definition below those points. Anything this document restated would be a second holder of a fact [model/](../../model/) owns.

## 2. The subject: the exact Sail definitions the relation perturbs

The subject is one function. `try_step(step_no : nat, exit_wait : bool) -> bool` in [postlude/step.sail](../../model/model/postlude/step.sail) is the model's fetch-decode-execute step, and the relation below is a perturbation of that function at two points inside the `HART_ACTIVE()` arm it dispatches to.

| Definition | Where | What this relation does with it |
| --- | --- | --- |
| `try_step` | [postlude/step.sail](../../model/model/postlude/step.sail) | the step the relation perturbs; one call is one transition |
| `hart_state : HartState` | [postlude/step.sail](../../model/model/postlude/step.sail), the type in [postlude/step_common.sail](../../model/model/postlude/step_common.sail) | the relation is defined on the `HART_ACTIVE()` arm; the waiting arm is unperturbed |
| `run_hart_active` | [postlude/step.sail](../../model/model/postlude/step.sail) | carries both perturbation points |
| `fetch()`, `FetchResult`, the `F_Base(w : word)` arm | [postlude/fetch.sail](../../model/model/postlude/fetch.sail), [postlude/step_common.sail](../../model/model/postlude/step_common.sail) | supplies `w`, the fetched 32-bit word; the perturbation applies to `w` after `fetch()` returns and the fetch's own checks have passed |
| `ext_decode(w)` | [postlude/decode_ext.sail](../../model/model/postlude/decode_ext.sail), which is the `encdec` mapping | consumes the perturbed word unchanged |
| `execute : instruction -> ExecutionResult` and the arms of `ExecutionResult` | [sys/insts_begin.sail](../../model/model/sys/insts_begin.sail) | consumes the decoded instruction unchanged; the `Retire_Success()` arm is what the skip perturbation substitutes |
| `nextPC = PC + 4`, `set_next_pc` | [postlude/step.sail](../../model/model/postlude/step.sail), [core/pc_access.sail](../../model/model/core/pc_access.sail) | unperturbed; the sequential advance is installed before `execute` runs, so a perturbed control transfer redirects exactly as a genuine one does |
| `tick_pc()`, `PC`, `nextPC`, `PCC`, `nextPCC` | [core/pc_access.sail](../../model/model/core/pc_access.sail), [core/regs.sail](../../model/model/core/regs.sail), [core/cap_regs.sail](../../model/model/core/cap_regs.sail) | the commit point; a transition of this relation is a call of `try_step` that reaches it |

Write `Sigma` for the model's architectural state: the merged register file, `PC`, `nextPC`, `PCC`, `nextPCC`, `hart_state`, the present CSR bank of [the profile's §5.1](isa-profile.md#51-present), and memory with its tag plane. Write `step(s)` for the state after one call `try_step(n, true)` from `s`, and `w(s)` for the word `fetch()` returns in its `F_Base` arm when the fetch succeeds. `step` is the fault-free transition, and it is the model's, not this document's.

Two perturbations are defined, each at a named point of `run_hart_active`.

- **`corrupt(w')`**, for a word `w' : bits(32)`: the step proceeds as `step` except that `ext_decode(w')` is evaluated where the model evaluates `ext_decode(w(s))`. Everything downstream is the model's own: the decode of `w'` is `encdec`'s, an unallocated `w'` reaches `ILLEGAL` through the wildcard clause and traps with the whole word in `mtval` as [the fetch's own note](../../model/model/postlude/fetch.sail) records, a `w'` whose execution raises a capability or address fault raises the model's fault, and a `w'` that is a control transfer redirects through `set_next_pc`.
- **`skip`**: the step proceeds as `step` except that `execute` is not applied and the `Step_Execute` payload is `Retire_Success()`. The sequential advance `nextPC = PC + 4` has already been installed and `nextPCC` is untouched, so `tick_pc()` commits the next sequential instruction and no other architectural state moves.

As a transition on `Sigma`, `skip` coincides with `corrupt` at the canonical no-op encoding, because a no-op's execution also changes nothing but the committed PC. Both are named because R-16-008f names both and because their physical origins differ: an instruction-skip and a corrupted instruction word are distinct injection mechanisms on the die, and whether the coincidence holds there is a question for the characterization named at the end of this document, not for the relation.

**The perturbation is applied to the fetched word and to nothing else.** That single sentence is the fault domain, and the exclusions below are its consequences rather than carve-outs added to it.

## 3. Protected regions and activations

A **protected region** `R` is a finite set of instruction addresses with a distinguished entry `a_in` and exit `a_out`, closed under the control-flow graph the compose-time instrumentation predicts its exit signature from, and reachable under one code capability. Membership is a property of the emitted image, fixed at compose time, and is not a runtime predicate the machine evaluates: R-16-008e forbids any ISA surface that could evaluate one.

The **region predicate** is taken on the committed program counter at the fetch point: `in_region(s)` holds when `PC(s)` is in `R` and `PCC(s)` is the region's code capability. Taking it on `PCC` as well as on `PC` is what makes it a statement about the region rather than about an address, since the profile's single physical address space is shared and the authority is what distinguishes one image's region from another's.

An **activation** is one traversal of `R`: a maximal run of transitions beginning at the step whose `PC` is `a_in` and ending at the first later step whose committed `PC` is `a_out`, or whose committed `PC` leaves `R` by any other route. A region entered twice is two activations, and the fault budget is per activation because R-16-008f's phrase is *"per protected region per activation"*.

R-16-008c's three sequence classes are the regions this model is about, and each is an ordinary instruction sequence on a composed hart:

| Class | What bounds the region | Why it needs no special surface |
| --- | --- | --- |
| The measured-boot chain's per-stage verify-then-transfer | entry at the stage's verification prologue, exit at the transfer of control to the verified stage | ordinary loads, arithmetic and a control transfer |
| The credential comparison at the RoT gate | entry at the comparison's prologue, exit at the point the gate's decision is consumed | the RoT's fuse bank, entropy root, counter file and watchdog are reached by ordinary loads and stores through capabilities, with no instruction, no access type, no CSR and nothing on the decode surface ([sys/rot.sail](../../model/model/sys/rot.sail)) |
| The lifecycle transition over one-way fuse state | entry at the transition's guard, exit at the point the new state is committed | the same fuse window, read and written as memory |

The split R-16-008c takes between a sequence that passes admission and one that lives in the boot ROM decides **where the theorem is checked**, on the final binary in the first case and fixed at tapeout in the second. It does not decide where the region is, and this relation is the same relation in both cases.

## 4. The relation

A faulted execution of one activation is indexed by a **budget** `b`, which is `1` at `a_in` and is never replenished within the activation. Two rules generate the relation on configurations `(s, b)`.

```
                                                        in_region(s)      f in { skip } U { corrupt(w') : w' in bits(32) }
  ------------------------------- (STEP)               ------------------------------------------------------------------ (FAULT)
   (s, b)  -->  (step(s), b)                                        (s, 1)  -->  (step_f(s), 0)
```

An **execution of the activation** is a finite derivation from `(s_in, 1)`, where `s_in` is a state with `PC = a_in`, to the first configuration whose committed `PC` is outside `R`. The relation is the set of those derivations.

Four properties of the statement are the ones the acceptance predicate asks about, and each is a property of the rules rather than a remark beside them.

- **A second fault in one activation is rejected by the absence of a rule.** `FAULT` requires budget `1` and produces budget `0`, and there is no rule with budget `0` in its premise other than `STEP`. A run carrying two perturbations therefore has no derivation. It is not excluded by a side condition that a later reading could soften, and it is not excluded by a predicate over the run: it is not generated.
- **An out-of-region fault is rejected the same way.** `FAULT` carries `in_region(s)` as a premise, so a perturbation at a step whose `PC` lies outside `R` has no derivation either. This reaches the case a reader is most likely to lose: a region that calls out to a helper spends its steps at addresses the region's control-flow graph does not contain, and a fault there is outside the model. Whether a given helper is inside `R` is a compose-time fact about the emitted image, and a construction that leaves the decision's work outside the region it protects is not covered by the theorem however short the region reads.
- **The fault index is finite and decidable.** For one activation of one region instance the index is the position of the faulted step in the run, crossed with the alternatives at that position: `skip`, or `corrupt(w')` for each of the 2^32 words. A run of a region instance has a bounded number of steps, so *every in-model fault of each protected region* is a quantification over a set the rules exhibit the shape of, which is what R-16-008f's acceptance criterion asks of the statement when it distinguishes quantifying from sampling. Nothing here says the quantification is cheap; it says it is a quantification.
- **The relation is the strongest hypothesis on the adversary that R-16-008f's words admit, and one choice in it is a judgment the register does not make.** R-16-008f says *"skipped or corrupted"* and stops. This document reads *corrupted* as **arbitrary replacement of the fetched word**, rather than as a bounded number of bit flips or as replacement of the instruction's effect, because that is the weakest assumption about what an attacker can achieve and R-16-008f's acceptance criterion forbids making the theorem easier. A reader who would narrow it should note that the scope test below does not depend on the choice: its witness uses `skip`, which is the half of R-16-008f's phrase that admits no reading at all.

## 5. Fault-free, in-model faulted, and excluded

Every execution of the machine falls in exactly one of three classes, and the middle one is the model.

**Fault-free.** Every transition of the activation is `STEP`. The budget is unspent. This is the curated Sail model's own semantics with nothing added, which is why the relation is a perturbation and not a second model.

**In-model faulted.** Exactly one transition is `FAULT`, at a step whose `PC` is in `R`, within one activation. This is the set R-16-008f's theorem quantifies over.

**Excluded.** Everything else, and each member is named here rather than left as a remainder.

| Excluded | Why it is outside | Where it is booked |
| --- | --- | --- |
| Two or more faults in one activation | no derivation at budget `0` | R-17-058b, as evidence rather than theorem, with region brevity, the doubled comparison, the RoT attempt counter and the watchdog tier named as the division of labour |
| Any fault at a step whose `PC` is outside `R`, a called helper and the code the region returns into included | `FAULT` requires `in_region(s)` | R-17-058b's first limit |
| The transient datapath strike: a wrong arithmetic result, a flipped bit in the merged register file including the signature register, a corrupted operand delivered by a load, a corrupted value on a store's write path, a flipped capability tag | the perturbation applies to the fetched instruction word alone, so none of these is in the relation's range | R-17-058b, unclaimed at consumer grade, its answer deployment-graded software redundancy |
| A fault in stored state | corrected by the pervasive ECC, and a fail-stop event where uncorrectable | R-16-008b, R-15-175, R-15-177, which is a different case from the line above and is reached by a mechanism rather than left open |
| A fault on the fetch path's own checks, making a failing capability, alignment or PMA check pass | the perturbation applies to `w` after `fetch()` has returned `F_Base`, so the checks in [postlude/fetch.sail](../../model/model/postlude/fetch.sail) are the fault-free ones | no entry states it; recorded here as a range restriction the relation makes and the characterization must read |
| A fault below the canonical instruction level, in the resident dictionary-format image | the relation perturbs the 32-bit word the Sail model fetches, and the dictionary encoding sits below that level | finding 4 below |

The two rows about the datapath are separated on purpose, because they are the two cases a reader most often merges. A fault in **stored** state is R-16-008b's, it has a mechanism, and the mechanism is ECC with a fail-stop where correction fails. A **transient** strike in the datapath itself has no mechanism here at all: R-16-008b enumerates the mechanism catching each injection, says the transient datapath strike is reached by neither of the two detector positions it leaves as the unreached cases, and books it at R-17-058b, where it is unclaimed at consumer grade. Neither is in this relation, and the reason differs in each case.

## 6. Witnesses

The witnesses are stated over one concrete region instance, `W`, a credential comparison at the RoT gate reduced to the smallest shape carrying every element R-16-008c's construction sentence names. Mnemonics and register names are the corpus's, as [corpus/cap-memory.s](../../corpus/cap-memory.s) writes them. The compose-time constants are twelve bits wide so the traces read; that width is itself a finding, recorded below.

```
    ; region W: entry a_in = 0x80000100, exit a_out = 0x80000180.
    ; s1 is the signature register, s2 the difference accumulator, a0 the token
    ; register. c10 and c11 authorize the stored and presented credentials, two
    ; 64-bit words each. Entry conditions: s1 = 0, a0 != T, PCC authorizes
    ; [a_in, a_out). Compose-time constants K1 = 0x11f, K2 = 0x2a3, K3 = 0x0d6;
    ; the graph predicts S_ok = 0x3bc at B2 and S_end = T = 0x36a at the exit.

B1: 0x80000100  xori s1, s1, K1        ; B1 folds its constant
    0x80000104  li   s2, 0
    0x80000108  ld   t0, 0(c10)
    0x8000010c  ld   t1, 0(c11)
    0x80000110  xor  t2, t0, t1
    0x80000114  or   s2, s2, t2        ; word 0 of the difference
    0x80000118  ld   t0, 8(c10)
    0x8000011c  ld   t1, 8(c11)
    0x80000120  xor  t2, t0, t1
    0x80000124  or   s2, s2, t2        ; word 1 of the difference
    0x80000128  beqz s2, B2            ; comparison, first of the two
    0x8000012c  j    B3
B2: 0x80000130  xori s1, s1, K2        ; B2 folds its constant
    0x80000134  xori t3, s1, S_ok      ; the signature check between the two
    0x80000138  bnez t3, B3
    0x8000013c  beqz s2, B4            ; comparison, second of the two
    0x80000140  j    B3
B4: 0x80000144  xori s1, s1, K3        ; B4 folds its constant
    0x80000148  xori t4, s1, S_end     ; the exit comparison against the graph
    0x8000014c  bnez t4, B3
    0x80000150  xor  a0, s1, s2        ; the token, computed from the comparison
    0x80000154  j    a_out
B3: 0x80000158  ...                    ; the fail-stop class R-17-030n names
```

`W` meets R-16-008c's construction sentence clause by clause: each basic block folds a compose-time constant into the signature register, the exit compares the accumulation against the value the graph predicts and a mismatch raises the fail-stop class, acceptance is a multi-bit token computed from the comparison that no fall-through, skipped branch or truncated region produces, and the comparison is performed twice with the signature check between the two. It is the strongest reading of that sentence this document could find, so that the scope test below is a test of the construction and not of a weak rendering of it.

**Witness N, fault-free.** The budget is unspent, so every transition is `STEP` and the trace is the model's own. With the two credentials equal, `s2` is `0` at `0x80000128`, the run takes `B2` and `B4`, `s1` holds `K1` after `0x80000100`, `S_ok` after `0x80000130` and `S_end` after `0x80000144`, both checks pass, and `0x80000150` commits `a0 = S_end xor 0 = 0x36a = T`. The activation ends at `a_out` with the token produced and the decision reached correctly.

**Witness F, one fault, token withheld.** Budget `1` is spent by `FAULT` with `f = skip` at the step whose `PC` is `0x80000130`, which is in `R`. `s1` therefore stays at `K1 = 0x11f` rather than reaching `S_ok`. At `0x80000134` the signature check computes `t3 = 0x11f xor 0x3bc = 0x2a3`, which is not zero, so `0x80000138` transfers to `B3` and the activation ends in the fail-stop class. Every later transition is `STEP`, the budget being `0`. `a0` is untouched and is not `T` by the entry condition, so the token is withheld. This is a member of the relation, and the only member's-eye difference from witness N is the one transition that used the budget.

**Witness X, two faults, a non-member.** Take witness F's fault and add a second at `0x80000134`, replacing the signature check with one that compares against `K1` so that `t3` is zero and the run continues into `B4`. There is no derivation: after the first `FAULT` the configuration carries budget `0`, and `FAULT` requires budget `1` in its premise, so the second perturbation is generated by no rule. That is the clause rejecting it, and naming it is the point. Whether the excluded run reaches the token is R-17-058b's evidence question and is not this relation's business.

**A fault outside `R`.** A perturbation at a step whose `PC` is `a_out` or beyond, or inside a helper the region calls, fails `FAULT`'s `in_region(s)` premise and has no derivation either. The entry conditions above are the visible consequence: `s1 = 0` and `a0 != T` at `a_in` are assumptions about state this relation does not govern, and a fault that established them is outside the model rather than silently inside the fault-free class.

## 7. The scope test, and what it returns

R-16-008f's conclusion is that *"no in-model fault yields the acceptance token, so the decision the sequence reaches is withheld rather than reached wrongly"*. The Q3c cell requires the model to be tested for a decisive scope counterexample before it is expanded, and forbids inferring a harmless-fault exception or excluding a difficult comparison or token step to make the theorem easier. The test was run on the epilogue boundary first, because R-17-058b's second limit says a fault inside the compare-and-fail-stop epilogue is not caught by that epilogue and R-16-008f's exclusions do not name the epilogue, so the epilogue is in-region and in-model and the two entries reconcile only if an in-model fault there still withholds the token. The epilogue survives the test on `W`: the doubled comparison with the signature check between the two, and a token computed from the signature rather than branched to, mean that a single perturbation of either comparison leaves the other standing and a single perturbation of any fold moves the token off `T`.

**The test returns a counterexample elsewhere, and it is decisive.** Take `FAULT` with `f = skip` at the step whose `PC` is `0x80000114`, which is in `R`, and let the presented credential differ from the stored one in word 0 alone, which the party presenting it chooses. Then:

| Step | Effect under the fault | Effect under no fault |
| --- | --- | --- |
| `0x80000114` | skipped: word 0's difference never enters `s2` | `s2` takes word 0's difference, which is non-zero |
| `0x80000124` | `s2` takes word 1's difference, which is zero | `s2` stays non-zero |
| `0x80000128` | `s2` is zero, so the run takes `B2` | the run takes `B3` |
| `0x80000130`, `0x80000144` | folded correctly; the budget is spent and every later transition is `STEP` | n/a |
| `0x80000134`, `0x80000148` | both checks pass: the path taken is a legal path of the graph and `s1` reaches `S_end` | n/a |
| `0x80000150` | `a0 = S_end xor 0 = T` | n/a |

One skipped instruction, in region, in budget, not a second fault, and not a datapath strike: the instruction word is what the relation perturbs, and no register bit is flipped and no arithmetic result is wrong. The acceptance token is produced, and the gate accepts a credential that does not match.

**What this refutes is not the relation.** The relation is exactly the one R-16-008f names, and narrowing it to save the conclusion is what the cell forbids. What is refuted is the entailment: **R-16-008c's construction obligations do not imply R-16-008f's conclusion.** A running control-flow signature decides that the path taken is a legal path of the region's graph. It does not decide that it is the path the data warrants, and a single fault on the reduction from the decision's data to the compared value changes the second without changing the first. The doubled comparison raises the cost of steering the comparison itself to two faults, which is what R-17-058b credits it with, and it does nothing at all when both comparisons read an accumulator a single earlier fault already emptied. R-16-008c's own sentence names the intent, *"the decision each sequence reaches is encoded so that omitted work yields refusal"*, and the mechanism it goes on to state does not achieve that intent for work omitted inside a basic block.

**What would close it is a construction obligation, and no entry states one.** The reduction from the decision's data to the compared value must be such that omitting or corrupting any single instruction of it cannot leave the compared value at its accepting point. A collision-resistant absorb over the whole credential has that shape, since dropping one absorb moves the digest; a word-wise difference accumulator does not, since dropping one accumulate removes one word's contribution and leaves the accepting value reachable. That obligation constrains the instrumentation R-16-008c mandates, is not implied by anything R-16-008c says, and is a register act rather than a reading. It is finding 1 below.

The witness is exhibited on the credential class because that class reduces attacker-supplied data to a decision in the shortest form. The other two classes owe the same reading against their own reductions before the theorem is stated over them, and this document claims no witness for either: a measured-boot verification whose comparison is already a digest may well satisfy the obligation the credential gate's word-wise comparison does not, and a lifecycle guard's reads of one-way fuse state have a third shape again.

## 8. What this model does not establish

**Sampled injections and satisfiability witnesses do not establish detection.** They refute. A campaign that injects faults at a sample of positions, and a solver run that finds no satisfying assignment within a bound, each establish that the positions tried did not defeat the construction. R-16-008f's acceptance criterion requires the proof to quantify over every in-model fault of each protected region rather than sampling them, and the gap between the two is the whole reason the relation is written down: a quantifier over the index set of the rules above is a different object from a set of trials, and no number of trials converts into one. Where a campaign finds a fault that yields the token it is a counterexample and decides the matter; where it finds none it decides nothing.

**No harmless-fault exception is taken, and none may be read into this document.** The relation admits every single perturbation at every in-region step, including perturbations that change nothing architecturally. Finding 3 below records what that costs R-16-008f's conclusion as written, and records it as a statement to be repaired rather than as a class to be removed from the model.

**No comparison or token step is excluded.** The compare-and-fail-stop epilogue is in-region and in-model, and `FAULT` applies at every one of its steps. R-17-058b's limit that a fault inside that epilogue is not caught *by that epilogue* is a statement about which mechanism catches it, not a licence to remove those steps from the model, and this document does not remove them.

**The other limits stay where they are booked.** The safe-error oracle, the acceptance token's trip-or-no-trip outcome being itself observable, is R-17-058b's and is bounded at the credential gate by the RoT attempt counter and elsewhere by the restart a trip costs. The lockstep decision for the S-class core alone is R-16-008d's. The combined adversary who probes and faults in one execution is R-17-058c's, and no conjunction of this axiom with R-15-053a's covers him until R-17-058d's reduction checks on the artifact.

## 9. The silicon assumption, and what is owed before acceptance

**The assumption's status is recorded, and its characterization has no owner.** R-16-008f makes the model *"an axiom about the silicon in the R-06-011 sense"*, and R-17-058b's acceptance criterion makes its faithfulness carry *"a bring-up characterization obligation and independent review rather than an assumed fit, the shape R-15-053a takes for leakage"*. R-15-053a's half of that has an owner: the plan's hardening opening owes the R-15-053a bring-up characterization, rehearsed on the FPGA and executed at first silicon, the rehearsal validating the harness and never the axiom. R-16-008f's half has none. Naming one is finding 5 below, and this document does not name one by implication.

**What this document owes to the review.** The Q3c acceptance predicate requires an independent review of the region, corruption and compare/fail-stop boundaries, with the region-boundary review separated from the corruption-relation review and their witnesses reconciled. That review has not run. The three judgments it should take first are the corruption relation's strength, which the register does not fix and §4 fixes at arbitrary word substitution with its reasons; the region predicate's reading on `PCC` as well as `PC`; and whether the scope test's counterexample is answered by a construction obligation on R-16-008c or by a qualification of R-16-008f's conclusion.

**The findings this document returns.** Each is a register decision owed before the relation is accepted, and none of them is answered by narrowing the model.

1. **R-16-008c's construction obligations do not imply R-16-008f's conclusion.** A single skipped instruction inside a protected region yields the acceptance token and a wrong decision, on a region instance meeting R-16-008c's construction sentence clause by clause. The act is an obligation on how the decision's data is reduced to the compared value, added at R-16-008c or carried as a named premise at R-16-008f.
2. **The acceptance token's width is load-bearing and is fixed nowhere.** R-16-008c says the token is multi-bit and stops. At the width `W` uses, one `corrupt` at `0x80000150` with the encoding of `addi a0, zero, 0x36a` constructs the token without the comparison being consulted at all, and the same holds for any token a twelve-bit signed immediate reaches or any token of the form a twenty-bit immediate shifted left by twelve. The act is a width obligation, stated against what a single instruction of the frozen profile can place in a register from an immediate or from live state.
3. **R-16-008f's conclusion admits no ineffective fault, and effect-preserving perturbations are in-model.** `corrupt(w')` where `w'` is a different encoding of the same architectural effect yields the acceptance token, so *no in-model fault yields the acceptance token* is false for any construction whatever. The conclusion the trailing clause of R-16-008f actually wants is that the decision is never reached wrongly, and the repair is the effective-fault disjunction R-17-058d's case split already uses on the masked datapath: every in-model fault either leaves the region's committed architectural effect equal to the fault-free one, or the token is withheld. That is a restatement of the theorem, not an exception in the model.
4. **The frozen encoding admits a single physical fault that perturbs more than one canonical instruction.** The profile's only instruction-fetch format is the fixed-rate dictionary encoding (R-15-036a), where the bundle header carries one escape-start bit per slot and decode is a pure function of the bundle's contents and the slot index (R-15-036b). One header bit therefore decides whether a slot pair is one escaped canonical instruction or two dictionary instructions, so a fault on that bit changes more than one instruction of the canonical stream this relation perturbs, which is outside *at most one skipped or corrupted instruction*. The relation is stated at the canonical level because that is where the Sail model and R-16-008f put it. What the act owes is a statement of the correspondence between a fault on the resident image and this relation's perturbation, which is characterization work and therefore runs into finding 5.
5. **No artifact owns the R-16-008f bring-up characterization.** R-17-058b's acceptance criterion obliges one. The plan's hardening-opening cell owes the R-15-053a characterization by name and states the others generically; no cell and no row of the unassigned proof map's mandatory list names this one. The act is to name an owner, at that cell or beside U-19, before the axiom is quoted as characterized.

**What is owed elsewhere, and is not owed here.** U-19 owns the detection theorem over this relation and its proof over a model instance. The compiler-emitted signature instrumentation has no toolchain cell, the countermeasure's authoring route waits on a register act, and the R-17-058d reduction is priced over accepted premises at the plan's post-M10 cell; all three are already recorded on [the unassigned proof map](../assurance/unassigned-proof-map.md)'s mandatory list. The binary-level check where a sequence passes admission is artifact-admission's. This document opens no cell for any of them.
