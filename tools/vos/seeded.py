# SPDX-License-Identifier: Apache-2.0
"""What a mutation run decides, spelled once for every oracle that runs one.

Four loops in this tree seed a defect and ask whether something noticed, and until
this module they agreed about the method and disagreed about everything a reader
sees: three of them counted the verdicts one way and the fourth counted them
another, each with its own tallies, its own report and its own arithmetic from
verdicts to an exit code. That is one engine written four times, and the failure
mode is the quiet one: an accounting that drifts between loops reads like two
different measurements of two different things.

So the vocabulary lives here and the loops keep only what is theirs, which is the
oracle. `vos/mutate.py` generates a population where the checker's selftest authors
one, and that difference is real and stays; what a *verdict* is does not depend on
where the mutant came from.

## The four verdicts, and why the fourth is not the third

**Killed** is a mutant that reached the oracle and moved its answer. **Survived** is
one that reached the oracle and did not, and it is the finding this whole method
exists to produce: the oracle does not decide about that site.

**Stillborn** is a mutant that never reached the oracle at all, because it did not
compile. Nothing was decided about the oracle by it, so it is counted, reported, and
deliberately **not** a finding, and the score is over the live population. Counting
stillborn mutants as kills is the standard way a mutation score is inflated, which is
why they are counted apart rather than dropped.

**Unseeded** is a mutant that never reached the oracle either, and it is a finding,
which is the one place a reader has to be careful. The two are not the same verdict
and merging them would lose the distinction that matters. A stillborn mutant is a
fact about the *subject*: the seed was applied and the result did not build, which is
an ordinary outcome of walking a source with an operator table that cannot know which
sites type. An unseeded mutant is a fact about the *case*: the seed did not apply,
so the artifact it was written against has moved and the case has stopped asking
anything. A generated population regenerates itself against whatever the source now
holds and cannot go unseeded; an authored one can, and would go on reporting its rule
live for exactly as long as nobody looked. That is why the population that can drift
is the one whose third verdict fails the run.

The two are therefore produced by different loops rather than by one loop's taste. A
generated oracle yields stillborn mutants and never unseeded ones; the checker's
authored oracle yields unseeded ones and never stillborn ones, its oracle being a
subprocess that always runs. `summarize` carries both because it is one report over
both, not because either loop is expected to produce the other's.
"""

from dataclasses import dataclass
from typing import Protocol

# The four verdicts, spelled once.
KILLED = "killed"
SURVIVED = "survived"
STILLBORN = "stillborn"
UNSEEDED = "unseeded"


class Seeded(Protocol):
    """What a verdict needs of the thing it is about, and the whole of it.

    One line naming the defect well enough that a reader can go and look at it.
    `mutate.Mutant` spells that as its site and its rewrite; an authored case has no
    site and spells it as the rule it is aimed at and the defect in words. Nothing
    else here reads anything else off a mutant, so nothing else is required.
    """

    @property
    def what(self) -> str: ...


@dataclass(frozen=True)
class Scope:
    """How much of a population a run covered, and what it left behind.

    A narrowed run is evidence about the mutants it ran and about nothing else, and the
    way that goes wrong is silence rather than error: a report stating its verdicts and
    not its scope reads as a whole-population run at every later citation, and the
    citation is what a completion note quotes. So the scope travels with the verdicts,
    is printed whether or not it is whole, and is repeated on the closing line, because
    the closing line is the one that gets copied.

    `left` names the axis a reader can act on rather than listing the absent mutants; a
    caller that knows its population's axes fills it and one that does not leaves it
    empty. Being partial is not a finding and does not fail a run: `--limit` and
    `--sample` are legitimate and the point here is that their result cannot be quoted
    as something it is not.
    """

    whole: int
    ran: int
    left: tuple[str, ...] = ()

    @property
    def partial(self) -> bool:
        return self.ran < self.whole

    def stated(self) -> str:
        """The scope as one clause, for the closing line to carry."""
        if not self.partial:
            return f"over the whole population of {self.whole} mutant(s)"
        return (f"over {self.ran} of {self.whole} mutant(s), which is a sample and "
                "not the population")


@dataclass(frozen=True)
class Verdict:
    """One mutant, run: what the oracle decided and on how much.

    `moved` is the size of the movement where the oracle measures one, in whatever
    unit that oracle counts, and zero where it does not: an oracle whose answer is a
    vector set says how much of it moved, and one whose answer is a rule firing has
    nothing to say beyond that it fired.
    """

    mutant: Seeded
    outcome: str
    detail: str
    moved: int = 0


