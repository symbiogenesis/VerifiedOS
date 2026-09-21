# Modeled device register declarations

U-10 supplies [the declaration](../../../interfaces/device-registers.json),
[its generator](../../../tools/vos/device_registers.py),
[Gallina accessors](../../../proofs/DeviceRegisters.v) and
[SystemVerilog constants](../../../rtl/generated/device_registers_pkg.sv).
Its acceptance predicate is the register-language slice in
[the prerequisite map](../../assurance/unassigned-proof-map.md).
R-05-083 owns field layout and generated access; R-05-138 owns the capability
through which a later HAL reaches the device; R-15-002b owns physical placement.

## Declaration and scope

Schema 1 uses a `platform` object with exactly the aperture keys discovered by
shape in the primary composition: an object with boolean `supported` and integer
`base`. Disabled declarations remain described. A separate `harness.htif` entry
covers the diagnostic port that the model enables externally. Neither object
copies a physical base address.

Each device states its kind and rationale. A `registers` device lists relative
eight-byte-aligned register offsets, access modes, array-index domains, fields,
and optional overlapping transfer views. Fields have a name, least-significant
bit and positive width within a 64-bit word. Fields in one register may not
overlap; views explicitly name subdivisions or transfer aliases. No view may
extend outside the declared fields. Unused bits are absent from the field set.
An argument-free `command` has no field. Array domains are descriptive model
references; this slice emits no array address arithmetic or bounds-checking HAL.

The memory sequencer declares that CPU accesses are refused. The boot ROM is
memory rather than a register file. The UART has no Sail register reader;
[the existing wrapper generator](../../../tools/vos/device_regs.py) and
`python tools/run.py rtl devicescheck` retain its upstream register contract.
This declaration does not substitute for that check or assert a UART Sail model.
The block device's delegated reader and writer are included alongside the direct
readers in `platform.sail`.

## Model correspondence and changes

Every field supplies a binding to a named Sail function, type or constant from
the existing machine-readable bundle. Templates substitute the declared width,
shift, high bit or mask into the expected source fragment. Register bindings
likewise hold relative offsets to their source constants or decode conditions.
Missing definitions and mismatches refuse emission. Source hashes are checked
against the current model before a bundle is used.

The declaration also carries a co-read record: `reviewed_functions` fingerprints
the complete modeled MMIO reader and writer bodies and their dispatch functions;
`reviewed_layout_sha256` binds those judgments to the complete declaration.
The reviewed function roster must equal the source's MMIO roster, including the
delegated block-device functions and indexed-door helpers. A new branch, reader,
or field omission therefore refuses even if every remaining fragment still
matches. Comments and whitespace do not change function fingerprints.

Changing either side requires reading the complete changed function and its
declaration, checking that every returned or consumed register field appears
once, checking each explicit view, then recording both fingerprints. This is a
semantic review act. The emitter and `check --fix` cannot refresh review evidence.
The record preserves the reviewed coverage judgment; it is not a verified Sail
parser or a proof of semantic correspondence between Sail and Gallina.

## Generated contract and verification

`python tools/run.py device-registers emit` validates every input before writing
the two artifacts. `python tools/run.py device-registers check` validates the same
inputs and compares exact UTF-8 bytes. K-88 runs both emitters as host rows.
Duplicate JSON keys, unknown schema members, absent or extra devices, duplicate
registers or fields, overlap, out-of-word fields, stale bundle sources and stale
review records are findings, with no partial model interpretation.

The Gallina declaration specifies extraction mathematically as division by
`2^shift`, followed by remainder modulo `2^width`. Each emitted accessor uses
binary-natural right shift and bitwise mask with concrete literals. Its theorem
quantifies over every input word and equates that implementation with the declared
projection. The common theorem uses the standard library's checked shift and mask
identities. The proof gate audits assumptions and rechecks the generated module
in the kernel. No axiom or admission is introduced.

The RTL package emits the same relative offsets, shifts, widths and unshifted
masks. `python tools/run.py rtl lint` checks its SystemVerilog syntax. Behavioral
tests seed a shifted generated constant, a changed model field, omitted fields,
new apertures, invalid overlap and stale source coverage. Generated-byte checks
must reject an artifact-only shift; model correspondence must reject a source
shift even after the bundle and source-review fingerprint are refreshed.

These are pure value projections. They create no capability, perform no MMIO,
and prove no initialization, ownership transfer, timing, lifecycle, or hardware
refinement theorem. U-11 supplies HAL contracts; later implementation work must
derive device access from the root capability passed at construction.
