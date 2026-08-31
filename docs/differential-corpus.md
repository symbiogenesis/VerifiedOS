# The Differential Corpus and the Commit-Trace Schema

*The artifact **M0.12** delivers, and the one every later executor of the frozen profile is checked against. It is versioned because it is evidence rather than scaffolding: a milestone that reports a figure against this corpus reports it against a stated edition of it.*

> **Two halves, and each is owned once.** This document says what the corpus is, what each member exercises, how a member is written, and what a trace record means. [corpus/manifest.json](../corpus/manifest.json) says what has been *measured*: each member's check count, its commit trace's length, and that trace's digest. Nothing appears in both. `tools/check.py` holds the membership equal in both directions, so a program added to one and not the other is a finding.

**Section references.** Three numberings meet in these pages and none of them is this repository's default, so every `§n` here names the document it belongs to rather than relying on a reading: the plan's, for the milestones and the harness; the profile's, for the encoding and the frozen surface; and this document's own, marked *below*. A bare `§n` elsewhere in the repository names the register's section, and there is deliberately not one in here to be read that way.

## Why this document exists

The [implementation checklist](implementation-checklist.md) §10 names one instrument three times: *"one corpus, one trace format, three executors."* Its §12 has since struck the middle one, so what emits the same capability-widened commit trace is the Sail emulator and the RTL through its `rvfi` port, and one CI runner diffs them. Without a versioned corpus and a written schema, "the same trace" is a wish: the second executor arrives with its own idea of what a record is, and the first divergence is an argument about formatting rather than about behaviour.

It exists **now**, ahead of both of those executors, because the corpus is the model's only whole-program evidence. `riscv-tests` went with the default data capability at M0.6f: every program there addresses memory with an integer base register, which a purecap machine reads as an untagged capability and faults on, so the suite is not a corpus this machine can run. What replaced it had to be authored, and the profile's own net-new instructions (M0.6g) and bespoke instructions (M0.6h) each want a program to run rather than only a property to assert.

## 1. What the corpus is

Twenty-six purecap programs, hand-written in the frozen dialect, each running to a defined end on the curated Sail emulator and reporting through HTIF. Together they exercise the base ISA, the adopted extensions, the capability surface the M0.6e transplant and the M0.6f re-parameterization put in the model, the profile rows M0.6g and M0.6h add that no upstream model carries, the memory plan M0.14 and M0.16 put beneath all of it, the memory model M0.7 states over it, the core-class roster M0.8a indexes `mhartid` into, the vector memory surface M0.8b puts the per-element capability check on, and the frozen Keccak unit M0.8d attaches to the classes that roster names.

