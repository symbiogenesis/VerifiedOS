# Vela editor and debugger interoperability

The [primary language design](verification-strategy.md#language-product-contract)
includes Language Server Protocol (LSP), Debug Adapter Protocol (DAP) and DWARF
support in Vela's intended toolchain. This contract defines their acceptance
boundaries. DWARF is a debugging information format; LSP and DAP are editor-facing
message protocols with different message models.

This is a non-normative design contract. The
[plan](../../../PLAN.md#vela-whole-system-authoring-proposal) owns implementation
stages and commissioning. The current parser and Gallina elaborator implement
none of these interfaces. Semantic services depend on the qualified frontend;
native debugging additionally needs an executable backend, its ABI and debug
information. A separately commissioned syntax-only server may precede those
dependencies if it advertises only its implemented subset.

## Standards and shared boundaries

Use the published [LSP specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/),
with interoperability tests for the selected 3.17-compatible feature subset.
LSP carries JSON-RPC 2.0 messages. DAP uses its own request, response and event
schema, defined by the [DAP specification](https://microsoft.github.io/debug-adapter-protocol/specification)
and [protocol schema](https://github.com/microsoft/debug-adapter-protocol/blob/main/debugAdapterProtocol.json).
Both use length-framed UTF-8 JSON. Pin the exact specifications, schemas and
client/server revisions in qualification evidence; a moving upstream link is not
a reproducible dependency pin. Capability exchange describes implemented optional
services and grants no target authority.

Use [DWARF 5 and its errata](https://dwarfstd.org/dwarf5std.html) for native debug
information. A later format revision requires its own consumer qualification;
[DWARF 6 remains a working draft](https://dwarfstd.org/download.html). Read the
selected implementation's licences before incorporating libraries, generators
or debugger code, under the [upstream rules](../../../THIRD-PARTY.md).

The compiler owns located syntax, name resolution, types, elaboration and source
maps. The language server consumes those services; it must not introduce another
parser, type system or proof acceptance path. Reuse
[contextual diagnostic judgments](core-design.md#typed-holes-and-invalidation)
from `core-diagnostics`. The existing Rocq editor and
[R-05-018a workflow](../../spec.md#r-05-018a) retain their own subject and scope;
their qualification is not Vela-server qualification.

Host development initially uses standard input/output connections, keeping logs
off the protocol stream. A resident VerifiedOS service must use the
[capability-delegated compartment transport](../../implementation/userspace-porting.md#zed-the-reference-editor)
and supervision model. Scope document access and debug sessions to explicitly
delegated workspaces and targets. Do not infer file, process, network or hardware
authority from a URI, workspace setting or client capability. A resident deployment
fixes its protocol version and feature profile at composition under
[R-12-043a](../../spec.md#r-12-043a), advertises that fixed profile and refuses
incompatible offers. Broader host-side feature negotiation supplies no exception
to that rule; resident negotiation beyond it needs a register/prose amendment
before implementation. Capability exchange cannot weaken admission or security.

Host development implementations remain untrusted diagnostic tools. Before
admitting any resident attacker-facing LSP/DAP endpoint, enumerate its exact
framing, JSON and message-schema profile and descriptor identities in the
[wire-format inventory](../../assurance/wire-format-inventory.md).
[R-05-042](../../spec.md#r-05-042) requires verified copy-once Narcissus parsers;
[R-05-043](../../spec.md#r-05-043) retains their required lowering and
[R-05-046](../../spec.md#r-05-046) independent descriptor review. A bounded JSON
library or successful protocol transcript discharges none of these duties.
The unpriced protocol stages select no resident profile or parser implementation.

Freeze bounds on header/body bytes, JSON nesting, document/workspace size,
outstanding requests, result size and worker time before implementation
qualification. Refuse malformed, truncated or over-budget input with bounded
errors or a closed session, as the selected protocol permits. Keep request
correlation, cancellation, shutdown and disconnection separate from worker
completion. An abandoned or late result never restores current evidence.

## Language Server Protocol

Provide ordinary editor features through standard LSP messages:

| Surface | Required behavior for the declared supported language subset |
| --- | --- |
| Lifecycle and documents | Initialize/capabilities, initialized, shutdown/exit, open/change/save/close, workspace changes and dependency-file invalidation |
| Diagnostics | Located lexical, syntax, name, type, resource and proof-obligation failures; distinguish unsupported features, unfinished work, timeout and stale results |
| Navigation and discovery | Hover, completion, signature help, definition/type-definition, references, document/workspace symbols and semantic tokens, using compiler-resolved identities |
| Refactoring | Prepare/perform rename and code actions as source edits tied to the current document versions; reject ambiguous, capturing or stale edits |
| Proof interaction | Inspect typed holes, local hypotheses, loans/captures, expected exits, theorem subjects and assumptions; show erased/proof information separately from runtime values |

Implement the lifecycle and diagnostics first. Advertise each later provider only
after its positive and refusal fixtures pass. A syntax-only increment may supply
syntax diagnostics and syntax symbols, but must label semantic/proof operations
unsupported. Incomplete editor input may produce partial syntax for navigation;
it cannot become accepted source or emitted production code.

Open documents have versioned in-memory overlays; unsaved text takes precedence
over disk. A result identifies the document version and the generation of the
source/dependency/tool/configuration closure used to produce it. Conservatively
invalidate the affected closure until precise dependency analysis is qualified.
Clear or mark old diagnostics when a file closes or a dependency disappears;
out-of-order worker replies cannot republish superseded diagnostics or edits.

Convert the [parser's half-open UTF-8 byte spans](vela-parser.md#bounded-increment)
explicitly to LSP's zero-based positions; identify the source API's coordinate
units rather than copying its one-based diagnostic columns.
Support UTF-16 positions, the LSP default; use UTF-8 only when negotiated with the
client. Test non-ASCII comments and supported string syntax, supplementary
characters and LF/CRLF/bare-CR boundaries, including edits before a diagnostic
and invalid ranges inside an encoded character. Never reinterpret byte offsets
as character indices.

Standard diagnostics and hover remain useful without a custom client. Rich proof
state may use a separately versioned, capability-advertised Vela extension with
an explicit schema, source/dependency identity, statuses and cancellation rules.
That extension adds presentation, not proof authority. Interactive recovery,
holes and cached goals cannot satisfy
[batch acceptance](../../spec.md#r-05-018a). A build command may report a separately
completed batch verdict only with its exact artifact/environment evidence.

## Debug Adapter Protocol

Provide a DAP adapter over an explicitly identified execution backend. Qualify
simulator debugging first; physical-target support requires the actual target
adapter and authenticated lifecycle authorization. A Gallina translation or
syntax tree alone supplies no runtime to debug.

The baseline session supports initialize, launch or attach for its declared
backend, configurationDone, source breakpoints, threads, stackTrace, scopes,
variables, continue, pause, next, stepIn, stepOut and disconnect, together with
the corresponding stopped, output and termination events. Honor the DAP startup
ordering and client path/line/column conventions. DAP coordinates have their own
declared conversion; do not reuse LSP coordinates implicitly. Each stopped state
has a generation; frame and variable handles expire on resume, restart, target
replacement or disconnect. Distinguish adapter termination from debuggee exit.

Resolve breakpoints against the exact image and its matching source/debug
sidecar. Report relocated positions and unverified breakpoints explicitly when
a line has no executable site. Source stepping accounts for inlining,
specialization and optimized control flow. Display optimized-away, erased,
uninitialized and unavailable values honestly. A suspended async frame is a
logical task frame only when the compiler/runtime supplies its mapping; it is
not an invented operating-system thread or physical stack frame.

Evaluation is bounded, read-only inspection of the stopped program's available
values. Refuse calls, writes, capability fabrication and access beyond delegated
authority. Pretty printers and DWARF expression evaluation obey the same limits.
Memory/register inspection requires explicit backend support and authority;
missing CHERI tag, bounds, permissions, sealing or provenance information is
reported unavailable, never reconstructed as live authority from an integer.
Mutation, arbitrary command execution, reverse execution, data breakpoints and
hot reload remain unadvertised unless separately contracted and qualified.

VerifiedOS's [debug lifecycle](../../spec.md#r-15-078) excludes production Debug
Module access. Development/RMA entry retains
[authenticated authorization and crypto-erase](../../spec.md#r-15-079).
The [trigger-module exclusion](../../spec.md#r-15-079a) applies in every lifecycle
state: no hardware breakpoints or watchpoints may be assumed. Use simulator
breakpoints or bounded external single-step/PC comparison on an authorized target,
reporting the latter's cost and limits. Never patch executable memory or add a
trigger comparator to make a DAP request work. A debug session's perturbed timing
is not WCET, constant-time or production-admission evidence.

## DWARF native debug information

Emit source-level debug information from the compiler's own representations,
carrying it through optimization, allocation, ABI lowering, linking and final
image composition. Describe compilation units, source files/lines/columns,
subprograms, lexical scopes, parameters/locals, concrete types/layouts, inlined
calls, address ranges and changing variable locations. Supply external stack
unwind descriptions sufficient for the qualified call/return and trap-frame
inspection; this introduces no runtime exception unwinder.

Map generics to their concrete specializations while retaining source identity.
Describe union discriminants, fields, arrays and concrete dependent indices where
represented. Ghost terms, proofs, resource grades and erased indices have no
fabricated runtime storage. Mark absent locations and optimization effects;
do not point an unavailable local at a recycled register. Identify generated
helpers and prologues so stepping can distinguish authored operations from
compiler work.

The target profile must specify register numbering, capability-sized locations,
pointer/address distinctions and unwind rules for its exact purecap ABI. Use
standard DWARF encodings where adequate and document every required CHERI/Vela
extension with independent reader controls. A generic RV64 debugger is not
presumed capability-aware. Consult the
[assigned language codes](https://dwarfstd.org/languages.html): obtain an assignment
or document a temporary code in DWARF's user range; never claim another language's
code as Vela's or invent a registered `DW_LANG_Vela` value.

Bind the debug sidecar to the final stripped/composed executable bytes, layout,
source closure, compiler/options and target/ABI identities. DWARF file checksums
and build identifiers aid matching; the package's exact-image binding remains
required. Any executable/layout change invalidates the match. Reproducible path
mapping must not leak host directories or silently substitute changed source.
Validate addresses against the final image, including dead elimination and
instruction encoding, rather than an intermediate object alone.

Keep ELF/DWARF readers in producer/debug compartments under
[R-13-010](../../spec.md#r-13-010). Symbols, debug and unwind metadata stay outside
execution SRAM under [R-13-010c](../../spec.md#r-13-010b), in host sidecars or the
authenticated store as permitted by the owning package contract. No loader,
install-path parser, admission certificate or capability authority is introduced
by a debug sidecar.

## Qualification and delivery

Each implementation increment first lands a priced plan cell, supported subset,
backend/client pins, numeric resource budgets and executable acceptance fixtures.
Language meaning, contextual diagnostics, lowering and protocol adapters retain
their separate owners; charge shared work once. Preserve full-frontend admission
prerequisites and existing compiler duties.

| Increment | Required positive and negative controls |
| --- | --- |
| LSP | Exercise the advertised features in two independent clients and a wire harness; unsaved edits, Unicode positions, rename capture, imported-file changes/deletion, configuration changes, cancellation and deliberately late old-generation responses; unfinished proofs never report batch acceptance |
| DAP | Run an image with independently expected stops, stepping, frames and values; test disconnect during startup, target exit, stale handles after continue/restart, source/image mismatch, erased/optimized values, unauthorized reads/evaluation and production-target refusal; distinguish simulator results from physical-target evidence |
| DWARF | Independent verifier/reader plus an end-to-end DAP consumer check unoptimized and optimized images with inlining, generic instances, relocated/removed code, spills, changing locations, CHERI values and unwinding; corrupt/truncate sections and alter source/image/layout to require bounded refusal of false mappings |
| LSP and DAP transport | Fragmented/coalesced frames, byte lengths with Unicode, malformed JSON, unknown requests, unsupported capabilities, limits, cancellation and clean shutdown; logs never corrupt the protocol stream and no rejected input publishes accepted artifacts |

Retain exact source, tool, client, backend and final-image identities with
transcripts, expected results and verdicts. Independent review checks that the
displayed source and values match the executed artifact, including telling
negative neighbors. Protocol conformance alone establishes no compiler theorem,
proof acceptance or measured productivity benefit. Complete the repository's
[validation handoff](../../../AGENTS.md#tool-execution-and-validation): require
Host CI on both platforms, dispatch the selected Guest CI lanes, and finish
without waiting for Guest CI.
