#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The Gallina front's input side: generated vectors, and randomized properties under QuickChick.

The CertiCoq -> Wasm oracle (M1.5) runs Gallina components on a stock engine and
**nothing generates their inputs**, so what it exercises is whatever a person thought
to write down. This tool is the missing side, and it comes in two halves that answer
the same question at different prices.

[quickchick/Vectors.v](quickchick/Vectors.v) is the half that runs today: a domain
declared in Gallina, walked exhaustively, printing one line of text per point. It
loads Stdlib alone, it is compiled in the proof gate's own switch, and its output is a
text file, which is the form both earlier model-as-oracle rigs crossed in.

[quickchick/Properties.v](quickchick/Properties.v) is the half that needs an install:
random generators and `forAll` over them, which reach a range rather than a list, drawn
from a seed the harness fixes so a verdict replays, a refuting draw printed as drawn
because `forAll` shrinks nothing. A property set whose domain holds no more points
than the draws QuickChick spends on it is decided instead by
[quickchick/Walks.v](quickchick/Walks.v), which loads Stdlib alone and walks the whole
domain, and `properties` runs both. The install is made, in a switch of its own, and
`check` reports what that switch holds. QuickChick's Coq and dune constraints require an
environment independent of the proof gate and CertiRocq compiler; `INSTALL` below
restores its tested package snapshot.

No QuickChick release installs beside Rocq 9.3.0, so `RECIPE` below builds a second
QuickChick switch at that release from the upstream commits Rocq's own CI builds, under
the lock guide's rule for commit pins. Its lock is pending the hosted checks that build
the switch from the recipe, so `check`, `properties` and `seed coq --quickchick` take
`--recipe` to run in that switch, holding the commit it was built from.

[quickchick/FreezeModel.v](quickchick/FreezeModel.v) is a third harness and a different
question: not *what does this artifact answer* but *do the two statements of one
arithmetic agree*. R-15-036i makes the instruction dictionary a permanent freeze-time
commitment, so the density model over it is the one arithmetic in this tree whose wrong
answer invalidates stored code rather than costing a recompile, and it is therefore
written down twice on purpose, in [vos/freezemodel.py](freezemodel.py) and in that
harness, and compared. `freeze` below runs the second and holds it against the first and
both against the four figures the register's own prose quotes.

    python tools/run.py quickchick check
    python tools/run.py quickchick vectors
    python tools/run.py quickchick properties
    python tools/run.py quickchick freeze

