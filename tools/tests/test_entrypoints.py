# SPDX-License-Identifier: Apache-2.0
"""The host entry points, run twice each over the live tree: identical or lying.

Goal 1's read-only half. Every tool here claims to only read the checkout, and a
claim like that is proven by running the tool twice and comparing everything it
answered: a byte of difference means a timestamp, an unordered set, or a write that
fed back. The module brackets all of it with `git status --porcelain` taken before
its first case and after its last, held identical rather than empty, because the
suite may run on a tree with untracked work in flight and the proof owed is that
these runs added none of it. `__pycache__` never appears in either capture: the
repository ignores it, which is why an interpreter warming its caches does not
break the bracket.

The doubled runs read the live documents, so nothing here asserts on their
content, only on agreement between the two runs and on the exit code's meaning.
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.harness import TOOLS, Case, ensure
from vos import toolenv

_ROOT = TOOLS.parent


def _locked_bootstrap() -> None:
    for platform in ("win32", "linux"):
        launch = Mock(return_value=SimpleNamespace(returncode=7))
        with patch.object(toolenv, "sys", SimpleNamespace(
                platform=platform, prefix="other", executable="python")), \
                patch.object(toolenv, "shutil", SimpleNamespace(which=lambda _: "uv")), \
                patch.object(toolenv, "os", SimpleNamespace(environ={
                    "VIRTUAL_ENV": "foreign", "UV_PROJECT_ENVIRONMENT": "foreign"})), \
                patch.object(toolenv, "subprocess", SimpleNamespace(run=launch)):
            ensure(toolenv.bootstrap(_ROOT, ["check", "--fix"]) == 7,
                   "bootstrap must preserve the command's exit code")
            argv = launch.call_args.args[0]
            ensure(
                "--locked" in argv and "--exact" in argv and "--python" not in argv,
                "bootstrap enforces the lock and lets the project select Python",
            )
            ensure(argv[-2:] == ["check", "--fix"], "arguments must survive verbatim")
            environment = launch.call_args.kwargs["env"]
            ensure(environment["UV_PROJECT_ENVIRONMENT"] == str(
                toolenv.environment(_ROOT, platform)), "the environment is OS-specific")
            ensure("VIRTUAL_ENV" not in environment, "ambient activation must not win")


def _settled_children_do_not_sync() -> None:
    token = toolenv.identity(_ROOT, sys.platform)
    launch = Mock()
    with patch.object(toolenv, "sys", SimpleNamespace(
            platform=sys.platform, prefix=str(toolenv.environment(_ROOT, sys.platform)))), \
            patch.object(toolenv, "os", SimpleNamespace(environ={toolenv.READY: token})), \
            patch.object(toolenv, "subprocess", SimpleNamespace(run=launch)):
        ensure(toolenv.bootstrap(_ROOT, ["check"]) is None,
               "a child in the settled environment dispatches directly")
        launch.assert_not_called()
    ensure(toolenv.environment(_ROOT, "win32") != toolenv.environment(_ROOT, "linux"),
           "Windows and WSL must never share a virtual environment")


def _bootstrap_prerequisites() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-bootstrap-") as temporary:
     root = Path(temporary)
     for name in ("pyproject.toml", "uv.lock"):
         (root / name).write_text("initial", encoding="utf-8")
     token = toolenv.identity(root, sys.platform)
     launch = Mock(return_value=SimpleNamespace(returncode=7))
     errors = StringIO()
     with patch.object(toolenv, "sys", SimpleNamespace(
          platform=sys.platform, prefix=str(toolenv.environment(root, sys.platform)),
          stderr=errors)), \
          patch.object(toolenv, "os", SimpleNamespace(environ={toolenv.READY: token})), \
          patch.object(toolenv, "shutil", SimpleNamespace(which=lambda _: "uv")), \
          patch.object(toolenv, "subprocess", SimpleNamespace(run=launch)):
         ensure(toolenv.bootstrap(root, ["check"]) is None,
             "unchanged setup state permits direct dispatch")
         (root / "uv.lock").write_text("changed", encoding="utf-8")
         ensure(toolenv.bootstrap(root, ["check"]) == 7,
             "a changed lock must synchronize even inside the environment")
         launch.assert_called_once()
         launch.reset_mock()
         (root / "uv.lock").unlink()
         ensure(toolenv.bootstrap(root, ["check"]) == 1,
             "a missing lock must refuse dispatch")
         launch.assert_not_called()
         (root / "uv.lock").write_text("changed", encoding="utf-8")
         with patch.object(toolenv, "shutil", SimpleNamespace(which=lambda _: None)):
          ensure(toolenv.bootstrap(root, ["check"]) == 1,
              "missing uv must refuse dispatch")
         launch.assert_not_called()
         launch.side_effect = OSError("cannot launch")
         ensure(toolenv.bootstrap(root, ["check"]) == 1,
             "an OS launch error must be a reported failure")
         ensure("could not be started" in errors.getvalue(),
             "the launch failure must include an actionable diagnostic")


def _run(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    done = subprocess.run(list(argv), capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=300, cwd=_ROOT,
                          env=env)
    return done.returncode, done.stdout, done.stderr


def _twice_identical(command: str, *args: str,
                     env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run one command twice and hold every observable equal, handing back the
    verdict. Launched through the one entry point, which is how a caller runs it."""
    first = _run(sys.executable, str(TOOLS / "run.py"), command, *args, env=env)
    second = _run(sys.executable, str(TOOLS / "run.py"), command, *args, env=env)
    ensure(first == second,
           f"{command} answered differently on its second run:\n"
           f"first:  {first!r}\nsecond: {second!r}")
    return first


