# Fixed native packages

Fixed packages are the default construction boundary of R-13-028. A native
generation maps already constructed package objects, then checks its concrete
layout and authority graph. It does not lower unchanged packages again. The
[production admission handoff](production-admission.md) still owns the actual
TAL/CIC checkers and installed-object correspondence; this contract supplies no
replacement proof checker or trusted compiler.

## Artifact identity and construction

A fixed artifact binds the exact source closure, capability/interface and
resource contract, target/specification/model/descriptor versions, immutable
code/rodata, writable initializer, derivation template, correspondence theorem
and required hyperproperty objects. Its identity hashes a canonical manifest
containing the digests of the actual output objects. A hash of producer inputs
alone is a build lookup key, never the content identity of a nondeterministic
output. Transport paths do not establish either identity or admission.

Construction performs dead elimination against the package's declared exports,
interrupt and scheduled roots, and package-local optimization. A changed source,
contract, context, initializer or proof is a different artifact. A cross-package
optimization may construct an explicitly named replacement artifact with fresh
evidence; ordinary installation never rewrites a reused artifact to perform it.
The base-image and checker reproducibility obligations retain R-13-026's scope.
Transparency names commit to source and the interface/resource contract;
publishers may additionally commit the realized artifact hash.

The host artifact schema is separate from the existing source-inventory schema.
It carries data, not an admission-success flag. Readers verify every object
digest and declared byte length, strict field shapes, bounded integer ranges,
region alignment, permissions, relative extents and exported entry offsets.
Code cannot be writable. Initializers contain untagged bytes, never stored
authority. Proof objects remain in the store and outside executable memory.
Missing, malformed, substituted or corrupt objects refuse reuse; the store does
not repair a corrupt object silently under its existing identity.

## Composition without rewriting

The first executable placement path translates one package-relative region
geometry by one base. Code-to-data displacement therefore stays fixed. Every
region moves by that same translation, with no relocation, reassembly or producer
invocation. The package contract fixes its span, alignment, region permissions,
memory classes and entry/export offsets. Composition rejects overlapping spans,
address overflow, incompatible class placement and entry points outside code.
An independently movable region needs the stronger capability-relative ABI and
correspondence premise; a claim in metadata does not establish it.

The host composer emits ordinary producer-side ELF as interchange and checks the
actual loadable bytes and permissions against each placed package. This does not
put an ELF reader in the target TCB or turn a host image into production admission.
Package bytes must be unchanged at two valid translated layouts. The existing
assembly-based harness remains a bring-up producer rather than the native
installation policy.

Each generation still obtains a new concrete TAL binding, monotonic capability
wiring, fresh modular linkage/instantiation connecting reused correspondence to
the exact installed image and wired capabilities, handler graph,
placement/memory-initialization check, schedule and global resource checks,
signed generation root and A/B transaction. Removing a package
does not execute its code. Activation remains the next boot under R-13-001a.

## Reusing checked proofs across generations

Reusable evidence is the current admitted generation's authenticated checked
set. The trusted admission adapter supplies that root from admitted state; an
artifact, fetched cache file, untrusted composer or candidate-generation signature
cannot supply its own trust anchor. Restoration verifies the complete checked-set
bytes against that root. An unauthenticated or mismatched prior set refuses.

A trusted current-generation checker/policy adapter supplies the expected
checking context; an untrusted request cannot select an older policy merely to
hit a prior entry. A reuse key binds the exact artifact and all package-local
proof objects to the contract, source closure, spec/model/profile/decoder versions, checker identity,
CIC environment, assumptions, tier, policy and resource context. Equality is
exact; changing any member requires the actual package proof checker. A matching
authenticated entry avoids only the package-local correspondence/hyperproperty
check. Concrete-layout TAL and all generation-level checks always run again.
The adapter rehashes the package objects and checks their binding before reusing
an entry. No proof search is part of ordinary install.

New successful package checks are staged privately. A failed proof, layout,
wiring, global check or interrupted generation publishes no successor checked
state. Only a completely checked generation supplies the successor root, which
the existing authenticated generation transaction commits with its other roots.
The coordinator's returned candidate state is not independently admitted state.
The existing anti-rollback and recovery rules also apply to this root. Missing
checker or trusted prior-root interfaces refuse; Boolean success metadata cannot
stand in for either.

## Implementation and acceptance

The executable increment contains a strict artifact reader/store, byte-preserving
placement and image join, a package-local proof reuse coordinator, and a public
host composition command. The coordinator uses explicit trusted checker/current
state interfaces; fixture adapters are declared fixtures, and the existing
production checker-unavailable refusal stays until its actual consumers land.

Independent controls must demonstrate:

- Build a native PC-relative fixture once, store it, and compose the same actual
  bytes at two translated layouts without invoking its producer again.
- Change one package in a multi-package roster: unchanged artifact bytes and
  authenticated package-local proof verdicts are reused across a simulated
  reboot; only the changed package invokes the package checker.
- Changes to source, contract, code, initializer, proof or any checked context
  invalidate reuse. Corrupt store bytes, forged or unanchored checked state,
  missing objects, invalid shapes, overlap, overflow and permission substitution
  refuse.
- Fresh TAL/wiring/global checks run for every generation. Failure or interruption
  preserves the old state and emits no admitted successor. Missing actual
  checker interfaces never become production acceptance.
- The emitted image contains the declared package bytes at the declared physical
  load addresses and permissions. Producer-side source/proof metadata supplies
  no executable or capability authority.

Focused host tests and Python checks supply local feedback. Host CI on Windows
and Ubuntu and all Guest lanes are user-managed under the
[validation handoff](../../../AGENTS.md#tool-execution-and-validation). Native
checker/producer qualification and end-to-end resident execution retain their
existing owners. Q31 measures capacity, timing and install costs against optional
roster-wide optimization; its open measurements no longer commission mandatory
re-lowering of unchanged packages.
