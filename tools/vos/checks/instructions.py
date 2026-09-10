# SPDX-License-Identifier: Apache-2.0
"""Both root agent entry points use one tracked source of shared instructions."""

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from vos import env
from vos.cli import sync_instructions

if TYPE_CHECKING:
    from . import Context

HEADING = "=== instructions: both agent entry points use AGENTS.md as their shared source ==="


def _index_faults(root: Path) -> list[str]:
    """An unresolved entry or tracked symlink cannot stand in for a regular source."""
    done = subprocess.run(["git", "-C", str(root), "ls-files", "--stage", "-z", "--",
                           *sync_instructions.NAMES], capture_output=True,
                          env={**os.environ, **env.git_env(root)}, check=False, timeout=30)
    if done.returncode:
        raise ValueError("cannot inspect instruction file modes in the Git index: "
                         + done.stderr.decode("utf-8", errors="replace").strip())
    entries: dict[str, list[tuple[str, str]]] = {}
    for entry in done.stdout.decode("utf-8").split("\0"):
        if not entry:
            continue
        staged, name = entry.split("\t", 1)
        mode, _, stage = staged.split()
        entries.setdefault(name, []).append((mode, stage))
    return [f"{name} must be tracked as one resolved regular file"
            for name in sync_instructions.NAMES
            if entries.get(name) not in ([("100644", "0")], [("100755", "0")])]


def run(ctx: Context) -> None:
    ctx.rep.line(HEADING)
    faults: list[str] = []
    try:
        faults.extend(_index_faults(ctx.root))
        sync_instructions.sync(ctx.root, check=True)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        faults.append(str(exc))
    ctx.rep.report("K-110", "invalid shared agent instructions:", faults,
                   "AGENTS.md is tracked nonempty UTF-8; tracked CLAUDE.md imports it")
    ctx.rep.line()
