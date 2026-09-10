#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The Gallina front's input side: generated vectors, and randomized properties under QuickChick.

The CertiCoq -> Wasm oracle (M1.5) runs Gallina components on a stock engine and
**nothing generates their inputs**, so what it exercises is whatever a person thought
to write down. This tool is the missing side, and it comes in two halves that answer
the same question at different prices.

[quickchick/Vectors.v](quickchick/Vectors.v) is the half that runs today: a domain
declared in Gallina, walked exhaustively, printing one line of text per point. It
needs no library this repository has not already got, it is compiled in the oracle's
own switch, and its output is a text file, which is the form both earlier
model-as-oracle rigs crossed in.

[quickchick/Properties.v](quickchick/Properties.v) is the half that needs an install:
random generators, `forAll` over them, and the thing no enumeration has, **automatic
counterexample shrinking**. The install is made, in a switch of its own, and `check`
reports which switch holds it and at what version. That the switch is its own is the
priced part rather than an aesthetic: the two routes into a switch this repository
already had cost a rebuild of a landed environment apiece, which is what `INSTALL`
below records.

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
# Rocq 9.2 and the CertiRocq oracle uses dune 3.23.1. The explicit prover request also
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


def installed(switch: str) -> str | None:
    """The QuickChick version in one switch, or None where it is not installed.

    Asked of opam rather than of the filesystem, because the question is which version
    a run would compile against and that is the switch's answer, not a directory's.
    """
    done = subprocess.run(["opam", "list", "--switch", switch, "--installed",
                           "--short", "--columns=version", PACKAGE],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False)
    found = done.stdout.strip()
    return found or None


def cmd_check(args: argparse.Namespace) -> int:
    """Whether the randomized half can run, and what it costs to make it able to.

    Deliberately not an install, though one has been made. A tool that installed a
    package into a switch a landed milestone depends on would be spending someone
    else's environment on its own convenience, and the measurement above says what that
    spend is; what this reports is which switch holds what, so a run's evidence carries
    the prover and the library version it was taken under.
    """
    del args
    out: list[str] = ["== the Gallina front's switches"]
    where: list[str] = []
    for switch in (gallina.ORACLE_SWITCH, gallina.QUICKCHICK_SWITCH):
        version = installed(switch)
        found = gallina.prover(switch)
        said = gallina.version(found) if found else "no `rocq` binary"
        out.append(f"   {switch:<18} {PACKAGE} {version or 'not installed':<15} {said}")
        # Both halves in one switch or neither counts: a switch holding the library and
        # no `rocq` is Coq 8 under another name, which compiles neither the shipped
        # proofs nor a harness that Requires them.
        if version == VERSION and found:
            where.append(f"{switch} at {version} under {said}")
        elif version and version != VERSION:
            out.append(f"     requires {PACKAGE} {VERSION}; installed {version}")
        elif version:
            out.append("     and no prover this repository can call: `rocq c` is Rocq "
                       "9's spelling and Coq 8 ships `coqc` alone")
    out.append("")
    if where:
        out.append(f"ok {PACKAGE} is installed: {', '.join(where)}; "
                   "`run.py quickchick properties` runs the randomized half")
        print("\n".join(out))
        return 0
    out.append(f"FAIL {PACKAGE} {VERSION} is installed in no switch this repository reaches, so "
               "the randomized half does not run")
    out.append("     the enumerative half does: `run.py quickchick vectors`")
    out.append("     the install, as one priced step:")
    out.append(f"       {env.install_line(INSTALL)}")
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
    found = gallina.prover(gallina.ORACLE_SWITCH)
    out.append(f"== {target} (lane {e.lane or 'primary'})")
    out.append(f"   {gallina.version(found) if found else 'unknown prover'} in the "
               f"{gallina.ORACLE_SWITCH} switch")
    out.append(f"   {len(lines)} vector(s) over the admission algebra")
    out.extend(f"     {line}" for line in lines[:args.show])
    out.append(f"ok the Gallina front answered {len(lines)} generated inputs")
    print("\n".join(out))
    return 0


def cmd_properties(args: argparse.Namespace) -> int:
    """The randomized half, which is QuickChick's, refused by name where it is absent.

    Refused rather than skipped: a run that reported `ok` having tested nothing is the
    vacuous pass every floor in this repository exists to catch.
    """
    return _with_workspace(args, _properties)


def _properties(args: argparse.Namespace, e: env.Environment, root: Path, work: Path) -> int:
    del args, e
    versions = {s: installed(s) for s in (gallina.QUICKCHICK_SWITCH, gallina.ORACLE_SWITCH)}
    switch = next((s for s, version in versions.items()
                   if version == VERSION and gallina.prover(s) is not None), None)
    if switch is None:
        found_versions = ", ".join(f"{s}: {v or 'not installed'}" for s, v in versions.items())
        print(f"FAIL no switch this repository reaches holds both {PACKAGE} {VERSION} and a "
              f"prover it can call\n     installed versions: {found_versions}\n"
              f"     the install, as one priced step:\n"
              f"       {env.install_line(INSTALL)}")
        return 1
    found = gallina.prover(switch)
    if found is None:
        print(f"FAIL the {switch} switch holds {PACKAGE} and no prover")
        return 1

    gallina.stage(root, work)
    failures = gallina.compile_proofs(found, work) + gallina.compile_support(found, work)
    if failures:
        print("\n".join(f"FAIL {f.source} did not compile:\n{f.said}"
                        for f in failures))
        return 1
    source = work / "harness" / gallina.RANDOMIZED
    if not source.is_file():
        print(f"FAIL there is no harness at "
              f"{gallina.HARNESS_DIR}/{gallina.RANDOMIZED}")
        return 1
    done = gallina.compile_one(found, work, source)
    print(done.stdout + done.stderr)
    if done.returncode != 0:
        print(f"FAIL {gallina.RANDOMIZED} did not run under {PACKAGE} in {switch}")
        return 1
    passed = done.stdout.count("+++ Passed")
    failed = done.stdout.count("*** Failed")
    if failed or not passed:
        print(f"FAIL {gallina.RANDOMIZED}: {failed} property set(s) failed and "
              f"{passed} passed")
        return 1
    print(f"ok {passed} property set(s) passed under {PACKAGE} in {switch}")
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
    found = gallina.prover(gallina.ORACLE_SWITCH)
    out.append(f"   {freezemodel.HARNESS:<32} {len(theirs):>4} vector(s)  "
               f"{vector_file}")
    out.append(f"   {gallina.version(found) if found else 'unknown prover'} in the "
               f"{gallina.ORACLE_SWITCH} switch")
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
    "properties": (cmd_properties, "the randomized half, which QuickChick runs"),
    "freeze": (cmd_freeze, "the freeze's density model, stated twice and compared"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name in ("vectors", "freeze"):
        sub.add_argument("--show", type=int, default=3, metavar="N",
                         help="print the first N vectors as a sample")


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, _flags, prog="run.py quickchick")
