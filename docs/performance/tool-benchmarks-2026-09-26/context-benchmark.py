# SPDX-License-Identifier: Apache-2.0
"""Compare complete Sail context reports against the frozen baseline on this host."""

import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / "tools/vos/sailcontext.py").is_file())
sys.path.insert(0, str(ROOT / "tools"))

from vos import sailbundle, sailcontext  # noqa: E402

BASE = "69e1d5f6322f80186a3de59e5f03bb248c84616e"
REPETITIONS = 9


def baseline() -> types.ModuleType:
    source = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", BASE + ":tools/vos/sailcontext.py"], text=True)
    module = types.ModuleType("context_baseline")
    sys.modules[module.__name__] = module
    exec(compile(source, "baseline/sailcontext.py", "exec"), module.__dict__)  # noqa: S102
    return module


def timed(callback: Callable[[], object]) -> tuple[float, object]:
    start = time.perf_counter()
    result = callback()
    return time.perf_counter() - start, result


def compare(old: Callable[[], object], new: Callable[[], object]) -> dict[str, Any]:
    expected = old()
    if expected != new():
        raise RuntimeError("baseline and candidate outputs differ")
    samples: dict[str, list[float]] = {"before": [], "after": []}
    for repetition in range(REPETITIONS):
        callbacks = (("before", old), ("after", new))
        if repetition % 2:
            callbacks = tuple(reversed(callbacks))
        for label, callback in callbacks:
            elapsed, result = timed(callback)
            if result != expected:
                raise RuntimeError(f"{label} changed its output")
            samples[label].append(elapsed)
    return {"samples_seconds": samples,
            "median_seconds": {label: statistics.median(values)
                               for label, values in samples.items()},
            "equal_outputs": True}


def owner_snapshot(module: types.ModuleType) -> object:
    _, digest, owners = module._read(ROOT)
    return digest, {rel: (owner.raw, owner.sha256, owner.lines)
                    for rel, owner in owners.items()}


def main() -> None:
    old = baseline()
    results: dict[str, Any] = {
        "baseline_revision": BASE,
        "candidate_revision": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "candidate_sha256": hashlib.sha256(
            (ROOT / "tools/vos/sailcontext.py").read_bytes()).hexdigest(),
        "python": sys.version, "platform": platform.platform(),
        "command": "python out/performance-parsers/context_benchmark.py",
        "repetitions": REPETITIONS, "workers": 1,
        "bundle_sha256": hashlib.sha256((ROOT / sailbundle.BUNDLE).read_bytes()).hexdigest(),
        "operations": {}}
    for operation, query in (("symbol", "capToBits"), ("search", "capability tag"),
                             ("references", "capToBits")):
        result = compare(lambda: old.context(ROOT, operation, query),
                         lambda: sailcontext.context(ROOT, operation, query))
        report = sailcontext.context(ROOT, operation, query)
        result["sources_checked"] = report["sources_checked"]
        result["coverage"] = report["coverage"]
        result["total_matches"] = report["total_matches"]
        results["operations"][operation] = result
    results["read_component"] = compare(
        lambda: owner_snapshot(old), lambda: owner_snapshot(sailcontext))
    output = ROOT / "out/performance-20260926/replay-context-results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="")
    print(json.dumps({key: value["median_seconds"]
                      for key, value in results["operations"].items()}, indent=2))
    print(output)


if __name__ == "__main__":
    main()
