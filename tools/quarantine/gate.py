#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the quarantined instruments, their rules, and their mutants.

Validates five sections in order:

    rules      K-58 and K-77 over the live tree
    floors     every enumeration and relation those rules read must be non-empty
    registry   check-rules.md against the checks in this directory, in both directions
    mutants    seeded defects per rule, using the shared verdict vocabulary
    tests      every test module under tests/

Mutants are seeded in memory (or in a temporary directory for configuration files) and
evaluated directly via each check group's `run(ctx)` rather than spawning a subprocess.
Verdicts use [vos/seeded.py](../vos/seeded.py), distinguishing **unseeded** cases
(whose target text moved) from **survived** cases (which the rule read without
reporting).

Exit 0 clean, 1 on any finding. The repository root is resolved from this file's path
rather than the working directory.
"""

import argparse
import importlib
import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Put `tools/` on `sys.path` so both `vos` and `quarantine` can be imported directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quarantine import banks, freeze
from quarantine.checks import GROUPS, Context
from tests.harness import Case
from vos import checkregistry
from vos import corpus as corpus_mod
from vos.corpus import Corpus
from vos.register import Artifacts, Register, read_artifacts, read_register
from vos.report import Reporter
from vos.seeded import KILLED, SURVIVED, UNSEEDED, Scope, Verdict, findings_in, summarize

HEADING = "=== quarantine: the deferred instruments, their rules, and their mutants ==="

HERE = Path(__file__).resolve().parent
RULES = "tools/quarantine/check-rules.md"
LANDING_RULES = "tools/check-rules.md"
CHECKS = HERE / "checks"

# Distinguish rules a check reports under (`REPORTED_RE`) from any rule ID cited in
# source comments (`RULE_ID_RE`), which may refer to rules in `tools/check-rules.md`.
REPORTED_RE = re.compile(rf'rep\.report\(\s*"({checkregistry.ID_PATTERN})"')
RULE_ID_RE = re.compile(rf"(?<![\w-]){checkregistry.ID_PATTERN}(?![\w-])")
REGISTRY_ROW_RE = re.compile(rf"(?m)^\| ({checkregistry.ID_PATTERN}) \|")
FAILED_RE = re.compile(rf"^FAIL ({checkregistry.ID_PATTERN}):")

# Uncounted enumerations and relation sizes read by K-58 and K-77.
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

type Seed = Callable[[Context, Path], bool]


@dataclass(frozen=True)
class Mutant:
    """A seeded defect case targeting `rule`."""

    rule: str
    description: str
    seed: Seed

    @property
    def what(self) -> str:
        return f"{self.rule}: {self.description}"


def _seed_contract(find: str, repl: str) -> Seed:
    """Seed a defect into `freeze.CONTRACT` via `ctx.fixed` in memory."""
    def apply(ctx: Context, _scratch: Path) -> bool:
        text = ctx.text(freeze.CONTRACT)
        if find not in text:
            return False
        ctx.fixed[freeze.CONTRACT] = text.replace(find, repl, 1)
        return True
    return apply


def _seed_composition(find: str, repl: str) -> Seed:
    """Seed a defect into `banks.CONFIG` inside a temporary root directory."""
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


MUTANTS: tuple[Mutant, ...] = (
    # Mutate the bank grant in the configuration while leaving the contract unchanged.
    Mutant("K-58", "a bank grant the contract and the composition no longer agree on",
           _seed_composition('"banks": 4096', '"banks": 2048')),

    # Renumber the last CI predicate in the contract so both directions of K-77's
    # membership check fire.
    Mutant("K-77", "a CI predicate the freeze contract states and its analyzer cannot "
                   "make",
           _seed_contract("| `G-13` | a variant that moves a knob",
                          "| `G-14` | a variant that moves a knob")),

    # Mutate §2's `Feeds` relation without changing the member or decision sets.
    Mutant("K-77", "a corpus member the freeze contract sends to fewer decisions than "
                   "its analyzer measures over it",
           _seed_contract("| FD-5, FD-7 |", "| FD-5 |")),

    # Mutate §6's per-decision threshold binding without changing §8's parameter keys.
    Mutant("K-77", "a decision spending a materiality floor its own section does not "
                   "name",
           _seed_contract("**Threshold, declared: T-form**, the instruction being "
                          "admitted",
                          "**Threshold, declared: T-enc**, the instruction being "
                          "admitted")),
)


def _context(root: Path, corpus: Corpus, reg: Register, art: Artifacts) -> Context:
    """Create a fresh [`Context`](../vos/checks/__init__.py#Context) with its own reporter."""
    return Context(root=root, corpus=corpus, reg=reg, art=art, rep=Reporter())


def _failed(rep: Reporter) -> set[str]:
    """Return the set of `K-nn` rule IDs that failed in `rep`."""
    return {m.group(1) for line in rep.out if (m := FAILED_RE.match(line))}


def _rules(ctx: Context, rep: Reporter) -> None:
    """Run all quarantined check groups over the live tree."""
    for group in GROUPS:
        group.run(ctx)
    rep.out.extend(ctx.rep.out)
    rep.findings += ctx.rep.findings


def _floors(ctx: Context, rep: Reporter) -> None:
    """Verify that every enumeration and relation in `FLOORS` is non-empty."""
    sizes = [(name, int(ctx.shared.get(key, 0) or 0)) for name, key in FLOORS]
    rep.report("floors", "enumeration(s) these rules read and find empty:",
               [f"the gate finds no {name}; whatever it reads them from has moved"
                for name, size in sizes if not size],
               f"all {len(sizes)} uncounted enumerations the quarantined rules read "
               "have members")


def _sources() -> list[str]:
    """Read all quarantined check modules in sorted order."""
    return [source.read_text(encoding="utf-8")
            for source in sorted(CHECKS.glob("*.py"))]


def _registry(ctx: Context, rep: Reporter) -> None:
    """Check `tools/quarantine/check-rules.md` against `checks/*.py` in both directions.

    Every rule reported via `rep.report` here must have a unique row in `RULES`, and
    every `K-nn` cited anywhere in `checks/*.py` must be registered in either `RULES`
    or `LANDING_RULES`.
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
    """Seed `mutant` into a fresh context and evaluate it against `GROUPS`."""
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
    """Run all `MUTANTS` when the unmutated baseline is clean."""
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
    """Return sorted stems of `test_*.py` modules under `tests/`."""
    return sorted(path.stem for path in (HERE / "tests").glob("test_*.py"))


def _tests(rep: Reporter, slow: bool) -> None:
    """Run every test module under `tests/`, failing if none are found."""
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
    """Run all five quarantine sections and return the [`Reporter`](../vos/report.py#Reporter)."""
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
