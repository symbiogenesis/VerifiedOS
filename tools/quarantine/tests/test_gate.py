# SPDX-License-Identifier: Apache-2.0
"""What this gate's fourth section decides, and the distinction it used to lose.

The gate runs the two quarantined rules against at least one seeded defect each, and a
case can fail in two ways that are repaired in two different places. A **survivor** is
a defect the rule read and said nothing about: the repair is in the rule, which is not
deciding. An **unseeded** case is one whose mutation no longer applies to an artifact
that moved under it: the repair is in the case, and until it is made the rule reports
live for as long as nobody looks. Merged into one findings list under one label, both failed the
run and neither was named, which is the state this module holds against.

Nothing here runs the gate. Its own run over the live tree is what `python
tools/quarantine/gate.py` is, and a case that re-entered it would be the tool testing
itself by running itself; what is held here is the reading between a seeded case and a
verdict, which is a pure function of the two.
"""

from pathlib import Path

from quarantine.checks import Context
from quarantine.gate import HERE, MUTANTS, REGISTRY_ROW_RE, RULES, Mutant
from tests.harness import Case, ensure
from vos import seeded


def _no_seeding(_ctx: Context, _scratch: Path) -> bool:
    """A seed that is never called: every case here is about the report a verdict makes
    rather than about applying one, and the table's own four are the live seedings."""
    return True


def _case(rule: str = "K-77", what: str = "a defect the contract states") -> Mutant:
    return Mutant(rule, what, _no_seeding)


def _a_case_names_itself_by_rule_and_defect() -> None:
    """`vos.seeded.Seeded` asks one thing of a mutant, a line naming the defect well
    enough that a reader can go and look at it. An authored case has no site, so what
    identifies it is the rule it is aimed at and the defect in words.

    Held against a literal here rather than over `MUTANTS`, because `what` is computed
    from the two fields: a pass over the live table would satisfy any table at all and
    so would decide nothing about either. What the live table owes is that its rules are
    the quarantine's, which is the case at the end of this module.
    """
    named = _case().what
    ensure(named == "K-77: a defect the contract states", f"a case names itself {named!r}")


def _the_two_failures_are_named_apart() -> None:
    """The whole of what the absorption buys. Both fail the run, as they did before;
    what is new is that the report says which is which and how many of each."""
    out: list[str] = []
    verdicts = [
        seeded.Verdict(_case("K-58"), seeded.KILLED, "the run reported K-58"),
        seeded.Verdict(_case("K-77", "a predicate its analyzer cannot make"),
                       seeded.SURVIVED, "the rule read the defect and the run was green"),
        seeded.Verdict(_case("K-77", "a corpus member sent to fewer decisions"),
                       seeded.UNSEEDED, "the artifact it seeds has moved"),
    ]
    code = seeded.summarize(out, verdicts, RULES, "quarantined rule")
    ensure(code == 1, f"a survivor beside an unseeded case passed: {out}")
    ensure(seeded.findings_in(verdicts) == 2,
           f"the gate would count {seeded.findings_in(verdicts)} finding(s) where the "
           f"report names two")

    survived = [line for line in out if "survived the" in line]
    unseeded = [line for line in out if "seeded nothing" in line]
    ensure(len(survived) == 1 and len(unseeded) == 1,
           f"the two verdicts share a label: {out}")
    ensure("1 of 2 live" in survived[0],
           f"the survivor is not scored over the live population: {survived[0]!r}")
    ensure("1 of 3" in unseeded[0],
           f"the unseeded case is not counted over the whole population: {unseeded[0]!r}")
    ensure(any("a predicate its analyzer cannot make" in line for line in out)
           and any("a corpus member sent to fewer decisions" in line for line in out),
           f"neither failure names the case it is about: {out}")


def _a_run_that_kills_them_all_says_over_how_many() -> None:
    """This population is authored and always whole, so the closing line states that
    rather than leaving a whole run and a sample reading the same."""
    out: list[str] = []
    verdicts = [seeded.Verdict(m, seeded.KILLED, f"the run reported {m.rule}")
                for m in MUTANTS]
    code = seeded.summarize(out, verdicts, RULES, "quarantined rule",
                            seeded.Scope(whole=len(MUTANTS), ran=len(verdicts)))
    ensure(code == 0, f"a population that was all killed failed: {out}")
    ensure("whole population" in out[-1], f"the closing line reads {out[-1]!r}")
    ensure(f"of {len(MUTANTS)} mutant(s)" in out[-1],
           f"the closing line does not carry the population size: {out[-1]!r}")


def _every_case_is_aimed_at_a_rule_this_registry_carries() -> None:
    """A case aimed at a rule the quarantine does not carry decides nothing about
    anything here, and the gate's registry section holds the rules against the checks
    rather than against the cases, so nothing else would report one."""
    registered = set(REGISTRY_ROW_RE.findall(
        (HERE / "check-rules.md").read_text(encoding="utf-8")))
    ensure(bool(registered),
           f"{RULES} carries no rule row, so this case decides nothing")
    stray = sorted({m.rule for m in MUTANTS} - registered)
    ensure(not stray, f"case(s) aimed outside the quarantine's rules: {stray}")


def cases() -> list[Case]:
    return [
        Case("a case names itself by rule and defect",
             _a_case_names_itself_by_rule_and_defect),
        Case("the two failures are named apart", _the_two_failures_are_named_apart),
        Case("a whole run says over how many",
             _a_run_that_kills_them_all_says_over_how_many),
        Case("every case is aimed at a rule this registry carries",
             _every_case_is_aimed_at_a_rule_this_registry_carries),
    ]
