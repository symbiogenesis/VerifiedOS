# September 19, 2026 component measurements

These saved samples support the four medians in
[the performance record](../../performance.md#recorded-component-measurements).
The three `*-results.json` files preserve the original values; Git normalizes
their line endings under the repository text rule. The paired scripts have only
their stale scratch/output paths changed to write replay results under
`out/performance-20260919/`; that ignored directory is separate from this archive.
Python 3.14.7 ran on Windows 11 ARM64. Unrelated guest proof jobs were active.
The scripts time components on shared inputs, not complete CI gates or proof
checking.

| Script and saved result | Historical input and code scope |
| --- | --- |
| [proof-benchmark.py](proof-benchmark.py), [proof-results.json](proof-results.json) | The baseline CLI source is loaded from `62a39d76b4946638043d5d780b0759d9241f99aa`; the candidate change landed in `4e6d4e15c127037121beca761ebffa7155e0eb5a`. The script reads the running checkout's proof corpus and shared helper modules, and verifies equal dependency, wave, and witness outputs. The synthetic cache fixture is not Rocq evidence. |
| [checker-benchmark.py](checker-benchmark.py), [checker-results.json](checker-results.json) | The recorded checkout was `1c7ac000d1cade95a8ab863f0b20fe7484b92ce9` with uncommitted edits to `tools/tests/test_corpus.py`, `tools/vos/checks/generated.py`, and `tools/vos/corpus.py`. Those paths later landed in `d1d977884bdb084bbe9b5973444c05444ae292b2`. The exact timed working-tree bytes are not pinned by the JSON. Batch and separate reads returned identical bytes and checker reports with zero findings. The full checker median was 3.388 s with separate reads and 3.642 s with batch reads, so this run does not support a whole-checker speedup. |
| [runner-final-benchmark.py](runner-final-benchmark.py), [runner-final-results.json](runner-final-results.json) | The baseline CLI source is loaded from `7a06adca16388873e26d02d59200b1acb87f13ec`. The candidate was a working tree based on `bfc6d0d00c80f93e94cc8212b4be244ea4f51cd9`; the reset repair later landed in `ecc9ace7d8bd5d38715e31116a082b60bc9e6389`. The published 5.277 s to 3.996 s comparison is the `baseline` to `reset` pair. `guarded` is an unlanded experimental source splice, not the accepted implementation. The script imports other modules from the running checkout. |

For an exploratory replay, run a script from the repository root with the
checkout's managed Python, for example
`python tools/performance/2026-09-19/proof-benchmark.py`. Each script discovers
its checkout. The proof and checker scripts write `replay-*-results.json` under
`out/performance-20260919/`; the runner writes `results.json` in a unique
`replay-runner-*` subdirectory there. The proof and runner scripts combine
historical source text with the current checkout's code and inputs; the checker
script compares the current checkout's readers. Later source changes can change
results or make a script's old API or exact text splice fail. The saved JSON is
the historical measurement record, and replay timings are new measurements.
