# Tool performance acceptance

Performance maintenance preserves the decisions owned by the
[checker registry](check-rules.md) and the
[proof evidence contract](README.md#current-evidence-and-generated-documentation).
The requirements register, authored citations and proof sources remain their
respective owners. Sharing their parsed representations must not create another
authored statement of the same fact.

## Scope and acceptance

This contract covers proof source analysis, host document checking and
validation orchestration. Dated measurements below retain their own baseline
and candidate identities.

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
5. Benchmarks run only on CI. Measurements identify the revision, input scope, interpreter, command,
   repetitions and worker count. Compare equivalent work on the same machine;
   record component time separately from end-to-end time. Accept a repeatable
   improvement in the changed path without a material end-to-end regression.
   Timing noise is not a test failure or a speedup claim.
6. The integrated tree follows the
   [validation handoff](../AGENTS.md#tool-execution-and-validation): Host CI must
   pass, and every Guest CI lane is dispatched without waiting for its verdict.
   New deliverables are tracked before validation. The integrator owns generated
   repairs, shared documentation and the final stable-tree checks. Experiments
   outside those workflows retain their separate acceptance predicates.

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

The selftest compiles checker modules into checked-hash bytecode once per immutable
template. Fresh child interpreters require hash validation against their own source
and suppress cache writes, retaining source-mutant isolation even when an edit keeps
its size and timestamp. Sandbox construction overlaps the baseline's read-only run
against the template; a repair-only run constructs no case sandbox.

Large retained proof readings use the manifest's lossless gzip representation.
Content hashes and byte counts still bind the original reading. Repository-wide
encoding, pin and interim scans retain their coverage of its expanded contents.
A shared streaming prescan can establish absence of bounded upstream names and
interim token candidates without materializing the expanded text. It consumes every
gzip member and validates its trailer. Reuse belongs to one checker context and
requires equal compressed bytes and matcher inputs. A candidate hit or unsupported
text retains the existing full parser and exact diagnostics; malformed input cannot
become a cached absence verdict. The archive remains in the audit's scope.

Hosted gate timings record bytecode and sandbox phases beside the baseline, cases
and repair path. The selftest checkpoints completed and active work so timeout
reports preserve progress without claiming a verdict. Complete timing runs and
benchmarks stay on CI. Host CI's optional `performance_base` dispatch input runs
[paired checker measurements](ci/archive_scan_benchmark.py) on Ubuntu: baseline
tools from that proper ancestor and candidate tools read the same indexed candidate
corpus in fresh processes, with two alternating repetitions each. The retained
artifact compares entire reports and records group and process time. It establishes
an improvement only for its named source revisions and corpus; separate historical
runner timings do not establish a paired speedup.

The behavioral tests cover
[source snapshots](tests/test_gallina.py),
[witness decisions](tests/test_proofs.py),
[indexed blobs](tests/test_corpus.py) and
[sandbox reuse](tests/test_selftest.py).

## Native Sail census validation todo

The outstanding actions and acceptance conditions are maintained in
[PLAN.md](../PLAN.md#native-sail-census-validation), under Q35q. This document
owns the performance measurement rules and recorded evidence.

## October 30 guardrail algorithms

The [maintenance scope](../PLAN.md#guardrail-performance-optimization) preserves
the existing decisions while reducing repeated work. Candidate publication to Host
CI may precede measurements; an algorithmic improvement supplies no measured speed
factor or native qualification verdict.

The checker collects possible upstream-name line regions before scanning pin IDs.
Its retained-archive pass shares glyph, pin and lineage facts while consuming all
gzip members and their integrity checks. Unsupported Unicode and long unfinished
lines retain the complete pin reader without discarding valid glyph and lineage
facts. A bounded streaming name check can still establish pin absence on huge
lines without expanding their full text. Literal searches with native boundary
assertions collect candidate regions; ID-free lines do not enter the
upstream-attribution parser. Archive work moves between groups, so compare the
complete checker as well as individual group times. Markdown structural readers
omit unused inline expansion; count readers reuse masks only when their line
representations agree. Proof-source facts are content-keyed within a context while
each consumer still acquires current source bytes.

Streaming presence and candidate-line searches use one bounded literal trie per
invocation. A first literal character precedes each left-boundary assertion;
right-boundary constraints sit at terminal nodes so a shorter name at the same
start remains visible when a longer name reaches an unknown window edge. The
existing parser still decides every ID and its attribution. Programs are bound to
the actual name tuple, and unsupported inputs retain the legacy scan. The boundary
oracle and chunk tests retain the original `isalnum` and underscore/hyphen rules.
The name matcher skips whole runs whose characters forbid a new left boundary.
It uses one anchored match per forward scan, with the actual name in a separate
capture; retrying a failed suffix with `search()` would lose that linear bound.
Completed spans skip name-line extraction while the complete streaming scan has
found no bounded name; unfinished lines and advancing line counts remain intact.
Nonword initial literals retain the legacy path. Lineage candidates retain the
original raw and ASCII-folded byte searches: the byte-trie experiment increased
their measured cost. Folding remains `bytes.lower()`. Matcher programs are local
to an invocation and carry no source verdict or persistent cache.
The pin-ID repeat is possessive: backing off a consumed hexadecimal character can
only put another word character before the refusing right boundary. Its frozen
greedy oracle compares full matches, captures and bounded searches. ASCII stream
windows skip glyph searches only when every requested needle needs a non-ASCII
byte; overlap windows and generic ASCII needles retain their complete checks.

The census validator resolves its schema plan once per call, retains every
compatible union branch and constructs diagnostic paths on failure. Reverse indexes
replace repeated population joins; declaration fallback serialization is lazy.
Native-effect comparisons retain all resolver effects. Unusual supplied schemas
retain the original interpreter, including its decisions about whether a malformed
constraint is visited for the actual value. The original three-root native control
emission is unavailable on this machine pending migration from the old machine.
The [replay descriptor](ci/census-benchmark-inputs.json) records that
gap explicitly. Missing input cannot yield completed comparison evidence. Q35q's
complete native census, independent positive and corruption controls, assumptions
and kernel acceptance remain open under their existing contracts.

Markdown table validation batches an exact private snapshot of indexed documents
through the pinned linter. Discovery must equal the selected file population;
unsupported configuration, carriage returns and unfamiliar diagnostics retain the
per-string route. Proof-header repair shares parsed facts only at unchanged cuts,
with separate reports and actual-byte assertions. All five full repair checks
remain. Proof-context snapshots hash each distinct loaded library path once and
read it afresh at the next snapshot.

The [hosted comparison workflow](../.github/workflows/guardrail-performance.yml)
compares baseline and candidate tools against the same indexed corpus in fresh
processes, with alternating repetitions. Its checker, runner and installed proof
context jobs record equal outputs, elapsed time and peak memory; the proof job
also runs the existing bounded native cache controls. Native census replay is an
explicit selection requiring complete retained inputs. These jobs supply no Host
or Guest CI verdict and do not replace either workflow's handoff.
Checker and proof-context RSS figures describe their worker process, not the sum
of its descendants or the full kernel check's residency.
After the unprofiled checker pairs, a separate candidate-only profiler run retains
diagnostic call costs. Its overhead supplies no baseline/candidate timing evidence.
The diagnostic-only input selects that worker without the paired comparisons;
it supplies no performance or checker-acceptance verdict.

The [retained comparison evidence](../docs/performance/tool-benchmarks-2026-10-30/README.md)
records the completed runner improvement, proof-context timing limits and rejected
checker runtime comparisons. A memory reduction alone does not satisfy the
complete checker runtime predicate. Later scanner revisions require their own
paired measurement; the earlier records do not establish their speed.

Additional shard changes, duration-based case ordering and new concurrent repair
sandboxes are not selected: they add scheduling state or concurrent corpus copies
without established equivalent-work benefit. Gate-wide pool changes likewise need
measured resource evidence. Generated-owner authentication retains its independent
live reads; sharing those decisions would need another freshness mechanism.
Canonical native-key memoization is not selected without a memory comparison on
the already large native graph. No persistent acceptance cache is added.

## October 29 Host CI scheduling

The [scheduling contract](../PLAN.md#host-ci-scheduling) keeps the existing test
population and acceptance checks while redistributing Ubuntu's mutation cases
over more runners. Windows's partitioning is unchanged. The workflow's matrix
owns the current counts; this change reduces the work assigned to each Ubuntu
runner and does not reduce total validation work.

Recent successful Host CI runs established the scheduling bottleneck:

| Baseline run | Tested revision | Longest gate step |
| --- | --- | --- |
| [40957610618](https://github.com/symbiogenesis/VerifiedOS/actions/runs/40957610618) | `ea919d9da6b29c7185ff588ad6008068fe32818e` | 978 s |
| [40953563369](https://github.com/symbiogenesis/VerifiedOS/actions/runs/40953563369) | `47e6afe5535ba868ea8d7f5dec5c2f73798cce87` | 1,041 s |
| [40935682020](https://github.com/symbiogenesis/VerifiedOS/actions/runs/40935682020) | `67bce3a2972189f24c60096a8f13e3be2961c72e` | 1,032 s |
| [40928723699](https://github.com/symbiogenesis/VerifiedOS/actions/runs/40928723699) | `d1617e1c50b9afcf1ef8b97e7bdfb8e455722647` | 963 s |
| [40914345900](https://github.com/symbiogenesis/VerifiedOS/actions/runs/40914345900) | `754f90f3550044d8c2cef6af9f189a2a7ac26256` | 1,114 s |

Each maximum belonged to an Ubuntu mutation-test shard. In the first listed run,
Ubuntu selftest members took 673.27–977.36 s while behavioral-test members took
28.10–50.15 s. Its unpartitioned Ubuntu checker spent 90.583 s in the pin group,
against 7.287 s in glyphs and 3.886 s in generated artifacts. These measurements
come from the normal hosted commands on their declared runner images and Python
3.14, using the automatic worker budgets. Each row is one run, on its own revision
and corpus. They identify the bottleneck but supply no paired speedup measurement
or claim of reduced checker cost. The integration handoff records the candidate's
revision, Host CI verdict and Guest CI dispatch; subsequent normal hosted timings
can show whether the scheduling change improves the critical path.

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

The proof comparison loads baseline CLI source from `62a39d76`; the candidate
change landed at `4e6d4e15`. Dependencies, wave order and witness decisions agree
across the complete source set. The index comparison timed a working tree based
on `1c7ac000` with three uncommitted candidate files, later accepted at
`d1d97788`; the complete checker reports agree. The template comparison loads
baseline `7a06adca` and times the reset candidate in a working tree based on
`bfc6d0d`, before the repair landed at `ecc9ace7`. It uses the same shared corpus
module and private fixture bytes, with separate caches. The edited-template
timing includes the cached-object completeness check and fresh index construction.

Full checker timing, unchanged-template timing and complete installed-library
context timing did not establish a reliable improvement. Pin-scanning rewrites
that measured slower were rejected. The adopted changes add no dependency and
retain fresh processes for checker mutations.

[Provenance notes](../docs/performance/tool-benchmarks-2026-09-19/README.md) and the archived
[proof script](../docs/performance/tool-benchmarks-2026-09-19/proof-benchmark.py) and
[proof samples](../docs/performance/tool-benchmarks-2026-09-19/proof-results.json),
[checker script](../docs/performance/tool-benchmarks-2026-09-19/checker-benchmark.py) and
[checker samples](../docs/performance/tool-benchmarks-2026-09-19/checker-results.json), and
[template script](../docs/performance/tool-benchmarks-2026-09-19/runner-final-benchmark.py) and
[template samples](../docs/performance/tool-benchmarks-2026-09-19/runner-final-results.json) are tracked.
CI-only replays write new results under ignored `out/performance-20260919/`
and measure the current checkout, so they do not recreate the historical input
population after later source edits. The native proof-cache and assumption-audit
regressions exercise actual Rocq behavior; these timing scripts do not issue proof
evidence. Changed gate inputs invalidate existing native proof receipts under the
normal proof-evidence contract.

## Parallel kernel execution

The proof launcher distributes independent changed dependency components across
bounded `rocqchk` processes. The smallest estimated batch also checks the complete
joint environment within its worker, so no separate consistency pass follows the
pool. Shared changed prerequisites remain in the same batch. Compiled size is a
scheduling heuristic; the source, object, gate and installed-library hashes still
own freshness. Unknown installed-library contexts use one checker process.

Automatic worker sizing uses the guest's usable logical CPUs and available memory
at each phase, with separate compile/audit and kernel budgets owned by
[`proofenv.proof_jobs`](vos/proofenv.py). The compile/audit budget is informed by the
[historical prover residency measurements](../docs/performance/toolchain-residency.md#the-prover-and-which-of-its-two-acts-the-device-performs).
The kernel budget is set at or above the measured peak of the one kernel worker that
checks every module on Guest CI's proofs runner, and `proof_jobs` records those
runs and the margin. A large core count therefore does not automatically launch a
memory-heavy checker on every core. Explicit `--jobs` overrides resource sizing.
Unknown memory uses conservative defaults, and help, metadata commands and complete
cache hits perform no capacity probe.

Every changed module must be an explicit recursive check target in one batch.
The launcher verifies complete, disjoint target coverage before starting workers.
The joint worker provisionally admits peer roots and their dependency closures;
the other workers check those roots recursively, with only validated cache hits
admitted there. Its own explicit targets override admissions. Consequently a
dependency skipped in the joint worker is covered by a peer or prior evidence.
The joint worker loads the full proof set, retaining dependency and universe
consistency across batches through the pinned checker's existing import path.
Its success is provisional until every peer succeeds silently and all recorded
bytes still match. Worker failures, diagnostics or changed objects refuse the
whole run even when the joint worker already succeeded. No partial worker result
is published or cached. The arrangement adds no trusted evaluator, library
exemption or persistent cache.

[Proof-cache regressions](tests/test_proofcache.py) specify bounded concurrent
execution, complete target coverage, shared-prerequisite placement, serial
fallbacks, refusal on worker failures and object changes, and joint consistency
within the same worker pool. A completed joint worker followed by a failed peer
must still fail, and malformed partitions cannot authorize provisional admissions.
The [environment cases](tests/test_env.py) cover phase-specific limits and distinguish
exhausted memory from an unavailable reading. The proof-cache cases cover explicit
overrides, independent phase sampling and commands that must avoid resource probes.
The [hosted proof-context comparisons](../docs/performance/tool-benchmarks-2026-10-30/README.md)
pass bounded native cache controls, including two-worker fixture checking,
contradictory-universe rejection, installed-library admission coverage and sealed
assumption refusals. POSIX workspace-lock and library-context fixtures also pass.
Their paired timings measure context construction rather than full proof-set
kernel execution. The [historical proof receipt](../proofs/proof-evidence.json)
owns its recorded full-gate timings; complete fresh serial and parallel
qualification remains outstanding under the acceptance conditions below.

Performance acceptance still requires equivalent fresh serial and parallel runs
on the same source and toolchain, with the worker count and input scope recorded.
Compare kernel and whole-gate elapsed time and peak memory, and exercise changed,
unchanged and unavailable-cache-context paths. The largest connected component,
unequal proof costs and repeated external-library reads can limit improvement;
compiled size does not predict conversion time exactly. No speedup is claimed
until the focused host/native regressions, stable host wave and comparison pass.

## September 26 source scans and context queries

The [recorded comparisons](../docs/performance/tool-benchmarks-2026-09-26/README.md)
retain baseline/candidate scripts, raw samples, input scope and source identities.
On Python 3.14.7 / Windows ARM64, identical complete checker reports took a median
3.529 seconds against 5.873 seconds before; source mutation enumeration took
1.055 seconds against 2.250 seconds. Complete Sail context API calls also improved.
These measurements exclude interpreter startup and do not claim a whole-gate speedup.

The [count checker](vos/checks/counts.py) searches for declared subjects before
applying the full count grammar at candidate offsets. Per-invocation document
snapshots share fence parsing, newline offsets and sorted claim intervals. Binary
search and prefix maximum endpoints decide containing claims without scanning every
claim for each count. Diagnostics retain their original positions and order.

The [mutation scanner](vos/mutate.py) searches lexical boundaries with the standard
library's compiled regular expressions and string searches. Slice operations mark
comments, strings and admitted regions. Each operator advances its newline-count
offset with its matches: line reporting scans at most the source length per
operator instead of rescanning the prefix for every mutant. Nested comments,
escapes, unterminated constructs and empty matches retain their behavior.

[Sail context](vos/sailcontext.py) validates each repeated source-path spelling
once per invocation with `functools.cache`, builds byte-line offsets with a compiled
newline search and skips search tokenization for exact-symbol queries. Every call
still reads and hashes all recorded owners and validates unselected records.
No dependency, persistent cache or proof-acceptance rule changes are introduced.

The [selftest runner](vos/cli/selftest.py) overlaps independent file placements
across directories while carrying a Git object store and constructing the initial
sandbox. It uses the configured setup worker budget. Later sandbox construction
already runs concurrently and uses one placement worker each, avoiding nested pools.
Copy fallback, private repair files, fresh checker processes and ordered reports
retain their existing behavior. Recorded setup medians with eight workers improved
from 0.988 to 0.425 seconds for the object store, 1.512 to 0.691 seconds for the first
sandbox, and 2.838 to 2.227 seconds for a complete warm template.

## September 27 JSONC scanning

The [recorded comparison](../docs/performance/tool-benchmarks-2026-09-27/README.md)
retains the source identities, replay script and raw samples. String-aware token
passes replace the JSONC reader's per-character Python state machine, preserving
exact output and error offsets. Configuration scanning and JSON parsing took a
median 4.842 ms against 13.534 ms before on the measured corpus. This is a
component improvement; no whole-gate or proof-compilation speedup is claimed.

## October 2 checker fixed cost

The [recorded comparison](../docs/performance/tool-benchmarks-2026-10-02/README.md)
retains the replay script and raw samples. Every checker run, and so every selftest
mutation case, regenerates the K-88 host rows in its generated group. The
[elastic-pool campaign](vos/elastic_pool_campaign.py) runs each command prefix once
and forks the pool for each continuation, and its observer checks each distinct
history once; [its test](tests/test_elastic_pool.py) holds the forked histories
equal to fresh replays. The [wire-format inventory](vos/wire_formats.py) reads and
blanks each proof source at most once, and blanks only a source whose text contains
a Narcissus name. The [test harness](tests/harness.py) runs one `git init` per
process and copies that repository into each sandbox tree, except a tree whose files
reach into `.git`. Component medians fell from 60.1 to 25.9 ms for the campaign,
186.1 to 100.7 ms for the inventory and 164.9 to 85.7 ms for a one-file sandbox
tree. No whole-gate speedup is claimed.
