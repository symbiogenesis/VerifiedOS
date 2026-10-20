#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""CI-only qualification of an exact Sail runtime patch against a pinned base.

The payload is source, never credentials. Before executing it, the route verifies
its digest, limits its paths, and retains the complete patch and source identities.
This instrument supplies focused runtime evidence, not model or proof acceptance.
"""

import base64
import gzip
import hashlib
import io
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Any, TypedDict

BASE = "8857cacf492c71b537e879a862ab5b62ba4abf81"
URL = "https://codeload.github.com/rems-project/sail/tar.gz/" + BASE
REVISION = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
PATHS = {"lib/rts.c", "lib/rts.h", "test/oneoff/rts_memory/test.c",
         "test/oneoff/rts_memory/test.sh"}
REPETITIONS = 7
FLAGS = ["-std=gnu11", "-O3", "-DNDEBUG", "-fno-lto"]


class Sample(TypedDict):
    case: str
    bytes: int
    iterations: int
    seconds: float
    checksum: str


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8", newline="")


def extract(archive: Path, destination: Path) -> Path:
    destination.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    entries = list(destination.iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        raise ValueError("source archive must have one root")
    return entries[0]


def parse_samples(stdout: str) -> list[Sample]:
    rows: list[Sample] = []
    for line in stdout.splitlines():
        row = json.loads(line)
        if (not isinstance(row, dict) or set(row) != {"case", "bytes", "iterations", "seconds", "checksum"}
                or not isinstance(row["case"], str) or not re.fullmatch(r"[A-Za-z0-9_]+", row["case"])
                or type(row["bytes"]) is not int or row["bytes"] <= 0
                or type(row["iterations"]) is not int or row["iterations"] <= 0
                or type(row["seconds"]) not in (int, float)
                or not math.isfinite(row["seconds"]) or row["seconds"] <= 0
                or not isinstance(row["checksum"], str)
                or not re.fullmatch(r"[0-9a-f]{16}", row["checksum"])):
            raise ValueError("malformed benchmark sample")
        rows.append(Sample(case=row["case"], bytes=row["bytes"], iterations=row["iterations"],
                           seconds=float(row["seconds"]), checksum=row["checksum"]))
    expected = {f"buffer_{operation}_{layout}_{size}"
                for operation in ("read", "write")
                for layout, sizes in (("sparse8", (1, 8, 16, 64, 4096, 1048576)),
                                      ("boundary", (64, 4096, 1048576)), ("head", (8, 4096)))
                for size in sizes}
    expected.update(f"fast_read_ram_{layout}_{size}" for layout in ("head", "sparse8")
                    for size in (1, 2, 4, 8))
    expected.add("load_raw_8MiB")
    if len(rows) != len(expected) or {row["case"] for row in rows} != expected:
        raise ValueError("benchmark case coverage differs")
    return rows


def milliseconds(value: dict[str, float]) -> str:
    return f"{value['median_seconds'] * 1000:.3f} ({value['min_seconds'] * 1000:.3f}–{value['max_seconds'] * 1000:.3f})"


class Campaign:
    def __init__(self, root: Path, checkout: Path) -> None:
        if not root.is_absolute() or root.exists():
            raise ValueError("qualification requires a fresh absolute runner temp directory")
        root.mkdir()
        self.root, self.checkout = root, checkout
        self.upload = root / "upload"
        self.upload.mkdir()
        self.environment = os.environ.copy()
        # The candidate code needs no GitHub credentials or raw dispatch payload.
        for key in ("GH_TOKEN", "GITHUB_TOKEN", "CANDIDATE_PATCH_GZIP_BASE64"):
            self.environment.pop(key, None)
        self.report: dict[str, Any] = {
            "schema": "verifiedos-sail-runtime-qualification/1", "status": "pending",
            "verifiedos_revision": os.environ["TESTED_REVISION"], "sail_base": BASE,
            "candidate_revision": os.environ["CANDIDATE_REVISION"],
            "patch_sha256": os.environ["CANDIDATE_PATCH_SHA256"],
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "compiler_flags": FLAGS, "repetitions": REPETITIONS,
            "platform": platform.platform(), "machine": platform.machine(), "commands": [],
            "method": "one discarded warmup; paired alternating process order; median, min, max; validation outside timers",
            "scope": "focused runtime calls on eight allocated sparse 16 MiB blocks; no emulator speedup claim",
        }
        self.save()

    def save(self) -> None:
        write(self.upload / "results.json", self.report)

    def run(self, name: str, argv: list[str], cwd: Path, *,
            environment: dict[str, str] | None = None, timeout: int = 90) -> str:
        start = time.monotonic()
        result = subprocess.run(argv, cwd=cwd, env=environment or self.environment,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout, check=False)
        (self.upload / (name + ".stdout.log")).write_text(result.stdout, encoding="utf-8", newline="")
        (self.upload / (name + ".stderr.log")).write_text(result.stderr, encoding="utf-8", newline="")
        self.report["commands"].append({"name": name, "argv": argv, "cwd": str(cwd),
            "exit_code": result.returncode, "wall_seconds": time.monotonic() - start})
        self.save()
        if result.returncode:
            raise RuntimeError(f"{name} failed ({result.returncode}): {result.stderr[-4000:]}")
        return result.stdout

    def sources(self) -> tuple[Path, Path]:
        expected = os.environ["CANDIDATE_PATCH_SHA256"]
        candidate = os.environ["CANDIDATE_REVISION"]
        if SHA256.fullmatch(expected) is None or REVISION.fullmatch(candidate) is None:
            raise ValueError("candidate requires full commit and patch SHA-256 identities")
        encoded = os.environ["CANDIDATE_PATCH_GZIP_BASE64"]
        if len(encoded) > 60000:
            raise ValueError("compressed patch exceeds dispatch budget")
        compressed = base64.b64decode(encoded, validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            patch = stream.read(1024 * 1024 + 1)
        if len(patch) > 1024 * 1024 or hashlib.sha256(patch).hexdigest() != expected:
            raise ValueError("candidate patch length or SHA-256 differs")
        patch_path = self.upload / "candidate.patch"
        patch_path.write_bytes(patch)
        archive = self.upload / "sail-base.tar.gz"
        # This literal HTTPS URL names a full upstream commit; the archive and its
        # byte hash remain in the artifact independently of GitHub's archive cache.
        with urllib.request.urlopen(URL, timeout=120) as response, archive.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        self.report["source_url"] = URL
        self.report["source_archive_sha256"] = digest(archive)
        baseline = extract(archive, self.root / "base")
        modified = self.root / "candidate"
        shutil.copytree(baseline, modified, symlinks=True)
        numstat = self.run("patch-paths", ["git", "apply", "--numstat", str(patch_path)], modified)
        paths = {line.split("\t")[2] for line in numstat.splitlines()}
        if paths != PATHS or any(line.startswith("-\t") for line in numstat.splitlines()):
            raise ValueError("patch must change only runtime implementation, header and focused tests")
        self.run("patch-check", ["git", "apply", "--check", "--whitespace=error-all", str(patch_path)], modified)
        self.run("patch-apply", ["git", "apply", str(patch_path)], modified)
        self.report["source_files"] = {
            name: {"base": digest(baseline / name) if (baseline / name).is_file() else None,
                   "candidate": digest(modified / name)} for name in sorted(PATHS)}
        self.save()
        return baseline, modified

    def qualify(self, candidate: Path) -> None:
        for label, cc, cxx, flags in (
                ("gcc", "gcc", "g++", "-O2"),
                ("clang", "clang", "clang++", "-O2"),
                ("sanitizers", "clang", "clang++", "-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined")):
            environment = dict(self.environment, CC=cc, CXX=cxx, CFLAGS=flags,
                               CXXFLAGS=flags, LDFLAGS=flags,
                               ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            self.run("regression-" + label, ["bash", "test/oneoff/rts_memory/test.sh"],
                     candidate, environment=environment)

    def benchmark(self, baseline: Path, candidate: Path) -> None:
        source = self.checkout / "tools/ci/sail_runtime_benchmark.c"
        shutil.copyfile(source, self.upload / source.name)
        self.report["benchmark_sha256"] = digest(source)
        self.run("compiler", ["gcc", "--version"], self.root)
        self.run("cpu", ["lscpu"], self.root)
        self.run("kernel", ["uname", "-a"], self.root)
        self.run("packages", ["dpkg-query", "-W", "gcc", "g++", "clang", "libgmp-dev"], self.root)
        binaries: dict[str, Path] = {}
        for label, tree in (("before", baseline), ("after", candidate)):
            binary = self.root / (label + "-benchmark")
            arguments = ["gcc", *FLAGS, "-I" + str(tree / "lib")]
            if label == "after":
                arguments.append("-DSAIL_BUFFER_API")
            arguments.extend([str(source), *(str(tree / "lib" / name) for name in
                ("rts.c", "sail.c", "sail_failure.c", "elf.c")), "-lgmp", "-o", str(binary)])
            self.run("build-" + label, arguments, self.root)
            binaries[label] = binary
        image = self.root / "image.bin"
        image.write_bytes(bytes((i * 29 + (i >> 8) * 7 + 19) & 255
                               for i in range(8 * 1048576)))
        self.report["image_sha256"] = digest(image)
        collected: dict[str, list[list[Sample]]] = {"before": [], "after": []}
        oracle: list[tuple[str, int, int, str]] | None = None
        for repetition in range(-1, REPETITIONS):
            order = ("before", "after") if repetition % 2 else ("after", "before")
            for label in order:
                phase = "warmup" if repetition < 0 else str(repetition + 1)
                rows = parse_samples(self.run(f"benchmark-{phase}-{label}",
                    [str(binaries[label]), str(image)], self.root))
                identity = [(row["case"], row["bytes"], row["iterations"], row["checksum"]) for row in rows]
                if oracle is None:
                    oracle = identity
                elif identity != oracle:
                    raise ValueError("before/after workloads or independently validated checksums differ")
                if repetition >= 0:
                    collected[label].append(rows)
                self.report["samples"] = collected
                self.save()
        comparisons: list[dict[str, Any]] = []
        for index, sample in enumerate(collected["before"][0]):
            row: dict[str, Any] = {"case": sample["case"], "bytes": sample["bytes"],
                                   "iterations": sample["iterations"]}
            for label in ("before", "after"):
                values = [repeat[index]["seconds"] for repeat in collected[label]]
                row[label] = {"median_seconds": statistics.median(values),
                              "min_seconds": min(values), "max_seconds": max(values)}
            row["speedup"] = row["before"]["median_seconds"] / row["after"]["median_seconds"]
            comparisons.append(row)
        self.report["comparisons"] = comparisons
        summary = ["## Sail runtime qualification", "",
            f"Base `{BASE}`; candidate `{self.report['candidate_revision']}`; patch SHA-256 `{self.report['patch_sha256']}`.", "",
            "GCC and Clang C/C++ regressions and ASan/UBSan passed. Seven repetitions after one discarded warmup; alternating before/after order.", "",
            "Buffer rows compare existing byte loops with the new API. `fast_read_ram` and `load_raw` rows call the existing entry points in each revision. Initialization and result validation are outside timers. Eight allocated sparse 16 MiB blocks; head-of-list and eight-block-tail controls; warm image reads. These are runtime measurements, not whole-emulator speedups.", "",
            "| Case | Before median (min–max), ms | After median (min–max), ms | Ratio |",
            "| --- | ---: | ---: | ---: |"]
        summary.extend(f"| `{row['case']}` | {milliseconds(row['before'])} | {milliseconds(row['after'])} | {row['speedup']:.2f}x |"
                       for row in comparisons)
        summary.append("\nRaw samples, commands, compiler/CPU identity, source archive, harness and exact patch are retained in the artifact.\n")
        rendered = "\n".join(summary)
        (self.upload / "summary.md").write_text(rendered, encoding="utf-8", newline="")
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8", newline="") as stream:
            stream.write(rendered)


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("runtime qualification and all benchmarks run only on GitHub Actions main")
    checkout = Path(__file__).resolve().parents[2]
    revision = os.environ["TESTED_REVISION"]
    if REVISION.fullmatch(revision) is None:
        raise ValueError("tested revision must be a full lowercase SHA")
    actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual != revision:
        raise ValueError("checkout differs from guarded revision")
    subprocess.run(["git", "-C", str(checkout), "merge-base", "--is-ancestor", revision,
                    os.environ["GITHUB_SHA"]], check=True)
    campaign = Campaign(Path(os.environ["RUNNER_TEMP"]) / "sail-runtime-qualification", checkout)
    try:
        baseline, candidate = campaign.sources()
        campaign.qualify(candidate)
        campaign.benchmark(baseline, candidate)
        campaign.report["status"] = "passed"
    except Exception as error:
        campaign.report["status"] = "failed"
        campaign.report["error"] = str(error)
        raise
    finally:
        campaign.save()


if __name__ == "__main__":
    main()
