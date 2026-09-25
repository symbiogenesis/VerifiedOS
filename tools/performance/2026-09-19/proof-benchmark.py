"""Read-only old/new proof metadata benchmark and corpus equivalence check."""
import dataclasses
import json
import platform
import statistics
import shutil
import subprocess
import sys
import time
import types
import tempfile
from pathlib import Path

ROOT = next(path for path in Path(__file__).resolve().parents if (path / "tools" / "run.py").is_file() and (path / ".git").exists())
BASE = "62a39d76b4946638043d5d780b0759d9241f99aa"
OUTPUT = ROOT / "out" / "performance-20260919"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools"))
from vos import proofs, receipts
from vos.cli import proofs as after

old = subprocess.run(["git", "-C", str(ROOT), "show", BASE + ":tools/vos/cli/proofs.py"],
                     capture_output=True, check=True, encoding="utf-8").stdout
before = types.ModuleType("proof_gate_before")
sys.modules[before.__name__] = before
exec(compile(old, "proof_gate_before.py", "exec"), before.__dict__)
sources = sorted((ROOT / "proofs").glob("*.v"))

def old_pass():
    needs = {source.name: sorted(proofs.local_requires(source, {p.stem for p in sources}))
             for source in sources}
    waves = [[path.name for path in wave] for wave in proofs.waves(sources)]
    found = {source.name: dataclasses.asdict(before.scan_witnesses(
        source.read_text(encoding="utf-8"), before._imported(source, sources))) for source in sources}
    return needs, waves, found

def new_pass():
    analysis = after.ProofAnalysis.read(sources)
    return ({source.name: sorted(path.stem for path in needs)
             for source, needs in analysis.index.needs.items()},
            [[path.name for path in wave] for wave in analysis.index.ordered],
            {source.name: dataclasses.asdict(found) for source, found in analysis.witnesses.items()})

expected = old_pass()
assert expected == new_pass(), "corpus metadata differs"
samples = {"before": [], "after": []}
for index in range(7):
    for name, run in (("before", old_pass), ("after", new_pass)) if index % 2 else (
            ("after", new_pass), ("before", old_pass)):
        start = time.perf_counter()
        actual = run()
        samples[name].append(time.perf_counter() - start)
        assert actual == expected, "corpus metadata differs"
result = {"baseline_revision": BASE, "python": sys.version, "platform": platform.platform(),
          "scope": "all proof source dependencies, waves and record witnesses",
          "source_count": len(sources), "workers": 1, "repetitions": 7,
          "corpus_equal": True, "seconds": samples,
          "medians_seconds": {name: statistics.median(values) for name, values in samples.items()}}
print(json.dumps(result, indent=2))
(OUTPUT / "replay-proof-results.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8")

with tempfile.TemporaryDirectory(prefix="synthetic-reuse-benchmark-", dir=OUTPUT) as temporary:
    work = Path(temporary)
    (work / "proofs").mkdir()
    products = []
    artifacts = {}
    for source in sources:
        staged = work / "proofs" / source.name
        shutil.copyfile(source, staged)
        product = staged.with_suffix(".vo")
        product.write_bytes(b"synthetic benchmark object; not Rocq evidence: " + source.name.encode())
        products.append(product)
        artifacts[source.name] = {"requires": sorted(proofs.local_requires(source, {s.stem for s in sources})),
            "symbols": [{"name": source.stem + ".fixture", "type": "True", "claims": [], "assumptions": []}]}
    inputs = after._inputs(ROOT, sources)
    context = {"synthetic_benchmark": True}
    toolchain = {"synthetic_benchmark": True}
    receipts.write(work / after.RECEIPT, {
        "schema": after.RECEIPT_SCHEMA, "status": "passed", "kernel_recheck": "passed",
        "toolchain": toolchain, "cache_context": context, "declared_assumptions": [],
        "inputs": inputs, "outputs": receipts.snapshot(work, products), "artifacts": artifacts,
        "kernel_evidence": {"mode": "full", "checked": sorted(s.stem for s in sources),
                            "reused": [], "basis_sha256": None}})
    samples = {"before": [], "after": []}
    for index in range(7):
        for name, module in (("before", before), ("after", after)) if index % 2 else (
                ("after", after), ("before", before)):
            start = time.perf_counter()
            reused = module._reusable(ROOT, work, sources, inputs, toolchain, context)
            samples[name].append(time.perf_counter() - start)
            assert set(reused) == {s.stem for s in sources}, "synthetic cache missed a source"
    result["synthetic_all_reusable_seconds"] = samples
    result["synthetic_all_reusable_medians"] = {name: statistics.median(values) for name, values in samples.items()}
    print(json.dumps({"synthetic_all_reusable_medians": result["synthetic_all_reusable_medians"]}, indent=2))
    (OUTPUT / "replay-proof-results.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
