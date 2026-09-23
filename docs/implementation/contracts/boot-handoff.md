# Boot handoff contract

This is M3.5's contract: the acceptance predicate for the RoT's measured release
of the boot core, the order of that release, the boot image layout, the
measurement the release records, the cryptographic operations the boot image's
stages call, and the kernel-entry and initial-capability handoff that M4.4's
kernel consumes.

**Precedence.** The [register](../../requirements-register.md) governs, and
[the specification's chain](../../spec.md#r-09-002) is its prose.
[RotFirmware.v](../../../proofs/RotFirmware.v) states the measured chain,
[RomVerifier.v](../../../proofs/RomVerifier.v) the ROM verifier's shape and
[MModeFirmware.v](../../../proofs/MModeFirmware.v) the handoff relation.
[The purecap ABI contract](purecap-abi.md#7-the-kernel-entry-interface) fixes
the register state at kernel entry and
[the sealing-bootstrap contract](sealing-bootstrap.md) the object-type roots.
This document is read after all of them and is defective wherever it disagrees
with one.

**Implementation owners.** [vos_boot.h](../../../firmware/include/vos_boot.h)
owns the constants the layout tables below state. `run.py boot-handoff layout`
holds the header, record, composition and initialization-descriptor tables
against it, the case table against the harness's case list, and the permission
column of the kernel-entry table against the assembled image's constants
(section 7); the operations table and the other kernel-entry cells are prose no
command reads. The release is
[boot_verify.c](../../../firmware/rot/boot_verify.c) over
[keccak.c](../../../firmware/crypto/keccak.c); the M-mode stage is
[handoff.s](../../../firmware/mmode/handoff.s). The
[firmware README](../../../firmware/README.md) states what each file is and is not.

## 1. Scope

This contract owns the predicate (section 2), the release sequence (section 3),
the image layout (section 4), the measurement and the assignment of every
cryptographic operation the boot image's stages call (section 5), and the
handoff layout, the initialization descriptor's included (section 6). It does
not own the kernel body, which is M4.4's; the compiler, the
backend and `compiler-diff`, which are M1.2f's; the target path, which is M1.7's;
the reset table's release points (R-15-198a), which are Q33's; or the executable
SLH-DSA verifier, which section 5 assigns to M7.1f. The real kernel joins at M7.1.

## 2. The acceptance predicate

The predicate is decided over two existing instruments and the two this item
adds, and over nothing else:

- the golden emulator built from this tree's model sources (`run.py model build`),
  read through its HTIF verdict line (`SUCCESS` or `FAILURE: n`) and its
  `--trace-commit` records;
- the same emulator under [verifiedos-rot.json](../../../model/config/verifiedos-rot.json),
  M3.1's composition, here running [the input probe](../../../firmware/harness/rot_inputs.s),
  whose signature region reports the lifecycle index, the entropy root's health
  word after the start-up tests and counter 0, the image security version;
- the RoT stage, `boot_verify.c` compiled for the host by
  [the harness driver](../../../firmware/harness/rot_stage_main.c), which stands
  in for the RoT hart until M1.7's target path builds it for the RoT composition;
- `run.py boot-handoff run`, which joins them and writes one report row per case.

**Release.** Let the RoT inputs be the probe's answers: the lifecycle state it
reads, an entropy verdict that passes exactly when the health word's completion
bit (32) is set and its fail-stop bit (33) is clear, a boot-target latch of 0,
and the floor F it reads. For a boot image whose header is well formed under
section 4, whose security version is at least F, whose signature the bound
verifier accepts under the one root that lifecycle state accepts, and whose
payload digest equals SHAKE256 of the payload at 256 bits:

1. the RoT stage reports `release`, calls its release hook exactly once, and
   records measurement items 1, 2, 3 and 5 in that order, item 4 being absent
   from this chain (sections 3 and 5);
2. its image window holds exactly the payload followed by zeros, and its handoff
   record holds the fields of section 6 with values equal to its report and its
   inputs, with the image digest equal to SHAKE256 of the payload;
3. the golden emulator started on
   [verifiedos.json](../../../model/config/verifiedos.json) from exactly that
   window at `composition.load_base` and that record at
   `composition.handoff_base` retires its first instruction at the load base,
   retires the kernel entry, and reports `SUCCESS`, which the
   [kernel-entry fixture](../../../firmware/harness/kernel_entry_fixture.s)
   writes only after its eleven checks of section 6 hold.

**Refusal.** For each refusal row of the table below, the RoT stage reports the
named refusal, `released=0`, an image window that is all zero and a handoff
window it never wrote, and records measurement items 1, 2 and 3 only; the
harness starts no main-die run, so no instruction of the refused image retires.

**Controls.** Three controls keep the predicate from passing vacuously. The
padding case flips a byte the kernel never reads: the RoT refuses it on the
measurement, and the same bytes forced past the RoT run to `SUCCESS`, so the
refusal is the measurement's decision and not a broken image. The valid payload
placed beside an all-zero record fails the fixture's check 6, so the record the
kernel reads is the RoT's and not the image's. The handoff mutants are signed
and released like the valid image and fail at kernel entry with the named check,
the armed timer's event being delivered to the kernel's trap entry before check
1 runs and reporting 32 plus the low five bits of the firmware's `gp`, zero
here, so the fixture's checks are load-bearing and release alone is not the
kernel entry predicate.

**The racing case.** `header-rewritten-during-verify` stands for another
requester writing the input while the release runs: its header was signed at
version F - 1 and shows F, and the harness's racing fixture verifier writes
F - 1 back into the input when it is called. A release that verified the input
rather than its own copy of the signed prefix would pass the floor on F and the
signature on F - 1; this one refuses the signature. It shows that the release
decides on one copy, not that the RoT's memory is private (section 3).

| Case | Input | RoT verdict | Main-die run |
| --- | --- | --- | --- |
| `valid` | well-formed image, version F, production root | `release` | `SUCCESS` |
| `payload-padding-byte-flipped` | one payload byte in the zero gap | `refuse-digest` | none; forced: `SUCCESS` |
| `payload-kernel-byte-flipped` | the kernel entry's first byte | `refuse-digest` | none |
| `digest-field-resigned` | header digest zeroed, then signed | `refuse-digest` | none |
| `digest-last-byte-resigned` | header digest's last byte changed, then signed | `refuse-digest` | none |
| `digest-field-unsigned` | header digest byte changed after signing | `refuse-signature` | none |
| `signature-byte-flipped` | one signature byte | `refuse-signature` | none |
| `development-root-on-production` | signed under the development root | `refuse-signature` | none |
| `below-floor` | version F - 1 | `refuse-floor` | none |
| `header-rewritten-during-verify` | signed at F - 1, shown as F, rewritten to F - 1 during verification | `refuse-signature` | none |
| `length-beyond-region` | declared length one past the region | `refuse-length` | none |
| `length-zero` | declared length 0 | `refuse-length` | none |
| `length-at-region` | payload zero-padded to exactly the region | `release` | `SUCCESS` |
| `image-window-short` | an image window one byte short of the payload | `refuse-placement` | none |
| `truncated-payload` | input one byte short of its payload | `refuse-truncated` | none |
| `truncated-header` | input one byte short of the header | `refuse-truncated` | none |
| `offset-not-fixed` | payload offset field off by 8, signed | `refuse-offset` | none |
| `magic-wrong` | format field 0, signed | `refuse-magic` | none |
| `stage-wrong` | the RoT runtime's stage identifier, signed | `refuse-stage` | none |
| `verifier-absent` | no bound signature verifier | `refuse-no-verifier` | none |
| `entropy-failed` | entropy verdict injected as failed | `refuse-entropy` | none |
| `lifecycle-raw` | lifecycle injected as raw | `refuse-no-root` | none |
| `development-part` | lifecycle injected as development, development root | `release` | `SUCCESS` |
| `mutant-mepcc-kept` | stage clears MEPCC through `cnull` | `release` | `FAILURE: 10` |
| `mutant-unseal-root-kept` | stage's clear keeps `c3` | `release` | `FAILURE: 1` |
| `mutant-global-stack` | stage keeps the stack global | `release` | `FAILURE: 4` |
| `mutant-linked-entry` | stage enters with `cjalr cra, c5, 0` | `release` | `FAILURE: 1` |
| `mutant-timer-armed` | stage arms an immediate boundary event before entry | `release` | `FAILURE: 32` |

The `development-part` row also holds R-09-025a's split: its generation register
equals the `valid` row's and its device register differs. The three injected
inputs are harness values, because the shipped RoT composition's seeded source
passes its start-up tests and its fuse holds production, so the probe cannot
produce them; each such row records its inputs in the report. The short window
and the racing verifier are harness driver arguments, and each row records them
too.

**What the predicate does not decide.** That the RoT hart executes the stage;
that any signature scheme verifies, the harness binding a fixture that section 5
describes; that the RoT's memory is private to it; that M4.4's kernel accepts
the handoff; any timing, including R-09-006b's worst-case figure; A/B selection
and boot counting (R-09-028); the ROM's verification and measurement of the RoT
runtime itself (item 4); the watchdog's arming and petting (R-15-198, R-15-240);
and the reset table's walk (R-15-198). A green run says the host-compiled stage,
the fixture signature, the fixture kernel and this emulator agree with this
contract over the listed cases, and every report carries
`milestone_acceptance: open`.

## 3. The release sequence

R-09-006 fixes the ROM's sequence and R-09-002 that no stage executes before its
measurement is recorded. RotFirmware.v's specification chain extends the three
inputs first, items 1, 2 and 3 at RoT start and before the ROM verifies any
payload (R-09-037), then measures and runs each stage in R-09-002's order: item
4 and the RoT runtime, then item 5 and the M-mode image. This release performs
that chain from reset with the RoT runtime's measurement and run left out,
because no RoT runtime image exists yet: it extends items 1, 2, 3 and 5, and a
chain that verifies the RoT runtime extends item 4 between its items 3 and 5.
For the M-mode stage the release runs, in this order, and stops at the first
refusal:

1. Extend the device register with the lifecycle index (item 1), before any byte
   of the image is read (R-09-037); then the entropy verdict as 0 or 1 (item 2,
   R-09-006a) and the boot-target latch's one bit (item 3, R-09-029). An
   extension the measurement log cannot record refuses (`refuse-measurement`),
   here and at step 7; the log holds `VOS_MEASURE_LOG_CAPACITY` items against a
   release's four extensions, which a static assertion in `boot_verify.c`
   holds, so no case reaches that refusal.
2. Refuse on a failed entropy verdict, which is a halt and consumes no boot
   attempt (R-09-006a); refuse where the lifecycle state accepts no root
   (R-09-036).
3. ReadHeader: refuse an input shorter than the header; copy the signed prefix,
   `header.signed_bytes` long, into the release's own storage once, and read
   every field below and the message step 5 verifies from that copy; then
   refuse a wrong magic, a stage other than the M-mode image, a payload offset
   other than `header.bytes`, a payload length of zero or beyond
   `composition.region_bytes`, and an input shorter than the header plus that
   length. Every field is at a constant offset and none locates another
   (R-09-005).
4. CheckFloor: refuse a security version below the floor (R-09-005, R-09-030).
5. VerifySignature: refuse where no verifier is bound, and where the verifier
   does not accept the signature over the copied signed prefix under the
   lifecycle state's root (R-05-058c, R-09-036).
6. Refuse where the image window is shorter than the payload or the handoff
   window shorter than `record.bytes` (`refuse-placement`), before any byte is
   placed. Place the payload in the image window and zero the rest of the
   window, then Measure: SHAKE256 of the placed bytes, so what is hashed is what
   the boot core will fetch, the core being held until the comparison. Refuse
   where it differs from the copied header's digest.
7. Extend the generation register with the digest (item 5) and compute the chain
   digest.
8. Write the handoff record (section 6), then release. Nothing follows the
   release.

Every refusal zeroes the image window, leaves the handoff window unwritten and
does not release. RomVerifier.v's `spec_order` is ReadHeader, CheckFloor,
VerifySignature, Measure, Execute, and steps 3 to 8 are that order with placement
inside Measure.

**What the release reads from its input, and when.** The signed prefix is read
once, so the magic, stage, offset, length, security version and digest the
release decides on are the bytes it verifies. The signature is read from the
input in place, by the verifier, and the payload once, into the image window.
The input and both windows must therefore be memory no requester other than the
RoT can write for the duration of the release; providing that is the RoT
composition's authority over its SRAM and the main SRAM windows, and nothing in
the host harness shows it.

## 4. The boot image layout

The header is fixed-layout and length-bounded (R-09-005). Integers are one
little-endian doubleword. The signed region is every byte before the signature.

| Field | Offset | Bytes | Check |
| --- | --- | --- | --- |
| `header.magic` | 0 | 8 | equals the bytes `VOSBOOT1` |
| `header.stage` | 8 | 8 | equals 1, the M-mode image in R-09-002's order |
| `header.security_version` | 16 | 8 | at least the floor |
| `header.payload_offset` | 24 | 8 | equals `header.bytes`; checked, never followed |
| `header.payload_length` | 32 | 8 | from 1 to `composition.region_bytes` |
| `header.payload_digest` | 40 | 32 | SHAKE256 of the payload at 256 bits |
| `header.signature` | 72 | 29792 | SLH-DSA-SHAKE-256s over the signed bytes |

| Constant | Value | Meaning |
| --- | --- | --- |
| `header.bytes` | 29864 | the header's length and the payload's offset |
| `header.signed_bytes` | 72 | the signed prefix |
| `composition.load_base` | 0x80000000 | where the stage is placed and where the released core starts |
| `composition.region_bytes` | 0x10000 | the M-mode image region's capacity |
| `composition.handoff_base` | 0x80010000 | where the RoT writes the handoff record |

The signature field is FIPS 205 Table 2's size for SLH-DSA-SHAKE-256s, which
RomVerifier.v computes. R-09-005 names the header's hash without fixing its
function or width; SHAKE256 at 256 bits is this contract's selection, as section
5's measurement encoding is. The composition constants are the bring-up composition's
and not architecture: the attested devicetree owes their production values
(R-09-007, R-15-002b). The released core's first instruction is the load base,
which is a constant and not a header field, so no entry point is read from the
image.

RomVerifier.v's `demo_header` packs four fields, offset, length, hash and
signature, from offset 0. This layout keeps those four in that order and adds
the magic, the stage and the security version before them, the floor comparison
needing a version the image declares and the statement's `Header` having no
field for it. Section 8 records that difference.

## 5. Measurement and the operations the boot image calls

**Registers (R-09-025a).** Two 32-byte registers, zero at reset: the generation
register takes every extension the generation's source determines, and the
device register every extension the unit supplies. An extension is
SHAKE256(`VOS-EXT1` || register || item code || length as four little-endian
bytes || data) at 256 bits, and the chain digest is
SHAKE256(`VOS-CHN1` || generation || device) at 256 bits. The item codes are
RotFirmware.v's `all_items` order: 1 the lifecycle state, 2 the entropy verdict,
3 the boot-target latch, and 4 to 7 the four stages from the RoT runtime to the
static image. Items 1 to 3 go into the device register and items 4 to 7 into the
generation register. In the specification chain items 1 to 3 are extended at
RoT start, before the ROM verifies the RoT runtime and extends item 4, and item
5 follows item 4. This release makes the same extensions in the same order with
item 4 left out (section 3), so its generation register holds item 5 alone, and
a chain that measures the RoT runtime reaches a different generation register
for the same M-mode image. Items 6 and 7 belong to the later stages.

**Operations.** Every cryptographic operation the boot image's two stages call,
and where each one's executable form is:

| Operation | Caller and use | Executable form | Owner of what is missing |
| --- | --- | --- | --- |
| SHAKE256 | the release: the payload digest, each extension, the chain digest | [keccak.c](../../../firmware/crypto/keccak.c), functional layer only | the target build (M1.7) and the constant-time layer (R-05-062, R-05-067) |
| SLH-DSA-SHAKE-256s verification | the release: the signature over the signed bytes | none: the harness binds a fixture | M7.1f, as an executable verifier under FIPS 205 with the parameter set RomVerifier.v states |
| Counter read | the release: the floor, counter 0 of R-10-013's enumeration | the RoT composition's counter window | n/a |
| Entropy draw | none: the release reads the start-up verdict and draws nothing | n/a | n/a |
| ML-DSA verification | the M-mode stage: the core-kernel stage's signature, before any core kernel runs; none at the ROM (R-05-058c, R-09-002) | none | M7.1f, as an executable ML-DSA verifier over M3.4b's Gallina reference, whose target lowering M3.4 leaves as separate work |
| Item-6 extension request | the M-mode stage: asking the RoT to extend the generation register with the core-kernel stage's measurement before that stage runs (R-09-002, R-09-025a) | none: no main-die interface to the RoT's registers exists | M3.5 |

The bring-up M-mode image carries the kernel-entry fixture inside itself, so the
fixture is measured as part of item 5, and neither the ML-DSA verification nor
the item-6 request occurs; both are owed once the core kernels are a separately
signed stage.

The SHAKE256 implementation is compared with Python's `hashlib.shake_256`, an
independent implementation, on every run of the harness, over input lengths
spanning the 136-byte rate's boundaries and output lengths spanning one squeeze
block. That comparison is a finite campaign and not a proof; the functional
reference is [Keccak.v](../../../proofs/Keccak.v) and no correspondence between
the two is claimed.

**The fixture verifier is not a signature scheme.** It accepts exactly
SHAKE256(`VOS-FIXTURE-SIG1` || public key || signed bytes) at the signature
size, which anyone holding the public key computes. It exercises the accept and
reject arms a verifier's answer drives; it verifies nothing, it is compiled into
the harness driver and never into firmware, and it cannot stand in a report as
the production binding.

## 6. The kernel entry and initial-capability handoff

The M-mode stage runs from `composition.load_base` under the model's reset
distribution: PCC, MTCC and MEPCC the execute root with access-system-registers,
MTDC null, `c1`
the store-side root, `c2` and `c3` the object-type roots, every other register
null. It installs the state below and enters the kernel with `cjr c5`, as
[purecap-abi.md section 7](purecap-abi.md#7-the-kernel-entry-interface) selects.
That section has firmware leave interrupt delivery disabled until the kernel has
installed its dispatch state. The profile's one asynchronous trap is the
slot-boundary timer, which neither `mie`, whose one field is hardwired one, nor
mstatus.MIE can mask (R-15-066a), so the stage disables delivery by arming
nothing: it never writes `mtimecmp`.
By this contract's selection the bring-up composition declares no sealing grant
type, so neither object-type root has an admitted derivation, and
[the sealing-bootstrap contract's section 2](sealing-bootstrap.md#2-composed-installation-and-lifetime)
requires the broad roots cleared before the kernel runs, so both are cleared.
The kernel the stage enters lies inside the measured M-mode image in this
composition and is measured as part of item 5 (section 5).

| Location at kernel entry | Bring-up value | Expanded permissions |
| --- | --- | --- |
| PCC | the kernel text extent, unsealed from the entry sentry | `0x9cb`: execute, load, load-capability, load-global, load-mutable, access-system-registers, global |
| `c5` | the forward sentry over the kernel text; the entry clears it | as PCC, sealed as the forward edge |
| `csp` / `c2` | the kernel stack region, cursor at its top | `0xfe`: perms_stack, local |
| `c10` | the root-set table, one slot holding the kernel data root | `0xcb`: perms_r_cap_lm_lg, global |
| `c11` | the handoff record below, the boot descriptor | `0x3`: read, global |
| `c12` | the kernel initialization descriptor | `0xcb` |
| MTCC | the kernel trap entry inside the kernel text | `0x9cb` |
| MTDC | the kernel data root | `0xdf`: perms_data_root, global |
| MEPCC | null | n/a |
| the boundary timer | unarmed and not pending: `mip` reads zero, and no boundary event arrives until the kernel programs `mtimecmp` | n/a |
| every other register | null, value and tag | n/a |

**The root-set table.** Slot `i` is one naturally aligned tagged capability for
the composition's `i`-th declared extent, and the table's length is eight bytes
per declared extent, so the kernel reads which slot is which from the
composition's declaration and never from the table's contents. The bring-up
composition declares one extent, the kernel data extent, whose root is `0xdf`.
A composition declaring partition roots and shared windows, which
KernelInstance.v's partition-root clause quantifies over, extends the table in
its declared order. Every extent is exactly representable, and the fixture checks
the base and length of each capability it is handed rather than trusting that.

**The handoff record.** The RoT writes it at `composition.handoff_base` before
release, outside the measured image, and the M-mode stage hands it to the kernel
read-only in `c11`. Integers are one little-endian doubleword; bytes from 200 to
255 are zero.

| Field | Offset | Bytes | Value |
| --- | --- | --- | --- |
| `record.magic` | 0 | 8 | the bytes `VOSHAND1` |
| `record.version` | 8 | 8 | 1 |
| `record.lifecycle` | 16 | 8 | the lifecycle index the release read |
| `record.entropy_ok` | 24 | 8 | 1, the verdict the release measured |
| `record.boot_target` | 32 | 8 | the latch's one bit, as measured |
| `record.security_version` | 40 | 8 | the released image's |
| `record.floor` | 48 | 8 | the floor at the decision |
| `record.load_base` | 56 | 8 | `composition.load_base` |
| `record.payload_length` | 64 | 8 | the released payload's length |
| `record.image_digest` | 72 | 32 | SHAKE256 of the placed payload |
| `record.generation` | 104 | 32 | the generation register after item 5, holding item 5 alone in this chain |
| `record.device` | 136 | 32 | the device register after item 3 |
| `record.chain` | 168 | 32 | the chain digest |

| Constant | Value | Meaning |
| --- | --- | --- |
| `record.bytes` | 256 | the record's extent and `c11`'s length |

**The initialization descriptor.** The composition writes it at build time
into the measured image, and the M-mode stage hands it to the kernel read-only
in `c12`. It names the planned save areas and the initial schedule inputs that
purecap-abi.md section 7 says `c12` names, with the partition, window and
switch-text extents M4.4's checks read. Integers are one little-endian
doubleword and an extent is two,
its base and then its top. The last column names the field of M4.4's consumer
record, `struct vos_init_desc`, that each field fills.

| Field | Offset | Bytes | Value | M4.4's field |
| --- | --- | --- | --- | --- |
| `init.magic` | 0 | 8 | the bytes `VOSINIT1` | n/a |
| `init.version` | 8 | 8 | 1 | n/a |
| `init.composition` | 16 | 8 | the composition's identity | `composition_id` |
| `init.hart` | 24 | 8 | the hart it is for, compared with `mhartid` | `hart_id` |
| `init.root` | 32 | 16 | the partition-bounded root's declared extent | `root` |
| `init.switch_text` | 48 | 16 | the kernel's switch text extent | `switch_text` |
| `init.partition_count` | 64 | 8 | P, the declared partitions | `partition_count` |
| `init.window_count` | 72 | 8 | W, the declared shared windows | `window_count` |
| `init.slot_count` | 80 | 8 | S, the schedule table's slots | `frame.slot_count` |
| `init.csr_count` | 88 | 8 | C, the CSR roster's rows | `machine.csr_count` |
| `init.major_frame` | 96 | 8 | the major frame (R-11-014d) | `frame.major_frame` |
| `init.phase_offset` | 104 | 8 | the frame's phase offset (R-11-014a) | `frame.phase_offset` |
| `init.reserved_count` | 112 | 8 | the reserved band's slots | `frame.reserved_count` |
| `init.pending_arm` | 120 | 8 | R-07-044's arm: 1 swapped, 0 static | `machine.pending_swapped` |
| `init.rotation_swaps` | 128 | 8 | whether the rotation swaps the pending component (R-07-037c) | `machine.rotation_swaps_pending` |
| `init.pending_static_mask` | 136 | 8 | the static arm's partition of the pending file | `machine.pending_static_mask` |

| Constant | Value | Meaning |
| --- | --- | --- |
| `init.header_bytes` | 144 | the header's length and the first array's offset |
| `init.partition_bytes` | 56 | one partition: its tenant, then its planned save area's, text's and data's extents (`partitions[]`) |
| `init.window_bytes` | 16 | one shared window's extent (`windows[]`) |
| `init.slot_bytes` | 40 | one slot: width, offset, bound, period and tenant, CyclicExecutive.v's `Slot` (`frame.slots[]`) |
| `init.csr_bytes` | 24 | one CSR roster row: the CSR's address, nameable and zeroized (`machine.roster[]`) |

The header is followed by the P partition records, the W window extents, the S
slots in the table's order and the C roster rows, and the descriptor's length,
which is `c12`'s, is `init.header_bytes` plus P, W, S and C times their record
sizes. An empty save-area extent, its base equal to its top, plans no context
for its partition; M4.4's record carries a `has_context` flag in its place.
M4.4's record has the other fields named above with narrower integer types whose
padding the target ABI decides, and no magic or version, so its kernel reads
this layout field by field rather than overlaying the struct; that join is
section 8's. The bring-up composition declares no partition, window, slot or
roster row, so its descriptor is the header alone and plans no successor, which
M4.4's kernel must refuse; the fixture, which is not that kernel, checks only
the fields its check 7 reads.

**What M4.4 consumes, and what it must check before its first dispatch.** The
register state above at its first instruction, with no return to firmware. From
`c11` it reads the record's magic and version and may read the measurement for
its own records; the record's bytes are the RoT's, and their authentication is
the measured chain's, not the capability's. From `c12` it must reject a missing
descriptor, a wrong magic or version, a composition identity other than its
own, a hart identity other than `mhartid`, a count beyond its capacity, a length
other than its counts imply, a root, switch-text, window, text or data extent
whose base is not below its top, a partition extent outside the root, and an
initialization with no planned successor, a slot whose tenant has no partition
with a planned save area, as purecap-abi.md section 7 requires. The fixture
checks the magic, the version, the composition identity and the hart identity;
`run.py boot-handoff layout` checks the fixture's descriptor's magic, version and
length against its counts. From `c10` it takes one tagged member per declared
extent. MTCC and MTDC are installed; MEPCC holds no continuation; no boundary
event is armed. The partition contexts and the schedule table are M4.4's to construct
and check from the descriptor (purecap-abi.md gap k).

**The M-mode stage is a hand lowering.** [handoff.s](../../../firmware/mmode/handoff.s)
is written in the assembler dialect because no compiler reaches the dialect yet:
its C lowering needs source bindings for `cspecialrw` and `csealentry` (M1.2d,
purecap-abi.md gap l) and M1.7's target path. The M-mode firmware's remaining
duties, R-07-028's installation of the composed graph and R-07-019's per-core
roots, are stated in MModeFirmware.v and are not discharged by this stage, which
installs the bring-up composition's one-kernel distribution.

## 7. The harness

`run.py boot-handoff run` compiles the RoT stage with the flags its report
records, AddressSanitizer and UndefinedBehaviorSanitizer included; compares its
SHAKE256 with `hashlib`; runs the probe under the RoT composition; assembles the
M-mode stage with the fixture; submits every case of section 2 to the stage; and
for each release starts the golden emulator from the placed window and record,
wrapped as ELF sections at their addresses with an HTIF `tohost` symbol. It
writes `report.json` with the input digests, the emulator's digest, the compiler
and every row, and exits 0 only when every row matches.
`run.py boot-handoff layout` holds, on either lane, the header, record,
composition and initialization-descriptor tables of sections 4 and 6 against
`vos_boot.h`, the case table of section 2 against the harness's case list, the
permission column of section 6's kernel-entry table against the assembled
image's constants, and the fixture's initialization descriptor against its
layout. Section 5's operations table and the kernel-entry table's other cells
are prose no command reads; the harness run holds the kernel-entry state
through the fixture's checks.

## 8. Open joins and findings

- **The RoT hart does not execute the release.** The stage runs host-compiled
  until the purecap backend (M1.2f) and M1.7's target path build it for the RoT
  composition.
- **No executable SLH-DSA-SHAKE-256s verifier exists.** Section 5 assigns it to
  M7.1f; until it lands the success case is conditional on the fixture.
- **The model has no boot-core release door and no boot-target latch door.**
  The emulator composes one hart per run, so release is realized as starting the
  main-die run, and the latch (R-09-029) is a harness constant. Where the reset
  table's release points live is Q33's (R-15-198a).
- **RomVerifier.v's `Header` carries no security version.** Its floor comparison
  reads a version the statement's header has no field for; this layout adds
  one, with the magic and the stage.
- **The floor is established in the same power-on.** The emulator retains no OTP
  state between runs, so the probe advances counter 0 to the floor it reports.
- **The measurement encoding and the payload digest are this contract's
  selection.** R-09-025a fixes the two registers and R-09-002 that every stage
  is measured; no entry fixes the extension function, the item encoding or the
  chain digest, and RotFirmware.v takes `extend` and `item_code` as fields.
  R-09-005 names the header's hash without its function or width. Sections 4
  and 5 make the bring-up selection.
- **The device register lacks two inputs the register names.** R-09-025a puts
  the per-unit calibration R-15-126 measures in the device register, and
  R-09-036a measures the enrolled root set into it at every boot. RotFirmware.v's
  `all_items` gives neither an item code, and this release extends neither.
- **Item 4 and the later stages are not measured here.** The ROM's measurement
  of the RoT runtime, which falls between items 3 and 5, is left out, so a
  released record's generation register is not the one a full chain produces for
  the same image. The M-mode stage's item-6 request and its ML-DSA verification
  of the core-kernel stage have no executable form, and M7.1f owns the
  executable ML-DSA verifier (section 5).
- **M4.4's consumer record differs from the initialization descriptor.** Its
  `struct vos_init_desc` carries no magic or version, a `has_context` flag
  where section 6 declares the planned save area's extent, and narrower
  integer fields laid out by the target ABI. The join is M4.4's kernel reading
  section 6's layout field by field, with the correspondence section 6's table
  records.
- **The firmware's watchdog duty is not discharged.** R-15-198 puts every
  sequencing step under a watchdog-bounded timeout that the RoT firmware
  executes, and R-15-240's pets are RoT-nonce challenge-responses; this release
  neither arms nor pets the watchdog.
- **A/B selection and boot counting are not exercised** (R-09-028, R-09-029).
