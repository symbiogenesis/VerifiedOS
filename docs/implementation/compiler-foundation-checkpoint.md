# Scalar compiler implementation checkpoint

The contained compiler carries the selected scalar C profile through the real
compiler passes to capability-aware assembly and composed Sail execution.
[M1.2g-ii, M1.2d-ii and M1.2e-ii](implementation-checklist.md) own the source,
lowering and narrowing joins. Their acceptance uses the
[source-value contract](contracts/compiler-source-values.md),
[kind interface](contracts/compiler-kind-interface.md),
[scalar ABI](contracts/purecap-abi.md) and
[sealing bootstrap](contracts/sealing-bootstrap.md).

Compiler sources, generated products and detailed replay receipts remain in
the local contained repository under the
[existing incorporation decision](../../THIRD-PARTY.md#compcert-and-secomp).
This document conveys their implementation status and evidence references.

## Source values

`riscV/SourceValues.v` relates abstract pointers, scalar values, explicit null
and opaque handles to concrete capabilities supplied by the selected composition
or obtained by checked derivation. Bounds, permissions, locality, lifetime and
role constrain the actual supplied value. Cursor changes, scaled pointer
arithmetic, comparisons, permission restriction, sentry calls and serialization
have inhabited witnesses and rejected neighboring cases. Explicit address
observation returns an integer and gives it no authority.

`riscV/SourceMemory.v` connects actual CompCert block-memory loads and stores to
the placement and physical byte/tag relation. Capability payloads use whole
tagged cells. Scalar writes clear intersected tags even when their data bytes
are unchanged; adjacent cells retain their contents. Typed copies preserve the
declared fields through disjoint copying or a complete pre-copy snapshot.
Initialization, live placement, effective type, alignment and source validity
remain explicit premises of the admitted operations.

`riscV/SourceCodeValues.v` binds code values to resolved function identity,
signature, generation, live code extent and entry. Ordinary code, forward
sentries and backward return capabilities have distinct roles. The selected
indirect-call path requires a closed, compatible callee set; a numerical code
address is insufficient.

`riscV/SourceHandleValues.v` binds the nominal source carrier to a declared grant
identity and a capability minted by actual sealing derivation. Minting records
the payload and sealing-authority origins separately. Typed block-memory and
physical stores, copies and reloads preserve the sealed value. Integer and byte
overlays cannot manufacture that relation. The source profile refuses handle
arithmetic, dereference, observation, reinterpretation and implicit unsealing.

The real source campaign interprets the generated C programs, compiles them,
assembles their output and observes the resulting Sail executions. The
destructive campaign starts with an actual compiled pointer spill. Every
intersecting byte write, an unchanged full-width scalar overwrite and scalar
restoration must execute, clear the tag, preserve the adjacent capability and
fault only at the later authority use. Assembly failure is not a killed mutant.

## Kinds and source types

The source adapter preserves pointer payloads before `Cshmgen` loses their
distinction from equal-width scalar chunks. Mandatory typed operations and
authority roles travel through the actual Csharpminor, Cminor, selection, RTL,
allocation, linearization and stacking path to the Mach emitter. Each supported
stage checks its inputs and outputs; missing kinds receive an explicit refusal.
The driver retains stage dumps and source/site records for independent checking.

The emitter uses capability moves, cursor operations, `lc` and `sc` for the
corresponding values. Scalar payloads retain scalar operations. Frame layout
accounts for capability spills, saved stack authority and return links, incoming
stack arguments and outgoing arguments beyond the register set. Large argument
offsets use the declared scratch register. Ordinary functions reuse their
bounded domain stack rather than narrowing every frame.

The selected source profile supports fixed-layout aggregates, typed disjoint
copying, snapshot copying, explicit null constants and compatible object-pointer
conversions through `void *`. Raw pointer/integer conversions, capability byte
inspection, untyped overlays, unrepresented primitive results and unsupported
signatures fail before emission. Floating, vector and variadic production
conventions retain their existing milestone owners.

The `verifiedos-scalar-source-v1` profile supplies a selected `stdint.h` with
fixed-width integer types and limits. It omits pointer-round-trip typedefs and
limits, diagnoses packages requesting that contract, and records the selected
header hash in the source receipt. Constant-expression nulls use the source
integer semantics and explicit layout inputs. Runtime zero and reconstructed
addresses remain refused. Explicit `cgetaddr` observes the composed cursor;
permitted narrowed views retain their source identity for pointer equality.

Primitive lowering checks the exact operation, signature, profile and immediate
operands. `fence.t`, `vmclear`, capability observations and derivations retain
their selected semantics. Capability-producing primitives need a represented
result; a possible non-null tag-cleared result is an unsupported lowering.
Privileged special-register operations require the kernel profile.

The boundary producer composes real kernel, service and leaf functions. Its
ten-argument nested calls transport borrowed objects and sealed handles through
register and stack arguments. Protected tables name code, stack, return and
grant authority. The producer localizes PCC, checks masks and active frame
identity, stages typed arguments, and clears the retiring stack and private
frame before publishing the caller. Timer restart clears all reserved stacks
and private storage independently of an interrupted phase, replaces the old
continuation and uses the checked modeled release schedule.

The cleanup proof quantifies over arbitrary initial physical bytes and tags.
It establishes the finite loop's exact iteration count, zero data and cleared
tags throughout each selected span, preservation outside that span, and safe
restart after any interrupted prefix. The concrete certificate binds those
loops, normal returns and terminal failure paths to the final image. Its
machine correspondence, installed authority and confined return-copy premises
remain explicit; the theorem does not provide a universal Sail simulation or
a physical timing bound.

Reset supplies separate Seal-only and Unseal-only roots in existing registers.
Firmware restricts them to the selected nonreserved type, installs separate
protected slots, seals the declared grant object and clears all broad-root
copies before handoff. Grant identity includes the declared object and rights;
the object-type number alone does not establish identity or freshness.

The installation consumer compares the actual boot graph with an independently
composed graph and checks the public sealing-aware handoff relation. Complete
boundary snapshots include registers, special registers and tagged memory.
Their graph closure covers all potential capability-load chains through each
fixed snapshot, including loads the observed program did not take. Borrowers
cannot reach private kernel data or type authority. Privileged return edges
must have actual hardware-link ancestry and an admitted continuation site.
These finite snapshot results do not establish arbitrary future-write safety.

The retirement supplement binds each selected return to its actual hardware
link and declared pop point. At every retained checkpoint after that pop, the
complete holder graph and its potential capability-load closure contain no
recorded descendant or identical-word copy of the retired authority. Cursor,
bounds and permission changes do not evade the ancestry check. The outer
continuation remains live until its own return. This establishes the selected
execution's retirement result; it does not replace the general cleanup theorem's
confinement and machine-correspondence premises.

## Narrowing provenance

`riscV/NarrowingProvenance.v` and the emitter's mandatory consumer use the total
plan-relative representability decision. Independent composition and source
layout inputs select each physical region, request, operand and authority
origin. Type-space authorities use a separately identified coordinate space.
They cannot satisfy a physical-memory request merely because coordinates match.

The final-byte checker decodes every executable word and joins every narrowing
in both directions to the selected operation and request. Missing, duplicate,
orphaned, stale and invalid obligations refuse acceptance. Code-local data cells
are excluded from instruction decoding only when independent declarations and
their actual initializers account for them. Unexplained executable bytes and
writes to instructions are rejected.

Runtime ancestry begins at the exact modeled reset roots and follows checked
derivations, register moves, special-register transfers and intact tagged
stores/loads. Equal numeric words never create provenance. The semantic sealing
and unsealing relations retain both parents; the executed Handle population
checks minting, transport and storage, without a `cunseal` execution. Generated
Gallina receipts check the actual full capability words, addresses and derivation
equations. Compiler-origin narrowing has its own
nonempty positive; firmware sites do not stand in for that case.

## Evidence and continuation

The contained `test/verifiedos-source-values/`, `test/verifiedos-source-handles/`,
`test/verifiedos-compiler-integration/`, `test/verifiedos-boundary/` and
`test/verifiedos-narrowing-provenance/` directories own the replay tools,
populations, immutable inputs and detailed receipts. Native outputs remain in
their assigned guest lanes. Receipts bind source, compiler, model, profile,
composition, image and observation identities as applicable and retain direct
command verdicts and input-stability checks.

The integrated compiler build is incremental over a source-verified retained
foundation seed. The complete proof, extraction and compiler build succeeds.
The source-value, source-memory, code-value and Handle modules also pass their
combined independent kernel and inherited-assumption audit. New local proof
results introduce no additional assumptions.

The source-profile, typed lowering, installed graph, return-copy retirement and
cleanup joins implement the selected bounded scalar composition. The final
recursive retirement kernel passes; hosted validation remains pending at
publication. Their exact receipt identities and qualification limits are recorded in the
[source and memory landing](completion-log.md#m12g-ii-integrate-capability-values-with-source-operations-and-emitted-memory-traffic),
[lowering landing](completion-log.md#m12d-ii-realize-typed-frame-call-and-primitive-lowering)
and [narrowing landing](completion-log.md#m12e-ii-enforce-plan-provenance-at-every-emitted-narrowing).
M1.2f continues to own the complete backend acceptance loop, including the
Gallina component's Wasm-to-purecap comparison. This implementation does not
supply a whole-program compiler-pass simulation, universal Sail refinement,
arbitrary future-write or repeated-activation safety, physical timing proof or
authenticated measured-boot chain. Those obligations remain with their
existing owners.
