# The Bedrock2 lowering loop, on one wire parser

One Gallina source, one mechanically regenerated C implementation, one checked relation between them, run by hand in the switch M1.6 stood up. This is Q2a's host-only experiment: the component is a wire-parser-shaped check over the ring descriptor the [generated interface artifact](../../proofs/RingContract.v) fixes, the imperative output is bedrock2 code Rupicola derives from the source with its functional relation closed at `Qed`, and the C is what bedrock2's printer emits from that code, cut out of the prover's output and never edited. What stops here is the device leg: the C reaches M1.2's contained `ccomp` and comes out as plain RV64 with the capability arms stubbed, which is the exit M1.6 measured and what Q2b closes after M1.2f. Nothing in this directory is sold as compilation of the golden model, and no theorem here reaches the Sail model, constant-time behaviour, resource bounds or the hardware refinement.

## What is here

| File | What it is |
| --- | --- |
| [DescriptorCheck.v](DescriptorCheck.v) | The component: the descriptor header check in Rupicola's subset, its `spec_of`, its `Derive`, and the `c_module` that prints it. Every layout constant is evaluated from the generated artifact it imports. |
| [IpChecksumBaseline.v](IpChecksumBaseline.v) | The yardstick: the package's own shipped `ip_checksum` derivation, printed through the same `c_module`. |
| [VerifiedExit.v](VerifiedExit.v) | The verified exit run over this component: `coq-bedrock2-compiler` over `coq-riscv` at the width and set the shipped recipe instantiates, for its instruction census alone. |
| [regenerate.py](regenerate.py) | The driver: stages the sources outside every checkout, compiles them in the switch, cuts the C out, prints the figures, and under `--check` holds the C to its digest. |
| [DIGESTS.md](DIGESTS.md) | The record `--check` compares against: SHA-256, bytes and lines of each emitted file. The C itself is not tracked. |