@dataclass
class _Flow:
    porcelain: str | None = None


_FLOW = _Flow()


def _status() -> str:
    code, out, err = _run("git", "-C", str(_ROOT), "status", "--porcelain")
    ensure(code == 0, f"git status failed: {err!r}")
    return out


def _tree_status_before() -> None:
    _FLOW.porcelain = _status()


def _coread_list_twice() -> None:
    code, out, _ = _twice_identical("coread")
    ensure(code == 0, f"list mode is a worklist and exits 0 either way, got {code}")
    ensure("pair" in out, f"the worklist names its pairs, got {out!r}")


def _unicode_pipe_twice() -> None:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "cp1252"
    code, out, err = _twice_identical(
        "coread", "--show", "R-05-158", env=environment)
    ensure(code == 0, f"redirected Unicode output failed: {err!r}")
    ensure("⊑" in out, f"the UTF-8 refinement symbol did not survive: {out!r}")


def _blast_radius_twice() -> None:
    code, out, _ = _twice_identical("blast")
    ensure(code == 0, f"bare mode on the live record exits 0, got {code}: {out!r}")
    ensure(out.startswith("the Vocabulary record's Prop fields and their consumers:"),
           f"bare mode prints the consumers map, got {out!r}")


def _typecheck_twice() -> None:
    code, out, _ = _twice_identical("typecheck")
    ensure(code == 0, f"the tools hold to their own discipline, got {code}: {out!r}")


def _check_twice() -> None:
    code, out, _ = _twice_identical("check")
    ensure(code == 0, f"the live tree checks clean, got {code}: {out!r}")
    ensure("every derived fact agrees with its artifact." in out,
           f"a clean run closes on its one sentence, got {out[-400:]!r}")


def _direct_check_unicode_twice() -> None:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "cp1252"
    argv = (sys.executable, str(TOOLS / "check.py"))
    first = _run(*argv, env=environment)
    second = _run(*argv, env=environment)
    ensure(first == second,
        "the direct checker answered differently on its second redirected run:\n"
        f"first:  {first!r}\nsecond: {second!r}")
    code, out, err = first
    ensure(code == 0, f"redirected direct-checker output failed: {err!r}")
    ensure("\ufffd" not in out + err,
        f"the direct checker's UTF-8 output did not survive: {out!r} {err!r}")


def _tree_status_after() -> None:
    ensure(_FLOW.porcelain is not None,
           "the before-case did not run, so there is nothing to hold the tree against")
    after = _status()
    ensure(after == _FLOW.porcelain,
           f"the doubled runs changed the tree:\nbefore: {_FLOW.porcelain!r}\n"
           f"after:  {after!r}")


def cases() -> list[Case]:
    # the first case captures the tree's state and the last holds the tree to it, so
    # everything between must leave no trace; `check.py` doubles past the ~2s mark
    # and rides in the slow set, which leaves the bracket and two doubled tools in
    # the fast one. The quarantined instruments' own doubled runs went with them and
    # are bracketed the same way by the quarantine's own gate.
    return [
        Case("locked-bootstrap", _locked_bootstrap),
        Case("settled-children-do-not-sync", _settled_children_do_not_sync),
        Case("bootstrap-prerequisites", _bootstrap_prerequisites),
        Case("tree-status-before", _tree_status_before, lane="host"),
        Case("coread-list-twice", _coread_list_twice, lane="host"),
        Case("unicode-pipe-twice", _unicode_pipe_twice, lane="host"),
        Case("blast-radius-twice", _blast_radius_twice, lane="host"),
        Case("typecheck-twice", _typecheck_twice, lane="host"),
        Case("check-twice", _check_twice, slow=True, lane="host"),
           Case("direct-check-unicode-twice", _direct_check_unicode_twice,
               slow=True, lane="host"),
        Case("tree-status-after", _tree_status_after, lane="host"),
    ]
