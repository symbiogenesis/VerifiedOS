# Completion Log

*Completion evidence for landed items in [the implementation checklist](implementation-checklist.md). The checklist owns the items, estimates and order; this log records their accepted outcomes and review evidence.*

## How to read this

Each entry gives the accepted result, decisive validation and material limits. Keep the artifact or contract links, evidence provenance needed to assess acceptance, recorded findings and landing tier. Distinguish a specification from an implementation, bounded checks from general guarantees, and passed checks from failed, skipped, canceled or pending ones.

Omit dispatch plans, partial progress histories, command transcripts, diff sizes, repeated routine gate inventories and incidental counts. Detailed mechanisms belong to their owning artifacts; measurements remain tied to their recorded inputs. Retained-estimate entries keep the original range and why actual effort is unavailable.

Entry headings match checklist labels and follow checklist order, with children one heading level below their parents. `tools/check.py` checks entry membership, findings blocks and landing declarations. The [findings register](../assurance/findings-register.md) owns each finding's description and disposition; this log holds no open obligations.

Evidence links resolve to [retained verbatim records](retained-evidence/README.md) that survive working-storage cleanup. Those records and their identities are unchanged when an entry is shortened.

## S · Serial-path decisions and program instruments

### S1 · Discharge the owed register acts

The register and profile decisions unblock kernel semantics, capability-bounds containment, test-exit policy, IDL ownership, SoC scope, single-instance bring-up and static measured boot. The matrix instruction decision remains with M0.8c and requires R-15-116's measured margin. Changed entry/prose pairs were read together and blessed.

  * Landed: Tier A.

### S2 · Adopt the two-tier landing rule and hold it by rule

K-84 checks that holder citations name registered rules and that Tier-B declarations name holders. Checker, mutation selftest, tools suite and typechecks passed. Whether a rule holds the claimed fact remains a review judgment; prior undeclared tiers are not assigned retroactively.

  * Landed: Tier A.

### S3 · Delete the dormant backends and inert vendored surface; initialize the gitlinks

Removed dormant Lean, Lem, Isabelle and HOL4 targets and unused imported support while preserving Rocq, SMT, live test downloads and build dependencies. Initialized the imported cores reached by R1b/R1c; absent OpenTitan still blocked elaboration. Model build, tests, profile sweep, corpus, proof audit and host checks passed; affected owner claims were repaired.

### S4 · Measure Sail emulator throughput against the M2 gate

Measured twelve integer/capability-loop runs at model revision `d359483-dirty`: untraced floors were 95/71 kIPS and traced floors 73/66 kIPS. Existing loops through M6 were not emulator-bound, so M2 remained struck. The projected 240-second boot ceiling permits about 1.7 × 10<sup>7</sup> instructions; M7.1 must replace it with a composed-boot measurement. Trace storage was 57.6–67.0 bytes per instruction. Model, proof and host checks passed.

  * Seven findings.
    * **The M2 gate carries no threshold.** Its entry asks whether Sail is *sufficient through M6*, and its trigger whether S4 finds it *insufficient through M6*; no repository artifact defines a number.
    * **No register entry owns a throughput floor or a boot-time ceiling for the development vehicle**, and no profile line or contract states a kIPS floor either.
    * **No workload short of the composed boot can carry the figure, and none can before M7.1.** The 199 `riscv-tests` are refused 199 of 199 on the frozen profile, every one addressing memory through an integer base register; the 26 differential-corpus members run 120 to 1,996 records and are startup-dominated; the rig is socket-bound; and the composed image does not exist until M7.1.
    * **The commit trace's cost is storage rather than speed.** Tracing costs twenty percent of the rate against 57.6 to 67.0 bytes a retired instruction: the CI arm's constraint is disk and the daily driver's is neither.
    * **A lane's emulator is stamped `-dirty` whatever the lane's state is.** [The configure line](../../tools/vos/cli/model.py) exports `GIT_DIR` to the child so that `git describe` finds the lane's commit, which is I7's finding answered, but it exports no `GIT_WORK_TREE`, so git takes the child's working directory as the tree and reads every tracked file as deleted.
    * **Three commands the table declares host-capable could not run on the host.** `config-keys`, `validate-config` and `asm` were in the `model` command's `host_ok` set, and `model`'s own `main` called `env.load()` before dispatch, which refuses on `win32`, so the declaration was unreachable and an assembly on the host was a hop into the guest.
    * **The merged register file makes an ABI integer name an authority destroyer, and the failure surfaces millions of instructions late.** `s0` is `x8` and `c8` is where every program here parks the root data capability, so a loop counter named `s0` clears that authority and the program runs correctly to its exit store and then traps there.

  * Landed: Tier A.

### S6a · Authenticate bounded host replay artifacts

The [host replay envelope](contracts/host-replay-envelope.md), landed before implementation at `f555b70b`, authenticates exact bounded replay bytes and independently supplied capture/trace identities before decoding. At `7dfb1cfa`, all eleven focused cases, typecheck and Ruff passed; integrator review checked authentication ordering and the independent wire oracle. The integrated host wave remained required.

Landed: Tier A. This accepts a development host instrument only. Production
sealing, device export authority, source completeness, signed-image trust and
paired machine replay remain open under S6, whose operational estimate is unchanged.

### S7 · Reconnaissance passes on R1b, M4.4, M6.2 and M2.3

The source/licence review rules out CHERI-seL4 kernel incorporation under this tree's terms and reprices clean implementation owners. CVA6 review separates configuration from authored cache removal and identifies the second store-holding structure and literal drain-bound dependencies. Kami's permissive terms were confirmed; Kôika's only/or-later status remained undecided. A cache-free elaboration measurement still requires R1b's replacement work.

  * Landed: Tier A.

### S8 · Extract and index the findings register

Extracted [the findings register](../assurance/findings-register.md). K-82 holds counted findings and their index total in both directions; prose-only findings retain a manual reading boundary. Checker, mutation/repair tests, tools tests and typechecks passed. Admission-input and capability-exponent gaps were reported to their owners.

  * Landed: Tier A.

### S9 · Make the lane host-portable, and retire S14's first blocker

[The provisioner](../../tools/vos/cli/provision.py) represents the lane as probes and owned installation recipes, with a report-only default and explicit apply arm. Versions come from their owners. Host checks, mutation selftests, tools tests and typechecks passed. Installation was unexercised on the already-provisioned host; WSL reclamation and editor posture remain outside its verdict.

  * Ten findings.
    * **The pinned solver's acquisition route was stated in no artifact and is now measured.** `/root/z3-5.1.0` is an unpacked `z3-solver` wheel, tagged `manylinux_2_38_aarch64`, and `uv pip install --target` of that distribution reproduces its `bin/z3` byte for byte at 20,515,824 bytes on one sha256.
    * **No register entry owns the development lane's toolchain at all.** The register books reproducibility of the shipped placement map and of the certifying toolchain, and nothing about the environment the golden model is built in.
    * **Verilator's pin was restated in three places and no rule held it, and I15 has since answered it**: [THIRD-PARTY.md](../../THIRD-PARTY.md)'s development-tools row, its own Verilator paragraph, and `rtl.py`'s `VERILATOR_PIN`.
    * **No artifact declared the distribution-package set the model build needs**, and the provisioner becomes its owner.
    * **Three provisioning routes have owners this tree cannot state as argv, and they are not the rows that plan nothing.** Each is reachable prose and none is a command a tool can run.
    * **The install arm is unexercised on this box, every fact being satisfied already**, so the tests hold the plan and never the execution: an injected table drives the probe-to-command mapping, and idempotence is held as the property that a satisfied probe yields an empty plan, a claim that decides nothing about an arm that never ran.
    * **I7's lane defect reaches a second site, and it is the corpus parse rather than cmake.** [vos/corpus.py](../../tools/vos/corpus.py) reads the git index without the `GIT_DIR` translation `env.git_dir` already provides, so inside the guest on a *linked worktree* `python3 tools/check.py` ends in a traceback naming `not a git repository` rather than in a verdict, and three `test_figures` cases fail the same way; the primary worktree is green on both lanes.
    * **I8's ground names two opam switches and this lane now carries four**, M1.5's CertiRocq switch and S13a's QuickChick switch having landed after that sentence was written.
    * **Every figure any document states about the fact table was a hand-copy, and three of them were wrong on the day they landed.** The row count, the rows carrying a command, the rows carrying none and the opam switches among them are each read off `FACTS`, restated across this cell, S14's and [tools/README.md](../../tools/README.md), and owned by nothing: K-75 holds one literal in that file and no rule computed a count over the table.
    * **A lane can block its own merge from outside its worktree, and no gate it runs can see that it has.** A zero-byte untracked `tools/vos/cli/provision.py` stood at this tool's own path in the primary worktree, where `git merge` refuses to overwrite an untracked file with a tracked one, and where the selftest's sandbox, which reads untracked files against `check.py`'s index, would take it as an empty source under `tools/`.

  * Landed: Tier A. Tier B's fourth condition is met in more than part and still not in whole: K-75 holds the one figure this act restated and K-24 the counts any document states about its table, while the two facts the act *created*, the distribution-package set and the z3 acquisition route, are held by nothing, and a full read is owed for the rest. Inventing a rule to hold a package list would be worse than saying so, I12's and S13b's precedent.

### S10 · Shard the hot files for ten-lane operation

Both child items landed; their evidence follows.

#### S10a · Shard `counts.py` by rule family

Split counts rules into sibling modules while retaining the claim table and run order. Definitions/functions matched the pre-shard implementation apart from intended comments/indentation; registry and selftest cases were unchanged. Host checks, mutation selftests, tools tests, typechecks and idempotent repair passed. Pre-existing dead-claim suppression under repair was left unchanged.

  * Landed: Tier B, held by **K-00**, which carries every one of the fifteen ids across the shard in both directions.

#### S10b · Move the per-item completion notes to the completion log

Moved landing notes into this log and kept completed checklist cells, summaries and entry links. K-82 checks entry membership and K-12 checks links. Live calibration holds in frozen notes were removed. Host checks, mutation selftests, tools tests, typechecks and idempotent repair passed; no model, RTL or proof run was required.

  * Three findings.
    * **A figure a checker rule holds live inside an item's cell loses its hold when the item lands**, the cell becoming a note this file keeps frozen, so an item whose cell carries a K-96 judged sentence or a K-24 claim must move or drop the hold in the same act, as the two holds above did.
    * **No landed item carried prose after its child items**, so every note was one contiguous span between its header line and the next item line, with nothing to attribute by hand.
    * **The fragment links inside the moved notes named two headings of the checklist**: the build-loop instruments section, which this file carries and the links now resolve inside, and the calibration record, which it does not and whose link was rewritten to point back at the checklist.

  * Landed: Tier A. It rewrites the checklist's conventions and its summary, retitles this item, and edits the findings register's preamble, so it is read whole; **K-82** holds the entry set this landing created and **K-12** the links, which is more of Tier B's fourth condition than most landings meet, and the read is still owed for the conventions.

### S11 · Join the TestRIG ecosystem over RVFI-DII

[The RVFI-DII rig](../../tools/vos/cli/testrig.py) shares trace adjudication with the corpus and documents packet projection/elisions. Generated no-defect streams agreed; all four seeded defects were detected on every seed; shrinking and packet/record comparison passed. Model build, corpus and host checks passed. This qualifies transport and seeded self-comparison: no independent second executor existed, and unrepresentable block operations were excluded.

  * Seven findings, the first two being why the rig works at all.
    * **A torn record reads as a divergence about a run that agreed.** The commit trace's default destination is `stdout`, block-buffered into a pipe, while the RVFI diagnostics go to an unbuffered `stderr`, and the end-of-trace acknowledgement prints verbosely whatever the trace flag says, its call site passing a comparison where every other passes the flag.
    * **Forty-seven milliseconds an instruction, and it is Nagle's algorithm on the implementation's socket.** A version-2 reply is two or three separate writes, the packet and each announced extension, and the second waits on an acknowledgement this side has nothing to piggyback on.
    * **The block operations stop the emulator rather than reporting something narrower.** The packet's write and read raise an internal error above sixteen bytes, so `cbo.zero`, `cbo.scrub`, `cloadtags` and `creclaim` abort a run under injection.
    * **The two emitters disagreed about a word whose low two bits are not `11`.** The profile excludes `C` and fixes ILEN at 32, but the fetch path still took upstream's compressed branch: the commit trace reported the sixteen-bit halfword the model decoded and the packet reported the whole injected word.
    * **The source half of the Integer extension is declared and never written**, both source addresses and their data always zero, which is vacuously legal under the packet's own rule and is what a comparison over the full field set would find first.
    * **The physical-address width is 64 and not 36**, so a commit memory record's address is sixteen hexadecimal digits: the 36-bit space is a property of the composition, not of the model's address type.
    * **The drift this item would otherwise leave unheld is held by a rule**, K-85 in the differential group: every record kind §4's schema table declares appears in exactly one of §9's meeting table and its elision table, and that membership is the record set the projection and the view actually produce.

  * Landed: Tier A.

### S12 · Read, pin and dispose the six unnamed start-froms

Read and pinned permissive Rupicola, Katamaran, Sail-to-μSail, Cerise/Cerisier and capability-property sources; [THIRD-PARTY.md](../../THIRD-PARTY.md) owns their terms/dispositions. Pin consistency, host checks, mutation coverage, tools tests and typechecks passed. Plain RISC-V Bedrock2 supplies no purecap backend. The NTT deposit still needs a terms reading under the recorded rule; the translation seam has no register-owned terms obligation.

  * Landed: Tier A.

#### S13a · The three instruments

Added standing [oracle](../../tools/vos/cli/oracle.py), [seed](../../tools/vos/cli/seed.py) and [QuickChick](../../tools/vos/cli/quickchick.py) instruments. Generated campaigns killed live capability, Keccak and admission mutants, reporting non-compiling mutants separately. Ten admission-definition mutants passed the original theorems but vectors detected them. Host checks, model build/tests, proof audit and unchanged RTL crosscheck passed. Checkout mutation needs exclusive use; enumeration and QuickChick provide complementary coverage.

  * Three findings.
    * **The `$[test]` harness reaches the packing after all, and the difference is resolution, not reach.** All five live packing mutants are killed on both sides; the harness reports the same property for all five, the alphabetically first to fire and the point at which it stops, where the vectors name which of six abutting fields moved and on how many lines.
    * **A mutation loop that writes into the checkout is a loop nothing else may read beside.** `seed.py properties` mutates `model/` because cmake is pointed there and a copy is a cold build per run.
    * **The model lane's opam environment leaks into the prover lane, and the failure names neither.** Every model loop needs the Sail switch's variables exported, a prover child inherits them, and where that child shells out to `ocamlfind`, as QuickChick's extraction does, findlib sees two definitions of one library and picks the wrong one.

  * Landed: Tier A.

#### S13b · Absorb the checker's selftest into the mutation engine

Unified [mutation verdicts/reporting](../../tools/vos/seeded.py), keeping an unapplied authored seed (a failure) distinct from a non-compiling generated mutant (no oracle verdict). Case table and registry were unchanged. Host checks, mutation comparison, repair path, tools tests and typechecks passed. Narrowed selftests name cases not run.

  * Two findings.
    * **A fifth mutation loop was outside this absorption, and I14 has since absorbed it.** [tools/quarantine/gate.py](../../tools/quarantine/gate.py) carried its own `MUTANTS` table, its own in-memory seeding and its own accounting.
    * **This item's own stated blocker does not survive inspection.** An appended case sits at the end of a 570-line data region and the run loop is 170 lines below its close, far outside the three lines of context a merge reads; the region came through this act byte-identical, so a concurrent append had nothing to conflict with.

  * Landed: Tier A. Tier B's fourth condition is a rule holding whatever fact the landing created, and this act moves no rule id and creates no fact any K- rule reads, so K-84 has nothing to hold.

### S14 · Unattended CI on whichever host runs it

Declined the then-unexercisable workflow after a stripped-host probe found missing bootstrap ownership. Repaired absent-installer traceback to per-step refusal. Host checks, mutation selftests, tools tests and typechecks passed; stripped-host probes exited 1 and no workflow ran at that decision. The push workflow subsequently landed; its evidence remains distinct.

  * Five findings.
    * **The gate group cannot be stood up from zero: two commands and one missing installer**, measured on the stripped host above.
    * **A workflow's green was unobservable at this decline**: no runner was registered against either remote and nothing in the session exercised a hosted image, so an authored workflow could not be held to anything before it landed.
    * **Three classes of fact a workflow must state have no owner in this tree**, the runner label, the action references it pins, and the bootstrap route.
    * **`--apply` ended in a traceback, not a verdict, where an installer was absent**: S9's artifact pointed at a host that is not the lane, the one defect this measurement found in it.
    * **The decline falsifies eight present-tense sentences elsewhere and each is repaired to what is true**: lane 9's open content, the two sequencing rows, the Tier-B risk row, M7's lead and M7.1's cell, S9's own forfeit clause naming this item as what answers the group split, and F-181's disposition in [the findings register](../assurance/findings-register.md).

  * Landed: Tier A.

Related findings: F-197d.

### S15 · Generate the derived artifacts from their owners

Tracked the model-generated bundle and replaced live Sail parsers with artifact readers. K-88 checks tracked bytes/source digests on the host; guest regeneration decides emitter equality. Mnemonic enumeration is a safe ceiling, not an exact census. Host checks, mutation/repair tests, typechecks and guest bundle comparison passed. The bundle generates neither prose nor RTL restatements.

  * Six findings.
    * **The emitter writes the checkout into the artifact, so a generated file holding a commit could never be held byte-for-byte.** `sail --doc` asks git where it is standing and, where that answers, writes the commit and a dirty flag into the bundle.
    * **A generated artifact broke a total-class rule on contact, and the rule was silent about why.** The bundle is one line of four megabytes in which every Sail bit literal reads as a short object id on a line that has already named an upstream, which K-81 read as **2,809 pin restatements**.
    * **Repointing a parse moved a selftest case's subject out from under it.** K-78's mutant seeded a model source that the core-class reading no longer opens, so the edit reported as a stale artifact and the rule it was meant to prove survived.
    * **Two artifacts cited constructs this tree does not carry.** The decode parser's docstring and K-66's registry row named an instruction shape taken from upstream under a name the curated model does not spell, the vector segment form and a widened atomic having each been curated out.
    * **The encoder table was a subset of the surface and nothing held the gap, and M1.4′ has since closed it by generating the table.** 593 of the 946 mnemonics the model spells had no row in the dialect's encoder table when this item measured it, subject to the over-approximation above.
    * **A count went stale where its own list shrank.** The tools' README stood a sentence naming five readers above a list of four, S16's move having taken one out.

  * Landed: Tier A. The generated artifact and its owner record are held by **K-88**, but K-66's direction is a changed claim about what a registered rule decides, not a repair to it, and a changed normative claim is a full read.

### S16 · Quarantine the instruments whose decisions are deferred

Moved deferred freeze/bank-count instruments into [quarantine](../../tools/quarantine/README.md), retaining contracts and separate gates. K-83 forbids landing-loop imports/path references into it. Host and quarantine checks, mutations and behavioral tests passed. Freeze inputs remained deferred and no bank candidate was admitted. Release requires the consumers/qualified data named by the owner.

  * Landed: Tier A.

### S17 · Re-read the standing adoptions against the ratified extension list

The dated source review kept all five proposed extension adoptions active and unratified, updating [the profile](../hardware/isa-profile.md). Host checks, mutation selftests and typechecks passed without register/co-read change. R-15-067p's scalar premise and R-15-067k's review-trigger vocabulary required owner amendments; this survey admitted no instructions.

### S18 · Author the acceptance predicates five open items owe

Authored independent acceptance predicates for M1.7, M4.4, M5.3, M6.3b and M6.5b with existing instruments. Partial predicates name missing decisions/mechanisms. The lane checker was red only on derived arithmetic under K-36, K-37 and K-82; typechecks and remaining rules passed. A red baseline supplies no mutation verdict; repair and integrated gate were deferred.

  * Nine findings, three of them the review gate's own reading of these cells and all three repaired here.
    * **Three device windows every shipped composition declares are claimed by no accessor, so an access answers zero instead of refusing.** `platform.blkdev`, `platform.uart` and `platform.boot_rom` are declared in all three configurations, held to `IOMemory` placement by [the validator](../../model/model/postlude/validate_config.sail), and emitted into the attested devicetree as `verifiedos,block-device`, `verifiedos,uart` and `verifiedos,boot-rom`; none appears in `within_mmio_readable`, `within_mmio_writable`, `mmio_read` or `mmio_write` in [sys/platform.sail](../../model/model/sys/platform.sail), so an access falls through to the RAM path.
    * **The emulator has no second bus initiator, so the DMA obligations have no mechanism to be measured over.** R-12-100's acceptance clause has the engine present the capability to the fabric for every access and a non-capability DMA write clear the tags of every granule it covers, and R-15-206 fixes the two admitted shapes; *DMA engine* occurs once in [sys/platform.sail](../../model/model/sys/platform.sail), in a comment naming what the reset hold covers, and every access this model makes is an instruction's.
    * **The recovery discipline M5.3's crash half would be stated over is still unchosen**, which is [JournalIndex.v](../../proofs/JournalIndex.v)'s reported gap met at the item that would measure it: both arms are exhibited, each keeps every obligation the other keeps, and from one crashed journal they reach different stores, so a predicate naming a post-crash store would take the decision, not measure it.
    * **The intent vocabulary a deterministic translation cache would be keyed on is still unenumerated**, which is [HandlerGraph.v](../../proofs/HandlerGraph.v)'s reported gap met at the item that owns the cache: the entry calling an intent a closed variant closes no variant set anywhere, so the key has nothing to quantify over.
    * **A predicate that would have a reader compute what the machine already decides is refused.** M4.4's containment half was first written as a condition on the trace, that no record carry a tagged capability outside the instance's root; deciding that means decoding the bounds triple, which [the corpus document's §4](../assurance/differential-corpus.md#4-the-commit-trace-schema-version-1) declines to do inside the reader, having the rig not re-derive base and top, a second implementation of the bounds algorithm inside a trace reader being a second place for it to be wrong.
    * **M4.4's name claims a plurality its own first bullet has ruled out, and no rule reads a cell's name against its bullets.** The item is *bring up one isolated C instance per emulated core* and its opening bullet takes the single-instance ruling, so *per emulated core* is one instance and the duplication the name promises is R2's.
    * **A predicate authored from a register entry alone re-asks what a landed artifact already answers.** R-18-037 names five test families and R-12-100 three clauses, and M6.4's generated [RingContract.v](../../proofs/RingContract.v) already attains the batch and segment maxima, states the payload as exactly the declared segments, spends a cancellation interval with the DMA quiescence inside it, and refuses a stale generation, over [a declaration](../../interfaces/ring-reference.json) fixing `max_segments` at 4 and `segment_max_bytes` at 1024.
    * **A measurement is stated in the unit its instrument emits.** An in-slot bound is cycles: R-11-015 derives it as a static max-path sum and [CyclicExecutive.v](../../proofs/CyclicExecutive.v) puts `slot_bound` in `slot_width`'s and `switch_cost`'s unit.
    * **Restating a condition already decided by a host rule adds no check.** **K-51** assembles every corpus program on every host run, so once M1.7's image is a corpus member its assembling is decided upstream of any condition that cell could write, and a condition that cannot fail where the bullet above it passes discriminates against nothing.

  * Landed: Tier A. Every cell this item writes is a claim about what a later gate must measure and no rule reads a predicate cell, so nothing holds what the landing created, which is why none of the three chain items becomes Tier-B admissible, and a full read is owed. The owed acts it reports are the register's, the model's and the plan's, none a rule this act could have written.

### S19 · Re-fit the calibration across both execution modes

Kept attended/agent-parallel calibration separate because their actuals measure different quantities without a conversion. Recorded earliest/taken-price bases, excluded moved-scope pairs and changed no midpoint. Host checks, mutation selftests, crossed-record tests and typechecks passed. Small pools and unrecorded parallel pass counts limit interpretation.

Calibration: no original estimate was recorded; excluded from the fit.

  * Six findings.
    * **The two execution modes cannot be pooled, and the disqualifying fact is the unit, not the spread.** The attended and parallel actuals are different quantities, elapsed attended time and summed agent-session wall-clock.
    * **The overrun pattern does not separate the modes; the asymmetry this item set out to record was an artefact of reading overruns on one basis and ratios on another.** On the record's own basis the class-X-authored pool is the most overrun-prone in both modes, 2 of 2 attended and 1 of 2 under fan-out against 9 of 45 and 1 of 7 for class I; that no class-X item overran under fan-out holds only against the taken prices, where M6.3a reads 0.83 and on the record 1.25.
    * **The n = 2 pool is closed to new members by execution mode, not by scarcity.** Both class-X-authored items landed since the fit, M6.0b and M6.3a, ran under fan-out, while the class-X residue before the M8a gate, which the basis counts beside the gate figures, is not empty; the other two class-X landings are outside the pool for other reasons (M1.6 read rather than authored, M3.4a's scope moved).
    * **The record's earliest-estimate convention measures a different thing in each series.** Six of the ten fitted agent-parallel items were re-priced downward at one act before any of them ran, one upward at another, and three never were (third bullet), so the earliest figure and the price the work was taken at differ by 20.5 h over the series and by nothing for those three.
    * **M3.4a's pair is unusable for calibration, and the convention F-205l asked for is now stated**: an item whose scope moved between its pricing and its landing is outside the fit and carries `n/a`.
    * **The parallel actual is a sum over passes and nothing records how many.** The convention defines the figure as the summed wall-clock of an item's authoring, verification and repair passes, and no cell states its pass count, so two items reading 7.5 h may be one pass or four.

  * Landed: Tier A. The ruling is a decision item and the `n/a` convention is a new normative claim about the record, so the mechanical conditions do not reach it however green the gates are.

### S20 · Repair the claims a later act falsified, across the plan and the findings register

Re-read stale plan/register claims, carried owner decisions back to reporting sites and removed redundant live-figure copies. Historical gate measurements were not recomputed. Typechecks and non-arithmetic rules passed; derived arithmetic under K-36, K-37, K-96 and K-82 remained red. No mutant verdict was available until integrated repair.

Calibration: no original estimate was recorded; excluded from the fit.

  * Eight findings.
    * **A register act closes a gap the plan reported and nothing carries the answer back to the cell that reported it.** M3.6a reported five register gaps; all five are taken at their own entries and read `closed` in the findings register, while the cell went on saying *is unstated* and *Owed at* at four of the five bullets and naming no ruling at the fifth.
    * **A disposition moved to `closed` while the plan bullet it indexes still read *reported rather than closed*.** F-142i and F-204 record acts that have been taken, and the bullets at M1.9 and R1c-i that they index still owed them.
    * **A landing falsifies the decline that priced it, [F-198d](../assurance/findings-register.md)'s class running the other way.** S14 declined the workflow on a measurement, and the workflow has since landed; four present-tense sentences in S14's and I8's cells and two dispositions in the findings register asserted there is no continuous integration here.
    * **A figure an artifact computes about itself was transcribed into the plan and drifted by twenty-three members.** [DischargeSequence.v](../../proofs/DischargeSequence.v) computes its own generated-family size, and two later passes over that file took the family from twenty-eight to fifty-one and the early-release count from four to seven while M3.6a's cell stood.
    * **A count of a proof file's obligations moves when a later item adds to that file.** M6.4's cell counted the ring campaign's obligations and the repair pass that rewrote the lost-wakeup statement added three theorems to the same file, so the cell understated its own artifact while the exit-evidence figure beside it stayed frozen and correct.
    * **A denominator nothing owns goes stale at the next landing and the numerator does not.** Three sites carried one: six of nineteen gitlinks against twenty-two today, three of twenty declared parameters against twenty-one, and one of fourteen proof sources against sixteen, the last already wrong on the day it landed.
    * **A roster sentence stops enumerating and the same document names the omitted item complete in its own summary.** The `Wasm-parallel` validation list, the open-lane list, and two Sequencing rows each named or scheduled an item this document names complete in its own summary.
    * **The truth of a prose sentence is the one thing no rule in the registry is about, and this sweep measures what that costs.** Every one of the 31 repairs here landed on a tree where `check.py` exits 0, and ten of them are figures, so the gap is not confined to judgment sentences.

  * Landed: Tier A. Nothing holds what this item created: what it repaired is the truth of prose sentences, which no rule in [the registry](../../tools/check-rules.md) is about, so Tier B's fourth condition has nothing to name and a full read is what the rest is owed.

### S21 · Repair the stale claims the tools' own documents carry

Repaired tools descriptions and retired gate paths in proof comments. Landing checks remained red on derived arithmetic, supplying no complete mutation verdict. Earlier tools-only checks/mutations and typechecks passed; test_lanes failed identically on the unchanged linked worktree because an imported gitlink was unpopulated. The out-of-scope licence claim remained with its owner.

Calibration: no original estimate was recorded; excluded from the fit.

  * Ten findings, every one a claim this item measured false and repaired.
    * **A command table transcribed from the entry point's order stopped at seventeen where the entry point carries eighteen.** `run.py help` prints eighteen commands.
    * **A sentence about the one input directory this repository does not author described one artifact where the directory carries two, and sent the byte-identity claim to the artifact this gate cannot decide it for.**
    * **A reader's five documents outside the model were stated as four on the page describing it.** The page describes the capability-format reader; the block-geometry constraint's site and the constant that names it landed in the same commit as the sentence, so the figure was one short the day it was written; the module's own docstring names all five.
    * **A class list that declares itself total named ninety-three of ninety-four rules.** The registry's closing section names them under its four classes, beneath a sentence declaring that it names every one, on the ground that a class list which stopped growing would be that document's own version of the defect it describes.
    * **A rule row located its window two ways and only one of them was carried when the window widened.** K-75's passing-means cell said *every site under `tools/`* and the ground cell says the window is the enumerated sites and that `tools/` carries all but one, the exception being the push workflow's own interpreter line; only the ground was carried when the ninth site landed in the push workflow.
    * **The checker's own map closed an enumeration at eighteen groups where the tool runs twenty-three.** The map closed in the words *three further* and *last*, where `GROUPS` runs twenty-three.
    * **A lane split written when the table held one row survived the row that falsified it.** The generated group's docstring said its emitter *cannot run at this gate at all* and refused to run the generator; both were true of the guest row and false of the host row, whose generator is Python over artifacts this checkout already carries, needs no toolchain, and whose bytes are compared outright.
    * **A docstring counted by hand what an enumeration in the same file states.** That module's docstring stated the same window as a directory and counted its restating sites by hand: seven described where `_FLOOR_SITES` holds nine, the two it misses being a comment in a checker settings file and the workflow's interpreter line.
    * **Three wall clocks for the wave stood where the tool's own page refuses to quote one.** They sat in the wave's own docstring, taken over a population that has since grown by half, and F-128n is standing on the ground that this host does not reproduce a wave figure within a factor of two.
    * **A decline's present-tense ground outlived the act that took it.** The wave's docstring said nothing runs the gates but a person, by hand, before anything lands; the push workflow runs the wave and the tools' tests at every push and pull request to `main`, and the working rules and the tools' page were both carried at that landing while this docstring was not.

  * Landed: Tier A. The mechanical conditions do not reach it. The first fails on the tree, the checker standing red on 20 sums a lane may not repair and no mutant verdict being claimable over a red baseline. The fourth wants a rule holding whatever fact the landing created, and every fact this one created is the truth of a sentence: rules do read several of the artifacts this item edited, [the rule registry](../../tools/check-rules.md) at the rule ids K-00 pairs against the checks modules, [the tools' page](../../tools/README.md) at the claim figures and the pin and floor sites its own rules enumerate, and this document and the findings register at citations and sums, which is where the 20 findings above come from; none of those readings decides whether a sentence is true. A full read is what the item is owed.

Related findings: F-198d.

### S22 · Re-read the model tree and the corpus against the documents over them

Repaired corpus accounting, register conventions, test headers, encoder coverage and reviewer CI descriptions. Model build, tests and corpus passed with unchanged trace digests; the generated bundle was refreshed. Typechecks and non-arithmetic rules passed; derived arithmetic remained red, so no complete mutation verdict is claimed.

Calibration: no original estimate was recorded; excluded from the fit.

  * Seven findings.
    * **A document addressed to an independent reviewer said there is no continuous integration here, and the push workflow landed fourteen hours later.** The onramp is non-normative but present tense, and its §6 is live prose, so the exemption that freezes a completed item's exit line does not reach it.
    * **A unit-test header called its properties the only programs exercising the capability instruction surface until a corpus that landed six and a half hours later.** `test_cheri_insts.sail` was edited three further times over the two days after that landing and the sentence was re-read at none of them.
    * **A second unit-test header called its properties the whole of the machine's own regression corpus, and the commit that falsified it last edited the file.** M0.12 created eleven purecap programs while editing `test_capability.sail` and left the sentence standing, the shortest distance between an act and the claim it falsifies that this sweep found.
    * **One program's trap accounting is stated in two tracked files and both are wrong, in opposite directions, from one authoring commit.** The source header undercounts the trap path at seven where the program takes it eight times; the corpus document's row breaks a correct total of eight into five capability violations where there are six.
    * **A method finding, and the reason the pair above went unreported: a rule that recomputes a quantity from a source does not read the prose restating that quantity beside it.** K-51 reports ok over `cap-trap`'s check count while the source's own header and the document's own row each state a different number.
    * **A corpus program's header states the register convention at a different register from the document that owns it.** `c10` upward against `c8` upward, refuted for every one of the 26 members.
    * **A landing repaired one of two sites in one document that state the same fact.** M1.4′ rewrote §3 to say the encoder table is generated and carries the vector arithmetic, and §7's absence table still gave *encoded by neither the assembler nor a member* as its ground.

  * Landed: Tier A. Nothing holds what this landing created: every edit is a sentence, and no rule in [the registry](../../tools/check-rules.md) decides whether a sentence is true. The one rule that moved is **K-88**, and it holds the generated bundle against the model tree, not anything this item wrote. A full read is what six repaired claims across six files are owed.

Related findings: F-198a, F-181.

### S23 · Repair the stale claims the recent landings left in the proofs, the plan and the crown jewels

Corrected hash-separation descriptions, completed roster and AES-GCM crown-jewel status. Host checks, mutation selftests, tools tests, typechecks and proof audit passed without added assumptions. Crown-jewel discharge status and stale CI dispositions were reported separately; the allegedly missing probing-model plan owner was verified false.

  * Six findings, three repaired and three reported.
    * **One hash-separation field described three ways as a thing the tree does not carry.** Keccak.v finding c, the M3.4a bullet and F-205g each named a total-separation `extend_separates` no hash function realizes, where the field is the finite `extend_separates_on_the_chain` discharged by conversion.
    * **A completed item missing from its own completed roster.** S22 is absent from the summary's `Completed:` line, which no rule reads.
    * **A crown-jewel row naming one functional reference where two exist.** Row 14's clause was true when written and falsified by AesGcm.v landing the day after.
    * **A statement artifact exists for a crown-jewel row that reads not authored, and the treatment is inconsistent with two sibling rows.** DischargeSequence.v states row 26's ordering as rows 14 and 17's artifacts state theirs, but row 26's conferred vehicle is a devicetree rider and its flip cascades to the crown-jewels totals and the coverage standings.
    * **Two clusters of continuous-integration framing in the findings register are stale.** The no-CI grounds of F-198a, F-181 and F-198b and the README wave-figure characterization of F-128n and F-235i were falsified by host-gates.yml and the F-229h repair; reported and not closed, each being self-corrected, kept deliberately by F-236a, or another item's disposition to restate.
    * **A sweep finding this item verified false.** The gap list at the off-clock paragraph does not undercount: row 23 is authored by the Post-M10 probing cell and so sits outside the no-item-authors gap, unlike row 24, which the Post-M10 reduction cell only stands over as an uncosted premise.

  * Landed: Tier A. It edits [crown-jewels.md](../assurance/crown-jewels.md), so it re-enters the R-05-150 review, and nothing holds what it created: every fix is a sentence, and no rule in [the registry](../../tools/check-rules.md) decides whether a sentence is true, the ground of the item and of its three predecessors. The one rule that moves is the proof gate over [Keccak.v](../../proofs/Keccak.v), whose comment this repairs, and it holds compilation and the assumption set, not the comment's truth.

### S24 · Repair the stale claims the deep proof-file audit found

Deep-read remaining large proof files and repaired stale comments without changing terms. Host checks, mutation selftests, tools tests, typechecks and proof audit passed; edited-file constants and empty assumptions were unchanged.

  * Five findings, all repaired, all in proof-file comments no rule reads.
    * **A cross-file claim naming a sibling that carries the opposite structure.** HandlerGraph.v said neither AdmissionPath.v nor SupervisionTree.v carries an edge, a template, a pool or a format; SupervisionTree.v carries capability-grant edges and `PoolLow`/`PoolExhausted` pool signals.
    * **A discharge attributed to an unrelated item.** EndpointIPC.v attributed R-07-028's discharge to M6.0b, the IDL profile, which has nothing to do with the initial capability distribution; R-07-028 is stated by M3.3 and its discharge against an installed graph is deferred, which [field-bindings.md](../assurance/field-bindings.md) records as owed to no item yet.
    * **A phrasing attributed to the wrong paragraph.** MemoryPlan.v credited M1.2's axis-6 paragraph with "a plan that lands two items later", which is M1.9's own entry; M1.2's axis-6 now records M1.9 ahead of it.
    * **A record-type count one short, wrong at authoring.** CopyRingService.v's no-shadow inventory said four record types where RingContract.v exports five (`labels` beside `buffer_ref`, `descriptor`, `completion` and `op_record`, present when the header was written).
    * **A symbol named without its prefix, wrong at authoring.** CopyRingService.v's header named `shared_cell` where the symbol is `is_shared_cell`.

  * Landed: Tier A. Every fix is a sentence in a proof-file comment and no rule decides whether a sentence is true, so it cannot be Tier B and a full read is owed, as for its four predecessors. The one rule that moves is the proof gate over the four edited files, which holds their compilation and assumption sets, not their comments' truth.

### S25 · Repair the stale claims the final proof-file audit found, and carry S1's answers back to the M4.2 cluster

Repaired proof comments and carried S1's kernel answers into the M4.2 cluster. Host checks, mutation selftests, tools tests, typechecks and proof audit passed with unchanged constants/assumptions. The complete proof-tree audit remained open: MModeFirmware had no body audit and RotFirmware only a targeted read.

  * Eight findings, six repaired, one verified false on severity, and one about this item's own first pass.
    * **A register-gap cluster whose index S1 updated and whose prose it did not.** PartitionContext.v's gap-list and the M4.2a plan cell reported seven gaps, a budget reading and two further findings as owed, all closed by S1's R-07-029a, R-07-031b, R-07-027a, R-07-037c, R-07-037d, R-15-220a, R-11-023's amended Accept and a struck registry row, and S1 carried the closures to the findings-register index, where F-157 through F-164 read closed, but not to the note's content.
    * **A resolved narrowness still reported unresolved.** CyclicExecutive.v said R-11-023's criterion is narrower than the check and not resolved; R-11-023's amended Accept now enumerates the four quantities and makes *never occupants* load-bearing.
    * **An AEAD named absent that a later item authored.** Keccak.v's item d named the AEAD as residue at M3.4c and absent; it moved to M3.4d and AesGcm.v authors AES-GCM.
    * **A provenance overreach.** Keccak.v's 12-round known-answer provenance claimed a standard-library SHA-3 cross-check; the Sail harness header scopes that cross-check to its eleven digests and this is a permutation state, not a digest.
    * **A step-mapping count one over.** AesGcm.v's reading 5 said "five step mappings" and named four, AES having four round steps.
    * **A literal count one over, at three sites.** SupervisionTree.v said "five literals" and listed four, in the header, at the count block and at the `each_unit_once` comment; the first pass had repaired two.
    * **A false positive on severity, verified and disambiguated.** The audit flagged SupervisionTree.v:47, "S12 records that the purecap Bedrock2 backend does not exist", as blocks-a-fresh-read, reading "S12" as the file's own obligation-numbering S12 (R-12-073).
    * **This item's own first pass introduced four false claims of the class it repairs, and an adversarial read caught all four before the commit.** It misnumbered AesGcm.v's reading 5 as reading 6 and propagated that into the findings register; it said the proof file and the plan cell report the same set where they report an overlapping one; it scoped the cluster at F-157 through F-162 where it runs to F-164; and its net-change roster named five proof files and one plan cell while the diff carried the findings register too.

  * Landed: Tier A. Every fix is a sentence in a proof-file comment or a plan cell and no rule decides whether a sentence is true, so it cannot be Tier B and a full read is owed, as for its four predecessors. The rules that move are the proof gate over the five edited files, which holds their compilation and assumption sets, not their comments' truth, and the checker's arithmetic over the plan.

### S26 · Close the critique's work list where the documents already answer it

Closed critique actions already answered by register/spec decisions, recording co-read agreement. The oracle/tool baseline takes periodic human review at re-pin. Integrated checks passed. Critique items 10 and 37 stayed open for qualified composition/schedule evidence and backend-generated measurement; no physical qualification was conferred.

  * Five findings.
    * **The work-list paragraph's class count is hand-maintained and no rule reads it.** A search of `tools/vos` for "open items are" and "work list" returns no check, so a miscount after a deletion passes every gate; recounted by hand to the two B items, and reported and not held, K-109 reserved and unused.
    * **The critique's first movement restated a composition the corpus did not own.** Line 80 of [the critique's](../background/critique.md) first movement carried the reduced-software-tier sentence against the critique's own rule that a disposition another document owns is cited and never restated; R-01-002a now books it and the line cites the entry.
    * **The first pass wrote four claims the corpus does not say, and an adversarial re-read caught all four before the wave.** R-15-172's tax as pools sitting mostly empty where the entry says pooling is forfeited; R-15-173a's prose placed below the r-15-247 span where its anchor sits above it, 2347 against 2354; CJ-VELUS and CJ-HAL as two rows where the inventory carries them as two targets over six rows; and R-06-015a's budget as a budget on the install where the entry declares it per proof over the closure.
    * **The periodic reading item 35 takes has a schedule and no dated baseline.** No artifact records which emulators, independent implementations and re-checking provers are eligible at the current pin, so the first reading at a re-pin act is a survey, not a diff; an S-item of S17's shape is the act if a baseline is wanted ahead of the next re-pin, and none is scheduled.
    * **The contained class's one accepting consumer is the biometric matcher, and its residue is authority and not quality.** The refutation grep over the register's biometric, fingerprint, face and trusted-path sites, 22 lines at 4984708, found R-12-016's matcher, which it places in the class, as the one contained consumer that turns a sample into what the machine accepts, the consent front-ends being taken by the trusted-path agent under R-15-144 and so outside the class; R-12-004 carves the matcher out as a bound on authority under R-12-019 and R-17-054, not as a quality figure or a proof.

  * Landed: Tier A. Every edit is a register or spec sentence and every one moves a co-read pair, so no rule holds what the landing created and a full read is owed.

### S27 · Carry the single-planar-tier budget to every site that restates it

Aligned capacity restatements with R-15-173a's single-planar-tier budget of order 0.5–1 GB. Changed pairs were read/blessed and anchored replacements/source searches verified the sites. Capacity still depends on qualified macro density, metadata and logic area; findings retain process and derivation gaps.

  * Two findings.
    * **The band does not name the process it is stated under, and the branch it is applied to may not be that process.** R-15-108a puts the ungraded branch's array on the same planar tier as the cores, R-15-161 declines gate-all-around and CFET on that bottom tier and R-17-063b keeps it on a frontside-powered fully-depleted SOI node an infra-red probe resolves, while R-15-170's band is stated for high-density SRAM at leading nodes.
    * **Two derivations of the same quantity disagree by a third and nothing holds them together.** The inspirations tree derives about 2.6 MB/mm² usable per full-reticle tier, which is 54.7% of its own raw macro figure, where R-15-170's band read with R-15-181a's metadata above the payload gives 27.7 to 46.2 Mb/mm² of payload.

  * Landed: Tier A. It edits the register, so it re-enters the R-05-150 review, and nothing holds what it created: what it repaired is the truth of sentences, which every rule in [the registry](../../tools/check-rules.md) is explicitly not about.

### S28 · State that no device region is executable, and hold it at the map

Specified non-executable device regions and added K-101 to check declared values across compositions/template. The implication is one-way: non-executable scratchpad is not device memory. Host checks, mutation selftests, typechecks and co-reads passed. K-88 supplies generated-map equality; K-101 does not independently derive RTL.

  * Two findings.
    * **A landed note and an open finding both named the next rule id as unspent, and only one of them could be repaired.** The completion-log note that named it is gate-time evidence and stays as written; the findings-register disposition beside it is open, so its sentence is carried to the act instead of asserting an id this landing spends.
    * **The rule reaches the declaration and never the map the RTL reads.** The SoC map package carries the same per-region bits and is generated from the primary composition, not authored beside it, which is K-88's subject, so K-101 holds the source and inherits the generation; a package hand-edited away from its source is that rule's finding, not this one's.

  * Landed: Tier A. It adds a register entry and edits the profile, so it re-enters the R-05-150 review and owes the full read, and the co-read pair it created is blessed on a reading of both sides, not on the arithmetic passing.

### S29 · Discharge a decline against every function the structure performed, not the one it is filed under

Extended the decline criterion to every function a removed structure performed, carrying fetch-permission and initialization-tag dispositions into owner entries. Roster review, host checks, mutation selftests, typechecks and co-reads passed. Function-enumeration completeness remains a judgment.

  * Two findings.
    * **The clause says its rosters are read off the citations, and they are not readable off the artifact the gate audits.** R-15-013's criterion states that every declined hedge cites *verify rather than hedge* at the point of decline and every admitted one at the point of admission, so that neither roster need be kept.
    * **The obligation R-15-013a states is not bounded from outside, and nothing decides when an enumeration is complete.** A reviewer can always name one more function a structure performed in its origin architecture, so the criterion decides that a named function carries a disposition and never that the naming has finished.

  * Landed: Tier A. It adds a register entry, edits two more and the absence contract, and creates a new normative claim, so it owes the full read.

### S30 · Hold the summary's completed roster against the items it names

Added K-102 to check completed-roster membership against checklist items while preserving authored grouping. Host checks, mutation selftests, repair idempotence, tools tests and typechecks passed. It decides membership, not grouping.

  * Two findings.
    * **The defect this rule holds had already happened twice before the rule existed, and the repair preceded it.** Two landings in a row added themselves to the lists that are recomputed and not to the roster sentence that is not, moving the recomputed figures on the same lines and leaving the roster stating a set it no longer described, and every gate stayed green over both, so the arithmetic beside the sentence was correct while the sentence was not.
    * **The first mutant fired a second rule and had to be narrowed, a property of the sites and not of the seed.** The run of ids it dropped occurs twice in the plan, once in the roster and once in a list K-102's neighbour rewrites from the cells, so the seeded defect was read by both and decided neither.

  * Landed: Tier B under **K-102**, which holds the fact this landing created, with **K-00** holding the registry against the checks and the selftest's own coverage check holding the case against the row. No register, profile, crown-jewel, absence-contract or coverage-matrix edit is made, no co-read pair moves, and the checker is green with every mutant killed.

### S31 · Supply independent specification and tooling prerequisites

Accepted schedule, register-accessor, wire-format and calibration prerequisites under [the landed map](../assurance/unassigned-proof-map.md). At `9100fd96`, native proof audit passed compilation, symbol/assumption enumeration and kernel recheck; RTL lint and focused host checks passed. Final Windows/Ubuntu Host CI belongs to the published revision. No target execution, physical qualification, ownership theorem, Narcissus derivation or mode transition was accepted. Incomplete per-item author/review/integration intervals leave every child at retained estimate, actual n/a.

Landed: Tier A. This is the integrator's full read of the four artifacts, the crown-jewel status edits and their generated coverage effects. **K-88** holds generated views and source validation; **K-109** holds the authored schedule's requirement fingerprint. Neither proves the semantic coverage judgments.

The integrated proof audit at implementation revision `9100fd96` passed compilation, complete symbol and assumption enumeration and kernel recheck. Later edits touch documentation, generated review wording and a host selftest seed, not proof-gate inputs. The native receipt is `/root/build/proof-gate/proofs/proof-evidence.json`; its portable snapshot is retained locally at [`out/evidence/prereq-proof-evidence.json`](retained-evidence/out/evidence/prereq-proof-evidence.json). The pre-existing local modification of the tracked portable receipt is preserved byte for byte. Integrated Verilator lint passed on the complete standalone RTL set. Focused host evidence covers the prerequisite validators, checker behavior, K-26 and K-88 mutation checks and idempotent repair. The required final Windows and Ubuntu Host CI verdict is attached to the published landing revision, not inferred from these focused runs.

#### S31a · Extend the shared schedule record

[ScheduleRecord.v](../../proofs/ScheduleRecord.v) adds R-11-017 outputs, symbolic per-mode admission and target re-entry reservation while preserving frames. Executable checks and accepted/refused instances exercise the record. Integrated native audit accepted 131 file constants without added assumptions. Symbolic inputs establish no qualified timing. Original estimate: 12 h, range 8–16; actual n/a because complete per-item intervals were not captured.

Landed: Tier A, including the complete record/requirement read and the explicit distinction between symbolic inputs and qualified timing evidence.

#### S31b · Generate device-register field accessors

[The register contract](contracts/device-registers.md) generates pure Gallina projections/RTL constants from reviewed bindings. Native audit accepted 221 file constants without added assumptions; RTL lint and stale/source/layout refusal tests passed. A non-convertible Gallina edit was refused at compilation, not counted as a killed executable mutant. Projections perform no MMIO and prove no ownership/device refinement. Original estimate: 14 h, range 9–19; actual n/a because intervals were incomplete.

Landed: Tier A, including the full modeled-field inventory read. **K-88** holds generated equality and source validation; semantic Sail correspondence remains a reviewed judgment.

Exit evidence: the integrated native gate enumerates 221 constants in `DeviceRegisters.v` and accepts the accessor equalities with no added assumptions; integrated RTL lint accepts the generated package. Behavioral checks reject stale generated constants, source/layout changes, omitted fields, new apertures and malformed bindings. The K-88 artifact-shift mutants are detected. A separate changed Gallina shift is refused at compilation as not convertible; that refusal is not counted as a killed executable mutant. The lane log is [`/root/logs/lane-prereq-registers-20260921-device-registers.log`](retained-evidence/root/logs/lane-prereq-registers-20260921-device-registers.log).

#### S31c · Inventory attacker-facing wire formats

[The wire-format inventory](../assurance/wire-format-inventory.md) records families, descriptor status, ownership and canonicity, separating reference codecs from unavailable Narcissus descriptors. Focused tests/K-88 reject malformed families, owners/symbols, stale views and descriptor promotion. A family row admits no parser. Original estimate: 8 h, range 5–11; actual n/a because the author interval omits full review/integration.

Landed: Tier A, including the inventory's correspondence to the crown-jewel member classes and the limitation that no parser is admitted by a family row. **K-88** holds the generated view and its source checks.

#### S31d · State calibration field classes and the digest binding

[The calibration schema](../hardware/calibration-manifest.md) defines unpopulated classes and reserved canonical-digest binding. Focused tests/K-88 detect invalid classes/bindings and stale views; independent review passed. R5 owns concrete fields/qualified bounds; authentication, encoding and measured-boot population remain open. Original estimate: 8 h, range 5–11; actual n/a because authoring/shared integration lacked complete intervals.

Landed: Tier A, including the requirement/field-class read and independent review. **K-88** holds the generated schema view and validator; schema validation establishes no physical containment or authenticity.

## Q · Assessment actions

### Q1 · Establish the baseline and its rejection gates

Separated headline claims/comparators and authored [the product-gate contract](contracts/product-gate.md) independently of admission. Host checks, mutation selftests, tools tests and typechecks passed at `f2dbdf4c6fa36c8a92168595f948fcb42e4007c3`. Envelope values remain proposed; this supplies neither ratified bounds nor R-18-004d's demonstration set. Cross-focus input-to-response has no register-owned bound.

  * Six findings.
    * **The headline blended five classes that share no comparator and restated a band no rule reads there.** The old three bullets stated the general-scalar band's ends at three sites and an approximate midpoint, none of them a site K-32's pattern reaches, it reading only the archetype table's row, and blended the classes into one *parity-or-better* sentence that pulled symmetric crypto and AI inference to parity-or-better where the vector-crypto row excludes secret operands and the second-class row calls token generation bandwidth-bound.
    * **The porting guide carried a second headline.** Line 107's *parity-to-many-×* restated the old synthesis outside the estimates, so a repair to one left the tree with two headlines.
    * **The README's five repairs stand, and one expected line number measured one off.** Seven sites at f2dbdf4 under the six site predicates, lines 7, 27, 69, 95, 112, 155 and 174, against an expected 7, 27, 69, 95, 112, 154 and 174: the overflow row sits at 155, the table's header rule at 154.
    * **A result is four clocks and never one.** Host elapsed time, target model cycles, FPGA observations and silicon measurements are the record's four column families, never summed, averaged or converted.
    * **Five envelope values are proposed and owed a ratification.** Sustained device power, enclosure temperature, update turnaround and the two inference-quality thresholds (the KL-divergence ceiling and the top-1 floor) are the physical envelope R-18-004a's fifth Accept says reaches no pre-silicon gate and Q10 reserves to the product's owner; each carries a ground and what would change it, and none binds until ratified.
    * **No register entry states an input-to-response bound across a change of focus.** R-11-023 names the change of focus, a rebinding the compositor requests and the kernel enacts at a major-frame boundary by permuting the slot→tenant map; R-07-031b's Accept lists it among the transitions enacted at that boundary, R-11-006 fits the slots to the major frame, and R-17-007 adds only that the permutation timestamps the change to the unfocused.

  * Landed: Tier A. No rule in [the registry](../../tools/check-rules.md) reads the new contract, the limits it states are a new claim class held by nothing mechanical, and a headline split is a judgment about which row owns which figure, so the mechanical conditions Tier B is admitted on are not met and saying so is cheaper than a rule that would hold a table of proposed values.

#### Q2a · Demonstrate the lowering route host-only on a wire parser

Demonstrated one host-only descriptor check's assumption-free Gallina-to-Bedrock2 derivation and reproducible C emission. C printer, plain-RISC-V compiler and machine connection are separate unchecked/unavailable boundaries; the verified backend emits RV32, not purecap. Owner-constant edits replayed cheaply while specification tightening required proof repair. Host checks, mutation selftests, tools tests and typechecks passed at `d12bc11`; target execution/storage/cycles and manual-route proof comparison were not taken. [The regeneration record](../../tools/bedrock2-lowering/DIGESTS.md) owns output identities and boundary audit.

  * Ten findings.
    * **The route's checked relation covers the first of four boundaries and the other three are not near.** Only Gallina to bedrock2 is checked, at `Qed` under no axioms; the printer carries no theorem, the compiler's theorem is about a target the register forbids, and nothing relates any of it to the Sail model (second bullet).
    * **The maintenance cost of relational compilation is asymmetric, and the expensive direction is the specification.** A constant moved in the owner costs zero component lines and one regeneration; a precondition moved in the component costs the derivation, which stops at seventeen sites and emits nothing.
    * **The reaching exit's gap on this program is its whole stubbed-arm set, every arm one the program needs.** The lowering item took the same measurement; this second, larger program shows 16 arms against its 19, so the census sizes the gap and is not a property of one program.
    * **The verified backend's operation compiler takes no instruction-set argument, so an instance declared for the base integer set emits multiply instructions from the M extension.** `compile_op_register` maps `mul`, `mulhuu`, `divu` and `remu` to their own instructions unconditionally, and this component's array index scalings come out as that many such instructions under an `RV32I` instance.
    * **The generated C is 5.9 times a hand-written C of the same check by bytes and 2.4 times by instruction, and the proof side of that comparison is not taken.** The route re-materializes each bound boolean and gives every refusing path its own status assignment; the printer's preamble is a seventh of the difference.
    * **The generated owner fixes every width and count and fixes no field order, so a consumer's offset arithmetic restates the profile's prose and nothing holds it there.** The component computes each offset itself in the order section 4.2 states; the owner carries that order only as the summation order of two definitions.
    * **The item names a wire parser as the component and the tree carries none to lower.** The wire-format inventory row reads `not authored`, no item on the plan authors one, and no decoder over bytes exists under the proofs tree, so the demonstration authors its own component under the tools tree, and the inventory row is unmoved by this landing.
    * **Two register entries assume a single lowering path carrying both proof transport and an admissible target, met again on a second program.** One requires the synthesis be counted as transport rather than an anchor and the other admits a verified compilation step with no clause about where the transport stops, and this loop is again the exit with the C and without the theorem.
    * **The intermediate language the register, the specification and the plan all name for this route is emitted by neither exit, met again on a second program.** The reaching exit emits C source text and the verified exit encoded machine words, and neither emits the named intermediate.
    * **The proof gate's switch no longer carries its prover and nothing else, and two tracked sites still say it does.** An inventory of that switch today lists four Rocq libraries beside the prover, installed by other work, where the page recording the lowering stack's terms states the emptiness as a deliberate property.

  * Landed: Tier A.

#### Q2c · Scope and assign the CHERI primitive and representation foundation

[The foundation map](../hardware/cheri-foundation-map.md) rejects commissioning missing common CHERI logic/representation at available scope/price. Independent/integrated review preserves R-13-016's translation-agreement duty and concrete laws required by a pilot. Integrated document checks, mutations and typechecks supply no primitive implementation or target proof. Closing review differs from original estimate scope and is excluded from calibration.

Landed: Tier A. Independent and integrator reads accept the reasoned rejection,
its required-route correction and preserved implementation obligations. The
checker cannot decide theorem adequacy or affordability.

### Q3a · Connect the capability-helper property suite to the narrowed model

Transcribed the capability properties for the narrowed model because the pin cannot load unchanged. The suite has 17 carried, 2 restated and 14 new properties; five absent upstream subjects are named. All 33 solver verdicts proved, with non-vacuity/boundary probes separate. Host/model checks passed at `7ee702c`. Solver cost makes mutation unaffordable here; transcription/probe limits and the still-owed edge case remain findings.

  * Eight findings.
    * **The pinned suite loads at neither the compiler nor the record, so what connects it is a transcription, not a run of the pin.** `EXTZ` is a type error under Sail 0.20.2 and the property bodies read four fields the narrowing spent, so the pin's `smt` target cannot be pointed at this model and its `check_properties` target needs an Isla that is not installed.
    * **Five upstream properties have no subject at these widths and their contract is restated nowhere.** `getRepresentableLength` and `getRepresentableAlignmentMask` left with `cram` and `crrl` at M0.6f and the obligation they carried moved to the static memory plan, where no property and no register entry states it as a checkable claim.
    * **R-15-007a's owed edge case is exercised and stays owed.** The entry says the format's property harness owes the containment domain as a case; `propSetBoundsContains` states it, `propSetBoundsWellFormed` states well-formedness inside it, both are proved, and the probe dropping the domain is satisfiable.
    * **`encodableCap` is neither identically true nor identically false, and one of the two domains is probe-pinned while the other is read.** Both guarding premises were put to the solver as the properties that drop them rather than assumed: the property asserting every `Capability` round-trips is satisfiable, so the predicate is not identically true; the three concrete reset capabilities are proved encodable, so it is not identically false; and the containment property with its domain inverted is satisfiable, so the 2^36 bound in `propSetBoundsContains` restricts something.
    * **A property naming two `perms_narrow` calls does not emit at this shape.** `perms_narrow` is a thirty-two-way search the SMT backend unrolls: one call is about 390,000 bytes of SMT-LIB and a fifth of a second of solving, while a property naming three and a probe naming two each ran past 900 s of emission with no file written and were stopped.
    * **A seed oracle over these properties is not affordable at their measured cost.** A mutant changes the model, so no emission is reused and each pays the whole 751.1 s emission before any solving, so a sample of ten is over two hours in one lane before the oracle itself is written.
    * **A populated gitlink stamps the emulator's revision `-dirty` from the guest while the host reads the tree clean.** cmake's `git describe --tags --always --dirty --broken` runs under `GIT_DIR` and `GIT_WORK_TREE` and consults the submodule, which reports modified in WSL over a Windows checkout, so `run.py model reference` printed `0affe37-dirty` with the pin populated and `0affe37` with it de-populated, at one commit and one worktree.
    * **A derived count carried into a note was never any tree's answer, and the half a reader spot-checks agreed.** The lane's report quoted K-63 as resolving 1,689 citations across 98 files.

  * Landed: Tier A. The landing edits a licence position (a vendored row, a retained notice, a pin's Use cell), which is the full read whatever else it carries; it also makes a new claim about the format's properties that no rule holds, K-88 holding the bundle and K-80 and K-81 the licence paths and the pin id but nothing holding the census or the verdicts.

#### Q4a · Measure host-side inference demand and state the target traffic budget

[The inference-demand report](../performance/inference-demand.md) records host measurements, tensor/cache demand, quality comparison and target traffic budgets at `87ce1e3`. Publisher digest checks/generated records establish inputs. Host observations neither measure target speed nor establish its bottleneck. Complete demand exceeds the minimum island grant; cache placement stays conditional and Q1 owns quality acceptance. Measurement variability limits ordering; host repacked weights differ from target storage.

  * Twelve findings.
    * **The floor's inference member and the floor's bandwidth line are jointly satisfiable only at a grant well above the stated minimum, and the aggregate is where the room has to come from.** At R-18-004a(vii)'s own rate and context, a three-billion-parameter model at a real four-bit density demands 9.29 GB/s of weight stream before any cache is read and whichever class the cache is on, above R-18-004b's 8 GB/s M-class grant floor, and 12.50 GB/s with the cheaper cache, 62% of the 20 GB/s aggregate that entry also requires to carry scanout, the compositor, the decode pool and the camera ring concurrently with it.
    * **The floor says *four-bit* and no artifact says what four-bit costs in bytes.** Every published four-bit format of a model this size costs more than four bits per parameter once block scales and the wider embedding and down-projection tensors are counted: 4.955 on the file measured, which the loader's own `4.95 BPW` agrees with.
    * **A pin taken from a release page is not a pin, and a correction that stops at the prose is not a correction.** The commit this lane and its brief recorded as a release carries the build tag `b10816` and nothing else, and sits seven commits after the `v0.4.0` tag, and its binaries report `0.4.0-dev`.
    * **A throughput comparison carries only what its own standard deviations resolve.** The eight per-file rows, taken over nearly three hours beside nine lanes and across a power change, put the widest file fastest in all four columns, the reverse of what bytes predict, while one invocation over the five files, twice, resolves the four-bit file above every wider one at 5.7 combined standard deviations and does not separate the three widest from each other at three repetitions under contention.
    * **This backend holds the repacked weights a second time, and the repacked set is identifiable to the byte.** For the four files whose block type it repacks, the second buffer is every tensor less the 784,384 bytes of `f32` normalizations; for the one it does not, the `q6_K` embedding alone (the loader figures and byte counts are in the allocation bullet above).
    * **Two five-bit formats show that bits per parameter alone do not determine quality.** `Q5_0` and `Q5_K_M` differ by 0.131 bits per parameter, and the k-quant divides mean KL divergence by 5.6 and lifts top-1 agreement by 8.3 points, tens of combined standard errors wide, because one carries a single scale over 32 elements and the other a super-block scale and minimum plus a per-sub-block scale and minimum over 256 (figures and block layouts in the bullet of the same title).
    * **The realized narrowing factor is bounded well below the nominal width ratio, because the head and the block scales do not narrow with the block type.** [The estimates](../performance/performance-estimates.md) read narrower weights as "a factor of two to four directly on bandwidth" against a nominal width ratio.
    * **The comparator's base is itself a quantization, and one of the instrument's three columns fails its own self-check.** The only permissively licensed dense GGUF at this size publishes no unquantized weight at its pinned revision, so the widest weight, and with it the base every divergence is measured against, is an eight-bit file.
    * **The two terms `llama-bench` excludes and the plan's item names do not move a token rate on this host.** Sampling stays under a tenth of one percent of every end-to-end total and the tool's own unaccounted term is 10.18 to 14.61 ms (exit evidence).
    * **The second-class capacity comparison has no per-consumer split and its figure is a floor, so a single-consumer measurement cannot be closed at that entry.** The 3.2 GB usable payload is R-18-004b's *at least* 4 GB less an exclusivity fraction of *at most* 20%, summed over R-15-247s's second list for the whole roster, of which the inference server is one member; the floor's own projected model takes 88% of it under the cheaper cache before any other consumer is placed.
    * **A truncated download passes every size-free check and only the publisher's own digest refuses it.** Two of the five weights ended at `curl` exit 56 at 57% and 32% of their length; both loaded far enough to look like files, and the tree listing's SHA-256 caught them before either was measured.
    * **The KV cache's memory class is a placement nobody has taken, and the budget's second-largest term rides on it.** R-18-004a(vii) places the model wholly on the second class and fixes nothing about the cache; R-15-247s's second list names bulk by volume and model weights and names no cache, and its criterion is latency-criticality, which a cache read once per generated token can be argued either side of.

  * Landed: Tier A.

#### Q5a · Export the placement problem and search it over the standing plan

Exported [MemoryPlan](../../proofs/MemoryPlan.v) witnesses and searched a declared finite base-placement set. Python checks mirror Gallina definitions; results admit no image and change no witness. Export/check/search and host validation passed at `2957352`. Owner, bank and separate reservation/timing fields are absent; footprint is independent of bases and improvement is over demo values. Q5b owns the composed-workload comparison.

  * Eight findings.
    * **The plan carries no owner and no bank, so two of the register's own terms cannot be exported.** R-08-012a's third locality term is bank spreading over banks the plan does not model, R-15-228a making the map an input the plan reads only as `island_of`, `island_base` and `island_span`; R-08-045's per-line-item charge is read over `placed` as region indices with no line item named.
    * **The footprint is not a function of bases, so a base search cannot reach R-08-012a's first objective.** The proven simultaneous peak is decided by live ranges and lengths alone; bases move span used, unused reservation with it one for one, and padding.
    * **The improvement found is over witness values and credits nothing.** The demo plan's bases were chosen to exhibit refutations, region 6 at 224 being the odd-base witness's neighbour, so the packings of the exit evidence, 32 bytes tighter in island 0 and 16 in island 1, show only that the machinery reaches an admitted assignment better than the standing one.
    * **The brief's ground for refusing OR-Tools was false the day it was written; the refusal stands on the item's own order.** The scout recorded ortools 9.15.6755 as shipping cp310 to cp313 wheels only; the same PyPI record read 2026-09-05 lists 34 wheels over cp39 through cp314.
    * **The candidate set is chosen by the plan it compares against.** Defining the quantum by the standing plan's own bases, their gcd from the island's base, makes the standing plan a member and the set small enough to walk, and a standing plan at coarser offsets yields a coarser grid; the finer granule grid (356,944,861,377 and 7,321,746,600 points at `2957352`) is counted and printed beside the enumerated one and never walked.
    * **The contract restates two facts the tool owns and no rule holds the restatement.** §2 quotes `PREDICATE` verbatim and §4's table restates `CONSTRAINTS`'s check-to-entry pairs; a change to either in [vos/memplan.py](../../tools/vos/memplan.py) leaves the document stale with no finding.
    * **`docs/background/critique.md:154` becomes a claim to re-read on landing.** The paragraph says nothing in the corpus prices packings; this landing prices a packing on span used, unused reservation and padding over a witness plan.
    * **The comparison on admitted workload is Q5b's and owed behind Q1 and a composed roster.** No admitted-workload comparison is taken and no composed roster exists to compare on: the plan's figures are witness values carrying no composition claim, R-18-004d's demonstration set is unauthored, R-18-004b's per-class resident bytes are summed by a whole-program plan that does not yet exist, and the absolute limits are Q1's to state.

  * Landed: Tier A.

### Q11 · Bound the reach of a run-ahead fetch, or record that it is unbounded

R-15-104a bounds complete run-ahead transfers against current PCC/executable regions before issue, with stale-authority handling and drain/timing duties. Optional suppression raises no early architectural exception. Changed pairs were read/blessed and complete host validation covered the settled documents. No independent depth cap, fence-cost bound or boot implementation was accepted.

Landed: Tier A. This is a register decision; no Sail fetch-buffer execution is
claimed.

Related findings: F-318.

### Q12 · Re-derive the inference floor against a ternary weight format and state its prompt-processing term

[The ternary record](../performance/ternary-static-demand.md) verifies publisher identity/static demand at `cd244c4869a2fbcb6b46c695060ab292e5bc8589`: 2.251451 tensor bits/parameter and 11.699/8.868 GB/s with declared caches, both above the 8 GB/s minimum. These are not target throughput. [The prompt decision](../performance/prompt-processing-term.md) refuses an unsupported threshold; Q1/Q4b own quality/target measurements. Review and malformed-cache tests passed without supply-floor change.

Landed: Tier A. The review checks measurement predicates, publisher identity, floor arithmetic and the refusal against the item's entry contract; a generated-record equality check cannot decide those claims.

### Q13 · Pin the bring-up Wasm interpreter and re-read its ranking against the absent predictors

Pinned the unverified interim to wasmi v2.0.0 with [terms/use](../../THIRD-PARTY.md#the-bring-up-wasm-interpreter) recorded. The porting guide classifies rankings against absent predictors and takes indirect threading's footprint trade. Register decisions preserve Wasm 2.0 and refuse unqualified validation shortcuts. Source/build comparison and adversarial review passed; no runtime was incorporated and no host ranking supplies target rate or verified-engine qualification.

Landed: Tier A. No rule holds what this item created: the verdict table, the pin's survive-curation split and the threading choice are prose no checker reads, and the two register acts are decisions inside existing Accept clauses rather than a new held fact, so Tier B is unavailable here on K-88's own reading. The porting guide's own restatements of upstream feature-set facts are read at the pin and dated there rather than held by a rule.

### Q14 · Reach the third matrix track, and record what already answers in-memory compute

[The comparison](../background/architectural-alternatives.md#x86-acearm-sme-architectural-state-not-imported) records AME/IME/VME constraints and digital/analog in-memory-compute dispositions, correcting gain-cell attribution and M0.8c inventory claims. Focused/integrated document checks passed. No matrix track, instruction surface, pin or physical array was admitted.

Landed: Tier A. The integration read accepts the bounded comparison and citation correction; no matrix surface or pin is admitted.

### Q15 · Weigh the contactless proximity surface and take an arm on each of its four uses

R-17-051b refuses first-release proximity-coupled radio, card emulation and payment/transit/identity roles. Alternatives record costs/portability losses, preserving contact-side smartcard/radio duties. Review, co-reads and document validation support the decision. ISO/IEC 18013-5 was unread and no decision relies on its clauses. No implementation was accepted.

Landed: Tier A. The co-read ledger moved, one checker disposition row was added so that the refusal vocabulary raises its candidate rather than being worded around it, and no named rule holds the fact this item created.

### Q16 · Decide whether the first release carries messaging

R-17-051a refuses SMS/MMS/RCS and bundled Internet messaging while preserving generic bytes and voice/IMS duties. [The alternatives](../background/architectural-alternatives.md#first-release-messaging-refused) record text-only SMS costs and usability losses. Document validation/paired review passed. This is a roster decision without model, proof or device execution.

Landed: Tier A. The register/prose read covers R-12-041, R-12-042, R-17-051a and R-18-004, including a messaging-service counterexample, generic-byte exceptions and the preserved voice obligation. Future messaging requires the register amendment and composed acceptance the new entry states.

### Q17 · Name the display-protocol decline at its target and rule the clipboard's grantable class

Specified the display typed-IDL/delegation boundary and clipboard ordinary-object grant. Paste designates immutable snapshot/authenticated recipient, consumes one-shot authority before delivery and retains trusted panel/input transition. Counterexample review/document validation passed. Implementation, measured latency and usability stay with existing owners.

Landed: Tier A. This closes the document decision, with implementation and usability evidence still owed by the existing component owners.

### Q18 · Bind proof headers to requirement references without copying normative text

Confirmed the existing writer/K-108/K-109 citation/fingerprint contract. Focused tests/selected mutants passed; corruption across authored manifests was repaired with original proof/export bytes restored and second pass a no-op. Citation sets/Gallina statements were unchanged. Closing validation over existing implementation supplies no comparable original-effort actual.

Landed: Tier A. The existing holder rules decide manifest equality and exclusion; the attended read also checks the unchanged authored meaning. Final batch evidence is recorded with Q11.

### Q19 · Qualify existing proof tooling and one reusable component

Closed bounded tooling decisions and canceled the uncommissioned generic trial. Child outcomes distinguish rejected qualification from canceled execution; mandatory compiler/admission/assurance duties retain owners.

Landed: Tier A.

#### Q19a · Qualify source-oriented proof diagnostics and rendered review

Rejected the presentation candidate under [the qualification contract](../assurance/proof-qualification-contract.md#q19a-and-q19b). At `cab1edadaeac56313c803ae511b3b76d2886a543`, replay showed stale successful rendering after an import definition was renamed; a fresh cache correctly failed. Source/configuration controls refused bad inputs and proof sources were unchanged. Positive qualification, human review-effort comparison and Q20b's environment prerequisite were not supplied; adoption must reopen the original predicate.

Original estimate: 14 h, range 8–20; actual n/a because earlier qualification/recovery lacked complete item-specific author/setup/review intervals. Machine replay timings cannot reconstruct effort or establish savings.

Landed: Tier A. The read checks the negative-outcome rule, the reproduced failure and the unmet downstream prerequisite separately; no normative entry or co-read pair changes.

The successful run's receipt is [`/root/build/q19a-closeout-20260916-b/receipt.json`](retained-evidence/root/build/q19a-closeout-20260916-b/receipt.json), exported to [`out/q19a-closeout-20260916/receipt.json`](retained-evidence/out/q19a-closeout-20260916/receipt.json). It records commands, source/configuration and executable hashes, installed candidate package versions, diagnostics, elapsed times, HTML hashes and the unchanged-source check. Its experiment SHA-256 is `7de444800811063b924313adafc41cffeb3efa6ae605d0235a17e22209976610`. The [replay instructions](../assurance/proof-tooling-qualification.md#reproducing-the-rejected-rendering-candidate) require an unused work directory and describe the success-as-reproduced-rejection exit convention.

The integration validation record is [`out/q19a-closeout-20260916/validation.json`](retained-evidence/out/q19a-closeout-20260916/validation.json): base revision above, the replay script and the three changed documents as the uncommitted scope, `python tools/run.py proofs` over unchanged proof inputs, and `python tools/run.py --fix --tests --summary out/q19a-closeout-20260916/host-gate.json` over the settled batch. The receipts carry the verdicts. Target execution is not claimed.

#### Q19b · Qualify selective libraries and replayable automation

[Selective-library trials](../assurance/proof-tooling-qualification.md) retained handwritten helpers after Stdlib, Equations and standalone sauto comparisons. CopyRing statements/empty assumptions were preserved; clients replayed and concrete/transport trials passed without global UIP. Incorporation was declined and the locked environment unchanged. The 2.2 h is a conservative overlapping upper bound over shared intervals, excluded from calibration. Q19a provides no presentation environment.

Landed: Tier A.

#### Q19c · Test one generic bounded component over proved CHERI primitives

Canceled before execution on 2026-09-26: concrete laws/machine connection were unavailable and uncommissioned. Former 21 h, range 12–30 estimate removed without execution credit. Required lowering/correspondence/admission/validation stay with owners. Re-entry needs a current consumer, checked prerequisites, usable environment, finite stop threshold and full reviewed estimate under a new suffixed ID.

Landed: Tier A. This is a scope disposition, not successful execution of the canceled trial.

### Q20 · Test the combined language and production-artifact goal

Retained the reviewed contract and canceled uncommissioned workflow/promotion trials. Mandatory producer duties remain; no experiment is recorded as executed.

Landed: Tier A.

#### Q20a · Author the combined acceptance and benchmark contract

[The workflow contract](../languages/workflow-contract.md) fixes parser client, held-out service, exits/cases, semantic probes, evidence identities and cost thresholds. Independent/integrated review and host document checks passed with proof/model/interfaces unchanged. The contract is authored; trials are unopened and missing copying baselines remain entry conditions.

Landed: Tier A. The independent read covers the intended outputs, every exit, negative-case obligations, semantic invalidation and full-cost comparison; mechanical document checks cannot decide those contracts, and no Tier-B holder is claimed. The absence of copying baselines is an explicit trial-entry condition, per Q20a's permission to prepare its contract before those implementations exist.

##### Q20b · Compare one integrated source and proof workflow on a held-out client

Canceled before execution on 2026-09-26: no qualified presentation environment/generic instance released the trial. Former 14 h, range 8–20 estimate removed without execution credit. Mandatory duties remain; re-entry needs Q19c's conditions and a new suffixed ID.

Landed: Tier A. This is a scope disposition, not successful execution of the canceled trial.

#### Q20c · Join the optimized artifact to its evidence and measure production promotion

Canceled before execution on 2026-09-26: workflow/production-evidence prerequisites were unavailable. Former 18 h, range 10–26 estimate removed without execution credit. Required correspondence/validation remain with producers; re-entry needs Q19c's conditions and a new suffixed ID.

Landed: Tier A. This is a scope disposition, not successful execution of the canceled trial.

### Q21 · Scope the unified language core and compiler-route comparison

Children decline core qualification/paired compiler commissioning, retaining contracts/reopening evidence. Q2c's foundation rejection and Q20a protocol stay the common boundary. Existing compiler duties, parser waypoint and checked-law gate are unchanged; the parent has no estimate/actual.

Landed: Tier A. The integrated read distinguishes a commissioning decision from
an implemented trial or production theorem.

#### Q21a · Specify the core design and its qualification contract

[The core contract](../languages/core-design.md) rejects at unavailable/unpriced returned-view laws and missing frontend admission. Exit, reborrow, cleanup, source and diagnostic-generation obligations remain. Independent/integrated review accepted corrections; closing review is excluded from calibration. No language refutation or implemented metatheory/frontend qualification is established.

Landed: Tier A. The reasoned rejection closes this decision while preserving
its conditional contract and reopening evidence. No metatheory, frontend
implementation or executed qualification case is claimed.

#### Q21b · Price the compiler alternatives and define their artifact trial

[The route contract](../languages/compiler-route-contract.md) rejects commissioning without full-endpoint price for contextual foundation, direct producer and maintenance. Independent/integrated review preserves equivalent endpoints/evidence and mandatory duties. Closing review is excluded from calibration; paired budget is conditional/unbooked. Neither route receives a feasibility, performance or production-theorem verdict.

Landed: Tier A. The read accepts this commissioning rejection and reopening
contract. It establishes no performance comparison, route infeasibility, licence
grant or production theorem.

### Q22a · Qualify revocation completion and reuse

The [qualification](../assurance/revocation-qualification.md) connects the bounded host model to Sail's authority and reclamation paths, distinguishing bitmap publication, semantic completion and physical reuse. Its holder map, loan inventory, single-core islands, proxy topology and service-cost assumptions remain explicit. Missing jobs or acknowledgements refuse completion; timeout retains quarantine and supplies no physical-containment evidence.

At authoring revision `e384832bb3e94b7c087aa9341f43b7506e9b9848`, focused tests pass; the integrated revocation assessment covers generated cleanup orders and refusal cases. M4.4 and R2 own implementation and proof connections. The integrated host gate passes; no guest evidence is claimed. Shared integration effort is charged here once, not at Q22b or Q22c.

* **Finding: an exact context restore is not a revocation barrier.** `PartitionContext.v`
  restores saved values and tags and supplies no revocation sanitation. M4.4 must
  connect a sanitized saved image or the defined filtered-load result to that
  relation; R2 must establish the actual proxy and device completion boundary.

Landed: Tier A. The attended read covers the source/model relation, the admission
and scheduling premises and the bounded result's limits; behavioral tests do not
become a universal temporal-safety theorem.

### Q22b · Qualify the witness policy and its transitions

The [qualification](../assurance/witness-policy-qualification.md) fixes the witness policy's fault, authentication, persistence and recovery assumptions. Continuous replacement needs terminal closure under the old policy and acceptance by the new one; authenticated rebootstrap starts a fresh trust scope. Availability and separately valid selective histories remain distinct.

Focused tests pass at `720ab3dcbaca85c795b3e2b2abe774c377b9d7ff`; the integrated assessment checks policies and quorum/fault assignments against the actual acceptance predicate. Independent review accepts the bounded scope. Ideal authentication and protected antirollback state remain assumptions. M5.5, M6.2c and M5.4 own formalization, validation/refinement and consumption. Q22a owns shared integration evidence and effort.

* **Finding: individually safe witness populations do not establish continuity between
  them.** A shared prefix alone fails the disjoint-policy counterexample: ordinary
  certificates at a shared prefix leave both epochs able to grow conflicting
  histories, so the qualified interface requires the terminal closure or
  authenticated rebootstrap with a replaced trust scope stated above.

Landed: Tier A. The read accepts the bounded model, counterexamples and downstream
assignments. CJ-WITNESS's machine-checked model and theorem remain open at M5.5.

### Q22c · Bind attestation to the application session

The [qualification](../assurance/session-binding-qualification.md) binds completed TLS handshakes to application sessions through an exporter derived from the protected key-owning context. Appraisal includes freshness, origin, role, measured state and unit policy; its connection-owned lifecycle refuses repeated authentication and reconstructed appraisers.

Focused tests pass at `4cda1c21f32c3e02cdc8114bc9bd5dfaeb493f20`; the integrated assessment accepts or refuses the delivery population without an independent observer finding a relation failure. Compromise cases retain their accepted attacks, and a transparent relay to the intended key holder is not endpoint substitution. Ideal cryptography, typed handles and endpoint assumptions remain premises. M6.9a–M6.9c own realization, implementation connection and theorem; M6.3b owns credential handles. Q22a owns shared integration evidence and effort.

* **Finding: a public exporter value is not evidence of local key custody.** A quote issuer
  that accepts a caller-provided exporter can attest a different endpoint's
  connection. Protected local context lookup and its authentication lifetime are
  therefore part of M6.9a/M6.9b's required connection to the model.

Landed: Tier A. This accepts a bounded qualification and its remaining owners;
CJ-ATTEST's formal model, theorem and implementation connection remain open.

### Q22d · Qualify the generated RTL correspondence boundary

The [boundary qualification](../assurance/rtl-correspondence-boundary.md) records source semantics, theorem endpoint, emitter identity/revision, emitted bytes, synthesis input and reached tier for the existing capability package and generated address map. Neither is a proved circuit/emitter chain; the candidate DSLs' circuit theorems stop before their emission layers. The licence-based Kami choice is unchanged.

At `9e2b56ab`, Verilator 5.052 cross-checks the model-generated vectors successfully. Three compiling perturbations are detected; an exported `clear_tag` no-op survives because the harness never selects that entry point. All four lint successfully. This establishes the tested correspondence and its uncovered selection seam; lint alone supplies no correspondence evidence.

Accounting: 0.7 h agent-parallel actual, excluding the preceding survey.

* **Finding: no register entry requires this record.** R-15-092's Accept states the fields
  for an elected version, and no entry makes the record a required artifact the way
  R-15-100a makes the absence contract required. Making it one is a register act, a new
  entry or an amendment to that Accept, and belongs to the register's owner. F-359.

* **Finding: R-18-010's rungs are stated per core and no rung admits a package.** Both
  worked examples are packages, so both rung lists are empty rather than short
  and the tier cells read R-01-002b as the ceiling over the unit, not as a reading taken over a block. Extending the ladder to
  non-core blocks, or ruling that it deliberately does not reach them, is the register's. F-360.

* **Finding: the register states no tier below evidence tier.** The predicate's *lower
  evidence tier* is therefore read on R-01-002b's own two-list test, as a shorter rung list
  and a weaker claim, not as a third tier this work would be inventing. A sub-tier
  is a register act. F-361.

* **Finding: no artifact owes the address map a theorem endpoint.** Its meaning is
  agreement with the model's `pmaCheck` in `model/model/sys/mem.sail` and no artifact
  states that relation. Assigning an owner is the plan's act. F-362.

* **Finding: `run.py rtl crosscheck` has no source override.** It reads the format package
  from the checkout unconditionally, so each trial replicated its Verilator invocation by
  hand. Reported and not repaired: this cell prices boundary qualification and a bounded
  experiment, not a tool mode. F-363.

Landed: Tier A. No checker rule was added and no checker artifact is created, so
nothing here is held by a rule of this landing's own making; the qualification adds no
obligation and the two register acts it names are reported, not taken.

### Q22f · Compare the storage index under one contract

The [comparison](comparisons/storage-index.md), frozen at `38cebaa`, tests buffered Bε and CoW B+ candidates under shared capacity, redo, snapshot, device/RAM and persistence accounting. At `130b58c`, independent map replay, exhaustive small-key streams, crash/recovery cases, focused behavior tests and type checks pass. Q14 records integrated validation and shared effort.

The singleton endurance sweep rejects both arms at four programs, admits only the buffered arm at five and both at six; larger transactions admit both. Bε remains provisional because B+ misses the central singleton envelope. This finite fixture chooses no general production index or recovery policy. Integrity, ownership and reservations are assumptions; target costs, geometry, batching, multilevel behavior and refinement remain M5.3 inputs.

Landed: Tier A. Behavioral checks hold the executable comparison; the finite experiment supplies no general index selection.

### Q22g · Price the unassigned proof and specification work

The [reviewed map](../assurance/unassigned-proof-map.md) assigns U-01–U-28 next slices with endpoints, gaps, prerequisites, ranges and acceptance predicates. Owner acceptance is still required before proposals become implementation cells; no theorem, inventory status or M8a dependency is advanced.

Source `ca05743df9a568cb728caf15312d31703ea0c405` and correction `e694a548e0c31520814eba0d5d1d981fd0571bb5` pass the integrated host validation, bound by the gate log and input hashes. No guest proof or device measurement is claimed. The 0.8 h actual includes recovered authoring, review and integration; shared ABI review is charged here once, not again at M1.2d.

  * Four findings.
    * **Source qualification is not inferred from metadata.** The review corrects claims about uninspected axiom closures and unverified prover compatibility: unchecked compatibility and axiom closure stay open until their named probes, and absent Islaris acquisition is assigned to the logic-route decision. F-349.
    * **A security subset does not complete a protocol row.** Bluetooth pairing leaves the remaining Bluetooth procedures and the wire-format mapping explicitly unpriced, visible beside the priced slices. F-350.
    * **Required implementations remain outside the proposed allowances.** Missing compiler, TAL and masked-datapath implementation obligations stay visible outside the priced proposals and need their separately named plan or register acts. F-351.
    * **A proof-producing slice is marked as such and an alternative route cannot silently override the register.** U-19 carries both statement and proof scope, and a direct replacement for the mandated Katamaran route stays conditional on a register amendment. F-352.

Landed: Tier A. The accepted artifact is the dependency and cost map with proposed scopes; implementation remains with the named owners.

### Q23a · Decide the ensemble instantiation and wire it into the register

The register adopts an ensemble of whole single-die machines with separate memory, address spaces, roots of trust and generations. Links are network boundaries with scheduled authenticated frames, mutually appraised sessions and composition-fixed replay/alignment state. The act reconciles single-die obligations, adds B-10 coverage and A-18–A-21 absences, and records the composed isolation, attestation and non-interference residuals.

The [inspirations](../background/inspirations.md#groqs-tensor-streaming-processor-static-scheduling-carried-across-chips-and-the-shared-address-space-an-ensemble-does-not-take) and [alternatives](../background/architectural-alternatives.md#a-second-die-radio-bifurcation-sram-chiplets-and-bonded-stacking-declined-once-at-the-trust-structure-they-share) own the sourced architectural comparisons. The first release is unchanged; the five admission artifacts and traffic calculation remain separately owned. Authoring `74cec1e` and fixup `6ed2b5b` receive co-reads and integrated host validation. No model, proof or device execution is claimed.

Calibration: no original estimate was recorded; excluded from the fit. Recorded effort uses session wall-clock bounds, including idle gaps and excluding hosted waiting and cleanup; no child receives completion credit.

  * Finding: **R-15-111's acceptance criterion cited R-15-146, the peripheral electronic-enable rule, as the ground for no die-to-die link existing anywhere in the machine.** The owning entry is R-15-162; a citation that resolves and names the wrong owner is the stale-claim shape no citation rule reads, and it is repaired in this act.
  * Finding: **Universal session-tag rules excluded the handshake that establishes the session.** Application traffic remains gated by the session; only bounded verified establishment processing receives scheduled handshake frames, which enable neither application delivery nor an origin leap.
  * Finding: **A valid slot tag does not authenticate the arrival instant within that slot.** Cross-slot replay is refused; delay by an adversarial wire within the accepted slot is booked beside a compromised leader's bounded timing walk.
  * Finding: **The ensemble entries both denied a shared mask set and required copies of one mask set.** Members are distinct physical dies with separate packages, memory and unit identities, each realizing the same mask-set design.

Landed: Tier A. The register/prose read covers every new entry and every amended one, the four absence rows and the seven B-10 cells, including a peer-on-another-unit counterexample at R-12-015d, a routed-fetch-across-a-link counterexample at R-15-171a, the circular-digest case R-13-001d's identity avoids and the unbounded-drift case R-15-196a's leap answers. Independent review at `6ed2b5b` identifies the second to fourth findings' defects; the corrected pairs and coverage cells pass a focused reread before the integrated host gate.

### Q23b · Author the ensemble link contract

[The ensemble link contract](../hardware/ensemble-link-contract.md) specifies frame grammar, endpoint registers and absences, windows, FIFO/line-rate admission, slot tables, fixed-function conditions and server interfaces. It supplies one of the five ensemble admission artifacts.

Frame size, latency, skew and code-family operands remain unqualified and owner-assigned. Narcissus descriptors, correctness/canonicity theorems and the remaining ensemble artifacts are not supplied. The devicetree declaration and register-offset acts are reported, not taken.

At source `cc321b0` and repair `be28779`, focused document checks pass; corpus-membership refusals confirm the new contract is checked. No guest proof or device measurement is claimed. Accounting: 1.0 h agent-parallel actual, excluding preceding survey and unrelated stalls.

  * Four findings.
    * **A general clause is not a declaration.** Ten of §4's rows name the attested devicetree as carrier on R-02-003a's general clause that every constant of an ensemble is carried there, and on that clause alone, no entry naming any of them and R-09-007's list of what the static devicetree declares reaching none of the link's per-link constants, and the register shows the clause is not read as exhaustive, R-15-228d putting the frame size in a different artifact by name. Whether R-09-007 owes an Accept clause for this class, on the precedent R-15-228h earned, is a register act. F-364.
    * **An inventory row's status is not lifted by a stated grammar.** Crown-jewel row 10 gains this descriptor set as a member and stays `not authored`; the descriptor, its Narcissus correctness pair and its canonicity theorem are all owed, and whether one stated grammar promotes the row is K-95's lift and its repairer's. F-365.
    * **A family chosen without its operand would rest on nothing.** The selection predicate admits both of R-15-119's families and no measurement in this tree separates them, the frame length being unfixed and the reach and raw error rate being physical quantities none of the five gating artifacts buys, so the family is recorded as owed. F-366.
    * **The endpoint's register offsets are declared by no entry.** R-15-002b makes an MMIO aperture's placement a stated constraint on the attested devicetree and no entry assigns an offset inside it to a register of §3.2's table, the same class of gap as the constants, recorded beside them and not filled. F-367.

Landed: Tier A. The item creates a contract whose content no rule in the registry holds: the gates decide id, link, section and glyph resolution and the crown-jewel row's membership, not what it says about frames, registers or R-04-010a's conditions, so the fourth Tier-B condition, a named rule holding a fact the landing created, is unmet and a green `check.py` is not a reading of the text. Independent review at `cc321b0` identifies an epoch register deciding against §5.3's own falsifying column, a §4.2 paragraph declaring closed the gap it had reported two clauses earlier, a frame-size carrier naming the wrong artifact, and five sentences claiming more than their evidence establishes; the repair at `be28779` deletes the epoch register in favour of the equalization freeze's own validity, sorts §4's rows by the authority their carrier rests on, moves the frame size to the attested schedule artifact, and rewrites the five sentences to what their entries decide. Q23c through Q23g remain open and no ensemble is composed.

### Q23e · Compute ensemble traffic and frame demand

[The traffic report](../performance/ensemble-sharding-traffic.md), [instrument](../performance/ensemble-sharding-traffic/shard.py) and [data](../performance/ensemble-sharding-traffic/traffic.json) supply a reproducible static calculation. They measure neither crypto throughput nor an admitted token rate. Q23h owns measured crypto costs and composition admission, consuming Q23d, Q23g and M6.8.

The calculation separates byte volume from serial exchange demand and prices both cycle/ring and fully connected collectives; topology changes the cadence/crypto tradeoff. It supplies symbolic traffic operands while frame size, endpoint costs, crypto throughput, bank grants and schedule periods remain missing. No mixture-of-experts population or floor-model dimensions are invented. Focused checks pass, generated output replays byte-identically and malformed inputs refuse. No guest timing enters the arithmetic.

Accounting: the retained 0.9 h is this calculation's actual, excluding preceding survey and unrelated stalls.

  * Four findings.
    * **A report whose subject is undeclared magnitudes will state a bound on one of them if nobody is counting.** The lead sentence asserted that no plausible link is short of 6.45 MB/s, a lower bound on the one constant the same report says it cannot decide and which R-12-015d bounds above by an undeclared throughput. The repair is conditional phrasing and a named owner; the headline lost nothing, the ordering of the terms being the result and the bandwidth claim decoration on it. F-368.
    * **A refusal derived over two declared parameters reads as a property of the shape unless the alternative is priced.** Above two members tensor-wise was refused on cadence; the refusal was the cycle's and the ring's, and a fully connected collective reverses it at 2.5 times the crypto charge. Pricing the alternative was fourteen lines of the instrument and moved a verdict. F-369.
    * **Three figures sat outside the file the report said every figure came from**, an FFN width no tracked artifact states, a head count owned by another report's section, and a cache constant hand-copied from it. All three are now derived in the instrument with predicates, and the derived cache bytes agree with their source section to the byte. The rule the miss breaks is the item's own Check clause. F-370.
    * **An entry that names three terms and no composition function invites the reader to supply one.** R-15-171a's rate was read as the minimum of three independent ceilings; R-11-017a's own text puts all three into one member's R-11-006 interval arithmetic as ordinary tasks and grants, which is one schedulability analysis and not three independent ceilings, so the independence was asserted against the entry the sentence relied on. Stated as an upper bound now, with the composition named as Q23d's. F-371.

Landed: Tier A. No rule in [the rule registry](../../tools/check-rules.md) holds any fact this landing created: the traffic tables, the exchange counts and the restatement of inference-demand's 12.46 GB/s are all unheld, and a rule over a derived traffic table would hold one script's output against the same script's accounting of it, the pattern S14 and I15 both declined. No rule is added: that costs three edits and a mutant for a table no other document wants.

### Q24a · Author the immutable module contract

[The immutable module contract](../hardware/immutable-module-contract.md) specifies the external confidentiality boundary, finite operations, seven-state lifecycle, private-state dispositions and separate arbitrary-card/honest-card claims. The endpoint accepts no host address, capability or DMA request; host destinations come from its outstanding-operation state.

Magnitudes, register layouts, parser/canonicity proofs, electrical steps and envelope values remain owner-assigned. Named cases are acceptance predicates, not executed evidence. Decision-table exhaustiveness is a drafting property; slot-occupancy indistinguishability concerns idle versus loaded established sessions, not module absence.

At authoring `5afea3b` and repairs `7affae9`/`057ec35`, requirement references and co-reads agree; K-24's derived crown-jewel counts await integrator repair. Accounting: 0.7 h agent-parallel actual, excluding preceding survey and unrelated stalls.

* **Finding: the checklist's Owns clause for this item names two glosses as socket states and omits three states.** The cell writes "absent, present, admitted, active, quiescing and isolated"; R-15-228h fixes absent, isolated, detected, reset, authenticated, active and quiescing. *Present* is the condition a card is in from `detected` onward and *admitted* is a property of a unit and design pair, not of the socket; the contract records both as glosses with the state each produces. `detected`, `reset` and `authenticated` are the three the clause drops. F-372.

Landed: Tier A. The read accepts the boundary, the grammar's exhaustiveness at its drafting-property standing, and the claim-scope separation. Every theorem the claim table names stays open at Q24c through Q24f, and the crown-jewel row stays `partial` on its remaining specification parts.

WHY TIER A AND NOT TIER B: the checker is not green at this head (K-24's six counts are outstanding for the integrator), the act edits crown-jewels.md prose, and no rule in the registry holds the fact this landing created, so there is nothing to name in a "Tier B under" line.

### Q23c · Author the ensemble link session reference model

The [session qualification](../assurance/session-binding-qualification.md) adds the ensemble construction: mutual fresh appraisal binds each unit, ensemble identity, fixed hybrid configuration and both slot-table digests. Keys remain in the crypto core; replay counts come from the schedule. Key derivation binds both accepted identities and challenges, with possession represented by holder sets.

The integrated assessment and 13 focused tests pass, with no independent event-oracle relation failure; substituted units, foreign ensembles and repeated decisions refuse. Device-identity construction is still a register premise. M6.9a–M6.9c own protocol, implementation and theorem, U-20 their foundation, and Q23d the concrete schedule. This is finite host evidence with ideal cryptography and symbolic identities, not frame execution, key exchange, computational reduction or proof. Production adoption and CJ-ATTEST remain open.

Accounting: 0.6 h agent-parallel actual, excluding preceding survey.

* **Finding: a session model can state key ownership and decide nothing about it.** The
  model as first authored derived its session key from the link name and the epoch
  alone, both public composition constants, so the appraisal and the key holder were
  unrelated: an honest establishment and one admitting a substituted die produced the
  same core, and a party that appraised nothing sealed frames the session delivered. The
  relay and key-exposure rows rested on a stipulated string, not a decision. The keying
  above, with possession as a holder set as in the TLS part, makes them decide.

* **Finding: an event-level oracle that reads a verifier's own predicate off the claim is
  not independent along that dimension.** Two of the ensemble oracle's seven conjuncts
  compared the appraiser's freshness and configuration checks against the claim, not
  against ghost state, so a defect in either comparison would have left the
  relation silent. The issuance now records the challenge it was handed and the
  configuration it was asked for as ghost fields beside the die that signed.

Landed: Tier A. This accepts a bounded symbolic qualification and its remaining owners;
CJ-ATTEST's formal model, theorem and implementation connection remain open.

### Q23f · State the composed non-interference obligation beside T

[ComposedNonInterference.v](../../proofs/ComposedNonInterference.v) states the ensemble target beside [T](../../proofs/ApexTheorem.v), leaving T's vocabulary and closed seam list unchanged. Machine-checked counterexamples show that per-member T and the named link predicates do not imply composition, and that an unsatisfiable session premise can admit the leaking instance vacuously. The target bounds graph-permitted adversaries and treats both endpoints as one wire boundary.

The statement intentionally supplies no unregistered label relation or semantic transfer from sent frames to delivery. Those are owner decisions, not proof-file assumptions. The file and its repair compile at the pinned prover with empty assumption readings. K-106's generated ledger awaits integration repair. The full proof gate was not rerun at the landing revision; repaired constant counts made its earlier totals stale, so integration owes fresh evidence. The composed theorem and R-17-014a remain open.

Accounting: 0.7 h agent-parallel actual, excluding preceding survey and unrelated stalls.

  * Three findings.
    * **The link's named contribution cannot bear on the conclusion, and no entry lets it.** R-17-014a calls R-15-228d's schedule and R-12-015d's session the link's *contribution*, which asserts they do work; as predicates over a link alone they reach nothing the target concludes (fifth bullet), the wire's semantic content sitting in the `delivered` field the entry does not name. What is missing is the transfer: R-15-228b fixes what a frame is, R-15-228d the slot it occupies, R-12-007a the indices it names and R-12-015d the session that authenticates it, and none of the four relates what a link delivers to a member to what the sending member's execution placed on the wire in that slot. Open, and the act is a register act: an Accept clause at R-17-003d, or an entry beside R-12-007a. A field asserting the relation in the proof file would decide by fiat what the register has not, which is decision 8's own ground met a second time.
    * **No entry decides what relation a link's two endpoint labels must stand in.** R-15-228b, R-15-228d, R-12-007a, R-12-015d and R-17-003d state the frame grammar, the slot table, the index-only payload and the session, and none states a label relation across the wire. `endpoints_share_a_label` gives the question a name and two instances, holding at one and failing at the other, and is left out of the target. Open, owed by row 2's compose-time policy model (R-08-028), which is unauthored (R-15-211).
    * **This item's own cell mis-cited the entry it leans on.** The Execute clause asked for the rejected instance "as R-05-157 asks of every claim"; R-05-157 says only that T is the formal reading of *hyper-secure* and of G2, and the entry asking for "a distinguishing instance its specification rejects" is R-05-166, which asks it of a policy statement and which the same cell's Owns clause already names. No rule holds a cited id against what the sentence attributes to it, so every gate stayed green.

Landed: Tier A. No rule holds what this item created: K-109 binds the file's generated header to its requirement owners, K-103 its citations, K-105 its annotations and K-108 its derived region, and `run.py proofs` compiles it and audits its assumptions, but none of them reads what the target *says*, so Tier B's fourth condition has nothing honest to name. Its first condition is unmet besides, `tools/check.py` being red on K-106's generated ledger until the repair path runs. The note books two open register acts, which is a full read's subject in any case.

### Q25 · Design the full graded dependent language and its control and mutation rules

The [full-language commitments](../languages/verification-strategy.md#full-language-design-commitments), [assurance presets](../languages/assurance-profiles.md) and [composition review](../languages/full-language-review.md) are completed design and qualification planning, covered by Q25a–Q25d. They join graded dependent typing, handlers, structured async/cancellation and guarded mutation.

Frontend commissioning remains blocked by the interpretation commitment and register acts. The bounded-pool amendment, concrete CHERI laws, metatheory, frontend/backend and target qualification remain with their owners. No executed language or production binary is supplied. Children own evidence and actuals; this parent duplicates no estimate or effort, and settled integration supplies host validation.

Landed: Tier A. The combined design and its recorded acceptance boundaries are read together, including the decisions that keep dependent implementation unopened.

#### Q25a · Specify the graded dependent foundation

The [foundation dossier](../languages/graded-foundation.md) specifies grades, dependent contexts and constructors, structural rules and substitution, with explicit inference, specialization, ABI and source-correspondence limits. Its examples separate exact use, erasure and resource authority.

At `6d0ee4e`, focused checks pass; integration reads the dossier against the strategy, synchronous core, sibling interfaces and register. Paper derivations supply no soundness theorem, concrete CHERI instance, executed negative case or qualified binary. The `GF-*` laws remain implementation obligations. Accounting: 0.2 h author/check actual; Q25d owns shared review, integration and host validation.

  * Finding: the call-by-name grading reference supplies no proof that effectful
    arguments execute once under the proposed call-by-value rules. Pure value
    substitution and explicit effectful binding are separated; `GF-cbv` remains
    the composed-law obligation. F-353.

Landed: Tier A. The full read accepts the rule dossier and its explicitly named
missing laws at Q25a's design predicate. It opens no frontend implementation.

#### Q25b · Specify handlers and structured async lifecycles

The [control dossier](../languages/handlers-async.md) specifies handler lookup/capture, resumption/disposal and bounded represented async reactions. Cancellation arrival, decision, commit, terminal publication and reuse are distinct; suffix bounds include child-result collection before cleanup dispatch.

Authoring `9503081` and independent review `1faa273` receive integration corrections to the cancellation bound and checkpoint order. The authored traces remain conditional derivations; `HA-*` laws, target bounds and frontend admission are unimplemented. Accounting: 0.2 h author/check actual; Q25d owns shared review, integration and final host checks. No guest measurement is claimed.

  * Two findings.
    * **Language-frame occupancy needs an explicit inventory disposition.**
      Q25d must classify it under R-08-046 or amend that entry and its prose before
      runtime implementation opens. F-354.
    * **Cancellation delay can precede committed work on one path.** A maximum
      between those terms omits that path; integration composes the decision
      prefix with the complete selected suffix, cancelled or committed, in one
      elapsed-time unit. F-355.

Landed: Tier A. The full and independent reads accept the lifecycle design after
the bound and checkpoint-order corrections, with all target laws still explicit.

#### Q25c · Specify interior mutability and interference guardrails

The [cell dossier](../languages/interior-mutability.md) specifies local/dynamic-borrow interfaces, invariant access, capture/sharing, publication, quiescence and source exits. `CountCell` conserves `AddOnce` allowances through one AMO commit; capability storage remains private. Functional, race, progress and leakage claims retain separate premises and missing `MUT-*` laws.

At `1f2d633`, focused checks pass; independent review and integration correct frame release and initialization/cancellation joins. Concrete CHERI witnesses and source-to-Sail correspondence remain owed; wrappers and grades supply no sharing authority. Accounting: 0.2 h author/check actual; Q25d owns shared review, integration and final host checks. No executed language or guest evidence is claimed.

  * Finding: the registered-but-unstarted cancellation branch must retain its
    frame while returned inputs await collection in the reserved cancelled
    completion record. Integration makes collection and the release gate precede
    frame reuse. F-356.

Landed: Tier A. The full and independent reads accept the interfaces, counter
protocol and qualification cases with their unmechanized obligations preserved.

#### Q25d · Review the combined calculus and price its implementation

The [composition dossier](../languages/full-language-review.md) joins the common client, refusal cases and laws over the named byte-and-capability carrier. It supplies reviewed ownership, conditional prices and acceptance predicates for the design debts, frontend and qualification increments, retaining unpriced foundation work. It constructs no carrier inhabitant or checked metatheory.

Admission is arm-dependent. A calculus interpreted by elaboration into an existing anchor can use R-05-009; the authored source judgments/reductions instead propose an eighth anchor refused by R-05-019/R-05-020. Frontend rows remain uncommissioned until the interpretation commitment and clarifying register act. R-08-046's inventory classification is negative: new runtime storage needs a proposed inventory/prose amendment, ordered after frontend admission. F-354's disposition separates those acts.

Authoring `4f10fab` and repair `2468545` pass focused document checks after independent review corrects the admission reading and owner joins. Accounting: 0.9 h agent-parallel actual, excluding preceding survey and unrelated stalls. Q2c's foundation commissioning and U-22's breakdown remain prerequisites; no executed language or qualified binary is claimed.

Landed: Tier A. The review states new claims about which admission arm the combined calculus takes and what its implementation still owes, so it took a full attended read rather than a spot read of its findings.

### Q26 · Price the resident toolchain against the floor's own comparisons

The [residency report](../performance/toolchain-residency.md) and [artifacts](../performance/toolchain-residency/) measure working set, store bytes and host turnaround against the release floor. The prover's 725,676,032-byte peak is 1.81 times the pessimistic payload floor and 0.91 times its optimistic end; the working-set shortfall exceeds measured repeatability spread. This is one host activation, not a full roster/device build.

The 678,113,124 unique store bytes are an incomplete floor with no declared supply capacity to score; turnaround has no device ceiling and no accepted host/device conversion. The report leaves the four response arms untaken and preserves the composition boundary. Independent reviews and repairs conclude with integrated host checks passing at `190326d4`.

Accounting: 4.6 h agent-parallel actual is a lower bound because the initial authoring state/interval cannot be recovered; later measured passes do not fill that gap.

  * Finding: the report's preamble relaxes this item's acceptance predicate. The
    Done-when read "each scored against the artifact that owns its supply"; the
    preamble reads "or is declared unscorable with the act that owes the supply
    named", and quantity 2 lands on that disjunct. The disjunct is right and the
    report is not where it belonged: the conventions make an acceptance predicate
    the cell's to author before the lane opens, so that an instrument
    does not arrive with its own acceptance criteria, and this one did.
    Recorded against the landing, not repaired into the cell, the cell being
    closed by this entry. F-383.

  * Finding: after this landing the host-run per-pass peak is owed by no item.
    This item asked for "a per-pass peak the port can be sized against, with the
    passes whose peak grows with roster size named apart from those whose peak
    does not", taken "from a host run of the same act the device will perform".
    The report declines it and names M1.10 as its owner; but M1.10 owns "a
    recorded peak per pass rather than a measurement of a host run", and its Join
    line reads "Q26 prices what they occupy", so the host-run form falls between
    the two. This is recorded as an unowned product, not a handoff: no cell
    carries it, and naming M1.10 would attribute to that item a measurement its
    own text excludes. F-384.

Landed: Tier A. The report states new claims about whether R-18-004e closes on the floors R-18-004b declares, which is a decision for the register's owner and the class the conventions send to a full attended read. No checker rule was added and none holds what this landing created: nothing in [the checker](../../tools/vos/checks/) reads this report's figures against its own JSON artifacts, which is the state [the inference demand](../performance/inference-demand.md) is already in, so the fourth Tier-B condition is unmet and a green wave is not a reading of the report.

### Q27 · Settle the certified-search question and record what a qualified-source survey supplies

The integrated disposition accepts inconclusive placement-search diagnostics and declines new certificate machinery on present evidence. Reopening requires a concrete composition case and reviewed acceptance contract. The source-bearing audit adds missing consumer notes while incorporating no source or proof and changing no estimates. Children own actuals; this parent duplicates no effort.

The existing phase-service assessment passes synthetic scenarios while the target comparison remains open: qualified memory/timing, core freeze and an emitted schedule are missing. Q22e and its prerequisite owners retain guest timing, physical qualification and the store-path/drain decision. The retained assessment and batch receipt bind that boundary.

Retained evidence: [`out/critique-20260914/phase-service.json`](retained-evidence/out/critique-20260914/phase-service.json).

Landed: Tier A. The integrated read checks the decision against the current
register and the source-to-consumer assignments against their actual cells.

#### Q27a · Take the certified-search disposition and record its arms

[The alternatives record](../background/architectural-alternatives.md#certified-placement-and-infeasibility-no-new-certificate-machinery) retains the asymmetric-trust search route: the host memory-plan checks decide today's candidates, while on-device TAL interference checking remains a hard unbuilt prerequisite. Optimality outside the candidate set, a zero lower-bound gap and a distinction between cutoff and infeasibility are not supplied.

New shipped certificate checkers remain refused by the existing yield, checker-inventory and anchor rules. A repository-authored, kernel-checked infeasibility term remains an unanswered unpriced route requiring R-05-020's demonstrations; [MemoryPlannerCertificates.v](../../proofs/MemoryPlannerCertificates.v) supplies finite one-hot theorems without their placement/anchor bridge. No candidate is installed, incorporated or benchmarked. Focused document checks pass at `a1064aa426ee399d7293a68dde7d8f346fc4711e`. Accounting: 0.4 h agent-parallel actual, excluding preceding survey.

  * Finding: the admitted arm's forfeit list closed on the clause "no lower-bound
    argument existing on either side of the port", which contradicts the clause it
    qualifies and is false on the tree: the scaling experiment carries a proved
    lower-bounds section, R-08-012 states charged peak as a lower bound on legal
    span, R-08-012a defines the reservation above it, and the planner's own
    footprint is a fixed floor. The arm now reports the gap as measured and never
    proved zero, and names the real absence, a machine-checked theorem behind any
    of those bounds.
    F-358.

Landed: Tier A. The act produces non-normative prose disposing of rules the register already carries, creating no declaration whose members a rule would count; K-12, K-13 and K-40 hold the entry's citations and its form, and no checker rule was added.

#### Q27b · Record which existing cell each newly qualified source bears on

The [bearing record](../assurance/proof-reuse-bearing.md) maps newly qualified sources to an existing consumer or a named refusal/non-consumer ground. SYS-REFINEDPROSA, Cogent/Dargent, Peregrine and Diaframe reach M4.4, U-10, M6.2b-i and Q19c. Qualification removes no priced sub-obligation, so estimates do not change; uncelled obligations remain in [the proof map](../assurance/unassigned-proof-map.md).

The added-source partition is a revision-bound measurement, not a permanent property. Integrated consumer notes and focused document/co-read checks resolve. No source incorporation, proof, implementation or guest measurement is supplied. Accounting: 0.6 h agent-parallel actual, excluding preceding survey.

  * Three findings.
    * **The survey's strongest language sources point at obligations no cell prices.** RustCompCert, Lean-MLIR, Tree Borrows, VerusBelt, RustHornBelt and Quiver are the six best-qualified Rust and refinement results the sweep added, and every one resolves to an obligation booked outside the priced total. That is no reason to open a cell: a source aimed at an unpriced obligation is a reading, and the plan refuses to let the survey open a cell.
    * **Two of the four consumers already held their source before this act ran.** R-18-018's fourth sub-deliverable names VerusBelt in the register itself, and Q19c's cell names Diaframe and states its terms at the PLDI 2022 deposit. The conventions give an existing start-from no second discount, so the record adds at those two the qualification behind a name the corpus already carried; it narrows what the cell may reach for and removes nothing.
    * **A repair to this record's own overclaim is why the section-8 paragraph reads as it does.** An earlier draft reported R-05-119 and R-05-121 as an obligation the map books nowhere and left its placement to the map owner. The register's trace lines decide it, and a false gap reported against another artifact is worse than an unreported one, because the artifact is correct where it sits.

Landed: Tier A. The record states which open cell each newly qualified source bears on, a new claim per source rather than a derived figure another artifact owns, so it took a full attended read. K-12 holds only that its citations resolve and no rule reaches what it asserts about bearing, so the fourth Tier-B condition is unmet and no checker rule is added or owed.

#### Q27c · Record which candidate's terms decide which consumer

[THIRD-PARTY.md](../../THIRD-PARTY.md) records five candidates whose terms decide existing consumers, distinguishing copyleft dependencies, non-commercial exclusion and absent/unread grants. Reads stay owed at the incorporation milestone; no source is fetched, pinned or incorporated. CakePB and VeriPB remain excluded with the HOL4/Lean class rather than receiving a consumer row.

Authoring `ebcbdfd` and repair `c694468` pass independent review, focused document checks and unchanged co-reads. Accounting: 0.3 h agent-parallel actual, excluding preceding survey.

  * Finding: the record gave CakePB and VeriPB a row deciding Q5b, splitting a
    class its own sources hold together. The plan's Q27a bullet, the static-memory
    research reading and the cited F07 all dispose of CakePB on its HOL4 prover
    before any yield is weighed, the same ground the record's closing
    paragraph uses to exclude the Lean checkers. Both names move to that paragraph
    with the ground named. F-357.

Landed: Tier A. The record states new claims about which upstream's terms reach
which open cell, so it took a full attended read, not a spot read of its
findings.

#### Q28a · Bind one cryptographic claim to its concrete premise dossier

The [AES-GCM dossier](../assurance/aes-gcm-premise-dossier.md) binds one storage-authentication consumer to its selected ideal-permutation theorem, symbolic loss, key/nonce limits and exact correspondence boundary. It records claim invalidation and a creation-based stored-secret horizon; other consumers remain outside this pilot. No upstream code or proof is imported.

[OracleInstantiation.v](../../proofs/OracleInstantiation.v) supplies an axiom-free finite fresh-oracle bound and a constant-oracle refutation of transfer. The integrated proof/kernel and host checks pass against `712afc03624eefbf29539c44d7bab6b8c15b2bf2` plus the document/proof batch. This is a boundary witness, not a GCM security reduction. Production correspondence, resource limits and physical/support evidence remain owed.

Accounting: original estimate 14 h, range 8–20; retained planning estimate, actual n/a, excluded from calibration. Initial candidate survey/source-selection intervals are missing; later timed proof/review does not replace them.

Landed: Tier A. The full read accepts the premise dossier's bounded scope;
it grants no numerical cryptographic margin or release admission.

#### Q29a · Freeze the web application profile and qualification contract

The [web profile](contracts/web-application-profile.md) freezes `vos-web-pilot/1`, its two pilots, identity/lifecycle/resource boundaries and paired success/refusal cases before implementation. Review preserves navigation freshness, borrow/reuse gates and pool outcomes, separating native operation cost, target time and compatibility claims.

The prerequisite ledger keeps existing owners and adds conditional browser packages outside totals. U-15/U-16 do not supply the interpreter or required theorems; parser work and the Rust-route opening decision remain separate. Q29b/Q29c stay open behind missing runtime, services, logic and timing. The estimate milestone partition is corrected without moving work into the software MVP. Integrated host checks pass against `fa7bd1722e4af406a7495a4c46b48bb2ec801875` plus the contract batch; no target run is claimed.

Accounting: original estimate 12 h, range 8–16; retained planning estimate, actual n/a, excluded from calibration because reliable exclusive session duration was not captured.

Landed: Tier A. The full read accepts a bounded qualification contract and its
opening assignments; it confers no browser implementation or admission proof.

#### Q30a · Freeze the standards feature map and compute semantic contract

The [feature map](compute-feature-map.md), [semantic contract](contracts/compute-semantic.md) and [source review](compute-upstream-review.md) freeze OpenCL 3.0.19/OpenCL C 1.2, SPIR-V 1.0 and ROCm 6.3.0 pilot targets. They specify finite computation domains, ordering, correspondence, actor/resource lifecycles, refusals and comparators. Q30d–Q30g retain implementation and qualification; no upstream is incorporated or full conformance claimed.

At `503285e5`, focused document, type, lint and compute-audit refusals pass. Membership is complete against OpenCL-Docs `85da0d12c298ffa9eefd2adb1864f2c8193cbe3e`, `xml/cl.xml` SHA-256 `eb5178c428da9e77ede6350bc74ab302890a8e321a44cd84dbf54ea16bdd6946`; semantic completeness remains reviewed judgment. Independent review repairs signed-zero and reduction-sequence ambiguities.

Accounting: original estimate 24 h, range 12–36; 0.5 h agent-parallel actual, excluding shared integration/gates.

Landed: Tier A. The accepted artifact is a reviewed contract and source audit;
admitted execution, runtime resource evidence and standards conformance remain
the open implementation and qualification owners' obligations.

#### Q32a · Formalize app lifecycle and workflow transition admission

[WorkflowProfiles.v](../../proofs/WorkflowProfiles.v) and [its contract](contracts/workflow-formal.md) formalize two abstract apps with finite arenas and settings. Ownership, resource bounds, transition peaks and conditional non-resurrection are proved; checkpoint/crash, grants, restore and release have explicit outcomes and complete reuse conditions.

At `8e76b43b`, native compilation, kernel checking, zero-assumption audit and quantified witnesses pass. The source-generated accepted/refused event population and named boundary cases agree. All 26 compiling mutants are killed, with zero stillborns, survivors or timeouts. The earlier stopped aggregate audit supplies no passing verdict; the integrator's full native gate supplies integrated evidence. Physical inventory, durable bytes, schedule/refinement, concrete presets and measurements remain Q32b/Q32c and runtime obligations. No production checker or universal allocator is supplied.

Accounting: original estimate 24 h, range 12–36; 0.6 h agent-parallel actual, excluding shared integration/gates.

Landed: Tier A. This accepts the finite formalization and its explicit refinement
interfaces, not the open operational pilot or measured reclamation economics.

#### Q34a · Author the elastic-domain contract

[ElasticDomain.v](../../proofs/ElasticDomain.v) extends the existing partition, executive and memory vocabularies; [its contract](contracts/elastic-domain.md) separates statements, proved contract properties and Q34b–Q34e consumers. It proves eligible-deadline selection, conforming dispatch boundaries, inter-app clearing, conditional share/counter bounds and directional capability confinement, with isolated refutations for every required negative.

Independent review repairs missing exit-block cost, leave-accounting attribution and confinement/yield/time premises. At `625596ea`, the source SHA-256 `979d236d8ba05d841a5dc9ea6042a2e8cd1e003da16499002629779130d50e33` compiles, has empty assumption readings and witnessed records, and passes recursive kernel checking. K-106's generated ledger awaits integrator repair; the full native gate owns integrated evidence. Crown-jewel row 31 is partial, and share-bound register questions remain open.

Accounting: original estimate 12 h, range 8–16; 2.4 h agent-parallel actual, excluding integration/gates.

  * Four findings.
    * **R-07-037g's lag bound omits the sink.** A conforming two-member trace ends with served-time lags of magnitude 22/5 against the register's bound of 4 (`the_register_s_lag_bound_is_refuted`), and over slot time the heavy member reaches 67/5. The trace stays inside a bound of one request plus a call bound plus a yield bound, which is named and not adopted. Standing: a register question, and Q34b's share-bound theorem waits on it.
    * **The share bound's time base is unstated.** Over slot time, intra-slot steps and idle tails accrue shortfall. A single member ends two slots of 12, served 6 of the 24 units, at lag 18 against a bound of 4 (`the_slot_time_reading_is_refuted`). R-11-006c charges the idle tail to the domain without saying whether a member's share is measured over it. Standing: a register question.
    * **Which lag the share bound quantifies, and with it whether the dispatch applies EEVDF's published leave rule, is unstated.** Without the adjustment, a member with work pending is starved slot after slot while its served-time lag stays inside the bound (`a_leave_without_the_published_adjustment_is_not_work_conserving`). With it, the same member is selected at once, but its accounting lag is 0 while its service lag is -13/2 (`the_published_leave_separates_accounting_from_service_lag`). Standing: a register question, and `charge` and `rebalance` follow its answer.
    * **Which members are live for the share bound is unstated.** The bound is taken over every enumerated member, each accruing entitlement only while it competes. Standing: a register question, recorded as the reading taken.

Landed: Tier A. No checker rule was added, and none holds what this item created. The proof gate's compile, exact assumption audit, witness scan and kernel recheck hold the artifact's decisions, and R-05-150's review holds its agreement with the register. The fourth Tier-B condition is therefore unmet.

#### Q35a · Record the verified-C route's blockers and assign the authored C

The reviewed record assigns authored C and separates source-level refinement from binary-level verification without changing the register. VST/Iris carriage, exact whole-environment assumptions and stock versus contained Clight semantics remain qualification questions. Installation results are solver simulations, not builds; CHERI/VST searches bound the survey and do not prove absence.

Kernel C takes the route selected by the review-gate acts; firmware retains source-level refinement; supervisor C remains its oracle/producer route; copy-service C stays contained with the safe-Rust obligation deferred. Harness, emulator and tool C do not ship except the target translation unit's included kernel sources. Binary proofs still need emitted machine semantics, support carriage, logic and compiler correctness; host differentials/target runs do not replace them. Independent verifiers repeat command/source readings except the two searches.

Calibration: no original estimate was recorded; excluded from the fit. Recorded agent-parallel actual is 5.5 h, excluding hosted validation.

* Six findings.
  * **No VST configuration is qualified at the locked prover.** The VST/Iris line three register entries name does not install beside the prover, and VST's non-Iris line, which those entries do not name, installs only with a CompCert that bounds the prover below its motivated upgrade. Open: Q35e qualifies a foundation or refuses one with a priced repair. F-462.
  * **Every VST or CompCert Clight development loads axioms and parameters outside R-05-164's empty declared set, and no entry decides whether they enter it.** Open: a register act at the review gate, with Q35e's measured summary as its input. F-463.
  * **Stock VST's theorems are stated over a host-configured stock Clight, not the contained compiler's compartment-annotated Clight over a capability-widened value type.** No entry decides whether VST enters as a program logic under R-05-020, or over which C semantics. Open: a register act at the review gate, with Q35e stating which C semantics each foundation covers and any bridge to the contained compiler's Clight. F-464.
  * **The solver no longer selects the VST release M3.4c-i's reading recorded.** A non-Iris release published after that reading installs beside the prover in simulation, while the Iris line either replaces the prover or finds no solution. Standing: [the VST record](../../THIRD-PARTY.md#vst) holds the current reading, and M3.4c-i's note remains the measurement of its day. F-465.
  * **R-07-050's fast-path proof has no cell, and the slot-boundary timer trap's executive calls are plausibly its scope.** R-07-050 names the trap and context-switch path, and the slot-boundary timer trap, R-07-040's sole asynchronous trap, calls the executive to advance the cursor and to select and release the successor. Open: the proof map places the proof at entry after M1.4 and U-26 decide the instrument, and the scope reading is a register question. F-466.
  * **Neither of Vélus's correctness theorems covers the library-mode product the supervisor trial exchanged.** Both assume a compiled main node, and the assembly-level one also rests on an axiom about builtins. Open: M6.1b-ii's complete producer records which Vélus theorem, if any, and in which mode, covers the Clight AST it generates, and that the printed, normalized text the accepted compiler parses stays outside every theorem. F-467.

Landed: Tier A. The full read covers the six findings against their register entries and the readings' verifier verdicts, the commissioned cells' predicates after the adversarial review's repairs, the proof map's commissioning lines and the work-order dispositions. No checker rule was added; K-12, K-40 and K-82 hold the entry's links, glyphs and finding count, and none holds its readings.

#### Q35c · State the logic route's reviewed breakdown

[The breakdown](../assurance/machine-logic-breakdown.md) states U-22's route, exact producer/semantic interfaces and the first checkable increments of R-13-017's four theories. It keeps the mandated Katamaran route; alternatives need a register amendment. Q35m's dependency trial and Q35k/Q35l's conditional increments are accepted separate cells; full agreement and remaining logic establishment stay unpriced and must be scoped first.

The retained receipt binds source identities and commands. Islaris `c978e10f50db5c40f0fdf113f5f76a779782c6f9` yields no compiled closure, not an empty assumption set. A separate Iris 4.5.0 probe builds and passes strict import/assumption/kernel checks; it qualifies neither every Iris source nor framework compatibility or a canonical machine. The first build's shell exit status is unretained, but explicit incremental confirmation passes. Before/after switch exports agree; no upstream source or shared lock changes.

Calibration: original estimate 16 h, range 9–23; retained estimate, actual n/a · agent-parallel. Initial discovery/reading and complete author/review intervals were not captured; the partial qualification/finalization interval is not a full actual and is excluded from calibration.

  * Finding: **Pinned Islaris cannot build unchanged at the locked prover, so the selected example's exact assumption closure is unavailable.** The dependency solver refuses for missing coq-lithium; pristine make refuses the removed Dune coq 0.8 extension; strict import and kernel audit refuse the absent compiled example root. Open: Q35m qualifies the required dependency combination or records a bounded refusal and separately scoped port follow-up. F-785.

Retained evidence: [receipt](retained-evidence/root/build/lane-q35c-20261010-logic/q35c/receipt.json), SHA-256 `92c7b48adbae2925f6d13ee8d9e257711c0936f460d72b6dc3dbd7962e2b9905`.

Landed: Tier A. The integrator read the whole route, selected theorem statements, producer/semantic boundaries, receipt and refusal evidence, and the first increments and consumer joins. The foundation ledger and proof map carry the accepted breakdown; third-party readings stay at their exact pins. Worker focused document checks and authored whitespace checks passed. [Initial Host CI](https://github.com/symbiogenesis/VerifiedOS/actions/runs/38034381487) refused retained copies without external native-path citations; the record now links their exact bytes and hashes, and the focused retained-evidence regression passes. The refreshed settled hosted handoff is recorded by fanout.

#### Q35e · Qualify a source-level C-refinement foundation at the locked prover

The [qualification](../assurance/c-refinement-foundation-qualification.md) builds or refuses the named foundations in private switches, binding sources, licences, commands and kernel summaries by receipts. The shared proof switch remains unchanged; no foundation or compiler source is incorporated.

VST 2.17's non-Iris line and a checked client build at Rocq 9.2.0, but recursive Floyd checking aborts without a summary. Admission-based summaries are diagnostic evidence, not acceptance. VST's Iris line fails. RefinedC builds only with Lithium's bound ignored; its checked client passes while the whole closure names one axiom and two test parameters, despite the client's assumption reading being empty. CN-to-Coq's pin refuses at the prover and its `provable` placeholder admits every constraint; the bound-ignored build is not run.

No foundation uses the anchor or contained compiler's C semantics, and no bridge exists. Proposed assumption/carriage acts are untaken; F-462, F-463 and F-464 remain open. VST's repairs are Q35h–Q35j; further ports remain unpriced. This records qualified probes and refusals, not an admitted source-refinement foundation.

Calibration: original estimate 14 h, range 8–20, class X; 3.6 h agent-parallel actual. Restarted sessions reuse inspected outputs; measured effort excludes host standby and hosted validation.

* Ten findings.
  * **The kernel checker aborts on VST's Floyd soundness module, so no Verifiable C client yields a summary.** Open for release adoption and VST requalification: Q35h reduces and reports the anomaly; upstream fixes #22555 in #22556 on 2026-10-08, but no fixed release is published as of 2026-10-10. F-486.
  * **The checker names checked fields of alias-sealed and functor-sealed modules as axioms, and no rule decides whether the gate covers them or an amendment enumerates them.** Open: Q35i, at the proof gate's owner. F-487.
  * **VST's Iris line does not build at the locked prover.** Standing: a port is unpriced, its failure census unmeasured. F-488.
  * **VST's non-Iris libraries build without CompCert's non-commercial package, but no route yet produces a client's input outside it.** Open, owed only if VST is admitted: another producer, a hand-authored AST, or an R-05-020 and containment act, with whether the build's reading of the unlisted `VERSION` engages that term. F-489.
  * **RefinedC builds at the locked prover only with Lithium's Coq bound ignored, on source pins the locks do not carry, and its theories install only with its frontend.** Open: an upstream bound or packages, or the opam guide's acts, if RefinedC is admitted. F-490.
  * **The gate's compile settings refuse both checked foundations' clients, because importing each raises a default warning.** Open: the gate's warning policy or the upstream notations. F-491.
  * **RefinedC's closure loads two Lithium test parameters beside its one axiom, and the gate refuses all three.** Open: the review gate's R-05-164 act, or an upstream removal that reduces it to one name. F-492.
  * **CN-to-Coq is refused at the prover by its own Coq pin, and its `provable` placeholder accepts every solver constraint, so it does not close obligations foundationally as R-10-008's specification text says.** Open: a register question. F-493.
  * **CompCert 3.18's release archive declares version 3.17, so `clightgen`'s banner does not identify the producing release.** Standing. F-494.
  * **Every foundation's theorem is about an input an unverified front end produced, over a C semantics the contained compiler does not consume.** Open: Q35j and the review gate's F-464 act. F-495.

Landed: Tier A. The integrator's read covers the ten findings against their register entries, the proposed amendment's three names and types against the retained summaries and the pinned sources, the refusal of VST against R-06-012, R-10-008 and R-18-026, both receipts for upstream content (which they carry by path, hash, line number and matched token only), the predicates and ranges of Q35h to Q35j, and the proof map's two rows. No checker rule was added; K-12, K-82 and the retained-evidence test hold the entry's links, finding count and receipt hashes, and none holds its readings.

#### Q35f · Remove the canonical term's model-side axioms and bind its target to the frozen profile

The model's canonical Rocq emission is bound to the frozen primary composition and removes 54 removable model axioms, leaving exactly F-480's 31 floating-point operations. [The record](../assurance/canonical-machine-term.md) owns the host-hook semantics and finite comparison evidence; Q35b still owns term compilation, closure and compiled size.

[The emission command](../../tools/vos/rocqterm.py) invalidates old output, refuses missing/stale/moving inputs and binds generation identity. Focused command refusals pass. Quotient/remainder checks satisfy round-toward-zero with negative controls; SoftFloat comparison replay agrees over 207,200 vectors. Mutation outcomes remain finite: adapter 1 killed/3 survived/11 stillborn; library 28 killed/6 survived/19 stillborn. Survivors are unreached paths or equivalent rewrites, not established proof coverage. Shipped compositions disable half-width operations, whose internal-error definitions remain in the term.

Both Sail candidates typecheck. Model/CTest/corpus/bundle behavior checks remain pending Guest CI evidence at publication. The retained emission receipt at `04c35541` binds `rv64d.v` `65db6f87…` and unchanged `rv64d_types.v` `d63859df…` to sources and configuration. No standing gate yet holds the axiom list or floating-point differential (F-735); F-479's upstream extern spelling remains unresolved outside this model.

Calibration: 1.4 h agent-parallel actual against 18 h estimate, range 11–25, class I; integration review and hosted validation excluded.

* Six findings.
  * **Guarding the library's emulator-memory file for Rocq is not enough on its own.** Sail typechecks the library's emulator implementation of the memory outcomes for every target, and that implementation calls the primitives. So the model restates the declarations for Rocq under `$sail_internal`, as internal-error definitions. Closed at the item. F-732.
  * **The half-width arms cannot be guarded, so their sixteen names leave the axiom list but not the term.** `$iftarget` works only between top-level definitions, and deleting the arms would remove `Zvfh` and `Zvfhmin` from the emulator's default template. Standing: the term carries them as internal-error definitions behind guards no shipped composition opens. F-733.
  * **The term's persistence choice over-approximates the emulator.** It admits a `true` after a `false`, and a `false` with no host failure, so any property needing a block command to complete `DONE` needs an assumption on the choice. Standing: Q35c's breakdown reads it. F-734.
  * **No CI runs `run.py model rocq` or the comparison differential.** The binding, the 31-axiom list and the SoftFloat agreement are lane evidence, not standing gates. Open: a hosted lane runs the emission and holds the term's digest and axiom list to the record. F-735.
  * **Q35b's record named a stale profile digest.** `verifiedos.json` was reformatted between Q35b's base and this one without moving the term. Closed at the item: the record states both digests. F-736.
  * **F-479 is fixed in this model only.** Upstream `sail-riscv` still spells the `rocq:` keys, which Sail 0.20.3's Rocq backend does not read. Standing: no upstream report is taken. F-737.

Retained evidence: [`/root/build/lane-q35f-axioms-20261002/q35f/quotrem/QuotRem.v`](retained-evidence/root/build/lane-q35f-axioms-20261002/q35f/quotrem/QuotRem.v); [`/root/build/lane-q35f-axioms-20261002/seed/sail-fpcompare.journal`](retained-evidence/root/build/lane-q35f-axioms-20261002/seed/sail-fpcompare.journal); [`/root/build/lane-q35f-axioms-20261002/seed/sail-fpcomparelib.journal`](retained-evidence/root/build/lane-q35f-axioms-20261002/seed/sail-fpcomparelib.journal); [`/root/build/lane-q35f-axioms-20261002/verifiedos-model/rocq/receipt.json`](retained-evidence/root/build/lane-q35f-axioms-20261002/verifiedos-model/rocq/receipt.json), SHA-256 `f50c72d6…`.

* Landed: Tier A. The item takes a new modelling decision, F-485's. The integrator's read covers:
  * every model diff against the cell's **Owns** list;
  * the half-width and emulator-memory definitions against the compositions that reach them;
  * the flag adapter's bit order;
  * the host-hook decision against the record's comparison;
  * the emission command's refusals and documentation;
  * the findings against the register.

  No checker rule was added, and nothing in the checker holds the term's axiom list (F-735). `test_model_rocq`, `test_oracle` and `test_retained_evidence` hold the command, the differential's specification and the retained copies.

#### Q35g · Remove the support library's Stdlib axioms from the canonical term's closure

[The canonical-term record](../assurance/canonical-machine-term.md#the-support-library-change) owns retained support-library/backend changes that remove F-481's five Stdlib axioms from a no-`Real` import closure. Probes and positive controls at locked Rocq 9.3.0 confirm no axioms without `Real`, the four real-number axioms with it and `eq_rect_eq` when explicitly imported. All 30 stdpp modules compile; independent review reproduces the changes and controls. BBV modules remain uncompiled.

The canonical term was neither emitted nor compiled. Sail's existing alternative-import flag removes `Real` without an upstream change (F-777); library carriage needs the opam-guide act (F-778/F-483). The owner moved the canonical-term compile check to Q35b. Retained patches/receipts supply the exact sources and licences; no submission or switch-carriage act is taken. Real-register emission still fails in the probe (F-779).

Calibration: original estimate 5.5 h, range 3–8, class X; 2.0 h agent-parallel actual, excluding provisioning, user decision and hosted validation.

* Three findings.
  * **The model's Rocq target still emits `Require Import SailStdpp.Real`.** Sail 0.20.3's `--rocq-alt-modules` can remove it with no Sail change, as the backend change does on a probe model. Open: a change to the model target, which moves the term's generation identity. F-777.
  * **The changed support library reaches the proof switch only by the opam guide's act.** The guide's rule admits commit pins in QuickChick's recipe alone and returns `rocq-sail-stdpp` only by a release. Open: the guide carries the change with a recorded exception and a hosted re-lock, or awaits an upstream release, whose submission needs the user's approval. F-778.
  * **Sail 0.20.3's Rocq backend emits a model with a real-typed register that does not compile.** Its register encoding requires `Countable` of each register type, and `R` has no instance. Standing: the model declares no real-typed register, and no upstream report is taken; whether `sail2` still fails is unread. F-779.

Retained evidence: [The canonical-term record](../assurance/canonical-machine-term.md#the-support-library-change) states two changes, one to `rocq-sail-stdpp` 0.20.3 and one to Sail's Rocq backend, which together take F-481's five Stdlib axioms out of a term that loads the changed library without `SailStdpp.Real`, and the probe that measures this at the locked prover. The user's direction made an upstream submission a last resort, approved only after the user sees the changes and only if it is essential and generally applicable, and preferably none; no route needs one, so both changes are held as retained evidence, [`/root/build/lane-q35g-20261003/q35g/coq-sail-reals-eqdep.patch`](retained-evidence/root/build/lane-q35g-20261003/q35g/coq-sail-reals-eqdep.patch); [`/root/build/lane-q35g-20261003/q35g/sail-rocq-real-import.patch`](retained-evidence/root/build/lane-q35g-20261003/q35g/sail-rocq-real-import.patch); [`/root/build/lane-q35g-20261003/q35g/receipt.json`](retained-evidence/root/build/lane-q35g-20261003/q35g/receipt.json), SHA-256 `2cbc04a706457a1085e677860e95d90ada83bbf7669ef6103de1e1f5636ff9b1`; [`/root/build/lane-q35g-20261003/onto/Onto.v`](retained-evidence/root/build/lane-q35g-20261003/onto/Onto.v).

Landed: Tier A. The integrator's read covers both diffs against the cell's **Owns**, the user's upstream direction and the generality argument; the probe and its controls against the cell's first **Check**; the owner's act that moved the second **Check** to Q35b's owed compile; the record's routes against the opam guide's rule; the licensing map's and THIRD-PARTY.md's rows for the retained diffs and licence; and the findings against the register. No checker rule was added; K-12, K-82 and the retained-evidence test hold the entry's links, finding count and retained copies, and nothing in the checker holds the probe's axiom lists.

#### Q35h · Reduce and report the kernel checker's anomaly on VST's Floyd closure

[The anomaly record](../assurance/checker-resolver-anomaly.md) and [standalone reproduction](../../tools/checker-reproductions/resolver-roots/README.md) reduce VST's recursive-checker failure without copying VST source or weakening its proof. Released 9.1.1/9.2.0/9.3.0 binaries and tested master reproduce the resolver-roots anomaly and related alias-typed-field failure, while one-construct controls pass. Receipts retain commands, binaries, sources and verdicts; no switch or upstream source changes.

The user-approved report [#22555](https://github.com/rocq-prover/rocq/issues/22555) is filed. [#22556](https://github.com/rocq-prover/rocq/pull/22556) merges on 2026-10-08 at `33ec1b11dbf2af4be99d53adeb275c5924e37e41`, but no fixed release or post-fix qualification is available at the 2026-10-10 reading. F-486/F-780 stay open for adoption and VST rechecking. Bounded admission leaves the soundness closure unchecked and cannot supply acceptance; source-side transparency changes are unqualified carriage/abstraction decisions.

Calibration: original estimate 6 h, range 3–9, class X; 2.2 h agent-parallel actual, excluding provisioning, user decision, report filing and hosted validation.

* Two findings.
  * **`rocqchk` 9.2, 9.3.0 and master raise `IllFormedConstant` on a constant typed through the alias field of a sealed module inside an applied functor, where 9.1.1 raises the resolver-roots anomaly and the compiler accepts the file.** Open for post-fix qualification: carried in #22555 as a symptom of F-486's defect; upstream closed the report through #22556 on 2026-10-08, but no fixed release or post-fix measurement is available as of 2026-10-10. F-780.
  * **The checker's `-admit M` leaves M's whole closure unchecked except libraries named on the command line, so the smallest admission over VST 2.17's client names 282 constants, 60 of them the soundness module's own sealed fields.** Standing: F-463's input. F-781.

Retained evidence: [The record](../assurance/checker-resolver-anomaly.md) reduces F-486, the anomaly `rocqchk` raises on VST 2.17's `floyd/SeparationLogicAsLogicSoundness.v`, to a standalone reproduction under [tools/checker-reproductions/resolver-roots/](../../tools/checker-reproductions/resolver-roots/README.md) that copies no VST source. It reads every released checker binary the guest holds and rocq master against the reproduction, reads upstream's sources, release line and tracker, files the report, and reads what the gate could obtain around the anomaly by checker flags, by admission and by a change to VST's own sources. It moves no register entry. Its receipt [`/root/build/lane-q35h-20261003/receipts/q35h-record.json`](retained-evidence/root/build/lane-q35h-20261003/receipts/q35h-record.json), SHA-256 `eef79158189f73d514a58d13e66f5217c6ecca93ed61428b6e2bd9dd56e03a33`; [`/root/logs/q35h-review-20261003-rereview-census.log`](retained-evidence/root/logs/q35h-review-20261003-rereview-census.log); [`/root/build/integrator-20261003/rocq-master-probe2.sh`](retained-evidence/root/build/integrator-20261003/rocq-master-probe2.sh); [`/root/logs/integrator-20261003-rocq-master2.log`](retained-evidence/root/logs/integrator-20261003-rocq-master2.log).

Landed: Tier A. The integrator's read covers the reduction table against the receipt's forty-two runs and seven checker identities and the census's seven more; the 9.3 line's backports against the clone; master's verdicts against its retained log; the filed report against the text the user approved and the user's upstream direction; the bounded admission's 282 names against Q35e's 380 and F-487's 204; the source-side route's twelve seals; and the two findings against the register. No checker rule was added; K-12, K-52 and the retained-evidence test hold the entry's links, the reproduction's licence marks and the retained copies, and none holds the readings.

#### Q35i · Decide the gate's reading of alias-sealed and functor-sealed module fields

The proof gate covers undeclared installed fields of checked alias/functor-sealed libraries by a framed compiler assumption query over the worker's roots. Admission cover runs first; proof-module names, failed or incomplete queries and undeclared assumptions never qualify. The soundness argument and eight locked-Rocq reductions resolve implementations through seals while preserving hidden-admission/axiom refusals. No register entry changes.

At `23f36e8e`, focused proofcache/proofaudit tests pass; the native sealed-field case and independent adversarial replay pass. All 12 compiling seeded weakenings are killed, with no survivors or stillborns. Retained reductions, queries, summaries and logs bind the evidence. The live corpus has no residue, so the new cover is not exercised there; implementation changes require fresh hosted evidence. F-487 closes as a gate-reading decision, not a qualification of VST's 204 sealed fields. F-486 and F-463 still govern those consumers.

Calibration: original estimate 8 h, range 4–12, class X; 1.8 h agent-parallel actual, excluding provisioning and hosted validation.

* Three findings.
  * **For an assumption a seal hides from the environment, the compiler's reading is the gate's only one.** rocqchk names no constant a functor body or a sealed body hides unless a field it checked under an interactive seal uses it, so the two enumerations are independent for every loaded name and not for a hidden one; before the cover every such field refused outright, and the hidden case still refuses through the compiler. Standing: a residual of the cover's design. F-774.
  * **The assumption parser refuses a `Print Assumptions` entry carrying Rocq's `used in … to prove` lines and an entry printed without a type.** Rocq 9.3.0 prints the first for an axiom eliminated by a bare empty `match` (`printing/printer.ml` 757-768) and the second where printing the type raises a noncritical error (724-726, `safe_pr_ltype`); the parser reads neither as an entry, so a hidden admission or axiom reached in either form refuses as a parse fault rather than by name. Standing: both refuse, and a declared axiom printed in either form would refuse as unframed, which R-05-164's declared set meets when it grows. F-775.
  * **No declared-entry spelling satisfies both of the gate's comparisons.** The gate compares a declared entry with the kernel summary by its fully qualified name (`_kernel_axioms`) and with `Print Assumptions` by the printed entry whole (`_worker_fault` and the assumption audit), whose name is the shortest path unambiguous in the query's environment, `Classical_Prop.classic` for `Stdlib.Logic.Classical_Prop.classic`; a declared entry spelled either way matches one reading and not the other. Open: owed before R-05-164's declared set grows a name, latent while that set is empty, on F-487 and F-463's join path. F-776.

Retained evidence: [`/root/build/lane-q35i-20261003/reduce/receipt.json`](retained-evidence/root/build/lane-q35i-20261003/reduce/receipt.json), SHA-256 `70832feeb22a56dacc34f94e8ade19ea0aada4bad359e7d7a50a438496955b8f`; [`/root/logs/q35i-20261003-reduce.log`](retained-evidence/root/logs/q35i-20261003-reduce.log); [`/root/build/lane-q35i-20261003/reduce/queries.txt`](retained-evidence/root/build/lane-q35i-20261003/reduce/queries.txt); [`/root/build/lane-q35i-20261003/reduce/NestedSealed.v`](retained-evidence/root/build/lane-q35i-20261003/reduce/NestedSealed.v); [test_proofaudit](../../tools/tests/test_proofaudit.py): `sealed-field-queries-are-framed` (the query Requires the roots first and frames each name; unqualified names, invalid roots and empty name lists are refused; answers are read as the audit reads them) and `kernel-verdict-needs-a-clean-summary`, which now reads the installed name through a self-reporting compiler and asks nothing for a proof module's own. [test_proofcache](../../tools/tests/test_proofcache.py): `kernel-reading-covers-checked-sealed-fields` (a closed field is covered and reported; a hidden assumption, an admitted implementation, a genuine axiom and a proof's own name, `Right.a` and the nested `Right.Inner.a` alike, refuse without being read; an omitted name and a failed reading cover nothing; a declared entry matches whole, type included, and every entry must be declared; the admission cover goes first and the compiler is asked exactly its residue, by every worker, over the worker's roots), `sealed-reading-runs-one-framed-query`, `kernel-admission-covers-installed-names` extended with the reading's residue, and the toolchain-lane `native-sealed-fields-read-through-seals`, which compiles four authored libraries, exposes them through `ROCQPATH`, which `rocq c` and `rocqchk` both read as a recursive root (`sysinit/coqloadpath.ml` 38, `checker/coqchk_main.ml` 123-136), and runs the gate: the proved alias and functor pass with four fields covered, the admitted alias refuses `Alias.x_le` and `Impl.x_le`, the admission hidden in a sealing functor refuses exactly `App.x_le`, and the genuine axiom refuses `Alias.x` and `genuine`. On the host, `test --only proofcache` passes 15 cases and `--only proofaudit` 29 at `23f36e8e`; the native case ran once in the guest as a bounded probe and passed in 12.8 s ([`/root/logs/q35i-20261003-native-sealed.log`](retained-evidence/root/logs/q35i-20261003-native-sealed.log).

Landed: Tier A. The integrator's read covers the rule against the cited checker lines and the review's nested probes, the cover's code and its soundness argument against the item's criterion, the tests and the twelve mutant results, the receipt and log against the readings stated here, and the three findings against their register entries. No checker rule was added; K-12, K-82 and the retained-evidence test hold the entry's links, finding count and the retained copies, and none holds its readings.

#### Q35j · State the bridge from a source-level foundation's C semantics to the contained compiler's Clight

[The bridge record](../assurance/c-semantics-bridge.md) and [Bridge.v](../../tools/c-semantics-bridge/Bridge.v) state a forward simulation between imported stock VST 2.17/Clight 3.17 and contained compartment/capability-widened Clight at `1cd36c710967e89db21da08f237ffca78843b883`. Statement, inhabited register-only witness and reached capability-assignment refutation compile privately at Coq 8.20.1; unchanged contained source refuses Rocq 9.3.0 and 9.2.0.

Acceptance closes only the statement, with producer, same-source, structural-correspondence and pointer-width premises. It supplies no frontend/backend correctness, simulation proof or locked-prover port. F-464, F-489, F-495, Q39 and F-522 remain open; no anchor, assumption allowance or foundation is admitted. The owner retains private receipts/logs; hosted gates assess repository deliverables separately.

Calibration: original estimate 16 h, range 9–23, class X; retained planning estimate, actual n/a. Initial reading/acquisition intervals are missing; build durations do not measure complete authoring/review/integration, so calibration is excluded.

Landed: Tier A. The integrator read the statement against both imported interfaces, the explicit frontend and architecture premises, the inhabited witness and reached refusal, the proof plan and anchor argument, and the private compilation evidence. This acceptance closes the statement item only. Host CI and cold Guest CI supply the settled batch's validation handoff; a pending guest verdict supplies no proof acceptance.

#### Q35m · Trial the machine-logic dependencies at the locked prover

[The dependency trial](../assurance/machine-logic-dependency-trial.md) reaches its bounded refusal endpoint: unchanged Rocq 9.3.0 strict compilation independently reproduces namespace/notation failures in the exact Islaris/Lithium/RecordUpdate and Katamaran chains. Framework closures, elaborated comparisons and exact assumption audits remain unavailable (`null`), not empty or passing. Frozen sources/settings and before/after switch exports are preserved.

The retained receipt and [catalog](../../tools/machine-logic-trial/evidence.json) bind attempts, licences and diagnostics. A separate stock-Iris adequacy import/kernel check passes only its probe. Source compatibility and carriage have an unpriced continuation; F-785 stays open and Q35k closed. No framework combination or canonical machine is qualified.

Calibration: original estimate 8 h, range 4–12, class X; retained planning estimate, actual n/a. Initial reading/acquisition and provisioning-to-dispatch effort are unmeasured, and root review/integration is additional; the non-exclusive bracket/final-probe duration cannot establish a complete actual. Calibration is excluded.

* Finding: **Pinned Katamaran's binary-adequacy source imports `Program.Equality`, whose separate exact probe names an undeclared equality axiom.** Strict compilation and recursive kernel checking of that probe exit 0, while `Print Assumptions` and the whole-environment summary name `Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq`. This is a dependency-import conflict, not a complete Katamaran audit. Open: the machine-logic foundation and opam carriage owners resolve the import under unchanged statements and exact-set policy before compatible carriage or Q35k; no allowlist expansion is accepted. F-786.

Retained evidence: [`/root/build/lane-solve-20261010-c/q35m/evidence/receipt.json`](retained-evidence/root/build/lane-solve-20261010-c/q35m/evidence/receipt.json), SHA-256 `42f49806a6d30b0e4c0ec04fe0a5770907cf15b7abd1221516ef42609bc326dd`.

Landed: Tier A. The integrator read the frozen source/interface choices and licences, strict diagnostic refusals, separately scoped Iris and equality probes, explicit unavailable closure fields, preserved switch exports, runner and retained evidence, and the continuation against the permitted refusal endpoint. Focused retained-evidence tests, lint and both type-check platforms pass. Host CI and cold Guest CI supply the settled batch's validation handoff; the guest verdict remains pending until supplied externally.

### Q36 · Upgrade the proof switch to Rocq 9.3.0

The proof switch and [rocq.lock](../../tools/opam/rocq.lock) move to Rocq 9.3.0 with OCaml 5.4.1. The exported switch equals the lock; no package is pinned. Release licence readings are unchanged. Comparisons use the unchanged proof sources at base `6a06a87d` on 2026-09-29 under Rocq 9.2.0 and 9.3.0.

Both proof runs passed compilation, exact assumption audit and kernel recheck: every constant was closed under the global context, with no unsafe assumption or undeclared axiom. Their inventories agree in symbol names, printed types and claims. Rocq 9.3.0 rejects all three #21839/#22382 counterexamples that 9.2.0 accepted. Both compilers still accept #22287's reproducer, and both kernel checkers reject it; that reading does not qualify the defect as fixed.

The kernel-summary parser requires 9.3.0's final section. The CIC exporter fixtures reproduce native output, and corpus reports agree except for dependency closures growing when assumption traversal includes types as well as bodies. No closure shrank. Focused proof-audit, corpus, provisioning and cache tests and type checks passed. The qualification findings retain the unresolved boundaries.

* Four findings.
  * **Every project switch recipe creates its switch empty and imports its lock, and the import records no invariant, so a provisioned switch's export omits the lock's `compiler:` section.** The locked switches in this guest carry an invariant no recipe sets. Open: the recipes set the invariant each lock names, or the opam guide states why the locks keep the section. F-496.
  * **Both editions' `rocqchk` refuse #22287's reproducer while both compilers accept it.** Standing: a reading of one reproducer, not of the defect. F-497.
  * **The CIC corpus exporter's test fixtures differed from what 9.2.0 and 9.3.0 print for probes of their shapes under the exporter's settings.** Closed here by verbatim replacements. F-498.
  * **The CIC qualification's count of symbols reaching no transparent constant rests on 9.2.0's body-only closure, so it includes symbols whose type alone reaches one.** The record's sentence now calls the figure an upper bound. Open: M6.2b-0b re-reads it at the locked prover. F-499.

Calibration: original estimate 6.5 h, range 4–9, class X; actual 1.6 h, attended. Unattended builds and comparisons ran inside the recorded interval; hosted validation is outside it.

Landed: Tier A. The read covers the lock and its export, the counterexample readings, both proof runs' inventories and the empty assumption audit, the kernel-summary parse against the pinned checker's sources, the exporter comparison and its named difference, the restated statements against the grep, and the four findings against their register entries and the qualification record they route to. No checker rule was added; K-12, K-82 and K-96 hold the entry's links, finding count and calibration row, and none holds its readings.

### Q37 · Upgrade the Sail switch to Sail 0.20.3

The Sail switch and [sail.lock](../../tools/opam/sail.lock) move to Sail 0.20.3 with OCaml 5.4.1. The switch export equals the lock, no package is pinned, and Sail/support-library licence readings are unchanged. Comparisons use the same sources at base `3184b0ed` on 2026-09-29.

Strict typechecking, the complete model build and its CTest tests passed. Both editions proved all SMT properties with byte-identical emitted SMT files. Generated C++ differs only in enum storage, hoisted temporaries and six tests that now execute calls previously constant-folded. The frozen profile validates against both schemas; 0.20.3 additionally closes option objects. The tracked model bundle reproduces a fresh emission. Existing build trees now bind the environment's Sail binary on every configure, and the bundle reader distinguishes compiler-carried `corelib.sail` from model and library sources.

The [canonical-term record](../assurance/canonical-machine-term.md) owns the emission identity. Normalized terms retain the same axioms/reference counts; types are byte-identical, with only a declaration relocation and two extern-name comments changing. The runs show no memory reduction. The support library's published package still excludes Rocq 9.3.0, and its source build there was not measured. Focused model/tool tests, type checks and selected K-78/K-88 mutations passed.

* Four findings.
  * **Every model build tree kept the Sail binary its first configure found, so a lock change left an existing tree emitting with the earlier compiler while its log and build receipt named the new one, and `emit` configured only a tree without `build.ninja`.** Closed here: the configure binds `SAIL_BIN` to the environment's `sail`, and `emit` configures every tree. F-500.
  * **Sail 0.20.3 hashes its compiler-carried `corelib.sail` under that bare name, which K-88's host half and the Sail context tool read as a model source the checkout lacks.** Closed here by `sailbundle.COMPILER_FILES`. F-501.
  * **At Sail 0.20.2 the constant folder evaluated six `$[test]` functions' calls at compile time, so the emulator's unit tests did not execute `fence_drains`, `setCapAddrChecked` or `capToMemBits` there.** The fence test's assertions compiled to `sail_assert(true, …)`; 0.20.3 emits the calls. Standing. F-502.
  * **Q36's restatement left the canonical-term record calling Rocq 9.2.0 the locked prover, inside both support-library releases' bound.** Closed here by restating it at 9.3.0. F-503.

Calibration: original estimate 7 h, range 4–10, class X; re-priced 7.5 h, range 4.5–10.5, for the configure repair. Actual 0.9 h, attended; hosted validation is outside it.

Landed: Tier A. The read covers the lock and its export, the release-archive reading, the three output comparisons and each named difference, the configure binding and the compiler-file class with their cases and mutants, the canonical-term record's restated identity against the emissions, the support library's re-read, the restated statements against the grep, and the four findings against their register entries. No checker rule was added; K-12, K-82, K-88 and K-96 hold the entry's links, finding count, regenerated bundle and calibration row, and none holds its readings.

### Q38 · Modernize and harden the proof corpus at Rocq 9.3.0

Q38a–Q38l hardened proof-source readers, qualified instrument switches, adopted Rocq 9.3 syntax and reduced proof-checking cost. Their entries below own evidence and estimates; the parent has no estimate or actual.

**Allocation.** Q38a/Q38d close gate settings and lexical bypasses; Q38b hardens other source readers; Q38c supplies elaborated-reading comparison; Q38e moves Stdlib-only instruments; Q38f/Q38g/Q38l settle QuickChick, the Wasm oracle and hosted switch validation; Q38h rewrites sources; Q38i/Q38j reduce evaluation cost and schedule checking; Q38k refuses coinductive forms affected by missing kernel fixes. An edit changing an elaborated statement, transparent body, opacity, assumption or witness returns to the requirement owner under [the portable proof workflow](../assurance/proof-assistance.md).

The finish predicate at `7eac8b19` required Q38f, Q38g, Q38h, Q38j and Q38l to land with no further child; all five landed. Q38i's comparison adds only its literals and lemmas. Q38h's final covering Guest CI run 36937812496 compares `28c26ec8` with `97ecd755` and finds no difference across all rewritten modules. Other children changed tools, harnesses, locks and guides. No existing statement moved.

No finding remains assigned to a Q38 child as its open owner. F-515 belongs to Q5b; F-566 requires a register act; F-596/F-598 remain reported and unclosed; F-626/F-630/F-701/F-713 have no item owner; F-704 shares F-496's act. Child entries retain the instrument, kernel and measurement qualification boundaries.

Landed: Tier A. The parent's closing decides that its finish line held and its allocation was carried out. The integrator's read covers:

* each child's entry and summary line, against the allocation retained above;
* the findings-register dispositions of the findings the children routed to one another;
* the cell's move.

No checker rule was added. K-12, K-82 and K-113 hold the entry's links, its presence for the landed parent and the cell's one summary line. None of them holds the entry's readings.

#### Q38a · Close the gate's Rocq 9.3 setting gaps and its prefix blind spots

The gate pins `Kernel Conversion Dep Heuristic` and `Default Proof Using`, reads settings/declarations after Rocq's command prefixes, and refuses `timeout`, `timeoutf` and `alloc_limit` as whole identifiers. Quoted attributes are read whole. Decorated records/statements still require witnesses; a failed witness declaration supplies none.

At `bf387669`, focused reader/cache tests and type checks passed; all changed-reader mutants were killed. Native probes confirmed the accepted bypasses. Live witness, setting, abstraction and dynamic-source readings were byte-identical to base `754969b3`. Five remaining lexical bypasses were routed to Q38d. The implementation changes invalidate proof and corpus reuse.

* Eight findings.
  * **The pinned-setting and `Timeout` readings, anchored at a sentence head, missed a setting after a bullet, brace or focusing selector, which the locked compiler keeps in effect beyond the proof.** Closed here by the shared prefixes. F-504.
  * **The machine-bound tacticals compile silently in forms a numeral-anchored reading passes: an Ltac identifier argument, Ltac2's first-class `Control.timeout` and `Control.timeoutf`, and a comment between the word and its argument.** Closed here by refusing the whole identifiers. F-505.
  * **The attribute prefix stopped at a `]` inside a quoted value, hiding a decorated statement from the witness scan and a `warnings` attribute from the pinned reading, and the base pattern was quadratic in its input.** Closed here by reading quoted values whole. F-506.
  * **`strip_comments` drops a comment that holds no newline and so joins its neighbours: `Set(* c *)Kernel Conversion Dep Heuristic.` compiles with the flag on, and no lexical reading sees it.** Open: Q38d. F-507.
  * **`sentences` splits at a full stop inside a string literal, so an attribute note such as `note="see x. y"` hides the statement it decorates from the witness scan and a `warnings` attribute after it from the pinned reading.** Open: Q38d. F-508.
  * **The witness scan's definer table lacks `Remark` and `Proposition`, which its statement table lists, and `Property`, so a statement under any of them never quantifies.** Open: Q38d. F-509.
  * **`Load` of a file outside `proofs/` runs commands no lexical reading sees, and the gate only withdraws cache reuse for it.** Open: Q38d. F-510.
  * **`Ltac2 @ external` binds a plugin primitive, the timeout tactical among them, under any name, which no lexical refusal can follow.** Open: Q38d. F-511.

Calibration: original estimate 3 h, range 2–4, class I; actual 2.2 h, agent-parallel. Hosted validation is outside it.

Landed: Tier A. The integrator's read covers the whole diff of the two gate modules against the cell, the review's ten findings and the repair's dispositions, the ratified widening of the prefixes, and the five findings routed to Q38d. No checker rule was added; K-12, K-82 and K-96 hold the entry's links, finding count and calibration row, and none holds the readings, which the host tests hold.

#### Q38b · Make the proof-source readers outside the gate refuse what they cannot read

The apex, memplan, mutate, consttab and CIC corpus readers read decorated declarations or refuse unsupported shapes by name. Completed-record values and `Fail`/`Succeed` follow each reader's contract. The memory-plan reader still cannot read an inline `build_plan` application or alias; F-515 routes missing exported values to Q5b.

At `fea51b48` and integrated `d54ff530`, focused reader/consumer tests, type checks and derived-fact checks passed. Selected checker mutants and all review mutants were killed. Compared with base `754969b3`, live facts, memory-plan export, mutants, table values, declaration counts and dated campaign selections were unchanged. Four lexical issues were routed to Q38d; the corpus-reader change invalidates older reports.

* Eight findings.
  * **The memory-plan reader dropped a plan value completed from a base with `with` when its type was not written, or when a comment held a `match` or a full stop, at the base and at the first head.** Closed here by refusing every value completed from a base that assigns a field of `Plan`, read over the file with its comments blanked. F-512.
  * **The first head read a `Fail`, `Succeed` or other decoration on a line of its own above a declaration as absent: apex read the definition as live, memplan and consttab read it as kept, and mutate opened no region at it; the corpus exporter counted declarations under `Fail` and `Succeed`.** Closed here in each reader. F-513.
  * **mutate opened a region at a Rocq line whose first character lies inside a comment or a string, a column-0 `Definition` inside a comment among them, at the base as at the first head.** Closed here; the live tree has no such line. F-514.
  * **The memory-plan export carries neither `interior_empty_region_plan`, which applies `build_plan` to two inline `cons` chains, nor `witness_Plan`, an alias, and no finding recorded either absence.** Open: Q5b, whose comparison reads the export. F-515.
  * **apex and memplan look back for a decoration over text whose comments are blanked and whose strings are not, so a string holding a full stop between a decoration and its command ends the look-back early and the command reads as undecorated.** Neither `ApexTheorem.v` nor `MemoryPlan.v` holds such a string. Open: Q38d. F-516.
  * **The decoration grammar is spelled once in each of apex, memplan, mutate, consttab and the corpus exporter, beside the gate's `CONTROL_PREFIXES`, where the tool guide's convention writes a parse once; its natural owner, `vos/proofs.py`, is a gate module that Q38b's cell did not own.** Open: Q38d. F-517.
  * **mutate's region keywords omit `Variant`, `CoInductive`, `CoFixpoint`, `Structure` and `Let`, so a line opening with one joins the region above it, and a rewrite of an `Inductive` as a `Variant` would move a region silently.** Open: Q38d. F-518.
  * **K-91's reader in `keccak.py` ends an `Example` at the next column-0 `Proof.`, so a `Proof using` line or a decorated `Example` fails K-91 loudly, but for a wrong stated reason.** Open: Q38d. F-519.

Calibration: original estimate 5 h, range 3–7, class I; actual 3.3 h, agent-parallel. Hosted validation is outside it.

Landed: Tier A. The integrator's read covers the whole diff of the five readers against the cell, the review's findings with their reproductions, and the repair's dispositions. It also covers the one knowingly unread shape, which F-515 routes to Q5b, and the four findings routed to Q38d. K-42, K-43, K-44, K-88 and K-107 hold these readers' outputs over the live tree. The host tests hold each reader's reading or refusal of each form.

#### Q38c · Read the whole corpus's elaborated meaning for comparison

`run.py proof-reading` records and compares elaborated meaning under the [reading schema](../../tools/proof-reading.schema.json). It reads only receipt-bound staged objects or sources it compiles itself, refuses stale/changed inputs and malformed output, and compares statements, transparent bodies, opacity, universes, inductives and membership. Provenance is recorded separately.

Two whole-corpus reads of base `754969b3` were byte-identical. Native controls detected tested meaning changes and accepted comment edits, opaque-script changes and the three intended syntax rewrites. At `3f403305`/`4223154f`, focused host/guest tests, type checks and derived-fact checks passed; all reader/receipt mutants were killed.

Comparison requires one installed library set. Digest checks at both ends do not exclude a concurrent gate restoring identical bytes mid-read. This whole-corpus comparison implements no part of the [statement freeze](../assurance/proof-assistance.md#statement-freeze).

* Five findings.
  * **The first head's `--objects` route read any directory's objects and recorded the sources beside them as their provenance, so an object older than a changed source was certified as that source's meaning.** Closed here by reading only a compile that passed: the gate's, bound to its receipt's digests, or one the command makes from the sources it is given. F-560.
  * **Rocq 9.3 names the fresh universe levels a query's `Check` gives a universe-polymorphic constant after the query file and a counter over the whole process, so a batched reading must rename them.** The corpus has no universe-polymorphic constant, so only the fixture exercises the renaming. F-561.
  * **Under `Set Printing Universes`, About states template polymorphism as `on <levels> (cannot be instantiated to Prop)`.** 52 corpus symbols carry that sentence. The CIC corpus exporter does not set the flag, and it still reads the shorter sentence. F-562.
  * **The reader's identity binds the prover banner and digest, the query flags and the settings, but not the installed library set that `run.py proofs` binds.** A base and a candidate reading compare only when both are taken against one installed library set. F-563.
  * **Two compiles of the identical 57 sources with identical flags, one under load and one idle, produced different `ElasticDomain.vo` and `MemoryPlan.vo`, while the other 55 objects and both readings were identical.** An object digest is therefore no reproducibility identity for those modules, which is why the reading does not compare provenance. F-564.

The review's remaining nit, holding the gate's workspace lock during a default-route read, is not taken. The digest binding at both ends leaves unguarded only a gate run that rewrites and then restores byte-identical files mid-read.

Calibration: original estimate 8 h, range 5–11, class I; actual 3.7 h, agent-parallel. Hosted validation is outside it.

Landed: Tier A. The integrator's read covers the command's and the reading's whole code against the cell, and the review's findings with the repair's dispositions. It checked that the default route's binding matches what the gate's receipt records: `.vo` outputs and top-level `.v` inputs under `proofs/`. It also covers the documentation rows it added. No checker rule holds the reading; the host tests and native controls hold it.

#### Q38d · Close the lexical bypasses the Q38a and Q38b reviews routed

The gate and proof-source consumers share one [lexer](../../tools/vos/proofs.py) for comments, strings, sentence endings and decoration prefixes. Comments separate tokens; strings and recursive `..` no longer split sentences. The gate refuses unreadable notation tokens and dynamic sources before compilation, and recognizes `Remark`, `Proposition` and `Property` as statements. Consumer look-backs, region keywords, K-91 and proof citations use the same grammar.

Native probes and positive controls established bypass readings/refusals. At integration onto `5857a2d5`, all live consumer readings were unchanged, including memory-plan output, mutants, citations and tables. Focused tests, type checks and selected checker mutations passed. The second round killed all hand mutants; the first had one equivalent mutant. Proof and corpus implementation identities changed.

F-596/F-598 remain reported and unclosed because repair would re-baseline mutant populations. F-597's multiline-string declaration shape is absent from the live tree; advisory `proofsearch` still has its own decoration prefix.

* Twelve findings.
  * **The first round's string-aware split let a declared token holding a quote or `(*` hide a later setting, Load or statement, which the base had refused.** Closed here by the declared-token refusal. F-588.
  * **The control prefixes needed a blank after a control word or a quoted target.** So `Time#[local]Set`, `Redirect"out"Load` and `Profile "a""b" Set` compiled with the setting unread. Closed here. F-589.
  * **The shared split ended a sentence at stdpp's `∀..`, and at a declared token ending in a full stop, `.` and `...` among them, losing the witness demand after it.** Closed here. F-590.
  * **The token refusal reads only a source's own declarations.** Its soundness rests on the audit of the installed switch, and it refuses loudly a declaring string holding a word that ends in a full stop. The audit is recorded, and the over-refusal is loud. F-591.
  * **The shared decorations read a control flag before a bullet, brace or goal selector as the following declaration's.** The locked compiler runs it as the brace's. Closed here. F-592.
  * **The second round's first cases for F-516 and F-518 passed their own regressions.** F-518's iterated the table under test, and F-516's put the flag in the head's own run. Closed here by cases that spell the keywords and pin both call sites. F-593.
  * **mutate's region keywords had no word boundary, and it read heads line by line.** So `Letter` opened a `Let` region, and a decoration reaching its command through a comment or a multi-line attribute was misread. Closed here. F-594.
  * **apex ended a definition's body at a string's full stop before a capital on the next line.** It silently dropped a consumer's read. Closed here. F-595.
  * **mutate's definitional region ends at the next keyword line rather than at its own full stop.** So a definition inside a proof makes the proof's later literals mutable, and so does a following `Compute` line. Ending regions at their sentence would re-baseline every proof's mutant population. Open: reported and not closed. F-596.
  * **apex and memplan read a column-0 declaration spelled inside a multi-line string of a non-Definition sentence as a declaration.** The live tree holds none. F-597.
  * **mutate's tables lag Rocq 9.3's grammar.**
    * Its region keywords omit `SubClass` and other defining vernaculars, among them `Module RingDma.` in RingContract.v, a live instance.
    * Its mutable set omits `Variant`, `CoInductive`, `CoFixpoint`, `Structure` and `Let`.
    * It reads `Export Set` as `Set`.

    Changing either table re-baselines the mutant populations. Open: reported and not closed. F-598.
  * **`proofsearch`, an advisory navigation reader outside the five readers F-517 names, still spells its own decoration prefix.** It validates nothing. F-599.

Calibration: original estimate 6.5 h, range 4–9, class I; actual 6.6 h, agent-parallel, excluding the overnight suspension and hosted validation.

Landed: Tier A. The integrator's read covers both rounds' whole diffs against the cell: the shared lexer and its refusals, the decoration grammar and every reader that now composes it, the keyword tables, the tests and cases, and both reviews' findings with their repairs' dispositions. It also covers the round-1 publication and this integration's merge and consumer comparison. Every consumer of the shared lexer reads the live tree as it did, and each finding the cell names is closed by a reading the host tests hold.

#### Q38e · Compile the Stdlib-only Gallina instruments in the proof switch

Stdlib-only `quickchick vectors`, `quickchick freeze`, `kernel vectors` and enumerative `seed coq` compile in the proof switch. `quickchick properties` compiles only its harness closure. **K-117** derives instrument switches/source reach from their owners and refuses newer syntax in sources compiled by older provers.

Against base `59cc31c3`, vectors and selected mutant verdicts were byte-identical; kernel/freeze checks passed. The property harness passed in its then-current Rocq 9.1.1 switch. Focused host/guest tests, type checks, derived-fact checks and selected K-100/K-117 mutants passed at integrated `ab90626a`.

K-117 deliberately over-refuses three older-compatible `&` forms absent from the live tree. QuickChick fallback/header issues went to Q38f and the undeclared oracle release to Q38g. Generated vectors establish their comparison predicates; instrument compatibility remains a separate boundary.

* Six findings.
  * **K-117's first head passed 16 `&` binders that Rocq 9.3.0 compiles and 9.1.1 rejects, inside record, class and instance braces and sigma bodies, and paired each rig module with its switch by hand.** Closed here by the brace and binder-list reading, checked against 63 probes compiled under both releases, and by reading each module's prover calls. F-567.
  * **K-117 opened a sentence at the second dot of `..`, so an `if` before a recursive notation's `..` left its `is` unrefused.** Closed at integration. F-568.
  * **`compare_component.py` names its switch but states no Rocq release, so K-117 holds its row older than 9.3.0 by its fail-closed default rather than by a release it reads.** Open: Q38g, whose declared switch gives it one. F-569.
  * **`quickchick properties` and `quickchick check` fall back to the CertiRocq switch at Rocq 9.1.1, so K-117 carries a second 9.1.1 row over Properties.v's closure, and `seed coq --quickchick` still compiles every proof source at 9.1.1.** Q38f's Check expects no row below 9.3.0 but the Wasm recipes and the lowering, which holds only once the fallback and its row go. Open: Q38f. F-570.
  * **Vectors.v's header still says Properties.v needs an install this repository has not made, and Properties.v's header names the undeclared switch `quickchick-9.1.1`.** Open: Q38f, which owns those headers' QuickChick claims. F-571.
  * **K-117's lexical reading refuses the intro patterns `(H & H')` and `as (a & b)` and a `&=` notation token, which Rocq 9.1.1 and 9.3.0 both compile.** The live set holds none, and the rule's docstring and registry row state them. F-572.

Calibration: original estimate 6 h, range 4–8, class I; actual 3.4 h, agent-parallel. Hosted validation is outside it.

Landed: Tier A. The integrator's read covers the whole diff against the cell: the switch move, the narrowed closure, K-117's module, registry row, selftest cases and tests, the restatements, the review's findings with the repair's dispositions, and the merge's resolution and repair. K-117 holds what the instruments older than Rocq 9.3.0 compile, and the host tests hold the switch each instrument asks for.

#### Q38f · Run the property harness at Rocq 9.3.0

[quickchick.lock](../../tools/opam/quickchick.lock) records the hosted export for `verifiedos-quickchick-9.3.0-ocaml-5.4.1`, with the three commits selected by Rocq V9.3.0's overlay. The harness walks small finite domains, uses truncating `Nat.sub`, fixes seed 20260930 and makes no shrinking claim. Seed journals compiles and leaves resource-limited/signalled runs undecided under the owner's scoring rule.

The three closing runs tested `a00a5538`:

* [36931493979](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36931493979) built the recipe, passed all drawn/walked sets, and re-imported its export on a second runner with equal packages and pins.
* [36931499615](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36931499615) confirmed each of the base's 33 verdicts under truncating subtraction.
* [36931504555](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36931504555) compared base `b22f44a1` with two candidates: every sampled verdict agreed, with 12 killed and 8 survived, none stillborn, unseeded or undecided. The comparison qualifies that sample and records its survivors.

`instrument-ci read` accepted all three as closing evidence with unchanged route inputs. Focused tests, type checks, derived-fact checks and selected rule mutants passed; Host CI passed on Windows/Ubuntu through closing merge `384e19a8` (36936375737). The hosted recipe condition was met. Rocq 9.1.1 QuickChick is absent from current recipes/statements; dated reports remain verbatim under the [retained-evidence guide](retained-evidence/README.md). The owner accepted that evidence exception to the literal retirement clause. K-117 still protects the older Wasm oracle and Rupicola source sets.

* Retained: [`out/instrument-ci/36931493979/artifacts/instrument-join-a00a5538733b989690b18ec4f3a7dda34569b0ef/report.json`](retained-evidence/out/instrument-ci/36931493979/artifacts/instrument-join-a00a5538733b989690b18ec4f3a7dda34569b0ef/report.json), SHA-256 `b6e9b346b1c67592875fa257fe375feadde1d3cf7532e2ef1160d9484615da3b`.
* Retained: [`out/instrument-ci/36931499615/artifacts/instrument-join-a00a5538733b989690b18ec4f3a7dda34569b0ef/report.json`](retained-evidence/out/instrument-ci/36931499615/artifacts/instrument-join-a00a5538733b989690b18ec4f3a7dda34569b0ef/report.json), SHA-256 `9f2073a643409a09e6b85c844b5dbd07b86eb8a3cee2987f2adeb7acb87b1f98`.
* Retained: [`out/instrument-ci/36931504555/artifacts/instrument-join-a00a5538733b989690b18ec4f3a7dda34569b0ef/report.json`](retained-evidence/out/instrument-ci/36931504555/artifacts/instrument-join-a00a5538733b989690b18ec4f3a7dda34569b0ef/report.json), SHA-256 `2a34d0efcddf6c0debec47210dd4c9a4217e69c5c2e6764f79a2717da43d0162`.

* Eighteen findings.
  * **Q38l's join read seed's `-- ` notes as part of the verdict before them, and its closing-line pattern and shortfall count missed the undecided mutants the closing line counts.** `51c65691` skips the notes and completes a step when its decided and undecided mutants count every one its head picked. F-623.
  * **No contract stated what a run with an undecided mutant exits.** It exits 1, as a run with a survivor or an unseeded mutant does, and Q38l's route reads the journal rather than the exit. F-624.
  * **`seed coq`'s enumerative mode shares the journalling, so it also journals each compile and leaves a stopped compile's mutant undecided, beyond the Owns' `--quickchick`.** Its verdicts are otherwise unchanged. F-625.
  * **`quickchick properties`, `vectors` and `freeze` and `kernel vectors` stop with a traceback on a per-file timeout or a signal rather than a FAIL line naming the file and the cause.** Both fail closed. Open, owned by no item. F-626.
  * **`RECIPE` and `INSTALL` pass `-y`, which also answers opam's root-format question.** Q38l's route runs them only over the fresh root its bootstrap creates, and the guides keep `provision --apply`'s import out of the local guest. F-627.
  * **A stopped Gallina compile left QuickChick's extracted program running, which loaded every later compile's timing.** `67472e21` ends the compile's whole process group. F-628.
  * **A drawn set whose program built and then crashed scored its mutant stillborn.** Under the owner's ruling, an ordinary exception kills the mutant; resource exhaustion, a signal or a status the reader cannot classify leaves it undecided; a program that did not build stays stillborn; and a prover a signal ended leaves its mutant undecided. `176015d5` and `7e41851b` implement it. F-629.
  * **Nothing checks each walk's printed point count against the domain size Walks.v's header records, so a walk that skips a point still passes.** Open, owned by no item. F-630.
  * **A proof refusal earlier in a run's compile waves is dropped when a later compile is ended by a signal or the per-file limit, leaving the mutant undecided rather than killed.** It errs toward undecided, the ruling treating a signal as the limit is treated. F-708.
  * **seed.py's comment said a refuted set kills the mutant however the run ends, while a drawn compile stopped at the per-file limit is undecided before its output is read.** `23d80862` narrows it. F-709.
  * **No test held gallina's reading of GNU time's signal line, both signal cases using a status above 128.** `f0e87ba8` holds it with a status below 128. F-710.
  * **The drawn-set reader's message shapes, read from QuickChick 2.2.0's plugin source, are held only by tests on synthetic output.** Each seed job of run 36931504555 met its refutation shape, reading `plus-to-minus` at line 215 as killed on QuickChick's `*** Failed after 3 tests`; no crash, signal or unfinished program has met a run. F-711.
  * **The route's join keys a mutant by its file, line and rewrite, so two sampled mutants on one line with the same rewrite would collapse into one identity.** The sample of `CyclicExecutive.v` held no such pair. F-712.
  * **A seed step whose baseline compile reaches gallina's per-file limit reads as failed rather than undecided, seed journalling the stopped baseline as no baseline and closing on none.** The subject's baselines compiled far below the limit. Open, owned by no item. F-713.
  * **S13a's note says the randomized half runs under QuickChick "with the counterexample shrinking no enumeration has", while `forAll` never shrinks.** S13a's note stays as recorded, and `a269146c` removed every current-state claim that the harness shrinks. F-714.
  * **The Check required that no tracked file outside the completion log name the retired switch, while the route's landing rule retains report copies that record the switch each run found, among them Q38l's control and this item's install and seed-base runs.** The clause is unmet as written; the integrator, as Q38f's owner, reads it as excepting retained evidence, every tracked recipe, constant, lock, test fixture and current-state statement naming the 9.3.0 switch. F-715.
  * **The closing diff may not touch seed.py, a route input, so seed.py's `--recipe` help still describes the recipe's switch as other than the provisioned one.** `e4a71a14` restates it after the closing landing. F-716.
  * **The replayed conditional commits carry the guest-built candidate lock until `73329e78` replaces it with the hosted export, so a guest lock sits in the closing merge's second-parent history, which the Owns' never-tracked rule did not foresee.** No revision on `main`'s first-parent line carries it, and the two locks differ only by `dune.3.23.1` among the roots. F-717.

Calibration: original estimate 10 h, range 7–13, class I; re-priced 11.5 h, range 8–15, for hosted builds. Actual 10.6 h, agent-parallel; integrating orchestration and runner time are outside it.

Landed: Tier A. The lock guide's amendment admitting commit pins is a new normative claim. The integrator's read covers the whole diff against the cell: the recipe, the lock bytes against the run's artifact, the walks, seed and journalling, the scoring under the owner's ruling, the conditional commits as replayed and the seed.py hunk they leave out, the restated guides, rows and tests, each review's findings with its repair's dispositions, the route's repairs, and every artifact of the four runs against their receipts and `report.json`.

#### Q38g · Settle the switch the Wasm oracle keeps

[certirocq.lock](../../tools/opam/certirocq.lock) declares unpatched CertiRocq 0.9.1+9.1 over Rocq 9.1.1 with OCaml 4.14.4. The local-built switch export equals the snapshot. A fresh-root import installed the same closure; setting its compiler invariant restored a byte-identical re-export.

Demo/IPC Wasm checks passed in the built and imported switches, and the seeded twin failed in both; all modules were byte-identical between switches. `provision` accepted the oracle fact; its overall fresh-root check failed only for the three other absent switches. `compare_component.py` checks the release exactly and labels a switch declared only against the snapshot's package closure.

Checks ran once locally under the user's 2026-10-01 ruling; no hosted runner built/checked CertiRocq. Licence incorporation is bounded by [THIRD-PARTY.md](../../THIRD-PARTY.md), including research-use-only local builds. The Docker build was unexercised on aarch64, and `provision --apply` plans no oracle installation. Focused tests, type checks, derived-fact checks and K-117/K-118 mutations passed at `a6c81a4a`.

* Sixteen findings.
  * **CertiRocq's `plugin/static/camlrocq.ml`, the copy `certirocq_plugin.cmxs` packs, offers `GPL-2.0-or-later` or the INRIA Non-Commercial License Agreement, not the `LGPL-2.1-or-later` the first reading gave every printer file.** THIRD-PARTY.md names each file's GNU option, and running them carries no condition under either. F-601.
  * **The host case for the oracle's candidate recipes passed ten mutants its docstring excludes.** A development repository, an `opam install .` or `opam switch import` step, a pin spelled after a global option and an install into another switch each passed. The case now holds each recipe to the released repository and the default alone and to installs of released versions into its own switch, killing all ten and the lane's six. F-602.
  * **The conditional CertiRocq licence row repeated the LGPL reading of `camlrocq.ml` and named neither Coq's `theories/ExtractionVanilla/` files nor Rocq's `benchmarks/lib/Makefile`, both `LGPL-2.1`, beside the OCaml runtime headers it named.** `ec052b59` names every non-MIT file group in the archive with how each reaches the build. F-603.
  * **The messages of the lane's `e4c0a26b` and `6312d09c` describe a hosted run of the oracle's checks, a route the user's ruling withdrew before their merge.** The merge's message records the withdrawal, and `796744cd` states the ruling. F-604.
  * **CertiRocq's package compiles and installs `libraries/CpdtTactics.v` under `CC-BY-NC-ND-3.0`, whose text does not say whether a compilation to `.vo` is an Adaptation.** Every CertiRocq build in the guest since M1.5 has reproduced and compiled it. The user's ruling of 2026-09-30 accepts local builds for research use with nothing distributed, and none runs on a hosted runner. F-605.
  * **The guest's wall clock read about 20 h 06 m behind until about 21:10 on 2026-09-30 and then jumped forward.** A guest timestamp before then, and a wall-clock duration across the jump, are wrong; the 4.14.4 candidate's 7,463 s is the progress log's 79,856 s corrected for the jump. F-606.
  * **The 5.1.1 candidate's switch name was `ORACLE_SWITCH`'s own and is an existing switch's in the guest's default root, so that candidate's recipe cannot create its switch there.** gallina.py's comment requires a root that does not already hold the switch, and `ORACLE_SWITCH` names the 4.14.4 switch. F-607.
  * **The default root's `verifiedos-certirocq-0.9.1-ocaml-5.1.1`, which `ORACLE_SWITCH` named, carries no `rocq-certirocq`, so `provision`'s CertiRocq fact could not hold there.** `ORACLE_SWITCH` names the 4.14.4 switch, whose fact `provision` read as holding over the fresh root; the default root holds no switch of that name, and `provision --apply` plans nothing for it. F-608.
  * **The Check's Wasm checks, fresh-root import and `provision` reading could not be decided under the user's rulings of 2026-09-30.** The user's ruling of 2026-10-01 ran them once in the local guest, where each passed. F-609.
  * **MetaRocq's archive carries five files under terms other than its MIT licence: `bytestring.v` under `LGPL-2.1` with BedRock Systems' exception, whose text it does not carry, `LibHypsNaming.v` under the LGPL version 3, `MR_ExtrOCamlInt63.v` and `MR_ExtrOCamlNatInt.v` under `LGPL-2.1` and `CanonicalTries.v` under `BSD-3-Clause`.** `bytestring.v`'s extraction is packed into the plugins every oracle run loads. `464ec037` names each in the MetaRocq row with how it reaches the build. F-634.
  * **The snapshot's other new archives compile, run or install files under terms their top-level licences do not state, in ppxlib, base, elpi, re, linenoise, mdx, ocamlbuild, yojson and Flocq.** `bf681e77` names the built groups in their rows and, for completeness, the files no package target builds. F-700.
  * **The rows this item only restated, OCaml's compiler, the Rocq prover, dune, Zarith, Menhir and CompCert, rest on their archives' top-level licence files, while those archives carry other in-file terms.** Their census is owed and owned by no item. F-701.
  * **CertiRocq's release archive carries `benchmarks/lib/SqlQueries3.v`, whose header says it is not open source and grants its use as a benchmark to the CertiRocq project alone.** Nothing builds or installs it, while every CertiRocq build downloads and unpacks it, each a local build under the user's ruling of 2026-09-30, and the CertiRocq row records it. F-702.
  * **`compare_component.py` accepted `9.1.1.1`, `9.1.1+dev` and `9.1.1~rc1` as Rocq 9.1.1 and labelled a run's switch declared by its name alone.** `a6c81a4a` reads the release exactly and labels a switch declared only when its export installs the snapshot's packages, and `test_compiler_component` holds both. F-703.
  * **The imported switch's own export omits the lock's `compiler:` section until `opam switch set-invariant` sets the built switch's invariant, after which it reproduces the lock byte for byte.** F-496 met on this lock; the lock guide states the form. F-704.
  * **`fd46e3a7`'s message makes its merge conditional on a hosted run and a lock taken from that run's artifact, a route the user's rulings withdrew.** The tracked lock is the local export, no hosted runner built or checked CertiRocq, and the records commit's message says so. F-705.

Calibration: original estimate 5 h, range 2.5–7.5, class I; actual 4.5 h, agent-parallel. The suspended candidate build and hosted validation are outside it.

Landed: Tier A. The item declares a new project switch and tracks its lock, which THIRD-PARTY.md, K-117, K-118, `provision` and `compare_component.py` read, and its Check rests on measured guest runs rather than a rule. The integrator's read covers the whole diff against the cell: the lock bytes, the restated guides, the licence rows and their census, the registry rows, `compare_component.py`'s release and scope readings and their tests, the review's findings with the repair's dispositions, and both merges' resolutions.

#### Q38h · Write the proof sources in Rocq 9.3's syntax

The rewrite adopts Rocq 9.3 source forms across 40 authored modules while preserving elaborated meaning. `seed coq --quickchick` compiles only the harness closure. Guest CI/fanout accept a validated ancestor `reading_base` and compare elaboration under one proof environment. Workflow guards prevent checked-out commands after refused dispatches; step limits leave reporting margin.

Final covering [Guest CI 36937812496](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36937812496) passed both lanes at `97ecd755`, comparing all rewritten modules with `28c26ec8` with no elaborated difference. Earlier covering runs 36884798806, 36907415013, 36924383823 and 36926000222 also passed/found no difference; 36884798806 was cold/fresh. Host CI passed on Windows/Ubuntu for every batch through 36937517740 at `97ecd755`. Instrument run 36938124707 passed the rewritten property closure in locked QuickChick and reproduced packages/pins on import. No proof gate, reading or instruction measurement ran locally.

Final host readings, dependency graph and mutable-region identities agree with base `feb70969`; the memory-plan export changes only its source digest. `ObjectRouter.v` loses eight boolean-pattern mutants when matches become `if`; other modules retain their populations. Q38i's literals, lemmas and VM-cast definitions are unchanged. Focused tests and selected mutants passed after integration; the earlier closure-lane baseline was undecided because newer syntax still reached the older QuickChick prover.

Scope preserves `EndpointIPC.v`, generated proof sources and dated anchors. `AttestedSession.v`, `MlDsa.v`, `StorageRecovery.v` and `SupervisionTree.v` remain whole because retained records bind their digests. `MemoryPlan.v` keeps its exporter-read match. `CopyRingService.v` keeps its Rocq 9.2 campaign prefix. Completed-record updates include projection, constant and application bases; or-pattern matches are admitted; collapsed tactics bind every hypothesis they read.

The six unexpressible forms remain: `(_ : nat)` binders in `charged_at_the_arrival`/`toggle_ops`, and repeated tactic windows across pre-focused goals in RotFirmware, InferenceAdmission and AdmissionPath. The Fixpoint exception preserves only the decreasing argument or the argument a recursive call receives as decreasing. A broader exception would restore 28 rewritten matches. These are recorded scope decisions. The syntax rewrite makes no measured performance claim.

Retained digest anchor: `AttestedSession.v` (`5de4430d…`) is bound by [`out/evidence/prereq-proof-evidence.json`](retained-evidence/out/evidence/prereq-proof-evidence.json) and the dated `mutate-results.json`.

* Fourteen findings.
  * **K-117 held every proof source while `seed coq --quickchick` compiled every one in QuickChick's Rocq 9.1.1 switch, so no authored source could take Rocq 9.3's syntax until that compile narrowed or QuickChick's switch moved.** Holding that compile to `Properties.v`'s `Require` closure left `PartitionContext.v`, `BoundaryCost.v`, `CyclicExecutive.v`, `EndpointIPC.v` and `RingContract.v` in the rule's set until Q38f's closing landing, and took out of that mode the nine sources outside the closure that depend on one of its members, which `seed coq`'s enumerative mode still compiles, at Rocq 9.3.0. Closed here: after Q38f's switch move the set holds no proof source but `EndpointIPC.v` and `RingContract.v`, and the three closure sources took the syntax. F-610.
  * **Q38i's retired-instruction procedure has no permitted site while guest runs are excluded, and Guest CI's wall times over the same sources vary by up to 71% between runs (F-612).** A cost claim about a rewrite that leaves every statement and transparent body as the base elaborated it, and Q38i's evaluation sites untouched, rests on that identity rather than on a figure. Standing. F-611.
  * **Guest CI's report step and Host CI's analysis, hook and report steps ran checked-out code under `!cancelled()` after the dispatch check refused a revision.** `5ec22789` runs each such step only when that check did not fail, and the checkout-guard test reads the condition in both workflows. Closed. F-637.
  * **Guest CI's model lane stated step limits summing to 365 minutes under a 360-minute job limit, so a run near them would be cancelled before its report and upload.** `e32755d8` restates the limits from the lane's measured durations with a margin for the report. Closed. F-638.
  * **The enumerative `seed coq` accepts a `--file` outside `proofs/` and fails at its first mutant, since its stage holds no copy of that file.** No current-state statement offers such a subject, and `--quickchick` refuses every subject outside `Properties.v`'s closure. Standing. F-639.
  * **The boot signature campaign's report step ran checked-out code under `!cancelled()` after its dispatch check refused a revision.** `42b1476f` makes each of its two checking jobs identify its check and runs the report step only when that check did not fail, and the checkout-guard test reads both jobs; the change to that workflow started its five-runner campaign once on push. Closed at `9c817113`. F-640.
  * **Rocq 9.3 checks an `Ltac` definition's hypothesis names when it reads the definition, so a body that names a hypothesis it does not bind, such as one `injection … as` introduces, is refused.** Each `Local Ltac` the rewrite adds binds the names it reads by its own intro patterns or takes them as parameters. Standing. F-641.
  * **The Owns let a lane rewrite `MemoryPlan.v` by regenerating the memory-plan export, while the Check held that export byte for byte, although the export records the source's MD5.** The Check excepts that `source_md5`. Closed. F-642.
  * **K-117's table does not read the dated Q19a review replay, `proofs/campaigns/q19a-render-cache.py`, which compiles `CopyRingService.v`'s prefix through `the_invariant_survives_every_interleaving` in a Rocq 9.2.0 switch it names at run time.** That prefix is a campaign anchor and stays as the base writes it. Standing. F-643.
  * **In `Keccak.v`'s `squeeze`, the constant-increment mutant of the `0` pattern, `if d - rate is 1`, compiles where the explicit match's mutant did not.** The population is unchanged; a later mutation run decides that mutant instead of counting it stillborn. Standing. F-644.
  * **In `MemoryPlan.v`'s `aggregate_demo_plan`, the constant-increment mutant of `slot_of`'s `0` pattern, `if r is 1`, compiles where the explicit match's mutant did not.** The population is unchanged at 679. Standing. F-645.
  * **Six forms meet a clause's letter that its target cannot hold in place: two `(_ : nat)` binders a named binder follows, which `&` would read as an application, and four repeated sequences reaching a goal a bullet or brace focused before they began, which no `Local Ltac` called where they start can reach.** The retained scope above names their owners. Standing. F-646.
  * **The rewrite lanes left twenty sites that met a clause by its letter for reasons the Owns does not give: bases that are projections, constants or applications, or-pattern first branches, and sequences whose bullet focuses the first goal their own tactic creates.** The read-only listing of the sources as of `5b4dafe0` found them; `q38h-rw9-20261001` wrote nineteen and `q38h-rw8-20261001` the twentieth, under the recorded scope decisions. Closed. F-647.
  * **The Fixpoint exception's "recurses on its scrutinee" admits a narrower and a broader reading.** The batch reads it as leaving only a match whose scrutinee is the enclosing Fixpoint's decreasing argument or what a recursive call receives as that argument. A broader reading, such as group 5's review's "any recursion on a part of the scrutinee", would return to `match` 28 matches inside a Fixpoint that the batch rewrote. Standing, the batch's reading stated. F-648.
* **Dispositions.** F-583 closes here: every literal, literal lemma and `vm_reflexivity` definition Q38i wrote is byte-identical to the base's, each lemma keeping its unfolded form. F-610's disposition is restated for the landed state, and F-646 to F-648 take theirs above.

Calibration: original estimate 15 h, range 10–20, class I; re-priced 19 h, range 13–25, for GitHub-only checks. Actual 16.4 h, agent-parallel. Contract restatement, parent records, integrating orchestration and hosted validation are outside it.

Landed: Tier A. Its Guest CI input and step and its `fanout` option are new normative claims. The integrator's read covers the whole diff against the cell: the narrowed compile, K-117's row and the `test_instruments` case; the dispatch check, the reading step, the report and `fanout`'s option, with their tests and restated contracts; the guard and limit repairs; every rewrite against its clause and the rulings above; each unwritten rewrite and left-whole source against its reason and the final grep; the host readings and mutant populations against the base; each review's findings with its repair's dispositions; and each covering run's comparison and digests against its log. No checker rule was added. K-12, K-82, K-96 and K-117 hold the entry's links, its finding count, its calibration row and the instruments' reach, and none holds its readings.

#### Q38i · Make the proofs cheaper to compile and recheck without moving a statement

Shared evaluated literals, single-evaluation VM casts and two tactic-context clears reduce checking cost. Against base `59cc31c3`, candidate `c559db3c` cut whole-corpus retired instructions 28.56% for compilation and 39.04% for kernel recheck. Every kernel summary was byte-identical; elaborated comparison names only the 14 added literals and their lemmas. No existing statement, transparent body, opacity or assumption moved.

The lane's proof gate passed without reuse, with every constant closed under the global context and no undeclared axiom. Live readers/campaign selections retained outputs; selected checker mutants passed. Source inputs match integrated sources apart from comments, with the settled revision rechecked by Guest CI.

Cast/literal clauses were narrowed where benefit was unmeasured, below noise, or regressive; dispositions are counted below. Literal lemmas must unfold before casting. Dated records stay unchanged. Small-module single-run instruction/peak variation cannot establish narrow thresholds; Q38j owns repeated peak sizing and Q38h preserves accepted evaluation forms.

* Ten findings.
  * **The cast clause and the Check's compile fall of more than 0.1% cannot both hold for ArithmeticComposition.v, CredentialHandles.v, InferenceAdmission.v and TwoSourceExtractor.v.** Their 16 such proofs evaluate goals too small for a fall beyond single-run noise. The cast also raised ArithmeticComposition.v's recheck by 2.78% and 2.80% in two single runs, past the 1% bound. The four modules keep their scripts. F-578.
  * **MlDsa.v's three such proofs stay unmade.** Two retained-evidence copies and a dated benchmark bind its digest, and no command regenerates a dated record. This is the clause's own exemption. F-579.
  * **Three proofs whose goals unfold to equalities keep their scripts.** These are `Disciplined demo`, `Disciplined demo_pr` and `Admissible demo`; the cast reads a goal's equality syntactically. F-580.
  * **HmacDrbg.v's `pr_true_run` and `first_draw` keep no literal.** With literals, the module's recheck counted 2,042.8e9 retired instructions against 2,019.9e9, but its one-run peak was 8,125,480 KB against 9,312,124 KB. Open: Q38j weighs the peak. F-581.
  * **Values that two Examples evaluate inside a `forallb` over a family keep no literal.** These are PqArith.v's ML-DSA-ring transforms of both probes, and StorageBridge.v's decode and walk of the medium flipped at offsets 272 and 144. Three round-trip Examples over the probes are not rewritten through the lemmas. Their benefit is unmeasured, beside the two modules' recheck falls of 20.44% and 28.77%. F-582.
  * **A literal lemma closed by a cast of `eq_refl` of its folded constant cost the recheck 2.5 and 6.2 times what unfolding it first costs.** Open: Q38h keeps the unfolded form. F-583.
  * **The 0.1% and 1% thresholds are decidable for modules under about 10e9 instructions only by repeated interleaved runs.** Single-run figures of unchanged small modules moved by up to 0.75% in compile and 0.62% in recheck between two sets. Open: Q38h and Q38j. F-584.
  * **A rerun of the dated ML-KEM mutation campaign's definitions-only compile would evaluate the seven literals under every mutant.** PqArith's proof oracle would then kill through the literal lemmas, although all 17 recorded selections name the same mutants. The campaign stays as recorded. F-585.
  * **The dated q19a render-cache campaign's review prefix of CopyRingService.v now carries the module's tactic and the cast.** Both of its anchors still resolve, and the campaign stays as recorded. F-586.
  * **`wait4` peaks of small `rocqchk` processes are unstable.** They read 129 to 131 MiB in two sets and 46 MiB in a third for the same modules. Sha256.v's rose from 1,458,428 KB to 1,626,180 KB at equal instructions. Open: Q38j repeats peaks before sizing workers. F-587.

Calibration: original estimate 10 h, range 7–13, class I; actual 5.3 h, agent-parallel, excluding the overnight suspension and hosted validation.

Landed: Tier A. The integrator's read covers the whole diff against the cell: every rewritten proof against the clause's shape, the literals and their lemmas, the clears, the reading comparison, the gate run, the reader invariants and the figures. It also covers the review's findings with their corrections, and the integration's prose repair. The narrowings this note names leave the cast and literal clauses partly met. Each is a finding with its disposition, and nothing here claims the cell's unnarrowed Owns. No statement, body, opacity or assumption moved.

#### Q38j · Schedule the proof gate by dependency and size its kernel workers from measured peaks

The proof gate schedules compile/audit work when dependencies finish, prioritizing the longest dependent chain. Unreadable dependencies retain the wave schedule; failed dependencies block consumers and remove stale objects. Each run logs its spans replayed under the prior schedule. The 10 GiB kernel budget rests on repeated runner peaks; a 16 GB runner admits one kernel/four compile workers. F-581's proposed literals buy no second kernel worker.

At `28c26ec8`, Host CI 36882333097 passed on Windows/Ubuntu and Guest CI 36883131989 passed both lanes. Compile/audit took 174.42 s against its own wave replay of 308.58 s. Cold/fresh Guest CI 36884798806 at `cb5a386e` passed both lanes and took 170.21 s against 303.29 s. Both peaks stayed under budget. The landed receipt and prior passing `8ef1da0b` receipt agree on inventories, dependencies, witnesses and empty declared assumptions. Focused tests/type checks passed.

Cross-dispatch wall times do not qualify scheduling benefit; the replay has the two biases recorded below. F-584/F-587 close through per-run replay and repeated peaks. The implementation change invalidates older reuse.

* Five findings.
  * **Three full rechecks of the same 57 sources on Guest CI's proofs runner, runs 36812890026, 36814984495 and 36819172207 at `1045acb9`, `2728d4a6` and `ae25ee8f`, took 152.67 to 246.83 s to compile and audit, 725.79 to 1,242.86 s to recheck and 1,032 to 1,745 s of user time.** A wall-time comparison between dispatches cannot decide a schedule change of about a tenth of a phase, so the Check holds each run to its own replay. Standing. F-612.
  * **On that runner the kernel checks every module in one worker, whose GNU time peak read 10,029,668, 10,030,124 and 10,029,820 KiB in those runs, 4.3% under the 10 GiB budget.** A uniform budget at or above that peak admits one worker on 16 GB, and only a per-component budget, which no item owns, could run two. Standing. F-613.
  * **A model weighting each module by Q38i's compile retired instructions puts a dependency schedule's compile phase 11.3% below the wave schedule's at the runner's 4 compile workers, and 22.1% below at the profiling guest's 12.** The compile and audit phase is 16 to 17% of a full recheck's wall time on the runner. Standing. F-614.
  * **The comparison of each run's compile and audit phase with the wave schedule replayed over its own spans leans both ways.** The phase carries the source analysis the replay leaves out, under a second, which disfavours the dependency schedule, while each span is measured with the workers more fully occupied than at a wave's end, which lengthens the replay and favours it. Standing, both leanings stated in `wave_makespan`'s docstring. F-635.
  * **With the priority this item ships, the longest chain of dependents first, the same model puts the dependency schedule at the 923.3e9 longest weighted chain, 28.9% below the wave schedule at 4 compile workers and 24.1% below at 12.** F-614's figures are a wave-then-name priority's. Standing. F-636.

Calibration: original estimate 5 h, range 3.5–6.5, class I; actual 0.8 h, agent-parallel. Contract restatement and hosted validation are outside it.

Landed: Tier A. The integrator's read covers the whole diff against the cell: the schedule and its fallback to waves, the timing lines and the replay, env.py's peaks, margin, worker counts and F-581's arithmetic, the restated statements, the tests, the review's findings with the repair's dispositions, and the two Guest CI runs and the receipt comparison. The schedule holds the wave schedule's verdicts and receipt fields with a shorter compile phase in both runs, and the budget holds every recorded peak.

#### Q38k · Refuse coinductive definitions while the locked kernel lacks the cofixpoint guard fixes

The gate refuses authored coinductive forms and notation declarations that could hide them before compilation while Rocq 9.3.0 lacks #22386/#22389 fixes. The same lexer protects machine-bound tacticals, and `proof-reading` repeats all source refusals. The [lock guide](../../tools/opam/README.md) owns retirement/residue through dependency sources, definitions, notations, tactics/hints and dependency-declared tokens.

Native guarded probes established refused spellings; no inconsistency reproducer was compiled. Live sources/campaign templates trigger no refusal. At integrated `82bf994d`, focused tests, type checks and derived-fact checks passed. Of 40 reader mutants, 38 were killed; two survivors had no distinguishing text in the bounded exhaustive differential. These results remove neither dependency-token residue nor the upstream defects. F-566 still requires a register-owned kernel-inconsistency response.

* Six findings.
  * **No requirements-register entry owns the response to a known inconsistency of the locked prover.** The audit's lexical refusals covering #22287, #22387 and #22510, and this item's for #22386 and #22389, stand on the lock guide's prose and the audit's code. R-05-018a's acceptance rests on the compile, the R-05-163 audit and `rocqchk`, which R-05-016a records as sharing the kernel's defects. Open: a register act at R-05-016a and R-05-018a rerunning the review gate. F-566.
  * **The first head passed a cofixpoint word joined to a token the source declares.** The locked compiler compiles `#_cofix`, `²cofix`, `٣cofix`, `₀cofix`, `#a1cofix`, `#a'cofix` and Ltac2's `Std.cofix_²sevens` to guarded cofixpoints, and Python's word boundaries read each as one identifier. Closed here by the ASCII word reading and the refusal of hiding declarations. F-573.
  * **The first head's numeral reading was held by no case.** 13 of the review's 14 mutants survived, and the reading missed `#00x1p5cofix` once a notation declares `#0`. Closed here by 15 probe-backed numeral cases and a decimal reading that stops before `0x`. F-574.
  * **A word joined to a token a dependency declares stays outside the reading.** After Stdlib's `+c`, the locked compiler reads `+c1cofix` as `+c`, `1` and `cofix`. The locked libraries declare 21 such tokens. The lock guide states it as the refusal's residue. F-575.
  * **The machine-bound tactical refusal passed `do 1timeout 5 (exact I)`, and `#_timeout 5 (exact I)` once a notation declares `#_`.** The locked compiler compiles both silently, so F-505's whole-identifier reading missed where the lexer ends a token. Closed at integration by `e554c96e`. F-576.
  * **`run.py proof-reading` repeated only the abstraction and pinned-setting refusals before compiling.** It would compile a copy holding an unreadable token, a coinductive form or a hiding token, or a loaded file, plugin or Ltac2 external. Closed at integration by `82bf994d`. F-577.

Calibration: original estimate 3 h, range 2–4, class I; actual 2.2 h, agent-parallel, excluding the overnight suspension and hosted validation.

Landed: Tier A. The integrator's read covers the whole diff against the cell: the refusal and its call site, the lexer model and the hiding-declaration reading, the tests and their cases, the lock guide's restated sentences, the review's findings with the repair's dispositions, and the integration's two repairs. The refusal holds every coinductive form an authored source writes or lets a declared token hide, the host tests hold each spelling the locked compiler was probed to accept, and the lock guide holds the residue and the retirement condition.

#### Q38l · Build and check the QuickChick switch on GitHub-hosted runners

The [instrument switch route](../../tools/ci/README.md#instrument-switch-route) builds, checks, exports and re-imports QuickChick on hosted runners, with validated inputs and retained receipts. It builds no CertiRocq input and performs no local QuickChick build/check.

Control [36900954975](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36900954975) passed at `5b4dafe0`: the then-locked Rocq 9.1.1 import passed all property sets, and a second runner reproduced package closure and byte-identical export. Seed jobs were skipped without a comparison base. `instrument-ci read` accepted unchanged route inputs as closing evidence.

Six plan-refusal runs started no later job: 36900981681 (short revision), 36900989559 (unreachable revision), 36900996043 (base equals revision), 36901002784 (non-ancestor base), 36901010152 (sample 21) and 36901017248 (missing recipe). Host tests held ref/build-choice refusals. Focused tests, type checks and derived-fact checks passed; K-75 killed all selected mutants. At `5b4dafe0`, Host CI 36899986247 passed on Windows/Ubuntu and Guest CI 36900715918 passed both lanes.

Recipe build, seed jobs, population listing and mutant join remained unexercised at this landing until Q38f. The sampler missed sub-minute peaks; F-706 routes repair to Q38f. Cross-host durations do not establish a performance comparison.

* **Retained.** [`out/instrument-ci/36900954975/artifacts/instrument-join-5b4dafe0404367b55f5d8a4968d8b35cf03acf4d/report.json`](retained-evidence/out/instrument-ci/36900954975/artifacts/instrument-join-5b4dafe0404367b55f5d8a4968d8b35cf03acf4d/report.json), SHA-256 `cf8d3f730ca665fafa9eccfc7082b452e3eea3f118e066b44f07799735d8de9b`. No step failed, so no failing step's log is retained.

* Fourteen findings.
  * **Q38f's conditional commits restate two inputs of this route, a comment in tools/vos/env.py and the header of tools/quickchick/Properties.v, which Q38f's closing landing may not touch beyond its lock, gallina.py, quickchick.py and provision.py.** Open: Q38f rewords both to hold before and after its switch moves and lands them with its unconditional commits. F-600.
  * **Seed's journal records no mutant's operator, so the join reads each one from the seed job's `seed list` listing of the same sample at the same revision.** The Owns names the listing. F-615.
  * **`run.py provision --apply` imports the QuickChick snapshot wherever its switch is missing, the local guest among them, where this route's Start builds and checks no QuickChick switch, and provision.py lies outside this item's Owns.** The tool guide, the route's contract and the lock guide state the import's exclusion from the local guest as the user's ruling. Open: Q38f, which restates `provision`'s QuickChick recipe. F-616.
  * **K-75 reads a job's interpreter only where the job installs one, so a job that installs none lies outside its sites.** Its registry row states the residue. F-617.
  * **The plan refuses more than the Owns first listed: a sample written with a sign or a leading zero, a recipe or `INSTALL` not declared as a non-empty literal, a base that is not a full commit, and a checkout other than the dispatching commit.** The Owns' plan clause names each. F-618.
  * **The import job's comparison and the seed jobs' population listing are steps the Owns did not name, each under an unmeasured 300 s limit, which the seed step's 10,500 s subtracts.** The Owns' limit clause names both. F-619.
  * **The reader refuses as closing evidence more than the Owns first listed: a run not completed or not passed, a build artifact with no export, a closing parent that is not the closing commit's first parent, and a route input that only the closing commit's own tree reaches.** The Owns' reader clause names each. F-620.
  * **GitHub may answer a dispatch whose `build` lies outside the input's choice before the plan runs.** The plan's build refusal is held by its host test, as its ref refusal is. F-621.
  * **The build job exports its switch with a plain `opam switch export`, so whether a `RECIPE` switch's export keeps the pins the import job compares is undecided.** Open: Q38f's first `recipe` dispatch decides it, and an export that loses them moves to `--freeze` under this route's contract. F-622.
  * **The Check's control precondition named gallina.py's later edits as the oracle's candidate switches and its opam environment alone, while `34c6595c` changed the closure readers `seed coq --quickchick` compiles through and Q38g moves the oracle's own switch.** Neither changes what the control runs, since `closure` reads the directory `quickchick properties` stages as `harness/`, and the Check names both. F-631.
  * **The route's import comparison ran under `!cancelled()` without its side guard as a conjunct, which F-637's rule, landed beside it, refuses.** The comparison carries the guard, and staging alone runs after a refused guard, reading the job's private root and no file of the side's checkout. `test_fanout_ci`'s refused-dispatch reading holds the route. F-632.
  * **The route also records a step undecided for its log's no-space report or gallina's per-file timeout, bounds each staged file and each artifact, refuses a non-regular file, records a job failed outside its wrapped steps, passes over an earlier attempt's artifact and refuses a receipt that disagrees with the plan, none of which the Owns named.** The Owns names each. F-633.
  * **The join's report and summary and the reader give a step's peak as the sampler's figure, which reads 0 KB for a step that ends before the sampler's first minute.** The control's `quickchick properties` read 0 there and 543,612 KB by GNU time, while the Owns makes that step's recorded peak the basis for raising seed's `--jobs`. Open: Q38f, which routes it, repairs the report under this route's contract before its first comparison dispatch. F-706.
  * **The plan accepts a `base_revision` dispatch whose side's seed.py binds no subject it can read.** That side's seed job builds its switch before its population listing refuses for want of a subject, so the run decides no verdict and costs only runner time. F-707.

Calibration: original estimate 9.5 h, range 7–12, class I; actual 4.8 h, agent-parallel. Shared integration is counted in Q38g; integrating orchestration, runner time and hosted validation are outside it.

Landed: Tier A. The route's contract is a new normative claim. The integrator's read covers the whole diff against the cell: the workflow and its guards, the plan, staging and join module, `bootstrap_instrument.py`, `instrument-ci` and their tests, K-75's sites and mutants, the route's contract and the restated guides and rows, both reviews' findings with their repairs' dispositions, the merges' resolutions, and every artifact of the seven runs against the receipts and `report.json`.

### Q40 · Re-derive the Fiat-Crypto field headers with the generator checked by the locked kernel

The [emission record](fiat-crypto-emission.md) binds the upstream pin, nested archives/licences, cold generator build under the locked kernel and reproducible field headers. Option A succeeded. Raw arithmetic bytes match the prior emission; only provenance wrappers move. No arithmetic byte was manually edited.

The Rocq 9.3.0/OCaml 5.4.1 build passed, switch exports were unchanged, repeated emissions/checks matched, and a second lane reproduced all header bytes from the same generator digest. That lane supplies no independent generator rebuild. The independent integer campaign passed all checks. Focused tests, type checks and selected K-88/K-81 live mutants passed, including refusal/repair paths. Final hosted handoff/retirement belong to fanout; pending Guest CI supplies no passing evidence.

Calibration: original estimate 5.5 h, range 3–8; retained planning weight, actual n/a. Complete session intervals are missing and cannot be reconstructed from build duration; calibration excludes estimate and actual. No product or repair remains identified. The shared closing allowance is counted once in Q39 and does not reconstruct Q40 actuals.

Landed: Tier A. The integrator read the driver and refusal tests against the
locked environment, source and output receipts; executed the independent lane's
real generator comparison; and read the incorporation, licensing and historical
pin scopes. The worker independently reviewed the shared license record and its
historical-manifest wording was corrected. Kernel-checked generator proofs do
not establish a proof of printed C, target refinement, timing or curve security.

### Q41 · Specify the environmental fault sensors and plan their characterization

[The environmental sensor contract](../hardware/environmental-fault-sensors.md) specifies supply-window, clock, replica/canary timing and direct optical families, a total instance map, immutable field ownership and one fail-stop boundary. Q41a owns implementation; Q41b owns process characterization. The contract adds no ISA/model state and preserves protected-model limits.

Campaigns require genuine negative controls, disabling/self-fault cases, refutation records and false-trip exposure. The source/licence reading binds OpenTitan `ae79548c0fb30c708ec3f870d4b462611ed87b4f` and Apache-2.0 headers; no source/physical result is incorporated. Process qualification remains open.

Focused document/whitespace checks passed at handoff `c9b043f638eb51204130a60495ed4dda5bfbd521`.

  * Finding: **The pinned OpenTitan structure supplies no VerifiedOS physical detector or immutable fail-stop qualification.** AST's secondary partition ties detector pairs inactive; software-selected sensor/alert policy does not establish this contract's boundary. Standing: source reuse is structural only, with actual cells and fail-stop implementation at Q41a and process-specific measurement at Q41b. F-784.

Calibration: original estimate 14 h, range 8–20; retained estimate, actual n/a · agent-parallel. Discovery and complete author/review intervals are missing; the partial interval is not a full actual and is excluded from measured calibration.

Landed: Tier A. The integrator read the entire contract, source-family and coverage limits, inventory/field ownership, fail-stop and no-architectural-state clauses, campaign controls and both implementation predicates. The process qualification remains open; the settled hosted handoff is recorded by fanout.

### Q42 · Author the backup and device-migration contract

[The backup and migration contract](contracts/backup-migration.md) maps all requirement criteria to acceptance cases. Export reaches only recursively rollbackable DataOnly state; Fresh regions, keys and credential/sealed authority remain excluded. Restore authenticates/plans the whole object before writes, stages beside old state and publishes atomically. Fresh initialization/counters prevent authority revival.

Migration binds mutual appraisal, channel credentials, receiver roots and source confirmation under explicit relay/compromise premises. It permits no persistent migration object or recovery display and retains surrendered-freshness residue. Q42a/Q42b/Q42c own realization/proof. Inventories record absent wire descriptors and owed crown-jewel members. No codec, implementation or mechanized migration theorem is claimed. Focused document/whitespace checks passed; no register/specification pair changed.

Calibration: original estimate 12 h, range 8–16; retained estimate, actual n/a · agent-parallel. Discovery and complete author/review intervals are missing; the partial interval is not a full actual and is excluded from measured calibration.

Landed: Tier A. The integrator read the whole contract against its requirement criteria, particularly export authority, consent-record freshness, authentication/schema zero-write outcomes, crash publication, trusted holder operations, mutual session binding and all three implementation predicates. Focused document and authored whitespace checks passed at handoff `3143a2c620fff3e60065ec95e0f9ca5138d35cf4`, based on `b238c3c5f8c216efa85ec0f413868e810a6aeeb8`; the settled hosted handoff is recorded by fanout. No backup implementation or physical/proof gate result is claimed by this contract landing.

## M0 · Hardware reference

### M0.1 · Pin upstream models

  * `sail-riscv` was pinned at `beaf4499` and `sail-cheri-riscv` at `bb07488d`, with vendoring baseline `8f91355e`. Applicable upstream fixes were carried into the curated model; excluded extensions and deleted targets were declined.

  * Finding: the CHERI tree embeds older `sail-riscv` commit `b748a82`; reconciliation therefore requires a semantic transplant, not configuration of one shared base.

### M0.2 · Stand up the Sail toolchain

  * Established the Sail 0.20.2 environment on WSL Ubuntu 26.04 with OCaml 5.4.0, opam 2.5.0 and z3 5.1.0. Typechecking agreed across the three tested solver versions; the Sail emitter version was pinned for fidelity.

### M0.3 · Build stock `sail-riscv` baseline

  * Built the stock `sail_riscv_sim` baseline out of tree; 664/664 tests passed.

### M0.4 · Build stock `sail-cheri-riscv` baseline

  * Built `cheri_riscv_sim_RV64` against embedded `sail-riscv` commit `b748a82`; 229/229 bundled RV64 tests passed. This baseline supplied the capability-semantics oracle.

### M0.5 · Reconcile the baselines

  * Selected modern `sail-riscv` as the base and transplanted the CTSRD capability layer. Later reconciliations carried applicable fixes while retaining the frozen ISA and locked toolchain. The curated model passed strict typechecking and its documentation bundle was regenerated. [THIRD-PARTY.md](../../THIRD-PARTY.md) owns the reviewed upstream references.

### M0.6a · Stand up the curated tree

  * Vendored the curated `model/` tree byte-identically from `8f91355e` with LF preserved. The out-of-tree build and all 664 tests passed.

### M0.6b · Measure configuration-level curation

  * Captured configuration-supported profile rows in `verifiedos.json`. The adopted-family run passed 132/134 tests; the other two were expected profile refusals. Configuration identified the remaining source-removal work and did not replace it.

### M0.6c · Remove excluded source surface

  * Removed excluded source surface in the four batches below, updating configuration, registries and test membership together.

#### c1 · Leaf extensions

  * Removed unentangled excluded modules and their obsolete hooks. The build and 352/352 tests passed; generated and profile configuration keys agreed.

#### c2 · Entangled extensions

  * Removed compressed instructions, excluded cache operations, pointer masking, Stateen, CFI and counters with their core hooks. The build, schema checks and 346/346 tests passed.

  * Three findings.
    * Fixed-width fetch is a *deletion of gating* **and** of the 16-bit path, this batch taking the first half and M0.20 the second: ILEN=32 makes a word whose low two bits are not `11` an unallocated 32-bit encoding, not a shorter instruction, so the parcel check goes with `C_ILLEGAL` and the compressed decode mapping it was the only user of, and nothing is left load-bearing with no clause behind it.
    * The alignment relaxation lives in four places, `fetch`, `rvfi_fetch`, `jump_to`, and the `xepc` legalization pair, and only the first two are visible from the extension registry.
    * The Lean emulator's handwritten register initializer was already stale from c1, writing `stimecmp` which went with `Sstc`; the typechecker cannot see it because that target is dormant. It and the two `SAIL_MODULES` lists naming deleted modules are corrected here.

#### c3 · Privilege and translation batch

  * Removed supervisor/user modes, translation, PMP, reservations and performance counters. The model retains machine-mode physical addressing. The build, schema checks and 329/329 tests passed.

  * Four findings.
    * `minstret` had a consumer that is not architectural, RVFI's `order` field, so deleting the counter would have deleted the differential rig's instruction ordering with it; a model-internal `retire_count` register with no CSR address replaces it.
    * The reservation flag on the memory API was never only that: `res`/`con` selected the reserved-read and conditional-write kinds of the concurrency interface, and after `Zalrsc` its one caller is the AMO, whose two halves are exactly those.
    * Two tests hang rather than fail and so cannot be left to a ctest timeout: `rv32si-p-dirty` and `rv64si-p-dirty`, whose handlers wait on a page-table A/D update that never comes with S off, the behaviour c2 booked as a profile refusal now appearing where it blocks.
    * `pagesize_bits` survives the walker: PMA regions must still be 4 KiB-aligned so that no PMA property changes inside one access, so the constant is renamed `pma_granule_bits`, not deleted.

#### c4 · Vector fork

  * Removed scalar floating-point state and `vstart`, retaining vector floating point with integer scalar operands and static RNE rounding. The build, schema checks and 261/261 tests passed. Partial vector writes were subsequently settled by M0.6e.

  * Four findings.
    * **The `.vf` forms had to be re-homed, not deleted**: ten instruction families name an `f` register upstream, and deleting the register file leaves the encodings needing a source, so the operand moves to the integer file and no encoding changes. The cost is that `vfmv.v.f` and `vfmv.s.f` become bit-for-bit duplicates of `vmv.v.x` and `vmv.s.x` and `vfmv.f.s` differs from `vmv.x.s` only in zero- versus sign-extension: three encodings the freeze can reclaim, not a curation batch's call.
    * **`fflags` has no destination and two comparisons still read it**: 44 accrual sites go, and the softfloat interface's flag half is discarded except at `fp_gt`/`fp_ge`, where the invalid-operation flag *is* the result, a quiet comparison answering false on a NaN.
    * **The scalar files were carrying the vector unit's classification predicates**, 33 `f_is_*_{H,S,D}` plus `negate_{H,S,D}`, and the float library's width-generic `float_is_*` are the same tests, so each three-way dispatch collapses to one line and the negate to a sign-bit flip; only `canonical_NaN` and three flag constructors moved, to [float_classify.sail](../../model/model/core/float_classify.sail).
    * **The `vstart` cut deleted an implementation-compatibility hack**: the four scalar-move instructions computed an LMUL-based element count only to match the bound other implementations chose for the `vstart` check, so the count, the LMUL read and the question go together; the whole-register load and store lose their partial-register prologue and the vector-crypto element-group start collapses to zero.

### M0.6d · Close the CSR bank

  * Closed the CSR bank to the frozen profile: machine-timer interrupt state, read-only `misa`, zero implementation identifiers and no debug-trigger selector. The build, schema checks and 327/327 tests passed.

  * Four findings.
    * The trap on an unallocated CSR address was already total and needed no work: `is_CSR_accessible` defaults to false in `csr_end.sail`, so `check_CSR` rejects every address no clause claims, and c3's exclusion of `mi-p-pmpaddr` for trapping rather than reading zero is the standing evidence.
    * Deleting the two interrupt *fields* deletes their two sources: the Simple Interrupt Generator device existed only to drive `MEIP`/`MSIP` and goes entirely, and the CLINT's `msip` door with it, leaving the CLINT as the machine timer and nothing else.
    * The external-interrupt bit was the sole reason `mip` read one value into `rd` and another into its own read-modify-write, so its deletion collapses `doCSR`'s two-value split into one and takes the platform-interrupt OR, the `XipReadType` enum, and `read_mip` with it.
    * Two enumerations follow the one-reachable-value rule c3 applied to `Privilege`: `InterruptType` keeps `I_M_Timer` alone, and `breakpoint_cause` goes entirely, `ebreak` being the only breakpoint source once the trigger module is deleted, which also removes a non-injective mapping whose two arms both encoded cause 3.

### M0.6e · Transplant CHERI capability semantics

  * Transplanted the capability algebra, merged registers, tagged memory, PCC/sentries, trap capabilities and checked accesses in the five batches below.

#### e1 · Fix XLEN at 64

  * Fixed XLEN at 64 and removed RV32 configurations, targets and corpus members. The build, schema checks and all 150 remaining tests passed.

  * Four findings.
    * **The transplant forces this cut rather than merely profiting from it.** A register is a capability whose address field is the register width (R-15-007i), and the 128-bit encoding e2 ports has no 32-bit instantiation in this tree, so an RV32 configuration would be a machine with no capability format to run under.
    * **Fixing XLEN changes the generated C++ interface and not only the model.**
    * **`in32BitMode` was already unreachable and the enumeration under it nearly so**: the one-reachable-value rule c3 applied to `Privilege` arrives here from the configuration, not from a deleted mode.
    * **The RV32 half of the corpus was never evidence for this profile**, exercising a base the profile does not have, so its removal costs no coverage and every excluded RV64 row is still excluded for the reason it was.

#### e2 · Port the capability format and algebra

  * Ported the capability encoding and CHERI Concentrate algebra into [cap_format.sail](../../model/model/core/cap_format.sail) and [cap_common.sail](../../model/model/core/cap_common.sail), retaining the upstream BSD licence. The build, 150 tests and eight capability properties passed.

  * Two findings.
    * **The relocation guards are dead at the source and are not carried across.** `have_cheri_relocation` is a constant `false` upstream and both the PCC and DDC relocation paths hang off it, so the port folds them out instead of transplanting unreachable branches into a model with no DDC to relocate.
    * **The tag plane needs no new machinery.**

#### e3 · Merge the register file and stand up the tag plane

  * Merged integer/capability register views and installed a granule-keyed tag plane; integer writes clear authority. The build, 150 tests and four additional register/tag properties passed.

  * Finding: **the granule keying is the model's to do.**

#### e4 · Port the checks, PCC and sentries, and the trap capabilities

  * Added PCC and data-authority checks, capability trap state and sentry-aware `mret`. The build, 150 tests and new trap/access properties passed.

  * Two findings.
    * **The transplant cannot delete DDC on its own schedule.** Hybrid mode and DDC therefore stay until M0.6f, which also sets that item's exit criterion: after the cut `riscv-tests` is not a corpus this machine can run, and the batch is gated on purecap test programs (M0.12) instead.
    * **Trap raising belongs in the postlude.** Checks read PCC in `core`, while trap raising calls the later-compiled exception machinery in `sys`. The three `ext_handle_*_error` hooks and two privilege-failure hooks therefore move to `postlude/cap_traps.sail`, where both are first in scope.

#### e5 · Port the instruction surface and stand up the differential harness

  * Ported the admitted ISAv9 instruction surface and established the differential harness. The build, 150 tests and ten new instruction properties passed; all 54 integer corpus members agreed for their first 97 records. That prefix did not establish full-program lockstep.

  * Four findings.
    * **The read path was discarding the tag.** e3 wired the granule-keyed plane into the write path, but `checked_mem_read` returned `default_meta` unconditionally (an upstream `TODO` about folding metadata across splits), so no capability could be loaded with its tag set; e5 is the first batch with an instruction that reads one.
    * **`lc` collides with `cbo.zero`.** The destination separates them here; the frozen dialect re-encodes this anyway (R-15-007), so the freeze owes a decision, not a repair.
    * **The two executors neither start at the same instruction nor report a register write at the same width.**
    * **`riscv-tests` cannot reach agreement past its own prologue, a fact about the corpus, not the transplant.**

### M0.6f · Re-parameterize to 64+1 bits

  * Implemented the frozen 64+1-bit purecap format, permission lattice and split sentry roles; removed hybrid mode and DDC. The model properties and configuration checks passed. The legacy integer-addressed corpus was thereafter refused in full; purecap programs became the behavioral oracle.

  * Five findings.
    * **The exponent field carries the case flag, because the table leaves no bit beside it.**
    * **The byte-exact threshold the frozen widths deliver is 128 bytes and the padding above it is one part in 64 per side, and R-15-007c is amended to them.** Both are now model properties over an unaligned base, so a later change to the widths or the packing cannot move them silently, and every consumer moves with them: R-15-007e and R-15-007f's admissibility argument for the indexed load and store, which the narrower threshold **strengthens**, R-15-007k's relocated rounding, R-08-004b's closed bit budget, and the alternatives register's declined bounds-check elision.
    * **An integer register is 64 bits and an address is 36, so a register's integer reading is its whole 64 data bits, and R-15-007i is amended to say so.**
    * **The corpus goes with DDC, entirely, not family by family.**
    * **Membership is by enumeration, which reaches four instructions and one otype decision this item's own list does not name.** The same rule freezes the object-type space: three of sixteen codepoints are reserved, the unsealed one and **two** sentry edges, R-15-071's forward/backward split being a reservation in that space, not a later amendment to it.

### M0.6g · Add profile rows absent upstream

  * Added conditional moves, revocation filtering/bitmap, `fence.t`, indexed capability accesses, `cclear` and machine-level AIA pending state. The build, 43 properties and 15-member differential corpus passed.

  * Five findings.
    * **The revocable interval's width is the model's to bound and the covered union is a predicate, not a list.** So the plane fixes 4096 granules, `validate_config` refuses a composition that does not fit instead of letting its top granules fall silently outside the filter, and a second interval is a clause in `revocation_covered` rather than a mechanism, every consumer quantifying over the predicate.
    * **Deleting the AIA indirect interface is what puts the pending array in the address map.** Upstream an interrupt file exposes `seteipnum` to senders and leaves the pending bits to `miselect`/`mireg`/`mtopei`; with those excluded the array has nowhere else to be, and *software reads pending bits with ordinary loads* is R-15-065's own sentence.
    * **`fence.t`'s Sail content is the enumeration, not the barrier**: the flush set is one structure and this model has no store buffer, so the file carries why every other structure is absent from the set. Its reserved fields trap where `fence`'s are ignored, this instruction having no future extension to reserve them for.
    * **The generated test-matrix configurations are a second declaration of the platform**: two new keys broke the build at schema conformance on `rv64d_*.json`, not on the profile's own configuration; a key added to one and not to [config.json.in](../../model/config/config.json.in) is a build failure, not a divergence found later.
    * **The model's own harness runs under the generated *max* configuration, not the profile's**, so a property reading a configured policy is about the wrong machine: that a misaligned indexed load faults is the profile's answer, not that configuration's, which defers misalignment to the PMA. Profile-conditional behaviour belongs in the corpus.

### M0.6h · Add the three bespoke block instructions

  * Added `vmclear`, `creclaim` and `cbo.scrub` with their capability checks. The build, 46 properties and 17-member differential corpus passed.

  * Six findings.
    * **The vector gate is the class, not the context.** The first build gated on the second and failed its own decode assertion at a reset whose `VS` is `Off`.
    * **The scrub had to become an arm of the access type rather than a convention of its caller.**
    * **The welded block size stopped belonging to `cloadtags`.**
    * **`cbo.scrub`'s telemetry and fail-stop have no architectural state to hang on, and are not invented here.** The file records where each half lands: correction telemetry goes to the sentinel, a device and a core class, not a structure the scrubbing hart can read, so correction is invisible in the timing (R-15-179); and the fail-stop needs no new channel, the block read already returning `MemoryOpResult`, so a detection joins the path a PMA refusal takes.
    * **What the scrub *is* in an architectural model is the tag-preserving pass, visible only against the write path.** Hence a block operation of its own, not a load-and-store loop; [platform-scrub.s](../../corpus/platform-scrub.s) checks it by doing both to the same block.
    * **`creclaim`'s clear lands in memory where the load filter's lands in a delivered value**, the reclamation half and the containment half of one protocol: clearing a revocation bit puts the object back in service for the filter and does not for `creclaim`, the tag being gone from the granule, not from a value (R-08-007a).

### M0.7 · Model Ztso and static-only prediction

  * Fixed the model to Ztso and static-only prediction, with Ztso named in the attested devicetree. The build, 56 properties and 20-member differential corpus passed.

  * Five findings.
    * **The item's reach is small.**
    * **That trap is the profile diverging from the base ISA's semantics, not only its encoding, and it is a deleted rule, not an added check.**
    * **The drain condition reads the I and O bits directly as one mask per side, not as an arm of a 256-case lattice, which lets `is_fiom_active` go.**
    * **One enumeration member had been dead since c1 and nothing said so**, a defect class the narrowing removes rather than the one it found: `Barrier_RISCV_i` lost its only constructor site when `Zifencei` was excluded, and an enum member with no site is not an error in Sail.
    * **Static-only prediction adds no Sail at all; the model gains a citation.**

#### M0.8a · The core roster and the class table

  * Added composition-fixed core classes, datapath records and hart roster to the attested devicetree. The build, model properties, corpus and fourteen seeded configuration refusals passed. **K-60** holds the restated class geometry.

  * Seven findings.
    * **`mhartid` was a selector into a table that did not exist.** R-15-052b requires the reachable value space to be a composition-time constant fixed by the core roster, so a hart identity outside the roster is not a value the machine can present.
    * **The class table cannot derive the vector geometry, so the binding is a refusal.**
    * **The `Zvl` ladder stopped at 1024 and would have described a V-class build as narrower than it is.**
    * **The `cpu` node hardwired hart zero.** Both now follow `plat_hartid`; the label stays `CPU0`, being a DTS label, not an identity.
    * **The roster is one property, not sixteen nodes, and both halves of that are forced.**
    * **A devicetree source is a grammar, not a rendering, and `dtc` is what says so.**
    * **The tree outgrew the region it is written into and nothing said so, because the bound was on a path no ordinary run takes.** Three things follow: the ROM region is sized for the tree it holds, not left at upstream's spike-bare 4 KiB default, which no one budgeted, and the region's extent is the composition's to state; the per-class core count comes back *out* of the tree, a count beside a roster being one fact written twice in one attested artifact; and `model.py devicetree` now generates, compiles, and hands the blob to the emulator's own bound, not a second copy of it.

#### M0.8b · V-class long-vector datapath and per-element capability checks

  * Exercised the V-class configuration at VLEN=4096 and added masked-off element checks. The build, 68 properties and 23-member differential corpus passed, with the existing datapath and encodings retained.

  * Seven findings.
    * **The type-level configuration is compile-time for the provers and load-time for the emulator, and only the second half was written down.** It does not hold of the C++ lane, which takes no `--config` at emission: the emitted model reads the configuration when it loads one, and `sizeof(vlen_exp)` answers 8 or 12 according to which file it was handed.
    * **The model has one inactive-element mask and R-15-115b's obligation attaches to a third of it.**
    * **The model pads every masked-off access, not only the failing one, which is stronger than the requirement and is forced.**
    * **Two of the item's four requirements were already satisfied and nothing said so.**
    * **The extension-context dirty fired once per element and put the geometry into the commit trace.**
    * **`vlseg<nf>e<eew>ff.v` was a vector operation that was neither all nor nothing, and the register has since answered it: the form is excluded.** Its defined result on a fault past the first element was to trim `vl` and retire rather than raise, which R-15-039a's all-or-nothing rule does not admit.
    * **The assembler's vector rows needed one operand that is spelled by being absent.**

#### M0.8d · FEC and Keccak units

  * Added fixed-geometry LDPC/polar decoders and the frozen Keccak permutation instructions, with profile bindings and bounded execution. The build, 84 properties, differential corpus, geometry refusals and NIST-vector checks passed.

  * Eight findings.
    * **The gate is the class *and* the context, and M0.6h's answer is right for its instruction and wrong for this one.**
    * **No row enters the extension registry, and that is the requirement.** `hartSupports` builds the generated `riscv,isa` string and `riscv,isa-extensions` array, so an `Ext_Zvknhk` row would have an **attested** artifact name a standards-track extension this machine does not implement, RVG-84 not having ratified.
    * **R-15-057a's `Zvl128b` mandate is unreachable, and the model is correct either way.**
    * **The two defects the known-answer vectors found were both transcriptions.** A known-answer vector says *wrong* and a structural property says *why*, and a test file does not get to choose the order between them.
    * **Where this model stops on the FEC half is correction, for the reason `cbo.scrub` stops at the syndrome.**
    * **The corpus found an encoding defect the harness structurally cannot.** A hand-written `vse64.v` merged the `rs1` and `funct3` nibbles and named `c11` where it meant `c10`, an uninitialized register whose untagged value faulted the access. A `$[test]` calls `execute` on a decoded instruction and so never sees a mis-encoded word.
    * **A property that saves a list register and restores it by assigning the saved binding does not restore it, and only the harness's per-property reset hides that.**
    * **The refusal set is one-directional, because the symmetric one would have refused every composition in this tree.**

### M0.9 · Add documented timing annotations

  * Authored the operation-class timing table in [timing.sail](../../model/model/core/timing.sail) and configuration checks; **K-63** validates model requirement citations. The build, model properties, corpus and seeded refusals passed. The model executes no cycles: this item supplies timing declarations, not measured latency qualification.

  * Six findings.
    * **The contract is the signature, not a comment beside it.** `timing_cycles` takes an operation class and no operand, register, address or prior state, so nothing can enter it. That is data-independent latency in a model that executes no cycles (R-15-053, R-15-095): a future consumer wanting an operand shows up as a changed signature.
    * **The scalar table is one table because the front end is one front end.**
    * **The table is deliberately not in the attested devicetree, and R-09-007 is why.**
    * **The crown-jewel row does not move, and `qualified` keeps that honest.**
    * **The membership rule this item set out to owe cannot be written without becoming the defect it would catch.** 11 register entries say an operation is one entry in the timing-annotated model, and holding that set against the table needs a mapping from each entry's prose to a class member, a third copy of the correspondence; a body-pattern selection returns two of the 11, the register stating one obligation in five wordings.
    * **The gap nobody had named is that the model's own citations reached no rule at all.**

### M0.10 · Generate and freeze the C-class golden emulator

  * Generated and froze the C-class executable ISA reference at `abcc685` under Sail 0.20.2. Its revision identity, 62 model properties and 21-member corpus passed validation.

  * Four findings.
    * **The reference could not name itself, and nothing said so.** `execute_process` runs in the current binary directory by default, and an out-of-tree build directory is not a repository, so `git describe` exited 128 and every emulator this tree ever built stamped itself `unknown commit`.
    * **The exit criterion had to be re-read, because the suite it names is one this machine cannot run.**
    * **The stamp is set at configure time and the working tree decides it.** `reference` prints the dirty marker rather than refusing it, a gate that failed on an edited tree being a gate that gets turned off; it refuses an **unknown** revision, the state this item closed.
    * **`--version` still reports upstream's release number, and that is right.** 0.13.1 is a true fact about the lineage this tree was curated from, and the model's own identity is the revision `--build-info` carries beside it.

### M0.11 · Define the profile-freeze measurement contract

  * Authored the [profile-freeze measurement contract](contracts/freeze-measurement.md), including corpus, composition recipe, decisions, thresholds, provenance and report predicates. It requires measured encoded bytes, dictionary reselection per variant and a closing pass at the admitted configuration; measurement execution belongs to its consumers.

### M0.12 · Version the differential corpus and capability trace schema

  * Versioned the [purecap differential corpus and capability trace schema](../assurance/differential-corpus.md), with an in-tree assembler and image composer. The landing build, model properties and eleven-member corpus passed; later members retain their own evidence. [Corpus limits](../assurance/differential-corpus.md#7-what-the-corpus-cannot-exercise-yet-and-why) remain explicit.

  * Two findings.
    * **A fetch of an instruction wholly inside PCC's bounds raised a length violation**, which `cap-control`'s bounded sentry entry found on its first run. The profile excludes `C` and fixes ILEN at 32, so `min_instruction_bytes` is four; it does not adopt `Ziccif`, so a fetch still splits into two 16-bit granules; and the per-granule bounds check asked for a whole instruction from the *second* granule, two bytes past the instruction.
    * **The store-side root arrives in the link register**: reset hands `c1` the root data capability and `c1` is `ra`, so a program that calls overwrites its own authority. Every corpus member therefore opens by moving it to `c8`, and §3's composed initial distribution is where that stops being the program's problem.

### M0.13 · Two-geometry CBO block-size constraint

  * Authored the [welded block-size constraint](../hardware/block-geometry-constraint.md) against capability-granule and ECC-payload geometry. **K-57** holds restated sizes to their owners. Six constraints were derivable and six still owed physical or producer inputs; block-size selection remained a separate decision.

  * Five findings.
    * **The item cannot evaluate its own output, and saying so is the result.**
    * **The first-class half is computable now, and it turns on a ceiling the destination register sets.**
    * **The declared 64 bytes is interior to that set, which makes the owed rows the interesting ones.**
    * **Holding the number meant letting one rule read the model, which the selftest's sandbox had made impossible.**
    * **Two of the four sites had no assertion behind them.**

### M0.14 · Two latency classes in the Sail model

  * Added both fixed-latency memory classes to the Sail platform and attested devicetree, with configuration refusals. The model build, properties and corpus passed; physical qualification remains separate.

  * Five findings.
    * **The record is symmetric and the machine is not, and the validator holds the difference.** They are declared zero there under the model's zero-is-absent idiom and the validator refuses anything else, so a composition cannot declare a refresh deadline over a latched array.
    * **The retention corner is two fields because only one of them is ever read.** R-15-247m states it as a measured interval, not a point, and R-15-247c consumes retention by the refresh deadline alone, so a mean with a tolerance would invite the ceiling into a guarantee.
    * **There is no separate fetch constant to declare.**
    * **A placeholder nothing distinguishes from a measurement becomes an input, so the qualification state is attested.**
    * **The corpus member is a set of claims that nothing is observable, which is what makes it worth running.**

### M0.15 · Capacity, placement, and bank checks in register tooling

  * Added tag-plane arithmetic, capacity/bank declarations and complete two-class placement checks. **K-54**, **K-55** and **K-56** hold their respective owners; checker mutations and typechecking passed. The bandwidth comparison remained unavailable without its producer operands.

  * Five findings.
    * **The first rule found a real disagreement on its first run.**
    * **The clause the item asks for has no operands, so the bank-count half ships as a booking, not a comparison.** *A stated island bandwidth ceiling its bank grant cannot deliver fails the pass* needs two figures and only the count is stated, a placeholder while `qualified` is false on both classes. The ceiling is not a figure: R-15-247p makes it fixed by the TDM schedule and the bank binding, so it is an output of the count under search times a per-bank width M0.8 owes and a slot share M1 owes, and R-15-228a forbids the memory plan from producing it.
    * **The tag plane is one field read five ways, so it is one rule.**
    * **`compounds` stopped being about one document; only the group's name survived the widening.**
    * **The placement is held total over the charge, not over its own words.**

### M0.16 · Refresh and discharge sequencer in the Sail platform model

  * Modeled fixed-cadence refresh and bank-staggered exit discharge in [memory_sequencer.sail](../../model/model/sys/memory_sequencer.sail), with a requester-refusing MMIO window. The build, properties, corpus and seeded configuration refusals passed. Charge retention and physical discharge remain outside the model.

  * Six findings.
    * **The discharge needed no mechanism of its own.**
    * **A window that refuses and a window that is absent are different facts, and only the first can be stated by claiming the address.**
    * **Refresh and discharge are modeled differently on purpose, only one having architectural content to execute.** A refresh restores a charge this model does not represent and disturbs nothing observable, so what it can get wrong is the cadence, and the model carries the deadline arithmetic and a refusal. The retention floor is multiplied up into cycles, not the sweep divided down into microseconds: that needs no runtime divisor and rounds nothing, where the other direction could round a cadence into a compliance it does not have.
    * **The unit of work is the bank because the walk over the banks is R-15-198's**, power and reset sequencing being one composition-time sequence table executed by the RoT firmware as the only sequencer. That also keeps the exit path a property, not a measurement: a composed bulk domain is gigabytes, and a whole-domain pass is an emulator run, not a `$[test]` assertion.
    * **The fail-stop's negative reading has no source in a valid composition.** The model holds the **shape**: read once after a fixed worst-corner dwell with no poll and no retry, over a real architectural latch, not a fault-injection register. A machine that can leave charge behind joins that read as a case, not a mechanism.
    * **One validator arm was dead the moment it was written, and running the seeded refusals found it.** `config_is_valid` short-circuits and the class record's own check refuses a zero bank count first, so a second message saying the same thing is a branch no configuration reaches; that arm has to be the arithmetic's precondition, an early return, not a refusal.

### M0.17 · Per-class bank-count DSE with droop as a hard constraint

  * Authored the [bank-count exploration contract](../hardware/bank-count-dse-contract.md) and symbolic report. **K-58** holds its declared point and qualification bindings. Eight of eleven candidates passed shape constraints; none was admitted because required physical coefficients were missing.

  * Six findings.
    * **The search cannot be run: every coefficient that would make it a search is missing.**
    * **The declared count is one doubling from the only shape constraint that can fail.**
    * **The hard constraint's asymmetry is what the rule protects, and it fails silently.** A pruning predicate with no operands admits everything or nothing depending on how it is written, and what changes that is a coefficient quietly acquiring a value. So K-58 reads the coefficient table's status column against the composition's qualification flag in the direction that bites: while the class is unqualified the two pruning symbols must be pending, a droop envelope with operands meaning a macro had been measured.
    * **The estimate document disqualifies its own figures as inputs here.** [performance-estimates.md](../performance/performance-estimates.md) carries a read energy of 0.1 to 0.5 pJ/bit and closes that row by saying every figure in it is an order-of-magnitude estimate over a retention corner spanning a factor of sixty and is not a freeze input.
    * **Holding the number meant one more model file inside the checker's reach, and the carve-out moved to where it can be seen.**
    * **R-15-108's parameter list was short the per-class bank count; that question is now answered.**

### M0.18 · Retire the first-party test harness

  * Retired the first-party test harness and its redistributable dependency surface, retaining the generated and differential validation routes.

  * Three findings.
    * **The RV32 half was broken at build, not dormant, and no gate could see it because the option is off.** Half the harness depended on a file no rule produces, so `-DFIRST_PARTY_TESTS=ON` failed at `configure`, not at a test, and the XLEN loop was removed here, not upstream.
    * **The deletion costs the checker a sixth of what it reads, and its subject does not move.**
    * **`model/.github/` stayed byte-identical to its pin here and I8's enumeration grew by one, and S3 has since answered it: the tree is deleted.**

### M0.19 · Land the vector-FP fork's decided residue and name `Zvfbfmin` in the model

  * Applied the decided vector-FP encoding residue and named `Zvfbfmin` in the model. The landing behavioral checks passed; this supplied no broader upstream re-pin qualification.

  * Landed: Tier A.

  * Six findings.
    * **The corpus assembler never carried a vector-FP row, so the follow-through the deletion was expected to owe did not exist.**
    * **K-66 measures the strike it cannot catch.** Its two model-side readings each fall by exactly two while its verdict is unchanged, §6 spelling these forms in prose where the rule reads rows.
    * **The profile contradicted itself about the fork inside one section, and the amendment created it.** §6's account of what the first fork costs at the instruction level said the profile keeps every one of those encodings and re-homes the operand instead of deleting the forms, which the paragraph four below it, added by the same amendment, had already falsified.
    * **M0.6c's c4 carried the same claim and its own bullet already refuted it**, *the vector unit keeps every floating-point form it had* standing beside *three encodings the freeze can reclaim rather than a curation batch's call*; this item is that reclamation for two of the three, and c4's sentence is repaired where it stands.
    * **`Zicclsm` is `Zbc`'s unrecorded sibling.** R-15-048a excludes it by name, `Ext_Zicclsm` sits in the isa-string roster with its key false in all three shipped files, so its exclusion is likewise a key, not a shape of the model, and it has no instruction file of its own to record the disposition in.
    * **Nothing left with the two clauses, each candidate checked against its callers by name.**

### M0.20 · Close the fetch path's instruction-length decision and the harness's restore idiom

  * Closed fixed-width instruction fetch and the harness restore idiom against the frozen profile. Model behavioral checks passed. The lane's checker had arithmetic drift, so its selftest supplied no mutation verdict; integration repair remained the integrator's.

Calibration: no original estimate was recorded; excluded from the fit.

  * Landed: Tier A. It changes what the machine does with a word, it deletes decode surface, and it moves two findings landed items recorded (third and fourth findings), so it is read whole, not spot-read.

  * Ten findings.
    * **The fetch contradicted the two checks above it inside one function.** It asked PCC for `min_instruction_bytes`, which is four because ILEN is 32, refused a PC that is not four-byte aligned because instructions are 32 bits wide, and then derived a second, shorter length from the word it had just authorised four bytes for.
    * **The packet was right and the trace was wrong, the direction S11's finding could not take.** `mtval` carried the halfword too, the same defect where a program, not a rig, can see it.
    * **What decides the boundary of the deletion is which act killed the construct, not that it is dead.**
    * **F-081's claim is false and only running it could say so.** The restore by assignment is exact: a Sail list is reference-counted and `COPY` increments before it kills, so the saved binding *aliases* the register instead of copying it, and the two are one chain the restore cannot lose.
    * **The emitted `cons` overwrites its destination without releasing what it overwrote.**
    * **`cap-trap`'s own trap count was stale in two artifacts and in two directions before this item touched it.**
    * **The `$[test]` harness cannot reach the fetch at all.** That sharpens M0.6g's split, which was stated for the configured-policy case: there the harness reaches the code and answers about the wrong machine, and here it does not reach the code.
    * **M1.4-prime's corpus-image criterion cannot tell a member that grew from an encoding that moved**, its subject being the encoder and its input being the corpus, so the first edit to any member reds it and its own instruction is never to repair a red run by rerecording. What admits a rerecord is measuring the old figure back: assembling the corpus with the changed member's pre-change source under the *current* encoder reproduces the transcribed 55,992 bytes and digest exactly, so the delta is this member's alone and no encoding moved. **The delta is also not the instruction count it looks like**, and the criterion's figure is an image total, not a text total: the four added statements assemble to five words and twenty bytes of `.text`, of which the image shows sixteen once the padding to the next section's alignment absorbs the rest.
    * **A lane that may not run `--fix` cannot run the mutation selftest at all.** Every landing moves the hours and the findings totals, so `check.py` is red until the arithmetic is rewritten, and the selftest's baseline *is* `check.py`: it reports `the unmutated sandbox does not pass, so no case can decide anything` and runs no mutant.
    * **The revision stamp's dirty marker decides nothing on this lane, and the two sides of it disagree.** Which side is right about the tree is not determined here and no cause is asserted; what is measured is that the marker beside a revision figure is not evidence the tree was edited, the half of M0.10's dirty-checkout finding a reader would otherwise take it for.

## M1 · Toolchain spine (incl. the CHERI-CompCert prerequisite)

### M1.1 · Locate and pin SECOMP2CHERI

`upstream/SECOMP` is pinned at `5c20b839`, the SECOMP2CHERI/CCS artifact carrying CompCert 3.17. The [licence record](../../THIRD-PARTY.md) binds the pin's non-commercial core terms; the gitlink conveys no source files.

The compartment front/middle end is a reference, with unfinished top-level integration and admitted stacking work. Its CHERI backend is incomplete, unverified and unintegrated, with ISAv8-lineage assumptions that differ from the frozen purecap profile. M1.2 owns measured usability and the backend decision; the stated upstream tool requirements alone supply no build evidence.

### M1.1a · Decide the compiler-provenance fork

The compiler remains a contained build-time producer and is never redistributed. This reversible choice preserves [COPYRIGHT.md](../../COPYRIGHT.md)'s distribution map but forfeits a third party rebuilding the image from source and leaves the bootstrap/validation-instrument claim dependent on it. Obtain-terms and route-around alternatives remain open; reassessment is tied to whether third-party rebuilding becomes load-bearing at M1.2's midpoint.

The [pin licence reading](../../THIRD-PARTY.md) places the verified/backend passes outside the dual-licensed subset; stock CompCert retains the same restriction. CompCert terms and SECOMP contributions require distinct authority if both are acquired. VST's non-dual-licensed concurrency tree can reintroduce the restriction, so its opam distribution is the accepted acquisition route. Containment was re-weighed after the incomplete/vacuous CHERI backend measurement and retained; no terms were inferred from lineage.

### M1.1b · Decide the backend's start-from

M1.2 authors the purecap backend over stock CompCert RISC-V; `upstream/SECOMP` remains a compartment-layer reference. The CHERI pin's step relation is vacuous, its semantics is not integrated with CompCert and its incomplete/admitted instruction work requires replacements rather than parameter changes. Stock RV64 is closer to the frozen static-frame, exact-narrowing profile.

This technical decision preserves M1.1a's containment restriction. Deferred robust-preservation work must join SECOMP's front/middle end to the authored backend; its compartment recomposition, blame and back-translation remain potential inputs. The measured width edit in the rejected tree supplies evidence rather than a transferred patch.

  * Landed: Tier A.

#### M1.2a · Re-baseline the delta against stock CompCert's RISC-V backend

The re-baseline reads `riscV/` at SECOMP pin `5c20b839`, a compartment-modified backend rather than a pinned stock release. Capability storage, permissions, tagged values, sealing and sentries must be authored; the uninitialized/frontier and invalid register conventions of `cheririscV/` disappear with that tree. Float-bank deletion is larger in RISC-V, and frame carving remains an OCaml expansion requiring capability operations and exact bounds.

CompCert's block-addressed semantics can remain: physical flattening belongs to the composer, globals already allocate before execution, static frames replace activation allocation, and forbidden heap builtins are separate table arms. Capability values/tagged memory belong to the `common/` seam, which the original child allocation omitted. The licence split places that seam in the dual-licensed subset and the backend outside it; using SECOMP-modified bytes also retains its contributor boundary.

No compiler source was authored or incorporated. Every axis was traced to its owner; containment was re-derived from the pin's licence. The re-price was declined: removed start-from defects and newly identified unpriced memory work do not translate line counts into attended effort. Existing midpoints/ranges stand with a qualified floor, and the bootstrap reassessment trigger is not reached.

  * Eight findings.
    * **The pin's RISC-V backend is compartment-modified, not stock**, with two admitted compartment-layer lemmas.
    * **Five axes have no counterpart in that backend.** Removing the rejected tree's defects does not price the remaining authoring.
    * **The register axis changes direction.** The rejected register defects disappear while scalar-FP deletion is larger.
    * **The block model survives.** Physical addresses belong to composition; frame placement and forbidden heap builtins are distinct from the memory type.
    * **Capability values and tagged memory require a `common/` fork**, absent from the original child allocation.
    * **The licence split crosses the delta.** The backend is non-commercial-only; the memory seam is dual-licensed.
    * **Frame carving is expanded in OCaml outside the verified pipeline**, and every derived narrowing must be exact.
    * **Start-from size is not work cost.** The measurement changes the estimate's standing without supplying a new midpoint.

  * Landed: Tier A.

#### M1.2b · Author the capability type, the merged register file and the width

The accepted backend-local representation at contained `a826d5f17bb09742940cb66f7c986c55ccfbf6de` supplies the frozen capability encoding/round trip, merged integer-capability registers and scalar-FP instruction refusal. The capability value/memory carrier remains M1.2g's scope.

A fresh source-only build compiled every registered proof module, extracted and linked `ccomp` with unchanged admit census. The independently reviewed [assembly comparator](comparisons/compiler-assembly.md) found all nine fresh FP-free source pairs equal, exempting only exact compartment metadata identifiers. Six historical sources were retained verbatim; three reviewed replacements exercise missing loop/call, variadic and memcpy cases. This does not claim equality of lost historical outputs. Scalar-FP refusal writes no assembly; integer capability-printer smoke succeeds.

The recomposition repair retains statement blocks/admit baseline. `common/` is unchanged; the sole `cheririscV/` difference removes an unreachable wildcard. The 2026-09-15 closeout added no compiler replay. F-319 leaves float-memory lowering to M1.3; source values, frames and target acceptance retain their owners. Evidence remains in contained `test/verifiedos-m12b/` and `/root/build/m12b-clean-20260912-closeout`.

  * Eight findings.
    * **Float-bank deletion breaks recomposition proof branches and positional inversions.** The focused repair and fresh full build close that failure.
    * **An unreachable `cheririscV/` wildcard becomes a redundant-pattern error** when float registers disappear; its deletion is the admitted exception.
    * **Raw `-S` byte identity fails through compartment metadata and allocator changes.** The reviewed comparison contract identifies the accepted relation and fresh corpus.
    * **Float-typed values can pass through integer registers but cannot load, store or spill.** M1.3 owns memory lowering.
    * **The constructor census counted uses, not deletions.** One float-naming instruction remains with a narrowed destination.
    * **The changed type/register convention would be unsound on RV32.** Configure now refuses that target.
    * **Definition shape affects proof automation.** Making `destroyed_by_op` reducible required removing tactic steps already closed by conversion.
    * **An empty `FILES` census can look successful.** Fresh acceptance checks a nonempty, uniquely resolved manifest and every expected object.

Calibration: original midpoint 6 h, range 4–8, class X; retained planning weight, cumulative actual n/a. Historical repair, shared integration and review intervals are unrecoverable; partial/build durations supply no measured actual or calibration pair.

Landed: Tier A. The technical acceptance and unavailable-actual accounting are reviewed judgments. The settled integration batch supplies the host validation; no repository rule replays the historical contained compiler campaign.

##### M1.2g-i · Exercise inhabited capability-memory semantics

Contained `4edef3bc2daa75e24c94abb9557c6ed28aa40495` qualifies [inhabited capability memory](contracts/compiler-prerequisites.md#1-inhabited-capability-memory). Generated specimens use allocated memory and actual access decisions. Supported chunk pairs preserve complete values; overlap, destructive writes, restoration, alignment and malformed-fragment cases establish their explicit outcomes. Incomplete encodings yield integer zero or `Vundef`, never a capability.

The final campaign passes 429 propositions, recursive `coqchk` and three false well-typed equality controls. Receipt SHA256 is `e8099cb232686a80d8fa0bc971c46bb28bed8e2601108afed65a66cf94e2db7c`; retained proof/log roots are `/root/build/lane-easy-m12g-20260920/acceptance` and `/root/logs/carrier-acceptance-easy-m12g-20260920`. Source identities were independently checked. The immutable foundation also passes proof, extraction and compiler build.

Four audits are closed; other propositions use only the inherited `Archi.ptr64`, classical, functional-extensionality and classical-real assumptions. Target statements quantify over `Archi.ptr64 = true`, bound to RV64 extraction/configuration; no new axiom asserts it. No production source/admission is added. Unsupported capability addresses, casts and arithmetic still refuse. Source execution, emitted traffic and Sail tag-clear refinement remain later joins.

The settled host batch is recorded by `out/compiler-prerequisites-final-gates.json` at base `a40f9e489ed50ee0bcfee080acf06b34489ada5f` plus its documented integration changes. Host validation does not replace the separate contained proof/kernel/oracle/build predicates.

Recorded actual: 0.7 h agent-parallel, including integrated review; initial scouting is excluded.

Landed: Tier A, by the integrator's full read of generated propositions, access
proofs, inherited assumptions, destructive controls, receipts and scope limits.

##### M1.2g-ii · Integrate capability values with source operations and emitted memory traffic

The contained scalar compiler implements the [source-value contract](contracts/compiler-source-values.md) through source operations, typed memory injection, byte/tag effects and emitted traffic. Object, code and nominal-grant identities remain bound to supplied/derived capabilities. Recursive checking passes the owned propositions and exact inherited APIs, with no new axiom or admission.

The accepted compiler is `d1d70bd80a7d11841bab1dc87fd2a3a7b2efb063`, executable SHA256 `0c9e63e5fe6759852d2b533daf71f818b3b4288f91b9d811b8abced2a8459af3`; the completed build/owner inventory preserves that executable and earlier immutable receipts. The recorded Sail build, sources, assembler and selected scalar header are joined to original/preprocessed C. Positive source/interpreter/target campaigns pass; destructive byte and copy-store controls execute and are detected, clearing the affected tag while preserving adjacent capability state. No survivor or stillborn result is counted as a kill.

Pointer equality with differing bounds, cursor/null observations, typed copies and precise source refusals have separate checked populations. Primitive externs use the composition-parameterized relation, not ordinary C-interpreter semantics. M1.2d-ii/M1.2e-ii supply call, installed-authority and narrowing joins. Validity, initialization, lifetime and placement remain premises; universal pass/Sail simulation, arbitrary-context preservation and the Gallina-component comparison retain their owners. Detailed sources, build products and campaigns stay contained.

Retained: [`/root/logs/compiler-unblock-integration-20260921/source-handle-final-1/result.json`](retained-evidence/root/logs/compiler-unblock-integration-20260921/source-handle-final-1/result.json); receipt SHA256 `0b996e6cb93cbb97b9baa343dd077554a1d3f074b29c4dbca8fa985b424544c1`.

Calibration: original midpoint 7.5 h, range 4–11; retained planning weight, cumulative actual n/a. Interrupted history/shared integration lack complete per-item intervals; gate durations do not replace them.

Landed: Tier A, with final hosted validation pending at publication, by the integrator's full read of the source and memory relations, actual compiler path, decisive controls, inherited assumptions, source/build bindings and acceptance limits. Validation uses hosted Windows and Ubuntu Host CI and the hosted Guest CI model, proof and RTL sweep; compiler-specific checks stay separate because their sources are contained. The public model and proof evidence is shared with M1.2d-ii.

#### M1.2c · Author the permission lattice and the otype space

Permission expansion/narrowing, the object-type space and sentry-role lemmas agree with their [Sail owners](../../model/model/core/cap_common.sail) at contained `5ef8b929cea56f941aad514a072d87dc064d9759`. Fresh vectors cover every permission codepoint, mask and object type. Focused kernel recheck and closed assumption audits pass with unchanged admit census. A combined build checks registered modules, extracts interfaces and links `ccomp`; integer smoke succeeds and scalar FP refuses.

This accepts helper authoring with M1.2b's representation prerequisite, not instruction-execution differential. A no-link jump admits either sentry; a linking call only a forward sentry. Carrier, frame, narrowing-emission and target integration remain separate. The 2026-09-15 closeout adds no contained replay; evidence remains in the contained repository and `/root/build/compiler-helpers-20260912-a`.

Calibration: historical midpoint 7 h, range 4–10, class X; retained estimate, cumulative actual n/a. No historical work interval is recoverable; this review/build duration supplies no measured actual or calibration pair.

Landed: Tier A. The helper acceptance is read against its model owners, and the settled integration batch supplies the host validation. No new contained compiler replay is claimed.

##### M1.2d-i · Locate lost capability kinds and state the lowering prerequisites

The [kind handoff](contracts/compiler-kind-handoff.md) satisfies the [diagnostic predicate](contracts/compiler-prerequisites.md). Contained `f5a55d4cfa84b311a425d0c354e8a8439a3d33a6` retains the source/tool/configuration-bound campaign under `test/verifiedos-m12d/`, using compiler source `cd1d3adbea95b9d7e1a25d335c4dd48e22435a6d`.

Pointer/integer copies differ in Clight but become identical Cminor/Mach bodies; Cshmgen's access mode and `Mptr` chunk lose the kind, while `Xptr` survives extended signatures. Across-call pointers spill as scalars. Ten runs cover both optimization settings; two reproduce the integer ninth-argument printer failure. The pointer ninth-argument printer is unexercised. Hash-bound outputs and semantic refusal controls pass independently checked identity/boundary tests.

The handoff assigns value, slot, authority, cast, primitive and plan joins to g-ii/d-ii/e-ii/f. It preserves the scalar ABI, leaves the switcher undecided and claims no emitted purecap execution. Diagnostic artifacts remain under `/root/build/lane-easy-m12d-20260920`; the shared host gate is recorded with g-i.

Recorded actual: 0.4 h agent-parallel, including integrated review; initial scouting is excluded.

Landed: Tier A, by a full read of the diagnostic, retained outputs, refusal
checks and handoff against their acceptance contract.

##### M1.2d-ii · Realize typed frame, call and primitive lowering

The scalar compiler preserves payload kinds/authority roles through the real lowering pipeline. Mandatory stage checks refuse unsupported kinds; frame/call/primitive operations, stack spills, globals, closed compatible indirect calls, typed copies, large frames and stack arguments follow the selected ABI. Exact primitive identity/signature/profile checks precede emission; M1.2g-ii binds the producer pair.

Final target replays, actual-C boundary controls and timer interruptions pass. Bounded nested returns clear private stack/activation state and local return copies before publishing callers. Cleanup theorems and exact-loop certificates pass recursive checking under explicit installed-writable-authority, physical-store/machine-correspondence and local-return-copy confinement premises. Timer and Handle populations are distinct; scheduled kernel pauses are not performance measurements.

Firmware graph proofs bind actual installation to independently declared composition and public sealing handoff/policy. Snapshot reachability covers registers, special state and tagged memory; privileged returns require hardware-link ancestry and continuation sites. The retirement supplement passes full recursive checking and proves no selected activation's descendant or full-word return alias survives its post-pop checkpoints. Nonrecursive diagnostics are not substituted. Reset/firmware derive/install exact Seal-only and Unseal-only authorities and clear broad roots; public model/proof checks pass.

Acceptance is the selected bounded acyclic scalar composition. It does not establish arbitrary future writes/repeated activation, universal Sail simulation, physical timing, boot authentication or full installation. Production floating/vector/variadic conventions and M1.2f's complete component/program loop retain owners; compiler-specific receipts remain separate from hosted public validation.

Retained: [`/root/build/lane-unblock-20260921-lowering/target-final-d1d70bd-1/result.json`](retained-evidence/root/build/lane-unblock-20260921-lowering/target-final-d1d70bd-1/result.json); receipt SHA256 `02e4ad3a9b93a9cc14fb2d8e19827c33bd75ea0abac4a7781f1b0445354b6ce0`.

Retained: [`/root/build/lane-unblock-20260921-lowering/cleanup-final-d1d70bd-1/result.json`](retained-evidence/root/build/lane-unblock-20260921-lowering/cleanup-final-d1d70bd-1/result.json); receipt SHA256 `4cfd7a477e16fe0202ab1ca176ee9788c0eb737edae688f228756d60ba75c45a`. Certificate SHA256 `5e6d889b488e9ef01e04b78299e56b0abe5a16cdfa8717be8e8118295aca04c0`.

Retained: [`/root/build/lane-unblock-20260921-values/firmware-handle-profile-1/result.json`](retained-evidence/root/build/lane-unblock-20260921-values/firmware-handle-profile-1/result.json); receipt SHA256 `a37f0c267e152fcd9a8f246e65cda84b531ac706232ab50a8cf831e9ee7bde6c`.

Retained: [`/root/build/lane-unblock-20260921-values/retirement-final-2/result.json`](retained-evidence/root/build/lane-unblock-20260921-values/retirement-final-2/result.json); receipt SHA256 `5a81cdd7b634095107dacbc702c8617b6cc52bf08f2d6a9a871481d672724027`.

Calibration: original midpoint 7.5 h, range 5–10; retained planning weight, cumulative actual n/a. Interrupted/shared integration intervals cannot be reconstructed.

Landed: Tier A, with final hosted validation pending at publication, by the integrator's full read of typed lowering, source and primitive boundaries, final target observations, sealed-authority graph, return/cleanup proofs and their explicit premises.

##### M1.2e-i · Check plan-relative narrowing requests

Contained `1763baa14252d1e4fef96166eaa9446d54a18eaf` qualifies [plan-relative narrowing requests](contracts/compiler-prerequisites.md#3-plan-relative-narrowing-requests). The total decision checks declared parent/granule, byte fields, granule multiples, containment and endpoint addressability. Clause-equivalence, byte/granule, containment/exactness and bounds-round-trip theorems have closed audits and a recursively checked receipt.

Fresh requests include accepted/refused cases and explicit inexact controls; complete-roster/unique-index checks prevent vacuous Sail agreement. Every exported witness region has its own granule/base/length check. Independent source/proof/driver reviews passed. Contained `c105b35` integrates extraction and passes dependency/proof/extraction/compiler builds, retaining the inherited opacity warning.

Finite witness agreement is not universal MemoryPlan/Sail refinement. Actual-plan membership, request provenance and complete emitted-narrowing coverage remain e-ii; the parent stays open. Native integration/campaign artifacts remain under `/root/build/compiler-prerequisites-integration-20260920` and `/root/build/lane-easy-m12e-20260920`; g-i records shared host validation.

Recorded actual: 0.6 h agent-parallel, including independent and integration review.

Landed: Tier A, by full integrator and independent reads of the proof, generator,
source bindings and limitations against the qualification predicate.

##### M1.2e-ii · Enforce plan provenance at every emitted narrowing

The mandatory emitter enforces the total narrowing decision against independent composition/layout/request inputs and actual authority origin. Final-byte census joins every executable narrowing both ways, refusing missing, duplicate, orphaned, stale or invalid obligations; code-local data is separately declared. Physical/type-authority coordinates remain distinct, and equal numeric bits supply no provenance.

The original-C positive executes and passes closed audits/recursive checking. Byte/lineage and owner controls pass as artifact controls, not target-mutant kills. The Handle image supplies a nonempty firmware join with actual reset/derivation, tagged transport and two-parent minting ancestry, plus installed-policy consequence and recursive acceptance. `cunseal` is not executed; the separate Handle-storage execution supplies no second ancestry-kernel result.

These are exact-image census, operand and ancestry results. Unobserved executions and whole-compiler correctness remain outside the receipts; M1.2f owns integrated backend acceptance. Shared build/model/proof/public-host evidence belongs to the preceding joins.

Retained: [`/root/build/lane-unblock-20260921-narrowing/compiler-profile-kernel-1/kernel.json`](retained-evidence/root/build/lane-unblock-20260921-narrowing/compiler-profile-kernel-1/kernel.json); receipt SHA256 `1c6f7b9ee17df4e41ceb1c365fa22c6dbdd1f019b6a4679c025ad2bbe39a01e9`. Generated proof SHA256 `b4ae32014bd3ed6beefafab534272c8191a66333ceabe05430cf92a87226bce8`.

Retained: [`/root/build/lane-unblock-20260921-narrowing/handle-profile-kernel-1/kernel.json`](retained-evidence/root/build/lane-unblock-20260921-narrowing/handle-profile-kernel-1/kernel.json); receipt SHA256 `c10201fab83e662d27d5705cea0232cb5d8a7dd5fbde1334ec19017957225a07`. Generated proof SHA256 `25ae1021c921dee959715ea37dd16309fa8c8b531843d936f1d1adcc2b7e51c5`. Checkpoint export `handle-profile-checkpoints-1/checkpoints.json` SHA256 `1887689073f4e97456f27785209732b410b2a23790f338eda35232667f4e91c2`.

Calibration: original midpoint 3.5 h, range 2–5; retained planning weight, cumulative actual n/a for unrecoverable interrupted/shared intervals.

Landed: Tier A, with final hosted validation pending at publication, by full integrator review of the plan-relative decision, source/build provenance, exhaustive final-byte census, runtime operand equations, root/derivation ancestry, decisive controls and finite scope.

#### M1.2f · Close the acceptance loop, both ends

The integrated scalar backend closes the generated-C, actual-local narrowing and [component comparison](contracts/compiler-component.md) predicates at the 2026-09-25 reference scope. The GC-free authored-C component arm establishes finite functional agreement, not extraction, source refinement or secure compilation. The compiler remains separately licensed and contained; its accepted executable is SHA256 `ecaa5ce0cd29d1099016dc1b62a93d16ecab1fe1bcb3a0e363c2697f6294ddca`.

Seed 20260922 produces 70 accepted programs and 70 perturbed twins, each failing its selected check; ordinary sources agree with the interpreter and profile primitives use their target relation. Complete final-image censuses bind compiler/harness narrowings and installed authority; runtime controls refuse a statically valid request displaced from its actual local. The combined receipt has closed assumption reports and successful `coqchk`. The pre-closeout kernel record SHA256 `f7a52cb8808664b0af762cd3875b81a0f5c5663b40db43ff11c418108fe132d3` is separate from the campaign report's deliberately pending-kernel field. Real alias/parameter-assignment mutants compile, execute and are detected.

Fresh Wasm/purecap components agree at all 84 ordered checks; semantic mutants share the complete failing set and first failure 40. Crossed and single-position corruptions refuse agreement. Producer binding covers the legacy oracle export/libraries, source closure, preprocessed C, wrappers, model and executables before/after execution. Final source/target populations reissue finite joins, not historical universal-boundary/retirement proofs.

Contained `test/verifiedos-acceptance/acceptance-integrated-20260925.json` owns the refreshed records at `255923c89d40da68be5c42b90e585073aab5e2d7`; all campaign images/traces reproduce the preceding run. Independent audit SHA256 `5e5612afff908eacda2b77e7ddde12480666c2b4db416e95620e92047208b9ff` matches the bound integration sources. Simulator SHA256 `25196ad08c3e787363e078269b696476403d8e63348e68a9525f36e02484f793` is bound separately from its model source population. Native compiler/component artifacts remain under `/root/build/lane-backend-accept-20260925/` and `/root/build/lane-compiler-accept-20260925/component-vector-final/`. Host CI [36211211382](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36211211382) passed checkpoint `2f64028d`; delivery owns final hosted handoff. No Guest CI pass is claimed here.

F-449/F-450/F-452/F-454/F-455/F-456 close at these finite boundaries; F-457 retains exact preprocessed-input binding. F-451 leaves the non-frame round trip to M1.7. Portable oracle bootstrap, universal source/target/security preservation, production completeness and downstream boot retain owners. Q34c allocator refinement and M4.4 kernel acceptance remain open.

Retained: [`/root/build/lane-backend-accept-20260925/campaign-kernel-integrated/kernel.json`](retained-evidence/root/build/lane-backend-accept-20260925/campaign-kernel-integrated/kernel.json); delivery records its exact hash. Integration source audit SHA256 `5e5612afff908eacda2b77e7ddde12480666c2b4db416e95620e92047208b9ff`.

Calibration: retained estimate 7 h, original range 4–10; actual n/a. Historical authoring, recovery and review intervals cannot be reconstructed; no measured calibration pair exists.

Landed: Tier A. The component-route ruling, concrete source correspondence, compiler fixes and final-artifact joins receive full review; source compilation and a green host gate alone do not decide those claims.

### M1.4′ · Extend the in-tree assembler and composer to the emitted mix

The bring-up assembler/composer already existed; this item generates its dialect table from the Sail bundle and extends it to the admitted surface. Positional constructor binding joins mnemonic and encoding clauses; parsed guards decide field constraints, refuse unread guards and distinguish extension presence from runtime state. The model owns operand signs/ranges and per-operand guards. `fence` spelling remains authored because the emitted bundle lacks its structured operand run.

The composer emits link-map and entry/escape streams under the shared freeze schema. Emitter intent remains the backend's sidecar obligation; geometry is a run parameter and an empty dictionary reports verbatim escapes. It supplies no freeze admission decision. At the recorded gate, the differential corpus passes and every image is byte-identical to the prior encoder, independently reproduced from exported `8189229`. Host/tool/quarantine gates, type checks and mutation controls pass. **K-88** checks generated table bytes; derived admitted counts follow their owner.

The findings retain configuration-union/site-ID ownership gaps, explicitly refused forms and ignored-output limitations. Generated artifacts and owner references replace transcription mechanisms; the hardened replacement M1.4 remains separate.

  * Seventeen findings.
    * **Repeated mappings need argument-sensitive keys.** Joining `bool_bit` by name alone silently mislabels atomic acquire/release bits; comparison with the prior encoder detects it.
    * **Execution clauses own operand interpretation.** Decode width and printer spelling alone do not establish signedness/range; generation reads execution semantics without changing emitted bits.
    * **Substring scans confuse `signed`/`unsigned` and name prefixes.** Word-bound matching and immediate-only queries close the false register restriction.
    * **`fence` spelling remains authored.** Sail emits its assembly body as unstructured text, although encoding resolves normally.
    * **Generation makes the complete vector table affordable.** No register/profile/plan entry decides whole-surface versus declared-scope encoding; the widening is reported.
    * **Configuration admission has no normative owner.** The generator takes the union of its three declared configurations; that choice remains reported.
    * **Unsupported forms refuse explicitly.** The recorded twelve cover unread vector guards, unsupported bfloat16 operand shapes, forbidden unsigned doubleword and disabled `clmulr`.
    * **Composer site IDs are not yet joined to backend IDs.** Stable unit/ordinal names alone do not establish sidecar correspondence.
    * **Emitted bundle/slot values do not decide FD-2.** The run declares geometry and exercises alternatives rather than inventing a default.
    * **An empty dictionary honestly yields zero hits and verbatim escapes.** FD-1 has no default arm and the composer does not select one.
    * **Untracked build output changes selftest membership.** Ignoring `/build/` keeps disposable emission out of its sandbox corpus.
    * **Producer availability must follow the input schema.** Freeze prose now derives which streams remain absent rather than repeating obsolete ownership claims.
    * **Tests must control ignored-output state.** Forced absence and an independent producer/analyzer join replace a host-dependent literal verdict.
    * **Generator work is paid per selftest sandbox.** Host load/power variation supplies no portable wall-time comparison.
    * **Quarantine release depends on an explicit emission run.** A fresh clone and emitted ignored tree can report different missing-input counts at one revision.
    * **Generated/vector scope changes invalidated corpus prose.** The owning corpus document is repaired; no rule decides prose claims about a Python module.
    * **Restated generated counts need owners.** Document claims derive from the table header; the docstring carries no hand-maintained count.

  * Landed: Tier B under **K-88**, which holds the generated table byte-for-byte against the generator that writes it, running that generator at the gate and not trusting the index. The rule id this item was priced against stays unspent and is not named here, on S14's own ground: [check-rules.md](../../tools/check-rules.md) registers a rule when a check carries it, so an id written in a document and registered nowhere is a citation no reader can resolve. Extending the generated table with a `host` lane is one edit where a rule of its own would have been three and a mutant, and the rule that already exists is the one whose subject this extends.

### M1.5 · Run the CertiCoq-to-Wasm oracle

The [Wasm oracle](../../tools/wasm-oracle/) runs Gallina `demo.v` through released CertiRocq 0.9.1+9.1 and stock Node, returning `true`. The release replaces the prior source pin/compatibility patch and carries the Wasm backend; this refresh is qualified only by the same demo round trip. Its Rocq 9.1.1 dependency is separate from the contained compiler's Coq 8.20.1 environment.

The native switch package/dependency closure was exercised. The container recipe's amd64 base/repository configuration was not tested on the arm64 host. Environment effects were addressed through repository-scoped WSL keepalive and the required proxy trust root. The later WSL Containers GA review kept that route declined: checkout filesystem placement, proxy trust and native hosted toolchain coverage remain the deciding boundaries. [The tool guide](../../tools/README.md#the-lane-as-a-fact-list-and-what-no-provisioner-reaches) owns that posture.

### M1.6 · Stand up GC-free lowering routes

The GC-free route stands up but forks: the proof-transport exit emits non-capability RV32I, while the C-printer/contained-compiler exit lacks a printer theorem and emitted plain RV64 in this measurement. Neither produced an admissible purecap artifact. The route is therefore directed to word/buffer parsers; CompCert-C/VST remains the default, and purecap completion belongs to M1.2.

The supervision-model measurement finds higher-order specification as the blocker, not general recursion or difficult datatypes. The target has neither function values nor indirect calls; most definitions do not cross unchanged. That model is an oracle rather than shipped control-plane code. Register/spec route and proof-transport gaps are reported, not repaired through checklist prose.

The isolated toolchain installs with its own compiler after the `ocaml-system` attempt fails through findlib shadowing. Package licences are read in [THIRD-PARTY.md](../../THIRD-PARTY.md); coq-riscv is BSD-3-Clause, the other incorporated packages MIT. Rust erasure and MCQC are precedents rather than qualified target routes; Rust purecap lowering remains absent. Host/tool/proof/model-typecheck gates passed. No compiler source or probe artifact was incorporated; the measured fork supplies no certified end-to-end lowering claim.

  * Ten findings.
    * **Neither exit combines admitted target and proof transport.** Verified encoded RV32I violates the profile; C printing reaches a candidate backend without a printer theorem.
    * **Higher-order specification blocks the subset.** Structural recursion and nullary enums are cheap, but function values/indirect calls are absent from the target.
    * **The supervision artifact is the oracle, not the shipped control plane.** A successful lowering of it would not decide image correctness.
    * **Replacing a route must re-read its consumer allocation.** The plan is re-pointed to the word/buffer consumer its route list assigns.
    * **Register proof-transport/admission criteria assume both route properties.** The measured split leaves that register act open.
    * **The arena/extraction consumer statement is stale.** The control plane belongs to Vélus; the reserved normative route list needs its owner's act.
    * **`ocaml-system` findlib prioritizes incomplete distribution packages.** A switch-local compiler avoids the observed Zarith shadowing failure.
    * **Shipped datatype examples do not establish lowering.** Many carry no `Derive` or compilation lemma; per-constructor effort is forecast rather than measured.
    * **The derived loop reaches all its required capability-printer stubs.** The contained backend's plain output does not establish purecap admissibility.
    * **Neither exit emits the claimed Clight intermediate.** One goes directly to RISC-V words, the other prints C source; the register/specification gap remains open.

  * Landed: Tier A.

### M1.7 · Boot purecap Gallina hello-world on the M0 emulator

The [maintained hello recipe](../../tools/bedrock2-lowering/HELLO.md) derives Gallina through Rupicola to Bedrock2, checks closed assumptions/kernel acceptance, and compiles emitted C plus the client with the accepted purecap backend. Its theorem ends at Bedrock2; printer/compiler/source-to-binary refinement is not claimed. No external runtime/helper body enters distributed assembly.

Recorded native runs store/reload intact tagged pointers in all dedicated image-data slots, excluding frames. The exact corpus predicate passes with `Hello, world!` plus newline, successful HTIF and no failed check. Independent integration reproduction gives assembly SHA256 `e126ecf0e0ef047c2669881fc5cd18955f0900d87d86ee4a32897c1c14b97975` and ELF SHA256 `bb5ccdfae4b64bfcc30c95d125477ca7d7fc8a3820da710598e0b770790811d0`; source/tool/model/output/trace identity and freshness are checked.

All three greeting/tag/store mutants compile, execute and are detected. Focused host tests hold receipt/trace handling, including separate terminal output and successful process exit; a corrupted trace was not accepted by refreshing its digest.

Calibration: original estimate 9 h, range 6–12; retained estimate, actual n/a. Historical trace-check intervals are missing; the later fan-out interval supplies no cumulative actual.

Landed: Tier A. Review read the generated client, derivation boundary, slot
ownership and exact corpus predicate. Host CI and both Guest CI lanes are the
settled batch's validation handoff; a pending Guest CI run supplies no verdict.

#### M1.8a · The instrument, its two renderings, its gate, and the checker rule

The [freeze instrument](../../tools/quarantine/freeze.py) and [report](../../tools/quarantine/freeze-report.py) implement the declared corpus, recipe, decision variants, joins and predicates. Both renderings derive from one record; absent operands name pending symbols. Value, n/a, pending and fixture are distinct, and synthetic fixtures cannot clear measurement predicates. The ordered recipe/decision passes remain explicit.

**K-77** checks contract/instrument enumerations and declared relations in both directions, with relation floors and mutants; column schema/predicate behavior is held separately by tests. The recorded report decides four predicates and defers eight with all three producer inputs absent; none rejects. Host/tool/typecheck gates and seeded predicate controls pass. No WSL/model evidence was taken.

Geometry break-even arithmetic directs later measurements but supplies no observed acceptance. Missing defaults/selection predicates and producer transport remain contract obligations; this instrument does not invent verdicts for them.

  * Eleven findings.
    * **The instrument is derivable before backend milestones.** The contract owns its schema/corpus/thresholds; a backend supplies transport.
    * **Recipe order and decision order differ in granularity.** Both are implemented; normative prose could name the distinction explicitly.
    * **Per-site image interpretation needs composer geometry.** Bytes plus entry/escape table preserve the joint measurement without assuming FD-2's answer.
    * **Break-even geometry arithmetic is not observed acceptance.** The 64-bit candidate fails the stated break-even bar, 256-bit clears it, and 128-bit needs low realized packing loss.
    * **Deferred predicates need active negative controls.** Each seeded defect must reject by name; fixture/deferred output alone demonstrates no body.
    * **Prose column paragraphs mix vocabularies.** Tests own column schema; K-77 cannot treat every backticked token as a column.
    * **FD-2 states no default.** The instrument reports n/a rather than treating the reference geometry as a decision.
    * **Relations need union-quantified comparison.** Equal ID rosters alone miss undeclared pairings; declared parameters bind per decision.
    * **Document floors do not detect a removed rule comparison.** Relation-size floors and separate mutants protect both joins.
    * **Checker ownership follows the index.** Shared parsing must use `Context.text`, not an off-corpus file left on disk.
    * **No declared CI predicate checks S6 re-selection inside each variant.** The record exposes it; adding the predicate belongs to the contract.

### M1.9 · Two-class static memory plan and placement WCET delta

[MemoryPlan.v](../../proofs/MemoryPlan.v) states static placement, representability and second-class code WCET deltas as admission inputs. The completion audit adds whole-plan `plan_timing_admission`: a complete region roster, per-slot accumulation and one charged-frame admission. The older one-region probe is not a whole-plan verdict. Lemmas establish accumulation/charged-frame obligations; computed controls cover combined overruns, exact budgets, separate slots and omitted/nonexistent members. Source-path fetch evidence and executable integration remain producers' obligations.

Historical acceptance at `81892291` compiled the artifact without axioms or admissions and killed all 461 seeded weakenings, none surviving/stillborn. The vector oracle contributed no kills because it did not reach this artifact; the prover supplied the result. Host/mutation/typecheck gates passed. That campaign does not validate the new whole-plan definitions; their recorded validation is `run.py proofs`, focused memplan tests and the host batch.

No lowering/emulator execution or whole-system verification is claimed. Composition magnitudes remain explicit witness fields, and register-owned enumeration, placement, pool, live-range and disjointness gaps retain their findings. The completeness/range repairs close decision-procedure bypasses without inventing those normative inputs.

  * Eleven findings, seven of them register gaps reported rather than closed.
    * **The complete region-kind enumeration is unspecified.** Its inductive follows named/by-criterion register arms; closure belongs to R-15-247s.
    * **Per-region versus per-task delta ownership is unspecified.** The historical probe priced one region; R-15-247j owns the norm for multi-region tasks.
    * **Hard-task reachability of cold second-class code is unspecified.** A region-kind placement rule supplies no call-graph guarantee; R-15-247j owns it.
    * **Origin-pool member regions are not enumerated.** The ceiling theorem quantifies over supplied rosters; R-14-015/R-14-009 own the missing norm.
    * **The live-range ordering/unit is unspecified.** The artifact uses nat intervals without claiming a unit; R-08-011 owns it.
    * **R-08-014's literal disjointness quantifier opposes the intended sharing rule.** The two readings are refuted by distinct witness plans; the register act remains open.
    * **Composition magnitudes are explicit fields.** Demo witnesses make no physical composition claim.
    * **The vector oracle reaches none of this artifact.** Every historical mutation kill is the prover's, not independent generated-vector evidence.
    * **Unrelated proofs were recompiled per mutant.** Dependency-closure compilation later answers the tool cost without changing this campaign's result.
    * **Interrupted whole-population attempts provide no complete verdict.** The accepted operator partitions cover exactly the full population; lease/incremental-report repair belongs to tools.
    * **An unowned line-count figure was miscounted.** Closing evidence re-measured it; no rule derives proof-source line counts.

  * Landed: Tier A.

## M2 · Fast emulator, struck

### M2.1 · Fork CHERI-QEMU and narrow compressed capabilities

The separately contained format/library experiment pins compressed-cap `78a34ba5` and CHERI-QEMU `d0bb921c` (QEMU 7.0.0). Its 64+1-bit instantiation agrees with 21,546 Sail-generated vectors and all format properties; the narrowed library passes its complete existing suite. This tree retains gitlinks, not the experiment's source or locally measured artifacts.

The library implements the profile's explicit exponent, enumerated permission lattice and 36-bit address inside a 64-bit capability. Unsupported fields/accessors remain absent so consumers fail compilation rather than receive invented defaults. Full `qemu-system-riscv64cheri` never linked; consumer adaptation/configure dependencies remained M2.2 work. The Rust device-model option was refused at that old base, pending a future re-pin.

[THIRD-PARTY.md](../../THIRD-PARTY.md) owns the QEMU GPL and separate BSD-2-Clause library readings. Emulator code remains in its own repository as a development instrument; no shipped image embeds it and no part is vendored here. The milestone and follow-up emulator work are struck.

  * **Finding, about the algebra rather than either implementation: `setCapBounds`'s containment property holds over a domain that nothing states.** The domain is a requested top at or below 2^36; above it the decoded top wraps below its own base, so the derived region does not contain the requested one. The model does the same and the cross-check agrees, so it is no divergence, and it is unreachable with a tag: `CSetBounds` clears the tag on precisely the test that fails there. Owed: **R-15-007a's representation-correctness proof states the condition** rather than carrying containment unconditionally, and the format's `$[test]` harness reaches that edge. Reported, not closed: no register entry governs this item.

### M2.2 · Implement the frozen decode surface and bespoke machine

* Struck in the checklist; no landing note was recorded.

### M2.3 · Add VLEN=4096 RVV, matrix, and FEC datapaths

* Struck in the checklist; no landing note was recorded.

### M2.4 · Reach corpus lockstep with M0 and boot M1 hello-world

* Struck in the checklist; no landing note was recorded.

## M3 · Boot chain

### M3.1 · Add RoT configuration and peripherals to the curated Sail tree

Added RoT lifecycle/fuse, entropy, counter and watchdog register slaves plus a same-model RoT composition. K-65 checks cross-configuration consistency and K-78 checks core-class features against the model. Build, properties, corpus, validator refusals, devicetree and host checks passed. The watchdog correction tests inclusive expiry, large advances and absorbing bite; independent event-source/reset wiring belongs to M3.5. Deterministic entropy replay/source qualification retain S5/S6 owners, and tools still lacked a configurable RoT loop at this landing.

  * Eight findings.
    * **`vlen_exp` cannot say *vectorless*.** The knob is Sail **type**-level and constrained `3 <= vlen_exp <= 16`, so zero cannot mean *no vector register file*; and every `Zvl` rung is gated on `sizeof(vlen_exp)` **alone** with no vector-support conjunct, where the eight vector-crypto flags are each refused by name at load.
    * **The seeded PRNG evades the deterministic-replay obligation rather than discharging it.** R-15-241 requires every draw accounted for in the replay nondeterminism record, R-16-015 puts every draw from the entropy root in that record's secret class, and R-16-017 requires a secret draw be recorded as a sealed commitment and **never as a value**.
    * **One validator arm was dead the moment it was written, and firing the seeded refusals found it.** The noise-source *ceiling* is the type's, `plat_rot_noise_sources` being read at `range(0, rot_max_noise_sources)` which the emission writes into the schema as a maximum, so an over-wide declaration is refused at schema conformance before `config_is_valid` runs.
    * **The watchdog carries no ratio to the spine, and that is a requirement, not an omission.** R-15-196 makes the RoT's independent slow clock one of exactly three genuinely asynchronous boundaries, *none modeled as fixed-latency*.
    * **The two fail-closed seams compose, as a consequence and not a third rule.** The pet's challenge comes from the entropy root, a predictable challenge being one a wedged core can compute ahead of time (R-15-240), so a latched health-test failure leaves no challenge to answer and the watchdog bites.
    * **The corpus member's ground differs from M0.8c's.** M0.8c installed its region inside the property because no shipped configuration had the structure; here every configuration has the four windows, so a C-class program reaches them from the outside and every check is a refusal.
    * **The attested tree's device windows ride R-15-002b, not R-09-007**, and the memory sequencer's node was already in that position.
    * **The model stops at the gate, and R-15-078 says so.** *The Sail model carries the gate rather than a model of the debugger* is that entry's criterion, so what is here is the predicate its RTL refinement obligation quantifies over, `no DM transaction reaches the fabric in the production state`.

### M3.2 · Specify RoT firmware in Gallina

[RotFirmware.v](../../proofs/RotFirmware.v) specifies measured boot, lifecycle, entropy failure, attestation and debug liveness, with inhabited parameters and discriminating alternative constructions. Native audit accepted 476 file constants with empty assumptions; host checks passed. The 244 mutation detections came entirely from prover refusal: vector and QuickChick harnesses reached none of this file. This accepts a specification, not executable firmware; M3.5 owns realization and target joins.

  * Five findings, every one a register gap reported rather than closed.
    * **Where the entropy verdict is extended against R-09-029's boot-target latch is unfixed.** R-09-037 fixes the lifecycle extension first and R-09-006a the verdict before any measured stage draws; neither orders the verdict against the latch, which R-09-029 measures *like every other input* without saying where.
    * **Whether the chain measures each stage before running it or the payload up front is unfixed.** R-09-002 fixes only the pairwise precedence and R-09-006 has the ROM place the verified M-mode image before releasing the boot core, the front-loaded shape for one stage and silent about the rest.
    * **What a successful boot does to the boot-attempt count is unstated.** R-09-028 states the counting with automatic revert and R-09-006a takes the entropy halt out of it as a §16 fault class consuming no attempt; no entry says whether a success clears the count, so the outcome enumeration here is that entry's two failure classes and nothing models a success.
    * **What the reference integrity manifest covers where it differs from the quote is unstated.** R-09-026 makes it the dual *covering the same vector*, so the appraisal is stated over whatever vector the quote covers and no manifest-side enumeration is invented.
    * **Whether R-09-025's *this set* is four terms or five is unfixed, and this file takes a side.** The MUST has attestation cover the chain and the discipline both; the criterion says *the quote's vector*, which is not the quote, and *this set*, which can name the four terms the colon introduces.

  * Landed: Tier A.

### M3.3 · Specify M-mode firmware in Gallina

[MModeFirmware.v](../../proofs/MModeFirmware.v) specifies initialization refinement, root derivation, quiescence and initial entry, including a build-time/installed-state counterexample. Native audit accepted 132 file constants without assumptions; seeded weakenings and host checks passed. It executes no firmware. M3.5 retains initialization, capability installation and real kernel handoff.

  * Six findings, every one a register gap reported rather than closed.
    * **Which codepoint names which permission set is unfixed.** R-15-007b enumerates the lattice *at freeze time* and no artifact in this repository carries the enumeration, so every W^X obligation is stated of an arbitrary decode.
    * **R-14-002's normative clause states the mechanism its own criterion demotes.** The MUST line grounds the invariant on monotonicity plus a machine-checked absence of Store and Execute *in the static initial capability distribution*; the criterion discharges it **at the permission encoding** and keeps the distribution check only as redundant confirmation, and R-15-007l goes further, R-14-003 no longer needing monotonicity for the intra-capability half.
    * **What *running kernel state* comprises is unstated.** R-07-028 obliges the firmware to instantiate exactly the composed cap graph as running kernel state, and no entry says whether the partition contexts R-07-015 restores and the schedule table R-11-024 swaps are inside that phrase or beside it.
    * **What completes a core's root set is unstated.** R-07-019 has the firmware derive each core's partition-bounded root and R-07-006 fixes the bound; R-15-007p makes it a permission-split set over the image's text and data extents, and no artifact here distinguishes text from data at a region.
    * **R-07-024's criterion audits an inventory no artifact carries.** Nothing enumerates the resident-code inventory, not the register, the prose, `proofs/`, the model or the corpus, which is R-07-031a's shape one entry over and closes the way R-07-031b did.
    * **R-05-091's Tier-0 proof has no owner.** The entry puts the no-ambient-state obligation on the firmware as ordinary Tier-0 proof over its statically planned state; no artifact here is that proof and no item authors one.

  * Landed: Tier A.

#### M3.4a · The cryptography licence reads, and SHA-3 in Gallina

Read the crypto/oracle licences at their pinned sources and authored [Keccak.v](../../proofs/Keccak.v)'s SHA-3 functional reference. Native audit accepted 186 file constants without assumptions; all 166 live weakenings and host checks passed. Licence dispositions remain in [THIRD-PARTY.md](../../THIRD-PARTY.md). This supplies functional statements, not binary constant time, masking or target implementation; unresolved suite/oracle and permutation obligations remain findings.

  * Twelve findings, eight of them acts owed elsewhere and reported rather than closed here.
    * **The VST opam route does not avoid the term it is chosen to avoid, and does not carry the developments it is chosen for.** Read at `f384d2db`: `coq-vst.opam` depends on `coq-compcert >= 3.15 < 3.17~`, declared `"coq-compcert" {>= "3.15" & < "3.17~"}`, so the opam route installs a CompCert into its switch exactly as the CertiRocq oracle's package does; what the route avoids is *tracking* `compcert/` and `compcert_new/`, not conveying the term.
    * **No entry fixes the oracle pair for an authored SHA-3.** R-15-058 names FIPS 202 and the ACVP vectors as the differential oracle for the *Sail* unit and `Zvbb`/`Zvbc` software Keccak as the reference; the parent cell wants two oracles of independent verification lineage; nothing decides which two an authored Gallina primitive takes.
    * **The item's own title named one classical signature and the frozen suite carries none.** R-05-058c splits by verifier with SLH-DSA at every ROM-verified object and ML-DSA above it, and R-05-058a freezes the parameter sets at Category 5 throughout.
    * **Which AEAD the Gallina module owes is unfixed between two documents.** The parent cell has both AEADs authored in Gallina; R-10-024 freezes the cipher to AES-GCM, "one cipher and not a menu", with ChaCha20/Poly1305 the frozen-out alternative.
    * **R-05-059's acceptance audits a crypto inventory no artifact carries.** The entry wants three evidence entries per primitive and a primitive missing any layer not shipped.
    * **R-05-060's acceptance has nothing to audit, and the pin is not the trace.** The entry wants every field-arithmetic implementation to trace to a Fiat-Crypto derivation; pinning the tree and reading its terms is not a derivation, no generator has been run and no emission is tracked, so no field-arithmetic implementation exists for that clause to audit.
    * **A hash-separation field stated at the chain's scale, not a total one.** [RotFirmware.v](../../proofs/RotFirmware.v)'s Machine declares `extend_separates_on_the_chain`, the finite instance of R-05-058c's computational hash-only assumption at the scale the chain uses it: at each of the seven digests the chain extends from, the seven item codes extend to seven distinct digests.
    * **Theta's invertibility is the one clause of the artifact's own permutation claim it leaves open, and no register entry owes an act for it.** R-15-056's acceptance reads whole "it clears all five admission tests; its correctness is a Sail invariant (fixed theta/rho/pi/chi/iota rounds, no tables, no secret-dependent control flow) riding RTL ⊑ Sail".
    * **A differential pair whose two halves are held together by nothing is two transcriptions, and the obstacle to holding them was imaginary.** Both files ship the same published constants and each gate, green on its own copy, decides its own transcription against that copy and says nothing about the copies agreeing, so a constant edited on one side alone leaves both passing with the pair's purpose gone.
    * **The Gallina vector harness reaches no artifact of this item, so the whole mutation score is the prover's.** `tools/quickchick/Vectors.v` and `Properties.v` compute nothing this file defines, the shape M3.2 met one artifact earlier: what killed a weakening here was a shipped statement, never a generated input, and the validation half is not priced as generated.
    * **The ACVP repository states its terms in a README because it carries no licence file**, and the conditions are three, not the two the parent cell stated: notice retention, a change notice on a modified work, and explicit acknowledgement of NIST as the source.
    * **The recorded actual is not an outturn against the deliverable the estimate was taken over.** This item shed four of the parent cell's deliverables into a new sibling at exit, not at entry, so the 9.5 h estimate was priced over a scope this landing did not carry and M3.4c was priced at 14 h of it.

  * Landed: Tier A.

Related findings: F-187.

#### M3.4c · The rest of the classical suite, and the Fiat-Crypto generator run

The aggregate classical-reference/emission scope is covered by M3.4c-i and M3.4c-ii; AES-GCM belongs to M3.4d. Children retain their evidence and costs, with no duplicate parent actual. The signature artifact supplies no executable SLH-DSA verifier. Target refinement/timing remain consumer work, while assembled interface, Wasm validation and F-205g hash binding stay open. F-205d's suite disagreement still requires register disposition.

Landed: Tier A.

#### M3.4c-i · SHA-256, HMAC-DRBG-SHA-256 and the boot verifier's signature statement in Gallina

[Sha256.v](../../proofs/Sha256.v) and [HmacDrbg.v](../../proofs/HmacDrbg.v) supply classical functional references; [RomVerifier.v](../../proofs/RomVerifier.v) supplies the frozen signature's substrate and verifier statement, not SLH-DSA's algorithm. The VST acquisition routes were refused on prover compatibility and available content. Native audit accepted 216/145/163 constants with empty assumptions and kernel recheck; published answers, survivor-driven statements and host checks passed. No binary, target refinement, constant-time, masking or computational reduction is accepted.

  * Five findings, two of them register acts reported rather than closed here.
    * **R-09-005a's permutation figure is not convicted or discharged by a call count.** The census bounds permutations from below and never from above, so a lower bound of 764 calls neither establishes the entry's figure nor refutes it, and the `Example` that computes it says calls in its own name, not permutations.
    * **The comment at [proofs.py](../../tools/vos/cli/proofs.py):435-437 justifies its ordering on a promise the ordering does not keep.** It puts rocqchk last because a witness the artifacts do not carry is "worth reporting in seconds rather than after a re-check of the whole tree", but `scan_witnesses` runs inside the compile loop and its verdict is reported only after every file has compiled.
    * **[THIRD-PARTY.md](../../THIRD-PARTY.md)'s Fiat-Crypto build section stated two claims false against the tree it measured.** `rewriter` does carry licence texts, `COPYRIGHT` naming three arms with `LICENSE-MIT`, `LICENSE-APACHE` and `LICENSE-BSD-1` beside it, so only a search for a file named exactly `LICENSE` finds nothing; and a zero of built objects was stated over `bedrock2/src`, a path the recursive checkout does not carry at all, where the tree `SKIP_BEDROCK2` declines is `rupicola/bedrock2/bedrock2/src`, present with 151 `.v` files and no `.vo`, beside `rupicola/src` with 66 and none.
    * **A thirty-two-bit shift probe spelled as one `nat` literal is a unary numeral the evaluator materializes before it shifts.** That reading took the guest VM down twice before the cause was found.
    * **The proof gate's runtime now exceeds the default command timeout an agent session applies to a foreground command, and its failure under a kill is silent.** The gate reports 5,180 constants over 21 files where it reported 4,656 over 18, and a killed run prints neither a `FAIL:` line nor a rocq diagnostic, so it reads as a proof defect.

#### M3.4c-ii · The Fiat-Crypto generator run and its tracked emission

[The emission record](fiat-crypto-emission.md) binds the Fiat-Crypto pin, reviewed nested licences, successful build/generator identity and two incorporated 32-bit 25519/P256 headers. Independent execution of the same generator reproduced every raw/wrapped byte; this was not an independent toolchain build. Both interfaces compiled and 6,786 results agreed with an integer oracle; focused source/mutation checks passed. Unexercised helpers, complete protocols, target refinement, constant time and WCET remain outside acceptance. The 2.4 h cost is a conservative overlapping upper bound, excluded from calibration.

Landed: Tier A.

#### M3.4d · The AEAD in Gallina

[AesGcm.v](../../proofs/AesGcm.v) supplies the AES/GHASH/GCM functional reference with published answers and discriminating alternatives. Native audit accepted 242 file constants without assumptions; host checks and the declared sample of 40 weakenings passed. Its prover was the whole mutation oracle because the vector harness reaches none of this file. MixColumns bijectivity and the Sail/Gallina table join remain open; binary constant time, masking, target execution and computational security are not claimed.

Calibration: no original estimate was recorded; excluded from the fit.

  * Twelve findings, eight of them register acts reported rather than closed here.
    * **No entry fixes the symmetric key length.** R-10-024 names the cipher and stops.
    * **No entry fixes the tag length.** SP 800-38D admits 128, 120, 112, 104 and 96 bits generally and 64 and 32 for named applications only; R-10-022 makes the tag the stored checksum and fixes no t.
    * **No entry fixes the nonce length or which initial-counter construction is taken.** SP 800-38D splits the two at a 96-bit nonce, the short arm a concatenation and the long one a GHASH of the nonce and its length.
    * **No entry carries the per-key invocation bound.** SP 800-38D bounds the invocations of the authenticated encryption function under one key, and no entry in this register states a bound of any kind; R-05-126b's linear nonce grade forces freshness and not a count.
    * **What a per-extent AEAD authenticates besides the extent is unstated.** R-10-022 and R-10-022a say where the nonce and the tag live and say nothing about the associated data, where an extent sealed with none and one sealed with its own address open differently against the block services R-10-021 puts below the integrity line and leaves free to move a block.
    * **One entry names two tag constructions and another freezes one of them out.** R-10-022 writes *the Poly1305/GHASH tag serving as the stored checksum* where R-10-024 freezes the cipher to AES-GCM and ChaCha20/Poly1305 out.
    * **The constant-time entry's enumeration names a primitive the frozen suite does not carry.** R-05-067 lists Keccak, AES, ChaCha and the lattice NTT and samplers as the control-flow-heavy primitives hardened and then verified on the artifact, and ChaCha is what R-10-024 freezes out; those two entries are the only two in the register that name it.
    * **No entry fixes the oracle pair for an authored AEAD**, as none fixes it for an authored hash: R-15-058 names FIPS 202 and the ACVP vectors for the model's Keccak unit and nothing names anything for this one, while M3.4's own cell wants two oracles of independent verification lineage and decides neither.
    * **The differential pair this file claims is held by no rule.** One file derives the tables the curated model transcribes and each gate decides its own side, so a table edited on one side alone leaves both gates green and the pair silently reduced to two transcriptions.
    * **MixColumns is the one step map not shown a bijection**, so the composite claim that AES is one is an obligation this file states of itself and leaves open: no prelude-only proof of the linearity step between the algebraic unit and the spanning-set round trip was found inside this item.
    * **A published literal is recomputed before it is written down, or it is a transcription and not a known answer.** Every constant this file quotes was produced twice and held equal before either reached the file; a single-source literal makes the check that quotes it a check against the transcriber's memory.
    * **Three seeded weakenings survived across two samples, and every one was a site nothing above it decided.** The key expansion's *Nk greater than six* guard is the first: `6 < Nk` and `7 < Nk` agree at 4, at 6 and at 8, so no key length FIPS 197 admits can part them and every published vector accepts the six one higher.

  * Landed: Tier A.

Related findings: F-205d.

### M3.5 · Reach the machine-mode kernel through measured boot

M3.5a accepts the host release predicate and M3.5b the finite target chain. The final target campaign releases through the RoT, measured M-mode bytes and kernel verifier under [the boot-handoff contract](contracts/boot-handoff.md#9-the-target-chain). Child records own their tested revisions, receipts, retained estimates and limits; no earlier partial checkpoint substitutes for the final chain evidence.

Landed: Tier A.

Retained evidence: [`/root/build/lane-bootchain-20260927/boot-release-target/report.json`](retained-evidence/root/build/lane-bootchain-20260927/boot-release-target/report.json).

Related findings: F-443, F-434, F-435, F-436, F-437, F-438, F-439, F-440, F-441, F-442, F-394.

#### M3.5a · Bind real signatures to the measured host release

The [release harness](../../firmware/README.md) uses actual SLH-DSA-SHAKE-256s over disposable lifecycle roots, including signed-prefix race and release ordering. At code revision cda686d1, all 28 cases and 102 SHAKE comparisons passed; the separate crypto campaign passed 140 records. Source/emulator identity and abnormal-process refusals were reviewed. The stage runs on the host; the cut-off RoT target trial is not a pass, and M3.5b owns actual target execution. Historical authoring intervals are irrecoverable; the 3 h estimate, range 2–4, remains a planning weight with actual n/a.

Calibration: split estimate 3 h, range 2–4; retained estimate, actual n/a.

Landed: Tier A. Independent review read the callback, race, source binding,
failure handling and capability producer. The settled batch retains the Host CI
requirement and both Guest CI lanes; a pending guest run is not counted as passed.

Retained evidence: [`/root/build/critical-fanout-20260926/boot-final/report.json`](retained-evidence/root/build/critical-fanout-20260926/boot-final/report.json) (SHA-256 `b7fe77239e81f8c3e896674af35936e1f0a15654c03875052a8f134a5b4fc889`).

#### M3.5b · Lower and compose the remaining measured boot chain

[The target chain](contracts/boot-handoff.md#9-the-target-chain) executes ROM measurement/signature release, runtime watchdog/reset/A-B recovery, separately signed M-mode verification and main-die kernel verification. [Run 37103959681](https://github.com/symbiogenesis/VerifiedOS/actions/runs/37103959681) passed all fifteen cases at 46c9ecef, with joined source/crypto identities reviewed. Receipt fields remain milestone_acceptance: open; this note records acceptance against the contract. [Section 9.15](contracts/boot-handoff.md#915-what-the-predicate-does-not-decide-and-findings) retains concurrency/privacy, response-authentication, timing, production reset, counter clearing/root enrollment/reset-vector, item-7 and kernel-acceptance limits. The 8.5 h estimate, range 6–11, remains retained because complete cross-session authoring intervals were not captured.

Calibration: split estimate 8.5 h, range 6–11; retained estimate, actual n/a. The contract, model, RoT, M-mode and campaign lanes ran as agent-parallel worktrees across sessions whose authoring intervals were not recorded, and the hosted campaign's wall-clock time is execution rather than effort.

  * Three findings.
    * **The eleven shards of one run built eleven distinct simulators from one model source map.** Every shard's simulator and build-receipt digests differ, where the runs F-720 records agreed within each run.
    * **The main-die ML-DSA-87 runs nearly reach section 9.14's sizing.** They took 404 to 568 s, the slowest at 95% of the 600 s per verification the section sizes and 32% of the 1,800 s main-die timeout; the boot runs that release took 6,930 to 7,224 s, at most 60% of the 12,000 s boot timeout.
    * **The watchdog challenge read after arming is one value in every boot run that arms.** All five read 14413068468049837094, the composition's seeded entropy source giving every boot the same value, so the campaign shows the challenge nonzero and not that it varies between boots.

  * Landed: Tier A. The integrator read every shard receipt against section 9.12's table and the joined receipt's freeze against the crypto manifest before recording acceptance. The landing revision follows the Host CI and Guest CI handoff; a pending guest verdict is not counted as passed.

Retained evidence: [`out/boot-chain-target/37103959681/report.json`](retained-evidence/out/boot-chain-target/37103959681/report.json) (SHA-256 `67c0ecdb285f2e3c31479e344393ae9af2fc3621f6f180852ead68a847dd84fa`); [`out/boot-chain-target/37103959681/cold-boot/report.json`](retained-evidence/out/boot-chain-target/37103959681/cold-boot/report.json); [`out/boot-chain-target/37103959681/recovery-latched/report.json`](retained-evidence/out/boot-chain-target/37103959681/recovery-latched/report.json); [`out/boot-chain-target/37103959681/revert-past-bound/report.json`](retained-evidence/out/boot-chain-target/37103959681/revert-past-bound/report.json); [`out/boot-chain-target/37103959681/entropy-halt/report.json`](retained-evidence/out/boot-chain-target/37103959681/entropy-halt/report.json); [`out/boot-chain-target/37103959681/lifecycle-raw/report.json`](retained-evidence/out/boot-chain-target/37103959681/lifecycle-raw/report.json); [`out/boot-chain-target/37103959681/runtime-signature-corrupt/report.json`](retained-evidence/out/boot-chain-target/37103959681/runtime-signature-corrupt/report.json); [`out/boot-chain-target/37103959681/runtime-digest-mismatch/report.json`](retained-evidence/out/boot-chain-target/37103959681/runtime-digest-mismatch/report.json); [`out/boot-chain-target/37103959681/mmode-below-floor/report.json`](retained-evidence/out/boot-chain-target/37103959681/mmode-below-floor/report.json); [`out/boot-chain-target/37103959681/mmode-signature-corrupt/report.json`](retained-evidence/out/boot-chain-target/37103959681/mmode-signature-corrupt/report.json); [`out/boot-chain-target/37103959681/main-die/report.json`](retained-evidence/out/boot-chain-target/37103959681/main-die/report.json); [`out/boot-chain-target/37103959681/watchdog/report.json`](retained-evidence/out/boot-chain-target/37103959681/watchdog/report.json).

Related findings: F-738, F-745, F-721, F-722, F-746, F-756, F-758, F-762, F-766, F-770, F-771, F-772, F-773.

#### M3.6a · State and refute the ordered sequence

[DischargeSequence.v](../../proofs/DischargeSequence.v) states reset hold, tag discharge, worst-corner dwell, single completion read, fail-stop and sanitization order. Inhabited parameters and generated alternatives discriminate those obligations. Native audit accepted 76 file constants without assumptions; seeded weakenings and host checks passed. It is a statement artifact without device execution; the register subsequently answered the five reported decisions.

  * Five findings, every one a register gap reported and not closed; the register has since taken all five.
    * **R-15-247d's data-plane disjunction had no arm selected, and the §11 budget read differently on each.** The entry has the data plane deterministically cleared *or* its discharge confirmed, R-15-247b commits both planes atomically at the granule so one pass would satisfy it, and R-17-024a insists the two are two boundaries.
    * **The completion indication's arity against the bank staggering was unstated, and the silence was observable rather than harmless.** R-15-247f states a single read and R-15-247g stages the discharge in phases over banks; one read per transition, one per phase and one per bank are three §11 terms and three degrees of partiality visibility.
    * **R-15-247d's acceptance clause is a necessary condition and not its criterion, found by writing the proof.** *No path admits a partially sanitized bank* is stated of a bank the pass reached and did not finish, so a bank nothing reached satisfies it, and the reader that **is** that clause is shown to admit an undrained domain.
    * **R-15-247h's reset hold had no scope, and R-15-190 was where the two readings parted.** The entry held every application core, DMA engine and capability-bearing fabric initiator in reset while the sequencer ran; R-15-190 keeps exactly one island live across standby with R-15-192 running paging reception on it as an admitted hard task, and R-15-190a admits a bulk domain taken OFF at that transition.
    * **Where the fail-stop latch lives was unstated.** R-15-247f and R-15-189n both latch on a negative reading and neither said in which power domain the latch sits, which matters because R-15-247q puts the discharge on the path that collapses the rail.

  * Landed: Tier A.

## M4 · Kernel

#### M3.4b · ML-KEM and ML-DSA in Gallina

[The functional reference](../assurance/pq-reference-contract.md) supplies PqArith transforms/codec inverses, ML-KEM-1024 and ML-DSA-87. Native audits and kernel rechecks accepted their closed statements; official/hash/refusal campaigns, generated signatures and independent OpenSSL comparisons passed. Twenty-one compile-valid semantic mutants were detected with no survivor or stillborn. [ML-KEM](../../proofs/campaigns/MLKEM-README.md) and [ML-DSA](../../proofs/campaigns/mldsa-reference.md) own pins, hashes and replay limits. No general multiplication correspondence, security reduction, universal failure bound, binary constant time, masking, production entropy, target refinement or Wasm integration is accepted. The 5.1 h overlapping session bound is excluded from calibration.

Landed: Tier A.

### M4.1 · Decide revocation sweep quanta

Declined quiescent-point sweep restructuring and retained R-08-007's incremental/preemptible background-slot discipline. [The alternatives record](../background/architectural-alternatives.md) owns grounds and reopening evidence: bitmap revocation is not reachability tracing and this design claims no mutator-overlap property for the proposed rule to discharge. Decision review/checker passed without a register/co-read change.

### M4.1a · Decide the kernel-specification provenance fork

Chose an authored kernel specification derived from this repository's design. Reviewed seL4 spec/proof objects are GPL-2.0-only and were not translated or incorporated; [THIRD-PARTY.md](../../THIRD-PARTY.md) records object-level terms and declined arms. The decision preserves clean specification ownership rather than importing incompatible derivative content.

### M4.1b · Decide the kernel-C provenance fork

Chose authored kernel C against the local Gallina specification. S7's file-level licence read rules out incorporating CHERI-seL4/CHERI-Microkit kernel sources under this tree's terms. [THIRD-PARTY.md](../../THIRD-PARTY.md) records the refused source and alternatives; implementation forfeits the maintained-code start-from. This is a provenance decision, not completed C implementation.

  * Landed: Tier A.

#### M4.2a · The partition context, the switch, and the cyclic-executive schedule

[PartitionContext.v](../../proofs/PartitionContext.v) and [CyclicExecutive.v](../../proofs/CyclicExecutive.v) specify scalar restore/pending state, switch costs and schedule admission with arbitrary composition parameters and non-vacuous refutations. Native audit accepted 85 file constants without assumptions; seeded weakenings and host checks passed. Neither artifact executes a switch. S1's later register decisions are carried back at S25.

  * Eight findings.
    * **R-07-031a's acceptance criterion audits an artifact that does not exist.** The criterion reads *the invocation list is enumerated and closed*, and no artifact here carries that enumeration: not the register, the spec, `proofs/`, the model or `corpus/`.
    * **R-07-029 and R-07-037a state incompatible things about the same act, and R-12-096 adds a third voice.** R-07-029 makes IPC synchronous endpoints; R-07-037a makes a compartment run to completion *with no blocking call*; R-12-096 has a ring consumer *sleep*, a word the register defines nowhere.
    * **Whether the R-07-037b rotation swaps R-07-044's pending bits is unstated, and the silence is observable rather than harmless.** R-07-037b has the intra-slot step *swap register and partition context* and R-07-044 states its discipline at the switch; neither says what the rotation does with the interrupt-file pending bits.
    * **A same-label group member begins its reaction on state the rotation does not clear, and no entry says what it may assume about it.** [The profile](../hardware/isa-profile.md) makes the vector CSRs zeroize rather than save, R-07-014c makes `vmclear` the one instruction that clears them, and R-07-037b's intra-slot step omits that pass; its ground for the omission decides confidentiality rather than this, and R-07-014b's sink-before-yield is scoped to a computation that spans slots.
    * **R-11-023's criterion enumerates the admission check's inputs more narrowly than R-11-006 and R-11-009 state the check.** The criterion says the interval arithmetic quantifies over *widths and offsets and never occupants*, while R-11-006 states it over slot WCETs and each task's period and R-11-009 requires the switch-duty ratio counted explicitly.
    * **R-15-220 fixes partition-switch cost at three terms and names neither the total restore nor R-07-044's pending swap among them.** Its terms are `fence.t`, one `vmclear` pass and OPP relock, and R-18-009 treats those as the whole of it.
    * **The surviving object count is five in the prose and three or four in the register, and nothing enumerates the five.** [The spec](../spec.md) and [the inspirations](../background/inspirations.md) each speak of five surviving classes without naming them and disagree on what happens to them; R-07-027 enumerates three, R-07-031a names four ABI groups one of which is not an object, and R-08-004d puts the grant table outside the restored classes, while R-07-020's criterion quantifies over an *object inventory* nothing enumerates.
    * **The rule registry has a gap at K-64 that nothing records and no rule can see.** [The registry](../../tools/check-rules.md) runs K-63 straight to K-65 with no struck row and no retirement note, and the id occurs nowhere else in the tree.

#### M4.2b · Endpoint and notification IPC, and the surviving object inventory

[EndpointIPC.v](../../proofs/EndpointIPC.v) specifies the closed invocation/object inventories, rendezvous/refusal IPC and pending visibility while leaving undecided ABI/magnitude choices as parameters. Native audit accepted 471 file constants with empty assumptions; all 274 live mutants and host checks passed. This accepts statements/refutations, not executable IPC; the nine register questions remain reported.

  * Nine findings, every one a register gap reported and not closed, at a through g and i and j of the artifact's own header; a tenth lettered entry records that every composition magnitude is a field and is not an open question. **Two of the nine are new, and each is a question this artifact's own first draft decided by fiat and this version reports instead.**
    * **The badge width of the message transfer shape is unfixed.** R-07-031 fixes the transfer and R-15-007 the bit budget, and nothing joins them, so the transfer is stated over an arbitrary width.
    * **What a typed refusal's type enumerates is unfixed.** R-07-029a requires the refusal and names no cause set.
    * **Which of the closed five invocations may refuse is unfixed**, owed at R-07-029a or R-08-004c.
    * **The ABI numbers themselves are fixed nowhere.** R-07-031b closes the surface at five and numbers none of them; the artifact exhibits a second numbering over the same five that passes the same check, so the choice is exhibited rather than argued.
    * **What a re-offer costs and how many are admitted is unfixed**, owed at R-07-042 or R-11-010.
    * **Whether a notification word is per partition, per endpoint or per ring is unfixed**, owed at R-12-096 or R-08-032.
    * **Whether an endpoint's readiness is one bit or one per offering peer is unfixed**, owed at R-07-029.
    * **What carries the compositor's request for a focus rebinding, a rung selection or a suspension is unfixed, and so whether the three trap.** R-07-031b names the three as kernel-enacted at a major-frame boundary without saying what carries the request, so the trap surface is a parameter and the one result that would otherwise turn on the gap is proved of every admissible value.
    * **Which of create, derive and revoke each surviving object class has is unfixed.** R-07-027a states the lifecycle only negatively of the two tables, R-07-031a deletes the derivation invocation and R-07-031b's closed five carries no create, so the artifact states the distinction the entry does draw and exhibits a second map discharging both obligations while disagreeing at cells no obligation reads.

  * Landed: Tier A.

### M4.3 · Exercise capability lifecycle, IPC, and slot faults through Wasm

Added generated IPC vectors/properties and the first real repository client staged through CertiRocq to Wasm. The oracle passed 84 checks and its deliberate wrong-source control failed; 31 property sets and the generated vectors passed. Twelve decider mutations were stillborn at prover compilation, so the Wasm oracle measures compiled-pipeline agreement rather than additional decider-defect coverage. The statement artifact's separate 274 live mutants were detected.

  * Landed: Tier A.

#### M4.4a · Execute the bounded scalar kernel composition

[The finite target recipe](../../kernel/README.md#finite-compiled-target) compiles scalar C, consumes authenticated boot output and checks descriptor/authority, timer-separated slots, exact restored values/tags and revocation completion. At cda686d1, all ten observations/fourteen executed defects had expected decisions; corrupted switch output and missing fence fail independent traces despite HTIF success. Corpus regeneration matched released bytes and passed 22 checks, digest 96176f2ae55df528. This is finite trusted-text evidence, not general ownership/admission/reuse or multi-hart proof. The 10 h estimate, range 6–14, is retained with actual n/a because historical C authoring intervals were not recoverable.

Calibration: split estimate 10 h, range 6–14; retained estimate, actual n/a.

Landed: Tier A. Independent source review verified the input/output boundary,
descriptor equality, protected authority and restore protocol repairs. The
broader parent remains open under M4.4b. Host CI and both Guest CI lanes form
the settled batch's hosted handoff; pending guest evidence is not a pass.

Retained evidence: [`/root/build/critical-fanout-20260926/kernel-final/report.json`](retained-evidence/root/build/critical-fanout-20260926/kernel-final/report.json) (SHA-256 `48ef22ca4918dfc5bf0e5be5acaa0d5e70ee9a6e318c0d58cf97e420c1c93a3e`).

##### M4.4b-i · Bind scalar restart and service effects

[The scalar integration](contracts/boot-roster.md#2a-scalar-integration-and-producer-joins) joins the real non-ASR supervisor, lifecycle consumer and copy service. The three-case target aggregate passed on code c8a7234e63b44252a8fd43f990b589c452585336 and source/model manifests remained current at 6daf827225308987fbc885ef1196e6c3f3cca028. Restart, stale grant and incomplete completion controls check actual release timing, clearing and saved-context retirement. The holder set has no external loans and zero joined protected-call depth; supplemental depth-two/private-loan fixtures do not extend it. Instruction-tick source bounds establish no physical WCET. M7.1 owns authenticated boot/full roster, M4.4b-ii group/elastic and general pending/CSR duties, and M4.4b-iii V/M restoration. Original estimate 4 h, range 2.6–5.4, actual n/a because component/review/integration intervals were inseparable.

* Landed: Tier A. Independent holder and timing reviews cover the settled
  composition, its refusal controls and the remaining scope above.

Retained evidence: [`/root/build/scalar-join/report.json`](retained-evidence/root/build/scalar-join/report.json) (SHA-256 `dc203e82975804680726910504d08e46d0e56f834e07b0a656b349cd2c1f7b0b`); [`/root/build/fanout-20260926-integrated/kernel-effects-settled/report.json`](retained-evidence/root/build/fanout-20260926-integrated/kernel-effects-settled/report.json) (SHA-256 `f76726e2814a1a9fe5a2f104dd62cc659ad012d761e8821d7d7f14a0ec92895d`); [`/root/build/lane-scalar-effects-20260926/kernel-protected-final/report.json`](retained-evidence/root/build/lane-scalar-effects-20260926/kernel-protected-final/report.json) (SHA-256 `530b6c06ac0676bba84612e09725dff6b0ea7349214789658d073f8322ec4e0a`); [`/root/build/fanout-20260926-integrated/copy-loan-final/report.json`](retained-evidence/root/build/fanout-20260926-integrated/copy-loan-final/report.json) (SHA-256 `b45634083b3a73aabec0fb6fa59bbf11b522f6320168cc91600cdcc3bbf9c308`); [`/root/build/supervisor-target/report.json`](retained-evidence/root/build/supervisor-target/report.json) (SHA-256 `0ada634502d5d22c38bc5ab20a9656b75945b5836df6ee99ff78092bbd5d7c8e`); [`/root/build/fanout-20260926-integrated/lifecycle-refusals/report.json`](retained-evidence/root/build/fanout-20260926-integrated/lifecycle-refusals/report.json) (SHA-256 `c8a12f36e182fa54ccfa34d9c5f1bbfa770ed8021171137a0313dc19099f8b60`).

## M5 · Storage and objects

### M5.1 · Specify L0 recovery and the L1 abstract index

[JournalIndex.v](../../proofs/JournalIndex.v) supplies abstract L0 recovery/L1 index statements, not a B-tree implementation. Structural admission checks node completeness, bounds, occupancy and terminating height, with general walk bound and cycle refusals. Both recovery disciplines are exhibited without choosing a normative arm. Native audit accepted 390 file constants without assumptions; all 210 live mutants and host checks passed. No code was extracted or run against storage hardware; M5.3 retains executable storage.

  * Eight findings, every one a register gap reported rather than closed.
    * **R-10-002 states no property of a commit.** It is a four-layer roster and a prover-provenance criterion, so the multi-block atomicity obligation is owed at R-10-036, whose acceptance clause is the one saying no partially updated region is ever committed.
    * **No entry chooses a recovery discipline.** R-10-002 names the GoJournal lineage and states no recovery rule; R-10-001a states the enumerate-and-select rule of the root copies and not of the log.
    * **No entry of §10 states a block-reuse rule.** R-10-010's refcounted extent sharing is the nearest thing and states no obligation over the allocator; R-10-021 leaves the allocator below the integrity line trusted for availability, and R-10-027 gives the subvolumes one free-space pool without saying who may take from it.
    * **No entry fixes an atomic write unit for the persistent medium.** R-15-181 and R-15-247b fix one for the main-memory array and R-12-026 a per-page code for NAND; R-10-001a speaks of a torn write costing a copy without saying at what unit a write is atomic.
    * **No entry says an L0 record is self-verifying.** R-10-001a says it of a root candidate, and a log that cannot tell a torn record from a whole one has no recovery point at all.
    * **No entry names what ends a transaction.** R-10-036 commits a checkpoint as a single L0 transaction and names no mechanism for the commit itself.
    * **The word fanout occurs in no entry**, and no entry fixes a node's minimum occupancy or whether an empty index is a legal tree.
    * **Every composition magnitude is a field**, the demo instantiating each with a witness value that carries no claim.

  * Landed: Tier A.

### M5.2 · Specify L2 semantics and L3 confidentiality

[KeyspaceDomains.v](../../proofs/KeyspaceDomains.v) instantiates the shared abstract index for typed-key/delta, transaction, snapshot, sealing and durable-state freshness statements. Native audit accepted 397 file constants with empty assumptions; all 377 live mutants and host checks passed. This is specification completion: no host/emulator execution, executable authentication or crypto/storage join is accepted. M5.3 owns implementation and two-instance/crash acceptance.

  * Nine findings, every one a register gap reported rather than closed.
    * **R-10-005 does not close its list of typed key kinds.** It names four things L2 represents, and R-10-005b adds *typed attribute value* without saying whether an attribute is a fifth kind or a component of the four.
    * **Whether a stored extent's existence is observable to a reader holding no key for its domain is unstated.**
    * **Whether an extent's plaintext length is observable is unstated, and no entry bounds the leak.** This is the largest-consequence gap of the nine: a file-length channel is the residual a disk-encryption design ordinarily books explicitly.
    * **Whether the confidentiality-domain label of a stored extent is observable is unstated.**
    * **Whether the rescan-required marker occupies a slot of the declared queue bound or stands beside it is unstated.**
    * **Whether a recorded right may be persisted into a key is unstated**, where R-10-005b forbids a capability and R-08-037a admits exactly one durable record that names rights and confers none.
    * **R-10-005c names no order over its deltas.**
    * **What a `Fresh` region's version is, and what unit a region is, are unstated.** R-10-013c computes one root over *the version of every `Fresh` region* without saying whether that version is a counter, a content digest, or R-10-005's own snapshot version, and R-10-035 does not fix a region's extent in the keyspace.
    * **Every composition magnitude is a field**, including the kind roster and the snapshot's declared cost.

  * Landed: Tier A.

### M5.3a · Generate and execute block-device payload families

[The payload campaign](../../model/test/unit_tests/block_payload.cpp) runs the generated Sail model under the landed contract. At d9489c76, generated pattern/write/read/staging families compare the entire allocated medium and returned bytes; a deliberate wrong byte fails. Canonical model build/wait and integrator review passed; combined receipts are recorded with M5.3c. Host-image persistence and authentication remain M5.3d's work.

Landed: Tier A.

### M5.3b · Execute every block-device reset boundary

[The reset campaign](../../model/test/unit_tests/block_reset.cpp) derives boundaries/buffers from model owners and exercises 516 resets plus stale responses, tears, corruption, priority and complete volatile cleanup. Both deliberate controls fail their intended comparisons. Canonical build/wait and focused campaign/control tests passed at 9b17f499. This covers explicit modeled reset, not process-exit persistence; M5.3d retains that join.

Landed: Tier A.

### M5.3c · Exercise block-device capability refusals through HTIF

[The authority generator](../../tools/vos/block_authority.py) emits the purecap corpus from permission/composition/exception owners. At 00eec542, valid accesses and 24 capability refusals pass 10 HTIF groups; wrong-byte/refusal/cause variants assemble and fail, so compilation is not credited as detection. Corpus digest verification, focused host/guest controls, typechecks and combined build validation passed. Finite device evidence supplies neither kernel authority distribution nor the complete storage image; M5.3d retains both.

Landed: Tier A.

Retained evidence: [`out/evidence/block-authority-compose-baseline.json`](retained-evidence/out/evidence/block-authority-compose-baseline.json); [`out/evidence/block-integration-validation.json`](retained-evidence/out/evidence/block-integration-validation.json); [`out/evidence/block-integration-host.json`](retained-evidence/out/evidence/block-integration-host.json); [`/root/logs/model-build-block-integration-20260919.json`](retained-evidence/root/logs/model-build-block-integration-20260919.json).

### M5.5 · Prove witness-policy continuity

[WitnessContinuity.v](../../proofs/WitnessContinuity.v) proves policy/history intersection, qualifying epoch continuity, recovery and unique terminal destinations with explicit authentication/durable witness assumptions. Native audit at ba6de0b89c75c13122c79c067226495270f38a42 accepted 283 constants with empty assumptions and kernel recheck. Bounded policy/quorum qualification, behavioral cases and Python/Gallina decisions agreed; independent review passed. No mutation verdict is claimed. U-20 owns crypto foundations, M6.2c executable reader/refinement and M5.4 transaction integration.

  * Three findings.
    * **F-389:** the recovered draft over-quantified symbolic-signature authentication. Restricting it to received certificates and jointly constructing the complete safety premises closes the vacuity.
    * **F-390:** the recovered predicate ignored malformed or duplicate extras and policy validity. Strict whole-certificate admission now guards every client transition, checked by generated cross-model decisions.
    * **F-391:** checkpoint-prefix compatibility left the destination policy unconstrained. Full terminal-statement uniqueness and recovery refusal cover alternate destinations.

Landed: Tier A. The read accepts the actual reference model and quantified theorem under the stated external assumptions; release-level independent specification review and the local executable reader remain separate obligations.

## M6 · Userland spine

### M6.0a · Decide the control-plane compiler provenance

The control-plane route uses Vélus as a contained build-time producer under its separately read Inria non-commercial grant. [THIRD-PARTY.md](../../THIRD-PARTY.md) owns the licence reading, including use restrictions, reciprocal distribution and termination. CompCert's grant does not extend to Vélus.

This route supports the proof of concept and requires new terms for changed commercial use. Obtaining separate terms and authoring the control plane directly in Gallina remain untaken alternatives; the latter forfeits Lustre's structural WCET, determinism and causality argument.

### M6.0b · Author the typed IDL profile

[The typed IDL profile](../languages/idl-profile.md) specifies the type/wire mapping, declared parameters and Gallina skeleton boundary. WIT supplies the type-layer start-from and FIDL the bytes-plus-out-of-band-authority discipline; their actual permissive licences are read in [THIRD-PARTY.md](../../THIRD-PARTY.md), with no source copied. The Wasm Canonical ABI and FIDL's unverified marshalling are not adopted.

The profile specifies bounded constructors and packed canonical encodings. Ring schema content lives inside this mapping; [the reference declaration](../../interfaces/ring-reference.json) and [ring generator](../../tools/vos/cli/ring.py) supply its present Gallina artifact. Verified parsers, marshalling, systems-language bindings, admission behavior and register-owned decisions remain unsupplied. R-12-013 excludes the kernel ABI; interpreted Wasm stays within its embedding boundary.

The repair's focused document/checker, mutation, type and tool evidence passes. K-89 holds generated equality, not semantic agreement with the profile. Recorded actual is agent-session wall-clock, excluding the review-gate repair charged at M6.4.

  * Twenty-four findings, nineteen of them owed acts reported rather than closed: seventeen are register gaps, and the other two are a coverage cell this item leaves stale and the crown-jewel row it reports ready and does not flip.
    * **The component model states its terms through a one-line pointer and the forge reports its licence as `NOASSERTION`.** A reading that stopped at the forge would have carried no instrument at all, and one that stopped at the announcement would have missed that the pointer defers to subdirectory licences; the tree carries none, so the deferral resolves.
    * **Fuchsia's own `LICENSE` is `BSD-2-Clause`, not the three-clause instrument the common characterization carries.** There is no *Neither the name of* clause.
    * **No register entry pins this document or names its version.** R-05-135a pins the language document by name and R-05-135b makes a bump a review-gate event; R-12-010 says fork-and-frozen and names no artifact, so an amendment to the constructor set or to the wire-format mapping is not a register edit and the gate never reads it. References: F-190a.
    * **The start-from is unnamed in the register.** Only the specification's §12 prose and [inspirations.md](../background/inspirations.md) say what the fork is a fork of, and neither is the audited artifact, so naming it is a maturity claim under R-18-001a with no register owner.
    * **Fork-and-frozen has no freeze act here.** R-15-014a gives the ISA profile a two-act freeze with a closed nine-item delta and an instrument per row; no entry says when this profile freezes, what its delta is, or what a post-freeze change costs beyond R-18-034's general amendment.
    * **No entry closes the type-constructor set.** R-12-012 restricts without enumerating what constructors exist, so §2's table is closed by the document and by nothing the gate audits.
    * **Whether a floating-point type is admitted is unstated, and it bears on canonicity.** NaN payloads and signed zero give one value several encodings, which R-05-051b forbids of any descriptor on an identity-bearing path.
    * **`string` has no admitted encoding and no statement of what its bound counts.**
    * **Which result type carries the relevance grade is unstated.** R-05-098's closed list names IDL call outcomes as one member and R-12-093 admits a per-operation closed refinement variant beside the common status set; whether each refinement is graded at its own definition in R-18-016's sense or inherits the common set's grade is undecided.
    * **The grade has no stated wire consequence.** R-18-016 places it at the definition and R-05-097 makes it a typing property, and nothing says whether it is carried on the wire, so a mapping that encodes it and one that does not are both admissible.
    * **The flow-label lattice has an owner and no enumeration, and the narrower claim is the true one.** R-07-025 fixes the confidentiality-label lattice at build with the composed topology, R-08-024 makes the fixed graph fix the lattice and the declassification points, and R-07-026 forbids either sanctioned transfer from adding a label, so the lattice is owned and composition-time, which answers the wire-or-composition question R-12-011 leaves open.
    * **Whether the IDL's own wire format is a member of the R-05-042 wire-format inventory is unstated.** R-12-024f puts translator content formats in it and R-05-046 makes each descriptor its own crown jewel; the mapping is row 3 under `CJ-IDL` rather than row 10 under `CJ-FORMAT`, and whether its descriptor is also a row-10 member, and so separately conferred, is undecided.
    * **Whether the mapping is on an identity-bearing path, and so owes an R-05-051a canonicity theorem, is undecided.** R-13-003 puts the interface descriptor inside the content-addressed manifest, which makes its encoding look identity-bearing, while R-05-051c's enumerated site list names the pack reader, the typed manifest, the content address and the deterministic-reuse key and does not name a live IDL call.
    * **The receiver-validation declaration has no vocabulary.** R-12-012a requires the IDL to declare which received values carry the index, length, offset or selector obligation and says nothing about whether that is a per-field marker, a per-operation clause, or a type of its own.
    * **One constructor has two readings and no entry says whether that is one constructor or two.** R-12-010 maps resources to capabilities and R-12-006 with R-12-007 admit only session-table indices on the data plane, so `resource` carries a control-plane reading and a data-plane reading with nothing deciding whether they are one former.
    * **Nothing bounds the size of a declaration.** R-05-143 bounds every recursive former and R-12-012 bounds every list and string, both bounds on values; the number of operations, types, fields, or worlds a declaration carries is not a runtime value and no entry bounds it.
    * **The Coq subset has no stated boundary.** R-12-010's criterion is that the admission checker verifies each Tier-1 proof is stated against the matching skeleton and R-18-037 requires conformance among four generated artifacts (the client, server, parsers and skeleton), and no entry says what a skeleton contains, so what a Tier-1 proof is stated against is undecided by the register.
    * **Two coverage cells read as though the profile existed.** `B-03` by `P-7` reads mode `proved` over R-12-010 and R-12-013a and `B-03` by `P-6` reads `admission-rejected` over R-12-012 and R-12-013, and the profile those four requirements fix did not exist when either mode was written.
    * **`CJ-IDL`'s row 3 is ready to flip and is not flipped here.** The status column reads `not authored`, §4 is the mapping that row names, and the flip is a crown-jewels edit, Tier A for the author, re-entering R-05-150's review rather than being read by this lane; this item reports the row and does not take it.
    * **No entry gives an interface declaration an identity that moves when the declaration moves.** R-12-010's criterion has the admission checker verify each Tier-1 proof is stated against *the matching skeleton* and names nothing a match is decided on; a declaration name plus a profile version does not move when a declaration is edited in place, so a proof stated against the superseded skeleton would still match.
    * **The wire mapping's encoding shape has no register owner at three places.** The byte order of multi-byte scalars, the width ladder every length, count and discriminant is drawn from, and what a descriptor variant shorter than its declared slot leaves in it are each free: R-05-051b requires that one form be admissible and decides which at none of the three, and R-12-091 fixes the slot size without saying what fills it.
    * **An encoding table is not reachable from a mapping's obligations unless something states where each declared value rides.** Every obligation of §4.2 was stated over the descriptor, which R-12-092 restricts to scalars, buffer references, a tag, a deadline and a flag set, so four rows of the encoding table encoded nothing any obligation placed and an operation taking a record or a string had no stated place on the wire.
    * **K-82's count-word vocabulary stopped at twenty where the plan's own figure convention spells word forms to ninety-nine.**
    * **The convention for an identifier inserted between two others and the permanence of identifiers collide once an out-of-order block has landed, and permanence holds.** §4.3's obligations are numbered IDL-050 through IDL-068 and sit between IDL-028 and IDL-029, where the house rule wanted IDL-028a onward; renumbering them would break the stronger rule, which this document restates normatively and the register's preamble states unconditionally.

  * Landed: Tier A.

#### M6.1a · The supervision tree as a Gallina state machine

[SupervisionTree.v](../../proofs/SupervisionTree.v) states the finite reference supervisor, roster bring-up, grant/revocation distinctions, detector/action isolation, class policy and bounded reaction/backoff rules. Composition values remain parameters. Generated and isolated refutations make each obligation observable, including threshold and zero-width hysteresis boundaries.

Proof compilation, exact zero-assumption readings, host checks and the complete seeded population pass: 146 killed, zero survivors and stillborns. The generated vector oracle reaches none of this file; all kills are the prover's. This is a statement/reference artifact, with no lowered Lustre, target execution, timing/causality proof, memory model or lifecycle implementation. M6.1b retains lowering and its joins.

  * Seven findings, every one a register gap reported rather than closed.
    * **The re-grant's extent is stated three ways and they are not one statement.**
    * **A supervised unit has no lifecycle.**
    * **What *no residue crosses the restart* quantifies over is unclear.**
    * **The minimal recovery state is named and never stated.**
    * **The backoff index's scope is three different counters.**
    * **Two ladders carry one name.**
    * **A hysteresis band may be zero-width.**

  * Landed: Tier A.

##### M6.1b-i · Decide the supervisor target route

The [bounded trial](../../supervisor/route/README.md) selects the existing C producer for M8a. Its [source-bound result](../../supervisor/route/result.json) binds Vélus `27ba860c2624ba232816591290c6c119b9ead88a`, CompCert `22c33b91d42c7df986c97b13b6cd630866a56494`, licences, toolchain and products. The real node compiles in Vélus, but the accepted purecap frontend refuses its printed parameter alignment. No target assembly, image or comparison verdict exists; this refuses the tested exchange, not every Vélus route.

The frozen C/Gallina baseline passes, and prepared start/restart rows do not replace missing target execution. M6.1b-ii retains complete Vélus delivery after M8a; M7.1b keeps actual privilege, handoff, fault and restart joins.

Accounting: original midpoint 1.5 h, range 1–2; retained planning estimate, actual n/a, excluded from calibration. The observed trial stays within its two-hour bound, but preparation and integration/review intervals were not isolated into a complete actual; approval waiting is excluded.

* Landed: Tier A. The integration review reads the failed predicate, emitted
  interface, provenance and unchanged downstream obligations. Hosted validation
  follows the batch handoff; component evidence does not assert a guest-gate verdict.

##### M6.1b-iii · Normalize the Vélus Clight exchange and repeat its bounded exchange trial

The [alignment normalizer](../../supervisor/route/normalize.py) and independent [token comparison](../../supervisor/route/token_compare.py) pass their declared erasure/refusal checks. [The frozen result](../../supervisor/route/exchange-result.json) records native node/oracle agreement, then the first failed target predicate: the accepted typed route refuses Clight `switch`. Check 5 is not reached. The switch-free control compiles but its straight-line driver exceeds the text window; neither driver has a target run. C remains the M8a route.

Review tightens pointer-alignment refusals; retained equivalence evidence confirms repaired tools reproduce every trial product/report. Frozen identities remain unchanged. The source-bound result owns the separate post-verdict observations and provenance limits, including the licence-read attestation. Route tools pass direct pinned type/lint checks.

Calibration: original estimate 2.5 h, range 1.5–3.5, class X; retained planning weight, actual n/a. Interrupted review passes have no recoverable exclusive active intervals; completed pass durations do not establish full effort. Integration review and hosted validation are additional.

* Five findings.
  * **The accepted typed purecap route refuses every Clight `switch`, and Vélus prints each Obc conditional as one.** No Vélus node with a conditional reaches the target through the normalized exchange. Open: M6.1b-iv declares a second exchange rewrite that lowers the printed `switch` shapes and repeats the target legs; Clight `switch` typing in the contained compiler would change a build other products bind, so a shape no declared rewrite carries is priced as a separate compiler-side cell. F-472.
  * **The control driver's single straight-line `main` does not fit `compiler-diff program`'s text window.** It compiles to 242,568 bytes of text against 32,768 and is refused at layout. The unchanged probe check 4 names has the same form; its size is unmeasured because of F-472. Open: M6.1b-iv splits both row sets into programs that fit, generated from the same rows. F-473.
  * **On the switch-free control program the erasure suffices for the accepted frontend.** The program compiles with every erased position and its member alignment, and the normalized node's diagnostics carry no alignment error. Standing: the exchange result records both. F-474.
  * **Vélus reports that it could not check semantic existence for the control program; the node compiles without that warning.** Standing: the result records it for M6.1b-ii's theorem-coverage record under F-467. F-475.
  * **Under `-nomain`, Vélus's Clight generation ignores `-lib`.** The no-main arm of ObcToClight `Generation.translate` makes every generated function public whether or not `-lib` is given, so no byte distinguishes `-nomain -lib` output. The normalizer therefore decides acceptance from the main-node markers it refuses. This is a reading of the pinned source, whose files the result binds by hash. Standing: the normalizer and the route README state it. F-476.

Retained evidence: [`/root/build/lane-m61biii-fix-20260928/equiv/equivalence.json`](retained-evidence/root/build/lane-m61biii-fix-20260928/equiv/equivalence.json).

* Landed: Tier A. The integrator's read covers the normalizer's enumerated positions and refusals against the cell, the token comparison's independence from the normalizer, the result's first failed predicate, its retained evidence and its `post_trial` amendments, the tool repair's equivalence record, the five findings against the register, and M6.1b-iv's cell, which takes the rewrite route and leaves the contained compiler unchanged. No checker rule was added; `test_supervisor_route` and `test_retained_evidence` hold the tools and the retained copies.

##### M6.1b-iv · Rewrite the exchange's Clight `switch` and repeat the bounded target legs

The [switch rewrite](../../supervisor/route/switch_rewrite.py) lowers only declared Vélus printer shapes to `if` chains, refusing other shapes and preserving other bytes. Independent [token comparison](../../supervisor/route/switch_compare.py) detects moved labels/statements; generated probe/control splits fit the target window.

[The source-bound trial](../../supervisor/route/switch-result.json) at `1f90ae78` passes every frozen check: exact producer replay, declared-shape comparison/refusals, accepted typed compilation, native/target agreement and final rehash. All 576 probe rows and 576 control rows agree; a compiled perturbed probe fails on target. F-472/F-473 close for this tested exchange, without changing contained compiler switch typing. Translation-site/printer hashes remain `0edb3ffa…`/`25a3f848…`; rewrite soundness is an argument outside the compiler theorems (F-467). C remains the M8a route.

Calibration: 0.7 h agent-parallel actual against 3.5 h estimate, range 2–5, class X; integration review and hosted validation excluded.

* Eight findings.
  * **The checkout's profile no longer has the bytes M6.1b-iii recorded.** A later commit reformatted `model/config/verifiedos.json`. The simulator ran under the recorded bytes, written from `d590c463` into the native lane, and the profile reader parses the recorded and current files to the same value. Standing: the result records the substitution. F-724.
  * **The Vélus and CompCert records in [THIRD-PARTY.md](../../THIRD-PARTY.md) list Sections 2, 3, 4 and 7 of each selected licence and omit Section 6, whose publication credit both licences ask for.** Open: the licence record states Section 6's condition. F-725.
  * **The declared shapes are a subset of what the site could print.** A switch with no case, and an empty case body anywhere but the `else-only` position, are refused. Neither occurs in this trial. Standing: M6.1b-ii's complete producer declares or refuses any further shape it meets. F-726.
  * **Vélus's Obc passes decide which shapes reach the printer.** Switch normalization moves a complete switch's last branch into the default, the two-way default insertion prints `case 0: break;`, and fusion merges adjacent switches on the same scrutinee. Measured on the control program. Standing. F-727.
  * **Vélus emits no semantic-existence warning for the switch control program**, unlike the control program of F-475. Standing. F-728.
  * **Vélus ran on authoring drafts before provisioning.** The runs came after a recorded licence read, in the authoring lane. The accepted compiler and the simulator first ran after provisioning. Standing: the result records both reads. F-729.
  * **Each control driver resets the node at its start**, so the control program's state is exercised only over runs of 24 instants. Standing. F-730.
  * **The rewrite's soundness is an argument, not a proof.** It rests on Clight expressions having no side effects and on the site's layout having no fall-through. The rewritten text, like the printed text, stays outside every theorem (F-467). Standing. F-731.

Retained evidence: [source-bound result](../../supervisor/route/switch-result.json) freezes 38 inputs, the tracked [orchestration](../../supervisor/route/switch_trial.py) and 15 tool identities at `1f90ae78` before provisioning. The tool identities include clang's `libclang-cpp` and gcc's `cc1`. Checks 1 to 5 pass in the 52 s after provisioning, 2026-10-03 01:53:45–01:54:37 UTC ([`/root/build/lane-m61biv-switch-20261002/trial/state/trial.json`](retained-evidence/root/build/lane-m61biv-switch-20261002/trial/state/trial.json).

* Landed: Tier A. The integrator's read covers four things:
  * the declared shapes against the translation site and the printer;
  * the comparison's independence from the rewrite, since it neither imports nor repeats the rewrite's parser and reads clang's tokens;
  * the rewrite's refusal set and its lowering;
  * the result's stages, retained copies, profile substitution and findings, checked against the register.

  No checker rule was added; `test_supervisor_switch` and `test_retained_evidence` hold the tools and the retained copies.

#### M6.2a · Specify the composition-time admission path

[AdmissionPath.v](../../proofs/AdmissionPath.v) specifies generation-wide composition admission for the golden-model roster, thin discharge records, tier obligations, move routing and ordered refusal phases. Refuting machines independently expose wrong evidence moves, phase order, partial generations and uncovered shared-service output.

Compilation, zero-assumption readings, host checks and the complete seeded population pass: 369 killed, zero survivors/stillborns. This supplies specification completion only: no serialized proof is decoded, instruction typed or hash computed. M7.1 owns executable roster admission and image-bound decisions; M6.2b separately owns the on-device CIC checker/refinement. Recorded actual sums competing author/review/repair sessions and is inflated by lane contention, rather than exclusive attended labor.

  * Eight findings, every one a register gap reported and not closed.
    * **Two enumerations this file depends on are closed nowhere in the register.** R-05-135a pins the language document, whose §8.4 fixes seven judgment forms and whose TAL-074 closes and orders six checker phases; the review gate audits the register, so an eighth form or a seventh phase is not a register edit.
    * **Tier 0's and Tier 1's evidence is stated in a vocabulary the eleven do not carry.** R-13-011 names functional refinement, non-interference, handler termination and information-flow theorems, and R-05-030 puts those outside every type system; R-06-009 hands the type-checker Tier 1's memory and ABI half and no more.
    * **No entry pairs a judgment form with the facet it discharges.** The judgment block fixes the forms and R-05-029 fixes the obligations, and nothing joins them, so the checker requires a form to be recognised and nothing about which one it is.
    * **A tier-local admission check sits outside every enumeration.** R-13-012 adds manifest consistency to the Tier-2 certificate and calls it not one of the eleven, so it is a required check no list carries.
    * **No entry says whether a roster may name one identifier twice.** R-13-001's content addressing and R-13-007's deduplication suggest an identifier is a key, and neither says a roster with two packages at one identifier is malformed.
    * **Which side of the admissible-versus-current line the composition-time act stands on is undecided.** R-11-005 makes proofs generation-scoped and R-11-005a separates admissible from current without saying whether composition compares against the versions the composer targets or the versions the device runs; and TAL-072 adds a decoder version to a verdict's key that no register entry names.
    * **Two facet partitions of the same eleven rows are in force and neither document says which one a derivation's records name.** R-05-036's move table gives thirteen and TAL-012 gives sixteen; the three extra splits take their rows' moves, so no verdict turns on it.
    * **No entry assigns a component to a tier.** R-13-011 defines the three and every roster below chooses its own, so a composed generation's tier assignment is a composition magnitude.

  * Landed: Tier A.

#### M6.2b-i · Qualify the bounded checker and its refinement contract

The [CIC qualification](../assurance/cic-checker-qualification.md) refuses MetaRocq `7d4f2fddb0e6b1ef03050999bce281237e2828f6` as an already usable admitted checker. Licence/configuration probes execute, but the actual SafeChecker entry lacks checked guard correctness, preservation/normalization and abstract-environment foundations plus a bounded wire reader. Import scanning is not a transitive assumption audit; no serialized-proof campaign is accepted.

M6.2b-0 owns the separately priced real-corpus partial-checker/metatheory qualification under unchanged exact assumptions. M6.2b-ii remains blocked on that checker and lowering foundations. No opaque callback or broader axiom allowance substitutes for them; general normalization is not promised.

Accounting: the recorded 2.4 h is a conservative non-exclusive upper bound counting the shared four-trial qualification and enclosing batch review whole. Overlapping bounds are not independently spent hours; calibration is n/a. The recovery report retains settled revision-bound gate receipts.

Landed: Tier A.

#### M6.3a · Specify the package composer and typed graph

[HandlerGraph.v](../../proofs/HandlerGraph.v) specifies finite typed graph/template composition, deterministic descriptor-only construction, recomposition on install/uninstall, fail-closed routing, bounded pool outcomes and unconditional verified-parser requirements. Composition magnitudes and unresolved stage/intent sets remain fields. Isolated refutations and boundary witnesses distinguish each obligation from well-formedness and from neighboring obligations.

Compilation, zero-assumption readings, host checks and the complete seeded population pass: 382 killed, zero survivors/stillborns, all prover kills. This supplies specification completion, not executable graph/image production, parsing, signing or nodes. M7.1 owns executable composition and accepted/refused reference comparison; M6.3b the router/cache, M6.2a admission and KeyspaceDomains.v resolution. Relevance grading stays with IDL/TAL owners. The source is authored rather than imported from the GPL-tagged CHERI-seL4 implementation.

  * Fifteen findings: nine register gaps reported and not closed, one question the entries in scope decide, and five methods the next artifact of this kind pays for or avoids. One more is raised in the prose above and indexed with them: the survivor's own lesson.
    * **No entry closes a media template's stage set.** R-12-024c names templates, pools and the four admitted quantities and names no stage; only the spec's parenthetical names four, and a parenthetical the register does not carry is not an enumeration the review gate audits.
    * **No entry says whether a graph may carry two edges matching one intent.** A deterministic selector is deterministic over an ambiguous or an unambiguous graph, and the two disciplines differ observably on the ambiguous one, so the file exhibits both.
    * **No entry enumerates the intent variants R-12-013a calls closed.** That entry fixes that an intent is a closed variant and not an executable name or command string and closes no variant set anywhere, so the intent count is a field and an intent is a finite index below it.
    * **Whether the graph may carry a node for the shared service compartment is unstated.** R-13-010b's duplication pass emits one shared service compartment into the composed image in place of a library linked into each consumer: a compartment, and no package the composer's roster names.
    * **Whether R-05-050's hand-transcribed exception reaches a graph node's format is decided, and by three entries the item's own scope names.** R-12-024f requires a Narcissus verified parser of every content format a translator or media node parses and carries no exception clause; R-05-042's exception is R-05-050's and permits one cellular grammar, which is none of the five families the graph admits; R-12-084a decides the media case by name.
    * **At what granularity the graph is re-signed is unstated.** R-12-024b has it rebuilt and re-signed with the generation and calls it a configuration object carried by the generation root; whether that is one signature or a second one over the graph is not fixed, and the difference is observable on R-10-030's retained roots when R-11-002 pins a prior one.
    * **Whether binding a template consumes a schedule slot the composition reserved is unstated.** R-12-024c requires the four quantities admitted under section 11 before a node may be bound, and R-11-008's two standing reservations name neither a node pool nor a template, so whether a binding is free against an already-admitted schedule is undecided.
    * **Whether an edge's declared limit is compared against the caller's bound at selection or at binding is unstated.** R-12-013a declares the transformation's resource limits and the spec makes routing selection under the caller's requested bound, and neither puts the comparison on a side; the file compares at selection and says so as a reading.
    * **Whether a typed signed configuration object carries one of the three assurance tiers is unstated.** R-13-011's acceptance clause gives every admitted artifact exactly one tier and its required evidence, and R-12-024b admits the graph on the ordinary install path; a configuration object is data and not code, so either it is not an admitted artifact in that sense or it carries evidence nothing names.
    * **Every composition magnitude is a field.** The package count and roster, each package's declared edges, script, manifest width, origin, admission time, admitted quantities and label, the type, intent and world counts, the wire-format inventory and its parser flag, the two pool capacities, the ring depth ceiling, the template's stages and declared end types, the declared inter-level channels, the ambiguity discipline and the graph's identity are fields the demo instantiates with witness values carrying no composition claim.
    * **A witness built by a field setter carries one figure where a witness written out carries ten, and the seeded population is counted in figures.** References: F-191.
    * **A scope a cell cites no id for is derived, and the derivation is the one sentence a reviewer can check, so it says which of its steps is a reading and which a judgment.** "The neighbours those four cite" is checkable and so has to be true of each entry, and five are reached by a noun and not by a citation; the three-step form above separates them.
    * **An entry's sentence is read for the clause it leads with as well as for the prohibitions after its colon.** R-08-047 leads with the verdict being relevance-graded under R-05-097's discipline and then lists three things it cannot be; a count taken off the list alone is short by one, and the leading clause's owner is elsewhere (the fourth obligation above), so this file names it and does not state the grade.
    * **An alternative construction refutes one obligation only once every obligation it does not break is stated of it, and a comment asserting it does is not the statement.** Three of the file's refuting families carried their keeps-theorems and the composer's did not, leaving two composers that might have read the ambient and run the script as well.
    * **Every figure in a note is measured at the revision the note ships, and a population figure taken before the last statement landed is the one that survives an edit unnoticed.**

  * Landed: Tier A.

### M6.4 · Author the ring-contract schema and generate the reference bindings

[The reference declaration](../../interfaces/ring-reference.json) owns ring constants and operation records; [the generator](../../tools/vos/cli/ring.py) reads register-owned status/lifecycle/cancellation enumerations and emits [RingContract.v](../../proofs/RingContract.v). K-89 holds byte identity. The schema belongs to [the IDL profile](../languages/idl-profile.md); later K-99 holds its encoding binding.

Generated campaign obligations compile with empty assumptions, and repaired host/tool/type checks pass. The seeded result is a sample: 28 killed, four surviving and zero stillborn out of 32 sampled mutants. The full population is owed and unrun, and the independent vector oracle reaches none of this file. Survivors vary unconstrained flow labels, marked-scalar/cancellation-point counts or an emitter-owned derived count; session generation remains unread by the statements. Completion capacity, batch size and commit-point inequalities still absorb incremented constants. These are recorded limits, not claimed coverage.

This supplies Gallina reference bindings and admission arithmetic, not an instantiated ring, implementation SPSC/lost-wakeup/typestate proof, verified parser or admitted on-device checker. Systems-language bindings remain M1.2's; IDL-068 preserves both missing implementation boundaries.

  * Fourteen findings, eight of them owed acts: seven are register gaps reported and not closed, and the eighth is a binding owed in the tools. Seven were raised by the review gate's own reading of this landing and not by the authoring, and four of those are closed by the repair the cell records above.
    * **R-12-091 names an index width and no entry says what it counts.**
    * **R-12-091's constant list is not the set a ring declaration must fix.** This declaration fixes fourteen ring constants where that entry names six.
    * **Nothing joins R-12-094's six states to R-12-097's cancellation answers.** That entry decides the answers by where a target stands against its declared points and never says which of the six lifecycle states are live to cancel, so the mapping of its four situations onto the six is the profile's and not the register's.
    * **No entry says which of R-12-093's eight statuses are refusals.** R-12-092's criterion has a malformed descriptor produce *one of the defined refusal completions* that closed set names, and the set is one vocabulary with no refusal subset marked, so the checker reading a refusal has nothing enumerated to read.
    * **R-12-101 names the terms of the joint bound and no inequality.** It requires the composition to prove that capacity, batch size, polling cadence, slot budget and device latency jointly prevent overwrite and meet the declared progress bound: five quantities and no relation, so the arithmetic the campaign decides is this document's and the register audits none of it.
    * **The guest lane failed mid-item and the failure is the machine's, not the tree's.**
    * **The artifact shipped a width rung the profile's own declared-parameter table says this profile does not have.** §8 states the ladder as one, two or four bytes with no eight-byte rung and names what would add one, a declaration needing a bound at or above 2^32, which does not exist; a second ladder in the emitter ended in that rung anyway, under a comment attributing both to IDL-023, and a shipped theorem machine-checked it.
    * **A figure computed as the difference of two ordinal positions reads no order at all.**
    * **Nothing held the emitter's own statement of the wire encoding against §4.2, and I15 has since written the binding.** The emitter writes IDL-023's ladder as a Gallina literal and §4.2's packed rule as three encoded sizes; **K-89** holds what it writes against the emitter and the declaration, which is agreement with the artifact's owners and not with the mapping, so a row edited in the profile moves neither.
    * **A rule claiming three fail-closed places had two.** The checker caught the emitter's own refusal and nothing else, and [check.py](../../tools/check.py) carries no `except` at all, so an owner shaped in a way no guard named ended the whole run.
    * **A seeded population figure is read by no rule, and this one was measured against a working copy and not against the artifact that landed.**
    * **Where a value outside R-12-092's enumeration rides is undecided by the register.** That entry enumerates what a descriptor carries and says nothing about a value the enumeration does not admit or about how a delegated buffer's payload is encoded, so reading the enumeration as a placement and not as a deletion is a decision; IDL-023a took it inside a §4.2 requirement before §8 carried it.
    * **Two entries disagree about whether a descriptor carries a session generation.** R-12-092 enumerates **exactly** six members and no generation is among them; R-12-099 binds every descriptor to a session generation and refuses every old-generation one, and R-12-092's own criterion has a stale generation produce a refusal completion, which a server cannot decide without reading the descriptor's own.
    * **What the sample does not reach is what the register states no relation over.** The four survivors are none of them a defect in the statements: a flow label, which nothing can constrain while the lattice has no owner anywhere; the count of an operation's marked scalars, which nothing bounds above while the receiver-validation declaration has no vocabulary; the count of a cancellable operation's declared cancellation points, which R-12-097 requires to exist and bounds in no direction; and a derived count the emitter writes, which the prover cannot reach and **K-89** does, a hand-edited count no longer being what `run.py ring emit` writes.

  * Landed: Tier A.

#### M6.5a · Specify the copy-based service

[CopyRingService.v](../../proofs/CopyRingService.v) uses generated [RingContract.v](../../proofs/RingContract.v) as its sole schema owner. It states arbitrary-interleaving SPSC invariants, drain-arm-recheck notification, capacity/cleanup/progress accounting, copy-once staging against a Byzantine buffer and independent partial-batch acceptance. Isolated refutations and bridge theorems connect sequence-number algebra to wire indices.

The repaired artifact compiles with zero assumptions and witnessed records. Its final sample kills all 40 selected mutants with zero survivors/stillborns; two operators remain unreached, the full population is owed and unrun, and the vector oracle reaches none of this file. Host arithmetic checks await the integrator's derived repair; the baseline selftest's refusal supplies no passing host verdict.

This is specification completion only. M7.1 owns target copy/notification behavior, M6.5b DMA authority/quiescence and bindings remain separate. No ring, byte copy, notification store, device or implementation Ztso proof is supplied here. The critical-chain residue is repaired without changing those boundaries.

  * Fourteen findings, eleven of them register gaps reported and not closed and the other three methods the next artifact of this kind pays for or avoids.
    * **No entry says which agent resets the notification word or at which point.** R-12-096 requires a binary armed state with a *defined* reset and defines none, and IDL-059 restates the requirement.
    * **R-12-100's bounded-segment discipline is stated of zero-copy DMA and reaches a copying service only through R-12-101's per-variant record.** That entry's sentence is about the session-table capability, the validated extent and the fabric throughout; what obliges a service that copies to bound its segments is a record field every operation variant must carry.
    * **A copy-based service has no device contract to import a device-service bound from.** R-12-101 requires that import, so the largest term of this service's per-operation WCET is a figure with no named owner.
    * **Which of R-12-094's six states make a request identifier live is unstated.** R-12-092 requires the identifier unique among the session's live requests and R-12-094 rejects reuse of a live one; Submitted and Accepted are forced and Free and Reclaimed are excluded on pain of no identifier ever being reusable, and Writing and Terminal are the declaration's.
    * **Whether the accounted latency includes the queueing delay of the requests ahead of a submission is undecided.**
    * **The polling cadence is declared nowhere.** It is one of the five terms of R-12-101's joint bound, it is not among the constants R-12-091 enumerates, and it is not among the fourteen the ring declaration fixes, so the term the arithmetic turns on has no owner.
    * **Nothing maps R-12-008a's four ownership phases onto R-12-094's six lifecycle states.** R-12-094's acceptance clause says the lifecycle refines those transitions without weakening them and gives no map, and four and six do not pair by counting.
    * **R-12-096 gives the producer a predicate it cannot evaluate.** *Signals only when the consumer may sleep* names the consumer's own recheck, and the only cell R-12-091's header gives the producer is the notification word, so either the armed word is that predicate or the clause names something no header cell carries.
    * **What a copy-based service copies into has no owner.** R-05-124 has a copy-once parser write its fixed destination buffer whole and no entry gives a server a staging buffer, a size for it, or a lifetime.
    * **No entry excludes a server re-reading a delegated buffer after validating it.** R-12-092 puts the validation before eligibility and says nothing about a second read, and R-12-100's *never reinterpreted after* is stated of the DMA extent alone, so the time-of-check defect a copying service is exposed to is excluded by no entry and is refuted here by construction.
    * **Every composition magnitude of this service is a field.** The accepted ceiling and its two slacks, the batch and its slack, and per operation the segments, the staging buffer, the cleanup cost, the released-reference count, the three reproduced costs, the accounted latency, the progress slack and the progress bound; and with them the live state set, the reset owner, the counter flag, the cadence, the accounting arm, the charging rule and the identity.
    * **A strict comparison between two positions in a list is weakened with nothing to notice.** The two orderings agree everywhere except where both operands are absent, which a generated family of reorderings never reaches: every member it produces still carries both acts.
    * **An obligation stated as arithmetic over a contract's ranks licenses every construction the arithmetic admits, not the ones the contract's relation names.** Lawfulness here read *one rank more or two ranks more*, which is `lifecycle_malformed_ok`'s own arithmetic; the contract's `lifecycle_malformed` is a partial relation answering at Submitted alone, so the arithmetic licensed a second skip at all six states.
    * **A header's roster of hand-authored refutations is prose no gate reads and it drifts.**

  * Landed: Tier A. **Nothing holds what this artifact created**, which is why the tier is not B: the proof gate is not a rule of [check-rules.md](../../tools/check-rules.md), no rule reads a `.v` file's statements, and the readings the header takes of R-12-096, R-12-100 and R-12-101 are register readings a reviewer checks by hand. The rules the landing does touch, **K-36**, **K-37**, **K-82** and **K-96**, hold the plan's arithmetic and the findings index, not the artifact.

## M7 · Full emulated system

#### M7.1e · Realize the copy-based service

The [bounded C copy service](../../copy-service/README.md) passes the final joint scalar aggregate on 2026-09-27, bound by [M4.4b-i's record](#m44b-i-bind-scalar-restart-and-service-effects) to accepted code `c8a7234e63b44252a8fd43f990b589c452585336`. Typed C, declaration-generated offsets and the actual fenced/atomic notification adapter realize the finite [CopyRingService](../../proofs/CopyRingService.v)/[RingContract](../../proofs/RingContract.v) reference.

Target campaigns pass payload/capacity/wrap/notification cases with executed altered-answer, lost-publication and authority-refusal controls. The joint supervisor/kernel/copy campaign passes normal restart, stale-grant refusal and incomplete-completion refusal, with independent release evidence. The private copy allocation remains continuously owned; small-slot revocation does not cover the large ring. Callers keep source bytes stable while staging.

Complete C/ISA refinement, production IDL/admission, public-client redemption, physical WCET and full boot remain open. C does not discharge the safe-Rust requirement. [Host CI 36294896736](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36294896736) passes at the accepted code; final documentation follows Host/Guest handoff without calling a pending guest verdict passed.

Accounting: original midpoint 14 h, range 9–19; retained planning estimate, actual/calibration n/a. Historical authoring and interleaved integration/review intervals do not establish a complete actual.

Retained evidence: [`/root/build/copy-target/report.json`](retained-evidence/root/build/copy-target/report.json), SHA256
  `8fd4c958f9eae4c959f3cbdfdf003da89f0575c654de2af1088d6d0892b2bdab`; [`/root/build/copy-notification/report.json`](retained-evidence/root/build/copy-notification/report.json), SHA256
  `5dabd8dd33e782da7707789ac45caadc52b6c32f1b3a0cb44ecc54acdb6be51b`; [`/root/build/copy-partition/report.json`](retained-evidence/root/build/copy-partition/report.json),
  SHA256 `96a83208d1bdf2f6c35503ceee0d350383c34cf6913fd917f85e768c68a08c0b`; [`/root/build/scalar-join/report.json`](retained-evidence/root/build/scalar-join/report.json).

Landed: Tier A.

#### M7.1f · Realize the boot verifier's executable crypto

[The executable verifier](../../firmware/crypto/README.md) supplies bounded C for SLH-DSA-SHAKE-256s, ML-DSA-87 and RoT release callbacks. The host campaign passes all 184 independent/reference comparisons. The local target run times out without an HTIF verdict and supplies no acceptance.

The separate [hosted target campaign](../../firmware/crypto/README.md#hosted-target-campaign), [run 36954830093](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36954830093) at `b906dbdd`, executes all 57 selected cases under the staged manifest SHA-256 `bdd11e25e9dc00692d8f4cac17049c402c49f6062875a55bb45893a1164fbd05`; positive and applicable refusal families agree with no omitted case. Retained receipts bind source/compiler/stream/simulator identities. Guest CI does not run this campaign.

[M3.5b's chain campaign](#m35b-lower-and-compose-the-remaining-measured-boot-chain), [run 37103959681](https://github.com/symbiogenesis/VerifiedOS/actions/runs/37103959681) at `46c9ecef`, joins the same verifier sources/compiler to RoT stage-0/stage-1 and main-die ML-DSA stage-2 verification, with corrupt signatures refused at their stages. M5.3d owns the separate storage join, M7.1a the full roster. Constant time and masking remain deferred; a signature theorem alone supplies no executable-verifier acceptance.

Calibration: re-priced estimate 13 h, range 8–18; retained estimate, actual n/a. Historical authoring intervals across parallel host/target/staging sessions were unrecorded; hosted campaign wall-clock is execution, not effort.

  * Six findings.
    * **The campaign's receipts record no per-case timeout, and the join's shared keys omit it, so a join would accept interfaces run under different timeouts.** The 9,000 s value is read from the job logs, and the instruction limit appears only in each case's argv. A passing receipt is unaffected, every case having returned an HTIF verdict. Closed: each interface receipt now records its case timeout and instruction limit, and `boot-crypto join` refuses a shard lacking either or differing from the others in either; run 36954830093's retained receipts predate the fields. F-718.
    * **Hosted case runtimes vary by runner by up to 1.56 times.** Across runs 36349072848, 36907039358 and 36954830093 over the same staged manifest, `slh-tg29-tc399-wrong-root` took between 3,198 and 4,990 s; the longest case reached 55% of the 9,000 s case timeout and the slowest interface 40% of the execution step's 320-minute limit. Standing: only run 36954830093's receipts are retained. F-719.
    * **Identical model source maps built different simulators across runs.** Runs 36907039358 and 36954830093 record the same 756-file model map and different simulator digests, while the five interfaces within each run agree. Standing: each receipt binds its simulator and build-receipt digests. F-720.
    * **The ML-DSA interfaces executed on the RoT composition, while their consumer is the M-mode stage on the main die.** Closed: M3.5b's chain campaign, [run 37103959681](https://github.com/symbiogenesis/VerifiedOS/actions/runs/37103959681), verified the stage-2 image with ML-DSA-87 on the main die. F-721.
    * **No record holds M3.5b's release-target unit to the staged manifest's verifier identities.** [rot_release_target.c](../../firmware/harness/rot_release_target.c) compiles its own unit over `keccak.c` and `slh256s.c`, and the hosted campaign exercises `vos_slh256s_verify_internal` rather than the `vos_boot_slh256s_verify` callback. Closed: section 9.13's identity freeze held in that run, the chain compiling `vos_boot_slh256s_verify` and the ML-DSA binding from sources and a compiler equal to the staged manifest's. F-722.
    * **[The boot-handoff contract's open joins](contracts/boot-handoff.md#8-open-joins-and-findings) still read the target signature-verifier binding as unbuilt and its run as fixture-only**, where M3.5b's `boot-handoff release-target` campaign at `0f61470a` binds `vos_boot_slh256s_verify` through the contained backend. Closed: section 8 now states that binding, and section 9.13 the chain's identity equality. F-723.

Retained evidence: [`/root/build/lane-bootcrypto-20260927/host-common-final/report.json`](retained-evidence/root/build/lane-bootcrypto-20260927/host-common-final/report.json); [`/root/build/lane-bootcrypto-20260927/target-common-final/report.json`](retained-evidence/root/build/lane-bootcrypto-20260927/target-common-final/report.json); [hosted campaign](../../firmware/crypto/README.md#hosted-target-campaign) executes the [staged streams](../../firmware/crypto/README.md#staged-target-streams), which carry that receipt's five compiled assembly SHA256 values, one interface per runner with a 9,000 s case timeout; Guest CI does not run it. [Run 36954830093](https://github.com/symbiogenesis/VerifiedOS/actions/runs/36954830093) at `b906dbdd`, over the staged manifest with SHA-256 `bdd11e25e9dc00692d8f4cac17049c402c49f6062875a55bb45893a1164fbd05`, joined each interface exactly once and matched all 57 selected cases, the local campaign's population with identical per-case inputs, leaving none unexecuted: 11 `slh`, 9 `slh-internal`, 14 `mldsa`, 12 `mldsa-internal` and 11 `mldsa-mu`. `slh-tg29-tc399-wrong-root` refused in 3,198 s, and the longest case, `slh-tg36-tc491-message-flipped`, took 4,276 s. Its joined receipt is retained at [`out/boot-crypto-target/36954830093/report.json`](retained-evidence/out/boot-crypto-target/36954830093/report.json), SHA-256 `aaae5ece67b69a24328e39b74a41804077dcb3d58c9080e2825663a091df9c67`.

  * Landed: Tier A. The integrator held the chain campaign's freeze against this item's staged manifest and read its main-die ML-DSA runs before recording the join. The landing revision follows the Host CI and Guest CI handoff; a pending guest verdict is not counted as passed.

## RTL track

#### R1a · The capability format's algebra, and the cross-check that decides it

[The authored capability package](../../rtl/vos_cheri_pkg.sv) implements the model's bounds/representation algebra and transformations, excluding architecture-removed instructions/datapaths. [The cross-check](../../tools/vos/cli/rtl.py) compares model-produced text directly with Verilator output, without a shared type adapter.

All 658,659 vectors agree, including exhaustive decode and permission-mask domains. Twelve separately compiling defects are killed. Lint, provenance, focused host/tool/type checks pass; imported-core elaboration is unchanged and not retaken. K-79 holds numeric parameter restatements and packing budgets, not the package's semantic algebra or count-word prose. Finite agreement supplies no functional-equivalence proof. Requested containment holds for `base ≤ top ≤ 2^36`; overflow can wrap below base, with `CSetBounds` clearing the tag. The representation proof must state that domain rather than claiming unconditional containment.

  * Six findings.
    * **`setCapBounds`'s containment property holds over a domain nothing states, and this is the third implementation to measure it.** Over the 22,152 vectors with `base` at or below `top` at or below 2^36 the derived region contains the requested one without exception; over the 3,296 with a requested top above it, 48 do not, the decoded top having wrapped below its own base.
    * **The same domain falsifies a sentence the model states about itself, that gap seen from the encode side.** `cap_common.sail`'s header says the effective exponent runs to `cap_max_E` = 30 "so *k* + 1 runs to 31 and the five bits are spent exactly".
    * **A vector population off entropy alone cannot tell one clause of `setCapBounds` from its absence.** Inside the exponent-increment branch the base's lost-significance flag reads bit 0 of the mantissa as it stood *before* the recompute; reading the recomputed one instead reproduced all 647,179 vectors on the first population.
    * **The provenance record owes no row for this work, on the record's own grammar.** A binding is a list of settings on [the configuration package](../../rtl/vos_c_class_config_pkg.sv) or `n/a` with a stated ground, both readings being about a structure the build does *not* contain.
    * **A hand-maintained count in that record was wrong as written.**
    * **The checker stated a width of its own, in the module whose preamble says it states none.** K-57's ceiling was `granule * 64` with a comment saying the 64 was XLEN, in a file that reads every other figure out of the artifact that owns it.

#### R1c-i · Write the MMIO windows into the composition

[The composition](../../model/config/verifiedos.json) adds boot-ROM, UART and block-device placements across shipped variants; existing RoT apertures remove the assumed fourth addition. Sail names the windows, emits their attested-tree nodes and refuses invalid placement/overlap or DTB/ROM collision. K-94 holds configuration, emission and the whole-map validator rows together.

These are placements, with device behavior retained by R1c-ii. Access fall-through remains bounded by each enclosing PMA; no unfinished zero-response corpus member is claimed. Boot ROM and DTB extents are separated at composition and blob write. The later R1c-ii decision retains non-executable ROM because boot releases directly into SRAM. F-111 and F-229c retain their original absence/console limits; F-205's stale enumeration is removed.

Model build/targeted behavior, profile refusal sweep, corpus, generated DTB/schema/bundle, focused host/checker mutation and type evidence pass. Seeded placement/write refusals and a missing whole-map row decide all new refusal sites. Co-reads and unrelated source semantics remain unchanged; the emulator's printed revision is a configure-time stamp, not a current-tree reading.

  * Seventeen findings.
    * **The fourth window already existed four times over, and reading M3.1 removed the premise.** The item names a *RoT window* beside the boot ROM, the serial port and the block device, and M3.1 declared four of them, the OTP fuse bank, the entropy root, the counter file and the watchdog, in all three shipped files one milestone earlier.
    * **The plan obliges the three devices to exist and the register obliges their placement, two different authorities.** Grepping the register for `serial port`, `console`, `block device` or `blkdev` returns nothing, and each of its ten `serial` hits is a serializer, a serialization point, a serial dependence, a serial-bound challenge or a device serial number, not a port; `boot ROM` returns three, R-09-003, R-09-036 and R-16-008c's acceptance, each the RoT's on-die metal-mask ROM on the RoT's island, reached by no requester on the fabric and a different ROM from this one.
    * **Two apertures every composition declares had no devicetree node at all.** The interrupt file and the revocation sidecar were each held in IO memory by the validator and each absent from the attested tree, inside the emitter whose own comment says R-15-002b, not R-09-007, is what puts a device window there and that *each node below therefore carries its window under R-15-002b*.
    * **The model called two figures attested-devicetree constants and neither had ever been in that tree.**
    * **Nothing held two declared apertures apart, because of the shape of `check_mem_layout`.** That function reads one window at a time against the regions, so two apertures declared at one base are both inside the same IO memory region and both pass it; a composition could put the interrupt file on top of the CLINT and validate.
    * **The boot ROM had no extent and the attested tree began at the region's base.** The ROM region's comment has said since M0.8a that it holds the boot ROM and the tree written at `memory.dtb_address`, which was the region's own base, while the ROM had no base and no size anywhere in the repository.
    * **A composition-time bound and a write-time bound over one region are different facts, and only the second knows a size.** M0.8a recorded that the emulator's bound sits on the `--device-tree-blob` path while `--validate-config` exits before reaching it; met again here from the other side, the composition knows where the tree starts and never how far it runs, so the boot-ROM pairing is refused at the address in the validator and at the extent where the blob is written.
    * **Three subcommands the command table declares answerable on either lane were refused on the host.** `vos/cli/__init__.py` put `config-keys`, `validate-config` and `asm` in the model command's `host_ok` set, and `vos/cli/model.py`'s `main` loaded the build environment before it dispatched, which exits on `win32` by design.
    * **The plan's own cell for this work stated a composition four apertures out of date.** R1c's bullet said the frozen profile's composition declares `clint`, `imsic`, revocation and memory-sequencer windows and no UART at all, which M3.1 falsified by adding four RoT windows and this item by adding three more.
    * **The silence this item priced its decision against is narrower than five sites said, because of the enclosing region's PMA.** `pmaCheck` decides an access before `checked_mem_read` and `checked_mem_write` reach the RAM fall-through (sys/mem.sail), so what falls through is only what the region already permits.
    * **The boot ROM's extent is declared inside a region that refuses an instruction fetch**, the one access an SoC boot ROM exists for.
    * **An enumeration was presented as a grep result and was not that grep's result.**
    * **The repair for F-205 replaced a stale enumeration with a hand-maintained count, the defect F-205 names.**
    * **The whole-map check is a list somebody maintains, and two artifacts said it was built.** `declared_apertures` is written out one row per window, and a window the composition gains joins only when a row is written.
    * **The obligation the disjointness refusal fail-stops on is filed nowhere.** R-15-002b places every aperture inside the 36-bit space with none at a wide power-of-two offset and makes the placement a stated constraint on the attested devicetree; it does not say two apertures may not share a byte, and no other entry does.
    * **A composition comment narrated its own revision.**
    * **The evidence sweep's model revision is a stamp taken at cmake configure, not a reading of the tree it prints from.**

  * Landed: Tier B under **K-94**.

### R4 · Second-class macro architecture specification

[The macro architecture view](../hardware/second-class-macro-architecture.md) states second-class organization, interfaces, maintenance, measurands, refusals and sourced device readings. It supplies shape only: density, latency, retention, geometry and other values remain pending. The bank-within-deck choice is declared with grounds and forfeited cross-deck amortization, not made normative by this derived view.

At `28e1897`, document references, type checks and focused tool evidence pass. K-24's derived-view counts remain outstanding for integrator repair; the baseline selftest refuses and supplies no accepted mutation figure. K-14/K-48 hold bearing citations, not architectural meaning. No WSL/device measurement is supplied; R5 retains physical qualification and inaccessible-source rereads. Recorded 0.6 h summed agent-session actual has an unrecorded earlier start.

  * Six findings.
    * **No register entry states what a macro architecture specification must contain, so the document is written against a measurement obligation and one sentence of the specification.**
    * **Five of the ten pages the alternatives entry cites did not serve an unauthenticated read, and the entry's own readings carry no date at the sentence.**
    * **The one shape decision the properties leave open has no owner in the register.**
    * **The eighth view moves a count two documents state, and the drift is left for the one `--fix`.**
    * **The first draft carried four claims its sources do not establish.**
    * **Two sequencing sites still place this item after the co-simulation gate.**

  * Landed: Tier A. The artifact carries claims the register does not own, an architecture's shape, and no rule holds a macro architecture's facts, none being derivable, so Tier B's fourth condition cannot be met; K-14 and K-48 hold the view's citations and not its content.

## Post-M10 hardening

### Post-M10 · Publish opening hardening obligations

[The opening plan](../assurance/hardening-opening-obligations.md) instantiates all five fallback positions per core/block, distinguishing scalar adaptation, imported cores, authored devices and unqualified blocks. It states proof/reduction interfaces and premises, and separates FPGA rehearsal from first-silicon fault/leakage characterization. No finite differential or capability-format check is promoted to functional equivalence, physical bound or hardening theorem.

F-385, F-386, F-387 and F-388 retain instrumentation, countermeasure, equivalence and laboratory commissioning acts and costs. Lean supplies a conditional arithmetic input, not a probability/composition foundation. Independent review accepts the four outputs and per-block fallback coverage at authored `381c44e2b4fd4c05e54092f9bc6b5e4759ca83d7`; implementation prerequisites stay open.

Accounting: 0.4 h agent-parallel actual includes recovered authoring and bounded recovery/review; compatibility work receives no duplicate actual, shared landing notes are charged at Q12 and unattended gate waiting is excluded.

Landed: Tier A. The read accepts an opening plan with explicit implementation and commissioning prerequisites.

## Build-loop instruments

### Initial check/emit/FAST tooling

  * No note was recorded at this item's landing.

### I0 · Standardize the tools on one language

  * Consolidated tools in Python on one interpreter, with shared parses in one package.

### I1 · Move sources to WSL ext4 and uncap local parallelism

  * Struck the WSL ext4 migration: measurements did not justify the move, and the remaining machine-setting clauses were outside repository control.

### I2 · Use one shared content-keyed SMT memo cache

  * Declined a shared SMT memo file because Sail rewrites it without locking or atomic publication. Corruption was reproduced deterministically. I7 supplies copy-on-create seeding and private lane caches; no cache crosses a solver or distribution boundary.

  * Finding, closed by I7 rather than by this item: the shared cache I2 proposed already existed for the typecheck loop, `/root/build/verifiedos-typecheck-smt-cache` being one file every checkout wrote, live across four concurrent lanes. It is per lane now.

### I3 · Benchmark a current z3 binary on a cold emission

  * Retained pinned z3 5.1.0: cold emission averaged about 214.6 s against distribution z3 4.13.3's 280.5 s, with byte-identical generated output. All four cold runs and three warm anchors succeeded, without crossing solver cache boundaries.

### I4 · Add shared ccache, then emit only when generated output changes

  * Enabled ccache when available, without sloppiness. Declined the additional emit-only-on-change alteration: byte-identical regeneration already reduced follow-on compilation/linking to 4.5 s. Cache sharing across build trees did not produce hits because their command paths differ.

  * **Finding: the shared `CCACHE_DIR` does not reach across build trees, and the claim that it did was wrong.** ccache hashes the command line along with the source, so the fast tree, differing by `-g`, and a second worktree, differing by every `-I`, share no entry with it: a lane's first 367-unit build against a cache holding 939 entries took 367 misses and no hits. [tools/vos/env.py](../../tools/vos/env.py) now records what the cache does and does not reach.

### I5 · Benchmark generated-TU flags, clang versus gcc, and mold

  * At the same canonical flags, clang compiled the generated unit in 38.7 s against gcc's 81.8 s; I10 owns adoption. Kept canonical debug flags and declined mold's roughly half-second saving. All eighteen compiles and nine links succeeded.

### I6 · Benchmark the same Sail 0.20.2 binary built with flambda

  * Declined a second flambda Sail switch: median emission improved from 34.4 s to 33.8 s, with byte-identical output, insufficient to justify maintaining another switch. The trial switch was retired.

### I7 · Run canonical builds in the background and standardize worktree lanes

  * Added background canonical builds, checkout-derived private lanes and build leases. A new lane built successfully; a competing build refused the live lease, and `wait` returned the completed build's verdict.

  * Finding, reported rather than closed: the sibling lanes had already worked the collision around by hand with a second build tree named for one worktree. That workaround is per-agent and undeclared, and reaches neither the log nor the typecheck cache, which every lane still shared as one file; the derivation reaches all three.

  * **Finding, closed here: two ways of standing a lane up reached no seeder, and the second was made by the fix above.** `emit` configures a tree that does not exist yet, and it is the loop the memo cache is worth most to, being the emission [I3](#build-loop-instruments) prices cold at ~3.6 min against ~36 s warm; a lane opened with `emit` rather than `build` paid that. Both seed through one `_seed_cache_file` now, which keeps a target that already exists and copies nothing when the donor is the target, so the primary worktree is not a special case for any caller.

### I8 · Optionally move quick checks to push CI and canonical tests to nightly CI

  * Declined moving the then-local edit checks to push/nightly CI on the recorded cost comparison. This historical decision describes those landing inputs; current hosted validation follows the repository's current rules.

  * **Finding: this tree carried CI workflow files, their being inert was what kept them green, and S3 has since answered it by deleting them.** Two of `ci.yml`'s own lines showed why that was load-bearing: its ninja line named `generated_smt_rv32d`, a target that does not exist since the prover-backend loop reduced to the RV64 arm, and its cmake line passed `-DFIRST_PARTY_TESTS`, an option no `CMakeLists.txt` declares since M0.18.

### I9 · Hold the co-stated facts and derive the reading view

  * Added owner-derived counts and checks for co-stated facts, and generated the register reading view. Checker mutations, repairs, co-reads and tool tests passed.

### I10 · Flip the model build's compiler to clang

  * Adopted clang for model builds when available, with the default compiler as fallback. The new build and all twenty-four differential members passed with unchanged trace digests.

### I11 · Hold the upstream pins against the gitlinks that own them

  * Added **K-81** to bind licence-record pins and restated sites to the Git index in both directions, including unpopulated gitlinks. Parser tests and checker mutations passed.

  * **Finding, fixed here: the mutation sandbox's index carried no gitlink at all.** That cost nothing while no rule read one; a rule that does would have reported every pin as owned by nothing and failed the baseline, which reports as a red tree rather than as a bad mutant.

### I12 · Give the tools one entry point, and the lane to the tool

  * Consolidated command entry points under [tools/run.py](../../tools/run.py), preserving per-command help and host/guest dispatch. Host validation and representative guest commands passed.

  * Landed: Tier A. No rule holds the one-entry-point fact, so the mechanical conditions Tier B is admitted on are not met, and saying so is cheaper than inventing a rule to hold a directory listing.

  * Four findings.
    * **`rtl.main` parsed `sys.argv` instead of accepting argv, so dispatcher calls failed despite typechecking under a cast.** It now accepts argv like other commands. Its dispatch marker remains local to the command rather than moving into the shared helper.
    * **K-83's path mutant became unseeded when its target `sys.path` preamble was deleted in the move to a package module.** It now targets the surviving entry-point preamble. A looser match could have mutated another construct and reported an irrelevant kill.
    * **The documents cite tool paths 180 times and only one of those paths is cited normatively**, the measurement that decided the `check.py` exception above.
    * **The tool surface is obligation rather than fat.** What makes the directory large is the number of cross-artifact facts somebody decided to hold, so the lever that shrinks it is S15's, generating what is transcribed, not a search for unused code.

### I13 · Close the three tool defects the plan reported and did not close

  * Repaired model revision stamps, checkout discovery and command-lane dispatch. Each repair passed a regression that failed with the original defect restored; host and guest behavior were checked.

  * Landed: Tier A. Nothing in [the rule registry](../../tools/check-rules.md) holds a fact this landing created: the tools' own suite holds them, which is not a rule this plan's Tier B admits, and turning a behavioural test into one would cost three edits and a mutant.

  * Seven findings.
    * **The missing work tree causes the always-on marker; distinguishing it from a configure-time snapshot requires varying the environment.**
    * **A finding restating a closed one stays open for as long as nobody re-measures it.** F-204 was raised from prose against a defect already closed, and its own neighbour in the register said so; the entry cost a reader the belief that three declared subcommands do not answer. A restatement is worth a measurement before it is worth an act.
    * **`--help` cannot test lane availability.** argparse exits before environment loading, so even a subcommand that would refuse the lane prints usage and exits 0. The case instead uses an argument table that reaches every handler.
    * **A case that sets a process-global override sets it for every module the runner is running in the pool beside it.** Pointing the corpus parse at a throwaway checkout through the environment failed twenty-five cases across six other modules, each reading the real tree through a variable this case had set.
    * **The set of subcommands that answer on either lane is prose in three places and a table in one, and two of the three had drifted.** Every subcommand the table declares is held against the README page now and the entry point's list stops enumerating; the other direction, a page naming what the table does not declare, is held by nothing and keeps the entry open.
    * **A host-lane reading that skips the toolchain preparations skipped them only on the lane that cannot take them.**
    * **An owner-level case cannot test a defect in its caller.**

### I14 · Make a seeded run survive its own lane, and absorb the loop that kept its own accounting

  * Added keepalive leases and per-verdict journals, compiled affected proof dependency closures and unified verdict accounting. Tool regressions and checker mutations passed; the journal retains decided verdicts after an interrupted run.

  * Landed: Tier A. No rule holds a verdict vocabulary, a lease or a journal, so Tier B's fourth condition has nothing to name.

  * Four findings.
    * **A disposition read open over an act the tree already carried.**
    * **A run's stated scope counted what it picked, not what it decided.** For two of the three oracles those are the same number; the one that writes into the checkout, the `$[test]` loop, stops when it cannot verify its own restore, so the closing line, which a completion note copies, would have stated a run larger than the verdicts printed under it.
    * **Eight relative links inside the tools' own docstrings resolve to nothing, seven of them naming an executable the one-entry-point move retired**, and no rule reads a link written in Python prose. Repaired under `tools/`; the same retired name stands in three shipped proof headers and is left, reported and not closed, a comment edit there costing a guest run of the proof gate this item does not take.
    * **A baseline that would not stand up discarded the prover's account of why it would not.**

### I15 · Hold the facts the plan reports as held by nothing

  * Added **K-97**, **K-99** and **K-100** for previously unheld facts, with **K-88** retaining generated-artifact validation. Checker mutations and tool tests passed; the IDL profile correction required Tier A review.

Calibration: no original estimate was recorded; excluded from the fit.

  * Landed: Tier A, and the condition that decides it is the second, not the fourth. **K-97**, **K-99** and **K-100** hold the three facts this landing created, each at the sites it created them over, and **K-88** holds the artifact the declined rule would have read, so the fourth condition is met in whole. What is not met is *no Tier-A edit*: the binding K-99 supplies falsifies a section of [the typed IDL profile](../languages/idl-profile.md) (fourth finding), and a profile is read at full attention whether the edit is normative or a repair to a claim about the tools.

  * Seven findings.
    * **The lane's fact table named its second owner by a bare file name**, `quickchick.py` where the index carries `tools/vos/cli/quickchick.py`, so the row pointed at nothing a reader or a tool could open. K-100 made the finding on the run that landed it, evidence that the rule bites.
    * **IDL-023 states its ladder twice and the second statement is the one the emitter implements.**
    * **The encoder-table gap is closed by generation, not by a rule, and the gap fell from 593 to 14, a factor of 42.** Recorded as the ground of the decline, not as a defect: a rule over the residue would hold one run's output against the same run's accounting of itself, the accounting and the artifact being one act.
    * **This landing falsified a section written to say what nothing holds.** The profile's own holders section reported the binding from §4.2 to the emitter as owed and not written, which K-99 makes false; the repair narrows the claim to the rows reached, because *no rule holds §4.2* is a wider claim than any rule replaces it with.
    * **The elaborator's other version is restated twice and owned by nothing.** K-97 does not reach it and would be inventing an owner if it did.
    * **A rule declared fail-closed at each reading was fail-closed at one of three.** F-218d.
    * **A declared residue gave a ground that did not describe the tree.**

### I16 · Put an authored source in the imported build, and partition the elaboration diff

  * Added authored RTL source substitutions and attribution of elaboration differences, without copying sources into upstream repositories. Real-manifest composition and behavioral tests passed; no replacement row or curated-core elaboration was accepted by this item.

  * Landed: Tier A. No rule holds either mechanism, and not because one would be hard to write: what they create is a declaration whose member set is empty today, so a rule over it would report `ok` about nothing until R1b declares a row. The tools' own tests are the gate a behavioral claim answers to here.

  * Six findings.
    * **The two authored-source declarations are not one list, and merging them would break a green loop.**
    * **A declaration that reaches no line and a file list one source short are indistinguishable in the result and opposite in meaning.** The composed list carries no trace of which happened, and the arm elaborates either way, so the declaration has to be fail-closed, not best-effort. Closed here, per substitution and per imported source.
    * **The record's *Elaborated result* column changes what it means at the first substitution that displaces a module kind, and the record is not this lane's to edit.**
    * **The attribution is by direct declaration and is therefore incomplete by construction.**
    * **A row whose two sides are both packages is visible to no member of the partition, and the row R1b's re-pointing would declare is one.**
    * **The end-to-end elaboration evidence is owed and cannot be taken in any checkout of this repository today.** The elaboration puts the primitive packages of the gitlink `opentitan` at the head of the imported core's file list and refuses by name on it; S3 left it uninitialized because nothing open reached it, and reaching it is a clone this item does not take, not a command.

### I17 · Name the host gate member that went red, without a login

  * Repaired the Windows bootstrap fixture's unresolved temporary path and added per-member host-gate JSON, annotations and job summaries. Focused gate/entrypoint tests and render fixtures passed at `0e134d9`. No hosted run was evidence for this original landing, and the scratch expression check was not a workflow-linter verdict.

Calibration: no original estimate was recorded; excluded from the fit.

Landed: Tier A. No checker rule was added and none holds what this item created: the workflow's expression contexts are decided by GitHub at validation time and by no gate here. The fourth Tier-B condition is therefore unmet and a green wave is not a reading of the workflow.

  * Two findings.
    * **The workflow's expression contexts are held by GitHub at validation and by no gate here.** A violation is invisible to `run.py --check --tests` and surfaces as a run that does not exist. Standing: the residue is carried, not closed, for the reason the fourth bullet above gives.
    * **Two statements of the workflow's command line outside the tools lane went stale with this landing.** No rule holds the pair; K-68's co-stated table does not carry it.
