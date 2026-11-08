#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The seeded-defect generator: one engine, several oracles, three verdicts.

Generates mutants via [vos/mutate.py](../mutate.py) and evaluates them against a selected
oracle:

    run.py seed sail --spec capformat   generated vectors ([vos/oracle.py](../oracle.py))
    run.py seed coq                     Rocq prover, then Gallina vectors or QuickChick
    run.py seed properties --file ...   the model's `$[test]` harness

Each mutant is classified via [vos/seeded.py](../seeded.py) as **stillborn** (failed to
compile), **killed** (compiled and detected by the oracle), **survived** (compiled and
undetected), or **undecided** (prover timeout/signal or unanswered QuickChick draw).
Every run holds the WSL keepalive lease ([vos/env.py](../env.py)) and journals verdicts
incrementally beside the staged trees.
"""

import argparse
import concurrent.futures
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

from vos import cli, env, gallina, mutate, sailrig
from vos import oracle as oracle_spec
from vos.cli import quickchick
from vos.corpus import find_root
from vos.seeded import (
    KILLED,
    STILLBORN,
    SURVIVED,
    UNDECIDED,
    Journal,
    Scope,
    Verdict,
    chosen,
    shard,
    summarize,
    unshard,
)

# Separate workspaces per oracle keep concurrent compiler runs from sharing a tree.
WORK = "seed"

# Default Gallina mutation subject (`proofs/CyclicExecutive.v`).
COQ_SUBJECT = "proofs/CyclicExecutive.v"


def lane_env() -> env.Environment:
    """Load the lane environment and acquire the WSL keepalive lease."""
    e = env.load()
    env.keepalive()
    return e


def journal_at(e: env.Environment, name: str) -> Journal:
    """Return a `Journal` in the lane's seed root outside rebuilt staging trees."""
    return Journal(e.lane_root / WORK / f"{name}.journal")


def read_source(path: Path) -> str:
    """Read UTF-8 source text while preserving exact line endings."""
    return path.read_bytes().decode("utf-8")


def write_source(path: Path, text: str) -> None:
    """Write UTF-8 source text while preserving exact line endings."""
    path.write_bytes(text.encode("utf-8"))


def population(root: Path, rel: str, named: tuple[str, ...] = (),
               only: tuple[str, ...] = ()) -> list[mutate.Mutant]:
    """Return all mutants of `rel`, optionally filtered by region (`named`) and operator (`only`)."""
    lane = mutate.lane_of(rel)
    found = mutate.mutants(read_source(root / rel), lane, rel, named=named)
    return [m for m in found if m.operator in only] if only else found


def picked_with_scope(root: Path, rel: str,
                      args: argparse.Namespace) -> tuple[list[mutate.Mutant], Scope]:
    """Select the mutants to run and record their coverage against the full population."""
    whole = population(root, rel)
    picked = chosen(population(root, rel, tuple(args.region), tuple(args.operator)),
                    args.limit, args.sample)
    left = tuple(sorted({m.operator for m in whole} - {m.operator for m in picked}))
    return picked, Scope(whole=len(whole), ran=len(picked), left=left)


# =====================================================================================
# list: the population, without running anything
# =====================================================================================


def cmd_list(args: argparse.Namespace) -> int:
    """List the mutants generated for one source file, grouped by operator."""
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
    """Copy the model files compiled by `spec` into `tree`."""
    if tree.exists():
        shutil.rmtree(tree)
    for source in spec.sources:
        target = tree / source
        target.parent.mkdir(parents=True, exist_ok=True)
        write_source(target, read_source(root / source))


def cmd_sail(args: argparse.Namespace) -> int:
    """Seed a defect into a model source and require the generated vectors to move."""
    e = lane_env()
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
    with env.hold_lock(work, "a Sail mutation run"):
        return _sail_run(args, e, root, spec, rel, work)


