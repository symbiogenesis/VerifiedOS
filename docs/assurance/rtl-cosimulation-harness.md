# The RTL Co-simulation Harness

*R2's contract: how the curated scalar core's retirements reach the one adjudicator the corpus already uses, what the retirement frame carries and refuses, the bounded model-checking smoke the harness owes under R-15-094, and the revocation join it takes as a specified input. Section numbers here are this document's own.*

> **What exists and what does not.** The adapter exists on both sides of the frame: a SystemVerilog writer that turns one retirement into one line, and a decoder that refuses a malformed or partial frame and projects the rest onto the commit trace. Both are exercised against the golden model's own traces and against seeded field changes. **No co-simulation result exists.** The curated core elaborates, but it does not yet compute a correct PC, jump target, data address or integer CSR value and the co-simulation gate has not run ([the RTL tree's own account](../../rtl/README.md#3-what-each-has-been-held-to-and-what-it-has-not)), so no frame has been written by a core, no corpus member has been compared against one, and no bounded model check has run. Everything below that concerns the core is an obligation, not a measurement.

## 1. The two halves of one comparison

The golden half is the commit trace of [the differential corpus's schema, version 1](differential-corpus.md#4-the-commit-trace-schema-version-1), which the emulator writes under `--trace-commit` for each member, and whose digest the corpus manifest records. The RTL half is the core's RVFI port. Between them sit three pieces and no second adjudicator:

| Piece | Where | What it does |
| --- | --- | --- |
| Frame writer | [tools/rvfi-harness/vos_rvfi_frame.sv](../../tools/rvfi-harness/vos_rvfi_frame.sv) | One line per retirement, in the frame of section 2, converting the destination's register form to its memory encoding through the authored format package's `cap_reg_to_cap_mem` |
| Frame decoder | [tools/vos/rtltrace.py](../../tools/vos/rtltrace.py) | Refuses every frame that breaks its protocol, and projects the rest onto commit records through [rvfi.py](../../tools/vos/rvfi.py)'s projection |
| Adjudicator | [tools/vos/trace.py](../../tools/vos/trace.py) | `trace.adjudicate`, unchanged, which the corpus, the RVFI-DII rig and this adapter all call |

**The corpus uses actual fetch and a retirement frame; generated streams use the
RVFI-DII socket.** Direct instruction injection replaces the fetch source
(section 6), so a socket run executes injected words and exercises none of the
fetch path's capability checks. The RVFI-DII version-2 packet also has no cause
field. The existing version-1 frame adds that cause to the packet's field set,
with a header and counted trailer that let the decoder refuse a torn or partial
file. The initial accepted core attachment uses the complete version-2 frame
selected in section 4.1; this frame version is distinct from the RVFI-DII packet
version. Both routes reuse the golden records, normalization and
`trace.adjudicate`. Their observation sets and fetch claims remain separate.

**A protocol failure is not a divergence, and agreement over a prefix is not agreement.** A torn record once read as a divergence about a run that agreed ([the rig's first finding](../implementation/completion-log.md#s11-join-the-testrig-ecosystem-over-rvfi-dii)), and `trace.adjudicate` treats one stream running out as two machines halting on different conditions, which is right for a legacy oracle and wrong for a corpus gate. So the decoder raises on a broken frame before anything is compared, and a comparison is *complete* only where the verdict agrees and both streams were consumed whole.

## 2. The frame, version 1

### 2.1 Lines

Text, one record per line, every line ending in a newline and carrying no carriage return.

| Line | Occurs | Content |
| --- | --- | --- |
| `vos-rtl-rvfi 1` | first, once | the format and its version; another version is refused rather than read as this one |
| `P` and its fields | once per retirement, in retirement order | the fields of section 2.2 in that order, space-separated, fixed-width hexadecimal in either case |
| `E` and a decimal count | last, once | how many `P` lines the writer wrote |

Retirement order across commit ports is port order within a cycle. The curated configuration has one commit port, and the writer takes a port count so that a second changes nothing on the decoder's side.

### 2.2 Fields

| Field | Digits | What it must be |
| --- | --- | --- |
| `order` | 16 | the retirement's index in this frame, from zero |
| `pc_rdata` | 16 | the address the retired instruction was fetched from, which is the `I` record's `pc` |
| `pc_wdata` | 16 | the address the next retirement was fetched from, wherever this retirement did not trap, which the decoder holds (section 2.3); not read on a trap, and compared by nothing, the commit trace having no such record |
| `insn` | 8 | the 32-bit word the golden trace records for the retirement; the emitter records zero where no word was fetched |
| `trap` | 1 | 1 on a retirement that took a synchronous exception |
| `cause` | 16 | the `mcause` value where `trap` is 1, and zero on every other retirement |
| `rd_addr` | 2 | the destination register, zero where none is written |
| `rd_tag`, `rd_wdata` | 1, 16 | the two halves of the destination's 64-bit memory encoding, the bits a store of the register writes; both zero where `rd_addr` is zero |
| `mem_addr` | 16 | the address of the access |
| `mem_rmask`, `mem_wmask` | 2, 2 | byte masks shifted to the access's own address: zero, or a low run of one, two, four or eight ones |
| `mem_rtag`, `mem_wtag` | 1, 1 | the tag of the access; only an eight-byte access carries one (R-15-203) |
| `mem_rdata`, `mem_wdata` | 16, 16 | the bytes read or written, lowest at `mem_addr`; bits above the access's width are not compared |

### 2.3 What the decoder refuses

The decoder rejects malformed frames before adjudication—never reporting them as behavioral divergences—and identifies the failing line and reason for each of the following:
- an empty frame, a missing or wrong header, or an unsupported version;
- a missing trailing newline (truncated write), any carriage return, or a line prefix other than `P` or `E`;
- a `P` line with the wrong field count, width, or hex alphabet, or a boolean flag other than `0` or `1`;
- an `order` field not equal to the retirement's sequential index, or a `pc_rdata` not equal to the preceding non-trapping retirement's `pc_wdata`;
- a register index outside `0..31`, nonzero data or tag on a write to `x0`, or a nonzero `cause` when `trap` is `0`;
- a memory mask that is not zero or a low run of 1, 2, 4, or 8 ones, or a nonzero memory tag on an empty or sub-granule access;
- a missing `E` trailer, a trailer count that disagrees with the number of `P` lines, or trailing lines after `E`.

**How `order` and PC continuity interact.** Because the imported RVFI port assigns no `order` (section 3), the SystemVerilog writer generates the sequential count; a retirement dropped *before* the writer leaves no gap in `order`. Instead, the preceding non-trapping retirement's `pc_wdata` exposes the drop at the next retirement's `pc_rdata`. Four drop sites bypass `pc_wdata` continuity and surface at adjudication as a divergence or incomplete stream: the first retirement, a retirement immediately after a trap, a self-loop jump fetched from its own target address, and the final retirement. Because asynchronous interrupts are absent (R-15-099), every trap-handler entry follows a trapping retirement. Once the port supplies its own retirement counter, `order` catches the first three cases directly, while a dropped final retirement still fails completeness.

## 3. What the imported port states, and what the harness must supply

Read at `core/cva6_rvfi.sv`, `core/cva6_rvfi_probes.sv` and `core/include/rvfi_types.svh` of the pinned CHERI-CVA6 datapath. These are obligations on the core-port contract R1b owns and the harness consumes, and each is a finding until that contract states it.

| Frame field | The port at the pin | What the harness needs |
| --- | --- | --- |
| a retirement | `valid` is raised on a synchronous exception only for the three environment-call causes and the capability cause | every synchronous exception retired, so the writer samples `valid` or `trap`, as the pinned TestRIG harness under `corev_apu/tb/tb_testRig_cheri/` already does |
| `order` | declared and assigned nowhere | a retirement count at the port, so the decoder's check reaches the core's side of the writer |
| `pc_wdata` | `mepc` for an `mret` that did not trap, the commit stage's next program counter for an instruction the decoder assigns the `CTRL_FLOW` unit, the instruction's address plus its length for any other, and `mtvec`'s base on a trap | the address the next retirement is fetched from wherever this one did not trap, a capability jump's target and the address `MEPCC` returns to included, so the continuity check of section 2.3 refuses only a lost, repeated or misreported retirement |
| `insn` on a fetch fault | the scoreboard entry's instruction word, whatever the fetch returned | zero where the fetch faulted and no word was fetched, as the golden emulator records it; otherwise a fetch-side fault diverges at the `I` record for a reason that is the port's and not the core's |
| `rd_tag`, `rd_wdata` | `rd_wdata` is declared at the register form's width and filled from the probes' `wdata`, which the probe record declares at `XLEN` | the destination's full register form, or its memory encoding with the tag, through the probe record |
| `rd_addr` on a trap | the scoreboard's destination is reported whether or not the instruction trapped | zero on a trap, as the golden trace writes no register on one |
| `mem_rtag`, `mem_wtag` | no field | the tag of the access from the load/store unit |
| `mem_rdata` | the instruction's result, which is the loaded value after extension | the bytes read; the result serves for a data load, whose low bytes are those bytes, and not for a capability load, whose result is a register form |
| masks on a trap | taken from the load/store unit's request, and nothing clears them when the access faults | zero where the golden trace records no access |
| `mem_addr` | the virtual address | the physical address, which is the same here, the MMU being deleted (R-15-099) |
| `cause` | assigned on every cycle from the commit stage's exception record, valid or not | read only where `trap` is 1, which the writer enforces |

**The writer converts one field and repairs none.** It writes the destination through `cap_reg_to_cap_mem`, applies RVFI's rule that a write to x0 carries nothing (the register form of an all-zero input does not encode to zero), and writes `cause` only on a trap. Every other field is passed through as the port states it, so a port that breaks an obligation above produces a frame that diverges or is refused, never one that agrees because the harness repaired it.

## 4. What a frame compares, and what it cannot carry

The golden trace is cut to what a frame can say by `rvfi.packet_view`, told that this executor carries the cause: the `T` record is kept, the `S` and `C` records are elided and counted, and a second read or write under one instruction is elided and counted. That is the same cut the RVFI-DII rig makes, less the trap, and the default view that K-85 holds is unchanged.

**Two consequences follow, and both narrow what a green comparison says.** The CSR and special-register writes a trap makes (`mepc`, `mcause`, `mtval`, `MEPCC`) are not compared; the cause is. And an instruction whose golden records hold more than one access compares the first access the golden trace records and no other, so the harness must report that same access for it; the port states nothing about which access it reports for such an instruction.

**Some retirements have no frame line at all**, and `rtltrace.carry` names each by retirement and reason: an access wider than the eight bytes a curated mask covers, two register writes under one instruction, a read and a write at different addresses, and two traps. `python tools/run.py testrig carry` runs every corpus member on the golden emulator, holds its trace to the manifest's digest, re-encodes it as the frame an RTL would have to write, and reports which members hold such retirements and which instruction words they are; a member with none must come back whole, and every seeded single-field change must then be reported. **Its producer is the golden model**, so what it measures is the adapter over real record shapes and the frame's carrying capacity, never the core.

A retirement the frame cannot hold is still written, carrying the part that fits, so a comparison over it diverges at that retirement rather than agreeing over a stream that skipped it.

### 4.1 The selected observation boundary

The first accepted attachment to the real scalar core uses frame version 2.
Specify and exercise its decoder, writer and current scalar probes before
expanding the core campaign. Version 1 remains the format of the existing
fixtures and recorded carrying-capacity evidence; those results establish no
version-2 or real-core acceptance.

Version 2 carries the complete commit-trace schema: each retirement's ordered
register, capability special-register, CSR, memory and trap effects. Its header
identifies the hart; continuation records carry every effect under its owning
retirement, including multiple register writes, multiple accesses, different
read/write addresses and block-width accesses. Preserve tags, exact widths,
memory encodings and trap causes. The schema and its decoder specify complete
group counts, continuation order, per-hart retirement order and PC continuity,
and refuse truncated, duplicated, misordered or unattached continuation records.
Current scalar probes
must supply the actual effects, including trap CSR writes, `cclear`, `creclaim`
and block operations; a missing effect fails the comparison rather than being
elided by `rvfi.packet_view`.

Reuse the existing adjudicator over these full records, with only the commit
schema's existing normalization. Extend the carrying-capacity and writer
fixtures with every effect shape and malformed-group refusal, and seed changes
to each newly carried field. Fixtures and golden-model round trips qualify the
transport only; the corresponding real-core programs still owe complete
comparisons. R1b owns faithful probe values under section 3, and R2 owns their
framing and comparison. The schema can be fixed and current scalar probes
qualified without a multi-hart composition. Device monitoring and ordered replay
across harts remain the later qualification of section 8.

## 5. The corpus-green predicate

**For each corpus member in the declared scope:**
1. The golden emulator run exits with HTIF success and matches the manifest's commit-trace digest.
2. The RTL harness loads the same image, enters at the same initial PC with the same reset capability grants (execute root in `PCC`, `MTCC`, and `MEPCC`; data, seal, and unseal roots in `c1`–`c3`), and stops after the retirement whose store reaches `tohost`.
3. The emitted retirement frame decodes without refusal, `rtltrace.compare` against the golden trace is complete, and the RTL HTIF exit status matches the golden verdict.

`python tools/run.py testrig adapt FRAME TRACE` checks frame decoding, trace comparison, and entry/exit completeness for a single member, but does not verify image identity, reset root grants, or the manifest digest.

**Declared scope exclusions.** The plan's predicate covers the shared corpus, but three member classes cannot pass on the scalar core under a version-1 frame:

- **Members with multi-effect or block retirements outside version-1 framing,** enumerated by `testrig carry`. Section 4.1's version-2 frame must carry these effects before the first accepted core attachment.
- **Members exercising vector or FEC units absent from the scalar core.** `testrig carry` identifies members that retire instructions from each dialect family (the vector and FEC units land at M10 after scalar bring-up), though members accessing vector CSRs via scalar CSR instructions still require manual classification.
- **Members exercising unbound SoC platform windows:** the revocation sidecar, refresh/discharge sequencer, two-class memory boundary, RoT peripherals, AIA pending array, and block device, which depend on R1c-ii's SoC top rather than the scalar core.

The gate's run configuration declares any excluded members with their class, and each remains an open finding against R2's predicate until discharged.

## 6. Generated streams over RVFI-DII

The rig's socket is the other route to the core and it needs no frame: the harness answers the version probe with version 2, carries the destination's tag in the integer extension's padding bit and each access's tag one bit above its byte mask ([the rig's dialect](differential-corpus.md#94-a-dialect-of-the-standard-packet-and-not-an-extension-of-it)), resets registers, memory and the program counter on an end-of-trace, and `testrig run` then drives it as the second executor with its generator, its seeded defects and its shrinker unchanged. The packet carries no cause, so a trap there is compared as a boolean.

**A DII run exercises a different configuration from the artifact of record.** Direct instruction injection replaces the fetch source (`RVFI_DII` in the imported configuration record, which the curated configuration sets to zero), so what a DII campaign establishes is about the datapath behind fetch and not about the fetch path.

## 7. The bounded model-checking smoke

R-15-094 places riscv-formal/rvfi as bounded-depth evidence and the cheapest bring-up gate, and its acceptance is that it grounds no refinement claim. The smoke is distinct from the Sail-generated SystemVerilog under commercial equivalence checking (R-15-090) and from the Kami/Kôika refinement (R-15-091, R-15-092): it refutes up to a depth and proves nothing beyond it.

**Predicate.** Under a riscv-formal wrapper with unconstrained instruction and data memory responses and reset asserted on cycle 1:
- no declared safety check (`insn`, `reg`, `pc_fwd`, `pc_bwd`, `causal`, `unique`) finds a counterexample within its bound;
- under the fairness assumption that every memory request completes within a bounded number of cycles, `liveness` finds no counterexample within its bound; and
- `cover` reaches a retirement of every in-scope instruction within the instruction depth, preventing vacuous passes on a pipeline deeper than the bound.

**Plan.** [tools/vos/bmc.py](../../tools/vos/bmc.py) declares the check kinds, the liveness fairness assumption, and provisional placeholder depths (to be calibrated and recorded with wall times on the first run once riscv-formal is pinned). `python tools/run.py testrig bmc` prints the plan and its instruction scope from the generated dialect table: the integer computational instructions of the base, M, bit-manipulation (`Zba`, `Zbb`, `Zbs`, `Zbkb`, `Zbkc`, `Zbkx`), and conditional-zero (`Zicond`) extensions. Non-integer constructors in those model files are excluded with stated reasons (capability-authorized loads/stores, PCC-bounded branches, collapsed fences, and capability trap/return paths); any unclassified constructor added to the model is reported as a finding.

**Wrapper-supplied instruction models.** At the revision cited by [HW-12](proof-reuse/hardware.md#hw-12-risc-v-formal-instruction-and-interface-checks), riscv-formal's generated `div`, `divw`, `rem`, and `remw` models evaluate signed division inside an expression with unsigned arms (forcing unsigned evaluation in Verilog) and test all 64 divisor bits in `remw` (F-470), and no `czero` model exists. The wrapper or a corrected upstream pin must supply faithful models for those five instructions.

**Dialect scope vs. core configuration.** Because the BMC scope is derived from the frozen dialect, any profile instruction that the imported decoder still refuses or misgates fails the instruction check: the imported decoder gates `pack`, `packh`, `packw`, `brev8`, `xperm4`, and `xperm8` on `ZKN` alongside the excluded scalar AES/SHA-2 instructions (R-15-041), and decodes `clmulr` under `RVB` despite its exclusion by R-15-048a (F-471).

**Wrapper obligations.** Present riscv-formal signals at `XLEN = 64` using the memory-encoded `rd_wdata` and the port's `order` (section 3); enable the memory fairness assumption only for `liveness`; assemble the instruction list from `bmc.py`'s scope; and supply the replacement models above. Capability tags are checked by co-simulation rather than riscv-formal.

**Prerequisites (each refused until present):**
1. `riscv-formal` pinned under `upstream/` with a license review in `THIRD-PARTY.md`.
2. Yosys, SymbiYosys, and an SMT solver provisioned in the guest lane and recorded in `THIRD-PARTY.md`.
3. The curated scalar core (R1b)—which currently elaborates under Verilator ([rtl/README.md](../../rtl/README.md#3-what-each-has-been-held-to-and-what-it-has-not))—elaborating through the formal front end with working PC, jump, address, and CSR datapaths.
4. The RVFI port obligations of section 3.

### Formal front-end candidate

Read on 2026-10-10: trial [sv-elab's 2026-09-08 release](https://github.com/povik/sv-elab/releases/tag/2026-09-08),
revision `b4fd362f4c53dc8ffab6946b9f866a6ea89e366d`, through Yosys `read_slang`
before authoring a compatibility layer for the existing smoke. Its
[pinned README](https://github.com/povik/sv-elab/blob/b4fd362f4c53dc8ffab6946b9f866a6ea89e366d/README.md)
lists plugin compatibility with Yosys 0.52–0.66 and integration from 0.67; neither
establishes that this curated core is supported. Its
[SVA lowering](https://github.com/povik/sv-elab/blob/b4fd362f4c53dc8ffab6946b9f866a6ea89e366d/src/sva.cc)
supports simple assertion expressions, supported clocks and `disable iff`, while
rejecting richer expression kinds and repetition. The
[formal fixtures](https://github.com/povik/sv-elab/blob/b4fd362f4c53dc8ffab6946b9f866a6ea89e366d/tests/various/formal_stmts.sv)
also cover immediate assertions and `$past`. Use the Yosys route: this edition's
standalone backend does not lower assertions.

Within the existing front-end prerequisite, pin the actual Yosys/plugin/dependency
closure and read its terms as [THIRD-PARTY.md](../../THIRD-PARTY.md#formal-front-end-candidate)
records. Read the curated core and wrapper without suppressing assertions or
accepting unexplained black boxes. Inspect retained assertion, assumption and cover
cells; exercise a satisfiable cover and a deliberately failing safety property.
Compare the signed arithmetic edge cases above through the formal front end and
Verilator. Record unsupported constructs and stop before a speculative parser port.
Run the bounded smoke at its declared scope; complete gate suites and comparative
benchmarks remain CI-only.

This is a candidate for R2's existing bring-up work. No front end is installed or
qualified by this reading, and no acceptance gate is added. Its possible saving is
avoided compatibility work; price that only after the actual core passes the trial.
The trial supplies no RTL-to-Sail refinement evidence.

## 8. The revocation join

[Q22a's qualification](revocation-qualification.md) supplies a bounded host model of revocation completion and reuse, and hands R2 the multi-hart, proxy and device paths. R-08-006's acceptance names the cases: retain a capability in a register across publication, spill and restore it, retain an interior-base capability, revoke a loan in progress, delay a proxy acknowledgement and leave a device transfer in flight, and none may report containment before its postcondition holds. The join is the harness input that lets those cases be decided on the RTL.

**Inputs.**

| Input | Owner | Form |
| --- | --- | --- |
| Holder and base inventory, affected bases, cores, proxies, swept locations | the admitted composition, in the shape of `revocation.Composition` | emitted per composition; the host fixture is not it |
| Schedule ledger: publication, barrier, cancellation, proxy notification and acknowledgement, device and sweep jobs | the admitted composition, in the shape of `revocation.Budget` | the declared failure bound is `Budget.bounds`' acknowledgement-failure decision |
| One retirement frame per hart | this harness | publication and sweep appear as writes to the revocation sidecar and `creclaim` retirements; core cleanup as register writes |
| Device completion events | the tag-carrying fabric's window registers (R-15-208, R-15-208a) | issue stopped, accepted writes landed, window closed, per delegated window |
| The kernel's own completion, failure and reuse reports | M4.4's kernel | writes to addresses the composition declares |

**Predicate.** Replaying the observed events in order through `revocation.py`'s transitions, a completion the kernel reports while `completion_errors` is nonempty fails; a missing acknowledgement or an outstanding device transfer must produce the kernel's failure report within the declared bound and never a completion; and a reuse the kernel reports while `reuse_errors` is nonempty fails. The bounded host model supplies no RTL completion evidence and is not a substitute for any input above.

**Instrumentation and its work owners.** Section 4.1's frame and current scalar
probes belong to the initial R2 attachment, priced in
[R2's checklist cell](../../PLAN.md#rtl-track).
They do not wait on the revocation join. The remaining instrumentation is a
separate proposal:

| Addition | What it carries | Proposal |
| --- | --- | --- |
| A device-completion monitor on the tag-carrying fabric | R-15-208a's boundary events per window | 4 to 6 h once R1c-ii binds the fabric |
| The join checker over `revocation.py` | the replay and the three decisions above, and R-08-006's cases driven as images | 4 to 6 h, with the images M4.4's |

This remaining 8 to 12 h proposal is outside R2's cell and waits on M4.4's
kernel, R1c-ii's fabric and a reviewed multi-hart composition. The split assigns
the observation work once; it claims no estimate saving or accepted evidence.
R2 still owes the complete revocation join; early scalar acceptance does not
complete that duty.

## 9. Running it

| Command | Lane | What it decides |
| --- | --- | --- |
| `python tools/run.py testrig adapt FRAME TRACE` | either | one frame against one golden trace: refused, divergent, incomplete or complete |
| `python tools/run.py testrig carry` | guest | the frame's carrying capacity over the corpus's golden traces, and that every seeded single-field change is reported |
| `python tools/run.py testrig framesim --controls --corpus` | guest | that the SystemVerilog writer's frames decode field for field as its stimulus stated, that compiled assertions stay enabled under locked runtime controls, that each seeded writer mutant is reported by that stimulus, and that every member `carry` holds whole comes back whole through it |
| `python tools/run.py testrig bmc` | either | the smoke's plan and its instruction scope; it runs nothing |
| `python tools/run.py test --only rtltrace` | either | the protocol refusals, the projection, the seeds, `carry`'s totals and their scopes, the writer mutants' anchors, the stimulus layout against its bench and this document's field table against the decoder |

**Every producer above is a fixture or the golden model.** `framesim`'s driver is a bench fed from stimulus files and `carry`'s producer is the golden trace re-encoded; they establish the adapter's handling of the protocol and of real record shapes, and the round trip of the authored format package's register form over the values they drive. The co-simulation gate's evidence is a frame the core wrote.

Guest CI's RTL lane runs `testrig framesim --controls` without the corpus or a
model-build dependency. Its assertion-policy fixture includes a passing assertion,
a failing assertion after an RTL disable attempt under the runtime lock, and the
same disable attempt without the lock. A compilation failure supplies no detection.
The reporter retains this command's outcome and native diagnostics. These controls
qualify the fixture's assertion policy, with the real-core attachment still owed.

## 10. What is owed

- The Verilator top that wraps the curated core, loads a corpus image, detects the `tohost` store and instantiates the frame writer, which waits on R1b's [core-port contract](../hardware/core-port-contract.md) stating the obligations of section 3; the curated core it wraps elaborates under Verilator.
- The port obligations of section 3, in that contract.
- The version-2 observation boundary of section 4.1, including its current scalar probes, before the first accepted core attachment.
- The declared member scope of section 5, and a disposition for the three classes it excludes.
- The bounded model-checking smoke's four inputs of section 7, the models its plan owes in place of riscv-formal's, and the depths its first run sets.
- The revocation join of section 8, with its instrumentation priced there and its joins with M4.4 and R1c-ii.
