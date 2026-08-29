#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The Gallina front's input side: generated vectors now, QuickChick when it is bought.

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
already had cost a rebuild of a landed environment apiece, which is what `_INSTALL`
below records.

    python tools/run.py quickchick check
    python tools/run.py quickchick vectors
    python tools/run.py quickchick properties

**Which finding this answers.** M0.8d's, in the register's other language: a property
written before the vectors and never run is a property whose subject somebody chose,
and the two defects that item's known-answer vectors found were both transcriptions no
structural property was written about. Generation does not depend on the choice.
"""

import argparse
import subprocess
from collections.abc import Callable

from vos import env, gallina
from vos.corpus import find_root

type Command = Callable[[argparse.Namespace], int]

# The opam package, and what installing it costs. Measured on 2026-08-29 rather than
# estimated, because the cost is the whole reason this is a priced step and the three
# routes price very differently.
#
# **Into the oracle's own `certirocq-0.9.1` switch**, the solver downgrades dune from
# 3.23.1 to 3.21.1 and **recompiles 59 packages**, the whole MetaRocq stack and
# `rocq-certirocq` itself among them: a rebuild of the M1.5 oracle's own environment to
# add a test library to it. Holding dune where it is does not help, the solver then
# removing `rocq-core`, `rocq-certirocq` and the twenty packages above them outright,
# `coq` conflicting with `rocq-runtime` at the versions that route admits.
#
# **Into the proof gate's `rocq-9.1.1`**, not at any price: that switch carries
# `rocq-core` and nothing else on purpose, an assumption reachable through an import
# being an assumption inside R-05-163's gate.
#
# **Into a switch of its own** is the route this constant states, and the finding worth
# recording is what the *obvious* spelling of it does: `opam install coq-quickchick`
# into a clean 4.14.2 switch resolves **Coq 8.16.1**, not Rocq 9.1.1, so the harness
# would be compiled by a prover five years from the one this tree pins and against a
# standard library whose modules are still named `Coq.`. The prover has to be asked for
# by name, which is why `rocq-core.9.1.1` and `coq.9.1.1` are on the line below.
PACKAGE = "coq-quickchick"
_INSTALL = (
    f"opam switch create {gallina.QUICKCHICK_SWITCH} --repos=rocq-released,default "
    "--packages=ocaml-base-compiler.4.14.2 -y && "
    f"opam install -y --switch={gallina.QUICKCHICK_SWITCH} rocq-core.9.1.1 coq.9.1.1 "
    f"{PACKAGE}")


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
        if version and found:
            where.append(f"{switch} at {version} under {said}")
        elif version:
            out.append("     and no prover this repository can call: `rocq c` is Rocq "
                       "9's spelling and Coq 8 ships `coqc` alone")
    out.append("")
    if where:
        out.append(f"ok {PACKAGE} is installed: {', '.join(where)}; "
                   "`run.py quickchick properties` runs the randomized half")
        print("\n".join(out))
        return 0
    out.append(f"FAIL {PACKAGE} is installed in no switch this repository reaches, so "
               "the randomized half does not run")
    out.append("     the enumerative half does: `run.py quickchick vectors`")
    out.append("     the install, as one priced step:")
    out.append(f"       {_INSTALL}")
    print("\n".join(out))
    return 1


def cmd_vectors(args: argparse.Namespace) -> int:
    """The enumerative half: the admission algebra's own answers, as text."""
    e = env.load()
    root = find_root()
    work = gallina.work_dir(e.lane_root)
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
    del args
    e = env.load()
    root = find_root()
    switch = next((s for s in (gallina.QUICKCHICK_SWITCH, gallina.ORACLE_SWITCH)
                   if installed(s) and gallina.prover(s) is not None), None)
    if switch is None:
        print(f"FAIL no switch this repository reaches holds both {PACKAGE} and a "
              f"prover it can call\n     the install, as one priced step:\n"
              f"       {_INSTALL}")
        return 1
    found = gallina.prover(switch)
    if found is None:
        print(f"FAIL the {switch} switch holds {PACKAGE} and no prover")
        return 1

    work = gallina.work_dir(e.lane_root)
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


COMMANDS: dict[str, tuple[Command, str]] = {
    "check": (cmd_check, "whether QuickChick is installed, and what installing costs"),
    "vectors": (cmd_vectors, "the enumerative half: generated inputs, as text"),
    "properties": (cmd_properties, "the randomized half, which QuickChick runs"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        sub = subs.add_parser(name, help=help_text)
        if name == "vectors":
            sub.add_argument("--show", type=int, default=3, metavar="N",
                             help="print the first N vectors as a sample")
    args = parser.parse_args(argv)
    handler, _ = COMMANDS[args.command]
    return handler(args)

