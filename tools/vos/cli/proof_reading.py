#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read what every compiled proof constant elaborates to, and compare two readings.

`record` reads a directory of compiled proof objects: by default the proof gate's
staged compile in this lane, which must be the one its native receipt records as
passed, or `--objects DIR` for a compile made elsewhere, such as a base revision's or
a candidate's copied into a scratch directory of this lane and compiled with the
gate's flags. For each module it enumerates the constants with the audit's own
`Search`, then asks `Check` and `About` of every one and `Print` of each transparent
constant and inductive, three prover processes per module, and writes one JSON
reading that [proof-reading.schema.json](../../proof-reading.schema.json) describes.
[vos/proofreading.py](../proofreading.py) states what the reading holds and the two
normalizations it makes.

`compare BASE CANDIDATE` exits 0 only when every compared entry of the two readings
is identical, and otherwise names each difference: the reader, an added or removed
module or constant, and every field that differs.

**Outside the proof gate's identity by construction.** The gate's implementation is
the set of modules `run.py proofs` imports, and none of them imports this one, so this
command can change without invalidating a cached proof object. It imports the audit's
inventory and the gate's flags and workspace rather than restating them.

**It changes nothing it reads.** Queries compile in a scratch directory of this lane,
removed afterwards; the objects' and sources' digests are taken before and after and a
change between the two refuses the reading, as does any prover diagnostic, a query
answer larger than `--max-bytes` and anything the parse cannot place. A refused
reading writes nothing.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

from vos import env, proofaudit, proofreading, receipts
from vos.cli import Table, dispatch, positive_int
from vos.cli import proofs as proofs_cli
from vos.corpus import find_root

READING = "out/proof-reading.json"

# One query's answer, in bytes. Transparent bodies print without notations, and one
# derived decidable equality alone runs past a megabyte, yet no module's answer comes
# near this; the bound exists so that a pathological one refuses the reading rather
# than exhausting memory, as the CIC corpus exporter's does.
MAX_QUERY_BYTES = 64 * 1024 * 1024


def _query(objects: Path, scratch: Path, name: str, text: str, bound: int) -> str:
    """One prover process over the objects, its answer refused on any diagnostic.

    The answer goes to a file and its size decides before it is read, as in the CIC
    corpus exporter, so the bound is a bound on memory as well as on the reading.
    """
    source = scratch / f"{name}.v"
    source.write_text(text, encoding="utf-8", newline="")
    answer = scratch / f"{name}.out"
    try:
        with answer.open("wb") as stream:
            done = subprocess.run(
                [*env.rocq_command(), "-q", "-Q", str(objects), "", *proofs_cli.STRICT,
                 str(source)],
                cwd=scratch, stdout=stream, stderr=subprocess.PIPE, check=False)
        said = done.stderr.decode("utf-8", errors="replace").strip()
        if done.returncode or said:
            raise proofreading.ReadingError(
                f"{name} exited {done.returncode}: {said[:2000] or 'no diagnostic'}")
        if answer.stat().st_size > bound:
            raise proofreading.ReadingError(f"{name}'s answer exceeded {bound} bytes")
        return answer.read_text(encoding="utf-8")
    finally:
        answer.unlink(missing_ok=True)


def read_module(objects: Path, scratch: Path, module: str,
                bound: int = MAX_QUERY_BYTES) -> dict[str, proofreading.Entry]:
    """Every constant of one compiled module, read in three prover processes."""
    proofreading.check_module(module)
    inventory = proofreading.query_module("Inventory", module)
    listed = _query(objects, scratch, inventory, proofaudit.inventory_query(module), bound)
    names = [symbol["name"] for symbol in proofaudit.inventory(listed, module)]
    if not names:
        return {}
    facts = proofreading.query_module("Facts", module)
    stated = proofreading.answers(
        _query(objects, scratch, facts, proofreading.facts_query(module, names), bound),
        [f"{name}|{what}" for name in names for what in ("check", "about")])
    abouts = {name: proofreading.parse_about(name, proofreading.fresh_universes(
        stated[f"{name}|about"], facts)) for name in names}
    printed = [name for name in names if abouts[name].printed]
    bodies: dict[str, str] = {}
    if printed:
        query = proofreading.query_module("Bodies", module)
        bodies = proofreading.answers(
            _query(objects, scratch, query, proofreading.bodies_query(module, printed),
                   bound),
            [f"{name}|print" for name in printed])
        bodies = {key: proofreading.fresh_universes(text, query)
                  for key, text in bodies.items()}
    return {name: proofreading.entry(
        proofreading.fresh_universes(stated[f"{name}|check"], facts), abouts[name],
        bodies.get(f"{name}|print")) for name in names}


