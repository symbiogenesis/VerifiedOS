# SPDX-License-Identifier: Apache-2.0
"""Alternate the baseline and current count scans on the same checkout bytes."""

import argparse
import hashlib
import importlib.util
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=next(path for path in Path(__file__).resolve().parents
                                     if (path / "tools/check.py").is_file()))
    parser.add_argument("--baseline", default="69e1d5f6322f80186a3de59e5f03bb248c84616e")
    parser.add_argument("--component-repetitions", type=int, default=7)
    parser.add_argument("--checker-repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path,
                        default=Path("out/performance-20260926/replay-checker-results.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / "tools"))
    import check
    from vos import corpus
    from vos.checks import Context, counts
    from vos.register import read_artifacts, read_register
    from vos.report import Reporter

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *arguments],
                                       text=True, encoding="utf-8")

    name = "vos.checks._counts_benchmark_baseline"
    spec = importlib.util.spec_from_loader(name, loader=None)
    if spec is None:
        raise RuntimeError("could not create the baseline module")
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[name] = baseline
    source = git("show", f"{args.baseline}:tools/vos/checks/counts.py")
    exec(compile(source, f"{args.baseline}:counts.py", "exec"), baseline.__dict__)
    current = counts.unheld_counts
    functions = {"before": baseline.unheld_counts, "after": current}
    documents = corpus.load(root)
    ctx = Context(root, documents, read_register(documents), read_artifacts(documents), Reporter())
    components: dict[str, list[float]] = {name: [] for name in functions}
    checker: dict[str, list[float]] = {name: [] for name in functions}
    expected = baseline.unheld_counts(ctx)
    if current(ctx) != expected:
        raise RuntimeError("the count findings differ before timing")
    report_lines: list[str] | None = None
    try:
        for repeat in range(args.component_repetitions):
            for name in (("before", "after") if repeat % 2 == 0 else ("after", "before")):
                start = perf_counter()
                result = functions[name](ctx)
                components[name].append(perf_counter() - start)
                if result != expected:
                    raise RuntimeError("the count findings changed during timing")
        # Warm optional imports once for both implementations before comparing
        # complete in-process checks. This is not Python/uv process startup timing.
        for name in functions:
            counts.unheld_counts = functions[name]
            report = check.run(root)
            if report_lines is not None and report.out != report_lines:
                raise RuntimeError("the complete checker reports differ")
            report_lines = report.out
        for repeat in range(args.checker_repetitions):
            for name in (("before", "after") if repeat % 2 == 0 else ("after", "before")):
                counts.unheld_counts = functions[name]
                start = perf_counter()
                report = check.run(root)
                checker[name].append(perf_counter() - start)
                if report.out != report_lines:
                    raise RuntimeError("the complete checker report changed during timing")
    finally:
        counts.unheld_counts = current
    output = {
        "baseline_revision": args.baseline,
        "checkout_revision": git("rev-parse", "HEAD").strip(),
        "working_tree_status": git("status", "--short"),
        "source_sha256": hashlib.sha256((root / "tools/vos/checks/counts.py").read_bytes()).hexdigest(),
        "interpreter": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "command": sys.argv,
        "workers": 1,
        "scope": {"markdown_documents": len(documents.docs),
                  "markdown_characters": sum(len(doc.raw) for doc in documents.docs),
                  "declared_count_scopes": len(counts.COUNT_SCOPES),
                  "count_findings": len(expected),
                  "checker_findings": report.findings,
                  "checker_report_sha256": hashlib.sha256("\n".join(report.out).encode()).hexdigest()},
        "component_seconds": components,
        "complete_in_process_checker_seconds": checker,
        "medians": {"component": {name: statistics.median(times)
                                    for name, times in components.items()},
                    "complete_in_process_checker": {name: statistics.median(times)
                                                    for name, times in checker.items()}},
        "limitations": "Same current checkout, alternating implementations; checker timing excludes "
                        "Python/uv startup and warms optional imports. No gate-suite timing claim.",
    }
    destination = root / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="")
    print(json.dumps({"medians": output["medians"], "scope": output["scope"]}, indent=2))


if __name__ == "__main__":
    main()