def _sail_run(args: argparse.Namespace, e: env.Environment, root: Path,
              spec: oracle_spec.Spec, rel: str, work: Path) -> int:
    """One population with its staged sources and journal held for the whole run."""
    tree = work / "tree"
    stage_sail(root, spec, tree)
    original = read_source(root / rel)
    picked, scope = picked_with_scope(root, rel, args)
    book = journal_at(e, f"sail-{spec.name}")

    out: list[str] = [book.start(rel, f"{spec.name} vector", scope)]
    baseline = oracle_spec.generate(root, spec, work / "base", out, model_root=tree)
    if baseline is None:
        out.append("FAIL the unmutated spec did not run, so there is no baseline")
        book.close(1)
        print("\n".join(out))
        return 1
    _, total, _ = sailrig.census(baseline)
    out.append(f"== baseline: {total} vector(s) from {spec.name}")

    verdicts: list[Verdict] = []
    for mutant in picked:
        write_source(tree / rel, mutant.apply(original))
        try:
            said: list[str] = []
            got = oracle_spec.generate(root, spec, work / "mutant", said,
                                       model_root=tree)
            if got is None:
                verdicts.append(book.record(
                    Verdict(mutant, STILLBORN, "the mutated model did not compile")))
                continue
            _, bad, n_want, n_got = sailrig.compare(baseline, got)
            if bad or n_want != n_got:
                verdicts.append(book.record(
                    Verdict(mutant, KILLED, f"{bad} of {total} vector(s) moved", bad)))
            else:
                verdicts.append(book.record(
                    Verdict(mutant, SURVIVED, "every vector reproduced")))
        finally:
            write_source(tree / rel, original)

    code = summarize(out, verdicts, rel, f"{spec.name} vector",
                     scope.decided(len(verdicts)))
    book.close(code)
    print("\n".join(out))
    return code


# =====================================================================================
# coq: the prover first, and then the Gallina vectors
# =====================================================================================


def _coq_verdict(found: gallina.Prover, work: Path, rel: str, harness: Path,
                 mutant: mutate.Mutant, baseline: list[str],
                 quickchick: bool) -> Verdict:
    """Evaluate one Gallina `mutant` in staged tree `work` against the prover and vector/QuickChick oracle."""
    walker = harness.parent / gallina.EXHAUSTIVE
    moved = gallina.closure_dependents(work, rel, harness, walker) if quickchick else None
    failures = gallina.compile_dependents(found, work, rel, moved)
    if failures:
        return Verdict(mutant, KILLED,
                       "the prover refused " + ", ".join(f.source for f in failures),
                       len(failures))
    if gallina.compile_support(found, work, moved, randomized=quickchick):
        return Verdict(mutant, STILLBORN,
                       "the harness would not build over the mutant")
    if quickchick:
        accepted = f"the proofs {gallina.RANDOMIZED}'s Require closure holds accepted it"
        walked, said = gallina.walks(found, work, walker)
        if said:
            return Verdict(mutant, STILLBORN,
                           "the walk harness did not run over the mutant")
        refuted = gallina.walk_failures(walked)
        if refuted:
            return Verdict(mutant, KILLED,
                           f"{accepted} and {len(refuted)} of {len(walked)} walked "
                           f"set(s) did not hold: {refuted[0]}", len(refuted))
        sets = gallina.properties(found, work, harness)
        if sets.failed:
            return Verdict(mutant, KILLED,
                           f"{accepted} and QuickChick refuted {sets.failed} of "
                           f"{sets.failed + sets.passed} property set(s): {sets.why}",
                           sets.failed)
        if sets.ended == gallina.DRAWN_CRASHED:
            return Verdict(mutant, KILLED, f"{accepted} and {sets.why}", 1)
        if sets.ended == gallina.DRAWN_UNANSWERED:
            return Verdict(mutant, UNDECIDED,
                           f"the drawn harness gave no answer over the mutant: {sets.why}, "
                           "so nothing was decided about it")
        if not sets.passed:
            return Verdict(mutant, STILLBORN,
                           f"the drawn harness decided nothing over the mutant: {sets.why}")
        return Verdict(mutant, SURVIVED,
                       f"{accepted}, {len(walked)} walked set(s) held and {sets.passed} "
                       "drawn property set(s) passed")
    lines, said = gallina.vectors(found, work, harness)
    if said:
        return Verdict(mutant, STILLBORN, "the harness did not run over the mutant")
    moved = _moved(baseline, lines)
    if moved:
        return Verdict(mutant, KILLED,
                       f"the proofs accepted it and {moved} of {len(baseline)} "
                       "vector(s) moved", moved)
    return Verdict(mutant, SURVIVED,
                   "the proofs accepted it and every vector reproduced")


def _accounted(book: Journal, tree: str) -> Callable[[gallina.Compiled], None]:
    """Return a callback that logs each compile's duration and exit status to `book`."""
    def note(done: gallina.Compiled) -> None:
        ended = (f"stopped at gallina's per-file limit of {done.limit:g} s"
                 if done.exit is None else f"exit {done.exit}")
        book.note(f"{tree}: compiled {done.source} in {done.seconds:.2f} s, {ended}")
    return note


