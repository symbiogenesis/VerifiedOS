#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The model-as-oracle vector generator: any Sail function, as a differential oracle.

M2.1 held a C instantiation of the capability format to 21,546 vectors the model
itself emitted, and R1a held the authored SystemVerilog to 658,659 over thirteen
kinds. Both rigs were built inside one item and thrown away, so the third consumer
would have written the formatters, the shift register, the loop nests and the line
discipline a third time. This is that rig standing, and what a caller supplies is a
**spec**: the model sources to compile against, and per line kind the parameters, the
domain that walks them, the Sail that calls the model, and what to print.

    python tools/run.py oracle list                     # the specs, and how large each is
    python tools/run.py oracle emit --spec capformat    # the Sail harness, on the host

    python tools/run.py oracle vectors --spec capformat
    python tools/run.py oracle vectors --spec keccak

`list` and `emit` answer on the host, being a parse and a text emission. `vectors`
runs in the guest, where Sail lives: it emits the harness, compiles it together with
the spec's model sources, runs it, and writes the vectors into this lane's own working
directory. The file is derived from the checkout rather than part of it, and two
worktrees emitting at once must not write one path, which is why the lane owns it.

**What a run decides** is what the named functions return over the domain the spec
states. It is a measurement and not a proof, and what it does not decide is whether
the domain reaches the case that matters. [tools/run.py seed](seed.py) is the instrument
that answers *that*, by seeding a defect and requiring these vectors to move.

**Which finding this answers.** M0.12's: its corpus found an encoding defect the
`$[test]` harness structurally cannot, because a `$[test]` calls `execute` on an
already-decoded instruction and never sees a mis-encoded word. What a probe reaches is
decided by the domain the spec walks and not by what a property happens to be written
about, so the encode side is reachable by declaring it.
"""

import argparse
from collections.abc import Callable
from pathlib import Path

from vos import oracle, sailrig
from vos.corpus import find_root

type Command = Callable[[argparse.Namespace], int]


def cmd_list(args: argparse.Namespace) -> int:
    """Every spec the repository carries, and the size of each domain.

    The vector count is arithmetic over the spec rather than a measurement of a run, so
    a spec's size is readable before anything is compiled, which is what makes the
    difference between an exhaustive sweep and a sampled one a decision somebody takes
    with the number in front of them.
    """
    del args
    root = find_root()
    found = oracle.names(root)
    if not found:
        print(f"FAIL no specs under {oracle.SPECS}")
        return 1
    out: list[str] = []
    bad = 0
    for name in found:
        try:
            spec = oracle.load(root, name)
        except oracle.SpecError as err:
            out.append(f"FAIL {name}: {err}")
            bad += 1
            continue
        out.append(f"== {name}: {spec.what}")
        out.append(f"   {len(spec.sources)} model source(s), {len(spec.probes)} "
                   f"probe(s), {spec.vectors} vector(s)")
        out.append(f"   answers {spec.answers or 'no finding named'}")
        for probe in spec.probes:
            domains = ", ".join(f"{p.name}/{p.over}" for p in probe.params) or "no input"
            out.append(f"     {probe.kind:<4} {probe.vectors:>7}  {domains}")
    if bad:
        out.append(f"FAIL {bad} of {len(found)} spec(s) do not parse")
    else:
        out.append(f"ok {len(found)} spec(s) parse, "
                   f"{sum(oracle.load(root, n).vectors for n in found)} vector(s) in all")
    print("\n".join(out))
    return 1 if bad else 0


def cmd_emit(args: argparse.Namespace) -> int:
    """The generated Sail for one spec, written where the caller says.

    Runs on the host, because emission is a text transformation over a JSON file and
    needs no toolchain. What it is for is reading the harness a spec produces before
    spending two minutes compiling it.
    """
    root = find_root()
    try:
        spec = oracle.load(root, args.spec)
    except oracle.SpecError as err:
        print(f"FAIL {err}")
        return 1
    text = oracle.harness(spec, oracle.TOOL)
    if args.to:
        target = Path(args.to)
        target.write_text(text, encoding="utf-8", newline="\n")
        print(f"ok {spec.name}: {len(text.splitlines())} line(s) of Sail at {target}")
        return 0
    print(text)
    return 0


def cmd_vectors(args: argparse.Namespace) -> int:
    """The model's own answers for one spec, written out as text."""
    from vos import env  # noqa: PLC0415  (guest-only: `env.load` refuses the host)

    e = env.load()
    root = find_root()
    try:
        spec = oracle.load(root, args.spec)
    except oracle.SpecError as err:
        print(f"FAIL {err}")
        return 1

    work = oracle.work_dir(e.lane_root, spec.name)
    out: list[str] = []
    vectors = oracle.generate(root, spec, work, out)
    if vectors is None:
        print("\n".join(out))
        return 1

    kinds, total, other = sailrig.census(vectors)
    out.append(f"== {vectors} (lane {e.lane or 'primary'})")
    out.append(f"   {total} vector(s) over {len(kinds)} kind(s), and {other} "
               "commentary line(s)")
    out.extend(f"     {kind:<4} {count}" for kind, count in sorted(kinds.items()))
    if total != spec.vectors:
        out.append(f"FAIL the spec states {spec.vectors} vector(s) and the harness "
                   f"wrote {total}")
        print("\n".join(out))
        return 1
    out.append(f"ok the model emitted {total} vectors from {len(spec.sources)} of its "
               "own sources, at the domain the spec states")
    print("\n".join(out))
    return 0


COMMANDS: dict[str, tuple[Command, str]] = {
    "list": (cmd_list, "the specs this repository carries, and the size of each"),
    "emit": (cmd_emit, "the generated Sail harness for one spec"),
    "vectors": (cmd_vectors, "compile the harness against the model and run it"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        sub = subs.add_parser(name, help=help_text)
        if name in ("emit", "vectors"):
            sub.add_argument("--spec", required=True, help="which spec to run")
        if name == "emit":
            sub.add_argument("--to", metavar="PATH",
                             help="write the harness here instead of to stdout")
    args = parser.parse_args(argv)
    handler, _ = COMMANDS[args.command]
    return handler(args)

