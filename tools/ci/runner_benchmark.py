# SPDX-License-Identifier: Apache-2.0
"""Compare complete Markdown and proof-header repair work on GitHub Actions."""

import argparse
import hashlib
import importlib
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
    component_seconds: float
    setup_seconds: float
    cpu_seconds: float
    peak_rss_kb: float | None
    temporary_apparent_bytes: int
    findings: int
    report: list[str]
    bytes_unchanged: bool
    process_seconds: NotRequired[float]


def _peak_rss_kb() -> float | None:
    """The measured worker's process peak, unavailable on the Windows API route."""
    if sys.platform == "win32":
        return None
    import resource

    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value / 1024 if sys.platform == "darwin" else value


def _identity(root: Path) -> str:
    """Bind index membership, gitlinks and actual indexed source bytes."""
    index = subprocess.check_output(["git", "-C", str(root), "ls-files", "--stage", "-z"])
    digest = hashlib.sha256(index)
    for entry in index.split(b"\0"):
        if not entry:
            continue
        metadata, rel = entry.split(b"\t", 1)
        mode, _, stage = metadata.split()
        if stage != b"0":
            raise ValueError("benchmark refuses an unmerged index")
        if mode == b"160000":
            continue
        digest.update(rel + b"\0")
        with (root / os.fsdecode(rel)).open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


def worker(root: Path, tools: Path, kind: str, output: Path) -> None:
    """Fresh selected implementation, private sandboxes, original complete reports."""
    sys.path.insert(0, str(tools))
    prepared = time.perf_counter()
    cpu = time.process_time()
    temporary_bytes = 0
    unchanged = True
    if kind == "markdown":
        markdown = importlib.import_module("vos.markdownlint")
        setup = time.perf_counter() - prepared
        started = time.perf_counter()
        report = markdown.run(root)
        elapsed = time.perf_counter() - started
        findings, lines = report.findings, report.out
    else:
        selftest = importlib.import_module("vos.cli.selftest")
        with tempfile.TemporaryDirectory(prefix="vos-repair-comparison-") as temporary:
            estate = Path(temporary)
            template = estate / "template"
            selftest.build_template(root, template, 1)
            box = selftest.stand_up(template, estate / "repair", fix_ok=True)
            before = selftest._copied_bytes(box)
            setup = time.perf_counter() - prepared
            started = time.perf_counter()
            problems, lines = selftest._proof_header_repair_path(box)
            elapsed = time.perf_counter() - started
            after = selftest._copied_bytes(box)
            unchanged = before == after and all(
                (template / rel).read_bytes() == data for rel, data in before.items() if rel != ".git")
            findings = len(problems) + int(not unchanged)
            temporary_bytes = sum(path.stat().st_size for path in estate.rglob("*") if path.is_file())
    data: Sample = {
        "component_seconds": elapsed, "setup_seconds": setup,
        "cpu_seconds": time.process_time() - cpu, "peak_rss_kb": _peak_rss_kb(),
        "temporary_apparent_bytes": temporary_bytes,
        "findings": findings, "report": lines, "bytes_unchanged": unchanged,
    }
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _measure(root: Path, sources: dict[str, Path], scratch: Path, repetitions: int,
             samples: dict[str, dict[str, list[Sample]]]) -> None:
    reference: dict[str, tuple[int, list[str], bool]] = {}
    for iteration in range(repetitions):
        order = ("baseline", "candidate") if iteration % 2 == 0 else ("candidate", "baseline")
        for kind in ("markdown", "proof_headers"):
            for variant in order:
                result = scratch / f"{kind}-{variant}-{iteration}.json"
                started = time.perf_counter()
                subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                "--worker-tools", str(sources[variant]), "--root", str(root),
                                "--kind", kind, "--output", str(result)],
                               check=True, timeout=1800)
                sample = cast(Sample, json.loads(result.read_text(encoding="utf-8")))
                sample["process_seconds"] = time.perf_counter() - started
                samples[variant][kind].append(sample)
                verdict = sample["findings"], sample["report"], sample["bytes_unchanged"]
                reference.setdefault(kind, verdict)
                if verdict != reference[kind] or sample["findings"] or not sample["bytes_unchanged"]:
                    raise RuntimeError(f"{kind}: decisions, diagnostics or exact byte assertions differ")
                print(f"{kind} {variant} repetition {iteration + 1}: "
                      f"{sample['component_seconds']:.3f}s", flush=True)


def _check_inputs(root: Path, scope: str, revision: str) -> None:
    if (_identity(root) != scope
            or subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != revision
            or subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)):
        raise RuntimeError("benchmark inputs changed")


def compare(root: Path, base: str, output: Path, repetitions: int) -> None:
    """Alternate both implementations against one clean, hash-bound indexed corpus."""
    if re.fullmatch(r"[0-9a-f]{40}", base) is None:
        raise ValueError("performance base must be a full lowercase commit SHA")
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if base == revision or repetitions < 2:
        raise ValueError("benchmark requires a proper ancestor and at least two repetitions")
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", base, revision],
                   check=True, capture_output=True)
    if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
        raise ValueError("benchmark requires a clean indexed checkout")
    scope = _identity(root)
    samples: dict[str, dict[str, list[Sample]]] = {
        variant: {kind: [] for kind in ("markdown", "proof_headers")}
        for variant in ("baseline", "candidate")}
    failure = ""
    (root / "out").mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="vos-runner-comparison-", dir=root / "out") as temporary:
            scratch = Path(temporary)
            archive = scratch / "tools.tar"
            subprocess.run(["git", "-C", str(root), "archive", "--format=tar", "-o", str(archive),
                            base, "tools"], check=True)
            with tarfile.open(archive) as source:
                source.extractall(scratch / "baseline", filter="data")
            sources = {"baseline": scratch / "baseline" / "tools", "candidate": root / "tools"}
            _measure(root, sources, scratch, repetitions, samples)
        _check_inputs(root, scope, revision)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        failure = f"{type(exc).__name__}: {exc}"
    data = {
        "baseline_revision": base, "candidate_revision": revision,
        "corpus_revision": revision, "indexed_inputs_sha256": scope,
        "python": sys.version, "platform": platform.platform(), "workers": 1,
        "repetitions": repetitions, "command": sys.argv,
        "scope": {"markdown": "complete indexed Markdown command and ordered report",
                  "proof_headers": "complete indexed proof-header repair sweep in private full-corpus sandboxes; exact source and template bytes preserved"},
        "report_identical": not failure, "byte_assertions_identical": not failure,
        "failure": failure,
        "median_component_seconds": {
            variant: {kind: statistics.median(s["component_seconds"] for s in values) if values else None
                      for kind, values in parts.items()} for variant, parts in samples.items()},
        "samples": samples,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["median_component_seconds"], indent=2), flush=True)
    if failure:
        raise RuntimeError(failure)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--worker-tools", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--kind", choices=("markdown", "proof_headers"), default="markdown", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("runner performance comparisons run only on GitHub Actions")
    if args.worker_tools is not None:
        worker(args.root.resolve(), args.worker_tools.resolve(), args.kind, args.output.resolve())
    elif args.base is not None:
        compare(args.root.resolve(), args.base, args.output.resolve(), args.repetitions)
    else:
        parser.error("--base is required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