| Member | What it exercises |
| --- | --- |
| [`base-integer`](../corpus/base-integer.s) | RV64I arithmetic, logic, shifts, the W forms, every branch condition, and the zero register |
| [`base-memory`](../corpus/base-memory.s) | loads and stores at every width through a capability derived from the reset root, byte order, sign and zero extension, and a narrowed authority |
| [`mul-div`](../corpus/mul-div.s) | the M extension, including division by zero, the signed overflow, and the W forms |
| [`bitmanip`](../corpus/bitmanip.s) | `Zba` shift-and-add, `Zbb` logic, counting, rotation and extension, `Zbs` single-bit, and the `Zbkb`/`Zbkc`/`Zbkx` crypto forms |
| [`atomics`](../corpus/atomics.s) | `Zaamo` at word and doubleword, `Zabha` at byte and halfword, the comparing forms, and the tag an atomic's store half clears |
| [`zicond-csr`](../corpus/zicond-csr.s) | `Zicond` in both polarities and as an if-conversion, the writable and read-only halves of the CSR bank, and `cspecialrw` over MTDC |
| [`cap-inspect`](../corpus/cap-inspect.s) | the inspection surface over the split root pair, the trap capabilities, and the null capability |
| [`cap-derive`](../corpus/cap-derive.s) | the monotone derivations, the untagged result a non-monotone one yields, the permission lattice under `candperm`, and `csealentry` |
| [`cap-memory`](../corpus/cap-memory.s) | the tag plane under capability and data stores, granule keying, `cloadtags` and `cbo.zero` over one block, and load transitivity |
| [`cap-control`](../corpus/cap-control.s) | sentry roles at `cjal` and `cjalr`, the backward edge a call mints, the forward edge `csealentry` mints, and the bounds a sentry carries into PCC |
| [`cap-trap`](../corpus/cap-trap.s) | eight traps through MTCC and back through MEPCC: five capability violations with their `mtval` detail, an alignment exception, and an unallocated CSR address |
| [`cap-select`](../corpus/cap-select.s) | `cmovz`/`cmovn` in both polarities and over data, the untouched destination an untaken arm leaves, and `cclear` over each half of the merged file |
| [`cap-indexed`](../corpus/cap-indexed.s) | `cld`/`csd` at each scale against the displaced access they replace, and the five faults they raise on the authority rather than on an intermediate |
| [`cap-revoke`](../corpus/cap-revoke.s) | the revocation bitmap through its window, the tag a revoked load clears, the base the bit is keyed by, and the tags `cloadtags` reports as stored |
| [`cap-reclaim`](../corpus/cap-reclaim.s) | `creclaim` over a group holding two objects with different bases, the surviving tags it returns, the bits it leaves untouched, its idempotence, its group boundary, and the clear it lands in memory where the load filter's lands in a delivered value |
| [`platform-aia`](../corpus/platform-aia.s) | `fence.t` disturbing nothing, and the machine-level pending array under sends, reads, clears, and the reserved identity |
| [`platform-scrub`](../corpus/platform-scrub.s) | `cbo.scrub` preserving data and tags where a store of the same bits clears them, its two permissions and its refusal over IO memory, and `vmclear` clearing the vector register file and the vector CSRs with the extension-context gate off, over a configuration and a file the program dirtied first rather than over the values reset leaves |
| [`platform-memclass`](../corpus/platform-memclass.s) | the boundary between the two static latency classes: a capability's round trip, the tag a data store clears, `cloadtags`, `cbo.zero`, `cbo.scrub`, an atomic, and a bounds violation all answering the same on the second class as on the first, and the revocation filter keyed by the loaded capability's base rather than by the class of the slot holding it |
| [`platform-memseq`](../corpus/platform-memseq.s) | the refresh and discharge sequencer from the only side a program reaches it from: its window refused in both directions at every width and through a capability-width access, the whole region rather than one address, the unclaimed IO page above it answering where the window does not, and the second class unmoved by an interval of ticks |
| [`memory-model`](../corpus/memory-model.s) | `fence` collapsed to a drain or a no-op: the draining arm and the minimal one, the no-op arms with `fence.tso` among them, the I and O bits this profile reads where upstream ignores them, a store already visible to the next load, the reserved `fm` that traps where the base ISA would execute it, and the `rs1`/`rd` class that stays legal and ignored |
| [`platform-coreclass`](../corpus/platform-coreclass.s) | the core class from the only side a program reaches it from: the identity `mhartid` indexes the composed roster with, inert on a read and trapping on a write, and the geometry `vlenb` carries from the class table, both unmoved by the partition switch's eager zeroize and its flush where the vector configuration beside them is scrubbed, and both unmoved by the extension-context gate a partition can turn off for itself |
| [`vector-memory`](../corpus/vector-memory.s) | the capability semantics of the vector memory surface: the check landing per element on the unit-stride, indexed and runtime-strided forms, the violation naming the base register the access took its authority from rather than the vector destination, the tag a vector store clears on the granule it overwrites, and the masked-off element that raises nothing, writes nothing, and leaves the granule it would have covered standing bit for bit |
| [`vector-geometry`](../corpus/vector-geometry.s) | the one class-table figure the instruction set carries: `vlenb` against the VLMAX a configuration instruction derives from it, the whole-register pair moving exactly a register's worth whatever `vl` says, and the element that reaches past an authority half a register wide, with every extent derived from `vlenb` rather than written down so that the program runs unchanged at VLEN=256 and at VLEN=4096 |
| [`keccak-perm`](../corpus/keccak-perm.s) | the frozen Keccak permutation as an instruction stream against the FIPS 202 and NIST ACVP known answers: both round counts over the 2048-bit element group at the C class's LMUL=8, the in-place form and the separate-destination form, one padded SHA-3-256 block whose result fixes the lane order, the unassigned round count that traps, the capability check on the vector load carrying the group, and the extension-context gate this instruction folds in where `vmclear` does not |
| [`platform-rot`](../corpus/platform-rot.s) | the Root of Trust's four peripherals from the only side a program on the C-class emulator reaches them from: the OTP window's lifecycle read and its one-way burn door, the entropy root's draw, the counter file in both directions, the watchdog in both directions, a capability-width access and a narrower one, the last doubleword of a window rather than its first, and the unclaimed IO page above them answering where the four windows do not |
| [`fec-surface`](../corpus/fec-surface.s) | the FEC decoders' surface from the only side a program on the C-class emulator reaches it from: both mnemonics refused on a composed hart the roster attaches no decoder to, the opcode and `funct3` the pair shares, the code family as the sub-opcode with nothing else moving with it, each operand in the field the form names, and the descriptor register whose contents reach no field of the encoding, every word read back out of the trap value rather than written down |

