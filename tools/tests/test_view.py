# SPDX-License-Identifier: Apache-2.0
"""Generated reading views cannot overwrite sources in another checkout."""

import subprocess
import tempfile
from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos.cli import view


def _output_ownership() -> None:
    with sandbox_tree({".gitignore": "/out/\n/.worktrees/\n", "source.md": "source\n"}) as root:
        ensure(view._output_path(root, None) == root / "out/spec-woven.md",
               "the default ignored output was refused")
        with tempfile.TemporaryDirectory(prefix="vos-view-external-") as folder:
            external = Path(folder).resolve() / "woven.md"
            ensure(view._output_path(root, str(external)) == external,
                   "an external generated output was refused")
        for candidate in ("source.md", "new-source.md"):
            try:
                view._output_path(root, candidate)
            except ValueError:
                pass
            else:
                raise AssertionError(f"source output was accepted: {candidate}")

        nested = root / ".worktrees/worker"
        nested.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(nested)], cwd=root,
                       check=True, capture_output=True, timeout=30)
        source = nested / "source.md"
        source.write_text("worker source\n", encoding="utf-8")
        (nested / ".gitignore").write_text("/out/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(nested), "add", "--", "source.md", ".gitignore"],
                       cwd=root, check=True, capture_output=True, timeout=30)
        for caller in (root, nested):
            try:
                view._output_path(caller, str(source))
            except ValueError:
                pass
            else:
                raise AssertionError("the ancestor's ignore rule allowed a nested source overwrite")
        ensure(view._output_path(root, str(nested / "out/woven.md")) == nested / "out/woven.md",
               "output ignored by both containing checkouts was refused")
        ensure(source.read_text(encoding="utf-8") == "worker source\n",
               "output selection changed the worker's source")


def cases() -> list[Case]:
    return [Case("generated output respects every containing checkout", _output_ownership)]
