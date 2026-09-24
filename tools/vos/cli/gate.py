# SPDX-License-Identifier: Apache-2.0
"""Validate the checkout with one host-gate verdict.

The default runs the checker, selftest and typecheck read-only, each in its own
process. `--check` is the same read-only run, named for a caller that wants no
ambiguity with `--fix`. `--fix` repairs derived facts alone, then runs a fresh
read-only checker alongside the selftest and typecheck.
Repair findings describe the old tree; only the final wave decides the repaired tree.
A repair without a verdict stops before that wave.

Independent gates run concurrently and report in declaration order. `--tests` adds the
tools' behavioral tests; those stay optional to keep document checks small and avoid
recursive test launches. Exit 0 means every final gate passed, 1 otherwise.

`--summary` writes the same verdict as data. The prose below says which member to read
and is what a person wants; a caller that has only the process's exit code has four
members collapsed into one number, which is the state a CI run reaches whoever reads it
without opening the log. The file is written outside the checkout, at the path the
caller names, and the reader decides what to render from it rather than parsing what
was printed.
"""

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from vos import corpus as corpus_mod
from vos import sharding
from vos.report import Reporter
from vos.sharding import Shard

HEADING = "=== gate: every host gate over this tree, in one run ==="

# Allow cold sandbox construction and the complete mutation and behavioral suites
# on slower runners. A member that reaches this bound must become a finding rather
# than a command that never returns.
TIMEOUT = 900

# What a member that never answered exited with. It has no code of its own, and a
# number outside the (0, 1) the conventions define is what makes it read as the
# crash it is rather than as the finding it is not.
NO_VERDICT = -1


@dataclass(frozen=True)
class Launch:
    """One member: the command, the arguments it takes here, and what it decides."""

    tool: str
    args: tuple[str, ...]
    decides: str

    @property
    def name(self) -> str:
        """How the member is named in the report, which is the command that ran."""
        return " ".join((self.tool, *self.args))


@dataclass
class Result:
    """One member's output, exit code and elapsed wall time, including launch."""

    launch: Launch
    code: int
    out: list[str]
    elapsed_seconds: float = 0.0


MEMBERS: tuple[Launch, ...] = (
    Launch("check", (), "every derived fact against the artifact that owns it"),
    Launch("selftest", (), "every rule the checker carries, against its mutant"),
    Launch("typecheck", (), "the tools' own Python, under two pinned checkers"),
)

# The member `--tests` adds, named here rather than spelled at its call site so that
# the wave's membership is one table.
TESTS = Launch("test", (), "the tools' own behavior, against the cases that hold it")

# The one member with a --fix branch, named rather than taken by position so that
# reordering the table above cannot quietly move which member the repair wave holds.
REPAIRS = "check"


def _plan(fix: bool, tests: bool, shard: Shard | None = None) -> list[list[Launch]]:
    """An optional isolated repair, then every read-only gate, including a fresh check."""
    members = [*MEMBERS, *([TESTS] if tests else [])]
    if shard is not None:
        if fix:
            raise ValueError("--shard cannot be combined with --fix")
        members = [Launch(m.tool, (*m.args, "--shard", str(shard)), m.decides)
                   if m.tool in ("selftest", "test") else m
                   for m in members if shard.index == 1 or m.tool in ("selftest", "test")]
    if not fix:
        return [members]
    repair = [Launch(m.tool, (*m.args, "--fix"), m.decides)
              for m in members if m.tool == REPAIRS]
    return [repair, members]


