#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The seeded-defect generator: one engine, several oracles, three verdicts.

[run.py selftest](selftest.py) proved mutation testing here, on the checker's own
rules, with at least one hand-authored mutant per rule. That shape is right for a registry
and wrong for everything else in this tree: a Sail function and a Gallina definition
have hundreds of mutable sites each and nobody is going to author hundreds of cases.
So [vos/mutate.py](../mutate.py) generates the population and this tool points it at
an **oracle**, which is whatever decides that a defect has been noticed:

    run.py seed sail --spec capformat   the generated vectors, which must move
    run.py seed coq                     the prover, and then the Gallina vectors
    run.py seed properties --file ...   the model's own `$[test]` harness

Three verdicts and never two. **Stillborn** is a mutant that did not compile, and
nothing was decided about the oracle because the oracle never ran. **Killed** is a
mutant that compiled and moved the oracle's answer. **Survived** is a mutant that
compiled and did not, and a survivor is the finding: the oracle does not reach that
site. Counting stillborn mutants as kills is the standard way a mutation score is
inflated, so a run here reports the three apart and scores over the live population.
What a verdict is, and the report and the exit code they imply, is
[vos/seeded.py](../seeded.py)'s and is shared with every other loop that seeds a
defect; what is here is the population and the three oracles.

The Coq lane runs **two** oracles in sequence and the second is the one worth the
item. A mutation the prover refuses is killed by the artifact's own statements, which
is a good answer and the one a reader expects. A mutation the prover accepts is a
weakening the theorems do not constrain, and it is handed straight to the generated
Gallina vectors; what those kill is exactly the dividend, and what survives both is
where neither the proofs nor the generated inputs decide anything.

**Which finding this answers.** M0.8d's: the property that named the *pi* defect was
written before the vectors and never ran, the harness running alphabetically so the
symptom aborted the executable ahead of the cause. A written property inherits every
blind spot in the choice of what to write; a generated mutant is not chosen at all.

