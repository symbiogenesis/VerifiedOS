# SPDX-License-Identifier: Apache-2.0
"""The seeded-defect generator's own reading of a source, and the three tools' host
entry points.

What is pinned here is that the loop **puts the tree back**: the `$[test]` oracle
writes into `model/`, which is a `-text` tree where a newline-translating round trip
rewrites every line of the file it touched. The verdict arithmetic this tool reports
through is `vos/seeded.py`'s and is held in [test_seeded.py](test_seeded.py), beside
the module that decides it and beside the loops that share it.

Also pinned, with a stub prover, is what `seed coq --quickchick` compiles: `Properties.v`'s
`Require` closure alone, what the walk harness Requires lying inside it, for its baseline
and for each mutant's dependents, a subject outside that closure refused before any
prover is asked.
"""

import argparse
import io
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from tests.harness import TOOLS, Case, ensure
from vos import gallina, mutate
from vos.cli import seed
from vos.seeded import SURVIVED

_ROOT = TOOLS.parent

# Properties.v Requires B, which Requires A, and two support harnesses, Probe over A and
# Side over C, and fixes its seed; the walk harness beside it Requires B. Far Requires A
# from outside that closure; Lone is support outside it, and Vectors is the enumerative
# entry point, which Requires Far.
_RIG = gallina.HARNESS_DIR
_CLOSED: dict[str, str] = {
    "proofs/A.v": "Definition a : nat := 1.\n",
    "proofs/B.v": "Require Import A.\nDefinition b : nat := a.\n",
    "proofs/C.v": "Definition c : nat := 2.\n",
    "proofs/Far.v": "Require Import A.\nDefinition far : nat := a.\n",
    f"{_RIG}/Probe.v": "Require Import A.\n",
    f"{_RIG}/Side.v": "Require Import C.\n",
    f"{_RIG}/Lone.v": "Require Import Far.\n",
    f"{_RIG}/{gallina.ENUMERATIVE}": "Require Import Far Probe.\n",
    f"{_RIG}/{gallina.RANDOMIZED}": "From QuickChick Require Import QuickChick.\n"
                                    "Require Import B Probe Side.\n"
                                    'Extract Constant newRandomSeed => '
                                    '"(Random.State.make [|7|])".\n',
    f"{_RIG}/{gallina.EXHAUSTIVE}": "Require Import B.\n",
}


@contextmanager
def _closed_tree() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="vos-seed-") as td:
        root = Path(td)
        for rel, text in _CLOSED.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8", newline="")
        yield root


@contextmanager
def _stub_prover(compiled: list[str]) -> Iterator[gallina.Prover]:
    """A prover that records each source it is handed, by stem, and prints one green
    property set and one vector for every compile, and one walked set that held for the
    walk harness's."""
    def compile_one(found: gallina.Prover, work: Path, source: Path,
                    timeout: int = 900) -> subprocess.CompletedProcess[str]:
        del found, work, timeout
        compiled.append(source.stem)
        if source.name == gallina.EXHAUSTIVE:
            return subprocess.CompletedProcess([], 0, '= ["prop_w 9 9 0 -"] : list string\n',
                                               "")
        return subprocess.CompletedProcess([], 0, '= ["v"]\n+++ Passed 10000 tests\n', "")

    with patch.object(gallina, "compile_one", side_effect=compile_one):
        yield gallina.Prover("stub", ("rocq", "c"))


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


def _the_randomized_mode_refuses_a_subject_outside_its_closure() -> None:
    """`--quickchick` mutates only a proof source `Properties.v`'s closure holds, and
    says so before it asks for a prover, whose lookup precedes any staging: a proof
    Requiring a member from outside, and a harness inside the closure, are each refused;
    the enumerative mode takes either proof."""
    asked: list[str] = []

    def absent(switch: str) -> None:
        asked.append(switch)

    with (_closed_tree() as root, patch.object(seed, "find_root", return_value=root),
          patch.object(seed, "lane_env", return_value=Mock()),
          patch.object(gallina, "prover", side_effect=absent)):
        ensure(seed.randomized_subjects(root) == ["proofs/A.v", "proofs/B.v", "proofs/C.v"],
               f"the closure's proof sources are A, B and C: {seed.randomized_subjects(root)}")
        for rel in ("proofs/Far.v", f"{_RIG}/Probe.v"):
            with redirect_stdout(io.StringIO()) as said:
                code = seed.cmd_coq(argparse.Namespace(file=rel, quickchick=True))
            text = said.getvalue()
            ensure(code == 1 and "is not a proof source Properties.v's Require closure" in text
                   and "mutates proofs/A.v, proofs/B.v, proofs/C.v" in text,
                   f"{rel} is refused with the closure's subjects named: {text}")
        ensure(not asked, f"a refused subject asks for no prover: {asked}")
        for rel, randomized in (("proofs/B.v", True), ("proofs/Far.v", False)):
            with redirect_stdout(io.StringIO()) as said:
                seed.cmd_coq(argparse.Namespace(file=rel, quickchick=randomized))
            ensure("no prover" in said.getvalue(),
                   f"{rel} reaches the prover's lookup: {said.getvalue()}")
    ensure(asked == [gallina.QUICKCHICK_SWITCH, gallina.VECTOR_SWITCH],
           f"the admitted subjects asked for their mode's switch: {asked}")


