# Findings Register

*An index of what the build has found, and not a second copy of it. The completion notes and cells of [the implementation checklist](implementation-checklist.md) own every finding's content; this register owns its id, its type, the item that raised it, and its disposition, and owns nothing else.*

## How to read this

A finding is something the build learned that the plan would otherwise learn again. The plan records 419 of them across 72 items and nothing read them, which costs three ways: the same fact found twice at two items, an owed act with nowhere to live until somebody assembles S1's rows out of prose by hand, and a methodological finding that never becomes a rule. This register is what reads them.

```
**F-nnn** <type>: what was found, named so that a reader recognizes it without the plan open
· Raised: the checklist item whose note records it
· Disposition: open, closed, or standing, and what makes it so
· Restates: (where the plan records one fact twice) the entry this one is the second sighting of
```

**One fact, one owner.** The plan's note is the finding and this register is the index over it, so an entry names what was found as far as a reader needs to recognize it and then stops. It carries no figure the note carries, and it never argues the note's case a second time. Where the two disagree the note wins, being the record of the act where this is a pointer at it.

**Ids are permanent and order is the plan's.** A retired finding keeps its number and is struck, never reused, because a number is what a later item cites when it meets the same fact. Entries sit in the order the plan records them, so a finding added to a note that already has others takes a letter suffix and sits where the note puts it, not where its number would.

**Four types, and each names what a reader does with the finding rather than who is to blame.**

- `owed-act`: something is still owed, and the entry names it. A register or profile act, a decision, a rule, a repair, or an enumeration nothing carries. These are the entries S1 reads.
- `upstream-defect`: a defect, a dead branch, a stale transcription, or an unstated assumption in an artifact this repository imported rather than authored: a pinned upstream, a vendored tree, a standard, a tool, or the environment it builds in. These are the entries a re-pin and a start-from read.
- `method`: a rule about how work here is done or checked, holding of the next item as well as of this one. These are the candidate checker rules and the conventions.
- `measurement`: a figure, an outcome, or a determinate result the item produced, recorded so that a later reader takes it rather than deriving it again.

A defect this repository's own work introduced and the same item closed is a `measurement` of that work rather than an `upstream-defect`: the type says where a reader goes next and not whose fault the finding was. A finding answering to two types is typed by what a reader does with it, and that choice is a person's, so this register decides a type and never a truth.

**Three dispositions, and every entry carries exactly one.**

- `open`: an act is owed and the entry names it. Every open `owed-act` is a row S1 does not have to assemble by hand.
- `closed`: the act is done and the entry names what did it.
- `standing`: nothing was owed and nothing is. The finding is a fact recorded so that it is not derived again.

**Two shapes are indexed, and only the first is held by rule.** A completion note states most findings under a count, `Six findings.` with six bullets beneath it, or as a bullet opening `Finding`. That is the plan's own declaration, and rule K-82 holds this register total over it in both directions: a counted finding with no entry, and an entry naming a finding its item's note no longer records, are each a finding of that rule. The rest the plan states in prose, and an entry indexing one carries `in prose` on its `· Raised:` line and is held only at its item existing. Which prose sentence is a finding is a reading, and a reading is the thing that rule cannot make.

**Rediscovery is shown rather than hidden.** Where the plan records one fact at two items, the second entry states it as a pointer and carries `· Restates:`, so the pair reads as one fact met twice instead of as two independent statements that may drift apart. Restating without that line is what the discipline forbids.

**Derived facts are computed, not copied.** The two figures the paragraph above states are recomputed from the entries by `tools/check.py` and rewritten under `--fix`, so neither is maintained here by care.

**What is outside this register.** A note's own reasoning is not a finding: an exit-evidence figure, a net-change line, or the ground for a disposition the item took. A fact of finding character that a note neither counts nor calls a finding is outside it too, by the same rule that makes the counted half checkable, and the repair for one worth indexing is to state it in the note's own declared shape.

---

## S · Serial-path decisions and program instruments

**F-000k** owed-act: the gate demanding a measured emulator throughput states no threshold to measure against, and no artifact in the repository states one for its *sufficient through M6* to mean
· Raised: S4
· Disposition: closed at the gate, the item stating the criterion it rules against and saying that it authored it; the register half is F-000l

**F-000l** owed-act: no register entry owns a throughput floor or a boot-time ceiling for the development vehicle, every throughput obligation there being on shipped hardware and R-18-004c putting the emulator outside timed obligations outright
· Raised: S4
· Disposition: open, reported and not closed, a register act rerunning the review gate

**F-000m** method: no workload this repository holds can carry a throughput figure, and none can before the composed image exists, so an item wanting one authors its own program outside the differential corpus
· Raised: S4
· Disposition: standing, the two programs authored here left untracked because a benchmark decides nothing about the model's answers and a corpus member no check reads is worse than none

**F-000n** measurement: the commit trace costs about a fifth of the rate and 57.6 to 67.0 bytes a retired instruction, so what bounds a traced run is storage rather than speed
· Raised: S4
· Disposition: standing, which puts the constraint on the arm that traces and on neither the daily driver nor the emulator

**F-000o** owed-act: a lane's configure child is given the administrative directory and no work tree, so the emulator it builds is stamped dirty whatever the lane's state is, the child's own directory being read as the tree and every tracked file as deleted
· Raised: S4
· Disposition: open, reported and not closed; the commit half is right and the flag is noise that would mask a genuinely edited lane

**F-000p** owed-act: three commands the entry point's table declares host-capable cannot run on the host, the command's own dispatch preparing the guest environment before it reads which subcommand was asked for
· Raised: S4
· Disposition: closed at M1.4-prime, which needed a fourth such command and so paid for the reconciliation: the environment reader takes a host-lane arm and the dispatch asks the entry point's own table which subcommands it applies to, rather than restating them

**F-000q** method: the merged register file makes an ABI integer name an authority destroyer, and the failure surfaces at the exit store millions of instructions after the write that caused it
· Raised: S4
· Disposition: standing, the dialect's own consequence rather than a defect; what is owed is that a program here name its authority holders before it names its scratch registers

**F-197** measurement: the pinned solver's acquisition route was stated in no artifact, and it is an architecture-portable wheel rather than a source build or a published image, one install of that distribution reproducing the unpacked binary byte for byte on one digest
· Raised: S9
· Disposition: closed, the provisioner becoming the route's owner and composing the distribution's version from the one the environment module fixes

**F-197a** owed-act: no register entry owns the development lane's toolchain at all, every reproducibility obligation there being over the shipped placement map and the certifying toolchain rather than over the environment the golden model is built in
· Raised: S9
· Disposition: open, reported and not closed, a register act rerunning the review gate; the provisioner discharges no requirement and creates none, which is what keeps it a build-loop instrument

**F-197b** owed-act: the simulator's version pin is restated in a document twice and in code once and no rule holds the three together, the commit-pin rule reading object ids alone and the checker-pin rule reading the two checkers alone
· Raised: S9
· Disposition: open, recorded as a candidate rule and none added here; the provisioner adds no fourth copy, importing the constant instead

**F-197c** owed-act: no artifact declared the distribution-package set the model build needs, so the provisioner becomes its owner and no rule holds the list
· Raised: S9
· Disposition: open, recorded as a candidate rule; what stands in for it is that every row names a consumer already in this tree and a row that cannot name one is not written

**F-197d** owed-act: three provisioning routes have owners that state them as prose for a person rather than as a command a tool can run, two of them being rows that probe and report and plan nothing and the third a route no row probes at all
· Raised: S9
· Disposition: open, the recipes wanting an owner that states them as an argument vector; inventing one would be the unowned derived fact the working rules refuse, and the verdict rather than the plan is what separates nothing to do from nothing this tool may do

**F-197e** method: a provisioner whose every fact is already satisfied cannot exercise its own install arm, so what its tests hold is the mapping from a probe's answer to a command and never the running of one
· Raised: S9
· Disposition: standing, held over injected tables rather than over the machine the tests run on; a claim of idempotence over an arm that never ran would be a check that decides nothing

**F-197f** upstream-defect: the corpus parse reads the git index without the translation the environment module already provides for a linked worktree, so inside the guest on a lane every corpus-reading tool ends in a traceback naming no git repository rather than in a verdict
· Raised: S9
· Disposition: open, reported and not closed, that parse being the one every rule reads; the primary worktree is green on both lanes and this item's own guest case reaches the translation rather than repeating it

**F-197g** measurement: a landed decline's ground names two opam switches where the lane now carries four, two having been added by milestones that landed after the sentence was written, and the argument the ground carries is strengthened rather than weakened by the count
· Raised: S9
· Disposition: standing, the decline's cell left alone rather than repaired at its own site, no stock image carrying any of the four

**F-197h** owed-act: every figure any document stated about the provisioner's fact table was a hand-copy no rule read, the row count and the rows carrying a command among them, and three of the stated figures disagreed with the table on the day they landed with every gate green
· Raised: S9
· Disposition: closed, the four counts made quantities of the asserted-count rule and computed off the table by import rather than by a second parse of the file, so a repair rewrites them; no rule id is spent, extending a claim table being the cheaper of the two stated acts

**F-197i** method: a lane can leave an untracked file at a tracked path in the worktree its branch merges into, where the merge refuses and the selftest's sandbox reads it as an empty source, and every gate the lane runs is green over it because each decides about the worktree it runs in
· Raised: S9
· Disposition: closed, the path clear at the landing and the primary worktree's status empty; the standing reading is that a lane's own gates decide nothing about the tree it merges into

**F-000a** upstream-defect: the commit trace's default destination is block-buffered into a pipe while the injection diagnostics are unbuffered on the other descriptor, and the end-of-trace acknowledgement prints whatever the trace flag says because its call site passes a comparison where every other passes the flag
· Raised: S11
· Disposition: closed on this side, the rig giving the trace a file of its own; a diagnostic landing inside a half-written record reads as a divergence about a run that agreed

**F-000b** upstream-defect: a version-2 reply is two or three separate writes on a socket with no delay disabled, so the second waits on an acknowledgement this side has nothing to piggyback on
· Raised: S11
· Disposition: closed, quick acknowledgement re-armed after every read taking 1,022 instructions from 49.1 s to 0.66 s; disabling delay on this side does not reach the held write, which is the emulator's

**F-000c** upstream-defect: the packet's write and read raise an internal error above sixteen bytes, so the block operations abort a run under injection rather than reporting something narrower
· Raised: S11
· Disposition: standing, the generated stream excluding them, which is the packet not being the transport seen from the side that has to generate around it

**F-000d** measurement: the two emitters disagree about a word whose low two bits are not `11`, the fetch path still taking upstream's compressed branch where the profile excludes `C` and fixes the instruction length
· Raised: S11
· Disposition: open, which emitter is right being the model's question; the generator spends no stream on encodings the profile does not have

**F-000e** upstream-defect: the source half of the packet's integer extension is declared and never written, both source addresses and their data always zero
· Raised: S11
· Disposition: standing, vacuously legal under the packet's own rule and what a comparison over the full field set would find first

**F-000f** measurement: the physical-address width is 64 and not 36, so a commit memory record's address is sixteen hexadecimal digits and the narrower space is the composition's rather than the address type's
· Raised: S11
· Disposition: standing, the bridge measuring the width off the records it compares rather than restating it

**F-000g** method: a schema-version bump can drift the meeting and elision tables away from the code that produces them, with every gate green
· Raised: S11
· Disposition: closed, K-85 holding §4's declared record kinds against §9's meeting and elision tables in both directions and both tables against the projection and the packet view themselves, which are run rather than read

**F-000z** measurement: the verified lowering route's compiler emits bare-metal position-independent code over the base integer extension with no capability back end, so the claim that its target exists is true of plain RISC-V and false against the purecap-only requirement
· Raised: S12, in prose
· Disposition: standing, the target gap read at the upstream rather than closed, and M1.6 meeting it end to end from the other side

**F-000h** measurement: the `$[test]` harness does reach the capability format's packing, killing all five live mutants of it, and names one property for every one of them because it stops at the alphabetically first to fire
· Raised: S13a
· Disposition: standing, which makes the argument for generation at that site resolution rather than reach and narrows M0.12's structural claim to the decode surface a property never sees

**F-000i** method: a mutation loop that writes into the checkout is a loop nothing else may read beside, the tree on disk being wrong for the length of one mutant however reversible the write
· Raised: S13a
· Disposition: closed as far as a lock reaches, the loop holding the lane's build lock so a second run of it and a build beside it are refused; an advisory lock reaches no reader that does not ask for it, so the printed warning stands beside it rather than being replaced by it

**F-000j** upstream-defect: the model lane's opam environment leaks into a prover child, and where that child shells out to the library manager it sees two definitions of one library and picks the wrong one
· Raised: S13a
· Disposition: closed, a prover child given its own switch's variables laid over the inherited ones; what it printed named neither switch

**F-000r** owed-act: a fourth mutation loop carries its own table, its own seeding and its own accounting, and merges the case whose seed no longer applies with the mutant that survived into one list under one label
· Raised: S13b
· Disposition: open, the loop being the quarantine's own gate and outside this absorption's scope; it may read the shared vocabulary, the rule holding the boundary forbidding only the landing loop reaching into the quarantine and not the reverse

**F-000s** method: an item's stated blocker did not survive the act it blocked, an appended case and the rewritten run loop lying far outside the context a merge reads and the shared region coming through byte-identical
· Raised: S13b
· Disposition: closed, the region measured identical on both sides rather than inspected; what is real is a last mile and an ordering preference, so the ordering stands and the ground under it does not

**F-198** measurement: on a host stripped to the distribution's own PATH the gate group reports three of its five rows absent, and the apply arm forms a plan of exactly two commands both of which invoke an installer the host does not have and this tree states no route for
· Raised: S14
· Disposition: standing, and it is the ground of the decline: the arm a push workflow runs cannot be stood up from zero by anything here, which is the second of the two grounds arriving one layer below where it was first found

**F-198a** measurement: a workflow's own green is unobservable from this repository, there being no continuous integration by decision, no runner registered against either remote, and nothing here that exercises a hosted image
· Raised: S14
· Disposition: standing, recorded as the ground of the decline rather than as a defect; an authored workflow could be held to nothing before it landed, which is what makes an unrun gate a promise in another file

**F-198b** owed-act: three classes of fact a workflow must state have no owner in this tree, the runner label, the action references it pins, and the bootstrap route
· Raised: S14
· Disposition: open, reported and not closed, and the rule this item was priced for is left unwritten with its id unspent: what a rule would hold does not exist until an owner does

**F-198c** measurement: the provisioner's apply arm ended in a traceback rather than a verdict where an installer was absent, found by pointing it at a host that is not the lane
· Raised: S14
· Disposition: closed, an absent installer reported per step with the run going on to re-probe, so the row it belongs to fails on its own terms and the exit convention holds

**F-198d** method: a landed decline falsifies the forward claims other cells made about the act it declined, and those are present-tense sentences no gate reads
· Raised: S14
· Disposition: closed, eight such sentences repaired to what is true across the plan and this register, with the rerun returning to the item that owns it and that cell deliberately not re-priced here; two of the eight stood a commit longer than the rest, which is the class arriving inside the item that names it

