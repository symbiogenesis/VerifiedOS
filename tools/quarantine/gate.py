#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run everything the quarantine holds, as one command and one verdict.

The two instruments here were taken out of the landing loop because their decisions
are deferred, and their two rules came with them. A rule that stops running is a fact
nothing holds, so neither stopped: they run here instead, and this is the command
that runs them.

Five things, in the order a reader wants them:

    rules      K-77 and K-58 over the live tree, the two check groups unchanged
    floors     the enumerations those two read, each required to have members
    registry   check-rules.md against the checks carrying it, in both directions
    mutants    at least one seeded defect per rule, in the shared verdict vocabulary
    tests      the test modules that moved with the instruments

That is the three-edit discipline `tools/README.md` states, kept whole inside the
quarantine rather than spread across the landing loop: a check, its registry row,
and its mutant, with nothing able to go missing quietly.

**The mutants are seeded in memory rather than in a sandbox**, which is the one place
this differs from [run.py selftest](../vos/cli/selftest.py) and it is a difference in
cost and not in what is decided. That tool must copy a tree because it runs the whole
checker as a subprocess; here the subject is two groups whose whole reading is a
document the `Context` already holds and a configuration read from a root the
`Context` already names, so a seeded run is the group's own `run(ctx)` over a context
whose document text or whose root has been moved. Nothing is written into the
checkout.

**The verdicts are [vos/seeded.py](../vos/seeded.py)'s, which is this loop joining the
four that already share them.** K-83 forbids the *landing* loop reaching into the
quarantine and says nothing about the reverse, so this gate reads the shared
vocabulary the way it already reads `vos.report` and `vos.corpus`. What that buys is
the distinction this loop used to lose: a mutation that no longer applies is
**unseeded** and a mutation the rule read and said nothing about is **survived**, and
the two are different defects repaired in different places, the first in the case and
the second in the rule. Merged into one findings list under one label they both failed
the run and neither was named. The population is authored and always whole, so the
report closes on a scope stating that, and this oracle produces no stillborn mutant at
all, its oracle being a group whose `run` always runs.