def _launch(root: Path, member: Launch) -> Result:
    """One member, in its own process, as what it printed and the code it exited.

    A subprocess rather than an import, and for reasons rather than for symmetry.
    The selftest reports by printing as it goes rather than by handing back a slate,
    so its verdict is a stream and this is what reads it. And a member's exit code is
    its own to decide, which keeps this tool from re-deriving three verdicts it would
    then have to keep in agreement with three `main` functions.

    Neither of the two ways a run can fail short of a verdict is allowed to become
    a traceback here: a member that hangs and a member that cannot be executed are
    both findings, on the convention typecheck.py's own runner keeps.
    """
    argv = [sys.executable, str(root / "tools" / "run.py"), member.tool, *member.args]
    started = time.perf_counter()
    try:
        done = subprocess.run(argv, capture_output=True, encoding="utf-8",
                              errors="replace", cwd=root, check=False, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return Result(member, NO_VERDICT,
                      [f"{member.name} gave no verdict within {TIMEOUT}s"],
                      time.perf_counter() - started)
    except OSError as err:
        return Result(member, NO_VERDICT, [f"{member.name} could not be run: {err}"],
                      time.perf_counter() - started)
    # stderr after stdout and never instead of it: a member reports on stdout, so
    # anything on stderr is what it said while dying and belongs under its heading
    # rather than lost.
    return Result(member, done.returncode, (done.stdout + done.stderr).splitlines(),
                  time.perf_counter() - started)


def _show(rep: Reporter, result: Result) -> None:
    """Keep a process's diagnostic output even when a later check supersedes it."""
    rep.line(f"--- {result.launch.name}: {result.launch.decides} ---")
    rep.line(f"elapsed: {result.elapsed_seconds:.2f}s")
    rep.out.extend(result.out)
    rep.line()


def _verdict(rep: Reporter, results: list[Result]) -> None:
    """Every member's own report under its own heading, then the line over them all.

    A member that exited 1 has already printed the findings it is being counted
    for, so what is said here is which member to go and read. A member that exited
    anything else printed no verdict at all, and saying so is the difference
    between a tree with a finding in it and a tool that did not run.
    """
    for result in results:
        _show(rep, result)

    rep.report("gate", "gate(s) that did not come back clean:",
               [f"{r.launch.name}: reported, above"
                if r.code == 1 else
                f"{r.launch.name}: exited {r.code} without reaching a verdict"
                for r in results if r.code != 0],
               f"all {len(results)} host gate(s) green")


def _verdict_data(results: list[Result], stopped: str = "") -> dict[str, object]:
    """What the wave decided, as data rather than as the lines a person reads.

    One record per member, each carrying the three things a reader has to tell apart:
    the command that ran, the code it exited, and whether that code is a verdict at all.
    `stopped` is the sentence that stands where no wave ran, which is the case a bare
    exit code cannot distinguish from a failing member and the one a reader most needs
    named: a repair that crashed without reaching a verdict ends here.
    """
    return {
        "green": bool(results) and all(r.code == 0 for r in results),
        "stopped": stopped,
        "members": [{"name": r.launch.name,
                     "decides": r.launch.decides,
                     "code": r.code,
                     "elapsed_seconds": r.elapsed_seconds,
                     "reached_verdict": r.code in (0, 1),
                     "clean": r.code == 0}
                    for r in results],
    }


def _write_summary(rep: Reporter, path: Path, data: dict[str, object]) -> None:
    """Put the verdict where a caller asked for it, or say it could not be put there.

    A finding on the convention `_launch` keeps: a run asked to say what it decided and
    unable to has not answered, and a CI failure nothing can name is the state this flag
    exists to end. The prose report is written either way, so the finding adds a reason
    rather than replacing one, and it is reported ahead of the wave's own verdict so
    that line stays last.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError as err:
        rep.report("summary", "per-member verdict:", [f"{path} could not be written: {err}"])
        return
    rep.report("summary", "per-member verdict:", [], ok=f"written to {path}")


def run(root: Path, fix: bool = False, tests: bool = False, check: bool = False,
        summary: Path | None = None, shard: Shard | None = None) -> Reporter:
    """Run the repair wave, if asked, then decide only the final validation wave."""
    if fix and check:
        raise ValueError("--fix and --check are mutually exclusive")
    rep = Reporter()
    rep.line(HEADING if shard is None else f"=== gate: shard {shard}; every shard must pass ===")

    plan = _plan(fix, tests, shard)
    if fix:
        repair = _launch(root, plan[0][0])
        _show(rep, repair)
        if repair.code not in (0, 1):
            stopped = (f"repair did not complete: {repair.launch.name} exited "
                       f"{repair.code} without reaching a verdict")
            rep.report("gate", "repair did not complete:",
                       [f"{repair.launch.name}: exited {repair.code} without reaching a verdict"])
            if summary is not None:
                _write_summary(rep, summary, _verdict_data([], stopped))
            return rep
        rep.line("repair pass complete; the fresh validation below decides the repaired tree")

    wave = plan[-1]
    with ThreadPoolExecutor(max_workers=len(wave)) as pool:
        results = list(pool.map(lambda member: _launch(root, member), wave))
    if summary is not None:
        data = _verdict_data(results)
        if shard is not None:
            data["shard"] = {"index": shard.index, "total": shard.total}
        _write_summary(rep, summary, data)
    _verdict(rep, results)
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py gate",
        description="Run the host's gates together and answer with one verdict.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fix", action="store_true",
                      help="repair derived facts, then validate")
    mode.add_argument("--check", action="store_true",
                      help="validate without repairing files")
    parser.add_argument("--tests", action="store_true",
                        help="add the tools' own behavioral tests to the wave")
    parser.add_argument("--summary", metavar="PATH", type=Path,
                        help="also write the per-member verdict there as JSON, for a "
                             "caller that has only this run's exit code")
    parser.add_argument("--shard", type=sharding.parse, metavar="INDEX/TOTAL",
                        help="partition selftest and tests; shard 1 also checks and typechecks; "
                             "all shards are required for a complete verdict")
    args = parser.parse_args(argv)
    if args.fix and args.shard is not None:
        parser.error("--shard cannot be combined with --fix")

    plan = _plan(args.fix, args.tests, args.shard)
    # The member reports remain accumulated in declaration order; this preflight
    # states what is running while the wave has not yet returned.
    preflight = "repairing derived facts; " if args.fix else ""
    print(preflight + f"running {len(plan[-1])} host gate(s): "
          + ", ".join(m.name for m in plan[-1]), flush=True)

    report = run(corpus_mod.find_root(), fix=args.fix, tests=args.tests, check=args.check,
                 summary=args.summary, shard=args.shard)
    print("\n".join(report.out))
    return 1 if report.findings else 0