**F-000t** upstream-defect: the model's documentation emitter writes the emitting checkout's commit and dirty flag into the artifact where git answers it, so a generated file held byte-for-byte would move on every commit and would differ between two lanes describing one model
· Raised: S15
· Disposition: open, the fact met twice carrying the first site's disposition: this site's emitter no longer answers the git question, and the configure child F-000o names is still owed its work tree
· Restates: F-000o

**F-000u** measurement: a four-megabyte machine-written file entered the tracked corpus and a total-class rule read 2,809 pin restatements out of its bit literals, every one of them an object id on a line that had already named an upstream
· Raised: S15
· Disposition: closed on its own subject, the generated artifacts taken out of that rule's window because a machine-written file restates nothing; standing as a coupling for every other total-class rule, one of which is now reachable from an anchored comment in the model

**F-000v** method: repointing a parse at the generated artifact moved a selftest case's subject out from under it, the seeded model source no longer being what the reading opens, so the case reported the artifact stale and the rule it was written to prove survived
· Raised: S15
· Disposition: closed, the case re-anchored on the artifact's own clause body; the hazard is general, a case seeding a Sail definition now having to seed the artifact rather than the file

**F-000w** upstream-defect: two artifacts here cite instruction shapes the curated model does not carry, a vector segment form and a widened atomic each taken from upstream under a name this tree does not spell
· Raised: S15
· Disposition: closed, both repaired to cite the atomic clause that is really there

**F-000x** owed-act: the encoder table is a proper subset of the surface the model spells and no rule reads the gap, 593 of the enumerated mnemonics having no row in it
· Raised: S15
· Disposition: open, recorded as a candidate rule and none added here; the converse holds today, every encoder row but the one unstructured clause appearing in the enumeration

**F-000y** measurement: a count went stale where its own list shrank, a sentence naming five readers standing above a list of four after the quarantine took one out
· Raised: S15
· Disposition: closed, repaired there and in the two parser docstrings that named the departed module as a sibling

## M0 · Hardware reference

**F-001** upstream-defect: the CHERI upstream embeds an older `sail-riscv` than the base it would be reconciled against, so the two are not one shared base under two configurations
· Raised: M0.1
· Disposition: closed, M0.5 taking current `sail-riscv` as the base and transplanting the capability layer onto it

**F-002** measurement: fixed-width fetch deletes the gating and not the 16-bit path, so the parcel check, the illegal-parcel cause and the compressed decode mapping stay load-bearing with no real clauses behind them
· Raised: c2
· Disposition: standing, the fixed instruction length making a short parcel an illegal instruction rather than a misaligned fetch

**F-003** upstream-defect: the alignment relaxation lives in four places rather than one, and only two of them are visible from the extension registry
· Raised: c2
· Disposition: closed, all four taken in the batch

**F-004** upstream-defect: the dormant emulator target's handwritten register initializer was already stale from the previous batch, and no typechecker could see it because that target is dormant
· Raised: c2
· Disposition: closed, the initializer and the two module lists corrected here; deleting the dormant target is S3's

**F-005** upstream-defect: the retired-instruction counter has a consumer that is not architectural, so deleting it would have deleted the differential rig's instruction ordering with it
· Raised: c3
· Disposition: closed, a model-internal retire counter with no CSR address replacing it

**F-006** upstream-defect: the memory API's reservation flag was never only that, selecting the concurrency interface's reserved-read and conditional-write kinds
· Raised: c3
· Disposition: closed, the parameter derived from the access rather than deleted, and no longer passable independently of what it describes

**F-007** method: a profile refusal that hangs rather than fails cannot be left to a test-runner timeout, because a hang blocks where a refusal only excludes
· Raised: c3
· Disposition: closed, the sweep capping each run and booking a hang as a refusal that blocks

**F-008** measurement: the page-size constant survives the walker's deletion, memory-attribute regions still needing their alignment so that no attribute changes inside one access
· Raised: c3
· Disposition: closed, the constant renamed for the property it now carries rather than deleted

**F-009** measurement: the scalar-operand vector forms have to be re-homed rather than deleted, which leaves encodings duplicating integer ones
· Raised: c4
· Disposition: closed, the duplication struck by R-15-040d and the model act carried at M0.19

**F-010** measurement: the accrued floating-point flags have no destination and two comparisons still read them, so no sticky flag is software-visible and a program detecting an invalid result tests the result
· Raised: c4
· Disposition: standing, the invalid-operation flag being the result at the two sites that keep it

**F-011** upstream-defect: the scalar files were carrying the vector unit's classification predicates, which the float library's width-generic tests already make
· Raised: c4
· Disposition: closed, each three-way dispatch collapsing to one line and only the canonical NaN and three flag constructors moving

**F-012** upstream-defect: the vector-start cut deletes an implementation-compatibility hack, the scalar moves having computed an element count only to match the bound other implementations chose
· Raised: c4
· Disposition: closed, the count, the geometry read and the question going together

**F-013** measurement: the trap on an unallocated CSR address was already total and needed no work, the accessibility predicate defaulting to false
· Raised: M0.6d
· Disposition: standing, the batch's own excluded test being the evidence

**F-014** measurement: deleting the two interrupt fields deletes their two sources with them, leaving the timer and nothing else
· Raised: M0.6d
· Disposition: closed, the interrupt generator and the software-interrupt door going entire

**F-015** measurement: the external-interrupt bit was the sole reason the pending register read one value into its destination and another into its own read-modify-write
· Raised: M0.6d
· Disposition: closed, the split collapsing and the platform OR, the read-type enumeration and the read function going with it

**F-016** method: an enumeration left with one reachable value is narrowed rather than kept, which is the rule the privilege type set applied to two more
· Raised: M0.6d
· Disposition: standing, and it also removed a non-injective mapping whose two arms encoded one cause

**F-017** measurement: the capability transplant forces the narrower base's deletion rather than merely profiting from it, the ported encoding having no 32-bit instantiation in this tree
· Raised: e1
· Disposition: standing, such a configuration being a machine with no capability format to run under

**F-018** measurement: fixing the register width changes the generated C++ interface and not only the model, a configuration-dependent width being emitted as a length-carrying type and a static one as a native integer
· Raised: e1
· Disposition: closed, the emulator harness's callback signatures following it

**F-019** upstream-defect: the narrow-mode query was already unreachable and the enumeration under it nearly so, the one-reachable-value rule arriving here from the configuration rather than from a deleted mode
· Raised: e1
· Disposition: closed, both deleted with the base

**F-020** measurement: the narrow-base half of the test corpus was never evidence for this profile, exercising a base the profile does not have
· Raised: e1
· Disposition: standing, its removal costing no coverage and every excluded row staying excluded for its own reason

**F-021** upstream-defect: the relocation guards are dead at the source, a constant false gating both relocation paths
· Raised: e2
· Disposition: closed, the port folding them out rather than transplanting unreachable branches

**F-022** measurement: the tag plane needs no new machinery, the concurrency interface already carrying a capability tag on its read and write requests
· Raised: e2
· Disposition: closed, the tag memory arriving as a parameter of the interface the curated tree already instantiates

**F-023** measurement: the granule keying is the model's to do, nothing below the model rounding an address to a granule
· Raised: e3
· Disposition: closed, the write path shifting the address down by the capability size and writing every granule the access spans

**F-024** measurement: the transplant cannot delete the default data capability on its own schedule, every test in the imported corpus addressing memory with an integer base register
· Raised: e4
· Disposition: closed, hybrid mode and that capability standing until M0.6f, which the finding also gave its exit criterion

**F-025** measurement: the trap raise has to sit in the postlude, a check reading the executing capability being core surface while raising a trap calls machinery compiled after it
· Raised: e4
· Disposition: closed, the five hooks moving to the first point at which both halves are in scope

**F-026** upstream-defect: the read path was discarding the tag, the checked read returning default metadata unconditionally under an upstream note about folding metadata across splits
· Raised: e5
· Disposition: closed, the fold now the conjunction over the splits at the write path's own polarity

**F-027** owed-act: the capability load collides with the cache-block zero, the two separated only by a zero destination and a small immediate, which upstream never meets
· Raised: e5
· Disposition: closed, the destination separating them and the frozen dialect re-encoding the surface at M0.6f

**F-028** measurement: the two executors neither start at the same instruction nor report a register write at the same width, and the store side is not comparable at all
· Raised: e5
· Disposition: closed, the streams aligning on the first program counter the curated model retires and M0.12 widening the write record

**F-029** measurement: the imported corpus cannot reach agreement past its own prologue, which is a fact about the corpus rather than about the transplant
· Raised: e5
· Disposition: closed, the regression the rig carries being that the agreeing prefix must not shorten

**F-030** measurement: the exponent field carries the case flag, because the field table leaves no bit beside it
· Raised: M0.6f
· Disposition: standing, the packing forced by the table rather than chosen and costing no mantissa bits where the upstream packing costs three

**F-031** measurement: the byte-exact threshold the frozen widths deliver is not the one the register stated, and the padding above it follows the mantissa width
· Raised: M0.6f
· Disposition: closed, R-15-007c amended to the delivered figures, both made model properties, and every consumer moved with them

**F-032** measurement: an integer register is wider than an address, so a register's integer reading is its whole data field and not the address field alone
· Raised: M0.6f
· Disposition: closed, R-15-007i amended to say so, the round trip resting on decode being total

**F-033** measurement: the imported test corpus goes with the default data capability, and it goes entirely rather than family by family
· Raised: M0.6f
· Disposition: closed, eleven extension-by-extension filters collapsing into one ground and the suite excluded from registration

**F-034** method: membership in the profile is by enumeration and never by inheritance, which reaches instructions and an object-type decision the item's own list does not name
· Raised: M0.6f
· Disposition: standing, the same rule freezing the object-type space and its reserved codepoints

**F-035** measurement: the revocable interval's width is the model's to bound and the covered union is a predicate rather than a list, a composition property meeting a fixed-width register
· Raised: M0.6g
· Disposition: closed, the validator refusing a composition that does not fit and every consumer quantifying over the predicate

**F-036** measurement: deleting the indirect interrupt interface is what puts the pending array in the address map, the array having nowhere else to be
· Raised: M0.6g
· Disposition: standing, the file having two doors and the receiver's being also how a bit is cleared

**F-037** measurement: the flush instruction's model content is the enumeration rather than the barrier, the flush set being one structure this model does not have
· Raised: M0.6g
· Disposition: standing, what the file carries being why every other structure is absent from the set

**F-038** method: the generated test-matrix configurations are a second declaration of the platform, so a key added to one and not to the template is a build failure rather than a divergence found later
· Raised: M0.6g
· Disposition: standing, schema conformance being where it bites

**F-039** method: the model's own property harness runs under the generated maximum configuration rather than the profile's, so a property reading a configured policy is a property about the wrong machine
· Raised: M0.6g
· Disposition: standing, profile-conditional behaviour belonging in the differential corpus

**F-040** measurement: the vector gate is the class and not the context, two predicates both reading as vector availability while only one is the static property the requirement names
· Raised: M0.6h
· Disposition: closed, the repair being what stops a partition dirtying the unit and then trapping the clear that erases it

**F-041** measurement: the scrub has to become an arm of the access type rather than a convention of its caller, reading and writing and belonging over main memory alone
· Raised: M0.6h
· Disposition: closed, the access union gaining a second arm and the four matches a case each

**F-042** measurement: the welded block size stopped belonging to the instruction it was defined beside, four instructions in three modules now reading it
· Raised: M0.6h
· Disposition: closed, the constant moved beside the granule it is a multiple of, where M0.13 scores it against two geometries

**F-043** method: a telemetry channel and a fail-stop with no architectural state to hang on are not invented in the model, an error model the machine does not have being a model of the harness
· Raised: M0.6h
· Disposition: standing, what the file carries being where each half lands instead

**F-044** measurement: what the scrub is in an architectural model is the tag-preserving pass, and that is visible only against the write path
· Raised: M0.6h
· Disposition: standing, an ordinary store of a granule's own bits clearing its validity tag, which is why the scrub is a block operation rather than a loop

**F-045** measurement: the reclaim's clear lands in memory where the load filter's lands in a delivered value, the two being one protocol's two halves rather than two spellings of one act
· Raised: M0.6h
· Disposition: standing, the clause reading each granule as bits and a tag and writing back the bits it read

**F-046** measurement: the item's honest reach is small and stating it is part of the deliverable, nothing about ordering being observable end to end on one hart
· Raised: M0.7
· Disposition: standing, what the model now does being to state the memory model rather than to guarantee it

**F-047** measurement: the reserved fence-mode trap is the profile diverging from the base ISA's semantics rather than from its encoding
· Raised: M0.7
· Disposition: standing, and it is a deleted rule rather than an added check, the reserved values trapping by reaching no clause

**F-048** upstream-defect: the drain condition reads the ordering bits directly, which is a semantic divergence from the upstream fence and not only an encoding one
· Raised: M0.7
· Disposition: standing, the unconditional reading being strictly stronger and belonging in front of a reviewer for that reason

**F-049** upstream-defect: one barrier enumeration member had been dead since the first curation batch and nothing said so, an enumeration member with no construction site not being an error in Sail
· Raised: M0.7
· Disposition: closed, the narrowing taking it and the orphaned handwritten support with it; the neighbouring herdtools directory is booked and S3 deletes it

**F-050** method: a deletion the model cannot state leaves an unwritten requirement and a discharged one indistinguishable from inside the tree, so the discharge is a citation of the absence contract
· Raised: M0.7
· Disposition: standing, the row numbers landing in the one file already making the claim

**F-051** measurement: the hart identifier was a selector into a table that did not exist, so any composition could declare any identity and the criterion had no instrument at all
· Raised: M0.8a
· Disposition: closed, the core roster closing it

**F-052** measurement: the class table cannot derive the vector geometry, the geometry knob being type-level and so realized one build at a time
· Raised: M0.8a
· Disposition: closed, the binding being a refusal rather than a computation, and corrected at M0.8b for the emulator lane

**F-053** upstream-defect: the minimum-vector-length ladder stopped short of this profile's geometries and would have described a wide build as narrower than it is
· Raised: M0.8a
· Disposition: closed, both rungs landing here and the generated tree unmoved

**F-054** upstream-defect: the processor node hardwired hart zero, the identifier being an emitter literal while the composition's was configurable
· Raised: M0.8a
· Disposition: closed, both following the composed identifier, the label staying a label

**F-055** measurement: the roster is one devicetree property rather than a node per core, and both halves of that are forced by the format and by the emulated hart count
· Raised: M0.8a
· Disposition: standing, the class column being an index the class nodes emit beside their own names

**F-056** method: a devicetree source is a grammar rather than a rendering, and the compiler is what says so, neither of its refusals being visible from inside a string-concatenating emitter
· Raised: M0.8a
· Disposition: closed, the compile and the measured blob size entering the exit evidence

**F-057** measurement: the generated tree outgrew the region it is written into and nothing said so, the emulator's bound sitting on a path no ordinary run takes
· Raised: M0.8a
· Disposition: closed, the region widened, a count taken back out of the tree, and the loop firing the emulator's own bound in both directions
**F-058** measurement: the type-level geometry is compile-time for the prover lanes and load-time for the emulator, and only the second half had been written down
· Raised: M0.8b
· Disposition: closed, correcting the reading M0.8a's own finding left, the emitted model reading the configuration it is handed

**F-059** measurement: the model has one inactive-element mask and the confidentiality obligation attaches to a third of it, the other two reasons being architectural registers a partition reads back
· Raised: M0.8b
· Disposition: closed, the separation derived from the existing function rather than restated

