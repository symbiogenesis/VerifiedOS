# Roster and boot-recipe contract

This contract fixes M7.1's executable roster, each member's entry and handoff, the
image recipe the composition follows, the boot record that binds it, and how the
console and event digests are defined and computed. The
[checklist](../implementation-checklist.md) owns M7.1's acceptance; this document owns
the rules [the boot harness](../../../tools/vos/boot.py) applies, and the harness reads
the roster from the table in section 2 rather than from a copy of it. `python tools/run.py
boot` is the command.

The harness composes, boots and digests whatever the recipe names. It establishes that
an image was composed from the bound inputs and that a run of it on the golden emulator
produced the stated digests. It does not establish that a member is the real producer:
a fixture is not, and a compiled Gallina statement is not an executable member. The image
composition here is placement and linking of assembled units; it is not M6.3a's package
composer, which remains a roster member of its own. The RoT's measurement and release of
the main die is M3.5's harness, not this one.

## 1. Order and scope

The chain is RoT, then verified M-mode firmware, then the per-core kernels, then the static
image (R-09-002). M4.4's ruling in the checklist makes M8a single-instance bring-up on the
emulator's one hart, so this roster carries one `kernel`. The ROM's one sequence places the
verified M-mode image and releases the boot core into the measured chain (R-09-006). The
kernel's first partition is the supervision tree, which brings up the remaining members in
its manifest's start order, as the plan's init-system section states. The roster below
follows that order: `rot` runs on the RoT's own composition, and the `image` members are
ranked in the order they are first entered on the main die.

The M8a roster is narrower than the component list [AdmissionPath.v](../../../proofs/AdmissionPath.v)
names as `golden_roster`. That list carries the object system and its update transactor,
which M5.4 defers past the M8a gate; the boot path keeps only its runtime read-verify half,
which is M5.3's system-integrity instance (R-10-001). It does not carry the copy-based
service, which M6.5 puts on the boot path. Its `crypto_core` is a package of its own, and
this roster keeps it as an image member (section 2). Executable admission is taken over
this roster.

The plan's init-system section has the supervisor read its configuration generation from
the object system, which M5.4 defers past the M8a gate. The supervisor's
[static typed C manifest](../../../supervisor/src/manifest.c) supplies its proposed M8a
source. Binding that manifest to the admitted image and target handoff remains open.

## 2. The roster