**Which finding this answers.** M0.8d's, in the register's other language: a property
written before the vectors and never run is a property whose subject somebody chose,
and the two defects that item's known-answer vectors found were both transcriptions no
structural property was written about. Generation does not depend on the choice.
"""

import argparse
import subprocess
from collections.abc import Callable
from pathlib import Path

from vos import cli, env, freezemodel, gallina
from vos.corpus import find_root

# QuickChick's latest release needs coq-simple-io, which caps Coq below 9.2~ and dune
# below 3.22. Give it an independent Rocq 9.1 environment while the proof gate uses
# Rocq 9.3 and the CertiRocq oracle uses dune 3.23.1. The explicit prover request also
# prevents a solver from satisfying the package through an older Coq generation.
#
# Public and stated as argv rather than as a sentence, for the reason `env.ROCQ_INSTALL`
# is: `run.py provision` stands this switch up and the two refusals below print it, and
# a recipe written once as a message and once as a command is a recipe only one reader
# ever runs. `env.install_line` composes the sentence from the argv.
PACKAGE = "coq-quickchick"
VERSION = "2.2.0"
INSTALL: tuple[tuple[str, ...], ...] = (
    ("opam", "switch", "create", gallina.QUICKCHICK_SWITCH,
     "--repos=rocq-released,default", "--empty", "--no-switch", "-y"),
    ("opam", "switch", "import", str(env.OPAM_LOCKS / "quickchick.lock"),
     f"--switch={gallina.QUICKCHICK_SWITCH}", "-y"),
)

# QuickChick's commit-pinned recipe, at Rocq 9.3.0. No QuickChick, coq-simple-io or
# coq-ext-lib release installs beside that release: coq-simple-io's latest caps Coq below
# 9.2 and coq-ext-lib's latest fails to build there. Each is pinned to the commit Rocq
# V9.3.0's own CI overlay builds, which tools/opam/README.md lists with the release that
# retires it, and dune to 3.23.1, below the 3.24 that rocq-elpi in QuickChick's closure
# admits. A pinned build calls itself `dev`, so what a check holds is the source opam
# says the switch's QuickChick was built from, `git+URL#commit`.
#
# Stated as argv for the reason INSTALL is. A hosted run builds the switch from it, runs
# the randomized half's checks there and exports the lock; that lock is tracked only once
# those checks pass, and until then INSTALL's snapshot is the switch provisioning makes.
PINS: tuple[tuple[str, str, str], ...] = (
    ("coq-ext-lib", "https://github.com/rocq-community/coq-ext-lib.git",
     "ddd03d257f6b85a93bfaa0ed4d03658e0ddf5075"),
    ("coq-simple-io", "https://github.com/Lysxia/rocq-simple-io.git",
     "d035c0a85f0bde4ad56c31a9fa9ef3cb5e8d0f18"),
    (PACKAGE, "https://github.com/QuickChick/QuickChick.git",
     "3d4d6c0e9f72172a9f0b26db61c5496ec8e0f568"),
)
STDLIB = "9.2.0"
DUNE = "3.23.1"
RECIPE_PIN = next(f"git+{url}#{commit}" for name, url, commit in PINS if name == PACKAGE)
RECIPE: tuple[tuple[str, ...], ...] = (
    ("opam", "switch", "create", gallina.QUICKCHICK_RECIPE_SWITCH,
     "--repos=rocq-released,default", f"--packages=ocaml-base-compiler.{env.OCAML_VERSION}",
     "--no-switch", "-y"),
    *(("opam", "pin", "add", f"--switch={gallina.QUICKCHICK_RECIPE_SWITCH}", "--no-action",
       "-y", f"{name}.dev", f"git+{url}#{commit}") for name, url, commit in PINS),
    ("opam", "install", f"--switch={gallina.QUICKCHICK_RECIPE_SWITCH}", "-y",
     f"ocamlfind.{env.OCAMLFIND_VERSION}",
     f"rocq-core.{gallina.QUICKCHICK_RECIPE_ROCQ_VERSION}", f"rocq-stdlib.{STDLIB}",
     f"dune.{DUNE}", *(f"{name}.dev" for name, _, _ in PINS)),
)


def installed(switch: str) -> str | None:
    """What QuickChick one switch carries: the source a pinned build was built from, as
    opam states it, `git+URL#commit`, or the version of a released one; None where the
    switch carries none.

    Asked of opam rather than of the filesystem, because the question is which source a
    run would compile against and that is the switch's answer, not a directory's.
    """
    done = subprocess.run(["opam", "list", "--switch", switch, "--installed",
                           "--short", "--columns=version,pin", PACKAGE],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False)
    fields = done.stdout.split()
    return fields[-1] if fields else None


def _held(recipe: bool) -> tuple[str, str | None, gallina.Prover | None, list[str]]:
    """The switch the randomized half runs in, what it holds of the half, and each
    reason it cannot run it: QuickChick's provisioned switch at VERSION, or with
    `recipe` the switch RECIPE builds, at its pinned commit.

    The package and the prover count together or not at all: a switch holding the
    library and no `rocq` is Coq 8 under another name, which compiles neither the
    shipped proofs nor a harness that Requires them. The one switch named is the one
    asked: a run that found the package somewhere else would compile in a switch no
    recipe here stands up."""
    switch = gallina.QUICKCHICK_RECIPE_SWITCH if recipe else gallina.QUICKCHICK_SWITCH
    wanted = RECIPE_PIN if recipe else VERSION
    held = installed(switch)
    found = gallina.prover(switch)
    why: list[str] = []
    if held is None:
        why.append(f"the {switch} switch carries no {PACKAGE}")
    elif held != wanted:
        why.append(f"requires {PACKAGE} {wanted}; the {switch} switch holds {held}")
    if found is None:
        why.append(f"the {switch} switch has no prover this repository can call: "
                   "`rocq c` is Rocq 9's spelling and Coq 8 ships `coqc` alone")
    return switch, held, found, why


def _install(recipe: bool) -> tuple[tuple[str, ...], ...]:
    return RECIPE if recipe else INSTALL


def cmd_check(args: argparse.Namespace) -> int:
    """Whether the randomized half can run, and what it costs to make it able to.

    Reports the package and prover in QuickChick's switch, or with `--recipe` in the
    switch the recipe builds, so a run's evidence carries the source and release it was
    taken under. Installation is the provisioner's separate command, and the recipe's a
    hosted run's.
    """
    wanted = RECIPE_PIN if args.recipe else VERSION
    switch, held, found, why = _held(args.recipe)
    said = gallina.version(found) if found else "no `rocq` binary"
    out: list[str] = ["== the randomized half's switch",
                      f"   {switch}  {PACKAGE} {held or 'not installed'}  {said}"]
    out.extend(f"     {line}" for line in why)
    out.append("")
    if not why:
        out.append(f"ok {PACKAGE} {wanted} is installed in {switch} under {said}; "
                   "`run.py quickchick properties` runs the randomized half")
        print("\n".join(out))
        return 0
    out.append(f"FAIL {PACKAGE} {wanted} is not installed in {switch}, so the randomized "
               "half does not run")
    out.append("     the enumerative half does: `run.py quickchick vectors`")
    out.append("     the install, as one priced step:")
    out.append(f"       {env.install_line(_install(args.recipe))}")
    print("\n".join(out))
    return 1


def cmd_vectors(args: argparse.Namespace) -> int:
    """The enumerative half: the admission algebra's own answers, as text."""
    return _with_workspace(args, _vectors)