def _prover() -> tuple[str, str]:
    done = subprocess.run([*env.rocq_command(), "--version"], capture_output=True,
                          text=True, encoding="utf-8", check=False)
    banner = done.stdout.strip()
    if done.returncode or not banner:
        raise proofreading.ReadingError("the prover printed no version banner")
    return banner, receipts.digest(Path(env.rocq_command()[0]).resolve())


def modules_in(objects: Path, named: list[str] | None = None) -> list[str]:
    """The modules to read: every source the directory holds, or the ones named.

    Each needs an object at least as new as its source, since an older one describes
    a source this directory no longer holds.
    """
    present = sorted(path.stem for path in objects.glob("*.v"))
    chosen = sorted(set(named)) if named else present
    missing = sorted(set(chosen) - set(present))
    if missing:
        raise proofreading.ReadingError(f"{objects} holds no source for {', '.join(missing)}")
    if not chosen:
        raise proofreading.ReadingError(f"{objects} holds no proof source to read")
    for module in chosen:
        proofreading.check_module(module)
        source, compiled = objects / f"{module}.v", objects / f"{module}.vo"
        if not compiled.is_file():
            raise proofreading.ReadingError(f"{module}.v has no compiled object in {objects}")
        if compiled.stat().st_mtime < source.stat().st_mtime:
            raise proofreading.ReadingError(f"{module}.vo is older than {module}.v")
    return chosen


def _snapshot(objects: Path) -> dict[str, str]:
    """Every source and object in the directory, which a read must leave as it found."""
    return receipts.snapshot(objects, [*objects.glob("*.v"), *objects.glob("*.vo")])


def gate_objects(root: Path) -> Path:
    """The proof gate's staged compile, refused unless its native receipt passed it.

    The receipt binds each staged source and object by digest, so the reading is
    taken from exactly the compile the gate checked, and a lane whose last run failed
    or whose objects have since moved has nothing this command may read by default.
    """
    work = proofs_cli.workspace(root)
    objects = work / proofs_cli.PROOFS
    native = work / proofs_cli.RECEIPT
    try:
        loaded: object = json.loads(native.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise proofreading.ReadingError(
            f"this lane has no native proof receipt: {error}") from error
    if not isinstance(loaded, dict):
        raise proofreading.ReadingError(f"{native} is not a proof receipt")
    receipt = cast("dict[str, object]", loaded)
    if receipt.get("status") != "passed" or receipt.get("kernel_recheck") != "passed":
        raise proofreading.ReadingError(f"{native} records no passing proof run")
    staged = sorted(objects.glob("*.v"))
    inputs = receipt.get("inputs")
    recorded = ({name: digest for name, digest in cast("dict[str, str]", inputs).items()
                 if name.startswith(f"{proofs_cli.PROOFS}/")}
                if isinstance(inputs, dict) else None)
    if not staged or receipts.snapshot(work, staged) != recorded:
        raise proofreading.ReadingError("the staged proof sources are not the ones the "
                                        "native receipt passed")
    compiled = receipts.snapshot(work, [path.with_suffix(".vo") for path in staged])
    if compiled != receipt.get("outputs"):
        raise proofreading.ReadingError("the staged proof objects are not the ones the "
                                        "native receipt passed")
    return objects


def record(root: Path, objects: Path, named: list[str] | None, jobs: int,
           bound: int = MAX_QUERY_BYTES) -> proofreading.Reading:
    """One complete reading of the directory's modules, or a refusal."""
    modules = modules_in(objects, named)
    before = _snapshot(objects)
    prover, prover_sha256 = _prover()
    lane = env.lane_root(env.lane_of(root)) / "proof-reading"
    lane.mkdir(parents=True, exist_ok=True)
    read: dict[str, dict[str, proofreading.Entry]] = {}
    failed: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="record-", dir=lane) as temporary:
        scratch = Path(temporary)

        def one(module: str) -> None:
            try:
                read[module] = read_module(objects, scratch, module, bound)
            except (OSError, ValueError) as error:
                failed[module] = str(error)
                return
            printed = sum(entry["print"] is not None for entry in read[module].values())
            print(f"  {module}: {len(read[module])} constant(s), {printed} printed",
                  flush=True)

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(one, modules))
    if failed:
        raise proofreading.ReadingError("; ".join(
            f"{module}: {failed[module]}" for module in sorted(failed)))
    if _snapshot(objects) != before:
        raise proofreading.ReadingError(f"the sources or objects in {objects} changed "
                                        "while they were read")
    return proofreading.validate({
        "format": proofreading.FORMAT, "schema": proofreading.SCHEMA,
        "reader": {"prover": prover, "prover_sha256": prover_sha256,
                   "query_flags": list(proofs_cli.STRICT),
                   "inventory_settings": proofaudit.SETTINGS,
                   "reading_settings": proofreading.SETTINGS},
        "modules": {module: {"constants": read[module]} for module in modules},
        "provenance": {
            "sources": {f"{module}.v": before[f"{module}.v"] for module in modules},
            "objects": {f"{module}.vo": before[f"{module}.vo"] for module in modules}}})


