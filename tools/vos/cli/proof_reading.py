#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read what every compiled proof constant elaborates to, and compare two readings.

`record` reads a passing compile of the proof sources, and only one. By default it is
the proof gate's staged compile in this lane, whose native receipt must record a
passing run and names every staged source and object by digest. `--sources DIR`
instead copies the proof sources in DIR, such as a base revision's or a candidate's,
into a scratch directory of this lane and compiles them there as the gate does, so an
object compiled anywhere else, stale or current, is never read as a source's meaning.
For each module it enumerates the constants with the audit's own `Search`, then asks
`Check` and `About` of every one and `Print` of each transparent constant and
inductive, three prover processes per module, and writes one JSON reading that
[proof-reading.schema.json](../../proof-reading.schema.json) describes.
[vos/proofreading.py](../proofreading.py) states what the reading holds and the two
normalizations it makes.

`compare BASE CANDIDATE` exits 0 only when every compared entry of the two readings
is identical, and otherwise names each difference: the reader, an added or removed
module or constant, and every field that differs.

**Outside the proof gate's identity by construction.** The gate's implementation is
the set of modules `run.py proofs` imports, and none of them imports this one, so this
command can change without invalidating a cached proof object. It imports the audit's
inventory and the gate's flags and workspace rather than restating them.

**It reads only what the compile made, and changes nothing it reads.** Every source
and object in the directory must carry the digest the receipt, or the compile this
command ran, recorded for it, when the read begins and again when it ends. Queries
compile in a scratch directory of this lane, removed afterwards. Any prover diagnostic,
a query answer larger than `--max-bytes` and anything the parse cannot place each
refuse the reading, and a refused reading writes nothing.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

from vos import env, proofaudit, proofreading, proofs, receipts
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
    """The modules to read: every source the directory holds, or the ones named."""
    present = sorted(path.stem for path in objects.glob("*.v"))
    chosen = sorted(set(named)) if named else present
    missing = sorted(set(chosen) - set(present))
    if missing:
        raise proofreading.ReadingError(f"{objects} holds no source for {', '.join(missing)}")
    if not chosen:
        raise proofreading.ReadingError(f"{objects} holds no proof source to read")
    for module in chosen:
        proofreading.check_module(module)
        if not (objects / f"{module}.vo").is_file():
            raise proofreading.ReadingError(f"{module}.v has no compiled object in {objects}")
    return chosen


def _snapshot(objects: Path) -> dict[str, str]:
    """Every source and object in the directory, which a read must leave as it found."""
    return receipts.snapshot(objects, [*objects.glob("*.v"), *objects.glob("*.vo")])


def _scratch(root: Path, prefix: str) -> tempfile.TemporaryDirectory[str]:
    """A directory of this lane's native build area, removed when it is closed."""
    lane = env.lane_root(env.lane_of(root)) / "proof-reading"
    lane.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=lane)


def gate_objects(root: Path) -> tuple[Path, dict[str, str]]:
    """The proof gate's staged compile, and the digests its native receipt passed.

    The receipt names each staged source among its inputs and each object among its
    outputs, relative to the gate's workspace; they are returned relative to the staged
    directory, where `record` holds the files to them. A lane whose last run failed, or
    whose staged files have moved since the run that passed, has nothing to read.
    """
    work = proofs_cli.workspace(root)
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
    inputs, outputs = receipt.get("inputs"), receipt.get("outputs")
    if not isinstance(inputs, dict) or not isinstance(outputs, dict):
        raise proofreading.ReadingError(f"{native} names no inputs and outputs")
    # The gate's own reading of its receipt: every input under the staged directory is
    # a staged source, and every output is its object.
    prefix = f"{proofs_cli.PROOFS}/"
    recorded = {**cast("dict[str, str]", inputs), **cast("dict[str, str]", outputs)}
    passed = {name.removeprefix(prefix): digest for name, digest in recorded.items()
              if name.startswith(prefix)}
    if not passed:
        raise proofreading.ReadingError(f"{native} names no staged proof source")
    return work / proofs_cli.PROOFS, passed


