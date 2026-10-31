# SPDX-License-Identifier: Apache-2.0
"""Paired installed proof-context measurements and native controls on Actions."""

import argparse
import hashlib
import importlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import NotRequired, TypedDict, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci.archive_scan_benchmark import validate_base


class Sample(TypedDict):
    seconds: float
    context_sha256: str
    peak_rss_kib: int
    process_seconds: NotRequired[float]


def worker(root: Path, implementation: Path, work: Path, output: Path) -> None:
    """Hash the actual installed context afresh, without compiling any project proof."""
    if sys.platform == "win32":
        raise RuntimeError("native proof identity requires a Linux worker")
    import resource

    sys.path.insert(0, str(implementation))
    gate = importlib.import_module("vos.cli.proofs")
    work.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    context = gate._cache_context(work, gate._sources(root))
    seconds = time.perf_counter() - started
    if context is None:
        raise RuntimeError("the installed context cannot authorize proof reuse")
    digest = hashlib.sha256(json.dumps(context, sort_keys=True).encode("utf-8")).hexdigest()
    output.write_text(json.dumps({"seconds": seconds, "context_sha256": digest,
                                  "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
                      + "\n", encoding="utf-8")


def native_controls() -> None:
    """Run existing bounded native controls explicitly with the Rocq-only switch."""
    from tests import test_proofcache  # noqa: PLC0415

    for case in test_proofcache.cases():
        if case.lane in {"guest", "toolchain"}:
            print(f"native proof-cache control: {case.name}", flush=True)
            case.fn()


def compare(root: Path, base: str, output: Path) -> None:
    revision = validate_base(root, base)
    if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
        raise ValueError("comparison requires a clean indexed checkout")
    samples: dict[str, list[Sample]] = {"baseline": [], "candidate": []}
    output.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint(status: str) -> None:
        record = {"baseline_revision": base, "candidate_revision": revision,
                  "python": sys.version, "platform": platform.platform(),
                  "workers": 1, "repetitions": 2, "status": status,
                  "native_controls": "passed" if status == "complete" else "pending",
                  "samples": samples,
                  "median_seconds": {name: statistics.median(sample["seconds"] for sample in rows)
                                     for name, rows in samples.items() if rows}}
        pending = output.with_suffix(".pending")
        pending.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        pending.replace(output)

    checkpoint("measuring")
    (root / "out").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vos-proof-identity-", dir=root / "out") as temporary:
        scratch = Path(temporary)
        archive = scratch / "tools.tar"
        subprocess.run(["git", "-C", str(root), "archive", "--format=tar", "-o", str(archive),
                        base, "tools"], check=True)
        with tarfile.open(archive) as stream:
            stream.extractall(scratch / "baseline", filter="data")
        implementations = {"baseline": scratch / "baseline/tools", "candidate": root / "tools"}
        expected = ""
        for repetition in range(2):
            order = ("baseline", "candidate") if repetition == 0 else ("candidate", "baseline")
            for name in order:
                sample_path = scratch / "sample.json"
                started = time.perf_counter()
                subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker-tools",
                                str(implementations[name]), "--root", str(root), "--work",
                                str(scratch / "context"), "--output", str(sample_path)],
                               check=True, timeout=600)
                sample = cast(Sample, json.loads(sample_path.read_text(encoding="utf-8")))
                sample["process_seconds"] = time.perf_counter() - started
                current = sample["context_sha256"]
                if expected and expected != current:
                    raise RuntimeError("proof context bytes or identity decisions differ")
                expected = current
                samples[name].append(sample)
                checkpoint("measuring")
                print(f"{name}: {sample['seconds']:.3f}s", flush=True)
        checkpoint("native-controls")
        native_controls()
    if (subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            != revision or subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain"], text=True)):
        raise RuntimeError("comparison inputs changed")
    checkpoint("complete")


def main() -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-tools", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--work", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("installed proof-context measurements run only on GitHub Actions")
    if args.worker_tools is not None and args.work is not None:
        worker(args.root.resolve(), args.worker_tools.resolve(), args.work.resolve(), args.output)
    elif args.base is not None:
        compare(args.root.resolve(), args.base, args.output)
    else:
        parser.error("--base is required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
