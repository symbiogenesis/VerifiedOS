# Boot handoff contract

This is M3.5's contract: the acceptance predicate for the RoT's measured release
of the boot core, the order of that release, the boot image layout, the
measurement the release records, the cryptographic operations it calls, and the
kernel-entry and initial-capability handoff that M4.4's kernel consumes.

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
owns the constants the tables below state, and `run.py boot-handoff layout`
holds every table row here against it. The release is
[boot_verify.c](../../../firmware/rot/boot_verify.c) over
[keccak.c](../../../firmware/crypto/keccak.c); the M-mode stage is
[handoff.s](../../../firmware/mmode/handoff.s). The
[firmware README](../../../firmware/README.md) states what each file is and is not.

## 1. Scope

This contract owns the predicate (section 2), the release sequence (section 3),
the image layout (section 4), the measurement and the assignment of every
cryptographic operation the release calls (section 5), and the handoff layout
(section 6). It does not own the kernel body, which is M4.4's; the compiler, the
backend and `compiler-diff`, which are M1.2f's; the target path, which is M1.7's;
the reset table's release points (R-15-198a), which are Q33's; or the executable
SLH-DSA verifier, which section 5 assigns to M3.4. The real kernel joins at M7.1.

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
   records measurement items 1, 2, 3 and 5 in that order (section 5);
2. its image window holds exactly the payload followed by zeros, and its handoff
   record holds the fields of section 6 with values equal to its report and its
   inputs, with the image digest equal to SHAKE256 of the payload;
3. the golden emulator started on
   [verifiedos.json](../../../model/config/verifiedos.json) from exactly that
   window at `composition.load_base` and that record at
   `composition.handoff_base` retires its first instruction at the load base,
   retires the kernel entry, and reports `SUCCESS`, which the
   [kernel-entry fixture](../../../firmware/harness/kernel_entry_fixture.s)
   writes only after its ten checks of section 6 hold.

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
so the fixture's checks are load-bearing and release alone is not the kernel
entry predicate.

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
| `length-beyond-region` | declared length one past the region | `refuse-length` | none |
| `length-zero` | declared length 0 | `refuse-length` | none |
| `length-at-region` | payload zero-padded to exactly the region | `release` | `SUCCESS` |
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

The `development-part` row also holds R-09-025a's split: its generation register
equals the `valid` row's and its device register differs. The three injected
inputs are harness values, because the shipped RoT composition's seeded source
passes its start-up tests and its fuse holds production, so the probe cannot
produce them; each such row records its inputs in the report.

**What the predicate does not decide.** That the RoT hart executes the stage;
that any signature scheme verifies, the harness binding a fixture that section 5
describes; that M4.4's kernel accepts the handoff; any timing, including
R-09-006b's worst-case figure; A/B selection and boot counting (R-09-028); the
ROM's verification and measurement of the RoT runtime itself (item 4); and the
reset table's walk (R-15-198). A green run says the host-compiled stage, the
fixture signature, the fixture kernel and this emulator agree with this contract
over the listed cases, and every report carries `milestone_acceptance: open`.

## 3. The release sequence

R-09-006 fixes the ROM's sequence and R-09-002 that no stage executes before its
measurement is recorded. For the M-mode stage the release runs, in this order,
and stops at the first refusal:

1. Extend the device register with the lifecycle index (item 1), before any byte
   of the image is read (R-09-037); then the entropy verdict (item 2, R-09-006a)
   and the boot-target latch (item 3, R-09-029).
2. Refuse on a failed entropy verdict, which is a halt and consumes no boot
   attempt (R-09-006a); refuse where the lifecycle state accepts no root
   (R-09-036).
3. ReadHeader: refuse an input shorter than the header, then a wrong magic, a
   stage other than the M-mode image, a payload offset other than
   `header.bytes`, a payload length of zero or beyond `composition.region_bytes`,
   and an input shorter than the header plus that length. Every field is at a
   constant offset and none locates another (R-09-005).
4. CheckFloor: refuse a security version below the floor (R-09-005, R-09-030).
5. VerifySignature: refuse where no verifier is bound, and where the verifier
   does not accept the signature over `header.signed_bytes` under the lifecycle
   state's root (R-05-058c, R-09-036).
6. Place the payload in the image window and zero the rest of the window, then
   Measure: SHAKE256 of the placed bytes, so what is hashed is what the boot
   core will fetch, the core being held until the comparison. Refuse where it
   differs from the header's digest.
7. Extend the generation register with the digest (item 5) and compute the chain
   digest.
8. Write the handoff record (section 6), then release. Nothing follows the
   release.

Every refusal zeroes the image window, leaves the handoff window unwritten and
does not release. RomVerifier.v's `spec_order` is ReadHeader, CheckFloor,
VerifySignature, Measure, Execute, and steps 3 to 8 are that order with placement
inside Measure.

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
RomVerifier.v computes. The composition constants are the bring-up composition's
and not architecture: the attested devicetree owes their production values
(R-09-007, R-15-002b). The released core's first instruction is the load base,
which is a constant and not a header field, so no entry point is read from the
image.

RomVerifier.v's `demo_header` packs four fields, offset, length, hash and
signature, from offset 0. This layout keeps those four in that order and adds
the magic, the stage and the security version before them, the floor comparison
needing a version the image declares and the statement's `Header` having no
field for it. Section 8 records that difference.

