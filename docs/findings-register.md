# Findings Register

*An index of what the build has found, and not a second copy of it. The completion notes and cells of [the implementation checklist](implementation-checklist.md) own every finding's content; this register owns its id, its type, the item that raised it, and its disposition, and owns nothing else.*

## How to read this

A finding is something the build learned that the plan would otherwise learn again. The plan records 200 of them across 48 items and nothing read them, which costs three ways: the same fact found twice at two items, an owed act with nowhere to live until somebody assembles S1's rows out of prose by hand, and a methodological finding that never becomes a rule. This register is what reads them.

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
· Disposition: open, named as K-85 in the differential group with its three edits and a floors-group member count, and left rather than added

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

**F-129** upstream-defect: the container recipe exists for the prover rather than for privilege, and no container runtime is installed on either lane
· Raised: M1.5, in prose
· Disposition: standing, the distribution carrying the compiler and running as root, so neither privilege nor toolchain argues for one

**F-130** upstream-defect: the guest idles out between commands and takes its containers with it, and the switch that disables it is global and permanent on the human's box
· Raised: M1.5, in prose
· Disposition: closed, the fix scoped into the repository as a detached, idempotent, self-expiring keepalive every model loop starts; S9 retires the class

**F-131** upstream-defect: an intercepting proxy re-signs the release-asset host, so the exported root CA must be installed into any guest trust store that fetches one
· Raised: M1.5, in prose
· Disposition: standing, a setting on the human's box that no benchmark reaches; S9 retires the class

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

**F-165** owed-act: the emulator runs one hart and every shipped configuration composes one, so the multikernel's defining property is first exercisable on the RTL track
· Raised: M4.4, in prose
· Disposition: closed, taken at M4.4: single-instance bring-up, the multikernel's defining property being first exercisable on the RTL track where a second implementation stands

## M6 · Userland spine

**F-166** owed-act: whether a statically composed image re-admits on device or measured boot covers it is unruled, and the split of the admission-checker milestone rests on it
· Raised: M6.2, in prose
· Disposition: closed, taken at M6.2: measured boot covers a statically composed image, on R-13-001c's own statement of the composer and of the device's act

**F-167** owed-act: the typed interface profile the ring contract is stated in is carried by no path in the tree and authored by no milestone here
· Raised: M6.4, in prose
· Disposition: closed, taken at M6.0b, which gives the typed IDL profile an item of its own rather than leaving M6.4 to author the type layer it is stated over

## RTL track

**F-168** measurement: the capability width identity collapses onto the register width across the imported core, one declaration that twenty-five files name
· Raised: R1, in prose
· Disposition: open, taken at R1b, and it takes a store rotate into an upper half that no longer exists with it

**F-169** measurement: the bounds encoding is not a narrowing of the imported one, the frozen format having no internal-exponent flag and stealing no mantissa bits
· Raised: R1, in prose
· Disposition: closed at R1a, the whole algebra authored against the model rather than edited, five required behaviours having no imported counterpart at all

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
· Disposition: closed, taken at R1c: the address map is a register act under R-15-002b and the peripherals are route-(c) references, the top following the map

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

**F-181** upstream-defect: this tree carries workflow files and their being inert is what keeps them green, two of their own lines naming a target and an option the curation has since removed
· Raised: I8
· Disposition: standing, making one live being the permanent vendored divergence I4 and I8 both refuse; S14 is the disposition

**F-182** measurement: the mutation sandbox's index carried no gitlink at all, standing each submodule up as a directory holding a stand-in
· Raised: I11
· Disposition: closed, the template putting the repository's own gitlinks back into its index on every build