def _record(args: argparse.Namespace) -> int:
    root = find_root()
    target = Path(args.out) if args.out else root / READING
    started = time.perf_counter()
    try:
        objects = Path(args.objects).resolve() if args.objects else gate_objects(root)
        reading = record(root, objects, args.module, args.jobs or env.proof_jobs(),
                         args.max_bytes)
    except (OSError, ValueError) as error:
        print(f"FAIL proof-reading: {error}")
        return 1
    receipts.write(target, reading)
    constants = [entry for module in reading["modules"].values()
                 for entry in module["constants"].values()]
    printed = sum(entry["print"] is not None for entry in constants)
    print(f"ok proof-reading: {len(constants)} constant(s) over {len(reading['modules'])} "
          f"module(s), {printed} printed; reading: {target} "
          f"({target.stat().st_size} bytes); {time.perf_counter() - started:.1f}s")
    return 0


def _compare(args: argparse.Namespace) -> int:
    try:
        base = proofreading.load(Path(args.base))
        candidate = proofreading.load(Path(args.candidate))
    except (OSError, ValueError) as error:
        print(f"FAIL proof-reading: {error}")
        return 1
    differences = proofreading.compare(base, candidate)
    if differences:
        print(f"FAIL proof-reading: {len(differences)} difference(s) between "
              f"{args.base} and {args.candidate}")
        for difference in differences:
            print(f"  {difference}")
        return 1
    count = sum(len(module["constants"]) for module in base["modules"].values())
    print(f"ok proof-reading: {args.base} and {args.candidate} read identically: "
          f"{count} constant(s) over {len(base['modules'])} module(s)")
    return 0


TABLE: Table = {
    "record": (_record, "read every constant of a compiled proof directory into JSON"),
    "compare": (_compare, "name every entry two readings disagree about"),
}


def _flags(name: str, parser: argparse.ArgumentParser) -> None:
    if name == "record":
        parser.add_argument("--objects", metavar="DIR",
                            help="a directory of compiled proofs (default: the proof "
                                 "gate's passing compile in this lane)")
        parser.add_argument("--module", action="append", metavar="NAME",
                            help="read only this module (repeatable; default: every "
                                 "source in the directory)")
        parser.add_argument("--out", help=f"where to write the reading (default {READING})")
        parser.add_argument("--jobs", type=positive_int,
                            help="modules read at once (default: the proof gate's "
                                 "compile limit)")
        parser.add_argument("--max-bytes", type=positive_int, default=MAX_QUERY_BYTES,
                            help="bound on one query's answer; beyond it the reading "
                                 "is refused")
    else:
        parser.add_argument("base", help="the reading taken first")
        parser.add_argument("candidate", help="the reading held against it")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py proof-reading")


if __name__ == "__main__":
    sys.exit(main())
