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

To connect a host editor, configure its stdio language-server command as `python`
with arguments consisting of the absolute path to `tools/run.py` followed by
`vela-lsp`; use `python3` on Linux. Associate Vela buffers with language ID `vela`
and the `.vela` extension. No editor extension or automatic registration is
installed by this command. The server uses open-buffer text and does not read the
URI's file. Diagnostics and navigation cover only the pure subset linked above.

For Neovim 0.11's built-in LSP client, adapt these absolute paths in `init.lua`
and reopen a `.vela` file. This configuration uses the
[documented client configuration API](https://github.com/neovim/neovim/blob/v0.11.0/runtime/doc/lsp.txt);
it is a setup example, with two-client qualification still outstanding.

```lua
vim.filetype.add({ extension = { vela = 'vela' } })
vim.lsp.config['vela'] = {
  cmd = { 'python', 'C:/src/VerifiedOS/tools/run.py', 'vela-lsp' },
  filetypes = { 'vela' },
  root_markers = { '.git' },
}
vim.lsp.enable('vela')
```

Use the manifest's Python minor version and `python3` on Linux. Prepare the locked
environment once with `python tools/run.py vela-lsp --help` before the editor's
first connection. In Neovim, `K` shows hover, `grr` finds references, `gO` lists
document symbols and `:lua vim.lsp.buf.definition()` jumps to a declaration.
Only complete sources accepted by the pure checker provide navigation; incomplete
or unsupported code continues to receive the producer's diagnostic.
Editors with standard inlay-hint support can also show inferred local `Nat` and
`bool` types through the [authoring-hint provider](#authoring-hints).

## Interface and bounds

Support initialize/initialized, shutdown/exit, incremental document synchronization
(open/change/save/close), push diagnostics and cancellation notifications over
stdio. Advertise UTF-16 positions and incremental synchronization. Unknown requests
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
ranged edits use zero-based UTF-16 positions in the preceding edit's result.
Convert positions back to exact UTF-8 boundaries without normalizing stored text.
Clamp character offsets beyond a line's end as LSP requires; refuse negative or
non-integer coordinates, nonexistent lines, reversed ranges and positions inside
a supplementary character. An optional deprecated `rangeLength` must match the
removed UTF-16 units, counting CRLF as two units. Apply each notification's edits
in order and publish only its final snapshot. Versions strictly increase, and an
invalid edit anywhere in a notification leaves the previous snapshot and session
generation unchanged.
Remember a newer received version even when its replacement text is refused;
an older later update cannot restore synchronization.
Close clears diagnostics. Save rechecks the overlay. Configuration and watched-file
changes invalidate and recheck all open snapshots conservatively. There are no
import, rename, semantic-token or interactive-proof providers. The separately
commissioned pure navigation increment below consumes existing resolution facts;
it supplies no wider-language qualification.

| Resource | Bound and refusal |
| --- | --- |
| Frame headers | 8,192 bytes; ASCII CRLF lines and exactly one decimal Content-Length; malformed/truncated frames close the session |
| Frame bodies and replies | 1,048,576 bytes; strict UTF-8 JSON objects, unique keys and finite numbers; malformed JSON receives a parse error and valid non-message JSON an invalid-request error |
| JSON nesting | 64 containers, counted outside strings before decoding; over-budget input closes the session |
| Documents | 16 open documents, each at most the pure producer's 65,536 UTF-8 bytes; URI at most 4,096 UTF-8 bytes |
| Changes | At most 64 sequential edits per notification; every intermediate text must fit the document bound; an empty batch advances a synchronized document's version without changing its text |
| Diagnostic output | One producer error per document; message at most 4,096 characters; include version and snapshot identity, never an acceptance claim |
| Work and concurrency | One synchronous check at a time, isolated worker timeout 5 seconds; no queued/background work or late publication |

Unsupported language constructs receive the producer's explicit unsupported
diagnostic. Empty diagnostics mean only that the prototype reported no error.
Cancellation has no outstanding asynchronous work to cancel; it cannot undo a
published notification. A worker timeout produces a diagnostic for that snapshot.
Invalid document notifications clear diagnostics for the affected open document,
are logged and leave overlays unchanged.
Save and invalidation cannot republish diagnostics for a refused edit's old text;
a valid full replacement or close/reopen restores synchronization. A ranged edit
cannot use a desynchronized overlay; a change batch must begin with a full
replacement before any subsequent ranged edits can restore synchronization.

## Pure navigation increment

Q25o commissions hover, definition, references and flat document symbols for
completely checked sources in the existing pure Nat/bool subset. These services
remain unqualified host diagnostics. Record immutable declaration identities,
types and occurrences in the existing pure elaborator's resolution decisions;
do not introduce another parser, resolver or type system. Retain both existing
translation routes and their emitted terms. No facts survive a failed complete
check. Partial syntax, imports, completion, rename, proof state and wider-language
services retain their existing prerequisites.

Support `textDocument/hover`, `textDocument/definition`,
`textDocument/references` and `textDocument/documentSymbol`; advertise only those
four navigation providers; [authoring hints](#authoring-hints) add the separate
inlay-hint provider. Hover uses plain text with the resolved function
signature or local/parameter type and an explicit unqualified-prototype label.
Definition returns the exact declaration identifier location. References use
resolved identity within the requested document and honor `includeDeclaration`.
Flat `SymbolInformation` lists functions, parameters and local bindings in source
order with exact identifier locations; it makes no function-body span claim.
Use distinct identities for same-spelled declarations in different functions or
sibling branches, and preserve the producer's distinct call/value namespaces and
earlier-function-only rule. Identifier ranges are half-open: positions at their
end, comments, punctuation and whitespace select no symbol.

Require the initialized notification and a synchronized open overlay for every
query. Unknown or closed documents are invalid parameters; desynchronized
documents return ContentModified (`-32801`). Refused source yields null hover
and definition, and empty references and symbols. Malformed query parameters
return invalid parameters (`-32602`). Worker/resource failure returns RequestFailed
(`-32803`), without partial facts, truncation or session termination. Requests
are synchronous and correlated; each result uses the current immutable snapshot.
Any cache is bound to its full identity and is discarded on changes, refused
updates, configuration/dependency invalidation, close and shutdown. A result for
an old snapshot cannot become a result for a newer one. URI strings grant no disk
access, and query responses cannot publish accepted artifacts.

Use the same isolated interpreter and five-second worker bound as diagnostics.
An inspection may contain at most 1,024 declarations and 4,096 identifier
occurrences, including declarations; exceeding either refuses inspection without
changing ordinary translation. Its internal JSON result is either
`{"status":"unavailable","reason":KIND}` or an object with `status: "ok"`,
`symbols` and `occurrences`. Each symbol has `name`, `kind` (`function`,
`parameter` or `variable`), `detail` and one-based normalized code-point `line`
and `column`. Its index is a snapshot-local identity. Each occurrence has
`symbol` (that index), `line`, `column` and boolean `declaration`. Validate the
worker shape, bounds, identity links and exact source spelling before converting
positions through the shared source API. Worker output and each complete reply
retain the 1,048,576-byte bound; an oversized result is refused as a whole.

Acceptance requires independently expected signatures, types, declaration sites
and reference sets for earlier calls, parameters, inferred locals, same-spelled
bindings across functions and sibling branches, and distinct call/value
namespaces. Cover half-open token selection, UTF-16 with supplementary comments,
LF/CRLF/bare CR, invalid and unsupported source, malformed parameters, all limits,
timeout, unopened/closed/desynchronized overlays and recovery. Incremental edits
must move or remove facts; invalidation and refused edits cannot expose cached
facts. A process-level stdio session exercises all four requests against the real
producer and an unsaved incremental update. Existing translation and LSP controls,
focused host tests, Python checks, both Host CI aggregates and selected Guest CI
dispatch remain required. Independent review must check the compiler fact
producer and protocol projection. Two pinned editor clients with retained
transcripts remain necessary for final interoperability qualification; a wire
harness alone does not close Q25o or Q25n.

## Authoring hints

[Q25p](../../../PLAN.md#q-assessment-actions) adds `textDocument/inlayHint` for
inferred local types in the completely checked pure subset. Advertise this
provider alongside the existing navigation providers. Requests contain a valid
half-open document range; return type hints at the ends of inferred local
identifiers wholly contained in that range, with `kind: 1` and labels such as `: Nat` or
`: bool`. Parameter declarations and explicit signatures need no redundant hint.
The identifier may end exactly at the requested range's end, which also anchors
its hint there. Use the compiler's existing resolved symbol facts; do not reparse source or infer
types in the protocol projection. Labels are diagnostic presentation and never
insert source, conversions, loans, proof steps or accepted artifacts.

Require synchronized initialized overlays, exact snapshot identity, bounded
complete output and the existing unavailable/error policy. Invalid coordinates,
reversed ranges, worker failures and stale/desynchronized documents follow the
navigation protocol's errors. Unsupported or invalid source yields an empty hint
list. Independent controls cover inferred types, shadowed declarations, requested
ranges, UTF-16 and mixed newlines, incremental edits, refusal/recovery, malformed
worker facts, limits and a real process-level request. Retain navigation and
translation controls and the shared hosted validation handoff.

Unsupported ownership/loan syntax should explain its requested mode and the
current pure checker's limit, instead of presenting a borrow-conflict judgment
that this producer cannot establish. Receiver mode/view hints and live-loan
conflict explanations remain required by the broader
[editor contract](tooling-protocols.md#language-server-protocol), and require the
corresponding compiler facts before advertising those services. This increment
does not commission a second surface parser or a source borrow checker.

Immutable-binding reassignment diagnostics identify the binding and explain
`let`/unmarked type-first immutability and explicit `var` reassignment. The pure
producer states that mutation requires the wider surface; it grants no accepted
mutable program or source borrow verdict. A write through an exclusive loan is
distinct from rebinding its immutable descriptor. Diagnostics and locations must
survive local shadowing, incremental edits and unsupported resource syntax.

## Acceptance and remaining qualification

Independent wire fixtures exercise fragmented and coalesced frames, Unicode byte
lengths, strict JSON and bounds, lifecycle ordering, unknown requests, clean and
unclean exit, overlays, stale versions, close clearing, configuration invalidation,
unsupported syntax, checker/type errors and timeout. Coordinate fixtures use
independently chosen UTF-8 and UTF-16 expectations at newline and supplementary
character boundaries. Tests verify that invalid updates preserve the previous
snapshot and that no URI causes a file read or accepted artifact publication.
Incremental controls cover sequential multi-edit coordinates, supplementary
characters, mixed newlines, clamped columns, optional range lengths, empty batches,
intermediate source/edit-count limits, later-edit rollback and recovery from a
refused update. A process-level wire session must show an incremental edit moving
or clearing a real producer diagnostic with the new document version.
Run focused host tests and Python type/lint checks, then the shared Host CI and
selected Guest CI handoff. No native build is required for this host increment.

This is a prototype checkpoint. Q25n remains open until two independent editor
clients have pinned revisions, retained transcripts and independent expected
diagnostics for the advertised subset under the broader protocol contract.
The wire harness alone supplies no two-client qualification. Broader asynchronous
services require explicit cancellation and deliberately late-result controls
before advertising them. DAP and DWARF implementation remain separately unpriced.
