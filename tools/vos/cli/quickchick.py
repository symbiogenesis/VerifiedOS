#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The Gallina front's input side: generated vectors, and randomized properties under QuickChick.

Harnesses under `tools/quickchick/`:
- [quickchick/Vectors.v](../../quickchick/Vectors.v): exhaustive domain walk using Stdlib,
  compiled in the proof switch (`vector`).
- [quickchick/Properties.v](../../quickchick/Properties.v) and
  [quickchick/Walks.v](../../quickchick/Walks.v): seeded QuickChick property sets and
  exhaustive small-domain walks, run in the QuickChick switch (or `--recipe` switch).
- [quickchick/FreezeModel.v](../../quickchick/FreezeModel.v): cross-checks the freeze
  density model (R-15-036i) against [vos/freezemodel.py](../freezemodel.py) and the
  register's anchor figures (R-15-036h, R-15-036j).

    python tools/run.py quickchick check
    python tools/run.py quickchick vectors
    python tools/run.py quickchick properties
    python tools/run.py quickchick freeze
"""

import argparse
import subprocess
from collections.abc import Callable
from pathlib import Path

from vos import cli, env, freezemodel, gallina
from vos.corpus import find_root

# Provisioned QuickChick opam switch imported from `tools/opam/quickchick.lock`.
PACKAGE = "coq-quickchick"
PINS: tuple[tuple[str, str, str], ...] = (
    ("coq-simple-io", "https://github.com/Lysxia/rocq-simple-io.git",
     "d035c0a85f0bde4ad56c31a9fa9ef3cb5e8d0f18"),
    (PACKAGE, "https://github.com/QuickChick/QuickChick.git",
     "3d4d6c0e9f72172a9f0b26db61c5496ec8e0f568"),
)
INSTALL_PIN = next(f"git+{url}#{commit}" for name, url, commit in PINS if name == PACKAGE)
INSTALL: tuple[tuple[str, ...], ...] = (
    ("opam", "switch", "create", gallina.QUICKCHICK_SWITCH,
     "--repos=rocq-released,default", "--empty", "--no-switch", "-y"),
    ("opam", "switch", "import", str(env.OPAM_LOCKS / "quickchick.lock"),
     f"--switch={gallina.QUICKCHICK_SWITCH}", "-y"),
)

# Candidate recipe at Rocq 9.3.0; see [opam/README.md](../../opam/README.md).
RECIPE_PINS: tuple[tuple[str, str, str], ...] = (
    ("coq-simple-io", "https://github.com/Lysxia/rocq-simple-io.git",
     "5c70625af00af6182817e490d93247cdefbed2e1"),
    (PACKAGE, "https://github.com/QuickChick/QuickChick.git",
     "527216554f31bfa526ae5395d64aa4de5beaf437"),
)
STDLIB = "9.2.0"
DUNE = "3.23.1"
EXTLIB = "0.13.2"
INTRINSICS = "v0.17.3"
RECIPE_PIN = next(f"git+{url}#{commit}" for name, url, commit in RECIPE_PINS if name == PACKAGE)
RECIPE: tuple[tuple[str, ...], ...] = (
    ("opam", "switch", "create", gallina.QUICKCHICK_RECIPE_SWITCH,
     "--repos=rocq-released,default", f"--packages=ocaml-base-compiler.{env.OCAML_VERSION}",
     "--no-switch", "-y"),
    *(("opam", "pin", "add", f"--switch={gallina.QUICKCHICK_RECIPE_SWITCH}", "--no-action",
       "-y", f"{name}.dev", f"git+{url}#{commit}") for name, url, commit in RECIPE_PINS),
    ("opam", "install", f"--switch={gallina.QUICKCHICK_RECIPE_SWITCH}", "-y",
     f"ocamlfind.{env.OCAMLFIND_VERSION}",
     f"rocq-core.{gallina.QUICKCHICK_RECIPE_ROCQ_VERSION}", f"rocq-stdlib.{STDLIB}",
     f"dune.{DUNE}", f"coq-ext-lib.{EXTLIB}", f"ocaml_intrinsics_kernel.{INTRINSICS}",
     *(f"{name}.dev" for name, _, _ in RECIPE_PINS)),
)


def installed(switch: str) -> str | None:
    """Return the installed `coq-quickchick` pin (`git+URL#commit`) or version in `switch`, or `None`."""
    done = subprocess.run(["opam", "list", "--switch", switch, "--installed",
                           "--short", "--columns=version,pin", PACKAGE],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, stdin=subprocess.DEVNULL,
                          env=env.declining_environment())
    fields = done.stdout.split() if done.returncode == 0 else []
    return fields[-1] if fields else None


def _held(recipe: bool) -> tuple[str, str | None, gallina.Prover | None, list[str]]:
    """Inspect the QuickChick switch (or recipe switch) and return `(switch, pin, prover, reasons)`."""
    switch = gallina.QUICKCHICK_RECIPE_SWITCH if recipe else gallina.QUICKCHICK_SWITCH
    expected = RECIPE_PIN if recipe else INSTALL_PIN
    held = installed(switch)
    found = gallina.prover(switch)
    why: list[str] = []
    if held is None:
        why.append(f"opam lists no {PACKAGE} in the {switch} switch")
    elif held != expected:
        why.append(f"requires {PACKAGE} built from {expected}; the {switch} switch "
                   f"holds {held}")
    if found is None:
        why.append(f"the {switch} switch has no prover this repository can call: "
                   "`rocq c` is Rocq 9's spelling and Coq 8 ships `coqc` alone")
    return switch, held, found, why


def _install(recipe: bool) -> tuple[tuple[str, ...], ...]:
    return RECIPE if recipe else INSTALL


def cmd_check(args: argparse.Namespace) -> int:
    """Report whether the QuickChick switch and prover are installed at the expected pin."""
    switch, held, found, why = _held(args.recipe)
    expected = RECIPE_PIN if args.recipe else INSTALL_PIN
    said = gallina.version(found) if found else "no `rocq` binary"
    out: list[str] = ["== the randomized half's switch",
                      f"   {switch}  {PACKAGE} {held or 'not installed'}  {said}"]
    out.extend(f"     {line}" for line in why)
    out.append("")
    if not why:
        recipe = " --recipe" if args.recipe else ""
        out.append(f"ok {PACKAGE} is built from {expected} in {switch} under {said}; "
                   f"`run.py quickchick properties{recipe}` runs the randomized half")
        print("\n".join(out))
        return 0
    out.append(f"FAIL {PACKAGE} built from {expected} is not installed in {switch}, so "
               "the randomized half does not run")
    out.append("     the enumerative half does: `run.py quickchick vectors`")
    out.append("     the install, as one priced step:")
    out.append(f"       {env.install_line(_install(args.recipe))}")
    print("\n".join(out))
    return 1


def cmd_vectors(args: argparse.Namespace) -> int:
    """Emit exhaustive admission-algebra vectors via `Vectors.v`."""
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
    """Run `Properties.v` (seeded QuickChick draws) and `Walks.v` (exhaustive small-domain walks)."""
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
        print(f"FAIL {gallina.RANDOMIZED} fixes QuickChick's random state other than once "
              "after its last Require of QuickChick, so no verdict it reaches replays; it "
              "states the seed in one "
              '`Extract Constant newRandomSeed => "(Random.State.make [|N|])".` after it')
        return 1
    failures = gallina.compile_closure(found, work, drawn, walked)
    if failures:
        print("\n".join(f"FAIL {f.source} did not compile:\n{f.said}"
                        for f in failures))
        return 1
    done = gallina.compile_one(found, work, drawn)
    print(done.stdout + done.stderr)
    sets = gallina.drawn_sets(done)
    passed, failed, why = sets.passed, sets.failed, sets.why
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
    """Compare Python and Gallina (`FreezeModel.v`) freeze-density vectors against register anchors."""
    return _with_workspace(args, _freeze)


def _freeze(args: argparse.Namespace, e: env.Environment, root: Path, work: Path) -> int:

    ours = freezemodel.vector_lines()
    fixed, said = freezemodel.anchors(root)
    findings: list[str] = [*said, *freezemodel.empty_families(ours, freezemodel.MODULE)]
    if fixed is not None:
        findings += freezemodel.held(ours, fixed, freezemodel.MODULE)

    # Write `model_file` after `gallina.emit`, which stages a clean `work` directory.
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
    "check": (cmd_check, "which QuickChick commit is installed, and what installing costs"),
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
                              "the provisioned QuickChick switch while its lock is "
                              "RECIPE's export, and name RECIPE's build rather than the "
                              "lock's import where that switch cannot run the half")


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, _flags, prog="run.py quickchick")