def _stopped(stopped: gallina.CompileTimeout | gallina.CompileSignalled) -> str:
    """Format a timeout or signal termination for verdict or baseline reporting."""
    if isinstance(stopped, gallina.CompileSignalled):
        return (f"the compile of {stopped.source} was ended by "
                f"{gallina.signal_named(stopped.signal)}")
    return (f"the compile of {stopped.source} reached gallina's per-file limit of "
            f"{stopped.timeout:g} s and was stopped")


def _coq_shard(found: gallina.Prover, work: Path, rel: str, harness_name: str,
               mutants: list[mutate.Mutant], original: str, baseline: list[str],
               quickchick: bool, book: Journal) -> list[Verdict]:
    """Run one shard of `mutants` serially in `work`, restoring `original` after each mutant."""
    staged = work / rel
    harness = work / "harness" / harness_name
    verdicts: list[Verdict] = []
    with gallina.observed(_accounted(book, work.name)):
        for mutant in mutants:
            book.note(f"{work.name}: mutant {mutant.ident} ({mutant.operator}) "
                      f"{mutant.what}")
            write_source(staged, mutant.apply(original))
            try:
                try:
                    verdict = _coq_verdict(found, work, rel, harness, mutant, baseline,
                                           quickchick)
                except (gallina.CompileTimeout, gallina.CompileSignalled) as stopped:
                    verdict = Verdict(mutant, UNDECIDED,
                                      f"{_stopped(stopped)}, so nothing was decided "
                                      "about it")
                verdicts.append(book.record(verdict,
                                            f"{work.name}: mutant {mutant.ident}"))
            finally:
                write_source(staged, original)
    return verdicts


def _run_shards(found: gallina.Prover, trees: list[Path], rel: str, harness_name: str,
                picked: list[mutate.Mutant], original: str, baseline: list[str],
                quickchick: bool, book: Journal) -> list[Verdict]:
    """Run `picked` across `trees` using round-robin sharding and reassemble in population order."""
    if len(trees) == 1:
        return _coq_shard(found, trees[0], rel, harness_name, picked, original,
                          baseline, quickchick, book)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(trees)) as pool:
        done = [pool.submit(_coq_shard, found, tree, rel, harness_name, part,
                            original, baseline, quickchick, book)
                for tree, part in zip(trees, shard(picked, len(trees)), strict=True)]
        got = [future.result() for future in done]
    return unshard(got)


def randomized_subjects(root: Path) -> list[str]:
    """Return sorted checkout-relative proof sources in `Properties.v`'s `Require` closure."""
    harness = root / gallina.HARNESS_DIR / gallina.RANDOMIZED
    if not harness.is_file():
        return []
    return sorted(source.relative_to(root).as_posix()
                  for wave in gallina.closure(root, harness) for source in wave
                  if source.parent == root / gallina.PROOFS)


def _quickchick_baseline(root: Path, found: gallina.Prover, work: Path,
                         harness_name: str, book: Journal | None = None
                         ) -> tuple[list[str] | None, str]:
    """Stage and verify the unmutated QuickChick and walk harnesses in `work`."""
    gallina.stage(root, work)
    drawn = work / "harness" / harness_name
    walker = work / "harness" / gallina.EXHAUSTIVE
    for harness in (drawn, walker):
        if not harness.is_file():
            return None, f"there is no harness at {gallina.HARNESS_DIR}/{harness.name}"
    seed = gallina.seed(drawn)
    if seed is None:
        return None, (f"{harness_name} fixes QuickChick's random state other than once "
                      "after its last Require of QuickChick, so no verdict over it replays")
    if book is not None:
        book.note(f"{work.name}: {harness_name} draws from seed {seed}")
    if gallina.compile_closure(found, work, drawn, walker):
        return None, "the unmutated tree did not compile, so there is no baseline"
    walked, said = gallina.walks(found, work, walker)
    if said or gallina.walk_failures(walked):
        return None, (f"the unmutated tree's {gallina.EXHAUSTIVE} is not green: "
                      f"{said or '; '.join(gallina.walk_failures(walked))}")
    sets = gallina.properties(found, work, drawn)
    if not (sets.passed or sets.failed):
        return None, f"the unmutated tree's {harness_name} decided nothing: {sets.why}"
    if sets.failed:
        return None, (f"the unmutated tree's {harness_name} is not green: {sets.failed} "
                      f"property set(s) failed and {sets.passed} passed: {sets.why}")
    return [], ""