def _the_randomized_baseline_compiles_its_closure_alone() -> None:
    """The baseline compiles what `Properties.v` and the walk harness Require, in
    Require order, and then the walk harness and `Properties.v`: never the proof that
    Requires a member from outside the closure, the support harness outside it, nor
    another entry point."""
    compiled: list[str] = []
    with (_closed_tree() as root, tempfile.TemporaryDirectory(prefix="vos-work-") as wd,
          _stub_prover(compiled) as found):
        got = seed._quickchick_baseline(root, found, Path(wd) / "quickchick",
                                        gallina.RANDOMIZED)
    ensure(got == ([], ""), f"the stubbed baseline stands up green: {got}")
    ensure(compiled[-2:] == ["Walks", "Properties"]
           and sorted(compiled[:-2]) == ["A", "B", "C", "Probe", "Side"],
           f"the baseline compiled {compiled}, not the closure and then the harnesses")
    ensure(compiled.index("A") < min(compiled.index("B"), compiled.index("Probe"))
           and compiled.index("C") < compiled.index("Side"),
           f"a Require was compiled after what reads it: {compiled}")


def _a_randomized_mutant_compiles_its_dependents_in_the_closure() -> None:
    """A mutant under QuickChick compiles the proofs of the closure it moves, then the
    support harnesses there it moves, then the walk harness and the drawn one: never a
    proof outside the closure that Requires it. The enumerative mode, unchanged,
    compiles every proof that Requires the mutant and the rig's whole support."""
    mutant = mutate.Mutant(ident="op/1", operator="op", path="proofs/A.v", line=1,
                           start=0, end=1, before="a", after="b")
    compiled: list[str] = []
    with (_closed_tree() as root, tempfile.TemporaryDirectory(prefix="vos-work-") as wd,
          _stub_prover(compiled) as found):
        work = Path(wd) / "quickchick"
        gallina.stage(root, work)
        runs: dict[tuple[str, bool], list[str]] = {}
        for rel in ("proofs/A.v", "proofs/C.v"):
            for randomized in (True, False):
                compiled.clear()
                harness = work / "harness" / (gallina.RANDOMIZED if randomized
                                              else gallina.ENUMERATIVE)
                verdict = seed._coq_verdict(found, work, rel, harness, mutant, ["v"],
                                            randomized)
                ensure(verdict.outcome == SURVIVED,
                       f"{rel}: the stub decides nothing: {verdict}")
                closed = f"the proofs {gallina.RANDOMIZED}'s Require closure holds"
                ensure((closed in verdict.detail) == randomized,
                       f"{rel}: a reason names the closure's proofs exactly where only "
                       f"they were asked: {verdict.detail}")
                runs[rel, randomized] = list(compiled)
    want = {("proofs/A.v", True): ["A", "B", "Probe", "Walks", "Properties"],
            ("proofs/C.v", True): ["C", "Side", "Walks", "Properties"],
            ("proofs/A.v", False): ["A", "B", "Far", "Lone", "Probe", "Side", "Vectors"],
            ("proofs/C.v", False): ["C", "Lone", "Probe", "Side", "Vectors"]}
    ensure(runs == want, f"the mutants compiled {runs}, not {want}")


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
        Case("the randomized mode refuses a subject outside its closure",
             _the_randomized_mode_refuses_a_subject_outside_its_closure),
        Case("the randomized baseline compiles its closure alone",
             _the_randomized_baseline_compiles_its_closure_alone),
        Case("a randomized mutant compiles its dependents in the closure",
             _a_randomized_mutant_compiles_its_dependents_in_the_closure),
        Case("mutation workspaces are held for the whole run",
             _mutation_workspaces_are_held_for_the_whole_run, lane="guest"),
        Case("oracle list runs over the live specs", _oracle_list_runs, lane="host"),
        Case("oracle emit produces a marked harness", _oracle_emit_runs, lane="host"),
        Case("seed list runs over a live source",
             _seed_list_runs_over_a_live_source, lane="host"),
        Case("seed list refuses a kind it has no lane for",
             _seed_list_refuses_an_unmutable_kind, lane="host"),
    ]
