# SPDX-License-Identifier: Apache-2.0
"""Proof performance tooling cannot run locally or omit its native controls."""

import os
import sys
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from ci import proof_identity_benchmark as benchmark
from tests import test_proofcache
from tests.harness import Case, ensure


def _hosted_only() -> None:
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
            patch.object(sys, "argv", ["benchmark", "--base", "b" * 40,
                                      "--output", "unused"]), \
            patch.object(benchmark, "compare") as compare, redirect_stderr(StringIO()):
        try:
            benchmark.main()
        except SystemExit as error:
            ensure(error.code == 2, "local measurement must be refused before reading inputs")
        else:
            raise AssertionError("accepted local installed-context measurement")
        ensure(not compare.called, "the hosted guard must precede comparison")


def _native_population() -> None:
    observed: list[str] = []
    controls = [Case(lane, lambda value=lane: observed.append(value), lane=lane)
                for lane in ("any", "host", "guest", "toolchain")]
    with patch.object(test_proofcache, "cases", return_value=controls):
        benchmark.native_controls()
    ensure(observed == ["guest", "toolchain"],
           "Rocq-only provisioning must run every native control without a Sail lane probe")
    with patch.object(test_proofcache, "cases", return_value=[
            Case("failure", lambda: (_ for _ in ()).throw(RuntimeError("native failed")),
                 lane="toolchain")]):
        try:
            benchmark.native_controls()
        except RuntimeError:
            pass
        else:
            raise AssertionError("a failed native control supplied acceptance")


def _worker_dispatch() -> None:
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
            patch.object(sys, "argv", ["benchmark", "--worker-tools", "tools", "--work",
                                      "scratch", "--root", ".", "--output", "sample.json"]), \
            patch.object(benchmark, "worker") as worker:
        ensure(benchmark.main() == 0, "explicit native worker dispatch failed")
        ensure(worker.call_args.args == (Path.cwd(), Path("tools").resolve(),
                                        Path("scratch").resolve(), Path("sample.json")),
               "worker inputs must retain the explicit corpus and implementation")


def cases() -> list[Case]:
    return [Case("hosted-only", _hosted_only),
            Case("complete-native-population", _native_population),
            Case("explicit-worker", _worker_dispatch)]
