# SPDX-License-Identifier: Apache-2.0
"""The seeded-defect generator's accounting, and the three tools' host entry points.

Two things are pinned here that a run's output cannot show. The first is the **verdict
arithmetic**: counting a stillborn mutant as a kill is the standard way a mutation
score is inflated, and a run that did it would print a larger number and read exactly
like a better one. The second is that the loop **puts the tree back**: the `$[test]`
oracle writes into `model/`, which is a `-text` tree where a newline-translating round
trip rewrites every line of the file it touched.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import seed
from tests.harness import TOOLS, Case, ensure
from vos import mutate

_ROOT = TOOLS.parent


def _run(tool: str, *args: str) -> tuple[int, str]:
    done = subprocess.run([sys.executable, str(TOOLS / tool), *args],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=300, cwd=_ROOT)
    return done.returncode, done.stdout + done.stderr


def _mutant(line: int = 1) -> mutate.Mutant:
    return mutate.Mutant(ident=f"op/{line}", operator="op", path="f.sail", line=line,
                         start=0, end=1, before="a", after="b")


def _a_survivor_fails_the_run() -> None:
    out: list[str] = []
    code = seed.summarize(out, [seed.Verdict(_mutant(), seed.SURVIVED, "reproduced")],
                          "f.sail", "test")
    ensure(code == 1, "a survivor did not fail the run")
    ensure(any("survived" in line for line in out), f"the report said {out}")


def _a_stillborn_mutant_does_not_fail_the_run() -> None:
    """Nothing was decided about the oracle by a mutant that never compiled, so it is
    counted and reported and is not a finding."""
    out: list[str] = []
    code = seed.summarize(out, [seed.Verdict(_mutant(1), seed.KILLED, "moved", 4),
                                seed.Verdict(_mutant(2), seed.STILLBORN, "no build")],
                          "f.sail", "test")
    ensure(code == 0, f"a stillborn mutant beside a kill failed the run: {out}")
    ensure(any("1 killed, 0 survived, 1 stillborn" in line for line in out),
           f"the three verdicts were not counted apart: {out}")


def _an_all_stillborn_run_is_a_finding() -> None:
    """The vacuous pass every floor in this repository exists to catch: a population
    that never compiled measured the compiler and not the oracle."""
    out: list[str] = []
    code = seed.summarize(out, [seed.Verdict(_mutant(), seed.STILLBORN, "no build")],
                          "f.sail", "test")
    ensure(code == 1, "a run that decided nothing passed")
    ensure(any("decided nothing" in line for line in out), f"the report said {out}")


def _the_kill_span_is_reported() -> None:
    out: list[str] = []
    seed.summarize(out, [seed.Verdict(_mutant(1), seed.KILLED, "moved", 4),
                         seed.Verdict(_mutant(2), seed.KILLED, "moved", 61579)],
                   "f.sail", "test")
    ensure(any("between 4 and 61579 lines" in line for line in out),
           f"the span R1a's standard is stated in is absent: {out}")


def _a_sample_spreads_and_a_limit_takes_a_prefix() -> None:
    """A population is ordered by operator, so a prefix of it is one operator's
    mutants: `--limit` is for iterating and `--sample` is for measuring."""
    population = [_mutant(n) for n in range(100)]
    ensure([m.line for m in seed.chosen(population, 3, 0)] == [0, 1, 2],
           "a limit did not take a prefix")
    spread = [m.line for m in seed.chosen(population, 0, 4)]
    ensure(spread == [0, 25, 50, 75], f"a sample of four gave {spread}")
    ensure(len(seed.chosen(population, 0, 0)) == 100,
           "neither flag should narrow the population")
    ensure(len(seed.chosen(population, 0, 200)) == 100,
           "a sample larger than the population is the population")


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
    code, out = _run("oracle.py", "list")
    ensure(code == 0, f"the live specs do not parse: {out}")
    ensure("vector(s) in all" in out, f"the listing printed {out!r}")


def _oracle_emit_runs() -> None:
    code, out = _run("oracle.py", "emit", "--spec", "capformat")
    ensure(code == 0, f"the capformat harness did not emit: {out[-400:]}")
    ensure(out.startswith("// SPDX-License-Identifier"),
           "a generated Sail file does not open with the mark COPYRIGHT.md requires")
    ensure("function main() -> unit" in out, "the harness has no entry point")


def _seed_list_runs_over_a_live_source() -> None:
    code, out = _run("seed.py", "list", "--file",
                     "model/model/extensions/keccak/keccak_p1600.sail", "--limit", "3")
    ensure(code == 0, f"the live Sail source yields no population: {out[-400:]}")
    ensure("mutant(s) over" in out, f"the listing printed {out!r}")


def _seed_list_refuses_an_unmutable_kind() -> None:
    code, out = _run("seed.py", "list", "--file", "tools/seed.py")
    ensure(code != 0, "a Python file was given a lane")
    ensure("two lanes" in out, f"the refusal said {out!r}")


def cases() -> list[Case]:
    return [
        Case("a survivor fails the run", _a_survivor_fails_the_run),
        Case("a stillborn mutant does not", _a_stillborn_mutant_does_not_fail_the_run),
        Case("an all-stillborn run is a finding", _an_all_stillborn_run_is_a_finding),
        Case("the kill span is reported", _the_kill_span_is_reported),
        Case("a sample spreads where a limit takes a prefix",
             _a_sample_spreads_and_a_limit_takes_a_prefix),
        Case("a source round trips byte for byte", _a_source_round_trips_byte_for_byte),
        Case("a length change counts as movement", _moved_counts_a_length_change),
        Case("oracle.py list runs over the live specs", _oracle_list_runs, lane="host"),
        Case("oracle.py emit produces a marked harness", _oracle_emit_runs, lane="host"),
        Case("seed.py list runs over a live source",
             _seed_list_runs_over_a_live_source, lane="host"),
        Case("seed.py list refuses a kind it has no lane for",
             _seed_list_refuses_an_unmutable_kind, lane="host"),
    ]
