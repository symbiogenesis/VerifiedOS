# Critique Into Action

Proposed, non-normative work distilled from [DESIGN-ASSESSMENT.md](DESIGN-ASSESSMENT.md). This is a decision checklist, not a replacement for the [implementation checklist](docs/implementation-checklist.md), a new requirement register, or a commitment to implement every alternative. All boxes are open recommendations. Promote accepted work into its owning plan and register; do not maintain parallel completion records here.

## TL;DR

**Use more of the tools already selected before selecting more tools.** First connect a small generated implementation to the actual target, measure a useful workload, and independently check the static resource assignment. These give the best chance of reducing effort without weakening the security architecture.

**For capacity, start with less data and better placement. For a major physical capacity increase, reconsider the physical topology.** Public immutable weights are the narrowest useful external-store experiment. More-transistor SRAM is not a density breakthrough, and more matrix throughput does not cure insufficient weight bandwidth.

**Do not increase the performance estimates just because these tasks are accepted.** Some repairs make the estimates less optimistic. Credit only a measured change against the current assumed baseline, not a feature the estimates already assume.

## Order of Work

The dependencies below are between review actions, not substitutes for the implementation plan's build prerequisites. A completed decision can reject an option; that still completes the decision task.

| Priority | Action | Depends On | Primary Payoff |
| --- | --- | --- | --- |
| Now | A: Correct the baseline and define rejection gates | n/a | Honest product and performance decisions |
| Now | B: Demonstrate a single-source lowering route | Existing lowering environment; target backend for the device leg | Less hand-maintained implementation and proof work |
| Now | C: Connect the existing assurance instruments | Existing model, oracle, and proof tooling | Security evidence reaching real code |
| Next | D: Measure inference and recover usable capacity | A; target leg also needs B or the existing backend | Smaller working set and possibly faster inference |
| Next | E: Search static placements and schedules | A; current resource contract and cost inputs | More useful work per fabricated byte and reserved cycle |
| Decision | F: Compare realizable memory topologies | D and E for workload demand; physical inputs for qualification | Potentially much greater physical capacity |
| Decision | G: Protect sensitive bulk against remanence | Threat decision can start now; design depends on F | Physical confidentiality hardening |
| Decision | H: Accelerate the measured bottleneck | A and a target trace from B or D | Workload-specific speed and energy improvement |
| Later | I: Restore selected compatibility and autonomy | A; bounded resource and admission contracts | Usability and reusable software |
| Before expansion | J: Choose a product scope and demonstrate it | B and C; D through I only where the product needs them | Avoid building an unusable large system |

A, B, and C can start independently. Host-side D need not wait for a whole OS. F begins as a demand-and-supply comparison, not a tapeout. Do not make a browser, full radio stack, or general external RAM prerequisite to the first vertical slice.

## Action Checklist

### A. Establish the Baseline

- [ ] Replace the unsupported aggregate performance headline with separate scalar, media, masked-crypto, prompt-processing, and token-generation claims. Preserve unknowns as unknowns.
- [ ] Fix the assessment's overview issues at their owners: allocator utilization versus fragmentation, represented capability bounds versus object bounds, timing-channel scope, the ECC fault model, and typed interpreter versus conventional shell.
- [ ] Put absolute pass/fail limits on a representative workload: response latency, sustained power and temperature, capacity refusals, update turnaround, and operation without the external build service. Set limits before measuring the candidate.
- [ ] Record image identity, workload, quality target, memory population, clock and power assumptions, measurement method, and uncertainty with each result. Separate host elapsed time, target model cycles, FPGA observations, and silicon measurements.