**F-060** measurement: the model pads every masked-off access rather than only the failing one, which is stronger than the requirement and is forced by a model that executes no cycles
· Raised: M0.8b
· Disposition: standing, a discarded check having no architecturally observable result

**F-061** method: two of the item's four requirements were already satisfied and nothing said so, what was missing being the statement, the citation, and anything that would notice either going
· Raised: M0.8b
· Disposition: standing, and it is the shape M0.7's own citation finding takes one milestone over

**F-062** upstream-defect: the extension-context dirty fired once per element and put the vector geometry into the commit trace, which makes a corpus member's digest a fact about which class ran it
· Raised: M0.8b
· Disposition: closed, the write made conditional on the value moving and the trace byte-identical at both geometries

**F-063** owed-act: the fault-only-first vector forms are neither all nor nothing, their defined result on a fault past the first element being to trim and retire
· Raised: M0.8b
· Disposition: closed, R-15-039b excluding them and this item carrying the deletion as a profile amendment rather than a curation call

**F-064** measurement: the assembler needs one vector operand that is spelled by being absent, a mask marking a masked operation and nothing marking an unmasked one
· Raised: M0.8b
· Disposition: closed, handled where the arity is checked rather than by giving each masked form a second mnemonic

**F-065** owed-act: the profile books the matrix extension as a unit and names no instruction, operand form or encoding, so there is nothing here to admit
· Raised: M0.8c
· Disposition: open, the enumeration being a register and profile act ahead of a model one, carried as item (ix) of R-15-014a's second act

**F-066** method: an empty profile cell is the symptom and a missing sorting rule is the defect, a unit booked without a surface needing to name the act that will book it
· Raised: M0.8c
· Disposition: closed, R-15-014b stating the rule and making a unit booked with neither a review-gate finding

**F-067** measurement: a scratchpad is a placement rather than a structure, which decides how much of one a Sail model can carry
· Raised: M0.8c
· Disposition: standing, the one irreducible new fact being whose it is and everything else a refusal over a field the address map already had

**F-068** measurement: the scratchpad is on neither latency class, and stating that relaxes an invariant rather than adding a third class
· Raised: M0.8c
· Disposition: closed, the validator's every-array-on-one-class clause narrowed rather than the class enumeration widened

**F-069** measurement: the matrix half of the partition switch's clear inventory is empty, which is an enumeration result rather than a milestone's residue
· Raised: M0.8c
· Disposition: standing, what a partition can dirty being the scratchpad and nothing else

**F-070** owed-act: the scratchpad has no size and no configuration in this tree declares one, the exploration that selects sizes not having run
· Raised: M0.8c
· Disposition: open, owed to R-15-108's exploration; the model carries the shape, refuses a wrong one, and carries no range

**F-071** measurement: the scratchpad is unreachable from the C-class emulator, so the item adds no corpus member and its properties install their own address map
· Raised: M0.8c
· Disposition: standing, a property about a structure no shipped configuration has being one that must supply it

**F-072** method: a new per-region property does not move the key-set gate, so an unmoved key count is not evidence that nothing was added to a configuration
· Raised: M0.8c
· Disposition: standing, schema conformance being what catches it instead

**F-073** upstream-defect: the build tree is one tree, and a second checkout's build fails at configure rather than at compile, the cache recording its source directory
· Raised: M0.8c
· Disposition: closed by I7, which derives a lane per checkout; the lever needed no tool change

**F-074** method: an item owes the checker no rule where the agreement it creates is between two facts one artifact states, a second reader of one file being no rule at all
· Raised: M0.8c
· Disposition: standing, the refusal firing on every run of every loop rather than on a document sweep

**F-075** method: what decides an instruction's availability predicate is whose instruction it is, so the switcher's gates on the static property and the partition's folds in the context
· Raised: M0.8d
· Disposition: standing, and M0.6h's answer is right for its instruction and wrong for this one

**F-076** measurement: no row enters the extension registry for a fork, because the registry builds the attested extension string and an unratified name there is an attested claim the machine cannot make
· Raised: M0.8d
· Disposition: open, the registry row arriving with the re-pin R-15-057a books, on the day the name means something

**F-077** upstream-defect: the draft's minimum-vector-length mandate is unreachable, the element group's width putting the effective floor above it at every legal multiplier
· Raised: M0.8d
· Disposition: open, booked as the second re-pin delta; the geometry check the model carries is strictly stronger

**F-078** method: a known-answer vector says wrong and a structural property says why, and the ordering between them is not a test file's to choose
· Raised: M0.8d
· Disposition: open, the harness running alphabetically so the symptom aborted the run ahead of the cause; a generated ordering is S13's

**F-079** measurement: where this model stops on the decoder half is the hard decision, belief propagation above it correcting a channel this model does not have
· Raised: M0.8d
· Disposition: standing, a clause computing one schedule's answer being a microarchitectural choice stated as an architectural result

**F-080** method: a whole-program corpus finds an encoding defect a property harness structurally cannot, a property calling execute on an already-decoded instruction never seeing a mis-encoded word
· Raised: M0.8d
· Disposition: open, the argument for carrying both, and the evidence S13 prices its generators against

**F-081** owed-act: a property that saves a list register and restores it by assigning the saved binding does not restore it, and only the harness's per-property reset hides that
· Raised: M0.8d
· Disposition: open, recorded rather than quietly repaired because a second property stands on the same idiom, correct as run and not correct the moment one wants to observe its own restore

**F-082** measurement: the one-directional refusal set is the point, the symmetric one having refused every composition in this tree
· Raised: M0.8d
· Disposition: standing, the converse being an exploration that has not run rather than a malformed composition

**F-083** measurement: a data-independent latency contract is the signature rather than a comment beside it, the timing function taking an operation class and no operand
· Raised: M0.9
· Disposition: standing, a future consumer wanting an operand showing up as a changed signature rather than as changed arithmetic

**F-084** measurement: the scalar timing table is one table because the front end is one front end, so a per-class scalar latency would be a second front end stated by arithmetic
· Raised: M0.9
· Disposition: standing, the two per-class rows being per class because one kernel binary budgets a switch on every class it may run on

**F-085** measurement: the timing table is deliberately not in the attested devicetree, a latency being none of the five things that artifact enumerates
· Raised: M0.9
· Disposition: standing, the constants being inputs to an off-device derivation rather than values a booting kernel reads

**F-086** owed-act: the crown-jewel row does not move and the qualification flag is what keeps that honest, not one latency magnitude being measured anywhere
· Raised: M0.9
· Disposition: open, what would earn the flip being a total map from every instruction to its class

**F-087** method: the membership rule this item set out to owe cannot be written without becoming the defect it would catch, a mapping from each entry's prose to a class member being a third copy of the correspondence
· Raised: M0.9
· Disposition: closed, membership staying a person's and resting on the profile table an existing rule already holds

**F-088** method: the model's own requirement citations reached no rule at all, the model tree being outside the checker's corpus wholesale
· Raised: M0.9
· Disposition: closed by K-63, for the files the declared model window admits; widening the rule means widening that list

**F-089** upstream-defect: the reference could not name itself, the version stamp running in a build directory that is not a repository, so every emulator this tree built stamped itself unknown
· Raised: M0.10
· Disposition: closed, the stamp running in the tree it describes; cosmetic upstream and freeze-blocking here

**F-090** owed-act: the exit criterion had to be re-read, naming a test suite this machine cannot run and that was retired two items earlier
· Raised: M0.10
· Disposition: closed, the criterion replaced by this repository's own property harness and differential corpus, both printed beside the revision

**F-091** measurement: the revision stamp is set at configure time and the working tree decides it, so only a clean checkout names something a third party could reproduce
· Raised: M0.10
· Disposition: standing, the reference printing the dirty marker rather than refusing it and refusing an unknown revision instead

**F-092** measurement: the emulator's version string still reports the upstream release number, which is right rather than residue
· Raised: M0.10
· Disposition: standing, changing it being a divergence inside the one file every reconciliation reads, to say what two other commands say

**F-093** measurement: a fetch of an instruction wholly inside the executing capability's bounds raised a length violation, the per-granule check asking for a whole instruction from the second granule
· Raised: M0.12
· Disposition: closed, the check taking the width its caller reads and two properties holding both halves

**F-094** measurement: the store-side root arrives in the link register, so a program that calls overwrites its own authority
· Raised: M0.12
· Disposition: standing, every corpus member opening by moving it, and the composed initial distribution being where it stops being the program's problem

**F-095** owed-act: the block-size instrument cannot evaluate its own output, the second-class axis wanting three quantities that exist nowhere in this repository
· Raised: M0.13
· Disposition: open, owed to R4 to author the macro architecture and to R5 to measure it; the matrix ships with both axes empty

**F-096** measurement: the first-class half is computable now, and it turns on a ceiling the destination register sets, a group wider than the register having nowhere to be returned
· Raised: M0.13
· Disposition: standing, the derivable candidate set following from that ceiling and the codeword floor

**F-097** measurement: the declared block size is interior to the derivable set, so a search that scored the array and stopped would return an interval that looked decided
· Raised: M0.13
· Disposition: open, the value inside the set being R-15-014a's second act rather than arithmetic

**F-098** method: holding a model number meant letting one rule read the model, which the selftest's sandbox had made impossible by standing every model path up as an empty file
· Raised: M0.13
· Disposition: closed, a named carve-out read by the sandbox and the rule alike, so an omitted path fails every baseline loudly

**F-099** measurement: two of the four sites that write the welded block size had no assertion behind them at all
· Raised: M0.13
· Disposition: closed by K-57, which reads the constraint arithmetic rather than the set the document states

**F-100** measurement: the per-class record is symmetric and the machine is not, three of its fields having no meaning on the latched class
· Raised: M0.14
· Disposition: standing, the difference held in the validator rather than left to a composition to declare

**F-101** measurement: the retention corner is two fields because only one of them is ever read, a mean with a tolerance inviting the ceiling into a guarantee
· Raised: M0.14
· Disposition: standing, a second consumer showing up as a new call site rather than as new arithmetic

**F-102** measurement: there is no separate fetch constant to declare, every cache being deleted so a fetch is a read of whichever class the code resides on
· Raised: M0.14
· Disposition: standing, the admission-visible delta being the difference of two numbers the record already carries, computed by M1.9

**F-103** method: a placeholder nothing distinguishes from a measurement is how it becomes an architectural input, so the qualification state is carried in the record and attested
· Raised: M0.14
· Disposition: standing, and no property asserts its value, a test fixing it being a test about the calendar

**F-104** measurement: the corpus member is a set of claims that nothing is observable, which is what makes it worth running
· Raised: M0.14
· Disposition: standing, the real difference being a latency constant invisible from inside the machine

**F-105** measurement: the first tag-plane rule found a real disagreement on its first run, an estimate document stating the codeword at the fallback width rather than the frozen one
· Raised: M0.15
· Disposition: closed, the repair rewriting both halves of the sentence and leaving what it argues untouched

**F-106** owed-act: the bank-count clause the item asks for has no operands, only the count being stated and the ceiling it would be compared against being an output of the count itself
· Raised: M0.15
· Disposition: open, the comparison arm opening when M0.8 and M1 land the operands; the rule ships as three bookings

**F-107** method: one field read five ways is one rule rather than five claims, a moved field leaving every spelling individually plausible and jointly wrong
· Raised: M0.15
· Disposition: closed by K-54, with the band beside it held by inequality because its figures are nobody's arithmetic

**F-108** measurement: the compound group stopped being about one document and only its name survived the widening, the two-class placement being the same defect at a different granularity
· Raised: M0.15
· Disposition: closed, the group's run split so that the placement is decided on every path

**F-109** method: a placement is held total over the charge rather than over its own words, so a byte the composition pays for that neither list accounts for is a finding rather than a silence
· Raised: M0.15
· Disposition: closed by K-56, which takes the charge as its enumeration

**F-110** measurement: the discharge needs no mechanism of its own, the ordinary write path already being the cells' write devices and already clearing the tags
· Raised: M0.16
· Disposition: standing, the exit-path discharge being a schedule over the write path and adding nothing to the decode surface

**F-111** method: a window that refuses and a window that is absent are different facts, and only the first can be stated by claiming the address
· Raised: M0.16
· Disposition: standing, an unclaimed address falling through to memory and reading as zero, which is silence rather than refusal

**F-112** measurement: refresh and discharge are modeled differently on purpose, only one of them having architectural content to execute
· Raised: M0.16
· Disposition: standing, and the crossing direction is not taste, the retention floor being multiplied up rather than the sweep divided down

**F-113** measurement: the unit of work is the bank because the walk over the banks belongs to the firmware sequence table rather than to this model
· Raised: M0.16
· Disposition: standing, which also keeps the exit path a property rather than a measurement

**F-114** measurement: the fail-stop's negative reading has no source in a valid composition, this model having no charge to leave behind
· Raised: M0.16
· Disposition: standing, what the model holds being the shape, one read after a fixed dwell with no poll and no retry

**F-115** method: a validator group placed after another inherits what that one already refuses, so a message it repeats is unreachable rather than redundant
· Raised: M0.16
· Disposition: open, a candidate checker rule and the class M3.1 meets again; the arm here became the arithmetic's precondition

**F-116** owed-act: the bank-count search cannot be run, and what it is missing is every coefficient that would make it a search
· Raised: M0.17
· Disposition: open, owed to R5's macro evidence for two coefficients and to M0.8 and M1 for the third's operands

**F-117** measurement: the declared bank count is one doubling from the only shape constraint that can fail, and that constraint points the opposite way from both objectives
· Raised: M0.17
· Disposition: standing, the item's one substantive result, and the figure was a product of three quantities declared in three places

**F-118** method: a pruning predicate with no operands admits everything or nothing, and what changes that is a coefficient quietly acquiring a value
· Raised: M0.17
· Disposition: closed by K-58, which reads the coefficient table's status against the composition's qualification flag in the direction that bites

**F-119** measurement: the estimate document disqualifies its own figures as inputs to this search, its own row closing by saying so
· Raised: M0.17
· Disposition: standing, the contract's refusal list naming it so the disqualification is not rediscovered

**F-120** method: holding a second model number meant a second file inside the checker's reach, so the carve-out moved to where it can be seen
· Raised: M0.17
· Disposition: closed, the named list moving beside the model exclusion it carves out of, read by sandbox and parses alike

**F-121** owed-act: the frozen parameter set was short the per-class bank count, leaving open whether the assignment it did name was that parameter under another name
· Raised: M0.17
· Disposition: closed, R-15-108 now naming both, an assignment presupposing a set of banks rather than fixing how many exist

**F-122** upstream-defect: the retired harness's other half was broken at build rather than dormant, asking for a generated configuration no rule produces, and no gate could see it because the option is off
· Raised: M0.18
· Disposition: closed by the deletion, which removed the loop here rather than upstream

**F-123** measurement: the deletion costs the citation rule a sixth of what it reads and its subject does not move at all
· Raised: M0.18
· Disposition: standing, which is the shape of a window that admits by kind rather than by name

**F-124** upstream-defect: the vendored workflow directory stays byte-identical to its pin and its enumeration of reasons those workflows could not run grows by one
· Raised: M0.18
· Disposition: closed at S3, which deleted the tree whole, the act neither I4 nor I8 refuses

