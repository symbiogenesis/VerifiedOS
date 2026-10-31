# SPDX-License-Identifier: Apache-2.0
"""Compare checker implementations on one immutable corpus, on Actions alone."""

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import NotRequired, TypedDict, cast


class Sample(TypedDict):
    wall_seconds: float
    units: list[dict[str, object]]
    findings: int
    report: list[str]
    process_seconds: NotRequired[float]
    peak_rss_kib: NotRequired[int | None]


def validate_base(root: Path, base: str) -> str:
    """Require a proper committed ancestor, never a revision expression."""
    if re.fullmatch(r"[0-9a-f]{40}", base) is None:
        raise ValueError("performance base must be a full lowercase commit SHA")
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if base == revision:
        raise ValueError("performance base must precede the tested revision")
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", base, revision],
                   check=True, capture_output=True)
    return revision


def worker(root: Path, tools: Path, output: Path) -> None:
    """Fresh interpreter and explicit corpus root for each measured implementation."""
    sys.path.insert(0, str(tools))
    spec = importlib.util.spec_from_file_location("archive_benchmark_check", tools / "check.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("checker module is unavailable")
    checker = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = checker
    spec.loader.exec_module(checker)
    # Resolve from the selected implementation, after installing its tools path.
    timings = importlib.import_module("vos.timings")
    clock = timings.Clock(cpu=True)
    started = time.perf_counter()
    report = checker.run(root, clock=clock)
    elapsed = time.perf_counter() - started
    peak_rss: int | None = None
    if sys.platform == "linux":
        import resource

        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output.write_text(json.dumps({"wall_seconds": elapsed, "units": clock.units(),
                                  "findings": report.findings, "report": report.out,
                                  "peak_rss_kib": peak_rss},
                                 indent=2) + "\n", encoding="utf-8")


def compare(root: Path, base: str, output: Path, repetitions: int) -> None:
    """Load baseline tools only; both versions read the unchanged candidate corpus."""
    revision = validate_base(root, base)
    if repetitions < 2:
        raise ValueError("at least two repetitions are required")
    if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
        raise ValueError("benchmark requires a clean indexed checkout")
    samples: dict[str, list[Sample]] = {"baseline": [], "candidate": []}
    # Baseline modules resolve repository-owned data from their __file__ ancestry.
    # Keep their sources below the real ignored output root so those imports find
    # the same corpus as the explicit checker argument, without patching a reader.
    (root / "out").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vos-archive-comparison-", dir=root / "out") as temporary:
        scratch = Path(temporary)
        archive = scratch / "tools.tar"
        subprocess.run(["git", "-C", str(root), "archive", "--format=tar", "-o", str(archive),
                        base, "tools"], check=True)
        with tarfile.open(archive) as source:
            source.extractall(scratch / "baseline", filter="data")
        tools_paths = {"baseline": scratch / "baseline" / "tools", "candidate": root / "tools"}
        reference: tuple[int, list[str]] | None = None
        for iteration in range(repetitions):
            order = ("baseline", "candidate") if iteration % 2 == 0 else ("candidate", "baseline")
            for variant in order:
                result_path = scratch / f"{variant}-{iteration}.json"
                started = time.perf_counter()
                subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker-tools",
                                str(tools_paths[variant]), "--root", str(root),
                                "--output", str(result_path)], check=True, timeout=600)
                sample = cast(Sample, json.loads(result_path.read_text(encoding="utf-8")))
                sample["process_seconds"] = time.perf_counter() - started
                verdict = (sample["findings"], sample["report"])
                if reference is None:
                    reference = verdict
                if verdict != reference or sample["findings"]:
                    raise RuntimeError("baseline/candidate decisions or diagnostics differ")
                samples[variant].append(sample)
                print(f"{variant} repetition {iteration + 1}: {sample['wall_seconds']:.3f}s",
                      flush=True)
    if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != revision:
        raise RuntimeError("revision changed during comparison")
    if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
        raise RuntimeError("corpus changed during comparison")
    report = reference[1] if reference is not None else []
    data = {
        "baseline_revision": base, "candidate_revision": revision,
        "corpus_revision": revision, "python": sys.version, "platform": platform.platform(),
        "workers": 1, "repetitions": repetitions,
        "command": "python tools/ci/archive_scan_benchmark.py --base SHA --output PATH",
        "report_identical": True, "report_sha256": hashlib.sha256(
            "\n".join(report).encode("utf-8")).hexdigest(),
        "median_seconds": {variant: statistics.median(s["wall_seconds"] for s in values)
                           for variant, values in samples.items()},
        "samples": samples,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["median_seconds"], indent=2), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--worker-tools", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("native archive comparison runs only on GitHub Actions")
    if args.worker_tools is not None:
        worker(args.root.resolve(), args.worker_tools.resolve(), args.output.resolve())
    elif args.base is not None:
        compare(args.root.resolve(), args.base, args.output.resolve(), args.repetitions)
    else:
        parser.error("--base is required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
