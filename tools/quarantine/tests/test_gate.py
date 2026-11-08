# SPDX-License-Identifier: Apache-2.0
"""Unit tests for [gate.py](../gate.py) mutant verdicts and rule registration.

Verifies that:
- `Mutant.what` formats the target rule and defect description,
- `seeded.summarize` distinguishes **survived** mutants from **unseeded** mutants,
- a full mutant run reports the population size, and
- every case in `MUTANTS` targets a rule registered in `tools/quarantine/check-rules.md`.
"""

from pathlib import Path

from quarantine.checks import Context
from quarantine.gate import HERE, MUTANTS, REGISTRY_ROW_RE, RULES, Mutant
from tests.harness import Case, ensure
from vos import seeded


def _no_seeding(_ctx: Context, _scratch: Path) -> bool:
    """No-op seed function for synthetic `Verdict` test cases."""
    return True


def _case(rule: str = "K-77", what: str = "a defect the contract states") -> Mutant:
    return Mutant(rule, what, _no_seeding)


def _a_case_names_itself_by_rule_and_defect() -> None:
    """Verify `Mutant.what` formatting."""
    named = _case().what
    ensure(named == "K-77: a defect the contract states", f"a case names itself {named!r}")


def _the_two_failures_are_named_apart() -> None:
    """Verify that survived and unseeded verdicts are reported separately."""
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