The precedent is [the Wasm oracle's](../wasm-oracle/README.md): a loop a later reader re-runs, one source against released packages, with a hand-run recipe and no `run.py` command, the label naming a validator the entry point does not carry. The emitted C stays outside the tree for two reasons stated at [THIRD-PARTY.md](../../THIRD-PARTY.md): bedrock2's printer prepends its own load-and-store preamble, which is bedrock2's text under bedrock2's terms, and the license-mark rule has no ruling for a `.c` kind. Nothing under `proofs/` moves: the proof gate compiles that directory in a switch of its own that carries none of the five packages this loop stands on, so a file requiring Rupicola there would turn `run.py proofs` red.

## Pinned environment

* **The switch** is `rupicola-9.1.1`, M1.6's, created over `ocaml-base-compiler.5.4.0` for the reason M1.6's note records, and this directory does not re-create it. What it must hold, and what `regenerate.py` prints at the top of every run, is `coq-rupicola` **0.0.11**, `coq-bedrock2` and `coq-bedrock2-compiler` **0.0.9**, `coq-coqutil` **0.0.7**, `coq-riscv` **0.0.6**, `rocq-core` **9.1.1** and the `coq` **9.1.1** compatibility metapackage, whose terms are read at [THIRD-PARTY.md](../../THIRD-PARTY.md). The prover is Rocq 9.1.1 spelled `coqc`, the metapackage supplying that name where the proof gate's switch has only `rocq`.
* **The owner** is [proofs/RingContract.v](../../proofs/RingContract.v), which `run.py ring emit` writes from [interfaces/ring-reference.json](../../interfaces/ring-reference.json) and rule K-89 holds byte-identical to its generator. It carries no `Require` of its own, so it compiles in this switch as it stands; the driver copies it into the stage beside the component.
* **The reaching exit** is the contained purecap `ccomp` of M1.2's build lane, `/root/build/secomp-m12/ccomp`, reporting *The CompCert C verified compiler, version 3.17*, with the preprocessor line of its `compcert.ini` relaxed as M1.2's cell records. It is not in this tree and never conveyed; the driver runs it only when handed its path, and its terms are the ones [THIRD-PARTY.md](../../THIRD-PARTY.md) decomposes under CompCert and SECOMP.
* **The stage** is a directory under `/root`, outside every checkout, named on the command line. Every path the driver takes is absolute: a relative write from the guest lands in the primary checkout.

## The component

`descriptor_check bs len` reads a descriptor from a byte buffer of declared length `len` and answers R-12-093's `status_ok` where the header is well formed under section 4.2 of [the IDL profile](../../docs/idl-profile.md) and `status_invalid` otherwise, both spelled as their case index (WF-7). In wire order it checks that the buffer holds a tag byte; that the tag is below the operation count; that the buffer holds the operation's packed descriptor, no interior padding (WF-6); each buffer reference's direction and content-type discriminants against their two-case enumerations (WF-7 over WF-11); the optional deadline's presence discriminant, `0` with no payload or `1` followed by a class index below the class count (WF-8); and the flag set, every bit above the declared flag count zero (WF-10). **No byte past `len` is read on any path.** Each read follows the length test that admits it, and the derivation discharges that side condition at every one of the nine `ListArray.get` sites the source carries, which the two shared definitions put at five use sites and the printer emits as seventeen `_br2_load` calls; a read placed past its test does not compile, which is the red path below.

What it does not decide is stated so that the claim stays the size of the artifact. The request identifier, the scalars and each reference's session index, offset and length are `validated_at_use` in the owner and pass through untouched; R-12-092's validation against the session table is the server's, after this check. The bytes after a descriptor inside its slot are the declared `op_fill`, which the owner's `descriptor_fills_its_slot_exactly` holds to the slot size, and are not a field, so they are not read. A descriptor is checked and never copied.

**Where the constants come from.** The file imports the owner and evaluates every offset, size and case count from its definitions at compile time (`Eval compute`), so a change to the declaration reaches the emitted C through one regeneration and no edit here; the maintenance probe below measures exactly that. Two things the file states rather than reads: the case indices of `op` and `status`, which WF-7 fixes as declaration order and Gallina cannot reflect. Each is a total match, so a constructor added to or removed from the owner fails this file rather than drifting past it, and the two-case enumerations are held complete by the `In` lemmas beside their lists. One arm serves both extent operations, and `extent_arm_shared` is the reflexivity lemma that admits the sharing: were the owner to give them different layouts, that lemma fails and the arm splits.

**The transcription, against M1.6's six moves.** The source is authored inside the subset rather than transcribed from a `nat`-and-`list` twin, so most of the moves are avoided rather than paid: the scalar is `word` throughout, the buffer is `ListArray.t byte` with its length an argument, there is no higher-order site (`fun` occurs zero times), no inductive is declared, and the result is a word carrying a case index rather than a `bool`. What is paid is the hand-supplied part: the `spec_of` with its `listarray_value AccessByte` footprint and the two length preconditions (10 lines), three `Hint` commands over nine lines, and an eight-line `Ltac` that turns each `word.ltu` branch hypothesis into the arithmetic the array lemma wants, which with the eight-line `Derive` block is the whole of the glue, 35 lines. The four lemmas in the file are about the owner and not about the derivation.

## Build and run

Keep the VM up first; a derivation is minutes long and WSL tears the utility VM down between commands, which [the Wasm oracle's README](../wasm-oracle/README.md) explains and prices.

```console
$ python tools/run.py model keepalive
$ python tools/bedrock2-lowering/regenerate.py --stage /root/q2-stage \
    --ccomp /root/build/secomp-m12/ccomp --baseline
== regenerate runs in WSL; re-launching there
=== bedrock2-lowering: regenerate descriptor_check in /root/q2-stage ===
switch rupicola-9.1.1: The Rocq Prover, version 9.1.1
  ...
RingContract.v: coqc exit 0 in 0.66 s wall
DescriptorCheck.v: coqc exit 0 in 50.26 s wall, maximum resident set 834660 KB, compile 34.466 s, Qed 13.504 s
  Print Assumptions: Closed under the global context
descriptor_check.c: 7874 bytes, 202 lines, sha256 3d85721281062243511867fe073235be624717ca6e6db3517f4fb9419a849136
ccomp -S: exit 0
  descriptor_check.s: 309 lines, 254 instructions, 21 distinct mnemonics, 0 capability mnemonics (predicate ^\s+c[a-z]+\s, call excluded)
ccomp -S -dcapasm: exit 0
  descriptor_check.cap_asm: 32905 bytes, 523 lines, 115 TODO tokens over 16 distinct arms
--- baseline: ip_checksum ---
  ...
--- DIGESTS.md rows ---
| `descriptor_check.c` | `3d857212...` | 7874 | 202 |
| `ip_checksum.c` | `11fdf341...` | 2340 | 62 |
$ python tools/bedrock2-lowering/regenerate.py --stage /root/q2-stage --check
  ...
check: descriptor_check.c agrees with DIGESTS.md (3d8572128106..)
```

From the host the driver re-launches itself in WSL with every Windows path translated; inside WSL it runs as `python3` with the same arguments. `--source` and `--owner` take other files, which is how a probe is run against a modified copy without touching the tree.

**Run the `--check` from a second checkout, not only from the one that recorded the digest.** A digest taken and re-checked in one working tree tests the driver and not the loop; the reading that decides is a fresh clone at the same commit, run into a stage of its own, and this record was taken that way: the same source at the same commit in a different directory emits a byte-identical file, so the digest is a property of the input and not of the tree it was derived in.

The verified exit is one more compile in the stage, after the driver has left `DescriptorCheck.vo` there:

```console
$ wsl -e bash -lc 'cd /root/q2-stage && eval $(opam env --switch=rupicola-9.1.1 --set-switch) \
    && cp /mnt/c/<repo>/tools/bedrock2-lowering/VerifiedExit.v . && coqc VerifiedExit.v'
=== INSTRUCTION COUNT ===
     = 257%nat
```

**The red path.** A green `--check` is worth having only if a red one is reachable, and here two are, each run in a stage of its own. Seed one read past its length test, `ext_dl` computed from `full_bytes` where only `ext_min` bytes are admitted, and the derivation stops: `compile` reports `Compilation incomplete` at exactly one site and `Qed` refuses with *Attempt to save an incomplete proof*, exit 1, so nothing is emitted to check. The buffer bound is discharged by the derivation and not by the printer, which is the whole reason this red path is reachable at all. Seed one owner constant instead, a third flag with its spare bit taken away, and the derivation closes untouched while `--check` exits `1` reporting that `descriptor_check.c` drifted: same 7,874 bytes and 202 lines, digest `eb59673c` against the recorded `3d857212`, the six flag tests in the C having moved from `< 4` to `< 8` and nothing else on the file's 202 lines.

## The boundary from Bedrock2's memory to capability-bearing code

Q2's third bullet, taken as a table over the emitted text. The last column is the bullet's own test: what an unchecked edit to the printer would and would not repair.

| Property | What the emitted C says | What a printer edit would and would not fix |
| --- | --- | --- |
| Pointer representation | The buffer arrives as `uintptr_t bs`; every read is `_br2_load((uintptr_t)(((char*)(bs))+(((uintptr_t)1ULL)*((uintptr_t)23ULL))), 1)`, an integer cast to `char*`, advanced, cast back, and dereferenced through `memcpy` inside the preamble's switch on the access size. bedrock2's memory is a map from words to bytes and its `expr.load` takes a word, so the integer is the representation and not an accident of printing. | A printer could spell `bs` as a capability-typed parameter and the arithmetic as an offset from it, but the theorem it prints from is stated over the integer-addressed memory and says nothing about a capability's bounds or tag: the relation ends at the bedrock2 function. |
| Provenance | Every address is computed by integer arithmetic on `bs`. On this machine an integer write yields an untagged capability (R-05-136, M0.6e's e3), so under purecap each of the seventeen `_br2_load` call sites would fault or would need a capability to carry the provenance the arithmetic strips. | A printer could emit `cincoffset` instead of `+` and keep the tag; what it could not emit is the proof that the offset stays inside the capability's bounds, which bedrock2 never states because it has no such object. |
| Bounds | There is no runtime bound in the C: the one bound is the `spec_of` precondition `len = word.of_Z (Z.of_nat (length bs))`, discharged at each read by the derivation, so a caller that lies about `len` gets undefined behaviour at the C level and is refused only by its own proof. | Nothing in the printer decides this. The bound lives in the relation, and a capability target would enforce it at the hardware bounds check, which the relation does not mention. |
| Calling convention | `uintptr_t descriptor_check(uintptr_t bs, uintptr_t len)` returns `uintptr_t`; the emitted entry spills `x11` and `x10` and reads them back as integers, the ini naming `arch=riscV`, `model=64` and `-mabi=lp64d` for the assembler. Of the 21 `call` instructions in the `.s`, seventeen are `call _br2_load` and four are `call memcpy`, the always-inline preamble not being inlined by `ccomp -S` at this setting. | A printer could name a purecap ABI in its prototypes; the frame layout, spill discipline and argument capabilities are M1.2d's, and no edit here reaches them. |
| External calls | bedrock2's `cmd.call` names its callee by a string literal and this function makes none; the `memcpy` in the `.s` is the preamble's, not the program's. Rupicola's `c_module` prints the preamble once per module: here 1,110 bytes over 28 lines, everything before the line declaring the function. | The preamble is where a printer edit would go, `_br2_load` taking a capability rather than an integer, and it is exactly the code no theorem covers: `Rupicola/Lib/ToCString.v` at 217 lines and `bedrock2/ToCString.v` at 324 hold zero `Theorem`, `Lemma`, `Proof` and `Qed` tokens between them, as M1.6 measured and this lane re-measured in the same switch. |
| Failure behaviour | The only failure is the Gallina one: `status_invalid`, a word `2`, assigned at the twenty-one refusing sites the printer emits from the source's sixteen, none of which reads past the admitted length. bedrock2 has no trap, no exception and no undefined value at this level; a malformed input is answered, never faulted on. | A capability target adds a second failure kind, the bounds or tag fault, which the C cannot express and the printer cannot invent; what a purecap backend does with a fault on this code is M1.2's semantics and not a printing choice. |

The bullet's last sentence is therefore confirmed on this program rather than argued: an integer address is not turned into a capability by an unchecked change to the printer, because every property in the table lives either below the printer, in the bedrock2 relation that stops at integers, or above it, in a backend that does not yet exist.

## The two device arms

Q2's fourth bullet reserves the choice; this is the comparison and one recommendation, taken as text.

**Arm A, capability-aware lowering through M1.2's backend.** The C reaches the contained `ccomp` today at exit 0, and what comes out bounds the arm: `-S` reaches the stock `riscV/` backend and emits 309 lines of lp64d RV64 over 21 mnemonics with no capability instruction, and `-S -dcapasm` emits a 523-line term carrying **115 `TODO` tokens over 16 distinct arms**, every one of which this program needs: `Pcvtw2l` 32 times and `Psltiul` 23 for the byte-to-word widenings and the comparisons, `Pbnel` 18 and `Pbeql` 15 for the branches, `Pseql` 6, `Psubl` and `Pluil` 4 each, `Psllil` and `Psrlil` 3, `Pbgeul` once, and the six capability loads and stores `PCUlbu`, `PCUlhu`, `PCUlw`, `PCUsb`, `PCUsh`, `PCUsw` once each. That printer is struck at M1.2 and stays struck; the census is the size of this component's gap against the backend M1.2b through M1.2f author, not a proposal to fill the arms. M1.2f is where generated C through `ccomp` to `asm.py`, `image.py` and the golden emulator closes, and it is the arm whose remaining work is already priced and sequenced on the plan.

**Arm B, a justified adaptation of the verified backend.** [VerifiedExit.v](VerifiedExit.v) runs `coq-bedrock2-compiler` over this component at the shipped instantiation, `Words32Naive` and `RV32I`, and emits **257 instructions over 11 mnemonics**: `Addi` 70, `Sltiu` 32, `Jal` 29, `Beq` 29, `Add` 20, `Sw` 18, `Lw` 18, `Mul` 17, `Lbu` 17, `Sub` 6, `Jalr` 1. Two things the census settles. The target is the plain RISC-V R-18-002 forbids at either width, the stack pointer an integer register and no capability instruction anywhere, `riscv-coq`'s `InstructionSet` enumerating sixteen constructors with no arm a capability set could be added at without editing the type. And the alphabet is not even RV32I: `compile_op_register` in `FlatToRiscvDef.v` takes no instruction-set argument and maps `bopname.mul` to `Mul`, `mulhuu` to `Mulhu` and `divu` and `remu` to their own, so the seventeen `1 *` index scalings the array access emits, one per load site in the C, come out as seventeen RV32M instructions under an instance declared `RV32I`. Adapting this arm means a fork of the verified backend, `riscv-coq`'s closed instruction type, the compiler's `FlatToRiscv` and its correctness proof, against a machine with no integer-addressed access at all (R-15-001c). M1.6 measured that fork's start as editing a sixteen-constructor type carrying zero capability tokens; nothing here narrows it.

**Recommendation, not decision.** Arm A. It is the only arm aimed at a backend R-18-002 admits, its gap on this program is measured to the arm and the token, its remaining work is M1.2b through M1.2f as already priced, and the C it consumes is what this loop already emits. Arm B buys proof transport to a machine the register forbids, at the price of forking a verified compiler whose alphabet is RV32IM. What Arm A does not buy is stated as plainly: the relation from the C to the device stays CompCert's theorem on a target the register admits only once M1.2 completes it, and the relation from Gallina to C stays the printer's, with no theorem, which is the fork M1.6 recorded and the second front end the bullet names.

**What stays a register act.** R-05-043's criterion counts the synthesis as proof transport rather than an anchor, and R-05-021 admits a verified compilation step with no clause about where the transport stops; both assume a single path carrying both properties, and this loop is the exit with the C and without the theorem. The Clight intermediate R-05-043 names is emitted by neither exit: the reaching one emits C source text and the verified one encoded words. Both are M1.6's findings met again on a second program and are reported, not closed.

## Measurements

Q2's fifth bullet, host half. Every figure below is taken with the switch and `ccomp` above. **The timings decide nothing and are labelled so.** The identical file's `Time compile.` measured 34.5 s and 90.7 s in two runs an hour apart, on a host on AC with one sibling proof build running at `-j4` throughout, and 224.8 s in a run on battery under a ten-lane fan-out: a spread of six and a half over one unchanged input, which is a property of the machine and not of the derivation. What is load-bearing is the counts, the sizes and the digests, and those reproduce exactly, the second run's emitted C being byte-identical to the first's. The C figures are the bytes between the quotes of the `Redirect` output, as [DIGESTS.md](DIGESTS.md) states.

| Figure | `descriptor_check` | `ip_checksum` (shipped) | hand-written C of the same check |
| --- | --- | --- | --- |
| Gallina source | 313 lines, 56 definitional commands (51 `Definition`, 4 `Lemma`, 1 `Instance`, 0 `Fixpoint`, 0 `Inductive`), 0 `fun` | 39 + 183 + 104 lines in the package | n/a |
| Hand-authored glue | 35 lines: `spec_of` 10, three `Hint` commands over 9, `Ltac` 8, `Derive` block 8 | 26 lines: `spec_of` 10, four `Hint` commands over 5, one side lemma of 3, `Derive` block 8 | 45 lines of C, every constant typed by hand |
| `Derive` | closes at `Qed`, `Closed under the global context` | closes at `Qed`, `Closed under the global context` | no proof |
| `compile` / `Qed`, one-shot, on AC beside a `-j4` build | 34.5 s / 13.5 s | 7.1 s / 0.2 s, the shipped file re-derived in the stage | n/a |
| `coqc` wall, peak resident, same run | 50.3 s, 834,660 KB | 7.9 s, 508,464 KB | n/a |
| Emitted C | 7,874 bytes, 202 lines | 2,340 bytes, 62 lines | 1,335 bytes, 45 lines |
| `ccomp -S` | 309 lines, 254 instructions, 21 mnemonics, 0 capability | 148 lines, 120 instructions, 26 mnemonics, 0 capability | 141 lines, 106 instructions, 14 mnemonics, 0 capability |
| `ccomp -S -dcapasm` | 115 `TODO` over 16 arms | 53 `TODO` over 20 arms | 46 `TODO` over 10 arms |
| Verified exit | 257 instructions, 11 mnemonics, 17 of them `Mul` | n/a, not run | n/a |
| Target cycles | `M1.2f` | `M1.2f` | `M1.2f` |
| Peak storage on target | `M1.2f` | `M1.2f` | `M1.2f` |

The generated C is 5.9 times the hand-written C by bytes and its assembly 2.4 times by instruction, which is where the route's cost sits at this size: the relational compiler re-materializes a bound boolean rather than copying it, `ok = d < 2` standing six times over three buffer references against `ok = c < 2` three times; every refusing path carries its own `st = 2`, twenty-one of them for the source's sixteen; and the preamble is 1,110 bytes of the 7,874. What the hand-written C does not have is the relation: its proof side is not taken here, no CompCert-C/VST refinement of this check existing in the tree, so the comparison is size and alphabet alone and says nothing about proof cost on the manual route.

**The maintenance probe, and it is asymmetric.** Two source changes, each regenerated in a stage of its own, and they price the two directions the maintenance cost runs in. **A constant the owner moves is free.** The owner gains a flag, `flag_count` 2 to 3 with `enc_flag_spare_bits` 6 to 5 so that its own well-formedness theorem still holds: two owner lines, **zero lines of the component**, no new hint and no new lemma, the derivation closing at `Qed` with `Closed under the global context`, and the C moving at exactly its six flag tests and nowhere else, `< 4` becoming `< 8`, at the same 7,874 bytes and 202 lines under a different digest, which is the drift `--check` reports. **A hypothesis the specification moves is a proof-engineering act.** The component's own precondition tightened to one slot, `Z.of_nat (length bs) < 2 ^ 64` to `<= Z.of_nat ring_descriptor_size_bytes`, is one component line and no owner line, and the derivation stops: `compile` reports `Compilation incomplete` at **seventeen** sites and `Qed` refuses with *Attempt to save an incomplete proof*, exit 1. Nothing is emitted, so there is no C to compare; closing it again is work on the side-condition tactic and not a regeneration. That asymmetry, and not the code size, is what this route costs to maintain, and it is the answer to the bullet's *expose the maintenance cost* that a single probe would have missed.

## Not taken, and what each waits on

* An execution on the target model, target cycles and peak storage: **M1.2f**, through M1.2b to M1.2e, which is Q2b.
* The relation to the Sail model, the intermediate-language step included: the two register acts above, and a backend that exists.
* The VST side of the manual-route comparison: no refinement of this check exists in the tree.
* Any claim past the first boundary: Gallina to bedrock2 is the `Derive`; bedrock2 to C is a printer with no theorem; C to RV64 is CompCert's theorem on a target R-18-002 forbids; RV64 to this machine does not exist.
