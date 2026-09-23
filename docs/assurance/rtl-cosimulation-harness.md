# The RTL Co-simulation Harness

*R2's contract: how the curated scalar core's retirements reach the one adjudicator the corpus already uses, what the retirement frame carries and refuses, the bounded model-checking smoke the harness owes under R-15-094, and the revocation join it takes as a specified input. Section numbers here are this document's own.*

> **What exists and what does not.** The adapter exists on both sides of the frame: a SystemVerilog writer that turns one retirement into one line, and a decoder that refuses a malformed or partial frame and projects the rest onto the commit trace. Both are exercised against the golden model's own traces and against seeded field changes. **No RTL result exists.** The curated core does not elaborate yet ([the RTL tree's own account](../../rtl/README.md#3-what-each-has-been-held-to-and-what-it-has-not)), so no frame has been written by a core, no corpus member has been compared against one, and no bounded model check has run. Everything below that concerns the core is an obligation, not a measurement.

## 1. The two halves of one comparison

The golden half is the commit trace of [the differential corpus's schema, version 1](differential-corpus.md#4-the-commit-trace-schema-version-1), which the emulator writes under `--trace-commit` for each member, and whose digest the corpus manifest records. The RTL half is the core's RVFI port. Between them sit three pieces and no second adjudicator:

| Piece | Where | What it does |
| --- | --- | --- |
| Frame writer | [tools/rvfi-harness/vos_rvfi_frame.sv](../../tools/rvfi-harness/vos_rvfi_frame.sv) | One line per retirement, in the frame of section 2, converting the destination's register form to its memory encoding through the authored format package's `cap_reg_to_cap_mem` |
| Frame decoder | [tools/vos/rtltrace.py](../../tools/vos/rtltrace.py) | Refuses every frame that breaks its protocol, and projects the rest onto commit records through [rvfi.py](../../tools/vos/rvfi.py)'s projection |
| Adjudicator | [tools/vos/trace.py](../../tools/vos/trace.py) | `trace.adjudicate`, unchanged, which the corpus, the RVFI-DII rig and this adapter all call |

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
| `pc_wdata` | 16 | the next program counter; carried and compared by nothing, the commit trace having no such record |
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

Each refusal names its line and its kind, and none is ever reported as a divergence: a frame that is empty or opens with anything but the header; another version; a last line with no newline (the writer stopped mid-record); a carriage return; a line that is neither `P` nor `E`; a `P` line with the wrong number of fields or a field of the wrong width or alphabet; a flag other than 0 or 1; an `order` other than the retirement's index (a packet lost, repeated or reordered between the order's source and the writer); a register outside the 32; data or a tag on a write to x0; a cause on a retirement that did not trap; a mask that is not a low run of one, two, four or eight ones; a tag on an empty or sub-granule access; a trailer whose count differs from the lines written; anything after the trailer; and a frame with no trailer at all.

**The writer's own count makes the `order` check a check on the writer.** The imported port assigns no `order` (section 3), so the writer counts; a retirement lost between the port and the writer leaves no gap in the orders the writer assigns, and surfaces as a divergence at adjudication rather than as a refusal. A port that states its own retirement count moves the check to the right side of that seam.

## 3. What the imported port states, and what the harness must supply

Read at `core/cva6_rvfi.sv`, `core/cva6_rvfi_probes.sv` and `core/include/rvfi_types.svh` of the pinned CHERI-CVA6 datapath. These are obligations on the core-port contract R1b owns and the harness consumes, and each is a finding until that contract states it.

| Frame field | The port at the pin | What the harness needs |
| --- | --- | --- |
| a retirement | `valid` is raised on a synchronous exception only for the three environment-call causes and the capability cause | every synchronous exception retired, so the writer samples `valid` or `trap`, as the pinned TestRIG harness under `corev_apu/tb/tb_testRig_cheri/` already does |
| `order` | declared and assigned nowhere | a retirement count at the port, so the decoder's check reaches the core's side of the writer |
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

## 5. The corpus-green predicate

**For each corpus member in the declared scope:** the golden run reaches a HTIF verdict of success and its trace matches the digest the manifest records; the RTL harness loads the same image, enters at the same first program counter with the same reset root pair in place, and stops after the retirement whose store reaches `tohost`, which is where the emulator stops; the frame it wrote decodes; `rtltrace.compare` against the golden trace is complete; and the RTL's HTIF verdict is the golden one. `python tools/run.py testrig adapt FRAME TRACE` decides the middle three for one member.

**The scope has to be declared, and declaring it is not this document's act.** The plan's predicate names the shared corpus whole, and three classes of member cannot pass on the curated scalar core through a version-1 frame:

- **Members whose retirements no frame line holds**, which `testrig carry` enumerates by name at each revision. Carrying them needs the frame extension priced in section 8 and core-side probes behind it.
- **Members that exercise a unit the scalar core does not carry.** `testrig carry` names, for each model family the dialect table decodes, the members whose golden runs retire a word of it, so a member retiring a vector word is found by its trace rather than by its description; the plan puts the vector and FEC units at M10 after scalar bring-up. A member that reads a vector CSR through the CSR instructions is not found that way, and is the one case in this class a reader still decides.
- **Members that exercise a platform window the SoC top has not bound**: the revocation sidecar, the refresh and discharge sequencer, the two-class memory boundary, the Root of Trust peripherals, the AIA pending array and the block device. Whether each passes is a property of R1c-ii's top and not of the core.

The scope is therefore a declared list the gate's run configuration carries, each excluded member with its class, and it is reported as a finding against R2's predicate rather than decided here.

## 6. Generated streams over RVFI-DII

The rig's socket is the other route to the core and it needs no frame: the harness answers the version probe with version 2, carries the destination's tag in the integer extension's padding bit and each access's tag one bit above its byte mask ([the rig's dialect](differential-corpus.md#94-a-dialect-of-the-standard-packet-and-not-an-extension-of-it)), resets registers, memory and the program counter on an end-of-trace, and `testrig run` then drives it as the second executor with its generator, its seeded defects and its shrinker unchanged. The packet carries no cause, so a trap there is compared as a boolean.

**A DII run exercises a different configuration from the artifact of record.** Direct instruction injection replaces the fetch source (`RVFI_DII` in the imported configuration record, which the curated configuration sets to zero), so what a DII campaign establishes is about the datapath behind fetch and not about the fetch path.

## 7. The bounded model-checking smoke

R-15-094 places riscv-formal/rvfi as bounded-depth evidence and the cheapest bring-up gate, and its acceptance is that it grounds no refinement claim. The smoke is distinct from the Sail-generated SystemVerilog under commercial equivalence checking (R-15-090) and from the Kami/Kôika refinement (R-15-091, R-15-092): it refutes up to a depth and proves nothing beyond it.

**Predicate.** For the curated scalar core under a riscv-formal wrapper, with instruction and data memory responses unconstrained and reset held for the first cycle, no check of the declared set finds a counterexample within its declared depth, and riscv-formal's cover check reaches a retirement of the in-scope forms within the instruction depth. The second clause is what keeps the first from being vacuous: a pipeline deeper than the bound retires nothing inside it, and every instruction check then holds for no reason.

**Plan.** [tools/vos/bmc.py](../../tools/vos/bmc.py) declares the check kinds (`insn`, `reg`, `pc_fwd`, `pc_bwd`, `causal`, `unique`, `liveness`, `cover`) and their depths, and `python tools/run.py testrig bmc` prints the plan with its instruction scope read out of the generated dialect table. The scope's rule is a set of Sail constructors, the integer computational forms of the base and M extensions whose semantics riscv-formal's RV64IM model shares with this dialect, and every other base or M constructor is excluded with its reason: loads and stores are authorized by a capability, branches trap on PCC's bounds, fences are collapsed, and traps and returns go through the capability special registers. A constructor the model gains that is neither in scope nor excluded is a finding the command reports.

**Wrapper obligations.** The wrapper presents riscv-formal's signals at `XLEN` 64, with register data as the memory encoding the frame's `rd_wdata` carries, and an `order` the port states (section 3). riscv-formal checks no tag; the tag's correctness is the co-simulation's to decide.

**What it waits on, each refused by name until present:** riscv-formal pinned under `upstream/` with its licence read at the pin and a THIRD-PARTY.md row before any of its files is used; Yosys, SymbiYosys and one SMT solver provisioned in the guest lane with their own rows; the curated core elaborating (R1b); and the port obligations of section 3. None is present at this revision, and the check names and meanings in the plan are riscv-formal's as its documentation states them, to be re-read at the pin before a run.

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

**Instrumentation it needs, priced as a proposal.** The version-1 frame carries none of three things the join reads, and each is a harness or core addition:

| Addition | What it carries | Proposal |
| --- | --- | --- |
| Frame version 2: a hart field in the header; continuation lines for the further accesses and register writes version 1 refuses or elides; `C` and `S` records from the port's CSR record and the capability special-register probes | per-hart frames, `creclaim` and the block operations whole, and the trap CSR writes version 1 does not compare | 5 h for the decoder, writer and fixtures, plus the core-side probes, 3 to 6 h depending on R1b's port |
| A device-completion monitor on the tag-carrying fabric | R-15-208a's boundary events per window | 4 to 6 h once R1c-ii binds the fabric |
| The join checker over `revocation.py` | the replay and the three decisions above, and R-08-006's cases driven as images | 4 to 6 h, with the images M4.4's |

That is 16 to 23 h in total, outside R2's cell as priced, and it waits on M4.4's kernel, R1c-ii's fabric and a reviewed multi-hart composition in any case.

## 9. Running it

| Command | Lane | What it decides |
| --- | --- | --- |
| `python tools/run.py testrig adapt FRAME TRACE` | either | one frame against one golden trace: refused, divergent, incomplete or complete |
| `python tools/run.py testrig carry` | guest | the frame's carrying capacity over the corpus's golden traces, and that every seeded single-field change is reported |
| `python tools/run.py testrig framesim --corpus` | guest | that the SystemVerilog writer's frames decode field for field as its stimulus stated, and that every member `carry` holds whole comes back whole through it |
| `python tools/run.py testrig bmc` | either | the smoke's plan and its instruction scope; it runs nothing |
| `python tools/run.py test --only rtltrace` | either | the protocol refusals, the projection, the seeds, the stimulus layout against its bench and this document's field table against the decoder |

**Every producer above is a fixture or the golden model.** `framesim`'s driver is a bench fed from stimulus files and `carry`'s producer is the golden trace re-encoded; they establish the adapter's handling of the protocol and of real record shapes, and the round trip of the authored format package's register form over the values they drive. The co-simulation gate's evidence is a frame the core wrote.

## 10. What is owed

- The Verilator top that wraps the curated core, loads a corpus image, detects the `tohost` store and instantiates the frame writer, which waits on R1b's elaborating core and its port contract.
- The port obligations of section 3, in that contract.
- The declared member scope of section 5, and a disposition for the three classes it excludes.
- The bounded model-checking smoke's four inputs of section 7.
- The revocation join of section 8, with its instrumentation priced there and its joins with M4.4 and R1c-ii.
