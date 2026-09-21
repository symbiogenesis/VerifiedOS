# Sealing-authority bootstrap contract

This contract supplies the reset-to-installation authority needed to construct
`Handle(h)` in the [source-value contract](compiler-source-values.md) and the
mixed handle arguments of the [purecap ABI](purecap-abi.md#4-calls-and-returns).
It specifies a prerequisite of M1.2d-ii and M1.2g-ii. Executable measured boot,
the authenticated installation producer and their system joins remain M3.5's
obligations. The reset model supplies the two object-type grants below; the
compiler prerequisite also requires the installation and execution evidence in
section 3.

## 1. Authority classes and existing state

[R-15-007p](../../spec.md#r-15-007p) and
[R-07-006](../../spec.md#r-07-006) govern memory authority.
The execute-side and store-side roots authorize their composed text and physical
partition extents. A sealing authority instead authorizes object-type names:
its bounds and cursor select members of the frozen, nonreserved otype space.
It has no memory-access permission, so its numeric bounds do not delegate low
physical addresses or enlarge any core's memory partition.

The frozen four-bit otype space has thirteen nonreserved values, 0 through 12.
Types 13, 14 and 15 are the backward edge, forward edge and unsealed markers.
The reset authority set contains the following additional tagged, unsealed
capabilities in the existing merged register file:

| Reset location | Authority | Expanded permissions | Encoded permissions | Base | Top | Cursor |
| --- | --- | --- | --- | --- | --- | --- |
| `c2` | Mint composition-declared grant types | `Global` and `Permit_Seal`, `0x201` | 30 | 0 | 13 | 0 |
| `c3` | Redeem composition-declared grant types | `Global` and `Permit_Unseal`, `0x401` | 31 | 0 | 13 | 0 |

The existing `c1` store-side bootstrap and execute-side reset PCC retain their
current fields and roles. Every other general register retains its existing
reset value. No register is added, widened or reserved during ordinary
execution; `c2` becomes the ABI stack pointer after the bootstrap authority is
consumed. No new CSR, instruction, permission code, configurable permission
bitmap, runtime root selector or tag-setting software operation is introduced.
This is an explicit change to the initial contents of two existing GPRs under
[R-15-007i](../../spec.md#r-15-007i), not a new register bank.
The same architectural reset action reinstalls these values on every reset;
ordinary traps and `mret` do not recreate them.

`Permit_Seal` and `Permit_Unseal` remain in separate lattice elements, preserving
[R-15-007o](../../spec.md#r-15-007o). Neither root carries Load,
Store, LoadCapability, StoreCapability, StoreLocal, Execute or ASR. Neither can
be derived from the existing data or execute roots: their absence from those
roots is preserved, and integer bits or image bytes cannot supply the missing
tag or authority. Reset is the explicit origin of the two new derivation
forests.

## 2. Composed installation and lifetime

The measured firmware is the first executing principal and the only initial
holder of these GPR authorities. Before reusing `c2` as a stack pointer, it may
move the roots into firmware-private registers or storage named by the boot
plan. Every copy remains part of the installation inventory and cleanup proof.

The immutable composition records each grant identity, selected nonreserved
otype, exact grant-object storage extent, permitted payload authority, mint
holder and redeem holder. It rejects an out-of-range or reserved type, an
undeclared holder, an ambiguous identity, and any overlap or alias prohibited
by the grant plan. A numeric otype alone is not a grant identity; the exact
object address and the authenticated grant-slot declaration also bind `h`.

For each admitted type `t`, firmware derives the appropriate authority only by
monotone operations from the matching reset root: cursor `t`, exact bounds
`[t,t+1)`, and the same Seal-only or Unseal-only permission set. These type-space
narrowings carry their own authority role and exactness evidence, without
pretending their coordinates describe a physical memory region. A request to
narrow beyond `[0,13)` or to add the opposite permission is rejected by the
installation checker and exercised as a target control.

Only the declared kernel mint path receives the selected mint authority, and
only the declared kernel redemption path receives the selected redemption
authority. They occupy distinct protected slots. A receiver of a sealed handle
receives neither authority. Installed-holder checks quantify over every copy
and transitive capability load path, including boot scratch, kernel tables,
compartment globals, code-local import tables, stacks and trap bootstrap data.
An unsealed usable ASR capability remains kernel-exclusive under the existing
firmware sealing-aware refinement; these roots confer no ASR themselves.

Firmware seals the actual admitted grant object using `CSeal` and the selected
mint authority. A handoff observation must show the resulting tag, nonreserved
otype, bounds, cursor and payload permissions, and its installation must bind
the same grant identity as the source `Handle(h)`. `CSealEntry`, a return sentry,
an integer slot number and a capability-looking byte sequence do not construct
a grant handle. Typed moves, declared slot loads/stores and admitted arguments
or results preserve `h`; source arithmetic, dereference, reinterpretation and
implicit unsealing remain refused.

Before ordinary kernel or compartment execution, firmware clears all broad
`[0,13)` bootstrap roots and all temporary copies, including their tags. It
retains only the composition-selected, exact-type authorities in their declared
protected slots. The computed final GPR clear covers the bootstrap registers;
private scratch cleanup covers any stored copies. Timer restart consumes the
installed restricted tables and never recreates or retains the broad roots.
Firmware then follows the existing quiescence and kernel-handoff contract.

## 3. Required executable and proof evidence

Implementation is accepted only when the following evidence agrees over the
same source/model/profile/composition/image closure:

- Reset tests decode both full tagged capabilities and establish exact `[0,13)`
  bounds, cursor 0 and permission masks `0x201`/`0x401`. They check all other GPR
  reset values and the unchanged data/PCC roots.
- A machine-checked root-role witness admits these as otype authorities,
  separately from memory and code roots. Derivation proofs cover exact-type
  bounds, permission restriction, actual `CSeal`/`CUnseal` behavior and preserved
  origin. No axiom or assumed tagged-image initialization supplies a handle.
- A real firmware image derives a selected type, mints a nonreserved sealed
  grant, installs the exact declared slots, clears every broad root copy and
  hands off. The installed graph and observed full words agree with the source
  handle identity and required role. A ten-argument mixed boundary carries the
  actual handle through register and stack slots, including nested use.
- Controls attempt Seal with the Unseal root, Unseal with the Seal root,
  reserved/out-of-range type selection, forged handle bytes and unauthorized
  holder installation. Actual executions must exhibit the profile's defined
  tag-clear or fault behavior, and source cases outside the authoring interface
  must be refused before emission.
- Boot scratch retention and missing-clear mutants are detected by exact
  tag/data observations. The boundary's existing masks, PCC localization,
  malformed targets, nonretention and timer cleanup populations remain required.

These checks establish the bounded producer and compiler prerequisite. They do
not establish signature verification, the RoT measured chain, complete grant
revocation, physical reset circuitry or M3.5 completion.