def _stand_up(root: Path, found: gallina.Prover, trees: list[Path], harness_name: str,
              quickchick: bool, book: Journal) -> tuple[list[str] | None, str]:
    """Stage and compile all `trees` concurrently and verify their unmutated baselines agree."""
    def one(work: Path) -> tuple[list[str] | None, str]:
        with gallina.observed(_accounted(book, work.name)):
            book.note(f"{work.name}: baseline")
            try:
                if quickchick:
                    return _quickchick_baseline(root, found, work, harness_name, book)
                said: list[str] = []
                return gallina.emit(root, work, said), "\n".join(said)
            except (gallina.CompileTimeout, gallina.CompileSignalled) as stopped:
                return None, f"{_stopped(stopped)}, so the unmutated tree has no baseline"

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(trees)) as pool:
        got = list(pool.map(one, trees))
    for baseline, why in got:
        if baseline is None:
            return None, why or "the unmutated tree did not run, so there is no baseline"
    first = got[0][0]
    if any(other != first for other, _ in got[1:]):
        return None, ("the staged trees disagree unmutated, so a verdict would depend "
                      "on which shard drew the mutant")
    return first, ""


def cmd_coq(args: argparse.Namespace) -> int:
    """Seed mutations into a Gallina source and test against the prover and vector/QuickChick oracle."""
    e = lane_env()
    root = find_root()
    rel = args.file
    if not (root / rel).is_file():
        print(f"FAIL {rel} is not in this checkout")
        return 1
    if args.quickchick:
        subjects = randomized_subjects(root)
        if Path(rel).as_posix() not in subjects:
            print(f"FAIL {rel} is not a proof source {gallina.RANDOMIZED}'s Require "
                  "closure holds, so no QuickChick property reads a mutation of it; "
                  f"--quickchick mutates {', '.join(subjects) or 'none'}, and the "
                  "enumerative mode mutates any proof source")
            return 1

    if args.recipe and not args.quickchick:
        print("FAIL --recipe names the switch QuickChick's recipe builds and runs only "
              "with --quickchick")
        return 1
    if args.quickchick:
        switch, _, found, why = quickchick._held(args.recipe)
        if why or found is None:
            check = "quickchick check --recipe" if args.recipe else "quickchick check"
            print("\n".join([f"FAIL the {switch} switch cannot run the randomized half",
                             *(f"     {line}" for line in why),
                             f"     `run.py {check}` says what installing it costs"]))
            return 1
    else:
        found = gallina.prover(gallina.VECTOR_SWITCH)
        if found is None:
            print(f"FAIL no prover in the {gallina.VECTOR_SWITCH} switch; "
                  "`run.py provision` says which switches this lane holds")
            return 1

    name = "quickchick" if args.quickchick else "coq"
    work = e.lane_root / WORK / name
    with env.hold_lock(work, "a Gallina mutation run"):
        return _coq_run(args, e, root, rel, found, work)


def _coq_run(args: argparse.Namespace, e: env.Environment, root: Path, rel: str,
             found: gallina.Prover, work: Path) -> int:
    """Execute a Gallina mutation run while the caller holds the workspace lock."""
    name = work.name
    switch = found.switch
    out: list[str] = []
    harness_name = gallina.RANDOMIZED if args.quickchick else gallina.ENUMERATIVE
    original = read_source(root / rel)
    oracle_name = ("prover-then-QuickChick" if args.quickchick
                   else "prover-then-vector")
    picked, scope = picked_with_scope(root, rel, args)

    book = journal_at(e, name)
    out.append(book.start(rel, oracle_name, scope))

    jobs = max(1, args.jobs)
    trees = [work] if jobs == 1 else [work / f"j{n}" for n in range(jobs)]
    baseline, why = _stand_up(root, found, trees, harness_name, args.quickchick, book)
    if baseline is None:
        out.append(f"FAIL {why}")
        book.note(f"no baseline: {why}")
        book.close(1)
        print("\n".join(out))
        return 1
    said = (f"{len(baseline)} vector(s) from the Gallina front" if not args.quickchick
            else (f"green under QuickChick from seed "
                  f"{gallina.seed(trees[0] / 'harness' / harness_name)} and at every "
                  "point of each walked domain"))
    out.append(f"== baseline: {said}, {gallina.version(found)} in {switch}"
               + (f", over {len(trees)} staged tree(s) agreeing unmutated"
                  if len(trees) > 1 else ""))

    verdicts = _run_shards(found, trees, rel, harness_name, picked, original,
                           baseline, args.quickchick, book)

    code = summarize(out, verdicts, rel, oracle_name, scope.decided(len(verdicts)))
    book.close(code)
    print("\n".join(out))
    return code