**F-124a** measurement: the corpus assembler never carried a vector-FP row at all, so the follow-through a decode-surface strike was expected to owe did not exist
· Raised: M0.19
· Disposition: closed, the encoder-row half of the rule that reads it unmoved and only its assembly-clause half moving

**F-124b** measurement: a rule measures the strike it structurally cannot catch, both its model-side readings falling by exactly two while its verdict is unchanged
· Raised: M0.19
· Disposition: closed, the profile spelling these forms in prose where the rule reads rows, which is what makes the two figures the item's evidence rather than a rule's

**F-124c** measurement: the profile contradicted itself about the fork inside one section, the amendment adding the paragraph that falsified the one four above it
· Raised: M0.19
· Disposition: closed, repaired in the striking requirement's own vocabulary; no rule reads the pair and none can, the co-read ledger's prose document being the specification alone

**F-124d** measurement: a completed item carried the same claim and its own next bullet already refuted it, naming three encodings the freeze could reclaim
· Raised: M0.19
· Disposition: closed, repaired where it stands, this item being that reclamation for two of the three

**F-124e** owed-act: an extension excluded by name has its exclusion carried by a configuration key rather than by a shape of the model, and no artifact says so
· Raised: M0.19
· Disposition: closed, held by K-87, which holds every excluded-by-name extension the model still gates on a key false in every shipped configuration

**F-124f** measurement: nothing left with the two struck clauses, every candidate checked against its callers by name rather than assumed dead
· Raised: M0.19
· Disposition: closed, the two live encodings the strike named the duplication against standing where they were
## M1 · Toolchain spine

**F-125** upstream-defect: the pinned compiler's dual-licensed subset does not reach the verified backend passes, the target backend, or the capability backend, which are precisely what the re-homing takes
· Raised: M1.1a, in prose
· Disposition: standing, the decomposition read from the pin's own licence file rather than inferred from its lineage

**F-126** measurement: a width re-parameterization moves the definitions mechanically and does not move the proofs, every capability case upstream discharging by splitting on the pointer width
· Raised: M1.2, in prose
· Disposition: standing, the cost measured as tactic repair over two files, two of the goals having selected residuals by index

**F-127** upstream-defect: the pin's directed-store clause reads the address off the value being stored rather than off the authority it is stored through, a pattern variable shadowing the function's own parameter
· Raised: M1.2, in prose
· Disposition: standing, nothing here resting on it, recorded so that a lane re-deriving the rule reaches for the comment rather than the code

**F-128** upstream-defect: the pin's generated configuration puts an ABI flag on three tools and no cross toolchain is installed, and the assembly output reaches the non-capability backend
· Raised: M1.2, in prose
· Disposition: standing, the preprocessor line relaxed for the one output that needs it and the other two waiting on M1.4's toolchain

**F-128a** method: a mapping applied twice in one clause needs its arguments in the key, a lookup by the mapping's name alone giving every application the first one's arm
· Raised: M1.4′
· Disposition: closed, the selector keyed on its argument positions as well as its name; caught by holding the generated constants against the transcription's own encoder over the rows both carry

**F-128b** method: an operand's admitted range is stated in the model's execute clause and in neither the encoding, which fixes only the width, nor the printer, which says how a disassembler displays it
· Raised: M1.4′
· Disposition: closed, the reading taken from the execute clause's own `sign_extend` or `zero_extend`, which answers where the printer answers wrongly twice

**F-128c** method: a name scan bounded on one side reads `unsigned(` as a signed reading and a name as its own prefix
· Raised: M1.4′
· Disposition: closed, the scan bounded on both sides and asked only of an immediate, a register number being an index rather than a value with a sign

**F-128d** measurement: one assembly clause of the model resists generation, its `forwards ... when` body left unstructured by the emitter, so its mnemonic is a skeleton and its operand run is absent
· Raised: M1.4′
· Disposition: standing, `fence` staying the one row of this table the repository writes by hand, with the encoding it resolves to restated beside it rather than half generated

**F-128e** owed-act: nothing decides whether the encoder table carries the model's whole admitted surface or a declared scope, generation having removed the transcription cost the scoping decision was against
· Raised: M1.4′
· Disposition: open, the whole surface carried and the reversal of M0.8b's vector scoping reported rather than performed silently

**F-128f** owed-act: nothing fixes which composition the dialect's admission is taken at, the dialect being one ISA across five core classes where enablement is per-composition
· Raised: M1.4′
· Disposition: open, the union over the three shipped configurations taken with its ground stated, and the entry that would fix it not written

**F-128g** measurement: twelve forms are refused and the twelve are four kinds, eight guarded on a vector register operand the evaluator cannot bind, two printing an operand shape this assembler does not write, one refusing itself on the joint encoding constraint the enumeration over-approximates, and one simply an extension off at the shipped configurations
· Raised: M1.4′
· Disposition: standing, each refused with its own guard quoted rather than admitted on a reading nobody took, and the artifact carrying the twelve strings the run wrote

**F-128h** owed-act: the sidecar stream has no producer, so the composer mints the site ids the join keys on and no artifact says whether they are the ids the backend will carry
· Raised: M1.4′
· Disposition: open, the ids minted as the unit's name and the site's ordinal and reported rather than declared a naming convention this item invented

**F-128i** measurement: a link map's bundle and slot columns filled at the reference instantiation are not a geometry verdict, the contract declaring the candidate set and stating no default arm
· Raised: M1.4′
· Disposition: standing, the geometry a declared parameter of the run and named on the run's own line
· Restates: F-138

**F-128j** measurement: an empty dictionary makes every site a verbatim escape and the stratified hit rate zero, which is a true report about a machine no dictionary has been selected for
· Raised: M1.4′
· Disposition: standing, the selection being the freeze's own first decision and an instrument that took it would be grading its own homework

**F-128k** upstream-defect: the build directory the freeze's producers write into was not ignored, and an untracked file under the checkout is green to the checker and red to the selftest's baseline
· Raised: M1.4′
· Disposition: closed, the directory ignored in the same edit on the generated reading view's exact precedent and anchored the same way

**F-128l** method: the freeze report named all three of its producers in one clause because all three inputs were absent, which two of them landing turned into a claim about a state the run was no longer in
· Raised: M1.4′
· Disposition: closed, the clause derived from the contract's own input table over the absent streams alone, and the same reading carried to the four prose sites that stated it by hand, the report's docstring and fixture line, the analyzer's two pending symbols, and the quarantine's README

**F-128m** method: a test pinning a report's verdict verbatim depends on untracked output the moment that output has a producer
· Raised: M1.4′
· Disposition: closed, the absent state forced by the case rather than assumed, and the end-to-end join it could not make added as a case of its own

**F-128n** measurement: a host-lane generated artifact costs its generator once per checker run and the selftest runs the checker once per case, so a fraction of a second is paid about a hundred times over
· Raised: M1.4′
· Disposition: standing, the cost stated as the generator's own median against the number of runs rather than as a wall clock for the wave, which this host does not reproduce within a factor of two and [the tools' README](../tools/README.md) declines to quote for that reason

**F-128o** method: an un-quarantine condition stated over what an instrument reports is decided by the working directory rather than by the repository, once one of the inputs it counts has a producer whose output the checkout ignores
· Raised: M1.4′
· Disposition: closed, the condition qualified by the run that produces the streams, so the same revision no longer answers it two ways, and the report saying on its own face that absence is read off an ignored build tree

**F-128p** method: a landing that reverses a scoping decision falsifies the document that states the decision, and no rule reads that document's section, so both gates stay green over a contradiction
· Raised: M1.4′
· Disposition: closed for this instance, [the corpus document](differential-corpus.md)'s §3 restated as generation and its vector-scoping paragraph rewritten to what the table now carries; no rule is added, the general case being the standing one S1 reads

**F-128q** measurement: the item arguing that a fact has one owner restated its generated artifact's own header by hand in two documents, where nothing computed it
· Raised: M1.4′
· Disposition: closed, the admitted count registered as a K-24 claim at both sites and recomputed from the artifact under `--fix`; the refusal count is left unregistered and stated in prose, its word form colliding with twenty-three unrelated sentences in K-26's alternation

**F-129** upstream-defect: the container recipe exists for the prover rather than for privilege, and no container runtime is installed on either lane
· Raised: M1.5, in prose
· Disposition: standing, the distribution carrying the compiler and running as root, so neither privilege nor toolchain argues for one

**F-130** upstream-defect: the guest idles out between commands and takes its containers with it, and the switch that disables it is global and permanent on the human's box
· Raised: M1.5, in prose
· Disposition: closed, the fix scoped into the repository as a detached, idempotent, self-expiring keepalive every model loop starts; the class stays open on WSL, S9 being a provisioner rather than a move

**F-131** upstream-defect: an intercepting proxy re-signs the release-asset host, so the exported root CA must be installed into any guest trust store that fetches one
· Raised: M1.5, in prose
· Disposition: standing, a setting on the human's box that no benchmark reaches, and one S9's provisioner does not reach either, standing up a lane rather than a box's trust store

**F-131a** measurement: the lowering route has two exits and neither carries both properties the plan asks of it, the exit that reaches encoded machine code with the proof intact landing on a target the register forbids anywhere and the exit that reaches a capability backend leaving the prover through a printer carrying no theorem
· Raised: M1.6
· Disposition: standing, the fork being what the item measures rather than something it can close
· Restates: F-000z

**F-131b** measurement: the restricted subset's blocker on this artifact is higher-order code rather than the general recursion and the inductive datatypes the earlier reading forecast from the upstream's own description, the first being at zero sites and the second being closed nullary enumerations, because the target language has neither a function value nor an indirect call
· Raised: M1.6
· Disposition: closed, measured construct by construct over the artifact, and the forecasting cell repaired to point at the figures rather than to go on asserting it

**F-131c** measurement: the artifact the plan's section 8 would hand this route is that section's own host-side differential-testing oracle and not the control plane that ships, which the same section assigns to a different compiler and a different item lowers
· Raised: M1.6
· Disposition: standing, so a lowering measured against it decides nothing about the image

**F-131d** method: a re-price that substitutes a route for a dead one carries the dead route's consumer across with it unless the substitution is read against the route list, and the plan's own list already gives this route a different consumer
· Raised: M1.6
· Disposition: closed, the route re-pointed inside the checklist at the consumer the register and the specification already name for it

**F-131e** owed-act: two register entries assume a single lowering path carrying both proof transport and an admissible target, one requiring the synthesis be counted as transport rather than an anchor and the other admitting a verified compilation step freely with no clause about where the transport stops
· Raised: M1.6
· Disposition: open, a register act, and whether the two are one gap or two is a reading this item does not take

**F-131f** owed-act: one consumer in the plan's route list is stale, the arena and extraction bullet naming the static init tree where the init-system section assigns that control plane to a synchronous-dataflow compiler and keeps the Gallina host-side, the rest of the route section already reading it the other way twice
· Raised: M1.6
· Disposition: open, a one-bullet plan act on the route list, which the plan's own opening reserves as the authority on what each milestone means where the execution state is a lane's

**F-131g** upstream-defect: a switch created over the system compiler package keeps the distribution's library directory ahead of its own on the library manager's path, so a package the switch has just installed complete is resolved to the distribution's incomplete copy and the build reports it absent rather than shadowed
· Raised: M1.6
· Disposition: closed, the switch re-created over a compiler of its own, which is what the proof gate's switch already does; the class stands wherever a switch reuses the system compiler
· Restates: F-000j

**F-131h** upstream-defect: the upstream ships an inductive-datatype example that it does not lower, and half its example files carry no derivation at all, every data-structure example among them
· Raised: M1.6
· Disposition: standing, which is what makes the per-constructor price for a datatype a forecast rather than a measurement even where it is right

**F-131i** measurement: the emitted C reaches the non-capability backend from a Gallina source, and the capability printer's stubbed arms are exactly the arithmetic, the branches and the loads and stores through a capability that a derived loop needs
· Raised: M1.6
· Disposition: standing, nothing here resting on the capability output, and the chain measured end to end rather than at the compiler alone
· Restates: F-128

**F-131j** owed-act: the intermediate language the register entry, the specification and the plan all name for this route is emitted by neither of its exits, one going straight to encoded machine words and the other to C source text through a printer and a second front end
· Raised: M1.6
· Disposition: open, a register act reported and not closed, and the checkable half of the gap the entry pair above states as a silence

**F-132** method: an instrument's landed half was gated on neither milestone the plan books it behind, what it needs from a backend being a transport rather than a design
· Raised: M1.8a
· Disposition: standing, and it is the acceptance-predicate convention paying out as booked

**F-133** owed-act: the plan's ordered act and the contract's read as two different orders, one being the recipe's and the other the decisions'
· Raised: M1.8a
· Disposition: open, what would settle it being a word in the plan saying which its list is; the instrument runs both and prints both

**F-134** measurement: the encoded image cannot be decoded per site before the geometry decision is taken, so the analyzer's third input arrives on two paths
· Raised: M1.8a
· Disposition: closed, the composer delivering the image's bytes beside a per-site entry-and-escape table, the join unchanged

**F-135** measurement: two of the three declared bundle geometries are already decided at the break-even hit rate, which is the one substantive result the instrument produces today
· Raised: M1.8a
· Disposition: standing, all three being readings of the model rather than the acceptance test, and what they decide is where the sweep's attention goes

**F-136** method: a gate with two outcomes prints the same lines whether or not a predicate has a body, so each predicate is seeded a defect it must reject by name
· Raised: M1.8a
· Disposition: closed, and two predicates needed their reading widened to reject at all

**F-137** measurement: the contract's column paragraphs are not a membership a rule can read, one backtick idiom carrying three vocabularies in one sentence
· Raised: M1.8a
· Disposition: standing, a property of the document rather than a gap in K-77; the column sets are the instrument's schema and its own tests hold them

**F-138** owed-act: one decision states no default arm and gives no ground for having none, where its neighbour in the same position states both
· Raised: M1.8a
· Disposition: open, owed to the contract; the instrument carries the absence with that ground rather than inventing a default

**F-139** method: a membership held in both directions is not a relation held in both directions, a relation walked from one side reaching only what that side names
· Raised: M1.8a
· Disposition: closed, both of K-77's relations quantified over the union of the two rosters

**F-140** method: a floor under the document does not floor the rule, a comparison deleted from a rule leaving every gate green and every mutant killed
· Raised: M1.8a
· Disposition: closed, the two relations carrying a floor over their own size and the rule taking three selftest cases rather than one

**F-141** method: a shared parse that reads a path off disk is outside the checker's corpus, and the checker's corpus is the git index
· Raised: M1.8a
· Disposition: standing, the one place a rule and the tool sharing its parse have to differ, a document deleted from the index being one this repository does not have

**F-142** owed-act: the contract says its gate makes an omission a rejection and no predicate of that gate does, the rule in question being the one it calls its most consequential
· Raised: M1.8a
· Disposition: open, the missing predicate being the contract's to add rather than the instrument's to invent; the record carries the rule per variant meanwhile

**F-142a** owed-act: no entry closes the enumeration of region kinds a composition may place, two lists naming twenty and a third entry a twenty-first while the charge's tenth term is answered by criterion rather than by name
· Raised: M1.9
· Disposition: open, the inductive being the register's own names plus the by-criterion arm and carrying no count; owed at the entry whose closure criterion is stated over the charge's terms rather than over the kinds