**The version is a commitment and the digest is a measurement.** `version` in the manifest names the edition; a member added, removed, or changed in what it asserts advances it. `trace_schema` names the record grammar of §4 below; a record type added or a field widened advances that. Each member's `digest` is the fingerprint of its commit trace, so a model change that alters what a program *does* is a finding at the next run rather than a surprise at the next milestone; `run.py model corpus --refresh` is how a deliberate change is recorded, and the edit shows up in review as a moved digest beside the model change that moved it.

## 2. Writing a member

Five conventions, and each of them is a property of this machine rather than a style.

- **`gp` names the check in flight.** A program sets `li gp, N` before check *N* and branches to `fail` on a mismatch; `fail` writes `(gp << 1) | 1` to `tohost` and `pass` writes `1`, so the HTIF exit code is the number of the check that failed. This is `riscv-tests`' convention, kept deliberately: it is the one thing about that suite this platform can still use.
- **The store-side root comes out of `c1` first.** Reset hands each core a **pair** of root capabilities, not one: no admitted permission set holds both store and execute, so the execute side is PCC and the store side lands in `c1` (R-15-007l, R-15-007p, [step_ext.sail](../model/model/postlude/step_ext.sail)). `c1` is also the link register, so a program that calls overwrites its own authority. Every member opens with `cmove c8, c1` and names `c8` thereafter.
- **A memory access derives its authority.** There is no default data capability and no integer-addressed access (R-15-001c), so `li` names an address and `csetaddr` turns the root into an authority at it. For code and read-only data `la` materializes a capability off PCC instead, which is the profile's own PC-relative pair (`auipcc` + `cincoffsetimm`); what it yields carries PCC's authority, so a store through it faults, and that is the intended answer.
- **Capabilities live in `c8` upward.** A register has two readings and one identity, so `c5` and `t0` are the same register. Keeping capabilities out of the `t` range is what stops a check from quietly clobbering the authority the check before it derived.
- **A program ends in the same six lines.** `fail` folds `gp` into the exit code, `pass` writes one, `exit` derives the `tohost` authority and stores, and `halt` spins. The emulator stops at the HTIF write, so the spin is never entered twice.

## 3. The assembler

The corpus is purecap and no toolchain assembles it: LLVM's MC layer and `lld` are re-homed to the dialect at **M1.4**, which is downstream of every milestone this corpus gates. What stands in is small enough to read, in the one language the tools lane carries:

- [tools/vos/dialect.py](../tools/vos/dialect.py) is one row per mnemonic the curated model decodes, transcribed from the model's own `mapping clause encdec` rather than from the RISC-V manuals. Where the two differ the model is what the corpus must run on, and they do differ: `auipcc`, `cjal` and `cjalr` hold the base encodings of `auipc`, `jal` and `jalr`, `lc` sits at MISC-MEM `funct3` 010 beside `cbo.zero`, and `sc` is the capability store rather than a store-conditional.
- [tools/vos/asm.py](../tools/vos/asm.py) is the parser, the layout, and the pseudo-instructions: labels, expressions, the data directives, `li` at any 64-bit constant, and `la` as the PC-relative pair. Layout is iterated to a fixed point rather than done in two passes, because `li` is as long as its value needs and a value can be a symbol.
- [tools/vos/image.py](../tools/vos/image.py) writes the ELF the emulator already loads: `PT_LOAD` segments at their physical addresses and a `.symtab` carrying `tohost`. Nothing else, because nothing else is read.

