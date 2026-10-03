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
owns the constants the layout tables of sections 4 and 6 state, and
[vos_chain.h](../../../firmware/chain/vos_chain.h) owns the target chain
composition's constants, verdicts, records and C entry points (section 9).
`run.py boot-handoff layout` holds the header, record, composition and
initialization-descriptor tables against `vos_boot.h`, section 9's tables
against `vos_chain.h` and the model's door declarations, the case table of
section 2 against the harness's case list, and the permission column of the
kernel-entry table against the assembled image's constants (section 7); the
operations table and the other kernel-entry cells are prose no command reads.
The release is [boot_verify.c](../../../firmware/rot/boot_verify.c) over
[keccak.c](../../../firmware/crypto/keccak.c); the M-mode stage is
[handoff.s](../../../firmware/mmode/handoff.s). The
[firmware README](../../../firmware/README.md) states what each file is and is not.

## 1. Scope

This contract owns the predicate (section 2), the release sequence (section 3),
the image layout (section 4), the measurement and the assignment of every
cryptographic operation the boot image's stages call (section 5), the
handoff layout, the initialization descriptor's included (section 6), and the
target chain composition and its acceptance predicate, which M3.5b owns
(section 9). It does
not own the kernel body, which is M4.4's; the compiler, the
backend and `compiler-diff`, which are M1.2f's; the target path, which is M1.7's;
the reset table's release points (R-15-198a), which are Q33's; or the executable
SLH-DSA verifier, which section 5 assigns to M7.1f. The real kernel joins at M7.1.

## 2. The acceptance predicate

This section is the bring-up composition's predicate, which M3.5a landed; the
target chain's predicate is section 9's, decided over a second composition, and
nothing in this section or its case table changes for it.

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
signature-scheme behavior when the fixture verifier is selected; that the
RoT's memory is private to it; that M4.4's kernel accepts
the handoff; any timing, including R-09-006b's worst-case figure; A/B selection
and boot counting (R-09-028); the ROM's verification and measurement of the RoT
runtime itself (item 4); the watchdog's arming and petting (R-15-198, R-15-240);
and the reset table's walk (R-15-198). A green run says the host-compiled stage,
the selected signature verifier, the fixture kernel and this emulator agree with this
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
| SHAKE256 | the release: the payload digest, each extension, the chain digest; in the chain (section 9), the ROM's and runtime's digests and extensions, and the M-mode chain stage's kernel-stage digest and item-6 binding check | [keccak.c](../../../firmware/crypto/keccak.c), functional layer only | the target build (M1.7) and the constant-time layer (R-05-062, R-05-067) |
| SLH-DSA-SHAKE-256s verification | the release: the signature over the signed bytes; in the chain, the ROM's verification of stage 0 and the runtime's of stage 1, both under the ROM root (R-09-036a) | [slh256s.c](../../../firmware/crypto/slh256s.c) through the release-policy callback `vos_boot_slh256s_verify`; `boot-handoff run --signature-scheme slh256s` binds it in the host stage and `boot-handoff release-target` binds it on the RoT composition through the contained backend | M7.1f's target lowering under FIPS 205 with the parameter set RomVerifier.v states; section 9.13's identity freeze with its staged manifest |
| Counter read | the release: the floor, counter 0 of R-10-013's enumeration | the RoT composition's counter window | n/a |
| Entropy draw | none: the release reads the start-up verdict and draws nothing; the chain's runtime draws through the watchdog's challenge alone (R-15-240) | n/a | n/a |
| ML-DSA-87 verification | the M-mode chain stage: the kernel stage's signature over its signed prefix, under the kernel-stage root the measured M-mode image carries, before any byte of that stage runs; none at the ROM (R-05-058c, R-09-002) | [mldsa87.c](../../../firmware/crypto/mldsa87.c): the chain binds `vos_mldsa87_verify_internal` over the 72 signed bytes (section 9.8); the hosted boot-crypto campaign executed it on the RoT composition | section 9's execution on the main die (F-721); a boot callback in `vos_signature.h`, which the staged manifest freezes until M7.1f stages again (F-742) |
| Item-6 extension request | the M-mode chain stage: asking the RoT to extend the generation register with the kernel stage's measurement before that stage runs (R-09-002, R-09-025a) | section 9.7's mailbox exchange: a request record the stage writes, a response record the RoT's item-6 service writes in its own run, and the stage's binding check over both | the two-hart realization, the mailbox's authority and the response's authentication (section 9.15) |

The bring-up M-mode image carries the kernel-entry fixture inside itself, so the
fixture is measured as part of item 5, and neither the ML-DSA verification nor
the item-6 request occurs in it; both belong to the chain composition's M-mode
stage (section 9), where the core kernels are a separately signed stage.

The SHAKE256 implementation is compared with Python's `hashlib.shake_256`, an
independent implementation, on every run of the harness, over input lengths
spanning the 136-byte rate's boundaries and output lengths spanning one squeeze
block. That comparison is a finite campaign and not a proof; the functional
reference is [Keccak.v](../../../proofs/Keccak.v) and no correspondence between
the two is claimed.

The optional `slh256s` campaign signs the actual copied header prefix with
OpenSSL, using disposable per-lifecycle roots held in the caller's native
output directory. The host stage verifies through `vos_slh256s_verify`; the
same case table and signed-prefix race control apply. The report records the
selected verifier and producer identities. This is executable real-signature
evidence for the host release path, with no claim that the RoT hart runs the
release stage or that the fixture kernel is M4.4's consumer.

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

**Scalar scheduled composition.** M4.4's scalar target member extends this
interface with three leading root-table slots, in order: the kernel data root, an
eight-byte read/write data window for hart zero's `mtimecmp`, and an eight-byte
read-only window for `mtime`. The timer addresses come from the selected
profile's CLINT base and the register offsets in
[the platform model](../../../model/model/sys/platform.sail). The producer
derives both timer capabilities from reset authority, narrows each exactly,
and removes capability-transfer and execute permissions. Read/write is the
least authority in the frozen permission lattice that permits a store; the
lattice has no store-only shape. The two timer
extents are explicit shared windows in the initialization descriptor; the
kernel receives no authority over the rest of CLINT. The descriptor's
`init.root` is the physical partition containing its declared text and data,
not a claim that its data-root capability also authorizes text. Execute and
store authority retain R-15-007p's split.

One execute-side root follows for each declared partition, in descriptor
order. Each is bounded exactly to that partition's text extent, unsealed,
and stripped of access-system-registers permission. Firmware derives them
from reset execute authority before narrowing its own kernel PCC. The kernel
checks these roots against the descriptor and uses them to construct the
initial saved program counters; neither an integer text address nor the
kernel's narrower PCC supplies authority for a successor outside kernel text.
No partition receives a timer or kernel-data root.