**F-142b** owed-act: whether the placement delta is charged per region or per task is unstated, one entry pricing second-class code placement and another charging a task's real cost, so a task whose code spans two regions is addressed by neither
· Raised: M1.9
· Disposition: open, the artifact charging per region and summing nothing

**F-142c** owed-act: whether a hard task may hold any code on the second class at all is unstated, the placement rule putting all hard-task code on the first class and saying nothing about a hard task calling a cold second-class routine
· Raised: M1.9
· Disposition: open, the artifact stating the placement rule over region kinds and stating no reachability relation

**F-142d** owed-act: which regions an origin-pool member owns is unstated, one entry booking the ceiling raise as a consequence and another fixing the pool at identical compartments with one manifest and one static memory plan, and neither enumerating a member's regions
· Raised: M1.9
· Disposition: open, the roster being a field and the ceiling stated over an arbitrary roster and an arbitrary population bound

**F-142e** owed-act: what a statically planned object's live range is measured in is unstated, one entry fixing the range at compile time and another making the side condition an interference test over it, with no entry naming the ordering it is an interval of
· Raised: M1.9
· Disposition: open, two fields carrying an interval over nat and no unit claimed

**F-142f** owed-act: the interference side condition's own quantifier refuses the mechanism it is a side condition for, slot disjointness over *disjoint* live ranges demanding separate slots of exactly the pair the collapse onto the proven simultaneous peak exists to colour together
· Raised: M1.9
· Disposition: open, the inversion machine-checked rather than argued, the literal reading refusing the shared-slot plan and admitting the overlapping-live one where the reading taken answers the other way on both

**F-142g** owed-act: every composition magnitude of the two-class plan is a field no entry fixes, the roster, the kinds, the cycle-criticality judgment, the assignment, the geometry, both class constants, the fetch counts, the charged slots and the budgets among them
· Raised: M1.9
· Disposition: open, the demo plan instantiating them with arbitrary witness values that carry no composition claim

**F-142h** measurement: every kill in the memory-plan population is the prover's, the enumerative Gallina harness computing over three other artifacts so that no mutation of this one can move a vector and the second oracle could not have contributed a kill
· Raised: M1.9
· Disposition: open, as F-189 is, the measurement falsifying nothing this item claimed and the act that would move it being the tools one F-189 names
· Restates: F-189

**F-142i** owed-act: a mutant costs a recompile of every shipped proof where only the mutated source and its dependents can move, and nothing in the tree requires this one, so most of each mutant is spent where the mutation cannot reach and the share grows with every artifact a lane lands
· Raised: M1.9
· Disposition: open, narrowing the recompile to the mutated source and its dependents being a tools act

**F-142j** owed-act: a whole-population Coq mutation run does not survive a fan-out, the guest distribution being torn down under it or wedged against launching it at all with three and four lanes running the same loop beside it, and the loop takes none of the keepalive lease every model loop takes while printing its report once at the end
· Raised: M1.9
· Disposition: open, both halves being tools acts; the population was decided instead by runs partitioned by operator whose union is the whole of it, detached in the guest so no host-side lifetime reaches them

**F-142k** measurement: no rule computes a proof artifact's line count, and the figure a cell carried for one had drifted off the file by a line while the file itself was unmoved
· Raised: M1.9
· Disposition: closed, the figure re-measured at this gate with every other figure that cell states

## M2 · Fast emulator

**F-143** upstream-defect: the fork derives the capability width from the target word size and has no arm for the frozen combination, a capability being twice a register on every target it carries
· Raised: M2.1, in prose
· Disposition: closed in the fork, the width stated by the target with the old inference kept as the default and the other base refused outright

**F-144** owed-act: the bounds-setting containment property holds over a domain that nothing states, the decoded top wrapping below its own base above it
· Raised: M2.1
· Disposition: closed, taken at R-15-007a, which now states the containment domain as a requested top at or below 2^36 and owes the format's property harness that edge

## M3 · Boot chain

**F-145** measurement: the type-level geometry knob cannot say vectorless, its constraint excluding the value that would mean it, and every ladder rung is gated on the knob alone
· Raised: M3.1
· Disposition: closed, the file declaring the type's floor and K-78 holding a vectorless composition below every rung; the cost is stated rather than absorbed

**F-146** owed-act: a seeded generator evades the deterministic-replay obligation rather than discharging it, a seed in a configuration file replacing nondeterminism with determinism
· Raised: M3.1
· Disposition: open, no item owning the replay nondeterminism record R-15-241 and R-16-015 onward specify; S6 is the act

**F-147** method: one validator arm was dead the moment it was written, the ceiling being the type's and refused at schema conformance before the validator runs
· Raised: M3.1
· Disposition: open, the same class one artifact over; the floor is the opposite case and no type expresses it
· Restates: F-115

**F-148** measurement: the watchdog carries no ratio to the spine, and that is a requirement rather than an omission
· Raised: M3.1
· Disposition: standing, a divisor beside the two bounds being exactly the asynchronous crossing the requirement refuses to model as fixed-latency

**F-149** measurement: the two fail-closed seams compose, a latched health-test failure leaving no challenge to answer so the watchdog bites
· Raised: M3.1
· Disposition: standing, asserted as a property rather than left to be discovered, the other reading being the degraded path the requirement refuses

**F-150** measurement: the corpus member's ground differs from M0.8c's, every configuration here having the four windows so a program reaches them from the outside
· Raised: M3.1
· Disposition: standing, M0.8c's disposition still governing what the management core itself sees

**F-151** measurement: the attested tree's device windows ride the address-map requirement rather than the attestation one, a device window being none of the five things the second enumerates
· Raised: M3.1
· Disposition: closed, and the memory sequencer's node was already in that position without saying so

**F-152** measurement: what the model stops at is the debug gate, the register putting the gate in Sail and the debugger nowhere
· Raised: M3.1
· Disposition: standing, and the same line is where the item stops for every firmware-side duty

**F-153** measurement: the watchdog's window bounds do have an owner, an admission artifact that emits them with the operating-point assignment and the interconnect schedule
· Raised: M3.1, in prose
· Disposition: standing, so their absence from the frozen parameter set is a correct sorting and not a gap

**F-154** owed-act: the start-up sample budget is owed to a source stochastic model this repository does not hold and no milestone on the plan authors
· Raised: M3.1, in prose
· Disposition: open, S5 being the act that authors it

**F-155** owed-act: no item owns the deterministic-replay nondeterminism record, so the obligation stands live and unscheduled
· Raised: M3.1, in prose
· Disposition: open, S6 being the act; stated from the register's side where F-146 states it from the model's
· Restates: F-146

**F-156** owed-act: two requirements cannot both be true of the Debug Module, one closing it permanently at the transition out of test and the other making entry an authenticated exchange in a later state
· Raised: M3.1, in prose
· Disposition: closed, taken at R-09-034, which carves the Debug Module out of the permanent test-exit closure and leaves it live in development and RMA alone

**F-188a** owed-act: where the entropy verdict is extended against the boot-target latch is unordered, one entry fixing the lifecycle extension first and another the verdict before any measured stage draws, with neither placing the latch the third measures *like every other input*
· Raised: M3.2
· Disposition: open, the two orders shown at the item to reach different digests, so the silence is observable rather than harmless

**F-188b** owed-act: whether the chain measures each stage before running it or places the payload up front is unfixed, one entry fixing only the pairwise precedence and another taking the front-loaded shape for a single stage and saying nothing about the rest
· Raised: M3.2
· Disposition: open, both shapes stated and shown to reach the same digest, so what is unfixed is what ran between the extensions rather than what was measured

**F-188c** owed-act: what a successful boot does to the boot-attempt count is unstated, the counting and the automatic revert being fixed and the entropy halt carved out as a fault class consuming no attempt, with no entry saying whether a success clears the count
· Raised: M3.2
· Disposition: open, the item modelling that entry's two failure classes and no success

**F-188d** owed-act: what the reference integrity manifest covers where it differs from the quote is unstated, the entry making it the dual *covering the same vector* and stopping there
· Raised: M3.2
· Disposition: open, the appraisal stated over whatever vector the quote covers and no manifest-side enumeration invented

**F-188e** owed-act: whether the attestation vector's *this set* names four terms or five is unfixed, the criterion saying *the quote's vector*, which is not the quote, and one neighbouring entry carrying the referent over without fixing it while another constrains the lifecycle state rather than the chain
· Raised: M3.2
· Disposition: open, the item taking the wide reading as a stated judgment carrying this gap rather than as an enumeration the register closes, and pricing the narrow one by computing that a relying party appraises clean on a forked chain

**F-189** measurement: neither differential instrument reaches the root-of-trust firmware artifact, the whole mutation score being the assumption gate refusing to compile, because the QuickChick harness requires two unrelated proof artifacts and nothing stages this one
· Raised: M3.2, in prose
· Disposition: open, reported and not closed, falsifying that item's own pricing of its validation half as generated; the act owed is a tools one rather than a proof one, of the shape M4.3 performed for the kernel surface

**F-186a** owed-act: which codepoint names which permission set is unfixed, the lattice being enumerated at freeze time and no artifact here carrying the enumeration
· Raised: M3.3
· Disposition: open, so the decode is a field and every one of the item's exclusion obligations is stated of an arbitrary one

**F-186b** owed-act: a normative clause states the mechanism its own criterion demotes, grounding the invariant on monotonicity and an absence in the static capability distribution where the criterion discharges it at the permission encoding and keeps the distribution check as redundant confirmation alone
· Raised: M3.3
· Disposition: open, the asymmetry machine-checked at the item rather than argued: the composed distribution passes on a machine whose encoding assigns the combination, so the two checks are not one check stated twice

**F-186c** owed-act: what *running kernel state* comprises is unstated, no entry saying whether the partition contexts one requirement restores and the schedule table another swaps are inside the phrase or beside it
· Raised: M3.3
· Disposition: open, the item stating the capability distribution alone, which is the narrowest reading the entries fix

**F-186d** owed-act: what completes a core's root set is unstated, the bound being fixed and the totality only ever *some root per core*, with no artifact distinguishing an image's text extent from its data extent at a region
· Raised: M3.3
· Disposition: open, the bound stated and the totality stated at the weakest thing the entries carry

**F-186e** owed-act: an acceptance criterion audits a resident-code inventory no artifact enumerates, not the register, the prose, the proofs, the model or the corpus
· Raised: M3.3
· Disposition: open, one entry over the shape M4.2a met at the invocation list, and closing the way that one closed
· Restates: F-157

**F-186f** owed-act: a Tier-0 proof obligation has no owner, the no-ambient-state clause being put on the firmware as ordinary proof over its statically planned state and no artifact here being that proof
· Raised: M3.3
· Disposition: open, the item shipping the obligation stated and refuted, which is a statement and not a discharge

**F-187** method: an upstream's licence election is stated in this repository's own prose rather than read at the upstream's own file, which is the inference from lineage this page forbids and has already had to correct once
· Raised: M3.4, in prose
· Disposition: closed, the reading taken at the pin in M3.4a: the election is confirmed at the upstream's own `COPYRIGHT`, which is the file that states it, and the record now carries the file, the commit and the date beside the arm

**F-205a** owed-act: the acquisition route chosen to avoid a non-commercial term neither avoids it nor delivers the two developments it was chosen for, its package declaring a dependency on the compiler and its build and install targets reaching neither of the two directories
· Raised: M3.4a
· Disposition: open, reported and not closed, the call belonging to the milestone cell that took it

**F-205b** owed-act: no entry fixes the oracle pair for an authored hash, one entry naming the standard and the vector corpus for the *model's* unit and a milestone cell wanting two oracles of independent verification lineage with nothing choosing which two
· Raised: M3.4a
· Disposition: open, the pair pinned on this item's own stated ground and named as the item's choice rather than the register's

**F-205c** owed-act: an item title named one classical signature and the frozen suite carries none, the split being hash-based at every ROM-verified object and lattice above it with every parameter set at Category 5
· Raised: M3.4a
· Disposition: open, the title retaken to what the item delivers and the scheme the plan's sentence meant left undecided

**F-205d** owed-act: which AEAD a Gallina module owes is unfixed between two documents, one having both authored and the register freezing one cipher and naming the other the frozen-out alternative
· Raised: M3.4a
· Disposition: open, the residue item naming what the register freezes and reporting the disagreement rather than resolving it

**F-205e** owed-act: an acceptance criterion audits a crypto inventory no artifact carries, wanting three evidence entries per primitive where nothing enumerates the primitives at all
· Raised: M3.4a
· Disposition: open, one entry over the shape F-157 already carries and closing the way that one closes

**F-205f** owed-act: a mandate's acceptance has nothing to audit, every field-arithmetic implementation being required to trace to a derivation while no generator run exists and no emission is tracked, so pinning the generator is not the trace
· Raised: M3.4a
· Disposition: open, residue named to M3.4c, which is the item that would run the generator

**F-205g** owed-act: a firmware machine declares a hash field no hash function realizes, asking for total separation of distinct inputs where collisions exist and the register's own assumption is computational
· Raised: M3.4a
· Disposition: open, the function supplied and the field left a declared assumption

**F-205h** owed-act: one of the five step mappings is not shown invertible, so the acceptance clause calling the permutation a permutation is stated and not closed, that step being a linear map on the column-parity space whose inverse is dense
· Raised: M3.4a
· Disposition: open, the other four discharged on arbitrary inputs and the composite left as an obligation the artifact states

**F-205i** method: no rule in the checker reads a Gallina source, so nothing holds the two transcriptions of one standard together, the pair being a discipline that each artifact's own gate executes rather than a mechanism
· Raised: M3.4a
· Disposition: standing, a rule reaching into the proofs directory needing a corpus-window change that leaves the host checker green and every sandbox baseline red

**F-205j** measurement: the Gallina vector harness reaches no artifact of this item either, so the whole mutation score is the prover's and the validation half is not the generated one the label prices
· Raised: M3.4a
· Disposition: open, the note pricing the half as authored statements rather than as generated inputs
· Restates: F-189

**F-205k** upstream-defect: the vector corpus states its terms in a README because it carries no licence file at any name, and the conditions are three rather than the two this plan counted, notice retention, a change notice, and explicit acknowledgement of the source
· Raised: M3.4a
· Disposition: standing, the terms recorded at the instrument and no row added to the fetched table, which wants a tracked licence file this component has none of

**F-205l** owed-act: an item shed four of its parent cell's deliverables into a new sibling at exit rather than at entry, so its recorded actual is not an outturn against the scope the estimate was taken over, and no clause anywhere says an actual may be incomparable to its estimate while the calibration re-fits every such pair whatever it means
· Raised: M3.4a
· Disposition: open, the datum named unusable for calibration at the item's own cell, a convention for an exit-time residue split being the plan's to state at the calibration paragraph and this being its first

**F-156a** owed-act: the data-plane disjunction has no arm selected, one entry admitting a deterministic clear or a confirmed discharge while another commits both planes atomically at the granule and a third insists the two are two boundaries
· Raised: M3.6a
· Disposition: closed, taken at R-15-247d: the disjunction resolves to one pass over both planes, so the transition carries one dwell and one read rather than two of each

**F-156b** owed-act: the completion indication's arity against the bank staggering is unstated, one read per transition, one per phase and one per bank being three budget terms and three degrees of partiality visibility
· Raised: M3.6a
· Disposition: closed, taken at R-15-247f: the read is per phase, per transition being refuted by DischargeSequence.v's own construction and per bank costing the bank count