**Done when:** a candidate can fail the product gate despite satisfying the security admission rules, and every performance claim identifies its comparator and evidence. Use the current [performance estimates](docs/performance-estimates.md) and [floor requirements](docs/spec.md#r-18-004a), not a second set of manually maintained arithmetic.

**Shortcut:** reuse the existing report and gate infrastructure. Do not build a benchmark dashboard before collecting a reproducible result. Documentation corrections improve accuracy, not hardware speed.

### B. Reduce Model-to-Implementation Duplication

- [ ] Start from the implementation plan's M1.6 result, not a fresh tool installation: the verified output targets ordinary RISC-V, while the C-text route lacks the required proof connection and depends on the incomplete purecap backend. Select a bounded wire-parser-shaped component, the consumer that measurement identifies, with an error path and explicit buffer bounds.
- [ ] Generate imperative output and its checked functional relation; keep generated output reproducible rather than editing it. Make a small source change and regenerate to expose maintenance cost.
- [ ] Audit the boundary from Bedrock2's word-and-byte memory to capability-bearing target code: pointer representation, provenance, bounds, calling convention, external calls, and failure behavior. Do not translate integer addresses into capabilities by an unchecked printer change.
- [ ] Choose the device path explicitly: capability-aware lowering through the existing backend, or a justified verified backend adaptation. Close the relation to the project's Sail model, including any intermediate-language translation. A stock Bedrock2 RISC-V theorem is not a theorem about this machine.
- [ ] Measure generated code size, target cycles, peak storage, proof-build time, and the hand-authored glue remaining. Compare with the manual-refinement route before expanding the technique.

**Done when:** a useful component has one authoritative operational source, mechanically regenerated implementation, a checked relation at each claimed boundary, and execution on the actual target model. A host-only prototype completes the first experiment, not the device proof.

**Use:** [Rupicola](https://github.com/mit-plv/rupicola) for customized relational compilation; [Bedrock2](https://github.com/mit-plv/bedrock2) for the imperative language and verification infrastructure. Their current role and licensing are already recorded in [THIRD-PARTY.md](THIRD-PARTY.md). Its lowering stack is available but no repository command invokes it. Connect it through the existing entry point rather than introducing a parallel build system.

**Known blocker, not a new discovery:** M1.6 also finds that higher-order specification code does not fit the target subset, and that the documented Clight intermediate is not emitted by either existing exit. Do not sell the tool as automatic compilation of the whole golden model. The CompCert-C/VST route remains the current default; replacing it needs a successful comparison. Scope the proposed proof work to the missing bridge or backend, and stop if that costs more than the duplication it removes.

**Expected effect:** potentially substantial effort reduction for recurring supported patterns; no guaranteed scalar-speed improvement. Functional compilation does not by itself establish constant-time behavior, resource bounds, robust preservation, or the hardware refinement.

**Do not:** build a general Gallina compiler or verified garbage collector first. Continue using domain-specific generation already in the plan where it fits. Keep manually refined code where it actually makes the implementation and proof simpler. The goal is less authored duplication, not one language at any cost.

### C. Make Existing Verification Reach the Implementation

- [ ] Connect the pinned capability-helper property suite to the narrowed model and enumerate the changed assumptions. Exercise bounds edges, malformed encodings, and the permission representation against the current semantics.
- [ ] Extend the existing oracle and mutation workflow for the chosen vertical slice. Keep compilation failures separate from mutants whose behavior is detected. Reject generated-output drift.
- [ ] Obtain a real implementation-to-specification theorem for that slice and inspect its assumptions. Keep host SMT checks and differential results labeled as evidence unless their results are replayed through the required trusted proof path.
- [ ] Specify and test the allowed fault model and fail-stop behavior at the touched hardware boundary. Assess common-mode failures before adding or rejecting a redundant protection mechanism.

**Done when:** the slice's production code is connected to its functional specification, its changed representation properties are checked, and the security claim says which assumptions and physical faults remain outside it.

**Use:** the existing Sail, Rocq, Verilator, QuickChick, `oracle`, and `seed` routes described in [tools/README.md](tools/README.md), plus the already pinned `sail-cheri-riscv-verif` property suite. A new fuzzing framework is not the first dependency needed here.

**Expected effect:** stronger evidence and less regression risk, usually additional immediate effort. Tests can falsify a claim; surviving tests do not discharge a universal theorem. No speed or capacity credit belongs to this action.

### D. Reduce Inference Demand Before Increasing Supply

- [ ] Select a useful model, representative tasks, quality threshold, context lengths, and concurrency. Track weights, KV state, scratch, decoding buffers, and the rest of the simultaneous workload separately.
- [ ] Compare weight and KV quantization where the quality and backend allow it. Measure dequantization and attention costs as well as packed size. Compare against what the current model-serving estimate already assumes.
- [ ] Run host-side prompt-processing and generation benchmarks with machine-readable output, then a separate end-to-end test including tokenization, sampling, and first-token latency. Record memory and energy through additional measurement instruments; do not assume the benchmark supplies them all.
- [ ] Extract the selected operator behavior and traffic demand, then measure corresponding target kernels and the fixed bandwidth grant. Do not carry host GPU token rates into the target estimate.

**Done when:** a quality-acceptable configuration has a measured host baseline, an explicit target traffic budget, and a report showing whether compute, bandwidth, storage, or the slot grant is limiting.

**Use:** [llama.cpp's llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench) as a host benchmark and behavioral comparator, not an automatically admitted runtime. Its documentation explicitly excludes tokenization and sampling time. Model weights have their own licenses, independent of the engine.

**Expected effect:** quantization can reduce weight or KV bytes and therefore traffic; smaller models or contexts reduce functionality as well as demand. No new physical cells are created. Bandwidth-bound decoding benefits only if saved transfers outweigh added computation and other traffic. Useful quality, not nominal parameter count, decides success.

### E. Recover Capacity Within the Existing Isolation Rules

- [ ] Export the current placement problem as structured data: object lifetimes, alignment, representable bounds, owner, bank, memory class, reserved sizes, slot grants, and timing limits. Use the existing [memory-plan obligations](docs/spec.md#r-08-012c) and [bank-count contract](docs/bank-count-dse-contract.md) as constraints.
- [ ] Start with enumeration for a small candidate set. Add OR-Tools CP-SAT only where a coupled placement or scheduling search actually justifies it.
- [ ] Let the solver propose static assignments, then independently check each assignment with exact arithmetic. Round uncertain physical costs conservatively. A search tool must not become the root of admission trust.
- [ ] Compare with the existing plan on admitted workload, unused reservation, image padding, and worst-case timing. Record solver status: timeout or `UNKNOWN` is not infeasibility, and `FEASIBLE` is not optimality.
- [ ] Optimize within the existing ownership and timing rules first. Treat cross-owner borrowing or new shared-lifetime assumptions as separate architecture changes, not solver conveniences.

**Done when:** the same workload has a checked improved assignment, or the report explains why no improvement was found without misrepresenting a limited search as proof of impossibility. An optimality claim needs stronger evidence than checking one feasible assignment.

**Use:** [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver), host-side only. The final trusted admission checks still need their required proof status; an independent Python validator is useful development hygiene, not automatically that proof.

**Expected effect:** possibly more usable payload in the same RAM and better useful throughput under the same schedule. No increase in raw physical capacity. If the present assignment is already good, the benefit can be zero.

### F. Compare Memory Topologies on the Same Workload

- [ ] Compare a smaller qualified all-SRAM configuration, the present SRAM-plus-gain-cell configuration, and SRAM plus an explicit public-weight store. State which workload each actually satisfies.
- [ ] For the public-weight candidate, stream bounded chunks authenticated against a trusted model identity. Keep authority-bearing state and verification buffers local; do not import executable authority or external capability tags. Specify buffering, integrity-failure behavior, and the physical requester interface.
- [ ] Account for link bandwidth, verification throughput, scratch buffers, loading time, storage energy, and visible access patterns. Public weights do not make prompt-dependent sparse accesses public. An external device can deny service, so do not promise hard delivery without a separately justified bound.
- [ ] Use supplied or measured physical coefficients, including ECC, tags where needed, periphery, routing, refresh, repair, and thermal corners. Ask a foundry or macro provider for realizable supply, not just literature cell density.
- [ ] Decide the memory topology and address-growth story before treating the current capability format as an irreversible deployed constraint. Explicit block storage need not be directly mapped into the capability address space; wider load/store addressing is a separate decision.

**Done when:** the candidates are compared on useful workload, total resources, implementation maturity, and physical threat claims, and the selected product has a credible supply path. A capacity-only winner that cannot deliver required bandwidth loses.

**Use conditionally:** [Ramulator2](https://github.com/CMU-SAFARI/ramulator2) for conventional-DRAM alternatives and [OpenRAM](https://github.com/VLSIDA/OpenRAM) for SRAM macro exploration with a suitable technology setup. Neither supplies or qualifies the proposed oxide-semiconductor stack. Do not use Ramulator's default out-of-order frontend, cache, or dynamic scheduling as a model of VerifiedOS; provide the relevant trace and controller policy. OpenRAM models in a different process are not a scaled prediction of this process.

**Expected effect:** the strongest route to substantially more physical storage changes the current one-die/no-external-memory restrictions. External block storage can expand accessible model data without increasing directly addressable RAM. It may make a larger model possible while making each token slower. More-transistor SRAM may improve stability or voltage margin but generally spends density.

### G. Address Bulk Remanence Deliberately

- [ ] Decide whether abrupt-power-loss confidentiality for sensitive bulk is required for the intended deployment. The present [remanence residual](docs/spec.md#r-17-058f) must not disappear behind capability-tag invalidation.
- [ ] If required, compare keeping sensitive data in appropriately protected local storage, reducing retained sensitive bulk, and an encrypted bulk path whose ephemeral key has an independently justified lifetime and destruction mechanism.
- [ ] For an adversary-controlled memory interface, include authentication, freshness, address and generation binding, and atomic data/metadata updates. Use a defined standard construction, not a newly invented cipher or mode.
- [ ] Measure masked cryptographic throughput, metadata storage, boot and power-loss behavior, and transition latency. Separate ciphertext confidentiality from remaining access-pattern, power, live-probe, and denial-of-service risks.

**Done when:** the design either has a concrete protection construction and evidence for its threat window, or the product explicitly declines deployments needing that property. The former requires changing the no-memory-crypto policy; the latter is scope control, not hardening.

**Use:** existing cryptographic proof and oracle work first. Reuse existing primitive and hardware-IP knowledge where appropriate, but do not mistake a verified primitive or masked AES block for a complete verified memory-protection subsystem.

**Expected effect:** genuine security improvement for a defined physical threat window; more area, metadata, effort, and latency. Any performance benefit is indirect, such as making a larger conventional memory option acceptable.

### H. Accelerate Only a Demonstrated Bottleneck

- [ ] Profile the target path before adding a new core mechanism. Distinguish frontend issue, pointer dependencies, bank stalls, memory traffic, vector utilization, and masked-crypto throughput.
- [ ] Try static improvements first: layout, loop transformations, bounded tiling, supported vector lowering, and fusion already compatible with the profile. Measure the code-size and working-set cost as well as cycles.
- [ ] For a remaining media or arithmetic hotspot, compare a bounded verified hardware operation with the software implementation. Include state, data movement, reset, authority, constant-time obligations where relevant, and proof maintenance in the comparison.
- [ ] Reuse Ara, Gemmini, or OpenTitan material already named in [THIRD-PARTY.md](THIRD-PARTY.md) where it fits. Do not assume the imported block's bus, DMA, timing, or verification contract matches this machine unchanged.

**Done when:** the composed workload improves at acceptable quality and energy without violating its timing and protection contracts. Make separate estimate scenarios for architectural alternatives; do not quietly modify the current-design baseline.

**Expected effect:** potentially large gains on the accelerated fraction, not a blanket scalar uplift. Many optimizations and accelerator families are already assumed in the estimates; implementing them realizes a budgeted benefit rather than earning it again. A new codec accelerator is not a weekend shortcut merely because fixed-function hardware is conceptually admissible.

### I. Restore Useful Compatibility Selectively

- [ ] Pick an actual blocked application or workflow before defining compatibility. Try a small explicit-authority API subset rather than a full POSIX personality.
- [ ] For development autonomy, first support bounded source processing and artifacts as data while preserving the native-code admission boundary. A compiler library does not provide the target's required certificates or make the package composer local for free.
- [ ] Consider a confined external-authenticator client with bounded protocol handling and no arbitrary DMA. State that the key's credential behavior remains an external trust dependency even if it cannot compromise platform isolation.
- [ ] Measure the external generation service's build, proof, transfer, restart, and recovery times. Cache identical artifacts and proof results only by complete dependency identity; invalidate them when semantics, configuration, or assumptions change. Do not turn caching into a bypass of required checking.

**Done when:** a named workflow works within an explicit capability, resource, and trust contract, with the relevant policy changes approved. Do not build speculative compatibility layers before a consumer exists.

**Expected effect:** usability and code reuse more than processor performance. Local development, protocol support, and autonomy add implementation work initially. Reuse can repay it, but the external-authenticator decision does not automatically strengthen every threat model.

### J. Choose the Product You Can Demonstrate

- [ ] Build a minimal production-path vertical slice: bounded input, capability transfer, persistent operation, controlled failure, and restart. Keep the same device binary across the executable model and RTL co-simulation.
- [ ] Exercise adverse but ordinary conditions: simultaneous work, full pools, interrupted updates, loss of the build service, thermal limits, and recovery within the declared fault model.
- [ ] If the simultaneous mobile floor cannot close on credible resources, explicitly revise scope. A smaller all-SRAM appliance or host-executed model can be a useful deliverable, but neither satisfies an unchanged mobile hardware claim.

**Done when:** useful behavior, implementation correspondence, resource accounting, and physical feasibility meet at one configuration. A host product is a different assurance scope because its host and runtime become dependencies, not an optimized-binary shortcut to the original theorem.

## Dependency Shortlist

The capability and root-license sources below were consulted for this review. These are candidates, not additions to the dependency inventory: nothing is installed or vendored by this checklist. Existing pinned components retain their license authority in [THIRD-PARTY.md](THIRD-PARTY.md). New candidates require a selected immutable revision, dependency and notice review, and a reproducible invocation before incorporation. Root licenses do not automatically cover bundled dependencies, PDKs, model weights, or every generated artifact.

| Candidate | Recommendation | Benefit and Integration Boundary | License Source |
| --- | --- | --- | --- |
| Rupicola / Bedrock2 | First compiler experiment, using the existing environment | Reduce repeated manual functional-to-imperative refinement for suitable parsers; close the known capability and proof gaps before claiming a device route | Existing MIT readings in [THIRD-PARTY.md](THIRD-PARTY.md) |
| Existing Sail helper proofs, QuickChick, oracle and mutation tools | Connect before adding another verification framework | Stronger coverage of the actual narrowed semantics and generated code; host solver results are not automatically Rocq proof objects | Existing inventory and [tools/README.md](tools/README.md) |
| OR-Tools CP-SAT | Add only if simple enumeration is insufficient | Host-side constrained search; exact independent admission checks keep search heuristics outside the trust base | [Apache-2.0 root license](https://raw.githubusercontent.com/google/or-tools/stable/LICENSE) |
| llama.cpp / llama-bench | Useful host-only workload instrument | Compare quality-acceptable model configurations and prompt/generation behavior; no certified target port implied | [MIT root license](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/LICENSE) |
| Ramulator2 | Conditional on evaluating conventional external DRAM | Avoid authoring a general DRAM timing simulator; adapt the traffic and scheduling assumptions, and add power analysis separately | [MIT root license](https://raw.githubusercontent.com/CMU-SAFARI/ramulator2/main/LICENSE) |
| OpenRAM | Conditional on a suitable PDK and macro experiment | Generate SRAM layout, timing, and power views; not a source of qualified gain cells or a ready-made high-density monolithic stack | [BSD-3-Clause root license](https://raw.githubusercontent.com/VLSIDA/OpenRAM/stable/LICENSE) |

For the new host tools, isolate their environment from the existing Rocq and Sail switches. Check platform and interpreter compatibility at the chosen revision; an upstream Python API is not proof that a wheel exists for this host and Python version. Prefer the repository's WSL dispatch when a tool's supported environment is Linux. Add commands through [tools/run.py](tools/run.py) if an experiment becomes recurring work.

**Licensing is also an implementation constraint.** The existing CompCert/SECOMP route has non-commercial terms outside its separately licensed portions, as the inventory explains. Do not assume that a permissive generator makes a commercially usable compiler chain, or that it solves third-party rebuildability. Resolve the intended use and distribution terms before depending on that route for a product. The permissive Bedrock2 route is worth comparing, but its missing CHERI target prevents treating it as an immediate replacement.

## What Benefits Can Actually Be Claimed?

These are conditional directions, not measured deltas or additive credits.

| Change | Performance | Capacity | Implementation Effort | Security |
| --- | --- | --- | --- | --- |
| Correct claims and instrument the baseline | Estimates may fall; hardware unchanged | Unchanged | Small setup cost; less misdirected work | Clearer claims, no new protection |
| Reusable generated lowering | Uncertain; target optimization still needed | Possibly less runtime or image overhead | Strongest candidate for recurring savings | Fewer manual correspondence gaps if the whole route is checked |
| Existing proof and oracle integration | Usually unchanged | Unchanged | More immediate work; less regression uncertainty | Stronger evidence, not universal fault immunity |
| Quantization and smaller inference demand | Can help bandwidth-bound work; quality and compute tradeoffs | More useful payload per byte, not more RAM cells | Moderate integration and validation work | No automatic hardening |
| Better static assignment | Can reduce waits or fit more useful work | Better utilization only | Solver integration plus independent checking | Isolation preserved if the same constraints hold |
| Explicit external public bulk | May slow generation despite improving fit | Potentially much larger data store | New interface, checking, and hardware integration | New integrity, traffic, and availability boundary |
| Authenticated-encrypted sensitive bulk | Usually a direct cost | Metadata consumes space; can enable a larger medium | Substantial new subsystem | Better defined physical confidentiality and integrity |
| Targeted acceleration | Potentially large local gain; limited total gain | Area competes with RAM | More hardware integration and proof work | Neutral only after new obligations are met |
| Bounded compatibility and local workflows | Primarily usability | Resource cost, not a capacity win | Can reduce porting; costs new interfaces | Must analyze each added trust boundary |
| Smaller product scope | Better chance of meeting latency and power | Less capacity required | Large reduction in the work needed for a useful product | Smaller attack and proof surface; fewer features |

For an optimization affecting only part of runtime, use the standard upper-bound sanity check rather than applying its local gain to the whole program:

$$
S_{total}=\frac{1}{(1-f)+f/S_{part}}
$$

Here $f$ is the original time fraction accelerated and $S_{part}$ its speedup, assuming the remaining costs are unchanged. Added transfers or changed scheduling invalidate that simplification and must be measured separately. Similarly, external bulk capacity is not a token-rate gain, and compressed data capacity is not a wider physical address space.

## Shortcuts Worth Taking

- Generate implementations and proof obligations from one source where that is cheaper than hand-maintaining both. Reuse the project's domain-specific routes before inventing a universal one.
- Use powerful untrusted search to propose a small artifact and a simpler independently justified check to admit it. The search algorithm need not become a trusted runtime.
- Reuse host libraries as behavioral comparators and measurement tools without promising they are shippable certified code.
- Change one architectural variable per comparison. Keep current-design and relaxed-design results separate.
- Reject an option after a small decisive experiment. Do not construct its entire toolchain merely to learn that it misses the bandwidth or proof-cost budget.

## Shortcuts to Avoid

- A second fast emulator, whole-system simulator, or new proof language without a demonstrated blocker in the existing workflow.
- Shipping extracted host code and treating native execution as evidence for the original capability, timing, and hardware theorem.
- Feeding generated integer-pointer C into the CHERI compiler and assuming source-to-device correspondence is inherited automatically.
- Replacing an unqualified cell with a simulator parameter and calling the memory qualified.
- Adding up improvements that address the same bottleneck, or crediting vectorization, quantization, and synthesis already present in the baseline.
- Installing every candidate dependency now. Select one experiment, review and pin its dependencies, and require it to answer a question before widening the toolset.