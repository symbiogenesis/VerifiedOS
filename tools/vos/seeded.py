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

## The report, and the second copy that survives the process

`summarize` is printed once, at the end, which is right for a run that ends. A
whole-population run over the prover is hours of prover, and the way it stops is a
teardown of the guest distribution underneath it: the run dies at member 460 and says
nothing about the 459 it had already decided, so the prover time is spent and the
answers go with the VM. `Journal` is that second copy, one line per verdict, flushed
as it is written. Nothing about the report moves: it stays accumulated, printed whole,
and in population order, and the journal is a record of what was decided and when.
"""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
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

    def decided(self, ran: int) -> Scope:
        """The same scope over what a run actually reached.

        `ran` is filled where the population is picked, which is before any verdict
        exists, and for two of the three oracles here that is also what gets decided.
        The third can stop early: the `$[test]` loop writes into the checkout and stops
        the moment it cannot verify its own restore, and a scope taken from the picking
        would then close on a line stating a run larger than the verdicts under it,
        which is the same misquotation `stated` exists to refuse one level up.
        """
        return Scope(whole=self.whole, ran=ran, left=self.left)

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


class Journal:
    """A run's verdicts written down as they are decided, for the run that does not end.

    **What it is for is the run that is killed rather than the run that fails.** A
    failing run reports: `summarize` prints its findings and the loop exits 1. A run
    whose distribution is torn down under it prints nothing at all, and a population
    that costs a prover run per member is exactly the run that outlives its lane. The
    report is unmoved by this and stays the artifact a completion note quotes; what is
    added is a file that is complete up to the moment the process stopped.

    **The head carries the scope and the tail carries the close.** How large the
    population is and how much of it this run picked are both known before the first
    mutant, so a reader of a file with no closing line still knows what fraction of what
    those verdicts are, which is the discipline `Scope` states for the report. The
    closing line's *absence* is the record: a journal that ends without one is a run
    that never reached its report.

    **One file, opened per verdict, under a lock.** Opening and closing around each
    line is the flush: nothing sits in a buffer waiting for an exit that may not come,
    and the cost is one `open` against a mutant that costs a compiler or a prover. The
    lock is because the Gallina lane shards its population across several trees at
    once, so the lines land in completion order where the report is in population
    order; that is the difference between the two artifacts rather than a defect in
    this one.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self._n = 0

    def start(self, subject: str, oracle_name: str, scope: Scope) -> str:
        """Open the file on this run's head, and say where it is.

        The line handed back is for the run's own first line: a journal nobody is told
        about is a journal nobody reads after the run that would have named it died.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write("w", [f"== {subject} against the {oracle_name} oracle",
                          f"   scope: {scope.stated()}",
                          "   one line per verdict, as it is decided; the closing line "
                          "is written only by a run that finished"])
        return (f"== every verdict is written to {self.path} as it is decided, so a "
                "run that does not finish still says what it decided")

    def record(self, verdict: Verdict) -> Verdict:
        """Write one verdict down and hand it back, so a loop journals and keeps in one
        expression rather than in two statements that can drift apart."""
        with self._lock:
            self._n += 1
            self._write("a", [f"{self._n:>5}  {verdict.outcome:<9} "
                              f"{verdict.mutant.what}: {verdict.detail}"])
        return verdict

    def close(self, code: int) -> None:
        """The closing line, which is what a truncated journal is missing."""
        self._write("a", [f"== complete: {self._n} verdict(s) decided, exit {code}"])

    def _write(self, mode: str, lines: list[str]) -> None:
        with self.path.open(mode, encoding="utf-8", newline="\n") as handle:
            handle.write("".join(f"{line}\n" for line in lines))


def findings_in(verdicts: list[Verdict]) -> int:
    """How many of a run's verdicts are findings, which is what its verdict stands on.

    Written here rather than at each caller because two callers now read it: the loops
    exit on it through `summarize`, and the quarantine's gate counts findings into a
    `Reporter` that also carries its rules, its floors, its registry and its tests. Two
    readings of one arithmetic is the drift this module exists to remove, so `summarize`
    takes its own exit code from here as well.

    A survivor is a finding and an unseeded mutant is a finding; a stillborn one is not,
    for the reasons stated at the top of this module. A population with nothing live in
    it at all is one finding about the *run* rather than one about any member, and it is
    the floor an empty population falls through.
    """
    counted = sum(1 for v in verdicts if v.outcome in (SURVIVED, UNSEEDED))
    live = any(v.outcome in (KILLED, SURVIVED) for v in verdicts)
    unseeded = any(v.outcome == UNSEEDED for v in verdicts)
    return counted + (0 if live or unseeded else 1)


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


def shard[T](population: list[T], parts: int) -> list[list[T]]:
    """A population split `parts` ways, for that many workers to run at once.

    **Exhaustive by construction, whatever the counts are.** Every member lands in
    exactly one part because the strides `i`, `i + n`, `i + 2n` partition the indices,
    so there is no arithmetic here that could leave a member out and no list anybody
    has to keep in step with the population. That is the property a hand-assembled
    partition lacks: an operator list written out by hand is where a whole kind of
    defect goes unrun and nothing says so.

    Striding rather than slicing into contiguous blocks, because a generated population
    is in operator order and the operators do not cost the same. A contiguous split
    hands one worker every member of the slowest operator; a stride interleaves them,
    and the parts finish together without anyone having measured a member.
    """
    return [population[i::parts] for i in range(parts)]


def unshard[T](parts: list[list[T]]) -> list[T]:
    """`shard` undone: the members back in population order.

    Read round-robin by position, which is exactly the inverse of the stride. What it
    is for is that a run's report should not depend on which worker finished first,
    the population order being the order a reader compares two runs in.
    """
    return [part[k] for k in range(max((len(p) for p in parts), default=0))
            for part in parts if k < len(part)]


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

    The code itself is `findings_in`'s, so that a caller counting findings for a
    reporter of its own and this function's exit code cannot disagree about which
    verdicts are findings.
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

    found = bool(findings_in(verdicts))
    if unseeded:
        # first, because it is the sharper of the two findings: a survivor says the
        # oracle is not deciding, and an unseeded mutant says nobody asked it to
        out.append(f"FAIL {len(unseeded)} of {len(verdicts)} mutant(s) seeded nothing, "
                   f"so the {oracle_name} oracle was never asked about them:")
        out.extend(f"       {v.mutant.what}: {v.detail}" for v in unseeded)
    if survived:
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
        out.append(f"FAIL every one of {len(verdicts)} mutant(s) was stillborn, so the "
                   f"{oracle_name} oracle decided nothing")
    if found:
        return 1
    said = f"ok all {live} live mutant(s) were killed by the {oracle_name} oracle"
    out.append(said if scope is None else f"{said}, {scope.stated()}")
    return 0
