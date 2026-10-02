# Checker fixed-cost comparison

The [replay script](checker-benchmark.py) and [raw samples](checker-results.json)
compare three components at `d1474a46ecf5a615a69d0b4d2e5305861229c17f` with the
replacements measured at `dab4847113eaf9b98c863896a6cf45282281c826`. Every checker
run regenerates the elastic-pool campaign and the wire-format inventory in its
generated group; the test harness builds a sandbox tree for each checker test case.

The run used CPython 3.14.7 on Windows ARM64 with Git 2.56.0, one process, one
worker and seven alternating baseline/candidate samples after one discarded warm-up
per component. Before timing, the script confirms equal campaign histories, rendered
campaign text, wire-format inventory entries and emitted inventory. The candidate
harness's one `git init` per process ran before timing.

| Component, median wall time | Baseline | Candidate |
| --- | --- | --- |
| `elastic_pool_campaign.histories()` | 60.1 ms | 25.9 ms |
| `wire_formats.load(root)` | 186.1 ms | 100.7 ms |
| `sandbox_tree({'x.md': ''})` | 164.9 ms | 85.7 ms |

These are component timings on a development machine that may have been running
other work. They exclude interpreter startup and do not establish a whole-gate
speedup. A sandbox tree's Git work runs in child processes, so its process CPU time
does not show the change.

Run `python docs/performance/tool-benchmarks-2026-10-02/checker-benchmark.py` from
this checkout to compare the historical baseline with current source. Replay writes
fresh results to ignored `out/checker-fixed-cost/results.json` and does not
overwrite the archived measurements. Later source changes produce a different
comparison.