def chosen[T](population: list[T], limit: int, sample: int) -> list[T]:
    """Which of a population to run, and the two ways of narrowing it.

    `--limit` takes a prefix, which is the right shape while iterating on one operator.
    `--sample` takes evenly spaced members, which is the right shape for a
    measurement: a prefix of an operator-ordered population is one operator's mutants
    and says nothing about the rest.

    Generic in the member, because what narrows a population does not read it: an
    authored case narrows the same way a generated mutant does.
    """
    if sample and sample < len(population):
        step = len(population) / sample
        return [population[int(n * step)] for n in range(sample)]
    return population[:limit] if limit else population


def summarize(out: list[str], verdicts: list[Verdict], subject: str,
              oracle_name: str, scope: Scope | None = None) -> int:
    """The one report shape every loop shares, and the exit code it implies.

    Three of the four verdicts decide the code and they decide it for the reasons
    stated above: a survivor is a finding, an unseeded mutant is a finding, and a
    stillborn one is not. The score is over the live population, which is the only
    population the oracle was asked about.

    The unseeded count is printed only where there is one, so a loop that cannot
    produce the verdict reports exactly what it reported before this module carried
    it, and a loop that can makes it conspicuous the moment it does.

    `scope` says how much of the population those verdicts are about, and it is stated
    twice on purpose: once in the header block a reader skims and once on the closing
    line, which is the line a completion note copies. A loop that passes none reports
    what it reported before, so the scope is an addition to this report and never a
    silent change to one.
    """
    killed = [v for v in verdicts if v.outcome == KILLED]
    survived = [v for v in verdicts if v.outcome == SURVIVED]
    still = [v for v in verdicts if v.outcome == STILLBORN]
    unseeded = [v for v in verdicts if v.outcome == UNSEEDED]
    live = len(killed) + len(survived)

    out.append("")
    out.append(f"== {subject} against the {oracle_name} oracle")
    counted = (f"{len(killed)} killed, {len(survived)} survived, "
               f"{len(still)} stillborn")
    out.append(f"   {len(verdicts)} mutant(s) run: {counted}"
               + (f", {len(unseeded)} unseeded" if unseeded else ""))
    if scope is not None:
        out.append(f"   scope: {scope.stated()}")
        if scope.left:
            out.append("   not asked about at all: " + ", ".join(scope.left))
    if killed:
        moved = [v.moved for v in killed if v.moved]
        span = (f", on between {min(moved)} and {max(moved)} lines"
                if moved else "")
        out.append(f"   every kill{span}")
        out.extend(f"     {v.mutant.what}: {v.detail}" for v in killed)
    if still:
        out.append(f"   {len(still)} stillborn, which decide nothing about the oracle:")
        out.extend(f"     {v.mutant.what}: {v.detail}" for v in still)
    out.append("")

    found = False
    if unseeded:
        # first, because it is the sharper of the two findings: a survivor says the
        # oracle is not deciding, and an unseeded mutant says nobody asked it to
        found = True
        out.append(f"FAIL {len(unseeded)} of {len(verdicts)} mutant(s) seeded nothing, "
                   f"so the {oracle_name} oracle was never asked about them:")
        out.extend(f"       {v.mutant.what}: {v.detail}" for v in unseeded)
    if survived:
        found = True
        out.append(f"FAIL {len(survived)} of {live} live mutant(s) survived the "
                   f"{oracle_name} oracle, so it does not reach the site:")
        # with the detail, on every verdict alike: a survivor is repaired differently
        # depending on how it survived, and the checker's oracle draws the sharpest of
        # those lines, between a run that reported nothing and a run that died before
        # it could report
        out.extend(f"       {v.mutant.what}: {v.detail}" for v in survived)
    if not live and not unseeded:
        # the vacuous pass every floor here exists to catch, and the floor an empty
        # population falls through: a run with nothing live measured the compiler, or
        # measured nothing at all
        found = True
        out.append(f"FAIL every one of {len(verdicts)} mutant(s) was stillborn, so the "
                   f"{oracle_name} oracle decided nothing")
    if found:
        return 1
    said = f"ok all {live} live mutant(s) were killed by the {oracle_name} oracle"
    out.append(said if scope is None else f"{said}, {scope.stated()}")
    return 0
