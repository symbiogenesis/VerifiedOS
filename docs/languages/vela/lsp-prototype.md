# Vela host language server prototype

## Commissioned increment

Q25n in [the plan](../../../PLAN.md#vela-whole-system-authoring-proposal) commissions
an untrusted host LSP 3.17-compatible development server, invoked with
`python tools/run.py vela-lsp`. Its producer is the existing
[pure prototype](vela-prototype.md), including its explicit Nat/bool subset and
unqualified diagnostics. It adds no parser, proof acceptance or production
emission. Broader syntax, semantic services and resident deployment retain the
[protocol contract](tooling-protocols.md#qualification-and-delivery)'s prerequisites.

Deliver LSP first, then DWARF when an executable backend and ABI exist, then DAP
over an identified execution backend. Simulator DAP can precede DWARF only when
its backend supplies independently qualified source/runtime mappings.

## Interface and bounds

Support initialize/initialized, shutdown/exit, full document synchronization
(open/change/save/close), push diagnostics and cancellation notifications over
stdio. Advertise UTF-16 positions and full synchronization only. Unknown requests
return method-not-found; pre-initialization requests return server-not-initialized.
Refuse repeated initialization and requests after shutdown. EOF or exit before
shutdown is an unsuccessful session. Logs use stderr. No filesystem, process
launch requested by the client, workspace traversal or network service is exposed.

Immutable snapshots bind URI, document version, source bytes and a monotonically
increasing session generation. URIs are opaque identifiers, never authority to
read disk. Diagnostics use the existing checker's one-based Unicode code-point
coordinates after newline normalization, converted explicitly to zero-based
UTF-16 positions. Shared source utilities also convert half-open UTF-8 byte
offsets, rejecting offsets inside encoded characters or CRLF. Handle LF, CRLF,
bare CR and supplementary characters. Full unsaved text replaces earlier text;
versions strictly increase, and invalid updates never alter the current snapshot.
Remember a newer received version even when its replacement text is refused;
an older later update cannot restore synchronization.
Close clears diagnostics. Save rechecks the overlay. Configuration and watched-file
changes invalidate and recheck all open snapshots conservatively. There are no
import, rename, navigation, semantic-token or interactive-proof providers.

| Resource | Bound and refusal |
| --- | --- |
| Frame headers | 8,192 bytes; ASCII CRLF lines and exactly one decimal Content-Length; malformed/truncated frames close the session |
| Frame bodies and replies | 1,048,576 bytes; strict UTF-8 JSON objects, unique keys and finite numbers; malformed JSON receives a parse error and valid non-message JSON an invalid-request error |
| JSON nesting | 64 containers, counted outside strings before decoding; over-budget input closes the session |
| Documents | 16 open documents, each at most the pure producer's 65,536 UTF-8 bytes; URI at most 4,096 UTF-8 bytes |
| Diagnostic output | One producer error per document; message at most 4,096 characters; include version and snapshot identity, never an acceptance claim |
| Work and concurrency | One synchronous check at a time, isolated worker timeout 5 seconds; no queued/background work or late publication |

Unsupported language constructs receive the producer's explicit unsupported
diagnostic. Empty diagnostics mean only that the prototype reported no error.
Cancellation has no outstanding asynchronous work to cancel; it cannot undo a
published notification. A worker timeout produces a diagnostic for that snapshot.
Invalid document notifications clear diagnostics for the affected open document,
are logged and leave overlays unchanged.
Save and invalidation cannot republish diagnostics for a refused edit's old text;
a valid full replacement or close/reopen restores synchronization.

## Acceptance and remaining qualification

Independent wire fixtures exercise fragmented and coalesced frames, Unicode byte
lengths, strict JSON and bounds, lifecycle ordering, unknown requests, clean and
unclean exit, overlays, stale versions, close clearing, configuration invalidation,
unsupported syntax, checker/type errors and timeout. Coordinate fixtures use
independently chosen UTF-8 and UTF-16 expectations at newline and supplementary
character boundaries. Tests verify that invalid updates preserve the previous
snapshot and that no URI causes a file read or accepted artifact publication.
Run focused host tests and Python type/lint checks, then the shared Host CI and
selected Guest CI handoff. No native build is required for this host increment.

This is a prototype checkpoint. Q25n remains open until two independent editor
clients have pinned revisions, retained transcripts and independent expected
diagnostics for the advertised subset under the broader protocol contract.
The wire harness alone supplies no two-client qualification. Broader asynchronous
services require explicit cancellation and deliberately late-result controls
before advertising them. DAP and DWARF implementation remain separately unpriced.
