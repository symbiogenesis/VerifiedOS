# SPDX-License-Identifier: Apache-2.0
"""The verdict arithmetic every mutation loop here shares.

What is pinned is what a run's output cannot show. Counting a stillborn mutant as a
kill is the standard way a mutation score is inflated, and a run that did it would
print a larger number and read exactly like a better one. Counting an unseeded case
the same way as a stillborn mutant would be the quieter version of it: a case that has
stopped applying to the document it was written against decides nothing and would
report its rule live for as long as nobody looked, so the two verdicts are apart here
and one of them fails the run.

The other half is the protocol. Two populations reach `summarize`, one walked out of a
source and one authored, and each satisfies `Seeded` from a different shape: a walked
mutant carries a site and a rewrite, an authored case carries the rule it is aimed at
and the defect in words. Both are held here, because a signature that admitted only
one of them would be found by running the loop that carries the other.
"""

from tests.harness import Case, ensure
from vos import mutate, seeded
from vos.cli import selftest


def _mutant(line: int = 1) -> mutate.Mutant:
    return mutate.Mutant(ident=f"op/{line}", operator="op", path="f.sail", line=line,
                         start=0, end=1, before="a", after="b")


def _a_survivor_fails_the_run() -> None:
    """And says how it survived, which is what decides the repair: a run that reported
    nothing and a run that died before it could report look the same from the rule's
    side and are two different defects."""
    out: list[str] = []
    code = seeded.summarize(
        out, [seeded.Verdict(_mutant(), seeded.SURVIVED, "reproduced")], "f.sail", "test")
    ensure(code == 1, "a survivor did not fail the run")
    ensure(any("survived" in line for line in out), f"the report said {out}")
    ensure(any("reproduced" in line for line in out),
           f"the survivor was reported without how it survived: {out}")


def _a_stillborn_mutant_does_not_fail_the_run() -> None:
    """Nothing was decided about the oracle by a mutant that never compiled, so it is
    counted and reported and is not a finding."""
    out: list[str] = []
    code = seeded.summarize(out, [seeded.Verdict(_mutant(1), seeded.KILLED, "moved", 4),
                                  seeded.Verdict(_mutant(2), seeded.STILLBORN, "no build")],
                            "f.sail", "test")
    ensure(code == 0, f"a stillborn mutant beside a kill failed the run: {out}")
    ensure(any("1 killed, 0 survived, 1 stillborn" in line for line in out),
           f"the three verdicts were not counted apart: {out}")


def _an_unseeded_mutant_is_a_finding() -> None:
    """The verdict a stillborn mutant must not be merged with.

    A stillborn mutant is a fact about the subject: the seed applied and the result did
    not build. An unseeded one is a fact about the case: the seed did not apply, so the
    artifact it was written against has moved and nothing was asked of the oracle at
    all. Only the second is a defect in the population, and only the second fails.
    """
    out: list[str] = []
    code = seeded.summarize(out, [seeded.Verdict(_mutant(1), seeded.KILLED, "moved"),
                                  seeded.Verdict(_mutant(2), seeded.UNSEEDED, "moved off")],
                            "f.sail", "test")
    ensure(code == 1, f"an unseeded mutant beside a kill passed the run: {out}")
    ensure(any("seeded nothing" in line for line in out),
           f"the report does not say the oracle was never asked: {out}")
    ensure(any("1 unseeded" in line for line in out),
           f"the fourth verdict was not counted: {out}")


def _no_unseeded_verdict_is_reported_as_none() -> None:
    """A loop that cannot produce the verdict reports what it reported before this
    module carried it: the count is printed only where there is one."""
    out: list[str] = []
    seeded.summarize(out, [seeded.Verdict(_mutant(), seeded.KILLED, "moved")],
                     "f.sail", "test")
    ensure(not any("unseeded" in line for line in out),
           f"a run with no unseeded mutant named the verdict anyway: {out}")


def _an_all_stillborn_run_is_a_finding() -> None:
    """The vacuous pass every floor in this repository exists to catch: a population
    that never compiled measured the compiler and not the oracle."""
    out: list[str] = []
    code = seeded.summarize(
        out, [seeded.Verdict(_mutant(), seeded.STILLBORN, "no build")], "f.sail", "test")
    ensure(code == 1, "a run that decided nothing passed")
    ensure(any("decided nothing" in line for line in out), f"the report said {out}")


def _an_empty_population_is_a_finding() -> None:
    """The same floor one step lower, and the one the checker's oracle can reach: it
    produces no stillborn mutant ever, so nothing but an empty case table leaves it
    with no live population at all."""
    out: list[str] = []
    ensure(seeded.summarize(out, [], "f.sail", "test") == 1,
           f"a run over no mutants at all passed: {out}")


def _the_kill_span_is_reported() -> None:
    out: list[str] = []
    seeded.summarize(out, [seeded.Verdict(_mutant(1), seeded.KILLED, "moved", 4),
                           seeded.Verdict(_mutant(2), seeded.KILLED, "moved", 61579)],
                     "f.sail", "test")
    ensure(any("between 4 and 61579 lines" in line for line in out),
           f"the span R1a's standard is stated in is absent: {out}")


def _a_kill_on_no_measured_movement_claims_no_span() -> None:
    """An oracle whose answer is a rule firing has nothing to say beyond that it fired,
    so it reports `moved` as zero and the span line must not invent a unit for it."""
    out: list[str] = []
    seeded.summarize(out, [seeded.Verdict(_mutant(), seeded.KILLED, "reported")],
                     "f.sail", "test")
    ensure(not any("lines" in line for line in out),
           f"a kill that measured no movement was given a span: {out}")


