import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

root = next(path for path in Path(__file__).resolve().parents
            if (path / "tools" / "check.py").is_file())
output = root / "out" / "performance-20260919"
output.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / "tools"))
import check
from vos import corpus
from vos.checks import generated

optimized = corpus.staged_blobs
paths = [row.path for row in generated.GENERATED if row.lane != "host"]

def separate(root, paths):
    return {path: corpus.staged_bytes(root, path) for path in paths}

def measure(function):
    start = time.perf_counter()
    value = function()
    return time.perf_counter() - start, value

data = {
    "python": sys.version,
    "platform": platform.platform(),
    "revision": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
    "uncommitted": subprocess.check_output(["git", "-C", str(root), "diff", "--name-only"], text=True).splitlines(),
    "workers": 1,
    "command": "python tools/performance/2026-09-19/checker-benchmark.py",
    "repetitions": 7,
    "blob_paths": paths,
    "samples": {name: [] for name in ("separate_blobs", "batched_blobs", "full_corpus_for_index", "index_only", "checker_separate", "checker_batch")},
}
samples = data["samples"]
reference = separate(root, paths)
if optimized(root, paths) != reference:
    raise RuntimeError("batch byte identity changed")
original_report = None
for iteration in range(data["repetitions"]):
    pairs = [("separate_blobs", lambda: separate(root, paths)),
             ("batched_blobs", lambda: optimized(root, paths)),
             ("full_corpus_for_index", lambda: corpus.load(root).gitlinks),
             ("index_only", lambda: corpus.read_index(root).gitlinks)]
    if iteration % 2:
        pairs.reverse()
    for name, function in pairs:
        elapsed, _ = measure(function)
        samples[name].append(elapsed)
    for name, factory in (("checker_separate", separate), ("checker_batch", optimized)) if iteration % 2 == 0 else (("checker_batch", optimized), ("checker_separate", separate)):
        corpus.staged_blobs = factory
        elapsed, report = measure(lambda: check.run(root))
        samples[name].append(elapsed)
        if report.findings:
            raise RuntimeError("checker findings: " + "\n".join(report.out))
        if original_report is None:
            original_report = report.out
        elif report.out != original_report:
            raise RuntimeError("report identity changed")
    print("iteration", iteration + 1, "complete", flush=True)
corpus.staged_blobs = optimized
data["median_seconds"] = {name: statistics.median(values) for name, values in samples.items()}
data["report_identical"] = True
data["findings"] = 0
(output / "replay-checker-results.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(json.dumps(data["median_seconds"], indent=2))
