# SPDX-License-Identifier: Apache-2.0
"""Refuse unsafe benchmark inputs and keep the measured corpus separate from code."""

import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from ci import archive_scan_benchmark as benchmark
from tests.harness import Case, ensure, sandbox_tree


def _base_refusals() -> None:
    revision = "a" * 40
    with patch.object(benchmark.subprocess, "check_output", return_value=revision), \
            patch.object(benchmark.subprocess, "run") as git:
        for base in ("main", "a" * 39, "A" * 40, "--all", revision):
            try:
                benchmark.validate_base(Path(), base)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted unsafe or identical base {base}")
        ensure(not git.called, "invalid bases must be refused before ancestry execution")
        git.side_effect = subprocess.CalledProcessError(1, ["git", "merge-base"])
        try:
            benchmark.validate_base(Path(), "b" * 40)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("accepted a base outside the tested ancestry")


def _hosted_only() -> None:
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
            patch.object(sys, "argv", ["benchmark", "--base", "b" * 40, "--output", "unused"]), \
            patch.object(benchmark, "compare") as compare, redirect_stderr(StringIO()):
        try:
            benchmark.main()
        except SystemExit as error:
            ensure(error.code == 2, "host-only refusal must be an argument error")
        else:
            raise AssertionError("allowed benchmark execution outside Actions")
        ensure(not compare.called, "host-only guard must precede corpus access")


def _worker_uses_explicit_corpus() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-benchmark-fixture-") as temporary:
        scratch = Path(temporary)
        tools, root = scratch / "implementation", scratch / "corpus"
        tools.mkdir()
        root.mkdir()
        (root / "marker").write_text("the selected corpus", encoding="utf-8")
        (tools / "check.py").write_text(
            "from types import SimpleNamespace\n"
            "def run(root, clock):\n"
            "    return SimpleNamespace(findings=0, out=[(root/'marker').read_text()])\n",
            encoding="utf-8")
        (tools / "vos").mkdir()
        (tools / "vos" / "__init__.py").write_text("", encoding="utf-8")
        (tools / "vos" / "timings.py").write_text(
            "class Clock:\n"
            "    def __init__(self, **kwargs): pass\n"
            "    def units(self): return []\n", encoding="utf-8")
        output = scratch / "sample.json"
        # This is a tiny fake checker, never the native archive or a timing benchmark.
        code = ("import sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(Path(benchmark.__file__).parents[1])!r}); "
                "from ci.archive_scan_benchmark import worker; "
                "worker(*(Path(p) for p in sys.argv[1:]))")
        subprocess.run([sys.executable, "-c", code, str(root), str(tools), str(output)], check=True)
        sample = json.loads(output.read_text(encoding="utf-8"))
        ensure(sample["findings"] == 0 and sample["report"] == ["the selected corpus"],
               "implementation location must not replace the explicit input corpus")


def _baseline_imports_share_repository_owners() -> None:
    # A tiny fake implementation exercises four worker launches, not a benchmark
    # of the repository checker or any native-sized retained evidence.
    files = {
        ".gitignore": "/out/\n__pycache__/\n",
        "docs/requirements-register.md": "owner marker\n",
        "owned.txt": "the common owner\n",
        "tools/check.py": (
            "from types import SimpleNamespace\nfrom vos.fixture import ROOT\n"
            "def run(root, clock):\n"
            "    if root != ROOT: raise ValueError('different owner root')\n"
            "    return SimpleNamespace(findings=0,out=[(ROOT/'owned.txt').read_text()])\n"),
        "tools/vos/__init__.py": "",
        "tools/vos/fixture.py": (
            "from pathlib import Path\n"
            "ROOT=next(p for p in Path(__file__).resolve().parents "
            "if (p/'.git').exists() and (p/'docs/requirements-register.md').exists())\n"),
        "tools/vos/timings.py": (
            "class Clock:\n"
            "    def __init__(self, **kwargs): pass\n"
            "    def units(self): return []\n"),
    }
    with sandbox_tree(files) as root:
        command = ["git", "-C", str(root), "-c", "user.name=Fixture",
                   "-c", "user.email=fixture@example.invalid", "commit", "--quiet"]
        subprocess.run([*command, "-m", "baseline"], check=True)
        base = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        subprocess.run([*command, "--allow-empty", "-m", "candidate"], check=True)
        output = root / "out/result.json"
        # Simulate the hosted boundary only for this isolated tiny fake checker;
        # no repository checker or retained native input is reachable here.
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            benchmark.compare(root, base, output, 2)
        result = json.loads(output.read_text(encoding="utf-8"))
        ensure(result["report_identical"] and all(len(rows) == 2 for rows in result["samples"].values()),
               "archived baseline imports must resolve the same repository owners in every worker")


def cases() -> list[Case]:
    return [Case("base-refusals", _base_refusals),
            Case("hosted-only", _hosted_only),
            Case("explicit-corpus", _worker_uses_explicit_corpus),
            Case("baseline-imports-share-owners", _baseline_imports_share_repository_owners)]
