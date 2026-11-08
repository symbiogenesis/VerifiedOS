# The Differential Corpus and the Commit-Trace Schema

*The artifact **M0.12** delivers, and the one every later executor of the frozen profile is checked against. It is versioned because it is evidence rather than scaffolding: a milestone that reports a figure against this corpus reports it against a stated edition of it.*

> **Two halves, and each is owned once.** This document says what the corpus is, what each member exercises, how a member is written, and what a trace record means. [corpus/manifest.json](../../corpus/manifest.json) says what has been *measured*: each member's check count, its commit trace's length, and that trace's digest. Nothing appears in both. `tools/check.py` holds the membership equal in both directions, so a program added to one and not the other is a finding.

**Section references.** Each section citation links to its owning document: the plan for milestones and the harness, the frozen ISA profile for encoding and the admitted surface, and this document for its schema and procedures.

## Why this document exists

The [project plan](../../PLAN.md) [§10](../../PLAN.md#10-emulating-the-hardware-reference-execution-and-rtl-comparison) defines the shared corpus and trace boundary. The Sail emulator executes the corpus and emits its commit traces; R2 owes the independent RTL execution and comparison through the [co-simulation harness](rtl-cosimulation-harness.md). A versioned corpus and written schema let both executors compare behavior against the same observation contract.

The corpus supplies whole-program regression evidence for the curated model. Unmodified integer-addressed `riscv-tests` programs lack the tagged memory authority this purecap profile requires, so they cannot serve as its whole-program corpus. The authored members also exercise the profile's net-new and bespoke instructions, alongside their model-level properties.

## 1. What the corpus is

The manifest lists purecap programs in the frozen dialect, each running to completion on the curated Sail emulator and reporting through HTIF. Together they exercise the base ISA, the adopted extensions, the transplanted and re-parameterized capability surface (M0.6e, M0.6f), the profile's net-new instructions (M0.6g, M0.6h), the two-class memory plan and sequencer (M0.14, M0.16), the Ztso memory model (M0.7), the `mhartid`-indexed core-class roster (M0.8a), per-element capability-checked vector memory (M0.8b), and the frozen Keccak unit (M0.8d).

| Member | What it exercises |
| --- | --- |
| [`gallina-hello`](../../corpus/gallina-hello.s) | Gallina character function lowered through Rupicola and the accepted purecap compiler; greeting bytes and tagged pointer stores and reloads in dedicated image-data slots; [reproduction recipe](../../tools/bedrock2-lowering/HELLO.md) |
| [`kernel-instance`](../../corpus/kernel-instance.s) | generated snapshot of the actual signed-release scalar kernel: exact handoff capabilities and descriptor, root/window bounds refusals, qualified saved-image revocation, complete context restores and two timer-driven slots; [reproduction recipe](../../kernel/README.md#finite-compiled-target) |
| [`base-integer`](../../corpus/base-integer.s) | RV64I arithmetic, logic, shifts, the W forms, every branch condition, and the zero register |
| [`base-memory`](../../corpus/base-memory.s) | loads and stores at every width through a capability derived from the reset root, byte order, sign and zero extension, and a narrowed authority |
| [`mul-div`](../../corpus/mul-div.s) | the M extension, including division by zero, the signed overflow, and the W forms |
| [`bitmanip`](../../corpus/bitmanip.s) | `Zba` shift-and-add, `Zbb` logic, counting, rotation and extension, `Zbs` single-bit, and the `Zbkb`/`Zbkc`/`Zbkx` crypto forms |
| [`vector-bitcount`](../../corpus/vector-bitcount.s) | generated native vector leading/trailing-zero and population counts against an independent fixed-width integer oracle, including the modulo-width CTZ/popcount identity, legal vector geometry, zero length, masks, undisturbed tails and in-place destinations; [the qualification contract](vector-bitcount.md) owns scope and acceptance |
| [`atomics`](../../corpus/atomics.s) | `Zaamo` at word and doubleword, `Zabha` at byte and halfword, the comparing forms, and the tag an atomic's store half clears |
| [`zicond-csr`](../../corpus/zicond-csr.s) | `Zicond` in both polarities and as an if-conversion, the writable and read-only halves of the CSR bank, and `cspecialrw` over MTDC |
| [`cap-inspect`](../../corpus/cap-inspect.s) | the inspection surface over the split root pair, the trap capabilities, and the null capability |
| [`cap-derive`](../../corpus/cap-derive.s) | the monotone derivations, the untagged result a non-monotone one yields, the permission lattice under `candperm`, and `csealentry` |
| [`cap-memory`](../../corpus/cap-memory.s) | the tag plane under capability and data stores, granule keying, `cloadtags` and `cbo.zero` over one block, and load transitivity |
| [`cap-control`](../../corpus/cap-control.s) | sentry roles at `cjal` and `cjalr`, the backward edge a call mints, the forward edge `csealentry` mints, and the bounds a sentry carries into PCC |
| [`cap-trap`](../../corpus/cap-trap.s) | nine traps through MTCC and back through MEPCC: six capability violations with their `mtval` detail, an alignment exception, an unallocated CSR address, and an unallocated instruction encoding whose two low bits are not `11`, whose `mtval` is the whole 32-bit word |
| [`cap-select`](../../corpus/cap-select.s) | `cmovz`/`cmovn` in both polarities and over data, the untouched destination an untaken arm leaves, and `cclear` over each half of the merged file |
| [`cap-indexed`](../../corpus/cap-indexed.s) | `cld`/`csd` at each scale against the displaced access they replace, and the five faults they raise on the authority rather than on an intermediate |
| [`cap-revoke`](../../corpus/cap-revoke.s) | the revocation bitmap through its window, the tag a revoked load clears, the base the bit is keyed by, and the tags `cloadtags` reports as stored |
| [`cap-reclaim`](../../corpus/cap-reclaim.s) | `creclaim` over a group holding two objects with different bases, the surviving tags it returns, the bits it leaves untouched, its idempotence, its group boundary, and the clear it lands in memory where the load filter's lands in a delivered value |
| [`platform-aia`](../../corpus/platform-aia.s) | `fence.t` disturbing nothing, and the machine-level pending array under sends, reads, clears, and the reserved identity |
| [`platform-scrub`](../../corpus/platform-scrub.s) | `cbo.scrub` preserving data and tags where a store of the same bits clears them, its two permissions and its refusal over IO memory, and `vmclear` clearing the vector register file and the vector CSRs with the extension-context gate off, over a configuration and a file the program dirtied first rather than over the values reset leaves |
| [`platform-memclass`](../../corpus/platform-memclass.s) | the boundary between the two static latency classes: a capability's round trip, the tag a data store clears, `cloadtags`, `cbo.zero`, `cbo.scrub`, an atomic, and a bounds violation all answering the same on the second class as on the first, and the revocation filter keyed by the loaded capability's base rather than by the class of the slot holding it |
| [`platform-memseq`](../../corpus/platform-memseq.s) | the refresh and discharge sequencer from the only side a program reaches it from: its window refused in both directions at every width and through a capability-width access, the whole region rather than one address, the unclaimed IO page above it answering where the window does not, and the second class unmoved by an interval of ticks |
| [`memory-model`](../../corpus/memory-model.s) | `fence` collapsed to a drain or a no-op: the draining arm and the minimal one, the no-op arms with `fence.tso` among them, the I and O bits this profile reads where upstream ignores them, a store already visible to the next load, the reserved `fm` that traps where the base ISA would execute it, and the `rs1`/`rd` class that stays legal and ignored |
| [`platform-coreclass`](../../corpus/platform-coreclass.s) | the core class from the only side a program reaches it from: the identity `mhartid` indexes the composed roster with, inert on a read and trapping on a write, and the geometry `vlenb` carries from the class table, both unmoved by the partition switch's eager zeroize and its flush where the vector configuration beside them is scrubbed, and both unmoved by the extension-context gate a partition can turn off for itself |
| [`vector-memory`](../../corpus/vector-memory.s) | the capability semantics of the vector memory surface: the check landing per element on the unit-stride, indexed and runtime-strided forms, the violation naming the base register the access took its authority from rather than the vector destination, the tag a vector store clears on the granule it overwrites, and the masked-off element that raises nothing, writes nothing, and leaves the granule it would have covered standing bit for bit |
| [`vector-geometry`](../../corpus/vector-geometry.s) | the one class-table figure the instruction set carries: `vlenb` against the VLMAX a configuration instruction derives from it, the whole-register pair moving exactly a register's worth whatever `vl` says, and the element that reaches past an authority half a register wide, with every extent derived from `vlenb` rather than written down so that the program runs unchanged at VLEN=256 and at VLEN=4096 |
| [`keccak-perm`](../../corpus/keccak-perm.s) | the frozen Keccak permutation as an instruction stream against the FIPS 202 and NIST ACVP known answers: both round counts over the 2048-bit element group at the C class's LMUL=8, the in-place form and the separate-destination form, one padded SHA-3-256 block whose result fixes the lane order, the unassigned round count that traps, the capability check on the vector load carrying the group, and the extension-context gate this instruction folds in where `vmclear` does not |
| [`platform-rot`](../../corpus/platform-rot.s) | the Root of Trust's four peripherals from the only side a program on the C-class emulator reaches them from: the OTP window's lifecycle read and its one-way burn door, the entropy root's draw, the counter file in both directions, the watchdog in both directions, a capability-width access and a narrower one, the last doubleword of a window rather than its first, and the unclaimed IO page above them answering where the four windows do not |
| [`block-authority`](../../corpus/block-authority.s) | generated block-device authority campaign: valid full-block write/readback, untagged and underbounded loads/stores, missing-load and missing-store permissions; exact trap cause/detail/site, control and staging preservation, and complete medium readback through valid authority |
| [`fec-surface`](../../corpus/fec-surface.s) | the FEC decoders' surface from the only side a program on the C-class emulator reaches it from: both mnemonics refused on a composed hart the roster attaches no decoder to, the opcode and `funct3` the pair shares, the code family as the sub-opcode with nothing else moving with it, each operand in the field the form names, and the descriptor register whose contents reach no field of the encoding, every word read back out of the trap value rather than written down |

**The version is a commitment and the digest is a measurement.** `version` in the manifest names the edition; a member added, removed, or changed in what it asserts advances it. `trace_schema` names the record grammar of [§4](#4-the-commit-trace-schema-version-1) below; a record type added or a field widened advances that. Each member's `digest` is the fingerprint of its commit trace, so a model change that alters what a program *does* is a finding at the next run rather than a surprise at the next milestone; `run.py model corpus --refresh` is how a deliberate change is recorded, and the edit shows up in review as a moved digest beside the model change that moved it.

The separate [reviewed image baseline](../../tools/corpus-image-baseline.json)
binds each member's source and encoded image bytes. `python tools/run.py
corpus-images check` and the composer regression test compare every member without
rewriting evidence. `corpus-images extend` records additions only after every old
source and image remains identical; a changed or removed member requires a separately
reviewed baseline update. The migration record identifies the aggregate image fixture
reproduced before these per-member records were written. Image agreement is an encoder
regression check and supplies no emulator or trace verdict.

The block-authority member is generated by `python tools/run.py block-authority emit`
from the composition and the profile's Sail exception and permission owners.
`block-authority check` and `test --only block_authority` reject stale output.
The existing generated-artifact registry also holds this member to its owners,
so the integration repair regenerates it with the other host-produced artifacts.
The generator bounds its input fixture to 256 bytes as a corpus resource limit;
configuration admission remains the emulator's decision. The campaign verifies
every modeled medium byte, using separate refused-command trials to observe
unchanged medium and preserved staging. Its trap handler rejects unexpected
causes, wrong fault sites and continuations reached without refusal.
`test --only block_authority --slow` in the provisioned guest additionally executes
wrong-byte, missing-refusal and wrong-cause negative controls. The
[M5.3c contract](../implementation/contracts/block-device-prerequisites.md#architectural-authority)
limits this evidence to architectural access refusal and modeled device state;
kernel authority distribution and storage integration remain separate obligations.
The full corpus command additionally runs [the generated persistence
campaign](../../tools/vos/block_persistence.py), outside the single-run manifest:
write/reopen and flush/reopen each use separate emulator processes, compare the
complete medium and retain image identities and input-event receipts. A wrong-byte
reader and a reader reopened from the original fixture must refuse. These device
checks do not establish storage authentication or crash recovery.

## 2. Writing a member

Corpus programs follow five machine-driven conventions:

- **`gp` names the active check.** Each check sets `li gp, N` and branches to `fail` on mismatch; `fail` writes `(gp << 1) | 1` to `tohost` and `pass` writes `1`, matching the `riscv-tests` HTIF exit-code convention.
- **Save the store-side root from `c1` first.** Reset provides two root capabilities because no admitted permission set holds both store and execute: the execute root is in `PCC` and the store root is in `c1` (R-15-007l, R-15-007p, [step_ext.sail](../../model/model/postlude/step_ext.sail)). Because `c1` is also the link register, every member begins with `cmove c8, c1` and derives data authorities from `c8`.
- **Every memory access derives explicit authority.** There is no default data capability or integer-addressed access (R-15-001c); `li` loads an address and `csetaddr` derives an authority from the root. Code and read-only data use `la` (`auipcc` + `cincoffsetimm`) to derive a capability from `PCC`, which faults on store.
- **Keep capabilities in `c8` and above.** Integer and capability names alias the same merged register file (for example, `c5` and `t0`), so keeping capabilities out of the `t` registers avoids clobbering derived authorities.
- **Standard six-line exit sequence.** `fail` encodes `gp`, `pass` sets `1`, `exit` derives the `tohost` capability and stores the verdict, and `halt` spins after the emulator stops on the HTIF write.

## 3. The assembler

Because no upstream toolchain assembles this purecap dialect, the tools lane provides a self-contained Python assembler. **M1.4′** extended it to cover the purecap backend's emitted instruction mix, **M1.4** pairs it with LLVM disassembly and object tooling, and [tools/vos/compose.py](../../tools/vos/compose.py) links backend images into the same ELF container. Replacing the assembler or composer requires a reviewed contract. The corpus path spans three modules:

- [tools/vos/dialect.py](../../tools/vos/dialect.py) loads [tools/generated/dialect-table.json](../../tools/generated/dialect-table.json), which [tools/vos/dialectgen.py](../../tools/vos/dialectgen.py) generates from the model's `mapping clause encdec` and `assembly` clauses in the Sail bundle (checked by **K-88**). Only `fence` remains hand-written because the emitter leaves its `assembly` clause as unstructured text. Where the curated model differs from the RISC-V manuals—`auipcc`, `cjal`, and `cjalr` reuse the base encodings of `auipc`, `jal`, and `jalr`; `lc` sits at MISC-MEM `funct3` `010` beside `cbo.zero`; and `sc` is the capability store rather than store-conditional—the encoder follows the model.
- [tools/vos/asm.py](../../tools/vos/asm.py) parses labels, expressions, data directives, arbitrary-width `li` constants, and PC-relative `la` pairs, iterating layout to a fixed point.
- [tools/vos/image.py](../../tools/vos/image.py) writes the minimal ELF expected by the emulator: physical `PT_LOAD` segments and a `.symtab` containing `tohost`.

**Deliberate omissions:** no relocations or object files (images are position-fixed under R-15-002b and R-15-036l), no linker scripts, and no macro processor.

**Scoped encoder omissions:**
- The dictionary bundle fetch format ([isa-profile.md](../hardware/isa-profile.md) [§1.1](../hardware/isa-profile.md#11-the-instruction-encoding)) is not yet modeled, so images contain canonical 32-bit instructions.
- The matrix instruction surface is deferred to the second-act freeze item R-15-014a (ix), conditioned on R-15-116's dense-GEMM margin, and no instruction enters the profile by inheritance (R-15-007j). By contrast, the FEC mnemonics (`ldpcdec` and `polardec`) are in the frozen profile and generated encoder table (R-15-119b).

**Vector and encoder coverage.** The vector members cover per-element capability checks ([`vector-memory`](../../corpus/vector-memory.s)), geometry ([`vector-geometry`](../../corpus/vector-geometry.s)), bit counts ([`vector-bitcount`](../../corpus/vector-bitcount.s), scoped by [vector-bitcount.md](vector-bitcount.md)), and Keccak ([`keccak-perm`](../../corpus/keccak-perm.s)). The generated encoder table includes additional admitted instructions that no corpus member yet executes; whether the table should carry the full admitted surface or a declared subset remains an open M1.4′ finding.

**Hand-written `.word` directives.** Assembling via a mnemonic checks operand kinds, register classes, and immediate ranges against the dialect table. A raw `.word` bypasses those checks and is permitted only on three grounds:

- **The encoder cannot express it.** The check targets a bitfield held constant by the dialect row (such as nonzero `fm`, `rd`, or `rs1` in `fence` in [`memory-model`](../../corpus/memory-model.s), or an unallocated 32-bit instruction with low bits other than `11` in [`cap-trap`](../../corpus/cap-trap.s)).
- **The encoder refuses it.** The `vkeccak.vi` row rejects round counts other than 12 or 24, so [`keccak-perm`](../../corpus/keccak-perm.s) uses `.word` to verify that an unassigned round count traps (R-15-057a).
- **The word is what the reader must see.** Writing to read-only `mhartid` ([`platform-coreclass`](../../corpus/platform-coreclass.s)) or reading a deleted PMP CSR ([`cap-trap`](../../corpus/cap-trap.s)) is expressible as an instruction, but is written as `.word` so the listing makes the deliberate illegal access explicit.

**"Not yet in the encoder" is never a valid ground.** **K-72** checks the table below against all `.word` directives in the corpus in both directions and verifies each row's ground against the assembler.

| Member | Word | Ground | Reading |
| --- | --- | --- | --- |
| [cap-trap](../../corpus/cap-trap.s) | `0x3B0022F3` | the word is what the reader must see | `csrrs t0, 0x3b0, zero` |
| [cap-trap](../../corpus/cap-trap.s) | `0x00100290` | the encoder cannot express it | `addi t0, zero, 1` |
| [keccak-perm](../../corpus/keccak-perm.s) | `0x0170200B` | the encoder refuses it | `vkeccak.vi v0, v0, 23` |
| [memory-model](../../corpus/memory-model.s) | `0x1330000F` | the encoder cannot express it | `fence rw, rw` |
| [memory-model](../../corpus/memory-model.s) | `0x0332830F` | the encoder cannot express it | `fence rw, rw` |
| [platform-coreclass](../../corpus/platform-coreclass.s) | `0xF1429073` | the word is what the reader must see | `csrrw zero, mhartid, t0` |

**Reading** is the instruction text corresponding to the `.word`. On the first two grounds, assembling **Reading** must *not* produce **Word** (if an encoder change makes it assemble to **Word**, the ground has expired and **K-72** reports it). On the third ground, assembling **Reading** must produce **Word** exactly.

## 4. The commit-trace schema, version 1

One record per retired instruction and one per effect under it, the effects following the instruction that caused them. Every field is fixed-radix, so a record is comparable as a string and a diff names a behaviour rather than a rendering. Hexadecimal is uppercase and unprefixed; counts are decimal.

| Record | Fields | What it says |
| --- | --- | --- |
| `I` | order, pc, insn | an instruction retired at `pc`, with the 32-bit word it decoded |
| `X` | reg, tag, value | a write to one of the 32 registers of the merged file |
| `S` | scr, tag, value | a write to one of the capability registers outside that file |
| `C` | csr, value | a CSR write |
| `R` | addr, width, tag, value | a data read of `width` bytes |
| `W` | addr, width, tag, value | a data write of `width` bytes |
| `T` | interrupt, cause | a trap taken |

**The schema is capability-widened in exactly the places a capability is wider than an integer**, and the plan's [§10](../../PLAN.md#10-emulating-the-hardware-reference-execution-and-rtl-comparison) list of what it carries, *"PC, instruction, register and memory effects, plus tag, bounds, permissions, and seal state"*, is read off these records this way:

- A register's **value** is its 64 data bits, which are its integer reading, and the **tag** is the one bit of a capability that reading cannot show (R-15-007i). Together they are the whole register. Permissions, object type, exponent and the two bounds mantissas are the fields of those 64 bits, at the offsets [isa-profile.md](../hardware/isa-profile.md) [§4.1](../hardware/isa-profile.md#41-the-capability-format) fixes, so the record carries them by carrying the encoding; **base and top are the *decode* of the bounds triple**, and the rig does not re-derive them, because a second implementation of the bounds algorithm inside the trace reader is a second place for it to be wrong.
- The value is the register's **memory** encoding, the same bits a store writes and a load reads, so a register record and a memory record of the same capability are the same string. That is the null-capability transform's doing and it is why an all-zeroes granule reads back as untagged NULL (R-15-182).
- A memory access carries **the tag of the access** rather than the tag in memory. A capability load asks for the metadata and reports what it got; a data load does not ask, and reports `0`, which is a true statement about the value it delivered.
- The four capability registers outside the merged file get records of their own, because none of them appears in the register-file trace: `cspecialrw` writes them, and so does every trap.

**Four things the schema does not carry**, each named rather than left to be discovered:

1. **Instruction fetches.** They carry nothing the `I` record does not, they arrive in two 16-bit granules under this profile, and no `rvfi` port reports them, so an executor that fetched differently could not be compared on them anyway.
2. **PCC.** Its address is the `I` record's `pc`; its bounds and permissions change only where a control transfer or a trap installs them, and a program that wants to see that reads PCC with `cspecialrw`, which produces an `X` record.
3. **CSR reads.** A read is not an effect.
4. **The `order` field, when comparing.** It counts retires from the start of a run, so two executors entering through different reset vectors disagree on it while agreeing on everything else. It is emitted, because it is what makes the stream readable, and dropped from the compared record.

## 5. The transport

The trace **reuses the RVFI plumbing**, which is what the curation preserved it for. The generic callbacks already report every effect; RVFI's own callbacks class assembles them into a per-instruction packet; the commit trace is a second class in the same slot, assembling them into a per-instruction record group ([riscv_callbacks_commit.cpp](../../model/c_emulator/riscv_callbacks_commit.cpp)), emitted under `--trace-commit`.

Two halves of that reuse are worth stating, because they went in opposite directions.

**The packet is widened where it can be.** `rvfi_wX` now carries the tag of the value written to `rd`, in a bit taken from the Integer packet's padding, and `rvfi_read`/`rvfi_write` carry the tag of a memory access as **one bit above the byte mask**: an access of *w* bytes sets mask bits 0 through *w* − 1 for its bytes and bit *w* where it carried a tag. That is the extension the CHERI-widened 32-bit masks were sized for, and it closes the two `TODO`s the tree carried. The RTL's `rvfi` port is what this half is for (the plan's [§11](../../PLAN.md#11-building-an-fpga-from-it-all)).

**The packet is not the transport.** It is fixed-size and holds one memory access per instruction, so it cannot express `cbo.zero`'s 64-byte block write or `cloadtags`' eight granule reads, and it has no field for the capability registers outside the merged file. The record stream carries the whole schema; the packet carries the subset it can, for the executor whose port emits packets. Where they overlap they say the same thing.

## 6. How a run is adjudicated

`python tools/run.py model corpus` assembles each member, runs it once, and checks two verdicts:

* **HTIF exit status:** `1` on pass, or `(gp << 1) | 1` identifying the failing check.
* **Commit-trace digest:** the normalized commit trace must match the digest in `corpus/manifest.json`.

When comparing against a second executor, [tools/vos/trace.py](../../tools/vos/trace.py) aligns and adjudicates the normalized commit records instruction by instruction. The M0.4 oracle is not a second executor for this corpus because it implements 128-bit ISAv9 with hybrid mode and a default data capability rather than the 64+1-bit purecap profile. With M2's CHERI-QEMU fork struck ([§12](../../PLAN.md#12-build-order-milestones-and-execution-state)), the standing second executor is **the RTL under Verilator co-simulation (R2)**, compared through `trace.py` over both the RVFI-DII rig (S11) for generated streams and the retirement frame ([rtl-cosimulation-harness.md](rtl-cosimulation-harness.md)) for corpus programs.

## 7. What the corpus cannot exercise yet, and why

The table distinguishes missing execution cases from missing model or implementation support. The model already supplies the reset sealing authorities and the vector instructions named below; those omissions require corpus cases. Other rows depend on the stated model, composition or implementation work.

| Absent | Why | Closes at |
| --- | --- | --- |
| `cseal`'s success case | [`ext_reset`](../../model/model/postlude/step_ext.sail) grants separate object-type authorities in `c2` and `c3`. The existing `cap-derive` case instead uses the store-side memory root and exercises refusal; it does not consume the seal root for a successful case. | a member exercising successful sealing from the reset object-type authority |
| An access-system-registers violation | Reaching it means executing without ASR on PCC, which on this machine is a one-way door: nothing in reach gives it back. | a composed distribution with a non-privileged compartment, the plan's [§5](../../PLAN.md#5-kernel-coq) |
| `cbo.scrub` correcting anything, and its fail-stop on an uncorrectable error | The model has no error model: no codeword carries a syndrome, so nothing is correctable and nothing is uncorrectable, and inventing a fault-injection register would model the harness rather than the machine. The refusals *are* exercised, and the detection joins the error path the block read already returns on. | an error model, which no milestone carries: the plan's [§10](../../PLAN.md#10-emulating-the-hardware-reference-execution-and-rtl-comparison) harness models ECC as no-ops-with-latency, and the sentinel the correction telemetry goes to is a class in the roster rather than an instrument |
| The exit-path discharge and the refresh cadence themselves | The sequencer is a register slave the RoT drives while every requester is held in reset, so no instruction reaches it and no program can start one, observe one, or time one (R-15-247h). What a program exercises is the refusal, which is the whole of the requester-side contract; the mechanism is asserted as properties over the model instead. | a composed image whose RoT firmware drives it, M3.5's measured boot. M3.1 landed the sequencer as a register slave and M3.2 the firmware as a Gallina statement, and neither puts a driven sequencer under a running program, so the absence outlived both |
| A revocation sweep with more than one covered interval | The covered union is a predicate over one composition-fixed interval, because one composed image has one revocable region; a second interval is a clause in that predicate rather than a mechanism. | the composed initial distribution, the plan's [§3](../../PLAN.md#3-m-mode-firmware-coq) |
| The matrix datapath | The class is declared and its geometry is, and the instruction surface is a second-act item: R-15-116 admits the unit only against a sustained dense-GEMM margin, which is a measurement against generated output, so R-15-014a carries the surface at (ix) rather than a milestone carrying it now. The vector datapath is no longer absent here: `vector-memory` and `vector-geometry` run it. | the freeze's second act, R-15-014a (ix) |
| An FEC decode that retires | The surface is in the model and [`fec-surface`](../../corpus/fec-surface.s) runs it, but only as far as the refusal: the gate is the composed roster entry's FEC attachment, the golden emulator is the C class, and the reference composition attaches the decoders to the pinned radio V pair, so no program this rig runs is on a hart that carries one. What a program reaches is the encoding and the trap; the pass, its two authorities, and the descriptor's refusals are asserted as properties over the model instead. | a composed image on a decoder-bearing hart, the plan's [§3](../../PLAN.md#3-m-mode-firmware-coq) |
| Vector arithmetic beyond the bit-count campaign, and the segment forms of vector memory | The generated bit-count campaign covers its count and supporting arithmetic instructions. The remaining arithmetic and segment forms lack corpus cases; the model and generated encoder already carry them. | members exercising those remaining forms |
| The dictionary bundle format | A fetch container the model does not implement. | the freeze, the profile's [§1.1](../hardware/isa-profile.md#11-the-instruction-encoding) |

## 8. What CI holds

Two instruments, and they run in different places for a reason: one needs a built emulator and one needs nothing but Python, so a corpus that has stopped assembling is a finding on the host rather than a surprise in WSL.

| Predicate | Where |
| --- | --- |
| every member assembles | `tools/check.py` (host) |
| the manifest and this document name the same members, in both directions | `tools/check.py` (host) |
| each member's recorded check count is the count its source carries | `tools/check.py` (host) |
| every member runs to a HTIF verdict of success | `tools/run.py model corpus` (WSL) |
| every member's commit trace matches the digest the manifest records | `tools/run.py model corpus` (WSL) |
| the wire format of [§9](#9-the-rvfi-dii-rig) below is what the codec encodes and decodes | `tools/run.py test` (host) |
| the emulator negotiates RVFI-DII v2 and retires an injected instruction | `tools/run.py testrig handshake` (WSL) |
| a generated stream's packets and its commit records agree, one run, both dialects | `tools/run.py testrig bridge` (WSL) |
| every seeded defect is reported, and no unseeded run diverges | `tools/run.py testrig run` (WSL) |
| an RTL retirement frame is refused, projected and adjudicated as its contract states | `tools/run.py test` (host) |

## 9. The RVFI-DII rig

*[§4](#4-the-commit-trace-schema-version-1) above is the trace format the plan's [§10](../../PLAN.md#10-emulating-the-hardware-reference-execution-and-rtl-comparison) sentence names; this is the runner it has never had, and this section says what the wire is, where it meets [§4](#4-the-commit-trace-schema-version-1), and what the rig can drive today.*

**The rig explores instruction streams beyond the fixed corpus campaigns.** A corpus member exercises its declared cases; a verification engine generates instruction streams, consumes execution traces, adjudicates two executors against each other, and **shrinks a counterexample automatically**, which no corpus can do at all. The instrument is [tools/run.py testrig](../../tools/vos/cli/testrig.py) over [vos/rvfi.py](../../tools/vos/rvfi.py), the wire format, and [vos/vengine.py](../../tools/vos/vengine.py), the generator, the socket and the shrinker; adjudication is [vos/trace.py](../../tools/vos/trace.py)'s, unchanged, so there is one adjudicator here and not two.

### 9.1 The wire, and where it is read from

**RVFI-DII is not this repository's format and is read at its own source**, which is `RVFI-DII.md` in CTSRD-CHERI's TestRIG at the commit [THIRD-PARTY.md](../../THIRD-PARTY.md) pins. Two structures over one socket, the implementation listening and the engine connecting:

| Structure | Size | What it is |
| --- | --- | --- |
| instruction packet | 8 bytes | `[0-3]` the instruction word, `[4-5]` an injection time, `[6]` a command, `[7]` padding |
| execution packet, v1 | 88 bytes | one fixed structure, the field order that document states |
| execution packet, v2 | 64 bytes and its extensions | a header stating its own total, then a 40-byte integer extension and an 88-byte memory extension where the header announces them |

Two commands are defined, `0` EndOfTrace and `1` Instruction, and a third, `v`, selects the wire format. An EndOfTrace whose instruction word is the ASCII `VERS` is a version probe rather than a reset; the reply is a v1-shaped packet whose halt byte is 1 for an implementation carrying only v1 and 3 for one that also has v2. The v2 structure is **not** in that document, which describes v1 alone; it is read from the model's own [core/rvfi_dii_v2.sail](../../model/model/core/rvfi_dii_v2.sail), which is the format's only written statement.

Three further requirements are the protocol's rather than the packet's, and this machine meets all three without anything being added for them: an EndOfTrace resets registers, memory and the program counter; the reset vector is `0x80000000`; and instructions are consumed from the socket rather than fetched, which `rvfi_fetch` does by taking the word out of the packet while still checking PCC's bounds and the alignment.

**The target upstream names does not exist here and the capability does.** `sail-cheri-riscv` builds a separate binary, `cheri_riscv_rvfi_RV64`, from an RVFI-specific source list compiled with `-DRVFI_DII`; the curated tree follows the current C++ backend, where the same capability is one binary behind `--rvfi-dii <port>`. TestRIG's own runner constructs that binary's *name*, so an unmodified `runTestRIG.py` reaches this model through its `--path-to-sail-riscv-dir` argument at a directory carrying that name, and nothing else about the conversation differs.

### 9.2 Where the packet and §4's record meet, field by field

| [§4](#4-the-commit-trace-schema-version-1) record | The packet's fields | Reading |
| --- | --- | --- |
| `I` | `rvfi_order`, `rvfi_pc_rdata`, `rvfi_insn` | one for one |
| `X` | `rvfi_rd_addr`, `rvfi_rd_wdata`, `rvfi_rd_tag` | one for one where `rd` is not `x0`. The tag is M0.12's bit, taken from the Integer extension's padding |
| `R` | `rvfi_mem_addr`, `rvfi_mem_rdata`, `rvfi_mem_rmask` | the mask's low run of ones is the width in bytes and the bit above it is the access's tag |
| `W` | the same three write fields | the same reading |

The mask's two readings are told apart by **the widths being powers of two**: a run of nine ones is an eight-byte tagged access, because nine is not a width. One length is genuinely ambiguous, a run of two being a two-byte untagged access and also a one-byte tagged one, and it is decided the first way because the tag granule is eight bytes (R-15-203): no access narrower than a granule can carry a tag, so the second reading names an access this machine has no form for.

### 9.3 Where they do not

| [§4](#4-the-commit-trace-schema-version-1) record | Why the packet cannot carry it |
| --- | --- |
| `S` | there is no field for the four capability registers outside the merged file. Upstream declares an availability bit for them and implements no structure behind it |
| `C` | the same, for CSR writes |
| `T` | `rvfi_trap` is a boolean where the record carries the cause |
| a second `R` or `W` under one instruction | the packet holds one memory access. A block operation therefore has no form in it at all, and `rvfi_write` and `rvfi_read` raise an internal error above sixteen bytes, which **stops the emulator** rather than reporting something narrower |
| `order`, when comparing | carried by both and compared by neither, for the reason [§4](#4-the-commit-trace-schema-version-1) gives |
| the order of effects under an instruction | a packet is a structure and not a sequence: it has one read group, one write group and one destination group, and no field saying which happened first. A comparison involving a packet therefore puts both sides in one fixed order, `R`, `W`, `X`, which is the model's own for the instruction that has all three |

One field the packet has and this model never fills is the source half of the Integer extension: `rvfi_rs1_addr`, `rvfi_rs2_addr` and their data are declared and never written, the model populating the destination half alone. That is a true statement under the packet's own rule, which requires the data only where the address is non-zero, and it is what a comparison over the full field set would find first.

### 9.4 A dialect of the standard packet, and not an extension of it

**M0.12's widening fits inside the standard v2 packet:** `rvfi_rd_tag` uses one padding bit in the Integer extension, and the memory masks place the tag one bit above the byte mask within the existing 32-bit mask fields.

**Effects that do not fit are structural:** variable-length effect lists, special capability registers, and trap causes require the full commit-trace grammar of [§4](#4-the-commit-trace-schema-version-1) rather than a wider fixed packet ([§9.3](#93-where-they-do-not)). As described in [§5](#5-the-transport), the record stream carries the full schema while the packet carries the representable subset, linked by [vos/rvfi.py](../../tools/vos/rvfi.py)'s projection.

**Version 1 cannot carry the widening:** v1 lacks `rd_tag` and truncates the 32-bit masks to 8 bits, dropping the tag bit of an 8-byte capability access at bit 8. Every session therefore negotiates v2.

### 9.5 What a generated stream may contain

Generated streams use five instruction templates built around purecap execution. Because all registers reset to null except the roots, every stream begins with a preamble that derives memory authority from the store root in `c1` (R-15-001c). Instructions are encoded through [vos/dialect.py](../../tools/vos/dialect.py), keeping generated streams within the frozen dialect.

Two classes of words are excluded from generation:
- **Block operations:** `rvfi_write` aborts the emulator on accesses wider than 16 bytes ([§9.3](#93-where-they-do-not)).
- **Words with low bits other than `11`:** all allocated 32-bit encodings in this profile end in `11`. Unallocated 16-bit-aligned encodings are already tested by [`cap-trap`](../../corpus/cap-trap.s) check 9, and drawing them uniformly would spend three quarters of every stream on illegal-instruction traps.

### 9.6 What the rig adjudicates today, and what it will

Until R2 connects the RTL's `rvfi` port, the rig runs in two modes:
- **Seeded-defect adjudication (`testrig run`):** compares the golden emulator against itself under named packet-level mutations, verifying that the generator, adjudicator, and counterexample shrinker detect and minimize every seeded divergence.
- **Cross-dialect bridge (`testrig bridge`):** runs a single emulator session emitting both RVFI-DII packets and commit-trace records, checking that [§9.2](#92-where-the-packet-and-4s-record-meet-field-by-field)'s projection agrees across both emitters.

When R2 attaches the RTL `rvfi` port, the same generator, projection, adjudicator, and shrinker will drive the RTL over the socket without modification.