## 5. Measurement and the operations the release calls

**Registers (R-09-025a).** Two 32-byte registers, zero at reset: the generation
register takes every extension the generation's source determines, and the
device register every extension the unit supplies. An extension is
SHAKE256(`VOS-EXT1` || register || item code || length as four little-endian
bytes || data) at 256 bits, and the chain digest is
SHAKE256(`VOS-CHN1` || generation || device) at 256 bits. The item codes are
RotFirmware.v's `all_items` order: 1 the lifecycle state, 2 the entropy verdict,
3 the boot-target latch, and 4 to 7 the four stages from the RoT runtime to the
static image. The release extends items 1 to 3 into the device register and
item 5 into the generation register. Item 4 is the ROM's measurement of the RoT
runtime, which precedes this sequence and which the harness does not exercise;
items 6 and 7 belong to the later stages.

**Operations.** Every cryptographic operation the release calls, and where each
one's executable form is:

| Operation | Called for | Executable form | Owner of what is missing |
| --- | --- | --- | --- |
| SHAKE256 | the payload digest, each extension, the chain digest | [keccak.c](../../../firmware/crypto/keccak.c), functional layer only | the target build (M1.7) and the constant-time layer (R-05-062, R-05-067) |
| SLH-DSA-SHAKE-256s verification | the signature over the signed bytes | none: the harness binds a fixture | M3.4, as an executable verifier under FIPS 205 with the parameter set RomVerifier.v states |
| Counter read | the floor, counter 0 of R-10-013's enumeration | the RoT composition's counter window | n/a |
| Entropy draw | none: the release reads the start-up verdict and draws nothing | n/a | n/a |
| ML-DSA verification | none at the ROM (R-05-058c) | n/a | the stage that verifies the core kernels |

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
The bring-up composition declares no sealing grant type, so neither object-type
root has an admitted derivation and both are cleared (sealing-bootstrap.md
section 2).

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
| `record.entropy_ok` | 24 | 8 | 1 |
| `record.boot_target` | 32 | 8 | the latch |
| `record.security_version` | 40 | 8 | the released image's |
| `record.floor` | 48 | 8 | the floor at the decision |
| `record.load_base` | 56 | 8 | `composition.load_base` |
| `record.payload_length` | 64 | 8 | the released payload's length |
| `record.image_digest` | 72 | 32 | SHAKE256 of the placed payload |
| `record.generation` | 104 | 32 | the generation register after item 5 |
| `record.device` | 136 | 32 | the device register after item 3 |
| `record.chain` | 168 | 32 | the chain digest |

| Constant | Value | Meaning |
| --- | --- | --- |
| `record.bytes` | 256 | the record's extent and `c11`'s length |

**The initialization descriptor** (`c12`) holds, as doublewords, the magic
`VOSINIT1`, version 1, the hart identity, a composition identity, the planned
context count and the first successor's index, then two zero words. It is part
of the measured image.

**What M4.4 consumes, and what it must check before its first dispatch.** The
register state above at its first instruction, with no return to firmware. From
`c11` it reads the record's magic and version and may read the measurement for
its own records; the record's bytes are the RoT's, and their authentication is
the measured chain's, not the capability's. From `c12` it must reject a missing
descriptor, a wrong magic or version, a hart identity other than `mhartid`, a
composition identity other than its own, and an initialization with no planned
successor, as purecap-abi.md section 7 requires; the fixture checks the magic
and the hart identity only. From `c10` it takes one tagged member per declared
extent. MTCC and MTDC are installed; MEPCC holds no continuation. The partition
contexts and the schedule table are M4.4's to construct and check (purecap-abi.md
gap k).

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
`run.py boot-handoff layout` holds the tables in sections 4 and 6, the case table
in section 2 and the assembled image against `vos_boot.h` and the harness's case
list, on either lane.

## 8. Open joins and findings

- **The RoT hart does not execute the release.** The stage runs host-compiled
  until the purecap backend (M1.2f) and M1.7's target path build it for the RoT
  composition.
- **No executable SLH-DSA-SHAKE-256s verifier exists.** Section 5 assigns it to
  M3.4; until it lands the success case is conditional on the fixture.
- **The model has no boot-core release door and no boot-target latch door.**
  The emulator composes one hart per run, so release is realized as starting the
  main-die run, and the latch (R-09-029) is a harness constant. Where the reset
  table's release points live is Q33's (R-15-198a).
- **RomVerifier.v's `Header` carries no security version.** Its floor comparison
  reads a version the statement's header has no field for; this layout adds
  one, with the magic and the stage.
- **The floor is established in the same power-on.** The emulator retains no OTP
  state between runs, so the probe advances counter 0 to the floor it reports.
- **The measurement encoding is this contract's selection.** R-09-025a fixes the
  two registers and R-09-002 that every stage is measured; no entry fixes the
  extension function, the item encoding or the chain digest, and RotFirmware.v
  takes `extend` and `item_code` as fields. Section 5's encoding is the bring-up
  selection.
- **Item 4 and the later stages are not measured here.** The ROM's measurement of
  the RoT runtime and the core-kernel stage's verification remain owed.
- **A/B selection and boot counting are not exercised** (R-09-028, R-09-029).
