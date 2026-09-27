# JSONC scanner comparison

The [replay script](jsonc-benchmark.py) and [raw samples](jsonc-results.json)
compare the scanner at `6daf827225308987fbc885ef1196e6c3f3cca028` with the
replacement committed as `b0d42d7a22445baefb6fe868a5feb0940bb0b495`. Measurement
ran immediately before the candidate commit; the results bind its source bytes.
The original command was `python out/simplify-json/benchmark.py` in the isolated
tooling worktree.

The run used CPython 3.14.7 on Windows ARM64, one worker, nine alternating
baseline/candidate samples and forty corpus traversals per sample. Each traversal
reads the same in-memory text from the model configuration files listed in the
results. Source scanning has identical output on those files and on the recorded
exhaustive and deterministic malformed-input population. Parsing uses the same
standard-library JSON decoder for both implementations.

| Component, median per corpus traversal | Baseline | Candidate |
| --- | --- | --- |
| Comment and trailing-comma scanning | 12.600 ms | 3.436 ms |
| Scanning and JSON parsing | 13.534 ms | 4.842 ms |

These are component timings, excluding interpreter startup and file I/O. They
do not establish a whole-gate or proof-compilation speedup. The source refactor
keeps string contents, newline positions, malformed-input behavior and every
output offset unchanged; it adds no package or persistent cache.

Run `python docs/performance/tool-benchmarks-2026-09-27/jsonc-benchmark.py`
from this checkout to compare the historical baseline with current source.
Replay writes fresh results to ignored `out/simplify-json/results.json` and
does not overwrite the archived measurements. Later source or configuration
changes produce a different comparison.
