# SPDX-License-Identifier: Apache-2.0
"""Shared git-base validation, baseline extraction, RSS, and atomic output for CI benchmarks."""

import json
import re
import subprocess
import sys
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


def validate_base(
    root: Path,
    base: str,
    *,
    same_error: str = "performance base must precede the tested revision",
    check_output: Callable[..., Any] = subprocess.check_output,
    run: Callable[..., Any] = subprocess.run,
) -> str:
    """Require a proper committed ancestor, never a revision expression."""
    if re.fullmatch(r"[0-9a-f]{40}", base) is None:
        raise ValueError("performance base must be a full lowercase commit SHA")
    revision = str(check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True)).strip()
    if base == revision:
        raise ValueError(same_error)
    run(["git", "-C", str(root), "merge-base", "--is-ancestor", base, revision],
        check=True, capture_output=True)
    return revision


def require_clean_checkout(
    root: Path,
    message: str = "benchmark requires a clean indexed checkout",
    *,
    check_output: Callable[..., Any] = subprocess.check_output,
) -> None:
    """Refuse dirty indexed checkouts before a paired benchmark begins."""
    if check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
        raise ValueError(message)


def verify_unchanged_checkout(
    root: Path,
    revision: str,
    *,
    revision_message: str = "revision changed during comparison",
    dirty_message: str = "corpus changed during comparison",
    check_output: Callable[..., Any] = subprocess.check_output,
) -> None:
    """Verify HEAD and indexed tree cleanliness did not drift during measurement."""
    head = str(check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True)).strip()
    if head != revision:
        raise RuntimeError(revision_message)
    if check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
        raise RuntimeError(dirty_message)


def extract_baseline_tools(
    root: Path,
    base: str,
    scratch: Path,
    *,
    run: Callable[..., Any] = subprocess.run,
    tar_open: Callable[..., Any] = tarfile.open,
) -> Path:
    """Extract `base:tools` via `git archive` into `scratch / 'baseline'` and return its path."""
    archive = scratch / "tools.tar"
    run(["git", "-C", str(root), "archive", "--format=tar", "-o", str(archive), base, "tools"],
        check=True)
    with tar_open(archive) as source:
        source.extractall(scratch / "baseline", filter="data")
    return scratch / "baseline" / "tools"


def peak_rss_kib() -> int | None:
    """Return process peak RSS in KiB on Linux, or `None` elsewhere."""
    if sys.platform != "linux":
        return None
    import resource

    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def paired_order(iteration: int) -> tuple[str, str]:
    """Alternate baseline/candidate order across paired repetitions."""
    return ("baseline", "candidate") if iteration % 2 == 0 else ("candidate", "baseline")


def write_json_atomic(output: Path, data: object, *, ensure_ascii: bool = True) -> None:
    """Write formatted JSON to a `.pending` sibling and atomically replace `output`."""
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + ".pending")
    try:
        pending.write_text(
            json.dumps(data, indent=2, ensure_ascii=ensure_ascii) + "\n",
            encoding="utf-8",
        )
        pending.replace(output)
    except BaseException:
        pending.unlink(missing_ok=True)
        raise
