# Canonical memory and tag binding qualification

Q35p remains open. The isolated canonical V1 candidate resolves the actual emitted
tag-read and tag-write calls through the concurrency outcome monad. Both untouched
minimal emitted modules compile strictly against the amended support. The candidate
has executable raw-key finite-map legality and native caller controls; its universal
caller correspondence, complete frozen comparison and production-carriage joins
remain owed.

[Isolated canonical tag candidate](retained-evidence/reuse-wire-tags-20261023/manifest.json),
SHA256 `3fe661163dd4ac2c9781d2229e2a8a546306bfe87359bbecffa1f0d762aaac0d`,
binds the immutable patch, exact commands, generated minimal modules, native readings,
assumption queries, scoped kernel recheck, installed-path inventories and notices at
base `a5e4ba0e3e2ab477cdde2ae8a59dd47b82a9da90`. The source archive and actual
BSD-2-Clause license match the unchanged
[source recipe](../../tools/opam/sail-support-qualification.json).
The [owner contract](contracts/canonical-tag-outcomes.md) governs this amendment.

[Executed native tag drivers](retained-evidence/reuse-wire-tags-drivers-20261023/manifest.json),
SHA256 `04b6f1e55fc37ca623105f559be23a23c6af723a271e0adfbd49074d1680dfb6`,
preserves the actual compile, emission and evidence drivers separately from the
packaged replay. The unchanged reproducer and its source notices also remain bound
by the [original memory source reading](retained-evidence/close3-q35p-20261013/manifest.json),
SHA256 `db26237bdbde7915efa9f3d4ce29b3b95c595dc1008842fb34ce9f713a4f3510`.

## Actual bindings and effects

The [native reading](retained-evidence/reuse-wire-tags-20261023/binding-reading.txt)
resolves the unchanged minimal reproducer's seven bindings:

| Binding | Resolved emitted meaning |
| --- | --- |
| `read_mem#` | `bindings.read_mem_ : ... -> M (mword (8 * n))`; existing `internal_error` refusal |
| `read_mem_ifetch#` | `bindings.read_mem_ifetch_ : ... -> M (mword (8 * n))`; existing refusal |
| `read_mem_exclusive#` | `bindings.read_mem_exclusive_ : ... -> M (mword (8 * n))`; existing refusal |
| `write_mem#` | `bindings.write_mem_ : ... -> M bool`; existing refusal |
| `write_mem_exclusive#` | `bindings.write_mem_exclusive_ : ... -> M bool`; existing refusal |
| `__read_tag` | `bindings_types.Defs.read_tag_bool : mword 64 -> monad E bool`; `Next (TagRead key) Ret` |
| `__write_tag` | `bindings_types.Defs.write_tag_bool : mword 64 -> bool -> monad E unit`; `Next (TagWrite key value) Ret` |

Here `M` remains `Defs.monad exception`. The semantic patch extends only the V1
outcome type, adds these two bindings and forwards both constructors through
`map_extra_iMon` and `try_catch`. The raw argument is already the granule key:
no additional shift or data request occurs. No tag is encoded as an exception.
The five emulator-memory refusal bodies and their error definitions remain emitted
from the unchanged reproducer. Its new native absolute source path appears in the
ordinary `__FILE__` diagnostic strings; those strings were not post-edited.

The original [interpreter](../../tools/sail-tag-outcomes/TagInterpreter.v) uses
`gmap Z bool`, indexed by the raw word's unsigned value. It derives default-false
reads, exact-key insertion, same-key lookup and other-key framing from executable
map operations. A generic frame carries every other state component. Primitive
bridges quantify over every initial map, key, written bit, frame and continuation;
the same fixed handler interprets old events. No handler law assumes tag agreement.
The generic outcome algebra's unconstrained responses are restricted by this
executable legality definition.

## Scoped checks and limits

Both baseline and candidate compile the explicitly selected 29-module support closure
under the unchanged strict locked flags without diagnostics. Actual private-plugin
emission of the unchanged minimal Sail source repeats both Rocq files byte for byte;
both generated files, the interpreter and the controls compile strictly. Two C-target
regenerations of that same minimal source also produce byte-identical `.c` and `.h`
files. This is a minimal-source comparison, not paired full-model regeneration.

The [native controls](../../tools/sail-tag-outcomes/TagControls.v) exercise absent,
set and cleared tags; zero, maximum and distinct raw keys; other-state framing;
aligned, partial and multi-granule metadata writes; ascending clears and the existing
empty interval after fixed-width wraparound. Actual `write_ram` controls preserve
data-before-metadata after all three `Ok` variants and no metadata after `Err ()`.
Requested and unrequested metadata reads preserve their data ordering and read
refusals. Forwarding covers `try_catch`, `map_extra_iMon` and early return, with a
real caught exception distinguished from a tag event. Native controls reject an
unconstrained read, discarded write, changed return type, dummy data event and
missing, reordered or added tag events.

All 33 explicitly queried new proofs report `Closed under the global context`.
That finite query is not a complete support declaration census. `rocqchk -norec`
passes on the two authored objects while admitting their dependencies; its retained
context summary is not an accepted dependency-axiom closure. No recursive whole-corpus
kernel check, package test, full gate or benchmark ran locally.

The checkpoint stops at twelve candidate checks, within a conservative 1,001-second
wall interval that includes preparation and evidence work. One eager wraparound
`vm_compute` attempt was stopped after its owned process grew to about 19 GB; the
unchanged statement closes by lazy kernel conversion, and other computational
controls have explicit tactic timeouts. Earlier fixed probe logs were overwritten;
the checkpoint retains their execution-tool diagnostic summaries and final native reading logs,
not a complete raw archive of every failed try.

Complete before/after inventories preserve all 10,904 installed proof `bin`/`lib`
paths, including additions and deletions. The 16,140 Sail paths are unchanged over
the later native-query and paired-C-generation interval; the initial minimal Rocq
emissions precede that Sail inventory interval. No shared installation was rebuilt
or repaired by this lane. The [packaged replay](../../tools/sail-tag-outcomes/README.md)
adds canonical path-overlap and identity refusals; its four focused host controls,
pinned Ruff and Linux/Windows typing pass. It has not been claimed as a clean native
replay of the packaged runner.

## Remaining acceptance

The native finite caller controls do not establish the contract's universal bridge
for every emitted metadata/physical-memory caller and continuation. Formal old-event
conservativity against the original outcome type and the complete native frozen
reading, including generated induction/elimination declarations and exact assumptions,
also remain open. The retained functor-layout readings supply no substitute for that
census and body comparison.

Q35p must then join Q35o's actual-plugin and deterministic full-emission checks,
Q35b's strict whole-term compile, exact closure and compiled size, full-model paired
non-Rocq regeneration, and Q35n/Q35q's cold source-carriage/census qualification.
The candidate recipe is separate from the production support recipe and proof switch.
The integrator's Host CI and cold Guest CI handoff provide their own recorded verdicts;
none is supplied by these isolated checks.