**It is the acceptance corpus M1.4 is later checked against rather than work M1.4 repeats.** Three things it deliberately does not do, each because the program that needs it is not a hand-written test: no relocations and no object files, since layout is absolute and the image is position-fixed anyway (R-15-002b, R-15-036l); no linker script; and no macro processor.

**Two absences in the encoder are scope and not oversight.** The dictionary bundle format of [isa-profile.md](isa-profile.md) §1.1 is a fetch container the model does not implement yet, so an image here is a stream of canonical 32-bit instructions, which is what the curated model fetches. And the matrix surface is absent because the profile names no instruction for it, which is a profile act and not a datapath's arrival: that surface is a second-act item R-15-014a carries at (ix), conditioned on the dense-GEMM margin R-15-116 admits the unit against. Nothing enters the profile by inheritance (R-15-007j), so there is no mnemonic to transcribe until a row names one, and the corpus version that follows that act adds its rows. The FEC pair is no longer among them: its scope is categorical rather than measured, so it was owed at the provisional freeze and the profile now names it, and `ldpcdec` and `polardec` are rows in the table like any other (R-15-119b).

**The vector rows are the memory surface and what feeds it**, which is the surface **M0.8b** puts the per-element capability check on: every form whose element addresses are made differently, at all four element widths, plus the configuration instruction that says how many elements there are and the four moves that put a value into the vector file and read one back. The vector arithmetic is not encoded, because a row nothing in the corpus writes is a row nothing checks.

**A hand-written word is the marked exception.** A member reaches an encoding through a mnemonic, and the parser then checks its operand kinds, register classes, and immediate ranges against the row before the encoder builds anything. A `.word` reaches one with none of that checked, so the grounds for writing one are closed rather than open, and there are three:

- **The encoder cannot express it.** A field the row holds constant is the point of the check, so the encoding is outside what any operand assignment reaches. Both of [`memory-model`](../corpus/memory-model.s)'s words are here: the `fence` row emits `fm` as the literal zero and `rd` and `rs1` as zero, which is what makes a reserved `fm` and a set-but-ignored register pair unreachable through it.
- **The encoder refuses it.** The row for `vkeccak.vi` will not emit a round count other than 12 or 24, so the check that an unassigned one traps writes the word. This is the only refusal in the table, and it is one because the round count is the operand whose unallocated values are the point of the requirement (R-15-057a).
- **The word is what the reader must see.** [`platform-coreclass`](../corpus/platform-coreclass.s)'s write to a read-only `mhartid` and [`cap-trap`](../corpus/cap-trap.s)'s read of a CSR address the PMP deletion emptied are both encodings the table emits perfectly well, because what a row can express is the encoder's business and what an encoding means is the machine's. They are written as words so that a listing cannot be read as a program that did it by accident.

***Not carried yet* is not a fourth ground**, and that is the one worth stating rather than leaving to judgment: a row that has not landed lands, and the member goes on writing the word afterward because nothing reads a `.word` to notice. The words below are therefore enumerated, and **K-72** holds the list against the members in both directions and holds each row's ground against the encoder itself, assembling the reading and requiring the encoder to answer as the ground says it does.

| Member | Word | Ground | Reading |
| --- | --- | --- | --- |
| [cap-trap](../corpus/cap-trap.s) | `0x3B0022F3` | the word is what the reader must see | `csrrs t0, 0x3b0, zero` |
| [keccak-perm](../corpus/keccak-perm.s) | `0x0170200B` | the encoder refuses it | `vkeccak.vi v0, v0, 23` |
| [memory-model](../corpus/memory-model.s) | `0x1330000F` | the encoder cannot express it | `fence rw, rw` |
| [memory-model](../corpus/memory-model.s) | `0x0332830F` | the encoder cannot express it | `fence rw, rw` |
| [platform-coreclass](../corpus/platform-coreclass.s) | `0xF1429073` | the word is what the reader must see | `csrrw zero, mhartid, t0` |

The **Reading** is the assembler text the member's own comment says the word is, and the rule reads it two ways according to the ground. On the first two grounds the encoder's answer to that text must **not** be the word, which is the ground restated as something a machine can decide and is what expires when a row lands. On the third it must be **exactly** the word, which is the member's comment held against the encoder rather than against a reader.

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