def _moved(want: Iterable[str], got: Iterable[str]) -> int:
    """Return the number of differing lines between `want` and `got`, including length differences."""
    a, b = list(want), list(got)
    moved = sum(1 for x, y in zip(a, b, strict=False) if x != y)
    return moved + abs(len(a) - len(b))


# =====================================================================================
# properties: the model's own $[test] harness as the oracle
# =====================================================================================


def cmd_properties(args: argparse.Namespace) -> int:
    """Seed mutations into a Sail model source in-place and test with the `$[test]` harness.

    Requires a clean Git status on the target file, holds the lane's build lock for the
    duration of the run, restores the original file after each mutant, and rebuilds the
    unmutated `unit_tests` target before returning. No other process may read the
    checkout while this command runs.
    """
    e = lane_env()
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
    # Keep the lock handle alive for the process lifetime to exclude concurrent builds
    # and properties runs in this lane. Acquire it before reading the build tree.
    _lane = env.build_lock(e.build_dir)
    harness = e.build_dir / "test" / "unit_tests" / "unit_tests"
    if not harness.exists():
        print(f"FAIL no $[test] harness at {harness}; run `run.py model build` first")
        return 1

    original = read_source(path)
    picked, scope = picked_with_scope(root, rel, args)
    book = journal_at(e, "properties")
    out: list[str] = [
        f"== this run writes into {rel} and puts it back after every mutant.",
        "   For the length of one mutant the checkout on disk is wrong, so nothing",
        "   else may read it: `git add` would stage a defect, `check.py` would report",
        "   a format that disagrees with itself, and the selftest would copy a",
        "   mutated tree into the template every sandbox links against.",
        book.start(rel, "$[test] harness", scope),
    ]
    base_ok, base_said = _properties_run(harness)
    if not base_ok:
        out.append(f"FAIL the unmutated model's harness is not green: {base_said}")
        book.close(1)
        print("\n".join(out))
        return 1
    out.append(f"== baseline: {base_said}")

    verdicts: list[Verdict] = []
    try:
        for mutant in picked:
            write_source(path, mutant.apply(original))
            built = _build_harness(e)
            if not built:
                verdicts.append(book.record(
                    Verdict(mutant, STILLBORN, "the mutated model did not build")))
            else:
                ok, said = _properties_run(harness)
                verdicts.append(book.record(Verdict(mutant, SURVIVED, said) if ok
                                            else Verdict(mutant, KILLED, said, 1)))
            write_source(path, original)
            if read_source(path) != original:
                out.append(f"FAIL {rel} could not be restored; the run stops here")
                break
    finally:
        write_source(path, original)

    # Rebuild and check the restored source: the build tree still holds the last
    # mutant, and downstream commands trust the simulator in that tree.
    rebuilt = _build_harness(e)
    ok, said = _properties_run(harness) if rebuilt else (False, "the rebuild failed")
    out.append(f"== the lane's build tree, rebuilt from the restored source: {said}")
    # Count recorded verdicts because a failed source restore can truncate the sample.
    code = summarize(out, verdicts, rel, "$[test] harness",
                     scope.decided(len(verdicts)))
    if not (rebuilt and ok):
        out.append(f"FAIL the lane's build tree does not hold the unmutated model; "
                   f"run `run.py model build` before anything reads {e.simulator}")
        code = 1
    book.close(code)
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
                         help="which Gallina source to mutate; with --quickchick, a "
                              "proof source Properties.v's Require closure holds")
        sub.add_argument("--quickchick", action="store_true",
                         help="let QuickChick's seeded draws, and the walks over "
                              "domains no larger than them, decide instead of the "
                              "enumerative harness's vectors")
        sub.add_argument("--recipe", action="store_true",
                         help="with --quickchick, run in the switch tools/vos/cli/"
                              "quickchick.py's RECIPE builds from its commit pins, "
                              "the provisioned QuickChick switch while its lock is "
                              "RECIPE's export, and point a refusal at `quickchick "
                              "check --recipe`")
        sub.add_argument("--jobs", type=int, default=1, metavar="N",
                         help="stage N trees and run the population across them at "
                              "once. Every mutant is one prover run and the trees "
                              "share no file, so a machine with idle cores finishes "
                              "in roughly an Nth of the wall clock; the partition is "
                              "the tool's and is exhaustive whatever N is, which a "
                              "hand-written one is not. Only this oracle takes it: "
                              "`properties` writes into the checkout and so cannot "
                              "have two of itself running")
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
