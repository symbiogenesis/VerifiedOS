# Tool performance acceptance

Performance maintenance preserves the decisions owned by the
[checker registry](check-rules.md) and the
[proof evidence contract](README.md#current-evidence-and-generated-documentation).
The requirements register, authored citations and proof sources remain their
respective owners. Sharing their parsed representations must not create another
authored statement of the same fact.

## Scope and acceptance

This maintenance batch covers proof source analysis, host document checking and
validation orchestration. Its starting revision is
`62a39d76b4946638043d5d780b0759d9241f99aa`.

An optimization is accepted only when all applicable conditions hold:

1. The old and new implementation produce equal decisions and diagnostics on the
   same inputs. Focused tests cover malformed inputs and the changed algorithm's
   boundaries, including edits between calls when parsing is reused.
2. A parse cache belongs to an explicit immutable input or one run. A path,
   timestamp or file size alone cannot authorize reuse after an edit. Failed or
   unsupported parses cannot become successful cached verdicts.
3. Proof dependency order, witness checks, assumption audits, content validation
   and the joint kernel check retain their existing meanings. A changed proof
   gate receives its applicable native regression checks; cached portable
   evidence cannot replace them.
4. Mutation sandboxes remain independent. Every selected case runs, failures
   remain failures, and reporting order stays deterministic. Worker reuse must
   not preserve mutations or uncontrolled process state between cases.
5. Measurements identify the revision, input scope, interpreter, command,
   repetitions and worker count. Compare equivalent work on the same machine;
   record component time separately from end-to-end time. Accept a repeatable
   improvement in the changed path without a material end-to-end regression.
   Timing noise is not a test failure or a speedup claim.
6. The integrated tree passes `python tools/run.py --check --tests`. New
   deliverables are tracked before validation. The integrator owns generated
   repairs, shared documentation and the final stable-tree wave.

The proof lane owns source-analysis machinery and its consumers; the checker
lane owns document/checker parsing; the runner lane owns sandbox and worker
orchestration. Their focused tests and measurements precede integration. A
dependency, persistent cache or trust-boundary change needs an explicit rationale
and tests for its additional failure modes before it joins this batch.

## Library and concurrency choices

The project already pins Astral's uv, Ruff and ty in
[pyproject.toml](pyproject.toml). Retain the locked environment and optimize
repeated work before adding another dependency.

Python 3.14's [executor API](https://docs.python.org/3.14/library/concurrent.futures.html)
offers bounded submission through `map(buffersize=...)` and isolated interpreter
workers. Interpreter workers still serialize arguments and results and import
their own modules; choose them only after measuring the actual workload and
preserving its isolation contract.

[Path.info](https://docs.python.org/3.14/library/pathlib.html#pathlib.Path.info)
can reuse directory-entry metadata. Such metadata can accelerate enumeration,
but it cannot establish proof-input freshness. The proof gate's content hashes
remain authoritative.

Astral documents [uv's shared cache](https://docs.astral.sh/uv/concepts/cache/)
as safe for concurrent uv operations. Each worktree still owns its installed
environment; sharing the download cache does not authorize sharing mutable
environments or proof outputs.

## Shared analysis and isolated execution

[SourceIndex](vos/proofs.py) holds immutable source text, parsed sentences,
dependency waves and transitive imports for one proof-source snapshot.
[ProofAnalysis](vos/cli/proofs.py) derives each source's witness declarations
once and combines them with the importing context. Compiler workers share that
analysis. Source and object hashes still decide freshness independently, and a
new invocation reads new bytes even when a file's size and timestamp are unchanged.

[The corpus index reader](vos/corpus.py) supplies file membership and gitlinks
without loading document text. Both document loading and mutation-template
construction use it. Generated-artifact checks read their indexed blobs in one
Git process, with NUL-framed headers and byte-sized payloads preserving binary
content. A failed batch falls back to individual reads, retaining support for
Git versions without the batch framing option. No indexed bytes survive between
checker invocations.

[Mutation templates](vos/cli/selftest.py) reuse the prior template's Git object
store after source edits. A batched object-header check refuses an incomplete
store. An unchanged index is reused; a changed template detaches that index and
rebuilds it, applying normalization and ignore rules exactly as on the cold path
while keeping the prior template intact. Changed or removed gitlinks invalidate
the index shortcut. Sandbox mutations still unlink before writing, repair
sandboxes still use private copies, and checker mutants still execute in fresh
processes.

The behavioral tests cover
[source snapshots](tests/test_gallina.py),
[witness decisions](tests/test_proofs.py),
[indexed blobs](tests/test_corpus.py) and
[sandbox reuse](tests/test_selftest.py).

## Recorded component measurements

The September 19, 2026 measurements use Python 3.14.7 on Windows ARM64 and
alternate old and new implementations over identical inputs. These are medians
of local component timings, not estimates of kernel-checking or whole-gate speed.
Unrelated guest proof jobs were active on the machine.

| Measured operation | Before | After | Repetitions | Workers |
| --- | --- | --- | --- | --- |
| Dependency waves and witness analysis over the proof corpus | 0.542 s | 0.159 s | 7 | 1 |
| Indexed generated-artifact blob reads | 0.335 s | 0.110 s | 7 | 1 |
| Git index metadata without consuming document contents | 0.245 s | 0.077 s | 7 | 1 |
| Mutation template construction after one document edit | 5.277 s | 3.996 s | 5 | 8 |

The proof comparison uses baseline `62a39d76` and candidate `4e6d4e15`.
Dependencies, wave order and witness decisions agree across the complete source
set. The index comparisons use `1c7ac000` plus the batch reader accepted at
`d1d97788`; their complete checker reports agree. The template comparison loads
baseline `7a06adca` and candidate `ecc9ace7` against the same shared corpus
module and private fixture bytes, with separate caches. The edited-template
timing includes the cached-object completeness check and fresh index construction.

Full checker timing, unchanged-template timing and complete installed-library
context timing did not establish a reliable improvement. Pin-scanning rewrites
that measured slower were rejected. The adopted changes add no dependency and
retain fresh processes for checker mutations.

Raw samples and replay scripts are retained locally under
`out/performance-20260919/`. Run a script with the checkout's managed Python;
it discovers the checkout above itself and compares against the named Git
revision. Replays measure the current checkout, so they do not recreate the
historical input population after later source edits. The native proof-cache and
assumption-audit regressions exercise actual Rocq behavior; these timing scripts
do not issue proof evidence. Changed gate inputs invalidate existing native
proof receipts under the normal proof-evidence contract.