**F-156c** owed-act: an acceptance clause is a necessary condition rather than its criterion, a bank nothing reached satisfying *no path admits a partially sanitized bank*
· Raised: M3.6a
· Disposition: closed, taken at R-15-247d, which states the clause and the completion read's domain as two obligations, each catching what the other cannot

**F-156d** owed-act: the reset hold has no scope, a die-wide hold and the one island kept live across standby with an admitted hard task on it not both holding as written
· Raised: M3.6a
· Disposition: closed, taken at R-15-247h: the reset hold is scoped to initiators that can address the domain, which is what leaves R-15-190's admitted hard task standing

**F-156e** owed-act: where the fail-stop latch lives is unstated, two entries latching on a negative reading and neither naming the power domain the latch sits in
· Raised: M3.6a
· Disposition: closed, taken at R-15-247f: the latch sits in the always-on root-of-trust domain, the discharge being taken on the path that collapses the rail

## M4 · Kernel

**F-157** owed-act: an acceptance criterion audits an artifact that does not exist, no artifact here carrying the invocation enumeration it calls enumerated and closed
· Raised: M4.2a
· Disposition: closed, taken at R-07-031b, which enumerates the invocation list and closes it at five with an amendment criterion, in the register the review gate audits

**F-158** owed-act: three entries state incompatible things about one act, two fixing synchronous endpoints and run-to-completion with no blocking call and a third naming a wait the register defines nowhere
· Raised: M4.2a
· Disposition: closed, taken at R-07-029a: synchronous means rendezvous or refusal, which is the only reading on which all three entries agree and the only one R-11-006 admits

**F-159** owed-act: whether the intra-slot rotation swaps the pending bits is unstated, and the silence is observable rather than harmless
· Raised: M4.2a
· Disposition: closed, taken at R-07-037c: the rotation swaps the pending component, those bits being delivery state rather than residue

**F-160** owed-act: a same-label group member begins its reaction on state the rotation does not clear, and no entry says what it may assume about it
· Raised: M4.2a
· Disposition: closed, taken at R-07-037d, which states the in-domain assumption R-07-037b's own ground for omitting the zeroize was already resting on

**F-161** owed-act: an invariance criterion enumerates the admission check's inputs more narrowly than the two entries that state the check
· Raised: M4.2a
· Disposition: closed, taken at R-11-023, whose criterion now names the four quantities the invariance is proved over, with the prose carrying the narrow reading repaired

**F-162** owed-act: the switch cost is fixed at three terms and names neither the total restore nor the pending swap among them, while two other entries put both inside the budget
· Raised: M4.2a
· Disposition: closed, taken at R-15-220a: the restore and the swap are a context term beside R-15-220's three platform terms, so no entry consuming the constant moves

**F-163** owed-act: the surviving object count is five in the prose and three or four in the register, and nothing enumerates the five
· Raised: M4.2a
· Disposition: closed, taken at R-07-027a, which resolves the count as a conflation of two kinds rather than by picking a number, and settles that no reply object survives

**F-164** owed-act: the rule registry has a gap in its numbering that nothing records and no rule can see, the id occurring nowhere else in the tree
· Raised: M4.2a
· Disposition: closed, held by a struck row in the rule registry recording that the id was never allocated and is not reused, written struck so K-00 holds the live rows alone

**F-192a** owed-act: the badge width of the message transfer shape is unfixed, one entry fixing the transfer and another the bit budget, with nothing joining them
· Raised: M4.2b
· Disposition: open, the transfer stated over an arbitrary width

**F-192b** owed-act: what a typed refusal's type enumerates is unfixed, the refusal being required and its cause set named nowhere
· Raised: M4.2b
· Disposition: open

**F-192c** owed-act: which of the closed five invocations may refuse is unfixed
· Raised: M4.2b
· Disposition: open

**F-192d** owed-act: the ABI numbers themselves are fixed nowhere, the surface check being stated over membership while the artifact also exhibits a second numbering over the same five that passes the same check
· Raised: M4.2b
· Disposition: open, the choice exhibited rather than argued

**F-192e** owed-act: what a re-offer costs and how many are admitted is unfixed
· Raised: M4.2b
· Disposition: open

**F-192f** owed-act: whether a notification word is per partition, per endpoint or per ring is unfixed
· Raised: M4.2b
· Disposition: open

**F-192g** owed-act: whether an endpoint's readiness is one bit or one per offering peer is unfixed
· Raised: M4.2b
· Disposition: open

**F-192i** owed-act: what carries the compositor's request for a focus rebinding, a rung selection or a suspension, and so whether the three trap, is unfixed, the entry closing the invocation surface naming the three as kernel-enacted at a frame boundary without saying what carries the request
· Raised: M4.2b
· Disposition: open, the trap surface left a parameter with the criterion the register does fix stated over it, two values admitted and three refused, and the one result that would otherwise turn on the gap proved of every admissible value

**F-192j** owed-act: which of create, derive and revoke each surviving object class has is unfixed, one entry stating the lifecycle only negatively of the two tables while two others delete the derivation invocation and carry no create in the closed five
· Raised: M4.2b
· Disposition: open, the artifact stating the distinction the entry does draw and exhibiting a second map that discharges both obligations while disagreeing at cells no obligation reads

**F-193** measurement: the Wasm oracle cannot report a defect in the artifact's own deciders that the proof gate would not report first, twelve one-token decider mutations being twelve stillborn, so what it uniquely tests is the compiled pipeline rather than the deciders
· Raised: M4.3, in prose
· Disposition: open as a standing reading of what staging a statement artifact into that loop buys, the loop's value being kernel conversion against the erasure and Wasm backend on a real artifact rather than a regression net

**F-165** owed-act: the emulator runs one hart and every shipped configuration composes one, so the multikernel's defining property is first exercisable on the RTL track
· Raised: M4.4, in prose
· Disposition: closed, taken at M4.4: single-instance bring-up, the multikernel's defining property being first exercisable on the RTL track where a second implementation stands

## M5 · Storage and objects

**F-194a** owed-act: the entry naming the storage layers states no property of a commit, being a layer roster and a prover-provenance criterion, so the multi-block atomicity obligation is owed at the entry whose acceptance clause says no partially updated region is ever committed
· Raised: M5.1
· Disposition: open, re-anchored at that entry, which commits a checkpoint as a single transaction and still names no mechanism

**F-194b** owed-act: no entry chooses a recovery discipline, one naming the log's lineage and stating no recovery rule and another stating the enumerate-and-select rule of the root copies rather than of the log
· Raised: M5.1
· Disposition: open, both arms exhibited over an arbitrary discipline, each proved to keep every obligation the other keeps, and the choice machine-checked to be observable from one crashed journal

**F-194c** owed-act: no entry of the storage section states a block-reuse rule, the nearest being refcounted extent sharing which states no obligation over the allocator, with the allocator left trusted for availability and one free-space pool given to the subvolumes without saying who may take from it
· Raised: M5.1
· Disposition: open, the capability-revocation entry that does state such a rule reaching no disk block

**F-194d** owed-act: no entry fixes an atomic write unit for the persistent medium, one being fixed for the main-memory array and a per-page code for NAND, while a torn write is said to cost a copy without saying at what unit a write is atomic
· Raised: M5.1
· Disposition: open

**F-194e** owed-act: no entry says an L0 record is self-verifying, that being said of a root candidate alone, and a log that cannot tell a torn record from a whole one has no recovery point
· Raised: M5.1
· Disposition: open

**F-194f** owed-act: no entry names what ends a transaction, a checkpoint being committed as a single transaction with no mechanism named for the commit itself
· Raised: M5.1
· Disposition: open

**F-194g** owed-act: the word fanout occurs in no entry, and no entry fixes a node's minimum occupancy or whether an empty index is a legal tree
· Raised: M5.1
· Disposition: open

**F-194h** owed-act: every composition magnitude of the journal and the index is a field no entry fixes
· Raised: M5.1
· Disposition: open, the demo instantiating each with a witness value that carries no claim

**F-195a** owed-act: the entry representing typed keys does not close its list of kinds, naming four things the layer represents while a neighbouring entry adds a fifth candidate without saying whether it is a kind or a component of the four
· Raised: M5.2
· Disposition: open, the count made a field of the composition and a kind a finite index below it, on the precedent where an object inventory had to be closed in the register before authoring could proceed

**F-195b** owed-act: whether a stored extent's existence is observable to a reader holding no key for its domain is unstated
· Raised: M5.2
· Disposition: open

**F-195c** owed-act: whether an extent's plaintext length is observable is unstated and no entry bounds the leak, which is the residual a design of this kind ordinarily books explicitly
· Raised: M5.2
· Disposition: open, and the largest consequence of this item's nine

**F-195d** owed-act: whether the confidentiality-domain label of a stored extent is observable is unstated
· Raised: M5.2
· Disposition: open

**F-195e** owed-act: whether the rescan-required marker occupies a slot of the declared queue bound or stands beside it is unstated
· Raised: M5.2
· Disposition: open

**F-195f** owed-act: whether a recorded right may be persisted into a key is unstated, one entry forbidding a capability there and another admitting exactly one durable record that names rights and confers none
· Raised: M5.2
· Disposition: open

**F-195g** owed-act: the entry writing ordered deltas names no order over them
· Raised: M5.2
· Disposition: open

**F-195h** owed-act: what a freshness-protected region's version is, and what unit such a region is, are unstated, one entry computing a root over the version of every declared region without fixing the representation and another not fixing a region's extent in the keyspace
· Raised: M5.2
· Disposition: open, the epoch obligations stated over an arbitrary version pair and an arbitrary declaration

**F-195i** owed-act: every composition magnitude of the two upper layers is a field no entry fixes, the kind roster and the snapshot's declared cost among them
· Raised: M5.2
· Disposition: open

**F-196** method: a name a file declares beside one it imports shadows silently and no gate reads it, so a file claiming to restate no imported theorem can restate nine of them while every count stays correct
· Raised: M5.2, in prose
· Disposition: closed at the item by renaming all nine and instantiating the four genuinely inherited theorems by conversion, so the sharing a Require is taken for is checked rather than asserted; standing as the hazard any second Require will carry

## M6 · Userland spine

**F-216** upstream-defect: the interface-definition start-from states its terms through a one-line pointer to a second file and the forge reports its licence as `NOASSERTION`, so a reading taken at the forge carries no instrument at all and one taken at the announcement misses that the pointer defers to subdirectory licences
· Raised: M6.0b
· Disposition: standing, the deferral resolving at the tree's own licence-file inventory, which carries two files and no subdirectory carve-out

**F-216a** measurement: the wire-layer exemplar's own licence file is the two-clause BSD instrument and not the three-clause one the common characterization carries, there being no name-endorsement clause in it
· Raised: M6.0b
· Disposition: standing, taken twice on two independent renderings of the same file because the contradiction with the usual characterization is the inference from lineage the maturity rule forbids

**F-216b** owed-act: no register entry pins the typed IDL profile or names its version, where the language document one artifact over is pinned by name and its bump made a review-gate event, so an amendment to the profile's constructor set or its wire-format mapping is not a register edit and the gate never reads it
· Raised: M6.0b
· Disposition: open, the profile declaring its own version and amendment rule as a declared parameter instead; F-190a's shape met a second time, on a document nothing pins rather than on enumerations a pinned document holds

**F-216c** owed-act: the fork-and-frozen start-from is unnamed in the register, only the specification's prose and the prior-art document saying what the fork is a fork of, so naming it is a maturity claim with no register owner
· Raised: M6.0b
· Disposition: open, the profile naming it as a declared parameter over the register's silence

**F-216d** owed-act: fork-and-frozen has no freeze act for this profile, no entry saying when it freezes, what its delta is, or what a post-freeze change costs beyond the general amendment rule, where the instruction-set profile has a two-act freeze with a closed delta and an instrument per row
· Raised: M6.0b
· Disposition: open, the profile declaring its own version and the amendment rule it asks for

**F-216e** owed-act: no entry closes the type-constructor set, the restriction entry restricting without enumerating what constructors exist, so the profile's table is closed by that document and by nothing the gate audits
· Raised: M6.0b
· Disposition: open, the object-inventory closure at M4.2b being the precedent for the register act that would close it

**F-216f** owed-act: whether a floating-point type is admitted is unstated, and it bears on canonicity rather than on taste, NaN payloads and signed zero giving one value several encodings where the no-slack rule forbids a second admissible encoding
· Raised: M6.0b
· Disposition: open, the profile deleting the former as a declared parameter carrying both arms and what each forfeits

**F-216g** owed-act: the string former has no admitted encoding and no statement of what its bound counts, the restriction entry requiring an explicit bound and saying nothing about bytes against code points, which encoding is admitted, or whether an ill-formed sequence is a decode failure
· Raised: M6.0b
· Disposition: open, the profile fixing the encoding as a declared parameter, over-long sequences being exactly the one-admissible-form case

**F-216h** owed-act: which result type carries the relevance grade is unstated, the closed list of graded result kinds naming IDL call outcomes as one member while a per-operation closed refinement variant is admitted beside the common status set, and nothing saying whether a refinement is graded at its own definition or inherits
· Raised: M6.0b
· Disposition: open, the profile grading every result type at its own definition as a declared parameter

**F-216i** owed-act: the relevance grade has no stated wire consequence, its placement entry putting it at the definition and its content entry making it a typing property, so a mapping that encodes it and one that does not are both admissible
· Raised: M6.0b
· Disposition: open, the profile carrying no wire field for it, a grade on the wire being a field the no-slack rule would then have to admit no slack in

**F-216j** owed-act: the flow-label lattice has an owner and no enumeration, the build-time composition entries fixing the lattice with the composed topology and forbidding either sanctioned transfer from adding a label, while no entry states the lattice's membership, its order, or its join and the security policy model that would enumerate one is unauthored
· Raised: M6.0b
· Disposition: open, the profile declaring the place the labels sit and stating its obligations over an arbitrary lattice rather than inventing one

**F-216k** owed-act: whether the IDL's own wire format is a member of the wire-format inventory is unstated, translator content formats being placed in it and each descriptor there separately conferred, while the IDL mapping is a crown-jewel row of its own
· Raised: M6.0b
· Disposition: open, adding it being a crown-jewels and a register act

**F-216l** owed-act: whether the wire-format mapping is on an identity-bearing path, and so owes a canonicity theorem, is undecided, one entry putting the interface descriptor inside the content-addressed manifest and another's enumerated site list not naming a live IDL call
· Raised: M6.0b
· Disposition: open, the profile taking the stronger reading as a declared parameter and admitting no slack anywhere

**F-216m** owed-act: the receiver-validation declaration has no vocabulary, the entry requiring the IDL to declare which received values carry the index, length, offset or selector obligation and saying nothing about whether that is a per-field marker, a per-operation clause, or a type of its own
· Raised: M6.0b
· Disposition: open, the profile taking a per-field marker plus a per-operation claim for the empty case as a declared parameter

**F-216n** owed-act: the resource former has a control-plane reading and a data-plane reading and no entry says whether that is one constructor or two, one entry mapping resources to capabilities and two others admitting only session-table indices on the data plane
· Raised: M6.0b
· Disposition: open, the profile carrying one constructor with two declared readings, the reading a property of the field

