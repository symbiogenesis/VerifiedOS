# SPDX-License-Identifier: Apache-2.0
"""Performance-controller refusals and equivalence checks use fixture data only."""

import io
import json
import os
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ci import runner_benchmark as runner
from tests.harness import Case, ensure, sandbox_tree


def _hosted_only() -> None:
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), redirect_stderr(io.StringIO()):
        try:
            runner.main(["--base", "a" * 40, "--output", "unused.json"])
        except SystemExit as exc:
            ensure(exc.code == 2, "local performance execution must be refused before work starts")
        else:
            raise AssertionError("local performance execution was accepted")


def _identity_reads_current_bytes() -> None:
    with sandbox_tree({"fixture.txt": "old"}) as root:
        original = runner._identity(root)
        path = root / "fixture.txt"
        before = path.stat()
        path.write_text("new", encoding="utf-8", newline="")
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        ensure(runner._identity(root) != original,
               "unchanged index/size/timestamp must not hide changed benchmark inputs")
        with patch.object(runner.subprocess, "check_output", return_value=b"100644 oid 1\tfixture.txt\0"):
            try:
                runner._identity(root)
            except ValueError:
                pass
            else:
                raise AssertionError("an unmerged benchmark population must refuse")


def _paired_order_and_failed_equivalence() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-runner-controller-") as temporary:
        scratch = Path(temporary)
        visits: list[tuple[str, str]] = []
        fault = ""

        def launch(argv: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
            kind = argv[argv.index("--kind") + 1]
            variant = Path(argv[argv.index("--worker-tools") + 1]).name
            visits.append((kind, variant))
            sample: runner.Sample = {
                "component_seconds": 1.0, "setup_seconds": 0.0, "cpu_seconds": 0.0,
                "peak_rss_kb": None, "temporary_apparent_bytes": 0,
                "findings": int(fault == "findings" and variant == "candidate"),
                "report": ["different" if fault == "report" and variant == "candidate" else "same"],
                "bytes_unchanged": not (fault == "bytes" and variant == "candidate"),
            }
            Path(argv[argv.index("--output") + 1]).write_text(json.dumps(sample), encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0)

        def samples() -> dict[str, dict[str, list[runner.Sample]]]:
            return {variant: {kind: [] for kind in ("markdown", "proof_headers")}
                    for variant in ("baseline", "candidate")}

        sources = {variant: scratch / variant for variant in ("baseline", "candidate")}
        with (patch.object(runner.subprocess, "run", side_effect=launch),
              patch.object(runner.time, "perf_counter", return_value=1.0),
              redirect_stdout(io.StringIO())):
            measured = samples()
            runner._measure(scratch, sources, scratch, 2, measured)
            ensure(visits == [(kind, variant) for order in (("baseline", "candidate"),
                                                           ("candidate", "baseline"))
                              for kind in ("markdown", "proof_headers") for variant in order],
                   "paired repetitions must alternate both complete workloads")
            for fault in ("findings", "report", "bytes"):
                measured = samples()
                try:
                    runner._measure(scratch, sources, scratch, 2, measured)
                except RuntimeError:
                    ensure(len(measured["candidate"]["markdown"]) == 1,
                           "the rejected sample must remain available for the failure report")
                else:
                    raise AssertionError(f"paired comparison accepted a changed {fault} result")


def _failed_comparison_retains_a_refusal_record() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-runner-refusal-") as temporary:
        root = Path(temporary)
        output = root / "report.json"
        with (patch.object(runner.subprocess, "check_output", side_effect=["f" * 40, ""]),
              patch.object(runner.subprocess, "run"), patch.object(runner.tarfile, "open"),
              patch.object(runner.platform, "platform", return_value="fixture-platform"),
              patch.object(runner, "_identity", return_value="scope"),
              patch.object(runner, "_measure", side_effect=RuntimeError("worker failed")),
              redirect_stdout(io.StringIO())):
            try:
                runner.compare(root, "a" * 40, output, 2)
            except RuntimeError:
                pass
            else:
                raise AssertionError("a failed worker must refuse performance acceptance")
        report = json.loads(output.read_text(encoding="utf-8"))
        ensure("worker failed" in report["failure"] and not report["report_identical"]
               and not report["byte_assertions_identical"],
               "a failed comparison must retain its reason without passing evidence")


def cases() -> list[Case]:
    return [Case("runner comparison is hosted only", _hosted_only),
            Case("runner comparison hashes current indexed bytes", _identity_reads_current_bytes),
            Case("runner pairs alternate and refuse changed results", _paired_order_and_failed_equivalence),
            Case("runner comparison retains failed evidence", _failed_comparison_retains_a_refusal_record)]
