# SPDX-License-Identifier: Apache-2.0
"""The whole exit-evidence sweep over the curated model, as one run and one block.

Every landed item in the plan quotes the same measurements: the build and its
bundled suite, the model's own property harness, the profile sweep, the differential
corpus, the attested devicetree, the golden model's identity, and the proof gate.
Taking them was six commands into the guest and then a hand-transcription of six
figures into a completion note, which is six chances to quote a figure from a run
that is not the one being reported.

This is that sweep as one command. Each member runs in order, prints its own report
under its own heading exactly as it does alone, and the block at the end states the
figures those runs produced, read back out of what they printed rather than
re-derived. A member that did not report a figure says so; nothing here invents one.

    python tools/run.py evidence              # build, then measure
    python tools/run.py evidence --no-build   # measure what is already built

The build comes first because everything after it reads the simulator it produces,
so a failed build makes every later member a second symptom of the first, and it is
the one member whose output is not held back: it is a quarter of an hour long and
prints where its log is, which a caller wants when it is printed and not when the
sweep is over. The proof gate is the one member that reads none of the model, and it
runs last rather than first because it is the one a model change cannot move.

Exit 0 when every member exits 0, 1 otherwise.
"""

import argparse
import contextlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vos import env
from vos.cli import model as model_cli
from vos.cli import proofs as proofs_cli
from vos.report import Reporter

HEADING = "=== evidence: the exit-evidence sweep over the curated model ==="

# The bundled suite's tally, as ctest itself writes it into the build log.
_CTEST_RE = re.compile(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)")


@dataclass(frozen=True)
class Member:
    """One member of the sweep: what it is called, what it runs, and whether its
    output is held back for the block or streamed as it goes."""

    name: str
    decides: str
    run: Callable[[], int]
    captured: bool = True


MEMBERS: tuple[Member, ...] = (
    Member("build", "the model built and its bundled suite run",
           lambda: model_cli.main(["build"]), captured=False),
    Member("reference", "what the frozen golden model is",
           lambda: model_cli.main(["reference"])),
    Member("sweep", "the downloaded riscv-tests against the frozen profile",
           lambda: model_cli.main(["sweep"])),
    Member("corpus", "the differential corpus, assembled and run",
           lambda: model_cli.main(["corpus"])),
    Member("devicetree", "the attested devicetree, compiled and sized",
           lambda: model_cli.main(["devicetree"])),
    Member("proofs", "every shipped proof and its assumptions",
           lambda: proofs_cli.main([])),
)


def _one(rep: Reporter, member: Member) -> tuple[int, str]:
    """One member, under its own heading, as its exit code and what it printed."""
    rep.line(f"--- {member.name}: {member.decides} ---")
    kept = io.StringIO()
    try:
        if member.captured:
            with contextlib.redirect_stdout(kept):
                code = member.run()
        else:
            code = member.run()
    except SystemExit as refusal:
        # A member that refuses by raising is a finding here rather than the end of
        # the sweep: the block still has to say which member stopped, and why.
        code = 1 if refusal.code is None else int(refusal.code)
        kept.write(f"{member.name} refused: {refusal}\n")
    text = kept.getvalue()
    rep.out.extend(text.splitlines() or ["(this member reported as it ran, above)"])
    rep.line()
    return code, text


def _ctest(log: Path) -> str:
    """The bundled suite's tally, out of the build log the run wrote.

    Read from the log rather than from what `build` printed, because a build prints
    only where its log is: the tally is in the log whether this run built or an
    earlier one did, which is what makes `--no-build` state the same figure.
    """
    if not log.is_file():
        return "not reported (no build log in this lane)"
    found = _CTEST_RE.search(log.read_text(encoding="utf-8", errors="replace"))
    if found is None:
        return "not reported (the log carries no ctest tally)"
    failed, total = int(found.group(2)), int(found.group(3))
    return f"{total - failed} of {total}"


def _figure(text: str, pattern: str, wording: Callable[[re.Match[str]], str]) -> str:
    """One figure out of one member's output, or the sentence saying it is absent."""
    found = re.search(pattern, text)
    return wording(found) if found else "not reported by its member"


def _block(rep: Reporter, said: dict[str, str], log: Path) -> None:
    """The figures the sweep produced, in the order a completion note states them."""
    reference, sweep = said.get("reference", ""), said.get("sweep", "")
    corpus, tree = said.get("corpus", ""), said.get("devicetree", "")
    proofs = said.get("proofs", "")

    rows = [
        ("model revision", _figure(reference, r"model revision\s+(\S+)",
                                   lambda m: m.group(1))),
        ("ctest", _ctest(log)),
        ("$[test] harness", _figure(reference, r"properties\s+(\d+)",
                                    lambda m: f"{int(m.group(1)):,} properties")),
        ("profile sweep", _figure(
            sweep, r"TOTAL pass=(\d+) refuse=(\d+) hang=(\d+) of (\d+)",
            lambda m: f"{int(m.group(2)):,} refusals of {int(m.group(4)):,}"
                      + (f", {m.group(3)} hang(s)" if m.group(3) != "0" else ""))),
        ("differential corpus", _figure(
            corpus, r"TOTAL pass=(\d+) fail=(\d+) of (\d+) \(corpus v(\d+)",
            lambda m: f"{m.group(1)} of {m.group(3)} at manifest version {m.group(4)}"
                      + (f", {m.group(2)} failing" if m.group(2) != "0" else ""))),
        ("corpus size", _figure(
            reference, r"corpus\s+v\d+, \d+ members, (\d+) checks, (\d+) records",
            lambda m: f"{int(m.group(1)):,} checks over {int(m.group(2)):,} records")),
        ("devicetree", _figure(tree, r"at (\d+) bytes",
                               lambda m: f"{int(m.group(1)):,} bytes, no warning")),
        ("proof gate", _figure(proofs, r"ok: (\d+) constant",
                               lambda m: f"{int(m.group(1)):,} constants closed")),
    ]

    rep.line("=== exit evidence ===")
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        rep.line(f"  {label:<{width}}  {value}")
    rep.line()


def run(build: bool = True) -> Reporter:
    """One whole sweep, as data, on the convention `check.py` set."""
    e = env.load()
    rep = Reporter()
    rep.line(HEADING)

    said: dict[str, str] = {}
    stopped: list[str] = []
    for member in MEMBERS:
        if member.name == "build" and not build:
            continue
        code, text = _one(rep, member)
        said[member.name] = text
        if code != 0:
            stopped.append(f"{member.name}: exited {code}, reported above")
            # Everything after the build reads the simulator it produces, so a
            # failed build makes every later member a second symptom of the first.
            if member.name == "build":
                break

    _block(rep, said, e.log("model-build"))
    rep.report("evidence", "member(s) that did not come back clean:", stopped,
               f"all {len(said)} member(s) of the sweep green")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py evidence",
        description="Take the whole exit-evidence sweep over the curated model.")
    parser.add_argument("--no-build", action="store_true",
                        help="measure the tree as it is built, without rebuilding it")
    args = parser.parse_args(argv)

    report = run(build=not args.no_build)
    print("\n".join(report.out))
    return 1 if report.findings else 0