**F-216o** owed-act: nothing bounds the size of a declaration, every bound in the register being a bound on a runtime value, so the number of operations, types, fields, or worlds a declaration carries is a composition magnitude with no owner
· Raised: M6.0b
· Disposition: open, stated as a field rather than a figure, which is the idiom the landed Gallina items already use

**F-216p** owed-act: the Coq interface subset has no stated boundary, one entry's criterion requiring a Tier-1 proof to be stated against the matching skeleton and another requiring conformance among four generated artifacts, with no entry saying what a skeleton contains
· Raised: M6.0b
· Disposition: open, the profile fixing six contents and no seventh and recording the decision in its declared-parameters table rather than presenting it as a reading

**F-216q** owed-act: two coverage cells read as though the interface profile existed, one at mode `proved` over the entries that fix the profile and its object references and one at `admission-rejected` over the restriction and the standing rules, and authoring the profile makes neither proved, no proof, checker or declaration following from a specification act
· Raised: M6.0b
· Disposition: open, reported against the matrix rather than repaired, no cell being owed by this item and a mode change being a register-first act

**F-216r** owed-act: the crown-jewel row the wire-format mapping is conferred on reads `not authored` and is ready to flip at the mapping's own section
· Raised: M6.0b
· Disposition: open, the flip being a crown-jewels edit whose reading is the release gate's rather than the lane's

**F-216s** owed-act: no entry gives an interface declaration an identity that moves when the declaration moves, the admission criterion deciding a proof against *the matching skeleton* and naming nothing a match is decided on, so a declaration edited in place leaves a proof stated against the superseded skeleton still matching
· Raised: M6.0b
· Disposition: open, the profile fixing a content address over the declaration's bytes as a declared parameter and deciding matching on it

**F-216t** owed-act: the wire mapping's encoding shape has no register owner at three places, the byte order of multi-byte scalars, the width ladder every length, count and discriminant is drawn from, and what a descriptor variant shorter than its declared slot leaves in it, the no-slack rule requiring one admissible form and deciding which at none of them
· Raised: M6.0b
· Disposition: open, each taken as a declared parameter with its ground and its refutation rather than inside a sentence of the mapping

**F-216u** method: an encoding table is not reachable from a mapping's obligations unless something states where each declared value rides, a mapping stated wholly over its descriptor leaving the aggregate and variable-length rows encoding nothing any obligation places while the table still reads as complete
· Raised: M6.0b
· Disposition: closed by the joining rule the profile now carries, an operation's declared values riding either as a descriptor member or as a delegated buffer payload

**F-216v** measurement: the rule holding the plan's findings against this register read count words only to twenty, where the tool's own figure convention spells them to ninety-nine, so a note declaring more than twenty matched no block and read as recording none
· Raised: M6.0b
· Disposition: closed, the table now built from that figure convention rather than kept beside it, so the reading stops where the convention stops

**F-216w** method: the convention for an identifier inserted between two others and the permanence of identifiers collide once an out-of-order block has landed, and permanence is the one that holds, so the repair belongs at the next insertion rather than at the landed one
· Raised: M6.0b
· Disposition: standing, the section carrying the order and the number carrying only the name, stated in place so a reader is not left looking for the missing run

**F-217** owed-act: the entry fixing a ring's composition-time constants names an index width and no entry says what it counts, so the mapping that must hold a capacity against it has no unit to read
· Raised: M6.4
· Disposition: open, the declaration counting bytes because every other width in the wire-format mapping is a byte width

**F-217a** owed-act: the ring-constant list is not the set a ring declaration must fix, this declaration fixing fourteen where that entry names six; four of the other eight are named by some other entry and by none as ring constants, the maximum simultaneously accepted requests and the completion capacity, the maximum segment count, and the slot budget the joint proof is taken against, and the remaining four are named by no entry at all, a segment's maximum size, the index span, the completion slot's size, and its declared fill
· Raised: M6.4
· Disposition: open, the declaration fixing all fourteen and the register naming six

**F-217b** owed-act: nothing joins the six-state request lifecycle to the cancellation entry's deterministic answers, that entry deciding by where a target stands against its declared points and never saying which states are live to cancel
· Raised: M6.4
· Disposition: open, the mapping of the four situations onto the six states taken in the profile rather than read from the register

**F-217c** owed-act: no entry says which members of the closed common status set are refusals, where the descriptor entry's criterion has a malformed descriptor produce one of *the defined refusal completions* that set names and the set is stated as one vocabulary with no subset marked
· Raised: M6.4
· Disposition: open, a checker reading a refusal having nothing enumerated to read

**F-217d** owed-act: the per-variant accounting entry names the five quantities its joint bound is over and no relation among them, so the admission arithmetic a generated artifact decides is the profile's and the register audits none of it
· Raised: M6.4
· Disposition: open, the artifact stating each obligation as an equality against a declared margin so that a weakening moves a figure rather than consuming slack

**F-217e** measurement: the guest lane refused every launch with `Wsl/Service/E_UNEXPECTED` for the length of one item, recovering only in brief windows, so a seeded population that fits one command had to be taken as a sample across the failure
· Raised: M6.4
· Disposition: standing, the failure being the machine's rather than the tree's and the proof gate's figures taken before it on the bytes the generator's own check holds the artifact to

**F-217f** measurement: a campaign of inequalities over a table of composition constants does not constrain it, an incremented constant that still satisfies its bound being absorbed as slack; a composition that declares its margin so that every bound becomes an equality is what turns each into a figure a weakening moves
· Raised: M6.4
· Disposition: standing, taken from a first sample that survived fifteen of twenty-four and a later one that survives four of thirty-two over the artifact as it now stands, the remaining survivors being the flow-label gap, the receiver-validation gap, the unbounded count of a cancellable operation's declared cancellation points, and a derived count a checker rule reaches where a prover cannot

**F-218** measurement: a generated artifact shipped a width rung its own profile's declared-parameter table says that profile does not have, under a comment attributing the ladder to the requirement whose ceiling forbids it, and that requirement fixes no width for the kind of field the rung was reached for at all
· Raised: M6.4
· Disposition: closed, the flag set's width moved to the declaration the wire-format row already calls its owner, the second ladder deleted, and the artifact left with the one ladder the requirement states

**F-218a** method: a figure computed as the difference of two ordinal positions in a list is true of the order it was written against and stays true of every reordering of that order, so a docstring claiming it reads the order is unfalsifiable by construction and the reach a requirement claims for it is narrower than stated
· Raised: M6.4
· Disposition: closed, the two ends read by name out of the two entry sentences that name them and the distance measured between those, so a state inserted between them moves the artifact

**F-218b** owed-act: nothing holds the emitter's own statement of the wire encoding against the section that states it, the rule over the generated artifact holding it against the emitter and the declaration rather than against the mapping, so a row edited in the profile moves neither and the drift is silent in both directions
· Raised: M6.4
· Disposition: open, stated as an absence in the profile's own holders section rather than repaired by a rule, the binding being the tools' act and not this document's

**F-218c** measurement: an exit line quoted a seeded population measured against a working copy that is not the artifact that landed, and no rule reads a population figure, so the sample fraction it reports was wrong by a fifth with every gate green
· Raised: M6.4
· Disposition: closed, re-measured against the tracked artifact at the repair and the fraction restated with it

**F-218d** method: a rule claiming to be fail-closed in three places was fail-closed in two, its third arm catching only the generator's own refusal, so an owner shaped in a way no guard names ended the whole checker run instead of reddening one rule
· Raised: M6.4
· Disposition: closed, every key the emitter reads named where the reading is refused and the rule catching what no guard reaches beside the refusal it already caught

**F-218e** owed-act: where an operation's declared values that the descriptor entry's enumeration does not admit ride is undecided, that entry enumerating what a descriptor carries and saying nothing about a value outside the enumeration or about how a delegated buffer's payload is encoded
· Raised: M6.4
· Disposition: open, the enumeration read as a placement rather than as a deletion and the reading collected as a declared parameter, the deletion reading refusing most operations outright

**F-218f** owed-act: two entries disagree about whether a descriptor carries a session generation, one enumerating exactly six members with no generation among them and the other binding every descriptor to a generation and refusing every old-generation one, which a server cannot decide without reading the descriptor's own
· Raised: M6.4
· Disposition: open, the generated record carrying the field where the enumeration entry has no row for it and the encoded size not spending it, so the field is inert until one of the two entries moves

**F-186g** owed-act: the extent of the authority a restart re-grants is stated three ways and they are not one statement, one entry fixing it at exactly the manifest's edges, another re-deriving at the manifest and the current revocation epoch, a third making user retraction a trigger beside restart, and a fourth carrying no epoch at all
· Raised: M6.1a
· Disposition: open, the difference observable on a retired edge and machine-checked at the item: the construction that faithfully rebuilds the manifest mints nothing and resurrects what a revocation retired

**F-186h** owed-act: a supervised unit has no lifecycle, the monotone lifecycle one entry states being a pool member's and the status set another states being a request's, so nothing gives a declarative unit states
· Raised: M6.1a
· Disposition: open, the item inventing none and stating its obligations over an arbitrary reaction instead

**F-186i** owed-act: what *no residue crosses the restart* quantifies over is unclear, the clause being attributed whole to a memory-allocation property that decides nothing about a grant slot while the authority half belongs to two other entries
· Raised: M6.1a
· Disposition: open, one mechanism credited with both halves

**F-186j** owed-act: the minimal recovery state is named and never stated, no entry saying what it holds or which roster it brings up, where one entry names it, a second makes boot counting a root-of-trust duty and a third sequences the ROM
· Raised: M6.1a
· Disposition: open

**F-186k** owed-act: the backoff index's scope is three different counters, one entry declaring a backoff per detector and action pair, another stating restart-with-backoff of the tree, and a third making a complete supervised subtree one victim
· Raised: M6.1a
· Disposition: open, per unit, per subtree and per window not being the same count

**F-186l** owed-act: two ladders carry one name, a default order over nine actions and a per-class permitted ordered ladder being different lists with no entry saying which one a class ladder is
· Raised: M6.1a
· Disposition: open

**F-186m** owed-act: a hysteresis band may be zero-width, both thresholds being required to be declared and nothing being said about the width between them, so a pair whose clear threshold equals its assertion threshold re-asserts the moment it clears
· Raised: M6.1a
· Disposition: open, the item taking the weaker reading because that is what the words carry; the oscillation admitted is the one the same entry's criterion is about

**F-166** owed-act: whether a statically composed image re-admits on device or measured boot covers it is unruled, and the split of the admission-checker milestone rests on it
· Raised: M6.2, in prose
· Disposition: closed, taken at M6.2: measured boot covers a statically composed image, on R-13-001c's own statement of the composer and of the device's act

**F-190a** owed-act: two enumerations the admission path depends on, the judgment forms and the checker phases, are closed in a pinned language document and nowhere in the register, so an eighth form or a seventh phase is not a register edit and the review gate never reads it
· Raised: M6.2a
· Disposition: open, the counts taken from the pinned document and cited there rather than restated as the register's

**F-190b** owed-act: the two lowest tiers state their evidence in a vocabulary the type-level obligation rows do not carry, functional refinement, non-interference, handler termination and information-flow theorems being placed outside every type system by the entry that names them
· Raised: M6.2a
· Disposition: open, the type-checker given the memory and ABI half one entry hands it and no more, and the per-tier required sets past Tier 2's left as fields

**F-190c** owed-act: no entry pairs a judgment form with the obligation facet it discharges, one block fixing the forms and another fixing the obligations with nothing joining them
· Raised: M6.2a
· Disposition: open, so the checker requires a form to be recognised and requires nothing about which one it is, and that freeness is machine-checked rather than assumed

**F-190d** owed-act: a tier-local admission check sits outside every enumeration, the Tier-2 certificate carrying a manifest-consistency check its own entry calls not one of the eleven
· Raised: M6.2a
· Disposition: open, a required check no list carries

**F-190e** owed-act: no entry says whether a roster may name one identifier twice, content addressing and deduplication both suggesting an identifier is a key and neither making a roster with two packages at one identifier malformed
· Raised: M6.2a
· Disposition: open

**F-190f** owed-act: which side of the admissible-versus-current line the composition-time act stands on is undecided, one entry making proofs generation-scoped and another separating the two without saying which versions composition compares against, with the pinned document adding a decoder version to a verdict's key that no entry names
· Raised: M6.2a
· Disposition: open, all four declared versions carried and compared componentwise so the choice is a reading rather than a mechanism

**F-190g** owed-act: two facet partitions of one obligation-row set are in force, the register's move table and the pinned document splitting it to different widths, and neither says which partition a derivation's discharge records name
· Raised: M6.2a
· Disposition: open, the three extra splits measured to take their rows' moves so no verdict turns on the choice, which is what makes the ambiguity survivable rather than absent

**F-190h** owed-act: no entry assigns a component to a tier, the three tiers being defined and every roster choosing its own
· Raised: M6.2a
· Disposition: open, so a composed generation's tier assignment is a composition magnitude rather than a reading

**F-191** measurement: a field no admission rule reads is a field a weakening moves in silence, which is the hazard the no-privileged-producer clause creates and which forty-six of one item's fifty-five seeded survivors were
· Raised: M6.2a, in prose
· Disposition: closed at the item by pinning every witness's pedigree and identity figures in a ledger rather than by narrowing the population; the hazard is the shape any artifact carrying unread fields will meet

**F-219a** owed-act: no entry closes a media template's stage set, the entry that names templates and pools naming no stage and the only list of four sitting in a parenthetical of the prose, which is not an enumeration the review gate audits
· Raised: M6.3a
· Disposition: open, the stage count and the stage kinds left as fields the composition instantiates

**F-219b** owed-act: no entry says whether a graph may carry two edges matching one intent, deterministic typed routing holding of a selector over an ambiguous graph and of one over an unambiguous graph alike
· Raised: M6.3a
· Disposition: open, both disciplines exhibited and each proved to keep every obligation the other keeps, with the difference machine-checked on a graph carrying two edges that match one intent

**F-219c** owed-act: no entry enumerates the intent variants the entry calling an intent a closed variant leaves closed, that entry excluding an executable name or command string and closing no variant set anywhere
· Raised: M6.3a
· Disposition: open, the intent count left a field and an intent a finite index below it

**F-219d** owed-act: whether the handler graph may carry a node for the shared service compartment is unstated, that compartment being one the duplication pass emits into the composed image and no package the composer's roster names, with no entry saying whether an edge may name it as an endpoint
· Raised: M6.3a
· Disposition: open, the closure obligation refusing one because the entry that fixes the graph gives the composer no node set but the installed packages whose descriptors it compiled, where the prose at that entry's anchor gives the wider set that would admit it

**F-219e** measurement: whether the hand-transcribed parser exception reaches a graph node's content format is decided rather than open, the entry that puts every format a translator or media node parses under the verified-parser discipline carrying no exception clause and the entry that permits one naming a single cellular grammar that is none of the five families the graph admits
· Raised: M6.3a
· Disposition: standing, nothing owed and the obligation stated unconditionally at the admissibility conjunct, with the same entry's five named families closed as an enumeration and no class of them exempt; the lesson beside it is that a gap is a gap only once every entry that could decide it has been read

**F-219f** owed-act: at what granularity the handler graph is re-signed is unstated, one entry rebuilding and re-signing it with the generation and calling it a configuration object carried by the generation root without fixing whether that is one signature or a second one over the graph
· Raised: M6.3a
· Disposition: open, the difference observable on the retained generation roots when a prior one is pinned, and the graph's identity left a field