Exit 0 clean, 1 on any finding. It may be run from anywhere: the repository root is
found from this file, never from the working directory.
"""

import argparse
import importlib
import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# The tools import `vos` without being installed, so each puts `tools/` on the path
# first; a tool inside the quarantine puts the directory *above* its own there, which
# is the one that carries both `vos` and this package. Every import below this line is
# deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quarantine import banks, freeze
from quarantine.checks import GROUPS, Context
from tests.harness import Case
from vos import corpus as corpus_mod
from vos.corpus import Corpus
from vos.register import Artifacts, Register, read_artifacts, read_register
from vos.report import Reporter
from vos.seeded import KILLED, SURVIVED, UNSEEDED, Scope, Verdict, findings_in, summarize

HEADING = "=== quarantine: the deferred instruments, their rules, and their mutants ==="

# This directory, and its own registry inside it.
HERE = Path(__file__).resolve().parent
RULES = "tools/quarantine/check-rules.md"
LANDING_RULES = "tools/check-rules.md"
CHECKS = HERE / "checks"

# What a check *decides* is the rule it reports under, and what it *names* is any id its
# prose cites. The two are different questions and the registry closure below asks both:
# these groups reason about the landing loop's rules by name, K-70 holding the freeze
# delta and K-73 the freshness enumeration among them, so a scan for every id would
# demand a row here for rules this directory does not carry.
REPORTED_RE = re.compile(r'rep\.report\(\s*"(K-\d{2,3})"')
RULE_ID_RE = re.compile(r"\bK-\d{2,3}\b")
REGISTRY_ROW_RE = re.compile(r"(?m)^\| (K-\d{2,3}) \|")
FAILED_RE = re.compile(r"^FAIL (K-\d{2,3}):")

# The enumerations the two groups read and no figure counts, each named by what it is
# rather than by where it is read, exactly as the floors group names its own. They left
# that group with the rules that fill them: a floor under a rule nothing runs is a floor
# under nothing, and one reported here is reported by whoever ran the rule.
#
# Nine of the eleven freeze floors are memberships and two are relation sizes, and the
# second kind is the floor under the *rule* rather than under the document: a relation
# dropped from K-77's comparison narrows it to its memberships with every gate still
# green, which no membership floor can see.
FLOORS: tuple[tuple[str, str], ...] = (
    ("bank counts the DSE contract declares", "bank_candidates"),
    ("freeze corpus members", "freeze corpus members"),
    ("freeze recipe steps", "freeze recipe steps"),
    ("freeze operand classes", "freeze operand classes"),
    ("freeze region classes", "freeze region classes"),
    ("freeze region-class refusal reasons", "freeze region-class refusal reasons"),
    ("freeze decisions", "freeze decisions"),
    ("freeze report blocks", "freeze report blocks"),
    ("freeze declared parameters", "freeze declared parameters"),
    ("freeze CI predicates", "freeze CI predicates"),
    ("freeze corpus feeds edges", "freeze corpus feeds edges"),
    ("freeze threshold bindings in §6", "freeze threshold bindings in §6"),
)

# One seeded defect, applied to a fresh context and a scratch directory of its own,
# answering whether it changed anything. A mutation that changes nothing is a case that
# has stopped testing its rule, which is why the answer is a bool.
type Seed = Callable[[Context, Path], bool]


@dataclass(frozen=True)
class Mutant:
    """One case: the rule the defect must provoke, what it is in words, and the seed.

    `what` is the one thing `vos.seeded.Seeded` asks of a mutant, one line naming the
    defect well enough that a reader can go and look at it. An authored case has no
    site, having been written rather than found, so what identifies it is the rule it
    is aimed at and the defect in words, exactly as the checker's own oracle spells it.
    """

    rule: str
    description: str
    seed: Seed

    @property
    def what(self) -> str:
        return f"{self.rule}: {self.description}"


def _seed_contract(find: str, repl: str) -> Seed:
    """A defect in the freeze contract, seeded where the run reads the document.

    `Context.text` answers out of `fixed` before it answers out of the corpus, which is
    the mechanism a repaired document is read back through, so a seeded text is read by
    the group exactly as a document on disk would be. Nothing is flushed: this gate
    never runs with `fix` set and never writes.
    """
    def apply(ctx: Context, _scratch: Path) -> bool:
        text = ctx.text(freeze.CONTRACT)
        if find not in text:
            return False
        ctx.fixed[freeze.CONTRACT] = text.replace(find, repl, 1)
        return True
    return apply


def _seed_composition(find: str, repl: str) -> Seed:
    """A defect in the composition, seeded by moving the root the grant is read from.

    The bank grant is read off disk out of two files rather than out of the corpus, so
    the seed is a scratch root holding those two and the group pointed at it. The
    checkout is opened for reading and never written, which is what keeps a mutant from
    reaching the tree the way the selftest's sandbox does.
    """
    def apply(ctx: Context, scratch: Path) -> bool:
        config = (ctx.root / banks.CONFIG).read_text(encoding="utf-8")
        if find not in config:
            return False
        contract = (ctx.root / banks.DOCUMENT).read_text(encoding="utf-8")
        for rel, text in ((banks.CONFIG, config.replace(find, repl, 1)),
                          (banks.DOCUMENT, contract)):
            path = scratch / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        ctx.root = scratch
        return True
    return apply


# The cases, each carrying the reason it seeds the side it seeds. These are the four
# that moved out of [run.py selftest](../vos/cli/selftest.py) with the rules they
# belong to.
MUTANTS: tuple[Mutant, ...] = (
    # The bank grant is moved in the composition and left in the contract, which is the
    # direction a real edit takes: the emulator needs a number, so the configuration is
    # where somebody changes one, and the contract is the copy that goes stale.
    Mutant("K-58", "a bank grant the contract and the composition no longer agree on",
           _seed_composition('"banks": 4096', '"banks": 2048')),

    # The contract's own last CI predicate is renumbered and the analyzer is left, which
    # is the direction the defect arrives from and the one that fires both halves of the
    # rule at once: the contract states a predicate no function can make, and the
    # analyzer carries a function no predicate asks for. A renumbering is chosen over an
    # insertion because it moves no count anywhere.
    Mutant("K-77", "a CI predicate the freeze contract states and its analyzer cannot "
                   "make",
           _seed_contract("| `G-12` | a threshold value in the report",
                          "| `G-13` | a threshold value in the report")),

    # One rule gets one case, and this rule gets three, because two of its pairs are
    # relations rather than memberships and neither is reached by the case above: with
    # either relation deleted from the comparison the mutant above is still killed, so a
    # rule narrowed to its enumerations would pass its own selftest.
    Mutant("K-77", "a corpus member the freeze contract sends to fewer decisions than "
                   "its analyzer measures over it",
           _seed_contract("| FD-5, FD-7 |", "| FD-5 |")),

    # The other relation, seeded on the document side for the same reason: §6 states in
    # each decision's own section which materiality floor it spends, and §8's table
    # collects the values, so a set comparison over §8's keys passes a decision spending
    # the 0.5% opcode floor where the contract puts the 0.1% one.
    Mutant("K-77", "a decision spending a materiality floor its own section does not "
                   "name",
           _seed_contract("**Threshold, declared: T-form**, the instruction being "
                          "admitted",
                          "**Threshold, declared: T-enc**, the instruction being "
                          "admitted")),
)


def _context(root: Path, corpus: Corpus, reg: Register, art: Artifacts) -> Context:
    """One run's slate, on `check.py`'s own shape and with its own reporter."""
    return Context(root=root, corpus=corpus, reg=reg, art=art, rep=Reporter())


def _failed(rep: Reporter) -> set[str]:
    """The rule ids a run reported, so a case asserts on what was decided rather than
    on the prose it was decided in."""
    return {m.group(1) for line in rep.out if (m := FAILED_RE.match(line))}


def _rules(ctx: Context, rep: Reporter) -> None:
    """The two groups over the live tree, each printing its own verdict whole."""
    for group in GROUPS:
        group.run(ctx)
    rep.out.extend(ctx.rep.out)
    rep.findings += ctx.rep.findings


def _floors(ctx: Context, rep: Reporter) -> None:
    """Every enumeration those two rules read and never count has members."""
    sizes = [(name, int(ctx.shared.get(key, 0) or 0)) for name, key in FLOORS]
    rep.report("floors", "enumeration(s) these rules read and find empty:",
               [f"the gate finds no {name}; whatever it reads them from has moved"
                for name, size in sizes if not size],
               f"all {len(sizes)} uncounted enumerations the quarantined rules read "
               "have members")


def _sources() -> list[str]:
    """The quarantined checks, as text, in a fixed order."""
    return [source.read_text(encoding="utf-8")
            for source in sorted(CHECKS.glob("*.py"))]


def _registry(ctx: Context, rep: Reporter) -> None:
    """This directory's registry against the checks it carries, in both directions.

    K-00's closure, applied to the quarantine's own registry, and asking one question
    more because there are two registries. What a check *decides* is the rule it reports
    under, and that set and this file's rows are held equal both ways. What a check
    *names* is wider: these groups cite the landing loop's rules by name where their
    reasoning turns on one, so every id named here has to be registered by one of the two
    files rather than by this one, which is what keeps a citation of a retired rule from
    reading as prose that resolves.

    It is a check of this gate rather than a K- rule of its own, because a K- id here
    would be an id the landing loop's registry does not carry, and the closure K-00
    already runs would then report it.
    """
    text = ctx.text(RULES)
    if not text:
        rep.report("registry", "missing artifact:",
                   [f"{RULES} is not in the checker's corpus, so the rules run here are "
                    "registered by nothing"])
        return

    sources = _sources()
    registered = REGISTRY_ROW_RE.findall(text)
    decided = {rule for source in sources for rule in REPORTED_RE.findall(source)}
    named = {rule for source in sources for rule in RULE_ID_RE.findall(source)}
    elsewhere = set(REGISTRY_ROW_RE.findall(ctx.text(LANDING_RULES)))

    seen: set[str] = set()
    findings: list[str] = []
    if not sources:
        findings.append(f"{CHECKS.name}/ carries no check, so this registry is held "
                        "against nothing")
    if not elsewhere:
        findings.append(f"{LANDING_RULES} carries no rule row this gate can read, so a "
                        "rule named here cannot be placed in either registry")
    for rule in registered:
        if rule in seen:
            findings.append(f"{rule} has more than one registry row")
        seen.add(rule)
    findings += [f"{rule} is registered here and no check here reports under it"
                 for rule in registered if rule not in decided]
    findings += [f"{rule} is reported here and has no registry row in {RULES}"
                 for rule in sorted(decided) if rule not in seen]
    findings += [f"{rule} is named here and registered by neither {RULES} nor "
                 f"{LANDING_RULES}"
                 for rule in sorted(named) if rule not in seen and rule not in elsewhere]
    rep.report("registry", "rule id(s) this registry and these checks disagree on:",
               findings,
               f"the quarantine's {len(seen)} rules and its checks agree, both "
               f"directions, and the {len(named - seen)} rule(s) they cite are "
               "registered where those rules run")


def _one_mutant(mutant: Mutant, root: Path, corpus: Corpus, reg: Register,
                art: Artifacts) -> Verdict:
    """One case seeded into a context of its own, and what the two groups made of it.

    Three of the four verdicts are reachable here and the fourth is not: a mutant that
    would not apply is **unseeded**, one whose rule reported is **killed**, one whose
    rule read it and said nothing is **survived**, and there is no **stillborn**,
    because nothing is compiled and the oracle is a `run(ctx)` that always runs.

    A kill names every rule that fired rather than only the one aimed at, which is the
    same reading the checker's own oracle takes: a mutant that trips its neighbours as
    well is expected, and a reader who cannot see which ones cannot tell that from a
    mutant that tripped only a neighbour.
    """
    with tempfile.TemporaryDirectory(prefix="vos-quarantine-") as scratch:
        ctx = _context(root, corpus, reg, art)
        if not mutant.seed(ctx, Path(scratch)):
            return Verdict(mutant, UNSEEDED,
                           "the artifact it seeds has moved, so the rule was never "
                           "asked about it")
        for group in GROUPS:
            group.run(ctx)
        failed = sorted(_failed(ctx.rep))
        if mutant.rule in failed:
            return Verdict(mutant, KILLED, f"the run reported {', '.join(failed)}")
        return Verdict(mutant, SURVIVED,
                       f"the rule read the defect and reported nothing; "
                       f"{', '.join(failed)} fired instead" if failed
                       else "the rule read the defect and the run was green")


def _mutants(root: Path, corpus: Corpus, reg: Register, art: Artifacts,
             rep: Reporter, clean: bool) -> None:
    """At least one seeded defect per rule, through the shared verdict vocabulary.

    At least one is the honest shape and the landing loop's registry states why: one
    defect does not always reach every direction a rule holds, so K-77 carries three
    cases where K-58 carries one, for the reason the table itself gives at them.

    Nothing below decides anything against a tree that was already failing, on the
    checker's own oracle's ground: a mutant would be reported killed by whatever was
    broken before it was introduced. That refusal is not a verdict about any mutant and
    so stays a `Reporter` finding of its own rather than being dressed as one.

    The finding count comes from `vos.seeded.findings_in` rather than from the lines
    printed, because this reporter carries four other sections and the exit code is
    over all five: `summarize`'s own exit code answers about the mutants alone.
    """
    if not clean:
        rep.report("mutants", "case(s) that could not be decided:",
                   [f"{len(MUTANTS)} case(s) were not run: the unmutated tree does not "
                    "pass, so no seeded defect decides anything"])
        return

    verdicts = [_one_mutant(mutant, root, corpus, reg, art) for mutant in MUTANTS]
    block: list[str] = []
    summarize(block, verdicts, RULES, "quarantined rule",
              Scope(whole=len(MUTANTS), ran=len(verdicts)))
    rep.out.extend(block)
    rep.findings += findings_in(verdicts)


def _test_modules() -> list[str]:
    """Every test module beside this file, sorted so the report order is fixed."""
    return sorted(path.stem for path in (HERE / "tests").glob("test_*.py"))


def _tests(rep: Reporter, slow: bool) -> None:
    """Every test module in this directory, on `run.py test`'s own conventions.

    Discovering no module at all is a failure rather than a green run, for the reason
    that suite states about itself: an empty suite decides nothing, and what is here is
    most of what holds the instruments' arithmetic, their wiring, each of the twelve CI
    predicates against a defect it must reject, and this gate's own reading of the
    seeded verdicts.
    """
    lane = "host" if sys.platform == "win32" else "guest"
    names = _test_modules()
    if not names:
        rep.report("tests", "empty suite:",
                   [f"nothing under {HERE.name}/tests/ matches test_*.py"])
        return

    for name in names:
        try:
            found = importlib.import_module(f"quarantine.tests.{name}").cases()
        except Exception as err:  # an unimportable module is a finding, not a crash
            rep.report(name, "module error(s):", [f"failed to load: {err!r}"])
            continue
        failures: list[str] = []
        ran = 0
        for case in found:
            if not isinstance(case, Case):
                failures.append(f"cases() returned a member that is not a Case: {case!r}")
                continue
            if (case.slow and not slow) or case.lane not in ("any", lane):
                continue
            ran += 1
            try:
                case.fn()
            except Exception as err:  # a case decides by raising; that is its verdict
                failures.append(f"{case.name}: {err}")
        rep.report(name, "failure(s):", failures, ok=f"{ran} case(s)")


def run(root: Path, slow: bool = False) -> Reporter:
    """One whole run, as data, on the convention `check.py` set: the caller decides what
    to do with the verdict rather than parsing what was printed."""
    rep = Reporter()
    rep.line(HEADING)

    corpus = corpus_mod.load(root)
    reg, art = read_register(corpus), read_artifacts(corpus)
    ctx = _context(root, corpus, reg, art)

    _rules(ctx, rep)
    _floors(ctx, rep)
    _registry(ctx, rep)
    _mutants(root, corpus, reg, art, rep, clean=ctx.rep.findings == 0)
    _tests(rep, slow)

    if rep.findings:
        rep.line(f"{rep.findings} finding(s).")
    else:
        rep.line("the quarantined instruments agree with the contracts they answer, "
                 "and their rules still bite.")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the quarantined instruments, their rules, and their mutants.")
    parser.add_argument("--slow", action="store_true",
                        help="include the test cases marked slow")
    args = parser.parse_args(argv)

    report = run(corpus_mod.find_root(), slow=args.slow)
    print("\n".join(report.out))
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