def _a_sample_spreads_and_a_limit_takes_a_prefix() -> None:
    """A population is ordered by operator, so a prefix of it is one operator's
    mutants: `--limit` is for iterating and `--sample` is for measuring."""
    population = [_mutant(n) for n in range(100)]
    ensure([m.line for m in seeded.chosen(population, 3, 0)] == [0, 1, 2],
           "a limit did not take a prefix")
    spread = [m.line for m in seeded.chosen(population, 0, 4)]
    ensure(spread == [0, 25, 50, 75], f"a sample of four gave {spread}")
    ensure(len(seeded.chosen(population, 0, 0)) == 100,
           "neither flag should narrow the population")
    ensure(len(seeded.chosen(population, 0, 200)) == 100,
           "a sample larger than the population is the population")


def _an_authored_case_satisfies_the_protocol() -> None:
    """The other population `summarize` reports on, named from a row rather than a
    site. What a reader has to be able to do with a finding is go and look at it, and
    for an authored case that means the rule and the defect in words."""
    seeding = selftest.Seeding("K-42", "a bookmark the prose no longer declares")
    ensure(seeding.what == "K-42: a bookmark the prose no longer declares",
           f"an authored case names itself {seeding.what!r}")
    out: list[str] = []
    ensure(seeded.summarize(
        out, [seeded.Verdict(seeding, seeded.UNSEEDED, "the document has moved")],
        "tools/check-rules.md", "checker") == 1,
        f"an authored case's unseeded verdict passed: {out}")
    ensure(any("K-42" in line for line in out),
           f"the finding does not name the case it is about: {out}")


def _a_partial_run_says_so_on_the_line_that_gets_quoted() -> None:
    """The closing `ok` line is what a completion note copies, so a run over part of a
    population has to carry its scope there and not only in the block above it. This is
    the defect the scope exists for: a green line quoted out of a narrowed run reads as
    a whole-population result at every later citation."""
    out: list[str] = []
    code = seeded.summarize(
        out, [seeded.Verdict(_mutant(), seeded.KILLED, "moved")], "f.sail", "test",
        seeded.Scope(whole=382, ran=16, left=("const-inc",)))
    ensure(code == 0, "a killed mutant failed the run")
    closing = out[-1]
    ensure(closing.startswith("ok "), f"the closing line was {closing!r}")
    ensure("16 of 382" in closing and "not the population" in closing,
           f"the closing line does not carry the scope: {closing!r}")
    ensure(any("const-inc" in line for line in out),
           f"an operator nothing asked about went unnamed: {out}")


def _a_whole_run_says_that_too() -> None:
    """Stated rather than left to silence. An absent scope line and a whole-population
    scope line would otherwise read the same, which puts the reader back to guessing
    which kind of run produced the number."""
    out: list[str] = []
    seeded.summarize(out, [seeded.Verdict(_mutant(), seeded.KILLED, "moved")],
                     "f.sail", "test", seeded.Scope(whole=1, ran=1))
    ensure("whole population" in out[-1], f"the closing line was {out[-1]!r}")


def _a_loop_that_passes_no_scope_reports_what_it_did_before() -> None:
    """The scope is an addition to this report and never a silent change to one: the
    checker's authored oracle passes none and its output must not move."""
    out: list[str] = []
    seeded.summarize(out, [seeded.Verdict(_mutant(), seeded.KILLED, "moved")],
                     "f.sail", "test")
    ensure(out[-1] == "ok all 1 live mutant(s) were killed by the test oracle",
           f"a scopeless run's closing line moved: {out[-1]!r}")
    ensure(not any("scope" in line for line in out),
           f"a scopeless run printed a scope: {out}")


def _a_scope_is_partial_only_when_it_ran_less() -> None:
    ensure(not seeded.Scope(whole=8, ran=8).partial, "a whole scope read as partial")
    ensure(seeded.Scope(whole=8, ran=7).partial, "a partial scope read as whole")


def cases() -> list[Case]:
    return [
        Case("a partial run says so on the quoted line",
             _a_partial_run_says_so_on_the_line_that_gets_quoted),
        Case("a whole run says that too", _a_whole_run_says_that_too),
        Case("a loop passing no scope is unmoved",
             _a_loop_that_passes_no_scope_reports_what_it_did_before),
        Case("a scope is partial only when it ran less",
             _a_scope_is_partial_only_when_it_ran_less),
        Case("a survivor fails the run", _a_survivor_fails_the_run),
        Case("a stillborn mutant does not", _a_stillborn_mutant_does_not_fail_the_run),
        Case("an unseeded mutant is a finding", _an_unseeded_mutant_is_a_finding),
        Case("a run with none reports no unseeded count",
             _no_unseeded_verdict_is_reported_as_none),
        Case("an all-stillborn run is a finding", _an_all_stillborn_run_is_a_finding),
        Case("an empty population is a finding", _an_empty_population_is_a_finding),
        Case("the kill span is reported", _the_kill_span_is_reported),
        Case("a kill on no measured movement claims no span",
             _a_kill_on_no_measured_movement_claims_no_span),
        Case("a sample spreads where a limit takes a prefix",
             _a_sample_spreads_and_a_limit_takes_a_prefix),
        Case("an authored case satisfies the protocol",
             _an_authored_case_satisfies_the_protocol),
    ]