**F-219g** owed-act: whether binding a composition-time template consumes a schedule slot the composition reserved is unstated, the four quantities being admitted under the scheduling section before a node may be bound while the two standing reservations name neither a node pool nor a template
· Raised: M6.3a
· Disposition: open, the four-quantity obligation stated without deciding it

**F-219h** owed-act: whether an edge's declared resource limit is compared against the caller's requested bound at selection or at binding is unstated, one entry declaring the transformation's limits and the prose making routing a selection under the caller's bound with neither putting the comparison on a side
· Raised: M6.3a
· Disposition: open, the item comparing at selection and recording that as a reading

**F-219i** owed-act: whether a typed signed configuration object carries one of the three assurance tiers is unstated, every admitted artifact carrying exactly one tier and its required evidence while a configuration object is data rather than code
· Raised: M6.3a
· Disposition: open, the item assigning none; adjacent to F-190h and not a second sighting of it, that one being which tier a component carries where this is whether a non-code artifact carries one at all

**F-219j** owed-act: every composition magnitude of the composer's emitted object is a field no entry fixes, the roster and each package's declared edges, script, manifest width, origin, admission time, admitted quantities and label among them, and so are the type, intent and world counts, the wire-format inventory, both pool capacities, the ring depth ceiling, the template's stages and end types, the declared inter-level channels, the ambiguity discipline and the graph's identity
· Raised: M6.3a
· Disposition: open, the demo instantiating each with a witness value that carries no composition claim and the pedigree ledger pinning every one; the same shape as F-195i at the two upper layers and not a second sighting of it, that one being over a keyspace and a snapshot where this is over a graph, a template and two pools

**F-219k** method: a witness built by a field setter carries one figure where a witness written out carries ten, and a seeded Gallina population is counted in figures, so the ledger a prior item's survivors require and the population that ledger creates are the same figures
· Raised: M6.3a
· Disposition: standing, the item's note carrying the arithmetic and the population figure it is derived from

**F-219l** method: a refuting construction's own comparisons need a witness on their boundary as much as the specification's do, and it is the specification's that get one by habit, so a refuter is refuted at a value far from its own cut and a weakening that moves that cut answers the same everywhere the artifact looks
· Raised: M6.3a, in prose
· Disposition: closed at the item by adding the request whose bound sits exactly on the edge the refuter reaches, the survivor that exposed it being one of the relational and connective operators' and real

**F-219m** method: a scope a completion cell cites no id for is derived, and the derivation is the one sentence a reviewer can check, so it separates the ids the entries it starts from actually spell out, the entries that cite one of those back by name, and the ones a judgment reaches by a noun an entry uses and does not define
· Raised: M6.3a
· Disposition: standing, the artifact's header stating the three steps apart and naming which is a reading and which a judgment

**F-219n** method: an entry's sentence is read for the clause it leads with as well as for the prohibitions after its colon, a grading or qualifying clause being an obligation the list after the colon does not repeat and a count taken off that list alone therefore being short by one
· Raised: M6.3a
· Disposition: open, the qualifying clause of the pool-verdict entry deferred by name to the artifacts its own acceptance clause puts it in rather than stated at the composer

**F-219o** method: an alternative construction refutes one obligation only once every obligation it does not break is stated of it, and a comment saying it keeps them is not the statement, a refuter shown only to be well formed leaving the reader unable to tell which of several defects the refutation isolated
· Raised: M6.3a
· Disposition: closed at the item by stating each composer refuter's other two obligations as theorems over an arbitrary machine, which is the discipline every other refuting family in the artifact already met

**F-219p** method: a seeded-population figure is read by no checker rule and is stated twice in a completion note, at its findings block and at its exit evidence, so a figure taken before the last statement landed survives an edit with every gate green and the two halves of one note disagreeing
· Raised: M6.3a
· Disposition: open, held only by re-measuring at the gate rather than carrying a figure forward, which the exit-evidence convention states and no `Landed:` line enforces

**F-167** owed-act: the typed interface profile the ring contract is stated in is carried by no path in the tree and authored by no milestone here
· Raised: M6.4, in prose
· Disposition: closed, taken at M6.0b, which gives the typed IDL profile an item of its own rather than leaving M6.4 to author the type layer it is stated over

## RTL track

**F-168** measurement: the capability width identity collapses onto the register width across the imported core, one declaration the delta books across twenty-five files
· Raised: R1, in prose
· Disposition: open, taken at R1b, and it takes a store rotate into an upper half that no longer exists with it

**F-169** measurement: the bounds encoding is not a narrowing of the imported one, the frozen format having no internal-exponent flag and stealing no mantissa bits
· Raised: R1, in prose
· Disposition: closed at R1a, the whole algebra authored against the model rather than edited, five required behaviours having no imported counterpart at all

**F-169a** measurement: the curated configuration's first elaboration is not warning-free and never was, the figure the item first recorded having measured the absence of output, because the elaboration loop prints the elaborator's output only on a non-zero exit that `-Wno-fatal` keeps warnings out of
· Raised: R1, in prose
· Disposition: open, the note carrying both arms' warning counts beside the zero-error figure and the loop still printing nothing on a clean exit, so what is owed is a tools act that reports the count the note took by hand

**F-170** owed-act: whether curating the pinned tag controller is the act R-15-092 forbids is a question this plan answers nowhere, the interconnect being a net-new block that requirement wants authored and proven
· Raised: R1, in prose
· Disposition: closed, taken at R1: the fabric is curated as a functional reference now and authored under route (a) afterwards, on section 11's own sentence about that route

**F-171** owed-act: the bounds-setting containment property holds over a domain nothing states, measured here from the RTL side and agreed by both implementations
· Raised: R1a
· Disposition: closed, together with F-144 at R-15-007a; three implementations agreeing line for line is what made it the algebra's rather than any one of theirs
· Restates: F-144

**F-172** owed-act: the same domain falsifies a sentence the model states about itself, the internal exponent leaving its stated range and the encoder truncating it into the other case
· Raised: R1a
· Disposition: closed, together with F-144: the header sentence describes the stated domain, and the domain is now stated where the proof obligation is

**F-173** method: a vector population off entropy alone cannot tell one clause from its absence, the branch that decides firing only where both operands are aligned to a large power of two
· Raised: R1a
· Disposition: closed, a directed sweep reaching it and turning a surviving mutant into one killed on a few dozen lines; the generality is S13's

**F-174** measurement: the provenance record owes no row for authored logic, a binding being a list of settings or a stated ground and both readings being about a structure the build does not contain
· Raised: R1a
· Disposition: standing, a row here being the claim the record exists to refuse

**F-175** measurement: a hand-maintained count in the provenance record was wrong as written, counting over the rows above it rather than over the items its own section lists
· Raised: R1a
· Disposition: closed, repaired with the reading stated; holding it by rule would need a marker on each row naming its ground, a document change and a decision

**F-176** measurement: the checker stated a width of its own, in the module whose preamble says it states none
· Raised: R1a
· Disposition: closed, the ceiling now read out of the model through the same parse, and the rule gained a fifth site in the same act

**F-177** owed-act: the platform devices have no definition in this repository to be authored against, there being no interconnect top, no bus and no address map, and the shipped composition declaring no serial port at all
· Raised: R1c, in prose
· Disposition: closed, taken at R1c: the address map is a composition act under R-15-002b and the peripherals are route-(c) references, the top following the map

**F-177a** owed-act: the root of trust's RTL route is unassigned, one entry's acceptance naming three imported cores and another's authored list naming three blocks with the root of trust on neither, while a third puts it in the trusted base and calls it verified
· Raised: R1c, in prose
· Disposition: open, a register act naming its route; the plan had been reading it onto the imported side by default, and R1c re-homes it to the authored one on the proof argument rather than on the uniformity one

**F-214** measurement: the fourth of the four windows this item names already exists four times over, the root of trust's peripherals having been declared in every shipped composition one milestone earlier and no artifact naming a fifth
· Raised: R1c-i
· Disposition: closed, declined with the measurement stated; three windows are declared and the fourth's premise is gone

**F-215** owed-act: no register entry requires a serial port, a block device, or an SoC boot ROM to exist, so what obliges the three devices is the plan's own list while the entry this item rides obliges only that their placement be stated
· Raised: R1c-i
· Disposition: open, a register act if the three are to be obligations rather than plan items; the placement discipline is enough to write the map and is not enough to say what a door does

**F-199** measurement: two apertures every composition declares had no node in the attested devicetree at all, inside the emitter whose own comment says each node below it carries its window under the placement entry
· Raised: R1c-i
· Disposition: closed, both nodes emitted and the pairing now held by rule in both directions

**F-200** measurement: the model called the revocation interval map and its register window attested-devicetree constants and neither had ever been in that tree
· Raised: R1c-i
· Disposition: closed, the node carries the window and both interval figures, so the sentence and the artifact agree

**F-201** measurement: nothing held two declared apertures apart, the validator reading each window against the regions one at a time so that two windows at one base both passed
· Raised: R1c-i
· Disposition: closed, a whole-map check over every aperture the composition declares, its list written out one row per window with each row reading that aperture's own key and base, and K-94 holding the list against what the shipped configurations declare

**F-202** measurement: the boot ROM had no extent anywhere in the tree while the attested devicetree's address was the ROM region's own base, so an image and the tree began at the same byte and nothing refused it
· Raised: R1c-i
· Disposition: closed, the extent declared and the two held apart at composition and again when the blob is written

**F-203** method: a composition-time bound and a write-time bound over one region are different facts, and only the second knows a size
· Raised: R1c-i
· Disposition: standing, the pairing written in both places rather than in whichever one was reached first
· Restates: F-057

**F-204** owed-act: three subcommands the command table declares answerable on either lane are refused on the host, the module loading the build environment before it dispatches
· Raised: R1c-i
· Disposition: open, a tools act at the module's entry point; the three shipped key sets and the three validations this item reports were taken from inside the guest instead

**F-205** measurement: the plan's own cell for this work stated a composition four apertures out of date, a milestone having added the root of trust's windows after the cell was written
· Raised: R1c-i
· Disposition: closed, the parent bullet repaired against the composition it names

**F-206** measurement: five artifacts said an access inside one of the three new windows is silence, and the enclosing region's PMA decides an access before the RAM fall-through, so inside the boot ROM's region a store and an instruction fetch are access faults
· Raised: R1c-i
· Disposition: closed, every site repaired against the regions the composition declares, the forfeit the arm not taken is priced against being a load and not every access

**F-207** owed-act: the boot ROM's extent is declared inside a region that is not executable, which refuses the one access an SoC boot ROM exists for
· Raised: R1c-i
· Disposition: open, a composition act at the region's attributes, taken with the top that fetches from the ROM; the attested devicetree shares the region, so turning it on makes the tree's own bytes executable

**F-208** measurement: a finding stated what a search of the register returns for the boot ROM and stated a smaller set than it returns, a third entry's acceptance naming the same metal-mask ROM
· Raised: R1c-i
· Disposition: closed, the sentence restated as the search's own result; the conclusion is unmoved, no entry obliging an SoC boot ROM

**F-209** measurement: the repair for F-205 replaced a stale enumeration with a hand-maintained aperture count nothing computes, which is the defect F-205 names
· Raised: R1c-i
· Disposition: closed, the count deleted rather than owned and the bullet restated as an additive claim about the artifact, with the same shape at an earlier landed cell's ROM size repaired beside it
· Restates: F-205

**F-210** measurement: the validator's whole-map list is written out one row per window and two artifacts said it was built from the composition, so a window the composition gains was held to join a check nothing made it join
· Raised: R1c-i
· Disposition: closed, both prose sites restated to the code's own reading and K-94 given a third hop holding that list against what the shipped configurations declare

**F-211** owed-act: no register entry requires two MMIO apertures to be disjoint, the placement entry constraining the space and the attested tree and saying nothing about two windows sharing a byte, while the validator's refusal borrowed that entry's word to carry the claim
· Raised: R1c-i
· Disposition: open, a register act; the refusal now states the ground it has, that two devices cannot answer at one address and an attested tree naming one address twice describes a die that does not exist

**F-212** measurement: a composition comment narrated the revision that produced it where the region's own opening comment already states the present state
· Raised: R1c-i
· Disposition: closed, the durable half kept and the narration deleted in all three shipped compositions

**F-213** method: the exit-evidence sweep's model revision is a stamp taken once at cmake configure and carried in the emulator, so its dirty marker names the tree that generated the reference rather than the tree the sweep prints from
· Raised: R1c-i
· Disposition: standing, the marker read as the configure-time state it is; the lane's `.git` pointer is translated for the guest so the stamp resolves at all, and a completion note quoting a revision says which build it came from

## Build-loop instruments

**F-178** measurement: the shared memo cache one instrument proposed already existed for the typecheck loop, one file every checkout wrote, live across four concurrent lanes
· Raised: I2
· Disposition: closed by I7, which derives one cache per lane

**F-179** measurement: the shared compiler cache does not reach across build trees, the command line being hashed with the source so two lanes share no entry
· Raised: I4
· Disposition: standing, the setting that would make lanes share deliberately not pulled, the object carrying the first lane's directory in its debug information

**F-180** method: an undeclared per-agent workaround reaches neither the log nor the shared cache, where a derivation reaches all three
· Raised: I7
· Disposition: closed, the lane derived from the checkout rather than declared, so it is unique by construction

**F-180a** method: splitting shared state per lane closes the sharing and leaves owed the copy that makes a new lane warm, and a seeder warms only the paths that call it, two of which called none
· Raised: I7
· Disposition: closed, every command that can stand a tree up seeding it before it configures one, and both memo caches seeding through one function whose donor is allowed to be its own target

**F-181** upstream-defect: this tree carries workflow files and their being inert is what keeps them green, two of their own lines naming a target and an option the curation has since removed
· Raised: I8
· Disposition: standing, making one live being the permanent vendored divergence I4 and I8 both refuse; S14 was to be the disposition and declined on a measurement, so this repository carries no workflow of its own either

**F-182** measurement: the mutation sandbox's index carried no gitlink at all, standing each submodule up as a directory holding a stand-in
· Raised: I11
· Disposition: closed, the template putting the repository's own gitlinks back into its index on every build

**F-183** measurement: one entry point read the process's own arguments rather than a list handed to it, so it typechecked green under a cast and would have raised the moment a dispatcher called it
· Raised: I12
· Disposition: closed, that command taking argv like every other and keeping the marker it writes around the dispatch rather than inside the shared helper

**F-184** method: a mutation case anchored on a construct a refactor deletes reports itself unseeded rather than passing, and a case written to match loosely would have seeded something else and killed a mutant about nothing
· Raised: I12
· Disposition: closed, the case re-seeded at the one site of that construct the move leaves standing

**F-185** measurement: the documents cite tool paths 180 times and the register names only one of those paths, in six places, so exactly one tool path is a claim a review gate audits and the rest are pointers
· Raised: I12
· Disposition: standing, and it is what decided which entry point keeps its path across the move

**F-186** measurement: a census over the tracked Python finds no public function named outside its own module and no module outside the test package that nothing imports, so the tool surface is the number of cross-artifact facts somebody decided to hold rather than unused code
· Raised: I12
· Disposition: standing, which is what puts the lever on S15's generation rather than on a search for dead code