**The checker's own rules are a fourth oracle over the same vocabulary, and its
population stays authored.** [run.py selftest](selftest.py) keeps one hand-written
mutant per registered rule, which is right rather than a shortfall: its subject is a
registry, where a rule and its mutant are two halves of one claim, and there is no
source to walk. What it shares is [vos/seeded.py](../seeded.py) and nothing else.
What stays its own is the `CASES` table, which sits where the rules are added and
where the one rule that reads a quoted path exempts it; the `Sandbox` class and its
hardlink template over the git index, which is that oracle's own staging and no other
oracle's; the repair path, which decides about `--fix` rather than about mutation;
and the registry-coverage check, which decides about the rule registry rather than
about any run. Its third verdict is `unseeded` rather than `stillborn`, and
`vos/seeded.py` states why the two are counted apart.
"""

import argparse
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from vos import cli, env, gallina, mutate, sailrig
from vos import oracle as oracle_spec
from vos.corpus import find_root
from vos.seeded import KILLED, STILLBORN, SURVIVED, Verdict, chosen, summarize

# This lane's working directories under the lane root, one per oracle, because two of
# them are running compilers over trees that must not be the same tree.
WORK = "seed"

# The Gallina lane's default subject: the file whose definitions the theorems above
# them are about. Named rather than globbed, because mutating a Record's field list is
# a stillborn mutant with near certainty and mutating `ApexTheorem.v`'s vocabulary is
# a mutation of a `Prop` no vector computes.
COQ_SUBJECT = "proofs/CyclicExecutive.v"


def read_source(path: Path) -> str:
    """A source's text with its own line endings intact.

    `read_text` translates newlines, so a round trip through it rewrites every line of
    a CRLF file. `model/` is `-text` in .gitattributes and a swept file there hides the
    real diff of whatever touched it, which is a rule this repository states and a
    mutation loop writing into the checkout would break silently.
    """
    return path.read_bytes().decode("utf-8")


def write_source(path: Path, text: str) -> None:
    """And back, byte for byte."""
    path.write_bytes(text.encode("utf-8"))


def population(root: Path, rel: str, named: tuple[str, ...] = (),
               only: tuple[str, ...] = ()) -> list[mutate.Mutant]:
    """Every mutant of one tracked source, in the engine's own order.

    `only` narrows to named operators, which is what makes two oracles comparable: a
    sample is evenly spaced over an operator-ordered population, so two runs at
    different sample sizes are two different populations and the pair says nothing.
    Naming the operator gives both oracles the same mutants.
    """
    lane = mutate.lane_of(rel)
    found = mutate.mutants(read_source(root / rel), lane, rel, named=named)
    return [m for m in found if m.operator in only] if only else found


# =====================================================================================
# list: the population, without running anything
# =====================================================================================


def cmd_list(args: argparse.Namespace) -> int:
    """The mutants one source yields, counted per operator. Runs on the host, being a
    text walk: what it is for is sizing a run before spending a toolchain on it."""
    root = find_root()
    rel = args.file
    if not (root / rel).is_file():
        print(f"FAIL {rel} is not in this checkout")
        return 1
    found = population(root, rel, tuple(args.region), tuple(args.operator))
    if not found:
        print(f"FAIL {rel} yields no mutant, so no oracle can be measured against it")
        return 1
    per: dict[str, int] = {}
    for mutant in found:
        per[mutant.operator] = per.get(mutant.operator, 0) + 1
    out = [f"== {rel}: {len(found)} mutant(s) over {len(per)} operator(s)"]
    out.extend(f"   {name:<20} {count}" for name, count in sorted(per.items()))
    out.extend(f"     {mutant.ident:<18} {mutant.what}"
               for mutant in chosen(found, args.limit, args.sample))
    out.append(f"ok {rel} yields {len(found)} mutant(s)")
    print("\n".join(out))
    return 0


# =====================================================================================
# sail: the generated vectors as the oracle
# =====================================================================================


def stage_sail(root: Path, spec: oracle_spec.Spec, tree: Path) -> None:
    """A copy of exactly the model files one spec compiles.

    Exactly those and no more, which is what makes the Sail lane cheap: the spec names
    five files where the model has a hundred and twenty-five, and the mutation loop
    recompiles the set once per mutant.
    """
    if tree.exists():
        shutil.rmtree(tree)
    for source in spec.sources:
        target = tree / source
        target.parent.mkdir(parents=True, exist_ok=True)
        write_source(target, read_source(root / source))


def cmd_sail(args: argparse.Namespace) -> int:
    """Seed a defect into a model source and require the generated vectors to move."""
    e = env.load()
    root = find_root()
    try:
        spec = oracle_spec.load(root, args.spec)
    except oracle_spec.SpecError as err:
        print(f"FAIL {err}")
        return 1

    # The last source by convention: a spec lists its files in dependency order, so the
    # last is the one carrying the algebra the earlier ones are the prelude to.
    rel = args.file or spec.sources[-1]
    if rel not in spec.sources:
        print(f"FAIL {rel} is not one of the sources spec `{spec.name}` compiles, so a "
              "mutation of it could not reach these vectors")
        return 1

    work = e.lane_root / WORK / f"sail-{spec.name}"
    tree = work / "tree"
    stage_sail(root, spec, tree)
    original = read_source(root / rel)

    out: list[str] = []
    baseline = oracle_spec.generate(root, spec, work / "base", out, model_root=tree)
    if baseline is None:
        out.append("FAIL the unmutated spec did not run, so there is no baseline")
        print("\n".join(out))
        return 1
    _, total, _ = sailrig.census(baseline)
    out.append(f"== baseline: {total} vector(s) from {spec.name}")

    verdicts: list[Verdict] = []
    picked = chosen(population(root, rel, tuple(args.region), tuple(args.operator)),
                    args.limit, args.sample)
    for mutant in picked:
        write_source(tree / rel, mutant.apply(original))
        try:
            said: list[str] = []
            got = oracle_spec.generate(root, spec, work / "mutant", said,
                                       model_root=tree)
            if got is None:
                verdicts.append(Verdict(mutant, STILLBORN, "the mutated model did not "
                                                           "compile"))
                continue
            _, bad, n_want, n_got = sailrig.compare(baseline, got)
            if bad or n_want != n_got:
                verdicts.append(Verdict(mutant, KILLED,
                                        f"{bad} of {total} vector(s) moved", bad))
            else:
                verdicts.append(Verdict(mutant, SURVIVED, "every vector reproduced"))
        finally:
            write_source(tree / rel, original)

    code = summarize(out, verdicts, rel, f"{spec.name} vector")
    print("\n".join(out))
    return code


# =====================================================================================
# coq: the prover first, and then the Gallina vectors
# =====================================================================================


def cmd_coq(args: argparse.Namespace) -> int:
    """Seed a weakening into a Gallina definition and ask two oracles about it.

    The prover answers first, because a mutation the shipped statements refuse is
    killed by the artifact itself and there is nothing further to measure about it. The
    generated inputs answer for the rest, and what they kill is what the theorems leave
    open: a definition the proofs do not constrain and generation does.

    Which generator supplies those inputs is `--quickchick`'s to choose, and the two
    are worth having apart. The enumerative harness walks a declared grid, so what it
    reaches is a list somebody wrote and its verdict is a whole vector file that moved.
    QuickChick draws instead and shrinks what refutes, so what it reaches is a range
    and its verdict is a minimal counterexample. A mutant both miss is a site neither
    the proofs nor either kind of generation decides anything about.
    """
    e = env.load()
    root = find_root()
    rel = args.file
    if not (root / rel).is_file():
        print(f"FAIL {rel} is not in this checkout")
        return 1

    switch = gallina.QUICKCHICK_SWITCH if args.quickchick else gallina.ORACLE_SWITCH
    found = gallina.prover(switch)
    if found is None:
        print(f"FAIL no prover in the {switch} switch; "
              "`run.py quickchick check` says which switch holds what")
        return 1

    work = e.lane_root / WORK / ("quickchick" if args.quickchick else "coq")
    out: list[str] = []
    harness_name = gallina.RANDOMIZED if args.quickchick else gallina.ENUMERATIVE
    staged = work / rel
    original = read_source(root / rel)
    harness = work / "harness" / harness_name

    if args.quickchick:
        gallina.stage(root, work)
        if gallina.compile_proofs(found, work) + gallina.compile_support(found, work):
            print("FAIL the unmutated tree did not compile, so there is no baseline")
            return 1
        passed, failed, _ = gallina.properties(found, work, harness)
        if failed or not passed:
            print(f"FAIL the unmutated tree's {harness_name} is not green: {failed} "
                  f"property set(s) failed and {passed} passed")
            return 1
        baseline: list[str] = []
        out.append(f"== baseline: {passed} property set(s) green under QuickChick, "
                   f"{gallina.version(found)} in {switch}")
    else:
        got = gallina.emit(root, work, out)
        if got is None:
            out.append("FAIL the unmutated tree did not run, so there is no baseline")
            print("\n".join(out))
            return 1
        baseline = got
        out.append(f"== baseline: {len(baseline)} vector(s) from the Gallina front, "
                   f"{gallina.version(found)} in {switch}")

    verdicts: list[Verdict] = []
    picked = chosen(population(root, rel, tuple(args.region), tuple(args.operator)),
                    args.limit, args.sample)
    for mutant in picked:
        write_source(staged, mutant.apply(original))
        try:
            failures = gallina.compile_dependents(found, work, rel)
            if failures:
                verdicts.append(Verdict(
                    mutant, KILLED,
                    "the prover refused " + ", ".join(f.source for f in failures),
                    len(failures)))
                continue
            # The harness's own shared sources come after the proofs and their failure
            # is a different verdict: a mutation the shipped statements accept and the
            # harness cannot be built over is a mutant no oracle ran against.
            if gallina.compile_support(found, work):
                verdicts.append(Verdict(mutant, STILLBORN,
                                        "the harness would not build over the mutant"))
                continue
            if args.quickchick:
                passed, failed, why = gallina.properties(found, work, harness)
                if failed:
                    verdicts.append(Verdict(
                        mutant, KILLED,
                        f"the proofs accepted it and QuickChick refuted {failed} of "
                        f"{failed + passed} property set(s): {why}", failed))
                elif not passed:
                    verdicts.append(Verdict(mutant, STILLBORN,
                                            "the harness did not run over the mutant"))
                else:
                    verdicts.append(Verdict(
                        mutant, SURVIVED,
                        f"the proofs accepted it and {passed} property set(s) held"))
                continue
            lines, said = gallina.vectors(found, work, harness)
            if said:
                verdicts.append(Verdict(mutant, STILLBORN,
                                        "the harness did not run over the mutant"))
                continue
            moved = _moved(baseline, lines)
            if moved:
                verdicts.append(Verdict(
                    mutant, KILLED,
                    f"the proofs accepted it and {moved} of {len(baseline)} vector(s) "
                    "moved", moved))
            else:
                verdicts.append(Verdict(mutant, SURVIVED,
                                        "the proofs accepted it and every vector "
                                        "reproduced"))
        finally:
            write_source(staged, original)

    code = summarize(out, verdicts, rel,
                     "prover-then-QuickChick" if args.quickchick
                     else "prover-then-vector")
    print("\n".join(out))
    return code


def _moved(want: Iterable[str], got: Iterable[str]) -> int:
    """How many lines of two vector sets differ, counting a length change as a
    disagreement at every line past the shorter one."""
    a, b = list(want), list(got)
    moved = sum(1 for x, y in zip(a, b, strict=False) if x != y)
    return moved + abs(len(a) - len(b))


# =====================================================================================
# properties: the model's own $[test] harness as the oracle
# =====================================================================================


def cmd_properties(args: argparse.Namespace) -> int:
    """Seed a defect into the model and require a `$[test]` property to report.

    This is the oracle S13 names and the expensive one, and its price is the reason it
    is a separate subcommand rather than a mode of `sail`: the `$[test]` harness links
    the whole generated model, so a mutant costs a re-emission and a recompile of the
    one large translation unit rather than the twenty seconds a spec's five files take.
    The loop is the same loop; what changes is what a kill is and what it costs.

    **It writes into `model/` and puts it back.** There is no alternative that is not a
    cold build per run: cmake is pointed at the checkout's model tree, and a copy of it
    is a second configure and a second full emission. The write is bytes-for-bytes
    reversible, it is refused outright unless git says the file is clean beforehand,
    and the restore is verified against the original text before the next mutant is
    written, so a run that cannot put the tree back stops rather than continuing. The
    lane's build tree is rebuilt from the restored source before the run reports, so
    what it leaves behind is the unmutated model rather than the last mutant's.

    **Nothing else may read the checkout while it runs**, and that is the one hazard
    the reversibility does not cover: for the length of one mutant the tree on disk is
    wrong, so `git add` stages a defect, `check.py` reports a capability format that
    disagrees with itself, and the selftest copies a mutated tree into its template.
    The run says so when it starts rather than leaving it to be discovered.

    It also **takes the lane's build lock for the whole run**, which is `run.py model
    build`'s own lock rather than a second mechanism: this loop rewrites the lane's
    build tree once per mutant, so two of these in one lane, or one of these beside a
    build, is the same wrongness that lock already exists to refuse. What the lock
    reaches is stated exactly, because an advisory lock overclaimed is worse than
    none: it refuses another run that *takes* it, and it does not and cannot refuse a
    `git add`, a `check.py`, or a selftest, none of which asks for it. Those stay the
    reader's to keep out of the window, which is why the warning below is printed as
    well as the lock being held.
    """
    e = env.load()
    root = find_root()
    rel = args.file
    path = root / rel
    if not path.is_file():
        print(f"FAIL {rel} is not in this checkout")
        return 1
    if _dirty(root, rel):
        print(f"FAIL {rel} has uncommitted changes; this loop writes into it and puts "
              "it back, so it refuses to start over an edit it would have to restore")
        return 1
    # Held for the life of this process; dropping the handle releases it, so it stays
    # bound rather than being taken and discarded. Refuses a second run of this loop in
    # the lane and a build beside it, which are the two collisions a lock can reach.
    # Taken before the harness is looked for rather than after: that look reads the
    # build tree, and a build holding the lane is exactly the run that would be part
    # way through writing what it reads.
    _lane = env.build_lock(e.build_dir)
    harness = e.build_dir / "test" / "unit_tests" / "unit_tests"
    if not harness.exists():
        print(f"FAIL no $[test] harness at {harness}; run `run.py model build` first")
        return 1

    original = read_source(path)
    out: list[str] = [
        f"== this run writes into {rel} and puts it back after every mutant.",
        "   For the length of one mutant the checkout on disk is wrong, so nothing",
        "   else may read it: `git add` would stage a defect, `check.py` would report",
        "   a format that disagrees with itself, and the selftest would copy a",
        "   mutated tree into the template every sandbox links against.",
    ]
    base_ok, base_said = _properties_run(harness)
    if not base_ok:
        out.append(f"FAIL the unmutated model's harness is not green: {base_said}")
        print("\n".join(out))
        return 1
    out.append(f"== baseline: {base_said}")

    verdicts: list[Verdict] = []
    try:
        picked = chosen(population(root, rel, tuple(args.region), tuple(args.operator)),
                        args.limit, args.sample)
        for mutant in picked:
            write_source(path, mutant.apply(original))
            built = _build_harness(e)
            if not built:
                verdicts.append(Verdict(mutant, STILLBORN,
                                        "the mutated model did not build"))
            else:
                ok, said = _properties_run(harness)
                verdicts.append(Verdict(mutant, SURVIVED, said) if ok
                                else Verdict(mutant, KILLED, said, 1))
            write_source(path, original)
            if read_source(path) != original:
                out.append(f"FAIL {rel} could not be restored; the run stops here")
                break
    finally:
        write_source(path, original)

    # The source is back and the *build tree* is not: it holds the last mutant's
    # emission, and every loop downstream of a build reads the simulator back out of
    # that tree without being able to tell whose model generated it. So the tree is
    # rebuilt from the restored source before this run reports, and the rebuild's own
    # verdict is part of what it reports.
    rebuilt = _build_harness(e)
    ok, said = _properties_run(harness) if rebuilt else (False, "the rebuild failed")
    out.append(f"== the lane's build tree, rebuilt from the restored source: {said}")
    code = summarize(out, verdicts, rel, "$[test] harness")
    if not (rebuilt and ok):
        out.append(f"FAIL the lane's build tree does not hold the unmutated model; "
                   f"run `run.py model build` before anything reads {e.simulator}")
        code = 1
    print("\n".join(out))
    return code


def _dirty(root: Path, rel: str) -> bool:
    """Whether git has anything to say about one path, which is what the restore
    guarantee stands on: a run that started over an edit could not tell its own
    restore from the edit it overwrote."""
    done = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=root,
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False)
    return bool(done.stdout.strip())


def _build_harness(e: env.Environment) -> bool:
    """Rebuild the `$[test]` executable alone, which is the emission and the one large
    translation unit and not the whole suite."""
    done = subprocess.run(["cmake", "--build", str(e.build_dir), "-j", str(e.jobs),
                           "--target", "unit_tests"],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False)
    return done.returncode == 0


def _properties_run(harness: Path) -> tuple[bool, str]:
    """Run the harness and say what it reported and whether every property held."""
    done = subprocess.run([str(harness)], capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=600)
    said = done.stdout + done.stderr
    spoke = [line.strip() for line in said.splitlines() if line.strip()]
    if done.returncode == 0:
        return True, f"{len(spoke)} harness line(s), every property held"
    first = next(iter(spoke), f"the harness exited {done.returncode}")
    return False, first[:160]


COMMANDS: cli.Table = {
    "list": (cmd_list, "the mutants one source yields, without running anything"),
    "sail": (cmd_sail, "seed a model source and require the generated vectors to move"),
    "coq": (cmd_coq, "seed a Gallina definition; the prover first, the vectors after"),
    "properties": (cmd_properties,
                   "seed a model source and require a $[test] property to report"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--limit", type=int, default=0, metavar="N",
                     help="run the first N mutants of the population")
    sub.add_argument("--sample", type=int, default=0, metavar="N",
                     help="run N evenly spaced mutants, which is what a "
                          "measurement wants where a prefix is one operator's")
    if name == "sail":
        sub.add_argument("--spec", required=True,
                         help="the oracle spec whose vectors decide")
        sub.add_argument("--file", help="which of the spec's sources to mutate; "
                                        "the last one by default")
    if name == "coq":
        sub.add_argument("--file", default=COQ_SUBJECT,
                         help="which Gallina source to mutate")
        sub.add_argument("--quickchick", action="store_true",
                         help="let QuickChick's draws and shrinking decide instead "
                              "of the enumerative harness's vectors")
    if name in ("list", "properties"):
        sub.add_argument("--file", required=True, help="the source to mutate")
    sub.add_argument("--region", action="append", default=[], metavar="NAME",
                     help="mutate only the region of this name; repeatable. What "
                          "it is for is asking an oracle about the definitions it "
                          "computes over rather than about every definition in the "
                          "file, a fixture no generated input reaches being a "
                          "survivor about the domain and not about the oracle")
    sub.add_argument("--operator", action="append", default=[], metavar="NAME",
                     help="run only this operator's mutants; repeatable. What it "
                          "is for is holding two oracles to the same population, "
                          "which a sample cannot do")


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, _flags, prog="run.py seed")

