# SPDX-License-Identifier: Apache-2.0
"""The seeded-defect generator's own reading of a source, and the three tools' host
entry points.

What is pinned here is that the loop **puts the tree back**: the `$[test]` oracle
writes into `model/`, which is a `-text` tree where a newline-translating round trip
rewrites every line of the file it touched. The verdict arithmetic this tool reports
through is `vos/seeded.py`'s and is held in [test_seeded.py](test_seeded.py), beside
the module that decides it and beside the loops that share it.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos.cli import seed

_ROOT = TOOLS.parent


def _run(command: str, *args: str) -> tuple[int, str]:
    done = subprocess.run([sys.executable, str(TOOLS / "run.py"), command, *args],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=300, cwd=_ROOT)
    return done.returncode, done.stdout + done.stderr


def _a_source_round_trips_byte_for_byte() -> None:
    """`model/` is `-text` in .gitattributes, so a read that translated newlines and a
    write that put them back as LF would rewrite every line of a CRLF file while the
    loop believed it had restored it."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "crlf.sail"
        raw = b"function f() -> unit = ()\r\nfunction g() -> unit = ()\r\n"
        path.write_bytes(raw)
        text = seed.read_source(path)
        seed.write_source(path, text)
        ensure(path.read_bytes() == raw,
               f"the round trip rewrote the file: {path.read_bytes()!r}")


def _moved_counts_a_length_change() -> None:
    ensure(seed._moved(["a", "b"], ["a", "b"]) == 0,
           "two equal vector sets moved")
    ensure(seed._moved(["a", "b"], ["a", "c"]) == 1,
           "one changed line did not count as one")
    ensure(seed._moved(["a", "b", "c"], ["a"]) == 2,
           "a shortened answer did not count its missing lines")


def _oracle_list_runs() -> None:
    code, out = _run("oracle", "list")
    ensure(code == 0, f"the live specs do not parse: {out}")
    ensure("vector(s) in all" in out, f"the listing printed {out!r}")


def _oracle_emit_runs() -> None:
    code, out = _run("oracle", "emit", "--spec", "capformat")
    ensure(code == 0, f"the capformat harness did not emit: {out[-400:]}")
    ensure(out.startswith("// SPDX-License-Identifier"),
           "a generated Sail file does not open with the mark COPYRIGHT.md requires")
    ensure("function main() -> unit" in out, "the harness has no entry point")


def _seed_list_runs_over_a_live_source() -> None:
    code, out = _run("seed", "list", "--file",
                     "model/model/extensions/keccak/keccak_p1600.sail", "--limit", "3")
    ensure(code == 0, f"the live Sail source yields no population: {out[-400:]}")
    ensure("mutant(s) over" in out, f"the listing printed {out!r}")


def _seed_list_refuses_an_unmutable_kind() -> None:
    code, out = _run("seed", "list", "--file", "tools/vos/cli/seed.py")
    ensure(code != 0, "a Python file was given a lane")
    ensure("two lanes" in out, f"the refusal said {out!r}")


_LOCK_PROBE = """
import argparse
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, sys.argv[1])
from vos import env, gallina
from vos.cli import quickchick, seed

root = Path(sys.argv[1]).parent
with tempfile.TemporaryDirectory(prefix="vos-lock-") as td:
    lane = Path(td)
    e = env.Environment(root, root / "model", lane, lane, "", 1, 4096, 1, 1)
    prover = gallina.Prover("test-switch", ("unused-prover",))
    args = argparse.Namespace(spec="capformat", file=None, quickchick=False)
    cases = [(seed, "cmd_sail", "_sail_run", lane / "seed" / "sail-capformat", args)]
    for randomized in (False, True):
        args = argparse.Namespace(file="proofs/CyclicExecutive.v", quickchick=randomized)
        work = lane / "seed" / ("quickchick" if randomized else "coq")
        cases.append((seed, "cmd_coq", "_coq_run", work, args))
    for name in ("vectors", "properties", "freeze"):
        cases.append((quickchick, "cmd_" + name, "_" + name,
                      lane / gallina.WORK, argparse.Namespace(show=0)))

    with patch.object(seed, "lane_env", return_value=e), \\
         patch.object(env, "load", return_value=e), \\
         patch.object(gallina, "prover", return_value=prover):
        for module, command, worker, work, args in cases:
            work.mkdir(parents=True, exist_ok=True)
            marker = work / "live-source"
            marker.write_text("live mutant", encoding="utf-8")
            journal = work.with_suffix(".journal")
            journal.write_text("run in progress", encoding="utf-8")
            def run_while_held(*unused):
                try:
                    with env.hold_lock(work, "contender"):
                        raise AssertionError("worker entered without its workspace held")
                except SystemExit:
                    return 23
            with patch.object(module, worker, side_effect=run_while_held) as called:
                with env.hold_lock(work, "first run"):
                    try:
                        getattr(module, command)(args)
                    except SystemExit as refusal:
                        if "already holds" not in str(refusal):
                            raise
                    else:
                        raise AssertionError(command + " admitted a competing run")
                if called.called:
                    raise AssertionError(command + " entered its worker under contention")
                if marker.read_text(encoding="utf-8") != "live mutant" or \\
                   journal.read_text(encoding="utf-8") != "run in progress":
                    raise AssertionError(command + " changed the active run's evidence")
                if getattr(module, command)(args) != 23:
                    raise AssertionError(command + " lost its worker's exit status")
            with env.hold_lock(work, "next run"):
                pass
            with patch.object(module, worker, side_effect=RuntimeError("worker failed")):
                try:
                    getattr(module, command)(args)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError(command + " swallowed a worker failure")
            with env.hold_lock(work, "after failure"):
                pass
print("all workspace holders refuse contention and release after success or failure")
"""


def _mutation_workspaces_are_held_for_the_whole_run() -> None:
    """Exercise real guest file locks with compilation stubbed in a private process."""
    done = subprocess.run([sys.executable, "-c", _LOCK_PROBE, str(TOOLS)],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=60)
    ensure(done.returncode == 0,
           f"workspace contention or release failed: {done.stdout}\n{done.stderr}")


def cases() -> list[Case]:
    return [
        Case("a source round trips byte for byte", _a_source_round_trips_byte_for_byte),
        Case("a length change counts as movement", _moved_counts_a_length_change),
        Case("mutation workspaces are held for the whole run",
             _mutation_workspaces_are_held_for_the_whole_run, lane="guest"),
        Case("oracle list runs over the live specs", _oracle_list_runs, lane="host"),
        Case("oracle emit produces a marked harness", _oracle_emit_runs, lane="host"),
        Case("seed list runs over a live source",
             _seed_list_runs_over_a_live_source, lane="host"),
        Case("seed list refuses a kind it has no lane for",
             _seed_list_refuses_an_unmutable_kind, lane="host"),
    ]