**The schema is capability-widened in exactly the places a capability is wider than an integer**, and the plan's §10 list of what it carries, *"PC, instruction, register and memory effects, plus tag, bounds, permissions, and seal state"*, is read off these records this way:

- A register's **value** is its 64 data bits, which are its integer reading, and the **tag** is the one bit of a capability that reading cannot show (R-15-007i). Together they are the whole register. Permissions, object type, exponent and the two bounds mantissas are the fields of those 64 bits, at the offsets [isa-profile.md](isa-profile.md) §4.1 fixes, so the record carries them by carrying the encoding; **base and top are the *decode* of the bounds triple**, and the rig does not re-derive them, because a second implementation of the bounds algorithm inside the trace reader is a second place for it to be wrong.
- The value is the register's **memory** encoding, the same bits a store writes and a load reads, so a register record and a memory record of the same capability are the same string. That is the null-capability transform's doing and it is why an all-zeroes granule reads back as untagged NULL (R-15-182).
- A memory access carries **the tag of the access** rather than the tag in memory. A capability load asks for the metadata and reports what it got; a data load does not ask, and reports `0`, which is a true statement about the value it delivered.
- The four capability registers outside the merged file get records of their own, because none of them appears in the register-file trace: `cspecialrw` writes them, and so does every trap.

**Four things the schema does not carry**, each named rather than left to be discovered:

1. **Instruction fetches.** They carry nothing the `I` record does not, they arrive in two 16-bit granules under this profile, and no `rvfi` port reports them, so an executor that fetched differently could not be compared on them anyway.
2. **PCC.** Its address is the `I` record's `pc`; its bounds and permissions change only where a control transfer or a trap installs them, and a program that wants to see that reads PCC with `cspecialrw`, which produces an `X` record.
3. **CSR reads.** A read is not an effect.
4. **The `order` field, when comparing.** It counts retires from the start of a run, so two executors entering through different reset vectors disagree on it while agreeing on everything else. It is emitted, because it is what makes the stream readable, and dropped from the compared record.

## 5. The transport

The trace **reuses the RVFI plumbing**, which is what the curation preserved it for. The generic callbacks already report every effect; RVFI's own callbacks class assembles them into a per-instruction packet; the commit trace is a second class in the same slot, assembling them into a per-instruction record group ([riscv_callbacks_commit.cpp](../model/c_emulator/riscv_callbacks_commit.cpp)), emitted under `--trace-commit`.

Two halves of that reuse are worth stating, because they went in opposite directions.