def compile_sources(sources: Path, objects: Path, jobs: int) -> dict[str, str]:
    """Copy a directory's proof sources into `objects` and compile them as the gate does.

    Only the sources are copied, so an object beside them is never read. A copy holding
    anything the gate refuses before compiling refuses here before anything compiles: a
    token the shared lexer cannot follow, a coinductive form or a token hiding one, a
    loaded file or plugin, a module body the native inventory cannot enumerate, or a
    reset of a setting the gate pins. The copies
    then compile under the gate's flags in its dependency waves, and a compile that
    exits nonzero or prints anything refuses. The result is the digest of every copy
    and object, which is the compile `record` may read.
    """
    found = sorted(sources.glob("*.v"))
    if not found:
        raise proofreading.ReadingError(f"{sources} holds no proof source to compile")
    for source in found:
        proofreading.check_module(source.stem)
        shutil.copyfile(source, objects / source.name)
    copies = sorted(objects.glob("*.v"))
    for copy in copies:
        text = copy.read_text(encoding="utf-8")
        refused = [*proofaudit.unreadable_tokens(text), *proofaudit.coinductive_forms(text),
                   *proofaudit.dynamic_sources(text), *proofaudit.unsupported_abstractions(text),
                   *proofaudit.pinned_overrides(text)]
        if refused:
            raise proofreading.ReadingError(
                f"{copy.name} holds what the proof gate refuses before compiling: "
                + "; ".join(refused)[:2000])
    try:
        ordered = proofs.waves(copies)
    except SystemExit as error:  # the gate's own refusal of a Require cycle
        raise proofreading.ReadingError(str(error)) from error

    def one(source: Path) -> str:
        done = subprocess.run(
            [*env.rocq_command(), "-q", "-Q", str(objects), "", *proofs_cli.STRICT,
             source.name], cwd=objects, capture_output=True, text=True, encoding="utf-8",
            check=False)
        said = (done.stderr + done.stdout).strip()
        return (f"{source.name} exited {done.returncode}: {said[:2000] or 'no diagnostic'}"
                if done.returncode or said else "")

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for wave in ordered:
            failed = [failure for failure in pool.map(one, wave) if failure]
            if failed:
                raise proofreading.ReadingError("; ".join(failed))
    return _snapshot(objects)


def record(root: Path, objects: Path, passed: dict[str, str], named: list[str] | None,
           jobs: int, bound: int = MAX_QUERY_BYTES) -> proofreading.Reading:
    """One complete reading of a passing compile's modules, or a refusal.

    `passed` is the digest of every source and object the compile made, as its receipt
    or its own run recorded them, relative to `objects`. The directory must hold
    exactly those files when the read begins and again when it ends.
    """
    modules = modules_in(objects, named)
    before = _snapshot(objects)
    if before != passed:
        raise proofreading.ReadingError(f"the sources and objects in {objects} are not "
                                        "the ones a passing compile made")
    prover, prover_sha256 = _prover()
    read: dict[str, dict[str, proofreading.Entry]] = {}
    failed: dict[str, str] = {}
    with _scratch(root, "record-") as temporary:
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
        raise proofreading.ReadingError(f"the sources and objects in {objects} changed "
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


def record_sources(root: Path, sources: Path, named: list[str] | None, jobs: int,
                   bound: int = MAX_QUERY_BYTES) -> proofreading.Reading:
    """A reading of a directory's proof sources, which it compiles first as the gate does."""
    with _scratch(root, "compile-") as temporary:
        objects = Path(temporary)
        return record(root, objects, compile_sources(sources, objects, jobs), named, jobs,
                      bound)


def _record(args: argparse.Namespace) -> int:
    root = find_root()
    target = Path(args.out) if args.out else root / READING
    started = time.perf_counter()
    try:
        jobs = args.jobs or env.proof_jobs()
        if args.sources:
            reading = record_sources(root, Path(args.sources).resolve(), args.module, jobs,
                                     args.max_bytes)
        else:
            objects, passed = gate_objects(root)
            reading = record(root, objects, passed, args.module, jobs, args.max_bytes)
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
    "record": (_record, "read every constant of a passing proof compile into JSON"),
    "compare": (_compare, "name every entry two readings disagree about"),
}


def _flags(name: str, parser: argparse.ArgumentParser) -> None:
    if name == "record":
        parser.add_argument("--sources", metavar="DIR",
                            help="compile the proof sources in DIR here, as the gate "
                                 "does, and read that compile (default: the proof "
                                 "gate's passing compile in this lane)")
        parser.add_argument("--module", action="append", metavar="NAME",
                            help="read only this module (repeatable; default: every "
                                 "source compiled)")
        parser.add_argument("--out", help=f"where to write the reading (default {READING})")
        parser.add_argument("--jobs", type=positive_int,
                            help="modules compiled or read at once (default: the proof "
                                 "gate's compile limit)")
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
