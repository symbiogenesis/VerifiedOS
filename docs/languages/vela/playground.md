# Vela browser playground

## Scope and launch

Q25aa in [the plan](../../../PLAN.md#q-assessment-actions) commissions a local
browser demo of the implemented [pure Nat/bool compiler](vela-prototype.md) and
[language server](lsp-prototype.md). Launch it with
`python tools/run.py vela-playground` (`python3` on Linux), then open the printed
loopback URL. The command accepts a port, including zero for an available port,
and stops with Ctrl+C. It never publishes, writes source files or installs an
editor extension. Hosting and wider-language qualification retain their owners.

The editor uses pinned Monaco 0.55.1 browser assets from jsDelivr. Internet access
is needed for those editor assets; authored source is sent only to the local
compiler service. The browser must clearly report an editor-load failure and
offer plain-text editing with the same compile/evaluate controls. This fallback
does not claim highlighting or editor language services. The
[third-party record](../../../THIRD-PARTY.md#browser-editor-assets) owns the
selected upstream terms and intended distribution.

## Browser behavior

Provide an editable source pane, examples, a diagnostics view, a read-only
Gallina output pane and a console for closed expressions. Include accessible
labels, keyboard actions, a responsive layout, connection/error status and an
explicit pure-prototype scope indication. A successful check means only that
the unqualified prototype reported no error. It supplies no kernel, source
correspondence, native execution or production-admission verdict.

Lexical highlighting is a syntax-only Monarch projection. Hover, definition,
references, document symbols, inferred-type hints, full semantic tokens and
explicit formatting consume the existing server's advertised capabilities.
The browser initializes a separate LSP session, synchronizes full unsaved
snapshots with monotonically increasing versions and serializes transport.
Discard diagnostics, editor replies and compiled/evaluated output after the
source or relevant input changes. Formatting applies only to its requested
unchanged snapshot. Render source-derived strings as text, including console
output and hover documentation. Completion, imports and wider semantics are
not advertised by this demo.

Compile shows the actual Gallina returned by `translate` for the exact UTF-8
source. The expression console selects `Nat` or `bool` and reuses the compiler's
existing required-static checking and bounded evaluation. A structured compiler
API validates the complete original source and exactly one synthetic constant
initializer, returning its typed value without a second parser or evaluator.
Reject declaration injection, unsupported constructs and resource exhaustion.
The authored source stays unchanged; the console describes the value as a
compile-time result. There is no runtime standard-output or native-code claim.

## Local transport

Bind only IPv4 loopback, use a random startup bearer token in the printed URL
fragment and require it for every API call. Remove the fragment from the visible
URL after reading it. Check the exact Host and any supplied Origin against the
bound loopback authority; never enable wildcard CORS. Serve only a fixed static
asset allowlist. No client-selected disk path, shell command, proxy, workspace
read or generated-file publication is exposed. Apply no-store and
no-referrer response policy and prevent framing.

The JSON API is same-origin POST with `Authorization: Bearer TOKEN`:

| Path | Request | Response |
| --- | --- | --- |
| `/api/session` | `{}` | `{ "session": "opaque-id" }` |
| `/api/lsp` | `{ "session": "opaque-id", "message": LSP_OBJECT }` | `{ "messages": [LSP_OBJECT] }` |
| `/api/compile` | `{ "source": "UTF-8 text" }` | `{ "ok": true, "sourceHash": "sha256", "module": "name", "gallina": "text" }` |
| `/api/evaluate` | `{ "source": "UTF-8 text", "expression": "text", "valueType": "Nat or bool" }` | `{ "ok": true, "sourceHash": "sha256", "valueType": "Nat or bool", "value": "decimal or true/false" }` |

Compiler refusals return `ok: false`, the original `sourceHash`, and an `error`
object containing `kind`, `message`, `line` and `column`. Coordinates are
one-based compiler coordinates; expression errors identify their expression
context. Transport refusals use an unsuccessful HTTP status and an `error`
string. The browser handles both explicitly. No refusal can retain a successful
result for changed input.

Use the existing strict protocol JSON reader and its nesting/byte limits, and
validate endpoint shapes. Bound HTTP reads, concurrent requests, session count
and idle lifetime. Serialize each session's `Server.handle` calls, retain the
server's document and isolated-worker limits, and bound complete HTTP replies.
Compile and evaluation use isolated same-interpreter workers with a finite
timeout and bounded input/output; no source becomes Python code. Sessions expire
and shutdown releases server resources. Log no source text or bearer tokens
except the initial local launch URL.

## Acceptance

Land this contract and Q25aa's estimate before implementation. Independently
review the compiler reuse, bridge and stale-response behavior. Focused host
controls cover actual natural/Boolean evaluation and Gallina, malformed and
injected expressions, semantic refusals and limits, immutable source, real LSP
initialization/diagnostics/navigation/formatting, Unicode and version isolation,
cross-session isolation, HTTP authority/authentication/JSON/path/size refusals
and session expiry. Check browser behavior with the available local browser
infrastructure, including an edit, diagnosis, hover, format, compile, evaluate
and rejected-source recovery; record unavailable browser verification explicitly.
Editor asset failure must leave usable compile/evaluate controls.

Run focused behavioral tests, Python validation and the corpus checker locally.
Record the settled revision and recommended hosted checks through `fanout`.
The user owns publication and Host/Guest CI; pending hosted verdicts do not
block the local demo handoff or qualify Q25n/Q25o/Q25u's independent-client gates.
