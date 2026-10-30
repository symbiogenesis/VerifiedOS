# SPDX-License-Identifier: Apache-2.0
"""Temporary hosted correctness comparison for shared RTL vector printing."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterator
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from vos import env, receipts, rtl_vectors, sailrig  # noqa: E402

BASELINE = "tools/cheri-equiv/gen_vectors.sail"
DATA = re.compile(rb"[a-z]+ [0-9a-f ]+ -> [0-9a-f ]+\n")


def data_lines(path: Path) -> Iterator[bytes]:
    with path.open("rb") as source:
        for line in source:
            if line.startswith(b"#") or line in (b"\n", b"\r\n"):
                continue
            if DATA.fullmatch(line) is None:
                raise ValueError(f"malformed data line in {path}: {line[:120]!r}")
            yield line


def compare_data(baseline: Path, candidate: Path) -> dict[str, object]:
    """Compare every ordered raw data line; headers supply no comparison credit."""
    left_hash, right_hash = hashlib.sha256(), hashlib.sha256()
    left_kinds: Counter[str] = Counter()
    right_kinds: Counter[str] = Counter()
    left_bytes = right_bytes = mismatches = 0
    examples: list[dict[str, object]] = []
    for index, (left, right) in enumerate(zip_longest(data_lines(baseline), data_lines(candidate)), 1):
        if left is not None:
            left_hash.update(left)
            left_kinds[left.split(b" ", 1)[0].decode("ascii")] += 1
            left_bytes += len(left)
        if right is not None:
            right_hash.update(right)
            right_kinds[right.split(b" ", 1)[0].decode("ascii")] += 1
            right_bytes += len(right)
        if left != right:
            mismatches += 1
            if len(examples) < 8:
                examples.append({"data_line": index,
                                 "baseline": None if left is None else left.decode("ascii"),
                                 "candidate": None if right is None else right.decode("ascii")})
    return {"equal": mismatches == 0 and bool(left_kinds), "mismatches": mismatches,
            "first_mismatches": examples,
            "baseline": {"data_sha256": left_hash.hexdigest(), "data_bytes": left_bytes,
                         "vectors": sum(left_kinds.values()), "kinds": dict(sorted(left_kinds.items()))},
            "candidate": {"data_sha256": right_hash.hexdigest(), "data_bytes": right_bytes,
                          "vectors": sum(right_kinds.values()), "kinds": dict(sorted(right_kinds.items()))}}


def controls() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="vector-comparison-") as temporary:
        root = Path(temporary)
        baseline, candidate = root / "baseline", root / "candidate"
        baseline.write_bytes(b"# old header\npn 000 -> 00 000\npn 001 -> 01 001\n")
        results: dict[str, bool] = {}
        for name, data, expected in (
            ("comment_change", b"# new header\npn 000 -> 00 000\npn 001 -> 01 001\n", True),
            ("altered", b"pn 000 -> 00 000\npn 001 -> 00 001\n", False),
            ("truncated", b"pn 000 -> 00 000\n", False),
            ("reordered", b"pn 001 -> 01 001\npn 000 -> 00 000\n", False),
            ("whitespace", b"pn 000  -> 00 000\npn 001 -> 01 001\n", False),
        ):
            candidate.write_bytes(data)
            results[name] = compare_data(baseline, candidate)["equal"] is expected
        return results


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True).stdout


def tool(name: str) -> dict[str, str]:
    binary = shutil.which(name)
    if binary is None:
        raise ValueError(f"missing tool: {name}")
    version = subprocess.run([binary, "--version"], check=True, capture_output=True,
                             text=True).stdout.strip()
    return {"path": binary, "sha256": receipts.digest(Path(binary)), "version": version}


def qualify(report: dict[str, object], work: Path, revision: str,
            control_results: dict[str, bool], log: list[str]) -> None:
    if not all(control_results.values()):
        raise ValueError("comparison controls failed")
    sources: dict[str, str] = {}
    for source in rtl_vectors.SOURCES:
        current = (ROOT / source).read_bytes()
        if current != git("show", f"{revision}:{source}"):
            raise ValueError(f"model source changed from baseline: {source}")
        sources[source] = hashlib.sha256(current).hexdigest()
    report["model_sources_sha256"] = sources
    report["candidate_sources_sha256"] = {
        source: receipts.digest(ROOT / source) for source in
        ("tools/vos/oracle.py", "tools/vos/rtl_vectors.py", rtl_vectors.CAMPAIGN,
         "tools/vos/sailrig.py", "tools/vos/cli/rtl.py", "tools/vos/env.py",
         "tools/opam/sail.lock", "tools/z3-requirements.txt", "tools/ci/rtl_vector_migration.py")}
    report["tools"] = {name: tool(name) for name in ("sail", "cc", "z3")}
    sail = shutil.which("sail")
    if sail is None:
        raise ValueError("Sail vanished after identification")
    library = sailrig.sail_lib(sail)
    report["sail_runtime_sha256"] = {name: receipts.digest(library / name)
                                    for name in sailrig.RUNTIME}
    baseline_source = work / "baseline" / "generator.sail"
    baseline_source.parent.mkdir(parents=True, exist_ok=True)
    baseline_source.write_bytes(git("show", f"{revision}:{BASELINE}"))
    candidate_source = work / "candidate" / "generator.sail"
    candidate_source.parent.mkdir(parents=True, exist_ok=True)
    candidate_source.write_text(rtl_vectors.harness(ROOT), encoding="utf-8", newline="\n")
    report["baseline_generator_sha256"] = receipts.digest(baseline_source)
    report["candidate_generator_sha256"] = receipts.digest(candidate_source)
    vectors: list[Path] = []
    for source in (baseline_source, candidate_source):
        binary = sailrig.build([*(ROOT / path for path in rtl_vectors.SOURCES), source],
                               source.parent, log)
        target = source.parent / "vectors.txt"
        if binary is None or not sailrig.emit(binary, target, log):
            raise ValueError(f"generation failed for {source}")
        vectors.append(target)
    comparison = compare_data(*vectors)
    report["comparison"] = comparison
    report["equal"] = comparison["equal"]
    if not report["equal"]:
        raise ValueError("complete ordered data differ")
    if sources != {source: receipts.digest(ROOT / source) for source in rtl_vectors.SOURCES}:
        raise ValueError("model source bytes changed during comparison")
    report["status"] = "passed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-revision", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    revision = args.baseline_revision
    if re.fullmatch("[a-f0-9]{40}", revision) is None:
        parser.error("baseline revision must be a full lowercase commit SHA")
    git("merge-base", "--is-ancestor", revision, "HEAD")
    environment = env.load()
    work = environment.lane_root / "cheri-equiv" / "migration"
    work.mkdir(parents=True, exist_ok=True)
    control_results = controls()
    report: dict[str, object] = {
        "baseline_revision": revision, "candidate_revision": git("rev-parse", "HEAD").decode().strip(),
        "controls": control_results, "scope": "complete ordered capability-vector data; no performance claim",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    try:
        qualify(report, work, revision, control_results, log)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report.update({"status": "failed", "error": str(error)})
    finally:
        report["log"] = log
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
