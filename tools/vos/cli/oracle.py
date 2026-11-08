#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The model-as-oracle vector generator: any Sail function, as a differential oracle.

Compiles and runs declarative vector specs ([vos/oracle.py](../oracle.py)) against the
curated Sail model:

    python tools/run.py oracle list                     # list specs and vector counts
    python tools/run.py oracle emit --spec capformat    # emit Sail harness on the host
    python tools/run.py oracle vectors --spec capformat # compile and emit vectors in WSL
    python tools/run.py oracle vectors --spec keccak

`list` and `emit` run on the host; `vectors` compiles and runs the generated Sail harness
in the guest lane's working directory. Use [tools/vos/cli/seed.py](seed.py) to measure
mutation sensitivity of the generated vectors.
"""

import argparse
from pathlib import Path

from vos import cli, oracle, sailrig
from vos.corpus import find_root


def cmd_list(args: argparse.Namespace) -> int:
    """List every oracle spec and its statically computed vector count."""
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
    """Emit the generated Sail harness for one spec."""
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


COMMANDS: cli.Table = {
    "list": (cmd_list, "the specs this repository carries, and the size of each"),
    "emit": (cmd_emit, "the generated Sail harness for one spec"),
    "vectors": (cmd_vectors, "compile the harness against the model and run it"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name in ("emit", "vectors"):
        sub.add_argument("--spec", required=True, help="which spec to run")
    if name == "emit":
        sub.add_argument("--to", metavar="PATH",
                         help="write the harness here instead of to stdout")


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, _flags, prog="run.py oracle")

