# SPDX-License-Identifier: Apache-2.0
"""The root agent entry point is one tracked source of shared instructions."""

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from vos import env

if TYPE_CHECKING:
    from . import Context

HEADING = "=== instructions: the agent entry point uses AGENTS.md as its shared source ==="

NAME = "AGENTS.md"


def _index_faults(root: Path) -> list[str]:
    """An unresolved entry or tracked symlink cannot stand in for a regular source."""
    done = subprocess.run(["git", "-C", str(root), "ls-files", "--stage", "-z", "--", NAME],
                          capture_output=True, env={**os.environ, **env.git_env(root)},
                          check=False, timeout=30)
    if done.returncode:
        raise ValueError("cannot inspect instruction file modes in the Git index: "
                         + done.stderr.decode("utf-8", errors="replace").strip())
    entries: list[tuple[str, str]] = []
    for entry in done.stdout.decode("utf-8").split("\0"):
        if not entry:
            continue
        staged, _name = entry.split("\t", 1)
        mode, _, stage = staged.split()
        entries.append((mode, stage))
    if entries not in ([("100644", "0")], [("100755", "0")]):
        return [f"{NAME} must be tracked as one resolved regular file"]
    return []


def _content_faults(root: Path) -> list[str]:
    """AGENTS.md must be a nonempty, valid-UTF-8 document, read directly rather than
    through the index: the working tree is what an agent session actually loads."""
    path = root / NAME
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return [f"{NAME} is missing; restore the shared instructions there"]
    except OSError as exc:
        return [f"{NAME} could not be read: {exc}"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{NAME} must contain valid UTF-8 instructions"]
    if not text.removeprefix("﻿").strip():
        return [f"{NAME} must contain nonempty shared instructions"]
    return []


def run(ctx: Context) -> None:
    ctx.rep.line(HEADING)
    faults: list[str] = []
    try:
        faults.extend(_index_faults(ctx.root))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        faults.append(str(exc))
    faults.extend(_content_faults(ctx.root))
    ctx.rep.report("K-110", "invalid shared agent instructions:", faults,
                   "AGENTS.md is tracked as one nonempty UTF-8 regular file")
    ctx.rep.line()
