# Library callbacks and runtime teardown qualification

This contract scopes Q47 in [the plan](../../../PLAN.md#q-assessment-actions).
It qualifies existing native safety and lifecycle obligations; it introduces no
new TAL premise class, semantic anchor, assurance tier or guest guarantee.
Implementation starts after this contract and Q47's predicate are committed.

## Scope and existing obligations

The [FORGE analysis](https://forge-blog.github.io/posts/rust-std-memory-safety/)
describes unsafe library code that assumes calls cannot unwind, trusts a
caller-supplied implementation's answers, or relies on shared Unix runtime state.
The [critique disposition](../../background/critique.md#rust-library-soundness-and-runtime-boundaries)
distinguishes architectural exclusions from unfinished qualification.

| Boundary | Existing owner | Qualification needed |
| --- | --- | --- |
| Native panic and nonlocal exit | [R-05-100](../../spec.md#r-05-100), native TAL soundness | Abnormal native exit cannot unwind into cleanup or resume the abandoned reaction. |
| Callback results and library invariants | [R-05-031](../../spec.md#r-05-031), [R-13-012](../../spec.md#r-13-012), library refinement and native admission | Safety holds for every callback behavior permitted by its checked contract, including inconsistent answers. |
| Dependencies and generated glue | [R-05-080](../../spec.md#r-05-080), [R-13-013](../../spec.md#r-13-013), certifying compilation | The actual linked closure satisfies the target's source and binary obligations; an application's source lint certifies no dependency. |
| Retirement and safe reuse | [R-08-004](../../spec.md#r-08-004), [R-16-001](../../spec.md#r-16-001), kernel, pool and supervisor | All remaining users are discharged before backing is zeroized and reused. |
| Wasm and host bindings | [R-14-013a](../../spec.md#r-14-013a), engine and application-host refinement | Guest exceptions stay in guest semantics; stale handles and reentry cannot break native invariants. Guest linear-memory object safety is excluded. |
| Host development and extracted execution | [Q10](../../../PLAN.md#q-assessment-actions), host-product assurance | Host Rust, libc, OS and tooling are outside the target exclusions; a host run establishes no target admission or teardown theorem. |

Native source correspondence can faithfully preserve a faulty library. CHERI
bounds do not validate UTF-8, collection lengths, initialization, aliasing or
lifetime protocols. Accesses within one collection's backing can violate its
logical length while staying inside a capability. R-13-012's Tier-2 scope also
leaves general arithmetic correctness outside its default certificate; library
safety cannot silently depend on that omitted property.

## Qualification record

Q47 produces a revision-bound boundary inventory from the actual package,
composition and linker inputs. Each entry names the exported operation, all
reachable implementation artifacts, caller-controlled calls and results, mutable
state and backing, normal/error/abort transitions, proof endpoint and owner, and
executable positive and negative controls. Include linked `core`/`alloc`/`std`
fragments where used, the capability libc, allocator and collection libraries,
compiler helpers, generated wrappers, HAL calls and guest imports. Do not infer
coverage from a crate name or from an empty search for `unsafe` in app sources.

Keep artifact membership derived from its owning package/build input, not a
second hand-maintained dependency list. Missing members, contracts, native
derivations or theorem connections leave the corresponding entry unqualified.
The [production-admission handoff](production-admission.md) owns the real
checker prerequisite; a metadata record or claimed certificate digest is no
substitute. Bootstrap checker binaries retain their separate assurance route
and do not admit themselves through this inventory.

## Callback safety predicate

For every exported library operation, the implementation preserves native
memory safety for every argument and callback execution allowed by its checked
input contract. Functional claims such as sorted order may have stronger
preconditions, but safety cannot acquire an unchecked comparator law, reported
length, stable borrow, encoding claim or allocator promise as a hidden premise.

- Bind validation and use to the same returned object and live ownership.
  Repeated calls may return different slices or lengths. Two-pass operations
  either retain validated immutable views or validate each result against the
  actual remaining destination before use. Cover growth and shrinkage,
  including the first element and empty/single-element cases.
- Validate an index or search range against the exact source object it
  addresses, with ordered endpoints, checked arithmetic and required encoding
  boundaries. A range from another string is not evidence about this one.
  UTF-8/ASCII validity comes from a checked constructor or theorem, or explicit
  validation; bytes plus a safe method's claim do not establish it.
- Collection length, initialized prefix and drop obligations agree at every
  reachable boundary. Capacity arithmetic remains safe under lying iterator
  lengths and allocation failures even where Tier 2 omits a general range
  obligation. A destructor cannot observe uninitialized elements or spend
  ownership twice on normal return or explicit error.
- Callbacks, including ordinary destructors and allocator hooks where present,
  run only with invariants and ownership sufficient for every permitted call
  back into the library. Reentry is either rejected through checked ownership
  and call rules or proved safe; finite callee enumeration establishes neither
  a state invariant nor exclusive access. Reentrant exit and recursive
  destruction receive explicit cases even when a callback returns normally.
- Stronger semantic postconditions are discharged by checked library/callback
  proofs or validation at the boundary. They are not added as arbitrary TAL
  premises: the [TAL language](../../languages/typed-assembly-language.md)
  retains its existing closed premise classes. Missing expressiveness is a
  finding for the language and proof owner before implementation proceeds.

## Abort and retirement predicate

Qualify allocation failure, explicit close, panic/abort, callback failure and
slot overrun at each publication and ownership-transfer boundary. Native
abandonment executes no user cleanup on the abandoned frames, performs no
nonlocal recovery into them, and never relies on a destructor to return a pool
chunk or device loan after abandonment. Ordinary successful-path drops remain
subject to the callback predicate above.

Tie close and restart to the existing holder inventory and completion barrier:
running harts, saved contexts, registered entries/handles, peer capabilities,
queued replies and outstanding DMA retain their owner's retirement duty.
Disabling a registration in the calling context does not retire another
context's reference. Missing completion retains quarantine and refuses reuse;
test this refusal before zeroization or publication of replacement backing.
Prove the lifecycle relation on the actual kernel/pool/supervisor interfaces,
including cleanup of partially initialized ownership and a second close/exit.
Do not add POSIX signal stacks, mutable `environ`, `atexit` or TLS cleanup to
reproduce the article's mechanism. Audit their absence in the target closure
and qualify the explicit capability-based replacement instead.

Wasm exceptions and resumable guest operations do not unwind native frames.
Host imports use explicit bounded handles, ownership and failure results; cover
guest trap/cancel, nested host calls where permitted, memory growth invalidating
a borrowed view, and a late reply after instance retirement. The
[application-host](application-host.md) and [Wasm execution](wasm-execution.md)
contracts retain their complete-language, resource and confinement obligations.
Guest object overflow, stale offsets and invalid guest-library representations
remain possible inside linear memory; stronger protection requires the concrete
consumer decision R-14-013a already calls for.

## Acceptance and evidence limits

Q47 closes only when the real closure inventory has no unexplained boundary,
each entry has its checked safety/lifecycle connection and an accepted owner
join, and generated adversarial controls exercise the predicates above against
the exact native artifacts. Include changing borrows, false iterator lengths,
inconsistent comparators, foreign-string ranges, non-ASCII byte patterns,
partial initialization, reentrant drop/exit, missing retirement acknowledgement,
late DMA/replies and forbidden native unwind/runtime imports, alongside valid
operations. Each control identifies its intended rejection, safe error or
contained abort; observing a hardware fault is not a library safety proof.

Seed defects that remove identity/encoding/range validation, publish an
uninitialized prefix, admit unwind glue, or release backing before completion.
Report non-compiling mutants separately from executed kills and investigate
survivors. Finite controls qualify the instruments; universal safety still
requires native soundness and library/lifecycle proofs. Existing compiler,
TAL, kernel, HAL, pool and guest-engine owners retain those proofs and budgets.
Missing foundations are assigned and priced before implementation opens; this
item prices the boundary inventory, controls and integration only.

Use focused local fixture checks as development feedback once their executable
owner exists. Complete host suites, native campaigns and proof acceptance use
the [validation handoff](../../../AGENTS.md#tool-execution-and-validation).
Record exact source/dependency/configuration/image identities, checked theorem
and assumption identities, control verdicts and unresolved entries. An article
comparison, contract, host witness or metadata check supplies no native admission
verdict; pending hosted acceptance remains pending.
