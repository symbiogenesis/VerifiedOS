# Optional native Sail language server

These commands run in the native guest lane; the Windows dispatcher takes the
same commands into WSL. No editor or agent extension is required.

```console
python tools/run.py sail-lsp install --json
python tools/run.py sail-lsp status --json
python tools/run.py sail-lsp serve
python tools/run.py sail-lsp qualify --json
```

Use `python3` on Linux. `serve` accepts standard LSP over JSON-RPC 2.0 with
Content-Length framing on stdin/stdout. Configure any LSP client to launch that
command from the checkout. This launcher always supplies a separate native
`--log-file`, so the server's own log stays in the lane's log location rather
than on the client's streams.
Configure the client to send `workspace/didChangeWatchedFiles` for
`**/*.sail` and `**/*.sail_project` in its workspace. This server does not request
dynamic watcher registration. The dependency-refresh patch handles these
standard notifications and `textDocument/didSave`; clients that omit both must
restart the server after an external dependency edit. UTF-16 positions and
incremental or full-buffer changes follow the server's advertised capabilities.

The optional install reads the complete existing `tools/opam/sail.lock` package
inventory and refuses drift. It builds the SHA-256-pinned archives in
[sources.lock.json](sources.lock.json) into the checkout's native
`sail-lsp/prefix`. It writes no opam switch and does not replace `sail`. The
private Libsail and the LSP server are built from the Sail release archive that
lock pins, the same SHA-256-identified archive the locked compiler's opam
package builds from. `install` refuses a Sail pin whose version is not the Sail
release `tools/opam/sail.lock` installs, and a test holds the pin equal to the
[Isla tools' Sail pin](../sail-isla/lock.json). The `sail_lsp.opam` package
label inside an archive can lag its release; the archive, not that label,
identifies the server's source.
The dependency closure adds the LSP/JSON-RPC runtime, its JSON conversion and
UTF library, and the UTF library's build helper. Compiler, dune, Yojson, and
other build dependencies come from the existing exact lock without solving
another package graph. Sources and license notices remain in the native lane.

`status` checks the recipe identity and SHA-256 of installed artifacts. It
refuses a stale recipe, an unreadable receipt, and a missing or changed
artifact, naming `install` as the repair. The recipe identity covers
[sources.lock.json](sources.lock.json), `tools/opam/sail.lock`, the installer
module `tools/vos/saillsp.py` and the dependency-refresh patch, so a change to
any of them, the installer's own code included, makes `status` refuse each
lane's installation as stale until `install` rebuilds it. `install` returns an
installation `status` accepts and otherwise builds one, first printing any
refusal it repairs. It downloads again any source archive that is missing or
differs from its pin, keeps a download only once its SHA-256 matches, and
extracts each source into a fresh tree. It removes
the previous receipt first and installs into an emptied prefix and
configuration, so nothing a superseded recipe installed is loaded or hashed as an
artifact, and an interrupted rebuild leaves no installation for `status` to
accept. Native install and qualification outputs remain in the assigned build
lane; build logs use its assigned native log location. Installation receipts
retain source hashes, license-file hashes, the complete inherited package
inventory, and artifact hashes. These detect accidental changes, not malicious
substitution of both artifacts and receipts.

[dependency-refresh.patch](dependency-refresh.patch) is the maintained local
change to [upstream handler.ml at the source pin](https://github.com/rems-project/sail/blob/3df54034910b31a1e00d948ee965b2e9603d68e0/src/sail_lsp/handler.ml).
It reloads changed compiler-owned file contents, preserves editor-owned unsaved
buffers, rebuilds project checking state, and publishes diagnostics for every
open document. Missing or unreadable dependencies clear typed state and produce
an explicit diagnostic. Restoring the dependency permits a new check. The patch
and its upstream context carry BSD-2-Clause; the selected upstream
[license notice](SAIL-LICENSE.md) is retained verbatim. No upstream compiler or
server source is otherwise vendored. Patch application requires the existing
native `patch` utility and refuses mismatched context (`--fuzz=0`).

`qualify` uses tracked two-file fixtures and opens the actual curated CHERI
source. It exercises initialization, diagnostics, hover, definition navigation,
an unsaved edit, a saved dependency edit, request cancellation, and a fresh
server process. Dependency regression also checks restoration, deletion, and
preservation of an unsaved dependent buffer. Its batch comparisons use the unchanged locked Sail with strict
flags on the same saved candidate bytes. Unsaved-buffer comparison materializes
the candidate only in its private native fixture. The default response budget
is 90 seconds per operation; `--timeout` accepts 1 through 600. Reports preserve
responses, separate live and batch timings, server peak RSS, transcripts, raw batch diagnostics and
exit codes. No timing here establishes a productivity improvement.

A failed capability remains failed in the report. Cancellation notifications
are advisory in LSP: a valid completed response passes the protocol check but
does not establish interrupted work. The separate work-interruption observation
is optional and remains false when unobserved. Terminating the server and
starting a new session provides the tested cancellation fallback. `qualify`
returns nonzero if any required check failed; `all_capabilities_passed` also
includes the optional observation. This does not disable the separately
launched server or grant it acceptance authority. Batch compilation and all
affected model, property, differential and proof gates retain their existing
meaning. The [shared workflow](../../docs/assurance/sail-assistance.md) owns that
policy; [the output schema](../sail-lsp.schema.json) owns status/report shapes.