The finite revocation composition may append one eight-byte read/write data
root after the partition execute roots, also declared as a shared window.
It covers exactly the bitmap word containing the dedicated retired object's
granule. The address is derived from the selected profile's revocation base
and interval and [the model's index function](../../../model/model/core/revocation.sail):
the object's offset is divided by the capability granule size, then by the
number of bits in one word. The producer narrows reset data authority to that
word and removes execute and capability-transfer permissions. The kernel
checks its tag, unsealed state, exact extent and permissions, and attempts an
over-bound derivation just as for every other declared window. No partition
receives the bitmap root.

This finite composition declares the retired object's complete resident and
saved-copy population and has no borrowed copy, proxy or device access to that
object. Its trusted kernel retains a wider protected data root, including
MTDC, that could mint authority to the object again. The finite witness
therefore assumes that this reviewed kernel text neither recreates nor regrants
retired authority after publication; the complete holder and derivable-base
inventory is explicit. A trace of cleared copies alone establishes no general
admission proof for that premise. Publication, resident-root clearing and filtered saved-image storage
must be observed before semantic completion permits dispatch. Epoch-only
completion and an unsanitized saved image refuse dispatch. The observation
does not claim reuse, a complete sweep, a general ownership proof or a
multi-hart barrier; [the revocation qualification](../../assurance/revocation-qualification.md)
retains those boundaries.

This composition keeps the timer unarmed through firmware entry. Before the
first dispatch the kernel checks the actual root-table capabilities' tags,
extents and permissions against the declaration. Its in-program bounds
controls cover the data root and both timer windows. A missing, swapped,
overbroad or wrongly permissioned timer slot refuses entry. The target
campaign must observe the timer-driven boundary and the complete restore;
descriptor decoding or an independently minted test capability supplies no
evidence for that producer/consumer join. M4.4 owns the nonempty schedule and
the emitted composition; the empty-descriptor fixture retains its separate
predicate above.

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
padding the target ABI decides, and no magic or version. Its
[byte reader](../../../kernel/src/handoff.c) checks the wire header and widths,
reads each field separately and retains the save-area extents beside that record.
Actual target entry remains section 8's join. The bring-up composition declares no
partition, window, slot or roster row, so its descriptor is the header alone and plans no successor, which
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
layout. It also holds section 9's constant tables against `vos_chain.h`, the
boot-control door offsets against `rot.sail`'s declarations and the window's
base against the RoT composition where either declares them, and reports how
many of the doors the model declares; and it parses section 9's case table,
refusing a duplicate name, an unknown run kind or an unknown verdict, so the
chain harness can hold its case list against it. Section 5's operations table
and the kernel-entry table's other cells are prose no command reads; the
harness run holds the kernel-entry state through the fixture's checks.

## 8. Open joins and findings

- **The bring-up release runs host-compiled, and the chain's stages are owed as
  target programs.** `boot-handoff run` compiles the release stage for the host
  and says so in every report. `boot-handoff release-target` compiles the
  preparation body `vos_rot_prepare_mmode` through the contained backend and runs
  it on the RoT composition, with assembly supplying the device reads the
  compiler does not lower; at `0f61470a` its seven cases passed and the released
  capture ran the main die to `SUCCESS`. The ROM, runtime, item-6 service and
  M-mode chain stage of section 9 are the target programs still owed.
- **The target signature-verifier binding is built for the release body and
  frozen by identity for the chain.** `release-target` binds
  `vos_boot_slh256s_verify` through the contained backend over the unchanged
  `keccak.c` and `slh256s.c`; `boot-handoff run` keeps the fixture verifier by
  default and binds the real one under `--signature-scheme slh256s`, so a default
  run's success establishes no signature verification. No record yet holds a
  chain unit's verifier identities to M7.1f's staged manifest; section 9.13
  states the equality the chain campaign must show (F-722).
- **The model has no boot-core release door, no boot-target latch door and no
  boot-control state.** The emulator composes one hart per run, so in the
  bring-up composition release is realized as starting the main-die run and the
  latch (R-09-029) is a harness constant (F-435). Section 9.4 specifies the
  boot-control window that adds the latch, slot, attempt and release doors; until
  it lands, `layout` reports that `rot.sail` declares none of them. Where the
  reset table's release points live is Q33's (R-15-198a).
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
- **Item 4 and the later stages are not measured in the bring-up composition.**
  The ROM's measurement of the RoT runtime, which falls between items 3 and 5,
  is left out of sections 2 and 3, so a released record's generation register is
  not the one the chain produces for the same image. Section 9 measures items 4
  and 6 and integrates the ML-DSA verification into the chain's M-mode stage;
  M7.1f owns the executable verifiers (section 5).
- **M4.4's target entry must bind the decoded records to actual capabilities.** Its
  `struct vos_init_desc` carries no magic or version, a `has_context` flag
  where section 6 declares the planned save area's extent, and narrower
  integer fields laid out by the target ABI. The bounded byte reader checks
  section 6's layout and preserves those save areas. The remaining join reads
  the actual c10/c11/c12 capabilities, establishes their provenance and extent,
  and constructs the initial contexts before dispatch. Host byte-reader checks
  supply no target capability or authentication evidence.
- **The firmware's watchdog duty is not discharged by the bring-up release.**
  R-15-198 puts every sequencing step under a watchdog-bounded timeout that the
  RoT firmware executes, and R-15-240's pets are RoT-nonce challenge-responses;
  the release of section 3 neither arms nor pets the watchdog. Section 9.6's
  runtime arms and pets it over the bring-up reset table, which is not Q33's
  table, and section 9.10 states the observations owed.
- **A/B selection and boot counting are not exercised by the bring-up release**
  (R-09-028, R-09-029); section 9.6 states both for the chain, and section 9.15
  the two counting questions the register leaves open (F-738, F-739).

## 9. The target chain

This section is M3.5b's acceptance predicate: R-09-002's measured chain from the
RoT's ROM through the RoT runtime, an A/B-selected M-mode image and a separately
signed kernel stage, executed by the golden emulator built from this tree's
model sources and decided from receipts. It is a second composition beside the
bring-up one of sections 2 to 7: that composition's constants, its 28-case
`boot-handoff run`, its 7-case `release-target`, `boot_handoff.scheduled_mmode`
and every M4.4 consumer keep their values, cases and verdicts, and nothing in
this section changes them. M3.5b's implementation starts after this section is
landed and is accepted when section 9.12's predicate holds on hosted runners
under section 9.14.

### 9.1 Owners and the composition's constants

[vos_chain.h](../../../firmware/chain/vos_chain.h) owns every constant below,
the verdict codes, the record layouts and the C entry points of section 9.11; it
includes `vos_boot.h` and changes none of its names. The chain's C and assembly
live beside it under `firmware/chain/`, or under `firmware/rot/`,
`firmware/mmode/` and `firmware/harness/`, and never under `firmware/include/`
or `firmware/crypto/`: M7.1f's staged manifest binds those two trees byte for
byte and by listing, and section 9.13's identity freeze is an equality with it.
A chain translation unit includes the bound sources unchanged, as
[rot_release_target.c](../../../firmware/harness/rot_release_target.c) does.

Both compositions share one address map, so the windows below are addresses in
the model's first-class RAM. The store windows stand for the raw-NAND boot
region R-09-004 fixes, the state window for the RoT's retained SRAM, and the
capture window for the RoT's view of main SRAM and for what it exports to the
harness (section 9.11). The attested devicetree owes the production values of
every constant here (R-09-007, R-15-002b); none is architecture.

| Constant | Value | Meaning |
| --- | --- | --- |
| `chain.rot_state_base` | 0x80380000 | the RoT state record window (section 9.5) |
| `chain.rot_state_window_bytes` | 0x1000 | its extent: the record at 0, a service run's request at `state.request_at` |
| `chain.rot_runtime_base` | 0x80400000 | where the ROM places stage 0 and enters it |
| `chain.rot_runtime_region_bytes` | 0x40000 | the RoT runtime execute region |
| `chain.rot_runtime_data_at` | 0x20000 | the runtime image's data half, measured with its text |
| `chain.rot_capture_base` | 0x80500000 | the RoT run's capture (section 9.11) |
| `chain.rot_capture_window_bytes` | 0x80000 | the capture capability's extent |
| `chain.store_runtime_base` | 0x80600000 | the boot-store window holding the stage-0 image |
| `chain.store_runtime_bytes` | 0x80000 | its capacity |
| `chain.store_a_base` | 0x80700000 | slot A's stage-1 image |
| `chain.store_b_base` | 0x80780000 | slot B's stage-1 image |
| `chain.store_recovery_base` | 0x80800000 | the recovery generation's stage-1 image (R-09-029) |
| `chain.store_mmode_bytes` | 0x80000 | each stage-1 store window's capacity |
| `chain.mmode_load_base` | 0x80000000 | where the runtime places the M-mode image and the released core starts |
| `chain.mmode_region_bytes` | 0x40000 | the M-mode image region |
| `chain.mmode_data_at` | 0x20000 | the M-mode image's data half |
| `chain.handoff_base` | 0x80040000 | where the runtime writes the handoff record |
| `chain.mailbox_base` | 0x80041000 | the item-6 mailbox (section 9.7) |
| `chain.mmode_capture_base` | 0x80042000 | the M-mode chain stage's capture |
| `chain.main_signature_bytes` | 0x2000 | the main-die run's signature region from the mailbox base |
| `chain.kernel_store_base` | 0x80080000 | the kernel stage's input window |
| `chain.kernel_store_bytes` | 0x20000 | its capacity |
| `chain.kernel_load_base` | 0x80100000 | where the M-mode stage places the kernel stage |
| `chain.kernel_region_bytes` | 0x10000 | the kernel stage region |
| `chain.tohost_base` | 0x80101000 | the main-die run's HTIF word: the kernel data extent's first word |
| `chain.boot_control_base` | 0x2A00000 | the boot-control window (section 9.4) |
| `chain.boot_control_bytes` | 0x1000 | its aperture |
| `chain.boot_attempt_bound` | 3 | RotFirmware.v's `boot_bound` for this composition |
| `chain.reset_steps` | 3 | the bring-up reset table's steps (section 9.6) |
| `chain.measure_extensions` | 6 | items 1 to 6, against `VOS_MEASURE_LOG_CAPACITY` |
| `chain.slow_clock_boot_ns` | 160000000 | the external slow clock's host period for boot runs |
| `chain.slow_clock_watchdog_ns` | 1000000 | its period for the watchdog cases' runtime-only runs |
| `chain.control_inst_limit` | 50000000 | the detached-clock control's instruction limit |
| `chain.mmode_exit_base` | 64 | the M-mode stage reports a refusal as HTIF exit 64 plus its code |

The chain's verdict codes are `vos_boot_verdict`'s 0 to 13 with their names
and meanings, and four more; every refusal names the first check that failed.

| Verdict | Code | Meaning |
| --- | --- | --- |
| `verdict.refuse_state` | 14 | the RoT state record's magic, version or run kind is not the run's |
| `verdict.refuse_record` | 15 | the handoff record's magic or version at the M-mode stage |
| `verdict.refuse_request` | 16 | an item-6 request not for stage 2, or a log that cannot record item 6 |
| `verdict.refuse_response` | 17 | an item-6 response that does not bind this request |

Slots are `slot.a` 0, `slot.b` 1 and `slot.recovery` 2; the phases a RoT run
reports are `phase.rom` 0, `phase.runtime` 1, `phase.released` 2 and
`phase.service` 3; the run kinds a state record carries are `run.boot` 1 and
`run.service` 2. Each is a macro of `vos_chain.h` under the name the row gives.

| Code | Value | Meaning |
| --- | --- | --- |
| `slot.a` | 0 | slot A |
| `slot.b` | 1 | slot B |
| `slot.recovery` | 2 | the recovery generation, outside the A/B count |
| `phase.rom` | 0 | the run ended in the ROM |
| `phase.runtime` | 1 | the run ended in the runtime before release |
| `phase.released` | 2 | the runtime wrote the release door |
| `phase.service` | 3 | an item-6 service run |
| `run.boot` | 1 | a boot run's state record |
| `run.service` | 2 | a service run's state record |

### 9.2 Instruments and run kinds

The predicate is decided over these instruments and nothing else:

- the golden emulator built from this tree's model sources, on
  [verifiedos-rot.json](../../../model/config/verifiedos-rot.json) for every RoT
  run and on [verifiedos.json](../../../model/config/verifiedos.json) for the
  main-die run, read through its verdict lines and its `--test-signature`
  capture, which it writes on an HTIF success, on a release and at the
  instruction limit, so a run ending on the limit is decided by its lines and
  its retired count and never by its capture (F-769);
- the RoT composition's four device windows
  ([rot.sail](../../../model/model/sys/rot.sail)) and the boot-control window
  section 9.4 adds, each varied per case through a per-case variant of the
  configuration file whose every other key is the shipped file's;
- the external slow clock, `--rot-slow-clock-ns`
  ([rot_slow_clock.h](../../../model/c_emulator/rot_slow_clock.h)), whose
  period is section 9.10's per run kind and is recorded in every receipt;
- the contained compiler, which compiles every chain unit where it is
  provisioned and never on a hosted runner (section 9.14);
- a host oracle: Python over `hashlib`'s SHAKE256 and the campaign's disposable
  OpenSSL keys, computing from each case's inputs every byte that crosses a run
  boundary and every verdict, by sections 9.5 to 9.8 and independently of the C;
- the chain harness and the hosted campaign that runs it (section 9.14).

**One hart per process, run boundaries as hart boundaries.** The emulator
composes one hart per run (R-15-005). Every point where the chain crosses from
one hart to another, or where the RoT waits on another hart, is a run boundary
with the harness as the channel, and every byte that crosses a boundary is
captured and compared with the oracle. The RoT state that persists between RoT
runs, the measurement registers and log and the boot inputs, travels in the
state record (section 9.5) that every RoT capture exports and the harness
supplies to the next RoT run; that carry stands for the RoT's retained SRAM, and
the predicate does not decide its privacy. The boot-control doors' values after
a run are read back into the capture by the firmware, and the harness starts
the next run from the oracle's expected values, not the capture's, so a lying
capture is a mismatch rather than an input.

| Run kind | Composition and entry | How it ends with a verdict |
| --- | --- | --- |
| boot run | the RoT composition; the ROM program at the reset vector, which enters the runtime at `chain.rot_runtime_base` on the ROM's release | a `RELEASE` line and a capture (the runtime wrote the release door); or one `SUCCESS` line and a capture whose `capture.verdict` is a refusal (a completed refusal); or the emulator's bite line and no capture |
| runtime-only run | the RoT composition; the stage-0 payload placed by the harness at `chain.rot_runtime_base` with a state record the ROM would leave, entered at that base after a harness-composed preamble performs the ROM's two device acts, the entropy root's start-up tests and counter 0's advance to F, so the runtime meets the devices a boot run's runtime meets | as a boot run; the watchdog cases of section 9.10 end on the bite line, and the detached-clock control on its instruction limit |
| service run | the RoT composition; the same payload with a `run.service` state record and a request at `state.request_at` | one `SUCCESS` line and a capture holding the response |
| main-die run | the main-die composition; the placed M-mode window, the record, the mailbox and the kernel store, entered at `chain.mmode_load_base` | `SUCCESS` from the kernel stage's report after its eleven checks, with the signature region captured; or `FAILURE: n`, n the fixture's check or 64 plus the M-mode stage's refusal code |

Any other ending, a timeout, an instruction limit outside the control case, a
Sail exception, a trap loop, two verdict lines, a `RELEASE` line beside an HTIF
line, or a missing or short capture, supplies no verdict, and a case with no
verdict fails. The emulator ends a RoT run at the instruction that writes the
release door, so nothing follows the release, and a bite ends it at the pump
that asserted the die reset, so nothing follows a bite; neither rests on the
firmware's own report.

### 9.3 The images

**Stage 0, the RoT runtime image.** Section 4's header with `header.stage` 0,
signed with SLH-DSA-SHAKE-256s under the lifecycle state's ROM root
(R-09-036a), payload length from 1 to `chain.rot_runtime_region_bytes`. The
payload is the runtime program laid out for its placement: text from
`chain.rot_runtime_base`, data from `chain.rot_runtime_data_at` within the
region, measured as one flat extent from the base to the end of the data with
the gap zero. Its entry is its base. The ROM enters it with the RoT's own
authority, PCC the reset execute root and `c1` the store-side root, because the
RoT runtime is RoT firmware and not a less-trusted stage; it reads the state
record at `chain.rot_state_base` and nothing else from the ROM.

**Stage 1, the M-mode image.** Section 4's header with `header.stage` 1, signed
under the same ROM root, payload length from 1 to `chain.mmode_region_bytes`,
in three store windows: slot A, slot B and the recovery generation. Each payload
is the chain's M-mode stage, the hand-lowered assembly of section 9.8 beside its
compiled body with the kernel-stage root key as data, laid out from
`chain.mmode_load_base` with data from `chain.mmode_data_at`, followed by one
eight-byte slot tag that nothing on the target reads: `VOSSLOTA`, `VOSSLOTB` or
`VOSRCVRY`, so the three images' digests and item 5 differ and the record says
which slot booted. Their security versions are the floor F for every slot.

**The kernel-stage root is carried inside the measured M-mode image.** This is
the contract's bring-up selection: the ML-DSA-87 public key that admits the
kernel stage is data of the stage-1 payload and so bound by item 5 and by the
ROM root's signature over that image. R-09-036a places the roots that admit a
generation in an enrolled set the RoT holds under counter-protected state; no
enrolled set exists in this composition, and section 9.15 records the gap
(F-741).

**Stage 2, the kernel stage.** Section 4's field order at section 4's offsets,
with the magic, stage and signature sizes below; the signed prefix is the 72
bytes before the signature, as for the SLH headers. The reader is the M-mode
stage, which refuses every stage but 2 before reading further, so its header
length is one constant and no field locates another (R-09-005).

| Field | Offset | Bytes | Check |
| --- | --- | --- | --- |
| `kstage.magic` | 0 | 8 | equals the bytes `VOSKERN1` |
| `kstage.stage` | 8 | 8 | equals 2, the core kernels in R-09-002's order |
| `kstage.security_version` | 16 | 8 | at least `record.floor` |
| `kstage.payload_offset` | 24 | 8 | equals `kstage.bytes`; checked, never followed |
| `kstage.payload_length` | 32 | 8 | from 1 to `chain.kernel_region_bytes` |
| `kstage.payload_digest` | 40 | 32 | SHAKE256 of the payload at 256 bits |
| `kstage.signature` | 72 | 4627 | ML-DSA-87 over the signed bytes (FIPS 204) |

| Constant | Value | Meaning |
| --- | --- | --- |
| `kstage.bytes` | 4699 | the header's length and the payload's offset |
| `kstage.signed_bytes` | 72 | the signed prefix |
| `kstage.public_key_bytes` | 2592 | the kernel-stage root's length |

The kernel-stage payload is the existing kernel-entry fixture
([kernel_entry_fixture.s](../../../firmware/harness/kernel_entry_fixture.s))
moved into its own image, its eleven checks unchanged, laid out inside the
kernel region as the table below fixes so that the M-mode stage derives the
kernel-entry state from constants and reads no entry point or extent from the
image. The fixture's initialization descriptor declares the kernel region as its
root extent and the kernel text as its switch text.

| Field | Offset | Bytes | Check |
| --- | --- | --- | --- |
| `kernel.text` | 0 | 0x1000 | the fixture's text; the entry is its first instruction |
| `kernel.data` | 0x1000 | 0x400 | the kernel data extent; its first word is `tohost` |
| `kernel.stack` | 0x1400 | 0x400 | the kernel stack region |
| `kernel.root_table` | 0x1800 | 8 | one slot, the kernel data root |
| `kernel.init` | 0x1840 | 144 | the initialization descriptor, section 6's header alone |

| Constant | Value | Meaning |
| --- | --- | --- |
| `kernel.entry_at` | 0 | the kernel entry's offset in the text |
| `kernel.trap_at` | 0x800 | the trap entry's offset in the text, where MTCC points |

### 9.4 The model's boot-control window

The RoT composition gains a fifth device window beside the OTP, the entropy
root, the counters and the watchdog, answering the RoT hart alone and faulting
every other requester and every width but a doubleword, as the four do.
[rot.sail](../../../model/model/sys/rot.sail) owns the offsets as `ROT_BOOT_*`
beside the four windows' layouts, and `vos_chain.h` mirrors them; `layout` holds
the two together. The configuration declares the window under
`platform.boot_control` with `supported`, `base`, `size`, `boot_target`,
`active_slot` and `attempts`, in every shipped configuration and in
`config.json.in`, because the three shipped files carry one key set; the
validator refuses `boot_target` or `active_slot` above 1, a `size` under
`door.bytes` and an aperture overlapping another. The shipped values are
`boot_target` 0, `active_slot` 0 and `attempts` 0; the harness varies them per
case through configuration variants, and the latch and the counts are emulation
facts like the entropy seed, not emitted into the attested devicetree.

| Door | Offset | Access | Meaning |
| --- | --- | --- | --- |
| `door.boot_target` | 0 | read | the latched boot-time signal's one bit (R-09-029), `boot_target` at reset and constant through the run |
| `door.slot` | 8 | read, write 0 or 1 | the active slot; `active_slot` at power-on |
| `door.attempts` | 16 | read, write | the active slot's attempt count; `attempts` at power-on |
| `door.release` | 24 | write 1 | releases the boot core: the run ends at this instruction |
| `door.bytes` | 32 | n/a | the doors' extent |

The slot and attempt doors hold the RoT's retained boot state (R-09-028): a
write to either takes effect at once, a write of a slot value above 1 or of a
release word other than 1 faults, and both values survive a die reset within a
run and not across runs, as F-438 records of the counters. The release door is
the model's realization of R-09-006's release in a one-hart emulator: the
emulator, on the step that wrote it, prints `RELEASE: the RoT released the boot
core` with the retired count, writes the `--test-signature` capture as it does
on an HTIF success, and exits 0; the Sail side latches `rot_released`, which
nothing clears. A release on a bitten watchdog is unreachable, the bite having
ended the run. The window exists so that the release observation and *nothing
follows the release* rest on the emulator and not on the firmware's count of
its own hook, which is what `release-target` relies on today.

### 9.5 The ROM

The ROM program is harness-composed for the RoT composition, the ROM body of
section 9.11 compiled through the contained compiler with the bound SLH verifier
and `vos_boot_slh256s_verify`, and its assembly reading the devices it names;
the emulator loads it as the run's program because R-09-003's metal-mask ROM has
no aperture in any composition. The floor is established in the same power-on
by advancing counter 0, as section 2's probe does (F-438). The ROM neither arms
nor pets the watchdog, which counts from power-on (R-15-240's always-on), so the
ROM phase runs under the window before the runtime opens it; section 9.10 sizes
the clock so that it fits. In order, stopping at the first refusal:

1. Read the lifecycle index from the OTP window and extend the device register
   with it (item 1), before any byte of any image is read (R-09-037).
2. Run the start-up health tests through the entropy root's door, read the
   health word, and extend the verdict, 1 where bit 32 is set and bit 33 clear
   and 0 otherwise (item 2, R-09-006a).
3. Read the boot-target latch door and extend its one bit (item 3, R-09-029).
   An extension the log cannot record refuses (`refuse-measurement`), here and
   at every later extension; `vos_chain.h`'s static assertion holds the log's
   capacity against the chain's six, so no case reaches it.
4. Refuse a failed verdict (`refuse-entropy`): the halt, which charges no
   attempt and touches no boot-control door (R-09-006a). Refuse a lifecycle
   state with no root (`refuse-no-root`, R-09-036).
5. ReadHeader over the stage-0 store window, as section 3's step 3, with the
   stage 0 and the region `chain.rot_runtime_region_bytes`; the signed prefix is
   copied once and every field is read from the copy.
6. CheckFloor against counter 0 (`refuse-floor`).
7. VerifySignature: SLH-DSA-SHAKE-256s over the copied prefix under the
   lifecycle state's root (`refuse-signature`).
8. Place the payload at `chain.rot_runtime_base`, zero the rest of the region,
   SHAKE256 the placed bytes and refuse a digest other than the copied header's
   (`refuse-digest`); extend the generation register with it (item 4).
9. Write the state record at `chain.rot_state_base`: `run.boot`, the inputs it
   read, the registers and log after item 4; write the capture head's input,
   measurement and `phase.rom` fields.
10. Enter the runtime at `chain.rot_runtime_base` (R-09-002's `Run RotRuntime`).
    Every refusal zeroes the runtime region, leaves the state record's magic
    zero, writes the capture head with the verdict and ends the run with an
    HTIF success, which is the completed attempt the capture decides.

| Field | Offset | Bytes | Value |
| --- | --- | --- | --- |
| `state.magic` | 0 | 8 | the bytes `VOSSTAT1` |
| `state.version` | 8 | 8 | 1 |
| `state.run_kind` | 16 | 8 | `run.boot` or `run.service` |
| `state.lifecycle` | 24 | 8 | the lifecycle index the ROM read |
| `state.entropy_ok` | 32 | 8 | the verdict it measured |
| `state.boot_target` | 40 | 8 | the latch's one bit |
| `state.floor` | 48 | 8 | the floor it read |
| `state.measure_count` | 56 | 8 | extensions so far |
| `state.log` | 64 | 16 | the item codes in order, zero beyond the count |
| `state.generation` | 80 | 32 | the generation register |
| `state.device` | 112 | 32 | the device register |

| Constant | Value | Meaning |
| --- | --- | --- |
| `state.bytes` | 256 | the record's extent; bytes from 144 to 255 are zero |
| `state.request_at` | 256 | where a service run finds its request in the state window |

### 9.6 The RoT runtime

The runtime reads the state record and refuses a magic, version or run kind
other than `run.boot` (`refuse-state`). Then it arms and walks the table,
selects and charges, verifies, writes the record and releases, in that order.

**The bring-up reset table.** The table is this composition's and not Q33's:
R-15-198a's release points and the production table are Q33's, and this table
exercises the mechanism R-15-198 states, an action, a ready indication over an
existing RoT device and the watchdog window as the step's timeout, with a pet
point at each completion. A step waits by polling its ready indication and never
pets while it waits, so a step that never becomes ready is ended by the bite and
by nothing in the firmware.

| Step | Code | Action | Ready indication |
| --- | --- | --- | --- |
| `step.arm` | 0 | write the watchdog's arm door | the challenge door reads nonzero |
| `step.entropy` | 1 | none: the ROM ran the tests | the health word's bit 32 set and bit 33 clear |
| `step.floor` | 2 | none | counter 0 reads nonzero |

**Pets.** At a pet point the runtime reads the tick door; where the count is at
or above the early bound and at or below the late bound it reads the challenge
door and writes the response door with that value, which is R-15-240's
RoT-nonce challenge-response, and counts an accepted pet; where the count is
below the early bound it counts a skipped pet and does not pet, because an early
pet is a bite. The pet points are the three completions and the point after the
stage-1 signature verification below. The capture records the challenge read at
arming, the two counts, and the bitten and tick doors read last.

**Selection and counting.** The runtime reads the A, B and recovery store
windows' headers and the slot and attempt doors. Selection and counting follow
RotFirmware.v: with the latch 1 the recovery generation is selected (R-09-029),
the A/B state is left as read and no attempt is charged, the recovery generation
standing outside the A/B count (F-738). With the latch 0: if the attempt count is
at or above `chain.boot_attempt_bound`, revert, the other slot becoming active
with a count of zero (`spec_revert`, `RevertsPastTheBound`); then charge, the
count becoming one more (`spec_charge`'s `OrdinaryFailure` arm,
`AdmitsBelowTheBound`); write the slot door and then the attempt door, and only
then verify the active slot's image, so the attempt is charged before the
verification it gates and a refusal leaves it charged (R-12-017's order, applied
to boots). A release leaves the count where the charge put it: nothing in this
composition clears it, and section 9.15 records that the register names no
clearing act (F-739).

**Verification, record and release.** The selected image is verified as section
3's steps 3 to 7 over its store window, with the stage 1, the region
`chain.mmode_region_bytes`, the root the state's lifecycle accepts and the
capture's M-mode window as the main SRAM image window: ReadHeader, CheckFloor
against `state.floor`, VerifySignature, placement with the tail zeroed, Measure,
item 5. A pet point follows the verification, which is the window that
verification spent. The runtime then writes the handoff record into the
capture's record slot (section 9.9) and the capture head's selection,
measurement and watchdog fields with `phase.released`, and writes 1 to the
release door; the emulator ends the run there.

Every refusal zeroes the M-mode window, leaves the record slot zero, writes the
capture head with the verdict and `phase.runtime`, and ends the run with an HTIF
success. RomVerifier.v's `spec_order` holds at both verifications.

### 9.7 The item-6 exchange

R-09-002 has the kernel stage measured before it runs and R-09-025a puts that
measurement in the RoT's generation register, which the main die cannot reach.
On the die the M-mode stage asks the RoT and waits; in a one-hart emulator the
ask is a run boundary. The choreography is:

- the M-mode stage computes the request on the main die from the kernel-stage
  payload it placed, and writes it to the mailbox's request slot before it reads
  the response slot;
- the RoT's item-6 service runs as a service run, its request computed by the
  host oracle from the kernel-stage image the campaign signed and its state
  record carried from the boot run's capture; it refuses a request whose magic
  or stage is not stage 2's or a log that cannot record item 6
  (`refuse-request`), extends the generation register with item 6 over the
  request's digest, and writes the response;
- the harness places that response in the mailbox before the main-die run, and
  the M-mode stage enters the kernel only when the response binds exactly its
  own request: the magic and stage are the response's, the echoed digest equals
  the digest it computed, the generation register equals
  SHAKE256(`VOS-EXT1` || `record.generation` || 6 || 32 as four little-endian
  bytes || digest), the device register equals `record.device`, and the chain
  digest equals SHAKE256(`VOS-CHN1` || generation || device); otherwise it
  refuses (`refuse-response`). The harness also compares the request the stage
  wrote with the oracle's byte for byte.

The binding check is a recomputation anyone holding the record can perform. It
decides that the response answers this request over this record and not that
the RoT produced it; the response's authentication, the mailbox's privacy and
the concurrency of a two-hart die are what section 9.15 leaves undecided
(F-743).

| Field | Offset | Bytes | Value |
| --- | --- | --- | --- |
| `request.magic` | 0 | 8 | the bytes `VOSITM6Q` |
| `request.stage` | 8 | 8 | 2 |
| `request.digest` | 16 | 32 | SHAKE256 of the placed kernel-stage payload |

| Constant | Value | Meaning |
| --- | --- | --- |
| `request.bytes` | 64 | the request's extent; bytes from 48 to 63 are zero |

| Field | Offset | Bytes | Value |
| --- | --- | --- | --- |
| `response.magic` | 0 | 8 | the bytes `VOSITM6R` |
| `response.stage` | 8 | 8 | the request's stage, 2 |
| `response.digest` | 16 | 32 | the request's digest, echoed |
| `response.generation` | 48 | 32 | the generation register after item 6 |
| `response.device` | 80 | 32 | the device register, unchanged |
| `response.chain` | 112 | 32 | the chain digest after item 6 |
| `response.measure_count` | 144 | 8 | 6 |
| `response.log` | 152 | 16 | the item codes 1 to 6, zero beyond |

| Constant | Value | Meaning |
| --- | --- | --- |
| `response.bytes` | 256 | the response's extent; bytes from 168 to 255 are zero |
| `mailbox.request_at` | 0 | the request slot in the mailbox |
| `mailbox.response_at` | 256 | the response slot |
| `mailbox.bytes` | 512 | the mailbox's used extent |

### 9.8 The M-mode chain stage and the kernel entry

The M-mode chain stage runs from `chain.mmode_load_base` under the model's reset
distribution, as section 6's stage does. Its special-register work stays
hand-lowered assembly beside a compiled C body, the C lowering of `cspecialrw`
and `csealentry` being outside this item (M1.2d, purecap-abi.md gap l); the
assembly derives bounded capabilities to the record, the kernel store, the
kernel region, the mailbox and the capture from the store-side root and hands
them to the body, which runs on a stack at the top of the M-mode region that the
assembly fixes and no stage-1 payload reaches (F-759). The body reaches the
kernel region by aligned doublewords alone, because `chain.tohost_base` lies
inside it and the emulator's HTIF device answers that word to aligned four- and
eight-byte accesses only; a payload whose doubleword at `kernel.data` is nonzero
therefore issues an HTIF command at placement, before the digest comparison
(F-758). In order, stopping at the first refusal:

1. Refuse a record whose magic or version is not section 6's (`refuse-record`).
2. ReadHeader over the kernel store window with section 9.3's stage-2 layout:
   an input shorter than `kstage.bytes` (`refuse-truncated`), a magic other than
   `VOSKERN1` (`refuse-magic`), a stage other than 2 (`refuse-stage`), an offset
   other than `kstage.bytes` (`refuse-offset`), a length of zero or beyond
   `chain.kernel_region_bytes` (`refuse-length`), an input shorter than the
   header plus the length (`refuse-truncated`); the signed prefix is copied once.
3. CheckFloor: a security version below `record.floor` (`refuse-floor`).
4. VerifySignature: `vos_mldsa87_verify_internal` over the copied 72-byte prefix
   with the signature in place and the kernel-stage root the image carries,
   FIPS 204's internal algorithm with no context prefix, as the SLH binding uses
   FIPS 205's (`refuse-signature`). This is the chain's ML-DSA boot binding;
   `vos_signature.h` carries no boot callback for ML-DSA and cannot gain one
   while the staged manifest binds it (F-742).
5. Place the payload at `chain.kernel_load_base`, zero the rest of the region,
   SHAKE256 the placed bytes, refuse a digest other than the copied header's
   (`refuse-digest`).
6. Write the request to the mailbox and read the response; refuse a response
   that does not bind the request (section 9.7, `refuse-response`).
7. Write the M-mode capture, install the kernel-entry state and enter.

A refusal zeroes the kernel region, writes its code to the M-mode capture and
reports it through HTIF as `chain.mmode_exit_base` plus the code, so the
fixture's codes 1 to 11 and 32 to 63 and the stage's 64 and above never meet.

**The kernel entry.** Section 6's table holds with these values: PCC and `c5`
over `kernel.text` from `chain.kernel_load_base`, the entry at `kernel.entry_at`
and MTCC at `kernel.trap_at`; `csp` over `kernel.stack` with the cursor at its
top; `c10` over `kernel.root_table`, its one slot the kernel data root over
`kernel.data`, which is also MTDC; `c11` the handoff record at
`chain.handoff_base`, `record.bytes` long; `c12` the descriptor at `kernel.init`;
MEPCC null, the boundary timer unarmed, every other register null. The
permissions are section 6's. The kernel stage's report writes `tohost` at
`chain.tohost_base`, the first word of its data extent, and the M-mode stage's
refusals write the same word, so the main-die run has one HTIF word.

### 9.9 The measurement and the record in the chain

The registers and encoding are section 5's. Items 1, 2 and 3 each extend one
byte, the lifecycle index, the verdict as 0 or 1 and the latch's bit, as section
3's release extends them (F-767). The chain extends items 1, 2 and 3
into the device register in the ROM, item 4 into the generation register in the
ROM, item 5 in the runtime and item 6 in the service run, in that order, which
is RotFirmware.v's specification chain through its sixth extension; item 7 and
the static image are outside this composition. The handoff record is section
6's layout at version 1, written by the runtime before release, with
`record.load_base` equal to `chain.mmode_load_base`, `record.generation` the
generation register after item 5, holding items 4 and 5, `record.device` the
device register after item 3, and `record.chain` the chain digest over both. The
record handed to the kernel in `c11` therefore predates item 6; the registers
after item 6 reach the main die in the response alone, which the kernel stage
does not read (F-744).

### 9.10 Watchdog and reset observations

The external slow clock is the host's, with no ratio to retirement
(R-15-196), and the window is the composition's, 1024 to 65536 ticks in the
shipped configurations. Which host period a run gets is this contract's, per run
kind, and every receipt records it:

- **Boot runs** run at `chain.slow_clock_boot_ns` (160 ms a tick). The late bound is then 10,486 s of host time, which holds the
  ROM phase, one SLH verification observed at 2,100 to 4,300 s on hosted runners
  plus its reads and placement, under the window before the runtime arms; after
  arming, the runtime's verification of stage 1 takes 13,000 to 27,000 ticks,
  inside the window, so the pet point after it is an accepted pet, and the
  three step completions, microseconds apart, are skipped pets. A boot run that
  releases therefore records at least one accepted pet, no bite and a bitten
  door reading zero.
- **The watchdog cases** run runtime-only at `chain.slow_clock_watchdog_ns` (1 ms
  a tick), where the late bound is 65.5 s after arming and the stall is reached
  in microseconds. No one period serves both: at the boot period a stall bites
  three hours after the ROM phase, and at the watchdog period the ROM phase
  itself would bite, so no run observes a bite after a complete ROM phase
  (F-740).
- **Service runs and the main-die run** run with no external clock. The main
  die's doors refuse every requester, and a service run pets nothing.

The observations owed, each a case of section 9.12:

- the positive path above: pets accepted in window and no bite;
- `watchdog-stalled-step`: a runtime whose `step.entropy` ready predicate is
  rewritten to a bit the health word never sets, so the step never becomes ready
  and no pet is issued; under the external clock the model bites at the first
  tick past the late bound and the emulator's join asserts the die reset and
  prints its bite line, the run ending there with no release and no capture,
  and the line's tick count is above the late bound;
- `watchdog-early-pet`: a runtime that pets at `step.arm`'s completion without
  reading the tick door, so the pet is early and the model bites at once; the
  join takes the reset on its next pump with no tick due, as
  [watchdog_join.cpp](../../../model/test/unit_tests/watchdog_join.cpp)'s
  unmatched-pet case shows the path, and the bite line's tick count is below the
  early bound, which separates this bite from a late one;
- `watchdog-stalled-no-clock`: the stalled runtime with no external clock, run
  to `chain.control_inst_limit`, which must end on the limit with no bite line
  and no HTIF line; it attributes the bite above to the clock and not to the
  harness's stepping, as that unit test's detached-clock control does.

The mutations are text substitutions of the runtime source, named and recorded
in the receipt as section 2's handoff mutants are; a runtime-only run verifies
no signature, so the mutants are placed unsigned. How these runs end is
decisive because the emulator exits on the pump that asserted the reset and
prints the bite line only then, and because a run on the instruction limit
prints no verdict line. What the run cannot observe is the die back at its
reset vector and the ROM reading the bitten latch after the reset: the emulator
exits before another instruction retires, and the reset-vector observation is
the unit test's (F-745).

### 9.11 Run choreography, captures and work packages

**The runs of a case**, each on its own emulator process:

- **R1**, the boot run: the ROM program with the campaign's stage-0 image in the
  runtime store window, the three stage-1 images in theirs, the ROM roots as
  data and the per-case configuration variant. On release its capture holds the
  state record, the handoff record and the placed M-mode window.
- **R2**, the service run: the stage-0 payload placed by the harness at
  `chain.rot_runtime_base`, R1's captured state record with `run.service` at
  `chain.rot_state_base`, and the oracle's request at `state.request_at`. Its
  capture holds the response and the state after item 6.
- **R3**, the main-die run: R1's placed window at `chain.mmode_load_base`, R1's
  record at `chain.handoff_base`, the mailbox with its request slot zero and
  R2's response in its response slot, the stage-2 image in the kernel store, a
  zero kernel region and `tohost` at `chain.tohost_base`, under
  `--test-signature` over `chain.main_signature_bytes` from the mailbox base.

**Byte comparisons.** The oracle computes, and the harness compares byte for
byte: R1's state record, handoff record and placed window and its head's
verdict, phase, input, selection and measurement fields; R2's response and
state; R3's request, response and M-mode capture on a run that reaches the
kernel. The emulator writes no capture on an HTIF failure, so a main-die refusal
is decided by its exit code alone, and a main-die exit that is neither the
kernel stage's report nor 64 plus a refusal code, the stage's own trap report
of 256 plus `mcause` included, supplies no verdict (F-760, F-761). The head's watchdog fields
are compared against predicates, because their values are the clock's and the
entropy root's: the challenge at arming nonzero; on a release at least one
accepted pet, the accepted and skipped counts summing to the table's steps plus
one, the bitten door zero and the tick door at or below the late bound; on a
runtime refusal the two counts summing to the steps or the steps plus one
(F-770).
Fields a run does not reach are zero on both sides.

| Field | Offset | Bytes | Value |
| --- | --- | --- | --- |
| `capture.verdict` | 0 | 8 | the run's verdict code |
| `capture.phase` | 8 | 8 | the phase reached |
| `capture.released` | 16 | 8 | 1 where the release door was written |
| `capture.lifecycle` | 24 | 8 | the lifecycle index read |
| `capture.health` | 32 | 8 | the health word read |
| `capture.boot_target` | 40 | 8 | the latch read |
| `capture.floor` | 48 | 8 | the floor read |
| `capture.slot_initial` | 56 | 8 | the slot door at the runtime's start |
| `capture.attempts_initial` | 64 | 8 | the attempt door at the runtime's start |
| `capture.slot_selected` | 72 | 8 | the slot code verified |
| `capture.slot_final` | 80 | 8 | the slot door read last |
| `capture.attempts_final` | 88 | 8 | the attempt door read last |
| `capture.pets_accepted` | 96 | 8 | pets the model accepted |
| `capture.pets_skipped` | 104 | 8 | pet points before the early bound |
| `capture.nonce_at_arm` | 112 | 8 | the challenge read after arming |
| `capture.bitten` | 120 | 8 | the bitten door read last |
| `capture.ticks_at_end` | 128 | 8 | the tick door read last |
| `capture.steps_completed` | 136 | 8 | reset-table steps completed |
| `capture.measure_count` | 144 | 8 | extensions made |
| `capture.log` | 152 | 16 | the item codes in order |
| `capture.generation` | 168 | 32 | the generation register |
| `capture.device` | 200 | 32 | the device register |
| `capture.chain` | 232 | 32 | the chain digest |
| `capture.runtime_digest` | 264 | 32 | SHAKE256 of the placed stage-0 payload |
| `capture.mmode_digest` | 296 | 32 | SHAKE256 of the placed stage-1 payload |
| `capture.mmode_security_version` | 328 | 8 | the selected image's version |
| `capture.mmode_payload_length` | 336 | 8 | the selected image's payload length |

| Constant | Value | Meaning |
| --- | --- | --- |
| `capture.head_bytes` | 0x200 | the head's extent |
| `capture.record_at` | 0x200 | the handoff record, `record.bytes` long |
| `capture.response_at` | 0x300 | a service run's response |
| `capture.request_at` | 0x400 | the request a service run read, echoed |
| `capture.state_at` | 0x500 | the state record as the run left it |
| `capture.window_at` | 0x1000 | the placed M-mode window, `chain.mmode_region_bytes` long |
| `capture.bytes` | 0x41000 | the capture's extent |

| Field | Offset | Bytes | Value |
| --- | --- | --- | --- |
| `mcapture.verdict` | 0 | 8 | the M-mode stage's verdict code |
| `mcapture.kernel_digest` | 8 | 32 | SHAKE256 of the placed kernel-stage payload |
| `mcapture.security_version` | 40 | 8 | the kernel stage's version |
| `mcapture.payload_length` | 48 | 8 | its payload length |
| `mcapture.request_written` | 56 | 8 | 1 after the request was written |
| `mcapture.response_bound` | 64 | 8 | 1 after the response bound the request |

| Constant | Value | Meaning |
| --- | --- | --- |
| `mcapture.bytes` | 128 | the M-mode capture's extent |

**Work packages.** Four lanes implement this section against `vos_chain.h`'s
prototypes, each leaving `firmware/include/` and `firmware/crypto/` byte for
byte as they are:

| Lane | Owns | Entry symbols and records |
| --- | --- | --- |
| model doors | `rot.sail`'s boot-control doors and `rot_released`, `platform.sail`'s decode, the validator clauses, the configuration key in the three shipped files and `config.json.in`, the emulator's `RELEASE` ending, a unit test beside `watchdog_join.cpp` | `ROT_BOOT_TARGET`, `ROT_BOOT_SLOT`, `ROT_BOOT_ATTEMPTS`, `ROT_BOOT_RELEASE`, `ROT_BOOT_BYTES`; `layout` reports 5 of 5 declared |
| RoT ROM and runtime | the ROM body and its device-reading assembly, the runtime image's assembly entry, table walk, pets, door writes and release, the item-6 service entry | `vos_chain_rom`, `vos_chain_select`, `vos_chain_pet_due`, `vos_chain_runtime_verify`, `vos_chain_service_item6`; the state record, the capture |
| M-mode chain stage and kernel stage | the stage's assembly and body, the kernel-stage image laid out by `kernel.*` from the fixture, the ML-DSA binding | `vos_chain_mmode`; the request, the M-mode capture, the kernel-entry state of section 9.8 |
| hosted campaign | the harness module and `boot-handoff` subcommand, the oracle, image and key production, configuration variants, the runs, receipts and join, the workflow | section 9.12's case table held against its case list; section 9.13's equality; section 9.14's receipts |

### 9.12 The acceptance predicate and the case table

Let F be the floor the ROM reads, established in the same power-on. The
campaign's keys are disposable: one SLH-DSA-SHAKE-256s root per lifecycle state
that accepts one, bound into the ROM as its roots, and one ML-DSA-87 key whose
public half the stage-1 payloads carry. The stage-0 image, the three stage-1
images and the stage-2 image are signed at version F.

**Release.** For `cold-boot`'s inputs, a latch of 0, slot A active with zero
attempts, the production lifecycle and a passing verdict, and well-formed
images: R1 ends on a `RELEASE` line with a capture whose verdict is 0, phase
`phase.released`, log 1, 2, 3, 4, 5 in that order, selected slot A, final slot
A with one attempt, at least one accepted pet and bitten 0, whose state record,
handoff record and placed window equal the oracle's; R2 ends on `SUCCESS` with
the oracle's response, its log 1 to 6; R3, entered at `chain.mmode_load_base`,
reports `SUCCESS`, which the kernel stage alone writes, after its eleven checks,
and its request and M-mode capture equal the oracle's. A commit trace across an
ML-DSA-87 verification is impractical, so that `SUCCESS` is the observation that
the kernel entry was reached; no M-mode stage path writes the value it reports
(F-762). `recovery-latched` and `revert-past-bound` release likewise with
the selection and counts the table gives.

**Refusal.** For each refusal row, the run named ends with the named verdict
and the capture, response or exit code the table gives, the log holds exactly
the items listed, the boot-control values read last are the table's, no release
door is written, and no later run of the case starts; where R1 refuses, its
M-mode window is zero and its record slot zero.

**Order and gating.** `cold-boot` must pass before the three main-die refusals
run, which take its R1 capture and R2 response, identified by SHA-256 in both
receipts; the other boot cases and the watchdog cases depend on no other case
and may run beside it, and the campaign fails whenever `cold-boot` does,
whatever the other rows show. Every case's inputs, period,
instruction limit, timeout, configuration variant, assembly and ELF digests are
in its receipt; a timeout, a trap, an instruction limit outside the control, a
missing or short capture and contradictory verdict lines supply no verdict.

| Case | Run | Inputs | RoT verdict | Items (device; generation) | Boot control after | Main die |
| --- | --- | --- | --- | --- | --- | --- |
| `cold-boot` | joined | latch 0, A active, 0 attempts, every image valid | `release` | 1,2,3; 4,5 then 6 | A, 1 | `SUCCESS` |
| `recovery-latched` | joined | latch 1, A active, 0 attempts | `release` | 1,2,3; 4,5 then 6 | A, 0 | `SUCCESS` |
| `revert-past-bound` | joined | latch 0, A active, 3 attempts | `release` | 1,2,3; 4,5 then 6 | B, 1 | `SUCCESS` |
| `entropy-halt` | joined | the health word read by the assembly injected as failed | `refuse-entropy` | 1,2,3; none | A, 0 | none |
| `lifecycle-raw` | joined | `platform.otp.lifecycle_state` raw | `refuse-no-root` | 1,2,3; none | A, 0 | none |
| `runtime-signature-corrupt` | joined | one stage-0 signature byte flipped | `refuse-signature` | 1,2,3; none | A, 0 | none |
| `runtime-digest-mismatch` | joined | one stage-0 payload byte flipped | `refuse-digest` | 1,2,3; none | A, 0 | none |
| `mmode-below-floor` | joined | slot A's header at version F - 1, signed | `refuse-floor` | 1,2,3; 4 | A, 1 | none |
| `mmode-signature-corrupt` | joined | one byte of slot A's signature flipped | `refuse-signature` | 1,2,3; 4 | A, 1 | none |
| `kernel-signature-corrupt` | main-die | one stage-2 signature byte flipped, over `cold-boot`'s R1 and R2 | `release` | 1,2,3; 4,5 then 6 | A, 1 | `FAILURE: 74` |
| `kernel-digest-mismatch` | main-die | one stage-2 payload byte flipped | `release` | 1,2,3; 4,5 then 6 | A, 1 | `FAILURE: 76` |
| `item6-response-nonbinding` | main-die | a self-consistent response computed for a digest one byte off | `release` | 1,2,3; 4,5 then 6 | A, 1 | `FAILURE: 81` |
| `watchdog-stalled-step` | runtime-only | the stall mutant at the watchdog period | `bite` | n/a | n/a | none |
| `watchdog-early-pet` | runtime-only | the early-pet mutant at the watchdog period | `bite` | n/a | n/a | none |
| `watchdog-stalled-no-clock` | runtime-only | the stall mutant with no external clock | `no-verdict` | n/a | n/a | none |

The main-die exit codes are `chain.mmode_exit_base` plus `refuse-signature`
(10), `refuse-digest` (12) and `refuse-response` (17). The entropy halt's
verdict is injected in the assembly that supplies the device reads, because the
shipped RoT composition's seeded source passes its start-up tests and no
configuration makes it fail, as section 2 records of the same input; the raw
lifecycle is a configuration variant and so a real device input here. The
three main-die refusals reuse `cold-boot`'s R1 capture and R2 response, so each
costs one ML-DSA verification; `item6-response-nonbinding`'s response is the
oracle's response for a digest with one byte flipped, with its own consistent
generation and chain digests, so what refuses it is the digest echo and the
generation recomputation and not a malformed record. A boot run costs at most
two SLH-DSA verifications and the whole campaign eleven.

**Controls against vacuity.** The release observation is the emulator's
`RELEASE` line and not the capture's `capture.released` word, and the two must
agree. `watchdog-stalled-no-clock` shows the bite is the clock's. `mmode-below-floor`
and `mmode-signature-corrupt` leave the attempt charged while
`entropy-halt` and `lifecycle-raw` leave it at zero, so the count is the
counting's and not an artifact of reaching the runtime. `recovery-latched`
and `revert-past-bound` release images whose tags differ from `cold-boot`'s, so
their records' image digests and generation registers differ from `cold-boot`'s
and from each other, while `revert-past-bound`'s device register equals
`cold-boot`'s and `recovery-latched`'s differs from it in item 3 alone, so the
selection is read off the measurement and not off the report.
`item6-response-nonbinding` is a self-consistent response, so the binding
check is shown to compare against the stage's own request. The ROM's
verification of stage 0 is shown load-bearing by `runtime-signature-corrupt`
and `runtime-digest-mismatch` refusing before item 4, and the runtime's by the
two `mmode-` refusals charging an attempt and extending no item 5.

### 9.13 The verifier identity freeze

The chain compiles its verifiers from the unchanged
[keccak.c](../../../firmware/crypto/keccak.c),
[slh256s.c](../../../firmware/crypto/slh256s.c) and
[mldsa87.c](../../../firmware/crypto/mldsa87.c), the SLH-DSA one through
`vos_boot_slh256s_verify` as `release-target` does and the ML-DSA one through
`vos_mldsa87_verify_internal` (section 9.8). Every chain receipt records, under
`sources_sha256`, the SHA-256 of `firmware/crypto/keccak.c`,
`firmware/crypto/slh256s.c`, `firmware/crypto/mldsa87.c`,
`firmware/include/vos_boot.h`, `firmware/include/vos_keccak.h` and
`firmware/include/vos_signature.h` as compiled, and under `compiler_provenance`
and `compiler_inputs_sha256` the contained compiler's `revision`,
`compiler_sha256` and `compcert.ini` digest. The campaign passes only if, for
the tracked [manifest.json](../../../firmware/crypto/target/manifest.json) at
the campaign's revision, each of those six digests equals the manifest's
`sources_sha256` entry for the same path, the three compiler identities equal
the manifest's, and every chain unit's recorded compile arguments carry
`-fverifiedos-typed` and `-Ifirmware/include` as the manifest's modes do; and
`boot-crypto verify` passes at that revision, which is what holds the manifest's
digests to the tracked files. The chain's streams are other translation units,
so no equality with the manifest's `assembly_sha256` values is claimed; the
freeze is of source bytes and compiler identity. A passing campaign closes
F-722 and, by executing the ML-DSA binding on the main-die composition, F-721.

### 9.14 Hosted execution

The campaign follows [the boot-crypto staged pattern](../../../firmware/crypto/README.md#hosted-target-campaign):
the contained compiler, whose license keeps it on the machine that holds it,
compiles the ROM, runtime, M-mode and kernel-stage units locally and a staging
command writes their streams, the signed images, the disposable public keys and
a manifest binding every input identity into a tracked directory; a workflow on
GitHub-hosted Linux verifies the staged inputs against the checkout, builds the
model, and runs one job per boot case and one job each for the main-die and the
watchdog groups, the main-die job depending on `cold-boot`'s job and taking its
R1 capture and R2 response as artifacts whose SHA-256 both receipts record; a
join composes the shard receipts into one, refusing a shard whose source,
model, manifest, compiler, period, instruction-limit or timeout identities
differ from the others' (F-718), listing unexecuted cases, and failing on any
failed case. Each job's per-case timeout and the execution step's limit are set
so that two SLH-DSA verifications at 5,000 s each, above the slowest
hosted case F-719 records, and one ML-DSA-87 verification at 600 s fit under the runner's six-hour cap with the model build;
a case that reaches its timeout supplies no verdict. Guest CI does not run the
campaign.

### 9.15 What the predicate does not decide, and findings

A passing campaign says the ROM, runtime, service and M-mode chain programs
compiled from this tree, the model's RoT devices and boot-control window, the
fixture kernel and this emulator agree with this section over the listed cases,
with the verifier identities frozen to M7.1f's manifest. It does not decide:
two harts running concurrently, the RoT waiting on the main die or the main die
on the RoT, which the run boundaries stand in for; the privacy of the RoT's
retained state, of the store windows, of the handoff record or of the mailbox,
and the RoT's authority over main SRAM, which the composition's authority
supplies and no harness shows; the authentication of the item-6 response beyond
that authority; any timing, including R-09-006b's figures; Q33's production
reset table and release points; the clearing of the attempt count by a booted
generation; the enrolled root set; the die's return to its reset vector after a
bite within a run; the static image and item 7; and that M4.4's kernel accepts
the handoff. Every report carries `milestone_acceptance: open` until the
integrator records the campaign's receipt against this section.

Findings this section raises, each recorded in
[the findings register](../../assurance/findings-register.md):

- **F-738.** The register does not say whether a recovery-generation boot under
  R-09-029's latch is charged by R-09-028's boot counting; this composition
  charges none and leaves the A/B state as read.
- **F-739.** RotFirmware.v's `Outcome` has no success (its gap c), and no entry
  names the act that clears the attempt count after a successful boot; this
  composition never clears it, so a device that boots successfully
  `chain.boot_attempt_bound` times reverts.
- **F-740.** The external slow clock's host period is a per-run-kind harness
  parameter; the positive path's window in host time is a function of it, and
  the stall and early-pet observations run runtime-only at a shorter period, so
  no run observes a bite after a complete ROM phase.
- **F-741.** The kernel-stage root is carried inside the measured M-mode image
  by this contract's selection, where R-09-036a places the roots that admit a
  generation in the RoT's enrolled set; no enrolled set exists in this
  composition and the RoT measures none.
- **F-742.** `vos_signature.h` carries no boot callback for ML-DSA and cannot
  change while the staged manifest binds it, so the chain binds
  `vos_mldsa87_verify_internal` over the signed prefix from outside the bound
  trees; a later staging may move the binding beside `vos_boot_slh256s_verify`.
- **F-743.** The item-6 binding check is a recomputation anyone holding the
  handoff record can perform; it decides that the response answers this request
  and not that the RoT produced it.
- **F-744.** The record handed to the kernel holds the generation register after
  item 5; the registers after item 6 reach the main die in the mailbox response
  alone, which the kernel stage does not read, so no consumer of the post-item-6
  registers exists in this composition.
- **F-745.** The emulator exits on the pump that asserted the die reset, so a
  run cannot observe the die at its reset vector or the ROM reading the bitten
  latch; the reset-vector observation is `watchdog_join.cpp`'s.