| Member | Kind | Rank | Status | Executable owner | Reference | Entry and handoff |
| --- | --- | --- | --- | --- | --- | --- |
| `rot-firmware` | `rot` | n/a | `statement-only` | M3.5 for the firmware; M7.1f for the boot verifier's executable crypto | [RotFirmware.v](../../../proofs/RotFirmware.v), [RomVerifier.v](../../../proofs/RomVerifier.v), [Keccak.v](../../../proofs/Keccak.v) | RoT reset on [the RoT composition](../../../model/config/verifiedos-rot.json); its ROM stage verifies `mmode-firmware` with SLH-DSA over SHAKE256 as the RoT's own integer code (R-09-005a, R-15-059), measures it and releases the main die through M3.5's harness |
| `mmode-firmware` | `image` | 1 | `statement-only` | M3.5 | [MModeFirmware.v](../../../proofs/MModeFirmware.v) | the image entry, reached with the reset root pair; enters `kernel` through [the selected scalar handoff](purecap-abi.md#7-the-kernel-entry-interface) |
| `kernel` | `image` | 2 | `statement-only` | M4.4 | [KernelInstance.v](../../../proofs/KernelInstance.v), [PartitionContext.v](../../../proofs/PartitionContext.v), [CyclicExecutive.v](../../../proofs/CyclicExecutive.v) | entered from `mmode-firmware` by the handoff's no-link sentry jump; dispatches `supervisor` as its first partition by `mret` |
| `supervisor` | `image` | 3 | `partial` | M7.1 | [SupervisionTree.v](../../../proofs/SupervisionTree.v) | the kernel's first partition; starts `crypto-core`, `storage` and `copy-service` in its manifest's start order |
| `crypto-core` | `image` | 4 | `statement-only` | M5.3d for the seal/open and keyed-digest operations storage invokes | [Keccak.v](../../../proofs/Keccak.v), [Sha256.v](../../../proofs/Sha256.v), [AesGcm.v](../../../proofs/AesGcm.v), [MlDsa.v](../../../proofs/MlDsa.v) | started by `supervisor` before `storage`; holds the volume keys and serves storage's seal/open and keyed-digest calls through its entry, no key material crossing to the caller (R-10-022, R-10-012, R-10-023) |
| `storage` | `image` | 5 | `statement-only` | M5.3d | [ExecutableIndex.v](../../../proofs/ExecutableIndex.v), [JournalIndex.v](../../../proofs/JournalIndex.v), [StorageRecovery.v](../../../proofs/StorageRecovery.v) | started by `supervisor`; one index body at the system-integrity and user-data instantiations over the modeled block device, calling `crypto-core` for seal/open over ciphertext extents and tags |
| `copy-service` | `image` | 6 | `partial` | M7.1 | [CopyRingService.v](../../../proofs/CopyRingService.v), [RingContract.v](../../../proofs/RingContract.v) | started by `supervisor`; serves one ring of the reference world in [the ring declaration](../../../interfaces/ring-reference.json) |
| `composer` | `offline` | n/a | `partial` | M7.1 | [HandlerGraph.v](../../../proofs/HandlerGraph.v) | runs at composition over the roster; emits the typed handler graph the image carries |
| `admission` | `offline` | n/a | `partial` | M7.1 | [AdmissionPath.v](../../../proofs/AdmissionPath.v) | runs at composition over the composed roster; emits the admission record bound to the image digest |

**The columns are closed vocabularies**, and the harness refuses a row it cannot read
whole. *Kind* is `rot` for a member running on the RoT's own composition, `image` for a
member composed into the main-die image and entered, and `offline` for an act at
composition that emits a record rather than code. No kind exists for code linked into the
members that call it: a service its consumers call is one shared compartment rather than a
library linked into each (R-13-010b). *Rank* is the order of first entry and is carried by
`image` members only. *Status* is `executable` where an executable product exists that a
recipe can compose, `partial` where part of one exists, `statement-only` where the member
exists only as a Gallina statement, and `fixture` in a fixture roster alone. A `partial` or
`statement-only` member blocks acceptance, and a recipe that names one is refused with its
owner.

**No member has an accepted target product at this contract's revision.** The supervisor and
[copy-service](../../../copy-service/README.md) have bounded host C implementations,
and the offline composer and admission checker have
reference implementations; their remaining target, descriptor and derivation joins keep
those rows `partial`. The other rows remain `statement-only`. The tracked Fiat-Crypto
emissions are C field arithmetic that no target build compiles. The modeled block device
and the RoT peripherals are executable Sail devices, which the members use and which are
not roster members. A status moves to `executable` in the same edit that adds the
member's product to a recipe, on the owner's landed evidence.

**The crypto core is a compartment of the image, never code linked into its callers.**
R-10-022's acceptance has the filesystem compartment invoke seal/open over ciphertext
extents and tags and never hold raw key material; R-10-012 and R-12-014 keep keys resident
only in the crypto core; R-10-023 names the interface to it; and AdmissionPath.v admits
`crypto_core` as a package of its own. Linking it into `storage` would put the volume keys
in the storage compartment. At M8a it serves storage alone, and M5.3d, which owns storage's
executable crypto, owns its product; the sealing and attestation service of R-12-014 is not
on this roster. Whether a later composition gives it hardware of its own, which the
specification's prose beside R-15-013 names as a disjoint failure domain, is not decided
here.

**M7.1f owns the boot verifier's executable crypto.** The ROM stage verifies
with SLH-DSA over SHAKE256 as the RoT's own scalar integer code (R-09-005a, R-15-059), and
[RomVerifier.v](../../../proofs/RomVerifier.v) states what that verifier needs without
authoring a scheme. ML-DSA verifies the replaceable stages above the ROM (R-09-002). M3.5
identifies those calls and consumes them as a join rather than owning their
implementation. M7.1f owns the executable verifiers and their comparisons;
M3.5 retains their firmware binding and target-execution join.

**The executable owner of each statement-only userland member is M7.1**: M6.1a's
supervisor, M6.2a's composition-time admission, M6.3a's package composer and M6.5a's
copy-based service. M6.2b's on-device CIC checker is not a roster member: M7.1's own
acceptance keeps that deferred checker outside this roster, and R-06-014 makes the checkers
the admitters no admission certificate covers.

## 3. Entry and handoff

The emulator enters the image at its ELF entry with the reset state: PCC is the
execute-side root and `c1` the store-side root. In the composed system the ROM places the
verified M-mode image and releases the core; this harness loads the image directly and
does not model that placement, its measurement or its signature check.

**An image member's entry is `_start` at the first byte of its text**, and a member reaches
a neighbour only at that neighbour's entry, through a name the recipe resolves. That is the
address the event log reads (section 6). The real transfers are the owners' contracts and
none is realized by a fixture:

- `mmode-firmware` to `kernel` is [the selected scalar handoff](purecap-abi.md#7-the-kernel-entry-interface):
  the kernel's entry text capability by the no-link sentry jump, `csp`, the root-set table,
  the boot descriptor, the initialization descriptor, MTCC and MTDC, with every other
  register null. M3.5 owns the producer and its installation evidence.
- `kernel` to `supervisor` is the kernel's first partition dispatch by `mret`, over the
  contexts and schedule the initialization descriptor names ([the single-instance
  contract](service-authoring.md#2-single-kernel-instance)). M4.4 owns it.
- `supervisor` to the services is the start order the composition's manifest fixes, stated
  as a precedence over the manifest's edges in SupervisionTree.v. The ranks of
  `crypto-core`, `storage` and `copy-service` in section 2 are that start order for this
  roster, the crypto core first because storage calls it; a composition whose manifest
  starts them otherwise changes the ranks in the same edit.
- `storage` to `crypto-core` is a call through the crypto core's entry for seal/open and the
  keyed digest, over ciphertext extents and tags, with no key material crossing it
  (R-10-022, R-10-023). M5.3d owns both sides.

## 4. The image recipe

A version 1 recipe is a JSON object with exactly these fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `name` | the composition's name, which names its output directory |
| `roster` | the roster the recipe composes against: this contract, or a fixture roster in JSON whose every member is `fixture` |
| `configuration` | the emulator configuration, whose `MainMemory` regions bound every extent |
| `inst_limit` | the emulator's instruction limit for the run |
| `tohost` | the HTIF doubleword's address, which the recipe owns and places |
| `members` | one object per image member in rank order: `id`, `producer`, `source`, `text_base`, `data_base` and `imports`, a map from an imported name to the member whose entry it names |
| `admission` | `null`: schema 1 defines no admission record |
| `expected` | `null`, or the reference run's digests (section 6) |

Composition refuses, with the cause named:

- a member composed twice, a member the roster does not declare, a member whose kind is
  not `image`, a `partial` or `statement-only` member, a declared image member the recipe
  leaves out, and an order contradicting the ranks;
- a text or data extent outside every `MainMemory` region, text in a region the
  configuration does not make executable, data or the tohost doubleword in one it does not
  make writable, a misaligned tohost, and any two overlapping extents;
- an import from a member the recipe does not compose or from the member itself, an import
  of `tohost`, a unit defining a name it imports, and an entry that is not `_start` at the
  text base.

**The producer is `asm`, [the in-tree assembler](../../../tools/vos/asm.py) at the recipe's
placement.** A member built by the accepted backend enters as the assembly that backend
emits, which is the target loop's route through M1.4′'s assembler. Binding the compile
step's own identity in the record is a schema change and joins at M1.2f. The link map
lists member extents only; the image's symbol table carries every member's labels
qualified by its id, so a reading over a member's functions, such as M5.3's one index
body at two instantiations (R-10-003), has the image's own symbols to read.

**Admission joins as a schema change.** The executable admission package defines the record
it emits; the schema that binds it holds the record's image digest equal to the composed
image's. Until then every record carries `accepted: false`.

### Reference composition attachments (version 2)

Version 2 retains the version 1 fields and adds `composer`, an object with exactly
`source` (the package descriptor document) and `address` (a hexadecimal placement).
Its `admission` field names the offline reference checker's request document. Both
attachments are required together. This version exercises the executable composition
boundary; its discharge metadata does not supply real member derivations, so the boot
record still carries `accepted: false` and names the outstanding production admission.

The composer reads the descriptor document against the recipe's exact roster, emits
canonical typed graph bytes and places them in a read-only, non-executable `.handler_graph`
ELF section. The section must fit wholly inside a declared `MainMemory` region and overlap
neither a member extent nor the HTIF doubleword. Its digest, placement and composer
implementation hash enter the
composition digest and boot record. The reference admission checker consumes that graph
and the final image bytes; each image member's certified artifact must be that member's
recipe source, bound by both path and digest. A refused runtime member refuses the whole
composition.

Before a run, the harness rechecks the descriptor and request bindings, regenerates the
graph, and revalidates the admission record against the actual image and roster. A changed
image digest, substituted graph, stale reference input or altered decision is a refusal.
The acceptance checks include those substitutions, graph extent violations, a refused
member and a successful fixture composition. Fixture success establishes binding and
reference-decision behavior only. Real descriptors, checked derivations and the accepted
target roster remain M7.1's joins; neither offline program certifies itself.

## 5. The boot record and staleness

`boot compose` removes any previous record first, then writes the image, a link map of
member extents and entries, and `record.json` last. The record carries the recipe's
declaration digest, the SHA-256 of the roster, the configuration, every member's source
and the image, the canonical digest of the composition (configuration digest, tohost and
the placed members), the revision, and whether any input differs from that revision's
bytes. The inputs that comparison reads include the modules that produce the image's bytes,
[asm.py](../../../tools/vos/asm.py), [image.py](../../../tools/vos/image.py) and the harness
itself, because a locally modified producer composes a different image from the same
recipe. The record lists the joins that keep the composition unaccepted.

The declaration digest is taken over the recipe with its `expected` block removed, in
canonical JSON, because refreshing a measurement changes nothing the composition reads.

`boot run` reads the whole record first and refuses one lacking a field it reads. It then
re-reads every binding before anything runs. A source, recipe declaration, roster,
configuration or image whose bytes no longer match is refused as a stale input, by name.

## 6. The run, the event log and the digests

The emulator runs as `--config <configuration> --trace-commit --terminal-log <console>
--inst-limit <inst_limit> image.elf`, its standard output read as a stream.

**The console digest is the SHA-256 of the console log's bytes.** The trace carries the same
bytes as the low byte of every eight-byte HTIF write with device 1 and command 1; the two
channels must agree.

**The event log is one ASCII line per event, each ending in LF, and the event digest is the
SHA-256 of the log's bytes.** It is a projection of [the commit trace](../../assurance/differential-corpus.md#4-the-commit-trace-schema-version-1):

| Event | Taken from |
| --- | --- |
| `ENTER <member>` | an `I` record whose `pc` is a member's entry, except the zero-word record of a step that takes an interrupt |
| `TRAP` | every `T` record, without its cause |
| `HTIF <offset> <width> <value>` | every `W` record inside the tohost doubleword, with the value as the trace prints it and the tag omitted |
| `EXIT <code>` or `EXIT none` | always the last line: the payload shifted right by one of the last eight-byte tohost write with device 0 and payload bit 0 set |

Every field the log reads is one the RVFI packet also carries: the retired `pc`, a trap
taken, and a memory write's address, width and data. The cause is left out because the
packet carries a trap as a boolean ([where the two do not
meet](../../assurance/differential-corpus.md#93-where-they-do-not)). A four-byte write to
tohost is logged and not decoded; members write the doubleword whole.

**An RTL run computes the same log only under a stated trap convention.** The step that
takes an interrupt is traced as an `I` record with a zero word at the saved PC, followed by
its trap's records with `T 1` among them; nothing is issued there, so that record enters no
member. This model's RVFI emitter sets `rvfi_trap` for an interrupt as for an exception
([the RVFI callbacks](../../../model/c_emulator/riscv_callbacks_rvfi.cpp)) and no model path
sets `rvfi_intr`. The standard packet sets `rvfi_trap` for a synchronous trap only and
marks the first instruction of every trap handler with `rvfi_intr`
([rvfi_dii.sail](../../../model/model/core/rvfi_dii.sail)), so counting `rvfi_trap` drops
every interrupt. Under that convention `TRAP` is one event per packet carrying `rvfi_intr`,
logged before that packet's own `ENTER`, which gives this log wherever every trap enters a
handler that issues an instruction. R2's adapter owns which convention the RTL's port
follows and the reading that goes with it. The fixture takes no interrupt, so no run yet
shows the two logs equal across one, and R3's comparison is claimed for synchronous traps
until one does.

**The commit-trace fingerprint is the corpus's**: [trace.py](../../../tools/vos/trace.py)'s
digest over the normalized records, with the number of `I` records beside it as `retired`.
That count is one per traced step, including a step that traps and the step that takes an
interrupt, so it is not the architectural retire count. The fingerprint checks that the
golden emulator reproduces its own run; it is not a cross-executor comparison.

A run is refused for a timeout, an emulator process that exits nonzero or is killed by a
signal whatever its output said, a missing or nonzero HTIF exit, an emulator verdict line
disagreeing with the HTIF exit the trace carries, console channels that disagree, an image
member never entered, and first entries out of rank order.

**The expected digests are the golden emulator's over the accepted image.** The recipe's
`expected` block holds `image_sha256`, `console_sha256`, `event_sha256`, `events`,
`trace_digest` and `retired`. `boot run --refresh` writes it from a clean run only, and a
refresh is a reviewed act: the reference executor's output becomes the value the rerun and
R3 reproduce. The block names the image it was measured on, so a changed image is reported
as an expectation to refresh and not as a digest mismatch. It does not name the emulator,
so a changed emulator is reported as a mismatch.

**Boot duration is reported and not decided here.** Each run records its `I` record count
and wall time. M7.1 reads the composed boot's figures against
[S4's projected budget](../completion-log.md#s4-measure-sail-emulator-throughput-against-the-m2-gate),
which is the measurement that could reopen M2.

`run.json` carries the run's figures and `roster_identity`, whose `roster_revision`,
`image_sha256` and `composition_sha256` are the identity [the roster measurement
contract](roster-measurement.md#shared-capture-boundary) requires of a capture. The identity
is carried only where the record's revision is a full Git object ID and no input or
producing module differs from that revision's bytes. Otherwise `roster_identity` is null
and `roster_identity_withheld` says why; withholding it refuses no boot, because the
digests are the bound bytes' either way.

## 7. Exit codes

`0` is a composition or run that met every check. `1` is a refusal this contract names.
`2` is an input the harness cannot read (a roster, recipe, member source or boot record
that is missing, not UTF-8 or malformed), an output it cannot write, or an emulator it
cannot find or start. `boot roster` answers `0` whenever the roster reads and states the
members that block acceptance on its verdict line.

`boot roster` answers on either lane. `compose` and `run` run in the guest, and `run.py`
re-launches them there from the host, so the record `compose` writes under the lane's guest
output and the emulator `run` boots it on are in one place.

## 8. The fixture recipe

[The fixture recipe](../../../tools/boot/fixture-recipe.json) composes three assembly units
against [a fixture roster](../../../tools/boot/fixture-roster.json): a firmware stand-in
that prints through HTIF and enters the next member, a kernel stand-in that takes one trap
and enters the last, and a service stand-in that ends the run. They carry the store-side
root in `c8`, which is their own convention and not the scalar handoff. They exercise
composition, placement, imports, the event log, both console channels and the expected
digests on the golden emulator; they are not roster members and establish nothing about
any real member's behaviour.

## 9. What stays open

No recipe composes accepted products for the whole roster. The supervisor, copy-service and offline
reference programs are partial implementations, with their open joins recorded above.
A version 2 recipe binds reference admission metadata; production derivations remain open.
The RoT stage is not driven. The supervisor's static C manifest is a proposed source
pending target qualification. The RVFI trap convention R3's comparison depends on is
R2's to fix. The expected digests of the
composed image, its boot measurement against S4's projection, and the rerun that
reproduces them wait for the executable members. M7.2 and M7.3 read captures from a
producer this harness does not yet supply. R3 consumes the accepted image and its console
and event digests under section 6.