def _with_workspace(args: argparse.Namespace,
                    run: Callable[[argparse.Namespace, env.Environment, Path, Path], int]
                    ) -> int:
    """Hold shared Gallina sources and outputs through staging, compilation and reporting."""
    e = env.load()
    root = find_root()
    work = gallina.work_dir(e.lane_root)
    with env.hold_lock(work, "a Gallina oracle run"):
        return run(args, e, root, work)


def _vectors(args: argparse.Namespace, e: env.Environment, root: Path, work: Path) -> int:
    out: list[str] = []
    lines = gallina.emit(root, work, out)
    if lines is None:
        print("\n".join(out))
        return 1
    target = gallina.write(lines, work / gallina.VECTORS)
    found = gallina.vector_prover()
    out.append(f"== {target} (lane {e.lane or 'primary'})")
    out.append(f"   {gallina.version(found) if found else 'unknown prover'} in the "
               f"{found.switch if found else gallina.VECTOR_SWITCH} switch")
    out.append(f"   {len(lines)} vector(s) over the admission algebra")
    out.extend(f"     {line}" for line in lines[:args.show])
    out.append(f"ok the Gallina front answered {len(lines)} generated inputs")
    print("\n".join(out))
    return 0


def cmd_properties(args: argparse.Namespace) -> int:
    """The randomized half, which is QuickChick's, refused by name where it is absent.

    Refused rather than skipped: a run that reported `ok` having tested nothing is the
    vacuous pass every floor in this repository exists to catch.

    It runs both harnesses of the half in QuickChick's switch, or with `--recipe` in the
    switch the recipe builds: Properties.v, whose sets QuickChick draws from the seed the
    harness fixes, and Walks.v, which decides each set small enough to enumerate at every
    point of its domain. It compiles their
    `Require` closure and nothing else, the proofs they read and the support harnesses
    they Require, as `kernel vectors` does for its harness. A proof outside that closure
    is compile time no verdict here can depend on.
    """
    return _with_workspace(args, _properties)


def _properties(args: argparse.Namespace, e: env.Environment, root: Path, work: Path) -> int:
    del e
    switch, held, found, why = _held(args.recipe)
    if why or found is None:
        print("\n".join([f"FAIL the {switch} switch cannot run the randomized half",
                         *(f"     {line}" for line in why),
                         "     the install, as one priced step:",
                         f"       {env.install_line(_install(args.recipe))}"]))
        return 1

    gallina.stage(root, work)
    drawn = work / "harness" / gallina.RANDOMIZED
    walked = work / "harness" / gallina.EXHAUSTIVE
    for harness in (drawn, walked):
        if not harness.is_file():
            print(f"FAIL there is no harness at {gallina.HARNESS_DIR}/{harness.name}")
            return 1
    seed = gallina.seed(drawn)
    if seed is None:
        print(f"FAIL {gallina.RANDOMIZED} fixes QuickChick's random state other than once, "
              "so no verdict it reaches replays; it states the seed in one "
              '`Extract Constant newRandomSeed => "(Random.State.make [|N|])".`')
        return 1
    failures = gallina.compile_closure(found, work, drawn, walked)
    if failures:
        print("\n".join(f"FAIL {f.source} did not compile:\n{f.said}"
                        for f in failures))
        return 1
    done = gallina.compile_one(found, work, drawn)
    print(done.stdout + done.stderr)
    passed, failed, why = gallina.drawn_sets(done)
    if not (passed or failed):
        print(f"FAIL {gallina.RANDOMIZED} decided no property set under {PACKAGE} in "
              f"{switch}: {why}")
        return 1
    found_walks, said = gallina.walks(found, work, walked)
    if said:
        print(f"FAIL {gallina.EXHAUSTIVE} did not run in {switch}:\n{said}")
        return 1
    print("\n".join(f"walked {w.name}: {w.points} point(s), {w.premise} meeting its "
                    f"premise, {w.refuted} refuting it" for w in found_walks))
    refuted = gallina.walk_failures(found_walks)
    if failed or refuted:
        print("\n".join([f"FAIL {gallina.RANDOMIZED}: {failed} drawn property set(s) "
                         f"failed and {passed} passed; {gallina.EXHAUSTIVE}: "
                         f"{len(refuted)} of {len(found_walks)} walked set(s) did not hold",
                         *(f"     {line}" for line in refuted)]))
        return 1
    print(f"ok {passed} drawn property set(s) passed under {PACKAGE} {held} in "
          f"{switch}, from seed {seed}, and {len(found_walks)} walked set(s) held at "
          f"every one of their {sum(w.points for w in found_walks)} point(s)")
    return 0


