# SPDX-License-Identifier: Apache-2.0
"""The hosted corpus verdict must include actual persistent-device execution."""

import argparse
import io
import sys
import tempfile
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.harness import Case, ensure
from vos import env
from vos.cli import model


def _environment(root: Path) -> env.Environment:
    return env.Environment(root, root / "model", root / "build", root / "logs",
                           "", 4, 4096, 2, 2)


def _arguments(**changes: object) -> argparse.Namespace:
    values: dict[str, object] = {"member": [], "assemble_only": False,
                                 "refresh": False, "persistence_only": False,
                                 "out": None, "timeout": 30}
    values.update(changes)
    return argparse.Namespace(**values)


def _full_corpus_combines_verdicts() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        elf = root / "member.elf"
        elf.write_bytes(b"fixture")
        corpus = SimpleNamespace(members=[SimpleNamespace(name="member")],
                                 version=1, trace_schema=1)
        for member_verdict, persistence, expected in (
                ("PASS", 0, 0), ("PASS", 1, 1), ("FAIL", 0, 1), ("FAIL", 1, 1)):
            with (patch.object(model.differential, "load", return_value=corpus),
                  patch.object(model.differential, "assemble", return_value=elf),
                  patch.object(model, "_run_member", return_value=(member_verdict, "", None)),
                  patch.object(model, "_corpus_persistence", return_value=persistence) as run,
                  redirect_stdout(io.StringIO())):
                result = model.cmd_corpus(_environment(root), _arguments())
            ensure(result == expected and run.call_count == 1,
                   "each independent failure must fail the full corpus, with both checks run")
        for arguments in (_arguments(member=["member"]), _arguments(assemble_only=True)):
            with (patch.object(model.differential, "load", return_value=corpus),
                  patch.object(model.differential, "assemble", return_value=elf),
                  patch.object(model, "_run_member", return_value=("PASS", "", None)),
                  patch.object(model, "_corpus_persistence") as run,
                  redirect_stdout(io.StringIO())):
                ensure(model.cmd_corpus(_environment(root), arguments) == 0,
                       "a named or assembly-only check retains its own scope")
            ensure(run.call_count == 0, "a focused member must not launch persistence")


def _explicit_scope_and_conflicts() -> None:
    e = _environment(Path("unused"))
    for verdict in (0, 1):
        with (patch.object(model, "_corpus_persistence", return_value=verdict) as run,
              patch.object(model.differential, "load", side_effect=AssertionError("loaded corpus"))):
            ensure(model.cmd_corpus(e, _arguments(persistence_only=True)) == verdict,
                   "persistence-only must return the campaign's actual verdict")
        ensure(run.call_count == 1, "explicit persistence must execute once")
    for conflict in ({"member": ["member"]}, {"refresh": True}, {"assemble_only": True}):
        with (patch.object(model, "_corpus_persistence") as run,
              redirect_stderr(io.StringIO())):
            result = model.cmd_corpus(e, _arguments(persistence_only=True, **conflict))
        ensure(result == 1 and run.call_count == 0,
               "contradictory scope must refuse before running any campaign")


def _campaign_lock() -> Mock:
    """`env.hold_lock` itself where `flock` exists, and on a Windows host, which has
    none, a stand-in that holds nothing; either records what the campaign locked."""
    return Mock(wraps=env.hold_lock) if sys.platform != "win32" else Mock(return_value=nullcontext())


def _incomplete_or_crashed_campaign_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        e = _environment(Path(td))
        outputs = []
        for report, expected in (({"passed": True}, 0), ({"passed": False}, 1),
                                 ({}, 1), ({"passed": "true"}, 1)):
            run, lock = Mock(return_value=report), _campaign_lock()
            with (patch.object(model.block_persistence, "run", run),
                  patch.object(model.env, "hold_lock", lock),
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                result = model._corpus_persistence(e, e.lane_root / "corpus", 30)
            ensure(result == expected, "only an explicit passing campaign supplies acceptance")
            ensure(lock.call_args.args[0] == run.call_args.args[3],
                   "the campaign holds the lock beside its own output directory")
            outputs.append(run.call_args.args[3])
        ensure(len(set(outputs)) == len(outputs), "reruns must use fresh persistent image directories")
        with (patch.object(model.block_persistence, "run", side_effect=OSError("image unavailable")),
              patch.object(model.env, "hold_lock", _campaign_lock()),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            ensure(model._corpus_persistence(e, e.lane_root / "corpus", 30) == 1,
                   "an unavailable backing image must fail the hosted command")


def cases() -> list[Case]:
    return [Case("full-corpus-combines-verdicts", _full_corpus_combines_verdicts),
            Case("explicit-scope-and-conflicts", _explicit_scope_and_conflicts),
            Case("incomplete-or-crashed-campaign-fails", _incomplete_or_crashed_campaign_fails)]
