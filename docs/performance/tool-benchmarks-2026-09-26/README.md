# September 26, 2026 Python tooling measurements

These records compare the baseline `69e1d5f6322f80186a3de59e5f03bb248c84616e`
with candidate implementations on identical inputs. Python 3.14.7 ran on Windows
11 ARM64. The scripts alternate baseline and candidate order and require equal
results. Other independent Python work was active on the machine; these local
medians are not predictions of GitHub runner or complete gate duration.

| Work measured | Baseline median | Candidate median | Repetitions per implementation | Workers |
| --- | --- | --- | --- | --- |
| Unregistered count scan | 3.047 s | 0.744 s | 7 | 1 |
| Complete checker, in process | 5.873 s | 3.529 s | 5 | 1 |
| Mutation population over tracked sources | 2.250 s | 1.055 s | 7 | 1 |
| Exact Sail symbol context | 0.383 s | 0.177 s | 9 | 1 |
| Sail context search | 0.424 s | 0.286 s | 9 | 1 |
| Sail reference context | 0.284 s | 0.174 s | 9 | 1 |

The [checker script](checker-benchmark.py) and [samples](checker-results.json)
compare `unheld_counts` while using identical current helper modules, files and
index membership. The input has 190 Markdown documents and 16 declared count
scopes. All complete reports agree and contain no findings. Complete-checker
measurements include corpus loading and every checker group, with imports warmed;
they exclude interpreter and uv startup. The JSON records the candidate source
digest, baseline revision, scope, working-tree status and raw timings.

The [mutation script](mutate-benchmark.py) and [samples](mutate-results.json)
compare every field of all 25,510 mutants from 191 tracked Sail/Gallina sources.
Sixty thousand deterministic randomized mask comparisons also cover malformed
comments, strings and the existing unknown-lane fallback. On synthetic inputs,
four times as many repeated definition lines increased candidate runtime from
0.019 to 0.082 seconds; the baseline increased from 0.074 to 0.885 seconds.
These timings include complete population generation, but no compiler or prover.
The source scanner landed as `10d589c5b8d4dcc602e3201d4a023f29b9f825ff`.
The JSON's command is the equivalent archived invocation; the original invocation
used `python out/performance-20260926/mutate-benchmark.py --out
out/performance-20260926/mutate-results.json` before archival.

The [Sail context script](context-benchmark.py) and [samples](context-results.json)
compare complete API reports for `symbol capToBits`, `search capability tag` and
`references capToBits`. Each invocation validates 121 owners and examines 6,000
declarations and 12,346 references. The separate owner-read component fell from
0.156 to 0.113 seconds. Complete API timing includes source reads, content hashing,
bundle parsing, all declaration/reference validation, filtering and excerpts;
it excludes interpreter startup and CLI bootstrap. The parser landed unchanged
as `784119697f4064c4da90669c847403be74b0a0a1` and was integrated as
`67113d2d`. Measurements preceded the commit, so the JSON distinguishes the
then-current HEAD from the exact candidate source digest.

Run these archived scripts with the checkout's managed interpreter. They discover
the checkout and write replay results under ignored `out/performance-20260926/`.
Archival changed only script root/output handling and removed an unused import;
saved samples remain unchanged. Replays combine baseline implementation code from
Git with the current inputs and helpers, so later changes can produce different
measurements or invalidate a historical API. Source digests identify the measured
working-tree bytes; Git newline normalization can change byte digests on checkout.

Focused tests exercise malformed input, lexical and UTF-8 boundaries, CRLF and
EOF offsets, edits between calls, exact report ordering and failure recovery.
Final acceptance uses Host CI and both Guest CI lanes under the repository's
[validation handoff](../../../AGENTS.md#tool-execution-and-validation).

The [runner component script](runner-benchmark.py) and
[samples](runner-results.json) compare object-store placement, initial sandbox
construction and complete warm-template construction. Seven alternating repetitions
use the same immutable template of 2,869 files including Git metadata, with eight
setup workers. Medians are respectively 0.988 to 0.425 seconds, 1.512 to 0.691 seconds,
and 2.838 to 2.227 seconds. The baseline field identifies the precommit HEAD;
the measured candidate changes landed as `501271ba1815a328e87bcad26e212d27bbbdbef2`
and were integrated as `a61c682d`. The
[selected-selftest script](runner-e2e-benchmark.py) and
[samples](runner-e2e-results.json) include setup, the pristine baseline, five K-52
mutants, registry coverage and cleanup. Three alternating repetitions with
`--jobs 5` returned equal ordered diagnostics and successful verdicts throughout.
The medians were 19.098 and 18.256 seconds. That small difference, on a shared
machine, supports no material regression rather than a general whole-suite speedup
claim. The existing nonrepair run has six sandbox slots with that configured
worker count; this optimization leaves mutation scheduling unchanged.

Runner replays create unique ignored output subdirectories and private caches.
Their saved commands retain the original lane paths as historical provenance;
archived scripts discover their current checkout. Component setup falls outside
the placement timers. The end-to-end replay may omit `--seed-cache` to prepare its
own seed before timing. These scripts exercise selected mutation cases, not the
complete host or guest acceptance suites.

The checker candidate was committed unchanged as
`0c208b59194291071c2c88069a77b3ff89c388b1`, integrated as `a3433dc3`.
Focused K-26 mutation testing killed its selected mutant; the other cases were
unselected and supply no mutation evidence from that run.