def cmd_freeze(args: argparse.Namespace) -> int:
    """The freeze's density arithmetic, stated twice and compared, plus the register.

    **Three readings and not two, and the third is what makes the first two mean
    anything.** Two statements of one model agreeing with each other says nothing about
    either agreeing with the entry it implements: a defect transcribed into both is
    exactly what their comparison cannot see. So each side is also held against the four
    figures R-15-036h and R-15-036j quote in their own prose, which is the reading a
    person makes by eye and the only one outside both statements.

    **Fail-closed at every step.** No prover, a harness that did not compile, a harness
    that printed no vector, a register sentence that has moved out from under the reader,
    or a declared family either side states nothing in: each is a finding and exit 1,
    never a comparison quietly made against less.
    """
    return _with_workspace(args, _freeze)


def _freeze(args: argparse.Namespace, e: env.Environment, root: Path, work: Path) -> int:

    ours = freezemodel.vector_lines()
    fixed, said = freezemodel.anchors(root)
    findings: list[str] = [*said, *freezemodel.empty_families(ours, freezemodel.MODULE)]
    if fixed is not None:
        findings += freezemodel.held(ours, fixed, freezemodel.MODULE)

    # The model's file is written *after* the staging and never before it. `emit` stages
    # into `work` and rebuilds it from scratch, so a file written there first is one this
    # same run deletes, and the line below would name a path the reader cannot open at
    # exactly the moment a disagreement makes them want to. Only a lane holding a prover
    # reaches the staging at all, which is why a proverless host never sees it.
    staged: list[str] = []
    theirs = gallina.emit(root, work, staged, harness=gallina.FREEZE)
    model_file = gallina.write(ours, work / gallina.FREEZE_MODEL)

    out: list[str] = [
        f"== the freeze density model ({freezemodel.SLOT_MODEL} and "
        f"{freezemodel.PACKING_TERM}), stated twice (lane {e.lane or 'primary'})",
        f"   {freezemodel.MODULE:<32} {len(ours):>4} vector(s)  {model_file}",
        *staged]
    if theirs is None:
        out.extend(f"     {line}" for line in findings)
        out.append(f"FAIL {freezemodel.HARNESS} did not answer, so nothing was "
                   "compared; the model's own statement stands unchecked")
        print("\n".join(out))
        return 1

    vector_file = gallina.write(theirs, work / gallina.FREEZE_VECTORS)
    found = gallina.vector_prover()
    out.append(f"   {freezemodel.HARNESS:<32} {len(theirs):>4} vector(s)  "
               f"{vector_file}")
    out.append(f"   {gallina.version(found) if found else 'unknown prover'} in the "
               f"{found.switch if found else gallina.VECTOR_SWITCH} switch")
    out.append("   " + "  ".join(f"{name} {count}" for name, count
                                 in freezemodel.family_counts(theirs).items()))
    out.extend(f"     {line}" for line in ours[:args.show])

    findings += freezemodel.empty_families(theirs, freezemodel.HARNESS)
    if fixed is not None:
        findings += freezemodel.held(theirs, fixed, freezemodel.HARNESS)
    findings += freezemodel.compare(theirs, ours)
    if findings:
        out.extend(f"     {line}" for line in findings)
        out.append(f"FAIL {len(findings)} finding(s) against an arithmetic "
                   f"{freezemodel.COMMITMENT} makes permanent")
        print("\n".join(out))
        return 1
    out.append(f"ok the two statements of the model agree on {len(ours)} vector(s), "
               f"and both agree with {freezemodel.REGISTER}")
    print("\n".join(out))
    return 0


COMMANDS: cli.Table = {
    "check": (cmd_check, "whether QuickChick is installed, and what installing costs"),
    "vectors": (cmd_vectors, "the enumerative half: generated inputs, as text"),
    "properties": (cmd_properties, "the randomized half: QuickChick's draws and the "
                                   "walks over domains no larger than them"),
    "freeze": (cmd_freeze, "the freeze's density model, stated twice and compared"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name in ("vectors", "freeze"):
        sub.add_argument("--show", type=int, default=3, metavar="N",
                         help="print the first N vectors as a sample")
    if name in ("check", "properties"):
        sub.add_argument("--recipe", action="store_true",
                         help="run in the switch RECIPE builds from its commit pins, "
                              "holding the pinned commit, rather than in the provisioned "
                              "QuickChick switch")


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, _flags, prog="run.py quickchick")