**The packet is widened where it can be.** `rvfi_wX` now carries the tag of the value written to `rd`, in a bit taken from the Integer packet's padding, and `rvfi_read`/`rvfi_write` carry the tag of a memory access as **one bit above the byte mask**: an access of *w* bytes sets mask bits 0 through *w* − 1 for its bytes and bit *w* where it carried a tag. That is the extension the CHERI-widened 32-bit masks were sized for, and it closes the two `TODO`s the tree carried. The RTL's `rvfi` port is what this half is for (the plan's §11).

**The packet is not the transport.** It is fixed-size and holds one memory access per instruction, so it cannot express `cbo.zero`'s 64-byte block write or `cloadtags`' eight granule reads, and it has no field for the capability registers outside the merged file. The record stream carries the whole schema; the packet carries the subset it can, for the executor whose port emits packets. Where they overlap they say the same thing.

## 6. How a run is adjudicated

`python tools/run.py model corpus` assembles every member, runs it once, and asks two questions of that run.

* **The program's own.** It reports through HTIF, so the verdict is the exit code it wrote, and a failure names the check that failed because `gp` carries it.
* **The rig's.** The same run emits the commit trace; the runner normalizes it, digests it, and holds the digest against the manifest's.

Against a second executor the same records are compared instruction by instruction, and [tools/vos/trace.py](../tools/vos/trace.py) is where the alignment and the adjudication live. That executor does not exist yet: the M0.4 oracle is not one, because it implements ISAv9's 128-bit encoding with a hybrid mode and a default data capability where this model carries the 64+1-bit purecap dialect, so the two are different machines and the agreeing prefix over `riscv-tests` is read as a fact about how far they happen to agree. The standing second executor is **the RTL under Verilator co-simulation (R2)**, adjudicated over one RVFI-DII trace format by the rig S11 stands up. M2's CHERI-QEMU fork was carried for that job and is struck with the rest of M2, so what the plan's §12 leaves is one second executor rather than two, arriving as the artifact that ships rather than as a second model.

## 7. What the corpus cannot exercise yet, and why

Each of these is an absence in the machine or in the model, not a gap in the corpus, and each closes with the milestone that supplies it.

| Absent | Why | Closes at |
| --- | --- | --- |
| `cseal`'s success case | The reset root pair holds neither `Permit_Seal` nor `Permit_Unseal`, and `candperm` can only remove, so no sealing authority is derivable from reset. The refusal *is* exercised. | the composed initial distribution, the plan's §3 |
| An access-system-registers violation | Reaching it means executing without ASR on PCC, which on this machine is a one-way door: nothing in reach gives it back. | a composed distribution with a non-privileged compartment, the plan's §5 |
| `cbo.scrub` correcting anything, and its fail-stop on an uncorrectable error | The model has no error model: no codeword carries a syndrome, so nothing is correctable and nothing is uncorrectable, and inventing a fault-injection register would model the harness rather than the machine. The refusals *are* exercised, and the detection joins the error path the block read already returns on. | an error model, which no milestone carries: the plan's §10 harness models ECC as no-ops-with-latency, and the sentinel the correction telemetry goes to is a class in the roster rather than an instrument |
| The exit-path discharge and the refresh cadence themselves | The sequencer is a register slave the RoT drives while every requester is held in reset, so no instruction reaches it and no program can start one, observe one, or time one (R-15-247h). What a program exercises is the refusal, which is the whole of the requester-side contract; the mechanism is asserted as properties over the model instead. | a composed image whose RoT firmware drives it, M3.5's measured boot. M3.1 landed the sequencer as a register slave and M3.2 the firmware as a Gallina statement, and neither puts a driven sequencer under a running program, so the absence outlived both |
| A revocation sweep with more than one covered interval | The covered union is a predicate over one composition-fixed interval, because one composed image has one revocable region; a second interval is a clause in that predicate rather than a mechanism. | the composed initial distribution, the plan's §3 |
| The matrix datapath | The class is declared and its geometry is, and the instruction surface is a second-act item: R-15-116 admits the unit only against a sustained dense-GEMM margin, which is a measurement against generated output, so R-15-014a carries the surface at (ix) rather than a milestone carrying it now. The vector datapath is no longer absent here: `vector-memory` and `vector-geometry` run it. | the freeze's second act, R-15-014a (ix) |
| An FEC decode that retires | The surface is in the model and [`fec-surface`](../corpus/fec-surface.s) runs it, but only as far as the refusal: the gate is the composed roster entry's FEC attachment, the golden emulator is the C class, and the reference composition attaches the decoders to the pinned radio V pair, so no program this rig runs is on a hart that carries one. What a program reaches is the encoding and the trap; the pass, its two authorities, and the descriptor's refusals are asserted as properties over the model instead. | a composed image on a decoder-bearing hart, the plan's §3 |
| The vector arithmetic, and the segment forms of the vector memory surface | Encoded by neither the assembler nor a member, because M0.8b's subject is what a vector access owes its authority and a segment access owes it exactly what a one-field access does, once per field. | the member that needs one |
| The dictionary bundle format | A fetch container the model does not implement. | the freeze, the profile's §1.1 |

## 8. What CI holds

Two instruments, and they run in different places for a reason: one needs a built emulator and one needs nothing but Python, so a corpus that has stopped assembling is a finding on the host rather than a surprise in WSL.

| Predicate | Where |
| --- | --- |
| every member assembles | `tools/check.py` (host) |
| the manifest and this document name the same members, in both directions | `tools/check.py` (host) |
| each member's recorded check count is the count its source carries | `tools/check.py` (host) |
| every member runs to a HTIF verdict of success | `tools/run.py model corpus` (WSL) |
| every member's commit trace matches the digest the manifest records | `tools/run.py model corpus` (WSL) |
| the wire format of §9 below is what the codec encodes and decodes | `tools/run.py test` (host) |
| the emulator negotiates RVFI-DII v2 and retires an injected instruction | `tools/run.py testrig handshake` (WSL) |
| a generated stream's packets and its commit records agree, one run, both dialects | `tools/run.py testrig bridge` (WSL) |
| every seeded defect is reported, and no unseeded run diverges | `tools/run.py testrig run` (WSL) |

## 9. The RVFI-DII rig

*§4 above is the trace format the plan's §10 sentence names; this is the runner it has never had, and this section says what the wire is, where it meets §4, and what the rig can drive today.*

**The corpus is authored and this is generated, which is the whole of what it adds.** A hand-written member exercises what somebody thought to write; a verification engine generates instruction streams, consumes execution traces, adjudicates two executors against each other, and **shrinks a counterexample automatically**, which no corpus can do at all. The instrument is [tools/run.py testrig](../tools/vos/cli/testrig.py) over [vos/rvfi.py](../tools/vos/rvfi.py), the wire format, and [vos/vengine.py](../tools/vos/vengine.py), the generator, the socket and the shrinker; adjudication is [vos/trace.py](../tools/vos/trace.py)'s, unchanged, so there is one adjudicator here and not two.

### 9.1 The wire, and where it is read from

**RVFI-DII is not this repository's format and is read at its own source**, which is `RVFI-DII.md` in CTSRD-CHERI's TestRIG at the commit [THIRD-PARTY.md](../THIRD-PARTY.md) pins. Two structures over one socket, the implementation listening and the engine connecting:

| Structure | Size | What it is |
| --- | --- | --- |
| instruction packet | 8 bytes | `[0-3]` the instruction word, `[4-5]` an injection time, `[6]` a command, `[7]` padding |
| execution packet, v1 | 88 bytes | one fixed structure, the field order that document states |
| execution packet, v2 | 64 bytes and its extensions | a header stating its own total, then a 40-byte integer extension and an 88-byte memory extension where the header announces them |

Two commands are defined, `0` EndOfTrace and `1` Instruction, and a third, `v`, selects the wire format. An EndOfTrace whose instruction word is the ASCII `VERS` is a version probe rather than a reset; the reply is a v1-shaped packet whose halt byte is 1 for an implementation carrying only v1 and 3 for one that also has v2. The v2 structure is **not** in that document, which describes v1 alone; it is read from the model's own [core/rvfi_dii_v2.sail](../model/model/core/rvfi_dii_v2.sail), which is the format's only written statement.

Three further requirements are the protocol's rather than the packet's, and this machine meets all three without anything being added for them: an EndOfTrace resets registers, memory and the program counter; the reset vector is `0x80000000`; and instructions are consumed from the socket rather than fetched, which `rvfi_fetch` does by taking the word out of the packet while still checking PCC's bounds and the alignment.

**The target upstream names does not exist here and the capability does.** `sail-cheri-riscv` builds a separate binary, `cheri_riscv_rvfi_RV64`, from an RVFI-specific source list compiled with `-DRVFI_DII`; the curated tree follows the current C++ backend, where the same capability is one binary behind `--rvfi-dii <port>`. TestRIG's own runner constructs that binary's *name*, so an unmodified `runTestRIG.py` reaches this model through its `--path-to-sail-riscv-dir` argument at a directory carrying that name, and nothing else about the conversation differs.

### 9.2 Where the packet and §4's record meet, field by field

| §4 record | The packet's fields | Reading |
| --- | --- | --- |
| `I` | `rvfi_order`, `rvfi_pc_rdata`, `rvfi_insn` | one for one |
| `X` | `rvfi_rd_addr`, `rvfi_rd_wdata`, `rvfi_rd_tag` | one for one where `rd` is not `x0`. The tag is M0.12's bit, taken from the Integer extension's padding |
| `R` | `rvfi_mem_addr`, `rvfi_mem_rdata`, `rvfi_mem_rmask` | the mask's low run of ones is the width in bytes and the bit above it is the access's tag |
| `W` | the same three write fields | the same reading |

The mask's two readings are told apart by **the widths being powers of two**: a run of nine ones is an eight-byte tagged access, because nine is not a width. One length is genuinely ambiguous, a run of two being a two-byte untagged access and also a one-byte tagged one, and it is decided the first way because the tag granule is eight bytes (R-15-203): no access narrower than a granule can carry a tag, so the second reading names an access this machine has no form for.

### 9.3 Where they do not

| §4 record | Why the packet cannot carry it |
| --- | --- |
| `S` | there is no field for the four capability registers outside the merged file. Upstream declares an availability bit for them and implements no structure behind it |
| `C` | the same, for CSR writes |
| `T` | `rvfi_trap` is a boolean where the record carries the cause |
| a second `R` or `W` under one instruction | the packet holds one memory access. A block operation therefore has no form in it at all, and `rvfi_write` and `rvfi_read` raise an internal error above sixteen bytes, which **stops the emulator** rather than reporting something narrower |
| `order`, when comparing | carried by both and compared by neither, for the reason §4 gives |
| the order of effects under an instruction | a packet is a structure and not a sequence: it has one read group, one write group and one destination group, and no field saying which happened first. A comparison involving a packet therefore puts both sides in one fixed order, `R`, `W`, `X`, which is the model's own for the instruction that has all three |

One field the packet has and this model never fills is the source half of the Integer extension: `rvfi_rs1_addr`, `rvfi_rs2_addr` and their data are declared and never written, the model populating the destination half alone. That is a true statement under the packet's own rule, which requires the data only where the address is non-zero, and it is what a comparison over the full field set would find first.

### 9.4 A dialect of the standard packet, and not an extension of it

**The widening M0.12 made is inside the standard packet**, and deliberately: `rvfi_rd_tag` is one bit out of the Integer extension's padding, and the memory masks carry the tag one bit above the byte mask, which is the extension the CHERI-widened 32-bit masks were already sized for.

**What does not fit is structural rather than a field short.** A format that must grow a variable-length effect list, a fifth register file and a trap cause is a different grammar and not a longer packet, and every one of §9.3's rows is that shape. So the record stream of §4 carries the whole schema and the packet carries the subset it can, exactly as §5 says, and [vos/rvfi.py](../tools/vos/rvfi.py)'s projection is the one place the two are held to say the same thing. The alternative, an extended packet, would fork the wire format away from every other TestRIG implementation to buy fields the record stream already has.

**Version 1 cannot carry the widening at all**, which is why every loop negotiates v2: v1 has no `rd_tag` field, and it truncates the 32-bit masks to their byte halves, so the tag of an eight-byte capability access, which sits at bit 8, is deleted rather than cleared. A v1 conversation is a conversation about an integer machine.

### 9.5 What a generated stream may contain

Five templates, and each is a property of this machine rather than a taste. A stream opens with a preamble because on a purecap machine every register holds the null capability until something is put in it, and the authority a memory access needs does not exist until a stream derives one from the root the reset puts in `c1` (R-15-001c). The words are encoded through [vos/dialect.py](../tools/vos/dialect.py), the same table the corpus assembles through, so a stream is in the frozen dialect by construction.

Two exclusions are the format's and not the machine's, and both are stated rather than left to be discovered. The **block operations** are out because `rvfi_write` stops the emulator on them, which is §9.3's last row seen from the side that has to generate around it. The **sub-32-bit encodings** are out because the profile excludes `C` and fixes ILEN at 32, so a word whose low two bits are not `11` is not an instruction this machine has; injecting one makes the two emitters disagree about what was injected, the commit trace reporting the sixteen-bit halfword `rvfi_fetch` decoded through upstream's compressed branch and the packet reporting the whole word, and which of those is right is a question for the model rather than for the generator.

### 9.6 What the rig adjudicates today, and what it will

**The second executor does not exist yet**, and the rig says which one it drove rather than implying two. M2's CHERI-QEMU fork is struck and the RTL is R1b's, so today the second side is the first **under a seeded defect**: a named packet-level mutation standing for a way a second implementation of the frozen profile gets an answer wrong. Each is written so that most instructions do not expose it, which is what makes shrinking a measurement rather than a demonstration, and the gate is the checker's own: a seeded defect that goes unreported is a finding, exactly as a checker rule saying nothing about its own mutant is.

The rig's other arm needs no second executor at all and is not a substitute for one: **one run emits both dialects**, the packets over the socket and the records into the trace log, because the two callback classes are registered independently. Holding those against each other is the only place §9.2's meeting is a measurement rather than a reading of two documents, and it is what would catch the emitters drifting apart.

**When R2 supplies the RTL's `rvfi` port**, it is the port this rig's socket already connects to and nothing else here changes: the generator, the projection, the adjudicator and the shrinker are all on this side of the socket. That is the sense in which this is the second executor the struck M2 items were carried for.
